"""Варианты фирменного звука Dewiar (владелец 29.10: «нравится, но обычный — как у Viber, чтобы ни на что не был похож»).

  drop  — «Капля»: два «блупа» с подъёмом высоты (синус, высота взлетает за 50–70 мс), второй выше и короче — живой,
          «водяной», узнаётся с первого раза;
  lira  — «Ли-ра»: синтетический голосок поёт два слога — гласные «и» → «а» (форманты), высота вверх-вниз, как имя;
  kalimba — «Калимба»: три ноты ритмом «та-та-таам» (G6 · D7 · B6) деревянно-металлическим тембром с коротким эхом.

    python3 tools/sounds/signature.py <вариант> <файл.ogg|.mp3|.wav>
"""
import subprocess
import sys

import numpy as np

SR = 48000


def env(t, a, d):
    return np.minimum(1, t / a) * np.exp(-t / d)


def bloop(t0, f0, f1, glide, dur, total, amp=1.0):
    t = np.arange(int(total * SR)) / SR - t0
    on = t >= 0
    t = np.where(on, t, 0)
    f = f1 + (f0 - f1) * np.exp(-t / glide)                       # высота взлетает от f0 к f1
    ph = 2 * np.pi * np.cumsum(f) / SR
    return amp * on * env(t, 0.004, dur) * (np.sin(ph) + 0.18 * np.sin(2 * ph))


def drop():
    T = 0.75
    x = bloop(0.0, 520, 1180, 0.022, 0.11, T) + 0.85 * bloop(0.16, 760, 1760, 0.016, 0.09, T)
    x += 0.25 * bloop(0.16, 380, 880, 0.02, 0.2, T)                   # мягкое «тело» под второй каплей
    return x, T


def formant_voice(f0c, vowels, T):
    """Пила через три формантных резонатора; форманты плавно переходят по vowels [(t, F1, F2, F3)]."""
    n = int(T * SR)
    t = np.arange(n) / SR
    f0 = np.interp(t, f0c[0], f0c[1])
    ph = np.cumsum(f0) / SR
    src = 2 * (ph % 1) - 1
    out = np.zeros(n)
    tv = [v[0] for v in vowels]
    for k, bw in ((1, 90), (2, 120), (3, 170)):
        F = np.interp(t, tv, [v[k] for v in vowels])
        r = np.exp(-np.pi * bw / SR)
        y1 = y2 = 0.0
        y = np.empty(n)
        for i in range(n):                                            # двухполюсный резонатор с переменной частотой
            c = 2 * r * np.cos(2 * np.pi * F[i] / SR)
            yi = src[i] + c * y1 - r * r * y2
            y[i] = yi
            y2, y1 = y1, yi
        out += y / np.abs(y).max() * (1.0 if k == 1 else 0.7 if k == 2 else 0.35)
    return out, t


def lira():
    T = 0.72
    # «Ли» — короткий высокий слог, «ра» — ниже и длиннее, с лёгким вибрато в конце
    f0c = ([0, 0.05, 0.22, 0.26, 0.5, 0.72], [740, 880, 900, 660, 640, 600])
    vowels = [(0, 300, 2300, 3000), (0.2, 300, 2250, 3000), (0.27, 650, 1500, 2600), (0.34, 780, 1250, 2500), (0.72, 760, 1200, 2500)]
    x, t = formant_voice(f0c, vowels, T)
    gate = np.where(t < 0.2, np.minimum(1, t / 0.012), np.where(t < 0.25, 0.35 + 0.65 * (0.25 - t) / 0.05, np.minimum(1, (t - 0.25) / 0.02)))
    x = x * gate * np.exp(-np.maximum(0, t - 0.32) / 0.22) * (1 + 0.04 * np.sin(2 * np.pi * 6 * t))
    return x, T


def kalimba():
    T = 1.0
    t = np.arange(int(T * SR)) / SR
    x = np.zeros_like(t)
    for t0, f, a in ((0.0, 1568.0, 0.8), (0.11, 2349.3, 0.7), (0.24, 1975.5, 1.0)):
        tt = t - t0
        on = tt >= 0
        tt = np.where(on, tt, 0)
        d = 0.38 if t0 == 0.24 else 0.14
        tone = np.sin(2 * np.pi * f * tt) + 0.5 * np.sin(2 * np.pi * f * 3.02 * tt) * np.exp(-tt / 0.03) + 0.2 * np.sin(2 * np.pi * f * 0.5 * tt)
        x += a * on * env(tt, 0.002, d) * tone
    echo = np.zeros_like(x)
    k = int(0.16 * SR)
    echo[k:] = 0.28 * x[:-k]
    return x + echo, T


def write(x, T, out):
    n = len(x)
    tail = np.clip((T - np.arange(n) / SR) / 0.06, 0, 1)
    x = x * tail
    x = x / np.abs(x).max() * 0.88
    raw = (x * 32767).astype("<i2").tobytes()
    codec = ["-c:a", "libvorbis", "-q:a", "5"] if out.endswith(".ogg") else (["-c:a", "libmp3lame", "-q:a", "2"] if out.endswith(".mp3") else [])
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "s16le", "-ar", str(SR), "-ac", "1", "-i", "-", *codec, out], input=raw, check=True)


if __name__ == "__main__":
    kind, out = sys.argv[1], sys.argv[2]
    x, T = {"drop": drop, "lira": lira, "kalimba": kalimba}[kind]()
    if kind == "lira":                                                # пила звенит — мягче, как голос, а не зуммер
        a = np.exp(-2 * np.pi * 4200 / SR)
        for _ in range(2):
            y = np.empty_like(x)
            p = 0.0
            for i, v in enumerate(x):
                p = (1 - a) * v + a * p
                y[i] = p
            x = y
    write(x, T, out)
    print(out)
