"""№688 (13.11, Windows 11): окно суфлёра тащишь за шапку — «курсор телепортируется в сторону, перемещение непривычное».
Перетаскивание pywebview считает по screenX/screenY страницы, а при масштабе экрана Windows это не те пиксели. Теперь на
Windows окно ведёт программа — туда, где курсор (drag_begin / drag_step, как виджет, №169); кнопки шапки не тащат;
на Linux шапку по-прежнему двигает оконный менеджер."""
import os, shutil, sys, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


tmp = Path(tempfile.mkdtemp()) / "ui"
shutil.copytree(ROOT / "ui", tmp)
(tmp / "assets/dewiar.js").write_text("""
window.CALLS = [];
window.pywebview = { api: { close_prompter() {}, open_settings() {},
  async drag_begin(m) { CALLS.push(['drag_begin', m]); return true; }, async drag_step(m) { CALLS.push(['drag_step', m]); return true; } } };
window.api = () => window.pywebview.api;
window.core = { _on: {}, on(k, f) { (this._on[k] = this._on[k] || []).push(f); }, emit(k, d) { (this._on[k] || []).forEach(f => f(d)); },
  async call(cmd, a) { if (cmd === 'prompter_state') return { on: false, hints: [], lines: [], files: [], sheet: [], hear: {} }; return {}; } };
""", encoding="utf-8")
with sync_playwright() as pw:
    b = pw.chromium.launch()
    for plat, win in (("Win32", True), ("Linux x86_64", False)):
        pg = b.new_page(viewport={"width": 440, "height": 690})
        pg.add_init_script(f"Object.defineProperty(navigator, 'platform', {{ get: () => '{plat}' }})")
        pg.goto((tmp / "prompter.html").as_uri()); pg.wait_for_timeout(500)
        cls = pg.evaluate("document.querySelector('header').className")
        box = pg.locator("header .t").bounding_box()
        pg.mouse.move(box["x"] + 10, box["y"] + 10); pg.mouse.down()
        for i in range(6):
            pg.mouse.move(box["x"] + 10 + i * 12, box["y"] + 10 + i * 4); pg.wait_for_timeout(40)
        pg.mouse.up(); pg.wait_for_timeout(100)
        calls = pg.evaluate("CALLS.map(c => c.join(':'))")
        if win:
            ok("pywebview-drag-region" not in cls and "drag_begin:prompter" in calls and calls.count("drag_step:prompter") >= 2,
               f"Windows: окно ведёт программа (drag_begin / drag_step), не pywebview: {calls[:4]}")
            n = len(calls); bb = pg.locator("#b-close").bounding_box()
            pg.evaluate("window.pywebview.api.close_prompter = () => CALLS.push(['close'])")
            pg.mouse.click(bb["x"] + 5, bb["y"] + 5); pg.wait_for_timeout(100)
            ok(not [c for c in pg.evaluate("CALLS.map(c => c.join(':'))")[n:] if c.startswith("drag")], "нажатие на кнопку шапки — не перетаскивание")
        else:
            ok("pywebview-drag-region" in cls and not [c for c in calls if c.startswith("drag")], "Linux: как раньше — шапку двигает оконный менеджер")
        pg.close()
    b.close()
src = (ROOT / "ui/app.py").read_text(encoding="utf-8")
ok('if mode == "prompter":' in src, "программа знает окно суфлёра (_hwnd)")
print("ИТОГ:", "всё прошло" if not fails else f"{len(fails)} ошибок")
sys.exit(1 if fails else 0)
