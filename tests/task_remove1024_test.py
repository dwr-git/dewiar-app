"""24.10, владелец: «Лира меня замучила напоминанием про задачу „Исследование“, я даже не знаю, откуда она… попросил
удалить — она долго рассказывала, что не умеет; попробовал сам — на телефоне не понятно, где удалить».
- компьютер: инструмент remove_task удаляет задачу по части названия;
- телефон: на карточке задачи в «Мой день» → «Сделанное» — «Удалить задачу» и, если ждёт ответа, поле «Ответить»;
  у себя задача пропадает сразу и не возвращается; компьютеру уходит запись задачи с want (core/sync.py _task_want);
- телефон: инструменты remove_task и answer_task — «удали задачу исследование» без долгих рассказов."""
import os, re, subprocess, sys, tempfile, types
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


# ---------- компьютер ----------
import tools as T  # noqa: E402
import sync as SY  # noqa: E402


class FakeTasks:
    def __init__(self):
        self.tasks = {"t1": types.SimpleNamespace(id="t1", title="Исследование", status="waiting"),
                      "t2": types.SimpleNamespace(id="t2", title="Тестовая задача", status="done")}
        self.log = []
    def get(self, tid):
        if tid in self.tasks:
            return self.tasks[tid]
        for t in self.tasks.values():
            if tid.lower() in t.title.lower():
                return t
        raise KeyError(f"нет задачи «{tid}»")
    def list(self):
        return [{"title": t.title} for t in self.tasks.values()]
    def delete(self, tid):
        self.log.append(("delete", tid)); self.tasks.pop(tid)
    def stop(self, tid):
        self.log.append(("stop", tid))
    def answer(self, tid, text):
        self.log.append(("answer", tid, text))


ft = FakeTasks()
ctx = {"tasks": ft}
r = T.TOOLS["remove_task"][3]({"name": "исследование"}, ctx)
ok(ft.log == [("delete", "t1")] and "удалена" in r, f"компьютер: «удали задачу исследование» — remove_task: {r}")
try:
    T.TOOLS["remove_task"][3]({"name": "отчёт о погоде"}, ctx); ok(False, "удалила несуществующую")
except T.ToolError as e:
    ok("Тестовая задача" in str(e), f"нет такой — модель видит, какие есть: {e}")
ok("remove_task" in __import__("tasks").SKIP_IN_TASK, "сама задача себя удалить не может")
ft = FakeTasks()
sy = SY.Sync.__new__(SY.Sync); sy.host = types.SimpleNamespace(tasks=ft)
ok(sy._apply_extra("task", "t1", {"title": "Исследование", "want": "answer", "text": "погода в Минске"}, False) is False
   and ft.log == [("answer", "t1", "погода в Минске")], f"с телефона: ответ задаче: {ft.log}")
sy._apply_extra("task", "t1", {"title": "Исследование", "want": "delete"}, False)
sy._apply_extra("task", "t9", {"title": "Чужая", "want": "delete"}, False)
ok(ft.log[-1] == ("delete", "t1") and "t1" not in ft.tasks and len(ft.log) == 2, "с телефона: «Удалить задачу»; чужую (другого компьютера) — не трогаем")
sy._apply_extra("task", "t2", {"title": "Тестовая задача", "status": "done"}, False)
ok(len(ft.log) == 2, "обычная запись задачи (без want) — как раньше, ничего не делает")

# ---------- телефон ----------
tmp = Path(tempfile.mkdtemp()); www = tmp / "www"
subprocess.run(["bash", str(ROOT / "android/tools/www_assemble.sh"), str(www)], check=True, capture_output=True)
PREP = """() => { S.sync = Object.assign({}, S.sync, { on: true }); syncCred = () => ({ token: 't', base: 'x' });
  prefSet('sync', JSON.stringify({ rev: 1, idx: {}, who: 'w', device: 'phone-1', kinds: ['task', 'taskreq'] }));
  const m = mind(); m.tasks = {
    t1: { title: 'Исследование', status: 'waiting', question: 'Что именно искать?', goal: 'Найти информацию', updated: '2026-10-24T17:30:00' },
    t2: { title: 'Тестовая задача', status: 'done', result: 'Всё работает', updated: '2026-10-24T17:00:00', files: [{ name: 'test-report.md' }] } };
  saveMind(m); }"""
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 393, "height": 820}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route(re.compile(r"^https?://"), lambda r: r.abort())
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(1000)
    pg.evaluate(PREP)
    pg.evaluate("() => { openSheet('#sh-day'); dayTab = 'made'; renderDay(); }"); pg.wait_for_timeout(400)
    pg.evaluate("() => document.querySelectorAll('details.task').forEach(d => d.open = true)"); pg.wait_for_timeout(200)
    ok(pg.locator("[data-del]").count() == 2 and pg.locator("[data-ans]").count() == 1, "у каждой задачи — «Удалить задачу»; у ждущей ответа — поле «Ответить»")
    pg.screenshot(path="/tmp/claude-0/phone_task_del.png")
    pg.fill("[data-ans-t='t1']", "Погода в Минске на неделю"); pg.click("[data-ans='t1']"); pg.wait_for_timeout(300)
    snap = pg.evaluate("syncSnapshot()")
    ok((snap.get("task:t1") or {}).get("want") == "answer" and snap["task:t1"]["text"] == "Погода в Минске на неделю",
       f"ответ уходит компьютеру записью задачи: {snap.get('task:t1')}")
    pg.on("dialog", lambda d: d.accept())
    pg.evaluate("() => document.querySelectorAll('details.task').forEach(d => d.open = true)")
    pg.click("[data-del='t2']"); pg.wait_for_timeout(300)
    ok("t2" not in pg.evaluate("Object.keys(mind().tasks)") and (pg.evaluate("syncSnapshot()").get("task:t2") or {}).get("want") == "delete",
       "«Удалить задачу» — пропала сразу, компьютеру ушло «удалить»")
    back = pg.evaluate("syncApply({ kind: 'task', id: 't2', data: { title: 'Тестовая задача', status: 'done' }, updated: Date.now() })")
    ok(back is False and "t2" not in pg.evaluate("Object.keys(mind().tasks)"), "старый компьютер прислал её снова — не возвращается")
    pg.evaluate("syncApply({ kind: 'task', id: 't1', deleted: true, data: {}, updated: Date.now() })")
    ok("t1" not in pg.evaluate("Object.keys(mind().tasks)"), "компьютер удалил задачу — пропала и на телефоне")
    # голосом: «удали задачу исследование»
    pg.evaluate(PREP)
    names = pg.evaluate("toolSpecs().map(t => t.name)")
    ok("remove_task" in names and "answer_task" in names, "есть задачи — у Лиры инструменты remove_task и answer_task")
    r = pg.evaluate("runTool('remove_task', { name: 'исследование' })")
    ok("удалена" in r and "t1" not in pg.evaluate("Object.keys(mind().tasks)"), f"«удали задачу исследование»: {r}")
    r = pg.evaluate("runTool('remove_task', { name: 'отчёт' })")
    ok("Тестовая задача" in r, f"нет такой — список задач: {r}")
    ok("remove_task" in pg.evaluate("recentPrompt()"), "в подсказке Лиры — как удалить задачу")
    ok(not errs, f"без ошибок: {errs[:2]}")
    b.close()
if fails:
    raise SystemExit(1)
