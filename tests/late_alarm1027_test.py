"""№327 (пакет 27.10, Ubuntu): «после включения компьютера постоянно звучит струна и голос „пропущено напоминание“, окна
нет, выключить нельзя». Пропущенные, пока компьютер был выключен, напоминания звенели по 2 минуты, а окно открывал только
виджет, успевший подключиться к ядру до звонка. Теперь опоздавшее — один звонок и одна фраза, дальше тихо ждёт ответа,
и виджет, подключившийся позже, сам открывает окно напоминания (звенящее приходит в «hello»)."""
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
(st / "reminders.json").write_text(json.dumps([{"id": "r1", "text": "полить цветы", "at": (datetime.now() - timedelta(minutes=40)).isoformat(timespec="seconds"), "done": False}]), encoding="utf-8")
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
    end = time.time() + 20
    while time.time() < end and "⏰ полить цветы" not in (tmp / "core.log").read_text(encoding="utf-8", errors="replace"):
        time.sleep(0.3)
    time.sleep(16)                                          # больше 12 с — звонок уже закончился бы, окна всё ещё нет
    log = (tmp / "core.log").read_text(encoding="utf-8", errors="replace")
    ok("⏰ полить цветы" in log, "пропущенное напоминание сработало при запуске")
    ok("отмечено пропущенным" not in log, "через 16 с оно ещё ждёт ответа (не «никто не ответил»)")
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page(viewport={"width": 300, "height": 420})
        pg.on("pageerror", lambda e: errs.append("pageerror: " + str(e)))
        pg.add_init_script("window._shown = []; setTimeout(() => { window.pywebview = { api: { show_alarm: (e) => _shown.push(e) } }; }, 1200);")
        pg.goto((ROOT / "ui/hud.html").as_uri() + f"?token={tok}&port={PORT}&mode=card"); pg.wait_for_timeout(4000)
        shown = pg.evaluate("_shown")
        ok(len(shown) == 1 and shown[0]["id"] == "r1" and shown[0]["late"], f"виджет подключился позже — окно напоминания открыто: {shown}")
        b.close()
    ok(log.count("Пропущенное напоминание") <= 1, "проговорено не больше одного раза")
finally:
    core.terminate(); mock.terminate()
ok(not errs, f"без ошибок страницы: {errs[:2]}")
print("ИТОГ:", "OK" if not fails else f"{len(fails)} ошибок")
sys.exit(1 if fails else 0)
