"""Владелец 14.11: английский урок своим голосом (образец 12 с по-русски) — «ужасающий акцент»; «врядли образец так
влияет на акценты, быстрее всего из него извлекается только эмбеддинг». Извлекался не только отпечаток: модель клонирования
(Qwen Base) получала запись-образец С ЕЁ ТЕКСТОМ и продолжала её — и говорила по-английски с русским произношением.
Теперь, если образец русский, а фраза на другом языке, — только отпечаток голоса (x_vector_only_mode): тембр свой,
произношение — родное для языка. По-русски — как было (с образцом и текстом — похоже точнее)."""
import os, sys, tempfile, wave
from pathlib import Path
import numpy as np
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ.update(TTS_FAKE="1", TTS_DATA=str(tmp / "data"), TTS_MAX_MODELS="2", TTS_PRELOAD="none")
sys.path.insert(0, str(ROOT / "server/voices"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import app as A  # noqa: E402
os.makedirs(A.vdir(), exist_ok=True)
with wave.open(A.vdir("me.wav"), "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(A.OUT_SR)
    w.writeframes((np.sin(np.arange(A.OUT_SR * 3) / 9) * 9000).astype("<i2").tobytes())
calls = []


class FakeQwen:
    def create_voice_clone_prompt(self, ref_audio, ref_text=None, x_vector_only_mode=False):
        calls.append(("prompt", ref_text, x_vector_only_mode)); return [{"x": x_vector_only_mode}]

    def generate_voice_clone(self, text, language, voice_clone_prompt, ref_text=None):
        calls.append(("gen", language[0] if isinstance(language, list) else language, voice_clone_prompt[0]["x"])); n = len(text) if isinstance(text, list) else 1
        return [np.zeros(2400, np.float32)] * n, A.OUT_SR


e = A.Engine()
e.get = lambda role: FakeQwen()
spec = {"kind": "clone", "engine": "qwen", "audio": "me.wav", "text": "Привет, это образец моего голоса"}
e._generate(spec, ["See you in the next lesson!"], A.lang_of("See you in the next lesson!"))
ok(("prompt", None, True) in calls and ("gen", "English", True) in calls, f"английская фраза русским образцом — только отпечаток голоса: {calls}")
calls.clear()
e._generate(spec, ["Увидимся в следующем уроке!"], "Russian")
ok(("prompt", "Привет, это образец моего голоса", False) in calls and ("gen", "Russian", False) in calls, f"по-русски — как было, с образцом и текстом: {calls}")
calls.clear()
e._generate(dict(spec, text="Hello, this is my English sample"), ["See you!"], "English")
ok(("gen", "English", False) in calls, "образец английский — полный образец (свой язык)")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
