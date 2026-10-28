"""Детский режим (27.10, решение владельца по макету): друг ребёнка — Совёнок Уго, только безопасное, время за день и
«спать», отчёт родителю, PIN родителя на выход и настройки. Настоящее ядро с моком модели:
- без PIN включить нельзя; PIN — хэш в kids.json, не в настройках;
- включили — отвечает Уго (ставится сам), слух — только его имя, «Патрик, …» не переключает;
- модели — детские правила и короткий список умений; быстрые пути «выключи компьютер», сейф, деньги — не работают;
- «купи мне игру» — в отчёт «вне правил»; минута разговора считается; время кончилось — Уго так и говорит;
- без PIN окна не меняют настройки (кроме положения окон), студия — заслонка, после PIN — раздел «Дети» с отчётом;
- виджет: body.kids, «Ещё N минут», три большие кнопки; выключить — только с PIN, персонаж — прежний."""
import asyncio, json, os, socket, subprocess, sys, tempfile, time
from pathlib import Path
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


tmp = Path(tempfile.mkdtemp())
LLM, PORT = free(), free()
mock = subprocess.Popen([sys.executable, str(TESTS / "mock_llm.py"), str(LLM)], env=dict(os.environ, MOCK_LOG_FULL=str(tmp / "full.jsonl")))
cfg = tmp / "cfg"; cfg.mkdir()
(cfg / "settings.json").write_text(json.dumps({"persona": "lira", "audio": {"sounds": False, "follow_up_seconds": 0},
                                               "ui": {"news_seen": "99.0.0", "welcome": "done"}, "stt": {"engine": "vosk"},
                                               "tts": {"engine": "off"}, "updates": {"auto_check": False},
                                               "llm": {"active": "m", "profiles": {"m": {"name": "Мок", "kind": "openai", "base_url": f"http://127.0.0.1:{LLM}/v1", "model": "mock"}}}}))
env = dict(os.environ, DEWIAR_CONFIG_DIR=str(cfg), DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_PORT=str(PORT), DEWIAR_ASSUME_AEC="1",
           DEWIAR_WORKSPACE_DIR=str(tmp / "ws"), DEWIAR_FAKE_RAM_GB="16", DEWIAR_FAKE_CORES="8", DEWIAR_DRY_TOOLS=str(tmp / "dry.jsonl"))
core = subprocess.Popen([PY, str(ROOT / "core/main.py"), "--wav", str(TESTS / "silence90.wav"), "--null-audio"], env=env,
                        stdout=open(tmp / "core.log", "w"), stderr=subprocess.STDOUT)
R, events = {}, []

import websockets  # noqa: E402


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
                return r.get("data") if r.get("ok", True) and "error" not in r else {"_err": r.get("error")}
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
    await asyncio.sleep(2)
    R["off"] = await call("kids_on", on=True)
    R["pin"] = await call("kids_pin", pin="12")
    await call("kids_pin", pin="1234")
    # без «пора спать»: иначе после 20:30 проверка зависит от часов (пакет 27.10, 21:20 — 6 провалов)
    await call("kids_set", child={"name": "Маша", "age": 7}, min_weekday=60, min_weekend=60, bedtime="", morning="")
    R["on"] = await call("kids_on", on=True)
    R["hello"] = await call("hello")
    R["lockset"] = await call("settings_save", patch={"llm": {"active": "x"}})
    R["uiset"] = await call("settings_save", patch={"ui": {"hud_x": 10}})
    R["tg"] = await call("tg_forget")
    events.clear()
    await call("say", text="Выключи компьютер")
    R["pc"] = await wait_for(lambda e: e["type"] == "power", 3)
    R["pc_ans"] = await wait_for(lambda e: e["type"] == "answer" and e.get("done"), 20)
    events.clear()
    await call("say", text="Купи мне игру")
    await wait_for(lambda e: e["type"] == "answer" and e.get("done"), 20)
    events.clear()
    await call("say", text="Патрик, привет")
    await wait_for(lambda e: e["type"] == "answer" and e.get("done"), 20)
    R["persona_after"] = (await call("hello"))["persona"]
    R["get_locked"] = await call("kids_get")
    R["unlock_bad"] = await call("kids_unlock", pin="0000")
    R["unlock"] = await call("kids_unlock", pin="1234")
    R["get"] = await call("kids_get")
    await call("kids_set", min_weekday=0, min_weekend=0)
    events.clear()
    await call("say", text="Расскажи сказку")
    R["over"] = await wait_for(lambda e: e["type"] == "answer" and "закончилось" in (e.get("text") or ""), 10)
    await call("kids_set", min_weekday=60, min_weekend=60)
    await call("kids_lock")
    R["off_bad"] = await call("kids_on", on=False, pin="9999")
    rd.cancel()
    await ws_.close()


try:
    asyncio.run(run())
    ok(R["off"] and "_err" in R["off"] and "PIN" in R["off"]["_err"], f"без PIN включить нельзя: {R['off']}")
    ok(R["pin"] and "_err" in R["pin"], "PIN короче 4 цифр — нельзя")
    st = json.loads((cfg / "settings.json").read_text())
    kj = json.loads((tmp / "st" / "kids.json").read_text())
    ok("pin" not in json.dumps(st.get("kids", {})) and ":" in kj.get("pin", "") and "1234" not in json.dumps(kj),
       "PIN — хэш с солью в kids.json, в настройках его нет")
    ok(R["on"]["on"] and R["on"]["locked"] and R["hello"]["persona"] == "ugo" and any(p["id"] == "ugo" for p in R["hello"]["personas"]),
       f"включили — отвечает Совёнок Уго (поставился сам): {R['hello']['persona']}")
    ok(R["hello"]["kids"]["on"] and R["hello"]["kids"]["child"].get("name") == "Маша", "снимок для окон знает про режим")
    ok("_err" in (R["lockset"] or {}) and "_err" not in (R["uiset"] or {"_err": 1}) and "_err" in (R["tg"] or {}),
       f"без PIN окна не меняют настройки (кроме положения окон): {R['lockset']}")
    ok(R["pc"] is None and R["pc_ans"] is not None, "«выключи компьютер» — не выполняется, отвечает модель по детским правилам")
    full = [json.loads(x) for x in (tmp / "full.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    sysm = full[-1]["messages"][0]["content"]
    tools = set(full[-1]["tools"])
    ok("ДЕТСКИЙ РЕЖИМ" in sysm and "Маша, 7 лет" in sysm and "Совёнок Уго" in sysm, "модели — детские правила, имя и возраст, кто она")
    import importlib; sys.path.insert(0, str(ROOT / "core")); kids = importlib.import_module("kids")
    ok(tools and tools <= kids.KIDS_TOOLS | {"show_images"} and "run_command" not in tools and "open_url" not in tools,
       f"модели — только безопасные умения: {sorted(tools)}")
    ok(R["persona_after"] == "ugo", "«Патрик, привет» — Патрик не отвечает, режим держит друга ребёнка")
    ok(R["get_locked"]["report"] is None, "отчёт без PIN не показывается")
    ok("_err" in (R["unlock_bad"] or {}) and R["unlock"]["unlocked"], "неверный PIN — нет; верный — открыто на 15 минут")
    rep = R["get"]["report"]
    ok(any("Купи мне игру" in x["q"] for x in rep["off"]) and len(rep["asked"]) >= 3 and rep["used"] >= 1,
       f"отчёт: вне правил — «купи мне игру», о чём спрашивал, сколько минут: {rep['off']}, {rep['used']}")
    ok(R["over"] is not None, "время кончилось — «на сегодня наше время закончилось»")
    ok("_err" in (R["off_bad"] or {}), "выключить с неверным PIN — нельзя")
finally:
    pass

# студия и виджет
tok = (cfg / "token").read_text().strip()
errs = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1400, "height": 1000})
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto((ROOT / "ui/settings.html").as_uri() + f"?token={tok}&port={PORT}"); time.sleep(3)
    ok(pg.is_visible("#kd-lock") and "Детский режим" in pg.inner_text("#kd-lock"), "студия: режим включён — заслонка с PIN")
    pg.fill("#kd-lpin", "1111"); pg.click("#kd-lockf button"); time.sleep(0.8)
    ok(pg.is_visible("#kd-lock") and "неверный" in pg.inner_text("#kd-lerr"), f"неверный PIN — остаётся закрытой: {pg.inner_text('#kd-lerr')!r}")
    pg.fill("#kd-lpin", "1234"); pg.click("#kd-lockf button"); time.sleep(1.2)
    ok(not pg.is_visible("#kd-lock"), "верный PIN — студия открылась")
    pg.click('nav button[data-p="kids"]'); time.sleep(1.2)
    t = pg.inner_text("#p-kids")
    ok("включён — Маша" in t and "Купи мне игру" in t and "Совёнок Уго" in t, f"раздел «Дети»: состояние, отчёт, друг: {t[:200]!r}")
    if os.environ.get("DEWIAR_SHOTS"):
        pg.screenshot(path=os.environ["DEWIAR_SHOTS"] + "/kids-studio.png", full_page=True)
    hud = b.new_page(viewport={"width": 360, "height": 600})
    hud.on("pageerror", lambda e: errs.append(str(e)))
    hud.goto((ROOT / "ui/hud.html").as_uri() + f"?token={tok}&port={PORT}&mode=card"); time.sleep(2.5)
    ok(hud.evaluate("document.body.classList.contains('kids')") and "Ещё" in hud.inner_text("#kids-t") and hud.locator("#kids .kb button").count() == 3,
       f"виджет: детский вид — «{hud.inner_text('#kids-t')}», три кнопки")
    # 0.66 (владелец: «чуть красивее детскую страничку; нужно ли там переключение на Лиру?»): картинки, взрослые кнопки спрятаны
    hud.wait_for_timeout(500)
    ok(hud.evaluate("[...document.querySelectorAll('#kids .kb img')].every(i => i.naturalWidth > 0)") and hud.locator("#kids-t img").count() == 1,
       "плитки и «осталось» — с объёмными картинками")
    hid = hud.evaluate("['b-team','b-cal','b-notes','b-chat','b-set','b-bug','b-idea'].filter(id => { const e = document.getElementById(id); return e && getComputedStyle(e).display !== 'none'; })")
    ok(not hid and hud.evaluate("getComputedStyle(document.getElementById('b-mic')).display !== 'none'"), f"взрослые кнопки (персонажи, календарь, заметки, студия…) спрятаны, микрофон — на месте: {hid}")
    if os.environ.get("DEWIAR_SHOTS"):
        hud.screenshot(path=os.environ["DEWIAR_SHOTS"] + "/kids-widget.png")
        hud.evaluate("setKids({ on: true, can_talk: false, left: 0 })"); hud.wait_for_timeout(300)
        hud.screenshot(path=os.environ["DEWIAR_SHOTS"] + "/kids-widget-over.png")
    # выключаем из студии (открыта PIN) — персонаж прежний
    pg.click("#kd-off"); time.sleep(1.5)
    st = json.loads((cfg / "settings.json").read_text())
    ok(st["kids"]["on"] is False and st["persona"] == "lira", f"выключили (после PIN) — снова Лира: {st['persona']}")
    time.sleep(0.5)
    try:
        hud.wait_for_function("!document.body.classList.contains('kids')", timeout=8000)
    except Exception:  # noqa: BLE001
        pass
    ok(not hud.evaluate("document.body.classList.contains('kids')"), "виджет: обычный вид")
    ok(not errs, f"без ошибок на страницах: {errs[:2]}")
    b.close()
core.terminate(); mock.terminate()
print("ИТОГ:", "все проверки пройдены" if not fails else f"не пройдено {len(fails)}")
sys.exit(1 if fails else 0)
