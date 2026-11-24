"""№940 (21.11, компьютер 1.0.53): «когда падает мой сервер, приложение автоматически перекидывает меня на облако Dewiar…
все галочки страховки сняла, но оно всё равно переключается». Сторож мозга (_ensure_brain) переключал на модели Dewiar
любую молчащую модель. Теперь: своя модель (LM Studio, Ollama, свой сервер) — только с согласия «Если своя модель не
отвечает — через Dewiar»; Dewiar Server дома и сервис по ключу — по «Подстраховке» (выключена — не переключаем);
«модель не выбрана» — чиним всегда."""
import os, sys, tempfile, threading
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


import engine_brain as EB  # noqa: E402
import settings as ST  # noqa: E402
import llm as LLM  # noqa: E402
from cloud import PROFILE_ID  # noqa: E402

def dead(prof, timeout=4):
    raise LLM.LLMError("нет связи")


class Acc:
    def logged_in(self):
        return False


def run(active, prof, **llm):
    s = ST.Settings(tmp / f"s{len(llm)}{active}.json")
    s.update({"cloud": {"key": "dw-test"}, "llm": dict({"active": active, "profiles": {active: prof, PROFILE_ID: {"name": "Dewiar", "cloud": True,
              "base_url": "https://dewiar.pro/dwrapp/cloud.php/v1", "model": "chat"}}}, **llm)})
    cls = next(c for c in vars(EB).values() if isinstance(c, type) and hasattr(c, "_ensure_brain"))
    e = cls.__new__(cls)
    e.s, e.account, e._brain_lock, e.stopping = s, Acc(), threading.Lock(), threading.Event()
    e.emit = lambda *a, **k: None; e.note = lambda *a, **k: None; e.push = lambda *a, **k: None
    e._brain_flap = lambda *a, **k: None; e.cloud = None
    for k in ("_stt_cloud_fallback", "_speech_fallback"):
        setattr(e, k, lambda *a, **kw: None)
    EB.list_models = dead
    try:
        e._ensure_brain("test")
    except Exception as x:  # noqa: BLE001 — дальше переключения (речь, сеть) нам не нужно
        print("  (дальше:", type(x).__name__, str(x)[:80], ")")
    return s.get("llm", "active")


own = {"name": "LM Studio", "kind": "openai", "base_url": "http://127.0.0.1:1234/v1", "model": "qwen"}
srv = {"name": "Мой сервер", "kind": "openai", "base_url": "http://192.168.1.20:8000/v1", "model": "qwen"}
key = {"name": "Kimi", "kind": "openai", "base_url": "https://api.moonshot.ai/v1", "api_key": "k", "model": "kimi"}
home = {"name": "Dewiar Server — домашняя сеть", "kind": "openai", "base_url": "http://192.168.1.46:9099/v1", "model": "chat"}
ok(run("own", own) == "own", "своя модель молчит, согласия нет — в облако не переключаемся")
ok(run("srv", srv) == "srv", "свой сервер молчит, согласия нет — тоже нет (№940)")
ok(run("own", own, own_fallback=True) == PROFILE_ID, "согласие «если своя модель не отвечает — через Dewiar» — переключаемся")
ok(run("key", key, key_fallback=False) == "key", "сервис по ключу, «Подстраховка» выключена — не переключаемся")
ok(run("dewiar-home", home, key_fallback=False) == "dewiar-home", "Dewiar Server дома, «Подстраховка» выключена — не переключаемся")
ok(run("dewiar-home", home) == PROFILE_ID, "Dewiar Server дома, «Подстраховка» как по умолчанию — переключаемся, как раньше")
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
