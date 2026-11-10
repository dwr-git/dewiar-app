"""№557 (ПК 0.84.0, 05.11, снимок): «На главной большой текст уезжает за границы панели. И ещё: я не нашёл „жучка“ на
главной :)». В «Утре с Лирой» строка дела «19:00 — Посмотри прогноз погоды (weather) для города «Балашов» на 2 дня. Если
ночью до 0° …» шла одной строкой далеко за край панели, тот же текст заливал синюю карточку «Дальше сегодня» на восемь строк;
у заголовка «Доброе утро, Роман» не было «жучка» и «лампочки» (их стирал hmRender, переписывая заголовок целиком).
№558 (05.11): «чтобы в левой колонке с командами был именно тот порядок, который я настроил под себя» — меню слева
идёт в порядке значков «Главной» (внутри своих групп), сразу после перестановки и после перезапуска.
Идея №142 (05.11): города в «Утре» нет, а в памяти есть — погода по нему и «из памяти · Запомнить».
Имя дела по расписанию вместо поручения модели — core (tests/jobs557_test.py); здесь — что видит человек."""
import json, os, re, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
SHOTS = os.environ.get("DEWIAR_SHOTS") or ""
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


LONG = ("Посмотри прогноз погоды (weather) для города «Балашов» на 2 дня. Если ночью до 0° и ниже — предупреди укрыть: …; "
        "если жара от +28 без дождя — напомни полить. Иначе ничего не сообщай")
MORNING = {"date": "2026-11-05", "weekday": "четверг", "time": "09:41", "city": "", "city_mem": "Балашове",
           "weather": {"city": "Балашов", "place": "Балашов, Саратовская область", "now": 3, "feels": 0, "sky": "пасмурно", "wind": 4,
                       "min": 1, "max": 6, "sky_day": "пасмурно", "rain": 20, "line": "Балашов: сейчас +3°"},
           "today": {"meet": [], "todo": [{"time": "19:00", "title": LONG}]}, "team": None, "clients": None, "mail": None, "tasks": None,
           "settings": {}, "daily": None, "mail_on": False}
CAL = {"days": {"2026-11-05": [{"type": "reminder", "id": "r1", "time": "19:00", "title": LONG, "text": LONG, "kind": "job", "done": False}]}}
FAKE = """(() => { window.calls = []; window.MORNING = MJSON; window.CAL = CJSON;
  const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.call = async (c, a) => { calls.push([c, a]);
      if (c === "morning_get") return JSON.parse(JSON.stringify(MORNING));
      if (c === "morning_set") { const m = JSON.parse(JSON.stringify(MORNING)); m.city = a.city; delete m.city_mem; m.settings = { city: a.city }; return m; }
      if (c === "calendar_month") return JSON.parse(JSON.stringify(CAL));
      if (c === "plugins") return { plugins: [{ id: "dacha", name: "Дача и огород", icon: "🌱", color: "#9BE15D", installed: true, settings: [], jobs: [] },
                                               { id: "kitchen", name: "Кухня", icon: "🍲", color: "#f90", installed: true, settings: [], jobs: [] }] };
      if (c === "done") return { today: 0, streak: 0 };
      if (c === "settings_save") { const pt = (a && a.patch) || {}; S.ui = Object.assign({}, S.ui, pt.ui || {}); return JSON.parse(JSON.stringify(S)); }
      if (c === "bug_shot") return { ok: true, preview: "", shots: [] };
      return {}; };
    setTimeout(() => core.emit("hello", {}), 200); };
  ready(); })();""".replace("MJSON", json.dumps(MORNING, ensure_ascii=False)).replace("CJSON", json.dumps(CAL, ensure_ascii=False))

errs = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1600, "height": 900}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.clock.set_fixed_time("2026-11-05T09:41:00")            # «Утро» видно с 4 до 13 часов
    pg.route(re.compile(r"^https?://"), lambda r: r.abort()); pg.add_init_script(FAKE)
    pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: (t, k) => (...a) => { (window.apiCalls = window.apiCalls || []).push([k, ...a]); return Promise.resolve(true); } }) };")
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(1200)
    pg.evaluate("() => { const w = document.querySelector('#wlc'); if (w) w.remove(); S = S || {}; S.user_name = 'Роман'; S.ui = Object.assign({}, S.ui, { lessons_seen: { x: 1 }, try_hide_until: Date.now() + 864e5 });"
                " document.querySelector('nav button[data-p=\"home\"]').click(); HM.ac = { at: Date.now(), d: { items: [] } }; loadHome(); }")
    pg.wait_for_timeout(1200)
    # как на снимке человека: четыре карточки «Сегодня» — у «Дальше сегодня» узкая колонка
    pg.evaluate("""() => { HM.data.py = { bills: [{ name: 'Платёж родителям', icon: '🧾', now: { s: 'soon', due: '2026-11-07' } }] };
      HM.ac = { at: Date.now(), d: { items: [{ id: 'l1', n: 1, title: 'Дозор', sec: 68, about: 'Лира присмотрит и скажет, когда готово' }] } };
      S.ui = Object.assign({}, S.ui, { lessons_seen: {} }); hmRender(); }""")
    pg.wait_for_timeout(300)

    # ---------- №557 (а): текст — в границах панели ----------
    g = pg.evaluate("""() => { const m = document.querySelector('#hm-morning'), r = m.getBoundingClientRect(), sm = [...m.querySelectorAll('.mn-rows small')];
      const card = document.querySelector('#hm-today .hm-card.next'), cb = card.querySelector('b'), lh = parseFloat(getComputedStyle(cb).lineHeight);
      return { hidden: m.hidden, sw: m.scrollWidth, cw: m.clientWidth, right: Math.max(...sm.map(x => x.getBoundingClientRect().right)), mr: r.right,
               rows: sm.map(x => Math.round(x.getBoundingClientRect().height / parseFloat(getComputedStyle(x).lineHeight))),
               cardLines: Math.round(cb.getBoundingClientRect().height / lh), cardH: card.getBoundingClientRect().height,
               full: (() => { cb.style.cssText = "display:block;-webkit-line-clamp:none;line-clamp:none;overflow:visible"; const n = Math.round(cb.getBoundingClientRect().height / lh); cb.style.cssText = ""; return n; })(),
               tip: card.title, page: document.documentElement.scrollWidth, vw: innerWidth }; }""")
    ok(not g["hidden"] and g["sw"] <= g["cw"] + 1 and g["right"] <= g["mr"], f"«Утро»: длинное дело переносится внутри панели, не за край: {g}")
    ok(g["rows"] and max(g["rows"]) <= 2, f"строка дела — не длиннее двух строк: {g['rows']}")
    ok(g["cardLines"] <= 3 and g["full"] > 3 and LONG[:40] in g["tip"], f"«Дальше сегодня» — не больше трёх строк, с «…», полный текст — во всплывающей подсказке: {g['cardLines']} строк, {g['cardH']:.0f}px")
    ok(g["page"] <= g["vw"], "страница не шире окна")
    if SHOTS:
        pg.screenshot(path=f"{SHOTS}/home557-light.png", clip={"x": 0, "y": 0, "width": 1600, "height": 900})

    # ---------- №557 (в): «жучок» и «лампочка» у «Доброе утро, …» ----------
    h = pg.evaluate("""() => { hmRender(); const h1 = document.querySelector('#p-home .hm-hi h1'), sp = h1.querySelector('#hm-greet');
      const bb = h1.querySelector('.hb-bug'), bi = h1.querySelector('.hb-idea'), t = sp && sp.getBoundingClientRect(), bbr = bb && bb.getBoundingClientRect();
      return { text: sp && sp.textContent, bug: !!bb, idea: !!bi, mid: t && bbr ? Math.abs((t.top + t.bottom) / 2 - (bbr.top + bbr.bottom) / 2) : 99 }; }""")
    ok(h["bug"] and h["idea"] and h["text"] == "Доброе утро, Роман", f"на «Главной» у приветствия — «жучок» и «лампочка», и они переживают перерисовку: {h}")
    ok(h["mid"] < 6, f"кнопки — по середине строки заголовка (смещение {h['mid']:.1f}px)")
    pg.click("#p-home .hm-hi h1 .hb-bug"); pg.wait_for_timeout(500)
    ok(any(c[0] == "bug_shot" for c in pg.evaluate("calls")) and pg.evaluate("document.querySelector('#rep-note').value") == "",
       "«жучок» на «Главной» снимает экран и открывает «Сообщить о проблеме» (без «Раздел «…»:» — это не раздел)")
    ok(["shot_hide", True] in pg.evaluate("apiCalls") and ["shot_hide", False] in pg.evaluate("apiCalls"),
       "№559: на время снимка виджет прячется и возвращается (shot_hide true → false)")
    pg.click('nav button[data-p="home"]'); pg.wait_for_timeout(300)

    # ---------- идея №142: город из памяти — «Запомнить» ----------
    ok(pg.is_visible("#mn-csave") and "из памяти" in pg.inner_text("#hm-morning .mn-w"), "города в «Утре» нет — погода по городу из памяти и «из памяти · Запомнить»")
    pg.click("#mn-csave"); pg.wait_for_timeout(300)
    ok(["morning_set", {"city": "Балашов, Саратовская область"}] in pg.evaluate("calls") and not pg.is_visible("#mn-csave"),
       "«Запомнить» — город «Утра» (как нашёл геокодер, с областью); после — без пометки «из памяти»")

    # ---------- тёмная тема ----------
    pg.evaluate("() => { MN = Object.assign({}, MN, { city: '', city_mem: 'Балашове' }); mnRender(); studioSkin('neudark', true); }"); pg.wait_for_timeout(500)
    g2 = pg.evaluate("() => { const m = document.querySelector('#hm-morning'); return { sw: m.scrollWidth, cw: m.clientWidth }; }")
    ok(g2["sw"] <= g2["cw"] + 1, "и в тёмной теме — в границах")
    if SHOTS:
        pg.screenshot(path=f"{SHOTS}/home557-dark.png", clip={"x": 0, "y": 0, "width": 1600, "height": 900})
    pg.evaluate("studioSkin('neusky', true)"); pg.wait_for_timeout(300)

    # ---------- №558: порядок меню — как на «Главной» ----------
    navs = lambda grp: pg.evaluate("""(g) => { const out = []; let on = false;
      for (const el of document.querySelector('nav').children) { if (el.classList.contains('ng')) { on = el.textContent.trim() === g; continue; }
        if (on && el.tagName === 'BUTTON' && el.dataset.p) out.push(el.dataset.p); } return out; }""", grp)
    before = navs("Для себя")
    ok(before[:3] == ["chat", "calendar", "reminders"], f"пока главную не настраивали — порядок меню свой: {before}")
    order = ["music", "vault", "chat", "notes", "reminders", "calendar", "pay", "council", "tasks", "watch", "plg:kitchen", "plg:dacha", "close"]
    pg.evaluate("(o) => hmSave(o)", order); pg.wait_for_timeout(300)
    got = navs("Для себя")
    ok(got == ["music", "vault", "chat", "notes", "reminders", "calendar", "pay"], f"перетащили значки — «Для себя» в том же порядке сразу: {got}")
    ok(navs("Лира делает сама")[:2] == ["council", "tasks"], f"и в других группах — внутри своей группы: {navs('Лира делает сама')}")
    ok(pg.evaluate("() => [...document.querySelectorAll('nav .ng')].map(x => x.textContent.trim()).slice(0, 2)") == ["Для себя", "Лира делает сама"],
       "группы и их заголовки — на месте")
    pg.evaluate("plpCatalog()"); pg.wait_for_timeout(300)
    ok(pg.evaluate("[...document.querySelectorAll('#nav-plugins .nav-plg')].map(x => x.dataset.plg)") == ["kitchen", "dacha"], "плагины в меню — тоже по главной")
    # перезапуск: настройки пришли с ядром — порядок тот же (hello → hmNav)
    pg.reload(); pg.wait_for_timeout(1200)
    pg.evaluate("(o) => core.emit('settings', { settings: Object.assign({}, S || {}, { ui: Object.assign({}, (S && S.ui) || {}, { home_apps: o }) }) })", order); pg.wait_for_timeout(400)
    ok(navs("Для себя") == ["music", "vault", "chat", "notes", "reminders", "calendar", "pay"], "после перезапуска — тот же порядок")
    if SHOTS:
        pg.screenshot(path=f"{SHOTS}/nav558.png", clip={"x": 0, "y": 0, "width": 260, "height": 900})

    # ---------- узко: без вылезания ----------
    pg.set_viewport_size({"width": 700, "height": 900})
    pg.evaluate("() => { document.querySelector('nav button[data-p=\"home\"]').click(); loadHome(); }"); pg.wait_for_timeout(900)
    ok(pg.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), "узкое окно — без горизонтальной прокрутки")
    b.close()
ok(not errs, "без ошибок JavaScript" + (f": {errs[:3]}" if errs else ""))
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
