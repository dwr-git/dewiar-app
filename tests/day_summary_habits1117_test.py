"""Владелец 17.11, 21:03 — в четвёртый раз: «Итог дня»: «Сегодня сделано: обед с картой (отмечено), плюс заметки по
АИГЕН…», а «Обед — не забудь взять карту» — напоминание каждый будний день. Прежние исправления говорили модели «привычки
не называй» и чистили приветствие «С возвращением», но в ход итога сами данные (календарь calendar_list, отчёт done_report,
строка «сделано сегодня» в справке, список напоминаний) по-прежнему несли «сделано: Обед…» — модель его пересказывала.
Теперь в ход-итог (дело по расписанию «итог / подведи / сводка», «итог дня» словами) привычек нет в данных, а названная
всё же привычка — переспрос и не звучит вслух. Настоящие engine_music, acts_day, tools_notes, tools_remind, done, quality."""
import os, sys, tempfile, types
from datetime import datetime, timedelta
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


tmp = Path(tempfile.mkdtemp())
os.environ.update(DEWIAR_CONFIG_DIR=str(tmp / "cfg"), DEWIAR_STATE_DIR=str(tmp / "st"), HOME=str(tmp / "home"))
(tmp / "home").mkdir()
sys.path.insert(0, str(ROOT / "core"))
import acts_day  # noqa: E402
import done as D  # noqa: E402
import engine_answer as EA  # noqa: E402
import engine_music as EM  # noqa: E402
import quality as Q  # noqa: E402
from tools_notes import t_calendar_list  # noqa: E402
from tools_remind import t_done_report, t_list_reminders  # noqa: E402

now = datetime.now()
today = now.date()
at_lunch = now.replace(hour=13, minute=0, second=0, microsecond=0)
items = [{"id": "r1", "text": "Обед не забудь взять карту", "kind": "reminder", "at": (at_lunch + timedelta(days=1)).isoformat(),
          "repeat": {"kind": "weekly", "days": [0, 1, 2, 3, 4], "time": "13:00"}},
         {"id": "r2", "text": "Позвонить в банк", "kind": "reminder", "at": (now + timedelta(days=1)).replace(hour=11, minute=0).isoformat()},
         {"id": "j1", "text": "Итог дня: что сделано из дел на сегодня, что осталось — коротко", "kind": "job", "preset": "evening",
          "at": now.replace(hour=21, minute=0).isoformat(), "repeat": {"kind": "daily", "time": "21:00"}}]
dn = D.Done(tmp / "done.json") if hasattr(D, "Done") else None
ok(dn is not None, "журнал «сделано» — настоящий done.Done")
ms = lambda d: int(d.timestamp() * 1000)  # noqa: E731
# «Обед…» отмечали и в прошлые будни, и сегодня в 13:56; сегодня же — одно разовое дело
for k in (3, 2, 1):
    dn.items.append({"id": f"d{k}", "title": "Обед не забудь взять карту", "rid": "r1", "at": ms(datetime.combine(today - timedelta(days=k), at_lunch.time()))})
dn.items.append({"id": "d0", "title": "Обед не забудь взять карту", "rid": "r1", "at": ms(now.replace(hour=13, minute=56))})
dn.items.append({"id": "d9", "title": "Отправить договор Вектору", "rid": "", "at": ms(now.replace(hour=15, minute=10))})

ws = types.SimpleNamespace(root=tmp / "ws", memory_get=lambda: "")
(tmp / "ws" / "Заметки").mkdir(parents=True)
(tmp / "ws" / "Заметки" / "АИГЕН.md").write_text("# АИГЕН\n", encoding="utf-8")
e = types.SimpleNamespace(reminders=types.SimpleNamespace(items=items), done=dn, workspace=ws,
                          money=types.SimpleNamespace(list=lambda a, b: [], summary=lambda a, b: {}),
                          calendars=types.SimpleNamespace(events=lambda a, b: []), tasks=types.SimpleNamespace(list=lambda: []), team=None,
                          s=types.SimpleNamespace(get=lambda *a, **k: None), turn=None)
e._default_currency = e._auto_currency = lambda: "RUB"
e._reminder_log = lambda: [{"id": "r1", "title": "Обед не забудь взять карту", "at": now.replace(hour=13, minute=0).isoformat(timespec="seconds"),
                            "due": now.replace(hour=13, minute=0).isoformat(timespec="seconds"), "kind": "reminder"}]
e.job_label = lambda r: EM.MusicMixin.job_name(r)
for n in ("_habits", "_habit_pred", "_done_no_habits"):
    setattr(e, n, types.MethodType(getattr(EM.MusicMixin, n), e))
e.calendar_month = types.MethodType(acts_day.DayMixin.calendar_month, e)
ctx = {"engine": e, "reminders": e.reminders, "done": dn}

# как было: обычный ход (не итог) — календарь показывает отметку у обеда
plain = t_calendar_list({"from": today.isoformat(), "to": today.isoformat()}, ctx)
ok("Обед не забудь взять карту" in plain, "вне итога календарь показывает всё, как раньше (и привычку)")

# ход-итог: «Итог дня» по расписанию — тот же текст поручения, что даёт программа в 21:00
prompt = EM.MusicMixin._job_prompt(types.SimpleNamespace(_routine_note=types.MethodType(EM.MusicMixin._routine_note, e),
                                                         _habits=e._habits), items[2])
ok(EA.HABIT_TURN_RX.search(prompt.split("»", 1)[0]), "поручение «Итог дня» в 21:00 — ход-итог")
for t in ("Итог дня", "Лира, подведи итоги дня", "что я сегодня сделал?"):
    ok(EA.HABIT_TURN_RX.search(t), f"«{t}» словами — тоже ход-итог")
for t in ("Проверь почту и скажи, если пришло важное", "Напомни завтра в 9 позвонить маме"):
    ok(not EA.HABIT_TURN_RX.search(t), f"«{t}» — не итог")
e.turn = types.SimpleNamespace(no_habits=True, habit=e._habit_pred())
cal = t_calendar_list({"from": today.isoformat(), "to": today.isoformat()}, ctx)
ok("Обед" not in cal and "Отправить договор Вектору" in cal and "АИГЕН" in cal,
   f"итог: в календаре дня нет «Обед…» (ни звонка, ни отметки), разовое дело и заметки — есть: {cal!r}")
ok("Итог дня" not in cal, "и самого дела по расписанию «Итог дня» в данных итога нет")
rep = t_done_report({"days": 1}, ctx)
ok("Обед" not in rep and "Отправить договор Вектору" in rep, f"«Дела: итог» в ход итога — без привычки: {rep.splitlines()[0]}")
lst = t_list_reminders({}, ctx)
ok("Обед" not in lst and "Позвонить в банк" in lst and "Итог дня" not in lst, f"список напоминаний в итоге — без привычек и дел по расписанию: {lst!r}")
line = D.now_line(dn, skip=e._habit_pred())
ok("Обед" not in line and "Отправить договор Вектору" in line and "сделано 1 " in line, f"справка «сделано сегодня» — без привычки: {line.strip()}")
ok("Обед" in D.now_line(dn), "без фильтра строка та же, что раньше (фильтр — явный)")
src = (ROOT / "core/answer_prompt.py").read_text(encoding="utf-8")
ok("now_line(self.done, skip=self._habit_pred()" in src, "справка разговора — всегда без привычек")

# ответ, который пришёл владельцу, — переспрос и не вслух
said = ("Сегодня сделано: обед с картой (отмечено), плюс заметки по АИГЕН, регистрации ЦОД на Девиар ПРО, правкам Лиры и "
        "плану обновлений. Трат за день нет. На завтра разовых дел нет.")
fix = Q.habit_said(said, e.turn.habit)
ok(fix and "Обед не забудь взять карту".lower() in fix.lower(), "«обед с картой (отмечено)» — названа привычка: переделать")
ok(not Q.habit_said("Сегодня сделано: отправили договор Вектору, заметки по АИГЕН. Трат нет. На завтра — звонок в банк в 11.", e.turn.habit),
   "итог без привычки — не трогаем")
ea = (ROOT / "core/engine_answer.py").read_text(encoding="utf-8")
ok('habit_said(step_text, getattr(turn, "habit", None)) if getattr(turn, "no_habits", False)' in ea, "переспрос стоит в ряду проверок хода")
ok("_habit_s(s_, getattr(turn, \"habit\", None))" in ea, "фраза с привычкой в итоге не звучит вслух до переделки")

print("\nИТОГ: " + ("всё прошло" if not fails else f"не прошло {len(fails)}"))
sys.exit(1 if fails else 0)
