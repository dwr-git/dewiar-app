"""Погода без модели (№373, 28.10: маленькая своя модель qwen2.5:1.5b погоду не искала — «облачно с ветром», а на
«а температура?» — «утром, днём и вечером облачно»; человек полчаса просил найти в интернете). Простой вопрос о погоде —
сразу настоящие числа Open-Meteo, как будильник или калькулятор: «какая погода?», «погода в Минске», «что с погодой
завтра?», «сколько градусов на улице?», «погода в Железногорске Курской области».

parse(text) -> {"city": как сказали или "", "day": 0 — сейчас и днём | 1 — завтра | 2 — послезавтра} или None.
Город не назван — из «Утра с Лирой» (настройка morning.city), потом из памяти («живу в …», «мой город — …»); нет и там —
спросим город. Названный город, если своего ещё нет, становится городом «Утра» — второй раз называть не нужно.
Город в падеже («в Минске», «в Нижнем Новгороде») ищем по основам — геокодер Open-Meteo ищет нечётко с 3 букв;
«… Курской области» — выбираем тот, что в этой области."""
import json
import re

import httpx

GEO = "https://geocoding-api.open-meteo.com/v1/search"
FC = "https://api.open-meteo.com/v1/forecast"
UA = {"User-Agent": "Mozilla/5.0 Dewiar"}
WMO = {0: "ясно", 1: "в основном ясно", 2: "переменная облачность", 3: "пасмурно", 45: "туман", 48: "изморозь", 51: "морось",
       53: "морось", 55: "сильная морось", 61: "небольшой дождь", 63: "дождь", 65: "сильный дождь", 66: "ледяной дождь",
       67: "ледяной дождь", 71: "небольшой снег", 73: "снег", 75: "сильный снег", 77: "снежная крупа", 80: "ливень", 81: "ливни",
       82: "сильные ливни", 85: "снегопад", 86: "сильный снегопад", 95: "гроза", 96: "гроза с градом", 99: "гроза с градом"}
ASK_RX = re.compile(r"(?:какая|какой|что|как|скажи|подскажи|узнай|глянь|посмотри|покажи)?\s*(?:там\s+|у\s+нас\s+|у\s+меня\s+)?"
                    r"(?:сейчас\s+|сегодня\s+|завтра\s+|послезавтра\s+)?(?:с\s+|про\s+)?погод[аеуыой]+", re.I)
TEMP_RX = re.compile(r"^(?:а\s+)?(?:сколько\s+(?:сейчас\s+)?градусов|какая\s+(?:сейчас\s+)?температура|температура)(?:\s+(?:сейчас|сегодня))?"
                     r"(?:\s+(?:на\s+улице|за\s+окном|снаружи))(?:\s+(?:сейчас|сегодня))?$|^(?:а\s+)?(?:холодно|тепло|жарко)\s+(?:ли\s+)?(?:сейчас\s+)?(?:на\s+улице|за\s+окном)$", re.I)
NOT_RX = re.compile(r"включи|поставь|песн|музык|трек|напомн|кажд\w+\s+(?:утро|день|час)|по\s+утрам|пришли|телеграм|\bmax\b|недел|выходн|месяц|вчера|"
                    r"прошл|прогноз\s+на\s+\d|почему|зачем|влияет|климат|запиши|заметк|календар", re.I)
TIME_WORDS = {"сейчас", "сегодня", "завтра", "послезавтра", "на", "будет", "там", "у", "нас", "меня", "за", "окном", "улице", "днём", "днем",
              "утром", "вечером", "какая", "какой", "какие", "какая-то", "пожалуйста", "подскажи", "скажи"}
PLACE = r"([А-ЯЁA-Z][\w-]+(?:,?\s+[А-ЯЁа-яё-]+(?:ой|ей|ого)\s+(?:области|края)|[\s-][А-ЯЁA-Z][\w-]+)?)"
MEM_RX = re.compile(r"(?i:живу|живёт|живет|проживаю|проживает|нахожусь|находится)\s+(?i:в|во)\s+(?:(?i:городе)\s+)?" + PLACE + "|"
                    r"(?i:мой\s+город|город\s+проживания|родной\s+город|город)\s*(?:—|-|:|это)?\s*" + PLACE)


class WeatherError(Exception):
    pass


def parse(text):
    t = re.sub(r"\s+", " ", str(text or "")).strip().strip(" .!?…")
    low = t.lower().replace("ё", "е")
    low = re.sub(r"^(?:(?:а|и|ну|так|слушай|лира|скажи|подскажи)[, ]+)+", "", low)
    low = re.sub(r"^(?:найди|поищи|посмотри|узнай)(?:\s+(?:в\s+интернете|в\s+сети))?\s+(?:информацию\s+|данные\s+)?(?:о|про|по)\s+погод\w*", "погода", low)
    low = re.sub(r"\s*(?:у\s+(?:меня|нас)\s+)?(?:в\s+(?:моем|нашем|своем)\s+городе|в\s+городе|у\s+(?:меня|нас))(?=\s|$)", "", low).strip()
    if len(low) > 80 or NOT_RX.search(low):
        return None
    day = 2 if "послезавтра" in low else 1 if "завтра" in low else 0
    if TEMP_RX.match(low):
        return {"city": "", "day": day}
    m = ASK_RX.match(low)
    if not m or not re.search(r"погод", low):
        return None
    rest = low[m.end():].strip(" ,")
    rest = re.sub(r"^(?:сейчас|сегодня|завтра|послезавтра|на\s+завтра|на\s+сегодня|будет|там|за\s+окном|на\s+улице)\b\s*", "", rest).strip(" ,")
    city = ""
    mc = re.match(r"^(?:в|во)\s+(.+)$", rest)
    if mc:
        words = [w for w in re.split(r"\s+", mc.group(1)) if w]
        while words and words[-1].strip(",") in TIME_WORDS:
            words.pop()
        city = " ".join(words).strip(" ,")
        if not city or len(city) > 60:
            return None
    elif rest and not all(w in TIME_WORDS for w in rest.replace(",", " ").split()):
        # «погода Железногорск Курской области» — город без «в»; «погода влияет на настроение» — геокодер не найдёт,
        # и вопрос уйдёт модели (engine_music._weather_cmd)
        if len(rest.split()) > 4 or re.search(r"[^а-яa-z\s,-]", rest):
            return None
        words = [w for w in rest.split() if w]
        while words and words[-1].strip(",") in TIME_WORDS:
            words.pop()
        city = " ".join(words).strip(" ,")
    if city:                                             # как сказали — с заглавной: «в минске» → «Минске»
        orig = re.search(r"(" + re.escape(city.split()[0]) + r".*)$", t, re.I)
        if orig:
            city = " ".join(orig.group(1).split()[:len(city.split())]).strip(" ,")
        city = " ".join(w[:1].upper() + w[1:] if w.lower() not in ("области", "края", "района", "республики") else w for w in city.split())
    return {"city": city, "day": day, "pre": bool(mc) and bool(city)}


def memory_city(text):
    return memory_place(text)[0]


def memory_place(text):
    """-> (город, сказан ли с «в»: «живу в Минске» — True, «мой город — Гродно» — False)."""
    m = MEM_RX.search(str(text or ""))
    if not m:
        return "", False
    return (m.group(1) or m.group(2) or "").strip(), bool(m.group(1))


def stored(place):
    """Как хранить город «Утра»: с областью, если она есть (Железногорск есть и под Курском, и под Красноярском)."""
    return place["name"] + (f", {place['admin1']}" if place.get("admin1") and place["admin1"] != place["name"] else "")


def _stems(word):
    """«Минске» → Минске, Минск; «Москве» → Москве, Москва, Москв; «Казани» → Казань; «Нижнем» → Нижний."""
    w = word.strip()
    out = [w]
    low = w.lower()
    for end, rep in (("ском", "ск"), ("ске", "ск"), ("ем", "ий"), ("ом", ""), ("е", "а"), ("е", ""), ("и", "ь"), ("и", "а"), ("у", "а"), ("ой", "ая"), ("ей", "ь")):
        if low.endswith(end) and len(low) - len(end) >= 3:
            out.append(w[:len(w) - len(end)] + rep)
    if len(w) > 4:
        out.append(w[:-1])
    seen, res = set(), []
    for x in out:
        if x.lower() not in seen:
            seen.add(x.lower()); res.append(x)
    return res


def _region(phrase):
    """«Железногорске Курской области» → («Железногорске», «курск»); «Москве» → («Москве», "")."""
    m = re.match(r"^(.*?)[\s,]+([А-ЯЁа-яё-]+?)(?:ой|ей|ая|ий|ый|ом|ем)?\s+(?:област[ьи]|кра[йя]|республик[аи]|район[ае]?)$", phrase.strip(), re.I)
    return (m.group(1).strip(" ,"), m.group(2).lower()[:5]) if m else (phrase.strip(" ,"), "")


def _get(url, params, via=None):
    try:
        r = httpx.get(url, params=params, headers=UA, timeout=10)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPError:
        if not via:
            raise
        return json.loads(via("fetch", str(httpx.URL(url, params=params))))


def geocode(phrase, via=None):
    """-> {name, lat, lon, admin1, country} или None (не нашли). Сеть упала — WeatherError."""
    name, region = _region(phrase)
    words = name.split()
    tries = []
    if len(words) == 1:
        tries = _stems(words[0])
    else:
        firsts = _stems(words[0])[:3]
        lasts = _stems(words[-1])[:3]
        mid = words[1:-1]
        tries = [" ".join([f] + mid + [l]) for f in firsts for l in lasts][:6] + [name]
    try:
        for q in tries:
            g = _get(GEO, {"name": q, "count": 10, "language": "ru"}, via)
            res = g.get("results") or []
            if region:
                res = [r for r in res if region in str(r.get("admin1") or "").lower().replace("ё", "е")] or []
            if not res:
                continue
            ql = q.lower().replace("ё", "е")
            res.sort(key=lambda r: (str(r.get("name") or "").lower().replace("ё", "е") != ql,
                                    not str(r.get("name") or "").lower().replace("ё", "е").startswith(ql[:4]), -(r.get("population") or 0)))
            r = res[0]
            if not str(r.get("name") or "").lower().replace("ё", "е").startswith(ql[:3]):
                continue
            return {"name": r["name"], "lat": r["latitude"], "lon": r["longitude"], "admin1": r.get("admin1") or "", "country": r.get("country") or ""}
    except (httpx.HTTPError, ValueError, Exception) as e:  # noqa: BLE001 — и запасной путь не вышел
        raise WeatherError(str(e)) from e
    return None


def forecast(place, via=None):
    try:
        w = _get(FC, {"latitude": place["lat"], "longitude": place["lon"], "timezone": "auto", "forecast_days": 3,
                      "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m",
                      "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max"}, via)
    except (httpx.HTTPError, ValueError, Exception) as e:  # noqa: BLE001
        raise WeatherError(str(e)) from e
    c, d = w.get("current") or {}, w.get("daily") or {}
    days = []
    for i, _ in enumerate(d.get("time") or []):
        pr = (d.get("precipitation_probability_max") or [None] * 9)[i]
        days.append({"min": round(d["temperature_2m_min"][i]), "max": round(d["temperature_2m_max"][i]), "sky": WMO.get(d["weather_code"][i], ""), "rain": pr})
    return {"now": round(c.get("temperature_2m", 0)), "feels": round(c.get("apparent_temperature", 0)), "sky": WMO.get(c.get("weather_code"), ""),
            "wind": round(c.get("wind_speed_10m", 0)), "days": days}


def deg(t):
    t = int(t)
    return f"минус {abs(t)}" if t < 0 else f"плюс {t}" if t > 0 else "ноль"


def say(where, f, day=0):
    """Одна-две фразы с настоящими числами. where — «в Минске» (как сказали) или «Минск» (город из настроек)."""
    pre = where.lower().startswith(("в ", "во "))
    if day and len(f["days"]) > day:
        x = f["days"][day]
        word = "Завтра" if day == 1 else "Послезавтра"
        head = f"{word} {where}" if pre else f"{where}, {word.lower()}:"
        return (f"{head} от {deg(x['min'])} до {deg(x['max'])}°, {x['sky']}" + (f", вероятность осадков {x['rain']}%" if x.get("rain") is not None else "") + ".")
    head = f"Сейчас {where}" if pre else f"{where}, сейчас"
    out = f"{head} {deg(f['now'])}°, {f['sky']}" + (f", ощущается как {deg(f['feels'])}" if abs(f["feels"] - f["now"]) >= 3 else "") + f", ветер {f['wind']} км/ч."
    if f["days"]:
        x = f["days"][0]
        out += f" Днём от {deg(x['min'])} до {deg(x['max'])}°, {x['sky']}" + (f", осадки {x['rain']}%" if x.get("rain") is not None and x["rain"] >= 20 else "") + "."
    return out
