"""Задача не крутится без конца и не жжёт токены (№54, №58/59: «жрёт токены, ничего не отменяет»):
— отказ человека запоминается: то же действие больше не спрашиваем; три отказа (или попытки после отказа) — пауза;
— вопросы без ответа (человека нет рядом) — после двух подряд пауза, а не вопрос каждые 2 минуты всю ночь;
— шаги без продвижения (разные команды, ни плана, ни блокнота, ни файлов) — через STUCK_STEPS новый план, на втором застое
  пауза, а не через 160;
— «останови задачу», пока она ждёт ответа «да/нет», срабатывает сразу (confirm слушает cancel)."""
import json, os, re, sys, tempfile, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ.update(DEWIAR_WORKSPACE=str(tmp / "ws"), DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_CONFIG_DIR=str(tmp / "cfg"),
                  DEWIAR_TASK_BREATHER_SEC="0.2", DEWIAR_TASK_STUCK_STEPS="12")
sys.path.insert(0, str(ROOT / "core"))
from workspace import Workspace  # noqa: E402
import tasks as TK  # noqa: E402
import tools as T  # noqa: E402

FAILS = []
def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        FAILS.append(m)

def wait_for(cond, sec=30):
    end = time.time() + sec
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.1)
    return False

# модель «как у Admin»: перебирает варианты одной команды, каждый раз чуть другие аргументы
DIRS = [f'Get-ChildItem "C:\\Users\\Admin\\Documents\\Dewiar\\Задачи\\вариант {i}"' for i in range(200)]
SCRIPTS = {
    "Отказы": [("run_command", {"command": c}) for c in DIRS],
    "Молчание": [("run_command", {"command": c}) for c in DIRS],
    "Буксует": [("read_file", {"path": f"заметки/файл {i}.md"}) for i in range(200)],
    "Стоп при вопросе": [("run_command", {"command": c}) for c in DIRS],
}
pos, lock = {}, threading.Lock()


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        sysm = body["messages"][0]["content"]
        if not body.get("tools"):
            out = '{"verdict": "ok"}' if sysm.startswith("Ты — строгий") else '{"lessons": []}' if sysm.startswith("Ты — аналитик") else "# Блокнот задачи\n"
            chunks = [{"choices": [{"delta": {"content": out}}]}]
        else:
            title = re.search(r"ЗАДАЧА: (.+)", sysm).group(1).strip()
            with lock:
                i = pos.get(title, 0); pos[title] = i + 1
            sc = SCRIPTS.get(title, [])
            name, args = sc[i] if i < len(sc) else ("finish", {"summary": "Готово."})
            tc = {"index": 0, "id": f"c{i}", "type": "function", "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)}}
            chunks = [{"choices": [{"delta": {"tool_calls": [tc]}}]}]
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
        for c in chunks:
            self.wfile.write(f"data: {json.dumps(c, ensure_ascii=False)}\n\n".encode())
        self.wfile.write(b"data: [DONE]\n\n")


srv = ThreadingHTTPServer(("127.0.0.1", 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()


class FakeS:
    def get(self, *k): return {} if k[0] == "tools" else None


class Host:
    def __init__(self):
        self.workspace = Workspace(None); self.s = FakeS(); self.toolbox = T.Toolbox(self.s, None); self.toolbox.hooks["workspace"] = self.workspace
        self.toolbox.run = lambda name, args: "Готово: выполнено."          # настоящие команды в проверке не запускаем
        self.said, self.asked, self.stopping, self.answer = [], [], threading.Event(), False
    def persona_name(self): return "Лира"
    def memory(self): return ""
    def llm_profile(self): return {"name": "mock", "kind": "openai", "base_url": f"http://127.0.0.1:{srv.server_port}/v1", "model": "m"}
    def max_steps(self): return 80
    def code_auto_run(self): return False
    def confirm(self, q, timeout=120, cancel=None):
        self.asked.append(q)
        if self.answer == "wait":                        # человек не отвечает; ждём, пока задачу не остановят
            while not cancel.is_set():
                time.sleep(0.05)
            return None
        return self.answer
    def ask_user(self, t, q): pass
    def announce(self, text): self.said.append(text)
    def push(self, title, text="", critical=False, file=None): pass
    def emit(self, *a, **k): pass


host = Host()
tm = TK.TaskManager(host)


def journal(t):
    return (t.dir / "журнал.md").read_text(encoding="utf-8")


# ── 1. отказы ──
host.answer = False
t = tm.create("Отказы", "найти файлы задачи")
ok(wait_for(lambda: t.status == "paused", 30), f"после отказов — пауза ({t.status}, шагов {t.steps})")
ok(len(host.asked) == 1, f"спросили один раз, дальше не спрашивали: {len(host.asked)}")
ok(t.steps <= TK.ASK_DECLINES + 1, f"пауза сразу, а не через сотни шагов: {t.steps}")
hist = json.dumps(json.loads((t.dir / "история.json").read_text(encoding="utf-8")), ensure_ascii=False)
ok("уже отказал" in hist and "не пробуй его другими командами" in hist, "модели сказано: отказали — не пробуй то же другими командами")
ok("✋ Пользователь отказал" in journal(t) and "⏸" in journal(t), "в журнале: отказ и пауза с причиной")
ok(any("Отказы" in s and "на паузе" in s for s in host.said), f"объявлено голосом: {host.said[-1:]}")
# «продолжи» — счёт заново: снова один вопрос
host.asked.clear(); n0 = t.steps
tm.start(t.id)
ok(wait_for(lambda: t.status == "paused" and t.steps > n0, 30) and len(host.asked) == 1, f"после «продолжи» — снова один вопрос и пауза: {len(host.asked)}")

# ── 2. вопросы без ответа ──
host.answer = None; host.asked.clear()
t2 = tm.create("Молчание", "найти файлы задачи")
ok(wait_for(lambda: t2.status == "paused", 30), f"никто не отвечает — пауза ({t2.status})")
ok(len(host.asked) == TK.ASK_SILENT, f"спросили {TK.ASK_SILENT} раза, не всю ночь: {len(host.asked)}")
ok("❔ Нет ответа" in journal(t2) and "когда будете рядом" in journal(t2), "в журнале: «нет ответа» и как продолжить")

# ── 3. буксует без продвижения ──
t3 = tm.create("Буксует", "прочитать заметки")
ok(wait_for(lambda: t3.status == "paused", 40), f"буксует — пауза ({t3.status}, шагов {t3.steps})")
# выпуск 4 «Больших задач»: первый застой — новый план (а не пауза), пауза — только на втором подряд без работы
ok(24 <= t3.steps <= 40, f"через ~2×STUCK_STEPS шагов (сначала новый план), а не через 2 круга по 80: {t3.steps}")
ok("🔄 Застой" in journal(t3) and "ЗАСТОЙ" in (t3.dir / "история.json").read_text(encoding="utf-8"), "первый застой — просьба составить новый план")
ok("без продвижения" in journal(t3) and any("Буксует" in s and "буксует" in s for s in host.said), "журнал и голос: «буксует»")

# ── 4. «стоп», пока задача ждёт «да/нет» ──
host.answer = "wait"; host.asked.clear()
t4 = tm.create("Стоп при вопросе", "найти файлы задачи")
ok(wait_for(lambda: len(host.asked) == 1, 20), "задача спросила разрешение")
t0 = time.time(); tm.stop(t4.id)
ok(wait_for(lambda: t4.status == "stopped", 5), f"остановилась сразу ({t4.status}, {time.time() - t0:.1f} с)")

# ── 5. engine.confirm: cancel, «нет ответа» = None, «нет» = False ──
import engine_answer as EA  # noqa: E402


class Fake:
    def __init__(self): self.pending_confirm, self.events, self.spoken = None, [], []
    def emit(self, kind, **k): self.events.append((kind, k))
    def announce(self, x): self.spoken.append(x)


f = Fake(); cancel = threading.Event()
threading.Timer(0.4, cancel.set).start()
t0 = time.time(); r = EA.AnswerMixin.confirm(f, "Задача «X»: выполнить команду?", timeout=30, cancel=cancel)
ok(r is None and time.time() - t0 < 2 and f.pending_confirm is None and f.events[-1][0] == "confirm_done",
   f"стоп во время вопроса: сразу, вопрос закрыт ({r}, {time.time() - t0:.1f} с)")
f = Fake()
ok(EA.AnswerMixin.confirm(f, "Вопрос?", timeout=0.3) is None, "никто не ответил — None (не «нет»)")
f = Fake()
def say_no():
    while f.pending_confirm is None:
        time.sleep(0.02)
    f.pending_confirm["event"].set()
threading.Thread(target=say_no).start()
ok(EA.AnswerMixin.confirm(f, "Вопрос?", timeout=5) is False, "«нет» — False")
f = Fake(); f.pending_confirm = {"event": threading.Event(), "answer": False}; cancel = threading.Event(); cancel.set()
t0 = time.time()
ok(EA.AnswerMixin.confirm(f, "Второй?", timeout=5, cancel=cancel) is None and time.time() - t0 < 1, "остановленная задача не ждёт 2 минуты чужого вопроса")

print("\nИТОГ:", "всё прошло" if not FAILS else f"провалов {len(FAILS)}")
os._exit(1 if FAILS else 0)
