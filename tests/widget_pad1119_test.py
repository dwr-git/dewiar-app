"""Владелец 19.11 (снимок виджета на Ubuntu): «при открытом блокноте справа видны джойстик, чашка… дизайн был бы чище;
и чтобы запоминалось: он у меня всегда открыт — открывался в следующий раз сам». Блокнот открыт — на виду только его кнопка
(остальные — при наведении на виджет); открыли кнопкой — ui.pad_open, закрыли (кнопка, ✕) — нет; при запуске — открыт снова."""
import os, re, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


hud = (ROOT / "ui/hud.html").read_text(encoding="utf-8")
pad = (ROOT / "ui/pad.js").read_text(encoding="utf-8")
ok("#corner.pinned .btn:not(.on) { opacity: 0;" in hud and "#card:hover #corner.pinned .btn" in hud, "блокнот открыт — лишние значки прячутся, при наведении видны")
ok("pad_open: !!r" in hud and "ui.pad_open" in hud, "кнопка блокнота запоминает: открыт / закрыт")
ok("pad_open: false" in pad, "✕ в блокноте — «закрыт» запоминается")
ok(re.search(r"if \(padRestored \|\| !ui\.pad_open \|\| ui\.hud_tray\) return;", hud) and "a.pad_toggle(\"notes\"); }, 1500)" in hud,
   "при запуске: был открыт и виджет не в трее — блокнот открывается сам, один раз")
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 420, "height": 600}); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route(re.compile(r"^https?://"), lambda r: r.abort())
    pg.add_init_script("""window.__calls = []; window.pywebview = { api: new Proxy({}, { get: (t, k) => (...a) => { window.__calls.push([k, a]); return Promise.resolve(k === 'pad_toggle' ? true : true); } }) };""")
    pg.goto((ROOT / "ui/hud.html").as_uri() + "?port=1"); pg.wait_for_timeout(1200)
    pg.evaluate("() => { document.getElementById('card').style.width = '200px'; padMark(true, 'notes'); }"); pg.mouse.move(415, 595); pg.wait_for_timeout(400)
    vis = pg.evaluate("[...document.querySelectorAll('#corner .btn')].filter(x => !x.hidden).map(x => [x.id, getComputedStyle(x).opacity])")
    ok(all(o == "0" for i, o in vis if i != "b-pad") and any(i == "b-pad" and o != "0" for i, o in vis), f"видна только кнопка блокнота: {vis}")
    xs = pg.evaluate("() => { const c = document.getElementById('corner').getBoundingClientRect(), b = document.getElementById('b-pad').getBoundingClientRect(); return [c.right, b.right]; }")
    ok(abs(xs[0] - xs[1]) < 2, f"кнопка открытого блокнота — у правого края, без пустого места (владелец 20.11): {xs}")
    pg.evaluate("() => padMark(false)"); pg.wait_for_timeout(300)
    ok(not pg.evaluate("document.getElementById('corner').classList.contains('pinned')"), "блокнот закрыт — угол как раньше")
    pg.evaluate("() => padMark(true, 'notes')"); pg.hover("#card"); pg.wait_for_timeout(400)
    ok(pg.evaluate("getComputedStyle(document.getElementById('b-rest')).opacity") == "1", "наведение на виджет — все значки снова видны")
    b.close()
ok(not errs, f"без ошибок: {errs[:3]}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
