"""03.11, человек: «в версии для Windows на главной странице Студии нет кнопки-жучка, непонятно, куда выслать скриншот
ошибки»; идея №98 — «лампочка идеи и жучок возле вопросика на каждой странице». Теперь: «Сообщить о проблеме» внизу меню
(видно и с «Главной»), а у заголовка каждого раздела — жучок (снимок экрана + форма с названием раздела) и лампочка
(«Идеи Лиры»)."""
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
    core.call = async (c, a) => { calls.push([c, a]);
      if (c === "bug_shot") return { ok: true, preview: "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==" };
      return {}; };
    setTimeout(() => core.emit("hello", {}), 200); };
  ready(); })();"""
errs = []
with sync_playwright() as p:
    b = p.chromium.launch()
    st = b.new_page(viewport={"width": 1300, "height": 900}); st.on("pageerror", lambda e: errs.append(str(e)) if "icons.js" in str(e.stack) else None)
    st.route(re.compile(r"^https?://"), lambda r: r.abort()); st.add_init_script(FAKE)
    st.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); st.wait_for_timeout(1200)
    st.evaluate("() => { const w = document.querySelector('#wlc'); if (w) w.remove(); }")
    nb = st.locator("#nav-bug")
    ok(nb.is_visible() and "Сообщить о проблеме" in nb.inner_text() and nb.locator("svg").count() == 1, "внизу меню — «Сообщить о проблеме» со значком, видно с «Главной»")
    nb.click(); st.wait_for_timeout(500)
    ok(st.evaluate("document.querySelector('#p-about').classList.contains('cur')") and st.evaluate("!document.querySelector('#bug-img').hidden")
       and ["bug_shot", None] in st.evaluate("calls") or any(c[0] == "bug_shot" for c in st.evaluate("calls")), "нажали — снимок экрана и форма «Сообщить о проблеме»")
    st.evaluate("() => { document.querySelector('#rep-note').value = ''; document.querySelector('nav button[data-p=\"pay\"]').click(); }"); st.wait_for_timeout(500)
    h = st.locator("#p-pay h1")
    ok(h.locator(".hb-bug").count() == 1 and h.locator(".hb-idea").count() == 1, "у заголовка раздела — жучок и лампочка")
    if SHOTS:
        st.screenshot(path=os.path.join(SHOTS, "bug-buttons.png"), clip={"x": 0, "y": 0, "width": 1300, "height": 200})
    h.locator(".hb-bug").click(); st.wait_for_timeout(500)
    ok(st.evaluate("document.querySelector('#p-about').classList.contains('cur')") and st.input_value("#rep-note").startswith("Раздел «Платежи»"),
       f"жучок раздела — форма с названием раздела: {st.input_value('#rep-note')!r}")
    st.evaluate("() => document.querySelector('nav button[data-p=\"pay\"]').click()"); st.wait_for_timeout(300)
    h.locator(".hb-idea").click(); st.wait_for_timeout(500)
    ok(st.evaluate("document.querySelector('#p-ideas').classList.contains('cur')"), "лампочка — «Идеи Лиры»")
    ok(st.locator("#p-about h1 .hb-bug").count() == 0, "в «О программе» жучка у заголовка нет — форма там же")
    ok(not errs, f"без ошибок: {errs}")
    b.close()
# №499 (03.11): «О программе» нажали раньше, чем загрузился tasks.js, — «renderUpdate is not defined» в журнале
ok('typeof renderUpdate === "function"' in (ROOT / "ui/studio/core.js").read_text(encoding="utf-8"), "«О программе» до загрузки tasks.js — без ошибки")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
