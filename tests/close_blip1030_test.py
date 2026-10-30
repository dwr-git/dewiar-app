"""«Близкие»: один сорвавшийся опрос — не «нет связи» (30.10, владелец: «сейчас вообще пишет, что нет связи», хотя
сообщения ходили и галочки «прочитано» были). Сбой — через 3 с ещё раз; человеку — только второй подряд; успех — снимает."""
import os, sys, threading, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import close as CL  # noqa: E402

CL.time.sleep = lambda s: None
c = CL.Close.__new__(CL.Close)
c.host = types.SimpleNamespace(credentials=lambda: ("tok", "", "https://x"))
c.st = {"hello_at": 9e12, "people": [{"pid": "p1"}]}
c.error = ""
c.calls = {}
seq, seen, waits = ["fail", "ok", "fail", "fail", "ok"], [], []
stop = threading.Event()


def poll():
    r = seq.pop(0) if seq else "stop"
    if r == "stop":
        stop.set(); return
    if r == "fail":
        raise CL.CloseError("нет связи с Dewiar — проверьте интернет")


class Soon:
    def wait(self, t):
        waits.append(t); seen.append(c.error)

    def clear(self): pass


c.poll = poll
c.soon = Soon()
c.active = lambda: True
c._fast = lambda: False
c.loop(stop)
ok(seen[0] == "" and waits[0] == 3, f"первый сбой — человеку не показываем, повтор через 3 с: {seen[0]!r}, {waits[0]}")
ok(seen[1] == "" and waits[1] == 6, "следующий опрос прошёл — всё чисто, обычный шаг 6 с")
ok(seen[2] == "" and seen[3].startswith("нет связи"), f"два сбоя подряд — «нет связи»: {seen[2:4]}")
ok(seen[4] == "", "связь вернулась — надпись ушла")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
