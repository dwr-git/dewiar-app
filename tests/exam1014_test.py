"""Экзамен 14.10 (0.38.34, облачная Qwen): что провалилось — то здесь.
1. «Запомни: в среду в 15:00 встреча с подрядчиком» (сказано в среду) → в новом разговоре «Что у меня в среду?» —
   модель смотрела только календарь на следующую среду: «пусто». Теперь вопрос о дне недели — тоже вопрос о планах,
   и записанное в памяти на эту дату лежит перед моделью вместе с календарём.
2. Курс доллара: строка «Доллар США» стояла на странице ЦБ дальше 6000 знаков — модель её не увидела и выдумала курс.
   Длинная страница — начало и места со словами вопроса (или find).
3. «Что посмотреть»: страница журнала прочиталась пустой — модель выдумала фильм. Пустая страница — честно «текста нет».
4. Таймер: посчитала 79 дней, а поставила 59 минут и сказала «на 79» — расхождение ловится (quality.number_mismatch).
Компьютер и телефон."""
import os, shutil, subprocess, sys, tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path[:0] = [str(ROOT), str(ROOT / "core")]
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import engine_tools  # noqa: E402
import tools  # noqa: E402
import quality as Q  # noqa: E402

today = date.today()
wd_names = ["понедельник", "вторник", "среду", "четверг", "пятницу", "субботу", "воскресенье"]


class WS:
    def __init__(self, text): self.t = text
    def memory_text(self): return self.t
    def memory_get(self): return self.t          # 0.47: даты ищутся по всей «Обо мне», а не по последним 2500 знакам


class Eng(engine_tools.ToolsMixin):
    def __init__(self, mem): self.workspace = WS(mem)
    def calendar_month(self, y, m): return {"days": {}}


# 1. день недели: сегодняшний и через неделю; из памяти — с датой
mem = f"- Встреча с подрядчиком по кухне в 15:00 (на {today:%d.%m.%Y}, {wd_names[today.weekday()]})\n- Любит чай"
ctx = Eng(mem).agenda_context(f"Что у меня в {wd_names[today.weekday()]}?")
ok("ПЛАНЫ ПОЛЬЗОВАТЕЛЯ" in ctx and "подрядчик" in ctx and "из твоей памяти" in ctx and "Любит чай" not in ctx,
   f"«что у меня в {wd_names[today.weekday()]}?» — встреча из памяти перед моделью: {ctx[-300:]!r}")
nxt = today + timedelta(days=7)
ok(f"{nxt:%d.%m}" in ctx and "ничего не запланировано" in ctx, "и та же день недели через неделю (там пусто)")
other = (today.weekday() + 2) % 7
d2 = today + timedelta(days=2)
ctx2 = Eng(f"- Сдать отчёт (на {d2:%d.%m.%Y})").agenda_context(f"Какие планы на {wd_names[other]}?")
ok(f"{d2:%d.%m}" in ctx2 and "Сдать отчёт" in ctx2 and f"{today:%d.%m}" not in ctx2, f"другой день недели — ближайший: {ctx2[-160:]!r}")
ok(Eng("").agenda_context("Расскажи про среду в истории") == "", "не вопрос о планах — без подсказки")
# 17.10 (суббота): «Какие планы на понедельник?» давало всю неделю — в «понедельник» тоже есть «недел»
ctx3 = Eng("").agenda_context("Какие планы на понедельник?")
mon = today + timedelta(days=(0 - today.weekday()) % 7 or 7) if today.weekday() else today
ok(f"{mon:%d.%m}" in ctx3 and ctx3.count("ничего не запланировано") <= 2, f"«планы на понедельник» — понедельник, а не вся неделя: {ctx3[-120:]!r}")

# 2–3. страницы
page = "Банк России. Официальные курсы. " + " ".join(f"{c} Валюта{i} {i}.{i:04d}" for i, c in enumerate(["AUD", "AZN"] * 400)) \
       + " 840 USD 1 Доллар США 81,2345 " + "EUR 1 Евро 95,1 " * 50
r = tools.page_excerpt(page, "", "Какой сегодня официальный курс доллара к рублю?")
ok("81,2345" in r and len(r) <= tools.PAGE_MAX + 400, f"длинная страница: курс доллара в выдержке ({len(r)} знаков)")
r2 = tools.page_excerpt(page, "Евро", "")
ok("95,1" in r2 and "Евро" in r2, "find — куски по этому слову")
r3 = tools.page_excerpt("x" * 9000, "", "")
ok("read_webpage ещё раз с find" in r3, "ничего не нашлось — подсказка, как искать дальше")
ok(tools.page_excerpt("  \n \n ", "", "") == tools.PAGE_EMPTY and "не придумывай" in tools.PAGE_EMPTY, "пустая страница — «текста нет, не придумывай»")
ok(tools.page_excerpt("Короткая страница с текстом о погоде в Минске: завтра +11, облачно, ветер 2 м/с, влажность 82 процента.", "", "") .startswith("Короткая"),
   "короткая страница — как есть")

# 4. число в ответе ≠ поставленному
calls = [{"name": "set_reminder", "args": {"text": "Таймер", "in_minutes": 59}, "result": "Напоминание «Таймер» поставлено: через 59 мин (id f)."}]
mm = Q.number_mismatch("До Нового года 79 дней. Таймер на 79 минут поставила.", calls)
ok(mm and "79" in mm and "59" in mm, f"«на 79 минут», а поставлено 59 — ловится: {mm!r}")
ok(not Q.number_mismatch("Таймер на 59 минут поставила.", calls), "совпадает — молчим")
ok(not Q.number_mismatch("Поставила таймер на час.", [{"name": "set_reminder", "args": {"in_minutes": 60}, "result": "через 60 мин"}]), "«на час» = 60 — молчим")
ok(not Q.number_mismatch("До Нового года 79 дней. Таймер поставлен.", calls), "минуты в ответе не названы — молчим")
ok(not Q.number_mismatch("Через 10 минут напомню.", [{"name": "weather", "args": {}, "result": "+11"}]), "без set_reminder — молчим")

# телефон: то же
tmp = Path(tempfile.mkdtemp()); www = tmp / "www"
shutil.copytree(ROOT / "android/assets/www", www)
for f in ("entities.js", "rich.js"):
    shutil.copy(ROOT / "ui/assets" / f, www / f)
shutil.copytree(ROOT / "ui/assets/live", www / "live", dirs_exist_ok=True)
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                capture_output=True, text=True, check=True).stdout, encoding="utf-8")
errs = []
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page()
    pg.on("pageerror", lambda x: errs.append(str(x)))
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(700)
    P = pg.evaluate("""(page) => ({ usd: pageExcerpt(page, "", "Какой сегодня официальный курс доллара к рублю?"),
        empty: pageExcerpt("   ", "", ""),
        mm: typeof numberMismatch === "function" ? numberMismatch("Таймер на 79 минут поставила.", [{ name: "set_reminder", args: { in_minutes: 59 }, result: "через 59 мин" }]) : "нет функции",
        same: typeof numberMismatch === "function" ? numberMismatch("Таймер на 59 минут.", [{ name: "set_reminder", args: { in_minutes: 59 }, result: "через 59 мин" }]) : "x" })""", page)
    b.close()
ok("81,2345" in P["usd"], "телефон: длинная страница — курс доллара в выдержке")
ok("не придумывай" in P["empty"], "телефон: пустая страница — честно")
ok(P["mm"] and "59" in P["mm"] and not P["same"], f"телефон: «на 79 минут» при 59 — ловится: {P['mm']!r}")
ok(not errs, "без ошибок JavaScript" + (f": {errs}" if errs else ""))
shutil.rmtree(tmp, ignore_errors=True)
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
