"""№375–376 (28.10, Windows 10): нажал «Блокнот» — появилось пустое окно, и кнопка больше ничего не делает; помог только
перезапуск программы. В журнале: «WebView2 initialization failed: Класс не зарегистрирован», потом каждое нажатие —
«Main window failed to start»: окно есть, страницы в нём нет, а «закрыть» отправлялось странице.
Теперь: страница не поднялась за PAD_WAIT — окно убирается и создаётся заново (один раз); не вышло — у виджета сказано,
что делать, и кнопка снова работает. Клик, пока лист ещё грузится, — не закрывает пустое окно. Студия так же: окно без
страницы при следующем «открыть» пересоздаётся."""
import os, sys, threading, time
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "ui")); sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import app  # noqa: E402


class Ev:
    def __init__(self): self.e = threading.Event(); self.cbs = []
    def __iadd__(self, cb): self.cbs.append(cb); return self
    def is_set(self): return self.e.is_set()
    def set(self): self.e.set(); [c() for c in self.cbs]


class Win:
    made = []

    def __init__(self, ok_page):
        self.events = type("E", (), {})()
        for n in ("loaded", "closed", "shown"):
            setattr(self.events, n, Ev())
        self.destroyed = False; self.js = []
        Win.made.append(self)
        if ok_page:
            self.events.loaded.set()
    def destroy(self): self.destroyed = True
    def show(self): pass
    def hide(self): pass
    def evaluate_js(self, code):
        if not self.events.loaded.is_set():
            raise RuntimeError("Main window failed to start")
        self.js.append(code)


a = app.Api.__new__(app.Api)
a.mode = "card"
said = []
a._js = lambda code: said.append(code)
a._stay = lambda: None
a._pad_geom = lambda: {"side": "left", "gap": 8, "clips": [], "w": 300, "h": 400, "x": 0, "y": 0, "dy": 0}
a._pad_place = lambda *x: None
a._pad_shape = lambda *x: None
a._url = lambda *x: "x"
a._gtk = lambda fn, timeout=2: True
a.PAD_WAIT = 0.4
app.WIN = True
plan = []                                                   # какие окна «поднимутся»: False — пустое (WebView2 сбой)
import webview  # noqa: E402
webview.create_window = lambda *x, **k: Win(plan.pop(0) if plan else True)

plan[:] = [False, True]
a.pad_open("notes")
w1 = Win.made[-1]
ok(a._pad is w1 and a._pad_on, "первое окно создано")
ok(a.pad_toggle("notes") is True and not w1.destroyed, "клик, пока лист грузится, — не закрывает и не ломает")
time.sleep(0.9)
w2 = Win.made[-1]
ok(w1.destroyed and w2 is not w1 and a._pad is w2 and w2.events.loaded.is_set(), "страница не поднялась — окно убрано и создано заново")
a.pad_toggle("notes")
ok(any("padClose" in c for c in w2.js), "теперь кнопка закрывает лист, как обычно")

# оба раза пусто — сказано у виджета, кнопка снова работает
a._pad, a._pad_on, a._pad_tries = None, False, 0
plan[:] = [False, False, True]
said.clear()
a.pad_open("notes"); time.sleep(0.6); time.sleep(0.6)
ok(any("padFail" in c and "перезапустите Dewiar" in c for c in said) and a._pad is None and not a._pad_on, f"и второй раз пусто — сказано, что делать: {[c for c in said if 'padFail' in c][:1]}")
ok(a.pad_toggle("notes") is True and a._pad is Win.made[-1] and a._pad_on, "следующий клик — снова пробует, а не молчит")

# окно было, а теперь мёртвое (старый случай: кнопка давно нажата) — клик пересоздаёт
dead = Win(False); a._pad, a._pad_on, a._pad_born = dead, True, time.monotonic() - 5
plan[:] = [True]
a.pad_toggle("notes")
ok(dead.destroyed and a._pad is not dead and a._pad.events.loaded.is_set(), "мёртвое окно — клик создаёт новое")

# _pad_js не роняет поток на мёртвом окне
a._pad = Win(False)
try:
    a._pad_js("1"); time.sleep(0.1); ok(True, "команда пустому окну — без падения потока")
except Exception as e:  # noqa: BLE001
    ok(False, f"команда пустому окну упала: {e}")

src = (ROOT / "ui/app.py").read_text(encoding="utf-8")
ok("not self._studio.events.loaded.is_set() and time.monotonic() - getattr(self, \"_studio_born\", 0) > 15" in src, "студия без страницы — при следующем «открыть» окно заново")
hud = (ROOT / "ui/hud.html").read_text(encoding="utf-8")
ok("window.padFail" in hud and "Date.now() > padFailUntil" in hud, "у виджета сообщение держится, проверка связи его не стирает")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
