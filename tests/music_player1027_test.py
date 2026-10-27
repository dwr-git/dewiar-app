"""Плеер «Музыки» в студии (27.10, владелец: «не хватает громкости, статуса проигранного, а это окошко фиолетовое — красивую
анимацию под музыку; кнопочки симпатичнее»). Настоящее ядро без звука (--null-audio), трек 40 с:
- полоса хода «0:0x / 0:40», время идёт; громкость — ползунок, запоминается (audio.radio_volume);
- нажали на полосу — перемотка (с этого места, а не сначала); пауза → «играть» — продолжает с того же места;
- спектр приходит (полосы > 0), фон-холст рисуется; кнопки — значки, без ошибок на странице."""
import io, json, os, shutil, socket, subprocess, sys, tempfile, time
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
TESTS = ROOT / "tests"
SHOTS = os.environ.get("DEWIAR_SHOTS")
PY = os.environ.get("DEWIAR_PY") or sys.executable
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


def free():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


FF = shutil.which("ffmpeg")
if not FF:
    print("нет ffmpeg — пропускаю"); sys.exit(0)
tmp = Path(tempfile.mkdtemp()); mus = tmp / "Музыка"; mus.mkdir()
subprocess.run([FF, "-loglevel", "error", "-y", "-f", "lavfi", "-i", "sine=f=220:d=40", "-f", "lavfi", "-i", "anoisesrc=d=40:a=0.08",
                "-filter_complex", "amix=inputs=2", "-metadata", "title=Длинная песня", "-metadata", "artist=Тест", str(mus / "long.mp3")], check=True)
PORT = free()
cfg = tmp / "cfg"; cfg.mkdir()
(cfg / "settings.json").write_text(json.dumps({"persona": "lira", "audio": {"sounds": False}, "ui": {"news_seen": "99.0.0", "welcome": "done"},
    "stt": {"engine": "vosk"}, "tts": {"engine": "off"}, "updates": {"auto_check": False}, "music": {"folder": str(mus), "dj_talk": False}}))
env = dict(os.environ, DEWIAR_CONFIG_DIR=str(cfg), DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_PORT=str(PORT), DEWIAR_ASSUME_AEC="1",
           DEWIAR_WORKSPACE_DIR=str(tmp / "ws"))
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
        b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1400, "height": 1000})
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto((ROOT / "ui/settings.html").as_uri() + f"?token={tok}&port={PORT}"); time.sleep(3)
        pg.click('nav button[data-p="music"]'); time.sleep(1.5)
        pg.evaluate("core.call('mm_scan')"); time.sleep(2)
        pg.click("#mm-play-all"); time.sleep(3.5)
        t0, t1 = pg.inner_text("#mm-t0"), pg.inner_text("#mm-t1")
        ok(t1 == "0:40" and t0 in ("0:01", "0:02", "0:03", "0:04"), f"полоса хода: {t0} / {t1}")
        ok(pg.evaluate("document.querySelector('#mm-pp').classList.contains('playing')") and pg.locator("#mm-pp svg").count() == 1, "кнопка — значок «пауза», не текст")
        v = pg.evaluate("core.call('mm_vis')")
        ok(v["playing"] and max(v["bands"]) > 0.1 and v["local"], f"спектр под музыку приходит: {[round(x, 2) for x in v['bands']]}")
        from PIL import Image
        im = Image.open(io.BytesIO(pg.locator("#mm-now").screenshot())).convert("RGB")
        px = im.getpixel((im.width - 80, im.height - 6)), im.getpixel((im.width // 2, 20))
        ok(px[0] != px[1], f"фон живой (холст рисует свет и столбики): {px}")
        if SHOTS:
            pg.locator("#mm-now").screenshot(path=os.path.join(SHOTS, "music-player.png"))
        pg.evaluate("const s = document.querySelector('#mm-vol'); s.value = 45; s.dispatchEvent(new Event('input')); s.dispatchEvent(new Event('change'))"); time.sleep(1)
        st = json.loads((cfg / "settings.json").read_text())
        ok(st["audio"]["radio_volume"] == 0.45 and pg.inner_text("#mm-volv") == "45%" and pg.evaluate("core.call('mm_vis')")["volume"] == 0.45,
           f"громкость — ползунок, запоминается: {st['audio'].get('radio_volume')}")
        box = pg.locator("#mm-bar i").bounding_box()
        pg.mouse.click(box["x"] + box["width"] * 0.6, box["y"] + box["height"] / 2); time.sleep(2)
        pos = pg.evaluate("core.call('mm_vis')")["pos"]
        ok(23 <= pos <= 28, f"нажали на полосу на 60% — играет с ~24 с: {pos}")
        pg.click("#mm-pp"); time.sleep(1)
        paused = pg.evaluate("core.call('mm_vis')")
        pg.click("#mm-pp"); time.sleep(1.5)
        back = pg.evaluate("core.call('mm_vis')")["pos"]
        ok(paused["pos"] >= 24 and back >= paused["pos"] and back - paused["pos"] < 4, f"пауза → «играть» — с того же места: {paused['pos']} → {back}")
        log = (tmp / "core.log").read_text(encoding="utf-8", errors="replace")
        ok("с 2" in log, "в журнале — «с N с» (перемотка и продолжение)")
        pg.evaluate("core.call('mm_ctl', { act: 'stop' })")
        ok(not errs, f"без ошибок на странице: {errs[:2]}")
        b.close()
finally:
    core.terminate()
print("ИТОГ:", "все проверки пройдены" if not fails else f"не пройдено {len(fails)}")
sys.exit(1 if fails else 0)
