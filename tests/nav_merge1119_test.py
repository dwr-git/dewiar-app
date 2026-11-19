"""19.11, владелец (вычитание меню): «все верно, это самые не популярные разделы… Убрать лишнее.. но как-то так элегантно,
чтобы и было, но не мелькало лишний раз без необходимости». Разделы не пропали, а ушли вкладками в соседние:
«Обучение» (Неделя с Лирой, Видеоуроки, Вопрос — ответ, Что я умею) — один пункт внизу; «Память и душа» (Память, Дневник,
Душа, Конституция, Обо мне); «Семья» — вкладкой «Платежей» («+ Семья», пока не включена); «Рефералы» — вкладкой
«Dewiar.pro»; «Для ребёнка» и «Для старших» — в меню только включённый режим (выбор — «Главная» и «Возможности»)."""
import os, re, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


VIS = "() => [...document.querySelectorAll('nav > button[data-p], nav > .ng')].filter(x => x.offsetParent).map(x => x.dataset.p || '#' + x.textContent.trim())"
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 1400, "height": 1300}); pg.on("pageerror", lambda e: errs.append(str(e) + " @ " + (e.stack or "")[:300]))
    pg.route(re.compile(r"^https?://"), lambda r: r.abort())
    pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };")
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(900)
    pg.evaluate("""() => { window._saves = []; window._mode = 'me';
      S = Object.assign({}, S || {}, { features: { family: false, team: false, clients: false, games: true }, ui: {} });
      core.call = (c, a) => { if (c === 'settings_save') { _saves.push(a.patch); S = JSON.parse(JSON.stringify(S));
          for (const [k, v] of Object.entries(a.patch)) S[k] = Object.assign({}, S[k] || {}, v); return Promise.resolve(S); }
        if (c === 'mode_get') return Promise.resolve({ mode: _mode, people: [] });
        if (c === 'pay_overview') return Promise.resolve({ bills: [] });
        return Promise.resolve({}); };
      featuresApply(); }""")
    pg.wait_for_timeout(300)
    vis = pg.evaluate(VIS)
    for gone in ("lessons", "qa", "tricks", "diary", "family", "ref", "kids", "senior"):
        ok(gone not in vis, f"в меню нет отдельного «{gone}»")
    ok("#Обучение" not in vis and "#Режимы Лиры" not in vis, f"пустые заголовки групп («Обучение», «Режимы Лиры») — прочь: {vis}")
    ok(vis.index("course") > vis.index("insight") and vis.index("course") < vis.index("ideas"), "«Обучение» — внизу, рядом с «Идеями Лиры»")
    ok(pg.inner_text('nav button[data-p="course"]').strip() == "Обучение" and pg.inner_text('nav button[data-p="memory"]').strip() == "Память и душа",
       "названия пунктов: «Обучение», «Память и душа»")
    ok(len([x for x in vis if not x.startswith("#")]) <= 38, f"пунктов в меню — 38 (было 45): {len(vis)}")

    # «Обучение»: вкладки, возврат на последнюю
    pg.click('nav button[data-p="course"]'); pg.wait_for_timeout(200)
    tabs = pg.evaluate("[...document.querySelectorAll('#p-course > .ntabs button')].filter(x => !x.hidden).map(x => x.textContent.trim())")
    ok(tabs == ["Неделя с Лирой", "Видеоуроки", "Вопрос — ответ", "Что я умею"], f"«Обучение» — четыре вкладки: {tabs}")
    pg.click('#p-course > .ntabs button[data-go="qa"]'); pg.wait_for_timeout(200)
    ok(pg.evaluate("document.querySelector('#p-qa').classList.contains('cur') && document.querySelector('nav button[data-p=course]').classList.contains('cur')"),
       "вкладка «Вопрос — ответ» открыта, слева горит «Обучение»")
    ok(pg.evaluate("document.querySelector('#p-qa > .ntabs button[data-go=qa]').classList.contains('on')"), "вкладка отмечена")
    pg.click('nav button[data-p="home"]'); pg.wait_for_timeout(100); pg.click('nav button[data-p="course"]'); pg.wait_for_timeout(200)
    ok(pg.evaluate("document.querySelector('#p-qa').classList.contains('cur')"), "снова «Обучение» — та же вкладка, где были")
    if os.environ.get("DEWIAR_SHOTS"): pg.screenshot(path=str(Path(os.environ["DEWIAR_SHOTS"]) / "studio-learn.png"))

    # «Память и душа»
    pg.click('nav button[data-p="memory"]'); pg.wait_for_timeout(200)
    tabs = pg.evaluate("[...document.querySelectorAll('#p-memory > .ntabs button')].map(x => x.textContent.trim())")
    ok(tabs == ["Память", "Дневник", "Душа", "Конституция", "Обо мне"], f"«Память и душа» — пять вкладок: {tabs}")
    pg.click('#p-memory > .ntabs button[data-go="soul"]'); pg.wait_for_timeout(200)
    ok(pg.evaluate("document.querySelector('#p-soul').classList.contains('cur') && document.querySelector('nav button[data-p=memory]').classList.contains('cur')"),
       "«Душа» — вкладкой, слева горит «Память и душа»")

    # «Платежи» + «Семья» (по желанию)
    pg.click('nav button[data-p="pay"]'); pg.wait_for_timeout(200)
    fam = pg.evaluate("(() => { const x = document.querySelector('#p-pay > .ntabs button[data-go=family]'); return x && [x.hidden, x.classList.contains('nopt')]; })()")
    ok(fam == [False, True], f"«Платежи»: вкладка «+ Семья», пока семья не включена: {fam}")
    ok(pg.evaluate("[...document.querySelectorAll('nav .nopt')].filter(x => !x.hidden && x.offsetParent).every(x => x.dataset.feat !== 'family')"),
       "в меню строки «+ Семья» больше нет — она во вкладках «Платежей»")
    pg.click('#p-pay > .ntabs button[data-go="family"]'); pg.wait_for_timeout(500)
    ok({"features": {"family": True}} in pg.evaluate("_saves") and pg.evaluate("document.querySelector('#p-family').classList.contains('cur')"),
       "нажали «+ Семья» — включено и открыто")
    ok(pg.evaluate("document.querySelector('nav button[data-p=pay]').classList.contains('cur')"), "слева горит «Платежи»")
    pg.evaluate("document.getElementById('fam-dot').classList.add('on')"); pg.wait_for_timeout(100)
    ok(pg.evaluate("[...document.querySelectorAll('nav button[data-p=pay] .ndot')].some(x => x.classList.contains('on'))"),
       "зовут в семью — точка у «Платежей» слева")

    # «Dewiar.pro» + «Рефералы»
    pg.click('nav button[data-p="dw"]'); pg.wait_for_timeout(200)
    tabs = pg.evaluate("[...document.querySelectorAll('#p-dw > .ntabs button')].filter(x => !x.hidden).map(x => x.dataset.go)")
    ok(tabs == ["dw", "ref"], f"«Dewiar.pro» — вкладка «Рефералы»: {tabs}")

    # режимы: в меню — только включённый
    pg.evaluate("() => { _mode = 'senior'; mdLoad(); }"); pg.wait_for_timeout(300)
    vis = pg.evaluate(VIS)
    ok("senior" in vis and "kids" not in vis and "#Режимы Лиры" in vis, f"включили «Для старших» — он в меню, «Для ребёнка» — нет: {vis[-30:]}")
    pg.evaluate("() => { _mode = 'me'; mdLoad(); }"); pg.wait_for_timeout(300)
    ok("senior" not in pg.evaluate(VIS), "выключили — снова не мелькает")
    pg.click('nav button[data-p="features"]'); pg.wait_for_timeout(200)
    ok(pg.is_visible("#ft-mode"), "«Возможности»: «Для ребёнка и для старших» — «Выбрать режим»")
    pg.click("#ft-mode"); pg.wait_for_timeout(300)
    ok(pg.is_visible("#md-dlg"), "«Выбрать режим» — тот же выбор, что на «Главной»")
    pg.keyboard.press("Escape")
    if os.environ.get("DEWIAR_SHOTS"): pg.screenshot(path=str(Path(os.environ["DEWIAR_SHOTS"]) / "studio-nav-merge.png"), clip={"x": 0, "y": 0, "width": 260, "height": 1300})
    b.close()
ok(not errs, "без ошибок JavaScript" + (f": {errs[:3]}" if errs else ""))
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
