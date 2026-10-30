"""30.10 (пользователь): «при клике на чат в виджете — свернуть/развернуть окно приложения, так же заметки, календарь:
первый клик — открытие, второй — сворачивание». Api.toggle_settings: первое нажатие — студия на разделе; второе подряд —
сворачивается; раздел в студии сменили или студию свернули сами — снова открывает."""
import os, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "ui")); sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import app  # noqa: E402
app._ui_log = lambda *a, **k: None


class Win:
    def __init__(self):
        self.page, self.mins = "", 0

    def evaluate_js(self, js):
        return self.page

    def minimize(self):
        self.mins += 1


api = app.Api.__new__(app.Api)
api._studio, api._toggled, api._studio_minimized = None, "", False
opened = []


def fake_open(page=""):
    if api._studio is None:
        api._studio = Win()
    api._studio.page = page
    opened.append(page)


api.open_settings = fake_open
ok(api.toggle_settings("chat") == "open" and opened == ["chat"], "первое нажатие «Чат» — студия на «Чате»")
ok(api.toggle_settings("chat") == "min" and api._studio.mins == 1, "второе подряд — студия свернулась")
ok(api.toggle_settings("chat") == "open" and opened[-1] == "chat", "третье — снова открыта (после сворачивания)")
ok(api.toggle_settings("notes") == "open" and opened[-1] == "notes", "другая кнопка — открывает свой раздел, не сворачивает")
api._studio.page = "calendar"                                     # в студии перешли в «Календарь»
ok(api.toggle_settings("notes") == "open" and opened[-1] == "notes", "раздел в студии сменили — «Заметки» снова открывают, а не сворачивают")
api._studio_minimized = True                                      # свернули студию сами (кнопкой окна)
ok(api.toggle_settings("notes") == "open", "студию свернули сами — нажатие разворачивает")
hud = (ROOT / "ui/hud.html").read_text(encoding="utf-8")
ok(all(f'$("{b}").onclick = () => studioToggle(' in hud for b in ("b-chat", "b-notes", "b-cal", "b-watch", "b-idea")),
   "виджет: «Чат», «Заметки», «Календарь», «Дозор», «Идеи» — через toggle")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
