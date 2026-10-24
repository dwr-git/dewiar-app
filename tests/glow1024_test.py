"""«Огонёк» (24.10, владелец: «нравятся игры типа Samorost — очень атмосферные… и эту игру в списке повыше»).
Проходится от начала до конца касаниями: луна → камыш → кувшинка → колокольчик (лягушка ныряет) → дальше;
сова → паутина → ведро → камень (подъёмник); одуванчик → мотылёк → фонарь — дом светится, сказка кончается.
Порядок важен: «рано» — Огонёк задумывается, а не проходит дальше."""
import os
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 420, "height": 860})
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto((ROOT / "ui/assets/arcade/glow/index.html").as_uri()); pg.wait_for_timeout(900)
    pg.click("#aGo"); pg.wait_for_timeout(2300)
    bx = pg.query_selector("canvas").bounding_box(); k = bx["width"] / 720

    def tap(x, y, ms=1200):
        pg.mouse.click(bx["x"] + x * k, bx["y"] + y * k); pg.wait_for_timeout(ms)

    st = lambda: pg.evaluate("(() => { const {G} = __glow(); return {si: G.si, n: G.count, mode: G.mode}; })()")
    # сцена 1: камыш до луны — светлячки спят
    tap(110, 850, 1500)
    ok(st()["n"] == 0, "в темноте камыш только шуршит — светлячки спят")
    tap(520, 260, 2600); tap(110, 850, 2400); tap(400, 1056, 2400)
    ok(st()["n"] == 3, f"луна вышла — три светлячка у Огонька: {st()}")
    tap(690, 900, 1500)
    ok(st()["si"] == 0, "лягушка спит на бревне — дальше не пройти")
    tap(238, 880, 4000); tap(690, 900, 4500)
    ok(st()["si"] == 1, f"колокольчик разбудил лягушку — вторая сцена: {st()}")
    # сцена 2: паук не пускает, пока не ухнула сова; ведро — только с освобождёнными светлячками
    pg.wait_for_timeout(1500)
    tap(520, 1020, 2500)
    ok(st()["si"] == 1 and not pg.evaluate("__glow().hero.ride"), "в ведро рано — светлячки ещё в паутине")
    tap(130, 560, 2600); tap(338, 812, 3400)
    ok(st()["n"] == 6, f"сова спугнула паука — паутина рвётся, шесть светлячков: {st()}")
    tap(520, 1020, 2300); tap(452, 214, 7500)
    ok(st()["si"] == 2, f"камень в корзину — подъёмник наверх, третья сцена: {st()}")
    # сцена 3
    pg.wait_for_timeout(1500)
    tap(300, 742, 2200)
    ok(st()["mode"] == "play" and pg.evaluate("__glow().G.sc && true"), "фонарь без всех светлячков не зажечь")
    tap(160, 805, 4000); tap(424, 880, 9800)
    ok(st()["n"] == 9, f"одуванчик и мотылёк — все девять: {st()}")
    tap(300, 742, 12000)
    ok(st()["mode"] == "end" and pg.is_visible("#aOverlay") and "Огонёк дома" in pg.inner_text("#aOverlay"), "фонарь горит, Огонёк дома — конец сказки")
    ok(not errs, f"без ошибок: {errs[:2]}")
    b.close()

if fails:
    raise SystemExit(1)
