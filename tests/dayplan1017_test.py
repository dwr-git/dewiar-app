"""План дня и отметки — без модели (отзыв 17.10: «Говорит, что записала "Запланируй на сегодня: в 13 позвонить в банк,
в 16 тренировка, в 19 купить подарок маме" — открываю "Дела" на телефоне, а там ничего не меняется… видимо куда-то ещё
пишет, может в Google календарь»). «Запланируй» не узнавала ни одна проверка, и модель писала дела в календарь.
Теперь план дня разбирает ядро: на каждое дело — напоминание (видно в «Делах»), прошедшее время — на завтра (и это
сказано), дело без времени — на 20:00. «Я позвонил в банк» закрывает дело из плана и считается в достижениях; без
«отметь / готово» — только если это и правда дело из плана («я позвонил маме» не закрывает «позвонить в банк»).
Компьютер (core/dayplan.py, engine_tools._plan_cmd/_mark_cmd) и телефон (planQuick/doneQuick) одинаково."""
import srctext  # noqa: E402 — текст исходника вместе с частями (tests/srctext.py)
import os, shutil, subprocess, sys, tempfile, types
from datetime import datetime, timedelta
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ["DEWIAR_STATE_DIR"] = str(tmp / "st"); os.environ["DEWIAR_CONFIG_DIR"] = str(tmp / "cfg")
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import dayplan as P  # noqa: E402
import done as D  # noqa: E402

ASK = "Запланируй на сегодня: в 13 позвонить в банк, в 16 тренировка, в 19 купить подарок маме"
MORNING, NIGHT = datetime(2026, 10, 17, 9, 0), datetime(2026, 10, 17, 22, 38)
p = P.parse_plan(ASK, MORNING)
ok(p and [(x["text"], f"{x['at']:%d %H:%M}") for x in p["items"]] == [("Позвонить в банк", "17 13:00"), ("Тренировка", "17 16:00"),
                                                                      ("Купить подарок маме", "17 19:00")],
   f"утром: три дела на сегодня со своим временем: {p and p['items']}")
ok(P.plan_say(p, MORNING) == "Записал план на сегодня: 13:00 — позвонить в банк; 16:00 — тренировка; 19:00 — купить подарок маме. "
   "Сделаете — скажите, и я отмечу.", f"ответ — сам план: {P.plan_say(p, MORNING)}")
p = P.parse_plan(ASK, NIGHT)
ok(p and all(x["at"].day == 18 and x["moved"] for x in p["items"]) and P.plan_say(p, NIGHT).startswith("Сегодня это время уже прошло — записал план на завтра"),
   f"в 22:38 время прошло — на завтра, и это сказано: {P.plan_say(p, NIGHT) if p else None}")
CASES = {
    "План на сегодня: в 13:00 позвонить в банк, в 16 тренировка и в 19 купить подарок маме": 3,
    "Лира, запланируй мне дела на сегодня: позвонить в банк, тренировка, купить подарок маме": 3,
    "Мои дела на завтра: в 12 обед с Олей, в 3 забрать детей": 2,
    "Напомни в 13 позвонить в банк, в 16 тренировка": 2,
    "добавь в план в 18 купить хлеб": 1,
    "запланируй на завтра в 13 позвонить в банк в 16 тренировка в 19 купить подарок маме": 3,   # как пишет распознавание: без запятых
    "запланируй позвонить в банк в 13 тренировка в 16": 2,
    "Напомни в 13 позвонить в банк": 0,                 # одно напоминание — обычный путь
    "Запланируй встречу с Иваном в 15": 0,              # встреча — календарь
    "запланируй отпуск": 0,
    "Что у меня запланировано на сегодня?": 0,
}
got = {q: len((P.parse_plan(q, MORNING) or {"items": []})["items"]) for q in CASES}
ok(got == CASES, f"что считается планом дня, а что нет: {[q for q in CASES if got[q] != CASES[q]]}")
p = P.parse_plan("Мои дела на завтра: в 12 обед с Олей, в 3 забрать детей", MORNING)
ok([(x["text"], x["at"].hour) for x in p["items"]] == [("Обед с Олей", 12), ("Забрать детей", 15)], f"«в 3» в плане — 15:00, имена с большой: {p['items']}")
p = P.parse_plan("Лира, запланируй мне дела на сегодня: позвонить в банк, тренировка, купить подарок маме", MORNING)
ok(all(x["at"].hour == 20 for x in p["items"]) and "без времени — напомню в 20:00" in P.plan_say(p, MORNING) and "20:00 —" not in P.plan_say(p, MORNING),
   f"дела без времени — вечером в 20:00 (и не «20:00 — …» у каждого): {P.plan_say(p, MORNING)}")

DONE = {"Я позвонил в банк": (["Позвонил в банк"], False), "Готово, купил подарок маме": (["Купил подарок маме"], True),
        "Отметь тренировку": (["Тренировку"], True), "Тренировка — готово": (["Тренировка"], True),
        "Лира, я позвонила в банк": (["Позвонила в банк"], False),
        "Я сходил на тренировку и купил подарок маме": (["Сходил на тренировку", "Купил подарок маме"], False),
        "Я не позвонил в банк": None, "Я позвонил в банк?": None, "Я вчера позвонил в банк": None, "что ты сделала": None,
        "Отметь в календаре день рождения": None, "Сними отметку с тренировки": None, "Хочу позвонить в банк": None}
got = {q: (lambda d: d and (d["items"], d["explicit"]))(P.parse_done(q)) for q in DONE}
ok(got == DONE, f"что считается отметкой: {[(q, got[q]) for q in DONE if got[q] != DONE[q]]}")

now = datetime.now().replace(microsecond=0)
rem = [{"id": "r1", "text": "Позвонить в банк", "at": (now + timedelta(hours=2)).isoformat()},
       {"id": "r2", "text": "Тренировка", "at": (now + timedelta(hours=26)).isoformat()},
       {"id": "r3", "text": "Сходить на тренировку", "at": (now + timedelta(hours=60)).isoformat()}]
ok(D.reminder_match("Позвонил в банк", rem)["id"] == "r1" and D.reminder_match("Позвонил маме", rem) is None,
   "«позвонил маме» не закрывает «позвонить в банк» (общий только глагол)")
ok(D.reminder_match("Сделал тренировку", rem) is None and D.reminder_match("Сделал тренировку", rem, ahead=True)["id"] == "r2",
   "дело из плана на завтра (в пределах 36 часов) — тоже закрывается: сделано раньше")

# ---------- ядро компьютера: _plan_cmd / _mark_cmd с настоящими напоминаниями и журналом ----------
import tools  # noqa: E402
import engine_tools as ET  # noqa: E402
said, events = [], []
eng = types.SimpleNamespace(reminders=tools.Reminders(lambda x: None), done=D.Done(tmp / "done.json"),
                            emit=lambda ev, **k: events.append((ev, k)), _reminder_public=lambda x: x,
                            _say_quick=lambda msg, text, via=None, **k: said.append((msg, k.get("acts"))))
ok(ET.ToolsMixin._plan_cmd(eng, "Запланируй на завтра: в 13 позвонить в банк, в 16 тренировка, в 19 купить подарок маме")
   and [x["text"] for x in eng.reminders.items] == ["Позвонить в банк", "Тренировка", "Купить подарок маме"]
   and said[-1][1] == ["set_reminder"] * 3 and said[-1][0].startswith("Записал план на завтра: 13:00"),
   f"компьютер: «запланируй…» — три напоминания сразу, без модели: {said[-1]}")
ok(not ET.ToolsMixin._plan_cmd(eng, "Запланируй встречу с Иваном в календаре на 15"), "встреча в календаре — модели")
for x in list(eng.reminders.items):
    eng.reminders.remove(x["id"])
for h, t in ((2, "Позвонить в банк"), (3, "Тренировка"), (4, "Купить подарок маме")):
    eng.reminders.add(now + timedelta(hours=h), t)
ok(not ET.ToolsMixin._mark_cmd(eng, "Я позвонил маме"), "«я позвонил маме» — не дело из плана: решает модель")
ok(ET.ToolsMixin._mark_cmd(eng, "Я позвонил в банк") and [x["text"] for x in eng.reminders.items] == ["Тренировка", "Купить подарок маме"]
   and eng.done.stats()["today"] == 1 and said[-1] == ("Отметил «Позвонить в банк». Сегодня это первое дело.", ["mark_done"]),
   f"«я позвонил в банк» — дело закрыто и отмечено: {said[-1]}")
ok(ET.ToolsMixin._mark_cmd(eng, "Отметь тренировку") and eng.done.stats()["today"] == 2, "«отметь тренировку» — второе")
ET.ToolsMixin._mark_cmd(eng, "Готово, купил подарок маме")
ev = [k for e, k in events if e == "done"][-1]
ok(not eng.reminders.items and "новое достижение «Тройка»" in said[-1][0] and [a["name"] for a in ev["fresh"]] == ["Тройка"]
   and ev["added"] == ["Купить подарок маме"], f"третье дело — значок «Тройка», студия получает его в событии: {said[-1][0]}")
src = srctext.text(ROOT, "core/engine_answer.py")
ok(src.index("self._plan_cmd(text, via)") < src.index("parse_when(text)") and "self._mark_cmd(text, via)" in src, "план и отметки — до модели и до разбора «напомни»")
brain = (ROOT / "ui/studio/brain.js").read_text(encoding="utf-8")
ok('if ((e.added || []).length) doneCelebrate(e);' in brain and brain.count("doneCelebrate(") == 2,
   "студия празднует любую отметку (и голосом) — один раз")
ok("это дела, не календарь" in (ROOT / "core/done.py").read_text(encoding="utf-8"), "в подсказке модели: план дня — не календарь")

# ---------- телефон: то же ----------
from playwright.sync_api import sync_playwright  # noqa: E402
www = tmp / "www"
shutil.copytree(ROOT / "android/assets/www", www)
for x in ("entities.js", "speechnorm.js"):
    shutil.copy(ROOT / "ui/assets" / x, www / x)
shutil.copytree(ROOT / "ui/assets/live", www / "live", dirs_exist_ok=True)
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                capture_output=True, text=True, check=True).stdout, encoding="utf-8")
with sync_playwright() as pw:
    b = pw.chromium.launch(); pg = b.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(800)
    r = pg.evaluate("""(a) => { const [ask, m, n] = a; const P = (t) => planParse(t, new Date(t0(m))), t0 = (s) => s;
        const p1 = planParse(ask, new Date(m)), p2 = planParse(ask, new Date(n));
        return { morning: p1 && p1.items.map(x => [x.text, x.at.getDate(), x.at.getHours()]), say: p1 && planSay(p1, new Date(m)),
                 night: p2 && planSay(p2, new Date(n)), nightDays: p2 && p2.items.map(x => x.at.getDate()) }; }""",
                    [ASK, "2026-10-17T09:00:00", "2026-10-17T22:38:00"])
    ok(r["morning"] == [["Позвонить в банк", 17, 13], ["Тренировка", 17, 16], ["Купить подарок маме", 17, 19]] and r["say"] == P.plan_say(P.parse_plan(ASK, MORNING), MORNING),
       f"телефон: тот же план и те же слова, что на компьютере: {r['morning']} / {r['say']}")
    ok(r["nightDays"] == [18, 18, 18] and r["night"].startswith("Сегодня это время уже прошло — записал план на завтра"), f"телефон: ночью — на завтра: {r['night']}")
    got = pg.evaluate("(qs) => qs.map(q => { const p = planParse(q, new Date('2026-10-17T09:00:00')); return p ? p.items.length : 0; })", list(CASES))
    ok(dict(zip(CASES, got)) == CASES, f"телефон: что считается планом: {[q for q, n in zip(CASES, got) if CASES[q] != n]}")
    got = pg.evaluate("(qs) => qs.map(q => { const d = doneParse(q); return d ? [d.items, d.explicit] : null; })", list(DONE))
    ok([tuple(x) if x else None for x in got] == [tuple(v) if v else None for v in DONE.values()],
       f"телефон: что считается отметкой: {[(q, g) for q, g in zip(DONE, got) if (tuple(g) if g else None) != (tuple(DONE[q]) if DONE[q] else None)]}")
    r = pg.evaluate("""async () => {
        const out = {}; const p = await quick("Запланируй на завтра: в 13 позвонить в банк, в 16 тренировка, в 19 купить подарок маме");
        out.plan = p && p.say; out.alarms = JSON.parse(D.alarms()).map(x => x.title);
        JSON.parse(D.alarms()).forEach(x => D.alarmCancel(x.id));
        [[2, "Позвонить в банк"], [3, "Тренировка"], [4, "Купить подарок маме"]].forEach(([h, t]) => addAlarm(t, new Date(Date.now() + h * 3600e3), "reminder", ""));
        out.mama = await quick("Я позвонил маме");
        out.a = (await quick("Я позвонил в банк")).say; out.b = (await quick("Отметь тренировку")).say; out.c = (await quick("Готово, купил подарок маме")).say;
        out.left = JSON.parse(D.alarms()).length; out.today = doneStats().today; out.card = !!document.getElementById("achc");
        return out; }""")
    ok(r["plan"] and r["plan"].startswith("Записал план на завтра: 13:00") and r["alarms"] == ["Позвонить в банк", "Тренировка", "Купить подарок маме"],
       f"телефон: «запланируй…» — три дела в «Делах» сразу: {r['plan']} {r['alarms']}")
    ok(r["mama"] is None or "Позвонил маме" not in str(r["mama"]), f"телефон: «я позвонил маме» — не дело из плана, не отмечаем сами: {r['mama']}")
    ok(r["a"] == "Отметил «Позвонить в банк». Сегодня это первое дело." and r["left"] == 0 and r["today"] == 3
       and "новое достижение «Тройка»" in r["c"] and r["card"], f"телефон: три отметки — дела закрыты, «Тройка» с карточкой: {r}")
    ok(not errs, f"без ошибок на странице: {errs[:2]}")
    b.close()
shutil.rmtree(tmp, ignore_errors=True)                # не оставлять копии страниц в /tmp
print("\nИТОГ:", "всё прошло" if not fails else f"не прошло {len(fails)}")
sys.exit(1 if fails else 0)
