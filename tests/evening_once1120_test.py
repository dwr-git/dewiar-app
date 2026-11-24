"""Владелец 20.11, 21:32: включил компьютер — «С возвращением» подвела итог дня («закрыл три дела… серия пять дней, всего
65… ужин, видимо, позади — хорошо, что не забыл карту»), а через минуту опоздавший «Итог дня» в 21:00 повторил его. Плюс
«проверила» вместо «проверил» и «А — пора выключать комп и бежать на автобус» (по двум дням недели) в итоге.
Теперь: итог дня — один (дело-итог впереди или опоздало — приветствие его не подводит; подвели при возвращении — дело
молчит); приветствие — без инструментов (done_report отдавал привычки, серию и «всего»); привычка — любое повторяющееся
два и больше дней в неделю; в ходе-итоге — только сделанное, серия — только круглая; дела — пользователя, не Лиры."""
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
import done as D  # noqa: E402
import engine_music as EM  # noqa: E402
import presence  # noqa: E402

now = datetime.now().replace(hour=21, minute=32, second=0, microsecond=0)
today = now.date()
job = {"id": "j1", "text": "Итог дня: что сделано из дел на сегодня, что осталось — коротко", "kind": "job", "preset": "evening",
       "at": now.replace(hour=21, minute=0).isoformat(), "repeat": {"kind": "daily", "time": "21:00"}}
bus = {"id": "r2", "text": "А - пора выключать комп и бежать на автобус", "kind": "reminder",
       "at": (now + timedelta(days=5)).replace(hour=16, minute=38).isoformat(), "repeat": {"kind": "weekly", "days": [2, 4], "time": "16:38"}}
month = {"id": "r3", "text": "Оплатить квартиру", "kind": "reminder", "at": (now + timedelta(days=20)).isoformat(),
         "repeat": {"kind": "monthly", "day": 15, "time": "09:00"}}
items = [job, bus, month]
e = types.SimpleNamespace(reminders=types.SimpleNamespace(items=items, update=lambda rid, d: next(x for x in items if x["id"] == rid).update(d)))
for n in ("_eve_job_pending", "_eve_done_today", "_habits"):
    setattr(e, n, types.MethodType(getattr(EM.MusicMixin, n), e))

# 1. итог по расписанию опоздал (компьютер включили в 21:32) — приветствие итог не подводит
ok(e._eve_job_pending(now), "«Итог дня» в 21:00 опоздал и выполнится — он впереди")
ok(e._eve_job_pending(now.replace(hour=19)), "в 19:00 «Итог дня» через 2 часа — тоже впереди")
ok(not e._eve_job_pending(now.replace(hour=12)), "днём до итога далеко — не мешает")
dstat = {"today": 2, "streak": 5, "items": [{"title": "Посмотреть ответы лёгких моделей"}, {"title": "Позвонить Игорю"}]}
p = presence.plan(4 * 3600, now - timedelta(hours=4), [], [], None, now=now, dstat=dstat, eve_said=today, day_brief=False)
ok(p is None or p["kind"] not in ("eve", "day"), f"при возвращении — ни итога, ни сводки дня: {p and p['kind']}")
p2 = presence.plan(4 * 3600, now - timedelta(hours=4), [], [], None, now=now, dstat=dstat)
ok(p2 and p2["kind"] == "eve" and "Серия" not in p2["facts"][0], "без дела-итога — итог при возвращении, серия 5 не звучит")
ok("Серия: 7" in presence.plan(4 * 3600, now - timedelta(hours=4), [], [], None, now=now, dstat=dict(dstat, streak=7))["facts"][0],
   "серия 7 — круглая, звучит")
pr = presence.prompt(p2)
ok("не «проверила»" in pr and "без догадок" in pr and "без инструментов" in pr, "приветствие: дела — его, только факты")

# 2. итог подвели при возвращении — дело «Итог дня» второй раз не подводит
e._eve_said = datetime.now().date()
ok(e._eve_done_today(job), "итог уже был — дело молчит")
ok(not e._eve_done_today({"text": "Итоги недели", "kind": "job", "preset": "week"}), "итоги недели — не тот итог")
e._eve_said = None
ok(not e._eve_done_today(job), "итога не было — дело работает")
src = (ROOT / "core/engine_music.py").read_text(encoding="utf-8")
ok("if self._eve_done_today(item):" in src and "self._eve_said = datetime.now().date()       # итог сегодня подведён" in src,
   "_run_job: проверяет и сам отмечает итог")
ok("eve_said=datetime.now().date() if eve_job else" in src and "day_brief=not eve_job" in src, "_welcome_back: итог впереди — не подводит")

# 3. привычки: по двум дням недели — тоже рутина; раз в неделю и раз в месяц — событие
ids, texts = e._habits()
ok("r2" in ids and "r3" not in ids and "j1" not in ids, f"привычки: автобус по 2 дням — да, квартира раз в месяц — нет ({sorted(ids)})")

# 4. отчёт в ходе-итоге: только сделанное
dn = D.Done(tmp / "done.json")
ms = lambda d: int(d.timestamp() * 1000)  # noqa: E731
dn.items.append({"id": "d1", "title": "Посмотреть ответы лёгких моделей", "rid": "", "at": ms(datetime.now())})
full = D.report(dn, 1)
brief = D.report(dn, 1, skip=lambda t, r: False)
ok("Всего:" in full and "Всего:" not in brief and "Достижения" not in brief and "не «проверила»" in brief,
   "done_report в ходе-итоге: без «всего», достижений; дела — пользователя")
ok("specs = []" in (ROOT / "core/engine_answer.py").read_text(encoding="utf-8").split('if getattr(turn, "greet", False):', 1)[1][:400],
   "«С возвращением» — без инструментов")
ok("не «проверила»" in EM.MusicMixin._routine_note.__code__.co_consts.__repr__() or "не «проверила»" in src, "итог по расписанию: дела — пользователя")

print("ИТОГ:", "всё в порядке" if not fails else f"ошибок {len(fails)}")
sys.exit(1 if fails else 0)
