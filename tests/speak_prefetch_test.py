"""Голос без пауз между фразами (engine_remote._speak_worker): пока звучит фраза, следующая уже синтезируется.
Медленный синтез (0,8 с на фразу) и звук в реальном времени (1 с на фразу): три фразы — около 3,8 с, а не 5,4,
как было, когда синтез ждал конца звучания. Отмена посреди ответа останавливает и звук, и синтез."""
import os
import queue
import sys
import threading
import time
import types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
import engine as E  # noqa: E402
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


class SlowTTS:
    name = "slow"

    def __init__(self):
        self.started = []

    def synth(self, text, voice, speed=1.0):
        self.started.append((time.monotonic(), text))
        time.sleep(0.8)
        yield 16000, b"\x10\x00" * 16000                  # секунда звука


class RealtimePlayer:
    rate = 16000

    def __init__(self):
        self.play = []

    def start(self, r):
        self.rate = r

    def write(self, b):
        self.play.append(time.monotonic())
        time.sleep(len(b) / 2 / self.rate)
        return True

    def finish(self):
        pass


def run(sentences, cancel_after=None):
    tts, pl = SlowTTS(), RealtimePlayer()
    me = types.SimpleNamespace(s=types.SimpleNamespace(get=lambda *k: {"speed": 1.0}.get(k[-1])), _voice_cfg=lambda: {}, _output_muted=lambda: False,
                               _fx_name=lambda v: "off", player=pl, set_state=lambda s: None, _engines_for_speech=lambda v, *a: [tts], _synth_mixed=lambda eng, text, voice, sp: eng.synth(text, voice, sp),
                               _wait_vosk_tts=lambda v: None, last_speak_end=0, vosk_tts=None, _said=[], null_player=True)
    turn = types.SimpleNamespace(cancel=threading.Event(), spoken=[])
    q = queue.Queue()
    for s in sentences:
        q.put(s)
    q.put(None)
    if cancel_after:
        threading.Timer(cancel_after, turn.cancel.set).start()
    t0 = time.monotonic()
    E.Engine._speak_worker(me, turn, q)
    return time.monotonic() - t0, tts, turn


took, tts, turn = run(["Первая фраза.", "Вторая фраза.", "Третья фраза."])
ok(len(turn.spoken) == 3, f"все три фразы сказаны: {turn.spoken}")
ok(took < 4.6, f"синтез следующей фразы — пока звучит текущая: {took:.1f} с (без опережения было бы ~5,4)")
gap = tts.started[1][0] - tts.started[0][0]
ok(gap < 1.2, f"вторая фраза начала синтезироваться через {gap:.1f} с — во время звучания первой")
took2, tts2, turn2 = run(["Раз.", "Два.", "Три.", "Четыре.", "Пять."], cancel_after=1.5)
time.sleep(1.0)
ok(took2 < 2.6 and len(tts2.started) <= 3, f"перебили — звук и синтез остановились: {took2:.1f} с, синтезов {len(tts2.started)}")
print("\nИТОГ:", "всё хорошо" if not fails else f"ошибок {len(fails)}")
sys.exit(1 if fails else 0)
