"""Идея №41 (30.10): «Дела и напоминания разделить на две вкладки: дела отдельно, напоминания отдельно. Дела и напоминания
отображаются в календаре. Выполненные дела имеют статус „выполнено“ и, возможно, зачёркнуты. Отметку о выполнении можно
ставить голосом или руками в списке. В календаре — галочка „Отображать выполненные“».
Студия → «Дела и напоминания»: вкладки «Все · Дела · Напоминания» (выбор запоминается). «Дела» — разовые напоминания с
кружком «сделано» и сделанное сегодня, зачёркнутое; «Напоминания» — повторы, будильники, таймеры, дела по расписанию.
Календарь: сделанные дела (done.py) — в своём дне, зачёркнуты, «выполнено в 12:00»; закрытое напоминание — его же строка;
«Показывать выполненные» — галочка, выбор запоминается."""
import json, os, re, sys, tempfile, types
from datetime import datetime, timedelta
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
SHOTS = os.environ.get("DEWIAR_SHOTS")
tmp = Path(tempfile.mkdtemp())
os.environ.update(DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_CONFIG_DIR=str(tmp / "cfg"), DEWIAR_HOME=str(tmp / "home"))
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


# ---- ядро: календарь со сделанным ----
import done as DN  # noqa: E402
import engine_tools as ET  # noqa: E402

noon = datetime.now().replace(hour=12, minute=0, second=0, microsecond=0)
ms = lambda t: int(t.timestamp() * 1000)


class Eng:
    calendar_month, _reminder_log, job_title = ET.ToolsMixin.calendar_month, ET.ToolsMixin._reminder_log, ET.ToolsMixin.job_title
    JOB_TITLES = ET.ToolsMixin.JOB_TITLES

    def __init__(self):
        self.s = types.SimpleNamespace(get=lambda *a, **k: None)
        self.reminders = types.SimpleNamespace(items=[{"id": "r-open", "at": (noon + timedelta(days=1)).isoformat(), "text": "Купить подарок", "kind": "reminder"}])
        self.money = types.SimpleNamespace(list=lambda a, b: [], summary=lambda a, b: {})
        self.tasks = types.SimpleNamespace(list=lambda: [])
        self.workspace = types.SimpleNamespace(root=tmp / "ws", memory_get=lambda: "")
        self.calendars = types.SimpleNamespace(events=lambda a, b: [])
        self.done = DN.Done(tmp / "st/done.json")

    def _default_currency(self): return "BYN"
    def _auto_currency(self): return "BYN"


E = Eng()
ET.STATE_DIR.mkdir(parents=True, exist_ok=True)
(ET.STATE_DIR / "reminders-log.json").write_text(json.dumps([
    {"at": (noon - timedelta(hours=2)).isoformat(timespec="seconds"), "text": "Позвонить маме", "kind": "reminder", "id": "r-mom"},
    {"at": (noon - timedelta(hours=1)).isoformat(timespec="seconds"), "text": "Полить цветы", "kind": "reminder", "id": "r-flow"}]), encoding="utf-8")
E.done.add([{"title": "Позвонить маме", "rid": "r-mom"}], "voice", at=ms(noon - timedelta(minutes=90)))
E.done.add(["Отправил отчёт"], "pc", at=ms(noon))
cal = E.calendar_month(noon.year, noon.month)
day = cal["days"].get(noon.date().isoformat(), [])
mom = [x for x in day if x["title"] == "Позвонить маме"]
ok(len(mom) == 1 and mom[0].get("closed") and mom[0]["closed_at"] == (noon - timedelta(minutes=90)).strftime("%H:%M"),
   f"закрытое «сделано» напоминание — одной строкой, «выполнено в …»: {mom}")
rep = [x for x in day if x["title"] == "Отправил отчёт"]
ok(len(rep) == 1 and rep[0]["closed"] and rep[0]["done"] and rep[0]["kind"] == "done" and rep[0]["time"] == "12:00",
   f"сделанное без напоминания — в своём дне, выполнено: {rep}")
flow = [x for x in day if x["title"] == "Полить цветы"]
ok(len(flow) == 1 and flow[0]["done"] and not flow[0].get("closed"), "прозвеневшее, но не отмеченное — не «выполнено»")
tom = cal["days"].get((noon + timedelta(days=1)).date().isoformat(), []) if (noon + timedelta(days=1)).month == noon.month else []
ok((noon + timedelta(days=1)).month != noon.month or any(x["title"] == "Купить подарок" and not x.get("done") for x in tom), "открытое дело — в своём дне")

# ---- студия ----
from playwright.sync_api import sync_playwright  # noqa: E402

today_ms = ms(noon)
FAKE = """(() => { window.calls = [];
  const NOW = %d, tomorrow = new Date(NOW + 864e5).toISOString().slice(0, 10) + "T08:00:00", tm = (h) => tomorrow.replace("08:", h + ":");
  let rems = [
    { id: "r1", at: tm("10"), at_hm: "10:00", text: "Позвонить маме", when: "завтра в 10:00", kind: "reminder", repeat: null, repeat_text: "" },
    { id: "r2", at: tm("09"), at_hm: "09:00", text: "Отправить отчёт", when: "завтра в 09:00", kind: "reminder", repeat: null, repeat_text: "" },
    { id: "r3", at: tomorrow, at_hm: "08:00", text: "Выпить таблетки", when: "завтра в 08:00", kind: "reminder", repeat: { kind: "daily" }, repeat_text: "каждый день" },
    { id: "r4", at: tomorrow, at_hm: "07:00", text: "Подъём", when: "завтра в 07:00", kind: "alarm", repeat: null, repeat_text: "" } ];
  let done = [{ id: "d1", title: "Полить цветы", at: NOW, src: "voice" }];
  const pub = () => ({ items: done, today: done.length, streak: 1, best_streak: 2, best_day: 3, total: 5, achievements: [],
    week: Array.from({ length: 7 }, (_, i) => ({ day: new Date(NOW - (6 - i) * 864e5).toISOString().slice(0, 10), n: i === 6 ? done.length : 1 })) });
  const day = new Date(NOW).toISOString().slice(0, 10);
  const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.call = async (c, a) => { calls.push([c, a]);
      if (c === "reminders") return rems;
      if (c === "done") return pub();
      if (c === "done_reminder") { const x = rems.find(r => r.id === a.id); rems = rems.filter(r => r.id !== a.id); done = done.concat([{ id: "d" + a.id, title: x.text, at: NOW + 60000, src: "pc", rid: a.id }]);
        return Object.assign(pub(), { added: [x.text], fresh: [], mile: 0 }); }
      if (c === "done_undo") { done = done.filter(d => d.id !== a.id); return pub(); }
      if (c === "reminder_parse") return /купить хлеб/.test(a.phrase) && !/20:00/.test(a.phrase) ? null : { text: "Купить хлеб", when: "сегодня в 20:00", repeat_text: "" };
      if (c === "reminder_add") { rems = rems.concat([{ id: "r9", at: tomorrow, at_hm: "20:00", text: "Купить хлеб", when: "сегодня в 20:00", kind: "reminder", repeat: null, repeat_text: "" }]); return rems[rems.length - 1]; }
      if (c === "calendar_month") return { year: +day.slice(0, 4), month: +day.slice(5, 7), currency: "BYN", money: {}, days: { [day]: [
        { type: "reminder", kind: "done", time: "09:30", title: "Отправил отчёт", done: true, closed: true, closed_at: "09:30" },
        { type: "reminder", kind: "reminder", time: "10:00", title: "Позвонить маме", done: true, closed: true, closed_at: "10:20" },
        { type: "reminder", id: "r1", kind: "reminder", time: "18:00", title: "Купить подарок", done: false } ] } };
      return {}; }; };
  ready(); })();""" % today_ms
errs = []
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1300, "height": 1000})
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route(re.compile(r"^https?://"), lambda r: r.abort()); pg.add_init_script(FAKE)
    url = (ROOT / "ui/settings.html").as_uri() + "?port=1"

    def go(sec):                  # как в calendar_late1028: настройки ядра — без связи с ним
        pg.evaluate("() => { S = Object.assign({}, S || {}, { ui: {}, llm: { profiles: {} }, features: {}, reminders: {} }); const w = document.querySelector('#wlc'); if (w) w.remove(); }")
        pg.evaluate("(s) => document.querySelector(`nav button[data-p=\"${s}\"]`).click()", sec)
    pg.goto(url); pg.wait_for_timeout(1200)
    go("reminders")
    pg.wait_for_timeout(800)
    tabs = pg.locator("#rt-tabs [data-rt]")
    ok(tabs.count() == 3 and re.sub(r"\d", "", pg.inner_text("#rt-tabs")).split() == ["Все", "Дела", "Напоминания"]
       and pg.get_attribute('#rt-tabs [data-rt="all"]', "aria-selected") == "true",
       f"вкладки «Все · Дела · Напоминания», сначала — «Все»: {pg.inner_text('#rt-tabs')!r}")
    ok(pg.inner_text("#rt-n-do") == "2" and pg.inner_text("#rt-n-rem") == "2", "на вкладках — сколько дел и напоминаний")
    pg.click('#rt-tabs [data-rt="do"]'); pg.wait_for_timeout(300)
    vis = lambda sel: pg.evaluate(f"() => {{ const e = document.querySelector('{sel}'); return !!e && !!e.offsetParent; }}")
    ok(vis("#td-list") and not vis("#r-list") and not vis("#j-pre") and vis("#d-head"), "«Дела»: список дел и сводка, без напоминаний и готовых дел")
    rows = pg.locator("#td-list .ritem.td")
    texts = [rows.nth(i).locator(".rtext").inner_text() for i in range(rows.count())]
    ok(texts == ["Отправить отчёт", "Позвонить маме", "Полить цветы"], f"открытые дела по времени, ниже — сделанное сегодня: {texts}")
    done_row = pg.locator("#td-list .ritem.td.ok")
    ok(done_row.count() == 1 and "line-through" in done_row.locator(".rtext").evaluate("e => getComputedStyle(e).textDecorationLine")
       and "выполнено в" in done_row.inner_text() and done_row.locator('.tchk[aria-checked="true"]').count() == 1,
       "сделанное — зачёркнуто, «выполнено в …», кружок с галочкой")
    ok("Выпить таблетки" not in pg.inner_text("#td-list") and "Подъём" not in pg.inner_text("#td-list"), "повторы и будильники — не в «Делах»")
    pg.fill("#td-phrase", "купить хлеб"); pg.wait_for_timeout(500)
    ok("20:00" in pg.inner_text("#td-parse"), f"дело без времени — на вечер: {pg.inner_text('#td-parse')!r}")
    if SHOTS:
        box = pg.locator("#p-reminders").bounding_box()
        pg.screenshot(path=os.path.join(SHOTS, "todo-tabs.png"), clip={"x": box["x"], "y": box["y"], "width": box["width"], "height": min(820, box["height"])})
    pg.click("#td-add"); pg.wait_for_timeout(400)
    ok(["reminder_add", {"phrase": "в 20:00 купить хлеб"}] in pg.evaluate("calls"), "«Добавить дело» без времени — «в 20:00 …»")
    pg.locator("#td-list .ritem.td", has_text="Позвонить маме").locator(".tchk").click(); pg.wait_for_timeout(900)
    ok(["done_reminder", {"id": "r1"}] in pg.evaluate("calls"), "кружок — «сделано» (done_reminder)")
    ok(pg.locator("#td-list .ritem.td.ok", has_text="Позвонить маме").count() == 1, "отмеченное — зачёркнуто внизу, в сделанном")
    pg.locator("#td-list .ritem.td.ok", has_text="Полить цветы").locator(".tchk").click(); pg.wait_for_timeout(500)
    ok(["done_undo", {"id": "d1"}] in pg.evaluate("calls") and pg.locator("#td-list", has_text="Полить цветы").count() == 0, "кружок с галочкой — снять отметку")

    pg.click('#rt-tabs [data-rt="rem"]'); pg.wait_for_timeout(300)
    rl = pg.inner_text("#r-list")
    ok(vis("#r-list") and vis("#j-pre") and not vis("#td-list") and not vis("#d-head"), "«Напоминания»: список, готовые дела, будильник — без дел")
    ok("Выпить таблетки" in rl and "Подъём" in rl and "Отправить отчёт" not in rl, f"в «Напоминаниях» — повторы и будильник, разовых дел нет")
    pg.click('#rt-tabs [data-rt="all"]'); pg.wait_for_timeout(300)
    ok("Отправить отчёт" in pg.inner_text("#r-list") and "Выпить таблетки" in pg.inner_text("#r-list") and vis("#d-list"), "«Все» — как было: всё разом")
    pg.click('#rt-tabs [data-rt="do"]'); pg.wait_for_timeout(200)
    pg.reload(); pg.wait_for_timeout(1200)
    go("reminders")
    pg.wait_for_timeout(600)
    ok(pg.get_attribute('#rt-tabs [data-rt="do"]', "aria-selected") == "true" and vis("#td-list"), "выбор вкладки запомнился")

    # календарь
    pg.evaluate("() => document.querySelector('nav button[data-p=\"calendar\"]').click()"); pg.wait_for_timeout(900)
    ok(pg.is_checked("#cal-done"), "в календаре — «Показывать выполненные», включено")
    cl = pg.locator("#cal-grid .ev.closed")
    ok(cl.count() == 2 and "line-through" in cl.first.locator("span").evaluate("e => getComputedStyle(e).textDecorationLine"), "выполненные дела в календаре зачёркнуты")
    side = pg.inner_text("#cal-side")
    ok("выполнено в 09:30" in side and "Купить подарок" in side, f"сбоку — «выполнено в …» и открытое дело: {side[:200]!r}")
    if SHOTS:
        pg.screenshot(path=os.path.join(SHOTS, "todo-calendar.png"))
    pg.uncheck("#cal-done"); pg.wait_for_timeout(300)
    ok(pg.locator("#cal-grid .ev.closed").count() == 0 and pg.locator("#cal-grid .ev", has_text="Купить подарок").count() == 1, "сняли галочку — выполненных нет, открытые остались")
    pg.reload(); pg.wait_for_timeout(1200)
    go("calendar")
    pg.wait_for_timeout(900)
    ok(not pg.is_checked("#cal-done") and pg.locator("#cal-grid .ev.closed").count() == 0, "выбор «Показывать выполненные» запомнился")
    ok(not errs, f"без ошибок: {errs}")
    b.close()
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
