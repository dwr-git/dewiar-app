"""Телефон: экзамен способностей (android/assets/www/exam.js) в песочнице. Модель — заглушка внутри страницы.
Экзамен начинают только из кабинета: задание приходит в ответ на пульс (или на вопрос телефона, которому его уже давали);
в «Ещё» кнопки нет. Проверяет: все испытания проходят по настоящему пути ответа; напоминание через быстрый ответ и через модель —
только в песочнице (на «телефоне» будильников нет); фонарик из быстрого ответа засчитан; расход и радио — по действиям;
судья ставит оценки; голос молчит; итог уходит в кабинет (?p=/exam) с пометкой «телефон»; после «Готово» приложение
перезагружается, и память, расходы и разговор человека — как были."""
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


www = Path(tempfile.mkdtemp()) / "www"
shutil.copytree(ROOT / "android/assets/www", www)
shutil.copy(ROOT / "ui/assets/entities.js", www / "entities.js")
shutil.copy(ROOT / "ui/assets/call.js", www / "call.js")
shutil.copytree(ROOT / "ui/assets/live", www / "live", dirs_exist_ok=True)
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                capture_output=True, text=True, check=True).stdout, encoding="utf-8")
(www / "radio.js").write_text("window.DEWIAR_RADIO = [];", encoding="utf-8")

SETUP = """() => {
  Object.assign(S.llm, { kind: "openai", base_url: "https://dewiar.pro/dwrapp/cloud.php?p=", api_key: "dw-test", model: "chat", cloud: true });
  S.onboarded = true; S.memory = ["Любит зелёный чай"]; saveS();
  history.push({ role: "user", content: "Привет" }, { role: "assistant", content: "Привет! Чем помочь?" }); saveH();
  window.resolveModel = async () => "chat";
  window._spoken = 0; const sp = D.speak; D.speak = function (id) { window._spoken++; return sp.apply(this, arguments); };
  const NL = String.fromCharCode(10, 10), sse = (o) => "data: " + JSON.stringify(o) + NL;
  window._sent = null; window._seen = []; window._states = []; window._polls = 0; window._cancelAt = 0;
  window.http = async (m, u, o) => {
    if (/p=\\/pulse/.test(u)) return { status: 200, body: JSON.stringify({ ok: true, exam: window._offer || undefined }) };
    if (/p=\\/exam\\/phone/.test(u) && m === "GET") { window._polls++; return { status: 200, body: JSON.stringify({ ok: true, exam: window._offer || undefined }) }; }
    if (/p=\\/exam\\/phone/.test(u)) {
      const b = typeof o.body === "string" ? JSON.parse(o.body) : o.body; window._states.push(b.state + ":" + (b.i || "") + ":" + b.id + ":" + b.dev);
      if (b.state === "done") { window._sent = b.report; return { status: 200, body: JSON.stringify({ ok: true, run: 7 }) }; }
      return { status: 200, body: JSON.stringify({ ok: true, cancel: window._cancelAt > 0 && b.i >= window._cancelAt }) };
    }
    if (!o.onChunk) return { status: 200, body: "{}" };
    const body = typeof o.body === "string" ? JSON.parse(o.body) : o.body; window._seen.push(body);
    const sys = body.messages[0].content || "", last = body.messages[body.messages.length - 1];
    const lastText = typeof last.content === "string" ? last.content : "";
    const userText = [...body.messages].reverse().find(x => x.role === "user").content;
    let content = "", calls = [];
    if (sys.startsWith("Ты — строгий и справедливый экзаменатор")) content = JSON.stringify({ score: 8, why: "по делу" });
    else if (last.role === "tool") content = "Сделала.";
    else if (/Запиши расход/.test(userText)) calls = [{ name: "money_add", args: { kind: "expense", amount: 450, category: "Продукты", note: "продукты" } }];
    else if (/радио/.test(userText)) calls = [{ name: "play_radio", args: { query: "джаз" } }];
    else if (/Нового года/.test(userText)) calls = [{ name: "set_reminder", args: { text: "Таймер", in_minutes: 50 } }];
    else content = "Хорошо, понял.";
    const chunks = [];
    if (content) chunks.push(sse({ choices: [{ delta: { content } }] }));
    calls.forEach((c, i) => chunks.push(sse({ choices: [{ delta: { tool_calls: [{ index: i, id: "c" + i, type: "function", function: { name: c.name, arguments: JSON.stringify(c.args) } }] } }] })));
    chunks.push(sse({ choices: [{ delta: {}, finish_reason: calls.length ? "tool_calls" : "stop" }] }) + "data: [DONE]" + NL);
    o.onChunk(chunks.join(""));
    return { status: 200, body: "" };
  };
}"""

with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(); errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(800)
    pg.evaluate(SETUP)
    pg.evaluate("() => { setTab = 'more'; openSettings('more'); }"); pg.wait_for_timeout(300)
    ok(pg.evaluate("() => !document.querySelector('#exam-go') && !/Экзамен/.test(document.body.innerText)"),
       "в «Ещё» экзамена нет — его начинают из кабинета")
    pg.evaluate("() => closeSheets()")
    pg.evaluate("() => pulseSend()"); pg.wait_for_timeout(300)
    ok(pg.evaluate("() => !document.querySelector('#exam-bar.on')") and pg.evaluate("() => D.pref('exam_dev')") != "1",
       "пульс без задания — экзамен не начинается")
    pg.evaluate("() => examPoll()"); pg.wait_for_timeout(200)
    ok(pg.evaluate("() => window._polls") == 0, "телефон, которому экзамен не давали, кабинет не спрашивает")
    pg.evaluate("() => { window._offer = { id: 'j1' }; pulseSend(); }")
    pg.wait_for_function("() => document.querySelector('#exam-stop') && document.querySelector('#exam-stop').textContent === 'Готово'", timeout=240000)
    R = pg.evaluate("""() => ({ now: document.querySelector('#exam-now').textContent, sent: window._sent, spoken: window._spoken,
        alarms: JSON.parse(D.alarms()), memPref: JSON.parse(D.pref('settings')).memory, histPref: JSON.parse(D.pref('history')).length })""")
    rep = R["sent"] or {}
    sc = {s["id"]: s for s in rep.get("scenarios", [])}
    ok(len(sc) >= 18 and "телефон" in rep.get("version", "") and rep.get("model", "").endswith("· телефон"),
       f"итог ушёл в кабинет: {len(sc)} испытаний, {rep.get('version')}, {rep.get('model')}")
    ok("Сдано" in R["now"] and "кабинете" in R["now"], f"на экране — итог: {R['now']}")
    ok(sc.get("oven", {}).get("passed"), f"напоминание через быстрый ответ — засчитано: {sc.get('oven', {}).get('checks')}")
    ok(sc.get("newyear_timer", {}).get("checks", [{}])[-1].get("ok") is False, "таймер не на то число минут — не засчитан")
    ok(sc.get("money", {}).get("passed") and sc.get("radio", {}).get("passed"), f"расход и радио — по действиям модели: {[(k, sc.get(k, {}).get('checks'), [s.get('answer') for s in sc.get(k, {}).get('steps', [])]) for k in ('money', 'radio')]}")
    ok(sc.get("flashlight", {}).get("passed"), "фонарик через быстрый ответ — засчитан (в песочнице)")
    ok(all(s.get("judge", {}).get("score") == 8 for s in sc.values()), "судья оценил каждое испытание")
    # ошибки, найденные руками 11.10, — в экзамене: заметки и напоминания «есть, а говорит нет», фото к заметке, сканер
    for k in ("notes_show", "reminders_show", "note_photo", "note_long", "scanner_open", "close_call_voice", "close_video_voice", "close_msg_voice",
              "stop_misheard"):
        ok(sc.get(k, {}).get("passed"), f"экзамен ловит «{k}»: {[(c['name'], c['ok']) for c in sc.get(k, {}).get('checks', [])]} · {[x.get('answer') for x in sc.get(k, {}).get('steps', [])]}")
    ok(not sc.get("notes_find", {}).get("passed"), "«что я записывал про ремонт» без поиска по заметкам (заглушка модели) — не засчитан")
    ok(R["alarms"] == [], f"на «телефоне» не появилось ни одного будильника: {R['alarms']}")
    ok(R["memPref"] == ["Любит зелёный чай"] and R["histPref"] == 2, "сохранённые память и разговор не тронуты")
    ok(R["spoken"] == 0, "голос во время экзамена молчал")
    ok("## " in rep.get("md", "") and "Сдано" in rep.get("md", ""), "отчёт Markdown — вместе с итогом")
    st = pg.evaluate("() => window._states")
    dev = pg.evaluate("() => devId()")
    ok(st[0] == f"running:1:j1:{dev}" and st[-1] == f"done::j1:{dev}" and len(st) == pg.evaluate("EXAM_PHONE.length") + 1,
       f"ход — в кабинет по каждому испытанию, итог — туда же: {st[:2]} … {st[-1:]} ({len(st)})")
    ok(pg.evaluate("() => D.pref('exam_dev')") == "1", "телефон запомнил, что экзамены ему дают (дальше спросит сам при открытии)")
    pg.evaluate("() => document.querySelector('#exam-stop').click()")
    pg.wait_for_timeout(1200)
    after = pg.evaluate("() => ({ mem: S.memory, hist: history.length, exam: typeof EXAM !== 'undefined' && EXAM, money: (S.money || []).length })")
    ok(after["mem"] == ["Любит зелёный чай"] and after["hist"] == 2 and not after["exam"], f"после «Готово» — всё как было: {after}")
    pg.evaluate(SETUP); pg.evaluate("() => { window._offer = { id: 'j2' }; window._cancelAt = 3; }")
    pg.evaluate("() => examPoll()")
    pg.wait_for_function("() => document.querySelector('#exam-stop') && document.querySelector('#exam-stop').textContent === 'Готово'", timeout=60000)
    st = pg.evaluate("() => window._states")
    ok(pg.evaluate("() => window._polls") == 1 and st[-1].startswith("cancelled") and not pg.evaluate("() => window._sent"),
       f"«Остановить» в кабинете — телефон останавливается и итог не сохраняет: {st}")
    ok(not errors, f"без ошибок страницы: {errors[:3]}")
    b.close()
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
print("ALL OK" if not fails else "")
sys.exit(1 if fails else 0)
