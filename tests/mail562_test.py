"""№562 (ПК 0.84.2, 05.11, Serge): «Было бы удобно: 1. Просмотр письма в HTML-виде. 2. Минимальное управление почтой:
Удалить, В спам, Переслать». Теперь письмо на «Главной» открывается «как в письме» — в рамке без скриптов и без своего
источника (sandbox="", CSP default-src 'none'), HTML вычищен (core/mailhtml.py), картинки из интернета — только по
кнопке, ссылки — списком под письмом; «Текстом» — как раньше. «Удалить» — в «Корзину» почты (папка по пометке \\Trash,
иначе по имени), «В спам» — в «Спам» (\\Junk), «Переслать» — письмо целиком (оригинал вложением .eml); голосом — то же
(manage_email, с вопросом «Удалить письмо …?»). Почта — поддельный IMAP/SMTP на 127.0.0.1."""
import base64, email, json, os, re, socket, socketserver, sys, tempfile, threading
from email.message import EmailMessage
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ["DEWIAR_CONFIG_DIR"] = str(tmp / "cfg"); os.environ["DEWIAR_STATE_DIR"] = str(tmp / "st")
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


USER, PASS = "serge@example.com", "app-pass-123"
SENT = []


def port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


class SMTP(socketserver.StreamRequestHandler):
    def w(self, s): self.wfile.write((s + "\r\n").encode())
    def handle(self):
        self.w("220 fake ESMTP")
        while True:
            line = self.rfile.readline().decode(errors="replace").strip()
            if not line: return
            cmd = line.upper()
            if cmd.startswith("EHLO"): self.w("250-fake"); self.w("250 AUTH PLAIN LOGIN")
            elif cmd.startswith("AUTH PLAIN"):
                arg = line.split(" ", 2)[2] if len(line.split(" ")) > 2 else ""
                if not arg: self.w("334 "); arg = self.rfile.readline().decode().strip()
                _, u, p = base64.b64decode(arg).decode().split("\0"); self.w("235 ok" if (u, p) == (USER, PASS) else "535 bad")
            elif cmd == "DATA":
                self.w("354 go"); data = b""
                while True:
                    l = self.rfile.readline()
                    if l in (b".\r\n", b".\n"): break
                    data += l[1:] if l.startswith(b"..") else l
                SENT.append(data); self.w("250 queued")
            elif cmd == "QUIT": self.w("221 bye"); return
            else: self.w("250 ok")


PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")


def letter(subj, frm, html=True, plain=True):
    m = EmailMessage(); m["From"] = frm; m["To"] = USER; m["Subject"] = subj; m["Date"] = "Thu, 05 Nov 2026 12:04:00 +0300"
    m["Message-ID"] = f"<{abs(hash(subj))}@example.org>"
    if plain:
        m.set_content("Здравствуйте, Сергей!\nЗавершается регистрация на сессию.")
    if html:
        h = ('<html><head><style>.hero{background:#0b5cff;color:#fff}</style><script>alert(1)</script></head><body onload="alert(2)">'
             '<div class="hero"><h1>Информационная безопасность</h1></div><p>Здравствуйте, <b>Сергей</b>!</p>'
             '<a href="https://tadviser.example/reg?u=1" onclick="x()">Зарегистрироваться</a> <a href="javascript:alert(3)">плохая</a>'
             '<img src="https://track.example/pixel.gif"><img src="cid:logo@x"><iframe src="https://evil.example"></iframe>'
             '<form action="https://evil.example"><input name="p"></form></body></html>')
        if plain:
            m.add_alternative(h, subtype="html")
            m.get_payload()[1].add_related(PNG, "image", "png", cid="<logo@x>")
        else:
            m.set_content(h, subtype="html")
    m.add_attachment(b"%PDF-1.4 fake", maintype="application", subtype="pdf", filename="программа.pdf")
    return m.as_bytes()


ST = {"caps": "IMAP4rev1 AUTH=PLAIN MOVE UIDPLUS", "list": "special", "cmds": []}
F = {}


def reset(list_kind="special", caps="IMAP4rev1 AUTH=PLAIN MOVE UIDPLUS"):
    ST.update(list=list_kind, caps=caps, cmds=[])
    F.clear()
    F["INBOX"] = {1: letter("Счёт за ноябрь", "Бухгалтерия <buh@corp.example>"), 2: letter("Регистрация на сессию", "Александр Панов <panov@tadviser.example>"),
                  3: letter("Только HTML", "Рассылка <news@shop.example>", plain=False)}
    trash, junk = {"special": ("&BBoEPgRABDcEOAQ9BDA-", "&BCEEPwQwBDw-"), "names": ("Trash", "Spam"), "none": (None, None)}[list_kind]
    for n in (trash, junk):
        if n: F[n] = {}
    return trash, junk


def unq(s):
    s = s.strip()
    return s[1:-1].replace('\\"', '"') if s.startswith('"') else s


class IMAP(socketserver.StreamRequestHandler):
    def w(self, s): self.wfile.write((s + "\r\n").encode() if isinstance(s, str) else s)
    def handle(self):
        self.w("* OK IMAP4rev1 fake ready"); cur = "INBOX"
        while True:
            line = self.rfile.readline().decode(errors="replace").strip()
            if not line: return
            tag, _, rest = line.partition(" "); cmd = rest.upper(); ST["cmds"].append(rest)
            if cmd.startswith("CAPABILITY"): self.w("* CAPABILITY " + ST["caps"]); self.w(f"{tag} OK done")
            elif cmd.startswith("LOGIN"): self.w(f"{tag} OK logged in")
            elif cmd.startswith("LIST"):
                self.w('* LIST (\\HasNoChildren) "/" INBOX')
                for name in F:
                    if name == "INBOX": continue
                    fl = ("\\Trash" if name.startswith("&BBo") else "\\Junk") if ST["list"] == "special" else ""
                    self.w(f'* LIST (\\HasNoChildren {fl}) "/" "{name}"'.replace(" )", ")"))
                self.w('* LIST (\\Noselect \\HasChildren) "/" "[Gmail]"')
                self.w(f"{tag} OK done")
            elif cmd.startswith("EXAMINE") or cmd.startswith("SELECT"):
                cur = unq(rest.split(" ", 1)[1]); self.w(f"* {len(F.get(cur, {}))} EXISTS")
                self.w(f"{tag} OK [READ-ONLY] done" if cmd.startswith("EXAMINE") else f"{tag} OK [READ-WRITE] done")
            elif cmd.startswith("UID FETCH"):
                parts = rest.split(" ", 3); uid = int(parts[2]); raw = F.get(cur, {}).get(uid)
                if raw:
                    if "HEADER.FIELDS" in cmd:
                        hdr = b"".join(l + b"\r\n" for l in raw.split(b"\n") if re.match(rb"(From|Subject):", l, re.I)).replace(b"\r\r", b"\r") + b"\r\n"
                        self.w(f"* {uid} FETCH (UID {uid} BODY[HEADER.FIELDS (FROM SUBJECT)] {{{len(hdr)}}}".encode() + b"\r\n" + hdr + b")\r\n")
                    elif "BODY" in cmd:
                        self.w(f"* {uid} FETCH (UID {uid} FLAGS (\\Seen) BODY[] {{{len(raw)}}}".encode() + b"\r\n" + raw + b")\r\n")
                    else:
                        self.w(f"* {uid} FETCH (UID {uid})")
                self.w(f"{tag} OK done")
            elif cmd.startswith("UID SEARCH"): self.w("* SEARCH " + " ".join(str(k) for k in sorted(F.get(cur, {})))); self.w(f"{tag} OK done")
            elif cmd.startswith("UID MOVE") or cmd.startswith("UID COPY"):
                _, op, uid, dest = rest.split(" ", 3); dest = unq(dest); uid = int(uid)
                if dest not in F: self.w(f"{tag} NO [TRYCREATE] no such folder"); continue
                F[dest][uid] = F[cur][uid]
                if op.upper() == "MOVE": del F[cur][uid]
                self.w(f"{tag} OK done")
            elif cmd.startswith("UID STORE"): self.w(f"{tag} OK done")
            elif cmd.startswith("UID EXPUNGE") or cmd.startswith("EXPUNGE"):
                uid = int(rest.split(" ")[2]) if cmd.startswith("UID") else None
                for u in list(F[cur]):
                    if uid in (None, u) and any(f"UID STORE {u} +FLAGS.SILENT (\\DELETED)" == c.upper() for c in ST["cmds"]): del F[cur][u]
                self.w(f"{tag} OK done")
            elif cmd.startswith("LOGOUT"): self.w("* BYE"); self.w(f"{tag} OK bye"); return
            else: self.w(f"{tag} OK")


sp, ip = port(), port()
for P, H in ((sp, SMTP), (ip, IMAP)):
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", P), H); srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()

import mail as M  # noqa: E402
import mailhtml as MH  # noqa: E402
import tools as T  # noqa: E402
from settings import Settings  # noqa: E402

mm = M.Mail(tmp / "mail.json")
mm.save({"address": USER, "password": PASS, "smtp_host": "127.0.0.1", "smtp_port": sp, "smtp_security": "none",
         "imap_host": "127.0.0.1", "imap_port": ip, "name": "Сергей"})

# ---------- папки: изменённый UTF-7, пометки SPECIAL-USE, имена ----------
ok(M._utf7_imap("&BBoEPgRABDcEOAQ9BDA-") == "Корзина" and M._utf7_imap("&BCEEPwQwBDw-") == "Спам" and M._utf7_imap("A&-B") == "A&B",
   "имена папок по-русски (изменённый UTF-7)")
trash, junk = reset("special")
ok(mm.boxes[0].special("trash") == (trash, "Корзина") and mm.boxes[0].special("junk") == (junk, "Спам"), "«Корзина» и «Спам» — по пометкам \\Trash и \\Junk")
reset("names")
ok(mm.boxes[0].special("trash") == ("Trash", "Trash") and mm.boxes[0].special("junk") == ("Spam", "Spam"), "без пометок — по частым именам (Trash, Spam)")

# ---------- «как в письме» ----------
reset("special")
r = mm.read("2", html_view=True)
h = r.get("html", "")
ok(r.get("plain") is True and "Здравствуйте, <b>Сергей</b>" in h and 'class="hero"' in h and "<style>" in h, "HTML письма — с оформлением, текстовая часть тоже есть")
ok(not re.search(r"(?i)<script|<iframe|<form|<input|onload|onclick|javascript:|alert\(", h), f"скрипты, фреймы, формы, on… и javascript: — вычищены: {h[:300]!r}")
ok('data-href="https://tadviser.example/reg?u=1"' in h and not re.search(r"\shref=", h), "ссылки внутри письма не кликаются (href → data-href)")
ok(r.get("html_links") == [{"url": "https://tadviser.example/reg?u=1", "text": "Зарегистрироваться"}], f"ссылки — списком с текстом: {r.get('html_links')}")
ok('src="data:image/png;base64,' in h and 'src="https://track.example/pixel.gif"' in h and r.get("html_remote") == 1,
   "картинка из письма (cid:) — прямо в тексте; внешняя — одна, грузится только по кнопке")
r3 = mm.read("3", html_view=True)
ok(r3.get("plain") is False and r3.get("html") and "Информационная безопасность" in r3["text"], "только HTML — есть и выжимка текстом")
ok("html" not in mm.read("2"), "без html_view — как раньше, только текст (голосу и модели HTML не нужен)")
s = MH.sanitize('<p style="background:url(javascript:alert(1));width:expression(alert(2))">x</p><style>@import url(https://e/x.css);b{background:url(http://e/y.png)}</style>'
                '<svg><script>alert(3)</script></svg><img src="http://e/z.png"><a href=" JaVaScRiPt:alert(4)">a</a><base href="https://e/"><meta http-equiv="refresh" content="0;url=https://e">')
ok(not re.search(r"(?i)javascript|expression\(|@import|http://|<svg|<script|<base|<meta|refresh", s["html"]) and "x" in s["html"],
   f"стили и адреса без лазеек: {s['html']!r}")

# ---------- удалить, в спам: MOVE, COPY+EXPUNGE, без корзины ----------
trash, junk = reset("special")
res = mm.manage("1", "trash")
ok(res["folder"] == "Корзина" and not res["permanent"] and 1 not in F["INBOX"] and 1 in F[trash] and any(c.upper().startswith("UID MOVE 1") for c in ST["cmds"]),
   f"«Удалить» — в «Корзину» почты (MOVE): {res}")
res = mm.manage("Панов", "junk")
ok(res["folder"] == "Спам" and 2 in F[junk] and 2 not in F["INBOX"], "«В спам» — по «от кого» тоже находит письмо")
trash, junk = reset("names", caps="IMAP4rev1 AUTH=PLAIN")
res = mm.manage("1", "trash")
ok(1 in F["Trash"] and 1 not in F["INBOX"] and any(c.upper() == "EXPUNGE" for c in ST["cmds"]) and any(c.upper().startswith("UID COPY 1") for c in ST["cmds"]),
   "почта без MOVE — COPY, пометка \\Deleted и EXPUNGE")
reset("none")
try:
    mm.manage("1", "junk"); err = ""
except M.MailError as e:
    err = str(e)
ok("не нашла папку «Спам»" in err and 1 in F["INBOX"], f"нет папки «Спам» — письмо не трогаем, так и говорим: {err!r}")
res = mm.manage("1", "trash")
ok(res["permanent"] and 1 not in F["INBOX"], "нет корзины — удалено совсем, и это видно (permanent)")

# ---------- переслать ----------
reset("special"); SENT.clear()
res = mm.manage("2", "forward", "andrey@example.org", "Посмотри, пожалуйста")
fw = email.message_from_bytes(SENT[-1]) if SENT else None
subj = str(email.header.make_header(email.header.decode_header(fw["Subject"]))) if fw else ""
parts = [p.get_content_type() for p in fw.walk()] if fw else []
body = next((p.get_payload(decode=True).decode() for p in fw.walk() if p.get_content_type() == "text/plain"), "") if fw else ""
ok(fw and fw["To"] == "andrey@example.org" and subj == "Fwd: Регистрация на сессию", f"переслано Андрею, тема «Fwd: …»: {subj!r}")
ok(body.startswith("Посмотри, пожалуйста") and "Пересланное сообщение" in body and "panov@tadviser.example" in body, "сверху — пара слов и «Пересланное сообщение»")
ok("message/rfc822" in parts and "application/pdf" in parts, f"оригинал целиком — вложением (с его вложениями): {parts}")
try:
    mm.manage("2", "forward", "не-адрес"); err = ""
except M.MailError as e:
    err = str(e)
ok("неверный адрес" in err, "неверный адрес — не отправляет")

# ---------- голосом: manage_email ----------
reset("special")
s_ = Settings(tmp / "s.json")
tb = T.Toolbox(s_, None); tb.hooks["mail"] = mm
ok(tb.policy("manage_email") == (True, True), "manage_email — только с вопросом «точно?»")
q = tb.describe("manage_email", {"action": "delete", "uid": "1"})
ok("Удалить письмо «Счёт за ноябрь» от Бухгалтерия" in q and "Корзину" in q, f"вопрос называет письмо: {q!r}")
out = T.TOOLS["manage_email"][3]({"action": "spam", "uid": "Бухгалтерия"}, {"mail": mm})
ok("Спам" in out and 1 in F["&BCEEPwQwBDw-"], f"«отправь в спам» голосом: {out!r}")
try:
    T.TOOLS["manage_email"][3]({"action": "forward", "uid": "2"}, {"mail": mm}); err = ""
except T.ToolError as e:
    err = str(e)
ok("кому переслать" in err, "переслать без адреса — спросит, кому")
SENT.clear()
out = T.TOOLS["manage_email"][3]({"action": "forward", "uid": "2", "to": "andrey@example.org"}, {"mail": mm})
ok("переслано: andrey@example.org" in out and SENT, f"«перешли Андрею»: {out!r}")
ok("manage_email" in T.NET_TOOLS, "при стоп-кране «ничего в интернет» — инструмента нет")
eng = (ROOT / "core/engine_commands.py").read_text(encoding="utf-8")
ok('if cmd == "mail_act":' in eng and '"mail_"' in eng.split("_KIDS_LOCKED")[1][:900], "студия: mail_act; в детском режиме — закрыто (mail_)")

# ---------- студия: рамка, картинки, ссылки, кнопки ----------
from playwright.sync_api import sync_playwright  # noqa: E402
reset("special")
READ = mm.read("2", html_view=True)
MAIL = [{"uid": "2", "from": READ["from"], "subject": READ["subject"], "date": READ["date"], "snippet": "Здравствуйте", "unread": True, "files": READ["files"]}]
CORE = r"""(() => { window.calls = []; window.DEWIAR_AUTO_ASK = true; const MAIL = __MAIL__, READ = __READ__;
  const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.call = async (c, a) => { calls.push([c, a]);
      if (c === "mail_inbox") return { on: true, items: MAIL };
      if (c === "mail_read") return READ;
      if (c === "mail_act") return a.action === "forward" ? { to: [a.to], forwarded: READ.subject } : { ok: true, folder: a.action === "junk" ? "Спам" : "Корзина", permanent: false };
      return null; };
    setTimeout(() => core.emit("hello", {}), 200); };
  ready(); })();""".replace("__MAIL__", json.dumps(MAIL, ensure_ascii=False)).replace("__READ__", json.dumps(READ, ensure_ascii=False))
errs, nets = [], []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1300, "height": 900}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route(re.compile(r"^https?://"), lambda r: (nets.append(r.request.url), r.abort()))
    pg.add_init_script("window._opened = []; window.pywebview = { api: new Proxy({}, { get: (t, k) => k === 'open_url' ? (u) => { _opened.push(u); return Promise.resolve(true); } : () => Promise.resolve(true) }) };")
    pg.add_init_script(CORE)
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1&skin=neusky"); pg.wait_for_timeout(1500)
    pg.evaluate("() => { try { localStorage.removeItem('dw_mail_view'); } catch (e) {} const w = document.querySelector('#wlc'); if (w) w.remove(); loadHome(); }"); pg.wait_for_timeout(700)
    pg.click("#hm-mail .hmm-row >> nth=0"); pg.wait_for_timeout(500)
    ok(["mail_read", {"uid": "2", "html": True}] in pg.evaluate("calls"), "открыли — письмо с HTML (mail_read html)")
    ok(pg.is_visible("#hmm-bar") and pg.locator("#hmm-body .hmm-text").count() == 1 and pg.locator("#hmm-body iframe").count() == 0,
       "есть текстовая часть — сначала «Текстом», переключатель виден")
    pg.click("#hmm-bar [data-v=html]"); pg.wait_for_timeout(400)
    fr = pg.locator("#hmm-body iframe.hmm-frame")
    ok(fr.count() == 1 and fr.get_attribute("sandbox") == "" and fr.get_attribute("referrerpolicy") == "no-referrer", "«Как в письме» — рамка sandbox=\"\" без referrer")
    sd = pg.evaluate("document.querySelector('.hmm-frame').srcdoc")
    ok("default-src 'none'; img-src data:;" in sd and "<script" not in sd, "в рамке: CSP default-src 'none', картинки — только встроенные")
    frame = pg.frame_locator(".hmm-frame")
    ok("Сергей" in frame.locator("body").inner_text(), "письмо видно в рамке")
    ok(not [u for u in nets if "track.example" in u], f"картинка-счётчик не загружена до нажатия: {nets}")
    ok(pg.is_visible("#hmm-pics") and "1" in pg.inner_text("#hmm-pics"), "кнопка «Показать картинки · 1»")
    pg.click("#hmm-pics"); pg.wait_for_timeout(400)
    sd = pg.evaluate("document.querySelector('.hmm-frame').srcdoc")
    ok("img-src data: https:;" in sd and "script-src" not in sd and pg.is_hidden("#hmm-pics"), "нажали — внешние картинки можно, скрипты — по-прежнему нет")
    ok(pg.evaluate("localStorage.getItem('dw_mail_view')") == "html", "выбор вида запомнен")
    # второй рубеж: даже если бы скрипт прошёл чистку — рамка его не выполнит
    pg.evaluate("() => { window._t0 = document.title; HMM.r = Object.assign({}, HMM.r, { html: '<p id=x>ок</p><script>parent.document.title = \"ВЗЛОМ\"; document.getElementById(\"x\").textContent = \"ran\";</script>' }); hmmShow(); }")
    pg.wait_for_timeout(400)
    ok(pg.evaluate("document.title === _t0") and pg.frame_locator(".hmm-frame").locator("#x").inner_text() == "ок", "скрипт в рамке не выполняется (sandbox)")
    pg.evaluate("() => { HMM.r = READ_BACK; hmmShow(); }".replace("READ_BACK", json.dumps(READ, ensure_ascii=False))); pg.wait_for_timeout(200)
    pg.click(".hmm-links summary"); pg.click(".hmm-links button >> nth=0"); pg.wait_for_timeout(200)
    ok(pg.evaluate("_opened") == ["https://tadviser.example/reg?u=1"] and "tadviser.example" in pg.inner_text(".hmm-links"),
       "ссылка из списка — в браузере, видно настоящий адрес")
    # переслать
    pg.click("#hmm-fwdb"); pg.wait_for_timeout(150)
    ok(pg.is_visible("#hmm-fwd") and pg.get_attribute("#hmm-fwdb", "aria-expanded") == "true", "«Переслать» — поля «Кому» и «Пара слов»")
    pg.fill("#hmm-fto", "не адрес"); pg.click("#hmm-fgo"); pg.wait_for_timeout(150)
    ok("Проверьте адрес" in pg.inner_text("#hmm-st") and not [c for c in pg.evaluate("calls") if c[0] == "mail_act"], "неверный адрес — не отправляет")
    pg.fill("#hmm-fto", "andrey@example.org"); pg.fill("#hmm-fnote", "Глянь"); pg.click("#hmm-fgo"); pg.wait_for_timeout(300)
    ok(["mail_act", {"uid": "2", "action": "forward", "to": "andrey@example.org", "note": "Глянь"}] in pg.evaluate("calls") and "Переслала" in pg.inner_text("#hmm-st"),
       "переслано — итог виден в окне")
    # в спам
    pg.click("#hmm-spam"); pg.wait_for_timeout(400)
    ok(["mail_act", {"uid": "2", "action": "junk", "to": "", "note": ""}] in pg.evaluate("calls") and not pg.evaluate("document.querySelector('#hmm-dlg').open")
       and pg.locator("#hm-mail .hmm-row").count() == 0, "«В спам» — окно закрылось, письмо ушло из списка")
    ok("Спам" in pg.inner_text("#toast"), "и сказано, куда")
    pg.screenshot(path=str(tmp / "mail562.png"))
    b.close()
ok(not errs, f"студия без ошибок: {errs[:2]}")
hm = (ROOT / "ui/studio/home.js").read_text(encoding="utf-8")
ok('sandbox=""' in hm and "allow-scripts" not in hm and "allow-same-origin" not in hm, "рамка письма — без скриптов и без своего источника")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
