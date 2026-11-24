"""Владелец 24.11 (Ubuntu): «виджет всегда выше всех — открываю студию, она под виджетом… на чём фокус, то и выше».
16:49 (1.0.66, «стало только хуже»): нажал «Студия» в виджете — виджет мигнул, блокнот остался сверху, студия вышла и тут же
спряталась под виджет; выбираю студию — всё равно под ним. Причины: открытие снимало «поверх» со студии через 0,7 с, даже когда
в ней уже работают, а окна Лиры опускались (кроме блокнота). Теперь окна Лиры не трогаем вовсе: пока студия активна, она сама
«поверх всех» и впереди них; ушли — обычное окно. «Поверх всех» у Лиры выключено — не трогаем."""
import os, re, sys, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    c or fails.append(m)


src = (ROOT / "ui/app.py").read_text(encoding="utf-8")
i = src.index("    def _studio_focus_hook(self):"); j = src.index("\n    def _studio_gw(self):", i)
hook = src[i:j]


class GW:
    def __init__(self):
        self.h, self.act, self.above = {}, False, None

    def connect(self, sig, fn):
        self.h[sig] = fn

    def is_active(self):
        return self.act

    def set_keep_above(self, v):
        self.above = v


ON_TOP, FRONT = [True], [False]
ns = {"ON_TOP": ON_TOP, "STUDIO_FRONT": FRONT, "_ui_log": print}
exec("class A:\n" + hook + "\n", ns)
a = ns["A"](); g = GW()
a._studio_gw = lambda: g
a._studio_focus_hook()
ok(g.above is False and FRONT[0] is False, "студия не в фокусе — обычное окно, Лира поверх")
g.act = True; g.h["notify::is-active"](g)
ok(g.above is True and FRONT[0] is True, "студия в фокусе — сама «поверх всех», впереди виджета и блокнота")
g.act = False; g.h["notify::is-active"](g)
ok(g.above is False and FRONT[0] is False, "ушли из студии — снова обычное окно")
ok("wins" not in hook and "set_keep_above(above)" not in hook, "окна Лиры (виджет, блокнот) студия не трогает — не мигают")
ON_TOP[0] = False; g.above = "x"; g.act = True; g.h["notify::is-active"](g)
ok(g.above == "x" and FRONT[0] is False, "«поверх всех» у Лиры выключено — студии слой не нужен")
ON_TOP[0] = True; g.act = True; g.h["notify::is-active"](g); g.h["destroy"]()
ok(FRONT[0] is False, "студию закрыли — сторож снова следит за окнами Лиры")
a._studio_focus_hook()
ok(len(g.h) == 2, "к окну студии подключаемся один раз")

# открытие: «на миг поверх» не снимается, если студия уже активна (иначе она пряталась под виджет через 0,7 с)
r = src[src.index("    def _raise_studio(self):"):src.index("    def _studio_resized(")]
ok("ON_TOP[0] and gw.is_active()" in r, "открытие: «поверх» со студии не снимается, пока в ней работают")
# сторож «поверх окон» не переподнимает виджет над активной студией
gsrc = src[src.index("def keep_above_guard"):src.index("def keep_above_guard") + 2500]
ok("if STUDIO_FRONT[0]:" in gsrc, "сторож «поверх окон» не поднимает Лиру над активной студией")
ok(re.search(r"win\.events\.shown \+= lift", src) is not None, "Linux: подключение при показе студии")

# Windows: то же по событиям формы студии — TopMost у самой студии, окна Лиры не трогаем
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


form = types.SimpleNamespace(Activated=Ev(), Deactivate=Ev())
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
ON_TOP[0] = True
ns2 = {"ON_TOP": ON_TOP, "STUDIO_FRONT": FRONT, "_ui_log": print, "_topmost_ui": lambda w, on: top.__setitem__(w.uid, on)}
exec("class B:\n" + src[i:j] + "\n", ns2)
b = ns2["B"](); st = types.SimpleNamespace(uid="st")
b.wins = {"mini": types.SimpleNamespace(uid="a")}
b._studio_focus_win(st)
ok(top == {"st": True}, f"Windows: студия открылась — сама TopMost, виджет не трогаем: {top}")
form.Deactivate.fire()
ok(top == {"st": False}, "Windows: ушли из студии — обычное окно")
form.Activated.fire()
ok(top["st"] is True, "Windows: вернулись в студию — она впереди")
b._studio_focus_win(st)
ok(len(form.Activated.fns) == 1, "Windows: к одной форме подключаемся один раз")
ON_TOP[0] = False; top.clear(); form.Activated.fire()
ok(top == {}, "Windows: «поверх всех» выключено — не трогаем")
print("ИТОГ: " + ("всё прошло" if not fails else f"провалов {len(fails)}"))
sys.exit(1 if fails else 0)
