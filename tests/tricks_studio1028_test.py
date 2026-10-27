"""Студия → «Что я умею» (28.10, владелец: «мелковато всё… иконки разделов крупнее и симпатичнее, чтобы не превращалось в
одну большую мелко описанную страницу»): сверху плитки разделов со значками и счётчиком фраз, ниже — фразы одного раздела
крупными карточками; плитка переключает раздел; ▶ отправляет фразу. Настоящее ядро (команда tricks), без модели."""
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


T = json.loads((ROOT / "data/tricks.json").read_text(encoding="utf-8"))
pc = [g for g in T["groups"] if any("pc" in (x.get("where") or []) for x in g["items"])]
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
errs = []
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        for w in (1400, 900):
            pg = b.new_page(viewport={"width": w, "height": 1000})
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.goto((ROOT / "ui/settings.html").as_uri() + f"?token={tok}&port={PORT}"); time.sleep(2.5)
            pg.click('nav button[data-p="tricks"]'); time.sleep(1)
            tiles = pg.locator("#tr-box .tr-tile")
            ok(tiles.count() == len(pc) and pg.locator("#tr-box .tr-tile svg").count() == len(pc), f"{w}: плитки разделов со значками ({tiles.count()} из {len(pc)})")
            size = pg.evaluate("(() => { const i = document.querySelector('#tr-box .tr-tile i').getBoundingClientRect(); const b = getComputedStyle(document.querySelector('#tr-box .trk b')); return [i.width, parseFloat(b.fontSize)]; })()")
            ok(size[0] >= 40 and size[1] >= 15, f"{w}: значки крупные, фразы — не мелкие: {size}")
            first = [x for x in pc[0]["items"] if "pc" in (x.get("where") or [])]
            ok(pg.locator("#tr-box .tr-list .trk").count() == len(first) and pc[0]["name"] in pg.inner_text(".tr-ph"), f"{w}: ниже — фразы одного раздела «{pc[0]['name']}»")
            sw = pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
            ok(sw <= 0, f"{w}: без горизонтальной прокрутки ({sw})")
            if SHOTS:
                pg.screenshot(path=os.path.join(SHOTS, f"tricks-{w}.png"))
            if w != 1400:
                pg.close(); continue
            snd = next(i for i, g in enumerate(pc) if "музык" in g["name"].lower())
            tiles.nth(snd).click(); time.sleep(0.3)
            ok("Включи радио" in pg.inner_text("#tr-box .tr-list") and pg.locator("#tr-box .tr-tile.on").count() == 1, "плитка «Радио, музыка и звук» — его фразы, плитка выделена")
            pg.locator("#tr-box .tplay:not([data-fill])").first.click(); time.sleep(0.8)
            ok("Отправил помощнику" in pg.inner_text("#toast"), "▶ — фраза ушла помощнику")
            pg.close()
        b.close()
    ok(not errs, f"без ошибок на странице: {errs[:2]}")
finally:
    core.terminate()
print("ИТОГ:", "все проверки пройдены" if not fails else f"не пройдено {len(fails)}")
sys.exit(1 if fails else 0)
