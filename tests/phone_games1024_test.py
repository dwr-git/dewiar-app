"""24.10, владелец: «Досуг» и «Возможности» на телефоне. Значок с джойстиком вверху — лист «Досуг» с пятью играми
(arcade/shelf.js — тот же список, что у компьютера), игра — во весь экран; «Игры» в игре и «Назад» — снова полка.
«Лира, давай поиграем» — без модели. «Возможности» (Настройки → Ещё): «Досуг», «Рядом», «Встречи»; у новых «Рядом» и
«Встречи» выключены, у прежних — всё как было; выключенная вкладка в «Близких» не показывается."""
import os, re, shutil, subprocess, sys, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


tmp = Path(tempfile.mkdtemp()); www = tmp / "www"
subprocess.run(["bash", str(ROOT / "android/tools/www_assemble.sh"), str(www)], check=True, capture_output=True)
ok((www / "arcade/shelf.js").is_file() and (www / "arcade/snake/index.html").is_file(), "игры попадают в приложение (www_assemble)")
try:
    with sync_playwright() as p:
        b = p.chromium.launch(); errs = []

        def page(prefs):
            pg = b.new_page(viewport={"width": 393, "height": 820}); pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.route(re.compile(r"^https?://"), lambda r: r.abort())
            if prefs is not None:
                pg.add_init_script("localStorage.setItem('p_settings', %r);" % prefs)
            pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(1000)
            return pg

        # новый человек
        pg = page(None)
        f = pg.evaluate("() => S.features")
        ok(f == {"games": True, "near": False, "meet": False}, f"новый: «Рядом» и «Встречи» выключены, «Досуг» включён: {f}")
        ok(pg.is_visible("#b-play"), "значок «Досуг» вверху")
        pg.click("#b-play"); pg.wait_for_timeout(500)
        names = pg.evaluate("[...document.querySelectorAll('#play-body .ag b')].map(b => b.textContent)")
        ok(pg.is_visible("#sh-play") and names == ["Огонёк", "Хутор Одуванчик", "Кто боится темноты", "Тетрис", "Конфетки", "Слияние", "Колючая почта", "Пятнашки", "Судоку", "Найди пару", "Кроссворд", "Пять букв", "Пять в ряд", "Крестики-нолики", "Реверси", "Выше облаков", "Бип", "Гонка", "Небесный пилот", "Кирпичики", "Змейка"], f"лист «Досуг» — все игры по порядку (кроме «Каляки» — с 0.45.1 только на компьютере): {names}")
        pg.screenshot(path="/tmp/claude-0/phone_shelf.png")
        pg.click("#play-body .ag[data-game='bricks']"); pg.wait_for_timeout(1500)
        st = pg.evaluate("() => ({ ov: !$('#gameov').hidden, src: $('#gamef').getAttribute('src'), sheet: $('#sh-play').classList.contains('on'), z: getComputedStyle($('#gameov')).zIndex })")
        ok(st["ov"] and st["src"].startswith("arcade/bricks/index.html") and not st["sheet"], f"игра — во весь экран: {st}")
        pg.screenshot(path="/tmp/claude-0/phone_game.png")
        ok(pg.evaluate("N.back()") is True and not pg.is_visible("#gameov") and pg.is_visible("#sh-play")
           and pg.evaluate("$('#gamef').getAttribute('src')") == "about:blank", "«Назад» телефона — из игры на полку, игра выгружена")
        pg.click("#play-body .ag[data-game='snake']"); pg.wait_for_timeout(1500)
        next(fr for fr in pg.frames if "snake" in fr.url).locator("#aBack").click(); pg.wait_for_timeout(400)
        ok(not pg.is_visible("#gameov") and pg.is_visible("#sh-play"), "«Игры» в самой игре — снова полка")
        pg.evaluate("closeSheets()")
        r = pg.evaluate("async () => { const r = await quick('Лира, давай поиграем'); await new Promise(z => setTimeout(z, 600)); return r && r.say; }")
        ok(r and "игру" in r and pg.is_visible("#sh-play"), f"«Лира, давай поиграем» — без модели, полка: {r}")
        pg.evaluate("closeSheets()")
        r = pg.evaluate("async () => { const r = await quick('поиграем в змейку'); await new Promise(z => setTimeout(z, 900)); return r && r.say; }")
        ok(r == "Открываю Змейку." and pg.evaluate("$('#gamef').getAttribute('src')").startswith("arcade/snake/"), f"«поиграем в змейку» — сразу игра: {r}")
        pg.evaluate("gameClose(false)")
        r = pg.evaluate("async () => { const r = await quick('давай поиграем в крестики нолики'); await new Promise(z => setTimeout(z, 900)); return r && r.say; }")
        ok(r == "Открываю Крестики-нолики." and pg.evaluate("$('#gamef').getAttribute('src')").startswith("arcade/tictac/"), f"«поиграем в крестики нолики» — сразу игра: {r}")
        pg.evaluate("gameClose(false)"); pg.wait_for_timeout(200)
        for ph, gid, say in (("давай поиграем в пять в ряд", "five", "Открываю «Пять в ряд»."), ("открой найди пару", "pairs", "Открываю «Найди пару»."), ("поиграем в пары", "pairs", "Открываю «Найди пару».")):
            r = pg.evaluate(f"async () => {{ const r = await quick('{ph}'); await new Promise(z => setTimeout(z, 900)); return r && r.say; }}")
            ok(r == say and pg.evaluate("$('#gamef').getAttribute('src')").startswith(f"arcade/{gid}/"), f"«{ph}» — сразу игра: {r}")
            pg.evaluate("gameClose(false)"); pg.wait_for_timeout(200)
        r = pg.evaluate("async () => { const r = await quick('давай сыграем в города'); return r && r.say; }")
        ok(not r, "«давай сыграем в города» — это разговор, его ведёт модель")
        r = pg.evaluate("async () => { const r = await quick('открой блокнот'); return r && r.say || ''; }")
        ok("игр" not in r.lower() and "Открываю Тетрис" not in r, f"«открой блокнот» — не игра «Тетрис»: {r}")
        # «Возможности»: выключили «Досуг»
        pg.evaluate("() => { renderSettings && 0; S.features.games = false; saveS(); featApply(); }")
        ok(not pg.is_visible("#b-play"), "«Досуг» выключен — значка нет")
        r = pg.evaluate("async () => { const r = await quick('давай поиграем'); return r && r.say; }")
        ok(r and "Возможности" in r, f"и голосом — подсказка, где включить: {r}")
        # вкладки «Близких»
        tabs = pg.evaluate("""() => { S.llm = Object.assign({}, S.llm, { cloud: true, account: false, api_key: 'dw-test', base_url: 'https://dewiar.pro/dwrapp/cloud.php?p=' });
            clHello = async () => ({}); clTab = 'near'; try { openClose(''); } catch (e) { } return [...document.querySelectorAll('#cl-tabs button')].map(b => b.dataset.t); }""")
        ok(tabs and "close" in tabs and "near" not in tabs and "meet" not in tabs, f"у нового в «Близких» нет «Рядом» и «Встречи»: {tabs}")
        pg.evaluate("() => { S.features = { games: true, near: true, meet: true }; closeSheets(); openClose(''); }")
        tabs = pg.evaluate("[...document.querySelectorAll('#cl-tabs button')].map(b => b.dataset.t)")
        ok("near" in tabs and "meet" in tabs, f"включили — вкладки на месте: {tabs}")
        pg.close()
        # прежний человек — ничего не прячем
        pg = page('{"persona":"lira","user_name":"Миша"}')
        f = pg.evaluate("() => S.features")
        ok(f == {"games": True, "near": True, "meet": True}, f"у прежних всё как было: {f}")
        pg.close()
        ok(not [e for e in errs if "gamepad" not in e], f"без ошибок: {errs[:2]}")
        b.close()
finally:
    shutil.rmtree(tmp, ignore_errors=True)

if fails:
    raise SystemExit(1)
