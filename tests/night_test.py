"""Ночной обход (core/night.py): сбои за сутки по видам, повтор задач с ошибкой (один раз, не для ошибок программы и
«зациклилась»), неудачные дела по расписанию, вопросы без ответа, проверка модели; разбор файлом «Здоровье/…md»,
фраза на утро (один раз), отчёт разработчику — только с согласия и без названий задач. Спокойная ночь — молчим."""
import datetime as dt, json, os, sys, tempfile, threading, time, types
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ.update(DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_CONFIG_DIR=str(tmp / "cfg"))
(tmp / "st").mkdir()
sys.path.insert(0, str(ROOT / "core"))
import night as N  # noqa: E402
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        self.rfile.read(int(self.headers["Content-Length"]))
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
        self.wfile.write(b'data: {"choices":[{"delta":{"content":"\\u0434\\u0430"}}]}\n\ndata: [DONE]\n\n')


srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
PROF = {"name": "m", "kind": "openai", "base_url": f"http://127.0.0.1:{srv.server_address[1]}/v1", "model": "m"}


class T:
    def __init__(self, tid, title, **d):
        self.id, self.title, self.data, self.saved = tid, title, dict(d), 0
    def save(self):
        self.saved += 1


now_iso = dt.datetime.now().isoformat(timespec="seconds")
tasks = {"a": T("a", "Отчёт о конкурентах", status="failed", error="модель или сеть не ответили", fail_kind="failed", failed_at=now_iso),
         "b": T("b", "Сломалось", status="failed", error="внутренняя ошибка программы", fail_kind="bug", failed_at=now_iso),
         "c": T("c", "Презентация", status="waiting", question="Какой цвет фона?"),
         "d": T("d", "Старое", status="failed", error="x", fail_kind="failed", failed_at="2020-01-01T00:00:00")}
told, sent = [], []
cfg = {("report", "auto"): True}
host = types.SimpleNamespace(
    tasks=types.SimpleNamespace(tasks=tasks, tell=lambda tid, text: told.append((tid, text))),
    reminders=types.SimpleNamespace(items=[{"kind": "job", "text": "Курс доллара", "last_ok": False, "last_error": "модель не ответила"},
                                           {"kind": "job", "text": "Сводка", "last_ok": True}]),
    workspace=types.SimpleNamespace(ensure=lambda: tmp / "ws"),
    s=types.SimpleNamespace(get=lambda *k: cfg.get(k), active_llm=lambda: dict(PROF)),
    incidents=lambda since: [{"ts": time.time() - 100, "kind": "task", "text": "Задача: модель или сеть не ответили 15 раз"}] * 3
    + [{"ts": time.time() - 50, "kind": "error", "text": "Модель (openai): timeout 12"}, {"ts": time.time() - 40, "kind": "error", "text": "Модель (openai): timeout 13"}],
    report_send=lambda **k: (sent.append(k), {"id": 77})[1])
(tmp / "ws").mkdir()

nw = N.NightWatch(host)
ok(nw.due(dt.datetime.now().replace(hour=4)) and not nw.due(dt.datetime.now().replace(hour=1)), "обход — после 3:00, раз в сутки")
r = nw.run()
ok([t for t, _ in told] == ["a"] and tasks["a"].data.get("night_retry"), f"задача с ошибкой связи — запущена снова, одна: {told}")
ok(not any(t == "b" for t, _ in told), "ошибку программы ночью не повторяем — она в «не решено»")
ok(any("Сломалось" in x for x in r["left"]) and any("ждёт ответа" in x for x in r["left"]) and any("Курс доллара" in x for x in r["left"]),
   f"не решено: ошибка программы, вопрос без ответа, неудачное дело: {r['left']}")
ok(not any("Старое" in x for x in r["left"]), "старые задачи (до прошлого обхода) не трогаем")
mod = [p for p in r["problems"] if "Модель" in p["text"]]
ok(mod and mod[0]["n"] == 2, f"одинаковые сбои с разными числами — одной строкой: {mod}")
ok(any("связь с моделью" in x for x in r["repaired"]), "модель проверена — отвечает")
f = Path(r["path"])
ok(f.exists() and "Ночной обход" in f.read_text() and "Что осталось" in f.read_text(), "разбор — файлом «Здоровье/…md»")
ok(r["note"] and "ночью: задача" in r["note"], f"фраза на утро: {r['note']}")
ok(nw.morning_note() == r["note"] and nw.morning_note() == "", "фраза на утро — один раз")
ok(sent and sent[0]["plain"] and "Отчёт о конкурентах" not in sent[0]["note"] and "Сломалось" not in sent[0]["note"]
   and "Ночной разбор" in sent[0]["summary"], "отчёт разработчику: технический, без журнала и названий задач")
ok(not nw.due(dt.datetime.now().replace(hour=5)), "второй раз за сутки — нет")

# 22.10: задача упала из-за прав («Отказано в доступе») — ночью не перезапускаем, объясняем; сбои только модели (ключ,
# страна, баланс) — не повод для отчёта разработчику (пакет 22.10, №193: «сбоев 4, не решено 0», всё про модель)
import tasks as TK  # noqa: E402
ok(TK.ACCESS_RX.search("[WinError 5] Отказано в доступе: 'C:\\Program Files\\x'") and TK.ACCESS_RX.search("PermissionError: [Errno 13] Permission denied")
   and not TK.ACCESS_RX.search("модель или сеть не ответили"), "ошибка прав узнаётся (Windows, Linux), сеть — нет")
tasks2 = {"e": T("e", "Почистить папку", status="failed", error="[WinError 5] Отказано в доступе", fail_kind="access", failed_at=now_iso)}
told2, sent2 = [], []
h2 = types.SimpleNamespace(tasks=types.SimpleNamespace(tasks=tasks2, tell=lambda tid, text: told2.append(tid)),
                           reminders=types.SimpleNamespace(items=[]), workspace=host.workspace, s=host.s,
                           incidents=lambda since: [{"ts": time.time() - 30, "kind": "error", "text": "Модель (openai): User location is not supported"}] * 3,
                           report_send=lambda **k: (sent2.append(k), {"id": 78})[1])
nw2 = N.NightWatch(h2); nw2.data = {}
r2 = nw2.run()
ok(not told2 and any("прав на файл или папку" in x for x in r2["left"]), f"нет прав — не перезапускаем, объясняем: {r2['left']}")
tasks2.clear(); sent2.clear(); nw2.data = {}
r3 = nw2.run()
ok(not sent2, "сбои только модели (страна, ключ) — отчёт разработчику не уходит")
h2.incidents = lambda since: [{"ts": time.time() - 30, "kind": "task", "text": "Задача: застрял: много раз повторил одно и то же"}] * 4
h2.s = types.SimpleNamespace(get=lambda *k: cfg.get(k), active_llm=lambda: None)
sent2.clear(); nw2.data = {}; nw2.run()
ok(not sent2, "задача застряла или не хватило окна модели — это модель, отчёт не уходит (№204, №210)")
# №235 (24.10): «Заряд Dewiar Облака закончился» и у дела по расписанию — настройки человека; подпись сбоя без переносов
charge = "Заряд Dewiar Облака закончился. После перевода средств, прикрепите скриншот или фото оплаты.\n\nПополнить можно через донат:\nhttps://donate.example/x"
h2.incidents = lambda since: [{"ts": time.time() - 30, "kind": "error", "text": "Модель (openai): " + charge}] * 4 + \
    [{"ts": time.time() - 30, "kind": "job", "text": "Дело по расписанию: " + charge}] * 2
h2.reminders = types.SimpleNamespace(items=[{"kind": "job", "last_ok": False, "text": "Утренняя сводка", "last_error": charge}])
sent2.clear(); nw2.data = {}; r4 = nw2.run()
ok(not sent2, f"заряд кончился — и дело по расписанию не удалось: не ошибка программы, отчёт не уходит (№235): {r4['left']}")
ok(all("\n" not in p["text"] and len(p["text"]) <= 161 for p in r4["problems"]) and any(p["text"].endswith("…") for p in r4["problems"]),
   f"подпись сбоя — одной строкой, длинная обрезана по слову: {[p['text'][-30:] for p in r4['problems']]}")
h2.incidents = lambda since: []
h2.reminders = types.SimpleNamespace(items=[{"kind": "job", "last_ok": False, "text": "Сводка", "last_error": "KeyError: 'deliver'"}])
sent2.clear(); nw2.data = {}; nw2.run()
ok(sent2, "дело не удалось из-за ошибки программы — отчёт уходит, как раньше")
h2.reminders = types.SimpleNamespace(items=[])

# второй обход: та же задача снова упала — повтора нет; согласия на отчёты нет — не шлём; спокойно — молчим
tasks["a"].data.update(failed_at=dt.datetime.now().isoformat(timespec="seconds"))
nw.data["last_day"], nw.data["last_ts"] = "", time.time() - 5
cfg[("report", "auto")] = None
told.clear(); sent.clear()
host.incidents = lambda since: []
r2 = nw.run()
ok(not told and any("Отчёт о конкурентах" in x for x in r2["left"]), "упала снова после ночного повтора — второй раз не повторяем, честно в «не решено»")
ok(not sent, "без согласия — отчёт не уходит")
host.reminders.items, tasks.clear()
host.reminders.items = []
nw.data["last_day"], nw.data["last_ts"] = "", time.time()
r3 = nw.run()
ok(r3["note"] == "" and not r3["left"], "спокойная ночь — утром ничего не говорим")
cfg[("night", "on")] = False
nw.data["last_day"] = ""
ok(not nw.due(dt.datetime.now().replace(hour=4)), "выключено настройкой — не ходим")
srv.shutdown()
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
