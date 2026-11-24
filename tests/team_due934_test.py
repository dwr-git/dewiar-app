"""№934 (20.11): поручение с телефона «Найди пару клиентов» сроком «В течении 30 дней» — компьютер ответил «не поняла
срок». Теперь сроки длительностью понятны: «в течение / за / через N дней, недель, месяцев» — к 18:00 последнего дня."""
import os, sys
from datetime import datetime
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
from team import due_parse  # noqa: E402

bad = 0


def ok(c, m):
    global bad
    bad += 0 if c else 1
    print(("✅ " if c else "❌ ") + m)


now = datetime(2026, 11, 20, 20, 47)
cases = {"В течении 30 дней": datetime(2026, 12, 20, 18, 0), "в течение недели": datetime(2026, 11, 27, 18, 0),
         "за 3 дня": datetime(2026, 11, 23, 18, 0), "через месяц": datetime(2026, 12, 20, 18, 0),
         "в течение двух недель": datetime(2026, 12, 4, 18, 0), "через 2 месяца": datetime(2027, 1, 20, 18, 0),
         "в течение дня": datetime(2026, 11, 20, 23, 59), "в течение часа": datetime(2026, 11, 20, 21, 47),
         "до пятницы": datetime(2026, 11, 27, 18, 0), "завтра к 12": datetime(2026, 11, 21, 12, 0)}
for p, want in cases.items():
    got = due_parse(p, now)[0]
    ok(got == want, f"«{p}» → {got}")
ok(due_parse("через 1 месяц", datetime(2027, 1, 31, 10, 0))[0] == datetime(2027, 2, 28, 18, 0), "31 января + месяц — 28 февраля")
print("ИТОГ:", "всё в порядке" if not bad else f"ошибок {bad}")
sys.exit(1 if bad else 0)
