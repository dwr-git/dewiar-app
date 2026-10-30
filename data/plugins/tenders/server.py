"""Плагин «Тендеры» — MCP-сервер (stdio). Перенос сути TenderWatch владельца (PHP, 30.10) на Python без сторонних
библиотек (только httpx, который есть в Dewiar):

  • площадки (goszakupki.by, icetrade.by и своя по шаблону адреса с {QUERY}) ищутся по запросам из настроек плагина;
  • разбор выдачи без модели: повторяющиеся строки (таблица или карточки) находятся сами, колонки — по заголовкам таблицы,
    найденный «рецепт» площадки запоминается; страница «ничего не найдено» распознаётся по фразе;
  • оценка 0–10 по основам слов: совпадение с запросом, плюс-слова, минус-слова (как score.php);
  • одно хранилище с дедупликацией: тот же тендер из двух запросов — одна запись, удалённое не возвращается.

Анализ тендера, сравнение и советы делает сама Лира (у неё есть read_webpage) — здесь только поиск и учёт.
Данные — в DEWIAR_PLUGIN_DATA, настройки — DEWIAR_PLUGIN_SETTINGS (JSON из карточки плагина).
Для проверок: DEWIAR_TENDERS_FIXTURES — папка с сохранёнными страницами вместо сети (имя файла — id площадки)."""

import hashlib
import html
import json
import os
import re
import sys
import time
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote_plus, urljoin

DATA = Path(os.environ.get("DEWIAR_PLUGIN_DATA") or Path.home() / ".dewiar-tenders")
DATA.mkdir(parents=True, exist_ok=True)
STORE = DATA / "store.json"
RECIPES = DATA / "recipes.json"

SOURCES = [
    {"id": "goszakupki", "name": "goszakupki.by", "base": "https://goszakupki.by",
     "url": "https://goszakupki.by/tenders/posted?TendersSearch[text]={QUERY}", "toggle": "goszakupki"},
    {"id": "icetrade", "name": "icetrade.by", "base": "https://icetrade.by",
     "url": "https://icetrade.by/search/auctions?search_text={QUERY}", "toggle": "icetrade"},
]


def settings():
    """Настройки из карточки плагина поверх значений по умолчанию из plugin.json."""
    out = {}
    try:
        for f in json.loads((Path(__file__).with_name("plugin.json")).read_text(encoding="utf-8")).get("settings") or []:
            if "default" in f:
                out[f["key"]] = f["default"]
    except (OSError, ValueError, KeyError, TypeError):
        pass
    try:
        s = json.loads(os.environ.get("DEWIAR_PLUGIN_SETTINGS") or "{}")
    except ValueError:
        s = {}
    out.update(s if isinstance(s, dict) else {})
    return out


def plist(v):
    """«видеонаблюдение; защита информации» или по строкам -> список фраз."""
    return [x.strip() for x in re.split(r"[;\n,]+", str(v or "")) if len(x.strip()) >= 2]


# ---------------- оценка (score.php) ----------------

STOP = set("и в во на по для с со к ко о об от до из за или а не услуг услуга услуги оказание оказания выполнение выполнения "
           "работ работы закупка закупки приобретение поставка поставки обеспечение обеспечения товаров товар том числе".split())
ENDS = sorted("ированного ированной ирование ирования ированию ениями ениях ностью ности ость остей ового ыми ими ого его ому "
              "ему ая яя ое ее ые ие ый ий ой ей ую юю ых их ам ям ах ях ами ями ов ев ом ем ию ия ии ье ья ью ы и а я о е у ю ь й"
              .split(), key=len, reverse=True)


def stem(w):
    w = w.lower().replace("ё", "е")
    if len(w) <= 4 or not re.search(r"[а-я]", w):
        return w
    for e in ENDS:
        if len(w) - len(e) >= 4 and w.endswith(e):
            return w[:-len(e)]
    return w


def stems(text, drop_stop=True):
    return [stem(w) for w in re.findall(r"[^\W_]+", str(text or "").lower()) if len(w) >= 2 and not (drop_stop and w in STOP)]


def phrase_hit(ps, textset):
    if not ps:
        return 0.0
    hit = 0
    for s in ps:
        if s in textset or (len(s) >= 5 and any(len(t) >= 5 and t[:5] == s[:5] for t in textset)):
            hit += 1
    return hit / len(ps)


def score(t, queries, plus, minus):
    """-> (балл 0–10, признаки, минус-слово?)"""
    ts = set(stems(f"{t.get('title', '')} {t.get('procedure_type', '')}"))
    if not ts:
        return 0, [], False
    sc, terms = 0, []
    for ph in plus:
        if phrase_hit(stems(ph), ts) >= 0.99:
            sc += 4
            terms.append("+" + ph)
    best = max([phrase_hit(stems(q), ts) for q in t.get("found_by") or []] or [0.0])
    if best >= 0.99:
        sc += 5
        terms.append("запрос целиком")
    elif best >= 0.6:
        sc += 3
    elif best > 0:
        sc += 1
    if len(t.get("found_by") or []) >= 2:
        sc += 1
    bad = next((ph for ph in minus if phrase_hit(stems(ph), ts) >= 0.99), None)
    if bad:
        terms.append("−" + bad)
    sc = max(0, min(10, sc))
    return (min(sc, 1) if bad else sc), terms, bool(bad)


# ---------------- DOM без сторонних библиотек ----------------

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
SKIP = {"script", "style", "noscript", "svg", "template"}


class Node:
    __slots__ = ("tag", "attrs", "kids", "parent", "_t")

    def __init__(self, tag, attrs, parent):
        self.tag, self.attrs, self.kids, self.parent, self._t = tag, dict(attrs), [], parent, None

    def text(self):
        if self._t is None:
            self._t = re.sub(r"\s+", " ", "".join(k if isinstance(k, str) else k.text() + " " for k in self.kids)).strip()
        return self._t

    def els(self):
        for k in self.kids:
            if isinstance(k, Node):
                yield k
                yield from k.els()

    def classes(self):
        out = []
        for c in (self.attrs.get("class") or "").split():
            if re.match(r"^(odd|even|first|last|active|selected|hover|current|new|visited|is-|js-|ng-|v-)", c, re.I) or re.search(r"\d", c):
                continue
            if re.match(r"^[A-Za-z_][\w-]*$", c):
                out.append(c)
        return sorted(set(out))[:4]

    def sig(self):
        return self.tag + "." + ".".join(self.classes())

    def path(self):
        p, n = [], self
        while n is not None and n.tag != "#root":
            p.append(n.sig())
            n = n.parent
        return "/".join(reversed(p))


class Tree(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("#root", {}, None)
        self.cur, self.skip = self.root, 0

    def handle_starttag(self, tag, attrs):
        if self.skip or tag in SKIP:
            self.skip += 0 if tag in VOID else 1
            return
        n = Node(tag, [(k, v or "") for k, v in attrs], self.cur)
        self.cur.kids.append(n)
        if tag not in VOID:
            self.cur = n

    def handle_endtag(self, tag):
        if self.skip:
            if tag in SKIP:
                self.skip -= 1
            return
        n = self.cur
        while n is not None and n.tag != tag:
            n = n.parent
        if n is not None and n.parent is not None:
            self.cur = n.parent

    def handle_data(self, data):
        if not self.skip and data.strip():
            self.cur.kids.append(data.replace("\xa0", " "))


def parse_html(text):
    t = Tree()
    try:
        t.feed(text)
        t.close()
    except Exception:  # noqa: BLE001
        pass
    return t.root


# ---------------- разбор выдачи (parse.php) ----------------

NUM_RE = re.compile(r"\b\d{4}-\d{6,8}(?!\d)|\bauc\d{6,}(?!\d)|№\s*([A-Za-zА-Яа-я]{0,4}[\-/]?\d[A-Za-z0-9\-/]{3,})")
PRICE_RE = re.compile(r"(\d[\d\s\xa0]*(?:[.,]\d{1,2})?)\s*(BYN|BYR|USD|EUR|RUB|руб\.?|бел\.?\s*руб\.?|₽|\$|€)")
DATE_RE = re.compile(r"\b(\d{2})[./](\d{2})[./](\d{4})\b|\b(\d{4})-(\d{2})-(\d{2})\b")
EMPTY = ["тендеры не найдены", "ничего не найдено", "не найдено ни одной", "по вашему запросу ничего", "результатов не найдено",
         "нет результатов", "записи не найдены", "закупки не найдены", "нет данных для отображения", "no results found",
         "nothing found", "найдено: 0", "найдено 0", "всего: 0"]
NOISE = ["проверка браузера", "расширенный поиск", "простой поиск", "личный кабинет", "обратная связь", "карта сайта", "регистрация",
         "авторизация", "войти", "семинар", "вебинар", "инструкция", "руководство пользователя", "часто задаваемые", "контакты",
         "о сайте", "подписаться", "версия для слабовидящих", "сообщить об ошибке", "политика обработки", "реестр недобросовестных",
         "архив закупок", "выводить на страницу"]
COLS = {"title": r"предмет|описани|наименование\s+(?:закуп|предмет|товар|работ|услуг)|название",
        "organization": r"заказчик|организатор|организаци|покупател",
        "deadline": r"предложени[^|]{0,20}\bдо\b|срок|окончани|дата\s+оконч|до\s+даты|прием",
        "price": r"стоимост|цена|сумма", "number": r"номер|№", "status": r"статус|состояни",
        "procedure_type": r"вид|тип\s+процедур|способ|процедур"}


def ui_noise(title):
    t = title.lower().strip()
    return len(t) < 12 or any(n in t for n in NOISE)


def page_empty(text):
    t = re.sub(r"\s+", " ", text.lower())
    return any(m in t for m in EMPTY)


def links(n):
    return [e for e in n.els() if e.tag == "a" and e.attrs.get("href")]


def groups(root, min_rows=3):
    g = {}
    for el in root.els():
        if el.tag not in ("tr", "li", "div", "article", "section", "dl"):
            continue
        ls = links(el)
        if not ls or len(ls) > 25:
            continue
        txt = el.text()
        if not 25 <= len(txt) <= 2500:
            continue
        key = (el.parent.path() if el.parent else "") + "|" + el.sig()
        g.setdefault(key, []).append(el)
    out = []
    for key, nodes in g.items():
        n = len(nodes)
        if n < min_rows:
            continue
        texts = [x.text() for x in nodes]
        wd = sum(bool(DATE_RE.search(t)) for t in texts)
        wn = sum(bool(NUM_RE.search(t)) for t in texts)
        wp = sum(bool(PRICE_RE.search(t)) for t in texts)
        lens = [len(t) for t in texts]
        avg = sum(lens) / n
        uni = max(0.0, 1 - (sum(abs(x - avg) for x in lens) / n) / avg) if avg else 0
        noise = sum(ui_noise(t) for t in texts)
        sc = wd / n * 3 + wn / n * 3 + wp / n * 2 + uni * 1.5 + min(n, 30) / 30 + min(avg, 300) / 300 - noise / n * 3
        out.append({"key": key, "nodes": nodes, "score": sc, "n": n})
    out.sort(key=lambda x: -x["score"])
    return out


def table_cols(row):
    if row.tag != "tr":
        return {}
    t = row.parent
    while t is not None and t.tag != "table":
        t = t.parent
    if t is None:
        return {}
    ths = [e for e in t.els() if e.tag == "th"]
    if len(ths) < 2:
        return {}
    cols, i = {}, 0
    for th in ths:
        txt = th.text().lower()
        for f, rx in COLS.items():
            if f not in cols and re.search(rx, txt):
                cols[f] = i
                break
        try:
            i += max(1, int(th.attrs.get("colspan") or 1))
        except ValueError:
            i += 1
    return cols


def norm_date(s):
    m = re.search(r"(\d{2})[./-](\d{2})[./-](\d{4})", s)
    if m:
        return f"{m[1]}.{m[2]}.{m[3]}"
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    return f"{m[3]}.{m[2]}.{m[1]}" if m else ""


def fmt_price(m):
    cur = m[2].upper().strip()
    return re.sub(r"[\s\xa0]+", " ", m[1]).strip() + " " + ("BYN" if "РУБ" in cur else cur)


def extract_row(row, base, cols):
    text = row.text()
    cells = [k for k in row.kids if isinstance(k, Node) and k.tag in ("td", "th")] if row.tag == "tr" else []
    cell = lambda f: cells[cols[f]] if f in cols and cols[f] < len(cells) else None   # noqa: E731
    title, url, tcell = "", "", cell("title")
    for a in links(tcell or row):
        t = a.text()
        if len(t) > len(title) and not re.match(r"^(подробнее|скачать|открыть|перейти)$", t, re.I):
            title, url = t, a.attrs.get("href") or ""
    if not title and tcell:
        title = tcell.text()
    if len(title) < 8:
        return None
    number = ""
    c = cell("number")
    if c:
        m = NUM_RE.search(c.text())
        number = (m[1] or m[0]) if m else c.text()[:40]
    if not number:
        m = NUM_RE.search(text)
        number = (m[1] or m[0]) if m else ""
    c = cell("deadline")
    deadline = norm_date(c.text()) if c else ""
    if not deadline:
        ds = re.findall(r"(\d{2})[./](\d{2})[./](\d{4})", text)
        deadline = ".".join(ds[-1]) if ds else ""
    price = ""
    c = cell("price")
    m = PRICE_RE.search(c.text()) if c else None
    if m:
        price = fmt_price(m)
    elif c and re.match(r"^\d[\d\s\xa0]*(?:[.,]\d{1,2})?$", c.text()):
        price = c.text().strip() + " BYN"
    else:
        m = PRICE_RE.search(text)
        price = fmt_price(m) if m else ""
    org = ""
    c = cell("organization")
    if c:
        org = c.text()
    elif tcell:
        rest = tcell.text().replace(title, "").strip()
        if 6 <= len(rest) < 200 and re.search(r"[«\"]|ОАО|ООО|РУП|УП\b|ЗАО|Учреждение|Государственн|Заказчик", rest):
            org = rest
    if not org:
        m = re.search(r"(?:Заказчик|Организатор|Покупатель)\s*[:\-—]\s*(.+?)(?:\s+[·|•]\s+|\s+(?:Предложени|Срок|Цена|Стоимость|Дата)|$)", text)
        org = m[1] if m else ""
    if not org:
        for e in row.els():
            p = e.text()
            if p and p != title and title.find(p) < 0 and len(p) <= 160 and not DATE_RE.search(p) and not PRICE_RE.search(p) and \
                    re.search(r"(?:^|\s|«|\")(?:ОАО|ООО|РУП|КУП|УП|ЗАО|ГП|ОДО|ГУ|ГУО|УЗ|ИП)\b|Государственное|Учреждение|Предприятие|"
                              r"Министерств|исполнительн\w+ комитет|Заказчик\s*:", p):
                org = p
                break
    org = re.sub(r"^\s*(?:Заказчик|Организатор|Покупатель)\s*[:\-—]\s*", "", org)[:200]
    c = cell("status")
    status = c.text()[:60] if c else ""
    c = cell("procedure_type")
    ptype = c.text()[:80] if c else ""
    return {"number": number, "title": title[:600], "organization": org, "procedure_type": ptype, "status": status,
            "deadline": deadline, "price": price, "url": urljoin(base + "/", html.unescape(url)) if url and not url.startswith(("#", "javascript:")) else ""}


CLOSED = re.compile(r"отмен|заверш|подписани|не состоял|состоял|закрыт|архив|прекращ|итоги", re.I)


def is_open(t, today=None):
    """Приём предложений ещё идёт: статус не «отменён/завершён/подписание договора», срок не прошёл."""
    if CLOSED.search(t.get("status") or ""):
        return False
    m = re.match(r"(\d{2})\.(\d{2})\.(\d{4})", t.get("deadline") or "")
    return not m or f"{m[3]}{m[2]}{m[1]}" >= (today or datetime.now().strftime("%Y%m%d"))


def is_tender(t):
    if not t or ui_noise(t["title"]):
        return False
    sig = bool(t["number"]) + bool(t["deadline"]) + bool(t["price"])
    return bool(t["number"]) or sig >= 2 or (bool(t["deadline"]) and len(t["title"]) >= 30)


def parse_page(text, src, recipe=None):
    """-> (тендеры, способ, новый рецепт или None). Способ: recipe | auto | empty | none."""
    root = parse_html(text)
    if recipe:
        nodes = [e for e in root.els() if e.tag in ("tr", "li", "div", "article", "section", "dl")
                 and ((e.parent.path() if e.parent else "") + "|" + e.sig()) == recipe.get("key")]
        if nodes:
            cols = table_cols(nodes[0])
            out = [t for t in (extract_row(n, src["base"], cols) for n in nodes) if is_tender(t)]
            if out:
                return out, "recipe", None
    if page_empty(root.text()):
        return [], "empty", None
    for mr in (3, 1):
        for g in groups(root, mr)[:3]:
            if g["score"] < 2.0:
                break
            cols = table_cols(g["nodes"][0])
            out = [t for t in (extract_row(n, src["base"], cols) for n in g["nodes"]) if is_tender(t)]
            if len(out) >= max(1, int(g["n"] * 0.4)):
                return out, "auto", {"key": g["key"], "at": int(time.time())} if mr == 3 else None
    return [], "none", None


# ---------------- сеть и хранилище ----------------

def fetch(src, query):
    fx = os.environ.get("DEWIAR_TENDERS_FIXTURES")
    if fx:
        p = Path(fx) / f"{src['id']}.html"
        return p.read_text(encoding="utf-8") if p.is_file() else ""
    url = src["url"].replace("{QUERY}", quote_plus(query))
    cl = client(src)
    last = None
    for i in range(2):
        try:
            r = cl.get(url)
            if r.status_code in (429,) or r.status_code >= 500:
                last = f"площадка ответила {r.status_code}"
                time.sleep(3 if r.status_code == 429 else 2)
                continue
            r.raise_for_status()
            return r.text
        except Exception as e:  # noqa: BLE001
            last = str(e)
            time.sleep(1.5)
    raise RuntimeError(last or "не открылась")


_CL = {}


def client(src):
    """Один клиент на площадку за проверку: куки, которые площадка ставит на главной (защита от роботов), живут между
    запросами — как curl с cookie-файлом в модуле владельца. Сначала — главная страница."""
    import httpx
    if src["id"] not in _CL:
        cl = httpx.Client(timeout=25, follow_redirects=True, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.6"})
        try:
            cl.get(src["base"] + "/")
        except Exception:  # noqa: BLE001
            pass
        _CL[src["id"]] = cl
    return _CL[src["id"]]


def load(p, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def save(p, data):
    tmp = p.with_suffix(".part")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(p)


def thash(t, src):
    key = (src + "|" + (t.get("number") or "") + "|" + (t.get("url") or "") + "|" + re.sub(r"\W+", " ", t.get("title", "").lower())[:200])
    return hashlib.md5(key.encode()).hexdigest()[:16]


def sources(s):
    out = [x for x in SOURCES if s.get(x["toggle"], True) not in (False, "false", "0", 0)]
    own = str(s.get("own_url") or "").strip()
    if own.startswith(("http://", "https://")) and "{QUERY}" in own:
        m = re.match(r"(https?://[^/]+)", own)
        out.append({"id": "own", "name": m[1].split("//")[1], "base": m[1], "url": own})
    return out


def scan(query=""):
    s = settings()
    queries = plist(query) or plist(s.get("queries"))
    if not queries:
        return {"error": "Нет запросов: впишите в настройках плагина «Тендеры», что искать (например: видеонаблюдение; защита информации)."}
    plus, minus = plist(s.get("plus")), plist(s.get("minus"))
    store, recipes = load(STORE, {"items": {}, "gone": []}), load(RECIPES, {})
    items, gone = store["items"], set(store.get("gone") or [])
    found, report = {}, []
    for src in sources(s):
        n_src, why = set(), ""
        for q in queries:
            try:
                page = fetch(src, q)
            except Exception as e:  # noqa: BLE001
                why = f"не открылась: {str(e)[:120]}"
                break
            rows, how, learn = parse_page(page, src, recipes.get(src["id"]))
            if learn:
                recipes[src["id"]] = learn
            if how == "none" and page.strip():
                why = "выдача не распознана"
            for t in rows:
                if not is_open(t):
                    continue
                h = thash(t, src["id"])
                if h in gone:
                    continue
                cur = found.get(h) or dict(t, id=h, source=src["name"], found_by=[])
                if q not in cur["found_by"]:
                    cur["found_by"].append(q)
                found[h] = cur
                n_src.add(h)
            if not os.environ.get("DEWIAR_TENDERS_FIXTURES"):
                time.sleep(0.7)                              # вежливо: не чаще запроса в 0,7 с к площадке
        report.append({"source": src["name"], "found": len(n_src), **({"problem": why} if why else {})})
    for c in _CL.values():
        c.close()
    _CL.clear()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    new = []
    for h, t in found.items():
        old = items.get(h)
        if old:
            t["found_by"] = sorted(set(old.get("found_by") or []) | set(t["found_by"]))
            t["first_seen"], t["seen"] = old.get("first_seen") or now, old.get("seen", False)
        else:
            t["first_seen"], t["seen"] = now, False
        t["score"], t["terms"], t["minus"] = score(t, queries, plus, minus)
        items[h] = t
        if not old:
            new.append(t)
    save(STORE, {"items": items, "gone": sorted(gone), "last_scan": now})
    save(RECIPES, recipes)
    try:
        floor = int(s.get("min_score") or 0)
    except ValueError:
        floor = 0
    good = sorted([t for t in new if t["score"] >= floor and not t["minus"]], key=lambda t: -t["score"])
    return {"new": len(new), "new_good": [brief(t) for t in good[:15]], "below_score": len(new) - len(good), "sources": report,
            "queries": queries, "min_score": floor}


def brief(t):
    return {k: t.get(k) for k in ("id", "title", "organization", "deadline", "price", "score", "url", "source", "number") if t.get(k) not in (None, "")}


def listing(only_new=True, min_score=0, q="", limit=20):
    items = list(load(STORE, {"items": {}})["items"].values())
    if only_new:
        items = [t for t in items if not t.get("seen")]
    if min_score:
        items = [t for t in items if t.get("score", 0) >= min_score]
    if q:
        qs = stems(q)
        items = [t for t in items if phrase_hit(qs, set(stems(t.get("title", "") + " " + t.get("organization", "")))) >= 0.6]
    items.sort(key=lambda t: (-t.get("score", 0), t.get("first_seen", "")), reverse=False)
    return {"total": len(items), "items": [brief(t) for t in items[:max(1, min(50, int(limit or 20)))]]}


def mark(ids, how):
    st = load(STORE, {"items": {}, "gone": []})
    ids = list(st["items"]) if ids in ("all", ["all"]) else [str(x) for x in (ids or [])]
    n = 0
    for i in ids:
        if i in st["items"]:
            if how == "delete":
                st["items"].pop(i)
                st.setdefault("gone", []).append(i)
            else:
                st["items"][i]["seen"] = True
            n += 1
    save(STORE, st)
    return {"marked": n, "how": how}


# ---------------- MCP ----------------

TOOLS = [
    {"name": "tenders_scan", "description": "Найти новые тендеры на площадках (goszakupki.by, icetrade.by и своя) по запросам из настроек "
     "плагина или по query. Возвращает новые с баллом от порога: название, заказчик, срок, цена, ссылка.",
     "annotations": {"readOnlyHint": True, "title": "Найти новые тендеры"},
     "inputSchema": {"type": "object", "properties": {"query": {"type": "string", "description": "свой запрос вместо настроек (необязательно)"}}}},
    {"name": "tenders_list", "description": "Найденные тендеры из учёта: непросмотренные (only_new) или все, с баллом от min_score, по словам q.",
     "annotations": {"readOnlyHint": True, "title": "Список тендеров"},
     "inputSchema": {"type": "object", "properties": {"only_new": {"type": "boolean"}, "min_score": {"type": "integer"},
                                                      "q": {"type": "string"}, "limit": {"type": "integer"}}}},
    {"name": "tenders_mark", "description": "Отметить тендеры просмотренными (seen) или убрать из учёта навсегда (delete). ids — список id или «all».",
     "annotations": {"readOnlyHint": True, "title": "Отметить тендеры"},
     "inputSchema": {"type": "object", "properties": {"ids": {"type": "array", "items": {"type": "string"}},
                                                      "how": {"type": "string", "enum": ["seen", "delete"]}}, "required": ["ids"]}},
]


def call(name, a):
    if name == "tenders_scan":
        return scan(str(a.get("query") or ""))
    if name == "tenders_list":
        return listing(a.get("only_new", True) is not False, int(a.get("min_score") or 0), str(a.get("q") or ""), a.get("limit") or 20)
    if name == "tenders_mark":
        return mark(a.get("ids"), "delete" if a.get("how") == "delete" else "seen")
    raise ValueError("нет такого действия")


def handle(msg):
    m, i = msg.get("method"), msg.get("id")
    if i is None:
        return None
    if m == "initialize":
        return {"jsonrpc": "2.0", "id": i, "result": {"protocolVersion": (msg.get("params") or {}).get("protocolVersion", "2024-11-05"),
                                                       "capabilities": {"tools": {}}, "serverInfo": {"name": "dewiar-tenders", "version": "1.0"}}}
    if m == "tools/list":
        return {"jsonrpc": "2.0", "id": i, "result": {"tools": TOOLS}}
    if m == "tools/call":
        p = msg.get("params") or {}
        try:
            res = call(p.get("name"), p.get("arguments") or {})
            return {"jsonrpc": "2.0", "id": i, "result": {"content": [{"type": "text", "text": json.dumps(res, ensure_ascii=False)}]}}
        except Exception as e:  # noqa: BLE001
            return {"jsonrpc": "2.0", "id": i, "result": {"isError": True, "content": [{"type": "text", "text": f"Ошибка: {e}"}]}}
    if m == "ping":
        return {"jsonrpc": "2.0", "id": i, "result": {}}
    return {"jsonrpc": "2.0", "id": i, "error": {"code": -32601, "message": "нет такого метода"}}


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            r = handle(json.loads(line))
        except ValueError:
            continue
        if r is not None:
            sys.stdout.write(json.dumps(r, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
