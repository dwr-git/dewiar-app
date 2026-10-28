"""Экономный режим (0.63; план «Идей Лиры»: «простые вопросы — недорогой модели, трудные — сильной: тот же ответ дешевле»).
Свой ключ сервиса: в профиле «Мозга» economy — недорогая модель того же сервиса. «Привет, как дела?» — ей; поручения,
длинное, сложное, с вложениями и после действий — основной; дешёвая не ответила — тот же вопрос основной, человек не
замечает; облаку Dewiar поле не нужно (делит само). Студия — поле и «Подобрать»; телефон — переключатель в «Мозге»."""
import json, os, socket, subprocess, sys, tempfile, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
TESTS = Path(__file__).resolve().parent
PY = os.environ.get("DEWIAR_PY") or sys.executable
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import economy as EC  # noqa: E402

P = {"base_url": "https://openrouter.ai/api/v1", "model": "openai/gpt-4o", "economy": "openai/gpt-4o-mini"}
for t in ("Привет, как дела?", "кто такой Пушкин", "Спасибо, ты лучшая", "сколько лет живут кошки"):
    ok(EC.model_for(P, t) == "openai/gpt-4o-mini", f"простое — недорогой: «{t}»")
for t in ("напомни завтра купить хлеб", "найди в интернете новости", "объясни, почему небо голубое", "напиши стих про осень",
          "какая погода завтра", "x " * 40):
    ok(EC.model_for(P, t) == "", f"поручение, сложное или длинное — основной: «{t.strip()[:30]}»")
ok(EC.model_for(P, "привет", images=True) == "" and EC.model_for(P, "что тут?\n\nВложения: a.pdf") == "", "с картинкой или вложением — основной")
ok(EC.model_for(P, "ок", [{"role": "assistant", "content": "Поставила", "acts": ["set_reminder"]}]) == "", "сразу после действий — основной")
ok(EC.model_for(P, "привет", think=True) == "" and EC.model_for(dict(P, economy=""), "привет") == ""
   and EC.model_for(dict(P, cloud=True), "привет") == "" and EC.model_for(dict(P, economy="openai/gpt-4o"), "привет") == "",
   "выключен, облако Dewiar, та же модель или «подумать» — основной")
ok(EC.suggest(["openai/gpt-4o", "openai/gpt-4o-mini", "anthropic/claude-3.5-haiku"], "openai/gpt-4o") == "openai/gpt-4o-mini"
   and EC.suggest(["claude-sonnet-4-5", "claude-haiku-4-5"], "claude-sonnet-4-5") == "claude-haiku-4-5"
   and EC.suggest(["deepseek-reasoner", "deepseek-chat"], "deepseek-reasoner") == "deepseek-chat"
   and EC.suggest(["text-embedding-3-small", "gpt-4o"], "gpt-4o") == "", "«Подобрать»: mini, haiku, deepseek-chat; не нашлось — пусто")

# ---------- живой ход: какая модель отвечала ----------
SEEN, MODE = [], {"cheap": "ok"}


class LLM(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, code, obj):
        b = json.dumps(obj).encode(); self.send_response(code)
        self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def do_GET(self):
        self._json(200, {"data": [{"id": "big"}, {"id": "small-mini"}]})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        m = body.get("model"); SEEN.append(m)
        if m == "small-mini" and MODE["cheap"] == "down":
            return self._json(503, {"error": {"message": "overloaded"}})
        text = f"Отвечает {m}."
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
        for ch in ({"choices": [{"delta": {"content": text}}]}, {"choices": [{"delta": {}, "finish_reason": "stop"}]}):
            self.wfile.write(f"data: {json.dumps(ch, ensure_ascii=False)}\n\n".encode())
        self.wfile.write(b"data: [DONE]\n\n")


def free():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


srv = ThreadingHTTPServer(("127.0.0.1", 0), LLM); threading.Thread(target=srv.serve_forever, daemon=True).start()
UP, PORT = srv.server_address[1], free()
tmp = Path(tempfile.mkdtemp())
cfg = tmp / "cfg"; cfg.mkdir(); st = tmp / "st"; st.mkdir()
(cfg / "settings.json").write_text(json.dumps({"audio": {"sounds": False}, "ui": {"news_seen": "99.0.0", "welcome": "done"}, "stt": {"engine": "vosk"},
                                               "tts": {"engine": "off"}, "tools": {"enabled_all": False},
                                               "llm": {"active": "m", "profiles": {"m": {"name": "Сервис", "kind": "openai", "base_url": f"http://127.0.0.1:{UP}/v1",
                                                                                          "model": "big", "economy": "small-mini"}}}}))
env = dict(os.environ, DEWIAR_CONFIG_DIR=str(cfg), DEWIAR_STATE_DIR=str(st), DEWIAR_PORT=str(PORT), DEWIAR_ASSUME_AEC="1",
           DEWIAR_WORKSPACE_DIR=str(tmp / "ws"), DEWIAR_FAKE_RAM_GB="16", DEWIAR_FAKE_CORES="8")
core = subprocess.Popen([PY, str(ROOT / "core/main.py"), "--wav", str(TESTS / "silence90.wav"), "--null-audio"], env=env,
                        stdout=open(tmp / "core.log", "w"), stderr=subprocess.STDOUT)
try:
    for _ in range(150):
        time.sleep(0.2)
        if (cfg / "token").exists():
            break
    time.sleep(2)
    from websockets.sync.client import connect
    ws = connect(f"ws://127.0.0.1:{PORT}", open_timeout=10)
    ws.send(json.dumps({"cmd": "hello", "token": (cfg / "token").read_text().strip()})); ws.recv(timeout=10)
    n = [0]

    def ask(text, wait=25):
        n[0] += 1; ws.send(json.dumps({"id": n[0], "cmd": "say", "args": {"text": text}}))
        end = time.time() + wait
        while time.time() < end:
            try:
                e = json.loads(ws.recv(timeout=1))
            except TimeoutError:
                continue
            if e.get("type") == "answer" and e.get("done"):
                return e.get("text", "")
        return ""

    def cmd(name, **args):
        n[0] += 1; ws.send(json.dumps({"id": n[0], "cmd": name, "args": args}))
        end = time.time() + 20
        while time.time() < end:
            e = json.loads(ws.recv(timeout=20))
            if e.get("id") == n[0]:
                return e.get("data")

    SEEN.clear(); a = ask("Привет, как дела?")
    ok(SEEN == ["small-mini"] and "small-mini" in a, f"«привет, как дела?» — ответила недорогая: {SEEN} {a!r}")
    SEEN.clear(); a = ask("разбери подробно мой план на неделю")
    ok(SEEN == ["big"] and "big" in a, f"сложное — основная: {SEEN}")
    MODE["cheap"] = "down"; SEEN.clear(); a = ask("Как настроение?")
    ok(SEEN[:1] == ["small-mini"] and SEEN[-1] == "big" and "big" in a, f"недорогая не ответила — ответила основная, без ошибки: {SEEN} {a!r}")
    r = cmd("llm_economy_suggest", profile={"kind": "openai", "base_url": f"http://127.0.0.1:{UP}/v1", "model": "big"})
    ok(r == {"model": "small-mini", "count": 2}, f"«Подобрать» в студии — недорогая из списка сервиса: {r}")
    ws.close()
    # студия: поле в профиле, «Подобрать» вписывает недорогую, у названия — «экономно»
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(); serr = []
        pg = b.new_page(viewport={"width": 1400, "height": 1000}); pg.on("pageerror", lambda e: serr.append(str(e)))
        pg.goto((ROOT / "ui/settings.html").as_uri() + f"?token={(cfg / 'token').read_text().strip()}&port={PORT}"); time.sleep(3)
        pg.click('nav button[data-p="brain"]'); time.sleep(0.5)
        ok("экономно" in pg.inner_text("#profiles .prof .head"), "студия: у профиля метка «экономно»")
        pg.click("#profiles .prof .head .btn"); time.sleep(0.4)
        pg.fill('#profiles [data-f="economy"]', ""); pg.dispatch_event('#profiles [data-f="economy"]', "change"); time.sleep(1)
        ok("экономно" not in pg.inner_text("#profiles .prof .head"), "пустое поле — режим выключен")
        pg.click('#profiles [data-a="econ"]'); time.sleep(2)
        ok(pg.input_value('#profiles [data-f="economy"]') == "small-mini" and "экономно" in pg.inner_text("#profiles .prof .head"),
           "«Подобрать» — вписала недорогую модель сервиса")
        if os.environ.get("DEWIAR_SHOTS"):
            pg.locator("#profiles .prof").first.screenshot(path=str(Path(os.environ["DEWIAR_SHOTS"]) / "economy-studio.png"))
        b.close()
    ok(not serr, "студия без ошибок" + (f": {serr[:2]}" if serr else ""))
finally:
    core.terminate(); srv.shutdown()
log = (tmp / "core.log").read_text(encoding="utf-8", errors="replace")
ok("💸 Простой вопрос — отвечает недорогая модель «small-mini»" in log and "💸 Недорогая модель «small-mini» не ответила" in log, "в журнале видно, кто отвечал и почему")

# ---------- студия и телефон ----------
bj = (ROOT / "ui/studio/brain.js").read_text(encoding="utf-8")
ok('data-f="economy"' in bj and 'core.call("llm_economy_suggest"' in bj and "econ-tag" in bj, "студия: поле «Экономный режим», «Подобрать», метка «экономно» у профиля")
from playwright.sync_api import sync_playwright  # noqa: E402
www = tmp / "www"
subprocess.run(["bash", str(ROOT / "android/tools/www_assemble.sh"), str(www)], check=True, capture_output=True)
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 412, "height": 900}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(1200)
    r = pg.evaluate("""() => { S.llm = Object.assign({}, DEF.llm, { name: 'OpenRouter', base_url: 'https://openrouter.ai/api/v1', api_key: 'k', model: 'openai/gpt-4o', economy: 'openai/gpt-4o-mini' });
        return [econModel('Привет, как дела?', false), econModel('напомни завтра про хлеб', false), econModel('привет', true),
                econSuggest(['openai/gpt-4o', 'openai/gpt-4o-mini']), (S.llm.cloud = true, econModel('привет', false))]; }""")
    ok(r == ["openai/gpt-4o-mini", "", "", "openai/gpt-4o-mini", ""], f"телефон: то же правило (простое, поручение, вложение, подбор, облако): {r}")
    pg.evaluate("() => { S.llm.cloud = false; openSettings('brain'); }"); pg.wait_for_timeout(500)
    t = pg.inner_text("#br-econ") if pg.locator("#br-econ").count() else ""
    ok("Экономный режим" in t and "openai/gpt-4o-mini" in t and pg.is_checked("#br-econ-on"), f"телефон: в «Мозге» — «Экономный режим», включён, видно модель: {t[:90]!r}")
    pg.evaluate("() => { S.llm = Object.assign({}, DEF.llm, { cloud: true, base_url: 'https://dewiar.pro/dwrapp/cloud.php?p=', api_key: 'dw-x', model: 'x' }); openSettings('brain'); }"); pg.wait_for_timeout(400)
    ok(pg.locator("#br-econ").count() == 0, "облако Dewiar — переключателя нет (делит само)")
    b.close()
ok(not errs, "без ошибок JavaScript" + (f": {errs[:2]}" if errs else ""))
import shutil  # noqa: E402
shutil.rmtree(tmp, ignore_errors=True)
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
