"""Экзамен владельца 12.11 (confirm_cut_yes): прошлый ответ перебили на вопросе «Выполнить действие «Напоминание»?
Скажите «да» или «нет»», человек сказал «Да.» — модель ответила «Хорошо. Что на уме?» и таймер не поставила. Вопрос
программы из истории убирается (№625–628: это не слова модели), и модель не знала, на что «да». Теперь у последней
реплики — пометка: что ждало разрешения и что «да» — значит выполнить."""
import os, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import engine_answer as E  # noqa: E402

h = [{"role": "user", "content": "Поставь таймер на 15 минут"},
     {"role": "assistant", "content": "Ставлю таймер на 15 минут. Выполнить действие «Напоминание»? Скажите «да» или «нет». …(меня перебили)"},
     {"role": "user", "content": "Да."}]
w = E.team_window(h, "lira", lambda x: "Лира")
a = [m for m in w if m["role"] == "assistant"][-1]["content"]
ok("Скажите «да»" not in a and "Выполнить действие" not in a, "служебный вопрос в историю не попал (№625–628)")
ok("«Напоминание»" in a and "выполни это действие сейчас" in a, f"пометка: что ждало разрешения и что делать на «да»: {a[-150:]!r}")
h2 = [h[0], h[1], {"role": "user", "content": "нет, другое"}, {"role": "assistant", "content": "Хорошо."}, {"role": "user", "content": "Да."}]
w2 = E.team_window(h2, "lira", lambda x: "Лира")
ok(not any("выполни это действие сейчас" in m["content"] for m in w2), "старый вопрос (не последняя реплика) — без пометки")
if fails:
    sys.exit(1)
print("\n✅ всё в порядке")
