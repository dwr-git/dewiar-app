"""04.11, владелец: «по плагинам очень красиво, но у нас же были готовые — переводчик, путешествия, художник, — они должны
здесь отображаться? Запутался, где что». В группе «Плагины» — «Все плагины» (каталог готовых), на странице «Создать плагин» —
полоса «Готовые плагины Dewiar» со ссылкой на каталог, а шаблоны своего плагина названы «Заготовки для своего плагина»."""
import os, re, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
SHOTS = os.environ.get("DEWIAR_SHOTS")
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


FAKE = """(() => { window.calls = [];
  const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.call = async (c, a) => { calls.push([c, a]); return {}; };
    setTimeout(() => core.emit("hello", {}), 200); };
  ready(); })();"""
errs = []
with sync_playwright() as p:
    b = p.chromium.launch()
    st = b.new_page(viewport={"width": 1300, "height": 900}); st.on("pageerror", lambda e: errs.append(str(e)))
    st.route(re.compile(r"^https?://"), lambda r: r.abort()); st.add_init_script(FAKE)
    st.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); st.wait_for_timeout(1200)
    st.evaluate("() => { const w = document.querySelector('#wlc'); if (w) w.remove(); }")
    na = st.locator("#nav-plg-all")
    ok(na.count() == 1 and "Все плагины" in na.inner_text(), "в группе «Плагины» — «Все плагины»")
    st.evaluate("() => document.querySelector('#nav-plg-all').click()"); st.wait_for_timeout(400)
    ok(st.evaluate("document.querySelector('#p-skills').classList.contains('cur')"), "«Все плагины» открывает каталог готовых")
    st.evaluate("() => { document.querySelector('#nav-plg-new').click(); if (!document.querySelector('#pmk-cat')) pmkRender(); }"); st.wait_for_timeout(600)
    ok(st.locator("#pmk-cat").is_visible() and "Художник" in st.inner_text("#pmk-cat"), "на «Создать плагин» — полоса «Готовые плагины Dewiar»")
    ok("Заготовки для своего плагина" in st.inner_text("#p-plgnew"), "шаблоны своего плагина названы заготовками, не «готовыми»")
    if SHOTS:
        st.screenshot(path=os.path.join(SHOTS, "plugins-all.png"))
    st.locator("#pmk-cat-go").click(); st.wait_for_timeout(400)
    ok(st.evaluate("document.querySelector('#p-skills').classList.contains('cur')"), "кнопка на полосе ведёт в каталог")
    ok(not [e for e in errs if "plugmake" in e or "show.js" in e], f"без ошибок: {errs[:3]}")
    b.close()
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
