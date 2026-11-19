"""«Перебивать без наушников (проба)» (19.11, владелец: «нельзя перебивать Лиру — разговор по очереди… готов протестировать,
пока под флагом»). В Windows и на Mac нет системного эхоподавления — свой голос вычитаем сами (soft_aec, WebRTC APM):
Player отдаёт, что и когда зазвучит, слух получает микрофон без своего голоса. Проверка на смоделированной комнате:
эхо из колонок гасится, живой голос остаётся; пока ассистент молчит — микрофон как есть; без флага и без библиотеки —
всё как раньше."""
import os
import sys
import wave
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


import soft_aec  # noqa: E402
import audio_io  # noqa: E402


def load(name, rate):
    with wave.open(str(ROOT / "data/sounds" / name), "rb") as w:
        a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32)
        if w.getnchannels() > 1:
            a = a.reshape(-1, w.getnchannels()).mean(axis=1)
        sr = w.getframerate()
    return np.interp(np.linspace(0, len(a) - 1, int(len(a) * rate / sr)), np.arange(len(a)), a)


rms = lambda x: float(np.sqrt(np.mean(np.square(x))) + 1e-9)  # noqa: E731
FR = audio_io.FRAME

if soft_aec.available():
    R = 16000
    far22 = load("alarm_noon.wav", 22050)[: int(22050 * 6)] * 0.6
    far16 = soft_aec._to16k(np.clip(far22, -32768, 32767).astype(np.int16).tobytes(), 22050, 1)
    n = len(far16)
    rng = np.random.default_rng(1)
    ir = rng.normal(0, 1, int(0.15 * R)) * np.exp(-np.arange(int(0.15 * R)) / (0.03 * R)); ir /= np.abs(ir).sum() * 0.8
    d = int(float(os.environ.get("AEC_D", "0.045")) * R)   # колонки → микрофон: 45 мс и отражения комнаты
    echo = np.zeros(n); echo[d:] = np.convolve(far16, ir)[: n - d]
    near = np.zeros(n); voice = load("alarm_sparks.wav", R); s0 = int(4 * R)
    near[s0:] = voice[: n - s0]
    near *= 3000 / rms(near[s0:]); echo *= 3000 / rms(echo[d:s0])      # колонки громко: эхо в микрофоне — как живой голос
    mic = np.clip(echo + near + rng.normal(0, 60, n), -32768, 32767)
    T0 = 1000.0
    sa = soft_aec.SoftAEC()
    step = int(22050 * 0.04)                              # как Player.write — куски по 40 мс, с моментом звучания,
    fi, out = 0, []                                       # не дальше чем на 0,25 с вперёд (Player.AHEAD)
    for k in range(0, n - FR, FR):
        now = T0 + (k + FR) / R
        while fi < len(far22) and T0 + fi / 22050 <= now + audio_io.Player.AHEAD:
            sa.far(np.clip(far22[fi:fi + step], -32768, 32767).astype(np.int16).tobytes(), 22050, 1, T0 + fi / 22050)
            fi += step
        out.append(np.frombuffer(sa.near(mic[k:k + FR].astype(np.int16).tobytes(), now=now), dtype=np.int16))
    out = np.concatenate(out).astype(np.float32)
    a, b = int(1.5 * R), int(3.8 * R)
    erle = 20 * np.log10(rms(mic[a:b]) / rms(out[a:b]))
    ok(erle > 15, f"эхо своего голоса из колонок гасится: {erle:.0f} дБ")
    seg = slice(int(4.3 * R), min(len(out), int(5.8 * R)))
    before = 20 * np.log10(rms(near[seg]) / rms(mic[a:b]))
    after = 20 * np.log10(rms(out[seg]) / rms(out[a:b]))
    ok(after > before + 15 and after > 10, f"живой голос поверх ответа слышен: голос/эхо {before:.0f} → {after:.0f} дБ")
    ok(rms(out[seg]) > 0.4 * rms(near[seg]), "живой голос не съеден")
    # ассистент молчит — микрофон как есть
    sa2 = soft_aec.SoftAEC()
    fr = (rng.normal(0, 3000, FR)).astype(np.int16).tobytes()
    outs = [sa2.near(fr, now=5000.0 + i * 0.032) for i in range(5)]
    ok(all(o == fr for o in outs[1:]) and sa2.cleaned == 0, "пока ассистент молчит — в слух идёт микрофон без изменений")
else:
    print("нет aec_audio_processing — проверка комнаты пропущена")

# --- Player отдаёт, что и когда зазвучит ---
got = []
pl = audio_io.Player(null=True)
pl.far_sink = lambda pcm, rate, ch, t: got.append((len(pcm), rate, ch, t))
pl.start(22050)
pl.write(b"\x01\x00" * 22050)
ok(got and got[0][1:3] == (22050, 1) and all(got[i + 1][3] > got[i][3] for i in range(len(got) - 1)) and sum(g[0] for g in got) == 2 * 22050,
   f"голос целиком уходит в эхоподавление, куски по порядку звучания ({len(got)} кусков)")

# --- включение: только флагом, только без системного AEC и наушников ---
import ears_mic  # noqa: E402


def setup(flag, use_aec=False, headphones=False, avail=True):
    e = SimpleNamespace(status={"aec": use_aec or headphones}, player=SimpleNamespace(far_sink=None), wav_input=None, soft_aec=None)
    real = soft_aec.available
    soft_aec.available = lambda: avail
    soft_aec_cls = soft_aec.SoftAEC
    soft_aec.SoftAEC = lambda: SimpleNamespace(far="far")
    try:
        ears_mic.MicMixin._soft_aec_setup(e, {"soft_aec": flag}, use_aec, headphones)
    finally:
        soft_aec.available, soft_aec.SoftAEC = real, soft_aec_cls
    return e


e = setup(True)
ok(e.soft_aec is not None and e.status["aec"] and e.status["aec_soft"] and e.player.far_sink == "far" and not e.status.get("aec_real"),
   "флаг включён, системного нет — своё эхоподавление: слушаем во время ответа (порог — осторожный)")
ok(setup(False).soft_aec is None and not setup(False).status["aec"], "без флага — как раньше (полудуплекс)")
ok(setup(True, use_aec=True).soft_aec is None, "есть системное (Linux) — своё не нужно")
ok(setup(True, headphones=True).soft_aec is None, "«Я в наушниках» — не нужно")
ok(setup(True, avail=False).soft_aec is None and not setup(True, avail=False).status["aec"], "нет библиотеки (Mac) — как раньше")

html = (ROOT / "ui/settings.html").read_text(encoding="utf-8")
ok('data-k="audio.soft_aec"' in html and "Перебивать без наушников (проба)" in html, "переключатель в «Звук и поведение»")
ok("aec-audio-processing==" in (ROOT / "requirements-win.lock").read_text(encoding="utf-8"), "библиотека — в сборке Windows")
src = (ROOT / "core/ears_listen.py").read_text(encoding="utf-8")
ok("frame = sa.near(frame, now)" in src, "слух получает микрофон без своего голоса")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
