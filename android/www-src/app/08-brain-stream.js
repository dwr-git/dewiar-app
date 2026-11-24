//@ Телефон и веб-версия, часть 08: мозг: ответ модели потоком, история для модели, починка JSON, речь по фразам.
//@ Собирается в android/assets/www/app.js (tools/app_join.py) — порядок частей = порядок исполнения; шапка «//@» в app.js не попадает.
/* ---------- мозг: ответ модели потоком ---------- */
/* Ответ модели потоком (OpenAI-совместимый /chat/completions или Ollama /api/chat). onText(кусок) — текст по мере прихода,
   уже без размышлений и вызовов функций текстом; -> {text, calls:[{id,name,args}]} */
var turnServers = new Set();                        // серверы облака, отвечавшие в этом ходе (экзамен: строка «сервер»)
/* №989 (24.11): «модель ответила 400: Invalid Unicode (unpaired surrogate)» на каждый вопрос. Тексты в истории и памяти
   обрезаются по длине (slice), а эмодзи — две половинки: обрезка по середине оставляет одну, и сервер не принимает запрос.
   Перед отправкой — каждую оборванную половинку заменяем знаком «�» (без «взгляда назад» — старый Safari). */
const wfStr = (s) => s.replace(/[\ud800-\udbff][\udc00-\udfff]|[\ud800-\udfff]/g, (m) => m.length === 2 ? m : "\ufffd");
function wellFormed(o) {
  if (typeof o === "string") return wfStr(o);
  if (Array.isArray(o)) return o.map(wellFormed);
  if (o && typeof o === "object") { const r = {}; for (const k of Object.keys(o)) r[k] = wellFormed(o[k]); return r; }
  return o;
}
let NO_GZ = "";                         // адрес облака Dewiar, не принявший сжатый запрос (сайт старше 1.0.67)
async function llmStream(messages, tools, onText, signal, opt = {}) {
  const model = await resolveModel();
  const think = opt.think != null ? !!opt.think : thinkMode() === "on";
  const limit = opt.max || (think ? (tools && tools.length ? 8192 : 6144) : tools && tools.length ? 6144 : 2048);   // размышлениям — запас   // с инструментами — запас на make_app (целый HTML)
  let body, url, ollama = isOllama();
  if (ollama) {
    url = ollamaRoot() + "/api/chat";
    body = { model, stream: true, messages: messages.map(toOllama), options: { temperature: llmTemp(), num_predict: limit } };
    if (!think && !S.llm.no_kwargs) body.think = false;
    if (tools && tools.length) body.tools = tools.map(t => ({ type: "function", function: t }));
  } else {
    url = llmBase() + "/chat/completions";
    /* сервер уже отказывался принимать функции полем (vLLM без --enable-auto-tool-choice, шлюзы) — описываем их текстом,
       ответ «<tool_call>{…}</tool_call>» разбирается ниже так же, как у Qwen и GLM */
    // №529 (04.11): отметка «функции текстом» — для этого сервера, этой модели и этой версии приложения; сменили модель
    // или обновились — сначала снова полем tools (так модели вызывают действия надёжнее), отказ — снова текстом
    const inPrompt = tools && tools.length && S.llm.tools_prompt === llmBase() && S.llm.tp_mark === toolsMark();
    body = { model, stream: true, messages: inPrompt ? promptToolMessages(messages, tools) : messages, max_tokens: limit, temperature: llmTemp() };
    if (!S.llm.no_kwargs && !/openai\.com|openrouter|deepseek|anthropic|googleapis/.test(url)) body.chat_template_kwargs = { enable_thinking: think };
    if (tools && tools.length && !inPrompt) { body.tools = tools.map(t => ({ type: "function", function: t })); body.tool_choice = "auto"; }
    // «Голос без пауз»: сколько токенов в подсказке и сколько сервер взял из кэша — только там, где поле точно понимают
    if (S.llm.no_usage !== llmBase() && (["dewiar", "local", "server"].includes(brainKind()) || /openai\.com|openrouter|deepseek\.com/.test(url))) body.stream_options = { include_usage: true };
  }
  body = wellFormed(body);                          // №989: без «половинок» эмодзи — иначе сервер отвечает 400
  const tAsk = Date.now(); let tFirst = 0, usage = null;
  let hold = null, held = "", text = "", buf = "", inThink = false, gate = true, gbuf = "", tcBuf = "", inTool = false, finish = "", sawReason = false;
  let afterCall = false, dropped = "";      // текст после вызова — сочинённый до результата: не озвучиваем
  const known = new Set((tools || []).map(x => x.name));
  const tcRaw = [];
  const calls = {};
  /* начало ответа придерживаем, пока не ясно: это ответ или рассуждение без тега (…</think> ответ, gpt-oss «assistantfinal») */
  const feedText = (piece) => {
    if (!gate) return feedInner(piece);
    gbuf += piece;
    const m = gbuf.match(FINAL_MARK);
    if (m) { gate = false; inThink = false; return feedInner(gbuf.slice(m.index + m[0].length).replace(/^\s+/, "")); }
    if (/^\s*<think>/.test(gbuf)) { gate = false; return feedInner(gbuf); }
    if (REASON_START.test(gbuf) && gbuf.length < 20000) return;
    if (gbuf.trim().length < 60 && !gbuf.trim().includes("\n")) return;
    gate = false; feedInner(gbuf);
  };
  const gateEnd = () => {
    if (!gate) return; gate = false;
    const letters = gbuf.slice(0, 1500).match(/[A-Za-zА-Яа-яЁё]/g) || [], latin = letters.filter(c => c < "\u0080").length / Math.max(1, letters.length);
    if (REASON_START.test(gbuf) && gbuf.length > 400 && (latin > 0.5 || /пользовател[ьяю](?![а-яё])/i.test(gbuf.slice(0, 300)))) return;   // одно рассуждение без ответа
    feedInner(gbuf);
  };
  /* DeepSeek пишет вызовы функций своим языком DSML (№301, пакет 27.10: в ответе было видно «<｜DSML｜invoke
     name="weather">…», погода не запрашивалась, а температура была выдуманной) — переводим в <tool_call>{json}, как
     DSMLFilter в core/llm.py; начало тега, разрезанное между кусками, придерживаем. */
  const CJK_RX = /[\u3000-\u303f\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uac00-\ud7af\uff00-\uff60]+/g;
  const lastUser = [...(messages || [])].reverse().find(m => m && m.role === "user");
  let lastTxt = lastUser ? (typeof lastUser.content === "string" ? lastUser.content : JSON.stringify(lastUser.content || "")) : "";
  // рецензия 04.11: только сам вопрос — в справке перед ним (память «был в Китае») слова «китай» не в счёт
  for (const mk of ["(Сообщение пользователя)\n", "(Дальше — разговор)\n"]) { const i = lastTxt.lastIndexOf(mk); if (i >= 0) { lastTxt = lastTxt.slice(i + mk.length); break; } }
  const noCjk = !/[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]|китай|япон|корей|иероглиф|chinese|japanese|korean|mandarin|kanji|hanzi/i.test(lastTxt);
  let dsBuf = "", dsIn = false;
  // №348: и «<DSML calls>», «<DSML invoke …>» без «｜», все аргументы — одним JSON в parameter name="arguments"
  const DO = "<\\s*[｜|]?\\s*DSML\\s*[｜|]?\\s*", DC = "<\\/\\s*[｜|]?\\s*DSML\\s*[｜|]?\\s*";
  const DS_OPEN = new RegExp(DO + "(?:function_calls|tool_calls|calls|invoke)\\b"),
    DS_STRAY = new RegExp(DC + "(?:function_calls|tool_calls|calls)\\s*>"),
    DS_END = new RegExp(DC + "(?:function_calls|tool_calls|calls)\\s*>|" + DC + "invoke\\s*>(?![\\s\\S]*" + DO + "invoke)");
  const dsmlCalls = (t) => [...t.matchAll(new RegExp(DO + 'invoke\\s+name="([^"]+)"\\s*>([\\s\\S]*?)(?:' + DC + "invoke\\s*>|$)", "g"))].map(([, name, body]) => {
    const args = {}; for (const [, k, str, v] of body.matchAll(new RegExp(DO + 'parameter\\s+name="([^"]+)"(?:\\s+string="(true|false)")?\\s*>([\\s\\S]*?)' + DC + "parameter\\s*>", "g"))) {
      let x = v.trim(); if (str === "false") { try { x = JSON.parse(x); } catch (e) { } } args[k] = x; }
    const a2 = Object.keys(args).length === 1 && args.arguments && typeof args.arguments === "object" ? args.arguments : args;
    return "<tool_call>" + JSON.stringify({ name, arguments: a2 }) + "</tool_call>"; }).join("");
  const dsmlFeed = (t, last) => {
    dsBuf += t; let o = "";
    for (;;) {
      if (dsIn) { const m = dsBuf.match(DS_END); if (!m) { if (last) { o += dsmlCalls(dsBuf) || dsBuf; dsBuf = ""; dsIn = false; } break; }
        const e = m.index + m[0].length; o += dsmlCalls(dsBuf.slice(0, e)); dsBuf = dsBuf.slice(e); dsIn = false; continue; }
      const sx = dsBuf.match(DS_STRAY), m = dsBuf.match(DS_OPEN);
      if (sx && (!m || sx.index < m.index)) { o += dsBuf.slice(0, sx.index); dsBuf = dsBuf.slice(sx.index + sx[0].length); continue; }
      if (m) { o += dsBuf.slice(0, m.index); dsBuf = dsBuf.slice(m.index); dsIn = true; continue; }
      let keep = 0; if (!last) for (const tag of ["<｜DSML｜invoke", "<｜DSML｜function_calls", "<|DSML|invoke", "<|DSML|function_calls", "<DSML calls", "<DSML invoke", "</DSML calls>", "</DSML function_calls>", "</｜DSML｜function_calls>", "</|DSML|function_calls>"]) for (let k = 1; k < tag.length; k++) if (dsBuf.endsWith(tag.slice(0, k))) keep = Math.max(keep, k);
      o += dsBuf.slice(0, dsBuf.length - keep); dsBuf = dsBuf.slice(dsBuf.length - keep); break;
    }
    return o;
  };
  let thBuf = "";
  const feedInner = (piece, last) => {    // вырезаем <think>…</think> «думающих» моделей (тег может прийти по кусочкам)
    thBuf += piece;
    let out = "";
    for (;;) {
      if (inThink) { const i = thBuf.indexOf("</think>"); if (i < 0) { thBuf = last ? "" : thBuf.slice(-8); break; } inThink = false; thBuf = thBuf.slice(i + 8); continue; }
      const i = thBuf.indexOf("<think>");
      if (i < 0) {
        let keep = 0;
        if (!last) for (let k = 1; k < 9; k++) if (thBuf.endsWith("</think>".slice(0, k)) || thBuf.endsWith("<think>".slice(0, k))) keep = k;
        out += thBuf.slice(0, thBuf.length - keep); thBuf = thBuf.slice(thBuf.length - keep); break;
      }
      out += thBuf.slice(0, i); inThink = true; thBuf = thBuf.slice(i + 7);
    }
    out = out.replace(/<\/think>/g, "").replace(/<\|[a-z_]+\|>/g, "");
    // вызов функции текстом (<tool_call>…</tool_call> — Qwen, GLM): не озвучиваем, разберём в конце
    // и голым JSON {"name": …, "arguments": …} посреди текста, часто с одиноким «</tool_call>» после — как ToolTagStripper в llm.py
    tcBuf += dsmlFeed(out, last); out = "";
    const emit = (t) => { if (afterCall) dropped += t; else out += t; };
    for (;;) {
      if (inTool) { const i = tcBuf.indexOf("</tool_call>"); if (i < 0) break; tcRaw.push(tcBuf.slice(0, i)); tcBuf = tcBuf.slice(i + 12); inTool = false; afterCall = true; continue; }
      const cands = [[tcBuf.indexOf("<tool_call>"), "open"], [tcBuf.indexOf("</tool_call>"), "stray"]].filter(x => x[0] >= 0);
      const bm = known.size ? BARE_CALL_RX.exec(tcBuf) : null; if (bm) cands.push([bm.index, "bare"]);
      if (!cands.length) {
        let keep = 0;
        if (!last) { for (const tag of ["<tool_call>", "</tool_call>"]) for (let k = 1; k < tag.length; k++) if (tcBuf.endsWith(tag.slice(0, k))) keep = Math.max(keep, k);
          const b = known.size ? tcBuf.lastIndexOf("{") : -1;            // «{"name": "mo…» — может оказаться вызовом, придержим
          if (b >= 0 && !tcBuf.slice(b).includes("}") && tcBuf.length - b < 160) keep = Math.max(keep, tcBuf.length - b); }
        emit(tcBuf.slice(0, tcBuf.length - keep)); tcBuf = tcBuf.slice(tcBuf.length - keep); break;
      }
      cands.sort((a, b) => a[0] - b[0]); const [k, kind] = cands[0];
      emit(tcBuf.slice(0, k));
      if (kind === "open") { tcBuf = tcBuf.slice(k + 11); inTool = true; continue; }
      if (kind === "stray") { tcBuf = tcBuf.slice(k + 12); continue; }
      tcBuf = tcBuf.slice(k); const end = jsonEnd(tcBuf);
      if (end < 0) { if (last) { tcRaw.push(tcBuf); tcBuf = ""; afterCall = true; } break; }
      const raw = tcBuf.slice(0, end); let nm = null; try { nm = callName(JSON.parse(raw)); } catch (e) { }
      if (!known.has(nm)) { emit(raw); tcBuf = tcBuf.slice(end); continue; }   // не наша функция — просто текст с JSON
      tcRaw.push(raw); afterCall = true;
      let rest = tcBuf.slice(end).replace(/^\s+/, "");
      if (rest.startsWith("</tool_call>")) rest = rest.slice(12);
      else if (!last && rest && "</tool_call>".startsWith(rest)) { tcBuf = rest; break; }
      tcBuf = rest;
    }
    // №337 (пакет 27.10): «читает вперемешку на разных языках» — иероглифы посреди русского ответа (Gemma, Qwen) — прочь,
    // как drop_cjk на компьютере; если человек сам спросил про китайский/японский или писал иероглифами — оставляем
    if (out && noCjk) out = out.replace(CJK_RX, "");
    if (out) {
      text += out;
      // ответ начинается с «{» или «`» при включённых функциях — возможно, вызов голым JSON: не озвучиваем до конца
      if (hold === null && text.trim()) hold = !!(tools && tools.length) && /^[{`\[]/.test(text.trim());
      if (!hold) { emitT(held + out); held = ""; } else held += out;
    }
  };
  let srv = "", srvModel = "";              // какой сервер облака отвечал и какая модель (21.11) (строка-комментарий «: dewiar-server …», 0.81)
  let netHeld = "";                         // ответ узла «Сети Лиры» — придерживаем целиком, решаем в конце (NET_SUSPECT_RX)
  const emitT = (t) => { if (/^n\d/.test(srv)) netHeld += t; else if (onText) onText(t); };
  const line = (l) => {
    l = l.trim(); if (!l) return;
    if (!tFirst) tFirst = Date.now();
    if (!ollama && l.startsWith(":")) { const m = /^:\s*dewiar-server\s+(\S+)(?:\s+(\S+))?/.exec(l); if (m) { srv = m[1]; srvModel = m[2] || ""; } return; }   // и «: keepalive» — поток жив
    if (!ollama) { if (!l.startsWith("data:")) return; l = l.slice(5).trim(); if (l === "[DONE]") return; }
    let o; try { o = JSON.parse(l); } catch (e) { return; }
    if (o.error) throw new Error(typeof o.error === "string" ? o.error : (o.error.message || "ошибка модели"));
    try { usage = usageOf(o) || usage; } catch (e) { }
    if (ollama) {
      const m = o.message || {};
      if (m.thinking) sawReason = true;
      if (o.done_reason) finish = o.done_reason;
      if (m.content) feedText(m.content);
      (m.tool_calls || []).forEach((c, i) => { const k = "o" + Object.keys(calls).length + i; calls[k] = { id: "call_" + k, name: c.function.name, args: typeof c.function.arguments === "string" ? c.function.arguments : JSON.stringify(c.function.arguments || {}) }; });
      return;
    }
    const ch = (o.choices || [])[0] || {}, d = ch.delta || {};
    if (ch.finish_reason) finish = ch.finish_reason;
    if (d.reasoning_content || d.reasoning) sawReason = true;
    if (d.content) feedText(d.content);
    (d.tool_calls || []).forEach(c => {
      const k = c.index != null ? c.index : 0, x = calls[k] = calls[k] || { id: c.id || "call_" + k, name: "", args: "" };
      if (c.id) x.id = c.id; if (c.function) { if (c.function.name) x.name += c.function.name; if (c.function.arguments) x.args += c.function.arguments; }
    });
  };
  let err = null;
  /* Сервер модели отклонил запрос: сначала — без chat_template_kwargs (облако Ollama за шлюзом отклоняет незнакомое
     поле, а функции полем принимает — так они работают лучше), потом — функции текстом (а не полем tools), в конце —
     без функций вовсе. Возвращает новый вызов или null, если пробовать больше нечего. */
  const retryRejected = (why) => {
    // №529: отказ не из-за полей запроса (нет такой модели, не тот ключ, не влезло в окно) — запоминать «функции текстом»
    // и «без chat_template_kwargs» нельзя: с опечаткой в имени модели («mercuri-3») телефон навсегда переходил на действия
    // текстом и для правильной модели
    if (NOT_FIELDS_RX.test(String(why || "")) && !/tool|function/i.test(String(why || ""))) return null;
    if (body.stream_options) { S.llm.no_usage = llmBase(); saveS(); return llmStream(messages, tools, onText, signal, opt); }   // подсчёт токенов — лишний
    // в запросе фото, а модель без зрения: отказ — из-за фото (дальше его заменит пояснение), а не из-за полей запроса.
    // №529: «Посмотри, пожалуйста» со скриншотом — 400, и телефон навсегда перешёл на действия текстом
    if (messages.some(m => Array.isArray(m.content) && m.content.some(x => x && x.type === "image_url"))) return null;
    if (body.chat_template_kwargs) { S.llm.no_kwargs = true; saveS(); return llmStream(messages, tools, onText, signal, opt); }
    if (body.tools) {
      S.llm.tools_prompt = llmBase(); S.llm.tp_mark = toolsMark(); saveS();
      plog("info", `🛠 сервер модели не принял действия полем tools (${clip(why, 90)}) — описываю их текстом; после смены модели или обновления проверю снова`);
      return llmStream(messages, tools, onText, signal, opt);
    }
    if (tools && tools.length) {      // и текстом не принял — этот ответ без действий: в журнале видно, почему «просто болтает»
      plog("warn", `⚠ сервер модели отклонил запрос с действиями (${clip(why, 90)}) — этот ответ без действий`);
      return llmStream(messages, null, onText, signal, opt);
    }
    return null;
  };
  // idle — сколько поток может молчать: программа (make_app) — целый HTML в одном вызове, и сервер модели нередко отдаёт
  // вызов целиком в конце (экзамен 0.9.18: «Сделай программу: 3D-модель атома» — 322 с и «сервер замолчал посреди ответа»)
  const hdr = llmHeaders(); if (opt.net && netHeaderOk()) hdr["X-Dewiar-Net"] = "1";
  if (opt.voice && S.llm.cloud) hdr["X-Dewiar-Voice"] = "1";   // сказано голосом: простой вопрос — лёгкому мозгу (сайт решает сам)
  // 1.0.67: облаку Dewiar — тело сжатым (сжимает Net.java): запрос 60–150 КБ, а сети по пути «замирают» на больших запросах.
  // Сайт старше 1.0.67 ответит 400 — этому адресу дальше как раньше (NO_GZ). Веб-версия и браузерные проверки (D.mock: fetch,
  // заголовок сжатия требует CORS-предзапроса) шлют как раньше
  const gz = !D.web && !D.mock && !ollama && brainKind() === "dewiar" && NO_GZ !== llmBase();
  if (gz) hdr["Content-Encoding"] = "gzip";
  const r = await http("POST", url, { headers: hdr, body, stream: true, timeout: 180000, signal, idle: opt.idle || 75000,
    onChunk: (chunk) => { if (err) return; buf += chunk; const parts = buf.split("\n"); buf = parts.pop(); try { parts.forEach(line); } catch (e) { err = e; } } });
  if (buf) { try { line(buf); } catch (e) { err = err || e; } }
  if (!err) { gateEnd(); feedInner("", true); }      // остаток, придержанный на случай разрезанного тега
  if (r.status >= 400 && gz && (r.status === 400 || r.status === 415) && /bad_request|Нужен JSON|gzip/i.test(String(r.body || ""))) {
    NO_GZ = llmBase(); plog("info", "Dewiar cloud: gzip request rejected (old site) — sending uncompressed");
    return llmStream(messages, tools, onText, signal, opt);
  }
  if (r.status >= 400) {
    let msg = r.body || "", ej = {}; try { let j = JSON.parse(msg); if (Array.isArray(j)) j = j[0] || {}; ej = (j && typeof j.error === "object" && j.error) || {}; msg = (j.error && (j.error.message || j.error)) || j.detail || msg; } catch (e) { }   // Gemini — ошибкой-списком
    // Gemini из России и др. (пакет 22.10): «User location is not supported» — повторять бесполезно, сказать, что делать
    if (/location is not supported|unsupported_country|not available in your (country|region)/i.test(String(msg)))
      throw Object.assign(new Error(`${brainName()}: Gemini недоступен из вашей страны. Включите VPN, подключите Gemini через OpenRouter или выберите другой мозг: Настройки → Мозг.`), { human: true });
    if (/insufficient (balance|quota|funds)|no resource package|exceeded your current quota/i.test(String(msg)))
      throw Object.assign(new Error(`${brainName()}: на ключе нет оплаченного пакета или закончились деньги — пополните баланс у сервиса или выберите другой мозг.`), { human: true });
    /* Сервер модели отклонил сам запрос (400/422; через облако Dewiar или шлюз — 502 с текстом «…400…», «отклонил»).
       Обычно виноваты функции полем tools или chat_template_kwargs: «Проверить» (без них) проходит, а разговор — нет. */
    const rejected = !ollama && (r.status === 400 || r.status === 422 || (r.status >= 500 && REJECT_RX.test(String(msg))));
    // №529: «нет такой модели» — сказать словами, что поправить, а не перебирать поля запроса
    if (!ollama && r.status < 500 && MODEL_GONE_RX.test(String(msg)) && !/tool|function/i.test(String(msg)))
      throw Object.assign(new Error(`${brainName()}: сервис не знает модель «${model}» (${clip(msg, 100)}). Проверьте имя модели: Настройки → Мозг.`), { human: true });
    if (rejected) { const again = retryRejected(msg); if (again) return again; }
    if (S.llm.cloud && r.status === 401 && await fixDeadKey(msg)) return llmStream(messages, tools, onText, signal, opt);   // ключ удалили — думаем по аккаунту
    if (S.llm.trial && [400, 403, 429, 502, 503].includes(r.status)) throw Object.assign(new Error(String(msg)), { human: true });   // проба: пределы — словами сайта
    // 402 облака (0.82.1): на экран — полный текст с номером DW-…, голосом — коротко и без ссылки (say), под фразой — кнопка
    // «Пополнить» (topup). Сайт до 0.82.1 полей не присылает — тогда тоже кнопка и та же короткая фраза.
    if (S.llm.cloud && r.status === 402) { cloudInfo = null; throw Object.assign(new Error(String(msg)), { human: true, topup: ej.topup !== false, say: String(ej.say || "Талеры закончились. Пополнить — кнопкой на экране.") }); }
    if (S.llm.cloud && [401, 403, 429, 502, 503].includes(r.status)) { cloudInfo = null; throw Object.assign(new Error(String(msg)), { human: true }); }
    if (r.status === 401) msg = "ключ не подходит (401)";
    // отчёт №117: Groq с компьютера (через VPN) работает, а с телефона — «403: Forbidden» и «413: Request too large»
    if (r.status === 403) throw Object.assign(new Error(`${brainName()} не пускает (403): так бывает, когда сервис закрыт для вашей страны или у ключа нет доступа. `
      + `Включите VPN или верните прежний мозг: Настройки → Мозг → «Прежние мозги».`), { human: true });
    if (r.status === 413) throw Object.assign(new Error(`Запрос больше, чем разрешает ваш тариф у ${S.llm.name || "сервиса"} (413: лимит токенов в минуту) — `
      + `на бесплатных тарифах подсказка с действиями не помещается. Возьмите платный тариф или верните прежний мозг: Настройки → Мозг.`), { human: true });
    if (r.status === 404 && !ollama) { const p = await http("GET", ollamaRoot() + "/api/tags", { timeout: 5000 }).catch(() => null); if (p && p.status === 200) { S.llm.kind = "ollama"; saveS(); return llmStream(messages, tools, onText, signal, opt); } }
    if (tools && /tool|function/i.test(String(msg)) && r.status < 500) {   // модель без инструментов
      plog("warn", `⚠ модель не принимает действия (${clip(msg, 90)}) — этот ответ без действий`);
      return llmStream(messages, null, onText, signal, opt);
    }
    if (body.chat_template_kwargs && (r.status === 400 || r.status === 422)) { S.llm.no_kwargs = true; saveS(); return llmStream(messages, tools, onText, signal, opt); }
    throw new Error(`модель ответила ${r.status}: ${String(msg).slice(0, 160)}`);
  }
  /* Ошибка пришла уже внутри потока (HTTP 200, строка «error»): так отвечают Ollama с облачными моделями и шлюзы —
     «upstream returned HTTP 400». Это тот же отказ от запроса, если модель ещё ничего не успела сказать. */
  if (err && !ollama && REJECT_RX.test(String(err.message)) && !text.trim() && !Object.keys(calls).length && !tcRaw.length) {
    if (MODEL_GONE_RX.test(String(err.message)) && !/tool|function/i.test(String(err.message)))
      throw Object.assign(new Error(`${brainName()}: сервис не знает модель «${model}» (${clip(err.message, 100)}). Проверьте имя модели: Настройки → Мозг.`), { human: true });
    const again = retryRejected(err.message); if (again) return again;
  }
  if (srv) { turnServers.add(srv); if (srv !== "main") plog("info", `🖥 ответил сервер облака ${srv}${srvModel ? " (" + srvModel + ")" : ""}`); }   // экзамен 0.9.18: кто выдумал — видно в отчёте
  if (usage && usage.prompt) { plog("info", usageLine(usage, ((tFirst || Date.now()) - tAsk) / 1000)); hCache(usage); }
  if (err) throw err;
  if (inTool && tcBuf.trim()) tcRaw.push(tcBuf);
  const fromNet = /^n\d/.test(srv);              // ответил узел «Сети Лиры» — вызовы текстом не разбираем
  let found = Object.values(calls).filter(c => c.name);
  if (!fromNet) tcRaw.forEach((raw, i) => { const c = parseToolCall(raw); if (c) found.push({ id: "call_t" + i, name: c.name, args: JSON.stringify(c.args) }); });
  else if (tcRaw.length) plog("warn", `🌐 Сеть Лиры: узел ${srv} прислал вызовы текстом — не выполняю`);
  if (afterCall && !found.length && dropped.trim()) { text += dropped; emitT(dropped); }   // вызов так и не разобрался — текст не теряем
  if (hold) {
    const bare = found.length || fromNet ? [] : bareCalls(text, new Set((tools || []).map(x => x.name)), { ext: turnReadOutside(messages) });
    if (bare.length) { bare.forEach((c, i) => found.push({ id: "call_b" + i, name: c.name, args: JSON.stringify(c.args) })); text = ""; plog("info", "🛠 вызов голым JSON: " + bare.map(c => c.name).join(", ")); }
    else if (held) emitT(held);
  }
  if (fromNet && found.length) found = netCallsFilter(found, lastTxt, tools);
  if (fromNet) {
    // рецензия 04.11, третья: ответ узла похож на вызов текстом («[run_command: …]»), на обещание без дела или на указание
    // модели — не показываем и не озвучиваем; тот же вопрос — главному мозгу, без заголовка сети и без текста узла
    const why = tcRaw.length ? "вызовы текстом" : NET_SUSPECT_RX.test(text) ? "вызов или указание в тексте"
      : (typeof claimedAction === "function" && claimedAction(text, new Set(), lastTxt)) ? "обещание без дела" : "";
    if (why && !(signal && signal.aborted)) { plog("warn", `🌐 Сеть Лиры: ответ узла ${srv} не показываю (${why}) — спрашиваю главный мозг`); return llmStream(messages, tools, onText, signal, Object.assign({}, opt, { net: false })); }
    if (netHeld && onText) onText(netHeld);
  }
  // модель ушла в размышления и упёрлась в лимит, так ничего и не сказав — повторяем без размышлений, с запасом
  // и просто пустой ответ (бывает у облачных моделей) — тоже ещё раз, а не сразу «переспросите» (отзыв 11.10: «защита данных»)
  if (!text.trim() && !found.length && !opt.retried && !(signal && signal.aborted)) {
    console.warn(`пустой ответ модели (${finish || "без ответа"}${sawReason ? ", размышляла" : ""}) — повторяю без размышлений`);
    return llmStream(messages, tools, onText, signal, Object.assign({}, opt, { think: false, retried: true, max: 4096 }));
  }
  return { text, calls: found, finish, fromNet };
}
/* История для модели — как на компьютере: реплики других персонажей приходят от «пользователя» с пометкой, две реплики
   одной роли подряд склеиваются, разговор начинается с пользователя. Иначе строгие шаблоны (Gemma, Mistral, Llama на
   vLLM/llama.cpp) отвечают 400 «roles must alternate» — например, после неудачного ответа в истории два «user» подряд. */
/* Реплики для модели нынешнего персонажа. Разговор человека с другим персонажем (Патриком) — не его: сворачивается в одну
   справку «пользователь говорил с коллегой Патрик, не продолжай их тему» (отзыв 13.10: обсудила задачу с Патриком,
   переключилась на Лиру — а Лира отвечает про задачу Патрика). Реплика человека относится к тому, кто на неё ответил;
   последняя — к нынешнему. Как team_window в core/engine_answer.py. */
function chatHistory(hist, text) {
  const out = [], me = persona().id;
  const msgs = hist.filter(m => m && m.content && typeof m.content === "string" && (m.role === "user" || m.role === "assistant"));
  const owner = new Array(msgs.length); let nxt = me;
  for (let i = msgs.length - 1; i >= 0; i--) { if (msgs[i].role === "assistant") nxt = msgs[i].who || me; owner[i] = nxt; }
  const push = (x) => { const last = out[out.length - 1]; if (last && last.role === x.role) { last.content += "\n\n" + x.content; last.team = x.team; } else out.push(x); };
  for (let i = 0; i < msgs.length;) {
    if (owner[i] === me) { const m = msgs[i++]; push({ role: m.role, content: (m.role === "assistant" && m.net ? NET_WRAP : "") + String(m.content) + (m.note ? "\n" + m.note : "") }); continue; }
    let j = i; const who = owner[i]; while (j < msgs.length && owner[j] === who) j++;
    const lastA = msgs.slice(i, j).reverse().find(m => m.role === "assistant") || {};
    if (lastA.handoff === me) {                      // коллега передал слово — его разговор справкой; иначе не наш разговор
      const name = (PERSONAS.find(p => p.id === who) || {}).name || "коллега";
      const lines = msgs.slice(i, j).map(m => (m.role === "user" ? "Пользователь: " : name + ": ") + String(m.content).replace(/\s+/g, " ").slice(0, 400)).slice(-8);
      push({ role: "user", team: true, content: `[До этого пользователь говорил не с тобой, а с коллегой по имени ${name} — и ${name} передал(а) слово тебе. Это для справки: не отвечай за коллегу, продолжай то, о чём тебя просят.]\n` + lines.join("\n") });
    }
    i = j;
  }
  const lastT = out[out.length - 1];
  push({ role: "user", content: (lastT && lastT.team ? "[Теперь пользователь обращается к тебе:]\n" : "") + text });
  while (out.length && out[0].role === "assistant") out.shift();
  return out.map(m => ({ role: m.role, content: m.content }));
}
/* Функции текстом: описание — в системное сообщение, прошлые вызовы и результаты — обычными репликами
   (сервер, не принимающий tools, обычно не принимает и роль tool). */
function promptToolMessages(messages, tools) {
  const desc = "\n\n# Инструменты\nТы можешь вызывать функции. Их описания — внутри <tools></tools>:\n<tools>\n" +
    tools.map(t => JSON.stringify({ type: "function", function: t })).join("\n") + "\n</tools>\n\nЧтобы вызвать функцию, выведи ровно так и больше ничего:\n<tool_call>\n" +
    '{"name": "<имя функции>", "arguments": {<аргументы>}}\n</tool_call>\nРезультат придёт в <tool_response></tool_response>. Если функция не нужна — просто отвечай.';
  const out = [];
  messages.forEach((m, i) => {
    if (i === 0 && m.role === "system") out.push({ role: "system", content: m.content + desc });
    else if (m.role === "assistant" && m.tool_calls) out.push({ role: "assistant", content: (m.content ? m.content + "\n" : "") + m.tool_calls.map(c => "<tool_call>\n" + JSON.stringify({ name: c.function.name, arguments: safeJSON(c.function.arguments) }) + "\n</tool_call>").join("\n") });
    else if (m.role === "tool") {
      const t = "<tool_response>\n" + m.content + "\n</tool_response>", last = out[out.length - 1];
      if (last && last.role === "user" && String(last.content).startsWith("<tool_response>")) last.content += "\n" + t; else out.push({ role: "user", content: t });
    } else if (m.role === "user" && Array.isArray(m.content) && out.length && out[out.length - 1].role === "user") {   // снимок сразу после результата
      const last = out[out.length - 1];
      last.content = (Array.isArray(last.content) ? last.content : [{ type: "text", text: String(last.content) }]).concat(m.content);
    } else out.push({ role: m.role, content: m.content });
  });
  if (!out.length || out[0].role !== "system") out.unshift({ role: "system", content: desc.trim() });
  return out;
}
function toOllama(m) {
  if (m.role === "assistant" && m.tool_calls) return { role: "assistant", content: m.content || "", tool_calls: m.tool_calls.map(c => ({ function: { name: c.function.name, arguments: safeJSON(c.function.arguments) } })) };
  if (m.role === "tool") return { role: "tool", content: m.content, tool_name: m.name };
  if (Array.isArray(m.content)) return { role: m.role, content: m.content.filter(x => x.type === "text").map(x => x.text).join("\n"),
    images: m.content.filter(x => x.type === "image_url").map(x => String(x.image_url.url).replace(/^data:[^,]+,/, "")) };
  return { role: m.role, content: m.content };
}
/* Аргументы вызова -> объект. Модели (и серверы) присылают их по-разному: строкой с JSON внутри строки, одним объектом
   дважды подряд («{…}{…}» — кусок повторился в потоке), оборванными по лимиту. Раньше всё это молча становилось {}:
   remember({}) отвечал «Запомнил», а не запоминал ничего (экзамен 0.6.40, «Помнит факт после нового разговора»). */
function safeJSON(s) {
  if (s && typeof s === "object") return s;
  const t = String(s || "").trim(); if (!t) return {};
  const obj = (v) => v && typeof v === "object" && !Array.isArray(v) ? v : null;
  try { let v = JSON.parse(t); if (typeof v === "string") v = JSON.parse(v); return obj(v) || {}; } catch (e) { }
  for (let i = t.lastIndexOf("{"); i > 0; i = t.lastIndexOf("{", i - 1)) {        // «{…}{…}» — берём последний целый
    if (t[i - 1] !== "}" && !/}\s*$/.test(t.slice(0, i))) continue;
    try { const v = obj(JSON.parse(t.slice(i))); if (v) return v; } catch (e) { }
  }
  return repairJSON(t) || {};
}
/* оборванный JSON: закрыть строку и скобки (как repair_json в llm.py) */
function repairJSON(t) {
  if (!t.startsWith("{")) return null;
  const st = []; let q = false, esc = false;
  for (const ch of t) {
    if (q) { if (esc) esc = false; else if (ch === "\\") esc = true; else if (ch === '"') q = false; continue; }
    if (ch === '"') q = true; else if (ch === "{" || ch === "[") st.push(ch === "{" ? "}" : "]"); else if (ch === "}" || ch === "]") st.pop();
  }
  let fixed = t + (q ? '"' : "");
  fixed = fixed.replace(/,\s*$/, "").replace(/:\s*$/, ': ""') + st.reverse().join("");
  try { const v = JSON.parse(fixed); return v && typeof v === "object" ? v : null; } catch (e) { return null; }
}

/* Разговорная очередь: показываем текст и озвучиваем по предложениям. Первую фразу без конца предложения — как можно
   раньше (по запятой или тире после 60 знаков, как на компьютере — SentenceSplitter): голос с сервера синтезирует фразу
   целиком, и длинное первое предложение заметно задерживало первый звук; дальше по запятой режем только очень длинные. */
/* ⏱ куда уходит время до первого звука (исследование 14.10: TTS — меньше секунды из 7–10): первое слово модели, первая
   фраза отдана в голос, звук пошёл — одной строкой в журнале (видно в отчётах) */
let turnT = null;
function turnTime(stage) {
  const t = turnT; if (!t || t.logged) return;
  if (stage === "word" && !t.word) t.word = Date.now();
  if (stage === "said" && !t.said) t.said = Date.now();
  if (stage === "sound" && t.said) {
    t.logged = true;
    const f = (a, b) => ((b - a) / 1000).toFixed(1).replace(".", ",");
    const via = S.tts.engine === "cloud" ? "голос Dewiar" : S.tts.engine === "server" ? "свой сервер голоса" : S.tts.engine === "eleven" ? "ElevenLabs" : "голос телефона";
    plog("info", `⏱ до звука ${f(t.t0, Date.now())} с: модель начала отвечать за ${f(t.t0, t.word || t.said)} с, первая фраза в голос +${f(t.word || t.said, t.said)} с, синтез и доставка (${via}) +${f(t.said, Date.now())} с`);
  }
}
const CALC_TURN = /посчитай|подсчитай|рассчитай|вычисли|сколько\s+(?:ещё\s+|еще\s+)?(?:дней|минут|часов|недель|месяцев|лет|будет|процент)|через\s+сколько|сколько\s+осталось/i;
/* Голос во время долгого действия (владелец 20.11, как на компьютере — core/act_cue.py): действие идёт дольше ~2,5 с,
   а Лира ещё ничего не сказала — одна короткая фраза о том, что она делает. Только для действий, которые бывают долгими;
   с подтверждением и говорящие сами — без фразы; текстовый режим и Telegram молчат сами (say). */
const ACT_CUE_MS = 2500;
const ACT_CUE = { web_search: "Ищу в интернете…", read_webpage: "Читаю страницу…", world_news: "Смотрю новости…",
  ask_knowledge: "Смотрю в знаниях…", find_notes: "Смотрю заметки…", recall: "Вспоминаю…", pc_documents: "Смотрю документы на компьютере…",
  weather: "Смотрю погоду…", calendar_list: "Смотрю календарь…", show_images: "Ищу картинки…", money_report: "Считаю…",
  month_summary: "Считаю…", client_list: "Смотрю клиентов…", route: "Строю маршрут…" };
function actCueArm(name, ctl, sink) {
  const p = ACT_CUE[name]; if (!p) return;
  setTimeout(() => {
    if (ctl.signal.aborted || turnAbort !== ctl || !busy || sink.text().trim()) return;
    plog("info", `🗣 «${name}» идёт дольше ${ACT_CUE_MS / 1000} с — «${p}»`); say(p);
  }, ACT_CUE_MS);
}
function sentenceSink() {
  let pending = "", shown = "", first = true, raw = "", inCode = false;
  // блоки ``` … ``` (код, схемы) вслух не читаем: они приходят кусками, поэтому граница блока ищется в потоке;
  // придерживаем только хвост из одной-двух ` (вдруг это начало ```), остальное — сразу в голос
  const speakable = (fin) => {
    let out = "";
    for (;;) {
      const i = raw.indexOf("```");
      if (i < 0) { const keep = fin ? 0 : (raw.match(/`{1,2}$/) || [""])[0].length; if (!inCode) out += raw.slice(0, raw.length - keep); raw = raw.slice(raw.length - keep); break; }
      if (!inCode) out += raw.slice(0, i);
      raw = raw.slice(i + 3); inCode = !inCode;
    }
    return out;
  };
  // №435 (31.10, телефон: «дважды пишет и проговаривает текст»): модель сказала «Записала: расход 3 795 руб…» до
  // действия и то же самое — после него. Начало каждого следующего круга придерживаем, пока не станет ясно, не повтор
  // ли это уже сказанного (первые 18 букв и цифр есть в сказанном) — повтор не показываем и не озвучиваем.
  let probing = false, probe = "", mute = false;
  const norm = (t) => String(t || "").toLowerCase().replace(/ё/g, "е").replace(/[^a-zа-я0-9]+/g, "");
  const decide = (fin) => {
    const h = norm(probe), seen = norm(shown);
    if (!fin && h.length < 18) return false;
    probing = false;
    const head = h.slice(0, 18);
    if (head.length >= (fin ? 10 : 18) && seen.includes(head)) { mute = true; plog("info", "🔁 повтор сказанного после действия — не повторяю"); }
    else { const t = probe; probe = ""; api.pushNow(t); }
    probe = "";
    return true;
  };
  /* экзамен 0.9.18: «Посчитай, сколько дней до Нового года, и поставь таймер на столько же минут» — до calc модель
     сказала «до Нового года 28 дней — это 40 320 минут», а calc дал 59: в ответе противоречие. На просьбу посчитать
     (holdNums) фразы с числами придерживаем до конца круга; круг кончился вызовом calc — их не показываем и не озвучиваем */
  let holdOn = false, hold = "", allOn = false;   // allOn — весь первый круг придерживаем (№528: «я на актуальной версии» — не в голос)
  const release = (drop) => {
    const h = hold; hold = ""; if (!h) return;
    if (drop && /\d/.test(h)) { plog("info", "🔢 числа до calc — не показываю и не озвучиваю: " + clip(h, 60)); return; }
    api.pushNow(h);
  };
  const api = {
    round() { release(false); if (probing && probe) decide(true); probing = !!norm(shown); probe = ""; mute = false; },
    holdNums(on) { holdOn = !!on; },
    holdAll(on) { allOn = !!on; },
    endRound(calcCalled, dropAll) {
      if (allOn) { allOn = false; if (dropAll) { if (hold.trim()) plog("info", "🔇 не проверив — не показываю и не озвучиваю: " + clip(hold, 60)); hold = ""; return; } }
      release(!!calcCalled);
    },
    push(piece) {
      if (allOn && piece) { hold += piece; return; }
      if (!holdOn || !piece) return api.pushNow(piece);
      hold += piece;
      if (/\d/.test(hold)) return;                    // фраза с числом — до конца круга
      const m = hold.match(/^[\s\S]*[.!?…\n]\s+/); // законченные фразы без чисел — сразу
      if (m) { hold = hold.slice(m[0].length); api.pushNow(m[0]); }
    },
    pushNow(piece) {
      if (mute) return;
      if (probing) { probe += piece; decide(false); return; }
      if (piece) turnTime("word");
      shown += piece; showBot(gfix(shown)); raw += piece; pending += speakable(false);    // героиня, а модель сбилась на «рад», «понял» — правим сами
      for (;;) {
        const m = pending.match(/^([\s\S]*?[.!?…](?:["»)]?)(?:\s+|$)|[\s\S]*?\n)/);
        if (m && m[0].length >= 2 && !(!/\s$/.test(m[0]) && m[0].length === pending.length)) {   // иначе конец ещё может продолжиться
          say(gfix(m[0])); pending = pending.slice(m[0].length); first = false; continue;
        }
        const limit = first ? 60 : 220;
        if (pending.length > limit) {
          const cut = Math.max(pending.lastIndexOf(", ", limit + 40), pending.lastIndexOf(" — ", limit + 40));
          if (cut > 25) { say(gfix(pending.slice(0, cut + 1))); pending = pending.slice(cut + 2); first = false; continue; }
        }
        break;
      }
    },
    own(t) { release(false); if (probing && probe) decide(true); probing = false; mute = false; api.pushNow(t); },   // наши слова (не модели) — не глушим как повтор
    flush() { release(false); if (probing && probe) decide(true); pending += speakable(true); if (pending.trim()) say(gfix(pending)); pending = ""; },
    text: () => gfix(shown),
  };
  return api;
}

