"""27.10, владелец: «По играм… рычажки справа и слева внизу, отбиваем шарик, а он выбивает разные там очки… может быть
попробуем и такую красоту возродить в виде игры?» — «Звёздный пинбол» (ui/assets/arcade/pinball):
- на полке «Досуга» (компьютер и телефон), с обложкой; голосом — «давай поиграем в пинбол»;
- пружина запускает шарик из канала, калитка не пускает его обратно; флипперы поднимаются клавишами;
- планеты дают очки, «Чёрная дыра» затягивает шарик, держит и выбрасывает, зажигает звезду Сулафат;
- шарик, упавший в первые секунды, возвращается «страховкой»; без неё — следующий шарик;
- широкое окно (лист «Досуг») — табло и задания по бокам; узкое (телефон) — табло сверху; ошибок на странице нет."""
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


ARC = ROOT / "ui/assets/arcade"
ok((ARC / "pinball/index.html").is_file() and (ARC / "pinball/cover.jpg").is_file(), "игра и обложка на месте")
shelf = (ARC / "shelf.js").read_text(encoding="utf-8")
ok('id: "pinball"' in shelf and "Звёздный пинбол" in shelf, "пинбол — на полке «Досуга»")
gj = (ARC / "pinball/game.js").read_text(encoding="utf-8")
ok(not re.search(r"https?://", gj), "игра не ходит в интернет")
import engine_base as EB  # noqa: E402
for t in ("давай поиграем в пинбол", "открой пинбол", "лира, сыграем в звёздный пинбол"):
    ok(EB.window_phrase(t) == "play" and EB.play_game(t) == "pinball", f"«{t}» → пинбол")
ok('"pinball": "«Звёздный пинбол»"' in (ROOT / "core/engine_commands.py").read_text(encoding="utf-8"), "ядро говорит «Открываю «Звёздный пинбол»»")
app = (ROOT / "android/assets/www/app.js").read_text(encoding="utf-8")
ok('["pinball", /пинбол|флиппер/, "«Звёздный пинбол»"]' in app and "пинбол\\\\S*" in app, "телефон: «поиграем в пинбол» — сразу игра")

U = (ARC / "pinball/index.html").as_uri()
ST = "() => { const S = __pinball.state(); return { mode: S.mode, score: S.score, ball: S.ball, save: S.save, stars: S.stars.slice(), " \
     "balls: S.balls.map(b => ({ x: b.x, y: b.y, ready: !!b.ready, lock: b.lock })), a: __pinball.FLIP.map(f => f.a) }; }"
with sync_playwright() as p:
    b = p.chromium.launch()
    for name, vp in (("широкое окно", {"width": 1280, "height": 800}), ("телефон", {"width": 420, "height": 880})):
        pg = b.new_page(viewport=vp); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(U); pg.wait_for_timeout(600)
        cw, ch = pg.evaluate("[__game.W, __game.H]")
        ok((cw, ch) == ((1280, 720) if name == "широкое окно" else (720, 1400)), f"{name}: поле {cw}×{ch}")
        ok(pg.locator(".pb-stars li").count() == 5, f"{name}: на заставке — пять заданий созвездия")
        pg.click("#aGo"); pg.wait_for_timeout(400)
        s = pg.evaluate(ST)
        ok(s["mode"] == "play" and s["balls"] and s["balls"][0]["ready"], f"{name}: шарик лежит на пружине")
        if name != "широкое окно":
            ok(not errs, f"{name}: без ошибок {errs[:2]}")
            continue
        pg.keyboard.down("Space"); pg.wait_for_timeout(800); pg.keyboard.up("Space"); pg.wait_for_timeout(1400)
        s = pg.evaluate(ST)
        ok(s["balls"] and not s["balls"][0]["ready"] and s["balls"][0]["x"] < 640, f"пружина запустила шарик на стол: {s['balls']}")
        ok(s["save"] > 0, "после запуска включилась страховка")
        pg.keyboard.down("ArrowLeft"); pg.keyboard.down("ArrowRight"); pg.wait_for_timeout(150)
        a = pg.evaluate(ST)["a"]
        ok(all(x < -.4 for x in a), f"флипперы поднялись: {a}")
        pg.keyboard.up("ArrowLeft"); pg.keyboard.up("ArrowRight"); pg.wait_for_timeout(200)
        # планета: шарик сверху падает на розовую
        sc = pg.evaluate("() => { const S = __pinball.state(); S.balls = [{ x: 268, y: 360, vx: 0, vy: 200, trail: [], still: 0, noHole: 0, lock: 0 }]; return S.score; }")
        pg.wait_for_timeout(500)
        s = pg.evaluate(ST)
        ok(s["score"] >= sc + 100, f"планета дала очки: {sc} → {s['score']}")
        # «Чёрная дыра»
        pg.evaluate("() => { const S = __pinball.state(), h = __pinball.HOLE; S.balls = [{ x: h.x + 40, y: h.y - 10, vx: -60, vy: 0, trail: [], still: 0, noHole: 0, lock: 0 }]; }")
        pg.wait_for_timeout(500)
        s = pg.evaluate(ST)
        ok(s["balls"] and s["balls"][0]["lock"] > 0 and s["stars"][3] == 1, f"«Чёрная дыра» затянула шарик и зажгла Сулафат: {s['stars']}")
        pg.wait_for_timeout(1700)
        s = pg.evaluate(ST)
        hx, hy = pg.evaluate("[__pinball.HOLE.x, __pinball.HOLE.y]")
        ok(s["balls"] and s["balls"][0]["lock"] == 0 and ((s["balls"][0]["x"] - hx) ** 2 + (s["balls"][0]["y"] - hy) ** 2) ** .5 > 40,
           f"и выбросила его обратно на стол: {s['balls']}")
        # страховка: шарик ушёл между флипперами
        pg.evaluate("() => { const S = __pinball.state(); S.save = 5; S.balls = [{ x: 335, y: 1200, vx: 0, vy: 600, trail: [], still: 0, noHole: 0, lock: 0 }]; }")
        pg.wait_for_timeout(600)
        s = pg.evaluate(ST)
        ok(s["ball"] == 1 and s["balls"] and s["balls"][0]["ready"], f"страховка вернула шарик на пружину: {s['ball']}")
        pg.evaluate("() => { const S = __pinball.state(); S.save = 0; S.balls = [{ x: 335, y: 1200, vx: 0, vy: 600, trail: [], still: 0, noHole: 0, lock: 0 }]; }")
        pg.wait_for_timeout(2600)
        s = pg.evaluate(ST)
        ok(s["ball"] == 2 and s["balls"] and s["balls"][0]["ready"], f"без страховки — следующий шарик: {s['ball']}")
        # 28.10, владелец: «слишком сложная… мячику не от чего отпрыгивать… справа штука, куда шарик попадает и проигрываем»
        k = pg.evaluate("() => __pinball.state().kick.slice()")
        ok(k == [True, True], f"новый шарик: обе пружины-спасатели в боковых дорожках горят: {k}")
        pg.evaluate("() => { const S = __pinball.state(); S.save = 0; S.mode = 'play'; S.balls = [{ x: 605, y: 1100, vx: 0, vy: 500, trail: [], still: 0, noHole: 0, lock: 0 }]; }")
        pg.wait_for_timeout(500)
        s = pg.evaluate(ST)
        ok(s["ball"] == 2 and s["balls"] and s["balls"][0]["y"] < 1150 and not pg.evaluate("__pinball.state().kick[1]"),
           f"шарик в правой боковой дорожке — пружина вернула его на стол: {s['balls']}")
        m = pg.evaluate("() => { const S = __pinball.state(), m = __pinball.MOONS[0]; S.balls = [{ x: m.x, y: m.y - 60, vx: 0, vy: 900, trail: [], still: 0, noHole: 0, lock: 0 }]; return [S.score, m.ci]; }")
        pg.wait_for_timeout(250)
        s2 = pg.evaluate("() => [__pinball.state().score, __pinball.MOONS[0].ci]")
        ok(s2[0] >= m[0] + 250 and s2[1] != m[1], f"луна: очки и новый цвет от удара: {m} → {s2}")
        ok(pg.evaluate("__pinball.SAVE_S") >= 15, "страховка после запуска — 15 секунд")
        ok(not errs, f"{name}: без ошибок {errs[:2]}")
    b.close()

print("ИТОГ: " + ("всё прошло" if not fails else f"ошибок {len(fails)}"))
sys.exit(1 if fails else 0)
