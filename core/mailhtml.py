"""Письмо «как в письме» (№562, 05.11, Serge: «удобно было бы смотреть письмо в HTML-виде»): HTML письма — в безопасный вид.

Студия показывает его в <iframe sandbox="" srcdoc> с запретом всего (CSP default-src 'none'), а это — второй, свой
рубеж: что пропускаем, решает белый список, а не поиск «плохого».
- скрипты, фреймы, объекты, формы, svg и math, <base>, <meta>, <link> — прочь вместе с содержимым (формы — без самих
  полей); все on…-атрибуты, srcset, javascript:/vbscript:/data:text — прочь;
- ссылки не кликаются внутри письма (переход внутри рамки ушёл бы на чужой сайт мимо всех запретов): href → data-href,
  а сами ссылки студия показывает списком под письмом, с настоящим адресом — открываются в браузере только по нажатию;
- картинки: вложенные в письмо (cid:) — data: прямо в тексте; внешние (https:) остаются, но грузятся, только когда
  человек нажмёт «Показать картинки» (до того их не пускает CSP рамки: img-src data:) — отправитель не узнает, что
  письмо открыли; http: — прочь;
- стили (<style> и style="") остаются — без них письмо не похоже на себя; из них убраны @import, expression(),
  behavior, -moz-binding и url() не на https:/data:.
"""

import base64
import html
import re
from html.parser import HTMLParser

# теги, которые выкидываем вместе со всем, что внутри
DROP = {"script", "noscript", "iframe", "frame", "frameset", "object", "embed", "applet", "svg", "math", "template",
        "title", "select", "textarea", "audio", "video", "canvas", "portal", "xml"}
# пустые (без закрывающего тега)
VOID = {"br", "hr", "img", "wbr", "col", "area"}
ALLOW = {"a", "abbr", "address", "article", "aside", "b", "bdi", "bdo", "big", "blockquote", "br", "caption", "center", "cite", "code",
         "col", "colgroup", "dd", "del", "details", "dfn", "div", "dl", "dt", "em", "figcaption", "figure", "font", "footer", "h1",
         "h2", "h3", "h4", "h5", "h6", "header", "hr", "i", "img", "ins", "kbd", "label", "li", "main", "mark", "nav", "ol", "p",
         "pre", "q", "s", "samp", "section", "small", "span", "strike", "strong", "sub", "summary", "sup", "table", "tbody", "td",
         "tfoot", "th", "thead", "time", "tr", "tt", "u", "ul", "var", "wbr", "style"}
ATTRS = {"style", "class", "align", "valign", "width", "height", "bgcolor", "color", "border", "cellpadding", "cellspacing",
         "colspan", "rowspan", "dir", "lang", "face", "size", "alt", "title", "start", "type", "span", "nowrap", "role"}
MAX_HTML = 1_500_000


def _css(s):
    """CSS письма без того, что может что-то загрузить или выполнить."""
    s = re.sub(r"(?i)@import[^;]*;?", "", s)
    s = re.sub(r"(?i)url\(\s*['\"]?\s*(?!https:|data:image/)(?:[^()]|\([^()]*\))*\)", "none", s)
    return re.sub(r"(?i)expression\s*\(|behavior\s*:|-moz-binding\s*:|javascript\s*:|vbscript\s*:", "x-blocked(", s)


def _url(u):
    u = html.unescape(u or "").strip()
    return re.sub(r"[\x00-\x20]+", "", u)


class _San(HTMLParser):
    def __init__(self, cid):
        super().__init__(convert_charrefs=True)
        self.out, self.skip, self.cid, self.links, self.remote, self.in_style, self.a = [], 0, cid, [], 0, False, None

    def handle_starttag(self, tag, attrs):
        t = tag.lower()
        if self.skip:
            if t in DROP and t not in VOID:
                self.skip += 1
            return
        if t in DROP:
            self.skip = 1
            return
        if t not in ALLOW:
            return                                         # html, body, form, input, button, meta, link, base… — без тега, текст остаётся
        a = []
        for k, v in attrs:
            k = (k or "").lower()
            v = v or ""
            if t == "a" and k == "href":
                u = _url(v)
                if re.match(r"(?i)(https?:|mailto:)", u):
                    self.a = {"url": u, "text": ""}
                    self.links.append(self.a)
                    a.append(("data-href", u))
                continue
            if t == "img" and k == "src":
                u = _url(v)
                if u.lower().startswith("cid:"):
                    u = self.cid.get(u[4:].strip("<>").lower(), "")
                if re.match(r"(?i)data:image/(png|jpe?g|gif|webp|bmp);base64,", u):
                    a.append(("src", u))
                elif u.lower().startswith("https:"):
                    self.remote += 1
                    a.append(("src", u))
                continue
            if k in ATTRS and not k.startswith("on"):
                if k == "style":
                    v = _css(v)
                    self.remote += len(re.findall(r"(?i)url\(\s*['\"]?\s*https:", v))
                a.append((k, v))
        if t == "a" and any(k == "data-href" for k, _ in a):
            a.append(("title", "Ссылка — ниже письма, откроется в браузере"))
        if t == "img" and not any(k == "src" for k, _ in a):
            return                                         # картинка по http: или неизвестно откуда — не показываем вовсе
        if t == "style":
            self.in_style = True
        self.out.append("<" + t + "".join(f' {k}="{html.escape(v, quote=True)}"' for k, v in a) + ">")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        t = tag.lower()
        if self.skip:
            if t in DROP:
                self.skip -= 1
            return
        if t == "style":
            self.in_style = False
        if t == "a":
            self.a = None
        if t in ALLOW and t not in VOID:
            self.out.append(f"</{t}>")

    def handle_data(self, data):
        if self.skip:
            return
        if self.in_style:
            css = _css(data)
            self.remote += len(re.findall(r"(?i)url\(\s*['\"]?\s*https:", css))
            self.out.append(css.replace("<", "\\3c "))
        else:
            if self.a is not None and len(self.a["text"]) < 120:
                self.a["text"] += data
            self.out.append(html.escape(data, quote=False))

    def handle_comment(self, data):
        pass                                               # условные комментарии Outlook и прочее — не нужны

    def unknown_decl(self, data):
        pass


def cid_map(msg, limit=4_000_000):
    """Картинки, вложенные в письмо (Content-ID) -> {cid: data:-адрес}. Всего не больше limit байт."""
    out, used = {}, 0
    for part in msg.walk():
        cid = (part.get("Content-ID") or "").strip().strip("<>").lower()
        if not cid or part.get_content_maintype() != "image" or part.is_multipart():
            continue
        try:
            raw = part.get_payload(decode=True) or b""
        except Exception:  # noqa: BLE001
            continue
        sub = part.get_content_subtype().lower()
        if sub not in ("png", "jpeg", "jpg", "gif", "webp", "bmp") or used + len(raw) > limit:
            continue
        used += len(raw)
        out[cid] = f"data:image/{sub};base64," + base64.b64encode(raw).decode()
    return out


def html_part(msg):
    """Самая «богатая» HTML-часть письма (не вложение) -> текст или ""."""
    best = ""
    for part in msg.walk() if msg.is_multipart() else [msg]:
        if part.is_multipart() or part.get_filename() or part.get_content_type() != "text/html":
            continue
        try:
            txt = (part.get_payload(decode=True) or b"").decode(part.get_content_charset() or "utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            continue
        if len(txt) > len(best):
            best = txt
    return best


def sanitize(src, cid=None):
    """HTML письма -> {"html": безопасный HTML (без <html>/<body>), "links": [{url, text}] по порядку, без повторов,
    "remote": N внешних картинок (и фонов в стилях)}."""
    p = _San(cid or {})
    try:
        p.feed((src or "")[:MAX_HTML])
        p.close()
    except Exception:  # noqa: BLE001 — разбор сломанного HTML не должен ронять открытие письма
        pass
    seen, links = {}, []
    for x in p.links:
        x = {"url": x["url"], "text": re.sub(r"\s+", " ", x["text"]).strip()[:100]}
        if x["url"] not in seen:
            seen[x["url"]] = x
            links.append(x)
        elif not seen[x["url"]]["text"]:
            seen[x["url"]]["text"] = x["text"]
    return {"html": "".join(p.out).strip(), "links": links[:60], "remote": p.remote}
