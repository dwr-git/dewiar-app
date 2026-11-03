"""03.11, человек: «пробую настроить почту (сгенерил спец-пароль и заполнил поля) — просит адрес и пароль приложения. Какого
приложения?» Адрес подставило автозаполнение (событие change не пришло — серверы не угадались), студия прислала пустые
поля серверов, и они затирали угаданное: smtp_host пустой → «сначала укажите адрес и пароль приложения».
Теперь пустые поля серверов не затирают угаданное, а если чего-то не хватает — сказано, чего именно и что такое пароль приложения."""
import os, sys, tempfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
import mail as M  # noqa: E402
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


tmp = Path(tempfile.mkdtemp())
m = M.Mail(path=tmp / "mail.json")
blank = {"smtp_host": "", "smtp_port": 465, "smtp_security": "ssl", "imap_host": "", "imap_port": 993, "name": "", "login": ""}
pub = m.save(dict(blank, address="someone@gmail.com", password="abcd efgh ijkl mnop"))
b = m.boxes[0].data
ok(pub["boxes"][0]["configured"] and b["smtp_host"] == "smtp.gmail.com" and b["imap_host"] == "imap.gmail.com",
   f"адрес автозаполнением, поля серверов пустые — серверы Gmail подставились сами: {b.get('smtp_host')!r}, {b.get('imap_host')!r}")
ok(b["password"] == "abcdefghijklmnop", "пароль Google с пробелами — без пробелов")
pub = m.save(dict(blank, address="someone@gmail.com", password=""))
ok(m.boxes[0].data["smtp_host"] == "smtp.gmail.com" and m.boxes[0].data["password"], "повторное «Подключить» с пустыми полями — ничего не стёрто")
m2 = M.Mail(path=tmp / "mail2.json")
m2.save(dict(blank, address="someone@gmail.com", password=""))
try:
    m2.boxes[0].test(); err = ""
except M.MailError as e:
    err = str(e)
ok("не пароль от почты" in err and "выдаёт сама почта" in err, f"нет пароля — сказано, что такое «пароль приложения»: {err!r}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
