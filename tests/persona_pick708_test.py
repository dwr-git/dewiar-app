"""№708 (14.11, McDuck): «выбор персонажа на ПК сделать также как на телефоне — левый верхний угол, это и проще и
быстрее». Облик и имя слева вверху студии — кнопка: список персонажей, одно нажатие — сменить, «Все персонажи…» — раздел."""
import json, os, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
P = [{"id": "lira", "name": "Лира", "color": "#8A9BFF", "style": "nexus"}, {"id": "patrik", "name": "Патрик", "color": "#F59E0B", "style": "nexus"},
     {"id": "eva", "name": "Эва", "color": "#EC4899", "style": "aura"}]
core = """(() => { const ready = () => { if (!window.core) return setTimeout(ready, 5);
core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
core.connected = true; window.__calls = []; core.call = async (c, a) => { __calls.push([c, a]); return null; }; }; ready(); })();"""
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 1200, "height": 800}, device_scale_factor=1)
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route("**/*", lambda r: r.abort() if r.request.url.startswith("http") else r.continue_())
    pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };"); pg.add_init_script(core)
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1&lang=ru"); pg.wait_for_timeout(900)
    pg.evaluate("(P) => { personas = P; active = 'lira'; personasHead(); }", P)
    pg.click(".brand"); pg.wait_for_timeout(300)
    if len(sys.argv) > 1: pg.screenshot(path=sys.argv[1], clip={"x": 0, "y": 0, "width": 420, "height": 330})
    r = pg.evaluate("[...document.querySelectorAll('#br-pick button')].map(b => b.innerText.trim())")
    pg.click("#br-pick button[data-id=patrik]"); pg.wait_for_timeout(200)
    calls = pg.evaluate("__calls.filter(c => c[0] === 'persona_set')")
    gone = pg.evaluate("!document.querySelector('#br-pick')")
    pg.click(".brand"); pg.wait_for_timeout(100); pg.click("#br-pick .all"); pg.wait_for_timeout(300)
    sec = pg.evaluate("(() => { const s = document.querySelector('#p-personas'); return !!s && getComputedStyle(s).display !== 'none'; })()")
    b.close()
fails = []
def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)
ok(r == ["Лира", "Патрик", "Эва", "Все персонажи…"], f"нажали облик слева вверху — список персонажей: {r}")
ok(calls == [["persona_set", {"id": "patrik"}]] and gone, "одно нажатие — говорит Патрик, список закрылся")
ok(sec, "«Все персонажи…» — раздел «Персонажи»")
ok(not errs, f"без ошибок страницы: {errs[:2]}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
