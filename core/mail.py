"""Почта: отправить письмо (результат задачи, заметку, файл) и прочитать входящие — своим ящиком.

Любой ящик по SMTP/IMAP: Яндекс, Mail.ru, Gmail, Outlook, Rambler, iCloud или свой сервер (серверы подставляются
по домену адреса — guess()). Для больших почт нужен «пароль приложения» (обычный пароль они сторонним программам
не дают) — студия подсказывает, где его взять. Настройки — в ~/.config/dewiar/mail.json (0600); пароль в студию
не отдаётся (public()). Чтение не помечает письма прочитанными (папка открывается только для чтения, BODY.PEEK).
"""

import email
import email.utils
import html
import imaplib
import json
import logging
import mimetypes
import os
import re
import smtplib
import time
import ssl
import threading
from email.header import decode_header, make_header
from email.message import EmailMessage
from pathlib import Path

from settings import CONFIG_DIR

log = logging.getLogger("dewiar.mail")
PATH = CONFIG_DIR / "mail.json"

# почтовая служба → (smtp, порт, защита: ssl — TLS сразу, starttls — по команде; imap, порт; где взять пароль приложения)
# DOMAINS ниже: домен адреса → служба.
PRESETS = {
    "yandex": ("smtp.yandex.ru", 465, "ssl", "imap.yandex.ru", 993, "https://id.yandex.ru/security/app-passwords"),
    "mailru": ("smtp.mail.ru", 465, "ssl", "imap.mail.ru", 993, "https://account.mail.ru/user/2-step-auth/passwords/"),
    "gmail": ("smtp.gmail.com", 465, "ssl", "imap.gmail.com", 993, "https://myaccount.google.com/apppasswords"),
    "outlook": ("smtp-mail.outlook.com", 587, "starttls", "outlook.office365.com", 993, "https://account.live.com/proofs/AppPassword"),
    "rambler": ("smtp.rambler.ru", 465, "ssl", "imap.rambler.ru", 993, ""),
    "icloud": ("smtp.mail.me.com", 587, "starttls", "imap.mail.me.com", 993, "https://account.apple.com"),
    "yahoo": ("smtp.mail.yahoo.com", 465, "ssl", "imap.mail.yahoo.com", 993, ""),
}
DOMAINS = {"yandex.ru": "yandex", "ya.ru": "yandex", "yandex.com": "yandex", "yandex.by": "yandex", "yandex.kz": "yandex",
           "narod.ru": "yandex", "mail.ru": "mailru", "bk.ru": "mailru", "inbox.ru": "mailru", "list.ru": "mailru",
           "internet.ru": "mailru", "gmail.com": "gmail", "googlemail.com": "gmail", "outlook.com": "outlook",
           "hotmail.com": "outlook", "live.com": "outlook", "rambler.ru": "rambler", "lenta.ru": "rambler",
           "icloud.com": "icloud", "me.com": "icloud", "yahoo.com": "yahoo"}


class MailError(Exception):
    pass


def guess(address):
    """Адрес → настройки серверов (по домену; неизвестный домен — smtp.<домен>:465 и imap.<домен>:993)."""
    dom = (address or "").rsplit("@", 1)[-1].lower().strip()
    key = DOMAINS.get(dom)
    if key:
        s, sp, sec, i, ip, help_url = PRESETS[key]
        return {"smtp_host": s, "smtp_port": sp, "smtp_security": sec, "imap_host": i, "imap_port": ip,
                "help": help_url, "provider": key}
    return {"smtp_host": f"smtp.{dom}" if dom else "", "smtp_port": 465, "smtp_security": "ssl",
            "imap_host": f"imap.{dom}" if dom else "", "imap_port": 993, "help": "", "provider": ""}


def _dec(v):
    """Заголовок письма в кодировке MIME (=?utf-8?b?…?=) → обычная строка; не разбирается — возвращаем как есть."""
    try:
        return str(make_header(decode_header(v or "")))
    except Exception:  # noqa: BLE001
        return v or ""


def _text_of(msg, limit=20000):
    """Письмо -> (текст до limit символов, имена вложений). Текст — из text/plain, а если его нет — html без разметки.
    Часть с именем файла считается вложением, даже если это текст."""
    plain, htm, files = [], [], []
    for part in msg.walk() if msg.is_multipart() else [msg]:
        if part.is_multipart():
            continue
        fn = part.get_filename()
        if fn:
            files.append(_dec(fn))
            continue
        ctype = part.get_content_type()
        try:
            payload = part.get_payload(decode=True) or b""
            txt = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            continue
        (plain if ctype == "text/plain" else htm if ctype == "text/html" else []).append(txt)
    body = "\n".join(plain).strip()
    if not body and htm:
        h = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", "\n".join(htm))
        h = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>|</li>", "\n", h)
        body = html.unescape(re.sub(r"<[^>]+>", " ", h))
        body = re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n\n", body)).strip()
    return body[:limit], files


class Box:
    """Один ящик. Соединение открывается на каждую операцию и сразу закрывается — держать его незачем.
    data — его настройки; store() — записать все ящики (Mail._store)."""

    def __init__(self, data=None, workspace=None, store=None):
        self.ws, self._store = workspace, store or (lambda: None)
        self._lock = threading.Lock()
        self.data = dict(data or {})

    # ---------- настройки ----------

    def configured(self):
        d = self.data
        return bool(d.get("address") and d.get("password") and d.get("smtp_host"))

    def public(self):
        d = dict(self.data)
        d["has_password"] = bool(d.pop("password", ""))
        d["configured"] = self.configured()
        if d.get("address") and not d.get("help"):
            d["help"] = guess(d["address"]).get("help", "")
        if d.get("address") and not d.get("provider"):
            d["provider"] = guess(d["address"]).get("provider", "")
        return d

    def save(self, patch):
        """Сохранить настройки из студии -> public(). Берутся только известные поля; файл пишется атомарно, права 0600."""
        with self._lock:
            patch = dict(patch or {})
            if not patch.get("password"):
                patch.pop("password", None)                     # пустое поле — пароль не меняем
            elif (guess(patch.get("address") or self.data.get("address") or "").get("provider")
                  and re.fullmatch(r"[A-Za-z]{4}( [A-Za-z]{4}){3}", patch["password"].strip())):
                # пароль приложения Google показывает «abcd efgh ijkl mnop» — копируют с пробелами (30.10, владелец)
                patch["password"] = patch["password"].replace(" ", "")
            addr = (patch.get("address") or self.data.get("address") or "").strip()
            if addr and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", addr):
                raise MailError("это не похоже на адрес почты")
            if addr != self.data.get("address") and not patch.get("smtp_host"):
                patch = {**guess(addr), **patch}                 # новый адрес — подставляем серверы сами
            self.data.update({k: v for k, v in patch.items() if k in (
                "address", "name", "password", "login", "smtp_host", "smtp_port", "smtp_security", "imap_host",
                "imap_port", "help", "provider")})
            self.data["address"] = addr
            if patch.get("password") or "smtp_host" in patch:
                self.data.pop("check", None)                     # новый пароль — прежняя проверка не в счёт
        self._store()
        return self.public()

    # ---------- соединения ----------

    def _auth_hint(self):
        """Что ещё проверить у этой почты (пакет 27.10: Яндекс не принимал вход, хотя пароль «сохранён»)."""
        p = self.data.get("provider") or guess(self.data.get("address", "")).get("provider", "")
        return {"yandex": ". В Яндексе: id.yandex.ru → «Безопасность» → «Пароли приложений» → «Почта» — новый пароль (16 букв); "
                          "и в настройках Яндекс Почты → «Почтовые программы» включите «С сервера imap.yandex.ru по протоколу IMAP» "
                          "и «Пароли приложений и OAuth-токены»",
                "mailru": ". В Mail.ru: «Безопасность» → «Пароли для внешних приложений» → новый пароль с доступом «Полный (IMAP, SMTP)»",
                "gmail": ". В Google: включите двухэтапную проверку, затем «Пароли приложений» — 16 букв без пробелов",
                "rambler": ". В Рамблере: настройки почты → «Почтовые программы» → включите доступ «С помощью почтовых клиентов»",
                }.get(p, "")

    def _login(self):
        # Логин обычно совпадает с адресом; отдельное поле — для своих серверов, где это не так.
        return self.data.get("login") or self.data.get("address")

    def _smtp(self):
        d = self.data
        host, port, sec = d.get("smtp_host"), int(d.get("smtp_port") or 465), d.get("smtp_security") or "ssl"
        try:
            if sec == "ssl":
                s = smtplib.SMTP_SSL(host, port, timeout=25, context=ssl.create_default_context())
            else:
                s = smtplib.SMTP(host, port, timeout=25)
                s.ehlo()
                if sec == "starttls":
                    s.starttls(context=ssl.create_default_context())
                    s.ehlo()
            s.login(self._login(), d.get("password", ""))
            return s
        except smtplib.SMTPAuthenticationError as e:
            raise MailError("почта не приняла логин или пароль — нужен «пароль приложения», не обычный пароль" + self._auth_hint()) from e
        except (OSError, smtplib.SMTPException) as e:
            # 30.10 (владелец, Gmail): «smtp.gmail.com:465 — Connection unexpectedly closed» — порт 465 рвёт антивирус
            # или провайдер. Тот же сервер умеет 587 со STARTTLS: пробуем его и, если вошли, запоминаем.
            if sec == "ssl" and port == 465:
                try:
                    s = smtplib.SMTP(host, 587, timeout=25)
                    s.ehlo(); s.starttls(context=ssl.create_default_context()); s.ehlo()
                    s.login(self._login(), d.get("password", ""))
                    log.info("mail: %s:465 закрыт (%s) — работает 587/STARTTLS, запоминаю", host, e)
                    d["smtp_port"], d["smtp_security"] = 587, "starttls"
                    self._store()
                    return s
                except smtplib.SMTPAuthenticationError as e2:
                    raise MailError("почта не приняла логин или пароль — нужен «пароль приложения», не обычный пароль" + self._auth_hint()) from e2
                except (OSError, smtplib.SMTPException):
                    pass
            raise MailError(f"не удалось подключиться к {host}:{port} — {e}. Похоже, порт закрыт антивирусом или сетью: "
                            "в антивирусе отключите «проверку почты» или добавьте Dewiar в исключения") from e

    def _imap(self):
        """Вход в IMAP. Порт 993 — TLS сразу; другой порт — STARTTLS, и без него не входим: пароль открытым текстом
        по сети не отправляем (исключение — свой сервер на этой же машине)."""
        d = self.data
        host, port = d.get("imap_host"), int(d.get("imap_port") or 993)
        try:
            if port == 993:
                m = imaplib.IMAP4_SSL(host, port, ssl_context=ssl.create_default_context(), timeout=25)
            else:
                m = imaplib.IMAP4(host, port, timeout=25)
                if host not in ("127.0.0.1", "localhost", "::1"):
                    try:
                        m.starttls(ssl.create_default_context())
                    except (imaplib.IMAP4.error, OSError) as e:
                        raise MailError(f"{host}:{port} не умеет STARTTLS — пароль открытым текстом не отправляю; укажите порт 993") from e
            m.login(self._login(), d.get("password", ""))
            return m
        except imaplib.IMAP4.error as e:
            raise MailError("почта не приняла логин или пароль (IMAP) — нужен «пароль приложения»" + self._auth_hint()) from e
        except OSError as e:
            raise MailError(f"не удалось подключиться к {host}:{port} — {e}") from e

    def test(self):
        """Проверить вход в SMTP и IMAP -> {"smtp": "ok" или текст ошибки, "imap": …} (IMAP — если указан)."""
        if not self.configured():
            raise MailError("сначала укажите адрес и пароль приложения")
        out = {"smtp": "", "imap": ""}
        try:
            self._smtp().quit()
            out["smtp"] = "ok"
        except MailError as e:
            out["smtp"] = str(e)
        if self.data.get("imap_host"):
            try:
                m = self._imap()
                m.logout()
                out["imap"] = "ok"
            except MailError as e:
                out["imap"] = str(e)
        ok = out["smtp"] == "ok" and out["imap"] in ("ok", "")
        # итог проверки помнится: студия не пишет «Подключена», если вход не прошёл (30.10, владелец — было зелёным при двух ошибках)
        import time
        self.data["check"] = {"ok": ok, "at": int(time.time()), "auth": not ok and any("не приняла логин" in v for v in out.values())}
        self._store()
        out["check"] = self.data["check"]
        return out

    # ---------- письма ----------

    def send(self, to="", subject="", body="", attachments=(), headers=None):
        """Отправить письмо -> {to, subject, attachments}. Без получателя — себе на свой адрес. headers — свои заголовки
        (рассылка: List-Unsubscribe).
        Вложения — пути в папке ассистента: ws.safe() не даёт выйти за её пределы. Предел 20 МБ на файл — столько
        принимают почтовые службы с запасом на кодирование вложения."""
        if not self.configured():
            raise MailError("почта не подключена (студия → «Подключение» → «Почта»)")
        to = [x.strip() for x in re.split(r"[,;\s]+", to or "") if x.strip()] or [self.data["address"]]
        for x in to:
            if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", x):
                raise MailError(f"неверный адрес: {x}")
        msg = EmailMessage()
        me = self.data["address"]
        msg["From"] = email.utils.formataddr((self.data.get("name") or "Dewiar", me))
        msg["To"] = ", ".join(to)
        msg["Subject"] = (subject or "Сообщение от Dewiar").strip()[:200]
        msg["Date"] = email.utils.formatdate(localtime=True)
        msg["Message-ID"] = email.utils.make_msgid(domain=me.split("@")[-1])
        for k, v in (headers or {}).items():
            msg[k] = v
        msg.set_content((body or "").strip() + "\n")
        names = []
        for rel in attachments or []:
            p = self.ws.safe(str(rel)) if self.ws else Path(rel)
            if not p.is_file():
                raise MailError(f"нет файла {rel} в папке ассистента")
            if p.stat().st_size > 20 * 1024 * 1024:
                raise MailError(f"файл {p.name} больше 20 МБ — почта его не примет")
            ctype = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
            main, sub = ctype.split("/", 1)
            msg.add_attachment(p.read_bytes(), maintype=main, subtype=sub, filename=p.name)
            names.append(p.name)
        s = self._smtp()
        try:
            s.send_message(msg)
        except smtplib.SMTPException as e:
            raise MailError(f"письмо не отправилось: {e}") from e
        finally:
            try:
                s.quit()
            except Exception:  # noqa: BLE001
                pass
        log.info("✉️  Письмо «%s» → %s%s", msg["Subject"], ", ".join(to), f" (вложения: {', '.join(names)})" if names else "")
        return {"to": to, "subject": msg["Subject"], "attachments": names}

    def inbox(self, limit=10, unread=False, query="", folder="INBOX"):
        """Последние письма: [{uid, from, subject, date, snippet, files, unread}] — новые сверху.
        Поиск query — по отправителю, теме и тексту, на нашей стороне, среди limit×4 последних писем."""
        m = self._imap()
        try:
            typ, _ = m.select(folder, readonly=True)
            if typ != "OK":
                raise MailError(f"нет папки {folder}")
            crit = ["UNSEEN"] if unread else ["ALL"]
            typ, data = m.uid("search", None, *crit)
            uids = (data[0] or b"").split()[::-1]
            out, q = [], (query or "").lower().strip()
            for uid in uids[: max(limit * (4 if q else 1), limit)]:
                typ, d = m.uid("fetch", uid, "(FLAGS BODY.PEEK[])")
                raw = next((x[1] for x in d if isinstance(x, tuple)), b"")
                flags = " ".join(x.decode(errors="ignore") if isinstance(x, bytes) else "" for x in d if not isinstance(x, tuple))
                flags += " ".join(x[0].decode(errors="ignore") for x in d if isinstance(x, tuple))
                msg = email.message_from_bytes(raw)
                body, files = _text_of(msg, 4000)
                item = {"uid": uid.decode(), "from": _dec(msg.get("From")), "subject": _dec(msg.get("Subject")) or "(без темы)",
                        "date": msg.get("Date", ""), "snippet": re.sub(r"\s+", " ", body)[:220], "files": files,
                        "unread": "\\Seen" not in flags}
                if q and q not in (item["from"] + " " + item["subject"] + " " + body).lower():
                    continue
                out.append(item)
                if len(out) >= limit:
                    break
            return out
        finally:
            try:
                m.logout()
            except Exception:  # noqa: BLE001
                pass

    def read(self, uid, folder="INBOX", mark=False):
        """Письмо целиком по uid из inbox() -> {uid, from, to, subject, date, text, files}.
        mark — человек его прочитал (открыл в студии или попросил Лиру прочитать): отметить «прочитано» и на почте
        (30.10, владелец: «прочитал через Лиру — а оно всё равно непрочитанное»). Меняем только флаг \\Seen этого
        письма; просмотр списка (inbox) и чтение без mark ничего на почте не трогают."""
        m = self._imap()
        try:
            try:
                m.select(folder, readonly=not mark)
            except imaplib.IMAP4.readonly:                     # папку не дают открыть на запись — покажем без отметки
                m.select(folder, readonly=True)
                mark = False
            typ, d = m.uid("fetch", str(uid).encode(), "(BODY.PEEK[])")
            raw = next((x[1] for x in d if isinstance(x, tuple)), b"")
            if not raw:
                raise MailError("такого письма нет")
            if mark:
                try:
                    m.uid("store", str(uid).encode(), "+FLAGS", "(\\Seen)")
                except (imaplib.IMAP4.error, OSError) as e:      # почта не дала поставить флаг — письмо всё равно покажем
                    log.info("mail: отметить прочитанным не вышло: %s", e)
            msg = email.message_from_bytes(raw)
            body, files = _text_of(msg)
            return {"uid": str(uid), "from": _dec(msg.get("From")), "to": _dec(msg.get("To")), "subject": _dec(msg.get("Subject")),
                    "date": msg.get("Date", ""), "text": body, "files": files}
        finally:
            try:
                m.logout()
            except Exception:  # noqa: BLE001
                pass


class Mail:
    """Почта: несколько ящиков (27.10, пакет: «как настроить на несколько ящиков? а то только один»). Первый — главный:
    с него письма уходят, если не сказано иначе. mail.json — {"boxes": [{…}, …]}; старый файл с одним ящиком
    (просто его настройки) читается как список из одного. API прежний: без box — главный ящик; inbox() без box —
    все ящики сразу (у писем не первого ящика uid «N:uid» и поле box — адрес)."""

    def __init__(self, path=PATH, workspace=None):
        self.path, self.ws = path, workspace
        self._lock = threading.Lock()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raw = {}
        lst = raw.get("boxes") if isinstance(raw, dict) and isinstance(raw.get("boxes"), list) else ([raw] if raw else [])
        self.boxes = [Box(d, workspace, self._store) for d in lst if isinstance(d, dict) and d]
        self.at = int(raw.get("at") or 0) if isinstance(raw, dict) and isinstance(raw.get("boxes"), list) else 0
        self.on_change = None    # почту поменяли здесь — разослать своим устройствам конвертом (engine: own_share)

    @property
    def data(self):                                  # прежнее поле: настройки главного ящика
        return self.boxes[0].data if self.boxes else {}

    def _store(self, at=None, quiet=False):
        """Записать mail.json. at — когда настройки поменялись (мс; своё изменение — сейчас), quiet — пришло с другого
        устройства: обратно не рассылаем."""
        with self._lock:
            self.at = int(at if at is not None else time.time() * 1000)
            live = [b.data for b in self.boxes if b.data.get("address")]
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            # без ящиков файл остаётся с отметкой времени: «почту отключили» тоже доходит до других устройств
            tmp.write_text(json.dumps({"boxes": live, "at": self.at}, ensure_ascii=False, indent=2), encoding="utf-8")
            try:
                os.chmod(tmp, 0o600)
            except OSError:
                pass
            tmp.replace(self.path)
        if not quiet and callable(self.on_change):
            try:
                self.on_change()
            except Exception:  # noqa: BLE001
                pass

    # ---------- между своими устройствами (30.10, владелец: «на рабочем компьютере добавил почту — дома её не вижу») ----------
    # Ящики с паролями приложений уходят только конвертом своим устройствам (сквозное шифрование «Близких», как умный
    # дом) — сайт их не видит. Новее — заменяет: подключили, поменяли пароль, отключили — то же на всех компьютерах.
    def share(self):
        """-> {boxes, at} или None (почту здесь ни разу не настраивали)."""
        if not self.at and not self.boxes:
            return None
        return {"boxes": [dict(b.data) for b in self.boxes if b.data.get("address")], "at": int(self.at or 1)}

    def adopt(self, boxes, at):
        """Почта с другого своего устройства. Новее здешней — берём. -> True, если что-то поменялось."""
        try:
            at = int(at or 0)
        except (TypeError, ValueError):
            return False
        if at <= int(self.at or 0) or not isinstance(boxes, list):
            return False
        keep = ("address", "name", "password", "login", "smtp_host", "smtp_port", "smtp_security", "imap_host", "imap_port", "help", "provider")
        clean = [{k: v for k, v in d.items() if k in keep} for d in boxes[:8] if isinstance(d, dict) and d.get("address")]
        if not self.at and self.boxes:
            # здесь почту настроили до 0.73 сами (без отметки времени) — свои ящики не теряем, а добавляем пришедшие
            have = {(b.data.get("address") or "").lower() for b in self.boxes}
            clean = [b.data for b in self.boxes] + [d for d in clean if d["address"].lower() not in have]
        self.boxes = [Box(d, self.ws, self._store) for d in clean]
        self._store(at=at, quiet=True)
        log.info("✉ Почта с другого своего устройства: %s", ", ".join(d["address"] for d in clean) or "отключена")
        return True

    def box(self, which=None):
        """Ящик по номеру или адресу (None — главный)."""
        if which in (None, "", 0, "0"):
            if not self.boxes:
                raise MailError("почта не подключена (студия → «Подключение» → «Почта»)")
            return self.boxes[0]
        if isinstance(which, int) or str(which).isdigit():
            i = int(which)
            if 0 <= i < len(self.boxes):
                return self.boxes[i]
            raise MailError("нет такого ящика")
        w = str(which).strip().lower()
        b = next((b for b in self.boxes if (b.data.get("address") or "").lower() == w), None) \
            or next((b for b in self.boxes if w and w in (b.data.get("address") or "").lower()), None)
        if not b:
            raise MailError(f"нет ящика «{which}» — подключены: " + ", ".join(x.data.get("address", "") for x in self.boxes))
        return b

    def configured(self):
        return any(b.configured() for b in self.boxes)

    def public(self):
        d = self.boxes[0].public() if self.boxes else {"has_password": False, "configured": False}
        d["boxes"] = [dict(b.public(), n=i) for i, b in enumerate(self.boxes)]
        return d

    def save(self, patch, box=0):
        """Сохранить настройки ящика box (номер; = числу ящиков — новый ящик) -> public()."""
        box = int(box or 0)
        if box >= len(self.boxes):
            addr = ((patch or {}).get("address") or "").strip().lower()
            if addr and any((b.data.get("address") or "").lower() == addr for b in self.boxes):
                raise MailError("этот ящик уже подключён")
            self.boxes.append(Box({}, self.ws, self._store))
            box = len(self.boxes) - 1
            try:
                self.boxes[box].save(patch)
            except MailError:
                self.boxes.pop()
                raise
            return self.public()
        self.boxes[box].save(patch)
        return self.public()

    def forget(self, box=None):
        """Убрать ящик (None — все)."""
        if box is None:
            self.boxes = []
        elif 0 <= int(box) < len(self.boxes):
            self.boxes.pop(int(box))
        self._store()
        return self.public()

    def test(self, box=0):
        return self.box(box).test()

    def send(self, to="", subject="", body="", attachments=(), box=None, headers=None):
        return self.box(box).send(to, subject, body, attachments, headers=headers)

    def inbox(self, limit=10, unread=False, query="", folder="INBOX", box=None):
        if box not in (None, ""):
            b = self.box(box)
            i = self.boxes.index(b)
            return [dict(x, uid=(f"{i}:{x['uid']}" if i else x["uid"]), box=b.data.get("address", "")) for x in b.inbox(limit, unread, query, folder)]
        live = [(i, b) for i, b in enumerate(self.boxes) if b.configured() and b.data.get("imap_host")]
        if not live:
            raise MailError("почта не подключена (студия → «Подключение» → «Почта»)")
        out, errs = [], []
        for i, b in live:
            try:
                out += [dict(x, uid=(f"{i}:{x['uid']}" if i else x["uid"]), box=b.data.get("address", "")) for x in b.inbox(limit, unread, query, folder)]
            except MailError as e:
                errs.append(f"{b.data.get('address')}: {e}")
        if errs and not out:
            raise MailError("; ".join(errs))

        def when(x):
            try:
                return email.utils.parsedate_to_datetime(x.get("date") or "").timestamp()
            except (TypeError, ValueError, IndexError, OverflowError):
                return 0
        out.sort(key=when, reverse=True)
        return out[: max(limit, limit * min(2, len(live)))] if len(live) > 1 else out[:limit]

    def read(self, uid, folder="INBOX", mark=False):
        """uid из inbox(): «N:uid» — письмо ящика N. mark — отметить прочитанным и на почте."""
        u = str(uid)
        i, u = (int(u.split(":", 1)[0]), u.split(":", 1)[1]) if re.fullmatch(r"\d+:\S+", u) else (0, u)
        b = self.box(i)
        return dict(b.read(u, folder, mark=mark), uid=str(uid), box=b.data.get("address", ""))
