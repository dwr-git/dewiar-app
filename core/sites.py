"""«Сайты» (03.11, владелец: «Лира должна научиться делать сайты… переделать сайт в любой момент — от структуры до дизайна —
одной командой; публикация на dewiar.pro — имя.dewiar.pro; аналитика и заявки — красиво; модерация — потом, в кабинете»).

Сайт — JSON (sites_kit — детали, sites_render — вёрстка):
  {id, name, tagline, template, theme: {palette, colors, fonts, radius, header, art}, logo: {text, mark, style, svg},
   menu: {style, cta}, contacts: {phone, email, address, hours, telegram, …}, seo: {description},
   pages: [{title, slug, description, blocks: [{uid, type, variant, tone, nav, id, …поля, items: […]}]}],
   assets: {"img/….webp": {w, h}}, published: {name, url, ts, status, reason}, created, updated}

Где лежит: STATE_DIR/sites/<id>/ — site.json, history/ (каждое изменение — версия, «верни как было» — откат), img/
(картинки, уже уменьшенные в webp), out/ (собранный сайт для просмотра в браузере).

Как меняется: apply(id, ops) — операции (палитра, шрифт, меню, добавить/убрать/переставить блок, поля блока, «другой
дизайн» — шаблон с сохранением текста…). say(id, фраза) — фраза человека: сначала простые правила (quick_ops: «тёмная
шапка», «строгий шрифт», «добавь цены», «меню бургером», «верни как было»), иначе — модель пишет операции (llm_ops).
create() — по описанию: шаблон по словам (sites_kit.pick_template), имя и контакты — из слов, тексты — модель
переписывает под дело человека (fill), без выдуманных отзывов, людей и цен.

Публикация — dewiar.pro (cloud.php → sites.php): /sites/check, /sites/publish (готовые файлы), /sites/stats (посещения
без cookie), /sites/leads (заявки с формы — раз в 2 минуты в «Клиенты», как «Чат для сайта»), /sites/remove, /sites/mine
(статус: заблокирован администратором и почему). Продвижение — audit(): заголовки, описания, h1/h2, alt, вес страниц,
контакты и форма, Open Graph, заглушки — понятными словами, у каждого пункта — фраза «исправь» для Лиры."""

import base64
import copy
import hashlib
import io
import json
import logging
import re
import secrets
import shutil
import threading
import time
from datetime import datetime
from pathlib import Path

import sites_kit as K

def ref_outline(url, timeout=12.0):
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
    if re.search(r"цвет|палитр|гамм|оформлени|тем[аеуы]\b", tt) and not re.search(r"шапк", tt):
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
             f"стиль {th.get('style') or 'classic'}.",
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


class Sites:
    def __init__(self, root, host=None, llm=None):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.host = host
        self._llm = llm                         # тесты: llm(system, user) -> текст
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread = None
        self.recent = []                        # заявки с сайтов за сеанс (студия)
        self.error = ""
        self._img_cache = {}

    # ---------- хранение ----------
    def _dir(self, sid):
        if not re.fullmatch(r"[a-z0-9]{6,16}", str(sid or "")):
            raise SiteError("нет такого сайта")
        return self.root / sid

    def ids(self):
        return [d.name for d in sorted(self.root.iterdir()) if d.is_dir() and (d / "site.json").exists()] if self.root.exists() else []

    def get(self, sid):
        try:
            return json.loads((self._dir(sid) / "site.json").read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            raise SiteError("нет такого сайта") from e

    def list(self):
        out = []
        for sid in self.ids():
            try:
                s = self.get(sid)
            except SiteError:
                continue
            out.append({"id": sid, "name": s.get("name"), "tagline": s.get("tagline"), "template": s.get("template"),
                        "updated": s.get("updated"), "created": s.get("created"), "published": s.get("published") or None,
                        "palette": (s.get("theme") or {}).get("palette"), "pages": len(s.get("pages") or []),
                        "blocks": sum(len(p.get("blocks") or []) for p in s.get("pages") or []),
                        "blog": {k: (s.get("blog") or {}).get(k) or 0 for k in ("on", "drafts", "live")}})
        return sorted(out, key=lambda x: -(x.get("updated") or 0))

    def find(self, who=""):
        """Сайт по имени или поддомену (пусто — последний изменённый). -> id."""
        items = self.list()
        if not items:
            raise SiteError("сайтов пока нет — скажите, какой сайт сделать")
        w = str(who or "").strip().lower()
        if not w:
            return items[0]["id"]
        for x in items:
            if w in (x["id"], ((x.get("published") or {}).get("name") or "")) or w in str(x.get("name") or "").lower():
                return x["id"]
        for x in items:
            if any(p for p in re.findall(r"\w{4,}", w) if p[:5] in str(x.get("name") or "").lower()):
                return x["id"]
        return items[0]["id"]

    def _save(self, s, label, to=None, merge=False):
        """Записать и положить версию в историю. merge — правка текста в студии: та же подпись в пределах 90 с не плодит
        версии, а обновляет последнюю (печатают по буквам)."""
        with self._lock:
            d = self._dir(s["id"])
            (d / "history").mkdir(parents=True, exist_ok=True)
            s["updated"] = _now()
            txt = json.dumps(s, ensure_ascii=False, indent=1)
            tmp = d / "site.json.tmp"
            tmp.write_text(txt, encoding="utf-8")
            tmp.replace(d / "site.json")
            idx = self._history(s["id"])
            if merge and idx and idx[-1]["label"] == str(label)[:120] and s["updated"] - idx[-1]["ts"] < 90 and len(idx) > 1:
                (d / "history" / f"{idx[-1]['v']:05d}.json").write_text(txt, encoding="utf-8")
                idx[-1]["ts"] = s["updated"]
                (d / "history" / "index.json").write_text(json.dumps(idx, ensure_ascii=False), encoding="utf-8")
                self._emit(s["id"])
                return s
            v = (idx[-1]["v"] + 1) if idx else 1
            (d / "history" / f"{v:05d}.json").write_text(txt, encoding="utf-8")
            idx.append({"v": v, "ts": s["updated"], "label": str(label or "Изменение")[:120], **({"to": to} if to else {})})
            for old in idx[:-HISTORY_MAX]:
                try:
                    (d / "history" / f"{old['v']:05d}.json").unlink()
                except OSError:
                    pass
            idx = idx[-HISTORY_MAX:]
            (d / "history" / "index.json").write_text(json.dumps(idx, ensure_ascii=False), encoding="utf-8")
        self._emit(s["id"])
        return s

    def _history(self, sid):
        try:
            return json.loads((self._dir(sid) / "history" / "index.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []

    def history(self, sid):
        return self._history(sid)[::-1]

    def restore(self, sid, v):
        idx = self._history(sid)
        it = next((x for x in idx if x["v"] == int(v)), None)
        if not it:
            raise SiteError("такой версии нет")
        s = json.loads((self._dir(sid) / "history" / f"{it['v']:05d}.json").read_text(encoding="utf-8"))
        cur = self.get(sid)
        s["published"] = cur.get("published")                   # публикация — состояние, а не версия
        return self._save(s, f"Возврат к версии от {datetime.fromtimestamp(it['ts']).strftime('%d.%m %H:%M')}: {it['label']}", to=it["v"])

    def undo(self, sid):
        """«Верни как было»: на шаг назад от того, что сейчас. Откат — запись с to (к какой версии вернулись): её
        состояние — та версия, поэтому «ещё раз» идёт от неё дальше назад, а не к отменённой правке."""
        idx = self._history(sid)
        byv = {x["v"]: x for x in idx}
        cur = idx[-1] if idx else None
        while cur and cur.get("to") in byv:
            cur = byv[cur["to"]]
        pos = idx.index(cur) if cur in idx else 0
        if pos < 1:
            raise SiteError("раньше этого ничего не было — откатывать некуда")
        return self.restore(sid, idx[pos - 1]["v"])

    def delete(self, sid):
        s = self.get(sid)
        if (s.get("published") or {}).get("name"):
            try:
                self.unpublish(sid)
            except SiteError as e:
                log.info("🌐 Сайт удалён, но с dewiar.pro не снялся: %s", e)
        shutil.rmtree(self._dir(sid), ignore_errors=True)
        self._emit("")
        return {"ok": True}

    def _emit(self, sid):
        try:
            if self.host is not None:
                self.host.emit("sites", id=sid)
        except Exception:  # noqa: BLE001
            pass

    # ---------- создание ----------
    def from_template(self, tid, name="", tagline="", contacts=None):
        tid = tid if tid in K.TEMPLATES else "personal"
        t = K.TEMPLATES[tid]
        s = {"id": secrets.token_hex(5), "template": tid, "name": (name or t["name"]).strip()[:80], "tagline": (tagline or t["tagline"]).strip()[:160],
             "theme": {"palette": t["palette"], "fonts": t["fonts"], "radius": t["radius"], "header": t["header"], "art": t["art"], "colors": {},
                       "style": t.get("style") or "classic"},
             "logo": {"text": (name or t["name"]).strip()[:60], "mark": t["logo"]["mark"], "style": t["logo"]["style"]},
             "menu": {"style": t["menu"]}, "contacts": dict(contacts if contacts is not None else t["contacts"]), "seo": {"description": ""},
             "pages": copy.deepcopy(t["pages"]), "assets": {}, "published": None, "created": _now()}
        for pg in s["pages"]:
            for b in pg["blocks"]:
                b["uid"] = _uid()
        if name and tid:
            for b in s["pages"][0]["blocks"]:
                if b["type"] == "hero" and b.get("variant") in ("poster", "center") and b.get("title") == t["name"]:
                    b["title"] = s["name"]               # обложка-афиша с названием — сразу своё
        return s

    def create(self, template="", describe="", name="", tagline="", contacts=None, fill=True, ref=""):
        """Новый сайт: шаблон (или по описанию), своё имя и контакты; тексты — моделью под дело человека.
        ref — сайт-образец (№552): его разделы и тон — подсказкой для шаблона и текстов, тексты и бренды — не копируем."""
        outline = ""
        if str(ref or "").strip():
            try:
                outline = ref_outline(str(ref).strip())
            except SiteError as e:
                log.info("🌐 Сайт-образец не прочитался: %s", e)
        tid = template if template in K.TEMPLATES else K.pick_template(f"{describe} {name} {outline[:600]}")
        ct = {k: str(v).strip()[:200] for k, v in (contacts or {}).items() if k in K.CONTACT_KEYS and str(v or "").strip()}
        s = self.from_template(tid, name, tagline, ct if ct else (None if not describe else {}))
        if describe and not ct:
            s["contacts"] = {}                          # контактов человек не назвал — заглушки шаблона не оставляем
        s["describe"] = str(describe or "")[:3000]
        if outline:
            s["ref"] = str(ref).strip()[:300]
        (self.root / s["id"]).mkdir(parents=True, exist_ok=True)
        note = ""
        if fill and (describe or outline):
            try:
                note = self.fill(s, describe or s.get("name") or "", outline)
            except Exception as e:  # noqa: BLE001
                log.info("🌐 Тексты под дело не написались (оставила заготовки шаблона): %s", e)
                note = "тексты пока из шаблона — модель не ответила"
        s["logo"]["text"] = s["name"]
        self._save(s, f"Создан из шаблона «{K.TEMPLATES[tid]['title']}»")
        s["_note"] = note
        return s

    def fill(self, s, describe, ref=""):
        """Модель переписывает тексты шаблона под дело человека (только его факты). ref — схема сайта-образца (№552)."""
        user = (f"ЧТО РАССКАЗАЛ ЧЕЛОВЕК:\n{describe}\n\n"
                + (f"САЙТ-ОБРАЗЕЦ, который человек привёл в пример (возьми только идею: какие разделы и в каком порядке, тон и "
                   f"длину текстов; НЕ копируй его тексты, названия, бренды, имена, цены, телефоны и адреса — всё своё, по делу "
                   f"человека):\n{ref}\n\n" if ref else "")
                + f"ШАБЛОН (uid блока — в квадратных скобках):\n{site_brief(s)}\n\n"
                "Верни JSON, как сказано. Блоки, которые не нужно менять, не включай.")
        d = _json_in(self.llm(FILL_SYSTEM, user, 3500))
        if not isinstance(d, dict):
            raise SiteError("модель не вернула JSON")
        if str(d.get("name") or "").strip():
            s["name"] = str(d["name"]).strip()[:80]
        if str(d.get("tagline") or "").strip():
            s["tagline"] = str(d["tagline"]).strip()[:160]
        if str(d.get("description") or "").strip():
            s.setdefault("seo", {})["description"] = str(d["description"]).strip()[:300]
        for k, v in (d.get("contacts") or {}).items():
            if k in K.CONTACT_KEYS and str(v or "").strip():
                s["contacts"][k] = str(v).strip()[:200]
        by = {b["uid"]: b for pg in s["pages"] for b in pg["blocks"]}
        # 0.94: «Цифры», «Полосы», «Кейсы» шаблона — чужие числа («1 400+ выпускников»): если модель их не переписала
        # числами человека, на сайт они не выходят (блок скрыт — человек включит, когда впишет свои)
        nums = {uid: json.dumps(b.get("items") or [], ensure_ascii=False) for uid, b in by.items() if b["type"] in ("stats", "bars", "cases")}
        for uid, f in (d.get("blocks") or {}).items():
            b = by.get(uid)
            if b is None or not isinstance(f, dict):
                continue
            f = clean_fields(f)
            if b["type"] in ("reviews",):
                f.pop("items", None)                     # отзывы — только от человека
            if b["type"] == "team" and "items" in f:
                for x in f["items"]:
                    x.setdefault("todo", True)
            b.update({k: v for k, v in f.items() if k not in ("type", "variant", "tone")})
        for uid, before in nums.items():
            if json.dumps(by[uid].get("items") or [], ensure_ascii=False) == before:
                by[uid]["hidden"] = True
        for b in s["pages"][0]["blocks"]:
            if b["type"] == "hero" and b.get("variant") == "poster" and len(str(b.get("title") or "")) > 24:
                b["variant"] = "split"                   # длинный заголовок на афише не помещается — вёрстка «текст и картинка»
        return ""

    def llm(self, system, user, max_tokens=2500):
        if self._llm:
            return self._llm(system, user)
        from llm import stream_chat
        h = self.host
        prof = h.s.active_llm() if h is not None else None
        if not (prof or {}).get("base_url") and (prof or {}).get("kind") != "ollama":
            raise SiteError("нет модели — выберите её в «Мозге»")
        return "".join(stream_chat(dict(prof, max_tokens=max_tokens, temperature=0.4), system, [{"role": "user", "content": user}]))

    # ---------- изменения ----------
    def _block(self, s, ref):
        """Блок по uid, якорю или типу (первый такого типа). -> (страница, индекс, блок)."""
        ref = str(ref or "").strip()
        for pi, pg in enumerate(s["pages"]):
            for j, b in enumerate(pg["blocks"]):
                if b.get("uid") == ref or (ref and b.get("id") == ref):
                    return pi, j, b
        for pi, pg in enumerate(s["pages"]):
            for j, b in enumerate(pg["blocks"]):
                if b.get("type") == ref:
                    return pi, j, b
        raise SiteError(f"нет такого раздела: {ref}")

    def apply(self, sid, ops, label="", merge=False):
        s = self.get(sid)
        if any(o.get("op") == "undo" for o in ops or [] if isinstance(o, dict)):
            return self.undo(sid)
        done = self.apply_ops(s, ops)
        if not done:
            raise SiteError("ничего не поменялось")
        return self._save(s, label or "; ".join(done)[:120], merge=merge)

    def apply_ops(self, s, ops):
        """Операции к сайту (на месте). -> список того, что сделано (для истории)."""
        done = []
        th = s.setdefault("theme", {})
        for o in ops or []:
            if not isinstance(o, dict):
                continue
            op = o.get("op")
            if op == "palette" and o.get("name") in K.PALETTES:
                th["palette"], th["colors"] = o["name"], {}
                done.append(f"палитра {K.PALETTES[o['name']]['title']}")
            elif op == "colors":
                cs = {k: v for k, v in o.items() if k in K.COLOR_KEYS and re.fullmatch(r"#[0-9a-fA-F]{6}", str(v or ""))}
                if cs:
                    th.setdefault("colors", {}).update(cs)
                    done.append("цвета")
                if o.get("header") in K.HEADERS:
                    th["header"] = o["header"]
                    done.append("шапка")
            elif op == "style" and o.get("value") in K.STYLES:
                # стиль (0.94): «Авангард» приносит свои палитру, шрифт и углы — их потом можно поменять отдельно
                st = K.STYLES[o["value"]]
                th["style"] = o["value"]
                for k in ("palette", "fonts", "radius", "header"):
                    if st.get(k) and not o.get("keep"):
                        th[k] = st[k]
                if st.get("palette") and not o.get("keep"):
                    th["colors"] = {}
                done.append(f"стиль «{st['title']}»")
            elif op == "header" and o.get("value") in K.HEADERS:
                th["header"] = o["value"]
                done.append(K.HEADERS[o["value"]].lower())
            elif op == "fonts" and o.get("name") in K.FONTS:
                th["fonts"] = o["name"]
                done.append(f"шрифт {K.FONTS[o['name']]['title']}")
            elif op == "radius" and o.get("name") in K.RADII:
                th["radius"] = o["name"]
                done.append(K.RADII[o["name"]]["title"].lower())
            elif op == "art" and o.get("name") in K.ARTS:
                th["art"] = o["name"]
                done.append("узор")
            elif op == "menu":
                m = s.setdefault("menu", {})
                if o.get("style") in K.MENUS:
                    m["style"] = o["style"]
                    done.append("меню " + K.MENUS[o["style"]].lower())
                if "cta" in o:
                    m["cta"] = _clip("button", o.get("cta") or "")
                    done.append("кнопка в шапке")
            elif op == "logo":
                lg = s.setdefault("logo", {})
                if o.get("text"):
                    lg["text"] = _clip("title", o["text"])[:60]
                if o.get("mark") in K.MARKS:
                    lg["mark"], lg["svg"] = o["mark"], ""
                if o.get("style") in K.LOGO_STYLES:
                    lg["style"] = o["style"]
                if o.get("svg"):
                    lg["svg"] = clean_svg(o["svg"])
                done.append("логотип")
            elif op == "site":
                for k in ("name", "tagline"):
                    if str(o.get(k) or "").strip():
                        s[k] = _clip("title", o[k]).strip()[:160 if k == "tagline" else 80]
                        if k == "name" and not (s.get("logo") or {}).get("svg"):
                            s.setdefault("logo", {})["text"] = s["name"]
                if "description" in o:
                    s.setdefault("seo", {})["description"] = _clip("text", o.get("description") or "")[:300]
                for k in ("verify_yandex", "verify_google"):          # 0.93: подтверждение в Вебмастере и Search Console
                    if k in o:
                        s.setdefault("seo", {})[k] = verify_code(o.get(k))
                done.append("название и описание")
            elif op == "contacts":
                ct = s.setdefault("contacts", {})
                for k, v in o.items():
                    if k in K.CONTACT_KEYS:
                        v = str(v or "").strip()[:200]
                        if v:
                            ct[k] = v
                        else:
                            ct.pop(k, None)
                done.append("контакты")
            elif op == "legal":
                if self._legal(s, o):
                    done.append("подвал и документы")
            elif op == "template" and o.get("id") in K.TEMPLATES:
                self._restyle(s, o["id"])
                done.append(f"дизайн «{K.TEMPLATES[o['id']]['title']}»")
            elif op == "add_block" and o.get("type") in K.BLOCKS:
                pi = int(o.get("page") or 0) if str(o.get("page") or "0").isdigit() else 0
                pi = max(0, min(pi, len(s["pages"]) - 1))
                bl = s["pages"][pi]["blocks"]
                b = K.blank_block(o["type"])
                b.update(clean_fields(o.get("data") or {}))
                if o["type"] == "reviews":
                    b["items"] = [x for x in b.get("items") or [] if str(x.get("text") or "").strip()]
                if o["type"] == "team":
                    for x in b.get("items") or []:
                        if not x.get("image") and not str(x.get("text") or "").strip() and x.get("name") in ("Имя", ""):
                            x["todo"] = True
                b["uid"] = _uid()
                b["nav"] = b.get("nav") or K.BLOCKS[o["type"]]["title"]
                at = None
                if o.get("after"):
                    try:
                        p2, j, _ = self._block(s, o["after"])
                        if p2 == pi:
                            at = j + 1
                    except SiteError:
                        pass
                if at is None:                           # по умолчанию — перед заявкой и контактами в конце страницы
                    at = len(bl)
                    while at > 0 and bl[at - 1]["type"] in ("lead", "contacts", "links") and o["type"] not in ("lead", "contacts"):
                        at -= 1
                prev = bl[at - 1]["tone"] if at > 0 else "alt"
                b["tone"] = b.get("tone") if o.get("data", {}).get("tone") in K.TONES else ("alt" if prev == "base" else "base")
                bl.insert(at, b)
                done.append(f"добавлен раздел {K.BLOCKS[o['type']]['title']}")
            elif op == "remove_block":
                pi, j, b = self._block(s, o.get("block"))
                s["pages"][pi]["blocks"].pop(j)
                done.append(f"убран раздел {K.BLOCKS.get(b['type'], {}).get('title', b['type'])}")
            elif op == "move_block":
                pi, j, b = self._block(s, o.get("block"))
                bl = s["pages"][pi]["blocks"]
                to = o.get("to")
                if to == "up":
                    to = j - 1
                elif to == "down":
                    to = j + 1
                try:
                    to = max(0, min(int(to), len(bl) - 1))
                except (TypeError, ValueError):
                    continue
                bl.insert(to, bl.pop(j))
                done.append("порядок разделов")
            elif op == "block":
                pi, j, b = self._block(s, o.get("block"))
                f = clean_fields({k: v for k, v in o.items() if k not in ("op", "block")})
                if f.get("variant") is not None and f["variant"] not in K.BLOCKS[b["type"]]["variants"]:
                    f.pop("variant")
                if f.get("tone") is not None and f["tone"] not in K.TONES:
                    f.pop("tone")
                if "id" in f:
                    f["id"] = re.sub(r"[^a-z0-9_-]", "", str(f["id"]).lower())[:30]
                if b["type"] == "reviews" and "items" in f:
                    f["items"] = [x for x in f["items"] if str(x.get("text") or "").strip()]
                if "items" in f:
                    for x in f["items"]:
                        if b["type"] == "team" and not x.get("todo") and x.get("name") in ("Имя врача", "Имя"):
                            x["todo"] = True
                b.update(f)
                done.append(f"раздел {K.BLOCKS.get(b['type'], {}).get('title', b['type'])}")
            elif op == "item":
                pi, j, b = self._block(s, o.get("block"))
                its = b.setdefault("items", [])
                i = o.get("index")
                if o.get("remove") and isinstance(i, int) and 0 <= i < len(its):
                    its.pop(i)
                elif isinstance(i, int) and 0 <= i < len(its):
                    its[i].update(clean_fields(o.get("data") or {}, "item"))
                    if its[i].get("todo") and o.get("data"):
                        its[i].pop("todo", None)          # человек заполнил заглушку — она его
                else:
                    its.append(clean_fields(o.get("data") or {}, "item"))
                done.append("карточки")
            elif op == "add_page":
                title = _clip("nav", o.get("title") or "Страница")
                slug = translit(title) or f"page{len(s['pages'])}"
                if slug == "index" or any(p.get("slug") == slug for p in s["pages"]):
                    slug += f"-{len(s['pages'])}"
                blocks = []
                for t in o.get("blocks") or ["text"]:
                    if t in K.BLOCKS:
                        b = K.blank_block(t)
                        b["uid"] = _uid()
                        blocks.append(b)
                s["pages"].append({"title": title, "slug": slug, "blocks": blocks})
                done.append(f"страница «{title}»")
            elif op == "remove_page":
                i = int(o.get("page") or 0)
                if 0 < i < len(s["pages"]):
                    s["pages"].pop(i)
                    done.append("страница убрана")
            elif op == "page":
                i = int(o.get("page") or 0)
                if 0 <= i < len(s["pages"]):
                    pg = s["pages"][i]
                    if o.get("title"):
                        pg["title"] = _clip("nav", o["title"])
                    if "description" in o:
                        pg["description"] = _clip("text", o.get("description") or "")[:300]
                    if "seo_title" in o:
                        pg["seo_title"] = _clip("title", o.get("seo_title") or "")[:90]
                    done.append("страница")
        return done

    @staticmethod
    def _legal(s, o):
        """«Подвал и документы» (0.87): реквизиты, документы (ссылка или свой текст — своя страница сайта), доп. ссылки.
        -> поменялось ли что-то."""
        lg = s.get("legal") if isinstance(s.get("legal"), dict) else {}
        before = json.dumps(lg, ensure_ascii=False, sort_keys=True)
        for k in K.LEGAL_FIELDS:
            if k not in o:
                continue
            v = re.sub(r"[\x00-\x1f]", " ", str(o.get(k) or "")).strip()
            if k in ("inn", "ogrn"):
                v = re.sub(r"\D", "", v)[:12 if k == "inn" else 15]
            v = v[:300 if k == "address" else 200]
            if v:
                lg[k] = v
            else:
                lg.pop(k, None)
        if isinstance(o.get("docs"), dict):
            docs = lg.setdefault("docs", {})
            for k, d in o["docs"].items():
                if k not in K.LEGAL_DOCS or not isinstance(d, dict):
                    continue
                cur = dict(docs.get(k) or {})
                if "mode" in d:
                    cur["mode"] = d["mode"] if d["mode"] in ("link", "text") else ""
                if "url" in d:
                    cur["url"] = str(d.get("url") or "").strip()[:500]
                if "text" in d:
                    t = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(d.get("text") or "")).replace("\r\n", "\n")[:K.LEGAL_TEXT_MAX]
                    if t != cur.get("text"):
                        cur["text"], cur["ts"] = t, _now()
                        if not d.get("draft"):
                            cur.pop("draft", None)          # человек поправил черновик Лиры — он его
                if d.get("draft"):
                    cur["draft"] = True
                if not cur.get("mode") and not cur.get("text") and not cur.get("url"):
                    docs.pop(k, None)
                else:
                    docs[k] = cur
            if not docs:
                lg.pop("docs", None)
        if isinstance(o.get("links"), list):
            links = []
            for x in o["links"][:K.LEGAL_LINKS_MAX]:
                if isinstance(x, dict):
                    t, u = str(x.get("title") or "").strip()[:80], str(x.get("url") or "").strip()[:500]
                    if t or u:
                        links.append({"title": t, "url": u})
            if links:
                lg["links"] = links
            else:
                lg.pop("links", None)
        if lg:
            s["legal"] = lg
        else:
            s.pop("legal", None)
        return json.dumps(lg, ensure_ascii=False, sort_keys=True) != before

    def legal_draft(self, sid, key="privacy"):
        """«Составить черновик политики ПД по моим данным» (0.87): Лира пишет политику (или согласие) по реквизитам и
        устройству сайта; кладём «своим текстом» с пометкой draft — в студии: «черновик — проверьте с юристом»."""
        if key not in ("privacy", "consent"):
            raise SiteError("черновик Лира пишет для политики обработки данных и согласия")
        s = self.get(sid)
        lg = s.get("legal") or {}
        ct = s.get("contacts") or {}
        org = str(lg.get("org") or "").strip()
        if not org:
            raise SiteError("сначала впишите название организации или ИП — в политике оно обязательно")
        mail, phone = str(lg.get("email") or ct.get("email") or "").strip(), str(lg.get("phone") or ct.get("phone") or "").strip()
        if not mail and not phone:
            raise SiteError("впишите почту или телефон — куда людям писать о своих данных")
        pub = (s.get("published") or {}).get("url") or ""
        blocks = [b for pg in s.get("pages") or [] for b in pg.get("blocks") or [] if not b.get("hidden")]
        lead = next((b for b in blocks if b.get("type") == "lead"), None)
        fields = ["имя", "телефон, почта или ник в Telegram"] + (["комментарий"] if lead and lead.get("ask_message") else [])
        facts = "\n".join(x for x in (
            f"Оператор: {org}", f"ИНН: {lg['inn']}" if lg.get("inn") else "", f"ОГРН/ОГРНИП: {lg['ogrn']}" if lg.get("ogrn") else "",
            f"Адрес: {lg.get('address') or ct.get('address') or ''}" if (lg.get("address") or ct.get("address")) else "",
            f"Почта для обращений: {mail}" if mail else "", f"Телефон: {phone}" if phone else "",
            f"Сайт: «{s.get('name') or ''}» {pub}".strip(), f"Чем занимается: {s.get('tagline') or ''}",
            ("Форма заявки на сайте собирает: " + ", ".join(fields) + ". Цель — связаться с человеком по его заявке.") if lead
            else "Формы заявки на сайте нет; данные приходят, только если человек сам напишет или позвонит.",
            "Сайт работает на сервисе Dewiar (dewiar.pro): заявки хранятся там и передаются владельцу сайта; посещения считаются без cookie и без сторонних счётчиков; cookie сайт не ставит.",
        ) if x)
        what = "политику в отношении обработки персональных данных (152-ФЗ, ст. 18.1)" if key == "privacy" else \
            "согласие посетителя на обработку персональных данных (152-ФЗ, ст. 9), которое он даёт галочкой в форме заявки"
        system = ("Ты — помощник по документам сайта в программе Dewiar. Напиши " + what + " для небольшого сайта по-русски, "
                  "простым ясным языком, без воды. Используй ТОЛЬКО факты ниже; чего нет — не выдумывай (не пиши о cookie, "
                  "рассылках, оплате, передаче за границу, если этого нет в фактах). Разделы — строкой «## Название» (общие "
                  "положения, кто оператор, какие данные, цели, правовые основания, сроки хранения, кому передаём, права "
                  "человека и как отозвать согласие, защита данных, изменения документа). Списки — строками «- …». Верни "
                  "только текст документа, без пояснений до и после.")
        text = self.llm(system, "ФАКТЫ:\n" + facts, 3500)
        text = re.sub(r"^```\w*\s*|\s*```\s*$", "", str(text or "").strip()).strip()
        if len(text) < 400:
            raise SiteError("модель вернула слишком короткий текст — попробуйте ещё раз")
        self.apply(sid, [{"op": "legal", "docs": {key: {"mode": "text", "text": text, "draft": True}}}],
                   f"Черновик: {K.LEGAL_DOCS[key]['title'].lower()}")
        return {"text": text}

    def _restyle(self, s, tid):
        """«Другой дизайн целиком»: тема, меню, вид логотипа и вёрстка блоков — из шаблона tid; тексты и порядок — свои."""
        t = K.TEMPLATES[tid]
        s["template"] = tid
        s["theme"] = {"palette": t["palette"], "fonts": t["fonts"], "radius": t["radius"], "header": t["header"], "art": t["art"], "colors": {},
                      "style": t.get("style") or "classic"}
        s.setdefault("menu", {})["style"] = t["menu"]
        lg = s.setdefault("logo", {})
        lg["style"] = t["logo"]["style"]
        tb = {}
        for b in t["pages"][0]["blocks"]:
            tb.setdefault(b["type"], b)
        for pg in s["pages"]:
            for j, b in enumerate(pg["blocks"]):
                src = tb.get(b["type"])
                if src:
                    b["variant"], b["tone"] = src["variant"], src["tone"]
                    if b["type"] == "hero" and src["variant"] == "poster" and len(str(b.get("title") or "")) > 24:
                        b["variant"] = "split"
                else:
                    b["tone"] = "alt" if j % 2 else "base"

    def say(self, sid, text):
        """Фраза человека -> изменение. -> {site, said}."""
        s = self.get(sid)
        ops, said = quick_ops(text, s)
        if ops:
            if ops[0].get("op") == "undo":
                return {"site": self.undo(sid), "said": said}
            try:
                return {"site": self.apply(sid, ops, f"«{str(text)[:80]}»"), "said": said}
            except SiteError:
                pass
        d = _json_in(self.llm(EDIT_SYSTEM + ops_help(), f"{site_brief(s)}\n\nПРОСЬБА ЧЕЛОВЕКА: {text}", 3500))
        if isinstance(d, list):
            d = {"ops": d}
        if not isinstance(d, dict) or not d.get("ops"):
            raise SiteError("не поняла, что поменять, — скажите иначе: «добавь раздел с ценами», «сделай шапку тёмной»")
        s2 = self.apply(sid, d["ops"], f"«{str(text)[:80]}»")
        return {"site": s2, "said": str(d.get("say") or "Готово.")[:300]}

    # ---------- картинки ----------
    def image_add(self, sid, data, alt=""):
        """Картинка (data:… или байты) -> уменьшенная webp в img/ сайта. -> путь (img/….webp) для поля image."""
        from PIL import Image, ImageOps
        if isinstance(data, str):
            m = re.match(r"data:image/[a-z+.-]+;base64,(.+)$", data, re.S)
            if not m:
                raise SiteError("нужна картинка (jpg, png, webp)")
            raw = base64.b64decode(m.group(1))
        else:
            raw = bytes(data)
        if len(raw) > 25 * 1024 * 1024:
            raise SiteError("картинка больше 25 МБ")
        try:
            im = Image.open(io.BytesIO(raw))
            im = ImageOps.exif_transpose(im).convert("RGB")
        except Exception as e:  # noqa: BLE001
            raise SiteError("это не картинка или она повреждена") from e
        im.thumbnail((1920, 1920))
        buf = io.BytesIO()
        im.save(buf, "WEBP", quality=80, method=5)
        b = buf.getvalue()
        name = f"img/{hashlib.sha1(b).hexdigest()[:16]}.webp"
        d = self._dir(sid)
        (d / "img").mkdir(parents=True, exist_ok=True)
        (d / name).write_bytes(b)
        s = self.get(sid)
        s.setdefault("assets", {})[name] = {"w": im.width, "h": im.height, "alt": str(alt or "")[:200], "size": len(b)}
        with self._lock:
            (d / "site.json").write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")
        return name

    def _images(self, sid, s, mode):
        out = {}
        for name in (s.get("assets") or {}):
            f = self._dir(sid) / name
            if not f.exists():
                continue
            if mode == "preview":
                key = (str(f), f.stat().st_mtime)
                if key not in self._img_cache:
                    self._img_cache[key] = "data:image/webp;base64," + base64.b64encode(f.read_bytes()).decode()
                out[name] = self._img_cache[key]
            else:
                out[name] = name
        return out

    # ---------- вёрстка ----------
    def render(self, sid, page=0, site=None):
        """Предпросмотр: page — номер страницы или «doc:privacy» (страница документа из «Подвала и документов»)."""
        s = site or self.get(sid)
        pg = str(page or 0)
        if pg.startswith("doc:"):
            return R.page_html(s, 0, "preview", self._images(sid, s, "preview"), doc=pg[4:])
        return R.page_html(s, int(pg) if pg.lstrip("-").isdigit() else 0, "preview", self._images(sid, s, "preview"))

    def build(self, sid, mode="publish", base_url=""):
        """Собрать сайт целиком: {путь: bytes}."""
        s = self.get(sid)
        imgs = self._images(sid, s, mode)
        files, fonts = R.site_files(s, imgs, base_url, mode)
        out = {k: v.encode("utf-8") for k, v in files.items()}
        for name, src in fonts:
            f = FONTS_DIR / src
            if f.exists():
                out["fonts/" + name] = f.read_bytes()
        used = "".join(files.values())
        for name in imgs:
            if name in used:
                out[name] = (self._dir(sid) / name).read_bytes()
        return out

    def export(self, sid):
        """Сайт в папку out/ — открыть в браузере с диска. -> путь к index.html."""
        d = self._dir(sid) / "out"
        shutil.rmtree(d, ignore_errors=True)
        for k, v in self.build(sid, "export").items():
            f = d / k
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(v)
        return d / "index.html"

    # ---------- продвижение ----------
    def audit(self, sid):
        """Проверка продвижения без внешних служб: заголовки и описания страниц, h1/h2, alt, вес, контакты и форма,
        Open Graph, заглушки. -> {score, items: [{ok, level, title, detail, fix}]} — fix: фраза для Лиры."""
        s = self.get(sid)
        files = self.build(sid, "publish", (s.get("published") or {}).get("url") or "")
        pages = [(i, pg, files.get(R.slug_of(pg, i) + ".html", b"").decode("utf-8", "replace")) for i, pg in enumerate(s.get("pages") or [])]
        items = []

        def add(ok, level, title, detail, fix=""):
            items.append({"ok": bool(ok), "level": level, "title": title, "detail": detail, "fix": "" if ok else fix})
        for i, pg, h in pages:
            pname = "главной" if i == 0 else f"страницы «{pg.get('title')}»"
            t = re.search(r"<title>(.*?)</title>", h, re.S)
            tl = len(R.html.unescape(t.group(1))) if t else 0
            add(15 <= tl <= 70, "важно", f"Заголовок {pname} для поисковиков",
                f"{tl} знаков — хорошо (нужно 15–70)" if 15 <= tl <= 70 else f"{tl} знаков, а лучше 15–70: в поиске заголовок {'обрежется' if tl > 70 else 'слишком короткий'}",
                f"Сделай заголовок {pname} для поисковиков длиной 40–65 знаков: название и чем занимаемся")
            dm = re.search(r'<meta name="description" content="([^"]*)"', h)
            dl = len(R.html.unescape(dm.group(1))) if dm else 0
            add(70 <= dl <= 170, "важно", f"Описание {pname}",
                f"{dl} знаков — хорошо" if 70 <= dl <= 170 else ("описания нет — поисковик возьмёт случайный кусок текста" if not dl else
                                                                 f"{dl} знаков, а лучше 120–160"),
                f"Напиши описание {pname} для поисковиков на 120–160 знаков: что предлагаем, где и почему к нам")
            h1 = len(re.findall(r"<h1[\s>]", h))
            add(h1 == 1, "важно", f"Главный заголовок (h1) {pname}", "один — как нужно" if h1 == 1 else f"их {h1}, а нужен ровно один",
                f"Добавь на {pname} обложку с главным заголовком")
            h2 = len(re.findall(r"<h2[\s>]", h))
            add(h2 >= 2 or len(pg.get("blocks") or []) < 3, "полезно", f"Подзаголовки разделов {pname}", f"{h2} — поисковику понятна структура" if h2 >= 2 else "мало подзаголовков",
                f"Дай каждому разделу {pname} понятный заголовок")
            imgs = re.findall(r"<img\b[^>]*>", h)
            noalt = [x for x in imgs if re.search(r'alt=""', x) or "alt=" not in x]
            add(not noalt, "полезно", f"Подписи к картинкам {pname}", "у всех картинок есть подписи" if imgs and not noalt else
                ("картинок нет" if not imgs else f"без подписи: {len(noalt)} из {len(imgs)}"),
                f"Подпиши фото на {pname}: коротко, что на них")
        size = sum(len(v) for k, v in files.items() if not k.startswith("fonts/"))
        fonts = sum(len(v) for k, v in files.items() if k.startswith("fonts/"))
        add(size < 1_500_000, "важно", "Вес сайта", f"{size // 1024} КБ страниц и картинок + {fonts // 1024} КБ шрифтов — открывается быстро даже с телефона"
            if size < 1_500_000 else f"{size // 1024} КБ — тяжело для мобильного интернета", "Уменьши фото на сайте или убери лишние")
        ct = s.get("contacts") or {}
        add(any(ct.get(k) for k in ("phone", "email", "telegram", "whatsapp", "max")), "важно", "Как связаться",
            "контакты есть" if any(ct.get(k) for k in ("phone", "email", "telegram", "whatsapp", "max")) else "ни телефона, ни почты, ни мессенджера",
            "Добавь на сайт телефон или Telegram — я продиктую")
        types = {b["type"] for pg in s.get("pages") or [] for b in pg.get("blocks") or []}
        add("lead" in types, "важно", "Форма заявки", "есть — заявки придут в «Клиенты»" if "lead" in types else "нет формы — посетителю сложнее оставить заявку",
            "Добавь форму заявки перед контактами")
        pol = R.legal_href(s, "privacy")
        draft = " (черновик Лиры — проверьте с юристом)" if pol.endswith(".html") and (((s.get("legal") or {}).get("docs") or {}).get("privacy") or {}).get("draft") else ""
        if pol:
            pdet = ("есть, в форме заявки — галочка согласия" if "lead" in types else "есть") + draft
        else:
            pdet = ("на сайте есть форма заявки, а политики обработки персональных данных нет — по закону (152-ФЗ) она нужна"
                    if "lead" in types else "формы заявки нет — политика пока не обязательна")
        add(bool(pol) or "lead" not in types, "важно" if "lead" in types else "полезно", "Политика обработки данных", pdet, "Подвал и документы")
        org = str((s.get("legal") or {}).get("org") or "").strip()
        add(bool(org), "полезно", "Реквизиты в подвале", f"есть: {org}" if org else "нет названия организации или ИП и ИНН — людям спокойнее, когда видно, кто за сайтом",
            "Подвал и документы")
        add(bool(ct.get("address")) or "contacts" in types, "полезно", "Адрес и карта", "есть" if ct.get("address") else "адреса нет — если вы принимаете у себя, его ищут первым",
            "Добавь адрес в контакты")
        add(True, "полезно", "Карточка для соцсетей (Open Graph)", "есть: название, описание и картинка в превью ссылки")
        if not any(b.get("image") for pg in s.get("pages") or [] for b in pg.get("blocks") or []):
            items[-1]["detail"] = "есть название и описание; добавьте фото на обложку — ссылка в мессенджерах будет с картинкой"
        todo = [b for pg in s.get("pages") or [] for b in pg.get("blocks") or [] if any(x.get("todo") for x in b.get("items") or [])]
        empty_prices = [b for pg in s.get("pages") or [] for b in pg.get("blocks") or [] if b["type"] in ("prices", "services", "products")
                        and any(not str(x.get("price") or "").strip() for x in b.get("items") or [])]
        add(not todo, "важно", "Заглушки", "все заглушки заменены" if not todo else
            f"в разделе «{K.BLOCKS[todo[0]['type']]['title']}» остались заглушки — их не видно на сайте, пока не замените",
            "Расскажу о сотрудниках — замени заглушки в команде")
        add(not empty_prices, "полезно", "Цены", "у всех позиций есть цены" if not empty_prices else "у части позиций нет цены — люди чаще пишут, когда видят цену",
            "Помоги заполнить цены — спроси меня о них")
        gal = [b for pg in s.get("pages") or [] for b in pg.get("blocks") or [] if b["type"] == "gallery"]
        if gal:
            have = sum(1 for b in gal for x in b.get("items") or [] if x.get("image"))
            add(have > 0, "полезно", "Фото в галерее", f"фото: {have}" if have else "фото не добавлены — галерея на сайте не покажется",
                "Как добавить фото в галерею?")
        pub = (s.get("published") or {}).get("url")
        seo = s.get("seo") or {}
        if pub:                                       # 0.93: технический SEO — сам; подтвердить сайт в поисковиках — одно поле
            add(True, "полезно", "Карта сайта и robots.txt", f"есть сами: {pub}/sitemap.xml — новые страницы и статьи попадают в неё автоматически, "
                "а Яндекс и Bing узнают о них сразу (IndexNow)")
            add(bool(seo.get("verify_yandex")), "полезно", "Яндекс Вебмастер", "сайт подтверждён — смотрите в Вебмастере, как Яндекс его видит"
                if seo.get("verify_yandex") else "не подтверждён — подтвердите: увидите поисковые запросы и ускорите появление в поиске", "@verify")
            add(bool(seo.get("verify_google")), "полезно", "Google Search Console", "сайт подтверждён" if seo.get("verify_google")
                else "не подтверждён — подтвердите, чтобы видеть, по каким запросам вас находят в Google", "@verify")
            bl = s.get("blog") or {}
            add(bool(bl.get("on")), "полезно", "Статьи", f"Лира ведёт статьи: на сайте {bl.get('live') or 0}" if bl.get("on")
                else "статей нет — статьи по вопросам клиентов приводят людей из поиска", "@blog")
        add(bool(pub), "важно", "Сайт в интернете", f"опубликован: {pub}" if pub else "ещё не опубликован — поисковики его не видят",
            "Опубликуй сайт")
        w = {"важно": 3, "полезно": 1}
        tot = sum(w[x["level"]] for x in items)
        score = round(100 * sum(w[x["level"]] for x in items if x["ok"]) / tot) if tot else 0
        return {"score": score, "items": sorted(items, key=lambda x: (x["ok"], x["level"] != "важно")), "size": size, "fonts": fonts}

    # ---------- dewiar.pro ----------
    def _key(self):
        return (getattr(getattr(self.host, "cloud", None), "key", "") or "").strip()

    def _fetch(self, path, body=None, timeout=40):
        from cloud import CloudError, fetch
        if not self._key():
            raise SiteError("нужен вход аккаунтом dewiar.pro или ключ Dewiar — студия → «Мозг»")
        try:
            return fetch(self.host.cloud.url, self._key(), path, timeout=timeout, body=body)
        except CloudError as e:
            raise SiteError(str(e)) from e

    def check_name(self, name, sid=""):
        n = str(name or "").strip().lower()
        p = name_problem(n)
        if p:
            return {"ok": False, "free": False, "reason": p}
        s = self.get(sid) if sid else {}
        if (s.get("published") or {}).get("name") == n:
            return {"ok": True, "free": True, "mine": True}
        d = self._fetch("/sites/check", {"name": n})
        return {"ok": True, "free": bool(d.get("free")), "mine": bool(d.get("mine")), "reason": d.get("reason") or ""}

    def suggest_name(self, sid):
        s = self.get(sid)
        return (s.get("published") or {}).get("name") or translit(s.get("name") or "")[:30].strip("-") or "moy-sait"

    def publish(self, sid, name=""):
        s = self.get(sid)
        n = str(name or (s.get("published") or {}).get("name") or self.suggest_name(sid)).strip().lower()
        p = name_problem(n)
        if p:
            raise SiteError(p)
        files = self.build(sid, "publish", f"https://{n}.dewiar.pro")
        total = sum(len(v) for v in files.values())
        if total > 8 * 1024 * 1024:
            raise SiteError(f"сайт весит {total // 1024 // 1024} МБ, а можно до 8 — уменьшите или уберите часть фото")
        was = (s.get("published") or {}).get("name") or ""
        body = {"name": n, "title": R.seo_title(s, 0)[:160], "description": R.seo_desc(s, 0)[:300], "site": sid, "from": was,
                "files": {k: ({"t": v.decode("utf-8")} if k.endswith((".html", ".css")) else {"b": base64.b64encode(v).decode()}) for k, v in files.items()}}
        d = self._fetch("/sites/publish", body, timeout=90)
        s["published"] = {"name": d.get("name") or n, "url": d.get("url") or f"https://{n}.dewiar.pro", "ts": _now(), "status": "live", "reason": ""}
        old = (self.get(sid).get("published") or {}).get("name")
        if old and old != n:
            try:
                self._fetch("/sites/remove", {"name": old})
            except SiteError:
                pass
        s["published"]["reach"] = reach(s["published"]["url"])
        self._save(s, f"Опубликован: {s['published']['url']}")
        log.info("🌐 Сайт опубликован: %s%s", s["published"]["url"],
                 "" if s["published"]["reach"]["ok"] else f" — по адресу пока не открывается ({s['published']['reach']['why']})")
        self.start()
        return s

    def recheck(self, sid):
        """Открывается ли опубликованный сайт по своему адресу — снова (кнопка «Проверить адрес», фон раз в полчаса)."""
        s = self.get(sid)
        pub = s.get("published") or {}
        if not pub.get("url"):
            return s
        was = (pub.get("reach") or {}).get("ok")
        pub["reach"] = reach(pub["url"])
        s["published"] = pub
        with self._lock:
            (self._dir(sid) / "site.json").write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")
        if pub["reach"]["ok"] and was is False and self.host is not None:
            try:
                self.host.push("Сайт открывается", f"{pub['url']} — адрес заработал, можно отправлять ссылку")
            except Exception:  # noqa: BLE001
                pass
        return s

    def unpublish(self, sid):
        s = self.get(sid)
        n = (s.get("published") or {}).get("name")
        if n:
            self._fetch("/sites/remove", {"name": n})
        s["published"] = None
        return self._save(s, "Снят с публикации")

    def stats(self, sid, days=30, prev=False):
        s = self.get(sid)
        n = (s.get("published") or {}).get("name")
        if not n:
            return {"none": True}
        d = self._fetch("/sites/stats", {"name": n, "days": int(days), "prev": bool(prev)})
        st = s.get("published") or {}
        if bool(d.get("blocked")) != (st.get("status") == "blocked") or (d.get("reason") or "") != (st.get("reason") or ""):
            st.update({"status": "blocked" if d.get("blocked") else "live", "reason": d.get("reason") or ""})
            s["published"] = st
            with self._lock:
                (self._dir(sid) / "site.json").write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")
        d["leads_local"] = [x for x in self.recent if x.get("site") == n][-20:][::-1]
        return d

    def sync_status(self):
        """Состояние своих сайтов на dewiar.pro (блокировка администратором и причина) -> обновить у себя."""
        if not any((self.get(i).get("published") or {}).get("name") for i in self.ids()):
            return 0
        d = self._fetch("/sites/mine", {})
        by = {x.get("name"): x for x in d.get("sites") or []}
        n = 0
        for sid in self.ids():
            s = self.get(sid)
            pub = s.get("published") or {}
            r = by.get(pub.get("name"))
            if not r:
                continue
            st = "blocked" if r.get("blocked") else "live"
            if st != pub.get("status") or (r.get("reason") or "") != (pub.get("reason") or ""):
                pub.update({"status": st, "reason": r.get("reason") or ""})
                s["published"] = pub
                with self._lock:
                    (self._dir(sid) / "site.json").write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")
                n += 1
                if st == "blocked":
                    try:
                        self.host.push("Сайт заблокирован", f"{pub.get('url')}: {r.get('reason') or 'причина в студии → «Сайты»'}")
                    except Exception:  # noqa: BLE001
                        pass
        if n:
            self._emit("")
        return n

    # ---------- заявки ----------
    def take(self, lead):
        """Заявка с формы сайта -> клиент (новый или знакомый) в «Клиентах». -> id клиента."""
        from sitechat import EMAIL_RX, PHONE_RX
        h = self.host
        C = getattr(h, "clients", None)
        if C is None:
            return ""
        contact = str(lead.get("contact") or "").strip()
        m1, m2 = EMAIL_RX.search(contact), PHONE_RX.search(contact)
        when = datetime.fromtimestamp(lead.get("ts") or time.time()).strftime("%d.%m %H:%M")
        text = (f"Заявка с сайта {lead.get('site')}.dewiar.pro ({when}): {contact}" + (f" — {lead['note']}" if lead.get("note") else "")
                + (f" (страница {lead['page']})" if lead.get("page") and lead.get("page") != "index" else ""))
        cid = h.sitechat._find_client(contact) if getattr(h, "sitechat", None) else None
        if cid:
            C.note(cid, text)
        else:
            cid = C.add((lead.get("name") or "").strip() or contact, phone=m2.group(0) if m2 and not m1 else "", email=m1.group(0) if m1 else "")["id"]
            C.note(cid, text)
        crm = getattr(h, "crm", None)
        if crm is not None and crm.connected() and crm.st.get("auto"):
            threading.Thread(target=lambda: crm.send(cid), name="crm-site", daemon=True).start()
        return cid

    def poll(self):
        if not self._key() or not any((self.get(i).get("published") or {}).get("name") for i in self.ids()):
            return 0
        try:
            d = self._fetch("/sites/leads", {})
        except SiteError as e:
            self.error = str(e)
            return 0
        self.error = ""
        done = []
        for lead in d.get("leads") or []:
            try:
                cid = self.take(lead)
            except Exception as e:  # noqa: BLE001
                log.warning("🌐 Заявка с сайта не завелась: %s", e)
                continue
            done.append(lead["id"])
            self._lead_log(lead, cid)
            self.recent.append({"ts": lead.get("ts"), "site": lead.get("site"), "name": lead.get("name") or "", "contact": lead.get("contact") or "",
                                "note": lead.get("note") or "", "page": lead.get("page") or "", "cid": cid})
            self.recent = self.recent[-100:]
            try:
                self.host.push("Заявка с сайта", f"{lead.get('name') or 'Посетитель'}, {lead.get('contact')} — в «Клиентах»")
            except Exception:  # noqa: BLE001
                pass
        if done:
            try:
                self._fetch("/sites/leads", {"ack": done})
            except SiteError as e:
                log.info("🌐 Заявки заведены, но сервер не узнал: %s", e)
            if self.host is not None:
                try:
                    (self.host.s.get("features") or {}).get("clients") or self.host.s.update({"features": {"clients": True}})
                except Exception:  # noqa: BLE001
                    pass
            self._emit("")
        return len(done)

    def _lead_log(self, lead, cid):
        """Заявка — и в журнал своего сайта (leads.json): вкладка «Заявки» показывает их и после перезапуска."""
        for sid in self.ids():
            if (self.get(sid).get("published") or {}).get("name") == lead.get("site"):
                f = self._dir(sid) / "leads.json"
                try:
                    items = json.loads(f.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    items = []
                items.append({"ts": lead.get("ts") or _now(), "name": lead.get("name") or "", "contact": lead.get("contact") or "",
                              "note": lead.get("note") or "", "page": lead.get("page") or "", "cid": cid})
                f.write_text(json.dumps(items[-500:], ensure_ascii=False), encoding="utf-8")
                return

    def leads(self, sid):
        """Заявки этого сайта (журнал leads.json; клиенты — в «Клиентах»), свежие сверху."""
        try:
            return json.loads((self._dir(sid) / "leads.json").read_text(encoding="utf-8"))[::-1]
        except (OSError, ValueError):
            return []

    # ---------- «Статьи» (0.93, sites_blog) ----------
    def blog_save_conf(self, sid, patch):
        """Настройки статей сайта — без версии в истории (это не правка сайта)."""
        with self._lock:
            s = self.get(sid)
            b = dict(s.get("blog") or {})
            b.update(patch)
            s["blog"] = b
            (self._dir(sid) / "site.json").write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")
        return b

    def blog_get(self, sid, fresh=True):
        import sites_blog as B
        s = self.get(sid)
        arts, err = [], ""
        if fresh and (s.get("published") or {}).get("name") and self._key():
            try:
                arts = B.sync(self, sid)
            except SiteError as e:
                err = str(e)
        b = B.conf(self.get(sid))
        r = B.radar_of(self)
        rad = {"sources": len([x for x in r.st.sources() if x.get("on", True)]), "items": len(r.st.items())} if r is not None else None
        return {"blog": b, "articles": arts, "error": err, "published": bool((s.get("published") or {}).get("name")),
                "url": (s.get("published") or {}).get("url") or "", "auto_after": B.AUTO_AFTER, "freqs": B.FREQ, "radar": rad}

    def blog_set(self, sid, patch):
        import sites_blog as B
        p = B.clean_patch(patch or {})
        if p.get("mode") == "auto" and B.conf(self.get(sid))["approved"] < B.AUTO_AFTER:
            raise SiteError(f"«Публиковать сразу» откроется после {B.AUTO_AFTER} одобренных черновиков — сначала посмотрите, как пишет Лира")
        was = B.conf(self.get(sid))
        b = self.blog_save_conf(sid, p)
        if p.get("on") and not was["on"]:                 # включили: Радар — сам, план — сразу, первый черновик — по расписанию
            boost = B.radar_boost(self, self.get(sid), wait=getattr(self, "blog_wait", False))   # проверки ждут обход
            self.blog_save_conf(sid, {"radar": bool(boost.get("sources")) or was.get("radar", False)})
            if not B.conf(self.get(sid))["plan"]:
                try:
                    B.make_plan(self, sid)
                except Exception as e:  # noqa: BLE001
                    self.blog_save_conf(sid, {"err": str(e)[:200]})
        if any(k in p for k in ("on", "freq", "day", "hour")):
            b = self.blog_save_conf(sid, {"next": B.next_slot(B.conf(self.get(sid))) if B.conf(self.get(sid))["on"] else 0})
        return self.blog_get(sid, fresh=False)

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="sites", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _loop(self):
        tick = 0
        while not self._stop.wait(120):
            try:
                import sites_blog
                sites_blog.due(self)                    # 0.93: пора — черновик статьи (по расписанию сайта)
            except Exception:  # noqa: BLE001
                log.exception("Сайты: статьи")
            try:
                self.poll()
                tick += 1
                if tick % 15 == 1:                      # раз в полчаса — не заблокирован ли сайт
                    self.sync_status()
                    for sid in self.ids():               # №549: адрес ещё не открывался — проверить снова, заработал — сказать
                        if ((self.get(sid).get("published") or {}).get("reach") or {}).get("ok") is False:
                            self.recheck(sid)
            except Exception:  # noqa: BLE001
                log.exception("Сайты: заявки")

    # ---------- для студии ----------
    def meta(self):
        return {"templates": [{"id": k, "title": K.TEMPLATES[k]["title"], "sub": K.TEMPLATES[k]["sub"], "palette": K.TEMPLATES[k]["palette"],
                               "fonts": K.TEMPLATES[k]["fonts"], "name": K.TEMPLATES[k]["name"],
                               "style": K.TEMPLATES[k].get("style") or "classic"} for k in K.TEMPLATE_ORDER],
                "palettes": {k: {c: v[c] for c in ("title",) + K.COLOR_KEYS} for k, v in K.PALETTES.items()},
                "fonts": {k: {"title": v["title"], "sub": v["sub"], "head": v["head"], "body": v["body"], "hw": v["hw"], "italic": bool(v.get("italic"))}
                          for k, v in K.FONTS.items()},
                "styles": {k: {"title": v["title"], "sub": v["sub"]} for k, v in K.STYLES.items()},
                "radii": {k: v["title"] for k, v in K.RADII.items()}, "menus": K.MENUS, "headers": K.HEADERS, "tones": K.TONES,
                "marks": {k: {"title": v[0], "svg": K.mark_svg(k)} for k, v in K.MARKS.items()}, "logo_styles": K.LOGO_STYLES,
                "contacts": K.CONTACT_KEYS,
                "legal": {"fields": K.LEGAL_FIELDS, "docs": {k: dict(v) for k, v in K.LEGAL_DOCS.items()}, "links_max": K.LEGAL_LINKS_MAX,
                          "text_max": K.LEGAL_TEXT_MAX},
                "blocks": {k: {"title": v["title"], "sub": v["sub"], "variants": v["variants"], "fields": v["fields"],
                               "items": v.get("items")} for k, v in K.BLOCKS.items()}}

    def template_preview(self, tid):
        s = self.from_template(tid)
        return R.page_html(s, 0, "preview")

    def artist_logos(self):
        """SVG из «Художника» (папка «Рисунки») — кандидаты в логотип."""
        try:
            ws = self.host.workspace.root() if self.host is not None else None
        except Exception:  # noqa: BLE001
            ws = None
        d = Path(ws) / "Рисунки" if ws else None
        if not d or not d.exists():
            return []
        out = []
        for f in sorted(d.glob("*.svg"), key=lambda p: -p.stat().st_mtime)[:24]:
            try:
                out.append({"name": f.stem, "svg": clean_svg(f.read_text(encoding="utf-8"), 64)})
            except (OSError, SiteError):
                continue
        return out

    def public(self, sid):
        s = self.get(sid)
        return {"site": s, "history": self.history(sid)[:40], "meta_v": 1}
