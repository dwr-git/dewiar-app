"""Персонажи не отвечают друг за друга (отзыв 13.10: «обсудила задачу с Патриком, переключилась на Лиру — а она мне
про задачу Патрика»). core/engine_answer.team_window: разговор с коллегой — одной справкой «это их разговор, не
продолжай его», свой — дословно; перед вопросом после чужого разговора — «[Теперь пользователь обращается к тебе:]»."""
import os, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


from engine_answer import team_window  # noqa: E402
NAMES = {"lira": "Лира", "patrik": "Патрик"}
H = [{"role": "user", "content": "Лира, привет"}, {"role": "assistant", "content": "Привет!", "who": "lira"},
     {"role": "user", "content": "Патрик, давай обсудим ремонт ванной"}, {"role": "assistant", "content": "План: плитка, сантехника.", "who": "patrik"},
     {"role": "user", "content": "Отлично, завтра начнём"}, {"role": "assistant", "content": "Всё записано, завтра начнём.", "who": "patrik"}]
w = team_window(H, "lira", NAMES.get)
# 23.10 (письмо пользователя): у каждого персонажа свой разговор — чужой в окно не попадает вовсе;
# №515 (04.11): но что слово переходило к коллеге — пометкой «до этого — Патрик, дальше — ты»
ok([m["role"] for m in w] == ["user", "assistant", "user"] and w[0]["content"] == "Лира, привет" and w[1]["content"] == "Привет!",
   f"у Лиры — её разговор и пометка о Патрике: {[m['content'][:20] for m in w]}")
ok(w[2].get("team") and "с коллегой — Патрик (2 реплики)" in w[2]["content"] and "дальше отвечаешь ты — Лира" in w[2]["content"]
   and "ремонт" not in w[2]["content"] and "плитка" not in w[2]["content"], "№515: пометка — кто говорил и кто дальше, без чужого разговора")
w2 = team_window(H, "patrik", NAMES.get)
ok([m["role"] for m in w2] == ["user", "user", "assistant", "user", "assistant"] and w2[0].get("team") and "коллегой — Лира (1 реплика)" in w2[0]["content"]
   and "дальше отвечаешь ты — Патрик" in w2[0]["content"] and "привет" not in w2[0]["content"].lower(), "у Патрика — его разговор, а перед ним пометка о Лире")
H2 = H[:-1] + [dict(H[-1], handoff="lira")]
w3 = team_window(H2, "lira", NAMES.get)
ok(w3[-1].get("team") and "передал(а) слово тебе" in w3[-1]["content"] and "Патрик: План: плитка" in w3[-1]["content"],
   "Патрик сам передал слово Лире («позови Лиру») — его разговор справкой")
ok(team_window([{"role": "user", "content": "Как дела?"}], "lira", NAMES.get) == [{"role": "user", "content": "Как дела?"}], "без ответа — реплика нынешнего")


class P:
    def get(self, pid): return {"name": NAMES.get(pid, "Коллега")}


class S:
    def get(self, *k, default=None): return {("llm", "history_turns"): 20, ("llm", "history_reset_seconds"): 28800, ("persona",): "lira"}.get(tuple(k), default)


class C:
    def expired(self, s): return False
    def window(self, h, n): return h


import engine_answer as EA  # noqa: E402
eng = type("E", (), {"s": S(), "conv": C(), "history": H, "personas": P()})()
cls = next(v for v in vars(EA).values() if isinstance(v, type) and "_messages" in vars(v))
msgs = cls._messages(eng, "Помоги с поздравлением маме")
ok(msgs[-1]["role"] == "user" and msgs[-1]["content"].endswith("[Теперь пользователь обращается к тебе:]\nПомоги с поздравлением маме")
   and "Патрик" in msgs[-1]["content"] and not any("ремонт" in str(m["content"]) for m in msgs),
   f"Лира не видит разговора о ремонте с Патриком, но знает, что говорил он: {[str(m['content'])[:30] for m in msgs]}")
eng.history = H2
msgs = cls._messages(eng, "Что думаешь?") if "cls" in dir() else EA.AnswerMixin._messages(eng, "Что думаешь?")
ok("[Теперь пользователь обращается к тебе:]" in msgs[-1]["content"], "после передачи слова — вопрос явно к Лире")
src = (ROOT / "core/engine_commands.py").read_text(encoding="utf-8")
ok('m["who"] = a["id"] + "~удалён"' in src, "удалили персонажа — его разговор в архив, новый с тем же именем начнёт с чистого листа")
pp = (ROOT / "core/personas.py").read_text(encoding="utf-8")
app = (ROOT / "android/assets/www/app.js").read_text(encoding="utf-8")
ok("не продолжай его и не отвечай за коллегу" in pp and "не продолжай его и не отвечай за коллегу" in app, "правило команды — в подсказке на компьютере и телефоне")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
