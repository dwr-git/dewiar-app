"""Дела по расписанию и утренняя сводка: «каждое утро в 9 присылай курс доллара в Телеграм» → дело (без звонка), в срок
ассистент сам выполняет поручение моделью и отвечает (Telegram не подключён — голосом и в виджете); «по пятницам в 18
собирай, что я сделал за неделю»; «утренняя сводка» — сразу, с делами и деньгами на сегодня; обычные напоминания
не превращаются в дела."""
import asyncio, datetime as dt, json, os, subprocess, sys, tempfile, time
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
PY = os.environ.get("DEWIAR_PY") or sys.executable
TESTS = Path(__file__).resolve().parent
tmp = Path(tempfile.mkdtemp())
ok = lambda c, m: print(("✅ " if c else "❌ ") + m)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))
from jobs import parse  # noqa: E402

j = parse("Каждое утро в 9 присылай курс доллара в Телеграм")
ok(j and j["repeat"]["kind"] == "daily" and j["repeat"]["time"] == "09:00" and j["deliver"] == "telegram" and j["task"] == "Присылай курс доллара",
   "«каждое утро в 9 присылай курс доллара в Телеграм» — дело каждый день в 9:00, в Telegram")
j = parse("по пятницам в 18 собирай, что я сделал за неделю")
ok(j and j["repeat"] == {"kind": "weekly", "days": [4], "time": "18:00"}, "«по пятницам в 18 собирай…» — каждую пятницу")
ok(parse("каждый день в 8 делай утреннюю сводку")["brief"] and parse("что у меня сегодня?") == {"op": "brief_now"},
   "утренняя сводка — по расписанию и сразу")
j = parse("каждый день в 21:00 подводи итог дня: что сделано, сколько потратил, что завтра")
ok(j and j["task"].endswith("что завтра") and j["repeat"]["time"] == "21:00", f"«…что завтра» в деле — не дата, текст целиком ({j and j['task']})")
ok(parse("напоминай каждый день в 8 выпить таблетки") is None and parse("напомни завтра в 9 позвонить маме") is None,
   "обычные напоминания — не дела")

import websockets  # noqa: E402
PORT, LLM_PORT = 8813, 8143
(tmp / "cfg").mkdir()
(tmp / "cfg/settings.json").write_text(json.dumps({
    "persona": "dewiar", "stt": {"engine": "vosk"}, "tts": {"engine": "off"}, "audio": {"sounds": False, "follow_up_seconds": 0},
    "llm": {"active": "m", "profiles": {"m": {"name": "mock", "kind": "openai", "base_url": f"http://127.0.0.1:{LLM_PORT}/v1", "model": "chat"}}}}))
env = dict(os.environ, DEWIAR_CONFIG_DIR=str(tmp / "cfg"), DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_PORT=str(PORT),
           DEWIAR_ASSUME_AEC="1", DEWIAR_WORKSPACE_DIR=str(tmp / "ws"))
mock = subprocess.Popen([sys.executable, str(TESTS / "mock_llm.py"), str(LLM_PORT)])
core = subprocess.Popen([PY, str(ROOT / "core/main.py"), "--wav", str(TESTS / "silence90.wav"), "--null-audio"], env=env,
                        stdout=open(tmp / "core.log", "w"), stderr=subprocess.STDOUT)
events, R = [], {}


async def run():
    ws_ = None
    for _ in range(300):
        await asyncio.sleep(0.2)
        if (tmp / "cfg/token").exists():
            try: ws_ = await websockets.connect(f"ws://127.0.0.1:{PORT}", max_size=None); break
            except OSError: continue
    await ws_.send(json.dumps({"cmd": "hello", "token": (tmp / "cfg/token").read_text().strip()}))
    n = [0]; replies = {}
    async def call(cmd, **args):
        n[0] += 1; i = n[0]; await ws_.send(json.dumps({"id": i, "cmd": cmd, "args": args}))
        for _ in range(600):
            if i in replies: return replies.pop(i)
            await asyncio.sleep(0.05)
    async def wait_for(pred, limit):
        end = time.monotonic() + limit
        while time.monotonic() < end:
            for e in events:
                if pred(e): return e
            await asyncio.sleep(0.1)
    async def reader():
        async for raw in ws_:
            e = json.loads(raw)
            if e["type"] == "reply": replies[e["id"]] = e
            elif e["type"] != "level": events.append(e)
    rd = asyncio.ensure_future(reader())
    await asyncio.sleep(2)
    await call("say", text="Каждое утро в 9 присылай курс доллара в Телеграм")
    R["set"] = await wait_for(lambda e: e["type"] == "answer" and e.get("done") and "буду" in e.get("text", ""), 10)
    items = (await call("reminders"))["data"]
    job = next((x for x in items if x.get("kind") == "job"), None)
    R["job"] = job
    events.clear()
    await call("reminder_update", id=job["id"], patch={"at": (dt.datetime.now() + dt.timedelta(seconds=2)).isoformat(timespec="seconds")})
    R["ran"] = await wait_for(lambda e: e["type"] == "heard" and "🗓" in e.get("text", ""), 15)
    R["answered"] = await wait_for(lambda e: e["type"] == "answer" and e.get("done") and e.get("text"), 20)
    R["no_alarm"] = not any(e["type"] == "alarm" for e in events)
    items = (await call("reminders"))["data"]
    nxt = next((x for x in items if x["id"] == job["id"]), {})
    R["next"] = nxt.get("at", "")
    await call("money_add", kind="expense", amount=8.5, category="Кафе и рестораны", note="кофе")
    events.clear()
    await call("say", text="Утренняя сводка")
    R["brief"] = await wait_for(lambda e: e["type"] == "heard" and "Утренняя сводка" in e.get("text", ""), 10)
    R["brief_ans"] = await wait_for(lambda e: e["type"] == "answer" and e.get("done") and e.get("text"), 20)
    r = await call("job_add", phrase="по будням в 9:15 делай курс валют", task="Курс доллара и евро на сегодня", deliver="voice", preset="fx")
    R["preset"] = r.get("data") or {}
    r = await call("job_add", phrase="каждый день в 21:00 делай итог дня", task="Итог дня: что сделано, что завтра", deliver="telegram", preset="evening")
    R["preset_tg"] = r
    r = await call("job_add", phrase="просто текст", task="x")
    R["preset_bad"] = r
    # пакет 27.10: «если писем нет — она всё равно появляется: „Тихо. Новых писем нет.“» — нового нет: молчим совсем
    for key, task in (("quiet", "Проверь почту MOCKSAY:Тихо. Новых писем нет."), ("loud", "Проверь почту MOCKSAY:Пришло письмо от Анны про ужин.")):
        r = await call("job_add", phrase="каждый час проверяй почту", task=task, deliver="voice")
        jid = (r.get("data") or {}).get("id") or next(x["id"] for x in (await call("reminders"))["data"] if task in x.get("text", ""))
        events.clear()
        await call("reminder_update", id=jid, patch={"at": (dt.datetime.now() + dt.timedelta(seconds=2)).isoformat(timespec="seconds")})
        await asyncio.sleep(9)
        R[key] = [e for e in events if e["type"] in ("heard", "answer")]
    rd.cancel()

try:
    asyncio.run(run())
finally:
    for p in (core, mock):
        p.terminate()
    core.wait()
log = (tmp / "core.log").read_text(encoding="utf-8")
ok(R.get("quiet") == [] and "нового нет — не беспокою" in log, f"проверка почты: новых писем нет — не появляется и не говорит: {R.get('quiet')}")
ok(any(e["type"] == "heard" and "🗓" in e.get("text", "") for e in R.get("loud", [])) and any("Пришло письмо от Анны" in (e.get("text") or "") for e in R.get("loud", [])),
   "пришло письмо — показывает и говорит")
ok(R.get("set") and R.get("job") and R["job"].get("deliver") == "voice", "дело поставлено; Telegram не подключён — честно сказал, что будет голосом")
ok(R.get("ran") and R.get("answered") and R.get("no_alarm"), "в срок — без звонка: ассистент сам выполнил поручение и ответил")
ok(R.get("next", "").endswith("09:00:00"), f"следующий раз — снова в 9:00 ({R.get('next')})")
ok(R.get("brief") and R.get("brief_ans") and "Утренняя сводка" in log, "«утренняя сводка» — сразу, с делами и деньгами")
p = R.get("preset") or {}
ok(p.get("kind") == "job" and p.get("preset") == "fx" and p.get("repeat") == {"kind": "weekly", "days": [0, 1, 2, 3, 4], "time": "09:15"}
   and p.get("text") == "Курс доллара и евро на сегодня" and p.get("deliver") == "voice",
   f"«Готовые дела»: курс валют по будням в 9:15, текст дела точный ({p.get('repeat')}, {p.get('text')})")
ok((R.get("preset_tg") or {}).get("ok") is False and "Telegram" in R["preset_tg"].get("error", ""),
   "в Telegram без подключённого бота — понятная ошибка, а не тихо голосом")
ok((R.get("preset_bad") or {}).get("ok") is False, "без расписания — ошибка")
