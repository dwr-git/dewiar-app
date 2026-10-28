"""Сделки и «кто нам должен» (0.58; согласовано с владельцем 28.10 — пункты 3 и 4 «Лиры как личной CRM»).
Ядро (deals.py в «Клиентах»): сделка — этапы заявка → предложение → счёт → оплачено / отказ, сумма, «оплатить до»; каждое
движение — в истории клиента; срок оплаты прошёл — должник; заявка или предложение без движения неделю — зависла; доска с
суммами; оплачено — в доходы «Денег» один раз (переключатель). Голосом: client_deal — «Ромашке выставили счёт на 1200 за
коробки, до пятницы» (новая или движение открытой), «Ромашка оплатила»; client_deals — «кто нам должен?», «что зависло?».
Утро с Лирой — должники. Студия: «Клиенты» → «Сделки и кто должен» — итог, доска, этап одной кнопкой; в карточке клиента
— его сделки и «+ Сделка»."""
import os, sys, tempfile, time, types
from datetime import date, timedelta
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


import clients as CL  # noqa: E402
import deals as DL  # noqa: E402
import tools as TL  # noqa: E402
from money import Money  # noqa: E402

C = CL.Clients(tmp / "clients.json")
C.currency = lambda: "BYN"
rom = C.add("Ромашка")["id"]
iv = C.add("Сергей Иванов", "Вектор")["id"]
d1 = C.deal_add(rom, "Коробки 200 шт", "1 200", stage="offer")
ok(d1["stage"] == "offer" and d1["amount"] == 1200 and d1["cur"] == "BYN" and "«Коробки 200 шт»: предложение, 1 200" in C.get(rom)["log"][-1]["t"],
   f"сделка: предложение 1 200 руб., строка в истории клиента: {C.get(rom)['log'][-1]['t']}")
past = (date.today() - timedelta(days=2)).isoformat()
C.deal_set(rom, d1["id"], stage="выставили счёт", due=past)
ds = C.deals()
ok(ds[0]["stage"] == "invoice" and ds[0]["owed"] and ds[0]["overdue"], "выставили счёт со сроком позавчера — должник, срок прошёл")
d2 = C.deal_add(iv, "Сайт", 3000, stage="lead")
with C._lock:
    next(x for x in C.st["clients"][iv]["deals"] if x["id"] == d2["id"])["moved"] = time.time() - 9 * 86400
st = {d["title"]: d for d in C.deals()}
ok(st["Сайт"]["stuck"] and st["Сайт"]["days"] == 9, "заявка без движения 9 дней — зависла")
b = C.deals_board()
ok(b["owed"] == {"BYN": 1200} and b["overdue"] == {"BYN": 1200} and b["stuck"] == 1 and [c["stage"] for c in b["cols"]] == list(DL.STAGES)
   and b["cols"][2]["sum"] == {"BYN": 1200}, f"доска: должны 1 200, просрочено 1 200, зависла одна, сумма колонки «Счёт»: {b['owed']}")
s = C.deals_summary("owed")
ok("Нам должны (итого 1 200" in s and "Ромашка — «Коробки 200 шт»" in s and "срок оплаты прошёл" in s, f"«кто нам должен?»: {s}")
ok("Сайт" in C.deals_summary("stuck") and "Коробки" in C.deals_summary("stuck"), "«что зависло?» — заявка без движения и просроченная оплата")
ok("Нам должны" in C.summary(), "«кто из клиентов ждёт?» — и кто должен")
ok(DL.stage_of("оплатила счёт") == "paid" and DL.stage_of("отправили КП") == "offer" and DL.stage_of("отказался") == "lost" and DL.amount_of("1,2 тыс") == 1200,
   "этапы и суммы словами")

# голосом
M = Money(tmp / "money.json", None, lambda: "BYN")
S = types.SimpleNamespace(get=lambda *k: {"deal_income": True} if k == ("clients",) else None)
ctx = {"clients": C, "money": M, "settings": S}
r = TL.t_client_deal({"who": "Ромашка", "stage": "paid"}, ctx)
ok("«Коробки 200 шт» — оплачено, 1 200" in r and "Записала в доходы" in r, f"«Ромашка оплатила» — движет её открытую сделку, в доходы: {r}")
inc = [x for x in M.items if x["kind"] == "income"]
ok(len(inc) == 1 and inc[0]["amount"] == 1200 and inc[0]["category"] == "Клиенты", f"в «Деньгах» — доход 1 200, «Клиенты»: {inc}")
TL.t_client_deal({"who": "Ромашка", "stage": "paid"}, ctx)
ok(len([x for x in M.items if x["kind"] == "income"]) == 1, "второй раз «оплатила» — дохода не два")
r = TL.t_client_deal({"who": "Ромашке", "title": "плёнка", "amount": 450, "stage": "invoice", "due": "до пятницы"}, ctx)
ok("Новая сделка с Ромашка: «плёнка» — счёт, 450" in r and "оплатить до" in r, f"другое название — новая сделка, не та же: {r}")
r = TL.t_client_deal({"who": "Петров из Альфы", "title": "Ремонт", "amount": 900}, ctx)
ok("Новая сделка" in r and "заявка" in r and any(c["name"] == "Петров" for c in C.st["clients"].values()), "нового клиента — завести вместе со сделкой")
ok("плёнка" in TL.t_client_deals({"what": "owed"}, ctx), "client_deals owed")
ok("client_deal" in TL.TOOLS and "client_deals" in TL.TOOLS and "client_deal" in TL.SAFE_CORE, "у модели — client_deal и client_deals (и в «только безопасное»)")

# утро
import morning as MO  # noqa: E402
C.deal_set(rom, C.deal_find(rom, "плёнка"), due=past)
eng = types.SimpleNamespace(clients=C, s=types.SimpleNamespace(get=lambda k, *a: {"clients": True} if k == "features" else None))
mc = MO._clients(eng, __import__("datetime").datetime.now())
ok(mc and any("плёнка" in x["what"] for x in mc["owed"]) and mc["stuck"] == 1, f"утро: должники и зависшие: {mc}")
ok("Должны, срок оплаты прошёл: Ромашка — «плёнка» — 450" in MO.context({"clients": mc}), "утро для модели — кто должен")

# студия
from playwright.sync_api import sync_playwright  # noqa: E402
board = C.deals_board(); board["income"] = True
card = C.get(rom)
with sync_playwright() as p:
    br = p.chromium.launch(); errs = []
    pg = br.new_page(viewport={"width": 1400, "height": 950}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };")
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(900)
    pg.evaluate("""([board, card, list]) => { window._calls = []; window.ask = () => Promise.resolve(true);
      core.call = (c, a) => { _calls.push([c, a || {}]);
        if (c === 'clients_deals') return Promise.resolve(board);
        if (c === 'clients_list') return Promise.resolve(list);
        if (c === 'client_get' || c === 'client_deal_set' || c === 'client_deal_add') return Promise.resolve(card);
        return Promise.resolve({}); };
      S = Object.assign(S || {}, { features: Object.assign({}, (S || {}).features, { clients: true }) });
      const nb = document.querySelector('nav button[data-p=clients]'); nb.hidden = false; nb.click(); }""",
                [board, card, C.list()])
    pg.wait_for_timeout(500)
    pg.click("#cr-tabs button[data-t=deals]"); pg.wait_for_timeout(500)
    r = pg.evaluate("""() => [document.querySelector('.dl-stat b').textContent, document.querySelector('.dl-stat').className, [...document.querySelectorAll('.dl-col header b')].map(x => x.textContent),
      [...document.querySelectorAll('.dl-col.s-invoice .dl-card b')].map(x => x.textContent), document.querySelector('.cr-main').hidden]""")
    ok("450" in r[0] and "late" in r[1] and r[2] == ["Заявка", "Предложение", "Счёт", "Оплачено · 30 дней"] and r[3] == ["плёнка"] and r[4],
       f"«Сделки»: нам должны (красным — просрочено), четыре колонки, счёт «плёнка»: {r[:4]}")
    if os.environ.get("DEWIAR_SHOTS"): pg.screenshot(path=str(Path(os.environ["DEWIAR_SHOTS"]) / "studio-deals.png"))
    pg.locator(".dl-col.s-invoice .dl-tap").first.click(); pg.wait_for_timeout(200)
    ok(pg.locator(".dl-card.open [data-st=paid]").inner_text() == "Оплачено", "открыли счёт — первым «Оплачено»")
    pg.click(".dl-card.open [data-st=paid]"); pg.wait_for_timeout(300)
    ok(any(c[0] == "client_deal_set" and c[1]["stage"] == "paid" for c in pg.evaluate("_calls")) and "в доходы" in pg.inner_text("#toast"), "«Оплачено» — этап и «записала в доходы»")
    pg.click("#dl-new"); pg.wait_for_timeout(300)
    pg.fill("#dl-t", "Этикетки"); pg.fill("#dl-a", "300"); pg.select_option("#dl-s", "offer"); pg.click("#dl-add button[type=submit]"); pg.wait_for_timeout(300)
    ok(any(c[0] == "client_deal_add" and c[1]["title"] == "Этикетки" and c[1]["stage"] == "offer" for c in pg.evaluate("_calls")), "«+ Сделка» на доске")
    pg.click("#cr-tabs button[data-t=list]"); pg.wait_for_timeout(500)
    pg.evaluate(f"() => {{ CR.cur = '{rom}'; crOpen('{rom}'); }}"); pg.wait_for_timeout(400)
    r = pg.evaluate("() => [...document.querySelectorAll('.cr-deals li b')].map(x => x.textContent)")
    ok("плёнка" in r and "Коробки 200 шт" in r, f"в карточке клиента — его сделки: {r}")
    pg.select_option(".cr-deals select[data-did]", "lost"); pg.wait_for_timeout(300)
    ok(any(c[0] == "client_deal_set" and c[1]["stage"] == "lost" for c in pg.evaluate("_calls")), "этап — прямо в карточке")
    br.close()
ok(not errs, "без ошибок JavaScript" + (f": {errs[:3]}" if errs else ""))
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
