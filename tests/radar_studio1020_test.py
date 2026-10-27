"""Радар «Рядом» на компьютере (20.10: «я бы хотел, чтобы радар был и на компе»): студия → «Близкие» → «Рядом». Центр —
ваш телефон (его место приходит своим устройствам), близкие — те, кто показал себя; 👋 — close_wave; без места телефона —
объяснение, где его включить. Ядро — radar1020_test (close.py geo_state, wave)."""
import math, os, sys, time
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


def dest(lat, lon, km, deg):
    d, b = km / 6371.0, math.radians(deg); f1, l1 = math.radians(lat), math.radians(lon)
    f2 = math.asin(math.sin(f1) * math.cos(d) + math.cos(f1) * math.sin(d) * math.cos(b))
    l2 = l1 + math.atan2(math.sin(b) * math.sin(d) * math.cos(f1), math.cos(d) - math.sin(f1) * math.sin(f2))
    return [math.degrees(f2), math.degrees(l2)]


H = [53.9006, 27.559]; now = int(time.time() * 1000)
P = [("p1", "Мама", 1.2, 312, 1), ("p2", "Андрей", 0.18, 122, 2), ("p3", "Вика", None, 0, 0)]
st = {"me": {"name": "Михаил", "pid": "pme", "face": 3}, "people": [{"pid": p[0], "name": p[1], "devs": [{"dev": "d"}], "unread": 0, "last": {}, "face": 2 if p[0] == "p1" else 0} for p in P], "offers": [],
      "geo": {"me": {"lat": H[0], "lon": H[1], "acc": 10, "ts": now}, "people": {p[0]: dict(zip(("lat", "lon"), dest(*H, p[2], p[3])), acc=15, ts=now - p[4] * 60000, until=-1) for p in P if p[2]}}}
from playwright.sync_api import sync_playwright  # noqa: E402
FAKE = "window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };"
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 1280, "height": 860}); pg.on("pageerror", lambda e: errs.append(str(e))); pg.add_init_script(FAKE)
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1", wait_until="domcontentloaded"); pg.wait_for_timeout(1000)
    pg.evaluate("""(st) => { window.ST = st; window.calls = []; S = Object.assign(S || {}, { close: {} });
      const PX = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==';
      core.call = async (c, a) => { calls.push([c, a]); return c === 'close_state' ? ST : c === 'close_history' ? [] : c === 'close_face' ? { data: PX } : {}; };
      document.querySelector('nav button[data-p="close"]').click(); }""", st)
    pg.wait_for_timeout(500); pg.click('#cl-tabs button[data-t="near"]'); pg.wait_for_timeout(500)
    ok(pg.locator("#nr-radar .rad-p").count() == 2 and pg.is_hidden(".cl-box"), "«Рядом»: на радаре двое, переписка спрятана")
    pg.wait_for_timeout(300)
    ok(pg.evaluate("document.querySelector('#nr-radar .rad-p[data-pid=\"p1\"] .cl-ava').classList.contains('has-face') && document.querySelector('#nr-radar .rad-me').classList.contains('has-face')"),
       "на радаре — фото близкого и своё в середине, а не буквы (пакет 27.10)")
    card = pg.inner_text(".nr-card")
    ok("Андрей" in card and "180 м" in card and "на юго-восток" in card, f"ближайший — в карточке: {card!r}")
    ok("Вика" in pg.inner_text(".nr-rest") and "Центр — ваш телефон" in pg.inner_text("#cl-near"), "кто не показал себя — ниже; подпись про центр")
    pg.click("#nr-wave"); pg.wait_for_timeout(300)
    ok(["close_wave", {"pid": "p2"}] in pg.evaluate("calls"), "👋 — close_wave тому, кто выбран")
    pg.click('#nr-radar .rad-p[data-pid="p1"]'); pg.wait_for_timeout(200)
    ok("Мама" in pg.inner_text(".nr-card") and "на северо-запад" in pg.inner_text(".nr-card"), "нажал на кружок — его карточка")
    pg.evaluate("() => { ST.geo.me = null; core.emit('close_geo', { geo: ST.geo }); }"); pg.wait_for_timeout(200)
    ok("Центр радара — ваш телефон" in pg.inner_text(".nr-card") and pg.locator("#nr-radar .rad-p").count() == 0, "без места телефона — объяснение, где его включить")
    pg.click('#cl-tabs button[data-t="chat"]'); pg.wait_for_timeout(200)
    ok(pg.is_visible(".cl-box") and pg.is_hidden("#cl-near"), "вкладка «Переписка» — как раньше")
    ok(not errs, f"без ошибок JavaScript: {errs[:2]}")
    b.close()
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
