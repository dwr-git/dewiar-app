"""Home Assistant — второй умный дом рядом с Яндексом (smarthome.py): тот же разбор фраз и тот же поиск устройств.

Подключение: адрес Home Assistant (http://homeassistant.local:8123 или http://192.168.1.20:8123) и долгосрочный токен
(в HA: профиль → вкладка «Безопасность» → «Долгосрочные токены доступа» → «Создать токен»). Дальше голосом, без модели:
«включи свет в спальне», «свет на кухне на 30 процентов», «сделай свет теплее», «кондиционер на 22», «закрой шторы»,
«запусти сценарий спокойной ночи», «какая температура в спальне».

Как устроено: HAHome наследует smarthome.Home — info() приводит сущности HA к виду устройств Яндекса (type —
devices.types.*, capabilities — on_off/range/color_setting, props — показания датчиков), поэтому match()/readings()/
scenario()/summary() и разбор parse() общие. Своё — подключение, запросы (REST API: GET /api/, GET /api/states,
POST /api/services/<домен>/<служба>, POST /api/template — комнаты: areas(), area_name(), area_entities()), act() и
run_scenario() (сцены и скрипты). Homes — все подключённые дома как один: команда идёт туда, где устройство нашлось
точнее (по названию, потом по комнате, потом по типу); поровну — во все.

Безопасность: токен — в файле с правами 0600 (как ключ Яндекса), в студию и журнал не отдаётся; своим устройствам —
только конвертом (engine_tools.own_snapshot, сквозное шифрование). Адрес в своей сети (192.168.…, *.local, имя без
точки) — всегда напрямую, мимо прокси системы: у прокси своя сеть, нашего дома он не видит."""

import json
import logging
import re
import time
from datetime import datetime
from urllib.parse import urlparse

from smarthome import COLOR, ON_OFF, RANGE, Home, HomeError

log = logging.getLogger("dewiar.homeassistant")


class HANetError(HomeError):
    """До Home Assistant не достучаться или токен не подходит — дальше по устройствам не пробуем."""

TOKEN_HELP = ("в Home Assistant: профиль (кружок с вашим именем внизу слева) → вкладка «Безопасность» → "
              "«Долгосрочные токены доступа» → «Создать токен»")
# домен HA → тип устройства Яндекса (smarthome.TYPES ищет по началу типа: «свет» → devices.types.light и т. д.)
DOMAIN_TYPE = {"light": "devices.types.light", "switch": "devices.types.switch", "input_boolean": "devices.types.switch",
               "fan": "devices.types.fan", "climate": "devices.types.thermostat", "cover": "devices.types.openable",
               "media_player": "devices.types.media_device", "vacuum": "devices.types.vacuum_cleaner",
               "humidifier": "devices.types.humidifier"}
# «включи» / «выключи» — служба домена; у штор «включи» = открыть, у пылесоса «выключи» = на базу
ON_OFF_SVC = {"light": ("turn_on", "turn_off"), "switch": ("turn_on", "turn_off"), "input_boolean": ("turn_on", "turn_off"),
              "fan": ("turn_on", "turn_off"), "climate": ("turn_on", "turn_off"), "media_player": ("turn_on", "turn_off"),
              "humidifier": ("turn_on", "turn_off"), "cover": ("open_cover", "close_cover"), "vacuum": ("start", "return_to_base")}
# device_class датчика → instance показания (smarthome.PROPS: как назвать и единица)
SENSOR_CLASS = {"temperature": "temperature", "humidity": "humidity", "carbon_dioxide": "co2_level",
                "pressure": "pressure", "atmospheric_pressure": "pressure", "illuminance": "illumination",
                "pm25": "pm2.5_density", "volatile_organic_compounds": "tvoc", "battery": "battery_level",
                "power": "power", "voltage": "voltage", "current": "amperage"}
UNIT_PROP = {"°C": "temperature", "°F": "temperature"}      # датчик без device_class — по единице
DEAD = ("unavailable", "unknown", "")
# комнаты одним запросом: [{id, name, e: [entity_id…]}] (area_entities включает и сущности устройств этой комнаты)
AREAS_TPL = ('{% set ns = namespace(r=[]) %}{% for a in areas() %}{% set ns.r = ns.r + [{"id": a, "name": area_name(a), '
             '"e": area_entities(a)}] %}{% endfor %}{{ ns.r | tojson }}')


def norm_url(text):
    """«homeassistant.local», «192.168.1.20:8123», «http://ha:8123/lovelace/0» -> «http://…:8123» (без пути).
    Без схемы — http и порт 8123 (так HA ставится по умолчанию); со схемой — как написали."""
    u = (text or "").strip().rstrip("/")
    if not u:
        raise HomeError("укажите адрес Home Assistant — например, http://homeassistant.local:8123 или http://192.168.1.20:8123")
    had = re.match(r"(?i)https?://", u)
    if not had:
        u = "http://" + u
    p = urlparse(u)
    try:
        port = p.port
    except ValueError:
        port = -1
    if not p.hostname or "@" in p.netloc or port == -1 or not re.fullmatch(r"[\w.\-\[\]:]+", p.netloc):
        raise HomeError("это не похоже на адрес — нужен такой: http://homeassistant.local:8123 или http://192.168.1.20:8123")
    netloc = p.netloc.lower()
    if not had and port is None:
        netloc += ":8123"
    return f"{p.scheme.lower()}://{netloc}"


def _norm_token(text):
    t = re.sub(r"\s+", "", re.sub(r"(?i)^\s*bearer\s+", "", text or ""))
    if not t:
        raise HomeError("вставьте долгосрочный токен — " + TOKEN_HELP)
    if t.startswith("y0_"):
        raise HomeError("это ключ умного дома Яндекса — он вставляется выше, в «Умный дом Яндекса». Для Home Assistant нужен "
                        "его собственный токен — " + TOKEN_HELP)
    if not re.fullmatch(r"[\w.-]{20,}", t):
        raise HomeError("это не похоже на токен — Home Assistant показывает его один раз после «Создать токен»: длинная "
                        "строка, начинается с eyJ. Скопируйте её целиком")
    return t


def _epoch(iso):
    try:
        return datetime.fromisoformat(str(iso).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return None


def _num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f and abs(f) != float("inf") else None


class HAHome(Home):
    """Подключённый Home Assistant. Тот же интерфейс, что у smarthome.Home: connected/connect/forget/adopt/share/
    public/info/match/readings/scenario/act/run_scenario/summary."""

    NAME = "Home Assistant"

    # ---------- подключение ----------

    def connected(self):
        return bool(self.data.get("token") and self.data.get("url"))

    def connect(self, url, token):
        url, token = norm_url(url), _norm_token(token)
        self._req("GET", "/api/", url=url, token=token, check=True)       # тот ли адрес и подходит ли токен
        old = dict(self.data)
        self.data, self._info = {"url": url, "token": token, "at": int(time.time() * 1000)}, None
        try:
            info = self.info(force=True)
        except HomeError:
            self.data = old
            raise
        self._save()
        log.info("🏠 Home Assistant подключён (%s): устройств %d, комнат %d, сценариев %d", url,
                 sum(1 for d in info["devices"] if d.get("capabilities")), len(info["rooms"]), len(info["scenarios"]))
        return self.public()

    def forget(self):
        self.data, self._info = {"at": int(time.time() * 1000)}, None
        self._save()
        return self.public()

    def adopt(self, url, token, at):
        """Адрес и токен (или отключение — пустые) с другого своего компьютера; берём, только если там поменяли позже."""
        url, token, at = str(url or "").strip(), str(token or "").strip(), int(at or 0)
        if at <= int(self.data.get("at") or 0) or (token and not re.fullmatch(r"[\w.-]{20,}", token)):
            return False
        if token:
            try:
                url = norm_url(url)
            except HomeError:
                return False
            if token == self.data.get("token") and url == self.data.get("url"):
                return False
        elif not self.data.get("token"):
            return False
        with self._lock:
            self.data, self._info = ({"url": url, "token": token, "at": at} if token else {"at": at}), None
            self._save()
        log.info("🏠 Home Assistant: %s с другого своего устройства", "подключён" if token else "отключён")
        return True

    def share(self):
        if not self.data.get("at") and not self.data.get("token"):
            return None
        return {"url": self.data.get("url", ""), "token": self.data.get("token", ""), "at": int(self.data.get("at") or 1)}

    def public(self):
        """Для студии: адрес, комнаты, устройства, датчики, сценарии; токен не отдаётся."""
        out = {"connected": self.connected(), "url": self.data.get("url", ""), "rooms": [], "devices": [], "sensors": [], "scenarios": []}
        if not self.connected():
            return out
        try:
            info = self.info()
        except HomeError as e:
            return dict(out, error=str(e))
        from smarthome import prop_text
        out["rooms"] = [r["name"] for r in info["rooms"]]
        out["devices"] = [{"name": d["name"], "room": d.get("room_name", ""), "type": d["type"], "on": d.get("on")}
                          for d in info["devices"] if d.get("capabilities")]
        out["sensors"] = [{"name": d["name"], "room": d.get("room_name", ""), "value": prop_text(d["props"][0], with_name=False)}
                          for d in info["devices"] if not d.get("capabilities") and d.get("props")]
        out["scenarios"] = [s["name"] for s in info["scenarios"]]
        return out

    # ---------- API ----------

    def _req(self, method, path, body=None, url=None, token=None, check=False):
        """Запрос к HA -> разобранный JSON (или текст). Ошибки — понятными словами (HomeError).
        Адрес в своей сети — напрямую (trust_env=False: ни переменные прокси, ни прокси системы)."""
        import httpx
        from net import _private_host
        url, token = url or self.data.get("url"), token or self.data.get("token")
        if not (url and token):
            raise HomeError("Home Assistant не подключён — студия → «Подключение» → «Home Assistant»")
        host = urlparse(url).hostname or ""
        try:
            with httpx.Client(timeout=httpx.Timeout(12, connect=6), trust_env=not _private_host(host)) as c:
                r = c.request(method, url + path, json=body, headers={"Authorization": "Bearer " + token})
        except httpx.TimeoutException as e:
            raise HANetError(f"Home Assistant по адресу {url} не отвечает — он включён, а компьютер в той же сети?") from e
        except httpx.HTTPError as e:
            s = str(e)
            if re.search(r"Name or service not known|nodename nor servname|getaddrinfo|name resolution|No address associated|11001|-[235]\]", s):
                raise HANetError(f"не нашёл «{host}» в сети — проверьте адрес или укажите IP Home Assistant, например "
                                "http://192.168.1.20:8123 (он есть в HA: «Настройки» → «Система» → «Сеть»)") from e
            if re.search(r"(?i)certificate|ssl|tls", s):
                raise HANetError(f"не получилось защищённое соединение с {url} — сертификат не подтверждён. В домашней сети "
                                "обычно адрес начинается с http://, а не https://") from e
            raise HANetError(f"нет связи с Home Assistant по адресу {url} — проверьте адрес и порт (обычно 8123), "
                            "что HA включён и компьютер в той же сети") from e
        if r.status_code == 401:
            raise HANetError("токен не подходит — создайте новый: " + TOKEN_HELP)
        if r.status_code == 403:
            raise HANetError("Home Assistant не пускает с этим токеном — нужен токен пользователя-администратора")
        try:
            d = r.json()
        except ValueError:
            d = None
        if check and (r.status_code != 200 or not isinstance(d, dict) or "message" not in d):
            raise HomeError(f"по адресу {url} отвечает не Home Assistant — проверьте адрес и порт (обычно 8123)")
        if r.status_code >= 400:
            msg = (d or {}).get("message") if isinstance(d, dict) else ""
            raise HomeError(f"Home Assistant ответил ошибкой{': ' + msg if msg else f' {r.status_code}'}")
        return d if d is not None else r.text

    def _areas(self):
        """Комнаты (areas) -> ([{id, name}], {entity_id: area_id}). Шаблоны — только у администратора: нет — без комнат,
        устройства тогда ищутся по названию («Спальня люстра»)."""
        try:
            raw = self._req("POST", "/api/template", {"template": AREAS_TPL})
            arr = json.loads(raw) if isinstance(raw, str) else raw
        except (HomeError, ValueError) as e:
            log.info("🏠 Home Assistant: комнаты не прочитались (%s) — ищу по названиям", e)
            return [], {}
        rooms, where = [], {}
        for a in arr if isinstance(arr, list) else []:
            if not isinstance(a, dict) or not a.get("id"):
                continue
            rooms.append({"id": str(a["id"]), "name": str(a.get("name") or a["id"])})
            for e in a.get("e") or []:
                where.setdefault(str(e), str(a["id"]))
        return rooms, where

    @staticmethod
    def _device(st, room, room_name):
        """Сущность HA -> устройство в виде Яндекса (или None, если это не устройство дома)."""
        eid = str(st.get("entity_id") or "")
        dom = eid.split(".", 1)[0]
        a = st.get("attributes") or {}
        s = str(st.get("state") or "")
        name = str(a.get("friendly_name") or eid.split(".", 1)[-1].replace("_", " "))
        d = {"id": eid, "name": name, "room": room, "room_name": room_name, "domain": dom, "state": s,
             "capabilities": [], "props": [], "on": None}
        # когда датчик последний раз присылал показание: last_reported (HA 2024.3+) — даже если значение то же;
        # last_updated меняется только с самим значением — по нему ровная температура выглядела бы «давно не присылал»
        upd = _epoch(st.get("last_reported")) if st.get("last_reported") else None
        if dom == "sensor":
            inst = SENSOR_CLASS.get(a.get("device_class") or "") or UNIT_PROP.get(a.get("unit_of_measurement") or "")
            v = _num(s)
            if not inst or v is None:
                return None
            unit = a.get("unit_of_measurement") or ""
            d["type"] = "devices.types.sensor"
            d["props"] = [{"instance": inst, "value": v, "unit": unit, "updated": upd}]
            return d
        if dom not in DOMAIN_TYPE:
            return None
        t = DOMAIN_TYPE[dom]
        dc = a.get("device_class") or ""
        if dom == "switch" and dc == "outlet":
            t = "devices.types.socket"
        elif dom == "cover" and dc in ("curtain", "blind", "shade", "shutter", "awning", ""):
            t = "devices.types.openable.curtain"
        elif dom == "media_player" and dc == "tv":
            t = "devices.types.media_device.tv"
        elif dom == "climate" and (not a.get("hvac_modes") or {"cool", "heat_cool", "auto"} & set(a.get("hvac_modes") or [])):
            t = "devices.types.thermostat.ac"                   # «кондиционер»; только обогрев — «обогреватель»
        d["type"] = t
        if s not in DEAD:
            d["on"] = (s in ("open", "opening") if dom == "cover" else s == "cleaning" if dom == "vacuum"
                       else s not in ("off", "standby", "idle") if dom == "media_player" else s != "off")
        caps = [{"type": ON_OFF, "state": {"instance": "on", "value": d["on"]}}]
        feat = int(a.get("supported_features") or 0)
        if dom == "light":
            modes = set(a.get("supported_color_modes") or [])
            if (modes - {"onoff"}) or (not modes and "brightness" in a):
                b = _num(a.get("brightness"))
                caps.append({"type": RANGE, "parameters": {"instance": "brightness"},
                             "state": {"instance": "brightness", "value": round(b * 100 / 255) if b is not None else None}})
            if "color_temp" in modes:
                lo, hi = _num(a.get("min_color_temp_kelvin")), _num(a.get("max_color_temp_kelvin"))
                if lo is None and _num(a.get("max_mireds")):
                    lo, hi = 1e6 / _num(a["max_mireds"]), 1e6 / (_num(a.get("min_mireds")) or 153)
                cur = _num(a.get("color_temp_kelvin"))
                caps.append({"type": COLOR, "parameters": {"temperature_k": {"min": int(lo or 2000), "max": int(hi or 6500)}},
                             "state": {"instance": "temperature_k", "value": int(cur) if cur else None}})
        elif dom == "climate":
            caps.append({"type": RANGE, "parameters": {"instance": "temperature"},
                         "state": {"instance": "temperature", "value": _num(a.get("temperature"))}})
            for k, inst in (("current_temperature", "temperature"), ("current_humidity", "humidity")):
                if _num(a.get(k)) is not None:
                    d["props"].append({"instance": inst, "value": _num(a[k]), "unit": "", "updated": upd})
        elif dom == "cover" and feat & 4:                       # SET_POSITION: «шторы на 50 процентов»
            caps.append({"type": RANGE, "parameters": {"instance": "open"},
                         "state": {"instance": "open", "value": _num(a.get("current_position"))}})
        elif dom == "fan" and feat & 1:                         # SET_SPEED: «вентилятор на 60 процентов»
            caps.append({"type": RANGE, "parameters": {"instance": "percentage"},
                         "state": {"instance": "percentage", "value": _num(a.get("percentage"))}})
        d["capabilities"] = caps
        return d

    def info(self, force=False):
        """Дом -> {rooms, devices, groups, scenarios} в виде Яндекса. Кэш на 2 минуты; после act() сбрасывается."""
        with self._lock:
            if not force and self._info and time.monotonic() - self._info_t < 120:
                return self._info
        states = self._req("GET", "/api/states")
        if not isinstance(states, list):
            raise HomeError("Home Assistant прислал непонятный список устройств")
        rooms, where = self._areas()
        rname = {r["id"]: r["name"] for r in rooms}
        devs, scen = [], []
        for st in states:
            if not isinstance(st, dict):
                continue
            eid = str(st.get("entity_id") or "")
            dom = eid.split(".", 1)[0]
            if dom in ("scene", "script"):
                a = st.get("attributes") or {}
                scen.append({"id": eid, "name": str(a.get("friendly_name") or eid.split(".", 1)[-1].replace("_", " ")),
                             "is_active": True})
                continue
            room = where.get(eid, "")
            d = self._device(st, room, rname.get(room, ""))
            if d:
                devs.append(d)
        info = {"rooms": rooms, "devices": devs, "groups": [], "scenarios": scen}
        with self._lock:
            self._info, self._info_t = info, time.monotonic()
        return info

    # ---------- кого имели в виду ----------

    def match_rank(self, target, info=None):
        """Как у Яндекса, но только среди того, чем можно управлять: у датчика «Люстра — мощность» то же название,
        что у люстры, а включать его нечего."""
        info = info or self.info()
        return super().match_rank(target, dict(info, devices=[d for d in info["devices"] if d.get("capabilities")]))

    # ---------- действия ----------

    def _calls(self, d, op, value):
        """Команда parse() для одного устройства -> [(домен, служба, данные)]; не умеет — []."""
        dom = d.get("domain")
        if op in ("on", "off"):
            svc = ON_OFF_SVC.get(dom)
            return [(dom, svc[0 if op == "on" else 1], {})] if svc else []
        if op in ("brightness", "brighter", "dimmer"):
            for dm, inst, svc, key, lo in (("light", "brightness", "turn_on", "brightness_pct", 1),
                                           ("cover", "open", "set_cover_position", "position", 0),
                                           ("fan", "percentage", "set_percentage", "percentage", 0)):
                c = self._cap(d, RANGE, inst) if dom == dm else None
                if c:
                    cur = (c.get("state") or {}).get("value")
                    cur = 50 if cur is None else cur
                    v = value if op == "brightness" else cur + (25 if op == "brighter" else -25)
                    return [(dom, svc, {key: max(lo, min(100, int(v)))})]
            return []
        if op == "temperature" and dom == "climate" and self._cap(d, RANGE, "temperature"):
            return ([(dom, "turn_on", {})] if d.get("on") is False else []) + [(dom, "set_temperature", {"temperature": value})]
        if op == "warm" and dom == "light":
            c = self._cap(d, COLOR)
            rng = ((c or {}).get("parameters") or {}).get("temperature_k") or {}
            if c and rng:
                lo, hi = rng.get("min", 2700), rng.get("max", 6500)
                cur = (c.get("state") or {}).get("value") or (lo + hi) // 2
                v = lo if value == -2 else hi if value == 2 else cur + int(value or 0) * 800
                return [(dom, "turn_on", {"color_temp_kelvin": max(lo, min(hi, int(v)))})]
        return []

    def act(self, devices, op, value=None):
        """Выполнить команду на устройствах -> сколько выполнили. Одинаковые вызовы — одним запросом на все сущности."""
        groups, todo = {}, {}
        for d in devices:
            calls = self._calls(d, op, value)
            if calls:
                todo[d["id"]] = True
            for dom, svc, data in calls:
                groups.setdefault((dom, svc, json.dumps(data, sort_keys=True)), []).append(d["id"])
        if not todo:
            raise HomeError("эти устройства так не умеют")
        bad, err = set(), None
        for (dom, svc, data), ids in groups.items():
            try:
                self._req("POST", f"/api/services/{dom}/{svc}", dict(json.loads(data), entity_id=ids if len(ids) > 1 else ids[0]))
            except HANetError:
                raise
            except HomeError as e:
                bad.update(ids)
                err = e
        with self._lock:
            self._info_t = 0.0                               # состояние поменялось — перечитаем
        if bad and len(bad) >= len(todo):
            raise err or HomeError("устройство не ответило — проверьте, что оно в сети")
        return len(todo) - len(bad)

    def run_scenario(self, s):
        dom = s["id"].split(".", 1)[0]
        self._req("POST", f"/api/services/{dom}/turn_on", {"entity_id": s["id"]})
        return s["name"]


class Homes:
    """Все подключённые умные дома как один (то, что видят быстрые команды и инструмент smart_home).
    Порядок — кого предпочесть при прочих равных; команда идёт туда, где устройство нашлось точнее
    (Home.match_rank: название → комната → тип), поровну — во все дома («весь свет»). Найденное помечено _home."""

    def __init__(self, *homes):
        self.homes = homes

    def on(self):
        return [h for h in self.homes if h.connected()]

    def connected(self):
        return bool(self.on())

    def info(self, force=False):
        """-> {"parts": [(дом, его info)], "errors": [(дом, ошибка)]}; не ответил ни один — его ошибка."""
        parts, errs = [], []
        for h in self.on():
            try:
                parts.append((h, h.info(force)))
            except HomeError as e:
                errs.append((h, e))
        if not parts:
            raise errs[0][1] if errs else HomeError("умный дом не подключён — студия → «Подключение»")
        if errs:
            log.info("🏠 %s не ответил: %s", errs[0][0].NAME, errs[0][1])
        return {"parts": parts, "errors": errs}

    def _parts(self, info):
        return (info or self.info())["parts"]

    def match(self, target, info=None):
        best, out = 0, []
        for h, i in self._parts(info):
            rank, devs = h.match_rank(target, i)
            if rank > best:
                best, out = rank, []
            if rank and rank == best:
                out += [dict(d, _home=h) for d in devs]
        return out

    def readings(self, target, what=None, info=None):
        found, vals = False, []
        for h, i in self._parts(info):
            f, v = h.readings(target, what, i)
            found = found or f
            if v and not vals:
                vals = v
        return found, vals

    def scenario(self, name, info=None):
        best, score = None, 0
        for h, i in self._parts(info):
            s, sc = h.scenario_score(name, i)
            if s and sc > score:
                best, score = dict(s, _home=h), sc
        return best

    def run_scenario(self, s):
        h = s.get("_home") or self.on()[0]
        return h.run_scenario({k: v for k, v in s.items() if k != "_home"})

    def act(self, devices, op, value=None):
        by = {}
        for d in devices:
            by.setdefault(id(d.get("_home") or self.on()[0]), (d.get("_home") or self.on()[0], []))[1].append(d)
        n, err = 0, None
        for h, devs in by.values():
            try:
                n += h.act(devs, op, value)
            except HomeError as e:
                err = e
        if not n and err:
            raise err
        return n

    def summary(self):
        info = self.info()
        if len(info["parts"]) == 1 and not info["errors"]:
            return info["parts"][0][0].summary()
        out = [f"{h.NAME}: {h.summary()}" for h, _ in info["parts"]]
        out += [f"{h.NAME}: не отвечает ({e})" for h, e in info["errors"]]
        return ". ".join(out)
