"""№466 (01.11, ПК 0.76.0, Ubuntu): «Добавил в текстовый редактор блок „Код“ — и его никак не удалить, он только двигается
по странице». В блокноте у виджета (ui/pad.js) Backspace в пустом блоке кода ничего не делал, а Delete втягивал в блок
следующий абзац. Теперь: Backspace в начале — снова обычный текст, в пустом — блок убран; Delete в пустом — убран;
кнопка «Код» в блоке — убирает его; Enter на пустой последней строке — выход из блока."""
import json, os, sys, urllib.parse
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


CORE = r"""
(() => { window.calls = [];
  const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.connected = true;
    core.call = async (c, a) => { calls.push([c, a]);
      if (c === "pad_tabs") return { tabs: [{ name: "Главное", mtime: 1 }], active: "Главное" };
      if (c === "pad_read") return { name: a.name, text: "bbb\n\nВот сервер с скриптом\n\nвторая строка\n", mtime: 1 };
      if (c === "pad_write") return { mtime: 2 };
      return {}; }; };
  ready(); })();
"""
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 454, "height": 600})
    pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };"); pg.add_init_script(CORE)
    pg.goto((ROOT / "ui/pad.html").as_uri() + "?skin=neusky&cfg=" + urllib.parse.quote(json.dumps({"side": "right", "gap": 14, "clips": []})))
    pg.wait_for_timeout(1200)
    h = lambda: pg.evaluate("document.querySelector('#ed').innerHTML")
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    h = lambda: pg.evaluate("document.querySelector('#ed').innerHTML")
    md = lambda: pg.evaluate("PadMD.html2md(document.querySelector('#ed').innerHTML)")

    def code_first():
        pg.click("#ed > :first-child"); pg.keyboard.press("End"); pg.click("#tools .tool[data-c=code]"); pg.wait_for_timeout(150)
    code_first()
    ok(h().startswith("<pre>bbb</pre>"), f"кнопка «Код» — строка стала блоком кода: {h()[:60]}")
    pg.keyboard.press("Home"); pg.keyboard.press("Backspace"); pg.wait_for_timeout(100)
    ok(h().startswith("<p>bbb</p>") and "<pre" not in h(), f"Backspace в начале блока — снова обычный текст: {h()[:60]}")
    code_first(); pg.keyboard.press("End")
    for _ in range(3):
        pg.keyboard.press("Backspace")
    ok(h().startswith("<pre"), "стёрли текст — пустой блок ещё на месте")
    pg.keyboard.press("Backspace"); pg.wait_for_timeout(100)
    ok("<pre" not in h() and h().startswith("<p><br></p><p>Вот сервер"), f"Backspace в пустом блоке — блока нет: {h()[:70]}")
    pg.evaluate("document.querySelector('#ed').innerHTML = '<p>ccc</p><p>вторая строка</p>'")
    code_first(); pg.keyboard.press("End")
    for _ in range(3):
        pg.keyboard.press("Backspace")
    pg.wait_for_timeout(100)
    before = h()
    pg.keyboard.press("Delete"); pg.wait_for_timeout(100)
    ok("<pre" not in h() and h().startswith("<p>вторая строка"), f"Delete в пустом блоке — блок убран, следующий абзац не втянут: {before[:50]} → {h()[:60]}")
    pg.evaluate("document.querySelector('#ed').innerHTML = '<p>один</p><p>два</p>'")
    code_first(); pg.keyboard.press("End"); pg.click("#tools .tool[data-c=code]"); pg.wait_for_timeout(100)
    ok(h() == "<p>один</p><p>два</p>", f"«Код» ещё раз в блоке — блок убран: {h()}")
    code_first(); pg.keyboard.press("End"); pg.keyboard.press("Enter"); pg.keyboard.type("x = 1")
    ok(h().startswith("<pre>один") and "x = 1</pre>" in h(), f"Enter в блоке — новая строка кода: {h()}")
    pg.keyboard.press("Enter"); pg.keyboard.press("Enter"); pg.keyboard.type("дальше текст")
    ok("x = 1</pre><p>дальше текст</p>" in h(), f"Enter на пустой последней строке — выход из блока: {h()}")
    ok("```" in md() and "дальше текст" in md(), "в Markdown — блок кода и текст после него")
    ok(not errs, f"без ошибок JavaScript: {errs[:2]}")
    b.close()
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
