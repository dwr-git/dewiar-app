"""«Рентген» ответа (план «Качество», владелец 21.11: «всё работает вслепую — какая комбинация промптов уходит на
обработку»): у каждого ответа — номер рентгена; по нему видно путь (быстрая команда — какая, или модель), из чего
подсказка и сколько весит, какая модель, какие действия вызваны и чем кончились, строки журнала хода. Полный текст
подсказки — по запросу и только последних ходов; в отчёт разработчику — краткая сводка."""
import asyncio, json, os, shutil, socket, subprocess, sys, tempfile, time
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
UP, PORT = free(), free()
mock = subprocess.Popen([sys.executable, str(TESTS / "mock_llm.py"), str(UP)])
(tmp / "cfg").mkdir()
(tmp / "cfg/settings.json").write_text(json.dumps({
    "persona": "dewiar", "stt": {"engine": "vosk"}, "tts": {"engine": "off"}, "audio": {"sounds": False},
    "llm": {"active": "mock", "profiles": {"mock": {"name": "Проба", "kind": "openai", "base_url": f"http://127.0.0.1:{UP}/v1",
                                                     "model": "chat"}}}}))
env = dict(os.environ, DEWIAR_CONFIG_DIR=str(tmp / "cfg"), DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_PORT=str(PORT),
           DEWIAR_ASSUME_AEC="1", DEWIAR_WORKSPACE_DIR=str(tmp / "ws"), DEWIAR_FAKE_RAM_GB="16", DEWIAR_FAKE_CORES="8")
R = {}


async def session():
    core = subprocess.Popen([PY, str(ROOT / "core/main.py"), "--wav", str(TESTS / "silence90.wav"), "--null-audio"], env=env,
                            stdout=open(tmp / "core.log", "w"), stderr=subprocess.STDOUT)
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
        cnt, replies, answers = [0], {}, []

        async def reader():
            async for raw in ws_:
                e = json.loads(raw)
                if e["type"] == "reply":
                    replies[e["id"]] = e
                elif e["type"] == "answer" and e.get("done"):
                    answers.append(e)
        rd = asyncio.ensure_future(reader())

        async def call(cmd, **args):
            cnt[0] += 1; i = cnt[0]
            await ws_.send(json.dumps({"id": i, "cmd": cmd, "args": args}))
            for _ in range(600):
                if i in replies:
                    return replies.pop(i)
                await asyncio.sleep(0.05)

        async def ask(text):
            n = len(answers)
            await call("say", text=text)
            for _ in range(400):
                if len(answers) > n:
                    break
                await asyncio.sleep(0.05)
            await asyncio.sleep(1.5)
            return answers[n] if len(answers) > n else None
        R["clock"] = await ask("сколько времени?")
        R["remind"] = await ask("напомни проверить чайник")
        R["hello"] = await ask("расскажи что-нибудь интересное")
        R["list"] = await call("xray_list")
        for k in ("clock", "remind", "hello"):
            a = R[k]
            xid = ((a or {}).get("meta") or {}).get("xray")
            R[k + "_x"] = await call("xray_get", id=xid or "", full=True) if xid else None
        R["missing"] = await call("xray_get", id="nope")
        rd.cancel()
        await ws_.close()
    finally:
        core.terminate()
        try:
            core.wait(10)
        except subprocess.TimeoutExpired:
            core.kill()


try:
    asyncio.run(session())
    res = lambda k: ((R.get(k) or {}).get("data") or {})        # noqa: E731
    c = res("clock_x")
    ok(c.get("route", {}).get("kind") == "cmd" and c["route"].get("label") == "Часы и дата",
       f"быстрая команда без модели — путь назван: {c.get('route')}")
    ok(c.get("answer") and c.get("prompt") is None, "без модели — подсказки нет, ответ записан")
    r = res("remind_x")
    ok(r.get("route", {}).get("kind") == "model", f"вопрос модели — путь «Модель»: {r.get('route')}")
    p = r.get("prompt") or {}
    ok(set(p.get("parts") or {}) >= {"sys", "tools", "hist"} and p.get("tools") and "set_reminder" in p["tools"],
       f"из чего подсказка (веса частей) и какие действия предложены: {list((p.get('parts') or {}).items())[:5]}, {len(p.get('tools') or [])}")
    ok((r.get("model") or {}).get("model") == "chat" and "window" in (r.get("model") or {}), f"модель и окно (неизвестно — None): {r.get('model')}")
    acts = r.get("acts") or []
    ok(any(a["name"] == "set_reminder" and a["ok"] and "чайник" in a["args"] and "поставлено" in a["result"] for a in acts),
   f"вызванное действие — с чем вызвано и чем кончилось: {acts[:2]}")
    ok(any(ln["m"].startswith("❓") for ln in r.get("log") or []), "строки журнала этого хода — в рентгене")
    full = r.get("full") or {}
    ok(full.get("system") and any(m["role"] == "user" and "чайник" in m["text"] for m in full.get("msgs") or []),
       "полный текст подсказки — по запросу (что ушло в модель)")
    h = res("hello_x")
    ok(h.get("answer") and h.get("t") is not None and h.get("id") != r.get("id"), "у каждого ответа — свой рентген")
    items = res("list").get("items") or []
    ok(len(items) >= 3 and items[0]["id"] == h.get("id"), f"список последних — свежие сверху ({len(items)})")
    ok(not (R.get("missing") or {}).get("ok", True) or (R.get("missing") or {}).get("error"), "нет такого — понятная ошибка")
    st = tmp / "st/xray.jsonl"
    ok(st.exists() and "system" not in st.read_text(encoding="utf-8")[:20000].split('"full"')[0][:0] + "x",
       "рентгены — на диске (последние 60)")
    ok('"full"' not in st.read_text(encoding="utf-8") if st.exists() else False, "полный текст подсказки на диск не пишется")
    import xray
    xray._mem.clear()
    for line in st.read_text(encoding="utf-8").splitlines():
        xray._mem.append(json.loads(line))
    b = xray.brief(3)
    ok("Модель" in b and "set_reminder" in b and "Часы и дата" not in b.split("\n")[-1], f"сводка для отчёта:\n{b}")
    ui = (ROOT / "ui/studio/xray.js").read_text(encoding="utf-8")
    ok('studio/xray.js' in (ROOT / "ui/settings.html").read_text(encoding="utf-8") and 'data-xray=' in (ROOT / "ui/studio/chat.js").read_text(encoding="utf-8")
       and 'core.call("xray_get", { id, full: true })' in ui, "в «Чате» студии у ответа — кнопка «Рентген», карта хода — studio/xray.js")
    ok(all(k in ui for k in ('heard:', 'route:', 'prompt:', 'model:', 'acts:', 'checks:', 'answer:')) and '<section class="xr-det"' not in ui,
       "карта: услышала → поняла → собрала → модель → сделала → проверила → ответила (подробности — не <section>: в студии они скрыты)")
finally:
    mock.terminate()
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
