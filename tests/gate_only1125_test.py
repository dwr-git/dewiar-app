"""Опыт 4 (аудит Fable 25.11, переключатель llm.gate_only, выключен): при включённом «Каркасе хода» (llm.ledger) — одни ворота
по журналу хода в конце вместо каскада проверок «сказала „сделано“ без действия» (money/saved/note/call/found_pics/action/
task_claim, failed_claim) и их честных замен после хода. Без «Каркаса хода» каскад работает всегда — иначе ответ остался бы
вовсе без проверки. Проверка — по исходнику хода: сам ход с моделью гоняет стенд."""
import os, re, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    c or fails.append(m)


src = (ROOT / "core/engine_answer.py").read_text(encoding="utf-8")
ok('gate_only = self.s.get("llm", "gate_only") is True and _ledger.on(self.s.get("llm", "ledger"), prof)' in src,
   "ворота одни — только при llm.gate_only И включённом «Каркасе хода»")
casc = re.search(r"if not calls and not turn\.cancel\.is_set\(\) and step < 5 and specs and not saved_checked( and not gate_only)?:\n\s+fix = reminder_missing", src)
ok(casc and casc.group(1), "каскад *_claim при gate_only молчит")
fc = re.search(r"not failed_checked and getattr\(turn, \"tools_err\", None\)[^\n]*\n?[^\n]*not gate_only", src)
ok(bool(fc), "failed_claim при gate_only молчит")
ok("if saved_checked and not called" in src and "if failed_checked and not turn.cancel.is_set()" in src,
   "честные замены после хода — только если каскад сработал (при gate_only — нет)")
ok("bad_ = ledger.check(text, turn.full, acts_, _ask_)" in src, "ворота журнала на месте")
ok('"gate_only": False' in (ROOT / "core/settings.py").read_text(encoding="utf-8"), "переключатель по умолчанию выключен")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
print("ALL OK" if not fails else "")
sys.exit(1 if fails else 0)
