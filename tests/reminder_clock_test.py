"""Напоминания не путают время (16.10: в 15:57 на «сколько времени» модель ответила «14:17» — повторила своё прошлое
время из разговора). Для напоминаний это опаснее всего: «через 20 минут» модель посчитала бы от старого времени.
Проверяем: «через N минут / полчаса / часов» — время считают компьютер и телефон по своим часам, даже если модель
передала другое; верное время модели и повторы («каждые 2 часа») не трогаются; телефон просит у модели when словами,
а не ISO; в подсказке обеих — «время из прошлых реплик устарело»."""
import srctext  # noqa: E402 — текст исходника вместе с частями (tests/srctext.py)
import os, re, shutil, subprocess, sys, tempfile
from datetime import datetime, timedelta
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import engine_tools as ET  # noqa: E402


class Eng(ET.ToolsMixin):
    pass


e = Eng()
now = datetime.now()
stale = now - timedelta(minutes=100) + timedelta(minutes=20)        # модель считала от времени на 100 минут раньше
asked = "Через 20 минут напомни выключить духовку, вот скрин\n\nВложения:\n[Картинка «a.png» — сохранена: Входящие/a.png]"
g = e._reminder_time_guard(asked, {"text": "Выключить духовку", "at": f"{stale:%Y-%m-%d %H:%M}"})
got = datetime.strptime(g["at"], "%Y-%m-%d %H:%M")
ok(abs((got - (now + timedelta(minutes=20))).total_seconds()) < 90 and g["text"] == "Выключить духовку",
   f"компьютер: «через 20 минут» — от настоящих часов, а не от времени модели: {g['at']} (модель: {stale:%H:%M})")
good = {"text": "Позвонить маме", "in_minutes": 30}
ok(e._reminder_time_guard("через полчаса напомни позвонить маме", good) == good, "верное время модели не трогаем")
ok(e._reminder_time_guard("напомни каждые 2 часа пить воду", {"text": "Пить воду", "when": "каждые 2 часа"})["when"] == "каждые 2 часа",
   "повторы («каждые 2 часа») — не сюда")
ok(e._reminder_time_guard("напомни завтра в 9 про отчёт", {"text": "Отчёт", "when": "завтра в 9"}) == {"text": "Отчёт", "when": "завтра в 9"},
   "без «через …» — разбирает when.parse, как и было")
src = srctext.text(ROOT, "core/engine_answer.py")
ok("прошлых реплик разговора устарели" in src, "компьютер: в подсказке — время из прошлых реплик устарело")

# день недели: «в пятницу в 15» в пятницу в 16:30 — следующая пятница, а не «не понял» (16.10: так напоминание с
# картинкой уходило модели и могло встать не туда); в 10:00 — сегодня
from when import parse  # noqa: E402
fri = datetime(2026, 10, 16, 16, 30)
got = {q: (parse(q, fri) or {}).get("at") for q in ("напомни в пятницу в 15:00 показать Саше", "напомни в пятницу в 18:00 позвонить",
                                                    "напомни в четверг в 9 отчёт", "напомни в субботу в 10 рынок")}
ok(list(got.values()) == [datetime(2026, 10, 23, 15, 0), datetime(2026, 10, 16, 18, 0), datetime(2026, 10, 22, 9, 0), datetime(2026, 10, 17, 10, 0)],
   f"компьютер: день недели — ближайший такой день с этим временем впереди: {[f'{v:%d.%m %H:%M}' if v else None for v in got.values()]}")
ok((parse("напомни в пятницу в 15:00 показать", datetime(2026, 10, 16, 10, 0)) or {}).get("at") == datetime(2026, 10, 16, 15, 0)
   and parse("напомни сегодня в 15 показать", fri) is None, "в пятницу утром «в пятницу в 15» — сегодня; «сегодня в 15» в 16:30 — уточнит модель")

# ---------- телефон ----------
from playwright.sync_api import sync_playwright  # noqa: E402
www = Path(tempfile.mkdtemp()) / "www"
shutil.copytree(ROOT / "android/assets/www", www)
for x in ("entities.js", "speechnorm.js"):
    shutil.copy(ROOT / "ui/assets" / x, www / x)
shutil.copytree(ROOT / "ui/assets/live", www / "live", dirs_exist_ok=True)
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                capture_output=True, text=True, check=True).stdout, encoding="utf-8")
errs = []
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(); pg.on("pageerror", lambda x: errs.append(str(x)))
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(800)
    r = pg.evaluate("""async () => {
        const stale = new Date(Date.now() - 80 * 60000), iso = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
        turnAtt = []; turnAsk = "Через 20 минут напомни выключить духовку";
        const t1 = await runTool("set_reminder", { text: "Выключить духовку", at: iso(stale) });
        const a1 = JSON.parse(D.alarms() || "[]").find(x => x.title === "Выключить духовку");
        turnAsk = "Напомни в пятницу в 18:30 забрать посылку";
        await runTool("set_reminder", { text: "Забрать посылку", when: "в пятницу в 18:30" });
        const a2 = JSON.parse(D.alarms() || "[]").find(x => x.title === "Забрать посылку");
        return [Math.round((a1.at - Date.now()) / 60000), t1, new Date(a2.at).getHours() + ":" + pad(new Date(a2.at).getMinutes()), new Date(a2.at).getDay()];
    }""")
    ok(r[0] in (19, 20) and "Поставлено" in r[1], f"телефон: «через 20 минут» — от часов телефона, а не от времени модели: через {r[0]} мин")
    ok(r[2] == "18:30" and r[3] == 5, f"телефон: when словами — телефон сам считает дату и время: {r[2]}, день {r[3]}")
    d = pg.evaluate("""() => { const now = new Date(), wd = ["воскресенье", "понедельник", "вторник", "среду", "четверг", "пятницу", "субботу"][now.getDay()];
        const past = new Date(now.getTime() - 3600e3), ahead = new Date(now.getTime() + 3600e3);
        if (past.getDate() !== now.getDate() || ahead.getDate() !== now.getDate()) return null;      // у полуночи не проверяем
        const days = (h) => { const w = parseWhen(`напомни в ${wd} в ${h.getHours()}:${pad(h.getMinutes())} дело`); return Math.round((new Date(w.at).setHours(0, 0, 0, 0) - new Date(now).setHours(0, 0, 0, 0)) / 864e5); };
        return [days(past), days(ahead)]; }""")
    ok(d is None or d == [7, 0], f"телефон: «в {{сегодняшний день недели}}» — сегодня, если час впереди, иначе через неделю: {d}")
    ok(not errs, f"без ошибок на странице: {errs[:3]}")
    b.close()
app = (ROOT / "android/assets/www/app.js").read_text(encoding="utf-8")
ok("посчитай сам от текущего времени" not in app and "время посчитает телефон" in app and "прошлых реплик разговора устарели" in app,
   "телефон: модель не считает время сама — передаёт слова; в подсказке — время из прошлых реплик устарело")

print("\nИТОГ:", "всё прошло" if not fails else f"не прошло {len(fails)}")
sys.exit(1 if fails else 0)
