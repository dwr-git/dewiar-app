"""YouTube 26.10: «Выключил микрофон и синтез речи, свернул виджет в трей… она стала вызывать инструмент, и виджет
развернулся с подтверждением… текста было много и он мелкий… в чате не было информации о выполнении команды… добавить
переключение в текстовый режим (без распознавания, без синтеза, с инструментами в чате)». И: llama.cpp с долгим разбором
вопроса — «Dewiar прерывал генерацию». Студия → «Чат»:
- «Текстовый режим»: микрофон выключен, голос выключен (прежний запомнен и возвращается), виджет на «Выполнить?» не
  выскакивает — открывается «Чат»;
- «Выполнить?» — карточкой в ленте (крупно, кнопки «Выполнить / Не надо»), ответ закрывает вопрос;
- под ответом — что сделано за ход: ✓ / ✕ и «Разрешение: … — отказано»; это сохраняется в ленте;
- своя модель на этом компьютере — первое слово ждём до 10 минут (облако — 3)."""
import asyncio, json, os, socket, subprocess, sys, tempfile, time
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
TESTS = Path(__file__).resolve().parent
PY = os.environ.get("DEWIAR_PY") or sys.executable
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


def free():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


sys.path.insert(0, str(ROOT / "core"))
import llm  # noqa: E402
ok(llm._local_base("http://127.0.0.1:8080/v1") and llm._local_base("http://192.168.1.20:11434") and not llm._local_base("https://openrouter.ai/api/v1"),
   "своя модель (этот компьютер, своя сеть) узнаётся по адресу")
src = (ROOT / "core/llm.py").read_text(encoding="utf-8")
ok("600 if _local_base(base) else 180" in src, "своей модели — до 10 минут на первое слово")

tmp = Path(tempfile.mkdtemp())
LLM, PORT = free(), free()
mock = subprocess.Popen([sys.executable, str(TESTS / "mock_llm.py"), str(LLM)], env=dict(os.environ, MOCK_LOG=str(tmp / "a.log")))
cfg = tmp / "cfg"; cfg.mkdir()
(cfg / "settings.json").write_text(json.dumps({"persona": "lira", "audio": {"sounds": False}, "ui": {"news_seen": "99.0.0", "welcome": "done"},
                                               "stt": {"engine": "vosk"}, "tts": {"engine": "piper", "v2": True}, "updates": {"auto_check": False},
                                               "llm": {"active": "m", "profiles": {"m": {"name": "Мок", "kind": "openai", "base_url": f"http://127.0.0.1:{LLM}/v1", "model": "mock"}}}}))
env = dict(os.environ, DEWIAR_CONFIG_DIR=str(cfg), DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_PORT=str(PORT), DEWIAR_ASSUME_AEC="1",
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
try:
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1400, "height": 1000})
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto((ROOT / "ui/settings.html").as_uri() + f"?token={tok}&port={PORT}"); time.sleep(3)
        pg.click('nav button[data-p="chat"]'); time.sleep(0.8)
        ok(pg.is_visible("label.ch-tm") and not pg.is_checked("#ch-tm"), "в «Чате» — переключатель «Текстовый режим»")
        pg.click("label.ch-tm"); time.sleep(1.0)
        st = json.loads((cfg / "settings.json").read_text())
        ok(st["ui"].get("text_mode") is True and st["tts"]["engine"] == "off" and st["ui"].get("text_prev") == "piper",
           f"включили — голос выключен, прежний запомнен: {st['tts']['engine']}, {st['ui'].get('text_prev')}")
        pg.fill("#ch-text", "выполни команду, покажи файлы"); pg.keyboard.press("Enter")
        for _ in range(40):
            time.sleep(0.25)
            if pg.is_visible("#ch-ask"):
                break
        ok(pg.is_visible("#ch-ask") and "Выполнить" in pg.inner_text("#ch-ask"), f"«Выполнить?» — карточкой в ленте: {pg.inner_text('#ch-ask')[:120]!r}")
        if os.environ.get("DEWIAR_SHOTS"):
            pg.locator("#ch-box").screenshot(path=os.environ["DEWIAR_SHOTS"] + "/textmode-ask.png")
        fs = pg.evaluate("parseFloat(getComputedStyle(document.querySelector('#ch-ask .q')).fontSize)")
        ok(fs >= 15, f"вопрос — крупным текстом ({fs}px)")
        pg.click("#ch-ask [data-a='no']")
        for _ in range(40):
            time.sleep(0.25)
            if "отказано" in pg.inner_text("#ch-msgs"):
                break
        ok(not pg.is_visible("#ch-ask"), "ответили — вопрос закрылся")
        if os.environ.get("DEWIAR_SHOTS"):
            pg.locator("#ch-box").screenshot(path=os.environ["DEWIAR_SHOTS"] + "/textmode-steps.png")
        ok("отказано" in pg.inner_text("#ch-msgs"), f"в ленте — «Разрешение на … — отказано»: {pg.inner_text('#ch-msgs')[-300:]!r}")
        log = [json.loads(x) for x in (tmp / "st" / "chat.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
        last = [x for x in log if x["role"] == "assistant"][-1]
        ok(any(s.get("s") == "no" and s["t"].startswith("Разрешение на «") for s in last.get("steps", [])), f"шаги хода сохранены в ленте: {last.get('steps')}")
        pg.reload(); time.sleep(3); pg.click('nav button[data-p="chat"]'); time.sleep(1.0)
        ok(pg.is_checked("#ch-tm") and "отказано" in pg.inner_text("#ch-msgs"), "после перезапуска студии — режим включён, шаги на месте")
        pg.click("label.ch-tm"); time.sleep(1.0)
        st = json.loads((cfg / "settings.json").read_text())
        ok(st["ui"].get("text_mode") is False and st["tts"]["engine"] == "piper", f"выключили — голос вернулся: {st['tts']['engine']}")
        ok(not errs, f"без ошибок на странице: {errs[:2]}")
        b.close()
    hud = (ROOT / "ui/hud.html").read_text(encoding="utf-8")
    ok("askInChat()" in hud and 'a.open_settings("chat")' in hud and "if (!TEXT_MODE) popUp();" in hud, "виджет: в текстовом режиме «Выполнить?» открывает «Чат», сам не выскакивает")
finally:
    core.terminate(); mock.terminate()

print("ИТОГ:", "все проверки пройдены" if not fails else f"не пройдено {len(fails)}")
sys.exit(1 if fails else 0)
