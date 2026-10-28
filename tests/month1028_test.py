"""«Мой месяц с Лирой» (0.61; план «Лира — любимица всех»: «итоги месяца: что сделали, сколько дел и напоминаний, траты по
категориям, лучшие моменты»). month.py считает месяц из «Дел», журнала напоминаний, «Денег», заметок и дневника; голосом —
инструмент month_summary («как прошёл мой месяц?»); студия — карточка на «Главной» первые 7 дней месяца: лента дней,
крупные числа, куда ушли деньги, «Рассказать голосом», «Скрыть» до следующего месяца."""
import datetime as dt, json, os, socket, subprocess, sys, tempfile, time
from pathlib import Path
from types import SimpleNamespace
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
TESTS = Path(__file__).resolve().parent
PY = os.environ.get("DEWIAR_PY") or sys.executable
SHOTS = os.environ.get("DEWIAR_SHOTS")
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import month as M  # noqa: E402
from done import Done  # noqa: E402
from money import Money  # noqa: E402
ok(M.prev_ym(dt.date(2026, 1, 5)) == "2025-12" and M.bounds("2026-12") == (dt.date(2026, 12, 1), dt.date(2027, 1, 1)), "границы месяца и прошлый месяц (через Новый год)")
tmp = Path(tempfile.mkdtemp())
ms = lambda d, h=12: int(dt.datetime(2026, 10, d, h).timestamp() * 1000)   # noqa: E731
done = [{"id": f"d{i}", "title": t, "at": ms(d)} for i, (t, d) in enumerate([("сдал отчёт", 3), ("позвонил в банк", 4), ("починил кран", 5), ("купил подарок маме", 5),
                                                                           ("записался к врачу", 20), ("старое", 1)])]
done.append({"id": "x", "title": "сентябрьское", "at": int(dt.datetime(2026, 9, 30, 12).timestamp() * 1000)})
(tmp / "done.json").write_text(json.dumps(done), encoding="utf-8")
money = Money(tmp / "money.json", None, lambda: "BYN")
for amt, cat in ((120, "продукты"), (80, "продукты"), (60, "транспорт"), (300, "дом")):
    money.add("expense", amt, "BYN", cat, date="2026-10-10")
money.add("income", 1500, "BYN", "зарплата", date="2026-10-05")
money.add("expense", 999, "BYN", "продукты", date="2026-11-02")
log = [{"at": "2026-10-07T09:00:00", "kind": "reminder"}, {"at": "2026-10-08T09:00:00", "kind": "reminder"}, {"at": "2026-10-09T09:00:00", "kind": "job"},
       {"at": "2026-10-09T10:00:00", "kind": "reminder", "skipped": True}, {"at": "2026-11-01T09:00:00", "kind": "reminder"}]
ws = tmp / "ws"; (ws / "Дневник").mkdir(parents=True); (ws / "Заметки").mkdir()
for d in ("2026-10-02", "2026-10-15", "2026-11-01"):
    (ws / "Дневник" / f"{d}.md").write_text("…", encoding="utf-8")
n = ws / "Заметки" / "идея.md"; n.write_text("…", encoding="utf-8"); t = dt.datetime(2026, 10, 12).timestamp(); os.utime(n, (t, t))
eng = SimpleNamespace(done=Done(tmp / "done.json"), money=money, _reminder_log=lambda: log, workspace=SimpleNamespace(ensure=lambda: ws),
                      watches=SimpleNamespace(data={"items": []}), care=SimpleNamespace(items=[]))
d = M.gather(eng, "2026-10")
ok(d["title"] == "октябрь" and d["done"]["n"] == 6 and d["done"]["streak"] == 3 and d["done"]["best_day"] == "2026-10-05" and d["done"]["best_n"] == 2,
   f"дела: 6 за октябрь (сентябрьское не в счёт), серия 3 дня, лучший день 5-го: {d['done']}")
ok(len(d["done"]["by_day"]) == 31 and d["done"]["by_day"][4] == 2 and sum(d["done"]["by_day"]) == 6, "лента: 31 день, по дням")
ok(d["rem"]["n"] == 2, f"напоминания: только прозвеневшие (без дел по расписанию и пропущенных): {d['rem']}")
ok(d["money"]["expense"] == 560 and d["money"]["income"] == 1500 and d["money"]["cats"][0] == {"name": "дом", "sum": 300.0}, f"деньги: траты октября по категориям: {d['money']}")
ok(d["notes"]["n"] == 1 and d["diary"]["days"] == 2 and not d["empty"], "заметки и дни дневника — за этот месяц")
c = M.context(d)
ok("Мой месяц с Лирой — октябрь 2026" in c and "Сделано дел: 6" in c and "«починил кран»" in c and "дом 300" in c, "строки для модели")
e = M.gather(SimpleNamespace(done=Done(tmp / "none.json"), money=Money(tmp / "m2.json", None), _reminder_log=lambda: [], workspace=None, watches=None, care=None), "2026-10")
ok(e["empty"] and "почти нет" in M.context(e), "пустой месяц — честно: записей нет")
import tools  # noqa: E402
ok("month_summary" in tools.TOOLS, "инструмент month_summary есть")
r = tools.TOOLS["month_summary"][3]({"month": "2026-10"}, {"engine": eng})
ok("Сделано дел: 6" in r and "тепло" in r, "инструмент: «итоги октября» — данные и как рассказать")
try:
    tools.TOOLS["month_summary"][3]({"month": "октябрь"}, {"engine": eng}); ok(False, "неверный месяц — ошибка")
except tools.ToolError:
    ok(True, "неверный месяц — понятная ошибка")


# студия на живом ядре
def free():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


LLM, PORT = free(), free()
mock = subprocess.Popen([sys.executable, str(TESTS / "mock_llm.py"), str(LLM)])
cfg = tmp / "cfg"; cfg.mkdir()
(cfg / "settings.json").write_text(json.dumps({"persona": "lira", "audio": {"sounds": False}, "ui": {"news_seen": "99.0.0", "welcome": "done", "memory_motion": "off"},
                                               "stt": {"engine": "vosk"}, "tts": {"engine": "off"},
                                               "llm": {"active": "m", "profiles": {"m": {"name": "Мок", "kind": "openai", "base_url": f"http://127.0.0.1:{LLM}/v1", "model": "mock"}}}}))
today = dt.date.today(); pm = M.prev_ym(today); y, m_ = map(int, pm.split("-"))
(cfg / "done.json").write_text(json.dumps([{"id": f"p{i}", "title": t, "at": int(dt.datetime(y, m_, dd, 12).timestamp() * 1000)}
                                           for i, (t, dd) in enumerate([("сдал отчёт", 3), ("позвонил в банк", 4), ("починил кран", 5), ("купил подарок маме", 5), ("записался к врачу", 20)])]), encoding="utf-8")
st = tmp / "st"; st.mkdir()
(st / "reminders-log.json").write_text(json.dumps([{"at": f"{pm}-07T09:00:00", "kind": "reminder"}] * 3), encoding="utf-8")
env = dict(os.environ, DEWIAR_CONFIG_DIR=str(cfg), DEWIAR_STATE_DIR=str(st), DEWIAR_PORT=str(PORT), DEWIAR_ASSUME_AEC="1",
           DEWIAR_WORKSPACE_DIR=str(tmp / "ws2"), DEWIAR_FAKE_RAM_GB="16", DEWIAR_FAKE_CORES="8")
core = subprocess.Popen([PY, str(ROOT / "core/main.py"), "--wav", str(TESTS / "silence90.wav"), "--null-audio"], env=env,
                        stdout=open(tmp / "core.log", "w"), stderr=subprocess.STDOUT)
for _ in range(150):
    time.sleep(0.2)
    if (cfg / "token").exists():
        break
time.sleep(2)
tok = (cfg / "token").read_text().strip()
errs = []
try:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1400, "height": 1000})
        pg.on("pageerror", lambda e: errs.append("pageerror: " + str(e)))
        pg.goto((ROOT / "ui/settings.html").as_uri() + f"?token={tok}&port={PORT}"); time.sleep(3)
        for k, v in (("expense", 120), ("expense", 300), ("income", 900)):
            pg.evaluate(f"core.call('money_add', {{ kind: '{k}', amount: {v}, category: '{'дом' if v == 300 else 'продукты'}', date: '{pm}-10' }})")
        time.sleep(0.5)
        if today.day > 7:
            ok(pg.evaluate("document.getElementById('hm-month').hidden"), "после 7-го числа карточки месяца на главной нет")
        pg.evaluate("moLoad(true)"); time.sleep(1)
        ok(pg.is_visible("#hm-month") and pg.inner_text("#hm-month h2").startswith("Ваш ") and "с Лирой" in pg.inner_text("#hm-month h2"), f"карточка «Ваш … с Лирой»: {pg.inner_text('#hm-month h2')!r}")
        sts = pg.evaluate("[...document.querySelectorAll('#hm-month .mo-st')].map(e => e.innerText.replace(/\\s+/g, ' '))")
        ok(any(s.startswith("5 дел сделано") for s in sts) and any(s.startswith("3 напоминания") for s in sts) and any(s.startswith("420 ") for s in sts), f"числа: дела, напоминания, траты: {sts}")
        ok(pg.evaluate("document.querySelectorAll('#hm-month .mo-rib i').length") == (M.bounds(pm)[1] - M.bounds(pm)[0]).days
           and pg.evaluate("document.querySelectorAll('#hm-month .mo-rib .lv4').length") == 1, "лента дней: квадрат на каждый день, самый густой — лучший день")
        ok("починил кран" in pg.inner_text("#hm-month .mo-top") and "дом" in pg.inner_text("#hm-month .mo-cats"), "«Чем можно гордиться» и «Куда ушли деньги»")
        if SHOTS:
            pg.locator("#hm-month").screenshot(path=f"{SHOTS}/month-card.png")
            pg.evaluate("studioSkin('graphite')"); time.sleep(0.3); pg.locator("#hm-month").screenshot(path=f"{SHOTS}/month-card-dark.png")
        pg.set_viewport_size({"width": 760, "height": 1000}); time.sleep(0.3)
        ok(pg.evaluate("document.documentElement.scrollWidth <= 760"), "узкое окно — без горизонтальной прокрутки")
        pg.click("#hm-month #mo-hide"); time.sleep(0.6)
        ok(pg.evaluate("document.getElementById('hm-month').hidden"), "«×» — скрыта")
        ok(json.loads((cfg / "settings.json").read_text())["ui"].get("month_hide") == pm, "скрыта до следующего месяца (ui.month_hide)")
        r = pg.evaluate("core.call('month_get', {})")
        ok(r["hidden"] and r["ym"] == pm, "month_get знает, что скрыта")
        b.close()
finally:
    core.terminate(); mock.terminate()
# телефон: тот же инструмент month_summary
w = tmp / "www"
subprocess.run(["bash", str(ROOT / "android/tools/www_assemble.sh"), str(w)], check=True, capture_output=True)
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 393, "height": 852}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto((w / "index.html").as_uri()); pg.wait_for_timeout(900)
    r = pg.evaluate("""() => { const t = (d, h) => new Date(2026, 9, d, h || 12).getTime();
      saveDone([{ id: 'a', title: 'сдал отчёт', at: t(3) }, { id: 'b', title: 'починил кран', at: t(4) }, { id: 'c', title: 'купил подарок', at: t(4, 15) }, { id: 'd', title: 'сентябрь', at: new Date(2026, 8, 30).getTime() }]);
      fileSave('money.json', JSON.stringify([{ kind: 'expense', amount: 300, currency: 'BYN', category: 'дом', date: '2026-10-10' }, { kind: 'expense', amount: 50, currency: 'BYN', category: 'кафе', date: '2026-10-11' }, { kind: 'expense', amount: 999, currency: 'BYN', category: 'дом', date: '2026-11-01' }]));
      return [monthSummary('2026-10'), monthSummary('2026-08'), monthSummary('октябрь'), JSON.stringify(toolSpecs()).includes('month_summary')]; }""")
    ok("октябрь 2026" in r[0] and "Сделано дел: 3" in r[0] and "серия — 2" in r[0] and "«починил кран»" in r[0] and "расходы 350" in r[0] and "дом 300" in r[0], f"телефон: итоги октября: {r[0][:160]}")
    ok("почти нет" in r[1] and r[2].startswith("Ошибка") and r[3], "телефон: пустой месяц — честно; неверный месяц — ошибка; инструмент есть у модели")
    b.close()
ok(not errs, f"без ошибок: {errs[:2]}")
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
