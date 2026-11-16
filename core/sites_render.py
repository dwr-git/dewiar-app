"""«Сайты»: JSON сайта -> статичный адаптивный HTML + CSS (sites_kit — детали, sites.py — работа с сайтами).

Режимы (mode):
  • "preview" — для студии: одна страница целиком (CSS внутри), картинки и шрифты (из ui/assets/fonts) — data:, у блоков
    data-b — щелчок по блоку в предпросмотре выбирает его в редакторе; маленький скрипт предпросмотра (только в студии);
    заглушки (todo, пустая галерея) видны пунктиром.
  • "publish" — файлы для dewiar.pro: страницы *.html, style.css, fonts/*.woff2, img/*; ни одного <script> (кроме
    application/ld+json — данные для поисковиков), форма заявки — POST /__lead (ловушка-поле для ботов), в подвале —
    «Пожаловаться» (/__report). Заглушки людей (todo) и пустые галереи не публикуются.
  • "export" — то же, что publish, для просмотра с диска (форма никуда не отправляет).

Весь текст экранируется; ссылки — только https://, mailto:, tel:, якоря и свои страницы."""

import base64
import html
import json
import math
import re
import urllib.parse
from datetime import datetime

import sites_kit as K

# сборка сайта разложена по модулям (чистое ядро, 1.0.16 — docs/CORE_PLAN.md): текст и части страницы — sites_parts,
# цвет и CSS — sites_style, узоры вместо фото — sites_art, блоки — sites_blocks; здесь — подвал, документы и страница.
# Все прежние имена — по-прежнему sites_render.<имя>
from sites_parts import (  # noqa: F401,E402 — прежние имена sites_render.* на месте
    anchor, btns, contact_list, CT_ICONS, Ctx, digits, doc_slug, E, head2, header, inline, items, legal_href,
    legal_of, link, LINK_RX, logo_html, map_href, menu_items, menu_with_blog, messenger_href, one, opt, own_url,
    para, phone_href, safe_url, slug_of)
from sites_style import (  # noqa: F401,E402 — прежние имена sites_render.* на месте
    ATELIER_CSS, AV_CSS, BASE_CSS, bg_css, bg_of, colors, contrast, css, _FONT_DATA, _font_data, FONT_DIR,
    font_faces, font_files, _hex, lum, mix, NEW_CSS, POSTER_CSS, PREVIEW_CSS, PREVIEW_JS, readable_on, _rgb,
    style_of, tone_vars)
from sites_art import (  # noqa: F401,E402 — прежние имена sites_render.* на месте
    art_svg, map_svg, _rand, _seed)
from sites_blocks import (  # noqa: F401,E402 — прежние имена sites_render.* на месте
    b_about, b_bars, b_cases, b_contacts, b_cta, b_duo, b_faq, b_features, b_gallery, b_hero, b_hub, b_lead, b_links,
    b_prices, b_products, b_reviews, b_schedule, b_services, b_stats, b_steps, b_team, b_text, b_ticker, b_video,
    block_html, case_viz, EXTRA_CLS, gallery_pairs, initials, kin_art, KIN_PATHS, kin_title, lead_form, num_of,
    pd_consent, price_tabs, RENDER, snake, TAB_MAX, video_embed, VIDEO_FILE)


# ---------- подвал и документы (0.87) ----------


def _a(h, text):
    """Ссылка (свои страницы, https, mailto, tel — их уже проверили) или просто текст."""
    return f'<a href="{E(h)}"{" rel=noopener" if h.startswith("https:") else ""}>{text}</a>' if h else text


def legal_html(site, c):
    """Строка подвала: наименование, ИНН, ОГРН, адрес, телефон, почта — и документы. Ничего не задано — пусто."""
    L = c.legal
    if not (L["org"] or L["req"] or L["docs"]):
        return ""
    req = "".join(f'<li class="lg-{k}">{_a(h, one(t))}</li>' for k, t, h in L["req"])
    who = (f'<p class="lg-org">{one(L["org"])}</p>' if L["org"] else "") + (f'<ul class="lg-req">{req}</ul>' if req else "")
    docs = "".join(f"<li>{_a(h, one(t))}</li>" for _, t, h in L["docs"])
    nav = '<nav aria-label="Документы"><ul class="lg-docs">' + docs + "</ul></nav>" if docs else ""
    return '<div class="lgl">' + (f"<div>{who}</div>" if who else "") + nav + "</div>"


def footer(site, c):
    m = menu_items(site, c)
    links = "".join(f'<a href="{E(h)}">{one(t)}</a>' for t, h, _ in m)
    year = datetime.now().year
    report = '<a href="/__report">Пожаловаться на сайт</a>' if c.mode == "publish" else '<a href="#">Пожаловаться на сайт</a>'
    return (f'<footer class="ftr"><div class="w"><div>{logo_html(site, href=c.page_file(0))}'
            f'</div><nav aria-label="Разделы">{links}</nav><div>{contact_list(c, ("phone", "email", "address", "telegram"))}</div>{legal_html(site, c)}'
            f'<div class="bot"><span>© {year} {one(site.get("name"))}</span><span>{report}<a href="https://dewiar.pro" rel="noopener">Сайт сделан в Dewiar</a></span></div></div></footer>')


def doc_text(text):
    """Текст документа -> HTML: пустая строка — новый абзац; «## …» или короткая строка «1. Общие положения» — заголовок;
    строки «- …» / «• …» — список. Всё экранировано."""
    out = []
    for blk in re.split(r"\n\s*\n", str(text or "").replace("\r", "").strip()):
        lines = [x.rstrip() for x in blk.strip().split("\n") if x.strip()]
        if not lines:
            continue
        if len(lines) == 1 and (lines[0].startswith("#") or (re.match(r"^\d+(\.\d+)*\.?\s+\S", lines[0]) and len(lines[0]) <= 110
                                                           and not re.search(r"[.;:,]$", lines[0]))):
            out.append(f"<h2>{one(lines[0].lstrip('#').strip())}</h2>")
            continue
        if lines[0].startswith("#"):
            out.append(f"<h2>{one(lines[0].lstrip('#').strip())}</h2>")
            lines = lines[1:]
        items, para_lines = [], []
        for ln in lines:
            mm = re.match(r"^\s*[-•—*]\s+(.*)$", ln)
            if mm:
                if para_lines:
                    out.append("<p>" + "<br>".join(inline(x) for x in para_lines) + "</p>")
                    para_lines = []
                items.append(f"<li>{inline(mm.group(1))}</li>")
            else:
                if items:
                    out.append("<ul>" + "".join(items) + "</ul>")
                    items = []
                para_lines.append(ln)
        if para_lines:
            out.append("<p>" + "<br>".join(inline(x) for x in para_lines) + "</p>")
        if items:
            out.append("<ul>" + "".join(items) + "</ul>")
    return "".join(out)


RU_MONTHS = ("января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря")


def doc_main(site, key, c):
    meta = K.LEGAL_DOCS[key]
    d = ((site.get("legal") or {}).get("docs") or {}).get(key) or {}
    ts = d.get("ts") or site.get("updated")
    when = ""
    if ts:
        dt = datetime.fromtimestamp(int(ts))
        when = f'<p class="doc-ed">Редакция от {dt.day} {RU_MONTHS[dt.month - 1]} {dt.year} г.</p>'
    L = c.legal
    req = "".join(f"<li>{_a(h, one(t))}</li>" for _, t, h in L["req"])
    card = (f'<aside class="doc-req card"><h2>Реквизиты</h2>{opt("p", L["org"], "lg-org")}{f"<ul>{req}</ul>" if req else ""}</aside>'
            if (L["org"] or req) else "")
    return (f'<section class="s t-base doc" id="doc"><div class="w"><a class="doc-back" href="{E(c.page_file(0))}">На главную</a>'
            f'<h1>{E(meta["title"])}</h1>{when}<div class="doc-text">{doc_text(d.get("text"))}</div>{card}</div></section>')


# ---------- страница ----------
def seo_title(site, i):
    pg = (site.get("pages") or [{}])[i]
    if pg.get("seo_title"):
        return str(pg["seo_title"])
    name, tag = site.get("name") or "Сайт", site.get("tagline") or ""
    if i == 0:
        return f"{name} — {tag}" if tag else name
    return f"{pg.get('title') or 'Страница'} — {name}"


def seo_desc(site, i):
    pg = (site.get("pages") or [{}])[i]
    d = pg.get("description") or (site.get("seo") or {}).get("description") if i == 0 else pg.get("description")
    if d:
        return re.sub(r"\s+", " ", str(d)).strip()[:300]
    for b in pg.get("blocks") or []:
        if b.get("text"):
            return re.sub(r"\s+", " ", str(b["text"])).strip()[:160]
    return ""


def favicon(site):
    p = colors(site.get("theme"))
    lg = site.get("logo") or {}
    body = (MARKS_PATH(lg.get("mark")) if lg.get("style") != "mono" else
            f'<text x="12" y="16.5" text-anchor="middle" font-family="Arial" font-weight="700" font-size="13" fill="{p["accent_ink"]}" stroke="none">'
            f'{E((lg.get("text") or site.get("name") or "С")[:1].upper())}</text>')
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="-4 -4 32 32"><rect x="-4" y="-4" width="32" height="32" rx="9" fill="{p["accent"]}"/>'
           f'<g fill="none" stroke="{p["accent_ink"]}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{body}</g></svg>')
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def MARKS_PATH(name):
    return (K.MARKS.get(name or "") or K.MARKS["spark"])[1]


def jsonld(site, base_url):
    ct = site.get("contacts") or {}
    d = {"@context": "https://schema.org", "@type": "LocalBusiness" if ct.get("address") else "Organization", "name": site.get("name") or ""}
    if site.get("tagline"):
        d["description"] = site["tagline"]
    if base_url:
        d["url"] = base_url
    if ct.get("phone"):
        d["telephone"] = ct["phone"]
    if ct.get("email"):
        d["email"] = ct["email"]
    if ct.get("address"):
        d["address"] = ct["address"]
    if ct.get("hours"):
        d["openingHours"] = ct["hours"]
    return json.dumps(d, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def doc_keys(site):
    """Документы «своим текстом» — у каждого своя страница сайта."""
    docs = (site.get("legal") or {}).get("docs") or {}
    return [k for k in K.LEGAL_DOCS if isinstance(docs.get(k), dict) and docs[k].get("mode") == "text" and str(docs[k].get("text") or "").strip()]


def page_html(site, i=0, mode="preview", images=None, base_url="", css_text=None, doc="", blog=False):
    """Одна страница сайта. preview — CSS внутри; publish/export — ссылка на style.css. doc — страница документа
    («Подвал и документы»: оферта, политика…) в стиле сайта, с той же шапкой и подвалом."""
    pages = site.get("pages") or []
    if not pages:
        pages = site["pages"] = [{"title": "Главная", "blocks": []}]
    doc = doc if doc in doc_keys(site) else ""
    i = -2 if blog else -1 if doc else max(0, min(i, len(pages) - 1))
    c = Ctx(site, mode, i, images, base_url)
    th = site.get("theme") or {}
    fonts = K.FONTS.get(th.get("fonts") or "", K.FONTS["warm"])
    if blog:                      # шаблон статей (0.93): сервер подставляет заголовок, описание, адрес и саму статью
        body, title, desc, url = "{{dw:main}}", "{{dw:title}}", "{{dw:desc}}", "{{dw:url}}"
    elif doc:
        body = doc_main(site, doc, c)
        title = f'{K.LEGAL_DOCS[doc]["title"]} — {site.get("name") or "Сайт"}'
        desc = title
        url = (base_url.rstrip("/") + "/" + doc_slug(site, doc) + ".html") if base_url else ""
    else:
        body = "".join(block_html(b, j, c) for j, b in enumerate(pages[i].get("blocks") or []))
        title, desc = seo_title(site, i), seo_desc(site, i)
        url = (base_url.rstrip("/") + "/" + ("" if i == 0 else c.page_file(i))) if base_url else ""
    og_img = ""
    for b in (pages[i].get("blocks") or []) if not doc and not blog else []:
        if b.get("image") and c.img(b["image"]) and not c.img(b["image"]).startswith("data:"):
            og_img = (base_url.rstrip("/") + "/" + c.img(b["image"])) if base_url else ""
            break
    p = colors(th)
    head = [f'<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">',
            f"<title>{E(title)}</title>", f'<meta name="description" content="{E(desc)}">' if desc else "",
            f'<meta name="theme-color" content="{p["bg"]}">', f'<link rel="icon" href="{favicon(site)}">',
            f'<meta property="og:type" content="website"><meta property="og:locale" content="ru_RU">',
            f'<meta property="og:site_name" content="{E(site.get("name") or "")}"><meta property="og:title" content="{E(title)}">',
            f'<meta property="og:description" content="{E(desc)}">' if desc else "",
            f'<meta property="og:url" content="{E(url)}"><link rel="canonical" href="{E(url)}">' if url else "",
            f'<meta property="og:image" content="{E(og_img)}">' if og_img else "",
            f'<meta name="twitter:card" content="{"summary_large_image" if og_img else "summary"}">']
    if mode == "preview":
        head.append(f"<style>{css_text if css_text is not None else css(site, 'preview')}</style>")
    else:
        head.append('<link rel="stylesheet" href="style.css">')
        if i == 0:
            head.append(f'<script type="application/ld+json">{jsonld(site, base_url)}</script>')
            seo = site.get("seo") or {}             # 0.93: подтверждение в Яндекс Вебмастере и Google Search Console
            for name, k in (("yandex-verification", "verify_yandex"), ("google-site-verification", "verify_google")):
                if re.fullmatch(r"[A-Za-z0-9_\-]{8,100}", str(seo.get(k) or "")):
                    head.append(f'<meta name="{name}" content="{E(seo[k])}">')
    cls = " ".join(x for x in ("pv" if mode == "preview" else "", "it" if fonts.get("italic") else "") if x)
    cls_attr = f' class="{cls}"' if cls else ""
    menu = (site.get("menu") or {}).get("style") or "top"
    if blog:
        head = [h.replace('og:type" content="website"', 'og:type" content="article"') for h in head]
    out = (f'<!doctype html><html lang="ru"{cls_attr}><head>{"".join(h for h in head if h)}</head>'
            f'<body class="m-{E(menu)}{" many" if len(menu_items(site, c)) > 5 else ""} sty-{E(style_of(site))}">{header(site, c)}<main>{body}</main>{footer(site, c)}'
            f'{PREVIEW_JS if mode == "preview" else ""}</body></html>')
    if blog:                      # /blog/… — на уровень глубже: свои адреса от корня сайта (style.css, img/…, страницы, #разделы)
        out = re.sub(r'\b(href|src)="(?![a-z][a-z0-9+.-]*:|/|\{\{)([^"]*)"', lambda m: f'{m[1]}="/{"" if m[2].startswith("#") else ""}{m[2]}"', out)
    return out


def site_files(site, images, base_url="", mode="publish"):
    """Все файлы сайта: {путь: текст} (картинки и шрифты кладёт sites.py). -> (files, fonts [(имя, файл)])."""
    files = {"style.css": css(site, mode)}
    for i, pg in enumerate(site.get("pages") or []):
        files[slug_of(pg, i) + ".html"] = page_html(site, i, mode, images, base_url)
    for k in doc_keys(site):
        files[doc_slug(site, k) + ".html"] = page_html(site, 0, mode, images, base_url, doc=k)
    if mode == "publish":         # шаблон страниц «Статей» — сервер собирает по нему /blog/ и /blog/<slug> (0.93)
        files["dw-blog.html"] = page_html(site, 0, mode, images, base_url, blog=True)
    return files, font_files((site.get("theme") or {}).get("fonts") or "warm")
