"""«Команда» — поручения сотрудникам в Telegram (28.10, по макету «Команда», владелец: «прекрасны, идеальны»).
Часть 1 — core/team.py с поддельным Telegram (DEWIAR_TG_API): бот компании, приглашения по коду, чужие не проходят,
поручение с кнопками «Беру» → «Сделано» (отчёт и фото) → «Принять»; «Перенести…» — новый срок и причина; двое Иванов —
вопрос «кому?»; поручение до входа сотрудника приходит после входа; напоминание за час и «просрочено»; «Вернуть с
замечанием»; календарь и сводка для модели. Часть 2 — настоящее ядро: голосом «поручи Анне…» (мок модели), студия →
«Команда»: доска, карточка с фото и «Принять»."""
import json, os, re, socket, sys, tempfile, threading, time
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
TESTS = ROOT / "tests"
PY = os.environ.get("DEWIAR_PY") or sys.executable
SHOTS = os.environ.get("DEWIAR_SHOTS")
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


def free():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


TOKEN = "987654321:AAHteamTokenForDewiarTests_abcdefghijk"
PERSONAL = "123456789:AAHpersonalTokenForDewiarTests_abcdefg"
ANNA, IVAN, IVAN2, STRANGER = 601, 602, 603, 777
JPEG = b"\xff\xd8\xff\xe0" + b"0" * 200 + b"\xff\xd9"


class TG:
    updates, sent, lock, uid = [], [], threading.Lock(), [100]

    @classmethod
    def push(cls, frm, text=None, **extra):
        with cls.lock:
            cls.uid[0] += 1
            m = {"message_id": cls.uid[0], "chat": {"id": frm, "type": "private"},
                 "from": {"id": frm, "first_name": {ANNA: "Анна", IVAN: "Иван"}.get(frm, "Кто-то"), "username": f"u{frm}"}, "date": int(time.time())}
            if text is not None:
                m["text"] = text
            m.update(extra)
            cls.updates.append({"update_id": cls.uid[0], "message": m})

    @classmethod
    def button(cls, frm, data):
        with cls.lock:
            cls.uid[0] += 1
            cls.updates.append({"update_id": cls.uid[0], "callback_query": {"id": str(cls.uid[0]), "from": {"id": frm}, "data": data,
                                                                            "message": {"message_id": 1, "chat": {"id": frm}}}})


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def out(self, code, obj):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b)))
        self.end_headers(); self.wfile.write(b)

    def do_GET(self):
        if self.path.startswith(f"/file/bot{TOKEN}/"):
            self.send_response(200); self.send_header("Content-Length", str(len(JPEG))); self.end_headers(); self.wfile.write(JPEG)
            return
        self.out(404, {"ok": False})

    def do_POST(self):
        m = re.match(r"/bot([^/]+)/(\w+)", self.path)
        raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        if not m or m.group(1) not in (TOKEN, PERSONAL):
            return self.out(401, {"ok": False, "error_code": 401, "description": "Unauthorized"})
        meth, params = m.group(2), json.loads(raw or b"{}")
        if meth == "getMe":
            return self.out(200, {"ok": True, "result": {"id": 9, "is_bot": True, "first_name": "Ромашка", "username": "romashka_team_bot"}})
        if meth == "getUpdates":
            off, end = params.get("offset", 0), time.time() + min(1, params.get("timeout", 0))
            got = []
            while time.time() < end:
                with TG.lock:
                    got = [u for u in TG.updates if u["update_id"] >= off]
                if got:
                    break
                time.sleep(0.05)
            return self.out(200, {"ok": True, "result": got})
        if meth == "getFile":
            return self.out(200, {"ok": True, "result": {"file_id": params["file_id"], "file_path": "photos/" + params["file_id"] + ".jpg"}})
        with TG.lock:
            TG.sent.append((meth, params))
            n = len(TG.sent)
        return self.out(200, {"ok": True, "result": {"message_id": 1000 + n}})


TGP = free()
srv = ThreadingHTTPServer(("127.0.0.1", TGP), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
os.environ["DEWIAR_TG_API"] = f"http://127.0.0.1:{TGP}"
tmp = Path(tempfile.mkdtemp())
os.environ["DEWIAR_CONFIG_DIR"] = str(tmp / "cfg0")
sys.path.insert(0, str(ROOT / "core"))
import team as T  # noqa: E402


class S:
    def __init__(self): self.d = {"user_name": "Михаил", "features": {"team": True}}
    def get(self, k, sub=None):
        v = self.d.get(k)
        return (v or {}).get(sub) if sub else v


class Host:
    def __init__(self): self.s, self.ev, self.pushed, self.said = S(), [], [], []
    def emit(self, t, **k): self.ev.append(t)
    def push(self, title, text, **k): self.pushed.append(f"{title}: {text}")
    def announce(self, text): self.said.append(text)


class Personal:
    data = {"token": PERSONAL, "proxy": ""}


def sent_to(chat, since=0):
    with TG.lock:
        return [(m, p) for m, p in TG.sent[since:] if str(p.get("chat_id")) == str(chat)]


def wait(pred, limit=6):
    end = time.time() + limit
    while time.time() < end:
        if pred():
            return True
        time.sleep(0.05)
    return False


def texts(chat, since=0):
    return [p.get("text", "") for m, p in sent_to(chat, since) if m == "sendMessage"]


# ---------- части due_parse ----------
mon = datetime.now()
at, rest = T.due_parse("до пятницы")
ok(at is not None and at.weekday() == 4 and (at.hour, at.minute) == (18, 0), f"«до пятницы» — пятница, 18:00: {at}")
at, rest = T.due_parse("до четверга 15:00")
ok(at is not None and at.weekday() == 3 and at.hour == 15, f"«до четверга 15:00»: {at}")
at, rest = T.due_parse("завтра к 12")
ok(at is not None and at.date() == (mon + timedelta(days=1)).date() and at.hour == 12, f"«завтра к 12»: {at}")
at, rest = T.due_parse("на понедельник, клиент заболел")
ok(at is not None and at.weekday() == 0 and "клиент заболел" in rest.lower(), f"«на понедельник, клиент заболел» — срок и причина: {at} / {rest}")
ok(T.due_parse("когда-нибудь потом")[0] is None, "непонятный срок — None")

host = Host()
tm = T.Team(host, tmp / "team.json", tmp / "team_bot.json", personal=Personal())
try:
    tm.connect(PERSONAL)
    ok(False, "личный бот не принимается")
except T.TeamError as e:
    ok("личного бота" in str(e), "токен личного бота в «Команду» не принимается")
p = tm.connect(TOKEN)
ok(p["connected"] and p["bot"] == "romashka_team_bot" and p["company"] == "Ромашка" and p["boss"] == "Михаил", f"бот компании подключён: {p['bot']}, «{p['company']}»")
ok(oct(os.stat(tmp / "team_bot.json").st_mode & 0o777) == "0o600" and "token" not in json.dumps(p), "токен — в файле 0600 и не уходит в студию")
for nm, role in (("Анна Ким", "сайт"), ("Иван Васильевич", "договоры"), ("Иван Сергеевич", "маркетинг")):
    p = tm.member_add(nm, role)
mem = {m["name"]: m for m in p["members"]}
ok(len(mem) == 3 and all(m["link"].startswith("https://t.me/romashka_team_bot?start=") for m in mem.values()), "у каждого — своя ссылка-приглашение")
code_anna = mem["Анна Ким"]["link"].rsplit("=", 1)[1]

TG.push(STRANGER, "Привет")
TG.push(STRANGER, "Ау")
wait(lambda: texts(STRANGER))
time.sleep(0.5)
ok(len(texts(STRANGER)) == 1 and "рабочий бот" in texts(STRANGER)[0], f"чужому — одна фраза: {texts(STRANGER)}")
TG.push(ANNA, "/start deadbeef00")
wait(lambda: texts(ANNA))
ok("не подошло" in (texts(ANNA) or [""])[0], "чужой код — «приглашение не подошло»")
n0 = len(TG.sent)
TG.push(ANNA, f"/start {code_anna}")
wait(lambda: any("Здравствуйте, Анна Ким" in t for t in texts(ANNA, n0)))
mem = {m["name"]: m for m in tm.public()["members"]}
ok(mem["Анна Ким"]["joined"] and not mem["Анна Ким"]["link"], "Анна вошла по ссылке — приглашение сгорело")
ok(wait(lambda: any("Анна Ким подключилась" in x for x in host.pushed)), "руководителю — «Анна подключилась»")

try:
    tm.assign("Ивану", "Сверка с бухгалтерией")
    ok(False, "двое Иванов")
except T.TeamError as e:
    ok("подходят двое" in str(e) and "Иван Васильевич" in str(e), f"«Ивану» — двое, вопрос «кому?»: {e}")
n0 = len(TG.sent)
r = tm.assign("Анне", "Обновить прайс на сайте", "до пятницы", via="voice")
card = sent_to(ANNA, n0)
ok(r["sent"] and card and "Новое поручение от Михаила" in card[0][1]["text"] and "Обновить прайс" in card[0][1]["text"],
   "Анне в Telegram — карточка «Новое поручение от Михаила»")
kb = card[0][1].get("reply_markup", {}).get("inline_keyboard", [[]])[0]
ok([b["text"] for b in kb] == ["Беру", "Перенести…"], f"кнопки «Беру» и «Перенести…»: {[b['text'] for b in kb]}")
tid = r["id"]
n0 = len(TG.sent)
TG.button(ANNA, f"tk:{tid}:take")
wait(lambda: tm.st["tasks"][tid]["state"] == "work" and any(m == "editMessageReplyMarkup" for m, _ in sent_to(ANNA, n0)))
ok(tm.st["tasks"][tid]["state"] == "work" and any(m == "editMessageReplyMarkup" for m, _ in sent_to(ANNA, n0)), "«Беру» — в работе, кнопки сменились")
ok(wait(lambda: any("в работе" in t for t in texts(ANNA, n0))), "сотруднику — «Записала: в работе»")
TG.button(STRANGER, f"tk:{tid}:done")
time.sleep(0.5)
ok(tm.st["tasks"][tid]["state"] == "work", "чужие нажатия не считаются")
n0 = len(TG.sent)
TG.button(ANNA, f"tk:{tid}:done")
wait(lambda: any("пару слов" in t for t in texts(ANNA, n0)))
TG.push(ANNA, None, caption="Прайс обновлён, проверьте раздел «Опт»", photo=[{"file_id": "ph1", "file_size": 200, "width": 90}])
wait(lambda: tm.st["tasks"][tid]["state"] == "done")
t = tm.st["tasks"][tid]
ok(t["state"] == "done" and t["report"]["t"].startswith("Прайс обновлён") and (tmp / "team" / t["report"]["photo"]).read_bytes() == JPEG,
   "«Сделано» — отчёт и фото сохранены")
ok(wait(lambda: any("Анна Ким сделала: «Обновить прайс на сайте» — Прайс обновлён" in x for x in host.said)), f"руководителю вслух: {host.said[-1:]}")
ok(wait(lambda: any("Отметила сделанным, фото приложила" in x for x in texts(ANNA, n0))), "сотруднику — «Отметила сделанным, фото приложила»")
n0 = len(TG.sent)
tm.accept(tid)
ok(tm.st["tasks"][tid]["state"] == "ok" and any("Михаил принял" in x for x in texts(ANNA, n0)), "«Принять» — сотруднику «принял»")

# перенос
r2 = tm.assign("Анна", "Выезд к клиенту", "завтра к 10")
n0 = len(TG.sent)
TG.button(ANNA, f"tk:{r2['id']}:move")
wait(lambda: any("На когда переносим" in x for x in texts(ANNA, n0)))
TG.push(ANNA, "когда получится")
ok(wait(lambda: any("Не поняла новый срок" in x for x in texts(ANNA, n0))), "непонятный срок — переспросить с примером")
TG.push(ANNA, "на понедельник")
ok(wait(lambda: any("А почему?" in x for x in texts(ANNA, n0))), "срок без причины — спросить причину")
TG.push(ANNA, "клиент заболел")
wait(lambda: tm.st["tasks"][r2["id"]]["state"] == "moved")
t2 = tm.st["tasks"][r2["id"]]
ok(t2["state"] == "moved" and datetime.fromisoformat(t2["due"]).weekday() == 0 and t2["reason"] == "клиент заболел", f"перенесено на понедельник, причина: {t2.get('reason')}")
ok(wait(lambda: any("переносит «Выезд к клиенту»" in x and "клиент заболел" in x for x in host.said)), "руководителю — кто переносит и почему")

# до входа сотрудника
r3 = tm.assign("Иван Васильевич", "Подготовить договор поставки", "до четверга 15:00")
ok(not r3["sent"] and not r3["joined"], "Иван ещё не вошёл — поручение ждёт")
code_ivan = {m["name"]: m for m in tm.public()["members"]}["Иван Васильевич"]["link"].rsplit("=", 1)[1]
TG.push(IVAN, code_ivan)
ok(wait(lambda: any("Подготовить договор поставки" in x for x in texts(IVAN))), "вошёл (код без /start) — поручение пришло сразу")

# напоминание и просрочка
with tm._lock:
    tm.st["tasks"][r3["id"]]["due"] = (datetime.now() + timedelta(minutes=40)).strftime("%Y-%m-%dT%H:%M")
n0 = len(TG.sent)
tm.tick(); tm.tick()
ok(sum("Напоминаю" in x for x in texts(IVAN, n0)) == 1, "за час до срока — одно напоминание")
tm.tick(datetime.now() + timedelta(hours=2))
ok(tm.st["tasks"][r3["id"]].get("late"), "срок прошёл — «просрочено»")
pub = tm.public()
ok(any(x["id"] == r3["id"] and x["late"] is False for x in pub["tasks"]), "в студии «просрочено» — по текущему времени")

# вернуть с замечанием
TG.button(IVAN, f"tk:{r3['id']}:take"); wait(lambda: tm.st["tasks"][r3["id"]]["state"] == "work")
TG.button(IVAN, f"tk:{r3['id']}:done"); time.sleep(0.4)
TG.push(IVAN, "готово"); wait(lambda: tm.st["tasks"][r3["id"]]["state"] == "done")
ok(tm.st["tasks"][r3["id"]]["report"]["t"] == "", "«готово» — сделано без лишнего текста")
n0 = len(TG.sent)
tm.back(r3["id"], "Добавьте пункт о штрафах")
ok(tm.st["tasks"][r3["id"]]["state"] == "work" and any("пункт о штрафах" in x for x in texts(IVAN, n0)), "«Вернуть с замечанием» — снова в работе, сотруднику — замечание")

# сообщение не по кнопке — руководителю
n0 = len(TG.sent)
TG.push(IVAN, "Юристы просят ещё день")
ok(wait(lambda: any("Передала Михаилу" in x for x in texts(IVAN, n0))) and any("Юристы просят" in x for x in host.pushed),
   "просто сообщение — руководителю")
cal = tm.calendar(datetime.now() - timedelta(days=40), datetime.now() + timedelta(days=40))
ok(any(it["title"].startswith("✓ Обновить прайс") for _, it in cal) and any(it["cal"] == "Поручения" for _, it in cal), "в календаре — сроки, сделанное с «✓»")
sm = tm.summary()
ok("Анна Ким: «Выезд к клиенту» — перенесено" in sm and "клиент заболел" in sm, f"сводка для модели:\n{sm}")
ok("Иван Васильевич" in tm.summary("Ивану Васильевичу") and "Анна" not in tm.summary("Ивану Васильевичу"), "сводка по одному человеку")
n0 = len(TG.sent)
TG.push(ANNA, "/tasks")
ok(wait(lambda: any("Выезд к клиенту" in x for x in texts(ANNA, n0))), "/tasks — мои открытые поручения с кнопками")
tm2 = T.Team(Host(), tmp / "team.json", tmp / "team_bot.json")
ok(len(tm2.public()["tasks"]) == len(tm.public()["tasks"]) and tm2.public()["connected"], "всё переживает перезапуск")
tm.stop(); tm2.stop()
n0 = len(TG.sent)
tm.member_del({m["name"]: m["id"] for m in tm.public()["members"]}["Иван Сергеевич"])
ok(len(tm.public()["members"]) == 2, "сотрудника можно убрать")

# ---------- часть 2: ядро, голос, студия ----------
import asyncio  # noqa: E402
import subprocess  # noqa: E402
import websockets  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

LLM, PORT = free(), free()
mock = subprocess.Popen([sys.executable, str(TESTS / "mock_llm.py"), str(LLM)])
cfg = tmp / "cfg"; cfg.mkdir()
st = tmp / "st"; st.mkdir()
# готовая команда из части 1 — в папки ядра
(st / "team.json").write_text((tmp / "team.json").read_text())
(st / "team").mkdir(); [(st / "team" / f.name).write_bytes(f.read_bytes()) for f in (tmp / "team").iterdir()]
(cfg / "team_bot.json").write_text((tmp / "team_bot.json").read_text())
(cfg / "settings.json").write_text(json.dumps({"persona": "lira", "user_name": "Михаил", "audio": {"sounds": False, "follow_up_seconds": 0},
    "ui": {"news_seen": "99.0.0", "welcome": "done"}, "stt": {"engine": "vosk"}, "tts": {"engine": "off"}, "updates": {"auto_check": False},
    "features": {"team": True, "games": True},
    "llm": {"active": "m", "profiles": {"m": {"name": "Мок", "kind": "openai", "base_url": f"http://127.0.0.1:{LLM}/v1", "model": "mock"}}}}))
env = dict(os.environ, DEWIAR_CONFIG_DIR=str(cfg), DEWIAR_STATE_DIR=str(st), DEWIAR_PORT=str(PORT), DEWIAR_ASSUME_AEC="1",
           DEWIAR_WORKSPACE_DIR=str(tmp / "ws"), DEWIAR_DRY_TOOLS=str(tmp / "dry.jsonl"))
core = subprocess.Popen([PY, str(ROOT / "core/main.py"), "--wav", str(TESTS / "silence90.wav"), "--null-audio"], env=env,
                        stdout=open(tmp / "core.log", "w"), stderr=subprocess.STDOUT)
R, events = {}, []


async def run():
    ws_ = None
    for _ in range(300):
        await asyncio.sleep(0.2)
        if (cfg / "token").exists():
            try:
                ws_ = await websockets.connect(f"ws://127.0.0.1:{PORT}", max_size=None); break
            except OSError:
                continue
    await ws_.send(json.dumps({"cmd": "hello", "token": (cfg / "token").read_text().strip()}))
    n, replies = [0], {}

    async def call(cmd, **args):
        n[0] += 1; i = n[0]; await ws_.send(json.dumps({"id": i, "cmd": cmd, "args": args}))
        for _ in range(600):
            if i in replies:
                r = replies.pop(i)
                return r.get("data") if r.get("ok", True) else {"error": r.get("error")}
            await asyncio.sleep(0.05)

    async def reader():
        async for raw in ws_:
            e = json.loads(raw)
            if e["type"] == "reply":
                replies[e["id"]] = e
            elif e["type"] != "level":
                events.append(e)
    rd = asyncio.ensure_future(reader())
    await asyncio.sleep(1.5)
    R["get"] = await call("team_get")
    n0 = len(TG.sent)
    await call("say", text="Поручи Анне подготовить счёт для «Северного» до среды 12:00")
    for _ in range(200):
        if any("счёт для «Северного»" in x for x in texts(ANNA, n0)):
            break
        await asyncio.sleep(0.1)
    R["voice"] = texts(ANNA, n0)
    R["after"] = await call("team_get")
    R["cal"] = await call("calendar_month", year=datetime.now().year, month=datetime.now().month)
    rd.cancel()
    await ws_.close()


try:
    asyncio.run(run())
    ok(R["get"]["connected"] and len(R["get"]["members"]) == 2, "ядро: команда на месте, бот подключён")
    ok(any("подготовить счёт для «северного»" in x.lower() for x in R["voice"]), f"голосом «поручи Анне…» — карточка ушла Анне: {R['voice'][:1]}")
    nt = [x for x in R["after"]["tasks"] if "Северного" in x["title"]]
    ok(nt and datetime.fromisoformat(nt[0]["due"]).weekday() == 2 and nt[0]["due"].endswith("12:00"), f"срок — среда 12:00: {nt[:1] and nt[0]['due']}")
    tok = (cfg / "token").read_text().strip()
    errs = []
    with sync_playwright() as pw:
        b = pw.chromium.launch(); pg = b.new_page(viewport={"width": 1440, "height": 1000})
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto((ROOT / "ui/settings.html").as_uri() + f"?token={tok}&port={PORT}"); time.sleep(3)
        nb = pg.locator('nav button[data-p="team"]')
        ok(nb.count() == 1 and nb.is_visible(), "студия: «Поручения» в меню (раздел включён)")
        nb.click(); time.sleep(1.5)
        t = pg.inner_text("#p-team")
        ok("Ромашка" in t and "Новые" in t and "В работе" in t and "Сделано" in t and "Перенесено" in t, "доска: «Новые», «В работе», «Сделано», «Перенесено»")
        ok(pg.locator("#tm-board .tm-card").count() >= 3, f"карточки поручений: {pg.locator('#tm-board .tm-card').count()}")
        if SHOTS:
            pg.screenshot(path=os.path.join(SHOTS, "team.png"))
        pg.locator("#tm-board .tm-card", has_text="Выезд к клиенту").first.click(); time.sleep(0.6)
        d = pg.inner_text("#tm-detail")
        ok("клиент заболел" in d and "Анна Ким" in d, "карточка: кто, причина переноса")
        pg.locator("#tm-board .tm-card", has_text="Подготовить договор").first.click(); time.sleep(0.6)
        d = pg.inner_text("#tm-detail")
        ok("Добавьте пункт о штрафах" in d, "история: замечание руководителя")
        if SHOTS:
            pg.locator("#tm-board .tm-card", has_text="Обновить прайс").first.click(); time.sleep(0.5)
            pg.screenshot(path=os.path.join(SHOTS, "team_detail.png"))
        # форма «Поручить»
        pg.click("#tm-new"); time.sleep(0.3)
        pg.select_option("#tm-who", label="Анна Ким")
        pg.fill("#tm-title", "Позвонить в «Северный»")
        pg.fill("#tm-due", "завтра к 11")
        n0 = len(TG.sent)
        pg.click("#tm-send"); time.sleep(1.5)
        ok(any("Позвонить в «Северный»" in x for x in texts(ANNA, n0)) and "Позвонить в «Северный»" in pg.inner_text("#tm-board"),
           "«Поручить» из студии — ушло Анне и на доске")
        pg.click('#p-team .stabs button[data-t="people"]'); time.sleep(0.6)
        pt = pg.inner_text("#tm-people")
        ok("Анна Ким" in pt and "в Telegram" in pt, "вкладка «Сотрудники»: кто подключён")
        pg.click('#p-team .stabs button[data-t="how"]'); time.sleep(0.5)
        bt = pg.inner_text("#tm-bots")
        ok("Telegram" in bt and "@romashka_team_bot" in bt and "MAX" in bt and "не подключён" in bt and pg.locator("#tm-bots [data-on=max]").count() == 1,
           f"«Как это работает»: бот Telegram подключён, MAX — можно подключить вторым: {bt!r}")
        pg.click('#p-team .stabs button[data-t="people"]'); time.sleep(0.4)
        pg.fill("#tm-pname", "Ольга Петровна"); pg.fill("#tm-prole", "бухгалтерия"); pg.click("#tm-padd"); time.sleep(1)
        ok("Ольга Петровна" in pg.inner_text("#tm-people") and pg.locator("#tm-people [data-copy]").count() >= 1, "добавить сотрудника — ссылка-приглашение")
        if SHOTS:
            pg.screenshot(path=os.path.join(SHOTS, "team_people.png"))
        pg.click('nav button[data-p="calendar"]'); time.sleep(1.2)
        ok("Поручения" in pg.inner_text("#p-calendar") or any(it.get("cal") == "Поручения" for v in R["cal"]["days"].values() for it in v),
           "календарь: поручения со сроком")
        ok(not errs, f"без ошибок на странице: {errs[:2]}")
        b.close()
finally:
    core.terminate(); mock.terminate()
print("ИТОГ:", "все проверки пройдены" if not fails else f"не пройдено {len(fails)}")
sys.exit(1 if fails else 0)
