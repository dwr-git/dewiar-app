"""Пакет «Здоровье» 29.10 вечер. №405 (телефон): «Запиши потраченную 2.000 руб» — «Записала», а money_add не вызван (дважды);
«верх правильный, низ не добавлено» — в «Куда ушли деньги» только три категории, сумма не сходилась с «потрачено».
№406 (компьютер): «выключи свет в зале» выключал свет везде (короткое «Зал» не узнавалось в «зале»), а «выключи сет в зале»
(ослышка) — модель звала power: выключить компьютер."""
import os, subprocess, sys, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


# ---------- №406: свет в зале ----------
import smarthome as S  # noqa: E402
names = ["Ванная", "Детская", "Домофон", "Зал", "Коридор", "Кухня", "Спальня", "Туалет", "Цех", "Сад"]
rooms = [{"id": str(i), "name": n} for i, n in enumerate(names)]
devs = [{"id": "d" + r["id"], "name": "Свет", "type": "devices.types.light", "room": r["id"], "room_name": r["name"],
         "capabilities": [{"type": S.ON_OFF}]} for r in rooms]
info = {"rooms": rooms, "devices": devs, "scenarios": []}
h = S.Home.__new__(S.Home)
got = lambda t: [d["room_name"] for d in h.match_rank(t, info)[1]]  # noqa: E731
ok(got("свет в зале") == ["Зал"], f"«свет в зале» — только зал: {got('свет в зале')}")
ok(got("свет в саду") == ["Сад"] and got("свет в цеху") == ["Цех"], "короткие комнаты: «в саду», «в цеху»")
ok(got("свет на кухне") == ["Кухня"] and got("всё в зале") == ["Зал"], "«на кухне», «всё в зале» — как раньше")
ok(len(got("свет")) == len(names) and len(got("весь свет")) == len(names) and len(got("свет в доме")) == len(names), "«свет», «весь свет», «в доме» — весь")
ok(got("свет в бане") == [] and got("свет в гараже") == [], "комнаты нет — не весь свет в доме, а ничего (уточнит модель)")
ok(not S._sim("дом", "домофон") and S._sim("зал", "зале") and not S._sim("зал", "залив"), "короткие слова: только падежное окончание")

import tools as T  # noqa: E402


class P:
    def schedule(self, a):
        return "ok " + a


res = []
for t in ["сет в зале", "свет", "лампу на кухне", "компьютер", ""]:
    try:
        res.append(T.t_power({"action": "shutdown", "target": t}, {"power": P()}))
    except T.ToolError:
        res.append("отказ")
ok(res == ["отказ", "отказ", "отказ", "ok shutdown", "ok shutdown"], f"power не выключает компьютер, если просят свет или комнату: {res}")
ok("smart_home" in T.TOOLS["power"][0] and "не power" in T.TOOLS["power"][0], "в описании power: свет и комнаты — это smart_home")

# ---------- №405: «записала», а money_add не было ----------
import quality as Q  # noqa: E402
ok(Q.money_claim("Запиши потраченную 2.000 руб", "Записала: 2000 рублей.", []).startswith("ПРОВЕРКА"), "«записала» без money_add — ловится")
ok(Q.money_claim("напиши расход окна аванс 20.000", "Готово, внесла 20 000 в окна.", ["money_report"]).startswith("ПРОВЕРКА"),
   "и когда звалось другое (money_report)")
ok(Q.money_claim("Запиши потраченную 2.000 руб", "Записала.", ["money_add"]) == "", "money_add был — не мешаем")
ok(Q.money_claim("сколько я потратил за месяц?", "Записано 2000.", []) == "", "вопрос о тратах — не запись")
ok("money_add" in Q.saved_claim("потратил 300", "Записала.", []), "общая проверка «записала» тоже называет money_add")
src = (ROOT / "core/engine_answer.py").read_text(encoding="utf-8")
ok("money_claim(text, step_text, called)" in src, "компьютер: проверка в ходе ответа")
import json  # noqa: E402
sc = json.loads((ROOT / "data/exam/scenarios.json").read_text(encoding="utf-8"))["scenarios"]
ok(any(x["id"] == "money_dot" for x in sc) and "money_dot" in (ROOT / "android/assets/www/exam.js").read_text(encoding="utf-8"),
   "сценарий экзамена «2.000 руб» — на компьютере и телефоне")

# телефон: claimedAction и «Куда ушли деньги»
w = Path(tempfile.mkdtemp()) / "www"
subprocess.run(["bash", str(ROOT / "android/tools/www_assemble.sh"), str(w)], check=True, capture_output=True)
errs = []
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 393, "height": 852}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto((w / "index.html").as_uri()); pg.wait_for_timeout(900)
    r = pg.evaluate("""() => [ (claimedAction('Записала: 2000 рублей.', new Set(), 'Запиши потраченную 2.000 руб') || {}).tool,
      (claimedAction('Готово, внесла.', new Set(['money_report']), 'напиши расход окна аванс 20.000') || {}).tool,
      claimedAction('Записала.', new Set(['money_add']), 'Запиши потраченную 2.000 руб'),
      claimedAction('В этом месяце ты потратил 2000.', new Set(), 'сколько я потратил?')]""")
    ok(r[0] == "money_add" and r[1] == "money_add" and r[2] is None and r[3] is None, f"телефон: «записала» без money_add — ловится: {r}")
    r = pg.evaluate("""() => { const t = (d) => `2026-10-${String(d).padStart(2, '0')}`;
      const m = [['Окна', 20000], ['Коммунальные услуги', 3514], ['Услуги', 2500], ['Прочее', 2000], ['Разное', 1000], ['Связь', 400]]
        .map(([c, a], i) => ({ kind: 'expense', amount: a, currency: 'RUB', category: c, date: t(i + 1) }));
      fileSave('money.json', JSON.stringify(m)); MON_AT = [2026, 9]; openMonth();
      return [$$('#sh-month .mon-sts b').map(e => e.textContent), $$('#sh-month .mon-cats li').map(e => [e.childNodes[1].textContent, e.querySelector('b').textContent]),
              $$('#sh-month .mon-bar i').length, $$('#sh-month .mon-cats li > i').map(e => getComputedStyle(e).backgroundColor)]; }""")
    pg.wait_for_timeout(200)
    tot = sum(int(v.replace(" ", "").replace(" ", "")) for _, v in r[1])
    ok(r[0][1].replace(" ", "").replace(" ", "") == "29414" and tot == 29414, f"«Куда ушли деньги» сходится с «потрачено»: {r[1]}")
    ok([n for n, _ in r[1]] == ["Окна", "Коммунальные услуги", "Услуги", "Прочее", "Остальное"] and r[2] == 5, "четыре крупные + «Остальное»")
    ok(len(set(r[3])) == 5 and "rgba(0, 0, 0, 0)" not in r[3], f"у каждой строки свой цвет: {r[3]}")
    b.close()
ok(not errs, f"без ошибок: {errs[:2]}")
month = (ROOT / "core/month.py").read_text(encoding="utf-8")
sys.path.insert(0, str(ROOT / "core"))
import month as M  # noqa: E402
c6 = M._cats([{"name": n, "sum": v} for n, v in [("а", 5), ("б", 4), ("в", 3), ("г", 2), ("д", 1), ("е", 1)]])
ok([x["name"] for x in c6] == ["а", "б", "в", "г", "Остальное"] and c6[-1]["sum"] == 2 and c6[-1]["rest"], "компьютер, «Мой месяц»: то же — «Остальное»")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
