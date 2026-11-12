"""Ретранслятор Сети Лиры (0.92, владелец 12.11: «чтобы держала любое количество пользовательских мощностей… основа для
устойчивой надёжной Лиры»).

Раньше каждая нода держала длинный опрос /net/pull прямо в PHP сайта — один обработчик PHP на ноду, поэтому на связи было
не больше 16 нод разом. Теперь ноды держат одно лёгкое соединение WebSocket с этой службой (asyncio: тысячи соединений —
мегабайты памяти), а сайт трогается только по делу:

  нода ──WebSocket── ретранслятор ──HTTP с ключом исполнителя── cloud.php (liranet.php: /net/relay/*)

• hello  — нода пришла со своим ключом (nk-…): сайт проверяет ключ, бан, место (net_max_nodes на человека) → её номера;
• beat   — раз в BEAT с (и сразу, когда кто-то пришёл, ушёл, освободился): кто на связи и кто свободен → сайт отмечает
           «на связи» (last_ok), считает сутки, ставит проверки по расписанию и сразу отдаёт задания, которым пришло время;
• wait   — один длинный опрос сайта на всю сеть (/net/relay/wait): вопрос ноде положен → сайт тут же «взято» → job ноде; путь от
           сайта к службе не нужен (сайт может быть в Docker); если он есть — сайт ещё и толкает сам (notify, net_relay_local);
• done   — ответ ноды уходит в /net/done её же ключом (сайт проверяет всё, как раньше).
Протокол задания тот же, что у опроса: job {id, port, body} → done {id, code, body}. Нода, которая не дошла сюда (нет
маршрута в nginx, старая программа), работает по-старому — опросом PHP.

Запуск — служба dewiar-relay (тот же пользователь и /etc/dewiar-runner.env, что у исполнителя; ставит её автообновление
сервера): python3 netrelay.py. Слушает RELAY_HOST:RELAY_PORT (служба — 0.0.0.0:8790: входной nginx может стоять на другой
машине домашней сети); снаружи — через nginx: location /dwrapp/relay (с Upgrade).
Только стандартный Python."""
import asyncio
import json
import logging
import os
import re
import struct
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wsmini  # noqa: E402

VERSION = 1
BEAT = 10                  # с между «пульсами» сайту (раньше — если кто-то пришёл, ушёл или освободился)
PING = 25                  # с между «жив?» ноде (nginx по умолчанию рвёт молчание через 60 с)
DEAD = 75                  # с без единого сообщения от ноды — соединение закрываем
WAIT = int(os.environ.get("RELAY_WAIT", "20"))   # с — длинный опрос сайта «есть ли вопросы моим нодам»
BUSY_MAX = 40              # задание у ноды дольше — считаем брошенным (сайт и так ждёт не больше 12 с)
MAX_CONN = int(os.environ.get("RELAY_MAX", "5000"))
HELLO_MAX = 20             # неудачных входов с одного адреса в минуту
log = logging.getLogger("dewiar.relay")


class Site:
    """Запросы к cloud.php ключом исполнителя (в потоке: urllib блокирует)."""

    def __init__(self, url, key):
        self.url, self.key = url.rstrip("/"), key

    def _call(self, path, body, node_key="", timeout=15):
        sep = "&" if "?" in self.url else "?"
        hdr = {"Content-Type": "application/json", "X-Runner-Key": self.key}
        if node_key:
            hdr = {"Content-Type": "application/json", "Authorization": "Bearer " + node_key}
        req = urllib.request.Request(f"{self.url}{sep}p={path}", data=json.dumps(body, ensure_ascii=False).encode(), headers=hdr)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as f:
                return json.loads(f.read(1_000_000).decode("utf-8") or "{}")
        except urllib.error.HTTPError as e:
            try:
                d = json.loads(e.read(65536).decode("utf-8") or "{}")
            except ValueError:
                d = {}
            err = d.get("error") if isinstance(d, dict) else None
            return {"ok": False, "http": e.code, "error": (err.get("message") if isinstance(err, dict) else err) or f"сайт ответил {e.code}"}
        except (OSError, ValueError) as e:
            return {"ok": False, "http": 0, "error": f"нет связи с сайтом: {e}"}

    async def call(self, path, body, node_key="", timeout=15):
        return await asyncio.to_thread(self._call, path, body, node_key, timeout)


class Conn:
    def __init__(self, reader, writer, key, peer):
        self.r, self.w, self.key, self.peer = reader, writer, key, peer
        self.ids, self.grp, self.on = [], "", False
        self.ready = False          # нода сейчас ждёт задание (сама сказала «ready»)
        self.busy = ""              # id задания, которое у неё в руках
        self.busy_at = 0.0
        self.last_rx = time.monotonic()
        self.lock = asyncio.Lock()
        self.closed = False

    @property
    def nid(self):
        return min(self.ids) if self.ids else 0

    async def send(self, obj):
        if self.closed:
            return
        async with self.lock:
            try:
                self.w.write(wsmini.frame(wsmini.OP_TEXT, json.dumps(obj, ensure_ascii=False).encode()))
                await asyncio.wait_for(self.w.drain(), 15)
            except (OSError, asyncio.TimeoutError, ConnectionError):
                self.closed = True

    async def close(self, why=""):
        if self.closed:
            return
        if why:
            await self.send({"bye": why})
        self.closed = True
        try:
            self.w.write(wsmini.frame(wsmini.OP_CLOSE, struct.pack(">H", 1000) + why.encode()[:120]))
            await asyncio.wait_for(self.w.drain(), 3)
        except (OSError, asyncio.TimeoutError, ConnectionError):
            pass
        try:
            self.w.close()
        except OSError:
            pass


class Relay:
    def __init__(self, site_url, key, host="127.0.0.1", port=8790):
        self.site = Site(site_url, key)
        self.key, self.host, self.port = key, host, port
        self.conns = set()
        self.by_id = {}             # номер узла -> соединение
        self.changed = asyncio.Event()
        self.rules_ver = 0
        self.ws_ok = 0              # сколько нод пришло по WebSocket с начала работы (маршрут nginx жив)
        self.tries = {}             # адрес -> времена неудачных входов (больше HELLO_MAX в минуту — отказ, сайт не дёргаем)
        self.server = None

    # ------------------------------------------------------------ HTTP ------------------------------------------------------------
    async def handle(self, reader, writer):
        peer = (writer.get_extra_info("peername") or ("?",))[0]
        try:
            head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 15)
        except (asyncio.IncompleteReadError, asyncio.LimitOverrunError, asyncio.TimeoutError, ConnectionError):
            writer.close()
            return
        lines = head.decode("latin-1").split("\r\n")
        try:
            method, path, _ = lines[0].split(" ", 2)
        except ValueError:
            writer.close()
            return
        h = {ln.split(":", 1)[0].strip().lower(): ln.split(":", 1)[1].strip() for ln in lines[1:] if ":" in ln}
        path = path.split("?", 1)[0].rstrip("/")
        if h.get("upgrade", "").lower() == "websocket" and path.endswith("/relay"):
            return await self.ws(reader, writer, h, h.get("x-real-ip") or peer)
        if path.endswith("/relay/health"):
            return self.reply(writer, 200, {"ok": True, "relay": VERSION, "conns": len(self.conns)})
        if path.endswith("/relay/notify") and method == "POST":
            if h.get("x-runner-key", "") != self.key or not self.key:
                return self.reply(writer, 403, {"ok": False})
            try:
                n = min(65536, int(h.get("content-length") or 0))
                body = json.loads((await asyncio.wait_for(reader.readexactly(n), 5)).decode() or "{}") if n else {}
            except (ValueError, asyncio.IncompleteReadError, asyncio.TimeoutError):
                body = {}
            ids = [int(x) for x in (body.get("ids") or []) if str(x).isdigit()]
            for c in {self.by_id[i] for i in ids if i in self.by_id}:
                asyncio.create_task(self.take(c))
            return self.reply(writer, 200, {"ok": True})
        return self.reply(writer, 404, {"ok": False, "error": "нет такого адреса"})

    @staticmethod
    def reply(writer, code, obj):
        b = json.dumps(obj, ensure_ascii=False).encode()
        writer.write(f"HTTP/1.1 {code} X\r\nContent-Type: application/json\r\nContent-Length: {len(b)}\r\nConnection: close\r\n\r\n".encode() + b)
        try:
            writer.close()
        except OSError:
            pass

    # ---------------------------------------------------------- WebSocket ----------------------------------------------------------
    async def ws(self, reader, writer, h, peer):
        key = h.get("sec-websocket-key", "")
        tok = re.sub(r"^Bearer\s+", "", h.get("authorization", ""))
        if not key or not re.fullmatch(r"nk-[0-9a-f]{48}", tok):
            return self.reply(writer, 401, {"ok": False, "error": "нужен ключ узла"})
        if len(self.conns) >= MAX_CONN:
            return self.reply(writer, 503, {"ok": False, "error": "ретранслятор полон"})
        now = time.monotonic()
        t = [x for x in self.tries.get(peer, []) if now - x < 60]
        if len(t) >= HELLO_MAX:
            return self.reply(writer, 429, {"ok": False, "error": "слишком часто — подождите минуту"})
        if len(self.tries) > 50000:
            self.tries = {k: v for k, v in self.tries.items() if v and now - v[-1] < 60}
        writer.write(("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                      f"Sec-WebSocket-Accept: {wsmini.accept_key(key)}\r\n\r\n").encode())
        c = Conn(reader, writer, tok, peer)
        d = await self.site.call("/net/relay/hello", {"key": tok, "ip": peer})
        if not d.get("ok"):
            self.tries[peer] = t + [now]                 # считаем только неудачные входы (чужой ключ, бан)
            await c.send({"hello": {"ok": False, "error": d.get("error") or "сайт не принял узел", "code": d.get("code") or ""}})
            return await c.close("не принят")
        c.ids, c.grp, c.on = [int(x) for x in d.get("ids") or []], str(d.get("grp") or ""), bool(d.get("on"))
        self.rules_ver = int(d.get("rules_ver") or self.rules_ver)
        # одна нода — одно соединение: прежнее (старая вкладка, обрыв без закрытия) — закрыть
        for old in {self.by_id[i] for i in c.ids if i in self.by_id}:
            await old.close("узел подключился заново")
            self.drop(old)
        gmax = int(d.get("gmax") or 0)
        if gmax and c.grp and sum(1 for x in self.conns if x.grp == c.grp) >= gmax:
            await c.send({"hello": {"ok": False, "error": "у этого человека уже на связи все его ноды", "code": "group_full"}})
            return await c.close("все места заняты")
        self.conns.add(c)
        for i in c.ids:
            self.by_id[i] = c
        self.ws_ok += 1
        await c.send({"hello": {"ok": True, "on": c.on, "state": d.get("state") or "", "rules_ver": self.rules_ver, "beat": BEAT}})
        self.changed.set()
        try:
            await self.read_loop(c)
        finally:
            self.drop(c)
            await c.close()
            self.changed.set()

    def drop(self, c):
        self.conns.discard(c)
        for i in c.ids:
            if self.by_id.get(i) is c:
                del self.by_id[i]

    async def read_loop(self, c):
        parts = []
        while not c.closed:
            try:
                b0, b1 = await asyncio.wait_for(c.r.readexactly(2), DEAD)
                op, n = b0 & 0x0F, b1 & 0x7F
                if n == 126:
                    n = struct.unpack(">H", await c.r.readexactly(2))[0]
                elif n == 127:
                    n = struct.unpack(">Q", await c.r.readexactly(8))[0]
                if n > wsmini.MSG_MAX or not b1 & 0x80:          # кадры клиента обязаны быть с маской
                    return
                m = await c.r.readexactly(4)
                data = wsmini.unmask(m, await asyncio.wait_for(c.r.readexactly(n), 30)) if n else b""
            except (asyncio.IncompleteReadError, asyncio.TimeoutError, ConnectionError, OSError):
                return
            c.last_rx = time.monotonic()
            if op == wsmini.OP_CLOSE:
                return
            if op == wsmini.OP_PING:
                async with c.lock:
                    c.w.write(wsmini.frame(wsmini.OP_PONG, data))
                continue
            if op in (wsmini.OP_PONG,):
                continue
            parts.append(data)
            if sum(len(x) for x in parts) > wsmini.MSG_MAX:
                return
            if not b0 & 0x80:
                continue
            try:
                msg = json.loads(b"".join(parts).decode("utf-8"))
            except ValueError:
                return
            parts = []
            if isinstance(msg, dict):
                await self.on_msg(c, msg)

    async def on_msg(self, c, msg):
        if "ready" in msg:
            was = c.ready
            c.ready = bool(msg["ready"]) and not c.busy
            if c.ready != was:
                self.changed.set()
                if c.ready:
                    asyncio.create_task(self.take(c))          # пока ноды не было в ожидании, могло прийти задание
        if "done" in msg and isinstance(msg["done"], dict):
            d = msg["done"]
            if not c.busy:                              # заданий у неё нет — сайт не дёргаем
                await c.send({"ack": {"id": d.get("id"), "ok": False}})
                return
            r = await self.site.call("/net/done", {k: d[k] for k in ("id", "code", "body", "away") if k in d}, node_key=c.key, timeout=20)
            c.busy, c.ready = "", False
            self.changed.set()
            await c.send({"ack": {"id": d.get("id"), "ok": bool(r.get("ok"))}})

    # ------------------------------------------------------------ задания ------------------------------------------------------------
    async def take(self, c):
        """Задание этой ноде, если сайт его приготовил (вопрос человека или проверка, которой пришло время)."""
        if c.closed or not c.ready or c.busy:
            log.debug("take %s: пропуск closed=%s ready=%s busy=%s", c.ids, c.closed, c.ready, c.busy)
            return
        d = await self.site.call("/net/relay/take", {"ids": c.ids})
        log.debug("take %s -> %s", c.ids, "job" if d.get("job") else d)
        if d.get("job") and not await self.give(c, d["job"]):
            await self.site.call("/net/done", {"id": d["job"].get("id"), "code": 0, "body": "", "away": True}, node_key=c.key, timeout=15)

    async def give(self, c, job):
        """Отдать задание ноде. -> False — она не ждёт (ушла, занята): задание надо вернуть."""
        if c.closed or not c.ready or c.busy:
            return False
        c.busy, c.busy_at, c.ready = str(job.get("id") or "?"), time.monotonic(), False
        await c.send({"job": job, "rules_ver": self.rules_ver})
        self.changed.set()
        return True

    async def beat_loop(self):
        while True:
            try:
                await asyncio.wait_for(self.changed.wait(), BEAT)
                await asyncio.sleep(0.3)                    # пачкой: пришли сразу несколько — один запрос
            except asyncio.TimeoutError:
                pass
            self.changed.clear()
            now = time.monotonic()
            for c in list(self.conns):
                if c.busy and now - c.busy_at > BUSY_MAX:
                    c.busy = ""
                if now - c.last_rx > DEAD:
                    await c.close("молчание")
                    self.drop(c)
            conns = [{"ids": c.ids, "ready": c.ready, "busy": bool(c.busy)} for c in self.conns]
            d = await self.site.call("/net/relay/beat", {"conns": conns, "ws_ok": self.ws_ok, "relay": VERSION})
            if not d.get("ok"):
                log.warning("сайт не принял пульс: %s", d.get("error"))
                continue
            self.rules_ver = int(d.get("rules_ver") or self.rules_ver)
            for nid in d.get("bye") or []:
                c = self.by_id.get(int(nid))
                if c:
                    await c.close("узел отключён на сайте")
                    self.drop(c)
            for nid, job in (d.get("jobs") or {}).items():
                c = self.by_id.get(int(nid))
                if c and not await self.give(c, job):
                    await self.site.call("/net/done", {"id": job.get("id"), "code": 0, "body": "", "away": True}, node_key=c.key, timeout=15)
            loop = asyncio.get_running_loop()
            for nid, secs in (d.get("due") or {}).items():   # проверка «в случайный момент» — взять ровно в срок
                c = self.by_id.get(int(nid))
                if c and 0 <= float(secs) <= 900:
                    loop.call_later(float(secs) + 0.05, lambda c=c: asyncio.ensure_future(self.take(c)))
            for nid, on in (d.get("on") or {}).items():
                c = self.by_id.get(int(nid))
                if c and bool(on) != c.on:
                    c.on = bool(on)
                    await c.send({"state": "" if on else (d.get("state") or {}).get(str(nid), ""), "on": c.on})

    async def watch_loop(self):
        """Один длинный опрос сайта на всю сеть: новые вопросы нодам, что ждут здесь, — сразу take (толчок сайта не нужен)."""
        after = 0
        while True:
            if not any(c.ready for c in self.conns):
                await asyncio.sleep(0.5)
                continue
            d = await self.site.call("/net/relay/wait", {"after": after, "wait": WAIT}, timeout=WAIT + 20)
            if not d.get("ok"):
                log.warning("сайт не ответил на ожидание вопросов: %s", d.get("error"))
                await asyncio.sleep(1)
                continue
            after = int(d.get("after") or after)
            for nid, job in (d.get("jobs") or {}).items():
                c = self.by_id.get(int(nid))
                if c and not await self.give(c, job):
                    # нода в этот миг ушла или занята — задание назад (как «ушла сама»): разговор сразу отдаст его главному
                    await self.site.call("/net/done", {"id": job.get("id"), "code": 0, "body": "", "away": True}, node_key=c.key, timeout=15)

    async def ping_loop(self):
        while True:
            await asyncio.sleep(PING)
            for c in list(self.conns):
                await c.send({"ping": int(time.time())})

    async def run(self):
        # запросы к сайту — в своих потоках: ожидание вопросов держит один поток по 20 с, а по умолчанию их всего cpu+4 —
        # на двух ядрах «возьми задание» вставало в очередь за ожиданиями и опаздывало к ноде (сайт ждёт взятия 1,5 с)
        from concurrent.futures import ThreadPoolExecutor
        asyncio.get_running_loop().set_default_executor(ThreadPoolExecutor(max_workers=64, thread_name_prefix="site"))
        self.server = await asyncio.start_server(self.handle, self.host, self.port, limit=wsmini.MSG_MAX + 1024)
        log.info("ретранслятор слушает %s:%s", self.host, self.port)
        await asyncio.gather(self.server.serve_forever(), self.beat_loop(), self.watch_loop(), self.ping_loop())


def main():
    logging.basicConfig(level=logging.DEBUG if os.environ.get("RELAY_DEBUG") else logging.INFO, format="%(asctime)s %(message)s")
    url = os.environ.get("DEWIAR_CLOUD_URL") or ""
    key = os.environ.get("DEWIAR_RUNNER_KEY") or ""
    if not url or len(key) < 24:
        sys.exit("нужны DEWIAR_CLOUD_URL и DEWIAR_RUNNER_KEY (/etc/dewiar-runner.env)")
    r = Relay(url, key, os.environ.get("RELAY_HOST", "127.0.0.1"), int(os.environ.get("RELAY_PORT", "8790")))
    try:
        asyncio.run(r.run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
