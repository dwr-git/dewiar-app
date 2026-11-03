"""«Сайты»: JSON сайта -> статичный адаптивный HTML + CSS (sites_kit — детали, sites.py — работа с сайтами).

Режимы (mode):
  • "preview" — для студии: одна страница целиком (CSS внутри), картинки data:, шрифты из ui/assets/fonts, у блоков
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
def font_faces(fonts, prefix):
    out = []
    for key in K.FONTS.get(fonts, K.FONTS["warm"])["files"]:
        for name, src, fam, style, rng in K.FONT_FILES[key]:
            url = prefix + (src if prefix.endswith("assets/fonts/") else name)
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
h3{font-size:1.2rem;line-height:1.25}
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
.steps{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,190px),1fr));gap:clamp(18px,3vw,34px);counter-reset:st}
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
@media (max-width:860px){
 .h-split .w,.split,.ft-split{grid-template-columns:1fr}
 .h-split .media{aspect-ratio:16/10}
 .h-poster .w{grid-template-columns:1fr}.h-poster .pside,.h-poster .pbig{grid-column:1;grid-row:auto}
 .row{grid-template-columns:1fr auto}.row>p{grid-column:1/-1;grid-row:2}
 .gal{grid-template-columns:repeat(2,1fr)}
 .gal.mos{grid-template-columns:repeat(2,1fr);grid-auto-rows:minmax(120px,38vw)}
 .ftr .w{grid-template-columns:1fr}
 .steps.v li{grid-template-columns:52px 1fr}
 .ag>div{grid-template-columns:1fr;gap:4px}
}
@media (max-width:480px){.btns .btn{flex:1 1 100%}.hero h1{word-break:normal;overflow-wrap:anywhere}}
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
         "tr": f["track"], "hs": str(f.get("scale", 1)), "r": f"{rd['r']}px", "rb": f"{rd['btn']}px", "hbg": hb[0], "hink": hb[1], "hline": hb[2], "hbtn": hb[3], "hbtnk": hb[4], "hacc": hb[5],
         "ftr-mut": mix(p["dark_ink"], p["dark"], .32), "ftr-line": mix(p["dark"], p["dark_ink"], .16)}
    for tone, vals in tone_vars(p).items():
        for k, val in zip(("bg", "ink", "mut", "btn", "btnk", "line", "card", "link"), vals):
            v[f"c-{tone}-{k}"] = val
    root = ":root{" + ";".join(f"--{k}:{val}" for k, val in v.items()) + ";color-scheme:" + ("dark" if lum(p["bg"]) < .2 else "light") + "}"
    prefix = "assets/fonts/" if mode == "preview" else "fonts/"
    return font_faces(th.get("fonts") or "warm", prefix) + root + BASE_CSS + (PREVIEW_CSS if mode == "preview" else "")


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
    for j, b in enumerate(pages[0].get("blocks") or [] if pages else []):
        if b.get("nav") and not b.get("hidden"):
            out.append((b["nav"], f"#{anchor(b, j)}", False))
    return out[:7]


def header(site, c):
    m = menu_items(site, c)
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
                         f'<div class="pr">{one(x.get("price"))}</div>{para(x.get("text"), "mut")}{bt}</article>')
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
    html_g, star = "", '<span class="star" title="Советуем">★</span>'
    for g in order:
        rows = "".join(f'<div class="pm-r"><span class="t">{one(x.get("title"))}{star if x.get("featured") else ""}'
                       f'{opt("span", x.get("text"), "d")}</span>'
                       f'<i class="dots"></i><b class="pr">{one(x.get("price"))}</b></div>' for x in groups[g])
        html_g += f'<div class="pm-g">{f"<h3>{E(g)}</h3>" if g else ""}{rows}</div>'
    return f'<div class="w">{head2(b, btns(b, c))}<div class="pm">{html_g}</div></div>'


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
    lis = "".join(f'<li><div><h3>{one(x.get("title"))}</h3>{para(x.get("text"), "mut")}</div></li>' for x in items(b, c))
    return f'<div class="w">{head2(b)}<ol class="steps{" v" if v == "list" else ""}">{lis}</ol></div>'


def b_gallery(b, c, v):
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


def lead_form(b, c):
    pg = slug_of(c.pages[c.page_i], c.page_i) if c.pages else "index"
    action = "/__lead" if c.mode == "publish" else "#"
    msg = '<label>Комментарий<textarea name="note" maxlength="600"></textarea></label>' if b.get("ask_message") else ""
    return (f'<form class="form" method="post" action="{action}"><input type="hidden" name="page" value="{E(pg)}">'
            f'<div class="hp" aria-hidden="true"><label>Не заполняйте<input name="website" tabindex="-1" autocomplete="off"></label></div>'
            f'<label>Как вас зовут<input name="name" maxlength="80" autocomplete="name" required></label>'
            f'<label>Телефон или почта<input name="contact" maxlength="120" autocomplete="tel" inputmode="email" required></label>{msg}'
            f'<button class="btn" type="submit">{one(b.get("button") or "Отправить")}</button>'
            f'<small>Нажимая кнопку, вы соглашаетесь, что с вами свяжутся по этим контактам.</small>'
            f'<p class="ok" id="lead-ok" role="status">{one(b.get("thanks") or "Спасибо! Скоро свяжемся.")}</p></form>')


def b_lead(b, c, v):
    if v == "card":
        return f'<div class="w ld-card"><div class="ldh"><h2>{one(b.get("title"))}</h2>{para(b.get("text"), "lede")}</div><div class="card">{lead_form(b, c)}</div></div>'
    return (f'<div class="w split top"><div><h2>{one(b.get("title"))}</h2>{para(b.get("text"), "lede")}{contact_list(c, ("phone", "telegram", "whatsapp", "email"))}</div>'
            f'<div class="card">{lead_form(b, c)}</div></div>')


RENDER = {"hero": b_hero, "about": b_about, "services": b_services, "prices": b_prices, "features": b_features, "steps": b_steps,
          "gallery": b_gallery, "products": b_products, "schedule": b_schedule, "reviews": b_reviews, "team": b_team, "faq": b_faq,
          "links": b_links, "cta": b_cta, "text": b_text, "contacts": b_contacts, "lead": b_lead}
EXTRA_CLS = {"hero": lambda v: f"hero h-{v}", "about": lambda v: f"ab-{v}", "contacts": lambda v: f"ct-{v}", "lead": lambda v: f"ld ld-{v}",
             "cta": lambda v: f"cta cta-{v}", "text": lambda v: f"tx {v}"}


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


def footer(site, c):
    m = menu_items(site, c)
    links = "".join(f'<a href="{E(h)}">{one(t)}</a>' for t, h, _ in m)
    year = datetime.now().year
    report = '<a href="/__report">Пожаловаться на сайт</a>' if c.mode == "publish" else '<a href="#">Пожаловаться на сайт</a>'
    return (f'<footer class="ftr"><div class="w"><div>{logo_html(site, href=c.page_file(0))}'
            f'</div><nav aria-label="Разделы">{links}</nav><div>{contact_list(c, ("phone", "email", "address", "telegram"))}</div>'
            f'<div class="bot"><span>© {year} {one(site.get("name"))}</span><span>{report}<a href="https://dewiar.pro" rel="noopener">Сайт сделан в Dewiar</a></span></div></div></footer>')


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


def page_html(site, i=0, mode="preview", images=None, base_url="", css_text=None):
    """Одна страница сайта. preview — CSS внутри; publish/export — ссылка на style.css."""
    pages = site.get("pages") or []
    if not pages:
        pages = site["pages"] = [{"title": "Главная", "blocks": []}]
    i = max(0, min(i, len(pages) - 1))
    c = Ctx(site, mode, i, images, base_url)
    th = site.get("theme") or {}
    fonts = K.FONTS.get(th.get("fonts") or "", K.FONTS["warm"])
    body = "".join(block_html(b, j, c) for j, b in enumerate(pages[i].get("blocks") or []))
    title, desc = seo_title(site, i), seo_desc(site, i)
    url = (base_url.rstrip("/") + "/" + ("" if i == 0 else c.page_file(i))) if base_url else ""
    og_img = ""
    for b in pages[i].get("blocks") or []:
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
    cls = " ".join(x for x in ("pv" if mode == "preview" else "", "it" if fonts.get("italic") else "") if x)
    cls_attr = f' class="{cls}"' if cls else ""
    menu = (site.get("menu") or {}).get("style") or "top"
    return (f'<!doctype html><html lang="ru"{cls_attr}><head>{"".join(h for h in head if h)}</head>'
            f'<body class="m-{E(menu)}{" many" if len(menu_items(site, c)) > 5 else ""}">{header(site, c)}<main>{body}</main>{footer(site, c)}'
            f'{PREVIEW_JS if mode == "preview" else ""}</body></html>')


def site_files(site, images, base_url="", mode="publish"):
    """Все файлы сайта: {путь: текст} (картинки и шрифты кладёт sites.py). -> (files, fonts [(имя, файл)])."""
    files = {"style.css": css(site, mode)}
    for i, pg in enumerate(site.get("pages") or []):
        files[slug_of(pg, i) + ".html"] = page_html(site, i, mode, images, base_url)
    return files, font_files((site.get("theme") or {}).get("fonts") or "warm")
