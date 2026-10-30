"""«Руки» ассистента: инструменты, которые модель вызывает сама (обработчики t_*), реестр TOOLS, Toolbox и напоминания.
TOOLS[имя] = (описание для модели, JSON-схема, риск, обработчик(args, ctx), название в студии). Риск "safe" — сразу,
"confirm" — сначала «Выполнить?» голосом и кнопками в виджете; в студии любой инструмент можно выключить или потребовать
подтверждение (настройки tools.enabled / tools.confirm). Команды и удаление дополнительно проверяет guard.py.
ctx обработчика — настройки, напоминания, навыки и Toolbox.hooks (объекты ядра, кладёт engine.py).
Описания и тексты результатов — подсказки модели: их правка меняет её поведение. Действия на рабочем столе записаны
командами Linux (xdg-open, gio, gdbus); на Windows их переводят launch() и winsys.py.
"""

import html
import json
import logging
import os
import re
import shlex
import shutil
import subprocess
import threading
import time
import urllib.parse
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import httpx

from settings import STATE_DIR, WIN

if WIN:
    import winsys

log = logging.getLogger("dewiar.tools")
DRY = os.environ.get("DEWIAR_DRY_TOOLS")          # тесты: путь к файлу, куда пишутся команды вместо запуска программ
EXAM_LAUNCH = os.environ.get("DEWIAR_EXAM_LAUNCH")   # экзамен: программы и браузер не запускаем, а записываем (core/exam.py)
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Dewiar/0.12" if WIN else "Mozilla/5.0 (X11; Linux x86_64) Dewiar/0.8"}


class ToolError(Exception):
    """Ожидаемый отказ инструмента: текст уходит модели результатом («Ошибка: …»), и она пересказывает его человеку.
    Поэтому тексты часто содержат и указание модели, что делать дальше."""
    pass


RADIO = []          # проигрыватель радио ядра (кладёт engine.py) — media_playing() учитывает и своё радио


# ---------- окружение рабочего стола ----------

def desktop_env():
    """Окружение для запуска программ на рабочем столе. Linux: служба systemd --user может стартовать раньше
    графического сеанса и не знать DISPLAY/WAYLAND_DISPLAY и шины D-Bus — берём их у systemctl --user show-environment."""
    env = dict(os.environ)
    env.pop("DEWIAR_BOX", None)
    if WIN:
        return env
    if not (env.get("DISPLAY") or env.get("WAYLAND_DISPLAY")):
        try:
            out = subprocess.run(["systemctl", "--user", "show-environment"], capture_output=True, text=True,
                                 timeout=3).stdout
            for line in out.splitlines():
                k, _, v = line.partition("=")
                if k in ("DISPLAY", "WAYLAND_DISPLAY", "XAUTHORITY", "XDG_CURRENT_DESKTOP", "DBUS_SESSION_BUS_ADDRESS"):
                    env.setdefault(k, v)
        except (OSError, subprocess.SubprocessError):
            pass
    return env


def launch(cmd):
    """Запустить программу отсоединённо (она переживёт ассистента). Команды — в терминах Linux (xdg-open, gio launch,
    gtk-launch); на Windows из них берётся последний аргумент и открывается «как двойным щелчком», прочее — ToolError.
    В тестах (DRY) команда только записывается в файл."""
    if DRY or EXAM_LAUNCH:
        with open(DRY or EXAM_LAUNCH, "a", encoding="utf-8") as f:
            f.write(json.dumps(cmd, ensure_ascii=False) + "\n")
        return
    if WIN:
        target = cmd[-1] if cmd[0] in ("xdg-open", "gio", "gtk-launch") else None
        if target is None:
            raise ToolError("это действие недоступно в Windows")
        try:
            winsys.startfile(target)
        except OSError as e:
            raise ToolError(f"не открылось: {e}") from e
        return
    import memcap                       # своя коробка systemd: программа не закроется при перезапуске ядра
    subprocess.Popen(memcap.scope_cmd(cmd), env=desktop_env(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)


_BROWSER_NEW_WINDOW = re.compile(r"chrome|chromium|firefox|yandex|brave|opera|vivaldi|edge|librewolf|floorp|waterfox", re.I)


def browser_cmd(url):
    """Команда открыть адрес в браузере — в НОВОМ окне (отзыв 17.10: «включи смешное видео на YouTube» раз сработало, потом
    «включаю» — и ничего: ролик открывался новой вкладкой в окне браузера, которое было свёрнуто или на другом мониторе).
    Браузер по умолчанию (xdg-settings) из семейства Chrome/Firefox — с --new-window; иначе и в тестах — xdg-open."""
    if DRY or WIN:
        return ["xdg-open", url]
    try:
        desk = subprocess.run(["xdg-settings", "get", "default-web-browser"], capture_output=True, text=True, timeout=3,
                              env=desktop_env()).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        desk = ""
    if not desk.endswith(".desktop") or not _BROWSER_NEW_WINDOW.search(desk):
        return ["xdg-open", url]
    dirs = [Path.home() / ".local/share/applications", Path("/usr/share/applications"), Path("/usr/local/share/applications"),
            Path("/var/lib/snapd/desktop/applications"), Path("/var/lib/flatpak/exports/share/applications"),
            Path.home() / ".local/share/flatpak/exports/share/applications"]
    for d in dirs:
        f = d / desk
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        m = re.search(r"^Exec=(.+)$", text.split("[Desktop Action", 1)[0], re.M)
        if not m:
            break
        try:
            parts = [x for x in shlex.split(m.group(1)) if not x.startswith("%")]
        except ValueError:
            break
        if parts and not any(x in ("--new-window", "-new-window") for x in parts):
            return parts + ["--new-window", url]
        break
    return ["xdg-open", url]


# ---------- инструменты ----------

def t_open_url(a, ctx):
    url = (a.get("url") or "").strip()
    if not re.match(r"^https?://", url):
        url = "https://" + url
    if not re.match(r"^https?://[^\s/$.?#].[^\s]*$", url):
        raise ToolError("это не похоже на адрес сайта")
    launch(browser_cmd(url))
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
        launch(["xdg-open", r["url"]])
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


def t_web_search(a, ctx):
    q = (a.get("query") or "").strip()
    if not q:
        raise ToolError("пустой запрос")
    searx = ctx["settings"].get("tools", "search_url") or ""
    via = ctx.get("dewiar_web")                                     # запасной путь: поиск через сервер Dewiar
    try:
        if searx:                                                   # свой SearXNG (JSON)
            r = httpx.get(searx.rstrip("/") + "/search", params={"q": q, "format": "json", "language": "ru"},
                          headers=UA, timeout=12)
            r.raise_for_status()
            res = [{"title": x.get("title", ""), "url": x.get("url", ""), "snippet": x.get("content", "")}
                   for x in r.json().get("results", [])]
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
    if not res:
        return "Ничего не нашлось."
    # 6 результатов хватает модели и не раздувает контекст
    return "\n".join(f"{i + 1}. {x['title']} — {x['snippet']} ({x['url']})" for i, x in enumerate(res[:6]))


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
    words = sorted({w for w in re.findall(r"[\w-]{4,}", q)}, key=len, reverse=True)
    tries = [q] + ([w for w in words if w.lower() != q.lower()][:2] if len(q.split()) > 1 else [])
    items, err = [], None
    for qq in tries:
        try:
            items = IM.search(qq, n, searx_url=ctx["settings"].get("tools", "search_url") or "", via=ctx.get("dewiar_web"))
        except httpx.HTTPError as e:
            err = e
            continue
        if items:
            break
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


def t_app_update(a, ctx):
    """«Проверь свои обновления» (жалоба №147, 20.10: «сам не проверяет и по просьбе не может»). Проверяет сайт сейчас же;
    новое скачивается и проверяется, в виджете появляется «Доступна версия … — нажмите, чтобы обновить"."""
    eng = ctx.get("engine")
    up = getattr(eng, "updater", None)
    if up is None:
        raise ToolError("обновления отсюда не проверить")
    info = up.check()
    st = up.public()
    cur = st.get("current") or ""
    if info:
        return (f"Есть новая версия Dewiar {info['version']} (сейчас {cur}); она уже скачана и проверена. В виджете — плашка "
                f"«Доступна версия {info['version']} — нажмите, чтобы обновить»: обновление ставит человек одним нажатием, "
                "разговор и настройки сохранятся. Скажи это коротко; сама не ставь.")
    if st.get("error"):
        return (f"Проверить обновления сейчас не получилось ({str(st['error'])[:160]}). Установлена {cur}. Скажи коротко и "
                "предложи попробовать позже; в студии — «О программе» → «Проверить обновления».")
    return f"Обновлений нет: установлена последняя версия Dewiar {cur}. Скажи это одной фразой."


def t_weather(a, ctx):
    """Погода из Open-Meteo (как на телефоне, app.js weather): сейчас и по дням. Экзамен 16.10: компьютер искал сайт погоды,
    сайт отдал одно меню — и модель выдумала «+7…+12». Здесь — настоящие числа или честная ошибка."""
    import datetime as _dt
    city = str(a.get("city") or "").strip()
    days = max(1, min(7, int(float(a.get("days") or 3))))
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
    return "\n".join(out) + "\n[Прогноз Open-Meteo. Называй только эти числа.]"


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


def desktop_apps():
    """Все программы из меню -> [{name, ru, keywords, id, path}]. Linux — по файлам .desktop (системные, свои, snap,
    flatpak), Windows — winsys.apps(). DEWIAR_APPS_DIR — тесты: только эта папка .desktop."""
    if WIN and not os.environ.get("DEWIAR_APPS_DIR"):
        return winsys.apps()
    dirs = [Path("/usr/share/applications"), Path("/usr/local/share/applications"),
            Path.home() / ".local/share/applications", Path("/var/lib/snapd/desktop/applications"),
            Path("/var/lib/flatpak/exports/share/applications"),
            Path.home() / ".local/share/flatpak/exports/share/applications"]
    extra = os.environ.get("DEWIAR_APPS_DIR")
    if extra:
        dirs = [Path(extra)]
    apps, seen = [], set()
    for d in dirs:
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.desktop")):
            if f.name in seen:
                continue
            try:
                txt = f.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            sec = txt.split("[Desktop Action")[0]
            if re.search(r"(?m)^(NoDisplay|Hidden)=true", sec) or not re.search(r"(?m)^Type=Application", sec):
                continue
            name = re.search(r"(?m)^Name=(.+)$", sec)
            ru = re.search(r"(?m)^Name\[ru\]=(.+)$", sec)
            kw = re.search(r"(?m)^Keywords(?:\[ru\])?=(.+)$", sec)
            if name:
                seen.add(f.name)
                apps.append({"name": name.group(1).strip(), "ru": ru.group(1).strip() if ru else "",
                             "keywords": kw.group(1).strip() if kw else "", "id": f.stem, "path": str(f)})
    return apps


# как программы называют вслух -> слово из их английского названия
APP_ALIASES = {"телеграм": "telegram", "телеграмм": "telegram", "хром": "chrome", "гугл хром": "chrome",
               "фаерфокс": "firefox", "файрфокс": "firefox", "мозилла": "firefox", "терминал": "terminal",
               "консоль": "terminal", "вскод": "code", "вс код": "code", "визуал студио": "code", "стим": "steam",
               "дискорд": "discord", "спотифай": "spotify", "зум": "zoom", "обс": "obs", "вайбер": "viber",
               "ватсап": "whatsapp", "либреофис": "libreoffice", "ворд": "writer", "эксель": "calc",
               "настройки": "settings", "файлы": "files", "яндекс музыка": "yandex music", "яндекс музыку": "yandex music",
               "яндекс.музыка": "yandex music", "проводник": "files", "гимп": "gimp", "блендер": "blender"}
# транслитерация: «телеграм» -> «telegram», чтобы находить программы без русского названия
_TR = dict(zip("абвгдеёжзийклмнопрстуфхцчшщъыьэюя", ["a", "b", "v", "g", "d", "e", "e", "zh", "z", "i", "y", "k", "l", "m",
               "n", "o", "p", "r", "s", "t", "u", "f", "h", "ts", "ch", "sh", "sch", "", "y", "", "e", "yu", "ya"]))


def find_app(query, apps):
    """Программа по словам пользователя -> элемент apps | None. Сравниваем с названием, русским названием, id
    и ключевыми словами (как есть, через APP_ALIASES и транслитерацию); ниже похожести 0.72 — не угадываем."""
    import difflib
    q = query.lower().strip()
    variants = {q, APP_ALIASES.get(q, q), "".join(_TR.get(ch, ch) for ch in q)}
    best, score = None, 0.0
    for a in apps:
        names = [a["name"], a["ru"], a["id"].split(".")[-1]] + [k for k in a["keywords"].split(";") if k]
        for n in names:
            n = n.lower().strip()
            if not n:
                continue
            for v in variants:
                s = 1.0 if n == v else 0.9 if (v in n or n in v) and len(v) >= 3 else difflib.SequenceMatcher(None, v, n).ratio()
                if s > score:
                    best, score = a, s
    return best if score >= 0.72 else None


def t_open_app(a, ctx):
    q = (a.get("name") or "").strip()
    apps = desktop_apps()
    app = find_app(q, apps)
    if not app:
        sample = ", ".join(sorted({x["ru"] or x["name"] for x in apps})[:40])
        raise ToolError(f"не нашёл программу «{q}». Установлены, например: {sample}")
    launch(["gio", "launch", app["path"]] if shutil.which("gio") or DRY else ["gtk-launch", app["id"]])
    if ctx.get("music_app") and re.search(r"yandex.?music|яндекс.?музык", f"{app.get('id', '')} {app['name']} {app['ru']}".lower()):
        ctx["music_app"]("yandex")                  # запомнить: следующие «включи электронную», «играй» — в ней
    return f"Запустил {app['ru'] or app['name']}"


def t_open_path(a, ctx):
    p = Path(os.path.expanduser((a.get("path") or "~").strip()))
    aliases = {"загрузки": "Downloads", "документы": "Documents", "рабочий стол": "Desktop", "музыка": "Music",
               "изображения": "Pictures", "видео": "Videos"}
    low = str(a.get("path", "")).lower().strip()
    if low in aliases and WIN:
        cand = [winsys.known_folder(aliases[low])]
    if low in aliases and not WIN:
        cand = [Path.home() / aliases[low], Path.home() / low.capitalize()]
    if low in aliases:
        p = next((c for c in cand if c.exists()), cand[0])
    if not p.exists() and not DRY:
        raise ToolError(f"нет такого пути: {p}")
    launch(["xdg-open", str(p)])
    return f"Открыл {p}"


def _mpris_status(env, player):
    """PlaybackStatus плеера MPRIS: Playing / Paused / Stopped или ""."""
    try:
        out = subprocess.run(["gdbus", "call", "--session", "--dest", player, "--object-path", "/org/mpris/MediaPlayer2",
                              "--method", "org.freedesktop.DBus.Properties.Get", "org.mpris.MediaPlayer2.Player",
                              "PlaybackStatus"], capture_output=True, text=True, env=env, timeout=3).stdout
    except (OSError, subprocess.SubprocessError):
        return ""
    m = re.search(r"(Playing|Paused|Stopped)", out)
    return m.group(1) if m else ""


def _mpris_players(env, prefer=""):
    """Плееры MPRIS (браузер, Яндекс Музыка, Spotify…). prefer — «yandex»: такой плеер (по имени или подписи) первым."""
    out = subprocess.run(["gdbus", "call", "--session", "--dest", "org.freedesktop.DBus", "--object-path",
                          "/org/freedesktop/DBus", "--method", "org.freedesktop.DBus.ListNames"],
                         capture_output=True, text=True, env=env, timeout=4).stdout
    players = re.findall(r"'(org\.mpris\.MediaPlayer2\.[^']+)'", out)
    if prefer and len(players) > 1:
        def who(pl):
            try:
                r = subprocess.run(["gdbus", "call", "--session", "--dest", pl, "--object-path", "/org/mpris/MediaPlayer2",
                                    "--method", "org.freedesktop.DBus.Properties.Get", "org.mpris.MediaPlayer2", "Identity"],
                                   capture_output=True, text=True, env=env, timeout=3).stdout
            except (OSError, subprocess.SubprocessError):
                r = ""
            return (pl + " " + r).lower()
        players.sort(key=lambda pl: 0 if any(w in who(pl) for w in MUSIC_APPS.get(prefer, {}).get("words", (prefer,))) else 1)
    return players


# Музыкальные приложения, которыми ассистент умеет управлять: поиск по ссылке приложения и кнопки плеера (MPRIS).
# words — как узнать плеер среди MPRIS по имени на шине или Identity
MUSIC_APPS = {"yandex": {"name": "Яндекс Музыка", "words": ("yandex", "яндекс"), "scheme": "yandexmusic",
                         "web": "https://music.yandex.ru"}}


def yandex_music_installed():
    """Стоит ли приложение Яндекс Музыки (оно открывает ссылки yandexmusic://)."""
    if DRY:
        return bool(os.environ.get("DEWIAR_FAKE_YANDEX_APP"))
    if WIN:
        try:
            import winreg
            winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "yandexmusic"))
            return True
        except OSError:
            return False
    try:
        r = subprocess.run(["xdg-mime", "query", "default", "x-scheme-handler/yandexmusic"], capture_output=True, text=True,
                           env=desktop_env(), timeout=4)
        if r.stdout.strip():
            return True
    except (OSError, subprocess.SubprocessError):
        pass
    return any("yandex" in (x.get("id") or "").lower() and "music" in (x.get("id") or "").lower() for x in desktop_apps())


def t_yandex_music(a, ctx):
    """Открыть в Яндекс Музыке поиск (жанр, исполнитель, песня) — в приложении, если оно стоит, иначе на сайте."""
    q = (a.get("query") or "").strip()
    path = "search?text=" + urllib.parse.quote(q) if q else ""
    app = yandex_music_installed()
    url = ("yandexmusic://" + path) if app else (MUSIC_APPS["yandex"]["web"] + "/" + path)
    launch(browser_cmd(url))
    hook = ctx.get("music_app")
    if hook:
        hook("yandex")
    where = "в приложении Яндекс Музыки" if app else "на сайте Яндекс Музыки"
    return (f"Открыл {where}" + (f" поиск «{q}»" if q else "") + ". Чтобы заиграло, нажмите на трек или плейлист — "
            "или скажите «играй», и я нажму воспроизведение.")


def t_play_radio(a, ctx):
    from radio import RadioError, pick, search
    r = ctx.get("radio")
    if not r:
        raise ToolError("радио недоступно")
    q = (a.get("query") or "").strip()
    url = (a.get("url") or "").strip()
    eng = ctx.get("engine")
    if url.startswith(("http://", "https://")):          # №359: ссылка на поток — играем её и запоминаем своей станцией
        st = eng.radio_custom_save(q, url) if eng is not None and hasattr(eng, "radio_custom_save") else {"name": q or "Своя станция", "url": url}
        found, mine = [dict(st, tags="своя", own=True)], True
    else:
        mine = ctx.get("music").match(q or "*") if ctx.get("music") else []     # сначала свой список станций (с сайта Dewiar)
    if url.startswith(("http://", "https://")):
        st = found[0]
    elif mine:
        found = mine[:6]
        st = found[0]
    else:
        try:
            found = search(q)
        except RadioError as e:
            raise ToolError(str(e)) from e
        st = pick(found, q)
    if not st:
        raise ToolError(f"не нашёл радиостанцию «{q}»")
    from radio import RadioError as RE
    try:
        r.play(st)
    except RE as e:
        raise ToolError(str(e)) from e
    # станция могла не ответить или зависнуть на подключении (ffmpeg жив, а звука нет) — ждём звук и пробуем другую
    if not r.wait_sound(6):
        r.stop()
        alt = next((x for x in found if x is not st), None)
        if alt:
            r.play(alt)
            if r.wait_sound(6):
                st = alt
            else:
                r.stop()
        if not r.sounding:
            why = r.failed or "не отвечает"
            fails = ctx.setdefault("radio_fails", [])
            fails.append(time.time())
            fails[:] = [x for x in fails if time.time() - x < 600]
            if len(fails) >= 2:                          # вторая неудача за 10 минут — дело не в станции: ищем, где поломка
                from radio import diagnose
                from eyes import ffmpeg_path
                where, fix = diagnose(ffmpeg_path(), st["url"])
                log.warning("Радио: проверка — %s; %s", where, fix)
                raise ToolError(f"радио не играет, и дело не в станции: {where}. Что сделать: {fix}. "
                                "Перескажи это пользователю простыми словами и не пробуй другие станции.")
            raise ToolError(f"станция «{st['name']}» не играет ({why}) — можно попробовать другую")
    others = ", ".join(x["name"] for x in found if x is not st)[:200]
    return (f"Играет радио «{st['name']}». Остановить — «стоп» или «пауза», продолжить — «продолжи»."
            + (f" Другие станции по запросу: {others}." if others else "") + " Скажи коротко, что включил, одной фразой.")


def t_play_youtube(a, ctx):
    """Ролик на YouTube: найти первый через yt_dlp и открыть в браузере (сразу воспроизводится).
    Нет yt_dlp или он не справился — открываем страницу поиска."""
    q = (a.get("query") or "").strip()
    if not q:
        raise ToolError("что найти на YouTube?")
    url = None
    if not DRY:
        try:
            import yt_dlp
            with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "extract_flat": True}) as y:
                info = y.extract_info(f"ytsearch1:{q}", download=False)
            e = (info.get("entries") or [None])[0]
            if e:
                url = f"https://www.youtube.com/watch?v={e['id']}"
                title = e.get("title") or q
        except Exception as ex:  # noqa: BLE001
            log.info("Поиск на YouTube: %s", ex)
    if not url:
        url, title = "https://www.youtube.com/results?search_query=" + urllib.parse.quote(q), None
    launch(browser_cmd(url))
    return f"Открыл на YouTube: «{title}»." if title else f"Открыл поиск на YouTube: {q}."


def media_players():
    """Сколько открыто плееров (MPRIS); None — узнать нельзя (Windows)."""
    if WIN:
        return None
    if DRY:
        return 1 if os.environ.get("DEWIAR_FAKE_PLAYING") or os.environ.get("DEWIAR_FAKE_PLAYER") else 0
    try:
        return len(_mpris_players(desktop_env())) if shutil.which("gdbus") else None
    except (OSError, subprocess.SubprocessError):
        return None


def media_playing():
    """Играет ли сейчас музыка/видео (MPRIS: браузер, плеер). True/False; None — узнать нельзя (Windows)."""
    r = RADIO[0] if RADIO else None
    if r is not None and r.playing:
        return True
    if WIN or DRY:
        return None if WIN else bool(os.environ.get("DEWIAR_FAKE_PLAYING"))
    env = desktop_env()
    try:
        if shutil.which("playerctl"):
            out = subprocess.run(["playerctl", "-a", "status"], capture_output=True, text=True, env=env, timeout=3).stdout
            return "Playing" in out
        for pl in _mpris_players(env) if shutil.which("gdbus") else []:
            out = subprocess.run(["gdbus", "call", "--session", "--dest", pl, "--object-path", "/org/mpris/MediaPlayer2",
                                  "--method", "org.freedesktop.DBus.Properties.Get", "org.mpris.MediaPlayer2.Player",
                                  "PlaybackStatus"], capture_output=True, text=True, env=env, timeout=3).stdout
            if "Playing" in out:
                return True
    except (OSError, subprocess.SubprocessError):
        return None
    return False


def t_media(a, ctx):
    action = a.get("action", "play_pause")
    r = ctx.get("radio")
    prefer = (ctx.get("music_pref") or (lambda: ""))()          # недавно открыта Яндекс Музыка — управляем ею
    # своё радио ядра — не MPRIS-плеер: кнопки для него обрабатываем сами
    if r and (r.playing or r.paused) and action in ("play", "pause", "play_pause", "stop", "next"):
        if action in ("pause", "stop") or (action == "play_pause" and r.playing):
            st = r.pause()
            return f"Радио «{(st or {}).get('name', '')}» на паузе"
        if action == "next" and r.station:
            from radio import search
            cur = r.station
            alts = [x for x in search(" ".join((cur.get("tags") or "").split(",")[:1]) or "") if x["url"] != cur["url"]]
            if alts:
                r.play(alts[0])
                return f"Следующая станция: «{alts[0]['name']}»"
        st = r.resume()
        if st:
            return f"Снова играет «{st['name']}»"
    methods = {"play": "Play", "pause": "Pause", "play_pause": "PlayPause", "next": "Next", "previous": "Previous",
               "stop": "Stop"}
    if action not in methods:
        raise ToolError("неизвестное действие")
    if DRY:
        launch(["media", action, prefer])
        return "Готово"
    if WIN:
        winsys.media(action)
        return "Готово"
    env = desktop_env()
    done = {"play": "Включил воспроизведение", "pause": "Поставил на паузу", "play_pause": "Нажал «играть/пауза»",
            "next": "Следующий трек", "previous": "Предыдущий трек", "stop": "Остановил"}[action]
    app = MUSIC_APPS.get(prefer, {}).get("name", "")
    players = _mpris_players(env, prefer) if shutil.which("gdbus") else []
    if len(players) > 1 and not prefer:                    # «пауза» — тому, кто играет; «играй» — тому, кто на паузе
        want = {"pause": "Playing", "stop": "Playing", "play": "Paused"}.get(action)
        if want:
            def status(pl):
                try:
                    return subprocess.run(["gdbus", "call", "--session", "--dest", pl, "--object-path", "/org/mpris/MediaPlayer2",
                                           "--method", "org.freedesktop.DBus.Properties.Get", "org.mpris.MediaPlayer2.Player",
                                           "PlaybackStatus"], capture_output=True, text=True, env=env, timeout=3).stdout
                except (OSError, subprocess.SubprocessError):
                    return ""
            players.sort(key=lambda pl: 0 if want in status(pl) else 1)
    if players:
        r = subprocess.run(["gdbus", "call", "--session", "--dest", players[0], "--object-path", "/org/mpris/MediaPlayer2",
                            "--method", f"org.mpris.MediaPlayer2.Player.{methods[action]}"], capture_output=True, env=env,
                           timeout=5)
        if r.returncode == 0:
            hit = app and any(w in players[0].lower() for w in MUSIC_APPS[prefer]["words"])
            want = {"play": "Playing", "pause": "Paused", "stop": "Stopped"}.get(action)
            if want:                                       # проверим, что плеер правда послушался, а не просто принял команду
                time.sleep(1.2)
                st = _mpris_status(env, players[0])
                if st and st != want and not (want == "Paused" and st == "Stopped"):
                    log.info("MPRIS %s: после %s состояние %s", players[0], methods[action], st)
                    return ("Нажал «играть», но плеер так и не заиграл — нажмите воспроизведение в самом приложении"
                            if want == "Playing" else "Нажал «пауза», но плеер продолжает играть")
            return done + (f" — {app}" if hit else "")
    if shutil.which("playerctl"):
        cmd = {"play_pause": "play-pause"}.get(action, action)
        r = subprocess.run(["playerctl", cmd], capture_output=True, text=True, env=env, timeout=5)
        if r.returncode == 0:
            return done
    raise ToolError("не вижу запущенного плеера — откройте музыку в браузере или в приложении (например, Яндекс Музыке)")


def t_play_music(a, ctx):
    q = (a.get("query") or "").strip()
    url = "https://music.youtube.com/search?q=" + urllib.parse.quote(q) if q else "https://music.youtube.com/"
    launch(browser_cmd(url))
    return f"Открыл YouTube Music{': ' + q if q else ''}. Пользователь нажмёт воспроизведение."


def desktop_notify(text, critical=False, env=None):
    """Всплывающее уведомление: notify-send, а если его нет — напрямую через D-Bus (gdbus из GLib есть почти всегда).
    -> показано ли."""
    if WIN:
        return winsys.notify(text)
    env = env or desktop_env()
    try:
        if shutil.which("notify-send"):
            subprocess.Popen(["notify-send", "-a", "Dewiar"] + (["-u", "critical"] if critical else []) + ["Dewiar", text],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
            return True
        if shutil.which("gdbus"):
            hints = "{'urgency': <byte 2>}" if critical else "{}"
            subprocess.Popen(["gdbus", "call", "--session", "--dest", "org.freedesktop.Notifications",
                              "--object-path", "/org/freedesktop/Notifications",
                              "--method", "org.freedesktop.Notifications.Notify",
                              "Dewiar", "0", "dewiar-assistant", "Dewiar", text, "[]", hints, "-1"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
            return True
    except OSError as e:
        log.info("Уведомление не показано: %s", e)
    return False


def human_error(e):
    """Техническая ошибка -> понятная человеку причина (сырые «No module named …», «[Errno 2]» — только в журнал)."""
    t = str(e)
    if isinstance(e, ImportError) or "No module named" in t or "cannot import" in t:
        return "на этом устройстве нет нужной части программы"
    if isinstance(e, PermissionError) or "Permission denied" in t:
        return "нет прав"
    if isinstance(e, FileNotFoundError) or "No such file" in t:
        return "не нашёл нужный файл или программу"
    if isinstance(e, TimeoutError) or "timed out" in t.lower():
        return "не дождался ответа"
    if re.search(r"[A-Za-z]{4,}", t) and not re.search(r"[А-Яа-яЁё]", t):
        return "сбой в системе (подробности — в журнале)"
    return re.sub(r"^(?:не получилось [^:]+:\s*)+", "", t, flags=re.I)


def t_volume(a, ctx):
    """Громкость: percent (0–150, выше 100 — усиление PulseAudio), change (±), mute."""
    if DRY:
        launch(["volume", a])
        return "Готово"
    if WIN:
        if a.get("mute") is None and a.get("percent") is None and a.get("change") is None:
            raise ToolError("укажите percent, change или mute")
        v = winsys.volume(percent=a.get("percent"), change=a.get("change"), mute=a.get("mute"))
        if a.get("mute") is not None and a.get("percent") is None and a.get("change") is None:
            return "Звук выключен" if a["mute"] else "Звук включён"
        return f"Громкость {v}%" if v is not None else "Готово"
    if not shutil.which("pactl"):                          # нет pactl — через libpulse напрямую (pulse.py)
        import pulse
        try:
            pulse.volume(percent=None if a.get("percent") is None else int(a["percent"]),
                         change=None if a.get("change") is None else int(a["change"]), mute=a.get("mute"))
        except Exception as e:  # noqa: BLE001
            raise ToolError(human_error(e)) from e
        if a.get("mute") is not None:
            return "Звук выключен" if a["mute"] else "Звук включён"
        if a.get("percent") is not None:
            return f"Громкость {max(0, min(150, int(a['percent'])))}%"
        if a.get("change") is not None:
            return f"Громкость {'+' if int(a['change']) >= 0 else ''}{int(a['change'])}%"
        raise ToolError("укажите percent, change или mute")
    if a.get("mute") is not None:
        subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "1" if a["mute"] else "0"], timeout=4)
        return "Звук выключен" if a["mute"] else "Звук включён"
    if a.get("percent") is not None:
        v = max(0, min(150, int(a["percent"])))
        subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{v}%"], timeout=4)
        return f"Громкость {v}%"
    if a.get("change") is not None:
        d = int(a["change"])
        subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{'+' if d >= 0 else '-'}{abs(d)}%"], timeout=4)
        return f"Громкость {'+' if d >= 0 else ''}{d}%"
    raise ToolError("укажите percent, change или mute")


def t_system(a, ctx):
    if WIN:
        du = shutil.disk_usage(str(Path.home()))
        return "; ".join(winsys.system_parts() + [f"диск: свободно {du.free / 1e9:.0f} из {du.total / 1e9:.0f} ГБ"])
    parts = []
    bats = list(Path("/sys/class/power_supply").glob("BAT*"))
    for b in bats:
        try:
            cap = (b / "capacity").read_text().strip()
            st = (b / "status").read_text().strip()
            parts.append(f"батарея {cap}% ({ {'Charging': 'заряжается', 'Discharging': 'разряжается', 'Full': 'заряжена'}.get(st, st)})")
        except OSError:
            pass
    try:
        load = os.getloadavg()[0]
        parts.append(f"нагрузка процессора {load:.1f} на {os.cpu_count()} ядер")
    except OSError:
        pass
    try:
        mem = dict(re.findall(r"(\w+):\s+(\d+)", Path("/proc/meminfo").read_text()))
        tot, av = int(mem["MemTotal"]) / 1048576, int(mem["MemAvailable"]) / 1048576
        parts.append(f"память: свободно {av:.1f} из {tot:.1f} ГБ")
    except (OSError, KeyError):
        pass
    du = shutil.disk_usage(str(Path.home()))
    parts.append(f"диск: свободно {du.free / 1e9:.0f} из {du.total / 1e9:.0f} ГБ")
    try:                                   # кто занимает память — чтобы можно было предложить закрыть лишнее
        from device import top_memory
        from memcap import dewiar_memory
        top = top_memory(4)
        if top:
            parts.append("больше всего памяти занимают: " + ", ".join(f"{k} {v} ГБ" for k, v in top))
        own = dewiar_memory()
        if own["core"] >= 0.1:
            parts.append(f"сам Dewiar: {own['core'] + own['ui']:.1f} ГБ (ядро {own['core']:.1f}, окна {own['ui']:.1f})")
    except Exception:  # noqa: BLE001
        pass
    return "; ".join(parts)


def t_run_command(a, ctx):
    """Команда терминала в домашней папке (30 с, с sudo — 180 с). Безопасность: guard.check_command отсекает опасное,
    пароль sudo в команде запрещён — sudo переписывается в sudo -A, и пароль спрашивает системное окно (askpass),
    мимо ассистента и журналов."""
    cmd = (a.get("command") or "").strip()
    if not cmd:
        raise ToolError("пустая команда")
    import guard
    v = guard.check_command(cmd)
    if v["level"] == "block":
        raise ToolError(f"защита Dewiar не выполнит это: {v['reason']}. Объясни пользователю, что такое действие опасно "
                        "для компьютера и ассистент его не делает; предложи безопасный вариант (например, удалить "
                        "конкретные файлы в корзину)")
    if PASS_IN_CMD.search(cmd):
        raise ToolError("пароль в команду не вставляю — он остался бы в истории и журналах. Выполни ту же команду с обычным "
                        "sudo (без -S и echo): Dewiar сам покажет пользователю окно для пароля. И не проси пароль в разговоре")
    if DRY:
        launch(["bash", "-lc", cmd])
        return "выполнено (тест)"
    if WIN:
        try:
            r = winsys.shell(cmd, timeout=30, cwd=str(Path.home()))
        except subprocess.TimeoutExpired:                  # №267, №302 (пакет 27.10): было необработанное исключение и автоотчёт
            return ("команда не закончилась за 30 с — остановил. Если она долгая (обход сетевого диска, поиск по всему "
                    "диску), сузь её или запусти в фоне: Start-Job { … }")
        out = ((r.stdout or "") + ("\n" + r.stderr if r.stderr else "")).strip()
        return f"код выхода {r.returncode}\n{out[-3000:]}"
    env, timeout = desktop_env(), 30
    if SUDO_AT.search(cmd):                                # пароль — в окне системы, не через ассистента
        cmd = SUDO_AT.sub(r"\1sudo -A ", cmd)
        env = dict(env, SUDO_ASKPASS=askpass_path())
        timeout = 180                                      # человеку нужно время ввести пароль
    try:
        r = subprocess.run(["bash", "-lc", cmd], capture_output=True, text=True, timeout=timeout, env=env,
                           cwd=str(Path.home()))
    except subprocess.TimeoutExpired:
        return f"команда не закончилась за {timeout} с — остановил. Если она долгая, запусти её в фоне или раздели на части"
    out = (r.stdout + ("\n" + r.stderr if r.stderr else "")).strip()
    # «no askpass program» печатает наш ASKPASS, когда нет ни zenity, ни kdialog, ни ssh-askpass
    if "no askpass program" in out or "askpass" in out and r.returncode != 0 and "incorrect password" not in out:
        out += ("\n(Окно для пароля не открылось — нет программы zenity. Попроси пользователя выполнить эту команду в "
                "терминале самому или установить zenity: sudo apt install zenity.)")
    return f"код выхода {r.returncode}\n{out[-3000:]}"


# sudo там, где начинается команда (не внутри аргументов); sudo -A/-S/-n уже со своим способом пароля — не трогаем
SUDO_AT = re.compile(r"(^\s*|[;&|(]\s*|\b(?:then|do|else)\s+)sudo\s+(?!-[ASn]\b)")
# безопасность: пароль в самой команде (echo … | sudo -S, sudo -S <<< …) остался бы в истории и журналах
PASS_IN_CMD = re.compile(r"(echo|printf)\s+[^|;&]*\|\s*sudo\s+(-\w*\s+)*-S\b|sudo\s+(-\w*\s+)*-S\b[^|;&]*<<<", re.S)
# скрипт для SUDO_ASKPASS: системное окно пароля; пароль идёт прямо в sudo, ассистент его не видит
ASKPASS = """#!/bin/sh
# Dewiar: окно пароля администратора для «sudo -A» (пароль идёт прямо в sudo, ассистент его не видит)
T="Dewiar — пароль администратора"
M="Ассистент выполняет команду с правами администратора. Введите пароль вашей учётной записи:"
if command -v zenity >/dev/null 2>&1; then exec zenity --password --title="$T" 2>/dev/null; fi
if command -v kdialog >/dev/null 2>&1; then exec kdialog --title "$T" --password "$M"; fi
if command -v ssh-askpass >/dev/null 2>&1; then exec ssh-askpass "$M"; fi
echo "no askpass program" >&2
exit 1
"""


def askpass_path():
    """Путь к скрипту окна пароля для sudo -A в STATE_DIR: перезаписывается, если отличается, и всегда исполняемый
    (0o700 — только владельцу)."""
    from settings import STATE_DIR
    p = STATE_DIR / "askpass.sh"
    try:
        if not p.exists() or p.read_text() != ASKPASS:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(ASKPASS)
        os.chmod(p, 0o700)
    except OSError as e:
        log.warning("Окно пароля sudo: %s", e)
    return str(p)


def t_server_run(a, ctx):
    from servers import ServerError
    sv = ctx.get("servers")
    if not (sv and sv.items):
        raise ToolError("серверов нет — добавьте в студии: «Подключение» → «Серверы»")
    try:
        r = sv.run(a.get("server", ""), a.get("command", ""), a.get("timeout") or 60)
    except ServerError as e:
        raise ToolError(str(e)) from e
    return f"Сервер «{r['server']}», код выхода {r['code']}\n{r['output'] or '(вывода нет)'}"


def _mail(ctx):
    """Подключённая почта из ctx, иначе ToolError с подсказкой, где подключить."""
    m = ctx.get("mail")
    if not m or not m.configured():
        raise ToolError("почта не подключена — студия → «Подключение» → «Почта»")
    return m


def t_send_email(a, ctx):
    from mail import MailError
    files = a.get("attachments") or []
    if isinstance(files, str):
        files = [x.strip() for x in files.split(",") if x.strip()]
    try:
        r = _mail(ctx).send(a.get("to", ""), a.get("subject", ""), a.get("body", ""), files, box=a.get("from") or None)
    except MailError as e:
        raise ToolError(str(e)) from e
    return f"Письмо «{r['subject']}» отправлено: {', '.join(r['to'])}" + (f"; вложения: {', '.join(r['attachments'])}" if r["attachments"] else "")


def t_send_telegram(a, ctx):
    from telegram import TelegramError
    tg = ctx.get("telegram")
    if not (tg and tg.paired()):
        raise ToolError("Telegram и MAX не подключены — студия → «Подключение»")
    to = str(a.get("to") or "").lower()
    if to and hasattr(tg, "bots"):                       # назвали мессенджер — туда, если он подключён; иначе — куда есть
        tg = next((b for b in tg.bots if b.TITLE.lower() == to and b.paired()), tg)
    files = a.get("files") or []
    if isinstance(files, str):
        files = [x.strip() for x in files.split(",") if x.strip()]
    ws = ctx.get("workspace")
    sent = []
    text = (a.get("text") or "").strip()
    if text and not tg.send(text):
        raise ToolError(tg.problem or "сообщение не отправилось")
    for f in files[:10]:
        try:                                             # безопасность: отправлять можно только файлы папки ассистента
            p = ws.safe(f) if ws else Path(f)
        except Exception as e:  # noqa: BLE001
            raise ToolError(f"{f}: {e}") from e
        if not p.is_file():
            raise ToolError(f"нет файла {f} в папке ассистента")
        try:
            sent.append(tg.send_file(p))
        except TelegramError as e:
            raise ToolError(str(e)) from e
    if not text and not sent:
        raise ToolError("нечего отправлять: нужен text или files")
    where = getattr(tg, "title", None) or getattr(tg, "TITLE", "Telegram")
    return f"Отправлено в {where}" + (f": {', '.join(sent)}" if sent else "") + "."


def t_read_emails(a, ctx):
    from mail import MailError
    try:
        items = _mail(ctx).inbox(limit=max(1, min(20, int(a.get("limit") or 8))), unread=bool(a.get("unread_only")),
                                 query=a.get("query", ""), box=a.get("box") or None)
    except MailError as e:
        raise ToolError(str(e)) from e
    if not items:
        return "Писем не нашлось."
    many = len({x.get("box") for x in items}) > 1                 # несколько ящиков — у письма видно, в каком оно
    return "\n".join(f"[{x['uid']}] {'● ' if x['unread'] else ''}{x['date'][:22]} · " + (f"в {x['box']} · " if many else "")
                     + f"{x['from']} · «{x['subject']}» — {x['snippet'][:160]}"
                     + (f" (вложения: {', '.join(x['files'])})" if x["files"] else "") for x in items) + \
        "\n\nЦеликом письмо — read_email с номером в скобках."


def t_read_email(a, ctx):
    from mail import MailError
    try:
        m = _mail(ctx).read(a.get("uid", ""), mark=True)    # прочитали человеку — и на почте «прочитано»
    except MailError as e:
        raise ToolError(str(e)) from e
    return (f"От: {m['from']}\nКому: {m['to']}\nТема: {m['subject']}\nДата: {m['date']}\n"
            + (f"Вложения: {', '.join(m['files'])}\n" if m["files"] else "") + "\n" + m["text"][:8000])


def t_search_documents(a, ctx):
    kn = ctx.get("knowledge")
    if not kn:
        raise ToolError("папка «Знания» недоступна")
    res = kn.search(a.get("query", ""), limit=5)
    if not res:
        return "В документах («Знания» и свои папки) ничего подходящего не нашлось."
    if ctx.get("sources"):                         # под ответом — кнопки «открыть» найденных файлов (Engine._turn_sources)
        try:
            ctx["sources"]([{"key": r["key"], "name": Path(r["path"]).name, "label": r["path"]} for r in res])
        except Exception:  # noqa: BLE001
            pass
    return "\n\n".join(f"[Файл «{Path(r['path']).name}» — {r['path']}]\n{r['text']}" for r in res) + \
        "\n\nОтвечай по этим отрывкам и назови файл, откуда взято (по имени, например «Регламент.pdf»). Если ответа в них нет — так и скажи."


def t_ask_knowledge(a, ctx):
    """Вопрос к Знаниям на сайте Dewiar (account.py); base — база или раздел библиотеки по названию."""
    acc = ctx.get("account")
    if not acc:
        raise ToolError("аккаунт недоступен")
    from account import AccountError
    base = None
    want = str(a.get("base") or "").strip().lower().replace("ё", "е")
    if want:                                           # «в разделе „История РФ“» — база по названию: точное, потом часть
        try:
            bases = acc.scope()["bases"]
        except AccountError:
            bases = []
        base = next((b for b in bases if b["label"].lower().replace("ё", "е") == want), None) or \
            next((b for b in bases if want in b["label"].lower().replace("ё", "е")), None)
        if not base:
            names = ", ".join(f"«{b['label']}»" for b in bases[:15])
            raise ToolError(f"нет базы «{a.get('base')}». Есть: {names or 'ни одной'}")
    try:
        r = acc.ask(a.get("question", ""), base=base)
    except AccountError as e:
        raise ToolError(str(e)) from e
    src = ("\nИсточники: " + "; ".join(r["sources"])) if r["sources"] else ""
    return (r["answer"] or "В Знаниях ничего не нашлось.") + src


def pictures_dir():
    """Папка «Изображения» пользователя (на Linux — по xdg-user-dir, она может называться по-русски)."""
    if WIN:
        return winsys.known_folder("Pictures")
    try:
        d = subprocess.run(["xdg-user-dir", "PICTURES"], capture_output=True, text=True, timeout=3).stdout.strip()
        if d and Path(d) != Path.home():
            return Path(d)
    except (OSError, subprocess.SubprocessError):
        pass
    return Path.home() / "Pictures"


def t_save_screenshot(a, ctx):
    from eyes import EyesError, capture_screen
    try:
        data = capture_screen(desktop_env())
    except EyesError as e:
        raise ToolError(str(e)) from e
    d = pictures_dir() / "Снимки экрана"
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"Снимок экрана {datetime.now():%Y-%m-%d %H-%M-%S}.png"
    if data[:8] != b"\x89PNG\r\n\x1a\n":                   # снимок мог прийти в JPEG (портал, Windows) — сохраним как PNG
        import io
        from PIL import Image
        buf = io.BytesIO()
        Image.open(io.BytesIO(data)).save(buf, "PNG")
        data = buf.getvalue()
    f.write_bytes(data)
    return f"Снимок экрана сохранён: {f}. Скажи пользователю коротко, что сохранил в «Изображения/Снимки экрана»."


def t_look_screen(a, ctx):
    """-> {"text", "image"}: картинка уходит модели вложением (нужна модель со зрением)."""
    from eyes import EyesError, capture_screen, prepare
    try:
        b64, w, h = prepare(capture_screen(desktop_env()))
    except EyesError as e:
        raise ToolError(str(e)) from e
    return {"text": f"Снимок экрана {w}×{h} приложен. Виджет ассистента на нём не учитывай.", "image": b64}


def t_look_camera(a, ctx):
    from eyes import EyesError, capture_camera, prepare
    try:
        b64, w, h = prepare(capture_camera(ctx["settings"].get("eyes", "camera") or ("" if WIN else "/dev/video0")))
    except EyesError as e:
        raise ToolError(str(e)) from e
    return {"text": f"Кадр с камеры {w}×{h} приложен.", "image": b64}


def t_create_skill(a, ctx):
    sk = ctx.get("skills")
    if sk is None:
        raise ToolError("навыки недоступны")
    name = sk.save(a.get("name", ""), a.get("description", ""), a.get("instructions", ""))
    return f"Навык «{name}» создан и уже работает. Его можно поправить в студии → «Плагины» → «Навыки»."


# ---------- напоминания ----------

class Reminders:
    """Напоминания, будильники, таймеры и дела по расписанию (kind="job", см. jobs.py): разовые и с повтором
    (when.next_time). Файл reminders.json в STATE_DIR; поток _loop раз в секунду вызывает on_fire для наступивших.
    on_change — после каждой записи (синхронизация с телефоном и сервером, sync.py). Изменения — под _lock: зовут из разных потоков."""

    def __init__(self, on_fire):
        self.path = STATE_DIR / "reminders.json"
        self.on_change = None
        self.on_fire = on_fire
        self.skip_late = None          # ("id@время") -> True, если опоздавшее напоминание уже пришло в Telegram с сервера
        self.on_wake = None            # компьютер проснулся или Dewiar запустился — сверить с телефоном (sync), прежде чем звенеть
        self.hold_until = 0.0          # до этого времени опоздавшие ждут: телефон мог уже прозвенеть и удалить их (28.10)
        self._lock = threading.Lock()
        try:
            self.items = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.items = []
        fixed = 0
        # исправление старых записей: «В будни - Обед» с повтором «каждый день» -> только будни (как _fix_days при создании)
        for it in self.items:
            rep = it.get("repeat")
            if isinstance(rep, dict) and rep.get("kind") == "daily":
                rep2, text = _fix_days({}, rep, it.get("text") or "")
                if rep2 is not rep:
                    it["repeat"], it["text"] = rep2, text
                    try:
                        from when import next_time
                        if datetime.fromisoformat(it["at"]).weekday() not in rep2["days"]:
                            it["at"] = next_time(rep2, datetime.now()).replace(microsecond=0).isoformat(timespec="seconds")
                    except (ValueError, KeyError, TypeError):
                        pass
                    fixed += 1
        if fixed:
            log.info("Напоминания: %d повторов «в будни/выходные» исправлено", fixed)
            try:
                self._save()
            except OSError:
                pass
        threading.Thread(target=self._loop, name="reminders", daemon=True).start()

    def _save(self):
        """Записать атомарно (через .tmp) и сообщить on_change. Вызывать под _lock."""
        self.items.sort(key=lambda x: x["at"])
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.items, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(self.path)
        if self.on_change:
            try:
                self.on_change(list(self.items))
            except Exception as e:  # noqa: BLE001
                log.warning("Напоминания: %s", e)

    def add(self, when: datetime, text, repeat=None, kind="reminder", extra=None):
        """-> копия записи. kind: reminder | alarm | timer | job; extra — поля дела по расписанию (deliver, brief, preset)
        и вложения: note — путь заметки с картинками и файлами в папке ассистента, note_id — её id синхронизации
        (заметка пришла с телефона), см. Engine._reminder_note."""
        with self._lock:
            item = {"id": uuid.uuid4().hex[:6], "at": when.replace(microsecond=0).isoformat(timespec="seconds"),
                    "text": (text or "Напоминание").strip(), "repeat": repeat or None, "kind": kind,
                    "created": datetime.now().isoformat(timespec="seconds")}
            item.update({k: v for k, v in (extra or {}).items() if k in ("deliver", "brief", "preset", "note", "note_id",
                         "care", "care_n", "care_of", "care_root", "care_at") and v not in (None, "")})   # care — лекарство (senior.py)
            self.items.append(item)
            self._save()
            return dict(item)

    def get(self, rid):
        return next((dict(x) for x in self.items if x["id"] == rid), None)

    def upsert(self, item):
        """Синхронизация (sync.py): напоминание с другого устройства — с тем же id (создать или заменить поля).
        Переносятся только at, text, repeat, kind, paused и note_id (заметка с вложениями; нет ключа — не трогаем)."""
        with self._lock:
            cur = next((x for x in self.items if x["id"] == item["id"]), None)
            if cur is not None and cur.get("kind") == "job":
                return dict(cur)                      # дела по расписанию не синхронизируются — их поля (deliver, brief…) не трогаем
            if cur is None:
                cur = {"id": item["id"], "created": datetime.now().isoformat(timespec="seconds")}
                self.items.append(cur)
            for k in ("at", "text", "repeat", "kind", "paused", "note_id"):
                if k in item:
                    cur[k] = item[k]
            if not cur.get("note_id"):
                cur.pop("note_id", None)
            if not cur.get("paused"):
                cur.pop("paused", None)
            self._save()
            return dict(cur)

    def remove(self, rid):
        """Удалить ровно этот id (без поиска по тексту, как у cancel)."""
        with self._lock:
            n = len(self.items)
            self.items = [x for x in self.items if x["id"] != rid]
            if len(self.items) != n:
                self._save()
                return True
            return False

    def update(self, rid, patch):
        with self._lock:
            for x in self.items:
                if x["id"] == rid:
                    for k in ("text", "at", "repeat", "paused", "kind", "deliver", "last_run", "last_ok", "last_error", "note", "note_id"):
                        if k in patch:
                            x[k] = patch[k]
                    self._save()
                    return dict(x)
        return None

    def find(self, query):
        """Записи по id или по тексту: запрос входит в текст или текст — в запрос («отмени напоминание про обед»)."""
        q = re.sub(r"\s+", " ", str(query or "").lower().replace("ё", "е")).strip()
        if not q:
            return []
        exact = [x for x in self.items if x["id"] == q]
        if exact:
            return exact
        texts = ((x, re.sub(r"\s+", " ", str(x.get("text") or "").lower().replace("ё", "е")).strip()) for x in self.items)
        return [x for x, t in texts if q in t or (t and t in q)]     # пустой текст записи совпал бы с любым запросом

    def cancel(self, rid):
        """Удалить все записи, найденные find (по id или тексту) -> найдено ли."""
        with self._lock:
            hit = {x["id"] for x in self.find(rid)}
            if not hit:
                return False
            self.items = [x for x in self.items if x["id"] not in hit]
            self._save()
            return True

    LATE_HOLD = 90                     # с — сколько опоздавшие ждут сверки с телефоном после пробуждения (не дольше)
    hold_from = 0.0

    def release_hold(self, since=None):
        """Сверка прошла (обмен, начатый после пробуждения) или её не будет (синхронизации нет) — опоздавшие звенят сразу."""
        if since is None or since >= self.hold_from:
            self.hold_until = 0.0

    def _loop(self):
        """Раз в секунду: наступившие — разовые удалить, повторяющиеся перенести; on_fire вызывается уже вне _lock.
        28.10 (владелец): компьютер спал всю ночь — утром разом прозвенело вчерашнее «Зарядить часы» (на телефоне оно уже
        прозвенело) и выполнился вчерашний «Итог дня». Теперь после пробуждения (или запуска) опоздавшие ждут LATE_HOLD с:
        on_wake сверяет с телефоном — удалённое там здесь уже не прозвенит; что звенеть — решает ядро (дела с большим
        опозданием пропускаются: _on_reminder)."""
        from when import next_time
        last = 0.0
        while True:
            time.sleep(1)
            mono = time.monotonic()
            if not last or mono - last > 60 or abs(time.time() - getattr(self, "_wall", time.time()) - (mono - last)) > 60:
                self.hold_until, self.hold_from = mono + self.LATE_HOLD, mono   # запустились или проснулись: сначала сверка
                if self.on_wake:
                    try:
                        threading.Thread(target=self.on_wake, daemon=True).start()
                    except Exception:  # noqa: BLE001
                        pass
            last, self._wall = mono, time.time()
            now = datetime.now().replace(microsecond=0)
            due = []
            with self._lock:
                for x in list(self.items):
                    if x.get("paused"):
                        continue
                    at = datetime.fromisoformat(x["at"])
                    if at <= now:
                        late_s = (now - at).total_seconds()
                        if late_s > 300 and mono < self.hold_until:
                            continue                                  # опоздавшее — после сверки с телефоном
                        fired = dict(x, late=late_s > 300, late_s=int(late_s))   # опоздало (компьютер спал или был выключен)
                        due.append(fired)
                        if x.get("repeat"):
                            nxt = next_time(x["repeat"], at)
                            while nxt <= now:                       # компьютер спал — пропущенные повторы не копим
                                nxt = next_time(x["repeat"], nxt)
                            x["at"] = nxt.isoformat(timespec="seconds")
                        else:
                            self.items.remove(x)
                if due:
                    self._save()
            for x in due:
                if x.get("late") and self.skip_late:
                    try:
                        if self.skip_late(f"{x['id']}@{x['at']}"):
                            log.info("Напоминание «%s» уже пришло в Telegram, пока компьютер был выключен", x.get("text"))
                            continue
                    except Exception:  # noqa: BLE001
                        log.debug("проверка напоминания с сервера", exc_info=True)
                try:
                    self.on_fire(x)
                except Exception:  # noqa: BLE001
                    log.exception("напоминание")

    def occurrences(self, days=14, limit=400):
        """Будущие срабатывания на days дней вперёд (с повторами) -> [{"id": "id@время", "at": unix, "text"}] — для сервера,
        который пришлёт их в Telegram, если компьютер выключен. Дела (job) не отдаём: их выполняет только компьютер.
        Не больше 60 повторов одной записи."""
        from when import next_time
        now, end = datetime.now(), datetime.now() + timedelta(days=days)
        out = []
        with self._lock:
            items = [dict(x) for x in self.items]
        for x in items:
            if x.get("paused") or x.get("kind") == "job":
                continue
            try:
                at = datetime.fromisoformat(x["at"])
            except (ValueError, KeyError, TypeError):
                continue
            for _ in range(60):
                if at > end:
                    break
                if at >= now - timedelta(minutes=1):
                    out.append({"id": f"{x['id']}@{at.isoformat(timespec='seconds')}", "at": int(at.timestamp()),
                                "text": x.get("text") or ("Будильник" if x.get("kind") == "alarm" else "Напоминание")})
                if not x.get("repeat"):
                    break
                at = next_time(x["repeat"], at)
        out.sort(key=lambda r: r["at"])
        return out[:limit]

    def done_elsewhere(self, occ):
        """Срабатывание «id@время» уже случилось на сервере: разовое — убрать, с повтором — перейти к следующему."""
        from when import next_time
        rid, _, when = str(occ).partition("@")
        with self._lock:
            for x in list(self.items):
                if x["id"] == rid and x["at"] == when:
                    if x.get("repeat"):
                        nxt = next_time(x["repeat"], datetime.fromisoformat(when))
                        while nxt <= datetime.now():
                            nxt = next_time(x["repeat"], nxt)
                        x["at"] = nxt.isoformat(timespec="seconds")
                    else:
                        self.items.remove(x)
                    self._save()
                    return True
        return False


# значения repeat из схемы set_reminder -> повтор в формате when.py
REPEAT_WORDS = {"daily": {"kind": "daily"}, "weekdays": {"kind": "weekly", "days": [0, 1, 2, 3, 4]},
                "weekends": {"kind": "weekly", "days": [5, 6]}, "weekly": {"kind": "weekly"},
                "monthly": {"kind": "monthly"}, "hourly": {"kind": "interval", "minutes": 60}}


def _when(a):
    """Аргументы set_reminder -> (когда, повтор, текст, вид). Главное — when по-русски («завтра в 9», «каждый день в 8»):
    разбираем сами (when.parse), не полагаясь на модель; запасные пути — in_minutes, at, repeat. Не поняли — ToolError."""
    from when import next_time, parse
    text = (a.get("text") or "").strip()
    phrase = str(a.get("when") or "").strip()
    if phrase:
        r = parse("напомни " + phrase + " " + text)
        if r:
            return r["at"], r["repeat"], text or r["text"], r["kind"]
    rep = a.get("repeat")
    if isinstance(rep, str):
        rep = dict(REPEAT_WORDS.get(rep.strip().lower(), {})) or None
    if isinstance(rep, dict) and rep.get("kind") == "interval" and a.get("every_minutes"):
        rep["minutes"] = int(float(a["every_minutes"]))
    if a.get("in_minutes") is not None:
        when = datetime.now() + timedelta(minutes=float(a["in_minutes"]))
        return when, rep, text, "reminder"
    at = re.sub(r"\s+", " ", str(a.get("at") or "").replace("\u202f", " ").replace("\xa0", " ")).strip()
    try:                                                 # «2026-10-15 08:00:00», «…T08:00+03:00», «…Z» — тоже дата
        iso = datetime.fromisoformat(at.replace("Z", "+00:00")) if re.match(r"\d{4}-\d\d-\d\d[T ]\d", at) else None
        if iso is not None:
            at = (iso.astimezone().replace(tzinfo=None) if iso.tzinfo else iso).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S", "%H:%M", "%d.%m.%Y %H:%M"):
        try:
            t = datetime.strptime(at, fmt)
            if fmt == "%H:%M":                           # только время — ближайшее: сегодня или завтра
                t = datetime.combine(datetime.now().date(), t.time())
                if t <= datetime.now():
                    t += timedelta(days=1)
            if rep and rep.get("kind") != "interval":
                rep.setdefault("time", f"{t:%H:%M}")
                if rep["kind"] == "weekly" and not rep.get("days"):
                    rep["days"] = [t.weekday()]
                if rep["kind"] == "monthly" and not rep.get("day"):
                    rep["day"] = t.day
            return t, rep, text, "reminder"
        except ValueError:
            continue
    if rep and rep.get("kind") == "interval":
        return next_time(rep, datetime.now()), rep, text, "reminder"
    raise ToolError("скажи, когда напомнить: when («через 10 минут», «завтра в 9», «каждый день в 8») "
                    "или in_minutes, или at (ГГГГ-ММ-ДД ЧЧ:ММ)")


# «в будни» / «по выходным» в тексте или в when
_WEEKDAYS_RX = re.compile(r"(?:^|\s)(?:по\s+будням|в\s+будни|будни|будний\s+день|в\s+рабочие\s+дни|по\s+рабочим\s+дням|рабочие\s+дни)"
                          r"(?=\s|$|[,.:;—-])", re.I)
_WEEKENDS_RX = re.compile(r"(?:^|\s)(?:по\s+выходным|в\s+выходные|выходные(?:\s+дни)?)(?=\s|$|[,.:;—-])", re.I)


def _fix_days(a, rep, text):
    """Модель написала «в будни» в тексте или в when, а повтор поставила «каждый день» — исправляем: только будни
    (или только выходные), а «В будни -» из текста убираем. -> (повтор, текст)."""
    said = f"{a.get('when') or ''} {text}"
    days = [0, 1, 2, 3, 4] if _WEEKDAYS_RX.search(said) else [5, 6] if _WEEKENDS_RX.search(said) else None
    # уже точнее, чем «будни» («по будням, кроме пятницы» -> пн–чт; 30.10: тут пятница возвращалась) — не трогаем
    narrower = rep and rep.get("kind") == "weekly" and rep.get("days") and set(rep["days"]) < set(days or [])
    if days and rep and rep.get("kind") in ("daily", "weekly") and rep.get("days") != days and not narrower:
        rep = dict(rep, kind="weekly", days=days)
    if days:
        text = _WEEKENDS_RX.sub(" ", _WEEKDAYS_RX.sub(" ", text)).strip(" -—–:,.") or text
        text = text[:1].upper() + text[1:]
    return rep, text


def t_reminder(a, ctx):
    from when import describe_repeat, human
    when, rep, text, kind = _when(a)
    rep, text = _fix_days(a, rep, text)
    if rep and rep.get("kind") == "weekly" and rep.get("days") and when.weekday() not in rep["days"]:
        from when import next_time
        when = next_time(rep, datetime.now())              # первый раз — в ближайший подходящий день
    moved = ""
    if rep and when < datetime.now() - timedelta(minutes=1):          # «по будням в 17:30», а уже 17:43 — первый раз
        from when import next_time                                    # в следующий подходящий, а не звонок сразу (№56)
        when = next_time(rep, datetime.now())
        moved = f" Сегодня это время уже прошло — первый раз {human(when)}; так и скажи."
    elif not rep and when < datetime.now() - timedelta(minutes=1):     # это время уже прошло («на 17:00», а сейчас 17:26) —
        while when < datetime.now():                                  # ставим на ближайшее такое же время, а не в прошлое
            when += timedelta(days=1)
        moved = " Это время сегодня уже прошло — поэтому на завтра; так и скажи."
    item = ctx["reminders"].add(when, text or "Напоминание", rep, kind)
    return (f"Напоминание «{item['text']}» поставлено: {human(when)}" + (f", {describe_repeat(rep)}" if rep else "") +
            f" (id {item['id']}).{moved} Подтверди коротко одной фразой.")


def t_schedule_job(a, ctx):
    """Дело по расписанию, которое делает сам ассистент (проверить почту, прислать курс, собрать новости) и сообщает
    итог; в срок не звонит человеку, а выполняет (engine_music._run_job). Отчёт №137, 20.10: «проверяй почту и сообщай
    о важном» становилось напоминанием человеку «проверь почту» каждый час — инструмента для такого дела у модели не было."""
    from when import describe_repeat, human, parse
    task = " ".join(str(a.get("task") or "").split()).strip(" .")
    phrase = str(a.get("when") or "").strip()
    if not task or not phrase:
        raise ToolError("нужны task — что делать тебе, и when — когда, с повтором («каждый день в 9», «по будням с 9 до 18 каждый час»)")
    r = parse("напоминай " + phrase + " " + task) or parse("напоминай " + phrase)
    if not r or not r.get("repeat"):
        raise ToolError("when — с повтором: «каждый день в 9», «по будням с 9 до 18 каждый час», «каждые 2 часа»; разовое дело — "
                        "сделай сейчас или set_reminder")
    deliver = a.get("deliver") if a.get("deliver") in ("telegram", "max", "voice") else "voice"
    item = ctx["reminders"].add(r["at"], task[0].upper() + task[1:], r["repeat"], "job", {"deliver": deliver, "brief": False})
    return (f"Дело «{item['text']}» заведено: {describe_repeat(r['repeat'])}, первый раз {human(r['at'])} (id {item['id']}). "
            "В срок его выполнишь ты сам и сообщишь итог"
            + (" в Telegram" if deliver == "telegram" else " в Max" if deliver == "max" else " голосом") + ". Подтверди одной фразой.")


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


def t_change_reminder(a, ctx):
    """Изменить напоминание (30.10, владелец: «попросил Лиру — сказала „сейчас внесу“, а ничего не изменилось»: инструмента
    правки не было). id или text — какое; when — новое время и повтор словами; new_text — новый текст."""
    from when import describe_repeat, human, next_time, parse
    rs = ctx["reminders"]
    hit = rs.find(a.get("id") or a.get("text") or "")
    if not hit:
        return "Не нашёл такого напоминания — посмотри list_reminders и возьми id."
    if len(hit) > 1:
        return "Подходит несколько: " + "; ".join(f"{x['id']}: {x['text']}" for x in hit[:6]) + ". Укажи id."
    x, patch = hit[0], {}
    if str(a.get("new_text") or "").strip():
        patch["text"] = str(a["new_text"]).strip()[:300]
    if str(a.get("when") or "").strip():
        r = parse("напомни " + str(a["when"]).strip() + " " + (patch.get("text") or x.get("text") or ""))
        if not r:
            raise ToolError("не понял время — скажи, например: «по будням, кроме пятницы, в 17:50»")
        when, rep = r["at"], r["repeat"]
        if rep and when < datetime.now() - timedelta(minutes=1):
            when = next_time(rep, datetime.now())
        patch.update(at=when.replace(microsecond=0).isoformat(timespec="seconds"), repeat=rep)
    if not patch:
        return "Что изменить? Нужен when (время и повтор) или new_text."
    y = rs.update(x["id"], patch)
    return (f"Изменено: «{y['text']}» — {human(datetime.fromisoformat(y['at']))}" + (f", {describe_repeat(y['repeat'])}" if y.get("repeat") else "")
            + f" (id {y['id']}). Подтверди коротко.")


def t_list_reminders(a, ctx):
    from when import describe_repeat, human
    items = [x for x in ctx["reminders"].items if not x.get("paused")]
    if not items:
        return "Напоминаний нет."
    return "\n".join(f"{x['id']}: {human(datetime.fromisoformat(x['at']))} — {x['text']}" +
                     (f" ({describe_repeat(x['repeat'])})" if x.get("repeat") else "") for x in items)


def t_cancel_reminder(a, ctx):
    return "Отменил." if ctx["reminders"].cancel(a.get("id") or a.get("text") or "") else "Не нашёл такого напоминания."


def _items_arg(v):
    if isinstance(v, (list, tuple)):
        return [str(x).strip() for x in v if str(x or "").strip()][:12]
    return [x.strip() for x in re.split(r"\s*[;\n]\s*", str(v or "")) if x.strip()][:12]


def t_mark_done(a, ctx):
    """Отметить дела сделанными (done.py): подходящее разовое напоминание на сегодня закрывается, повторяющееся остаётся."""
    import done as D
    dn = ctx.get("done")
    if dn is None:
        raise ToolError("журнал дел недоступен")
    items = _items_arg(a.get("items") or a.get("text"))
    if not items:
        raise ToolError("не понял, какое дело отметить — спроси коротко")
    eng = ctx.get("engine")
    if a.get("undo"):
        today, gone = list(reversed(dn.stats()["items"])), []
        for t in items:
            w = D.stems(t)
            x = next((i for i in today if i not in gone and any(s in w for s in D.stems(i["title"]))), None) \
                or (next((i for i in today if i not in gone), None) if len(items) == 1 else None)
            if x:
                dn.undo(x["id"])
                gone.append(x)
        if eng is not None and gone:
            eng.emit("done", **dn.public())
        return (f"Отметка снята: {', '.join('«' + x['title'] + '»' for x in gone)}. Сегодня сделано {dn.stats()['today']}."
                if gone else "Среди сегодняшних отметок такого нет.")
    rem = ctx.get("reminders")
    closed, lst = [], []
    for t in items:
        m = D.reminder_match(t, list(rem.items) if rem is not None else [], ahead=True)
        if m:
            if not m.get("repeat"):
                rem.remove(m["id"])
                closed.append(m.get("text") or "")
            lst.append({"title": m.get("text") or t, "rid": m["id"]})
        else:
            lst.append({"title": t})
    r = dn.add(lst, "pc")
    if eng is not None:
        eng.emit("done", **dn.public(), fresh=[{"icon": x[3], "name": x[4], "what": x[5]} for x in r["fresh"]], mile=r["mile"],
                 added=[x["title"] for x in r["items"]])
    return D.say(r, closed)


def t_done_report(a, ctx):
    import done as D
    dn = ctx.get("done")
    if dn is None:
        raise ToolError("журнал дел недоступен")
    try:
        days = int(float(a.get("days") or 1))
    except (TypeError, ValueError):
        days = 1
    return D.report(dn, days)


# ---------- папка ассистента ----------

def _ws(ctx):
    """Папка ассистента (workspace.py) из ctx. Все пути инструментов к ней проходят через её проверки (ws.safe)."""
    ws = ctx.get("workspace")
    if ws is None:
        raise ToolError("папка ассистента недоступна")
    return ws


def _ws_call(fn):
    """Выполнить fn, превратив WorkspaceError в ToolError."""
    from workspace import WorkspaceError
    try:
        return fn()
    except WorkspaceError as e:
        raise ToolError(str(e)) from e


def t_watch(a, ctx):
    """«Дозор» (engine_watch.py): присмотреть за экраном, папкой или страницей и сказать, когда готово."""
    eng = ctx.get("watch")
    if eng is None:
        raise ToolError("«Дозор» здесь недоступен")
    act = str(a.get("action") or "add")
    if act == "list":
        pub = eng.watch_public()
        act_ = [x for x in pub["items"] if x["status"] == "active"]
        if not act_:
            return "Дозоров сейчас нет."
        return "Идут дозоры: " + "; ".join(f"{x['title']} (id {x['id']}, последний раз: {x.get('note') or 'ещё не смотрела'})" for x in act_)
    if act == "stop":
        n = eng.watch_stop(str(a.get("id") or ""))
        return f"Остановлено дозоров: {n}." if n else "Нечего останавливать — дозоров нет."
    try:
        it = eng.watch_add(a)
    except ValueError as e:
        raise ToolError(str(e)) from e
    mins = max(1, round(it["every"] / 60)) if it["every"] >= 60 else 0
    how = {"screen": f"буду смотреть на экран раз в {mins} мин", "file": "слежу за папкой",
           "page": f"проверяю страницу раз в {mins} мин"}[it["kind"]]
    hrs = round((it["until"] - it["created"]) / 3600, 1)
    return (f"Дозор начат: «{it['title']}» — {how}, до {hrs:g} ч. Как только будет готово — скажу здесь и пришлю на телефон. "
            "Скажи об этом одной-двумя фразами; если смотришь на экран — что снимки никуда не сохраняются.")


def t_save_link(a, ctx):
    """«Сохрани это видео / статью / ссылку» (0.58, «Заметки как Keep, только умнее»): заметка с ссылкой — в студии она
    карточкой с обложкой и названием; метка «интересное» (и свои), пересказ — если модель его дала."""
    url = str(a.get("url") or "").strip()
    if not re.match(r"https?://\S+$", url):
        raise ToolError("нужна ссылка целиком, с https://")
    lm = ctx.get("linkmeta")
    meta = {}
    if lm is not None:
        try:
            meta = lm.get(url)
        except Exception:  # noqa: BLE001
            meta = {}
    title = (str(a.get("title") or "").strip() or meta.get("title") or meta.get("site") or "Ссылка")[:80]
    summary = str(a.get("summary") or "").strip()
    tags = ["интересное"] + [str(t).strip().lstrip("#") for t in (a.get("tags") or []) if str(t).strip().lstrip("#")]
    body = url + ("\n\n" + summary if summary else "")
    w = _ws(ctx)
    rel = _ws_call(lambda: w.save_note(title, body))
    import workspace as _W
    f = w.safe(rel)
    f.write_text(_W.note_front_set(f.read_text(encoding="utf-8"), {"tags": list(dict.fromkeys(tags))}), encoding="utf-8")
    kind = "видео" if meta.get("video") else "ссылку"
    return (f"Сохранила {kind} в «Заметки» с меткой «интересное»: «{title}»" + (" — с пересказом." if summary else ".")
            + " Скажи коротко, что сохранила.")


PAGE_CSS = """:root{color-scheme:light dark;--bg:#f6f4fb;--card:#fff;--ink:#1d1b26;--mut:#6b6880;--acc:#6d5ce8;--line:#e6e2f2}
@media (prefers-color-scheme:dark){:root{--bg:#14131b;--card:#1e1c28;--ink:#eeeaf8;--mut:#9d98b4;--acc:#a99cff;--line:#2e2b3d}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:17px/1.6 "Manrope","Segoe UI",Ubuntu,system-ui,sans-serif}
main{max-width:860px;margin:0 auto;padding:48px 20px 80px}h1{font-size:34px;line-height:1.15;margin:0 0 8px;letter-spacing:-.01em}
h2{font-size:22px;margin:0 0 10px;color:var(--acc)}h3{font-size:18px;margin:18px 0 6px}p,li{max-width:70ch}
.lead{color:var(--mut);margin:0 0 30px}section,article{background:var(--card);border:1px solid var(--line);border-radius:20px;padding:22px 26px;margin:0 0 18px}
ul,ol{padding-left:22px}li{margin:3px 0}table{border-collapse:collapse;width:100%}td,th{padding:8px 10px;border-bottom:1px solid var(--line);text-align:left}
img{max-width:100%;border-radius:14px}a{color:var(--acc)}footer{color:var(--mut);font-size:13px;margin-top:30px}"""


def page_html(title, html):
    """Готовая страница: полный HTML — как есть; кусок (секции, списки) — в оформление Dewiar с заголовком."""
    import html as _h
    body = str(html or "").strip()
    body = re.sub(r"^```(?:html)?\s*|\s*```$", "", body)
    if re.search(r"<html[\s>]|<!doctype", body, re.I):
        return body
    t = _h.escape(title)
    return (f'<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f"<title>{t}</title><style>{PAGE_CSS}</style></head><body><main><h1>{t}</h1>{body}"
            f"<footer>Собрала Лира · Dewiar · {datetime.now().strftime('%d.%m.%Y')}</footer></main></body></html>")


def md_html(text):
    """Заметка Markdown -> HTML для страницы (show_page с file): заголовки, списки, задачи, цитаты, код, ссылки, жирный и
    курсив. Всё экранируется — HTML внутри заметки показывается текстом, а не выполняется."""
    import html as _h

    def inline(t):
        t = _h.escape(t, quote=False)
        t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
        t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
        t = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", t)
        t = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", lambda m: f'<a href="{_h.escape(m.group(2))}">{m.group(1)}</a>', t)
        t = re.sub(r"(?<![\"'>=])(https?://[^\s<]+)", lambda m: f'<a href="{m.group(1)}">{m.group(1)}</a>', t)
        return t
    out, para, lst, code = [], [], None, None

    def flush():
        nonlocal para, lst
        if para:
            out.append("<p>" + "<br>".join(inline(x) for x in para) + "</p>")
            para = []
        if lst:
            out.append(f"<{lst[0]}>" + "".join(f"<li>{x}</li>" for x in lst[1]) + f"</{lst[0]}>")
            lst = None
    for line in str(text or "").replace("\r\n", "\n").split("\n"):
        if code is not None:
            if line.strip().startswith("```"):
                out.append("<pre><code>" + _h.escape("\n".join(code)) + "</code></pre>")
                code = None
            else:
                code.append(line)
            continue
        st = line.strip()
        if st.startswith("```"):
            flush()
            code = []
            continue
        m = re.match(r"(#{1,6})\s+(.*)", st)
        if m:
            flush()
            n = min(6, len(m.group(1)) + 1)
            out.append(f"<h{n}>{inline(m.group(2))}</h{n}>")
            continue
        m = re.match(r"[-*+]\s+(?:\[([ xX])\]\s+)?(.*)", st) or re.match(r"(\d+)[.)]\s+(.*)", st)
        if m:
            kind = "ol" if st[:1].isdigit() else "ul"
            if para:
                flush()
            if lst and lst[0] != kind:
                flush()
            item = inline(m.group(2))
            if kind == "ul" and m.group(1):
                item = ("☑ " if m.group(1).lower() == "x" else "☐ ") + item
            lst = lst or (kind, [])
            lst[1].append(item)
            continue
        if st.startswith(">"):
            flush()
            out.append("<blockquote>" + inline(st.lstrip("> ")) + "</blockquote>")
            continue
        if not st:
            flush()
            continue
        if lst:
            flush()
        para.append(st)
    if code is not None:
        out.append("<pre><code>" + _h.escape("\n".join(code)) + "</code></pre>")
    flush()
    return "\n".join(out)


def t_show_page(a, ctx):
    """«Покажи в браузере красиво» (28.10, пользователь: «нашла рецепты, но создала кучу питоновских скриптов, а HTML — не в
    файле, а в чате, и начала зачитывать его со всеми тегами»): страница — файлом в «Страницы», сразу в браузере."""
    title = re.sub(r"[\\/:*?\"<>|\n\r\t]+", " ", str(a.get("title") or "").strip())[:80].strip() or "Страница"
    html = str(a.get("html") or "")
    src = str(a.get("file") or "").strip()
    if src:
        # своя заметка или файл — показываем как есть, без пересказа моделью (28.10, отзыв: «попросил вывести мою заметку
        # в браузере — она отказалась перепечатывать текст и показала кусочек»): текст берём с диска сами
        r = _ws_call(lambda: _ws(ctx).read(src, limit=400000))
        if r.get("binary"):
            raise ToolError(f"«{r['path']}» — не текстовый файл, его так не показать")
        body = r["text"]
        if not a.get("title"):
            title = re.sub(r"[\\/:*?\"<>|\n\r\t]+", " ", Path(str(r.get("path") or src)).stem)[:80].strip() or title
        html = (body if str(r.get("path") or src).lower().endswith((".html", ".htm")) else md_html(body)) + (
            "\n<p><i>…(дальше обрезано)</i></p>" if r.get("truncated") else "")
        if not html.strip():
            raise ToolError("файл пустой")
    if len(html.strip()) < 20 and not src:
        raise ToolError("нужно содержимое страницы — html с разделами, списками или таблицей")
    w = _ws(ctx)
    root = _ws_call(lambda: w.ensure()) / "Страницы"
    root.mkdir(parents=True, exist_ok=True)
    f = root / f"{title}.html"
    f.write_text(page_html(title, html), encoding="utf-8")
    launch(["xdg-open", str(f)])
    return (f"Страница «{title}» открыта в браузере (файл — «Страницы/{f.name}» в папке Dewiar). Скажи одной фразой, что "
            "открыла. HTML в ответе не повторяй.")


def t_debate(a, ctx):
    """«Пусть модели поспорят: …» (0.62, debate.py): две модели отвечают и возражают друг другу — итог подводит Лира."""
    import debate as DB
    s = ctx.get("settings")
    if s is None:
        raise ToolError("спор моделей — в программе Dewiar")
    try:
        a_, b_ = DB.pick_pair(s)
        return DB.context(DB.run(a.get("question") or "", a_, b_))
    except DB.DebateError as e:
        raise ToolError(str(e)) from e


def t_council(a, ctx):
    """«Собери совет: …», «посоветуйся с командой» (0.67, council.py): персонажи обсуждают вопрос в студии («Совет ИИ» —
    открывается сама). Ждать минуту-две молча нельзя: отвечаем сразу, итог Лира скажет сама, когда совет закончит."""
    eng = ctx.get("engine")
    if eng is None or not hasattr(eng, "council"):
        raise ToolError("«Совет ИИ» — в программе Dewiar на компьютере")
    from council import CouncilError
    try:
        r = eng.council.start(a.get("question") or "", None, announce=True)
    except CouncilError as e:
        raise ToolError(str(e)) from e
    eng.emit("council", sid=r["sid"], open=True)
    names = ", ".join(m["name"] for m in r["members"])
    return (f"Совет собран: {names}. Они обсуждают вопрос в студии «Совет ИИ» (открылась) — мнения, спор и итог; итог прозвучит "
            "сам, когда совет закончит. Скажи об этом одной фразой, без своего ответа на вопрос.")


def t_writing_today(a, ctx):
    """«Сколько я написал сегодня?» (0.68, writing.py): прирост слов в своих текстах из папок «Документов»."""
    w = ctx.get("writing")
    if w is None:
        raise ToolError("«Пишу» — в программе Dewiar на компьютере")
    return w.text()


def t_month_summary(a, ctx):
    """«Как прошёл мой месяц?», «итоги октября» (0.61, month.py): данные месяца — модели, рассказать тепло."""
    eng = ctx.get("engine")
    if eng is None:
        raise ToolError("итоги месяца — в программе Dewiar")
    import month as M
    ym = str(a.get("month") or "").strip()
    if ym in ("", "this", "текущий", "этот"):
        ym = None
    elif ym in ("prev", "last", "прошлый"):
        ym = M.prev_ym()
    elif not re.match(r"^\d{4}-\d{2}$", ym):
        raise ToolError("месяц — в виде 2026-10, или prev — прошлый")
    return M.context(M.gather(eng, ym)) + "\n\n" + M.PROMPT


def t_suggest_idea(a, ctx):
    """«Предложи идею разработчику» (0.61): через ядро (ideas.suggest) — похожая есть: голос за неё; нет — новая."""
    eng = ctx.get("engine")
    if eng is None:
        raise ToolError("идеи — только в программе Dewiar")
    import ideas
    try:
        return ideas.suggest(eng, a.get("title") or "", a.get("text") or "")
    except ideas.IdeasError as e:
        raise ToolError(str(e)) from e


def t_save_note(a, ctx):
    rel = _ws_call(lambda: _ws(ctx).save_note(a.get("title", ""), a.get("text", ""), a.get("folder", ""),
                                              bool(a.get("append"))))
    return f"Записал в папку Dewiar: {rel}"


# Бюджет, лимит, «заложим 70 тысяч» — план, а не трата: в расходы не пишем (иначе «потрачено 70 000» в отчёте)
PLAN_RX = re.compile(r"\b(?:бюджет|лимит)\w*\s+(?:на|для)\b|^\s*(?:бюджет|лимит|план)\w*\b|заложи\w*|запланир\w*|планиру\w*|"
                     r"(?:увелич|уменьш|повыш|сниж)\w*\s+(?:с|до)\s+\d", re.I)
SPENT_RX = re.compile(r"из бюджета|потрат|купил|оплат|заплат|получил|пришл|зарплат", re.I)


def is_plan(note):
    return bool(PLAN_RX.search(note or "")) and not SPENT_RX.search(note or "")


def t_money_add(a, ctx):
    m = ctx.get("money")
    if m is None:
        raise ToolError("учёт денег недоступен")
    if is_plan(f"{a.get('category') or ''} {a.get('note') or ''}".strip()) or is_plan(a.get("note") or ""):
        return ("Не записано: это план (бюджет, лимит), а не трата или доход — в расходы не пишу. Запомни его как факт "
                "(remember, например «Бюджет на мебель — 65 тысяч рублей»): новое значение заменит старое и сохранит историю.")
    from money import fmt
    try:
        it = m.add(a.get("kind") or "expense", a.get("amount") or 0, a.get("currency") or None, a.get("category") or "",
                   a.get("note") or "", a.get("date") or None)
    except (TypeError, ValueError) as e:
        raise ToolError(str(e)) from e
    # №382 (28.10): «бот куда-то записал расходы, такого раздела нет, в „Платежах“ нет» — говорим, где их видно
    return (f"Записано: {'доход' if it['kind'] == 'income' else 'расход'} {fmt(it['amount'], it['currency'])}, {it['category']}, {it['date']}. "
            "Если человек спросит, где это смотреть или впервые записывает траты: студия → «Календарь» → вкладка «Деньги» "
            "(«Платежи» — это обязательные счета: свет, газ, интернет). В ответе — коротко.")


def t_close_send(a, ctx):
    c = ctx.get("close")
    if c is None:
        raise ToolError("«Близкие» недоступны")
    from close import CloseError
    rw = str(a.get("remind_when") or "").strip()
    try:
        files = [str(Path(x).expanduser()) for x in (a.get("files") or []) if x]
        if rw:                                       # «Лира в группе»: «напомни всем в группе Семья в субботу в 10 про дачу»
            g = c.group_of(a.get("to") or "") or c.group_match(a.get("to") or "")
            if not g:
                raise ToolError("напомнить всем можно только в группе своих — назови группу («в группу Семья»)")
            import when as W
            w = W.parse("напомни " + rw + " " + (a.get("text") or "дело"))
            if not w or not w.get("at"):
                raise ToolError(f"не понял, когда напомнить: «{rw}» — спроси у пользователя день и время")
            it = c.gsend(g["gid"], a.get("text") or "", files, remind_at=w["at"])
            return (f"Отправлено {it['to']}: у каждого участника (и у тебя) встанет напоминание на {w['at'].strftime('%d.%m %H:%M')}."
                    " Скажи коротко, что напомнишь всем.")
        it = c.send(a.get("to") or "", a.get("text") or "", files)
    except (CloseError, OSError) as e:
        raise ToolError(str(e)) from e
    to = it.get("to") or c.person(a.get("to") or "")["name"]          # группа («Группы своих») — «в группу «Семья»»
    return f"Отправлено {to}" + (f" (файлов: {len(it.get('f') or [])})" if it.get("f") else "") + ". Скажи коротко, что отправила."


def t_close_call(a, ctx):
    c = ctx.get("close")
    if c is None:
        raise ToolError("«Близкие» недоступны")
    from close import CloseError
    try:
        r = c.call(a.get("to") or "", bool(a.get("video")))
    except CloseError as e:
        raise ToolError(str(e)) from e
    return f"Открыла окно звонка: звоню {r['name']}. Скажи одной фразой, что звонишь."


def t_close_read(a, ctx):
    c = ctx.get("close")
    if c is None:
        raise ToolError("«Близкие» недоступны")
    from close import CloseError
    try:
        return c.recent(a.get("who") or "")
    except CloseError as e:
        raise ToolError(str(e)) from e


def _team(ctx):
    t = ctx.get("team")
    if t is None or not t.connected():
        raise ToolError("«Поручения» не подключены — студия → «Поручения»")
    return t


def _mailing(ctx):
    m = ctx.get("mailing")
    if m is None:
        raise ToolError("рассылка недоступна")
    return m


def t_mailing(a, ctx):
    """«Разошли всем клиентам…», «напиши всем сотрудникам письмо…» — каждому своё письмо (mailing.py)."""
    from mailing import MailingError
    m = _mailing(ctx)
    try:
        d = m.draft(a.get("subject") or "", a.get("body") or "", a.get("recipients") or "list", a.get("list") or "",
                    a.get("tag") or "", a.get("kind") or "work")
        m.start(d["id"])
    except MailingError as e:
        raise ToolError(str(e)) from e
    sk = d.get("skipped") or {}
    extra = (f"; отписавшихся пропускаю: {sk['stop']}" if sk.get("stop") else "") + (f"; повторы убрала: {sk['dup']}" if sk.get("dup") else "")
    from mailing import plain
    return (f"Рассылка «{plain(d['subject'])}» пошла: {d['total']} писем, каждому своё, по одному с паузой{extra}. Итог пришлю, "
            "ход — в студии → «Рассылка». Скажи это одной фразой.")


def t_mailing_status(a, ctx):
    ls = _mailing(ctx).list()
    if not ls:
        return "Рассылок ещё не было."
    st = {"draft": "черновик", "sending": "идёт", "waiting": "ждёт завтра (дневной предел почты)", "done": "закончена",
          "stopped": "остановлена", "paused": "на паузе"}
    from mailing import plain
    return "\n".join(f"«{plain(c['subject'])}»: {st.get(c['status'], c['status'])}, ушло {c['sent']} из {c['total']}"
                     + (f", не дошло {c['failed']}" if c["failed"] else "") for c in ls[:5])


def t_team_assign(a, ctx):
    from team import TeamError, due_text
    try:
        r = _team(ctx).assign(a.get("who") or "", a.get("task") or "", a.get("due") or "", a.get("note") or "", via="voice")
    except TeamError as e:
        raise ToolError(str(e)) from e
    if r.get("repeat"):                                # «каждый понедельник к 18» — повторяющееся поручение
        return (f"Буду поручать {r['name_dat']} «{r['title']}» {r['rule']}; первое уйдёт само в день срока ({due_text(r['first'])}). "
                "Скажи это одной фразой.")
    due = due_text(r.get("due"))
    where = "отправила в Telegram" if r.get("sent") else "записала — уйдёт в Telegram, как только сотрудник откроет приглашение"
    return f"Поручила {r['name']}: «{r['title']}»" + (f", срок {due}" if due else "") + f"; {where}. Скажи это одной фразой."


def t_team_message(a, ctx):
    from team import TeamError
    try:
        T = _team(ctx)
        T.message(a.get("who") or "", a.get("text") or "")
    except TeamError as e:
        raise ToolError(str(e)) from e
    return "Отправила сотруднику. Скажи коротко."


def t_team_status(a, ctx):
    from team import TeamError
    try:
        return _team(ctx).summary(a.get("who") or "")
    except TeamError as e:
        raise ToolError(str(e)) from e


def _clients(ctx):
    c = ctx.get("clients")
    if c is None:
        raise ToolError("«Клиенты» выключены — студия → «Возможности» → «Клиенты»")
    return c


def t_client_note(a, ctx):
    """«Запиши: Иванов из „Ромашки“ хочет 200 коробок до пятницы» — в историю клиента (нет — карточка заводится)."""
    from clients import ClientError
    C = _clients(ctx)
    who = " ".join(x for x in (a.get("who") or "", f"«{a['company']}»" if a.get("company") else "") if x)
    try:
        before = set(C.st["clients"])
        cid = C.find(who, create=True)
        c = C.note(cid, a.get("text") or "", a.get("kind") or "note", a.get("phone") or "", a.get("email") or "")
    except ClientError as e:
        raise ToolError(str(e)) from e
    made = cid not in before
    return (f"Записала в карточку {C.title(c)}" + (" (новый клиент — карточка заведена)" if made else "") + f": «{c['log'][-1]['t']}». "
            "Скажи это одной фразой. Если в записи есть срок или «перезвонить» — предложи поставить следующий шаг (client_next).")


def t_client_info(a, ctx):
    from clients import ClientError
    C = _clients(ctx)
    try:
        return C.card_text(C.find(a.get("who") or ""))
    except ClientError as e:
        raise ToolError(str(e)) from e


def t_client_crm(a, ctx):
    """«Передай Иванова в Битрикс» — клиент лидом в CRM (crm.py); уже там — новые записи комментарием."""
    from clients import ClientError
    from crm import CrmError
    C, R = _clients(ctx), ctx.get("crm")
    if not (R and R.connected()):
        raise ToolError("CRM не подключена — студия → «Клиенты» → «CRM»")
    try:
        cid = C.find(a.get("who") or "")
        r = R.send(cid)
    except (ClientError, CrmError) as e:
        raise ToolError(str(e)) from e
    where = R.public()["name"]
    if r["new"]:
        return f"Передала {C.title(C.get(cid))} в {where} новым лидом (№{r['id']}). Скажи это одной фразой."
    return (f"В {where} у этого клиента уже есть лид №{r['id']}: " + (f"добавила новых записей — {r['n']}." if r["n"] else "новых записей нет — всё уже там.")
            + " Скажи это одной фразой.")


def _post_target(P, name):
    """«в канал Чайный двор» -> id чата бота; пусто — первый, где можно публиковать."""
    cs = [c for c in P.chats() if c["can"]]
    n = (name or "").strip().lower().lstrip("@")
    if not n:
        return [cs[0]["id"]] if cs else []
    hit = [c["id"] for c in cs if n in c["title"].lower() or (c["username"] and n == c["username"].lower())]
    if not hit:
        raise ToolError("бот не состоит в «" + name + "». Есть: " + (", ".join(c["title"] for c in cs) or "ничего — добавьте бота в канал"))
    return hit[:1]


def t_channel_post(a, ctx):
    """«Опубликуй в канале…», «запланируй пост на завтра в 10», «сделай опрос в группе» — от имени бота персонажа."""
    from pbot_posts import PostError
    from when import parse
    P = ctx.get("pbot_posts")
    if P is None or not P.bot.connected():
        raise ToolError("бот персонажа не подключён — студия → «Бот в Telegram»")
    at = None
    w = (a.get("when") or "").strip()
    if w and not re.search(r"^(сейчас|сразу)$", w, re.I):
        r = parse("напомни " + w)
        if not r:
            raise ToolError(f"не поняла, когда: «{w}» — уточни день и время")
        at = r["at"]
    poll = {"question": a.get("poll_question"), "options": a.get("poll_options") or []} if a.get("poll_question") else None
    try:
        p = P.add(a.get("text") or "", _post_target(P, a.get("chat") or ""), at, poll, source="voice")
    except PostError as e:
        raise ToolError(str(e)) from e
    where = ", ".join(c["title"] for c in P.chats() if c["id"] in p["chats"])
    if p["status"] == "sent":
        return f"Опубликовала в «{where}»." + (" Ссылка: " + p["sent"][0]["link"] if p["sent"] and p["sent"][0]["link"] else "") + " Скажи коротко."
    if p["status"] == "failed":
        raise ToolError("Telegram не принял пост: " + p["err"])
    from clients import _when
    return f"Запланировала пост в «{where}» — {_when(p['at'])}. Скажи это одной фразой."


def t_client_next(a, ctx):
    """Следующий шаг с клиентом: что и когда; когда — напоминание в «Делах»."""
    from clients import ClientError
    from when import parse
    C = _clients(ctx)
    at = None
    w = (a.get("when") or "").strip()
    if w:
        r = parse("напомни " + w)
        if not r:
            raise ToolError(f"не поняла, когда: «{w}» — уточни день и время")
        at = r["at"]
    try:
        cid = C.find(a.get("who") or "", create=True)
        if a.get("done"):
            c = C.next_done(cid)
            return f"Отметила: следующий шаг с {C.title(c)} сделан, записано в историю."
        c = C.set_next(cid, a.get("what") or "связаться", at)
    except ClientError as e:
        raise ToolError(str(e)) from e
    from clients import _when
    return (f"Следующий шаг с {C.title(c)}: {c['next']['what']}" + (f" — {_when(c['next']['at'])}, напоминание поставлено" if at else "")
            + ". Скажи это одной фразой.")


def t_client_list(a, ctx):
    return _clients(ctx).summary(a.get("query") or "")


def t_client_deal(a, ctx):
    """Сделка: новая или движение по этапам. «Ромашке выставили счёт на 1200 за коробки, оплатить до пятницы» — счёт;
    «Ромашка оплатила» — оплачено (и в доходы, если не выключено); «Иванов отказался» — отказ."""
    from clients import ClientError
    from deals import STAGES, DealError, fmt_amount, human_date, stage_of, to_money
    C = _clients(ctx)
    stage = stage_of(a.get("stage") or "") or ""
    try:
        cid = C.find(a.get("who") or "", create=True)
        did = ""
        if not a.get("new"):
            try:
                did = C.deal_find(cid, a.get("title") or "", strict=bool(a.get("title")) and not stage_of(a.get("title") or ""))
            except DealError:
                did = ""
        if did:
            f = {k: a[k] for k in ("amount", "due") if a.get(k)}
            d = C.deal_set(cid, did, stage=stage or None, **f) if (stage or f) else next(x for x in C.deals(cid=cid) if x["id"] == did)
            made = False
        else:
            d = C.deal_add(cid, a.get("title") or "", a.get("amount") or 0, "", stage or "lead", a.get("due") or "")
            made = True
    except (ClientError, DealError) as e:
        raise ToolError(str(e)) from e
    income = ""
    s = ctx.get("settings")
    if d["stage"] == "paid" and ((s.get("clients") or {}).get("deal_income", True) if s else True) is not False:
        income = to_money(ctx.get("money"), d)
        if income:
            C.deal_set(d["cid"], d["id"], income=income)
    amt = f", {fmt_amount(d['amount'], d['cur'])}" if d.get("amount") else ""
    due = f", оплатить до {human_date(d['due'])}" if d["stage"] == "invoice" and d.get("due") else ""
    return (f"{'Новая сделка' if made else 'Сделка'} с {d['client']}: «{d['title']}» — {STAGES[d['stage']].lower()}{amt}{due}."
            + (" Записала в доходы." if income else "") + " Скажи это одной фразой.")


def t_deal_remind(a, ctx):
    """«Напомни Ромашке об оплате» — вежливое письмо клиенту о счёте (почта) или текст, чтобы отправить самому."""
    from clients import ClientError
    from deals import DealError
    C = _clients(ctx)
    try:
        cid = C.find(a.get("who") or "")
        ds = [d for d in C.deals(stage="invoice", cid=cid)]
        if not ds:
            raise ToolError("у этого клиента нет выставленных неоплаченных счетов")
        if a.get("title"):
            did = C.deal_find(cid, a.get("title") or "")
            ds = [d for d in ds if d["id"] == did] or ds
        d = ds[0]
        s = ctx.get("settings")
        me = ((s.get("close") or {}).get("name") or s.get("user_name") or "") if s else ""
        r = C.deal_remind_text(cid, d["id"], me)
    except (ClientError, DealError) as e:
        raise ToolError(str(e)) from e
    m = ctx.get("mail")
    if r["to"] and m and m.configured() and a.get("send", True) is not False:
        from mail import MailError
        try:
            m.send(r["to"], r["subject"], r["body"])
        except MailError as e:
            raise ToolError(str(e)) from e
        C.deal_reminded(cid, d["id"], "письмом")
        return f"Письмо-напоминание об оплате «{d['title']}» отправлено {r['name']} ({r['to']}). Скажи коротко."
    why = "у клиента не записана почта" if not r["to"] else "почта не подключена (студия → «Подключение» → «Почта»)"
    return (f"Отправить письмом не получилось: {why}. Вот текст — предложи отправить его в мессенджер или записать почту "
            f"клиента, и покажи текст:\n\n{r['body']}")


def t_client_deals(a, ctx):
    return _clients(ctx).deals_summary(a.get("what") or "")


def t_app_help(a, ctx):
    import guide
    return guide.answer(a.get("query") or "", a.get("where") or "")


def t_money_report(a, ctx):
    m = ctx.get("money")
    if m is None:
        raise ToolError("учёт денег недоступен")
    import datetime as _dt
    from money import fmt
    end = a.get("to") or _dt.date.today().isoformat()
    start = a.get("from") or _dt.date.today().replace(day=1).isoformat()
    sm = m.summary(start, end)
    if not sm["count"]:
        return f"С {start} по {end} записей о деньгах нет."
    out = [f"С {start} по {end}, записей: {sm['count']}."]
    for c in sm["by_currency"]:
        out.append(f"{c['currency']}: доходы {fmt(c['income'], c['currency'])}, расходы {fmt(c['expense'], c['currency'])}, "
                   f"остаток {fmt(c['balance'], c['currency'])}. Расходы по категориям: "
                   + ", ".join(f"{x['name']} {fmt(x['sum'], c['currency'])}" for x in c["expense_cats"]) + ".")
    last = m.list(start, end)[:15]
    out.append("Последние: " + "; ".join(f"{x['date']} {'+' if x['kind'] == 'income' else '−'}{x['amount']} "
                                         f"{x['currency']} {x['note'] or x['category']}" for x in last))
    return "\n".join(out)


def t_calendar_list(a, ctx):
    """Календарь по дням (engine.calendar_month: события, напоминания, заметки, задачи, деньги); не больше 300 строк."""
    eng = ctx.get("engine")
    if eng is None:
        raise ToolError("календарь недоступен")
    import datetime as _dt
    end = _dt.date.fromisoformat(a.get("to") or _dt.date.today().isoformat())
    start = _dt.date.fromisoformat(a.get("from") or (end - _dt.timedelta(days=6)).isoformat())
    out, y, m = [], start.year, start.month
    while (y, m) <= (end.year, end.month):
        days = eng.calendar_month(y, m)["days"]
        for d in sorted(days):
            if start.isoformat() <= d <= end.isoformat():
                for it in days[d]:
                    if it["type"] == "money":
                        out.append(f"{d} деньги: {'+' if it['kind'] == 'income' else '−'}{it['amount']} {it['currency']} {it['title']}")
                    else:
                        kind = {"reminder": "сделано" if it.get("done") else "напоминание", "note": "заметка",
                                "diary": "дневник", "task": "задача", "event": f"событие ({it.get('cal', 'календарь')})"}.get(it["type"], it["type"])
                        tm = (it.get("time") or "") + (f"–{it['end']}" if it.get("end") else "")
                        out.append(f"{d} {tm} {kind}: {it.get('title', '')}".replace("  ", " ") + (f", {it['place']}" if it.get("place") else ""))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return "\n".join(out[-300:]) or "За этот период в календаре ничего нет."


NOTES_GENERIC = re.compile(r"^(?:заметк\w*|все|всё|мои|мой|моих|последн\w*|покажи|прочитай|список|какие|есть|что|там|запис\w*|сохран\w*)$")


def _latest_notes(ctx, lead=""):
    """Последние заметки — когда просят «покажи заметки» или по словам ничего нет (иначе Лира отвечала «заметок нет»)."""
    try:
        lst = _ws(ctx).notes()
    except Exception:  # noqa: BLE001
        lst = []
    if not lst:
        return "Заметок пока нет."
    rows = [f"{n['path']}: {n['title']} — {n['snippet'][:200]}" + (f" [вложений: {n['att']}]" if n.get("att") else "") for n in lst[:10]]
    return lead + f"Всего заметок: {len(lst)}. Последние (новые сверху):\n" + "\n".join(rows) + "\n\nЦеликом — read_file с путём."


def _memory_hits(ctx, q):
    """Строки «Обо мне» к запросу (по началу слов) — или последние, если совпадений нет. Экзамен 11.10: «запомни: на работе
    отчёт, дизайнер, сайт» → новый разговор → «вспомни, что я говорил про работу» — модель искала в заметках и календаре,
    ничего не нашла по слову «работа» и ответила «ничего не записано», хотя всё было в памяти. -> текст или ""."""
    try:
        body = _ws(ctx).memory_text(limit=6000)
    except Exception:  # noqa: BLE001
        return ""
    facts = [ln.strip()[2:] for ln in body.splitlines() if ln.strip().startswith("- ")]
    if not facts:
        return ""
    stems = {w[:5] if len(w) > 5 else w for w in re.findall(r"[а-яa-z0-9]{4,}", q.lower().replace("ё", "е")) if not NOTES_GENERIC.match(w)}
    hit = [f for f in facts if any(st in f.lower().replace("ё", "е") for st in stems)]
    recent = [f for f in facts[-8:] if f not in hit]
    if hit:                                   # и недавние: «работа» могла быть сказана другими словами («начальник просил…»)
        return "Из твоей памяти «Обо мне»:\n" + "\n".join("- " + f for f in hit[-12:]) + \
            ("\nНедавно запомнено (может быть о том же):\n" + "\n".join("- " + f for f in recent) if recent else "")
    return "В памяти «Обо мне» по этим словам ничего, вот последние записи (может, это оно):\n" + "\n".join("- " + f for f in facts[-10:])


def _chat_hits(ctx, q, days=14):
    """Что человек сам говорил в прошлых разговорах (лента «Чата», chatlog.py) по словам запроса — и соседние его реплики
    того же разговора (±20 мин): «на работе три дела…» и «ещё начальник просил презентацию» — одно, хотя слова «работа»
    во второй нет. Экзамен 0.38.47: модель сказала «записала», не вызвав remember, а через новый разговор на «вспомни, что я
    говорил про работу» нашла только память о ремонте. -> текст или ""."""
    log_ = ctx.get("chatlog")
    if log_ is None:
        return ""
    stems = {w[:5] if len(w) > 5 else w for w in re.findall(r"[а-яa-z0-9]{4,}", q.lower().replace("ё", "е")) if not NOTES_GENERIC.match(w)}
    if not stems:
        return ""
    import time as _t
    since = _t.time() - days * 86400
    mine = [x for x in list(getattr(log_, "items", []))[-2000:] if x.get("role") == "user" and x.get("ts", 0) >= since and x.get("text")]
    hit = [i for i, x in enumerate(mine) if any(st in x["text"].lower().replace("ё", "е") for st in stems)]
    if not hit:
        return ""
    keep = sorted({j for i in hit for j in range(len(mine)) if abs(mine[j]["ts"] - mine[i]["ts"]) <= 1200})[-12:]
    return "Ты сам(а) говорил(а) в прошлых разговорах:\n" + "\n".join(
        f"- {_t.strftime('%d.%m %H:%M', _t.localtime(mine[j]['ts']))} — {mine[j]['text'][:300]}" for j in keep)


def t_find_notes(a, ctx):
    """Сначала поиск recall.py (ранжированный, с Obsidian), ничего — простой поиск по папке ассистента. К найденному —
    строки памяти «Обо мне» (_memory_hits): «вспомни, что я говорил…» часто про запомненное, а не про заметки."""
    q = str(a.get("query", "") or "")
    if not [w for w in re.split(r"[\s,.]+", q.lower().replace("ё", "е")) if len(w) > 2 and not NOTES_GENERIC.match(w)]:
        return _latest_notes(ctx)
    mem = _memory_hits(ctx, q)
    said = _chat_hits(ctx, q)
    tail = ("\n\n" + mem if mem else "") + ("\n\n" + said if said else "")
    rc = ctx.get("recall")
    if rc is not None:
        res = rc.search(a.get("query", ""), limit=8)
        if res:
            return "\n".join(f"{r['path']}: {r['snippet'][:300]}" for r in res) + \
                "\n\nЦеликом — read_file с путём." + tail
    res = _ws_call(lambda: _ws(ctx).find(a.get("query", "")))
    if not res:
        return _latest_notes(ctx, "В заметках по этим словам ничего не нашлось. ") + tail
    return "\n".join(f"{r['path']}: {r['snippet']}" for r in res) + tail


def t_read_file(a, ctx):
    r = _ws_call(lambda: _ws(ctx).read(a.get("path", ""), limit=12000))
    if r.get("binary"):
        return f"{r['path']} — не текстовый файл ({r['size']} байт)."
    return r["text"] + ("\n…(дальше обрезано)" if r.get("truncated") else "")


def t_remember(a, ctx):
    r = _ws_call(lambda: _ws(ctx).remember(a.get("fact", "")))
    if r == "Это я уже знаю.":                 # экзамен 13.10: на вопрос «сколько раз я менял бюджет?» — «Запомнила» вместо ответа
        return ("Это уже есть в памяти — ничего нового. Если пользователь задал вопрос, ответь на него по памяти (с прежними "
                "значениями, если они там есть); не говори «запомнила» и «записала».")
    return r


def t_write_diary(a, ctx):
    who = ctx["persona_name"]() if ctx.get("persona_name") else ""
    rel = _ws_call(lambda: _ws(ctx).diary(a.get("entry", ""), who))
    return f"Записал в дневник ({rel})."


def t_lab_write(a, ctx):
    rel = _ws_call(lambda: _ws(ctx).lab_write(a.get("name", ""), a.get("content", "")))
    return f"Файл сохранён: {rel}"


def t_lab_run(a, ctx):
    if DRY:                                              # тесты: записываем и всё равно запускаем (скрипт — в лаборатории)
        launch(["lab_run", a.get("name", "")])
    r = _ws_call(lambda: _ws(ctx).lab_run(a.get("name", ""), a.get("args", "")))
    return f"Код завершения {r['code']}. Вывод (полностью — {r['log']}):\n{r['output'] or '(пусто)'}"


def t_delete_files(a, ctx):
    """Удаление только в корзину и только того, что разрешил guard.plan_delete (системное и главные папки — нельзя)."""
    import guard
    try:
        plan = guard.plan_delete([str(x) for x in (a.get("paths") or []) if str(x).strip()])
        if DRY:
            launch(["trash"] + [x["path"] for x in plan])
            return "В корзине (тест)"
        done = guard.trash(plan)
    except guard.Blocked as e:
        raise ToolError(f"защита Dewiar: {e}. Это удалять нельзя — объясни пользователю почему") from e
    except OSError as e:
        raise ToolError(f"не получилось удалить: {e}") from e
    return "Перемещено в корзину: " + ", ".join(done) + ". Восстановить можно из корзины."


def t_smart_home(a, ctx):
    h = ctx.get("home")                          # homeassistant.Homes: Яндекс и Home Assistant как один дом
    if h is None or not h.connected():
        raise ToolError("умный дом не подключён — студия → «Подключение» → «Умный дом» или «Home Assistant»")
    from smarthome import HomeError
    act, target = a.get("action") or "list", (a.get("target") or "").strip()
    try:
        if act == "list":
            return h.summary()
        if act == "scenario":
            sc = h.scenario(target)
            if not sc:
                raise ToolError(f"нет сценария «{target}». " + h.summary())
            return f"Запущен сценарий «{h.run_scenario(sc)}»"
        devs = h.match(target)
        if not devs:
            raise ToolError(f"не нашёл «{target}». " + h.summary())
        n = h.act(devs, act, a.get("value"))
        return f"Готово: {', '.join(d['name'] for d in devs)} ({n} из {len(devs)} ответили)"
    except HomeError as e:
        raise ToolError(str(e)) from e


# №406 (29.10): «выключи сет в зале» (распознало «сет» вместо «свет») — модель позвала power {"action": "off", "target": "сет в
# зале»}: спросила, выключать ли компьютер, а свет так и горел. Цель — свет, комната, устройство -> не компьютер.
_NOT_PC = re.compile(r"(?<![а-яё])(?:свет|сет|ламп|люстр|торшер|бра|подсветк|гирлянд|розетк|телевизор|тв|кондиционер|обогревател|"
                     r"чайник|пылесос|колонк|штор|жалюз|вентилятор|в\s+(?!компьютер|систем)[а-яё]+е(?![а-яё])|на\s+кухн)", re.I)


def t_power(a, ctx):
    pw = ctx.get("power")
    if pw is None:
        raise ToolError("управление питанием недоступно")
    tgt = " ".join(str(a.get(k) or "") for k in ("target", "device", "what", "room"))
    if tgt.strip() and _NOT_PC.search(tgt):
        raise ToolError("power выключает только этот компьютер, а просят про свет или устройство в комнате — это умный дом: "
                        "вызови smart_home (выключить свет в нужной комнате). Компьютер не трогай.")
    act = a.get("action") or ""
    if act == "cancel":
        was = pw.cancel()
        if ctx.get("engine"):
            ctx["engine"].emit("power", cancelled=True)
        return "Выключение отменено." if was else "Ничего не было запланировано."
    try:
        msg = pw.schedule(act)
    except ValueError as e:
        raise ToolError(str(e)) from e
    if ctx.get("engine"):
        # виджету: показать отсчёт с кнопкой «Отменить»
        ctx["engine"].emit("power", action=act, seconds=60 if act in ("shutdown", "reboot", "logout") else 0)
    return msg


def t_widget(a, ctx):
    """Виджет — в трей или обратно. Обычно «спрячься» ловит _window_cmd без модели; это — когда фраза расслышана
    неточно и её поняла модель (иначе она обещала «ухожу в трей» и оставалась на экране)."""
    eng = ctx.get("engine")
    if eng is None or not getattr(getattr(eng, "bridge", None), "clients", None):
        raise ToolError("виджета на экране нет")
    act = "show" if a.get("action") == "show" else "tray"
    if act == "tray":
        eng._tray_at = __import__("time").monotonic()    # спрятали — не заговаривать первой (Engine._welcome_back)
    eng.emit("window", do=act)
    return "Виджет спрятан в трей: позовут по имени — появлюсь." if act == "tray" else "Виджет снова на экране."


# ---------- телевизор (Chromecast / Google TV / Android TV) ----------

def _catt(args, timeout=40, device=""):
    """Запустить catt (трансляция на Chromecast) -> (код выхода, вывод). Берём catt рядом с нашим Python (venv)."""
    import sys as _sys
    from pathlib import Path as _P
    exe = _P(_sys.executable).with_name("catt")
    cmd = [str(exe) if exe.exists() else "catt"] + (["-d", device] if device else []) + args
    if DRY:
        launch(cmd)
        return 0, "ok"
    if WIN:                                 # в Windows нет отдельной команды catt — запускаем модуль
        py = _sys.executable
        if py.lower().endswith("pythonw.exe"):          # pythonw не даёт вывода — нужен консольный python.exe
            py = py[:-len("pythonw.exe")] + "python.exe"
        cmd = [py, "-X", "utf8", "-c", "from catt.cli import main; main()"] + cmd[1:]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace",
                           creationflags=0x08000000 if WIN else 0)
    except FileNotFoundError as e:
        raise ToolError("не установлен модуль трансляции (catt) — переустановите Dewiar") from e
    except subprocess.TimeoutExpired as e:
        raise ToolError("телевизор не ответил вовремя") from e
    return r.returncode, (r.stdout + r.stderr).strip()


def _tv_device(a, ctx):
    """Имя телевизора: из аргумента, иначе из настроек tools.tv_device, иначе "" (catt выберет сам)."""
    return (a.get("device") or (ctx["settings"].get("tools", "tv_device") or "") if ctx.get("settings") else a.get("device") or "").strip()


def t_tv(a, ctx):
    action = a.get("action", "play")
    dev = _tv_device(a, ctx)
    if action == "devices":
        code, out = _catt(["scan"], timeout=25)
        if code or "No devices" in out:
            return ("Телевизоров с Chromecast в сети не нашёл. Подходят Chromecast, Google TV, Android TV и телевизоры "
                    "со встроенным Chromecast (Sony, Philips, Xiaomi, TCL…), в той же сети Wi-Fi, что и компьютер.")
        return out
    if action == "play":
        what = (a.get("url") or a.get("query") or "").strip()
        if not what:
            raise ToolError("что показать? нужна ссылка или что найти на YouTube")
        if not re.match(r"^https?://", what):               # «включи на телевизоре клип …» — ищем на YouTube
            try:
                import yt_dlp
                with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "extract_flat": True}) as y:
                    info = y.extract_info(f"ytsearch1:{what}", download=False)
                e = (info.get("entries") or [None])[0]
                if not e:
                    raise ToolError(f"на YouTube не нашлось «{what}»")
                what = e.get("url") or f"https://www.youtube.com/watch?v={e['id']}"
            except ToolError:
                raise
            except Exception as ex:  # noqa: BLE001
                raise ToolError(f"не получилось найти на YouTube: {ex}") from ex
        code, out = _catt(["cast", what], timeout=60, device=dev)
        if code:
            raise ToolError(out[-300:] or "не получилось включить на телевизоре")
        return f"Включил на телевизоре: {what}"
    if action == "site":
        url = (a.get("url") or "").strip()
        if not re.match(r"^https?://", url):
            raise ToolError("нужен адрес сайта")
        code, out = _catt(["cast_site", url], device=dev)
        if code:
            raise ToolError(out[-300:] or "не получилось показать сайт на телевизоре")
        return f"Сайт {url} открыт на телевизоре."
    cmds = {"pause": ["pause"], "resume": ["play"], "stop": ["stop"], "status": ["status"]}
    if action == "volume":
        v = max(0, min(100, int(a.get("level", 30))))
        cmds["volume"] = ["volume", str(v)]
    if action not in cmds:
        raise ToolError("неизвестное действие")
    code, out = _catt(cmds[action], device=dev)
    if code:
        raise ToolError(out[-300:] or "телевизор не ответил")
    return out or "Готово"


# ---------- фоновые задачи ----------

def _tm(ctx):
    """TaskManager (tasks.py) из ctx, иначе ToolError."""
    tm = ctx.get("tasks")
    if tm is None:
        raise ToolError("фоновые задачи недоступны")
    return tm


def t_start_task(a, ctx):
    goal = (a.get("goal") or "").strip()
    if not goal:
        raise ToolError("опиши цель задачи")
    on = (a.get("on") or "").strip()
    if on and ctx.get("remote_task"):                  # «на рабочем компьютере…» (0.56): задача названному своему компьютеру
        try:
            r = ctx["remote_task"](on, a.get("title") or "", goal, (a.get("if_off") or "").strip())
        except ValueError as e:
            raise ToolError(str(e)) from e
        if r is not None:
            return r
    try:
        t = _tm(ctx).create(a.get("title") or goal[:50], goal, a.get("project") or "")
    except ValueError as e:
        raise ToolError(str(e)) from e
    return (f"Задача «{t.title}» запущена в фоне. План и журнал — в папке «Задачи» и в студии. Результата ЕЩЁ НЕТ — он "
            "появится через несколько минут или дольше. Скажи пользователю одной фразой, что взялся и сообщишь, когда будет "
            "готово; не говори «готово», «сделал», «вот презентация» — это неправда, пока задача не закончилась.")


def t_task_status(a, ctx):
    tm = _tm(ctx)
    items = tm.list()
    if not items:
        return "Задач пока нет."
    lines = []
    for x in items[:6]:
        prog = x.get("progress") or [0, 0]
        extra = f", план {prog[0]} из {prog[1]}" if prog[1] else ""
        q = f", вопрос: {x['question']}" if x.get("question") else ""
        w = f", ждёт: {x['wait_reason']}" if x.get("status") == "sleeping" and x.get("wait_reason") else ""
        lines.append(f"«{x['title']}» — {x['status_ru']}, шагов {x.get('steps', 0)}{extra}{q}{w}"
                     + (f". Итог: {x['result'][:300]}" if x.get("result") else ""))
    try:                                                    # главное из блокнота текущей задачи — что уже известно
        cur = tm.get("")
        nb = cur.notebook() if cur.status != "done" else ""
        facts = [ln.strip() for ln in nb.splitlines() if ln.strip().startswith("- ")][:8]
        if facts:
            lines.append(f"Блокнот «{cur.title}»:\n" + "\n".join(facts))
    except (KeyError, AttributeError, OSError):
        pass
    return "\n".join(lines)


def t_remove_task(a, ctx):
    """24.10, владелец: «попросил удалить задачу — она долго рассказывала, что не умеет»."""
    tm = _tm(ctx)
    try:
        t = tm.get(str(a.get("name") or "").strip() or "\u0000")
    except KeyError as e:
        raise ToolError(f"{e}. Задачи: " + ", ".join(f"«{x['title']}»" for x in tm.list()[:8])) from e
    title = t.title
    tm.delete(t.id)
    return f"Задача «{title}» удалена — напоминаний о ней больше не будет."


def t_stop_task(a, ctx):
    try:
        t = _tm(ctx).stop(a.get("name") or "")
    except KeyError as e:
        raise ToolError(str(e)) from e
    return f"Задача «{t.title}» остановлена."


def t_resume_task(a, ctx):
    try:
        t = _tm(ctx).start(a.get("name") or "")
    except KeyError as e:
        raise ToolError(str(e)) from e
    return f"Продолжаю задачу «{t.title}»."


def t_tell_task(a, ctx):
    text = (a.get("text") or "").strip()
    if not text:
        raise ToolError("что передать задаче?")
    try:
        t = _tm(ctx).tell(a.get("name") or "", text)
    except (KeyError, ValueError) as e:
        raise ToolError(str(e)) from e
    return f"Передал задаче «{t.title}» — она учтёт и продолжит работу."


def t_call_persona(a, ctx):
    fn = ctx.get("call_persona")
    if fn is None:
        raise ToolError("переключение персонажей недоступно")
    return fn(str(a.get("name", "")))


# ---------- реестр ----------

# На сервере (main.py --server) нет экрана, звука, камеры и окна — эти инструменты там выключены.
SERVER_OFF = {"council", "open_url", "open_app", "open_path", "show_page", "play_music", "play_radio", "play_youtube", "yandex_music", "media_control",
              "set_volume", "look_at_screen", "save_screenshot", "look_through_camera", "widget", "power"}


def S(props, req=()):
    """JSON-схема параметров инструмента."""
    return {"type": "object", "properties": props, "required": list(req)}


# имя: (описание для модели, схема, риск, обработчик, название в студии)
TOOLS = {
    "route": ("Маршрут на карте: «как дойти до…», «проложи маршрут», «построй пешком дворами», геоточка или ссылка на карту. "
              "to — куда: адрес с городом, место или координаты, ссылка на карту; from — откуда (пусто — от того места, где "
              "пользователь сейчас); mode — walk (пешком, по умолчанию) | transit | car | bike; app — yandex (по умолчанию) | google. "
              "Карта сама строит кратчайший путь (пешком — и дворами); не выдумывай улицы и время.",
              S({"to": {"type": "string"}, "from": {"type": "string"}, "mode": {"type": "string", "enum": ["walk", "transit", "car", "bike"]},
                 "app": {"type": "string", "enum": ["yandex", "google"]}}, ["to"]), "safe", t_route, "Карта: маршрут"),
    "open_url": ("Открыть сайт в браузере по умолчанию.", S({"url": {"type": "string", "description": "адрес сайта"}}, ["url"]), "safe", t_open_url, "Браузер: открыть сайт"),
    "web_search": ("Найти в интернете свежую информацию (новости, курсы, факты; погода — инструментом weather). Возвращает список результатов со ссылками.", S({"query": {"type": "string"}}, ["query"]), "safe", t_web_search, "Поиск в интернете"),
    "app_update": ("Проверить обновления Dewiar на этом компьютере прямо сейчас: «проверь обновления», «есть новая версия?», "
                   "«обновись». Ставит обновление человек — нажатием в виджете.", S({}, []), "safe", t_app_update, "Обновления Dewiar"),
    "weather": ("Погода сейчас и на ближайшие дни по городу (настоящий прогноз; погоду не ищи в интернете — бери отсюда). "
                "city — город (не назван — из памяти о пользователе: «живу в …», «город …»; нет там — спроси; не угадывай и "
                "не подставляй другой город), days — на сколько дней (1–7).",
                S({"city": {"type": "string"}, "days": {"type": "number"}}, ["city"]), "safe", t_weather, "Погода"),
    "read_webpage": ("Прочитать текст веб-страницы по адресу (например, из результатов поиска). Длинная страница — начало и "
                     "места со словами find (или вопроса).", S({"url": {"type": "string"}, "find": {"type": "string", "description":
                     "что ищешь на странице, если она длинная: «Доллар США», «15 октября»"}}, ["url"]), "safe", t_read_webpage, "Чтение веб-страниц"),
    "open_app": ("Запустить установленную программу по названию (Firefox, Терминал, Telegram, Калькулятор…).", S({"name": {"type": "string"}}, ["name"]), "safe", t_open_app, "Запуск программ"),
    "open_path": ("Открыть файл или папку (можно «загрузки», «документы», «рабочий стол» или путь).", S({"path": {"type": "string"}}, ["path"]), "safe", t_open_path, "Открытие файлов и папок"),
    "play_music": ("Включить музыку: открывает поиск в YouTube Music.", S({"query": {"type": "string", "description": "исполнитель, песня или настроение"}}), "safe", t_play_music, "Музыка в YouTube Music"),
    "play_radio": ("Включить радио онлайн внутри ассистента: по названию станции («Европа Плюс», «Радио Маяк»), жанру "
                   "(«джаз», «рок», «классика», «релакс») или пусто — популярное русское. Только чтобы ВКЛЮЧИТЬ: «выключи радио», «хватит» — "
                   "это media_control с action stop, а не play_radio. Не говори «выключила», не вызвав media_control.",
                   S({"query": {"type": "string"}, "url": {"type": "string", "description": "прямая ссылка на поток, если человек её дал (http…)"}}),
                   "safe", t_play_radio, "Радио"),
    "play_youtube": ("Найти и показать ролик на YouTube (откроется в браузере и сразу заиграет): клип, видео, лекция, "
                     "обзор. query — что искать.", S({"query": {"type": "string"}}, ["query"]), "safe", t_play_youtube,
                     "Ролик YouTube"),
    "yandex_music": ("Яндекс Музыка: открыть поиск (жанр, настроение, исполнитель, песня) в приложении Яндекс Музыки, если оно "
                     "установлено, иначе на сайте. Когда просят музыку в Яндекс Музыке или пользователь только что открыл её. "
                     "Запустить/остановить воспроизведение потом — media_control.",
                     S({"query": {"type": "string"}}), "safe", t_yandex_music, "Яндекс Музыка"),
    "media_control": ("Нажать кнопку плеера, который уже открыт (Яндекс Музыка, браузер, Spotify…): play — играть, pause — "
                      "пауза, next/previous — трек вперёд/назад. Всегда этим, а не кликами по экрану и не командами терминала.", S({"action": {"type": "string", "enum": ["play", "pause", "play_pause", "next", "previous", "stop"]}}, ["action"]), "safe", t_media, "Управление плеером"),
    "set_volume": ("Громкость системы: percent (0–150), или change (+/-), или mute (true/false).", S({"percent": {"type": "integer"}, "change": {"type": "integer"}, "mute": {"type": "boolean"}}), "safe", t_volume, "Громкость"),
    "system_status": ("Состояние компьютера: батарея, память, диск, нагрузка и какие программы занимают больше всего памяти. "
                      "Компьютер тормозит или программа зависла — посмотри здесь, назови виновника и предложи закрыть его "
                      "(run_command, pkill по имени программы — только после согласия человека).", S({}), "safe", t_system, "Состояние компьютера"),
    "set_reminder": ("Поставить напоминание, будильник или таймер, в том числе повторяющееся. when — когда, обычными "
                     "словами по-русски: «через 10 минут», «завтра в 9», «в пятницу в 18:30», «каждый день в 8», «по "
                     "будням в 9:15», «по будням, кроме пятницы, в 17:50», «каждые 2 часа». Будни, выходные, дни недели — только в when, не в text. text — о чём напомнить, коротко. "
                     "Напоминание — ЧЕЛОВЕКУ: в срок он сам что-то сделает. Если делать должен ТЫ («проверяй почту», «присылай "
                     "курс», «сообщай о важном», «следи за…») — это schedule_job, а не напоминание.",
                     S({"text": {"type": "string"}, "when": {"type": "string"}, "in_minutes": {"type": "number"},
                        "at": {"type": "string"}, "repeat": {"type": "string", "enum": list(REPEAT_WORDS)}}, ["text"]),
                     "safe", t_reminder, "Напоминания и таймеры"),
    "schedule_job": ("Дело по расписанию, которое делаешь ТЫ сам: проверить почту и сообщить о важном, прислать курс или "
                     "новости, собрать сводку, следить за чем-то. В срок ты выполняешь его с инструментами и сообщаешь итог — "
                     "человеку ничего делать не нужно. Просят регулярно «проверяй / присылай / сообщай / следи» — только это, "
                     "не set_reminder. task — что сделать, своими словами (как поручение тебе); when — повтор обычными словами: "
                     "«каждый день в 9», «по будням с 9 до 18 каждый час», «каждые 2 часа»; «периодически» без интервала — "
                     "«каждый час». deliver — куда сообщать итог: voice (голосом, по умолчанию), telegram, max.",
                     S({"task": {"type": "string"}, "when": {"type": "string"}, "deliver": {"type": "string", "enum": ["voice", "telegram", "max"]}},
                       ["task", "when"]),
                     "safe", t_schedule_job, "Дела по расписанию"),
    "world_time": ("Который час сейчас в другом городе или стране (по часовому поясу). Время в других городах не считай в уме "
                   "и калькулятором — только этим. city — город.", S({"city": {"type": "string"}}, ["city"]), "safe", t_world_time,
                   "Время в городе"),
    "list_reminders": ("Список активных напоминаний.", S({}), "safe", t_list_reminders, "Напоминания: список"),
    "change_reminder": ("Изменить напоминание: время, дни повтора или текст. id (из list_reminders) или text — какое; when — "
                        "новое время и повтор обычными словами: «по будням, кроме пятницы, в 17:50», «с понедельника по четверг "
                        "в 17:50», «каждый день в 8»; new_text — новый текст. В один день недели нужно другое время (по пятницам "
                        "раньше) — change_reminder без этого дня («с понедельника по четверг в 17:50») и set_reminder на этот день "
                        "(«по пятницам в 16:40»). Не говори «изменила», не вызвав инструмент.",
                        S({"id": {"type": "string"}, "text": {"type": "string"}, "when": {"type": "string"}, "new_text": {"type": "string"}}),
                        "safe", t_change_reminder, "Напоминания: изменить"),
    "calc": ("Посчитать точно: любые вычисления (проценты, суммы, скидки, деление, курсы) и даты. Считай ВСЕГДА этим "
             "инструментом, не в уме. Выражение как в Python: 2350 * 17 / 100, (1200 - 15%) * 3; даты в виде ГГГГ-ММ-ДД: "
             "days_until(\"2027-01-01\") — сколько дней осталось до даты, days_between(\"2026-10-01\", \"2026-12-31\"), "
             "weekday(\"2026-10-14\") — день недели, date_add(\"2026-10-10\", 30) — дата через 30 дней.",
             S({"expression": {"type": "string", "description": "выражение"}}, ["expression"]), "safe", t_calc, "Калькулятор"),
    "cancel_reminder": ("Отменить напоминание по id или тексту.", S({"id": {"type": "string"}}, ["id"]), "safe", t_cancel_reminder, "Напоминания: отмена"),
    "mark_done": ("Отметить дела сделанными: пользователь говорит, что сделал («я позвонил Игорю и сделал тренировку», «отметь как "
                  "исполненное», «готово, купил хлеб»). items — каждое дело отдельно и коротко, как оно называется («Позвонить Игорю», "
                  "«Тренировка»); подходящее напоминание на сегодня закроется само. undo: true — снять отметку, если отметили по ошибке.",
                  S({"items": {"type": "array", "items": {"type": "string"}}, "undo": {"type": "boolean"}}, ["items"]), "safe", t_mark_done, "Дела: сделано"),
    "done_report": ("Что пользователь сделал и его достижения: days — за сколько дней (1 — сегодня, 7 — неделя). Для «что я сегодня "
                    "сделал», «сколько дел за неделю», «какие у меня достижения».", S({"days": {"type": "number"}}), "safe", t_done_report, "Дела: итог"),
    "show_images": ("Показать пользователю картинки к тому, о чём рассказываешь (руны и орнаменты, животные и растения, "
                    "картины, здания, места, устройство вещей) — они появятся на экране рядом с ответом. Вызывай, когда "
                    "рассказ о том, что лучше увидеть, или просят «покажи». Ищет как поисковик картинок. query — 2–5 ключевых слов "
                    "(«руническая вязь камень», «Urnes style runestone»); count — сколько (1–6, обычно 3–4); caption — подпись. "
                    "Не говори «вот изображение», не вызвав инструмент.",
                    S({"query": {"type": "string"}, "count": {"type": "integer"}, "caption": {"type": "string"}}, ["query"]),
                    "safe", t_show_images, "Картинки к рассказу"),
    "look_at_screen": ("Посмотреть на экран пользователя (снимок придёт картинкой; нужна модель со зрением). Когда спрашивают, что на "
                       "экране, просят посмотреть на ошибку, окно, текст, график.", S({"question": {"type": "string"}}),
                       "safe", t_look_screen, "Смотрю на экран"),
    "send_email": ("Отправить письмо со своей почты пользователя. Кому (to) — адреса через запятую; пусто — самому "
                   "пользователю («пришли мне на почту»). Тема, текст письма целиком и вложения — пути файлов из папки "
                   "ассистента (заметки, отчёты задач, «Входящие»). Пиши письмо полностью, вежливо, по-русски. «Отправь карточку "
                   "организации / реквизиты Ивану» — найди заметку с реквизитами (find_notes: «реквизиты», «карточка») и приложи "
                   "её файл; адрес по имени — из памяти о пользователе, а если его там нет — спроси одной фразой.",
                   S({"to": {"type": "string"}, "subject": {"type": "string"}, "body": {"type": "string"},
                      "attachments": {"type": "array", "items": {"type": "string"}},
                      "from": {"type": "string", "description": "с какого ящика (адрес), если подключено несколько и назван; иначе — главный"}}, ["subject", "body"]),
                   "confirm", t_send_email, "Отправить письмо"),
    "mailing": ("Рассылка писем многим со своей почты пользователя: КАЖДОМУ своё письмо (адресов друг друга не видят) — "
                "«разошли всем клиентам…», «напиши всем сотрудникам письмо…», «отправь этим 20 адресам…». recipients: clients — "
                "«Клиенты» (у кого есть почта; tag — только с этой меткой), team — сотрудники, list — свой список в list (строки "
                "«Имя адрес»). В теме и тексте {имя} — обращение по имени: «Здравствуйте, {имя}!». kind: work — деловое письмо "
                "(сотрудникам, клиентам по делу), ads — реклама и новости (только тем, кто согласился; строка «отписаться» "
                "добавится сама). Одному-трём адресатам — send_email, не рассылка. Пиши письмо полностью, вежливо.",
                S({"subject": {"type": "string"}, "body": {"type": "string"}, "recipients": {"type": "string", "enum": ["clients", "team", "list"]},
                   "list": {"type": "string"}, "tag": {"type": "string"}, "kind": {"type": "string", "enum": ["work", "ads"]}},
                  ["subject", "body", "recipients"]),
                "confirm", t_mailing, "Рассылка писем"),
    "mailing_status": ("Как идёт рассылка писем: сколько ушло, ошибки, ждёт ли следующего дня.", S({}), "safe", t_mailing_status,
                       "Как идёт рассылка"),
    "send_telegram": ("Прислать пользователю в мессенджер (Telegram или MAX — куда подключён) сообщение (text) и/или файлы "
                      "из папки ассистента (files — пути: заметки, отчёты задач, «Входящие», снимки). «Пришли мне в "
                      "телеграм…», «скинь в макс…», «скинь на телефон…». to — telegram или max, если назван мессенджер.",
                      S({"text": {"type": "string"}, "files": {"type": "array", "items": {"type": "string"}},
                         "to": {"type": "string", "enum": ["telegram", "max"]}}),
                      "safe", t_send_telegram, "Прислать в Telegram или MAX"),
    "read_emails": ("Посмотреть почту пользователя: последние письма (кто, тема, начало). unread_only — только "
                    "непрочитанные, query — слово для поиска (отправитель, тема, текст). Письма не помечаются прочитанными. "
                    "Ящиков несколько — смотрит все сразу; box — адрес одного ящика, если пользователь его назвал.",
                    S({"limit": {"type": "integer"}, "unread_only": {"type": "boolean"}, "query": {"type": "string"},
                       "box": {"type": "string"}}),
                    "safe", t_read_emails, "Проверить почту"),
    "read_email": ("Прочитать одно письмо целиком по номеру из read_emails.", S({"uid": {"type": "string"}}, ["uid"]),
                   "safe", t_read_email, "Прочитать письмо"),
    "search_documents": ("Найти в документах пользователя на этом компьютере (папка «Знания» и его папки, выбранные для "
                         "поиска: инструкции, договоры, регламенты, книги, конспекты, рабочие файлы). Вызывай, когда вопрос "
                         "про его документы или файлы, «что написано в…», «найди в моих документах». "
                         "Запрос — ключевые слова по-русски, без лишних слов.",
                         S({"query": {"type": "string"}}, ["query"]), "safe", t_search_documents, "Мои документы"),
    "ask_knowledge": ("Спросить Знания пользователя на сайте Dewiar — его загруженные документы, регламенты, базы "
                      "знаний компании. Вызывай, когда вопрос про его документы, работу, компанию или «что у меня в "
                      "Знаниях». Вопрос пиши полностью, без «это» и «там». Ответ приходит с источниками — назови их.",
                      S({"question": {"type": "string"}, "base": {"type": "string", "description": "необязательно: название "
                         "папки или раздела публичной библиотеки, если пользователь его назвал («в Библии», «в истории РФ»)"}},
                        ["question"]), "safe", t_ask_knowledge, "Знания с сайта"),
    "save_screenshot": ("Сделать снимок экрана и сохранить его файлом в «Изображения/Снимки экрана». Вызывай, когда "
                        "просят «сделай скриншот», «сфотографируй экран», «сохрани экран». Смотреть на снимок не нужно.",
                        S({}, []), "safe", t_save_screenshot, "Скриншот"),
    "look_through_camera": ("Сделать кадр с веб-камеры (придёт картинкой). Когда просят посмотреть на что-то в руках "
                            "или в комнате.", S({"question": {"type": "string"}}), "confirm", t_look_camera, "Камера"),
    "create_skill": ("Создать новый навык (инструкцию для особой задачи), когда пользователь просит научиться чему-то "
                     "или запомнить порядок действий. name — латиницей через дефис; description — когда применять; "
                     "instructions — пошаговые инструкции для тебя самого.",
                     S({"name": {"type": "string"}, "description": {"type": "string"}, "instructions": {"type": "string"}},
                       ["name", "description", "instructions"]), "confirm", t_create_skill, "Создание навыка"),
    "watch": ("«Дозор»: присмотреть и сказать, когда готово — «скажи, когда Claude ответит», «присмотри за экраном, пока "
              "идёт экспорт», «скажи, когда в Загрузках появится файл», «скажи, когда на странице появится „Одобрено“». "
              "action: add (по умолчанию) | list (что сейчас под присмотром) | stop (id или пусто — все). kind: screen — "
              "экран (what — что должно появиться, своими словами, конкретно), file — папка (folder: «Загрузки» или путь; "
              "pattern: «*.mp4»), page — страница (url; what — слово, которое должно появиться, или пусто — любое изменение). "
              "every_minutes — как часто смотреть (экран — по умолчанию 5), hours — сколько ждать (по умолчанию 3).",
              S({"action": {"type": "string", "enum": ["add", "list", "stop"]}, "kind": {"type": "string", "enum": ["screen", "file", "page"]},
                 "what": {"type": "string"}, "every_minutes": {"type": "number"}, "hours": {"type": "number"},
                 "folder": {"type": "string"}, "pattern": {"type": "string"}, "url": {"type": "string"}, "id": {"type": "string"}}, []),
              "safe", t_watch, "Дозор"),
    "debate": ("Спор моделей: две разные модели ИИ отвечают на трудный вопрос и возражают друг другу, потом ты подводишь итог — "
               "когда просят «пусть модели поспорят», «устрой спор моделей», «что скажут разные ИИ о …». question — вопрос целиком.",
               S({"question": {"type": "string"}}, ["question"]), "safe", t_debate, "Спор моделей"),
    "council": ("«Совет ИИ»: персонажи (у каждого свой характер и своя модель) вместе обсуждают вопрос, спорят и подводят итог — "
                "когда просят «собери совет», «посоветуйся с командой», «что скажет совет ИИ о …», «обсудите вместе». "
                "Обсуждение идёт в студии (откроется само) минуту-две; итог прозвучит сам, когда совет закончит — сейчас скажи одной "
                "фразой, что совет собран, и не отвечай на вопрос сам. question — вопрос целиком.",
                S({"question": {"type": "string"}}, ["question"]), "safe", t_council, "Совет ИИ"),
    "writing_today": ("Сколько пользователь написал сегодня в своих текстах (рукопись, статьи, конспекты в папках «Документов»): "
                      "слова за день, цель, за неделю, дни подряд, в каких файлах. Когда спрашивают «сколько я написал сегодня», "
                      "«много ли я написал», «как идёт книга», «сколько слов в моей рукописи».", S({}, []), "safe", t_writing_today, "Пишу"),
    "month_summary": ("Итоги месяца пользователя («Мой месяц с Лирой»): сделанные дела, напоминания, траты по категориям, заметки, "
                      "дневник — когда спрашивают «как прошёл мой месяц», «итоги октября», «что я сделал за месяц». month — 2026-10, "
                      "prev — прошлый месяц, пусто — текущий.", S({"month": {"type": "string"}}, []), "safe", t_month_summary, "Мой месяц"),
    "suggest_idea": ("Предложить идею разработчику Dewiar («Идеи Лиры»): когда пользователь просит «предложи идею…» или согласился "
                     "предложить то, чего ты не умеешь. title — суть одной фразой («Будильник с плавным рассветом»), text — подробнее, "
                     "если человек объяснил. Похожая уже есть — голос уйдёт за неё. Без согласия пользователя не вызывай.",
                     S({"title": {"type": "string"}, "text": {"type": "string"}}, ["title"]), "safe", t_suggest_idea, "Идеи Лиры"),
    "show_page": ("Показать в браузере красиво оформленную страницу — когда просят «покажи в браузере», «оформи красиво», "
                  "«сделай страницу / подборку / таблицу»: рецепты, список, сравнение, отчёт. Сначала собери данные "
                  "(find_notes, read_file, web_search), потом одним вызовом передай html — разметку содержимого: <section> с "
                  "<h2>, списки, таблицы (оформление и заголовок добавятся сами) или полный документ. Сохранится в «Страницы» и "
                  "откроется. НЕ пиши HTML в ответе, НЕ пиши скрипты ради этого. Показать СВОЮ заметку или файл пользователя "
                  "(«выведи мою заметку про … в браузере») — передай file: путь из find_notes, без html: текст покажется "
                  "целиком, как есть.",
                  S({"title": {"type": "string"}, "html": {"type": "string"}, "file": {"type": "string"}}, []), "safe", t_show_page, "Страницы"),
    "save_link": ("Сохранить ссылку — видео, статью, сайт — в «Заметки» (там она карточкой с обложкой, с меткой «интересное»): "
                  "когда просят «сохрани это видео / ссылку / статью», «отложи почитать», «запомни этот ролик». url — адрес "
                  "целиком; summary — короткий пересказ своими словами, если просили пересказать (сначала прочитай страницу "
                  "read_webpage); tags — свои метки (необязательно); title — если пользователь назвал сам.",
                  S({"url": {"type": "string"}, "summary": {"type": "string"}, "title": {"type": "string"},
                     "tags": {"type": "array", "items": {"type": "string"}}}, ["url"]), "safe", t_save_link, "Заметки"),
    "save_note": ("Сохранить заметку в папку ассистента (Markdown): когда просят записать, запомнить текст, составить "
                  "список, план, конспект. title — короткое название; text — содержимое в Markdown; folder — подпапка "
                  "(необязательно); append=true — дописать в существующую заметку.",
                  S({"title": {"type": "string"}, "text": {"type": "string"}, "folder": {"type": "string"},
                     "append": {"type": "boolean"}}, ["title", "text"]), "safe", t_save_note, "Заметки"),
    "calendar_list": ("Календарь пользователя за период: встречи и события из его календарей (Google, Яндекс), "
                      "напоминания (и что уже прозвенело), заметки, дневник, задачи, деньги — по дням. Для «что у меня "
                      "завтра?», «какие встречи на неделе?», «что я сделал за неделю». from/to — ГГГГ-ММ-ДД "
                      "(пусто — последние 7 дней; про будущее — укажи даты вперёд).", S({"from": {"type": "string"}, "to": {"type": "string"}}), "safe",
                      t_calendar_list, "Календарь"),
    "money_add": ("Записать уже сделанный расход или полученный доход: «купил продукты на 40», «получил зарплату». "
                  "Бюджет, лимит, план («бюджет на мебель — 50 тысяч», «заложим 70») — НЕ расход и не доход: это remember. "
                  "kind — expense|income; amount — число; currency — код (BYN, RUB, USD, EUR), пусто — основная; "
                  "category — категория по-русски («Продукты», «Транспорт», «Зарплата»…); note — что именно; "
                  "date — ГГГГ-ММ-ДД, пусто — сегодня. Несколько покупок — несколько вызовов.",
                  S({"kind": {"type": "string", "enum": ["expense", "income"]}, "amount": {"type": "number"},
                     "currency": {"type": "string"}, "category": {"type": "string"}, "note": {"type": "string"},
                     "date": {"type": "string"}}, ["kind", "amount"]), "safe", t_money_add, "Деньги: записать"),
    "close_send": ("Написать человеку из «Близких» (переписка между помощниками Dewiar: дойдёт в его приложение, его помощник "
                   "скажет вслух). Только когда пользователь прямо просит написать, передать или сказать кому-то из близких. "
                   "to — имя как сказал пользователь («Андрею», «маме») или группа своих («в группу Семья» — письмо всем в ней); text — само сообщение от лица пользователя, как он сказал бы сам "
                   "(«Задержусь на полчаса»), без «передай»; files — пути файлов (необязательно). «Напомни всем в группе Семья в субботу "
                   "в 10 про дачу» — to: группа, text: о чём («Едем на дачу»), remind_when: когда («в субботу в 10») — напоминание встанет у всех.",
                   S({"to": {"type": "string"}, "text": {"type": "string"}, "files": {"type": "array", "items": {"type": "string"}},
                      "remind_when": {"type": "string"}}, ["to", "text"]),
                   "safe", t_close_send, "Близкие: написать"),
    "close_call": ("Позвонить человеку из «Близких» через Dewiar — откроется окно звонка (video true — видеозвонок). Только когда "
                   "пользователь прямо просит позвонить кому-то из близких.",
                   S({"to": {"type": "string"}, "video": {"type": "boolean"}}, ["to"]), "safe", t_close_call, "Близкие: позвонить"),
    "team_assign": ("Поручить задачу сотруднику (раздел «Поручения») — уйдёт ему в Telegram с кнопками «Беру», «Сделано», «Перенести». "
                    "Только когда пользователь прямо поручает что-то сотруднику («поручи Анне…», «пусть Иван подготовит…»). "
                    "who — имя как сказал пользователь; task — что сделать, коротко, повелительно или как дело («Подготовить договор "
                    "поставки»); due — срок словами как сказал («до четверга 15:00», «завтра к 12») или пусто; повторяющееся поручение — "
                    "срок с «каждый»/«по будням» как сказал («каждый понедельник к 18», «по будням к 10»); note — подробности.",
                    S({"who": {"type": "string"}, "task": {"type": "string"}, "due": {"type": "string"}, "note": {"type": "string"}},
                      ["who", "task"]), "safe", t_team_assign, "Поручения: поручить"),
    "team_message": ("Написать сотруднику из «Поручений» не по поручению — ответить на его сообщение или сказать что-то («напиши Анне, "
                     "что отчёт жду к обеду», «ответь Ивану: хорошо»). Дойдёт туда, где он получает поручения. who — имя, text — само "
                     "сообщение от лица пользователя.", S({"who": {"type": "string"}, "text": {"type": "string"}}, ["who", "text"]),
                     "safe", t_team_message, "Поручения: написать сотруднику"),
    "team_status": ("Что с поручениями сотрудникам: кто взял, кто сделал (с отчётом), что перенесено и почему, что просрочено. "
                    "who — имя или пусто — все.", S({"who": {"type": "string"}}), "safe", t_team_status, "Поручения: что с ними"),
    "client_note": ("«Клиенты» (личная CRM): записать в карточку клиента, о чём договорились, что хочет, звонок, сделку. "
                    "«Запиши: Иванов из „Ромашки“ хочет 200 коробок до пятницы», «клиент Петров звонил, просит скидку». Нет такого "
                    "клиента — карточка заведётся сама. who — имя клиента как сказал (или название компании); company — компания в "
                    "именительном падеже («Ромашка»), если названа; text — суть, коротко, своими словами в прошедшем или настоящем "
                    "(«Хочет 200 коробок до пятницы»); kind — note|call|deal; phone, email — если продиктовали.",
                    S({"who": {"type": "string"}, "company": {"type": "string"}, "text": {"type": "string"},
                       "kind": {"type": "string", "enum": ["note", "call", "deal"]}, "phone": {"type": "string"}, "email": {"type": "string"}},
                      ["who", "text"]), "safe", t_client_note, "Клиенты: записать"),
    "client_info": ("«Клиенты»: карточка клиента — контакты, о чём договаривались (последние записи), следующий шаг. «Что у нас с "
                    "Ивановым?», «напомни, о чём договорились с „Ромашкой“». who — имя или компания.",
                    S({"who": {"type": "string"}}, ["who"]), "safe", t_client_info, "Клиенты: карточка"),
    "client_crm": ("«Клиенты»: передать клиента в CRM пользователя (Битрикс24 или свой вебхук) — «передай Иванова в Битрикс», "
                   "«заведи лид на „Ромашку“», «отправь в CRM, о чём договорились с Петровым». Первый раз — новым лидом, дальше — "
                   "новые записи комментарием. who — имя или компания.",
                   S({"who": {"type": "string"}}, ["who"]), "safe", t_client_crm, "Клиенты: в CRM"),
    "channel_post": ("Опубликовать пост от имени бота персонажа в Telegram-канале или группе, где он состоит: «опубликуй в канале…», "
                     "«запланируй пост на пятницу в 10», «сделай опрос в группе». text — пост целиком (напиши его сам, по делу, "
                     "без выдуманных отзывов, цифр и собеседников — только факты пользователя), when — когда словами (пусто — сейчас), "
                     "chat — название канала или группы, если назван; опрос — poll_question и 2–10 poll_options.",
                     S({"text": {"type": "string"}, "when": {"type": "string"}, "chat": {"type": "string"},
                        "poll_question": {"type": "string"}, "poll_options": {"type": "array", "items": {"type": "string"}}}),
                     "confirm", t_channel_post, "Пост в канал"),
    "client_next": ("«Клиенты»: следующий шаг с клиентом — что сделать и когда («перезвонить Иванову в четверг в 11», «отправить "
                    "«Ромашке» счёт завтра»); когда — словами, как сказал пользователь; будет напоминание в «Делах». done true — "
                    "следующий шаг сделан («я перезвонил Иванову»).",
                    S({"who": {"type": "string"}, "what": {"type": "string"}, "when": {"type": "string"}, "done": {"type": "boolean"}},
                      ["who"]), "safe", t_client_next, "Клиенты: следующий шаг"),
    "client_list": ("«Клиенты»: кто ждёт ответа (просроченные шаги), ближайшие шаги, клиенты без следующего шага. «Кому из клиентов "
                    "надо перезвонить?», «что по клиентам на этой неделе?». query — поиск по имени, компании или записям, или пусто.",
                    S({"query": {"type": "string"}}), "safe", t_client_list, "Клиенты: кто ждёт"),
    "client_deal": ("«Клиенты» → сделки: новая сделка или её этап. Этапы: lead — заявка, offer — предложение (КП, смета), invoice — "
                    "счёт выставлен (нам должны), paid — оплачено, lost — отказ. «Ромашке выставили счёт на 1200 за коробки, оплатить "
                    "до пятницы» → who «Ромашка», title «Коробки», amount 1200, stage invoice, due «до пятницы»; «Ромашка оплатила "
                    "счёт» → stage paid (оплата сама запишется в доходы); «Иванов отказался» → lost. Есть открытая сделка — двигает "
                    "её; new true — точно новая. title — коротко, что продаём; due — срок оплаты словами.",
                    S({"who": {"type": "string"}, "title": {"type": "string"}, "amount": {"type": "number"},
                       "stage": {"type": "string", "enum": ["lead", "offer", "invoice", "paid", "lost"]}, "due": {"type": "string"},
                       "new": {"type": "boolean"}}, ["who"]), "safe", t_client_deal, "Клиенты: сделка"),
    "deal_remind": ("Напомнить клиенту об оплате выставленного счёта — вежливое письмо с его почты пользователя («напомни Ромашке об "
                    "оплате», «напиши Иванову, что ждём оплату»). who — клиент, title — какая сделка (если счетов несколько).",
                    S({"who": {"type": "string"}, "title": {"type": "string"}}, ["who"]), "confirm", t_deal_remind, "Клиенты: напомнить об оплате"),
    "client_deals": ("«Клиенты» → сделки: «кто нам должен?» (what owed — выставленные неоплаченные счета, итог, просроченные), "
                     "«какие сделки зависли?» (stuck — без движения неделю, просроченная оплата), или все открытые (пусто).",
                     S({"what": {"type": "string", "enum": ["owed", "stuck", ""]}}), "safe", t_client_deals, "Клиенты: кто должен"),
    "close_read": ("Последние сообщения от близких (и мои им): «что мне писали», «что ответил Андрей»; группа — «что ответили в группе "
                   "Семья», «кто что берёт?» (собери ответы по людям). who — имя, группа или пусто — все.",
                   S({"who": {"type": "string"}}), "safe", t_close_read, "Близкие: прочитать"),
    "app_help": ("Руководство Dewiar — как пользоваться самим этим приложением: где кнопка или раздел, как настроить, как пригласить "
                 "близкого или друга, сканер, стили, напоминания на часах, синхронизация, данные и т. п. Вызывай, когда спрашивают про "
                 "Dewiar и его функции («как…», «где…», «что ты умеешь…»), — не выдумывай меню и кнопки. query — о чём спросили; "
                 "where — pc|phone, если ясно, про какое устройство.",
                 S({"query": {"type": "string"}, "where": {"type": "string", "enum": ["pc", "phone"]}}, ["query"]), "safe", t_app_help, "Руководство"),
    "payments": ("«Платежи» — реестр обязательных оплат (коммунальные, связь, кредиты, страховка): у каждого счёта реквизиты "
                 "«как платить», срок, история оплат с показаниями счётчика. action: open — что не оплачено в этом месяце; report — "
                 "сводка (или bill — по одному счёту: как платить и последние оплаты); year — итоги года по счетам (year); "
                 "add_payment — записать оплату (bill, amount, reading — показание, used — расход, date ГГГГ-ММ-ДД, status "
                 "paid|unpaid); add_bill — новый вид платежа (bill — название, kind meter|fixed|loan|yearly|other, day — число "
                 "срока, how — реквизиты). Это не «Деньги»: разовые покупки — туда, а счета и их оплаты — сюда.",
                 S({"action": {"type": "string", "enum": ["open", "report", "year", "add_payment", "add_bill"]}, "bill": {"type": "string"},
                    "amount": {"type": "number"}, "reading": {"type": "number"}, "used": {"type": "number"}, "date": {"type": "string"},
                    "status": {"type": "string", "enum": ["paid", "unpaid"]}, "kind": {"type": "string"}, "day": {"type": "integer"},
                    "month": {"type": "integer"}, "how": {"type": "string"}, "year": {"type": "integer"}, "note": {"type": "string"}},
                   ["action"]), "safe", lambda a, ctx: __import__("engine_pay").t_payments(a, ctx), "Платежи"),
    "money_report": ("Итоги личного бюджета за период: доходы, расходы по категориям, остаток, последние операции. "
                     "from/to — ГГГГ-ММ-ДД (пусто — текущий месяц).",
                     S({"from": {"type": "string"}, "to": {"type": "string"}}), "safe", t_money_report, "Деньги: отчёт"),
    "find_notes": ("Найти в папке ассистента заметки, дневник, память по словам (что записывали раньше); если подключён "
                   "Obsidian — и в заметках пользователя там (пути «obsidian:…»).",
                   S({"query": {"type": "string"}}, ["query"]), "safe", t_find_notes, "Поиск по заметкам"),
    "read_file": ("Прочитать файл из папки ассистента (путь из find_notes или из списка).",
                  S({"path": {"type": "string"}}, ["path"]), "safe", t_read_file, "Чтение заметок"),
    "remember": ("Запомнить надолго факт о пользователе: имя, близкие, работа, предпочтения, привычки, важные даты. "
                 "Одна короткая фраза в третьем лице («Любит крепкий чай», «Дочь зовут Аня»).",
                 S({"fact": {"type": "string"}}, ["fact"]), "safe", t_remember, "Память о вас"),
    "write_diary": ("Записать в свой дневник короткое наблюдение после содержательного разговора: что обсуждали, что "
                    "пользователю важно, что в следующий раз сделать лучше. Не чаще раза за разговор.",
                    S({"entry": {"type": "string"}}, ["entry"]), "safe", t_write_diary, "Дневник"),
    "lab_write": ("Записать файл в свою лабораторию (скрипт .py или .sh, данные, черновик) — когда задачу удобнее "
                  "решить кодом: расчёты, обработка файлов, анализ. name — имя файла, можно с подпапкой.",
                  S({"name": {"type": "string"}, "content": {"type": "string"}}, ["name", "content"]), "safe",
                  t_lab_write, "Лаборатория: запись"),
    "lab_run": ("Запустить скрипт из лаборатории (" + (".py — Python, .ps1 — PowerShell, .bat — cmd" if WIN else ".py — Python, .sh — bash") + ") и получить вывод. Работает 2 минуты максимум.",
                S({"name": {"type": "string"}, "args": {"type": "string"}}, ["name"]), "confirm", t_lab_run,
                "Лаборатория: запуск"),
    "start_task": ("Запустить большую задачу в фоне: исследование с отчётом, работа с кодом проекта, подготовка "
                   "документа, разбор файлов, дело на несколько дней с ожиданием ответов (вернуть билет, добиться "
                   "ответа, проследить статус) — всё, что требует многих шагов. Ассистент работает сам по плану, "
                   "ведёт блокнот фактов, ждёт и возвращается к делу, сообщает новости и скажет, когда готово. project — путь к папке проекта для работы с "
                   "кодом (необязательно).",
                   S({"title": {"type": "string"}, "goal": {"type": "string", "description": "подробная цель"},
                      "project": {"type": "string"},
                      "on": {"type": "string", "description": "на каком своём компьютере («на рабочем», «Ноутбук») — имя из списка компьютеров; пусто — здесь"},
                      "if_off": {"type": "string", "enum": ["", "wait", "cloud"], "description": "тот компьютер не на связи: wait — сделать, когда включится; cloud — сейчас в облаке Dewiar (только если пользователь так ответил)"}},
                     ["goal"]), "safe", t_start_task, "Фоновая задача"),
    "task_status": ("Как идут фоновые задачи: статус, прогресс, вопросы, итог.", S({}), "safe", t_task_status,
                    "Задачи: статус"),
    "stop_task": ("Остановить фоновую задачу (name — часть названия; пусто — текущую).",
                  S({"name": {"type": "string"}}), "safe", t_stop_task, "Задачи: стоп"),
    "remove_task": ("Удалить фоновую задачу совсем — из списка «Задачи», с её папкой и файлами (name — часть названия). "
                    "Когда просят «удали задачу», «убери эту задачу», «хватит напоминать про задачу». Сначала спроси, если "
                    "у задачи есть готовые файлы, которые человек мог бы хотеть сохранить.",
                    S({"name": {"type": "string"}}, ["name"]), "safe", t_remove_task, "Задачи: удалить"),
    "resume_task": ("Продолжить остановленную или приостановленную задачу (или ждущую — прямо сейчас).",
                    S({"name": {"type": "string"}}), "safe", t_resume_task, "Задачи: продолжить"),
    "tell_task": ("Передать фоновой задаче новые сведения, уточнение или просьбу пользователя (например: «по багажу "
                  "ответили, номер такой-то», «бюджет до 500 евро»). Ждущая задача сразу проснётся и учтёт. "
                  "name — часть названия (пусто — текущая).",
                  S({"name": {"type": "string"}, "text": {"type": "string"}}, ["text"]), "safe", t_tell_task,
                  "Задачи: сообщить"),
    "tv": ("Телевизор с Chromecast / Google TV / Android TV в домашней сети. action: play — включить видео по ссылке "
           "или найти на YouTube (query); site — показать сайт; pause, resume, stop, volume (level 0–100), status; "
           "devices — какие телевизоры видны. Используй, когда просят включить что-то на телевизоре или "
           "«транслировать на ТВ».",
           S({"action": {"type": "string", "enum": ["play", "site", "pause", "resume", "stop", "volume", "status", "devices"]},
              "url": {"type": "string"}, "query": {"type": "string"}, "level": {"type": "integer"},
              "device": {"type": "string", "description": "имя телевизора, если их несколько"}}, ["action"]),
           "safe", t_tv, "Телевизор"),
    "call_persona": ("Позвать другого персонажа команды (Агент, Лира, Патрик, Джарвис, Эва, Кодер или созданного "
                     "пользователем), когда пользователь просит позвать, передать слово или поговорить с ним. После "
                     "твоего ответа персонаж сам откликнется своим голосом и обликом и продолжит разговор.",
                     S({"name": {"type": "string", "description": "имя персонажа"}}, ["name"]), "safe", t_call_persona,
                     "Позвать персонажа"),
    "delete_files": ("Удалить файлы или папки пользователя — В КОРЗИНУ (можно восстановить). paths — полные пути "
                     "(~ — домашняя папка). Системные папки, домашнюю папку целиком и главные папки (Документы, "
                     "Загрузки, Рабочий стол…) удалить нельзя — защита откажет. Для удаления используй только это, не "
                     "команды терминала. Если просят «удали всё» — сначала уточни, что именно.",
                     S({"paths": {"type": "array", "items": {"type": "string"}}}, ["paths"]), "confirm", t_delete_files,
                     "Удаление в корзину"),
    "smart_home": ("Умный дом (Яндекс — устройства, что у Алисы, и Home Assistant): action — list (какие есть устройства, сценарии и показания датчиков: температура, влажность в комнатах), on, off, "
                   "brightness (value 1–100), brighter, dimmer, temperature (value, °C), warm (value −1 теплее, 1 холоднее), "
                   "scenario (target — название сценария). target — устройство и/или комната словами: «свет в спальне», "
                   "«весь свет», «кондиционер», «розетка на кухне».",
                   S({"action": {"type": "string", "enum": ["list", "on", "off", "brightness", "brighter", "dimmer", "temperature", "warm", "scenario"]},
                      "target": {"type": "string"}, "value": {"type": "number"}}, ["action"]), "safe", t_smart_home, "Умный дом"),
    "widget": ("Спрятать свой виджет в трей (tray) или вернуть на экран (show) — когда просят «спрячься», «уйди в трей», "
               "«покажись». Скажи после этого одной короткой фразой.",
               S({"action": {"type": "string", "enum": ["tray", "show"]}}, ["action"]), "safe", t_widget, "Окно ассистента"),
    "power": ("Питание компьютера: shutdown — выключить, reboot — перезагрузить (оба через минуту, можно отменить), "
              "sleep — спящий режим, lock — заблокировать экран, logout — выйти из системы, cancel — отменить "
              "выключение. Только когда пользователь явно просит выключить КОМПЬЮТЕР. «Выключи свет», «выключи в зале», "
              "лампу, телевизор, кондиционер — это умный дом (smart_home), не power.",
              S({"action": {"type": "string", "enum": ["shutdown", "reboot", "sleep", "lock", "logout", "cancel"]}},
                ["action"]), "confirm", t_power, "Питание компьютера"),
    "server_run": ("Выполнить команду на сервере пользователя по SSH (Linux, bash) и вернуть вывод: проверить место, "
                   "нагрузку, логи, службы, сайт; исправить проблему. server — имя сервера из списка, command — команда. "
                   "Сначала смотри (df -h, free -m, systemctl status, journalctl -n 50, tail логов), потом предлагай "
                   "исправление одной понятной командой. Интерактивное (top без -b, nano, less) не работает — бери "
                   "top -bn1, cat, tail. Каждую команду пользователь подтверждает.",
                   S({"server": {"type": "string"}, "command": {"type": "string"}, "timeout": {"type": "integer"}}, ["server", "command"]),
                   "confirm", t_server_run, "Команды на сервере"),
    "run_command": (("Выполнить команду в PowerShell (Windows)" if WIN else "Выполнить команду в терминале Linux (bash)") + " и вернуть вывод. Только если пользователь явно просит.", S({"command": {"type": "string"}}, ["command"]), "confirm", t_run_command, "Команды терминала"),
}
# Этим умениям нужен интернет из самого Dewiar — при стоп-кране (студия → «Безопасность») модель о них не узнаёт.
# Открыть сайт, музыку или карту в браузере человека — можно: это его браузер и его просьба.
NET_TOOLS = {"web_search", "weather", "read_webpage", "send_email", "mailing", "client_crm", "channel_post", "read_emails", "read_email", "send_telegram", "close_send",
             "close_call", "close_read", "team_assign", "deal_remind", "ask_knowledge", "play_radio", "smart_home", "show_images", "server_run", "app_update"}
DEFAULT_OFF = set()          # команды терминала включены, но каждая — только после «Выполнить?»
# «Только безопасное» (студия → «Безопасность», отзыв 18.10: «лучше чтоб пользователь мог выбрать, что можно делать, а не
# что нельзя — разрешаю только калькулятор»): разговор, напоминания, заметки, деньги, поиск и чтение — ничего на компьютере
# не трогают и ничего не отправляют от вашего имени. Остальное кнопка выключает; включить по одному — «Руки» → «Умения».
SAFE_CORE = {"calc", "world_time", "weather", "web_search", "read_webpage", "show_images", "set_reminder", "list_reminders",
             "cancel_reminder", "change_reminder", "mark_done", "done_report", "save_note", "save_link", "show_page", "suggest_idea", "month_summary", "writing_today", "watch", "find_notes", "read_file", "remember", "write_diary",
             "money_add", "money_report", "payments", "calendar_list", "app_help", "call_persona", "widget", "play_radio", "media_control",
             "set_volume", "system_status", "task_status", "search_documents", "ask_knowledge", "client_note", "client_info", "client_next",
             "client_list", "client_deal", "client_deals"}


# инструменты навыков (skills.py): есть, только когда навыки включены; выполняет Toolbox.run
SKILL_TOOLS = {
    "use_skill": ("Загрузить инструкции навыка по имени (из списка навыков) и следовать им.",
                  S({"name": {"type": "string"}}, ["name"])),
    "read_skill_file": ("Прочитать дополнительный файл навыка (путь из списка файлов навыка).",
                        S({"name": {"type": "string"}, "path": {"type": "string"}}, ["name", "path"])),
}


class Toolbox:
    """Что модели доступно и как это выполнить: TOOLS + инструменты навыков + MCP. Пользуются чат (engine_tools.py)
    и задачи (tasks.py)."""
    def __init__(self, settings, reminders, skills=None, mcp=None):
        self.s, self.reminders, self.skills, self.mcp = settings, reminders, skills, mcp
        self.hooks = {}          # объекты и действия ядра (почта, задачи, Telegram, позвать персонажа…) — кладёт engine.py,
                                 # уходят в ctx обработчиков; по ним же policy решает, подключена ли служба

    def policy(self, name):
        """-> (включён, нужно подтверждение). Инструменты неподключённых служб выключены — модель о них и не узнает."""
        kids = self.hooks.get("kids")
        if kids is not None and kids.on() and name not in kids.tools():
            return False, False                 # детский режим (kids.py): только безопасные умения
        if name in SKILL_TOOLS:
            return bool(self.skills and self.skills.enabled()), False
        if self.mcp and self.mcp.has(name):
            conf = (self.s.get("tools", "confirm") or {}).get(name)
            return True, self.mcp.needs_confirm(name) if conf is None else bool(conf)
        if name not in TOOLS:
            return False, False
        if name in ("send_email", "read_emails", "read_email", "mailing", "mailing_status"):     # только когда почта подключена
            m = self.hooks.get("mail")
            if not (m and m.configured()):
                return False, False
        if name in SERVER_OFF and self.hooks.get("server"):   # сервер без экрана и звука: «открыла сайт» было бы неправдой
            return False, False
        if name == "smart_home":                # только когда подключён умный дом (Яндекс или Home Assistant)
            h = self.hooks.get("home")
            if not (h and h.connected()):
                return False, False
        if name == "send_telegram":             # только когда бот подключён к владельцу
            tg = self.hooks.get("telegram")
            if not (tg and tg.paired()):
                return False, False
        if name == "channel_post":               # посты — когда бот персонажа подключён и состоит в канале или группе
            P = self.hooks.get("pbot_posts")
            if not (P is not None and P.bot.connected() and any(c["can"] for c in P.chats())):
                return False, False
        if name.startswith("client_") or name == "deal_remind":   # «Клиенты»: включены в «Возможностях»
            if not (self.hooks.get("clients") is not None and (self.s.get("features") or {}).get("clients")):
                return False, False
            if name == "client_crm" and not (self.hooks.get("crm") and self.hooks["crm"].connected()):   # и CRM подключена
                return False, False
        if name in ("team_assign", "team_status", "team_message"):   # «Поручения»: раздел включён и бот компании подключён
            tm = self.hooks.get("team")
            if not (tm and tm.connected() and (self.s.get("features") or {}).get("team")):
                return False, False
        if name == "server_run":                # только когда добавлен хотя бы один сервер
            sv = self.hooks.get("servers")
            if not (sv and sv.items):
                return False, False
        if name == "search_documents":          # только когда в «Знаниях» есть документы
            kn = self.hooks.get("knowledge")
            if not (kn and kn.has_files()):
                return False, False
        if name == "ask_knowledge":             # только после входа в аккаунт сайта
            acc = self.hooks.get("account")
            if not (acc and acc.logged_in()):
                return False, False
        if name in NET_TOOLS and (self.s.get("privacy") or {}).get("local_only"):
            return False, False                 # стоп-кран «Ничего не уходит в интернет»: этим нужен интернет (off_note скажет модели)
        if name == "run_command" and (self.s.get("privacy") or {}).get("files") == "folder":
            return False, False                 # замок «Файлы: только папка Dewiar» (студия → «Безопасность»): терминал может всё
        t = self.s.get("tools") or {}
        on = t.get("enabled", {}).get(name, name not in DEFAULT_OFF)
        conf = t.get("confirm", {}).get(name, TOOLS[name][2] == "confirm")
        return bool(on), bool(conf)

    def specs(self):
        """Описания включённых инструментов для модели: [{name, description, parameters}]."""
        out = [{"name": n, "description": d, "parameters": p} for n, (d, p, *_rest) in TOOLS.items()
               if self.policy(n)[0]]
        kids = self.hooks.get("kids")
        if kids is not None and kids.on():
            return out                          # детский режим: ни навыков, ни подключённых MCP — только KIDS_TOOLS
        if self.skills and self.skills.enabled():
            out += [{"name": n, "description": d, "parameters": p} for n, (d, p) in SKILL_TOOLS.items()]
        if self.mcp:
            out += self.mcp.specs()
        return out

    def off_note(self):
        """Что человек сам выключил в студии («Руки» → «Умения») — чтобы модель не говорила «не умею» (№144, 20.10:
        «открой сайт» — «я не могу открывать сайты», а открытие сайтов было выключено переключателем)."""
        en = (self.s.get("tools") or {}).get("enabled") or {}
        off = [n for n, v in en.items() if v is False and n in TOOLS]
        pv = self.s.get("privacy") or {}
        out = ""
        if off:
            names = "; ".join(f"{n} — «{TOOLS[n][4]}»" for n in sorted(off))
            out += ("\n\nВыключено пользователем в студии («Руки» → «Умения»; камера и экран — ещё и в «Безопасности»): " + names
                    + ". Просят это — не говори «не умею»: скажи одной фразой, что это умение выключено в настройках, и где его включить.")
        if pv.get("files") == "folder":
            out += ("\n\nВ «Безопасности» стоит замок «Файлы: только папка Dewiar»: команды терминала выключены, удалять и отправлять "
                    "можно только файлы из папки ассистента. Просят другое — скажи об этом одной фразой и где снять замок.")
        if pv.get("local_only"):
            out += ("\n\nВключён стоп-кран «Ничего не уходит в интернет» (студия → «Безопасность»): поиск, погода, сайты, почта, "
                    "Telegram, «Близкие» и облако сейчас недоступны — соединение наружу не откроется. Просят такое — не пробуй, "
                    "скажи одной фразой, что включён этот режим и где его выключить. Всё, что на этом компьютере, — работает.")
        return out

    def title(self, name):
        if name in TOOLS:
            return TOOLS[name][4]
        if name in SKILL_TOOLS:
            return "Навык"
        if self.mcp and self.mcp.has(name):
            return self.mcp.title(name)
        return name

    def _needs(self, name):
        """Чего не хватает инструменту (№264, 25.10: «включаю — пишет „Сохранено“, а переключатель не включается»: почта,
        Telegram, «Знания», аккаунт не подключены). -> (что сделать, раздел студии) или None."""
        h = self.hooks
        if name in ("send_email", "read_emails", "read_email", "mailing", "mailing_status") and not (h.get("mail") and h["mail"].configured()):
            return "Сначала подключите почту — «Подключение» → «Почта»", "connect"
        if name == "send_telegram" and not (h.get("telegram") and h["telegram"].paired()):
            return "Сначала подключите Telegram или MAX — «Подключение»", "connect"
        if name == "smart_home" and not (h.get("home") and h["home"].connected()):
            return "Сначала подключите умный дом (Яндекс или Home Assistant) — «Подключение»", "connect"
        if name == "server_run" and not (h.get("servers") and h["servers"].items):
            return "Сначала добавьте сервер — «Серверы»", "servers"
        if name == "search_documents" and not (h.get("knowledge") and h["knowledge"].has_files()):
            return "Сначала добавьте документы в «Знания» — «Обо мне» → «Мои документы»", "me"
        if name == "ask_knowledge" and not (h.get("account") and h["account"].logged_in()):
            return "Нужен вход аккаунтом dewiar.pro — «Dewiar.pro»", "dw"
        if name in NET_TOOLS and (self.s.get("privacy") or {}).get("local_only"):
            return "Включён стоп-кран «Ничего не уходит в интернет» — «Безопасность»", "safety"
        if name == "run_command" and (self.s.get("privacy") or {}).get("files") == "folder":
            return "Стоит замок «Файлы: только папка Dewiar» — «Безопасность»", "safety"
        return None

    def catalog(self):
        """Список инструментов для студии (включён, нужно ли подтверждение)."""
        en = ((self.s.get("tools") or {}).get("enabled") or {}) if getattr(self, "s", None) is not None else {}
        out = []
        for n, v in TOOLS.items():
            on, conf = self.policy(n)
            want = en.get(n, n not in DEFAULT_OFF)
            # почему выключено: user — сами в студии; service — служба не подключена или замок/стоп-кран
            off_by = "" if on else ("user" if not want else "service")
            need = self._needs(n) if not on else None
            if need and off_by == "user":                  # выключили сами, а служба и так не подключена — скажем и это
                off_by = "service"
            out.append({"name": n, "title": v[4], "description": v[0], "risk": v[2], "enabled": on, "confirm": conf,
                        "off_by": off_by, "core": n in SAFE_CORE, "needs": need[0] if need else "", "page": need[1] if need else ""})
        return out

    def guard(self, name, args):
        """Защита до вопроса «Выполнить?»: -> (причина запрета | None, подтверждение обязательно, текст вопроса | None).
        Опасное подтверждается, даже если в настройках подтверждение для инструмента выключено."""
        import guard
        s = getattr(self, "s", None)
        if name in ("delete_files", "close_send") and s is not None and (s.get("privacy") or {}).get("files") == "folder":
            # замок «Файлы: только папка Dewiar»: удалять и отправлять можно только то, что лежит в папке ассистента
            roots = [Path(w).expanduser().resolve() for w in guard.WORKSPACE]
            key = "paths" if name == "delete_files" else "files"
            for x in (args or {}).get(key) or []:
                fp = Path(str(x)).expanduser().resolve()
                if not any(fp == r or r in fp.parents for r in roots):
                    return (f"«{fp.name}» — вне папки ассистента, а в «Безопасности» стоит замок «Файлы: только папка Dewiar». "
                            "Снять его можно там же"), False, None
        if name == "run_command":
            v = guard.check_command(str((args or {}).get("command") or ""))
            if v["level"] == "block":
                return v["reason"], False, None
            if v["level"] == "warn":
                return None, True, f"{guard.describe_warn(v)} Выполнить: {args.get('command', '')}?"
        if name == "server_run":
            from servers import check as remote_check
            v = remote_check(str((args or {}).get("command") or ""))
            if v["level"] == "block":
                return v["reason"] + " (на сервере)", False, None
            if v["level"] == "warn":
                return None, True, f"Осторожно: {v['reason']}. На сервере «{args.get('server', '')}» выполнить: {args.get('command', '')}?"
        if name == "delete_files":
            try:
                plan = guard.plan_delete([str(x) for x in ((args or {}).get("paths") or []) if str(x).strip()])
            except guard.Blocked as e:
                return str(e), False, None
            return None, True, guard.describe_delete(plan)
        if name == "close_send" and (args or {}).get("files"):
            # файлы уходят другому человеку — только с подтверждением; ключи и пароли не уходят вовсе
            # (просьбу «отправь…» могла подсунуть страница или чужое сообщение)
            from settings import CONFIG_DIR
            names = []
            for x in (args or {}).get("files") or []:
                fp = Path(str(x)).expanduser().resolve()
                secret = re.search(r"(^|[\\/])(\.ssh|\.gnupg|\.password-store|keyrings?)([\\/]|$)", str(fp), re.I) \
                    or re.search(r"(^\.env(\..*)?$|^id_[a-z0-9]+$|\.(pem|key|jks|keystore|p12|pfx|kdbx)$|^provision.*\.json$)", fp.name, re.I) \
                    or Path(CONFIG_DIR).resolve() in fp.parents
                if secret:
                    return f"«{fp.name}» похож на ключ или пароль — такие файлы не отправляю", False, None
                names.append(fp.name)
            return None, True, f"Отправить {args.get('to', '')}: {', '.join(names)}?"
        if name == "lab_run" and self.hooks.get("workspace"):
            try:
                p = self.hooks["workspace"].safe(str(Path("Лаборатория") / str((args or {}).get("name") or "").lstrip("/")))
                if p.is_file() and p.suffix.lower() in (".sh", ".ps1", ".bat", ".cmd"):
                    v = guard.check_command(p.read_text(encoding="utf-8", errors="replace"), cwd=str(p.parent))
                    if v["level"] == "block":
                        return v["reason"], False, None
                    if v["level"] == "warn":
                        return None, True, f"{guard.describe_warn(v)} Запустить {p.name}?"
            except Exception:  # noqa: BLE001 — не прочитали скрипт: остаётся обычное подтверждение lab_run
                pass
        return None, False, None

    def auto_ok(self, name, args):
        """Можно без вопроса: для сервера выбрано «спрашивать только изменения» (ask="changes"), а команда только читает."""
        if name != "server_run":
            return False
        sv = self.hooks.get("servers")
        s = sv.find(str((args or {}).get("server") or "")) if sv else None
        if not s or s.get("ask") != "changes":
            return False
        from servers import check as remote_check
        v = remote_check(str((args or {}).get("command") or ""))
        return v["level"] == "ok" and v["readonly"]

    def server_readonly(self, args):
        """Команда на сервере только смотрит (servers.check: ok и readonly) — её можно разрешить «всегда»."""
        try:
            from servers import check as remote_check
            v = remote_check(str((args or {}).get("command") or ""))
            return v["level"] == "ok" and bool(v["readonly"])
        except Exception:  # noqa: BLE001
            return False

    def describe(self, name, args):
        """Как спросить подтверждение по-человечески."""
        if name == "power":
            return {"shutdown": "Выключить компьютер", "reboot": "Перезагрузить компьютер", "sleep": "Перевести компьютер в сон",
                    "lock": "Заблокировать экран", "logout": "Выйти из системы", "cancel": "Отменить выключение"}.get(
                args.get("action"), "Питание компьютера") + "?"
        if name == "run_command":
            return f"Выполнить команду: {args.get('command', '')}?"
        if name == "server_run":
            return f"На сервере «{args.get('server', '')}» выполнить: {args.get('command', '')}?"
        if name == "look_through_camera":
            return "Включить камеру и сделать кадр?"
        if name == "create_skill":
            return f"Создать навык «{args.get('name', '')}»: {args.get('description', '')}?"
        if name == "lab_run":
            return f"Запустить в лаборатории {args.get('name', '')}?"
        if name == "channel_post":
            P = self.hooks.get("pbot_posts")
            try:
                where = ", ".join(c["title"] for c in P.chats() if c["id"] in _post_target(P, args.get("chat") or ""))
            except Exception:  # noqa: BLE001
                where = args.get("chat") or "канал"
            what = (f"опрос «{args.get('poll_question')}»" if args.get("poll_question") else f"«{(args.get('text') or '')[:160]}" + ("…»" if len(args.get("text") or "") > 160 else "»"))
            return f"Опубликовать в «{where}» {('— ' + args['when']) if args.get('when') else 'сейчас'}: {what}?"
        if name == "mailing":
            try:
                rs, _ = self.hooks["mailing"].recipients(args.get("recipients") or "list", args.get("list") or "", args.get("tag") or "")
                n = len(rs)
            except Exception:  # noqa: BLE001
                n = 0
            who = {"clients": "клиентам", "team": "сотрудникам"}.get(args.get("recipients") or "", "по списку")
            return (f"Разослать письмо «{args.get('subject', '')}» — {n} {who}, каждому своё" +
                    (" (реклама: со строкой «отписаться»)" if args.get("kind") == "ads" else "") + "?")
        if name == "send_email":
            to = args.get("to") or "вам самим"
            att = args.get("attachments") or []
            return f"Отправить письмо «{args.get('subject', '')}» → {to}" + (f" с вложениями ({len(att)})" if att else "") + "?"
        return f"Выполнить действие «{self.title(name)}»?"

    def run(self, name, args):
        """Выполнить инструмент -> текст или {"text", "image"}. Ошибки (ToolError и др.) ловит вызывающий."""
        if not self.policy(name)[0]:
            raise ToolError(f"инструмент {name} выключен или неизвестен")
        if name == "use_skill":
            return self.skills.use(str(args.get("name", "")))
        if name == "read_skill_file":
            return self.skills.read_file(str(args.get("name", "")), str(args.get("path", "")))
        if self.mcp and self.mcp.has(name):
            return self.mcp.call(name, args or {})
        # _truncated — служебная пометка llm.py об оборванном ответе, обработчикам не нужна
        args = {k: v for k, v in coerce_args(TOOLS[name][1], args).items() if not k.startswith("_trunc")}
        return TOOLS[name][3](args or {}, {"settings": self.s, "reminders": self.reminders, "skills": self.skills, **self.hooks})


def coerce_args(schema, args):
    """Модели нередко присылают вместо строки список или объект, вместо числа — строку («5»), вместо true — «да».
    Приводим к схеме инструмента, а не падаем с «'list' object has no attribute 'strip'»."""
    if not isinstance(args, dict):
        return {"text": str(args)} if args else {}
    props = (schema or {}).get("properties") or {}
    out = dict(args)
    # нужное поле названо иначе ({"q": …} вместо {"query": …}) — единственный чужой ключ отдаём недостающему полю
    missing = [k for k in (schema or {}).get("required") or [] if k not in out]
    unknown = [k for k in out if k not in props and not k.startswith("_")]
    if props and len(missing) == 1 and len(unknown) == 1:
        out[missing[0]] = out.pop(unknown[0])
    args = dict(out)
    for k, v in args.items():
        want = (props.get(k) or {}).get("type")
        if want == "string" or (want is None and isinstance(v, list) and k in ("plan", "summary", "content", "text", "fact", "question", "reason", "query")):
            if isinstance(v, list):
                items = [x if isinstance(x, str) else json.dumps(x, ensure_ascii=False) for x in v]
                if k == "plan":
                    items = [x if re.match(r"^\s*([-*]\s*\[|#)", x) else f"- [ ] {x.lstrip('-* ').strip()}" for x in items]
                out[k] = "\n".join(items) if k in ("plan", "content", "text", "summary") else " ".join(items)
            elif isinstance(v, dict):
                out[k] = json.dumps(v, ensure_ascii=False, indent=1)
            elif v is None:
                out[k] = ""
            elif not isinstance(v, str):
                out[k] = str(v).lower() if isinstance(v, bool) else str(v)
        elif want in ("integer", "number") and isinstance(v, str):
            try:
                out[k] = int(float(v.replace(",", "."))) if want == "integer" else float(v.replace(",", "."))
            except ValueError:
                out.pop(k)
        elif want == "boolean" and isinstance(v, str):
            out[k] = v.strip().lower() in ("true", "1", "да", "yes")
    return out


def say_command(cmd):
    """Команда списком -> строка для показа человеку (с кавычками shell)."""
    return " ".join(shlex.quote(c) for c in cmd)
