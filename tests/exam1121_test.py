"""Экзамен владельца 21.11 («Понимание ситуации», сцена разговора, 5 из 8) и «как дела?»:
- чужая фраза в кавычках («Я вёл проект запуска приложения…») приложила раздел руководства — разговор сбился (sit_goal);
- «Как твои дела?» — «Удалось немного посидеть в тишине… Что заставило тебя спросить?» (владелец: «неимоверно глупо»)."""
import json, os, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import guide  # noqa: E402
import personas as P  # noqa: E402

q = "На первый я отвечу так: «Я вёл проект запуска приложения, команда 6 человек, уложились в срок». Нормально?"
ok(not guide.hint(q, "pc") and not guide.attach(q, "pc"), "цитата человека про его приложение — не вопрос о Dewiar, руководство не прикладываем")
ok(guide.hint("что за значки у меня в «Делах»?", "pc"), "название раздела в кавычках — по-прежнему раздел руководства")
ok("О себе — только правда" in P.TALK_RULES and "как у тебя дела" not in P.TALK_RULES,
   "о себе — общий принцип (нет дня и занятий вне разговоров), а не правило на фразу «как дела» (владелец 21.11: не словарь)")
sc = {s["id"]: s for s in json.loads((ROOT / "data/exam/scenarios.json").read_text(encoding="utf-8"))["scenarios"]}
t = sc.get("talk_howareyou") or {}
ok(t.get("group") == "Разговор" and "в тишине" in (t.get("expect") or {}).get("none", []), "сценарий экзамена «Как твои дела?» — в группе «Разговор» (стенд)")
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
