"""Творческие просьбы смелее (отзыв 17.10: «экзамен сдаётся слабовато потому, что креатив в модели не высокий, а в такого
рода задачах он должен быть выше»). Стихи, сказки, поздравления, тосты, «придумай» — температура не ниже 0.95 (для дел
и фактов остаётся из профиля, 0.7); стихам — ремесло рифмы: пары рифм по ударному слогу подбираются заранее.
Музыка («включи песню») и обычные вопросы — без изменений. Компьютер и телефон одинаково."""
import os, re, shutil, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import llm  # noqa: E402
CASES = {"Напиши четверостишие про осень с настоящей рифмой.": (0.95, True), "Сочини сказку для дочки про ёжика": (0.95, False),
         "Поздравь маму с днём рождения": (0.95, False), "Придумай название для кофейни": (0.95, False),
         "Включи песню Цоя": (0.7, False), "Который час?": (0.7, False), "Напомни завтра в 9 про отчёт": (0.7, False),
         "Напиши песню про кота": (0.95, True)}
got = {t: (llm.creative_temp(t, 0.7), bool(llm.POEM_ASK.search(t))) for t in CASES}
ok(got == CASES, f"компьютер: творческое — 0.95, стихи — с ремеслом рифмы, дела и музыка — как было: {[t for t in CASES if got[t] != CASES[t]]}")
ok(llm.creative_temp("Напиши стих", 1.1) == 1.1, "температуру выше заданной человеком не снижаем")
ok(llm.creative_temp("Напиши стих", 0.3) == 0.3 and llm.creative_temp("Напиши стих", None) == 0.95 and llm.creative_temp("Который час?", None) == 0.7,
   "№311: свою температуру в профиле (0,3) творческая просьба не поднимает; без неё — 0,95")
src = (ROOT / "core/engine_answer.py").read_text(encoding="utf-8")
ok("prof = dict(prof, temperature=temp)" in src and "system += POEM_NOTE" in src, "компьютер: ответ берёт эту температуру и ремесло рифмы")

from playwright.sync_api import sync_playwright  # noqa: E402
www = Path(tempfile.mkdtemp()) / "www"
shutil.copytree(ROOT / "android/assets/www", www)
for x in ("entities.js", "speechnorm.js"):
    shutil.copy(ROOT / "ui/assets" / x, www / x)
shutil.copytree(ROOT / "ui/assets/live", www / "live", dirs_exist_ok=True)
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                capture_output=True, text=True, check=True).stdout, encoding="utf-8")
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(800)
    r = pg.evaluate("""(cases) => Object.keys(cases).map(t => [CREATIVE_ASK.test(t) ? 0.95 : 0.7, POEM_ASK.test(t)])""", CASES)
    ok([tuple(x) for x in r] == list(CASES.values()), f"телефон: те же правила, что на компьютере: {r}")
    t = pg.evaluate("() => { S.llm.temperature = 0.7; creativeTurn = true; const a = llmTemp(); S.llm.temperature = 0.3; const b = llmTemp(); creativeTurn = false; return [a, b, llmTemp()]; }")
    ok(t == [0.95, 0.3, 0.3], f"телефон: творческий ход — 0.95, своя 0,3 главнее (№311): {t}")
    ok(not errs, f"без ошибок на странице: {errs[:2]}")
    b.close()
app = (ROOT / "android/assets/www/app.js").read_text(encoding="utf-8")
ok(app.count("temperature: llmTemp()") == 2 and "POEM_ASK.test(text) ? POEM_NOTE" in app and "creativeTurn = !opts.hidden && CREATIVE_ASK.test(text)" in app,
   "телефон: запрос к модели берёт llmTemp(), стихам — ремесло рифмы")
print("\nИТОГ:", "всё прошло" if not fails else f"не прошло {len(fails)}")
sys.exit(1 if fails else 0)
