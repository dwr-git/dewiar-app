"""24.10, владелец (Ubuntu): «Лира исчезла, а блокнот остался… открыл папку — она перекрыла виджет, но не блокнот; они
должны быть на одном уровне». Сторож keep_above_guard (раз в 3 с, X11): у видимого виджета, значка или блокнота
оконный менеджер снял «поверх» — ставим обратно (снять и поставить: иначе GTK думает, что флаг и так стоит)."""
import ast, os, sys, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


src = (ROOT / "ui/app.py").read_text(encoding="utf-8")
fn = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == "keep_above_guard")


class X11Window:
    def __init__(self, above): self.above = above
    def get_state(self): return 4 if self.above else 0


class Win:
    def __init__(self, title, above, visible=True):
        self.title, self.gdw, self.vis, self.calls = title, X11Window(above), visible, []
    def get_title(self): return self.title
    def get_visible(self): return self.vis
    def get_mapped(self): return self.vis
    def get_window(self): return self.gdw
    def set_keep_above(self, v): self.calls.append(v); self.gdw.above = v


wins = [Win("Dewiar", False), Win("Dewiar — блокнот", True), Win("Dewiar — значок", False, visible=False), Win("Nautilus", False)]
gi = types.ModuleType("gi"); rep = types.ModuleType("gi.repository")
rep.Gdk = types.SimpleNamespace(WindowState=types.SimpleNamespace(ABOVE=4))
rep.Gtk = types.SimpleNamespace(Window=types.SimpleNamespace(list_toplevels=lambda: wins))
rep.GdkX11 = types.SimpleNamespace(X11Window=X11Window)
gi.repository = rep; sys.modules["gi"] = gi; sys.modules["gi.repository"] = rep
ns = {"TITLES": {"card": "Dewiar", "mini": "Dewiar — значок"}, "PAD_TITLE": "Dewiar — блокнот", "ABOVE_TITLES": None, "sys": sys,
      "ON_TOP": [True]}                                          # 0.68: «Виджет поверх всех окон» можно выключить (№48)
exec(ast.get_source_segment(src, fn), ns)
r = ns["keep_above_guard"]()
ok(r is True and wins[0].calls == [False, True], f"виджет потерял «поверх» — поставлен снова: {wins[0].calls}")
ok(wins[1].calls == [] and wins[2].calls == [] and wins[3].calls == [], "блокнот и так поверх, спрятанный значок и чужие окна — не трогаем")
ns["keep_above_guard"]()
ok(wins[0].calls == [False, True], "второй круг — всё уже поверх, ничего не делаем")
# выключили «поверх» (идея №48) — виджет не поднимаем, блокнот — по-прежнему
ns["ON_TOP"][0] = False
wins[0].gdw.above = False; wins[0].calls = []; wins[1].gdw.above = False; wins[1].calls = []
ns["keep_above_guard"]()
ok(wins[0].calls == [] and wins[1].calls == [False, True], f"«поверх» выключен — виджет не поднимаем, блокнот поднимаем: {wins[0].calls} {wins[1].calls}")
ok("GLib.timeout_add_seconds(3, keep_above_guard)" in src, "сторож запускается с интерфейсом (Linux)")

if fails:
    raise SystemExit(1)
