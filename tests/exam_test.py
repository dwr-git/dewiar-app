"""Экзамен способностей (core/exam.py) на модели-заглушке: настоящее ядро в режиме сервера, сценарии из
data/exam/scenarios.json. Проверяется сам экзамен: память через новый разговор, напоминание и расход в состоянии
программы, картинка (чек) уходит модели, судья ставит оценку, «выдумщик» не сдаёт, задача по коду — правка в рабочей
копии, тесты и скрытые проверки, тесты проекта не тронуты; отчёт JSON и Markdown."""
import asyncio, json, os, re, sys, tempfile, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
import exam as X  # noqa: E402
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


def text_of(m):
    c = m.get("content")
    return " ".join(x.get("text", "") for x in c if isinstance(x, dict)) if isinstance(c, list) else str(c or "")


CODE = [("code_run", {"command": "python3 -m unittest discover -s tests -t . -q"}),
        ("code_edit", {"path": "stats.py", "old": "return sum(xs) / (len(xs) - 1)", "new": "return sum(xs) / len(xs)"}),
        ("code_edit", {"path": "stats.py", "old": "return (s[mid] + s[mid + 1]) / 2", "new": "return (s[mid - 1] + s[mid]) / 2"}),
        ("code_run", {"command": "python3 -m unittest discover -s tests -t . -q"}),
        ("finish", {"summary": "Исправил среднее (делил на n-1) и медиану (брал не те элементы). Все тесты проходят."})]
code_pos = [0]
IMAGES = []


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        b = json.dumps({"data": [{"id": "m"}]}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b)))
        self.end_headers(); self.wfile.write(b)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        msgs = body["messages"]
        sysm = text_of(msgs[0]) if msgs and msgs[0]["role"] == "system" else ""
        last = text_of(msgs[-1])
        calls, out = [], ""
        if sysm.startswith("Ты — строгий и справедливый экзаменатор"):
            bad = "яичницу" in last and "Помощник: На завтрак вы ели" in last
            out = json.dumps({"score": 2 if bad else 8, "why": "выдумал завтрак" if bad else "по делу"}, ensure_ascii=False)
        elif "ЗАДАЧА:" in sysm:
            i = code_pos[0]; code_pos[0] += 1
            calls = [CODE[min(i, len(CODE) - 1)]]
        elif any(isinstance(m.get("content"), list) for m in msgs):
            IMAGES.append(1)
            out = "Итого по чеку 1437,50 руб., дороже всего — сыр российский за 520 руб."
        elif "Что у меня в среду" in last:
            seen = json.dumps(msgs, ensure_ascii=False)
            out = "В среду в 15:00 у вас встреча с подрядчиком по кухне." if "подрядчик" in seen else "Не знаю."
        elif last.startswith("Запомни") and msgs[-1]["role"] == "user":
            calls = [("remember", {"fact": "В среду в 15:00 встреча с подрядчиком по кухне"})]
        elif (msgs[-1]["role"] == "tool" or last.startswith("<tool_response>")) and ("Покажи мои заметки" in json.dumps(msgs, ensure_ascii=False) or "Какие у меня напоминания" in json.dumps(msgs, ensure_ascii=False)):
            out = "Вот что есть: " + last[:400]                 # пересказывает результат инструмента
        elif "Покажи мои заметки" in last:
            calls = [("find_notes", {"query": "заметки"})]     # «заметки» — не слово для поиска: инструмент отдаёт последние
        elif "Какие у меня напоминания" in last:
            calls = [("list_reminders", {})]
        elif "Подготовь поздравление коллеге" in last and msgs[-1]["role"] == "user":     # Б12: сначала один вопрос
            out = "Кому и на какую почту его отправить?"
        elif "Сергею Петрову" in last and msgs[-1]["role"] == "user":
            out = "Вот поздравление: «Сергей, с юбилеем! Пусть рыбалка радует уловом». Отправить на sp@example.org?"
        elif "завтрак" in last:
            out = "На завтрак вы ели яичницу с беконом."
        else:
            out = "Хорошо, запомнила."
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
        if out:
            self.wfile.write(f"data: {json.dumps({'choices': [{'delta': {'content': out}}]}, ensure_ascii=False)}\n\n".encode())
        for k, (name, args) in enumerate(calls):
            tc = {"index": k, "id": f"c{code_pos[0]}", "type": "function", "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)}}
            self.wfile.write(f"data: {json.dumps({'choices': [{'delta': {'tool_calls': [tc]}}]}, ensure_ascii=False)}\n\n".encode())
        self.wfile.write(b'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n')


srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
prof = {"name": "mock", "kind": "openai", "base_url": f"http://127.0.0.1:{srv.server_address[1]}/v1", "model": "m", "title": "Заглушка"}
ok(X.days_to_new_year(__import__("datetime").date(2026, 12, 30)) == 2, "дни до Нового года считаются")
im = X.make_image("receipt")
ok(im and im.startswith("data:image/png;base64,"), "картинка чека рисуется")
logs = []
rep = asyncio.run(X.run_exam(prof, only={"memory_meeting", "money", "oven", "honest_breakfast", "vision_receipt", "code_bugfix", "notes_show", "reminders_show", "stop_misheard"},
                             log=lambda s: (print(s), logs.append(s))))
R = {r["id"]: r for r in rep["scenarios"]}
ok(R["memory_meeting"]["passed"], f"память через новый разговор — сдан: {R['memory_meeting']['steps'][-1]['answer']}")
ok(R["money"]["passed"] and R["oven"]["passed"], f"расход и напоминание — видны в состоянии программы: {R['money']['checks']} {R['oven']['checks']}")
hb = R["honest_breakfast"]
ok(not hb["passed"] and hb["score"] == 2, f"выдумал завтрак — судья не пропустил: {hb.get('judge')}")
ok(R["vision_receipt"]["passed"] and IMAGES, "чек — картинкой модели, ответ проверен")
cb = R["code_bugfix"]
ok(cb["passed"] and all(c["ok"] for c in cb["checks"]), f"код: задача, тесты, тесты не тронуты — {[(c['name'], c['ok']) for c in cb['checks']]}")
for k in ("notes_show", "reminders_show"):      # заметки и напоминания положены перед сценарием — и найдены
    ok(R[k]["passed"], f"экзамен: {k} — {[(c['name'], c['ok']) for c in R[k]['checks']]} · {R[k]['steps'][-1]['answer'][:160]}")
sm = R["stop_misheard"]                         # «Ctop.», «Сстоп!», «Паузу.» — замолчала, а не «Хорошо, я слушаю» (отзыв 11.10)
ok(sm["passed"] and [x["answer"] for x in sm["steps"]] == ["", "", ""], f"экзамен: ослышанное «стоп» — сон: {sm['checks']} {sm.get('error')}")
s = rep["summary"]
ok(s["total"] == 9 and s["passed"] == 8 and "Код" in s["by_group"], f"итог: {s}")
md = X.markdown(rep)
ok("# Экзамен Dewiar" in md and "❌ Честность" in md and "Сдано **8 из 9**" in md, "отчёт Markdown")
ok(json.loads(json.dumps(rep, ensure_ascii=False))["version"], "отчёт JSON")
# Б12 «Человек в контуре» (17.11): проверки шага — вопрос на первом шаге, без отправки, детали — на втором
rep2 = asyncio.run(X.run_exam(prof, only={"loop_b12_greeting"}, log=lambda s: None))
b12 = {c["name"]: c["ok"] for c in rep2["scenarios"][0]["checks"]}
ok(b12.get("шаг 1: уточняющий вопрос") and b12.get("шаг 1: без send_email") and b12.get("шаг 2: в ответе есть: Серг")
   and b12.get("шаг 2: в ответе есть: рыбал"), f"Б12: проверки по шагам — {b12}")
srv.shutdown()
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
