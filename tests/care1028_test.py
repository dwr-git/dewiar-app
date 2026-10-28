"""«Заботливая память» (0.61; план «Лира — любимица всех»: «сама вспоминает, что вам важно — „как прошёл врач?“»).
Между делом сказано «завтра иду к врачу», «в пятницу собеседование», «мама приезжает в субботу» — Лира запоминает с датой;
событие прошло — один раз тепло спрашивает, как прошло: в приветствии (вернулись к компьютеру) или в конце ответа.
Вопросы, просьбы о напоминании, погода, чужие дела — не события. Компьютер (care.py) и телефон (app.js)."""
import datetime as dt, json, os, shutil, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import care  # noqa: E402
import presence  # noqa: E402
now = dt.datetime(2026, 10, 28, 12, 0)                     # среда
yes = {"Завтра иду к врачу": dt.date(2026, 10, 29), "В пятницу у меня собеседование в Яндексе": dt.date(2026, 10, 30),
       "Мама приезжает в субботу": dt.date(2026, 10, 31), "сдаю экзамен 3 ноября": dt.date(2026, 11, 3),
       "Записалась к стоматологу на четверг": dt.date(2026, 10, 29), "У сына завтра соревнования по плаванию": dt.date(2026, 10, 29)}
for t, d in yes.items():
    e = care.detect(t, now)
    ok(e and e["day"] == d, f"событие: «{t}» → {e and e['day']}")
for t in ("Напомни завтра позвонить врачу", "Какая погода завтра?", "Врач сказал пить больше воды", "Завтра встреча с подрядчиком",
          "Когда у меня собеседование?"):
    ok(care.detect(t, now) is None, f"не событие: «{t}»")
tmp = Path(tempfile.mkdtemp())
clock = [now]
c = care.Care(tmp / "care.json", now=lambda: clock[0])
ok(c.note("Завтра иду к врачу") and c.note("Завтра иду к врачу") is None and len(c.public()) == 1, "запомнила один раз")
ok(c.context() == ("", []), "до события — не спрашивает")
clock[0] = dt.datetime(2026, 10, 29, 19, 0)
line, ids = c.context()
ok("сегодня" in line and "как прошло" in line and "к врачу" in line, f"вечером в тот же день — спросить: {line[:80]}")
clock[0] = dt.datetime(2026, 10, 30, 9, 0)
line, ids = c.context()
ok("вчера" in line, "на следующий день — «вчера»")
c.mark(ids)
ok(c.context() == ("", []) and c.public() == [], "спросила — больше не спрашивает")
c2 = care.Care(tmp / "care.json", now=lambda: clock[0])
ok(c2.context() == ("", []), "и после перезапуска")
c.note("В пятницу у меня собеседование")
clock[0] = dt.datetime(2026, 11, 8, 10, 0)
ok(c.context() == ("", []), "прошло больше 5 дней — уже не спрашивает")
p = presence.plan(4 * 3600, dt.datetime(2026, 10, 30, 10), [], [], dt.datetime(2026, 10, 30, 9), now=dt.datetime(2026, 10, 30, 14), care="[Заботливая память] …")
ok(p and p["kind"] == "back" and "один тёплый вопрос" in presence.prompt(p), "вернулись к компьютеру — в приветствии можно один тёплый вопрос")
eng = (ROOT / "core/engine_answer.py").read_text(encoding="utf-8")
ok("care_context(text, turn)" in eng, "в ответах — тоже (care_context)")

# телефон
from playwright.sync_api import sync_playwright  # noqa: E402
w = tmp / "www"
subprocess.run(["bash", str(ROOT / "android/tools/www_assemble.sh"), str(w)], check=True, capture_output=True)
seen = []


def llm_route(route):
    req = route.request
    if req.method == "OPTIONS":
        return route.fulfill(status=204, headers={"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*", "Access-Control-Allow-Methods": "*"})
    seen.append(json.loads(req.post_data or "{}").get("messages") or [])
    d = {"choices": [{"delta": {"content": "Хорошо!"}}]}
    route.fulfill(status=200, body=f"data: {json.dumps(d, ensure_ascii=False)}\n\ndata: [DONE]\n\n", headers={"Access-Control-Allow-Origin": "*", "Content-Type": "text/event-stream"})


with sync_playwright() as pw:
    b = pw.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 393, "height": 852}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route("http://127.0.0.1:9/**", llm_route)
    pg.goto((w / "index.html").as_uri()); pg.wait_for_timeout(900)
    pg.evaluate("() => { Object.assign(S.llm, { kind: 'openai', base_url: 'http://127.0.0.1:9/v1', model: 'm', name: 'тест', cloud: false }); saveS(); }")
    pg.evaluate("async () => { await ask('Завтра иду к врачу, немного волнуюсь'); }"); pg.wait_for_timeout(500)
    lst = pg.evaluate("() => careList()")
    ok(len(lst) == 1 and "врачу" in lst[0]["what"], f"телефон: запомнила событие: {lst}")
    pg.evaluate("() => { const d = new Date(Date.now() - 864e5), k = d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()); prefSet('care', JSON.stringify(careList().map(x => Object.assign(x, { day: k })))); }")
    pg.evaluate("async () => { await ask('Привет! Что нового?'); }"); pg.wait_for_timeout(500)
    u = [m for m in seen[-1] if m["role"] == "user"][-1]["content"]
    ok("[Заботливая память]" in u and "вчера" in u, "телефон: на следующий день — к ответу «спроси, как прошло»")
    pg.evaluate("async () => { await ask('Какие планы?'); }"); pg.wait_for_timeout(500)
    u2 = [m for m in seen[-1] if m["role"] == "user"][-1]["content"]
    ok("[Заботливая память]" not in u2, "телефон: спросила один раз")
    ok(not errs, f"без ошибок: {errs[:2]}")
    b.close()
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
