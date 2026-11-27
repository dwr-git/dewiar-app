"""№915 (KDE Plasma 6.8, Wayland, Archcraft): виджет — тёмный квадрат. Окна через XWayland, KWin не объявляет X-клиентам,
что он композитор: GTK говорил «не композитор» → сплошное окно, а форма X Shape там не применялась. Под Wayland окно
XWayland с альфа-каналом смешивает сам композитор — виджет прозрачный, углы гладкие."""
import os, sys, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
bad = 0
def ok(c, m):
    global bad
    bad += 0 if c else 1
    print(("✅ " if c else "❌ ") + m)

src = (ROOT / "ui/app.py").read_text(encoding="utf-8")
fn = src[src.index("def composited_x11():"):src.index("\ndef ", src.index("def composited_x11():") + 10)]


def run(composited, rgba, wayland, nvidia=False, solid=False):
    class Scr:
        def is_composited(self): return composited
        def get_rgba_visual(self): return object() if rgba else None
    gdk = types.SimpleNamespace(Screen=types.SimpleNamespace(get_default=lambda: Scr()))
    gtk = types.SimpleNamespace(init_check=lambda a: True)
    gi = types.ModuleType("gi"); gi.require_version = lambda *a: None
    rep = types.ModuleType("gi.repository"); rep.Gdk, rep.Gtk = gdk, gtk
    sys.modules["gi"], sys.modules["gi.repository"] = gi, rep
    env = {"WAYLAND_DISPLAY": "wayland-0"} if wayland else {}
    if solid:
        env["DEWIAR_HUD_SOLID"] = "1"
    said = []
    g = {"os": types.SimpleNamespace(environ=env), "ui_settings": lambda: {}, "nvidia_driver": lambda: nvidia,
         "_ui_log": said.append}
    exec(fn, g)
    return g["composited_x11"](), said

r, said = run(composited=False, rgba=True, wayland=True)
ok(r is True and said, "KDE Plasma 6 (XWayland, композитор не объявлен) — прозрачный виджет, причина в журнале")
ok(run(composited=True, rgba=True, wayland=True)[0] is True, "GNOME на Wayland — как было (прозрачный)")
ok(run(composited=False, rgba=True, wayland=False)[0] is False, "X11 без композитора — как было (форма X Shape)")
ok(run(composited=False, rgba=False, wayland=True)[0] is False, "нет альфа-канала — как было")
ok(run(composited=False, rgba=True, wayland=True, nvidia=True)[0] is False, "драйвер NVIDIA — сплошное окно, как было (№234)")
ok(run(composited=True, rgba=True, wayland=True, solid=True)[0] is False, "DEWIAR_HUD_SOLID=1 — сплошное, как было")
print("ALL OK" if not bad else f"FAILED {bad}")
sys.exit(1 if bad else 0)
