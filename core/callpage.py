"""Страница звонка «Близким» для компьютера: крошечный HTTP-сервер на 127.0.0.1 (случайный порт) отдаёт ui/call.html и
два скрипта — браузер открывает её как http://127.0.0.1:…/call.html (адрес localhost — «безопасный», камера и микрофон
разрешены; окно студии WebKitGTK звонить умеет не везде). Сама страница говорит с ядром по WebSocket временным
токеном (bridge.allow) — только команды звонка. Больше ничего сервер не отдаёт."""
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

log = logging.getLogger("dewiar.callpage")
UI = Path(__file__).resolve().parent.parent / "ui"
FILES = {"/call.html": (UI / "call.html", "text/html; charset=utf-8"),
         "/assets/boot.js": (UI / "assets" / "boot.js", "text/javascript; charset=utf-8"),   # первый скрипт каждой страницы (0.85)
         "/assets/call.js": (UI / "assets" / "call.js", "text/javascript; charset=utf-8"),
         "/assets/dewiar.js": (UI / "assets" / "dewiar.js", "text/javascript; charset=utf-8"),
         "/assets/logo-white.png": (UI / "assets" / "logo-white.png", "image/png")}
_srv = None
_lock = threading.Lock()


class _H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        f = FILES.get(self.path.split("?", 1)[0])
        if not f or not f[0].exists():
            self.send_error(404)
            return
        data = f[0].read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", f[1])
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Permissions-Policy", "camera=(self), microphone=(self)")
        self.end_headers()
        self.wfile.write(data)


def base():
    """Адрес сервера страницы (запускается при первом звонке)."""
    global _srv
    with _lock:
        if _srv is None:
            _srv = ThreadingHTTPServer(("127.0.0.1", 0), _H)
            threading.Thread(target=_srv.serve_forever, name="callpage", daemon=True).start()
            log.info("Страница звонков: http://127.0.0.1:%d", _srv.server_address[1])
        return f"http://127.0.0.1:{_srv.server_address[1]}"
