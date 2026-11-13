"""Журнал задачи — сначала новое (идеи №81 и №82, 30.10: «когда много шагов, при входе в журнал видна первая запись — нужно
мотать вниз, чтобы посмотреть, что происходит сейчас»). По умолчанию сверху последняя запись; «По порядку» — как раньше;
выбор помнится."""
import json, os, re, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


J = "".join(f"\n**10:0{i}:00** · шаг {i}\n" for i in range(1, 6))
TASK = {"id": "t1", "goal": "отчёт", "title": "Собрать отчёт", "status": "running", "status_ru": "идёт", "steps": 5, "plan": "- [x] один\n- [ ] два",
        "journal": J, "summary": "", "notebook": "", "outputs": [], "created": "2026-10-30T10:00:00", "progress": [1, 2], "activity": "читаю"}
CORE = """(() => { const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    window.TASK = TASK_JSON; core.call = async (c, a) => { if (c === "task_get") return window.TASK; if (c === "tasks_list" || c === "task_list") return [window.TASK]; return null; };
    setTimeout(() => core.emit("hello", {}), 200); };
  ready(); })();""".replace("TASK_JSON", json.dumps(TASK, ensure_ascii=False))
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 1300, "height": 900}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route(re.compile(r"^https?://"), lambda r: r.abort())
    pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };"); pg.add_init_script(CORE)
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(1500)
    pg.evaluate("document.querySelector('nav button[data-p=\"tasks\"]').click()"); pg.wait_for_timeout(300)
    pg.evaluate("openTask('t1')"); pg.wait_for_timeout(300)
    pg.click('#t-view [data-tab="journal"]'); pg.wait_for_timeout(300)
    first = pg.evaluate("document.querySelector('#t-view .tj').innerText.trim().split('\\n')[0]")
    ok("шаг 5" in first and "5 записей" in pg.inner_text("#t-view .tj-bar"), f"журнал открывается с последней записи: {first!r}")
    pg.click('#t-view .tj-o[data-tj="old"]'); pg.wait_for_timeout(300)
    first = pg.evaluate("document.querySelector('#t-view .tj').innerText.trim().split('\\n')[0]")
    ok("шаг 1" in first and pg.evaluate("document.querySelector('.tj-o[data-tj=old]').getAttribute('aria-pressed')") == "true", f"«По порядку» — как раньше: {first!r}")
    pg.evaluate("openTask('t1')"); pg.wait_for_timeout(300)
    ok("шаг 1" in pg.evaluate("document.querySelector('#t-view .tj').innerText.trim().split('\\n')[0]"), "выбор помнится")
    if os.environ.get("DEWIAR_SHOTS"):
        pg.locator("#t-view").screenshot(path=os.environ["DEWIAR_SHOTS"] + "/task-journal.png")
    # выпуск 4 «Больших задач»: в карточке — список дел со статусами и «Готово, когда» с итогом проверки (критерии)
    pg.evaluate("""TASK.todos = [{id: 1, text: "найти источники", status: "done", evidence: "outputs/цифры.csv"},
                                 {id: 2, text: "сравнить с газом", status: "in_progress", evidence: ""},
                                 {id: 3, text: "позвонить", status: "blocked", evidence: "нет телефона"}];
                   TASK.criteria = [{label: "страниц в outputs/site: 3", ok: false, detail: "есть 2, нужно 3"}, {label: "файл есть", ok: true}];""")
    pg.evaluate("openTask('t1')"); pg.wait_for_timeout(300)
    pg.click('#t-view [data-tab="plan"]'); pg.wait_for_timeout(300)
    cls = pg.evaluate("[...document.querySelectorAll('#t-view .pchk .pi')].map(e => e.className)")
    ok(cls == ["pi done", "pi now", "pi blocked"] and "outputs/цифры.csv" in pg.inner_text("#t-view .pi.done small")
       and "нет телефона" in pg.inner_text("#t-view .pi.blocked small"), f"список дел со статусами и доказательствами: {cls}")
    ok("есть 2, нужно 3" in pg.inner_text("#t-view .pc.bad") and pg.locator("#t-view .pc.ok").count() == 1, "«Готово, когда» — критерии с итогом проверки")
    # №674 (13.11, McDuck): «дополнить задачу» — после отправки текст оставался в поле, приходилось выделять и стирать
    pg.evaluate("TASK.status = 'done'; window.__told = []; const oc = core.call; core.call = async (c, a) => { if (c === 'task_tell') { __told.push(a.text); return 'ok'; } return oc(c, a); }")
    pg.evaluate("openTask('t1')"); pg.wait_for_timeout(300)
    pg.fill("#t-msg", "ещё добавь график по месяцам"); pg.click("#t-msggo"); pg.wait_for_timeout(500)
    ok(pg.evaluate("__told") == ["ещё добавь график по месяцам"] and pg.input_value("#t-msg") == "", "№674: отправили дополнение — поле пустое")
    pg.fill("#t-msg", "черновик"); pg.evaluate("openTask('t1')"); pg.wait_for_timeout(300)
    ok(pg.input_value("#t-msg") == "черновик", "неотправленный черновик при обновлении — бережём, как раньше")
    b.close()
ok(not errs, f"без ошибок на странице: {errs[:3]}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
