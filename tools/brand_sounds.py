"""Фирменные звонки Dewiar (24.10, владелец: «хочется чего-то более глубокого, не похожего ни на что другое»;
выбрал «Струну» основным, остальные — в коллекцию). Синтез numpy/scipy, без чужих записей:
  struna  — «Струна»: низкая щипковая струна (Karplus–Strong) и флажолет — фирменный (id signature);
  chasha  — «Чаша»: две поющие чаши с биением обертонов;
  kolodec — «Колодец»: капли в каменном гроте мотивом Dewiar (соль–ре–си);
  hor     — «Хор»: тёплое «м-м-м» на три голоса, вверх;
  glubina — «Глубина»: аккорд раскрывается снизу, сверху — прежний мотив Dewiar.
Прежний мотив остаётся как «motif» (на телефоне — android/res/raw/alarm_motif.ogg, на компьютере — синтез signature_tone).
Запуск: python3 tools/brand_sounds.py — пишет android/res/raw/alarm_*.ogg (моно 44,1 кГц) и data/sounds/alarm_*.wav
(моно 22 050 Гц, их играет core/audio_io.alarm_tone). Нужны numpy, scipy и ffmpeg с libvorbis."""
import math, subprocess, tempfile, wave
from pathlib import Path
import numpy as np
from scipy.signal import fftconvolve, butter, lfilter, sosfilt
SR = 44100
R = np.random.default_rng(11)
def hz(n):
    names = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}
    return 440.0 * 2 ** ((names[n[:-1]] + 12 * (int(n[-1]) + 1) - 69) / 12)
def lp(x, f, o=2): return sosfilt(butter(o, f / (SR / 2), output="sos"), x)
def hp(x, f, o=2): return sosfilt(butter(o, f / (SR / 2), "high", output="sos"), x)
def bp(x, f, q):
    w = 2 * math.pi * f / SR; al = math.sin(w) / (2 * q)
    b = [al, 0, -al]; a = [1 + al, -2 * math.cos(w), 1 - al]
    return lfilter(b, a, x)
def room(x, sec=2.6, decay=0.9, wet=0.35, bright=4200, pre=0.02):
    n = int(SR * sec); t = np.arange(n) / SR
    irl = lp(R.standard_normal(n), bright) * np.exp(-t / decay); irr = lp(R.standard_normal(n), bright) * np.exp(-t / decay)
    for ir in (irl, irr): ir[: int(SR * pre)] = 0; ir /= np.sqrt(np.sum(ir ** 2))
    if x.ndim == 1: x = np.stack([x, x])
    y = np.stack([fftconvolve(x[0], irl)[: x.shape[1]], fftconvolve(x[1], irr)[: x.shape[1]]])
    return (1 - wet) * x + wet * y
def env_ad(n, a, tau):
    t = np.arange(n) / SR; return np.minimum(1, t / max(a, 1e-4)) * np.exp(-t / tau)
def put(out, start, s):
    i = int(SR * start); m = min(s.shape[-1], out.shape[-1] - i)
    if out.ndim == 2 and s.ndim == 1: out[:, i:i + m] += s[:m]
    else: out[..., i:i + m] += s[..., :m]
def pan(s, p):  # p -1..1
    return np.stack([s * math.cos((p + 1) * math.pi / 4), s * math.sin((p + 1) * math.pi / 4)])

def bowl(f, dur, amp=1.0):
    """Поющая чаша: негармоничные обертоны парами с биением."""
    n = int(SR * dur); t = np.arange(n) / SR; s = np.zeros(n)
    for ratio, a, tau, beat in [(1, 1, 3.2, 1.3), (2.76, .55, 2.0, 2.1), (5.4, .28, 1.1, 3.0), (8.9, .12, .6, 4.2)]:
        for d in (-beat / 2, beat / 2):
            s += a * .5 * np.sin(2 * math.pi * (f * ratio + d) * t + R.uniform(0, 6)) * np.exp(-t / tau)
    s *= np.minimum(1, t / .006)
    s += lp(R.standard_normal(n), 2500) * np.exp(-t / .012) * .25      # касание колотушки
    return amp * s

def drop(f, amp=1.0):
    """Капля в колодце: «блуп» с подъёмом тона + низкий отклик."""
    n = int(SR * 1.6); t = np.arange(n) / SR
    ff = f * (1 + 1.1 * (1 - np.exp(-t / .03)))
    ph = 2 * math.pi * np.cumsum(ff) / SR
    s = np.sin(ph) * env_ad(n, .002, .09)
    body = (np.sin(2 * math.pi * f * .5 * t) + .4 * np.sin(2 * math.pi * f * t)) * env_ad(n, .01, .35) * .55
    return amp * (s + body)

def fm(f, dur, amp, ratio=3.5, index=2.0, decay=.6):
    n = int(SR * dur); t = np.arange(n) / SR
    e = np.minimum(1, t / .003) * np.exp(-t / decay)
    return amp * e * np.sin(2 * math.pi * f * t + index * np.exp(-t / (decay * .35)) * np.sin(2 * math.pi * f * ratio * t))

def saw(f, n, det=0.0):
    t = np.arange(n) / SR; ph = (f * (1 + det)) * t
    return 2 * (ph - np.floor(ph + .5))

OUT = {"1-chasha": "chasha", "2-kolodec": "kolodec", "3-hor": "hor", "4-glubina": "glubina", "5-struna": "struna"}
ROOT = Path(__file__).resolve().parent.parent
TMP = Path(tempfile.mkdtemp())


def finish(name, x, tail=.4):
    if x.ndim == 1: x = np.stack([x, x])
    f = int(SR * tail); x[:, -f:] *= np.linspace(1, 0, f) ** 2
    x = hp(x, 40)
    rms = np.sqrt(np.mean(x ** 2)); x = x / rms * .12
    pk = np.max(np.abs(x)); x = x / max(pk, 1) * .89 if pk > .89 else x
    pcm = (np.clip(x.T, -1, 1) * 32767).astype(np.int16)
    sid = OUT[name]; wav = TMP / f"{sid}.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
    raw = "signature" if sid == "struna" else sid                     # «Струна» — фирменный звонок
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-ac", "1", "-c:a", "libvorbis", "-q:a", "4",
                    str(ROOT / f"android/res/raw/alarm_{raw}.ogg")], check=True)
    (ROOT / "data/sounds").mkdir(exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-ac", "1", "-ar", "22050", "-c:a", "pcm_s16le",
                    str(ROOT / f"data/sounds/alarm_{sid}.wav")], check=True)

# 1. Чаша — две поющие чаши (соль и ре) и тихий отклик октавой выше
x = np.zeros((2, int(SR * 5.2)))
put(x, .0, pan(bowl(hz("G3"), 5, 1.0), -.25)); put(x, .55, pan(bowl(hz("D4"), 4.6, .8), .25)); put(x, 1.25, pan(bowl(hz("B4"), 4, .35), 0))
finish("1-chasha", room(x, 3.2, 1.2, .3))

# 2. Колодец — три капли мотивом Dewiar (соль-ре-си) в каменном гроте
x = np.zeros((2, int(SR * 4.6)))
for st, nt, a, p in [(0, "G4", 1, -.3), (.32, "D5", .85, .3), (.62, "B4", .9, 0), (1.5, "G4", .6, -.2), (1.72, "G5", .5, .2)]:
    put(x, st, pan(drop(hz(nt), a), p))
finish("2-kolodec", room(x, 3.6, 1.4, .5, 3000, .045))

# 3. Хор — «м-м-м» тёплым голосом: три голоса, гласная «о», мотив вверх
def hum(f, dur, amp):
    n = int(SR * dur); t = np.arange(n) / SR
    vib = 1 + .006 * np.sin(2 * math.pi * 5.2 * t) * np.minimum(1, t / .6)
    ph = np.cumsum(f * vib) / SR; src = 2 * (ph - np.floor(ph + .5)) + .3 * R.standard_normal(n) * .05
    v = bp(src, 450, 6) * 1.0 + bp(src, 800, 7) * .6 + bp(src, 2600, 9) * .12 + lp(src, 300) * .3
    e = np.minimum(1, t / .22) * np.minimum(1, (dur - t) / .5).clip(0, 1)
    return amp * v * e
x = np.zeros((2, int(SR * 4.8)))
for st, nts, a in [(0, ["G3", "D4", "B4"], 1), (.9, ["D4", "A4", "D5"], .9), (1.9, ["G3", "B4", "G5"], .8)]:
    for k, nt in enumerate(nts):
        put(x, st + k * .03, pan(hum(hz(nt) * (1 + (k - 1) * .002), 1.6 if st < 1.8 else 2.7, a * (1 - k * .15)), (k - 1) * .5))
put(x, 2.0, pan(fm(hz("D7"), 1.5, .08, 2, 1.2, .5), .3))
finish("3-hor", room(x, 3, 1.1, .35))

# 4. Глубина — тёплый аккорд раскрывается снизу, сверху прежний мотив Dewiar тише (узнаваемость сохраняется)
n = int(SR * 5); t = np.arange(n) / SR
pad = sum(saw(hz(nt), n, d) for nt in ["G2", "D3", "A3", "B3", "F#4"] for d in (-.003, .003)) / 10
cut = 250 + 1700 * np.sin(np.clip(t / 2.4, 0, 1) * math.pi / 2) * np.exp(-np.clip(t - 2.4, 0, None) / 1.5)
y = np.zeros(n); z1 = z2 = 0.0
co = 1 - np.exp(-2 * math.pi * cut / SR)
for i in range(n):                                          # плавный фильтр с ходом частоты (две ступени, без щелчков)
    z1 += co[i] * (pad[i] - z1); z2 += co[i] * (z1 - z2); y[i] = z2
y *= np.minimum(1, t / .9) * np.minimum(1, (5 - t) / 1.6).clip(0, 1)
x = np.zeros((2, n)); put(x, 0, pan(y * 1.3, 0))
for st, nt, a in [(.7, "G5", .32), (.86, "D6", .34), (1.08, "B5", .3), (2.3, "G5", .2), (2.46, "D6", .22), (2.68, "G6", .2)]:
    put(x, st, pan(fm(hz(nt), 2, a), (hash(nt) % 3 - 1) * .3))
finish("4-glubina", room(x, 2.8, 1.0, .3))

# 5. Струна — низкая струна (как гучжэн/виолончель щипком) и флажолет: Karplus-Strong
def ks(f, dur, amp, bright=.5):
    n = int(SR * dur); L = int(SR / f); buf = lp(R.standard_normal(L), 3000 * bright + 400); out = np.zeros(n); i = 0
    d = .9985
    for k in range(n):
        v = buf[k % L]; nxt = buf[(k + 1) % L]; buf[k % L] = d * .5 * (v + nxt); out[k] = v
    return amp * out
x = np.zeros((2, int(SR * 4.8)))
put(x, 0, pan(ks(hz("G2"), 4.6, 1.0, .35), -.2)); put(x, .02, pan(ks(hz("D3"), 4.5, .5, .4), .2))
put(x, .55, pan(fm(hz("G5"), 2.6, .22, 1.0, .4, 1.1), .3)); put(x, .8, pan(fm(hz("D6"), 2.4, .18, 1.0, .4, 1.0), -.2))
put(x, 1.1, pan(ks(hz("B2"), 3.6, .45, .35), .1))
finish("5-struna", room(x, 3, 1.0, .3))
print("готово:", ", ".join(OUT.values()))
