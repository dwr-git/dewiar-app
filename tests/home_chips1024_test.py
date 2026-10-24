"""Умный дом в студии (24.10, Ubuntu: «в подключённых устройствах текст не читается, слишком светлый»): включённые
устройства — тёплым, но в светлых темах текст тёмный (контраст не меньше 4,5), в тёмной — как раньше."""
import os, re
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


FAKE = "window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };"
CONTRAST = """(sel) => { const el = document.querySelector(sel); if (!el) return 0;
  const p = (c) => (c.match(/[\\d.]+/g) || []).map(Number);
  const L = ([r, g, b]) => { const f = (v) => { v /= 255; return v <= .03928 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4; }; return .2126 * f(r) + .7152 * f(g) + .0722 * f(b); };
  const fg = p(getComputedStyle(el).color); let bg = null, n = el;
  while (n && !bg) { const c = p(getComputedStyle(n).backgroundColor); if (c.length === 3 || (c.length === 4 && c[3] > .5)) bg = c.slice(0, 3); n = n.parentElement; }
  bg = bg || (document.documentElement.classList.contains('st-light') ? [238, 243, 249] : [22, 22, 40]); const a = L(fg.slice(0, 3)), b = L(bg); return (Math.max(a, b) + .05) / (Math.min(a, b) + .05); }"""
H = {"connected": True, "devices": [{"name": "Подсветка зеркала", "room": "Ванная", "type": "light", "on": True}, {"name": "Камин", "room": "Кухня", "type": "socket", "on": False}],
     "rooms": ["Ванная", "Кухня"], "scenarios": ["Я дома"]}
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    for sk, light in (("neusky", True), ("brand", False)):
        pg = b.new_page(viewport={"width": 1280, "height": 900}); pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.route(re.compile(r"^https?://"), lambda r: r.abort())
        pg.add_init_script(FAKE + f" try {{ localStorage.setItem('studio_skin', '{sk}'); }} catch (e) {{}}")
        pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(900)
        pg.evaluate("(sk) => { S = Object.assign({}, S || {}, { ui: { skin: sk }, smarthome: {} }); core.emit('settings', { settings: S }); }", sk); pg.wait_for_timeout(300)
        pg.evaluate("(h) => shFill(h)", H)
        on = pg.evaluate(CONTRAST, "#sh-devs .chip.shd.on"); off = pg.evaluate(CONTRAST, "#sh-devs .chip.shd:not(.on):not(.scn)")
        cls = pg.evaluate("document.documentElement.className")
        ok(("st-light" in cls) == light and on >= 4.5 and off >= 4.5, f"«{sk}»: включённое читается ({on:.1f}), выключенное тоже ({off:.1f})")
        pg.close()
    ok(not errs, f"без ошибок: {errs[:2]}")
    b.close()
if fails:
    raise SystemExit(1)
