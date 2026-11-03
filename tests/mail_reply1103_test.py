"""03.11, владелец: «почту подключил, прошу ответить на письмо — пишет „читаю“, и на этом всё, по 3–4 раза приходится
просить». Модели приходилось связать read_emails → read_email → send_email (адрес, тема) — слабая сбивалась на «читаю».
Теперь send_email(reply_to=номер или «от кого», body) — кому, «Re: тема», In-Reply-To и цитата подставляются сами;
«Читаю.» без действия — обещание, модель просят сделать."""
import os, sys, tempfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
import mail as M  # noqa: E402
import quality as Q  # noqa: E402
import tools as T  # noqa: E402
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


tmp = Path(tempfile.mkdtemp())
mm = M.Mail(path=tmp / "mail.json")
mm.save({"address": "me@gmail.com", "password": "abcdefghijklmnop"})
sent = []
LETTER = {"uid": "42", "from": "Иван Петров <ivan@firma.by>", "to": "me@gmail.com", "subject": "Встреча в пятницу", "date": "Mon, 3 Nov 2026 10:00:00 +0300",
          "text": "Добрый день!\nУдобно ли в пятницу в 15:00?", "files": [], "message_id": "<abc@firma.by>", "references": "", "reply_to": ""}
b = mm.boxes[0]
b.read = lambda uid, folder="INBOX", mark=False: dict(LETTER, uid=str(uid))
b.inbox = lambda limit=10, unread=False, query="", folder="INBOX": [dict(LETTER, snippet="", unread=True)] if query.lower() in "иван петров ivan@firma.by встреча" else []
b.send = lambda to, subject, body, attachments=(), headers=None: (sent.append((to, subject, body, headers)) or {"to": [to], "subject": subject, "attachments": []})
r = mm.reply("Иван", "Да, в пятницу в 15:00 удобно.")
to, subj, body, hdr = sent[-1]
ok(to == "ivan@firma.by" and subj == "Re: Встреча в пятницу", f"ответ по «от кого»: кому и «Re: тема» — сами: {to}, {subj}")
ok(hdr.get("In-Reply-To") == "<abc@firma.by>" and "<abc@firma.by>" in hdr.get("References", ""), "в цепочке письма (In-Reply-To, References)")
ok(body.startswith("Да, в пятницу") and "> Удобно ли в пятницу в 15:00?" in body, "текст ответа и цитата письма")
mm.reply("42", "Хорошо")
ok(sent[-1][0] == "ivan@firma.by", "ответ по номеру письма из списка")
try:
    mm.reply("Сидоров", "привет"); err = ""
except M.MailError as e:
    err = str(e)
ok("не нашла письма" in err, f"не нашла — так и говорит: {err!r}")
ctx = {"mail": mm, "settings": None}
T._mail = lambda c: mm
out = T.t_send_email({"reply_to": "Иван", "body": "Согласен."}, ctx)
ok(out.startswith("Ответ на письмо «Встреча в пятницу» отправлен: ivan@firma.by"), f"инструмент send_email с reply_to: {out!r}")
spec = T.TOOLS["send_email"]
ok("reply_to" in str(spec[1]) and "subject" not in (spec[1].get("required") or []), "у send_email есть reply_to, тема для ответа не нужна")
ok(all(Q.looks_like_promise(t, "ответь Ивану на письмо") for t in ("Читаю.", "Читаю письмо.", "Открываю почту.", "Пишу ответ Ивану.")),
   "«Читаю.», «Открываю почту.» без действия — обещание: модель попросят сделать")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
