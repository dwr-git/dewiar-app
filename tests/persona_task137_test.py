"""Идея №137 (Gray, 04.11): «передать задачу между персонажами, а не только слово: „Патрик, сверь эти цифры с прошлым
периодом и запиши вывод“ — второй начинает с чистого листа и угадывает мотив». Теперь у call_persona есть task —
поручение своими словами; новый персонаж получает его явной вводной (сделать самому, инструментами, данные — из
разговора, заметок и файлов), а итог длиннее пары фраз кладёт в общую заметку «Команда: …»."""
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

spec = TL.TOOLS["call_persona"]
ok("task" in spec[1]["properties"] and "поручение" in spec[0], "call_persona: поле task — поручение")
got = []
TL.t_call_persona({"name": "Патрик", "task": "сверь цифры за октябрь с сентябрём и запиши вывод"}, {"call_persona": lambda n, t="": got.append((n, t)) or "ok"})
ok(got == [("Патрик", "сверь цифры за октябрь с сентябрём и запиши вывод")], "поручение доходит до ядра")
got.clear()
TL.t_call_persona({"name": "Патрик"}, {"call_persona": lambda n: got.append((n,)) or "ok"})
ok(got == [("Патрик",)], "без поручения — как раньше")

e = E.Engine.__new__(E.Engine)
e.find_persona = lambda n: "patrik"
e.s = SimpleNamespace(get=lambda *k: "lira")
e.personas = SimpleNamespace(get=lambda pid: {"name": "Патрик"}, all=lambda: [])
e.turn = SimpleNamespace()
r = e._tool_call_persona("Патрик", "сверь цифры за октябрь с сентябрём")
ok(e.turn.switch_to == "patrik" and e.turn.switch_task == "сверь цифры за октябрь с сентябрём" and "возьмётся за поручение" in r,
   f"ход запоминает, кому и что передано: {r[:80]}")
src = (ROOT / "core" / "engine_answer.py").read_text(encoding="utf-8")
ok("передал(а) тебе поручение пользователя" in src and "«Команда: <о чём>»" in src, "новый персонаж получает поручение явной вводной; итог — в общую заметку")
print("ALL OK" if not fails else f"FAILED: {len(fails)}")
sys.exit(1 if fails else 0)
