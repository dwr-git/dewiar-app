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


real, real_which = subprocess.Popen, G.shutil.which
G.subprocess.Popen = P
G.shutil.which = lambda n: None
try:
    ok(G.keep_awake(True) and calls and calls[-1][0] == "systemd-inhibit" and "--what=sleep:idle" in calls[-1], f"дозор пошёл — сон запрещён: {calls[-1:]}")
    ok(not G.keep_awake(True) and len(calls) == 1, "второй раз — без нового запрета")
    p = G._awake["proc"]
    ok(G.keep_awake(False) and p.dead and G._awake["proc"] is None, "дозоров нет — запрет снят")
    # 16.11 (владелец, Ubuntu: «экран гаснет через 10 минут, потом гибернация»): в GNOME — ещё и его запрет простоя и сна
    calls.clear()
    G.shutil.which = lambda n: "/usr/bin/" + n
    os.environ.setdefault("XDG_RUNTIME_DIR", "/run/user/1000")
    ok(G.keep_awake(True) and any(c[0] == "gnome-session-inhibit" and "idle:suspend" in c for c in calls), f"GNOME: экран не гаснет и не засыпает: {calls}")
    g = G._awake["gnome"]
    ok(G.keep_awake(False) and g.dead and G._awake["gnome"] is None, "GNOME: дозор кончился — запрет снят")
finally:
    G.subprocess.Popen, G.shutil.which = real, real_which
ok("ES_DISPLAY_REQUIRED" in (ROOT / "core/sleepguard.py").read_text(encoding="utf-8"), "Windows: и экран не гаснет")
src = (ROOT / "core/engine_watch.py").read_text(encoding="utf-8")
ok("keep_awake(on)" in src and "keep_awake(False)" in src, "цикл дозора держит компьютер бодрым, пока есть активный дозор, и отпускает в конце")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
