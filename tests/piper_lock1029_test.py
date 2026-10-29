"""Отчёт №400 (29.10, Windows): ядро падало «access violation» в piper/phonemize_espeak — eSpeak не переносит двух фраз
одновременно (ответ, заготовка следующей фразы, напоминание из других потоков). Синтез Piper — строго по очереди."""
import sys, threading, time, types
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))
import tts  # noqa: E402

inside, worst = [0], [0]
lk = threading.Lock()


class FakeVoice:
    def synthesize(self, text, syn_config=None):
        with lk:
            inside[0] += 1; worst[0] = max(worst[0], inside[0])
        time.sleep(0.05)                                   # «фонемы» — пока тут сидит один, второму нельзя
        with lk:
            inside[0] -= 1
        yield types.SimpleNamespace(sample_rate=22050, audio_int16_bytes=b"\0\0" * 10)


sys.modules["piper"] = types.SimpleNamespace(SynthesisConfig=lambda **k: k, PiperVoice=None)
p = tts.PiperTTS()
p._voice = lambda vid: FakeVoice()
out = []
ts = [threading.Thread(target=lambda i=i: out.append(list(p.synth(f"фраза {i}", {}, norm=False)))) for i in range(6)]
[t.start() for t in ts]; [t.join() for t in ts]
ok = worst[0] == 1 and len(out) == 6 and all(o and o[0][0] == 22050 for o in out)
print(("✅ " if ok else "❌ ") + f"шесть фраз из разных потоков — Piper синтезирует по одной (одновременно: {worst[0]})")
sys.exit(0 if ok else 1)
