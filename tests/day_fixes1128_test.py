"""Разбор кода человеком (28.11) — «Мой день» говорит правду:
№1145 — прозвеневшее напоминание в календаре было «сделано», хотя человек его не отмечал; «Оплатить счёт» пропадал из итога
дня как «привычка», потому что есть ежедневное «Оплатить интернет» (совпал один глагол).
№1143 — утром напоминание на паузе называлось делом дня; календарь не прочитался — «дел нет»; деньги — только первая валюта."""
import os, sys
from datetime import datetime
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    c or fails.append(m)


import engine_music  # noqa: E402
import morning  # noqa: E402


class H(engine_music.MusicMixin):
    done = None

    def _habits(self, weekly=False):
        return set(), {"Оплатить интернет", "Обед — не забудь взять карту"}


h = H()._habit_pred()
ok(not h("Оплатить счёт"), "«Оплатить счёт» — не привычка «Оплатить интернет» (общий только глагол)")
ok(h("Карту взяла") and h("Обед"), "«Карту взяла», «Обед» — по-прежнему привычка «Обед — не забудь взять карту»")
ok(h("Оплатить интернет") and not h("Отправила договор Вектору"), "сама привычка — да; чужое дело — нет")


class Eng:
    def calendar_month(self, y, m):
        k = datetime(y, m, 15).date().isoformat()
        return {"days": {k: [{"type": "reminder", "title": "Позвонить маме", "time": "10:00"},
                             {"type": "reminder", "title": "Отпуск: билеты", "time": "12:00", "paused": True},
                             {"type": "reminder", "title": "Таблетки", "time": "08:00", "done": True}]}}


t = morning._today(Eng(), datetime(2026, 11, 15, 7, 0))
ok([x["title"] for x in t["todo"]] == ["Позвонить маме"], f"утро: на паузе и прозвеневшее — не дела дня: {t['todo']}")
src = (ROOT / "core/engine_music.py").read_text(encoding="utf-8")
ok("календарь сейчас не прочитался" in src and "cal_ok = t is not None" in src, "календарь не прочитался — не «дел нет»")
ok('for c in sm["by_currency"][:3]:' in src, "деньги утром — по каждой валюте")
tn = (ROOT / "core/tools_notes.py").read_text(encoding="utf-8")
ok('"сделано" if it.get("closed") or it.get("kind") == "done" else "пропущено" if it.get("skipped")' in tn
   and 'else "прозвенело" if it.get("done")' in tn, "календарь: «сделано» — только отмеченное, иначе «прозвенело» или «пропущено»")
print("ИТОГ: " + ("всё прошло" if not fails else f"провалов {len(fails)}"))
sys.exit(1 if fails else 0)
