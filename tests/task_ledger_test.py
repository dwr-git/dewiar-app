"""Выпуск 4 «Больших задач» (docs/HARNESS.md): план-учёт и смена плана.
— список дел задачи.json (todo_update): pending / in_progress / done / blocked; done — только с доказательством (путь к
  файлу, который есть, вывод, ссылка); update_plan (Markdown) — совместимо, пишет и задачи.json;
— застой (шаги без продвижения) — новый план с записью в журнал, а не пауза; пауза — только на втором застое подряд;
— опрос хода раз в POLL_EVERY шагов: «петля, хода нет» — тоже новый план; «дальше — …» — в «Состоянии задачи»;
— продолжение после перезапуска (и после ожидания) начинается со сверки: прогресс, файлы, «сделано» без доказательства —
  снова в работу."""
import json
import os
import threading

os.environ.update(DEWIAR_TASK_STUCK_STEPS="6", DEWIAR_TASK_BROWSER="0", DEWIAR_TASK_POLL_LOCAL="8")   # заглушка модели — на 127.0.0.1
from task_mock import Host, Mock, done, ok, wait_for  # noqa: E402
import tasks as TK  # noqa: E402

mock = Mock({})
POLL = {}                                    # цель задачи -> ответ на опрос хода


def side(sysm, body):
    if sysm.startswith("Ты — наблюдатель хода"):
        user = body["messages"][-1]["content"]
        ASKED.append(user)
        for goal, ans in POLL.items():
            if goal in user:
                return ans
    return None


ASKED = []
mock.side_fn = side
host = Host(mock)
tm = TK.TaskManager(host)


def journal(t):
    return (t.dir / "журнал.md").read_text(encoding="utf-8")


def last_user(req):
    for m in reversed(req["messages"]):
        c = m.get("content")
        if m["role"] in ("user", "tool") and isinstance(c, str) and not c.startswith("[Состояние задачи"):
            return c
    return ""


def said(req, text):
    return any(text in str(m.get("content")) for m in req["messages"] if m["role"] == "user")


# ---------- 1. done — только с доказательством; update_plan совместим ----------
t = tm.create("Учёт", "Собрать данные и сделать отчёт outputs/отчёт.md", start=False)
r = tm._tool_raw(t, "todo_update", {"items": [{"text": "собрать данные", "status": "in_progress"}, {"text": "сделать отчёт"}, {"text": "отправить"}]})
ok("сделано 0 из 3" in r and [x["status"] for x in t.todos()] == ["in_progress", "pending", "pending"], f"список дел записан: {r}")
r = tm._tool_raw(t, "todo_update", {"items": [{"id": 1, "status": "done"}]})
ok(r.startswith("Ошибка") and "НЕ отмечен сделанным" in r and "доказательств" in r and t.todos()[0]["status"] == "in_progress",
   f"done без доказательства не принят: {r[:120]}")
r = tm._tool_raw(t, "todo_update", {"items": [{"id": 1, "status": "done", "evidence": "готово"}]})
ok("не доказательство" in r and t.todos()[0]["status"] != "done", "«готово» — не доказательство")
r = tm._tool_raw(t, "todo_update", {"items": [{"id": 2, "status": "done", "evidence": "outputs/отчёт.md"}]})
ok("файла outputs/отчёт.md нет" in r and t.todos()[1]["status"] == "pending", "путь к файлу, которого нет, — не доказательство")
(t.dir / "outputs").mkdir(exist_ok=True)
(t.dir / "outputs/отчёт.md").write_text("# Отчёт\n", encoding="utf-8")
r = tm._tool_raw(t, "todo_update", {"items": [{"id": 1, "status": "done", "evidence": "https://example.org/data — 120 строк"},
                                              {"id": 2, "status": "done", "evidence": "outputs/отчёт.md"},
                                              {"id": 3, "status": "blocked"}]})
st = [x["status"] for x in t.todos()]
ok(st == ["done", "done", "pending"] and "blocked — напиши в evidence" in r, f"ссылка и существующий файл — доказательства; blocked — только с причиной: {st}")
r = tm._tool_raw(t, "todo_update", {"items": [{"id": 3, "status": "blocked", "evidence": "нет адреса получателя"}, {"text": "показать", "status": "in_progress"}]})
plan = (t.dir / "план.md").read_text(encoding="utf-8")
ok("- [x] 1. собрать данные — ✓ https://example.org" in plan and "- [-] 3. отправить _(не сделать: нет адреса получателя)_" in plan
   and "_(в работе)_" in plan, "план.md — из списка дел: сделано с доказательством, не сделать — с причиной")
ok(t.data["progress"] == [2, 4], f"ход по списку дел: {t.data['progress']}")
s = tm._state(t)
ok("СПИСОК ДЕЛ (сделано 2 из 4" in s and "▶ 4. показать (в работе)" in s and "✓ 2. сделать отчёт — outputs/отчёт.md" in s,
   "список дел со статусами — в «Состоянии задачи» в конце запроса")
d = tm.detail(t.id)
ok([x["status"] for x in d["todos"]] == ["done", "done", "blocked", "in_progress"], "студии — список дел со статусами")
tm._tool_raw(t, "todo_update", {"items": [{"text": "проверить отчёт", "status": "in_progress"}]})
ok([x["status"] for x in t.todos()][3:] == ["pending", "in_progress"], "«в работе» — один пункт за раз")
t2 = tm.create("Старый план", "x", start=False)
r = tm._tool_raw(t2, "update_plan", {"plan": "**Готово, когда:** файл есть\n\n- [x] шаг один — 120 строк\n- [x] шаг полтора\n- [ ] шаг два"})
ok([(x["text"].split(" —")[0], x["status"]) for x in t2.todos()] == [("шаг один", "done"), ("шаг полтора", "in_progress"), ("шаг два", "pending")]
   and t2.data["progress"] == [1, 3] and "без доказательства" in r,
   f"update_plan (Markdown) — и в задачи.json; «[x]» без доказательства — «в работе» (рецензия 0.84): {r[-120:]}")
ok("ТЕКУЩИЙ ПЛАН:" in tm._state(t2) and "Готово, когда" in tm._state(t2), "план из update_plan виден модели, как раньше")

# рецензия 0.84: пустышки и служебные файлы — не доказательство; «USD/RUB» и «05/11» — не пути
tp = tm.create("Пробы доказательств", "x", start=False)
bad = ["всё сделано", "Сделала.", "ок, проверила", "журнал.md", "задача.json", "план.md", "USD/RUB", "ветка fix/login", "outputs/", "https://x"]
good = ["05/11 — 3 письма", "код 0: 12 passed", "km/h 120", "https://example.org/a"]
ok(all(tm._proof_bad(tp, e) for e in bad) and not any(tm._proof_bad(tp, e) for e in good),
   f"доказательство — путь к своему файлу, ссылка или вывод с цифрами: {[e for e in bad if not tm._proof_bad(tp, e)]} {[e for e in good if tm._proof_bad(tp, e)]}")
D = "Пустышки"
mock.scripts[D] = [("todo_update", {"items": [{"text": "собрать данные"}, {"text": "написать"}, {"text": "проверить"}]}),
                   ("todo_update", {"items": [{"id": 1, "status": "done", "evidence": "всё сделано"}, {"id": 2, "status": "done", "evidence": "журнал.md"},
                                              {"id": 3, "status": "done", "evidence": "проверила лично"}]}), ("finish", {"summary": "Готово."})]
tdd = tm.create(D, "Заметка outputs/з.md")
wait_for(lambda: tdd.status in ("done", "failed", "paused"), 30)
ok([x["status"] for x in tdd.todos()] == ["pending"] * 3, f"D: «всё сделано», «журнал.md», «проверила лично» — не приняты: {[x['status'] for x in tdd.todos()]}")
# задача 0.83: план чек-листом, задачи.json нет — первый todo_update его не теряет
t3 = tm.create("План 0.83", "x", start=False)
(t3.dir / "план.md").write_text("# План\n\n- [ ] собрать\n- [ ] свести\n", encoding="utf-8")
tm._tool_raw(t3, "todo_update", {"items": [{"text": "показать"}]})
ok([x["text"] for x in t3.todos()] == ["собрать", "свести", "показать"], f"задача 0.83: пункты старого плана сохранены: {[x['text'] for x in t3.todos()]}")
TK.POLL_LOCAL = 3 * TK.POLL_EVERY
ok(TK.TaskManager._poll_every({"base_url": "http://127.0.0.1:8080/v1"}) == 3 * TK.POLL_EVERY
   and TK.TaskManager._poll_every({"base_url": "http://192.168.1.5:1234/v1"}) == 3 * TK.POLL_EVERY
   and TK.TaskManager._poll_every({"base_url": "https://api.anthropic.com", "kind": "anthropic"}) == TK.POLL_EVERY,
   "свой сервер модели (кэш одного разговора) — опрос хода втрое реже")
TK.POLL_LOCAL = TK.POLL_EVERY

# ---------- 2. застой -> новый план, а не пауза ----------
A = "Застой"
(TK.Path(host.workspace.root) / "данные.txt").write_text("\n".join(f"строка {i}" for i in range(400)), encoding="utf-8")
st_a = {"replanned": False, "n": 0}


def step_a(req):
    if said(req, "ЗАСТОЙ:") and not st_a["replanned"]:
        st_a["replanned"] = True
        return ("todo_update", {"replace": True, "items": [{"text": "свести данные скриптом", "status": "in_progress"}]})
    if st_a["replanned"]:
        st_a["n"] += 1
        return [("write_file", {"path": "outputs/свод.md", "content": "# Свод\n\nстрок: 400\n"}),
                ("todo_update", {"items": [{"text": "свести данные скриптом", "status": "done", "evidence": "outputs/свод.md"}]}),
                ("show", {"path": "outputs/свод.md"}), ("finish", {"summary": "Свод — outputs/свод.md."})][min(st_a["n"] - 1, 3)]
    k = req["i"]
    return ("file_read", {"path": str(TK.Path(host.workspace.root) / "данные.txt"), "start": 1 + k * 3, "end": 3 + k * 3}) if k else \
        ("todo_update", {"items": [{"text": "прочитать данные", "status": "in_progress"}, {"text": "свести"}]})


mock.scripts[A] = [step_a] * 60
ta = tm.create(A, "Свести данные из файла данные.txt", folders=[str(host.workspace.root)])
ok(wait_for(lambda: ta.status in ("done", "failed", "paused"), 60), f"задача закончилась ({ta.status})")
j = journal(ta)
ok(ta.status == "done" and "🔄 Застой" in j and "⏸" not in j, f"застой — новый план и работа дальше, а не пауза ({ta.status}; шагов {ta.steps})")
lj = json.loads((ta.dir / "задачи.json").read_text(encoding="utf-8"))
ok(len(lj.get("replans") or []) >= 2 and any("прочитать данные" in " ".join(x.get("was") or []) for x in lj["replans"]),
   f"смена плана записана: застой и прежний план ({len(lj.get('replans') or [])})")
ok([x["text"] for x in lj["items"]] == ["свести данные скриптом"] and lj["items"][0]["status"] == "done", "новый план — вместо прежнего")

# ---------- 3. второй застой подряд без работы — пауза ----------
B = "Застой дважды"
mock.scripts[B] = [("file_read", {"path": str(TK.Path(host.workspace.root) / "данные.txt"), "start": 1 + k, "end": 1 + k}) for k in range(80)]
tb = tm.create(B, "Прочитать данные.txt", folders=[str(host.workspace.root)])
ok(wait_for(lambda: tb.status in ("done", "failed", "paused"), 60) and tb.status == "paused", f"второй застой — пауза ({tb.status}, шагов {tb.steps})")
jb = journal(tb)
ok(jb.count("🔄 Застой") == 1 and "после смены плана" in jb and any("буксует" in s for s in host.said), "сначала новый план, потом пауза с причиной")

# ---------- 3б. №551: скрипты шагов (_run/шагN.py) — не продвижение ----------
R = "Скрипты по кругу"
mock.scripts[R] = [("run_python", {"code": f"print('проверка {k}')"}) for k in range(40)] + [("finish", {"summary": "Готово."})]
tr = tm.create(R, "Разобраться с данными")
ok(wait_for(lambda: tr.status in ("done", "failed", "paused"), 90), f"задача остановилась ({tr.status})")
jr = journal(tr)
nrun = len(list((tr.dir / "_run").glob("*.py"))) if (tr.dir / "_run").is_dir() else 0
ok("🔄 Застой" in jr and tr.steps < 40 and tr.status == "paused", f"40 run_python, которые оставляют только _run/*.py, — застой, новый план, потом пауза "
   f"(шагов {tr.steps}, {tr.status}, скриптов {nrun})")
(tr.dir / "_run" / "ещё.py").parent.mkdir(exist_ok=True)
s0, w0 = TK.TaskManager._progress_sig(tr), tm._work_sig(tr)
(tr.dir / "_run" / "ещё.py").write_text("print(1)", encoding="utf-8")
(tr.dir / "_out").mkdir(exist_ok=True)
(tr.dir / "_out" / "run_python-99.txt").write_text("x" * 5000, encoding="utf-8")
ok(TK.TaskManager._progress_sig(tr) == s0 and tm._work_sig(tr) == w0, "_run/ и _out/ не меняют ни отпечаток продвижения, ни отпечаток работы")
(tr.dir / "outputs").mkdir(exist_ok=True)
(tr.dir / "outputs" / "итог.md").write_text("# Итог\n", encoding="utf-8")
ok(TK.TaskManager._progress_sig(tr) != s0 and tm._work_sig(tr) != w0, "а файл результата — меняет")

# ---------- 4. опрос хода: «петля» — новый план; «дальше» — в состоянии ----------
C = "Опрос"
POLL["Сводка для опроса хода"] = '{"done": false, "loop": true, "progress": false, "next": "свести данные одним скриптом"}'
st_c = {"n": 0}


def step_c(req):
    if said(req, "опрос хода: задача ходит по кругу"):
        st_c["n"] += 1
        return [("write_file", {"path": "outputs/итог.md", "content": "# Итог\n"}), ("show", {"path": "outputs/итог.md"}),
                ("finish", {"summary": "Итог — outputs/итог.md."})][min(st_c["n"] - 1, 2)]
    return ("log", {"text": f"смотрю строку {req['i']}"})


mock.scripts[C] = [step_c] * 30
tc = tm.create(C, "Сводка для опроса хода")
ok(wait_for(lambda: tc.status in ("done", "failed", "paused"), 60) and tc.status == "done", f"опрос хода сработал, задача доделана ({tc.status})")
jc = journal(tc)
ok("🧭 Опрос хода: хода нет, ходит по кругу. Дальше: свести данные одним скриптом" in jc and "🔄 Застой (опрос хода" in jc, "«петля, хода нет» — новый план")
r9 = [x for x in mock.of(C) if x["i"] == TK.POLL_EVERY][0]
ok("Опрос хода (шаг 8): дальше — свести данные одним скриптом" in r9["messages"][-1]["content"], "«что дальше» — в «Состоянии задачи»")
polls = [x for x in ASKED if "Сводка для опроса хода" in x]
ok(len(polls) == tc.steps // TK.POLL_EVERY and all(len(x) < 4000 for x in polls), f"опрос — короткий и раз в {TK.POLL_EVERY} шагов: {len(polls)} за {tc.steps} шагов")

# опрос «петля», а работа идёт (файлы пишутся) — не меняем план
C2 = "Опрос при работе"
POLL["Сводка с работой"] = '{"done": false, "loop": true, "progress": false, "next": "дальше"}'
mock.scripts[C2] = [("write_file", {"path": f"outputs/ч{k}.md", "content": f"# {k}\n"}) for k in range(17)] + [
    ("show", {"path": "outputs/ч0.md"}), ("finish", {"summary": "Готово: outputs/ч0.md"})]
tw = tm.create(C2, "Сводка с работой")
ok(wait_for(lambda: tw.status in ("done", "failed", "paused"), 60) and tw.status == "done" and "🔄" not in journal(tw)
   and journal(tw).count("🧭 Опрос хода") == 2, "опрос «петля», а файлы прибавляются — план не меняется")

# ---------- 5. продолжение после перезапуска — со сверки ----------
D = "Перезапуск"
gate, stopped = threading.Event(), threading.Event()


def hold(req):
    gate.set()
    stopped.wait(20)
    return ("log", {"text": "работаю"})


mock.scripts[D] = [("todo_update", {"items": [{"text": "первая половина"}, {"text": "вторая половина"}]}),
                   ("write_file", {"path": "outputs/часть1.csv", "content": "a;b\n1;2\n"}),
                   ("todo_update", {"items": [{"id": 1, "status": "done", "evidence": "outputs/часть1.csv"}]}),
                   hold,
                   ("write_file", {"path": "outputs/часть1.csv", "content": "a;b\n1;2\n"}),
                   ("todo_update", {"items": [{"id": 1, "status": "done", "evidence": "outputs/часть1.csv"}, {"id": 2, "status": "done", "evidence": "outputs/часть1.csv, строки 2"}]}),
                   ("show", {"path": "outputs/часть1.csv"}), ("finish", {"summary": "Готово: outputs/часть1.csv."})]
td = tm.create(D, "Две половины работы")
ok(wait_for(gate.is_set, 30), "задача дошла до середины")
tm.stop(td.id)
stopped.set()
ok(wait_for(lambda: not (td.thread and td.thread.is_alive()), 20), "поток задачи остановлен")
(td.dir / "outputs/часть1.csv").unlink()                 # результат пропал, пока программа была выключена
td.data["status"] = "running"                             # как будто программу выключили посреди работы
td.save()
host2 = Host(mock)
tm2 = TK.TaskManager(host2)
t2 = tm2.get(td.id)
ok(t2.status == "paused" and t2.data.get("auto_resume"), "после запуска программы — пауза с автопродолжением")
ok(wait_for(lambda: t2.status in ("done", "failed"), 40) and t2.status == "done", f"продолжила и доделала ({t2.status} {t2.error})")
first = [x for x in mock.of(D) if x["i"] == 4][0]
lu = last_user(first)
ok("СВЕРКА ПЕРЕД ПРОДОЛЖЕНИЕМ (после перезапуска программы)" in lu and "сделано 0 из 2" in lu and "снова в работе: 1. первая половина" in lu,
   f"первый запрос после перезапуска — со сверки: прогресс, файлы, «сделано» без доказательства — снова в работе: {lu[-300:]}")
jd = journal(t2)
ok("🔎 Сверка перед продолжением (после перезапуска программы)" in jd and jd.count("▶ Начал работу") == 1, "в журнале — сверка, а не начало заново")

# ---------- 6. после ожидания — тоже сверка ----------
E = "Ожидание"
mock.scripts[E] = [("todo_update", {"items": [{"text": "дождаться ответа"}]}), ("wait", {"minutes": 0.02, "reason": "ответ на письмо"}),
                   ("finish", {"summary": "Ответ пришёл."})]
te = tm.create(E, "Дождаться ответа")
ok(wait_for(lambda: te.status in ("done", "failed"), 40) and te.status == "done", f"проснулась и закончила ({te.status})")
w = last_user([x for x in mock.of(E) if x["i"] == 2][0])
ok("⏰ Ты ждал" in w and "СВЕРКА ПЕРЕД ПРОДОЛЖЕНИЕМ (после ожидания)" in w, "после ожидания — сверка")
host.stopping.set()
host2.stopping.set()
done()
