"""Звонки будильника на компьютере (28.10, владелец: «наши убрать, мелодии глубокие, с ударными — очень красиво»; выбрал
пять из двенадцати, «Пульс» — по умолчанию). data/sounds/alarm_*.wav — звуки Android Open Source Project (Apache 2.0,
NOTICE); прежний выбор (Струна, Чаша…, bells) — снова «Пульс»; без файла — запасной синтез, будильник не молчит."""
import os, sys
from pathlib import Path
import numpy as np
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
import audio_io  # noqa: E402
from audio_io import ALARM_RATE, BRAND_SOUNDS, alarm_tone, signature_tone  # noqa: E402
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


ok(BRAND_SOUNDS == ("signature", "noon", "night", "wave", "sparks") and ALARM_RATE == 32000, "пять звонков, 32 кГц")
ok(sorted(p.name for p in (ROOT / "data/sounds").glob("alarm_*.wav")) == sorted(f"alarm_{s}.wav" for s in BRAND_SOUNDS), "в data/sounds — только они")
tones = {}
for s in BRAND_SOUNDS:
    a = np.frombuffer(alarm_tone(s), dtype=np.int16)
    tones[s] = a
    dur, peak = len(a) / ALARM_RATE, int(np.abs(a).max())
    rms = float(np.sqrt((a.astype(np.float64) ** 2).mean()))
    ok(4 <= dur <= 15.5 and 12000 < peak < 32767 and rms > 2500, f"звонок «{s}»: {dur:.1f} с, громко и ровно (пик {peak}, RMS {rms:.0f})")
ok(max(np.sqrt((t.astype(np.float64) ** 2).mean()) for t in tones.values()) / min(np.sqrt((t.astype(np.float64) ** 2).mean()) for t in tones.values()) < 2.2,
   "громкость выровнена — ни один не вдвое тише другого")
for old in ("chasha", "struna", "motif", "bells", "", None):
    ok(alarm_tone(old) == alarm_tone("signature"), f"прежний выбор «{old}» — звенит «Пульс»")
ok(alarm_tone("signature") != signature_tone(ALARM_RATE), "фирменный — «Пульс», не синтез")
real = audio_io._wav_tone
audio_io._wav_tone = lambda *a: None
ok(alarm_tone("signature") == signature_tone(ALARM_RATE), "нет файла — запасной синтез, будильник не молчит")
audio_io._wav_tone = real
html = (ROOT / "ui/settings.html").read_text(encoding="utf-8")
ok(all(f'<option value="{v}">' in html for v in BRAND_SOUNDS) and 'value="chasha"' not in html, "студия: пять звонков в списке, прежних нет")
et = (ROOT / "core/engine_tools.py").read_text(encoding="utf-8")
ok("pl.start(ALARM_RATE)" in et, "звонок играется с той же частотой, что записан")
if fails:
    raise SystemExit(1)
