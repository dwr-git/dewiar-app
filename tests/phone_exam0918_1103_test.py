"""Экзамен телефона 0.9.18 (03.11, HONOR, «Dewiar chat · телефон», сдано 55 из 72; владелец: «Лира довольно плохо работает»).
Провалы — ответы словами без действия и выдумки. Подставная модель отвечает «плохо» — как на экзамене; проверяем, что
приложение переспросило и в итоге действие вызвано; что обычные короткие ответы на разговор не переспрашиваются; что
«слушай …, напомни …» ставит напоминание; что числа до calc не уходят в ответ; что вопросы о приложении идут по руководству."""
import os, subprocess, sys, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


w = Path(tempfile.mkdtemp()) / "www"
subprocess.run(["bash", str(ROOT / "android/tools/www_assemble.sh"), str(w)], check=True, capture_output=True)
SETUP = """() => {
  Object.assign(S.llm, { cloud: true, api_key: 'dw-test-key', base_url: 'http://127.0.0.1:9/cloud.php?p=', model: 'chat' });
  window._said = []; say = (t) => _said.push(t); syncSoon = () => {};
  window._calls = []; runTool = async (n, a) => { _calls.push({ n, a }); return n === "calc" ? 'days_until("2027-01-01") = 59' : "Готово: " + n; };
  window._asks = []; window._plan = null;
  llmStream = async (msgs, tools, onText) => {
    const last = msgs[msgs.length - 1]; _asks.push(typeof last.content === "string" ? last.content : JSON.stringify(last.content));
    const s = _plan(msgs, _asks.length - 1) || { text: "" };
    if (s.text) onText(s.text);
    return { text: s.text || "", calls: (s.calls || []).map((c, i) => ({ id: "c" + _asks.length + i, name: c.name, args: JSON.stringify(c.args || {}) })), finish: s.calls ? "tool_calls" : "stop" };
  };
  window._people = [{ pid: "p1", name: "Миша Исаев", devs: [{ dev: "d1", pub: "A".repeat(43) }] }];
  try { const st = clLoad(); st.people = _people; } catch (e) { }
}"""
# сценарий: первый ответ — «плохой» (как на экзамене); после проверки (ПРОВЕРКА / СТОП) — вызов нужного действия, потом итог словами
RUN = """async ([q, bad, tool, args, fin]) => {
  _said = []; _calls = []; _asks = []; history = [];
  _plan = (msgs, i) => {
    const last = String(msgs[msgs.length - 1].content || "");
    if (msgs[msgs.length - 1].role === "tool") return { text: fin };
    if (/^(?:ПРОВЕРКА|СТОП)/.test(last)) return { calls: [{ name: tool, args }] };
    return i === 0 ? { text: bad } : { text: fin };
  };
  await ask(q); await new Promise(r => setTimeout(r, 200));
  return { calls: _calls.map(c => c.n), args: _calls.map(c => c.a), asks: _asks, bot: document.querySelector("#bot").textContent, hist: (history.slice(-1)[0] || {}).content };
}"""
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 393, "height": 852}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route("https://**", lambda r: r.abort())
    pg.goto((w / "index.html").as_uri()); pg.wait_for_timeout(900)
    pg.evaluate(SETUP)
    run = lambda *a: pg.evaluate(RUN, list(a))  # noqa: E731

    # 1. «Помаши Мише» — «Помахала Мише 👋» без close_wave
    c = pg.evaluate("(() => { const c = claimedAction('Помахала Мише 👋', new Set(), 'Помаши Мише'); return c && c.tool; })()")
    ok(c == "close_wave", f"«Помахала Мише 👋» без действия — обещание без дела (close_wave): {c}")
    r = run("Помаши Мише", "Помахала Мише 👋", "close_wave", {"to": "Мише"}, "Помахала — Миша увидит.")
    ok("close_wave" in r["calls"] and any("close_wave" in a for a in r["asks"][1:2]), f"переспросила — и правда помахала (close_wave): {r['calls']} {r['asks'][1:2]}")

    # 2. «…Отметь как исполненное» — теперь отмечается сразу, без модели; и «Отметила! 🎉» без mark_done — обещание
    d = pg.evaluate("doneParse('Лира, я позвонила Игорю и сделала тренировку. Отметь как исполненное')")
    ok(d and d["explicit"] and len(d["items"]) == 2 and "Игорю" in d["items"][0] and "тренировку" in d["items"][1].lower(), f"«…Отметь как исполненное» — два дела, без модели: {d}")
    d2 = pg.evaluate("doneParse('отметь, что я купил хлеб')")
    ok(d2 and any("хлеб" in x for x in d2["items"]), f"«отметь, что я купил хлеб» — отметка без модели: {d2}")
    c = pg.evaluate("(() => { const c = claimedAction('Отметила! 🎉', new Set(), 'Лира, я позвонила Игорю и сделала тренировку. Отметь как исполненное'); return c && c.tool; })()")
    ok(c == "mark_done", f"«Отметила! 🎉» без действия — mark_done: {c}")
    r = run("Лира, я позвонила Игорю и сделала тренировку. Отметь как исполненное", "Отметила! 🎉", "mark_done", {}, "")
    ok(not r["asks"] and "Отметил" in r["bot"] and "Игорю" in r["bot"], f"отметка — сразу, без модели: {r['bot']}")

    # 3. «Удали задачу» — «Удалила» без remove_task
    c = pg.evaluate("(() => { const c = claimedAction('Удалила. Задача «Исследование» больше не висит в списке.', new Set(), 'Удали задачу «Исследование», она мне больше не нужна.'); return c && c.tool; })()")
    ok(c and c.startswith("remove_task"), f"«Удалила» без действия — remove_task: {c}")
    r = run("Удали задачу «Исследование», она мне больше не нужна.", "Удалила. Задача «Исследование» больше не висит в списке.", "remove_task", {"name": "Исследование"}, "Удалила задачу «Исследование».")
    ok("remove_task" in r["calls"], f"переспросила — и правда удалила: {r['calls']}")

    # 4. Фонарик «Я проверю.» — поручение, короткий ответ без действия
    r = run("Фонарик у меня всё ещё горит, хотя я уже просил его выключить. Сделай что-нибудь, чтобы он погас.", "Я проверю.", "flashlight", {"on": False}, "Выключила фонарик.")
    ok("flashlight" in r["calls"] and r["args"][0] == {"on": False} and "flashlight" in (r["asks"][1] if len(r["asks"]) > 1 else ""),
       f"«Я проверю.» на поручение — переспросила с подсказкой flashlight, фонарик выключен: {r['calls']} {r['asks'][1:2]}")

    # 5. Погода: «Привет! Какая сейчас погода в Минске?» — без модели (приветствие не мешает); модель «Давай гляну» — переспрос
    q = pg.evaluate("wqParse('Привет! Какая сейчас погода в Минске?')")
    ok(q and q["city"] == "Минске" and q["day"] == 0, f"«Привет! Какая погода в Минске?» — погода сразу, город понят: {q}")
    q = pg.evaluate("wqParse('Здравствуйте, Лира! Какая погода завтра в Минске?')")
    ok(q and q["city"] == "Минске" and q["day"] == 1, f"«Здравствуйте, Лира! …завтра» — тоже: {q}")
    ok(pg.evaluate("wqParse('Привет! А погода?')") is not None, "«Привет! А погода?» — погода в городе человека")
    h = pg.evaluate("orderUndone('Привет! Какая сейчас погода в Минске?', 'Привет! Давай гляну.', new Set())")
    ok("weather" in h, f"«Давай гляну» без погоды — переспрос с подсказкой weather: {h[:90]}")
    h = pg.evaluate("inventedFacts('Какая погода завтра в Минске?', 'Завтра в Минске от плюс 3 до плюс 5°, морось.', new Set())")
    ok("выдуманы" in h, "числа погоды без weather — выдумка, переспрос")
    ok(pg.evaluate("inventedFacts('Какая погода завтра в Минске?', 'Завтра в Минске от плюс 3 до плюс 5°.', new Set(['weather']))") == "", "после weather — числа настоящие")

    # 6. «слушай … напомни мне завтра в 9 утра» — «Слушаю тебя.»
    r = run("слушай встреча с Ирой переносится на послезавтра на 12 напомни мне завтра в 9 утра", "Слушаю тебя.", "set_reminder",
            {"text": "Встреча с Ирой переносится на послезавтра, 12:00", "when": "завтра в 9"}, "Напомню завтра в 9:00.")
    ok("set_reminder" in r["calls"] and "завтра в 9" in r["args"][r["calls"].index("set_reminder")].get("when", ""), f"«…напомни мне завтра в 9» — напоминание поставлено: {r['calls']}")
    ok(r["asks"] and r["asks"][0].split("(Сообщение пользователя)\n")[-1].startswith("встреча с Ирой"), f"«слушай» в начале — не модели: {r['asks'][0][-90:]!r}")
    ok(pg.evaluate("SET_ASK.test('слушай встреча с Ирой переносится на послезавтра на 12 напомни мне завтра в 9 утра')"), "«напомни мне завтра…» в середине фразы — просьба поставить")

    # 7. Новый год: «на столько же минут» — 59, а не 59×24×60; «28 дней», сказанное до calc, — не в ответ
    fx = pg.evaluate("""sameMinutesFix('Посчитай, сколько дней осталось до Нового года, и поставь таймер на столько же минут.',
      [{ name: 'calc', args: {}, result: 'days_until("2027-01-01") = 59' }, { name: 'calc', args: {}, result: '59*24*60 = 84960' },
       { name: 'set_reminder', args: { in_minutes: 84960 }, result: 'Поставлено' }])""")
    ok("in_minutes: 59" in fx, f"«на столько же минут» — то же число (59), а не 84 960: {fx[:100]}")
    r = pg.evaluate("""async () => { _said = []; _calls = []; _asks = []; history = [];
      _plan = (msgs, i) => i === 0 ? { text: "Сегодня 3 ноября, так что до Нового года 28 дней — это 40 320 минут. Ставлю таймер.", calls: [{ name: "calc", args: { expression: 'days_until("2027-01-01")' } }] }
        : i === 1 ? { calls: [{ name: "set_reminder", args: { text: "Таймер", kind: "timer", in_minutes: 59 } }] } : { text: "До Нового года 59 дней — таймер на 59 минут стоит." };
      await ask("Посчитай, сколько дней осталось до Нового года, и поставь таймер на столько же минут."); await new Promise(r => setTimeout(r, 200));
      return { bot: document.querySelector("#bot").textContent, said: _said.join(" "), hist: history.slice(-1)[0].content }; }""")
    ok("28" not in r["bot"] + r["said"] + r["hist"] and "59" in r["bot"], f"числа до calc («28 дней») не показаны и не озвучены: {r}")
    r = pg.evaluate("""async () => { _said = []; history = [];
      _plan = (msgs, i) => ({ text: "Привет! Рада тебя слышать. Чем займёмся?" });
      await ask("Привет!"); await new Promise(r => setTimeout(r, 100)); return { said: _said.join(" "), n: _asks.length }; }""")
    ok("Привет" in r["said"], "обычный ответ без счёта — озвучивается как раньше")

    # 8. Вопросы о самом приложении — руководство приложено к вопросу; «такой функции нет» без руководства — переспрос
    for ask_, want in (("Хочу вести общий бюджет с женой, чтобы видеть траты друг друга. Как это сделать?", "Семья"),
                       ("А есть у тебя видеоуроки, чтобы посмотреть, что ты умеешь?", "Видеоурок"),
                       ("Как мне добавить маму, чтобы мы могли переписываться через наших помощников?", "Пригласить")):
        r = run(ask_, "Ответ по руководству.", "app_help", {"query": ask_}, "")
        ok(want in r["asks"][0] and "Из руководства Dewiar" in r["asks"][0], f"«{ask_[:40]}…» — руководство приложено к вопросу ({want})")
    h = pg.evaluate("appHelpMissing('Можно вести учёт вместе?', 'Но общего бюджета с женой в Dewiar пока нет — это функция, которой у меня сейчас нет.', new Set())")
    ok("app_help" in h, "«в Dewiar пока нет» без руководства — переспрос: загляни в app_help")
    ok(pg.evaluate("appHelpMissing('Есть у тебя видеоуроки?', 'Да, в «Всё» → «Видеоуроки».', new Set(['app_help']))") == "", "после руководства — без переспроса")

    # 9. «через сколько дней» — назвать число дней
    h = pg.evaluate("daysMissing('Чей день рождения ближайший и через сколько дней?', 'Ближайший — у Пети, 12 ноября.', new Set())")
    ok("days_until" in h, "«через сколько дней» — «12 ноября» без числа дней: переспрос с calc")
    ok(pg.evaluate("daysMissing('Чей день рождения ближайший и через сколько дней?', 'У Пети, 12 ноября — через 9 дней.', new Set())") == "", "«через 9 дней» — ответ полный")

    # 10. «покажи, как выглядит» — без show_images
    h = pg.evaluate("imagesMissing('Расскажи в двух словах про руническую вязь и покажи, как она выглядит.', 'Руническая вязь — это орнамент из рун.', new Set())")
    ok("show_images" in h, "«покажи, как выглядит» — рассказала без картинок: переспрос show_images")
    ok(pg.evaluate("imagesMissing('Посмотри, как я выгляжу', 'Отлично выглядишь!', new Set())") == "", "«как я выгляжу» — это камера, не картинки")

    # 11. Обычные короткие ответы на разговор — без переспроса
    for ask_, ans in (("Привет!", "Привет! Как дела?"), ("Спасибо!", "Пожалуйста!"), ("Как дела?", "Отлично, а у тебя?"), ("Расскажи анекдот", "Колобок повесился."),
                      ("Сделай потише.", "Что сделать тише — радио ничего не играет?"), ("Ты молодец", "Спасибо, приятно!"), ("Что я ел сегодня на завтрак?", "Не знаю — ты не говорил."),
                      ("Какая погода в доме у Петровых?", "Тёплая, по-моему.")):
        ok(pg.evaluate("([q, a]) => orderUndone(q, a, new Set()) + inventedFacts(q, a, new Set()) + appHelpMissing(q, a, new Set()) + imagesMissing(q, a, new Set()) + daysMissing(q, a, new Set())", [ask_, ans]) == "",
           f"разговор «{ask_}» → «{ans}» — без переспроса")
    r = pg.evaluate("""async () => { _said = []; _asks = []; history = [];
      _plan = (msgs, i) => ({ text: "Привет! Рада слышать." });
      await ask("Привет, Лира!"); await new Promise(r => setTimeout(r, 100)); return _asks.length; }""")
    ok(r == 1, f"«Привет, Лира!» — один ответ модели, без переспроса: {r}")

    # 12. Креатив: рифма, «короткая» — до 8 предложений, только существующие песни
    ok(pg.evaluate("STORY_ASK.test('Сочини короткую смешную историю про шкаф, который не хотел собираться.')") and "8 предложений" in pg.evaluate("STORY_NOTE"),
       "«короткая история» — не больше 8 предложений")
    ok("однокоренного" in pg.evaluate("POEM_NOTE") and "реально существующие" in pg.evaluate("RECO_NOTE"), "стихи — рифма по окончаниям; песни — только существующие")

    b.close()

    # 13. Кто отвечал: строка «: dewiar-server w3» в потоке — в журнал и в отчёт экзамена; «: keepalive» не ломает разбор
    # (настоящий llmStream, без подмены — отдельной страницей)
    b = p.chromium.launch(); pg = b.new_page(); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route("https://**", lambda r: r.abort())
    pg.goto((w / "index.html").as_uri()); pg.wait_for_timeout(900)
    srv = pg.evaluate("""async () => {
      Object.assign(S.llm, { cloud: true, api_key: 'k', base_url: 'http://127.0.0.1:9/cloud.php?p=', model: 'chat' });
      const keepHttp = http; turnServers = new Set(); const seen = {};
      http = async (m, u, o) => { seen.idle = o.idle; o.onChunk(": dewiar-server w3\\n\\n: keepalive\\n\\ndata: " + JSON.stringify({ choices: [{ delta: { content: "Привет!" } }] }) + "\\n\\ndata: [DONE]\\n\\n"); return { status: 200, body: "" }; };
      try { const r = await llmStream([{ role: "user", content: "привет" }], null, () => {}, null, {});
        const r2 = await llmStream([{ role: "user", content: "сделай программу" }], null, () => {}, null, { idle: 300000 });
        return { text: r.text, srv: [...turnServers], idle: seen.idle }; } finally { http = keepHttp; } }""")
    ok(srv["text"] == "Привет!" and srv["srv"] == ["w3"], f"«: dewiar-server w3» и «: keepalive» — сервер запомнен, текст цел: {srv}")
    ok(srv["idle"] == 300000, f"длинная генерация (программа) — поток может молчать до 5 минут: {srv['idle']}")
    b.close()

src = (ROOT / "android/assets/www/app.js").read_text(encoding="utf-8")
ok("longGen ? { idle: 300000 }" in src and "MAKE_ASK_RX.test(text)" in src, "make_app: длинное ожидание потока на просьбу сделать программу")
wb = (ROOT / "android/web/webbridge.js").read_text(encoding="utf-8")
ok("arm();" in wb and "const arm = () =>" in wb, "веб-версия: предел — на молчание потока, а не на весь ответ")
ex = (ROOT / "android/assets/www/exam.js").read_text(encoding="utf-8")
for sid in ("close_wave_voice", "done_mark", "task_remove", "flashlight_off", "weather_hello", "weather", "life_move_remind", "newyear_timer",
            "help_family", "help_lessons", "app_howto_close", "memory_birthdays", "show_pics", "poem_rhyme", "story", "playlist", "make_3d",
            "close_wave_mom", "done_bread", "weather_hi_short"):
    ok(f'id: "{sid}"' in ex, f"сценарий экзамена «{sid}» есть")
ok("servers: [...turnServers]" in ex and "_(сервер:" in ex, "отчёт экзамена: какой сервер облака отвечал")
ok(not errs, f"без ошибок JavaScript: {errs[:3]}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
