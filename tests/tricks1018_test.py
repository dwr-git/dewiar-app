"""«Что я умею» (18.10: «у нас есть функции, про которые никто не знает… включить радио, фонарик, сканер кодов,
очистку мусора — нигде у нас не проговаривается»). Один список — data/tricks.json — на телефоне («Всё» → «Что я
умею», нажатие — сказать фразу), в студии («Что я умею») и в руководстве. Главное — список честный: каждая фраза,
помеченная quick, правда понимается сразу, без модели, — на телефоне (quick()) и на компьютере (настоящее ядро:
ответ без «думаю»)."""
import asyncio, json, os, shutil, socket, subprocess, sys, tempfile, time
from pathlib import Path
import websockets
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
PY = os.environ.get("DEWIAR_PY") or sys.executable
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


T = json.loads((ROOT / "data/tricks.json").read_text(encoding="utf-8"))
items = [x for g in T["groups"] for x in g["items"]]
ok(len(T["groups"]) >= 7 and len(items) >= 40 and all(x["say"] and x["what"] and x["where"] for x in items),
   f"список: {len(T['groups'])} групп, {len(items)} фраз — у каждой «что делает» и где работает")
ok(all(set(x.get("quick", [])) <= set(x["where"]) for x in items), "«сразу» — только там, где фраза вообще работает")
must = ["Включи фонарик", "Открой сканер", "Освободи место", "Включи радио", "Таймер на 5 минут", "Спрячься"]
ok(all(any(x["say"] == m for x in items) for m in must), "есть то, о чём никто не знает: фонарик, сканер, «освободи место», радио, таймер, «спрячься»")

# ---------- телефон: каждая quick-фраза понимается сразу ----------
from playwright.sync_api import sync_playwright  # noqa: E402
tmp = Path(tempfile.mkdtemp()); www = tmp / "www"
shutil.copytree(ROOT / "android/assets/www", www)
for x in ("entities.js", "speechnorm.js", "skins.css", "skins.js"):
    shutil.copy(ROOT / "ui/assets" / x, www / x)
shutil.copytree(ROOT / "ui/assets/live", www / "live", dirs_exist_ok=True)
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                capture_output=True, text=True, check=True).stdout, encoding="utf-8")
(www / "radio.js").write_text("window.RADIO_LIST = " + (ROOT / "data/radio.json").read_text(encoding="utf-8") + ";", encoding="utf-8")
(www / "tricks.js").write_text("window.DEWIAR_TRICKS = " + (ROOT / "data/tricks.json").read_text(encoding="utf-8") + ";", encoding="utf-8")
phone = [x["say"] for x in items if "phone" in x.get("quick", [])]
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 412, "height": 880}); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(1200)
    r = pg.evaluate("""async (qs) => { radio.play = async () => ({ ok: true, station: { name: "Jazz" } });
      const out = {}; for (const q of qs) { let f = null; try { f = await quick(q); } catch (e) { f = { say: "ERR " + e.message }; }
        out[q] = f ? (f.say || (f.switchTo ? "→ " + f.switchTo : f.stop ? "стоп" : "ok")) : null; } return out; }""", phone)
    miss = [q for q, a in r.items() if not a or a.startswith("ERR")]
    ok(not miss, f"телефон: {len(phone)} фраз «сразу» понимаются без модели: не поняты {miss}")
    # экран «Что я умею»: группы, фразы; нажатие — спросить, «…» — в поле ввода
    pg.wait_for_timeout(3000)                    # отложенное от фраз выше (сканер, «Хранилище», листы) — отработало
    pg.evaluate("() => { closeSheets(); try { scanClose && scanClose(); } catch (e) {} }")
    s = pg.evaluate("""async () => { openApps(); await new Promise(r => setTimeout(r, 100)); const btn = document.querySelector("[data-app=tricks]"); if (!btn) return null; btn.click();
      await new Promise(r => setTimeout(r, 300));
      const sh = document.getElementById("sh-tricks"), out = { on: sh && sh.classList.contains("on"), groups: sh ? sh.querySelectorAll(".trg").length : 0,
        chips: sh ? sh.querySelectorAll("[data-say]").length : 0 };
      window._asked = []; const _ask = ask; ask = (t) => { window._asked.push(t); };                       // eslint-disable-line
      sh.querySelector('[data-say="Включи фонарик"]').click(); await new Promise(r => setTimeout(r, 200));
      out.asked = window._asked.slice(); out.closed = !sh.classList.contains("on");
      openApps(); await new Promise(r => setTimeout(r, 100)); document.querySelector("[data-app=tricks]").click(); await new Promise(r => setTimeout(r, 400));
      sh.querySelector('[data-fill="1"]').click(); await new Promise(r => setTimeout(r, 300));
      out.fill = (document.querySelector("#typed") || {}).value || ""; ask = _ask;                  // eslint-disable-line
      return out; }""")
    ok(s and s["on"] and s["groups"] >= 6 and s["chips"] >= 30 and s["asked"] == ["Включи фонарик"] and s["closed"] and s["fill"].endswith("…") is False and len(s["fill"]) > 3,
       f"телефон: «Ещё» → «Что я умею» — группы и фразы; нажатие — сказать, фраза с «…» — в поле дописать: {s}")
    ok(not errs, f"телефон без ошибок: {errs[:2]}")
    b.close()


# ---------- компьютер: настоящее ядро — ответ без модели ----------
def free():
    s_ = socket.socket(); s_.bind(("127.0.0.1", 0)); p_ = s_.getsockname()[1]; s_.close(); return p_


ctmp = Path(tempfile.mkdtemp()); (ctmp / "cfg").mkdir()
PORT, LLM = free(), free()
(ctmp / "cfg/settings.json").write_text(json.dumps({
    "persona": "lira", "llm": {"active": "t", "profiles": {"t": {"name": "Mock", "kind": "openai", "base_url": f"http://127.0.0.1:{LLM}/v1", "disable_thinking": True}}},
    "stt": {"engine": "vosk"}, "tts": {"engine": "off"}, "audio": {"sounds": False, "follow_up_seconds": 0}}))
env = dict(os.environ, DEWIAR_CONFIG_DIR=str(ctmp / "cfg"), DEWIAR_STATE_DIR=str(ctmp / "st"), DEWIAR_PORT=str(PORT),
           DEWIAR_ASSUME_AEC="1", DEWIAR_WORKSPACE_DIR=str(ctmp / "ws"), DEWIAR_DRY_TOOLS=str(ctmp / "dry.jsonl"))
mock = subprocess.Popen([sys.executable, str(ROOT / "tests/mock_llm.py"), str(LLM)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
core = subprocess.Popen([PY, str(ROOT / "core/main.py"), "--wav", str(ROOT / "tests/silence90.wav"), "--null-audio"], env=env,
                        stdout=open(ctmp / "core.log", "w"), stderr=subprocess.STDOUT)
pc = [x["say"] for x in items if "pc" in x.get("quick", [])]
got = {}


async def run():
    ws = None
    for _ in range(200):
        await asyncio.sleep(0.2)
        if (ctmp / "cfg/token").exists():
            try:
                ws = await websockets.connect(f"ws://127.0.0.1:{PORT}", max_size=None); break
            except OSError:
                continue
    await ws.send(json.dumps({"cmd": "hello", "token": (ctmp / "cfg/token").read_text().strip()}))
    ev = []

    async def reader():
        async for raw in ws:
            ev.append(json.loads(raw))
    rd = asyncio.ensure_future(reader())
    await asyncio.sleep(3)
    for i, q in enumerate(pc):
        n0 = len(ev)
        await ws.send(json.dumps({"id": 100 + i, "cmd": "say", "args": {"text": q}}))
        for _ in range(60):
            await asyncio.sleep(0.2)
            new = ev[n0:]
            if any(e.get("type") in ("answer", "window", "sleep", "handoff") and (e.get("done") or e.get("type") != "answer") for e in new) or \
                    any(e.get("type") == "state" and e.get("state") == "thinking" for e in new):
                break
        await asyncio.sleep(0.6)
        new = ev[n0:]
        got[q] = {"model": any(e.get("type") == "state" and e.get("state") == "thinking" for e in new),
                  "said": next((e.get("text") for e in reversed(new) if e.get("type") == "answer" and e.get("text")), "")}
        await ws.send(json.dumps({"id": 900 + i, "cmd": "say", "args": {"text": "отмени выключение"}})) if q == "Выключи компьютер" else None
        await asyncio.sleep(0.3)
    rd.cancel()

try:
    asyncio.run(run())
finally:
    core.terminate(); mock.terminate()
    try:
        core.wait(10)
    except subprocess.TimeoutExpired:
        core.kill()
miss = {q: v for q, v in got.items() if v["model"]}
ok(len(got) == len(pc) and not miss, f"компьютер: {len(pc)} фраз «сразу» — без модели: ушли к модели {list(miss)}")
shutil.rmtree(tmp, ignore_errors=True); shutil.rmtree(ctmp, ignore_errors=True)
print("\nИТОГ:", "всё прошло" if not fails else f"не прошло {len(fails)}")
sys.exit(1 if fails else 0)
