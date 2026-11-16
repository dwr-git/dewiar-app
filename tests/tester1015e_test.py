"""Отчёт №66 (телефон 0.6.45) и экзамены 0.6.45 / 0.38.51:
— «Запиши в заметки: …», затем «Напомни об этом завтра в 10 часов утра» — вышло напоминание «Этом часов утра». Теперь
  «об этом / о ней / о последней заметке» — только что записанная заметка; давно не записывали — решает модель; хвост
  «часов утра» в название не попадает;
— «Я просил напомнить по последней заметке» → «Поняла, поправлю», «Так поправь» → «Готово» — а ничего не сделано.
  «Готово / поправила / поправлю» без единого действия — модель просят сделать это инструментами;
— «поставь таймер» — а модель переспросила «скажи — поставлю»: просили прямо — ставь (и на компьютере — promise_test);
— «составь список идей» — мини-программа «на экране» вместо списка; «нарисуй схему» — программа вместо схемы (и в экзамене);
— «Напиши Андрею…», а его нет в «Близких» — модель говорит об этом, а не «Готово»."""
import srctext  # noqa: E402 — текст исходника вместе с частями (tests/srctext.py)
import json, os, re, shutil, subprocess, sys, tempfile
from datetime import datetime, timedelta
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import quality as Q  # noqa: E402
ok(Q.saved_claim("Так поправь", "Готово.", set()) and Q.saved_claim("Я просил напомнить по последней заметке", "Поняла, поправлю.", set())
   and not Q.saved_claim("Как дела?", "Готово ли ты?", set()), "компьютер: «Готово / поправлю» без действия — проверка")
ok(Q.reminder_missing("Посчитай, сколько дней до Нового года, и поставь таймер на столько же минут.", "78 дней. Скажи — поставлю.", {"calc"})
   and not Q.reminder_missing("Поставь таймер на 5 минут", "Поставила.", {"set_reminder"}) and not Q.reminder_missing("Как поставить таймер?", "Скажи…", set()),
   "компьютер: просили поставить таймер — без set_reminder проверка")

tmp = Path(tempfile.mkdtemp()); www = tmp / "www"
os.environ["DEWIAR_WORKSPACE_DIR"] = str(tmp / "ws")
import engine_answer as EA  # noqa: E402
import when  # noqa: E402
from workspace import Workspace  # noqa: E402
r = when.parse("Напомни об этом завтра в 10 часов утра")
ok(r and EA.REF_RX.match(r["text"]) and not EA.REF_RX.match("Позвонить маме"), f"компьютер: «об этом» узнаётся как ссылка: {r and r['text']}")
ws = Workspace(None)
F = type("F", (), {"workspace": ws})()
ok(EA.AnswerMixin._fresh_note(F) == "", "заметок нет — не выдумываем")
ws.save_note("Если у пользователя", "Если у пользователя отключён звук на устройстве, не синтезировать для него голос")
ok(EA.AnswerMixin._fresh_note(F).startswith("Заметка: Если у пользователя отключён звук"), f"компьютер: «об этом» — только что записанная заметка: {EA.AnswerMixin._fresh_note(F)}")
src = srctext.text(ROOT, "core/engine_answer.py")
ok("REF_RX.match(r.get(\"text\") or \"\")" in src or 'REF_RX.match(r.get("text") or "")' in src, "быстрое напоминание на компьютере проверяет «об этом»")
shutil.copytree(ROOT / "android/assets/www", www)
for x in ("entities.js", "rich.js", "skins.js", "skins.css"):
    if (ROOT / "ui/assets" / x).exists():
        shutil.copy(ROOT / "ui/assets" / x, www / x)
shutil.copytree(ROOT / "ui/assets/live", www / "live", dirs_exist_ok=True)
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                capture_output=True, text=True, check=True).stdout, encoding="utf-8")
errs, seen = [], []


def llm_route(route):
    req = route.request
    if req.method == "OPTIONS":
        return route.fulfill(status=204, headers={"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*", "Access-Control-Allow-Methods": "*"})
    msgs = json.loads(req.post_data or "{}").get("messages") or []
    seen.append(msgs)
    last = msgs[-1] if msgs else {}
    if last.get("role") == "tool":
        names = [m.get("name") for m in msgs if m.get("role") == "tool"]
        if names[-1] == "list_reminders":
            d = [{"tool_calls": [{"index": 0, "id": "c2", "type": "function", "function": {"name": "set_reminder",
                  "arguments": json.dumps({"text": "Заметка про звук", "at": (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%dT10:00")})}}]}]
        else:
            d = [{"content": "Исправила: завтра в 10:00 — «Заметка про звук»."}]
    elif str(last.get("content", "")).startswith("ПРОВЕРКА: ты написал(а), что сделал"):
        d = [{"tool_calls": [{"index": 0, "id": "c1", "type": "function", "function": {"name": "list_reminders", "arguments": "{}"}}]}]
    else:
        d = [{"content": "Поняла, поправлю."}]
    body = "".join(f"data: {json.dumps({'choices': [{'delta': x}]}, ensure_ascii=False)}\n\n" for x in d) + "data: [DONE]\n\n"
    route.fulfill(status=200, body=body, headers={"Access-Control-Allow-Origin": "*", "Content-Type": "text/event-stream"})


with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 400, "height": 820})
    pg.on("pageerror", lambda x: errs.append(str(x)))
    pg.route("http://127.0.0.1:9/**", llm_route)
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(1000)
    pg.evaluate("() => { Object.assign(S.llm, { kind: 'openai', base_url: 'http://127.0.0.1:9/v1', model: 'm', name: 'тест', cloud: false }); saveS(); }")
    R = pg.evaluate("""async () => {
        await quick('Запиши в заметки: если у пользователя отключён звук на устройстве, не синтезировать для него голос');
        const r = await quick('Напомни об этом завтра в 10 часов утра');
        const x = JSON.parse(D.alarms()).slice(-1)[0];
        return [r && r.say, x && x.title, x && new Date(x.at).getHours()]; }""")
    ok(R[1] and R[1].startswith("Заметка: Если у пользователя отключён звук") and "часов" not in R[1] and R[2] == 10,
       f"«напомни об этом» сразу после заметки — о ней, в 10:00: {R}")
    R2 = pg.evaluate("""async () => { const n = notes(); n.forEach(x => x.time = Date.now() - 3 * 3600e3); saveNotes(n);
        const r = await quick('Напомни об этом завтра в 10 часов утра'); return r ? r.say : null; }""")
    ok(R2 is None, f"заметка давняя — «об этом» решает модель (видит разговор): {R2}")
    R3 = pg.evaluate("""async () => { const r = await quick('Напомни завтра в 10 часов утра позвонить маме'); return JSON.parse(D.alarms()).slice(-1)[0].title; }""")
    ok(R3 == "Позвонить маме", f"«в 10 часов утра» — в название не попадает: {R3!r}")
    # «поправлю» без действия → просим сделать
    pg.evaluate("t => { window._done = false; ask(t).then(() => window._done = true, () => window._done = true); }", "Я просил напомнить по последней заметке")
    for _ in range(100):
        pg.wait_for_timeout(100)
        if pg.evaluate("window._done && state === 'idle'"):
            break
    nudge = [m for m in seen[-1] if m.get("role") == "user" and str(m.get("content", "")).startswith("ПРОВЕРКА: ты написал(а), что сделал")]
    tools = [m.get("name") for m in seen[-1] if m.get("role") == "tool"]
    ok(nudge and tools == ["list_reminders", "set_reminder"], f"«Поняла, поправлю» без действия — попросили сделать, сделала: {tools}")
    ok(pg.evaluate("() => JSON.parse(D.alarms()).some(x => x.title === 'Заметка про звук')"), "напоминание и правда поставлено")
    K = pg.evaluate("""() => [!!remindMissing('Посчитай, сколько дней до Нового года, и поставь таймер на столько же минут', new Set(['calc'])),
        !!remindMissing('Поставь таймер на 5 минут', new Set(['set_reminder'])),
        makeAppRefusal('Составь список из пяти идей подарка для мамы на день рождения'), makeAppRefusal('Сделай калькулятор чаевых'),
        makeAppRefusal('Нарисуй схему: как заявка проходит от клиента через менеджера на склад'),
        notCloseNote('Напиши Андрею, что я опоздаю на десять минут'), notCloseNote('Напиши в Макс, что опоздаю')]""")
    ok(K[0] and not K[1], f"телефон: просили таймер — без set_reminder проверка: {K[:2]}")
    ok(K[2].startswith("Не сделано") and "списком" not in K[2] and "пунктами" in K[2] and K[3] == "" and "```mermaid" in K[4],
       f"мини-программа — только когда просили: {[k[:40] for k in K[2:5]]}")
    ok("«Андрею» нет в «Близких»" in K[5] and K[6] == "", f"«Напиши Андрею» — его нет в «Близких»: {K[5][:80]!r}")
    ex = (ROOT / "android/assets/www/exam.js").read_text(encoding="utf-8")
    ok("makeAppRefusal(turnAsk)" in ex and "notCloseNote(turnAsk)" in ex, "экзамен на телефоне — те же правила для make_app и send_message")
    b.close()
ok(not errs, "без ошибок JavaScript" + (f": {errs}" if errs else ""))
shutil.rmtree(tmp, ignore_errors=True)
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
