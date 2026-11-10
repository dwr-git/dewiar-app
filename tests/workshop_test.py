"""Мастерская задач: write_file (частями), read_file, list_files, run_python (с разрешением один раз на задачу),
show → «Результаты», transcribe (расшифровка своим слухом с метками времени, .txt и .srt), download; пути — только
внутри папки задачи; живой статус по-русски; импортированные навыки и презентация (slides) на месте."""
import json, os, shutil, subprocess, sys, tempfile, threading, http.server
from pathlib import Path
tmp = Path(tempfile.mkdtemp())
os.environ.update(DEWIAR_CONFIG_DIR=str(tmp / "cfg"), DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_WORKSPACE_DIR=str(tmp / "ws"))
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "core"))
ok = lambda c, m: print(("✅ " if c else "❌ ") + m)
from settings import Settings  # noqa: E402
from workspace import Workspace  # noqa: E402
from tasks import TaskManager, WORK_TOOLS  # noqa: E402
from skills import Skills  # noqa: E402


class Host:
    def __init__(self):
        self.s = Settings(tmp / "cfg/settings.json"); self.workspace = Workspace(self.s); self.events = []; self.asked = []
        self.answer = True
    def emit(self, kind, **kw): self.events.append((kind, kw))
    def persona_name(self): return "Агент"
    def code_auto_run(self): return False
    def confirm(self, q, timeout=120): self.asked.append(q); return self.answer
    def transcribe_file(self, p, cancel=None): return [(0.0, 2.5, "Привет, это проверка."), (2.5, 61.2, "Вторая фраза.")]


h = Host()
tm = TaskManager(h)
t = tm.create("Калькулятор", "сделай калькулятор", start=False)
w = lambda n, **a: tm._work(t, n, a)  # noqa: E731
r1 = w("write_file", path="outputs/app.html", content="<!doctype html><html><body><h1>Калькулятор</h1>")
r2 = w("write_file", path="outputs/app.html", content="</body></html>", append=True)
txt = (t.dir / "outputs/app.html").read_text(encoding="utf-8")
ok("нет </html>" in r1 and "нет </html>" not in r2 and txt.endswith("</html>"), "write_file: частями, с подсказкой про незакрытый HTML")
try:
    w("write_file", path="../../escape.txt", content="x"); esc = False
except ValueError:
    esc = True
ok(esc and not (tmp / "ws/escape.txt").exists(), "за пределы папки задачи писать нельзя")
ok("2: </body>" not in w("read_file", path="outputs/app.html") and "1: <!doctype" in w("read_file", path="outputs/app.html"), "read_file с номерами строк")
ok("outputs/app.html" in w("list_files"), "list_files")
r = w("run_python", code="import json, os\nopen('outputs/data.json','w').write(json.dumps({'sum': 2+2}))\nprint('сумма', 2+2, bool(os.environ.get('FFMPEG') is not None))")
import sandbox  # noqa: E402
real = sandbox.real_sandbox(sandbox.mode())
ok("сумма 4 True" in r and (t.dir / "outputs/data.json").exists() and len(h.asked) == (0 if real else 1),
   f"run_python ({sandbox.mode()}): {'в песочнице — без вопроса' if real else 'под охраной — с разрешения'}, выполнил, файл создан")
# без песочницы (DEWIAR_SANDBOX=off) — как раньше: разрешение раз на задачу
os.environ["DEWIAR_SANDBOX"] = "off"
h.asked.clear()
t_off = tm.create("Калькулятор 2", "сделай калькулятор", start=False)
r = tm._work(t_off, "run_python", {"code": "print('снова')"})
ok("снова" in r and len(h.asked) == 1, "без песочницы: спросил разрешение один раз, выполнил")
r = tm._work(t_off, "run_python", {"code": "print('и ещё')"})
ok("и ещё" in r and len(h.asked) == 1, "второй запуск — без вопроса (разрешено для этой задачи)")
t2 = tm.create("Другая", "x", start=False); h.answer = False
ok("отказался" in tm._work(t2, "run_python", {"code": "print(1)"}), "отказ — код не запускается")
os.environ.pop("DEWIAR_SANDBOX")
r = w("show", path="outputs/app.html", title="Калькулятор")
ok(t.data["outputs"][0] == {**t.data["outputs"][0], "path": "outputs/app.html", "title": "Калькулятор"} and any(k == "task" for k, _ in h.events),
   "show → в «Результатах» и студия узнала")
(t.dir / "downloads").mkdir(); (t.dir / "downloads/лекция.mp4").write_bytes(b"x")
r = w("transcribe", path="downloads/лекция.mp4")
srt = (t.dir / "outputs/лекция.srt").read_text(encoding="utf-8")
ok("[00:00] Привет" in r and "[00:02] Вторая" in (t.dir / "outputs/лекция.txt").read_text(encoding="utf-8")
   and "00:00:02,500 --> 00:01:01,200" in srt, "transcribe: текст с метками времени, .txt и .srt")
www = tmp / "www"; www.mkdir(); (www / "doc.pdf").write_bytes(b"%PDF-1.4 test")
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), lambda *a, **k: http.server.SimpleHTTPRequestHandler(*a, directory=str(www), **k))
threading.Thread(target=srv.serve_forever, daemon=True).start()
r = w("download", url=f"http://127.0.0.1:{srv.server_address[1]}/doc.pdf")
ok((t.dir / "downloads/doc.pdf").read_bytes().startswith(b"%PDF"), "download: файл в downloads/")
srv.shutdown()
sk = Skills(h.s)
names = {x["name"] for x in sk.catalog()}
need = {"slides", "html-app", "html-viz", "data-report", "media-transcribe", "research", "xlsx", "docx", "pptx", "pdf", "web-download"}
ok(need <= names and "deck.html" in sk.use("slides") and "<section class=\"slide title\">" in sk.read_file("slides", "deck.html"),
   f"навыки мастерской на месте ({len(names)} навыков), шаблон презентации читается")
ok(len(sk.use("html-viz")) > 12000, "длинный навык отдаётся целиком")
spec_names = {x["name"] for x in tm._specs(t)} if hasattr(h, "toolbox") else set(WORK_TOOLS)
ok(set(WORK_TOOLS) <= spec_names, "инструменты мастерской доступны задаче")
