"""Отзыв на YouTube 18.10: «я установил программу, сказал ей привет, и мне ответили голосом, а вот что с ней делать дальше —
ума не приложу». Теперь новичку видны фразы-примеры «Попробуйте сказать»: на компьютере — в окне «Первые шаги» (нажатие
отправляет фразу ассистенту), на телефоне — на пустом экране, пока человек сам спросил меньше 4 раз. Тем, кто уже
пользовался (есть разговор или память), подсказки не появляются; «Больше не показывать» — насовсем."""
import os, shutil, subprocess, sys, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


tmp = Path(tempfile.mkdtemp())
www = tmp / "www"
shutil.copytree(ROOT / "android/assets/www", www)
shutil.copy(ROOT / "ui/assets/entities.js", www / "entities.js")
shutil.copytree(ROOT / "ui/assets/live", www / "live", dirs_exist_ok=True)
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                capture_output=True, text=True, check=True).stdout, encoding="utf-8")
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        # ---------- компьютер: «Первые шаги» ----------
        pg = b.new_page(viewport={"width": 1100, "height": 900}); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(700)
        pg.evaluate("""() => { S = { persona: 'lira', llm: { profiles: {}, active: '' }, ui: {} }; window._said = [];
            core.call = (cmd, a) => { if (cmd === 'say') window._said.push(a.text); return Promise.resolve(null); }; wlcOpen(); }""")
        pg.wait_for_timeout(300)
        qs = pg.evaluate("() => [...document.querySelectorAll('#wlc .tq')].map(b => b.dataset.q)")
        ok(len(qs) == 3 and any(q.startswith("Лира, ") for q in qs), f"в «Первых шагах» (0.99 — одно окно) — три вопроса, один с именем персонажа: {qs}")
        ok(pg.evaluate("() => !document.querySelector('#wlc-brain').hidden") and pg.evaluate("window._said") == [],
           "мозг ещё не выбран — вместо вопросов карточка «Подключить», ничего не уходит")
        free = pg.inner_text("#wlc-brain")
        ok("Ollama" in free and "облако Dewiar" in free and "Бесплатно" in free, "коротко, что бесплатно: облако Dewiar по входу или своя модель")
        pg.evaluate("() => { wlcBrainOk = true; wlcBrain(); }")
        pg.click("#wlc .tq >> nth=1"); pg.wait_for_timeout(200)
        ok(pg.evaluate("window._said") == [qs[1]], f"мозг работает — нажатие отправляет вопрос ассистенту: {pg.evaluate('window._said')}")
        ok(not errs, f"студия без ошибок: {errs[:2]}")
        pg.close()

        # ---------- телефон: пустой экран у новичка ----------
        pg = b.new_page(viewport={"width": 360, "height": 740}); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(900)
        pg.evaluate("""() => { window._asked = []; ask = (t) => { window._asked.push(t); triesState().n++; quietCheck(); return Promise.resolve(); };
            S.llm.base_url = 'http://127.0.0.1:9/v1'; S.tries = null; history.length = 0; S.memory = [];
            $('#you').textContent = ''; $('#bot').textContent = ''; $('#bot').className = ''; showCard(''); quietCheck(); }""")
        vis = lambda: pg.evaluate("() => !$('#tries').hidden")
        ok(vis(), "новичок, экран пуст — «Попробуйте сказать» видно")
        box = pg.evaluate("() => { const r = $('#tries').getBoundingClientRect(), m = $('#mic').getBoundingClientRect(); return [r.bottom, m.top]; }")
        ok(box[0] <= box[1], f"на маленьком телефоне (360×740) подсказки не залезают под микрофон: {box}")
        pg.click("#tries .tq >> nth=1"); pg.wait_for_timeout(100)
        ok(pg.evaluate("window._asked") == ["Включи радио"], f"нажатие — спрашивает: {pg.evaluate('window._asked')}")
        pg.evaluate("() => { $('#bot').textContent = 'Ответ'; quietCheck(); }")
        ok(not vis(), "на экране ответ — подсказок нет")
        # «первая минута» (1.0.26): на экране только приветствие первого запуска — подсказки видны; пришёл ответ — нет
        pg.evaluate("() => greet('Готово, всё подключено. Нажмите на вопрос ниже — или на микрофон и говорите.')")
        box = pg.evaluate("() => { const r = $('#tries').getBoundingClientRect(), m = $('#mic').getBoundingClientRect(); return [r.bottom, m.top]; }")
        ok(vis() and box[0] <= box[1], f"приветствие первого запуска — подсказки под ним видны и не под микрофоном: {box}")
        pg.evaluate("() => showBot('Ответ')")
        ok(not vis(), "пришёл ответ — подсказки ушли")
        pg.evaluate("() => { $('#bot').textContent = ''; quietCheck(); setState('listening'); }")
        ok(not vis(), "слушает — подсказок нет")
        pg.evaluate("() => setState('idle')")
        ok(vis(), "снова тишина — подсказки вернулись")
        pg.evaluate("() => { S.tries.n = 4; quietCheck(); }")
        ok(not vis(), "спросил сам 4 раза — больше не показываем")
        pg.evaluate("() => { S.tries = { n: 0, off: false }; quietCheck(); }")
        pg.click("#tries-x"); pg.wait_for_timeout(100)
        ok(not vis() and pg.evaluate("S.tries.off") is True, "«Больше не показывать» — насовсем")
        pg.evaluate("() => { S.tries = null; history.push({ role: 'user', content: 'привет' }); quietCheck(); }")
        ok(not vis(), "кто уже разговаривал (есть история) — подсказки не появляются после обновления")
        pg.evaluate("() => { S.tries = null; history.length = 0; S.llm.base_url = ''; quietCheck(); }")
        ok(not vis() or pg.evaluate("loggedIn()"), "мозг не подключён — примеры не предлагаем")
        ok(not errs, f"телефон без ошибок: {errs[:2]}")
        b.close()
finally:
    shutil.rmtree(tmp, ignore_errors=True)

if fails:
    raise SystemExit(1)
