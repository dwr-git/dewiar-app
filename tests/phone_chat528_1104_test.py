"""№528 (04.11, владелец, телефон 0.9.21): «В телефоне в беседе хочется написать, но как?» — в «Разговоре» лента с
«Прослушать / копировать / в заметки / скачать», а поля ввода нет, только системная навигация внизу. Теперь внизу листа —
поле, как в мессенджере: «Напишите…», микрофон и «Отправить» (пустое — «Отправить» неактивна). Написанное уходит в
разговор, в ленте сразу видно и вопрос, и ответ по мере прихода (до него — три точки), лист не закрывается; длинная
лента прокручивается под полем, поле — на месте. Обе темы — «Небесный» (neusky) и «Графит» (graphite) — на 390 px.
И главный экран: поле ввода по кнопке клавиатуры (идея №126) — на месте, в обеих темах.
Снимки — в папку из аргумента: python3 tests/phone_chat528_1104_test.py /tmp/shots"""
import os, shutil, subprocess, sys, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
SHOTS = Path(sys.argv[1]) if len(sys.argv) > 1 else None
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


www = Path(tempfile.mkdtemp()) / "www"
shutil.copytree(ROOT / "android/assets/www", www)
for x in ("entities.js", "rich.js", "skins.js", "skins.css"):
    if (ROOT / "ui/assets" / x).exists():
        shutil.copy(ROOT / "ui/assets" / x, www / x)
shutil.copytree(ROOT / "ui/assets/live", www / "live", dirs_exist_ok=True)
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                capture_output=True, text=True, check=True).stdout, encoding="utf-8")
HIST = [{"role": "user", "content": "обновись"},
        {"role": "assistant", "content": "Есть новая версия 0.9.22 — обновляю. Всё ваше сохранится.", "who": "lira"},
        {"role": "user", "content": "стоп"}, {"role": "assistant", "content": "Хорошо.", "who": "lira"},
        {"role": "assistant", "content": "Привет, Миша! С возвращением — день уже в самом разгаре. За окном пасмурно и +4, так что куртка не помешает.", "who": "lira"}]
with sync_playwright() as p:
    b = p.chromium.launch()
    for skin in ("neusky", "graphite"):
        pg = b.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2)
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(900)
        pg.evaluate("""([skin, hist]) => { S.onboarded = true; S.skin = skin; applyLook(); closeSheets();
            history = hist.map(m => Object.assign({ t: Date.now() }, m)); saveH();
            window._asked = []; }""", [skin, HIST])
        # ---------- главный экран: поле по кнопке клавиатуры (№126) ----------
        pg.click("#b-kb"); pg.wait_for_timeout(200)
        tb = pg.evaluate("() => { const r = document.querySelector('#typed').getBoundingClientRect(); return { vis: !!document.querySelector('#typed').offsetParent, w: r.width, bottom: r.bottom, send: getComputedStyle(document.querySelector('#send')).display }; }")
        ok(tb["vis"] and tb["w"] > 300 and tb["send"] != "none", f"{skin}: главный экран — по кнопке клавиатуры поле ввода и «Отправить»: {tb}")
        if SHOTS:
            SHOTS.mkdir(parents=True, exist_ok=True); pg.screenshot(path=str(SHOTS / f"528-main-{skin}.png"))
        pg.click("#b-kb"); pg.wait_for_timeout(150)

        # ---------- «Разговор»: поле внизу ----------
        pg.click("#b-hist"); pg.wait_for_timeout(500)
        g = pg.evaluate("""() => { const q = (s) => document.querySelector(s), r = (s) => q(s).getBoundingClientRect().toJSON();
            const sh = r('#sh-hist'), c = r('#hcomp'), t = r('#htyped'), m = r('#hmic'), s = r('#hsend');
            return { open: q('#sh-hist').classList.contains('on'), sh, c, t, m, s, sendOff: q('#hsend').disabled,
              ph: q('#htyped').placeholder, bg: getComputedStyle(q('#hcomp')).backgroundColor, vw: innerWidth }; }""")
        ok(g["open"] and abs(g["c"]["bottom"] - g["sh"]["bottom"]) < 2, f"{skin}: поле — у нижнего края листа «Разговор»")
        mids = [g[k]["top"] + g[k]["height"] / 2 for k in ("t", "m", "s")]
        ok(g["t"]["right"] <= g["m"]["left"] and g["m"]["right"] <= g["s"]["left"] and g["s"]["right"] <= g["vw"] - 8 and g["t"]["left"] >= 8
           and max(mids) - min(mids) < 2, f"{skin}: «Напишите…», микрофон и «Отправить» — в одну строку, в пределах 390 px")
        ok(g["t"]["width"] >= 230 and g["s"]["width"] >= 44 and g["m"]["width"] >= 44, f"{skin}: поле широкое, кнопки — под палец (44 px): {g['t']['width']:.0f}")
        ok(g["sendOff"] and g["ph"] == "Напишите…", f"{skin}: пустое поле — «Отправить» неактивна, подсказка «Напишите…», как на главном")
        ok("0, 0, 0, 0" not in g["bg"] and g["bg"] != "transparent", f"{skin}: у поля плотный фон — лента под ним не просвечивает: {g['bg']}")
        if SHOTS:
            pg.screenshot(path=str(SHOTS / f"528-chat-{skin}.png"))

        # пишем — уходит в разговор, лист открыт, вопрос и ответ видны сразу
        pg.evaluate("""() => { window._release = null;
            window.ask = async (t) => { window._asked.push(t); busy = true; showYou(t); showBot('', 'wait');
              await new Promise(r => window._release = r);
              showBot('Есть версия 0.9.22. Скажите «обновись» — обновлю.');
              history.push({ role: 'user', content: t }, { role: 'assistant', content: 'Есть версия 0.9.22. Скажите «обновись» — обновлю.', who: 'lira', t: Date.now() }); saveH(); busy = false; }; }""")
        pg.fill("#htyped", "Проверь, есть ли новая версия"); pg.wait_for_timeout(100)
        ok(not pg.evaluate("document.querySelector('#hsend').disabled"), f"{skin}: набрали — «Отправить» активна")
        pg.click("#hsend"); pg.wait_for_timeout(250)
        live = pg.evaluate("""() => ({ asked: window._asked, val: document.querySelector('#htyped').value, open: document.querySelector('#sh-hist').classList.contains('on'),
            you: (document.querySelector('#hlive .msg.u') || {}).textContent || '', dots: !!document.querySelector('#hlive .hdots'),
            seen: (() => { const r = document.querySelector('#hlive').getBoundingClientRect(), c = document.querySelector('#hcomp').getBoundingClientRect(); return r.bottom <= c.top + 2 && r.height > 20; })() })""")
        ok(live["asked"] == ["Проверь, есть ли новая версия"] and live["val"] == "" and live["open"],
           f"{skin}: «Отправить» — текст ушёл в разговор, поле очищено, лист не закрылся: {live['asked']}")
        ok("Проверь, есть ли новая версия" in live["you"] and live["dots"] and live["seen"],
           f"{skin}: в ленте сразу вопрос и три точки, над полем: {live}")
        if SHOTS:
            pg.screenshot(path=str(SHOTS / f"528-chat-wait-{skin}.png"))
        pg.evaluate("window._release()"); pg.wait_for_timeout(300)
        done = pg.evaluate("""() => ({ msgs: [...document.querySelectorAll('#hlist > .msg')].map(m => m.textContent.trim().slice(0, 40)),
            live: document.querySelector('#hlive').innerHTML, open: document.querySelector('#sh-hist').classList.contains('on') })""")
        ok(done["open"] and any("Проверь, есть ли новая версия" in m for m in done["msgs"]) and any("Есть версия 0.9.22" in m for m in done["msgs"])
           and not done["live"], f"{skin}: ответ пришёл — в ленте из истории, без дубля: {done['msgs'][-2:]}")
        # длинная лента — поле на месте, последний ответ над ним
        pg.evaluate("""() => { for (let i = 0; i < 14; i++) history.push({ role: 'user', content: 'Вопрос ' + i }, { role: 'assistant', content: 'Ответ номер ' + i + '. ' + 'Текст ответа. '.repeat(6), who: 'lira' }); saveH(); }""")
        pg.wait_for_timeout(300)
        lg = pg.evaluate("""() => { const sh = document.querySelector('#sh-hist'), c = document.querySelector('#hcomp').getBoundingClientRect(), last = [...document.querySelectorAll('#hlist > .msg')].pop().getBoundingClientRect();
            return { scroll: sh.scrollHeight > sh.clientHeight, cb: c.bottom, sb: sh.getBoundingClientRect().bottom, lastB: last.bottom, ct: c.top }; }""")
        ok(lg["scroll"] and abs(lg["cb"] - lg["sb"]) < 2 and lg["lastB"] <= lg["ct"] + 2, f"{skin}: длинная лента прокручивается, поле внизу, последний ответ — над ним: {lg}")
        # многострочное — растёт вверх; на телефоне Enter — новая строка (отправка кнопкой)
        h1 = pg.evaluate("document.querySelector('#htyped').getBoundingClientRect().height")
        pg.fill("#htyped", "Первая строка\nвторая\nтретья\nчетвёртая"); pg.wait_for_timeout(200)
        h2 = pg.evaluate("document.querySelector('#htyped').getBoundingClientRect().height")
        ok(h2 > h1 + 30, f"{skin}: длинный текст — поле растёт: {h1:.0f} → {h2:.0f}")
        if SHOTS:
            pg.screenshot(path=str(SHOTS / f"528-chat-multiline-{skin}.png"))
        # микрофон в «Разговоре» — тот же, что на главном экране
        pg.evaluate("() => { window._mic = 0; document.querySelector('#mic').onclick = () => { window._mic++; }; }")
        pg.click("#hmic"); pg.wait_for_timeout(100)
        ok(pg.evaluate("window._mic") == 1 and pg.evaluate("document.querySelector('#sh-hist').classList.contains('on')"), f"{skin}: микрофон в «Разговоре» — слушает, лист открыт")
        ok(not errors, f"{skin}: без ошибок: {errors}")
        pg.close()
    b.close()
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
