"""Харнесс 1.0.30 (по образцу Aigen, «выборочные рассуждения»): в задаче модель думает перед шагом только в ключевые
моменты — первый шаг, два неудачных шага подряд, отказ проверки перед итогом, повтор одного и того же; не больше 4 раз
за задачу. В остальные шаги — без рассуждений (быстро). «Думать над сложными просьбами» выключено или своя модель с
«думать всегда/никогда» — как раньше. Признак в запросе к модели: нет chat_template_kwargs {"enable_thinking": false}."""
import os

os.environ["DEWIAR_TASK_BROWSER"] = "0"
from task_mock import Host, Mock, done, ok, wait_for  # noqa: E402
import tasks as TK  # noqa: E402


class LS:
    def __init__(self, auto=None):
        self.auto = auto

    def get(self, *k):
        return self.auto if k == ("llm", "think_auto") else None


mock = Mock({})
host = Host(mock)
host.s = LS()
tm = TK.TaskManager(host)


def settle(t, sec=60):
    return wait_for(lambda: t.status in ("done", "failed", "paused", "stopped") and not (t.thread and t.thread.is_alive()), sec)


def thinks(title):
    return [r["kw"] is None for r in mock.of(title)]


A = "Думать первый шаг"
mock.scripts[A] = [("write_file", {"path": "outputs/a.md", "content": "# Итог\nготово\n"}), ("show", {"path": "outputs/a.md"}),
                   ("finish", {"summary": "Итог в outputs/a.md."})]
t = tm.create(A, "Напиши короткий итог в файл")
ok(settle(t) and t.status == "done", f"задача сделана ({t.status} {t.error})")
th = thinks(A)
ok(th[:1] == [True] and not any(th[1:]), f"думает только на первом шаге: {th}")
ok("💡 Обдумываю шаг: первый шаг" in (t.dir / "журнал.md").read_text(encoding="utf-8"), "в журнале — почему думала")

B = "Думать две неудачи"
mock.scripts[B] = [("file_edit", {"path": "нет.md", "old": "a", "new": "b"}), ("file_edit", {"path": "нет2.md", "old": "a", "new": "b"}),
                   ("write_file", {"path": "outputs/b.md", "content": "# Итог\nок\n"}), ("show", {"path": "outputs/b.md"}),
                   ("finish", {"summary": "Итог в outputs/b.md."})]
t = tm.create(B, "Поправь файлы")
ok(settle(t), f"задача остановилась ({t.status})")
th = thinks(B)
ok(th[:4] == [True, False, True, False], f"после двух неудачных шагов подряд — обдумать следующий: {th}")

C = "Думать отказ проверки"
mock.scripts[C] = [("write_file", {"path": "outputs/c.md", "content": "# Итог\nок\n"}), ("show", {"path": "outputs/c.md"}),
                   ("finish", {"summary": "Готово: таблица в outputs/таблица.xlsx и итог в outputs/c.md."}),
                   ("finish", {"summary": "Итог в outputs/c.md (таблицу не делала)."})]
t = tm.create(C, "Сделай итог")
ok(settle(t), f"задача остановилась ({t.status})")
th = thinks(C)
ok(len(th) >= 4 and th[3] is True and not any(th[1:3]), f"проверка не приняла итог — следующий шаг обдуман: {th}")

host.s = LS(False)
D = "Думать выключено"
mock.scripts[D] = [("write_file", {"path": "outputs/d.md", "content": "# Итог\nок\n"}), ("show", {"path": "outputs/d.md"}),
                   ("finish", {"summary": "Итог в outputs/d.md."})]
t = tm.create(D, "Сделай итог")
ok(settle(t), f"задача остановилась ({t.status})")
ok(not any(thinks(D)), f"«Думать над сложными просьбами» выключено — без рассуждений: {thinks(D)}")
host.s = LS()
host.prof["think"] = "off"
E = "Думать никогда"
mock.scripts[E] = list(mock.scripts[D])
t = tm.create(E, "Сделай итог")
ok(settle(t) and not any(thinks(E)), f"у модели «думать никогда» — без рассуждений: {thinks(E)}")

done()
