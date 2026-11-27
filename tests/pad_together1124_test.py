"""Владелец 24.11, 21:25 (Ubuntu, «поверх всех» выключено): «фокус на виджете — он поднялся над браузером, а блокнот, который
с ним работает, под браузером; нажал на блокнот — он поднялся, а виджет спрятан». Виджет и блокнот — два окна, каждое
поднималось само. Теперь блокнот — подчинённое окно виджета (transient_for): оконный менеджер поднимает их вместе.
Если на машине есть Xvfb, mutter и GTK — проверяем в настоящем Mutter: без подчинения — порядок «виджет, браузер, блокнот»
(ошибка), с ним — «браузер, виджет, блокнот»."""
import os, shutil, subprocess, sys, tempfile, textwrap, time, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    c or fails.append(m)


src = (ROOT / "ui/app.py").read_text(encoding="utf-8")
i = src.index("    def _pad_attach(self, gw):"); j = src.index("\n    def ", i + 10)
code = textwrap.dedent(src[i:j])


class W:
    def __init__(self, title):
        self.title, self.parent = title, None

    def get_title(self):
        return self.title

    def get_transient_for(self):
        return self.parent

    def set_transient_for(self, p):
        self.parent = p


card, mini, pad = W("Dewiar"), W("Dewiar — значок"), W("Dewiar — блокнот")
gtk = types.ModuleType("gi.repository"); gtk.Gtk = types.SimpleNamespace(Window=types.SimpleNamespace(list_toplevels=lambda: [mini, card, pad]))
sys.modules.setdefault("gi", types.ModuleType("gi")); sys.modules["gi.repository"] = gtk
logs = []
ns = {"TITLES": {"card": "Dewiar", "mini": "Dewiar — значок"}, "_ui_log": logs.append}
exec(code, ns)
me = types.SimpleNamespace(mode="card")
ns["_pad_attach"](me, pad)
ok(pad.parent is card, "блокнот — подчинённое окно виджета («Dewiar»)")
ns["_pad_attach"](me, pad)
ok(len(logs) == 1, "второй показ — уже подчинён, ничего не меняем")
for tag in ('self._pad_attach(gw)\n                        gw.show_all()\n                        gw.present()',
            'self._pad_attach(gw)\n                        gw.show_all()\n                        gw.get_window().move'):
    ok(tag in src, f"подчиняем до показа: {'повторный показ' if 'present' in tag else 'первый показ'}")

# настоящий Mutter (если есть): порядок окон после щелчков
py = shutil.which("python3.12") or sys.executable
have = all(shutil.which(x) for x in ("Xvfb", "mutter", "dbus-run-session", "xprop")) and \
    subprocess.run([py, "-c", "import gi; gi.require_version('Gtk','3.0'); from gi.repository import Gtk"], capture_output=True).returncode == 0
if not have:
    print("— настоящего Mutter здесь нет: проверка порядка окон пропущена")
else:
    exp = Path(tempfile.mkdtemp()) / "exp.py"
    exp.write_text(textwrap.dedent('''
        import subprocess, sys, gi
        gi.require_version("Gtk", "3.0"); gi.require_version("GdkX11", "3.0")
        from gi.repository import Gtk, GLib, GdkX11
        wins, out = {}, []
        for t in ("widget", "pad", "browser"):
            w = Gtk.Window(title=t); w.set_default_size(200, 150); w.show_all(); wins[t] = w
        def stack():
            o = subprocess.run(["xprop", "-root", "_NET_CLIENT_LIST_STACKING"], capture_output=True, text=True).stdout
            ids = [int(x.strip().rstrip(","), 16) for x in o.split("#")[-1].split(",") if x.strip()]
            names = {w.get_window().get_xid(): t for t, w in wins.items()}
            return ",".join(names.get(i, "?") for i in ids)
        def click(t):
            wins[t].present_with_time(GdkX11.x11_get_server_time(wins[t].get_window()))
        def go():
            if sys.argv[1] == "attach":
                wins["pad"].set_transient_for(wins["widget"])
            seq = [lambda: click("browser"), lambda: click("widget"), lambda: out.append(stack()),
                   lambda: click("browser"), lambda: click("pad"), lambda: out.append(stack()), Gtk.main_quit]
            for k, f in enumerate(seq):
                GLib.timeout_add(600 * (k + 1), lambda f=f: (f(), False)[1])
            return False
        GLib.timeout_add(800, go); Gtk.main(); print("|".join(out))
    '''), encoding="utf-8")
    disp = ":%d" % (90 + os.getpid() % 50)
    xv = subprocess.Popen(["Xvfb", disp, "-screen", "0", "1280x800x24"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)
    try:
        res = {}
        for m in ("plain", "attach"):
            r = subprocess.run(["dbus-run-session", "--", "bash", "-c", f"mutter --x11 --replace >/dev/null 2>&1 & sleep 2; {py} {exp} {m}; kill %1"],
                               capture_output=True, text=True, timeout=60, env=dict(os.environ, DISPLAY=disp))
            res[m] = (r.stdout.strip().splitlines() or [""])[-1]
        ok(res["plain"].startswith("pad,browser,widget|widget,browser,pad"), f"без подчинения — та самая ошибка: {res['plain']}")
        ok(res["attach"] == "browser,widget,pad|browser,widget,pad", f"с подчинением — щёлкнули на виджет или на блокнот: оба над браузером: {res['attach']}")
    finally:
        xv.kill()
print("ИТОГ: " + ("всё прошло" if not fails else f"провалов {len(fails)}"))
sys.exit(1 if fails else 0)
