"""Оформление: темы виджета (calm — по умолчанию, graphite, neon — как раньше) и чем голос отзывается вокруг портрета
(лучи, пульс, волна). Виджет перекрашивается по настройкам ui.skin / ui.voice_fx, студия → «Оформление» — живые образцы
и выбор (и сама студия перекрашивается), телефон → «Ещё» → «Оформление». Облики рисуются в Chromium, ядро не нужно."""
import os, shutil, subprocess, sys, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


from settings import DEFAULTS  # noqa: E402
ok(DEFAULTS["ui"]["skin"] == "neusky" and DEFAULTS["ui"]["voice_fx"] == "bars", "по умолчанию — «Небесный» (20.10) и лучи")
sk = (ROOT / "ui/assets/skins.js").read_text(encoding="utf-8"); css = (ROOT / "ui/assets/skins.css").read_text(encoding="utf-8")
import re as _re
ids = _re.findall(r'id: "([a-z]+)"', sk)
ok(ids and all(f".skin-{i} " in css or f".skin-{i}," in css for i in ids) and all((ROOT / "ui/assets/skins" / f).exists() for f in _re.findall(r'skins/([a-z]+\.webp)', css)),
   f"у каждого фона из skins.js есть стиль, текстуры на месте: {ids}")
bs = (ROOT / "android/tools/www_assemble.sh").read_text(encoding="utf-8")
ok("skins.css" in bs and "ui/assets/skins\"" in bs, "сборка телефона берёт те же темы")
IMG = (ROOT / "data/avatars/lira.webp").as_uri()
FAKE = "window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };"
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    # облики: каждая анимация рисует кадры, когда говорит, и в покое не мешает
    pg = b.new_page(); pg.on("pageerror", lambda e: errs.append(str(e)))
    d = Path(tempfile.mkdtemp()); (d / "p.html").write_text(f"""<!doctype html><meta charset=utf-8><body style="background:#111">
<script src="{(ROOT / 'ui/assets/entities.js').as_uri()}"></script><script>
window.E = {{}}; window.cnt = {{}};
for (const fx of ["bars", "pulse", "wave"]) for (const tone of ["mono", "color"]) {{
  const c = document.createElement("canvas"); c.style.cssText = "width:160px;height:160px"; document.body.appendChild(c);
  const id = fx + "-" + tone, e = new DewiarEntity(c, {{ style: "photo", color: "#B78CFF", image: null, plate: false, tone, fx }});   // без фото: холст не «заражён» file://
  const ctx = c.getContext("2d"), st = ctx.stroke.bind(ctx); cnt[id] = 0; ctx.stroke = (...a) => {{ cnt[id]++; return st(...a); }};
  e.set({{ state: "speaking", level: .6 }}); E[id] = e;
}}
</script>""", encoding="utf-8")
    pg.goto((d / "p.html").as_uri()); pg.wait_for_timeout(1500)
    c = pg.evaluate("cnt")
    ok(all(v > 10 for v in c.values()), f"лучи, пульс и волна рисуются в обоих тонах: {c}")
    px = pg.evaluate("""() => { const out = {}; for (const id of ['bars-mono', 'bars-color']) { const cv = E[id].canvas, x = cv.getContext('2d');
        const d = x.getImageData(0, 0, cv.width, cv.height).data; let r = 0, g = 0, b = 0, n = 0;
        for (let i = 0; i < d.length; i += 4) if (d[i + 3] > 200 && Math.hypot((i / 4) % cv.width - cv.width / 2, Math.floor(i / 4 / cv.width) - cv.height / 2) > cv.width * 0.36) { r += d[i]; g += d[i + 1]; b += d[i + 2]; n++; }
        out[id] = n ? [r / n, g / n, b / n].map(Math.round) : null; } return out; }""")
    mono, color = px["bars-mono"], px["bars-color"]
    ok(mono and color and abs(mono[0] - mono[1]) < 30 and color[2] - color[1] > 25,
       f"сдержанный тон — белые лучи, цветной — цвета персонажа: {mono} / {color}")
    pg.close()

    # виджет: тема и анимация по настройкам
    pg = b.new_page(viewport={"width": 300, "height": 420}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.add_init_script(FAKE)
    pg.goto((ROOT / "ui/hud.html").as_uri() + "?mode=card&port=1"); pg.wait_for_timeout(800)
    w0 = pg.evaluate("() => [document.body.className, entity.tone, entity.fx]")
    ok("skin-neusky" in w0[0] and "light" in w0[0] and w0[1] == "neu" and w0[2] == "bars", f"виджет по умолчанию — «Небесный»: {w0}")
    pg.evaluate("() => core.emit('settings', { settings: { ui: { skin: 'neu' } } })")
    wl = pg.evaluate("() => [document.body.className, entity.tone, getComputedStyle(document.getElementById('bubble')).color, getComputedStyle(document.getElementById('bubble')).boxShadow]")
    ok("light" in wl[0] and "neu" in wl[0] and wl[1] == "neu" and wl[2] != "rgb(255, 255, 255)" and wl[3].count("rgb") >= 2,
       f"неоморфизм: светлая тема, тёмный текст, двойные тени, тёмные лучи: {wl[:3]}")
    pg.evaluate("() => core.emit('settings', { settings: { ui: { skin: 'neon', voice_fx: 'pulse' } } })")
    w1 = pg.evaluate("() => [document.body.className, entity.tone, entity.fx, getComputedStyle(document.getElementById('card')).backgroundImage.includes('51, 32, 58')]")
    ok("skin-neon" in w1[0] and "skin-calm" not in w1[0] and w1[1] == "color" and w1[2] == "pulse" and not w1[3], f"студия выбрала «Неон» и «Пульс» — виджет сразу перекрасился: {w1[:3]}")
    pg.evaluate("() => core.emit('settings', { settings: { ui: { skin: 'frost' } } })")
    ok("grain.webp" in pg.evaluate("getComputedStyle(document.getElementById('card')).backgroundImage"), "«Матовое стекло» — зерно подгрузилось в фон")
    pg.evaluate("() => core.emit('settings', { settings: { ui: { skin: 'calm' } } })")
    ok(pg.evaluate("getComputedStyle(document.getElementById('card')).backgroundImage.includes('51, 32, 58')"), "сдержанная тема — мягкий фон в фирменных цветах (#33203a в углу)")
    ok(pg.evaluate("getComputedStyle(document.getElementById('bubble')).borderTopWidth") == "0px", "строка состояния — без рамки")
    pg.evaluate("() => { updating = Date.now(); core.emit('offline'); }")
    up = pg.evaluate("() => [entity.state, $('say').textContent]")
    ok(up == ["idle", "Обновляюсь — скоро вернусь"], f"обновление: спокойное «обновляюсь», лицо не притушено: {up}")
    pg.evaluate("() => { updating = 0; core.emit('offline'); }")
    ok(pg.evaluate("entity.state") == "offline", "без обновления — честное «нет связи»")
    pg.close()

    # студия → «Оформление»
    pg = b.new_page(viewport={"width": 1100, "height": 760}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.add_init_script(FAKE)
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(1000)
    pg.evaluate("""(img) => { S = { ui: { skin: 'calm', voice_fx: 'bars' } }; personas = [{ id: 'lira', name: 'Лира', color: '#B78CFF', style: 'strings', avatar_url: img, live: 'lira' }];
      window.saved = []; window.save = (patch) => { saved.push(patch); Object.assign(S.ui, patch.ui || {}); return Promise.resolve(); };
      $('nav button[data-p="look"]').click(); }""", IMG)
    pg.wait_for_timeout(600)
    cards = pg.evaluate("() => [$$('#lk-skins .lk').length, $$('#lk-fx .lk canvas').length, $('#lk-skins .lk.on').dataset.skin, $('#lk-fx .lk.on').dataset.fx, $$('#lk-skins .lk-group').length]")
    ok(cards[0] >= 10 and cards[1:] == [3, "calm", "bars", 6], f"фоны по группам, три живых образца анимации, выбранное отмечено: {cards}")
    pg.click('.lk[data-skin="graphite"]'); pg.wait_for_timeout(300)
    pg.click('.lk[data-fx="wave"]'); pg.wait_for_timeout(300)
    ok(pg.evaluate("saved") == [{"ui": {"skin": "graphite"}}, {"ui": {"voice_fx": "wave"}}] and pg.evaluate("$('#lk-skins .lk.on').dataset.skin") == "graphite",
       f"выбор сохраняется сразу: {pg.evaluate('saved')}")
    # студия сама — в выбранном стиле: фон темы, светлые — тёмный текст, неоморфизм — двойные тени
    th = lambda: pg.evaluate("() => [document.documentElement.className, getComputedStyle(document.body).color, getComputedStyle(document.body).backgroundImage.slice(0, 60), getComputedStyle($('.lk.on')).boxShadow]")
    g = th()
    ok("st-skin" in g[0] and "st-light" not in g[0] and g[1] == "rgb(244, 244, 246)", f"«Графит»: студия в тёмной теме графита: {g[:3]}")
    pg.click('.lk[data-skin="snow"]'); pg.wait_for_timeout(300)
    w = th()
    ok("st-light" in w[0] and w[1] != "rgb(244, 244, 246)" and w[2] != g[2], f"«Белоснежная»: светлый фон и тёмный текст: {w[:3]}")
    pg.click('.lk[data-skin="neu"]'); pg.wait_for_timeout(300)
    n = th()
    ok("st-neu" in n[0] and "inset" in n[3], f"неоморфизм: выбранная карточка вдавлена в материал: {n[0]} / {n[3][:60]}")
    pg.click('.lk[data-skin="brand"]'); pg.wait_for_timeout(300)
    b0 = th()
    ok("st-skin" not in b0[0] and "120, 119, 198" in pg.evaluate("getComputedStyle(document.body).backgroundImage"), "«Фирменная» — студия как раньше")
    ok(pg.evaluate("localStorage.getItem('studio_skin')") == "brand", "тема запомнена — студия открывается сразу в ней")
    pg.close()

    # телефон → «Ещё» → «Оформление»
    www = Path(tempfile.mkdtemp()) / "www"
    shutil.copytree(ROOT / "android/assets/www", www)
    shutil.copy(ROOT / "ui/assets/entities.js", www / "entities.js")
    for f in ("skins.css", "skins.js"):                     # как в сборке (android/tools/build_apk.sh)
        shutil.copy(ROOT / "ui/assets" / f, www / f)
    shutil.copytree(ROOT / "ui/assets/skins", www / "skins", dirs_exist_ok=True)
    shutil.copytree(ROOT / "ui/assets/live", www / "live", dirs_exist_ok=True)
    (www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                    capture_output=True, text=True, check=True).stdout, encoding="utf-8")
    pg = b.new_page(viewport={"width": 393, "height": 820}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route("https://**", lambda r: r.abort())
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(900)
    th = pg.evaluate("async () => [(await quick('Спасибо большое')) || null, (await quick('ладно, благодарю')) || null, await quick('спасибо, а что ещё ты умеешь')]")
    ok(th[0] and th[1] and th[0]["say"].startswith(("Пожалуйста", "Обращайтесь")) and not th[2], f"телефон: «спасибо» — вежливый ответ без модели: {th}")
    ph0 = pg.evaluate("() => [document.body.className, orb.tone, orb.fx]")
    ok("skin-neusky" in ph0[0] and ph0[1] == "neu" and ph0[2] == "bars", f"телефон по умолчанию — «Небесный»: {ph0}")
    pg.evaluate("openSettings('about')"); pg.wait_for_timeout(400)
    card = pg.evaluate("() => [document.querySelector('#set-body').textContent.includes('№' + devId().slice(-4)), !!document.querySelector('#dev-ping')]")
    ok(card == [True, True], "«Этот телефон в кабинете»: №… как в списке экзамена и кнопка «Отметиться в кабинете»")
    pg.evaluate("openSettings('look')"); pg.wait_for_timeout(400)
    ok(pg.evaluate("$$('.skm').length") >= 20 and pg.evaluate("$$('.skm[data-skin=snow]').length") == 1
       and pg.evaluate("$('.skm.on').dataset.skin") == "neusky", "телефон: все темы — круглыми образцами (группы — в подсказке), и светлые тоже; выбранная отмечена")
    # 30.10 (отзыв «не видно всё сразу»): «Сейчас — …» сверху, сетка — прежняя
    ok(pg.locator(".skins").count() == 1, "телефон: темы — одной ровной сеткой (группы с подписями владельцу показались неаккуратными)")
    ok("Сейчас — Небесный" in pg.inner_text("#sk-now"), f"сверху — какая тема сейчас: {pg.inner_text('#sk-now')!r}")
    if os.environ.get("DEWIAR_SHOTS"):
        pg.screenshot(path=os.environ["DEWIAR_SHOTS"] + "/phone-skins.png", full_page=True)
    pg.click('.skm[data-skin="neon"]'); pg.select_option("#ap-fx", "pulse"); pg.wait_for_timeout(300)
    ok("Сейчас — Неон" in pg.inner_text("#sk-now"), "выбрали — строка сверху обновилась")
    ph1 = pg.evaluate("() => [document.body.className, orb.tone, orb.fx, S.skin, S.voice_fx]")
    ok("skin-neon" in ph1[0] and ph1[1:] == ["color", "pulse", "neon", "pulse"], f"телефон: тема и анимация меняются и запоминаются: {ph1}")
    pg.click('.skm[data-skin="snow"]'); pg.wait_for_timeout(300)
    sn = pg.evaluate("() => [document.body.className, orb.tone, getComputedStyle(document.getElementById('bot')).color, window._bars, $('.skm.on').dataset.skin]")
    ok("light" in sn[0] and sn[1] == "ink" and sn[2] != "rgb(244, 244, 246)" and sn[3] == ["#F8F9FB", True] and sn[4] == "snow",
       f"телефон: «Белоснежная» — тёмный текст, тёмные лучи, светлая строка состояния: {sn}")
    pg.click('.skm[data-skin="neudark"]'); pg.wait_for_timeout(300)
    nd = pg.evaluate("() => [document.body.className, getComputedStyle(document.getElementById('orbwrap'), '::before').boxShadow, window._bars]")
    ok("neu" in nd[0] and "light" not in nd[0] and nd[1].count("rgb") == 2 and nd[2] == ["#262a31", False],
       f"телефон: тёмный неоморфизм — выпуклый круг под обликом, полосы в цвет материала: {nd}")
    pg.close()
    b.close()
ok(not errs, f"без ошибок на страницах: {errs[:3]}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
