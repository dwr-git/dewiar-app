"""Почта: подключение, проверка, письмо с вложением из папки ассистента, чтение входящих — через поддельные
SMTP и IMAP серверы (без шифрования, на 127.0.0.1)."""
import base64, email, os, socket, socketserver, sys, tempfile, threading
from email.message import EmailMessage
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ["DEWIAR_CONFIG_DIR"] = str(tmp / "cfg"); os.environ["DEWIAR_STATE_DIR"] = str(tmp / "st")
sys.path.insert(0, str(ROOT / "core"))
ok = lambda c, m: print(("✅ " if c else "❌ ") + m)
USER, PASS = "anna@example.com", "app-pass-123"
SENT = []


def port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


class SMTP(socketserver.StreamRequestHandler):
    def w(self, s): self.wfile.write((s + "\r\n").encode())
    def handle(self):
        self.w("220 fake ESMTP"); authed = False
        while True:
            line = self.rfile.readline().decode(errors="replace").strip()
            if not line: return
            cmd = line.upper()
            if cmd.startswith("EHLO"): self.w("250-fake"); self.w("250 AUTH PLAIN LOGIN")
            elif cmd.startswith("HELO"): self.w("250 fake")
            elif cmd.startswith("AUTH PLAIN"):
                arg = line.split(" ", 2)[2] if len(line.split(" ")) > 2 else ""
                if not arg: self.w("334 "); arg = self.rfile.readline().decode().strip()
                _, u, p = base64.b64decode(arg).decode().split("\0")
                authed = (u, p) == (USER, PASS); self.w("235 ok" if authed else "535 bad credentials")
            elif cmd.startswith("MAIL") or cmd.startswith("RCPT"): self.w("250 ok" if authed else "530 auth")
            elif cmd == "DATA":
                self.w("354 go"); data = b""
                while True:
                    l = self.rfile.readline()
                    if l in (b".\r\n", b".\n"): break
                    data += l[1:] if l.startswith(b"..") else l
                SENT.append(data); self.w("250 queued")
            elif cmd == "QUIT": self.w("221 bye"); return
            else: self.w("250 ok")


def mk(uid, frm, subj, body, attach=None):
    m = EmailMessage(); m["From"] = frm; m["To"] = USER; m["Subject"] = subj; m["Date"] = "Thu, 01 Oct 2026 09:00:00 +0300"
    m.set_content(body)
    if attach: m.add_attachment(b"%PDF-1.4 fake", maintype="application", subtype="pdf", filename=attach)
    return m.as_bytes()


BOX = {1: (mk(1, "Бухгалтерия <buh@corp.ru>", "Счёт за сентябрь", "Добрый день! Счёт на оплату во вложении.", "счёт.pdf"), True),
       2: (mk(2, "Мама <mama@mail.ru>", "Приезжай в субботу", "Жду тебя в субботу к обеду."), False)}


class IMAP(socketserver.StreamRequestHandler):
    def w(self, s): self.wfile.write((s + "\r\n").encode() if isinstance(s, str) else s)
    def handle(self):
        self.w("* OK IMAP4rev1 fake ready")
        while True:
            line = self.rfile.readline().decode(errors="replace").strip()
            if not line: return
            tag, _, rest = line.partition(" "); cmd = rest.upper()
            if cmd.startswith("CAPABILITY"): self.w("* CAPABILITY IMAP4rev1 AUTH=PLAIN"); self.w(f"{tag} OK done")
            elif cmd.startswith("LOGIN"):
                parts = rest.split(" ")
                u, p = parts[1].strip('"'), parts[2].strip('"')
                self.w(f"{tag} OK logged in" if (u, p) == (USER, PASS) else f"{tag} NO [AUTHENTICATIONFAILED] bad")
            elif cmd.startswith("EXAMINE") or cmd.startswith("SELECT"): self.w(f"* {len(BOX)} EXISTS"); self.w(f"{tag} OK [READ-ONLY] done")
            elif cmd.startswith("UID SEARCH"):
                ids = [str(k) for k, (_, seen) in BOX.items() if "UNSEEN" not in cmd or not seen]
                self.w("* SEARCH " + " ".join(ids)); self.w(f"{tag} OK done")
            elif cmd.startswith("UID FETCH"):
                uid = int(rest.split(" ")[2]); raw, seen = BOX.get(uid, (b"", False))
                if raw:
                    flags = "\\\\Seen" if seen else ""
                    self.w(f"* {uid} FETCH (UID {uid} FLAGS ({flags}) BODY[] {{{len(raw)}}}".encode() + b"\r\n" + raw + b")\r\n")
                self.w(f"{tag} OK done")
            elif cmd.startswith("LOGOUT"): self.w("* BYE"); self.w(f"{tag} OK bye"); return
            else: self.w(f"{tag} OK")


sp, ip = port(), port()
for P, H in ((sp, SMTP), (ip, IMAP)):
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", P), H); srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()

from settings import Settings  # noqa: E402
from workspace import Workspace  # noqa: E402
from mail import Mail, MailError, guess  # noqa: E402
from tools import Toolbox, t_read_emails  # noqa: E402

g = guess("ivan@yandex.ru")
ok(g["smtp_host"] == "smtp.yandex.ru" and g["imap_port"] == 993 and "yandex" in g["help"], "Яндекс: серверы и ссылка на пароль приложения — сами")
ok(guess("x@bk.ru")["smtp_host"] == "smtp.mail.ru" and guess("y@gmail.com")["imap_host"] == "imap.gmail.com", "Mail.ru и Gmail — сами")
s = Settings(); s.update({"workspace": {"path": str(tmp / "ws")}})
ws = Workspace(s); ws.ensure()
m = Mail(tmp / "mail.json", ws)
tb = Toolbox(s, None); tb.hooks["mail"] = m
ok(not tb.policy("send_email")[0], "без настроенной почты инструментов почты у модели нет")
try: m.save({"address": "не-адрес"}); ok(False, "плохой адрес")
except MailError: ok(True, "неверный адрес не принимается")
cfg = {"address": USER, "password": "wrong", "smtp_host": "127.0.0.1", "smtp_port": sp, "smtp_security": "none",
       "imap_host": "127.0.0.1", "imap_port": ip, "name": "Анна"}
m.save(cfg)
r = m.test()
ok("пароль приложения" in r["smtp"] and "пароль" in r["imap"], f"неверный пароль — понятно: {r['smtp'][:60]}")
pub = m.save({"password": PASS})
ok(pub["configured"] and "password" not in pub and pub["has_password"], "пароль сохранён, наружу не отдаётся")
_t = m.test()
ok(_t["smtp"] == "ok" and _t["imap"] == "ok" and _t["check"]["ok"] is True, "проверка: отправка и чтение работают, итог помнится")
ok(tb.policy("send_email") == (True, True) and tb.policy("read_emails") == (True, False), "отправка — с подтверждением, чтение — сразу")
(ws.root / "Заметки" / "Отчёт.md").write_text("# Отчёт\nВсё готово.", encoding="utf-8")
res = m.send("", "Отчёт по задаче", "Привет! Отчёт во вложении.", ["Заметки/Отчёт.md"])
msg = email.message_from_bytes(SENT[-1])
att = [p.get_filename() for p in msg.walk() if p.get_filename()]
ok(res["to"] == [USER] and "Отчёт по задаче" in str(email.header.make_header(email.header.decode_header(msg["Subject"]))) and att == ["Отчёт.md"],
   "«пришли мне»: письмо себе с вложением из папки ассистента")
try: m.send("", "x", "y", ["../../etc/passwd"]); ok(False, "выход из папки")
except Exception: ok(True, "вложить файл вне папки ассистента нельзя")
box = m.inbox(limit=5)
ok([x["uid"] for x in box] == ["2", "1"] and box[1]["files"] == ["счёт.pdf"] and box[0]["unread"] and not box[1]["unread"],
   "входящие: новые сверху, вложения и «непрочитано» видны")
ok([x["uid"] for x in m.inbox(unread=True)] == ["2"], "только непрочитанные")
ok([x["uid"] for x in m.inbox(query="счёт")] == ["1"], "поиск по слову")
full = m.read("1")
ok("Счёт на оплату" in full["text"] and "Бухгалтерия" in full["from"], "письмо целиком")
out = t_read_emails({"limit": 5}, {"mail": m})
ok("Приезжай в субботу" in out and "●" in out, "инструмент read_emails — понятный список для модели")
ok(Mail(tmp / "mail.json", ws).configured(), "настройки почты переживают перезапуск")
# несколько ящиков (пакет 27.10: «как настроить на несколько ящиков? а то только один»)
import json as _json  # noqa: E402
pub = m.save(dict(cfg, address="work@example.com", login=USER, password=PASS), box=1)
ok(len(pub["boxes"]) == 2 and pub["boxes"][1]["address"] == "work@example.com" and pub["address"] == USER and all("password" not in b for b in pub["boxes"]),
   "второй ящик добавлен, главный — прежний, пароли наружу не отдаются")
try: m.save(dict(cfg, password=PASS), box=2); ok(False, "тот же ящик дважды")
except MailError: ok(True, "тот же ящик второй раз не добавляется")
both = m.inbox(limit=5)
ok(len(both) == 4 and {x["box"] for x in both} == {USER, "work@example.com"} and "1:1" in [x["uid"] for x in both], f"«что в почте?» — письма из всех ящиков: {[x['uid'] for x in both]}")
ok("Счёт на оплату" in m.read("1:1")["text"] and m.read("1:1")["box"] == "work@example.com", "письмо второго ящика целиком — по его номеру")
ok([x["box"] for x in m.inbox(box="work")] == ["work@example.com"] * 2, "«что в рабочей почте?» — один ящик по адресу")
out = t_read_emails({"limit": 5}, {"mail": m})
ok("в work@example.com" in out, "у модели видно, в каком ящике письмо")
m.send("", "С рабочего", "Тест", box="work@example.com")
ok("work@example.com" in email.message_from_bytes(SENT[-1])["From"], "письмо — с названного ящика")
ok(len(Mail(tmp / "mail.json", ws).boxes) == 2 and _json.loads((tmp / "mail.json").read_text())["boxes"][1]["address"] == "work@example.com",
   "оба ящика переживают перезапуск")
(tmp / "old.json").write_text(_json.dumps(dict(cfg, password=PASS)), encoding="utf-8")
ok(Mail(tmp / "old.json", ws).data.get("address") == USER and len(Mail(tmp / "old.json", ws).boxes) == 1, "старый файл с одним ящиком читается как раньше")
m.forget(1)
ok(len(m.boxes) == 1 and m.data["address"] == USER, "«Отключить» второй ящик — главный остался")
m.forget()
ok(not m.configured() and not (tmp / "mail.json").exists(), "«Отключить» — всё стёрто")
