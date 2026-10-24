"""24.10, владелец (Ubuntu): «уместилось три вкладки, а перед „Щитом“ у меня ещё одна — её не вижу и не понимаю, как на
неё промотать… может, возле плюсика выпадающий список с вкладками, если их много». Теперь: не влезли — у «+» кнопка «⌄»
со списком всех вкладок (выбрали — открылась и видна в ряду), край ряда тает там, где есть ещё вкладки, колёсико листает
ряд. Влезли все — кнопки нет."""
import json, os, urllib.parse
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


FAKE = """window.pywebview = { api: new Proxy({}, { get: (_, k) => (...a) => Promise.resolve(k === 'get_pos' ? [1500, 300] : true) }) };"""
CORE = r"""
(() => { window.calls = []; window.TABS = %s;
  const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.connected = true;
    core.call = async (c, a) => { calls.push([c, a]);
      if (c === "pad_tabs") return { tabs: TABS.map(n => ({ name: n, mtime: 1 })), active: TABS[TABS.length - 1] };
      if (c === "pad_read") return { name: a.name, text: "Текст вкладки " + a.name + "\n", mtime: 1 };
      return {}; }; };
  ready(); })();
"""
URL = (ROOT / "ui/pad.html").as_uri() + "?skin=neusky&cfg=" + urllib.parse.quote(json.dumps({"side": "left", "gap": 14, "clips": []}))
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 440, "height": 560}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.add_init_script(FAKE); pg.add_init_script(CORE % json.dumps(["Серверы", "Щит", "PHP уязвимость", "Обновить", "Покупки"]))
    pg.goto(URL); pg.wait_for_timeout(1200)
    ok(pg.is_visible("#b-list"), "вкладок больше, чем влезает, — у «+» есть «⌄»")
    cls = pg.evaluate("document.querySelector('#tabs').className")
    ok("more-l" in cls, f"открыта последняя — левый край ряда тает: там ещё вкладки ({cls})")
    pg.click("#b-list"); pg.wait_for_timeout(150)
    items = pg.evaluate("[...document.querySelectorAll('#tl button')].map(b => [b.textContent, b.getAttribute('aria-current')])")
    ok([i[0] for i in items] == ["Серверы", "Щит", "PHP уязвимость", "Обновить", "Покупки"] and items[-1][1] == "true",
       f"список — все вкладки по порядку, открытая отмечена: {items}")
    pg.screenshot(path="/tmp/claude-0/pad_tabs_list.png")
    pg.click("#tl button >> text=Серверы"); pg.wait_for_timeout(400)
    ok(not pg.is_visible("#tl") and pg.evaluate("P.active") == "Серверы", "выбрали первую — открылась, список закрылся")
    vis = pg.evaluate("""(() => { const t = document.querySelector('.tab.on').getBoundingClientRect(), r = document.querySelector('#tabs').getBoundingClientRect();
        return t.left >= r.left - 1 && t.right <= r.right + 1; })()""")
    ok(vis and "more-r" in pg.evaluate("document.querySelector('#tabs').className"), "и видна в ряду; теперь тает правый край")
    x0 = pg.evaluate("document.querySelector('#tabs').scrollLeft")
    box = pg.locator("#tabs").bounding_box(); pg.mouse.move(box["x"] + 40, box["y"] + 10); pg.mouse.wheel(0, 200); pg.wait_for_timeout(200)
    ok(pg.evaluate("document.querySelector('#tabs').scrollLeft") > x0, "колёсико над вкладками листает ряд")
    pg.click("#b-list"); pg.wait_for_timeout(100); pg.keyboard.press("Escape"); pg.wait_for_timeout(100)
    ok(not pg.is_visible("#tl") and not any(c[0] == "pad_hide" for c in []) and pg.is_visible("#ed"), "Esc закрывает список, а не блокнот")
    # мало вкладок — кнопки нет
    p2 = b.new_page(viewport={"width": 440, "height": 560}); p2.on("pageerror", lambda e: errs.append(str(e)))
    p2.add_init_script(FAKE); p2.add_init_script(CORE % json.dumps(["Главное", "Идеи"]))
    p2.goto(URL); p2.wait_for_timeout(1000)
    ok(not p2.is_visible("#b-list") and "more-" not in p2.evaluate("document.querySelector('#tabs').className"), "все влезли — ни «⌄», ни тающих краёв")
    # 24.10, владелец (Ubuntu): «вставить скриншот из буфера — не работает» — WebKitGTK отдаёт при вставке только текст;
    # картинку берём у окна (Api.clipboard_image), как виджет
    PNG = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    p3 = b.new_page(viewport={"width": 440, "height": 560}); p3.on("pageerror", lambda e: errs.append(str(e)))
    p3.add_init_script("window.pywebview = { api: new Proxy({}, { get: (_, k) => (...a) => Promise.resolve(k === 'clipboard_image' ? %r : k === 'get_pos' ? [1500, 300] : true) }) };" % PNG)
    p3.add_init_script((CORE % json.dumps(["Главное"])).replace('return {}; };', 'if (c === "pad_attach") return { line: "![](Вложения/снимок.png)" }; return {}; };'))
    p3.goto(URL); p3.wait_for_timeout(1000)
    p3.click("#ed"); p3.evaluate("() => { const dt = new DataTransfer(); ED.dispatchEvent(new ClipboardEvent('paste', { clipboardData: dt, bubbles: true, cancelable: true })); }")
    p3.wait_for_timeout(600)
    ok(p3.evaluate("!!document.querySelector('#ed img[data-src=\"Вложения/снимок.png\"]')") and any(c[0] == "pad_attach" for c in p3.evaluate("calls")),
       "Ctrl+V со снимком экрана (странице дали пустой буфер) — картинка из буфера окна в листе")
    ok(not errs, f"без ошибок на странице: {errs[:2]}")
    b.close()

if fails:
    raise SystemExit(1)
