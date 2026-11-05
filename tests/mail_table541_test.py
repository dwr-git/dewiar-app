"""№541 (пакет 04.11, ПК 0.82.2, своя модель в LM Studio): «подготовь Excel с содержимым почтового ящика: адрес
отправителя, дата, тема, с вложением или нет, и статистика, с какого адреса сколько писем — с файлами она работать не
может?». read_emails отдавал до 20 писем и без поля «вложение», записать .xlsx было нечем (openpyxl не в комплекте) —
модель за 203 с выдала скрипт на Python. Теперь: mail.headers (заголовки и строение письма пачками), xlsx_lite (Excel
без библиотек), инструмент mail_table и быстрый путь без модели. Поддельный IMAP — с литералом имени файла в BODYSTRUCTURE."""
import email.utils, os, socket, socketserver, sys, tempfile, threading
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ.update(DEWIAR_CONFIG_DIR=str(tmp / "cfg"), DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_DOWNLOADS=str(tmp / "dl"),
                  DEWIAR_DRY_TOOLS="1")
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


USER, PASS = "anna@example.com", "app-pass-123"


def hdr(frm, subj, day):
    return (f"From: {frm}\r\nSubject: {email.header.Header(subj, 'utf-8').encode()}\r\n"
            f"Date: {day}\r\n\r\n").encode()


import email.header  # noqa: E402
TXT = b'("text" "plain" ("charset" "utf-8") NIL NIL "7bit" 10 1 NIL NIL NIL NIL)'
PDF = b'("application" "pdf" ("name" "report.pdf") NIL NIL "base64" 100 NIL ("attachment" ("filename" "report.pdf")) NIL NIL)'
NAME_RU = "договор.pdf".encode()
MSGS = {   # uid: (заголовки, BODYSTRUCTURE (кусками: литерал — отдельно), прочитано)
    1: (hdr("Бухгалтерия <buh@corp.ru>", "Счёт за сентябрь", "Thu, 01 Oct 2026 09:00:00 +0300"), [b"(" + TXT + PDF + b' "mixed")'], True),
    2: (hdr("Мама <mama@mail.ru>", "Приезжай в субботу", "Fri, 02 Oct 2026 10:00:00 +0300"), [TXT], False),
    3: (hdr("Бухгалтерия <buh@corp.ru>", "Договор", "Sat, 03 Oct 2026 11:00:00 +0300"),
        [b"(" + TXT + b'("application" "pdf" ("NAME" ', NAME_RU, b') NIL NIL "base64" 100 NIL NIL NIL NIL) "mixed")'], False),
    4: (hdr("support@pro-talk.ru", "Re[2]: Подписка", "Sun, 25 Oct 2026 21:47:00 +0300"), [TXT], True),
}


class IMAP(socketserver.StreamRequestHandler):
    def w(self, s): self.wfile.write((s + "\r\n").encode() if isinstance(s, str) else s)

    def handle(self):
        self.w("* OK IMAP4rev1 fake ready")
        while True:
            line = self.rfile.readline().decode(errors="replace").strip()
            if not line:
                return
            tag, _, rest = line.partition(" "); cmd = rest.upper()
            if cmd.startswith("CAPABILITY"): self.w("* CAPABILITY IMAP4rev1 AUTH=PLAIN"); self.w(f"{tag} OK done")
            elif cmd.startswith("LOGIN"): self.w(f"{tag} OK logged in")
            elif cmd.startswith("EXAMINE") or cmd.startswith("SELECT"): self.w(f"* {len(MSGS)} EXISTS"); self.w(f"{tag} OK [READ-ONLY] done")
            elif cmd.startswith("UID SEARCH"): self.w("* SEARCH " + " ".join(str(k) for k in MSGS)); self.w(f"{tag} OK done")
            elif cmd.startswith("UID FETCH"):
                for u in [int(x) for x in rest.split(" ")[2].split(",")]:
                    h, parts, seen = MSGS[u]
                    out = f"* {u} FETCH (UID {u} FLAGS ({'\\Seen' if seen else ''}) BODYSTRUCTURE ".encode()
                    for k, part in enumerate(parts):
                        out += (b"{" + str(len(part)).encode() + b"}\r\n" + part) if k % 2 else part
                    out += b" BODY[HEADER.FIELDS (FROM SUBJECT DATE)] {" + str(len(h)).encode() + b"}\r\n" + h + b")\r\n"
                    self.w(out)
                self.w(f"{tag} OK done")
            elif cmd.startswith("LOGOUT"): self.w("* BYE"); self.w(f"{tag} OK bye"); return
            else: self.w(f"{tag} OK")


s = socket.socket(); s.bind(("127.0.0.1", 0)); IP = s.getsockname()[1]; s.close()
srv = socketserver.ThreadingTCPServer(("127.0.0.1", IP), IMAP); srv.daemon_threads = True
threading.Thread(target=srv.serve_forever, daemon=True).start()

from settings import Settings  # noqa: E402
from workspace import Workspace  # noqa: E402
from mail import Mail  # noqa: E402
import tools as TL  # noqa: E402
import xlsx_lite  # noqa: E402

st = Settings(); st.update({"workspace": {"path": str(tmp / "ws")}})
ws = Workspace(st); ws.ensure()
m = Mail(tmp / "mail.json", ws)
m.save({"address": USER, "password": PASS, "smtp_host": "127.0.0.1", "smtp_port": 1, "smtp_security": "none",
        "imap_host": "127.0.0.1", "imap_port": IP, "name": "Анна"})

# 1) заголовки всех писем без текста — и есть ли вложение
hs = m.headers(limit=100)
ok([x["uid"] for x in hs] == ["4", "3", "2", "1"], f"все письма, новые сверху: {[x['uid'] for x in hs]}")
att = {x["uid"]: x["attach"] for x in hs}
ok(att == {"1": True, "2": False, "3": True, "4": False}, f"вложение видно — и когда имя файла пришло литералом (кириллица): {att}")
ok(hs[2]["from"] == "Мама <mama@mail.ru>" and hs[1]["subject"] == "Договор" and hs[0]["unread"] is False and hs[1]["unread"] is True,
   "отправитель, тема (кодированная) и «прочитано» — на месте")

# 2) таблица Excel — открывается настоящим openpyxl, два листа
tb = TL.Toolbox(st, None); tb.hooks["mail"] = m
ok(tb.policy("mail_table")[0], "mail_table у модели есть, когда почта подключена")
r = tb.run("mail_table", {})
files = list((tmp / "dl").glob("*.xlsx"))
ok(files and "Загрузки" in r and "Писем: 4" in r and "с вложениями: 2" in r and "buh@corp.ru — 2" in r, f"ответ модели: {r[:140]}")
try:
    import openpyxl
    wb = openpyxl.load_workbook(files[0])
    ws1, ws2 = wb.worksheets
    head = [c.value for c in ws1[1]]
    ok(wb.sheetnames == ["Письма", "По отправителям"] and head == ["Дата", "Отправитель", "Адрес", "Тема", "Вложение", "Прочитано"],
       f"Excel: листы и колонки — как просили: {wb.sheetnames} {head}")
    rows = [[c.value for c in r_] for r_ in ws1.iter_rows(min_row=2)]
    ok(rows[1] == ["2026-10-03 11:00", "Бухгалтерия", "buh@corp.ru", "Договор", "да", "нет"], f"строка письма: {rows[1]}")
    st_rows = [[c.value for c in r_] for r_ in ws2.iter_rows(min_row=2)]
    ok(st_rows[0][:4] == ["buh@corp.ru", "Бухгалтерия", 2, 2] and len(st_rows) == 3, f"статистика по адресам — числами: {st_rows}")
    ok(ws1.freeze_panes == "A2" and ws1.auto_filter.ref == "A1:F5", "шапка закреплена, фильтр стоит")
except ImportError:
    ok(True, "openpyxl нет — проверяю только файл")

# 3) быстрый путь без модели: просьба из жалобы
import engine as E  # noqa: E402
e = E.Engine.__new__(E.Engine)
said = []
e.mail, e.toolbox = m, tb
e.emit = lambda *a, **k: None
e.set_state = lambda st_: None
e._say_quick = lambda msg, text, via=None, **k: said.append(msg)
q = ("подготовь excel файл с информацией о содержимом почтового ящика с указанием адреса отправителя, даты письма, темы "
     "письма, с вложением письмо или нет и  статистики с какого адреаа сколько иписем в общем")
ok(e._mail_table_cmd(q), "просьба из жалобы №541 — без модели")
import time  # noqa: E402
for _ in range(50):
    if said:
        break
    time.sleep(0.1)
ok(said and said[0].startswith("Готово: таблица") and "«Загрузках»" in said[0] and "Писем — 4" in said[0], f"вслух коротко: {said[:1]}")
ok(len(list((tmp / "dl").glob("*.xlsx"))) == 2, "второй файл — рядом, первый не затёрт")
for t in ("Сколько писем в ящике?", "отправь письмо с таблицей Excel маме", "сделай таблицу расходов в Excel", "проверь почту"):
    ok(not e._mail_table_cmd(t), f"не сюда: «{t}»")

# 4) xlsx_lite сам по себе: спецсимволы, числа, пустые
p = tmp / "t.xlsx"
xlsx_lite.write(p, [("Лист: [1]", [["А", "Б"], ["<&>\"'", 3.5], [None, True]])])
try:
    import openpyxl
    w = openpyxl.load_workbook(p).worksheets[0]
    ok([[c.value for c in r_] for r_ in w.iter_rows()] == [["А", "Б"], ["<&>\"'", 3.5], [None, "да"]] and w.title == "Лист   1",
       f"спецсимволы и числа не ломают файл: {w.title!r}")
except ImportError:
    pass
srv.shutdown()
print("ALL OK" if not fails else f"FAILED: {len(fails)}")
sys.exit(1 if fails else 0)
