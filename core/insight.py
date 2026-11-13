"""«Радар» — Лира-аналитик ниши (владелец 12.11.2026; устройство — docs/RADAR.md).

Здесь всё без движка: источники (что за ссылка и где у неё лента), разбор лент и страниц, хранилище, подсказки модели
и разбор её ответов, тренды, поле сигналов, «Галактика», срочное. Сеть и модель дают снаружи (engine_insight.py), поэтому
модуль проверяется целиком без интернета.

Внутреннее имя — insight: «radar» уже занято («Близкие» → «Рядом»)."""
import hashlib
import html as _html
import json
import math
import re
import threading
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlparse

ITEMS_MAX = 3000                 # сколько материалов хранить (старые уходят; разобранные с сигналом ≥ 7 — дольше)
TEXT_MAX = 1600                  # начало текста материала для разбора (знаков)
DAILY_MAX = 60                   # разборов в сутки по умолчанию (insight.daily_max)
URGENT_MIN = 8.5                 # сигнал, с которого материал — срочное
URGENT_GAP = 3600                # срочное — не чаще раза в час
TREND_DAYS = 8                   # спарклайн тренда — столько дней
TYPES = ("release", "analysis", "news", "practice", "incident", "opinion", "video", "research")
DETECT_V = 3                     # версия detect(): старые источники при обходе определяются заново (3 — vk.ru, №690)
KINDS = ("rss", "site", "youtube", "telegram", "reddit", "github", "vk", "dzen", "article")

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
      "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/rss+xml;q=0.9,*/*;q=0.8",
      "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8"}


# ---------------- источники ----------------

def norm_link(u):
    """Ссылка для сравнения: без схемы, www, хвостового «/», меток utm и якоря."""
    u = (u or "").strip()
    p = urlparse(u if "://" in u else "https://" + u)
    q = "&".join(x for x in (p.query or "").split("&") if x and not re.match(r"(utm_|fbclid|yclid|gclid|ref=)", x))
    host = (p.netloc or "").lower().removeprefix("www.").removeprefix("m.")
    return host + (p.path or "").rstrip("/") + ("?" + q if q else "")


def detect(link):
    """Ссылка человека -> {kind, url, feed, name} без сети. feed — адрес ленты, если он известен заранее (RSS, Reddit,
    GitHub, Telegram, YouTube с channel_id); иначе обход сначала откроет страницу и поищет ленту в ней (find_feed)."""
    s = (link or "").strip().strip("<>\"'")
    if not s:
        return None
    m = re.fullmatch(r"@([A-Za-z][\w]{3,31})", s)                      # @канал — Telegram
    if m:
        return {"kind": "telegram", "url": f"https://t.me/{m[1]}", "feed": f"https://t.me/s/{m[1]}", "name": "@" + m[1]}
    m = re.fullmatch(r"r/([\w]{2,30})", s)                              # r/сабреддит
    if m:
        s = f"https://www.reddit.com/r/{m[1]}"
    if not re.match(r"https?://", s):
        if not re.match(r"[\w.-]+\.[a-zа-я]{2,}(/|$)", s, re.I):
            return None
        s = "https://" + s
    p = urlparse(s)
    host = p.netloc.lower().removeprefix("www.").removeprefix("m.")
    path = p.path.rstrip("/")
    name = host
    if host in ("t.me", "telegram.me"):
        ch = path.strip("/").split("/")[-1] if path.strip("/") else ""
        ch = ch if ch != "s" else ""
        if ch:
            return {"kind": "telegram", "url": f"https://t.me/{ch}", "feed": f"https://t.me/s/{ch}", "name": "@" + ch}
    if host == "web.telegram.org":                                       # веб-Telegram: #@канал читается, #-100… — нет
        ch = (p.fragment or "").lstrip("@")
        if re.fullmatch(r"[A-Za-z][\w]{3,31}", ch):
            return {"kind": "telegram", "url": f"https://t.me/{ch}", "feed": f"https://t.me/s/{ch}", "name": "@" + ch}
        return {"kind": "telegram", "url": s, "feed": "", "name": "Telegram", "bad": "tg_web"}
    if host == "habr.com":                                               # «Моя лента» Хабра — страница, а не RSS
        m = re.fullmatch(r"(?:/(ru|en))?/feed(?:/.*)?", path or "/feed")
        if m:
            lang = m[1] or "ru"
            return {"kind": "rss", "url": s, "feed": f"https://habr.com/{lang}/rss/articles/?fl={lang}", "name": "Хабр"}
    if host.endswith("youtube.com") or host == "youtu.be":
        m = re.search(r"/channel/(UC[\w-]{20,})", path)
        feed = f"https://www.youtube.com/feeds/videos.xml?channel_id={m[1]}" if m else ""
        m2 = re.search(r"/(@[\w.-]+)", path)
        return {"kind": "youtube", "url": s, "feed": feed, "name": (m2[1] if m2 else "YouTube")}
    if host.endswith("reddit.com"):
        m = re.search(r"/r/([\w]+)", path)
        if m:
            return {"kind": "reddit", "url": f"https://www.reddit.com/r/{m[1]}", "feed": f"https://www.reddit.com/r/{m[1]}/.rss",
                    "name": "r/" + m[1]}
    if host == "github.com":
        parts = [x for x in path.split("/") if x]
        if len(parts) >= 2:
            return {"kind": "github", "url": f"https://github.com/{parts[0]}/{parts[1]}",
                    "feed": f"https://github.com/{parts[0]}/{parts[1]}/releases.atom", "name": f"{parts[0]}/{parts[1]}"}
    if host in ("vk.com", "vk.ru") or host.endswith((".vk.com", ".vk.ru")):          # vk.ru — новый адрес VK (№690)
        nm = vk_name(s)
        return {"kind": "vk", "url": f"https://vk.com/{nm}" if nm else s, "feed": "", "name": "VK " + (nm or host)}
    if host.endswith("dzen.ru") or host.endswith("zen.yandex.ru"):
        return {"kind": "dzen", "url": s, "feed": "", "name": "Дзен " + (path.strip("/").split("/")[-1] or "")}
    if re.search(r"(\.rss|\.atom|\.xml|/rss|/feed|/atom)(/|\?|$)", path + ("?" if p.query else ""), re.I) or "format=rss" in (p.query or ""):
        return {"kind": "rss", "url": s, "feed": s, "name": name}
    # длинный путь со «словами» — одна статья; корень или раздел — сайт
    if len([x for x in path.split("/") if x]) >= 2 and re.search(r"[\w-]{12,}", path.split("/")[-1] or ""):
        return {"kind": "article", "url": s, "feed": "", "name": name}
    return {"kind": "site", "url": s, "feed": "", "name": name}


def vk_name(url):
    """vk.com/имя, vk.ru/club123, m.vk.com/public123 -> «имя» / «club123»; не сообщество (wall, feed…) — ""."""
    p = urlparse(url if "://" in url else "https://" + url)
    parts = [x for x in p.path.split("/") if x]
    if not parts:
        return ""
    n = parts[0].lower()
    if n in ("wall", "feed", "im", "away.php", "search", "video", "music", "groups", "friends", "login") or not re.fullmatch(r"[a-z0-9_.]{2,64}", n):
        return ""
    return n


def first_line(text, n=140):
    t = re.sub(r"\s+", " ", (text or "").strip().split("\n")[0])
    return t if len(t) <= n else t[:n - 1].rstrip() + "…"


def parse_vk(html, name=""):
    """Посты со страницы сообщества VK (мобильная m.vk.com: pi_text; обычная: wall_post_text) -> материалы.
    Ссылка — /wall-123_456 рядом с текстом; дата у разметки VK словами («вчера в 12:30») — берём время чтения."""
    out, seen = [], set()
    for m in re.finditer(r'class="(?:pi_text|wall_post_text)[^"]*"[^>]*>(.*?)</div>', html or "", re.S):
        body = re.sub(r"<br\s*/?>", "\n", m.group(1))
        text = _html.unescape(re.sub(r"<[^>]+>", "", body)).strip()
        if len(text) < 20:
            continue
        before = html[max(0, m.start() - 4000):m.start()]
        w = re.findall(r"/wall(-?\d+_\d+)", before)
        url = f"https://vk.com/wall{w[-1]}" if w else f"https://vk.com/{name}"
        if url in seen and w:
            continue
        seen.add(url)
        out.append({"title": first_line(text), "url": url, "ts": int(time.time()), "text": text[:6000]})
    return out[:30]


def split_links(text):
    """Поле «Добавить источники»: по одной в строке, через пробел или запятую."""
    return [x for x in re.split(r"[\s,;]+", text or "") if x.strip()]


def looks_html(text):
    """Пришла страница, а не лента (RSS-адрес оказался обычной страницей)."""
    return bool(re.search(r"<(html|body|div)\b", (text or "")[:20000], re.I)) and not re.search(r"<(rss|feed|rdf:RDF)\b", (text or "")[:4000], re.I)


def find_feed(page, base):
    """Адрес ленты в <link rel="alternate" type="application/rss+xml|atom+xml"> страницы (сайт, YouTube-канал)."""
    for m in re.finditer(r"<link\b[^>]*>", page or "", re.I):
        tag = m.group(0)
        if re.search(r"rel=[\"']?alternate", tag, re.I) and re.search(r"type=[\"']?application/(rss|atom)\+xml", tag, re.I):
            h = re.search(r"href=[\"']([^\"']+)", tag, re.I)
            if h:
                return urljoin(base, _html.unescape(h[1]))
    return ""


def _strip_tags(s):
    s = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", s or "", flags=re.S | re.I)
    s = re.sub(r"<br\s*/?>|</p>|</div>|</li>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = _html.unescape(s)
    return re.sub(r"[ \t\xa0]+", " ", re.sub(r"\n\s*\n+", "\n", s)).strip()


def _ts(v):
    """Дата из ленты (RFC 822, ISO 8601) -> секунды или 0."""
    v = (v or "").strip()
    if not v:
        return 0
    try:
        from email.utils import parsedate_to_datetime
        return int(parsedate_to_datetime(v).timestamp())
    except (TypeError, ValueError, IndexError):
        pass
    try:
        return int(datetime.fromisoformat(v.replace("Z", "+00:00")).timestamp())
    except ValueError:
        return 0


def parse_feed(text, base=""):
    """RSS 2.0 / Atom / RDF -> [{title, url, ts, text}] (без сторонних библиотек). Не лента — []."""
    try:
        root = ET.fromstring((text or "").encode("utf-8") if isinstance(text, str) else text)
    except ET.ParseError:
        return []
    out = []

    def local(t):
        return t.rsplit("}", 1)[-1].lower()
    for el in root.iter():
        if local(el.tag) not in ("item", "entry"):
            continue
        f = {}
        for c in el:
            n = local(c.tag)
            if n == "link":
                href = c.get("href")
                if href and (c.get("rel") in (None, "alternate")):
                    f.setdefault("url", href)
                elif (c.text or "").strip():
                    f.setdefault("url", c.text.strip())
            elif n in ("title",):
                f["title"] = _strip_tags(c.text or "")
            elif n in ("pubdate", "published", "updated", "date"):
                f.setdefault("ts", _ts(c.text))
            elif n in ("description", "summary", "content", "encoded"):
                t = _strip_tags(c.text or "".join(ET.tostring(x, encoding="unicode") for x in c))
                if len(t) > len(f.get("text", "")):
                    f["text"] = t
            elif n == "group":                                   # YouTube: media:group → media:description
                for g in c:
                    if local(g.tag) == "description" and (g.text or "").strip():
                        f["text"] = _strip_tags(g.text)
            elif n == "videoid":
                f["video"] = True
        if f.get("title") and f.get("url"):
            out.append({"title": f["title"][:300], "url": urljoin(base, f["url"]), "ts": f.get("ts") or 0,
                        "text": (f.get("text") or "")[:TEXT_MAX], **({"video": True} if f.get("video") else {})})
    return out


def parse_telegram(page, channel=""):
    """Открытая страница канала t.me/s/<канал> -> материалы (сообщение = материал; заголовок — первая строка)."""
    out = []
    for m in re.finditer(r'<div class="tgme_widget_message[^"]*"[^>]*data-post="([^"]+)"(.*?)(?=<div class="tgme_widget_message[^"]*"[^>]*data-post=|\Z)',
                         page or "", re.S):
        post, body = m.group(1), m.group(2)
        t = re.search(r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', body, re.S)
        text = _strip_tags(t.group(1)) if t else ""
        if len(text) < 30:
            continue
        d = re.search(r'<time[^>]*datetime="([^"]+)"', body)
        first = text.split("\n", 1)[0]
        title = first if len(first) <= 160 else first[:157].rsplit(" ", 1)[0] + "…"
        out.append({"title": title, "url": f"https://t.me/{post}", "ts": _ts(d.group(1)) if d else 0, "text": text[:TEXT_MAX]})
    return out


def parse_page_links(page, base):
    """Сайт без ленты: ссылки на свои материалы с осмысленным текстом (заголовки статей), без меню и подвала."""
    host = urlparse(base).netloc.lower().removeprefix("www.")
    seen, out = set(), []
    for m in re.finditer(r"<a\b[^>]*href=[\"']([^\"'#]+)[\"'][^>]*>(.*?)</a>", page or "", re.S | re.I):
        url = urljoin(base, _html.unescape(m.group(1)))
        p = urlparse(url)
        if p.netloc.lower().removeprefix("www.") != host or len([x for x in p.path.split("/") if x]) < 1:
            continue
        title = _strip_tags(m.group(2))
        if len(title) < 28 or len(title) > 220 or len(title.split()) < 4:
            continue
        k = norm_link(url)
        if k in seen:
            continue
        seen.add(k)
        out.append({"title": title, "url": url, "ts": 0, "text": ""})
    return out[:40]


def article_text(page, limit=TEXT_MAX):
    """Текст статьи со страницы: <article> или самый длинный блок абзацев; заголовок — <h1> или <title>. limit — сколько
    знаков (для разбора — начало; для «читалки» студии — целиком, с запасом)."""
    t = re.search(r"<h1[^>]*>(.*?)</h1>", page or "", re.S | re.I) or re.search(r"<title[^>]*>(.*?)</title>", page or "", re.S | re.I)
    title = _strip_tags(t.group(1)) if t else ""
    a = re.search(r"<article[^>]*>(.*?)</article>", page or "", re.S | re.I)
    body = a.group(1) if a else page or ""
    paras = [_strip_tags(x) for x in re.findall(r"<p[^>]*>(.*?)</p>", body, re.S | re.I)]
    text = "\n".join(x for x in paras if len(x) > 40)
    if not text:
        meta = re.search(r'<meta[^>]+(?:name|property)=["\'](?:og:)?description["\'][^>]+content=["\']([^"\']+)', page or "", re.I)
        text = _html.unescape(meta[1]) if meta else ""
    return title, text[:limit]


READ_MAX = 60000                 # «читалка»: текст статьи целиком (знаков)


# ---------------- хранилище ----------------

def _hid(url, title):
    return hashlib.md5((norm_link(url) or re.sub(r"\W+", " ", (title or "").lower())).encode()).hexdigest()[:14]


class Store:
    """STATE_DIR/insight/: источники, материалы, бриф, разум, журнал тактов. Пишет атомарно, под замком."""

    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()

    def _p(self, name):
        return self.root / f"{name}.json"

    def load(self, name, default):
        try:
            d = json.loads(self._p(name).read_text(encoding="utf-8"))
            return d if isinstance(d, type(default)) else default
        except (OSError, ValueError):
            return default

    def save(self, name, data):
        p = self._p(name)
        tmp = p.with_suffix(".part")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1 if name != "items" else None), encoding="utf-8")
        tmp.replace(p)

    # источники
    def sources(self):
        return self.load("sources", [])

    def add_sources(self, text):
        """-> (добавлены, не понятые, почему) — по каждой ссылке поля «Добавить источники». why: {ссылка: код} для
        ссылок, которые понятны, но не читаются (веб-Telegram с номером канала)."""
        with self.lock:
            src = self.sources()
            have = {norm_link(s["url"]) for s in src}
            added, bad, why = [], [], {}
            for link in split_links(text):
                d = detect(link)
                if not d or d.get("bad"):
                    bad.append(link)
                    if d:
                        why[link] = d["bad"]
                    continue
                k = norm_link(d["url"])
                if k in have:
                    continue
                have.add(k)
                d.update(id=hashlib.md5(k.encode()).hexdigest()[:10], on=True, added=int(time.time()), last=0, err="", n_week=0, v=DETECT_V)
                src.append(d)
                added.append(d)
            self.save("sources", src)
            return added, bad, why

    def update_source(self, sid, **kw):
        with self.lock:
            src = self.sources()
            for s in src:
                if s["id"] == sid:
                    s.update(kw)
            self.save("sources", src)

    def remove_source(self, sid):
        with self.lock:
            self.save("sources", [s for s in self.sources() if s["id"] != sid])

    # материалы
    def items(self):
        return self.load("items", [])

    def add_items(self, src, found):
        """Новые материалы источника (повторы по ссылке и заголовку — мимо) -> сколько добавлено."""
        with self.lock:
            items = self.items()
            have = {x["id"] for x in items}
            now, n = int(time.time()), 0
            for f in found:
                hid = _hid(f.get("url"), f.get("title"))
                if hid in have:
                    continue
                have.add(hid)
                items.append({"id": hid, "src": src["id"], "src_name": src.get("name") or "", "kind": src.get("kind") or "",
                              "title": f.get("title") or "", "url": f.get("url") or "", "ts": int(f.get("ts") or now),
                              "seen": now, "text": (f.get("text") or "")[:TEXT_MAX], **({"video": True} if f.get("video") else {})})
                n += 1
            if len(items) > ITEMS_MAX:
                items.sort(key=lambda x: (float((x.get("a") or {}).get("signal") or 0) >= 7, x.get("seen", 0)))
                items = items[len(items) - ITEMS_MAX:]
            self.save("items", items)
            return n

    def queue(self, limit=10, long_ok=True):
        """Ещё не разобранные — свежие первыми; длинное (видео) — только когда long_ok (ночью)."""
        q = [x for x in self.items() if not x.get("a") and not x.get("fail") and (long_ok or not x.get("video"))]
        return sorted(q, key=lambda x: -max(x.get("ts", 0), x.get("seen", 0)))[:limit]

    def set_analysis(self, iid, a=None, fail=""):
        with self.lock:
            items = self.items()
            for x in items:
                if x["id"] == iid:
                    if a:
                        x["a"], x["text"] = a, x.get("text", "")[:400]        # разобран — длинный текст больше не нужен
                    else:
                        x["fail"] = (fail or "не разобрался")[:120]
            self.save("items", items)

    def mark(self, iid, **kw):
        with self.lock:
            items = self.items()
            for x in items:
                if x["id"] == iid:
                    x.update(kw)
            self.save("items", items)


# ---------------- модель: разбор, бриф, разум ----------------

def lang_name(lang):
    return "English" if (lang or "ru").startswith("en") else "русский"


def today_line(lang="ru", now=None):
    """Владелец 12.11: «гипотезы — в прошедшем времени… модель не знает текущее время». Модель знает мир только до своего
    обучения — сегодняшнюю дату даём в каждой подсказке Радара, с датами материалов."""
    d = datetime.fromtimestamp(now or time.time())
    return (f"Today is {d:%Y-%m-%d}. Treat materials by their dates; your own knowledge may be outdated — the materials are newer."
            if (lang or "ru").startswith("en") else
            f"Сегодня {d:%Y-%m-%d}. Смотри на даты материалов; твои собственные знания могут быть устаревшими — материалы новее.")


def _date(x):
    ts = x.get("ts") or x.get("seen") or 0
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d") if ts else "?"


def analyze_prompt(mission, item, lang="ru"):
    """Подсказка разбора одного материала -> (system, user). Сигнал — не «интересно ли», а насколько это меняет картину."""
    en = (lang or "ru").startswith("en")
    system = (
        "You are a sharp industry analyst. Read one item and answer ONLY with JSON:\n"
        if en else
        "Ты — сильный отраслевой аналитик. Прочитай один материал и ответь ТОЛЬКО JSON:\n") + (
        '{"summary": "1–2 sentences: what happened, with key numbers", "why": "1 sentence: why it matters for THIS niche", '
        f'"type": one of {list(TYPES)}, "tags": ["2–4 short topic tags, lowercase"], '
        '"entities": ["companies, products, people mentioned — as written"], "signal": 0–10}\n'
        + ("Signal: 9–10 — changes the picture for the niche (breach, ban, price shock, major release); 6–8 — notable for "
           "practitioners; 3–5 — routine; 0–2 — noise or off-topic. Off-topic for the niche — signal ≤ 2. "
           f"Write summary and why in {lang_name(lang)}. Do not invent facts that are not in the text."
           if en else
           "Сигнал: 9–10 — меняет картину ниши (утечка, запрет, скачок цен, крупный выпуск); 6–8 — заметно для практиков; "
           "3–5 — рутина; 0–2 — шум или не по теме. Не по теме ниши — сигнал ≤ 2. "
           f"summary и why — на языке: {lang_name(lang)}. Не придумывай того, чего нет в тексте."))
    user = ((f"Niche (mission): {mission or 'not set — judge for a general professional reader'}\n" if en else
             f"Ниша (миссия): {mission or 'не задана — оценивай для профессионала вообще'}\n")
            + f"{today_line(lang)}\nSource: {item.get('src_name', '')}\nDate: {_date(item)}\nTitle: {item.get('title', '')}\nURL: {item.get('url', '')}\n\n"
            + (item.get("text") or "")[:TEXT_MAX])
    return system, user


def _json_obj(raw):
    raw = re.sub(r"<think>.*?</think>", "", raw or "", flags=re.S)
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
        return d if isinstance(d, dict) else None
    except ValueError:
        return None


def parse_analysis(raw):
    """Ответ модели -> {summary, why, type, tags, entities, signal} или None (не JSON, нет сути)."""
    d = _json_obj(raw)
    if not d or not str(d.get("summary") or "").strip():
        return None
    try:
        sig = max(0.0, min(10.0, float(str(d.get("signal", 0)).replace(",", "."))))
    except ValueError:
        sig = 0.0
    tags = [re.sub(r"\s+", " ", str(t)).strip().lower().lstrip("#")[:32] for t in (d.get("tags") or []) if str(t).strip()][:4]
    ents = [re.sub(r"\s+", " ", str(t)).strip()[:40] for t in (d.get("entities") or []) if str(t).strip()][:6]
    typ = str(d.get("type") or "news").strip().lower()
    return {"summary": str(d["summary"]).strip()[:500], "why": str(d.get("why") or "").strip()[:400],
            "type": typ if typ in TYPES else "news", "tags": list(dict.fromkeys(tags)), "entities": list(dict.fromkeys(ents)),
            "signal": round(sig, 1)}


def brief_prompt(mission, items, tr, lang="ru"):
    """Бриф дня по разобранному за сутки -> (system, user)."""
    en = (lang or "ru").startswith("en")
    top = sorted(items, key=lambda x: -x["a"]["signal"])[:25]
    lines = "\n".join(f"[{x['id']}] {_date(x)} ({x['a']['signal']}) {x['title']} — {x['a']['summary']}" for x in top)
    tl = ", ".join(f"{t['name']} ({t['status']}, {t['day']} за сутки)" for t in tr[:10])
    system = (("You are the analyst of this niche. Write the morning brief as JSON only: " if en else
               "Ты — аналитик этой ниши. Составь утренний бриф — ТОЛЬКО JSON: ")
              + '{"headline": "one strong sentence — the main shift of the day", "points": ["up to 5 points, one line each, with numbers"], '
              '"main": [{"id": "material id", "why": "2–3 sentences: what it means and what to do"}] (3 items)}. '
              + (f"Language: {lang_name(lang)}. Only facts from the materials; no generic phrases."
                 if en else f"Язык: {lang_name(lang)}. Только факты из материалов; без общих слов."))
    user = (f"{today_line(lang)}\n{'Niche' if en else 'Ниша'}: {mission or '—'}\n{'Trends' if en else 'Тренды'}: {tl or '—'}\n\n"
            f"{'Materials (id, date, signal, title — summary)' if en else 'Материалы (id, дата, сигнал, заголовок — суть)'}:\n{lines}")
    return system, user


def parse_brief(raw, items):
    d = _json_obj(raw) or {}
    ids = {x["id"] for x in items}
    head = str(d.get("headline") or "").strip()
    if not head:
        return None
    pts = [str(p).strip() for p in (d.get("points") or []) if str(p).strip()][:5]
    main = [{"id": str(m.get("id")), "why": str(m.get("why") or "").strip()[:600]}
            for m in (d.get("main") or []) if isinstance(m, dict) and str(m.get("id")) in ids][:3]
    return {"headline": head[:200], "points": pts, "main": main, "at": int(time.time()), "n": len(items)}


def evolve_prompt(mission, mind, items, lang="ru"):
    """Ночная «эволюция» разума: тезисы картины мира с опорой на материалы, гипотезы (новые и проверка старых)."""
    en = (lang or "ru").startswith("en")
    lines = "\n".join(f"[{x['id']}] {_date(x)} ({x['a']['signal']}) {x['title']} — {x['a']['summary']}"
                      for x in sorted(items, key=lambda x: -x["a"]["signal"])[:40])
    today = datetime.now().date()
    th = "\n".join(f"- {t['text']}" for t in (mind.get("theses") or [])[:12]) or "—"
    hy = "\n".join(f"- [{h['id']}] {h['text']} (до {h.get('due', '?')})" for h in (mind.get("hyps") or []) if h.get("state") == "open") or "—"
    system = (("You maintain an expert's picture of the niche. JSON only: " if en else "Ты ведёшь картину ниши эксперта. Только JSON: ")
              + '{"theses": [{"text": "a claim about the niche now", "refs": ["material ids"]}] (up to 8, each backed by refs), '
              f'"new_hyps": [{{"text": "a checkable forecast about the FUTURE", "due": "YYYY-MM-DD between {today + timedelta(days=7)} and {today + timedelta(days=60)}"}}] (up to 3), '
              '"checks": [{"id": "hypothesis id", "state": "confirmed|refuted|open", "refs": ["ids"]}]} '
              + (f"Language: {lang_name(lang)}. No claim without refs. Theses describe the niche NOW (by material dates); a forecast is "
                 f"only about what has not happened yet — never a date before today ({today})."
                 if en else f"Язык: {lang_name(lang)}. Ни одного тезиса без ссылок. Тезисы — о нише СЕЙЧАС (по датам материалов); прогноз — "
                 f"только о том, что ещё не случилось, и никогда не о дате раньше сегодняшней ({today})."))
    user = (f"{today_line(lang)}\nNiche: {mission or '—'}\nCurrent theses:\n{th}\nOpen hypotheses:\n{hy}\n\nNew materials:\n{lines}" if en else
            f"{today_line(lang)}\nНиша: {mission or '—'}\nТекущие тезисы:\n{th}\nОткрытые гипотезы:\n{hy}\n\nНовые материалы:\n{lines}")
    return system, user


def apply_evolve(mind, raw, items):
    """Ответ «эволюции» -> новый разум (версия +1, запись в дневник). Тезис без ссылок на настоящие материалы — мимо."""
    d = _json_obj(raw)
    if not d:
        return None
    ids = {x["id"] for x in items}
    m = dict(mind)
    th = [{"text": str(t.get("text")).strip()[:300], "refs": [r for r in (t.get("refs") or []) if r in ids][:5]}
          for t in (d.get("theses") or []) if isinstance(t, dict) and str(t.get("text") or "").strip()]
    th = [t for t in th if t["refs"]][:8]
    hyps = list(m.get("hyps") or [])
    by = {h["id"]: h for h in hyps}
    changed = 0
    for c in d.get("checks") or []:
        h = by.get(str(c.get("id")))
        st = str(c.get("state") or "")
        if h and h.get("state") == "open" and st in ("confirmed", "refuted"):
            h.update(state=st, closed=int(time.time()), refs=[r for r in (c.get("refs") or []) if r in ids][:5])
            changed += 1
    today = datetime.now().date()
    for n in (d.get("new_hyps") or [])[:3]:
        if isinstance(n, dict) and str(n.get("text") or "").strip():
            if not due_ok(n.get("due"), today):              # прогноз в прошлое (12.11) или без срока — не прогноз
                continue
            hid = hashlib.md5(str(n["text"]).encode()).hexdigest()[:8]
            if hid not in by:
                hyps.append({"id": hid, "text": str(n["text"]).strip()[:300], "due": str(n.get("due") or "")[:10], "state": "open",
                             "at": int(time.time())})
    v = int(m.get("v") or 0) + 1
    if th:
        m["theses"] = th
    m.update(hyps=hyps[-40:], v=v)
    m["diary"] = (list(m.get("diary") or []) + [{"v": v, "at": int(time.time()), "theses": len(th), "new_hyps": len(d.get("new_hyps") or []),
                                                  "closed": changed}])[-60:]
    return m


def due_ok(due, today=None):
    """Срок гипотезы: дата позже сегодняшней и не дальше полугода."""
    today = today or datetime.now().date()
    try:
        d = datetime.strptime(str(due or "")[:10], "%Y-%m-%d").date()
    except ValueError:
        return False
    return today < d <= today + timedelta(days=183)


def clean_hyps(mind):
    """Открытые гипотезы со сроком раньше дня, когда их выдвинули, — «прогноз в прошлое» (до 0.92.2 модель не знала даты):
    убираем. -> (разум, сколько убрали)."""
    hs = list(mind.get("hyps") or [])
    keep = []
    for h in hs:
        try:
            due = datetime.strptime(str(h.get("due") or "")[:10], "%Y-%m-%d").date()
        except ValueError:
            due = None
        born = datetime.fromtimestamp(int(h.get("at") or 0)).date() if h.get("at") else None
        if h.get("state") == "open" and due and born and due <= born:
            continue
        keep.append(h)
    return dict(mind, hyps=keep), len(hs) - len(keep)


def accuracy(mind):
    hs = [h for h in (mind.get("hyps") or []) if h.get("state") in ("confirmed", "refuted")]
    ok = sum(1 for h in hs if h["state"] == "confirmed")
    return {"confirmed": ok, "refuted": len(hs) - ok, "rate": round(ok / len(hs), 2) if hs else None}


# ---------------- тренды, поле сигналов, галактика, срочное ----------------

def _day(ts):
    return datetime.fromtimestamp(ts).date()


def trends(items, now=None, days=TREND_DAYS):
    """По тегам и сущностям: сутки против нормы за предыдущие 7 дней. -> [{name, kind, day, norm, impulse, status,
    spark, sources}] — сильнее сверху. «новая тема» — раньше не было, «растёт», «стабильно», «спадает»."""
    now = now or time.time()
    t0 = now - 86400
    week0 = now - 8 * 86400
    acc = {}
    for x in items:
        a = x.get("a")
        if not a:
            continue
        ts = x.get("ts") or x.get("seen") or 0
        if ts < now - days * 86400:
            continue
        names = [(t, "topic") for t in a.get("tags") or []] + [(e, "entity") for e in a.get("entities") or []]
        for n, kind in names:
            key = n.lower()
            r = acc.setdefault(key, {"name": n, "kind": kind, "spark": [0] * days, "day": 0, "week": 0, "srcs": set(), "ids": []})
            idx = days - 1 - min(days - 1, int((now - ts) // 86400))
            r["spark"][idx] += 1
            if ts >= t0:
                r["day"] += 1
                r["ids"].append(x["id"])
            elif ts >= week0:
                r["week"] += 1
            r["srcs"].add(x.get("src"))
    out = []
    for r in acc.values():
        if r["day"] + r["week"] < 2:
            continue
        norm = r["week"] / 7.0
        imp = round((r["day"] - norm) / math.sqrt(norm + 1), 2)
        status = ("new" if r["week"] == 0 and r["day"] >= 2 else "up" if imp >= 1 else "down" if imp <= -0.8 else "flat")
        out.append({"name": r["name"], "kind": r["kind"], "day": r["day"], "norm": round(norm, 2), "impulse": imp, "status": status,
                    "spark": r["spark"], "sources": len(r["srcs"]), "ids": r["ids"][:8]})
    return sorted(out, key=lambda t: (-t["impulse"], -t["day"]))


def field(items, now=None, days=7):
    """«Поле сигналов»: точки разобранных материалов за неделю -> [{id, x (0..days, дробно — время), s, title, src}]."""
    now = now or time.time()
    out = []
    for x in items:
        a = x.get("a")
        ts = x.get("ts") or x.get("seen") or 0
        if not a or ts < now - days * 86400:
            continue
        out.append({"id": x["id"], "x": round(days - (now - ts) / 86400, 3), "s": a["signal"], "title": x["title"][:120],
                    "src": x.get("src_name", "")})
    return out


def galaxy(items, k=6):
    """Созвездия: k самых частых тегов — центры; материал — к созвездию своего самого частого тега. -> {clusters, points}."""
    cnt = {}
    for x in items:
        for t in (x.get("a") or {}).get("tags") or []:
            cnt[t] = cnt.get(t, 0) + 1
    centers = [t for t, _ in sorted(cnt.items(), key=lambda kv: -kv[1])[:k]]
    clusters = {c: {"name": c, "n": 0, "near": {}} for c in centers}
    points = []
    for x in items:
        tags = (x.get("a") or {}).get("tags") or []
        if not tags:
            continue
        c = next((t for t in sorted(tags, key=lambda t: -cnt.get(t, 0)) if t in clusters), None)
        if c is None:
            continue
        cl = clusters[c]
        cl["n"] += 1
        for t in tags:
            if t != c:
                cl["near"][t] = cl["near"].get(t, 0) + 1
        points.append({"id": x["id"], "c": centers.index(c), "s": x["a"]["signal"], "title": x["title"][:120], "src": x.get("src_name", "")})
    cls = [{"name": c["name"], "n": c["n"], "tags": [t for t, _ in sorted(c["near"].items(), key=lambda kv: -kv[1])[:3]]}
           for c in clusters.values()]
    return {"clusters": cls, "points": points}


def urgent(items, tr, sent, now=None, min_signal=URGENT_MIN):
    """Что сказать сразу: материалы с сигналом ≥ min_signal за последние 6 часов и темы-всплески (импульс ≥ 3 и ≥ 3
    материала за сутки), о которых ещё не говорили (sent — множество id и имён тем). -> [{kind, id|name, text}]."""
    now = now or time.time()
    out = []
    for x in items:
        a = x.get("a")
        if a and a["signal"] >= min_signal and (x.get("seen") or 0) >= now - 6 * 3600 and x["id"] not in sent:
            out.append({"kind": "item", "id": x["id"], "title": x["title"], "text": a["summary"], "url": x.get("url", ""), "signal": a["signal"]})
    for t in tr:
        if t["impulse"] >= 3 and t["day"] >= 3 and ("t:" + t["name"].lower()) not in sent:
            out.append({"kind": "trend", "id": "t:" + t["name"].lower(), "title": t["name"], "day": t["day"], "impulse": t["impulse"]})
    return out


def ask_context(items, tr, brief, mind, query="", limit=12):
    """Для инструмента insight_ask: что важного (по сигналу) или по запросу (слова в заголовке, сути, тегах) + тренды."""
    words = [w for w in re.findall(r"[\wё]{3,}", (query or "").lower())]

    def hit(x):
        if not words:
            return True
        blob = " ".join([x.get("title", ""), (x.get("a") or {}).get("summary", ""), " ".join((x.get("a") or {}).get("tags") or []),
                         " ".join((x.get("a") or {}).get("entities") or [])]).lower()
        return any(w in blob for w in words)
    rows = sorted([x for x in items if x.get("a") and hit(x)], key=lambda x: (-x["a"]["signal"], -(x.get("ts") or 0)))[:limit]
    return {"brief": {k: brief.get(k) for k in ("headline", "points")} if brief else None,
            "trends": [{k: t[k] for k in ("name", "status", "day", "norm", "impulse")} for t in tr[:8]],
            "items": [{"id": x["id"], "title": x["title"], "url": x.get("url"), "source": x.get("src_name"), "date": datetime.fromtimestamp(x.get("ts") or x.get("seen") or 0).strftime("%d.%m"),
                       "signal": x["a"]["signal"], "summary": x["a"]["summary"], "why": x["a"].get("why", "")} for x in rows],
            "theses": [t["text"] for t in (mind or {}).get("theses") or []][:6]}


def question_prompt(question, ctx, mission="", lang="ru"):
    """«Спросите Лиру о теме» прямо в «Радаре»: ответ только по разобранному, со ссылками [n] на материалы."""
    en = (lang or "ru").startswith("en")
    rows = "\n".join(f"[{i + 1}] {x['date']} · {x['source']} · signal {x['signal']} — {x['title']}: {x['summary']} {x.get('why') or ''}".strip()
                     for i, x in enumerate(ctx.get("items") or []))
    tr = ", ".join(f"{t['name']} ({t['status']}, {t['day']}/{t['norm']})" for t in ctx.get("trends") or [])
    b = ctx.get("brief") or {}
    if en:
        system = ("You are Lira, a calm analyst of the user's field. Answer ONLY from the Radar data below — no outside facts, no guesses. "
                  "Be brief: 2–5 sentences or up to 5 short bullets, plain text, no headings. Cite materials as [n]. If the data does not "
                  "answer the question, say so honestly and suggest which sources to add. Answer in English.")
    else:
        system = ("Ты — Лира, спокойный аналитик темы человека. Отвечай ТОЛЬКО по данным Радара ниже — без фактов со стороны и без "
                  "догадок. Коротко: 2–5 предложений или до 5 коротких пунктов, простым текстом, без заголовков. Ссылайся на материалы "
                  "как [n]. Если в данных ответа нет — честно скажи и подскажи, какие источники добавить. Отвечай по-русски.")
    user = (f"{today_line(lang)}\n{'Mission' if en else 'Тема человека'}: {mission or '—'}\n"
            f"{'Daily brief' if en else 'Бриф дня'}: {b.get('headline') or '—'}\n"
            f"{'Trends (day/norm)' if en else 'Тренды (сутки/норма)'}: {tr or '—'}\n"
            f"{'Materials' if en else 'Материалы'}:\n{rows or '—'}\n\n"
            f"{'Question' if en else 'Вопрос'}: {question}")
    return system, user


def parse_answer(raw, ctx):
    """Ответ модели -> {text, refs}: без размышлений; [n] — только существующие материалы (выдуманные номера убираются)."""
    text = re.sub(r"<think>.*?</think>", "", raw or "", flags=re.S).strip()
    text = re.sub(r"\*\*|__|^#+\s*", "", text, flags=re.M)              # разметку Markdown — в простой текст
    text = re.sub(r"^\s*[-*•]\s+", "• ", text, flags=re.M)
    items = ctx.get("items") or []
    used = []

    def ref(m):
        n = int(m.group(1))
        if 1 <= n <= len(items):
            if n not in used:
                used.append(n)
            return f"[{n}]"
        return ""
    text = re.sub(r"\[(\d{1,2})\]", ref, text)
    text = re.sub(r"[ \t]+([.,;:])", r"\1", text).strip()
    return {"text": text[:3000], "refs": [{"n": n, "id": items[n - 1]["id"], "title": items[n - 1]["title"], "url": items[n - 1].get("url"),
                                           "source": items[n - 1].get("source")} for n in used]}
