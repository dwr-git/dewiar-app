"""Экзамен владельца 15.11 (0.99.0, DWR Chat Qwen 3.8, 100 из 122) — что провалилось по нашей вине, то здесь.
1. «Расскажи утро»: справка о планах брала «завтра» из наших же пояснений к сводке («ни в планах на завтра») и клала перед
   моделью «16.11 (завтра): ничего не запланировано» — сводка сказала «дел нет», а в 23:58 «позвонить маме». Сводке справка
   о планах не нужна (свои данные «Утра»); в делах по расписанию дни — по словам поручения, не по нашим пояснениям.
2. «Сколько места на диске?», «проанализируй компьютер»: run_command {} — пустой вызов, а человеку «Выполнить?» и «жду
   вашего да». Пустой вызов — подсказка модели (system_status, start_task), без вопроса человеку.
3. «Гостиница в Праге с 1 по 14 января» (ноябрь 2026) — подсказка «январь — 2027» была, а ответ «на январь 2026» —
   проверка ответа: месяц без года с прошедшим годом — переделать.
4. «Прочитай стихотворение Некрасова целиком» — «прочитала» по памяти, наполовину сочинив: стихи — из поиска и страницы.
5. Большая задача: «Не выполнено: проверка не согласилась…» и тут же «**Готово — поездка спланирована**» — заголовок
   «Готово» из рассказа задачи убираем, рассказ подписан как мнение задачи.
6. Сам экзамен: отметки «сделано» прошлых испытаний («Тройка» за первое дело, «7 дел за день», «хлеб куплен»); разговор
   до сценария (перебитый «Выполнить?») стирался «новым разговором»; «напиши статью для сайта» без сайта — честный ответ
   инструмента засчитывается; судье — что на стикере."""
import srctext  # noqa: E402 — текст исходника вместе с частями (tests/srctext.py)
import json, os, re, sys
from datetime import date, datetime, timedelta
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path[:0] = [str(ROOT), str(ROOT / "core")]
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import engine_tools  # noqa: E402
import engine_answer as EA  # noqa: E402
import engine_music as EM  # noqa: E402

today = date.today()


class WS:
    def memory_get(self): return ""


class Eng(engine_tools.ToolsMixin):
    def __init__(self, days): self.workspace, self.days = WS(), days
    def calendar_month(self, y, m): return {"days": self.days}


# 1. сводка и итог дня
cal = {today.isoformat(): [{"type": "reminder", "time": "23:58", "title": "Позвонить маме", "id": "r1"}]}
brief = ("Сегодня …\nДела и напоминания на сегодня: 23:58 Позвонить маме.\n\n[Утро с Лирой] Составь по этим данным короткую "
         "утреннюю сводку" + EM.MusicMixin._routine_note(type("X", (), {"_habits": lambda self, weekly=False: (set(), set())})(), silent=False))
ok("завтра" in brief and Eng(cal).agenda_context(brief) == "", "утренняя сводка — без справки о планах (своё «Утро»), хоть в пояснениях и «завтра»")
job = ("[Дело по расписанию] Поручение пользователя: «Итог дня: что сделано и что осталось». Выполни его сам прямо сейчас."
       + EM.MusicMixin._routine_note(type("X", (), {"_habits": lambda self, weekly=False: (set(), set())})()))
ctx = Eng(cal).agenda_context(job)
ok(f"{today:%d.%m} (сегодня)" in ctx and "Позвонить маме" in ctx, f"итог дня: сегодняшние дела в справке, а не только «завтра»: {ctx[-160:]!r}")
ok(f"{today + timedelta(days=1):%d.%m} (завтра)" in Eng(cal).agenda_context("Что у меня завтра?"), "«что завтра?» человека — по-прежнему завтра")

# 2. пустой run_command
src = srctext.text(ROOT, "core/engine_tools.py")
i = src.index('if name in ("run_command", "server_run") and not str((args or {}).get("command") or "").strip():')
j = src.index("blocked, force, warn_q = self.toolbox.guard(name, args)")
ok(i < j and "system_status" in src[i:j] and "start_task" in src[i:j] and "_confirm" not in src[i:j],
   "пустой run_command — подсказка модели (system_status, start_task) до «Выполнить?», человека не спрашиваем")

# 3. год у месяца без года
nov = datetime(2026, 11, 15, 2, 0)
q = "Найди в Праге самый дешёвый номер в гостинице с ванной на два дня где-то с 1 по 14 января."
ok("2027" in EA.month_year_wrong(q, "Самые дешёвые номера на январь 2026 года — от 25 евро.", nov), "«январь 2026» в ноябре 2026 — переделать про 2027")
ok(EA.month_year_wrong(q, "На январь 2027 года — от 25 евро.", nov) == "" and EA.month_year_wrong("что было в январе 2026?", "В январе 2026 …", nov) == "",
   "верный год или год назван в вопросе — без переспроса")

# 4. стихи — из найденного
poem = "Однажды в студёную зимнюю пору\nЯ из лесу вышел; был сильный мороз.\nГляжу, поднимается медленно в гору\nЛошадка"
ask = "Стихотворение Некрасова «Однажды в студёную зимнюю пору» — прочитай мне его целиком."
ok(EA.poem_unsourced(ask, poem, []) and "web_search" in EA.poem_unsourced(ask, poem, []), "«прочитай стихотворение» без поиска — найди и читай со страницы")
ok(not EA.poem_unsourced(ask, poem, ["web_search", "read_webpage"]) and not EA.poem_unsourced("Напиши четверостишие про осень", poem, []),
   "нашла и прочитала — хорошо; «напиши стих» — не про это")
ea = srctext.text(ROOT, "core/engine_answer.py")
ok("or month_year_wrong(ask0, step_text)" in ea and "poem_unsourced(ask0, step_text, called)" in ea, "обе проверки — в цепочке проверок ответа")

# 5. итог невыполненной задачи
ts = srctext.text(ROOT, "core/tasks.py")
k = ts.index('if t.data.get("unfinished"):                 # №368')
ok("готово" in ts[k:k + 700] and "проверка с " in ts[k:k + 900], "невыполненная задача: «Готово» из её рассказа убрано, рассказ — с оговоркой")

# 6. сам экзамен
ex = srctext.text(ROOT, "core/exam.py")
r = ex.index("async def reset_state(core)")
ok('"done_undo"' in ex[r:r + 4000], "между испытаниями — и отметки «сделано» прочь")
rs = ex.index("async def _run_scenario(")
ok('await core.say("Начнём новый разговор"' in ex[rs:rs + 600] and 'exam_history' in ex[rs:rs + 900]
   and ex[rs:rs + 900].index("Начнём новый разговор") < ex[rs:rs + 900].index("exam_history"),
   "разговор до сценария — после «нового разговора», а не до (стирался)")
ok('exam_history' not in ex[ex.index("async def seed(core, sd)"):ex.index("async def seed(core, sd)") + 600], "в seed разговор больше не ставится")
sc = {s["id"]: s for s in json.loads((ROOT / "data/exam/scenarios.json").read_text(encoding="utf-8"))["scenarios"]}
ok(sc["site_article"]["tool"] == {"site_article": {"tried": True}} and '"tried"' in ex, "«статья для сайта» без сайта: попытка засчитывается")
ok("Позвонить Ольге 17:00" in sc["remind_screenshot_model"]["judge"], "судья знает, что на стикере")
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
