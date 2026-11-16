"""Экзамен владельца на 1.0.5 (16.11, 107 из 124): провалы, которые чинятся в программе.
- plan_today: «Что у нас по плану?» — модель отметила «Полить цветы» сделанным и сказала, что дел нет. Вопрос — не отметка.
- disk_free_real_call: «сколько места на диске» — своя модель 89 с, пустой run_command и «жду вашего да». Числа — сразу.
- open_folder_after_shot573: «сделай снимок» → «открой эту папку» → открыла «/». Корень сразу после сохранения — его папка.
- draw_offer_plugin: второй раз за 6 часов — без справки о плагине, модель ушла в расспросы. Напомнить одной фразой.
- task_folders720: «проанализируй компьютер… предложи структуру» — по одной команде вместо задачи. Справка: start_task.
- playlist: песни не тех исполнителей — справка «только те, в которых уверена».
- big_b13_dashboard: «echarts is not defined» — навык html-viz обещал готовые библиотеки в js/, которых нет.
- help_ubuntu_cmd: ответ по разделу руководства — и событие app_help, как при attach."""
import os, sys, time
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path[:0] = [str(ROOT), str(ROOT / "core")]
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import tools as T  # noqa: E402


class Done:
    def __init__(self): self.added = []
    def add(self, lst, src): self.added += lst; return {"items": lst, "fresh": [], "mile": None}
    def public(self): return {}


dn = Done()
try:
    T.t_mark_done({"items": ["Полить цветы"]}, {"done": dn, "reminders": None, "turn_text": lambda: "Что у нас по плану?"})
    ok(False, "plan_today: на вопрос «что по плану?» отметка не ставится")
except T.ToolError as e:
    ok(not dn.added and "спрашивает" in str(e), "plan_today: на вопрос «что по плану?» отметка не ставится, модели сказано почему")
import done as D  # noqa: E402
real_say = D.say
D.say = lambda r, closed: "ok"
try:
    for t in ("я полил цветы", "готово, купил хлеб", "отметь тренировку"):
        dn.added.clear()
        T.t_mark_done({"items": ["x"]}, {"done": dn, "reminders": None, "turn_text": lambda t=t: t})
        ok(dn.added, f"«{t}» — отмечается")
finally:
    D.say = real_say

import engine_answer as EA  # noqa: E402
for t in ("Проверь, сколько свободного места на диске этого компьютера.", "сколько места на диске?", "Лира, сколько осталось места на диске"):
    ok(EA.DISK_ASK_RX.match(t), f"«{t}» — место на диске сразу, без модели")
ok(not EA.DISK_ASK_RX.match("сколько места занимает папка Загрузки"), "«сколько места занимает папка» — не то")
src = (ROOT / "core/engine_answer.py").read_text(encoding="utf-8")
ok("DISK_ASK_RX.match((text or \"\").strip())" in src and "shutil.disk_usage" in src, "быстрый ответ о диске — до модели")

import tempfile  # noqa: E402
shots = Path(tempfile.mkdtemp()) / "Снимки экрана"
shots.mkdir()
T._LAST_SAVED.update(path=str(shots / "x.png"), at=time.time())
seen = []
real_launch = T.launch
T.launch = lambda cmd: seen.append(cmd)
try:
    r = T.t_open_path({"path": "/"}, {})
finally:
    T.launch = real_launch
    T._LAST_SAVED.update(path="", at=0.0)
ok("Снимки экрана" in r, f"open_folder_after_shot573: «/» сразу после снимка — папка снимка ({r})")

ok("включить уже предлагали" in src and "plugin_enable с id" in src, "draw_offer_plugin: повторная просьба — напомнить о плагине одной фразой")
ok(EA.BIG_PC_RX.search("Проанализируй мой компьютер, папки, диски, покажи, что есть, и предложи структуру."), "task_folders720: узнаётся")
ok("сразу запусти \"\n                    \"фоновую задачу start_task" in src or "фоновую задачу start_task с этой целью" in src, "task_folders720: справка — задачей")
ok(EA.SONGS_ASK_RX.search("Подбери мне плейлист под моё сегодняшнее настроение, штук пять песен."), "playlist: узнаётся")
viz = (ROOT / "data/skills/html-viz/SKILL.md").read_text(encoding="utf-8")
ok('src="js/' not in viz and "Готовых копий библиотек в системе НЕТ" in viz, "big_b13: навык не обещает библиотек в js/")
ok("раздел руководства приложен к вопросу" in src, "help_ubuntu_cmd: ответ по руководству — с событием app_help")
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
