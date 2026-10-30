"""Длинные задачи — присмотр (core/tasks.py: _watch, _ask_remind, _fail) и дела по расписанию с повтором
(engine_music._run_job). Модель — заглушка: по названию задачи — свой сценарий, «Медленная» отвечает с паузой.
Шаг молчит дольше HANG_SEC — «задача не отвечает» (уведомление, пульс), ожил — «шаг ожил»; долгая задача шлёт
весточку «как идёт»; вопрос без ответа — напоминание один раз; ошибка в самой программе — честная остановка с
голосом, уведомлением и записью в пульс; дело по расписанию: сбой → повтор → успех, итог записан в само дело."""
import json, os, re, sys, tempfile, threading, time, types
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ.update(DEWIAR_WORKSPACE=str(tmp / "ws"), DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_CONFIG_DIR=str(tmp / "cfg"),
                  DEWIAR_TASK_HANG_SEC="1.5", DEWIAR_TASK_PROGRESS_FIRST="1", DEWIAR_TASK_PROGRESS_EVERY="2",
                  DEWIAR_TASK_ASK_REMIND_SEC="1.5", DEWIAR_JOB_RETRY_SCALE="0.001")
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


SCRIPTS = {
    "Медленная": [("update_plan", {"plan": "- [x] собрать\n- [ ] проверить\n- [ ] итог"}), ("log", {"text": "думаю"}),
                  ("update_plan", {"plan": "- [x] собрать\n- [x] проверить\n- [ ] итог"}), ("log", {"text": "ещё"}),
                  ("update_plan", {"plan": "- [x] собрать\n- [x] проверить\n- [x] итог"}), ("finish", {"summary": "Сделано медленно."})],
    "Вопрос": [("ask_user", {"question": "Какой формат отчёта нужен?"}), ("finish", {"summary": "Ок."})],
    "Сломанная": [("log", {"text": "шаг"}), ("finish", {"summary": "не дойдёт"})],
}
SLOW = {"Медленная": {1: 2.6}}              # шаг №1 (второй запрос) — пауза перед ответом
pos, lock = {}, threading.Lock()


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        sysm = body["messages"][0]["content"]
        if not body.get("tools"):
            out = '{"verdict": "ok"}' if sysm.startswith("Ты — строгий") else '{"lessons": []}'
            chunks = [{"choices": [{"delta": {"content": out}}]}]
        else:
            title = re.search(r"ЗАДАЧА: (.+)", sysm).group(1).strip()
            with lock:
                i = pos.get(title, 0)
                pos[title] = i + 1
            time.sleep(SLOW.get(title, {}).get(i, 0.25))
            sc = SCRIPTS.get(title, [])
            name, args = sc[i] if i < len(sc) else ("finish", {"summary": "Готово."})
            tc = {"index": 0, "id": f"c{i}{title}", "type": "function", "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)}}
            chunks = [{"choices": [{"delta": {"content": f"Шаг {i + 1}. "}}]}, {"choices": [{"delta": {"tool_calls": [tc]}}]}]
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
        for c in chunks:
            self.wfile.write(f"data: {json.dumps(c, ensure_ascii=False)}\n\n".encode())
        self.wfile.write(b"data: [DONE]\n\n")


srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()


class FakeS:
    def get(self, *k):
        return {} if k[0] == "tools" else None


class Host:
    def __init__(self):
        self.workspace = Workspace(None); self.toolbox = T.Toolbox(FakeS(), None); self.toolbox.hooks["workspace"] = self.workspace
        self.said, self.pushes, self.problems, self.stopping = [], [], [], threading.Event()
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
    def health_problem(self, text, kind="error"): self.problems.append((kind, text))


host = Host()
tm = TK.TaskManager(host)


def journal(t):
    return (t.dir / "журнал.md").read_text(encoding="utf-8")


# ---------- зависший шаг и весточки ----------
t = tm.create("Медленная", "Сделать медленно")
ok(wait_for(lambda: tm.get(t.id).status == "done", 40), f"медленная задача доделана: {tm.get(t.id).status}")
j = journal(t)
ok("не отвечает" in j and "ожил" in j, "шаг молчал дольше порога — «не отвечает», потом «ожил» (журнал)")
ok(any(p[0].startswith("⏳ Задача не отвечает") and p[2] for p in host.pushes), "о зависшем шаге — важное уведомление")
ok(any(k == "task" and "завис" in x for k, x in host.problems), "зависание — в пульс «Здоровья» и журнал сбоев")
prog = [p for p in host.pushes if p[0].startswith("⏱ Работаю над")]
ok(bool(prog) and ("из 3 по плану" in prog[0][1] or "шагов" in prog[0][1]), f"долгая задача — весточка «как идёт»: {prog[:1]}")
ok(len(prog) <= 3, f"весточки не чаще срока: {len(prog)}")

# ---------- вопрос без ответа ----------
q = tm.create("Вопрос", "Спросить формат")
ok(wait_for(lambda: tm.get(q.id).status == "waiting", 15), "задача спросила и ждёт")
ok(wait_for(lambda: any(p[0].startswith("❓ Задача ждёт ответа") for p in host.pushes), 10), "вопрос без ответа — напоминание")
time.sleep(2.5)
ok(len([p for p in host.pushes if p[0].startswith("❓ Задача ждёт ответа")]) == 1, "напоминание — один раз")
tm.answer(q.id, "PDF")
ok(wait_for(lambda: tm.get(q.id).status == "done", 15), "ответили — доделала")

# ---------- ошибка в программе ----------
orig, orig_sys = TK.TaskManager._tool_raw, TK.TaskManager._system
seen = {"n": 0}


def boom(self, t, name, args):
    if t.title == "Сломанная" and name == "log":
        raise KeyError("profile")                                   # инструмент упал — модели ответ, разработчику пульс
    return orig(self, t, name, args)


def sys_boom(self, t):
    if t.title == "Сломанная":
        seen["n"] += 1
        if seen["n"] >= 2:
            raise AttributeError("'NoneType' object has no attribute 'strip'")   # упала сама задача
    return orig_sys(self, t)


TK.TaskManager._tool_raw, TK.TaskManager._system = boom, sys_boom
b = tm.create("Сломанная", "Упасть")
ok(wait_for(lambda: tm.get(b.id).status == "failed", 15), "ошибка программы — задача остановлена честно")
ok("внутренняя ошибка" in tm.get(b.id).error and any("Сломанная" in s for s in host.said), "сказано голосом, что сломалось")
ok(any(p[0].startswith("⚠ Задача остановилась") for p in host.pushes), "и уведомлением")
ok(any(k == "task" and "AttributeError" in x for k, x in host.problems), "и в пульс разработчику (тип ошибки, без содержания задачи)")
ok(any(k == "task" and "инструмент log: KeyError" in x for k, x in host.problems), "упавший инструмент — тоже в пульс")
TK.TaskManager._tool_raw, TK.TaskManager._system = orig, orig_sys

# ---------- дело по расписанию: сбой → повтор → успех ----------
import engine_music as EM  # noqa: E402
calls, upd, probs, sent, pushes = [], [], [], [], []


def fake_ask(text, via=None, raw=False, shown=None, report=None, **k):
    calls.append(via is not None)
    threading.Thread(target=lambda: report(len(calls) >= 2, "Курс доллара — 90." if len(calls) >= 2 else "модель не ответила")).start()


bot = types.SimpleNamespace(paired=lambda: True, send=lambda t: sent.append(t))
me = types.SimpleNamespace(turn=None, state="idle", alarm=None, ask=fake_ask, _job_prompt=lambda it: "сделай", _bot_for=lambda d: bot,
                           reminders=types.SimpleNamespace(update=lambda rid, p: upd.append(p)), stopping=threading.Event(),
                           health_problem=lambda t, kind="error": probs.append((kind, t)), emit=lambda *a, **k: pushes.append(k),
                           JOB_RETRY_MIN=EM.MusicMixin.JOB_RETRY_MIN if hasattr(EM, "MusicMixin") else (5, 15))
_mm = next(c for c in vars(EM).values() if isinstance(c, type) and "_run_job" in vars(c))
me.job_nothing = lambda text: _mm.job_nothing(text) if "job_nothing" in vars(_mm) else False   # 0.51: «ничего нового» — молчать
me._run_job = lambda item, attempt=0: run(item, attempt)


def run(item, attempt=0):
    cls = next(c for c in vars(EM).values() if isinstance(c, type) and "_run_job" in vars(c))
    return cls._run_job(me, item, attempt)


run({"id": "j1", "text": "Курс доллара", "deliver": "telegram"})
ok(len(calls) == 2, f"дело не удалось — повторено: {len(calls)} попыток")
ok(len(sent) == 1 and "90" in sent[0], f"в Telegram ушёл только удачный ответ, без ошибки: {sent}")
ok(upd and upd[0]["last_ok"] is False and upd[-1]["last_ok"] is True, "итог записан в само дело (неудача, потом успех)")
ok(probs and probs[0][0] == "job", "сбой дела — в журнал сбоев")

# отчёт №407 (29.10): модели не хватает окна контекста — повтор через 5 и 15 минут упадёт так же; сразу итог, без повторов
from llm import CTX_TEXT  # noqa: E402
calls.clear(); sent.clear(); pushes.clear()
me.ask = lambda text, via=None, raw=False, shown=None, report=None, **k: (calls.append(1), threading.Thread(target=lambda: report(False, CTX_TEXT)).start())
run({"id": "j2", "text": "Проверить почту", "deliver": "telegram"})
ok(len(calls) == 1 and sent and sent[-1].startswith("⚠") and "окна контекста" in sent[-1],
   f"не хватает окна контекста — без повторов, сразу понятное «не получилось»: {len(calls)} попыток, {sent[-1][:60] if sent else ''!r}")

srv.shutdown()
print("\nИТОГ:", "всё прошло" if not FAILS else f"провалов {len(FAILS)}")
sys.exit(1 if FAILS else 0)
