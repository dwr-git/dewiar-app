"""№974 (23.11, realme, Android 16): «Это устройство» в «Кто распознаёт голос», а при нажатии микрофона — ошибка веб-версии
«В этом браузере распознавание речи не работает». Распознаватель телефона отвечал ошибкой 13 (ERROR_LANGUAGE_UNAVAILABLE:
не умеет выбирать между двумя языками — в настройках второй язык), а приложение принимало 13 за знак веб-версии.
Теперь: Speech.java при 12/13 сразу слушает ещё раз только на основном языке (и дальше так), а «нет распознавания в
браузере» — только в веб-версии (D.web)."""
import os, re, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    c or fails.append(m)


j = (ROOT / "android/src/pro/dewiar/app/Speech.java").read_text(encoding="utf-8")
ok("(code == 12 || code == 13) && !ready[0] && sw" in j and "noLangSwitch = true" in j and "if (sw) {" in j,
   "телефон: 12/13 — сразу ещё раз без выбора языка, и дальше только основной язык")
ok("case 12: case 13:" in j, "у ошибки 12/13 — понятная причина, а не «ошибка распознавания 13»")
js = (ROOT / "android/www-src/app/06-ears-voice.js").read_text(encoding="utf-8")
ok('e.code === 13 && D.web)' in js, "«в этом браузере распознавания нет» — только в веб-версии")
app = (ROOT / "android/assets/www/app.js").read_text(encoding="utf-8")
ok('e.code === 13 && D.web)' in app, "app.js собран")
print("ИТОГ: " + ("всё прошло" if not fails else f"провалов {len(fails)}"))
sys.exit(1 if fails else 0)
