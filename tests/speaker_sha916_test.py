"""№914/916 (20.11): «Суфлёр — модель голоса не скачалась: контрольная сумма не совпала». Сумма sha256 модели голоса
(3D-Speaker CAM++, sherpa-onnx на GitHub) в программе была не от этого файла: модель скачивалась и удалялась, голос
владельца не запоминался. Сверено с файлом на GitHub 20.11 (28 281 165 байт, вход x, выход — 192 числа)."""
import os
import re
import sys
from pathlib import Path

ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


GOOD = "53cab20ba8f2eb2f6e2d89ecc18e88ef3222169b61b4419cbc13666744a4574b"
sp = (ROOT / "core/speaker.py").read_text(encoding="utf-8")
pub = (ROOT / "tools/publish_update.py").read_text(encoding="utf-8")
ok(re.search(r'^MODEL_SHA256 = "([0-9a-f]{64})"', sp, re.M).group(1) == GOOD, "программа: сумма модели голоса — от настоящего файла")
ok(re.search(r'^SPEAKER_SHA = "([0-9a-f]{64})"', pub, re.M).group(1) == GOOD, "зеркало на сайте — та же сумма")
ok("aa3cfc16963a" not in sp + pub, "старой неверной суммы нигде нет")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
