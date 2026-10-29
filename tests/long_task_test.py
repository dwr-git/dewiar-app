"""Долгие задачи «до конца»: план с критерием готовности, блокнот фактов (переживает сжатие памяти), сообщения
по ходу, ожидание и возвращение к делу, новые сведения от пользователя будят задачу, проверка перед итогом,
повтор при сбое модели, продолжение после перезапуска программы. Модель — заглушка со сценарием на каждую задачу."""
import json, os, re, sys, tempfile, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ.update(DEWIAR_WORKSPACE=str(tmp / "ws"), DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_CONFIG_DIR=str(tmp / "cfg"),
                  DEWIAR_TASK_RETRY="0.03,0.03,0.03", DEWIAR_TASK_RESUME_SEC="1")
sys.path.insert(0, str(ROOT / "core"))
from workspace import Workspace  # noqa: E402
import tasks as TK  # noqa: E402
import tools as T  # noqa: E402

FAILS = []
def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        FAILS.append(m)

def wait_for(cond, sec=20):
    end = time.time() + sec
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.1)
    return False

# ---------- модель-заглушка: у каждой задачи свой сценарий ----------
SCRIPTS = {
    "Перебронировать рейс": [
        ("update_plan", {"plan": "**Готово, когда:** новый билет подтверждён и багаж найден\n\n- [ ] узнать варианты\n- [ ] подтвердить новый билет\n- [ ] найти багаж"}),
        ("remember", {"fact": "Код брони ABC123, рейс KL1234 отменён"}),
        ("notify", {"text": "Рейс KL1234 отменили — ищу замену."}),
        ("notify", {"text": "Ещё одна мелочь"}),
        ("wait", {"minutes": 0.05, "reason": "ответ KLM о новом рейсе"}),
        ("finish", {"summary": "Новый билет есть"}),                         # рано: в плане не всё отмечено
        ("update_plan", {"plan": "**Готово, когда:** новый билет подтверждён и багаж найден\n\n- [x] узнать варианты\n- [x] подтвердить новый билет\n- [ ] найти багаж"}),
        ("wait", {"minutes": 600, "reason": "ответ по багажу"}),
        ("remember", {"fact": "Багаж нашли: AMS-777"}),
        ("update_plan", {"plan": "**Готово, когда:** новый билет подтверждён и багаж найден\n\n- [x] узнать варианты\n- [x] подтвердить новый билет\n- [x] найти багаж"}),
        ("finish", {"summary": "Новый билет **KL1236** подтверждён, багаж AMS-777 доставят домой."}),
    ],
    "Большое исследование": [("remember", {"fact": "секретный код 4242"})]
    + [("log", {"text": f"Шаг {i}: " + "подробности " * 80}) for i in range(10)]
    + [("finish", {"summary": "Исследование готово."})],
    "Сбой модели": [("finish", {"summary": "Получилось после сбоя."})],
    "Проверить статус утром": [("wait", {"minutes": 0.1, "reason": "проверить статус обращения"}),
                               ("finish", {"summary": "Статус проверен после перезапуска."})],
}
pos, reqs, consolidations, fail_left, checks = {}, [], [], [0], []
think_left = [0]
plain = []                        # запросы, где действия описаны текстом (tools_mode prompt)                  # «Задачи на часы»: модель уходит в размышления и не отвечает (пакет 29.10)
lock = threading.Lock()


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        sysm = body["messages"][0]["content"]
        with lock:
            if fail_left[0] > 0:
                fail_left[0] -= 1
                self.send_response(503); self.end_headers(); self.wfile.write(b"overloaded"); return
            if not body.get("tools") and sysm.startswith(("Ты — строгий", "Ты — аналитик")):   # самопроверка итога, уроки
                checks.append(sysm[:20])
                out = '{"verdict": "ok"}' if sysm.startswith("Ты — строгий") else '{"lessons": []}'
                chunks = [{"choices": [{"delta": {"content": out}}]}]
                tc = None
            elif "ЗАДАЧА: Без действий" in sysm:            # модель не понимает инструменты полем — только текстом
                if body.get("tools"):
                    chunks = [{"choices": [{"delta": {"content": "Хорошо, подумаю, как это сделать."}}]}]
                else:
                    plain.append(sysm)
                    chunks = [{"choices": [{"delta": {"content": '<tool_call>\n{"name": "finish", "arguments": {"summary": "Сделано через описание действий текстом."}}\n</tool_call>'}}]}]
                tc = None
            elif not body.get("tools"):                                    # блокнот переписывается моделью
                consolidations.append(body)
                out = "# Блокнот задачи\n\n## Что известно\n- секретный код 4242\n- консолидировано: 10 шагов исследования\n\n## Что дальше\n- итог"
                chunks = [{"choices": [{"delta": {"content": out}}]}]
                tc = None
            elif think_left[0] > 0 and "Долго думает" in sysm:
                think_left[0] -= 1
                chunks = [{"choices": [{"delta": {"reasoning_content": "Хм, надо подумать... " * 40}}]}, {"choices": [{"delta": {}, "finish_reason": "stop"}]}]
                tc = None
            else:
                title = re.search(r"ЗАДАЧА: (.+)", sysm).group(1).strip()
                i = pos.get(title, 0); pos[title] = i + 1
                sc = SCRIPTS.get(title, [])
                name, args = sc[i] if i < len(sc) else ("finish", {"summary": "Готово."})
                reqs.append({"title": title, "i": i, "system": sysm, "messages": body["messages"][1:], "tool": name})
                tc = {"index": 0, "id": f"c{len(reqs)}", "type": "function", "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)}}
                chunks = [{"choices": [{"delta": {"content": f"Шаг {i + 1}. "}}]}, {"choices": [{"delta": {"tool_calls": [tc]}}]}]
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
        for c in chunks:
            self.wfile.write(f"data: {json.dumps(c, ensure_ascii=False)}\n\n".encode())
        self.wfile.write(b"data: [DONE]\n\n")


srv = ThreadingHTTPServer(("127.0.0.1", 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()


class FakeS:
    def get(self, *k): return {} if k[0] == "tools" else None


class Host:
    def __init__(self):
        self.workspace = Workspace(None); self.toolbox = T.Toolbox(FakeS(), None); self.toolbox.hooks["workspace"] = self.workspace
        self.said, self.pushes, self.stopping = [], [], threading.Event()
    def persona_name(self): return "Лира"
    def memory(self): return ""
    def llm_profile(self): return {"name": "mock", "kind": "openai", "base_url": f"http://127.0.0.1:{srv.server_port}/v1", "model": "m"}
    def max_steps(self): return 30
    def code_auto_run(self): return True
    def confirm(self, q): return True
    def ask_user(self, t, q): pass
    def announce(self, text): self.said.append(text)
    def push(self, title, text="", critical=False, file=None): self.pushes.append((title, text, critical))
    def emit(self, *a, **k): pass


def last_user(title):
    r = [x for x in reqs if x["title"] == title][-1]
    return next((m["content"] for m in reversed(r["messages"]) if m["role"] == "user"), "")


host = Host()
tm = TK.TaskManager(host)

# ---------- 1. долгое дело: блокнот, сообщения, ожидание, новые сведения, проверка перед итогом ----------
A = "Перебронировать рейс"
t = tm.create(A, "Рейс KL1234 отменили: перебронировать на ближайший и проследить за багажом")
ok(wait_for(lambda: t.status == "sleeping"), f"задача ушла ждать ответа ({t.status})")
ok(t.data.get("wait_reason") == "ответ KLM о новом рейсе" and t.data.get("wake_at"), "знает, чего ждёт и когда вернуться")
ok("ждёт" in T.t_task_status({}, {"tasks": tm}) and "ABC123" in T.t_task_status({}, {"tasks": tm}),
   "task_status: ждёт и что уже известно из блокнота")
nb = t.notebook()
ok("ABC123" in nb and "## Что известно" in nb, "факт записан в блокнот под «Что известно»")
ok(any("БЛОКНОТ ЗАДАЧИ" in r["system"] and "ABC123" in r["system"] for r in reqs if r["title"] == A and r["i"] >= 2),
   "блокнот — в каждом шаге модели")
ok(any("Готово, когда" in r["system"] for r in reqs if r["title"] == A), "план с критерием готовности виден модели")
notif = [p for p in host.pushes if p[0] == f"📌 {A}"]
ok(len(notif) == 1 and "KL1234" in notif[0][1], f"сообщение по ходу ушло пользователю, второе подряд — придержано ({len(notif)})")
ok("🔕" in (t.dir / "журнал.md").read_text(encoding="utf-8"), "придержанное сообщение — в журнале")

ok(wait_for(lambda: t.data.get("wait_reason") == "ответ по багажу" and t.status == "sleeping", 15),
   f"проснулся сам, проверил и снова ждёт ({t.status}, {t.data.get('wait_reason')})")
woke = [r for r in reqs if r["title"] == A and r["i"] == 5]
ok(woke and "⏰ Ты ждал: «ответ KLM о новом рейсе»" in next(m["content"] for m in reversed(woke[0]["messages"]) if m["role"] == "user"),
   "после пробуждения модель знает, чего ждала")
j = (t.dir / "журнал.md").read_text(encoding="utf-8")
ok("✋" in j and t.status != "done", "ранний finish остановлен: в плане есть невыполненное")
guard = [r for r in reqs if r["title"] == A and r["i"] == 6]
ok(guard and "найти багаж" in json.dumps(guard[0]["messages"][-1], ensure_ascii=False), "модель получила список невыполненного")

w = TK.dt.datetime.fromisoformat(t.data["wake_at"])
ok(w - TK.dt.datetime.now() > TK.dt.timedelta(hours=9), "долгое ожидание — до 10 часов")
r = T.t_tell_task({"name": "перебронировать", "text": "Багаж нашли: AMS-777"}, {"tasks": tm})
ok("Передал" in r, "tell_task из разговора: " + r)
ok(wait_for(lambda: t.status == "done", 15), f"новые сведения разбудили задачу — она довела дело до конца ({t.status})")
ok("Багаж нашли: AMS-777" in last_user(A) or any("Багаж нашли: AMS-777" in json.dumps(x["messages"], ensure_ascii=False) for x in reqs if x["title"] == A and x["i"] == 8),
   "сообщение пользователя дошло до модели")
ok("AMS-777" in t.notebook() and "ABC123" in t.notebook(), "в блокноте всё дело целиком")
ok(any(p[0].startswith("✅ Готово") for p in host.pushes) and any("готова" in s for s in host.said), "итог — уведомлением и голосом")
d = tm.detail(t.id)
ok("AMS-777" in d.get("notebook", ""), "студия получает блокнот (task_get)")

# ---------- 2. сжатие памяти: ранние шаги уходят, важное остаётся в блокноте ----------
TK.BUDGET = 4000
B = "Большое исследование"
tb = tm.create(B, "Собрать много сведений и сделать вывод")
ok(wait_for(lambda: tb.status == "done", 30), f"длинная задача завершена ({tb.status} {tb.error})")
ok(consolidations, f"модель переписала блокнот перед сжатием ({len(consolidations)} раз)")
ok(consolidations and "секретный код 4242" in json.dumps(consolidations[0], ensure_ascii=False), "в переписку блокнота ушли ранние шаги")
late = [r for r in reqs if r["title"] == B][-1]
ok(len(late["messages"]) < 2 * 11, f"разговор задачи сжат ({len(late['messages'])} сообщений вместо {2 * 11 + 1})")
ok("ранние шаги убраны" in late["messages"][0]["content"] and "Собрать много" in late["messages"][0]["content"], "цель на месте, пометка о сжатии")
ok("4242" in late["system"] and "консолидировано" in late["system"], "факт из ранних шагов виден через блокнот")
ok("🧠" in (tb.dir / "журнал.md").read_text(encoding="utf-8"), "сжатие отмечено в журнале")
TK.BUDGET = 60000

# ---------- 3. сбой модели — не падаем, повторяем позже ----------
C = "Сбой модели"
fail_left[0] = 4                  # 24.10: на 503 ядро само один раз тихо повторяет — две попытки задачи = четыре отказа
os.environ["DEWIAR_BUSY_WAIT"] = "0.1"
tc_ = tm.create(C, "Проверка повтора")
ok(wait_for(lambda: tc_.status == "sleeping"), f"сбой → ждёт повтора, а не «не получилось» ({tc_.status} {tc_.error})")
ok(wait_for(lambda: tc_.status == "done", 25), f"после двух сбоев задача выполнена ({tc_.status} {tc_.error})")
jc = (tc_.dir / "журнал.md").read_text(encoding="utf-8")
ok(jc.count("Попробую снова") == 2 and not tc_.error, "в журнале две попытки, ошибки нет")

# ---------- 4. перезапуск программы: ждущая задача и прерванная продолжаются сами ----------
D = "Проверить статус утром"
td = tm.create(D, "Проверить статус обращения позже")
ok(wait_for(lambda: td.status == "sleeping"), "задача ждёт")
te = tm.create("Прерванная работа", "Доделать после перезапуска", start=False)
te.data["status"] = "running"; te.save()                     # программу закрыли посреди работы
host.stopping.set(); time.sleep(2.5)                         # «выключили» первую копию
host2 = Host()
tm2 = TK.TaskManager(host2)
d2, e2 = tm2.get(td.id), tm2.get(te.id)
ok(d2.status == "sleeping" and e2.status == "paused" and e2.data.get("auto_resume"), f"после запуска: {d2.status}, {e2.status}")
ok(wait_for(lambda: d2.status == "done" and e2.status == "done", 25), f"обе продолжились и завершились ({d2.status}, {e2.status})")
ok(any(r["title"] == D and r["i"] == 1 for r in reqs), "ждущая проснулась в новой копии программы")
ok("продолжаю, где остановился" in (e2.dir / "журнал.md").read_text(encoding="utf-8"), "прерванная — «продолжаю, где остановился»")

# ---------- 6. «Задачи на часы»: модель ушла в размышления и не ответила — шаг повторяется, задача не падает ----------
think_left[0] = 2                 # ядро само повторяет один раз (без размышлений) — значит, один шаг задачи «не ответил»
tf = tm2.create("Долго думает", "Проверка: долгие размышления не роняют задачу")
ok(wait_for(lambda: tf.status == "done", 25), f"модель «думала и не ответила» — задача продолжилась и закончена ({tf.status} {tf.error})")
jf = (tf.dir / "журнал.md").read_text(encoding="utf-8")
ok("долгие размышления" in jf and not tf.error, "в журнале — «ушла в долгие размышления… прошу короче», ошибки нет")
ok(any("слишком долго размышлял" in json.dumps(r["messages"], ensure_ascii=False) for r in reqs if r["title"] == "Долго думает"),
   "модель получила просьбу действовать короче")

# ---------- 7. своя модель не понимает действия полем запроса — описываем их текстом, а не «не взялась за дело» ----------
tg = tm2.create("Без действий", "Проверка: модель без родных функций")
ok(wait_for(lambda: tg.status == "done", 25), f"модель без родных функций — задача сделана через текст ({tg.status} {tg.error})")
ok(plain and "↻ Модель не вызывает действия — описываю их ей текстом" in (tg.dir / "журнал.md").read_text(encoding="utf-8"),
   "в журнале — перешли на описание действий текстом")
# ---------- 5. сообщение готовой задаче — дополнение, работа продолжается ----------
tm2.tell(d2.id, "Ещё проверь, пришло ли письмо")
ok(wait_for(lambda: d2.status == "done" and d2.steps >= 3, 15), f"готовая задача приняла дополнение и снова закрылась ({d2.status}, шагов {d2.steps})")
ok(any("Ещё проверь" in json.dumps(r["messages"], ensure_ascii=False) for r in reqs if r["title"] == D), "дополнение дошло до модели")

# ---------- 6. остановка ждущей ----------
tf = tm2.create("Ждать долго", "ждать", start=False)
tf.data.update(status="sleeping", wake_at=(TK.dt.datetime.now() + TK.dt.timedelta(hours=5)).isoformat(timespec="seconds")); tf.save()
tm2.stop(tf.id)
ok(tf.status == "stopped" and not tf.data.get("wake_at"), "остановленная ждущая не проснётся")

print("ИТОГ:", "всё прошло" if not FAILS else f"провалов {len(FAILS)}")
sys.exit(1 if FAILS else 0)
