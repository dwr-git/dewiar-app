"""Пачка 16.11, 15:09:
№786: два микрофона, Лира спросила руководство «выбор микрофона, несколько микрофонов, устройство ввода» — а нашла
     «Установку» («несколько компьютеров», «добавить устройство»). Теперь — «Если что-то не работает» с прямым ответом:
     студия → «Звук и поведение» → «Микрофон». Там же: «текстовый файлик создать, чтобы я почитал» — заметку не
     сохраняли («без просьбы записать»), хотя просьба была.
№788: «мой подкаст готов?» — task_status отвечал «задач нет», хотя выпуск ждал в «Подкастах»."""
import os, sys, time
from pathlib import Path
from types import SimpleNamespace
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path[:0] = [str(ROOT), str(ROOT / "core")]
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import guide  # noqa: E402
for q in ("выбор микрофона, несколько микрофонов, какой микрофон слушает, устройство ввода",
          "устройство ввода микрофона выбрать, какой микрофон использует Dewiar", "у меня два микрофона, как выбрать нужный"):
    got = [s["id"] for s in guide.search(q, "pc")]
    ok(got[:1] == ["troubleshooting"], f"№786: «{q[:40]}…» → {got}")
txt = guide.answer("выбор микрофона, несколько микрофонов", "pc")
ok("«Звук и поведение» → «Микрофон»" in txt, "№786: в ответе руководства — где выбрать микрофон")
ok([s["id"] for s in guide.search("несколько компьютеров", "pc")][:1] == ["install"], "«несколько компьютеров» — по-прежнему «Установка»")

from engine_tools import NOTE_ASK_RX  # noqa: E402
for s in ("Ты можешь как-то текстовый файлик создать, чтобы я почитал, когда мне будет удобно?",
          "создай мне документ с этим планом", "сделай текстовый файл со списком", "запиши это"):
    ok(bool(NOTE_ASK_RX.search(s)), f"№786: просьба записать — «{s}»")
for s in ("напиши четверостишие про осень", "какие у тебя есть идеи для подарка?", "открой файл отчёта"):
    ok(not NOTE_ASK_RX.search(s), f"не просьба записать — «{s}»")

import tools_tasks as TT  # noqa: E402
now = time.time()
pods = [{"id": "p1", "title": "Почему мозг не может остановиться", "status": "done", "created": now - 3600, "duration": 569},
        {"id": "p2", "title": "Старый выпуск", "status": "done", "created": now - 10 * 86400, "duration": 300},
        {"id": "p3", "title": "Про сон", "status": "working", "created": now - 60, "duration": 0}]
eng = SimpleNamespace(podcasts=SimpleNamespace(list=lambda: pods))
r = TT.t_task_status({}, {"tasks": SimpleNamespace(list=lambda: []), "engine": eng})
ok("Почему мозг не может остановиться" in r and "готов — 9:29" in r and "Про сон» — готовится" in r and "Старый" not in r
   and "«Подкасты»" in r, f"№788: «мой подкаст готов?» — подкасты в ответе: {r}")
r = TT.t_task_status({}, {"tasks": SimpleNamespace(list=lambda: []), "engine": SimpleNamespace()})
ok(r == "Задач пока нет.", "без подкастов и задач — как было")
import tools as T  # noqa: E402
ok("подкаст" in T.TOOLS["task_status"][0], "описание task_status — и про подкасты")

print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
