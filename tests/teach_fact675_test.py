"""№675, №677, №678 (13.11, ПК 0.92.1, своя модель gemma4:12b): человек учит — «у меня музыка в MG:\\Музыка», «C.C. Catch —
вот как она написана», «у тебя есть доступ к плееру AIMP, запомни навсегда», «даю тебе разрешение и доступ к системе» —
модель дважды отвечала «запомнил / буду искать там» без remember, проверка честности отвечала «до дела так и не дошло».
Теперь: человек сообщил факт — после второй неудачи программа сама кладёт его в память (quality.self_fact), и «запомнил»
становится правдой; напоминания, траты и вопросы — по-прежнему через свои проверки. Сценарий экзамена teach_fact675."""
import json, os, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
import quality as Q  # noqa: E402
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


f = Q.self_fact("нет я хочу чтобы ты знал у меня есть музыка МG:\\Музыка там много папок", "Запомнил.")
ok("МG:\\Музыка" in f, f"«хочу, чтобы ты знал: у меня есть музыка в …» — факт: {f!r}")
f = Q.self_fact("Слушай, у тебя есть доступ к плееру Aimp. Это факт. Запомни это навсегда. Запускай всегда в нём.", "Записал.")
ok("плееру Aimp" in f and "Запомни" not in f and "Это факт" not in f, f"«запомни это навсегда», «это факт» — убраны из факта: {f!r}")
f = Q.self_fact("я даю тебе разрешение зайти посмотреть и даю доступ к моей системе.", "Хорошо, захожу.")
ok("разрешение" in f, f"«даю разрешение и доступ» — факт: {f!r}")
ok(Q.self_fact("C.C. Catch вот как она написана", "Запомнил.") == "C.C. Catch вот как она написана", "«вот как она написана» — факт")
ok(not Q.self_fact("Запомни: напомни завтра купить хлеб", "Записала."), "напоминание — не факт (своя проверка)")
ok(not Q.self_fact("Запомни, я потратил 500 рублей на такси", "Записала."), "трата — не факт (своя проверка)")
ok(not Q.self_fact("Что у меня в среду?", "Записала."), "вопрос — не факт")
ok(not Q.self_fact("Открой эту папку", "Открыла."), "просьба сделать — не факт")
src = (ROOT / "core/engine_answer.py").read_text(encoding="utf-8")
ok("fact = self_fact(text, turn.full)" in src and "self.workspace.remember(fact)" in src, "ядро: после второй неудачи — сама в память")
ok("elif not saved_fact:" in src and "PROMISE_GIVEUP if len(turn.full) < 300" in src, "не факт — честное «пока ничего не сделано», как раньше")
sc = {x["id"]: x for x in json.loads((ROOT / "data/exam/scenarios.json").read_text(encoding="utf-8"))["scenarios"]}
ok("teach_fact675" in sc and any(s.get("new") for s in sc["teach_fact675"]["steps"]), "сценарий экзамена: научил → новый разговор → помнит")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
