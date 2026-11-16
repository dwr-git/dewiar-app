"""Пачка 15.11, 22:17:
№257 (идея): «Озвучка Лиры звучит очень быстро. Она не может себя замедлить» — а курс «Неделя с Лирой» обещал «Говори
     помедленнее». Теперь короткая просьба о темпе — без модели: «Голос» → «Темп речи» на шаг, «машина быстрее» — не она.
№755: Ubuntu, «дай команду для скачки» — Лира выдумала адрес dewiar.pro/downloads/… и сказала «для Ubuntu не выпускается».
     В руководстве — настоящая команда (GitHub, последняя версия) и что на VPS без экрана не ставят; сценарий экзамена.
№757: «Мозг: нет настройки запасного мозга» — Лира обещала «при сбое DeepSeek пересяду на Ollama» (так нельзя): руководство
     говорит честно, где какой запасной."""
import srctext  # noqa: E402 — текст исходника вместе с частями (tests/srctext.py)
import json, os, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path[:0] = [str(ROOT), str(ROOT / "core")]
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import engine_answer as EA  # noqa: E402


class P:
    def all(self): return [{"name": "Лира", "aliases": ["лира"]}, {"name": "Патрик"}]


class S:
    def __init__(self): self.d = {"tts": {"speed": 1.25}}

    def get(self, *k):
        v = self.d
        for x in k:
            v = (v or {}).get(x)
        return v

    def update(self, p): self.d["tts"].update(p["tts"])
    def snapshot(self): return self.d


said = []
e = type("E", (), {})()
e.personas, e.s, e.emit = P(), S(), (lambda *a, **k: None)
e._say_quick = lambda m, t, v=None: said.append(m)
run = lambda t: EA.AnswerMixin._speed_cmd(e, t)  # noqa: E731
ok(run("Говори помедленнее, пожалуйста") and e.s.d["tts"]["speed"] == 1.1 and said[-1] == "Хорошо, говорю медленнее.", "«говори помедленнее» — темп на шаг ниже, одной фразой")
ok(run("Лира, не так быстро") and e.s.d["tts"]["speed"] == 0.95, "«Лира, не так быстро» — тоже")
ok(run("говори быстрее") and e.s.d["tts"]["speed"] == 1.1, "«говори быстрее» — на шаг выше")
for t in ("машина быстрее", "едет медленнее", "быстрее!", "давай быстрее", "расскажи медленнее про погоду"):
    ok(not run(t), f"«{t}» — не просьба о темпе голоса")
e.s.d["tts"]["speed"] = 0.7
ok(run("помедленнее") and e.s.d["tts"]["speed"] == 0.7 and "некуда" in said[-1], "медленнее некуда — так и сказано")
src = srctext.text(ROOT, "core/engine_answer.py")
ok("self._speed_cmd(text, via)" in src, "просьба о темпе проверяется до модели")

g = (ROOT / "data/guide.json").read_text(encoding="utf-8")
ok("releases/latest/download/dewiar-assistant_all.deb && sudo apt install ./dewiar-assistant_all.deb" in g and "VPS" in g,
   "№755: в руководстве — настоящая команда для Ubuntu и про VPS")
ok("Пересадить сервис по ключу на свою модель" in g, "№757: руководство не обещает запасной, которого нет")
ok("говори помедленнее" in g, "№257: в руководстве — темп голосом")
sc = json.loads((ROOT / "data/exam/scenarios.json").read_text(encoding="utf-8"))
items = sc if isinstance(sc, list) else sc["scenarios"]
u = next((x for x in items if x.get("id") == "help_ubuntu_cmd"), None)
ok(u and "dewiar.pro/downloads/" in u["expect"]["none"], "№755: сценарий экзамена — без выдуманного адреса")
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
