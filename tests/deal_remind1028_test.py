"""«Напомни клиенту об оплате» и выгрузка сделок (0.62; план «Идей Лиры»: «Лира сама напишет вежливое напоминание,
выгрузка сделок в таблицу»). Ядро: вежливое письмо по счёту (срок прошёл — «был», нет — «до»), отметка «напомнили» в
сделке и истории клиента, CSV для Excel. Голосом: deal_remind — почта подключена и адрес есть — письмо уходит; нет —
текст, чтобы отправить самому. Студия: «Напомнить об оплате» у счёта — черновик правится, «Отправить письмом» /
«Скопировать»; «Выгрузить в таблицу»."""
import csv, io, os, sys, tempfile, types
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
import tools as TL  # noqa: E402

C = CL.Clients(tmp / "clients.json")
C.currency = lambda: "BYN"
rom = C.add("Ромашка", email="buh@romashka.by")["id"]
iv = C.add("Сергей Иванов")["id"]
past = (date.today() - timedelta(days=3)).isoformat()
d1 = C.deal_add(rom, "Коробки 200 шт", "1 200", stage="invoice", due=past)
d2 = C.deal_add(iv, "Сайт; лендинг", 3000, stage="invoice")
d3 = C.deal_add(iv, "Логотип", 500, stage="lead")
r = C.deal_remind_text(rom, d1["id"], "Михаил")
ok(r["to"] == "buh@romashka.by" and r["subject"] == "Напоминание об оплате: Коробки 200 шт" and "1 200" in r["body"] and "Срок оплаты был" in r["body"]
   and r["body"].rstrip().endswith("Михаил") and r["overdue"], f"письмо: кому, тема, сумма, «срок был», подпись: {r['body'][:120]}")
r2 = C.deal_remind_text(iv, d2["id"])
ok(r2["body"].startswith("Здравствуйте, Сергей!") and "Срок" not in r2["body"] and r2["to"] == "", "без срока и почты — тоже вежливо, кому — пусто")
try:
    C.deal_remind_text(iv, d3["id"]); ok(False, "по заявке напоминать нельзя")
except Exception as e:  # noqa: BLE001
    ok("«Счёт»" in str(e), "по заявке (не счёт) — понятная ошибка")
C.deal_reminded(rom, d1["id"])
ok(any("Напомнили об оплате письмом: «Коробки 200 шт»" in x["t"] for x in C.get(rom)["log"]) and next(d for d in C.deals() if d["id"] == d1["id"]).get("reminded"),
   "отметка: в истории клиента и в сделке")
rows = list(csv.reader(io.StringIO(C.deals_csv().lstrip("﻿")), delimiter=";"))
ok(rows[0][:5] == ["Клиент", "Сделка", "Сумма", "Валюта", "Этап"] and len(rows) == 4 and ["Сергей Иванов", "Сайт; лендинг", "3000", "BYN", "Счёт"] == rows[2][:5]
   and rows[1][6] == "да", f"CSV для Excel: заголовки, «;» внутри — в кавычках, просрочено: {rows[1][:7]}")


class Mail:
    def __init__(self): self.sent = []
    def configured(self): return True
    def send(self, to, subject, body, *a, **k): self.sent.append((to, subject, body)); return {"to": [to], "subject": subject, "attachments": []}


m = Mail()
ctx = {"clients": C, "mail": m, "settings": types.SimpleNamespace(get=lambda k, *a: {"name": "Михаил"} if k == "close" else None)}
res = TL.t_deal_remind({"who": "Ромашке"}, ctx)
ok(m.sent and m.sent[0][0] == "buh@romashka.by" and "отправлено Ромашка" in res, f"голосом: «напомни Ромашке об оплате» — письмо ушло: {res}")
res = TL.t_deal_remind({"who": "Иванову"}, ctx)
ok("не записана почта" in res and "Здравствуйте, Сергей!" in res and len(m.sent) == 1, "нет почты клиента — текст, чтобы отправить самому")
ok(TL.TOOLS["deal_remind"][2] == "confirm" and "deal_remind" in TL.NET_TOOLS, "письмо от вашего имени — только после «Отправить?»")

# студия
from playwright.sync_api import sync_playwright  # noqa: E402
board = C.deals_board(); board["income"] = True
with sync_playwright() as p:
    br = p.chromium.launch(); errs = []
    pg = br.new_page(viewport={"width": 1400, "height": 950}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };")
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(900)
    pg.evaluate("""([board, rem, list]) => { window._calls = [];
      core.call = (c, a) => { _calls.push([c, a || {}]);
        if (c === 'clients_deals') return Promise.resolve(board);
        if (c === 'clients_list') return Promise.resolve(list);
        if (c === 'client_deal_remind') return Promise.resolve(Object.assign({}, rem, { mail: true }));
        if (c === 'clients_deals_export') return Promise.resolve({ path: 'Клиенты/Сделки 2026-10-28.csv', n: 3 });
        return Promise.resolve({}); };
      S = Object.assign(S || {}, { features: Object.assign({}, (S || {}).features, { clients: true }) });
      const nb = document.querySelector('nav button[data-p=clients]'); nb.hidden = false; nb.click(); }""", [board, r, C.list()])
    pg.wait_for_timeout(500)
    pg.click("#cr-tabs button[data-t=deals]"); pg.wait_for_timeout(500)
    pg.locator(".dl-col.s-invoice .dl-card.late .dl-tap").first.click(); pg.wait_for_timeout(200)
    ok(pg.locator(".dl-card.open [data-rem]").count() == 1, "у счёта — «Напомнить об оплате»")
    pg.click(".dl-card.open [data-rem]"); pg.wait_for_timeout(300)
    ok(pg.input_value("#dl-rto") == "buh@romashka.by" and "Напоминаю об оплате" in pg.input_value("#dl-rbody"), "черновик письма — над доской, правится")
    if os.environ.get("DEWIAR_SHOTS"): pg.screenshot(path=str(Path(os.environ["DEWIAR_SHOTS"]) / "deal-remind.png"))
    pg.fill("#dl-rbody", "Добрый день! Ждём оплату по счёту, спасибо."); pg.click("#dl-rsend"); pg.wait_for_timeout(300)
    c = [x for x in pg.evaluate("_calls") if x[0] == "client_deal_remind_send"]
    ok(c and c[-1][1]["to"] == "buh@romashka.by" and c[-1][1]["body"].startswith("Добрый день!"), "«Отправить письмом» — с правками")
    pg.click("#dl-csv"); pg.wait_for_timeout(300)
    ok(any(x[0] == "clients_deals_export" for x in pg.evaluate("_calls")) and any(x[0] == "ws_open" for x in pg.evaluate("_calls")), "«Выгрузить в таблицу» — файл и открыть")
    br.close()
ok(not errs, "без ошибок JavaScript" + (f": {errs[:3]}" if errs else ""))
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
