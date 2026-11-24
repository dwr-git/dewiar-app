"""№364 (20.11, Денис: «окно суфлёра фиксированного размера, а текста в нём много — читать неудобно; тянуть за край, с
запоминанием между запусками»). Теперь уголок внизу справа тянет окно (не меньше 360×420), отпустили — размер в
настройки (ui.prompter_w / prompter_h), следующее окно откроется таким же; двойной щелчок — прежний размер."""
import os, re, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
bad = 0


def ok(c, m):
    global bad
    bad += 0 if c else 1
    print(("✅ " if c else "❌ ") + m)


app = (ROOT / "ui/app.py").read_text(encoding="utf-8")
html = (ROOT / "ui/prompter.html").read_text(encoding="utf-8")
ok('"prompter_resize", "prompter_size"' in app and "def prompter_resize(self, w, h, final=False):" in app, "мост окна: размер суфлёра")
ok("resizable=True, min_size=PROMPTER_MIN" in app and 'ui.get("prompter_w")' in app, "окно тянется, не меньше наименьшего; открывается своим размером")
body = app.split("def prompter_resize", 1)[1].split("\n    def ", 1)[0]
ok("winshell.shape(hwnd, \"prompter\", PROMPTER_RADIUS)" in body and "shape_window(gw, \"prompter\", (w, h), PROMPTER_RADIUS)" in body,
   "скругление — заново по новому размеру (Windows и Linux)")
ok('id="grip"' in html and "a.prompter_resize(last[0], last[1], true).then(save)" in html and "prompter_w: b[0], prompter_h: b[1]" in html,
   "уголок в окне: тянуть и запомнить")
ok('"prompter_w": None, "prompter_h": None' in (ROOT / "core/settings.py").read_text(encoding="utf-8"), "настройки знают размер суфлёра")
print("ИТОГ:", "всё в порядке" if not bad else f"ошибок {bad}")
sys.exit(1 if bad else 0)
