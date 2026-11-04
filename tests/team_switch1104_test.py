"""№515 (пакет 04.11, компьютер 0.80.0): «нужно научить модели Джарвис, Кодер, Лира понимать, что они переходят от одной
модели к другой». У каждого персонажа свой разговор (23.10) — чужой в окно модели не попадал вовсе, и Кодер не знал,
что до него говорила Лира («Кодер и Лира, вы работаете сообща?»). Теперь на месте чужого разговора — пометка «до этого
пользователь говорил с коллегой — Лира; дальше отвечаешь ты — Кодер» (без самого разговора), а смена модели у персонажа
— пометка «до этого отвечала модель A, дальше — B». Модель ответа хранится в истории и переживает перезапуск."""
import json, os, sys, tempfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
tmp = Path(tempfile.mkdtemp())
os.environ.update(DEWIAR_CONFIG_DIR=str(tmp / "cfg"), DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_WORKSPACE=str(tmp / "ws"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import engine_answer as EA  # noqa: E402
NAMES = {"lira": "Лира", "coder": "Кодер", "jarvis": "Джарвис"}
H = [{"role": "user", "content": "Лира, привет"}, {"role": "assistant", "content": "Привет! Чем займёмся?", "who": "lira", "model": "gemma4:12b"},
     {"role": "user", "content": "Кодер, помоги с сервером"}, {"role": "assistant", "content": "Покажи конфиг nginx.", "who": "coder", "model": "qwen2.5-coder:14b"},
     {"role": "user", "content": "Вот он"}, {"role": "assistant", "content": "Порт 9000 занят — смени на 9001.", "who": "coder", "model": "qwen2.5-coder:14b"},
     {"role": "user", "content": "Джарвис, проверь папку"}, {"role": "assistant", "content": "Папка проверена: 120 файлов.", "who": "jarvis", "model": "gemma4:12b"}]

# 1) Кодер: его разговор + пометки, кто говорил до и после
w = EA.team_window(H, "coder", NAMES.get, model="qwen2.5-coder:14b")
marks = [m["content"] for m in w if m.get("team")]
ok(len(marks) == 2, f"две пометки о коллегах (Лира до, Джарвис после): {len(marks)}")
ok("с коллегой — Лира (1 реплика)" in marks[0] and "дальше отвечаешь ты — Кодер" in marks[0], "до Кодера говорила Лира — Кодер это знает")
ok("с коллегой — Джарвис" in marks[1] and "дальше отвечаешь ты — Кодер" in marks[1], "после — Джарвис, а теперь снова Кодер")
ok(not any("Чем займёмся" in m["content"] or "120 файлов" in m["content"] for m in w), "чужих ответов в окне нет (решение 23.10 в силе)")
ok(w[-1].get("team"), "последним — пометка о Джарвисе: вопрос дальше явно к Кодеру")

# 2) _messages: пометка и «[Теперь пользователь обращается к тебе:]» — в одном сообщении с вопросом
class P:
    def get(self, pid): return {"name": NAMES.get(pid, "Коллега")}


class S:
    def __init__(self, me): self.me = me
    def get(self, *k, default=None): return {("llm", "history_turns"): 20, ("llm", "history_reset_seconds"): 28800, ("persona",): self.me}.get(tuple(k), default)


class C:
    def expired(self, s): return False
    def window(self, h, n): return h


eng = type("E", (), {"s": S("coder"), "conv": C(), "history": H, "personas": P()})()
cls = next(v for v in vars(EA).values() if isinstance(v, type) and "_messages" in vars(v))
msgs = cls._messages(eng, "Кодер и Лира, вы работаете сообща?", (), {"model": "qwen2.5-coder:14b"})
last = msgs[-1]["content"]
ok("Джарвис" in last and "[Теперь пользователь обращается к тебе:]\nКодер и Лира, вы работаете сообща?" in last, "вопрос — после пометки, явно Кодеру")
ok(all(set(m) == {"role", "content"} for m in msgs) and all(a["role"] != b["role"] or a["role"] == "assistant" for a, b in zip(msgs, msgs[1:])),
   "служебные поля не уходят модели, роли чередуются")

# 3) смена модели у того же персонажа
H2 = [{"role": "user", "content": "Лира, привет"}, {"role": "assistant", "content": "Привет!", "who": "lira", "model": "gemma4:12b"},
      {"role": "user", "content": "Как дела?"}, {"role": "assistant", "content": "Отлично.", "who": "lira", "model": "gemma4:12b"}]
w = EA.team_window(H2, "lira", NAMES.get, model="DWR Chat Qwen")
ok(w[-1].get("mark") and "до этого отвечала «gemma4:12b», дальше — «DWR Chat Qwen»" in w[-1]["content"] and "тот же разговор с тобой, Лира" in w[-1]["content"],
   "сменили мозг Лиры — пометка «до этого модель gemma, дальше — новая»")
ok(not any(m.get("mark") for m in EA.team_window(H2, "lira", NAMES.get, model="gemma4:12b")), "модель та же — пометки нет")
H3 = H2 + [{"role": "user", "content": "А теперь?"}, {"role": "assistant", "content": "Тоже хорошо.", "who": "lira", "model": "DWR Chat Qwen"}]
w = EA.team_window(H3, "lira", NAMES.get, model="DWR Chat Qwen")
k = next(i for i, m in enumerate(w) if m.get("mark"))
ok(w[k - 1]["content"] == "Отлично." and w[k + 1]["content"] == "А теперь?" and w[k + 2]["content"] == "Тоже хорошо." and sum(1 for m in w if m.get("mark")) == 1,
   "смена посреди истории — пометка ровно на месте смены")
ok(not any(m.get("mark") for m in EA.team_window([{"role": "user", "content": "x"}, {"role": "assistant", "content": "y", "who": "lira"}], "lira", NAMES.get, model="m")),
   "старая история без модели — без пометок")
ok(EA.model_label({"model": "chat", "title": "DWR Chat Qwen 3.8"}) == "DWR Chat Qwen 3.8" and EA.model_label({"model": "gemma4:12b"}) == "gemma4:12b",
   "имя модели: облачная — по названию, своя — по модели")

# 4) модель ответа — в истории и в conversation.json
src = (ROOT / "core/engine_answer.py").read_text(encoding="utf-8")
ok('turn.model = model_label(prof)' in src and '{"model": turn.model}' in src, "ответ запоминает, какой моделью дан")
ok('model=model_label(prof) if prof else ""' in src, "окно модели знает нынешнюю модель персонажа")
import conversation  # noqa: E402
cv = conversation.Conversation(tmp / "conv.json") if "path" in conversation.Conversation.__init__.__code__.co_varnames else None
if cv is not None:
    cv.save(H)
    saved = json.loads((tmp / "conv.json").read_text(encoding="utf-8"))["history"]
    ok(saved[1].get("model") == "gemma4:12b", "после перезапуска модель ответа не теряется")
else:
    ok('("role", "content", "who", "model")' in (ROOT / "core/conversation.py").read_text(encoding="utf-8"), "conversation.json хранит модель ответа")
pp = (ROOT / "core/personas.py").read_text(encoding="utf-8")
ok("дальше отвечаешь ты]» значит: слово переходило к коллеге" in pp and "разговоры — " in pp, "правило команды объясняет пометку")

# 5) экзамен: новый персонаж знает, кто говорил до него
sc = {s["id"]: s for s in json.loads((ROOT / "data/exam/scenarios.json").read_text(encoding="utf-8"))["scenarios"]}
t = sc.get("team_knows_switch") or {}
ok([s.get("persona") for s in t.get("steps", [])] == ["lira", "patrik"] and "Лир" in t.get("expect", {}).get("any", []),
   "сценарий экзамена «Новый персонаж знает, кто говорил до него»")
print("ИТОГ:", "OK" if not fails else f"{len(fails)} ошибок")
sys.exit(1 if fails else 0)
