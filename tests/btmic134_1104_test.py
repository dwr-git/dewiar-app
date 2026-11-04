"""Идея №134 (04.11): «Bluetooth-гарнитура. В студии „Звук и поведение“ выбрано „Системный по умолчанию“, но при повторном
подключении гарнитуры Dewiar не слышит, пока не поменяешь в настройках на „другой“ микрофон, а потом обратно».
Причина: PortAudio помнит список устройств с запуска, а поток слуха оставался на прежнем микрофоне — Windows сделала главной
гарнитуру, а Dewiar об этом не знал. Теперь: (1) «по умолчанию» открывается, каждый раз перечитав список устройств;
(2) раз в 3 с слух сверяет, какой микрофон Windows сейчас главный и сколько их (winmm, без COM), — сменился — переоткрывает
слух на новом (только в покое). Проверка — без Windows: DEWIAR_FAKE_DEFMIC и подменённый sounddevice."""
import os, sys, threading, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
os.environ["DEWIAR_AUDIO_BACKEND"] = "sounddevice"
os.environ["DEWIAR_FAKE_DEFMIC"] = "2|Микрофон (Realtek)"
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


log = {"init": 0, "opened": []}


class Stream:
    def __init__(self, **k):
        log["opened"].append(k.get("device"))

    def start(self): pass
    def stop(self): pass
    def close(self): pass


sd = types.ModuleType("sounddevice")
sd.RawInputStream = Stream
sd.PortAudioError = type("PortAudioError", (Exception,), {})
sd._terminate = lambda: None
sd._initialize = lambda: log.__setitem__("init", log["init"] + 1)
sd.default = types.SimpleNamespace(device=[0, 0])
sd.query_devices = lambda *a: [{"name": "Микрофон (Realtek)", "hostapi": 0, "max_input_channels": 1, "max_output_channels": 0}]
sys.modules["sounddevice"] = sd

import audio_io  # noqa: E402

ok(audio_io.win_default_input() == (2, "Микрофон (Realtek)"), "отпечаток микрофона по умолчанию: сколько их и какой главный")
cap = audio_io.Capture(device="")
cap.open()
ok(log["init"] == 1 and log["opened"] == [None], "«Системный по умолчанию»: перед открытием список устройств перечитан")
ok(cap.def_sig == (2, "Микрофон (Realtek)"), "запомнили, какой микрофон был главным при открытии")
cap.close()
cap2 = audio_io.Capture(device="Микрофон (Realtek)")
cap2.open(); cap2.close()
ok(log["init"] == 1 and cap2.def_sig is None, "выбран конкретный микрофон — список не перечитываем и не следим")

import engine_audio  # noqa: E402

eng = types.SimpleNamespace(capture=cap, state="idle", hold=None)
moved = lambda: engine_audio.AudioMixin._default_mic_moved(eng)
ok(not moved(), "ничего не менялось — слух не трогаем")
os.environ["DEWIAR_FAKE_DEFMIC"] = "3|Headset (Sony WH-1000XM4)"      # гарнитуру подключили — Windows сделала её главной
eng.state = "speaking"
ok(not moved(), "сменилось посреди ответа — ответ не обрываем, ждём покоя")
eng.state = "idle"
ok(moved() and cap.def_sig[1] == "Headset (Sony WH-1000XM4)", "в покое — переоткрыть слух на гарнитуре")
ok(not moved(), "и один раз, а не каждые 3 с")
os.environ["DEWIAR_FAKE_DEFMIC"] = "2|Микрофон (Realtek)"            # гарнитуру выключили
ok(moved(), "гарнитуру выключили — обратно на встроенный")
eng.capture = cap2
os.environ["DEWIAR_FAKE_DEFMIC"] = "3|Headset (Sony WH-1000XM4)"
ok(not moved(), "выбран конкретный микрофон — смена главного в Windows его не трогает")

src = (ROOT / "core/engine_audio.py").read_text(encoding="utf-8")
lst = src[src.index("    def _listen(self):"):]
ok("self._default_mic_moved()" in lst[:4000] and "self.restart_audio.set()" in lst[lst.index("self._default_mic_moved()"):][:200],
   "в цикле слуха: сменился главный микрофон — restart_audio (переоткрытие без «Микрофон недоступен»)")
print("ALL OK" if not fails else f"FAILS: {len(fails)}")
sys.exit(1 if fails else 0)
