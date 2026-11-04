"""Сквозной тест ядра без микрофона и колонок.
Вместо микрофона — WAV со сценарием, вместо vLLM — mock_llm.py, голос — eSpeak (в тишину).
Проверяет: имя → вопрос → потоковый ответ → озвучка; перебивание другим именем со
сменой персонажа; продолжение разговора без имени; вырезание <think>.
    python3 tests/e2e_voice_test.py /tmp/dewiar-test-audio/scenario.wav"""
import asyncio, json, os, subprocess, sys, tempfile, time
from pathlib import Path
import websockets

ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
PY = os.environ.get("DEWIAR_PY") or sys.executable
TESTS = Path(__file__).resolve().parent
WAV = sys.argv[1]
if os.environ.get("SCENARIO") in ("smart_barge", "half_stop"):   # «хватит» поверх рассказа слышит модель имён Vosk
    sys.path.insert(0, str(TESTS))
    from vosk_have import skip_without_vosk
    skip_without_vosk(ROOT)
PORT, LLM_PORT = 8799, 8124
tmp = Path(tempfile.mkdtemp())
(tmp / "cfg").mkdir()
(tmp / "cfg/settings.json").write_text(json.dumps({
    "llm": {"active": "t", "profiles": {"t": {"name": "Mock vLLM", "kind": "openai",
            "base_url": f"http://127.0.0.1:{LLM_PORT}/v1", "disable_thinking": True}}},
    "stt": {"engine": "remote", "remote": {"base_url": f"http://127.0.0.1:{LLM_PORT}/v1"}}, "tts": {"engine": "espeak"}, "audio": {"sounds": False}}))
# имени «Девиар» нет в словаре Vosk — им и проверяем узнавание имён без словаря (свой персонаж; главный — «Агент»)
(tmp / "cfg/personas").mkdir(parents=True, exist_ok=True)
(tmp / "cfg/personas/deviar.json").write_text(json.dumps({"name": "Девиар", "gender": "male", "wake": ["девиар"], "style": "nexus",
    "character": "Тебя зовут Девиар. Ты внимательный помощник."}, ensure_ascii=False), encoding="utf-8")
env = dict(os.environ, DEWIAR_CONFIG_DIR=str(tmp / "cfg"), DEWIAR_STATE_DIR=str(tmp / "state"),
           DEWIAR_PORT=str(PORT), DEWIAR_ASSUME_AEC="0" if os.environ.get("SCENARIO") == "half_stop" else "1")
# Что «распознает» сервер для каждой фразы сценария (по порядку). Сценарий:
#   фоновая фраза без имени → «Девиар, …» (имени нет в словаре Vosk — ловит точная модель) →
#   «Патрик, расскажи историю» → посреди рассказа «Лира, привет» → «как дела» без имени →
#   снова история Патрика → посреди неё «Девиар, привет» (перебивание фирменным именем).
SCRIPT = ["Игра была отличной.", "Девиар, сколько будет два плюс два?", "Патрик, расскажи историю.", "Лира, привет!",
          "Как дела?", "Патрик, расскажи историю.", "Девиар, привет!"]
if os.environ.get("SCENARIO") == "classic":
    SCRIPT = ["Патрик, сколько будет два плюс два?", "Патрик, расскажи историю.", "Лира, привет!", "Как дела?"]
if os.environ.get("SCENARIO") == "long_barge":
    # перебивание речью случается раньше проверки имени, поэтому распознаётся одна целая фраза
    SCRIPT = ["Патрик, расскажи историю.", "Девиар, подожди, расскажи лучше про космос и звёзды."]
if os.environ.get("SCENARIO") == "smart_barge":
    SCRIPT = ["Патрик, расскажи историю.", "Патрик, расскажи историю.", "Подожди, лучше расскажи про космос."]
if os.environ.get("SCENARIO") == "half_stop":      # без эхоподавления: «хватит» поверх рассказа всё равно слышно
    SCRIPT = ["Патрик, расскажи историю.", "Патрик, расскажи историю.", "Подожди, лучше расскажи про космос."]
# Разговор общий: ответы других персонажей приходят модели в истории. Заглушка повторяет только последнюю реплику —
# иначе ответ Лиры растягивается на всю историю и «как дела» попадает на её речь.
mock = subprocess.Popen([sys.executable, str(TESTS / "mock_llm.py"), str(LLM_PORT)] + SCRIPT, env=dict(os.environ, MOCK_ECHO_LAST="1"))
core = subprocess.Popen([PY, str(ROOT / "core/main.py"), "--wav", WAV, "--null-audio"], env=env,
                        stdout=open(tmp / "core.log", "w"), stderr=subprocess.STDOUT)
events = []

async def run():
    token = None
    for _ in range(100):
        await asyncio.sleep(0.2)
        tp = tmp / "cfg/token"
        if tp.exists():
            token = tp.read_text().strip()
            try:
                ws = await websockets.connect(f"ws://127.0.0.1:{PORT}")
                break
            except OSError:
                continue
    await ws.send(json.dumps({"cmd": "hello", "token": token}))
    t0 = time.monotonic()
    async for raw in ws:
        e = json.loads(raw); e["t"] = round(time.monotonic() - t0, 2)
        if e["type"] != "level":
            events.append(e)
        if e["type"] == "eof" or time.monotonic() - t0 > 120:
            break

try:
    asyncio.run(run())
except Exception as e:  # noqa: BLE001
    print("соединение с ядром оборвалось:", e)
finally:
    core.terminate(); mock.terminate(); core.wait(); mock.wait()

log = (tmp / "core.log").read_text()
print(log[-3500:])
print("---- события ----")
for e in events:
    if e["type"] in ("state", "heard", "interrupted", "persona", "error", "wake") or (e["type"] == "answer" and e.get("done")):
        print(e["t"], e["type"], {k: v for k, v in e.items() if k not in ("type", "t", "status", "personas", "settings")})
answers = [e["text"] for e in events if e["type"] == "answer" and e.get("done")]
checks = {
    "фоновая фраза без имени проигнорирована": not any("игра" in a.lower() for a in answers),
    # «сколько будет два плюс два» теперь считает сам помощник, без модели (quickmath) — ответ «2 плюс 2 — будет 4»
    "«Девиар» услышан без словаря Vosk": any((a.startswith("Я Девиар") and "два плюс два" in a) or "будет 4" in a for a in answers),
    "think вырезан": all("надо ответить" not in a for a in answers),
    "звучал голос (speaking)": any(e["type"] == "state" and e["state"] == "speaking" for e in events),
    "перебивание сработало": any(e["type"] == "interrupted" for e in events),
    "переключились на Лиру": any(e["type"] == "persona" and e["persona"] == "lira" for e in events),
    "Лира ответила": any(a.startswith("Я Лира") for a in answers),
    "продолжение без имени": any("как дела" in a.lower() for a in answers),
    "Девиар перебил Патрика": sum(e["type"] == "interrupted" for e in events) >= 2 and answers[-1].startswith("Я Девиар") and "привет" in answers[-1],
}
if os.environ.get("SCENARIO") == "classic":
    checks = {k: v for k, v in checks.items() if "Девиар" not in k}
    checks["Патрик ответил"] = any((a.startswith("Я Патрик") and "два плюс два" in a) or "будет 4" in a for a in answers)
if os.environ.get("SCENARIO") == "long_barge":
    t_int = next((e["t"] for e in events if e["type"] == "interrupted"), None)
    t_think = next((e["t"] for e in events if e["type"] == "heard" and "космос" in e.get("text", "")), None)
    print("перебил на", t_int, "с; фраза распознана на", t_think, "с")
    checks = {"замолчал раньше, чем вы договорили": t_int is not None and t_think is not None and t_int < t_think - 1.0,
              "ответил на всю фразу": any("космос" in a for a in answers) and answers[-1].startswith("Я Девиар")}
if os.environ.get("SCENARIO") == "smart_barge":
    ints = [e for e in events if e["type"] == "interrupted"]
    t_stop = next((e["t"] for e in ints if e.get("reason") in ("хватит", "стоп")), None)
    t_speech = next((e["t"] for e in ints if e.get("reason") == "речь"), None)
    after_stop = [e for e in events if e["type"] == "answer" and e.get("done") and t_stop and t_stop < e["t"] < t_stop + 5]
    print("«хватит» на", t_stop, "с; перебит речью на", t_speech, "с")
    checks = {"«хватит» остановило рассказ": t_stop is not None,
              "после «хватит» — тишина, без нового ответа": t_stop is not None and not after_stop,
              "перебил просто речью, без имени": t_speech is not None and (t_stop is None or t_speech > t_stop),
              "ответил на сказанное поверх ответа": any("космос" in a for a in answers) and answers[-1].startswith("Я Патрик")}
if os.environ.get("SCENARIO") == "half_stop":
    ints = [e for e in events if e["type"] == "interrupted"]
    t_stop = next((e["t"] for e in ints if e.get("reason") in ("хватит", "стоп")), None)
    after_stop = [e for e in events if e["type"] == "answer" and e.get("done") and t_stop and t_stop < e["t"] < t_stop + 5]
    log = (tmp / "core.log").read_text(encoding="utf-8", errors="replace")
    print("«хватит» на", t_stop, "с")
    checks = {"без эхоподавления: «хватит» остановило рассказ": t_stop is not None and "без эхоподавления" in log,
              "после «хватит» — тишина": t_stop is not None and not after_stop,
              "режим действительно без эхоподавления": "эхоподавление: нет" in log}
for k, v in checks.items():
    print(("✅" if v else "❌"), k)
sys.exit(0 if all(checks.values()) else 1)
