"""28.10 (владелец): каждый день напоминания «не забыть карту» (обед) и «выключить комп» — а «Итог дня» в 21:00 каждый
раз говорил «сделано 1 дело — „Обед, не забудь карту“… Завтра: 12:28 обед, 17:50 выключить компьютер, 21:00 итог дня».
Теперь в итогах и сводках по расписанию ежедневные привычки и сами дела по расписанию не упоминаются, а если кроме них
сказать нечего — итог молчит (ТИШИНА). Обычные дела по расписанию (проверить почту) — как раньше."""
import os, sys, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import engine_music as EM  # noqa: E402
items = [{"id": "r1", "text": "Обед — не забудь взять карту", "kind": "reminder", "repeat": {"kind": "daily", "time": "12:28"}},
         {"id": "r2", "text": "Выключить компьютер", "kind": "reminder", "repeat": {"kind": "weekly", "days": [0, 1, 2, 3, 4], "time": "17:50"}},
         {"text": "Планёрка", "kind": "reminder", "repeat": {"kind": "weekly", "days": [0], "time": "10:00"}},
         {"text": "Позвонить в банк", "kind": "reminder", "at": "2026-10-29T11:00"},
         {"text": "Итог дня: что сделано из дел на сегодня, что осталось…", "kind": "job", "repeat": {"kind": "daily", "time": "21:00"}}]
e = types.SimpleNamespace(reminders=types.SimpleNamespace(items=items))
e._habits = types.MethodType(EM.MusicMixin._habits, e)
e._routine_note = types.MethodType(EM.MusicMixin._routine_note, e)
e._brief_context = lambda: ""
p = EM.MusicMixin._job_prompt(e, {"text": "Итог дня: что сделано из дел на сегодня, что осталось, сколько потрачено за день и что запланировано на завтра — коротко"})
ok("«Обед — не забудь взять карту»" in p and "«Выключить компьютер»" in p and "не упоминай" in p and "ТИШИНА" in p.split("Повторяющиеся")[1],
   "«Итог дня»: привычки (каждый день, по будням) — названы и не упоминаются; кроме них нечего — тишина")
ok("Планёрка" not in p and "Позвонить в банк" not in p, "раз в неделю и разовые — дела, их итог упоминает")
p2 = EM.MusicMixin._job_prompt(e, {"text": "Проверь почту и скажи, если пришло важное"})
ok("Повторяющиеся" not in p2 and "ТИШИНА" in p2, "обычное дело по расписанию — как раньше")
ok(EM.MusicMixin.job_nothing("ТИШИНА"), "«ТИШИНА» — молчим")
# 29.10 (владелец, Ubuntu): «С возвращением» вечером — «закрыл два дела: не забыл карту и выключил компьютер» —
# итог при возвращении брал отметки «сделано» у ежедневных напоминаний
import presence  # noqa: E402
from datetime import datetime  # noqa: E402
st = {"today": 3, "streak": 5, "items": [{"title": "Обед — не забудь взять карту", "rid": "r1"}, {"title": "Выключить компьютер", "rid": ""},
                                         {"title": "Позвонить в банк", "rid": "r9"}]}
f = EM.MusicMixin._done_no_habits(e, st)
ok(f["today"] == 1 and [x["title"] for x in f["items"]] == ["Позвонить в банк"], f"сделанное без привычек (по id и по тексту): {f}")
only = EM.MusicMixin._done_no_habits(e, dict(st, today=2, items=st["items"][:2]))
NOW = datetime(2026, 10, 29, 22, 10)
pl0 = presence.plan(4 * 3600, datetime(2026, 10, 29, 18, 0), [], [], datetime(2026, 10, 29, 9, 0), now=NOW, dstat=dict(st, today=2, items=st["items"][:2]), eve_said=None)
pl = presence.plan(4 * 3600, datetime(2026, 10, 29, 18, 0), [], [], datetime(2026, 10, 29, 9, 0), now=NOW, dstat=only, eve_said=None)
ok(pl0 and pl0["kind"] == "eve" and (not pl or pl.get("kind") != "eve"), f"кроме привычек ничего — вечернего «закрыл два дела» нет (было: {pl0 and pl0['kind']}): {pl}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
