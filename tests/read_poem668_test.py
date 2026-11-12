"""№668 (12.11): «Стихотворение Некрасова. Лошадка, везущая хворосту воз» — включались «сочини стихи» (POEM_NOTE про рифмы)
и температура 0.95; модель сочиняла и пересказывала, прочитала пять строк, и человек решил, что обрывается голос. Теперь
просьба прочитать готовое произведение (llm.reading) — без творческой температуры, с подсказкой READ_NOTE: точный текст
целиком, не уверена — найти и открыть страницу; выдача поиска напоминает, что это отрывки. Телефон — так же (app.js)."""
import json, os, re, subprocess, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import llm  # noqa: E402
import tools  # noqa: E402

READ = ["Стихотворение Некрасова. Лошадка, везущая хворосту воз.", "прочитай стихотворение Пушкина «Зимнее утро»",
        "Муся, найди в интернете это стихотворение, выучи наизусть и расскажи", "прочитай басню Крылова «Ворона и лисица»",
        "расскажи стих Есенина про берёзу", "продекламируй Лермонтова стих «Парус»"]
WRITE = ["напиши стих о Пушкине", "напиши стих в стиле Есенина", "сочини стихотворение про осень", "расскажи сказку",
         "придумай четверостишие на день рождения", "какая погода завтра", "блокнот со стихами открой"]
ok(all(llm.reading(t) for t in READ), f"прочитать готовое узнаётся: {[t for t in READ if not llm.reading(t)]}")
ok(not any(llm.reading(t) for t in WRITE), f"сочинить и прочее — не «прочитать»: {[t for t in WRITE if llm.reading(t)]}")
ok(llm.creative_temp(READ[0]) == 0.7 and llm.creative_temp("сочини стихотворение про осень") == 0.95,
   "прочитать — без творческой температуры, сочинить — как раньше 0.95")
ok("read_webpage" in llm.READ_NOTE and "целиком" in llm.READ_NOTE and "сочиняй" in llm.READ_NOTE, "подсказка: точный текст целиком, страница")
src = (ROOT / "core/engine_answer.py").read_text()
ok(re.search(r"if reading\(text\.split[^\n]+\n\s+notes\.append\(READ_NOTE\)\s+#[^\n]*\n\s+elif POEM_ASK", src),
   "в ходе разговора: прочитать — READ_NOTE вместо ремесла рифмы")
st = tools.search_text([{"title": "Мужичок с ноготок", "snippet": "Однажды в студёную…", "url": "https://rustih.ru/x"}])
ok("read_webpage" in st and "отрывки" in st, f"выдача поиска напоминает: это отрывки, текст — read_webpage: {st[-90:]!r}")
ok(tools.search_text([]) == "Ничего не нашлось.", "пусто — как раньше")

# телефон: те же решения
app = (ROOT / "android/assets/www/app.js").read_text()
a, b = app.index("const READ_ASK"), app.index("const READ_NOTE")
js = app[a:b].replace("const ", "var ") + "\nconst T = %s; console.log(JSON.stringify(T.map(t => reading(t))));" % json.dumps(READ + WRITE, ensure_ascii=False)
r = subprocess.run(["node", "-e", "var window = {t: k => k};\n" + js], capture_output=True, text=True)
got = json.loads(r.stdout or "[]")
ok(got == [True] * len(READ) + [False] * len(WRITE), f"телефон узнаёт так же: {got} {r.stderr[:200]}")
ok("reading(text) ? READ_NOTE()" in app and "CREATIVE_ASK.test(text) && !reading(text)" in app and "SEARCH_TAIL()" in app,
   "телефон: подсказка, температура и хвост выдачи поиска")
for lang in ("ru", "en"):
    d = json.loads((ROOT / f"data/i18n/{lang}.json").read_text())
    ok(d.get("tool.note.read") and d.get("tool.search.tail"), f"{lang}: тексты подсказки и выдачи — в словаре")
ex = json.loads((ROOT / "data/exam/scenarios.json").read_text())["scenarios"]
ok(any(x["id"] == "read_poem_whole" for x in ex) and "read_poem_whole" in (ROOT / "android/assets/www/exam.js").read_text(),
   "сценарий экзамена read_poem_whole — на компьютере и телефоне")
print("ИТОГ:", "всё прошло" if not fails else f"{len(fails)} ошибок")
sys.exit(1 if fails else 0)
