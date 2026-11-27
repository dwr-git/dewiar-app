"""№1010 (24.11, Windows): «радар не делает обходы по источникам, последний раз 8 дней назад, в очереди 102». Режим Радара
«только ночью» (1:00–7:00), а компьютер ночью выключен — обхода не было вовсе. Теперь: ночного обхода не было больше суток —
один обход днём; был недавно — днём ждём ночи, как раньше; «пауза» — не трогаем."""
import os, sys, tempfile, time
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ["DEWIAR_STATE_DIR"] = str(tmp / "st"); os.environ["DEWIAR_CONFIG_DIR"] = str(tmp / "cfg")
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    c or fails.append(m)


import engine_insight as EI  # noqa: E402


class Stop:
    def __init__(self, n):
        self.n = n

    def wait(self, t):
        self.n -= 1
        return self.n < 0

    def is_set(self):
        return self.n < 0


class St:
    def __init__(self, last):
        self.last = last

    def sources(self):
        return [{"url": "https://example.com"}]

    def load(self, k, d=None):
        return {"last_tick": self.last} if k == "log" else (d or {})


def run(mode, last_ago, night):
    r = EI.Radar.__new__(EI.Radar)
    r.st = St(time.time() - last_ago)
    r.conf = lambda: dict(EI.DEFAULTS, mode=mode)
    r.night = lambda now=None: night
    ticks = []
    r.tick = lambda *a, **k: ticks.append(1)
    r.loop(Stop(1))  # одна проверка после стартовой паузы
    return len(ticks)


ok(run("night", 8 * 86400, False) == 1, "«только ночью», ночного обхода не было 8 дней — обход днём")
ok(run("night", 3 * 3600, False) == 0, "«только ночью», ночью обходил — днём ждём ночи, как раньше")
ok(run("night", 3600, True) == 1, "ночью — обход по расписанию")
ok(run("pause", 8 * 86400, False) == 0, "«пауза» — не трогаем")
ok(run("always", 3600, False) == 1, "«всегда» — как раньше")
print("ИТОГ: " + ("всё прошло" if not fails else f"провалов {len(fails)}"))
sys.exit(1 if fails else 0)
