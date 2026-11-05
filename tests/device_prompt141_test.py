"""Идея №141 (05.11, «Автопрефикс устройства в каждом запросе»): ассистент должен знать, на каком устройстве идёт разговор.
Телефон пишет «Ты работаешь на телефоне пользователя (Android)» в каждой подсказке (app.js); компьютер — теперь тоже: «Ты
работаешь на компьютере пользователя (Windows / Linux / macOS)» — крупно, без версии, чтобы начало запроса оставалось общим."""
import os, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import engine_answer as E  # noqa: E402
ok(E.device_os() in ("Windows", "Linux", "macOS"), f"система крупно: {E.device_os()}")
src = (ROOT / "core/engine_answer.py").read_text(encoding="utf-8")
i = src.index("def _system_stable"); body = src[i:i + 3000]
ok("Ты работаешь на компьютере пользователя ({device_os()})" in body, "в общей части подсказки компьютера — устройство")
js = (ROOT / "android/assets/www/app.js").read_text(encoding="utf-8")
ok("Ты работаешь на телефоне пользователя (Android)" in js, "телефон — «Android» в каждой подсказке")
print("ИТОГ:", "всё прошло" if not fails else f"{len(fails)} ошибок")
sys.exit(1 if fails else 0)
