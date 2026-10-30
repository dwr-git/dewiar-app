"""«Вопрос — ответ» в студии (27.10, владелец: «нужно сделать, удобно, красиво, плиткой, с поиском»): плитки разделов
руководства (data/guide.json) со счётчиками; плитка — статьи раздела; поиск своими словами — первая статья справа;
«Попробуйте сказать» — фраза уходит Лире; «Открыть раздел» — в раздел студии; «Спросить Лиру» — вопрос в «Чат».
Настоящее ядро (команда guide), без модели."""
import json, os, socket, subprocess, sys, tempfile, time
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
TESTS = ROOT / "tests"
PY = os.environ.get("DEWIAR_PY") or sys.executable
SHOTS = os.environ.get("DEWIAR_SHOTS")
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


def free():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


tmp = Path(tempfile.mkdtemp()); PORT = free(); cfg = tmp / "cfg"; cfg.mkdir()
(cfg / "settings.json").write_text(json.dumps({"persona": "lira", "audio": {"sounds": False}, "ui": {"news_seen": "99.0.0", "welcome": "done"},
    "stt": {"engine": "vosk"}, "tts": {"engine": "off"}, "updates": {"auto_check": False}}))
env = dict(os.environ, DEWIAR_CONFIG_DIR=str(cfg), DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_PORT=str(PORT), DEWIAR_ASSUME_AEC="1",
           DEWIAR_WORKSPACE_DIR=str(tmp / "ws"), DEWIAR_DRY_TOOLS=str(tmp / "dry.jsonl"))
core = subprocess.Popen([PY, str(ROOT / "core/main.py"), "--wav", str(TESTS / "silence90.wav"), "--null-audio"], env=env,
                        stdout=open(tmp / "core.log", "w"), stderr=subprocess.STDOUT)
for _ in range(150):
    time.sleep(0.2)
    if (cfg / "token").exists():
        break
time.sleep(2); tok = (cfg / "token").read_text().strip()
G = json.loads((ROOT / "data/guide.json").read_text(encoding="utf-8"))
errs = []
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        for w in (1400, 900):
            pg = b.new_page(viewport={"width": w, "height": 1000}); pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.goto((ROOT / "ui/settings.html").as_uri() + f"?token={tok}&port={PORT}"); time.sleep(2.5)
            pg.click('nav button[data-p="qa"]'); time.sleep(1.2)
            tiles = pg.locator("#qa-left .qa-tile")
            groups = list(dict.fromkeys(s["group"] for s in G))
            ok(tiles.count() == len(groups) and "статьи" in pg.inner_text("#qa-left") or "статей" in pg.inner_text("#qa-left"), f"{w}: плитки разделов ({tiles.count()} из {len(groups)}) со счётчиками")
            ok(pg.is_visible("#qa-art h2"), f"{w}: справа сразу статья — «{pg.inner_text('#qa-art h2')}»")
            sw = pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
            ok(sw <= 0, f"{w}: без горизонтальной прокрутки ({sw})")
            fs = pg.evaluate("(() => { const i = getComputedStyle(document.querySelector('#qa-q')); return [i.boxShadow, i.backgroundColor]; })()")
            ok(fs[0] == "none" and fs[1] in ("rgba(0, 0, 0, 0)", "transparent"), f"{w}: поле поиска не вдавлено второй раз внутри полосы (28.10): {fs}")
            if SHOTS:
                pg.screenshot(path=os.path.join(SHOTS, f"qa-{w}.png"))
            if w != 1400:
                pg.close(); continue
            pg.click('#qa-left .qa-tile:has-text("Семья и дети")'); time.sleep(0.6)
            rows = pg.evaluate("[...document.querySelectorAll('#qa-left .qa-row b')].map(x => x.textContent)")
            ok(any("Детский режим" in r for r in rows) and any("Семья" in r for r in rows), f"плитка «Семья и дети» — её статьи: {rows}")
            # 30.10, владелец: «опять выделение активного блока обводкой, которые я не люблю»; «справа всё объясняется —
            # раскрашивать в цвет выбранной темы, как в нашем текстовом редакторе»
            pg.click('#qa-left .qa-row:has-text("Детский режим")'); time.sleep(0.4)
            on = pg.evaluate("(() => { const r = document.querySelector('#qa-left .qa-row.on'); const c = getComputedStyle(r);"
                             " return [c.boxShadow, c.outlineStyle, c.backgroundColor, getComputedStyle(r.querySelector('b')).color]; })()")
            ok("inset" not in on[0] and on[1] == "none", f"выбранная статья — без обводки: {on[:2]}")
            plain = pg.evaluate("getComputedStyle(document.querySelector('#qa-left .qa-row:not(.on)')).backgroundColor")
            ok(on[2] != plain, f"выбранная — подложкой цвета темы: {on[2]} (остальные {plain})")
            art = pg.evaluate("(() => { const a = document.querySelector('#qa-art'), ink = getComputedStyle(a.querySelector('.qa-lead')).color;"
                              " const h = a.querySelector('h4'), b = a.querySelector('.qa-how b');"
                              " return [a.dataset.cs, ink, h && getComputedStyle(h).color, b && getComputedStyle(b).color]; })()")
            ok(art[0] and art[2] and art[2] != art[1] and art[3] and art[3] != art[1],
               f"статья — в цветах схемы ({art[0]}): заголовки {art[2]}, «названия» {art[3]}, текст {art[1]}")
            if SHOTS:
                pg.screenshot(path=os.path.join(SHOTS, "qa-on.png"))
            pg.fill("#qa-q", "как связать телефон и компьютер"); time.sleep(1.0)
            ok("Устройства" in pg.inner_text("#qa-art h2") and "Подключить ещё устройство" in pg.inner_text("#qa-art"),
               f"поиск своими словами — нужная статья справа: {pg.inner_text('#qa-art h2')}")
            if SHOTS:
                pg.screenshot(path=os.path.join(SHOTS, "qa-search.png"))
            pg.fill("#qa-q", "детский режим"); time.sleep(1.0)
            pg.click("#qa-art .qa-try >> nth=0"); time.sleep(1.5)
            dry = (tmp / "dry.jsonl").read_text(encoding="utf-8") if (tmp / "dry.jsonl").exists() else ""
            log = (tmp / "core.log").read_text(encoding="utf-8", errors="replace")
            ok("Уго" in log or "Уго" in dry, "«Попробуйте сказать» ▶ — фраза ушла Лире")
            pg.click("#qa-go"); time.sleep(0.6)
            ok(pg.evaluate("document.querySelector('nav button.cur').dataset.p") == "kids", "«Открыть раздел» — студия → «Дети»")
            pg.click('nav button[data-p="qa"]'); time.sleep(0.4)
            pg.fill("#qa-q", "квантовая хромодинамика"); time.sleep(1.0)
            ok("Ничего не нашлось" in pg.inner_text("#qa-left") and "Спросить Лиру" in pg.inner_text("#qa-left"), "не нашлось — честно и подсказка спросить Лиру")
            pg.click("#qa-ask"); time.sleep(1.0)
            ok(pg.evaluate("document.querySelector('nav button.cur').dataset.p") == "chat", "«Спросить Лиру» — вопрос в «Чат»")
            pg.close()
        ok(not errs, f"без ошибок на странице: {errs[:2]}")
        b.close()
finally:
    core.terminate()
print("ИТОГ:", "все проверки пройдены" if not fails else f"не пройдено {len(fails)}")
sys.exit(1 if fails else 0)
