"""Картинки к рассказу (просьба 14.10: «Лира рассказывает про руническую вязь — пусть показывает изображения, о которых
говорит»). Ищем как обычный поисковик картинок — так находится что угодно, от рун до новой модели телефона:
  1. свой SearXNG, если задан (Настройки → tools.search_url; categories=images);
  2. DuckDuckGo Картинки (тот же поисковик, что у web_search; безопасный поиск включён);
  3. то же через сервер Dewiar (?p=/images), если поисковик из сети пользователя не открывается;
  4. Wikimedia Commons — запасной путь: свободные изображения с автором и лицензией.
Миниатюры поисковика идут с его же прокси (их можно показывать), крупно — оригинал с сайта, не открылся — миниатюра.
Адреса подменяются переменными DEWIAR_DDG_URL и DEWIAR_COMMONS_API (тесты, зеркала)."""
import html
import logging
import os
import re
import urllib.parse

import httpx

log = logging.getLogger("dewiar.images")
API = os.environ.get("DEWIAR_COMMONS_API") or "https://commons.wikimedia.org/w/api.php"
DDG = (os.environ.get("DEWIAR_DDG_URL") or "https://duckduckgo.com").rstrip("/")
UA = {"User-Agent": "Dewiar/0.38 (voice assistant; https://dewiar.pro)"}
BROWSER = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
           "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.6"}
SKIP = re.compile(r"\b(?:logo|icon|flag of|coat of arms|map of|locator|signature|svg)\b", re.I)


def _clean(v):
    v = html.unescape(re.sub(r"<[^>]+>", " ", str(v or "")))
    return re.sub(r"\s+", " ", v).strip()


def _site(url):
    try:
        h = urllib.parse.urlparse(url).hostname or ""
    except ValueError:
        return ""
    return h[4:] if h.startswith("www.") else h


def _web_item(src, full, page, title, w=0):
    title = _clean(title)[:120]
    return {"src": src, "full": full or src, "page": page or full or src, "title": title or _site(page) or "картинка",
            "desc": "", "author": "", "license": "", "site": _site(page or full), "source": "web", "width": w}


def ddg(query, n=4):
    """DuckDuckGo Картинки: страница поиска даёт ключ vqd, по нему — i.js (JSON). -> [items]."""
    with httpx.Client(headers=BROWSER, timeout=12, follow_redirects=True) as c:
        r = c.get(DDG + "/", params={"q": query, "iax": "images", "ia": "images", "kp": "1"})
        r.raise_for_status()
        m = re.search(r"""vqd=["']?([\d-]+)""", r.text)
        if not m:
            raise httpx.HTTPError("поисковик картинок не дал ключ (капча?)")
        r = c.get(DDG + "/i.js", params={"l": "ru-ru", "o": "json", "q": query, "vqd": m.group(1), "f": ",,,,,", "p": "1"},
                  headers={"Referer": DDG + "/", "Accept": "application/json"})
        r.raise_for_status()
        res = r.json().get("results") or []
    out = []
    for x in res:
        src, full = x.get("thumbnail") or "", x.get("image") or ""
        if not src or (x.get("width") or 999) < 200 or full.lower().endswith(".svg") or SKIP.search(x.get("title") or ""):
            continue
        out.append(_web_item(src, full, x.get("url") or "", x.get("title") or "", x.get("width") or 0))
        if len(out) >= n:
            break
    return out


def searx(base, query, n=4):
    """Свой SearXNG: /search?format=json&categories=images. -> [items]."""
    r = httpx.get(base.rstrip("/") + "/search", params={"q": query, "format": "json", "categories": "images",
                                                       "safesearch": 2, "language": "ru"}, headers=UA, timeout=12)
    r.raise_for_status()
    out = []
    for x in r.json().get("results") or []:
        full = x.get("img_src") or ""
        src = x.get("thumbnail_src") or full
        if not src or full.lower().endswith(".svg") or SKIP.search(x.get("title") or ""):
            continue
        out.append(_web_item(urllib.parse.urljoin(base, src), full, x.get("url") or "", x.get("title") or ""))
        if len(out) >= n:
            break
    return out


def commons(query, n=4, width=480):
    """Wikimedia Commons -> [{src, full, page, title, desc, author, license, source: "commons"}]."""
    q = (query or "").strip()
    params = {"action": "query", "format": "json", "generator": "search", "gsrnamespace": 6, "gsrlimit": 16,
              "gsrsearch": f"{q} filetype:bitmap", "prop": "imageinfo", "iiprop": "url|extmetadata|mime|size",
              "iiurlwidth": width, "iiextmetadatafilter": "ObjectName|ImageDescription|Artist|LicenseShortName",
              "iiextmetadatalanguage": "ru"}
    r = httpx.get(API, params=params, headers=UA, timeout=12, follow_redirects=True)
    r.raise_for_status()
    pages = sorted(((r.json().get("query") or {}).get("pages") or {}).values(), key=lambda p: p.get("index", 0))
    out = []
    for p in pages:
        ii = (p.get("imageinfo") or [{}])[0]
        if not ii.get("thumburl") or not str(ii.get("mime", "")).startswith("image/") or ii.get("mime") == "image/svg+xml":
            continue
        if (ii.get("width") or 0) < 200:
            continue
        meta = ii.get("extmetadata") or {}
        name = re.sub(r"^File:|\.[a-z0-9]+$", "", p.get("title", ""), flags=re.I).replace("_", " ")
        title = _clean((meta.get("ObjectName") or {}).get("value")) or name
        if SKIP.search(name):
            continue
        thumb = ii["thumburl"]
        out.append({"src": thumb, "full": re.sub(r"/\d+px-", "/1280px-", thumb) if (ii.get("width") or 0) > 1280 else ii.get("url", thumb),
                    "page": ii.get("descriptionurl", ""), "title": title[:120],
                    "desc": _clean((meta.get("ImageDescription") or {}).get("value"))[:200],
                    "author": _clean((meta.get("Artist") or {}).get("value"))[:80],
                    "license": _clean((meta.get("LicenseShortName") or {}).get("value"))[:40],
                    "site": "commons.wikimedia.org", "source": "commons"})
        if len(out) >= n:
            break
    return out


def search(query, n=4, searx_url="", via=None):
    """Картинки по запросу: SearXNG → DuckDuckGo → сервер Dewiar → Commons; первый, кто нашёл. -> [items]
    (ошибки путей — в журнал; не ответил никто — последняя ошибка)."""
    q = (query or "").strip()
    if not q:
        return []
    ways = ([("SearXNG", lambda: searx(searx_url, q, n))] if searx_url else []) + [("DuckDuckGo", lambda: ddg(q, n))]
    if via:
        ways.append(("сервер Dewiar", lambda: [_web_item(x.get("src", ""), x.get("full", ""), x.get("page", ""), x.get("title", ""))
                                              for x in via("images", q) if x.get("src")][:n]))
    ways.append(("Wikimedia Commons", lambda: commons(q, n)))
    err, answered = None, False
    for name, fn in ways:
        try:
            items = fn()
        except Exception as e:  # noqa: BLE001 — любой путь может не ответить: пробуем следующий
            log.info("Картинки: %s не ответил (%s)", name, e)
            err = e
            continue
        answered = True
        if items:
            log.info("🖼 Картинки «%s»: %s — %d", q[:60], name, len(items))
            return items
    if answered or err is None:
        return []                                    # кто-то ответил, но ничего не нашёл
    raise err if isinstance(err, httpx.HTTPError) else httpx.HTTPError(str(err))


def relevant(items, query):
    """Картинки, в подписи которых есть слово запроса (по основе: «runestone» → «runest», «вязь» → «вязь»)."""
    stems = {w.lower()[:max(4, min(6, len(w) - 2))] for w in re.findall(r"[\w-]{4,}", query or "")}
    return [x for x in items or [] if any(st in f"{x.get('title', '')} {x.get('desc', '')}".lower() for st in stems)] if stems else list(items or [])


def credit(items):
    """Подпись для модели и ленты: откуда картинки."""
    if items and all(x.get("source") == "commons" for x in items):
        return "Wikimedia Commons"
    sites = [s for s in dict.fromkeys(x.get("site") for x in items) if s]
    return "поиск картинок" + (f" (сайты: {', '.join(sites[:4])})" if sites else "")
