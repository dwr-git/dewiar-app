"""№529 (04.11, McDuck, телефон 0.9.21, Xiaomi, обновился с 0.9.16): «С последним обновлением абсолютно отказывается
что-либо делать — это просто чат-бот». Мозг — своя модель (mercury-3 у api.inceptionlabs.ai по ключу).

Что показал журнал отчёта: действия модели уходили и выполнялись (web_search, read_webpage, open_url, open_app), но
1) в 16:48:32 человек прислал скриншот («Посмотри, пожалуйста.»), модель без зрения — сервер отказал (400), а телефон
   принял отказ за «сервер не понимает поле tools» и НАВСЕГДА перешёл на «действия текстом» (в настройках отчёта —
   tools_prompt этого сервера). Сразу после: ответ 16 749 знаков за 5 с и пять ответов подряд без единого действия;
2) «Управлять приложениями» выключено (phone_screen трижды: «выключено»), а человек уверен, что всё включено («всё у тебя
   открыто») — после обновления Android (особенно MIUI) отключает эту службу; модель открывала «Настройки» и вставала.
Сравнение 0.9.16 / 0.9.20 / 0.9.21 на заглушке модели: запросы одинаковые (47 действий полем tools или текстом, tool_choice
auto, вызовы не теряются; личная справка — в первом сообщении, ~1 тыс. знаков), stream_options такому сервису не шлётся —
«Голос без пауз» ни при чём. Причина — запоминание «действий текстом» по отказу, который был вовсе не про действия.

Теперь: отказ из-за фото, имени модели, ключа или окна — не меняет способ передачи действий («нет такой модели» — понятной
фразой); «действия текстом» помнятся для этого сервера, модели и версии приложения — после обновления или смены модели
снова поле tools; переход и ответ без действий — строкой в журнале. Руки: телефон помнит, что они работали, и говорит
прямо «после обновления Android отключил — включите снова» (и карточкой на главном экране), «служба не запущена — выключите
и включите». И в отчёте больше нет ключа «Дома по Wi-Fi» (sync.home k/t/h были как есть)."""
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
for x in ("entities.js", "rich.js", "skins.js", "skins.css"):
    if (ROOT / "ui/assets" / x).exists():
        shutil.copy(ROOT / "ui/assets" / x, www / x)
shutil.copytree(ROOT / "ui/assets/live", www / "live", dirs_exist_ok=True)
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                capture_output=True, text=True, check=True).stdout, encoding="utf-8")
PIX = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
SETUP = """(pix) => {
  const base = "https://api.example-llm.ai/v1";
  window.BASE = base; window.PIX = pix;
  Object.assign(S.llm, { kind: "openai", name: "api.example-llm.ai", base_url: base, model: "mercury-3", cloud: false, no_kwargs: true });
  delete S.llm.tools_prompt; delete S.llm.tp_mark; S.onboarded = true; saveS();
  window.seen = []; window.srv = { rejectImage: "Bad Request", rejectTools: "", rejectAll: "", model: "" };
  const sse = (t) => t.match(/[\\s\\S]{1,9}/g).map(c => "data: " + JSON.stringify({ choices: [{ delta: { content: c } }] }) + "\\n\\n").join("") + "data: [DONE]\\n\\n";
  const sseCall = (name, args) => "data: " + JSON.stringify({ choices: [{ delta: { tool_calls: [{ index: 0, id: "c1", function: { name, arguments: JSON.stringify(args) } }] } }] }) + "\\n\\ndata: " + JSON.stringify({ choices: [{ delta: {}, finish_reason: "tool_calls" }] }) + "\\n\\ndata: [DONE]\\n\\n";
  const bad = (m) => ({ status: 400, body: JSON.stringify({ error: { message: m } }) });
  const real = window.http;
  window.http = async (m, u, o) => {
    if (!/example-llm/.test(u)) return real(m, u, o);
    const body = typeof o.body === "string" ? JSON.parse(o.body) : o.body; seen.push(body);
    const all = JSON.stringify(body.messages);
    if (srv.model && body.model !== srv.model) return bad(`The model \\`${body.model}\\` does not exist or you do not have access to it.`);
    if (srv.rejectAll) return bad(srv.rejectAll);
    if (srv.rejectImage && all.includes("image_url")) return bad(srv.rejectImage);
    if (srv.rejectTools && body.tools) return bad(srv.rejectTools);
    const last = body.messages[body.messages.length - 1];
    const toolResp = last.role === "tool" || /<tool_response>/.test(JSON.stringify(last));
    let s;
    if (toolResp) s = sse("Нашла: OlliteRT.");
    else if (/модел|гитхаб/i.test(JSON.stringify(last.content)) && body.tools) s = sseCall("web_search", { query: "local llm android" });
    else if (/модел|гитхаб/i.test(JSON.stringify(last.content)) && /<tools>/.test(body.messages[0].content)) s = sse('<tool_call>\\n{"name": "web_search", "arguments": {"query": "local llm android"}}\\n</tool_call>');
    else s = sse("Не вижу картинок — выберите модель со зрением.");
    o.onChunk && o.onChunk(s); return { status: 200, body: "" };
  };
  window.runTool = async (n, a) => (window.ran = (window.ran || []).concat(n), "Найдено: OlliteRT — github.com/NightMean/OlliteRT");
  history = []; saveH();
}"""
Q = "найди на гитхаб варианты локальной модели для телефона"
LAST = "() => ({ answer: (history[history.length - 1] || {}).content || '', bot: document.querySelector('#bot').textContent })"
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 390, "height": 844}); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(900)
    pg.evaluate(SETUP, PIX)

    # ---------- 1. скриншот модели без зрения: отказ из-за фото — не повод переходить на «действия текстом» ----------
    for why in ("Bad Request", "Invalid content: image_url is only supported by certain models"):
        pg.evaluate("(w) => { delete S.llm.tools_prompt; delete S.llm.tp_mark; srv.rejectImage = w; seen.length = 0; window.ran = []; }", why)
        pg.evaluate("async () => { await ask('Посмотри, пожалуйста.', { attach: [{ kind: 'image', name: 'фото', url: PIX }] }); }")
        st = pg.evaluate("() => ({ tp: S.llm.tools_prompt || null, n: seen.length, kw: S.llm.no_kwargs })")
        ok(st["tp"] is None, f"фото, отказ «{why}» — способ передачи действий не меняется (tools_prompt: {st['tp']}, запросов {st['n']})")
        pg.evaluate("async (q) => { seen.length = 0; await ask(q); }", Q)
        q = pg.evaluate("() => seen[0]")
        ok(len(q.get("tools") or []) > 30 and q.get("tool_choice") == "auto" and "<tools>" not in q["messages"][0]["content"],
           f"следующий вопрос — действия полем tools ({len(q.get('tools') or [])}), tool_choice auto")
        ok(pg.evaluate("window.ran") == ["web_search"] and "OlliteRT" in pg.evaluate(LAST)["answer"], "вызов из ответа не потерялся — поиск выполнен, ответ по найденному")

    # ---------- 2. опечатка в имени модели — понятной фразой, флаги не трогаем ----------
    pg.evaluate("() => { srv.model = 'mercury-3'; S.llm.model = 'mercuri-3'; S.llm.no_kwargs = false; delete S.llm.tools_prompt; seen.length = 0; }")
    pg.evaluate("async (q) => { await ask(q); }", Q)
    st = pg.evaluate("() => ({ tp: S.llm.tools_prompt || null, kw: !!S.llm.no_kwargs, n: seen.length, bot: document.querySelector('#bot').textContent })")
    ok(st["tp"] is None and not st["kw"], f"«модели не существует» — ни «действий текстом», ни «без chat_template_kwargs»: {st}")
    ok("mercuri-3" in st["bot"] and "имя модели" in st["bot"] and st["n"] == 1, f"человеку — что поправить, одним запросом: {st['bot'][:140]}")
    pg.evaluate("() => { srv.model = ''; S.llm.model = 'mercury-3'; S.llm.no_kwargs = true; }")

    # ---------- 3. отметка «действия текстом» из 0.9.21 (без модели и версии) — после обновления снова полем tools ----------
    pg.evaluate("() => { S.llm.tools_prompt = BASE; delete S.llm.tp_mark; srv.rejectTools = ''; seen.length = 0; window.ran = []; }")
    pg.evaluate("async (q) => { await ask(q); }", Q)
    q = pg.evaluate("() => seen[0]")
    ok(len(q.get("tools") or []) > 30 and pg.evaluate("window.ran") == ["web_search"], "старая отметка (как в отчёте №529) — сначала снова полем tools, действие выполнено")
    # сервер правда не принимает tools — текстом; отметка с моделью и версией, следующий вопрос — сразу текстом
    pg.evaluate("() => { delete S.llm.tools_prompt; delete S.llm.tp_mark; srv.rejectTools = '\"auto\" tool choice requires --enable-auto-tool-choice'; seen.length = 0; window.ran = []; }")
    pg.evaluate("async (q) => { await ask(q); }", Q)
    st = pg.evaluate("() => ({ tp: S.llm.tools_prompt, mark: S.llm.tp_mark, want: toolsMark(), n: seen.length, log: PLOG.filter(l => l.includes('🛠')).slice(-1)[0] || '' })")
    ok(st["tp"] == "https://api.example-llm.ai/v1" and st["mark"] == st["want"] and "mercury-3|" in st["mark"],
       f"не принял поле tools — «действия текстом» для этого сервера, модели и версии: {st['mark']}")
    ok("не принял действия полем tools" in st["log"], f"переход — строкой в журнале: {st['log'][-120:]}")
    pg.evaluate("async (q) => { seen.length = 0; window.ran = []; await ask(q); }", Q)
    q = pg.evaluate("() => seen")
    sys0 = q[0]["messages"][0]["content"]
    users = [m for m in q[0]["messages"] if m["role"] == "user"]
    lastu = users[-1]["content"] if isinstance(users[-1]["content"], str) else json.dumps(users[-1]["content"], ensure_ascii=False)
    ok(not q[0].get("tools") and "<tools>" in sys0 and sys0.count('"name":') > 30, f"дальше — сразу текстом: описания действий в подсказке ({sys0.count('\"name\":')})")
    ok(lastu.endswith(Q) and len(lastu) < len(Q) + 3000, f"вопрос — в конце своего сообщения, справка перед ним небольшая ({len(lastu)} знаков)")
    ok(pg.evaluate("window.ran") == ["web_search"] and "OlliteRT" in pg.evaluate(LAST)["answer"], "вызов текстом <tool_call> разобран и выполнен")
    pg.evaluate("() => { S.llm.model = 'mercury-3-mini'; seen.length = 0; }")
    pg.evaluate("async (q) => { await ask(q); }", Q)
    ok(pg.evaluate("() => !!seen[0].tools"), "сменили модель — снова сначала полем tools")
    pg.evaluate("() => { S.llm.model = 'mercury-3'; }")
    # и текстом не принял — ответ без действий, но в журнале видно почему
    pg.evaluate("() => { srv.rejectTools = ''; srv.rejectAll = ''; S.llm.tools_prompt = BASE; S.llm.tp_mark = toolsMark(); window._n = 0; const h = window.http; window.http = async (m, u, o) => { const b = typeof o.body === 'string' ? JSON.parse(o.body) : o.body; if (/example-llm/.test(u) && /<tools>/.test(b.messages[0].content)) { seen.push(b); return { status: 400, body: JSON.stringify({ error: { message: 'Bad Request' } }) }; } return h(m, u, o); }; }")
    pg.evaluate("async (q) => { await ask(q); }", Q)
    ok(any("этот ответ без действий" in l for l in pg.evaluate("PLOG.slice(-6)")), "отказ и текстом — «этот ответ без действий» в журнале")

    # ---------- 4. руки: были включены, после обновления выключились ----------
    pg.evaluate("() => { window.HS = 'on'; D.handsState = () => HS; D.handsScreen = () => HS === 'on' ? 'Настройки: 1 [кнопка] О телефоне' : 'OFF'; delete S.handsOk; showCard(''); }")
    pg.evaluate("() => handsWatch(true)")
    hl = pg.evaluate("PLOG.slice(-3)")
    ok(pg.evaluate("S.handsOk") is True and any("🖐 управлять приложениями: включено" in l for l in hl), f"руки работают — запомнено, в журнале строка состояния: {hl}")
    pg.evaluate("() => { HS = ''; handsLogged = handsCardShown = false; busy = false; closeSheets(); showCard(''); }")
    pg.evaluate("() => handsWatch(true)")
    lg = pg.evaluate("PLOG.slice(-2)")
    ok(any("выключено" in l for l in lg) and any("похоже, после обновления" in l for l in lg), f"после обновления выключилось — в журнале: {lg}")
    ok(pg.evaluate("!!document.querySelector('#card .hands-lost #hands-again')"), "карточка «Управлять приложениями — выключено» с кнопкой «Включить»")
    off = pg.evaluate("async () => await handsTool('phone_screen', {})")
    ok("после обновления" in off and "включите снова" in off, f"phone_screen модели — «после обновления… включите снова»: {off[:90]}")
    pg.evaluate("() => { HS = 'pending'; }")
    pend = pg.evaluate("async () => await handsTool('phone_screen', {})")
    ok("служба не запустилась" in pend and "выключить и включить снова" in pend, f"включено, но не запущено — «выключить и включить снова»: {pend[:90]}")
    pg.evaluate("() => { HS = ''; delete S.handsOk; }")
    ok("Управление другими приложениями выключено" in pg.evaluate("async () => await handsTool('phone_screen', {})"), "никогда не включали — прежнее объяснение, как включить")

    # ---------- 5. отчёт: ключ и токен «Дома по Wi-Fi» — звёздочками ----------
    pg.evaluate("() => { S.sync = Object.assign({}, S.sync, { home: { u: ['http://192.168.0.5:8766/'], t: 'tok123secret', k: 'KEYbase64secretvalue', h: 'hh99', n: 'PC' } }); window.repBody = '';"
                " const h = window.http; window.http = async (m, u, o) => { if (/report/.test(u)) { repBody = typeof o.body === 'string' ? o.body : JSON.stringify(o.body); return { status: 200, body: '{}' }; } return h(m, u, o); }; }")
    pg.evaluate("async () => { try { await reportSend('проверка', false); } catch (e) { } }")
    rb = pg.evaluate("repBody")
    ok(rb and "KEYbase64secretvalue" not in rb and "tok123secret" not in rb and "hh99" not in rb, "в отчёте нет ключа, токена и номера связки «Дома по Wi-Fi»")
    ok(not errs, f"без ошибок на странице: {errs}")
    b.close()
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
