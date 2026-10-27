"""Студия 0.47: «Обо мне» — память по людям и темам (поиск по смыслу, «×» забыть, «Запомнить»), «Музыка» — своя папка
(выбрать, счётчики, подборки, играть, ♥). Настоящее ядро без звука; разговор с моком: старый факт о маме приходит к
вопросу в справке «Из памяти», хотя в подсказку целиком память уже не влезает."""
import asyncio
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
TESTS = ROOT / "tests"
SHOTS = os.environ.get("DEWIAR_SHOTS")
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


def free():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


tmp = Path(tempfile.mkdtemp())
mus = tmp / "Музыка"
(mus / "Кино").mkdir(parents=True)
FF = shutil.which("ffmpeg")
for name, meta in (("Кино/01.mp3", {"title": "Звезда по имени Солнце", "artist": "Кино", "genre": "Русский рок", "date": "1989", "album": "Звезда по имени Солнце"}),
                   ("Кино/02.mp3", {"title": "Группа крови", "artist": "Кино", "genre": "Русский рок", "date": "1988", "album": "Группа крови"}),
                   ("clair.flac", {"TITLE": "Clair de lune", "ARTIST": "Debussy", "GENRE": "Classical"})):
    subprocess.run([FF, "-loglevel", "error", "-y", "-f", "lavfi", "-i", "sine=f=440:d=2",
                    *sum([["-metadata", f"{k}={v}"] for k, v in meta.items()], []), str(mus / name)], check=True)
ws = tmp / "ws"
(ws / "Память").mkdir(parents=True)
facts = ["Меня зовут Михаил, живу в Минске _(01.03.2026)_", "У мамы день рождения 14 ноября _(04.03.2026)_",
         "Мама Людмила любит пионы, не любит лилии _(05.03.2026)_", "Мама живёт в Гродно (раньше: в Лиде; менялось 1 раз). _(06.06.2026)_",
         "Дочь Маша, 7 лет _(02.03.2026)_", "Люблю короткие ответы _(08.03.2026)_"]
facts += [f"Отчёт для клиента номер {i} сдан вовремя, заказчик доволен работой _(1{i % 9}.04.2026)_" for i in range(60)]
(ws / "Память" / "Обо мне.md").write_text("# Обо мне\n\nЧто ассистент знает о вас.\n\n" + "".join(f"- {f}\n" for f in facts), encoding="utf-8")

LLM, PORT = free(), free()
mock = subprocess.Popen([sys.executable, str(TESTS / "mock_llm.py"), str(LLM)], env=dict(os.environ, MOCK_LOG=str(tmp / "mock.log")))
cfg = tmp / "cfg"; cfg.mkdir()
(cfg / "settings.json").write_text(json.dumps({"persona": "lira", "audio": {"sounds": False}, "ui": {"news_seen": "99.0.0", "welcome": "done"},
    "stt": {"engine": "vosk"}, "tts": {"engine": "off"}, "updates": {"auto_check": False}, "workspace": {"dir": str(ws)},
    "llm": {"active": "m", "profiles": {"m": {"name": "Мок", "kind": "openai", "base_url": f"http://127.0.0.1:{LLM}/v1", "model": "mock"}}}}))
env = dict(os.environ, DEWIAR_CONFIG_DIR=str(cfg), DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_PORT=str(PORT), DEWIAR_ASSUME_AEC="1",
           DEWIAR_WORKSPACE_DIR=str(ws))
core = subprocess.Popen([sys.executable, str(ROOT / "core/main.py"), "--wav", str(TESTS / "silence90.wav"), "--null-audio"], env=env,
                        stdout=open(tmp / "core.log", "w"), stderr=subprocess.STDOUT)
for _ in range(150):
    time.sleep(0.2)
    if (cfg / "token").exists():
        break
time.sleep(2); tok = (cfg / "token").read_text().strip()
R = {}


async def go():
    import websockets
    async with websockets.connect(f"ws://127.0.0.1:{PORT}", max_size=None) as w:
        await w.send(json.dumps({"cmd": "hello", "token": tok}))
        n = [0]

        async def call(cmd, **a):
            n[0] += 1; i = n[0]
            await w.send(json.dumps({"id": i, "cmd": cmd, "args": a}))
            while True:
                m = json.loads(await asyncio.wait_for(w.recv(), 60))
                if m.get("type") == "reply" and m.get("id") == i:
                    return m.get("data") if m.get("ok", True) else {"_error": m.get("error")}
        R["view"] = await call("memory_view")
        await call("say", text="Что подарить маме?")
        for _ in range(60):
            await asyncio.sleep(0.5)
            if (tmp / "mock.log").exists() and "подарить" in (tmp / "mock.log").read_text(encoding="utf-8", errors="replace"):
                break
        await asyncio.sleep(1.5)
        R["ctx"] = await call("ctx_view")
asyncio.run(go())
try:
    v = R["view"]
    titles = [p["title"] for p in v["pages"]]
    ok(not v["fits"] and v["total"] == 66 and "Мама" in titles and "Маша, дочь" in titles, f"память большая: страницы {titles[:5]}…")
    log = (tmp / "mock.log").read_text(encoding="utf-8", errors="replace") if (tmp / "mock.log").exists() else ""
    ok("Из памяти о пользователе" in log and "пионы" in log, "к вопросу «что подарить маме» — справка «Из памяти» с пионами")
    errs = []
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1400, "height": 1000})
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto((ROOT / "ui/settings.html").as_uri() + f"?token={tok}&port={PORT}"); time.sleep(3)
        pg.evaluate("document.querySelector('nav button[data-p=me]').click()"); time.sleep(1.5)
        pages = pg.evaluate("[...document.querySelectorAll('#mpx-pages .mpx-pg b')].map(x => x.textContent)")
        ok(pages[:2] == ["Обо мне", "Мама"] or ("Мама" in pages and pages[0] == "Обо мне"), f"«Обо мне»: страницы слева {pages[:4]}")
        strip = pg.inner_text("#mpx-strip")
        ok("из 66" in strip and "по смыслу" in strip, f"полоса: главное из 66, остальное по смыслу: «{strip[:120]}»")
        pg.click('#mpx-pages .mpx-pg:has-text("Мама")'); time.sleep(0.5)
        card = pg.inner_text("#mpx-card")
        ok("Мама живёт в Гродно" in card and "сейчас" in card and "Раньше: в Лиде" in card.replace("\n", ""), "страница «Мама»: «сейчас» и прежнее значение")
        if SHOTS:
            pg.screenshot(path=os.path.join(SHOTS, "me-pages.png"))
        pg.fill("#mpx-find", "что подарить маме"); time.sleep(1.0)
        found = pg.inner_text("#mpx-card")
        ok("пионы" in found and "день рождения" in found, "поиск по смыслу — день рождения и пионы")
        pg.fill("#mpx-find", ""); time.sleep(0.6)
        pg.fill("#mpx-new", "Сын Петя учится в третьем классе"); pg.click("#mpx-addgo"); time.sleep(1.2)
        ok("Петя, сын" in pg.inner_text("#mpx-pages"), "«Запомнить» — новая страница «Петя, сын»")
        pg.click('#mpx-pages .mpx-pg:has-text("Петя")'); time.sleep(0.4)
        pg.click("#mpx-card .mpx-del"); time.sleep(0.2)
        ok(pg.inner_text("#mpx-card .mpx-del") == "Забыть?", "«×» — сначала переспросит")
        pg.click("#mpx-card .mpx-del"); time.sleep(1.2)
        ok("Петя" not in pg.inner_text("#mpx-pages") and "Петя" not in (ws / "Память" / "Обо мне.md").read_text(encoding="utf-8"), "второе нажатие — забыл, и в файле тоже")
        pg.click("#mpx-raw"); time.sleep(0.3)
        ok(pg.is_visible("#me-mem") and "Меня зовут Михаил" in pg.input_value("#me-mem"), "«Править текстом» — весь файл, как раньше")

        # ---------- «Музыка» ----------
        pg.click('nav button[data-p="music"]'); time.sleep(1.0)
        ok("Папка не выбрана" in pg.inner_text("#mm-folder") and "Выберите подборку" in pg.inner_text("#mm-np"), "«Музыка» без папки — подсказка выбрать")
        pg.evaluate(f"core.call('mm_folder', {{ folder: {json.dumps(str(mus))} }})"); time.sleep(2.5)
        pg.evaluate("loadMyMusic()"); time.sleep(1.2)
        st = pg.inner_text("#mm-stats")
        ok("3" in st and "трека" in st and "2" in st, f"папка прочитана: {st!r}")
        chips = pg.evaluate("[...document.querySelectorAll('#mm-chips .chip')].map(x => x.textContent)")
        ok(chips[:2] == ["Все треки", "Любимое"] and "Кино" in chips, f"подборки и исполнители: {chips}")
        pg.click('#mm-chips .chip:has-text("Спокойное")'); time.sleep(0.8)
        ok(pg.evaluate("[...document.querySelectorAll('#mm-list .tt b')].map(x => x.textContent)") == ["Clair de lune"], "«Спокойное» — Дебюсси")
        pg.click("#mm-play-all"); time.sleep(1.5)
        ok("Clair de lune" in pg.inner_text("#mm-np") and "Сейчас играет" in pg.inner_text("#mm-np"), "«Играть» — сейчас играет, сверху")
        pg.click("#mm-heart"); time.sleep(0.8)
        ok(pg.evaluate("document.querySelector('#mm-heart').classList.contains('on')"), "♥ — в любимом")
        if SHOTS:
            pg.screenshot(path=os.path.join(SHOTS, "music.png"))
            for sk in ("neu", "neudark"):
                pg.evaluate(f"save({{ ui: {{ skin: '{sk}' }} }}, true)"); time.sleep(0.8)
                pg.goto((ROOT / "ui/settings.html").as_uri() + f"?token={tok}&port={PORT}&skin={sk}"); time.sleep(2.5)
                pg.click('nav button[data-p="music"]'); time.sleep(1.2)
                pg.screenshot(path=os.path.join(SHOTS, f"music-{sk}.png"))
                pg.evaluate("document.querySelector('nav button[data-p=me]').click()"); time.sleep(1.2)
                pg.click('#mpx-pages .mpx-pg:has-text("Мама")'); time.sleep(0.5)
                pg.screenshot(path=os.path.join(SHOTS, f"me-{sk}.png"))
        b.close()
    ok(not errs, f"без ошибок страницы: {errs[:3]}")
finally:
    core.terminate(); mock.terminate()
    try:
        core.wait(10)
    except Exception:  # noqa: BLE001
        core.kill()
print("ИТОГ:", "все проверки пройдены" if not fails else f"не пройдено {len(fails)}")
shutil.rmtree(tmp, ignore_errors=True)
sys.exit(1 if fails else 0)
