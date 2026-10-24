"""Игры на компьютере во весь экран (владелец 24.10: «можно ли в играх на компьютере также открыть их на весь экран?
…быстрее всего это будет нужно»): в листе «Досуг» у игры есть кнопка «во весь экран» — лист разворачивается на весь
экран (Api.pad_full), ещё раз или Esc — обратно; «домой» из полного экрана — тоже обратно."""
import json, os, re, sys, urllib.parse
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


app = (ROOT / "ui/app.py").read_text(encoding="utf-8")
pf = app[app.index("def pad_full"):app.index("def pad_hide")]
ok("winshell.monitor_area(hw)" in pf and "win.resize(" in pf and "toggle_fullscreen()" not in pf and "gw.fullscreen()" in pf and "gw.unfullscreen()" in pf,
   "Api.pad_full: Windows — растягиваем сами на весь монитор (toggle_fullscreen у окна без рамки не работал, 25.10), Linux — fullscreen")
ok("def monitor_area(h)" in (ROOT / "ui/winshell.py").read_text(encoding="utf-8") and 'getattr(self, "_pad_full", False):        # игра на весь экран' in app,
   "весь монитор — rcMonitor; на весь экран лист не ездит за виджетом")
ok(re.search(r"def pad_hide\(self\):[\s\S]{0,300}self\.pad_full\(False\)", app), "лист спрятали из полного экрана — сначала обратно")
ok("_pad_apply(g, True)" in app[app.index("def pad_full"):app.index("def pad_hide")], "обратно — лист у виджета с прежней формой")

from playwright.sync_api import sync_playwright  # noqa: E402
FAKE = """window.apiCalls = []; window.pywebview = { api: new Proxy({}, { get: (_, k) => (...a) => { apiCalls.push([k, ...a]);
  if (k === 'pad_size') return Promise.resolve([440, 520]);
  return Promise.resolve(true); } }) };"""
CORE = r"""
(() => { window.calls = [];
  const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.connected = true;
    core.call = async (c, a) => { calls.push([c, a]);
      if (c === "pad_tabs") return { tabs: [{ name: "Главное", mtime: 1 }], active: "Главное" };
      if (c === "pad_read") return { name: a.name, text: "# Главное\n", mtime: 1 };
      return {}; }; };
  ready(); })();
"""
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 454, "height": 600}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.add_init_script(FAKE); pg.add_init_script(CORE)
    pg.goto((ROOT / "ui/pad.html").as_uri() + "?skin=neusky&cfg=" + urllib.parse.quote(json.dumps({"side": "right", "gap": 14, "clips": []})))
    pg.wait_for_timeout(1000)
    pg.evaluate("gameOpen('blocks')"); pg.wait_for_timeout(2500)
    fr = next((f for f in pg.frames if "blocks" in (f.url or "")), None)
    ok(fr is not None, "Тетрис открылся в листе")
    vis = bool(fr) and fr.evaluate("""(() => { const b = document.getElementById('aFs');
      if (!b || b.hidden) return false; window.__fs = b; return true; })()""")
    ok(vis, "в игре на компьютере есть кнопка «во весь экран»")
    if vis:
        fr.evaluate("window.__fs.click()"); pg.wait_for_timeout(400)
        full = [c for c in pg.evaluate("apiCalls") if c[0] == "pad_full"]
        ok(full and full[-1][1] is True and pg.evaluate("document.body.classList.contains('full')"),
           f"нажали — лист просит окно на весь экран, крепления спрятаны: {full}")
        fr.evaluate("document.querySelector('canvas') && document.querySelector('canvas').focus()")
        fr.press("canvas", "Escape"); pg.wait_for_timeout(400)
        full = [c for c in pg.evaluate("apiCalls") if c[0] == "pad_full"]
        ok(full[-1][1] is False and not pg.evaluate("document.body.classList.contains('full')"), f"Esc — обратно к виджету: {full}")
        paused = fr.evaluate("document.documentElement.classList.contains('full')")
        ok(not paused, "в игре снят признак полного экрана")
        fr.evaluate("window.__fs.click()"); pg.wait_for_timeout(300)
        fr.evaluate("window.parent.postMessage({ arcade: 'home' }, '*')"); pg.wait_for_timeout(500)
        full = [c for c in pg.evaluate("apiCalls") if c[0] == "pad_full"]
        ok(full[-1][1] is False, "«к играм» из полного экрана — окно тоже возвращается")
    ok(not errs, f"без ошибок на странице: {errs[:3]}")
    b.close()

print("\nИТОГ:", "все проверки прошли" if not fails else f"не прошло {len(fails)}")
sys.exit(1 if fails else 0)
