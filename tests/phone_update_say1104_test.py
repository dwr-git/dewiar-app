"""№519 (04.11, телефон 0.9.18, «Раньше сама обновлялась, сейчас нет»; на «обновись» модель ответила «Я не могу обновить
саму себя»). «Обновись», «проверь обновления», «есть новая версия?» — делом и без модели: есть новее — «Есть новая версия
X — обновляю» и открывается обновление; нет — «У вас последняя версия». Обычные фразы со словом «обнови» сюда не попадают.
№528 (04.11, владелец, снимок): на «обновись» Лира ответила моделью «Я не могу обновить себя самостоятельно — я уже работаю
на актуальной версии». Фраза была сказана в 09:25 на 0.9.20 (журнал: «что нового: 0.9.18 → 0.9.20» в 08:38, 0.9.21 — только
в 16:47) — быстрого ответа тогда ещё не было. Теперь фраз больше («обновись до последней», «обнови себя», «проверь, есть ли
новая версия», «у тебя последняя версия?», «какая у тебя версия»), а что мимо — у модели действие app_update, правило в
подсказке и проверка: «я на актуальной версии» без app_update — переспрос «проверь по-настоящему»."""
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


tmp = Path(tempfile.mkdtemp()); www = tmp / "www"
shutil.copytree(ROOT / "android/assets/www", www)
for x in ("entities.js", "rich.js", "skins.js", "skins.css", "privacy.js", "closecrypto.js", "qrcode.js", "call.js", "codes.js"):
    if (ROOT / "ui/assets" / x).exists():
        shutil.copy(ROOT / "ui/assets" / x, www / x)
shutil.copytree(ROOT / "ui/assets/live", www / "live", dirs_exist_ok=True)
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                capture_output=True, text=True, check=True).stdout, encoding="utf-8")
LATEST = {"v": "0.9.99"}
errs = []
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 390, "height": 844})
    pg.on("pageerror", lambda x: errs.append(str(x)))
    pg.route("https://dewiar.pro/dwrapp/latest.json", lambda r: r.fulfill(status=200, body=json.dumps({"android": {"version": LATEST["v"], "apk": "Dewiar.apk", "sha256": "x"}}),
                                                                      headers={"Access-Control-Allow-Origin": "*", "Content-Type": "application/json"}))
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(1000)
    pg.evaluate("() => { const i = D.info; D.info = () => JSON.stringify(Object.assign(JSON.parse(i ? i() || '{}' : '{}'), { version: '0.9.18' })); window.updChecked = 0; const c = checkUpdate; checkUpdate = (m) => { updChecked++; return c(m); }; window.updGets = 0; D.updateGet = () => { updGets++; }; }")
    # рецензия 0.82: «проверь обновления», «есть новая версия?» — сказать и показать, но не скачивать
    for q in ("Лира, проверь обновления", "есть новая версия?", "обновление есть?"):
        r = pg.evaluate("async (q) => (await quick(q)) || null", q)
        pg.wait_for_timeout(900)
        ok(r and "0.9.99" in r["say"] and "обновись" in r["say"] and "обновляю" not in r["say"] and pg.evaluate("updGets") == 0,
           f"«{q}» при новой версии — «Скажите „обновись“», без скачивания: {r and r['say']}")
    ok(pg.evaluate("updChecked") >= 1 and pg.evaluate("!!document.querySelector('#upd-go')"), "«О приложении» открыто, кнопка «Обновить» — для человека")
    pg.evaluate("() => { const s = document.querySelector('#sh-set'); if (s) s.classList.remove('on'); }")
    for q in ("Обновись", "Лира, обнови приложение", "установи обновление"):
        pg.evaluate("window.updGets = 0")
        r = pg.evaluate("async (q) => (await quick(q)) || null", q)
        ok(r and "0.9.99" in r["say"] and "обновляю" in r["say"], f"«{q}» при новой версии — делом, без модели: {r}")
        pg.wait_for_timeout(900)
        ok(pg.evaluate("updGets") == 1, f"«{q}» — скачивание началось (открыто «О приложении», «Обновить»)")
    # детский режим: не скачиваем и PIN не просим
    pg.evaluate("() => { window.updGets = 0; window.pinAsked = 0; const kp = kidsPin; kidsPin = (t) => { pinAsked++; }; S.kids = Object.assign({}, S.kids || {}, { on: true }); }")
    r = pg.evaluate("async () => (await quick('Обновись')) || null")
    pg.wait_for_timeout(900)
    ok(r and "взрослый" in r["say"] and pg.evaluate("updGets") == 0 and pg.evaluate("pinAsked") == 0,
       f"детский режим: «Обновление ставит взрослый», без скачивания и PIN: {r and r['say']}")
    pg.evaluate("() => { S.kids.on = false; }")
    LATEST["v"] = "0.9.18"
    r = pg.evaluate("async () => (await quick('Лира, проверь обновления')) || null")
    ok(r and "последняя версия" in r["say"] and "0.9.18" in r["say"], f"«проверь обновления» без новой — «У вас последняя версия»: {r}")
    for q in ("есть новая версия?", "обнови приложение"):
        r = pg.evaluate("async (q) => (await quick(q)) || null", q)
        ok(r and "последняя версия" in r["say"], f"«{q}» — тоже: {r and r['say']}")
    # №528: больше фраз — и всё без модели
    LATEST["v"] = "0.9.99"
    for q in ("Лира, обновись до последней версии", "обнови себя", "обновись, пожалуйста", "поставь новую версию", "давай обновимся"):
        pg.evaluate("window.updGets = 0")
        r = pg.evaluate("async (q) => (await quick(q)) || null", q)
        pg.wait_for_timeout(900)
        ok(r and "обновляю" in r["say"] and pg.evaluate("updGets") == 1, f"№528: «{q}» — обновляет: {r and r['say']}")
        pg.evaluate("() => { const s = document.querySelector('#sh-set'); if (s) s.classList.remove('on'); }")
    for q in ("Проверь, есть ли новая версия", "у тебя последняя версия?", "ты на последней версии?", "какая у тебя версия", "проверь наличие обновлений", "вышла новая версия?"):
        pg.evaluate("window.updGets = 0")
        r = pg.evaluate("async (q) => (await quick(q)) || null", q)
        pg.wait_for_timeout(700)
        ok(r and "0.9.99" in r["say"] and "обновляю" not in r["say"] and pg.evaluate("updGets") == 0, f"№528: «{q}» — проверяет и говорит, без скачивания: {r and r['say']}")
    LATEST["v"] = "0.9.18"
    for q in ("обнови список покупок", "обновись в заметке про ремонт", "какая версия андроида у меня", "расскажи про новую версию айфона"):
        r = pg.evaluate("async (q) => (await quick(q)) || null", q)
        ok(not r or "верси" not in (r.get("say") or ""), f"«{q}» — не про обновление программы")
    # что мимо быстрых фраз — модель: действие app_update, правило в подсказке, проверка «не проверив»
    ok(pg.evaluate("() => toolSpecs().some(t => t.name === 'app_update')") and "app_update" in pg.evaluate("systemStable()"),
       "у модели — действие app_update и правило «версия и обновление — только через него»")
    r = pg.evaluate("async () => await runTool('app_update', { action: 'check' })")
    ok("последняя версия" in r and "0.9.18" in r, f"app_update check — по-настоящему с сайта: {r}")
    fix = pg.evaluate("() => updateClaim('слушай, ты сама обновляешься или мне надо что-то сделать, чтобы была новая версия?', 'Я не могу обновить себя самостоятельно — я уже работаю на актуальной версии.', new Set())")
    ok(fix.startswith("ПРОВЕРКА") and "app_update" in fix, "«я на актуальной версии» без app_update — переспрос «проверь»")
    ok(not pg.evaluate("() => updateClaim('обновись', 'У вас последняя версия.', new Set(['app_update']))")
       and not pg.evaluate("() => updateClaim('расскажи про новую версию айфона', 'В последней версии iOS…', new Set())"),
       "проверено app_update или речь не о приложении — без переспроса")
    # весь ход: модель отвечает «я на актуальной версии» — переспрос, вызов app_update, итог по нему
    pg.evaluate("""() => { S.llm.base_url = 'https://api.example-llm.ai/v1'; S.llm.model = 'm'; S.llm.kind = 'openai'; S.llm.cloud = false; window.seen2 = [];
        const sse = (t) => 'data: ' + JSON.stringify({ choices: [{ delta: { content: t } }] }) + '\\n\\ndata: [DONE]\\n\\n';
        const call = 'data: ' + JSON.stringify({ choices: [{ delta: { tool_calls: [{ index: 0, id: 'u1', function: { name: 'app_update', arguments: '{"action":"check"}' } }] } }] }) + '\\n\\ndata: [DONE]\\n\\n';
        const real = window.http;
        window.http = async (m, u, o) => { if (!/example-llm/.test(u)) return real(m, u, o);
          const b = typeof o.body === 'string' ? JSON.parse(o.body) : o.body; seen2.push(b); const last = JSON.stringify(b.messages.slice(-1));
          o.onChunk(last.includes('"role":"tool"') ? sse('Проверила: у вас последняя версия.') : last.includes('ПРОВЕРКА') ? call : sse('Я не могу обновить себя сама — я уже работаю на актуальной версии.'));
          return { status: 200, body: '' }; }; }""")
    pg.evaluate("async () => { await ask('слушай, а ты вообще сама обновляешься до новой версии или нет'); }")
    hist = pg.evaluate("() => history.slice(-1)[0].content")
    n2 = pg.evaluate("seen2.length")
    ok(n2 == 3 and "Проверила" in hist and "актуальной версии" not in hist, f"ход целиком: «актуальная версия» не проверив → app_update → итог по нему ({n2} запроса): {hist}")
    ok(not errs, f"без ошибок: {errs}")
    b.close()
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
