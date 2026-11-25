"""Опыт 1 (аудит Fable 25.11, переключатель llm.history_native, по умолчанию выключен): действия прошлых ответов — в истории
родным форматом (вызов с аргументами → итог → слова), как в самом ходе, а не пометкой «[в этом ответе выполнено
инструментами: …]». Проверяем: что попадает в историю (без служебного more_tools, ключи — ***, коротко); окно модели —
вызовы у последних ответов, у старых — прежняя пометка; формат по протоколу (OpenAI — tool_calls и tool, без родных
действий — текстом <tool_call>, Claude — пометкой); выключено — всё как раньше; id вызовов не повторяются."""
import json, os, sys, tempfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
tmp = Path(tempfile.mkdtemp())
os.environ.update(DEWIAR_CONFIG_DIR=str(tmp / "cfg"), DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_WORKSPACE=str(tmp / "ws"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    c or fails.append(m)


import engine_answer as EA  # noqa: E402
import answer_rules as AR  # noqa: E402
import settings as ST  # noqa: E402

ok(ST.DEFAULTS["llm"]["history_native"] is False if hasattr(ST, "DEFAULTS") else '"history_native": False' in (ROOT / "core/settings.py").read_text(encoding="utf-8"),
   "переключатель есть и по умолчанию выключен")

# 1) что уходит в историю
done = [{"name": "more_tools", "args": {"packs": ["core"]}, "result": "Добавлены: core"},
        {"name": "set_reminder", "args": {"text": "позвонить маме", "when": "2026-11-26T09:00", "token": "ghp_" + "a" * 30},
         "result": "Поставлено на 26.11 в 9:00 " + "x" * 600}]
c = AR.hist_calls(done)
ok([x["name"] for x in c] == ["set_reminder"], f"служебное more_tools — не дело: {[x['name'] for x in c]}")
ok(c[0]["args"]["token"] == "ghp_***" and c[0]["args"]["text"] == "позвонить маме", "аргументы — с ключами под ***")
ok(len(c[0]["result"]) <= AR.HIST_RES + 1 and c[0]["result"].startswith("Поставлено"), "итог — коротко")
ok(len(AR.hist_calls([{"name": f"t{i}", "args": {}, "result": "r"} for i in range(20)])) == AR.HIST_CALLS, "не больше HIST_CALLS вызовов")

# 2) окно: вызовы у последних ответов, у старых — пометка; выключено — как раньше
H = []
for i in range(10):
    H += [{"role": "user", "content": f"вопрос {i}"},
          {"role": "assistant", "content": f"ответ {i}", "who": "lira", "acts": ["web_search"], "facts": [f"web_search(q{i}) → r{i}"],
           "calls": [{"name": "web_search", "args": {"query": f"q{i}"}, "result": f"r{i}"}]}]
w = AR.team_window(H, "lira", lambda p: "Лира", native=True)
a = [m for m in w if m["role"] == "assistant"]
ok("calls" in a[-1] and "выполнено инструментами" not in a[-1]["content"] and "узнано инструментами" not in a[-1]["content"],
   "последний ответ — с вызовами, без текстовых пометок")
ok("calls" not in a[0] and "выполнено инструментами" in a[0]["content"], "старый ответ — прежней пометкой (история не разрастается)")
w0 = AR.team_window(H, "lira", lambda p: "Лира")
ok(not any("calls" in m for m in w0) and "выполнено инструментами" in w0[-1]["content"], "выключено — как раньше")


# 3) _messages: формат по протоколу
class P:
    def get(self, pid): return {"name": "Лира"}


class S:
    def __init__(self, native): self.native = native
    def get(self, *k, default=None):
        return {("llm", "history_turns"): 40, ("llm", "history_reset_seconds"): 28800, ("persona",): "lira",
                ("llm", "history_native"): self.native}.get(tuple(k), default)


class C:
    def expired(self, s): return False
    def window(self, h, n): return h


cls = next(v for v in vars(EA).values() if isinstance(v, type) and "_messages" in vars(v))
eng = type("E", (), {"s": S(True), "conv": C(), "history": H, "personas": P()})()
m = cls._messages(eng, "а что нашла в последний раз?", (), {"model": "chat", "cloud": True})
tc = [x for x in m if x.get("tool_calls")]
ok(tc and m[-1]["role"] == "user" and any(x["role"] == "tool" for x in m), "OpenAI: tool_calls и tool в истории")
i = m.index(tc[-1])
ok(m[i + 1]["role"] == "tool" and m[i + 1]["tool_call_id"] == tc[-1]["tool_calls"][0]["id"] and m[i + 2] == {"role": "assistant", "content": "ответ 9"},
   "порядок: вызов → итог → слова ответа")
ids = [t["id"] for x in tc for t in x["tool_calls"]]
ok(len(ids) == len(set(ids)) and all(len(x) == 9 and x.isalnum() for x in ids), f"id вызовов разные, 9 знаков (шаблон Mistral): {ids[:3]}")
ok(json.loads(tc[-1]["tool_calls"][0]["function"]["arguments"]) == {"query": "q9"}, "аргументы — JSON")
ok(all(set(x) <= {"role", "content", "tool_calls", "tool_call_id"} for x in m), "служебные поля (calls, who) модели не уходят")
import llm  # noqa: E402
flat = llm.flat_messages(m)
ok(not llm._has_tool_history(flat) and any("<tool_call>" in str(x["content"]) for x in flat), "без действий в запросе — текстом (llm.flat_messages)")
ma = cls._messages(eng, "а что нашла?", (), {"model": "claude", "kind": "anthropic"})
ok(not any(x.get("tool_calls") or isinstance(x.get("content"), list) for x in ma) and "выполнено инструментами" in ma[-2]["content"],
   "Claude — пометкой (без описаний действий запрос с вызовами в истории не примут)")
eng0 = type("E", (), {"s": S(False), "conv": C(), "history": H, "personas": P()})()
m0 = cls._messages(eng0, "а что нашла?", (), {"model": "chat", "cloud": True})
ok(not any(x.get("tool_calls") for x in m0) and all(set(x) == {"role", "content"} for x in m0), "выключено — только слова и пометки, как раньше")

# 4) ход пишет вызовы в историю только при включённом переключателе
src = (ROOT / "core/engine_answer.py").read_text(encoding="utf-8")
ok('turn.done_calls = done_calls' in src and 'hist_calls(getattr(turn, "done_calls", None)) if self.s.get("llm", "history_native") is True' in src,
   "_turn_finish: calls — из вызовов хода, только при llm.history_native")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
print("ALL OK" if not fails else "")
sys.exit(1 if fails else 0)
