"""№1132 (27.11, Windows 11, Logitech C525): «не могу добиться использования Лирой микрофона веб-камеры, при этом Chrome
слышит». В журнале каждые 10 минут: MME не открывает микрофон с 16 кГц («MME error 11» — неверный параметр), и
«по умолчанию» — он же. Chrome слушает через WASAPI в родном формате устройства. Теперь так же: MME не открыл — тот же
микрофон через WASAPI (потом DirectSound) на его частоте и каналах, к 16 кГц моно приводим сами. Проверка без Windows:
подменённый sounddevice; и что перевод частоты не искажает речь (тон 440 Гц остаётся 440 Гц той же громкости)."""
import os, sys, types
import numpy as np
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
os.environ["DEWIAR_AUDIO_BACKEND"] = "sounddevice"
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    c or fails.append(m)


opened = []
PAE = type("PortAudioError", (Exception,), {})
DEVS = [{"name": "Переназначение звуковых устр. - Input", "hostapi": 0, "max_input_channels": 2, "max_output_channels": 0, "default_samplerate": 44100},
        {"name": "Микрофон (Logi C525 HD WebCam)", "hostapi": 0, "max_input_channels": 1, "max_output_channels": 0, "default_samplerate": 44100},
        {"name": "Микрофон (Logi C525 HD WebCam)", "hostapi": 1, "max_input_channels": 2, "max_output_channels": 0, "default_samplerate": 48000},
        {"name": "Микрофон (Logi C525 HD WebCam)", "hostapi": 2, "max_input_channels": 2, "max_output_channels": 0, "default_samplerate": 48000}]
APIS = [{"name": "MME", "default_input_device": 0}, {"name": "Windows DirectSound", "default_input_device": 2},
        {"name": "Windows WASAPI", "default_input_device": 3}]


class Stream:
    def __init__(self, **k):
        d = DEVS[k["device"]] if k.get("device") is not None else DEVS[0]
        if d["hostapi"] == 0 or (d["hostapi"] == 2 and k["channels"] == 1):   # MME — «неверный параметр»; WASAPI — только 2 канала
            raise PAE("Error opening RawInputStream: Unanticipated host error [PaErrorCode -9999] [MME error 11]")
        self.k = k
        opened.append((k["device"], k["samplerate"], k["channels"]))

    def start(self): pass
    def stop(self): pass
    def close(self): pass


sd = types.ModuleType("sounddevice")
sd.RawInputStream, sd.PortAudioError = Stream, PAE
sd._terminate = sd._initialize = lambda: None
sd.default = types.SimpleNamespace(device=[0, 0])
sd.query_devices = lambda *a: DEVS[a[0]] if a else DEVS
sd.query_hostapis = lambda: APIS
sys.modules["sounddevice"] = sd
import audio_io  # noqa: E402

cap = audio_io.Capture(device="Микрофон (Logi C525 HD WebCam)")
label = cap.open()
ok(opened == [(3, 48000, 2)] and "WASAPI" in label, f"MME не открыл C525 — тот же микрофон через WASAPI, 48 кГц, 2 канала: {opened} · {label}")
# кадры с микрофона: 48 кГц стерео, тон 440 Гц → в очередь — 16 кГц моно по 512 сэмплов
t = np.arange(48000) / 48000.0
x = (8000 * np.sin(2 * np.pi * 440 * t)).astype(np.int16)
st = np.stack([x, x], 1).reshape(-1)
for i in range(0, len(st), 960):                          # кусками по 10 мс, как WASAPI
    cap.stream.k["callback"](st[i:i + 960].tobytes(), 480, None, None)
out = b""
while not cap._sd_q.empty():
    c = cap._sd_q.get_nowait()
    ok(len(c) == 1024, "кусок — ровно 512 сэмплов") if not out else None
    out += c
y = np.frombuffer(out, np.int16).astype(np.float32)
f = np.argmax(np.abs(np.fft.rfft(y[2000:2000 + 8192]))) * 16000 / 8192
ok(15800 <= len(y) <= 16000, f"секунда звука — 16 000 сэмплов (±1 кусок): {len(y)}")
ok(abs(f - 440) < 4, f"тон остался 440 Гц: {f:.0f}")
amp = np.sqrt(np.mean(y[2000:14000] ** 2)) * np.sqrt(2)
ok(7000 < amp < 8100, f"громкость та же (≈8000): {amp:.0f}")
# 44,1 кГц моно — дробный шаг между кусками
rs = audio_io._Resample(44100, 1)
t = np.arange(44100 * 2) / 44100.0
x = (6000 * np.sin(2 * np.pi * 300 * t)).astype(np.int16).tobytes()
y = b"".join(c for i in range(0, len(x), 882) for c in rs.feed(x[i:i + 882]))
y = np.frombuffer(y, np.int16).astype(np.float32)
f = np.argmax(np.abs(np.fft.rfft(y[1000:1000 + 16384]))) * 16000 / 16384
ok(31700 <= len(y) <= 32000 and abs(f - 300) < 3, f"44,1 кГц → 16 кГц: {len(y)} сэмплов за 2 с, тон {f:.0f} Гц")
# «по умолчанию» и MME не открыл — WASAPI по умолчанию
opened.clear()
cap2 = audio_io.Capture(device="")
label = cap2.open()
ok(opened == [(3, 48000, 2)], f"«по умолчанию»: MME не открыл — микрофон WASAPI по умолчанию: {opened} · {label}")
# нигде не открылся — ошибка, как раньше (окно скажет «микрофон недоступен»)
Stream.__init__ = lambda self, **k: (_ for _ in ()).throw(PAE("host error"))
try:
    audio_io.Capture(device="Микрофон (Logi C525 HD WebCam)").open()
    ok(False, "нигде не открылся — должна быть ошибка")
except PAE:
    ok(True, "нигде не открылся — ошибка, как раньше")
print("ИТОГ: " + ("всё прошло" if not fails else f"провалов {len(fails)}"))
sys.exit(1 if fails else 0)
