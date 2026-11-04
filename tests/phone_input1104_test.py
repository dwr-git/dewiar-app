"""Телефон, идеи №126 и №127 (04.11, RusMan).
№126: «На главном экране поле ввода текста — больше; при наборе увеличивается вверх; кнопки разместить в линию. Важно для
сложных промптов». Теперь: многострочное поле растёт вверх до 40% высоты экрана (дальше — прокрутка в нём), а скрепка,
клавиатура, микрофон (поменьше), разговор и «Отправить» — одной строкой под ним; сцена с ответом поднимается над панелью.
Клавиатура компьютера (веб): Enter — отправить, Shift+Enter — новая строка; телефон — Enter даёт новую строку, отправка кнопкой.
№127: «В чате на смартфоне — кнопки: Скопировать, В заметки, Скачать» — у каждого ответа в «Разговоре».
Снимки — в папку из аргумента (input-before/after делались этим же сценарием)."""
import json, os, shutil, subprocess, sys, tempfile
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
shutil.copy(ROOT / "ui/assets/entities.js", www / "entities.js")
shutil.copytree(ROOT / "ui/assets/live", www / "live", dirs_exist_ok=True)
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                capture_output=True, text=True, check=True).stdout, encoding="utf-8")
LONG = ("Составь план запуска онлайн-курса по фотографии для новичков: 6 недель, по уроку в неделю. Для каждого урока — тема, "
        "домашнее задание и что проверить. Учти, что ученики снимают на телефон. В конце — как продвигать курс без бюджета.")
ANSWER = "## План курса\n\n1. Свет и композиция.\n2. Портрет.\n\nГлавное — снимать каждый день."
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2)
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(900)
    pg.evaluate("""() => { S.onboarded = true; document.querySelectorAll('.sheet.on').forEach(x => x.classList.remove('on'));
        window._asked = []; window.ask = (t, o) => { window._asked.push(t); }; }""")

    # ---------- №126: поле ввода ----------
    closed = pg.evaluate("() => ['#b-att', '#send'].map(s => getComputedStyle(document.querySelector(s)).display)")
    ok(closed == ["none", "none"], f"поле закрыто — скрепки и «Отправить» нет, внизу как прежде: {closed}")
    pg.click("#b-kb"); pg.wait_for_timeout(150)
    ok(pg.evaluate("() => document.querySelector('#typed').tagName") == "TEXTAREA", "поле ввода — многострочное (textarea)")
    pg.fill("#typed", "Короткий вопрос"); pg.wait_for_timeout(150)
    short = pg.evaluate("() => document.querySelector('#typed').getBoundingClientRect().toJSON()")
    row = pg.evaluate("""() => ['#b-att', '#b-kb', '#mic', '#b-hist', '#send'].map(s => { const r = document.querySelector(s).getBoundingClientRect();
        return { s, mid: r.top + r.height / 2, h: r.height, left: r.left, right: r.right, vis: !!document.querySelector(s).offsetParent }; })""")
    mids = [r["mid"] for r in row]
    ok(all(r["vis"] for r in row) and max(mids) - min(mids) < 3, f"скрепка, клавиатура, микрофон, разговор, «Отправить» — в одну линию: {[round(m) for m in mids]}")
    ok(all(a["right"] <= b["left"] for a, b in zip(row, row[1:])) and row[0]["left"] >= 0 and row[-1]["right"] <= 390,
       "кнопки в линию не налезают друг на друга и не выходят за экран (390)")
    ok(row[2]["h"] <= 60, f"микрофон в строке — поменьше ({row[2]['h']:.0f} px), поле важнее")
    ok(short["bottom"] <= min(r["mid"] - r["h"] / 2 for r in row), "поле — над строкой кнопок")
    pg.fill("#typed", LONG); pg.wait_for_timeout(250)
    big = pg.evaluate("() => document.querySelector('#typed').getBoundingClientRect().toJSON()")
    ok(big["height"] > short["height"] * 2.5 and abs(big["bottom"] - short["bottom"]) < 2 and big["top"] < short["top"] - 100,
       f"при наборе поле растёт вверх (низ на месте): {short['height']:.0f} → {big['height']:.0f} px")
    if SHOTS:
        SHOTS.mkdir(parents=True, exist_ok=True); pg.screenshot(path=str(SHOTS / "input-after.png"))
    pg.fill("#typed", "\n".join(f"Строка {i}" for i in range(40))); pg.wait_for_timeout(250)
    huge = pg.evaluate("() => { const t = document.querySelector('#typed'); return { h: t.getBoundingClientRect().height, ov: getComputedStyle(t).overflowY, sh: t.scrollHeight }; }")
    ok(huge["h"] <= 844 * 0.4 + 3 and huge["sh"] > huge["h"] and huge["ov"] == "auto", f"не выше 40% экрана, дальше — прокрутка в поле: {huge}")
    st = pg.evaluate("() => ({ stage: document.querySelector('#stage').getBoundingClientRect().bottom, bar: document.querySelector('#bar').getBoundingClientRect().top })")
    ok(st["stage"] <= st["bar"] + 1, f"сцена с ответом заканчивается над панелью, ответ не прячется под поле: {st}")
    # Enter: клавиатура компьютера — отправить; Shift+Enter — новая строка
    pg.fill("#typed", "первая"); pg.press("#typed", "Shift+Enter"); pg.type("#typed", "вторая")
    ok(pg.evaluate("() => [document.querySelector('#typed').value, window._asked.length]") == ["первая\nвторая", 0], "Shift+Enter — новая строка, не отправка")
    pg.press("#typed", "Enter"); pg.wait_for_timeout(100)
    r = pg.evaluate("() => [window._asked.slice(-1)[0], document.querySelector('#typed').value, document.querySelector('#typed').getBoundingClientRect().height]")
    ok(r[0] == "первая\nвторая" and r[1] == "" and r[2] < 60, f"Enter — отправить (обе строки), поле снова маленькое: {r}")
    pg.fill("#typed", "кнопкой"); pg.click("#send"); pg.wait_for_timeout(100)
    ok(pg.evaluate("() => window._asked.slice(-1)[0]") == "кнопкой", "«Отправить» в строке кнопок — отправляет")
    src = (ROOT / "android/assets/www/app.js").read_text(encoding="utf-8")
    ok('matchMedia("(pointer: coarse)")' in src and "|| TOUCH) return;" in src, "на телефоне (палец) Enter — новая строка, отправка кнопкой")

    # ---------- №127: «Скопировать», «В заметки», «Скачать» у ответа в «Разговоре» ----------
    pg.evaluate("""(a) => { window._copied = []; window._saved = [];
        D.copy = (t) => { window._copied.push(t); return true; }; D.saveDownload = (n, m, t) => { window._saved.push([n, m, t]); return 'Загрузки/' + n; };
        history = [{ role: 'user', content: 'План курса?' }, { role: 'assistant', content: a, who: 'lira' }]; }""", ANSWER)
    pg.click("#b-kb"); pg.click("#b-hist"); pg.wait_for_timeout(300)
    btns = pg.evaluate("() => [...document.querySelectorAll('#hlist .msg.a [data-ma]')].map(b => [b.dataset.ma, b.getAttribute('aria-label')])")
    ok([x[0] for x in btns] == ["copy", "note", "save"] and all(x[1] for x in btns), f"у ответа — три действия с подписями: {btns}")
    ok(pg.evaluate("() => document.querySelectorAll('#hlist .msg.u [data-ma]').length") == 0, "у своих сообщений — нет")
    n0 = pg.evaluate("() => notes().length")
    pg.click("#hlist [data-ma=copy]"); pg.click("#hlist [data-ma=note]"); pg.click("#hlist [data-ma=note]"); pg.click("#hlist [data-ma=save]")
    pg.wait_for_timeout(200)
    r = pg.evaluate("() => ({ copied: window._copied, notes: notes(), saved: window._saved })")
    ok(r["copied"] == [ANSWER], "«Скопировать» — весь ответ")
    added = r["notes"][n0:]
    ok(len(added) == 1 and added[0]["text"] == ANSWER and added[0]["title"] == "План курса", f"«В заметки» — одна заметка, второй раз не дублирует: {[x['title'] for x in added]}")
    ok(len(r["saved"]) == 1 and r["saved"][0][0] == "План курса.md" and r["saved"][0][1] == "text/markdown" and r["saved"][0][2] == ANSWER,
       f"«Скачать» — файлом .md: {[x[0] for x in r['saved']]}")
    geo = pg.evaluate("""() => { const m = document.querySelector('#hlist .msg.a'), r = m.getBoundingClientRect();
        return [...m.querySelectorAll('.mrow button')].every(b => { const q = b.getBoundingClientRect(); return q.right <= r.right + 1 && q.height >= 32; }); }""")
    ok(geo, "кнопки в строке ответа помещаются на 390 px и удобны пальцу (≥ 32 px)")
    if SHOTS:
        pg.screenshot(path=str(SHOTS / "chat-actions.png"))
    ok(not errors, f"без ошибок на странице: {errors[:2]}")
    b.close()
print("ИТОГ:", "OK" if not fails else f"{len(fails)} ошибок")
sys.exit(1 if fails else 0)
