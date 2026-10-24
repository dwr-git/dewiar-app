"""Подключение по коду с другого устройства в студии (24.10, человек: «ввожу код с телефона на компе — „Не получилось:
escH is not defined“», а мозг при этом подключился). Общий помощник escH — в core.js (первый файл студии); сбой
перерисовки после удачного подключения не выдаётся за «не получилось»; ошибки страницы уходят в журнал ядра."""
import os, re
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


FAKE = "window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };"
CORE = r"""
(() => { window.calls = [];
  const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.call = async (c, a) => { calls.push([c, a]);
      if (c === "cloud_connect") return { connected: true, active: true, percent: 80, turns: 1200, label: "Андрей", tail: "ab12", profile: "dewiar-cloud" };
      if (c === "llm_test") return { ok: true, model: "qwen", reply: "Привет", total_ms: 900 };
      return {}; };
    setTimeout(() => core.emit("hello", {}), 300); };
  ready(); })();
"""
with sync_playwright() as p:
    b = p.chromium.launch()
    for broken in (False, True):
        pg = b.new_page(viewport={"width": 1280, "height": 900}); errs = []
        pg.on("pageerror", lambda e, errs=errs: errs.append(str(e)))
        pg.route(re.compile(r"^https?://"), lambda r: r.abort())
        if broken:                                              # как у человека: один файл студии не загрузился
            pg.route(re.compile(r"studio/folder\.js$"), lambda r: r.abort())
        pg.add_init_script(FAKE); pg.add_init_script(CORE)
        pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(1200)
        pg.evaluate("() => { S = Object.assign({}, S || {}, { ui: {}, llm: { profiles: { 'dewiar-cloud': { name: 'Dewiar', base_url: 'x', model: 'qwen' } }, active: 'dewiar-cloud' }, features: {} }); }")
        pg.evaluate("() => { $('nav button[data-p=\"brain\"]').click(); }"); pg.wait_for_timeout(300)
        pg.evaluate("() => { $('#dk-key').value = '123456'; $('#dk-go').click(); }"); pg.wait_for_timeout(1500)
        res = pg.inner_text("#dk-res")
        what = "один файл студии не загрузился" if broken else "всё загрузилось"
        ok(res.startswith("Подключено") and "Андрей" in res and "…ab12" in res and "Не получилось" not in res,
           f"{what}: код с телефона — «Подключено: Андрей · ключ …ab12» (видно, что учётка та же): {res!r}")
        ok(pg.evaluate("typeof escH") == "function", f"{what}: escH есть всегда (core.js)")
        if broken:
            pg.wait_for_timeout(2500)
            ok(pg.evaluate("calls.some(c => c[0] === 'js_errors')") or not pg.evaluate("(window.__jsErr || []).length"), "ошибки страницы уходят в журнал ядра")
        pg.close()
    b.close()
if fails:
    raise SystemExit(1)
