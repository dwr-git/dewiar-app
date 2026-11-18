"""№834 (17.11, Windows, масштаб 80 %): «открываешь главное окно — шрифт крупный, сворачиваешь Лиру — шрифт уменьшается,
что-то исчезает из меню». Масштаб из настроек и видимость разделов ставились только при ответе ядра (hello), а если там
что-то падало — только при первом изменении настроек (свернули виджет — сохранилось его место). Теперь масштаб — сразу
из адреса окна (ui/app.py, macui: &zoom=…&text=…) или из запомненного, а refreshStatic в hello — первым и отдельно."""
import json, os, sys, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


tmp = Path(tempfile.mkdtemp())
sys.path.insert(0, str(ROOT / "ui")); sys.path.insert(0, str(ROOT / "core"))
import app as A  # noqa: E402
A.SETTINGS_PATH = tmp / "settings.json"
A.SETTINGS_PATH.write_text(json.dumps({"ui": {"zoom": 0.8, "text": 0.95}}), encoding="utf-8")
ok(A.ui_zoom_q() == "&zoom=0.8&text=0.95", f"адрес студии несёт масштаб и текст: {A.ui_zoom_q()}")
A.SETTINGS_PATH.write_text(json.dumps({"ui": {"zoom": 1}}), encoding="utf-8")
ok(A.ui_zoom_q() == "", "обычный размер — в адресе ничего лишнего")
src = (ROOT / "ui/app.py").read_text(encoding="utf-8") + (ROOT / "ui/macui.py").read_text(encoding="utf-8")
ok(src.count("ui_zoom_q()") >= 2, "и Windows/Linux, и Mac открывают студию с масштабом в адресе")
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1366, "height": 768}); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?zoom=0.8&text=0.95"); pg.wait_for_timeout(600)
    z = pg.evaluate("() => [document.documentElement.style.zoom, getComputedStyle(document.documentElement).getPropertyValue('--dw-text').trim()]")
    ok(z == ["0.8", "0.95"], f"студия сразу в своём масштабе, ещё до связи с ядром: {z}")
    pg.evaluate("() => localStorage.setItem('studio_zoom', JSON.stringify({zoom: 0.9, text: 1}))")
    pg.goto((ROOT / "ui/settings.html").as_uri()); pg.wait_for_timeout(600)
    z2 = pg.evaluate("() => document.documentElement.style.zoom")
    ok(z2 == "0.9", f"без адреса — последний запомненный масштаб: {z2}")
    b.close()
dj = (ROOT / "ui/studio/dewiar.js").read_text(encoding="utf-8")
ok("for (const f of [refreshStatic, renderPersonas" in dj, "в hello масштаб и разделы — первыми, сбой отрисовки их не отменяет")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
