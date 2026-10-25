"""«Платежи» (0.45, владелец 25.10: «каждый месяц делаю оплаты коммунальных и вношу, за что и сколько заплатил… чтобы точно
быть уверенным, что всё оплачено своевременно»; «гибко и универсально»; «сколько за год — красивые графики»; «изображение
прикрепить из буфера или перетаскиванием»). Ядро (core/payments.py): счета, оплаты, расход из показаний, статусы и сроки,
напоминание один раз, перенос из органайзера, отчёты словами, .md в папке ассистента. Голосом без модели. Студия: «Месяц»,
«Год», «Аналитика», панель счёта, запись оплаты, вложение, перенос; значок на «Главной» (и у тех, кто её уже настраивал)."""
import asyncio, base64, datetime as dt, json, os, socket, subprocess, sys, tempfile, time
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
TESTS = ROOT / "tests"
sys.path.insert(0, str(ROOT / "core"))
SHOTS = os.environ.get("DEWIAR_SHOTS")
FAILS = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        FAILS.append(m)


import payments as P  # noqa: E402


class WS:
    def __init__(self, root):
        self.root = Path(root)

    def ensure(self):
        self.root.mkdir(parents=True, exist_ok=True)
        return self.root


tmp = Path(tempfile.mkdtemp())
pm = P.Payments(tmp / "p.json", WS(tmp / "ws"))
gas = pm.bill_save({"name": "Газ", "day": 25})
ok(gas["kind"] == "meter" and gas["unit"] == "м³" and gas["group"] == "Коммунальные" and gas["icon"] == "🔥", f"новый «Газ» — сам: счётчик, м³, коммунальные, значок: {gas}")
net = pm.bill_save({"name": "Интернет", "day": 23, "autopay": True, "amount": 75})
ok(net["kind"] == "fixed" and net["group"] == "Связь", "«Интернет» — постоянная сумма, связь")
try:
    pm.bill_save({"name": "газ"}); ok(False, "второй «газ» — отказ")
except ValueError:
    ok(True, "второй «газ» — отказ")
p1 = pm.pay_save({"bill": "Газ", "date": "2026-01-25", "reading": 27214, "amount": 101.87})
p2 = pm.pay_save({"bill": "за газ", "date": "2026-02-28", "reading": 27707, "amount": 104.76})
ok(p2["used"] == 493 and p2["period"] == "2026-02", f"расход сам из прошлого показания: {p2['used']}")
today = dt.date(2026, 3, 24)
ok(pm.status(pm.bill(gas["id"]), "2026-03", today)["s"] == "soon" and pm.status(pm.bill(gas["id"]), "2026-02", today)["s"] == "paid"
   and pm.status(pm.bill(gas["id"]), "2026-03", dt.date(2026, 3, 26))["s"] == "overdue", "статусы: оплачено, скоро срок, просрочено")
d1 = pm.check_due(dt.date(2026, 3, 24), now_hour=11)
d2 = pm.check_due(dt.date(2026, 3, 24), now_hour=12)
ok(len(d1) == 1 and "Завтра срок оплаты: Газ" in d1[0][1] and "показания" in d1[0][1] and not d2, f"накануне срока — напоминание один раз, автооплату не напоминаем: {d1}")
pm.pay_save({"bill": "Газ", "date": "2026-03-24", "reading": 27923, "amount": 46.84})
ok(not pm.check_due(dt.date(2026, 3, 25), now_hour=9), "оплачено — в день срока не напоминаем")
g = pm.year_grid(2026, today)
row = next(r for r in g["rows"] if r["bill"]["name"] == "Газ")
ok([c["s"] for c in row["cells"][:3]] == ["paid", "paid", "paid"] and row["cells"][4]["s"] == "future", "таблица года: оплачено по месяцам, впереди — пусто")
st = pm.stats(2026)
ok(abs(st["total"] - 253.47) < 0.01 and st["by_group"][0]["name"] == "Коммунальные" and st["meters"][0]["points"][1]["rate"], f"аналитика: итог, группы, цена куба: {st['total']}")
md = (tmp / "ws/Платежи/Газ.md").read_text(encoding="utf-8")
ok("| 28.02.26 | 27 707 | 493 м³ | 104,76 |" in md, "«Платежи/Газ.md» — история таблицей для поиска и Obsidian")
att = pm.attach("bill", gas["id"], "памятка.png", b"\x89PNG\r\n\x1a\n")
ok(att["img"] and (tmp / "ws" / att["path"]).exists() and pm.bill(gas["id"])["att"][0]["id"] == att["id"], "вложение к счёту — файл в «Платежи/Вложения/Газ/»")
rep = pm.text_report("газ", today)
ok("Последние оплаты" in rep and "показание 27 923" in rep, f"«как платить за газ» — словами: {rep[:120]}")

T = """КРЕДИТ счёт 1111
25.01.26 - 38 рублей автооплата (не погашено).
~~~~~~~~~~~~~~~
ВОДА: показания с 20 по 7
25.01.26 (801 потреблено, 791.19 начислено = 43.19 р.)
28.02.26 (825 потреблено, 816.11 начислено = 50.20 р.)
~~~~~~~~~~~~~~~
За Электричество:
- Номер абонента 000
25.01.26 - 15034 ==   539  киловат ==   152.97 р.
"""
items = P.parse_import(T)
names = [x["name"] for x in items]
el = next(x for x in items if x["name"] == "Электричество")
ok(names == ["Кредит", "Вода", "Электричество"] and items[0]["pays"][0]["status"] == "unpaid" and el["pays"][0]["used"] == 539 and el["pays"][0]["amount"] == 152.97
   and "Номер абонента" in el["how"], f"перенос: разделы, «не погашено», расход, сумма, реквизиты: {names}")
r = P.import_apply(pm, items)
r2 = P.import_apply(pm, items)
ok(r["bills"] == 3 and r["pays"] == 4 and r2["pays"] == 0, f"перенос — без повторов при втором нажатии: {r} {r2}")
for t, want in [("оплатил газ 47,84 показания 28135", ("pay", 47.84, 28135)), ("Лира, оплатил свет 203 рубля 48 копеек", ("pay", 203.48, None)),
                ("что у меня не оплачено?", ("open",)), ("как платить за электричество", ("how",)), ("оплатил кофе 5", None),
                # примеры из справки «?» раздела (25.10): так говорят чаще всего
                ("Что я ещё не оплатил в этом месяце?", ("open",)), ("Сколько за год ушло на газ?", ("sum",))]:
    c = P.parse_voice(t, pm)
    got = c and ((c["op"], c.get("amount"), c.get("reading")) if c["op"] == "pay" else (c["op"],))
    ok(got == want, f"голосом: «{t}» → {got}")


def free():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


LLM, PORT = free(), free()
mock = subprocess.Popen([sys.executable, str(TESTS / "mock_llm.py"), str(LLM)])
cfg = tmp / "cfg"; cfg.mkdir()
(cfg / "settings.json").write_text(json.dumps({"persona": "lira", "audio": {"sounds": False}, "ui": {"news_seen": "99.0.0", "welcome": "done", "home_apps": ["chat", "notes"]},
    "stt": {"engine": "vosk"}, "tts": {"engine": "off"}, "updates": {"auto_check": False},
    "llm": {"active": "m", "profiles": {"m": {"name": "Мок", "kind": "openai", "base_url": f"http://127.0.0.1:{LLM}/v1", "model": "mock"}}}}))
env = dict(os.environ, DEWIAR_CONFIG_DIR=str(cfg), DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_PORT=str(PORT), DEWIAR_ASSUME_AEC="1",
           DEWIAR_WORKSPACE_DIR=str(tmp / "ws2"))
core = subprocess.Popen([sys.executable, str(ROOT / "core/main.py"), "--wav", str(TESTS / "silence90.wav"), "--null-audio"], env=env,
                        stdout=open(tmp / "core.log", "w"), stderr=subprocess.STDOUT)
for _ in range(150):
    time.sleep(0.2)
    if (cfg / "token").exists():
        break
time.sleep(2); tok = (cfg / "token").read_text().strip()
R = {}


async def go():
    import websockets
    async with websockets.connect(f"ws://127.0.0.1:{PORT}", max_size=None) as ws:
        await ws.send(json.dumps({"cmd": "hello", "token": tok}))
        n = [0]

        async def call(cmd, **a):
            n[0] += 1; i = n[0]
            await ws.send(json.dumps({"id": i, "cmd": cmd, "args": a}))
            end = time.time() + 15
            while time.time() < end:
                try:
                    e = json.loads(await asyncio.wait_for(ws.recv(), 1))
                except asyncio.TimeoutError:
                    continue
                if e.get("type") == "reply" and e.get("id") == i:
                    return e.get("data") if e.get("ok", True) else {"error": e.get("error")}
            return None

        async def say(text):
            n[0] += 1; ev = []
            await ws.send(json.dumps({"id": n[0], "cmd": "say", "args": {"text": text}}))
            end = time.time() + 20
            while time.time() < end:
                try:
                    e = json.loads(await asyncio.wait_for(ws.recv(), 1))
                except asyncio.TimeoutError:
                    continue
                ev.append(e)
                if e.get("type") == "answer" and e.get("done"):
                    break
            await asyncio.sleep(0.4)
            return next((e.get("text") or "" for e in reversed(ev) if e.get("type") == "answer" and e.get("done")), "")

        y = dt.date.today().year
        g = await call("pay_bill_save", bill={"name": "Газ", "day": 25, "how": "ЕРИП → Газоснабжение → номер абонента 000"})
        await call("pay_bill_save", bill={"name": "Электричество", "day": 25})
        await call("pay_bill_save", bill={"name": "Интернет", "day": 23, "autopay": True, "amount": 75})
        await call("pay_bill_save", bill={"name": "Кредит", "kind": "loan", "day": 25, "total": 1200, "amount": 100})
        for m, (r_, a_, e_, ea) in enumerate([(27214, 101.87, 15034, 152.97), (27707, 104.76, 15613, 164.32), (27923, 46.84, 16063, 127.71),
                                              (28135, 47.84, 16745, 207.12), (28196, 14, 17262, 157), (28229, 7, 17962, 213)], start=1):
            if dt.date(y, m, 25) > dt.date.today():
                break
            await call("pay_save", pay={"bill": "Газ", "date": f"{y}-{m:02d}-25", "reading": r_, "amount": a_})
            await call("pay_save", pay={"bill": "Электричество", "date": f"{y}-{m:02d}-25", "reading": e_, "amount": ea})
            await call("pay_save", pay={"bill": "Интернет", "date": f"{y}-{m:02d}-23", "amount": 55 if m < 6 else 75, "note": "автооплата"})
            await call("pay_save", pay={"bill": "Кредит", "date": f"{y}-{m:02d}-25", "amount": 100})
        await call("pay_save", pay={"bill": "Газ", "date": f"{y - 1}-11-25", "amount": 120})
        R["voice"] = await say("Лира, оплатил газ 8,65 показания 28325")
        R["open"] = await say("что у меня не оплачено?")
        R["how"] = await say("как платить за газ")
        R["ov"] = await call("pay_overview")
        R["att"] = await call("pay_attach", target="bill", id=g["id"], name="памятка.png", data="data:image/png;base64," + base64.b64encode(
            bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c6360f8cfc0000003010100c9fe92ef0000000049454e44ae426082")).decode())
try:
    asyncio.run(go())
    gas = next(b for b in R["ov"]["bills"] if b["name"] == "Газ")
    ok(R["voice"].startswith("Записал") and "Записал" in R["voice"] and "8,65" in R["voice"] and gas["last"]["reading"] == 28325, f"голосом без модели: «{R['voice']}»")
    ok("оплачен" in R["open"].lower() or "срок" in R["open"].lower(), f"«что не оплачено?» — по счетам: «{R['open'][:120]}»")
    ok("ЕРИП" in R["how"], f"«как платить за газ» — реквизиты: «{R['how'][:100]}»")
    ok(R["att"] and R["att"].get("img"), "вложение из окна (Ctrl+V / перетаскивание) — сохранено")
    tok_url = (ROOT / "ui/settings.html").as_uri() + f"?token={tok}&port={PORT}"
    errs = []
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1400, "height": 1000})
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(tok_url); time.sleep(3)
        apps = pg.evaluate("[...document.querySelectorAll('#hm-apps .hm-app')].map(x => x.dataset.app)")
        ok("pay" in apps and apps[:2] == ["chat", "notes"], f"у настроившего «Главную» — новый значок «Платежи» появился сам, в конце: {apps}")
        pg.click('nav button[data-p="pay"]'); time.sleep(1.2)
        cards = pg.evaluate("[...document.querySelectorAll('#py-body .py-card')].map(c => c.querySelector('.py-top b').textContent)")
        ok(cards[:4] == ["Газ", "Электричество", "Интернет", "Кредит"], f"«Этот месяц» — карточки по порядку: {cards}")
        if SHOTS:
            pg.screenshot(path=os.path.join(SHOTS, "pay-month.png"))
        pg.click('#py-body .py-card[data-b] >> nth=0'); time.sleep(0.8)
        ok(pg.is_visible("#py-drawer.on") and "Записать оплату" in pg.inner_text("#py-drawer"), "карточка — панель с историей")
        # владелец 25.10: «справа обрезается надпись» — в своей рамке окна (frame=1) заголовок панели прятался под полосой окна
        top = pg.evaluate("(() => { document.documentElement.classList.add('framed'); const t = document.querySelector('#py-drawer').getBoundingClientRect().top; document.documentElement.classList.remove('framed'); return t; })()")
        ok(top >= 38, f"в своей рамке окна панель платежа — под полосой заголовка: top={top}")
        ok(pg.evaluate("[...document.querySelectorAll('.py-foot > *')].every(x => getComputedStyle(x).whiteSpace === 'nowrap')"), "сумма за год и «Записать оплату» не ломаются по словам")
        # владелец 25.10: «в полях какие-то зигзаги» — стрелка списка повторялась на всё поле в светлой теме
        pg.click('#py-drawer .py-dtabs button[data-k="set"]'); time.sleep(0.6)
        rep = pg.evaluate("(() => { document.documentElement.classList.add('st-light'); const r = [...document.querySelectorAll('#py-drawer select')].map(x => getComputedStyle(x).backgroundRepeat); document.documentElement.classList.remove('st-light'); return r; })()")
        ok(rep and all(r == "no-repeat" for r in rep), f"списки в настройках платежа — одна стрелка, без «зигзагов»: {rep}")
        pg.click('#py-drawer .py-dtabs button[data-k="hist"]'); time.sleep(0.4)
        pg.click('#py-drawer .py-dtabs button[data-k="how"]'); time.sleep(0.8)
        ok("ЕРИП" in pg.input_value("#py-how") and pg.locator("#py-drawer .py-atts figure").count() == 1, "«Как платить»: реквизиты и картинка-памятка")
        if SHOTS:
            pg.screenshot(path=os.path.join(SHOTS, "pay-drawer.png"))
        pg.click("#py-dx"); time.sleep(0.4)
        pg.click('#py-tabs button[data-t="year"]'); time.sleep(1)
        ok(pg.locator("#py-body .py-grid tbody tr").count() == 4 and pg.locator("#py-body .py-cell.s-ok").count() >= 4, "«Год» — таблица счета × месяцы")
        if SHOTS:
            pg.screenshot(path=os.path.join(SHOTS, "pay-year.png"))
        pg.click('#py-tabs button[data-t="stats"]'); time.sleep(1)
        ok(pg.locator("#py-body .py-hero").count() == 1 and pg.locator("#py-body .py-donut circle").count() >= 2 and pg.locator("#py-body .py-mini").count() >= 2,
           "«Аналитика» — итог, кольцо, по месяцам, счётчики")
        if SHOTS:
            pg.screenshot(path=os.path.join(SHOTS, "pay-stats.png"))
            pg.evaluate("document.querySelector('#p-pay .py-an').lastElementChild.scrollIntoView()"); time.sleep(0.3)
            pg.screenshot(path=os.path.join(SHOTS, "pay-stats2.png"))
        pg.evaluate("document.documentElement.classList.add('st-light')"); time.sleep(0.3)
        if SHOTS:
            pg.screenshot(path=os.path.join(SHOTS, "pay-stats-light.png"), full_page=True)
        pg.evaluate("document.documentElement.classList.remove('st-light')")
        pg.click('#py-tabs button[data-t="month"]'); time.sleep(0.6)
        pg.click("#py-add"); time.sleep(0.3)
        pg.fill("#pb-name", "Страховка машины"); time.sleep(0.1)
        ok(pg.evaluate("document.querySelector('input[name=pb-kind]:checked').value") == "yearly", "«страховка» — сама «раз в год»")
        pg.click("#pb-ok"); time.sleep(1)
        ok(pg.is_visible("#py-drawer.on") and "Страховка машины" in pg.inner_text("#py-drawer"), "новый платёж — сразу открыт")
        pg.click("#py-drawer #py-dpay"); time.sleep(0.4)
        pg.fill("#pp-amount", "310"); pg.click("#pp-ok"); time.sleep(1)
        ok("310" in pg.inner_text("#py-drawer"), "оплата записана из окна")
        pg.click("#py-dx"); time.sleep(0.3)
        pg.click("#py-imp"); time.sleep(0.3)
        pg.fill("#pi-text", T); pg.click("#pi-go"); time.sleep(0.8)
        ok(pg.locator("#pi-prev .pi-it").count() == 3, "перенос: предпросмотр трёх разделов")
        if SHOTS:
            pg.screenshot(path=os.path.join(SHOTS, "pay-import.png"))
        b.close()
    ok(not errs, f"без ошибок на странице: {errs[:3]}")
finally:
    core.terminate(); mock.terminate()
print("\nИТОГ:", "все проверки прошли" if not FAILS else f"не прошло {len(FAILS)}")
sys.exit(1 if FAILS else 0)
