"""№461, №463, №483 (ПК 0.76, 01–02.11): «плагины не работают — Лира говорит „сейчас всё сделаю / собираю список / сейчас
посмотрю“ (бывает дважды) — и больше ничего: ни статуса работы, ни ответа». По журналам: модель (облако, «chat») ни разу не
вызвала ни навык, ни действие плагина — отвечала обещанием. Проверка «обещал, но не сделал» не узнавала «Собираю список.»,
«Смотрю, что лежит в папке…», «Сейчас нарисую…», а после одной просьбы сделать сдавалась — и ход кончался обещанием.
Теперь: просьба к установленному плагину — в справке к вопросу его навык и действия (или что сервер не запустился);
обещание узнаётся и в этих формах; просим сделать до двух раз; не взялась и тогда — честно говорим, что ничего не сделано.
Шаг плагина в виджете и «Чате» подписан по-человечески: «Плагин «Рекрутер»: разобрать резюме…».
№461 ещё: путь к папке с резюме — кнопкой «Выбрать папку…» (тип настройки folder)."""
import asyncio, json, os, socket, subprocess, sys, tempfile, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
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


# ---------- обещание без действия: формы из журналов ----------
from quality import PROMISE_GIVEUP, looks_like_promise, promise_nudge  # noqa: E402
PROM = ["Смотрю, что лежит в папке с резюме.", "Собираю список.", "Сейчас нарисую логотип для кофейни «Зерно».",
        "Сейчас посмотрю, какие резюме есть, и сравню их под бухгалтера.", "Хорошо, ищу тендеры на видеонаблюдение.",
        "Нашла 4 файла. Сейчас прочитаю протокол и положения, затем отвечу."]
REAL = ["Собираю: паспорт, страховка, зарядка, крем от солнца.", "Какой город?", "Привет! Всё хорошо.", "В Дубае +31, возьмите панаму.",
        "Пишу на русском и английском, если нужно.", "Готово: логотип в папке «Рисунки».", "Читаю тебе сказку: жил-был кот."]
ok(all(looks_like_promise(t) for t in PROM), f"обещания из журналов узнаются: {[t for t in PROM if not looks_like_promise(t)]}")
ok(not any(looks_like_promise(t) for t in REAL), f"ответы по делу — не обещания: {[t for t in REAL if looks_like_promise(t)]}")
ok(not looks_like_promise("Смотрю в окно и жду тебя.", "Что делаешь?") and not looks_like_promise("Занимаюсь своими делами.", "Чем занимаешься?")
   and not looks_like_promise("Считаю, что лучше взять зонт.") and looks_like_promise("Смотрю, что лежит в папке.", "Разбери резюме в папке"),
   "«что делаешь?» — «смотрю в окно» — ответ о себе, а не обещание")
n2 = promise_nudge(False, again=True, hint="Это просьба к плагину «Рекрутер»")
ok("снова" in n2 and "ТОЛЬКО" in n2 and "«Рекрутер»" in n2, "второй раз за ход — жёстче и с действиями плагина")
ok("ничего не сделано" in PROMISE_GIVEUP and "взял" not in PROMISE_GIVEUP, "не взялась — честная фраза (без рода: и для Патрика)")

# ---------- просьба к плагину: какой и чем делать ----------
import settings as ST  # noqa: E402
import plugins as PL  # noqa: E402
import mcp as M  # noqa: E402
s = ST.Settings(tmp / "s.json")
P = PL.Plugins(s)
for pid in ("recruiter", "travel", "artist", "rates"):
    P.install(pid)
for q, want in (("Разбери резюме в папке", "recruiter"), ("Кто лучше всех подходит на бухгалтера?", "recruiter"),
                ("ОАЭ с 3 по 10 ноября. Путешествие. Что взять и что может понадобиться.", "travel"),
                ("Нарисуй логотип для кофейни «Зерно»", "artist"), ("Сколько будет 2+2?", None), ("Привет, как дела?", None),
                ("Какая погода завтра?", None), ("Сколько сейчас времени?", None),
                # 03.11: «Художник» на своей модели — «не умею рисовать, такого плагина нет»: «нарисуй …» — к нему
                ("Нарисуй кота в шляпе", "artist"), ("Сделай открытку для бабушки", "artist"), ("Какой курс доллара?", "rates"),
                ("Что у меня записано про отпуск?", None), ("Найди в документах договор аренды", None), ("Утреннюю сводку", None)):
    got = (P.match(q) or {}).get("id")
    ok(got == want, f"«{q}» → {want or 'не плагин'} ({got})")
h = P.hint_for("Разбери резюме в папке", {"recruiter": [("mcp_recruiter-main_recruit_add", "Разобрать резюме")]}, {})
ok("«Рекрутер»" in h and "use_skill recruiter" in h and "mcp_recruiter-main_recruit_add — «Разобрать резюме»" in h and "сразу" in h,
   f"справка: навык и действия плагина, делать сразу: {h[:160]}")
h = P.hint_for("Разбери резюме в папке", {}, {"recruiter": "не найдена программа"})
ok("не работают" in h and "не найдена программа" in h, "сервер плагина не запустился — честно сказать, а не обещать")
ok("use_skill travel-buddy" in P.hint_for("Путешествие в ОАЭ — что взять?"), "плагин без своего кода — его навык")
ok(P.hint_for("Сколько будет 2+2?") == "", "обычный вопрос — без справки о плагинах")
src = (ROOT / "core/engine_answer.py").read_text(encoding="utf-8")
ok("keep=self._plugin_keep(text)" in src and "in keep]" in src, "маленькое окно модели: действия плагина, к которому просьба, не выбрасываются")

# ---------- подпись шага плагина ----------
s.update({"plugins": {"on": {"recruiter": {"at": 1, "values": {"folder": str(tmp / "cv")}, "jobs": {}}}}})
mgr = M.MCPManager(s)
mgr.reconcile()
for _ in range(150):
    if (mgr.status().get("recruiter-main") or {}).get("status") in ("ok", "error"):
        break
    time.sleep(0.1)
pt = mgr.plugin_tools().get("recruiter") or []
add = next((n for n, _ in pt if n.endswith("recruit_add")), "")
ok(add and dict(pt)[add] == "Разобрать резюме", f"действия плагина с названиями: {pt[:3]}")
ok(add and mgr.title(add) == "Плагин «Рекрутер»: разобрать резюме", f"шаг в виджете и «Чате»: {mgr.title(add) if add else ''}")
ok(mgr.plugin_errors() == {}, "ошибок запуска нет")
mgr.close()
srvx = M.Server("x-main", {"plugin": "recruiter"}); srvx.status, srvx.error = "error", "сервер MCP не ответил вовремя"
mgr.servers = {"x-main": srvx}
ok(mgr.plugin_errors() == {"recruiter": "сервер MCP не ответил вовремя"}, "сервер плагина упал — видно, какой и почему")
mgr.servers = {}

# ---------- №461: папка — кнопкой ----------
pj = json.loads((ROOT / "data/plugins/recruiter/plugin.json").read_text(encoding="utf-8"))
ok(next(x for x in pj["settings"] if x["key"] == "folder")["type"] == "folder", "«Папка с резюме» — поле-папка")
ok(next(x for x in P.items["recruiter"]["settings"] if x["key"] == "folder")["type"] == "folder", "ядро знает тип folder")
js = (ROOT / "ui/studio/plugins.js").read_text(encoding="utf-8")
ok('s.type === "folder"' in js and "Выбрать папку…" in js and "pick_folder" in js and 'run("plugin_values"' in js,
   "студия: «Выбрать папку…» — системный диалог, выбранная папка сразу сохраняется")
ok(".pld-dir" in (ROOT / "ui/studio/studio.css").read_text(encoding="utf-8"), "поле и кнопка — в одну строку")
r = subprocess.run(["node", "--check", str(ROOT / "ui/studio/plugins.js")], capture_output=True, text=True)
ok(r.returncode == 0, f"plugins.js без ошибок синтаксиса {r.stderr[-200:]}")


# ---------- настоящее ядро: «сейчас посмотрю» дважды → действие плагина; «Собираю список.» до конца → честно ----------
def free():
    so = socket.socket(); so.bind(("127.0.0.1", 0)); p = so.getsockname()[1]; so.close(); return p


CTX = []


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
        if "резюме" in first:
            CTX.append(first.split("(Сообщение пользователя)\n")[0])
            add_ = next((n for n in tools if n.endswith("recruit_add")), "")
            if msgs[-1]["role"] == "tool":
                send({"content": "Разобрала: новое резюме одно — бухгалтер, стаж пять лет."}); send({}, "stop")
            elif last.startswith("СТОП. Ты снова") and add_:
                send({"tool_calls": [{"index": 0, "id": "a1", "type": "function", "function": {"name": add_, "arguments": "{}"}}]})
                send({}, "tool_calls")
            elif last.startswith("СТОП"):
                send({"content": "Сейчас посмотрю, что в папке."}); send({}, "stop")
            else:
                send({"content": "Смотрю, что лежит в папке с резюме."}); send({}, "stop")
        else:
            send({"content": "Собираю список."}); send({}, "stop")
        self.wfile.write(b"data: [DONE]\n\n")


UP, PORT = free(), free()
srv = ThreadingHTTPServer(("127.0.0.1", UP), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
(tmp / "cfg").mkdir()
(tmp / "cv").mkdir(exist_ok=True)
(tmp / "cv/Кандидат.txt").write_text("Петров Пётр\nБухгалтер\nОпыт работы — 5 лет\n1С, отчётность\n", encoding="utf-8")
base = f"http://127.0.0.1:{UP}/v1"
(tmp / "cfg/settings.json").write_text(json.dumps({
    "persona": "lira", "stt": {"engine": "vosk"}, "tts": {"engine": "off"}, "audio": {"sounds": False}, "ui": {"intro": "done"},
    "report": {"pulse": False}, "team": {"route": False},
    "plugins": {"on": {"recruiter": {"at": 1, "values": {"folder": str(tmp / "cv")}, "jobs": {}}, "travel": {"at": 1, "values": {}, "jobs": {}}}},
    "mcp": {"servers": {"recruiter-main": {"type": "stdio", "command": "{python}", "args": ["{plugin_dir}/server.py"], "env": {},
                                           "plugin": "recruiter", "enabled": True}}},
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
        for _ in range(150):                                 # сервер плагина подключился
            if "MCP «recruiter-main»: подключён" in (tmp / "core.log").read_text(encoding="utf-8", errors="replace"):
                break
            await asyncio.sleep(0.2)
        for q, key in (("Разбери резюме в папке", "cv"), ("ОАЭ с 3 по 10 ноября. Путешествие. Что взять?", "trip")):
            m = len(EV)
            await call("say", text=q)
            R[key] = await final(m)
            R[key + "_ev"] = EV[m:]
            await asyncio.sleep(1.0)
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
ok(CTX and "Это просьба к плагину «Рекрутер»" in CTX[0] and "recruit_add" in CTX[0], f"справка к вопросу: плагин и его действия ({CTX[0][-200:] if CTX else ''})")
ok("✋ Модель только пообещала — прошу сделать, а не обещать (ещё раз)" in log, "обещание дважды — просим второй раз")
steps = [e for e in R["cv_ev"] if e["type"] == "tool"]
ok(any(e.get("status") == "run" and e.get("title") == "Плагин «Рекрутер»: разобрать резюме" for e in steps),
   f"пока плагин работает — шаг «Плагин «Рекрутер»: разобрать резюме…»: {[(e.get('title'), e.get('status')) for e in steps]}")
ok(any(e.get("status") == "done" for e in steps) and "Разобрала" in R["cv"], f"плагин сделал, ответ по результату: {R['cv'][-80:]!r}")
ok(PROMISE_GIVEUP in R["trip"] and "✋ Модель так и не взялась" in log,
   f"«Собираю список.» и после двух просьб — честно: ничего не сделано: {R['trip'][-120:]!r}")
ok("🧩 Это просьба к плагину «Путешествие»" in log, "в журнале видно, к какому плагину просьба")
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
