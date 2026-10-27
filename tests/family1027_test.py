"""Семейный бюджет (27.10, решение владельца по макету «Dewiar — новые режимы»): общий месяц с близкими.
Часть 1 — две семьи (Михаил и Анна), связанные поддельными «Близкими» (сообщения вида fam идут сразу к другому):
- приглашение → у Анны «приглашает вас»; принять → оба «в семье», Анне приходят уже заведённые платежи и лимит;
- трата у Михаила («Деньги» → on_add) — в ленте у обоих, итог месяца по людям; доход и «не делиться» — не уходят;
- удалили трату — пропала и у Анны; платёж: завели, «Оплачено» — у обоих; поздняя правка главнее, старая не затирает;
- лимит — общий; «Напомнить» — обычное сообщение тому, кто платит; чужой (не в семье) — не принимается; ушёл — всё.
Часть 2 — настоящее ядро: fam_* команды, студия → «Семья» (итог, полоса по людям, платежи, лента), без ошибок."""
import asyncio, json, os, socket, subprocess, sys, tempfile, time, types
from datetime import date
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
TESTS = Path(__file__).resolve().parent
PY = os.environ.get("DEWIAR_PY") or sys.executable
sys.path.insert(0, str(ROOT / "core"))
import family as fammod  # noqa: E402
import money as moneymod  # noqa: E402
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


tmp = Path(tempfile.mkdtemp())
TODAY = date.today().isoformat()


class FakeClose:
    def __init__(self, me, pid):
        self.st, self.pid, self.peer, self.sent, self.texts = {"me": {"name": me}}, pid, None, [], []

    def person(self, who):
        if who != self.peer.pid:
            raise fammod.FamilyError("нет такого")
        return {"pid": self.peer.pid, "name": self.peer.st["me"]["name"]}

    def send(self, who, text="", kind="msg", payload=None):
        self.sent.append((who, kind, payload, text))
        if kind == "msg":
            self.texts.append(text)
            return
        # сообщение — сразу у другого: как close._take → family.incoming
        self.peer.host.family.incoming(self.pid, self.st["me"]["name"], dict(payload or {}, t=text))


def host(me, pid, d):
    h = types.SimpleNamespace(events=[], pushes=[])
    h.close = FakeClose(me, pid)
    h.emit = lambda t, **k: h.events.append(t)
    h.push = lambda a, b: h.pushes.append(b)
    feats = {"family": False}
    h.s = types.SimpleNamespace(get=lambda *k: feats.get(k[-1]), update=lambda p: feats.update(p.get("features", {})), snapshot=lambda: {"features": feats}, feats=feats)
    h.money = moneymod.Money(d / "money")
    h.family = fammod.Family(h, d / "family.json")
    h.money.on_add, h.money.on_delete = h.family.share_spend, h.family.delete_spend
    return h


def settle():
    time.sleep(0.3)                                       # траты уходят в фоне


M, A = host("Михаил", "pM", tmp / "m"), host("Анна", "pA", tmp / "a")
M.close.peer, A.close.peer = A.close, M.close
M.close.peer.host, A.close.peer.host = A, M
# до приглашения у Михаила уже есть платёж и лимит — Анне они должны прийти при вступлении
M.family.bill_save({"name": "Свет", "amount": 27.4, "due": TODAY, "payer": "Анна"})
M.family.set_limit(2500)
ok(not M.close.sent, "пока семьи нет — никому ничего не уходит")
M.family.invite("pA")
pa = A.family.public()
ok(pa["members"] and pa["members"][0]["st"] == "asked" and pa["members"][0]["name"] == "Михаил" and A.pushes,
   f"приглашение: у Анны «приглашает вас» и уведомление: {pa['members']}")
ok(A.s.feats["family"] is True and "settings" in A.events, "позвали в семью — раздел «Семья» у Анны включился сам (он по желанию)")
ok(M.close.sent[0][1] == "fam" and "Семья" in json.dumps(M.close.sent, ensure_ascii=False), "приглашение — вид fam с понятным текстом для старых программ")
A.family.accept("pM")
settle()
pm, pa = M.family.public(), A.family.public()
ok(pm["active"] and pa["active"] and pm["members"][0]["st"] == "joined" and pa["members"][0]["st"] == "joined", "приняла — оба «в семье»")
ok(pa["limit"] == 2500 and [b["name"] for b in pa["bills"]] == ["Свет"], f"Анне пришли уже заведённые платёж и лимит: {pa['limit']}, {pa['bills']}")

M.money.add("expense", 46.2, None, "", "продукты", TODAY)
A.money.add("expense", 2, None, "", "проезд", TODAY)
M.money.add("income", 900, None, "", "зарплата", TODAY)
settle()
pm, pa = M.family.public(), A.family.public()
ok(pm["total"] == 48.2 and pa["total"] == 48.2, f"итог месяца одинаковый у обоих (доход не в счёт): {pm['total']} / {pa['total']}")
byA = {v["name"]: v["sum"] for v in pa["by"]}
ok(byA.get("Я") == 2 and byA.get("Михаил") == 46.2 and pa["by"][0]["pid"] == "", f"у Анны по людям: я 2, Михаил 46,2: {pa['by']}")
ok([x["note"] for x in pa["feed"]][:2] == ["проезд", "продукты"] or {x["note"] for x in pa["feed"]} == {"проезд", "продукты"},
   "лента «Сегодня» — у Анны обе траты")
last_exp = next(x for x in reversed(M.money.items) if x["kind"] == "expense")
M.money.delete(last_exp["id"])
settle()
ok(A.family.public()["total"] == 2, f"удалил трату — пропала и у Анны: {A.family.public()['total']}")
M.family.set_share(False)
M.money.add("expense", 300, None, "", "подарок", TODAY)
settle()
ok(A.family.public()["total"] == 2, "«не делиться моими тратами» — Анна не видит")
M.family.set_share(True)

bid = A.family.public()["bills"][0]["id"]
A.family.bill_paid(bid)
pb = M.family.public()["bills"][0]
ok(pb["paid_by"] == "Анна" and pb["paid_at"], f"«Оплачено» у Анны — у Михаила тоже: {pb}")
stale = dict(pb, paid_by="", at=pb["at"] - 10000)
A.family.incoming("pM", "Михаил", {"fam": {"op": "bill", "b": stale}})
ok(A.family.public()["bills"][0]["paid_by"] == "Анна", "старая правка не затирает свежую")
M.family.bill_save({"name": "Газ", "amount": 38, "due": TODAY, "payer": "Анна"})
ok(len(A.family.public()["bills"]) == 2 and A.family.public()["bills"][0]["name"] == "Газ", "новый платёж — у обоих, неоплаченные сверху")
gid = M.family.public()["bills"][0]["id"]
M.family.remind(gid)
ok(M.close.texts and "Газ" in M.close.texts[-1] and M.close.sent[-1][0] == "pA", f"«Напомнить» — сообщение Анне: {M.close.texts[-1:]}")
A.family.set_limit(3000)
ok(M.family.public()["limit"] == 3000, "лимит поменяла Анна — у Михаила тот же")
M.family.bill_delete(gid)
ok(len(A.family.public()["bills"]) == 1, "удалил платёж — у Анны пропал")
A.family.incoming("pX", "Чужой", {"fam": {"op": "spend", "e": {"id": "x1", "amount": 999, "date": TODAY}}})
ok(A.family.public()["total"] == 2, "трата от чужого (не в семье) — не принимается")
try:
    M.family.bill_save({"name": "  "})
    ok(False, "платёж без названия — нельзя")
except fammod.FamilyError:
    ok(True, "платёж без названия — нельзя")
A.family.leave("pM")
ok(not A.family.public()["active"] and not M.family.public()["active"], "Анна ушла — у обоих семьи больше нет")
st = json.loads((tmp / "a" / "family.json").read_text())
ok("ledger" in st and "bills" in st, "состояние — в family.json")

# ---------- часть 2: настоящее ядро и студия ----------
from playwright.sync_api import sync_playwright  # noqa: E402
import websockets  # noqa: E402


def free():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


LLM, PORT = free(), free()
mock = subprocess.Popen([sys.executable, str(TESTS / "mock_llm.py"), str(LLM)])
cfg, stdir = tmp / "cfg", tmp / "st"
cfg.mkdir(); stdir.mkdir()
(cfg / "settings.json").write_text(json.dumps({"persona": "lira", "audio": {"sounds": False, "follow_up_seconds": 0},
                                               "ui": {"news_seen": "99.0.0", "welcome": "done"}, "stt": {"engine": "vosk"},
                                               "tts": {"engine": "off"}, "updates": {"auto_check": False}, "features": {"family": True},
                                               "llm": {"active": "m", "profiles": {"m": {"name": "Мок", "kind": "openai", "base_url": f"http://127.0.0.1:{LLM}/v1", "model": "mock"}}}}))
import settings as setmod  # noqa: E402
ok(setmod.DEFAULTS["features"]["family"] is False if hasattr(setmod, "DEFAULTS") else True, "«Семья» по умолчанию выключена — включается в «Возможностях»")
now = int(time.time() * 1000)
(stdir / "family.json").write_text(json.dumps({
    "members": {"pA": {"name": "Анна", "st": "joined", "at": 1}, "pD": {"name": "Дима", "st": "asked", "at": 1}},
    "ledger": [{"id": "a1", "who": "pA", "name": "Анна", "amount": 690, "cur": "BYN", "note": "продукты", "said": "продукты шестьсот девяносто", "date": TODAY, "ts": now - 60000}],
    "bills": {"b1": {"id": "b1", "name": "Газ", "amount": 38, "due": TODAY, "payer": "Анна", "paid_by": "", "paid_at": 0, "at": 1}},
    "limit": {"v": 2500, "at": 1}, "share": True}, ensure_ascii=False))
env = dict(os.environ, DEWIAR_CONFIG_DIR=str(cfg), DEWIAR_STATE_DIR=str(stdir), DEWIAR_PORT=str(PORT), DEWIAR_ASSUME_AEC="1",
           DEWIAR_WORKSPACE_DIR=str(tmp / "ws"), DEWIAR_FAKE_RAM_GB="16", DEWIAR_FAKE_CORES="8", DEWIAR_DRY_TOOLS=str(tmp / "dry.jsonl"))
core = subprocess.Popen([PY, str(ROOT / "core/main.py"), "--wav", str(TESTS / "silence90.wav"), "--null-audio"], env=env,
                        stdout=open(tmp / "core.log", "w"), stderr=subprocess.STDOUT)
R = {}


async def run():
    ws_ = None
    for _ in range(300):
        await asyncio.sleep(0.2)
        if (cfg / "token").exists():
            try:
                ws_ = await websockets.connect(f"ws://127.0.0.1:{PORT}", max_size=None); break
            except OSError:
                continue
    await ws_.send(json.dumps({"cmd": "hello", "token": (cfg / "token").read_text().strip()}))
    n = [0]; replies = {}

    async def call(cmd, **args):
        n[0] += 1; i = n[0]; await ws_.send(json.dumps({"id": i, "cmd": cmd, "args": args}))
        for _ in range(600):
            if i in replies:
                r = replies.pop(i)
                return r.get("data") if r.get("ok", True) and "error" not in r else {"_err": r.get("error")}
            await asyncio.sleep(0.05)

    async def reader():
        async for raw in ws_:
            e = json.loads(raw)
            if e["type"] == "reply":
                replies[e["id"]] = e
    rd = asyncio.ensure_future(reader())
    await asyncio.sleep(1.5)
    R["get"] = await call("fam_get")
    await call("money_add", kind="expense", amount=820, note="бензин")
    R["after"] = await call("fam_get")
    R["nobill"] = await call("fam_bill", name="")
    R["bill"] = await call("fam_bill", name="Интернет", amount=35, due=TODAY, payer="Анна")
    rd.cancel()
    await ws_.close()


asyncio.run(run())
ok(R["get"] and R["get"]["limit"] == 2500 and R["get"]["total"] == 690 and R["get"]["people"] == [], f"fam_get из ядра: {str(R['get'])[:160]}")
ok(R["after"]["total"] == 1510 and any(v["pid"] == "" and v["sum"] == 820 for v in R["after"]["by"]),
   f"расход из «Деньги» — сразу в общем итоге: {R['after']['total']}")
ok("_err" in (R["nobill"] or {}) and "назовите" in R["nobill"]["_err"], f"платёж без названия — понятная ошибка: {R['nobill']}")
ok(len(R["bill"]["bills"]) == 2, "fam_bill — платёж добавлен")

tok = (cfg / "token").read_text().strip()
errs = []
with sync_playwright() as p:
    b = p.chromium.launch()
    for w in (820, 1400):
        pg = b.new_page(viewport={"width": w, "height": 1000})
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto((ROOT / "ui/settings.html").as_uri() + f"?token={tok}&port={PORT}"); time.sleep(2.5)
        ok(pg.evaluate("document.querySelector('#fam-dot').classList.contains('on')"), f"{w}: точка у «Семьи» — Дима приглашает")
        if w == 1400:
            pg.click('nav button[data-p="home"]'); time.sleep(1)
            ok(pg.locator('.hm-app[data-app="family"]').count() == 1, "на «Главной» — значок «Семья»")
            if os.environ.get("DEWIAR_SHOTS"):
                pg.screenshot(path=os.environ["DEWIAR_SHOTS"] + "/family-home.png")
        ok(pg.is_visible('nav button[data-p="family"]'), f"{w}: «Семья» в меню (включена в «Возможностях»)")
        pg.click('nav button[data-p="family"]'); time.sleep(1.2)
        t = pg.inner_text("#p-family").replace("\u00a0", " ").replace("\u202f", " ")
        ok("1 510" in t and "из 2 500 на месяц" in t and "Анна" in t and "приглашает вас" in t and "Газ" in t and "Напомнить" in t,
           f"{w}: итог, лимит, люди, платежи: {t[:240]!r}")
        ok(pg.locator("#fm-month .fm-bar i").count() == 2 and "голосом: «продукты шестьсот девяносто»" in t, f"{w}: полоса по людям и лента с голосовой фразой")
        sw = pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        ok(sw <= 0, f"{w}: без горизонтальной прокрутки ({sw})")
        if os.environ.get("DEWIAR_SHOTS"):
            pg.screenshot(path=os.environ["DEWIAR_SHOTS"] + f"/family-{w}.png", full_page=True)
        if w == 1400:
            pg.click('#fm-bills [data-paid="b1"]'); time.sleep(1)
            ok("оплатил(а)" in pg.inner_text("#fm-bills"), "«Оплачено» — сразу видно в списке")
            pg.fill("#fm-limit", "1000"); pg.dispatch_event("#fm-limit", "change"); time.sleep(1)
            ok("больше лимита на 510" in pg.inner_text("#fm-month") and pg.evaluate("document.querySelector('.fm-bar').classList.contains('over')"),
               "лимит меньше трат — «больше лимита на …» и красная обводка")
            pg.click('#fm-people [data-acc="pD"]'); time.sleep(1)
            ok("приглашает вас" not in pg.inner_text("#fm-people") and not pg.evaluate("document.querySelector('#fam-dot').classList.contains('on')"),
               "принял приглашение — точка погасла")
            pg.click('nav button[data-p="features"]'); time.sleep(0.5)
            pg.click('#p-features label.tg:has(input[data-k="features.family"])'); time.sleep(1.2)
            ok(not pg.is_visible('nav button[data-p="family"]'), "выключили в «Возможностях» — «Семья» пропала из меню")
        pg.close()
    ok(not errs, f"без ошибок на странице: {errs[:2]}")
    b.close()
core.terminate(); mock.terminate()
print("ИТОГ:", "все проверки пройдены" if not fails else f"не пройдено {len(fails)}")
sys.exit(1 if fails else 0)
