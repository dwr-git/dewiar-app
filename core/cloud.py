"""Dewiar Облако: модели сервера Dewiar по ключу (dw-…) и «заряд» в талерах.

Ключ выдаёт администратор Dewiar и пополняет его баланс; вместо ключа можно войти аккаунтом сайта (connect(account=True)).
Программа ходит к моделям через cloud.php на сайте как к обычному OpenAI-совместимому серверу (адрес …/cloud.php?p= —
к нему приписывается /chat/completions): профиль модели "dewiar-cloud" в настройках llm. Человек видит не деньги,
а полосу заряда и сколько примерно ответов осталось. Серверная часть — server/dwrapp/cloud.php."""
import logging
import re
import threading
import time

import httpx

log = logging.getLogger("dewiar.cloud")
DEFAULT_URL = "https://dewiar.pro/dwrapp/cloud.php"
PROFILE_ID = "dewiar-cloud"
REFRESH = 600                       # заряд в фоне — раз в 10 минут
AFTER_TURN = 20                     # и через 20 с после ответа облачной модели (не чаще)


class CloudError(Exception):
    """Ошибка с понятным человеку текстом (из ответа облака)."""


def base_of(url):
    """Адрес облака в любом виде -> https://…/cloud.php без параметров (пусто — облако на dewiar.pro)."""
    u =(url or "").strip() or DEFAULT_URL
    u = u.split("?", 1)[0].rstrip("/")
    if not u.startswith(("http://", "https://")):
        u = "https://" + u
    if not u.endswith(".php"):
        u += "/cloud.php"
    return u


def api_base(url):
    """base_url для OpenAI-клиента: путь API (/chat/completions, /models…) окажется в параметре p."""
    return base_of(url) + "?p="


def is_cloud(profile):
    """Профиль модели ведёт в облако Dewiar? (флаг cloud или адрес вида cloud.php?p=)"""
    return bool(profile and (profile.get("cloud") or "cloud.php?p=" in (profile.get("base_url") or "")))


def norm_key(key):
    """Ключ из буфера обмена: без пробелов, переносов строк и кавычек; ключ dw- — в нижнем регистре."""
    k ="".join((key or "").split()).strip().strip("«»\"'")
    return k.lower() if k.lower().startswith("dw-") else k          # токен аккаунта сайта — как есть (регистр важен)


def fetch(url, key, path, timeout=10, body=None):
    """Запрос к облаку (GET, с body — POST) -> JSON-словарь. Ошибка — CloudError с текстом облака;
    нет связи — с подсказкой, что делать, если dewiar.pro блокирует провайдер."""
    try:
        h = {"Authorization": f"Bearer {norm_key(key)}"}
        r = httpx.post(api_base(url) + path, headers=h, json=body, timeout=timeout) if body is not None else \
            httpx.get(api_base(url) + path, headers=h, timeout=timeout)
    except httpx.ConnectError as e:
        from net import blocked_hint
        raise CloudError("нет связи с облаком Dewiar — проверьте интернет." + blocked_hint()) from e
    except httpx.TimeoutException as e:
        from net import blocked_hint
        raise CloudError("облако Dewiar не ответило вовремя." + blocked_hint()) from e
    try:
        d = r.json()
    except ValueError:
        d = {}
    if r.status_code >= 400 or not isinstance(d, dict):
        msg = ((d.get("error") or {}).get("message") if isinstance(d, dict) and isinstance(d.get("error"), dict) else "") or \
            f"облако ответило ошибкой {r.status_code}"
        raise CloudError(msg)
    return d


def public(url, path, body=None, timeout=20):
    """Запрос к облаку без ключа (заявка на доступ, код другого устройства) -> JSON; ошибка — CloudError с текстом облака."""
    try:
        r = httpx.post(api_base(url) + path, json=body, timeout=timeout) if body is not None else httpx.get(api_base(url) + path, timeout=timeout)
    except httpx.HTTPError as e:
        from net import blocked_hint
        raise CloudError("нет связи с облаком Dewiar — проверьте интернет." + blocked_hint()) from e
    try:
        d = r.json()
    except ValueError:
        d = {}
    if r.status_code >= 400 or not isinstance(d, dict):
        msg = ((d.get("error") or {}).get("message") if isinstance(d, dict) and isinstance(d.get("error"), dict) else "") or \
            f"облако ответило ошибкой {r.status_code}"
        raise CloudError(msg)
    return d


def join_send(url, name, contact, note="", device="компьютер", auto=False):
    """Заявка на модели Dewiar без регистрации (cloud.php ?p=/join) -> {id, secret, status: new|ok, key?, text}.
    auto — автоподключение при первом запуске (0.69): без контакта, сайт одобряет сам."""
    body = {"name": name, "contact": contact, "note": note, "device": device}
    if auto:
        body["auto"] = 1
    return public(url, "/join", body)


def join_status(url, jid, secret):
    """Что с заявкой -> {status: new|ok|no, key?, reply, text}."""
    import urllib.parse
    return public(url, f"/join&id={int(jid)}&s={urllib.parse.quote(str(secret))}")


def pair_claim(url, code):
    """Код из 6 цифр с другого устройства -> ключ dw- того устройства."""
    return public(url, "/pair/claim", {"code": re.sub(r"\D", "", str(code))}).get("key", "")


def key_gone(e):
    """Ключ dw- удалён или перевыпущен на сайте (облако его не знает)? Узнаём по тексту ошибки cloud.php."""
    return bool(re.search(r"ключ dewiar не найден|invalid_api_key|ключ отозван", str(e), re.I))


class Cloud:
    """Подключение к облаку и заряд. Ключ и адрес — в настройках (cloud.key, cloud.url); заряд — в памяти,
    обновляется фоном (loop) и после ответов облачной модели; каждое обновление уходит в студию событием "cloud"."""

    def __init__(self, settings, emit):
        self.s, self.emit = settings, emit
        self.info, self.at, self.error = None, 0.0, ""
        self._lock = threading.Lock()
        self._next = 0.0
        self._stop = threading.Event()
        self.on_low = None              # (info) -> None: заряд стал «мало» или кончился — напомнить в мессенджер
        self.on_key_gone = None         # () -> None: ключ dw- удалили на сайте — перейти на аккаунт, если вошли (engine_brain)

    # ---------- ключ ----------
    @property
    def key(self):
        return (self.s.get("cloud", "key") or "").strip()

    @property
    def url(self):
        return self.s.get("cloud", "url") or DEFAULT_URL

    def connect(self, key, url="", account=False, activate=True):
        """Ключ dw-… или (account=True) токен входа аккаунта сайта: облако узнаёт пользователя сайта и даёт ему свой заряд.
        Проверяет ключ (/balance, /models), создаёт профиль модели с первой моделью из списка и (activate) делает его
        активным -> status() + выбранная модель. Ответ /models заодно говорит, есть ли в облаке распознавание речи."""
        key, url = norm_key(key), (url or "").strip() or self.url
        if not account and key and key == norm_key(self.key) and self.s.get("cloud", "account"):
            account = True                     # переподключение тем же входом аккаунтом («Отвечать моделями Dewiar»)
        if not account and not key.startswith("dw-"):
            raise CloudError("это не ключ Dewiar: он начинается с dw-. Вошли аккаунтом dewiar.pro — ключ не нужен")
        info = fetch(url, key, "/balance")
        md = fetch(url, key, "/models")
        models = md.get("data") or []
        if not models:
            raise CloudError("в облаке пока нет доступных моделей — напишите администратору")
        m = models[0]
        prof = {"name": "Dewiar Облако", "kind": "openai", "base_url": api_base(url), "api_key": key, "model": m["id"],
                "cloud": True, "title": m.get("title") or m["id"]}
        profiles = dict(self.s.get("llm", "profiles") or {})
        profiles[PROFILE_ID] = prof
        llm = {"profiles": profiles}
        if activate:
            llm["active"] = PROFILE_ID
        self.s.update({"llm": llm, "cloud": {"key": key, "url": base_of(url), "account": bool(account), "stt_ok": bool(md.get("stt")), "tts_ok": bool(md.get("tts"))}})
        self._set(info)
        log.info("☁ Подключён ключ Dewiar Облака …%s (%s): заряд %s%%", key[-4:], info.get("label"), info.get("percent"))
        return dict(self.status(), model=m["id"], title=prof["title"], profile=PROFILE_ID)

    def stt_is_cloud(self):
        """Распознавание речи идёт через облако (set_stt(True))? Без ключа оно работать не будет."""
        return self.s.get("stt", "engine") == "remote" and bool(self.s.get("stt", "remote", "cloud"))

    def forget(self, stt_local=""):
        """Отключить облако: убрать ключ и профиль модели; был активным — активным станет первый оставшийся профиль.
        Распознавание через облако без ключа сломается: с stt_local (имя своего движка) переключает его на него само
        (в ответе stt_reset=True — движки надо перезапустить), иначе отдаёт stt_cloud=True — вызывающий переключает сам
        (ему известен движок для этого компьютера). -> status() + stt_cloud, stt_reset."""
        profiles = dict(self.s.get("llm", "profiles") or {})
        profiles.pop(PROFILE_ID, None)
        active = self.s.get("llm", "active")
        patch = {"llm": {"profiles": profiles}, "cloud": {"key": "", "account": False}}
        if active == PROFILE_ID:
            patch["llm"]["active"] = next(iter(profiles), "")
        stt_cloud, stt_reset = self.stt_is_cloud(), False
        if stt_cloud and stt_local:
            patch["stt"] = {"engine": stt_local, "remote": {"cloud": False, "api_key": ""}}   # ключа больше нет — не храним его копию
            stt_cloud, stt_reset = False, True
        self.s.update(patch)
        self.info, self.error = None, ""
        self.emit("cloud", connected=False)
        return dict(self.status(), stt_cloud=stt_cloud, stt_reset=stt_reset)

    # ---------- заряд ----------
    def _set(self, info):
        """Новый заряд: сразу в студию. on_low — только при переходе в «мало» или «пусто», если облако — активная
        модель, и не при первом получении после запуска (иначе напоминание приходило бы при каждом старте)."""
        prev = self.info or {}
        self.info, self.at, self.error = info, time.monotonic(), ""
        self.emit("cloud", **self.status())
        newly = (info.get("empty") and not prev.get("empty")) or (info.get("low") and not prev.get("low") and not info.get("empty"))
        if prev and newly and self.on_low and self.s.get("llm", "active") == PROFILE_ID:
            try:
                self.on_low(info)
            except Exception:  # noqa: BLE001
                log.exception("облако: напоминание о заряде")

    # ---------- расход, пополнение, модели, распознавание ----------
    def usage(self):
        return fetch(self.url, self.key, "/usage") if self.key else {"days": []}

    def topup_info(self):
        return fetch(self.url, self.key, "/topup") if self.key else {}

    def topup_request(self, amount=0, note="", image=""):
        """Заявка «я оплатил»: сумма, комментарий, снимок оплаты (data:image/…;base64,…). Администратор проверит и зачислит."""
        if not self.key:
            raise CloudError("сначала подключите ключ Dewiar")
        r = fetch(self.url, self.key, "/topup", timeout=40, body={"amount": amount, "note": note, "image": image})
        log.info("☁ Заявка на пополнение №%s отправлена", r.get("id"))
        return r

    def models(self):
        return fetch(self.url, self.key, "/models") if self.key else {"data": []}

    def set_model(self, mid):
        profiles = dict(self.s.get("llm", "profiles") or {})
        prof = profiles.get(PROFILE_ID)
        if not prof:
            raise CloudError("облако не подключено")
        m = next((x for x in self.models().get("data") or [] if x["id"] == mid), None)
        if not m:
            raise CloudError("такой модели в облаке нет")
        prof.update(model=m["id"], title=m.get("title") or m["id"])
        self.s.update({"llm": {"profiles": profiles}})
        return prof

    def set_stt(self, on):
        """Распознавание речи через облако (для слабых компьютеров) — или снова своё (GigaAM)."""
        if on:
            if not self.key:
                raise CloudError("сначала подключите ключ Dewiar")
            self.s.update({"stt": {"engine": "remote", "remote": {"base_url": api_base(self.url), "api_key": self.key, "model": "gigaam",
                                                                  "language": "ru", "cloud": True}}})
        else:
            self.s.update({"stt": {"engine": "gigaam", "remote": {"cloud": False}}})
        return self.s.get("stt")

    def set_tts(self, on, local="vosk"):
        """«Голос Dewiar»: говорит облако — те же голоса, что у телефона («Голос Dewiar»), у каждого персонажа свой
        (voice.remote: serena, aiden…). Облако отдаёт WAV целиком (cloud.php proxy_tts), поэтому extra — wav без потока.
        Выключить — снова свой голос (local)."""
        if on:
            if not self.key:
                raise CloudError("сначала подключите ключ Dewiar или войдите аккаунтом")
            self.s.update({"tts": {"engine": "remote", "remote": {"base_url": api_base(self.url), "api_key": self.key, "model": "tts-1",
                                                                  "sample_rate": 24000, "voice_f": "", "voice_m": "",
                                                                  "extra": {"response_format": "wav", "stream": False},
                                                                  "cloud": True, "from_account": True}}})
        else:
            self.s.update({"tts": {"engine": local, "remote": {"cloud": False, "from_account": False, "extra": {}}}})
        return self.s.get("tts")

    def refresh(self):
        """Узнать заряд сейчас -> status(). Ключ dw- больше не действует (и вход не по аккаунту) — on_key_gone
        в отдельном потоке: переход на аккаунт идёт по сети и не должен держать вызывающего."""
        if not self.key:
            return self.status()
        gone = False
        with self._lock:
            try:
                self._set(fetch(self.url, self.key, "/balance"))
            except CloudError as e:
                self.error, self.at = str(e), time.monotonic()
                log.info("☁ Заряд не узнал: %s", e)
                gone = key_gone(e) and not self.s.get("cloud", "account") and self.on_key_gone
        if gone:
            threading.Thread(target=self.on_key_gone, daemon=True).start()
        elif self.error:
            self.emit("cloud", **self.status())
        return self.status()

    def status(self, refresh=False):
        """Состояние для студии. Устарело (REFRESH) или ещё неизвестно — обновляется в фоне; refresh=True — сразу.
        От ключа dw- показываем только 4 последних знака, от токена аккаунта — ничего."""
        if not self.key:
            return {"connected": False, "url": self.url}
        if refresh or (self.info is None and not self.error) or time.monotonic() - self.at > REFRESH:
            threading.Thread(target=self.refresh, daemon=True).start() if not refresh else self.refresh()
        d = {"connected": True, "url": self.url, "tail": "" if self.s.get("cloud", "account") else self.key[-4:], "error": self.error,
             "active": (self.s.get("llm", "active") == PROFILE_ID), "account": bool(self.s.get("cloud", "account"))}
        d.update(self.info or {})
        return d

    def after_turn(self, profile):
        """Ответила облачная модель — через ~20 с узнаём новый заряд (виджет предупредит, если мало)."""
        if not is_cloud(profile) or not self.key:
            return
        now = time.monotonic()
        if now < self._next:
            return
        self._next = now + AFTER_TURN
        threading.Timer(AFTER_TURN, self.refresh).start()

    def loop(self):
        """Фоновая проверка заряда раз в REFRESH секунд (поток запускает engine.py)."""
        while not self._stop.wait(REFRESH):
            if self.key:
                self.refresh()
