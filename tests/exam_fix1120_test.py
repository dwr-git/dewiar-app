"""Экзамен 1.0.47 (владелец, 20.11): что в нём было ошибкой программы, а не модели.
1) №857 снова: «Каждое утро я встаю рано… присылай каждый день в 5:30» — дело встало на 17:30 (час 1–6 без «утра» в
   повторе считали дневным). Утро, сказанное словами (утро, по утрам, рано, встаю), — утро.
2) «Итог дня» в пятый раз назвал «карту»: «обед, карту взяла» модель отметила двумя делами — «Обед» и «Карту взяла»;
   второе не узнавалось как часть привычки «Обед — не забудь взять карту».
3) «Отметь ещё: отправила договор…» — дело записалось как «Еще: отправила договор…»."""
import os, sys, tempfile, types
from datetime import datetime
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
import jobs  # noqa: E402
import when  # noqa: E402

c = jobs.parse("Каждое утро я встаю рано. Собирай прогноз погоды на день и присылай мне каждый день в 5:30, а не просто напоминай.")
ok(c and c["repeat"].get("time") == "05:30", f"«каждое утро… в 5:30» — 05:30 ({c and c['repeat']})")
n = datetime(2026, 11, 20, 8, 49)
r = when.parse("напомни каждый день в 3 пить таблетки", now=n)
ok(r["repeat"]["time"] == "15:00" and r.get("guessed"), "«каждый день в 3» без утра — по-прежнему днём, с подсказкой модели")
ok(when.parse("напомни завтра рано в 6 встать", now=n)["at"].hour == 6, "«завтра рано в 6» — утро")

dn = D.Done(tmp / "done.json")
r = dn.add(["Еще: отправила договор Вектору", "и ещё позвонила в банк", "Ещё раз проверить отчёт"])
ok([x["title"] for x in r["items"]] == ["Отправила договор Вектору", "Позвонила в банк", "Ещё раз проверить отчёт"],
   f"«ещё:» из просьбы не входит в дело: {[x['title'] for x in r['items']]}")

items = [{"id": "r1", "text": "обед не забудь взять карту", "kind": "reminder", "at": n.isoformat(),
          "repeat": {"kind": "weekly", "days": [0, 1, 2, 3, 4], "time": "13:00"}},
         {"id": "r2", "text": "проверить договор", "kind": "reminder", "at": n.isoformat(), "repeat": {"kind": "daily", "time": "10:00"}}]
e = types.SimpleNamespace(reminders=types.SimpleNamespace(items=items), done=types.SimpleNamespace(items=[]))
e._habits = types.MethodType(EM.MusicMixin._habits, e)
habit = EM.MusicMixin._habit_pred(e)
ok(habit("Обед") and habit("Карту взяла") and habit("Взяла карту"), "«Обед» и «Карту взяла» — куски привычки «обед, не забудь взять карту»")
ok(not habit("Отправила договор Вектору") and not habit("Купила новую карту памяти для фотоаппарата"),
   "разовые дела — не привычки (одно общее слово из трёх — мало)")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
