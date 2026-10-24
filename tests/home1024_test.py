"""Студия: «Главная» (владелец 24.10: «сделать красивую первичную страничку… иконками, как на айфоне… главное иметь
возможность здесь же включить нужное и убрать ненужное… очень стильные красивые иконки»). На живом ядре:
студия открывается «Главной»; значки ведут в свои разделы; «Настроить главную» — скрыть значок и переставить, выбор
сохраняется в ui.home_apps и переживает перезагрузку; «Сегодня» показывает ближайшее дело; Персонажи — в «Настройке»."""
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
mock = subprocess.Popen([sys.executable, str(TESTS / "mock_llm.py"), str(LLM)])
cfg = tmp / "cfg"; cfg.mkdir()
(cfg / "settings.json").write_text(json.dumps({"persona": "lira", "audio": {"sounds": False}, "ui": {"news_seen": "99.0.0", "welcome": "done", "memory_motion": "off"},
                                               "stt": {"engine": "vosk"}, "tts": {"engine": "off"},
                                               "llm": {"active": "m", "profiles": {"m": {"name": "Мок", "kind": "openai", "base_url": f"http://127.0.0.1:{LLM}/v1", "model": "mock"}}}}))
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
try:
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1400, "height": 1000})
        pg.on("pageerror", lambda e: errs.append("pageerror: " + str(e)))
        url = (ROOT / "ui/settings.html").as_uri() + f"?token={tok}&port={PORT}"
        pg.goto(url); time.sleep(3)
        ok(pg.evaluate("document.querySelector('section.cur') && document.querySelector('section.cur').id") == "p-home",
           "студия открывается «Главной»")
        ok(pg.evaluate("document.querySelector('nav button.cur') && document.querySelector('nav button.cur').dataset.p") == "home", "в меню выделена «Главная»")
        apps = pg.evaluate("[...document.querySelectorAll('#hm-apps .hm-app')].map(a => a.dataset.app)")
        ok(len(apps) >= 8 and "chat" in apps and "play" in apps and "close" in apps and "ref" not in apps, f"значки приложений (Рефералы — только по желанию): {apps}")
        ok(pg.evaluate("[...document.querySelectorAll('#hm-apps .hm-ic svg')].length") == len(apps), "у каждого значка — рисунок")
        today = pg.evaluate("document.querySelector('#hm-today').innerText")
        ok("позвонить маме" in today, f"«Сегодня» — ближайшее дело: {today[:120]!r}")
        nav = pg.evaluate("[...document.querySelectorAll('nav > *')].map(x => x.dataset.p || ('#' + x.textContent.trim()))")
        ok(nav.index("personas") > nav.index("#Настройка") and nav.index("brain") > nav.index("#Настройка"), f"Персонажи — в «Настройке»: {nav[:14]}")
        if SHOTS:
            pg.screenshot(path=f"{SHOTS}/home.png")
        # значок ведёт в раздел
        pg.click("#hm-apps .hm-app[data-app='notes'] .hm-ic"); time.sleep(0.6)
        ok(pg.evaluate("document.querySelector('section.cur').id") == "p-notes", "значок «Заметки» открывает заметки")
        pg.click("nav button[data-p='home']"); time.sleep(0.8)
        # настроить: скрыть «Блокнот», показать «Рефералы» (по умолчанию скрыт), переставить «Досуг» в начало
        pg.click("#hm-edit"); time.sleep(0.3)
        ok(pg.evaluate("document.querySelector('#hm-apps').classList.contains('edit')"), "«Настроить главную» — режим правки")
        ok(not pg.evaluate("document.querySelector('[data-tg=ref]').checked") and pg.evaluate("document.querySelector('[data-tg=pad]').checked"),
           "в правке видны и скрытые значки (выключены)")
        pg.click("#hm-apps .hm-app[data-app='pad'] .hm-tg"); time.sleep(0.3)
        pg.click("#hm-apps .hm-app[data-app='ref'] .hm-tg"); time.sleep(0.3)
        pg.drag_and_drop("#hm-apps .hm-app[data-app='play']", "#hm-apps .hm-app[data-app='chat']"); time.sleep(0.3)
        pg.click("#hm-edit"); time.sleep(1.2)
        saved = json.loads((cfg / "settings.json").read_text(encoding="utf-8"))["ui"].get("home_apps")
        ok(isinstance(saved, list) and "pad" not in saved and "ref" in saved and saved.index("play") < saved.index("chat"),
           f"выбор сохранён в ui.home_apps: {saved}")
        shown = pg.evaluate("[...document.querySelectorAll('#hm-apps .hm-app')].map(a => a.dataset.app)")
        ok("pad" not in shown and "ref" in shown and shown.index("play") < shown.index("chat"), f"после правки — «Блокнот» скрыт, «Рефералы» есть, «Досуг» перед «Чатом»: {shown}")
        pg.reload(); time.sleep(3)
        again = pg.evaluate("[...document.querySelectorAll('#hm-apps .hm-app')].map(a => a.dataset.app)")
        ok(again == shown, f"после перезагрузки — так же: {again}")
        ok(pg.evaluate("document.querySelectorAll('#hm-set .hm-pill').length") >= 4, "внизу — ссылки на настройки")
        pg.set_viewport_size({"width": 760, "height": 900}); time.sleep(0.4)
        ok(pg.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), "узкое окно — без прокрутки вбок")
        b.close()
finally:
    core.terminate(); mock.terminate()
    try:
        core.wait(10)
    except subprocess.TimeoutExpired:
        core.kill()
ok(not errs, f"без ошибок JavaScript: {errs[:3]}")
print("\nИТОГ:", "все проверки прошли" if not fails else f"не прошло {len(fails)}")
sys.exit(1 if fails else 0)
