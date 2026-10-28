"""28.10, владелец (Ubuntu, после обновления): «пока не вижу слева „Семья“, и в разделе „Работа“ не вижу поручений».
Разделы «по желанию» (Семья, Поручения, Клиенты) выключены, пока их не включат в «Возможностях», — о них не знали. Теперь
на их месте в меню — тихая строка «+ Поручения»: нажали — раздел включён и открыт; включён — строки нет; спрятали значок
на «Главной» сами — строки тоже нет."""
import os, re, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 1400, "height": 1000}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route(re.compile(r"^https?://"), lambda r: r.abort())
    pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };")
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(900)
    pg.evaluate("""() => { window._saves = [];
      S = Object.assign({}, S || {}, { features: { family: false, team: false, clients: false, games: true }, ui: {} });
      core.call = (c, a) => { if (c === 'settings_save') { _saves.push(a.patch); S = JSON.parse(JSON.stringify(S));
          for (const [k, v] of Object.entries(a.patch)) S[k] = Object.assign({}, S[k] || {}, v); return Promise.resolve(S); }
        if (c === 'team_get') return Promise.resolve({ connected: false, bots: [], members: [], tasks: [], inbox: [], repeats: [] });
        return Promise.resolve({}); };
      featuresApply(); }""")
    pg.wait_for_timeout(300)
    r = pg.evaluate("() => [...document.querySelectorAll('nav .nopt')].filter(x => !x.hidden).map(x => x.textContent)")
    ok(set(r) == {"+Семья", "+Поручения", "+Клиенты"}, f"выключенные разделы «по желанию» — тихими строками «+ …» на своём месте: {r}")
    ok(pg.evaluate("document.querySelector('nav button[data-p=team]').hidden"), "сам раздел, пока выключен, — скрыт")
    if os.environ.get("DEWIAR_SHOTS"): pg.screenshot(path=str(Path(os.environ["DEWIAR_SHOTS"]) / "studio-nav-optin.png"), clip={"x": 0, "y": 0, "width": 260, "height": 1000})
    pg.click("nav .nopt[data-feat=team]"); pg.wait_for_timeout(500)
    ok({"features": {"team": True}} in pg.evaluate("_saves") and pg.evaluate("!document.querySelector('nav button[data-p=team]').hidden && document.querySelector('nav button[data-p=team]').classList.contains('cur')"),
       "нажали «+ Поручения» — включено и открыто")
    ok(pg.evaluate("document.querySelector('nav .nopt[data-feat=team]').hidden") and "«Возможностях»" in pg.inner_text("#toast"), "строка ушла; сказано, где выключить")
    pg.evaluate("() => { S.ui = { home_apps: ['chat', 'close', 'calendar', 'reminders', 'notes', 'tasks'], home_known: ['chat', 'close', 'family', 'calendar', 'reminders', 'notes', 'pay', 'vault', 'music', 'kids', 'qa', 'tasks', 'team', 'clients', 'play', 'prompter', 'memory', 'ref'] }; hmNav(); }")
    ok(pg.evaluate("[...document.querySelectorAll('nav .nopt')].every(x => x.hidden)"), "спрятали значки на «Главной» сами — строк «+» нет")
    b.close()
ok(not errs, "без ошибок JavaScript" + (f": {errs[:3]}" if errs else ""))
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
