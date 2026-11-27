"""Владелец 26.11: «у меня купленный прокси и ключ Gemini, оно работает. Почему Гугл давал отказы — похоже на программный
баг: видимо, не всегда отвечал прокси (он бывает перегружен), и запросы шли мимо него». Так и было: свой прокси профиля
модели (и внешнего судьи стенда) не ответил — запрос уходил напрямую, и 15 минут все запросы к этому серверу шли мимо
прокси; напрямую Google отвечает «страна не поддерживается». Теперь свой прокси — строго: не ответил — повтор через него
же, напрямую не отправляем никогда; а судья повторяет оценку ещё дважды с паузой."""
import os, sys, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


hits = []


class S(BaseHTTPRequestHandler):                  # «сервер модели», до которого напрямую доходить нельзя
    def log_message(self, *a):
        pass

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        hits.append(self.path)
        body = b'{"error": "User location is not supported for the API use."}'
        self.send_response(400); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)


srv = ThreadingHTTPServer(("127.0.0.1", 0), S)
threading.Thread(target=srv.serve_forever, daemon=True).start()
URL = f"http://127.0.0.1:{srv.server_address[1]}/v1"

import httpx  # noqa: E402
import net  # noqa: E402

net.install()
net.BACKOFF = (0.01, 0.01, 0.01)
dead = {"base_url": URL, "proxy": "127.0.0.1:1"}          # прокси «перегружен» — не принимает соединение
for i in range(3):
    err = ""
    with net.profile_proxy(dead):
        try:
            httpx.post(URL + "/chat/completions", json={"x": 1}, timeout=5)
        except httpx.HTTPError as e:
            err = str(e)
    ok(not hits and "напрямую не отправлен" in err, f"попытка {i + 1}: прокси молчит — запрос не ушёл мимо него: {err[:90]} · напрямую: {len(hits)}")
ok(not net._direct_ok, "«ходить напрямую 15 минут» для своего прокси не запоминается")
src = (ROOT / "core/net.py").read_text(encoding="utf-8")
ok('_Lazy(hp, kw.get("verify", True), kw.get("cert"), strict=True)' in src, "прокси профилей модели (bind_hosts, profile_proxy) — строгие")
ok("t = _Lazy(px, kw.get(\"verify\", True), kw.get(\"cert\")) if px" in src, "прокси Dewiar к серверам Dewiar — как было (может пойти напрямую)")

# ---------- судья: повторяет оценку ----------
import exam  # noqa: E402
import llm  # noqa: E402
calls = []


def flaky(profile, system, msgs, **kw):
    calls.append(1)
    if len(calls) < 3:
        raise httpx.ProxyError("прокси не ответил (ConnectError) — запрос к generativelanguage.googleapis.com напрямую не отправлен")
    yield '{"score": 8, "why": "по делу"}'


llm.stream_chat = flaky
exam.time.sleep = lambda s: None
r = exam.judge({"base_url": "https://generativelanguage.googleapis.com/v1beta/openai", "model": "gemini", "proxy": "http://u:secret@127.0.0.1:1"},
               {"title": "т", "judge": "ответил"}, "Пользователь: привет", "—")
ok(r["score"] == 8 and len(calls) == 3, f"судья: прокси дважды не ответил — третья попытка оценила: {r} · попыток {len(calls)}")
calls.clear()


def down(profile, system, msgs, **kw):
    calls.append(1)
    raise httpx.ProxyError("прокси не ответил: http://u:secret@127.0.0.1:1")
    yield ""


llm.stream_chat = down
r = exam.judge({"base_url": "https://x.invalid/v1", "model": "m"}, {"title": "т", "judge": "ответил"}, "П: привет", "—")
ok(r["score"] is None and len(calls) == 3 and "secret" not in r["why"] and "•••" in r["why"],
   f"не ответил и с третьего раза — без оценки, пароль прокси скрыт: {r['why'][:80]}")
srv.shutdown()
print("\nИТОГ: " + ("всё прошло" if not fails else f"не прошло {len(fails)}"))
sys.exit(1 if fails else 0)
