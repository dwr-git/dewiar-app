"""Длинный разговор. Ядро с тестовой моделью:
— последние реплики уходят модели дословно, а начало разговора сама модель сворачивает в краткое содержание,
  и оно идёт в системную подсказку: факт из первой реплики («собаку зовут Бублик») не теряется и через 12 реплик;
— запрос к модели не растёт с длиной разговора;
— разговор переживает перезапуск программы; перерыв дольше 20 минут модель видит; после 8 часов тишины — новый разговор;
— «начнём новый разговор» — с чистого листа."""
import asyncio, json, os, socket, subprocess, sys, tempfile, time
from pathlib import Path
import websockets
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


tmp = Path(tempfile.mkdtemp())
PORT, LLM = free(), free()
LOG = tmp / "llm.jsonl"
(tmp / "cfg").mkdir()
(tmp / "cfg/settings.json").write_text(json.dumps({
    "persona": "dewiar", "stt": {"engine": "vosk"}, "tts": {"engine": "off"}, "audio": {"sounds": False, "follow_up_seconds": 0},
    "llm": {"active": "m", "history_turns": 3, "profiles": {"m": {"name": "mock", "kind": "openai", "base_url": f"http://127.0.0.1:{LLM}/v1", "model": "chat"}}}}))
env = dict(os.environ, DEWIAR_CONFIG_DIR=str(tmp / "cfg"), DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_PORT=str(PORT),
           DEWIAR_ASSUME_AEC="1", DEWIAR_WORKSPACE_DIR=str(tmp / "ws"), DEWIAR_FAKE_RAM_GB="16", DEWIAR_FAKE_CORES="8")
mock = subprocess.Popen([sys.executable, str(TESTS / "mock_llm.py"), str(LLM)], env=dict(os.environ, MOCK_LOG_FULL=str(LOG)))
CONV = tmp / "st/conversation.json"


def requests():
    if not LOG.exists():
        return []
    return [json.loads(x) for x in LOG.read_text(encoding="utf-8").splitlines() if x.strip()]


def chats():
    """Запросы разговора (не сворачивания): системная подсказка ассистента."""
    return [r for r in requests() if not r["messages"][0]["content"].startswith("Ты ведёшь краткое содержание")]


def sys_of(r):
    """Подсказка и личная справка в начале разговора (04.11: память, содержание долгого разговора — справкой в первом
    сообщении, llm.put_profile)."""
    ms = r["messages"]
    return ms[0]["content"] + ("\n" + str(ms[1].get("content")).split("(Дальше — разговор)")[0] if len(ms) > 1 else "")


def talk_of(r):
    """Сообщения разговора без личной справки."""
    ms = [dict(m) for m in r["messages"][1:]]
    if ms and isinstance(ms[0].get("content"), str) and "(Дальше — разговор)" in ms[0]["content"]:
        ms[0]["content"] = ms[0]["content"].split("(Дальше — разговор)\n", 1)[-1]
    return ms


def folds():
    return [r for r in requests() if r["messages"][0]["content"].startswith("Ты ведёшь краткое содержание")]


async def session(n, body):
    core = subprocess.Popen([PY, str(ROOT / "core/main.py"), "--wav", str(TESTS / "silence90.wav"), "--null-audio"], env=env,
                            stdout=open(tmp / f"core{n}.log", "w"), stderr=subprocess.STDOUT)
    try:
        ws_ = None
        for _ in range(300):
            await asyncio.sleep(0.2)
            if (tmp / "cfg/token").exists():
                try:
                    ws_ = await websockets.connect(f"ws://127.0.0.1:{PORT}", max_size=None); break
                except OSError:
                    continue
        await ws_.send(json.dumps({"cmd": "hello", "token": (tmp / "cfg/token").read_text().strip()}))
        events, replies, cnt = [], {}, [0]

        async def call(cmd, **args):
            cnt[0] += 1; i = cnt[0]
            await ws_.send(json.dumps({"id": i, "cmd": cmd, "args": args}))
            for _ in range(600):
                if i in replies:
                    return replies.pop(i)
                await asyncio.sleep(0.05)

        async def reader():
            async for raw in ws_:
                e = json.loads(raw)
                if e["type"] == "reply":
                    replies[e["id"]] = e
                elif e["type"] != "level":
                    events.append(e)
        rd = asyncio.ensure_future(reader())
        await asyncio.sleep(1.5)

        async def say(text, limit=20):
            events.clear()
            await call("say", text=text)
            end = time.monotonic() + limit
            while time.monotonic() < end:
                a = [e for e in events if e["type"] == "answer" and e.get("done")]
                if a:
                    await asyncio.sleep(0.3)
                    return a[-1].get("text", "")
                await asyncio.sleep(0.1)
            return ""
        await body(say)
        rd.cancel()
        await ws_.close()
    finally:
        core.terminate()
        try:
            core.wait(10)
        except subprocess.TimeoutExpired:
            core.kill()


R = {}


async def first(say):
    R["a1"] = await say("Запомни для разговора: мою собаку зовут Бублик, а встреча с Олегом в четверг в 15:00.")
    for i in range(2, 13):
        await say(f"Вопрос номер {i}: расскажи что-нибудь про число {i * 7}.")
    for _ in range(60):                                  # сворачивание идёт в фоне
        if folds() and CONV.exists() and "Бублик" in json.loads(CONV.read_text(encoding="utf-8")).get("summary", ""):
            break
        await asyncio.sleep(0.2)
    R["last_chat"] = await say("А теперь вопрос номер 13: как дела?")


try:
    asyncio.run(session(1, first))
    st = json.loads(CONV.read_text(encoding="utf-8")) if CONV.exists() else {}
    cs = chats()
    last = cs[-1] if cs else {"messages": [{"content": ""}]}
    sysp = sys_of(last)
    ok(folds(), f"начало разговора сворачивается в фоне — запросов на сворачивание: {len(folds())}")
    ok("Бублик" in st.get("summary", "") and st.get("turns", 0) >= 13, f"содержание разговора сохранено, в нём — факт из первой реплики ({st.get('turns')} реплик)")
    ok("Раньше в нём было" in sysp and "Бублик" in sysp and "15:00" in sysp,
       "через 13 реплик факт из первой («собака Бублик», «в четверг в 15:00») всё ещё у модели — в содержании")
    sizes = [len(r["messages"]) for r in cs]
    ok(max(sizes) <= 2 * (3 + 8) + 2 and len(last["messages"]) <= 2 * (3 + 4) + 2,
       f"запрос к модели не растёт с разговором: реплик в запросах {sizes}")
    ok(not any("Запомни для разговора" in m["content"] for m in talk_of(last)), "сама первая реплика дословно уже не отправляется — только содержанием")
    ok("вопрос номер 12" in json.dumps(last["messages"][1:], ensure_ascii=False).lower(), "последние реплики — дословно")
    ok(len(st.get("history", [])) <= 2 * (3 + 4) + 2, f"на диске — содержание и последние реплики ({len(st.get('history', []))})")

    # перезапуск: разговор продолжается; перерыв 45 минут — модель о нём знает
    st["last"] = time.time() - 45 * 60
    CONV.write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")
    n0 = len(chats())

    async def second(say):
        R["after_restart"] = await say("Напомни, как зовут мою собаку?")
        R["new"] = await say("Начнём новый разговор")
        R["fresh"] = await say("Привет!")
    asyncio.run(session(2, second))
    cs2 = chats()[n0:]
    s1 = (sys_of(cs2[0]) + "\n" + json.dumps(cs2[0]["messages"][-1], ensure_ascii=False)) if cs2 else ""
    ok("Бублик" in s1 and len(cs2[0]["messages"]) > 3 if cs2 else False, "после перезапуска программы разговор продолжается: содержание и последние реплики на месте")
    ok("перерыв 45 мин" in s1, "перерыв 45 минут модель видит и не путает новую просьбу со старой темой")
    ok("чистого листа" in R.get("new", ""), f"«Начнём новый разговор» — ответ без модели: {R.get('new')}")
    s3 = cs2[-1]["messages"][0]["content"] if len(cs2) > 1 else ""
    ok(cs2 and "Бублик" not in json.dumps(cs2[-1], ensure_ascii=False) and "Раньше в нём было" not in s3,
       "после «начнём новый разговор» прежнего содержания у модели нет")

    # 9 часов тишины — новый разговор сам
    st = json.loads(CONV.read_text(encoding="utf-8"))
    st.update(summary="- Пользователь говорил про Бублика", turns=20, last=time.time() - 9 * 3600)
    CONV.write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")
    n1 = len(chats())

    async def third(say):
        await say("Добрый вечер")
        # погоду с 0.6x ядро отвечает само, без модели (№373, engine_music._weather_cmd); ложный отказ «нет доступа
        # к интернету» — на другом свежем вопросе
        R["weather"] = await say("Сколько сейчас стоит биткоин?", 30)
    asyncio.run(session(3, third))
    cs3 = chats()[n1:]
    ok(cs3 and "Бублик" not in json.dumps(cs3[0], ensure_ascii=False) and len(cs3[0]["messages"]) == 2,
       "после 8 часов тишины — новый разговор: старое не подмешивается")
    logs = "".join((tmp / f"core{i}.log").read_text(encoding="utf-8", errors="replace") for i in (1, 2, 3))
    ok("Модель отказалась" in logs and R.get("weather", "").startswith("Готово. Результат") and
       any("web_search" in r.get("tools", []) and r["messages"][-1]["content"].startswith("СТОП. Ты отказался") for r in requests()),
       f"«нет доступа к интернету», а поиск есть — ассистент сам ищет и отвечает по найденному: {R.get('weather', '')[:60]}")
    # личная справка (llm.put_profile) и справка к вопросу — в каждом запросе разговора ровно по разу, и в кругах с
    # инструментами тоже (поиск после ложного отказа): дубли раздували бы запрос и сбивали кэш сервера модели
    heads = [(sum(str(m.get("content")).count("(О пользователе и о тебе — справка от программы") for m in r["messages"]),
              sum(str(m.get("content")).count("(Справка к этому сообщению") for m in r["messages"])) for r in chats()[n0:]]
    ok(heads and all(h == (1, 1) for h in heads),
       f"справки в запросах без дублей: {heads}")
    ok("Traceback" not in logs, "без ошибок в журнале ядра")
finally:
    mock.terminate()
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
