"""«Ум Лиры», шаг 0 (владелец 20.11: «максимально важное»): раздел экзамена «Понимание ситуации» — замер до любых перемен.
Разговоры в несколько ходов: «а второй вариант?», возврат к теме после отступления, поправка «нет, я имел в виду…»,
деталь из начала разговора, «ей» — о ком речь, сказанное о себе раньше, неясная просьба (спросить, а не делать), цель
разговора («что ещё осталось?»). Сценарии — data/exam/scenarios.json, оценка — проверки ответа и судья."""
import json, os, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
from exam import check_answer  # noqa: E402

bad = 0
def ok(c, m):
    global bad
    bad += 0 if c else 1
    print(("✅ " if c else "❌ ") + m)

sc = [x for x in json.loads((ROOT / "data/exam/scenarios.json").read_text(encoding="utf-8"))["scenarios"]
      if x.get("group") == "Понимание ситуации"]
ok(len(sc) >= 8, f"сценариев в разделе: {len(sc)}")
ok(all(len(x["steps"]) >= 2 and x.get("judge") and "последний" in x["judge"] for x in sc), "в каждом — несколько ходов и судья о последнем ответе")
ok(all(not x.get("long") and not x.get("big") for x in sc), "идут в обычном экзамене (не долгие)")
by = {x["id"]: x for x in sc}
need = {"sit_second_option", "sit_come_back", "sit_correction", "sit_early_detail", "sit_who_is_she", "sit_preference", "sit_unclear_ask", "sit_goal"}
ok(need <= set(by), "все восемь видов: второй вариант, возврат, поправка, деталь, «ей», о себе, уточнить, цель")


def passes(i, ans):
    return all(c["ok"] for c in check_answer(by[i].get("expect"), ans))


ok(passes("sit_correction", "Яблоки 360 и груши 540 — вместе 900 рублей.") and not passes("sit_correction", "Вместе 720 рублей."),
   "поправка: 900 — да, 720 — нет")
ok(passes("sit_second_option", "Суп — около 40 минут.") and not passes("sit_second_option", "Паста варится 10 минут."), "второй вариант — суп")
ok(passes("sit_preference", "Нут с овощами и сыром фета — запеките 20 минут.") and not passes("sit_preference", "Курица с рисом."),
   "ужин без мяса: курица — провал")
u = by["sit_unclear_ask"]["steps"][-1]
ok(u.get("ask") and "close_send" in u.get("no_tool", []), "неясная просьба: уточняющий вопрос и ничего не отправлено")

print("ИТОГ:", "всё в порядке" if not bad else f"ошибок {bad}")
sys.exit(1 if bad else 0)
