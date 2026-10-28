"""Диктовка удержанием на компьютере (просьба 14.10: «на телефоне удобно диктовать длинное, удерживая кнопку, — на
компьютере она прерывает; нажал — диктуешь сколько хочешь — отправилось, надёжно и предсказуемо»). Настоящее ядро:
— hold_start: ответ замолкает, состояние «слушаю», событие hold; звук берётся с самого нажатия (back_ms из кольца);
— hold_end: весь звук — одним запросом распознавания (паузы не обрывают), текст — вопросом без имени; имя первым
  словом («Патрик, …») переключает персонажа; отмена (увели палец, Esc) — ничего не уходит, «не слушаю»;
— длинная запись режется по самым тихим местам на куски до 20 с, текст склеивается; кусок не распознался — Vosk;
— виджет: удержание облика дольше 0,3 с — hold_start, отпустили — hold_end; короткое нажатие — как раньше (ptt);
  увели в сторону — «Отпустите — отменить» и отмена; пробел — то же удержание; таймер записи в подписи."""
import asyncio, http.server, io, json, os, re, shutil, socket, subprocess, sys, tempfile, threading, time, wave
from pathlib import Path
from types import SimpleNamespace
import numpy as np
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


# ── 1. длинная запись — куски по тихим местам ──
import engine_audio  # noqa: E402
RATE = 16000
sec = 50
a = (np.sin(np.arange(sec * RATE) / RATE * 2 * np.pi * 220) * 8000).astype(np.int16)
for q in (14.0, 31.0):                                     # тихие места — там и резать
    a[int(q * RATE):int((q + 0.3) * RATE)] = 0
got = []


class STT:
    name = "заглушка"

    def __init__(self, bad=()):
        self.bad = bad

    def transcribe(self, pcm):
        got.append(len(pcm) / 2 / RATE)
        if len(got) in self.bad:
            raise RuntimeError("сбой")
        return f"кусок {len(got)}"


me = SimpleNamespace(vosk_stt=SimpleNamespace(name="Vosk", transcribe=lambda pcm: "из воска"))
text = engine_audio.AudioMixin._transcribe_long(me, STT(), a.tobytes())
ok(len(got) == 3 and all(x <= 20.01 for x in got) and abs(got[0] - 14.0) < 0.4 and abs(sum(got) - sec) < 0.1 and text == "кусок 1 кусок 2 кусок 3",
   f"50 с — три куска до 20 с, разрез в тишине (14 с): {[round(x, 1) for x in got]} → «{text}»")
got.clear()
text = engine_audio.AudioMixin._transcribe_long(me, STT(bad=(2,)), a.tobytes())
ok(text == "кусок 1 из воска кусок 3", f"кусок не распознался — его распознал Vosk: «{text}»")
got.clear()
text = engine_audio.AudioMixin._transcribe_long(me, STT(), a[:10 * RATE].tobytes())
ok(len(got) == 1 and text == "кусок 1", "короткая запись — одним куском")

# ── 2. ядро: hold_start / hold_end ──
STT_SEEN, SCRIPT = [], []


class S(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_POST(self):
        raw = self.rfile.read(int(self.headers["Content-Length"]))
        i = raw.find(b"RIFF")
        if i >= 0:
            w = wave.open(io.BytesIO(raw[i:raw.rfind(b"\r\n--")]))
            STT_SEEN.append(w.getnframes() / w.getframerate())
        b = json.dumps({"text": SCRIPT.pop(0) if SCRIPT else ""}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)


stt_srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), S)
threading.Thread(target=stt_srv.serve_forever, daemon=True).start()
tmp = Path(tempfile.mkdtemp())
PORT, LLM = free(), free()
(tmp / "cfg").mkdir()
(tmp / "cfg/settings.json").write_text(json.dumps({
    "persona": "lira", "tts": {"engine": "off"}, "audio": {"sounds": False, "follow_up_seconds": 0},
    "ui": {"welcome": "done"},
    "stt": {"engine": "remote", "remote": {"base_url": f"http://127.0.0.1:{stt_srv.server_address[1]}/v1", "model": "whisper-1"}},
    "llm": {"active": "m", "profiles": {"m": {"name": "mock", "kind": "openai", "base_url": f"http://127.0.0.1:{LLM}/v1", "model": "chat"}}}}))
env = dict(os.environ, DEWIAR_CONFIG_DIR=str(tmp / "cfg"), DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_PORT=str(PORT), DEWIAR_ASSUME_AEC="1",
           DEWIAR_WORKSPACE_DIR=str(tmp / "ws"), NO_PROXY="127.0.0.1,localhost", no_proxy="127.0.0.1,localhost", MOCK_LOG_FULL=str(tmp / "llm.jsonl"))
mock = subprocess.Popen([sys.executable, str(TESTS / "mock_llm.py"), str(LLM)], env=env)
core = subprocess.Popen([PY, str(ROOT / "core/main.py"), "--wav", str(TESTS / "silence90.wav"), "--null-audio"], env=env,
                        stdout=open(tmp / "core.log", "w"), stderr=subprocess.STDOUT)
events, R = [], {}
import websockets  # noqa: E402


async def run():
    ws_ = None
    for _ in range(300):
        await asyncio.sleep(0.2)
        if (tmp / "cfg/token").exists():
            try:
                ws_ = await websockets.connect(f"ws://127.0.0.1:{PORT}", max_size=None); break
            except OSError:
                continue
    await ws_.send(json.dumps({"cmd": "hello", "token": (tmp / "cfg/token").read_text().strip()}))
    n = [0]; replies = {}

    async def call(cmd, **args):
        n[0] += 1; i = n[0]; await ws_.send(json.dumps({"id": i, "cmd": cmd, "args": args}))
        for _ in range(600):
            if i in replies:
                return replies.pop(i)
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
    await asyncio.sleep(3)
    # держат 3 с с паузами (в записи тишина) — одним вопросом
    SCRIPT.append("напиши письмо Игорю о встрече в четверг и не забудь спросить про отчёт")
    events.clear()
    R["start"] = await call("hold_start", back_ms=400)
    R["st_listen"] = await wait_for(lambda e: e["type"] == "state" and e["state"] == "listening", 3)
    R["hold_on"] = await wait_for(lambda e: e["type"] == "hold" and e.get("on"), 3)
    await asyncio.sleep(3.0)
    R["end"] = await call("hold_end")
    R["hold_off"] = await wait_for(lambda e: e["type"] == "hold" and not e.get("on"), 3)
    R["answer"] = await wait_for(lambda e: e["type"] == "answer" and e.get("done"), 30)
    R["stt1"] = list(STT_SEEN)
    await asyncio.sleep(1)
    # имя первым словом — другой персонаж
    SCRIPT.append("Патрик, расскажи короткий анекдот")
    events.clear()
    await call("hold_start"); await asyncio.sleep(1.5); await call("hold_end")
    R["persona"] = await wait_for(lambda e: e["type"] == "persona" or (e["type"] == "state" and e.get("persona") == "patrik"), 15)
    await wait_for(lambda e: e["type"] == "answer" and e.get("done"), 30)
    await asyncio.sleep(1)
    # отмена
    STT_SEEN.clear(); events.clear()
    await call("hold_start"); await asyncio.sleep(1.5)
    R["cancel"] = await call("hold_end", cancel=True)
    R["st_idle"] = await wait_for(lambda e: e["type"] == "state" and e["state"] == "idle", 3)
    await asyncio.sleep(2)
    R["stt_after_cancel"] = list(STT_SEEN)
    # микрофон выключен: удержание и нажатие — разовые, микрофон остаётся выключенным (отзыв 14.10)
    await call("mute", on=True); await asyncio.sleep(1)
    SCRIPT.append("какая завтра погода"); STT_SEEN.clear(); events.clear()
    await call("hold_start")
    R["m_listen"] = await wait_for(lambda e: e["type"] == "state" and e["state"] == "listening", 3)
    await asyncio.sleep(1.5)
    R["m_end"] = await call("hold_end")
    R["m_answer"] = await wait_for(lambda e: e["type"] == "answer" and e.get("done"), 30)
    await asyncio.sleep(2)
    R["m_stt"] = list(STT_SEEN)
    R["m_unmuted"] = [e for e in events if e["type"] == "muted" and not e.get("on")]
    R["m_last"] = [e["state"] for e in events if e["type"] == "state"][-1:]
    events.clear()
    R["m_ptt"] = await call("ptt")
    R["m_ptt_listen"] = await wait_for(lambda e: e["type"] == "state" and e["state"] == "listening", 3)
    await asyncio.sleep(10)                                  # тишина — фраза не сложилась, снова «микрофон выключен»
    R["m_ptt_last"] = [e["state"] for e in events if e["type"] == "state"][-1:]
    R["m_ptt_unmuted"] = [e for e in events if e["type"] == "muted" and not e.get("on")]
    rd.cancel()

try:
    asyncio.run(run())
finally:
    for p in (core, mock):
        p.terminate()
    core.wait()
    stt_srv.shutdown()
log = (tmp / "core.log").read_text(encoding="utf-8")
end = (R.get("end") or {}).get("data") or {}
me = (R.get("m_end") or {}).get("data") or {}
ok(R.get("m_listen") and me.get("ok") and len(R.get("m_stt") or []) == 1 and R.get("m_answer"),
   f"микрофон выключен — удержание слышно и уходит вопросом: {me} {R.get('m_stt')}")
ok(not R.get("m_unmuted") and R.get("m_last") == ["muted"], f"после ответа микрофон снова выключен, сам не включился: {R.get('m_last')} {R.get('m_unmuted')}")
ok(((R.get("m_ptt") or {}).get("data")) == "listening" and R.get("m_ptt_listen") and R.get("m_ptt_last") == ["muted"] and not R.get("m_ptt_unmuted"),
   f"нажатие при выключенном — слушает одну фразу и снова «микрофон выключен»: {R.get('m_ptt')} {R.get('m_ptt_last')}")
ok(R.get("st_listen") and R.get("hold_on"), "hold_start: «слушаю», событие hold")
ok(end.get("ok") and 1.5 <= end.get("sec", 0) <= 4.6 and R.get("hold_off"), f"hold_end: вся запись с самого нажатия (+0,4 с): {end}")
ok(len(R.get("stt1") or []) == 1 and 1.5 <= R["stt1"][0] <= 4.6, f"распознавание — одним запросом, паузы не обрывают: {R.get('stt1')}")
asked = [json.loads(x) for x in (tmp / "llm.jsonl").read_text(encoding="utf-8").splitlines()] if (tmp / "llm.jsonl").exists() else []
users = [m["content"] if isinstance(m["content"], str) else json.dumps(m["content"], ensure_ascii=False) for x in asked for m in x["messages"] if m["role"] == "user"]
ok(any("письмо Игорю о встрече в четверг" in u for u in users), "текст диктовки ушёл вопросом — без имени и без «разговор не со мной»")
ok(R.get("persona") is not None and any("расскажи короткий анекдот" in u and "Патрик" not in u for u in users), "«Патрик, …» первым словом — отвечает Патрик, имя из вопроса убрано")
c = (R.get("cancel") or {}).get("data") or {}
ok(c.get("cancel") and not c.get("ok") and R.get("st_idle") and not R.get("stt_after_cancel"), f"отмена — ничего не распознаётся и не уходит: {c} {R.get('stt_after_cancel')}")
ok("Диктовка удержанием" in log and "Traceback" not in log, "в журнале — понятные строки, без ошибок")

# ── 3. виджет: удержание облика, отмена, пробел ──
from playwright.sync_api import sync_playwright  # noqa: E402
calls, errs = [], []
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 380, "height": 560})
    pg.on("pageerror", lambda x: errs.append(str(x)))
    pg.add_init_script("""window.__calls = [];
      window.DewiarCore = null;""")
    pg.goto((ROOT / "ui/hud.html").as_uri() + "?token=x&port=1"); pg.wait_for_timeout(800)
    # подменяем связь с ядром: запоминаем вызовы, состояние — «покой»
    pg.evaluate("""() => { core.call = (cmd, args) => { window.__calls.push([cmd, args || {}]); return Promise.resolve(cmd === "hold_end" ? { ok: true } : true); };
                           setState("idle"); }""")
    box = pg.locator("#orb").bounding_box(); cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    # короткое нажатие — как раньше
    pg.mouse.move(cx, cy); pg.mouse.down(); pg.wait_for_timeout(120); pg.mouse.up(); pg.wait_for_timeout(200)
    c1 = pg.evaluate("() => window.__calls.map(c => c[0])")
    # удержание 1,4 с — hold_start, подпись с таймером, отпустили — hold_end
    pg.evaluate("() => { window.__calls = []; }")
    pg.mouse.down(); pg.wait_for_timeout(1400)
    say = pg.inner_text("#say"); cls = pg.get_attribute("#bubble", "class")
    pg.mouse.up(); pg.wait_for_timeout(200)
    c2 = pg.evaluate("() => window.__calls")
    # удержание и увели в сторону — отмена
    pg.evaluate("() => { window.__calls = []; }")
    pg.mouse.move(cx, cy); pg.mouse.down(); pg.wait_for_timeout(600); pg.mouse.move(cx + 140, cy + 20, steps=4); pg.wait_for_timeout(150)
    say_far = pg.inner_text("#say"); pg.mouse.up(); pg.wait_for_timeout(200)
    c3 = pg.evaluate("() => window.__calls")
    # пробел
    pg.evaluate("() => { window.__calls = []; document.activeElement && document.activeElement.blur && document.activeElement.blur(); }")
    pg.keyboard.down("Space"); pg.wait_for_timeout(800); pg.keyboard.up("Space"); pg.wait_for_timeout(200)
    c4 = pg.evaluate("() => window.__calls.map(c => c[0])")
    pg.evaluate("() => { window.__calls = []; }")
    pg.keyboard.down("Space"); pg.wait_for_timeout(100); pg.keyboard.up("Space"); pg.wait_for_timeout(200)
    c5 = pg.evaluate("() => window.__calls.map(c => c[0])")
    after = pg.inner_text("#say")
    b.close()
ok(c1 == ["ptt"], f"короткое нажатие на облик — как раньше (ptt): {c1}")
ok([c[0] for c in c2] == ["hold_start", "hold_end"] and not c2[1][1].get("cancel") and c2[0][1].get("back_ms") >= 300,
   f"удержание — hold_start (со звуком с нажатия), отпустили — hold_end: {c2}")
ok(re.match(r"0:0[01] · отпустите — отправлю", say) and "hold" in (cls or ""), f"пока держат — красная точка и время: «{say}» {cls}")
ok(say_far == "Отпустите — отменить" and [c[0] for c in c3] == ["hold_start", "hold_end"] and c3[1][1].get("cancel"), f"увели в сторону — отмена: «{say_far}» {c3}")
ok(c4 == ["hold_start", "hold_end"] and c5 == ["ptt"], f"пробел: держать — диктовка, коротко — как нажатие: {c4} {c5}")
ok("отпустите" not in after, f"после — обычная подпись: «{after}»")
ok(not errs, "без ошибок JavaScript" + (f": {errs}" if errs else ""))
shutil.rmtree(tmp, ignore_errors=True)
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
