"""Курс «Неделя с Лирой» (27.10, владелец: «обучающий курс — ОЧЕНЬ нравится»). Часть 1 — core/course.py: шаг
засчитывается по фразе и по открытому разделу, урок пройден — следующий завтра (или «следующий сейчас»), предложение —
раз в день и не после «не сегодня». Часть 2 — настоящее ядро с моком модели: фразы урока засчитываются сами, «урок дня»
отвечает без модели, утреннее приветствие предлагает урок; студия → «Неделя с Лирой» и карточка на «Главной»."""
import asyncio, json, os, socket, subprocess, sys, tempfile, time
from datetime import date, timedelta
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
TESTS = ROOT / "tests"
PY = os.environ.get("DEWIAR_PY") or sys.executable
SHOTS = os.environ.get("DEWIAR_SHOTS")
sys.path.insert(0, str(ROOT / "core"))
import course as C  # noqa: E402
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


tmp = Path(tempfile.mkdtemp())
ev = []
c = C.Course(tmp / "c.json", lambda t, **k: ev.append(t))
p = c.public()
ok(p["lesson"]["day"] == 1 and p["lesson"]["open"] and p["done"] == 0 and len(p["days"]) == 7, "старт: урок 1 открыт, 7 дней")
line = c.offer_line()
ok("урок" in line and "«Лира, привет!" in line and c.offer_line() == "", "предложение урока — раз в день")
c.heard("Лира, привет! Что ты умеешь?"); c.heard("напомни через 10 минут проверить чайник")
ok([s["done"] for s in c.public()["lesson"]["steps"]] == [True, True, False] and "course" in ev, "фразы урока — шаги засчитаны сами")
c.heard("какие у меня дела?")
p = c.public()
ok(p["done"] == 1 and p["lesson"]["day"] == 2 and not p["lesson"]["open"], "урок 1 пройден — второй откроется завтра")
ok(c.heard("запланируй на завтра встречу") is None, "пока урок закрыт — фразы не засчитываются")
c.ahead()
ok(c.public()["lesson"]["open"], "«Следующий урок сейчас» — открыт")
ok(c.seen("calendar") == 2 and c.public()["lesson"]["steps"][2]["done"], "шаг «Откройте «Календарь»» — по переходу в раздел")
c2 = C.Course(tmp / "c.json")
ok(c2.public()["done"] == 1 and c2.public()["lesson"]["steps"][2]["done"], "прогресс переживает перезапуск")
c2._cs()["done"]["2"] = (date.today() - timedelta(days=1)).isoformat()
c2._cs()["steps"]["2"] = [0, 1, 2]
c2.st.pop("offered", None)
ok(c2.public()["lesson"]["day"] == 3 and c2.public()["lesson"]["open"], "прошёл вчера — сегодня следующий открыт")
c2.skip_today()
ok(c2.offer_line() == "", "«не сегодня» — не предлагать до завтра")
c2.restart(1)
ok(c2.public()["days"][0]["state"] != "done", "урок можно повторить")
pf = c2.pick("family")
ok(pf["title"] == "Лира для семьи" and pf["lesson"]["day"] == 1 and [x["id"] for x in pf["courses"]] == ["week", "family", "work"],
   "курсы: «Неделя с Лирой», «Лира для семьи», «Лира для работы» — у каждого свой ход")
ok(c2.seen("close") == 0 and c2.public()["lesson"]["steps"][0]["done"] and C.Course(tmp / "c.json").public()["course"] == "family", "«Лира для семьи»: шаг «Откройте «Близкие»»")
c2.pick("week")
ok(c2.public()["done"] == 1, "вернулись к «Неделе» — её ход на месте")
week_days = [L["title"] for L in C.BY_ID["week"]["lessons"]]
ok(any("Досуг" in t for t in week_days) and any("Детский" in L["title"] for L in C.BY_ID["family"]["lessons"]),
   f"в «Неделе» — досуг (радио, музыка, игры), в «Семье» — детский режим: {week_days}")
old = tmp / "old.json"; old.write_text('{"done": {"1": "2026-10-01"}, "steps": {"1": [0, 1, 2]}, "offer": true}')
ok(C.Course(old).public()["done"] == 1, "старый файл курса читается как «Неделя с Лирой»")

# ---------- часть 2: ядро и студия ----------
from playwright.sync_api import sync_playwright  # noqa: E402
import websockets  # noqa: E402


def free():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p_ = s.getsockname()[1]; s.close(); return p_


LLM, PORT = free(), free()
mock = subprocess.Popen([sys.executable, str(TESTS / "mock_llm.py"), str(LLM)])
cfg = tmp / "cfg"; cfg.mkdir()
(cfg / "settings.json").write_text(json.dumps({"persona": "lira", "audio": {"sounds": False, "follow_up_seconds": 0},
    "ui": {"news_seen": "99.0.0", "welcome": "done"}, "stt": {"engine": "vosk"}, "tts": {"engine": "off"}, "updates": {"auto_check": False},
    "llm": {"active": "m", "profiles": {"m": {"name": "Мок", "kind": "openai", "base_url": f"http://127.0.0.1:{LLM}/v1", "model": "mock"}}}}))
env = dict(os.environ, DEWIAR_CONFIG_DIR=str(cfg), DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_PORT=str(PORT), DEWIAR_ASSUME_AEC="1",
           DEWIAR_WORKSPACE_DIR=str(tmp / "ws"), DEWIAR_DRY_TOOLS=str(tmp / "dry.jsonl"))
core = subprocess.Popen([PY, str(ROOT / "core/main.py"), "--wav", str(TESTS / "silence90.wav"), "--null-audio"], env=env,
                        stdout=open(tmp / "core.log", "w"), stderr=subprocess.STDOUT)
R, events = {}, []


async def run():
    ws_ = None
    for _ in range(300):
        await asyncio.sleep(0.2)
        if (cfg / "token").exists():
            try:
                ws_ = await websockets.connect(f"ws://127.0.0.1:{PORT}", max_size=None); break
            except OSError:
                continue
    await ws_.send(json.dumps({"cmd": "hello", "token": (cfg / "token").read_text().strip()}))
    n = [0]; replies = {}

    async def call(cmd, **args):
        n[0] += 1; i = n[0]; await ws_.send(json.dumps({"id": i, "cmd": cmd, "args": args}))
        for _ in range(600):
            if i in replies:
                r = replies.pop(i)
                return r.get("data")
            await asyncio.sleep(0.05)

    async def wait_for(pred, limit):
        end = time.monotonic() + limit
        while time.monotonic() < end:
            for e in events:
                if pred(e):
                    return e
            await asyncio.sleep(0.1)

    async def reader():
        async for raw in ws_:
            e = json.loads(raw)
            if e["type"] == "reply":
                replies[e["id"]] = e
            elif e["type"] != "level":
                events.append(e)
    rd = asyncio.ensure_future(reader())
    await asyncio.sleep(1.5)
    events.clear()
    await call("say", text="Урок дня")
    R["lesson"] = await wait_for(lambda e: e["type"] == "answer" and "Урок 1 из 7" in (e.get("text") or ""), 10)
    for t in ("Лира, привет! Что ты умеешь?", "Напомни через 10 минут проверить чайник"):
        events.clear()
        await call("say", text=t)
        await wait_for(lambda e: e["type"] == "answer" and e.get("done"), 20)
        await asyncio.sleep(0.5)
    R["get"] = await call("course_get")
    rd.cancel()
    await ws_.close()


try:
    asyncio.run(run())
    ok(R.get("lesson") is not None, "«урок дня» — Лира говорит, что за урок, без модели")
    ok([s["done"] for s in R["get"]["lesson"]["steps"]] == [True, True, False], f"фразы урока в разговоре — засчитаны: {R['get']['lesson']['steps']}")
    tok = (cfg / "token").read_text().strip()
    errs = []
    with sync_playwright() as pw:
        b = pw.chromium.launch(); pg = b.new_page(viewport={"width": 1400, "height": 1000})
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto((ROOT / "ui/settings.html").as_uri() + f"?token={tok}&port={PORT}"); time.sleep(3)
        ok("Урок дня" in pg.inner_text("#hm-today") and "Разговор и напоминания" in pg.inner_text("#hm-today"), "«Главная»: карточка «Урок дня»")
        pg.click('nav button[data-p="course"]'); time.sleep(1.2)
        t = pg.inner_text("#p-course")
        ok("Разговор и напоминания" in t and "Сделано" in t and "Ждём" in t and pg.locator("#cs-days li").count() == 7, "студия: 7 дней, урок дня, шаги «Сделано» и «Ждём»")
        if SHOTS:
            pg.screenshot(path=os.path.join(SHOTS, "course.png"), full_page=True)
        pg.click("#cs-lesson [data-say]"); time.sleep(3)
        ok("Пройдено 1 из 7" in pg.inner_text("#cs-pt").replace("\n", " ") and "Урок пройден" in pg.inner_text("#cs-lesson") or "Календарь и дела" in pg.inner_text("#cs-lesson"),
           f"▶ у последнего шага — урок пройден: {pg.inner_text('#cs-pt')!r}")
        ok(not errs, f"без ошибок на странице: {errs[:2]}")
        b.close()
finally:
    core.terminate(); mock.terminate()
print("ИТОГ:", "все проверки пройдены" if not fails else f"не пройдено {len(fails)}")
sys.exit(1 if fails else 0)
