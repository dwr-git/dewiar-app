"""«Рядом — ещё одна Лира» в студии и на телефоне (1.0.36, письмо 18.11). Студия: блок над картой — «Рядом — ещё одна
Лира: «Ноутбук»» с «Сделать одной Лирой» / «Это не моё»; уже предложено — «Ждёт ответа»; пришло предложение — «Да, одна
Лира» / «Нет»; нажатия зовут near_ask / near_hide / near_answer. Телефон: те же слова (одна функция — одно название).
Нечего предлагать — блока нет. DEWIAR_SHOTS=<папка> — снимок studio-near.png."""
import json, os, subprocess, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


now = int(time.time())
SYNC = {"available": True, "on": True, "ok": True, "at": now - 20, "error": "", "e2e": {"on": False},
        "near": [{"id": "pc-lap", "name": "Ноутбук", "app": "pc", "seen": now - 7200}, {"id": "phone-2", "name": "Pixel 8", "app": "phone", "seen": now - 60, "asked": now - 30}],
        "asks": [{"id": "a1", "from": "Рабочий", "app": "pc", "ts": now - 100}]}
DEV = {"me": {"id": "pc-home", "name": "Домашний", "app": "pc", "custom": True}, "mode": "key", "login": "", "can_pair": True, "error": "", "sync": SYNC,
       "devices": [{"id": "pc-home", "name": "Домашний", "app": "pc", "ver": "1.0.36", "seen": now, "me": True},
                   {"id": "phone-1", "name": "Мой телефон", "app": "phone", "ver": "0.9.64", "seen": now - 40, "me": False}]}
EMPTY = dict(DEV, sync=dict(SYNC, near=[], asks=[]))
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 1400, "height": 1000}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };")
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(1000)
    pg.evaluate("""([dev, empty]) => { window._calls = []; window._st = dev; window._empty = empty;
      core.call = (c, a) => { _calls.push([c, a || {}]);
        if (c === 'devices_get') return Promise.resolve(_st);
        if (c === 'near_ask') { _st = JSON.parse(JSON.stringify(_st)); _st.sync.near[0].asked = 1; _st.asked = 'Ноутбук'; return Promise.resolve(_st); }
        if (c === 'near_hide') return Promise.resolve(_st);
        if (c === 'near_answer') { _st = JSON.parse(JSON.stringify(_st)); _st.sync.asks = []; return Promise.resolve(Object.assign({}, _st, { linked: true, with_name: 'Рабочий' })); }
        return Promise.resolve({}); };
      document.querySelector('nav button[data-p=devices]').click(); }""", [DEV, EMPTY])
    pg.wait_for_timeout(700)
    rows = pg.evaluate("() => [...document.querySelectorAll('#dv-near .dv-nr')].map(r => [r.querySelector('b').textContent, r.querySelector('small').textContent, [...r.querySelectorAll('button')].map(b => b.textContent), r.textContent])")
    ok(len(rows) == 3, f"три строки: предложение и два устройства рядом: {len(rows)}")
    ok(rows and "«Рабочий» предлагает стать одной Лирой" in rows[0][0] and rows[0][2] == ["Да, одна Лира", "Нет"] and "только если это ваше устройство" in rows[0][1],
       f"предложение: «Да, одна Лира» / «Нет», про баланс сказано: {rows and rows[0][:3]}")
    ok(len(rows) > 1 and "Рядом — ещё одна Лира: «Ноутбук»" in rows[1][0] and rows[1][2] == ["Сделать одной Лирой", "Это не моё"] and "кого-то из семьи" in rows[1][1] and "был 2 ч назад" in rows[1][1],
       f"рядом — «Ноутбук», был 2 ч назад: {rows[1][:3] if len(rows) > 1 else ''}")
    ok(len(rows) > 2 and rows[2][2] == [] and "Ждёт ответа на «Pixel 8»" in rows[2][3], "уже предложено — «Ждёт ответа», без кнопок")
    if os.environ.get("DEWIAR_SHOTS"):
        pg.locator("#p-devices").screenshot(path=str(Path(os.environ["DEWIAR_SHOTS"]) / "studio-near.png"))
    pg.click("#dv-near [data-nask]"); pg.wait_for_timeout(300)
    ok(["near_ask", {"to": "pc-lap"}] in pg.evaluate("() => _calls"), "«Сделать одной Лирой» → near_ask")
    ok("Ждёт ответа на «Ноутбук»" in pg.inner_text("#dv-near"), "после — «Ждёт ответа на «Ноутбук»»")
    pg.click("#dv-near [data-nyes]"); pg.wait_for_timeout(300)
    ok(["near_answer", {"id": "a1", "yes": True}] in pg.evaluate("() => _calls") and "одна Лира с «Рабочий»" in pg.inner_text("body"), "«Да, одна Лира» → near_answer, тост")
    ok(pg.evaluate("() => document.querySelectorAll('#dv-near [data-nyes]').length") == 0, "предложение ушло из списка")
    pg.evaluate("() => { _st = _empty; loadMyDevices(false); }"); pg.wait_for_timeout(300)
    ok(pg.evaluate("() => document.querySelector('#dv-near').hidden"), "нечего предлагать — блока нет")
    ok("Дома телефон может обмениваться с компьютером ещё и напрямую по Wi-Fi — Лира та же" in pg.inner_text("#p-devices .lead"),
       "вступление: dewiar.pro — связь, Wi‑Fi — короче путь, Лира та же (не «два способа»)")
    ok(not errs, f"без ошибок на странице: {errs}")
    b.close()

# телефон — те же слова
js = r"""const src = require('fs').readFileSync(process.argv[1], 'utf8');
const a = src.indexOf('const devNearHid'), b = src.indexOf('function devNearBind()');
globalThis.esc = (x) => String(x); globalThis.DEV_APP = { pc: "Компьютер", phone: "Телефон" };
globalThis.prefGet = () => ""; globalThis.devAgo = () => "был 2 ч назад"; globalThis.NEAR = JSON.parse(process.argv[2]);
eval(src.slice(a, b).replace(/const (devNearHid|devAppWord) =/g, 'globalThis.$1 =').replace(/^function devNearHtml/m, 'globalThis.devNearHtml = function'));
console.log(JSON.stringify({ html: devNearHtml({ token: "x" }), home: devNearHtml({ home: true }), none: (NEAR = { near: [], asks: [] }, devNearHtml({ token: "x" })) }));"""
r = subprocess.run(["node", "-e", js, str(ROOT / "android/assets/www/devices.js"), json.dumps({"near": SYNC["near"], "asks": SYNC["asks"]})], capture_output=True, text=True)
out = json.loads(r.stdout or "{}")
if not out:
    print(r.stderr[-800:])
h = out.get("html", "")
ok("«Рабочий»</b> в этой же сети предлагает стать одной Лирой" in h and "Да, одна Лира" in h and ">Нет<" in h, "телефон: предложение — те же слова и кнопки")
ok("Рядом — ещё одна Лира" in h and "Сделать одной Лирой" in h and "Это не моё" in h and "Соглашайтесь, только если это ваше устройство" in h and "Предложение отправлено" in h, "телефон: рядом — «Сделать одной Лирой», «Не сейчас», уже предложено")
ok(out.get("home") == "" and out.get("none") == "", "по Wi‑Fi без входа и когда нечего предлагать — пусто")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
