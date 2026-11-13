"""13.11 (владелец, снимок телефона 0.9.34): у имени персонажа — оранжевая плашка «1,7630 тал.», шире аватара и уехала за край
экрана: «случайно здесь или поехала вёрстка?». Это значок «мало талеров» (0.82.1) — у счёта сайта он писал баланс целиком.
Теперь коротко — «1,7» (от 10 — целое), полностью — в подсказке; плашка не выходит за экран. EN — словарём."""
import os, re, subprocess, sys, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


www = Path(tempfile.mkdtemp()) / "www"
subprocess.run(["bash", str(ROOT / "android/tools/www_assemble.sh"), str(www)], check=True, capture_output=True)
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 393, "height": 820})
    pg.route(re.compile(r"^https?://"), lambda r: r.abort())
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(1300); pg.evaluate("closeSheets()")
    pg.evaluate("S.llm = Object.assign({}, S.llm, { cloud: true }); balBadge({ site: true, balance: 1.763, balance_text: '1,7630 тал.', percent: 5 })")
    t = pg.text_content("#bal-t"); box = pg.locator("#bal").bounding_box() or {}
    ok(t == "1,7", f"счёт сайта: коротко «1,7», а не «1,7630 тал.»: {t!r}")
    ok(box.get("x", -1) >= 0 and box.get("width", 99) <= 60, f"плашка в пределах экрана и не шире аватара: {box}")
    ok("1,7630 тал." in (pg.get_attribute("#bal", "title") or ""), "полностью — в подсказке")
    pg.evaluate("balBadge({ site: true, balance: 23.4, balance_text: '23,4 тал.', percent: 20 })")
    ok(pg.text_content("#bal-t") == "23", "от 10 — целое")
    pg.evaluate("balBadge({ site: false, balance: 1, percent: 12 })")
    ok(pg.text_content("#bal-t") == "12%", "ключ Dewiar — как раньше, процент")
    pg.evaluate("dwSetLang('en'); balBadge({ site: true, balance: 1.763, balance_text: '1.763', percent: 5 })")
    ok((pg.get_attribute("#bal", "title") or "").startswith("Balance: "), "по-английски — словарём")
    b.close()
print("ИТОГ:", "всё прошло" if not fails else f"{len(fails)} ошибок")
sys.exit(1 if fails else 0)
