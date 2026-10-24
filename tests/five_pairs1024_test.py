"""Две игры по идеям людей (24.10, владелец: «люди начинают присылать свои идеи по играм: 5 в линию; поиск двух одинаковых
картинок — кликаешь на карточку, она разворачивается на секунду и опять закрывается»). Свои версии, нарисованные кодом.
«Пять в ряд» — гомоку 13×13 против Лиры: закрывает чужую четвёрку, достраивает свою, «Ход назад» снимает и её ход, и ваш.
«Найди пару» — в начале карточки показываются («Запомните!»), неверная пара закрывается сама, уровни растут."""
import os
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
ARC = ROOT / "ui/assets/arcade"
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    for vw, vh, tag in ((727, 560, "широкое окно"), (393, 820, "телефон")):
        pg = b.new_page(viewport={"width": vw, "height": vh}); pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto((ARC / "five/index.html").as_uri() + "?light=1"); pg.wait_for_timeout(900)
        W = pg.evaluate("__game.W")
        ok(W == (1280 if vw > vh else 720), f"«Пять в ряд», {tag}: своя раскладка ({W})")
        pg.click("#aGo"); pg.wait_for_timeout(500)
        box = pg.query_selector("canvas").bounding_box(); s = box["width"] / W
        geo = (74, 58, 604) if W == 1280 else (50, 318, 620)
        cell = geo[2] / 13

        def tap(x, y, ms=1300):
            pg.mouse.click(box["x"] + (geo[0] + cell / 2 + x * cell) * s, box["y"] + (geo[1] + cell / 2 + y * cell) * s); pg.wait_for_timeout(ms)
        st = lambda: pg.evaluate("(() => { const S = __five(); return {turn: S.turn, n: S.hist.length, mode: S.mode, win: S.win && S.win.p}; })()")
        tap(6, 6)
        ok(st()["n"] == 2 and st()["turn"] == 1, f"{tag}: ваш камень и ответ Лиры: {st()}")
        # Лира закрывает открытую четвёрку: подставляем позицию (4 ваших в ряд, её ход)
        blk = pg.evaluate("""(() => { const S = __five(); for (const r of S.b) r.fill(0); S.hist = [];
            for (let x = 3; x < 7; x++) { S.b[10][x] = 1; S.hist.push([x, 10, 1]); }
            S.b[0][0] = 2; S.b[0][1] = 2; S.b[0][2] = 2; S.hist.push([0, 0, 2], [1, 0, 2], [2, 0, 2]); S.turn = 2; S.think = 0; return true; })()""")
        pg.wait_for_timeout(1600)
        bb = pg.evaluate("(() => { const S = __five(); return [S.b[10][2], S.b[10][7]]; })()")
        ok(blk and 2 in bb and not st()["win"], f"{tag}: Лира закрывает вашу четвёрку: {bb}")
        # «Ход назад» — снимает её ход и ваш
        n0 = st()["n"]; tap(8, 3, 1500); n1 = st()["n"]
        und = (740, 560, 230, 74) if W == 1280 else (60, 1012, 290, 82)
        pg.mouse.click(box["x"] + (und[0] + und[2] / 2) * s, box["y"] + (und[1] + und[3] / 2) * s); pg.wait_for_timeout(400)
        ok(n1 == n0 + 2 and st()["n"] == n0 and st()["turn"] == 1 and not pg.evaluate("__five().b[3][8]"), f"{tag}: «Ход назад» — снова ваш ход ({n0}→{n1}→{st()['n']})")
        # своя пятёрка — победа и окно конца
        pg.evaluate("""(() => { const S = __five(); for (const r of S.b) r.fill(0); S.hist = [];
            for (let y = 2; y < 6; y++) { S.b[y][1] = 1; S.hist.push([1, y, 1]); } S.b[12][12] = 2; S.b[12][11] = 2; S.turn = 1; return true; })()""")
        tap(1, 6, 2600)
        ok(st()["mode"] == "over" and pg.is_visible("#aOverlay") and "Ещё партию" in pg.inner_text("#aOverlay"), f"{tag}: пять в ряд — победа, «Ещё партию»: {st()}")
        pg.close()

        # «Найди пару»
        pg = b.new_page(viewport={"width": vw, "height": vh}); pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto((ARC / "pairs/index.html").as_uri() + "?light=1"); pg.wait_for_timeout(900)
        pg.click("#aGo"); pg.wait_for_timeout(700)
        W = pg.evaluate("__game.W"); box = pg.query_selector("canvas").bounding_box(); s = box["width"] / W
        ok(pg.evaluate("__pairs().cards.every(c => c.open || c.shown || c.face > .5) || __pairs().peek > 0"), f"«Найди пару», {tag}: в начале карточки показываются")
        pg.wait_for_timeout(2600)
        for lvl in range(2):
            cards = pg.evaluate("__pairs().cards.map(c => c.k)")
            rects = pg.evaluate("""(() => { const S = __pairs(), L = S.L; return S.cards.map((c, i) => { const x = i % S.cols, y = (i / S.cols) | 0;
                return [L.x0 + x * (L.cw + L.gap) + L.cw / 2, L.y0 + y * (L.ch + L.gap) + L.ch / 2]; }); })()""")
            click = lambda i, ms=260: (pg.mouse.click(box["x"] + rects[i][0] * s, box["y"] + rects[i][1] * s), pg.wait_for_timeout(ms))
            j = next(i for i, k in enumerate(cards) if i > 0 and k != cards[0])
            click(0); click(j, 1400)
            ok(pg.evaluate("__pairs().pairs") == 0 and pg.evaluate(f"!__pairs().cards[0].open && !__pairs().cards[{j}].open"), f"{tag}, уровень {lvl + 1}: неверная пара закрылась сама")
            done = set()
            for i in range(len(cards)):
                if i in done:
                    continue
                m = next(q for q, k in enumerate(cards) if q != i and k == cards[i]); done |= {i, m}
                click(i); click(m)
            pg.wait_for_timeout(1900)
            r = pg.evaluate("(() => { const S = __pairs(); return {mode: S.mode, pairs: S.pairs, n: S.cards.length}; })()")
            ok(r["mode"] != "play" and pg.is_visible("#aOverlay") and r["pairs"] * 2 == r["n"], f"{tag}, уровень {lvl + 1}: все пары найдены — окно уровня: {r}")
            n = r["n"]; pg.click("#aGo"); pg.wait_for_timeout(3300)
            if lvl == 0:
                ok(pg.evaluate("__pairs().cards.length") > n, f"{tag}: следующий уровень — карточек больше ({n}→{pg.evaluate('__pairs().cards.length')})")
        pg.close()
    ok(not errs, f"без ошибок: {errs[:2]}")
    b.close()

if fails:
    raise SystemExit(1)
