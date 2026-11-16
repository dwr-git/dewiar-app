"""Маршрут на карте (отзыв 13.10: «Лира берёт геоточку, открывает карту и предлагает короткий пешеходный маршрут дворами»).
— координаты из текста и ссылок: «55.75, 37.61», geo:, Google (@, q=), Яндекс (ll и pt — долгота первой; точка «что здесь»
  важнее центра карты; rtext — широта первой); «ул. Ленина 5» — не координаты;
— адрес → координаты (Nominatim; здесь — заглушка), не нашёлся — Яндекс ищет место сам, Google — по тексту;
— Яндекс: rtext=~точка&rtt=pd (от того места, где человек сейчас), Google: travelmode=walking; транспорт, машина, велосипед;
— компьютер: инструмент route открывает ссылку в браузере и говорит модели не выдумывать улицы;
— телефон: стоят Яндекс Карты — открывается их приложение (yandexmaps://), нет — Google; короткая ссылка — по переадресации;
  в подсказке модели есть route; в экзамене маршрут только отмечается."""
import os, shutil, subprocess, sys, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import route as R  # noqa: E402
import tools as T  # noqa: E402

CASES = [("55.751244, 37.618423", (55.751244, 37.618423)), ("geo:55.75,37.61?z=17", (55.75, 37.61)),
         ("https://yandex.ru/maps/?ll=37.618423%2C55.751244&z=17", (55.751244, 37.618423)),
         ("https://yandex.ru/maps/213/moscow/?ll=37.617635%2C55.755814&mode=whatshere&whatshere%5Bpoint%5D=37.620000%2C55.753000&z=17", (55.753, 37.62)),
         ("https://yandex.ru/maps/?pt=30.315868,59.939095&z=16", (59.939095, 30.315868)),
         ("https://yandex.ru/maps/?rtext=~55.750000%2C37.600000&rtt=pd", (55.75, 37.6)),
         ("https://www.google.com/maps/place/X/@55.7520,37.6175,17z", (55.752, 37.6175)),
         ("https://maps.google.com/?q=55.7520,37.6175", (55.752, 37.6175)),
         ("ул. Ленина 5, кв 12", None), ("Красная площадь", None)]
for t, want in CASES:
    ok(R.parse_coords(t) == want, f"координаты: {t[:60]} → {R.parse_coords(t)}")
ok(R.is_short_link("смотри https://yandex.ru/maps/-/CHu~ZT5H") and R.is_short_link("https://maps.app.goo.gl/AbC123") and not R.is_short_link("https://yandex.ru/maps/?ll=1,2"),
   "короткие ссылки на карту узнаются")
fake = lambda u, h: ([{"lat": "55.7539", "lon": "37.6208", "display_name": "Красная площадь, Москва, Россия"}] if "%D0%9A%D1%80%D0%B0%D1%81" in u else [])  # noqa: E731
r = R.plan("Красная площадь, Москва", app="yandex", get=fake)
ok(r["url"] == "https://yandex.ru/maps/?rtext=~55.753900,37.620800&rtt=pd" and r["found"], f"адрес → координаты → пешком в Яндекс Картах от текущего места: {r['url']}")
r = R.plan("Красная площадь, Москва", app="google", mode="transit", get=fake)
ok(r["url"].startswith("https://www.google.com/maps/dir/?api=1&destination=55.753900%2C37.620800&travelmode=transit"), f"Google, на транспорте: {r['url']}")
r = R.plan("Неизвестная улица 999", app="yandex", get=fake)
ok(r["url"].startswith("https://yandex.ru/maps/?text=") and not r["found"] and "выберет его на карте" in R.say(r), f"не нашлось — Яндекс ищет сам: {r['url'][:60]}")
r = R.plan("Неизвестная улица 999", app="google", get=fake)
ok("destination=%D0%9D" in r["url"] and "travelmode=walking" in r["url"], "Google — по тексту")
r = R.plan("https://yandex.ru/maps/-/CHu~ZT5H", app="yandex", get=fake, resolve=lambda u: "https://yandex.ru/maps/?ll=37.5%2C55.7&z=12")
ok(r["coords"] == (55.7, 37.5), f"короткая ссылка — по переадресации: {r['coords']}")
r = R.plan("55.7558,37.6173", frm="Тверская 1, Москва", mode="bike", app="yandex", get=lambda u, h: [{"lat": "55.757", "lon": "37.613", "display_name": "x"}])
ok(r["url"] == "https://yandex.ru/maps/?rtext=55.757000,37.613000~55.755800,37.617300&rtt=bc", f"откуда и куда, на велосипеде: {r['url']}")
s = R.say(R.plan("55.7558,37.6173", app="yandex"))
ok("пешком" in s and "дворами" in s and "не выдумывай улицы" in s, f"модели — честно: {s}")

# компьютер: инструмент
opened = []
import tools_base  # noqa: E402 — запуск — в основе действий (1.0.8)
tools_base.launch = lambda cmd, *a, **k: opened.append(cmd)
R.geocode = lambda q, get=None: (55.7539, 37.6208, "Красная площадь, Москва, Россия")
out = T.TOOLS["route"][3]({"to": "Красная площадь, Москва"}, {})
ok(opened and opened[-1][-1] == "https://yandex.ru/maps/?rtext=~55.753900,37.620800&rtt=pd" and "Открыла маршрут пешком" in out, f"компьютер: открыл в браузере: {opened[-1:]} {out[:60]}")
out = T.TOOLS["route"][3]({"to": "Красная площадь", "app": "google", "mode": "car"}, {})
ok("travelmode=driving" in opened[-1][-1] and "на машине" in out, "компьютер: Google на машине")

# телефон
www = Path(tempfile.mkdtemp()) / "www"
shutil.copytree(ROOT / "android/assets/www", www)
for f in ("entities.js", "skins.css", "skins.js", "privacy.js"):
    shutil.copy(ROOT / "ui/assets" / f, www / f)
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                capture_output=True, text=True, check=True).stdout, encoding="utf-8")
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route("https://**", lambda r: r.abort())
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(700)
    pg.evaluate("""() => { window._open = []; window._apps = ["Телефон", "Яндекс Карты", "Карты"]; D.apps = () => JSON.stringify(_apps);
      D.openUrl = (u) => { _open.push(u); return true; };
      http = async (m, u) => { if (/nominatim/.test(u)) return { status: 200, url: u, body: /%D0%9A%D1%80%D0%B0%D1%81|%D0%BA%D1%80%D0%B0%D1%81/i.test(u) || /Красн/.test(decodeURIComponent(u)) ? JSON.stringify([{ lat: "55.7539", lon: "37.6208", display_name: "Красная площадь, Тверской район, Москва, Россия" }]) : "[]" };
        if (/yandex\\.ru\\/maps\\/-\\//.test(u)) return { status: 200, url: "https://yandex.ru/maps/?ll=30.315868%2C59.939095&z=16", body: "<html></html>" };
        return { status: 404, body: "" }; }; }""")
    out = pg.evaluate("routeTool({ to: 'Красная площадь, Москва' })")
    op = pg.evaluate("_open.slice()")
    ok(op == ["yandexmaps://maps.yandex.ru/?rtext=~55.753900,37.620800&rtt=pd"] and "Открыла маршрут пешком до «Красная площадь, Тверской район, Москва»" in out,
       f"телефон: стоят Яндекс Карты — их приложение, пешком от текущего места: {op} {out[:90]}")
    pg.evaluate("() => { _open = []; _apps = ['Телефон', 'Карты']; }")
    out = pg.evaluate("routeTool({ to: 'Красная площадь, Москва', mode: 'transit' })")
    op = pg.evaluate("_open.slice()")
    ok(len(op) == 1 and op[0].startswith("https://www.google.com/maps/dir/?api=1&destination=55.753900%2C37.620800&travelmode=transit") and "на транспорте" in out,
       f"телефон: только Google Карты — Google, на транспорте: {op}")
    pg.evaluate("() => { _open = []; _apps = ['Яндекс Карты']; }")
    out = pg.evaluate("routeTool({ to: 'вот точка https://yandex.ru/maps/-/CHu~ZT5H' })")
    op = pg.evaluate("_open.slice()")
    ok(op == ["yandexmaps://maps.yandex.ru/?rtext=~59.939095,30.315868&rtt=pd"], f"телефон: геоточка короткой ссылкой — по переадресации: {op}")
    pg.evaluate("() => { _open = []; D.openUrl = (u) => { _open.push(u); return !u.startsWith('yandexmaps:'); }; }")
    out = pg.evaluate("routeTool({ to: '59.9391, 30.3159' })")
    op = pg.evaluate("_open.slice()")
    ok(op == ["yandexmaps://maps.yandex.ru/?rtext=~59.939100,30.315900&rtt=pd", "https://yandex.ru/maps/?rtext=~59.939100,30.315900&rtt=pd"],
       f"приложение не открылось — та же ссылка в браузере: {op}")
    out = pg.evaluate("routeTool({ to: 'Нигде 999' })")
    ok("выберет его на карте" in out and pg.evaluate("_open.slice(-1)[0]").startswith("https://yandex.ru/maps/?text="), "телефон: не нашлось — поиск в Яндекс Картах")
    ok("route" in pg.evaluate("toolSpecs().map(t => t.name).join(' ')") and "маршрут на карте" in pg.evaluate("systemPrompt()"), "телефон: инструмент и подсказка модели")
    ok(pg.evaluate("JSON.stringify(parseCoords('https://yandex.ru/maps/213/moscow/?ll=37.617635%2C55.755814&mode=whatshere&whatshere%5Bpoint%5D=37.620000%2C55.753000&z=17'))") == "[55.753,37.62]"
       and pg.evaluate("parseCoords('ул. Ленина 5, кв 12')") is None and pg.evaluate("JSON.stringify(parseCoords('geo:55.75,37.61'))") == "[55.75,37.61]",
       "телефон: координаты из ссылок — как на компьютере")
    b.close()
ok(not errs, f"без ошибок на странице: {errs[:3]}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
