"""MAX: писать ассистенту из мессенджера MAX и получать от него итоги, напоминания и вопросы — как в Telegram.

Два способа, как и у Telegram:
  • бот Dewiar (общий) — через сайт: dewiar.pro/dwrapp/max.php раскладывает сообщения по компьютерам (ключ dev:…),
    человек нажимает ссылку max.ru/<бот>?start=<код> — и бот его. Создавать своего бота не нужно (в MAX ботов
    могут создавать только ИП и организации);
  • свой бот — токен из кабинета MAX для партнёров (business.max.ru → Чат-боты → Интеграция → токен).

Внутри это тот же класс, что и Telegram (owner, код привязки, кнопки «Да/Нет», голосовые, файлы): здесь только
перевод запросов и событий MAX ⇄ вид Telegram. Bot API MAX: https://platform-api2.max.ru, токен — в заголовке
Authorization без «Bearer». Messengers — Telegram и MAX вместе для движка: куда отвечать и куда слать уведомления.
"""

import json
import logging
import os
import time

import httpx

from settings import CONFIG_DIR
from telegram import Telegram, TelegramError

log = logging.getLogger("dewiar.max")
PATH = CONFIG_DIR / "max.json"
DEFAULT_API = "https://platform-api2.max.ru"
SHARED_URL = "https://dewiar.pro/dwrapp/max.php"
LIMIT = 4000
HELP = ("Я — ваш ассистент Dewiar. Пишите или присылайте голосовые — отвечу как дома. Можно прислать фото или документ "
        "с вопросом.\n\n/stop — остановить ответ\n/status — что я сейчас делаю\n/help — эта подсказка")
UPLOAD_KIND = {"sendPhoto": ("image", "photo"), "sendDocument": ("file", "document"), "sendVoice": ("audio", "voice"),
               "sendAudio": ("audio", "audio")}


def to_tg(u, seq):
    """Событие MAX → событие в виде Telegram (его понимает общий код владельца, кнопок и вложений)."""
    t = u.get("update_type") or u.get("type")
    if t == "message_callback":
        cb = u.get("callback") or {}
        return {"update_id": seq, "callback_query": {"id": cb.get("callback_id", ""), "data": cb.get("payload") or "",
                                                     "from": {"id": (cb.get("user") or {}).get("user_id")}}}
    if t == "bot_started":
        usr = u.get("user") or {}
        text = "/start " + (u.get("payload") or "") if u.get("payload") else "/start"
        return {"update_id": seq, "message": {"message_id": f"start{seq}", "text": text.strip(),
                                              "chat": {"id": u.get("chat_id"), "type": "private"}, "from": _user(usr)}}
    if t != "message_created":
        return None
    m = u.get("message") or {}
    rc, body = m.get("recipient") or {}, m.get("body") or {}
    msg = {"message_id": body.get("mid", ""), "text": body.get("text") or "",
           "chat": {"id": rc.get("chat_id") or rc.get("user_id"), "type": "private" if rc.get("chat_type") == "dialog" else "group"},
           "from": _user(m.get("sender") or {})}
    for a in body.get("attachments") or []:
        p = a.get("payload") or {}
        url = p.get("url")
        if not url:
            continue
        if a.get("type") == "image":
            msg.setdefault("photo", []).append({"file_id": url, "file_size": 0})
        elif a.get("type") == "audio":
            msg["voice"] = {"file_id": url, "file_size": a.get("size") or 0}
        elif a.get("type") in ("file", "video"):
            msg["document"] = {"file_id": url, "file_name": a.get("filename") or ("видео.mp4" if a.get("type") == "video" else "файл"),
                               "file_size": a.get("size") or 0}
    return {"update_id": seq, "message": msg}


def _user(usr):
    return {"id": usr.get("user_id"), "first_name": usr.get("first_name") or usr.get("name") or "",
            "last_name": usr.get("last_name") or "", "username": usr.get("username") or ""}


def keyboard(markup):
    """reply_markup Telegram (inline_keyboard с callback_data) → вложение-клавиатура MAX."""
    rows = (markup or {}).get("inline_keyboard") or []
    return {"type": "inline_keyboard", "payload": {"buttons": [[{"type": "callback", "text": b.get("text", ""),
                                                                 "payload": b.get("callback_data", "")} for b in row]
                                                               for row in rows]}}


class Max(Telegram):
    """Бот MAX поверх общего кода Telegram: переопределены адреса, запросы (_call) и приём событий (_get_updates)."""
    TITLE = "MAX"
    HELP = HELP

    def __init__(self, on_message=None, path=PATH):
        super().__init__(on_message=on_message, path=path)
        self._seq = int(self.data.get("seq") or 0)

    # ---------- адреса ----------

    def _api(self):
        if self.shared():
            return self.data.get("api", "").rstrip("/")
        return (os.environ.get("DEWIAR_MAX_API") or self.data.get("api") or DEFAULT_API).rstrip("/")

    def _php(self):
        """Бот Dewiar в MAX — только dwrapp/max.php: метод в ?m=, без долгого ожидания."""
        return self.shared()

    def _hdr(self):
        # MAX ждёт в Authorization сам токен; сайту нужен «Bearer <ключ компьютера или аккаунта>».
        tok = self.data.get("token", "")
        return {"Authorization": ("Bearer " + tok) if self.shared() else tok}

    def link(self):
        bot, code = (self.data.get("bot") or {}).get("username", ""), self.data.get("code", "")
        return f"https://max.ru/{bot}?start={code}" if bot and code and not self.paired() else ""

    def _http(self, method, url, **kw):
        return httpx.request(method, url, **kw)       # MAX не заблокирован — без прокси Telegram

    # ---------- запросы ----------

    def _max(self, method, path, params=None, body=None, files=None, timeout=20):
        """Запрос к MAX (свой бот: path — путь API) или к сайту (бот Dewiar: path — метод в ?m=…) -> ответ.
        Сайт оборачивает ответ в {ok, result} — отдаём result; у MAX ответ без обёртки."""
        if self.shared():
            url, params = self._api(), dict(params or {}, m=path)
        else:
            url = self._api() + path
        try:
            r = self._http(method, url, params=params, json=body if files is None else None, files=files,
                           data=None if files is None else {k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else str(v))
                                                             for k, v in (body or {}).items()},
                           headers=self._hdr(), timeout=timeout)
        except httpx.HTTPError as e:
            raise TelegramError(f"MAX не отвечает: {e}") from e
        try:
            d = r.json()
        except ValueError as e:
            raise TelegramError(f"MAX ответил {r.status_code}") from e
        if r.status_code == 401:
            raise TelegramError(self._e401())
        if r.status_code >= 400 or (isinstance(d, dict) and d.get("ok") is False):
            raise TelegramError(_err(d, r.status_code))
        return d.get("result", d) if self.shared() and isinstance(d, dict) and "ok" in d else d

    def _e401(self):
        if self.shared():
            return "бот Dewiar в MAX на сайте не принял ключ — обновите dwrapp/max.php на сайте"
        return "токен бота MAX не подходит (его перевыпустили в кабинете MAX?)"

    def _call(self, method, timeout=20, files=None, **params):
        """Метод Bot API Telegram, который зовёт общий код, -> запрос MAX с ответом в виде Telegram.
        setLinkCode/dewiarUnlink/dewiarStatus есть только у сайта — для своего бота ничего не делают.
        Фото или голосовое, которое MAX не принял как картинку/аудио, отправляем ещё раз обычным файлом.
        getFile ничего не запрашивает: file_id у MAX — уже ссылка на файл (см. to_tg)."""
        if not self.data.get("token"):
            raise TelegramError("MAX не подключён")
        if method == "getMe":
            if self.shared():
                return self._max("POST", "getMe", timeout=timeout)
            me = self._max("GET", "/me", timeout=timeout)
            return {"id": me.get("user_id"), "username": me.get("username") or "", "first_name": me.get("first_name") or me.get("name") or "MAX"}
        if method in ("setLinkCode", "dewiarUnlink", "dewiarStatus"):
            if not self.shared():
                return True
            return self._max("POST", method, body=params, timeout=timeout)
        if method == "sendMessage":
            body = {"text": params.get("text", "")[:LIMIT]}
            if params.get("reply_markup"):
                body["attachments"] = [keyboard(params["reply_markup"])]
            r = self._send(params.get("chat_id"), body, timeout)
            mid = (((r or {}).get("message") or {}).get("body") or {}).get("mid") if isinstance(r, dict) else None
            return dict(r, message_id=mid) if isinstance(r, dict) and mid else r     # как у Telegram: номер сообщения
        if method == "editMessageReplyMarkup":
            # кнопки под сообщением (поручения, 28.10): у своего бота — PUT /messages с новым набором вложений;
            # у бота Dewiar на сайте такого метода нет — общий код это переживает (кнопки останутся прежними)
            if self.shared():
                raise TelegramError("MAX: правка кнопок через сайт не поддерживается")
            rm = params.get("reply_markup") or {}
            return self._max("PUT", "/messages", params={"message_id": params.get("message_id")},
                             body={"attachments": [keyboard(rm)] if rm.get("inline_keyboard") else []}, timeout=timeout)
        if method == "sendChatAction":
            if self.shared():
                return self._max("POST", "action", body={"action": "typing_on"}, timeout=timeout)
            return self._max("POST", f"/chats/{params.get('chat_id')}/actions", body={"action": "typing_on"}, timeout=timeout)
        if method == "answerCallbackQuery":
            cid = params.get("callback_query_id", "")
            if self.shared():
                return self._max("POST", "answer", body={"callback_id": cid}, timeout=timeout)
            return self._max("POST", "/answers", params={"callback_id": cid}, body={"notification": "Принято"}, timeout=timeout)
        if method in UPLOAD_KIND:
            kind, field = UPLOAD_KIND[method]
            name, data, ctype = _file_tuple((files or {}).get(field))
            try:
                return self._upload_send(params.get("chat_id"), kind, name, data, ctype, params.get("caption", ""), timeout)
            except TelegramError:
                if kind == "file":
                    raise
                return self._upload_send(params.get("chat_id"), "file", name, data, ctype, params.get("caption", ""), timeout)
        if method == "getFile":
            return {"file_path": params.get("file_id")}
        raise TelegramError(f"MAX: {method} не поддерживается")

    def _send(self, chat_id, body, timeout=20):
        """Отправить сообщение. Загруженное вложение MAX обрабатывает не сразу и отвечает ошибкой «…not.ready» —
        тогда ждём и повторяем (12 попыток, всего около 40 секунд)."""
        for i in range(12):
            try:
                if self.shared():
                    return self._max("POST", "send", body=body, timeout=timeout)
                return self._max("POST", "/messages", params={"chat_id": chat_id}, body=body, timeout=timeout)
            except TelegramError as e:
                if "not.ready" not in str(e) or i == 11:
                    raise
                time.sleep(1.0 + i * 0.5)

    def _upload_send(self, chat_id, kind, name, data, ctype, caption, timeout):
        """Файл владельцу. У MAX в три шага: POST /uploads -> адрес загрузки, загрузка -> токен файла
        (у картинок — внутри photos), затем сообщение с вложением по этому токену."""
        if self.shared():                               # сайт сам загрузит файл в MAX и пришлёт владельцу
            return self._max("POST", "upload", params={"type": kind}, body={"caption": caption[:1000]},
                             files={"data": (name, data, ctype)}, timeout=max(timeout, 120))
        up = self._max("POST", "/uploads", params={"type": kind}, timeout=timeout)
        try:
            r = self._http("POST", up["url"], files={"data": (name, data, ctype)}, timeout=max(timeout, 120))
            r.raise_for_status()
            res = r.json() if r.content else {}
        except (httpx.HTTPError, ValueError, KeyError) as e:
            raise TelegramError(f"файл не загрузился в MAX: {e}") from e
        token = up.get("token") or res.get("token")
        if kind == "image" and isinstance(res.get("photos"), dict) and res["photos"]:
            token = next(iter(res["photos"].values())).get("token") or token
        if not token:
            raise TelegramError("MAX не вернул ключ загруженного файла")
        body = {"text": caption[:1000] or None, "attachments": [{"type": kind, "payload": {"token": token}}]}
        return self._send(chat_id, body, timeout)

    # ---------- приём ----------

    def _get_updates(self):
        """События -> список в виде Telegram. Сайт отдаёт [{update_id, max: событие}] и понимает offset.
        Свой бот: MAX вместо offset даёт marker, а номеров событий нет — нумеруем сами (seq), потому что
        общий код Telegram запоминает offset по update_id."""
        if self.shared():
            got = self._max("POST", "getUpdates", body={"offset": self.data.get("offset", 0)}, timeout=40)
            out = []
            for x in got or []:
                u = to_tg(x.get("max") or {}, x.get("update_id", 0))
                if u:
                    out.append(u)
                else:                                   # ненужное событие — подтвердить, чтобы не пришло снова
                    with self._lock:
                        self.data["offset"] = x.get("update_id", 0) + 1
            return out
        params = {"timeout": 25, "types": "message_created,message_callback,bot_started"}
        if self.data.get("marker") is not None:
            params["marker"] = self.data["marker"]
        d = self._max("GET", "/updates", params=params, timeout=40)
        out = []
        for x in d.get("updates") or []:
            self._seq += 1
            u = to_tg(x, self._seq)
            if u:
                out.append(u)
        with self._lock:
            if d.get("marker") is not None:
                self.data["marker"] = d["marker"]
            self.data["seq"] = self._seq
            self._save()
        return out

    def download(self, file_id, size=None):
        """file_id здесь — прямая ссылка на вложение из события MAX (см. to_tg), скачиваем её без заголовков."""
        if size and size > 50 * 1024 * 1024:
            raise TelegramError("файл больше 50 МБ")
        try:
            r = self._http("GET", file_id, timeout=60, follow_redirects=True)
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise TelegramError(f"файл не скачался: {e}") from e
        return r.content

    # ---------- подключение ----------

    def connect(self, token, api=""):
        """Свой бот MAX — как Telegram.connect. Формат токена MAX не описан, поэтому проверка грубая (длина, пробелы),
        а настоящая — запросом /me. Для того же токена сохраняется marker, чтобы не получить старые события заново."""
        token = (token or "").strip()
        if len(token) < 20 or " " in token:
            raise TelegramError("это не похоже на токен бота MAX — он длинный, без пробелов (кабинет MAX → Чат-боты → Интеграция)")
        old = dict(self.data)
        self.data = {"token": token, "api": (api or "").strip()}
        try:
            me = self._call("getMe")
        except TelegramError:
            self.data = old
            raise
        self.stop()
        import random
        with self._lock:
            same = old.get("token") == token
            self.data = {"token": token, "api": (api or "").strip(),
                         "bot": {"username": me.get("username", ""), "name": me.get("first_name", "")},
                         "owner": old.get("owner") if same else None,
                         "code": old.get("code") if same and old.get("code") else f"{random.SystemRandom().randint(0, 999999):06d}",
                         "notify": old.get("notify", True), "voice_home": old.get("voice_home", False),
                         "voice_reply": old.get("voice_reply", True), "marker": old.get("marker") if same else None,
                         "seq": old.get("seq", 0)}
            self._save()
        self.problem = ""
        self.start()
        log.info("MAX: бот %s подключён", me.get("username"))
        return self.public()

    def connect_shared(self, api="", account_token=""):
        return super().connect_shared(api or SHARED_URL, account_token)

    def public(self):
        """Как у Telegram, но без прокси: MAX ходит напрямую."""
        p = super().public()
        p.pop("proxy", None)
        return p


def _file_tuple(f):
    """Элемент files=… общего кода ((имя, данные или открытый файл[, тип])) -> (имя, bytes, тип)."""
    if f is None:
        raise TelegramError("нет файла")
    name, data = f[0], f[1]
    ctype = f[2] if len(f) > 2 else "application/octet-stream"
    if hasattr(data, "read"):
        data = data.read()
    return name, data, ctype


def _err(d, code):
    """Текст ошибки: MAX отвечает {code, message}, сайт — {description}; код добавляем, если его нет в тексте."""
    if isinstance(d, dict):
        msg = d.get("description") or d.get("message") or d.get("error") or ""
        c = d.get("code") or ""
        return f"{msg} ({c})" if c and c not in msg else (msg or f"ошибка {code}")
    return f"ошибка {code}"


class Messengers:
    """Telegram и MAX вместе: уведомления — во все подключённые; ответ, файл, дело — туда, где владелец писал последним."""

    def __init__(self, *bots):
        self.bots = bots

    def linked(self):
        return [b for b in self.bots if b.paired()]

    def paired(self):
        return bool(self.linked())

    def notify_on(self):
        return any(b.notify_on() for b in self.bots)

    def primary(self):
        got = self.linked()
        return max(got, key=lambda b: b.last_in) if got else None

    @property
    def problem(self):
        b = self.primary()
        return b.problem if b else ""

    @property
    def title(self):
        b = self.primary()
        return b.TITLE if b else "Telegram"

    def send(self, text, buttons=None):
        b = self.primary()
        return bool(b and b.send(text, buttons=buttons))

    def send_file(self, path, caption=""):
        b = self.primary()
        if not b:
            raise TelegramError("Telegram и MAX не подключены")
        return b.send_file(path, caption)

    def notify(self, text, buttons=None, file=None):
        """Уведомление во все подключённые мессенджеры с включёнными уведомлениями -> ушло ли хоть в один.
        Файл — вдогонку; его ошибка только пишется в журнал."""
        ok = False
        for b in self.bots:
            if b.notify_on():
                ok = b.send(text, buttons=buttons) or ok
                if file:
                    try:
                        b.send_file(file)
                    except (TelegramError, OSError) as e:
                        log.warning("%s: файл не отправился: %s", b.TITLE, e)
        return ok
