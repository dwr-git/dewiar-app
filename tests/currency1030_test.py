"""Валюта «Денег» (30.10, №422, пользователь из Украины: «в ПК всё настроено по региону, перезагружал — валюта не
меняется; на Android сразу подхватило; и нет возможности самому выбрать валюту»). На Windows догадка искала часовой пояс
как на Linux и всегда давала рубли; гривен в словаре не было. Теперь: регион системы (Windows — «Регион», Linux — язык
и пояс), гривна, тенге, лари и другие — в словах и подписях; «Календарь» → «Деньги» → «Валюта» — выбрать самому;
прежние записи в ошибочной валюте — поменять разом (суммы те же)."""
import json, os, re, sys, tempfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
import money  # noqa: E402
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


ok([money._country_of_locale(x) for x in ("uk_UA.UTF-8", "ru-BY", "Ukrainian_Ukraine.1251", "ru_RU.UTF-8", "C")] == ["UA", "BY", "UA", "RU", ""],
   "страна из языка и формата системы: uk_UA, ru-BY, Ukrainian_Ukraine")
for reg, cur in (("UA", "UAH"), ("BY", "BYN"), ("KZ", "KZT"), ("DE", "EUR"), ("", "RUB")):
    os.environ["DEWIAR_REGION"] = reg
    ok(money.region_currency("RUB") == cur, f"регион «{reg or 'не узнали'}» → {cur}")
os.environ.pop("DEWIAR_REGION")
P = lambda t, d="RUB": (money.parse(t, d) or {})
ok(P("купил хлеб за 30 гривен")["currency"] == "UAH" and P("купил хлеб за 30 гривен")["note"] == "хлеб", "«30 гривен» — гривны, «хлеб» без хвоста")
ok(P("получил зарплату 20000 гривень")["currency"] == "UAH" and P("заплатил 40 грн за такси")["currency"] == "UAH", "«гривень», «грн» — тоже")
ok(P("потратил 200 тенге на такси")["currency"] == "KZT" and P("заплатил 50 лари за ужин")["currency"] == "GEL", "тенге, лари")
ok(P("купил кофе за 8 рублей", "UAH")["currency"] == "UAH", "просто «рубли» — валюта по умолчанию (как было)")
ok(P("купил кофе за 5 евро")["currency"] == "EUR", "евро — как было")
ok(money.fmt(1200, "UAH") == "1 200 ₴" and money.fmt(5, "KZT") == "5 ₸", f"подписи: {money.fmt(1200, 'UAH')}, {money.fmt(5, 'KZT')}")

tmp = Path(tempfile.mkdtemp())
m = money.Money(tmp / "money.json", None, lambda: "RUB")
for a in (10, 20, 30):
    m.add("expense", a, None, "Продукты", "хлеб")
m.add("expense", 5, "USD", "Кафе и рестораны", "кофе")
ok(m.relabel("RUB", "UAH") == 3 and {x["currency"] for x in m.items} == {"UAH", "USD"}
   and json.loads((tmp / "money.json").read_text())["items"][0]["currency"] == "UAH", "ошибочная валюта — поменять разом, доллары не тронуты, сохранено")
ok(m.relabel("RUB", "UAH") == 0 and m.relabel("UAH", "UAH") == 0, "нечего менять — 0")

# студия: «Календарь» → «Деньги» → «Валюта»
from playwright.sync_api import sync_playwright  # noqa: E402
ITEMS = [{"id": f"m{i}", "date": "2026-10-30", "kind": "expense", "amount": 10 * i, "currency": "RUB", "category": "Продукты", "note": "хлеб"} for i in (1, 2)]
CORE = """(() => { window.calls = []; const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.call = async (c, a) => { calls.push([c, a]);
      if (c === "calendar_month") return { year: 2026, month: 10, days: {}, money: { by_currency: [], count: 0, days: {} }, currency: "RUB", currency_auto: "RUB", currency_set: "" };
      if (c === "money_list") return ITEMS;
      if (c === "money_summary") return { by_currency: [{ currency: "RUB", income: 0, expense: 30, balance: -30, expense_cats: [] }], count: 2, days: {} };
      if (c === "money_relabel") return { changed: 2 };
      if (c === "settings_save") return Object.assign({}, window.S || {}, a.patch);
      return null; };
    setTimeout(() => core.emit("hello", {}), 200); };
  ready(); })();""".replace("ITEMS", json.dumps(ITEMS, ensure_ascii=False))
SHOT = os.environ.get("DEWIAR_SHOTS")
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 1300, "height": 900}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route(re.compile(r"^https?://"), lambda r: r.abort())
    pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };"); pg.add_init_script(CORE)
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(1500)
    pg.evaluate("document.querySelector('nav button[data-p=\"calendar\"]').click()"); pg.wait_for_timeout(300)
    pg.click('#cal-tabs button[data-ct="money"]'); pg.wait_for_timeout(500)
    ok(pg.is_visible("#mo-cur") and "Как в системе — Российский рубль" in pg.inner_text("#mo-cur") and "Гривна" in pg.inner_text("#mo-cur"),
       "в «Деньгах» — выбор валюты: «Как в системе — …» и список")
    if SHOT:
        pg.screenshot(path=str(Path(SHOT) / "money-currency.png"))
    pg.select_option("#mo-cur", "UAH"); pg.wait_for_timeout(500)
    calls = pg.evaluate("calls")
    ok(["settings_save", {"patch": {"money": {"currency": "UAH"}}}] in calls, "выбрали гривну — сохранено в настройках")
    q = pg.inner_text(".dwq") if pg.locator(".dwq").count() else ""
    ok("рублях (2)" in q and "гривнах" in q, f"прежние записи в рублях — вопрос, не поменять ли: {q[:120]!r}")
    pg.click(".dwq button.yes"); pg.wait_for_timeout(400)
    ok(["money_relabel", {"from": "RUB", "to": "UAH"}] in pg.evaluate("calls"), "«Поменять» — валюта у записей исправлена")
    b.close()
ok(not errs, f"без ошибок на странице: {errs[:3]}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
