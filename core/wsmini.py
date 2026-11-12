"""WebSocket (RFC 6455) без сторонних библиотек — клиент для ноды Лиры (core/liranode.py; та же копия — в агенте узла
server/dwrapp/lira-node.py, там только стандартный Python) и кадры для ретранслятора (core/netrelay.py).

Только то, что нужно сети Лиры: текстовые сообщения JSON до MSG_MAX, ping/pong, close; ws:// и wss://. Клиент маскирует
кадры (так требует RFC), сервер — нет. Ошибка связи — WSError: нода сразу возвращается к обычному опросу сайта."""
import base64
import hashlib
import json
import os
import socket
import ssl
import struct
import time
from urllib.parse import urlsplit

GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC11B65"
MSG_MAX = 262_144            # сообщение больше 256 КБ — обрыв: задание и ответ узла и так меньше
OP_CONT, OP_TEXT, OP_BIN, OP_CLOSE, OP_PING, OP_PONG = 0, 1, 2, 8, 9, 10


class WSError(Exception):
    pass


def accept_key(key):
    return base64.b64encode(hashlib.sha1((key + GUID).encode()).digest()).decode()


def frame(op, data=b"", mask=False):
    """Один кадр (FIN): клиент — с маской, сервер — без."""
    n = len(data)
    head = bytes([0x80 | op])
    mbit = 0x80 if mask else 0
    if n < 126:
        head += bytes([mbit | n])
    elif n < 65536:
        head += bytes([mbit | 126]) + struct.pack(">H", n)
    else:
        head += bytes([mbit | 127]) + struct.pack(">Q", n)
    if not mask:
        return head + data
    m = os.urandom(4)
    return head + m + bytes(b ^ m[i % 4] for i, b in enumerate(data))


def unmask(m, data):
    return bytes(b ^ m[i % 4] for i, b in enumerate(data))


class Client:
    """Соединение ноды с ретранслятором: send(obj), recv(timeout) -> obj | None (тишина), close()."""

    def __init__(self, url, headers=None, timeout=10, ctx=None):
        u = urlsplit(url)
        if u.scheme not in ("ws", "wss"):
            raise WSError("адрес ретранслятора не ws:// и не wss://")
        host, port = u.hostname or "", u.port or (443 if u.scheme == "wss" else 80)
        try:
            s = socket.create_connection((host, port), timeout=timeout)
            if u.scheme == "wss":
                s = (ctx or ssl.create_default_context()).wrap_socket(s, server_hostname=host)
        except (OSError, ssl.SSLError) as e:
            raise WSError(f"нет связи с ретранслятором: {e}") from e
        self.sock, self.buf, self.closed = s, b"", False
        key = base64.b64encode(os.urandom(16)).decode()
        path = (u.path or "/") + ("?" + u.query if u.query else "")
        hdr = "".join(f"{k}: {v}\r\n" for k, v in (headers or {}).items())
        req = (f"GET {path} HTTP/1.1\r\nHost: {u.netloc}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
               f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n{hdr}\r\n")
        try:
            s.sendall(req.encode())
            head = self._until(b"\r\n\r\n", 16384, timeout)
        except (OSError, ssl.SSLError) as e:
            self.close()
            raise WSError(f"ретранслятор не ответил: {e}") from e
        lines = head.decode("latin-1").split("\r\n")
        if not lines[0].startswith("HTTP/1.1 101"):
            self.close()
            raise WSError("ретранслятор недоступен по этому адресу: " + lines[0][:80])
        h = {ln.split(":", 1)[0].strip().lower(): ln.split(":", 1)[1].strip() for ln in lines[1:] if ":" in ln}
        if h.get("sec-websocket-accept") != accept_key(key):
            self.close()
            raise WSError("ответ ретранслятора не по протоколу")

    def _until(self, mark, limit, timeout):
        end = time.monotonic() + timeout
        while mark not in self.buf:
            if len(self.buf) > limit:
                raise WSError("слишком длинный ответ")
            left = end - time.monotonic()
            if left <= 0:
                raise socket.timeout("timed out")
            self.sock.settimeout(left)
            ch = self.sock.recv(65536)
            if not ch:
                raise WSError("соединение закрыто")
            self.buf += ch
        i = self.buf.index(mark) + len(mark)
        out, self.buf = self.buf[:i], self.buf[i:]
        return out

    def _need(self, n, end):
        while len(self.buf) < n:
            left = end - time.monotonic() if end else None
            if left is not None and left <= 0:
                raise socket.timeout("timed out")
            self.sock.settimeout(left)
            ch = self.sock.recv(65536)
            if not ch:
                raise WSError("ретранслятор закрыл соединение")
            self.buf += ch
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def send(self, obj):
        if self.closed:
            raise WSError("соединение закрыто")
        try:
            self.sock.settimeout(15)
            self.sock.sendall(frame(OP_TEXT, json.dumps(obj, ensure_ascii=False).encode(), mask=True))
        except (OSError, ssl.SSLError) as e:
            self.close()
            raise WSError(f"обрыв связи с ретранслятором: {e}") from e

    def recv(self, timeout):
        """Следующее сообщение JSON или None, если за timeout секунд ничего не пришло. Ping — ответ сам; close — WSError."""
        end = time.monotonic() + max(0.01, timeout)
        parts, total = [], 0
        try:
            while True:
                if not self.buf:
                    left = end - time.monotonic()
                    if left <= 0:
                        return None
                    self.sock.settimeout(left)
                    try:
                        ch = self.sock.recv(65536)
                    except socket.timeout:
                        return None
                    if not ch:
                        raise WSError("ретранслятор закрыл соединение")
                    self.buf += ch
                # кадр начался — дочитываем его целиком (не дольше 20 с)
                lim = time.monotonic() + 20
                b0, b1 = self._need(2, lim)
                op, n = b0 & 0x0F, b1 & 0x7F
                if n == 126:
                    n = struct.unpack(">H", self._need(2, lim))[0]
                elif n == 127:
                    n = struct.unpack(">Q", self._need(8, lim))[0]
                if n > MSG_MAX or total + n > MSG_MAX:
                    raise WSError("слишком большое сообщение")
                m = self._need(4, lim) if b1 & 0x80 else None
                data = self._need(n, lim) if n else b""
                if m:
                    data = unmask(m, data)
                if op == OP_PING:
                    self.sock.sendall(frame(OP_PONG, data, mask=True))
                    continue
                if op == OP_PONG:
                    continue
                if op == OP_CLOSE:
                    self.close()
                    raise WSError("ретранслятор закрыл соединение" + (": " + data[2:].decode("utf-8", "replace") if len(data) > 2 else ""))
                parts.append(data)
                total += n
                if b0 & 0x80:
                    try:
                        obj = json.loads(b"".join(parts).decode("utf-8"))
                    except ValueError as e:
                        raise WSError("сообщение не JSON") from e
                    if isinstance(obj, dict) and "ping" in obj:          # «жив?» ретранслятора — ответ сразу
                        self.send({"pong": obj["ping"]})
                        parts, total = [], 0
                        continue
                    return obj
        except socket.timeout as e:
            self.close()
            raise WSError("ретранслятор замолчал посреди сообщения") from e
        except (OSError, ssl.SSLError) as e:
            self.close()
            raise WSError(f"обрыв связи с ретранслятором: {e}") from e

    def close(self):
        if self.closed:
            return
        self.closed = True
        try:
            self.sock.settimeout(2)
            self.sock.sendall(frame(OP_CLOSE, struct.pack(">H", 1000), mask=True))
        except (OSError, ssl.SSLError):
            pass
        try:
            self.sock.close()
        except OSError:
            pass
