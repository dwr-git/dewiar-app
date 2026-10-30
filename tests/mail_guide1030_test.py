"""Почта: понятное подключение (30.10, владелец: «Хотел почту привязать, пока не понимаю как. Не понятно написано. У меня
двухэтапная проверка включена, но что и куда откуда ввести не ясно»; на снимке — зелёное «Подключена» при двух ошибках
и «smtp.gmail.com:465 — Connection unexpectedly closed»).
Ядро: пароль приложения Google с пробелами («abcd efgh ijkl mnop») сохраняется без пробелов; порт 465 закрыт — сам
пробует 587 со STARTTLS и запоминает; итог проверки хранится (check), чтобы студия не писала «Подключена» без входа.
Студия: шаги по своей почте с кнопкой «Открыть «Пароли приложений» Google»; поля подписаны; пароль не принят — одна понятная
строка; вход прошёл — шаги свёрнуты в «Как получить пароль приложения»; «вход не прошёл» — красным, не «Подключена»."""
import os, re, smtplib, sys, tempfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import mail  # noqa: E402
d = Path(tempfile.mkdtemp())
M = mail.Mail(d / "mail.json")
pub = M.save({"address": "ivan@gmail.com", "password": "abcd efgh ijkl mnop"}, 0)
ok(M.boxes[0].data["password"] == "abcdefghijklmnop" and pub["provider"] == "gmail", "пароль приложения Google с пробелами — сохраняется без пробелов")
M.save({"address": "ivan@gmail.com", "password": "мой пароль с пробелами"}, 0)
ok(M.boxes[0].data["password"] == "мой пароль с пробелами", "обычный пароль с пробелами не трогаем")


class Closed(smtplib.SMTP_SSL):
    def __init__(self, *a, **k):
        raise smtplib.SMTPServerDisconnected("Connection unexpectedly closed")


class Plain:
    seen = []
    def __init__(self, host, port, timeout=0): Plain.seen.append((host, port))
    def ehlo(self): pass
    def starttls(self, context=None): pass
    def login(self, u, p):
        if p != "abcdefghijklmnop":
            raise smtplib.SMTPAuthenticationError(535, b"5.7.8 Username and Password not accepted")
    def quit(self): pass


class IMAPBad:
    def __init__(self, *a, **k): pass
    def login(self, u, p): raise mail.imaplib.IMAP4.error("AUTHENTICATIONFAILED")


mail.smtplib.SMTP_SSL, mail.smtplib.SMTP = Closed, Plain
real_imap = mail.imaplib.IMAP4_SSL
mail.imaplib.IMAP4_SSL = IMAPBad
M.save({"address": "ivan@gmail.com", "password": "abcd efgh ijkl mnop"}, 0)
tr = M.test(0)
b = M.boxes[0].data
ok(tr["smtp"] == "ok" and ("smtp.gmail.com", 587) in Plain.seen and b["smtp_port"] == 587 and b["smtp_security"] == "starttls",
   f"465 закрыт — отправка сама переходит на 587/STARTTLS и запоминает: {tr['smtp']!r}")
ok(tr["check"]["ok"] is False and tr["check"]["auth"] is True and M.public()["boxes"][0]["check"]["ok"] is False,
   "чтение не вошло — итог проверки «не прошёл» помнится (для студии)")
M2 = mail.Mail(d / "mail.json")
ok(M2.boxes[0].data["smtp_port"] == 587 and M2.boxes[0].data.get("check", {}).get("ok") is False, "после перезапуска — тот же порт и тот же итог")
M.save({"address": "ivan@gmail.com", "password": "qwer tyui opas dfgh"}, 0)
ok("check" not in M.boxes[0].data, "новый пароль — прежний итог проверки сброшен")
mail.smtplib.SMTP_SSL = Closed
M.boxes[0].data.update(smtp_port=465, smtp_security="ssl")
tr = M.test(0)
ok("не приняла логин" in tr["smtp"], f"на 587 пароль не принят — честно «не приняла логин», а не «не удалось подключиться»: {tr['smtp'][:60]!r}")


class Dead:
    def __init__(self, *a, **k): raise OSError("Connection refused")


mail.smtplib.SMTP = Dead
tr = M.test(0)
ok("антивирус" in tr["smtp"] and "465" in tr["smtp"], f"оба порта закрыты — подсказка про антивирус и сеть: {tr['smtp'][:90]!r}")
mail.imaplib.IMAP4_SSL = real_imap

# ---------- студия ----------
from playwright.sync_api import sync_playwright  # noqa: E402
FAKE = "window.pywebview = { api: new Proxy({}, { get: (_, k) => k === 'open_url' ? ((u) => { (window.opened = window.opened || []).push(u); return Promise.resolve(true); }) : () => Promise.resolve(true) }) };"
CORE = r"""
(() => { window.calls = []; window.TEST = { smtp: "почта не приняла логин или пароль — нужен «пароль приложения»", imap: "почта не приняла логин или пароль (IMAP) — нужен «пароль приложения»" };
  window.MB = [];
  const pub = () => Object.assign({}, MB[0] || { has_password: false, configured: false }, { boxes: MB.map((b, n) => Object.assign({ n }, b)) });
  const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.call = async (c, a) => { calls.push([c, a]);
      if (c === "mail_guess") return a.address.endsWith("gmail.com") ? { smtp_host: "smtp.gmail.com", smtp_port: 465, smtp_security: "ssl", imap_host: "imap.gmail.com", imap_port: 993, help: "https://myaccount.google.com/apppasswords", provider: "gmail" }
        : { smtp_host: "smtp.x.ru", smtp_port: 465, smtp_security: "ssl", imap_host: "imap.x.ru", imap_port: 993, help: "", provider: "" };
      if (c === "mail_save") { MB[a.box] = Object.assign(MB[a.box] || {}, { address: a.patch.address, has_password: true, configured: true, provider: a.patch.address.endsWith("gmail.com") ? "gmail" : "", smtp_host: "smtp.gmail.com", imap_host: "imap.gmail.com" }); delete MB[a.box].check; return pub(); }
      if (c === "mail_test") { const okk = TEST.smtp === "ok" && TEST.imap === "ok"; const r = Object.assign({}, TEST, { check: { ok: okk, auth: !okk } }); MB[a.box].check = r.check; return r; }
      return {}; };
    setTimeout(() => mlFill(pub()), 300); };
  ready(); })();
"""
SHOT = os.environ.get("DEWIAR_SHOTS")
with sync_playwright() as p:
    br = p.chromium.launch(); errs = []
    pg = br.new_page(viewport={"width": 1280, "height": 1000}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route(re.compile(r"^https?://"), lambda r: r.abort())
    pg.add_init_script(FAKE); pg.add_init_script(CORE)
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(1200)
    pg.evaluate("document.querySelector('nav button[data-p=\"connect\"]').click()"); pg.wait_for_timeout(300)
    ok("Впишите адрес почты" in pg.inner_text("#ml-guide") and pg.inner_text("#mail-box .ml-f span").startswith("Адрес почты"), "пусто — «впишите адрес», поля подписаны")
    pg.fill("#ml-addr", "ivan@gmail.com"); pg.dispatch_event("#ml-addr", "change"); pg.wait_for_timeout(300)
    g = pg.inner_text("#ml-guide")
    ok(pg.locator("#ml-guide .ml-steps li").count() == 4 and "Dewiar" in g and "16 букв" in g and "Безопасность" in g and pg.inner_text("#ml-pass-l") == "Пароль приложения — 16 букв от Google",
       "Gmail — четыре шага: где страница, что вписать, что скопировать, куда вставить")
    pg.click("#ml-guide .ml-go"); pg.wait_for_timeout(150)
    ok(pg.evaluate("window.opened") == ["https://myaccount.google.com/apppasswords"], "кнопка открывает «Пароли приложений» Google в браузере")
    if SHOT: pg.locator("#mail-box").screenshot(path=str(Path(SHOT) / "mail-guide.png"))
    pg.fill("#ml-pass", "Мой-обычный-пароль"); pg.click("#ml-save"); pg.wait_for_timeout(500)
    res, st = pg.inner_text("#ml-res"), pg.inner_text("#ml-state")
    ok(res.startswith("Google не принял пароль.") and "16 букв" in res and "Чтение:" not in res, f"пароль не принят — одна понятная строка: {res!r}")
    ok("вход не прошёл" in st and "Подключена" not in st and "bad" in pg.get_attribute("#ml-state", "class"), f"не «Подключена» зелёным, а «вход не прошёл»: {st!r}")
    ok(pg.locator("#ml-guide .ml-steps li").count() == 4, "шаги остаются на виду")
    if SHOT: pg.locator("#mail-box").screenshot(path=str(Path(SHOT) / "mail-guide-bad.png"))
    pg.evaluate("TEST.smtp = 'ok'; TEST.imap = 'ok'"); pg.fill("#ml-pass", "abcd efgh ijkl mnop"); pg.click("#ml-save"); pg.wait_for_timeout(500)
    ok("Готово" in pg.inner_text("#ml-res") and pg.inner_text("#ml-state") == "Подключена: ivan@gmail.com" and pg.locator("#ml-guide .ml-steps").count() == 0
       and pg.inner_text("#ml-more") == "Как получить пароль приложения", "вход прошёл — «Подключена», шаги свёрнуты в ссылку")
    pg.click("#ml-more"); pg.wait_for_timeout(100)
    ok(pg.locator("#ml-guide .ml-steps li").count() == 4, "«Как получить пароль приложения» — шаги снова видны")
    pg.evaluate("MB.length = 0; mlBox = 0; document.querySelector('#ml-addr').value = ''; mlFill({ has_password: false, configured: false, boxes: [] })")
    pg.fill("#ml-addr", "ivan@x.ru"); pg.dispatch_event("#ml-addr", "change"); pg.wait_for_timeout(300)
    ok(pg.locator("#ml-guide .ml-steps").count() == 0 and "пароль приложения" in pg.inner_text("#ml-guide"), "незнакомая почта — общая подсказка без шагов")
    pg.set_viewport_size({"width": 760, "height": 900}); pg.wait_for_timeout(200)
    ok(pg.evaluate("document.documentElement.scrollWidth <= innerWidth"), "узкое окно — без прокрутки вбок")
    br.close()
ok(not errs, f"без ошибок на странице: {errs[:3]}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
