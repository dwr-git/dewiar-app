"""Дневник ассистента: ночью ассистент записывает анализ прожитого дня и днём пользуется выводами; дневник — отдельный раздел.
— реплики дня копятся только локально (STATE_DIR/days), ночью (после 3:00 или утром, когда компьютер проснулся) модель
  голосом персонажа пишет запись о прожитом дне: заголовок, настроение, текст и выводы «на завтра»;
— запись ложится в «Дневник/ГГГГ-ММ-ДД.md»; повторная заменяет прежнюю, а не дублирует;
— выводы «на завтра» идут в системную подсказку следующего дня — ночные мысли меняют дневные разговоры;
— тихий день (без разговоров) — без записи; студия видит дни с заголовками («Дневник»)."""
import asyncio, datetime as dt, json, os, socket, subprocess, sys, tempfile, time
from pathlib import Path
import websockets
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
TESTS = Path(__file__).resolve().parent
PY = os.environ.get("DEWIAR_PY") or sys.executable
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


def free():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


tmp = Path(tempfile.mkdtemp())
os.environ["DEWIAR_WORKSPACE_DIR"] = str(tmp / "ws0")
import diary as D  # noqa: E402
from workspace import Workspace  # noqa: E402

# ---------- разбор ответа модели ----------
g = D.parse("ЗАГОЛОВОК: «Тихий вторник»\nНАСТРОЕНИЕ: ☕\nДНЕВНИК:\nСегодня было спокойно.\n\nВечером говорили о книгах.\nНА ЗАВТРА:\n- Спросить про книгу\n2) Не торопить")
ok(g["title"] == "Тихий вторник" and g["mood"] == "☕" and "о книгах" in g["text"] and g["tomorrow"] == ["Спросить про книгу", "Не торопить"],
   f"ответ модели разбирается: {g['title']!r} {g['mood']} {g['tomorrow']}")
g = D.parse("<think>хм</think>**ЗАГОЛОВОК:** День\n**ДНЕВНИК:**\nТекст записи про день.\n**НА ЗАВТРА:**\n- раз")
ok(g["title"] == "День" and g["text"] == "Текст записи про день." and g["tomorrow"] == ["раз"], f"жирная разметка и <think> не мешают: {g}")
g = D.parse("Просто текст без разметки, модель забыла формат.")
ok(g["text"].startswith("Просто текст") and not g["tomorrow"], "без разметки — весь ответ считается записью")

# ---------- когда писать ----------
class FakeHost:
    def __init__(self):
        self.workspace = Workspace(None)
        self.tasks = type("T", (), {"tasks": {}})()
        self.s = type("S", (), {"get": lambda self, *k: None})()
        self.asked = []
    def persona_name(self): return "Лира"
    def diary_ask(self, instr, msg):
        self.asked.append((instr, msg))
        return "ЗАГОЛОВОК: Первый день\nНАСТРОЕНИЕ: ✨\nДНЕВНИК:\nСегодня хозяин впервые со мной заговорил. Я запомнил его голос.\nНА ЗАВТРА:\n- Поздороваться по имени"

h = FakeHost()
di = D.Diary(h, tmp / "st0")
today = dt.date.today()
y, y2 = today - dt.timedelta(days=1), today - dt.timedelta(days=2)
(tmp / "st0/days").mkdir(parents=True)
for d, n in ((y, 3), (y2, 1)):
    (tmp / f"st0/days/{d}.jsonl").write_text("".join(json.dumps({"t": "10:00", "u": f"привет {i}", "a": "здравствуйте"}) + "\n" for i in range(n)))
night = dt.datetime.combine(today, dt.time(1, 30))
ok(di.pending(now=night) is None, "в половине второго ночи о вчерашнем ещё не пишем (ждём 3:00)")
ok(di.pending(now=dt.datetime.combine(today, dt.time(3, 5))) == y, "после 3:00 — пора написать о вчерашнем дне")
got = di.write(y)
ok(got and got["title"] == "Первый день" and "Лира" in h.asked[0][0] and "привет 0" in h.asked[0][1],
   "запись пишется голосом персонажа по репликам дня")
f = h.workspace.root / f"Дневник/{y}.md"
txt = f.read_text(encoding="utf-8")
ok("## 🌙 Ночью — о прожитом дне · «Первый день» ✨" in txt and "**На завтра:**\n- Поздороваться по имени" in txt, "запись — в файле того дня")
di.write(y)
ok(f.read_text(encoding="utf-8").count("## 🌙") == 1, "повторная запись заменяет прежнюю, не дублирует")
ok(di.pending(now=dt.datetime.combine(today, dt.time(9))) is None and f"{y2}" in di.data.get("done", []),
   "вчерашний описан; позавчерашний тихий день (одна реплика) — без записи")
ok("Поздороваться по имени" in di.prompt() and "«Первый день»" in di.prompt(), "выводы на завтра — в подсказку")
di.data["insights"]["day"] = str(today - dt.timedelta(days=4))
ok(di.prompt() == "", "старые выводы (4 дня) в подсказку уже не идут")
h.workspace.diary("Днём записал короткую мысль.", "Лира")
days = h.workspace.diary_days(di.data.get("titles"))
ok(days[1].get("who") == "Лира" and (di.data.get("insights") or {}).get("who") == "Лира",
   "у ночной записи — кто писал (16.10: переключил на Патрика — а записи Лиры подписаны как его)")
ok(days[0]["day"] == str(today) and days[1]["title"] == "Первый день" and days[1]["night"] and days[1]["preview"].startswith("Сегодня хозяин"),
   f"студия: дни с заголовками и началом текста ({[(x['day'], x['title'], x['count']) for x in days]})")

# ---------- с ядром ----------
PORT, LLM = free(), free()
LOG = tmp / "llm.jsonl"
(tmp / "cfg").mkdir()
(tmp / "cfg/settings.json").write_text(json.dumps({
    "persona": "lira", "stt": {"engine": "vosk"}, "tts": {"engine": "off"}, "audio": {"sounds": False, "follow_up_seconds": 0},
    "llm": {"active": "m", "profiles": {"m": {"name": "mock", "kind": "openai", "base_url": f"http://127.0.0.1:{LLM}/v1", "model": "chat"}}}}))
env = dict(os.environ, DEWIAR_CONFIG_DIR=str(tmp / "cfg"), DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_PORT=str(PORT),
           DEWIAR_ASSUME_AEC="1", DEWIAR_WORKSPACE_DIR=str(tmp / "ws"), DEWIAR_FAKE_RAM_GB="16", DEWIAR_FAKE_CORES="8")
mock = subprocess.Popen([sys.executable, str(TESTS / "mock_llm.py"), str(LLM)], env=dict(os.environ, MOCK_LOG_FULL=str(LOG)))


def requests():
    return [json.loads(x) for x in LOG.read_text(encoding="utf-8").splitlines() if x.strip()] if LOG.exists() else []


async def session(n, body, extra=None):
    core = subprocess.Popen([PY, str(ROOT / "core/main.py"), "--wav", str(TESTS / "silence90.wav"), "--null-audio"], env=dict(env, **(extra or {})),
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
            for _ in range(1200):
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
                if [e for e in events if e["type"] == "answer" and e.get("done")]:
                    await asyncio.sleep(0.3); return True
                await asyncio.sleep(0.1)
            return False
        await body(say, call, events)
        rd.cancel()
        await ws_.close()
    finally:
        core.terminate()
        try:
            core.wait(10)
        except subprocess.TimeoutExpired:
            core.kill()


R = {}


async def day1(say, call, events):
    await say("Мою собаку зовут Бублик, мы гуляем по вечерам.")
    await say("Какая сегодня погода?")
    R["list0"] = (await call("diary_list")).get("data") or {}
    R["now"] = await call("diary_write_now")
    R["now2"] = await call("diary_write_now")
    R["list"] = (await call("diary_list")).get("data") or {}
    R["soul0"] = (await call("soul_get")).get("data") or {}
    R["soul"] = await call("soul_update")
    R["const_bad"] = await call("const_save", text="# Конституция\n\n")
    c = (await call("const_get")).get("data") or {}
    R["const"] = await call("const_save", text=c.get("text", "") + "9. **Тишина ночью.** После полуночи отвечаю шёпотом и коротко.\n")
    await say("Доброе утро!")


try:
    asyncio.run(session(1, day1))
    log = tmp / f"st/days/{dt.date.today()}.jsonl"
    rows = [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines()] if log.exists() else []
    ok(len(rows) >= 2 and "Бублик" in rows[0]["u"] and rows[0].get("who"), f"реплики дня копятся локально ({len(rows)})")
    ok(R["list0"].get("today_turns", 0) >= 2, "студия знает, что сегодня уже было о чём поговорить")
    d = (R["now"] or {}).get("data") or {}
    ok(d.get("title") == "День, когда я узнал про Бублика" and d.get("mood") == "🌿", f"«Записать о сегодняшнем дне» — запись готова: {d.get('title')!r} ({(R['now'] or {}).get('error')})")
    day = tmp / f"ws/Дневник/{dt.date.today()}.md"
    t = day.read_text(encoding="utf-8") if day.exists() else ""
    ok(t.count("## 🌙") == 1 and "собаку зовут Бублик" in t and "Отвечать короче" in t, "в файле дня — одна ночная запись (вторая её заменила)")
    nr = [r for r in requests() if r["messages"][-1]["content"].startswith("Сейчас ночь")]
    ok(nr and not nr[0]["tools"] and "Лира" in nr[0]["messages"][-1]["content"] and "Бублик" in nr[0]["messages"][-1]["content"],
       "запись пишет модель без инструментов, голосом Лиры, по репликам дня")
    ds = R["list"].get("days") or []
    ok(ds and ds[0]["title"] == "День, когда я узнал про Бублика" and ds[0]["night"] and (R["list"].get("insights") or {}).get("lines"),
       "студия: день с заголовком и выводы «на завтра»")
    chats = [r for r in requests() if r["tools"] and "Доброе утро" in json.dumps(r["messages"][-1], ensure_ascii=False)]
    # подсказка и личная справка в начале разговора (04.11, «Голос без пауз»: личное — не в подсказке, llm.put_profile)
    # 0.87 (кэш подсказки): справка в начале разговора — снимок; что появилось с тех пор (выводы ночи, душа) — в справке к вопросу
    sysp = (chats[-1]["messages"][0]["content"] + "\n" + str(chats[-1]["messages"][1].get("content"))
            + "\n" + str(chats[-1]["messages"][-1].get("content"))) if chats else ""
    ok("Твои выводы после прошлого дня" in sysp and "Отвечать короче" in sysp, "выводы ночи — в подсказке дневного разговора")
    ok("свой дневник" in sysp, "днём ассистент сам записывает мысли в дневник (подсказка)")
    # душа (пишется по дневнику) и конституция — в подсказке разговора
    sd = (R["soul"] or {}).get("data") or {}
    sf = tmp / "ws/Память/Душа/Лира.md"
    ok(not R["soul0"].get("text") and R["soul0"].get("nights", 0) >= 1, "души сначала нет — она вырастет из дневника")
    ok("## Кто я" in sd.get("text", "") and sf.exists() and "Бублик" in sf.read_text(encoding="utf-8"),
       f"«Обновить по дневнику» — Лира пишет свою душу по ночным записям ({(R['soul'] or {}).get('error')})")
    soul_req = [r for r in requests() if r["messages"][-1]["content"].startswith("Перечитай свой дневник")]
    ok(soul_req and "День, когда я узнал про Бублика" in soul_req[0]["messages"][-1]["content"] and not soul_req[0]["tools"],
       "душа пишется по дневнику, без инструментов")
    ok("ТВОЯ ДУША" in sysp and "Учусь говорить короче" in sysp, "душа — в подсказке разговора")
    ok("ТВОЯ КОНСТИТУЦИЯ" in sysp and "Честность" in sysp and "Тишина ночью" in sysp,
       "конституция (с правкой пользователя) — в подсказке разговора")
    ok(not (R["const_bad"] or {}).get("ok") and (tmp / "ws/Память/Конституция.md").exists(), "пустую конституцию не сохранить")

    # ночь: вчерашний день — живой, ещё не описан; ассистент «просыпается» и пишет сам
    yday = dt.date.today() - dt.timedelta(days=1)
    (tmp / f"st/days/{yday}.jsonl").write_text("".join(json.dumps({"t": "21:00", "u": f"вечерний вопрос {i}", "a": "ответ", "who": "Лира"}, ensure_ascii=False) + "\n"
                                                       for i in range(3)), encoding="utf-8")
    cfg = json.loads((tmp / "cfg/settings.json").read_text(encoding="utf-8")); cfg["diary"] = {"night": True, "hour": 0}
    (tmp / "cfg/settings.json").write_text(json.dumps(cfg))

    async def night(say, call, events):
        for _ in range(80):
            if any(e["type"] == "diary" for e in events):
                break
            await asyncio.sleep(0.25)
        R["ev"] = [e for e in events if e["type"] == "diary"]
    asyncio.run(session(2, night, {"DEWIAR_DIARY_WAIT": "2"}))
    print(open(tmp / "core2.log", encoding="utf-8").read()[-3000:]) if os.environ.get("DBG") else None
    yf = tmp / f"ws/Дневник/{yday}.md"
    ok(R["ev"] and R["ev"][0].get("day") == str(yday) and yf.exists() and "## 🌙" in yf.read_text(encoding="utf-8"),
       "ночью ассистент сам «просыпается» и пишет о вчерашнем дне")
    st = json.loads((tmp / "st/diary.json").read_text(encoding="utf-8"))
    ok(str(yday) in st.get("done", []) and str(dt.date.today()) not in st.get("done", []),
       "вчерашний отмечен описанным; о сегодняшнем ночью напишет ещё раз, полнее")
finally:
    mock.terminate()

# студия: дневник общий — у записи подпись, кто писал, а не имя текущего персонажа (16.10)
from playwright.sync_api import sync_playwright  # noqa: E402
DAY = {"day": "2026-10-15", "title": "Тихий четверг", "mood": "🌙", "who": "Лира", "night": True, "count": 1, "preview": "День…",
       "text": "# Дневник — 15 октября 2026\n\n## 🌙 Ночью — о прожитом дне · «Тихий четверг» 🌙\n\nДень, в котором я сказала всего две реплики.\n"}
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1360, "height": 900}); perr = []
    pg.on("pageerror", lambda e: perr.append(str(e)))
    pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };")
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(1000)
    r = pg.evaluate("""async (day) => { core.call = (c) => Promise.resolve(c === 'diary_list' ? { days: [day], insights: { lines: ['Короче по утрам'], who: 'Лира' } } : {});
        await loadDiary(); await new Promise(r => setTimeout(r, 300));
        return [$('#d-lead').textContent, $('#d-ins').textContent, $('#d-days').textContent, $('#d-page').textContent]; }""", DAY)
    ok("Общий дневник" in r[0] and "Лира" in r[1] and "Лира" in r[2] and "пишет Лира" in r[3],
       f"студия: дневник общий, у записи — кто её написал: {[x[:80] for x in r]}")
    ok(not perr, f"студия без ошибок: {perr[:2]}")
    b.close()
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
