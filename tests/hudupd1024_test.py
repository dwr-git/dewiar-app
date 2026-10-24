"""Значок обновления у жучка в виджете (24.10, владелец: «возле жучка слева вверху не хватает значка обновления,
было бы удобно одним нажатием обновляться»): нажали — проверка; новее нет — «У вас последняя версия»; есть — сразу
установка (install_update); пока обновление ждёт — значок виден всегда и с точкой, нажатие ставит его."""
import os, re, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


FAKE = """window.apiCalls = []; window.pywebview = { api: new Proxy({}, { get: (_, k) => (...a) => { apiCalls.push([k, ...a]);
  if (k === 'install_update') return Promise.resolve({ ok: true, started: false }); return Promise.resolve(true); } }) };"""
CORE = r"""
(() => { window.calls = []; window.UPD_NEXT = { current: "0.43.1", available: null, error: "" };
  const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.call = async (c, a) => { calls.push([c, a]);
      if (c === "update_check") { await new Promise(r => setTimeout(r, 300)); return JSON.parse(JSON.stringify(UPD_NEXT)); }
      return {}; };
    setTimeout(() => core.emit("hello", {}), 200); };
  ready(); })();
"""
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 300, "height": 420}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route(re.compile(r"^https?://"), lambda r: r.abort())
    pg.add_init_script(FAKE); pg.add_init_script(CORE)
    pg.goto((ROOT / "ui/hud.html").as_uri()); pg.wait_for_timeout(1500)
    ok(pg.locator("#corner-l #b-upd").count() == 1 and pg.evaluate("document.querySelector('#b-bug').nextElementSibling.id") == "b-upd",
       "значок обновления — рядом с жучком")
    pg.hover("#card"); pg.wait_for_timeout(300)
    pg.click("#b-upd"); pg.wait_for_timeout(100)
    ok("Проверяю обновления" in pg.inner_text("#upd") and pg.evaluate("document.querySelector('#b-upd').classList.contains('busy')"), "нажали — «Проверяю обновления…», значок крутится")
    pg.wait_for_timeout(500)
    ok("последняя версия — 0.43.1" in pg.inner_text("#upd"), f"новее нет — так и сказано: {pg.inner_text('#upd')!r}")
    pg.wait_for_timeout(5300)
    ok(not pg.is_visible("#upd"), "строка сама прячется через 5 секунд")
    # обновление нашлось при проверке — сразу ставится
    pg.evaluate("UPD_NEXT = { current: '0.43.1', available: { version: '0.44.0', path: '/tmp/x.deb' }, error: '' }")
    pg.hover("#card"); pg.click("#b-upd"); pg.wait_for_timeout(900)
    inst = [c for c in pg.evaluate("apiCalls") if c[0] == "install_update"]
    ok(inst and inst[0][1] == "/tmp/x.deb", f"нашлось — одним нажатием ставится: {inst}")
    ok("перезапускаюсь" in pg.inner_text("#upd").lower(), f"видно, что идёт: {pg.inner_text('#upd')!r}")
    # обновление пришло само (событие) — значок виден без наведения, с точкой, нажатие ставит
    pg.reload(); pg.wait_for_timeout(1200)
    pg.evaluate("core.emit('update', { update: { current: '0.43.1', available: { version: '0.44.1', path: '/tmp/y.deb' } } })"); pg.wait_for_timeout(300)
    pg.mouse.move(5, 400); pg.wait_for_timeout(400)
    ok(pg.evaluate("getComputedStyle(document.querySelector('#corner-l')).opacity") == "1" and pg.evaluate("document.querySelector('#b-upd').classList.contains('has')"),
       "есть обновление — значок виден всегда, с точкой")
    ok("0.44.1" in pg.get_attribute("#b-upd", "title"), "в подсказке — какая версия")
    pg.click("#b-upd"); pg.wait_for_timeout(500)
    inst = [c for c in pg.evaluate("apiCalls") if c[0] == "install_update"]
    ok(inst and inst[-1][1] == "/tmp/y.deb" and not any(c[0] == "update_check" for c in pg.evaluate("calls")), "нажали — ставится сразу, без лишней проверки")
    ok(not errs, f"без ошибок на странице: {errs[:3]}")
    b.close()
print("\nИТОГ:", "все проверки прошли" if not fails else f"не прошло {len(fails)}")
sys.exit(1 if fails else 0)
