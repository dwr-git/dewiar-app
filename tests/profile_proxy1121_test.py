"""Владелец 21.11: «сервер стоит в стране, где запросы к модели заблокированы… если бы там же, где ставим модели, можно было
добавить свой прокси (адрес, порт, логин, пароль)». У профиля модели — поле «Прокси»: запросы к серверу этой модели идут через
него, всё остальное — как было (напрямую или прокси Dewiar к серверам Dewiar). Облако Dewiar и свой компьютер — мимо."""
import os, sys, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


seen = []


class P(BaseHTTPRequestHandler):                  # HTTP-прокси: запрос приходит с полным адресом
    def log_message(self, *a):
        pass

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        self.rfile.read(n)
        seen.append((self.path, self.headers.get("Proxy-Authorization") or ""))
        body = b'{"ok": true}'
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(body)))
        self.end_headers(); self.wfile.write(body)


srv = ThreadingHTTPServer(("127.0.0.1", 0), P)
threading.Thread(target=srv.serve_forever, daemon=True).start()
PORT = srv.server_address[1]

import httpx  # noqa: E402
import net  # noqa: E402
import engine_brain  # noqa: E402

net.install()
settings = {"llm": {"profiles": {
    "a": {"name": "Fable", "kind": "openai", "base_url": "http://brain.example.invalid/v1", "proxy": f"127.0.0.1:{PORT}:user:pa:ss"},
    "b": {"name": "Dewiar", "cloud": True, "base_url": "https://dewiar.pro/dwrapp/cloud.php?p=", "proxy": "127.0.0.1:1"},
    "c": {"name": "Дома", "base_url": "http://192.168.1.10:8000/v1", "proxy": "127.0.0.1:1"},
    "d": {"name": "Без прокси", "base_url": "https://api.other.invalid/v1"}}}}
eng = SimpleNamespace(s=SimpleNamespace(get=lambda *k: settings.get(k[0], {}).get(k[1]) if len(k) > 1 else settings.get(k[0])))
conf = engine_brain.BrainMixin._host_px_conf(eng)
ok(conf == {"brain.example.invalid": f"http://user:pa%3Ass@127.0.0.1:{PORT}"},
   f"прокси — только у своего сервиса модели (облако Dewiar и домашняя сеть — мимо), «адрес:порт:логин:пароль» понят: {conf}")
net.bind_hosts(lambda: conf)
r = httpx.post("http://brain.example.invalid/v1/chat/completions", json={"x": 1}, timeout=10)
ok(r.status_code == 200 and seen and seen[-1][0] == "http://brain.example.invalid/v1/chat/completions" and seen[-1][1].startswith("Basic "),
   f"запрос к модели — через прокси профиля, с логином: {seen[-1:]}")
n = len(seen)
try:
    httpx.post("http://api.other.invalid/v1/x", timeout=3)
except httpx.HTTPError:
    pass
ok(len(seen) == n, "к другим адресам — не через этот прокси")
net.bind_hosts(lambda: {})
n = len(seen)
with net.profile_proxy({"base_url": "http://other.example.invalid/v1", "proxy": f"127.0.0.1:{PORT}"}):
    r = httpx.post("http://other.example.invalid/v1/models", timeout=10)    # «Подключить» по ключу: профиль ещё не сохранён
ok(r.status_code == 200 and len(seen) == n + 1 and seen[-1][0].startswith("http://other.example.invalid/"),
   "подключение по ключу через прокси: список моделей и проверка — через него ещё до сохранения профиля")
try:
    httpx.post("http://other.example.invalid/v1/models", timeout=3)
except httpx.HTTPError:
    pass
ok(len(seen) == n + 1, "после проверки — прокси не остаётся")
cmd = (ROOT / "core/commands_brain.py").read_text(encoding="utf-8")
ok(cmd.count("net.profile_proxy(") >= 3, "проверка, список моделей и подбор экономной — через прокси профиля")
html = (ROOT / "ui/settings.html").read_text(encoding="utf-8"); cj = (ROOT / "ui/studio/connect.js").read_text(encoding="utf-8")
ok('id="ck-proxy"' in html and "prof.proxy = px" in cj, "«Облачная модель по ключу» → «Через прокси» — поле прокси сразу при подключении")
ui = (ROOT / "ui/studio/brain.js").read_text(encoding="utf-8")
ok('data-f="proxy"' in ui and "p.cloud ? \"\" : `<label class=\"f\">Прокси" in ui, "студия → «Мозг» → профиль: поле «Прокси» (у облака Dewiar его нет)")
ok("net.bind_hosts(self._host_px_conf)" in (ROOT / "core/engine.py").read_text(encoding="utf-8"), "ядро подключает прокси профилей")
srv.shutdown()
print("ИТОГ:", "всё прошло" if not fails else f"{len(fails)} не прошло")
sys.exit(1 if fails else 0)
