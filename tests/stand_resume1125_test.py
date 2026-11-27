"""Владелец 25.11, прогон 3 стенда с платным внешним судьёй: «экзамен почти закончился — и запустился заново… уже почти
час работало, и всё заново. Я оплачиваю токены большой модели». Публикация архива сервера перезапускает исполнителя;
обычный экзамен продолжал с места (--partial/--resume), а стенд эти флаги не получал и начинал с первого прогона.
Теперь стенд пишет каждый готовый прогон (и сценарии текущего) и после перезапуска продолжает."""
import asyncio, json, os, sys, tempfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import exam  # noqa: E402
import stand  # noqa: E402

calls = []


class Boom(Exception):
    pass


async def fake(prof, jp, only, long, log=print, groups=None, overrides=None, label="", partial=None, resume=False, **k):
    calls.append({"label": label, "partial": partial, "resume": resume})
    if len(calls) == STOP_AT:
        raise Boom()                                     # исполнитель перезапустили посреди прогона
    r = {"id": "s1", "group": "Честность", "title": "т", "passed": True, "time_s": 1.0, "score": 9, "checks": []}
    return {"scenarios": [r], "summary": {}, "started": "2026-11-25T19:00:00"}

exam.run_exam = fake
pf = Path(tempfile.mkdtemp()) / "partial.json"
STOP_AT = 6                                              # 5 готовых прогонов из 10, шестой оборвался
try:
    asyncio.run(stand.run_stand({"model": "m"}, None, ["Честность"], {}, {"llm.force_call": True}, 5, log=lambda t: None,
                                partial=str(pf), resume=False))
except Boom:
    pass
st = json.loads(pf.read_text(encoding="utf-8"))
ok(len(st["done"]) == 5, f"готовые прогоны записаны: {len(st['done'])}")
ok(calls[5]["partial"] and calls[5]["partial"].startswith(str(pf)), "внутри прогона — свой файл сценариев")
calls.clear(); STOP_AT = 0
rep = asyncio.run(stand.run_stand({"model": "m"}, None, ["Честность"], {}, {"llm.force_call": True}, 5, log=lambda t: None,
                                  partial=str(pf), resume=True))
ok(len(calls) == 5, f"после перезапуска — только оставшиеся 5 прогонов, а не все 10: {len(calls)}")
ok(calls[0]["resume"] is True, "оборванный прогон — продолжает по своим сценариям")
ok(rep["stand"]["groups"]["Честность"]["A"][1] == 5 and rep["stand"]["groups"]["Честность"]["B"][1] == 5, "итог — по всем 10 прогонам")
src = (ROOT / "core/exam.py").read_text(encoding="utf-8")
ok("partial=a.partial, resume=a.resume))" in src.split("stand.run_stand(")[1][:300], "exam.py передаёт стенду --partial и --resume исполнителя")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
