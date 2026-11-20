"""Выбор проверок по функциям (17.11, владелец: «код модульный и хорошо описан — это позволит значительно сократить
количество обязательных проверок»). Настоящий tools/test_impact.py в маленьком git-репозитории: две проверки выполняют
разные функции одного модуля — правка внутри одной функции зовёт только «свою» проверку; константа — проверки функций,
где она встречается, и проверку, что называет её сама; комментарий — никого; код уровня модуля — по-старому, весь файл;
исходник, прочитанный как текст, — всегда; переводы только пополнились — проверки переводов. И запись прогона пишет
выполненные функции (tests/trace/sitecustomize.py)."""
import gzip, json, os, shutil, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


tmp = Path(tempfile.mkdtemp())
R = tmp / "repo"
(R / "tools").mkdir(parents=True)
(R / "tests").mkdir()
(R / "core").mkdir()
(R / "ui" / "assets").mkdir(parents=True)
shutil.copy(ROOT / "tools/test_impact.py", R / "tools/test_impact.py")
git = lambda *a: subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *a], cwd=R, capture_output=True, text=True, check=True)
git("init", "-q")
(R / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
MOD = '''"""Модуль для проверки."""
import re

LIMIT = 10
WORDS = re.compile(r"привет")
DERIVED = LIMIT * 2


def alpha(x):
    # первая
    return x + 1


def beta(x):
    return x * LIMIT


class Box:
    SIZE = 3

    def put(self, x):
        return x

    def take(self):
        return DERIVED


print("уровень модуля")
'''
(R / "core/mod.py").write_text(MOD, encoding="utf-8")
(R / "ui/studio").mkdir(parents=True)
(R / "data").mkdir()
(R / "ui/studio/sites.js").write_text("function stLook() {}\n", encoding="utf-8")
(R / "ui/studio/notes.js").write_text("function ntShow() {}\n", encoding="utf-8")
(R / "ui/settings.html").write_text("<script src=studio/sites.js></script>\n", encoding="utf-8")
(R / "data/whatsnew.json").write_text('[{"pc": "1.0.1"}]\n', encoding="utf-8")
(R / "ui/assets/i18n.tx.js").write_text('/* сборка */\nwindow.DW_TX = {"en":{"Да":"Yes"}};\n', encoding="utf-8")
tests = {"a_test.py": "import mod\nmod.alpha(1)\n", "b_test.py": "import mod\nmod.beta(1)\n", "c_test.py": "import mod\nmod.Box().take()\n",
         "src_test.py": "print(open('core/mod.py').read()[:5])\n", "const_test.py": "import mod\nassert mod.LIMIT == 10\n",
         "i18n_test.py": "print('переводы')\n", "other_test.py": "print('другое')\n",
         "studio_smoke_test.py": "# открывает settings.html целиком\n", "sites_page_test.py": "# settings.html: раздел sites\n",
         "notes_page_test.py": "# settings.html: раздел заметок\n", "news_test.py": "# data/whatsnew.json — «Что нового»\n"}
for n, body in tests.items():
    (R / "tests" / n).write_text(body, encoding="utf-8")
(R / "tests/run_quick.sh").write_text("".join(f'run "{n}" $PY "$T/{n}"\n' for n in tests), encoding="utf-8")
git("add", "-A")
git("commit", "-qm", "base")
git("tag", "v1")

# запись прогона: каждая проверка — с настоящим sitecustomize записи
tr = tmp / "trace"
tr.mkdir()
for n in tests:
    env = dict(os.environ, DEWIAR_TRACE_FILE=str(tr / (n + ".txt")), DEWIAR_TRACE_ROOT=str(R),
               PYTHONPATH=str(ROOT / "tests/trace") + os.pathsep + str(R / "core"))
    subprocess.run([sys.executable, str(R / "tests" / n)], cwd=R, env=env, capture_output=True, text=True, timeout=60)
ta = (tr / "a_test.py.txt").read_text(encoding="utf-8")
ok("fn:core/mod.py::alpha" in ta and "fn:core/mod.py::beta" not in ta, f"запись: a выполнила alpha и не beta: {ta.split()}")
ok("src:core/mod.py" in (tr / "src_test.py.txt").read_text(encoding="utf-8") and "src:" not in ta,
   "исходник, прочитанный как текст, — «src:»; импорт — нет")
ok("fn:core/mod.py::Box.take" in (tr / "c_test.py.txt").read_text(encoding="utf-8"), "методы — «Класс.метод»")
r = subprocess.run([sys.executable, "tools/test_impact.py", "build", str(tr)], cwd=R, capture_output=True, text=True)
ok((R / "tests/impact.fn.json.gz").is_file() and "карта функций" in r.stdout, f"карта функций собрана: {r.stdout.strip()[-120:]}")
fmap = json.loads(gzip.decompress((R / "tests/impact.fn.json.gz").read_bytes()))
ok(not any(k.startswith("tests/") for k in fmap["keys"]), "функции самих проверок в карту не идут")
git("add", "-A")
git("commit", "-qm", "map")


def pick():
    r = subprocess.run([sys.executable, "tools/test_impact.py", "pick", "v1"], cwd=R, capture_output=True, text=True)
    return [x for x in r.stdout.split() if x.endswith(".py")], r.stderr, r.stdout


def case(name, new_src, want, not_want=(), extra=None):
    (R / "core/mod.py").write_text(new_src, encoding="utf-8")
    if extra:
        extra()
    got, err, out = pick()
    ok(set(want) <= set(got) and not set(not_want) & set(got) and "ALL" not in out,
       f"{name}: {sorted(got)} | {err.strip().splitlines()[-2:] if err else ''}")
    git("checkout", "-q", "--", ".")


# карта сама — не изменение кода; tools/test_impact.py изменён в «map»? нет — только карта
case("правка внутри alpha", MOD.replace("return x + 1", "return x + 2"), ["a_test.py", "src_test.py"], ["b_test.py", "c_test.py", "const_test.py"])
case("правка метода Box.take", MOD.replace("        return DERIVED", "        return DERIVED + 0"), ["c_test.py"], ["a_test.py", "b_test.py"])
# 20.11: поправили только комментарий — код тот же: проверки функции не нужны, остаются те, что читают сам текст файла
case("только комментарий в функции — код тот же", MOD.replace("# первая", "# первая и главная"), ["src_test.py"], ["a_test.py", "b_test.py"])
case("константа LIMIT — beta (использует), take (через DERIVED) и проверка, что называет LIMIT",
     MOD.replace("LIMIT = 10", "LIMIT = 11"), ["b_test.py", "c_test.py", "const_test.py", "src_test.py"], ["a_test.py"])
case("код уровня модуля — весь файл, как раньше", MOD.replace('print("уровень модуля")', 'print("другое")'),
     ["a_test.py", "b_test.py", "c_test.py", "const_test.py"])
case("переводы только пополнились — проверки переводов",
     MOD, ["i18n_test.py"], ["a_test.py", "b_test.py", "other_test.py"],
     extra=lambda: (R / "ui/assets/i18n.tx.js").write_text('/* сборка */\nwindow.DW_TX = {"en":{"Да":"Yes","Нет":"No"}};\n', encoding="utf-8"))

def touch(path, text):
    return lambda: (R / path).write_text(text, encoding="utf-8")


case("страница студии sites.js — её проверки и студия целиком, а не все, кто открывает студию", MOD,
     ["sites_page_test.py", "studio_smoke_test.py"], ["notes_page_test.py", "a_test.py"],
     extra=touch("ui/studio/sites.js", "function stLook() { return 1; }\n"))
case("«Что нового»: сверху новая запись — проверки «Что нового»", MOD, ["news_test.py"], ["studio_smoke_test.py", "a_test.py"],
     extra=touch("data/whatsnew.json", '[{"pc": "1.0.2"}, {"pc": "1.0.1"}]\n'))
(R / "data/whatsnew.json").write_text('[{"pc": "1.0.2"}, {"pc": "1.0.0"}]\n', encoding="utf-8")
got, err, _ = pick()
ok("сверху новая запись" not in err, "старую запись «Что нового» поправили — правило не срабатывает")
git("checkout", "-q", "--", ".")

# изменённый перевод (не только добавление) — так не считается
(R / "ui/assets/i18n.tx.js").write_text('/* сборка */\nwindow.DW_TX = {"en":{"Да":"Yeah"}};\n', encoding="utf-8")
got, err, _ = pick()
ok("переводы только пополнились" not in err, "перевод изменили, а не добавили — правило не срабатывает")
git("checkout", "-q", "--", ".")

src = (ROOT / "tools/test_impact.py").read_text(encoding="utf-8")
ok("tests/trace/" in src and '"tools/test_impact.py"' in src, "изменение самой записи или выбора — по-прежнему весь набор")
print("\nИТОГ: " + ("всё прошло" if not fails else f"не прошло {len(fails)}"))
sys.exit(1 if fails else 0)
