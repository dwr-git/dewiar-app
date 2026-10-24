"""Черновики автора голосом (идеи пользователей 24.10: «отдельная папка для голосовых сообщений — пишу книгу, статью,
стихи»): «Лира, запиши в книгу: …» — дословно, без модели, в конец заметки «Заметки/Черновики/Книга» со временем;
«запиши в статью «Как мы строили дом» …» — своё название; «запиши в календарь…», «добавь в список покупок…» — не сюда.
Компьютер (core/engine_tools.py _draft_cmd) и телефон (app.js draftQuick)."""
import asyncio, json, os, shutil, socket, subprocess, sys, tempfile, time
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent; TESTS = ROOT / "tests"
sys.path.insert(0, str(ROOT / "core"))
FAILS = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        FAILS.append(m)


import engine_tools as T  # noqa: E402
for t, want in [("Лира, запиши в книгу: герой проснулся рано утром", ("книгу", None, "герой проснулся рано утром")),
                ("запиши в стихи что осень пахнет яблоками", ("стихи", None, "осень пахнет яблоками")),
                ("добавь в статью «Как мы строили дом» фундамент залили в мае", ("статью", "Как мы строили дом", "фундамент залили в мае")),
                ("запиши в календарь встречу в пятницу", None), ("добавь в список покупок молоко", None), ("запиши в заметки купить хлеб", None)]:
    m = T.DRAFT_RX.match(t)
    got = m and (m.group("kind"), m.group("name"), m.group("body"))
    ok(got == want, f"«{t}» → {got}")


def free():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


tmp = Path(tempfile.mkdtemp()); LLM, PORT = free(), free()
mock = subprocess.Popen([sys.executable, str(TESTS / "mock_llm.py"), str(LLM)])
cfg = tmp / "cfg"; cfg.mkdir()
(cfg / "settings.json").write_text(json.dumps({"persona": "lira", "audio": {"sounds": False}, "ui": {"news_seen": "99.0.0", "welcome": "done"},
    "stt": {"engine": "vosk"}, "tts": {"engine": "off"}, "updates": {"auto_check": False},
    "llm": {"active": "m", "profiles": {"m": {"name": "Мок", "kind": "openai", "base_url": f"http://127.0.0.1:{LLM}/v1", "model": "mock"}}}}))
env = dict(os.environ, DEWIAR_CONFIG_DIR=str(cfg), DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_PORT=str(PORT), DEWIAR_ASSUME_AEC="1",
           DEWIAR_WORKSPACE_DIR=str(tmp / "ws"))
core = subprocess.Popen([sys.executable, str(ROOT / "core/main.py"), "--wav", str(TESTS / "silence90.wav"), "--null-audio"], env=env,
                        stdout=open(tmp / "core.log", "w"), stderr=subprocess.STDOUT)
for _ in range(150):
    time.sleep(0.2)
    if (cfg / "token").exists():
        break
time.sleep(2); tok = (cfg / "token").read_text().strip()
ANS = []


async def go():
    import websockets
    async with websockets.connect(f"ws://127.0.0.1:{PORT}", max_size=None) as ws:
        await ws.send(json.dumps({"cmd": "hello", "token": tok}))
        n = 0
        for t in ["Лира, запиши в книгу: герой проснулся рано утром", "запиши в книгу, что за окном шёл снег и пахло хвоей"]:
            n += 1; await ws.send(json.dumps({"id": n, "cmd": "say", "args": {"text": t}}))
            end = time.time() + 15
            while time.time() < end:
                try:
                    e = json.loads(await asyncio.wait_for(ws.recv(), 1))
                except asyncio.TimeoutError:
                    continue
                if e.get("type") == "answer" and e.get("done"):
                    ANS.append(e.get("text") or ""); break
            await asyncio.sleep(0.6)
try:
    asyncio.run(go())
finally:
    core.terminate(); mock.terminate()
f = tmp / "ws/Заметки/Черновики/Книга.md"
txt = f.read_text(encoding="utf-8") if f.exists() else ""
ok(txt.startswith("# Книга") and "Герой проснулся рано утром." in txt and "За окном шёл снег и пахло хвоей." in txt
   and txt.index("Герой") < txt.index("За окном") and txt.count("*") >= 4, f"компьютер: обе диктовки — дословно, по порядку, со временем: {txt[:300]!r}")
ok(len(ANS) == 2 and ANS[0] == "Записала в «Книгу» — 4 слова." and ANS[1].startswith("Записала в «Книгу»"), f"ответ — коротко, сколько слов: {ANS}")
ok(not list((tmp / "ws/Заметки/Черновики").glob("Книга (*")), "не плодит «Книга (2)» — дописывает")

# телефон
from playwright.sync_api import sync_playwright  # noqa: E402
www = tmp / "www"
shutil.copytree(ROOT / "android/assets/www", www)
for x in ("entities.js", "skins.css", "skins.js", "privacy.js"):
    shutil.copy(ROOT / "ui/assets" / x, www / x)
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                capture_output=True, text=True, check=True).stdout, encoding="utf-8")
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 393, "height": 820}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route("https://**", lambda r: r.abort())
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(900)
    r = pg.evaluate("""async () => { fileSave('notes.json', '[]');
      const a = await quick('Лира, запиши в книгу: герой проснулся рано утром'), b = await quick('запиши в книгу что за окном шёл снег'),
            c = await quick('добавь в статью «Как мы строили дом» фундамент залили в мае'), d = await quick('запиши в календарь встречу в пятницу');
      return [a && a.say, b && b.say, c && c.say, d && d.say, notes().map(x => [x.folder, x.title, x.text])]; }""")
    ns = r[4]
    book = [x for x in ns if x[1] == "Книга"]
    ok(r[0] == "Записала в «Книгу» — 4 слова." and len(book) == 1 and book[0][0] == "Черновики"
       and "Герой проснулся рано утром." in book[0][2] and book[0][2].index("Герой") < book[0][2].index("За окном"), f"телефон: дописывает в «Черновики/Книга»: {r[:2]} {book}")
    ok(any(x[1] == "Как мы строили дом" and x[0] == "Черновики" for x in ns), "своё название в кавычках")
    ok(not (r[3] or "").startswith("Записала в «"), f"«запиши в календарь…» — не черновик: {r[3]!r}")
    ok(not errs, f"без ошибок: {errs[:2]}")
    b.close()
print("\nИТОГ:", "все проверки прошли" if not FAILS else f"не прошло {len(FAILS)}")
sys.exit(1 if FAILS else 0)
