"""Плагин «Художник» — MCP-сервер (stdio). Владелец 30.10: «генеративной модели у нас нет, а было бы интересно, если бы
Лира умела красиво рисовать». Лира рисует кодом — так, как рисует Claude: векторная картинка (SVG) или анимация на
холсте (canvas). Плагин проверяет и чистит рисунок, сохраняет в «Рисунки» папки Dewiar и открывает в браузере страницу
просмотра: «Сохранить PNG» (в обычном и двойном размере) и у анимации — «Записать видео» (WebM). Все работы — в
«Галерее» (Рисунки/Галерея.html).

Безопасность: из SVG убираются скрипты, обработчики on…, внешние ссылки и <foreignObject>; страницы — с запретом сети
(Content-Security-Policy: ни запросов, ни чужих картинок и шрифтов), код анимации не может обращаться к сети и хранилищам.
Для проверок: DEWIAR_ARTIST_NO_OPEN=1 — не открывать браузер."""

import html
import json
import os
import re
import sys
import webbrowser
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from artparts import PARTS, catalog, symbol  # noqa: E402

SIZES = {"Квадрат 1080×1080": (1080, 1080), "Сторис 1080×1920": (1080, 1920), "Обложка 1920×1080": (1920, 1080),
         "Открытка 1500×1050": (1500, 1050), "Значок 512×512": (512, 512)}
DEF_SIZE = "Квадрат 1080×1080"
SVG_NS = "http://www.w3.org/2000/svg"
XLINK = "http://www.w3.org/1999/xlink"
CSP = ("default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: blob: 'self' file:; "
       "media-src blob:; font-src data:; connect-src 'none'; frame-src 'none'; form-action 'none'; base-uri 'none'")
BAD_JS = re.compile(r"\b(fetch|XMLHttpRequest|WebSocket|EventSource|importScripts|import\s*\(|navigator\.sendBeacon|localStorage|"
                    r"sessionStorage|indexedDB|document\.cookie|window\.open|location\s*[.=]|top\.|parent\.|opener|postMessage|"
                    r"eval\s*\(|Function\s*\(|Worker\s*\()", re.I)


def settings():
    out = {}
    try:
        for f in json.loads(Path(__file__).with_name("plugin.json").read_text(encoding="utf-8")).get("settings") or []:
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


def folder():
    base = os.environ.get("DEWIAR_WORKSPACE") or str(Path.home() / "Dewiar")
    d = Path(os.path.expanduser(base)) / "Рисунки"
    d.mkdir(parents=True, exist_ok=True)
    return d


def size_of(name):
    if isinstance(name, str):
        m = re.fullmatch(r"\s*(\d{2,4})\s*[x×х]\s*(\d{2,4})\s*", name)
        if m:
            return max(64, min(4096, int(m[1]))), max(64, min(4096, int(m[2])))
        for k, v in SIZES.items():
            if name and (name == k or name.lower() in k.lower()):
                return v
    return SIZES.get(settings().get("size") or DEF_SIZE, SIZES[DEF_SIZE])


def safe_name(title):
    t = re.sub(r"[\\/:*?\"<>|\n\r\t]+", " ", str(title or "").strip())
    t = re.sub(r"\s+", " ", t).strip(" .")[:60]
    return t or "Рисунок"


def unique(d, stem, exts):
    n, s = 1, stem
    while any((d / f"{s}{e}").exists() for e in exts):
        n += 1
        s = f"{stem} ({n})"
    return s


def opener(p: Path):
    if os.environ.get("DEWIAR_ARTIST_NO_OPEN"):
        return
    try:
        webbrowser.open(p.resolve().as_uri())
    except Exception:  # noqa: BLE001
        pass


# ---------------- SVG: проверка и чистка ----------------

def clean_svg(src, w, h):
    """-> (svg-текст, заметки). Убирает скрипты, on…, внешние ссылки, foreignObject; ставит xmlns, viewBox и размер."""
    s = str(src or "").strip()
    s = re.sub(r"^```(?:svg|xml|html)?\s*|\s*```$", "", s)
    i = s.find("<svg")
    if i < 0:
        raise ValueError("нужен рисунок в формате SVG: <svg …>…</svg>")
    s = s[i:s.rfind("</svg>") + 6] if "</svg>" in s else s[i:]
    if 'xmlns="' not in s[:400]:
        s = s.replace("<svg", f'<svg xmlns="{SVG_NS}"', 1)
    if "xlink:" in s and "xmlns:xlink" not in s[:600]:
        s = s.replace("<svg", f'<svg xmlns:xlink="{XLINK}"', 1)
    s = re.sub(r"&(?!(?:#\d+|#x[0-9a-fA-F]+|amp|lt|gt|quot|apos);)", "&amp;", s)        # «Том & Джерри» — не ломает разбор
    for ent, ch in (("&nbsp;", " "), ("&mdash;", "—"), ("&ndash;", "–"), ("&laquo;", "«"), ("&raquo;", "»")):
        s = s.replace(ent.replace("&", "&amp;"), ch)
    used = [n for n in dict.fromkeys(re.findall(r'href=["\']#dw-([a-z]+)["\']', s)) if n in PARTS]
    if used:                                         # готовые детали: <use href="#dw-balloon" …> — их <symbol> вставляем сами
        s = re.sub(r"(<svg\b[^>]*>)", lambda m: m[1] + "<defs>" + "".join(symbol(n) for n in used) + "</defs>", s, count=1)
    ET.register_namespace("", SVG_NS)
    ET.register_namespace("xlink", XLINK)
    try:
        root = ET.fromstring(s)
    except ET.ParseError as e:
        raise ValueError(f"SVG не разбирается ({e}) — проверь закрытые теги и кавычки") from e
    if not root.tag.endswith("svg"):
        raise ValueError("корневой тег — не <svg>")
    notes, dropped = [], 0
    for parent in list(root.iter()):
        for ch in list(parent):
            tag = ch.tag.split("}")[-1].lower() if isinstance(ch.tag, str) else ""
            if tag in ("script", "foreignobject", "iframe", "object", "embed", "audio", "video"):
                parent.remove(ch)
                dropped += 1
    for el in root.iter():
        for k in list(el.attrib):
            kl = k.split("}")[-1].lower()
            v = el.attrib[k]
            if kl.startswith("on") or (kl == "href" and not v.startswith(("#", "data:image/"))) or "javascript:" in v.lower():
                del el.attrib[k]
                dropped += 1
            elif kl == "style" and re.search(r"url\(\s*['\"]?(?!#|data:)", v, re.I):
                el.attrib[k] = re.sub(r"url\([^)]*\)", "none", v)
                dropped += 1
        if el.tag.split("}")[-1] == "style" and el.text:
            el.text = re.sub(r"@import[^;]*;?", "", el.text)
            el.text = re.sub(r"url\(\s*['\"]?(?!#|data:)[^)]*\)", "none", el.text)
    if used:
        notes.append("детали: " + ", ".join(used))
    if dropped:
        notes.append(f"убрано небезопасное или внешнее: {dropped}")
    if "viewBox" not in root.attrib:
        try:
            vw, vh = float(re.sub(r"[^\d.]", "", root.attrib.get("width", "")) or w), float(re.sub(r"[^\d.]", "", root.attrib.get("height", "")) or h)
        except ValueError:
            vw, vh = w, h
        root.attrib["viewBox"] = f"0 0 {vw:g} {vh:g}"
        notes.append("добавлен viewBox")
    vb = [float(x) for x in re.split(r"[\s,]+", root.attrib["viewBox"].strip()) if x][:4]
    if len(vb) == 4 and vb[2] > 0 and vb[3] > 0:                          # размер — по пропорции рисунка
        k = max(w, h) / max(vb[2], vb[3])
        w, h = round(vb[2] * k), round(vb[3] * k)
    root.attrib["width"], root.attrib["height"] = str(w), str(h)
    notes += text_overflow(root, vb if len(vb) == 4 else [0, 0, w, h])
    n = sum(1 for _ in root.iter())
    if n < 4:
        notes.append("рисунок очень простой — добавь фон, детали, свет и тень")
    out = ET.tostring(root, encoding="unicode")
    return out, notes, (w, h), n


def _num(v, default=0.0):
    m = re.match(r"\s*(-?[\d.]+)", str(v or ""))
    try:
        return float(m[1]) if m else default
    except ValueError:
        return default


def text_overflow(root, vb):
    """Надписи, которые, судя по длине и размеру шрифта, вылезают за край (модель картинку не видит — подсказываем ей).
    Оценка грубая: ширина буквы ≈ 0,55 кегля (жирный — 0,6); учитывается text-anchor и сдвиг родительских <g translate>."""
    out = []
    parents = {c: p for p in root.iter() for c in p}
    for el in root.iter():
        if el.tag.split("}")[-1] != "text":
            continue
        txt = "".join(el.itertext()).strip()
        if not txt or "transform" in el.attrib:
            continue
        st = el.attrib.get("style", "")
        fs = _num(el.attrib.get("font-size") or (re.search(r"font-size\s*:\s*([\d.]+)", st) or [None, ""])[1], 16)
        bold = re.search(r"bold|[6-9]00", el.attrib.get("font-weight", "") + st)
        width = len(txt) * fs * (0.6 if bold else 0.55)
        x = _num(el.attrib.get("x"))
        anc = el.attrib.get("text-anchor") or (re.search(r"text-anchor\s*:\s*(\w+)", st) or [None, "start"])[1]
        p, rot = parents.get(el), False
        while p is not None:                               # сдвиги групп: translate(x y)
            tr = p.attrib.get("transform", "")
            m = re.search(r"translate\(\s*(-?[\d.]+)", tr)
            if m:
                x += float(m[1])
            if re.search(r"rotate|matrix|scale", tr):
                rot = True
            p = parents.get(p)
        if rot:
            continue
        left = x - (width / 2 if anc == "middle" else width if anc == "end" else 0)
        right = left + width
        x0, x1 = vb[0], vb[0] + vb[2]
        if left < x0 - 2 or right > x1 + 2:
            out.append(f"надпись «{txt[:40]}» скорее всего вылезает за {'левый' if left < x0 - 2 else 'правый'} край "
                       f"(≈{round(left)}–{round(right)} при ширине {round(vb[2])}) — уменьши шрифт, перенеси строку или сдвинь")
        elif right > x1 - vb[2] * 0.03 or left < x0 + vb[2] * 0.03:
            out.append(f"надпись «{txt[:40]}» почти касается края — оставь поля")
    return out[:6]


def check_js(code):
    code = str(code or "").strip()
    code = re.sub(r"^```(?:js|javascript)?\s*|\s*```$", "", code)
    if "draw" not in code:
        raise ValueError("нужна функция draw(ctx, t, w, h) — рисует кадр в момент t (секунды)")
    m = BAD_JS.search(code)
    if m:
        raise ValueError(f"в анимации нельзя «{m[0]}» — только рисование на холсте")
    if len(code) > 60000:
        raise ValueError("код анимации слишком длинный")
    return code


# ---------------- страницы ----------------

PAGE_CSS = """
:root { color-scheme: dark; --bg: #14161c; --ink: #eef0f6; --mut: #9aa0b2; --chip: rgba(255,255,255,.07); --chip-hi: rgba(255,255,255,.13); --acc: #8b7bff; }
@media (prefers-color-scheme: light) { :root { color-scheme: light; --bg: #eceef3; --ink: #191b22; --mut: #5d6375; --chip: rgba(0,0,0,.06); --chip-hi: rgba(0,0,0,.11); --acc: #5a49e6; } }
* { box-sizing: border-box; margin: 0; }
body { min-height: 100vh; background: var(--bg); color: var(--ink); font: 15px/1.5 "Segoe UI", system-ui, -apple-system, Roboto, "Noto Sans", sans-serif; }
header { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; padding: 18px 24px; }
header h1 { font-size: 19px; font-weight: 700; margin-right: auto; letter-spacing: -.01em; }
header small { display: block; color: var(--mut); font-size: 12.5px; font-weight: 400; }
button, a.b { border: 0; border-radius: 12px; padding: 9px 15px; font: inherit; font-weight: 600; font-size: 14px; cursor: pointer; color: var(--ink);
  background: var(--chip); text-decoration: none; transition: background .15s; }
button:hover, a.b:hover { background: var(--chip-hi); }
button.p { background: var(--acc); color: #fff; } button.p:hover { filter: brightness(1.08); }
button:focus-visible, a:focus-visible { outline: 2px solid var(--acc); outline-offset: 2px; }
button:disabled { opacity: .55; cursor: default; }
.stage { display: grid; place-items: center; padding: 8px 24px 32px; }
.art { max-width: min(100%, 1100px); max-height: calc(100vh - 120px); width: auto; height: auto; border-radius: 14px;
  box-shadow: 0 30px 80px -30px rgba(0,0,0,.55); background: repeating-conic-gradient(rgba(127,127,127,.12) 0 25%, transparent 0 50%) 0 0 / 24px 24px; }
.rec { position: fixed; left: 50%; bottom: 22px; transform: translateX(-50%); padding: 10px 16px; border-radius: 14px; background: var(--chip-hi);
  backdrop-filter: blur(10px); font-weight: 600; font-size: 14px; display: none; }
.rec.on { display: block; }
"""


def viewer_svg(title, svg, w, h):
    return f"""<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="{CSP}">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{html.escape(title)}</title><style>{PAGE_CSS}</style></head><body>
<header><h1>{html.escape(title)}<small>{w}×{h} · нарисовала Лира · {datetime.now().strftime("%d.%m.%Y")}</small></h1>
<button class="p" id="png1">Сохранить PNG</button><button id="png2">PNG ×2</button><a class="b" href="Галерея.html">Галерея</a></header>
<div class="stage"><img class="art" id="art" alt="{html.escape(title)}" width="{w}" height="{h}"></div>
<script>
const SVG = {json.dumps(svg, ensure_ascii=False)}, W = {w}, H = {h}, NAME = {json.dumps(title, ensure_ascii=False)};
const url = URL.createObjectURL(new Blob([SVG], {{ type: "image/svg+xml" }}));
document.getElementById("art").src = url;
function save(k) {{
  const img = new Image();
  img.onload = () => {{ const c = document.createElement("canvas"); c.width = W * k; c.height = H * k;
    c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
    c.toBlob(b => {{ const a = document.createElement("a"); a.href = URL.createObjectURL(b); a.download = NAME + (k > 1 ? " ×2" : "") + ".png"; a.click(); }}, "image/png"); }};
  img.src = url;
}}
document.getElementById("png1").onclick = () => save(1);
document.getElementById("png2").onclick = () => save(2);
</script></body></html>"""


def viewer_anim(title, code, w, h, seconds, bg):
    return f"""<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="{CSP}">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{html.escape(title)}</title><style>{PAGE_CSS}</style></head><body>
<header><h1>{html.escape(title)}<small>{w}×{h} · {seconds:g} с по кругу · нарисовала Лира · {datetime.now().strftime("%d.%m.%Y")}</small></h1>
<button id="pause">Пауза</button><button id="png1">Кадр PNG</button><button class="p" id="rec">Записать видео · {seconds:g} с</button><a class="b" href="Галерея.html">Галерея</a></header>
<div class="stage"><canvas class="art" id="cv" width="{w}" height="{h}"></canvas></div><div class="rec" id="recst"></div>
<script>window.__err = ""; window.onerror = (m) => {{ window.__err = String(m); }};</script>
<script>
{code}
</script>
<script>
(() => {{
const W = {w}, H = {h}, SEC = {seconds}, BG = {json.dumps(bg)}, NAME = {json.dumps(title, ensure_ascii=False)};
const cv = document.getElementById("cv"), ctx = cv.getContext("2d");
let err = window.__err || (typeof draw !== "function" ? "нет функции draw(ctx, t, w, h)" : "");
let t0 = performance.now(), paused = false, pt = 0;
function frame(now) {{
  const t = paused ? pt : (Math.max(0, now - t0) / 1000) % SEC;
  if (!paused) pt = t;
  ctx.save(); if (BG) {{ ctx.fillStyle = BG; ctx.fillRect(0, 0, W, H); }} else ctx.clearRect(0, 0, W, H);
  try {{ if (!err) draw(ctx, t, W, H); }} catch (e) {{ err = String(e && e.message || e); }}
  ctx.restore();
  if (err) {{ ctx.fillStyle = "#c33"; ctx.font = "28px sans-serif"; ctx.fillText("Ошибка в анимации: " + err, 30, 60); return; }}
  requestAnimationFrame(frame);
}}
requestAnimationFrame(frame);
document.getElementById("pause").onclick = (e) => {{ paused = !paused; if (!paused) t0 = performance.now() - pt * 1000; e.target.textContent = paused ? "Дальше" : "Пауза"; }};
document.getElementById("png1").onclick = () => cv.toBlob(b => {{ const a = document.createElement("a"); a.href = URL.createObjectURL(b); a.download = NAME + ".png"; a.click(); }}, "image/png");
document.getElementById("rec").onclick = () => {{
  const st = document.getElementById("recst"), btn = document.getElementById("rec");
  if (!cv.captureStream || typeof MediaRecorder === "undefined") {{ st.textContent = "Этот браузер не умеет записывать видео — откройте страницу в Chrome, Edge или Firefox"; st.classList.add("on"); return; }}
  const type = ["video/webm;codecs=vp9", "video/webm;codecs=vp8", "video/webm", "video/mp4"].find(x => MediaRecorder.isTypeSupported(x)) || "";
  const rec = new MediaRecorder(cv.captureStream(30), {{ mimeType: type, videoBitsPerSecond: 8e6 }}), parts = [];
  rec.ondataavailable = (e) => e.data.size && parts.push(e.data);
  rec.onstop = () => {{ const b = new Blob(parts, {{ type: type || "video/webm" }}), a = document.createElement("a");
    a.href = URL.createObjectURL(b); a.download = NAME + (type.includes("mp4") ? ".mp4" : ".webm"); a.click();
    st.textContent = "Видео сохранено в «Загрузки»"; setTimeout(() => st.classList.remove("on"), 4000); btn.disabled = false; }};
  paused = false; t0 = performance.now(); btn.disabled = true; st.classList.add("on");
  rec.start(250); let left = SEC;
  st.textContent = "Записываю… " + Math.ceil(left) + " с";
  const iv = setInterval(() => {{ left -= 1; st.textContent = "Записываю… " + Math.max(0, Math.ceil(left)) + " с"; }}, 1000);
  setTimeout(() => {{ clearInterval(iv); rec.stop(); }}, SEC * 1000 + 120);
}};
}})();
</script></body></html>"""


def index_page(d: Path):
    works = load_index(d)
    cards = []
    for w in sorted(works, key=lambda x: x["at"], reverse=True):
        pv = (f'<img src="{html.escape(w["file"])}" alt="" loading="lazy">' if w["kind"] == "picture"
              else f'<span class="an">▶</span>')
        cards.append(f'<a class="w" href="{html.escape(w["page"])}"><span class="pv">{pv}</span><b>{html.escape(w["title"])}</b>'
                     f'<small>{"анимация" if w["kind"] == "animation" else "рисунок"} · {html.escape(w["at"][:16].replace("T", " "))}</small></a>')
    body = "".join(cards) or '<p class="empty">Здесь будут рисунки Лиры. Скажите: «Нарисуй открытку для мамы».</p>'
    css = PAGE_CSS + """
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 18px; padding: 6px 24px 40px; }
.w { display: flex; flex-direction: column; gap: 4px; color: inherit; text-decoration: none; }
.pv { aspect-ratio: 1; border-radius: 16px; background: var(--chip); display: grid; place-items: center; overflow: hidden; transition: transform .2s; }
.w:hover .pv { transform: translateY(-3px); } .pv img { width: 100%; height: 100%; object-fit: contain; }
.an { font-size: 42px; color: var(--acc); } .w b { font-size: 14.5px; margin-top: 6px; } .w small { color: var(--mut); font-size: 12.5px; }
.empty { color: var(--mut); padding: 30px 24px; }"""
    (d / "Галерея.html").write_text(f"""<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="{CSP}"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Галерея Лиры</title><style>{css}</style></head><body><header><h1>Галерея<small>{len(works)} · рисунки и анимации Лиры</small></h1></header>
<div class="grid">{body}</div></body></html>""", encoding="utf-8")


def load_index(d: Path):
    try:
        x = json.loads((d / ".gallery.json").read_text(encoding="utf-8"))
        return [w for w in x if (d / w["page"]).exists()]
    except (OSError, ValueError, KeyError, TypeError):
        return []


def add_index(d, item):
    works = [w for w in load_index(d) if w["page"] != item["page"]] + [item]
    (d / ".gallery.json").write_text(json.dumps(works, ensure_ascii=False, indent=1), encoding="utf-8")
    index_page(d)


# ---------------- действия ----------------

def draw(title, svg, size="", replace=False):
    w, h = size_of(size)
    out, notes, (w, h), n = clean_svg(svg, w, h)
    d = folder()
    stem = safe_name(title) if replace else unique(d, safe_name(title), (".svg", ".html"))
    (d / f"{stem}.svg").write_text(out, encoding="utf-8")
    page = d / f"{stem}.html"
    page.write_text(viewer_svg(stem, out, w, h), encoding="utf-8")
    add_index(d, {"title": stem, "kind": "picture", "file": f"{stem}.svg", "page": page.name, "at": datetime.now().isoformat(timespec="seconds")})
    opener(page)
    return {"saved": str(d / f"{stem}.svg"), "page": str(page), "size": f"{w}×{h}", "elements": n, "notes": notes,
            "say": (f"Есть замечания — исправь и вызови art_draw снова с тем же title и replace: true. " if any(x.startswith("надпись") for x in notes) else "")
            + f"Рисунок «{stem}» открыт в браузере: там «Сохранить PNG». Файл — «Рисунки» в папке Dewiar."}


def animate(title, code, seconds=6, size="", background="#101218", replace=False):
    w, h = size_of(size)
    code = check_js(code)
    try:
        sec = max(1.0, min(30.0, float(seconds or 6)))
    except (TypeError, ValueError):
        sec = 6.0
    bg = str(background or "")
    if bg and not re.fullmatch(r"#[0-9a-fA-F]{3,8}|[a-z]{3,20}|rgba?\([\d\s.,%]+\)", bg):
        bg = "#101218"
    d = folder()
    stem = safe_name(title) if replace else unique(d, safe_name(title), (".html",))
    page = d / f"{stem}.html"
    page.write_text(viewer_anim(stem, code, w, h, sec, bg), encoding="utf-8")
    add_index(d, {"title": stem, "kind": "animation", "file": page.name, "page": page.name, "at": datetime.now().isoformat(timespec="seconds")})
    opener(page)
    return {"page": str(page), "size": f"{w}×{h}", "seconds": sec,
            "say": f"Анимация «{stem}» открыта в браузере: там «Записать видео» и «Кадр PNG». Файл — «Рисунки» в папке Dewiar."}


def gallery(open_it=True, q=""):
    d = folder()
    index_page(d)
    works = load_index(d)
    if q:
        works = [w for w in works if q.lower() in w["title"].lower()]
    if open_it:
        if q and works:
            opener(d / works[-1]["page"])
        else:
            opener(d / "Галерея.html")
    return {"count": len(works), "folder": str(d), "works": [{"title": w["title"], "kind": w["kind"], "at": w["at"]} for w in works[-20:]]}


TOOLS = [
    {"name": "art_draw", "description": "Нарисовать картинку, открытку, иллюстрацию, логотип, постер: передай svg — полный код <svg> "
     "(viewBox, градиенты, фильтры; готовые детали — <use href=\"#dw-balloon\" …>, список в навыке). Сохранит, откроет в браузере с «Сохранить PNG».",
     "annotations": {"readOnlyHint": True, "title": "Нарисовать"},
     "inputSchema": {"type": "object", "properties": {"title": {"type": "string"}, "svg": {"type": "string"},
                                                      "size": {"type": "string", "description": "«1080x1080», «Сторис», «Обложка» — или пусто: из настроек"},
                                                      "replace": {"type": "boolean", "description": "поправка — заменить работу с тем же названием"}},
                     "required": ["title", "svg"]}},
    {"name": "art_animate", "description": "Анимация на холсте: code — JS с function draw(ctx, t, w, h) (t — секунды, по кругу seconds). "
     "Откроется в браузере, там «Записать видео».",
     "annotations": {"readOnlyHint": True, "title": "Анимация"},
     "inputSchema": {"type": "object", "properties": {"title": {"type": "string"}, "code": {"type": "string"}, "seconds": {"type": "number"},
                                                      "size": {"type": "string"}, "background": {"type": "string"}, "replace": {"type": "boolean"}},
                     "required": ["title", "code"]}},
    {"name": "art_gallery", "description": "Открыть галерею рисунков (или работу по названию q) и вернуть их список.",
     "annotations": {"readOnlyHint": True, "title": "Галерея"},
     "inputSchema": {"type": "object", "properties": {"q": {"type": "string"}, "open": {"type": "boolean"}}}},
]


def call(name, a):
    if name == "art_draw":
        return draw(a.get("title"), a.get("svg"), a.get("size") or "", bool(a.get("replace")))
    if name == "art_animate":
        return animate(a.get("title"), a.get("code"), a.get("seconds") or 6, a.get("size") or "", a.get("background", "#101218"), bool(a.get("replace")))
    if name == "art_gallery":
        return gallery(a.get("open", True) is not False, str(a.get("q") or ""))
    raise ValueError("нет такого действия")


def handle(msg):
    m, i = msg.get("method"), msg.get("id")
    if i is None:
        return None
    if m == "initialize":
        return {"jsonrpc": "2.0", "id": i, "result": {"protocolVersion": (msg.get("params") or {}).get("protocolVersion", "2024-11-05"),
                                                       "capabilities": {"tools": {}}, "serverInfo": {"name": "dewiar-artist", "version": "1.0"}}}
    if m == "tools/list":
        return {"jsonrpc": "2.0", "id": i, "result": {"tools": TOOLS}}
    if m == "tools/call":
        p = msg.get("params") or {}
        try:
            res = call(p.get("name"), p.get("arguments") or {})
            return {"jsonrpc": "2.0", "id": i, "result": {"content": [{"type": "text", "text": json.dumps(res, ensure_ascii=False)}]}}
        except Exception as e:  # noqa: BLE001
            return {"jsonrpc": "2.0", "id": i, "result": {"isError": True, "content": [{"type": "text", "text": f"Не получилось: {e}. Исправь и вызови снова."}]}}
    if m == "ping":
        return {"jsonrpc": "2.0", "id": i, "result": {}}
    return {"jsonrpc": "2.0", "id": i, "error": {"code": -32601, "message": "нет такого метода"}}


def main():
    try:                                               # «Открыть галерею» в панели плагина работает и до первой работы
        d = folder()
        if not (d / "Галерея.html").exists():
            index_page(d)
    except OSError:
        pass
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
