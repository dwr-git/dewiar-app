"""Блоки сайта (sites_render.py): первый экран, услуги, цены, галерея, отзывы, команда, вопросы, заявка; блоки
«Авангарда» (цифры, схема, два пути, полосы, кейсы, бегущая строка), видео; реестр RENDER и block_html."""

import re
import sites_kit as K

from sites_art import art_svg, map_svg, _rand, _seed
from sites_parts import (
    anchor, btns, contact_list, E, head2, items, legal_href, link, map_href, one, opt, para, safe_url, slug_of)


# ---------- блоки ----------


def b_hero(b, c, v):
    tt = one(b.get("title") or c.site.get("name"))
    t = f'<h1{" class=long" if len(tt) > 38 and v != "poster" else ""}>{tt}</h1>'
    lede = para(b.get("text"), "lede")
    note = f'<p class="note">{one(b["note"])}</p>' if b.get("note") else ""
    bt = btns(b, c)
    if v == "center":
        lg = c.site.get("logo") or {}
        mk = (f'<div class="hmark lg-mono">{E((lg.get("text") or c.site.get("name") or "С")[:1].upper())}</div>' if lg.get("style") == "mono"
              else f'<div class="hmark">{K.mark_svg(lg.get("mark") or "spark", 76, 1.3)}</div>')
        wide = c.media(b.get("image"), b.get("_k", "h") + "w", "media wide", b.get("title", "")) if c.img(b.get("image")) else ""
        return f'<div class="w">{mk}{t}{lede}{bt}{note}{wide}</div>'
    if v == "poster":
        big = c.media(b.get("image"), b.get("_k", "h"), "pbig", b.get("title", ""))
        return f'<div class="w">{t}{big}<div class="pside">{lede}{bt}</div>{note}</div>'
    if v == "kinetic":
        return f'<div class="w hk"><div class="hk-t">{kin_title(b.get("title") or c.site.get("name"))}{lede}{bt}{note}</div>{kin_art(b, c)}</div>'
    if v == "photo":
        src = c.img(b.get("image"))
        bg = f'<img src="{E(src)}" alt="">' if src else art_svg(c.art, {**c.pal, "surface": c.pal["dark"]}, b.get("_k", "h"), 1600, 1000)
        return f'<div class="bgm">{bg}</div><div class="w">{t}{lede}{bt}{note}</div>'
    return f'<div class="w"><div>{t}{lede}{bt}{note}</div>{c.media(b.get("image"), b.get("_k", "h"), "media", b.get("title", ""))}</div>'


def b_about(b, c, v):
    if v == "split":
        return (f'<div class="w split"><div><h2>{one(b.get("title"))}</h2>{para(b.get("text"), "lede")}</div>'
                f'{c.media(b.get("image"), b.get("_k", "a"), "media", b.get("title", ""))}</div>')
    facts = ""
    if v == "facts":
        facts = '<div class="facts">' + "".join(f'<div><b>{one(x.get("title"))}</b><span>{one(x.get("text"))}</span></div>' for x in items(b, c)) + "</div>"
    return f'<div class="w"><div><h2>{one(b.get("title"))}</h2>{para(b.get("text"), "lede")}</div>{facts}</div>'


def b_services(b, c, v):
    xs = items(b, c)
    if v == "list":
        rows = "".join(f'<div class="row sm"><div><h3>{one(x.get("title"))}</h3>{para(x.get("text"))}</div><b class="pr">{one(x.get("price"))}</b></div>' for x in xs)
        return f'<div class="w">{head2(b)}<div class="rows" style="max-width:860px">{rows}</div></div>'
    if v == "rows":
        rows = "".join(f'<div class="row"><h3>{one(x.get("title"))}</h3>{para(x.get("text")) or "<p></p>"}<b class="pr">{one(x.get("price"))}</b></div>' for x in xs)
        return f'<div class="w">{head2(b)}<div class="rows">{rows}</div></div>'
    cards = "".join(f'<article class="card svc-card"><span class="ic">{K.mark_svg(x.get("mark") or "check")}</span><h3>{one(x.get("title"))}</h3>'
                    f'{para(x.get("text"), "mut")}{opt("b", x.get("price"), "pr")}</article>' for x in xs)
    return f'<div class="w">{head2(b)}<div class="grid">{cards}</div></div>'


def b_prices(b, c, v):
    xs = items(b, c)
    if v == "plans":
        cards = []
        for x in xs:
            on = bool(x.get("featured"))
            bt = f'<a class="btn{"" if on else " ghost"}" href="{E(c.href(b.get("button_to") or "lead"))}">{one(b.get("button") or "Выбрать")}</a>'
            cards.append(f'<article class="card plan{" on" if on else ""}">{"<span class=chip>Чаще выбирают</span>" if on else ""}<h3>{one(x.get("title"))}</h3>'
                         f'{opt("s", x.get("old"), "old")}<div class="pr">{one(x.get("price"))}</div>{para(x.get("text"), "mut")}{bt}</article>')
        return f'<div class="w">{head2(b)}<div class="plans">{"".join(cards)}</div></div>'
    if v == "table":
        rows = "".join(f'<tr><td>{one(x.get("title"))}{opt("small", x.get("text"))}</td>'
                       f'<td>{one(x.get("price"))}</td></tr>' for x in xs)
        return f'<div class="w">{head2(b, btns(b, c))}<table class="tbl" style="max-width:860px">{rows}</table></div>'
    groups, order = {}, []
    for x in xs:
        g = str(x.get("group") or "").strip()
        if g not in groups:
            groups[g] = []
            order.append(g)
        groups[g].append(x)
    if v == "tabs" and len(order) > 1:
        return f'<div class="w">{head2(b, btns(b, c))}{price_tabs(b, order[:TAB_MAX], groups)}</div>'
    html_g, star = "", '<span class="star" title="Советуем">★</span>'
    for g in order:
        rows = "".join(f'<div class="pm-r"><span class="t">{one(x.get("title"))}{star if x.get("featured") else ""}'
                       f'{opt("span", x.get("text"), "d")}</span>'
                       f'<i class="dots"></i><b class="pr">{one(x.get("price"))}</b></div>' for x in groups[g])
        html_g += f'<div class="pm-g">{f"<h3>{E(g)}</h3>" if g else ""}{rows}</div>'
    return f'<div class="w">{head2(b, btns(b, c))}<div class="pm">{html_g}</div></div>'


TAB_MAX = 6


def price_tabs(b, order, groups):
    """Цены вкладками по разделам («Терапия», «Гигиена»…) — без скриптов: переключатели-радио и CSS (на опубликованном
    сайте скриптов нет). Стрелками ←/→ переключаются, как обычные вкладки; без раздела — «Другое»."""
    k = re.sub(r"[^a-z0-9]", "", str(b.get("_k") or b.get("uid") or "t").lower())[-12:] or "t"
    radios = "".join(f'<input type="radio" class="tb-r" name="tb{k}" id="tb{k}{i}"{" checked" if i == 0 else ""}>' for i in range(len(order)))
    labels = "".join(f'<label for="tb{k}{i}">{one(g or "Другое")}</label>' for i, g in enumerate(order))
    star = '<span class="star" title="Советуем">★</span>'
    panels = "".join('<div class="tb-p">' + "".join(
        f'<div class="pm-r"><span class="t">{one(x.get("title"))}{star if x.get("featured") else ""}{opt("span", x.get("text"), "d")}</span>'
        f'<i class="dots"></i><b class="pr">{one(x.get("price"))}</b></div>' for x in groups[g]) + "</div>" for g in order)
    return f'<div class="tabs">{radios}<div class="tb-l">{labels}</div><div class="tb-ps">{panels}</div></div>'


def b_features(b, c, v):
    xs = items(b, c)
    if v == "big":
        cells = "".join(f'<div>{K.mark_svg(x.get("mark") or "spark", 44, 1.4)}<h3>{one(x.get("title"))}</h3>{para(x.get("text"), "mut")}</div>' for x in xs)
        return f'<div class="w">{head2(b)}<div class="ft-big">{cells}</div></div>'
    if v == "split":
        lis = "".join(f'<li>{K.mark_svg(x.get("mark") or "check", 28)}<div><h3>{one(x.get("title"))}</h3>{para(x.get("text"), "mut")}</div></li>' for x in xs)
        return f'<div class="w ft-split"><div><h2>{one(b.get("title"))}</h2>{para(b.get("text"), "lede")}</div><ul>{lis}</ul></div>'
    cells = "".join(f'<div class="ft-i">{K.mark_svg(x.get("mark") or "spark", 30)}<h3>{one(x.get("title"))}</h3>{para(x.get("text"), "mut")}</div>' for x in xs)
    return f'<div class="w">{head2(b)}<div class="grid">{cells}</div></div>'


def b_steps(b, c, v):
    if v == "snake":
        return f'<div class="w">{head2(b)}{snake(items(b, c))}</div>'
    lis = "".join(f'<li><div><h3>{one(x.get("title"))}</h3>{para(x.get("text"), "mut")}</div></li>' for x in items(b, c))
    return f'<div class="w">{head2(b)}<ol class="steps{" v" if v == "list" else ""}">{lis}</ol></div>'


def b_gallery(b, c, v):
    if v == "pairs":
        return gallery_pairs(b, c)
    figs = []
    for i, x in enumerate(items(b, c)):
        src = c.img(x.get("image"))
        if not src and c.mode != "preview":
            continue                                  # пустые клетки галереи — только в предпросмотре
        cap = one(x.get("caption"))
        if src:
            m = f'<div class="media"><img src="{E(src)}" alt="{cap}" loading="lazy"></div>'
        else:
            m = f'<div class="media">{art_svg(c.art, c.pal, b.get("_k", "g") + str(i))}<span class="pvph">Добавьте фото</span></div>'
        figs.append(f'<figure>{m}{f"<figcaption>{cap}</figcaption>" if cap else ""}</figure>')
    if not figs:
        return ""
    if v == "mosaic" and len(figs) <= 2:
        v = "grid"
    if v == "mosaic":                                 # мозаика без дыр: первая — 2×2, последние — во всю пару колонок
        need = (4 - (len(figs) + 3) % 4) % 4
        for k in range(len(figs) - need, len(figs)):
            if k > 0:
                figs[k] = figs[k].replace("<figure>", '<figure class="wd">', 1)
    cls = {"mosaic": "gal mos", "strip": "gal strip"}.get(v, "gal")
    return f'<div class="w">{head2(b)}<div class="{cls}">{"".join(figs)}</div></div>'


def gallery_pairs(b, c):
    """«До и после»: фото идут парами (1-е — до, 2-е — после), подпись — у любого из пары. На сайт попадает только полная
    пара; в предпросмотре пустые места — узором с подсказкой «Добавьте фото»."""
    xs, out = items(b, c), []
    for i in range(0, len(xs), 2):
        pair = xs[i:i + 2]
        srcs = [c.img(x.get("image")) for x in pair]
        if c.mode != "preview" and (len(pair) < 2 or not all(srcs)):
            continue
        cap = one(next((x.get("caption") for x in pair if str(x.get("caption") or "").strip()), ""))
        cells = []
        for n, lab in enumerate(("До", "После")):
            src = srcs[n] if n < len(srcs) else ""
            m = (f'<img src="{E(src)}" alt="{cap + " — " if cap else ""}{lab.lower()}" loading="lazy">' if src
                 else f'{art_svg(c.art, c.pal, b.get("_k", "g") + str(i + n))}<span class="pvph">Добавьте фото</span>')
            cells.append(f'<div class="media">{m}<span class="ba-l">{lab}</span></div>')
        out.append(f'<figure class="ba">{"".join(cells)}{f"<figcaption>{cap}</figcaption>" if cap else ""}</figure>')
    if not out:
        return ""
    return f'<div class="w">{head2(b)}<div class="gal-ba">{"".join(out)}</div></div>'


def b_products(b, c, v):
    xs = items(b, c)
    if v == "list":
        rows = "".join(f'<div class="row sm"><div><h3>{one(x.get("title"))}</h3>{para(x.get("text"))}</div><b class="pr">{one(x.get("price"))}</b></div>' for x in xs)
        return f'<div class="w">{head2(b, btns(b, c))}<div class="rows">{rows}</div></div>'
    bt = one(b.get("button") or "Заказать")
    cards = "".join(f'<article class="prod">{c.media(x.get("image"), b.get("_k", "p") + str(i), "media", x.get("title", ""))}<h3>{one(x.get("title"))}</h3>'
                    f'{para(x.get("text"), "mut")}<div class="pr">{one(x.get("price"))}</div>'
                    f'<a class="btn ghost" href="{E(c.href(b.get("button_to") or "lead"))}">{bt}</a></article>' for i, x in enumerate(xs))
    return f'<div class="w">{head2(b)}<div class="grid">{cards}</div></div>'


def b_schedule(b, c, v):
    xs = items(b, c)
    if v == "days":
        cards = "".join(f'<div class="card"><b>{one(x.get("time"))}</b><h3>{one(x.get("title"))}</h3>{para(x.get("text"), "mut")}</div>' for x in xs)
        return f'<div class="w days">{head2(b)}<div class="grid">{cards}</div></div>'
    rows = "".join(f'<div><b>{one(x.get("time"))}</b><div><h3>{one(x.get("title"))}</h3>{para(x.get("text"), "mut")}</div></div>' for x in xs)
    return f'<div class="w">{head2(b)}<div class="ag">{rows}</div></div>'


def b_reviews(b, c, v):
    xs = [x for x in items(b, c) if str(x.get("text") or "").strip()]
    if not xs:
        if c.mode != "preview":
            return ""
        return (f'<div class="w">{head2(b)}<div class="card ph"><p>Здесь будут отзывы ваших клиентов. Пришлите их Лире — она добавит. '
                f'Выдумывать отзывы Лира не будет.</p></div></div>')
    if v == "masonry":
        tones = ("", "acc", "", "a2", "", "", "acc", "a2")
        figs = "".join(f'<figure class="card rm {tones[i % len(tones)]}"><blockquote>«{one(x.get("text")).strip("«»")}»</blockquote>'
                       f'<figcaption><i aria-hidden="true">{E(initials(x.get("name")))}</i><span><b>{one(x.get("name"))}</b>{opt("small", x.get("role"))}</span></figcaption></figure>'
                       for i, x in enumerate(xs))
        return f'<div class="w rv">{head2(b)}<div class="rms">{figs}</div></div>'
    figs = "".join(f'<figure class="{"card" if v == "cards" else ""}"><blockquote>«{one(x.get("text")).strip("«»")}»</blockquote>'
                   f'<figcaption><b>{one(x.get("name"))}</b>{", " + one(x.get("role")) if x.get("role") else ""}</figcaption></figure>' for x in xs)
    return f'<div class="w rv">{head2(b)}<div class="grid">{figs}</div></div>'


def b_team(b, c, v):
    xs = items(b, c)
    if not xs:
        return ""
    cards = []
    for x in xs:
        src = c.img(x.get("image"))
        ph = (f'<div class="media"><img src="{E(src)}" alt="{one(x.get("name"))}" loading="lazy"></div>' if src
              else f'<div class="media mono">{E((str(x.get("name") or "?").strip() or "?")[:1].upper())}</div>')
        cards.append(f'<article class="{"todo" if x.get("todo") else ""}">{ph}<h3>{one(x.get("name"))}</h3><p class="mut">{one(x.get("role"))}</p>{para(x.get("text"))}</article>')
    return f'<div class="w tm">{head2(b)}<div class="grid">{"".join(cards)}</div></div>'


def b_faq(b, c, v):
    ds = "".join(f'<details><summary>{one(x.get("q"))}</summary><div>{para(x.get("a"))}</div></details>' for x in items(b, c))
    return f'<div class="w">{head2(b)}<div class="faq{" two" if v == "two" else ""}">{ds}</div></div>'


def b_links(b, c, v):
    xs = [(one(x.get("title")), safe_url(x.get("href"))) for x in items(b, c)]
    xs = [(t, h) for t, h in xs if h]
    if not xs:
        return ""
    if v == "list":
        return f'<div class="w">{head2(b)}<div class="lk ls">{"".join(link(h, t) for t, h in xs)}</div></div>'
    return f'<div class="w">{head2(b)}<div class="lk">{"".join(link(h, t, "btn ghost") for t, h in xs)}</div></div>'


def b_cta(b, c, v):
    inner = f'<div><h2>{one(b.get("title"))}</h2>{para(b.get("text"), "lede")}</div>{btns(b, c)}'
    if v == "card":
        return f'<div class="w"><div class="card">{inner}</div></div>'
    return f'<div class="w">{inner}</div>'


def b_text(b, c, v):
    return f'<div class="w"><div>{opt("h2", b.get("title"))}{para(b.get("text"), "lede")}</div></div>'


def b_contacts(b, c, v):
    lst = contact_list(c)
    addr = c.contacts.get("address")
    if v == "band":
        return f'<div class="w ct-band">{head2(b)}{lst}</div>'
    mp = (f'<a class="ct-map" href="{E(map_href(addr))}" rel="noopener" aria-label="Открыть адрес на карте">{map_svg(c.pal, addr)}'
          f'<span class="btn">Открыть на карте</span></a>') if addr else c.media("", b.get("_k", "c"), "media ct-map")
    return f'<div class="w split"><div><h2>{one(b.get("title") or "Контакты")}</h2>{para(b.get("text"), "lede")}{lst}</div>{mp}</div>'


def pd_consent(c):
    """152-ФЗ: задана политика обработки ПД — в форме заявки галочки со ссылками (обязательные). С 01.09.2025 согласие на
    обработку ПД оформляется отдельно от других документов (№1100, 26.11: «нужен модуль с 3 чекбоксами: согласие, политика,
    оферта»): своя галочка — согласие, своя — «ознакомлен с политикой», своя — с офертой, если оферта на сайте есть.
    pd_need — серверу (sites.php), чтобы без галочки согласия заявку не принять и без браузера."""
    pol = legal_href(c.site, "privacy")
    if not pol:
        return ""
    con, of = legal_href(c.site, "consent"), legal_href(c.site, "oferta")
    lk = lambda h, t: f'<a href="{E(h)}" target="_blank" rel="noopener">{t}</a>' if h else t
    box = lambda name, txt: (f'<label class="pdc"><input type="checkbox" name="{name}" value="1" required>'
                             f'<span>{txt}</span></label>')
    return ('<input type="hidden" name="pd_need" value="1">'
            + box("pd_ok", f'Даю {lk(con, "согласие на обработку персональных данных")}')
            + box("pd_pol", f'Ознакомлен(а) с {lk(pol, "политикой обработки персональных данных")}')
            + (box("pd_of", f'Ознакомлен(а) с {lk(of, "публичной офертой")}') if of else ""))


def lead_form(b, c):
    pg = slug_of(c.pages[c.page_i], c.page_i) if c.pages else "index"
    pub = str((c.site.get("published") or {}).get("url") or "")
    if c.mode == "export" and re.match(r"^https://", pub):
        # 15.11: сайт архивом на своём хостинге — форма там не отправит (заявки принимает dewiar.pro): кнопка ведёт к форме
        # опубликованной копии, заявка всё так же приходит в «Клиенты»
        href = pub.rstrip("/") + "/" + ("" if pg == "index" else pg + ".html") + "#lead"
        return (f'<div class="form"><a class="btn" href="{E(href)}" target="_blank" rel="noopener">{one(b.get("button") or "Оставить заявку")}</a>'
                f'<small>Форма откроется в новой вкладке.</small></div>')
    action = "/__lead" if c.mode == "publish" else "#"
    msg = '<label>Комментарий<textarea name="note" maxlength="600"></textarea></label>' if b.get("ask_message") else ""
    return (f'<form class="form" method="post" action="{action}"><input type="hidden" name="page" value="{E(pg)}">'
            f'<div class="hp" aria-hidden="true"><label>Не заполняйте<input name="website" tabindex="-1" autocomplete="off"></label></div>'
            f'<label>Как вас зовут<input name="name" maxlength="80" autocomplete="name" required></label>'
            f'<label>Телефон или почта<input name="contact" maxlength="120" autocomplete="tel" inputmode="email" required></label>{msg}'
            f'{pd_consent(c)}<button class="btn" type="submit">{one(b.get("button") or "Отправить")}</button>'
            f'{"" if legal_href(c.site, "privacy") else "<small>Нажимая кнопку, вы соглашаетесь, что с вами свяжутся по этим контактам.</small>"}'
            f'<p class="ok" id="lead-ok" role="status">{one(b.get("thanks") or "Спасибо! Скоро свяжемся.")}</p></form>')


def b_lead(b, c, v):
    if v == "card":
        return f'<div class="w ld-card"><div class="ldh"><h2>{one(b.get("title"))}</h2>{para(b.get("text"), "lede")}</div><div class="card">{lead_form(b, c)}</div></div>'
    return (f'<div class="w split top"><div><h2>{one(b.get("title"))}</h2>{para(b.get("text"), "lede")}{contact_list(c, ("phone", "telegram", "whatsapp", "email"))}</div>'
            f'<div class="card">{lead_form(b, c)}</div></div>')


# ---------- блоки «Авангарда» (0.94): работают в любом стиле, движение — только CSS (без скриптов) ----------


def initials(name):
    w = [s for s in re.split(r"[\s.]+", str(name or "")) if s]
    return "".join(s[0] for s in w[:2]).upper() or "•"


def kin_title(t):
    t = re.sub(r"\s+", " ", str(t or "")).strip()
    dot = "" if not t or t[-1] in ".!?…»\"" else '<i class="dot" aria-hidden="true">.</i>'
    return f'<h1 class="kin{" long" if len(t) > 30 else ""}">{E(t)}{dot}</h1>'


KIN_PATHS = ("M20 120 C 120 200, 230 40, 350 100 S 490 60, 540 40", "M10 280 C 110 230, 210 350, 320 280 S 470 240, 540 280",
             "M20 440 C 140 400, 240 490, 360 420 S 490 390, 540 410")


def kin_art(b, c):
    words = [w.strip() for w in re.split(r"[·•|,;]", str(b.get("words") or "")) if w.strip()][:6]
    if not words:
        words = [w for w in (c.site.get("name"), c.site.get("tagline")) if w] or ["Ваше дело"]
    lines = [" · ".join(words[i::3]).upper() for i in range(min(3, len(words)))]
    fills = ("var(--slink)", "var(--a2)", "var(--sink)")
    k = re.sub(r"[^a-z0-9]", "", b.get("_k", "h")) or "h"
    defs = "".join(f'<path id="kp{k}{i}" d="{d}"/>' for i, d in enumerate(KIN_PATHS))
    rails = "".join(f'<use href="#kp{k}{i}" class="kr kr{i}"/>' for i in range(len(lines)))
    texts = "".join(f'<text class="kt kt{i}" fill="{fills[i]}"><textPath href="#kp{k}{i}" startOffset="{(4, 9, 3)[i]}%">{E(t)}</textPath></text>'
                    for i, t in enumerate(lines))
    dots = "".join(f'<circle class="kd kd{i}" r="6" style="offset-path:path(\'{KIN_PATHS[i]}\')"/>' for i in range(len(lines)))
    return f'<div class="hk-art" aria-hidden="true"><svg viewBox="0 0 540 520"><defs>{defs}</defs>{rails}{dots}{texts}</svg></div>'


def num_of(v):
    m = re.search(r"-?\d+(?:[.,]\d+)?", str(v or "").replace("\u00a0", "").replace(" ", ""))
    return float(m[0].replace(",", ".")) if m else 0.0


def b_stats(b, c, v):
    xs = [x for x in items(b, c) if str(x.get("value") or "").strip()]
    if not xs:
        return ""
    if v == "formula":
        parts = []
        for i, x in enumerate(xs[:3]):
            if i:
                parts.append(f'<span class="op" aria-hidden="true">{"+" if i < len(xs[:3]) - 1 else "="}</span>')
            parts.append(f'<div class="fig f{i}"><b>{one(x.get("value"))}</b>{opt("small", x.get("label"))}</div>')
        return f'<div class="w">{head2(b)}<div class="formula">{"".join(parts)}</div></div>'
    if v == "stickers":
        src = c.img(b.get("image"))
        pic = (f'<div class="sk-pic"><img src="{E(src)}" alt="{E(b.get("title") or "")}" loading="lazy"></div>' if src else
               f'<div class="sk-pic sk-mono"><span>{E(initials(c.site.get("name")))}</span></div>')
        st = "".join(f'<div class="stk k{i}{" hot" if i == 1 else ""}"><b>{one(x.get("value"))}</b>{opt("small", x.get("label"))}</div>' for i, x in enumerate(xs[:4]))
        t = f'<h2>{one(b.get("title"))}</h2>' if b.get("title") else ""
        return f'<div class="w sk"><div class="sk-art">{pic}{st}</div><div class="sk-t hd2"><div>{t}{para(b.get("text"), "lede")}</div></div></div>'
    cells = "".join(f'<div class="st-c"><b>{one(x.get("value"))}</b>{opt("span", x.get("label"))}</div>' for x in xs[:6])
    return f'<div class="w">{head2(b)}<div class="st-row">{cells}</div></div>'


def b_hub(b, c, v):
    xs = items(b, c)[:8]
    if not xs:
        return ""
    k = re.sub(r"[^a-z0-9]", "", b.get("_k", "h")) or "h"
    radios = "".join(f'<input class="hub-r" type="radio" name="hub{k}" id="hub{k}-{i}"{" checked" if not i else ""} aria-label="{E(x.get("title") or "")}">'
                     for i, x in enumerate(xs))

    def lab(i, x):
        return (f'<label class="node" for="hub{k}-{i}" data-i="{i}"><em>{i + 1:02d}</em><b>{one(x.get("title"))}</b>'
                f'{opt("small", x.get("sub"))}</label>')
    half = (len(xs) + 1) // 2
    left = "".join(lab(i, x) for i, x in enumerate(xs[:half]))
    right = "".join(lab(i + half, x) for i, x in enumerate(xs[half:]))
    says = "".join(f'<div class="hub-p" data-i="{i}"><b>{one(x.get("title"))}</b>{para(x.get("text") or x.get("sub"))}</div>' for i, x in enumerate(xs))
    core = (f'<div class="hub-core"><svg viewBox="0 0 260 260" aria-hidden="true"><circle cx="130" cy="130" r="124" class="c1"/>'
            f'<circle cx="130" cy="130" r="104" class="c2"/><circle cx="130" cy="130" r="84" class="c3"/></svg>'
            f'<p>{one(b.get("center") or c.site.get("name"))}</p></div>')
    return f'<div class="w">{head2(b)}<div class="hub n{len(xs)}">{radios}<div class="hub-col">{left}</div>{core}<div class="hub-col">{right}</div><div class="hub-say">{says}</div></div></div>'


def b_duo(b, c, v):
    xs = items(b, c)[:2]
    if not xs:
        return ""
    cards = "".join(f'<article class="duo-c d{i}"><div class="dr"><span>Путь {i + 1:02d}</span>{opt("i", x.get("tag"))}</div>'
                    f'<span class="num" aria-hidden="true">{i + 1:02d}</span><h3>{one(x.get("title"))}</h3>{para(x.get("text"))}'
                    f'{opt("div", x.get("foot"), "foot")}</article>' for i, x in enumerate(xs))
    return f'<div class="w">{head2(b)}<div class="duo">{cards}</div></div>'


def b_bars(b, c, v):
    xs = [x for x in items(b, c) if str(x.get("title") or "").strip()]
    if not xs:
        return ""
    mx = max([num_of(x.get("value")) for x in xs] + [0]) or 1
    unit = one(b.get("unit"))
    rows = "".join(f'<div class="br{" on" if x.get("featured") else ""}"><span>{one(x.get("title"))}</span>'
                   f'<div class="tr"><i style="width:{max(2, round(num_of(x.get("value")) / mx * 100))}%"></i></div>'
                   f'<b>{one(x.get("value"))}{(" " + unit) if unit else ""}</b></div>' for x in xs[:10])
    return f'<div class="w bars-w">{head2(b)}<div class="bars card">{rows}</div></div>'


def b_cases(b, c, v):
    xs = items(b, c)
    if not xs:
        return ""
    cards = []
    for i, x in enumerate(xs[:12]):
        has_img = bool(c.img(x.get("image")))
        m = (f'<div class="meter"><b>{one(x.get("metric"))}</b>{opt("small", x.get("metric_label"))}</div>' if x.get("metric") and has_img else "")
        vis = (c.media(x.get("image"), b.get("_k", "c") + str(i), "media", x.get("title", "")) if has_img or not x.get("metric")
               else case_viz(x, b.get("_k", "c") + str(i)))
        cards.append(f'<article class="case card"><header><em>{i + 1:02d} /</em>{opt("span", x.get("who"))}</header>'
                     f'{vis}<h3>{one(x.get("title"))}</h3>{para(x.get("text"), "mut")}{m}</article>')
    if v == "grid":
        return f'<div class="w">{head2(b)}<div class="cs-grid">{"".join(cards)}</div></div>'
    return (f'<div class="w cs">{head2(b, "<span class=cs-hint>Листайте →</span>" if len(cards) > 2 else "")}'
            f'<div class="cs-rail" tabindex="0" role="region" aria-label="{E(b.get("title") or "Кейсы")}">{"".join(cards)}</div>'
            f'<div class="cs-bar" aria-hidden="true"><i></i></div></div>')


def case_viz(x, seed):
    """Кейс без картинки: результат числом крупно и линия тренда — рост или падение по знаку числа (без выдуманных осей)."""
    r = _rand(_seed(seed))
    down = str(x.get("metric") or "").strip().startswith(("−", "-"))
    ys, y = [], 0.0
    for _ in range(9):
        y += (r() - .3) * 1.0
        ys.append(y)
    lo, hi = min(ys), max(ys)
    pts = [(10 + i * 280 / 8, (10 + (yy - lo) / ((hi - lo) or 1) * 80) if down else (90 - (yy - lo) / ((hi - lo) or 1) * 80)) for i, yy in enumerate(ys)]
    d = " ".join(("M" if i == 0 else "L") + f"{px:.1f} {py:.1f}" for i, (px, py) in enumerate(pts))
    grid = "".join(f'<line class="gd" x1="0" x2="300" y1="{g}" y2="{g}"/>' for g in (20, 50, 80))
    return (f'<div class="case-viz"><div><b>{one(x.get("metric"))}</b>{opt("small", x.get("metric_label"))}</div>'
            f'<svg viewBox="0 0 300 100" preserveAspectRatio="none" aria-hidden="true">{grid}<path class="ar" d="{d} L290 100 L10 100Z"/>'
            f'<path class="ln" d="{d}"/></svg></div>')


def b_ticker(b, c, v):
    words = [w.strip() for w in re.split(r"[·•|]", str(b.get("text") or "")) if w.strip()][:12]
    if not words:
        return ""
    run = "".join(f"<span>{E(w)}</span>" for w in words)
    return (f'<p class="vh">{E(" · ".join(words))}</p><div class="tk" aria-hidden="true"><div class="tk-t">{run}{run}</div></div>')


def snake(xs):
    """Шаги змейкой: по 4 в ряд, чётные ряды — справа налево, поворот — дугой у края (на телефоне — столбиком)."""
    xs = [x for x in xs if str(x.get("title") or "").strip()][:12]
    rows, out = [xs[i:i + 4] for i in range(0, len(xs), 4)], []
    n = 0
    for r, row in enumerate(rows):
        cells = []
        for x in row:
            n += 1
            cells.append(f'<li class="sn-s"><span class="n c{min(3, 1 + (n - 1) * 3 // max(1, len(xs)))}">{n:02d}</span>'
                         f'<b>{one(x.get("title"))}</b>{opt("small", x.get("text"))}</li>')
        out.append(f'<ol class="sn-row{" rev" if r % 2 else ""}" start="{n - len(row) + 1}">{"".join(cells)}</ol>')
        if r < len(rows) - 1:
            out.append(f'<div class="sn-turn {"r" if r % 2 == 0 else "l"}" aria-hidden="true"></div>')
    return f'<div class="snake">{"".join(out)}</div>'


VIDEO_FILE = re.compile(r"^https://[^\s\"'<>]+\.(?:mp4|webm|m4v)(?:\?[^\s\"'<>]*)?$", re.I)


def video_embed(url):
    """Ссылка на ролик -> (вид, адрес для встраивания): youtube | rutube | vk — iframe, file — <video>; не ролик — (None, "").
    Только известные площадки и https — чужой код на сайт не попадает (15.11)."""
    u = str(url or "").strip()
    m = re.match(r"^https?://(?:www\.|m\.)?(?:youtube\.com/(?:watch\?(?:[^#\s]*&)?v=|shorts/|embed/|live/)|youtu\.be/)([\w-]{11})", u, re.I)
    if m:
        return "youtube", f"https://www.youtube-nocookie.com/embed/{m.group(1)}"
    m = re.match(r"^https?://(?:www\.)?rutube\.ru/(?:video|play/embed|shorts)/([0-9a-f]{32})", u, re.I)
    if m:
        return "rutube", f"https://rutube.ru/play/embed/{m.group(1)}"
    m = re.match(r"^https?://(?:www\.|m\.)?(?:vk\.com|vkvideo\.ru)/(?:video|clip)(-?\d+)_(\d+)", u, re.I) \
        or re.match(r"^https?://(?:www\.)?vk\.com/video_ext\.php\?oid=(-?\d+)&id=(\d+)", u, re.I)
    if m:
        return "vk", f"https://vk.com/video_ext.php?oid={m.group(1)}&id={m.group(2)}&hd=2"
    if VIDEO_FILE.match(u):
        return "file", u
    return None, ""


def b_video(b, c, v):
    figs = []
    for x in items(b, c):
        kind, src = video_embed(x.get("url"))
        cap = one(x.get("caption"))
        if not kind:
            if c.mode != "preview":
                continue                              # пустая или непонятная ссылка — на сайте не показываем
            m = '<div class="vid vph"><span>▶</span><small>Добавьте ссылку на видео (YouTube, Rutube, VK или .mp4)</small></div>'
        elif c.mode == "preview" and kind != "file":
            host = {"youtube": "YouTube", "rutube": "Rutube", "vk": "VK Видео"}[kind]
            m = f'<div class="vid vph"><span>▶</span><small>Видео {host} — на сайте будет плеер</small></div>'
        elif kind == "file":
            m = f'<div class="vid"><video src="{E(src)}" controls preload="metadata" playsinline></video></div>'
        else:
            m = (f'<div class="vid"><iframe src="{E(src)}" title="{E(x.get("caption") or b.get("title") or "Видео")}" loading="lazy" allowfullscreen '
                 f'allow="autoplay; encrypted-media; picture-in-picture; fullscreen" referrerpolicy="strict-origin-when-cross-origin"></iframe></div>')
        figs.append(f'<figure>{m}{f"<figcaption>{cap}</figcaption>" if cap else ""}</figure>')
    if not figs:
        return ""
    return f'<div class="w">{head2(b)}<div class="vids{" vg" if v == "grid" and len(figs) > 1 else ""}">{"".join(figs)}</div></div>'


RENDER = {"hero": b_hero, "about": b_about, "services": b_services, "prices": b_prices, "features": b_features, "steps": b_steps,
          "gallery": b_gallery, "products": b_products, "schedule": b_schedule, "reviews": b_reviews, "team": b_team, "faq": b_faq,
          "links": b_links, "cta": b_cta, "text": b_text, "contacts": b_contacts, "lead": b_lead,
          "stats": b_stats, "hub": b_hub, "duo": b_duo, "bars": b_bars, "cases": b_cases, "ticker": b_ticker, "video": b_video}


EXTRA_CLS = {"hero": lambda v: f"hero h-{v}", "about": lambda v: f"ab-{v}", "contacts": lambda v: f"ct-{v}", "lead": lambda v: f"ld ld-{v}",
             "cta": lambda v: f"cta cta-{v}", "text": lambda v: f"tx {v}", "stats": lambda v: f"stt st-{v}", "ticker": lambda v: "tkr"}


def block_html(b, j, c):
    t = b.get("type")
    fn = RENDER.get(t)
    if not fn or b.get("hidden"):
        return ""
    v = b.get("variant") if b.get("variant") in K.BLOCKS[t]["variants"] else next(iter(K.BLOCKS[t]["variants"]))
    b = dict(b, _k=f"{c.page_i}-{j}-{t}")
    inner = fn(b, c, v)
    if not inner:
        return ""
    tone = b.get("tone") if b.get("tone") in K.TONES else "base"
    cls = f"s t-{tone} b-{t} " + (EXTRA_CLS[t](v) if t in EXTRA_CLS else "")
    data = f' data-b="{E(str(b.get("uid") or ""))}"' if c.mode == "preview" else ""
    return f'<section id="{anchor(b, j)}" class="{cls.strip()}"{data}>{inner}</section>'
