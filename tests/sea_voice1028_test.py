"""«Морской бой» голосом (0.63; план «Идей Лиры»: «„Б пять!“ — Лира ставит выстрел сама и отвечает голосом: „мимо“,
„ранен“, „убит“»). Игра во фрейме у хозяина (телефон — app.js, компьютер — pad.js): {arcade: 'heard'} — ход, итог хода и
выстрел Лиры — одной фразой {arcade: 'say'}; кнопка микрофона — {arcade: 'listen'}. Касаниями — молча, как раньше.
Компьютер: пока игра открыта (game_mark), «бэ пять» — не вопрос модели, а ход (событие game); game_say говорит итог."""
import os, re, sys, shutil, tempfile, time
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


# ---------- компьютер: ход голосом — к игре, а не модели ----------
import engine_commands as EC  # noqa: E402


class Eng:
    SEA_CELL_RX, SEA_CMD_RX = EC.CommandsMixin.SEA_CELL_RX, EC.CommandsMixin.SEA_CMD_RX
    _game_voice = EC.CommandsMixin._game_voice

    def __init__(self):
        self.ev = []

    def emit(self, kind, **kw):
        self.ev.append((kind, kw))


E = Eng()
ok(not E._game_voice("бэ пять"), "игра не открыта — «бэ пять» идёт как обычно")
E._game_on = ("sea", time.monotonic())
moves = ["бэ пять", "Б5", "Д 7", "стреляю в ка десять", "е три", "Лира, а один", "сдаюсь", "ещё партию", "играем", "сколько у тебя кораблей"]
got = [m for m in moves if E._game_voice(m)]
ok(got == moves and E.ev[0] == ("game", {"game": "sea", "text": "бэ пять"}), f"игра открыта — ход и слова игры уходят в игру: {[m for m in moves if m not in got]}")
E.ev.clear()
talk = ["какая погода завтра", "расскажи анекдот", "поставь будильник на семь", "включи музыку", "а что ты умеешь делать в этой программе вообще"]
ok(not any(E._game_voice(m) for m in talk) and not E.ev, "обычные просьбы в игре — по-прежнему Лире")
E._game_on = ("snake", time.monotonic())
ok(not E._game_voice("бэ пять"), "другая игра — голосом не ходим")
ea = (ROOT / "core/engine_answer.py").read_text(encoding="utf-8"); ec = (ROOT / "core/engine_commands.py").read_text(encoding="utf-8")
ok(ea.index("self._game_voice(text)") < ea.index("self._window_cmd(text)") and 'cmd == "game_mark"' in ec and 'cmd == "game_say"' in ec and "keep=False" in ec,
   "ядро: ход — до остальных быстрых команд; game_mark / game_say; ход игры не пишется в разговор")
src = (ROOT / "ui/pad.js").read_text(encoding="utf-8")
ok('core.call("game_mark"' in src and 'core.call("game_say"' in src and 'core.call("ptt")' in src and 'arcade: "heard"' in src,
   "лист «Досуг» на компьютере: отмечает игру, передаёт ход, слушает по кнопке, говорит итог")
ph = (ROOT / "android/assets/www/app.js").read_text(encoding="utf-8")
ok("if (gameVoice()) return gameHeard(t)" in ph and 'e.data.arcade === "listen" && gameVoice()' in ph and 'e.data.arcade === "say" && gameVoice()' in ph,
   "телефон: услышанное в игре — игре, «слушать» и «сказать» — от игры")

# ---------- сама игра во фрейме ----------
tmp = Path(tempfile.mkdtemp(prefix="seav"))
host = tmp / "host.html"
host.write_text("""<!doctype html><meta charset="utf-8"><body style="margin:0">
<iframe id="g" src="%s" style="width:420px;height:860px;border:0"></iframe>
<script>window.msgs = []; addEventListener('message', e => { if (e.source === document.getElementById('g').contentWindow) msgs.push(e.data); });
window.hear = (t) => document.getElementById('g').contentWindow.postMessage({ arcade: 'heard', text: t }, '*');</script>""" % (ARC / "sea/index.html").as_uri(), encoding="utf-8")
try:
    with sync_playwright() as p:
        b = p.chromium.launch(); errs = []
        pg = b.new_page(viewport={"width": 420, "height": 860}); pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.route(re.compile(r"^https?://"), lambda r: r.abort())
        pg.goto(host.as_uri()); pg.wait_for_timeout(900)
        fr = pg.frame_locator("#g"); gf = pg.frames[1]
        cells = gf.evaluate("() => ['Б5', 'бэ пять', 'стреляю в дэ семь', 'К-10', 'ка десять', 'а один', 'Е 3', 'привет', 'и 11'].map(__seaCell)")
        ok(cells == [[1, 4], [1, 4], [4, 6], [9, 9], [9, 9], [0, 0], [5, 2], None, None], f"клетки на слух: {cells}")
        ok(fr.locator("#seaMic").count() == 1, "во фрейме — кнопка микрофона в панели игры")
        says = lambda: [m["text"] for m in pg.evaluate("msgs") if m.get("arcade") == "say"]   # noqa: E731
        # «играем» голосом с заставки — партия начинается
        pg.evaluate("hear('играем')"); pg.wait_for_timeout(500)
        ok(gf.evaluate("__sea().mode") == "play" and any("Ваш выстрел" in t for t in says()), f"«играем» — партия началась и Лира зовёт стрелять: {says()}")
        # мимо: клетка без корабля -> «… — мимо.» и выстрел Лиры одной фразой
        free = gf.evaluate("""() => { const s = __sea(); for (let y = 0; y < 10; y++) for (let x = 0; x < 10; x++) {
            let near = false; for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) if ((s.ai.b[y + dy] || [])[x + dx]) near = true;
            if (!near) return [x, y]; } }""")
        LET = ["а", "бэ", "вэ", "гэ", "дэ", "е", "жэ", "зэ", "и", "ка"]
        n0 = len(says())
        pg.evaluate(f"hear('{LET[free[0]]} {free[1] + 1}')"); pg.wait_for_timeout(250)
        ok(gf.evaluate(f"__sea().ai.shot[{free[1]}][{free[0]}]") == 1 and gf.evaluate("__sea().turn") == "ai", "«дэ семь» — выстрел в эту клетку, мимо — ход Лиры")
        pg.evaluate("hear('бэ два')"); pg.wait_for_timeout(200)
        ok(any("Подождите" in t for t in says()[n0:]), "пока Лира целится — «подождите»")
        for _ in range(60):
            if gf.evaluate("__sea().turn") == "me" or gf.evaluate("__sea().end"):
                break
            pg.wait_for_timeout(250)
        pg.wait_for_timeout(200)
        last = [t for t in says()[n0:] if "Подождите" not in t]
        ok(last and "мимо." in last[0] and "Стреляю:" in last[0] and ("Ваш ход" in last[0] or "победила" in last[0]),
           f"одна фраза: мой выстрел — мимо, выстрел Лиры и «ваш ход»: {last}")
        # уже стреляли и непонятное
        n1 = len(says())
        pg.evaluate(f"hear('{LET[free[0]]} {free[1] + 1}')"); pg.wait_for_timeout(200)
        pg.evaluate("hear('хочу пиццу')"); pg.wait_for_timeout(200)
        pg.evaluate("hear('')"); pg.wait_for_timeout(200)
        s2 = says()[n1:]
        ok(len(s2) == 3 and "уже стреляли" in s2[0] and "Не поняла клетку" in s2[1] and "Не расслышала" in s2[2], f"уже стреляли / не поняла / не расслышала: {s2}")
        # попадание: «ранили — стреляйте ещё» сразу, ход остаётся
        hit = gf.evaluate("() => { const s = __sea(), sh = s.ai.ships.find(z => z.cells.length === 3 && !z.sunk); return sh.cells[0]; }")
        n2 = len(says())
        pg.evaluate(f"hear('{LET[hit[0]]} {hit[1] + 1}')"); pg.wait_for_timeout(250)
        ok(gf.evaluate("__sea().turn") == "me" and any("Ранили! Стреляйте ещё" in t for t in says()[n2:]), f"попал — «ранили, стреляйте ещё»: {says()[n2:]}")
        pg.evaluate("hear('сколько кораблей осталось')"); pg.wait_for_timeout(200)
        ok("У меня кораблей: 10, у вас:" in says()[-1], f"«сколько осталось»: {says()[-1]}")
        # микрофон — просьба хозяину слушать
        fr.locator("#seaMic").click(); pg.wait_for_timeout(200)
        ok({"arcade": "listen"} in pg.evaluate("msgs"), "кнопка микрофона — {arcade: 'listen'} хозяину")
        if os.environ.get("DEWIAR_SHOTS"):
            pg.screenshot(path=str(Path(os.environ["DEWIAR_SHOTS"]) / "sea-voice.png"))
        pg.evaluate("hear('сдаюсь')"); pg.wait_for_timeout(1200)
        ok(gf.evaluate("__sea().mode") == "over" and gf.evaluate("__sea().reveal"), "«сдаюсь» — партия окончена, корабли Лиры видны")
        # касаниями — молча (голос не включали)
        pg.goto(host.as_uri()); pg.wait_for_timeout(900); gf = pg.frames[1]
        pg.frame_locator("#g").locator("#aGo").click(); pg.wait_for_timeout(300)
        bx = pg.frame_locator("#g").locator("canvas").bounding_box(); GW, GH = gf.evaluate("[__game.W, __game.H]")
        c = 560 / 10
        for (x, y) in [(0, 0), (5, 5), (9, 9)]:
            if gf.evaluate("__sea().turn") == "me":
                pg.mouse.click(bx["x"] + (80 + (x + .5) * c) / GW * bx["width"], bx["y"] + (280 + (y + .5) * c) / GH * bx["height"]); pg.wait_for_timeout(1500)
        ok(gf.evaluate("__sea().shots") >= 1 and not says(), "касаниями — играет молча, голосом не говорит")
        b.close()
    ok(not errs, "без ошибок JavaScript" + (f": {errs[:3]}" if errs else ""))
finally:
    shutil.rmtree(tmp, ignore_errors=True)
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
