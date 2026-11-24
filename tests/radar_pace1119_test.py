"""Владелец 19.11 (снимок «Пульта»): «статьи из Радара — в определённое время, и потом тишина… раз в сутки? Ночью нагрузка
меньше — Радар мог бы работать полнее». Суточный запас разборов (daily_max) уходил за первые часы работы компьютера.
Теперь он разложен по суткам: ночной час весит вдвое; ручной «Обновить» и первый обход новых источников — без раскладки."""
import os, sys
from datetime import datetime
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import engine_insight as E  # noqa: E402
R = E.Radar.__new__(E.Radar)
R.conf = lambda: dict(E.DEFAULTS, daily_max=60)
P = {h: R.paced(datetime(2026, 11, 20, h, 0)) for h in (0, 1, 7, 12, 18, 23)}
ok(P[0] < P[1] < P[7] < P[12] < P[18] < P[23] <= 60, f"запас растёт по часам, а не весь сразу: {P}")
ok(P[7] - P[1] >= 18 and P[18] <= 52, f"ночью (1–7) — около 40 % суток, к вечеру остаётся на вечер и ночь: {P}")
ok(R.paced(datetime(2026, 11, 20, 23, 59)) == 60, "к концу суток — весь запас")
used = {"n": 0}
R.used_today = lambda: used["n"]
R.night = lambda now=None: False
q = []


class St:
    def queue(self, n, long_ok=False):
        q.append(n); return []


R.st = St()
R.paced = lambda now=None: 10
used["n"] = 8
R.analyze(25)
ok(q[-1] == 2, f"к этому часу — не больше его доли: разрешено {q[-1]} из 25")
R.analyze(25, paced=False)
ok(q[-1] == 25, "ручное «Обновить» — без раскладки (до суточного запаса)")
src = (ROOT / "core/engine_insight.py").read_text(encoding="utf-8")
ok("paced=not manual" in src, "такт: раскладка — только для автоматического")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
