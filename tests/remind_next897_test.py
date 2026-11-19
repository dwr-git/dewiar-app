"""№897 (19.11, владелец): «В следующий понедельник в 13 часов напомни связаться с Артёмом» — Лира ответила «напомню завтра
в 13:00» и поставила на пятницу. Разбор дня ждал «в» прямо перед днём недели: «в следующий понедельник» не узнавался,
оставалось только «в 13 часов», а 13:00 уже прошло — завтра. Теперь на компьютере (when.py) и телефоне (parseWhen)
понимаются «следующий / ближайший / этот понедельник», «на понедельник», «в пятницу на следующей неделе»; а если в «о чём
напомнить» остались слова о дне, которые разбор не понял, быстрый путь не угадывает — фразу решает модель."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


from when import parse  # noqa: E402

NOW = datetime(2026, 11, 19, 14, 39)                      # четверг, как в отчёте
CASES = [   # фраза, (день, месяц, час), о чём
    ("В следующий понедельник в 13 часов напомни связаться с Артемом Бородиным", (23, 11, 13), "Связаться с Артемом Бородиным"),
    ("напомни в следующий понедельник в 13 связаться с Артёмом", (23, 11, 13), "Связаться с Артёмом"),
    ("напомни в понедельник в 13 связаться с Артёмом", (23, 11, 13), "Связаться с Артёмом"),
    ("напомни в следующий четверг в 10 позвонить", (26, 11, 10), "Позвонить"),
    ("напомни в пятницу на следующей неделе в 9 оплатить счёт", (27, 11, 9), "Оплатить счёт"),
    ("напомни на следующей неделе в среду в 9 оплатить счёт", (25, 11, 9), "Оплатить счёт"),
    ("напомни в эту субботу в 12 купить цветы", (21, 11, 12), "Купить цветы"),
    ("напомни в ближайшую пятницу в 18 забрать посылку", (20, 11, 18), "Забрать посылку"),
]
# --- компьютер ---
for q, (d, mo, h), what in CASES:
    r = parse(q, NOW)
    ok(r and (r["at"].day, r["at"].month, r["at"].hour) == (d, mo, h) and r["text"] == what,
       f"компьютер: «{q}» → {r and r['at']:%d.%m %H:%M}, «{r and r['text']}»" if r else f"компьютер: «{q}» → не понял")
ok(parse("напомни через неделю в понедельник позвонить", NOW) is None, "непонятые слова о дне — быстрый путь не угадывает (решает модель)")
ok(parse("напомни в 21 подготовить завтрак", NOW) is not None and parse("напомни в 21 подготовить завтрак", NOW)["text"] == "Подготовить завтрак",
   "«завтрак» — не «завтра»: ставится сразу")
r = parse("напомни завтра в 13 купить хлеб", NOW)
ok(r and r["at"] == datetime(2026, 11, 20, 13, 0), "«завтра» — как было")
# владелец 19.11: «Завтра в 10 часов напомни "ЗАВТРА СКАЧАТЬ…"» — «завтра» в кавычках принималось за непонятый день, фраза
# уходила модели, а та спрашивала «Выполнить?». В кавычках — сам текст напоминания, дословно
r = parse('Завтра в 10 часов напомни "ЗАВТРА СКАЧАТЬ СЕБЕ НА НОУТ VLLM!!!"', NOW)
ok(r and r["at"] == datetime(2026, 11, 20, 10, 0) and r["text"] == "ЗАВТРА СКАЧАТЬ СЕБЕ НА НОУТ VLLM!!!",
   f"слова о дне в кавычках — текст, ставится сразу и дословно: {r and (r['at'], r['text'])}")
r = parse("напомни завтра в 10 «позвонить в пятницу Ане»", NOW)
ok(r and r["at"] == datetime(2026, 11, 20, 10, 0) and "пятницу" in r["text"], f"«…в пятницу…» в кавычках — тоже текст: {r and r['at']}")
ok(parse("напомни в 13 позвонить через неделю в понедельник", NOW) is None, "вне кавычек — по-прежнему решает модель")
r = parse("каждый понедельник в 9 напоминай про планёрку", NOW)
ok(r and r["repeat"] and r["repeat"].get("days") == [0], "«каждый понедельник» — повтор, как было")

# --- телефон ---
tmp = Path(tempfile.mkdtemp()); www = tmp / "www"
subprocess.run(["bash", str(ROOT / "android/tools/www_assemble.sh"), str(www)], check=True, capture_output=True)
errs = []
with sync_playwright() as p:
    b = p.chromium.launch(); ctx = b.new_context(viewport={"width": 400, "height": 820}, timezone_id="Europe/Minsk")
    pg = ctx.new_page(); pg.on("pageerror", lambda x: errs.append(str(x)))
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(1000)
    JNOW = "new Date(2026, 10, 19, 14, 39)"

    def pw(t):
        return pg.evaluate(f"""() => {{ const w = parseWhen({json.dumps(t)}, {JNOW}); return w && {{ d: w.at.getDate(), mo: w.at.getMonth() + 1,
          h: w.at.getHours(), rest: remindWhat(w.rest), left: LEFT_DAY.test(remindWhat(w.rest)) }}; }}""")
    for q, (d, mo, h), what in CASES:
        t = q.lower().replace("ё", "е")
        t = t.replace("напомни ", "", 1) if t.startswith("напомни ") else t
        w = pw(t)
        ok(w and (w["d"], w["mo"], w["h"]) == (d, mo, h) and not w["left"], f"телефон: «{t}» → {w}")
    w = pw("в 9 позвонить в пятницу")
    ok(w and (w["d"], w["h"]) == (20, 9) and w["rest"] == "позвонить", f"телефон: «в пятницу» — как было: {w}")
    w = pw("через неделю в понедельник позвонить")
    ok(w is None or w["left"] or (w["d"], w["mo"]) == (23, 11), f"телефон: «через неделю в понедельник» — не завтра: {w}")
    ok(pg.evaluate("LEFT_DAY.test('позвонить через неделю')") and not pg.evaluate("LEFT_DAY.test('подготовить завтрак')"),
       "телефон: проверка непонятых слов о дне (и «завтрак» — не день)")
    # быстрый путь: непонятые слова о дне — null (решает модель)
    r = pg.evaluate("async () => { const n = JSON.parse(D.alarms() || '[]').length; const q = await quick('напомни в 13 позвонить через неделю в понедельник'); return [q, JSON.parse(D.alarms() || '[]').length - n]; }")
    ok(r[0] is None and r[1] == 0, f"телефон, быстрый путь: не понял день — не ставит, отдаёт модели: {r}")
    r = pg.evaluate("async () => { const q = await quick('напомни завтра в 10 «позвонить в пятницу ане»'); return q && q.say; }")
    ok(r and "пятницу" in r, f"телефон, быстрый путь: день в кавычках — текст, ставит сразу: {r}")
    # модель передала when «в следующий понедельник в 13:00» — инструмент ставит на понедельник
    r = pg.evaluate("""async () => { turnAsk = 'В следующий понедельник в 13 часов напомни связаться с Артемом';
      const t = await runTool('set_reminder', { text: 'Связаться с Артемом', when: 'в следующий понедельник в 13:00' });
      const x = JSON.parse(D.alarms() || '[]').find(y => y.title === 'Связаться с Артемом'); const a = new Date(x.at);
      return [t, a.getDay(), a.getHours(), Math.round((a - Date.now()) / 864e5)]; }""")
    ok(r[1] == 1 and r[2] == 13 and r[3] >= 1, f"телефон, инструмент: when «в следующий понедельник» — понедельник 13:00: {r}")
    b.close()
ok(not errs, f"без ошибок на странице: {errs[:3]}")
shutil.rmtree(tmp, ignore_errors=True)
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
