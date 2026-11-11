"""«Подкасты» в студии (0.87): страница во всех видах тем (по умолчанию, светлая neusky, тёмная neudusk, фирменная тёмная brand, светлая snow) и в узком окне.
- пункт «Подкасты» в «Лира делает сама», «?» раздела, значок на «Главной»;
- «Новый выпуск»: файлы (выбор — список с размером и «×»), ссылка из поля — строкой «страница/видео», длина, подача,
  ведущие (поменять ролями), цена до старта; «Сделать подкаст» отправляет файлы, длину, подачу, ведущих, язык, заставку;
- ход работы — этапы по событиям ядра, полоса готовности, «Остановить»;
- готовый выпуск — две дорожки ведущих (полоса на каждую реплику их цветами), текст выпуска; нажатие на реплику —
  перемотка и подсветка; «Скачать MP3», «На телефон», «Открыть папку», «Удалить»; остановленный — «Продолжить».
Звук — настоящий MP3 (podcast.encode)."""
import json
import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
import numpy as np  # noqa: E402
import podcast as PC  # noqa: E402

FAILS = []
SHOTS = os.environ.get("DEWIAR_SHOTS", "")


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        FAILS.append(m)


try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("⚠ playwright нет — проверка пропущена")
    sys.exit(0)

tmp = Path(tempfile.mkdtemp())
# настоящий MP3: реплики — тоны двух высот, паузы между ними
texts = [("a", "Что меньше бактерии и всё же губит табачные поля?"), ("b", "Ого! Не знаю."),
         ("a", "В 1892 году Дмитрий Ивановский пропустил сок больного табака через фарфоровый фильтр — и сок остался заразным."),
         ("b", "Подожди… то есть фильтр не помог?"), ("a", "Именно. Так и нашли вирусы: они меньше любых пор."), ("b", "Ага."),
         ("a", "Вирус меньше бактерии в сотни раз — в обычный микроскоп его не увидеть."),
         ("b", "Значит, прививка — это тренировка против невидимки?"), ("a", "Точно. Главное: крошечные, открыты фильтром, а прививки учат организм заранее.")]
lines, out, t = [], [], 0.0
for who, tx in texts:
    n = int(PC.OUT_RATE * (0.4 + 0.035 * len(tx)))
    tone = (np.sin(2 * np.pi * (440 if who == "a" else 180) * np.arange(n) / PC.OUT_RATE) * 7000).astype(np.int16)
    lines.append({"who": who, "text": tx, "t0": round(t, 2), "t1": round(t + n / PC.OUT_RATE, 2)})
    out += [tone, np.zeros(int(0.3 * PC.OUT_RATE), dtype=np.int16)]
    t += n / PC.OUT_RATE + 0.3
mp3 = PC.encode(np.concatenate(out), tmp, "Невидимки")
ok(mp3.suffix == ".mp3" and mp3.stat().st_size > 2000, f"MP3 для проигрывателя: {mp3.name}")
HOSTS = [{"id": "lira", "name": "Лира", "color": "#9BD4FF"}, {"id": "patrik", "name": "Патрик", "color": "#FFB547"},
         {"id": "eva", "name": "Эва", "color": "#FF7AC6"}]
EP = {"id": "a1b2c3d4e5", "title": "Невидимки: как открыли вирусы", "status": "done", "created": 1762850000, "done_at": 1762850300,
      "minutes": 5, "style": "simple", "duration": round(t, 1), "audio": mp3.name, "uri": mp3.as_uri(), "path": "Подкасты/x/Невидимки.mp3",
      "folder": "Подкасты/x", "hosts": {"a": HOSTS[0], "b": HOSTS[1]}, "lines": lines,
      "sources": [{"kind": "file", "name": "вирусы.pdf", "title": "вирусы.pdf"}], "checked": {"fixed": 1, "missing": ["вирус не растёт на питательной среде"]}}
STOP = {"id": "f0f0f0f0f0", "title": "Как работает память", "status": "stopped", "created": 1762840000, "hosts": EP["hosts"], "lines": [], "minutes": 10, "style": "deep"}
ITEMS = [{"id": EP["id"], "title": EP["title"], "status": "done", "created": EP["created"], "duration": EP["duration"], "audio": True},
         {"id": STOP["id"], "title": STOP["title"], "status": "stopped", "created": STOP["created"], "duration": 0, "audio": False}]
EST = {"minutes": 10, "talers": 0.046, "rub": 3.7, "answers": 9, "voice": "голоса Dewiar", "wait": 4, "cloud": True, "long": False}

CORE = """(() => { const ready = () => { if (!window.core) return setTimeout(ready, 5);
  core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
  window.CALLS = []; window.D = DATA;
  core.call = async (c, a) => { window.CALLS.push([c, a]);
    if (c === "podcast_list") return { items: D.items, state: D.state || null, hosts: D.hosts, pick: ["lira", "patrik"] };
    if (c === "podcast_get") return a.id === D.ep.id ? D.ep : D.stop;
    if (c === "podcast_estimate") return D.est;
    if (c === "podcast_start") return { id: "c0c0c0c0c0", title: "Сны", minutes: a.minutes, hosts: {} };
    if (c === "podcast_send") return { to: "Telegram" };
    if (c === "podcast_resume") return { id: D.stop.id, title: D.stop.title };
    if (c === "ws_export") return { dir: "/home/u/Загрузки", name: "Невидимки.mp3" };
    return null; };
  setTimeout(() => core.emit("hello", {}), 200); };
  ready(); })();"""
DATA = json.dumps({"items": ITEMS, "hosts": HOSTS, "ep": EP, "stop": STOP, "est": EST}, ensure_ascii=False)
fdir = tmp / "in"
fdir.mkdir()
(fdir / "лекция.pdf").write_bytes(b"%PDF-1.4 " + b"x" * 300_000)
(fdir / "глава.epub").write_bytes(b"PK" + b"x" * 1000)

with sync_playwright() as p:
    b = p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
    for skin in ("", "neusky", "neudusk", "brand", "snow"):
        errs = []
        pg = b.new_page(viewport={"width": 1360, "height": 920})
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.route(re.compile(r"^https?://"), lambda r_: r_.abort())
        pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };")
        pg.add_init_script(CORE.replace("DATA", DATA))
        pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1" + (f"&skin={skin}" if skin else ""))
        pg.wait_for_timeout(1200)
        nav = pg.locator('nav button[data-p="podcast"]')
        ok(nav.count() == 1 and "Подкасты" in nav.inner_text(), "пункт «Подкасты» в меню")
        nav.click()
        pg.wait_for_timeout(700)
        ok(pg.evaluate("CALLS.some(c => c[0] === 'podcast_list')"), "страница спрашивает список выпусков")
        main = pg.inner_text("#pd-main")
        ok(EP["title"] in main and "Ведут Лира и Патрик" in main and "вирусы.pdf" in main, f"последний выпуск открыт ({skin or 'по умолчанию'})")
        ok(pg.locator("#pd-main .pd-bars i").count() == len(lines) and pg.locator("#pd-main .pd-bars i.r1").count() == 4,
           "две дорожки: полоса на каждую реплику, у Патрика — свои")
        ok(pg.locator("#pd-main .pd-ln").count() == len(lines) and "Сверка с материалом поправила 1 место" in main, "текст выпуска и сверка")
        pg.wait_for_function("document.querySelector('#pd-main audio').readyState >= 1", timeout=8000)
        ok(abs(pg.evaluate("document.querySelector('#pd-main audio').duration") - t) < 0.6, "MP3 открылся в проигрывателе, длина верная")
        pg.locator("#pd-main .pd-ln").nth(2).click()
        pg.wait_for_timeout(400)
        cur = pg.evaluate("document.querySelector('#pd-main audio').currentTime")
        ok(cur >= lines[2]["t0"] - 0.05 and pg.locator("#pd-main .pd-ln.now").get_attribute("data-i") == "2"
           and pg.locator("#pd-main .pd-bars i.now").get_attribute("data-i") == "2", f"нажатие на реплику — перемотка и подсветка: {cur:.2f}")
        pg.evaluate("document.querySelector('#pd-main audio').pause()")
        box = pg.locator("#pd-main .pd-bars").bounding_box()
        pg.mouse.click(box["x"] + box["width"] * 0.9, box["y"] + 10)
        pg.wait_for_timeout(300)
        ok(abs(pg.evaluate("document.querySelector('#pd-main audio').currentTime") - 0.9 * EP["duration"]) < 0.6, "нажатие на дорожку — перемотка")
        pg.wait_for_timeout(300)
        ok("0,046 талера" in pg.inner_text("#pd-cost") and "≈ 3,7 ₽" in pg.inner_text("#pd-cost") and "9 обычных ответов" in pg.inner_text("#pd-cost")
           or "темы одной строкой" in pg.inner_text("#pd-cost"), "строка цены")
        if SHOTS:
            pg.screenshot(path=f"{SHOTS}/podcast-episode-{skin or 'default'}.png", full_page=False)
        if not skin:
            # «Новый выпуск»: файлы, ссылка, длина, подача, ведущие
            pg.set_input_files("#pd-file", [str(fdir / "лекция.pdf"), str(fdir / "глава.epub")])
            pg.fill("#pd-topic", "для школьника https://youtu.be/abc123 и https://example.org/statya")
            pg.wait_for_timeout(600)
            src = pg.inner_text("#pd-src")
            ok("лекция.pdf" in src and "глава.epub" in src and "youtu.be/abc123" in src and "видео" in src and "страница" in src,
               f"материал — списком: файлы с размером, ссылки: {src!r}")
            ok("0,046 талера" in pg.inner_text("#pd-cost") and "через 4" in pg.inner_text("#pd-cost") and "голоса Dewiar" in pg.inner_text("#pd-cost"),
               f"цена и время до старта: {pg.inner_text('#pd-cost')!r}")
            e = pg.evaluate("CALLS.filter(c => c[0] === 'podcast_estimate').pop()[1]")
            ok(e["urls"] == 2 and len(e["files"]) == 2 and e["files"][0]["size"] > 300_000, f"оценка знает о файлах и ссылках: {e}")
            pg.locator("#pd-src li button").first.click()
            ok("лекция.pdf" not in pg.inner_text("#pd-src"), "«×» убирает файл")
            pg.click('#pd-len button[data-m="20"]')
            pg.click('#pd-style [data-s="debate"]')
            ok("за" in pg.inner_text("#pd-hosts") and "против" in pg.inner_text("#pd-hosts"), "«Спор двух мнений» — ведущие «за» и «против»")
            pg.click("#pd-hosts .pd-swap")
            ok(pg.eval_on_selector('#pd-hosts select[data-k="0"]', "s => s.value") == "patrik", "ведущих можно поменять ролями")
            pg.click("#pd-go")
            pg.wait_for_timeout(700)
            st = pg.evaluate("CALLS.filter(c => c[0] === 'podcast_start').pop()[1]")
            ok(st["minutes"] == 20 and st["style"] == "debate" and st["hosts"] == ["patrik", "lira"] and len(st["files"]) == 1
               and st["files"][0]["name"] == "глава.epub" and st["files"][0]["b64"].startswith("data:") and "youtu.be" in st["topic"] and st["intro"] is True,
               f"«Сделать подкаст» — всё, что выбрано: { {k: v for k, v in st.items() if k != 'files'} }")
            ok(pg.locator("#pd-main .pd-steps li").count() == 7 and pg.is_disabled("#pd-go"), "пошёл ход работы, кнопка занята")
            for stg, pct, note in (("read", 3, ""), ("digest", 15, "часть 2 из 4"), ("script", 40, "часть 1 из 2"), ("voice", 80, "реплика 51 из 120")):
                pg.evaluate("([s, p, n]) => core.emit('podcast', {id: 'c0c0c0c0c0', stage: s, pct: p, note: n, status: 'working', title: 'Сны: что это было'})", [stg, pct, note])
                pg.wait_for_timeout(120)
            now = pg.locator("#pd-main .pd-steps li.now")
            ok(now.get_attribute("data-k") == "voice" and "реплика 51 из 120" in now.inner_text() and pg.locator("#pd-main .pd-steps li.done").count() == 5
               and "Сны: что это было" in pg.inner_text("#pd-main .pd-title"), "этапы по событиям ядра, название из плана")
            ok("80%" in pg.get_attribute("#pd-main .pd-bar b", "style"), "полоса готовности")
            if SHOTS:
                pg.locator("#p-podcast").screenshot(path=f"{SHOTS}/podcast-progress.png")
            pg.click("#pd-main .pd-stop")
            ok(pg.evaluate("CALLS.some(c => c[0] === 'podcast_stop')"), "«Остановить»")
            # остановленный — «Продолжить»
            pg.evaluate("PD.live = null; pdOpen('f0f0f0f0f0')")
            pg.wait_for_timeout(300)
            ok("Продолжить" in pg.inner_text("#pd-main") and "остановили" in pg.inner_text("#pd-main"), "остановленный выпуск — «Продолжить»")
            pg.click('#pd-main [data-a="resume"]')
            pg.wait_for_timeout(200)
            ok(pg.evaluate("CALLS.some(c => c[0] === 'podcast_resume' && c[1].id === 'f0f0f0f0f0')"), "«Продолжить» — ядру")
            pg.evaluate("PD.live = null; pdOpen('a1b2c3d4e5')")
            pg.wait_for_timeout(300)
            pg.click('#pd-main [data-a="phone"]')
            pg.wait_for_timeout(200)
            pg.click('#pd-main [data-a="dl"]')
            pg.wait_for_timeout(200)
            ok(pg.evaluate("CALLS.some(c => c[0] === 'podcast_send') && CALLS.some(c => c[0] === 'ws_export' && c[1].path.endsWith('.mp3'))"),
               "«На телефон» и «Скачать MP3»")
            ok(pg.evaluate("typeof DEWIAR_HELP !== 'undefined' && !!DEWIAR_HELP.podcast"), "у раздела есть «?»")
            # пустая страница и узкое окно
            pg.evaluate("D.items = []; PD.cur = ''; loadPodcasts()")
            pg.wait_for_timeout(400)
            ok("первый выпуск" in pg.inner_text("#pd-main"), "без выпусков — приглашение начать")
            if SHOTS:
                pg.screenshot(path=f"{SHOTS}/podcast-empty.png")
            pg.evaluate("D.items = %s; loadPodcasts()" % json.dumps(ITEMS, ensure_ascii=False))
            pg.set_viewport_size({"width": 860, "height": 900})
            pg.wait_for_timeout(500)
            ok(pg.evaluate("document.querySelector('main').scrollWidth <= document.querySelector('main').clientWidth + 1"), "узкое окно — без прокрутки вбок")
            if SHOTS:
                pg.screenshot(path=f"{SHOTS}/podcast-narrow.png", full_page=False)
            # рецензия 0.87: подменённый podcast.json (или ответ ядра) — разметкой не становится
            dialogs = []
            pg.on("dialog", lambda d_: (dialogs.append(d_.message), d_.dismiss()))
            evil = {"id": '"><img src=x onerror=alert(1)>', "title": "<img src=x onerror=alert(5)>", "status": 'x"><svg onload=alert(2)>',
                    "created": "<b>", "duration": "<img src=x onerror=alert(6)>", "audio": True}
            evil_ep = dict(EP, id='"><img src=x onerror=alert(1)>', title="<svg onload=alert(7)>", duration="<img src=x onerror=alert(8)>",
                           uri="javascript:alert(9)", checked={"fixed": "<img src=y onerror=alert(3)>", "missing": ["<img src=z onerror=alert(4)>"]},
                           hosts={"a": dict(HOSTS[0], name="<img src=q onerror=alert(10)>"), "b": HOSTS[1]})
            pg.evaluate("([it, ep]) => { D.items = [it]; D.ep = ep; PD.cur = ''; PD.live = null; loadPodcasts(); }", [evil, evil_ep])
            pg.wait_for_timeout(600)
            pg.evaluate("pdOpen(D.ep.id)")
            pg.wait_for_timeout(500)
            inj = pg.evaluate("document.querySelectorAll('#p-podcast img, #p-podcast svg[onload], #p-podcast [onerror], #p-podcast [onload]').length")
            ok(inj == 0 and not dialogs and "<svg onload=alert(7)>" in pg.inner_text("#pd-main .pd-title")
               and not pg.evaluate("(document.querySelector('#pd-main audio') || {}).src || ''").startswith("javascript:"),
               f"чужие поля выпуска — текстом, не разметкой: элементов {inj}, окон {dialogs}")
            pg.evaluate("D.items = %s; D.ep = %s; loadPodcasts()" % (json.dumps(ITEMS, ensure_ascii=False), json.dumps(EP, ensure_ascii=False)))
            pg.wait_for_timeout(400)
            pg.evaluate("document.querySelector('nav button[data-p=\"home\"]').click()")
            pg.wait_for_timeout(500)
            ok(pg.evaluate("[...document.querySelectorAll('#p-home [data-app], #p-home button')].some(x => /Подкасты/.test(x.textContent))"), "значок на «Главной»")
        ok(not errs, f"без ошибок на странице ({skin or 'по умолчанию'}): {errs[:2]}")
        pg.close()
    b.close()

print("ИТОГ:", "всё прошло" if not FAILS else f"провалов {len(FAILS)}")
sys.exit(1 if FAILS else 0)
