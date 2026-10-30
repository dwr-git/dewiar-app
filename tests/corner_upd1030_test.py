"""Виджет: «жук и лампочка пропадают, когда уводишь курсор, а обновление остаётся» (владелец 30.10, 0.73). Пока горит
дозор (глаз), стоп-кран или текстовый режим, левый угол виден всегда, но прятал только жук и лампочку — значок
обновлений висел без дела, хотя нового нет. Теперь без курсора видны только сами метки (глаз, щит, «текстом») и значок
обновлений, когда обновление правда есть (с точкой) или идёт проверка; под курсором — все кнопки, как раньше."""
import os, re, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


CORE = r"""
(() => { const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.call = async () => ({});
    setTimeout(() => core.emit("hello", { version: "0.73.0" }), 200); };
  ready(); })();
"""
VIS = "(id) => getComputedStyle(document.querySelector('#corner-l')).opacity === '1' && getComputedStyle(document.getElementById(id)).opacity === '1'"
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 700, "height": 760}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route(re.compile(r"^https?://"), lambda r: r.abort())
    pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };"); pg.add_init_script(CORE)
    pg.goto((ROOT / "ui/hud.html").as_uri()); pg.wait_for_timeout(1500)
    pg.add_style_tag(content="#card { position: fixed !important; width: 320px !important; height: 480px !important; inset: 0 auto auto 0 !important; }")  # виджет меньше окна — курсор можно увести
    for cls, what in (("watch", "дозор"), ("lo", "стоп-кран"), ("tm", "текстовый режим")):
        pg.evaluate(f"document.querySelector('#corner-l').className = '{cls}'; document.querySelector('#b-upd').className = 'btn'")
        pg.mouse.move(690, 750); pg.wait_for_timeout(350)
        ok(not pg.evaluate(VIS, "b-upd") and not pg.evaluate(VIS, "b-bug") and not pg.evaluate(VIS, "b-idea"),
           f"{what}, курсор ушёл, обновлений нет — значок обновлений прячется вместе с жуком и лампочкой")
        pg.hover("#card"); pg.mouse.move(60, 200); pg.wait_for_timeout(350)
        ok(pg.evaluate(VIS, "b-upd") and pg.evaluate(VIS, "b-bug"), f"{what}, курсор на виджете — все кнопки на месте")
    pg.evaluate("document.querySelector('#corner-l').className = 'watch upd'; document.querySelector('#b-upd').className = 'btn has'")
    pg.mouse.move(690, 750); pg.wait_for_timeout(350)
    ok(pg.evaluate(VIS, "b-upd") and not pg.evaluate(VIS, "b-bug"), "обновление правда есть — значок с точкой виден и без курсора")
    pg.evaluate("document.querySelector('#corner-l').className = 'watch'; document.querySelector('#b-upd').className = 'btn busy'")
    pg.wait_for_timeout(350)
    ok(float(pg.evaluate("getComputedStyle(document.querySelector('#b-upd')).opacity")) > 0.3, "идёт проверка — крутящийся значок не исчезает")
    b.close()
ok(not errs, f"без ошибок на странице: {errs[:3]}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
