"""Сбой из пакета 04.11 (8 раз, 4 компьютера, 0.81.2): «dewiar.sync: Синхронизация — ValueError: Unknown scheme for proxy URL
URL('socks4://127.0.0.1:10808')». Windows отдаёт системный прокси «socks=адрес:порт» (v2rayN, Clash) как socks4:// —
httpx такого не знает и не создавал ни одного соединения: синхронизация, облако, обновления падали.
Теперь: прокси компьютера SOCKS4 — тот же адрес как SOCKS5 (программы VPN понимают оба), «Сеть» объясняет, что делать,
а вписать socks4:// в «Сеть» нельзя — понятный отказ при сохранении."""
import json, os, socket, struct, subprocess, sys, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import net  # noqa: E402
try:
    net.normalize_proxy("socks4://127.0.0.1:10808"); ok(False, "socks4 в «Сети» должен отказать")
except net.NetError as e:
    ok("socks4 не поддерживается — используйте socks5 или http" in str(e), f"«Сеть»: {e}")
ok(net.normalize_proxy("socks5://127.0.0.1:10808") == "socks5://127.0.0.1:10808", "socks5 — как раньше")
fixed = net._socks4_fix({"all://": "socks4://127.0.0.1:10808", "all://localhost": None})
ok(fixed == {"all://": "socks5://127.0.0.1:10808", "all://localhost": None} and net.SOCKS4["seen"], f"прокси системы socks4 → socks5: {fixed}")
ok("SOCKS4" in net.SOCKS4_HINT and "SOCKS5 или HTTP" in net.SOCKS4_HINT, "подсказка «Сети»: что это и что делать")
eb = (ROOT / "core" / "engine_brain.py").read_text(encoding="utf-8")
ok('"sys_socks4"' in eb and "n.sys_socks4" in (ROOT / "ui" / "studio" / "dewiar.js").read_text(encoding="utf-8"), "«Сеть» показывает подсказку")


# настоящий запрос: прокси системы socks4:// (как из реестра Windows), на том адресе — SOCKS5 (как v2rayN)
class Web(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_GET(self):
        b = b"through-socks"
        self.send_response(200); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)


web = ThreadingHTTPServer(("127.0.0.1", 0), Web)
threading.Thread(target=web.serve_forever, daemon=True).start()
USED = []


def socks5_server():
    srv = socket.socket(); srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); srv.bind(("127.0.0.1", 0)); srv.listen(5)

    def pipe(a, b):
        try:
            while True:
                d = a.recv(65536)
                if not d:
                    break
                b.sendall(d)
        except OSError:
            pass
        finally:
            for s in (a, b):
                try:
                    s.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

    def handle(c):
        try:
            ver, n = c.recv(2)
            c.recv(n); c.sendall(b"\x05\x00")
            _, cmd, _, at = c.recv(4)
            if at == 1:
                host = socket.inet_ntoa(c.recv(4))
            elif at == 3:
                host = c.recv(c.recv(1)[0]).decode()
            else:
                return c.close()
            port = struct.unpack(">H", c.recv(2))[0]
            USED.append((host, port))
            r = socket.create_connection((host if host != "example.test" else "127.0.0.1", port if host != "example.test" else web.server_port))
            c.sendall(b"\x05\x00\x00\x01" + socket.inet_aton("127.0.0.1") + struct.pack(">H", port))
            threading.Thread(target=pipe, args=(c, r), daemon=True).start(); pipe(r, c)
        except Exception:  # noqa: BLE001
            c.close()

    def loop():
        while True:
            c, _ = srv.accept()
            threading.Thread(target=handle, args=(c,), daemon=True).start()
    threading.Thread(target=loop, daemon=True).start()
    return srv.getsockname()[1]


SP = socks5_server()
SCRIPT = r'''
import os, sys, json
sys.path.insert(0, sys.argv[1] + "/core")
import httpx, net
net.install()
out = {}
try:
    out["text"] = httpx.get("http://example.test/ping", timeout=8).text
except Exception as e:
    out["text"] = f"{type(e).__name__}: {e}"
out["seen"] = net.SOCKS4["seen"]
print(json.dumps(out))
'''
env = {k: v for k, v in os.environ.items() if k.lower() not in ("http_proxy", "https_proxy", "all_proxy", "no_proxy")}
env["ALL_PROXY"] = f"socks4://127.0.0.1:{SP}"
r = subprocess.run([sys.executable, "-c", SCRIPT, str(ROOT)], env=env, capture_output=True, text=True, timeout=60)
try:
    out = json.loads(r.stdout.strip().splitlines()[-1])
except (ValueError, IndexError):
    out = {"text": r.stdout + r.stderr}
ok(out.get("text") == "through-socks", f"прокси компьютера socks4:// — соединение есть (через SOCKS5), не ValueError: {str(out.get('text'))[:120]}")
ok(USED and USED[0][0] == "example.test", f"и правда через прокси: {USED[:1]}")
web.shutdown()
print("ALL OK" if not fails else f"FAILED: {len(fails)}")
sys.exit(1 if fails else 0)
