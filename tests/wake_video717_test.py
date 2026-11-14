"""№717 (14.11): «смотрю видео на YouTube — он включается, записывает часть голосового от видео, я его останавливаю — он
опять включается». По журналу: «Имя посреди долгого звука (10,7 с)… (16,5 с)» — «агент», «Оскар», «Патрик» звучали в ролике.
Теперь имя посреди сплошной речи дольше 6 с, когда есть точная модель, — не отклик сразу, а проверка (имя должно звучать
обращением в начале фразы). Короче 6 с или без точной модели — как раньше: слушаю с имени."""
import collections, os, queue, sys, threading, time
from pathlib import Path
from types import SimpleNamespace
import numpy as np
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import engine as E  # noqa: E402


def run(sound_s, checker):
    e = E.Engine.__new__(E.Engine)
    e.calls, e.tones = [], []
    e.play_tone = lambda k: e.tones.append(k)
    e.s = SimpleNamespace(get=lambda *k, default=None: {("audio", "end_silence_ms"): 650, ("audio", "barge_in"): "smart"}.get(k, default))
    e.stopping, e.restart_audio, e.muted, e.state = threading.Event(), threading.Event(), False, "idle"
    e.status, e.meeting, e.alarm, e.utt_id, e.wake_time = {"aec": True}, [], None, 7, 0.0
    e._listen_peak = e._listen_vad = 0.0
    e._pending_media_stop, e.check_q, e.stt_q = 0.0, queue.Queue(), queue.Queue()
    e.radio = SimpleNamespace(playing=False)
    e._meeting_ignores = lambda p: False
    e._noisy = lambda: False
    e.wake_checker = lambda: checker
    e._level = lambda *a: None
    e.interrupt = lambda *a, **k: None
    e.emit = lambda *a, **k: None
    e.vosk_wake_check, e._vosk_wake_word = -1, ""
    e.follow_up_until, e.pending_confirm, e._said, e._spoke_until = 0.0, None, collections.deque(maxlen=40), 0.0
    got = []
    e._on_utterance = lambda pcm, t0, now: got.append(len(pcm) / 2 / 16000)
    frames = int(sound_s / E.FRAME_S)
    name_at = frames - int(0.4 / E.FRAME_S)
    total = frames + int(2.0 / E.FRAME_S)
    st = {"i": 0}

    def read():
        i = st["i"]; st["i"] += 1
        if i >= total:
            e.stopping.set()
            return b"\0" * (E.FRAME * 2)
        return (np.random.default_rng(i).normal(0, 2000, E.FRAME)).astype(np.int16).tobytes() if i < frames else b"\0" * (E.FRAME * 2)
    e.capture = SimpleNamespace(read=read)
    e.vad = SimpleNamespace(prob=lambda f: 0.9 if st["i"] <= frames else 0.05, reset=lambda: None)
    e.spotter = SimpleNamespace(feed=lambda f: [("wake", "агент")] if st["i"] == name_at else [], rec=SimpleNamespace(Reset=lambda: None), last_final=None)
    e.set_state = lambda s_: setattr(e, "state", s_)
    e.wav_input = None
    e._mic_ring = collections.deque(maxlen=40)
    e._quiet_until = 0.0
    e.hold = None
    E.Engine._listen(e)
    return e, got


GIGA = SimpleNamespace(name="GigaAM", ready=True)
e, got = run(16.5, GIGA)
ok(e.state == "idle" and e.tones == [] and e.vosk_wake_check not in (-1, None) and e._vosk_wake_word == "агент",
   f"«агент» посреди 16 с речи из видео — не откликаюсь сразу, проверит точная модель: {e.state}, {e.tones}")
ok(got and got[0] < 3.0, f"на проверку — фраза с имени, а не 16 с ролика ({got[0] if got else '—'})")
e, got = run(4.0, GIGA)
ok(e.state == "listening" and e.tones == ["wake"] and e.vosk_wake_check == -1, "имя после 4 с звука (музыка, человек рядом) — слушаю сразу, как раньше")
e, got = run(16.5, None)
ok(e.state == "listening", "нечем проверить (нет точной модели) — как раньше, слушаю с имени")
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
