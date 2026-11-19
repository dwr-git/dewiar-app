"""Идея №190 (13.11): «перешёл по ссылке — не хватает кнопки вернуться, откуда пришёл». В студии — «назад», как в браузере:
боковая кнопка мыши «назад» и Alt+← возвращают в прошлый раздел; без новой кнопки на экране."""
import os, re, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


CUR = "document.querySelector('section.cur').id"
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 1400, "height": 1000}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route(re.compile(r"^https?://"), lambda r: r.abort())
    pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };")
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(900)
    pg.evaluate("() => { S = Object.assign({}, S || {}, { features: {}, ui: {} }); core.call = (c) => Promise.resolve(c === 'pay_overview' ? { bills: [] } : {}); }")
    for sec in ("look", "notes", "features"):
        pg.click(f'nav button[data-p="{sec}"]'); pg.wait_for_timeout(150)
    ok(pg.evaluate(CUR) == "p-features", "открыли «Оформление» → «Заметки» → «Возможности»")
    pg.keyboard.press("Alt+ArrowLeft"); pg.wait_for_timeout(150)
    ok(pg.evaluate(CUR) == "p-notes", "Alt+← — назад в «Заметки»")
    pg.mouse.move(700, 500); pg.evaluate("() => document.dispatchEvent(new MouseEvent('mouseup', { button: 3 }))"); pg.wait_for_timeout(150)
    ok(pg.evaluate(CUR) == "p-look", "боковая кнопка мыши «назад» — ещё раз назад")
    pg.keyboard.press("Alt+ArrowLeft"); pg.wait_for_timeout(150)
    ok(pg.evaluate(CUR) in ("p-home", "p-look"), "дальше некуда — остаёмся (или «Главная», откуда начали)")
    pg.click('nav button[data-p="notes"]'); pg.wait_for_timeout(150)
    pg.focus("body"); pg.evaluate("() => { const i = document.createElement('input'); i.id = 'tmpi'; document.body.appendChild(i); i.focus(); }")
    pg.keyboard.press("Alt+ArrowLeft"); pg.wait_for_timeout(150)
    ok(pg.evaluate(CUR) == "p-notes", "в поле ввода Alt+← — не уходит из раздела")
    b.close()
ok(not errs, "без ошибок JavaScript" + (f": {errs[:3]}" if errs else ""))
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
