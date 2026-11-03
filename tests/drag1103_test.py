"""№457 (01.11, Windows 11): «не могу выделить мышью свой написанный текст в окошке агента — окно двигается при движении
мыши». Нажатие в поле вопроса (textarea #askin) начинало перетаскивание виджета (с захватом указателя — выделить
нельзя): textarea не было в списке исключений. Теперь окно не тащат поле ввода, тексты ответа и реплики и всё, где
текст выделяется (user-select: text); своя реплика «Вы: …» в карточке тоже выделяется. И №442: на Wayland (окна
прямо, чёткий текст) окно двигает композитор — страница отдаёт ему перетаскивание (drag_native), а не move_to."""
import os, re, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


CORE = r"""(() => { window.__calls = [];
  window.pywebview = { api: new Proxy({}, { get: (t, k) => (...x) => { __calls.push([k, ...x]);
    return Promise.resolve(k === "get_pos" ? [100, 100] : k === "native_drag" ? !!window.__native : true); } }) };
  const ready = () => { if (!window.core) return setTimeout(ready, 5);
  core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; try { core.ws.close(); } catch (e) {} } core.connected = true;
  core.call = async () => ({}); setTimeout(() => { core.emit("hello", { settings: { ui: { skin: "neon" }, llm: { active: "m" }, features: {} }, status: {}, persona: "lira", personas: [{ id: "lira", name: "Лира" }], reminders: [], state: "idle" }); }, 150); }; ready(); })();"""
errs = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 300, "height": 520}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route(re.compile(r"^https?://"), lambda r: r.abort()); pg.add_init_script(CORE)
    pg.goto((ROOT / "ui/hud.html").as_uri() + "?port=1&mode=card"); pg.wait_for_timeout(1200)
    r = pg.evaluate("""() => { document.getElementById('ask').style.display = 'block'; const t = document.getElementById('askin');
      const you = document.getElementById('you'); you.textContent = 'мой вопрос'; document.getElementById('cap').classList.add('show');
      return { ta: noDrag(t), you: noDrag(you), youSel: getComputedStyle(you).userSelect, orb: noDrag(document.getElementById('orb')),
               card: noDrag(document.getElementById('card')), rd: noDrag(document.getElementById('rd-body')), btn: noDrag(document.getElementById('b-mic')) }; }""")
    ok(r["ta"], "поле вопроса (textarea) — не перетаскивание: текст выделяется")
    ok(r["you"] and r["youSel"] == "text", f"своя реплика «Вы: …» выделяется и не тащит окно ({r['youSel']})")
    ok(r["rd"] and r["btn"], "текст «Ответ целиком» и кнопки — не перетаскивание")
    ok(not r["orb"] and not r["card"], "облик и пустое место карточки — по-прежнему тащат виджет")
    # настоящее нажатие и движение мыши в поле: окно не двигается, текст выделяется
    pg.evaluate("() => { __calls.length = 0; const t = document.getElementById('askin'); t.value = 'выделить этот текст'; t.focus(); }")
    box = pg.locator("#askin").bounding_box()
    if box:
        pg.mouse.move(box["x"] + 4, box["y"] + box["height"] / 2); pg.mouse.down()
        pg.mouse.move(box["x"] + box["width"] - 6, box["y"] + box["height"] / 2, steps=8); pg.mouse.up()
        pg.wait_for_timeout(200)
        c = pg.evaluate("() => ({ moves: __calls.filter(c => /^(get_pos|move_to|drag_begin|drag_step)$/.test(c[0])).length, sel: (() => { const t = document.getElementById('askin'); return t.selectionEnd - t.selectionStart; })() })")
        ok(c["moves"] == 0, f"движение мыши в поле не двигает окно: {c['moves']} вызовов")
        ok(c["sel"] > 3, f"текст в поле выделился: {c['sel']} знаков")
    else:
        ok(False, "поле вопроса не видно")
    # пустое место карточки — окно едет (как раньше)
    pg.evaluate("() => { __calls.length = 0; document.getElementById('ask').style.display = ''; }")
    cb = pg.locator("#card").bounding_box()
    pg.mouse.move(cb["x"] + 20, cb["y"] + 60); pg.mouse.down(); pg.mouse.move(cb["x"] + 60, cb["y"] + 90, steps=6); pg.wait_for_timeout(150); pg.mouse.up()
    pg.wait_for_timeout(200)
    mv = pg.evaluate("() => __calls.filter(c => c[0] === 'move_to').length")
    ok(mv > 0, f"за пустое место карточки виджет тащится: move_to × {mv}")
    pg.close()

    # №442: окна прямо на Wayland — перетаскивание отдаём композитору, move_to и сохранение места не зовём
    pg = b.new_page(viewport={"width": 300, "height": 520}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route(re.compile(r"^https?://"), lambda r: r.abort()); pg.add_init_script("window.__native = true;"); pg.add_init_script(CORE)
    pg.goto((ROOT / "ui/hud.html").as_uri() + "?port=1&mode=card"); pg.wait_for_timeout(1900)
    pg.evaluate("() => { __calls.length = 0; }")
    cb = pg.locator("#card").bounding_box()
    pg.mouse.move(cb["x"] + 20, cb["y"] + 60); pg.mouse.down(); pg.mouse.move(cb["x"] + 60, cb["y"] + 90, steps=6); pg.wait_for_timeout(150); pg.mouse.up()
    pg.wait_for_timeout(200)
    c = pg.evaluate("() => ({ nat: __calls.filter(c => c[0] === 'drag_native').length, mv: __calls.filter(c => c[0] === 'move_to').length, sv: __calls.filter(c => c[0] === 'save_pos').length })")
    ok(c["nat"] == 1 and c["mv"] == 0 and c["sv"] == 0, f"Wayland: тащит композитор (drag_native один раз, без move_to/save_pos): {c}")
    pg.close()
    b.close()
ok(not errs, f"без ошибок страницы: {errs[:2]}")
src = (ROOT / "ui/app.py").read_text(encoding="utf-8")
ok("def drag_native(self" in src and "begin_move_drag" in src and "def native_drag(self)" in src, "app.py: перетаскивание силами композитора на Wayland")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
