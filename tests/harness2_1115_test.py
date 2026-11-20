"""Харнесс, шаг 2 (15.11): облегчённая системная подсказка — вместе с облегчённым набором действий (tools.slim, по
умолчанию да). Навыки — только именами (описания 1–3 подходящих — справкой к вопросу), «Ваши данные» — справкой только к
вопросу о данных; подсказка не меняется от вопроса к вопросу (кэш сервера цел). tools.slim: false — всё как раньше.
Сравнение размеров на живом ядре — lean_prompt1023 (короче на ~6 тыс. знаков)."""
import srctext  # noqa: E402 — текст исходника вместе с частями (tests/srctext.py)
import os, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path[:0] = [str(ROOT), str(ROOT / "core")]
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import engine_answer as EA  # noqa: E402
yes = ["где хранятся мои данные?", "кто видит наши разговоры?", "Сохраняет ли облако переписку?", "мои данные в безопасности?",
       "это конфиденциально?", "куда уходят мои записи и данные?", "соответствует 152-ФЗ?"]
no = ["Привет", "напомни завтра в 9 позвонить маме", "включи радио", "сколько будет 15% от 2400", "напиши письмо клиенту"]
ok(all(EA.PRIVACY_ASK_RX.search(t) for t in yes), "вопросы о данных узнаются: " + ", ".join(t for t in yes if not EA.PRIVACY_ASK_RX.search(t)))
ok(not any(EA.PRIVACY_ASK_RX.search(t) for t in no), "обычные просьбы — без справки о данных: " + ", ".join(t for t in no if EA.PRIVACY_ASK_RX.search(t)))


class S:
    def __init__(self, d): self.d = d
    def get(self, *k):
        v = self.d
        for x in k:
            v = (v or {}).get(x)
        return v


e = type("E", (), {})()
e.s = S({"tools": {}})
ok(EA.AnswerMixin._slim_prompt(e, True) and not EA.AnswerMixin._slim_prompt(e, False), "по умолчанию облегчённая — только с действиями")
e.s = S({"tools": {"slim": False}})
ok(not EA.AnswerMixin._slim_prompt(e, True), "tools.slim: false — подсказка как раньше")
src = srctext.text(ROOT, "core/engine_answer.py")
st = src[src.index("    def _system_stable("):src.index("    def _slim_prompt(")]
ok("if not self._slim_prompt(with_tools):" in st and "self._privacy_rule()" in st, "«Ваши данные» в подсказке — только без облегчения")
ok("self.skills.prompt_lean() if (lean or self._slim_prompt(with_tools)) else self.skills.prompt()" in st, "навыки — именами при облегчении")
tc = src[src.index("    def _turn_context("):]
ok("PRIVACY_ASK_RX.search(text)" in tc[:6000] and "self.skills.hint_for(ask_core(text))" in tc[:6000], "справка к вопросу: подходящие навыки (по самой просьбе, без вставки — 1.0.49) и «Ваши данные» — по вопросу")
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
