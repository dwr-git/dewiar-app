"""Память 2.0 (27.10, владелец: «в подсказку идут только последние 2500 знаков "Обо мне" — старое о человеке теряется;
нужны страницы по людям и темам с датами и поиск по смыслу»). core/memory.py: страницы, главное в подсказке,
к вопросу — по смыслу, метки «сейчас» и «через N дней»; файл и формат строк прежние (телефон и синхронизация)."""
import datetime as dt
import os
import random
import sys
from pathlib import Path

ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
import memory as M  # noqa: E402

fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


BASE = """# Обо мне

Что ассистент знает о вас.

- Меня зовут Михаил, живу в Минске _(01.03.2026)_
- Дочь Маша, 7 лет _(02.03.2026)_
- Маша любит рисовать _(03.03.2026)_
- У мамы день рождения 14 ноября _(04.03.2026)_
- Мама Людмила любит пионы, не любит лилии _(05.03.2026)_
- Мама живёт в Гродно (раньше: в Лиде; менялось 1 раз). _(06.06.2026)_
- Работаю бухгалтером в фирме «Альфа» _(07.03.2026)_
- Люблю короткие ответы _(08.03.2026)_
- Собака Бади, лабрадор _(09.03.2026)_
- Бади ест только сухой корм _(09.03.2026)_
- Сергей — мой коллега, сидим рядом _(10.03.2026)_
- Пью таблетки от давления по утрам _(10.03.2026)_
"""
today = dt.date(2026, 10, 27)
facts = M.parse(BASE)
ok(len(facts) == 12 and facts[5]["prev"] == ["в Лиде"] and facts[5]["text"] == "Мама живёт в Гродно" and facts[0]["date"] == dt.date(2026, 3, 1),
   "разбор: 12 фактов, дата записи, история «раньше» отдельно")
v = M.view(BASE, today)
pg = {p["title"]: p for p in v["pages"]}
ok(v["pages"][0]["title"] == "Обо мне" and "Меня зовут Михаил" in v["pages"][0]["facts"][0]["text"], "первая страница — «Обо мне»: имя и город")
ok(len(pg.get("Мама", {}).get("facts", [])) == 3, f"страница «Мама» — три факта (и «мама Людмила» туда же): {list(pg)}")
ok(len(pg.get("Маша, дочь", {}).get("facts", [])) == 2, "«Маша, дочь»: имя, однажды названное с родством, узнаётся и одно")
ok(len(pg.get("Бади, собака", {}).get("facts", [])) == 2 and "Сергей, коллега" in pg, "питомец и коллега — свои страницы")
ok("Здоровье" in pg and "Работа" in pg and "Как со мной говорить" in pg, "темы: здоровье, работа, как со мной говорить")
mama = {f["text"]: f for f in pg["Мама"]["facts"]}
ok(mama["Мама живёт в Гродно"]["tags"] == [["now", "сейчас"]] and mama["Мама живёт в Гродно"]["prev"] == ["в Лиде"], "менялось — метка «сейчас» и прежнее значение")
ok(["soon", "через 18 дней"] in mama["У мамы день рождения 14 ноября"]["tags"], "день рождения скоро — «через 18 дней»")
ok(v["fits"] and v["core"] == 12, "память маленькая — в подсказку идёт целиком (как раньше)")
ok(M.core_text(BASE) == "\n".join(f["line"] for f in facts), "core_text маленькой памяти — все строки, как прежний memory_text")

# по смыслу: слов «подарок» в памяти нет — а мама, день рождения и пионы находятся
r = M.find("что подарить маме", BASE)
ok([x["text"] for x in r[:3]] == ["У мамы день рождения 14 ноября", "Мама Людмила любит пионы, не любит лилии", "Мама живёт в Гродно"],
   f"«что подарить маме» → день рождения, пионы, Гродно: {[x['text'] for x in r[:3]]}")
r = M.find("как дела у дочки в школе", BASE)
ok({x["text"] for x in r[:2]} == {"Маша любит рисовать", "Дочь Маша, 7 лет"}, "«у дочки» → страница «Маша, дочь»")
r = M.find("чем покормить собаку", BASE)
ok("Бади ест только сухой корм" in [x["text"] for x in r[:2]], "«покормить собаку» → «Бади ест только сухой корм»")
r = M.find("что у меня со здоровьем", BASE)
ok(r and r[0]["text"] == "Пью таблетки от давления по утрам", "«со здоровьем» → страница «Здоровье»")
ok(not M.find("какая погода завтра", BASE), "вопрос не о человеке — ничего не подбирается")

# большая память: главное (о себе, кто есть кто, новое) — в подсказку, остальное — к вопросу
random.seed(3)
extra = "".join(f"- Заметка о работе номер {i}: отчёт для клиента {i} сдан вовремя _(1{i % 9}.04.2026)_\n" for i in range(120))
BIG = BASE + extra + "- Мама просила купить ей новый телефон _(20.10.2026)_\n"
core = M.core_text(BIG)
ok(len(core) <= 2500 + 120 and "И ещё" in core and "Меня зовут Михаил" in core and "Люблю короткие ответы" in core,
   "большая память: в подсказке главное о себе и как говорить, и строка «И ещё N фактов…»")
ok("Дочь Маша, 7 лет" in core or "Маша любит рисовать" in core, "кто есть кто — в подсказке всегда")
ok("Мама просила купить ей новый телефон" in core, "самое новое — в подсказке")
ok(core == M.core_text(BIG), "подсказка не меняется от вопроса к вопросу (кэш модели)")
lines, pages = M.relevant("что подарить маме на день рождения", BIG)
ok("У мамы день рождения 14 ноября" in lines or "У мамы день рождения 14 ноября" in core, "день рождения мамы — в подсказке или в справке к вопросу")
ok("пионы" in lines + core and (not lines or "Мама" in pages), f"пионы найдутся по смыслу: страницы {pages}")
lines2, _ = M.relevant("какая погода", BIG)
ok(lines2 == "", "к вопросу не о человеке справки «Из памяти» нет")

# убрать факт по номеру — только он
t2 = M.forget(BASE, 3)
ok("У мамы день рождения" not in t2 and t2.count("\n- ") == 11 and t2.startswith("# Обо мне"), "«Забыть» убирает одну строку, шапка на месте")
ok(M.forget(BASE, 99) == BASE, "чужой номер — файл не меняется")

# формат строки совместим с телефоном и синхронизацией (sync._FACT)
import re  # noqa: E402
FACT = r"^- (.+?)(?: _\(\d\d\.\d\d\.\d{4}\)_)?\s*$"
ok(all(re.match(FACT, f["line"]) for f in M.parse(BIG)), "строки фактов — прежнего формата (sync._FACT)")

# ---------- телефон: то же — последние факты в подсказке, старые к вопросу по смыслу (app.js memPick) ----------
import json, shutil, subprocess, tempfile  # noqa: E401,E402
from playwright.sync_api import sync_playwright  # noqa: E402
tmp = Path(tempfile.mkdtemp()); www = tmp / "www"
shutil.copytree(ROOT / "android/assets/www", www)
for x in ("entities.js", "speechnorm.js", "skins.css", "skins.js"):
    shutil.copy(ROOT / "ui/assets" / x, www / x)
shutil.copytree(ROOT / "ui/assets/live", www / "live", dirs_exist_ok=True)
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                capture_output=True, text=True, check=True).stdout, encoding="utf-8")
old = ["У мамы день рождения 14 ноября", "Мама любит пионы", "Собака Бади ест только сухой корм", "Пью таблетки от давления по утрам"]
fill = [f"Отчёт для клиента {i} сдан" for i in range(40)]
with sync_playwright() as pw:
    b = pw.chromium.launch(); pg = b.new_page(viewport={"width": 400, "height": 820}); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(1000)
    r = pg.evaluate("""([old, fill]) => { S.memory = old.concat(fill);
      return { gift: memPick("что подарить маме"), dog: memPick("чем покормить собаку"), none: memPick("какая погода"),
               ctx: turnContext("что подарить маме"), small: (S.memory = old, memPick("что подарить маме")) }; }""", [old, fill])
    b.close()
ok(r["gift"][:2] == ["Мама любит пионы", "У мамы день рождения 14 ноября"] or set(r["gift"][:2]) == {"Мама любит пионы", "У мамы день рождения 14 ноября"},
   f"телефон: «что подарить маме» — старые факты о маме по смыслу: {r['gift']}")
ok(r["dog"] and r["dog"][0] == "Собака Бади ест только сухой корм", f"телефон: «покормить собаку» → Бади: {r['dog']}")
ok(r["none"] == [] and r["small"] == [], "телефон: не о человеке или память маленькая — без справки")
ok("Из памяти о пользователе" in r["ctx"] and "пионы" in r["ctx"], "телефон: подобранное — в справке к вопросу")
ok(not errs, f"телефон: без ошибок страницы {errs[:2]}")
shutil.rmtree(tmp, ignore_errors=True)

print("ИТОГ:", "все проверки пройдены" if not fails else f"не пройдено {len(fails)}")
sys.exit(1 if fails else 0)
