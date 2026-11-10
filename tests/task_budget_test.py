"""Выпуск 7 «Больших задач» (начало, docs/HARNESS.md): бюджет задачи в токенах (tasks.budget_tokens / create(budget_tokens)).
— 50 % — весточка человеку и строка в журнале; в «Состоянии задачи» — сколько потрачено;
— 80 % — задаче «подведи итог сейчас» (finish: сделано, не успела, что осталось);
— послушалась — итог; не послушалась ещё 3 шага — пауза с причиной голосом и уведомлением (не тратит дальше);
— «продолжи» человека — бюджет ещё на столько же, задача продолжает;
— у частей своего бюджета задачи нет (у них limits выпуска 6); без бюджета — ничего не меняется.
Модель — заглушка (task_mock): токены запроса считает сервер-заглушка (prompt_tokens)."""
import os

os.environ["DEWIAR_TASK_BROWSER"] = "0"
from task_mock import Host, Mock, done, ok, wait_for  # noqa: E402
import tasks as TK  # noqa: E402

mock = Mock({})
host = Host(mock)
tm = TK.TaskManager(host)


def journal(t):
    return (t.dir / "журнал.md").read_text(encoding="utf-8")


def last_text(req):
    return "\n".join(str(m.get("content")) for m in req["messages"][-3:])


def settle(t, sec=40):
    return wait_for(lambda: t.status in ("done", "failed", "paused", "stopped") and not (t.thread and t.thread.is_alive()), sec)


# ---------- 1. не слушается — пауза на 80 % + 3 шага; «продолжи» — ещё столько же, итог ----------
A = "Бюджет — пауза"


def step_a(i):
    def f(req):
        t = tm.get(A)
        if int((t.data.get("budget") or {}).get("tokens") or 0) > 12000:      # после «продолжи» — сдаёт итог
            return ("finish", {"summary": "Собрала факты, итог — в блокноте."})
        return ("remember", {"fact": f"факт номер {i} про поставщиков"})
    return f


mock.scripts[A] = [step_a(i) for i in range(40)]
t = tm.create(A, "Собери факты о поставщиках", budget_tokens=12000)
ok(t.data.get("budget") == {"tokens": 12000, "base": 12000}, f"бюджет задачи записан: {t.data.get('budget')}")
ok(settle(t), f"задача остановилась ({t.status})")
ok(t.status == "paused", f"бюджет кончился, итога нет — пауза ({t.status} {t.error})")
j = journal(t)
ok("💰 Потрачено" in j and "% бюджета задачи" in j and any("половина бюджета" in p[0] for p in host.pushes), "50 % — строка в журнале и весточка")
reqs = mock.of(A)
warned = [r for r in reqs if "БЮДЖЕТ ЗАДАЧИ НА ИСХОДЕ" in last_text(r)]
ok(warned, "80 % — задаче сказано подвести итог")
stop_at = int(t.data.get("budget_stop") or 0)
ok(int(t.data["steps"]) == stop_at + TK.BUDGET_GRACE, f"пауза через {TK.BUDGET_GRACE} шага после просьбы ({t.data['steps']} / {stop_at})")
ok(any("на паузе: потрачено" in s for s in host.said) and any("Задача на паузе" in p[0] for p in host.pushes), f"голосом и уведомлением — почему: {host.said[-1:]}")
ok(any("Бюджет задачи: потрачено" in last_text(r) for r in reqs), "в «Состоянии задачи» — сколько бюджета потрачено")
ok(t.public().get("budget_pct", 0) >= 80, f"в карточке — процент бюджета ({t.public().get('budget_pct')})")
n_before = len(reqs)
tm.start(t.id)                                       # человек: «продолжи задачу»
ok(settle(t), f"после «продолжи» задача закончилась ({t.status})")
spent0 = TK.task_spent(t.data)
ok(t.status == "done" and t.data["budget"]["tokens"] >= 24000 and "Бюджет увеличен" in journal(t)
   and not any("БЮДЖЕТ ЗАДАЧИ НА ИСХОДЕ" in last_text(r) for r in mock.of(A)[n_before:]),
   f"«продолжи» — бюджет: потраченное + ещё столько же (сразу «на исходе» не говорит), итог ({t.status}, {t.data.get('budget')})")
ok(len(mock.of(A)) - n_before <= 3, "после продолжения — без лишних шагов")

# ---------- 2. послушалась на 80 % — итог, а не пауза ----------
B = "Бюджет — итог"


def step_b(i):
    def f(req):
        if "БЮДЖЕТ ЗАДАЧИ НА ИСХОДЕ" in last_text(req):
            return ("finish", {"summary": "Сделано: собрала факты (в блокноте). Не успела: сравнение — осталось на потом."})
        return ("remember", {"fact": f"запись {i}"})
    return f


mock.scripts[B] = [step_b(i) for i in range(40)]
t = tm.create(B, "Собери факты", budget_tokens=12000)
ok(settle(t) and t.status == "done" and "Не успела" in (t.result or ""), f"на 80 % задача подвела итог сама ({t.status})")

# ---------- 3. без бюджета — как раньше; у частей бюджета задачи нет ----------
C = "Без бюджета"
mock.scripts[C] = [("remember", {"fact": f"x{i}"}) for i in range(6)] + [("finish", {"summary": "Готово."})]
t = tm.create(C, "Просто задача")
ok(settle(t) and t.status == "done" and "budget" not in t.data and "budget_pct" not in t.public(), "без бюджета — ничего не меняется")
ok(not any("Бюджет задачи" in last_text(r) for r in mock.of(C)), "без бюджета — строки о бюджете нет")
kid = tm.create("Часть", "часть", start=False, parent=t.id, budget_tokens=5000)
ok("budget" not in kid.data, "у части бюджета задачи нет (у неё limits выпуска 6)")
src = (TK.Path(TK.__file__)).read_text(encoding="utf-8")
ok('"budget_tokens": 0' in (TK.Path(TK.__file__).parent / "settings.py").read_text(encoding="utf-8"), "настройка tasks.budget_tokens (0 — без предела)")

host.stopping.set()
done()
