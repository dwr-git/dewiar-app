"""HARNESS, выпуск 7 «Бюджет и голос» (docs/HARNESS.md; владелец 12.11: «харнесс — важнейшее»): большую задачу Лира не
запускает молча — по завершённым задачам того же вида знает, сколько такая обычно идёт и стоит, и сначала говорит
человеку «план в двух фразах, срок, цена — начинаю?». Простые и без истории — сразу; «да» — start_task с confirmed;
дело по расписанию — спросить некого, запускаем."""
import datetime as dt, os, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import tasks  # noqa: E402
import tools  # noqa: E402

ok([tasks.task_kind(g) for g in ("Исследуй рынок кофеен Минска", "Сделай презентацию о проекте", "Почини баг в скрипте",
                                  "Проследи статус возврата билета", "Купи хлеба")] == ["research", "doc", "code", "wait", "other"],
   "вид задачи по цели")


class X:
    def __init__(self, d):
        self.data = d


now = dt.datetime.now()


def done(goal, mins, tok):
    return X({"status": "done", "goal": goal, "created": (now - dt.timedelta(minutes=mins)).isoformat(timespec="seconds"),
              "updated": now.isoformat(timespec="seconds"), "quality": {"usage": {"in": tok, "out": 0}}})


tm = tasks.TaskManager.__new__(tasks.TaskManager)
tm.tasks = {"a": done("Исследуй конкурентов", 35, 2_000_000)}
ok(tm.estimate("Изучи рынок")["tokens"] == 0, "одной похожей задачи мало — оценки нет")
tm.tasks.update(b=done("Сравни тарифы банков", 41, 2_400_000), c=done("Сделай отчёт", 5, 90_000),
                d=X({"status": "failed", "goal": "Изучи рынок", "quality": {}}))
e = tm.estimate("Изучи рынок электросамокатов")
ok(e["kind"] == "research" and e["n"] == 2 and e["minutes"] >= 35 and e["tokens"] >= 2_000_000, f"оценка по похожим завершённым: {e}")

made = []


class TM:
    estimate = tm.estimate

    def create(self, title, goal, project="", **kw):
        made.append(goal)
        return type("T", (), {"title": title})()


ctx = {"tasks": TM(), "talers_for_tokens": lambda n: round(n / 1e6 * 0.4, 2)}
r = tools.t_start_task({"goal": "Изучи рынок электросамокатов в Минске", "title": "Рынок"}, ctx)
ok(r.startswith("НЕ ЗАПУЩЕНО") and "начинаю?" in r and "мин" in r and "талера" in r and not made, f"большая — сначала «план, срок, цена — начинаю?»: {r[:120]}")
r2 = tools.t_start_task({"goal": "Изучи рынок электросамокатов в Минске", "title": "Рынок", "confirmed": True}, ctx)
ok("запущена" in r2 and made, "человек согласился — запущена")
made.clear()
r3 = tools.t_start_task({"goal": "Сделай отчёт по продажам", "title": "Отчёт"}, ctx)
ok("запущена" in r3 and made, "обычно быстрая (или без истории) — сразу")
made.clear()
r4 = tools.t_start_task({"goal": "Изучи рынок самокатов", "_unattended": True}, ctx)
ok("запущена" in r4 and made, "дело по расписанию — спросить некого, запускаем")
spec = tools.TOOLS["start_task"][1] if hasattr(tools, "TOOLS") else None
src = (ROOT / "core/tools.py").read_text(encoding="utf-8")
ok('"confirmed": {"type": "boolean"' in src, "у start_task есть confirmed")
et = (ROOT / "core/engine_tools.py").read_text(encoding="utf-8")
ok('args = dict(args, _unattended=True)' in et and "def _talers_for_tokens" in et, "дело по расписанию помечено; цена — из цен облака")
# большая просьба не влезла в 6 шагов разговора — на последнем шаге предложить задачу (а не молча оборвать)
ea = (ROOT / "core/engine_answer.py").read_text(encoding="utf-8")
i = ea.index("if step == 5 and specs:")
blk = ea[i:i + 1200]
ok('"start_task" not in called' in blk and "Сделать это задачей?" in blk, "последний шаг разговора: не доделал — предлагает «сделать это задачей»")

# весточки на вехах, а не по таймеру
import time  # noqa: E402
pushes = []
tm._push = lambda title, text, **k: pushes.append((title, text))


class TT:
    def __init__(self):
        self.data, self.title, self.run_t0, self.j = {"progress": [1, 4]}, "Рынок", time.monotonic() - 300, []

    def journal(self, x):
        self.j.append(x)


t = TT()
items = [{"id": 1, "text": "Найти источники", "status": "done"}, {"id": 2, "text": "Свести цены в таблицу", "status": "done"},
         {"id": 3, "text": "Написать вывод", "status": "pending"}, {"id": 4, "text": "Проверить", "status": "pending"}]
tm._milestone(t, items)
ok(len(pushes) == 1 and "2 из 4" in pushes[0][0] and "Свести цены" in pushes[0][1], f"пункт сделан — весточка с тем, что готово: {pushes}")
t.data["progress"] = [2, 4]
items[2]["status"] = "done"
tm._milestone(t, items)
ok(len(pushes) == 1, "следующая веха через минуту — молчим (не чаще раза в 3 минуты)")
t.data["milestone_at"] = 0
items[3]["status"] = "done"
t.data["progress"] = [3, 4]
tm._milestone(t, items)
ok(len(pushes) == 1, "последний пункт — без весточки: о нём скажет итог")
t2 = TT()
t2.run_t0 = time.monotonic() - 30
tm._milestone(t2, [dict(x, status="done") if i == 0 else x for i, x in enumerate(items[:1] + [{"id": 9, "text": "x", "status": "pending"}])])
ok(len(pushes) == 1, "первые 2 минуты — без весточек (план только расписан)")

if fails:
    print(f"\n❌ провалов: {len(fails)}")
    sys.exit(1)
print("\n✅ всё в порядке")
