"""Владелец 25.11, блокнот у виджета:
1) «если были пустые строки (переходы на следующую строку) — после обновления Лиры они исчезают» — Markdown схлопывает
   пустые строки; пустой абзац теперь пишется строкой из неразрывного пробела и читается обратно пустым абзацем;
2) «выделить текст и нажать H1 — станет крупнее, и так сколько угодно, текст гигантский» — заголовок вкладывался в
   заголовок (размер в em рос). Теперь повторное H1 — снова абзац; в пункте списка строка выходит из списка."""
import json, os, sys, urllib.parse
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


from playwright.sync_api import sync_playwright  # noqa: E402
FAKE = "window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };"
TEXT = "# Важное\n\nПервая строка\n\n \n\n \n\nПосле двух пустых\n\n1. Раз\n2. Два\n3. Сколько времени в офисе?\n"
CORE = r"""
(() => { const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; try { core.ws.close(); } catch (e) {} }
    core.connected = true;
    core.call = async (c, a) => {
      if (c === "pad_tabs") return { tabs: [{ name: "Главное", mtime: 1 }], active: "Главное" };
      if (c === "pad_read") return { name: a.name, text: %s, mtime: 1 };
      return {}; }; };
  ready(); })();
""" % json.dumps(TEXT, ensure_ascii=False)
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 700, "height": 700}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.add_init_script(FAKE); pg.add_init_script(CORE)
    pg.goto((ROOT / "ui/pad.html").as_uri() + "?skin=neusky&cfg=" + urllib.parse.quote(json.dumps({"side": "right", "gap": 14, "clips": []})))
    pg.wait_for_timeout(1200)
    md = lambda: pg.evaluate("PadMD.html2md(document.querySelector('#ed').innerHTML)")
    ok(pg.evaluate("[...document.querySelectorAll('#ed > p')].filter(p => !p.textContent.trim()).length") >= 2, "две пустые строки — на месте после открытия")
    ok(md() == TEXT, f"сохраняется так же, как было: {md()!r}")
    # пустая строка, сделанная Enter, переживает сохранение и открытие
    rt = pg.evaluate("PadMD.html2md(PadMD.md2html(PadMD.html2md('<p>А</p><p><br></p><p>Б</p><p><br></p>')))")
    ok(rt == "А\n\n \n\nБ\n", f"Enter → пустая строка между абзацами сохраняется, хвостовая — нет: {rt!r}")
    # H1 по выделению: много раз — не растёт
    pg.evaluate("""() => { const p = [...document.querySelectorAll('#ed > p')].find(x => x.textContent === 'Первая строка');
        const r = document.createRange(); r.selectNodeContents(p); const s = getSelection(); s.removeAllRanges(); s.addRange(r); }""")
    for _ in range(4):
        pg.click('#tools .tool[data-c="h1"]'); pg.wait_for_timeout(80)
    ok(pg.locator("#ed h1 h1, #ed h1 h2, #ed h2 h1").count() == 0, "H1 много раз — заголовок не вкладывается в заголовок")
    sizes = pg.evaluate("[...document.querySelectorAll('#ed h1')].map(h => parseFloat(getComputedStyle(h).fontSize))")
    ok(sizes and max(sizes) <= 40, f"размер заголовка не растёт: {sizes}")
    ok("Первая строка" in md() and "# # " not in md(), f"чётное число нажатий — снова абзац или заголовок, без мусора: {md()!r}")
    # H1 в пункте списка — строка выходит из списка, номер не становится гигантским
    pg.evaluate("""() => { const li = [...document.querySelectorAll('#ed li')].find(x => x.textContent.includes('Сколько времени'));
        const r = document.createRange(); r.selectNodeContents(li); const s = getSelection(); s.removeAllRanges(); s.addRange(r); }""")
    pg.click('#tools .tool[data-c="h1"]'); pg.wait_for_timeout(120)
    ok(pg.locator("#ed li h1").count() == 0 and "# Сколько времени в офисе?" in md(), f"H1 в пункте списка — отдельный заголовок, не огромный номер: {md()!r}")
    ok(not errs, f"без ошибок на странице: {errs}")
    b.close()
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
