"""«Возможности» без путаницы (владелец 30.10: «немножко путает — включение и отключение того же суфлёра есть и на главной;
как сделать чётче и логичнее?»). Было два переключателя в разных местах: здесь — «включить совсем», на главной — «показать
значок». Теперь здесь оба сразу, тремя положениями: «Выключено» / «Без значка» / «На главной»; под ними — что это значит.
Главная → «Настроить» меняет то же самое, и «Возможности» показывают это положение."""
import json, os, re, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import settings as SET  # noqa: E402

ST = json.loads(json.dumps(SET.DEFAULTS))
ST["features"].update({"prompter": True, "clients": False})
ST["ui"]["home_apps"] = ["chat", "calendar", "prompter", "play"]
ST["ui"]["home_known"] = []
CORE = """(() => { window.calls = []; const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.call = async (c, a) => { calls.push([c, a]);
      if (c === "settings_save") { const m = (o, p) => { for (const k in p) { if (p[k] && typeof p[k] === "object" && !Array.isArray(p[k])) m(o[k] = o[k] || {}, p[k]); else o[k] = p[k]; } return o; };
        return m(JSON.parse(JSON.stringify(S)), a.patch); }
      return null; };
    setTimeout(() => core.emit("hello", { settings: ST, personas: [], persona: "lira", presets: {}, piper_voices: [] }), 200); };
  ready(); })();""".replace("ST", json.dumps(ST, ensure_ascii=False))
SHOT = os.environ.get("DEWIAR_SHOTS")
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 1300, "height": 900}); pg.on("pageerror", lambda e: errs.append(str(e) + " " + (e.stack or "")[:200]))
    pg.route(re.compile(r"^https?://"), lambda r: r.abort())
    pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };"); pg.add_init_script(CORE)
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(1500)
    pg.evaluate("document.querySelector('#wlc') && document.querySelector('#wlc').remove()")
    pg.evaluate("document.querySelector('nav button[data-p=\"features\"]').click()"); pg.wait_for_timeout(400)
    st = lambda k: pg.evaluate(f"(document.querySelector('#ft-list .ft[data-k=\"{k}\"] button[aria-checked=\"true\"]') || {{}}).dataset?.v || ''")
    ok(st("prompter") == "home" and st("clients") == "off" and st("near") == ("home" if SET.DEFAULTS["features"].get("near") is not False else "off"),
   f"положения как в настройках: суфлёр — на главной, клиенты — выключены: {st('prompter')}, {st('clients')}, {st('near')}")
    ok("Работает: значок — на главной" in pg.inner_text('#ft-list .ft[data-k="prompter"]'), "под переключателем — что это значит")
    labels = pg.evaluate("[...document.querySelectorAll('#ft-list .ft[data-k=\"prompter\"] button')].map(b => b.textContent)")
    ok(labels == ["Выключено", "Без значка", "На главной"], f"три положения: {labels}")
    ok(pg.evaluate("[...document.querySelectorAll('#ft-list .ft[data-k=\"near\"] button')].map(b => b.textContent)") == ["Выключено", "Включено"],
       "у «Рядом» значка на главной нет — два положения")
    if SHOT:
        pg.screenshot(path=str(Path(SHOT) / "features.png"))
    pg.click('#ft-list .ft[data-k="prompter"] button[data-v="on"]'); pg.wait_for_timeout(400)
    last = [c for c in pg.evaluate("calls") if c[0] == "settings_save"][-1][1]["patch"]
    ok(last["features"]["prompter"] is True and "prompter" not in last["ui"]["home_apps"], f"«Без значка» — работает, значка на главной нет: {last}")
    ok(st("prompter") == "on" and pg.evaluate("document.querySelector('nav button[data-p=\"prompter\"]').hidden"), "и в меню его нет")
    pg.click('#ft-list .ft[data-k="clients"] button[data-v="home"]'); pg.wait_for_timeout(400)
    last = [c for c in pg.evaluate("calls") if c[0] == "settings_save"][-1][1]["patch"]
    ok(last["features"]["clients"] is True and "clients" in (last.get("ui") or {}).get("home_apps", pg.evaluate("hmApps()")) and st("clients") == "home",
   f"«На главной» — включено и значок есть: {last}")
    pg.click('#ft-list .ft[data-k="prompter"] button[data-v="off"]'); pg.wait_for_timeout(400)
    last = [c for c in pg.evaluate("calls") if c[0] == "settings_save"][-1][1]["patch"]
    ok(last == {"features": {"prompter": False}} and st("prompter") == "off", f"«Выключено» — только выключить: {last}")
    # главная → «Настроить»: спрятали «Досуг» — здесь «Без значка»
    pg.evaluate("hmSave(hmApps().filter(x => x !== 'play'))"); pg.wait_for_timeout(300)
    ok(st("games") == "on", f"спрятали значок на главной — здесь «Без значка»: {st('games')}")
    b.close()
errs = [x for x in errs if "loadGallery" not in x]           # галерея персонажей без данных — заглушка, не про это
ok(not errs, f"без ошибок на странице: {errs[:3]}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
