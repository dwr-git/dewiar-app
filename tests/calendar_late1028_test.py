"""Календарь после ночи с выключенным компьютером (28.10, владелец: «в 8:56 у меня утренняя сводка — не понимаю, где я её
включал, пытался изменить время — не понимаю как… «Зарядить наручные часы» вчера срабатывало на 20:56, а сегодня вижу на
8:56… «Итог дня» — какой может быть итог в 8 утра… Календарь, задачи и заметки — самая главная часть Лиры»).
1. Проснулись (или запустились) — опоздавшие напоминания ждут сверки с телефоном: удалённое там (прозвенело на телефоне)
   здесь уже не звенит; остальное звенит после сверки.
2. Дело по расписанию, опоздавшее больше 2 часов, не выполняется («пропущено — компьютер был выключен»).
3. Календарь: сработавшее — в назначенное время («прозвенело позже — в 08:56»), у готовых дел — короткое имя («Итог дня»).
4. Из календаря: нажать на напоминание или дело — сменить время (у повторяющегося — для всех повторов), текст, выключить,
   «Выполнить сейчас», «Все дела по расписанию»."""
import json, os, re, sys, tempfile, threading, time, types
from datetime import datetime, timedelta
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ.update(DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_CONFIG_DIR=str(tmp / "cfg"), DEWIAR_HOME=str(tmp / "home"))
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import engine_tools as ET  # noqa: E402
import tools as TL  # noqa: E402

# 1. сверка перед опоздавшими
TL.Reminders.LATE_HOLD = 2
fired, woke = [], []
R = TL.Reminders(lambda it: fired.append(it))
R.on_wake = lambda: woke.append(time.time())
past = (datetime.now() - timedelta(hours=12)).replace(microsecond=0).isoformat()
with R._lock:
    R.items = [{"id": "w1", "at": past, "text": "Зарядить наручные часы", "kind": "reminder"},
               {"id": "w2", "at": past, "text": "Полить цветы", "kind": "reminder"}]
time.sleep(1.4)
ok(woke and not fired, f"запустились — сначала сверка с телефоном, опоздавшие ждут (сработало: {len(fired)})")
R.remove("w1")                                   # синхронизация: на телефоне уже прозвенело и удалено
time.sleep(2.5)
ok([x["text"] for x in fired] == ["Полить цветы"] and fired[0]["late"] and fired[0]["late_s"] > 40000 and fired[0]["at"] == past,
   f"после сверки звенит только не прозвеневшее на телефоне, с назначенным временем: {[x['text'] for x in fired]}")
fresh = (datetime.now() + timedelta(seconds=1)).replace(microsecond=0).isoformat()
with R._lock:
    R.items.append({"id": "n1", "at": fresh, "text": "Вовремя", "kind": "reminder"})
time.sleep(2.2)
ok(any(x["text"] == "Вовремя" and not x["late"] for x in fired), "вовремя — звенит сразу, без ожидания")
src = (ROOT / "core/engine.py").read_text(encoding="utf-8")
ok("self.reminders.on_wake = self._reminders_wake" in src and "self.sync.on_pass = self.reminders.release_hold" in src,
   "ядро: проснулись — синхронизация сразу; обмен прошёл — опоздавшие звенят, не дожидаясь конца паузы")
# сверка прошла раньше паузы — звенит сразу; обмен, начатый ДО пробуждения, паузу не снимает; синхронизации нет — не ждём
TL.Reminders.LATE_HOLD = 60
fired2, R2 = [], None
R2 = TL.Reminders(lambda it: fired2.append(it))
R2.on_wake = lambda: None
with R2._lock:
    R2.items = [{"id": "z1", "at": past, "text": "Опоздавшее", "kind": "reminder"}]
time.sleep(1.4)
R2.release_hold(R2.hold_from - 5); time.sleep(1.3)
ok(not fired2, "обмен начался до пробуждения — пауза остаётся")
R2.release_hold(R2.hold_from + 0.5); time.sleep(1.3)
ok([x["text"] for x in fired2] == ["Опоздавшее"], "сверка после пробуждения прошла — звенит сразу, не через минуту")


class _Rm:
    released = 0
    def release_hold(self, since=None): self.released += 1


class _Sy:
    def __init__(self): self.soon = __import__("threading").Event()


wk = getattr(ET, next(n for n in dir(ET) if hasattr(getattr(ET, n), "_reminders_wake")))
for creds, sync_on, want in ((("dw-key", "", ""), True, "sync"), (("", "", ""), True, "release"), (("dw-key", "", ""), False, "release")):
    h = type("H", (), {})(); h.reminders, h.sync, h.wav_input = _Rm(), _Sy(), None
    h.s = type("S", (), {"get": lambda self, a, b=None, _on=sync_on: (None if _on else False) if (a, b) == ("sync", "enabled") else None})()
    h.credentials = lambda c=creds: c
    wk._reminders_wake(h)
    got = "sync" if h.sync.soon.is_set() else "release" if h.reminders.released else "-"
    ok(got == want, f"пробуждение: ключ {'есть' if creds[0] else 'нет'}, синхронизация {'вкл' if sync_on else 'выкл'} → {want} ({got})")


# 2–3. пропущенное дело и журнал
class Eng:
    _on_reminder, _log_reminder, _reminder_log, job_title, calendar_month = (ET.ToolsMixin._on_reminder, ET.ToolsMixin._log_reminder,
                                                                             ET.ToolsMixin._reminder_log, ET.ToolsMixin.job_title,
                                                                             ET.ToolsMixin.calendar_month)
    JOB_LATE_MAX, JOB_TITLES = ET.ToolsMixin.JOB_LATE_MAX, ET.ToolsMixin.JOB_TITLES

    def __init__(self):
        self.ran = []
        self.s = types.SimpleNamespace(get=lambda *a, **k: None)
        self.reminders = types.SimpleNamespace(items=[])
        self.money = types.SimpleNamespace(list=lambda a, b: [], summary=lambda a, b: {})
        self.tasks = types.SimpleNamespace(list=lambda: [])
        self.workspace = types.SimpleNamespace(root=tmp / "ws", memory_get=lambda: "")
        self.calendars = types.SimpleNamespace(events=lambda a, b: [])
    def _run_job(self, item): self.ran.append(item["text"])
    def _default_currency(self): return "BYN"
    def _auto_currency(self): return "BYN"


E = Eng()
EVE = "Итог дня: что сделано из дел на сегодня, что осталось, сколько потрачено за день и что запланировано на завтра — коротко"
y21 = (datetime.now() - timedelta(days=1)).replace(hour=21, minute=0, second=0, microsecond=0)
E._on_reminder({"id": "j1", "kind": "job", "text": EVE, "preset": "evening", "at": y21.isoformat(), "late": True, "late_s": int((datetime.now() - y21).total_seconds())})
time.sleep(0.2)
ok(not E.ran, "вчерашний «Итог дня» утром не выполняется")
m8 = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0) if datetime.now().hour >= 8 else datetime.now() - timedelta(minutes=30)
E._on_reminder({"id": "j2", "kind": "job", "text": "Утренняя сводка", "brief": True, "preset": "brief", "at": m8.isoformat(), "late": True, "late_s": 3300})
time.sleep(0.2)
ok(E.ran == ["Утренняя сводка"], "сводка, опоздавшая меньше чем на 2 часа, — выполняется")
lg = E._reminder_log()
ok(lg[0].get("skipped") and lg[0]["title"] == "Итог дня" and lg[0]["due"].startswith(y21.date().isoformat()), f"журнал: пропущено, с назначенным временем: {lg[0]}")
E.reminders.items = [{"id": "j1", "kind": "job", "text": EVE, "preset": "evening", "at": (y21 + timedelta(days=1)).isoformat(), "repeat": {"kind": "daily", "time": "21:00"}, "deliver": "voice"}]
cal = E.calendar_month(y21.year, y21.month)
yd = cal["days"].get(y21.date().isoformat(), [])
ok(any(x.get("skipped") and x["time"] == "21:00" and x["title"] == "Итог дня" for x in yd), f"календарь: вчера в 21:00 «Итог дня» — пропущено: {yd}")
nxt = (y21 + timedelta(days=1))
if nxt.month == y21.month:
    td = cal["days"].get(nxt.date().isoformat(), [])
    ok(any(x["title"] == "Итог дня" and x["repeat_text"] == "каждый день в 21:00" and x["text"] == EVE for x in td), f"будущее дело — коротким именем и с расписанием: {td[:1]}")

# 4. студия: правка из календаря
from playwright.sync_api import sync_playwright  # noqa: E402
D = datetime.now().date().isoformat()
DAYS = {D: [
    {"type": "reminder", "title": "Итог дня", "text": EVE, "time": "21:00", "id": "j1", "kind": "job", "repeat": True, "repeat_text": "каждый день в 21:00", "deliver": "voice"},
    {"type": "reminder", "title": "Зарядить наручные часы", "time": "20:56", "done": True, "kind": "reminder", "fired": D + "T08:56"},
    {"type": "reminder", "title": "Главные новости", "time": "08:30", "done": True, "kind": "job", "skipped": True},
    {"type": "reminder", "title": "Позвонить Артёму", "time": "23:30", "id": "r2", "kind": "reminder"},
    {"type": "reminder", "title": "Пора выключать компьютер", "text": "Пора выключать компьютер", "time": "17:50", "id": "r3", "kind": "reminder",
     "repeat": True, "repeat_text": "по будням в 17:50", "rdays": [0, 1, 2, 3, 4]}]}
CORE = r"""
(() => { window.calls = []; window.DAYS = %s;
  const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.call = async (c, a) => { calls.push([c, a]);
      if (c === "calendar_month") return { days: DAYS, currency: "BYN" };
      if (c === "reminder_update") return { repeat_text: "каждый день в 22:15", when: "сегодня в 23:45" };
      if (c === "reminder_split") return { kept: {}, new: {} };
      return {}; }; };
  ready(); })();
""" % json.dumps(DAYS, ensure_ascii=False)
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 1400, "height": 900}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route(re.compile(r"^https?://"), lambda r: r.abort())
    pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };"); pg.add_init_script(CORE)
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(900)
    pg.evaluate("() => { S = Object.assign({}, S || {}, { ui: {}, llm: { profiles: {} }, features: {} }); window.ask = () => Promise.resolve(true); }")
    pg.evaluate("() => { $('nav button[data-p=\"calendar\"]').click(); }"); pg.wait_for_timeout(500)
    pg.click(f"#cal-grid .day[data-d='{D}']"); pg.wait_for_timeout(400)
    rows = pg.evaluate("[...document.querySelectorAll('#dd-body .cit')].map(x => [x.querySelector('.t span').textContent, x.querySelector('.t small').textContent])")
    by = dict(rows)
    ok(by.get("Зарядить наручные часы") == "прозвенело позже — в 08:56", f"«прозвенело позже — в 08:56» в своё время: {by.get('Зарядить наручные часы')}")
    ok(by.get("Главные новости") == "пропущено — компьютер был выключен", f"пропущенное дело: {by.get('Главные новости')}")
    ok(by.get("Итог дня") == "дело по расписанию · каждый день в 21:00", f"дело — коротко и с расписанием: {by.get('Итог дня')}")
    pg.locator("#dd-body .cit", has_text="Итог дня").click(); pg.wait_for_timeout(250)
    ed = pg.inner_text("#dd-body .remed")
    ok("Дело по расписанию · каждый день в 21:00 · голосом" in ed and EVE in ed and "Выполнить сейчас" in ed and "Выключить" in ed and "Все дела по расписанию" in ed,
       f"нажали — что это за дело и что с ним сделать: {ed[:120]!r}")
    if os.environ.get("DEWIAR_SHOTS"): pg.screenshot(path=str(Path(os.environ["DEWIAR_SHOTS"]) / "studio-calendar-edit.png"))
    pg.fill("#dd-body #re-time", "22:15"); pg.click("#dd-body #re-save"); pg.wait_for_timeout(300)
    ok(any(c[0] == "reminder_update" and c[1]["id"] == "j1" and c[1]["patch"]["at"].endswith("T22:15:00") for c in pg.evaluate("calls")) and "каждый день в 22:15" in pg.inner_text("#toast"),
       "сменить время — reminder_update, «Теперь каждый день в 22:15»")
    pg.locator("#dd-body .cit", has_text="Итог дня").click(); pg.wait_for_timeout(200)
    pg.click("#dd-body #re-del"); pg.wait_for_timeout(300)
    ok(["reminder_cancel", {"id": "j1"}] in pg.evaluate("calls"), "«Выключить» — дело снято")
    pg.locator("#dd-body .cit", has_text="Позвонить Артёму").locator(".t").click(); pg.wait_for_timeout(200)
    pg.fill("#dd-body #re-text", "Позвонить Артёму Бородину"); pg.fill("#dd-body #re-time", "23:45"); pg.click("#dd-body #re-save"); pg.wait_for_timeout(300)
    ok(any(c[0] == "reminder_update" and c[1]["id"] == "r2" and c[1]["patch"].get("text") == "Позвонить Артёму Бородину" for c in pg.evaluate("calls")), "напоминание: текст и время")
    # 30.10 (владелец: «по будням 17:50, а по пятницам — 16:40, вручную не понятно как»): дни кнопками, «только в этот день»
    wd = ["понедельникам", "вторникам", "средам", "четвергам", "пятницам", "субботам", "воскресеньям"][datetime.fromisoformat(D).weekday()]
    pg.locator("#dd-body .cit", has_text="Пора выключать компьютер").locator(".t").click(); pg.wait_for_timeout(250)
    chips = pg.evaluate("[...document.querySelectorAll('#dd-body .remed-days .rd')].map(b => [b.textContent, b.classList.contains('on')])")
    only = pg.inner_text("#dd-body .remed-only") if pg.locator("#dd-body .remed-only").count() else ""
    if os.environ.get("DEWIAR_SHOTS"): pg.screenshot(path=str(Path(os.environ["DEWIAR_SHOTS"]) / "studio-calendar-days.png"))
    wdi = datetime.fromisoformat(D).weekday()
    ok([c[0] for c in chips] == ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"] and [c[1] for c in chips] == [True] * 5 + [False] * 2
       and (wdi > 4 or f"только по {wd}" in only), f"повтор по дням — кнопки дней (будни включены) и «только по {wd}»: {chips}, {only!r}")
    if wdi <= 4:
        pg.fill("#dd-body #re-time", "16:40"); pg.check("#dd-body #re-only"); pg.click("#dd-body #re-save"); pg.wait_for_timeout(300)
        ok(["reminder_split", {"id": "r3", "day": wdi, "time": "16:40"}] in pg.evaluate("calls"), "«только в этот день» — reminder_split с днём и временем")
    pg.locator("#dd-body .cit", has_text="Пора выключать компьютер").locator(".t").click(); pg.wait_for_timeout(250)
    pg.click("#dd-body .remed-days .rd[data-d='4']"); pg.click("#dd-body #re-save"); pg.wait_for_timeout(300)
    ok(any(c[0] == "reminder_update" and c[1]["id"] == "r3" and c[1]["patch"].get("days") == [0, 1, 2, 3] for c in pg.evaluate("calls")), "сняли «Пт» — дни повтора без пятницы")
    # 30.10 (владелец: «„Удалить все повторы“ — только затемняет экран: окошко удаления появляется под этим окном»)
    pg.locator("#dd-body .cit", has_text="Пора выключать компьютер").locator(".t").click(); pg.wait_for_timeout(250)
    pg.add_script_tag(path=str(ROOT / "ui/assets/dialog.js"))          # настоящий вопрос вместо заглушки выше
    pg.click("#dd-body #re-del"); pg.wait_for_timeout(300)
    top = pg.evaluate("""(() => { const y = document.querySelector('.dwq button.yes'); if (!y) return 'нет окна';
      const r = y.getBoundingClientRect(), el = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2); return el === y ? 'сверху' : (el && (el.id || el.className)) || '?'; })()""")
    if os.environ.get("DEWIAR_SHOTS"): pg.screenshot(path=str(Path(os.environ["DEWIAR_SHOTS"]) / "studio-calendar-ask.png"))
    ok(top == "сверху", f"вопрос «Удалить со всеми повторами?» — поверх окна дня, его можно нажать: {top}")
    pg.click(".dwq button.yes"); pg.wait_for_timeout(400)
    ok(["reminder_cancel", {"id": "r3"}] in pg.evaluate("calls") and pg.locator(".dwq-back").count() == 0 and pg.evaluate("document.querySelector('#day-dlg').open"),
       "«Удалить» — повторы удалены, вопрос закрыт, окно дня осталось")
    pg.locator("#dd-body .cit", has_text="Пора выключать компьютер").locator(".t").click(); pg.wait_for_timeout(250)
    pg.click("#dd-body #re-del"); pg.wait_for_timeout(250); pg.keyboard.press("Escape"); pg.wait_for_timeout(300)
    ok(pg.locator(".dwq-back").count() == 0 and pg.evaluate("document.querySelector('#day-dlg').open"), "Esc — закрывает только вопрос, окно дня остаётся")
    b.close()
ok(not errs, "без ошибок JavaScript" + (f": {errs[:3]}" if errs else ""))

# ядро: новое время повторяющегося — для всех повторов, ближайший в будущем
src = (ROOT / "core/engine_tools.py").read_text(encoding="utf-8")
ok("rep = dict(rep, time=at.strftime(\"%H:%M\"))" in src and "at = next_time(rep, datetime.now())" in src, "ядро: у повтора меняется и время повтора; прошло сегодня — со следующего раза")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
