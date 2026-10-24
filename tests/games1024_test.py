"""24.10, владелец: «Досуг» — «сидишь в очереди к врачу: „Лира, давай поиграем“ — и набор миленьких игр прямо в
интерфейсе Лиры… на компьютере — в похожем формате, как блокнот; можно в него игры». Пять игр (ui/assets/arcade):
- блокнот у виджета: кнопка 🎮 → полка игр (assets/arcade/shelf.js), игра во фрейме; «Игры» в игре — снова полка,
  «к блокноту» — снова заметки; фрейм пустеет (музыка не играет в фоне); светлая тема — ?light=1;
- «Возможности» → «Досуг» выключен — кнопки нет, режим не открывается;
- голосом: «Лира, давай поиграем», «поиграем в змейку» — window_phrase "play", play_game; «сыграем в города» — модели;
- игры без сети: шрифт Rubik свой, ни одного адреса в интернете."""
import json, os, re, sys, urllib.parse
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
web = [f for f in ARC.rglob("*") if f.suffix in (".html", ".js", ".css") and re.search(r"https?://", f.read_text(encoding="utf-8"))]
ok(not web, f"игры не ходят в интернет (шрифты свои): {web}")
ok(all((ARC / g / "index.html").is_file() and (ARC / g / "cover.jpg").is_file() for g in ("plane", "bip", "bricks", "snake", "racer", "blocks", "candy", "merge", "sudoku", "fifteen", "reversi", "tictac", "crossword", "words", "glow", "five", "pairs"))
   and (ARC / "shared/fonts/OFL-Rubik.txt").is_file(), "семнадцать игр с обложками, лицензия шрифта рядом")

import engine_base as EB  # noqa: E402
for t, k, g in (("Лира, давай поиграем", "play", ""), ("хочу поиграть", "play", ""), ("поиграем в змейку", "play", "snake"),
                ("открой гонку", "play", "racer"), ("поиграем в судоку", "play", "sudoku"), ("давай в тетрис поиграем", None, ""), ("открой блокнот", None, ""), ("давай сыграем в города", None, ""), ("спрячься", "tray", ""),
                ("давай поиграем в крестики нолики", "play", "tictac"), ("лира, сыграем в кроссворд", "play", "crossword"), ("хочу поиграть в пять букв", "play", "words"),
                ("давай поиграем в пять в ряд", "play", "five"), ("сыграем в гомоку", "play", "five"), ("открой найди пару", "play", "pairs"), ("поиграем в пары", "play", "pairs"),
                ("давай поиграем пару минут", None, "")):
    ok(EB.window_phrase(t) == k and (k != "play" or EB.play_game(t) == g), f"«{t}» → {EB.window_phrase(t)} {EB.play_game(t)!r}")
cmd = (ROOT / "core/engine_commands.py").read_text(encoding="utf-8")
ok('kind == "play"' in cmd and '.get("games") is False' in cmd and 'self.emit("window", do="play", game=game)' in cmd, "ядро: «поиграем» — событие окну, выключено — подсказка про «Возможности»")
app = (ROOT / "ui/app.py").read_text(encoding="utf-8")
ok("def play_open(self, game=\"\")" in app and "def pad_toggle(self, mode=\"notes\")" in app and '"&mode=play"' in app, "окно: блокнот открывается сразу «Досугом»")
hud = (ROOT / "ui/hud.html").read_text(encoding="utf-8")
ok('id="b-play"' in hud and 'a.pad_toggle("play")' in hud and 'e.do === "play" && a.play_open' in hud, "виджет: кнопка 🎮 и «давай поиграем»")

FAKE = """window.apiCalls = []; window.pywebview = { api: new Proxy({}, { get: (_, k) => (...a) => { apiCalls.push([k, ...a]);
  if (k === 'pad_size') return Promise.resolve([440, 560]); if (k === 'get_pos') return Promise.resolve([1500, 300]); return Promise.resolve(true); } }) };"""
CORE = r"""
(() => { window.calls = []; window.FEAT = %s;
  const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.connected = true;
    core.call = async (c, a) => { calls.push([c, a]);
      if (c === "pad_tabs") return { tabs: [{ name: "Главное", mtime: 1 }], active: "Главное" };
      if (c === "pad_read") return { name: a.name, text: "Текст\n", mtime: 1 };
      return {}; };
    setTimeout(() => core.emit("settings", { settings: { ui: { skin: "neusky" }, features: FEAT } }), 300); };
  ready(); })();
"""
URL = (ROOT / "ui/pad.html").as_uri() + "?skin=neusky&cfg=" + urllib.parse.quote(json.dumps({"side": "left", "gap": 14, "clips": []}))
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 454, "height": 620}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route(re.compile(r"^https?://"), lambda r: r.abort())
    pg.add_init_script(FAKE); pg.add_init_script(CORE % json.dumps({"games": True}))
    pg.goto(URL); pg.wait_for_timeout(1200)
    ok(pg.is_visible("#b-play"), "в блокноте — кнопка «Досуг»")
    pg.click("#b-play"); pg.wait_for_timeout(500)
    names = pg.evaluate("[...document.querySelectorAll('#shelf .ag b')].map(b => b.textContent)")
    ok(names == ["Огонёк", "Хутор Одуванчик", "Кто боится темноты", "Тетрис", "Конфетки", "Слияние", "Каляка", "Колючая почта", "Пятнашки", "Судоку", "Найди пару", "Кроссворд", "Пять букв", "Пять в ряд", "Крестики-нолики", "Реверси", "Выше облаков", "Бип", "Гонка", "Небесный пилот", "Кирпичики", "Змейка"] and not pg.is_visible("#tabs") and not pg.is_visible("#ed") and pg.is_visible("#b-notes"),
       f"«Досуг»: полка игр вместо вкладок и листа: {names}")
    ok(["pad_mode_mark", "play"] in pg.evaluate("apiCalls"), "виджет узнаёт, что открыт «Досуг» (подсветка кнопки)")
    pg.screenshot(path="/tmp/claude-0/games_shelf.png")
    pg.click("#shelf .ag[data-game='snake']"); pg.wait_for_timeout(2200)
    src = pg.evaluate("document.querySelector('#game').getAttribute('src')")
    ok(src.endswith("snake/index.html?light=1") and pg.is_visible("#game") and not pg.is_visible("#shelf") and pg.inner_text("#play-t") == "Досуг",
       f"игра во фрейме, в светлой теме: {src}")
    fr = pg.frame_locator("#game")
    ok(fr.locator("#aBack .lbl").inner_text() == "Игры" and fr.locator("#aFs").is_visible() and
       next(f for f in pg.frames if "snake" in f.url).evaluate("document.documentElement.classList.contains('light')"),
       "внутри: «Игры» вместо «Аркада», «во весь экран» — лист на весь экран (24.10), светлая оболочка")
    pg.screenshot(path="/tmp/claude-0/games_snake.png")
    fr.locator("#aBack").click(); pg.wait_for_timeout(400)
    ok(pg.is_visible("#shelf") and pg.evaluate("document.querySelector('#game').getAttribute('src')") == "about:blank", "«Игры» в игре — снова полка, игра остановлена")
    pg.click("#shelf .ag[data-game='plane']"); pg.wait_for_timeout(1200)
    pg.click("#b-notes"); pg.wait_for_timeout(400)
    ok(pg.is_visible("#ed") and pg.is_visible("#tabs") and pg.evaluate("document.querySelector('#game').getAttribute('src')") == "about:blank",
       "«к блокноту» — снова заметки, игра не играет в фоне")
    pg.evaluate("padGame('racer')"); pg.wait_for_timeout(800)
    ok(pg.evaluate("document.querySelector('#game').getAttribute('src')").startswith("assets/arcade/racer/"), "«поиграем в гонку» — сразу игра")
    # каждая игра запускается и играет без ошибок (светлая и тёмная оболочка); «Играть» — первая кнопка на заставке
    for gid in ("glow", "pairs", "five", "blocks", "candy", "merge", "tictac", "crossword", "words", "sudoku", "fifteen", "reversi", "plane", "bip", "bricks", "snake", "racer", "farm", "dark", "post", "doodle", "hop"):
        gp = b.new_page(viewport={"width": 420, "height": 860}); ge = []; gp.on("pageerror", lambda e, ge=ge: ge.append(str(e)))
        gp.route(re.compile(r"^https?://"), lambda r: r.abort())
        gp.goto((ARC / gid / "index.html").as_uri() + ("?light=1" if gid in ("sudoku", "fifteen") else "")); gp.wait_for_timeout(700)
        gp.click("#aGo"); gp.wait_for_timeout(300)
        for k in ("ArrowLeft", "ArrowUp", "ArrowRight", "Space", "ArrowDown"):
            gp.keyboard.press(k); gp.wait_for_timeout(120)
        gp.mouse.click(210, 430); gp.wait_for_timeout(300)
        ok(not ge and gp.evaluate("window.__game && window.__game.playing !== undefined"), f"«{gid}»: запускается и играет без ошибок {ge[:1]}")
        gp.close()
    # 24.10, владелец: «змейка — сложно играть, есть задержка между нажатием на телефоне» — поворот, пока палец ещё ведёт
    gp = b.new_page(viewport={"width": 420, "height": 860}); ge = []; gp.on("pageerror", lambda e, ge=ge: ge.append(str(e)))
    gp.goto((ARC / "snake/index.html").as_uri()); gp.wait_for_timeout(600); gp.click("#aGo"); gp.wait_for_timeout(400)
    d0 = gp.evaluate("__snake().snake.dir"); bx = gp.query_selector("canvas").bounding_box()
    cx, cy = bx["x"] + bx["width"] / 2, bx["y"] + bx["height"] / 2
    turn = "right" if d0 in ("up", "down") else "down"
    gp.mouse.move(cx, cy); gp.mouse.down()
    gp.mouse.move(cx + (60 if turn == "right" else 0), cy + (60 if turn == "down" else 0), steps=6); gp.wait_for_timeout(400)
    st = gp.evaluate("(() => { const s = __snake().snake; return [s.dir, s.queue.slice()]; })()")
    gp.mouse.up()
    ok(st[0] == turn or turn in st[1], f"змейка поворачивает, пока палец ведёт (не дожидаясь отпускания): {d0} → {st}")
    ok(not ge, f"без ошибок {ge[:1]}"); gp.close()
    # 24.10, владелец: «Блоки выглядят странновато» → «нравится, как сделал для тетриса, и для других так же» — в широком
    # окне (лист «Досуг» на компьютере) у каждой игры своя раскладка 1280×720; на телефоне (книжное окно) — прежняя 720×1280
    for gid in ("blocks", "candy", "merge", "fifteen", "sudoku", "reversi", "tictac", "crossword", "words", "snake", "plane", "bricks", "racer", "glow", "five", "pairs", "farm", "dark", "post", "doodle", "hop"):
        gp = b.new_page(viewport={"width": 772, "height": 560}); ge = []; gp.on("pageerror", lambda e, ge=ge: ge.append(str(e)))
        gp.route(re.compile(r"^https?://"), lambda r: r.abort())
        gp.goto((ARC / gid / "index.html").as_uri() + "?light=1"); gp.wait_for_timeout(600)
        wide = gp.evaluate("__game.W") == 1280 and gp.evaluate("__game.H") == 720
        gp.click("#aGo"); gp.wait_for_timeout(300)
        for k in ("ArrowLeft", "ArrowUp", "ArrowRight", "Space", "ArrowDown"):
            gp.keyboard.press(k); gp.wait_for_timeout(100)
        bx = gp.query_selector("canvas").bounding_box()
        gp.mouse.click(bx["x"] + bx["width"] * .5, bx["y"] + bx["height"] * .5); gp.wait_for_timeout(250)
        ok(wide and not ge and bx["width"] > 640, f"«{gid}» в широком окне: своя раскладка 1280×720, поле {int(bx['width'])} px шириной, без ошибок {ge[:1]}")
        gp.close()
    # 24.10, владелец: «игра должна занимать ширину блока», «окна белые размытые» — поле в широком окне «разлито» цветами
    # своих краёв, экраны меню — в тон игры (тёмная Бип — тёмное стекло и в светлой теме Dewiar)
    gp = b.new_page(viewport={"width": 727, "height": 560}); ge = []; gp.on("pageerror", lambda e, ge=ge: ge.append(str(e)))
    gp.goto((ARC / "sudoku/index.html").as_uri() + "?light=1"); gp.wait_for_timeout(700); gp.click("#aGo"); gp.wait_for_timeout(2200)
    ok(gp.evaluate("document.getElementById('aWrap').classList.contains('tinted')") and "gradient" in gp.evaluate("getComputedStyle(document.getElementById('aWrap')).backgroundImage")
       and gp.evaluate("getComputedStyle(document.getElementById('aStage')).boxShadow") == "none", "книжная игра в широком окне — вокруг поля его же цвета, без рамки «телефона»")
    gp.goto((ARC / "bip/index.html").as_uri() + "?light=1"); gp.wait_for_timeout(900)
    bg = gp.evaluate("getComputedStyle(document.querySelector('.card')).backgroundColor")
    ok(gp.evaluate("document.documentElement.classList.contains('tone-dark')") and bg.startswith("rgba(20, 22, 44"), f"Бип в светлой теме: меню — тёмное стекло ({bg})")
    ok(not ge, f"без ошибок {ge[:1]}"); gp.close()
    # Крестики-нолики (24.10, владелец: «рисуешь крестик или нолик пальцами»): нарисованная петля — нолик, чужой знак стирается
    gp = b.new_page(viewport={"width": 420, "height": 860}); ge = []; gp.on("pageerror", lambda e: ge.append(str(e)))
    gp.goto((ARC / "tictac/index.html").as_uri()); gp.wait_for_timeout(700); gp.click("#aGo"); gp.wait_for_timeout(900)
    bx = gp.query_selector("canvas").bounding_box(); k = bx["width"] / 720
    P = lambda x, y: (bx["x"] + x * k, bx["y"] + y * k)
    import math
    gp.mouse.move(*P(415, 630)); gp.mouse.down()
    for i in range(28):
        a = i * .25; gp.mouse.move(*P(360 + 55 * math.cos(a), 630 + 50 * math.sin(a))); gp.wait_for_timeout(16)
    gp.mouse.up(); gp.wait_for_timeout(1900)
    st = gp.evaluate("(() => { const {S, T} = __tictac(); return {sym: T.sym, c4: S.cells[4] && S.cells[4].who, free: S.cells.findIndex(c => !c)}; })()")
    ok(st["sym"] == "o" and st["c4"] == "p", f"нарисованная петля — нолик игрока, Лира ответила: {st}")
    f = st["free"]; x0, y0 = 90 + (f % 3 + .5) * 180, 360 + (f // 3 + .5) * 180
    for (ax, ay), (bx2, by2) in (((x0 - 50, y0 - 50), (x0 + 50, y0 + 50)), ((x0 + 50, y0 - 50), (x0 - 50, y0 + 50))):
        gp.mouse.move(*P(ax, ay)); gp.mouse.down()
        for i in range(11):
            gp.mouse.move(*P(ax + (bx2 - ax) * i / 10, ay + (by2 - ay) * i / 10)); gp.wait_for_timeout(16)
        gp.mouse.up(); gp.wait_for_timeout(120)
    gp.wait_for_timeout(900)
    st = gp.evaluate(f"(() => {{ const {{S}} = __tictac(); return {{cell: !!S.cells[{f}], msg: S.msg}}; }})()")
    ok(not st["cell"] and "ноликами" in st["msg"], f"крестик у играющего ноликами — стёрт с подсказкой: {st}")
    ok(not ge, f"крестики-нолики без ошибок {ge[:1]}"); gp.close()
    # Кроссворд: сетка из ≥9 слов, ответ печатается с обычной клавиатуры и засчитывается
    gp = b.new_page(viewport={"width": 420, "height": 860}); ge = []; gp.on("pageerror", lambda e: ge.append(str(e)))
    gp.goto((ARC / "crossword/index.html").as_uri()); gp.wait_for_timeout(700); gp.click("#aGo"); gp.wait_for_timeout(300)
    n = gp.evaluate("__cross().words.length")
    for _ in range(20):
        w = gp.evaluate("""(() => { const S = __cross(); const o = S.words.find(q => !q.done); if (!o) return null; S.cur = S.words.indexOf(o);
          const cs = [...o.w].map((_, i) => ({x: o.x + (o.dir ? 0 : i), y: o.y + (o.dir ? i : 0)})); S.pos = cs.findIndex(c => !S.grid[c.y][c.x].ok);
          return cs.map((c, i) => S.grid[c.y][c.x].ok ? '' : o.w[i]).join(''); })()""")
        if not w:
            break
        gp.evaluate("w => { for (const ch of w) dispatchEvent(new KeyboardEvent('keydown', {key: ch})); }", w); gp.wait_for_timeout(60)
    gp.wait_for_timeout(1700)
    ok(n >= 9 and gp.evaluate("__cross().mode") == "over" and gp.is_visible("#aOverlay"), f"кроссворд из {n} слов разгадан до конца")
    ok(not ge, f"кроссворд без ошибок {ge[:1]}"); gp.close()
    # Пять букв: английская раскладка печатает русские буквы по месту клавиши
    gp = b.new_page(viewport={"width": 420, "height": 860}); ge = []; gp.on("pageerror", lambda e: ge.append(str(e)))
    gp.goto((ARC / "words/index.html").as_uri()); gp.wait_for_timeout(700); gp.click("#aGo"); gp.wait_for_timeout(300)
    gp.evaluate("for (const c of ['KeyF', 'Comma', 'KeyE']) dispatchEvent(new KeyboardEvent('keydown', {key: 'x', code: c}))"); gp.wait_for_timeout(200)
    ok(gp.evaluate("__words().cur") == "абу" and not ge, f"«Пять букв»: раскладка любая → {gp.evaluate('__words().cur')!r}"); gp.close()
    # выключено в «Возможностях»
    p2 = b.new_page(viewport={"width": 454, "height": 620}); p2.on("pageerror", lambda e: errs.append(str(e)))
    p2.route(re.compile(r"^https?://"), lambda r: r.abort())
    p2.add_init_script(FAKE); p2.add_init_script(CORE % json.dumps({"games": False}))
    p2.goto(URL); p2.wait_for_timeout(1200)
    p2.evaluate("padMode('play')"); p2.wait_for_timeout(200)
    ok(not p2.is_visible("#b-play") and p2.is_visible("#ed"), "«Досуг» выключен — ни кнопки, ни режима")
    ok(not errs, f"без ошибок на странице: {errs[:2]}")
    b.close()

if fails:
    raise SystemExit(1)
