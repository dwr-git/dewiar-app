"""Готовые персонажи — с портретами сразу (30.10, владелец: «открываю персонажей — все без изображений; изображения
появляются, только когда наведу мышью на серые кружочки»). Облик на странице со многими персонажами рисует один кадр
и замирает (still); раньше замирал через 1,5 с — фото, пришедшее позже, так и не рисовалось. Теперь замирает, только
когда фото загрузилось и кадр нарисован."""
import json, os, re, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


IMG = (ROOT / "data/avatars/eva.webp").read_bytes()
GAL = [{"id": "eva", "name": "Эва", "role": "Учёба", "tagline": "т", "skills": [], "color": "#ff7ac6", "style": "aura", "avatar_url": "http://img.test/eva.webp"},
       {"id": "doc", "name": "Доктор", "role": "Здоровье", "tagline": "т", "skills": [], "color": "#4be3a1", "style": "aura", "avatar_url": "http://img.test/doc.webp"}]
CORE = """(() => { const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.call = async (c, a) => { if (c === "gallery") return GAL; return null; };
    setTimeout(() => core.emit("hello", {}), 200); };
  ready(); })();""".replace("GAL", json.dumps(GAL, ensure_ascii=False))


def slow(route):
    time.sleep(2.6)                                  # фото приходит позже, чем облик замирает (было 1,5 с)
    route.fulfill(status=200, body=IMG, headers={"Content-Type": "image/webp", "Access-Control-Allow-Origin": "*"})


with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 1400, "height": 1000}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route("http://img.test/**", slow)
    pg.route(re.compile(r"^https?://(?!img\.test)"), lambda r: r.abort())
    pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };"); pg.add_init_script(CORE)
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(1200)
    pg.evaluate("document.querySelector('nav button[data-p=\"personas\"]').click()"); pg.wait_for_timeout(300)
    pg.evaluate("loadGallery()"); pg.wait_for_timeout(8000)   # фото приходят по очереди: второе — через ~5,5 с
    # центр портрета: фото — много разных цветов; пустой круг — почти один (снимок экрана: холст с чужим фото не читается)
    import io
    from PIL import Image
    colors = []
    for i in range(pg.locator("#ggrid canvas").count()):
        im = Image.open(io.BytesIO(pg.locator("#ggrid canvas").nth(i).screenshot())).convert("RGB")
        w, h = im.size
        crop = im.crop((int(w * .35), int(h * .35), int(w * .65), int(h * .65)))
        colors.append(len({(r >> 4, g >> 4, b2 >> 4) for r, g, b2 in crop.getdata()}))
    ok(len(colors) == 2 and all(c > 40 for c in colors), f"фото пришло позже — портреты нарисованы без наведения мыши: разных цветов {colors}")
    if os.environ.get("DEWIAR_SHOTS"):
        pg.locator("#ggrid").screenshot(path=os.environ["DEWIAR_SHOTS"] + "/gallery-still.png")
    b.close()
ok(not errs, f"без ошибок на странице: {errs[:3]}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
