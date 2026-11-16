"""Честное «готово» (отзыв 13.10: «говорит "Сделала!", а результата нет — появляется через 20–60 минут или не появляется»).
Фоновую задачу только запустили (start_task) — результата ещё нет:
— инструмент прямо говорит модели «результата ЕЩЁ НЕТ, не говори "готово"» (компьютер и телефон);
— модель всё равно сказала «Готово! Вот презентация» — помощник тут же поправляется вслух и в тексте; «взялась, сообщу,
  когда будет готово» — без поправки; модель промолчала — «Задача передана — пришлю уведомление», а не «Сделала»."""
import srctext  # noqa: E402 — текст исходника вместе с частями (tests/srctext.py)
import os, shutil, subprocess, sys, tempfile
from pathlib import Path
from types import SimpleNamespace
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
d = tempfile.mkdtemp(); os.environ.update(DEWIAR_CONFIG_DIR=d + "/cfg", DEWIAR_STATE_DIR=d + "/st")
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import engine_brain as E  # noqa: E402
src = srctext.text(ROOT, "core/tools.py")
ok("Результата ЕЩЁ НЕТ" in src and "не говори «готово»" in src, "компьютер: start_task говорит модели, что результата ещё нет")
early = lambda full, tools=("start_task",): E.BrainMixin._early_done(None, SimpleNamespace(full=full, tools_ok=list(tools)))  # noqa: E731
for t, want in (("Готово! Презентация уже в папке.", True), ("Сделала! Вот презентация о погоде.", True), ("Отлично, отчёт готов.", True),
                ("Взялась за презентацию — сообщу, когда будет готово.", False), ("Запустил задачу, займёт минут десять.", False),
                ("Приступаю. Как только закончу — скажу.", False)):
    ok(bool(early(t)) == want, f"компьютер: «{t}» — {'поправиться' if want else 'честно'}")
ok(early("Готово!", ("set_reminder",)) == "", "без фоновой задачи «Готово» — правда, не поправляем")
ans = srctext.text(ROOT, "core/engine_answer.py")
ok('"Задача запущена — сообщу, когда будет готово." if "start_task" in turn.tools_ok' in ans and "self._early_done(turn)" in ans,
   "компьютер: модель промолчала после задачи — не «Готово.»; поправка — в ответе")

www = Path(tempfile.mkdtemp()) / "www"
shutil.copytree(ROOT / "android/assets/www", www)
for f in ("entities.js", "skins.css", "skins.js", "privacy.js"):
    shutil.copy(ROOT / "ui/assets" / f, www / f)
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)], capture_output=True, text=True, check=True).stdout, encoding="utf-8")
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 393, "height": 820}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route("https://**", lambda r: r.abort())
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(800)
    pg.evaluate("""() => { Object.assign(S.llm, { cloud: true, api_key: 'dw-test-key', base_url: 'http://127.0.0.1:9/cloud.php?p=', model: 'chat' }); S.sync = { on: true };
      window._said = []; say = (t) => _said.push(t); syncSoon = () => {};
      window._script = []; llmStream = async (msgs, tools, onText) => { const s = _script.shift() || { text: "" }; if (s.text) onText(s.text);
        return { text: s.text || "", calls: s.calls || [], finish: s.calls ? "tool_calls" : "stop" }; }; }""")
    run = lambda reply: pg.evaluate("""async (reply) => { _said = []; const call = { id: "c1", name: "start_task", args: JSON.stringify({ title: "Презентация о погоде", goal: "Сделай презентацию о погоде на завтра" }) };
        _script = [{ calls: [call] }, { text: reply }, { text: "" }];
        await ask("Сделай презентацию о погоде на завтра"); await new Promise(r => setTimeout(r, 300));
        return { said: _said.join(" "), bot: document.querySelector("#bot").textContent, hist: history.slice(-1)[0].content, tool: (history.length, "") }; }""", reply)
    r = run("Готово! Вот презентация о погоде на завтра.")
    ok("Поправлюсь: задача только началась" in r["said"] and "Поправлюсь" in r["bot"] and "Поправлюсь" in r["hist"], f"телефон: «Готово!» сразу после передачи задачи — поправилась вслух, на экране и в истории: {r}")
    r = run("Взялась! Сообщу, когда презентация будет готова.")
    ok("Поправлюсь" not in r["said"] + r["bot"], f"телефон: «взялась, сообщу» — без поправки: {r['bot']}")
    r = run("")
    ok("Задача передана — пришлю уведомление" in r["said"] + r["bot"] and "Сделала" not in r["said"] + r["bot"], f"телефон: модель промолчала — «Задача передана», а не «Сделала»: {r}")
    q = pg.evaluate("""async () => { const r = await runTool("start_task", { title: "Отчёт", goal: "Сделай отчёт" }); return r; }""")
    ok("Результата ЕЩЁ НЕТ" in q, "телефон: инструмент говорит модели, что результата ещё нет")
    ok(not errs, f"без ошибок на странице: {errs[:3]}")
    b.close()
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
