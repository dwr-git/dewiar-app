"""Лира держит разговор (24.10, владелец: «попросил обновиться — проверила, обновлений нет; спросил „а теперь“ — ответила
что-то несвязанное. Точно учитывает контекст?»). Проверка на живом ядре: (1) быстрые ответы без модели («Обновись») лежат
в истории, и модель видит их перед следующим вопросом; (2) «а теперь?» / «ещё раз» сразу после быстрой команды — та же
команда ещё раз, а не догадка модели."""
FAILS = []
def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c: FAILS.append(m)
ANS = {}
CTX = {}
import asyncio, json, os, socket, subprocess, sys, tempfile, time
from pathlib import Path
import websockets
ROOT = Path(__file__).resolve().parent.parent; TESTS = ROOT / "tests"
def free():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p
tmp = Path(tempfile.mkdtemp()); LLM, PORT = free(), free(); LOG = tmp / "full.jsonl"
mock = subprocess.Popen([sys.executable, str(TESTS / "mock_llm.py"), str(LLM)], env=dict(os.environ, MOCK_LOG_FULL=str(LOG)))
cfg = tmp / "cfg"; cfg.mkdir()
(cfg / "settings.json").write_text(json.dumps({"persona": "lira", "audio": {"sounds": False}, "ui": {"news_seen": "99.0.0", "welcome": "done"},
    "stt": {"engine": "vosk"}, "tts": {"engine": "off"}, "updates": {"auto_check": False},
    "llm": {"active": "m", "profiles": {"m": {"name": "Мок", "kind": "openai", "base_url": f"http://127.0.0.1:{LLM}/v1", "model": "mock"}}}}))
env = dict(os.environ, DEWIAR_CONFIG_DIR=str(cfg), DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_PORT=str(PORT), DEWIAR_ASSUME_AEC="1",
           DEWIAR_WORKSPACE_DIR=str(tmp / "ws"), DEWIAR_UPDATE_URL="http://127.0.0.1:9/none.json")
core = subprocess.Popen([sys.executable, str(ROOT / "core/main.py"), "--wav", str(TESTS / "silence90.wav"), "--null-audio"], env=env, stdout=open(tmp / "core.log", "w"), stderr=subprocess.STDOUT)
for _ in range(150):
    time.sleep(0.2)
    if (cfg / "token").exists(): break
time.sleep(2); tok = (cfg / "token").read_text().strip()
async def go():
    async with websockets.connect(f"ws://127.0.0.1:{PORT}", max_size=None) as ws:
        await ws.send(json.dumps({"cmd": "hello", "token": tok}))
        n = 0
        async def call(c, **a):
            nonlocal n; n += 1; await ws.send(json.dumps({"id": n, "cmd": c, "args": a}))
        n += 1; await ws.send(json.dumps({"id": n, "cmd": "ctx_view", "args": {}}))
        end = time.time() + 10
        while time.time() < end:
            e = json.loads(await asyncio.wait_for(ws.recv(), 10))
            if e.get("type") == "reply" and e.get("id") == n:
                CTX.update(e.get("data") or {}); break
        for t in ["привет, как дела?", "Обновись", "а теперь?", "расскажи анекдот"]:
            await call("say", text=t); 
            end = time.time() + 15
            while time.time() < end:
                try: e = json.loads(await asyncio.wait_for(ws.recv(), 1))
                except asyncio.TimeoutError: continue
                if e.get("type") == "answer" and e.get("done"): ANS[t] = e.get("text") or ""; break
            await asyncio.sleep(1)
asyncio.run(go())
core.terminate(); mock.terminate()
reqs = [json.loads(l)["messages"] for l in open(LOG, encoding="utf-8")]
upd = ANS.get("Обновись", "")
ok("обновлени" in upd.lower(), f"«Обновись» — быстрый ответ без модели: {upd[:80]!r}")
ok(ANS.get("а теперь?") == upd, f"«а теперь?» сразу после — та же проверка ещё раз: {ANS.get('а теперь?', '')[:80]!r}")
last = reqs[-1] if reqs else []
flat = [(m["role"], str(m["content"])) for m in last]
ok(any(r == "user" and c.strip() == "Обновись" for r, c in flat) and any(r == "assistant" and "обновлени" in c.lower() for r, c in flat),
   "следующий вопрос модели — с быстрым обменом в истории (контекст не теряется)")
ok(flat and "расскажи анекдот" in flat[-1][1] and any("привет, как дела?" in c for r, c in flat), "и с началом разговора")
# выводы ночи можно убрать из разговора (владелец: «накопился мусор… боюсь, что подмешивается в беседу»)
sys.path.insert(0, str(ROOT / "core"))
import datetime as _dt
from diary import Diary
dd = Diary(None, tmp / "dtest")
dd.data["insights"] = {"day": _dt.date.today().isoformat(), "title": "т", "lines": ["ты часто возвращаешься после пауз", "любишь краткость"]}
ok("после пауз" in dd.prompt(), "выводы ночи — в подсказке модели")
dd.drop_insight(0)
ok("после пауз" not in dd.prompt() and "краткость" in dd.prompt(), "убрали один — его больше нет, другой остался")
dd.drop_insight(None)
ok(dd.prompt() == "" and Diary(None, tmp / "dtest").prompt() == "", "«не учитывать ни один» — пусто и после перезапуска")
src = (ROOT / "ui/studio/soul.js").read_text(encoding="utf-8")
ok("diary_insight_drop" in src and "dins-x" in src, "в «Дневнике» у каждого вывода — «×»")
keys = [x.get("key") for x in CTX.get("parts") or []]
ok(keys[:2] == ["persona", "memory"] and "insights" in keys and "summary" in keys and CTX.get("full_chars", 0) > 1000,
   f"«Для отладки: что Лира учитывает» — части подсказки и подсказка целиком: {keys}, {CTX.get('full_chars')}")
print("\nИТОГ:", "все проверки прошли" if not FAILS else f"не прошло {len(FAILS)}")
sys.exit(1 if FAILS else 0)
