"""Части страницы сайта (sites_render.py): экранирование и ссылки (только https://, mailto:, tel:, якоря, свои
страницы), строки текста, контекст сборки (Ctx), шапка, меню, кнопки, контакты, ссылки на документы
сайта (реквизиты, политика)."""

import html
import re
import sites_kit as K
import urllib.parse

from sites_art import art_svg
from sites_style import colors


E = html.escape


# ---------- текст ----------


# ссылки в тексте разделов (владелец 16.11, снимок: «Лира на сайтах ссылки показывает в виде текста» — модель написала в
# текст раздела <a href="…">читайте статью</a>, а страница показала это кодом): <a href>, [текст](адрес) и голый адрес —
# настоящей ссылкой; адрес — только https/mailto/tel или свой (#раздел, страница.html, /blog/…); остальное — как было, текстом
LINK_RX = re.compile(r"""<a\s[^>]*?href\s*=\s*["']([^"']{1,500})["'][^>]*>(.*?)</a\s*>"""
                     r"|\[([^\]\n]{1,200})\]\(([^)\s]{1,500})\)"
                     r"""|(?<![\w/="'])((?:https?://|www\.)[^\s<>"'«»]{3,500})""", re.I | re.S)


def own_url(u):
    """Адрес на своём сайте: #раздел, about.html, /blog/статья — без схемы и без «..»."""
    u = str(u or "").strip()
    return u if re.match(r"^[#/]?[\w\-./#?=&%]{1,300}$", u) and ":" not in u and ".." not in u and not u.startswith("//") else ""


def inline(x):
    """Строка текста -> HTML: всё экранировано, ссылки — ссылками."""
    x = str(x or "")
    out, pos = [], 0
    for m in LINK_RX.finditer(x):
        out.append(E(x[pos:m.start()]))
        tail = ""
        if m.group(1) is not None:
            href, txt = m.group(1), re.sub(r"<[^>]*>", "", m.group(2) or "").strip()
        elif m.group(3) is not None:
            href, txt = m.group(4), m.group(3).strip()
        else:
            raw = m.group(5)
            href = raw.rstrip(".,;:!?)")
            tail, txt = raw[len(href):], href
        h = href.strip()
        u = own_url(h) if re.match(r"^[#/]|^[\w-]+\.html?([#?].*)?$", h) else safe_url(h)
        if u and txt:
            ext = u.startswith(("https://", "http://"))
            out.append(f'<a href="{E(u)}"' + (' target="_blank" rel="noopener"' if ext else "") + f">{E(txt)}</a>")
        else:
            out.append(E(m.group(0)))
        out.append(E(tail))
        pos = m.end()
    out.append(E(x[pos:]))
    return "".join(out)


def para(text, cls=""):
    """Абзацы: пустая строка — новый <p>, перенос строки — <br>. Всё экранировано, ссылки — ссылками (inline)."""
    t = str(text or "").strip()
    if not t:
        return ""
    c = f' class="{cls}"' if cls else ""
    return "".join(f"<p{c}>" + "<br>".join(inline(x) for x in p.split("\n")) + "</p>" for p in re.split(r"\n\s*\n", t) if p.strip())


def one(text):
    return E(re.sub(r"\s+", " ", str(text or "")).strip())


def opt(tag, val, cls=""):
    """<tag class=…>текст</tag>, если текст есть; иначе пусто."""
    if not str(val or "").strip():
        return ""
    open_tag = f'<{tag} class="{cls}">' if cls else f"<{tag}>"
    return open_tag + one(val) + f"</{tag}>"


def link(h, t, cls=""):
    c = f' class="{cls}"' if cls else ""
    return f'<a{c} href="{E(h)}" rel="noopener">{t}</a>'


def slug_of(page, i):
    return "index" if i == 0 else (page.get("slug") or f"page{i}")


def safe_url(u):
    u = str(u or "").strip()
    if re.match(r"^(https://|mailto:|tel:)[^\s\"'<>]{1,500}$", u, re.I):
        return u
    if re.match(r"^http://[^\s\"'<>]{1,500}$", u, re.I):
        return "https://" + u[7:]
    if re.match(r"^[a-z0-9.-]+\.[a-z]{2,}(/[^\s\"'<>]*)?$", u, re.I):
        return "https://" + u
    return ""


def phone_href(p):
    d = re.sub(r"[^\d+]", "", str(p or ""))
    return f"tel:{d}" if len(re.sub(r"\D", "", d)) >= 5 else ""


def messenger_href(kind, v):
    v = str(v or "").strip()
    if not v:
        return ""
    if kind == "telegram":
        m = re.search(r"(?:t\.me/|@)?([A-Za-z0-9_]{4,32})$", v)
        return f"https://t.me/{m.group(1)}" if m else safe_url(v)
    if kind == "whatsapp":
        d = re.sub(r"\D", "", v)
        return f"https://wa.me/{d}" if len(d) >= 8 else safe_url(v)
    if kind == "email":
        return f"mailto:{v}" if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", v) else ""
    if kind == "phone":
        return phone_href(v)
    if kind == "vk" and not v.startswith("http"):
        return "https://vk.com/" + v.lstrip("@/")
    if kind == "instagram" and not v.startswith("http"):
        return "https://instagram.com/" + v.lstrip("@/")
    return safe_url(v)


def map_href(address):
    return "https://yandex.ru/maps/?text=" + urllib.parse.quote(str(address or ""))


# ---------- части страницы ----------


class Ctx:
    """Что нужно блокам: сайт, режим, картинки, страницы и якоря (куда ведут кнопки)."""

    def __init__(self, site, mode, page_i, images=None, base_url=""):
        self.site, self.mode, self.page_i = site, mode, page_i
        self.pal = colors(site.get("theme"))
        self.images = images or {}                 # id картинки -> data: (предпросмотр) или путь img/…
        self.base_url = base_url
        self.pages = site.get("pages") or []
        self.art = (site.get("theme") or {}).get("art") or "beans"
        self.contacts = site.get("contacts") or {}
        self.legal = legal_of(site)                 # подвал и документы (0.87)
        self.anchors = {}                           # якорь -> индекс страницы
        for i, pg in enumerate(self.pages):
            for j, b in enumerate(pg.get("blocks") or []):
                self.anchors.setdefault(anchor(b, j), i)

    def page_file(self, i):
        return slug_of(self.pages[i], i) + ".html"

    def href(self, to):
        """Куда ведёт кнопка: lead, contacts, phone, #якорь, page:slug, https://…"""
        to = str(to or "lead").strip()
        here = self.page_i

        def at(anc):
            i = self.anchors.get(anc)
            if i is None:
                return None
            return f"#{anc}" if i == here else f"{self.page_file(i)}#{anc}"
        if to == "phone":
            return phone_href(self.contacts.get("phone")) or at("lead") or at("contacts") or "#"
        if to in ("lead", "contacts"):
            return at(to) or at("contacts") or at("lead") or (phone_href(self.contacts.get("phone")) or "#")
        if to.startswith("#"):
            return at(to[1:]) or "#"
        if to.startswith("page:"):
            for i, pg in enumerate(self.pages):
                if slug_of(pg, i) == to[5:] or pg.get("slug") == to[5:]:
                    return self.page_file(i)
            return "#"
        return safe_url(to) or at("lead") or "#"

    def img(self, ref):
        return self.images.get(str(ref or ""), "")

    def media(self, ref, seed, cls="media", alt=""):
        src = self.img(ref)
        if src:
            return f'<div class="{cls}"><img src="{E(src)}" alt="{E(alt)}" loading="lazy"></div>'
        return f'<div class="{cls}">{art_svg(self.art, self.pal, seed, mark=(self.site.get("logo") or {}).get("mark", ""))}</div>'


def anchor(b, j):
    t = b.get("type")
    if t in ("lead", "contacts"):
        return t
    a = re.sub(r"[^a-z0-9_-]", "", str(b.get("id") or "").lower())
    return a or f"b{j}"


def btns(b, c, ghost2=True):
    o = []
    if b.get("button"):
        o.append(f'<a class="btn" href="{E(c.href(b.get("button_to") or "lead"))}">{one(b["button"])}</a>')
    if b.get("button2"):
        o.append(f'<a class="btn ghost" href="{E(c.href(b.get("button2_to") or "contacts"))}">{one(b["button2"])}</a>')
    return f'<div class="btns">{"".join(o)}</div>' if o else ""


def head2(b, extra=""):
    t, tx = b.get("title"), b.get("text")
    if not t and not tx:
        return ""
    return f'<div class="hd2"><div>{f"<h2>{one(t)}</h2>" if t else ""}{para(tx, "lede") if tx else ""}</div>{extra}</div>'


def items(b, c, people=False):
    out = []
    for x in b.get("items") or []:
        if not isinstance(x, dict):
            continue
        if x.get("todo") and c.mode != "preview":
            continue                                  # заглушки людей не публикуем
        out.append(x)
    return out


def logo_html(site, cls="logo", href="index.html"):
    lg = site.get("logo") or {}
    name = one(lg.get("text") or site.get("name") or "Сайт")
    st = lg.get("style") or "plain"
    if lg.get("svg"):
        mk = f'<span class="lg-own">{lg["svg"]}</span>'
    elif st == "badge":
        mk = f'<span class="lg-badge">{K.mark_svg(lg.get("mark") or "spark")}</span>'
    elif st == "mono":
        mk = f'<span class="lg-mono">{E((lg.get("text") or site.get("name") or "С").strip()[:1].upper())}</span>'
    elif st == "text":
        mk = ""
    else:
        mk = f'<span class="lg-plain">{K.mark_svg(lg.get("mark") or "spark", 30)}</span>'
    tag = one(site.get("tagline") or "")
    return f'<a class="{cls}" href="{href}" aria-label="{name} — на главную">{mk}<span><b>{name}</b>{f"<small>{tag}</small>" if tag else ""}</span></a>'


def menu_items(site, c):
    """Меню: страницы (если их несколько) или разделы главной с подписью nav."""
    pages = c.pages
    if len(pages) > 1:
        return [(pg.get("title") or f"Страница {i + 1}", c.page_file(i), i == c.page_i) for i, pg in enumerate(pages)]
    out = []
    pre = "" if c.page_i == 0 or not pages else c.page_file(0)     # со страницы документа — на разделы главной
    for j, b in enumerate(pages[0].get("blocks") or [] if pages else []):
        if b.get("nav") and not b.get("hidden"):
            out.append((b["nav"], f"{pre}#{anchor(b, j)}", False))
    return out[:7]


def menu_with_blog(site, c):
    """Меню + «Статьи», когда на сайте есть опубликованные статьи (0.93; в предпросмотре студии — нет: /blog/ там не открыть)."""
    m = menu_items(site, c)
    if c.mode != "preview" and ((site.get("blog") or {}).get("live") or 0) > 0:
        m = m[:7] + [("Статьи", "/blog/", c.page_i == -2)]
    return m


def header(site, c):
    m = menu_with_blog(site, c)
    links = "".join(f'<a href="{E(h)}"{" aria-current=page" if cur else ""}>{one(t)}</a>' for t, h, cur in m)
    cta_t = ((site.get("menu") or {}).get("cta") or "").strip()
    has_lead = "lead" in c.anchors
    if not cta_t:
        cta_t = "Оставить заявку" if has_lead else ""
    cta = f'<a class="btn hdr-cta" href="{E(c.href("lead"))}">{one(cta_t)}</a>' if cta_t and (has_lead or c.contacts.get("phone")) else ""
    mob = (f'<details class="mnav"><summary aria-label="Меню"><i></i>Меню</summary><nav>{links}'
           f'{cta.replace("btn hdr-cta", "btn") if cta else ""}</nav></details>') if (links or cta) else ""
    return f'<header class="hdr"><div class="w">{logo_html(site, href=c.page_file(0))}<nav class="nav" aria-label="Разделы">{links}</nav>{cta}{mob}</div></header>'


CT_ICONS = {"phone": "chat", "email": "pen", "address": "pin", "hours": "clock", "telegram": "chat", "whatsapp": "chat", "vk": "star",
            "max": "chat", "instagram": "camera", "site": "home"}


def contact_list(c, keys=None):
    ct = c.contacts
    li = []
    for k in keys or ("phone", "email", "address", "hours", "telegram", "whatsapp", "max", "vk", "instagram", "site"):
        v = str(ct.get(k) or "").strip()
        if not v:
            continue
        h = map_href(v) if k == "address" else ("" if k == "hours" else messenger_href(k, v))
        val = f'<a href="{E(h)}"{" rel=noopener" if h.startswith("https") else ""}>{one(v)}</a>' if h else one(v)
        li.append(f'<li>{K.mark_svg(CT_ICONS.get(k, "spark"))}<span><small>{E(K.CONTACT_KEYS[k])}</small>{val}</span></li>')
    return f'<ul class="ct-list">{"".join(li)}</ul>' if li else ""


# ---------- подвал и документы (0.87) ----------


def digits(v, n=15):
    return re.sub(r"\D", "", str(v or ""))[:n]


def doc_slug(site, key):
    """Адрес страницы документа (без .html): oferta, privacy, soglasie, terms; занят страницей сайта — doc-…"""
    base = K.LEGAL_DOCS[key]["slug"]
    taken = {slug_of(pg, i) for i, pg in enumerate(site.get("pages") or [])}
    return base if base not in taken else f"doc-{base}"


def legal_of(site):
    """Что из «Подвала и документов» есть на сайте -> {req: [(вид, текст, ссылка)], org, docs: [(ключ, подпись, ссылка)], links: […]}.
    Документ «свой текст» — своя страница (ключ.html), «ссылка» — только https (safe_url); пустое не показываем."""
    lg = site.get("legal") or {}
    if not isinstance(lg, dict):
        lg = {}
    org = re.sub(r"\s+", " ", str(lg.get("org") or "")).strip()
    inn, ogrn = digits(lg.get("inn"), 12), digits(lg.get("ogrn"), 15)
    req = []
    if inn:
        req.append(("inn", f"ИНН {inn}", ""))
    if ogrn:
        req.append(("ogrn", f"{'ОГРНИП' if len(ogrn) == 15 else 'ОГРН'} {ogrn}", ""))
    if str(lg.get("address") or "").strip():
        req.append(("address", str(lg["address"]).strip(), ""))
    if str(lg.get("phone") or "").strip():
        req.append(("phone", str(lg["phone"]).strip(), phone_href(lg["phone"])))
    if str(lg.get("email") or "").strip():
        em = str(lg["email"]).strip()
        req.append(("email", em, f"mailto:{em}" if re.fullmatch(r"[^@\s<>\"']+@[^@\s<>\"']+\.[^@\s<>\"']+", em) else ""))
    docs = []
    for key, meta in K.LEGAL_DOCS.items():
        d = (lg.get("docs") or {}).get(key) or {}
        if not isinstance(d, dict):
            continue
        if d.get("mode") == "text" and str(d.get("text") or "").strip():
            docs.append((key, meta["short"], doc_slug(site, key) + ".html"))
        elif d.get("mode") == "link" and safe_url(d.get("url")):
            docs.append((key, meta["short"], safe_url(d.get("url"))))
    links = []
    for x in (lg.get("links") or [])[:K.LEGAL_LINKS_MAX]:
        if isinstance(x, dict) and str(x.get("title") or "").strip() and safe_url(x.get("url")):
            links.append(("", str(x["title"]).strip()[:80], safe_url(x["url"])))
    return {"org": org, "req": req, "docs": docs + links}


def legal_href(site, key):
    """Ссылка на документ (ключ из LEGAL_DOCS) или ""."""
    return next((h for k, _, h in legal_of(site)["docs"] if k == key), "")
