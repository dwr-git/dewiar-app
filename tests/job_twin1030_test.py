"""«Итог дня» в 21:00 запустился два раза подряд (владелец 30.10: «первый раз рассказала, и второй раз сразу после»).
В списке оказалось два одинаковых дела по расписанию (добавлено дважды) — сработали оба, второе подождало, пока первое
договорит, и выполнилось в 21:01. Теперь: такое же дело второй раз не заводится (job_add отдаёт уже имеющееся), двойники
при запуске сливаются в одно, а если всё же сработали два одинаковых — второй в течение 10 минут пропускается."""
import os, sys, tempfile, threading, time, types
from datetime import datetime, timedelta
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import tools as T  # noqa: E402

tmp = Path(tempfile.mkdtemp())
R = T.Reminders.__new__(T.Reminders)                       # без потока часов: списки и срабатывание — руками
R.items, R._lock, R._save, R.on_change = [], threading.RLock(), (lambda: None), None
at = (datetime.now() + timedelta(hours=1)).replace(second=0, microsecond=0)
rep = {"kind": "daily"}
a = R.add(at, "Подведи итог дня", rep, "job", {"deliver": "voice", "preset": "evening"})
time.sleep(1.1)
b = R.add(at, "Подведи итог дня", rep, "job", {"deliver": "voice", "preset": "evening"})
c = R.add(at + timedelta(hours=1), "Подведи итог дня", rep, "job", {"deliver": "voice", "preset": "evening"})
d = R.add(at, "Купить хлеб", None, "reminder")
ok(R.job_sig(a) == R.job_sig(b) and R.job_sig(a) != R.job_sig(c), "одинаковые дела узнаются; другое время — уже другое дело")
n = R.dedupe_jobs()
ids = {x["id"] for x in R.items}
ok(n == 1 and a["id"] in ids and b["id"] not in ids and c["id"] in ids and d["id"] in ids, f"при запуске двойник убран, остальное на месте: {n}")

# job_add: второе такое же — не заводится
from engine_tools import ToolsMixin  # noqa: E402

eng = types.SimpleNamespace(reminders=R, emit=lambda *a, **k: None, _bot_for=lambda d: None,
                            _reminder_public=lambda x: {"id": x["id"], "text": x["text"]})
import jobs  # noqa: E402

cnt = len(R.items)
args = {"phrase": "каждый день в 21:00 делай итог дня", "task": "Итог", "preset": "evening"}
r1 = ToolsMixin._reminder_cmd(eng, "job_add", dict(args))
r2 = ToolsMixin._reminder_cmd(eng, "job_add", dict(args))
ok(len(R.items) == cnt + 1 and r2.get("already") and r2["id"] == r1["id"], f"«Итог дня» добавили второй раз — второе не заводится: {r2}")

# срабатывание: два одинаковых подряд — второй пропускается
ran = []
eng2 = types.SimpleNamespace(reminders=R, JOB_LATE_MAX=7200, _log_reminder=lambda *a, **k: ran.append("log"), _run_job=lambda item: ran.append(item["id"]))
item1 = dict(a, at=at.isoformat(), late_s=0)
item2 = dict(b, at=at.isoformat(), late_s=0)
import threading as _th  # noqa: E402
orig = _th.Thread


class Now:
    def __init__(self, target=None, args=(), **k):
        self.t, self.a = target, args

    def start(self):
        self.t(*self.a)


_th.Thread = Now
try:
    ToolsMixin._on_reminder(eng2, item1)
    ToolsMixin._on_reminder(eng2, item2)
finally:
    _th.Thread = orig
ok(ran == ["log", a["id"]], f"сработали два одинаковых — выполнено одно, в календаре — одна запись: {ran}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
