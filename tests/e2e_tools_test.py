"""Сквозной тест «Рук» (этап 4): модель вызывает инструменты, ядро их выполняет.
Программы не запускаются — DEWIAR_DRY_TOOLS пишет команды в файл.
    python3 tests/e2e_tools_test.py [/tmp/dewiar-test-audio/tools.wav]   (WAV: тишина + «да, выполняй» на 12-й секунде;
    без аргумента — этот файл, его сделает tests/make_audio.py)"""
import asyncio, json, os, subprocess, sys, tempfile, time
from pathlib import Path
import websockets
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
PY = os.environ.get("DEWIAR_PY") or sys.executable
TESTS = Path(__file__).resolve().parent
PORT, LLM_PORT = 8796, 8126
tmp = Path(tempfile.mkdtemp()); (tmp / "cfg").mkdir()
dry = tmp / "launched.jsonl"
(tmp / "cfg/settings.json").write_text(json.dumps({
    "persona": "dewiar",
    "llm": {"active": "t", "profiles": {"t": {"name": "Mock", "kind": "openai", "base_url": f"http://127.0.0.1:{LLM_PORT}/v1"}}},
    "stt": {"engine": "remote", "remote": {"base_url": f"http://127.0.0.1:{LLM_PORT}/v1"}}, "tts": {"engine": "espeak"},
    "audio": {"sounds": False, "follow_up_seconds": 0},
    "tools": {"enabled": {"run_command": True}, "search_url": f"http://127.0.0.1:{LLM_PORT}"}}))
env = dict(os.environ, DEWIAR_CONFIG_DIR=str(tmp / "cfg"), DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_PORT=str(PORT),
           DEWIAR_ASSUME_AEC="1", DEWIAR_DRY_TOOLS=str(dry), DEWIAR_WORKSPACE=str(tmp / "ws"))
mock = subprocess.Popen([sys.executable, str(TESTS / "mock_llm.py"), str(LLM_PORT), "Да, выполняй."])
# без аргумента — тот же файл, что даёт run_all.sh ($DEWIAR_TEST_AUDIO/tools.wav); нет его — сделаем (make_audio.py)
WAV = sys.argv[1] if len(sys.argv) > 1 else str(Path(os.environ.get("DEWIAR_TEST_AUDIO", "/tmp/dewiar-test-audio")) / "tools.wav")
if not Path(WAV).exists():
    subprocess.run([sys.executable, str(TESTS / "make_audio.py")], check=True, stdout=subprocess.DEVNULL)
core = subprocess.Popen([PY, str(ROOT / "core/main.py"), "--wav", WAV, "--null-audio"], env=env,
                        stdout=open(tmp / "core.log", "w"), stderr=subprocess.STDOUT)
events = []

async def run():
    for _ in range(100):
        await asyncio.sleep(0.2)
        if (tmp / "cfg/token").exists():
            try:
                ws = await websockets.connect(f"ws://127.0.0.1:{PORT}"); break
            except OSError:
                continue
    await ws.send(json.dumps({"cmd": "hello", "token": (tmp / "cfg/token").read_text().strip()}))
    t0 = time.monotonic(); n = [0]
    async def say(text):
        n[0] += 1; await ws.send(json.dumps({"id": n[0], "cmd": "say", "args": {"text": text}}))
    async def wait_for(pred, limit):
        end = time.monotonic() + limit
        while time.monotonic() < end:
            if any(pred(e) for e in events): return True
            await asyncio.sleep(0.1)
        return False
    async def reader():
        async for raw in ws:
            e = json.loads(raw); e["t"] = round(time.monotonic() - t0, 2)
            if e["type"] != "level": events.append(e)
    rd = asyncio.ensure_future(reader())
    await wait_for(lambda e: e["type"] == "status" and e["status"].get("input"), 20)   # микрофон (WAV) открыт
    await say("Открой ютуб")
    await wait_for(lambda e: e["type"] == "answer" and e.get("done") and "Готово" in e["text"], 15)
    await say("Найди погоду в Москве на завтра")
    await wait_for(lambda e: e["type"] == "answer" and e.get("done") and "Погода" in e["text"], 15)
    await say("Выполни команду")                      # подтверждение — голосом («да, выполняй» в WAV)
    await wait_for(lambda e: e["type"] == "confirm_done", 25)
    await wait_for(lambda e: e["type"] == "answer" and e.get("done") and "тест" in e["text"], 15)
    n0 = sum(e["type"] == "confirm" for e in events)
    await say("Выполни команду ещё раз")              # отказ — кнопкой в виджете
    await wait_for(lambda e: sum(x["type"] == "confirm" for x in events) > n0, 15)
    n[0] += 1; await ws.send(json.dumps({"id": n[0], "cmd": "confirm_answer", "args": {"ok": False}}))
    await wait_for(lambda e: e["type"] == "tool" and e.get("status") == "declined", 10)
    await asyncio.sleep(3)
    await say("Напомни через три секунды про чайник")
    await wait_for(lambda e: e["type"] == "reminder", 20)
    await wait_for(lambda e: e["type"] == "answer" and "Напоминание:" in e.get("text", ""), 15)
    await say("Запиши список покупок")
    await wait_for(lambda e: e["type"] == "answer" and e.get("done") and "Покупки" in e["text"], 15)
    await say("Позови Лиру")
    await wait_for(lambda e: e["type"] == "persona" and e.get("persona") == "lira", 15)
    await wait_for(lambda e: e["type"] == "answer" and e.get("done") and "Я Лира" in e["text"], 15)
    rd.cancel()

try:
    asyncio.run(run())
finally:
    core.terminate(); mock.terminate(); core.wait(); mock.wait()
log = (tmp / "core.log").read_text()
print(log[log.find("Traceback"):][:1500] if "Traceback" in log else "")
launched = [json.loads(l) for l in dry.read_text().splitlines()] if dry.exists() else []
print("запущено:", launched); print("ОТВЕТЫ:", [e["text"][:90] for e in events if e["type"] == "answer" and e.get("done")][-3:])
answers = [e["text"] for e in events if e["type"] == "answer" and e.get("done")]
checks = {
    "открыл YouTube в браузере": ["xdg-open", "https://youtube.com"] in launched,
    "нашёл в интернете и ответил по результату": any("Погода в Москве" in a for a in answers),
    "спросил подтверждение перед командой": any(e["type"] == "confirm" and "ls ~" in e["text"] for e in events),
    "выполнил после голосового «да»": ["bash", "-lc", "ls ~"] in launched,
    "не выполнил после отказа кнопкой": launched.count(["bash", "-lc", "ls ~"]) == 1 and any(e["type"] == "tool" and e.get("status") == "declined" for e in events),
    "напоминание сработало и прозвучало": any(e["type"] == "reminder" for e in events) and any("Напоминание: Про чайник" in a or "Напоминание: проверить чайник" in a for a in answers),
    "«запиши…»: заметка в папке ассистента": (tmp / "ws/Заметки/Покупки.md").exists() and "молоко" in (tmp / "ws/Заметки/Покупки.md").read_text(),
    "папка создана, напоминания в Напоминания.md": (tmp / "ws/Напоминания.md").exists() and (tmp / "ws/Память/Обо мне.md").exists(),
    "«позови Лиру»: сменился персонаж": any(e["type"] == "persona" and e.get("persona") == "lira" for e in events),
    "Лира откликнулась сама, без «Вы: …» в виджете": any(e["type"] == "answer" and e.get("done") and "Я Лира" in e["text"] for e in events)
        and not any(e["type"] == "heard" and "позвал" in e.get("text", "") for e in events),
    "в виджет шли события инструментов": any(e["type"] == "tool" and e.get("status") == "done" for e in events),
}
for k, v in checks.items(): print(("✅" if v else "❌"), k)
sys.exit(0 if all(checks.values()) else 1)
