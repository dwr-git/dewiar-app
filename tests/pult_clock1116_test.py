"""«Пульт» после 1.0.7 (владелец 16.11, 17:18: «напоминание на 22 часа — ощущение, что точка должна стоять слева сверху,
как на обычных часах»; 16:19: «в моменты, когда тихо и блок пустой, — что-то из новых трендов, Лирин пересказ»):
- циферблат как у часов: 12 наверху, 3 справа; стрелка — «сейчас»; будущее (12 ч) — внешняя дорожка, прошлое — внутренняя;
- тихо (за день ещё ничего) — в ленте «Сегодня» одна находка Радара с «Сутью от Лиры», нажатие — Радар."""
import json, math, os, sys, time, urllib.parse
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path[:0] = [str(ROOT), str(ROOT / "core")]
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import engine_commands as EC  # noqa: E402


class Ins:
    def analyzed(self, h=None):
        return [{"title": "Слабое", "src_name": "x", "a": {"signal": 0.2, "summary": "Мелочь."}, "ts": time.time() - 900},
                {"title": "Про новый Fable", "src_name": "@data_secrets", "ts": time.time() - 600,
                 "a": {"signal": 0.9, "summary": "Anthropic представила модели Fable 5.2 и Mythos 5.2, которые вдвое дешевле при той же "
                                                 "производительности. Ещё одно предложение, которое в карточку не идёт."}}]
    def day_trend(self): return None


class E(EC.CommandsMixin):
    def __init__(self):
        self.insight = Ins()


r = E()._pult_data()
pk = (r.get("radar") or {}).get("pick") or {}
ok(pk.get("title") == "Про новый Fable" and pk.get("src") == "@data_secrets", f"«Из Радара» — сильнейшее за сутки: {pk.get('title')}")
ok(pk.get("gist", "").endswith("производительности.") and "Ещё одно" not in pk.get("gist", ""), f"суть — первая фраза: {pk.get('gist')}")

now = time.time()
fut = now + 5 * 3600 + 120
DATA = json.dumps({"notes": [], "counts": {}, "diary": None, "next": [], "leads": [], "who": "",
                   "radar": {"items": [{"title": "Про новый Fable", "src": "@data_secrets", "signal": 0.9, "ts": now}], "trend": None, "n": 1, "pick": pk},
                   "day": [{"k": "remind", "ts": int(fut), "t": "Привести в порядок папку"}]}, ensure_ascii=False)
FAKE = """window.pywebview = { api: new Proxy({}, { get: (_, k) => (...a) => Promise.resolve(k === 'pad_size' ? [800, 560] : true) }) };"""
CORE = r"""
(() => { window.UI = %s;
  const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.connected = true;
    core.call = async (c, a) => { if (c === "pad_tabs") return { tabs: [{ name: "Главное", mtime: 1 }], active: "Главное" };
      if (c === "pad_read") return { name: a.name, text: "", mtime: 1 }; if (c === "pult_data") return %s; return {}; };
    setTimeout(() => core.emit("hello", { settings: { ui: UI, features: {} } }), 250); };
  ready(); })();
"""
URL = (ROOT / "ui/pad.html").as_uri() + "?skin=neusky&cfg=" + urllib.parse.quote(json.dumps({"side": "left", "gap": 14, "clips": []}))
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 820, "height": 600})
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.add_init_script(FAKE)
    pg.add_init_script(CORE % (json.dumps({"skin": "neusky", "pult_seen": True}), DATA))
    pg.goto(URL)
    pg.wait_for_timeout(1100)
    pg.click("#pt-tab"); pg.wait_for_timeout(700)
    geo = pg.evaluate("""() => { const f = document.querySelector('.pu-face'), d = document.querySelector('.pu-ev .e.remind .dot'),
        n = document.querySelector('.pu-now'), t = [...document.querySelectorAll('.pu-hours text')].map(x => [x.textContent, +x.getAttribute('x'), +x.getAttribute('y')]);
        return { cx: +f.getAttribute('cx'), cy: +f.getAttribute('cy'), dx: d ? +d.getAttribute('cx') : null, dy: d ? +d.getAttribute('cy') : null,
                 nx: +n.getAttribute('cx'), ny: +n.getAttribute('cy'), t }; }""")
    lab = {x[0]: x for x in geo["t"]}
    ok(set(lab) == {"12", "3", "6", "9"} and lab["12"][2] < geo["cy"] and lab["3"][1] > geo["cx"] and lab["9"][1] < geo["cx"],
       f"подписи как у часов: 12 наверху, 3 справа, 9 слева ({sorted(lab)})")

    def clock(ts):
        d = datetime.fromtimestamp(ts)
        return ((d.hour % 12) * 3600 + d.minute * 60 + d.second) / 43200 * 2 * math.pi

    def angle(x, y):
        return math.atan2(x - geo["cx"], -(y - geo["cy"])) % (2 * math.pi)

    diff = lambda a, b: abs((a - b + math.pi) % (2 * math.pi) - math.pi)
    ok(diff(angle(geo["nx"], geo["ny"]), clock(now)) < 0.05, "стрелка «сейчас» — там, где часовая стрелка")
    ok(geo["dx"] is not None and diff(angle(geo["dx"], geo["dy"]), clock(fut)) < 0.05,
       f"напоминание через 5 ч — на своём часе циферблата ({datetime.fromtimestamp(fut):%H:%M})")
    rd = math.hypot(geo["dx"] - geo["cx"], geo["dy"] - geo["cy"]); rn = math.hypot(geo["nx"] - geo["cx"], geo["ny"] - geo["cy"])
    ok(abs(rd - rn) < 3, "будущее — на внешней дорожке")
    feed = pg.inner_text("#pu-feed")
    ok(pg.is_visible(".pu-pick") and "Из Радара" in feed and "Fable 5.2" in feed and "Про новый Fable" in feed, "тихо — в «Сегодня» находка Радара с сутью")
    st = pg.evaluate("(() => { const c = getComputedStyle(document.querySelector('.pu-stage')); return [c.boxShadow, c.backgroundImage, c.backdropFilter]; })()")
    ok(st[0].count("inset") <= 2 and not st[0].startswith("rgb(184") and "rgba(36, 50, 74" in st[0] and "linear-gradient" in st[1] and "blur" in st[2],
       f"светлая тема: сцена — матовое стекло, не вдавленная (владелец 18.11): {st[0][:80]}…")
    pg.click(".pu-pick")
    ok(not errs, f"без ошибок: {errs}")
    if os.environ.get("PULT_SHOTS"):
        pg.screenshot(path=os.environ["PULT_SHOTS"] + "/clock-wide.png")
    b.close()

print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
