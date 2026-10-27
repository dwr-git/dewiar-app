"""27.10, YouTube: «Пробовал ставить голоса Денис, Руслан и Дмитрий — они одинаковые». Причина: при голосах Vosk TTS
(по умолчанию) выбор «Голос Piper» в карточке персонажа ничего не менял — Piper звучал, только если Vosk недоступен.
Теперь: выбрали голос Piper — персонаж говорит им («Голос Vosk TTS» сам становится «Всегда Piper»); под полями — что
звучит сейчас; «Послушать» — выбранный голос, а не сохранённый; ядро: у персонажа prefer piper цепочка — Piper."""
import json, os, socket, subprocess, sys, tempfile, time
from pathlib import Path
from types import SimpleNamespace
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


# ядро: голос персонажа «Всегда Piper» при готовом Vosk TTS — звучит Piper с его голосом
sys.path.insert(0, str(ROOT / "core"))
from engine_remote import RemoteMixin  # noqa: E402
piper = SimpleNamespace(has=lambda vid: True)
fake = SimpleNamespace(s=SimpleNamespace(get=lambda *k, **kw: "vosk"), tts_remote=None, piper=piper,
                       vosk_tts=SimpleNamespace(ready=True, error=None), espeak=SimpleNamespace(available=lambda: False))
ok(RemoteMixin._engines_for_speech(fake, {"piper": "ru_RU-ruslan-medium", "prefer": "piper"}) == [piper], "«Всегда Piper» при готовом Vosk — звучит Piper")
ok(RemoteMixin._engines_for_speech(fake, {"piper": "ru_RU-ruslan-medium"}) == [fake.vosk_tts], "без выбора — Vosk, как раньше")

tmp = Path(tempfile.mkdtemp())
LLM, PORT = free(), free()
mock = subprocess.Popen([sys.executable, str(TESTS / "mock_llm.py"), str(LLM)], env=dict(os.environ, MOCK_LOG=str(tmp / "a.log")))
cfg = tmp / "cfg"; cfg.mkdir()
(cfg / "settings.json").write_text(json.dumps({"persona": "lira", "audio": {"sounds": False}, "ui": {"news_seen": "99.0.0", "welcome": "done"},
                                               "stt": {"engine": "vosk"}, "tts": {"engine": "vosk", "v2": True}, "updates": {"auto_check": False},
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
        pg.click('nav button[data-p="personas"]'); time.sleep(0.8)
        pg.locator("#pgrid .card", has_text="Патрик").first.locator(".edit").click(); time.sleep(0.6)
        ok("Vosk TTS" in pg.inner_text("#e-vhint") and pg.input_value("#e-vosk") != "piper", f"сейчас звучит Vosk — так и написано: {pg.inner_text('#e-vhint')!r}")
        pg.select_option("#e-piper", "ru_RU-ruslan-medium"); time.sleep(0.3)
        ok(pg.input_value("#e-vosk") == "piper" and "«Руслан»" in pg.inner_text("#e-vhint"), f"выбрали Руслана — персонаж говорит им: {pg.inner_text('#e-vhint')!r}")
        pg.evaluate("() => { window.__calls = []; const c0 = core.call.bind(core); core.call = (c, a) => { __calls.push([c, a]); return c === 'voice_test' ? Promise.resolve(true) : c0(c, a); }; }")
        pg.click("#e-listen"); time.sleep(0.3)
        vt = pg.evaluate("__calls.filter(x => x[0] === 'voice_test').map(x => x[1].voice)")
        ok(vt and vt[0].get("piper") == "ru_RU-ruslan-medium" and vt[0].get("prefer") == "piper", f"«Послушать» — выбранный голос, не сохранённый: {vt}")
        pg.click("#e-save"); time.sleep(1.0)
        pj = json.loads((cfg / "personas" / "patrik.json").read_text(encoding="utf-8"))
        ok(pj["voice"].get("piper") == "ru_RU-ruslan-medium" and pj["voice"].get("prefer") == "piper", f"сохранено: {pj['voice']}")
        ok(not errs, f"без ошибок на странице: {errs[:2]}")
        b.close()
finally:
    core.terminate(); mock.terminate()

print("ИТОГ:", "все проверки пройдены" if not fails else f"не пройдено {len(fails)}")
sys.exit(1 if fails else 0)
