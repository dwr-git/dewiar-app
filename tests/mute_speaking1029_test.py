"""№410 (29.10): «пока агент говорит, нажал „заглушить микрофон“ — озвучка обрывается». Ожидание: кнопка микрофона не
сбрасывает ответ, который говорится или думается; слушание (недоговорённый вопрос) — обрывает, как раньше."""
import os, sys, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import engine_commands as EC  # noqa: E402


def make(state):
    e = types.SimpleNamespace(state=state, muted=False, follow_up_until=5.0, cancelled=[], states=[], ev=[])
    e.cancel_turn = lambda: e.cancelled.append(1)
    e.set_state = lambda st: (e.states.append(st), setattr(e, "state", st))
    e.emit = lambda name, **k: e.ev.append((name, k))
    return e


for st in ("speaking", "thinking"):
    e = make(st)
    EC.CommandsMixin.set_mute(e, True)
    ok(e.muted and not e.cancelled and e.state == st and ("muted", {"on": True}) in e.ev,
       f"{st}: микрофон выключен, ответ не оборван, состояние «{e.state}»")
    EC.CommandsMixin.set_mute(e, False)
    ok(not e.muted and not e.cancelled and e.state == st, f"{st}: включили обратно — ответ тоже идёт дальше")
e = make("listening")
EC.CommandsMixin.set_mute(e, True)
ok(e.cancelled and e.states[-1] == "muted", "слушала вопрос — выключили микрофон: слушание оборвано, «микрофон выключен»")
e = make("idle")
EC.CommandsMixin.set_mute(e, True)
ok(e.states[-1] == "muted" and e.follow_up_until == 0.0, "в покое — «микрофон выключен»")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
