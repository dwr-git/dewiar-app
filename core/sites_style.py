"""Цвет и CSS сайта (sites_render.py): палитра темы и читаемость, шрифты (data: в предпросмотре, файлы при
публикации), базовые стили и стили «Авангарда», «Афиши», «Ателье», фон."""

import base64
import re
import sites_kit as K


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
.w{width:min(1160px,100%);margin:0 auto;padding:0 max(14px,calc(clamp(18px,5vw,40px)*var(--sp,1)))}
.s{background:var(--sbg);color:var(--sink);padding:calc(clamp(56px,9vw,116px)*var(--sp,1)) 0;position:relative}
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
.hero{padding:calc(clamp(48px,8vw,104px)*var(--sp,1)) 0}
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
.h-poster{padding:calc(clamp(40px,7vw,90px)*var(--sp,1)) 0 calc(clamp(48px,7vw,90px)*var(--sp,1));overflow:hidden}
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
.vids{display:grid;gap:20px;max-width:960px;margin:0 auto}.vids.vg{grid-template-columns:repeat(2,1fr);max-width:none}
.vid{position:relative;aspect-ratio:16/9;border-radius:var(--r);overflow:hidden;background:#000}
.vid iframe,.vid video{position:absolute;inset:0;width:100%;height:100%;border:0}
.vid.vph{display:grid;place-items:center;align-content:center;gap:8px;background:var(--scard);color:var(--smut);text-align:center;padding:16px}
.vid.vph span{font-size:42px;color:var(--slink)}.vids figcaption{margin-top:8px;color:var(--smut);font-size:.95em}
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
.cta-card .card{text-align:center;padding:calc(clamp(32px,6vw,72px)*var(--sp,1))}.cta-card .card .lede{margin:0 auto}.cta-card .btns{justify-content:center}
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
.s.doc{padding-top:calc(clamp(36px,6vw,72px)*var(--sp,1))}
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
 .vids.vg{grid-template-columns:1fr}
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
.sty-atelier .s{padding:calc(clamp(72px,11vw,140px)*var(--sp,1)) 0}
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
    sp = K.SPACES.get(th.get("space") or "", K.SPACES["normal"])
    hdr = th.get("header") or "light"
    hb = {"light": (p["bg"], p["ink"], p["line"], p["accent"], p["accent_ink"], readable_on(p["accent"], p["bg"], 3)),
          "dark": (p["dark"], p["dark_ink"], mix(p["dark"], p["dark_ink"], .14), *tone_vars(p)["dark"][3:5],
                   p["accent2"] if contrast(p["accent2"], p["dark"]) >= 3 else p["dark_ink"]),
          "accent": (p["accent"], p["accent_ink"], mix(p["accent"], p["accent_ink"], .2), p["accent_ink"], p["accent"], p["accent_ink"])}[hdr if hdr in ("light", "dark", "accent") else "light"]
    v = {"bg": p["bg"], "ink": p["ink"], "muted": p["muted"], "accent": p["accent"], "accent-ink": p["accent_ink"], "surface": p["surface"],
         "line": p["line"], "dark": p["dark"], "dark-ink": p["dark_ink"], "a2": p["accent2"], "fh": f["head"], "fb": f["body"], "hw": str(f["hw"]),
         "tr": f["track"], "hs": str(f.get("scale", 1)), "h3s": str(f.get("scale3", 1)), "r": f"{rd['r']}px", "rb": f"{rd['btn']}px", "sp": str(sp["k"]), "hbg": hb[0], "hink": hb[1], "hline": hb[2], "hbtn": hb[3], "hbtnk": hb[4], "hacc": hb[5],
         "ftr-mut": mix(p["dark_ink"], p["dark"], .32), "ftr-line": mix(p["dark"], p["dark_ink"], .16)}
    for tone, vals in tone_vars(p).items():
        for k, val in zip(("bg", "ink", "mut", "btn", "btnk", "line", "card", "link"), vals):
            v[f"c-{tone}-{k}"] = val
    root = ":root{" + ";".join(f"--{k}:{val}" for k, val in v.items()) + ";color-scheme:" + ("dark" if lum(p["bg"]) < .2 else "light") + "}"
    prefix = "data:" if mode == "preview" else "fonts/"
    sty = {"avangard": AV_CSS, "poster": POSTER_CSS, "atelier": ATELIER_CSS}.get(style_of(site), "")
    return font_faces(th.get("fonts") or "warm", prefix) + root + BASE_CSS + NEW_CSS + sty + bg_css(th, p) + (PREVIEW_CSS if mode == "preview" else "")


def bg_of(theme):
    """Фон сайта целиком (0.99, владелец 14.11: «прошу фон градиентом оранжево-красным — „ничего не изменилось“, а цвет фона
    меняет акценты»): theme.bg = [цвет] или [цвет, цвет] — один цвет или градиент под всеми разделами. -> список или []."""
    v = (theme or {}).get("bg") or []
    v = [c for c in (v if isinstance(v, list) else [v]) if re.fullmatch(r"#[0-9a-fA-F]{6}", str(c or ""))][:2]
    return v


def bg_css(theme, p):
    """Фон под всеми разделами (кроме разделов цвета акцента): разделы прозрачные, текст — светлый или тёмный по фону."""
    v = bg_of(theme)
    if not v:
        return ""
    a, b = v[0], v[-1]
    mid = mix(a, b, .5)
    light_ink = lum(mid) < .42
    ink = "#FFFFFF" if light_ink else (p["ink"] if contrast(p["ink"], mid) >= 4.5 else "#15171C")
    card = "rgba(255,255,255,.12)" if light_ink else "rgba(255,255,255,.62)"
    line = "rgba(255,255,255,.26)" if light_ink else "rgba(0,0,0,.14)"
    bg = a if a == b else f"linear-gradient(165deg,{a} 0%,{b} 100%)"
    return (f"html{{background:{b}}}body{{background:{bg};background-color:{a}}}"
            f".t-base,.t-alt,.t-dark{{--sbg:transparent;--sink:{ink};--smut:{mix(ink, mid, .3)};--sline:{line};--scard:{card};--slink:{ink}}}")
