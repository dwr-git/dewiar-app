"""Сеть Dewiar: прокси только для серверов Dewiar (dewiar.pro, его поддомены и свой сайт из аккаунта/облака/обновлений).
Бывает, что провайдер блокирует dewiar.pro — тогда вход, облако, Знания, речь на сервере, обновления и модели идут
через прокси, а всё остальное (свой сервер моделей, радио, поиск) — напрямую. У Telegram свой прокси (telegram.py).

Как: httpx для каждого запроса выбирает «транспорт» по адресу (mounts). install() (из main.py) подменяет
httpx.Client.__init__ и добавляет каждому клиенту транспорт через прокси для адресов Dewiar — так это работает во всех
модулях сразу, включая httpx.get/post/stream (они создают Client внутри). httpx.AsyncClient не затронут.
Настройки берутся при создании клиента из bind(provider) — смена прокси действует со следующего запроса.
check() — проверка связи для студии: напрямую и через прокси.

Дома — напрямую (set_lan): сайт Dewiar стоит дома, а снаружи к нему ходят по имени через прокси или VPN; дома так медленно
(ответ модели — минута вместо секунд), а то и вовсе не открывается. Сайт сообщает внутренний адрес своей папки
(cloud.php ?p=/lan: http://192.168.x.x:порт/dwrapp/ и метку). Запросы к той же папке по имени (https://dewiar.pro/dwrapp/…)
идут на внутренний адрес, если он отвечает и это именно наш сайт (подпись метки на случайное число — чужой сервер с тем же
адресом в другой сети ответить так не сможет). Не отвечает — как обычно (прокси или напрямую); проверка — не чаще раза в
LAN_OK_SEC, неудача — снова не раньше чем через LAN_BAD_SEC."""
import logging
import threading
import time
from urllib.parse import parse_qs, quote, urlparse

import httpx

log = logging.getLogger("dewiar.net")

BASE_HOSTS = ("dewiar.pro",)
RETRIES = 3                            # прокси нередко пускает «не с первого раза» — сколько раз повторить
BACKOFF = (0.4, 1.2, 2.5)              # паузы между повторами, секунды
DIRECT_SEC = 900                       # прокси подвёл, а напрямую работает — столько секунд ходим напрямую
_state = {"proxy": "", "hosts": BASE_HOSTS, "provider": None}
_direct_ok = {}                        # адрес -> до какого времени ходить к нему напрямую
_tl = threading.local()                # _tl.off = True — клиенты этого потока без прокси (на время check())
_orig_init = httpx.Client.__init__
_installed = False
LAN_OK_SEC, LAN_BAD_SEC, LAN_TIMEOUT = 300, 180, 1.5
_lan = {"public": "", "base": "", "id": "", "ok_until": 0.0, "bad_until": 0.0, "lock": threading.Lock()}


def set_lan(public="", base="", lid=""):
    """Папка сайта по имени (https://dewiar.pro/dwrapp/) и она же в домашней сети (http://192.168.1.46:9099/dwrapp/) с меткой
    сайта; пусто — выключить. Новый адрес проверяется заново при первом запросе."""
    public, base = (public or "").strip(), (base or "").strip()
    if public and not public.endswith("/"):
        public += "/"
    if base and not base.endswith("/"):
        base += "/"
    if (public, base, lid or "") != (_lan["public"], _lan["base"], _lan["id"]):
        _lan.update(public=public if base and lid else "", base=base if public and lid else "", id=lid or "", ok_until=0.0, bad_until=0.0)
        if _lan["base"]:
            log.info("Дома — напрямую: %s → %s (если отвечает)", public, base)


def lan_status():
    """Для студии и проверок: {"base", "ok"} — ok: последняя проверка прошла (дома, ходим напрямую)."""
    return {"base": _lan["base"], "ok": bool(_lan["base"]) and time.time() < _lan["ok_until"]}


def _lan_ok():
    """Отвечает ли внутренний адрес и наш ли это сайт. Кэш: да — LAN_OK_SEC, нет — LAN_BAD_SEC."""
    if not _lan["base"]:
        return False
    now = time.time()
    if now < _lan["ok_until"]:
        return True
    if now < _lan["bad_until"]:
        return False
    with _lan["lock"]:
        if time.time() < _lan["ok_until"]:
            return True
        if time.time() < _lan["bad_until"]:
            return False
        import hashlib
        import hmac
        import secrets
        n = secrets.token_hex(16)
        ok = False
        try:
            with httpx.HTTPTransport(retries=0) as t:
                r = t.handle_request(httpx.Request("GET", _lan["base"] + f"cloud.php?p=/lan&n={n}",
                                                   extensions={"timeout": {"connect": LAN_TIMEOUT, "read": 4, "write": 4, "pool": 4}}))
                r.read()
            want = hmac.new(_lan["id"].encode(), n.encode(), hashlib.sha256).hexdigest()
            ok = r.status_code == 200 and hmac.compare_digest(str((r.json() or {}).get("h") or ""), want)
        except Exception:  # noqa: BLE001 — не дома, адрес не отвечает, ответил не наш сервер
            ok = False
        if ok:
            if time.time() >= _lan["ok_until"] and _lan["ok_until"] == 0:
                log.info("Дома: сайт отвечает напрямую (%s) — хожу к нему без прокси", _lan["base"])
            _lan["ok_until"], _lan["bad_until"] = time.time() + LAN_OK_SEC, 0.0
        else:
            _lan["ok_until"], _lan["bad_until"] = 0.0, time.time() + LAN_BAD_SEC
        return ok


class _LanFirst(httpx.BaseTransport):
    """Адреса папки сайта — сначала на внутренний адрес (дома), иначе — inner (прокси или напрямую)."""

    def __init__(self, inner, verify, cert):
        self.inner, self.verify, self.cert, self.t = inner, verify, cert, None

    def handle_request(self, request):
        url = str(request.url)
        pub = _lan["public"]
        if pub and url.startswith(pub) and _lan_ok():
            new = _lan["base"] + url[len(pub):]
            nu = httpx.URL(new)
            headers = [(b"Host", nu.netloc)] + [(k, v) for k, v in request.headers.raw if k.lower() != b"host"]
            req = httpx.Request(request.method, nu, headers=headers, stream=request.stream, extensions=request.extensions)
            if self.t is None:
                self.t = httpx.HTTPTransport(verify=self.verify, cert=self.cert)
            try:
                return self.t.handle_request(req)
            except (httpx.ConnectError, httpx.ConnectTimeout):
                _lan["ok_until"], _lan["bad_until"] = 0.0, time.time() + LAN_BAD_SEC    # ушли из дома — как обычно
        return self.inner.handle_request(request)

    def close(self):
        for x in (self.t, self.inner):
            if x is not None:
                x.close()


def _private_host(host):
    """Этот компьютер или своя сеть: localhost, *.local/*.lan, 127.*, 10.*, 192.168.*, 172.16–31.*, 169.254.*, ::1, fc00::/7."""
    import ipaddress
    h = (host or "").strip("[]").lower()
    if h in ("localhost",) or h.endswith((".local", ".lan", ".localdomain", ".home.arpa")):
        return True
    try:
        ip = ipaddress.ip_address(h)
    except ValueError:
        return False
    return ip.is_private or ip.is_loopback or ip.is_link_local


class _SysProxy(httpx.BaseTransport):
    """Прокси системы (Windows: «Параметры → Сеть → Прокси», переменные HTTP(S)_PROXY) — для интернета, а к своей модели
    на этом компьютере и в своей сети — напрямую (№358, 27.10: «пока включено прокси на компьютере, локальная модель не
    подключается»: httpx слал запрос к localhost:11434 на прокси, а у прокси свой localhost). Как «Не использовать
    прокси для локальных адресов» в Windows."""

    def __init__(self, env_mounts, verify, cert):
        from httpx._utils import URLPattern
        self.pats = sorted(((URLPattern(k), v) for k, v in env_mounts.items()), key=lambda kv: kv[0])   # как у httpx: точнее — раньше
        self.verify, self.cert, self.t, self.d = verify, cert, {}, None

    def _direct(self):
        if self.d is None:
            self.d = httpx.HTTPTransport(verify=self.verify, cert=self.cert, trust_env=False)
        return self.d

    def handle_request(self, request):
        host = request.url.host
        px = None
        if not _private_host(host):
            for pat, val in self.pats:
                if pat.matches(request.url):
                    px = val
                    break
        if not px:
            return self._direct().handle_request(request)
        if px not in self.t:
            self.t[px] = httpx.HTTPTransport(proxy=px, verify=self.verify, cert=self.cert, trust_env=False)
        return self.t[px].handle_request(request)

    def close(self):
        for x in list(self.t.values()) + [self.d]:
            if x is not None:
                x.close()


def _env_proxies():
    """Прокси из окружения и системы, как их видит httpx: {шаблон: прокси | None (без прокси)}."""
    try:
        from httpx._utils import get_environment_proxies
        return get_environment_proxies()
    except Exception:  # noqa: BLE001
        return {}


class _Plain(httpx.BaseTransport):
    """Обычный путь (без прокси) — создаётся при первом запросе, как у httpx по умолчанию."""

    def __init__(self, verify, cert, trust_env):
        self.verify, self.cert, self.trust_env, self.t = verify, cert, trust_env, None

    def handle_request(self, request):
        if self.t is None:
            self.t = httpx.HTTPTransport(verify=self.verify, cert=self.cert, trust_env=self.trust_env)
        return self.t.handle_request(request)

    def close(self):
        if self.t is not None:
            self.t.close()


class NetError(Exception):
    pass


def normalize_proxy(text):
    """socks5://user:pass@host:1080, http://host:3128, host:port (HTTP), ссылка tg://socks?… или t.me/socks?… -> адрес прокси
    ("" — без прокси). socks:// понимается как socks5://. MTProto-прокси (tg://proxy?…secret=…) — только для приложения
    Telegram: программам он не подходит, на него — NetError с объяснением. Общий разбор и для Telegram (telegram.py)."""
    t = (text or "").strip()
    if not t:
        return ""
    low = t.lower()
    if low.startswith(("tg://socks", "https://t.me/socks", "http://t.me/socks", "t.me/socks")):
        q = parse_qs(urlparse(t if "://" in t else "https://" + t).query)
        host, port = (q.get("server") or [""])[0], (q.get("port") or ["1080"])[0]
        if not host:
            raise NetError("в ссылке нет адреса прокси (server=…)")
        user, pw = (q.get("user") or [""])[0], (q.get("pass") or [""])[0]
        cred = f"{quote(user, safe='')}:{quote(pw, safe='')}@" if user else ""
        return f"socks5://{cred}{host}:{port}"
    if low.startswith(("tg://proxy", "https://t.me/proxy", "http://t.me/proxy", "t.me/proxy")) or "secret=" in low:
        raise NetError("это MTProto-прокси — он работает только в приложении Telegram. Нужен SOCKS5- или "
                       "HTTP-прокси (socks5://адрес:порт) или VPN на компьютере")
    if "://" not in t:
        t = "http://" + t
    u = urlparse(t)
    if u.scheme.lower() not in ("http", "https", "socks5", "socks5h", "socks"):
        raise NetError("прокси — socks5://адрес:порт или http://адрес:порт")
    if u.scheme.lower() == "socks":
        t = "socks5" + t[len(u.scheme):]
    try:
        port = u.port
    except ValueError:
        port = None
    if not u.hostname or not port:
        raise NetError("у прокси нужен адрес и порт, например socks5://192.168.1.10:1080")
    return t


def hide(px):
    """Прокси для показа и журнала: пароль заменён точками."""
    import re
    return re.sub(r"//([^:/@]+):[^@]*@", r"//\1:•••@", px or "")


def host_of(url):
    try:
        return (urlparse(url if "://" in (url or "") else "https://" + (url or "")).hostname or "").lower()
    except ValueError:
        return ""


def _hosts(extra):
    """dewiar.pro + дополнительные адреса (ссылки или имена) -> кортеж имён. Свой компьютер через прокси не пускаем."""
    hosts = list(BASE_HOSTS)
    for h in extra or ():
        h = host_of(h) if "/" in (h or "") or ":" in (h or "") else (h or "").lower().strip(".")
        if h and h not in ("localhost", "127.0.0.1", "::1") and h not in hosts:
            hosts.append(h)
    return tuple(hosts)


def configure(proxy="", extra_hosts=()):
    """Прокси для серверов Dewiar ("" — напрямую) и дополнительные адреса (свой сайт, свой сервер облака).
    Отменяет bind(): дальше действуют эти постоянные значения."""
    _state.update(proxy=proxy or "", hosts=_hosts(extra_hosts), provider=None)


def bind(provider):
    """provider() -> (прокси, [адреса]) — читается при создании каждого httpx.Client: смена настроек действует сразу
    (engine.py передаёт сюда чтение настроек)."""
    _state["provider"] = provider


def current():
    """-> (прокси, адреса Dewiar). Если provider упал — последние значения из configure()."""
    f = _state.get("provider")
    if f:
        try:
            px, extra = f()
            return px or "", _hosts(extra)
        except Exception:  # noqa: BLE001
            log.debug("net: настройки не прочитались", exc_info=True)
    return _state["proxy"], _state["hosts"]


def uses_proxy(url):
    """Пойдёт ли этот адрес через прокси: сам адрес Dewiar или его поддомен."""
    px, hosts = current()
    if not px:
        return False
    h = host_of(url)
    return any(h == d or h.endswith("." + d) for d in hosts)


class _Lazy(httpx.BaseTransport):
    """Транспорт через прокси, который создаётся только при первом запросе (обычные запросы не платят за него)."""

    def __init__(self, proxy, verify, cert):
        self.proxy, self.verify, self.cert, self.t, self.d = proxy, verify, cert, None, None

    def _direct(self, request):
        if self.d is None:
            self.d = httpx.HTTPTransport(verify=self.verify, cert=self.cert)
        return self.d.handle_request(request)

    def handle_request(self, request):
        """Прокси не пускает к серверу Dewiar (403, обрыв TLS, молчит), а напрямую сервер доступен — идём напрямую и
        помним это DIRECT_SEC: прокси нужен только там, где dewiar.pro заблокирован, а не чтобы ломать связь там, где нет."""
        if time.time() < _direct_ok.get(request.url.host, 0):
            try:
                return self._direct(request)
            except (httpx.ConnectError, httpx.ConnectTimeout):
                _direct_ok.pop(request.url.host, None)            # напрямую перестало — снова через прокси
        try:
            return self._via_proxy(request)
        except (httpx.ProxyError, httpx.ConnectError, httpx.ConnectTimeout) as e:
            try:
                r = self._direct(request)                        # до сервера через прокси ничего не дошло — повтор безопасен
            except (httpx.ConnectError, httpx.ConnectTimeout):
                raise e from None
            _direct_ok[request.url.host] = time.time() + DIRECT_SEC
            log.info("Прокси не пускает к %s (%s), а напрямую связь есть — хожу напрямую", request.url.host, e or type(e).__name__)
            return r

    def _via_proxy(self, request):
        """Платные и общие прокси нередко отвечают на соединение «502 Bad Gateway» или обрывают его — со второго-третьего
        раза проходит. Повторяем сами, пока запрос не ушёл дальше прокси (до сервера ничего не дошло — повтор безопасен);
        чтение ответа оборвалось — повторяем только запросы без последствий (GET/HEAD)."""
        if self.t is None:
            self.t = httpx.HTTPTransport(proxy=self.proxy, verify=self.verify, cert=self.cert)
        safe = request.method in ("GET", "HEAD", "OPTIONS")
        for attempt in range(RETRIES + 1):
            try:
                return self.t.handle_request(request)
            except (httpx.ProxyError, httpx.ConnectError, httpx.ConnectTimeout) as e:
                if attempt >= (1 if isinstance(e, httpx.ConnectTimeout) else RETRIES):   # молчащий прокси — один повтор (каждый ждёт таймаут)
                    raise
                log.info("Прокси: %s — повтор %d (%s)", e or type(e).__name__, attempt + 1, request.url.host)
            except (httpx.RemoteProtocolError, httpx.ReadError) as e:
                if not safe or attempt >= RETRIES:
                    raise
                log.info("Прокси оборвал ответ (%s) — повтор %d", e or type(e).__name__, attempt + 1)
            time.sleep(BACKOFF[min(attempt, len(BACKOFF) - 1)])

    def close(self):
        for x in (self.t, self.d):
            if x is not None:
                x.close()


def _patched_init(self, *a, **kw):
    """Замена httpx.Client.__init__: адреса Dewiar (и их поддомены) — через прокси.
    mounts, переданные вызывающим явно, важнее наших."""
    off = getattr(_tl, "off", False)
    px, hosts = current() if not off else ("", ())
    m = {}
    if px:
        t = _Lazy(px, kw.get("verify", True), kw.get("cert"))
        for h in hosts:
            m[f"all://{h}"] = t
            m[f"all://*.{h}"] = t
    lh = host_of(_lan["public"]) if _lan["base"] and not off else ""
    if lh:                                            # дома — к папке сайта напрямую (остальное — как выше)
        inner = m.get(f"all://{lh}") or _Plain(kw.get("verify", True), kw.get("cert"), kw.get("trust_env", True))
        m[f"all://{lh}"] = _LanFirst(inner, kw.get("verify", True), kw.get("cert"))
    if kw.get("trust_env", True) and not kw.get("proxy") and "transport" not in kw:
        env = _env_proxies()
        if any(v for v in env.values()):              # прокси системы есть — свои адреса мимо него
            sp = _SysProxy(env, kw.get("verify", True), kw.get("cert"))
            m.setdefault("http://", sp)
            m.setdefault("https://", sp)
    if m:
        kw["mounts"] = {**m, **dict(kw.get("mounts") or {})}
    _orig_init(self, *a, **kw)


def install():
    """Подменить httpx.Client.__init__ — один раз при запуске ядра (main.py); повторный вызов ничего не делает.
    И сертификаты — из хранилища системы (trust_system)."""
    global _installed
    if not _installed:
        trust_system()
        httpx.Client.__init__ = _patched_init
        _installed = True


def trust_system():
    """Проверять сертификаты сайтов по хранилищу системы (Windows, macOS, Linux), а не только по встроенному списку.
    Антивирусы с проверкой защищённых соединений (Касперский, ESET) и корпоративные шлюзы подменяют сертификат своим —
    его корень есть в системе, но не во встроенном списке Python: «CERTIFICATE_VERIFY_FAILED … self-signed certificate
    in certificate chain», и не работало ничего — вход, облако, обновления, модели (пакеты 22–23.10, №156, №168, №169,
    №207). Проверка не слабеет: доверяем тому же, чему доверяет браузер этого компьютера. -> True, если включено."""
    try:
        import truststore
        truststore.inject_into_ssl()
        return True
    except Exception as e:  # noqa: BLE001 — нет библиотеки (старая установка) — как раньше, встроенный список
        log.info("Сертификаты — встроенный список (хранилище системы недоступно: %s)", e)
        return False


def _probe_once(url, proxy, timeout):
    """Проверка одного пути -> (ок, текст). Через прокси повторяем при его типичных сбоях, как и _Lazy."""
    for attempt in range(RETRIES + 1 if proxy else 1):      # прокси «не с первого раза» — проверка тоже повторяет
        res = _probe_try(url, proxy, timeout)
        if res[0] or not proxy or not res[1].startswith(("прокси не пускает", "соединение отклонено", "ответ 5")):
            return res
        time.sleep(BACKOFF[min(attempt, len(BACKOFF) - 1)])
    return res


def _probe_try(url, proxy, timeout):
    """Одна попытка GET -> (ок, текст для человека). Ок — любой ответ ниже 500: сервер достижим.
    _tl.off отключает наш общий прокси, чтобы «напрямую» значило напрямую. Ошибки переводятся в понятные
    признаки блокировки (DNS не находит адрес, подменённый сертификат)."""
    _tl.off = True
    try:
        kw = {"timeout": timeout, "follow_redirects": True, "headers": {"User-Agent": "Dewiar net check", "Cache-Control": "no-cache"}}
        if proxy:
            kw["mounts"] = {"all://": httpx.HTTPTransport(proxy=proxy)}
        else:
            kw["trust_env"] = False                          # «напрямую» — без системного прокси
        with httpx.Client(**kw) as c:
            r = c.get(url)
        return r.status_code < 500, f"ответ {r.status_code}"
    except httpx.ProxyError as e:
        return False, f"прокси не пускает: {e}"
    except httpx.ConnectTimeout:
        return False, "нет ответа (время вышло)"
    except httpx.ConnectError as e:
        s = str(e)
        if "Name or service" in s or "getaddrinfo" in s or "nodename" in s or "No address" in s:
            return False, "адрес не находится (DNS) — похоже на блокировку провайдером"
        if "refused" in s.lower():
            return False, "соединение отклонено"
        if "SSL" in s or "certificate" in s.lower():
            return False, "подменён защищённый канал (сертификат) — похоже на блокировку провайдером"
        return False, s[:160] or "нет соединения"
    except httpx.TimeoutException:
        return False, "нет ответа (время вышло)"
    except ImportError:
        return False, "для SOCKS-прокси не хватает модуля socksio — переустановите Dewiar"
    except Exception as e:  # noqa: BLE001
        return False, str(e)[:160]
    finally:
        _tl.off = False


def check(url, proxy="", timeout=8.0):
    """Проверка связи с сервером Dewiar: напрямую и (если задан) через прокси.
    -> {"direct": [ок, текст], "proxy": [ок, текст] | None, "advice": текст}"""
    d = _probe_once(url, "", timeout)
    p = _probe_once(url, proxy, timeout) if proxy else None
    host = host_of(url) or url
    if d[0] and (p is None or p[0]):
        advice = f"{host} открывается напрямую" + (" и через прокси." if p else ".")
    elif p and p[0]:
        advice = f"Напрямую {host} недоступен ({d[1]}), через прокси — работает. Dewiar ходит к нему через прокси."
    elif p:
        advice = f"Не открывается ни напрямую ({d[1]}), ни через прокси ({p[1]}). Проверьте адрес и порт прокси или включите VPN."
    else:
        advice = (f"{host} не открывается ({d[1]}). Если у вас его блокирует провайдер — укажите прокси (socks5://адрес:порт "
                  "или http://адрес:порт) или включите VPN.")
    return {"direct": list(d), "proxy": list(p) if p else None, "advice": advice}


def blocked_hint():
    """Добавка к сообщению «нет связи с сервером Dewiar»: что делать, если сайт блокирует провайдер."""
    px, _ = current()
    if px:
        return f" Сейчас Dewiar ходит туда через прокси {hide(px)} — проверьте, что он работает (студия → «Dewiar.pro» → «Компьютер, сеть…» → «Сеть»)."
    return " Если dewiar.pro у вас блокирует провайдер — укажите прокси: студия → «Dewiar.pro» → «Компьютер, сеть…» → «Сеть»."



LOCAL_HOSTS = ("127.0.0.1", "localhost", "0.0.0.0", "::1")


def my_lan_ip():
    """Адрес этого компьютера в домашней сети (192.168…, 10.…) или "" — без отправки пакетов."""
    import ipaddress
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 9))                  # пакет не уходит: так система называет адрес основной сети
            ip = s.getsockname()[0]
        return ip if ipaddress.ip_address(ip).is_private and not ip.startswith(("127.", "172.17.")) else ""
    except (OSError, ValueError):
        return ""


def lan_url(url, ip=None):
    """Адрес модели «на этом компьютере» (http://127.0.0.1:1234/v1) — для другого устройства в той же сети:
    http://192.168.1.5:1234/v1. 19.10: телефон по QR получил 127.0.0.1 — это он сам, и 16 раз «Failed to connect».
    -> (адрес, был ли локальный). Не локальный — как есть; локальный, а адреса сети нет — как есть, True."""
    u = urlparse(url or "")
    if (u.hostname or "") not in LOCAL_HOSTS:
        return url, False
    ip = my_lan_ip() if ip is None else ip
    if not ip:
        return url, True
    return u._replace(netloc=ip + (f":{u.port}" if u.port else "")).geturl(), True
