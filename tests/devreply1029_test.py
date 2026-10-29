"""Ответ разработчика на жалобу (29.10, владелец: «чтобы тот, кому пришёл ответ, получал пуш и чувствовал и видел, что ему
ответили»). Компьютер: проверка раз в 10 минут, пока есть жалобы без ответа (было — раз в 6 часов); пришёл ответ —
уведомление системы и Telegram, строка «💬 Ответ на жалобу №…» в виджете (пока не посмотрели), коротко голосом, в «Чат»;
в «О программе» — «новый ответ», открыли — прочитано. Телефон: раз в 15 минут и при открытии приложения, уведомление и плашка."""
import json, os, sys, tempfile, threading, types
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ.update(DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_CONFIG_DIR=str(tmp / "cfg"))
(tmp / "st").mkdir()
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


ANS = {"status": "seen", "reply": ""}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        items = [{"id": x["id"], "status": ANS["status"], "reply": ANS["reply"], "fixed": "0.68.0" if ANS["status"] == "fixed" else ""} for x in body["items"]]
        b = json.dumps({"items": items}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)


srv = ThreadingHTTPServer(("127.0.0.1", 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
import health as HL  # noqa: E402

ev, pushes, said = [], [], []
me = types.SimpleNamespace(s=types.SimpleNamespace(get=lambda *k: "lira"), chatlog=None, bridge=None,
                           emit=lambda t, **k: ev.append((t, k)), push=lambda t, x="", **k: pushes.append((t, x, k)), announce=said.append,
                           _cloud_base=lambda: f"http://127.0.0.1:{srv.server_address[1]}/cloud.php", _thanks_list=(9e12, []))
for n in ("_complaints", "_complaints_save", "complaints_check", "complaints_view", "complaint_message", "complaints_seen"):
    setattr(me, n, types.MethodType(getattr(HL.HealthMixin, n), me) if n not in ("_complaints_save", "complaint_message") else getattr(HL.HealthMixin, n))
me._complaints_save([{"id": 401, "s": "x" * 32, "note": "Радио молчит", "status": "new", "ts": __import__("time").time() - 3600}])
ok(me.complaints_check() == [] and not pushes, "ответа ещё нет — тихо")
ANS.update(status="fixed", reply="Нашли и исправили — обновитесь.")
news = me.complaints_check()
ok(len(news) == 1 and pushes and pushes[0][0] == "Ваша жалоба №401 исправлена" and pushes[0][2].get("telegram", True) is not False,
   f"ответили — уведомление системы и в Telegram: {pushes[:1]}")
ok(any(t == "dev_reply" and k.get("id") == 401 and k.get("unread") == 1 for t, k in ev), "виджету — строка «ответ разработчика»")
ok(said and "Вам ответил разработчик Dewiar — на жалобу номер 401. Нашли и исправили" in said[0], f"голосом — коротко: {said[:1]}")
v = me.complaints_view()
ok(v["unread"] == 1 and v["mine"][0].get("unread"), "в «О программе» — новый ответ отмечен")
me.complaints_seen()
ok(me.complaints_view()["unread"] == 0 and any(t == "dev_reply" and k.get("unread") == 0 for t, k in ev), "посмотрели — строка уходит")
pushes.clear(); said.clear()
ok(me.complaints_check() == [] and not pushes and not said, "тот же ответ второй раз — не повторяем")
hs = (ROOT / "core/health.py").read_text(encoding="utf-8")
ok("def _complaints_loop" in hs and 'DEWIAR_COMPLAINTS_EVERY") or 600' in hs and "target=self._complaints_loop" in hs, "проверка раз в 10 минут, пока есть жалобы без ответа")
hud = (ROOT / "ui/hud.html").read_text(encoding="utf-8")
ok('id="drb"' in hud and 'core.on("dev_reply", drbSet)' in hud and 'open_settings("about")' in hud, "виджет: строка, нажатие — «О программе»")
app = (ROOT / "android/assets/www/app.js").read_text(encoding="utf-8")
ok("setInterval(() => cmpTick(15 * 6e4 - 3e4)" in app and 'addEventListener("visibilitychange", () => { if (!document.hidden) cmpTick(2 * 6e4); })' in app,
   "телефон: раз в 15 минут и при открытии приложения")
# не висеть вечно (владелец 29.10: «забыли ответить — а вопрос висит, и лишние запросы бесконечно»)
D, now = 86400, 2_000_000_000
W, E = HL.complaint_watch, HL.complaints_every
ok(W({"s": "x", "ts": now - D, "status": "new"}, now) and not W({"s": "x", "ts": now - 61 * D, "status": "work"}, now), "старше 60 дней — не спрашиваем совсем")
ok(W({"s": "x", "ts": now - 3 * D, "status": "fixed"}, now) and not W({"s": "x", "ts": now - 8 * D, "status": "seen", "reply": "Спасибо!"}, now),
   "ответили — ещё неделю (вдруг допишем), потом нет")
ok(E([{"s": "x", "ts": now - 3600, "status": "new"}], 600, now) == 600, "свежая без ответа — раз в 10 минут")
ok(E([{"s": "x", "ts": now - 5 * D, "status": "seen"}], 600, now) == 3600, "старше 2 дней — раз в час")
ok(E([{"s": "x", "ts": now - 20 * D, "status": "work"}], 600, now) == 0, "старше 14 дней — только с пульсом раз в 6 часов")
ok(E([{"s": "x", "ts": now - 3600, "status": "seen", "reply": "Ответ"}], 600, now) == 0, "ответили — часто не спрашиваем")
ok("const cmpWait = () =>" in app and "now - (c.ts || 0) < 60 * 86400" in app, "телефон — так же")
srv.shutdown()
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
