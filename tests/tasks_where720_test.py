"""№720 (14.11): «открыла вкладку задачи, посмотрела урок, но не нашла вкладку план и где посмотреть результаты…
не получила уведомления». По журналу: просьба «проанализируй мой компьютер… предложи структуру» ушла не задачей, а
одной командой терминала в разговоре (её отменило «остановись») — в «Задачах» ничего и не появилось.
Теперь: в пустых «Задачах» под идеями — где появится задача (план, ход, результаты) и что ответ в разговоре ищут в
«Чате»; модели в описании run_command — большая работа по папкам — start_task; сценарий экзамена task_folders720."""
import srctext  # noqa: E402 — текст исходника вместе с частями (tests/srctext.py)
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


src = srctext.text(ROOT, "core/tools.py")
m = re.search(r'"run_command": \((.+?)S\(\{"command"', src, re.S)
ok(m and "start_task" in m.group(1) and "папки" in m.group(1), "run_command: большая работа по папкам — start_task, а не команда")
sc = {s["id"]: s for s in json.loads((ROOT / "data/exam/scenarios.json").read_text(encoding="utf-8"))["scenarios"]}
ok("task_folders720" in sc and sc["task_folders720"]["tool"] == {"start_task": 1}, "сценарий экзамена: «проанализируй компьютер» — start_task")

FAKE = """(() => { window._tasks = [];
  const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.call = async (c, a) => { if (c === "tasks_list") return _tasks; if (c === "task_get") return Object.assign({ plan: [], log: [], files: [] }, _tasks[0]); return {}; };
  };
  ready(); })();"""
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 1300, "height": 900}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route(re.compile(r"^https?://"), lambda r: r.abort())
    pg.add_init_script(FAKE)
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(1000)
    pg.evaluate("() => { document.querySelectorAll('section').forEach(s => s.classList.remove('cur')); document.querySelector('#p-tasks').classList.add('cur'); loadTasks(); }")
    pg.wait_for_timeout(300)
    vis = lambda s: pg.evaluate("(s) => { const e = document.querySelector(s); return !!e && e.offsetParent !== null; }", s)
    t = pg.inner_text("#t-where") if vis("#t-where") else ""
    ok("план" in t and "результат" in t and "«Чате»" in t, f"задач нет — сказано, где появится задача и где ответ разговора: {t[:60]!r}")
    pg.evaluate("() => { _tasks = [{ id: 'a', title: 'Порядок в папках', status: 'running', progress: [1, 4] }]; loadTasks(); }")
    pg.wait_for_timeout(300)
    ok(not vis("#t-where") and vis("#t-box"), "задача есть — подсказки нет, видно список задач")
    ok(not errs, f"без ошибок: {errs[:2]}")
    b.close()
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
