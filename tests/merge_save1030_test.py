"""«Слияние» запоминает партию (идеи №77 и №78, 30.10: «возможность сохранить текущее состояние, чтобы позже продолжить»).
После каждого хода — сохранено; снова открыли игру — «Продолжить» с тем же полем и счётом и «Новая игра»; новая игра
и конец партии сохранение забывают. Та же игра — в «Досуге» компьютера и телефона."""
import os, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


URL = (ROOT / "ui/assets/arcade/merge/index.html").as_uri()
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    ctx = b.new_context(viewport={"width": 420, "height": 860})
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL); pg.wait_for_timeout(700)
    ok(pg.inner_text("#aGo") == "Играть" if pg.locator("#aGo").count() else "Играть" in pg.inner_text("#aOverlay"), "первый раз — «Играть»")
    pg.locator("#aOverlay button").first.click(); pg.wait_for_timeout(300)
    for k in ["ArrowLeft", "ArrowDown", "ArrowRight", "ArrowDown", "ArrowLeft", "ArrowUp", "ArrowDown", "ArrowLeft"]:
        pg.keyboard.press(k); pg.wait_for_timeout(260)
    sv = pg.evaluate("JSON.parse(localStorage.getItem('arcade.save.merge') || 'null')")
    ok(sv and sum(v > 0 for r in sv["g"] for v in r) >= 3, f"после ходов партия сохранена: {sv}")
    pg.close()
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL); pg.wait_for_timeout(700)
    btns = pg.evaluate("[...document.querySelectorAll('#aOverlay button')].map(b => b.textContent.trim())")
    ok("Продолжить" in btns and "Новая игра" in btns, f"снова открыли — «Продолжить» и «Новая игра»: {btns}")
    pg.locator("#aOverlay button", has_text="Продолжить").click(); pg.wait_for_timeout(300)
    now = pg.evaluate("JSON.parse(localStorage.getItem('arcade.save.merge'))")
    ok(now["g"] == sv["g"] and now["s"] == sv["s"], "поле и счёт — те же, что были")
    pg.close()
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL); pg.wait_for_timeout(700)
    pg.locator("#aOverlay button", has_text="Новая игра").click(); pg.wait_for_timeout(300)
    ok(pg.evaluate("localStorage.getItem('arcade.save.merge')") is None, "«Новая игра» — сохранение забыто, поле новое")
    b.close()
ok(not errs, f"без ошибок на странице: {errs[:3]}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
