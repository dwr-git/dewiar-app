"""№655 (ПК 0.87.1, 11.11, storex): «Подкасты: время и дата создания подкаста не соответствуют действительности» — у
выпуска «1 января в 04:00». podcast.clean_meta пропускал числа только меньше 1e9, а сегодняшнее время Unix — 1,76e9:
created и done_at становились 0 (1970 год). Теперь время — своим пределом."""
import os, sys, tempfile, time
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
import podcast as P  # noqa: E402
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


now = int(time.time())
d = Path(tempfile.mkdtemp())
m = P.clean_meta({"id": "0123456789", "status": "done", "title": "Инфляция", "created": now - 300, "done_at": now, "duration": 318.4}, d)
ok(m["created"] == now - 300 and m["done_at"] == now, f"время создания и готовности — как есть: {m['created']}, {m.get('done_at')}")
ok(m["duration"] == 318.4, "длительность — как есть")
ok(P.clean_meta({"id": "0123456789", "created": "x"}, d)["created"] == 0, "мусор — 0, как раньше")
ok(P.clean_meta({"id": "0123456789", "created": 10 ** 12}, d)["created"] == 0, "время в миллисекундах — не принимается за секунды")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
