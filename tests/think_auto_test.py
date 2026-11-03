"""Сложная просьба — модель думает перед ответом (компьютер): стихи, задачи, анализ, сравнение, планы, код, длинные
просьбы. Простые вопросы, «почему…» и команды (включи песню, напомни) — сразу, без размышлений. Запрос к модели:
без chat_template_kwargs {enable_thinking: false} и с запасом лимита; переключатель llm.think_auto в студии."""
import json, os, sys, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


from llm import stream_events, wants_think  # noqa: E402

hard = ["Напиши стих про Милу", "Сочини поздравление в стихах для мамы", "Реши задачу: поезд вышел из А в 9 утра",
        "Сравни iPhone и Samsung", "Как бы ты торговала на криптобирже?", "Составь план тренировок на неделю",
        "Напиши код сортировки на Python", "Взвесь за и против переезда", "x" * 300]
easy = ["Почему небо голубое?", "Сколько будет два плюс два", "Напомни завтра позвонить маме", "Включи песню Цоя",
        "Включи радио", "Привет, как дела?", "Расскажи анекдот", "Какая погода завтра?"]
ok(all(wants_think(t) for t in hard), f"сложное — думать: {[t[:30] for t in hard if not wants_think(t)] or 'все'}")
ok(not any(wants_think(t) for t in easy), f"простое — сразу: {[t for t in easy if wants_think(t)] or 'все'}")
ok(wants_think("привет", "on") and not wants_think("Напиши стих", "off"), "явное on/off профиля важнее догадки")

# что уходит модели: с размышлениями — без enable_thinking:false и с большим лимитом
seen = []


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_POST(self):
        seen.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
        self.wfile.write('data: {"choices":[{"delta":{"content":"Осень."}}]}\n\ndata: [DONE]\n\n'.encode())


srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
P = {"kind": "openai", "base_url": f"http://127.0.0.1:{srv.server_address[1]}/v1", "model": "m"}
list(stream_events(dict(P, think="on", max_tokens=6144), "sys", [{"role": "user", "content": "Напиши стих"}]))
list(stream_events(P, "sys", [{"role": "user", "content": "Привет"}]))
srv.shutdown()
ok("chat_template_kwargs" not in seen[0] and seen[0]["max_tokens"] == 6144, f"думает: размышления не выключаются, лимит 6144: {seen[0].get('chat_template_kwargs')} {seen[0]['max_tokens']}")
ok(seen[1].get("chat_template_kwargs") == {"enable_thinking": False}, "обычный вопрос — размышления выключены, как раньше")

src = (ROOT / "core/engine_answer.py").read_text(encoding="utf-8")
ok('wants_think(think_ask(text' in src and 'think="on"' in src and '"think_auto"' in src, "ядро: сложная просьба — профиль хода с think=on (выключается llm.think_auto)")
from settings import DEFAULTS  # noqa: E402
ok(DEFAULTS["llm"]["think_auto"] is True and 'data-k="llm.think_auto"' in (ROOT / "ui/settings.html").read_text(encoding="utf-8"),
   "включено по умолчанию, переключатель в студии («Мозг»)")
# ответ «Итак, пользовательские данные…» — это ответ, а не рассуждение вслух (отзыв 11.10: «защита персональных
# данных» → «Не получилось ответить»); «Итак, пользователь спрашивает…» — по-прежнему рассуждение
from llm import _REASON_START  # noqa: E402
ok(not _REASON_START.match("Итак, пользовательские данные хранятся у вас на устройстве.") and _REASON_START.match("Итак, пользователь спрашивает о данных"),
   "«Итак, пользовательские данные…» — ответ, «Итак, пользователь спрашивает…» — рассуждение")
app = (ROOT / "android/assets/www/app.js").read_text(encoding="utf-8")
ok("итак, пользовател[ьяю](?![а-яё])" in app and "if (!text.trim() && !found.length && !opt.retried" in app,
   "телефон: то же различие, и пустой ответ модели — ещё одна попытка, а не сразу «переспросите»")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
