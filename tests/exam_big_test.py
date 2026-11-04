"""Экзамен больших задач (docs/HARNESS.md, раздел 5; выпуск 1, 04.11): заготовки детерминированы (один seed — те же байты
и те же ответы), проверки Б3–Б7 и Б11 на заведомо верном итоге дают «сдано», на заведомо неверном — «не сдано».
Сценарии — в группе «Большие задачи» (поле big), идут только с --big; предел — до 60 минут; метрики — шаги, токены, кэш."""
import csv
import hashlib
import io
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
import exam  # noqa: E402
import exam_big as EB  # noqa: E402

FAILS = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        FAILS.append(m)


TMP = Path(tempfile.mkdtemp())


def tree(d):
    return {p.relative_to(d).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path(d).rglob("*")) if p.is_file()}


def passed(chs):
    return all(c["ok"] for c in chs)


def fresh(kind, name):
    d = TMP / name
    info = exam.make_fixture(kind, d, 1)
    return d, info


# ---------- детерминированность ----------
for kind in EB.FIXTURES:
    a, b, c = TMP / f"{kind}-a", TMP / f"{kind}-b", TMP / f"{kind}-c"
    ia, ib, ic = exam.make_fixture(kind, a, 1), exam.make_fixture(kind, b, 1), exam.make_fixture(kind, c, 2)
    ok(tree(a) == tree(b) and json.dumps(ia, ensure_ascii=False) == json.dumps(ib, ensure_ascii=False) and tree(a),
       f"{kind}: один seed — те же файлы байт в байт и те же ответы ({len(tree(a))} файлов)")
    ok(tree(a) != tree(c), f"{kind}: другой seed — другие данные")

# ---------- Б3: папка из 200 файлов ----------
d, info = fresh("downloads", "b3ok")
root = d / "Загрузки-фикстура"
ok(len(list(root.iterdir())) == 200 and len(info["pairs"]) == 15, "Б3: 200 файлов, 15 пар дубликатов")
from PIL import Image  # noqa: E402
ph = next(f for f in info["files"] if f["cat"] == "photo")
ok(Image.open(root / ph["name"]).getexif().get_ifd(0x8769).get(0x9003, "").startswith(str(ph["year"])), "Б3: год фото — в EXIF")
dups = {b for a, b in info["pairs"]}


def sort_b3(d, info, bad=False):
    root = d / "Загрузки-фикстура"
    inv = []
    for f in info["files"]:
        if f["name"] in dups:
            dst = Path("Дубликаты") / f["name"]
        elif f["cat"] == "photo":
            dst = Path("Фото") / str(f["year"] + (1 if bad and f["name"] == "IMG_1010.jpg" else 0)) / f["name"]
        elif f["cat"] == "invoice":
            dst = Path("Счета") / str(f["year"]) / f["name"]
        elif f["cat"] == "doc":
            dst = Path("Документы") / f["name"]
        else:
            dst = Path("Мусор") / f["name"]
        (root / dst).parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(root / f["name"]), str(root / dst))
        inv.append([f["name"], dst.as_posix()])
    if bad:
        next((root / "Мусор").iterdir()).unlink()
    (d / "outputs").mkdir(exist_ok=True)
    with open(d / "outputs" / "опись.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["было", "стало"])
        w.writerows(inv)


sort_b3(d, info)
chs = exam.BIG_CHECKS["downloads"](d, info)
ok(passed(chs), f"Б3: верная раскладка — сдано {[c['name'] for c in chs if not c['ok']]}")
d2, info2 = fresh("downloads", "b3bad")
sort_b3(d2, info2, bad=True)
chs = exam.BIG_CHECKS["downloads"](d2, info2)
bad = {c["name"][:30] for c in chs if not c["ok"]}
ok(not passed(chs) and any("ровно один раз" in c["name"] and not c["ok"] for c in chs) and any("EXIF" in c["name"] and not c["ok"] for c in chs),
   f"Б3: удалён файл и фото не в своём году — не сдано: {bad}")

# ---------- Б4: скрипт по выпискам ----------
SCRIPT = r'''
import csv, io, glob, os, collections, openpyxl
rows = {}
for f in sorted(glob.glob("выписки/*.csv")):
    raw = open(f, "rb").read()
    try:
        t = raw.decode("utf-8")
    except UnicodeDecodeError:
        t = raw.decode("cp1251")
    d = ";" if t.splitlines()[0].count(";") else ","
    for r in list(csv.reader(io.StringIO(t), delimiter=d))[1:]:
        rows[r[1]] = (r[3], float(r[4].replace(",", ".")) * K)
cats = collections.defaultdict(float)
for c, s in rows.values():
    cats[c] += s
os.makedirs("outputs", exist_ok=True)
wb = openpyxl.Workbook(); ws = wb.active; ws.append(["Категория", "Сумма"])
for c, s in sorted(cats.items()):
    ws.append([c, round(s, 2)])
wb.save("outputs/итоги.xlsx")
open("outputs/итоги.md", "w", encoding="utf-8").write("# Итоги\n" + "\n".join(f"- {c}: {s:.2f}" for c, s in cats.items()) + "\nПовтор операции учтён один раз.\n")
'''
import subprocess  # noqa: E402
for name, k, want in (("b4ok", "1", True), ("b4bad", "1.01", False)):
    d, info = fresh("statements", name)
    ok(len(list((d / "выписки").glob("*.csv"))) == 12 and (d / "выписки" / "2025-01.csv").read_bytes().decode("cp1251").startswith("Дата;"),
       f"Б4 ({name}): 12 выписок, январь — cp1251 и «;»") if name == "b4ok" else None
    (d / "outputs").mkdir(exist_ok=True)
    (d / "outputs" / "считать.py").write_text(SCRIPT.replace("* K", "* " + k), encoding="utf-8")
    r = subprocess.run([sys.executable, "outputs/считать.py"], cwd=d, capture_output=True, text=True)
    chs = exam.BIG_CHECKS["statements"](d, info)
    ok(passed(chs) == want and r.returncode == 0, f"Б4: {'верный скрипт — сдано' if want else 'суммы на 1% больше — не сдано'} "
                                                 f"{[(c['name'][:40], c['detail'][:80]) for c in chs if not c['ok']]}")
d, info = fresh("statements", "b4dup")
import openpyxl  # noqa: E402
(d / "outputs").mkdir()
wb = openpyxl.Workbook()
ws = wb.active
for c, s in info["cats"].items():
    ws.append([c, round(s + (info["dup"]["sum"] if c == info["dup"]["cat"] else 0), 2)])
wb.save(d / "outputs" / "итоги.xlsx")
chs = exam.BIG_CHECKS["statements"](d, info, rerun=False)
ok(any("один раз" in c["name"] and not c["ok"] for c in chs), "Б4: повтор посчитан дважды — «повтор учтён один раз» не сдано")

# ---------- Б5: сайт ----------


def site(d, info, bad=False):
    s = d / "outputs" / "site"
    s.mkdir(parents=True)
    nav = '<nav><a href="index.html">Главная</a> <a href="menu.html">Меню</a> <a href="contacts.html">Контакты</a></nav>'
    vp = "" if bad else '<meta name="viewport" content="width=device-width, initial-scale=1">'
    items = info["items"][:-1] if bad else info["items"]
    menu = "".join(f"<li>{it['name']} — {it['price']} ₽</li>" for it in items)
    for name, body in (("index.html", "<h1>Пекарня «Колос»</h1><p>Тёплый хлеб каждое утро.</p>"), ("menu.html", f"<ul>{menu}</ul>"),
                       ("contacts.html", f"<p>Телефон: {info['phone']}</p>")):
        (s / name).write_text(f"<!doctype html><html><head><meta charset='utf-8'>{vp}<title>Колос</title></head><body>{nav}{body}</body></html>",
                              encoding="utf-8")


d, info = fresh("bakery", "b5ok")
site(d, info)
chs = exam.BIG_CHECKS["bakery"](d, info, browser=False)
ok(passed(chs), f"Б5: три страницы, навигация, меню, viewport — сдано {[c['name'] for c in chs if not c['ok']]}")
d, info = fresh("bakery", "b5bad")
site(d, info, bad=True)
chs = exam.BIG_CHECKS["bakery"](d, info, browser=False)
ok(not passed(chs) and sum(1 for c in chs if not c["ok"]) >= 2, f"Б5: без viewport и без одной позиции — не сдано {[c['name'][:30] for c in chs if not c['ok']]}")

# Б5 в настоящем браузере (Playwright + Chromium): ширина 375, прокрутка вбок, ошибки консоли
BR = EB.browser_ok()
name375 = "ширина 375 (телефон): без горизонтальной прокрутки и ошибок консоли"
if BR:
    d, info = fresh("bakery", "b5br")
    site(d, info)
    chs = exam.BIG_CHECKS["bakery"](d, info)
    c = next(x for x in chs if x["name"] == name375)
    ok(passed(chs) and "ширина 375 при экране 375" in c["detail"], f"Б5 в браузере: верный сайт на ширине 375 — сдано ({c['detail'][:90]})")
    m = d / "outputs/site/menu.html"
    m.write_text(m.read_text(encoding="utf-8").replace("<ul>", "<div style='width:900px'>широкая таблица</div><script>nope()</script><ul>"),
                 encoding="utf-8")
    c = next(x for x in exam.BIG_CHECKS["bakery"](d, info) if x["name"] == name375)
    ok(not c["ok"] and "menu.html: ширина 9" in c["detail"] and "nope" in c["detail"],
       f"Б5 в браузере: блок шире экрана и ошибка скрипта — не сдано ({c['detail'][:140]})")
else:
    print("⚠ браузера (Playwright + Chromium) здесь нет — Б5 в браузере проверен только как «не проверено»")
real = EB.browser_pages
EB.browser_pages = lambda *a, **k: None                  # как на сервере без браузера
d, info = fresh("bakery", "b5nobr")
site(d, info)
chs = exam.BIG_CHECKS["bakery"](d, info)
c = next(x for x in chs if x["name"] == name375)
ok(not c["ok"] and c.get("unchecked") and "не проверено (нет браузера" in c["detail"], "нет браузера — «не проверено», а не «пройдено»")
import types  # noqa: E402
r = exam.finish_result(types.SimpleNamespace(tmp=TMP), {"id": "big_b5_site", "group": "Большие задачи", "title": "Б5", "steps": [], "checks": chs, "judge": {"score": 8, "why": "хорошо"}})
ok(not r["passed"] and r["partial"] and r["unchecked"] == [name375], "сценарий не сдан полностью: отдельный статус partial")
sm = exam.summary([r])
ok(sm["passed"] == 0 and sm["partial"] == 1 and sm["by_group"]["Большие задачи"].get("partial") == 1, f"в сводке — отдельно: {sm}")
md = exam.markdown({"version": "x", "started": "2026-11-04T10:00:00", "model": "m", "duration_s": 60, "summary": sm,
                    "scenarios": [dict(r, time_s=1, score=8)]})
ok("## ◐" in md and "не проверено до конца" in md and "- ◐ ширина 375" in md, "в отчёте .md — ◐ «не проверено»")
EB.browser_pages = real

# ---------- Б6: сверка ----------
d, info = fresh("reconcile", "b6")
ok(len(info["planted"]) == 9 and (d / "сверка" / "склад.xlsx").is_file() and (d / "сверка" / "выгрузка_1С.csv").is_file(), "Б6: три таблицы, 9 заложенных расхождений")
sk = [r for r in openpyxl.load_workbook(d / "сверка" / "склад.xlsx").active.iter_rows(values_only=True)]
ok(250 < len(sk) < 320, f"Б6: ≈300 строк ({len(sk)})")


def rep_b6(d, arts):
    (d / "outputs").mkdir(exist_ok=True)
    with open(d / "outputs" / "расхождения.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["артикул", "где", "что не так", "значения"])
        for a in arts:
            w.writerow([a, "склад / 1С", info["planted"].get(a, "?"), "—"])


planted = sorted(info["planted"])
rep_b6(d, planted[:8])
ok(passed(exam.BIG_CHECKS["reconcile"](d, info)), "Б6: 8 из 9 без ложных — сдано")
rep_b6(d, planted[:6] + ["A-1001", "A-1002", "A-1003"])
chs = exam.BIG_CHECKS["reconcile"](d, info)
ok(not passed(chs), f"Б6: 6 из 9 и 3 ложных — не сдано {[c['detail'][:60] for c in chs if not c['ok']]}")

# ---------- Б7: поездка ----------
d, info = fresh("trip", "b7")
data = json.loads((d / "поездка" / "цены_казань.json").read_text(encoding="utf-8"))
P = info["prices"]


def trip(d, bad=False):
    (d / "outputs").mkdir(exist_ok=True)
    m1 = "Национальный музей Татарстана" if bad else "Музей-заповедник «Казанский кремль»"
    (d / "outputs" / "поездка.md").write_text(
        f"# Казань на 3 дня\n\n## День 1 — понедельник\n- 10:00 {m1}\n- 14:00 Обед: Столовая «Дом татарской кулинарии»\n- 16:00 Улица Баумана\n\n"
        "## День 2 — вторник\n- 10:00 Национальный музей Татарстана\n- 13:00 Кафе «Чак-чак»\n- 15:00 Музей чак-чака\n\n"
        "## День 3 — среда\n- 09:30 Автобус в Свияжск, туда-обратно\n- 11:00 Остров-град Свияжск\n- 18:00 Ресторан «Тюбетей»\n", encoding="utf-8")
    rows = [("Отель «Волжский», 2 ночи", P["Отель «Волжский»"] * 2), ("Музей-заповедник «Казанский кремль», 2 билета", 1400),
            ("Национальный музей Татарстана, 2 билета", 1000), ("Музей чак-чака, 2 билета", 1800),
            ("Столовая «Дом татарской кулинарии», 2 чел.", 1400), ("Кафе «Чак-чак», 2 чел.", 1800), ("Ресторан «Тюбетей», 2 чел.", 3000),
            ("Автобус в Свияжск, туда-обратно, 2 чел.", 1800), ("Остров-град Свияжск, 2 чел.", 1000), ("Такси по центру, 4 поездки", 1800)]
    if bad:
        rows.append(("Подарки", 50000))
    with open(d / "outputs" / "смета.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["статья", "сумма"])
        w.writerows(rows)
        w.writerow(["Итого", sum(x[1] for x in rows)])


trip(d)
chs = exam.BIG_CHECKS["trip"](d, info)
ok(passed(chs), f"Б7: план по дням и смета из заготовки — сдано {[(c['name'][:30], c['detail'][:80]) for c in chs if not c['ok']]}")
trip(d, bad=True)
chs = exam.BIG_CHECKS["trip"](d, info)
nb = [c["name"] for c in chs if not c["ok"]]
ok(any("понедельник" in n for n in nb) and any("60000" in n for n in nb), f"Б7: закрытый в понедельник музей и перерасход — не сдано {nb}")

# ---------- Б11: Anki с перезапуском ----------
d, info = fresh("anki", "b11")
ok(len((d / "слова.txt").read_text(encoding="utf-8").split()) == 40, "Б11: 40 слов")


def anki(d, words, journal):
    (d / "outputs").mkdir(exist_ok=True)
    (d / "outputs" / "anki.csv").write_text("".join(f"{w};перевод {w};This is a {w}.\n" for w in words), encoding="utf-8")
    (d / "журнал.md").write_text(journal, encoding="utf-8")


info["restarted"] = True
anki(d, info["words"], "# Журнал\n**10:00** · ▶ Начал работу (Лира).\n**10:05** · ▶ Компьютер включили — продолжаю, где остановился.\n")
ok(passed(exam.BIG_CHECKS["anki"](d, info, {"status": "done"})), "Б11: 40 карточек, продолжила после перезапуска — сдано")
anki(d, info["words"][:39] + info["words"][:1], "# Журнал\n**10:00** · ▶ Начал работу (Лира).\n**10:05** · ▶ Начал работу (Лира).\n")
chs = exam.BIG_CHECKS["anki"](d, info, {"status": "done"})
ok(sum(1 for c in chs if not c["ok"]) == 2, f"Б11: повтор вместо 40-го слова и начала заново — не сдано {[c['name'][:40] for c in chs if not c['ok']]}")

# ---------- сценарии и пределы ----------
sc = [s for s in json.loads((ROOT / "data/exam/scenarios.json").read_text(encoding="utf-8"))["scenarios"] if s.get("big")]
ok({s["big"]["fixture"] for s in sc} == set(EB.FIXTURES) and all(s["group"] == "Большие задачи" and s.get("judge") for s in sc),
   f"сценарии группы «Большие задачи»: {[s['id'] for s in sc]}")
ok(all(exam.scenario_limit(s) <= exam.BIG_MAX_S == 3600 and exam.scenario_limit(s) > exam.LONG_MAX_S for s in sc),
   "предел большой задачи — до 60 минут (обычный долгий — 25)")
m = exam.big_metrics({"steps": 30, "quality": {"usage": {"in": 1000, "out": 50, "cached": 700, "ck": 3, "req": 3}}}, 125.4)
ok(m == {"steps": 30, "tok_in": 1000, "tok_out": 50, "cache": 0.7, "time_s": 125, "req": 3}, f"метрики: шаги, токены, доля кэша, время {m}")
s = exam.summary([{"group": "Большие задачи", "passed": True, "score": 7, "metrics": m}, {"group": "Разговор", "passed": False, "score": 3}])
ok(s["big"]["n"] == 1 and s["big"]["cache"] == 0.7, f"в сводке — средние метрики больших задач {s.get('big')}")
md = exam.markdown({"version": "x", "started": "2026-11-04T10:00:00", "model": "m", "duration_s": 60, "summary": s,
                    "scenarios": [{"group": "Большие задачи", "title": "Б3", "time_s": 1, "passed": True, "steps": [], "checks": [], "metrics": m}]})
ok("большие задачи в среднем" in md and "из кэша 70%" in md, "в отчёте .md — метрики")
import cloudrunner  # noqa: E402
src = (ROOT / "core/cloudrunner.py").read_text(encoding="utf-8")
ok('args.append("--big")' in src and "openpyxl" in cloudrunner.BIG_PROBE and "playwright" in cloudrunner.BIG_PROBE and "--only-shell" in src,
   "исполнитель в облаке: галочка big → --big; в окружении экзамена openpyxl и playwright, Chromium — в папку исполнителя")

# ---------- Б11 целиком: exam.run_big с перезапуском «ядра» посреди задачи (заглушка модели, настоящий TaskManager) ----------
os.environ.update(DEWIAR_WORKSPACE=str(TMP / "ws"), DEWIAR_STATE_DIR=str(TMP / "st"), DEWIAR_TASK_RESUME_SEC="1")
sys.path.insert(0, str(ROOT / "tests"))
import asyncio  # noqa: E402
import time  # noqa: E402
import task_mock as TMK  # noqa: E402
import tasks as TK  # noqa: E402
CODE = ("words = open('слова.txt', encoding='utf-8').read().split()\nimport os\nos.makedirs('outputs', exist_ok=True)\n"
        "open('outputs/anki.csv', 'w', encoding='utf-8').write(''.join(f'{w};перевод {w};A {w} here.\\n' for w in words[:N]))\nprint('ok')")
STEPS = [("update_plan", {"plan": "**Готово, когда:** 40 карточек\n\n- [ ] 1–10\n- [ ] 11–40"})]
STEPS += [("run_python", {"code": CODE.replace("N]", f"{n}]")}) for n in (10, 20, 30, 40)]
STEPS += [("log", {"text": f"проверил {k}"}) for k in range(5)]
STEPS += [("run_python", {"code": CODE.replace("N]", "40]")})]      # шаг, прерванный перезапуском, модель повторяет — здесь сам сценарий
STEPS += [("update_plan", {"plan": "**Готово, когда:** 40 карточек\n\n- [x] 1–10\n- [x] 11–40"}), ("show", {"path": "outputs/anki.csv"}),
          ("finish", {"summary": "40 карточек в outputs/anki.csv."})]
STEPS = [(lambda req, s_=s_: (time.sleep(0.5), s_)[1]) for s_ in STEPS]      # шаг модели — полсекунды: экзамен успевает перезапустить
mk = TMK.Mock({"Б11. Карточки Anki с перезапуском посреди работы": STEPS})


class FakeCore:
    """Ядро для run_big: те же команды (task_create, task_resume, tasks_list), stop/start — как выключить и включить программу."""
    def __init__(self):
        self.restarts = 0
        self.start()

    def start(self):
        self.host = TMK.Host(mk)
        self.tm = TK.TaskManager(self.host)

    async def connect(self):
        pass

    async def stop(self):
        self.restarts += 1
        self.host.stopping.set()
        for t in self.tm.tasks.values():
            t.cancel.set()
        for t in self.tm.tasks.values():
            if t.thread:
                t.thread.join(10)
            if t.status not in ("done", "failed"):
                t.data["status"] = "running"          # процесс убит посреди работы — на диске остаётся «выполняется»
                t.save()

    async def call(self, cmd, timeout=60, **a):
        if cmd == "task_create":
            return self.tm.create(a["title"], a["goal"], start=a.get("start", True)).public()
        if cmd == "task_resume":
            return self.tm.start(a["id"]).public()
        if cmd == "tasks_list":
            return self.tm.list()
        if cmd == "task_answer":
            return self.tm.answer(a["id"], a["text"]).public()
        raise RuntimeError(cmd)


sc = next(s for s in json.loads((ROOT / "data/exam/scenarios.json").read_text(encoding="utf-8"))["scenarios"] if s["id"] == "big_b11_restart")
sc = dict(sc, big=dict(sc["big"], restart_after=3, timeout=90))
fc = FakeCore()
res = {"id": sc["id"], "group": sc["group"], "title": sc["title"], "steps": [], "checks": []}
st = asyncio.run(exam.run_big(fc, sc, res, time.time(), TMP / "work", lambda x: None))
ok(fc.restarts == 1 and all(c["ok"] for c in res["checks"]),
   f"Б11 целиком: перезапуск после 3-го шага, задача продолжила и сдала: {[(c['name'][:40], c['detail'][:80]) for c in res['checks'] if not c['ok']]}")
ok(res.get("metrics", {}).get("steps", 0) >= 10 and res["metrics"]["tok_in"] > 0 and res["metrics"]["cache"] is not None,
   f"метрики сценария: {res.get('metrics')}")
ok((TMP / "work" / "big" / "big_b11_restart.json").is_file()
   and not any(p.name == "big_b11_restart.json" for p in Path(fc.tm.list()[0]["dir"]).rglob("*")), "ответы экзамена — у экзамена, не в папке задачи")
# браузер экзамена у исполнителя: ставится один раз в его папку; не вышло — экзамен идёт, повтор не раньше чем через неделю
ej = cloudrunner.ExamJob({"id": "x", "big": True})
ej.home = TMP / "runner_exam"
ej.home.mkdir()
ej.post = lambda *a, **k: None
fake = TMP / "fakepy.sh"
fake.write_text("#!/bin/sh\necho \"$@\" >> \"$(dirname \"$0\")/pw-calls.txt\"\nexit ${FAKE_RC:-1}\n")
fake.chmod(0o755)
w = ej.browser(fake)
calls = (TMP / "pw-calls.txt").read_text().splitlines()
ok(w == ej.home / "pw-browsers" and (ej.home / "pw-browsers.tried").exists() and not (w / ".ok").exists()
   and calls == ["-m playwright install --only-shell chromium", "-m playwright install chromium"],
   f"Chromium не скачался — экзамен идёт без него, попытка отмечена ({calls})")
ej.browser(fake)
ok(len((TMP / "pw-calls.txt").read_text().splitlines()) == 2, "повторно в ту же неделю — не качаем")
(ej.home / "pw-browsers.tried").unlink()
os.environ["FAKE_RC"] = "0"
w = ej.browser(fake)
ok((w / ".ok").exists(), "скачался — отмечен, дальше без попыток")
os.environ.pop("FAKE_RC")
shutil.rmtree(TMP, ignore_errors=True)
print("ИТОГ:", "всё прошло" if not FAILS else f"провалов {len(FAILS)}")
sys.exit(1 if FAILS else 0)
