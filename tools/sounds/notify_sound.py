"""Фирменный звук уведомлений Dewiar (0.69; владелец 29.10: «у Viber свой звук — можем и мы свой»; из трёх вариантов выбрал
«Калимбу»): три ноты ритмом «та-та-таам» (G6 · D7 · B6) деревянно-металлическим тембром с коротким эхом — ни на что
системное не похоже. Сам звук собирает tools/sounds/signature.py (там же «Капля» и «Ли-ра»).

    python3 tools/sounds/notify_sound.py android/res/raw/dewiar_note.ogg
"""
import subprocess
import sys
from pathlib import Path

if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "dewiar_note.ogg"
    subprocess.run([sys.executable, str(Path(__file__).with_name("signature.py")), "kalimba", out], check=True)
