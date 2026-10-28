"""№374 (28.10): «звук моно везде — и в радио, и в проигрывании плеера». Радио и своя музыка шли через ffmpeg «-ac 1» —
одним каналом. Теперь музыка — стерео 44,1 кГц (ffmpeg -ac 2, Player.start(rate, 2): libpulse, pacat и sounddevice — по
два канала); голос по-прежнему моно. Время звучания и «пришло ли 3 секунды звука» считаются в кадрах, не в отсчётах."""
import os, sys, time
from pathlib import Path
import numpy as np
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import radio as R  # noqa: E402
from audio_io import Player  # noqa: E402

ok(R.CH == 2 and R.BPS == R.RATE * 4, "радио: стерео, 44,1 кГц")
src = (ROOT / "core/radio.py").read_text(encoding="utf-8")
ok('"-ac", str(CH)' in src and "self.player.start(RATE, CH)" in src and "player.start(RATE, CH)" in src.split("def _pump")[1], "ffmpeg отдаёт два канала, проигрыватель открыт на два — и после сбоя вывода тоже")
au = (ROOT / "core/audio_io.py").read_text(encoding="utf-8")
ok('f"--channels={self.ch}"' in au and "channels=self.ch, dtype=\"int16\"" in au and "_PulseOut(rate, self.device, self.ch)" in au, "все три вывода (libpulse, pacat, sounddevice) — с числом каналов")
ok("--channels=1" not in au.split("class Player")[1].split("def write")[0] and "channels=1, dtype" not in au.split("class Player")[1].split("def write")[0], "у проигрывателя нет зашитого «моно»")
p = Player(null=True)
p.start(R.RATE, 2)
t = np.linspace(0, 1, R.RATE, endpoint=False)
st = np.stack([np.sin(2 * np.pi * 440 * t) * 8000, np.sin(2 * np.pi * 660 * t) * 8000], axis=1).astype(np.int16).tobytes()
t0 = time.monotonic(); p.write(st); dt = time.monotonic() - t0
ok(p._written == R.RATE and abs(dt - (1 - p.AHEAD)) < 0.25, f"секунда стерео — это секунда (кадров {p._written}, писали {dt:.2f} с)")
got = b"".join(p.captured)
arr = np.frombuffer(got, dtype=np.int16).reshape(-1, 2)
ok(arr.shape[0] == R.RATE and not np.array_equal(arr[:, 0], arr[:, 1]), "левый и правый каналы разные — не склеены в один")
v = Player(null=True); v.start(22050)
ok(v.ch == 1, "голос — по-прежнему моно")
b = R._bands(st[: R.BPS // 10], np)
ok(len(b) == 8 and max(b) > 0, "полосы для анимации — из стерео")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
