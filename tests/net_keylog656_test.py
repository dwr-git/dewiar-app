"""Отчёт 656 (Windows 11, 0.87.2): у человека вся сеть падала «[Errno 13] Permission denied: '\\\\?\\Volume{…}\\
virtual_file.log'» — облако, синхронизация, «Близкие», список моделей. Причина: в системе задана SSLKEYLOGFILE (её
ставят отладчики сети, VPN, антивирусы) с путём, куда писать нельзя, а Python открывает этот файл при каждом защищённом
соединении. Теперь net.keylog_guard() при запуске убирает такую переменную для Dewiar (доступный файл — не трогает).

Там же: задача, поставленная до 0.86, хранила в «files» записи {"name", "b64"} — продолжение после паузы падало
«sequence item 0: expected str instance, dict found». Теперь в описание задачи идут имена."""
import os, sys, tempfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import net  # noqa: E402

tmp = Path(tempfile.mkdtemp())
bad = tmp / "нет-такой-папки" / "virtual_file.log"
os.environ["SSLKEYLOGFILE"] = str(bad)
ok(net.keylog_guard() is True and "SSLKEYLOGFILE" not in os.environ, "файл недоступен — переменная убрана")
import ssl  # noqa: E402
try:
    ssl.create_default_context()
    ok(True, "после этого защищённое соединение создаётся")
except OSError as e:
    ok(False, f"защищённое соединение: {e}")
good = tmp / "keys.log"
os.environ["SSLKEYLOGFILE"] = str(good)
ok(net.keylog_guard() is False and os.environ.get("SSLKEYLOGFILE") == str(good), "доступный файл — не трогаем")
os.environ.pop("SSLKEYLOGFILE", None)
ok(net.keylog_guard() is False, "переменной нет — ничего не делаем")
src = (ROOT / "core/net.py").read_text(encoding="utf-8")
i = src.index("def install(")
ok("keylog_guard()" in src[i:i + 600], "проверка — при запуске ядра (net.install)")

import tasks  # noqa: E402
ok(tasks._file_names([{"name": "чек.pdf", "b64": "AAAA"}, "Входящие/фото.jpg", "", None]) == ["чек.pdf", "Входящие/фото.jpg"],
   "старые записи файлов задачи {name, b64} -> имена")
ok(tasks._file_names(None) == [] and tasks._file_names("a.txt") == ["a.txt"], "пусто и одна строка")
ts = (ROOT / "core/tasks.py").read_text(encoding="utf-8")
ok('"; ".join(t.data["files"]' not in ts and '"; ".join(tf[:20])' in ts, "описание задачи собирается из имён")

if fails:
    print(f"\n❌ провалов: {len(fails)}")
    sys.exit(1)
print("\n✅ всё в порядке")
