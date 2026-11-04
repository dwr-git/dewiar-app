"""«Обещал, но не сделал»: модель отвечает «сейчас посмотрю и расскажу» и не вызывает ни одного действия, а на просьбу
о презентации не запускает задачу — ядро просит её сделать (quality.promise_nudge), и задача запускается. Обычный ответ и
уточняющий вопрос («Какой город?») не трогаем. Настоящее ядро по wav-файлу и своя модель-заглушка.
Отчёт 14.10: «что у нас по плану?» → «Достаю календарь и напоминания — одну секунду» — и всё:
— вопрос о планах: дела и календарь уже в подсказке модели (ПЛАНЫ ПОЛЬЗОВАТЕЛЯ) — отвечает сразу по ним;
— «достаю … одну секунду» без действия (вопрос без слова «план») — тоже обещание: ядро просит сделать."""
import asyncio, json, os, re, socket, subprocess, sys, tempfile, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import websockets
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
TESTS = Path(__file__).resolve().parent
PY = os.environ.get("DEWIAR_PY") or sys.executable
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


def free():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


SEEN = []
HINT = []                                         # подсказка «просят схему» в системной — для запроса со схемой


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
        ctx = "\n".join(m["content"].split("(Сообщение пользователя)\n")[0] for m in msgs if m["role"] == "user"
                        and isinstance(m["content"], str) and "(Сообщение пользователя)\n" in m["content"])   # справка к сообщению (время, дела)
        msgs = [dict(m, content=m["content"].split("(Сообщение пользователя)\n")[-1]) if m["role"] == "user" and isinstance(m["content"], str) else m
                for m in msgs]
        user = next((m["content"] for m in reversed(msgs) if m["role"] == "user" and isinstance(m["content"], str)), "")
        first_q = next((m["content"] for m in reversed(msgs) if m["role"] == "user" and isinstance(m["content"], str)
                        and not m["content"].startswith("СТОП")), "")
        SEEN.append(user[:80])
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()

        def send(delta, fin=None):
            self.wfile.write(f"data: {json.dumps({'choices': [{'delta': delta, 'finish_reason': fin}]}, ensure_ascii=False)}\n\n".encode())
        if any("до Нового года, и поставь" in str(m.get("content")) for m in msgs if m["role"] == "user"):   # экзамен 0.38.51
            if msgs[-1]["role"] == "tool":
                send({"content": "Поставила таймер на 78 минут."}); send({}, "stop")
            elif user.startswith("ПРОВЕРКА: пользователь прямо попросил поставить"):
                send({"tool_calls": [{"index": 0, "id": "n1", "type": "function", "function": {"name": "set_reminder",
                      "arguments": json.dumps({"text": "Таймер", "in_minutes": 78})}}]}); send({}, "tool_calls")
            else:
                send({"content": "До Нового года 78 дней. Скажи — поставлю таймер на 78 минут."}); send({}, "stop")
        elif any("остановимся на 65" in str(m.get("content")) for m in msgs if m["role"] == "user"):   # экзамен 0.38.48
            if msgs[-1]["role"] == "tool":
                send({"content": "Записала: 65 000."}); send({}, "stop")
            elif user.startswith("ПРОВЕРКА: ты написал(а), что сделал"):
                send({"tool_calls": [{"index": 0, "id": "r1", "type": "function", "function": {"name": "remember",
                      "arguments": json.dumps({"fact": "Бюджет на мебель для гостиной — 65 000"}, ensure_ascii=False)}}]}); send({}, "tool_calls")
            else:
                send({"content": "Окей, записала 65 000."}); send({}, "stop")
        elif any("Нарисуй схему" in str(m.get("content")) for m in msgs if m["role"] == "user"):
            HINT.append("СЕЙЧАС ПРОСЯТ СХЕМУ" in str(msgs[0].get("content")) + ctx)   # экзамен 15.10: «Схема готова и уже на экране» — без схемы (подсказка — в справке к вопросу)
            if user.startswith("ПРОВЕРКА: тебя попросили нарисовать схему"):
                send({"content": "Вот она.\n```mermaid\nflowchart LR\n  A[\"Клиент\"] --> B[\"Менеджер\"] --> C[\"Склад\"] --> A\n```"}); send({}, "stop")
            else:
                send({"content": "Схема готова и уже на экране. Клиент — менеджер — склад — клиент."}); send({}, "stop")
        elif "Поставь таймер" in first_q or user.startswith("ПРОВЕРКА"):          # экзамен 14.10: «на 79», а поставлено 59
            if user.startswith("ПРОВЕРКА"):
                send({"content": "Поправка: верно 59 минут."}); send({}, "stop")
            elif msgs[-1]["role"] == "tool":
                send({"content": "Таймер на 79 минут поставила."}); send({}, "stop")
            else:
                send({"tool_calls": [{"index": 0, "id": "t1", "type": "function", "function": {"name": "set_reminder",
                      "arguments": json.dumps({"text": "Таймер", "in_minutes": 59})}}]}); send({}, "tool_calls")
        elif msgs[-1]["role"] == "tool" or user.startswith("<tool_response>"):   # без инструментов история — текстом
            send({"content": "Взялась за презентацию — сообщу, когда будет готово."}); send({}, "stop")
        elif user.startswith("СТОП") and "start_task" in user:
            send({"tool_calls": [{"index": 0, "id": "c1", "type": "function", "function": {"name": "start_task",
                  "arguments": json.dumps({"title": "Презентация погоды", "goal": "Презентация о погоде в Минске на завтра"}, ensure_ascii=False)}}]})
            send({}, "tool_calls")
        elif user.startswith("СТОП"):
            send({"content": "Завтра в Минске +12 и облачно."}); send({}, "stop")
        elif msgs[-1]["role"] == "tool":
            send({"content": "Взялась за презентацию — сообщу, когда будет готово."}); send({}, "stop")
        elif "ПЛАНЫ ПОЛЬЗОВАТЕЛЯ" in str(msgs[0].get("content")) + ctx and "полить цветы" in (str(msgs[0].get("content")) + ctx).lower():
            send({"content": "Сегодня впереди — полить цветы."}); send({}, "stop")
        elif "план" in first_q or "просил" in first_q:
            send({"content": "Ты спросил, что у нас по плану. Достаю календарь и напоминания — одну секунду."}); send({}, "stop")
        elif "город" in first_q:
            send({"content": "Какой город?"}); send({}, "stop")
        elif "презентац" in first_q or "погод" in first_q or "кино" in first_q:
            send({"content": "Я сейчас посмотрю, какая будет погода на завтра, а затем расскажу."}); send({}, "stop")
        else:
            send({"content": "Привет! Всё хорошо."}); send({}, "stop")
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
    "llm": {"active": "m", "tools_probe_v": 2, "tools_modes": {f"{base}|m": "native"},
            "profiles": {"m": {"name": "mock", "kind": "openai", "base_url": base, "model": "m"}}}}))
env = dict(os.environ, DEWIAR_CONFIG_DIR=str(tmp / "cfg"), DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_PORT=str(PORT), DEWIAR_ASSUME_AEC="1",
           DEWIAR_WORKSPACE_DIR=str(tmp / "ws"), DEWIAR_FAKE_RAM_GB="16", DEWIAR_FAKE_CORES="8")
R = {}
# «Какая погода завтра?» с 28.10 отвечает быстрый путь погоды без модели (weather_quick1028_test) — обещание и уточняющий
# вопрос проверяем на других просьбах (экзамен ПК 0.81.1: проверка падала и до него)


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
            for _ in range(t * 20):                      # ждём, пока ответы перестанут приходить 2 с
                d = [e for e in events[mark:] if e["type"] == "answer" and e.get("done")]
                quiet = quiet + 1 if d and len(events) == last_n else 0
                last_n = len(events)
                if quiet >= 40:
                    return d[-1].get("text", "")
                await asyncio.sleep(0.05)
            d = [e for e in events[mark:] if e["type"] == "answer" and e.get("done")]
            return d[-1].get("text", "") if d else ""
        await call("reminder_add", phrase="через 30 минут полить цветы")
        for q, key in (("Сделай мне презентацию о завтрашней погоде", "pres"), ("Посмотри, какой фильм идёт в кино завтра", "promise"),
                       ("Сколько стоит такси в моём городе?", "ask"), ("Привет", "plain"), ("Что у нас по плану?", "plan"),
                       ("А я что у тебя просил?", "asked"), ("Поставь таймер на столько минут, сколько дней до Нового года", "timer"),
                       ("Нарисуй схему: как заявка проходит от клиента через менеджера на склад и обратно клиенту.", "diagram"),
                       ("Ладно, остановимся на 65 тысячах.", "saved"),
                       ("Посчитай, сколько дней осталось до Нового года, и поставь таймер на столько же минут.", "ny")):
            m = len(events)
            await call("say", text=q)
            R[key] = await final(m)
            R[key + "_all"] = " | ".join(e.get("text", "") for e in events[m:] if e["type"] == "answer" and e.get("done"))
            await asyncio.sleep(1.0)
        rd.cancel(); await ws_.close()
    finally:
        core.terminate()
        try:
            core.wait(10)
        except subprocess.TimeoutExpired:
            core.kill()

sys.path.insert(0, str(ROOT / "core"))
from quality import looks_like_promise  # noqa: E402
PROM = ["Ты спросил, что у нас по плану. Достаю календарь и напоминания — одну секунду.", "Сейчас, вот они — календарь и напоминания.",
        "Секунду, открываю календарь.", "Сейчас гляну календарь."]
REAL = ["Вот они: в 10:00 iCad, в 12:28 обед.", "Вот он, твой план: полить цветы и позвонить маме.", "Сейчас 10 утра, в календаре пусто.",
        "В 10:00 скопировать проект iCad, в 12:28 обед — не забудьте карту.", "Вот так и живём."]
ok(all(looks_like_promise(t) for t in PROM) and not any(looks_like_promise(t) for t in REAL),
   f"обещания без результата узнаются, ответы по делу — нет: {[t for t in PROM if not looks_like_promise(t)]} {[t for t in REAL if looks_like_promise(t)]}")
asyncio.run(session())
log = (tmp / "core.log").read_text(encoding="utf-8", errors="replace")
srv.shutdown()
ok("Взялась за презентацию" in R["pres_all"] and "«Презентация погоды»" in R["pres_all"], f"презентация: обещание → задача запущена ({R['pres_all'][:160]})")
ok("+12" in R["promise"], f"«сейчас посмотрю» без действия → доделала: {R['promise'][-60:]}")
ok(R["ask"].strip() == "Какой город?", f"уточняющий вопрос не трогаем: {R['ask']}")
ok(R["plain"].startswith("Привет"), "обычный ответ не трогаем")
ok("полить цветы" in R["plan"] and "секунду" not in R["plan_all"], f"«что у нас по плану» — дела уже перед моделью, ответ сразу: {R['plan_all'][:120]}")
ok("+12" in R["asked"], f"«достаю календарь — одну секунду» без действия → доделала: {R['asked_all'][-80:]}")
ok(log.count("✋ Модель") == 3, f"просили доделать трижды (презентация, погода, «одну секунду»): {log.count('✋ Модель')}")
ok("Поправка: верно 59" in R["timer_all"] and "✋ Число в ответе не совпадает" in log,
   f"«таймер на 79 минут», а поставлено 59 — модель поправилась: {R['timer_all'][-120:]}")
ok("```mermaid" in R["diagram"] and "✋ Просили схему" in log, f"«нарисуй схему» — ответ словами → дорисовала: {R['diagram'][-140:]!r}")
ok(HINT and all(HINT), f"просят схему — модель заранее знает: только блок mermaid рисует, «на экране» без него не говорить: {HINT}")
mem = "".join(x.read_text(encoding="utf-8") for x in (tmp / "ws").rglob("Обо мне.md"))
# рецензия 0.82 («Голос без пауз»): бюджет — не «Деньги», фраза не придерживается — «записала» звучит сразу, после remember
# это уже правда; повтор «Записала: 65 000» глушит проверка повторов (№435)
ok("✋ Сказала «готово/записала»" in log and "65 000" in mem and "аписала" in R["saved_all"] and "65 000" in R["saved_all"]
   and "money_add" not in log.split("остановимся на 65")[-1].split("❓")[0] and R["saved_all"].lower().count("записала") == 1,
   f"«записала 65 000», ничего не вызвав, → записала по-настоящему: {R['saved_all'][-100:]!r}, в памяти: {'65 000' in mem}")
ok("Поставила таймер на 78 минут" in R["ny_all"] and "set_reminder" in log, f"«поставь таймер» — а модель переспросила: попросили поставить, поставила: {R['ny_all'][-120:]!r}")
ok("📅 Вопрос о планах" in log, "в журнале: вопрос о планах — дела и календарь в подсказке")
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
