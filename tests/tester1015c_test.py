"""Экзамены 15.10, вторая пара (телефон 0.6.42, компьютер 0.38.48):
— телефон: «запомни: в среду встреча» запомнено, а «что у меня в среду?» — «в календаре пусто». Теперь запомненное с датой
  и напоминания на этот день — и в ответе calendar_list, и сразу в подсказке модели на вопрос о планах;
— телефон: к готовому поздравлению «вот вариант… на открытке» дописалось «Секунду — собираю. Ничего не вышло…» — проверка
  «обещала программу» срабатывает, только когда программу и просили;
— телефон: «нарисуй схему» — make_app отказывает и просит ```mermaid (модель сделала схему HTML-программой);
— вызов текстом «<function": "web_search", "arguments": {…}}» — разобран (компьютер и телефон);
— компьютер: «записала 65 000», ничего не вызвав, — просим записать по-настоящему (promise_test)."""
import json, os, shutil, subprocess, sys, tempfile
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


import llm  # noqa: E402
import quality as Q  # noqa: E402
ok(llm.parse_tool_call('\n<function": "web_search", "arguments": {"query": "фильмы 2025"}}\n') == {"name": "web_search", "args": {"query": "фильмы 2025"}},
   "компьютер: «<function\": …» разобран")
ok(Q.saved_claim("Ладно, остановимся на 65 тысячах.", "Окей, записала 65 000.", set()) and not Q.saved_claim("Ладно, 65.", "Записала.", {"remember"})
   and not Q.saved_claim("Ты записала?", "Нет, не записала.", set()), "«записала» без действий — подсказка; с действием или на вопрос — нет")

tmp = Path(tempfile.mkdtemp()); www = tmp / "www"
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
    seen.append(json.loads(req.post_data or "{}").get("messages") or [])
    d = {"choices": [{"delta": {"content": "В среду в 15:00 — встреча с подрядчиком по кухне."}}]}
    route.fulfill(status=200, body=f"data: {json.dumps(d, ensure_ascii=False)}\n\ndata: [DONE]\n\n",
                  headers={"Access-Control-Allow-Origin": "*", "Content-Type": "text/event-stream"})


with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 400, "height": 820})
    pg.on("pageerror", lambda x: errs.append(str(x)))
    pg.route("http://127.0.0.1:9/**", llm_route)
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(1000)
    pg.evaluate("() => { Object.assign(S.llm, { kind: 'openai', base_url: 'http://127.0.0.1:9/v1', model: 'm', name: 'тест', cloud: false }); saveS(); }")
    wed = datetime.now() + timedelta(days=(2 - datetime.now().weekday()) % 7)   # в среду «в среду» — это сегодня (21.10 проверка падала по средам)
    pg.evaluate("async () => { await quick('Запомни, пожалуйста: в среду в 15:00 у меня встреча с подрядчиком по кухне.'); }")
    got = pg.evaluate("() => { const m = memArr().map(f => /\\(на (\\d\\d)\\.(\\d\\d)\\.(\\d{4})/.exec(f)).find(Boolean); return m ? m[3] + '-' + m[2] + '-' + m[1] : ''; }")
    if got:                                                  # в среду после 15:00 «в среду в 15:00» — следующая среда (28.10)
        wed = datetime.strptime(got, "%Y-%m-%d")
    ok(wed.weekday() == 2, f"запомнилось на среду: {got}")
    C = pg.evaluate(f"async () => await runTool('calendar_list', {{ from: '{wed:%Y-%m-%d}', days: 1 }})")
    ok("встреча с подрядчиком по кухне" in C and "Назови и это" in C, f"calendar_list на среду — и запомненное: {C[:220]!r}")
    C2 = pg.evaluate(f"async () => await runTool('calendar_list', {{ from: '{(wed + timedelta(days=1)):%Y-%m-%d}', days: 1 }})")
    ok("подрядчик" not in C2, "на другой день — без него")
    A = pg.evaluate("() => [agendaPlans('Что у меня в среду?'), agendaPlans('Какие планы на среду?'), agendaPlans('Что такое среда?'), agendaPlans('Как дела?')]")
    ok("подрядчик" in A[0] and "подрядчик" in A[1] and not A[2] and not A[3], f"вопрос о планах на день — планы сразу; другие вопросы — нет: {[bool(x) for x in A]}")
    pg.evaluate("t => { window._done = false; ask(t).then(() => window._done = true, () => window._done = true); }", "Что у меня в среду?")
    for _ in range(80):
        pg.wait_for_timeout(100)
        if pg.evaluate("window._done && state === 'idle'"):
            break
    # 19.10: план дня — справкой в сообщении пользователя (подсказка модели не меняется — кэш своего сервера)
    sysm = " ".join(str(m.get("content")) for m in (seen[-1] if seen else []) if m.get("role") in ("system", "user"))
    ok("ПЛАНЫ ПОЛЬЗОВАТЕЛЯ на этот день" in sysm and "подрядчик" in sysm, "«что у меня в среду?» — модель сразу видит запомненную встречу")
    # проверка «обещала программу»
    MOM = "Вот вариант — тёплый, без пафоса, можно отправить в мессенджер или написать на открытке: «Мам, с днём рождения!»"
    K = pg.evaluate("""([m]) => [claimedAction(m, new Set(), 'Лира, помоги придумать короткое тёплое поздравление для мамы с днём рождения.'),
        (claimedAction('Готово, калькулятор сделан — он уже на экране.', new Set(), 'Сделай калькулятор чаевых') || {}).tool]""", [MOM])
    ok(K[0] is None and K[1] == "make_app", f"поздравление «на открытке» — не обещание программы; «калькулятор готов» без make_app — да: {K}")
    # схема — не программой
    M = pg.evaluate("""async () => { turnAsk = 'Нарисуй схему: как заявка проходит от клиента через менеджера на склад'; const r1 = await runTool('make_app', { title: 'Схема', html: '<html><body><div>x</div></body></html>' });
        turnAsk = 'Сделай приложение со схемой метро'; const r2 = await runTool('make_app', { title: 'Метро', html: '<html><body><div>x</div></body></html>' }); turnAsk = ''; return [r1, r2]; }""")
    ok(M[0].startswith("Не сделано") and "```mermaid" in M[0] and M[1].startswith("Сделано"), f"«нарисуй схему» — make_app отказывает, «сделай приложение» — нет: {[m[:40] for m in M]}")
    P = pg.evaluate("""() => parseToolCall('<function": "web_search", "arguments": {"query": "фильмы 2025"}}')""")
    ok(P == {"name": "web_search", "args": {"query": "фильмы 2025"}}, f"телефон: «<function\": …» разобран: {P}")
    b.close()
src = (ROOT / "android/assets/www/app.js").read_text(encoding="utf-8")
ok("радио сам не включай, если не просили включить" in src, "плейлист — список песен, а не включённое радио")
ok(not errs, "без ошибок JavaScript" + (f": {errs}" if errs else ""))
shutil.rmtree(tmp, ignore_errors=True)
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
