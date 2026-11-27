"""Ход разговора по шагам (чистое ядро 1.0.12–1.0.13, docs/CORE_PLAN.md): _run_turn — короткий поток хода, работа — в шагах
_turn_prepare → _turn_steps → _turn_finish. Проверка следит, чтобы «сердце» ответа снова не разрослось в один метод на
900 строк, и что о сбое модели сообщается по той модели, которой шёл ход (e.turn_prof: экономный режим или запасная)."""
import ast, os, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path[:0] = [str(ROOT), str(ROOT / "core")]
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


src = (ROOT / "core/engine_answer.py").read_text(encoding="utf-8")
t = ast.parse(src)
cls = next(n for n in t.body if isinstance(n, ast.ClassDef) and n.name == "AnswerMixin")
m = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}
# 1.0.57: _run_turn — обёртка «Рентгена» (xray.attach/finish), поток хода — _run_turn_body
size = {k: m[k].end_lineno - m[k].lineno + 1 for k in ("_run_turn_body", "_turn_prepare", "_turn_steps", "_turn_finish") if k in m}
ok(set(size) == {"_run_turn_body", "_turn_prepare", "_turn_steps", "_turn_finish"}, f"шаги хода на месте: {sorted(size)}")
ok(size.get("_run_turn_body", 999) <= 120, f"_run_turn_body — короткий поток хода ({size.get('_run_turn_body')} строк, не больше 120)")
ok("self._run_turn_body(" in ast.get_source_segment(src, m["_run_turn"]) and "xray.finish" in ast.get_source_segment(src, m["_run_turn"]),
   "_run_turn — поток хода под рентгеном")
rt = ast.get_source_segment(src, m["_run_turn_body"])
ok(rt.index("self._turn_prepare(") < rt.index("self._turn_steps(") < rt.index("self._turn_finish("), "порядок: подготовить → ход → после ответа")
ok('prof = getattr(e, "turn_prof", prof)' in rt, "сбой модели — по той модели, которой шёл ход")
for k in ("_turn_prepare", "_turn_steps"):
    seg = ast.get_source_segment(src, m[k])
    ok("e.turn_prof = prof" in seg and "raise" in seg, f"{k}: LLMError уходит наверх с моделью хода")

import engine  # noqa: E402
ok(all(hasattr(engine.Engine, k) for k in size), "Engine знает все шаги хода")
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
