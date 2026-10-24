"""Фирменный звонок (24.10, владелец: «хочется чего-то более глубокого, не похожего ни на что другое» — выбрал «Струну»,
остальные — в коллекцию). Компьютер играет data/sounds/alarm_*.wav (tools/brand_sounds.py), прежний мотив — «motif»."""
import os, sys
from pathlib import Path
import numpy as np
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
from audio_io import alarm_tone, signature_tone  # noqa: E402
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


for s in ("signature", "chasha", "kolodec", "hor", "glubina"):
    a = np.frombuffer(alarm_tone(s), dtype=np.int16)
    dur, peak = len(a) / 22050, int(np.abs(a).max())
    ok(4 <= dur <= 6 and 8000 < peak < 32767 and abs(int(a[-50:].astype(int).sum())) < 50 * 300, f"звонок «{s}»: {dur:.1f} с, слышно, без щелчка в конце")
ok(alarm_tone("signature") == alarm_tone("struna") != signature_tone(), "фирменный — «Струна», не прежний мотив")
ok(alarm_tone("motif") == signature_tone(), "прежний мотив остался в коллекции (motif)")
html = (ROOT / "ui/settings.html").read_text(encoding="utf-8")
ok(all(f'<option value="{v}">' in html for v in ("signature", "chasha", "kolodec", "hor", "glubina", "motif", "bells")), "студия: все звонки в списке")
ok((ROOT / "tools/brand_sounds.py").is_file(), "звуки собираются своим синтезом (tools/brand_sounds.py)")
if fails:
    raise SystemExit(1)
