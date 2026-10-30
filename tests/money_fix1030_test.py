"""Удалить или исправить трату голосом (идея №75, 30.10: «ассистент может только добавлять траты — убрать ошибочную запись
или дубль, запись с неверной валютой голосом нельзя; найти по дате, сумме, категории и заметке, показать найденное и
удалить только после подтверждения»). money_find — найти (id), money_fix — удалить или поправить; подтверждение —
вопросом системы с найденными записями, а не на слово модели."""
import os, shutil, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
import money  # noqa: E402
import tools as T  # noqa: E402
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


m = money.Money(Path(tempfile.mkdtemp()) / "money.json", None, lambda: "RUB")
k1 = m.add("expense", 8, None, "Кафе и рестораны", "кофе", "2026-10-29")
k2 = m.add("expense", 8, None, "Кафе и рестораны", "кофе", "2026-10-29")
tx = m.add("expense", 450, None, "Транспорт", "такси", "2026-10-30")
m.add("income", 2000, None, "Зарплата", "аванс", "2026-10-30")

f = m.find("2026-10-29", "2026-10-29", None, "кофе")
ok([x["id"] for x in f] and {x["id"] for x in f} == {k1["id"], k2["id"]}, "«вчерашний кофе» — обе записи (дубль)")
ok([x["id"] for x in m.find(None, None, 450)] == [tx["id"]] and m.find(None, None, None, "такси", kind="income") == [], "по сумме; доход и расход не путаются")
ok(m.find(None, None, None, "кофей") and m.find(None, None, None, "такси", "USD") == [], "слово в другой форме находится; валюта — фильтр")

S = type("S", (), {"get": lambda self, *k: None})()
tb = T.Toolbox(S, None)
tb.hooks["money"] = m
ok(tb.policy("money_find") == (True, False) and tb.policy("money_fix") == (True, True), "найти — сразу, удалить или поправить — только после «да»")
r = tb.run("money_find", {"date": "2026-10-29", "text": "кофе"})
ok(k1["id"] in r and k2["id"] in r and "уточни" in r, f"нашла две — модель уточнит, какую: {r[:120]!r}")
q = tb.describe("money_fix", {"ids": [k2["id"]], "action": "delete"})
ok(q.startswith("Удалить запись: 29.10 −8 ₽ кофе"), f"вопрос человеку — с самой записью: {q!r}")
r = tb.run("money_fix", {"ids": [k2["id"]], "action": "delete"})
ok("Удалено записей: 1" in r and all(x["id"] != k2["id"] for x in m.list()), "дубль удалён, вторая запись цела")
q = tb.describe("money_fix", {"ids": [tx["id"]], "action": "update", "currency": "uah"})
ok("валюта → UAH" in q and "такси" in q, f"исправить валюту — вопрос показывает что и где: {q!r}")
tb.run("money_fix", {"ids": [tx["id"]], "action": "update", "currency": "uah"})
ok(next(x for x in m.list() if x["id"] == tx["id"])["currency"] == "UAH", "валюта у записи — гривны, сумма та же")
try:
    tb.run("money_fix", {"ids": ["нет-такой"], "action": "delete"}); bad = False
except T.ToolError:
    bad = True
ok(bad, "чужой или выдуманный id — ошибка, ничего не удалено")
ok("money_find" in T.SAFE_CORE and "money_fix" in T.SAFE_CORE, "и в режиме «Только безопасное» — это свои записи, наружу ничего")

# телефон: те же money_find / money_fix (там подтверждение — вторым вызовом с confirmed после «да»)
from playwright.sync_api import sync_playwright  # noqa: E402
www = Path(tempfile.mkdtemp()) / "www"
shutil.copytree(ROOT / "android/assets/www", www)
shutil.copy(ROOT / "ui/assets/entities.js", www / "entities.js")
for f in ("skins.css", "skins.js"):
    shutil.copy(ROOT / "ui/assets" / f, www / f)
shutil.copytree(ROOT / "ui/assets/live", www / "live", dirs_exist_ok=True)
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                capture_output=True, text=True, check=True).stdout, encoding="utf-8")
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 393, "height": 820}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route("https://**", lambda r: r.abort())
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(900)
    r = pg.evaluate("""async () => { await runTool('money_add', { kind: 'expense', amount: 8, category: 'Кафе', note: 'кофе' });
        await runTool('money_add', { kind: 'expense', amount: 8, category: 'Кафе', note: 'кофе' });
        const f = await runTool('money_find', { text: 'кофе' }); const ids = [...f.matchAll(/^(m\\d+):/gm)].map(x => x[1]);
        const ask = await runTool('money_fix', { ids: [ids[0]], action: 'delete' }); const n1 = money().length;
        const done = await runTool('money_fix', { ids: [ids[0]], action: 'delete', confirmed: true });
        return [f, ids.length, ask, n1, done, money().length]; }""")
    ok(r[1] >= 1 and "Спроси пользователя: «Удалить" in r[2] and r[3] == 2 and "Удалено записей: 1" in r[4] and r[5] == 1,
       f"телефон: нашла, спросила, удалила только после «да»: {r[1]}, {r[2][:60]!r}, {r[3]}→{r[5]}")
    b.close()
ok(not errs, f"телефон без ошибок: {errs[:3]}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
