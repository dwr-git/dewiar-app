"""«Сайты» — основа (чистое ядро 1.0.18 — docs/CORE_PLAN.md): шаблоны и стили, имена и адреса, быстрые операции
без модели, проверка адреса (reach), фото по ссылке (fetch_image). Работа с сайтами — core/sites.py (Sites), части —
sites_make, sites_edit, sites_out; прежние имена sites.X на месте. Подменять в проверках — здесь (sites_base.reach…)."""
import json
import logging
import re
import secrets
import time
from pathlib import Path

import sites_kit as K

def fetch_image(url, timeout=20.0, limit=25 * 1024 * 1024):
    """Картинка по ссылке -> байты (только http(s), не больше 25 МБ, тип image/*)."""
    import httpx
    u = str(url or "").strip()
    if not re.match(r"^https?://[^/\s]+", u, re.I):
        raise SiteError("нужна ссылка на картинку (https://…)")
    try:
        with httpx.stream("GET", u, timeout=timeout, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0 Dewiar"}) as r:
            r.raise_for_status()
            if not r.headers.get("content-type", "").lower().startswith("image/"):
                raise SiteError("по ссылке не картинка")
            buf = b""
            for ch in r.iter_bytes():
                buf += ch
                if len(buf) > limit:
                    raise SiteError("картинка больше 25 МБ")
            return buf
    except httpx.HTTPError as e:
        raise SiteError(f"картинка не скачалась: {e}") from e


def page_media(base, page, images=12, videos=4):
    """Фото и видео страницы (15.11: «сделай сайт по моей странице, возьми фото и видео с сайта»): большие картинки
    (без значков, логотипов и svg), ролики (YouTube, Rutube, VK, .mp4 — из <video>, <iframe>, ссылок). -> {images, videos}."""
    from urllib.parse import urljoin
    import sites_render as SR
    imgs, vids = [], []
    for m in re.finditer(r"(?is)<img\b[^>]*>", page):
        tag = m.group(0)
        src = (re.search(r"(?i)\b(?:data-src|data-lazy-src|src)\s*=\s*[\"']([^\"']+)", tag) or [None, ""])[1]
        w = int((re.search(r"(?i)\bwidth\s*=\s*[\"']?(\d+)", tag) or [None, "999"])[1])
        if not src or src.startswith("data:") or w < 200 or re.search(r"(?i)logo|icon|avatar|sprite|pixel|\.svg(?:\?|$)|gravatar", src):
            continue
        u = urljoin(base, src.strip())
        if re.match(r"^https?://", u) and u not in imgs:
            imgs.append(u)
    for u in re.findall(r"(?i)(?:src|href|content)\s*=\s*[\"']([^\"']+)", page):
        u = urljoin(base, u.strip())
        if SR.video_embed(u)[0] and u not in vids:
            vids.append(u)
    og = re.search(r"(?is)<meta[^>]+property=[\"']og:image[\"'][^>]+content=[\"']([^\"']+)", page)
    if og:
        u = urljoin(base, og.group(1))
        imgs = [u] + [x for x in imgs if x != u]
    return {"images": imgs[:images], "videos": vids[:videos]}


def ref_outline(url, timeout=12.0, media=None):
    """№552 (05.11: «в „Сайтах“ — поле для ссылки на сайт-референс, по которому создать свой»): схема чужой страницы без
    её текстов — заголовок, разделы (h1–h3), меню, кнопки, основные цвета. -> строка до ~1500 знаков; не открылась — SiteError."""
    import html as _h
    import httpx
    u = url if re.match(r"^https?://", url, re.I) else "https://" + url
    if not re.match(r"^https?://[^/\s]+\.[^/\s]+", u):
        raise SiteError("это не похоже на адрес сайта")
    try:
        r = httpx.get(u, timeout=timeout, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0 Dewiar"})
        r.raise_for_status()
    except httpx.HTTPError as e:
        raise SiteError(f"сайт-образец не открылся: {e}") from e
    page = r.text[:600_000]
    if media is not None:
        media.update(page_media(str(r.url), page))
    page = re.sub(r"(?is)<(script|style|noscript|svg)\b.*?</\1>", " ", page)
    txt = lambda x: re.sub(r"\s+", " ", _h.unescape(re.sub(r"<[^>]+>", " ", x))).strip()   # noqa: E731
    title = txt((re.search(r"(?is)<title[^>]*>(.*?)</title>", page) or [None, ""])[1])[:120]
    heads = [f"{m.group(1).upper()}: {txt(m.group(2))[:90]}" for m in re.finditer(r"(?is)<(h[1-3])[^>]*>(.*?)</\1>", page) if txt(m.group(2))][:24]
    nav = [txt(x)[:30] for x in re.findall(r"(?is)<nav\b.*?</nav>", page)[:1] for x in re.findall(r"(?is)<a\b[^>]*>(.*?)</a>", x) if txt(x)][:12]
    btns = list(dict.fromkeys(txt(x)[:30] for x in re.findall(r"(?is)<button\b[^>]*>(.*?)</button>", page) if txt(x)))[:8]
    colors = [c for c, _ in __import__("collections").Counter(x.lower() for x in re.findall(r"#[0-9a-fA-F]{6}\b", r.text[:600_000])).most_common(5)]
    out = [f"Адрес: {u}", f"Заголовок страницы: {title}" if title else "", "Разделы по порядку: " + " · ".join(heads) if heads else "",
           "Меню: " + ", ".join(nav) if nav else "", "Кнопки: " + ", ".join(btns) if btns else "", "Основные цвета: " + ", ".join(colors) if colors else ""]
    res = "\n".join(x for x in out if x)[:1500]
    if not heads and not title:
        raise SiteError("на странице-образце не нашлось ни заголовков, ни разделов")
    return res


EMBED_RX = re.compile(r"(?is)<\s*(?:iframe|video|source|embed|object)\b[^>]*>|<\s*/\s*(?:iframe|video|object)\s*>")
URL_RX = re.compile(r"https?://[^\s\"'<>]+", re.I)


def code_to_video(s):
    """15.11 (люди: «отдал Лире код видео — он просто показан на сайте текстом»): код встраивания (<iframe>, <video>) в
    текстовых полях не показываем никогда. Ролик из него (YouTube, Rutube, VK, .mp4) — разделом «Видео»: текстовый раздел, где
    был только код, сам становится «Видео»; иначе «Видео» встаёт сразу после него. -> сколько роликов нашлось."""
    found = 0
    for pg in s.get("pages") or []:
        out = []
        for b in pg.get("blocks") or []:
            vids = []
            for x in [b] + [i for i in b.get("items") or [] if isinstance(i, dict)]:
                for k, v in list(x.items()):
                    if not isinstance(v, str) or not EMBED_RX.search(v):
                        continue
                    us = [u.rstrip(").,;") for u in URL_RX.findall(v) if R.video_embed(u.rstrip(").,;"))[0]]
                    if b.get("type") == "video" and k == "url" and x is not b:
                        x[k] = us[0] if us else ""         # код вставили в поле ссылки — оставляем саму ссылку
                        continue
                    vids += us
                    x[k] = re.sub(r"[ \t]+", " ", re.sub(r"(?is)<[^>]+>", " ", v)).strip()
                    x[k] = "\n".join(ln.strip() for ln in x[k].splitlines() if ln.strip() and not URL_RX.fullmatch(ln.strip()))
            vids = list(dict.fromkeys(u.rstrip(").,;") for u in vids))
            found += len(vids)
            if vids and b.get("type") == "video":
                b.setdefault("items", []).extend({"url": u, "caption": ""} for u in vids)
                out.append(b)
            elif vids and b.get("type") == "text" and not str(b.get("text") or "").strip():
                b.update(type="video", variant="one", items=[{"url": u, "caption": ""} for u in vids])
                b.pop("text", None)
                out.append(b)
            else:
                out.append(b)
                if vids:
                    out.append({"type": "video", "variant": "one", "tone": b.get("tone", "base"), "title": "Видео", "uid": _uid(),
                                "items": [{"url": u, "caption": ""} for u in vids]})
        pg["blocks"] = out
    return found


# «…и добавь с сайта фото и видео», «возьми картинки с моей страницы» — взять медиа со страницы-образца (она его)
TAKE_MEDIA_RX = re.compile(r"(?:фото|картин|изображ|снимк|видео|ролик)[^.!?]{0,60}(?:с\s+(?:мо(?:его|ей)\s+)?(?:сайт|страниц|образц)|оттуда)|"
                           r"(?:с\s+(?:мо(?:его|ей)\s+)?(?:сайт|страниц|образц)\w*|оттуда)[^.!?]{0,60}(?:фото|картин|изображ|снимк|видео|ролик)", re.I)


REACH_SAY = ("Сайт сохранён на dewiar.pro. Адрес {url} заработает, когда сервер сайтов будет настроен — администратор об этом знает; "
             "я проверю сам и скажу, когда откроется.")


def reach(url, timeout=8.0):
    """№549 (04.11: «Опубликовать» — пустая страница, адрес не открывается: DNS_PROBE_FINISHED_NXDOMAIN): открывается ли сайт по
    своему адресу -> {ok, why: "" | dns | cert | server | net, at}. Не открывается — не показываем пустую страницу, а говорим как есть."""
    import httpx
    why = ""
    try:
        r = httpx.get(url, timeout=timeout, follow_redirects=True)
        if r.status_code >= 400:
            why = "server"
    except httpx.ConnectError as e:
        t = str(e).lower()
        why = ("dns" if re.search(r"getaddrinfo|name or service|nodename|11001|no address|name resolution|not known|temporary failure in name", t)
               else "cert" if "certificate" in t or "ssl" in t else "net")
    except httpx.HTTPError as e:
        why = "cert" if "certificate" in str(e).lower() or "ssl" in str(e).lower() else "net"
    return {"ok": not why, "why": why, "at": int(time.time())}
import sites_render as R

log = logging.getLogger("dewiar.sites")
FONTS_DIR = Path(__file__).resolve().parent.parent / "ui" / "assets" / "fonts"
HISTORY_MAX = 60
NAME_RX = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,28})[a-z0-9]$")
RESERVED = {"www", "api", "admin", "mail", "dwrapp", "app", "cloud", "pro", "dewiar", "support", "help", "static", "cdn", "ftp",
            "smtp", "imap", "pop", "ns1", "ns2", "dashboard", "login", "account", "billing", "pay", "test", "dev", "stage", "blog",
            "shop", "news", "status", "docs", "id", "auth", "oauth", "voice", "voices", "web", "lira", "academy", "abuse", "security"}
TEXT_MAX = {"title": 200, "text": 3000, "note": 200, "button": 60, "button2": 60, "nav": 40, "caption": 200, "price": 60, "q": 300,
            "a": 2000, "name": 120, "role": 160, "time": 60, "group": 80, "href": 500, "thanks": 200}


class SiteError(Exception):
    pass


def _now():
    return int(time.time())


def _uid():
    return secrets.token_hex(3)


def translit(s):
    tr = dict(zip("абвгдеёжзийклмнопрстуфхцчшщъыьэюя", ["a", "b", "v", "g", "d", "e", "e", "zh", "z", "i", "y", "k", "l", "m", "n", "o", "p",
                                                       "r", "s", "t", "u", "f", "h", "ts", "ch", "sh", "sch", "", "y", "", "e", "yu", "ya"]))
    out = "".join(tr.get(c, c) for c in str(s or "").lower())
    out = re.sub(r"[^a-z0-9]+", "-", out).strip("-")
    return out[:30].strip("-")


def name_problem(name):
    """Имя поддомена: латиница, цифры, дефис, 3–30 знаков. -> текст ошибки или ""."""
    n = str(name or "").strip().lower()
    if not NAME_RX.match(n):
        return "имя — латиница, цифры и дефис, от 3 до 30 знаков, не начинается и не кончается дефисом"
    if "--" in n:
        return "два дефиса подряд нельзя"
    if n in RESERVED:
        return "это имя занято под службы Dewiar — выберите другое"
    return ""


def _clip(k, v):
    if isinstance(v, bool) or v is None:
        return v
    if isinstance(v, (int, float)):
        return v
    s = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(v))
    return s[:TEXT_MAX.get(k, 1000)]


def clean_fields(d, kind="block"):
    """Поля блока или карточки от модели или из студии: только строки разумной длины, флаги, без служебного."""
    out = {}
    for k, v in (d or {}).items():
        if not isinstance(k, str) or k.startswith("_") or k in ("uid", "type"):
            continue
        if k == "items" and kind == "block":
            if isinstance(v, list):
                out["items"] = [clean_fields(x, "item") for x in v[:40] if isinstance(x, dict)]
            continue
        if isinstance(v, (dict, list)):
            continue
        out[k] = _clip(k, v)
    return out


# ---------- SVG логотипа из «Художника» ----------

SVG_TAGS = {"svg", "g", "path", "circle", "ellipse", "rect", "line", "polyline", "polygon", "defs", "lineargradient", "radialgradient", "stop",
            "text", "tspan", "title", "clippath", "mask", "use", "symbol", "pattern"}
SVG_ATTRS = re.compile(r"^(?:d|x|y|x1|x2|y1|y2|cx|cy|r|rx|ry|width|height|viewbox|points|fill|stroke|stroke-width|stroke-linecap|stroke-linejoin|"
                       r"stroke-dasharray|stroke-opacity|fill-opacity|opacity|transform|offset|stop-color|stop-opacity|gradientunits|gradienttransform|"
                       r"font-size|font-weight|font-family|text-anchor|dominant-baseline|letter-spacing|id|clip-path|mask|fill-rule|clip-rule|"
                       r"preserveaspectratio|href|xmlns|xmlns:xlink|xlink:href|patternunits|fx|fy|dx|dy|class|style)$")


def clean_svg(src, size=96):
    """Свой знак из «Художника»: только рисующие теги и атрибуты, ссылки — только внутренние (#…), без стилей с url()."""
    import xml.etree.ElementTree as ET
    s = str(src or "")
    i = s.find("<svg")
    if i < 0:
        raise SiteError("это не SVG")
    s = s[i:s.rfind("</svg>") + 6]
    try:
        root = ET.fromstring(s)
    except ET.ParseError as e:
        raise SiteError(f"SVG не читается: {e}") from e
    for parent in list(root.iter()):
        for ch in list(parent):
            tag = ch.tag.split("}")[-1].lower() if isinstance(ch.tag, str) else ""
            if tag not in SVG_TAGS:
                parent.remove(ch)
    for el in root.iter():
        for k in list(el.attrib):
            kl = k.split("}")[-1].lower()
            v = el.attrib[k]
            full = ("xlink:" if "xlink" in k else "") + kl
            if not SVG_ATTRS.match(full) and not SVG_ATTRS.match(kl):
                del el.attrib[k]
            elif kl == "href" and not v.startswith("#"):
                del el.attrib[k]
            elif re.search(r"url\(\s*['\"]?(?!#)|javascript:|expression\(|@import", v, re.I):
                del el.attrib[k]
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    root.attrib["width"], root.attrib["height"] = str(size), str(size)
    out = ET.tostring(root, encoding="unicode")
    out = re.sub(r"\sxmlns:ns\d+=\"[^\"]*\"", "", out)
    if re.search(r"<script|on[a-z]+\s*=|javascript:|foreignObject", out, re.I):
        raise SiteError("в SVG осталось небезопасное")
    return out[:60000]


# ---------- быстрые правила для фраз ----------

PALETTE_WORDS = [("pistachio", r"фисташ|оливков"), ("espresso", r"эспрессо|кофейн\w* цвет|коричнев|шоколад"), ("plum", r"слив|розов|пудров|бордов"),
                 ("navy", r"морск|тёмно-?син|темно-?син|строг\w* син|деловой цвет"), ("ultramarine", r"ультрамарин|ярко-?син|\bсин"),
                 ("tomato", r"томат|красн|оранжев|терракот"), ("graphite", r"графит|чёрн|черн|тёмн\w* (?:тем|фон|сайт)|темн\w* (?:тем|фон|сайт)"),
                 ("mint", r"мят|бирюз|медицин"), ("sun", r"солн|жёлт|желт|ярк\w* жёлт"), ("ice", r"лёд|лед\b|бел\w* (?:фон|сайт)|изумруд|чист"),
                 ("sage", r"шалфе|зелён|зелен|природ|эко"), ("concrete", r"бетон|сер(?:ый|ая|ое|ые)\b"), ("berry", r"ягод|малин|вишн"),
                 ("night", r"ноч|космос")]
# цвета словами — для фона (0.99): «оранжево-красный градиент» -> по порядку слов
COLOR_WORDS = [("#FF7A18", r"оранж"), ("#E52D27", r"красн|алый|алого"), ("#7A1F2B", r"бордов"), ("#FFC93C", r"жёлт|желт"),
               ("#D4A537", r"золот"), ("#2EAD5B", r"зелён|зелен"), ("#9BE3C7", r"мятн"), ("#1FB5A8", r"бирюз"), ("#5BB8F5", r"голуб"),
               ("#2D6BE0", r"\bсин|синего|синий"), ("#14234B", r"тёмно-?син|темно-?син"), ("#7B4BD6", r"фиолет"), ("#B59CE8", r"сирен|лилов"),
               ("#F06BA8", r"розов"), ("#FFB38A", r"персик"), ("#E9DCC6", r"бежев"), ("#6B4226", r"коричнев"), ("#8A8F98", r"сер(?:ый|ого|ым|ая|ой)\b"),
               ("#111318", r"чёрн|черн"), ("#FFFFFF", r"бел(?:ый|ого|ым|ая|ой)\b")]


def _colors_in(tt):
    """Цвета из фразы по порядку: «#ff7a18», «оранжево-красный» -> ["#FF7A18", "#E52D27"]."""
    found = [(m.start(), m.group(0).upper()) for m in re.finditer(r"#[0-9a-fA-F]{6}\b", tt)]
    for hx, rx in COLOR_WORDS:
        m = re.search(rx, tt)
        if m and not (hx == "#2D6BE0" and re.search(r"тёмно-?син|темно-?син", tt)):
            found.append((m.start(), hx))
    out = []
    for _, c in sorted(found):
        if c not in out:
            out.append(c)
    return out


def mix_hex(a, b, t):
    from sites_render import mix
    return mix(a, b, t)


FONT_WORDS = [("strict", r"строг|делов|современ|плотн"), ("warm", r"тёпл|тепл|уютн|засечк"), ("bold", r"смел|ярк\w* шрифт|крупн\w* шрифт|молодёж|молодеж"),
              ("classic", r"классич|солидн|традиц"), ("editorial", r"журнал|элегант|курсив|изящн|нежн"), ("light", r"прост|лёгк|легк|системн|обычн")]
BLOCK_WORDS = [("prices", r"цен|прайс|тариф|стоимост|меню"), ("services", r"услуг"), ("reviews", r"отзыв"), ("faq", r"вопрос|faq|чаво"),
               ("team", r"команд|сотрудник|врач|мастер\w* (?:раздел|блок)|специалист"), ("gallery", r"галере|фото|портфолио|работ\b|работы"),
               ("contacts", r"контакт|карт\w|адрес"), ("lead", r"заявк|форм|запис"), ("features", r"преимущ|почему мы|почему нас"),
               ("steps", r"шаг|как (?:мы )?работа|этап"), ("schedule", r"программ|расписан|агенд"), ("products", r"товар|каталог|витрин"),
               ("links", r"ссылк|соцсет"), ("about", r"о нас|о себе|о компании|обо мне|истори"), ("cta", r"призыв|баннер"), ("text", r"текст")]
BLOCK_WORDS += [("stats", r"цифр|числ|показател|достижени"), ("hub", r"схем|круг\w* с част"), ("duo", r"два пути|двух путей|сравнени\w* (?:с|без)"),
                ("bars", r"полос|сравнени\w* числ|график"), ("cases", r"кейс|проект\w* (?:клиент|выпускник|учени)"),
                ("ticker", r"бегущ|строк\w* слов")]
STYLE_WORDS = [("avangard", r"авангард|avangard"), ("poster", r"афиш|постер"), ("atelier", r"ателье|atelier"), ("classic", r"классич|как было|обычн\w* стил")]
TEMPLATE_WORDS = [(tid, rx) for tid, rx in K.KIND_WORDS]


def _find(rules, text):
    for k, rx in rules:
        if re.search(rx, text):
            return k
    return None


def _simple(rest):
    """Просьба про один раздел без подробностей («добавь отзывы»)? Иначе («добавь цены: стрижка 1500», «вопросы после
    раздела о нас и отзывы») — пусть разберёт модель."""
    rest = rest.strip()
    hits = {k for k, rx in BLOCK_WORDS if re.search(rx, rest)}
    return (len(hits) == 1 and len(rest.split()) <= 5 and not re.search(r"[:\d]|после|перед|вместо|сверху|снизу|\bи\b|в конц|в начал", rest))


def quick_ops(text, site):
    """Простые просьбы без модели -> (ops, что сделала) или (None, "") — тогда модель. «undo» — отдельной операцией."""
    t = " " + str(text or "").lower().replace("ё", "е") + " "
    tt = t.replace("е", "е")
    if re.search(r"верни\w* (?:как было|назад|обратно|прежн)|отмени\w*|откати\w*|как было", tt):
        return [{"op": "undo"}], "Вернула как было."
    ops, said = [], []
    if re.search(r"шапк|хедер|верх\w* (?:сайта|част)", tt):
        if re.search(r"т[её]мн|черн", tt):
            ops.append({"op": "header", "value": "dark"})
            said.append("шапка тёмная")
        elif re.search(r"светл|бел", tt):
            ops.append({"op": "header", "value": "light"})
            said.append("шапка светлая")
        elif re.search(r"акцент|цветн|ярк", tt):
            ops.append({"op": "header", "value": "accent"})
            said.append("шапка цвета акцента")
    if "шрифт" in tt:
        f = _find(FONT_WORDS, tt)
        if f:
            ops.append({"op": "fonts", "name": f})
            said.append(f"шрифт «{K.FONTS[f]['title']}»")
    if re.search(r"угл|скругл", tt):
        r = "sharp" if re.search(r"остр|прям|строг|без скругл", tt) else "round" if re.search(r"кругл|сильн", tt) else "soft"
        ops.append({"op": "radius", "name": r})
        said.append(K.RADII[r]["title"].lower() + " углы" if r != "soft" else "мягкие углы")
    if re.search(r"\bменю\b", tt) and re.search(r"бургер|кнопк|спрят|свер\w+ в|сбоку|слева|боков|по центру|центр|сверху|наверх", tt):
        st = ("burger" if re.search(r"бургер|кнопк|спрят|свер\w+ в", tt) else "side" if re.search(r"сбоку|слева|боков", tt)
              else "center" if re.search(r"центр", tt) else "top")
        ops.append({"op": "menu", "style": st})
        said.append("меню — " + K.MENUS[st].lower())
    bgw = re.search(r"\bфон|градиент", tt) and not re.search(r"шапк|кнопк|раздел\w* с|картинк|фото", tt)
    if bgw:
        cs = _colors_in(tt)
        if re.search(r"убер\w*|убр\w*|как был|обычн\w* фон|без градиент", tt) and not cs:
            ops.append({"op": "background", "colors": []})
            said.append("фон — как в палитре")
        elif cs:
            if re.search(r"градиент|переход|перелив", tt) and len(cs) == 1:
                cs = [cs[0], mix_hex(cs[0], "#000000", .35)]
            ops.append({"op": "background", "colors": cs[:2]})
            said.append("фон " + ("градиентом" if len(cs) > 1 else "одним цветом") + " — под всеми разделами")
    if not bgw and re.search(r"цвет|палитр|гамм|оформлени|тем[аеуы]\b", tt) and not re.search(r"шапк", tt):
        p = _find(PALETTE_WORDS, tt)
        if p:
            ops.append({"op": "palette", "name": p})
            said.append(f"палитра «{K.PALETTES[p]['title']}»")
    sty = _find(STYLE_WORDS, tt) if re.search(r"стил|авангард|ателье|афиш", tt) else None
    if sty and not re.search(r"шрифт|палитр|цвет", tt):          # 0.94: «сделай в стиле Авангард», «стиль — Ателье»
        ops.append({"op": "style", "value": sty})
        said.append(f"стиль «{K.STYLES[sty]['title']}»")
    if not sty and re.search(r"друг\w+ дизайн|смени\w* дизайн|поменя\w* дизайн|переделай\w* (?:весь )?дизайн|нов\w+ дизайн|в стиле|дизайн как у|как у (?:юрист|кофейн|салон)", tt):
        tid = _find(TEMPLATE_WORDS, re.sub(r".*(?:в стиле|как у|под)\s+", "", tt)) if re.search(r"в стиле|как у|под ", tt) else None
        if not tid or tid == site.get("template"):
            order = [x for x in K.TEMPLATE_ORDER if x != site.get("template")]
            cur = K.TEMPLATE_ORDER.index(site["template"]) if site.get("template") in K.TEMPLATE_ORDER else 0
            tid = order[cur % len(order)]
        ops.append({"op": "template", "id": tid})
        said.append(f"новый дизайн в духе «{K.TEMPLATES[tid]['title']}» (тексты те же)")
    m = re.search(r"(?:добав\w*|встав\w*|сделай|нуж\w+|созда\w*)\s+(?:ещ[её]\s+)?(?:раздел|блок|секци\w*|страниц\w*)?\s*(?:с|про|о|об|для)?\s*(.+)", tt)
    if m and not ops and not _simple(m.group(1)):
        m = None
    if m and not ops:
        bt = _find(BLOCK_WORDS, m.group(1))
        if bt and not re.search(r"сайт\b", m.group(1)[:20]):
            ops.append({"op": "add_block", "type": bt})
            said.append(f"добавила раздел «{K.BLOCKS[bt]['title']}»")
    m = re.search(r"(?:убер\w*|удал\w*|скрой|спрячь|не нуж\w+)\s+(?:раздел|блок|секци\w*)?\s*(?:с|про|о|об)?\s*(.+)", tt)
    if m and not ops and not _simple(m.group(1)):
        m = None
    if m and not ops:
        bt = _find(BLOCK_WORDS, m.group(1))
        if bt:
            ops.append({"op": "remove_block", "block": bt})
            said.append(f"убрала раздел «{K.BLOCKS[bt]['title']}»")
    if not ops:
        return None, ""
    return ops, ("Готово: " + ", ".join(said) + ".") if said else "Готово."


# ---------- модель ----------

OPS_HELP = """Операции (JSON-список ops):
{"op":"palette","name":"<палитра>"} — цвета; палитры: %(pal)s
{"op":"colors","accent":"#rrggbb","bg":"#rrggbb",…} — точечно (ключи: bg, surface, ink, muted, accent, accent_ink, dark, dark_ink, accent2, line)
{"op":"background","colors":["#rrggbb"] или ["#rrggbb","#rrggbb"]} — ФОН САЙТА целиком: один цвет или градиент под всеми разделами (и тёмными); «фон», «цвет фона», «градиент» — это он, а не accent; [] — убрать
{"op":"header","value":"light|dark|accent"} — шапка
{"op":"style","value":"classic|avangard"} — стиль вёрстки: avangard — крупный широкий шрифт, номера разделов, движение (приносит свою палитру и шрифт; "keep":true — оставить свои)
{"op":"fonts","name":"<пара>"} — шрифты: %(fonts)s
{"op":"radius","name":"sharp|soft|round"}
{"op":"menu","style":"top|center|burger|side","cta":"текст кнопки в шапке"}
{"op":"logo","text":"…","mark":"<знак>","style":"badge|plain|mono|text"} — знаки: %(marks)s
{"op":"site","name":"…","tagline":"…","description":"описание для поисковиков 120–160 знаков"}
{"op":"contacts","phone":"…","email":"…","address":"…","hours":"…","telegram":"…","whatsapp":"…","vk":"…"}
{"op":"legal","org":"ИП Иванов Иван Иванович","inn":"…","ogrn":"…","address":"юридический адрес","phone":"…","email":"…","docs":{"oferta":{"mode":"link","url":"https://…"}},"links":[{"title":"Доставка и возврат","url":"https://…"}]} — подвал: реквизиты и документы (oferta, privacy, consent, terms; mode link|text|"" — убрать); только то, что назвал человек
{"op":"template","id":"<шаблон>"} — другой дизайн целиком, тексты остаются: %(tpl)s
{"op":"add_block","type":"<тип>","after":"<uid блока или пусто — в конец, перед заявкой и контактами>","data":{поля}} — типы: %(blocks)s
{"op":"remove_block","block":"<uid>"}
{"op":"move_block","block":"<uid>","to":<номер позиции с 0>}
{"op":"block","block":"<uid>","variant":"…","tone":"base|alt|dark|accent","nav":"подпись в меню", …поля блока, "items":[…полный новый список карточек]}
{"op":"add_page","title":"…","blocks":["<тип>",…]} / {"op":"remove_page","page":<номер>}
{"op":"image","url":"https://…картинка","block":"<uid>","index":<номер карточки или нет>,"caption":"…"} — картинка ПО ССЫЛКЕ (человек
дал ссылку или попросил фото со своего сайта): скачается и встанет в раздел (в галерее — новой карточкой). Картинка, которую
человек ПРИЛОЖИЛ в чат («сохранена: Входящие/…»): {"op":"image","file":"Входящие/имя.jpg","block":…} — так же. Видео — раздел video:
{"op":"add_block","type":"video","data":{"items":[{"url":"https://youtu.be/…","caption":"…"}]}} (YouTube, Rutube, VK Видео, файл .mp4).
Код встраивания (<iframe>, <video>, HTML) в текст не вставляй никогда — только ссылку в раздел video.
{"op":"media_from","url":"https://сайт-человека/страница","photo":true,"video":true} — человек просит взять фото и видео со СВОЕЙ
страницы: первое фото — на обложку, остальные — в галерею, ролики — в «Видео». Чужие сайты без просьбы — нет.
"""


def ops_help():
    return OPS_HELP % {"pal": ", ".join(f"{k} ({v['title']})" for k, v in K.PALETTES.items()),
                       "fonts": ", ".join(f"{k} ({v['title']})" for k, v in K.FONTS.items()),
                       "marks": ", ".join(K.MARKS), "tpl": ", ".join(f"{k} ({K.TEMPLATES[k]['title']})" for k in K.TEMPLATE_ORDER),
                       "blocks": "; ".join(f"{k} ({v['title']}: варианты {', '.join(v['variants'])}; поля {', '.join(f[0] for f in v['fields'])}"
                                           + (f"; карточки {', '.join(f[0] for f in v['items'][0])}" if v.get("items") else "") + ")" for k, v in K.BLOCKS.items())}


def site_brief(site, full=True):
    """Сайт коротко — для модели: тема, страницы, блоки с uid и текстами."""
    th = site.get("theme") or {}
    lines = [f"Сайт «{site.get('name')}» — {site.get('tagline') or ''}. Шаблон {site.get('template')}, палитра {th.get('palette')}, "
             f"шрифты {th.get('fonts')}, углы {th.get('radius')}, шапка {th.get('header')}, меню {(site.get('menu') or {}).get('style')}, "
             f"стиль {th.get('style') or 'classic'}" + (f", фон сайта {' → '.join(th['bg'])}" if th.get("bg") else "") + ".",
             "Контакты: " + json.dumps(site.get("contacts") or {}, ensure_ascii=False)]
    for i, pg in enumerate(site.get("pages") or []):
        lines.append(f"Страница {i} «{pg.get('title')}»:")
        for b in pg.get("blocks") or []:
            d = {k: v for k, v in b.items() if k not in ("uid", "type", "variant", "tone", "items") and v not in ("", None)}
            if not full:
                d = {k: (str(v)[:60] if isinstance(v, str) else v) for k, v in d.items() if k in ("title", "nav")}
            its = b.get("items") or []
            lines.append(f"  [{b.get('uid')}] {b.get('type')}/{b.get('variant')}/{b.get('tone')} {json.dumps(d, ensure_ascii=False)}"
                         + (f" items: {json.dumps(its, ensure_ascii=False)[:1500]}" if its and full else (f" ({len(its)} карточек)" if its else "")))
    return "\n".join(lines)


def chat_knowledge(site):
    """05.11 (владелец: «как на наш созданный сайт вставить виджет Лиры?»): «Чат для сайта» включают прямо из «Сайтов» —
    и если знаний у консультанта ещё нет, он узнаёт дело с сайта: название, о чём, контакты, услуги и цены, расписание,
    вопросы и ответы. Только то, что написано на сайте (заглушки людей и скрытые разделы — нет). -> {title, brief, greeting, kb}"""
    name = str(site.get("name") or "").strip()
    seo = str((site.get("seo") or {}).get("description") or "").strip()
    brief = " — ".join(x for x in (name, str(site.get("tagline") or "").strip()) if x)
    brief = (brief + (". " + seo if seo else "")).strip()[:1500]
    out = []
    ct = {k: v for k, v in (site.get("contacts") or {}).items() if str(v or "").strip() and k in K.CONTACT_KEYS}
    if ct:
        out.append("Контакты:\n" + "\n".join(f"{K.CONTACT_KEYS[k]}: {v}" for k, v in ct.items()))
    for pg in site.get("pages") or []:
        for b in pg.get("blocks") or []:
            if b.get("hidden") or b.get("type") in ("lead", "links", "gallery", "team", "reviews"):
                continue
            head = str(b.get("title") or K.BLOCKS.get(b.get("type"), {}).get("title") or "").strip()
            lines = [str(b.get(k) or "").strip() for k in ("text", "note") if str(b.get(k) or "").strip()]
            for x in b.get("items") or []:
                if not isinstance(x, dict) or x.get("todo"):
                    continue
                if b.get("type") == "faq":
                    q, a = str(x.get("q") or "").strip(), str(x.get("a") or "").strip()
                    if q and a:
                        lines.append(f"Вопрос: {q} Ответ: {a}")
                    continue
                parts = [str(x.get(k) or "").strip() for k in ("time", "group", "title", "text") if str(x.get(k) or "").strip()]
                if str(x.get("price") or "").strip():
                    parts.append("цена " + str(x["price"]).strip())
                if parts:
                    lines.append("— " + ", ".join(parts))
            if lines:
                out.append(f"{head}:\n" + "\n".join(lines) if head else "\n".join(lines))
    kb = "\n\n".join(out)[:12000]
    return {"title": name[:300], "brief": brief, "kb": kb,
            "greeting": f"Здравствуйте! Подскажу по услугам, ценам и записи{' в «' + name + '»' if name else ''}. Что вас интересует?"[:300]}


def verify_code(v):
    """Код подтверждения поисковика: человек вставляет весь метатег («<meta name="yandex-verification" content="…">») или
    только код — берём код; странное — пусто."""
    v = str(v or "").strip()
    m = re.search(r'content\s*=\s*["\']([^"\']+)', v)
    v = (m.group(1) if m else v).strip()
    return v if re.fullmatch(r"[A-Za-z0-9_\-]{8,100}", v) else ""


def _json_in(text):
    t = str(text or "")
    t = re.sub(r"^```(?:json)?\s*|\s*```\s*$", "", t.strip())
    for opener, closer in (("{", "}"), ("[", "]")):
        i, j = t.find(opener), t.rfind(closer)
        if i >= 0 and j > i:
            try:
                return json.loads(t[i:j + 1])
            except ValueError:
                continue
    return None


EDIT_SYSTEM = ("Ты — веб-дизайнер в программе Dewiar. Сайт хранится данными (не HTML), ты меняешь его операциями. Человек просит "
               "изменение одной фразой — верни ТОЛЬКО JSON: {\"ops\": [...], \"say\": \"что сделала, одной фразой\"}. Тексты пиши "
               "по-русски, живо и по делу, без канцелярита. НЕ выдумывай отзывы, людей, награды, цифры и цены, которых не дал человек; "
               "нужен раздел отзывов, а отзывов нет — добавь блок reviews без карточек. Меняй только то, о чём просят.\n\n")
FILL_SYSTEM = ("Ты — копирайтер и веб-дизайнер в программе Dewiar. Есть шаблон сайта с текстами-заготовками; человек описал своё дело. "
               "Перепиши тексты под его дело: название, слоган, заголовки, описания, услуги, меню, вопросы. Используй ТОЛЬКО факты "
               "человека; чего он не сказал — пиши в общем виде, без конкретных цифр. Цены — только названные человеком, остальные "
               "оставь пустыми (\"\"). НЕ выдумывай отзывы, имена людей, награды, годы, количества клиентов. "
               "Блоки с числами (stats — «Цифры», bars — «Полосы», cases — «Кейсы»): только числа и проекты, которые назвал человек; "
               "если их нет — верни для такого блока {\"hidden\": true}. Пиши живо, коротко, "
               "по-русски, без «качественно и недорого». Верни ТОЛЬКО JSON: {\"name\": \"…\", \"tagline\": \"…\", \"description\": "
               "\"описание для поисковиков 120–160 знаков\", \"contacts\": {…только названные}, \"blocks\": {\"<uid>\": {поля и "
               "\"items\": [полный список карточек]}}}.")
