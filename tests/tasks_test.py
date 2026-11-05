"""Фоновые задачи и режим «Код»: модель (заглушка) ведёт план, ищет и правит код в рабочей копии git-проекта,
запускает тест, спрашивает пользователя, завершает; изменения принимаются в проект только по команде."""
import json, os, subprocess, sys, tempfile, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ.update(DEWIAR_WORKSPACE=str(tmp / "ws"), DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_CONFIG_DIR=str(tmp / "cfg"))
sys.path.insert(0, str(ROOT / "core"))
from workspace import Workspace  # noqa: E402
from tasks import TaskManager  # noqa: E402
import tools as T  # noqa: E402

def ok(c, m): print(("✅ " if c else "❌ ") + m)

# проект с ошибкой
proj = tmp / "calc"; proj.mkdir()
(proj / "calc.py").write_text("def add(a, b):\n    return a - b\n")
(proj / "test_calc.py").write_text("from calc import add\nassert add(2, 3) == 5, 'add сломан'\nprint('тест прошёл')\n")
g = lambda *a: subprocess.run(["git", "-C", str(proj)] + list(a), capture_output=True, text=True, env=dict(os.environ, GIT_AUTHOR_NAME="u", GIT_AUTHOR_EMAIL="u@x", GIT_COMMITTER_NAME="u", GIT_COMMITTER_EMAIL="u@x"))
g("init", "-q"); g("add", "-A"); g("commit", "-qm", "init")
(proj / "README.md").write_text("незакоммиченная правка пользователя\n")      # должна попасть в рабочую копию

PLAN = [
    ("update_plan", {"plan": "- [ ] найти add\n- [ ] исправить\n- [ ] запустить тест"}),
    ("code_search", {"pattern": "def add"}),
    ("code_read", {"path": "calc.py"}),
    ("code_edit", {"path": "calc.py", "old": "return a - b", "new": "return a + b"}),
    ("code_run", {"command": "python3 test_calc.py"}),
    ("ask_user", {"question": "Закоммитить изменения?"}),
    ("update_plan", {"plan": "- [x] найти add — calc.py\n- [x] исправить — calc.py\n- [x] запустить тест — код 0: 1 passed"}),   # 0.84: «[x]» — с доказательством
    ("code_diff", {}),
    ("finish", {"summary": "Исправил **add**: было вычитание. Тест проходит."}),
]
seen = []
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        seen.append(body)
        n = sum(1 for m in body["messages"] if m["role"] == "assistant")
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
        name, args = PLAN[min(n, len(PLAN) - 1)]
        tc = {"index": 0, "id": f"c{n}", "type": "function", "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)}}
        for c in ([{"choices": [{"delta": {"content": f"Шаг {n + 1}. "}}]}], [{"choices": [{"delta": {"tool_calls": [tc]}}]}]):
            self.wfile.write(f"data: {json.dumps(c[0], ensure_ascii=False)}\n\n".encode())
        self.wfile.write(b"data: [DONE]\n\n")
srv = ThreadingHTTPServer(("127.0.0.1", 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()

class FakeS:
    def get(self, *k): return {} if k[0] == "tools" else None
class Host:
    def __init__(self):
        self.workspace = Workspace(None); self.toolbox = T.Toolbox(FakeS(), None); self.toolbox.hooks["workspace"] = self.workspace
        self.said, self.events, self.questions, self.confirms = [], [], [], []
    def persona_name(self): return "Девиар"
    def memory(self): return ""
    def llm_profile(self): return {"name": "mock", "kind": "openai", "base_url": f"http://127.0.0.1:{srv.server_port}/v1", "model": "m"}
    def max_steps(self): return 30
    def code_auto_run(self): return False
    def confirm(self, q): self.confirms.append(q); return True
    def ask_user(self, t, q):
        self.questions.append(q)
        threading.Timer(0.3, lambda: tm.answer(t.id, "Нет, не коммить")).start()
    def announce(self, text): self.said.append(text)
    def emit(self, *a, **k): self.events.append((a, k))
host = Host()
tm = TaskManager(host)
t = tm.create("Починить калькулятор", "Функция add возвращает неверный результат — исправь и проверь тестом", str(proj))
for _ in range(100):
    if t.status in ("done", "failed", "stopped"): break
    time.sleep(0.2)
ok(t.status == "done", f"задача выполнена ({t.status}, шагов {t.steps}{', ' + t.error if t.error else ''})")
d = tm.detail(t.id)
ok("[x] исправить" in d["plan"] and t.data.get("progress") == [3, 3], "план ведётся и отмечается")
ok("code_edit" in d["journal"] and "тест прошёл" in d["journal"], "журнал: правка и вывод теста")
ok(host.confirms and "python3 test_calc.py" in host.confirms[0], "команда в проекте — с подтверждением")
ok(host.questions == ["Закоммитить изменения?"] and "Нет, не коммить" in d["journal"], "вопрос пользователю и ответ")
ok(d["summary"].startswith("# Итог") and "Тест проходит" in d["summary"], "итог записан")
ok(any("готова" in s for s in host.said), "о готовности сказано голосом")
ok("return a - b" in (proj / "calc.py").read_text(), "проект не тронут до принятия")
ok(d.get("changes") == [("modified", "calc.py")] or d.get("changes") == [["modified", "calc.py"]], f"в изменениях только calc.py ({d.get('changes')})")
ok("-    return a - b" in d["diff"] and "+    return a + b" in d["diff"], "diff показывает правку")
sys_prompt = seen[0]["messages"][0]["content"] if seen[0]["messages"][0]["role"] == "system" else json.dumps(seen[0])
ok("Починить калькулятор" in json.dumps(seen[0], ensure_ascii=False) and any(tl["function"]["name"] == "code_edit" for tl in seen[0]["tools"]),
   "модель получила цель и инструменты кода")
msg = tm.accept(t.id)
ok("return a + b" in (proj / "calc.py").read_text() and "перенесены" in msg, "«Принять» — правка в проекте")
ok((proj / "README.md").read_text().startswith("незакоммиченная"), "правка пользователя в проекте цела")
ok(not (t.dir / "рабочая копия").exists() and "рабочая копия" not in g("worktree", "list").stdout, "рабочая копия убрана")
# без git и «Отклонить»
proj2 = tmp / "plain"; proj2.mkdir(); (proj2 / "calc.py").write_text("def add(a, b):\n    return a - b\n"); (proj2 / "test_calc.py").write_text((proj / "test_calc.py").read_text())
PLAN[:] = [("code_edit", {"path": "calc.py", "old": "return a - b", "new": "return a + b"}), ("finish", {"summary": "Готово"})]
t2 = tm.create("Без git", "Исправь add", str(proj2))
for _ in range(60):
    if t2.status in ("done", "failed"): break
    time.sleep(0.2)
d2 = tm.detail(t2.id)
ok(t2.status == "done" and "+    return a + b" in d2["diff"], "проект без git: копия и diff")
tm.discard(t2.id)
ok("return a - b" in (proj2 / "calc.py").read_text() and not (t2.dir / "рабочая копия").exists(), "«Отклонить» — проект не изменён")
# задача без проекта + инструменты чата
PLAN[:] = [("save_note", {"title": "Отчёт", "text": "Нашёл три варианта"}), ("finish", {"summary": "Отчёт в заметках"})]
host.toolbox.hooks["tasks"] = tm
out = host.toolbox.run("start_task", {"title": "Исследование", "goal": "Сравни три варианта"})
t3 = tm.get("Исследование")
for _ in range(60):
    if t3.status == "done": break
    time.sleep(0.2)
ok("запущена" in out and t3.status == "done" and (tmp / "ws/Заметки/Отчёт.md").exists(), "start_task из разговора → заметка в папке")
st = host.toolbox.run("task_status", {})
ok("Исследование" in st and "готово" in st, "task_status рассказывает о задачах")
tm2 = TaskManager(host)
ok(len(tm2.list()) == 3, "задачи переживают перезапуск")
