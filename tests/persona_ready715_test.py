"""№715 (14.11): «попросила подключить Гастона, Лира пишет, что не понимает, о ком речь». Гастон — готовый персонаж,
но в команду его ещё не добавили, и call_persona знал только команду. Теперь «подключи/позови Гастона» добавляет готового
персонажа в команду и передаёт ему слово; неизвестное имя — ошибка со списком команды и готовых."""
import os, sys, tempfile
from pathlib import Path
from types import SimpleNamespace
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
tmp = Path(tempfile.mkdtemp())
os.environ.update(DEWIAR_CONFIG_DIR=str(tmp / "cfg"), DEWIAR_STATE_DIR=str(tmp / "st"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import tools as TL  # noqa: E402
import engine as E  # noqa: E402
from personas import Personas  # noqa: E402

ok("подключить" in TL.TOOLS["call_persona"][0] and "Гастон" in TL.TOOLS["call_persona"][0], "модель знает: готового персонажа можно позвать — добавится сам")
e = E.Engine.__new__(E.Engine)
e.personas = Personas()
ev = []
e.emit = lambda t, **k: ev.append(t)
e.s = SimpleNamespace(get=lambda *k: "lira")
e.turn = SimpleNamespace()
ok(not any(p["name"] == "Гастон" for p in e.personas.all()), "сначала Гастона в команде нет")
r = e._tool_call_persona("Гастона")
ok(any(p["name"] == "Гастон" for p in e.personas.all()) and getattr(e.turn, "switch_to", "") and "добавлен(а) в команду" in r and "personas" in ev,
   f"«подключи Гастона» — добавлен в команду и получает слово: {r[:90]}")
pid = e.turn.switch_to
e.turn = SimpleNamespace()
r2 = e._tool_call_persona("Гастон")
ok(e.turn.switch_to == pid and "добавлен" not in r2, "второй раз — уже из команды, без повторного добавления")
try:
    e._tool_call_persona("Шерлок"); msg = ""
except TL.ToolError as x:
    msg = str(x)
ok("нет персонажа «Шерлок»" in msg and "Готовые" in msg and "Фемида" in msg, f"неизвестное имя — честно, со списком готовых: {msg[:120]}")
print("ALL OK" if not fails else f"FAILED: {len(fails)}")
sys.exit(1 if fails else 0)
