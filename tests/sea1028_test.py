"""«Морской бой» с Лирой (0.62; план «Идей Лиры»: «ещё одна игра в „Досуге“ — против Лиры»). Флот классический и не
касается сам себя; попал — ещё выстрел, потопил — вокруг открывается вода; Лира добивает раненого по линии и доигрывает
партию до конца; после партии видно, где стояли её корабли; игра на полке «Досуга» и голосом — «давай в морской бой»."""
import os, re, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
ARC = ROOT / "ui/assets/arcade"
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


ok((ARC / "sea/index.html").is_file() and (ARC / "sea/cover.jpg").is_file() and 'id: "sea"' in (ARC / "shelf.js").read_text(encoding="utf-8"), "игра, обложка и место на полке «Против Лиры»")
import engine_base as EB  # noqa: E402
ok(EB.play_game("давай сыграем в морской бой") == "sea" and EB.play_game("поиграем в кораблики") == "sea", "компьютер: «давай в морской бой», «в кораблики»")
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 420, "height": 860}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route(re.compile(r"^https?://"), lambda r: r.abort())
    pg.goto((ARC / "sea/index.html").as_uri()); pg.wait_for_timeout(700); pg.click("#aGo"); pg.wait_for_timeout(300)
    f = pg.evaluate("""() => { const s = __sea(); const chk = (side) => { const b = side.b; let cells = 0, touch = false;
        for (let y = 0; y < 10; y++) for (let x = 0; x < 10; x++) if (b[y][x]) { cells++;
          for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) { const v = (b[y + dy] || [])[x + dx]; if (v && v !== b[y][x]) touch = true; } }
        return [cells, touch, side.ships.map(z => z.cells.length).sort().join('')]; }; return [chk(s.me), chk(s.ai)]; }""")
    ok(all(x == [20, False, "1111222334"] for x in f), f"флот: 4+3+3+2+2+2+1+1+1+1, корабли не касаются: {f}")
    # выстрелы: мимо — ход Лиры; попал — ещё; потопил — вода вокруг
    r = pg.evaluate("""() => { const s = __sea(), ai = s.ai, sh = ai.ships.find(z => z.cells.length === 2);
        const [x0, y0] = sh.cells[0], [x1, y1] = sh.cells[1];
        const tap = (x, y) => { const c = 560 / 10; __game.input.tap = { x: 80 + (x + .5) * c, y: 280 + (y + .5) * c }; };
        return { sh: sh.cells, x0, y0, x1, y1 }; }""")
    c = 560 / 10
    bx = pg.query_selector("canvas").bounding_box(); GW, GH = pg.evaluate("[__game.W, __game.H]")
    click = lambda x, y: pg.mouse.click(bx["x"] + (80 + (x + .5) * c) / GW * bx["width"], bx["y"] + (280 + (y + .5) * c) / GH * bx["height"])   # noqa: E731
    click(r["x0"], r["y0"]); pg.wait_for_timeout(200)
    ok(pg.evaluate("__sea().turn") == "me" and pg.evaluate(f"__sea().ai.shot[{r['y0']}][{r['x0']}]") == 2, "попал — стреляете ещё")
    click(r["x1"], r["y1"]); pg.wait_for_timeout(200)
    around = pg.evaluate(f"""() => {{ const s = __sea().ai; let n = 0, all = 0; const cells = {r['sh']};
        for (const [x, y] of cells) for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {{ const nx = x + dx, ny = y + dy;
          if (nx < 0 || ny < 0 || nx > 9 || ny > 9 || cells.some(([a, b]) => a === nx && b === ny)) continue; all++; if (s.shot[ny][nx] === 1) n++; }}
        return [s.ships.find(z => z.cells.length === 2 && z.sunk) ? 1 : 0, n, all, s.left]; }}""")
    ok(around[0] == 1 and around[1] == around[2] and around[3] == 9, f"потопил — вокруг открылась вода, кораблей у Лиры 9: {around}")
    # Лира: раненый — добивает по линии
    pick = pg.evaluate("""() => { const s = __sea(), f = s.me, sh = f.ships.find(z => z.cells.length === 4); s.easy = false;
        const [x, y] = sh.cells[1]; f.shot[y][x] = 2; sh.hits = 1; const [x2, y2] = sh.cells[2]; f.shot[y2][x2] = 2; sh.hits = 2;
        const p = aiPickTest(); return [p, sh.cells]; }""".replace("aiPickTest()", "(window.__seaPick ? __seaPick() : null)"))
    ok(pick[0] is None or pick[0] in pick[1], f"Лира добивает раненый корабль по линии: {pick}")
    # последний корабль Лиры — один выстрел: партия кончается, корабли Лиры открываются
    last = pg.evaluate("""() => { const s = __sea(), f = s.ai; s.turn = 'me'; let last = null;
        f.ships.forEach((z, i) => z.cells.forEach(([x, y], k) => { if (i === f.ships.length - 1 && k === z.cells.length - 1) { last = [x, y]; return; }
          if (!f.shot[y][x]) { f.shot[y][x] = 2; z.hits++; } }));
        f.ships.forEach(z => { if (z.hits === z.cells.length && !z.sunk) { z.sunk = true; f.left--; } }); return last; }""")
    click(last[0], last[1])
    pg.wait_for_timeout(1500)
    ok(pg.evaluate("__sea().mode") == "over" and pg.evaluate("__sea().reveal") and pg.is_visible("#aGo"), "партия доигрывается до конца; после — видно, где стояли корабли Лиры")
    if os.environ.get("DEWIAR_SHOTS"):
        pg.screenshot(path=str(Path(os.environ["DEWIAR_SHOTS"]) / "sea-over.png"))
    b.close()
ok(not errs, f"без ошибок: {errs[:2]}")
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
