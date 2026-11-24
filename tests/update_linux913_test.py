"""№913 (20.11, CachyOS): обновление просит пароль, а окна пароля у системы нет («нужно открывать терминал») — и в
«Проверке» строка «Версия» печатала словарь обновления целиком. Теперь ошибка установки через pkexec подсказывает ту же
установку одной строкой для терминала (sudo …, путь к скачанному и проверенному файлу), а «Версия» — только номер."""
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


app = (ROOT / "ui/app.py").read_text(encoding="utf-8")
ok('err += ". Можно поставить и в терминале: sudo " + " ".join(shlex.quote(x) for x in cmd[1:]' in app and 'if cmd and cmd[0] == "pkexec":' in app,
   "ошибка установки через pkexec — с командой для терминала")
import shlex  # noqa: E402
cmd = ["pkexec", "bash", "/opt/dewiar/install.sh", "--yes", "--no-deps", "--deb", "/home/r/.local/share/dewiar/updates/dewiar-assistant_1.0.48_all.deb"]
line = "sudo " + " ".join(shlex.quote(x) for x in cmd[1:] if x not in ("-o", "APT::Status-Fd=1"))
ok(line == "sudo bash /opt/dewiar/install.sh --yes --no-deps --deb /home/r/.local/share/dewiar/updates/dewiar-assistant_1.0.48_all.deb", line)
apt = ["pkexec", "apt-get", "install", "-y", "--allow-downgrades", "-o", "APT::Status-Fd=1", "/x/a b.deb"]
ok("sudo " + " ".join(shlex.quote(x) for x in apt[1:] if x not in ("-o", "APT::Status-Fd=1")) == "sudo apt-get install -y --allow-downgrades '/x/a b.deb'",
   "для apt — без служебного вывода хода, путь в кавычках")
rep = (ROOT / "core/answer_report.py").read_text(encoding="utf-8")
ok("isinstance(u['available'], dict)" in rep, "«Версия» в «Проверке» — номер, а не словарь")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
