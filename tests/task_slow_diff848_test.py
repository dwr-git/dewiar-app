"""Отчёты №848 и №849 (17.11, Windows, задача по коду в большом проекте): «Задачи — что-то жёстко поломалось: по задачам
тыкаю, не меняется ничего, пишет „Занят: task_get — 196 с“»; «невозможно удалить задачу и вообще с ней взаимодействовать».
Каждое открытие карточки (и каждое событие задачи) заново делало git add и diff всей рабочей копии — минуты на большом
проекте, и всё это время студия ждала. Теперь «Изменения» считаются один раз на состояние задачи, в своём потоке:
не уложились в 3 с — карточка приходит сразу («считаю изменения»), готовое приходит событием задачи. Настоящий
core/tasks.py (TaskManager.detail), рабочая копия — подмена с медленным git."""
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from task_mock import ROOT, Host, Mock, done, ok  # noqa: E402
import tasks as TK  # noqa: E402

host = Host(Mock({}))
events = []
host.emit = lambda kind, **k: events.append((kind, k))
tm = TK.TaskManager(host)
t = tm.create("Скрипт", "PowerShell-скрипт", start=False)
t.data.update(project=str(Path(ROOT)), status="failed", steps=24)
calls = []


class SlowWork:
    def __init__(self, delay):
        self.delay, self.work = delay, Path(ROOT)

    def changes(self):
        calls.append("changes"); time.sleep(self.delay); return [("modified", "скрипт.ps1")]

    def diff(self):
        calls.append("diff"); return "--- a/скрипт.ps1\n+++ b/скрипт.ps1\n+Write-Host 1\n"


slow = SlowWork(5)
t.code = lambda: slow
t0 = time.time(); d = tm.detail(t.id); dt = time.time() - t0
ok(dt < 4.5 and d.get("diff_pending") and d["changes"] == [] and d.get("plan") is not None,
   f"большой проект: карточка задачи пришла за {dt:.1f} с, «Изменения» досчитываются в фоне")
t0 = time.time(); d2 = tm.detail(t.id); dt2 = time.time() - t0
ok(calls.count("changes") == 1, f"повторное открытие не запускает git снова: {calls}")
deadline = time.time() + 8
while time.time() < deadline and not any(k == "task" for k, _ in events):
    time.sleep(0.1)
ok(any(k == "task" and e["task"]["id"] == t.id for k, e in events), "досчитались — событие задачи: студия перерисует карточку")
t0 = time.time(); d3 = tm.detail(t.id)
ok(time.time() - t0 < 0.5 and d3["changes"] == [("modified", "скрипт.ps1")] and "Write-Host" in d3["diff"] and not d3.get("diff_pending"),
   "и дальше карточка открывается сразу, с изменениями")
ok(calls.count("changes") == 1, "пока задача не сделала новый шаг — тот же расчёт")
t.data["steps"] = 25
slow.delay = 0.1
d4 = tm.detail(t.id)
ok(calls.count("changes") == 2 and not d4.get("diff_pending") and d4["changes"], "новый шаг задачи — пересчёт; быстрый проект — сразу в карточке, как раньше")
js = (ROOT / "ui/studio/tasks.js").read_text(encoding="utf-8")
ok("t.diff_pending" in js and "Считаю изменения" in js, "студия: «Считаю изменения… карточка обновится сама»")
done()
