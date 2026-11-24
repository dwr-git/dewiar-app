"""Владелец 24.11 (Ubuntu): «виджет всегда выше всех — открываю студию, она под виджетом… на чём фокус, то и выше».
Пока студия в фокусе — окна Лиры не «поверх всех»; ушли из студии — снова поверх; «поверх всех» выключено — не трогаем."""
import os, sys, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    c or fails.append(m)


src = (ROOT / "ui/app.py").read_text(encoding="utf-8")
i = src.index("    def _studio_focus_hook(self):"); j = src.index("\n    def _studio_gw(self):", i)
state = {}


class GW:
    def __init__(self):
        self.h, self.act = {}, False

    def connect(self, sig, fn):
        self.h[sig] = fn

    def is_active(self):
        return self.act


class Win:
    def __init__(self):
        self.above = None

    def set_keep_above(self, v):
        self.above = v


wa, wb = Win(), Win()
gtkmod = types.ModuleType("webview.platforms.gtk")
gtkmod.BrowserView = type("BV", (), {"instances": {"a": types.SimpleNamespace(window=wa), "b": types.SimpleNamespace(window=wb)}})
sys.modules["webview.platforms.gtk"] = gtkmod
ON_TOP = [True]
FRONT = [False]
ns = {"ON_TOP": ON_TOP, "STUDIO_FRONT": FRONT, "_ui_log": print}
exec("class A:\n" + src[i:j] + "\n", ns)
a = ns["A"](); g = GW()
a._studio_gw = lambda: g
a.wins = {"mini": types.SimpleNamespace(uid="a"), "card": types.SimpleNamespace(uid="b")}
a._studio_focus_hook()
ok(wa.above is True and wb.above is True, "студия не в фокусе — Лира поверх")
g.act = True; g.h["notify::is-active"](g)
ok(wa.above is False and wb.above is False, "студия в фокусе — окна Лиры не перекрывают её")
ok(FRONT[0] is True, "студия в фокусе — сторож «поверх окон» не поднимает Лиру обратно")
ok("if STUDIO_FRONT[0]:" in src[src.index("def keep_above_guard"):src.index("def keep_above_guard") + 2500], "сторож «поверх окон» смотрит на фокус студии")
g.act = False; g.h["notify::is-active"](g)
ok(wa.above is True and FRONT[0] is False, "ушли из студии — снова поверх")
ON_TOP[0] = False; g.act = True; wa.above = "x"; g.h["notify::is-active"](g)
ok(wa.above == "x", "«поверх всех» выключено — не трогаем")
ON_TOP[0] = True; g.act = True; g.h["notify::is-active"](g); g.h["destroy"]()
ok(wa.above is True, "студию закрыли — Лира снова поверх")

# Windows: то же по событиям формы студии (Activated / Deactivate / FormClosed), TopMost — через _topmost_ui в потоке
i = src.index("    def _studio_focus_win(self, win):"); j = src.index("\n    def _studio_focus_hook(self):", i)


class Ev:
    def __init__(self):
        self.fns = []

    def __iadd__(self, fn):
        self.fns.append(fn)
        return self

    def fire(self):
        for fn in self.fns:
            fn(None, None)


form = types.SimpleNamespace(Activated=Ev(), Deactivate=Ev(), FormClosed=Ev())
wfmod = types.ModuleType("webview.platforms.winforms")
wfmod.BrowserView = type("BV", (), {"instances": {"st": form}})
sys.modules["webview.platforms.winforms"] = wfmod
top = {}


class T:
    def __init__(self, target, args, daemon):
        self.f, self.a = target, args

    def start(self):
        self.f(*self.a)


import threading  # noqa: E402
threading.Thread = T
ns2 = {"ON_TOP": ON_TOP, "_ui_log": print, "_topmost_ui": lambda w, on: top.__setitem__(w.uid, on)}
exec("class B:\n" + src[i:j] + "\n", ns2)
b = ns2["B"](); st = types.SimpleNamespace(uid="st")
b.wins = {"mini": types.SimpleNamespace(uid="a"), "card": types.SimpleNamespace(uid="b")}
b._studio_focus_win(st)
ok(top == {"a": False, "b": False}, f"Windows: студия открылась (активна) — окна Лиры без TopMost: {top}")
form.Deactivate.fire()
ok(top == {"a": True, "b": True}, "Windows: ушли из студии — снова поверх")
form.Activated.fire()
ok(top["a"] is False, "Windows: вернулись в студию — она впереди")
form.FormClosed.fire()
ok(top["a"] is True, "Windows: студию закрыли — Лира снова поверх")
b._studio_focus_win(st)
ok(len(form.Activated.fns) == 1, "Windows: к одной форме подключаемся один раз")
ON_TOP[0] = False; top.clear(); form.Deactivate.fire()
ok(top == {}, "Windows: «поверх всех» выключено — не трогаем")
print("ИТОГ: " + ("всё прошло" if not fails else f"провалов {len(fails)}"))
sys.exit(1 if fails else 0)
