"""Экзамен под новое (19.11, владелец: «на основании всех нововведений нужно ли обновить экзамены?»): напоминание со словами
в кавычках — сразу и дословно, без «Выполнить?»; «в следующий понедельник» — именно понедельник (№897, проверка дня недели
dow); «я руковожу компанией — чем поможет?» — полный цикл по руководству (урок 30). На компьютере и телефоне — одинаково."""
import json, os, re, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


IDS = ["remind_quoted_1119", "remind_next_monday_897", "company_whatfor_1119"]
pc = {s["id"]: s for s in json.loads((ROOT / "data/exam/scenarios.json").read_text(encoding="utf-8"))["scenarios"]}
ph = (ROOT / "android/assets/www/exam.js").read_text(encoding="utf-8")
for i in IDS:
    ok(i in pc and f'id: "{i}"' in ph, f"сценарий {i} — на компьютере и телефоне")
ok(pc["remind_next_monday_897"]["state"]["reminder"].get("dow") == 0 and 'dow: 0' in ph, "«следующий понедельник» проверяется днём недели")
ok(pc["remind_quoted_1119"]["state"]["reminder"]["hm"] == "10:00" and "Выполнить действие" in pc["remind_quoted_1119"]["expect"]["none"],
   "кавычки: 10:00 и без «Выполнить действие»")
src = (ROOT / "core/exam.py").read_text(encoding="utf-8")
ok('"dow" in want and at.weekday() != int(want["dow"])' in src, "компьютер: проверка дня недели в состоянии напоминания")
ok(re.search(r"w\.dow != null && \(new Date\(x\.at\)\.getDay\(\) \+ 6\) % 7 !== w\.dow", ph) and "if (w.hm)" in ph, "телефон: проверки hm и dow")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
