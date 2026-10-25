"""Токены — не в журнал и не в отчёт (отчёт 256, 25.10: токен умного дома, вставленный в команду PowerShell
«$token = "eyJ…"», попал в журнал целиком и уехал в отчёт). Обычные строки — без изменений."""
import os, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
from engine_base import redact, mask_tokens  # noqa: E402
import engine_answer  # noqa: E402
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9." + "eyJpc3MiOiJhYmMxMjMifQ" + "." + "Zm9vYmFyYmF6cXV4MTIzNDU2Nzg5"
secret = [
    (f'run_command {{"command": "$token = \\"{jwt}\\"; Invoke-RestMethod"}}', "JWT в команде"),
    (f"❓ 192.168.1.21   {jwt}", "JWT в реплике"),
    ("remember Home Assistant: порт 8123, токен API: Zx9q" + "w8e7r6t5y4u3i2o1p0" * 2, "«токен API: …»"),
    ("Authorization: Bearer abcdEFGH12345678xyz", "Bearer"),
    ("ключ sk-ant-api03-" + "x1" * 20, "ключ Anthropic"),
    ("ghp_" + "A1b2C3" * 6, "токен GitHub"),
    ("https://api.telegram.org/bot123456789:" + "AAk" * 12 + "/getMe", "токен Telegram"),
]
for text, what in secret:
    r = redact(text)
    leak = jwt[-12:] if "eyJ" in text else text.rstrip("/getM")[-12:]
    ok("***" in r and leak not in r, f"{what} → спрятан")
plain = ["Сколько времени?", "Сейчас 17:13.", "открой /home/user/Documents/report2026.txt", "commit 3f2a1b9c8d7e6f5a",
         "напомни в 18:30 позвонить маме", "погода в Минске на завтра", "run_command {\"command\": \"Get-Process | Sort CPU\"}"]
for t in plain:
    ok(redact(t) == t, f"обычная строка без изменений: {t[:40]!r}")
cls = next(v for v in vars(engine_answer).values() if isinstance(v, type) and hasattr(v, "_redact") and "_log_tail" in vars(v))
ok(jwt not in cls._redact(f"16:48:13 INFO run_command $token = \"{jwt}\""), "и в отчёте — последней страховкой")
ok(mask_tokens(None) == "", "пустое — пусто")
print("ИТОГ:", "OK" if not fails else f"{len(fails)} ошибок")
sys.exit(1 if fails else 0)
