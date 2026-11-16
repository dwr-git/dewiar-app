"""Короткие фразы (отчёт 11.10): «спасибо» — ответить «Пожалуйста!» и уснуть, а не молча погаснуть; после «Лира» быстрое
«спасибо» или «как дела» — это фраза человека, а не ослышанное имя (раньше снова «Слушаю…», и фраза терялась)."""
import srctext  # noqa: E402 — текст исходника вместе с частями (tests/srctext.py)
import os, sys, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


from engine_base import thanks_phrase, is_sleep_phrase  # noqa: E402
yes = ["Спасибо", "спасибо большое", "Благодарю тебя", "ладно, спасибо", "огромное спасибо за помощь", "Thanks"]
no = ["стоп, спасибо", "Хватит, спасибо!", "спасибо, а что ещё ты умеешь", "скажи спасибо маме", "хватит"]
ok(all(thanks_phrase(t) for t in yes), f"благодарность: {[t for t in yes if not thanks_phrase(t)] or 'все'}")
ok(not any(thanks_phrase(t) for t in no), f"не благодарность (стоп, вопрос): {[t for t in no if thanks_phrase(t)] or 'все'}")
ok(is_sleep_phrase("Хватит, спасибо!") and is_sleep_phrase("стоп"), "«хватит, спасибо», «стоп» — по-прежнему сон без ответа")

from engine_audio import AudioMixin  # noqa: E402
host = types.SimpleNamespace(aliases={"lira": ["Лира"], "eva": ["Эва"], "agent": ["Агент"], "patrik": ["Патрик"]})
nl = lambda t: AudioMixin._name_like(host, t)  # noqa: E731
ok(all(nl(t) for t in ["", "Лера", "Игрова", "Элла", "Ира"]), "ослышанное имя («Лера», «Игрова», «Элла») — имя, слушаем вопрос")
ok(not any(nl(t) for t in ["спасибо", "как дела", "да", "стоп", "который час"]), "«спасибо», «как дела», «да» — фраза человека, не имя")

src = srctext.text(ROOT, "core/engine_answer.py")
ok("thanks_phrase(text)" in src and "def _thanks" in src and "THANKS_REPLIES" in src, "ядро: на «спасибо» — короткий ответ, затем звук «не слушаю»")
src = srctext.text(ROOT, "core/engine_audio.py")
ok("self._name_like(text)" in src and "thanks_phrase(rest)" in src, "«Лира, спасибо» и ослышанное имя — через новые проверки")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
