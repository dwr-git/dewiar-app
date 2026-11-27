"""Выбор проверок по функциям JS (20.11, владелец: «выпуски стали очень долгими… телефон — по функциям, да, давай сделаем»).
1) запись прогона (tests/trace/sitecustomize.py) пишет, какие функции JS выполнились в браузере («jsfn:») и чьё покрытие
   снято («jscov:»), — и для копии файла во временной папке (телефон собирается www_assemble.sh), если она байт в байт та же;
2) tools/test_impact.py: правка внутри функции app.js — только проверки, что её выполняли (и что называют её, читая текст);
   константа — проверки функций, где она названа; код верхнего уровня или проверка без покрытия файла — по-старому."""
import os, shutil, subprocess, sys, tempfile, textwrap
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)

bad = 0
def ok(c, m):
    global bad
    bad += 0 if c else 1
    print(("✅ " if c else "❌ ") + m)

tmp = Path(tempfile.mkdtemp(prefix="dw-impjs-"))
R = tmp / "repo"
(R / "tools").mkdir(parents=True); (R / "tests/trace").mkdir(parents=True); (R / "android/assets/www").mkdir(parents=True)
shutil.copy(ROOT / "tools/test_impact.py", R / "tools/test_impact.py")
shutil.copy(ROOT / "tests/trace/sitecustomize.py", R / "tests/trace/sitecustomize.py")
APP = textwrap.dedent("""\
    "use strict";
    const LIMIT = 3;
    /* заметки
    function notAFunction() — внутри комментария */
    function notesRender(list) {
      return list.slice(0, LIMIT).map(x => "<li>" + x + "</li>").join("");
    }
    const greet = (name) => "Привет, " + name;
    function calcTotal(a, b) {
      return a + b;
    }
    function unused() { return 0; }
    document.body.dataset.ready = "1";
    """)
(R / "android/assets/www/app.js").write_text(APP, encoding="utf-8")
(R / "android/assets/www/index.html").write_text('<!doctype html><meta charset="utf-8"><body><script src="app.js"></script>', encoding="utf-8")
tests = {"notes_ui_test.py": "notesRender", "calc_ui_test.py": "calcTotal", "greet_ui_test.py": "greet"}
for t, fn in tests.items():
    (R / "tests" / t).write_text(f"# открывает телефон и вызывает {fn}\n", encoding="utf-8")
(R / "tests/text_src_test.py").write_text("src = open('android/assets/www/app.js').read()\nassert 'notesRender' in src\n", encoding="utf-8")
(R / "tests/run_quick.sh").write_text("\n".join(f'run "{t}" $PY "$T/{t}"' for t in [*tests, "text_src_test.py"]) + "\n", encoding="utf-8")
g = lambda *a: subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *a], cwd=R, capture_output=True, text=True)
g("init", "-q"); g("add", "-A"); g("commit", "-qm", "v0"); g("tag", "v0")

# ---------- запись: реальный Chromium через Playwright под sitecustomize ----------
tr = tmp / "trace"; tr.mkdir()
www = tmp / "copy" / "www"; shutil.copytree(R / "android/assets/www", www)        # как www_assemble.sh: копия во временной папке
for t, fn in tests.items():
    code = textwrap.dedent(f"""
        from pathlib import Path
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.launch(); pg = b.new_page()
            pg.goto(Path({str(www / 'index.html')!r}).as_uri()); pg.wait_for_timeout(150)
            pg.evaluate("{fn}" + ({fn!r} == "notesRender" and "(['a'])" or {fn!r} == "greet" and "('Мир')" or "(1, 2)"))
    """)
    env = dict(os.environ, DEWIAR_TRACE_FILE=str(tr / (t + ".txt")), DEWIAR_TRACE_ROOT=str(R),
               PYTHONPATH=str(R / "tests/trace"))           # своя запись — не та, что у прогона (если он с записью)
    env.pop("NODE_V8_COVERAGE", None)
    r = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=120)
    if r.returncode:
        print(r.stderr[-800:])
# две копии записи в PYTHONPATH (проверка записи внутри прогона с записью) — не зовут друг друга без конца (прогон 1.0.50)
env2 = dict(os.environ, DEWIAR_TRACE_FILE=str(tmp / "two.txt"), DEWIAR_TRACE_ROOT=str(R),
            PYTHONPATH=os.pathsep.join([str(R / "tests/trace"), str(ROOT / "tests/trace")]))
try:
    r2 = subprocess.run([sys.executable, "-c", "print('ok')"], env=env2, capture_output=True, text=True, timeout=30)
    ok(r2.stdout.strip() == "ok", "две копии записи в одном процессе — запускается сразу")
except subprocess.TimeoutExpired:
    ok(False, "две копии записи в одном процессе — зависло")
rec = {t: set((tr / (t + ".txt")).read_text(encoding="utf-8").split()) if (tr / (t + ".txt")).is_file() else set() for t in tests}
n = rec["notes_ui_test.py"]
ok("jscov:android/assets/www/app.js" in n, "покрытие копии app.js из временной папки — записано на файл проекта")
ok("jsfn:android/assets/www/app.js::notesRender" in n and "jsfn:android/assets/www/app.js::calcTotal" not in n
   and "jsfn:android/assets/www/app.js::unused" not in n, "записаны только выполненные функции")
ok("jsfn:android/assets/www/app.js::greet" in rec["greet_ui_test.py"], "const greet = () => … — тоже функция с именем")
(tr / "text_src_test.py.txt").write_text("android/assets/www/app.js\n", encoding="utf-8")              # читает текстом

r = subprocess.run([sys.executable, str(R / "tools/test_impact.py"), "build", str(tr)], cwd=R, capture_output=True, text=True)
ok(r.returncode == 0 and (R / "tests/impact.fn.json.gz").is_file(), "карта с функциями JS собрана")
g("add", "-A"); g("commit", "-qm", "map"); g("tag", "-f", "v0")


def pick(edit):
    (R / "android/assets/www/app.js").write_text(edit(APP), encoding="utf-8")
    r = subprocess.run([sys.executable, str(R / "tools/test_impact.py"), "pick", "v0"], cwd=R, capture_output=True, text=True)
    (R / "android/assets/www/app.js").write_text(APP, encoding="utf-8")
    return set(r.stdout.split()), r.stderr


got, why = pick(lambda s: s.replace("return a + b;", "return a + b + 0;"))
ok(got == {"calc_ui_test.py"}, f"правка calcTotal — только её проверка: {sorted(got)}")
got, why = pick(lambda s: s.replace('.join("")', '.join(" ")'))
ok(got == {"notes_ui_test.py", "text_src_test.py"}, f"правка notesRender — её проверка и читающая текст с этим именем: {sorted(got)}")
got, why = pick(lambda s: s.replace("const LIMIT = 3;", "const LIMIT = 4;"))
ok("notes_ui_test.py" in got and "calc_ui_test.py" not in got, f"константа LIMIT — проверки функций, где она названа: {sorted(got)}")
got, why = pick(lambda s: s.replace('"Привет, "', '"Здравствуй, "'))
ok(got == {"greet_ui_test.py"}, f"стрелочная функция greet: {sorted(got)}")
got, why = pick(lambda s: s.replace('dataset.ready = "1"', 'dataset.ready = "2"'))
ok(got >= set(tests), f"код верхнего уровня — все, кто грузит файл: {sorted(got)}")
got, why = pick(lambda s: s.replace("/* заметки", "/* заметки телефона"))
ok(not got & set(tests), f"только комментарий — проверки функций не нужны: {sorted(got)}")
shutil.rmtree(tmp, ignore_errors=True)

print("ИТОГ:", "всё в порядке" if not bad else f"ошибок {bad}")
sys.exit(1 if bad else 0)
