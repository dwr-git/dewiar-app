"""№413 (30.10, Manjaro, Wayland, NVIDIA, Python 3.14): виджет не появлялся — для Python не нашлось GTK, pywebview молча
пробовал Qt («QT cannot be loaded»). Теперь перед запуском окна — понятная причина и команда своего дистрибутива (в журнал
интерфейса и уведомлением)."""
import os, sys, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "ui")); sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import app  # noqa: E402
real = sys.modules.get("gi")
sys.modules["gi"] = None                                   # import gi → ImportError
ok(app.gtk_missing().startswith("нет PyGObject для Python"), f"нет PyGObject — так и сказано: {app.gtk_missing()!r}")
fake = types.ModuleType("gi")
def req(name, v):
    if name == "WebKit2":
        raise ValueError("Namespace WebKit2 not available")
fake.require_version = req
sys.modules["gi"] = fake
ok(app.gtk_missing() == "нет WebKit2GTK 4.1", "нет WebKit2GTK — так и сказано")
fake.require_version = lambda n, v: None
ok(app.gtk_missing() == "", "всё есть — пусто")
if real is not None:
    sys.modules["gi"] = real
else:
    sys.modules.pop("gi", None)
w = app.shutil.which
app.shutil.which = lambda exe: "/usr/bin/pacman" if exe == "pacman" else None
ok("sudo pacman -S --needed python-gobject gtk3 webkit2gtk-4.1" in app.gtk_tip(), f"Manjaro/Arch — команда pacman: {app.gtk_tip()}")
app.shutil.which = w
src = (ROOT / "ui/app.py").read_text(encoding="utf-8")
ok('why = gtk_missing()' in src and 'notify-send' in src, "перед окном — проверка и уведомление")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
