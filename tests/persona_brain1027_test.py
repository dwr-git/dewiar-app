"""Свой мозг у персонажа (27.10, №346 и отзывы с YouTube: «разным персонажам — разных ИИ: один на GPT, второй на Gemini,
третий на Claude»). Студия → «Персонажи» → «Изменить» → «Мозг»: чипы «Как у всех» и модели из «Мозга»; выбор
сохраняется сразу (llm.persona), на карточке — отметка. Ядро: персонаж со своей моделью думает ею, остальные — общей."""
import json, os, socket, subprocess, sys, tempfile, time
from datetime import datetime, timedelta
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
TESTS = Path(__file__).resolve().parent
PY = os.environ.get("DEWIAR_PY") or sys.executable
SHOTS = os.environ.get("DEWIAR_SHOTS")
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


def free():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


tmp = Path(tempfile.mkdtemp())
LLM, PORT = free(), free()
LLM2 = free()
mock = subprocess.Popen([sys.executable, str(TESTS / "mock_llm.py"), str(LLM)], env=dict(os.environ, MOCK_LOG=str(tmp / "a.log")))
mock2 = subprocess.Popen([sys.executable, str(TESTS / "mock_llm.py"), str(LLM2)], env=dict(os.environ, MOCK_LOG=str(tmp / "b.log")))
cfg = tmp / "cfg"; cfg.mkdir()
(cfg / "settings.json").write_text(json.dumps({"persona": "lira", "audio": {"sounds": False}, "ui": {"news_seen": "99.0.0", "welcome": "done", "memory_motion": "off"},
                                               "stt": {"engine": "vosk"}, "tts": {"engine": "off"},
                                               "llm": {"active": "m", "profiles": {"m": {"name": "Мок", "kind": "openai", "base_url": f"http://127.0.0.1:{LLM}/v1", "model": "mock"}, "c": {"name": "Claude", "kind": "openai", "base_url": f"http://127.0.0.1:{LLM2}/v1", "model": "mock"}}}}))
st = tmp / "st"; st.mkdir()
soon = datetime.now() + timedelta(minutes=50)
if soon.date() != datetime.now().date():
    soon = datetime.now().replace(hour=23, minute=59)
(st / "reminders.json").write_text(json.dumps([{"id": "r1", "text": "позвонить маме", "at": soon.isoformat(timespec="seconds"), "done": False}]), encoding="utf-8")
env = dict(os.environ, DEWIAR_CONFIG_DIR=str(cfg), DEWIAR_STATE_DIR=str(st), DEWIAR_PORT=str(PORT), DEWIAR_ASSUME_AEC="1",
           DEWIAR_WORKSPACE_DIR=str(tmp / "ws"), DEWIAR_FAKE_RAM_GB="16", DEWIAR_FAKE_CORES="8")
core = subprocess.Popen([PY, str(ROOT / "core/main.py"), "--wav", str(TESTS / "silence90.wav"), "--null-audio"], env=env,
                        stdout=open(tmp / "core.log", "w"), stderr=subprocess.STDOUT)
for _ in range(150):
    time.sleep(0.2)
    if (cfg / "token").exists():
        break
time.sleep(2)
tok = (cfg / "token").read_text().strip()
errs = []


async def say(text):
    import websockets
    async with websockets.connect(f"ws://127.0.0.1:{PORT}") as ws:
        await ws.send(json.dumps({"cmd": "hello", "token": tok})); await ws.recv()
        await ws.send(json.dumps({"id": 1, "cmd": "say", "args": {"text": text}}))
        end = time.time() + 20
        while time.time() < end:
            e = json.loads(await asyncio.wait_for(ws.recv(), 20))
            if e.get("type") == "answer" and e.get("done"):
                return e.get("text", "")
    return ""
import asyncio  # noqa: E402
try:
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1400, "height": 1000})
        pg.on("pageerror", lambda e: errs.append("pageerror: " + str(e)))
        pg.goto((ROOT / "ui/settings.html").as_uri() + f"?token={tok}&port={PORT}"); time.sleep(3)
        pg.click('nav button[data-p="personas"]'); time.sleep(0.8)
        card = pg.locator("#pgrid .card", has_text="Патрик").first
        card.locator(".edit").click(); time.sleep(0.6)
        chips = pg.evaluate("[...document.querySelectorAll('#e-brain .bp')].map(b => b.innerText.split('\\n')[0])")
        ok(chips[:3] == ["Как у всех", "Мок", "Claude"] and "Другая модель" in chips[-1], f"«Мозг» в редакторе — общий и модели из «Мозга»: {chips}")
        ok(pg.evaluate("document.querySelector('#e-brain .bp.on').dataset.b") == "", "по умолчанию — «Как у всех»")
        pg.click("#e-brain [data-b='c']"); time.sleep(0.6)
        ok(json.loads((cfg / "settings.json").read_text())["llm"]["persona"].get("patrik") == "c", "выбор сохранён в настройках сразу")
        if SHOTS:
            pg.locator("#drawer").screenshot(path=f"{SHOTS}/persona_brain.png")
        pg.click("#e-x"); time.sleep(0.5)
        ok("Claude" in pg.locator("#pgrid .card", has_text="Патрик").first.inner_text(), "на карточке Патрика — «🧠 Claude»")
        b.close()
    asyncio.run(say("Привет"))                                 # говорит Лира — общий мозг
    a1 = (tmp / "a.log").read_text() if (tmp / "a.log").exists() else ""; b1 = (tmp / "b.log").read_text() if (tmp / "b.log").exists() else ""
    ok("Привет" in a1 and "Привет" not in b1, "Лира думает общим мозгом")
    subprocess.run([sys.executable, "-c", "pass"])
    import websockets  # noqa: E402

    async def setp():
        async with websockets.connect(f"ws://127.0.0.1:{PORT}") as ws:
            await ws.send(json.dumps({"cmd": "hello", "token": tok})); await ws.recv()
            await ws.send(json.dumps({"id": 2, "cmd": "persona_set", "args": {"id": "patrik"}})); await asyncio.sleep(0.5)
    asyncio.run(setp())
    asyncio.run(say("Как дела у Патрика"))
    b1 = (tmp / "b.log").read_text() if (tmp / "b.log").exists() else ""
    ok("Как дела у Патрика" in b1, "Патрик думает своей моделью («Claude»)")
finally:
    core.terminate(); mock.terminate(); mock2.terminate()
ok(not errs, f"без ошибок страницы: {errs[:2]}")
print("ИТОГ:", "OK" if not fails else f"{len(fails)} ошибок")
sys.exit(1 if fails else 0)
