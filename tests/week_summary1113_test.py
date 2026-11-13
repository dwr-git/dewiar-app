"""13.11 (владелец, снимок «Итоги недели»): «рассказала про постоянные еженедельные события, которые всегда прописаны …
долго думала и сказала, что ошиблась». Ответ был: «Извини, я ошиблась — 17:50 … подтянула из прошлой недели. Исправляю,
строго по справке: в пятницу 20-го — виклик в 15:25, итоги недели в 16:00, бэкап файлов и органайзер в 16:30, выключение
компьютера в 16:40…». Теперь:
- в итогах недели всё, что повторяется каждую неделю (и сами дела по расписанию), — не события; в итоге дня привычка —
  и то, что три-четыре дня в неделю («по будням, кроме пятницы, в 17:50»);
- справка о планах к итогу по расписанию кладёт постоянное отдельной строкой «не называй», а проверка «дел нет» её не
  считает (иначе заставляла перечислить постоянное);
- «на следующую неделю» — с понедельника по воскресенье;
- при переспросе после проверки модель не извиняется: человек прошлого ответа не видел."""
import os, sys, types
from datetime import date, datetime, timedelta
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import engine_music as EM  # noqa: E402
import engine_tools as ET  # noqa: E402
import quality as Q  # noqa: E402

items = [{"id": "v", "text": "Виклик с командой", "kind": "reminder", "repeat": {"kind": "weekly", "days": [4], "time": "15:25"}},
         {"id": "b", "text": "Бэкап файлов и органайзер", "kind": "reminder", "repeat": {"kind": "weekly", "days": [4], "time": "16:30"}},
         {"id": "off", "text": "Выключить компьютер", "kind": "reminder", "repeat": {"kind": "weekly", "days": [0, 1, 2, 3], "time": "17:50"}},
         {"id": "w", "text": "Итоги недели: что я сделал за неделю…", "kind": "job", "preset": "week", "repeat": {"kind": "weekly", "days": [4], "time": "16:00"}},
         {"id": "gui", "text": "Удалить графическую оболочку с сервера Лиры", "kind": "reminder", "at": "2026-11-22T20:05"}]
e = types.SimpleNamespace(reminders=types.SimpleNamespace(items=items))
for n in ("_habits", "_routine_note", "_week_job"):
    setattr(e, n, types.MethodType(getattr(EM.MusicMixin, n), e) if n != "_week_job" else EM.MusicMixin._week_job)
e._brief_context = lambda: ""
WEEK = {"preset": "week", "text": "Итоги недели: что я сделал за неделю, траты за неделю по категориям и что запланировано на следующую неделю"}
p = EM.MusicMixin._job_prompt(e, WEEK)
note = p.split("Повторяющиеся")[1] if "Повторяющиеся" in p else ""
ok(all(f"«{t}" in note for t in ("Виклик с командой", "Бэкап файлов", "Выключить компьютер", "Итоги недели")) and "Удалить графическую" not in note,
   "итоги недели: еженедельное и дела по расписанию — постоянное, разовое — нет")
ok("в планах на следующую неделю" in note and "Если разовых дел впереди нет" in note, "в планах на неделю постоянное не называть")
DAY = {"preset": "evening", "text": "Итог дня: что сделано из дел на сегодня, что осталось и что запланировано на завтра"}
pd = EM.MusicMixin._job_prompt(e, DAY)
nd = pd.split("Повторяющиеся")[1]
ok("«Выключить компьютер»" in nd and "Виклик" not in nd, "итог дня: «по будням, кроме пятницы» — привычка; раз в неделю — дело, как раньше")

# справка о планах к итогу недели (пятница 13.11 → неделя 16–22.11)
today = date.today()
mon = today + timedelta(days=7 - today.weekday())
fri, sun = mon + timedelta(days=4), mon + timedelta(days=6)


def month(y, m):
    days = {}
    for d in (mon + timedelta(days=i) for i in range(7)):
        if (d.year, d.month) != (y, m):
            continue
        L = []
        if d.weekday() < 4:
            L.append({"type": "reminder", "id": "off", "time": "17:50", "title": "Выключить компьютер", "kind": "reminder", "repeat": True})
        if d == fri:
            L += [{"type": "reminder", "id": "v", "time": "15:25", "title": "Виклик с командой", "kind": "reminder", "repeat": True},
                  {"type": "reminder", "id": "w", "time": "16:00", "title": "Итоги недели", "kind": "job", "repeat": True},
                  {"type": "reminder", "id": "b", "time": "16:30", "title": "Бэкап файлов и органайзер", "kind": "reminder", "repeat": True}]
        if d == sun:
            L.append({"type": "reminder", "id": "gui", "time": "20:05", "title": "Удалить графическую оболочку", "kind": "reminder"})
        days[d.isoformat()] = L
    return {"days": days}


t = types.SimpleNamespace(AGENDA_Q=ET.ToolsMixin.AGENDA_Q, WEEKDAY_Q=ET.ToolsMixin.WEEKDAY_Q, _habits=e._habits,
                          workspace=types.SimpleNamespace(memory_get=lambda: ""), calendar_month=month)
ag = ET.ToolsMixin.agenda_context(t, f"[Дело по расписанию] Поручение пользователя: «{WEEK['text']}». Выполни его сам")
main, _, rout = ag.partition(ET.ROUTINE_HEAD)
ok("Удалить графическую оболочку" in main and "20:05" in main and not any(w in main for w in ("Виклик", "Бэкап", "Выключить", "Итоги недели")),
   f"справка итога недели: в планах только разовое: {main[-300:]!r}")
ok(all(w in rout for w in ("Виклик", "Бэкап", "Выключить", "16:00")), "постоянное — отдельной строкой «не называй» (время в справке есть)")
ok(fri.strftime("%d.%m") in ag and sun.strftime("%d.%m") in ag and today.strftime("%d.%m (сегодня)") not in ag,
   "«на следующую неделю» — понедельник–воскресенье")
plain = ET.ToolsMixin.agenda_context(t, "что запланировано на следующую неделю?")
ok(ET.ROUTINE_HEAD not in plain and "Виклик" in plain, "обычный вопрос «что на следующей неделе» — всё, как раньше")

# проверки: «разовых дел нет, кроме …» и время постоянного — не повод переспрашивать
ans = "За неделю ничего особенного. На следующей неделе одно разовое дело: в воскресенье в 20:05 — удалить графическую оболочку."
ag2 = "\n".join(l for l in ag.splitlines() if "20:05" not in l)
ok(Q.agenda_invented(ans, ag) == "" and Q.agenda_missed("итоги недели", "На следующую неделю ничего не запланировано.", ag2) == "",
   "только постоянное — «ничего не запланировано» верно, перечислять его не заставляем")
ok(Q.agenda_missed("итоги недели", "На следующую неделю ничего не запланировано.", ag) != "", "а разовое дело забыть нельзя")
ok(Q.agenda_invented("в пятницу в 15:25 виклик", ag) == "", "время постоянного не считается выдуманным")

src = (ROOT / "core/engine_answer.py").read_text(encoding="utf-8")
ok("не извиняйся и не говори об ошибке" in src, "переспрос после проверки — без «Извини, я ошиблась»")

print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
