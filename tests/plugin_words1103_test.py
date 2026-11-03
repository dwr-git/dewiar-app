"""№507 (ПК 0.79, 03.11): человек сделал плагин «Луна» (MCP-действие moon_next_phases) и в описании написал «ВСЕГДА
ВЫЗЫВАЙ MCP-ИНСТРУМЕНТ». На «Когда ближайшее полнолуние?» Лира ответила по памяти и неверно («5 ноября»); только на
«С расчётами когда…» вызвала плагин и ответила верно («24 ноября»). Причина: у своего плагина нет поля words, а имя
«Луна» не совпадало ни с «луны», ни с «полнолуние» — просьба к плагину не узнавалась, подсказки не было.
Теперь:
- плагин без words — слова выводятся сами: из названия, подписи, описания и действий его MCP-сервера (по корню:
  «Луна» → луна/луны/лунный, «полнолуние», «фаза»); общие слова («ближайший», «дата») не берутся;
- к вопросу по теме плагина — твёрдая подсказка: вызвать действие и отвечать только по его результату;
- ответила фактами (дата, число) без действия подходящего плагина — один повтор с подсказкой; неверный ответ в итог
  не идёт. Экзамен плагины ставить не умеет — проверка здесь, на подставной модели и настоящем ядре."""
import asyncio, json, os, socket, subprocess, sys, tempfile, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import websockets
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
TESTS = Path(__file__).resolve().parent
PY = os.environ.get("DEWIAR_PY") or sys.executable
tmp = Path(tempfile.mkdtemp())
os.environ["DEWIAR_STATE_DIR"] = str(tmp / "st"); os.environ["DEWIAR_CONFIG_DIR"] = str(tmp / "cfg")
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


# ---------- плагин «Луна», как у человека: без words, тема — в действиях ----------
pd = tmp / "cfg/plugins/moon"
pd.mkdir(parents=True)
(pd / "plugin.json").write_text(json.dumps({
    "id": "moon", "name": "Луна", "icon": "🌙", "category": "Разное", "tagline": "Лунный календарь для вашего города",
    "description": "ВСЕГДА ВЫЗЫВАЙ MCP-ИНСТРУМЕНТ. Точный расчёт по алгоритму, без интернета.",
    "mcp": {"moon": {"type": "stdio", "command": "{python}", "args": ["{plugin_dir}/server.py"]}}}, ensure_ascii=False), encoding="utf-8")
TOOLS = [{"name": "moon_next_phases", "description": "Ближайшие фазы Луны от даты: новолуние, первая четверть, полнолуние, последняя четверть",
          "inputSchema": {"type": "object", "properties": {"from": {"type": "string"}}}, "annotations": {"title": "Ближайшие фазы", "readOnlyHint": True}},
         {"name": "moon_phase", "description": "Фаза Луны и освещённость на дату", "inputSchema": {"type": "object", "properties": {}},
          "annotations": {"title": "Фаза на дату", "readOnlyHint": True}}]
(pd / "server.py").write_text(f"""import json, sys
TOOLS = {json.dumps(TOOLS, ensure_ascii=False)!r}
for line in sys.stdin:
    try:
        m = json.loads(line)
    except ValueError:
        continue
    i = m.get("id")
    if i is None:
        continue
    if m.get("method") == "initialize":
        r = {{"protocolVersion": "2024-11-05", "capabilities": {{"tools": {{}}}}, "serverInfo": {{"name": "moon", "version": "1"}}}}
    elif m.get("method") == "tools/list":
        r = {{"tools": json.loads(TOOLS)}}
    elif m.get("method") == "tools/call":
        r = {{"content": [{{"type": "text", "text": "Ближайшие фазы Луны: полнолуние — 24 ноября 2026, 17:54"}}]}}
    else:
        r = {{}}
    sys.stdout.write(json.dumps({{"jsonrpc": "2.0", "id": i, "result": r}}, ensure_ascii=False) + "\\n"); sys.stdout.flush()
""", encoding="utf-8")

import settings as ST  # noqa: E402
import plugins as PL  # noqa: E402
P = PL.Plugins(ST.Settings(tmp / "s.json"))
P.install("moon")
for pid in ("recruiter", "travel", "artist", "rates", "kitchen", "dacha"):
    P.install(pid)
tt = {"moon": [f"{t['name'].replace('_', ' ')} {t['annotations']['title']} {t['description']}" for t in TOOLS]}
ok((P.match("Когда ближайшее полнолуние?") or {}).get("id") != "moon", "без действий сервера «полнолуния» в плагине нет — не узнаётся (как было)")
P.tool_texts = lambda: tt
aw = P.auto_words(P.items["moon"])
ok({"лун", "полнолу", "фаз", "новолун"} <= aw and not aw & {"ближайш", "дат", "плагин", "вызыва", "всегд", "перв", "последн", "вашег", "интерне", "календа"},
   f"слова плагина выведены: луна, полнолуние, фаза, новолуние — без общих: {sorted(aw)}")
for q, want in (("Когда ближайшее полнолуние?", "moon"), ("Какая фаза Луны сегодня?", "moon"), ("Когда новолуние?", "moon"),
                ("Какая сегодня луна?", "moon"), ("Лунный календарь на неделю", "moon"),
                ("Где ближайшая аптека?", None), ("Какая погода завтра?", None), ("Сколько будет 2+2?", None),
                ("Какой сегодня день недели?", None), ("Когда у мамы день рождения?", None), ("Какие последние новости?", None),
                ("Что у меня в календаре на неделю?", None), ("Как первая помощь при ожоге?", None), ("Почему нет интернета?", None),
                ("Нарисуй кота в шляпе", "artist"), ("Какой курс доллара?", "rates"), ("Разбери резюме в папке", "recruiter")):
    got = (P.match(q) or {}).get("id")
    ok(got == want, f"«{q}» → {want or 'не плагин'} ({got})")
ok(P.auto_words(P.items["artist"]) == set(), "у плагина со своими words ничего не выводится")
h = P.hint_for("Когда ближайшее полнолуние?", {"moon": [("mcp_moon-moon_moon_next_phases", "Ближайшие фазы")]}, {})
ok("«Луна»" in h and "ОБЯЗАТЕЛЬНО вызови" in h and "по памяти не называй" in h, f"твёрдая подсказка: {h[:200]}")

from quality import plugin_skipped  # noqa: E402
A = ["mcp_moon-moon_moon_next_phases"]
f = plugin_skipped("Ближайшее полнолуние — 5 ноября 2026 года.", set(), A, "Луна")
ok(f.startswith("СТОП") and "«Луна»" in f and A[0] in f, "ответ с датой без действия плагина — повтор с подсказкой")
ok(plugin_skipped("Полнолуние — в четверг.", set(), A, "Луна") != "", "день недели — тоже факт")
ok(plugin_skipped("Ближайшее полнолуние — 24 ноября.", {A[0]}, A, "Луна") == "", "действие вызвано — без повтора")
ok(plugin_skipped("Для какого города посчитать?", set(), A, "Луна") == "", "переспросила — без повтора")
ok(plugin_skipped("Луна — спутник Земли, красивая.", set(), A, "Луна") == "", "без дат и чисел — без повтора")
ok(plugin_skipped("5 ноября", set(), [], "") == "", "нет подходящего плагина — без повтора")


# ---------- настоящее ядро: по памяти «5 ноября» → повтор → плагин → «24 ноября» ----------
def free():
    so = socket.socket(); so.bind(("127.0.0.1", 0)); p = so.getsockname()[1]; so.close(); return p


CTX, ASKS = [], []


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        b = json.dumps({"data": [{"id": "m"}]}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b)))
        self.end_headers(); self.wfile.write(b)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        msgs = body["messages"]
        tools = [t["function"]["name"] for t in body.get("tools") or []]
        users = [m["content"] for m in msgs if m["role"] == "user" and isinstance(m["content"], str)]
        last = users[-1].split("(Сообщение пользователя)\n")[-1] if users else ""
        first = next((u for u in reversed(users) if "(Сообщение пользователя)\n" in u), "")
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()

        def send(delta, fin=None):
            self.wfile.write(f"data: {json.dumps({'choices': [{'delta': delta, 'finish_reason': fin}]}, ensure_ascii=False)}\n\n".encode())
        nxt = next((n for n in tools if n.endswith("moon_next_phases")), "")
        if "полнолуние" in first:
            CTX.append(first.split("(Сообщение пользователя)\n")[0])
            ASKS.append(last)
            if msgs[-1]["role"] == "tool":
                send({"content": "Ближайшее полнолуние — 24 ноября 2026 года, в 17:54."}); send({}, "stop")
            elif last.startswith("СТОП. Это вопрос к плагину") and nxt:
                send({"tool_calls": [{"index": 0, "id": "m1", "type": "function", "function": {"name": nxt, "arguments": "{\"from\": \"2026-11-03\"}"}}]})
                send({}, "tool_calls")
            else:
                send({"content": "Ближайшее полнолуние — 5 ноября 2026 года, в четверг."}); send({}, "stop")
        else:
            send({"content": "Привет!"}); send({}, "stop")
        self.wfile.write(b"data: [DONE]\n\n")


UP, PORT = free(), free()
srv = ThreadingHTTPServer(("127.0.0.1", UP), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{UP}/v1"
(tmp / "cfg/settings.json").write_text(json.dumps({
    "persona": "lira", "stt": {"engine": "vosk"}, "tts": {"engine": "off"}, "audio": {"sounds": False}, "ui": {"intro": "done"},
    "report": {"pulse": False}, "team": {"route": False},
    "plugins": {"on": {"moon": {"at": 1, "values": {}, "jobs": {}}}},
    "mcp": {"servers": {"moon-moon": {"type": "stdio", "command": "{python}", "args": ["{plugin_dir}/server.py"], "env": {},
                                      "plugin": "moon", "enabled": True}}},
    "llm": {"active": "m", "tools_probe_v": 5, "tools_modes": {f"{base}|m": "native"},
            "profiles": {"m": {"name": "mock", "kind": "openai", "base_url": base, "model": "m"}}}}, ensure_ascii=False), encoding="utf-8")
env = dict(os.environ, DEWIAR_CONFIG_DIR=str(tmp / "cfg"), DEWIAR_STATE_DIR=str(tmp / "st2"), DEWIAR_PORT=str(PORT), DEWIAR_ASSUME_AEC="1",
           DEWIAR_WORKSPACE_DIR=str(tmp / "ws"), DEWIAR_FAKE_RAM_GB="16", DEWIAR_FAKE_CORES="8")
R, EV = {}, []


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
        cnt, replies = [0], {}

        async def reader():
            async for raw in ws_:
                e = json.loads(raw)
                if e["type"] == "reply":
                    replies[e["id"]] = e
                elif e["type"] != "level":
                    EV.append(e)
        rd = asyncio.ensure_future(reader())

        async def call(cmd, **args):
            cnt[0] += 1; i = cnt[0]
            await ws_.send(json.dumps({"id": i, "cmd": cmd, "args": args}))
            for _ in range(1200):
                if i in replies:
                    return replies.pop(i)
                await asyncio.sleep(0.05)

        async def final(mark, t=40):
            last_n, quiet = -1, 0
            for _ in range(t * 20):
                d = [e for e in EV[mark:] if e["type"] == "answer" and e.get("done")]
                quiet = quiet + 1 if d and len(EV) == last_n else 0
                last_n = len(EV)
                if quiet >= 40:
                    return d[-1].get("text", "")
                await asyncio.sleep(0.05)
            d = [e for e in EV[mark:] if e["type"] == "answer" and e.get("done")]
            return d[-1].get("text", "") if d else ""
        for _ in range(150):
            if "MCP «moon-moon»: подключён" in (tmp / "core.log").read_text(encoding="utf-8", errors="replace"):
                break
            await asyncio.sleep(0.2)
        m = len(EV)
        await call("say", text="Когда ближайшее полнолуние?")
        R["a"] = await final(m)
        R["ev"] = EV[m:]
        rd.cancel(); await ws_.close()
    finally:
        core.terminate()
        try:
            core.wait(10)
        except subprocess.TimeoutExpired:
            core.kill()

asyncio.run(session())
log = (tmp / "core.log").read_text(encoding="utf-8", errors="replace")
srv.shutdown()
ok(CTX and "Это просьба к плагину «Луна»" in CTX[0] and "moon_next_phases" in CTX[0] and "ОБЯЗАТЕЛЬНО вызови" in CTX[0],
   f"к вопросу о полнолунии — твёрдая подсказка вызвать плагин «Луна» ({CTX[0][-220:] if CTX else ''})")
ok("✋ Ответила по памяти, не вызвав плагин «Луна»" in log, "ответ по памяти с датой — повтор с подсказкой")
ok("🛠  mcp_moon-moon_moon_next_phases" in log, "после повтора вызван плагин")
ok("24 ноября" in R.get("a", "") and "5 ноября" not in R.get("a", ""), f"итог — по расчёту плагина, неверное «5 ноября» не осталось: {R.get('a', '')!r}")
ok(log.count("✋ Ответила по памяти") == 1, "повтор — один раз")
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
