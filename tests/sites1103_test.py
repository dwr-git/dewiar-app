"""«Сайты» (03.11): вёрстка JSON → HTML. Все шаблоны собираются без ошибок; страница — с viewport, описанием и Open Graph;
никаких внешних подключений (CDN, шрифты, картинки чужих сайтов) — шрифты свои, картинки свои; текст экранируется (HTML
из полей не проходит); в опубликованном виде — ни одного <script> (кроме данных для поисковиков) и нет заглушек людей и пустых
галерей; палитры читаются (контраст ≥ 4,5); на телефоне 390 px и на компьютере нет горизонтальной прокрутки — во всех
шаблонах, во всех вариантах блоков, во всех меню (playwright)."""
import copy, os, re, sys, tempfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
import sites, sites_kit as K, sites_render as R  # noqa: E402
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


ok(8 <= len(K.TEMPLATE_ORDER) <= 30 and set(K.TEMPLATE_ORDER) == set(K.TEMPLATES), f"шаблонов {len(K.TEMPLATE_ORDER)} (8–30; 05.11 — 20)")
ok(len({(t["palette"], t["fonts"], t["menu"]) for t in K.TEMPLATES.values()}) == len(K.TEMPLATES), "у каждого шаблона свой характер (палитра+шрифт+меню)")
for k, p in K.PALETTES.items():
    c1, c2, c3 = R.contrast(p["ink"], p["bg"]), R.contrast(p["muted"], p["bg"]), R.contrast(p["accent_ink"], p["accent"])
    ok(min(c1, c2, c3) >= 4.5 and R.contrast(p["dark_ink"], p["dark"]) >= 4.5, f"палитра {k}: текст {c1:.1f}, второстепенный {c2:.1f}, кнопка {c3:.1f}")
for tid in K.TEMPLATE_ORDER:
    t = K.TEMPLATES[tid]
    blob = repr(t)
    ok(not any(b["type"] == "reviews" and b.get("items") for p in t["pages"] for b in p["blocks"]), f"{tid}: отзывы не выдуманы")
    ok(all(x.get("todo") for p in t["pages"] for b in p["blocks"] if b["type"] == "team" for x in b.get("items") or []), f"{tid}: люди — только заглушки (todo)")

S = sites.Sites(tempfile.mkdtemp())
all_html = {}
for tid in K.TEMPLATE_ORDER:
    s = S.create(tid, fill=False)
    files = S.build(s["id"], "publish", "https://test.dewiar.pro")
    h = files["index.html"].decode()
    all_html[tid] = (s, files)
    ext = re.findall(r'(?:src|href)="(https?:[^"]+)"', re.sub(r'<a\b[^>]*>', "", h))
    ext = [u for u in ext if not u.startswith("https://test.dewiar.pro")]
    ok(not ext and "@import" not in files["style.css"].decode() and not re.search(r"url\((?!fonts/|img/|data:)", files["style.css"].decode()),
       f"{tid}: ничего не грузится с чужих сайтов {ext[:2]}")
    ok('name="viewport" content="width=device-width, initial-scale=1"' in h and '<meta name="description"' in h and 'og:title' in h and 'lang="ru"' in h,
       f"{tid}: viewport, описание, Open Graph")
    ok(not re.search(r"<script(?! type=\"application/ld\+json\")", h) and " onclick" not in h, f"{tid}: без скриптов")
    ok(h.count("<h1") == 1, f"{tid}: один h1")
    ok(all(k.startswith(("fonts/", "img/")) or k.endswith((".html", ".css")) for k in files), f"{tid}: файлы — страницы, стили, свои шрифты")
    ok(len(files["index.html"]) + len(files["style.css"]) < 120_000, f"{tid}: лёгкий — {(len(files['index.html']) + len(files['style.css'])) // 1024} КБ HTML+CSS")
    ok('action="/__lead"' in h and 'href="/__report"' in h, f"{tid}: форма заявки на /__lead и «Пожаловаться»")
    ok("Имя врача" not in h and "Добавьте фото" not in h, f"{tid}: заглушки людей и пустая галерея не публикуются")

# экранирование
s = S.create("personal", fill=False)
evil = '<img src=x onerror=alert(1)> "кавычки" & <b>жирный</b>'
S.apply(s["id"], [{"op": "site", "name": evil}, {"op": "block", "block": "hero", "title": evil, "text": evil},
                  {"op": "block", "block": "links", "items": [{"title": "плохо", "href": "javascript:alert(1)"}, {"title": "хорошо", "href": "t.me/x"}]}])
h = S.build(s["id"])["index.html"].decode()
ok("<img src=x" not in h and "&lt;img src=x onerror=alert(1)&gt;" in h and "javascript:" not in h and 'href="https://t.me/x"' in h,
   "текст полей экранируется, javascript:-ссылки выбрасываются, «t.me/x» → https")

# предпросмотр: блоки выбираются, заглушки видны
s = S.create("clinic", fill=False)
pv = S.render(s["id"])
ok(pv.count(' data-b="') == len(S.get(s["id"])["pages"][0]["blocks"]) and "Имя врача" in pv and "data:font/woff2;base64," in pv,
   "предпросмотр: блоки с data-b, заглушки видны, шрифты внутри страницы (фрейм без allow-same-origin)")

# телефон 390 и компьютер: нет горизонтальной прокрутки, меню на телефоне — кнопкой
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None
if sync_playwright:
    out = Path(tempfile.mkdtemp())
    (out / "assets").symlink_to(ROOT / "ui/assets")
    with sync_playwright() as p:
        b = p.chromium.launch()
        pages = {w: b.new_page(viewport={"width": w, "height": 860}) for w in (390, 1280)}
        variants = []
        for tid in K.TEMPLATE_ORDER:
            s = S.create(tid, fill=False)
            variants.append((tid, s["id"]))
        # все варианты всех блоков — на одной странице, разные меню
        s = S.create("startup", fill=False)
        ops = []
        for t, B in K.BLOCKS.items():
            for v in B["variants"]:
                d = dict(K.blank_block(t), variant=v)
                d.pop("type")
                ops.append({"op": "add_block", "type": t, "data": dict(d, variant=v, title=f"{B['title']} — {B['variants'][v]} — длинный заголовок раздела, чтобы проверить перенос строк")})
        S.apply(s["id"], ops)
        for m in K.MENUS:
            S.apply(s["id"], [{"op": "menu", "style": m}])
            variants.append((f"все блоки, меню {m}", s["id"]))
        for name, sid in variants:
            (out / "p.html").write_text(S.render(sid))
            for w, pg in pages.items():
                pg.goto((out / "p.html").as_uri()); pg.wait_for_timeout(120)
                sw = pg.evaluate("document.documentElement.scrollWidth")
                ok(sw <= w, f"{name}: ширина {w} — без горизонтальной прокрутки ({sw})")
                if w == 390:
                    ok(pg.locator(".mnav summary").is_visible() and not pg.locator(".hdr .nav").is_visible(), f"{name}: на телефоне меню — кнопкой")
        # опубликованный вид (style.css, fonts/) тоже
        s, files = all_html["coffee"]
        d = out / "pub"
        for k, v in files.items():
            (d / k).parent.mkdir(parents=True, exist_ok=True); (d / k).write_bytes(v)
        pg = pages[390]
        pg.goto((d / "index.html").as_uri()); pg.wait_for_timeout(200)
        ff = pg.evaluate("getComputedStyle(document.querySelector('h1')).fontFamily")
        loaded = pg.evaluate("document.fonts.ready.then(() => [...document.fonts].filter(f => f.status === 'loaded').map(f => f.family).join(','))")
        ok(pg.evaluate("document.documentElement.scrollWidth") <= 390 and ff.replace('"', "").startswith("Lora") and "Lora" in loaded,
           f"опубликованный вид: свои шрифты загружены ({loaded}), на телефоне без прокрутки")
        b.close()
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
