"""№522 (04.11, своя модель в LM Studio): «Не все инструменты работают, в частности работа с удалённым сервером». Модель писала
вызов действия ТЕКСТОМ — «[вызваны инструменты: load_skill …, run_command (command: ssh …)] Жду вывод — как дойдёт,
отчитаюсь», «[run_command: pip install python-docx --quiet] Жду результат установки» — и ход кончался: ничего не
выполнено, а человек ждёт. Теперь: такой текст — то же обещание (quality.fake_call): не озвучивается и не остаётся в
ответе, модель просят вызвать действие по-настоящему (FAKE_NUDGE); не взялась и после двух просьб — честно: «эта модель
пишет действия словами, а не выполняет их» (FAKE_GIVEUP), без выдуманного вызова в тексте.
№524 (вторая часть, разобрал сам человек): справочное действие вместе с обычным (calc + world_time) без слов после — не
попадало ни в «ответь по найденному», ни в «Готово.», и выходило «модель вернула пустой ответ».
Настоящее ядро по wav-файлу и своя модель-заглушка; адреса и имена — выдуманные."""
import asyncio, json, os, socket, subprocess, sys, tempfile, threading
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


def free():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


import quality  # noqa: E402
NAMES = {"run_command", "load_skill", "web_search", "world_time"}
FAKE = ["Поняла — проверяю. Загружаю навык «Статус сервера»:\n[вызваны инструменты: load_skill test-server-status, run_command "
        "(command: ssh admin@10.0.0.9 \"df -h\")]\nЖду вывод по свободному месту — как дойдёт, отчитаюсь.",
        "Сначала установлю библиотеку: [run_command: pip install python-docx --quiet] Жду результат установки.",
        "Выполняю run_command(command=\"df -h\") — секунду."]
REAL = ["На диске свободно 120 ГБ из 500.", "Могу проверить место командой df -h — запустить?", "Пример ссылки: [сайт] — откройте её.",
        "Есть инструмент run_command — им я запускаю команды.", "Вот ответ: [1] первый пункт, [2] второй пункт."]
ok(all(quality.fake_call(t, NAMES) for t in FAKE), f"вызов текстом узнаётся: {[t[:40] for t in FAKE if not quality.fake_call(t, NAMES)]}")
ok(not any(quality.fake_call(t, NAMES) for t in REAL), f"обычный ответ — не вызов: {[t for t in REAL if quality.fake_call(t, NAMES)]}")
ok(quality.hold_sentence("Проверь место", "Проверь место", FAKE[1], (), NAMES), "фраза с выдуманным вызовом не озвучивается")

N = {"stubborn": 0}


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
        user = users[-1] if users else ""
        first = next((u for u in reversed(users) if not u.startswith(("СТОП", "Ответь мне сейчас", "<tool_response>"))), "")
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()

        def send(delta, fin=None):
            self.wfile.write(f"data: {json.dumps({'choices': [{'delta': delta, 'finish_reason': fin}]}, ensure_ascii=False)}\n\n".encode())
        if "дробь" in first or "кубик" in first:          # №524: справочное (calc) и действие (world_time) за один шаг, потом — пробел
            if "Ответь мне сейчас словами" in user and "дробь" in first:
                send({"content": "Получилось 0,75, а в Москве сейчас утро."}); send({}, "stop")
            elif msgs[-1]["role"] == "tool" or user.startswith(("Ответь мне сейчас словами", "<tool_response>")):
                send({"content": " "}); send({}, "stop")
            else:
                send({"tool_calls": [{"index": 0, "id": "c1", "type": "function", "function": {"name": "calc", "arguments": json.dumps({"expression": "3/4"})}},
                                     {"index": 1, "id": "c2", "type": "function", "function": {"name": "world_time", "arguments": json.dumps({"city": "Москва"}, ensure_ascii=False)}}]})
                send({}, "tool_calls")
        elif "Токио" in first:                                  # послушная: после просьбы вызывает по-настоящему
            if msgs[-1]["role"] == "tool":
                send({"content": "В Токио сейчас вечер — время из часов."}); send({}, "stop")
            elif user.startswith("СТОП. Ты написал(а) вызов действия ТЕКСТОМ"):
                send({"tool_calls": [{"index": 0, "id": "w1", "type": "function", "function": {"name": "world_time",
                      "arguments": json.dumps({"city": "Токио"}, ensure_ascii=False)}}]}); send({}, "tool_calls")
            else:
                send({"content": "Смотрю часы: [world_time: Токио] Жду результат."}); send({}, "stop")
        elif "сервер" in first:                                # упрямая: только текстом
            N["stubborn"] += 1
            send({"content": "Подключаюсь к серверу.\n[вызваны инструменты: run_command (command: ssh admin@10.0.0.9 \"df -h\")]\n"
                             "Жду вывод — как дойдёт, отчитаюсь."}); send({}, "stop")
        else:
            send({"content": "Привет!"}); send({}, "stop")
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
            "profiles": {"m": {"name": "mock", "kind": "openai", "base_url": base, "model": "m"}}}}))
env = dict(os.environ, DEWIAR_CONFIG_DIR=str(tmp / "cfg"), DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_PORT=str(PORT), DEWIAR_ASSUME_AEC="1",
           DEWIAR_WORKSPACE_DIR=str(tmp / "ws"), DEWIAR_FAKE_RAM_GB="16", DEWIAR_FAKE_CORES="8")
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
        cnt, replies, events = [0], {}, []

        async def reader():
            async for raw in ws_:
                e = json.loads(raw)
                if e["type"] == "reply":
                    replies[e["id"]] = e
                elif e["type"] != "level":
                    events.append(e)
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
                d = [e for e in events[mark:] if e["type"] == "answer" and e.get("done")]
                quiet = quiet + 1 if d and len(events) == last_n else 0
                last_n = len(events)
                if quiet >= 40:
                    return d[-1].get("text", "")
                await asyncio.sleep(0.05)
            d = [e for e in events[mark:] if e["type"] == "answer" and e.get("done")]
            return d[-1].get("text", "") if d else ""
        for q, key in (("Посмотри по часам, который час в городе Токио", "tokyo"), ("Проверь место на диске сервера Прокс", "server"),
                       ("Переведи дробь три четверти в десятичную и глянь время в Москве", "mixed"),
                       ("Переведи кубик в десятичную и глянь время в Москве", "mixed_mute")):
            m = len(events)
            await call("say", text=q)
            R[key] = await final(m)
            R[key + "_said"] = " ".join(e.get("text", "") for e in events[m:] if e["type"] == "say")
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
ok("вечер" in R["tokyo"] and "[world_time" not in R["tokyo"] and "написала вызов «world_time» текстом" in log,
   f"вызов текстом → попросили по-настоящему → вызвала и ответила, выдуманного вызова в ответе нет: {R['tokyo']!r}")
ok("пишет действия словами" in R["server"] and "[вызваны" not in R["server"] and "Жду вывод" not in R["server"] and N["stubborn"] == 3,
   f"упрямая модель: две просьбы, затем честно — что модель пишет действия словами: {R['server']!r} (запросов {N['stubborn']})")
ok("✋ Модель так и не взялась" in log, "в журнале: не взялась после просьб")
# №524 (04.11): справочное и действие в одном ходе, а слов нет — было «Не получилось: модель вернула пустой ответ»
ok("0,75" in R["mixed"] and "пустой ответ" not in R["mixed"], f"№524: calc + world_time без слов — попросили ответить по найденному и сделанному: {R['mixed']!r}")
ok(R["mixed_mute"].strip() == "Готово.", f"№524: и тогда без слов — «Готово.», а не «пустой ответ»: {R['mixed_mute']!r}")
ok("модель вернула пустой ответ" not in log, "в журнале нет «модель вернула пустой ответ»")
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
