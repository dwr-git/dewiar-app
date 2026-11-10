"""№596 (ПК 0.84.2, 06.11): «„Календарь“ → „Деньги“: при выборе „Доход“ пусть в списке будут только доходы, при „Расходе“ —
расходы». На снимке: выбран «Доход», а подсказка категорий — «Продукты, Кафе и рестораны, Транспорт…». Теперь категории
подсказки зависят от вида записи (как в core/money.py), чужая категория при смене вида стирается."""
import os, re, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import money  # noqa: E402
errs = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1300, "height": 860}); pg.on("pageerror", lambda x: errs.append(str(x)))
    pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };")
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(1000)
    opts = lambda: pg.evaluate("() => [...document.querySelectorAll('#mo-cats-list option')].map(o => o.value)")
    pg.evaluate("() => { document.querySelectorAll('section.cur').forEach(x => x.classList.remove('cur')); const s = document.querySelector('#mo-kind').closest('section'); s.classList.add('cur');"
                " document.querySelectorAll('#ct-month, #ct-feed').forEach(x => x.style.display = 'none'); document.querySelector('#ct-money').style.display = ''; moCats(); }")
    exp = opts()
    ok("Продукты" in exp and "Зарплата" not in exp, f"«Расход» — категории расходов: {exp[:4]}…")
    pg.fill("#mo-cat", "Продукты")
    pg.select_option("#mo-kind", "income"); pg.wait_for_timeout(150)
    inc = opts()
    ok("Зарплата" in inc and "Продукты" not in inc and "Кафе и рестораны" not in inc, f"«Доход» — только доходы: {inc}")
    ok(pg.input_value("#mo-cat") == "" and "дохода" in pg.get_attribute("#mo-cat", "placeholder"), "категория расхода при «Доходе» стёрта, подсказка «категория дохода»")
    pg.select_option("#mo-kind", "expense"); pg.wait_for_timeout(150)
    ok("Продукты" in opts() and "Зарплата" not in opts(), "обратно «Расход» — снова расходы")
    b.close()
src = (ROOT / "ui/studio/day.js").read_text(encoding="utf-8")
js_inc = re.search(r"income: \[([^\]]+)\]", src).group(1)
ok(all(f'"{n}"' in js_inc for n, _ in money.INCOME_CATS), "категории доходов студии — те же, что понимает ядро (INCOME_CATS)")
ok(not errs, f"без ошибок на странице: {errs[:3]}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
