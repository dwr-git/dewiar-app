"""Качество долгих задач (механизмы из Aigen, своим слоем — core/quality.py): проверка файлов кодом перед итогом,
быстрая проверка после записи, подсказки по ошибкам скриптов, защита от зацикливания, напоминание при ложном отказе
(«нет доступа к интернету»), независимая самопроверка итога, следы задач и выученные уроки, уборка служебных файлов."""
import json, os, re, sys, tempfile, threading, time, zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ.update(DEWIAR_WORKSPACE=str(tmp / "ws"), DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_CONFIG_DIR=str(tmp / "cfg"),
                  DEWIAR_REFLECT_EVERY="0")
sys.path.insert(0, str(ROOT / "core"))
import quality as Q  # noqa: E402
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


def wait_for(cond, sec=30):
    end = time.time() + sec
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.1)
    return False


# ---------------- 1. проверка файлов ----------------
d = tmp / "files"; d.mkdir()
W = lambda name, data: ((d / name).write_bytes(data) if isinstance(data, bytes) else (d / name).write_text(data, encoding="utf-8")) and d / name
good = {"a.html": "<!doctype html><html><body><div>Привет</div><script>1</script></body></html>", "a.json": '{"x": 1}',
        "a.csv": "имя,возраст\nАня,30\nБорис,41\n", "a.py": "print('ok')\n", "a.md": "# Заголовок\nтекст",
        "a.png": b"\x89PNG\r\n\x1a\n" + b"0" * 100, "a.pdf": b"%PDF-1.4\n...\n%%EOF\n"}
for n, c in good.items():
    W(n, c)
with zipfile.ZipFile(d / "a.docx", "w") as z:
    z.writestr("word/document.xml", "<w/>")
bad = {"b.html": "<html><body><div>оборвано", "c.html": "&lt;html&gt;&lt;body&gt;&lt;div&gt;&lt;p&gt;текст", "d.html":
       "<html><body><script>let x = 1;</body></html>", "e.html": "<html><body><script>fetch('data.json')</script></body></html>",
       "b.json": '{"x": 1,}', "b.csv": "a,b,c\n1,2\n3\n4,5,6,7\n8\n9,1\n", "b.py": "def f(:\n  pass\n", "b.docx": "не архив",
       "b.pdf": b"%PDF-1.4\ncut", "b.png": b"GIF89a", "empty.txt": "", "b.md": b"\xff\xfe\xfa\xfb text"}
for n, c in bad.items():
    W(n, c)
gp = {n: Q.check_file(d / n, n) for n in list(good) + ["a.docx"]}
bp = {n: Q.check_file(d / n, n) for n in bad}
ok(not any(gp.values()), f"исправные файлы — без замечаний ({ {k: v for k, v in gp.items() if v} })")
ok(all(bp.values()), f"брак найден в каждом испорченном файле ({[k for k, v in bp.items() if not v]} пропущены)")
ok("ОБОРВАН" in bp["b.html"][0] and "ЭКРАНИРОВАНА" in bp["c.html"][0] and "<script>" in bp["d.html"][0] and "fetch" in bp["e.html"][0],
   "HTML: оборван, экранирован, незакрытый script, fetch локального файла")
ok("JSON" in bp["b.json"][0] and "колонок" in bp["b.csv"][0] and "строке 1" in bp["b.py"][0] and "ПУСТОЙ" in bp["empty.txt"][0],
   "JSON, CSV, синтаксис Python (со строкой), пустой файл")
ok(Q.check_file(d / "нет.html", "outputs/нет.html")[0].startswith("outputs/нет.html: файл обещан"), "обещанного файла нет")
ok(Q.quick_check(d / "b.py") and not Q.quick_check(d / "b.html"), "быстрая проверка: сломанный .py — сразу; HTML, который ещё дописывается, — не трогает")
ok("Модуля pandas нет" in Q.error_hint("ModuleNotFoundError: No module named 'pandas'") and "User-Agent" in Q.error_hint("HTTP 403 Forbidden")
   and "порциями" in Q.error_hint("Остановлено по времени (180 с)") and Q.error_hint("всё хорошо") == "", "подсказки по ошибкам скрипта")

# ---------------- 2. зацикливание, отказ, уроки ----------------
g = Q.LoopGuard()
seq = [g.observe("list_files", {}, "a.txt") for _ in range(7)]
ok(seq[2] == "warn" and seq[4] == "finish" and seq[6] == "stop", f"одно и то же с тем же результатом: {seq}")
g = Q.LoopGuard()
ok(all(g.observe("run_python", {"code": "step()"}, f"порция {i}") is None for i in range(8)), "повтор с новым результатом (порции) — не тупик")
ok(Q.looks_like_refusal("К сожалению, у меня нет доступа к интернету в реальном времени.") and not Q.looks_like_refusal("Курс доллара 3,2."),
   "ложный отказ узнаётся")
m = Q.merge_lessons(["При 403 от сайта добавляй заголовок User-Agent браузера"],
                    ["при 403 от сайта добавляй User-Agent браузера в заголовок", "Работай аккуратнее", "коротко",
                     "Перед чтением файла проверяй, что он существует (os.path.exists)"])
ok(m == ["При 403 от сайта добавляй заголовок User-Agent браузера", "Перед чтением файла проверяй, что он существует (os.path.exists)"],
   f"уроки: без повторов, банальностей и обрывков: {m}")

# ---------------- 3. задачи с моделью-заглушкой ----------------
from workspace import Workspace  # noqa: E402
import tools as T  # noqa: E402
import tasks as TK  # noqa: E402

SCRIPTS = {
    "Страница": [
        ("write_file", {"path": "outputs/app.py", "content": "def f(:\n  pass\n"}),
        ("write_file", {"path": "outputs/app.py", "content": "def f():\n    return 1\n"}),
        ("write_file", {"path": "outputs/app.html", "content": "<!doctype html><html><body><h1>Калькулятор</h1>"}),
        ("show", {"path": "outputs/app.html", "title": "Калькулятор"}),
        ("run_python", {"code": "import numpy_нет_такого"}),
        ("finish", {"summary": "Страница готова."}),
        ("write_file", {"path": "outputs/app.html", "content": "</body></html>", "append": True}),
        ("finish", {"summary": "Страница готова: outputs/app.html."}),
    ],
    "Погода": [
        ("text", "К сожалению, у меня нет доступа к интернету в реальном времени, поэтому погоду сказать не могу."),
        ("web_search", {"query": "погода Минск сегодня"}),
        ("finish", {"summary": "В Минске сегодня +12, облачно (по данным поиска)."}),
    ],
    "Цикл": [("list_files", {})] * 12,
    "Отчёт": [
        ("finish", {"summary": "Отчёт готов."}),
        ("write_file", {"path": "outputs/отчёт.md", "content": "# Отчёт\n\nПродажи выросли на 12%.\n"}),
        ("show", {"path": "outputs/отчёт.md", "title": "Отчёт"}),
        ("finish", {"summary": "Отчёт: outputs/отчёт.md."}),
    ],
    "После уроков": [("finish", {"summary": "Готово."})],
}
pos, reqs, crit, refl = {}, [], [], []
lock = threading.Lock()


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        sysm = body["messages"][0]["content"]
        tc, text = None, ""
        with lock:
            if sysm.startswith("Ты — строгий"):
                user = body["messages"][-1]["content"]
                crit.append(user)
                text = ('{"verdict": "revise", "problems": "Обещан отчёт, а файла с отчётом нет — создай outputs/отчёт.md и покажи его."}'
                        if "Отчёт готов." in user else '{"verdict": "ok"}')
            elif sysm.startswith("Ты — аналитик"):
                refl.append(body["messages"][-1]["content"])
                text = '{"lessons": ["Перед запуском импортируй нужный модуль в отдельной проверке и обходись без него, если его нет", "Работай лучше"]}'
            else:
                title = re.search(r"ЗАДАЧА: (.+)", sysm).group(1).strip()
                i = pos.get(title, 0); pos[title] = i + 1
                sc = SCRIPTS.get(title, [])
                name, args = sc[i] if i < len(sc) else ("finish", {"summary": "Готово."})
                reqs.append({"title": title, "i": i, "system": sysm, "messages": body["messages"][1:]})
                if name == "text":
                    text = args
                else:
                    text = f"Шаг {i + 1}. "
                    tc = {"index": 0, "id": f"c{len(reqs)}", "type": "function", "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)}}
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
        for c in [{"choices": [{"delta": {"content": text}}]}] + ([{"choices": [{"delta": {"tool_calls": [tc]}}]}] if tc else []):
            self.wfile.write(f"data: {json.dumps(c, ensure_ascii=False)}\n\n".encode())
        self.wfile.write(b"data: [DONE]\n\n")


srv = ThreadingHTTPServer(("127.0.0.1", 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()


class FakeS:
    def get(self, *k): return {} if k[0] == "tools" else None


class Host:
    def __init__(self):
        self.workspace = Workspace(None); self.toolbox = T.Toolbox(FakeS(), None); self.toolbox.hooks["workspace"] = self.workspace
        self.said, self.pushes = [], []
        run0 = self.toolbox.run
        self.toolbox.run = lambda name, args: ("1. Погода в Минске: +12, облачно — pogoda.by" if name == "web_search" else run0(name, args))
    def persona_name(self): return "Лира"
    def memory(self): return ""
    def llm_profile(self): return {"name": "mock", "kind": "openai", "base_url": f"http://127.0.0.1:{srv.server_port}/v1", "model": "m"}
    def max_steps(self): return 30
    def code_auto_run(self): return True
    def confirm(self, q): return True
    def ask_user(self, t, q): pass
    def announce(self, text): self.said.append(text)
    def push(self, title, text="", critical=False, file=None): self.pushes.append((title, text))
    def emit(self, *a, **k): pass


host = Host()
tm = TK.TaskManager(host)
J = lambda t: (t.dir / "журнал.md").read_text(encoding="utf-8")
user_after = lambda title, i: next((m["content"] for m in reversed([r for r in reqs if r["title"] == title and r["i"] == i][0]["messages"])
                                    if m["role"] in ("user", "tool") and not str(m["content"]).startswith("[Состояние задачи")), "")   # 0.83: состояние — последним

t = tm.create("Страница", "Сделай страницу-калькулятор")
ok(wait_for(lambda: t.status in ("done", "failed")), f"задача «Страница» закончилась ({t.status})")
ok("ПРОВЕРКА" in user_after("Страница", 1) and "строке 1" in user_after("Страница", 1), "сломанный .py — замечание сразу после записи")
ok("Подсказка: Модуля numpy_нет_такого нет" in user_after("Страница", 5), "ошибка скрипта — с подсказкой, что делать")
ok("МАШИННАЯ ПРОВЕРКА ФАЙЛОВ НАШЛА БРАК" in user_after("Страница", 6) and "ОБОРВАН" in user_after("Страница", 6),
   "итог с оборванной страницей не принят: машинная проверка нашла брак")
ok(t.status == "done" and "</html>" in (t.dir / "outputs/app.html").read_text(encoding="utf-8") and "Машинная проверка" in J(t),
   "страницу дописали — итог принят, в журнале видно проверку")
ok(not (t.dir / "_run").exists() and (t.dir / "outputs/app.html").exists(), "готово — служебные скрипты шагов убраны, результаты на месте")
ok(crit and "outputs/app.html" in crit[-1] and "ФАКТЫ ОТ СИСТЕМЫ" in crit[-1], "самопроверка видит готовые файлы и факты системы")

t = tm.create("Погода", "Какая сегодня погода в Минске?")
ok(wait_for(lambda: t.status in ("done", "failed")) and t.status == "done", f"«Погода» готова ({t.status})")
ok("СТОП. Ты отказался" in user_after("Погода", 1) and "+12" in t.result, f"ложный отказ «нет доступа» — напомнил про поиск, ответ по найденному: {t.result}")

t = tm.create("Цикл", "Посмотри файлы")
ok(wait_for(lambda: t.status in ("done", "failed")), f"«Цикл» остановилась ({t.status})")
ok(t.status == "failed" and "застрял" in t.data.get("error", ""), f"повторяет одно и то же — остановлено с честной причиной: {t.data.get('error', '')[:60]}")
ok("СТОП: ты уже несколько раз" in user_after("Цикл", 3) and "Пора завершать" in user_after("Цикл", 5), "сначала «смени подход», потом «пора завершать»")

t = tm.create("Отчёт", "Сделай отчёт о продажах")
ok(wait_for(lambda: t.status in ("done", "failed")) and t.status == "done", f"«Отчёт» готов ({t.status})")
ok("САМОПРОВЕРКА отклонила" in user_after("Отчёт", 1) and (t.dir / "outputs/отчёт.md").exists() and "Самопроверка вернула" in J(t),
   "самопроверка вернула итог без файла — файл сделан, итог принят")

tr = Path(os.environ["DEWIAR_STATE_DIR"]) / "task_traces"
traces = [json.loads(f.read_text(encoding="utf-8")) for f in sorted(tr.glob("*.json"))]
ok(len(traces) == 4 and {x["reason"] for x in traces} == {"final", "loop_detected"}, f"следы задач сохранены ({[x['reason'] for x in traces]})")
ok(any(x["refusal"] for x in traces) and any(x["verify_fail"] for x in traces) and any(x["critic"] for x in traces)
   and any(x["errors"] for x in traces), "в следах — отказы, брак файлов, самопроверка, ошибки")
lp = tmp / "ws" / Q.LESSONS_FILE
ok(wait_for(lambda: lp.exists(), 15), "выводы из задач сделаны сами")
ls = Q.read_lessons(lp)
ok(ls == ["Перед запуском импортируй нужный модуль в отдельной проверке и обходись без него, если его нет"],
   f"в «Память/Уроки задач.md» — полезное правило, банальность отброшена: {ls}")
ok(refl and "ЛОЖНЫХ ОТКАЗОВ" in refl[0] and "Частые ошибки" in refl[0], "дайджест для выводов: отказы, частые ошибки")
t = tm.create("После уроков", "Просто закончи")
ok(wait_for(lambda: t.status == "done"), "следующая задача")
ok("ВЫУЧЕННЫЕ УРОКИ" in [r for r in reqs if r["title"] == "После уроков"][0]["system"] and ls[0] in [r for r in reqs if r["title"] == "После уроков"][0]["system"],
   "уроки — в подсказке следующей задачи")
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
