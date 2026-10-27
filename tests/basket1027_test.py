"""«Лукошко» (27.10, владелец: «игра из детства — ловил яйца, падающие с полок… попробуем добавить такую?»): свои герои,
ЖК-экран. Яйцо доходит до конца жёлоба — лукошко там: очко; нет: разбилось, промах; три промаха — конец; каждые 100 —
промахи прощены. Кнопки (стрелки, Q/A/P/L, нажатие на четверть экрана) ставят лукошко. Широкое окно и телефон стоя."""
import os, time
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
URL = (ROOT / "ui/assets/arcade/basket/index.html").as_uri()
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


errs = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1280, "height": 800}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL); time.sleep(1)
    ok("Лукошко" in pg.inner_text("#aOverlay") and "Игра Б" in pg.inner_text("#aOverlay"), "заставка: «Игра А» и «Игра Б»")
    pg.evaluate("__basket.start('A')"); time.sleep(.3)
    S = lambda: pg.evaluate("({ score: __basket.S.score, miss: __basket.S.miss, pose: __basket.S.pose, mode: __basket.S.mode, eggs: __basket.S.eggs.length })")
    pg.keyboard.press("ArrowRight"); pg.keyboard.press("ArrowUp"); time.sleep(.1)
    ok(S()["pose"] == 2, f"→ и ↑ — лукошко справа вверху: {S()['pose']}")
    pg.keyboard.press("KeyA"); time.sleep(.1)
    ok(S()["pose"] == 1, "A — слева внизу")
    pg.evaluate("__basket.S.nextT = 99; __basket.S.eggs = [{ ramp: 1, pos: 4 }]; __basket.step()")
    ok(S()["score"] == 1 and S()["miss"] == 0, f"яйцо в лукошко — очко: {S()}")
    pg.evaluate("__basket.S.eggs = [{ ramp: 2, pos: 4 }]; __basket.step()")
    ok(S()["miss"] == 1, "мимо лукошка — разбилось, промах")
    pg.evaluate("__basket.S.score = 99; __basket.S.eggs = [{ ramp: 1, pos: 4 }]; __basket.step()")
    ok(S()["score"] == 100 and S()["miss"] == 0, "100 очков — промахи прощены")
    box = pg.locator("canvas").bounding_box()
    pg.mouse.click(box["x"] + box["width"] * .7, box["y"] + box["height"] * .3); time.sleep(.1)
    ok(S()["pose"] == 2, "нажатие на правую верхнюю четверть экрана — лукошко туда")
    pg.mouse.click(box["x"] + box["width"] * (105 / 1280), box["y"] + box["height"] * (520 / 720)); time.sleep(.1)
    ok(S()["pose"] == 1, "левая нижняя красная кнопка — лукошко слева внизу")
    pg.evaluate("for (let i = 0; i < 3; i++) { __basket.S.eggs = [{ ramp: 3, pos: 4 }]; __basket.step(); }"); time.sleep(1.4)
    ok(S()["mode"] == "over" and "Ещё раз" in pg.inner_text("#aOverlay"), "три промаха — конец игры, «Ещё раз»")
    pg.evaluate("__basket.start('B')"); time.sleep(3)
    ok(S()["eggs"] >= 1 and S()["mode"] == "play", "«Игра Б»: яйца катятся сами")
    pg.close()
    ph = b.new_page(viewport={"width": 400, "height": 860}, has_touch=True, is_mobile=True); ph.on("pageerror", lambda e: errs.append(str(e)))
    ph.goto(URL + "?phone=1"); time.sleep(1)
    cb = ph.locator("canvas").bounding_box()
    ok(cb["height"] > cb["width"], f"телефон стоя — устройство стоя, кнопки под экраном: {int(cb['width'])}×{int(cb['height'])}")
    ph.close()
    ok(not errs, f"без ошибок: {errs[:2]}")
    b.close()
print("ИТОГ:", "все проверки пройдены" if not fails else f"не пройдено {len(fails)}")
raise SystemExit(1 if fails else 0)
