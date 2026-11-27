"""Опыт 2 (аудит Fable 25.11, переключатель llm.rules_with_tools, выключен): правила действий в подсказке — кусками
(answer_prompt.TOOL_RULES), у каждого — свои действия. Выключено — подсказка прежняя байт в байт (кэш начала запроса у
всех, кто не в опыте); включено — кусок идёт, только если его действие есть в этом ходе («СЧЁТ» — с calc, «МУЗЫКА» — с
музыкой, «разобраться с компьютером» — с run_command); общее («СЛОВА НЕ ДЕЙСТВУЮТ», пароли, схемы) — всегда. Пришла
группа по more_tools — подсказка собирается заново, с её правилами."""
import os, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
import answer_prompt as A  # noqa: E402
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    c or fails.append(m)


class S:
    def __init__(self, on): self.on = on
    def get(self, *k, default=None): return {("llm", "rules_with_tools"): self.on}.get(k, default)


class E(A.PromptMixin):
    pass


e = E()
e._music_service = lambda: "radio"
full = "".join(t for _, t in A.TOOL_RULES)
ok(full.startswith("\n\nУ тебя есть инструменты") and "СЧЁТ:" in full and full.rstrip().endswith("«запомни пароль от …: …»."),
   "куски склеиваются в прежний текст правил (начало, середина, конец)")
e.s, e._rule_names = S(False), {"web_search"}
ok(e._tool_rules().startswith(full) and "МУЗЫКА" in e._tool_rules() and "разобраться с компьютером" in e._tool_rules() and e._rule_on(A.MUSIC_TOOLS) and e._rule_on(("run_command",)), "выключено — все правила, как раньше")
e.s = S(True)
part = e._tool_rules()
ok("СЛОВА НЕ ДЕЙСТВУЮТ" in part and "Пароли, пин-коды" in part and "КАРТИНКИ И СХЕМЫ" in part, "общее — всегда")
ok("СЧЁТ:" not in part and "money_add" not in part and "lab_write" not in part and "БЕЗОПАСНОСТЬ" not in part,
   f"чужие правила не идут: {len(part)} из {len(full)} знаков")
ok(not e._rule_on(A.MUSIC_TOOLS) and not e._rule_on(("run_command",)), "музыка и «разобраться с компьютером» — без своих действий не идут")
e._rule_names = A.spec_names([{"name": "calc"}, {"type": "function", "function": {"name": "play_radio"}}])
ok("СЧЁТ:" in e._tool_rules() and e._rule_on(A.MUSIC_TOOLS), "с calc — «СЧЁТ», с play_radio — «МУЗЫКА» (описания обоих видов)")
e._rule_names = None
ok(e._tool_rules().startswith(full) and "МУЗЫКА" in e._tool_rules(), "набор действий неизвестен — все правила")

src = (ROOT / "core/engine_answer.py").read_text(encoding="utf-8")
ok(src.count("self._rule_names = spec_names(specs)") >= 4 and "system = system.replace(old_r, new_r, 1)" in src,
   "ход: набор правил — по действиям хода (начало, переход к делу); группа по more_tools — правила заменяются на месте")
ap = (ROOT / "core/answer_prompt.py").read_text(encoding="utf-8")
ok('out += "" if not self._rule_on(MUSIC_TOOLS) else ("\\n\\nМУЗЫКА: "' in ap and 'base += self._tool_rules()' in ap, "подсказка собирается из кусков")
# замена на месте: правила — сплошной кусок, его начало в подсказке одно
e.s = S(True)
e._rule_names = {"web_search"}
old_r = e._tool_rules()
sysp = "ХАРАКТЕР" + old_r + "НАВЫКИ"
e._rule_names = {"web_search", "calc", "play_radio"}
new_r = e._tool_rules()
ok(sysp.replace(old_r, new_r, 1) == "ХАРАКТЕР" + new_r + "НАВЫКИ" and "МУЗЫКА" in new_r and "МУЗЫКА" not in old_r, "пришла группа — правила заменены на месте, остальное цело")
ok('"rules_with_tools": False' in (ROOT / "core/settings.py").read_text(encoding="utf-8"), "переключатель по умолчанию выключен")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
print("ALL OK" if not fails else "")
sys.exit(1 if fails else 0)
