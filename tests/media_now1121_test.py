"""Владелец 21.11, 21:34: «Один раз включал радио, давно выключил — а Лира рассказывает, что музыка всё ещё играет». Модель
судила по разговору. Если в разговоре была музыка, справка к вопросу говорит, что на самом деле сейчас (из программы):
играет такое-то, на паузе или не играет. Без музыки в разговоре — ни слова (лишнее в подсказке)."""
import os, sys
from pathlib import Path
from types import SimpleNamespace
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import answer_prompt as AP  # noqa: E402
M = AP.PromptMixin.media_now_line
H = [{"role": "user", "content": "включи радио"}, {"role": "assistant", "content": "Включила радио «Groove Salad»."}]
e = SimpleNamespace(history=H, radio=SimpleNamespace(status=lambda: {"playing": False, "station": "", "paused": ""}))
ok("не играет" in M(e) and "не говори, что она звучит" in M(e), f"радио выключили — справка говорит правду: {M(e)}")
e.radio = SimpleNamespace(status=lambda: {"playing": True, "station": "Groove Salad", "paused": ""})
ok(M(e) == "Сейчас в Dewiar играет «Groove Salad».", f"играет — называет что: {M(e)}")
e.radio = SimpleNamespace(status=lambda: {"playing": False, "station": "", "paused": "Groove Salad"})
ok("на паузе" in M(e), "на паузе — так и говорит")
e.history = [{"role": "user", "content": "как дела?"}, {"role": "assistant", "content": "Хорошо."}]
ok(M(e) == "", "музыки в разговоре не было — ни слова")
src = (ROOT / "core/answer_prompt.py").read_text(encoding="utf-8")
ok("media = self.media_now_line()" in src, "в справке к каждому вопросу")
print("ИТОГ:", "всё прошло" if not fails else f"{len(fails)} не прошло")
sys.exit(1 if fails else 0)
