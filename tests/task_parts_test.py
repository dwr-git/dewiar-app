"""Долгие задачи: части работают одновременно (spawn_parts / wait_parts) и задача не упирается в 400 шагов, но и
не буксует бесконечно. Модель — заглушка со сценарием по названию задачи (как в long_task_test)."""
import json, os, re, sys, tempfile, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ.update(DEWIAR_WORKSPACE=str(tmp / "ws"), DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_CONFIG_DIR=str(tmp / "cfg"),
                  DEWIAR_TASK_BREATHER_SEC="0.2")
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

CITIES = ["Минск", "Гродно", "Брест"]
def part_script(city):
    return [("write_file", {"path": f"outputs/{city}.md", "content": f"# {city}\n\nПогода в городе {city}: ясно."}),
            ("show", {"path": f"outputs/{city}.md", "title": city}),
            ("finish", {"summary": f"{city}: ясно, +12. Файл outputs/{city}.md"})]
SCRIPTS = {
    "Обзор трёх городов": [
        ("update_plan", {"plan": "**Готово, когда:** обзор по трём городам\n\n- [ ] раздать части\n- [ ] собрать"}),
        ("spawn_parts", {"parts": [{"title": c, "goal": f"Погода в городе {c} на сегодня"} for c in CITIES]}),   # без формата — ошибка поручения
        ("spawn_parts", {"parts": [{"title": c, "goal": f"Погода в городе {c} на сегодня", "output": f"outputs/{c}.md: погода одной строкой"}
                                   for c in CITIES]}),
        ("wait_parts", {"minutes": 2}),
        ("update_plan", {"plan": "**Готово, когда:** обзор по трём городам\n\n- [x] раздать части\n- [x] собрать"}),
        ("finish", {"summary": "Обзор готов: Минск, Гродно, Брест — ясно."}),
    ],
    **{c: part_script(c) for c in CITIES},
    "Буксует": [("log", {"text": "думаю"})] * 400,
    "Длинная": [("remember", {"fact": f"факт {i}"}) for i in range(14)] + [("finish", {"summary": "Сделано за много кругов."})],
}
pos, reqs, inflight, peak = {}, [], set(), [0]
lock = threading.Lock()


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        sysm = body["messages"][0]["content"]
        if not body.get("tools"):
            out = '{"verdict": "ok"}' if sysm.startswith("Ты — строгий") else '{"lessons": []}' if sysm.startswith("Ты — аналитик") else "# Блокнот задачи\n"
            chunks, title = [{"choices": [{"delta": {"content": out}}]}], ""
        else:
            title = re.search(r"ЗАДАЧА: (.+)", sysm).group(1).strip()
            with lock:
                i = pos.get(title, 0); pos[title] = i + 1
                sc = SCRIPTS.get(title, [])
                name, args = sc[i] if i < len(sc) else ("finish", {"summary": "Готово."})
                reqs.append({"title": title, "i": i, "system": sysm, "tools": [t["function"]["name"] for t in body["tools"]], "tool": name})
                if title in CITIES:
                    inflight.add(title); peak[0] = max(peak[0], len(inflight))
            if title in CITIES:
                time.sleep(0.4)                      # часть «думает» — чтобы было видно, что части идут одновременно
                with lock:
                    inflight.discard(title)
            tc = {"index": 0, "id": f"c{len(reqs)}", "type": "function", "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)}}
            chunks = [{"choices": [{"delta": {"tool_calls": [tc]}}]}]
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
        for c in chunks:
            self.wfile.write(f"data: {json.dumps(c, ensure_ascii=False)}\n\n".encode())
        self.wfile.write(b"data: [DONE]\n\n")


srv = ThreadingHTTPServer(("127.0.0.1", 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()


class FakeS:
    def __init__(self): self.v = {}
    def get(self, *k): return {} if k[0] == "tools" else self.v.get(k)


class Host:
    def __init__(self):
        self.workspace = Workspace(None); self.s = FakeS(); self.toolbox = T.Toolbox(self.s, None); self.toolbox.hooks["workspace"] = self.workspace
        self.said, self.pushes, self.stopping, self.steps = [], [], threading.Event(), 30
    def persona_name(self): return "Лира"
    def memory(self): return ""
    def llm_profile(self): return {"name": "mock", "kind": "openai", "base_url": f"http://127.0.0.1:{srv.server_port}/v1", "model": "m"}
    def max_steps(self): return self.steps
    def code_auto_run(self): return True
    def confirm(self, q): return True
    def ask_user(self, t, q): pass
    def announce(self, text): self.said.append(text)
    def push(self, title, text="", critical=False, file=None): self.pushes.append((title, text, critical))
    def emit(self, *a, **k): pass


host = Host()
tm = TK.TaskManager(host)

# ---------- 1. части одновременно ----------
t = tm.create("Обзор трёх городов", "Погода в Минске, Гродно и Бресте — обзор")
ok(wait_for(lambda: t.status == "done", 60), f"главная задача готова ({t.status} {t.error})")
kids = [c for c in tm.tasks.values() if c.data.get("parent") == t.id]
ok(len(kids) == 3 and all(c.status == "done" for c in kids), f"три части выполнены: {[(c.title, c.status) for c in kids]}")
ok(peak[0] >= 2, f"части работали одновременно (сразу до {peak[0]})")
ok(peak[0] <= TK.PARTS_PARALLEL, f"не больше {TK.PARTS_PARALLEL} сразу")
first = [r for r in reqs if r["title"] == "Обзор трёх городов"][0]
ok("spawn_parts" in first["tools"] and "ЧАСТИ И РАЗВЕДКА" in first["system"], "у главной задачи есть spawn_parts и подсказка про части")
ok("Сравнение вариантов — 2–4 части" in first["system"] and "до 4 сразу" in first["system"], "правило объёма в подсказке (выпуск 6)")
kid_req = [r for r in reqs if r["title"] == "Минск"][0]
ok("spawn_parts" not in kid_req["tools"] and "Ты — помощник" in kid_req["system"], "часть сама частей не раздаёт, знает, что она помощник")
ok("часть большой задачи «Обзор трёх городов»" in kid_req["system"], "часть знает общую цель")
waited = [r for r in reqs if r["title"] == "Обзор трёх городов" and r["i"] == 4]
hist = json.loads((t.dir / "история.json").read_text(encoding="utf-8"))
got = json.dumps(hist, ensure_ascii=False)
ok("Гродно: ясно, +12" in got and "parts/Брест/Брест.md" in got, "wait_parts вернул итоги и пути файлов частей")
ok(all((t.dir / "parts" / c / f"{c}.md").is_file() for c in CITIES), "файлы частей скопированы в parts/ главной задачи")
ok(not any(s.startswith(("Задача «Минск»", "Задача «Гродно»", "Задача «Брест»")) for s in host.said) and any("Обзор трёх городов" in s for s in host.said),
   f"объявлена только главная задача: {host.said}")

# ---------- 2. стоп главной — стоп частей ----------
SCRIPTS["Стоп"] = [("spawn_parts", {"parts": [{"title": "Долгая часть", "goal": "долго", "output": "outputs/долго.md — отчёт"}]}), ("wait_parts", {"minutes": 5})]
SCRIPTS["Долгая часть"] = [("wait", {"minutes": 60, "reason": "ждём"})]
ts = tm.create("Стоп", "проверка остановки")
ok(wait_for(lambda: any(c.data.get("parent") == ts.id for c in tm.tasks.values()) and ts.data.get("activity", "").startswith("жду части")),
   "главная ждёт часть")
tm.stop(ts.id)
kid = next(c for c in tm.tasks.values() if c.data.get("parent") == ts.id)
ok(wait_for(lambda: ts.status == "stopped" and kid.status == "stopped", 10), f"остановлены обе ({ts.status}, {kid.status})")

# ---------- 3. больше 400 шагов можно, буксовать — нельзя ----------
host.steps = 3
tl = tm.create("Длинная", "много шагов")
ok(wait_for(lambda: tl.status == "done", 40), f"задача прошла больше пяти кругов (раньше предел — 5) и закончилась ({tl.status}, шагов {tl.steps}, кругов)")
ok(tl.steps >= 15, f"шагов: {tl.steps} (кругов по 3 — больше пяти)")
tb = tm.create("Буксует", "ничего не продвигается")
ok(wait_for(lambda: tb.status == "paused", 40), f"буксующая задача остановилась сама ({tb.status}, шагов {tb.steps})")
ok(tb.steps <= 3 * (TK.STALE_CYCLES + 1), f"рано, а не через 1200 шагов ({tb.steps})")
ok("без продвижения" in (tb.dir / "журнал.md").read_text(encoding="utf-8") and any("буксует" in s for s in host.said), "в журнале и голосом — почему")
host.s.v[("tasks", "cycles")] = 2
ok(tm._cycles() == 2, "число кругов — из настроек tasks.cycles")

# GitHub, 23.10: «готово» записывалось раньше истории, история — не атомарно: проверка читала пустой файл (JSONDecodeError)
src = (ROOT / "core/tasks.py").read_text(encoding="utf-8")
ok("hist.write_text" not in src and "os.replace(tmp, path)" in src[src.index("def _write_hist"):], "история задачи пишется через временный файл и замену")
end = src[src.index("пользователь написал, пока задача заканчивала круг"):]
ok(end.index("_write_hist(hist, msgs)") < end.index("t.save()"), "в конце круга история пишется раньше состояния «готово»")

host.stopping.set()
print("ALL OK" if not FAILS else f"ошибок: {len(FAILS)}")
sys.exit(1 if FAILS else 0)
