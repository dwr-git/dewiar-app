"""Почта на Windows (пакет 27.10, жалоба пользователя: «не получается присоединить почту, и вверху слева выскакивает
окно»). 1) Яндекс не принял вход — ошибка должна сказать, что именно сделать (пароль приложения + «Почтовые программы»
→ IMAP), а не только «нужен пароль приложения». 2) Окно «сайт хочет просматривать буфер обмена» — WebView2 спрашивал,
потому что копирование в сейфе через Windows молча падало (64-битные дескрипторы без argtypes), и страница сама читала
буфер через 30 с. Теперь argtypes заданы, а в окне программы страница буфер не читает."""
import imaplib, os, re, smtplib, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
import mail as M  # noqa: E402
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


class BadSMTP:
    def __init__(self, *a, **k): pass
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def ehlo(self, *a): pass
    def starttls(self, *a, **k): pass
    def login(self, *a): raise smtplib.SMTPAuthenticationError(535, b"auth failed")
    def quit(self): pass
    def close(self): pass


class BadIMAP:
    error = imaplib.IMAP4.error

    def __init__(self, *a, **k): pass
    def login(self, *a): raise imaplib.IMAP4.error("AUTHENTICATIONFAILED")
    def logout(self): pass
    def shutdown(self): pass


smtplib.SMTP_SSL = smtplib.SMTP = BadSMTP
imaplib.IMAP4_SSL = BadIMAP


def errs(addr):
    b = M.Box({**M.guess(addr), "address": addr, "password": "x" * 16})
    out = []
    for fn in (lambda: b.send(addr, "т", "т"), lambda: b.inbox()):
        try:
            fn(); out.append("")
        except M.MailError as e:
            out.append(str(e))
        except Exception as e:  # noqa: BLE001
            out.append(f"{type(e).__name__}: {e}")
    return out


ya = errs("user@yandex.ru")
ok(all("пароль приложения" in e for e in ya), f"Яндекс: ошибка входа — про пароль приложения: {ya}")
ok(all("Почтовые программы" in e and "IMAP" in e and "id.yandex.ru" in e for e in ya), "Яндекс: подсказка — где создать пароль и где включить IMAP")
mr = errs("user@mail.ru")
ok(all("Пароли для внешних приложений" in e for e in mr), f"Mail.ru: своя подсказка: {mr[0][-90:]!r}")
gm = errs("user@gmail.com")
ok(all("двухэтапную" in e for e in gm), "Gmail: своя подсказка")
other = errs("user@example.org")
ok(all(e.endswith("«пароль приложения»") or e.endswith("не обычный пароль") for e in other), f"незнакомая почта — без чужих советов: {other}")

app = (ROOT / "ui/app.py").read_text()
for fn in ("_win_clip_set", "_win_clip_clear_if"):
    body = app.split(f"def {fn}", 1)[1].split("\ndef ", 1)[0]
    ok("GlobalUnlock.argtypes" in body and "OpenClipboard.argtypes" in body, f"{fn}: дескрипторы Windows с argtypes (64 бита)")
vj = (ROOT / "ui/studio/vault.js").read_text()
cp = vj.split("async function vlCopy", 1)[1].split("\nfunction ", 1)[0].split("\nasync function ", 1)[0]
ok(re.search(r"if \(a\)[^\n]*writeText\(\"\"\)", cp) is not None and "readText" in cp.split("else", 1)[-1],
   "сейф: в окне программы буфер не читается (без вопроса WebView2), в браузере — как раньше")
print("ИТОГ:", "все проверки пройдены" if not fails else f"не пройдено {len(fails)}")
sys.exit(1 if fails else 0)
