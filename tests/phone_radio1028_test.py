"""«Радио» на телефоне (0.65; как вкладка «Радио» в «Музыке» студии): «Всё» → «Радио» или нажать название станции.
Популярные — наш список плитками; значки — favicon из каталога (наш список — в фоне), нет — буквы; жанры и поиск по
каталогу без повторов; нажали — играет именно она, нажали играющую — пауза; ♥ — «Мои станции» (и голосом по названию);
каталог молчит — понятно; у «Для старших» плитки крупнее (два столбца)."""
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path
from urllib.parse import urlparse, parse_qs
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
SHOTS = os.environ.get("DEWIAR_SHOTS", "")
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


Q, MODE = [], {"down": False}
SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="12" fill="#e53935"/><circle cx="32" cy="32" r="13" fill="#fff"/></svg>'


def catalog(route):
    q = parse_qs(urlparse(route.request.url).query); Q.append(q)
    if MODE["down"]:
        return route.abort()
    name, tag = (q.get("name") or [""])[0], (q.get("tag") or [""])[0]
    if name.startswith("русское"):
        rows = [{"name": "Русское Радио", "url_resolved": "https://s.test/rr", "favicon": "https://x.test/rr.svg"}]
    elif tag == "jazz" or name.startswith("smooth"):
        rows = [{"name": "Smooth Jazz 24", "url_resolved": "https://s.test/sj", "favicon": "https://x.test/sj.svg", "tags": "jazz,smooth", "countrycode": "US"},
                {"name": "Smooth Jazz 24", "url_resolved": "https://s.test/sj2", "favicon": "", "tags": "jazz"},
                {"name": "Jazz Radio", "url_resolved": "https://s.test/jr", "favicon": "https://x.test/nope.png", "tags": "jazz", "countrycode": "FR"}]
    else:
        rows = []
    route.fulfill(status=200, headers={"Content-Type": "application/json"}, body=json.dumps(rows))


def icon(route):
    if route.request.url.endswith(".svg"):
        return route.fulfill(status=200, headers={"Content-Type": "image/svg+xml"}, body=SVG)
    route.fulfill(status=404, body="")


tmp = Path(tempfile.mkdtemp()); www = tmp / "www"
subprocess.run(["bash", str(ROOT / "android/tools/www_assemble.sh"), str(www)], check=True, capture_output=True)
from playwright.sync_api import sync_playwright  # noqa: E402
try:
    with sync_playwright() as p:
        b = p.chromium.launch(); errs = []
        pg = b.new_page(viewport={"width": 400, "height": 860}); pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.route("https://**.api.radio-browser.info/**", catalog); pg.route("https://x.test/**", icon)
        pg.route("https://dewiar.pro/**", lambda r: r.abort())
        pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(1000)
        pg.evaluate("() => { document.querySelectorAll('.sheet.on').forEach(s => s.classList.remove('on')); S.radio_fav = []; saveS(); prefSet('radio_logos', ''); }")
        pg.evaluate("() => openApps()"); pg.wait_for_timeout(400)
        ok(pg.locator("#apps-body [data-app=radio]").count() == 1, "во «Всё» — плитка «Радио»")
        pg.click("#apps-body [data-app=radio]"); pg.wait_for_timeout(1500)
        ok(pg.is_visible("#sh-radio"), "открылся лист «Радио»")
        names = pg.eval_on_selector_all("#radio-body [data-l=top] .rp-play b", "e => e.map(x => x.textContent)")
        ok(len(names) >= 10 and names[0] == "Русское Радио", f"«Популярные» — наш список: {names[:4]}")
        pg.wait_for_timeout(1500)
        pic = pg.evaluate("document.querySelector('#radio-body [data-l=top] .rp-logo').classList.contains('pic')")
        ok(pic and pg.evaluate("JSON.parse(prefGet('radio_logos'))['русское'].logo") == "https://x.test/rr.svg", "значок станции нашего списка нашёлся в каталоге")
        mono = pg.eval_on_selector_all("#radio-body [data-l=top] .rp-logo:not(.pic) i", "e => e.map(x => x.textContent)")
        ok(mono and all(1 <= len(m) <= 2 for m in mono), f"без значка — буквы: {mono[:4]}")
        chips = pg.eval_on_selector_all(".rp-chip", "e => e.map(x => x.textContent)")
        ok(chips[0] == "Популярные" and "Джаз" in chips, f"жанры: {chips}")

        pg.click(".rp-chip:text-is('Джаз')"); pg.wait_for_timeout(1200)
        names = pg.eval_on_selector_all("#radio-body [data-l=top] .rp-play b", "e => e.map(x => x.textContent)")
        ok("Smooth Jazz 24" in names and names.count("Smooth Jazz 24") == 1 and "Jazz Radio" in names, f"«Джаз»: свои и каталог без повторов: {names}")
        ok(any(q.get("tag") == ["jazz"] for q in Q), "каталог спрошен по тегу jazz")
        pg.wait_for_timeout(600)
        i = names.index("Smooth Jazz 24")
        tile = f"#radio-body [data-l=top] .rp-t:nth-child({i + 1})"
        ok(pg.evaluate(f"document.querySelector('{tile} .rp-logo').classList.contains('pic')"), "значок из каталога")
        j = names.index("Jazz Radio")
        ok(not pg.evaluate(f"!!document.querySelector('#radio-body [data-l=top] .rp-t:nth-child({j + 1}) .rp-logo img')"), "значок не загрузился — буквы")

        pg.click(f"{tile} .rp-play"); pg.wait_for_timeout(600)
        ok(pg.evaluate("D._radio.url") == "https://s.test/sj" and pg.evaluate("radio.state().state") == "playing", "нажали — играет именно она")
        now = pg.inner_text(".rp-now")
        ok("В эфире" in now and "Smooth Jazz 24" in now, f"сверху — что играет: {now!r}")
        ok("on" in pg.get_attribute(f"{tile}", "class"), "играющая плитка отмечена")
        if SHOTS:
            pg.screenshot(path=os.path.join(SHOTS, "phone-radio.png"))
        pg.click("#rp-heart"); pg.wait_for_timeout(300)
        fav = pg.evaluate("S.radio_fav")
        ok(fav and fav[0]["name"] == "Smooth Jazz 24" and fav[0]["logo"] == "https://x.test/sj.svg", f"♥ — в «Моих станциях»: {fav}")
        ok(pg.eval_on_selector_all("#radio-body [data-l=mine] .rp-play b", "e => e.map(x => x.textContent)") == ["Smooth Jazz 24"], "«Мои станции» сверху")
        ok(pg.evaluate("radio.match('smooth jazz 24')[0].url") == "https://s.test/sj", "голосом «включи Smooth Jazz 24» — найдётся")
        pg.click("#radio-body [data-l=mine] .rp-t.on .rp-play"); pg.wait_for_timeout(300)
        ok(pg.evaluate("radio.state().state") == "paused" and "На паузе" in pg.inner_text(".rp-now"), "нажали играющую — пауза")
        pg.click("#rp-pp"); pg.wait_for_timeout(300)
        ok(pg.evaluate("radio.state().state") == "playing", "⏯ — снова играет")
        pg.click("#radio-body [data-l=mine] .rp-fav"); pg.wait_for_timeout(300)
        ok(pg.evaluate("S.radio_fav.length") == 0 and pg.locator("#radio-body [data-l=mine]").count() == 0, "♥ ещё раз — убрана")

        pg.fill("#rp-q", "Smooth"); pg.press("#rp-q", "Enter"); pg.wait_for_timeout(1000)
        ok(pg.inner_text("#radio-body h3.rp-h") == "«Smooth»" and any(q.get("name") == ["smooth"] for q in Q), "поиск по названию")
        pg.fill("#rp-q", ""); pg.wait_for_timeout(400)
        ok(pg.inner_text("#radio-body h3.rp-h") == "Популярные", "очистили — снова популярные")
        MODE["down"] = True
        pg.fill("#rp-q", "Минск"); pg.press("#rp-q", "Enter"); pg.wait_for_timeout(1500)
        ok("Каталог радиостанций сейчас не отвечает" in pg.inner_text("#radio-body"), "каталог молчит — понятно")
        # название станции над Лирой — открывает «Радио»
        pg.evaluate("() => closeSheets()"); pg.wait_for_timeout(300)
        pg.click("#rchip > b"); pg.wait_for_timeout(500)
        ok(pg.is_visible("#sh-radio"), "нажать название станции — открывается «Радио»")
        pg.evaluate("() => { S.senior = { on: true }; saveS(); srApply(); openRadio(); }"); pg.wait_for_timeout(400)
        cols = pg.evaluate("getComputedStyle(document.querySelector('#radio-body .rp-grid')).gridTemplateColumns.split(' ').length")
        ok(cols == 2, f"«Для старших» — два столбца, крупнее: {cols}")
        ok(pg.evaluate("[...document.querySelectorAll('#radio-body .rp-t')].every(t => t.getBoundingClientRect().right <= innerWidth + 1)"), "плитки не вылезают за экран")
        b.close()
    ok(not errs, "без ошибок JavaScript" + (f": {errs[:3]}" if errs else ""))
finally:
    shutil.rmtree(tmp, ignore_errors=True)
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
