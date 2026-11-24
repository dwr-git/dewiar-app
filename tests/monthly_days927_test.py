"""№927 (20.11): «каждый месяц с 15 по 19 число напоминать об оплате за квартиру, пока не будет выполнено; не каждый час,
а раз в день» — ставилось «каждый час с 15:00 до 19:00», а после «Готово» продолжало звенеть. Теперь: дни месяца — повтор
«с 15 по 19 число», раз в день; «Сделано» (кнопкой, голосом, в Telegram) — до следующего месяца."""
import os, sys, tempfile
from datetime import datetime
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
from when import after_done, describe_repeat, next_time, parse  # noqa: E402

bad = 0
def ok(c, m):
    global bad
    bad += 0 if c else 1
    print(("✅ " if c else "❌ ") + m)

now = datetime(2026, 11, 20, 18, 0)
r = parse("напомни каждый месяц с 15 по 19 число месяца об оплате за квартиру пока не будет выполнено. Не каждый час, а раз в день", now)
ok(r and r["repeat"] == {"kind": "monthly", "day": 15, "to_day": 19, "time": "09:00"}, f"дни месяца, а не часы: {r and r['repeat']}")
ok(r and r["at"] == datetime(2026, 12, 15, 9, 0), f"первое — 15 декабря в 9:00: {r and r['at']}")
ok(r and r["text"] == "Об оплате за квартиру пока не будет выполнено", f"текст без «не каждый час, а раз в день»: {r and r['text']!r}")
ok(describe_repeat(r["repeat"]) == "каждый месяц с 15 по 19 число в 9:00", describe_repeat(r["repeat"]))
r2 = parse("напоминай с 15 по 19 число каждого месяца в 10 оплатить квартиру", now)
ok(r2 and r2["repeat"].get("to_day") == 19 and r2["at"] == datetime(2026, 12, 15, 10, 0), "«с 15 по 19 число каждого месяца в 10»")
r3 = parse("напоминай по будням с 9 до 18 проверить почту", now)
ok(r3 and r3["repeat"]["kind"] == "interval" and r3["repeat"]["from"] == "09:00", "окно часов «по будням с 9 до 18» — как раньше")
r4 = parse("напомни каждый месяц 15 числа в 10 оплатить квартиру", now)
ok(r4 and r4["repeat"] == {"kind": "monthly", "day": 15, "time": "10:00"}, "«каждый месяц 15 числа» — как раньше")

rep = r["repeat"]
ok(next_time(rep, datetime(2026, 12, 15, 9, 0)) == datetime(2026, 12, 16, 9, 0), "каждый день окна: 15 → 16")
ok(next_time(rep, datetime(2026, 12, 19, 9, 0)) == datetime(2027, 1, 15, 9, 0), "после 19-го — 15 января")
ok(next_time({"kind": "monthly", "day": 28, "to_day": 31, "time": "09:00"}, datetime(2027, 2, 28, 9, 0)) == datetime(2027, 3, 28, 9, 0),
   "в феврале — до последнего дня")
ok(after_done(rep, datetime(2026, 12, 16, 9, 0), datetime(2026, 12, 16, 8, 0)) == datetime(2027, 1, 15, 9, 0),
   "«Сделано» 16-го — до 15 января")
ok(after_done(rep, datetime(2027, 1, 15, 9, 0), datetime(2026, 12, 16, 10, 0)) is None, "следующее уже в новом месяце — не трогаем")
ok(after_done({"kind": "interval", "minutes": 60, "from": "15:00", "to": "19:00"}, datetime(2026, 11, 20, 17, 0), datetime(2026, 11, 20, 16, 30))
   == datetime(2026, 11, 21, 15, 0), "окно часов: «Сделано» — до завтрашнего окна")
ok(after_done({"kind": "daily", "time": "19:00"}, datetime(2026, 11, 20, 19, 0), datetime(2026, 11, 20, 18, 0)) == datetime(2026, 11, 21, 19, 0),
   "каждый день: сделал до звонка — сегодня не звенит")
ok(after_done({"kind": "daily", "time": "19:00"}, datetime(2026, 11, 21, 19, 0), datetime(2026, 11, 20, 20, 0)) is None, "звонок уже завтра — не трогаем")
ok(after_done({"kind": "interval", "minutes": 60}, datetime(2026, 11, 20, 19, 0), now) is None, "простой интервал — как раньше")

# хранилище: «Сделано» двигает напоминание, во всех путях (кнопка, голос, инструмент)
os.environ["DEWIAR_STATE_DIR"] = tempfile.mkdtemp()
import tools_remind as TR  # noqa: E402
st = TR.Reminders(lambda x: None) if hasattr(TR, "Reminders") else None
if st is not None:
    x = st.add(datetime(2026, 12, 15, 9, 0), "Оплатить квартиру", rep)
    st.done_round(x["id"], now=datetime(2026, 12, 15, 10, 0))
    ok(st.get(x["id"])["at"].startswith("2027-01-15T09:00"), f"хранилище: следующее — 15 января ({st.get(x['id'])['at']})")
src = "".join((ROOT / f).read_text(encoding="utf-8") for f in ("core/acts_alarm.py", "core/acts_quick.py", "core/tools_remind.py"))
ok(src.count("done_round(") >= 4, "«Сделано» кнопкой в студии, словами и инструментом — следующий круг")

print("ИТОГ:", "всё в порядке" if not bad else f"ошибок {bad}")
sys.exit(1 if bad else 0)
