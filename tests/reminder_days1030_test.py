"""Напоминания по дням недели (30.10, владелец: «ставил на будни „Пора выключать компьютер“, просил кроме пятницы — Лира
поставила и на пятницу; в пятницу сокращённый день, выключить в 16:40; вручную не понятно как; попросил Лиру — сказала
„сейчас внесу“, но ничего не изменилось. Это то, с чем я имею дело каждый день»).
1. when: «по будням, кроме пятницы», «с понедельника по четверг», «пн-чт», «каждый день кроме выходных».
2. set_reminder: «кроме пятницы» не перебивается «по будням» (_fix_days возвращал пятницу).
3. change_reminder — инструмент правки (его не было — модель обещала и не делала).
4. Календарь: дни повтора кнопками (reminder_update days) и «новое время — только по пятницам» (reminder_split)."""
import os, sys, tempfile, types
from datetime import datetime
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ.update(DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_CONFIG_DIR=str(tmp / "cfg"), DEWIAR_HOME=str(tmp / "home"))
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import when as W  # noqa: E402
import tools as TL  # noqa: E402
import engine_tools as ET  # noqa: E402

now = datetime(2026, 10, 30, 11, 0)
cases = {"напомни по будням кроме пятницы в 17:50 пора выключать компьютер": [0, 1, 2, 3],
         "напомни по будням в 17:50, кроме пятницы, пора выключать компьютер": [0, 1, 2, 3],
         "напомни с понедельника по четверг в 17:50 выключить компьютер": [0, 1, 2, 3],
         "напомни пн-чт в 17:50 выключить компьютер": [0, 1, 2, 3],
         "напомни каждый день кроме субботы и воскресенья в 8 зарядка": [0, 1, 2, 3, 4],
         "напомни по будням но не в среду в 9 планёрка": [0, 1, 3, 4]}
texts = {"напомни по будням но не в среду в 9 планёрка": "Планёрка"}
for t, days in cases.items():
    r = W.parse(t, now)
    ok(r and r["repeat"]["kind"] == "weekly" and r["repeat"]["days"] == days and "кроме" not in r["text"].lower() and r["at"].weekday() in days,
       f"«{t[8:]}» → {r and (r['repeat'], r['text'])}")
    if t in texts:
        ok(r["text"] == texts[t], f"текст — без «кроме…»: {r['text']}")
r = W.parse("напомни по пятницам в 16:40 пора выключать компьютер", now)
ok(r["repeat"]["days"] == [4] and r["at"] == datetime(2026, 10, 30, 16, 40), "«по пятницам в 16:40» — сегодня, пятница")

R = TL.Reminders(lambda it: None)
ctx = {"reminders": R}
out = TL.TOOLS["set_reminder"][3]({"text": "Пора выключать компьютер", "when": "по будням, кроме пятницы, в 17:50"}, ctx)
x = R.items[-1]
ok(x["repeat"]["days"] == [0, 1, 2, 3], f"set_reminder: «по будням, кроме пятницы» — пн–чт, пятница не возвращается: {x['repeat']} · {out[:80]}")
out = TL.TOOLS["change_reminder"][3]({"text": "выключать компьютер", "when": "с понедельника по пятницу в 18"}, ctx)
ok(R.items[-1]["repeat"]["days"] == [0, 1, 2, 3, 4] and R.items[-1]["repeat"]["time"] == "18:00" and out.startswith("Изменено"),
   f"change_reminder — правит по тексту: {out[:90]}")
ok("change_reminder" in TL.SAFE_CORE and "по будням, кроме пятницы" in TL.TOOLS["set_reminder"][0], "инструмент правки — в «только безопасном», пример исключения — в описании")
import engine_answer as EA  # noqa: E402
ok("change_reminder" in EA.CORE_TOOLS, "и в главных действиях (маленькое окно модели)")


class Eng:
    _reminder_cmd, _reminder_public = ET.ToolsMixin._reminder_cmd, ET.ToolsMixin._reminder_public

    def __init__(self):
        self.reminders = TL.Reminders(lambda it: None)
        self.events = []
        self.s = types.SimpleNamespace(get=lambda *a, **k: None)

    def emit(self, ev, **kw): self.events.append((ev, kw))
    def _reminder_note(self, it): return ""


E = Eng()
E.reminders.items = []
it = E.reminders.add(datetime(2026, 11, 2, 17, 50), "Пора выключать компьютер", {"kind": "weekly", "days": [0, 1, 2, 3, 4], "time": "17:50"}, "reminder")
r = E._reminder_cmd("reminder_split", {"id": it["id"], "day": 4, "time": "16:40"})
items = {tuple(x["repeat"]["days"]): x for x in E.reminders.items}
ok(set(items) == {(0, 1, 2, 3), (4,)} and items[(4,)]["repeat"]["time"] == "16:40" and items[(0, 1, 2, 3)]["repeat"]["time"] == "17:50"
   and items[(4,)]["text"] == "Пора выключать компьютер", f"календарь: «только по пятницам — 16:40» — пятница отдельно, остальные как были: {[(k, v['repeat']['time']) for k, v in items.items()]}")
r = E._reminder_cmd("reminder_update", {"id": it["id"], "patch": {"days": [0, 1, 2]}})
ok(r["repeat"]["days"] == [0, 1, 2] and datetime.fromisoformat(r["at"]).weekday() in (0, 1, 2), f"календарь: дни повтора кнопками: {r['repeat_text']}")
try:
    E._reminder_cmd("reminder_update", {"id": it["id"], "patch": {"days": []}}); empty = False
except ValueError:
    empty = True
ok(empty, "без дней нельзя — «оставьте хотя бы один день»")
js = (ROOT / "ui/studio/day.js").read_text(encoding="utf-8")
ok('core.call("reminder_split"' in js and "remed-days" in js and "Новое время — только" in js, "студия: кнопки дней и «только по пятницам» в календаре")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
