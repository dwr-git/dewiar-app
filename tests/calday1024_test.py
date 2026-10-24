"""Календарь в студии (24.10, владелец: «хочется нажать на день и просмотреть подробнее, не получается… пытаюсь сделать
блок справа больше»). Щелчок по дню — день крупно поверх месяца: по времени, задачи, заметки, дневник, деньги с итогом,
текст целиком; ← → — соседние дни (и через границу месяца), Esc — к месяцу. Правый столбец тянется мышью за край."""
import datetime as dt, json, os, re
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


today = dt.date.today(); D = today.isoformat()
LONG = "Итог дня: что сделано из дел на сегодня, что осталось, сколько потрачено за день и что запланировано на завтра — коротко"
DAYS = {D: [
    {"type": "reminder", "title": "Обед — не забудь взять карту", "time": "13:00", "done": True},
    {"type": "event", "title": "Созвон с командой", "time": "09:30", "end": "10:00", "cal": "Работа"},
    {"type": "reminder", "title": LONG, "time": "21:00", "id": "r1"},
    {"type": "task", "title": "Сделать бэкап файлов и скопировать органайзер", "id": "t1", "status": "Идёт"},
    {"type": "note", "title": "Идеи", "path": "notes/idei.md"},
    {"type": "diary", "title": "Дневник", "path": "diary/x.md"},
    {"type": "money", "kind": "expense", "amount": 60, "currency": "BYN", "title": "продукты", "category": "еда", "id": "m1"},
    {"type": "money", "kind": "income", "amount": 1, "currency": "BYN", "title": "бонус", "category": "доход", "id": "m2"}]}
FAKE = "window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };"
CORE = r"""
(() => { window.calls = []; window.DAYS = %s;
  const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.call = async (c, a) => { calls.push([c, a]);
      if (c === "calendar_month") return { days: a.month === %d ? DAYS : {}, currency: "BYN" };
      if (c === "settings_save") return S;
      return {}; }; };
  ready(); })();
""" % (json.dumps(DAYS, ensure_ascii=False), today.month)
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 1400, "height": 900}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route(re.compile(r"^https?://"), lambda r: r.abort())
    pg.add_init_script(FAKE); pg.add_init_script(CORE)
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(900)
    pg.evaluate("() => { S = Object.assign({}, S || {}, { ui: {}, llm: { profiles: {} }, features: {} }); }")
    pg.evaluate("() => { $('nav button[data-p=\"calendar\"]').click(); }"); pg.wait_for_timeout(500)
    pg.click(f"#cal-grid .day[data-d='{D}']"); pg.wait_for_timeout(400)
    ok(pg.evaluate("$('#day-dlg').open"), "щелчок по дню — день открыт крупно")
    secs = pg.evaluate("[...document.querySelectorAll('#dd-body .dd-sec > .k')].map(x => x.textContent)")
    ok(secs == ["По времени", "Задачи", "Заметки", "Дневник", "Деньги"], f"разделы по порядку: {secs}")
    times = pg.evaluate("[...document.querySelectorAll('#dd-body .dd-sec:first-child .tm')].map(x => x.textContent)")
    ok(times == ["09:30", "13:00", "21:00"], f"по времени — по порядку часов: {times}")
    full = pg.evaluate(f"[...document.querySelectorAll('#dd-body .t span')].some(s => s.textContent === {json.dumps(LONG, ensure_ascii=False)} && s.scrollWidth <= s.clientWidth + 1)")
    ok(full, "длинная запись — целиком, без обрезки")
    sub = pg.inner_text("#dd-sub")
    ok("сегодня" in sub and "8 записей" in sub and "расход 60" in sub, f"под заголовком — сводка дня: {sub}")
    pg.screenshot(path="/tmp/claude-0/calday.png")
    pg.keyboard.press("ArrowRight"); pg.wait_for_timeout(500)
    nxt = (today + dt.timedelta(days=1)).isoformat()
    ok(pg.evaluate("calSel") == nxt and "завтра" in pg.inner_text("#dd-sub") and pg.is_visible(".dd-empty"), "→ — следующий день; пустой — с подсказкой")
    for _ in range(40):
        pg.keyboard.press("ArrowRight"); pg.wait_for_timeout(30)
    pg.wait_for_timeout(500)
    ok(pg.evaluate("calM") != today.month and pg.evaluate("$('#day-dlg').open"), "через границу месяца — месяц под окном тоже листается")
    pg.keyboard.press("Escape"); pg.wait_for_timeout(300)
    ok(not pg.evaluate("$('#day-dlg').open"), "Esc — назад к месяцу")
    # правый столбец тянется
    pg.evaluate("calY = null; loadCalendar()"); pg.wait_for_timeout(500)
    w0 = pg.evaluate("$('#cal-side').getBoundingClientRect().width")
    g = pg.query_selector("#cal-grip").bounding_box()
    pg.mouse.move(g["x"] + 4, g["y"] + 40); pg.mouse.down(); pg.mouse.move(g["x"] - 150, g["y"] + 40, steps=8); pg.mouse.up(); pg.wait_for_timeout(300)
    w1 = pg.evaluate("$('#cal-side').getBoundingClientRect().width")
    saved = pg.evaluate("calls.filter(c => c[0] === 'settings_save').map(c => c[1].patch.ui && c[1].patch.ui.cal_side_w).pop()")
    ok(w1 > w0 + 100 and saved == round(w1), f"столбец справа шире ({w0:.0f} → {w1:.0f}), ширина запомнена: {saved}")
    pg.mouse.move(g["x"] - 150, g["y"] + 40); pg.mouse.down(); pg.mouse.move(g["x"] - 900, g["y"] + 40, steps=8); pg.mouse.up(); pg.wait_for_timeout(300)
    ok(pg.evaluate("$('#cal-side').getBoundingClientRect().width") <= 561, "но не шире 560 — месяц остаётся читаемым")
    pg.screenshot(path="/tmp/claude-0/calside.png")
    pg.click("#cs-open"); pg.wait_for_timeout(300)
    ok(pg.evaluate("$('#day-dlg').open"), "заголовок дня в столбце тоже открывает день крупно")
    ok(not errs, f"без ошибок на странице: {errs[:2]}")
    b.close()

if fails:
    raise SystemExit(1)
