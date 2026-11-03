"""№478, №491 (ПК 0.76, 02–03.11): «Спрашивает разрешение, отвечаю „да“ — считает, что это отказ». По журналам:
— №478: модель спросила словами «запустить скрипт?», человек ответил «Да» (микрофон не слышал — набирал) — и тут же второй
  вопрос «Выполнить?»; через 15 с тишины — «Подтверждение: нет», и Лира «не разрешили». Теперь: короткое «да» на вопрос
  ассистента — это и есть ответ на первое «Выполнить?» за ход (опасное защита всё равно спрашивает); ждём 30 с (в текстовом
  режиме 90), а молчание — не «нет»: модели — «ответа не было, спроси ещё раз», в окне — «ответа не было».
— №491: на «Выполнить?» набрали «давай» — это ушло новым вопросом, ход отменился, подтверждение засчиталось как «нет».
  Теперь короткий набранный ответ, пока ждём «да/нет», — ответ на вопрос.
— «Да.», «да, давай», «разрешаю», «одобряю», «так точно», «не против» — да; «нет, давай потом», «да нет, не надо» — нет."""
import asyncio, json, os, queue, socket, subprocess, sys, tempfile, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
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


from engine_tools import ToolsMixin, confirm_word  # noqa: E402
from engine_base import Turn  # noqa: E402

YES = ["да", "Да.", "ДА!", "да, давай", "Давай", "ага", "угу", "разрешаю", "Я же разрешаю", "одобряю", "так точно", "не против",
       "подтверждаю", "запускай", "действуй", "ок", "Хорошо, выполняй", "давай, я одобряю, действуй", "конечно"]
NO = ["нет", "Нет.", "не надо", "да нет, не нужно", "нет, давай потом", "отмена", "стоп", "подожди", "не разрешаю"]
OTHER = ["а что это за команда", "почему", "расскажи подробнее", "а можно подробнее?", "ты точно уверена?"]
ok(all(confirm_word(t) is True for t in YES), f"«да» во всех формах: {[t for t in YES if confirm_word(t) is not True]}")
ok(all(confirm_word(t) is False for t in NO), f"«нет» во всех формах (отрицание сильнее): {[t for t in NO if confirm_word(t) is not False]}")
ok(all(confirm_word(t) is None for t in OTHER), f"не ответ — ждём дальше: {[t for t in OTHER if confirm_word(t) is not None]}")


class FakeBox:
    def policy(self, n):
        return True, True

    def title(self, n):
        return "Команды терминала"

    def guard(self, n, a):
        return None, False, None

    def auto_ok(self, n, a):
        return False

    def describe(self, n, a):
        return f"Выполнить команду: {a.get('command')}?"

    def run(self, n, a):
        RAN.append(a)
        return "код выхода 0 1103"


RAN = []


class E(ToolsMixin):
    def __init__(self):
        self.pending_confirm, self.events, self.follow_up_until, self.history, self.last_turn_time = None, [], 0, [], 0.0
        self.toolbox = FakeBox()

    def emit(self, k, **d):
        self.events.append((k, d))

    def set_state(self, s):
        pass


def drained():
    q = queue.Queue()

    def run():
        while True:
            x = q.get()
            if isinstance(x, tuple):
                x[1].set()
    threading.Thread(target=run, daemon=True).start()
    return q


e = E()
for txt, want in (("Да.", True), ("да, давай", True), ("нет, давай потом", False)):
    out = {}
    th = threading.Thread(target=lambda: out.update(r=e._confirm(Turn(1), "Выполнить команду: echo 1?", drained(), timeout=5)))
    th.start()
    for _ in range(50):
        if e.pending_confirm:
            break
        time.sleep(0.05)
    e._answer_confirm(txt)
    th.join(6)
    ok(out.get("r") is want, f"«Выполнить?» → «{txt}» → {want}")
t0 = time.monotonic()
r = e._confirm(Turn(2), "Выполнить команду: echo 2?", drained(), timeout=1)
ok(r is None and time.monotonic() - t0 < 4, f"молчание — не «нет», а «ответа не было»: {r}")
src = (ROOT / "core/engine_tools.py").read_text(encoding="utf-8")
ok("timeout = 90 if" in src and "else 30" in src, "ждём 30 с, в текстовом режиме — 90 (было 15)")

# первое «Выполнить?» после «да» на вопрос ассистента — уже отвечено
e = E()
e.history = [{"role": "user", "content": "прочитай протоколы"}, {"role": "assistant", "content": "Нужен скрипт на Python. Запустить?"}]
e.last_turn_time = time.monotonic()
t = Turn(3); t.asked = "Да"
res = e._use_tool(t, {"name": "run_command", "args": {"command": "echo 1103"}}, drained())
ok(RAN and "1103" in str(res) and not any(k == "confirm" for k, _ in e.events), f"«Да» на вопрос «Запустить?» — выполнено без второго вопроса: {res}")
RAN.clear(); e.events = []
t = Turn(4); t.asked = "Да"
e.history[-1] = {"role": "assistant", "content": "Готово, всё прочитала."}         # ассистент ни о чём не спрашивал
th = threading.Thread(target=lambda: e._use_tool(t, {"name": "run_command", "args": {"command": "echo x"}}, drained()))
th.start()
for _ in range(50):
    if e.pending_confirm:
        break
    time.sleep(0.05)
ok(e.pending_confirm is not None, "«да» без вопроса ассистента — «Выполнить?» спрашиваем как обычно")
e._answer_confirm("нет"); th.join(6)
t = Turn(5); t.asked = "Да, и ещё скачай всё из интернета и установи все программы, какие найдёшь"
e.history[-1] = {"role": "assistant", "content": "Запустить?"}
ok(not e._just_agreed(t), "длинная просьба — не короткое «да»")
e.last_turn_time = time.monotonic() - 600
t.asked = "да"
ok(not e._just_agreed(t), "вопрос ассистента был давно (больше 5 минут) — спрашиваем")

# молчание: модели — не «отказался»
e = E()
e._confirm = lambda *a, **k: None
res = e._use_tool(Turn(6), {"name": "run_command", "args": {"command": "echo y"}}, drained())
ok("НЕ отказ" in res and not res.startswith("Пользователь отказался") and not RAN, f"молчание: модели — «ответа не было, спроси ещё раз»: {res[:90]}")
ok(any(k == "tool" and d.get("error", "").startswith("ответа не было") for k, d in e.events), "в окне: «ответа не было — спрошу ещё раз»")


# ---------- настоящее ядро: набранное «давай», пока ждём «Выполнить?» ----------
def free():
    so = socket.socket(); so.bind(("127.0.0.1", 0)); p = so.getsockname()[1]; so.close(); return p


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
        users = [m["content"].split("(Сообщение пользователя)\n")[-1] for m in msgs if m["role"] == "user" and isinstance(m["content"], str)]
        last = users[-1] if users else ""
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()

        def send(delta, fin=None):
            self.wfile.write(f"data: {json.dumps({'choices': [{'delta': delta, 'finish_reason': fin}]}, ensure_ascii=False)}\n\n".encode())
        if msgs[-1]["role"] == "tool":
            res = str(msgs[-1].get("content"))
            send({"content": "Готово, вывод: 1103." if "1103" in res else "Не выполнила: " + res[:60]}); send({}, "stop")
        elif "Проверь систему" in last:
            send({"content": "Для этого запущу короткую команду в терминале. Запустить?"}); send({}, "stop")
        elif "Выведи число" in last or last.strip().lower().startswith("да"):
            send({"tool_calls": [{"index": 0, "id": "c1", "type": "function", "function": {"name": "run_command",
                  "arguments": json.dumps({"command": "echo 1103"})}}]}); send({}, "tool_calls")
        else:
            send({"content": "Хорошо."}); send({}, "stop")
        self.wfile.write(b"data: [DONE]\n\n")


UP, PORT = free(), free()
srv = ThreadingHTTPServer(("127.0.0.1", UP), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
tmp = Path(tempfile.mkdtemp())
(tmp / "cfg").mkdir()
base = f"http://127.0.0.1:{UP}/v1"
(tmp / "cfg/settings.json").write_text(json.dumps({
    "persona": "lira", "stt": {"engine": "vosk"}, "tts": {"engine": "off"}, "audio": {"sounds": False}, "ui": {"intro": "done"},
    "report": {"pulse": False}, "team": {"route": False},
    "llm": {"active": "m", "tools_probe_v": 5, "tools_modes": {f"{base}|m": "native"},
            "profiles": {"m": {"name": "mock", "kind": "openai", "base_url": base, "model": "m"}}}}), encoding="utf-8")
env = dict(os.environ, DEWIAR_CONFIG_DIR=str(tmp / "cfg"), DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_PORT=str(PORT), DEWIAR_ASSUME_AEC="1",
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
                e_ = json.loads(raw)
                if e_["type"] == "reply":
                    replies[e_["id"]] = e_
                elif e_["type"] != "level":
                    EV.append(e_)
        rd = asyncio.ensure_future(reader())

        async def call(cmd, **args):
            cnt[0] += 1; i = cnt[0]
            await ws_.send(json.dumps({"id": i, "cmd": cmd, "args": args}))
            for _ in range(1200):
                if i in replies:
                    return replies.pop(i)
                await asyncio.sleep(0.05)

        async def final(mark, t=30):
            last_n, quiet = -1, 0
            for _ in range(t * 20):
                d = [x for x in EV[mark:] if x["type"] == "answer" and x.get("done")]
                quiet = quiet + 1 if d and len(EV) == last_n else 0
                last_n = len(EV)
                if quiet >= 30:
                    return d[-1].get("text", "")
                await asyncio.sleep(0.05)
            d = [x for x in EV[mark:] if x["type"] == "answer" and x.get("done")]
            return d[-1].get("text", "") if d else ""
        # №491: «Выполнить?» — набрали «давай»
        m = len(EV)
        await call("say", text="Выведи число в терминале")
        for _ in range(200):
            if any(x["type"] == "confirm" for x in EV[m:]):
                break
            await asyncio.sleep(0.05)
        R["asked"] = any(x["type"] == "confirm" for x in EV[m:])
        await call("say", text="давай")
        R["typed"] = await final(m)
        await asyncio.sleep(0.5)
        # №478: «Запустить?» — «Да» — без второго вопроса
        m = len(EV)
        await call("say", text="Проверь систему")
        R["q"] = await final(m)
        m = len(EV)
        await call("say", text="Да")
        R["yes"] = await final(m)
        R["yes_confirm"] = any(x["type"] == "confirm" for x in EV[m:])
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
ok(R.get("asked") and "Подтверждение набрано: «давай»" in log and "❓ давай" not in log,
   "№491: набранное «давай» на «Выполнить?» — ответ на вопрос, а не новый вопрос")
ok("1103" in R.get("typed", ""), f"и команда выполнена: {R.get('typed', '')[-60:]!r}")
ok(R.get("q", "").rstrip().endswith("Запустить?"), f"модель спросила словами: {R.get('q', '')[-40:]!r}")
ok("1103" in R.get("yes", "") and not R.get("yes_confirm") and "только что ответили" in log,
   f"№478: «Да» на «Запустить?» — выполнено без второго «Выполнить?»: {R.get('yes', '')[-60:]!r}")
ok("Подтверждение: нет" not in log, "ни одного «нет», которого человек не говорил")
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
