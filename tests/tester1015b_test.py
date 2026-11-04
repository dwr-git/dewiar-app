"""Экзамены 15.10 (компьютер 0.38.47, телефон 0.6.40) и скриншот пользователя Windows («не обновляется у него»):
— «Запомни: в среду в 15:00 у меня встреча с подрядчиком» на телефоне — сразу в память с точной датой, без модели (модель
  спрашивала про календарь, и через новый разговор «что у меня в среду?» — «пусто»);
— «Вспомни, что я говорил про работу» на компьютере — и по прошлым разговорам: модель сказала «записала», не записав;
— «Нарисуй схему» — телефон заранее говорит модели, что схема — только блок ```mermaid (была «Схема готова, она уже на
  экране» без схемы; компьютер — promise_test);
— Windows: нажали «обновить», а после перезапуска версия прежняя — виджет так и говорит и открывает установщик обычным
  окном (в нём видно, что мешает), а не предлагает снова ту же тихую установку."""
import json, os, re, shutil, subprocess, sys, tempfile, time
from datetime import datetime, timedelta
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ.update(DEWIAR_WORKSPACE_DIR=str(tmp / "ws"), DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_CONFIG_DIR=str(tmp / "cfg"))
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


# ── 1. компьютер: «вспомни, что я говорил про работу» — и по ленте разговоров ──
import tools as T  # noqa: E402
from chatlog import ChatLog  # noqa: E402
from workspace import Workspace  # noqa: E402
cl = ChatLog(tmp / "chat.jsonl")
now = time.time()
cl.items = [
    {"id": "1", "ts": now - 3 * 86400, "role": "user", "text": "Какая погода в Минске?"},
    {"id": "2", "ts": now - 600, "role": "user", "text": "На работе у меня сейчас три дела: сдать отчёт по продажам в пятницу, нанять дизайнера и обновить сайт."},
    {"id": "3", "ts": now - 590, "role": "assistant", "text": "Поняла. Записала."},
    {"id": "4", "ts": now - 500, "role": "user", "text": "И ещё начальник просил подготовить презентацию для инвесторов."},
    {"id": "5", "ts": now - 30 * 86400, "role": "user", "text": "Работа над ремонтом идёт медленно."},
]
ws = Workspace(None)
r = T.t_find_notes({"query": "работа"}, {"workspace": ws, "chatlog": cl})
ok("отчёт по продажам" in r and "презентацию для инвесторов" in r, f"сказанное в прошлом разговоре нашлось, и соседняя реплика без слова «работа»: {r[-260:]!r}")
ok("погода" not in r and "ремонтом" not in r and "Записала" not in r, "чужие разговоры, давнее (месяц) и ответы ассистента — не подмешиваются")
ok(T._chat_hits({"chatlog": cl}, "рыбалка") == "", "ничего не нашлось — тишина")
ok('self.toolbox.hooks["chatlog"] = self.chatlog' in (ROOT / "core/engine.py").read_text(encoding="utf-8"), "ядро даёт find_notes ленту разговоров")

# ── 2. Windows: обновление не встало ──
import updater as U  # noqa: E402
ud = tmp / "upd"; (ud / "updates").mkdir(parents=True)
(ud / "updates/Dewiar-Setup-0.38.47.exe").write_bytes(b"MZ")
(ud / "updates/pending.json").write_text(json.dumps({"file": "Dewiar-Setup-0.38.47.exe", "ts": time.time()}))
u = U.Updater(None, "0.38.40", ud)
f = u.public()["failed"]
ok(f and f["version"] == "0.38.47" and f["path"].endswith("Dewiar-Setup-0.38.47.exe") and not (ud / "updates/pending.json").exists(),
   f"после «обновить» запустилась прежняя версия — ядро это знает: {f}")
(ud / "updates/pending.json").write_text(json.dumps({"file": "Dewiar-Setup-0.38.47.exe", "ts": time.time()}))
ok(U.Updater(None, "0.38.47", ud).public()["failed"] is None, "встала — тишина")
(ud / "updates/pending.json").write_text(json.dumps({"file": "Dewiar-Setup-0.38.47.exe", "ts": time.time() - 10 * 86400}))
ok(U.Updater(None, "0.38.40", ud).public()["failed"] is None, "метка давняя (больше недели) — не вспоминаем")
app_src = (ROOT / "ui/app.py").read_text(encoding="utf-8")
ok('(allowed / "pending.json").write_text' in app_src and "def run_installer(self, path)" in app_src and "os.startfile(str(p))" in app_src,
   "окно перед тихой установкой ставит метку; «открыть установщик» — только скачанный файл, обычным окном")

# ── 3. виджет и телефон в браузере ──
www = tmp / "www"
shutil.copytree(ROOT / "android/assets/www", www)
for x in ("entities.js", "rich.js", "skins.js", "skins.css"):
    if (ROOT / "ui/assets" / x).exists():
        shutil.copy(ROOT / "ui/assets" / x, www / x)
shutil.copytree(ROOT / "ui/assets/live", www / "live", dirs_exist_ok=True)
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                capture_output=True, text=True, check=True).stdout, encoding="utf-8")
errs, seen = [], []
WD = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
MON = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"]


def llm_route(route):
    req = route.request
    if req.method == "OPTIONS":
        return route.fulfill(status=204, headers={"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*", "Access-Control-Allow-Methods": "*"})
    body = json.loads(req.post_data or "{}"); seen.append(body.get("messages") or [])
    d = {"choices": [{"delta": {"content": "Вот:\n```mermaid\nflowchart LR\n  A[\"Клиент\"] --> B[\"Склад\"]\n```"}}]}
    route.fulfill(status=200, body=f"data: {json.dumps(d, ensure_ascii=False)}\n\ndata: [DONE]\n\n",
                  headers={"Access-Control-Allow-Origin": "*", "Content-Type": "text/event-stream"})


with sync_playwright() as p:
    b = p.chromium.launch()
    # виджет: баннер «не установилось»
    hw = b.new_page(viewport={"width": 300, "height": 420})
    hw.on("pageerror", lambda x: errs.append("виджет: " + str(x)))
    hw.add_init_script("window.__inst = []; window.pywebview = { api: { run_installer: (p) => { window.__inst.push(p); return Promise.resolve({ ok: true }); },"
                       " install_update: () => Promise.resolve({ ok: true }), save_pos: () => Promise.resolve([0, 0]), get_pos: () => Promise.resolve([0, 0]),"
                       " set_mode: () => Promise.resolve(null), set_zoom: () => Promise.resolve(null) } };")
    hw.goto((ROOT / "ui/hud.html").as_uri() + "?token=x&port=9&mode=card"); hw.wait_for_timeout(1200)
    hw.evaluate("() => showUpd({ current: '0.38.40', failed: { version: '0.38.47', path: 'C:/Users/a/AppData/Local/Dewiar/updates/Dewiar-Setup-0.38.47.exe' },"
                " available: { version: '0.38.47', path: 'C:/x.exe' } })")
    t1 = hw.evaluate("() => [document.getElementById('upd').classList.contains('on'), document.getElementById('upd').textContent]")
    ok(t1[0] and "0.38.47 не установилось" in t1[1] and "установщик" in t1[1], f"виджет говорит, что обновление не встало: {t1}")
    hw.click("#upd"); hw.wait_for_timeout(300)
    t2 = hw.evaluate("() => [window.__inst, document.getElementById('upd').textContent]")
    ok(t2[0] == ["C:/Users/a/AppData/Local/Dewiar/updates/Dewiar-Setup-0.38.47.exe"] and "Установщик открыт" in t2[1],
       f"нажали — открыт скачанный установщик (не тихая установка заново): {t2}")
    hw.evaluate("() => showUpd({ current: '0.38.40', available: { version: '0.38.48', path: 'C:/y.exe' } })")
    ok("Доступна версия 0.38.48" in hw.evaluate("() => document.getElementById('upd').textContent"), "обычное обновление — как раньше")
    # телефон
    pg = b.new_page(viewport={"width": 400, "height": 820})
    pg.on("pageerror", lambda x: errs.append("телефон: " + str(x)))
    pg.route("http://127.0.0.1:9/**", llm_route)
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(1000)
    pg.evaluate("() => { Object.assign(S.llm, { kind: 'openai', base_url: 'http://127.0.0.1:9/v1', model: 'm', name: 'тест', cloud: false }); saveS(); }")
    wed = datetime.now() + timedelta(days=(2 - datetime.now().weekday()) % 7 or 7)   # ближайшая среда (сегодня среда — следующая)
    Q = pg.evaluate("async () => { const r = await quick('Запомни, пожалуйста: в среду в 15:00 у меня встреча с подрядчиком по кухне.'); return [r && r.say, S.memory.slice(-1)[0]]; }")
    ok(Q[0] and Q[0].startswith(("Запомнила", "Запомнил")) and "в среду, " in Q[0], f"«запомни: в среду…» — сразу, без модели, с днём: {Q[0]}")
    ok(Q[1] and "встреча с подрядчиком по кухне" in Q[1] and re.search(r"\(на \d\d\.\d\d\.\d{4}, среда\)", Q[1]), f"в памяти — с точной датой: {Q[1]}")
    if Q[1] and datetime.now().weekday() != 2:
        ok(f"{wed:%d.%m.%Y}" in Q[1], f"дата — ближайшая среда {wed:%d.%m}: {Q[1]}")
    N = pg.evaluate("""async () => { const out = []; for (const t of ['Запомни это', 'Запомни про отпуск', 'Запомни, что Земля круглая', 'Запомни, где я оставил ключи?',
        'Запиши в заметки: купить хлеб']) { const r = await quick(t); out.push([t, r && r.say || '']); } return out; }""")
    ok(all(not s.startswith("Запомн") for _, s in N), f"«запомни это», «про…», не о себе и вопросы — не сюда (решает модель): {N}")
    ok(N[-1][1].startswith("Записал"), f"«запиши в заметки» — по-прежнему заметкой: {N[-1]}")
    # «нарисуй схему» — модель заранее знает про mermaid
    pg.evaluate("t => { window._done = false; ask(t).then(() => window._done = true, () => window._done = true); }",
                "Нарисуй схему: как заявка проходит от клиента через менеджера на склад и обратно клиенту.")
    for _ in range(100):
        pg.wait_for_timeout(100)
        if pg.evaluate("window._done && state === 'idle'"):
            break
    # 04.11 «Голос без пауз»: подсказка к просьбе — в справке к вопросу (последнее сообщение), подсказка остаётся прежней
    sysm = (str(seen[0][0].get("content")) + "\n" + str(seen[0][-1].get("content"))) if seen else ""
    ok("СЕЙЧАС ПРОСЯТ СХЕМУ" in sysm and "не делай схему через make_app" in sysm, "телефон: просят схему — модель заранее знает, что рисует только ```mermaid")
    ok(len(seen) == 1, f"нарисовала сразу — без второго запроса: {len(seen)}")
    b.close()
ok(not errs, "без ошибок JavaScript" + (f": {errs}" if errs else ""))
shutil.rmtree(tmp, ignore_errors=True)
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
