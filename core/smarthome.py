"""Умный дом Яндекса (тот же дом, что у Алисы): свет, розетки, кондиционер, шторы, пылесос, сценарии.

Подключение: ключ OAuth с правами iot:view и iot:control (кнопка «Получить ключ» в студии → войти в Яндекс →
скопировать ключ). Дальше голосом, без модели: «включи свет в спальне», «выключи весь свет», «свет на кухне на 30
процентов», «сделай свет теплее», «кондиционер на 22», «закрой шторы», «запусти сценарий Спокойной ночи». Сложные
просьбы модель решает инструментом smart_home.

Части: parse() — разбор фразы в команду; Home.match()/scenario() — какие устройства или сценарий имелись в виду;
Home.act()/run_scenario() — выполнение. Ключ хранится в файле с правами 0600 и в студию не отдаётся.
API: https://api.iot.yandex.net/v1.0 — user/info, devices/actions, scenarios/{id}/actions."""

import json
import logging
import os
import re
import threading
import time
from pathlib import Path

log = logging.getLogger("dewiar.smarthome")
API = os.environ.get("DEWIAR_YANDEX_IOT") or "https://api.iot.yandex.net/v1.0"
# приложение «Dewiar» на oauth.yandex.ru (доступы iot:view и iot:control, адрес возврата verification_code): общее для всех —
# человеку остаётся «Получить ключ» → «Разрешить» → вставить ключ. ClientID не секрет (он и так в адресе входа);
# своё приложение — настройка smarthome.client_id или DEWIAR_YANDEX_CLIENT_ID.
CLIENT_ID = os.environ.get("DEWIAR_YANDEX_CLIENT_ID") or "bd46169129964deea1f608cf45f7122a"
CLIENT_ID_RX = re.compile(r"[0-9a-f]{32}")
OAUTH_URL = "https://oauth.yandex.ru/authorize?response_type=token&client_id={cid}"

ON_OFF = "devices.capabilities.on_off"
RANGE = "devices.capabilities.range"
COLOR = "devices.capabilities.color_setting"
TYPES = {  # начало слова → тип устройства Яндекса; тип сравнивается по началу (thermostat включает и thermostat.ac)
    "свет": "devices.types.light", "лампа": "devices.types.light", "лампочк": "devices.types.light", "люстр": "devices.types.light",
    "торшер": "devices.types.light", "светильник": "devices.types.light", "ночник": "devices.types.light", "подсветк": "devices.types.light",
    "розетк": "devices.types.socket", "кондиционер": "devices.types.thermostat.ac", "обогреват": "devices.types.thermostat",
    "термостат": "devices.types.thermostat", "чайник": "devices.types.cooking.kettle", "пылесос": "devices.types.vacuum_cleaner",
    "телевизор": "devices.types.media_device.tv", "увлажнител": "devices.types.humidifier", "очистител": "devices.types.purifier",
    "штор": "devices.types.openable.curtain", "жалюзи": "devices.types.openable.curtain", "вентилятор": "devices.types.fan",
    "колонк": "devices.types.media_device", "кофеварк": "devices.types.cooking.coffee_maker", "стиральн": "devices.types.washing_machine",
}
# Цветовая температура: ±1 — шаг 800 K от текущей, ±2 — крайнее значение лампы; минус — теплее (меньше кельвинов).
WARM = {"теплее": -1, "холоднее": 1, "тёплый": -2, "теплый": -2, "холодный": 2, "дневной": 1}
ON_RX = r"(?:включи|включить|зажги|запусти|открой|подними)"
OFF_RX = r"(?:выключи|выключить|отключи|погаси|потуши|закрой|опусти|останови)"
# Числа словами — для процентов яркости и градусов, если распознавание речи записало их буквами.
NUMW = {"десять": 10, "двадцать": 20, "тридцать": 30, "сорок": 40, "пятьдесят": 50, "шестьдесят": 60, "семьдесят": 70,
        "восемьдесят": 80, "девяносто": 90, "сто": 100, "половину": 50, "восемнадцать": 18, "девятнадцать": 19,
        "двадцать один": 21, "двадцать два": 22, "двадцать три": 23, "двадцать четыре": 24, "двадцать пять": 25,
        "шестнадцать": 16, "семнадцать": 17}


class HomeError(Exception):
    pass


def _words(s):
    """Слова фразы: нижний регистр, ё→е, однобуквенные (предлоги) отброшены."""
    return [w for w in re.findall(r"[\wё]+", (s or "").lower().replace("ё", "е")) if len(w) > 1]


def _num(s):
    s = (s or "").strip()
    if s.isdigit():
        return int(s)
    return NUMW.get(s)


# SKIP — служебные слова, в поиске устройства не участвуют. GENERIC — общие слова («свет», «лампы»): по названию
# устройства ими не ищем (иначе «выключи свет» найдёт одну лампу с «свет» в названии), они ведут к поиску по типу.
SKIP = {"в", "во", "на", "мне", "пожалуйста", "у", "с", "и", "весь", "все", "всё", "везде", "всюду", "всех", "сделай", "поставь"}
GENERIC = {"свет", "света", "светом", "устройства", "устройство", "лампы", "лампочки"}

# Датчики (отчёт №362, 27.10: «не может сказать температуру в спальне»): показания приходят в properties устройства
# (devices.properties.float). instance → как назвать и единица; давление и кельвины — по unit из parameters.
PROPS = {"temperature": ("температура", "°"), "humidity": ("влажность", "%"), "co2_level": ("углекислый газ", " ppm"),
         "pressure": ("давление", " мм рт. ст."), "illumination": ("освещённость", " лк"), "pm2.5_density": ("пыль PM2.5", " мкг/м³"),
         "tvoc": ("летучие вещества", " мкг/м³"), "battery_level": ("заряд", "%"), "water_level": ("вода", "%"),
         "power": ("мощность", " Вт"), "voltage": ("напряжение", " В"), "amperage": ("ток", " А")}
UNITS = {"unit.pressure.pascal": " Па", "unit.pressure.atm": " атм", "unit.pressure.bar": " бар", "unit.temperature.kelvin": " K",
         # единицы Home Assistant (unit_of_measurement датчика) — homeassistant.py
         "°C": "°", "°F": " °F", "K": " K", "hPa": " гПа", "kPa": " кПа", "Pa": " Па", "mbar": " мбар", "bar": " бар",
         "mmHg": " мм рт. ст.", "inHg": " дюйм рт. ст.", "W": " Вт", "kW": " кВт", "V": " В", "A": " А", "lx": " лк",
         "µg/m³": " мкг/м³", "μg/m³": " мкг/м³", "ppm": " ppm", "ppb": " ppb"}
# слово в вопросе → какой датчик спрашивают
ASK = (("температур", "temperature"), ("градус", "temperature"), ("влажн", "humidity"), ("углекисл", "co2_level"),
       ("co2", "co2_level"), ("давлен", "pressure"))
_ASK_RX = r"(температур\w*|градус\w*|влажност\w*|углекисл\w*(?:\s+газ\w*)?|co2|давлени\w*)"
_Q_RX = r"(?:а\s+)?(?:какая|какой|какое|каков\w*|сколько|скажи|подскажи|узнай|проверь|покажи|назови)?"


def fmt_value(v, unit=""):
    """22.46 → «22,5»: одна цифра после запятой, целое — без неё."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    r = round(f, 1)
    return (str(int(r)) if r == int(r) else str(r).replace(".", ",")) + unit


def prop_text(p, with_name=True):
    """{'instance': 'humidity', 'value': 41} → «влажность 41%»."""
    name, unit = PROPS.get(p.get("instance"), (p.get("instance") or "", ""))
    unit = UNITS.get(p.get("unit") or "", unit)
    return (name + " " if with_name else "") + fmt_value(p.get("value"), unit)


_PLACE_RX = re.compile(r"(?:^|\s)(?:в|во|на)\s+([а-яё]{2,})", re.I)
_HOME_WORDS = ("дом", "доме", "дома", "квартир", "везде", "всем")


def _unknown_place(target):
    """«…в <месте>» / «…на <месте>», где место — не весь дом: названа комната, которой нет."""
    m = _PLACE_RX.search(str(target or "").lower().replace("ё", "е"))
    return bool(m) and not m.group(1).startswith(_HOME_WORDS)


def _sim(a, b):
    """Одно слово в разных падежах: «кухня»/«кухне», «люстра»/«люстру», «гостиная»/«гостиной».
    Без словаря: общее начало не короче 4 букв, а отличаются не больше двух последних букв более короткого слова."""
    a, b = a.lower().replace("ё", "е"), b.lower().replace("ё", "е")
    if a == b:
        return True
    if len(a) < 4 or len(b) < 4:
        # короткое название комнаты: «зал»/«зале», «сад»/«саду» (№406, 29.10: «выключи свет в зале» выключал весь свет —
        # «зале» не узнавалось как «Зал») — слово целиком в начале другого и окончание не длиннее двух букв
        s_, l_ = (a, b) if len(a) <= len(b) else (b, a)
        return len(s_) == 3 and l_.startswith(s_) and len(l_) - 3 <= 2 and l_[3:] in ("а", "е", "у", "ом", "ах", "ы", "ой", "ам")
    
    n = 0
    while n < min(len(a), len(b)) and a[n] == b[n]:
        n += 1
    return n >= 4 and n >= min(len(a), len(b)) - 2


def parse(text):
    """-> {"op": "on"|"off"|"brightness"|"brighter"|"dimmer"|"temperature"|"warm"|"scenario", "target", "value"} | None.
    Только разбор фразы; есть ли такое устройство — решает Home.match(). Фраза длиннее 10 слов — не команда,
    её разбирает модель. Порядок проверок важен: «включи сценарий …» и «свет на 30%» раньше простого «включи …»."""
    t = re.sub(r"[^\w\s%-]", " ", (text or "").lower().replace("ё", "е"))
    t = " ".join(t.split())
    if not t or len(t.split()) > 10:
        return None
    m = re.fullmatch(r"(?:запусти|включи|активируй|выполни)\s+сценари[йя]\s+(.+)", t)
    if m:
        return {"op": "scenario", "target": m.group(1)}
    m = re.fullmatch(r"(?:сделай\s+)?(.+?)\s+(?:на|в)\s+(\d+|[а-я ]+?)\s*(?:%|процент\w*)", t)
    if m and _num(m.group(2)) is not None and not re.search(r"громк|звук", m.group(1)):
        return {"op": "brightness", "target": re.sub(r"^(?:поставь|сделай|включи)\s+", "", m.group(1)), "value": _num(m.group(2))}
    m = re.fullmatch(r"(?:поставь\s+|сделай\s+|установи\s+)?(?:температуру\s+)?(.*?(?:кондиционер|обогреват|термостат|отоплени)\w*.*?)\s+(?:на\s+)?(\d+|[а-я ]+?)\s*(?:градус\w*)?", t)
    if m and _num(m.group(2)) is not None and 10 <= _num(m.group(2)) <= 35:
        return {"op": "temperature", "target": m.group(1), "value": _num(m.group(2))}
    m = re.fullmatch(r"(?:сделай\s+)?(.*?)\s*(ярче|поярче|темнее|потемнее|приглуши|потише)\s*(.*)", t)
    if m and re.search(r"свет|ламп|люстр|торшер|подсветк|ночник|светильник", t):
        tgt = (m.group(1) + " " + m.group(3)).strip() or "свет"
        return {"op": "brighter" if "ярче" in m.group(2) else "dimmer", "target": tgt}
    m = re.fullmatch(r"(?:сделай\s+)?(.*?)\s*(теплее|холоднее|т[её]плый|холодный|дневной)(?:\s+свет)?\s*(.*)", t)
    if m and re.search(r"свет|ламп|люстр|торшер|светильник", t):
        return {"op": "warm", "target": (m.group(1) + " " + m.group(3)).strip() or "свет", "value": WARM[m.group(2).replace("ё", "е")] if m.group(2).replace("ё", "е") in WARM else 0}
    # показания датчика: «какая температура в спальне», «сколько градусов в детской», «в спальне какая влажность»
    m = re.fullmatch(rf"{_Q_RX}\s*(?:сейчас\s+)?(?:уровень\s+)?{_ASK_RX}\s+(?:сейчас\s+)?(?:воздуха\s+)?((?:в|во|на|у)\s+.+?)(?:\s+сейчас)?", t)
    m2 = None if m else re.fullmatch(rf"{_Q_RX}\s*(?:сейчас\s+)?((?:в|во|на|у)\s+.+?)\s+(?:сейчас\s+)?(?:какая|какой|какое|сколько)?\s*(?:уровень\s+)?{_ASK_RX}(?:\s+воздуха)?(?:\s+сейчас)?", t)
    if m or m2:
        what_w, place = (m.group(1), m.group(2)) if m else (m2.group(2), m2.group(1))
        what = next((v for k, v in ASK if what_w.startswith(k)), "temperature")
        return {"op": "read", "target": place, "what": what}
    m = re.fullmatch(rf"{ON_RX}\s+(.+)", t)
    if m:
        return {"op": "on", "target": m.group(1)}
    m = re.fullmatch(rf"{OFF_RX}\s+(.+)", t)
    if m:
        return {"op": "off", "target": m.group(1)}
    return None


class Home:
    """Подключённый умный дом. client_id — функция: адрес входа в Яндекс строится из актуального значения."""

    NAME = "Умный дом Яндекса"                # как назвать дом, если подключены два (homeassistant.Homes)

    def __init__(self, path, client_id=None):
        self.path = Path(path)
        self.client_id = client_id or (lambda: CLIENT_ID)
        self._lock = threading.RLock()
        self._info, self._info_t = None, 0.0
        self.data = {}
        try:
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.data = {}

    # ---------- подключение ----------

    def connected(self):
        return bool(self.data.get("token"))

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
        if os.name != "nt":                                       # в файле ключ — читать его может только владелец
            os.chmod(tmp, 0o600)
        tmp.replace(self.path)

    def connect(self, token):
        token = (token or "").strip()
        m = re.search(r"access_token=([^&\s]+)", token)          # вставили всю ссылку после входа (ключ в #access_token=…)
        if m:
            token = m.group(1)
        if not token:
            raise HomeError("сначала нажмите «Получить ключ» — Яндекс покажет ключ, вставьте его сюда")
        if re.fullmatch(r"eyJ[\w-]+\.[\w-]+\.[\w-]+", token):
            raise HomeError("это токен Home Assistant, а не ключ Яндекса — его вставляют ниже, в блок «Home Assistant», вместе с адресом")
        if CLIENT_ID_RX.fullmatch(token.lower()):
            raise HomeError("это ClientID приложения, а не ключ. Нажмите «Получить ключ» → «Разрешить» — "
                            "Яндекс покажет ключ: длинную строку, которая начинается с y0_")
        if not re.fullmatch(r"[\w.-]{20,}", token):
            raise HomeError("это не похоже на ключ — Яндекс показывает его после «Разрешить»: длинная строка, начинается с y0_. "
                            "Скопируйте её целиком")
        old = dict(self.data)
        self.data = {"token": token, "at": int(time.time() * 1000)}   # at — когда поменяли: свои устройства берут более позднее
        try:
            info = self.info(force=True)
        except HomeError:
            self.data = old
            raise
        self._save()
        log.info("🏠 Умный дом Яндекса подключён: устройств %d", len(info["devices"]))
        return self.public()

    def forget(self):
        self.data, self._info = {"at": int(time.time() * 1000)}, None   # «отключили тогда-то» — чтобы и телефон отключился
        self._save()
        return self.public()

    def adopt(self, token, at):
        """Ключ (или отключение — пустой) с другого своего устройства; берём, только если там поменяли позже. -> взяли ли."""
        token, at = str(token or "").strip(), int(at or 0)
        if at <= int(self.data.get("at") or 0) or (token and not re.fullmatch(r"[\w.-]{20,}", token)) or token == self.data.get("token", ""):
            return False
        with self._lock:
            self.data, self._info = ({"token": token, "at": at} if token else {"at": at}), None
            self._save()
        log.info("🏠 Умный дом Яндекса: %s с другого своего устройства", "подключён" if token else "отключён")
        return True

    def share(self):
        """Что передать своим устройствам: {token, at} — подключён или отключён; None — ни разу не настраивали."""
        if not self.data.get("at") and not self.data.get("token"):
            return None
        return {"token": self.data.get("token", ""), "at": int(self.data.get("at") or 1)}   # подключили до 0.38.10 — «давно»

    def public(self):
        """Для студии: комнаты, устройства, сценарии и адрес входа в Яндекс; сам ключ не отдаётся."""
        info = None
        if self.connected():
            try:
                info = self.info()
            except HomeError as e:
                return {"connected": True, "error": str(e), "client_id": self.client_id()}
        cid = self.client_id()
        return {"connected": self.connected(), "client_id": cid,
                "auth_url": OAUTH_URL.format(cid=cid) if cid else "",
                "rooms": [r["name"] for r in (info or {}).get("rooms", [])],
                "devices": [{"name": d["name"], "room": d.get("room_name", ""), "type": d.get("type", ""), "on": d.get("on")}
                            for d in (info or {}).get("devices", [])],
                "scenarios": [s["name"] for s in (info or {}).get("scenarios", []) if s.get("is_active", True)]}

    # ---------- API ----------

    def _req(self, method, path, body=None):
        import httpx
        if not self.connected():
            raise HomeError("умный дом Яндекса не подключён — студия → «Подключение» → «Умный дом»")
        try:
            r = httpx.request(method, API.rstrip("/") + path, json=body, timeout=12,
                              headers={"Authorization": "Bearer " + self.data["token"]})
        except httpx.HTTPError as e:
            raise HomeError(f"умный дом не отвечает: {e}") from e
        if r.status_code == 401:
            raise HomeError("ключ умного дома больше не действует — подключите заново")
        if r.status_code == 403:
            raise HomeError("у ключа нет прав на умный дом — при получении нужны права iot:view и iot:control")
        try:
            d = r.json()
        except ValueError as e:
            raise HomeError(f"умный дом ответил {r.status_code}") from e
        if d.get("status") not in (None, "ok"):
            raise HomeError(d.get("message") or "умный дом ответил ошибкой")
        return d

    def info(self, force=False):
        """Дом -> {rooms, devices, groups, scenarios}; у устройств добавлены room_name, on и caps.
        Кэш на 2 минуты — чтобы не спрашивать Яндекс на каждую команду; после act() кэш сбрасывается."""
        with self._lock:
            if not force and self._info and time.monotonic() - self._info_t < 120:
                return self._info
        d = self._req("GET", "/user/info")
        rooms = {r["id"]: r.get("name", "") for r in d.get("rooms", [])}
        devs = []
        for x in d.get("devices", []):
            caps = {c.get("type"): c for c in x.get("capabilities", [])}
            on = (caps.get(ON_OFF) or {}).get("state", {}) or {}
            props = [{"instance": (p.get("state") or {}).get("instance") or (p.get("parameters") or {}).get("instance"),
                      "value": (p.get("state") or {}).get("value"), "unit": (p.get("parameters") or {}).get("unit", ""),
                      "updated": p.get("last_updated")}
                     for p in x.get("properties", []) or []
                     if p.get("type") == "devices.properties.float" and (p.get("state") or {}).get("value") is not None]
            devs.append(dict(x, room_name=rooms.get(x.get("room"), ""), on=on.get("value"), caps=list(caps), props=props))
        info = {"rooms": d.get("rooms", []), "devices": devs, "groups": d.get("groups", []),
                "scenarios": d.get("scenarios", [])}
        with self._lock:
            self._info, self._info_t = info, time.monotonic()
        return info

    # ---------- кого имели в виду ----------

    def match(self, target, info=None):
        """«свет в спальне», «весь свет», «люстру», «кондиционер», «торшер в гостиной» -> [устройства] (может быть пусто)."""
        return self.match_rank(target, info)[1]

    def match_rank(self, target, info=None):
        """match() и насколько точно нашлось: 3 — по названию устройства, 2 — по типу в названной комнате («свет в
        спальне», «всё в спальне»), 1 — по типу во всём доме, 0 — ничего. Если подключены два дома (homeassistant.Homes),
        команда идёт туда, где нашлось точнее."""
        info = info or self.info()
        words = [w for w in _words(target) if w not in SKIP]
        allw = any(w in ("весь", "все", "всё", "везде", "всюду", "всех") for w in _words(target))
        rooms = [r for r in info["rooms"] if any(_sim(a, b) for a in _words(r.get("name")) for b in words)]
        room_ids = {r["id"] for r in rooms}
        room_words = {b for r in rooms for a in _words(r.get("name")) for b in words if _sim(a, b)}
        rest = [w for w in words if w not in room_words]
        in_room = lambda d: not room_ids or d.get("room") in room_ids  # noqa: E731
        # 1) по названию устройства («люстра», «розетка чайника», «торшер»)
        scored = []
        for d in info["devices"]:
            sc = sum(1 for a in _words(d.get("name")) for b in rest if b not in GENERIC and _sim(a, b))
            if sc and in_room(d):
                scored.append((sc, d))
        if scored:
            top = max(x for x, _ in scored)
            return 3, [d for x, d in scored if x == top]
        # 2) по типу («свет», «кондиционер», «розетки») — все такие (в комнате, если названа)
        wtype = next((tp for k, tp in TYPES.items() if any(w.startswith(k) for w in rest)), None)
        if wtype and not room_ids and not allw and _unknown_place(target):
            return 0, []      # «свет в зимнем саду», а такой комнаты нет — не весь свет в доме (№406): пусть уточнит модель
        if wtype:
            found = [d for d in info["devices"] if str(d.get("type", "")).startswith(wtype) and in_room(d)]
            return (2 if room_ids else 1) if found else 0, found
        # 3) «выключи всё в спальне»
        if allw and room_ids:
            found = [d for d in info["devices"] if d.get("room") in room_ids and self._cap(d, ON_OFF)]
            return 2 if found else 0, found
        return 0, []

    def readings(self, target, what=None, info=None):
        """Показания датчиков в комнате (или у устройства с таким названием) -> (комнаты нашлись?, [показания]).
        Сначала датчики (devices.types.sensor…), потом прочие (кондиционер тоже знает температуру); по одному на instance."""
        info = info or self.info()
        words = [w for w in _words(target) if w not in SKIP]
        rooms = {r["id"] for r in info["rooms"] if any(_sim(a, b) for a in _words(r.get("name")) for b in words)}
        by_name = lambda d: any(_sim(a, b) for a in _words(d.get("name")) for b in words)  # noqa: E731
        devs = [d for d in info["devices"] if d.get("props") and (d.get("room") in rooms if rooms else by_name(d))]
        devs.sort(key=lambda d: not str(d.get("type", "")).startswith("devices.types.sensor"))
        out, seen = [], set()
        for d in devs:
            for p in d["props"]:
                if (what and p["instance"] != what) or p["instance"] in seen:
                    continue
                seen.add(p["instance"])
                out.append(dict(p, device=d.get("name", ""), room=d.get("room_name", "")))
        return bool(rooms) or bool(devs), out

    def scenario(self, name, info=None):
        """Сценарий с наибольшим числом совпавших слов названия -> сценарий или None."""
        return self.scenario_score(name, info)[0]

    def scenario_score(self, name, info=None):
        """-> (сценарий или None, сколько слов названия совпало)."""
        info = info or self.info()
        want = _words(name)
        best, score = None, 0
        for s in info["scenarios"]:
            sc = sum(1 for a in _words(s.get("name")) for b in want if _sim(a, b))
            if sc > score:
                best, score = s, sc
        return best, score

    # ---------- действия ----------

    @staticmethod
    def _cap(d, typ, inst=None):
        """Умение устройства этого типа (и instance, если задан) или None. instance ищем и в state, и в parameters:
        state в ответе Яндекса бывает пустым (null)."""
        for c in d.get("capabilities", []):
            if c.get("type") == typ and (inst is None or (c.get("state") or {}).get("instance") == inst
                                         or (c.get("parameters") or {}).get("instance") == inst):
                return c
        return None

    def act(self, devices, op, value=None):
        """Выполнить команду parse() на устройствах -> сколько устройств выполнили.
        Яркость и температура заодно включают устройство. «Ярче/темнее» — ±25% от текущей (неизвестна — от 50).
        Устройства, которые так не умеют, пропускаются; если не умеет ни одно — HomeError."""
        acts = []
        for d in devices:
            a = []
            if op in ("on", "off"):
                if self._cap(d, ON_OFF):
                    a.append({"type": ON_OFF, "state": {"instance": "on", "value": op == "on"}})
            elif op in ("brightness", "brighter", "dimmer"):
                c = self._cap(d, RANGE, "brightness")
                if c:
                    cur = ((c.get("state") or {}).get("value") or 50)
                    v = value if op == "brightness" else cur + (25 if op == "brighter" else -25)
                    a.append({"type": RANGE, "state": {"instance": "brightness", "value": max(1, min(100, int(v)))}})
                    if self._cap(d, ON_OFF):
                        a.append({"type": ON_OFF, "state": {"instance": "on", "value": True}})
            elif op == "temperature":
                if self._cap(d, RANGE, "temperature"):
                    a.append({"type": RANGE, "state": {"instance": "temperature", "value": int(value)}})
                    if self._cap(d, ON_OFF):
                        a.append({"type": ON_OFF, "state": {"instance": "on", "value": True}})
            elif op == "warm":
                c = self._cap(d, COLOR)
                rng = ((c or {}).get("parameters") or {}).get("temperature_k") or {}
                if c and rng:
                    lo, hi = rng.get("min", 2700), rng.get("max", 6500)
                    cur = ((c.get("state") or {}).get("value") if (c.get("state") or {}).get("instance") == "temperature_k" else None) or (lo + hi) // 2
                    v = lo if value == -2 else hi if value == 2 else cur + int(value or 0) * 800
                    a.append({"type": COLOR, "state": {"instance": "temperature_k", "value": max(lo, min(hi, int(v)))}})
            if a:
                acts.append({"id": d["id"], "actions": a})
        if not acts:
            raise HomeError("эти устройства так не умеют")
        r = self._req("POST", "/devices/actions", {"devices": acts})
        # Считаем устройства, а не умения: у лампы «яркость + включить» — два действия, и две ошибки одной лампы
        # иначе списали бы два устройства (счёт уходил бы в минус)
        bad = {x.get("id") for x in r.get("devices", []) for c in x.get("capabilities", [])
               if ((c.get("state") or {}).get("action_result") or {}).get("status") == "ERROR"}
        with self._lock:
            self._info_t = 0.0                               # состояние поменялось — перечитаем
        if bad and len(bad) >= len(acts):
            raise HomeError("устройство не ответило — проверьте, что оно в сети")
        return len(acts) - len(bad)

    def run_scenario(self, s):
        self._req("POST", f"/scenarios/{s['id']}/actions", {})
        return s["name"]

    def summary(self):
        """Для модели: какие есть комнаты, устройства и сценарии."""
        info = self.info()
        lines = []
        for d in info["devices"]:
            st = "" if d.get("on") is None else (" — вкл" if d["on"] else " — выкл")
            if d.get("props"):
                st += " — " + ", ".join(prop_text(p) for p in d["props"])
            lines.append(f"{d['name']}" + (f" ({d['room_name']})" if d.get("room_name") else "") + st)
        sc = [s["name"] for s in info["scenarios"] if s.get("is_active", True)]
        return ("Устройства: " + "; ".join(lines) if lines else "Устройств нет") + (". Сценарии: " + ", ".join(sc) if sc else "")
