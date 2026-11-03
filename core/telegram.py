"""Telegram: писать ассистенту с телефона и получать от него итоги задач и уведомления.

Два режима. Свой бот (токен от @BotFather): Dewiar сам опрашивает Bot API (long polling) — работает за NAT, порты
открывать не нужно. Общий бот Dewiar (mode="dewiar"): те же методы Bot API через шлюз — server/tg (с долгим ожиданием)
или dwrapp/tg.php на сайте (метод в ?m=, ответ сразу; умеет отвечать, пока компьютер выключен — sync()).
Принимает текст, голосовые (тот же слух, что дома), фото и документы, кнопки «Да/Нет», /stop, /status;
наружу — send(), send_file(), send_voice(). Класс Telegram — основа и для MAX (maxbot.py).

Безопасность: бот отвечает только владельцу — тому, кто первым прислал код из студии; остальным одна фраза и молчание.
Токен хранится в ~/.config/dewiar/telegram.json (0600) и в студию не отдаётся (public() его не содержит).
"""

import json
import logging
import os
import random
import re
import secrets
import threading
import time
from pathlib import Path

import httpx

from settings import CONFIG_DIR

log = logging.getLogger("dewiar.telegram")
PATH = CONFIG_DIR / "telegram.json"
DEFAULT_API = "https://api.telegram.org"
SHARED_URL = "https://dewiar.pro/dwrapp/tg.php"     # общий бот Dewiar на сайте (без аккаунта — по ключу компьютера)
LIMIT = 4000                       # Telegram принимает до 4096 символов в сообщении
MAX_FILE = 20 * 1024 * 1024        # Bot API отдаёт ботам файлы до 20 МБ
TOKEN_RX = re.compile(r"^\d{5,15}:[A-Za-z0-9_-]{30,60}$")
HELP = ("Я — ваш ассистент Dewiar. Пишите или присылайте голосовые — отвечу как дома. Можно прислать фото или документ "
        "с вопросом.\n\n/stop — остановить ответ\n/status — что я сейчас делаю\n/help — эта подсказка")


class TelegramError(Exception):
    pass


class TelegramConflict(TelegramError):
    """Ответ 409: этот же бот (свой токен) уже опрашивает другая программа — обычно второй компьютер с тем же токеном
    (№512: слепок с другого компьютера принёс токен бота «своего» режима). См. _conflict_hit."""


CONFLICT_SAY = "Этого бота слушает другой ваш компьютер — бот отвечает оттуда"


class TelegramAuthError(TelegramError):
    """Ответ 401: ключ (токен бота, ключ компьютера или вход в аккаунт) больше не принимают. Сам по себе не
    пройдёт — приём не повторяет запрос по кругу, а ждёт долго (см. _poll)."""


def normalize_proxy(text):
    """Прокси для Telegram: socks5://user:pass@host:1080, http://host:3128, ссылка tg://socks?… или t.me/socks?… -> строка URL.
    MTProto-прокси (tg://proxy?…secret=…) работает только в приложении Telegram, Bot API через него не ходит.
    Разбор общий — net.normalize_proxy; ошибка превращается в TelegramError."""
    from net import NetError, normalize_proxy as _norm
    try:
        return _norm(text)
    except NetError as e:
        raise TelegramError(str(e)) from None


def _hide(px):
    """Прокси для показа в студии: пароль заменён точками."""
    import re as _re
    return _re.sub(r"//([^:/@]+):[^@]*@", r"//\1:•••@", px or "")


def chunks(text, n=LIMIT):
    """Длинный ответ — на несколько сообщений: режем по абзацу, строке, предложению или пробелу.
    Если удобное место раньше трети лимита — режем ровно по лимиту, иначе кусочки выйдут слишком мелкими."""
    text = (text or "").strip()
    out = []
    while len(text) > n:
        cut = max(text.rfind("\n\n", 0, n), text.rfind("\n", 0, n), text.rfind(". ", 0, n), text.rfind(" ", 0, n))
        cut = cut if cut > n // 3 else n
        out.append(text[:cut].rstrip())
        text = text[cut:].lstrip()
    if text:
        out.append(text)
    return out


class Telegram:
    """Подключение к одному боту: хранение настроек, поток приёма сообщений, отправка владельцу.
    События уходят в on_message(kind, data): ask, confirm, alarm_cb, stop, status, paired.
    Max (maxbot.py) наследует всё и переопределяет только запросы к API."""
    TITLE = "Telegram"
    HELP = HELP

    def __init__(self, on_message=None, path=PATH):
        self.path = Path(path)
        self.on_message = on_message or (lambda kind, data: None)
        self._lock = threading.Lock()
        self.data = self._load()
        self._stop = threading.Event()
        self._thread = None
        self.problem = ""
        self.last_seen = 0.0
        self.last_in = 0.0                 # когда владелец писал сюда последний раз (куда отвечать, если мессенджеров два)
        self._strangers = set()
        # Несколько компьютеров одного аккаунта (03.11): бот общий, сообщение забирает один — «главный» (выбирает сервер,
        # dwrapp/tg.php q_main). node() -> {"device", "name", "act"} — кто этот компьютер и сколько секунд назад человек
        # говорил с ним сам (Engine); main — этот ли компьютер сейчас отвечает; nodes — кто ещё подхватит (для студии).
        # quiet_follower() -> True — уведомления шлёт только главный (напоминания одни и те же на всех — синхронизация).
        self.node = None
        self.main = True
        self.nodes = {}
        self.quiet_follower = lambda: True
        self._c_first = self._c_last = 0.0      # №512: 409 — с какого и до какого времени бота слушает кто-то ещё
        self._c_said = False                    # сказали человеку «слушает другой компьютер» — опрашиваем редко

    # ---------- хранение ----------

    def _load(self):
        try:
            d = json.loads(self.path.read_text(encoding="utf-8"))
            return d if isinstance(d, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save(self):
        """Атомарная запись через .tmp; права 0600 — в файле токен бота."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        tmp.replace(self.path)

    def _api(self):
        if self.shared():
            return self.data.get("api", "").rstrip("/")
        return (os.environ.get("DEWIAR_TG_API") or self.data.get("api") or DEFAULT_API).rstrip("/")

    def shared(self):
        """Общий бот Dewiar (через шлюз server/tg или dwrapp/tg.php), а не свой бот пользователя."""
        return self.data.get("mode") == "dewiar"

    def _php(self):
        """Общий бот одним PHP-файлом на сайте (dwrapp/tg.php): метод — параметром ?m=, без долгого ожидания."""
        return self.shared() and ".php" in self._api()

    def _url(self, method):
        # Шлюзу общего бота токен в адресе не нужен (там «bot0»): компьютер он узнаёт по заголовку Authorization (_hdr).
        if self._php():
            return f"{self._api()}?m={method}"
        return f"{self._api()}/bot{'0' if self.shared() else self.data.get('token')}/{method}"

    def _hdr(self):
        return {"Authorization": "Bearer " + self.data.get("token", "")} if self.shared() else {}

    def _hdr_dev(self):
        """Заголовки с прежним ключом компьютера (X-Dewiar-Dev) — когда сервер должен знать, что он прикреплён к аккаунту."""
        h = self._hdr()
        if self.uses_account() and str(self.data.get("dev", "")).startswith("dev:"):
            h["X-Dewiar-Dev"] = self.data["dev"]
        return h

    def uses_account(self):
        """Общий бот через аккаунт сайта (а не по ключу компьютера) — при выходе из аккаунта отключается."""
        return self.shared() and not str(self.data.get("token", "")).startswith("dev:")

    def link(self):
        """Ссылка «одним нажатием»: открыть бота и сразу отправить ему код (кнопка «Запустить» в Telegram)."""
        bot, code = (self.data.get("bot") or {}).get("username", ""), self.data.get("code", "")
        return f"https://t.me/{bot}?start={code}" if bot and code and not self.paired() else ""

    def connected(self):
        return bool(self.data.get("token"))

    def paired(self):
        return bool(self.data.get("token") and (self.data.get("owner") or {}).get("id"))

    def notify_on(self):
        return self.paired() and self.data.get("notify", True) and (self.main or not self.quiet_follower())

    def public(self):
        """Состояние для студии. Токен сюда не попадает никогда; код привязки — только пока владельца нет."""
        d = self.data
        return {"connected": self.connected(), "paired": self.paired(), "bot": (d.get("bot") or {}).get("username", ""),
                "bot_name": (d.get("bot") or {}).get("name", ""), "owner": (d.get("owner") or {}).get("name", ""),
                "code": "" if self.paired() else d.get("code", ""), "notify": d.get("notify", True),
                "voice_home": bool(d.get("voice_home")), "voice_reply": d.get("voice_reply", True), "api": d.get("api", ""),
                "running": bool(self._thread and self._thread.is_alive()), "problem": self.problem,
                "mode": "dewiar" if self.shared() else ("own" if self.connected() else ""), "link": self.link(),
                "account": self.uses_account(), "proxy": _hide(d.get("proxy", "")),
                "offline": d.get("offline", True), "can_offline": self._php(), "offline_state": getattr(self, "offline_state", {}),
                "main": self.main, "who": self.who()}

    def who(self):
        """Кто сейчас отвечает в боте и кто подхватит -> строка для студии и /status («Отвечает: Ноутбук (этот компьютер) ·
        запасные: Домашний ПК, телефон, сервер Dewiar») или "" — сервер не сообщил (старый tg.php) или бот не привязан."""
        dw = self.nodes or {}
        if not dw or not self.paired():
            return ""

        def name(n):
            s = n.get("name") or "компьютер"
            return s + (" (этот компьютер)" if n.get("me") else "" if n.get("live") else " (выключен)")
        pcs = dw.get("nodes") or []
        main = next((n for n in pcs if n.get("main")), None)
        spare = [name(n) for n in pcs if n is not main]
        ph = dw.get("phone") or {}
        if ph.get("on"):
            spare.append("телефон" if ph.get("live") else "телефон (когда приложение открыто)")
        if dw.get("server"):
            spare.append("сервер Dewiar")
        return "Отвечает: " + (name(main) if main else "сервер Dewiar") + (" · запасные: " + ", ".join(spare) if spare else "")

    # ---------- запросы к Telegram ----------

    def _http(self, method, url, **kw):
        """Запрос к Telegram — напрямую или через прокси из настроек (на случай, когда провайдер блокирует Telegram).
        Прокси применяется ко всем запросам этого бота, в том числе к шлюзу общего бота."""
        px = self.data.get("proxy") or None
        try:
            return httpx.request(method, url, proxy=px, **kw) if px else httpx.request(method, url, **kw)
        except ImportError as e:
            raise TelegramError("для SOCKS-прокси нужна библиотека socksio — обновите Dewiar или возьмите HTTP-прокси") from e
        except httpx.ProxyError as e:
            raise TelegramError(f"прокси не отвечает или не пускает: {e}") from e

    def _call(self, method, timeout=20, files=None, **params):
        """Метод Bot API -> поле result ответа. С files — multipart (вложенные dict/list уходят строкой JSON,
        так требует Bot API), без них — JSON. Любая неудача — TelegramError с понятным человеку текстом."""
        token = self.data.get("token")
        if not token:
            raise TelegramError(f"{self.TITLE} не подключён")
        url = self._url(method)
        try:
            if files:
                r = self._http("POST", url, data={k: (json.dumps(v) if isinstance(v, (dict, list)) else str(v))
                                                  for k, v in params.items()}, files=files, timeout=timeout, headers=self._hdr())
            else:
                r = self._http("POST", url, json=params, timeout=timeout, headers=self._hdr())
        except httpx.HTTPError as e:
            raise TelegramError(f"Telegram не отвечает: {e}") from e
        try:
            d = r.json()
        except ValueError as e:
            raise TelegramError(f"Telegram ответил {r.status_code}") from e
        if not d.get("ok"):
            if r.status_code == 401:
                raise TelegramAuthError(self._e401())
            if r.status_code == 409 and not self.shared():
                raise TelegramConflict("этого бота уже слушает другая программа (или второй Dewiar)")
            raise TelegramError(d.get("description") or f"ошибка {r.status_code}")
        return d.get("result")

    def _e401(self):
        if self.uses_account():
            return "вход в аккаунт Dewiar устарел — войдите заново"
        if self.shared():
            return "бот Dewiar на сайте не принял ключ — обновите dwrapp/tg.php на сайте"
        return "токен бота не подходит (его отозвали в @BotFather?)"

    # ---------- подключение ----------

    def connect(self, token, api=""):
        """Свой бот: проверить токен (getMe), сохранить и запустить приём -> public().
        Тот же токен — владелец и смещение сохраняются; новый — нужен новый 6-значный код привязки. Прокси не сбрасывается."""
        token = (token or "").strip()
        if not TOKEN_RX.match(token):
            raise TelegramError("это не похоже на токен бота — он выглядит так: 123456789:AAH…")
        old = dict(self.data)
        self.data = {"token": token, "api": (api or "").strip(), "proxy": old.get("proxy", "")}
        try:
            me = self._call("getMe")
        except TelegramError:
            self.data = old
            raise
        self.stop()
        with self._lock:
            same = old.get("token") == token
            self.data = {"token": token, "api": (api or "").strip(),
                         "bot": {"username": me.get("username", ""), "name": me.get("first_name", "")},
                         "owner": old.get("owner") if same else None,
                         "code": old.get("code") if same and old.get("code") else f"{random.SystemRandom().randint(0, 999999):06d}",
                         "notify": old.get("notify", True), "voice_home": old.get("voice_home", False),
                         "voice_reply": old.get("voice_reply", True),
                         "offset": old.get("offset", 0) if same else 0, "proxy": old.get("proxy", "")}
            self._save()
        self.problem = ""
        self.start()
        log.info("Telegram: бот @%s подключён", me.get("username"))
        return self.public()

    def connect_shared(self, api="", account_token=""):
        """Общий бот Dewiar -> public(). Аккаунт не нужен: Dewiar придумывает ключ этого компьютера (dev:…, при
        повторном подключении — прежний) и регистрирует на сайте одноразовый код; человек открывает ссылку
        t.me/<бот>?start=<код>, жмёт «Запустить» — бот его. Если передан account_token — вместо ключа компьютера
        используется вход в аккаунт сайта (uses_account)."""
        api = (api or SHARED_URL).strip()
        old = dict(self.data)
        k = str(old.get("token", ""))
        dev = k if old.get("mode") == "dewiar" and k.startswith("dev:") else str(old.get("dev", ""))
        if not dev.startswith("dev:"):
            dev = ""
        if not account_token:
            account_token = dev or "dev:" + secrets.token_hex(24)
        acc = not account_token.startswith("dev:")
        self.data = {"mode": "dewiar", "token": account_token, "api": api.rstrip("/"), "proxy": old.get("proxy", ""),
                     **({"dev": dev} if acc and dev else {})}
        try:
            me = self._call("getMe")
        except TelegramError:
            self.data = old
            raise
        self.stop()
        same = old.get("mode") == "dewiar"
        with self._lock:
            same = same and old.get("token") == account_token
            self.data = {"mode": "dewiar", "token": account_token, "api": api.rstrip("/"),
                         "bot": {"username": me.get("username", ""), "name": me.get("first_name", "")},
                         "owner": old.get("owner") if same else None, "code": "",
                         "notify": old.get("notify", True), "voice_home": old.get("voice_home", False),
                         "voice_reply": old.get("voice_reply", True), "offset": old.get("offset", 0) if same else 0,
                         "proxy": old.get("proxy", ""), **({"dev": dev} if acc and dev else {})}
            self._save()
        if acc and not self.paired():
            self._adopt()                    # бот аккаунта уже привязан на другом устройстве — подхватываем без кода
        if not self.paired():
            self._register_code()
        self.problem = ""
        self.start()
        log.info("Telegram: общий бот @%s", me.get("username"))
        return self.public()

    def _register_code(self):
        """Зарегистрировать на шлюзе общего бота новый код привязки и сохранить его -> код.
        Шлюз отвечает «занят», если такой код уже выдан другому компьютеру, — тогда пробуем другой."""
        for _ in range(5):
            code = secrets.token_urlsafe(18)          # длинный, угадать нельзя; вводить не нужно — он в ссылке
            try:
                self._call("setLinkCode", code=code, **self._node_params())
            except TelegramError as e:
                if "занят" in str(e):
                    continue
                raise
            with self._lock:
                self.data["code"] = code
                self._save()
            return code
        raise TelegramError("не удалось получить код привязки — попробуйте ещё раз")

    def _node_params(self):
        """Кто этот компьютер — для сервера (device, name, act); пусто, если Engine не сказал."""
        try:
            n = self.node() if self.node else None
        except Exception:  # noqa: BLE001
            n = None
        return {k: v for k, v in (n or {}).items() if v is not None and v != ""}

    def _adopt(self, st=None):
        """Привязка уже есть у аккаунта (её сделал другой компьютер или телефон) — взять владельца с сервера.
        -> True, если владелец теперь известен."""
        if st is None:
            try:                                              # с прежним ключом компьютера — сервер перенесёт его привязку в аккаунт
                r = self._http("POST", self._url("dewiarStatus"), json=self._node_params(), timeout=15, headers=self._hdr_dev())
                st = r.json().get("result") if r.status_code == 200 else None
            except (httpx.HTTPError, ValueError, TelegramError):
                return False
        own = (st or {}).get("owner") or {}
        if not ((st or {}).get("linked") and own.get("id") and own.get("chat")):
            return False
        with self._lock:
            self.data["owner"] = {"id": own["id"], "chat": own["chat"], "name": own.get("name") or st.get("name", ""), "username": ""}
            self.data.pop("code", None)
            if st.get("bot") and not (self.data.get("bot") or {}).get("username"):
                self.data["bot"] = {"username": st["bot"], "name": "Dewiar"}
            self._save()
        log.info("Telegram: бот аккаунта подхвачен — владелец %s", self.data["owner"]["name"])
        return True

    def join(self, account_token, api):
        """Компьютер вошёл в аккаунт — бот аккаунта отвечает и отсюда, без повторной активации (03.11; «включаю второй
        комп, синхронизированный с первым, — отвечает сервер»). Раз в минуту (Engine._tg_join):
        - бот здесь не подключён, а у аккаунта он есть — подхватить (владелец с сервера);
        - бот здесь по ключу этого компьютера (dev:) — перенести его в аккаунт: ключ уходит заголовком X-Dewiar-Dev, сервер
          переводит привязку и данные (если у аккаунта своей привязки к другому человеку нет);
        - бот аккаунта отключили на другом устройстве — здесь тоже отключить.
        Свой бот (@BotFather) не трогаем. -> True, если что-то поменялось."""
        if not account_token or (self.connected() and not self.shared()):
            return False
        api = (self._api() if self.shared() else api or SHARED_URL).rstrip("/")
        if ".php" not in api:
            return False                                      # шлюз server/tg аккаунты не объединяет
        tok = str(self.data.get("token", ""))
        dev = tok if self.shared() and tok.startswith("dev:") else str(self.data.get("dev", ""))
        hdr = {"Authorization": "Bearer " + account_token}
        if dev.startswith("dev:") and tok != account_token:
            hdr["X-Dewiar-Dev"] = dev
        try:
            r = self._http("POST", f"{api}?m=dewiarStatus", json=self._node_params(), timeout=15, headers=hdr)
            d = r.json()
        except (httpx.HTTPError, ValueError, TelegramError):
            return False
        if r.status_code != 200 or not d.get("ok"):
            return False
        st = d.get("result") or {}
        own = st.get("owner") or {}
        if not st.get("linked") or not own.get("id"):
            if self.uses_account() and self.paired() and tok == account_token:
                log.info("Telegram: бот аккаунта отключили на другом устройстве — здесь тоже")
                self.leave(server=False)
                return True
            return False
        mine = (self.data.get("owner") or {}).get("id")
        if tok == account_token and mine == own.get("id"):
            return False                                      # уже подхвачен
        if self.shared() and tok.startswith("dev:") and self.paired() and mine != own.get("id"):
            return False                                      # здесь бот другого человека в Telegram — не смешиваем
        moved = self.shared() and tok.startswith("dev:")
        self.stop()
        with self._lock:
            old = dict(self.data)
            self.data = {"mode": "dewiar", "token": account_token, "api": api, "proxy": old.get("proxy", ""),
                         "bot": old.get("bot") or {"username": st.get("bot", ""), "name": "Dewiar"},
                         "notify": old.get("notify", True), "voice_home": old.get("voice_home", False),
                         "voice_reply": old.get("voice_reply", True), "offline": old.get("offline", True),
                         "offset": 0, "inbox_ack": old.get("inbox_ack", 0) if moved else 0}
            if dev.startswith("dev:"):
                self.data["dev"] = dev
            self._save()
        self._adopt(st)
        self.problem = ""
        self.start()
        log.info("Telegram: %s", "бот этого компьютера перенесён в аккаунт" if moved else "бот аккаунта подхвачен на этом компьютере")
        return True

    def leave(self, server=True):
        """Выход из аккаунта: этот компьютер больше не отвечает в боте аккаунта, а бот у аккаунта остаётся — телефону и
        другим компьютерам. Ключ компьютера (dev:) и прокси сохраняются: «Подключить» без аккаунта возьмёт прежний ключ."""
        if server and self.uses_account():
            try:                                              # с прежним ключом: сервер открепит его от аккаунта
                self._http("POST", self._url("dewiarLeave"), json=self._node_params(), timeout=8, headers=self._hdr_dev())
            except (httpx.HTTPError, TelegramError):
                pass
        self.stop()
        with self._lock:
            keep = {k: self.data[k] for k in ("proxy", "dev") if self.data.get(k)}
            self.data = keep
            try:
                if keep:
                    self._save()
                else:
                    self.path.unlink()
            except OSError:
                pass
        self.main, self.nodes = True, {}
        self.problem = ""
        return self.public()

    def can_sync(self):
        """Бот Dewiar на сайте (dwrapp/tg.php) и он привязан — сервер может отвечать, пока компьютер выключен."""
        return self._php() and self.paired()

    def sync(self, payload):
        """dewiarSync: отдать серверу то, что нужно для ответов без компьютера (ключ облака, персона, напоминания,
        списки, недавний разговор — собирает engine_remote._tg_sync_payload), и забрать сделанное сервером за это время."""
        return self._call("dewiarSync", timeout=20, **payload)

    def refresh_token(self, account_token):
        """После нового входа в аккаунт — передать общему боту новый токен (только если бот работает через аккаунт)."""
        if self.uses_account() and account_token:
            with self._lock:
                self.data["token"] = account_token
                self._save()

    def set(self, patch):
        with self._lock:
            for k in ("notify", "voice_home", "voice_reply", "offline"):
                if k in patch:
                    self.data[k] = bool(patch[k])
            self._save()
        return self.public()

    def set_proxy(self, text):
        """Задать прокси (пусто — без прокси) и сразу проверить, что Telegram через него отвечает; не отвечает —
        прежний прокси возвращается. Для общего бота и до подключения проверяем api.telegram.org (токена нет),
        для своего — getMe."""
        px = normalize_proxy(text)
        old = self.data.get("proxy", "")
        with self._lock:
            self.data["proxy"] = px
        if px:
            try:
                r = self._http("GET", "https://api.telegram.org" if self.shared() or not self.connected() else self._url("getMe"),
                               timeout=15, headers={} if self.shared() else self._hdr())
                if r.status_code >= 500:
                    raise TelegramError(f"через прокси Telegram ответил {r.status_code}")
            except (TelegramError, httpx.HTTPError) as e:
                with self._lock:
                    self.data["proxy"] = old
                raise TelegramError(f"через этот прокси Telegram недоступен: {e}") from e
        with self._lock:
            self._save()
        self.problem = ""
        if self.connected():                          # поток приёма держит старое соединение — перезапускаем
            self.stop()
            self.start()
        return self.public()

    def new_code(self):
        """Сменить владельца: прежний отвязан (у общего бота — и на шлюзе), выдаётся новый код привязки."""
        with self._lock:
            self.data["owner"] = None
            self.data["code"] = f"{random.SystemRandom().randint(0, 999999):06d}"
            self._save()
        if self.shared():
            try:
                self._call("dewiarUnlink")
            except TelegramError:
                pass
            self._register_code()
        return self.public()

    def forget(self):
        """Отключить бота и стереть его настройки. Прокси остаётся: он понадобится и следующему боту."""
        if self.shared():
            try:
                self._call("dewiarUnlink", timeout=8)
            except TelegramError:
                pass
        self.stop()
        with self._lock:
            px = self.data.get("proxy", "")
            self.data = {"proxy": px} if px else {}
            try:
                if px:
                    self._save()
                else:
                    self.path.unlink()
            except OSError:
                pass
        self.problem = ""
        return self.public()

    # ---------- приём сообщений ----------

    def start(self):
        if not self.connected() or (self._thread and self._thread.is_alive()):
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._poll, name="telegram", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        t = self._thread
        if t and t.is_alive() and t is not threading.current_thread():
            t.join(timeout=3)
        self._thread = None

    ALLOWED = ["message", "callback_query"]          # какие события просить у Telegram (бот персонажа — ещё my_chat_member)
    CONFLICT_AFTER = 60       # №512: 409 дольше минуты — это второй компьютер, а не перезапуск: говорим и опрашиваем реже
    CONFLICT_RARE = 600       # тогда — раз в 10 минут (вдруг тот компьютер выключили)

    def _conflict_hit(self, now=None):
        """Очередной 409 -> перешли ли на редкий опрос. Один раз за такой период — сказать человеку (on_message
        «conflict») и в журнал; дальше молча."""
        now = time.time() if now is None else now
        if not self._c_first or now - self._c_last > 3 * self.CONFLICT_RARE:
            self._c_first = now
        self._c_last = now
        if not self._c_said and now - self._c_first >= self.CONFLICT_AFTER:
            self._c_said = True
            log.warning("Telegram: %s — здесь проверяю раз в %d мин", CONFLICT_SAY, self.CONFLICT_RARE // 60)
            try:
                self.on_message("conflict", {"text": CONFLICT_SAY})
            except Exception:  # noqa: BLE001
                log.exception("Telegram: сообщение о втором компьютере")
        return self._c_said

    def _conflict_gone(self, now=None):
        """Опрос прошёл. 409 давно не было (тот компьютер выключили) — снова отвечаем отсюда, как обычно."""
        now = time.time() if now is None else now
        if self._c_said and now - self._c_last > 2 * self.CONFLICT_RARE:
            self._c_said, self._c_first = False, 0.0
            log.info("Telegram: другой компьютер больше не слушает бота — отвечаю отсюда")
        return not self._c_said

    def _poll(self):
        """Поток приёма. Ошибки сети — повтор с паузой 3→60 с; негодный токен — пауза 5 минут (сам он не исправится).
        Смещение сохраняется до обработки: сообщение, на котором обработка падает, не придёт повторно по кругу."""
        wait = 3
        while not self._stop.is_set():
            import egress
            if egress.local_only():                          # стоп-кран: бот на паузе (без ошибок в журнале)
                self.problem = "на паузе: включён режим «Ничего не уходит в интернет»"
                self._stop.wait(10)
                continue
            try:
                ups = self._get_updates()
                rare = not self._conflict_gone()
                self.problem, wait = (CONFLICT_SAY if rare else ""), 3
                self.last_seen = time.time()
                if rare:
                    self._stop.wait(self.CONFLICT_RARE)     # №512: бот отвечает с другого компьютера — не перебиваем его
                elif not ups and self._php():
                    self._stop.wait(2.0)             # PHP-шлюз не умеет ждать — спрашиваем раз в 2 секунды
            except TelegramError as e:
                if self._stop.is_set():
                    break
                if isinstance(e, TelegramConflict) and self._conflict_hit():
                    self.problem = CONFLICT_SAY             # сказано один раз; дальше — редко и без записей в журнал
                    self._stop.wait(self.CONFLICT_RARE)
                    continue
                if self.problem != str(e):
                    log.warning("Telegram: %s", e)
                self.problem = str(e)
                fatal = isinstance(e, TelegramAuthError) or "токен" in str(e)   # по тексту — для maxbot.py
                self._stop.wait(300 if fatal else wait)
                wait = min(wait * 2, 60)
                continue
            for u in ups or []:
                with self._lock:
                    self.data["offset"] = u["update_id"] + 1
                    self._save()
                try:
                    self._handle(u)
                except Exception:  # noqa: BLE001 — одно странное сообщение не должно ронять приём
                    log.exception("Telegram: сообщение %s", u.get("update_id"))

    def _get_updates(self):
        """getUpdates -> список событий. Long polling 25 с (Telegram и server/tg); PHP-шлюз отвечает сразу (timeout 0).
        Отдельно от _call: нужен свой таймаут и пустой список вместо None."""
        url = self._url("getUpdates")
        body = {"offset": self.data.get("offset", 0), "timeout": 0 if self._php() else 25, "allowed_updates": self.ALLOWED}
        if self._php():
            body.update(self._node_params())          # сервер выбирает, какой компьютер аккаунта забирает сообщения
        try:
            r = self._http("POST", url, json=body, timeout=40, headers=self._hdr())
        except httpx.HTTPError as e:
            raise TelegramError(f"Telegram не отвечает: {e}") from e
        try:
            d = r.json()
        except ValueError as e:
            raise TelegramError(f"Telegram ответил {r.status_code}") from e
        if not d.get("ok"):
            if r.status_code == 401:
                raise TelegramAuthError(self._e401())
            if r.status_code == 409 and not self.shared():
                raise TelegramConflict("этого бота уже слушает другая программа (или второй Dewiar)")
            raise TelegramError(d.get("description") or f"ошибка {r.status_code}")
        dw = d.get("dewiar")
        if isinstance(dw, dict):                      # кто отвечает в боте (tg.php 03.11); старый сервер не присылает
            was = (self.main, self.who())
            self.main, self.nodes = bool(dw.get("main", True)), dw
            if was != (self.main, self.who()):
                if was[0] != self.main:
                    log.info("Telegram: %s", "этот компьютер теперь отвечает в боте" if self.main else "в боте отвечает другой компьютер")
                self.on_message("nodes", {"main": self.main})
        return d.get("result") or []

    def _handle(self, u):
        """Одно событие: нажатие кнопки, привязка владельца по коду, команда или вопрос (с вложениями) -> on_message."""
        if "callback_query" in u:
            q = u["callback_query"]
            if self._is_owner(q.get("from", {}).get("id")):
                try:
                    self._call("answerCallbackQuery", callback_query_id=q["id"])
                except TelegramError:
                    pass
                data = q.get("data") or ""
                if data.startswith("alarm:"):
                    self.on_message("alarm_cb", {"data": data})
                else:
                    self.on_message("confirm", {"ok": data == "yes"})
            return
        m = u.get("message")
        if not m:
            return
        chat, user = m.get("chat", {}), m.get("from", {})
        text = (m.get("text") or m.get("caption") or "").strip()
        if chat.get("type") != "private":
            return                                                   # в группах бот не работает — только лично
        if not self.paired():
            code = self.data.get("code", "")
            tok = text.split()[-1] if text else ""        # «/start КОД» из ссылки; цифры — код, набранный вручную
            if code and (tok == code or re.sub(r"\D", "", text) == code):
                name = " ".join(x for x in (user.get("first_name"), user.get("last_name")) if x) or user.get("username", "")
                with self._lock:
                    self.data["owner"] = {"id": user["id"], "chat": chat["id"], "name": name,
                                          "username": user.get("username", "")}
                    self.data.pop("code", None)
                    self._save()
                log.info("Telegram: владелец — %s", name)
                self.send("Готово! Теперь я ваш. " + self.HELP)
                self.on_message("paired", {"name": name})
            else:
                self._reply(chat["id"], f"Откройте ссылку из студии Dewiar («Подключение» → «{self.TITLE}» → «Открыть {self.TITLE}») "
                                        "или пришлите код оттуда, например: /start 123456")
            return
        if not self._is_owner(user.get("id")):
            if chat["id"] not in self._strangers:
                self._strangers.add(chat["id"])
                self._reply(chat["id"], "Это личный ассистент — он отвечает только своему владельцу.")
                log.info("Telegram: чужой пользователь %s (%s) — не отвечаю", user.get("id"), user.get("username"))
            return
        self.last_in = time.time()
        cmd = text.split()[0].split("@")[0].lower() if text.startswith("/") else ""
        if cmd in ("/start", "/help"):
            return self.send(self.HELP)
        if cmd == "/stop":
            return self.on_message("stop", {})
        if cmd == "/status":
            return self.on_message("status", {})
        try:
            files, voice = self._attachments(m)
        except TelegramError as e:
            return self.send(f"Не получилось взять вложение: {e}.")
        if not (text or files or voice):
            return self.send("Такое я пока не понимаю — пришлите текст, голосовое, фото или документ.")
        self.on_message("ask", {"text": text, "files": files, "voice": voice})

    def _attachments(self, m):
        """Скачать вложения сообщения -> (files [{name, data}], голосовое bytes или None).
        Из размеров фото берётся самый крупный."""
        files, voice = [], None
        if m.get("voice") or m.get("audio"):
            v = m.get("voice") or m.get("audio")
            voice = self.download(v["file_id"], v.get("file_size"))
        if m.get("photo"):
            ph = max(m["photo"], key=lambda p: p.get("file_size") or p.get("width", 0))
            files.append({"name": f"фото {time.strftime('%Y-%m-%d %H-%M-%S')}.jpg",
                          "data": self.download(ph["file_id"], ph.get("file_size"))})
        if m.get("document"):
            doc = m["document"]
            files.append({"name": doc.get("file_name") or "документ", "data": self.download(doc["file_id"], doc.get("file_size"))})
        return files, voice

    def _is_owner(self, uid):
        own = self.data.get("owner") or {}
        return bool(uid) and uid == own.get("id")

    def download(self, file_id, size=None):
        """Файл из сообщения -> bytes. Через getFile узнаём путь, затем скачиваем: у Telegram — /file/bot…,
        у PHP-шлюза — ?file=."""
        if size and size > MAX_FILE:
            raise TelegramError("файл больше 20 МБ — Telegram не отдаёт ботам такие файлы")
        f = self._call("getFile", file_id=file_id)
        try:
            if self._php():
                from urllib.parse import quote
                url = f"{self._api()}?file={quote(str(f['file_path']), safe='')}"
            else:
                url = f"{self._api()}/file/bot{'0' if self.shared() else self.data['token']}/{f['file_path']}"
            r = self._http("GET", url, timeout=60, headers=self._hdr())
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise TelegramError(f"файл не скачался: {e}") from e
        return r.content

    # ---------- отправка ----------

    def _reply(self, chat, text, buttons=None):
        """Отправить текст (несколькими сообщениями, если длинный); кнопки — под последним сообщением."""
        for i, part in enumerate(chunks(text)):
            params = {"chat_id": chat, "text": part, "disable_web_page_preview": True}
            if buttons and i == len(chunks(text)) - 1:
                params["reply_markup"] = {"inline_keyboard": [[{"text": t, "callback_data": d} for t, d in buttons]]}
            self._call("sendMessage", **params)

    def send(self, text, buttons=None):
        """Сообщение владельцу. Ошибку не бросаем — уведомление не должно ломать ответ дома."""
        own = self.data.get("owner") or {}
        if not own.get("chat") or not (text or "").strip():
            return False
        try:
            self._reply(own["chat"], text, buttons)
            return True
        except TelegramError as e:
            log.warning("Telegram: не отправилось: %s", e)
            self.problem = str(e)
            return False

    def ask_confirm(self, question):
        """Вопрос с кнопками «Да/Нет»; нажатие придёт в on_message("confirm", {"ok": …})."""
        return self.send(question, buttons=[("Да", "yes"), ("Нет", "no")])

    def typing(self):
        own = self.data.get("owner") or {}
        if own.get("chat"):
            try:
                self._call("sendChatAction", chat_id=own["chat"], action="typing", timeout=8)
            except TelegramError:
                pass

    def send_file(self, path, caption=""):
        """Отправить файл владельцу -> имя файла. Ограничения Bot API: файл до 50 МБ, фото до 10 МБ (больше —
        документом), подпись до 1024 символов."""
        own = self.data.get("owner") or {}
        if not own.get("chat"):
            raise TelegramError("Telegram не подключён к владельцу")
        p = Path(path)
        if p.stat().st_size > 50 * 1024 * 1024:
            raise TelegramError(f"{p.name} больше 50 МБ — Telegram такие файлы от ботов не принимает")
        photo = p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp") and p.stat().st_size < 10 * 1024 * 1024
        with p.open("rb") as fh:
            self._call("sendPhoto" if photo else "sendDocument", timeout=120, chat_id=own["chat"],
                       caption=caption[:1000], files={"photo" if photo else "document": (p.name, fh)})
        return p.name

    def send_voice(self, ogg: bytes, caption=""):
        """Голосовой ответ. Telegram показывает как голосовое только OGG/Opus; ошибку не бросаем, как и send()."""
        own = self.data.get("owner") or {}
        if not own.get("chat"):
            return False
        try:
            self._call("sendVoice", timeout=60, chat_id=own["chat"], caption=caption[:1000],
                       files={"voice": ("ответ.ogg", ogg, "audio/ogg")})
            return True
        except TelegramError as e:
            log.warning("Telegram: голосовое не отправилось: %s", e)
            return False

    def test(self):
        if not self.paired():
            raise TelegramError("сначала пришлите боту код из студии")
        if not self.send("Проверка связи: Dewiar на связи ✅"):
            raise TelegramError(self.problem or "сообщение не отправилось")
        return True
