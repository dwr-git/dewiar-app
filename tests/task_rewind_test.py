"""Снимки результатов и откат («Большие задачи», выпуск 5, docs/HARNESS.md). Раньше испорченный outputs/ задачи было не
вернуть: run_python или write_file затирали хороший файл — и всё. Теперь (core/snapshots.py):
- перед первой записью в outputs/ на шаге N (write_file, file_edit, run_python, run_shell) — снимок «как перед шагом N»;
- rewind(step=N) (инструмент задачи) и «Откатить к шагу N» (студия) возвращают outputs/ ровно к этому виду: те же файлы,
  те же байты, лишнее уходит; текущий вид перед откатом сохраняется — откат можно отменить;
- снимки ограничены (число и объём), удалённый снимок — честная ошибка; подменённый снимок («../») не выводит из outputs/;
- пока задача работает, студия откатывать не даёт; об откате человеком задача узнаёт на следующем шаге."""
import json
import os
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from task_mock import ROOT, Host, Mock, done, ok, wait_for  # noqa: E402
import snapshots as SN  # noqa: E402
import tasks as TK  # noqa: E402

mock = Mock({})
host = Host(mock)
tm = TK.TaskManager(host)
t = tm.create("Откат", "сделать отчёт", start=False)
OUT = t.dir / "outputs"


def tree():
    """outputs/ -> {путь: байты}."""
    return {p.relative_to(OUT).as_posix(): p.read_bytes() for p in sorted(OUT.rglob("*")) if p.is_file()} if OUT.is_dir() else {}


def step(n, name, **a):
    t.data["steps"] = n
    return tm._tool(t, name, a)


before = {}                                  # шаг -> outputs/ перед ним
before[1] = tree()
step(1, "write_file", path="outputs/отчёт.md", content="# Отчёт\n\nверсия 1\n")
step(1, "write_file", path="outputs/данные.csv", content="a;b\n1;2\n")          # вторая запись того же шага — без снимка
before[2] = tree()
step(2, "file_edit", path="outputs/отчёт.md", old="версия 1", new="версия 2")
step(2, "write_file", path="заметка.txt", content="не outputs — снимок не нужен")
before[3] = tree()
r = step(3, "run_python", code="import os\nos.makedirs('outputs/графики', exist_ok=True)\n"
                               "open('outputs/графики/g.svg','w').write('<svg/>')\nopen('outputs/данные.csv','w').write('испорчено')\n"
                               "os.remove('outputs/отчёт.md')")
ok(r.startswith("Код выхода 0"), f"run_python шагом 3: {r[:60]!r}")
before[4] = tree()
step(4, "write_file", path="outputs/бинарь.bin", content="")
(OUT / "бинарь.bin").write_bytes(bytes(range(256)) * 10)           # и двоичное содержимое (запись «руками» внутри шага)
before[5] = tree()
step(5, "log", text="без записи")                                    # шаг без записи — снимка нет
before[6] = tree()
step(6, "write_file", path="outputs/итог.md", content="итог")
after = tree()
snaps = SN.Snapshots(t.dir).listing()
ok([x["step"] for x in snaps if x["kind"] == "step"] == [6, 4, 3, 2, 1], f"снимки — по одному на шаг с записью в outputs/: {[x['step'] for x in snaps]}")
lst = tm._tool(t, "rewind", {})
ok("перед шагом 6" in lst and "перед шагом 1" in lst and "rewind(step=N)" in lst, f"список снимков понятен модели: {lst[:120]!r}")

# откат к шагу 3: outputs/ — ровно как перед шагом 3
t.data["outputs"] = [{"path": "outputs/графики/g.svg", "title": "график"}, {"path": "outputs/отчёт.md", "title": "отчёт"}]
r = step(7, "rewind", step=3)
ok(tree() == before[3] and "как перед шагом 3" in r and "откат можно отменить" in r, f"rewind(3): outputs/ — байт в байт как перед шагом 3: {r[:120]!r}")
ok(not (OUT / "графики").exists(), "лишнее (файлы и пустые папки) убрано")
ok([o["path"] for o in t.data["outputs"]] == ["outputs/отчёт.md"], "в «Результатах» — только файлы, которые есть")
ok("⏪ Откат (задача)" in (t.dir / "журнал.md").read_text(encoding="utf-8"), "откат — в журнале")
ok((t.dir / "заметка.txt").exists(), "откат трогает только outputs/")
for n in (4, 2, 1):
    tm._tool(t, "rewind", {"step": n})
    ok(tree() == before[n], f"rewind({n}) — ровно как перед шагом {n}")
r = step(8, "rewind", step=5)
ok(tree() == before[6] and "как перед шагом 6" in r, "rewind(5): шаг 5 ничего не писал — вид перед шагом 6")
ok("не менялся" in tm._tool(t, "rewind", {"step": 9}), "rewind после последней записи — «откатывать нечего»")
# отменить откат: снимок «перед откатом»
undo = [x for x in SN.Snapshots(t.dir).listing() if x["kind"] == "undo"]
ok(len(undo) >= 4, f"каждый откат сохранил прежний вид ({len(undo)})")
tm._tool(t, "rewind", {"step": 1})
ok(tree() == {}, "к шагу 1 — outputs/ пуст")
last_undo = SN.Snapshots(t.dir).listing()[0]
msg = tm.rewind(t.id, seq=last_undo["seq"])
ok(tree() == before[6] and "снимке" in msg, f"студия: «Вернуть как было» — откат отменён: {msg[:80]!r}")
ok(any("Человек откатил" in x for x in t.data.get("sys_notes") or []), "задача узнает, что человек откатил результаты")

# студия: пока задача работает — нельзя
t.data["status"] = "running"
t.thread = threading.Thread(target=lambda: threading.Event().wait(5), daemon=True)
t.thread.start()
try:
    tm.rewind(t.id, step=2)
    ok(False, "работающую задачу откатывать нельзя")
except ValueError as e:
    ok("сначала остановите" in str(e), f"работающую задачу студия не откатывает: {e}")
t.data["status"] = "paused"
t.thread = None
ok(tm.rewind(t.id, step=2) and tree() == before[2], "остановленную — откатывает (к шагу 2)")

# подменённый снимок: путь «../» — отказ, снаружи ничего не появилось
sn = SN.Snapshots(t.dir)
d = sn.all()[-1]
bad = dict(d, seq=999, kind="step", step=100, files=dict(d["files"], **{"../../снаружи.txt": list(d["files"].values())[0]}))
(t.dir / "_snap" / "999.json").write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
r = tm._tool(t, "rewind", {"step": 100})
ok(r.startswith("Ошибка") and "испорчен" in r and not (t.dir.parent / "снаружи.txt").exists() and tree() == before[2],
   f"подменённый снимок — отказ, outputs/ не тронут: {r[:80]!r}")
(t.dir / "_snap" / "999.json").unlink()

# снимки ограничены: число и объём; удалённый — честная ошибка
SN.SNAP_MAX, SN.OBJ_MAX = 5, 300 << 10
t2 = tm.create("Пределы", "много шагов", start=False)
for n in range(1, 13):
    t2.data["steps"] = n
    tm._tool(t2, "write_file", {"path": "outputs/f.bin", "content": (f"{n % 10}" * 100_000)})    # по ~100 КБ нового за шаг
s2 = SN.Snapshots(t2.dir)
objs = [p for p in (t2.dir / "_snap" / "objects").rglob("*") if p.is_file()]
size = sum(p.stat().st_size for p in objs)
ok(len(s2.all()) <= 5, f"снимков не больше предела ({len(s2.all())})")
ok(size <= SN.OBJ_MAX, f"содержимое снимков ограничено ({size // 1024} КБ при пределе {SN.OBJ_MAX // 1024} КБ)")
r = tm._tool(t2, "rewind", {"step": 2})
ok(r.startswith("Ошибка") and "уже удалён" in r and "самый ранний" in r, f"удалённый снимок — честно: {r[:120]!r}")
first = min(x["step"] for x in s2.listing() if x["kind"] == "step")
r = tm._tool(t2, "rewind", {"step": first})
ok("как перед шагом" in r and (t2.dir / "outputs/f.bin").read_text() == f"{(first - 1) % 10}" * 100_000,
   f"самый ранний оставшийся — откатывается (к шагу {first})")
SN.SNAP_MAX, SN.OBJ_MAX = 40, 256 << 20
ok("_snap" in TK.Q.SERVICE and "_snap" not in tm._tool(t2, "file_glob", {"pattern": "**/*"}) and "_snap" not in tm._tool(t2, "list_files", {}),
   "снимки — служебное: не в списках файлов и не «продвижение»")
r = tm._tool(t2, "write_file", {"path": "_snap/1.json", "content": "{}"})
ok(r.startswith("Ошибка") and "служебный" in r, "write_file в _snap/ — отказ (снимки ведёт Dewiar)")

# целиком: модель портит файл и сама откатывает; человек откатывает — задача узнаёт на следующем шаге
A = "Порча и откат"
mock.scripts[A] = [("write_file", {"path": "outputs/страница.html", "content": "<html><body>хорошая</body></html>"}),
                   ("run_python", {"code": "open('outputs/страница.html','w').write('сломано')"}),
                   ("rewind", {"step": 2}),
                   ("file_read", {"path": "outputs/страница.html"}),
                   ("show", {"path": "outputs/страница.html"}),
                   ("finish", {"summary": "Готово: outputs/страница.html"})]
ta = tm.create(A, "страница", start=True)
ok(wait_for(lambda: ta.status in ("done", "failed"), 60), f"задача с откатом дошла до конца ({ta.status} {ta.data.get('error', '')})")
ok((ta.dir / "outputs/страница.html").read_text(encoding="utf-8") == "<html><body>хорошая</body></html>",
   "модель откатила испорченный файл инструментом rewind")
reqs = mock.of(A)
ok(any("хорошая" in json.dumps(r_["messages"], ensure_ascii=False) and "как перед шагом 2" in json.dumps(r_["messages"], ensure_ascii=False) for r_ in reqs),
   "модель видела итог отката и файл после него")
B = "Человек откатил"
mock.scripts[B] = [("write_file", {"path": "outputs/a.md", "content": "раз"}), ("write_file", {"path": "outputs/a.md", "content": "два"}),
                   ("wait", {"minutes": 60, "reason": "жду"}), ("finish", {"summary": "готово: outputs/a.md"})]
tb = tm.create(B, "файл", start=True)
ok(wait_for(lambda: tb.status == "sleeping", 30), "задача уснула")
ok(wait_for(lambda: not (tb.thread and tb.thread.is_alive()), 10), "поток задачи ушёл")
msg = tm.rewind(tb.id, step=2)
ok((tb.dir / "outputs/a.md").read_text(encoding="utf-8") == "раз", f"студия откатила спящую задачу к шагу 2: {msg}")
tm.start(tb.id)
ok(wait_for(lambda: tb.status in ("done", "failed"), 60), "задача продолжила и закончила")
ok(any("Сообщение Dewiar" in json.dumps(r_["messages"], ensure_ascii=False) and "Человек откатил" in json.dumps(r_["messages"], ensure_ascii=False)
       for r_ in mock.of(B)), "об откате человеком задача узнала следующим шагом")

# студия: вкладка «Снимки» — кнопка «Откатить к шагу N» зовёт task_rewind, у работающей — выключена
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None
    print("⚠ playwright нет — проверка студии пропущена")
if sync_playwright:
    import re
    d = tm.detail(t.id)
    d.update(status="paused", status_ru="на паузе")
    CORE = """(() => { const ready = () => { if (!window.core) return setTimeout(ready, 5);
        core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
        window.TASK = TASK_JSON; window.CALLS = []; window.ask = async () => true;
        core.call = async (c, a) => { window.CALLS.push([c, a]); if (c === "task_get") return window.TASK; if (c === "tasks_list") return [window.TASK];
          if (c === "task_rewind") return "outputs/ — как перед шагом 2"; return null; };
        setTimeout(() => core.emit("hello", {}), 200); };
      ready(); })();""".replace("TASK_JSON", json.dumps(d, ensure_ascii=False))
    with sync_playwright() as p:
        b = p.chromium.launch()
        errs = []
        pg = b.new_page(viewport={"width": 1300, "height": 900})
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.route(re.compile(r"^https?://"), lambda r_: r_.abort())
        pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };")
        pg.add_init_script(CORE)
        pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1")
        pg.wait_for_timeout(1500)
        pg.evaluate("document.querySelector('nav button[data-p=\"tasks\"]').click()")
        pg.wait_for_timeout(300)
        pg.evaluate("openTask('%s')" % t.id)
        pg.wait_for_timeout(400)
        pg.click('#t-view [data-tab="snaps"]')
        pg.wait_for_timeout(400)
        txt = pg.inner_text("#t-view")
        ok(any(x in txt for x in ("Песочница", "Защита ядра", "Охрана кода", "Без песочницы")), "студия: строка о песочнице кода")
        ok(pg.locator("#t-view .snap").count() == len(d["snaps"]) and "Откатить к шагу 2" in txt and "Вернуть как было" in txt,
           f"студия: список снимков ({pg.locator('#t-view .snap').count()}) с кнопками «Откатить к шагу N» и «Вернуть как было»")
        pg.click('#t-view [data-snap="s2"]')
        pg.wait_for_timeout(400)
        calls = pg.evaluate("window.CALLS.filter(c => c[0] === 'task_rewind')")
        ok(calls and calls[0][1] == {"id": t.id, "step": 2}, f"«Откатить к шагу 2» → task_rewind {calls[:1]}")
        pg.click('#t-view #t-net')
        pg.wait_for_timeout(300)
        ok(pg.evaluate("window.CALLS.some(c => c[0] === 'task_net' && c[1].on === true)"), "переключатель «Интернет для кода задачи» → task_net")
        if os.environ.get("DEWIAR_SHOTS"):
            pg.locator("#t-view").screenshot(path=os.environ["DEWIAR_SHOTS"] + "/task-snaps.png")
        pg.evaluate("window.TASK.status = 'running'; openTask('%s')" % t.id)
        pg.wait_for_timeout(400)
        ok(pg.locator('#t-view [data-snap][disabled]').count() == len(d["snaps"]), "у работающей задачи кнопки отката выключены")
        ok(not errs, f"без ошибок на странице {errs[:2]}")
        b.close()
done()
