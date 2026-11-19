"""№881 (18.11): компьютер, включённый весь день, не обновлялся — каждый новый выпуск заново тянул случайные 0…6 ч.
Жребий за версию, которая так и не встала, переходит на следующую; после установки — новый жребий."""
import json, os, sys, tempfile, time
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ.update(DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_CONFIG_DIR=str(tmp / "cfg"))
sys.path.insert(0, str(ROOT / "core"))
import updater as UP  # noqa: E402

fails = 0
def ok(c, m):
    global fails
    print(("✅ " if c else "❌ ") + m)
    fails += not c

class S:
    def get(self, *a, **k): return k.get("default")

u = UP.Updater(S(), "1.0.30", tmp / "a")
t0 = time.time()
a1 = u._spread_at("1.0.31")
ok(t0 <= a1 <= time.time() + UP.SPREAD, "первый жребий — в ближайшие 6 ч")
a2 = u._spread_at("1.0.32")
ok(a2 == a1, "вышла 1.0.32, а 1.0.31 ещё не встала — время то же, не новые 0…6 ч")
f = tmp / "a" / "updates" / "spread.json"
ok(json.loads(f.read_text())["version"] == "1.0.32", "жребий записан за новой версией")
d = json.loads(f.read_text()); d["at"] = time.time() - 3600; f.write_text(json.dumps(d))
ok(u._spread_at("1.0.33") <= time.time(), "время уже прошло — новую версию качаем сразу")

u2 = UP.Updater(S(), "1.0.33", tmp / "a")                     # 1.0.33 встала
t4 = time.time()
a4 = u2._spread_at("1.0.34")
ok(a4 >= t4, "после установки — новый жребий, все разом не качают")
sys.exit(1 if fails else 0)
