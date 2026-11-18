"""Харнесс 1.0.30 (по образцу Aigen, владелец 18.11): замок на тесты. Задача по коду, которая ради «зелёного» итога
переписала или удалила тесты, что были в проекте до неё, итог сдать не может: прежние версии этих тестов прогоняются на
новом коде (codework.run_with_original_tests) и должны пройти. Цель сама просила поправить тесты — замка нет. Файлы
тестов после прогона — как их оставила задача. И git-проект, и папка без git."""
import os, shutil, subprocess, sys, tempfile, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
import codework as C  # noqa: E402
from tasks_verify import VerifyMixin  # noqa: E402
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


TEST = ("import unittest\nfrom calc import add\n\n\nclass T(unittest.TestCase):\n    def test_add(self):\n"
        "        self.assertEqual(add(2, 2), {want})\n")


def project(git):
    d = Path(tempfile.mkdtemp()) / "proj"
    (d / "tests").mkdir(parents=True)
    (d / "calc.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    (d / "tests" / "__init__.py").write_text("", encoding="utf-8")
    (d / "tests" / "test_calc.py").write_text(TEST.format(want=4), encoding="utf-8")
    if git:
        env = dict(os.environ, **C.GIT_ENV)
        for a in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "init"]):
            subprocess.run(["git", "-C", str(d)] + a, check=True, env=env, capture_output=True)
    return d


class Host:
    def code_auto_run(self):
        return True


class T:
    def __init__(self, code, goal="Поправь функцию add"):
        self.title, self.goal, self.data, self.log, self._code = "Калькулятор", goal, {}, [], code

    def journal(self, x):
        self.log.append(x)

    def code(self):
        return self._code


class M(VerifyMixin):
    host = Host()


ok(C.is_test_path("tests/test_calc.py") and C.is_test_path("src/a.spec.ts") and not C.is_test_path("calc.py")
   and not C.is_test_path("contest.py"), "файлы тестов узнаются по пути")

for git in (True, False):
    kind = "git" if git else "без git"
    pr = project(git)
    cw = C.CodeWork(pr, pr.parent / "задача" / "рабочая копия")
    cw.prepare()
    # «починила» тест вместо кода: код сломан (a - b), тест переписан под него
    cw.write("calc.py", "def add(a, b):\n    return a - b\n")
    cw.write("tests/test_calc.py", TEST.format(want=0))
    cmd = C.test_command(cw.work)
    ok(cmd and cw.run(cmd, 120).startswith("Код завершения 0"), f"{kind}: с переписанным тестом всё «зелёное»")
    ok(cw.touched_tests() == [("modified", "tests/test_calc.py")], f"{kind}: изменённый прежний тест найден: {cw.touched_tests()}")
    t, q = T(cw), {"verify_fail": 0}
    r = M()._tests_lock(t, cw, q)
    ok(r and "ПРЕЖНИЕ версии" in r and "tests/test_calc.py" in r and q["verify_fail"] == 1,
       f"{kind}: итог не принят — прежний тест на новом коде не проходит")
    ok("want" not in (cw.work / "tests/test_calc.py").read_text() and "add(2, 2), 0)" in (cw.work / "tests/test_calc.py").read_text(),
       f"{kind}: после прогона тест — как его оставила задача")
    # исправила код — прежний тест проходит, хотя файл теста всё ещё изменён
    cw.write("calc.py", "def add(a, b):\n    return a + b\n")
    cw.write("tests/test_calc.py", TEST.format(want=4) + "\n    def test_more(self):\n        self.assertEqual(add(1, 1), 2)\n")
    t2 = T(cw)
    r2 = M()._tests_lock(t2, cw, {"verify_fail": 0})
    ok(r2 is None and t2.data.get("lock_gate") == 9, f"{kind}: код исправлен — прежние тесты проходят, итог принят")
    # удалила тест — прежний возвращается на время прогона
    cw.write("calc.py", "def add(a, b):\n    return 0\n")
    cw.delete("tests/test_calc.py")
    t3 = T(cw)
    r3 = M()._tests_lock(t3, cw, {"verify_fail": 0})
    ok(r3 and not (cw.work / "tests/test_calc.py").exists(), f"{kind}: удалённый прежний тест прогнан и снова убран")
    # цель просила поправить тест — замка нет
    t4 = T(cw, goal="Тест test_add устарел — исправь тест под новое поведение")
    ok(M()._tests_lock(t4, cw, {"verify_fail": 0}) is None, f"{kind}: цель просила поправить тест — замка нет")
    shutil.rmtree(pr.parent, ignore_errors=True)

src = (ROOT / "core/tasks_verify.py").read_text(encoding="utf-8")
ok("lock = self._tests_lock(t, code, q)" in src and "lock_fail" in src, "замок стоит в проверке перед итогом, проверяющий видит пометку")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
