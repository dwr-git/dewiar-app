"""Опыт 6 (аудит Fable 25.11): быстрая команда сделала дело без модели («Каждый будний день в 8…» — дело по расписанию,
«Сколько места на диске?»), а система этого не видела: в рентгене и журнале хода — пусто, судья стенда ставил 0 («не вызвал
инструмент»), модель в следующем ходе видела «беру на себя» без следа действия. Теперь команда пишет в журнал ту же запись,
что действие модели (событие «quick»); экзамен показывает её судье как действие. Виджету и студии это событие не нужно."""
import os, sys, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    c or fails.append(m)


import xray  # noqa: E402
import exam  # noqa: E402


class Eng:
    def __init__(self):
        self.events = []

    def emit(self, type_, **kw):
        if type_ in ("tool", "answer", "quick"):
            xray.event(type_, kw)
        self.events.append(dict(kw, type=type_))

    def _job_cmd(self, text, via=None):
        self.emit("answer", text="Хорошо, беру это на себя: по будням в 8:00 — «прогноз погоды».", done=True)
        return True

    def _clock_cmd(self, text, via=None):
        self.emit("tool", name="set_reminder", status="done", result="ок")   # команда сама вызвала действие
        self.emit("answer", text="Поставила.", done=True)
        return True


e = Eng()
xray.instrument(e)
xr = xray.begin("Каждый будний день в 8 утра присылай мне прогноз погоды")
e._job_cmd("Каждый будний день в 8 утра присылай мне прогноз погоды")
ok(xr["route"]["kind"] == "cmd" and xr["acts"] and xr["acts"][0]["name"] == "cmd:job_cmd" and xr["acts"][0]["quick"] and xr["acts"][0]["ok"],
   f"в журнале хода — запись команды: {xr['acts']}")
t = exam.tools_of(e.events)
ok(t and t[0]["name"] == "команда «Работа»" and "беру это на себя" in t[0]["result"], f"экзамен: судья видит команду как действие: {t}")
e.events.clear()
xr = xray.begin("напомни через 5 минут")
e._clock_cmd("напомни через 5 минут")
ok([a["name"] for a in xr["acts"]] == ["set_reminder"], "команда сама вызвала действие — вторую запись не пишем")
ok(not any(x["type"] == "quick" for x in e.events), "…и события «quick» нет")
src = (ROOT / "core/engine.py").read_text(encoding="utf-8")
ok('if type_ in ("tool", "answer", "quick"):' in src, "ядро передаёт «quick» рентгену")
ok("[ответила сама программа" not in (ROOT / "core/exam.py").read_text(encoding="utf-8"), "оговорка для судьи больше не нужна — журнал вместо неё")
print("ИТОГ: " + ("всё прошло" if not fails else f"провалов {len(fails)}"))
sys.exit(1 if fails else 0)
