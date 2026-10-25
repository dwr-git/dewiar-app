"""«Главная» → «Последний разговор»: имя того, кто ответил (отчёт 256, 25.10: ответ Патрика подписан «Лира»).
personas в студии — «let» из core.js, на window её нет; hmWho смотрел window.personas и всегда падал в «Лира»."""
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
(cfg / "settings.json").write_text(json.dumps({"persona": "patrik", "audio": {"sounds": False}, "ui": {"news_seen": "99.0.0", "welcome": "done", "memory_motion": "off"},
                                               "stt": {"engine": "vosk"}, "tts": {"engine": "off"},
                                               "llm": {"active": "m", "profiles": {"m": {"name": "Мок", "kind": "openai", "base_url": f"http://127.0.0.1:{LLM}/v1", "model": "mock"}}}}))
st = tmp / "st"; st.mkdir()
soon = datetime.now() + timedelta(minutes=50)
if soon.date() != datetime.now().date():
    soon = datetime.now().replace(hour=23, minute=59)
now = time.time()
(st / "chat.jsonl").write_text(json.dumps({"id": "u1", "ts": now - 60, "role": "user", "text": "Сколько времени?"}, ensure_ascii=False) + "\n" + json.dumps({"id": "a1", "ts": now - 59, "role": "assistant", "text": "Сейчас 17:13.", "who": "patrik"}, ensure_ascii=False) + "\n", encoding="utf-8")
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
        pg.goto((ROOT / "ui/settings.html").as_uri() + f"?token={tok}&port={PORT}"); time.sleep(3.5)
        t = pg.evaluate("(document.querySelector('#hm-chat') || {}).innerText || ''")
        ok("Патрик: Сейчас 17:13" in t, f"ответ подписан Патриком: {t[-60:]!r}")
        ok("Лира:" not in t, "и не Лирой")
        ok(pg.evaluate("hmWho('nobody')") == "Nobody" and pg.evaluate("hmWho('')") == "Патрик", "неизвестный — по имени из id; без id — активный персонаж")
        b.close()
finally:
    core.terminate(); mock.terminate()
ok(not errs, f"без ошибок страницы: {errs[:2]}")
print("ИТОГ:", "OK" if not fails else f"{len(fails)} ошибок")
sys.exit(1 if fails else 0)
