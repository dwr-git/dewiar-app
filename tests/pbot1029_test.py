"""«Бот персонажа» в Telegram (0.67; владелец 28.10: «персонаж, обученный на знаниях, — в телеграм-бот, а лучше если в
группе работает»). На настоящем ядре и студии, Telegram и модель — подставные:
- отдельный публичный бот: токен личного бота не берёт, токен в студию не отдаётся, файл — 0600;
- отвечает всем лично; в группе — только когда упомянули, ответили ему или /ask; ответ — ответом на сообщение;
- думает мозгом персонажа (свой мозг Патрика), отвечает по его знаниям (папка), без памяти владельца, без разметки;
- ограничения: на человека в день (одна вежливая фраза сверх), пауза бота — молчит; добавили в группу — здоровается;
- студия: схема, «Проверить ответ», «Что спрашивали», группы."""
import json, os, re, socket, stat, subprocess, sys, tempfile, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
TESTS = Path(__file__).resolve().parent
PY = os.environ.get("DEWIAR_PY") or sys.executable
SHOTS = os.environ.get("DEWIAR_SHOTS", "")
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


def free():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


TOK = "7000000001:AAH" + "b" * 32
OWN = "7000000002:AAH" + "o" * 32                       # личный бот владельца
BOT_ID = 7000000001
UPD, SENT, LLM, ACTIONS = [], [], [], []
lock = threading.Lock()


def push(msg):
    with lock:
        UPD.append({"update_id": len(UPD) + 1, "message": dict(msg, date=int(time.time()))})


class M(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, d):
        b = json.dumps(d, ensure_ascii=False).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def do_GET(self):
        self._json({"data": [{"id": "gpt-mock"}, {"id": "claude-mock"}]})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        m = re.match(r"^/bot([^/]+)/(\w+)", self.path)
        if m:
            tok, meth = m.groups()
            if tok != TOK:                                   # личный бот — у него своя жизнь, в тесте молчит
                if meth == "getUpdates":
                    time.sleep(1)
                return self._json({"ok": True, "result": [] if meth == "getUpdates" else {"id": 7000000002, "username": "my_own_bot", "first_name": "Мой"}})
            if meth == "getMe":
                return self._json({"ok": True, "result": {"id": BOT_ID, "is_bot": True, "username": "lira_shop_bot", "first_name": "Чайный двор"}})
            if meth == "getUpdates":
                off = body.get("offset", 0)
                for _ in range(10):
                    with lock:
                        got = [u for u in UPD if u["update_id"] >= off]
                    if got:
                        return self._json({"ok": True, "result": got})
                    time.sleep(0.1)
                return self._json({"ok": True, "result": []})
            if meth == "sendMessage":
                with lock:
                    SENT.append(body)
                return self._json({"ok": True, "result": {"message_id": 1000 + len(SENT), "chat": {"id": body["chat_id"]}}})
            ACTIONS.append(meth)
            return self._json({"ok": True, "result": True})
        sysm = next((x["content"] for x in body.get("messages", []) if x.get("role") == "system"), "")
        LLM.append({"model": body.get("model"), "system": sysm, "messages": body.get("messages", [])})
        text = "Сенча стоит 450 рублей за 100 граммов. **Заходите!**" if "Сенча" in sysm else "Спросите меня о чае — подскажу."
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
        for w in re.findall(r"\S+\s*", text):
            self.wfile.write(("data: " + json.dumps({"choices": [{"delta": {"content": w}}]}, ensure_ascii=False) + "\n\n").encode()); self.wfile.flush()
        self.wfile.write(b'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n')


srv = ThreadingHTTPServer(("127.0.0.1", 0), M); threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = f"http://127.0.0.1:{srv.server_address[1]}"
tmp = Path(tempfile.mkdtemp()); cfg = tmp / "cfg"; cfg.mkdir()
kb = tmp / "Прайс чая"; kb.mkdir()
(kb / "прайс.md").write_text("# Прайс\n\nСенча — 450 рублей за 100 граммов. Доставка по городу бесплатно от 1500 рублей.\n", encoding="utf-8")
PORT = free()
(cfg / "settings.json").write_text(json.dumps({
    "persona": "lira", "user_name": "Секретов Иннокентий", "audio": {"sounds": False}, "ui": {"news_seen": "99.0.0", "welcome": "done", "mode_seen": 1},
    "stt": {"engine": "vosk"}, "tts": {"engine": "off"}, "updates": {"auto_check": False}, "workspace": {"path": str(tmp / "ws")},
    "llm": {"active": "g", "profiles": {"g": {"name": "ChatGPT", "kind": "openai", "base_url": BASE + "/v1", "model": "gpt-mock"},
                                        "c": {"name": "Claude", "kind": "openai", "base_url": BASE + "/v1", "model": "claude-mock"}},
            "persona": {"patrik": "c"}}}), encoding="utf-8")
(cfg / "telegram.json").write_text(json.dumps({"token": OWN, "bot": {"username": "my_own_bot"}, "owner": {"id": 1, "chat": 1}}), encoding="utf-8")
env = dict(os.environ, DEWIAR_CONFIG_DIR=str(cfg), DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_PORT=str(PORT), DEWIAR_ASSUME_AEC="1",
           DEWIAR_WORKSPACE_DIR=str(tmp / "ws"), DEWIAR_FAKE_RAM_GB="16", DEWIAR_FAKE_CORES="8", DEWIAR_TG_API=BASE)
core = subprocess.Popen([PY, str(ROOT / "core/main.py"), "--wav", str(TESTS / "silence90.wav"), "--null-audio"], env=env,
                        stdout=open(tmp / "core.log", "w"), stderr=subprocess.STDOUT)
for _ in range(150):
    time.sleep(0.2)
    if (cfg / "token").exists():
        break
time.sleep(2)
tok = (cfg / "token").read_text().strip()
errs = []


def sent_to(chat, n0):
    return [x for x in SENT[n0:] if x["chat_id"] == chat]


def wait_sent(chat, n0, k=1, limit=15):
    end = time.time() + limit
    while time.time() < end:
        if len(sent_to(chat, n0)) >= k:
            return sent_to(chat, n0)
        time.sleep(0.15)
    return sent_to(chat, n0)


DM = {"id": 501, "type": "private", "first_name": "Анна"}
ANNA = {"id": 501, "is_bot": False, "first_name": "Анна"}
GR = {"id": -9001, "type": "supergroup", "title": "Чайный клуб"}
BOB = {"id": 777, "is_bot": False, "first_name": "Борис"}
try:
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1440, "height": 1200})
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto((ROOT / "ui/settings.html").as_uri() + f"?token={tok}&port={PORT}"); time.sleep(3)
        call = lambda cmd, a=None: pg.evaluate("([c, a]) => core.call(c, a || {}).then(r => r, e => ({__err: e.message}))", [cmd, a])  # noqa: E731
        ok(pg.locator('nav button[data-p="pbot"]').count() == 1, "в меню — «Бот в Telegram»")
        pg.click('nav button[data-p="pbot"]'); time.sleep(1.2)
        ok(pg.is_visible("#bp-setup") and "@BotFather" in pg.inner_text("#bp-setup") and pg.locator("#bp-flow .bp-wall em").count() >= 4,
           "не подключён: шаги с @BotFather; на схеме — чего бот не видит")
        r = call("pbot_connect", {"token": OWN})
        ok("личный бот" in (r.get("__err") or ""), f"токен личного бота — нельзя: {r}")
        r = call("pbot_connect", {"token": "123"})
        ok("не похоже на токен" in (r.get("__err") or ""), "не токен — понятная ошибка")
        call("persona_save", {"persona": {"id": "patrik", "name": "Патрик", "knowledge": [{"kind": "folder", "path": str(kb), "label": "Прайс чая"}]}})
        pg.fill("#bp-token", TOK); pg.click("#bp-connect"); pg.wait_for_selector("#bp-bot:not([hidden])", timeout=20000); time.sleep(0.3)
        ok(pg.is_visible("#bp-bot") and "@lira_shop_bot" in pg.inner_text("#bp-bot") and pg.get_attribute("#bp-addgr", "href").endswith("?startgroup=1"),
           "подключён: имя бота, «Открыть», «Добавить в группу»")
        d = call("pbot_get")
        ok(TOK not in json.dumps(d) and "b" * 32 not in json.dumps(d), "токен в студию не отдаётся")
        mode = stat.S_IMODE((cfg / "pbot.json").stat().st_mode)
        ok(mode == 0o600, f"файл с токеном — только владельцу: {oct(mode)}")
        pg.click('#bp-ps .co-m[data-id="patrik"]'); time.sleep(0.8)
        ok(call("pbot_get").get("persona") == "patrik" and "Патрик" in pg.inner_text("#bp-who") and "claude-mock" in pg.inner_text("#bp-model"),
           "кто отвечает — Патрик; на схеме его мозг: claude-mock")
        pg.fill("#bp-brief", "Ты консультант магазина «Чайный двор»."); time.sleep(1.4)
        # знания читаются в фоне — «Проверить ответ», пока не найдёт
        for _ in range(30):
            LLM.clear(); pg.fill("#bp-q", "Сколько стоит Сенча?"); pg.click("#bp-send")
            pg.wait_for_function("() => !document.querySelector('#bp-send').disabled", timeout=20000)
            if LLM and "450" in LLM[-1]["system"]:
                break
            time.sleep(0.7)
        last = pg.inner_text("#bp-chat .bp-b.bot:last-child")
        ok("450 рублей" in last and "**" not in last, f"«Проверить ответ»: отвечает по знаниям, без разметки: {last!r}")
        s0 = LLM[-1]["system"] if LLM else ""
        ok(LLM and LLM[-1]["model"] == "claude-mock" and "Ты — Патрик" in s0 and "Чайный двор" in s0, "думает мозгом Патрика, с «О чём бот»")
        ok("НЕТ доступа" in s0 and "Секретов" not in s0 and "Иннокентий" not in s0, "в подсказке — что доступа к личному нет; имени владельца нет")
        # лично
        n0 = len(SENT); push({"message_id": 1, "chat": DM, "from": ANNA, "text": "/start"})
        got = wait_sent(501, n0)
        ok(got and "Патрик" in got[0]["text"] and "Чайный двор" in got[0]["text"], f"/start — приветствие персонажа: {got[:1]}")
        n0 = len(SENT); push({"message_id": 2, "chat": DM, "from": ANNA, "text": "Сколько стоит Сенча?"})
        got = wait_sent(501, n0)
        ok(got and "450 рублей" in got[0]["text"] and "reply_parameters" not in got[0], f"лично — отвечает на всё: {got[:1]}")
        ok("typing" in json.dumps(ACTIONS) or "sendChatAction" in ACTIONS, "пока думает — «печатает…»")
        # группа: без обращения — молчит
        n0, l0 = len(SENT), len(LLM)
        push({"message_id": 10, "chat": GR, "from": BOB, "text": "Всем привет, кто пьёт пуэр?"})
        time.sleep(2.5)
        ok(not sent_to(-9001, n0) and len(LLM) == l0, "в группе без обращения — молчит и модель не зовёт")
        push({"message_id": 11, "chat": GR, "from": BOB, "text": "@lira_shop_bot а Сенча почём?"})
        got = wait_sent(-9001, n0)
        ok(got and got[0].get("reply_parameters", {}).get("message_id") == 11 and "450" in got[0]["text"], f"упомянули — отвечает ответом на сообщение: {got[:1]}")
        u = [m for m in LLM[l0:]][-1]["messages"][-1]["content"] if len(LLM) > l0 else ""
        ok(u == "Борис: а Сенча почём?" and "в группе «Чайный клуб»" in LLM[-1]["system"], f"в группе — имена реплик и название группы: {u!r}")
        time.sleep(4.2)                                       # в группе — не чаще раза в 4 с
        n0 = len(SENT)
        push({"message_id": 12, "chat": GR, "from": ANNA, "text": "А доставка?", "reply_to_message": {"message_id": 1003, "from": {"id": BOT_ID, "is_bot": True}}})
        got = wait_sent(-9001, n0)
        ok(got and got[0].get("reply_parameters", {}).get("message_id") == 12, "ответили на сообщение бота — отвечает")
        hist = LLM[-1]["messages"]
        ok(any("Борис: а Сенча почём?" == m.get("content") for m in hist), "помнит, о чём говорили в этом чате")
        # добавили в группу — здоровается
        n0 = len(SENT); push({"message_id": 20, "chat": {"id": -9002, "type": "group", "title": "Книжный клуб"}, "from": BOB,
                              "new_chat_members": [{"id": BOT_ID, "is_bot": True, "first_name": "Чайный двор"}]})
        got = wait_sent(-9002, n0)
        ok(got and "упомянут" in got[0]["text"], f"добавили в группу — здоровается и говорит, как к нему обращаться: {got[:1]}")
        # ограничение на человека
        call("pbot_set", {"patch": {"per_user": 3}})
        n0 = len(SENT)
        for i in range(3):
            push({"message_id": 30 + i, "chat": DM, "from": ANNA, "text": f"Вопрос номер {i}"}); time.sleep(0.9)
        got = wait_sent(501, n0, 2, limit=10); time.sleep(1.5)
        got = sent_to(501, n0)
        ok(len(got) == 2 and sum("Возвращайтесь завтра" in x["text"] for x in got) == 1, f"сверх лимита — одна вежливая фраза: {[x['text'][:40] for x in got]}")
        push({"message_id": 40, "chat": DM, "from": ANNA, "text": "Ещё вопрос"}); time.sleep(1.5)
        ok(len(sent_to(501, n0)) == 2, "дальше — молчит до завтра")
        # пауза
        call("pbot_set", {"patch": {"per_user": 30, "on": False}})
        n0 = len(SENT); push({"message_id": 50, "chat": {"id": 502, "type": "private"}, "from": {"id": 502, "first_name": "Вера"}, "text": "Есть кто?"}); time.sleep(2)
        ok(not sent_to(502, n0), "на паузе — не отвечает")
        call("pbot_set", {"patch": {"on": True}}); time.sleep(2)
        got = wait_sent(502, n0)
        ok(got, "включили — отвечает (и на то, что писали в паузе)")
        # студия: что спрашивали, группы
        pg.click('nav button[data-p="home"]'); time.sleep(0.4); pg.click('nav button[data-p="pbot"]'); time.sleep(1.2)
        log_t = pg.inner_text("#bp-log")
        ok("Сколько стоит Сенча?" in log_t and "Борис" in log_t and "Чайный клуб" in pg.inner_text("#bp-chats"), "«Что спрашивали»: вопросы, кто и где; группы")
        ok(re.search(r"сегодня \d+", pg.inner_text("#bp-stat")) is not None, f"счётчик за сегодня: {pg.inner_text('#bp-stat')!r}")
        ok(pg.locator("#bp-wires path.bp-w").count() == 8, "схема: провода от людей к персонажу и к знаниям и мозгу")
        if SHOTS:
            pg.evaluate("pbPulse()"); time.sleep(0.5)
            pg.screenshot(path=os.path.join(SHOTS, "pbot.png"), full_page=True)
        ok(not errs, f"без ошибок на странице: {errs[:2]}")
        b.close()
finally:
    core.terminate(); srv.shutdown()
# голосовое лично — распознаём тем же слухом, что дома, и отвечаем; длинное — просим покороче
sys.path.insert(0, str(ROOT / "core"))
import types  # noqa: E402
import pbot as PB  # noqa: E402
srv2 = ThreadingHTTPServer(("127.0.0.1", 0), M); threading.Thread(target=srv2.serve_forever, daemon=True).start()
B2 = f"http://127.0.0.1:{srv2.server_address[1]}"
heard = []
host = types.SimpleNamespace(s=types.SimpleNamespace(get=lambda *k: "patrik", active_llm=lambda: {}),
                             personas=types.SimpleNamespace(get=lambda pid: {"id": "patrik", "name": "Патрик", "character": "весёлый"}),
                             persona_llm=lambda pid: {"kind": "openai", "base_url": B2 + "/v1", "model": "claude-mock"},
                             _persona_knowledge=lambda *a, **k: "\n\nТВОЯ БАЗА ЗНАНИЙ: Сенча — 450 рублей.",
                             _tg_transcribe=lambda b: heard.append(b) or "Сколько стоит Сенча?", emit=lambda *a, **k: None)
bot = PB.PersonaBot(host, path=tmp / "pb2.json")
bot.data = {"token": TOK, "api": B2, "bot": {"id": BOT_ID, "username": "lira_shop_bot"}}
bot.download = lambda fid, size=None: b"OggS-voice"
n0 = len(SENT)
bot._handle({"update_id": 1, "message": {"message_id": 5, "chat": {"id": 801, "type": "private"}, "from": {"id": 801, "first_name": "Ира"},
                                         "voice": {"file_id": "v1", "duration": 4, "file_size": 9000}}})
got = wait_sent(801, n0)
ok(heard == [b"OggS-voice"] and got and "450" in got[0]["text"], f"голосовое лично — распознано и отвечено: {got[:1]}")
n0 = len(SENT)
bot._handle({"update_id": 2, "message": {"message_id": 6, "chat": {"id": 801, "type": "private"}, "from": {"id": 801, "first_name": "Ира"},
                                         "voice": {"file_id": "v2", "duration": 300}}})
got = wait_sent(801, n0)
ok(got and "покороче" in got[0]["text"] and len(heard) == 1, "длинное голосовое — просим покороче, не распознаём")
srv2.shutdown()
src = (ROOT / "core/engine_commands.py").read_text(encoding="utf-8")
ok('"pbot_"' in src.split("_KIDS_LOCKED")[1][:200], "в детском режиме без PIN — недоступно")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
