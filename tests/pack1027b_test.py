"""Пакет 27.10, 11:31. №348: DeepSeek v4.1 (polza.ai) писал вызовы «<DSML calls><DSML invoke …><DSML parameter
name="arguments" string="false">{json}» — без «｜» и одним JSON; Dewiar не узнавал их и читал код вслух («бэкслэш,
бэкслэш…»). №347: «Запустишь заново?» — «Перезапустила», а задачи нет — в «Задачах» пусто."""
import os, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
import llm  # noqa: E402
import quality as Q  # noqa: E402
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


txt = ('Пишу скрипт.\n<DSML calls>\n<DSML invoke name="lab_write">\n<DSML parameter name="arguments" string="false">'
       '{"name": "money_analysis.py", "content": "P = r\\"C:\\\\\\\\Users\\\\\\\\u\\\\\\\\money.json\\""}</DSML parameter>\n</DSML invoke>\n</DSML calls>\n')
for n in (1, 4, 9, 400):
    t = llm.ToolTagStripper(); t.known = {"lab_write"}
    out = "".join(t.feed(txt[i:i + n]) for i in range(0, len(txt), n)) + t.tail()
    c = t.calls()
    ok(out.strip() == "Пишу скрипт." and c and c[0]["name"] == "lab_write" and c[0]["args"].get("name") == "money_analysis.py",
       f"№348: «<DSML calls>» куски по {n} — вызов выполняется, код не звучит: {out!r} {c}")
t = llm.ToolTagStripper()
ok(t.feed("Про формат DSML и <b>теги</b> — просто текст.") + t.tail() == "Про формат DSML и <b>теги</b> — просто текст.", "слово DSML в обычном тексте — не теряется")
old = '<｜DSML｜function_calls><｜DSML｜invoke name="weather"><｜DSML｜parameter name="city" string="true">Москва</｜DSML｜parameter></｜DSML｜invoke></｜DSML｜function_calls>'
ok(llm.dsml_calls(old) == '<tool_call>{"name": "weather", "arguments": {"city": "Москва"}}</tool_call>', "прежний вид DSML (№301) — как раньше")

ok(Q.task_claim("Перезапустила задачу — скоро будет результат.") and Q.task_claim("Хорошо, запустила её заново."),
   "№347: «перезапустила», «запустила заново» без start_task — просим запустить")
ok(not Q.task_claim("Перезапустила.", {"start_task"}), "запуск был — всё правда")
ok(not Q.task_claim("Я запустила задачу 10 минут назад, она работает.") and not Q.task_claim("Перезапустить задачу?")
   and not Q.task_claim("Не перезапустила — жду ваш ответ."), "рассказ о прошлом запуске, вопрос и «не перезапустила» — не трогаем")
src = (ROOT / "core/engine_answer.py").read_text(encoding="utf-8")
ok("task_claim(step_text, called)" in src, "ответ проверяется на «перезапустила» без запуска")
app = (ROOT / "android/assets/www/app.js").read_text(encoding="utf-8")
ok("/^Script error\\.?$/i.test(e.message) && !e.filename" in app, "веб-версия: «Script error. (:0)» чужих скриптов (расширения браузера) — не сбой Dewiar, не шлётся")
print("ИТОГ:", "все проверки пройдены" if not fails else f"не пройдено {len(fails)}")
sys.exit(1 if fails else 0)
