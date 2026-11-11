"""«Попробуйте плагин» на «Главной» (владелец 30.10: «на десктопе на главной показывать плагины — рандомно или ещё как, чтобы
человек видел, мог включить и сразу посмотреть, как работает; в будущем — видео к каждому»):
— одна карточка: ещё не включённый плагин, каждый день другой, стрелка — следующий;
— «Включить» — сразу; плагину нужны настройки (required) — «Настроить и включить» открывает его панель;
— включили — «Спросить Лиру» задаёт его фразу в чате (видно, как работает);
— ролик: свой (поле video — урок Академии или адрес) или общий урок «Плагины»;
— «×» — скрыть на две недели; все включены — карточки нет; мобильная ширина — без вылезания."""
import json, os, re, sys, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ["DEWIAR_STATE_DIR"] = str(tmp / "st"); os.environ["DEWIAR_CONFIG_DIR"] = str(tmp / "cfg")
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import settings as ST  # noqa: E402
import plugins as PL  # noqa: E402
P = PL.Plugins(ST.Settings(tmp / "s.json"))
cat = json.loads(json.dumps({"plugins": P.catalog()}, default=str))
t = next(x for x in cat["plugins"] if x["id"] == "tenders")
ok(t["try"] == "Есть новые тендеры?" and any(s["required"] for s in t["settings"]) and t["video"] == "", "в каталоге — фраза «попробуйте», обязательные настройки, ролик")
ok(next(x for x in cat["plugins"] if x["id"] == "kitchen")["try"] == next(x for x in cat["plugins"] if x["id"] == "kitchen")["phrases"][0],
   "нет своей фразы — первая из «Попробуйте сказать»")
lessons = [{"id": "15-plugins", "n": 15, "title": "Плагины", "about": "", "sec": 65, "video": "https://x.test/15.mp4", "poster": "", "youtube": ""}]
FAKE = """(() => { window.calls = []; window.CAT = CATJSON;
  const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.call = async (c, a) => { calls.push([c, a]);
      if (c === "academy_list") return { ok: true, items: LESSONS };
      if (c === "plugins") return JSON.parse(JSON.stringify(CAT));
      if (c === "plugin_install") { CAT.plugins.find(x => x.id === a.id).installed = true; return JSON.parse(JSON.stringify(CAT)); }
      if (c === "settings_save") { const pt = (a && a.patch) || {}; S.ui = Object.assign({}, S.ui, pt.ui || {}); return JSON.parse(JSON.stringify(S)); }
      return {}; };
    setTimeout(() => core.emit("hello", {}), 200); };
  ready(); })();""".replace("CATJSON", json.dumps(cat, ensure_ascii=False)).replace("LESSONS", json.dumps(lessons, ensure_ascii=False))
errs = []
with sync_playwright() as p:
    b = p.chromium.launch()
    st = b.new_page(viewport={"width": 1300, "height": 900}); st.on("pageerror", lambda e: errs.append(str(e)))
    st.route(re.compile(r"^https?://"), lambda r: r.abort()); st.add_init_script(FAKE)
    st.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); st.wait_for_timeout(1200)
    st.evaluate("() => { const w = document.querySelector('#wlc'); if (w) w.remove(); S = S || {}; S.ui = Object.assign({}, S.ui, { lessons_seen: { '15-plugins': 1 } }); document.querySelector('nav button[data-p=\"home\"]').click(); HM.ac = null; HM.tryI = 0; loadHome(); }")
    st.wait_for_timeout(1000)
    vis = lambda: st.evaluate("() => { const b = document.querySelector('#hm-try'); return !!b && !b.hidden && b.getBoundingClientRect().height > 60; }")
    name = lambda: st.inner_text("#hm-try .ht-t b")
    ok(vis() and "Попробуйте плагин" in st.inner_text("#hm-try"), "на «Главной» — карточка «Попробуйте плагин»")
    # 04.11 (владелец, снимок: «Дайджест по интересам» уже соседних блоков и «как будто другой дизайн»): ширина — как у
    # «Совета ИИ» и всей колонки, заголовок — шрифтом соседних карточек, не крупным Unbounded
    wd = st.evaluate("""() => { const t = document.querySelector('#hm-try'), c = document.querySelector('#hm-council'), p = t.parentElement, cs = getComputedStyle(p);
      return { t: t.getBoundingClientRect().width, c: c.hidden ? 0 : c.getBoundingClientRect().width,
               col: p.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight), f: getComputedStyle(t.querySelector('.ht-t b')).fontFamily }; }""")
    ok(abs(wd["t"] - wd["col"]) < 2 and (not wd["c"] or abs(wd["t"] - wd["c"]) < 2) and "Unbounded" not in wd["f"],
       f"карточка плагина — во всю ширину, как «Совет ИИ», заголовок как у соседей: {wd}")
    first = name()
    order = sorted([x for x in cat["plugins"] if not x["installed"]], key=lambda x: x["id"])
    ok(first == order[0]["name"] and "«" not in st.inner_text("#hm-try q"), f"плагин дня, фраза — репликой: {first}")
    st.click("#ht-next"); st.wait_for_timeout(150)
    ok(name() == order[1]["name"], f"стрелка — другой плагин: {name()}")
    ok(st.evaluate("!!document.querySelector('#ht-vid')") and "Как работают плагины" in st.inner_text("#ht-vid"), "свой ролик не задан — общий урок «Плагины»")
    st.evaluate("() => { window._played = null; lsPlay = (l) => { _played = l.id; }; }")
    st.click("#ht-vid"); st.wait_for_timeout(150)
    ok(st.evaluate("_played") == "15-plugins", "▶ — плеер с уроком")
    # «Тендеры»: нужны запросы — «Настроить и включить» ведёт в панель плагина
    st.evaluate("() => { HM.tryI = hmTryList().findIndex(p => p.id === 'tenders'); hmTry(); }")
    ok(st.inner_text("#ht-on") == "Настроить и включить", "плагину нужны настройки — «Настроить и включить»")
    st.click("#ht-on"); st.wait_for_timeout(500)
    ok(st.evaluate("document.querySelector('#p-skills').classList.contains('cur')") and st.evaluate("document.querySelector('#pld').classList.contains('open')")
       and "Тендеры" in st.inner_text("#pld-name"), "— открыта панель «Тендеров» в «Плагинах»")
    ok(not [c for c in st.evaluate("calls") if c[0] == "plugin_install"], "без настроек не установлен")
    # «Кухня» — включается сразу; после — «Спросить Лиру»
    st.evaluate("() => { document.querySelector('nav button[data-p=\"home\"]').click(); HM.tryI = hmTryList().findIndex(p => p.id === 'kitchen'); hmTry(); }")
    st.wait_for_timeout(200)
    ok(st.inner_text("#ht-on") == "Включить", "настройки не обязательны — просто «Включить»")
    st.click("#ht-on"); st.wait_for_timeout(400)
    ok(["plugin_install", {"id": "kitchen", "values": {}}] in st.evaluate("calls"), "«Включить» — установка одной кнопкой")
    ok("Плагин включён" in st.inner_text("#hm-try") and st.evaluate("!!document.querySelector('#ht-ask')"), "включили — «Плагин включён», «Спросить Лиру»")
    ok(st.evaluate("!!document.querySelector('#hm-plgs [data-app=\"plg:kitchen\"]')"), "и значок плагина появился среди плагинов")
    st.evaluate("() => { window._asked = null; qaAsk = (t) => { _asked = t; }; }")
    st.click("#ht-ask"); st.wait_for_timeout(200)
    ok(st.evaluate("_asked") == next(x for x in cat["plugins"] if x["id"] == "kitchen")["try"], "«Спросить Лиру» — его фраза в чате: видно, как работает")
    st.evaluate("() => { document.querySelector('nav button[data-p=\"home\"]').click(); hmTry(); }"); st.wait_for_timeout(200)
    ok(vis() and "Попробуйте плагин" in st.inner_text("#hm-try") and name() != "Кухня", "дальше — снова не включённые")
    # 05.11 (владелец: «блок в студии ты должен был выровнять — без изменений»): это <section>, а общее «section
    # {max-width: 1040px}» сужало его — на широком окне справа оставался зазор. Ширина — как у «Совета ИИ» и «Почты»
    st.set_viewport_size({"width": 1700, "height": 900}); st.wait_for_timeout(250)
    wd = st.evaluate("""() => { const w = (s) => { const e = document.querySelector(s); return e && !e.hidden ? Math.round(e.getBoundingClientRect().width) : 0; };
      return [w('#hm-try'), w('#hm-council'), w('#hm-today')]; }""")
    ok(wd[0] > 1040 and abs(wd[0] - max(wd[1], wd[2])) <= 2, f"широкое окно: «Попробуйте плагин» — во всю ширину, как соседние блоки: {wd}")
    if os.environ.get("TRY_WIDE"): st.screenshot(path=os.environ["TRY_WIDE"], full_page=True)
    st.set_viewport_size({"width": 1300, "height": 900}); st.wait_for_timeout(150)
    shot = tmp / "try.png"; st.locator("#hm-try").screenshot(path=str(shot))
    if os.environ.get("TRY_SHOT"): st.evaluate("() => { const h = document.documentElement; h.classList.toggle(\"st-light\"); }"); st.wait_for_timeout(300); st.locator("#hm-try").screenshot(path=os.environ["TRY_SHOT"]); st.evaluate("() => document.documentElement.classList.toggle(\"st-light\")")
    st.click("#ht-x"); st.wait_for_timeout(300)
    ok(not vis() and (st.evaluate("S.ui.try_hide_until") or 0) > st.evaluate("Date.now() + 13 * 864e5"), "«×» — скрыта на две недели")
    st.evaluate("() => { S.ui.try_hide_until = 0; HM.all.forEach(p => p.installed = true); hmTry(); }")
    ok(not vis(), "всё включено — карточки нет")
    st.evaluate("() => { HM.all.forEach(p => p.installed = false); HM.all.find(p => p.id === 'bedtime').video = 'https://x.test/b.mp4'; HM.tryI = hmTryList().findIndex(p => p.id === 'bedtime'); hmTry(); }")
    ok("Смотреть ролик" in st.inner_text("#ht-vid"), "свой ролик плагина — «Смотреть ролик»")
    st.set_viewport_size({"width": 390, "height": 860}); st.wait_for_timeout(200)
    r = st.evaluate("() => { const b = document.querySelector('#hm-try').getBoundingClientRect(); return [b.right <= innerWidth + 1, document.documentElement.scrollWidth <= innerWidth + 1]; }")
    ok(all(r), f"узкое окно — не вылезает: {r}")
    ok(not errs, f"без ошибок JavaScript: {errs[:2]}")
    print("снимок:", shot)
    b.close()
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
