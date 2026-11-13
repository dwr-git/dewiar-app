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

E = html.escape


# ---------- цвет ----------
def _rgb(h):
    h = str(h or "#000000").lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        return [int(h[i:i + 2], 16) for i in (0, 2, 4)]
    except ValueError:
        return [0, 0, 0]


def _hex(c):
    return "#%02x%02x%02x" % tuple(max(0, min(255, round(v))) for v in c)


def mix(a, b, t):
    """Цвет между a и b (t — доля b)."""
    x, y = _rgb(a), _rgb(b)
    return _hex([x[i] + (y[i] - x[i]) * t for i in range(3)])


def lum(h):
    c = [v / 255 for v in _rgb(h)]
    c = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def contrast(a, b):
    x, y = sorted((lum(a), lum(b)), reverse=True)
    return (x + 0.05) / (y + 0.05)


def readable_on(color, bg, ratio=4.5):
    """color, сдвинутый к чёрному или белому, пока не читается на bg."""
    target = "#000000" if lum(bg) > 0.4 else "#ffffff"
    c = color
    for i in range(1, 21):
        if contrast(c, bg) >= ratio:
            return c
        c = mix(color, target, i / 20)
    return target


def colors(theme):
    """Палитра темы (именованная + свои поправки theme.colors) -> полный набор цветов."""
    p = dict(K.PALETTES.get((theme or {}).get("palette") or "", K.PALETTES["pistachio"]))
    for k, v in ((theme or {}).get("colors") or {}).items():
        if k in K.COLOR_KEYS and re.fullmatch(r"#[0-9a-fA-F]{6}", str(v or "")):
            p[k] = v
    p.pop("title", None)
    return p


# ---------- текст ----------
def para(text, cls=""):
    """Абзацы: пустая строка — новый <p>, перенос строки — <br>. Всё экранировано."""
    t = str(text or "").strip()
    if not t:
        return ""
    c = f' class="{cls}"' if cls else ""
    return "".join(f"<p{c}>" + "<br>".join(E(x) for x in p.split("\n")) + "</p>" for p in re.split(r"\n\s*\n", t) if p.strip())


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


# ---------- узоры вместо фото ----------
def _rand(seed):
    x = (abs(hash(seed)) if not isinstance(seed, int) else seed) % 2147483647 or 7

    def r():
        nonlocal x
        x = (x * 48271) % 2147483647
        return x / 2147483647
    return r


def _seed(s):
    h = 0
    for ch in str(s):
        h = (h * 131 + ord(ch)) % 2147483647
    return h or 11


def art_svg(kind, pal, seed="a", w=800, h=1000, mark=""):
    """Декоративная композиция вместо фото — в цветах темы, своя для каждого шаблона; seed меняет расклад."""
    r = _rand(_seed(seed))
    bg, a1, a2, ink, sf = pal["surface"], pal["accent"], pal["accent2"], pal["ink"], pal["bg"]
    ln = mix(pal["surface"], pal["ink"], .14)
    o = [f'<svg class="art" viewBox="0 0 {w} {h}" preserveAspectRatio="xMidYMid slice" aria-hidden="true" xmlns="http://www.w3.org/2000/svg">',
         f'<rect width="{w}" height="{h}" fill="{bg}"/>']
    if kind == "beans":
        o.append(f'<circle cx="{w * (.55 + r() * .2):.0f}" cy="{h * (.35 + r() * .2):.0f}" r="{min(w, h) * .42:.0f}" fill="{mix(bg, a1, .16)}"/>')
        for i in range(9):
            cx, cy, rot = w * r(), h * r(), r() * 180
            s = min(w, h) * (.08 + r() * .07)
            col = [a1, ink, a2][i % 3]
            o.append(f'<g transform="translate({cx:.0f} {cy:.0f}) rotate({rot:.0f})"><ellipse rx="{s:.0f}" ry="{s * .68:.0f}" fill="{col}"/>'
                     f'<path d="M{-s * .8:.0f} 0 C{-s * .3:.0f} {-s * .28:.0f} {s * .3:.0f} {s * .28:.0f} {s * .8:.0f} 0" stroke="{bg}" stroke-width="{s * .09:.1f}" fill="none" stroke-linecap="round"/></g>')
    elif kind == "arches":
        cols = [a1, a2, mix(bg, a1, .35), sf, a1]
        n, cx = 5, w * (.5 + (r() - .5) * .2)
        for i in range(n):
            rw = w * (.46 - i * .075)
            top = h * (.18 + i * .07)
            o.append(f'<path d="M{cx - rw:.0f} {h} V{top + rw:.0f} A{rw:.0f} {rw:.0f} 0 0 1 {cx + rw:.0f} {top + rw:.0f} V{h} Z" fill="{cols[i % len(cols)]}"/>')
        o.append(f'<circle cx="{w * (.15 + r() * .2):.0f}" cy="{h * .12:.0f}" r="{w * .05:.0f}" fill="{a2}"/>')
    elif kind == "frames":
        o.append(f'<rect x="{w * .14:.0f}" y="{h * .12:.0f}" width="{w * .62:.0f}" height="{h * .62:.0f}" fill="{mix(bg, a1, .55)}"/>')
        for i in range(4):
            d = 26 + i * 30
            o.append(f'<rect x="{w * .14 + d:.0f}" y="{h * .12 + d:.0f}" width="{w * .62:.0f}" height="{h * .62:.0f}" fill="none" stroke="{ink}" stroke-opacity="{.5 - i * .1:.2f}" stroke-width="1.5"/>')
        o.append(f'<rect x="{w * .5:.0f}" y="{h * .58:.0f}" width="{w * .34:.0f}" height="{h * .28:.0f}" fill="{a2}"/>')
    elif kind == "dots":
        step = max(w, h) / 18
        dots = "".join(f'<circle cx="{x * step:.0f}" cy="{y * step:.0f}" r="3" fill="{ln}"/>' for x in range(19) for y in range(int(h / step) + 2))
        o.append(dots)
        o.append(f'<circle cx="{w * .62:.0f}" cy="{h * .42:.0f}" r="{w * .3:.0f}" fill="{a1}"/>')
        o.append(f'<path d="M0 {h} V{h * .68:.0f} A{w * .32:.0f} {w * .32:.0f} 0 0 1 {w * .32:.0f} {h} Z" fill="{a2}"/>')
        o.append(f'<rect x="{w * .14:.0f}" y="{h * .16:.0f}" width="{w * .18:.0f}" height="{w * .18:.0f}" rx="{w * .04:.0f}" fill="{ink}" transform="rotate(12 {w * .23:.0f} {h * .16 + w * .09:.0f})"/>')
    elif kind == "blocks":
        n = 4
        cw, chh = w / n, h / 5
        cols = [a1, a2, ink, sf, mix(bg, a1, .3)]
        for x in range(n):
            for y in range(5):
                v = r()
                if v < .42:
                    continue
                col = cols[int(r() * len(cols))]
                if v > .82:
                    o.append(f'<circle cx="{x * cw + cw / 2:.0f}" cy="{y * chh + chh / 2:.0f}" r="{min(cw, chh) * .42:.0f}" fill="{col}"/>')
                elif v > .62:
                    o.append(f'<path d="M{x * cw:.0f} {(y + 1) * chh:.0f} A{cw:.0f} {chh:.0f} 0 0 1 {(x + 1) * cw:.0f} {y * chh:.0f} V{(y + 1) * chh:.0f}Z" fill="{col}"/>')
                else:
                    o.append(f'<rect x="{x * cw + 6:.0f}" y="{y * chh + 6:.0f}" width="{cw - 12:.0f}" height="{chh - 12:.0f}" fill="{col}"/>')
    elif kind == "rings":
        cx, cy = w * (.6 + r() * .15), h * (.4 + r() * .2)
        for i in range(9, 0, -1):
            o.append(f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="{min(w, h) * .085 * i:.0f}" fill="{mix(bg, a1, .07 * (10 - i)) if i % 2 else bg}"/>')
        o.append(f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="{min(w, h) * .085:.0f}" fill="{a1}"/>')
        o.append(f'<circle cx="{w * .2:.0f}" cy="{h * .8:.0f}" r="{min(w, h) * .07:.0f}" fill="{a2}"/>')
    elif kind == "stripes":
        sw = max(w, h) / 9
        for i in range(-4, 14):
            col = [a1, a2, sf][i % 3]
            o.append(f'<path d="M{i * sw:.0f} {h} L{i * sw + h * .7:.0f} 0 H{i * sw + h * .7 + sw * .55:.0f} L{i * sw + sw * .55:.0f} {h}Z" fill="{col}"/>')
        o.append(f'<circle cx="{w * .5:.0f}" cy="{h * .5:.0f}" r="{min(w, h) * .26:.0f}" fill="{sf}"/>')
    elif kind == "grid":
        step = 40
        g = "".join(f'<path d="M{x} 0V{h}" stroke="{ln}"/>' for x in range(0, w + 1, step)) + "".join(f'<path d="M0 {y}H{w}" stroke="{ln}"/>' for y in range(0, h + 1, step))
        o.append(g)
        for i in range(3):
            x, y = w * (.12 + i * .1), h * (.14 + i * .24)
            o.append(f'<rect x="{x:.0f}" y="{y:.0f}" width="{w * .62:.0f}" height="{h * .17:.0f}" rx="18" fill="{sf}" stroke="{ln}" stroke-width="2"/>'
                     f'<circle cx="{x + 46:.0f}" cy="{y + h * .085:.0f}" r="20" fill="{[a1, a2, ink][i]}"/>'
                     f'<rect x="{x + 84:.0f}" y="{y + h * .06:.0f}" width="{w * .3:.0f}" height="12" rx="6" fill="{mix(sf, ink, .25)}"/>'
                     f'<rect x="{x + 84:.0f}" y="{y + h * .095:.0f}" width="{w * .18:.0f}" height="10" rx="5" fill="{mix(sf, ink, .12)}"/>')
    elif kind == "pulse":                              # фитнес: косые полосы скорости и линия пульса
        sw = w / 7
        for i in range(-3, 9):
            col = [a1, mix(bg, a1, .28), mix(bg, ink, .1)][i % 3]
            if r() < .35:
                continue
            o.append(f'<path d="M{i * sw:.0f} {h} L{i * sw + h * .5:.0f} 0 H{i * sw + h * .5 + sw * .42:.0f} L{i * sw + sw * .42:.0f} {h}Z" fill="{col}"/>')
        y0, pts = h * (.5 + (r() - .5) * .16), []
        x = -10
        while x < w + 20:
            pts.append(f"{x:.0f},{y0:.0f}")
            if r() < .5:
                pk = h * (.14 + r() * .12)
                pts += [f"{x + 22:.0f},{y0:.0f}", f"{x + 36:.0f},{y0 - pk:.0f}", f"{x + 54:.0f},{y0 + pk * .7:.0f}", f"{x + 68:.0f},{y0:.0f}"]
                x += 68
            x += w * .1
        o.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="{ink}" stroke-width="{max(w, h) * .016:.0f}" stroke-linejoin="round" stroke-linecap="round"/>')
        o.append(f'<circle cx="{w * .82:.0f}" cy="{h * .2:.0f}" r="{min(w, h) * .07:.0f}" fill="{a2}"/>')
    elif kind == "pebbles":                            # стоматология: мягкая галька и блики
        for i in range(7):
            cx, cy = w * (.1 + r() * .8), h * (.1 + r() * .8)
            rx = min(w, h) * (.14 + r() * .16)
            col = [mix(bg, a1, .22), a2, sf, mix(bg, a1, .45)][i % 4]
            o.append(f'<ellipse cx="{cx:.0f}" cy="{cy:.0f}" rx="{rx:.0f}" ry="{rx * (.62 + r() * .25):.0f}" fill="{col}" transform="rotate({r() * 180:.0f} {cx:.0f} {cy:.0f})"/>')
        for i in range(3):
            cx, cy, s = w * (.2 + r() * .6), h * (.15 + r() * .7), min(w, h) * (.03 + r() * .03)
            o.append(f'<path d="M{cx:.0f} {cy - s * 2:.0f} C{cx + s * .3:.0f} {cy - s * .3:.0f} {cx + s * .3:.0f} {cy - s * .3:.0f} {cx + s * 2:.0f} {cy:.0f} '
                     f'C{cx + s * .3:.0f} {cy + s * .3:.0f} {cx + s * .3:.0f} {cy + s * .3:.0f} {cx:.0f} {cy + s * 2:.0f} C{cx - s * .3:.0f} {cy + s * .3:.0f} {cx - s * .3:.0f} {cy + s * .3:.0f} {cx - s * 2:.0f} {cy:.0f} '
                     f'C{cx - s * .3:.0f} {cy - s * .3:.0f} {cx - s * .3:.0f} {cy - s * .3:.0f} {cx:.0f} {cy - s * 2:.0f}Z" fill="{sf}"/>')
    elif kind == "confetti":                           # детский центр: конфетти — кружки, треугольники, волнистые ленты
        cols = [a1, a2, ink, mix(a1, a2, .5), mix(bg, a1, .5)]
        u = min(w, h)
        o.append(f'<circle cx="{w * (.55 + r() * .2):.0f}" cy="{h * (.45 + r() * .1):.0f}" r="{u * .3:.0f}" fill="{mix(bg, a2, .3)}"/>')
        for i in range(16):
            cx, cy, s, col, rot = w * r(), h * r(), u * (.03 + r() * .04), cols[i % len(cols)], r() * 360
            k = i % 4
            if k == 0:
                o.append(f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="{s:.0f}" fill="{col}"/>')
            elif k == 1:
                o.append(f'<path d="M0 {-s * 1.2:.0f} L{s * 1.1:.0f} {s * .8:.0f} L{-s * 1.1:.0f} {s * .8:.0f}Z" fill="{col}" transform="translate({cx:.0f} {cy:.0f}) rotate({rot:.0f})"/>')
            elif k == 2:
                o.append(f'<path d="M{-s * 2.4:.0f} 0 q{s * .6:.0f} {-s:.0f} {s * 1.2:.0f} 0 t{s * 1.2:.0f} 0 t{s * 1.2:.0f} 0 t{s * 1.2:.0f} 0" fill="none" stroke="{col}" '
                         f'stroke-width="{s * .55:.0f}" stroke-linecap="round" transform="translate({cx:.0f} {cy:.0f}) rotate({rot:.0f})"/>')
            else:
                o.append(f'<rect x="{-s:.0f}" y="{-s * .45:.0f}" width="{s * 2:.0f}" height="{s * .9:.0f}" rx="{s * .45:.0f}" fill="{col}" transform="translate({cx:.0f} {cy:.0f}) rotate({rot:.0f})"/>')
    elif kind == "hazard":                             # автосервис: сигнальная лента, шестерня и болты
        u = min(w, h)
        g = "".join(f'<path d="M{x} 0V{h}" stroke="{ln}"/>' for x in range(0, w + 1, 50)) + "".join(f'<path d="M0 {y}H{w}" stroke="{ln}"/>' for y in range(0, h + 1, 50))
        o.append(g)
        cx, cy, R1 = w * (.58 + r() * .1), h * .42, u * .3
        teeth = "".join(f'<rect x="{-u * .045:.0f}" y="{-R1 - u * .07:.0f}" width="{u * .09:.0f}" height="{u * .12:.0f}" rx="4" fill="{mix(bg, ink, .22)}" transform="rotate({k * 30})"/>' for k in range(12))
        o.append(f'<g transform="translate({cx:.0f} {cy:.0f})">{teeth}<circle r="{R1:.0f}" fill="{mix(bg, ink, .22)}"/><circle r="{R1 * .42:.0f}" fill="{bg}"/>'
                 f'<circle r="{R1 * .18:.0f}" fill="{a1}"/></g>')
        by, bh = h * .74, h * .12
        cid = f"hz{_seed(f'{seed}-{w}-{h}') % 99991}"                # своё имя на каждый узор: на странице их несколько
        o.append(f'<clipPath id="{cid}"><rect x="0" y="{by:.0f}" width="{w}" height="{bh:.0f}"/></clipPath><g clip-path="url(#{cid})"><rect x="0" y="{by:.0f}" width="{w}" height="{bh:.0f}" fill="{ink}"/>'
                 + "".join(f'<path d="M{x:.0f} {by + bh:.0f} L{x + bh:.0f} {by:.0f} H{x + bh * 1.9:.0f} L{x + bh * .9:.0f} {by + bh:.0f}Z" fill="{a1}"/>' for x in range(-int(bh * 2), w + 1, int(bh * 1.8))) + "</g>")
        for i in range(4):
            bx, byy = [(.1, .1), (.9, .1), (.1, .6), (.9, .6)][i]
            o.append(f'<circle cx="{w * bx:.0f}" cy="{h * byy:.0f}" r="{u * .025:.0f}" fill="none" stroke="{mix(bg, ink, .4)}" stroke-width="3"/>')
    elif kind == "botanic":                            # свадьбы: тонкое золотое кольцо и ветви
        u = min(w, h)
        cx, cy = w * (.5 + (r() - .5) * .16), h * .5                # по центру: кадр 5:4 и 16:9 срезает верх и низ
        o.append(f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="{u * .27:.0f}" fill="{sf}"/>')
        o.append(f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="{u * .3:.0f}" fill="none" stroke="{a2}" stroke-width="{u * .006 + 1:.1f}"/>')
        for side, (bx, by, ang) in enumerate(((cx - u * .36, h * .5 + u * .3, -52 - r() * 10), (cx + u * .36, h * .5 + u * .26, -128 + r() * 10),
                                              (cx, h * .5 + u * .36, -90))):
            L = u * (.5 if side < 2 else .34)
            col = [a1, mix(a1, bg, .35), a2][side]
            o.append(f'<g transform="translate({bx:.0f} {by:.0f}) rotate({ang:.0f})"><path d="M0 0 Q{L * .5:.0f} {-L * .06:.0f} {L:.0f} 0" fill="none" stroke="{col}" stroke-width="3"/>')
            for k in range(1, 8):
                px = L * k / 8
                ls = u * (.06 - k * .0045)
                for sgn in (1, -1):
                    o.append(f'<path d="M{px:.0f} 0 q{ls * .5:.0f} {sgn * -ls * .9:.0f} {ls * 1.3:.0f} {sgn * -ls * .7:.0f} q{-ls * .4:.0f} {sgn * ls * .6:.0f} {-ls * 1.3:.0f} {sgn * ls * .7:.0f}Z" fill="{col}"/>')
            o.append("</g>")
    elif kind == "plan":                               # недвижимость: планировка квартиры
        u = min(w, h)
        x0, y0, W2, H2 = w * .12, h * .14, w * .76, h * .72
        st = max(6, u * .016)
        flip = r() < .5
        if flip:
            o.append(f'<g transform="translate({w} 0) scale(-1 1)">')
        o.append(f'<rect x="{x0:.0f}" y="{y0:.0f}" width="{W2:.0f}" height="{H2:.0f}" fill="{bg}"/>')
        sx, sy = x0 + W2 * (.42 + r() * .18), y0 + H2 * (.44 + r() * .16)
        o.append(f'<rect x="{x0:.0f}" y="{y0:.0f}" width="{sx - x0:.0f}" height="{sy - y0:.0f}" fill="{mix(sf, a1, .16)}"/>')
        o.append(f'<rect x="{sx:.0f}" y="{sy:.0f}" width="{x0 + W2 - sx:.0f}" height="{y0 + H2 - sy:.0f}" fill="{mix(sf, a2, .14)}"/>')
        wall = f'stroke="{ink}" stroke-width="{st:.0f}" stroke-linecap="square" fill="none"'
        o.append(f'<rect x="{x0:.0f}" y="{y0:.0f}" width="{W2:.0f}" height="{H2:.0f}" {wall}/>')
        o.append(f'<path d="M{sx:.0f} {y0:.0f}V{sy - H2 * .12:.0f}M{sx:.0f} {sy + H2 * .05:.0f}V{y0 + H2:.0f}M{x0:.0f} {sy:.0f}H{x0 + (sx - x0) * .6:.0f}M{sx + (x0 + W2 - sx) * .3:.0f} {sy:.0f}H{x0 + W2:.0f}" {wall}/>')
        d = H2 * .12                                   # двери — четверть круга
        o.append(f'<path d="M{sx:.0f} {sy - d:.0f} A{d:.0f} {d:.0f} 0 0 1 {sx + d:.0f} {sy:.0f}" fill="none" stroke="{ink}" stroke-width="2" stroke-dasharray="6 5"/>')
        o.append(f'<path d="M{x0 + (sx - x0) * .6:.0f} {sy:.0f} A{d:.0f} {d:.0f} 0 0 0 {x0 + (sx - x0) * .6 + d:.0f} {sy + d:.0f}" fill="none" stroke="{ink}" stroke-width="2" stroke-dasharray="6 5"/>')
        for wx in (x0 + W2 * .18, x0 + W2 * .7):                                 # окна
            o.append(f'<rect x="{wx:.0f}" y="{y0 - st:.0f}" width="{W2 * .14:.0f}" height="{st * 2:.0f}" fill="{bg}" stroke="{ink}" stroke-width="2"/>')
        o.append(f'<rect x="{x0 + W2 * .08:.0f}" y="{y0 + H2 * .1:.0f}" width="{W2 * .16:.0f}" height="{H2 * .24:.0f}" rx="6" fill="{a1}" opacity=".85"/>')
        o.append(f'<circle cx="{sx + (x0 + W2 - sx) * (.4 + r() * .3):.0f}" cy="{y0 + H2 * (.18 + r() * .16):.0f}" r="{u * .07:.0f}" fill="{a2}" opacity=".8"/>')
        o.append(f'<rect x="{sx + (x0 + W2 - sx) * .2:.0f}" y="{sy + (y0 + H2 - sy) * .45:.0f}" width="{(x0 + W2 - sx) * .5:.0f}" height="{(y0 + H2 - sy) * .32:.0f}" rx="8" fill="{mix(sf, ink, .2)}"/>')
        if flip:
            o.append("</g>")
    elif kind == "horizon":                            # туры: солнце, слои гор и волны
        u = min(w, h)
        o.append(f'<circle cx="{w * (.62 + r() * .14):.0f}" cy="{h * .34:.0f}" r="{u * .17:.0f}" fill="{a2}"/>')
        for k, (top, amp, col) in enumerate(((.42, .16, mix(bg, a1, .35)), (.52, .14, mix(bg, a1, .6)), (.62, .1, a1))):
            pts, x, up = [f"0,{h}"], 0.0, True
            while x <= w + 40:
                pts.append(f"{x:.0f},{h * (top + (0 if up else amp * (.6 + r() * .6))):.0f}")
                x += w * (.12 + r() * .14)
                up = not up
            pts.append(f"{w},{h}")
            o.append(f'<polygon points="{" ".join(pts)}" fill="{col}"/>')
        y = h * .76
        o.append(f'<rect x="0" y="{y:.0f}" width="{w}" height="{h - y:.0f}" fill="{ink}"/>')
        for k in range(4):
            yy = y + (h - y) * (.22 + k * .2)
            o.append(f'<path d="M0 {yy:.0f}' + "".join(f" q{w / 16:.0f} {-u * .025:.0f} {w / 8:.0f} 0 t{w / 8:.0f} 0" for _ in range(4)) + f'" fill="none" stroke="{sf}" stroke-opacity="{.5 - k * .1:.2f}" stroke-width="3"/>')
    elif kind == "spots":                              # груминг: пятна, как на шерсти, и косточка
        u = min(w, h)
        for i in range(8):
            cx, cy, s = w * r(), h * r(), u * (.07 + r() * .1)
            col = [a1, a2, mix(bg, ink, .75), mix(bg, a1, .4)][i % 4]
            pts, n = [], 10
            for k in range(n):
                ang = k / n * 6.283
                rr = s * (.86 + r() * .22)
                pts.append((cx + rr * math.cos(ang), cy + rr * math.sin(ang)))
            dd = f"M{(pts[0][0] + pts[-1][0]) / 2:.0f} {(pts[0][1] + pts[-1][1]) / 2:.0f}" + "".join(
                f" Q{pts[k][0]:.0f} {pts[k][1]:.0f} {(pts[k][0] + pts[(k + 1) % n][0]) / 2:.0f} {(pts[k][1] + pts[(k + 1) % n][1]) / 2:.0f}" for k in range(n)) + "Z"
            o.append(f'<path d="{dd}" fill="{col}"/>')
        bx, by, bl = w * .5, h * .5, u * .34
        o.append(f'<g transform="translate({bx:.0f} {by:.0f}) rotate(-24)" fill="{sf}"><rect x="{-bl / 2:.0f}" y="{-u * .035:.0f}" width="{bl:.0f}" height="{u * .07:.0f}"/>'
                 + "".join(f'<circle cx="{sx * bl / 2:.0f}" cy="{sy * u * .045:.0f}" r="{u * .055:.0f}"/>' for sx in (-1, 1) for sy in (-1, 1)) + "</g>")
    elif kind == "sprinkles":                          # торты: посыпка и торт сверху с волнистым краем
        u = min(w, h)
        cx, cy, R1 = w * (.5 + (r() - .5) * .2), h * (.48 + (r() - .5) * .1), u * .32
        sc = "".join(f'<circle cx="{cx + R1 * math.cos(k / 18 * 6.283):.0f}" cy="{cy + R1 * math.sin(k / 18 * 6.283):.0f}" r="{u * .055:.0f}"/>' for k in range(18))
        o.append(f'<g fill="{a2}">{sc}<circle cx="{cx:.0f}" cy="{cy:.0f}" r="{R1:.0f}"/></g><circle cx="{cx:.0f}" cy="{cy:.0f}" r="{R1 * .82:.0f}" fill="{sf}"/>')
        o.append(f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="{R1 * .62:.0f}" fill="none" stroke="{a1}" stroke-width="3" stroke-dasharray="2 12" stroke-linecap="round"/>')
        o.append(f'<circle cx="{cx + R1 * .2:.0f}" cy="{cy - R1 * .22:.0f}" r="{u * .05:.0f}" fill="{mix(a2, ink, .25)}"/>')
        cols = [a1, a2, mix(a2, sf, .5), mix(bg, a1, .5)]
        for i in range(30):
            x, y = w * r(), h * r()
            if (x - cx) ** 2 + (y - cy) ** 2 < (R1 * 1.25) ** 2:
                continue
            s = u * (.018 + r() * .012)
            o.append(f'<rect x="{-s * 1.6:.0f}" y="{-s / 2:.0f}" width="{s * 3.2:.0f}" height="{s:.0f}" rx="{s / 2:.0f}" fill="{cols[i % 4]}" transform="translate({x:.0f} {y:.0f}) rotate({r() * 180:.0f})"/>')
    else:
        o.append(f'<circle cx="{w / 2:.0f}" cy="{h / 2:.0f}" r="{min(w, h) * .3:.0f}" fill="{a1}"/>')
    if mark:
        s = min(w, h) * .2
        o.append(f'<g transform="translate({w - s * 1.5:.0f} {h - s * 1.5:.0f}) scale({s / 24:.2f})" fill="none" stroke="{ink}" stroke-width="1.4" '
                 f'stroke-linecap="round" stroke-linejoin="round" opacity=".55">{(K.MARKS.get(mark) or K.MARKS["spark"])[1]}</g>')
    o.append("</svg>")
    return "".join(o)


def map_svg(pal, seed="m"):
    """Схематичная карта для «Контактов»: улицы и метка (без загрузки чужих карт)."""
    r = _rand(_seed(seed))
    w, h = 640, 420
    bg, ln, a1 = mix(pal["surface"], pal["bg"], .3), mix(pal["surface"], pal["ink"], .1), pal["accent"]
    o = [f'<svg class="art" viewBox="0 0 {w} {h}" preserveAspectRatio="xMidYMid slice" aria-hidden="true" xmlns="http://www.w3.org/2000/svg"><rect width="{w}" height="{h}" fill="{bg}"/>']
    o.append(f'<path d="M0 {h * .72:.0f} C{w * .3:.0f} {h * .62:.0f} {w * .45:.0f} {h * .92:.0f} {w} {h * .8:.0f} V{h} H0Z" fill="{mix(bg, pal["accent2"], .22)}"/>')
    for i in range(7):
        x = w * r()
        o.append(f'<path d="M{x:.0f} -10 L{x + (r() - .5) * 160:.0f} {h + 10}" stroke="{ln}" stroke-width="{6 + r() * 10:.0f}" fill="none"/>')
    for i in range(5):
        y = h * r()
        o.append(f'<path d="M-10 {y:.0f} L{w + 10} {y + (r() - .5) * 120:.0f}" stroke="{ln}" stroke-width="{6 + r() * 12:.0f}" fill="none"/>')
    o.append(f'<path d="M{w / 2} {h * .62:.0f}c-34-40-52-64-52-90a52 52 0 0 1 104 0c0 26-18 50-52 90z" fill="{a1}"/>'
             f'<circle cx="{w / 2}" cy="{h * .62 - 90:.0f}" r="18" fill="{pal["accent_ink"]}"/></svg>')
    return "".join(o)


# ---------- CSS ----------
FONT_DIR = __import__("pathlib").Path(__file__).resolve().parent.parent / "ui" / "assets" / "fonts"
_FONT_DATA = {}


def _font_data(src):
    """Файл шрифта как data: — для предпросмотра в студии (четвёртая рецензия: страница сайта показывается во фрейме без
    allow-same-origin, а такому фрейму браузер не даёт файлов с диска: «Not allowed to load local resource»)."""
    if src not in _FONT_DATA:
        try:
            _FONT_DATA[src] = "data:font/woff2;base64," + base64.b64encode((FONT_DIR / src).read_bytes()).decode()
        except OSError:
            _FONT_DATA[src] = ""
    return _FONT_DATA[src]


def font_faces(fonts, prefix):
    """prefix "data:" — шрифты внутри страницы (предпросмотр студии), "fonts/" — рядом с опубликованным сайтом."""
    out = []
    for key in K.FONTS.get(fonts, K.FONTS["warm"])["files"]:
        for name, src, fam, style, rng in K.FONT_FILES[key]:
            url = (_font_data(src) or "assets/fonts/" + src) if prefix == "data:" else prefix + (src if prefix.endswith("assets/fonts/") else name)
            out.append(f"@font-face{{font-family:\"{fam}\";font-style:{style};font-weight:300 800;font-display:swap;src:url({url}) format(\"woff2\");unicode-range:{rng}}}")
    return "".join(out)


def font_files(fonts):
    """[(имя на сайте, файл в ui/assets/fonts)] — что положить рядом с опубликованным сайтом."""
    return [(n, s) for key in K.FONTS.get(fonts, K.FONTS["warm"])["files"] for n, s, *_ in K.FONT_FILES[key]]


def tone_vars(p):
    """Переменные для четырёх фонов разделов: обычный, второй, тёмный, акцент."""
    dk_btn = p["accent"] if contrast(p["accent"], p["dark"]) >= 3 else p["dark_ink"]
    dk_btn_ink = p["accent_ink"] if dk_btn == p["accent"] else p["dark"]
    ac_btn, ac_btn_ink = p["accent_ink"], p["accent"]
    return {
        "base": (p["bg"], p["ink"], p["muted"], p["accent"], p["accent_ink"], p["line"], p["surface"], readable_on(p["accent"], p["bg"], 4.5)),
        "alt": (p["surface"], p["ink"], readable_on(p["muted"], p["surface"]), p["accent"], p["accent_ink"], mix(p["line"], p["ink"], .06), p["bg"],
                readable_on(p["accent"], p["surface"], 4.5)),
        "dark": (p["dark"], p["dark_ink"], mix(p["dark_ink"], p["dark"], .3), dk_btn, dk_btn_ink, mix(p["dark"], p["dark_ink"], .16),
                 mix(p["dark"], p["dark_ink"], .07), readable_on(dk_btn, p["dark"], 4.5)),
        "accent": (p["accent"], p["accent_ink"], mix(p["accent_ink"], p["accent"], .22), ac_btn, ac_btn_ink, mix(p["accent"], p["accent_ink"], .25),
                   mix(p["accent"], p["accent_ink"], .1), p["accent_ink"]),
    }


BASE_CSS = r"""
*,*::before,*::after{box-sizing:border-box}
html{-webkit-text-size-adjust:100%;scroll-behavior:smooth;scroll-padding-top:84px}
@media (prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
body{margin:0;background:var(--bg);color:var(--ink);font:400 1.0625rem/1.62 var(--fb);overflow-x:hidden;text-rendering:optimizeLegibility}
img,svg{display:block;max-width:100%}
a{color:inherit}
h1,h2,h3{font-family:var(--fh);font-weight:var(--hw);letter-spacing:var(--tr);line-height:1.08;margin:0;text-wrap:balance}
h1{font-size:calc(clamp(2.35rem,5.6vw,4.5rem) * var(--hs,1))}
h2{font-size:calc(clamp(1.8rem,3.7vw,2.9rem) * var(--hs,1));margin-bottom:.45em}
h3{font-size:calc(1.2rem * var(--h3s,1));line-height:1.25}
p{margin:0 0 .9em}p:last-child{margin-bottom:0}
.it h1,.it h2{font-style:italic}
.w{width:min(1160px,100%);margin:0 auto;padding:0 clamp(18px,5vw,40px)}
.s{background:var(--sbg);color:var(--sink);padding:clamp(56px,9vw,116px) 0;position:relative}
.s .mut,.s .lede{color:var(--smut)}
.lede{font-size:1.15rem;max-width:62ch}
.hd2{display:flex;justify-content:space-between;align-items:end;gap:24px;flex-wrap:wrap;margin-bottom:clamp(26px,4vw,48px)}
.hd2>div{max-width:680px}
.t-base{--sbg:var(--c-base-bg);--sink:var(--c-base-ink);--smut:var(--c-base-mut);--sbtn:var(--c-base-btn);--sbtnk:var(--c-base-btnk);--sline:var(--c-base-line);--scard:var(--c-base-card);--slink:var(--c-base-link)}
.t-alt{--sbg:var(--c-alt-bg);--sink:var(--c-alt-ink);--smut:var(--c-alt-mut);--sbtn:var(--c-alt-btn);--sbtnk:var(--c-alt-btnk);--sline:var(--c-alt-line);--scard:var(--c-alt-card);--slink:var(--c-alt-link)}
.t-dark{--sbg:var(--c-dark-bg);--sink:var(--c-dark-ink);--smut:var(--c-dark-mut);--sbtn:var(--c-dark-btn);--sbtnk:var(--c-dark-btnk);--sline:var(--c-dark-line);--scard:var(--c-dark-card);--slink:var(--c-dark-link)}
.t-accent{--sbg:var(--c-accent-bg);--sink:var(--c-accent-ink);--smut:var(--c-accent-mut);--sbtn:var(--c-accent-btn);--sbtnk:var(--c-accent-btnk);--sline:var(--c-accent-line);--scard:var(--c-accent-card);--slink:var(--c-accent-link)}
.btn{display:inline-flex;align-items:center;justify-content:center;gap:.5em;min-height:48px;padding:.75em 1.4em;border-radius:var(--rb);background:var(--sbtn);color:var(--sbtnk);font:700 1rem/1.2 var(--fb);text-decoration:none;border:2px solid var(--sbtn);cursor:pointer;transition:transform .15s,box-shadow .15s}
.btn:hover{transform:translateY(-1px);box-shadow:0 10px 24px -14px var(--sink)}
.btn.ghost{background:transparent;color:var(--sink);border-color:var(--sline)}
.btn.ghost:hover{border-color:var(--sink)}
.btns{display:flex;flex-wrap:wrap;gap:12px;margin-top:28px}
a:focus-visible,.btn:focus-visible,summary:focus-visible,input:focus-visible,textarea:focus-visible{outline:3px solid var(--slink,var(--accent));outline-offset:3px}
.lnk{color:var(--slink);font-weight:700;text-decoration-thickness:2px;text-underline-offset:4px}
.card{background:var(--scard);border-radius:var(--r);padding:clamp(20px,3vw,30px)}
.ph{outline:2px dashed var(--sline);outline-offset:-2px}
.media{border-radius:var(--r);overflow:hidden;background:var(--scard);position:relative}
.media img,.media .art{width:100%;height:100%;object-fit:cover}
.media .art{position:absolute;inset:0}
.chip{display:inline-block;font-size:.8rem;font-weight:700;padding:.3em .8em;border-radius:999px;background:var(--sbtn);color:var(--sbtnk)}
/* шапка */
.hdr{position:sticky;top:0;z-index:20;background:var(--hbg);color:var(--hink);border-bottom:1px solid var(--hline)}
.hdr .w{display:flex;align-items:center;gap:24px;min-height:74px}
.logo{display:inline-flex;align-items:center;gap:12px;text-decoration:none;color:inherit;min-width:0}
.logo b{font:var(--hw) 1.28rem/1.05 var(--fh);letter-spacing:var(--tr);white-space:nowrap}
.logo small{display:block;font-size:.78rem;opacity:.72;font-family:var(--fb);font-weight:500;letter-spacing:0;margin-top:3px;white-space:nowrap}
.lg-badge{width:42px;height:42px;border-radius:50%;background:var(--accent);color:var(--accent-ink);display:grid;place-items:center;flex:none}
.lg-badge svg{width:24px;height:24px}
.lg-plain{color:var(--hacc);flex:none}.lg-plain svg{width:30px;height:30px}
.lg-mono{width:44px;height:44px;border-radius:calc(var(--r) * .6 + 4px);border:2px solid currentColor;display:grid;place-items:center;font:var(--hw) 1.3rem/1 var(--fh);flex:none}
.lg-own{width:46px;height:46px;flex:none}.lg-own svg{width:100%;height:100%}
.nav{display:flex;align-items:center;gap:clamp(14px,2.2vw,30px);margin-left:auto}
.nav a{text-decoration:none;font-weight:600;font-size:.95rem;opacity:.86;padding:6px 0;border-bottom:2px solid transparent;white-space:nowrap}
.nav a:hover,.nav a[aria-current]{opacity:1;border-color:currentColor}
.hdr .btn{--sbtn:var(--hbtn);--sbtnk:var(--hbtnk);min-height:42px;padding:.55em 1.1em;font-size:.95rem}
.mnav{display:none;margin-left:auto}
.mnav summary{list-style:none;cursor:pointer;display:flex;align-items:center;gap:10px;font-weight:700;padding:10px 0}
.mnav summary::-webkit-details-marker{display:none}
.mnav summary i{width:22px;height:2px;background:currentColor;position:relative;display:block}
.mnav summary i::before,.mnav summary i::after{content:"";position:absolute;left:0;width:22px;height:2px;background:currentColor;top:-7px}
.mnav summary i::after{top:7px}
.mnav[open] summary i{background:transparent}.mnav[open] summary i::before{top:0;transform:rotate(45deg)}.mnav[open] summary i::after{top:0;transform:rotate(-45deg)}
.mnav nav{position:absolute;left:0;right:0;top:100%;background:var(--hbg);border-bottom:1px solid var(--hline);padding:10px clamp(18px,5vw,40px) 26px;display:flex;flex-direction:column}
.mnav nav a{font:var(--hw) 1.5rem/1.2 var(--fh);letter-spacing:var(--tr);text-decoration:none;padding:12px 0;border-bottom:1px solid var(--hline)}
.mnav nav .btn{margin-top:18px;font:700 1rem var(--fb)}
.m-center .hdr .w{flex-direction:column;gap:8px;padding-top:18px;padding-bottom:14px}
.m-center .hdr .nav{margin:0 auto;flex-wrap:wrap;justify-content:center}
.m-center .hdr .hdr-cta{display:none}
.m-burger .nav,.m-burger .hdr-cta{display:none}.m-burger .mnav{display:block}.m-burger .hdr{position:relative}
@media (min-width:1000px){
 .m-side .hdr{position:fixed;inset:0 auto 0 0;width:270px;border-bottom:0;border-right:1px solid var(--hline)}
 .m-side .hdr .w{flex-direction:column;align-items:flex-start;height:100%;padding:40px 34px;gap:36px}
 .m-side .hdr .nav{flex-direction:column;align-items:flex-start;margin:0;gap:4px}
 .m-side .hdr .nav a{font:var(--hw) 1.35rem/1.3 var(--fh);letter-spacing:var(--tr)}
 .m-side .hdr .hdr-cta{margin-top:auto}
 .m-side main,.m-side .ftr{margin-left:270px}
 .m-side .logo small{white-space:normal}
}
@media (max-width:999px){.m-side .hdr .nav,.m-side .hdr .hdr-cta{display:none}.m-side .mnav{display:block}.m-side .hdr{position:relative}}
@media (max-width:1180px){.many .hdr .nav,.many .hdr .hdr-cta{display:none}.many .mnav{display:block}.many .hdr{position:relative}}
@media (max-width:860px){
 .hdr{position:relative}.hdr .nav,.hdr .hdr-cta{display:none}.mnav{display:block}
 .m-center .hdr .w{flex-direction:row;padding-top:0;padding-bottom:0}
 .logo small{display:none}
}
/* обложка */
.hero{padding:clamp(48px,8vw,104px) 0}
.hero h1{max-width:16ch}
.hero .lede{margin-top:22px;font-size:clamp(1.08rem,1.6vw,1.28rem)}
.hero .note{margin-top:28px;font-weight:600;font-size:.95rem;display:flex;gap:10px;align-items:center;color:var(--smut)}
.hero .note::before{content:"";width:28px;height:2px;background:currentColor;flex:none}
.h-split .w{display:grid;grid-template-columns:1.08fr .92fr;gap:clamp(28px,5vw,72px);align-items:center}
.h-split .media{aspect-ratio:4/5}
.h-center{text-align:center}.h-center h1{margin:0 auto}.h-center .lede{margin-left:auto;margin-right:auto}.h-center .btns,.h-center .note{justify-content:center}
.h-center .note::before{display:none}
.h-center h1{max-width:20ch}.hero h1.long{font-size:clamp(2.1rem,4.4vw,3.6rem)}
.h-center .hmark{width:76px;height:76px;margin:0 auto 26px;color:var(--slink)}
.h-center .hmark.lg-mono{width:84px;height:84px;font-size:2.1rem;border-radius:50%}
.h-center .wide{margin-top:clamp(36px,6vw,64px);aspect-ratio:21/8}
.h-poster{padding:clamp(40px,7vw,90px) 0 clamp(48px,7vw,90px);overflow:hidden}
.h-poster .w{display:grid;grid-template-columns:1fr minmax(240px,.42fr);gap:clamp(24px,4vw,56px);align-items:end}
.h-poster h1{font-size:clamp(3.3rem,12.5vw,10.5rem);line-height:.88;max-width:none;letter-spacing:calc(var(--tr) - .02em);grid-column:1/-1}
.h-poster .pside{grid-column:2;grid-row:2}
.h-poster .pbig{grid-column:1;grid-row:2;aspect-ratio:16/9;border-radius:var(--r);overflow:hidden;position:relative}
.h-poster .pbig .art,.h-poster .pbig img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}
.h-poster .note{grid-column:1/-1;margin-top:8px;font:var(--hw) clamp(1.1rem,2.3vw,1.6rem)/1.2 var(--fh);color:var(--sink);border-top:2px solid var(--sink);padding-top:18px}
.h-poster .note::before{display:none}
.h-photo{min-height:min(88vh,860px);display:flex;align-items:flex-end;padding:0;color:#fff;isolation:isolate}
.h-photo .bgm{position:absolute;inset:0;z-index:-2}.h-photo .bgm img,.h-photo .bgm .art{width:100%;height:100%;object-fit:cover}
.h-photo::after{content:"";position:absolute;inset:0;z-index:-1;background:linear-gradient(180deg,rgba(0,0,0,.05) 30%,rgba(0,0,0,.72))}
.h-photo .w{padding-bottom:clamp(40px,7vw,90px);padding-top:120px}
.h-photo .lede,.h-photo .note{color:rgba(255,255,255,.88)}
.h-photo .btn.ghost{color:#fff;border-color:rgba(255,255,255,.55)}
/* сетки */
.grid{display:grid;gap:clamp(14px,2vw,22px);grid-template-columns:repeat(auto-fit,minmax(min(100%,240px),1fr))}
.split{display:grid;grid-template-columns:1fr 1fr;gap:clamp(28px,5vw,72px);align-items:center}
.split .media{aspect-ratio:5/4}
.split.top{align-items:start}
/* о нас */
.ab-text .w>div{max-width:760px}.ab-text h2{margin-bottom:.6em}
.ab-text .lede{font-size:clamp(1.12rem,1.8vw,1.35rem);max-width:none}
.facts{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,180px),1fr));gap:0;margin-top:clamp(28px,4vw,44px);border-top:2px solid var(--sink)}
.facts div{padding:20px 20px 0 0}.facts b{display:block;font:var(--hw) clamp(1.6rem,3.2vw,2.4rem)/1.05 var(--fh);letter-spacing:var(--tr)}.facts span{color:var(--smut);font-size:.95rem}
/* услуги */
.svc-card .mk{width:26px;height:26px}
.svc-card .ic{width:52px;height:52px;border-radius:calc(var(--r) * .7 + 6px);display:grid;place-items:center;background:var(--sbg);color:var(--slink);margin-bottom:18px}
.svc-card h3{margin-bottom:8px}.svc-card .pr{margin-top:14px;font-weight:800}
.svc-card{display:flex;flex-direction:column}.svc-card .pr{margin-top:auto;padding-top:14px}
.rows{border-top:1px solid var(--sline)}
.row{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(0,1.4fr) auto;gap:clamp(14px,3vw,40px);padding:clamp(18px,2.6vw,30px) 0;border-bottom:1px solid var(--sline);align-items:baseline}
.row h3{font-size:clamp(1.25rem,2.2vw,1.7rem)}
.row .pr{font-weight:800;white-space:nowrap;text-align:right}
.row.sm{grid-template-columns:minmax(0,1fr) auto;padding:16px 0}
.row.sm h3{font-size:1.1rem;font-family:var(--fb);font-weight:700;letter-spacing:0}
.row.sm p{color:var(--smut);font-size:.95rem;margin-top:3px}
/* меню с точками */
.pm{columns:2 340px;column-gap:clamp(28px,5vw,72px)}
.pm-g{break-inside:avoid;margin-bottom:34px}
.pm-g h3{font-size:1.35rem;margin-bottom:10px;color:var(--slink)}
.pm-r{display:flex;align-items:baseline;gap:10px;padding:9px 0}
.pm-r .t{font-weight:700}.pm-r .d{display:block;color:var(--smut);font-size:.92rem;font-weight:400}
.pm-r .dots{flex:1;border-bottom:2px dotted var(--sline);transform:translateY(-5px);min-width:20px}
.pm-r .pr{font-weight:800;white-space:nowrap}
.pm-r .star{color:var(--slink);margin-left:.3em}
/* тарифы */
.plans{display:grid;gap:clamp(14px,2vw,22px);grid-template-columns:repeat(auto-fit,minmax(min(100%,250px),1fr));align-items:stretch}
.plan{display:flex;flex-direction:column;gap:10px;border:2px solid var(--sline);background:transparent}
.plan .pr{font:var(--hw) clamp(1.8rem,3vw,2.4rem)/1.1 var(--fh);letter-spacing:var(--tr);margin:6px 0 4px}
.plan .btn{margin-top:auto}
.plan.on{background:var(--sbtn);color:var(--sbtnk);border-color:var(--sbtn)}.plan.on .mut{color:inherit;opacity:.8}
.plan.on .btn{background:var(--sbtnk);color:var(--sbtn);border-color:var(--sbtnk)}
.plan .chip{align-self:flex-start;background:var(--sbtnk);color:var(--sbtn)}
.tbl{width:100%;border-collapse:collapse;font-size:1.02rem}
.tbl td{padding:15px 0;border-bottom:1px solid var(--sline);vertical-align:baseline}.tbl td+td{text-align:right;font-weight:800;white-space:nowrap;padding-left:20px}
.tbl small{display:block;color:var(--smut);font-size:.9rem}
/* цены вкладками: радио + CSS, без скриптов */
.tabs{position:relative}
.tb-r{position:absolute;opacity:0;width:1px;height:1px;pointer-events:none}
.tb-l{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:clamp(18px,3vw,30px)}
.tb-l label{cursor:pointer;padding:.6em 1.15em;border-radius:var(--rb);border:1.5px solid var(--sline);font-weight:700;font-size:.98rem;transition:background .15s,color .15s}
.tb-l label:hover{border-color:var(--sink)}
.tb-p{display:none;max-width:860px}
.tb-r:nth-of-type(1):checked~.tb-l label:nth-child(1){background:var(--sbtn);color:var(--sbtnk);border-color:var(--sbtn)}
.tb-r:nth-of-type(1):checked~.tb-ps .tb-p:nth-child(1){display:block}
.tb-r:nth-of-type(2):checked~.tb-l label:nth-child(2){background:var(--sbtn);color:var(--sbtnk);border-color:var(--sbtn)}
.tb-r:nth-of-type(2):checked~.tb-ps .tb-p:nth-child(2){display:block}
.tb-r:nth-of-type(3):checked~.tb-l label:nth-child(3){background:var(--sbtn);color:var(--sbtnk);border-color:var(--sbtn)}
.tb-r:nth-of-type(3):checked~.tb-ps .tb-p:nth-child(3){display:block}
.tb-r:nth-of-type(4):checked~.tb-l label:nth-child(4){background:var(--sbtn);color:var(--sbtnk);border-color:var(--sbtn)}
.tb-r:nth-of-type(4):checked~.tb-ps .tb-p:nth-child(4){display:block}
.tb-r:nth-of-type(5):checked~.tb-l label:nth-child(5){background:var(--sbtn);color:var(--sbtnk);border-color:var(--sbtn)}
.tb-r:nth-of-type(5):checked~.tb-ps .tb-p:nth-child(5){display:block}
.tb-r:nth-of-type(6):checked~.tb-l label:nth-child(6){background:var(--sbtn);color:var(--sbtnk);border-color:var(--sbtn)}
.tb-r:nth-of-type(6):checked~.tb-ps .tb-p:nth-child(6){display:block}
.tb-r:focus-visible~.tb-l{outline:3px solid var(--slink);outline-offset:6px;border-radius:var(--rb)}
/* до и после */
.gal-ba{display:grid;gap:clamp(18px,3vw,32px);grid-template-columns:repeat(auto-fit,minmax(min(100%,440px),1fr))}
.ba{margin:0;display:grid;grid-template-columns:1fr 1fr;gap:6px}
.ba .media{aspect-ratio:4/5}
.ba .media:first-child{border-top-right-radius:0;border-bottom-right-radius:0}.ba .media:nth-child(2){border-top-left-radius:0;border-bottom-left-radius:0}
.ba-l{position:absolute;left:10px;bottom:10px;font:700 .82rem/1 var(--fb);padding:.45em .8em;border-radius:999px;background:var(--bg);color:var(--ink)}
.ba .media:nth-child(2) .ba-l{background:var(--accent);color:var(--accent-ink)}
.ba figcaption{grid-column:1/-1;font-weight:600;margin-top:6px}
/* преимущества */
.ft-i .mk{width:30px;height:30px;color:var(--slink);margin-bottom:16px}
.ft-i h3{margin-bottom:6px}
.ft-big{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,280px),1fr));gap:clamp(24px,4vw,56px)}
.ft-big h3{font-size:clamp(1.6rem,3vw,2.3rem);margin:18px 0 10px}
.ft-big .mk{width:44px;height:44px;color:var(--slink)}
.ft-split{display:grid;grid-template-columns:.9fr 1.1fr;gap:clamp(28px,6vw,90px)}
.ft-split ul{list-style:none;margin:0;padding:0;border-top:1px solid var(--sline)}
.ft-split li{display:grid;grid-template-columns:44px 1fr;gap:16px;padding:22px 0;border-bottom:1px solid var(--sline)}
.ft-split li .mk{width:28px;height:28px;color:var(--slink)}
/* шаги */
.steps{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,160px),1fr));gap:clamp(18px,3vw,34px);counter-reset:st}
.steps li{counter-increment:st;border-top:2px solid var(--sink);padding-top:16px}
.steps li::before{content:counter(st);font:var(--hw) 2.6rem/1 var(--fh);color:var(--slink);display:block;margin-bottom:14px}
.steps.v{grid-template-columns:1fr;max-width:760px;gap:0}
.steps.v li{display:grid;grid-template-columns:72px 1fr;border-top:1px solid var(--sline);padding:22px 0}
.steps.v li::before{margin:0}
/* галерея */
.gal{display:grid;gap:12px;grid-template-columns:repeat(3,1fr)}
.gal figure{margin:0}.gal .media{aspect-ratio:1}
.gal figcaption{font-size:.9rem;color:var(--smut);margin-top:8px}
.gal.mos{grid-template-columns:repeat(4,1fr);grid-auto-rows:minmax(150px,min(19vw,240px));grid-auto-flow:dense}
.gal.mos figure:first-child{grid-column:span 2;grid-row:span 2}
.gal.mos figure.wd{grid-column:span 2}
.gal.mos .media{aspect-ratio:auto;height:100%}
.gal.mos figure{position:relative}.gal.mos figcaption{position:absolute;left:12px;bottom:10px;margin:0;color:#fff;font-weight:600;text-shadow:0 1px 8px rgba(0,0,0,.5)}
.gal.strip{display:flex;overflow-x:auto;scroll-snap-type:x mandatory;padding-bottom:10px}
.gal.strip figure{flex:0 0 min(78%,380px);scroll-snap-align:start}.gal.strip .media{aspect-ratio:4/5}
/* товары */
.prod .media{aspect-ratio:1;margin-bottom:16px}
.prod h3{margin-bottom:4px}.prod .pr{font-weight:800;font-size:1.1rem;margin:10px 0 14px}
.prod{display:flex;flex-direction:column}.prod .btn{margin-top:auto;align-self:flex-start;min-height:42px}
/* программа */
.ag{border-top:2px solid var(--sink)}
.ag>div{display:grid;grid-template-columns:minmax(90px,.32fr) 1fr;gap:clamp(16px,4vw,48px);padding:clamp(16px,2.4vw,26px) 0;border-bottom:1px solid var(--sline)}
.ag b{font:var(--hw) clamp(1.4rem,2.6vw,2rem)/1.1 var(--fh);letter-spacing:var(--tr);color:var(--slink)}
.ag h3{font-size:1.25rem;margin-bottom:4px}
.days .card b{display:block;color:var(--slink);font-weight:800;margin-bottom:8px}
/* отзывы, команда */
.rv blockquote{margin:0;font:var(--hw) clamp(1.2rem,2vw,1.5rem)/1.4 var(--fh);letter-spacing:var(--tr)}
.rv figcaption{margin-top:16px;color:var(--smut)}
.rv figure{margin:0}
.tm .media{aspect-ratio:4/5;margin-bottom:14px}
.tm h3{margin-bottom:2px}
.tm .mono{display:grid;place-items:center;font:var(--hw) 3rem/1 var(--fh);color:var(--slink);background:var(--scard)}
/* вопросы */
.faq{max-width:860px;border-top:1px solid var(--sline)}
.faq details{border-bottom:1px solid var(--sline)}
.faq summary{list-style:none;cursor:pointer;display:flex;justify-content:space-between;gap:20px;padding:22px 0;font-weight:700;font-size:1.1rem}
.faq summary::-webkit-details-marker{display:none}
.faq summary::after{content:"+";font:400 1.6rem/1 var(--fb);color:var(--slink);transition:transform .2s}
.faq details[open] summary::after{transform:rotate(45deg)}
.faq details>div{padding:0 0 22px;color:var(--smut);max-width:68ch}
.faq.two{max-width:none;columns:2 360px;column-gap:clamp(28px,5vw,64px);border:0}
.faq.two details{break-inside:avoid;border-top:1px solid var(--sline);border-bottom:0}
/* ссылки */
.lk{display:flex;flex-direction:column;gap:12px;max-width:560px}
.lk .btn{justify-content:space-between;min-height:58px;font-size:1.05rem}
.lk .btn::after{content:"";width:9px;height:9px;border-top:2px solid currentColor;border-right:2px solid currentColor;transform:rotate(45deg)}
.lk.ls{gap:0}.lk.ls a{padding:16px 0;border-bottom:1px solid var(--sline);font-weight:700;text-decoration:none}
/* призыв */
.cta .w{display:flex;justify-content:space-between;gap:28px;align-items:center;flex-wrap:wrap}
.cta h2{margin:0 0 .3em}.cta .w>div{max-width:640px}
.cta-card .card{text-align:center;padding:clamp(32px,6vw,72px)}.cta-card .card .lede{margin:0 auto}.cta-card .btns{justify-content:center}
/* текст */
.tx .w>div{max-width:720px}.tx.wide .lede{font:var(--hw) clamp(1.4rem,2.6vw,2rem)/1.35 var(--fh);letter-spacing:var(--tr);max-width:none}
/* контакты */
.ct-list{list-style:none;padding:0;margin:22px 0 0;display:grid;gap:16px}
.ct-list li{display:grid;grid-template-columns:28px 1fr;gap:12px;align-items:start}
.ct-list .mk{width:22px;height:22px;color:var(--slink);margin-top:3px}
.ct-list small{display:block;color:var(--smut);font-size:.85rem}
.ct-list a{font-weight:700;text-decoration:none;border-bottom:1px solid var(--sline)}
.ct-map{aspect-ratio:4/3;border-radius:var(--r);overflow:hidden;position:relative;display:block}
.ct-map .art{position:absolute;inset:0;width:100%;height:100%}
.ct-map .btn{position:absolute;left:18px;bottom:18px;min-height:42px}
.ct-band .ct-list{grid-template-columns:repeat(auto-fit,minmax(min(100%,220px),1fr));gap:22px}
/* заявка */
.form{display:grid;gap:12px}
.form label{display:grid;gap:6px;font-weight:600;font-size:.92rem}
.form input,.form textarea{font:inherit;color:var(--ink);background:var(--bg);border:1.5px solid var(--line);border-radius:calc(var(--r) * .6 + 4px);padding:13px 15px;width:100%}
.form textarea{min-height:110px;resize:vertical}
.form .btn{width:100%;margin-top:6px;--sbtn:var(--accent);--sbtnk:var(--accent-ink)}
.form .hp{position:absolute;left:-6000px;width:1px;height:1px;overflow:hidden}
.form small{color:var(--muted);font-size:.8rem}
.form .pdc{display:flex;gap:10px;align-items:flex-start;font-weight:400;font-size:.86rem;line-height:1.45;color:var(--muted);cursor:pointer}
.form .pdc input{width:20px;height:20px;padding:0;margin:1px 0 0;flex:none;accent-color:var(--c-base-btn);cursor:pointer}
.form .pdc a{color:var(--c-base-link);text-underline-offset:3px}
.ld .card{background:var(--bg);color:var(--ink)}
.ld-card .card{max-width:620px;margin:0 auto}
.ld-card .ldh{text-align:center;max-width:620px;margin:0 auto 26px}
.ok{display:none;margin-top:14px;padding:14px 16px;border-radius:calc(var(--r) * .6 + 4px);background:var(--surface);color:var(--ink);font-weight:700}
.ok:target{display:block}
/* подвал */
.ftr{background:var(--dark);color:var(--dark-ink);padding:clamp(44px,7vw,80px) 0 28px;font-size:.95rem}
.ftr .w{display:grid;grid-template-columns:1.3fr 1fr 1fr;gap:32px}
.ftr .mut{color:var(--ftr-mut)}
.ftr nav{display:flex;flex-direction:column;gap:8px}.ftr a{text-decoration:none}.ftr a:hover{text-decoration:underline}
.ftr .bot{grid-column:1/-1;display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap;border-top:1px solid var(--ftr-line);padding-top:20px;margin-top:20px;font-size:.84rem;color:var(--ftr-mut)}
.ftr .bot span{display:flex;gap:18px;flex-wrap:wrap}
.ftr .logo{--hacc:var(--dark-ink)}
/* подвал: наименование, реквизиты и документы (0.87) — тише меню, но читается; задано пусто — строки нет */
.ftr .lgl{grid-column:1/-1;display:flex;justify-content:space-between;align-items:flex-start;gap:14px 48px;flex-wrap:wrap;border-top:1px solid var(--ftr-line);padding-top:22px;margin-top:20px;font-size:.86rem;line-height:1.5;color:var(--ftr-mut)}
.ftr .lgl>div{max-width:62ch}
.ftr .lg-org{margin:0 0 3px;color:var(--dark-ink);font-weight:700;font-size:.92rem}
.ftr .lgl ul{list-style:none;margin:0;padding:0;display:flex;flex-wrap:wrap;gap:3px 18px}
.ftr .lg-docs{justify-content:flex-end;gap:6px 22px}
.ftr .lg-docs a{color:var(--dark-ink);text-decoration:underline;text-decoration-color:var(--ftr-line);text-underline-offset:4px;text-decoration-thickness:1.5px}
.ftr .lg-docs a:hover{text-decoration-color:currentColor}
.ftr .lgl+.bot{border-top:0;padding-top:6px;margin-top:6px}
/* страница документа: оферта, политика… — для чтения, в стиле сайта */
.s.doc{padding-top:clamp(36px,6vw,72px)}
.doc .w{width:min(860px,100%)}
.doc-back{display:inline-block;margin-bottom:clamp(22px,3vw,34px);font-weight:600;font-size:.93rem;color:var(--slink);text-decoration:none;border-bottom:1.5px solid currentColor;padding-bottom:1px}
.doc h1{font-size:calc(clamp(1.9rem,4.2vw,3.1rem) * var(--hs,1));max-width:24ch}
.doc-ed{color:var(--smut);margin:14px 0 clamp(26px,4vw,44px);font-size:.95rem}
.doc-text{max-width:68ch;line-height:1.72;overflow-wrap:anywhere}
.doc-text h2{font-size:calc(1.3rem * var(--h3s,1));line-height:1.3;margin:2em 0 .7em}
.doc-text h2:first-child{margin-top:0}
.doc-text ul{margin:0 0 .9em;padding-left:1.25em}.doc-text li{margin:.3em 0}.doc-text li::marker{color:var(--slink)}
.doc-req{margin-top:clamp(36px,5vw,60px);max-width:68ch}
.doc-req h2{font-size:calc(1.15rem * var(--h3s,1));margin-bottom:.7em}
.doc-req .lg-org{font-weight:700;margin-bottom:.3em}
.doc-req ul{list-style:none;margin:0;padding:0;display:grid;gap:4px;color:var(--smut)}
.doc-req a{color:var(--slink)}
/* «Статьи» (0.93): /blog/ и /blog/<slug> — страницы собирает сервер по шаблону dw-blog.html */
.dw-crumbs{display:flex;flex-wrap:wrap;gap:8px;font-size:.92rem;margin-bottom:clamp(20px,3vw,30px)}.dw-crumbs a{color:var(--slink);text-decoration:none;font-weight:600}.dw-crumbs span{color:var(--smut)}
.dw-meta{display:flex;flex-wrap:wrap;gap:6px 18px;color:var(--smut);font-size:.95rem;margin:14px 0 clamp(26px,4vw,40px)}
.dw-body h3{font-size:calc(1.12rem * var(--h3s,1));line-height:1.35;margin:1.6em 0 .5em}
.dw-body p{margin:0 0 1em}.dw-body ol{margin:0 0 .9em;padding-left:1.4em}.dw-body a{color:var(--slink)}
.dw-body blockquote{margin:1.3em 0;padding:.1em 0 .1em 1.1em;border-left:3px solid var(--slink);color:var(--smut)}
.dw-refs,.dw-more{margin-top:clamp(36px,5vw,56px);max-width:68ch}.dw-more{max-width:none}
.dw-refs>b,.dw-more>b{display:block;font-family:var(--fh);font-weight:var(--hw);font-size:calc(1.12rem * var(--h3s,1));margin-bottom:.8em}
.dw-refs ul{margin:0;padding-left:1.2em;color:var(--smut)}.dw-refs li{margin:.3em 0}.dw-refs a{color:var(--slink);overflow-wrap:anywhere}
.dw-blog h1{margin-bottom:clamp(24px,4vw,40px)}
.dw-posts{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(260px,100%),1fr));gap:clamp(14px,2vw,22px)}
.dw-card{display:flex;flex-direction:column;gap:8px;padding:clamp(18px,2.4vw,26px);border-radius:var(--r);background:var(--scard);color:var(--sink);text-decoration:none;border:1px solid var(--sline);transition:transform .2s,border-color .2s}
.dw-card:hover{border-color:var(--slink);transform:translateY(-2px)}.dw-card:focus-visible{outline:2px solid var(--slink);outline-offset:3px}
.dw-card small{color:var(--smut);font-size:.85rem}.dw-card b{font-family:var(--fh);font-weight:var(--hw);font-size:calc(1.12rem * var(--h3s,1));line-height:1.3}
.dw-card span{color:var(--smut);font-size:.95rem;line-height:1.5}
.dw-pages{display:flex;justify-content:space-between;gap:16px;margin-top:28px}.dw-pages a{color:var(--slink);font-weight:600}
@media (prefers-reduced-motion:reduce){.dw-card{transition:none}.dw-card:hover{transform:none}}
@media (max-width:860px){
 .h-split .w,.split,.ft-split{grid-template-columns:1fr}
 .h-split .media{aspect-ratio:16/10}
 .h-poster .w{grid-template-columns:1fr}.h-poster .pside,.h-poster .pbig{grid-column:1;grid-row:auto}
 .row{grid-template-columns:1fr auto}.row>p{grid-column:1/-1;grid-row:2}
 .gal{grid-template-columns:repeat(2,1fr)}
 .gal.mos{grid-template-columns:repeat(2,1fr);grid-auto-rows:minmax(120px,38vw)}
 .ftr .w{grid-template-columns:1fr}
 .ftr .lgl{flex-direction:column;gap:14px}.ftr .lg-docs{justify-content:flex-start;flex-direction:column;gap:2px}.ftr .lg-docs a{display:inline-block;padding:6px 0}
 .steps.v li{grid-template-columns:52px 1fr}
 .ag>div{grid-template-columns:1fr;gap:4px}
}
@media (max-width:480px){.btns .btn{flex:1 1 100%}.hero h1{word-break:normal;overflow-wrap:anywhere}}
"""

NEW_CSS = r"""
/* 0.94: блоки «Авангарда» — в любом стиле */
.hk{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(0,.9fr);gap:24px;align-items:center}.hk-t{min-width:0}
.hero h1.kin{font-size:calc(clamp(2.6rem,6.4vw,6.2rem) * var(--hs,1));line-height:.9;letter-spacing:calc(var(--tr) - .01em);max-width:11ch}
.hero h1.kin.long{font-size:calc(clamp(2.3rem,5.6vw,5rem) * var(--hs,1));max-width:16ch}
h1 .dot{display:none;font-style:normal;color:var(--slink)}
.hk-art{aspect-ratio:540/520;max-width:100%}
.hk-art svg{width:100%;height:100%;overflow:visible}
.hk-art .kr{fill:none;stroke:var(--sline);stroke-width:1.5}
.hk-art .kt{font:600 34px/1 var(--fh);letter-spacing:.1em}
.hk-art .kd{fill:var(--slink);offset-distance:0%}
@media (max-width:860px){.hk{grid-template-columns:1fr}.hk-art{max-width:520px}}
.st-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,180px),1fr));gap:clamp(18px,3vw,34px)}
.st-c b{display:block;font:var(--hw) clamp(2.6rem,6vw,4.6rem)/.95 var(--fh);letter-spacing:var(--tr);color:var(--slink)}
.st-c span{display:block;margin-top:10px;color:var(--smut)}
.formula{display:flex;flex-wrap:wrap;align-items:flex-end;gap:clamp(10px,2vw,26px)}
.fig{display:grid;gap:10px}
.fig b{font:var(--hw) clamp(4.2rem,14vw,11rem)/.82 var(--fh);letter-spacing:calc(var(--tr) - .02em)}
.fig.f1 b{background:var(--sbtn);color:var(--sbtnk);border-radius:var(--r);padding:.12em .16em .06em}
.fig.f2 b{color:transparent;-webkit-text-stroke:2px var(--slink)}
.fig small{font-size:.82rem;letter-spacing:.1em;text-transform:uppercase;color:var(--smut)}
.formula .op{font:500 clamp(2rem,5vw,4rem)/1 var(--fh);color:var(--slink);padding-bottom:2.2rem}
.sk{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.05fr);gap:clamp(28px,5vw,60px);align-items:center}
.sk-art{position:relative;aspect-ratio:1/1.05;max-width:520px;width:100%}
.sk-pic{position:absolute;inset:10% 14%;border-radius:40% 40% var(--r) var(--r);overflow:hidden;background:var(--scard);border:1.5px solid var(--sline)}
.sk-pic img{width:100%;height:100%;object-fit:cover}
.sk-mono{display:grid;place-items:center}.sk-mono span{font:var(--hw) clamp(4rem,12vw,9rem)/1 var(--fh);color:transparent;-webkit-text-stroke:2px var(--a2)}
.stk{position:absolute;padding:14px 16px;border-radius:calc(var(--r) * .6 + 6px);background:var(--scard);border:1.5px solid var(--sline);max-width:180px;box-shadow:0 20px 40px -24px rgba(0,0,0,.6)}
.stk b{display:block;font:var(--hw) 1.8rem/1 var(--fh);letter-spacing:var(--tr)}
.stk small{display:block;margin-top:6px;font-size:.78rem;line-height:1.3;color:var(--smut)}
.stk.hot{background:var(--sbtn);color:var(--sbtnk);border-color:var(--sbtn)}.stk.hot small{color:inherit;opacity:.75}
.stk.k0{left:0;top:6%;transform:rotate(-6deg)}.stk.k1{right:0;top:0;transform:rotate(5deg)}.stk.k2{left:2%;bottom:8%;transform:rotate(-4deg)}.stk.k3{right:4%;bottom:14%;transform:rotate(7deg)}
@media (max-width:860px){.sk{grid-template-columns:1fr}.sk-art{margin:0 auto}}
.hub{display:grid;grid-template-columns:1fr minmax(180px,260px) 1fr;gap:14px 28px;align-items:center;position:relative}
.hub-r{position:absolute;opacity:0;width:1px;height:1px;pointer-events:none}
.hub-col{display:grid;gap:12px}
.hub .node{display:grid;grid-template-columns:auto 1fr;gap:2px 14px;align-items:center;padding:16px 18px;cursor:pointer;background:var(--scard);border:1.5px solid var(--sline);border-radius:var(--r);transition:border-color .25s,transform .25s}
.hub .node em{font-style:normal;font-size:.75rem;font-weight:700;color:var(--slink);grid-row:span 2}
.hub .node b{font-size:1.2rem;font-weight:600;line-height:1.2}
.hub .node small{font-size:.82rem;color:var(--smut)}
.hub .node:hover{border-color:var(--sink)}
.hub-core{position:relative;aspect-ratio:1;display:grid;place-items:center;text-align:center}
.hub-core svg{position:absolute;inset:0;width:100%;height:100%}
.hub-core .c1{fill:none;stroke:var(--sline);stroke-width:1.5}.hub-core .c2{fill:none;stroke:var(--slink);stroke-width:1.5;stroke-dasharray:4 7}.hub-core .c3{fill:var(--scard)}
.hub-core p{position:relative;margin:0;font:600 1.4rem/1.15 var(--fh);max-width:9ch}
.hub-say{grid-column:1/-1;border-top:1px solid var(--sline);padding-top:20px;margin-top:14px;min-height:5em}
.hub-p{display:none}.hub-p b{display:block;font-size:.8rem;letter-spacing:.12em;text-transform:uppercase;color:var(--smut);margin-bottom:6px}
.hub-p p{font-size:1.12rem;max-width:70ch}
.hub-r:nth-of-type(1):checked~.hub-say .hub-p[data-i="0"],.hub-r:nth-of-type(2):checked~.hub-say .hub-p[data-i="1"],.hub-r:nth-of-type(3):checked~.hub-say .hub-p[data-i="2"],.hub-r:nth-of-type(4):checked~.hub-say .hub-p[data-i="3"],.hub-r:nth-of-type(5):checked~.hub-say .hub-p[data-i="4"],.hub-r:nth-of-type(6):checked~.hub-say .hub-p[data-i="5"],.hub-r:nth-of-type(7):checked~.hub-say .hub-p[data-i="6"],.hub-r:nth-of-type(8):checked~.hub-say .hub-p[data-i="7"]{display:block}
.hub-r:nth-of-type(1):checked~.hub-col .node[data-i="0"],.hub-r:nth-of-type(2):checked~.hub-col .node[data-i="1"],.hub-r:nth-of-type(3):checked~.hub-col .node[data-i="2"],.hub-r:nth-of-type(4):checked~.hub-col .node[data-i="3"],.hub-r:nth-of-type(5):checked~.hub-col .node[data-i="4"],.hub-r:nth-of-type(6):checked~.hub-col .node[data-i="5"],.hub-r:nth-of-type(7):checked~.hub-col .node[data-i="6"],.hub-r:nth-of-type(8):checked~.hub-col .node[data-i="7"]{border-color:var(--slink);background:color-mix(in srgb,var(--slink) 9%,var(--scard))}
.hub-r:focus-visible~.hub-col .node{outline:2px dashed var(--sline);outline-offset:2px}
@media (max-width:860px){.hub{grid-template-columns:1fr}.hub-core{max-width:220px;margin:0 auto;order:-1}}
.duo{display:grid;grid-template-columns:1fr 1fr;gap:18px}
.duo-c{position:relative;overflow:hidden;border-radius:calc(var(--r) + 6px);padding:clamp(22px,3vw,30px);min-height:260px;display:flex;flex-direction:column}
.duo-c.d0{background:var(--sbtn);color:var(--sbtnk)}
.duo-c.d1{background:var(--scard);border:1.5px solid var(--sline)}
.duo-c .dr{display:flex;justify-content:space-between;align-items:center;font-size:.75rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase}
.duo-c .dr i{font-style:normal;padding:6px 12px;border-radius:999px;box-shadow:inset 0 0 0 1.5px currentColor;letter-spacing:.06em}
.duo-c .num{position:absolute;right:18px;top:70px;font:var(--hw) 8rem/.8 var(--fh);letter-spacing:-.06em;opacity:.14;pointer-events:none}
.duo-c.d1 .num{opacity:1;color:transparent;-webkit-text-stroke:2px var(--sline)}
.duo-c h3{font-size:calc(clamp(1.5rem,2.6vw,2.1rem) * var(--h3s,1));margin:34px 0 10px;max-width:14ch;line-height:1.05}
.duo-c p{max-width:36ch}.duo-c.d1 p{color:var(--smut)}
.duo-c .foot{margin-top:auto;padding:22px 0 10px;border-bottom:1.5px solid currentColor;font-size:.75rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase}
.duo-c.d1 .foot{border-color:var(--sline);color:var(--smut)}
@media (max-width:760px){.duo{grid-template-columns:1fr}.duo-c .num{font-size:5rem;top:56px}}
.bars{display:grid;gap:18px;max-width:900px}
.br{display:grid;grid-template-columns:minmax(0,190px) 1fr 80px;gap:16px;align-items:center;font-size:.95rem}
.br .tr{height:10px;border-radius:10px;background:color-mix(in srgb,var(--sline) 70%,transparent);overflow:hidden}
.br .tr i{display:block;height:100%;border-radius:10px;background:var(--a2);transform-origin:left}
.br.on .tr i{background:var(--slink)}
.br b{text-align:right;font-variant-numeric:tabular-nums}
@media (max-width:620px){.br{grid-template-columns:1fr 64px}.br .tr{grid-column:1/-1;grid-row:2}}
.cs{timeline-scope:--cs}
.cs-hint{color:var(--slink);font-weight:700}
.cs-rail{display:grid;grid-auto-flow:column;grid-auto-columns:calc((100% - 18px) / 2);gap:18px;overflow-x:auto;scroll-snap-type:x mandatory;padding-bottom:14px;scroll-timeline:--cs x;scrollbar-width:thin;scrollbar-color:var(--slink) transparent}
.case{scroll-snap-align:start;display:flex;flex-direction:column;gap:14px;min-width:0}
.case header{display:flex;justify-content:space-between;font-weight:600}.case header em{font-style:normal;color:var(--smut)}
.case .media{aspect-ratio:16/10}
.case-viz{aspect-ratio:16/10;border-radius:calc(var(--r) * .7);background:var(--sbg);border:1.5px solid var(--sline);padding:16px 18px;display:grid;grid-template-rows:auto 1fr;gap:6px;overflow:hidden}
.case-viz b{font:var(--hw) clamp(2rem,4vw,3rem)/1 var(--fh);letter-spacing:var(--tr);color:var(--slink)}.case-viz small{display:block;color:var(--smut);font-size:.8rem;margin-top:4px}
.case-viz svg{width:100%;height:100%}.case-viz .ln{fill:none;stroke:var(--slink);stroke-width:2.5;stroke-linejoin:round;stroke-linecap:round}.case-viz .ar{fill:var(--slink);opacity:.12}.case-viz .gd{stroke:var(--sline);stroke-width:1}
.case .meter{align-self:flex-start;margin-top:auto;padding:10px 14px;border-radius:calc(var(--r) * .6 + 4px);border:1.5px solid var(--sline)}
.case .meter b{display:block;font:var(--hw) 1.6rem/1 var(--fh);letter-spacing:var(--tr)}.case .meter small{color:var(--smut)}
.cs-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,300px),1fr));gap:18px}
.cs-bar{display:none;height:3px;border-radius:3px;background:var(--sline);margin-top:14px;overflow:hidden}
.cs-bar i{display:block;height:100%;width:100%;background:var(--slink);transform-origin:left;transform:scaleX(.2)}
@supports (animation-timeline:scroll()){.cs-bar{display:block}.cs-rail{scrollbar-width:none}.cs-rail::-webkit-scrollbar{display:none}
 .cs-bar i{animation:dwBar linear both;animation-timeline:--cs}}
@keyframes dwBar{from{transform:scaleX(.2)}to{transform:scaleX(1)}}
@media (max-width:760px){.cs-rail{grid-auto-columns:86%}}
.plan .pr{white-space:nowrap}.plan .old{color:var(--smut);font-weight:600}.plan.on .old{color:inherit;opacity:.6}
.rms{columns:3 280px;column-gap:18px}
.rm{break-inside:avoid;margin:0 0 18px;display:block}
.rm blockquote{font:400 1.02rem/1.55 var(--fb);letter-spacing:0}
.rm figcaption{display:flex;align-items:center;gap:12px;margin-top:16px;color:inherit}
.rm figcaption i{font-style:normal;flex:none;width:36px;height:36px;border-radius:50%;display:grid;place-items:center;font:700 .75rem/1 var(--fh);background:var(--sbg);color:var(--slink)}
.rm figcaption small{display:block;opacity:.7}
.rm.acc{background:var(--sbtn);color:var(--sbtnk)}.rm.a2{background:var(--a2);color:var(--dark)}
.snake{position:relative;display:grid;gap:0}
.sn-row{list-style:none;margin:0;padding:0 56px 0 0;display:grid;grid-template-columns:repeat(4,1fr);position:relative}
.sn-row.rev{direction:rtl}.sn-row.rev>li{direction:ltr}
.sn-row::before{content:"";position:absolute;left:12.5%;right:calc(12.5% + 56px);top:37px;border-top:2px dashed var(--sline)}
.sn-s{position:relative;display:grid;justify-items:center;gap:10px;text-align:center;padding:0 6px 26px}
.sn-s .n{position:relative;z-index:1;width:74px;height:74px;border-radius:20px;display:grid;place-items:center;font:var(--hw) 1.7rem/1 var(--fh);letter-spacing:var(--tr);background:var(--sbg);border:2px solid var(--sline)}
.sn-s .n.c1{color:var(--slink);border-color:var(--slink)}.sn-s .n.c2{color:var(--a2)}.sn-s .n.c3{color:var(--a2)}
.sn-s b{font-weight:600;max-width:15ch}.sn-s small{color:var(--smut);max-width:22ch}
.sn-turn{height:44px;margin:-26px 0 0;position:relative}
.sn-turn::before{content:"";position:absolute;top:-36px;bottom:-37px;width:60px;border:2px dashed var(--sline)}
.sn-turn.r::before{right:12px;border-left:0;border-radius:0 60px 60px 0}
.sn-turn.l::before{left:calc(12.5% - 48px);border-right:0;border-radius:60px 0 0 60px}
@media (max-width:760px){.sn-row,.sn-row.rev{grid-template-columns:1fr;direction:ltr;padding:0}.sn-row::before,.sn-turn{display:none}
 .sn-s{grid-template-columns:56px 1fr;justify-items:start;text-align:left;align-items:center;padding:0 0 14px}.sn-s .n{width:52px;height:52px;font-size:1.2rem;grid-row:span 2}}
.vh{position:absolute!important;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
.s.tkr{padding:clamp(16px,2.4vw,24px) 0;overflow:hidden}
.tk{overflow:hidden}
.tk-t{display:flex;width:max-content;animation:dwTick 36s linear infinite}
.tk-t span{font:var(--hw) clamp(1.3rem,2.8vw,2.2rem)/1 var(--fh);letter-spacing:var(--tr);white-space:nowrap;padding-right:1.4em;display:inline-flex;align-items:center;gap:1.4em}
.tk-t span::after{content:"✦";font-size:.7em;opacity:.8}
@keyframes dwTick{to{transform:translateX(-50%)}}
@media (prefers-reduced-motion:reduce){.tk-t{animation:none}}
"""

POSTER_CSS = r"""
/* 0.94 стиль «Афиша»: узкий шрифт огромными буквами, обводки и жёсткие тени, наклейки, бегущая строка */
.sty-poster h1,.sty-poster h2,.sty-poster h3{text-transform:uppercase;letter-spacing:.005em}
.sty-poster h1{font-size:calc(clamp(3rem,9vw,8.4rem) * var(--hs,1));line-height:.88}
.sty-poster .hero h1.kin{font-size:calc(clamp(3rem,8.4vw,8rem) * var(--hs,1));line-height:.86;max-width:12ch}
.sty-poster .hero .lede{margin-top:40px}
.sty-poster h2{font-size:calc(clamp(2.4rem,6vw,5.2rem) * var(--hs,1));line-height:.9}
.sty-poster .btn{border-radius:0;border:2px solid var(--sink);box-shadow:5px 5px 0 var(--sink);text-transform:uppercase;letter-spacing:.04em;font-weight:800}
.sty-poster .btn:hover{transform:translate(-2px,-2px);box-shadow:7px 7px 0 var(--sink)}
.sty-poster .btn.ghost{background:var(--sbg)}
.sty-poster .card,.sty-poster .duo-c,.sty-poster .stk,.sty-poster .node,.sty-poster .bars{border:2px solid var(--sink);box-shadow:6px 6px 0 var(--sink);border-radius:0}
.sty-poster .duo-c.d1{background:var(--sbg)}
.sty-poster .media{border:2px solid var(--sink);border-radius:0}
.sty-poster .hd2>div>h2{display:inline}
.sty-poster .hd2>div:first-child::before{content:"";display:block;width:64px;height:10px;background:var(--slink);margin-bottom:18px}
.sty-poster .tkr .tk-t span{text-transform:uppercase}
.sty-poster .chip,.sty-poster .star{transform:rotate(-4deg);display:inline-block}
.sty-poster .hero .note{display:inline-flex;padding:8px 14px;border:2px solid var(--sink);background:var(--a2);color:var(--dark-ink);transform:rotate(-2deg);margin-top:30px}
.sty-poster .hero .note::before{display:none}
.sty-poster .pm-g h3{display:inline-block;background:var(--sink);color:var(--sbg);padding:4px 10px;transform:rotate(-2deg)}
.sty-poster .st-c b{font-size:clamp(3rem,8vw,6.4rem);line-height:.85}
.sty-poster .hk-art .kt{font-family:var(--fh);text-transform:uppercase;letter-spacing:.06em;font-size:40px}
@media (prefers-reduced-motion:no-preference){
 .sty-poster .stk:hover,.sty-poster .card:hover{transform:rotate(-1deg) translate(-2px,-2px)}
 .sty-poster .hk-art .kt{animation:dwFloat 6s ease-in-out infinite alternate}.sty-poster .hk-art .kd{animation:dwRun 10s linear infinite}
 @supports (animation-timeline:view()){
  .sty-poster .hd2,.sty-poster .card,.sty-poster .duo-c,.sty-poster .st-c{animation:dwSlide linear both;animation-timeline:view();animation-range:entry 0% entry 70%}
  .sty-poster .br .tr i{animation:dwGrow linear both;animation-timeline:view();animation-range:entry 20% cover 45%}}
}
@keyframes dwSlide{from{opacity:.3;transform:translateX(-36px) rotate(-1.5deg)}to{opacity:1;transform:none}}
"""

ATELIER_CSS = r"""
/* 0.94 стиль «Ателье»: крупные лёгкие засечки, курсив в акцентах, тонкие линии, арки, много воздуха */
.sty-atelier{--hw:500}
.sty-atelier h1,.sty-atelier h2{font-weight:500;letter-spacing:-.01em}
.sty-atelier h1,.sty-atelier .hero h1{font-size:calc(clamp(2.6rem,5.4vw,5rem) * var(--hs,1));line-height:1}
.sty-atelier h2{font-size:calc(clamp(2.2rem,4.8vw,4.2rem) * var(--hs,1));line-height:1.02;font-style:italic}
.sty-atelier .s{padding:clamp(72px,11vw,140px) 0}
.sty-atelier .hd2{border-top:1px solid var(--sline);padding-top:22px}
.sty-atelier main{counter-reset:sec}
.sty-atelier .hd2>div:first-child::before{counter-increment:sec;content:counter(sec,upper-roman);display:block;font:500 1rem/1 var(--fh);font-style:italic;color:var(--slink);margin-bottom:12px}
.sty-atelier .btn{border-radius:999px;background:transparent;color:var(--sink);border:1px solid var(--sink);font-weight:600;letter-spacing:.02em}
.sty-atelier .btn:not(.ghost){background:var(--sbtn);color:var(--sbtnk);border-color:var(--sbtn)}
.sty-atelier .media,.sty-atelier .sk-pic{border-radius:999px 999px var(--r) var(--r)}
.sty-atelier .h-split .media{aspect-ratio:3/4}
.sty-atelier .card,.sty-atelier .node,.sty-atelier .duo-c.d1,.sty-atelier .stk{background:transparent;border:1px solid var(--sline);box-shadow:none}
.sty-atelier .tbl td{padding-block:20px}
.sty-atelier .st-c b{font-weight:500;font-style:italic}
.sty-atelier .st-c{border-top:1px solid var(--sline);padding-top:18px}
.sty-atelier .hub-core .c2{stroke-dasharray:1 6;stroke-linecap:round}
@media (prefers-reduced-motion:no-preference){@supports (animation-timeline:view()){
 .sty-atelier .hd2,.sty-atelier .media,.sty-atelier .card,.sty-atelier .st-c,.sty-atelier .node{animation:dwSoft linear both;animation-timeline:view();animation-range:entry 0% entry 80%}}}
@keyframes dwSoft{from{opacity:.25;filter:blur(6px);transform:translateY(16px)}to{opacity:1;filter:none;transform:none}}
"""

AV_CSS = r"""
/* 0.94 стиль «Авангард»: широкий шрифт крупно, разделы по номерам, капсулы, движение при прокрутке (только CSS) */
.sty-avangard{--rb:999px}
.sty-avangard h1,.sty-avangard h2{letter-spacing:var(--tr)}
.sty-avangard h2{font-size:calc(clamp(1.9rem,4.6vw,3.9rem) * var(--hs,1));line-height:1;max-width:18ch}
.sty-avangard h1 .dot{display:inline}
.sty-avangard main{counter-reset:sec}
.sty-avangard .hd2>div:first-child::before{counter-increment:sec;content:counter(sec,decimal-leading-zero) " /";display:block;font:600 .75rem/1 var(--fb);letter-spacing:.14em;color:var(--smut);margin-bottom:14px}
.sty-avangard .hero .hd2>div:first-child::before,.sty-avangard .sk-t>div:first-child::before{content:none}
.sty-avangard .btn{border-radius:999px;padding:.9em 1.6em;font-size:1.02rem}
.sty-avangard .btn:not(.ghost)::after{content:"→";font-weight:700;transition:transform .2s}
.sty-avangard .btn:hover::after{transform:translateX(3px)}
.sty-avangard .hdr{background:color-mix(in srgb,var(--hbg) 84%,transparent);backdrop-filter:blur(14px)}
@media (min-width:861px){.sty-avangard.m-top .hdr .nav{padding:4px;border-radius:999px;box-shadow:inset 0 0 0 1px var(--hline);gap:2px;margin:0 auto}
 .sty-avangard.m-top .hdr .nav a{padding:8px 16px;border-radius:999px;border:0;font-size:.88rem}
 .sty-avangard.m-top .hdr .nav a:hover,.sty-avangard.m-top .hdr .nav a[aria-current]{background:var(--c-alt-card,rgba(127,127,127,.12))}}
.sty-avangard .hero .note{letter-spacing:.02em}
.sty-avangard .hero .note::before{display:none}
.sty-avangard .card{border:1.5px solid var(--sline)}
.sty-avangard .plan.on{border-color:var(--sbtn)}
.sty-avangard .plan .pr{font-size:clamp(2.4rem,4.4vw,3.6rem);letter-spacing:-.05em}
.sty-avangard .faq details,.sty-avangard .faq .qa{border-radius:var(--r)}
@media (prefers-reduced-motion:no-preference){
 .sty-avangard .hk-art .kt{animation:dwFloat 7s ease-in-out infinite alternate}
 .sty-avangard .hk-art .kt1{animation-duration:9s;animation-delay:-2s}.sty-avangard .hk-art .kt2{animation-duration:8s;animation-delay:-4s}
 .sty-avangard .hk-art .kd{animation:dwRun 11s linear infinite}.sty-avangard .hk-art .kd1{animation-duration:14s;animation-delay:-5s}.sty-avangard .hk-art .kd2{animation-duration:12s;animation-delay:-8s}
 .sty-avangard .hub-core .c2{animation:dwSpin 40s linear infinite;transform-origin:130px 130px}
 @supports (animation-timeline:view()){
  .sty-avangard .hd2,.sty-avangard .card,.sty-avangard .duo-c,.sty-avangard .stk,.sty-avangard .fig,.sty-avangard .st-c,.sty-avangard .node,.sty-avangard .sn-s{animation:dwRise linear both;animation-timeline:view();animation-range:entry 0% entry 70%}
  .sty-avangard .br .tr i{animation:dwGrow linear both;animation-timeline:view();animation-range:entry 20% cover 45%}
  .sty-avangard .sn-row::before{transform-origin:left;animation:dwGrow linear both;animation-timeline:view();animation-range:entry 30% cover 50%}
 }
}
@keyframes dwRise{from{opacity:.3;transform:translateY(30px)}to{opacity:1;transform:none}}
@keyframes dwGrow{from{transform:scaleX(0)}to{transform:scaleX(1)}}
@keyframes dwFloat{from{transform:translateX(-10px)}to{transform:translateX(14px)}}
@keyframes dwRun{from{offset-distance:0%}to{offset-distance:100%}}
@keyframes dwSpin{to{transform:rotate(360deg)}}
"""

PREVIEW_CSS = """
html.pv [data-b]{cursor:pointer}
html.pv [data-b]:hover{box-shadow:inset 0 0 0 3px rgba(120,110,255,.55)}
html.pv [data-b].sel{box-shadow:inset 0 0 0 3px #7c6cff}
html.pv .todo{outline:2px dashed #e0a100;outline-offset:2px}
.pvph{position:absolute;left:10px;top:10px;font:600 12px/1.2 system-ui,sans-serif;background:rgba(0,0,0,.55);color:#fff;padding:4px 8px;border-radius:6px}
"""

# скрипт ТОЛЬКО для предпросмотра в студии (в опубликованный сайт не попадает): выбрать блок щелчком, свои страницы — без
# перехода, внешние ссылки и форма — никуда
PREVIEW_JS = """<script>
document.addEventListener('click',function(e){var a=e.target.closest('a');if(a){e.preventDefault();var h=a.getAttribute('href')||'';
 if(/^[a-z0-9_-]+\\.html/.test(h)){parent.postMessage({dwsite:'page',slug:h.split('.html')[0]},'*');return;}
 if(h.charAt(0)==='#'){var t=document.getElementById(h.slice(1));if(t)t.scrollIntoView({behavior:'smooth'});}}
 var b=e.target.closest('[data-b]');if(b&&!e.target.closest('summary')){document.querySelectorAll('.sel').forEach(function(x){x.classList.remove('sel')});b.classList.add('sel');parent.postMessage({dwsite:'pick',id:b.getAttribute('data-b')},'*');}},true);
document.addEventListener('submit',function(e){e.preventDefault();var ok=e.target.querySelector('.ok');if(ok){ok.style.display='block';}},true);
var sct=0;window.addEventListener('scroll',function(){clearTimeout(sct);sct=setTimeout(function(){parent.postMessage({dwsite:'scroll',y:window.scrollY},'*')},90)});
window.addEventListener('load',function(){parent.postMessage({dwsite:'ready'},'*')});
window.addEventListener('message',function(e){var d=e.data||{};if(d.dwsite==='scrollTo'){window.scrollTo(0,d.y||0);if(d.sel){var q=document.querySelector('[data-b="'+d.sel+'"]');if(q)q.classList.add('sel');}return;}
 if(d.dwsite==='show'){var b=document.querySelector('[data-b="'+d.id+'"]');
 document.querySelectorAll('.sel').forEach(function(x){x.classList.remove('sel')});if(b){b.classList.add('sel');b.scrollIntoView({behavior:'smooth',block:'start'});}}});
</script>"""


def style_of(site):
    s = (site.get("theme") or {}).get("style")
    return s if s in K.STYLES else "classic"


def css(site, mode="preview"):
    th = site.get("theme") or {}
    p = colors(th)
    f = K.FONTS.get(th.get("fonts") or "", K.FONTS["warm"])
    rd = K.RADII.get(th.get("radius") or "", K.RADII["soft"])
    hdr = th.get("header") or "light"
    hb = {"light": (p["bg"], p["ink"], p["line"], p["accent"], p["accent_ink"], readable_on(p["accent"], p["bg"], 3)),
          "dark": (p["dark"], p["dark_ink"], mix(p["dark"], p["dark_ink"], .14), *tone_vars(p)["dark"][3:5],
                   p["accent2"] if contrast(p["accent2"], p["dark"]) >= 3 else p["dark_ink"]),
          "accent": (p["accent"], p["accent_ink"], mix(p["accent"], p["accent_ink"], .2), p["accent_ink"], p["accent"], p["accent_ink"])}[hdr if hdr in ("light", "dark", "accent") else "light"]
    v = {"bg": p["bg"], "ink": p["ink"], "muted": p["muted"], "accent": p["accent"], "accent-ink": p["accent_ink"], "surface": p["surface"],
         "line": p["line"], "dark": p["dark"], "dark-ink": p["dark_ink"], "a2": p["accent2"], "fh": f["head"], "fb": f["body"], "hw": str(f["hw"]),
         "tr": f["track"], "hs": str(f.get("scale", 1)), "h3s": str(f.get("scale3", 1)), "r": f"{rd['r']}px", "rb": f"{rd['btn']}px", "hbg": hb[0], "hink": hb[1], "hline": hb[2], "hbtn": hb[3], "hbtnk": hb[4], "hacc": hb[5],
         "ftr-mut": mix(p["dark_ink"], p["dark"], .32), "ftr-line": mix(p["dark"], p["dark_ink"], .16)}
    for tone, vals in tone_vars(p).items():
        for k, val in zip(("bg", "ink", "mut", "btn", "btnk", "line", "card", "link"), vals):
            v[f"c-{tone}-{k}"] = val
    root = ":root{" + ";".join(f"--{k}:{val}" for k, val in v.items()) + ";color-scheme:" + ("dark" if lum(p["bg"]) < .2 else "light") + "}"
    prefix = "data:" if mode == "preview" else "fonts/"
    sty = {"avangard": AV_CSS, "poster": POSTER_CSS, "atelier": ATELIER_CSS}.get(style_of(site), "")
    return font_faces(th.get("fonts") or "warm", prefix) + root + BASE_CSS + NEW_CSS + sty + (PREVIEW_CSS if mode == "preview" else "")


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
    """152-ФЗ: задана политика обработки ПД — в форме заявки галочка «Даю согласие…» со ссылками (обязательная);
    pd_need — серверу (sites.php), чтобы без галочки заявку не принять и без браузера."""
    pol = legal_href(c.site, "privacy")
    if not pol:
        return ""
    con = legal_href(c.site, "consent")
    lk = lambda h, t: f'<a href="{E(h)}" target="_blank" rel="noopener">{t}</a>'
    txt = (f'Даю {lk(con, "согласие на обработку персональных данных")} в соответствии с {lk(pol, "политикой конфиденциальности")}' if con
           else f'Даю согласие на обработку персональных данных в соответствии с {lk(pol, "политикой конфиденциальности")}')
    return (f'<input type="hidden" name="pd_need" value="1"><label class="pdc"><input type="checkbox" name="pd_ok" value="1" required>'
            f'<span>{txt}</span></label>')


def lead_form(b, c):
    pg = slug_of(c.pages[c.page_i], c.page_i) if c.pages else "index"
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


RENDER = {"hero": b_hero, "about": b_about, "services": b_services, "prices": b_prices, "features": b_features, "steps": b_steps,
          "gallery": b_gallery, "products": b_products, "schedule": b_schedule, "reviews": b_reviews, "team": b_team, "faq": b_faq,
          "links": b_links, "cta": b_cta, "text": b_text, "contacts": b_contacts, "lead": b_lead,
          "stats": b_stats, "hub": b_hub, "duo": b_duo, "bars": b_bars, "cases": b_cases, "ticker": b_ticker}
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
                    out.append("<p>" + "<br>".join(E(x) for x in para_lines) + "</p>")
                    para_lines = []
                items.append(f"<li>{E(mm.group(1))}</li>")
            else:
                if items:
                    out.append("<ul>" + "".join(items) + "</ul>")
                    items = []
                para_lines.append(ln)
        if para_lines:
            out.append("<p>" + "<br>".join(E(x) for x in para_lines) + "</p>")
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
