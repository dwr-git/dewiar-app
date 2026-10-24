"""23.10, владелец: «ложная сработка, Лира стала слушать быстрые разговоры издалека, потом виджет исчез, остался только
блокнот — смотрится странно». Виджет был «в трее» (так он начинает после автозапуска и перезапуска с обновлением, если
его когда-то убирали в трей): на имя он показывается сам, а после разговора прячется обратно (tray_back). Блокнот рядом
при этом оставался один. Теперь открытый блокнот значит «человек работает»: виджет выходит из трея насовсем и не прячется."""
import ast, os
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


src = (ROOT / "ui/app.py").read_text(encoding="utf-8")
tree = ast.parse(src)
api = next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and any(
    isinstance(f, ast.FunctionDef) and f.name == "tray_back" for f in n.body))
want = {"tray_back", "_stay", "to_tray"}
mod = ast.Module(body=[f for f in api.body if isinstance(f, ast.FunctionDef) and f.name in want], type_ignores=[])
ns = {"WIN": False, "_notify": lambda *a: None}
exec(compile(mod, "app.py", "exec"), ns)


class Fake:
    _tray = True
    tray_back, _stay, to_tray = ns["tray_back"], ns["_stay"], ns["to_tray"]

    def __init__(self, pad):
        self.in_tray, self.popped, self._pad_on = True, True, pad
        self.hidden, self.js = 0, []

    def _hide_now(self):
        self.hidden += 1

    def _js(self, code):
        self.js.append(code)

    def pad_hide(self):
        self._pad_on = False


a = Fake(pad=True)                       # показался из трея на имя, рядом открыт блокнот
a.tray_back()
ok(a.hidden == 0, "после разговора виджет с открытым блокнотом не прячется")
ok(not a.in_tray and not a.popped, "и выходит из трея насовсем")
ok(any("trayLeft" in c for c in a.js), "запомнено: при следующем запуске — на экране (trayLeft → ui.hud_tray=false)")

b = Fake(pad=False)                      # показался из трея на имя, блокнота нет — как раньше, прячется обратно
b.tray_back()
ok(b.hidden == 1 and b.in_tray, "без блокнота — после разговора обратно в трей, как раньше")

c = Fake(pad=True)                       # кнопка «В трей» прячет и блокнот (и вернёт его потом)
c.in_tray, c.popped = False, False
c.to_tray(quiet=True)
ok(c.hidden == 1 and c._pad_on is False and c._pad_back is True, "кнопка «В трей» по-прежнему прячет виджет вместе с блокнотом")

body = src[src.index("    def pad_open(self, mode=\"notes\"):"):src.index("    def pad_hide(self):")]
ok(body.index("self._stay()") < body.index("self._pad_on = g"), "открыть блокнот у показавшегося из трея виджета — выйти из трея")

if fails:
    raise SystemExit(1)
