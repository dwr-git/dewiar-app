"""Идеи №360/№361 (20.11): на «собери совет агентов — что лучше, бег или силовые?» модель отправила разработчику две «идеи»
(«Совет из агентов: …»). Идея уходит, только когда о ней говорят («предложи идею», «передай разработчику») или человек
согласился на вопрос Лиры («да», «давай»). Компьютер и телефон одинаково."""
import os, re, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
import tools_notes as TN  # noqa: E402
from tools_base import ToolError  # noqa: E402

bad = 0
def ok(c, m):
    global bad
    bad += 0 if c else 1
    print(("✅ " if c else "❌ ") + m)

yes = ["Предложи идею: тёмная тема для часов", "передай разработчику, что нужен экспорт", "да", "Давай, предложи",
       "Хорошо бы добавить в приложение папки", "добавьте выбор голоса"]
no = ["Собери совет агентов: что лучше — бег или силовые?", "Как совместить бег и силовые?", "что посмотреть вечером"]
ok(all(TN.IDEA_OK_RX.search(t) for t in yes), "просьба об идее и согласие — узнаются: " + ", ".join(t for t in yes if not TN.IDEA_OK_RX.search(t)))
ok(not any(TN.IDEA_OK_RX.search(t) for t in no), "совет, вопрос — не идея: " + ", ".join(t for t in no if TN.IDEA_OK_RX.search(t)))
try:
    TN.t_suggest_idea({"title": "Совет из агентов: бег или силовые"}, {"engine": object(), "turn_text": lambda: no[0]})
    ok(False, "компьютер: совет агентов идеей не уходит")
except ToolError as e:
    ok("ответь на его вопрос сам" in str(e), "компьютер: совет агентов идеей не уходит")
ph = (ROOT / "android/www-src/app/12-tools.js").read_text(encoding="utf-8")
m = re.search(r"const IDEA_OK_RX = (/.+?/i);", ph)
py = TN.IDEA_OK_RX.pattern.replace("\\s", "\\s")
ok(m and "if (turnQ && !IDEA_OK_RX.test(turnQ))" in ph, "телефон: та же проверка перед отправкой")
ok(m and "предлож|разработчик" in m.group(1) and "согласен" in m.group(1), "телефон: те же слова, что на компьютере")
print("ИТОГ:", "всё в порядке" if not bad else f"ошибок {bad}")
sys.exit(1 if bad else 0)
