"""№201 (22.10): «в задачах — закреплять пин, чтобы видеть, что исполняется, а не скролить вверх и вниз». Студия →
«Задачи»: булавка у задачи — закреплённые сверху в порядке закрепления (ui.task_pins), открепить — на прежнее место.
И «Возможности» в студии (24.10): выключенные «Суфлёр», «Рядом», «Встречи» прячутся из меню и вкладок «Близких»."""
import json, os, re
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
  window.TASKS = [{ id: "t1", title: "Свежая задача", status: "running", status_ru: "идёт", created: "2026-10-24T10:00:00", progress: [1, 3] },
                  { id: "t2", title: "Вчерашний отчёт", status: "done", status_ru: "готово", created: "2026-10-23T10:00:00" },
                  { id: "t3", title: "Сайт для кафе", status: "sleeping", status_ru: "ждёт", created: "2026-10-22T10:00:00" }];
  const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.call = async (c, a) => { calls.push([c, a]);
      if (c === "tasks_list") return JSON.parse(JSON.stringify(TASKS));
      if (c === "task_get") return Object.assign({ steps: 0, plan: "", journal: "", outputs: [] }, TASKS.find(t => t.id === a.id));
      if (c === "settings_save") { const m = (o, p) => { for (const k in p) { if (p[k] && typeof p[k] === "object" && !Array.isArray(p[k]) && o[k]) m(o[k], p[k]); else o[k] = p[k]; } return o; }; return m(JSON.parse(JSON.stringify(S)), a.patch); }
      return {}; }; };
  ready(); })();
"""
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 1280, "height": 900}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route(re.compile(r"^https?://"), lambda r: r.abort())
    pg.add_init_script(FAKE); pg.add_init_script(CORE)
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(900)
    pg.evaluate("() => { S = Object.assign({}, S || {}, { ui: { task_pins: [] }, llm: { profiles: {} }, tasks: {}, features: { prompter: false, near: false, meet: true, games: true } }); }")
    pg.evaluate("() => { $('nav button[data-p=\"tasks\"]').click(); }"); pg.wait_for_timeout(300)
    pg.evaluate("loadTasks()"); pg.wait_for_timeout(400)
    order = lambda: pg.evaluate("[...document.querySelectorAll('#t-list .titem > b')].map(b => b.textContent)")
    ok(order() == ["Свежая задача", "Вчерашний отчёт", "Сайт для кафе"], f"без булавок — как раньше, по времени: {order()}")
    pg.hover("#t-list .titem:nth-child(3)"); pg.click("#t-list .titem:nth-child(3) .tpin"); pg.wait_for_timeout(500)
    ok(order()[0] == "Сайт для кафе" and pg.evaluate("S.ui.task_pins") == ["t3"], f"закрепили «Сайт для кафе» — он сверху, булавки в настройках: {order()}")
    ok(pg.evaluate("document.querySelector('#t-list .titem').classList.contains('pinned')") and not pg.evaluate("calls.some(c => c[0] === 'task_get' && c[1].id === 't3' && calls.indexOf(c) > calls.length - 3)"),
       "булавка не открывает задачу, закреплённая отмечена")
    pg.hover("#t-list .titem:nth-child(3)"); pg.click("#t-list .titem:nth-child(3) .tpin"); pg.wait_for_timeout(500)
    ok(order()[:2] == ["Сайт для кафе", "Вчерашний отчёт"] and pg.evaluate("S.ui.task_pins") == ["t3", "t2"], f"вторая булавка — под первой: {order()}")
    pg.click("#t-list .titem:nth-child(1) .tpin"); pg.wait_for_timeout(500)
    ok(order() == ["Вчерашний отчёт", "Свежая задача", "Сайт для кафе"], f"открепили — задача на своём месте по времени: {order()}")
    pg.screenshot(path="/tmp/claude-0/pins.png")
    # «Возможности»
    pg.evaluate("featuresApply()")
    ok(pg.evaluate("$('nav button[data-p=\"prompter\"]').hidden") and pg.evaluate("$('#cl-tabs button[data-t=\"near\"]').hidden")
       and not pg.evaluate("$('#cl-tabs button[data-t=\"meet\"]').hidden") and not pg.is_visible("nav button[data-p='prompter']"),
       "«Возможности»: «Суфлёр» и «Рядом» выключены — их нет в меню и вкладках, «Встречи» на месте")
    ok(pg.evaluate("!!document.querySelector('#p-features input[data-k=\"features.games\"]')"), "раздел «Возможности» с переключателями")
    ok(not errs, f"без ошибок на странице: {errs[:2]}")
    b.close()

if fails:
    raise SystemExit(1)
