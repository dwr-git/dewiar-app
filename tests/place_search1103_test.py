"""№510 (ПК 0.76, 03.11): «Задание найти в Праге номер гостиницы с ванной на неточное время с 1 по 14 января…» (текстом).
Лира искала «Протвин гостиница с ванной номер цена за сутки 2026» и рассказала про гостиницы в Протвино, да ещё «с 1 по
14 января 2026 года» — а сейчас ноябрь 2026, значит, январь 2027.
Теперь:
- место из вопроса («в Праге») должно быть в запросе поиска; его нет, а есть другое слово с большой буквы — поиск не
  выполняется, модель один раз просят искать заново, с местом из вопроса;
- месяц без года — ближайший будущий: к вопросу — «январь — 2027 года», и в поиске, и в ответе."""
import asyncio, json, os, socket, subprocess, sys, tempfile, threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import websockets
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
TESTS = Path(__file__).resolve().parent
PY = os.environ.get("DEWIAR_PY") or sys.executable
tmp = Path(tempfile.mkdtemp())
os.environ["DEWIAR_STATE_DIR"] = str(tmp / "ust"); os.environ["DEWIAR_CONFIG_DIR"] = str(tmp / "ucfg")
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


ASK = ("Задание найти в Праге номер гостиницы с ванной на неточное время с 1 по 14 января за этот промежуток времени "
       "на найти самый дешёвый номер с ванной. На два дня в будни или выходные не имеют значения.")
from quality import ask_places, search_place_fix  # noqa: E402
ok([w for _, w in ask_places(ASK)] == ["Праге"], f"место из вопроса — «в Праге»: {ask_places(ASK)}")
f = search_place_fix(ASK, "Протвин гостиница с ванной номер цена за сутки 2026")
ok("«в Праге»" in f and "«Протвин»" in f and "Повтори поиск" in f, f"запрос с чужим городом — просим искать заново: {f}")
for q in ("Прага гостиница с ванной январь 2027", "Гостиницы Праги с ванной", "hotel Prague bathtub January 2027",
          "гостиница с ванной январь 2027"):
    ok(search_place_fix(ASK, q) == "", f"запрос «{q}» — без повтора")
ok(search_place_fix("Какая погода в Минске завтра?", "погода Москва завтра") != "", "«в Минске» → «Москва» — повтор")
for a, q in (("Что посмотреть в Нижнем Новгороде?", "Нижний Новгород достопримечательности"),
             ("Театры в Санкт-Петербурге", "Санкт-Петербург театры афиша"), ("Билеты в Рим", "Рим авиабилеты"),
             ("Спроси у Маши, что купить", "Маша подарок"), ("Кто такой Илон Маск?", "Илон Маск биография"),
             ("Как сварить борщ?", "Борщ рецепт")):
    ok(search_place_fix(a, q) == "", f"«{a}» → «{q}» — без повтора")

from engine_answer import month_years  # noqa: E402
n = datetime(2026, 11, 3, 21, 0)
m = month_years(ASK, n)
ok("январь — 2027 года" in m and "в запросах поиска" in m, f"«с 1 по 14 января» в ноябре 2026 — январь 2027: {m}")
ok("декабрь — 2026 года" in month_years("Отпуск в декабре", n) and "ноябрь — 2026 года" in month_years("до 20 ноября", n),
   "декабрь и ноябрь — этого года")
ok(month_years("с 1 по 14 января 2027", n) == "" and month_years("Как дела?", n) == "", "год назван или месяца нет — без подсказки")
src = (ROOT / "core/engine_answer.py").read_text(encoding="utf-8")
ok("my = month_years(text, now)" in src, "подсказка о годе — в справке к вопросу про даты")


# ---------- настоящее ядро: «Протвин» не ищется, повтор с Прагой, год 2027 ----------
def free():
    so = socket.socket(); so.bind(("127.0.0.1", 0)); p = so.getsockname()[1]; so.close(); return p


CTX, SEARCHED, TOOLRES = [], [], []


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/search":                              # свой SearXNG
            q = parse_qs(u.query).get("q", [""])[0]
            SEARCHED.append(q)
            b = json.dumps({"results": [{"title": f"Отели: {q}", "url": "https://example.org/h", "content": f"{q} — от 50 €"}]},
                           ensure_ascii=False).encode()
        else:
            b = json.dumps({"data": [{"id": "m"}]}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b)))
        self.end_headers(); self.wfile.write(b)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        msgs = body["messages"]
        users = [m["content"] for m in msgs if m["role"] == "user" and isinstance(m["content"], str)]
        first = next((u for u in reversed(users) if "(Сообщение пользователя)\n" in u), "")
        tres = [m for m in msgs if m["role"] == "tool"]
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()

        def send(delta, fin=None):
            self.wfile.write(f"data: {json.dumps({'choices': [{'delta': delta, 'finish_reason': fin}]}, ensure_ascii=False)}\n\n".encode())

        def search(q, i):
            send({"tool_calls": [{"index": 0, "id": f"s{i}", "type": "function",
                                  "function": {"name": "web_search", "arguments": json.dumps({"query": q}, ensure_ascii=False)}}]})
            send({}, "tool_calls")
        if "Праге" in first:
            CTX.append(first.split("(Сообщение пользователя)\n")[0])
            yr = "2027" if "январь — 2027 года" in first else "2026"
            if not tres:
                search("Протвин гостиница с ванной номер цена за сутки 2026", 1)       # как в журнале №510
            elif len(tres) == 1:
                TOOLRES.append(str(tres[-1].get("content")))
                search(f"Прага гостиница номер с ванной январь {yr}", 2)
            else:
                send({"content": f"В Праге с 1 по 14 января {yr} года самый дешёвый номер с ванной — от 50 € за ночь."}); send({}, "stop")
        else:
            send({"content": "Привет!"}); send({}, "stop")
        self.wfile.write(b"data: [DONE]\n\n")


UP, PORT = free(), free()
srv = ThreadingHTTPServer(("127.0.0.1", UP), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{UP}/v1"
(tmp / "cfg").mkdir()
(tmp / "cfg/settings.json").write_text(json.dumps({
    "persona": "lira", "stt": {"engine": "vosk"}, "tts": {"engine": "off"}, "audio": {"sounds": False}, "ui": {"intro": "done"},
    "report": {"pulse": False}, "team": {"route": False}, "tools": {"search_url": f"http://127.0.0.1:{UP}"},
    "llm": {"active": "m", "tools_probe_v": 5, "tools_modes": {f"{base}|m": "native"},
            "profiles": {"m": {"name": "mock", "kind": "openai", "base_url": base, "model": "m"}}}}, ensure_ascii=False), encoding="utf-8")
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
        m = len(EV)
        await call("say", text=ASK)
        R["a"] = await final(m)
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
now = datetime.now()
want = str(now.year + 1 if now.month > 1 else now.year)
ok(CTX and f"январь — {want} года" in CTX[0], f"к вопросу — какой год у «января» ({want}): {CTX[0][:300] if CTX else ''}")
ok("✋ В запросе поиска нет места из вопроса" in log, "запрос «Протвин…» не выполнен — просим искать заново")
ok(TOOLRES and "«в Праге»" in TOOLRES[0], f"модели сказано, какое место в вопросе: {TOOLRES[0][:160] if TOOLRES else ''}")
ok(SEARCHED and all("Праг" in q for q in SEARCHED) and not any("Протвин" in q for q in SEARCHED), f"искали только Прагу: {SEARCHED}")
ok("Праге" in R.get("a", "") and f"{want} года" in R.get("a", "") and "Протвин" not in R.get("a", ""), f"ответ — про Прагу и {want}: {R.get('a', '')!r}")
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
