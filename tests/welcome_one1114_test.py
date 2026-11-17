"""0.99 (владелец 14.11: «первый запуск в один экран… элегантно»): «Первые шаги» — одно окно: персонаж здоровается
по имени, три вопроса крупно; нажали — вопрос уходит ассистенту, ответ появляется здесь же (живой текст по событиям
answer, итог — done), после ответа — «Готово». Мозга нет или он не отвечает — вместо вопросов одна карточка
«Подключить» (раздел «Мозг»). Сказали имя вслух — ответ тоже сюда. Шагов «Telegram», списка фраз и «Что бесплатно» больше нет."""
import os, re, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


FAKE = """(() => { window._said = []; window._saves = []; window._llm = { ok: true, total_ms: 900 };
  const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.call = async (c, a) => { if (c === "say") _said.push(a.text); if (c === "llm_test") return _llm;
      if (c === "settings_save") { _saves.push(a.patch); return S; } return {}; };
  };
  ready(); })();"""
OUT = Path(os.environ.get("DW_SHOTS") or "")
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 1200, "height": 900}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route(re.compile(r"^https?://"), lambda r: r.abort())
    pg.add_init_script(FAKE)
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(1000)
    pg.evaluate("""() => { S = Object.assign(S || {}, { persona: 'lira', llm: { profiles: { a: { name: 'Облако', model: 'm' } }, active: 'a' }, ui: {} }); wlcBoot({}); }""")
    pg.wait_for_timeout(400)
    vis = lambda sel: pg.evaluate("(s) => { const e = document.querySelector(s); return !!e && e.offsetParent !== null && getComputedStyle(e).visibility !== 'hidden'; }", sel)
    ok(vis("#wlc .box") and "Лира" in pg.inner_text("#wlc h2"), "первый запуск — окно с приветствием персонажа по имени")
    qs = pg.evaluate("() => [...document.querySelectorAll('#wlc-qs .tq')].map(b => b.textContent)")
    ok(len(qs) == 3 and any(q.startswith("Лира, ") for q in qs), f"три вопроса (те же, что в виджете), один — с именем: {qs}")
    ok(not pg.query_selector("#wlc .wst") and not pg.query_selector("#wlc-free") and not pg.query_selector("#wlc-tlist"),
       "нет шагов 1-2-3, «Telegram», списка фраз и «Что бесплатно» — одно действие")
    ok(not vis("#wlc-brain") and not vis("#wlc-done") and vis("#wlc-later"), "мозг отвечает — карточки «Подключить» нет; пока не спросил — «Позже»")
    if OUT.name:
        pg.screenshot(path=str(OUT / "wlc-1.png"))
    pg.click("#wlc-qs .tq >> nth=1"); pg.wait_for_timeout(150)
    ok(pg.evaluate("_said") == [qs[1]], f"нажатие — вопрос ушёл ассистенту: {pg.evaluate('_said')}")
    ok(vis("#wlc-ans") and pg.evaluate("$('#wlc-ans').classList.contains('wait')"), "пока думает — пузырь с точками")
    pg.evaluate("() => { window._ev = (t, d) => core.emit(t, d); }")
    pg.evaluate("() => _ev('answer', { text: 'Завтра в Москве' })"); pg.wait_for_timeout(60)
    live = pg.inner_text("#wlc-ans p")
    pg.evaluate("() => _ev('answer', { text: 'Завтра в Москве +3 и дождь — зонт пригодится.', done: true })"); pg.wait_for_timeout(100)
    ok(live == "Завтра в Москве" and "зонт" in pg.inner_text("#wlc-ans p") and not pg.evaluate("$('#wlc-ans').classList.contains('wait')"),
       f"ответ — здесь же, по мере ответа и целиком ({live!r})")
    ok(vis("#wlc-done") and not vis("#wlc-later"), "после ответа — «Готово»")
    if OUT.name:
        pg.screenshot(path=str(OUT / "wlc-2.png"))
    pg.click("#wlc-done"); pg.wait_for_timeout(100)
    ok(not vis("#wlc .box") and any(((x or {}).get("ui") or {}).get("welcome") == "done" for x in pg.evaluate("_saves")), "«Готово» — окно закрыто и запомнено")
    # без мозга
    pg.evaluate("() => { window._llm = { ok: false, error: 'нет связи' }; S.ui = {}; wlcOpen(); }"); pg.wait_for_timeout(300)
    ok(vis("#wlc-brain") and not vis("#wlc-qs") and not vis("#wlc-sub") and not vis("#wlc-done") and "не отвечает" in pg.inner_text("#wlc-brain"), "мозг не отвечает — вместо вопросов одна карточка «Подключить»")
    pg.evaluate("() => { S.llm = { profiles: {}, active: '' }; wlcOpen(); }"); pg.wait_for_timeout(200)
    ok(vis("#wlc-brain") and "Ollama" in pg.inner_text("#wlc-brain") and "облако Dewiar" in pg.inner_text("#wlc-brain"),
       "мозг не выбран — коротко, что есть бесплатно")
    if OUT.name:
        pg.screenshot(path=str(OUT / "wlc-3.png"))
    pg.click("#wlc-brain [data-go]"); pg.wait_for_timeout(150)
    ok(not vis("#wlc .box") and pg.evaluate("document.querySelector('nav button[data-p=\"brain\"]').classList.contains('cur') || location.hash.includes('brain') || !!document.querySelector('#p-brain.cur')"),
       "«Подключить» — раздел «Мозг»")
    # имя вслух
    pg.evaluate("() => { window._llm = { ok: true }; S.llm = { profiles: { a: { name: 'x' } }, active: 'a' }; wlcOpen(); }"); pg.wait_for_timeout(200)
    pg.evaluate("() => { _ev('wake', { word: 'лира' }); _ev('answer', { text: 'Привет! Я здесь.', done: true }); }"); pg.wait_for_timeout(100)
    ok("Привет" in pg.inner_text("#wlc-ans p"), "сказали «Лира, …» вслух — ответ тоже в окне")
    pg.set_viewport_size({"width": 420, "height": 760}); pg.wait_for_timeout(150)
    w = pg.evaluate("() => [document.querySelector('#wlc .box').getBoundingClientRect().right, innerWidth, document.documentElement.scrollWidth]")
    ok(w[0] <= w[1] and w[2] <= w[1], f"узкое окно — без горизонтальной прокрутки: {w}")
    ok(not errs, f"без ошибок: {errs[:2]}")
    b.close()
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
