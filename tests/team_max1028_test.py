"""«Поручения» через MAX (28.10, владелец: «не только Telegram… чтобы масштабируемо было»): у каждого мессенджера свой
бот компании, Team различает каналы. Поддельный Bot API MAX (DEWIAR_MAX_API): бот подключается, ссылка-приглашение
max.ru/<бот>?start=<код>, вход по «Запустить» (bot_started), карточка с кнопками-вложениями, «Беру» (нажатие без чата —
чат берётся у сотрудника), правка кнопок (PUT /messages), «Сделано» с фото по ссылке, перенос; токен личного MAX не
принимается; ответы уходят в тот канал, откуда пришло событие."""
import json, os, re, socket, sys, tempfile, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


def free():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


TOKEN, PERSONAL = "max-team-token-abcdefghijklmnopqrstuvwxyz", "max-personal-token-abcdefghijklmnopqrst"
PETR, CHAT = 9001, 7001
JPEG = b"\xff\xd8\xff\xe0" + b"1" * 300 + b"\xff\xd9"


class MX:
    ups, sent, edits, answers, lock, n = [], [], [], [], threading.Lock(), [0]

    @classmethod
    def add(cls, u):
        with cls.lock:
            cls.ups.append(u)


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def out(self, code, obj):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b)))
        self.end_headers(); self.wfile.write(b)

    def _auth(self):
        return self.headers.get("Authorization") == TOKEN

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/files/photo.jpg":
            self.send_response(200); self.send_header("Content-Length", str(len(JPEG))); self.end_headers(); self.wfile.write(JPEG); return
        if not self._auth():
            return self.out(401, {"code": "verify.token", "message": "Invalid access_token"})
        if u.path == "/me":
            return self.out(200, {"user_id": 1, "username": "romashka_max_bot", "first_name": "Ромашка"})
        if u.path == "/updates":
            end = time.time() + 1
            while time.time() < end:
                with MX.lock:
                    got, MX.ups[:] = list(MX.ups), []
                if got:
                    return self.out(200, {"updates": got, "marker": int(time.time() * 1000)})
                time.sleep(0.05)
            return self.out(200, {"updates": [], "marker": 1})
        self.out(404, {})

    def _body(self):
        raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        return json.loads(raw or b"{}")

    def do_POST(self):
        if not self._auth():
            return self.out(401, {"code": "verify.token"})
        u = urlparse(self.path); q = parse_qs(u.query); b = self._body()
        if u.path == "/messages":
            with MX.lock:
                MX.n[0] += 1; mid = f"mid.{MX.n[0]}"
                MX.sent.append((int(q["chat_id"][0]), b, mid))
            return self.out(200, {"message": {"recipient": {"chat_id": int(q["chat_id"][0])}, "body": {"mid": mid, "text": b.get("text")}}})
        if u.path == "/answers":
            with MX.lock:
                MX.answers.append(q.get("callback_id", [""])[0])
            return self.out(200, {"success": True})
        self.out(404, {})

    def do_PUT(self):
        if not self._auth():
            return self.out(401, {"code": "verify.token"})
        u = urlparse(self.path); q = parse_qs(u.query); b = self._body()
        with MX.lock:
            MX.edits.append((q.get("message_id", [""])[0], b))
        self.out(200, {"success": True})


srv = ThreadingHTTPServer(("127.0.0.1", free()), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
API = f"http://127.0.0.1:{srv.server_port}"
os.environ["DEWIAR_MAX_API"] = API
tmp = Path(tempfile.mkdtemp())
os.environ["DEWIAR_CONFIG_DIR"] = str(tmp / "cfg0")
sys.path.insert(0, str(ROOT / "core"))
import team as T  # noqa: E402


class S:
    def get(self, k, sub=None):
        return {"user_name": "Михаил"}.get(k)


class Host:
    def __init__(self): self.s, self.pushed, self.said = S(), [], []
    def emit(self, t, **k): pass
    def push(self, title, text, **k): self.pushed.append(text)
    def announce(self, text): self.said.append(text)


class PersonalMax:
    data = {"token": PERSONAL}


def wait(pred, limit=6):
    end = time.time() + limit
    while time.time() < end:
        if pred():
            return True
        time.sleep(0.05)
    return False


def texts():
    with MX.lock:
        return [b.get("text", "") for c, b, _ in MX.sent if c == CHAT]


host = Host()
tm = T.Team(host, tmp / "team.json", tmp / "team_bot.json", personal_max=PersonalMax())
try:
    tm.connect(PERSONAL, "max"); ok(False, "личный MAX не принимается")
except T.TeamError as e:
    ok("личного бота" in str(e), "токен личного бота MAX в «Поручения» не принимается")
p = tm.connect(TOKEN, "max")
mx = next(b for b in p["bots"] if b["ch"] == "max")
ok(p["connected"] and mx["connected"] and mx["bot"] == "romashka_max_bot" and not next(b for b in p["bots"] if b["ch"] == "tg")["connected"],
   "бот компании в MAX подключён, Telegram — нет")
p = tm.member_add("Пётр Ильич", "склад")
m = p["members"][0]
ok(m["links"].get("max", "").startswith("https://max.ru/romashka_max_bot?start=") and "tg" not in m["links"], f"ссылка-приглашение в MAX: {m['links']}")
code = m["links"]["max"].rsplit("=", 1)[1]
MX.add({"update_type": "bot_started", "chat_id": CHAT, "user": {"user_id": PETR, "first_name": "Пётр"}, "payload": code})
ok(wait(lambda: any("Здравствуйте, Пётр Ильич" in t for t in texts())), "«Запустить» в MAX — сотрудник вошёл, бот поздоровался там же")
ok(wait(lambda: any("подключился к поручениям в MAX" in x for x in host.pushed)), "руководителю — «подключился к поручениям в MAX»")
r = tm.assign("Петру", "Пересчитать коробки на складе", "завтра к 10")
card = [b for c, b, _ in MX.sent if c == CHAT and "Пересчитать" in (b.get("text") or "")]
kb = card and card[0].get("attachments", [{}])[0].get("payload", {}).get("buttons", [[]])[0]
ok(r["sent"] and card and [x["text"] for x in kb] == ["Беру", "Перенести…"] and kb[0]["payload"] == f"tk:{r['id']}:take",
   "карточка в MAX — с кнопками «Беру» и «Перенести…»")
tid = r["id"]
MX.add({"update_type": "message_callback", "callback": {"callback_id": "cb1", "payload": f"tk:{tid}:take", "user": {"user_id": PETR}}})
ok(wait(lambda: tm.st["tasks"][tid]["state"] == "work"), "«Беру» в MAX — в работе (чат взят у сотрудника)")
ok(wait(lambda: "cb1" in MX.answers) and wait(lambda: any(e[0].startswith("mid.") for e in MX.edits)), "нажатие подтверждено, кнопки под карточкой сменились (PUT /messages)")
ok(wait(lambda: any("в работе" in t for t in texts())), "ответ — в MAX")
MX.add({"update_type": "message_callback", "callback": {"callback_id": "cb2", "payload": f"tk:{tid}:done", "user": {"user_id": PETR}}})
wait(lambda: any("пару слов" in t for t in texts()))
MX.add({"update_type": "message_created", "message": {"recipient": {"chat_id": CHAT, "chat_type": "dialog"}, "sender": {"user_id": PETR, "first_name": "Пётр"},
        "body": {"mid": "in1", "text": "Пересчитал, 140 штук", "attachments": [{"type": "image", "payload": {"url": API + "/files/photo.jpg"}}]}}})
ok(wait(lambda: tm.st["tasks"][tid]["state"] == "done"), "«Сделано» в MAX")
t = tm.st["tasks"][tid]
ok(t["report"]["t"] == "Пересчитал, 140 штук" and (tmp / "team" / t["report"]["photo"]).read_bytes() == JPEG, "отчёт и фото из MAX сохранены")
ok(wait(lambda: any("Пётр Ильич сделал: «Пересчитать коробки на складе» — Пересчитал" in x for x in host.said)), "руководителю вслух — кто и что сделал")
r2 = tm.assign("Пётр", "Принять фуру")
MX.add({"update_type": "message_callback", "callback": {"callback_id": "cb3", "payload": f"tk:{r2['id']}:move", "user": {"user_id": PETR}}})
wait(lambda: any("На когда переносим" in t for t in texts()))
MX.add({"update_type": "message_created", "message": {"recipient": {"chat_id": CHAT, "chat_type": "dialog"}, "sender": {"user_id": PETR},
        "body": {"mid": "in2", "text": "на пятницу, фура задерживается"}}})
ok(wait(lambda: tm.st["tasks"][r2["id"]]["state"] == "moved") and tm.st["tasks"][r2["id"]]["reason"] == "фура задерживается", f"перенос в MAX — срок и причина: {tm.st['tasks'][r2['id']]} {texts()[-3:]}")
MX.add({"update_type": "message_created", "message": {"recipient": {"chat_id": 5555, "chat_type": "dialog"}, "sender": {"user_id": 4444},
        "body": {"mid": "in3", "text": "привет"}}})
ok(wait(lambda: any(c == 5555 and "рабочий бот" in (b.get("text") or "") for c, b, _ in MX.sent)), "чужому в MAX — одна фраза")
pub = tm.public()
ok(next(x for x in pub["members"] if x["name"] == "Пётр Ильич")["ch"] == "MAX", "в студии видно, где сотрудник: MAX")
tm.stop()
tm2 = T.Team(Host(), tmp / "team.json", tmp / "team_bot.json")
ok(tm2.public()["connected"] and tm2._mch(next(iter(tm2.st["members"].values()))) == "max", "после перезапуска — тот же канал")
tm2.stop()
print("ИТОГ:", "все проверки пройдены" if not fails else f"не пройдено {len(fails)}")
sys.exit(1 if fails else 0)
