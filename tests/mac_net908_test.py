"""№908 (20.11, Mac, отчёт «Ошибка при установке обновления»): в журнале — «Близкие» и синхронизация падали каждые 6 с
(FileNotFoundError из load_verify_locations: переменная SSL_CERT_FILE указывала на файл, которого нет), а положение
виджета и размер студии не запоминались: «message too big — 5 МБ» (ответ ядра на hello больше 1 МБ — предел websockets).
Теперь: несуществующие пути сертификатов для Dewiar убираются при запуске; разовые вызовы ядра из интерфейса — без предела."""
import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import net  # noqa: E402
real = tempfile.NamedTemporaryFile(delete=False, suffix=".pem").name
os.environ["SSL_CERT_FILE"] = "/nonexistent/dewiar/cert.pem"
os.environ["SSL_CERT_DIR"] = "/nonexistent/dewiar/certs"
os.environ["REQUESTS_CA_BUNDLE"] = real
gone = net.certs_guard()
ok(set(gone) == {"SSL_CERT_FILE", "SSL_CERT_DIR"} and "SSL_CERT_FILE" not in os.environ and os.environ.get("REQUESTS_CA_BUNDLE") == real,
   f"несуществующие пути сертификатов убраны, настоящий — оставлен: {gone}")
import httpx  # noqa: E402
try:
    httpx.Client().close()
    ok(True, "после этого защищённый клиент создаётся без FileNotFoundError")
except FileNotFoundError as e:
    ok(False, f"клиент не создался: {e}")
os.unlink(real)
src = (ROOT / "core/net.py").read_text(encoding="utf-8")
ok(re.search(r"keylog_guard\(\)\n\s+certs_guard\(\)\n\s+trust_system\(\)", src), "проверка — при запуске ядра, до сертификатов системы")
for f in ("ui/app.py", "ui/winshell.py"):
    s = (ROOT / f).read_text(encoding="utf-8")
    bad = [x for x in re.findall(r'connect\(f"ws://127\.0\.0\.1:[^)]*\)', s) if "max_size=None" not in x]
    ok(not bad, f"{f}: вызовы ядра без предела 1 МБ ({bad[:2]})")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
