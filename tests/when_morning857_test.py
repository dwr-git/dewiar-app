"""Отчёт №857 (18.11, 05:07): «не может поставить время на 5:30 утра или 6:30 — ставит вечернее». Дело «каждый день в 5:30
присылай прогноз погоды» трижды ложилось на 17:30: час без «утра/вечера» для повторов 1–6 считается днём, а модель не
знала, что время угадано, и переставляла на то же. Теперь угадывание видно: ответ инструмента говорит, что поставлено
(17:30) и как переставить на утро, если по разговору это утро; «в 5:30 утра» — 05:30, как было. Сценарий экзамена
job_morning_530_857. Настоящие core/when.py и core/tools_remind.py."""
import os, sys, tempfile, types
from datetime import datetime
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ.update(DEWIAR_CONFIG_DIR=str(tmp / "cfg"), DEWIAR_STATE_DIR=str(tmp / "st"))
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import when as W  # noqa: E402
import tools_remind as TR  # noqa: E402

now = datetime(2026, 11, 18, 9, 1)
r = W.parse("напоминай каждый день в 5:30 собрать прогноз погоды", now)
ok(r["repeat"]["time"] == "17:30" and r["guessed"] == ("05:30", "17:30"), f"«каждый день в 5:30» без части суток — по-прежнему днём, но угадано: {r['repeat']} {r.get('guessed')}")
n = W.guess_note(r)
ok("17:30" in n and "5:30 утра" in n and "переставь" in n, f"подсказка модели — что поставлено и как переставить: {n}")
r = W.parse("напоминай каждый день в 5:30 утра собрать прогноз погоды", now)
ok(r["repeat"]["time"] == "05:30" and not r.get("guessed") and W.guess_note(r) == "", "«в 5:30 утра» — 05:30, угадывать нечего")
ok(not W.parse("напомни каждый день в 8 зарядка", now).get("guessed"), "«в 8» — утро и без подсказки")
r = W.parse("напомни в 3 позвонить", now)
ok(r["at"].hour == 15 and r.get("guessed"), "разовое «в 3» в 9 утра — 15:00, и это тоже видно")


class Rs:
    def __init__(self):
        self.items = []

    def add(self, at, text, rep, kind, extra=None):
        x = {"id": f"r{len(self.items)}", "text": text, "at": at.isoformat(), "repeat": rep, "kind": kind}
        self.items.append(x)
        return x

    def find(self, q):
        return [i for i in self.items if i["id"] == q or q.lower() in i["text"].lower()]

    def update(self, rid, patch):
        x = next(i for i in self.items if i["id"] == rid)
        x.update(patch)
        return x


rs = Rs()
ctx = {"reminders": rs}
out = TR.t_schedule_job({"task": "Собрать прогноз погоды для Красноярска и прислать в Telegram", "when": "каждый день в 5:30", "deliver": "telegram"}, ctx)
ok("17:30" in out and "5:30 утра" in out, f"schedule_job: в ответе — поставлено на 17:30 и как переставить на утро: {out[-170:]}")
out = TR.t_change_reminder({"id": rs.items[0]["id"], "when": "каждый день в 5:30 утра"}, ctx)
ok(rs.items[0]["repeat"]["time"] == "05:30" and "переставь" not in out, f"переставили «в 5:30 утра» — 05:30, без подсказки: {out}")
out = TR.t_reminder({"text": "Пробежка", "when": "каждый день в 6:30"}, ctx)
ok("18:30" in out and "6:30 утра" in out, f"set_reminder «каждый день в 6:30» — та же подсказка: {out[-150:]}")
import json  # noqa: E402
sc = [s for s in json.loads((ROOT / "data/exam/scenarios.json").read_text(encoding="utf-8"))["scenarios"] if s["id"] == "job_morning_530_857"]
ok(sc and sc[0]["state"]["reminder"]["hm"] == "05:30", "сценарий экзамена: утренняя сводка — именно 05:30")
print("\nИТОГ: " + ("всё прошло" if not fails else f"не прошло {len(fails)}"))
sys.exit(1 if fails else 0)
