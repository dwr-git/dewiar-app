"""Идея №112 (02.11): «в чате отключено контекстное меню для копирования текста, Ctrl+C неудобно». Окна pywebview прячут
меню WebView2 — теперь своё: на выделенном тексте «Копировать», в поле — ещё «Вырезать» и «Вставить»; мимо — ничего."""
import os, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


for f in ("ui/settings.html", "ui/pad.html", "ui/hud.html"):
    ok("assets/ctxmenu.js" in (ROOT / f).read_text(encoding="utf-8"), f"{f}: меню правой кнопки подключено")
with sync_playwright() as p:
    b = p.chromium.launch(); ctx = b.new_context(permissions=["clipboard-read", "clipboard-write"]); pg = ctx.new_page()
    HTML = "<html><body><p id='t'>Ответ Лиры про погоду</p><textarea id='a'>моё</textarea><div id='e' style='height:40px'></div></body></html>"
    pg.route("https://dewiar.test/", lambda r: r.fulfill(body=HTML, content_type="text/html; charset=utf-8"))
    pg.goto("https://dewiar.test/")                   # буфер обмена — только на защищённой странице
    pg.add_script_tag(path=str(ROOT / "ui/assets/ctxmenu.js"))
    pg.click("#e", button="right"); ok(pg.locator(".dwcm").count() == 0, "мимо текста и полей — меню нет")
    pg.evaluate("() => { const r = document.createRange(); r.selectNodeContents(document.querySelector('#t')); getSelection().removeAllRanges(); getSelection().addRange(r); }")
    pg.click("#t", button="right"); pg.wait_for_timeout(100)
    items = pg.evaluate("[...document.querySelectorAll('.dwcm button span')].map(x => x.textContent)")
    ok(items == ["Копировать", "Выделить всё"], f"на выделенном ответе — «Копировать»: {items}")
    pg.click(".dwcm button >> nth=0"); pg.wait_for_timeout(150)
    ok(pg.evaluate("navigator.clipboard.readText()") == "Ответ Лиры про погоду" and pg.locator(".dwcm").count() == 0, "скопировано, меню закрылось")
    pg.click("#a"); pg.keyboard.press("End"); pg.click("#a", button="right"); pg.wait_for_timeout(100)
    items = pg.evaluate("[...document.querySelectorAll('.dwcm button span')].map(x => x.textContent)")
    ok(items == ["Копировать", "Вырезать", "Вставить", "Выделить всё"], f"в поле — и «Вставить»: {items}")
    pg.click(".dwcm button >> nth=2"); pg.wait_for_timeout(200)
    ok(pg.input_value("#a").endswith("Ответ Лиры про погоду"), f"вставлено: {pg.input_value('#a')!r}")
    b.close()
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
