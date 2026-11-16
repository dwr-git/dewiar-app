"""Действия модели: интернет и быстрые ответы — сайты, поиск, картинки, чтение страниц, погода, время в городах,
маршрут, калькулятор."""

import html
import httpx
import json
import os
import re
import urllib.parse

from tools_base import browser_cmd, log, ToolError, UA
import tools_base as base          # launch — через основу: проверки подменяют их там


def t_open_url(a, ctx):
    url = (a.get("url") or "").strip()
    if not re.match(r"^https?://", url):
        url = "https://" + url
    if not re.match(r"^https?://[^\s/$.?#].[^\s]*$", url):
        raise ToolError("это не похоже на адрес сайта")
    base.launch(browser_cmd(url))
    return f"Открыл в браузере: {url}"


def t_route(a, ctx):
    """Маршрут на карте в браузере (route.py): пешком по умолчанию, Яндекс Карты (или Google, если просят)."""
    import route as RT
    to = str(a.get("to") or "").strip()
    if not to:
        raise ToolError("не понял, куда — спроси адрес или место")
    app = "google" if re.search(r"google|гугл", str(a.get("app") or ""), re.I) else "yandex"

    def resolve(u):
        import httpx
        return str(httpx.get(u, headers=UA, timeout=10, follow_redirects=True).url)
    r = RT.plan(to, str(a.get("from") or ""), str(a.get("mode") or "walk"), app, resolve=resolve)
    try:
        base.launch(["xdg-open", r["url"]])
        opened = True
    except (ToolError, OSError):
        opened = False
    return RT.say(r, opened)


def parse_ddg(page):
    """HTML-выдача html.duckduckgo.com -> [{title, url, snippet}]. Ссылки там — переходы с настоящим адресом в uddg=…"""
    out = []
    for m in re.finditer(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>(.*?)(?=class="result__a"|$)', page, re.S):
        href, title, rest = m.group(1), m.group(2), m.group(3)
        q = urllib.parse.urlparse(html.unescape(href))
        url = urllib.parse.parse_qs(q.query).get("uddg", [html.unescape(href)])[0]
        sn = re.search(r'class="result__snippet"[^>]*>(.*?)</a>', rest, re.S)
        clean = lambda s: html.unescape(re.sub(r"<[^>]+>", "", s)).strip()  # noqa: E731
        if "duckduckgo.com/y.js" in url:
            continue                                                          # реклама
        out.append({"title": clean(title), "url": url, "snippet": clean(sn.group(1)) if sn else ""})
    return out


def searx_results(base, q):
    """Поиск через SearXNG (JSON) -> [{title, url, snippet}]. Ошибка сети — httpx.HTTPError."""
    r = httpx.get(base.rstrip("/") + "/search", params={"q": q, "format": "json", "language": "ru"}, headers=UA, timeout=12)
    r.raise_for_status()
    return [{"title": x.get("title", ""), "url": x.get("url", ""), "snippet": x.get("content", "")} for x in r.json().get("results", [])]


def search_text(res):
    """Выдача -> текст для модели: 6 результатов хватает модели и не раздувает контекст."""
    if not res:
        return "Ничего не нашлось."
    return ("\n".join(f"{i + 1}. {x['title']} — {x['snippet']} ({x['url']})" for i, x in enumerate(res[:6]))
            + "\n(Это отрывки страниц. Нужен сам текст целиком — стихотворение, статья, инструкция — открой ссылку: read_webpage.)")


def t_web_search(a, ctx):
    q = (a.get("query") or "").strip()
    if not q:
        raise ToolError("пустой запрос")
    # DEWIAR_SEARCH_URL — свой поиск (SearXNG JSON) поверх настроек: проверки и экзамен с локальным «интернетом» (docs/HARNESS.md)
    searx = os.environ.get("DEWIAR_SEARCH_URL") or ctx["settings"].get("tools", "search_url") or ""
    via = ctx.get("dewiar_web")                                     # запасной путь: поиск через сервер Dewiar
    try:
        if searx:                                                   # свой SearXNG (JSON)
            res = searx_results(searx, q)
        else:
            r = httpx.post("https://html.duckduckgo.com/html/", data={"q": q, "kl": "ru-ru"}, headers=UA, timeout=12,
                           follow_redirects=True)
            r.raise_for_status()
            res = parse_ddg(r.text)
            if not res and via and ("anomaly" in r.text or "captcha" in r.text.lower()):
                raise httpx.HTTPError("поисковик просит капчу")
    except httpx.HTTPError as e:
        # поисковик бывает недоступен из сети пользователя (провайдер рвёт соединение, капча) — ищем через сервер Dewiar
        res = None
        if via:
            try:
                res = via("search", q)
                log.info("Поиск через сервер Dewiar (напрямую: %s)", e)
            except Exception as e2:  # noqa: BLE001
                log.info("Поиск через сервер Dewiar не удался: %s", e2)
        if res is None:
            raise ToolError(f"поиск недоступен: {e}") from e
    return search_text(res)


def t_show_images(a, ctx):
    """Показать картинки к рассказу (images.py: поисковик картинок, запасной — Wikimedia Commons) — в виджете, «Чате»
    студии; модели — что показано."""
    import images as IM
    q = (a.get("query") or "").strip()
    if not q:
        raise ToolError("пустой запрос — что показать?")
    n = max(1, min(6, int(a.get("count") or 4)))
    # не нашлось — пробуем проще сами (экзамен 0.38.49: модель трижды подряд звала «rune knotwork» и сдалась): самые
    # длинные слова запроса по отдельности, не больше двух попыток
    # экзамен ПК 0.81.1: «runestone knotwork runic inscription» в Commons — морские узлы и церковные скамьи, трижды. Подписи
    # не о том — пробуем дальше по словам запроса в его порядке (главное слово модель ставит первым), пока подписи не совпадут
    words = list(dict.fromkeys(w for w in re.findall(r"[\w-]{4,}", q)))
    tries = [q] + ([w for w in words if w.lower() != q.lower()][:3] if len(q.split()) > 1 else [])
    items, err, first = [], None, []
    for qq in tries:
        try:
            items = IM.search(qq, n, searx_url=ctx["settings"].get("tools", "search_url") or "", via=ctx.get("dewiar_web"))
        except httpx.HTTPError as e:
            err = e
            continue
        if items and IM.relevant(items, qq):
            items = IM.relevant(items, qq) + [x for x in items if x not in IM.relevant(items, qq)]
            break
        first = first or items
        items = []
    items = items or first
    if not items and err is not None:
        raise ToolError(f"картинки сейчас не загрузились ({err}) — скажи об этом коротко") from err
    if not items:
        return ("Картинок по этому запросу не нашлось. Не говори, что показала их; можно попробовать запрос проще (одно-два "
                "слова) или по-английски.")
    eng = ctx.get("engine")
    if eng is not None and hasattr(eng, "show_media"):
        eng.show_media(items, str(a.get("caption") or ""))
    return (f"На экране показано картинок: {len(items)} ({IM.credit(items)}). Что на них (подписи с сайтов):\n"
            + "\n".join(f"{i + 1}. {x['title']}" + (f" — {x['desc'][:120]}" if x.get("desc") else "")
                        + (f" [{x['site']}]" if x.get("site") and x.get("source") != "commons" else "") for i, x in enumerate(items))
            + "\nГовори о них как о показанных («на второй картинке…»), но описывай только то, что следует из подписей; "
              "не выдумывай деталей. Подпись не о том — не выдавай картинку за нужную.")


def html_to_text(page):
    """Грубо: HTML -> текст для модели (без скриптов, стилей, навигации, боковых меню, шапки и подвала). Есть <main> или
    <article> с текстом — берём его (отчёт №69: у справочника на Nextra первые тысячи знаков были боковым меню)."""
    page = re.sub(r"(?is)<(script|style|noscript|svg|nav|footer|header|aside)[^>]*>.*?</\1>", " ", page)
    m = re.search(r"(?is)<(main|article)\b[^>]*>(.*)</\1>", page)
    if m and len(re.sub(r"<[^>]+>|\s+", "", m.group(2))) > 200:
        page = m.group(2)
    page = re.sub(r"(?i)<br\s*/?>|</p>|</h\d>|</li>|</div>", "\n", page)
    text = html.unescape(re.sub(r"<[^>]+>", " ", page))
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n", text).strip()


PAGE_MAX = 6000


PAGE_EMPTY = ("Страница открылась, но текста на ней нет (скорее всего, он подгружается скриптом). Ничего не пересказывай "
              "за неё и не придумывай — открой другой адрес из поиска или честно скажи, что страница не прочиталась.")


_STOP = set("какой какая какие каков сегодня сейчас завтра вчера скажи покажи найди пожалуйста можно нужно этот этого "
            "много очень только было будет есть где когда почему зачем сколько".split())


def _terms(text):
    """Слова вопроса для поиска по странице: основа (5 букв) — «доллара» найдёт «Доллар США»."""
    out = []
    for w in re.findall(r"[A-Za-zА-Яа-яЁё0-9]{4,}", text or ""):
        w = w.lower()
        if w not in _STOP and not w.isdigit() and w[:5] not in out:
            out.append(w[:5])
    return out[:8]


def page_excerpt(text, find="", question=""):
    """Длинная страница -> начало и куски вокруг слов find (или вопроса), всё в PAGE_MAX. Экзамен 14.10: строка
    «Доллар США» на странице ЦБ стояла после шести тысяч знаков — модель её не увидела и выдумала курс;
    пустая страница журнала — выдумала фильм."""
    text = (text or "").strip()
    if len(re.sub(r"\s+", "", text)) < 80:
        return PAGE_EMPTY
    if len(text) <= PAGE_MAX:
        return text
    terms = _terms(find) or _terms(question)
    low = text.lower()
    spans = []
    for t in terms:
        for m in re.finditer(re.escape(t), low):
            if m.start() < 1500:
                continue
            spans.append((max(1500, m.start() - 500), min(len(text), m.end() + 700)))
            if len(spans) > 40:
                break
    spans.sort()
    merged = []
    for a_, b_ in spans:
        if merged and a_ <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b_))
        else:
            merged.append((a_, b_))
    if not merged:
        return (text[:PAGE_MAX] + f"…\n[Страница длиннее: показано {PAGE_MAX} из {len(text)} знаков. Если нужного здесь нет — "
                "вызови read_webpage ещё раз с find (что ищешь на странице, например «Доллар США»); не додумывай.]")
    out, left = [text[:1500]], PAGE_MAX - 1500
    for a_, b_ in merged:
        if left <= 200:
            break
        piece = text[a_:min(b_, a_ + left)]
        out.append(piece); left -= len(piece)
    return ("\n…\n".join(out) + f"\n[Страница длинная ({len(text)} знаков): выше начало и места со словами "
            f"«{', '.join(terms)}». Чего здесь нет — того на странице не видно; не додумывай.]")


WMO = {0: "ясно", 1: "в основном ясно", 2: "переменная облачность", 3: "пасмурно", 45: "туман", 48: "изморозь", 51: "морось",
       53: "морось", 55: "сильная морось", 61: "небольшой дождь", 63: "дождь", 65: "сильный дождь", 66: "ледяной дождь",
       67: "ледяной дождь", 71: "небольшой снег", 73: "снег", 75: "сильный снег", 77: "снежная крупа", 80: "ливень", 81: "ливни",
       82: "сильные ливни", 85: "снегопад", 86: "сильный снегопад", 95: "гроза", 96: "гроза с градом", 99: "гроза с градом"}


def t_weather(a, ctx):
    """Погода из Open-Meteo (как на телефоне, app.js weather): сейчас и по дням. Экзамен 16.10: компьютер искал сайт погоды,
    сайт отдал одно меню — и модель выдумала «+7…+12». Здесь — настоящие числа или честная ошибка."""
    import datetime as _dt
    city = str(a.get("city") or "").strip()
    days = max(1, min(7, int(float(a.get("days") or 3))))
    src = ""
    if not city:                         # идея №142: город не назван — из «Утра с Лирой», потом из памяти («живу в Балашове»)
        city, src = home_city((ctx or {}).get("engine") if isinstance(ctx, dict) else None)
    if not city:
        raise ToolError("спроси, в каком городе")
    def get(url, params):
        """open-meteo напрямую; не открылся — тем же адресом через сервер Dewiar (пакет 27.10: у части людей провайдер или
        слабая сеть — «прогноз не получить»)."""
        try:
            r = httpx.get(url, params=params, headers=UA, timeout=10)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPError as e:
            via = (ctx or {}).get("dewiar_web") if isinstance(ctx, dict) else None
            if not via:
                raise
            log.info("Погода через сервер Dewiar (напрямую: %s)", e)
            return json.loads(via("fetch", str(httpx.URL(url, params=params))))
    try:
        g = get("https://geocoding-api.open-meteo.com/v1/search", {"name": city, "count": 1, "language": "ru"})
        p = (g.get("results") or [None])[0]
        if not p:                        # «Балашове», «Минска» — как сказали: ищем по основам (weatherq)
            import weatherq as W
            try:
                q = W.geocode(city, (ctx or {}).get("dewiar_web") if isinstance(ctx, dict) else None)
            except W.WeatherError:
                q = None
            p = {"name": q["name"], "latitude": q["lat"], "longitude": q["lon"]} if q else None
        if not p:
            return f"Город «{city}» не нашёлся — уточни название."
        w = get("https://api.open-meteo.com/v1/forecast", {
            "latitude": p["latitude"], "longitude": p["longitude"], "timezone": "auto", "forecast_days": days,
            "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m,precipitation",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max"})
    except (httpx.HTTPError, ValueError, Exception) as e:  # noqa: BLE001 — и запасной путь не вышел
        # без подробностей о запасном пути (№412: «у меня локальная модель — при чём тут Dewiar?»)
        log.info("Погода: прогноз не получить: %s", e)
        raise ToolError("прогноз сейчас не получить — сервис погоды не отвечает (проверь интернет); так и скажи одной "
                        "фразой, цифры не придумывай, про Dewiar и аккаунты не говори") from None
    c, d = w.get("current") or {}, w.get("daily") or {}
    out = [f"{p.get('name', city)}: сейчас {round(c.get('temperature_2m', 0))}°, ощущается как {round(c.get('apparent_temperature', 0))}°, "
           f"{WMO.get(c.get('weather_code'), '')}, ветер {round(c.get('wind_speed_10m', 0))} км/ч."]
    today = _dt.date.today()
    for i, t in enumerate(d.get("time") or []):
        k = (_dt.date.fromisoformat(t) - today).days
        mark = {0: " (сегодня)", 1: " (завтра)", 2: " (послезавтра)"}.get(k, "")
        pr = (d.get("precipitation_probability_max") or [None] * 99)[i]
        out.append(f"{t}{mark}: {round(d['temperature_2m_min'][i])}…{round(d['temperature_2m_max'][i])}°, "
                   f"{WMO.get(d['weather_code'][i], '')}, осадки {pr if pr is not None else '?'}%")
    note = ""
    if src == "memory":
        note = (f"\n[Город не назван — взят из памяти о человеке: {p.get('name', city)}. Назови его в ответе; нужен другой — пусть "
                "скажет какой. Сделать его городом для погоды по умолчанию — «Главная» студии → «Утро с Лирой» → «Запомнить город».]")
    elif src:
        note = f"\n[Город не назван — взят город человека из «Утра с Лирой»: {p.get('name', city)}. Назови его в ответе.]"
    return "\n".join(out) + "\n[Прогноз Open-Meteo. Называй только эти числа.]" + note


def home_city(eng):
    """Город человека, когда его не назвали (идея №142, 05.11: «если не указано место — брать моё местоположение из Памяти;
    то же для „Дачи и огорода“»): город «Утра с Лирой» (morning.city) → память («живу в Балашове», «мой город — Гродно»,
    «я из Минска» — как сказано, в падеже: геокодер weatherq ищет по основам). -> (город, "settings" | "memory" | "")."""
    if eng is None:
        return "", ""
    try:
        mine = str(((eng.s.get("morning") or {}) if hasattr(eng, "s") else {}).get("city") or "").strip()
    except Exception:  # noqa: BLE001
        mine = ""
    if mine:
        return mine, "settings"
    try:
        import weatherq as W
        c = W.memory_place(eng.workspace.memory_get())[0]
    except Exception:  # noqa: BLE001 — памяти нет
        c = ""
    return (c, "memory") if c else ("", "")


# Часовые пояса без сети: города, о которых спрашивают чаще всего (отчёт №131, 20.10: «время говорит на 3 часа позднее» —
# модель «посчитала» Омск, вычтя 3 часа вместо прибавления). Остальные — геокодер Open-Meteo (поле timezone).
CITY_TZ = {"москв": "Europe/Moscow", "петербург": "Europe/Moscow", "питер": "Europe/Moscow", "калининград": "Europe/Kaliningrad",
           "самар": "Europe/Samara", "екатеринбург": "Asia/Yekaterinburg", "челябинск": "Asia/Yekaterinburg", "уф": "Asia/Yekaterinburg",
           "тюмен": "Asia/Yekaterinburg", "омск": "Asia/Omsk", "новосибирск": "Asia/Novosibirsk", "томск": "Asia/Tomsk",
           "барнаул": "Asia/Barnaul", "красноярск": "Asia/Krasnoyarsk", "кемерово": "Asia/Novokuznetsk", "новокузнецк": "Asia/Novokuznetsk",
           "иркутск": "Asia/Irkutsk", "улан-удэ": "Asia/Irkutsk", "чит": "Asia/Chita", "якутск": "Asia/Yakutsk",
           "владивосток": "Asia/Vladivostok", "хабаровск": "Asia/Vladivostok", "магадан": "Asia/Magadan",
           "сахалин": "Asia/Sakhalin", "южно-сахалинск": "Asia/Sakhalin", "камчат": "Asia/Kamchatka", "петропавловск-камчатск": "Asia/Kamchatka",
           "минск": "Europe/Minsk", "киев": "Europe/Kyiv", "алмат": "Asia/Almaty", "астан": "Asia/Almaty",
           "ташкент": "Asia/Tashkent", "бишкек": "Asia/Bishkek", "ереван": "Asia/Yerevan", "тбилиси": "Asia/Tbilisi", "баку": "Asia/Baku",
           "лондон": "Europe/London", "париж": "Europe/Paris", "берлин": "Europe/Berlin", "рим": "Europe/Rome", "мадрид": "Europe/Madrid",
           "стамбул": "Europe/Istanbul", "дуба": "Asia/Dubai", "пекин": "Asia/Shanghai", "токио": "Asia/Tokyo", "сеул": "Asia/Seoul",
           "бангкок": "Asia/Bangkok", "дели": "Asia/Kolkata", "нью-йорк": "America/New_York", "чикаго": "America/Chicago",
           "лос-анджелес": "America/Los_Angeles", "сан-франциско": "America/Los_Angeles", "торонто": "America/Toronto",
           "сидне": "Australia/Sydney", "иерусалим": "Asia/Jerusalem", "тель-авив": "Asia/Jerusalem"}


def city_tz(city, geocode=True):
    """Город -> (название, имя часового пояса IANA) или (город, None)."""
    c = city.lower().replace("ё", "е").strip()
    for k, tz in CITY_TZ.items():
        if c.startswith(k) or c == k:
            return city, tz
    if not geocode:
        return city, None
    try:
        g = httpx.get("https://geocoding-api.open-meteo.com/v1/search", params={"name": city, "count": 1, "language": "ru"},
                      headers=UA, timeout=10).json()
        p = (g.get("results") or [None])[0]
        return (p.get("name") or city, p.get("timezone")) if p else (city, None)
    except (httpx.HTTPError, ValueError):
        return city, None


def world_time(city, now=None, geocode=True, prep=""):
    """Который час в городе — по часовому поясу, а не «в уме». prep — «в»/«во», как сказал человек («в Омске»): тогда
    «В Омске сейчас 12:39…», иначе «Омск: сейчас 12:39…». -> строка для человека или None (город не найден)."""
    import datetime as _dt
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    name, tz = city_tz(city, geocode)
    if not tz:
        return None
    try:
        z = ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError):
        return None
    now = now or _dt.datetime.now().astimezone()
    there = now.astimezone(z)
    diff = round((there.utcoffset() - now.utcoffset()).total_seconds() / 3600, 1)
    d = int(diff) if diff == int(diff) else diff
    n = abs(d)
    word = "часа" if n != int(n) else ("час" if n % 10 == 1 and n % 100 != 11 else "часа" if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14 else "часов")
    rel = "как у вас" if diff == 0 else (f"на {str(n).replace('.', ',')} {word} " + ("больше" if diff > 0 else "меньше") + ", чем у вас")
    days = (there.date() - now.date()).days
    day = ", там уже завтра" if days > 0 else ", там ещё вчера" if days < 0 else ""
    if prep:
        return f"{prep.capitalize()} {city[:1].upper() + city[1:]} сейчас {there:%H:%M}{day} — {rel}."
    return f"{name[:1].upper() + name[1:]}: сейчас {there:%H:%M}{day} — {rel}."


def t_world_time(a, ctx):
    city = str(a.get("city") or "").strip()
    if not city:
        raise ToolError("спроси, в каком городе")
    r = world_time(city)
    if not r:
        return f"Город «{city}» не нашёлся — уточни название. Время не считай в уме."
    return r + " [Посчитано по часовому поясу — называй именно это время.]"


def t_read_webpage(a, ctx):
    """Текст страницы, не больше PAGE_MAX символов — чтобы одна страница не съела контекст модели; длинная — начало и
    куски вокруг нужных слов (find или слова вопроса), пустая — честно «текста нет»."""
    eng = ctx.get("engine")
    find, question = (a.get("find") or "").strip(), getattr(eng, "_turn_text", "") if eng else ""
    url = (a.get("url") or "").strip()
    if not re.match(r"^https?://", url):
        raise ToolError("нужен полный адрес страницы")
    import video                                 # YouTube, Rutube, VK: текст ролика — из субтитров (video.py), а не описание
    if video.is_video(url):
        try:
            return video.for_model(url, video.transcript(url))
        except video.NoTranscript as e:
            return video.no_transcript_text(url, e)
        except Exception as e:  # noqa: BLE001 — сеть, yt-dlp: читаем страницу как обычно
            log.info("Субтитры видео не получены: %s", e)
    try:
        r = httpx.get(url, headers=UA, timeout=15, follow_redirects=True)
        r.raise_for_status()
    except httpx.HTTPError as e:
        via = ctx.get("dewiar_web")
        blocked = not isinstance(e, httpx.HTTPStatusError) or e.response.status_code in (403, 451)
        if via and blocked:                                         # сайт не открывается из этой сети (или 403/451 по
                                                                    # стране) — через сервер Dewiar
            try:
                text = via("fetch", url)
                log.info("Страница через сервер Dewiar (напрямую: %s)", e)
                return page_excerpt(text, find, question)
            except Exception as e2:  # noqa: BLE001
                log.info("Страница через сервер Dewiar не открылась: %s", e2)
        raise ToolError(f"страница не открылась: {e}") from e
    if "html" not in r.headers.get("content-type", "html"):
        return page_excerpt(r.text, find, question)
    out = page_excerpt(html_to_text(r.text), find, question)
    links = page_links(r.text, str(r.url))
    if len(links) >= 3 and out != PAGE_EMPTY:      # справочник, документация: что ещё есть на сайте — открыть нужное
        out += "\n\nРазделы этого сайта (нужное можно открыть read_webpage по адресу):\n" + "\n".join(f"- {t} — {u}" for t, u in links)
    return out


def page_links(page, base, limit=30):
    """Ссылки страницы на тот же сайт -> [(текст, адрес)] без повторов, якорей и файлов (для разбора справочников)."""
    from urllib.parse import urljoin, urlparse
    host = urlparse(base).netloc
    seen, out = {base.split("#")[0].rstrip("/")}, []
    for href, inner in re.findall(r'(?is)<a\b[^>]*?href=["\']([^"\'#][^"\']*)["\'][^>]*>(.*?)</a>', page or ""):
        u = urljoin(base, html.unescape(href)).split("#")[0]
        t = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", inner))).strip()
        if urlparse(u).netloc != host or not u.startswith("http") or not t or len(t) > 90 \
                or re.search(r"\.(png|jpe?g|gif|svg|pdf|zip|css|js|xml|ico)(\?|$)", u, re.I) or u.rstrip("/") in seen:
            continue
        seen.add(u.rstrip("/"))
        out.append((t, u))
        if len(out) >= limit:
            break
    return out


def calc_eval(expr, today=None):
    """Безопасный счёт: числа, + - * / // % **, скобки, проценты («17% * 2350», «2350 * 17%»), round abs min max sqrt,
    даты: days_until("2027-01-01") — дней до даты, days_between("2026-10-01", "2026-12-31"), weekday("2026-10-14"),
    date_add("2026-10-10", 30). today — для проверок. -> число или строка. Ошибка — ToolError."""
    import ast
    import datetime as _dt
    import math
    import operator as op
    today = today or _dt.date.today()

    def d(x):
        try:
            return _dt.date.fromisoformat(str(x))
        except ValueError:
            raise ToolError(f"дата «{x}» — нужна в виде ГГГГ-ММ-ДД")
    WDN = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
    fns = {"round": round, "abs": abs, "min": min, "max": max, "sqrt": math.sqrt, "floor": math.floor, "ceil": math.ceil,
           "days_until": lambda x: (d(x) - today).days, "days_between": lambda a, b: (d(b) - d(a)).days,
           "weekday": lambda x: WDN[d(x).weekday()], "date_add": lambda x, n: (d(x) + _dt.timedelta(days=int(n))).isoformat(),
           "today": lambda: today.isoformat()}
    ops = {ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul, ast.Div: op.truediv, ast.FloorDiv: op.floordiv,
           ast.Mod: op.mod, ast.Pow: op.pow, ast.USub: op.neg, ast.UAdd: op.pos}
    src = str(expr or "").strip().replace("×", "*").replace("÷", "/").replace("^", "**")
    src = re.sub(r"(\d)\s+(?=\d{3}\b)", r"\1", src)                  # «1 437» — одно число
    src = re.sub(r"(?<=\d),(?=\d)", ".", src)                           # 399,5 → 399.5
    src = re.sub(r"(\d+(?:\.\d+)?)\s*%", r"(\1/100)", src)              # 17% → (17/100)
    if not src or len(src) > 300:
        raise ToolError("пустое или слишком длинное выражение")

    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float, str)):
            return n.value
        if isinstance(n, ast.BinOp) and type(n.op) in ops:
            a, b = ev(n.left), ev(n.right)
            if isinstance(n.op, ast.Pow) and abs(b) > 100:
                raise ToolError("слишком большая степень")
            return ops[type(n.op)](a, b)
        if isinstance(n, ast.UnaryOp) and type(n.op) in ops:
            return ops[type(n.op)](ev(n.operand))
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in fns and not n.keywords:
            return fns[n.func.id](*[ev(x) for x in n.args])
        raise ToolError("в выражении можно только числа, + - * / % ( ) и функции: " + ", ".join(fns))
    try:
        r = ev(ast.parse(src, mode="eval"))
    except ToolError:
        raise
    except ZeroDivisionError:
        raise ToolError("деление на ноль")
    except (SyntaxError, TypeError, ValueError) as e:
        raise ToolError(f"не понял выражение: {e}")
    if isinstance(r, float):
        r = round(r, 10)
        if r.is_integer():
            r = int(r)
    return r


def t_calc(a, ctx):
    r = calc_eval(a.get("expression", ""))
    shown = str(r).replace(".", ",") if isinstance(r, float) else str(r)
    return f"{a.get('expression', '').strip()} = {shown}"
