"""Харнесс 1.0.30 (по образцу Aigen, владелец 18.11): проверяющий изменений не может выдумать замечание. Замечание о
месте кода обязано дословно цитировать строку из того, что ему показали (diff, выдержки, итог, дочитанное); пункт с
цитатой, которой там нет, отбрасывается (quality_task.drop_false_quotes); все пункты выдуманы — решают машинные проверки
(«unclear»), а не возврат задачи на доработку. Пункты без цитат («нет функции …») и задачи без diff — как раньше."""
import json, os, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
import quality_task as QT  # noqa: E402
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


DIFF = "--- a/calc.py\n+++ b/calc.py\n@@ -1,2 +1,2 @@\n def add(a, b):\n-    return a + b\n+    return a - b\n"
p, dropped = QT.drop_false_quotes("1) В add: «return a - b» — должно быть a + b.\n2) В main: «print(sum(xs) / len(xs))» "
                                  "падает на пустом списке.\n3) Нет функции mul, которую просила цель.", "ЗАДАЧА\n" + DIFF)
ok("return a - b" in p and "mul" in p and "print(sum" not in p and len(dropped) == 1,
   f"выдуманная цитата — пункт отброшен, настоящая и пункт без цитаты остались: {p!r}")
p2, d2 = QT.drop_false_quotes("Слово «пользователь» в итоге лучше заменить.", DIFF)
ok(p2 and not d2, "кавычки вокруг обычных слов (не кода) — не цитата кода, пункт остаётся")
p3, _ = QT.drop_false_quotes("«return   a -  b» неверно", DIFF)
ok("return" in p3, "цитата сверяется без учёта пробелов")


def run(answer, diff=DIFF):
    return QT.verify_task(lambda s, m: answer, "Сложение", "Готово", ["calc.py"], diff=diff)


v, pr = run(json.dumps({"verdict": "revise", "problems": "В add: «return a * b» — умножение вместо сложения."}, ensure_ascii=False))
ok(v == "unclear" and not pr, f"единственное замечание с выдуманной цитатой — не возврат на доработку: {v} {pr!r}")
v, pr = run(json.dumps({"verdict": "revise", "problems": "В add: «return a - b» — вычитание вместо сложения."}, ensure_ascii=False))
ok(v == "revise" and "return a - b" in pr, f"настоящая цитата — revise как раньше: {v}")
v, pr = run(json.dumps({"verdict": "revise", "problems": "В отчёте «итого: 42 (см. таблицу)» не сходится с файлом."}, ensure_ascii=False), diff="")
ok(v == "revise" and "42" in pr, "задача без diff — фильтр цитат не включается")
ok("ДОСЛОВНОЙ цитатой" in QT.VERIFY, "проверяющему сказано цитировать строку из diff")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
