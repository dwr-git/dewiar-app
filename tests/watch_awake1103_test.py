"""Идея №111 (01.11): «во время Дозора частая проблема — засыпание компьютера. Если Дозор включён, засыпать не должен».
Пока есть активный дозор — системе сказано не засыпать (Windows — SetThreadExecutionState, Linux — systemd-inhibit);
дозоров нет — снова можно."""
import os, subprocess, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
import sleepguard as G  # noqa: E402
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


calls = []


class P:
    def __init__(self, args, **kw):
        calls.append(args); self.dead = False

    def terminate(self):
        self.dead = True


real = subprocess.Popen
G.subprocess.Popen = P
try:
    ok(G.keep_awake(True) and calls and calls[-1][0] == "systemd-inhibit" and "--what=sleep:idle" in calls[-1], f"дозор пошёл — сон запрещён: {calls[-1:]}")
    ok(not G.keep_awake(True) and len(calls) == 1, "второй раз — без нового запрета")
    p = G._awake["proc"]
    ok(G.keep_awake(False) and p.dead and G._awake["proc"] is None, "дозоров нет — запрет снят")
finally:
    G.subprocess.Popen = real
src = (ROOT / "core/engine_watch.py").read_text(encoding="utf-8")
ok("keep_awake(on)" in src and "keep_awake(False)" in src, "цикл дозора держит компьютер бодрым, пока есть активный дозор, и отпускает в конце")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
