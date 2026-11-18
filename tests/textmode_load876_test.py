"""№876 (18.11): «на компьютере нет микрофона и не планируется, а при включении и обновлении приложение очень долго ищет
микрофон и подготавливает транскрибацию — нужна настройка». Настройка есть — «Текстовый режим» (студия → «Чат»): теперь в
нём точное распознавание (GigaAM, до 100 с при первом запуске) не загружается совсем, а выключили режим — загрузится тогда.
И подсказка «Микрофон молчит» без настоящего микрофона сама предлагает «Текстовый режим»."""
import os, sys, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core")); sys.path.insert(0, str(ROOT / "tests"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import ears_models as EM  # noqa: E402
import srctext  # noqa: E402

loads = []


class G(EM.GigaAMSTT):
    def __init__(self): self._r, self.model_name = False, "gigaam"
    ready = property(lambda self: self._r)
    def cached(self): return True
    def load(self, on_progress=None): loads.append(1); self._r = True; return True


class S:
    def __init__(self, tm): self.tm = tm
    def get(self, a, b=None):
        return {"ui": {"text_mode": self.tm}, "tts": {"engine": "off"}}.get(a, {}).get(b) if b else {}


def eng(tm):
    e = types.SimpleNamespace(s=S(tm), stt=G(), status={}, notes=[])
    for n in ("_names_note", "ensure_voice", "health_mark", "_load", "_loaded", "_dl"):
        setattr(e, n, lambda *a, **k: None)
    e.note = lambda t: e.notes.append(t)
    e._mirror = lambda *a: None
    return e


e = eng(True)
EM.ModelsMixin._background_loads(e)
ok(not loads and not e.stt.ready, "текстовый режим — распознавание не загружается совсем")
e = eng(False)
EM.ModelsMixin._background_loads(e)
ok(loads and e.stt.ready, "обычный режим — как было, загружается")
src = srctext.text(ROOT, "core/commands_talk.py")
ok('if not getattr(self.stt, "ready", True):' in src and "target=self._background_loads" in src, "выключили текстовый режим — распознавание загрузится тогда")
mic = (ROOT / "core/ears_mic.py").read_text(encoding="utf-8")
ok("Микрофона нет и не будет? Включите «Текстовый режим»" in mic, "«Микрофон молчит» без настоящего микрофона — предлагает «Текстовый режим»")
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
