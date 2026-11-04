"""Набор исправлений: персонажа зовут без модели, модель без зрения не ломает ответ, скриншот сохраняется файлом,
голос не меняется посреди ответа, отчёт для разработчика."""
import asyncio, base64, io, json, os, queue, subprocess, sys, tempfile, threading, time, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
PY = os.environ.get("DEWIAR_PY") or sys.executable
TESTS = Path(__file__).resolve().parent
tmp = Path(tempfile.mkdtemp())
ok = lambda c, m: print(("✅ " if c else "❌ ") + m)
os.environ["DEWIAR_CONFIG_DIR"] = str(tmp / "cfg0"); os.environ["DEWIAR_STATE_DIR"] = str(tmp / "st0")
os.environ["HOME"] = str(tmp / "home"); (tmp / "home").mkdir()
sys.path.insert(0, str(ROOT / "core"))

# ---------- скриншот файлом ----------
import eyes, tools  # noqa: E401,E402
from PIL import Image  # noqa: E402
b = io.BytesIO(); Image.new("RGB", (64, 40), (30, 60, 90)).save(b, "PNG")
eyes.capture_screen = lambda env: b.getvalue()
tools.pictures_dir = lambda: tmp / "home" / "Изображения"
r = tools.t_save_screenshot({}, {})
shots = list((tmp / "home" / "Изображения" / "Снимки экрана").glob("*.png"))
ok(len(shots) == 1 and shots[0].read_bytes()[:4] == b"\x89PNG" and "сохранён" in r, f"скриншот сохранён файлом: {shots[0].name if shots else '—'}")
ok("save_screenshot" in tools.TOOLS and tools.TOOLS["save_screenshot"][2] == "safe", "инструмент «Скриншот» есть и не требует подтверждения")

# ---------- голос не меняется посреди ответа ----------
import engine as E  # noqa: E402


class FakeTTS:
    def __init__(self, name, fail_on=()):
        self.name, self.fail_on, self.said = name, fail_on, []

    def synth(self, text, voice, speed=1.0):
        if any(f in text for f in self.fail_on):
            raise RuntimeError("не могу")
        self.said.append(text)
        yield 22050, b"\0\0" * 100


class FakePlayer:
    rate = 22050
    def start(self, r): self.rate = r
    def write(self, b): return True
    def finish(self): pass


vosk, piper = FakeTTS("vosk", fail_on=("Nvidia",)), FakeTTS("piper")
me = types.SimpleNamespace(s=types.SimpleNamespace(get=lambda *k: {"speed": 1.0}.get(k[-1])), _voice_cfg=lambda: {}, _output_muted=lambda: False,
                           _fx_name=lambda v: "off", player=FakePlayer(), set_state=lambda s: None,
                           _engines_for_speech=lambda v, force=False: [vosk, piper], _synth_mixed=lambda eng, text, voice, sp: eng.synth(text, voice, sp), _wait_vosk_tts=lambda v: None, last_speak_end=0,
                           _remote_voice_down=lambda eng, e: None, vosk_tts=vosk, _said=[])
turn = types.SimpleNamespace(cancel=threading.Event(), spoken=[])
q = queue.Queue()
for s in ["Привет, это первая фраза.", "Видеокарта Nvidia RTX, вторая фраза.", "И третья фраза."]:
    q.put(s)
q.put(None)
E.Engine._speak_worker(me, turn, q)
ok(not piper.said and len(vosk.said) == 3, f"одним голосом весь ответ (vosk: {len(vosk.said)} фраз, piper: {len(piper.said)})")
vosk2, piper2 = FakeTTS("vosk", fail_on=("Привет",)), FakeTTS("piper")
me._engines_for_speech = lambda v, force=False: [vosk2, piper2]
q = queue.Queue(); [q.put(s) for s in ["Привет!", "Вторая фраза.", None]]
E.Engine._speak_worker(me, turn, q)
ok(len(piper2.said) == 2 and not vosk2.said, "не вышло с первой фразы — весь ответ запасным голосом, без скачков")
# сбой в самом потоке синтеза (не в движке) не вешает голос: фраза закрывается, ход заканчивается (раньше — ждал вечно)
def _boom(eng, e):
    raise AttributeError("сбой потока синтеза")
me._remote_voice_down = _boom
vosk3, piper3 = FakeTTS("vosk", fail_on=("Привет",)), FakeTTS("piper")
me._engines_for_speech = lambda v, force=False: [vosk3, piper3]
q = queue.Queue(); [q.put(s) for s in ["Привет!", "Вторая фраза.", None]]
th = threading.Thread(target=E.Engine._speak_worker, args=(me, turn, q), daemon=True); th.start(); th.join(15)
ok(not th.is_alive(), "сбой в потоке синтеза — голос не зависает, ход заканчивается")
me._remote_voice_down = lambda eng, e: None

# ---------- живое ядро: позвать персонажа, модель без зрения, отчёт ----------
import websockets  # noqa: E402
PORT, LLM_PORT = 8801, 8133
(tmp / "cfg").mkdir()
(tmp / "cfg/personas").mkdir()                       # команда как раньше: Кодер, Джарвис, Эва — добавлены из «Готовых»
for _pid in ['eva', 'jarvis', 'agent']:
    (tmp / "cfg/personas" / f"{_pid}.json").write_text('{"template": true}')
(tmp / "cfg/settings.json").write_text(json.dumps({
    "persona": "dewiar", "stt": {"engine": "vosk"}, "tts": {"engine": "off"}, "audio": {"sounds": False, "follow_up_seconds": 0},
    "llm": {"active": "m", "profiles": {"m": {"name": "mock", "kind": "openai", "base_url": f"http://127.0.0.1:{LLM_PORT}/v1",
                                              "model": "blind", "api_key": "sk-very-secret-4242"}}}}))
env = dict(os.environ, DEWIAR_CONFIG_DIR=str(tmp / "cfg"), DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_PORT=str(PORT), DEWIAR_ASSUME_AEC="1")
sil = TESTS / "silence90.wav"
if not sil.exists():
    import wave
    with wave.open(str(sil), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000); w.writeframes(b"\0\0" * 16000 * 90)
mock = subprocess.Popen([sys.executable, str(TESTS / "mock_llm.py"), str(LLM_PORT)])
core = subprocess.Popen([PY, str(ROOT / "core/main.py"), "--wav", str(sil), "--null-audio"], env=env,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
events, R = [], {}
img = "data:image/png;base64," + base64.b64encode(b.getvalue()).decode()


async def run():
    ws = None
    for _ in range(300):
        await asyncio.sleep(0.2)
        if (tmp / "cfg/token").exists():
            try: ws = await websockets.connect(f"ws://127.0.0.1:{PORT}", max_size=None); break
            except OSError: continue
    await ws.send(json.dumps({"cmd": "hello", "token": (tmp / "cfg/token").read_text().strip()}))
    n = [0]; replies = {}
    async def call(cmd, **args):
        n[0] += 1; i = n[0]; await ws.send(json.dumps({"id": i, "cmd": cmd, "args": args}))
        for _ in range(600):
            if i in replies: return replies.pop(i)
            await asyncio.sleep(0.05)
    async def wait_for(pred, limit):
        end = time.monotonic() + limit
        while time.monotonic() < end:
            if any(pred(e) for e in events): return True
            await asyncio.sleep(0.1)
    async def reader():
        async for raw in ws:
            e = json.loads(raw)
            if e["type"] == "reply": replies[e["id"]] = e
            elif e["type"] != "level": events.append(e)
    rd = asyncio.ensure_future(reader())
    await wait_for(lambda e: e["type"] == "status" and e["status"].get("input"), 60)
    await call("say", text="Позови Лиру")
    R["lira"] = await wait_for(lambda e: e["type"] == "persona" and e.get("persona") == "lira", 10)
    R["greet"] = await wait_for(lambda e: e["type"] == "answer" and e.get("done") and "Лира" in e.get("text", ""), 20)
    events.clear()
    await call("say", text="Дай слово Эве, как дела?")
    R["eva"] = await wait_for(lambda e: e["type"] == "persona" and e.get("persona") == "eva", 10)
    R["eva_q"] = await wait_for(lambda e: e["type"] == "answer" and e.get("done") and "как дела" in e.get("text", ""), 20)
    events.clear()
    await call("say", text="Позови Машу")
    await wait_for(lambda e: e["type"] == "answer" and e.get("done"), 20)
    R["masha"] = not any(e["type"] == "persona" for e in events)
    events.clear()
    await call("say", text="Что на этой картинке?", image=img)
    R["blind"] = await wait_for(lambda e: e["type"] == "answer" and e.get("done") and "Вы сказали" in e.get("text", ""), 30)
    R["blind_err"] = any(e["type"] == "error" for e in events)
    R["report"] = await call("report")
    rd.cancel()

try:
    asyncio.run(run())
finally:
    core.terminate(); mock.terminate(); core.wait(); mock.wait()
ok(R.get("lira"), "«Позови Лиру» — Лира сразу, без модели")
ok(R.get("greet"), "Лира поздоровалась сама")
ok(R.get("eva") and R.get("eva_q"), "«Дай слово Эве, как дела?» — Эва отвечает на вопрос")
ok(R.get("masha"), "«Позови Машу» (не персонаж) — персонаж не меняется")
ok(R.get("blind") and not R.get("blind_err"), "модель без зрения: картинку убрали, ответ есть, ошибки нет")
rep = R.get("report", {})
path = Path(rep.get("data", "")) if rep.get("ok") else None
txt = path.read_text(encoding="utf-8") if path and path.exists() else ""
ok(bool(txt) and "Dewiar" in txt and "== Журнал" in txt and "Лира" in txt, f"отчёт сохранён: {path.name if path else rep}")
ok(txt and "very-secret-4242" not in txt and "***" in txt, "в отчёте нет ключей")
ok("👥" in txt and "⏱" in txt, "в журнале видно: вызов без модели и время ответа")
