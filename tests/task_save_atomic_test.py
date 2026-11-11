"""задача.json пишется целиком или никак (10.11: tasks_test «задачи переживают перезапуск» падал раз из четырёх —
второй менеджер читал файл посреди записи поверх, видел обрывок и терял задачу). Пишем в одном потоке, читаем в другом:
читающий всегда видит целый JSON."""
import json, os, sys, tempfile, threading
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
import tasks  # noqa: E402

ok = lambda c, m: print(("✅ " if c else "❌ ") + m) or c
d = Path(tempfile.mkdtemp()) / "задача"
d.mkdir()
t = tasks.Task(d, {"id": "t1", "title": "проба", "status": "running", "big": "я" * 200_000})
t.save()
stop, bad, reads = threading.Event(), [], [0]


def writer():
    i = 0
    while not stop.is_set():
        t.data["n"] = i; i += 1
        t.save()


def reader():
    while not stop.is_set():
        try:
            json.loads((d / "задача.json").read_text(encoding="utf-8"))
            reads[0] += 1
        except ValueError as e:
            bad.append(str(e)[:60])


ws = [threading.Thread(target=writer) for _ in range(2)]
r = threading.Thread(target=reader)
for x in ws + [r]:
    x.start()
threading.Event().wait(2.0)
stop.set()
for x in ws + [r]:
    x.join()
fails = 0
fails += not ok(not bad and reads[0] > 20, f"читающий ни разу не увидел обрывок ({reads[0]} чтений, обрывков {len(bad)})")
fails += not ok(not (d / "задача.json.tmp").exists(), "временный файл не остаётся")
fails += not ok(json.loads((d / "задача.json").read_text(encoding="utf-8"))["id"] == "t1", "задача на месте")
print("ИТОГ:", "всё прошло" if not fails else f"{fails} ошибок")
sys.exit(1 if fails else 0)
