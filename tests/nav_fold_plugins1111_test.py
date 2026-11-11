"""Владелец 11.11 (Ubuntu): «включённые плагины не сворачиваются, а их может быть много — всегда слева, сжирают много
места; должны быть в разделе ПЛАГИНЫ сворачиваемыми». Пункты плагинов (и групп под «Близкими») лежат в своих блоках
меню — сворачиваются вместе с заголовком группы; свёрнутость помнится (ui.nav_fold); открытый сейчас плагин виден."""
import json, os, re, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


PLUGS = [{"id": f"p{i}", "name": n, "icon": "🧩", "color": "#5b8def", "installed": True, "tagline": n} for i, n in
         enumerate(["Курсы и цены", "Проверка договора", "Дача и огород", "Кухня", "Тендеры", "Художник"])]
FAKE = """(() => { window.calls = [];
  const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.call = async (c, a) => { calls.push([c, a]);
      if (c === "plugins") return { plugins: JSON.parse(PLUGS) };
      if (c === "plugin_page") return { id: a && a.id, name: "Кухня", acts: [], files: [] };
      if (c === "month_get") throw new Error("нет");
      return {}; };
    setTimeout(() => core.emit("hello", {}), 200); };
  ready(); })();""".replace("PLUGS", json.dumps(json.dumps(PLUGS, ensure_ascii=False)))
errs = []
with sync_playwright() as p:
    b = p.chromium.launch()
    st = b.new_page(viewport={"width": 1300, "height": 900}); st.on("pageerror", lambda e: errs.append(str(e)))
    st.route(re.compile(r"^https?://"), lambda r: r.abort()); st.add_init_script(FAKE)
    st.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); st.wait_for_timeout(1200)
    st.evaluate("() => { if (!S) S = { ui: {} }; const w = document.querySelector('#wlc'); if (w) w.remove(); plpNav(JSON.parse(%s)); }" % json.dumps(json.dumps(PLUGS, ensure_ascii=False)))
    st.wait_for_timeout(300)
    vis = lambda: st.evaluate("[...document.querySelectorAll('#nav-plugins .nav-plg')].filter(b => b.offsetParent).length")   # noqa: E731
    ok(vis() == 6, f"плагины в меню видны: {vis()}")
    st.click("#nav-plg-h"); st.wait_for_timeout(300)
    ok(vis() == 0, f"свернули «Плагины» — пунктов плагинов не видно: {vis()}")
    ok(st.evaluate("!document.querySelector('#nav-plg-new').offsetParent && !document.querySelector('#nav-plg-all').offsetParent"),
       "«Создать плагин» и «Все плагины» тоже свёрнуты")
    saved = [c for c in st.evaluate("calls") if c[0] == "settings_save"]
    ok(saved and "Плагины" in json.dumps(saved[-1][1], ensure_ascii=False), "свёрнутость сохраняется в настройках (ui.nav_fold)")
    st.evaluate("plpNav(JSON.parse(%s).concat([{id:'p9',name:'Новый',icon:'✨',color:'#000',installed:true}]))" % json.dumps(json.dumps(PLUGS, ensure_ascii=False)))
    st.wait_for_timeout(200)
    ok(vis() == 0, "меню перерисовано (поставили плагин) — группа так и свёрнута")
    st.evaluate("plpOpen('p3')"); st.wait_for_timeout(400)
    ok(vis() == 1 and st.evaluate("document.querySelector('#nav-plugins .nav-plg.cur').offsetParent !== null"), "открытый плагин виден и в свёрнутой группе")
    st.click("#nav-plg-h"); st.wait_for_timeout(300)
    ok(vis() == 7, f"развернули — все плагины снова видны: {vis()}")
    src = (ROOT / "ui/studio/groups.js").read_text(encoding="utf-8")
    ok('if (typeof ngApply === "function") ngApply();' in src, "группы под «Близкими» сворачиваются вместе с заголовком")
    ok(not errs, f"без ошибок JavaScript: {errs[:2]}")
    b.close()
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
