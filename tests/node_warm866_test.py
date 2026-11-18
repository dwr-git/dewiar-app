"""№866 (18.11, Merzava: Ollama на сервере в сети с несколькими моделями — «Подходит ли мой компьютер: Скорость — модель
не ответила: timed out», хотя в чате та же Ollama отвечает). Первый вопрос замера ждал, пока Ollama выгрузит одну модель
и загрузит другую (27B — дольше 30 с). Теперь:
— замер берёт модель, которой Лира уже думает (она в памяти), если она на этом сервере;
— первый вопрос ждёт загрузку (LOAD_WAIT), а долгий первый ответ перемеряется вторым вопросом — скорость уже загруженной;
— таймаут объясняется словами, а не «timed out»."""
import json, os, sys, tempfile, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ["DEWIAR_STATE_DIR"] = str(tmp / "st"); os.environ["DEWIAR_CONFIG_DIR"] = str(tmp / "cfg")
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import liranode as N  # noqa: E402
import llm  # noqa: E402

ANS = json.dumps({"choices": [{"message": {"content": "Небо голубое из-за рассеяния света."}}], "usage": {"completion_tokens": 12}})
clock = [0.0]
N.time = types.SimpleNamespace(monotonic=lambda: clock[0], time=lambda: 0.0, sleep=lambda s: None)
calls = []


def ask(base, model, body, timeout, key=""):
    calls.append((model, timeout))
    clock[0] += 40.0 if len(calls) == 1 else 1.5      # первый — с загрузкой модели, второй — уже из памяти
    return 200, ANS


N.ask_model = ask
r = N.speed_test("http://192.168.2.44:11434/v1", "qwen3.5:9b")
ok(r["ok"] and r["s"] == 1.5 and len(calls) == 2, f"долгий первый ответ (загрузка) — перемерено вторым вопросом: {r}, {calls}")
ok(calls[0][1] >= N.LOAD_WAIT and calls[1][1] == 30, f"первый вопрос ждёт загрузку модели, второй — обычный срок: {calls}")

calls.clear()
N.ask_model = lambda *a, **k: (calls.append(1), clock.__setitem__(0, clock[0] + 2.0), (200, ANS))[2]
r = N.speed_test("http://192.168.2.44:11434/v1", "qwen3.5:9b")
ok(r["ok"] and len(calls) == 1, f"быстрый первый ответ — одного вопроса хватает: {r}")

N.ask_model = lambda *a, **k: (0, "своя модель не ответила: timed out")
r = N.speed_test("http://192.168.2.44:11434/v1", "qwen3.8:27b")
ok(not r["ok"] and "timed out" not in r["error"] and "не ответила за" in r["error"], f"таймаут — словами: {r['error']}")

# «Подходит ли мой компьютер»: модель — та, которой Лира уже думает, а не первая в списке сервера
llm.discover_local = lambda start=False: []
llm._models_at = lambda b, t=1.5, key="", known="": ["gemma4:26b", "qwen3.8:27b", "qwen3.5:9b"] if "192.168.2.44" in b else None
prof = {"p1": {"name": "Сервер — qwen3.5:9b", "kind": "openai", "base_url": "http://192.168.2.44:11434/v1", "model": "qwen3.5:9b"}}
sett = {("llm", "profiles"): prof, ("llm", "active"): "p1"}
eng = types.SimpleNamespace(s=types.SimpleNamespace(get=lambda a, b=None: sett.get((a, b))), cloud=types.SimpleNamespace(key="k", url="u"))
nd = N.Node.__new__(N.Node)
nd.e = eng
nd.rules = lambda: ({"on": True, "app": {"max_answer_s": 6}}, "")
picked = []
N.speed_test = lambda base, model, timeout=30, key="": (picked.append(model), {"ok": True, "s": 1.0, "tps": 30, "cyr": True})[1]
N.SYS = types.SimpleNamespace(gpu=lambda fresh=False: None, on_battery=lambda: False)
res = nd.check()
ok(res["pick"] and res["pick"]["model"] == "qwen3.5:9b" and picked == ["qwen3.5:9b"],
   f"замер — модель из «Мозга» (уже в памяти), не gemma4:26b первой в списке: {res['pick']}")
sett[("llm", "active")] = "нет"
res = nd.check()
ok(res["pick"] and res["pick"]["model"] in ("gemma4:26b", "qwen3.8:27b", "qwen3.5:9b"), "мозг не на этом сервере — выбор как раньше")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
