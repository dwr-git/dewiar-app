//@ Телефон и веб-версия, часть 18: мессенджеры, кнопки и запуск.
//@ Собирается в android/assets/www/app.js (tools/app_join.py) — порядок частей = порядок исполнения; шапка «//@» в app.js не попадает.
/* ---------- мессенджеры: MAX, Telegram, WhatsApp… — текст уходит в приложение, получателя выбирает человек ---------- */
const MESSENGERS = {
  max: { name: "MAX", pkgs: ["ru.oneme.app"] },
  telegram: { name: "Telegram", pkgs: ["org.telegram.messenger", "org.telegram.messenger.web", "org.thunderdog.challegram"] },
  whatsapp: { name: "WhatsApp", pkgs: ["com.whatsapp", "com.whatsapp.w4b"] },
  viber: { name: "Viber", pkgs: ["com.viber.voip"] },
  vk: { name: "VK", pkgs: ["com.vkontakte.android"] },
};
function msgApp(w) {
  w = String(w || "").toLowerCase();
  return /^(тел|тг|tele)/.test(w) ? "telegram" : /^(ват|вот|вац|whats)/.test(w) ? "whatsapp" : /^(вай|viber)/.test(w) ? "viber" : /^(вк|вконт)/.test(w) ? "vk" : "max";
}
/* Номер контакта — в международный вид для ссылок мессенджеров: 8 916… и 916… (10 цифр) — Россия; иначе как записан.
   -> цифры без «+» или "" — номер не годится (короткий, без кода страны) */
function intlPhone(num) {
  let d = String(num || "").replace(/[^\d+]/g, "");
  if (/^\+/.test(d)) return d.slice(1).replace(/\D/g, "").length >= 10 ? d.slice(1).replace(/\D/g, "") : "";
  d = d.replace(/\D/g, "");
  if (/^8\d{10}$/.test(d)) return "7" + d.slice(1);
  if (/^9\d{9}$/.test(d)) return "7" + d;
  return d.length >= 11 ? d : "";
}
/* Идея №4 (план улучшений 19.11, п. 5: «пишет в Telegram и MAX от вашего имени — с подтверждением каждого сообщения»):
   «напиши Ане в телеграм: опоздаю на 10 минут» — открываем чат именно с Аней (по номеру из контактов), текст уже в поле;
   «Отправить» нажимает человек — это и есть подтверждение. Telegram — ссылкой tg://resolve?phone=…&text=…, WhatsApp —
   wa.me; MAX, Viber, VK ссылок на чат по номеру не дают — как раньше: приложение с текстом, получателя выбирает человек.
   -> строка для человека / модели или {ask} — в контактах несколько похожих */
async function sendTo(app, text, who) {
  const m = MESSENGERS[app] || MESSENGERS.max; text = String(text || "").trim(); who = String(who || "").trim();
  if (!text) return "Нечего отправлять — скажите текст сообщения.";
  if (who && (app === "telegram" || app === "whatsapp") && D.openUrl) {
    const rel = typeof relOf === "function" ? relOf(who) : null, known = rel && (S.relations || {})[rel];   // «маме» — как для звонка
    let c = known && known.number ? { name: known.name || REL_RU[rel], number: known.number } : JSON.parse(D.contact(rel ? REL_RU[rel] : who) || "{}");
    if (c.need && await needPerm(CONTACTS)) c = JSON.parse(D.contact(rel ? REL_RU[rel] : who) || "{}");
    if ((c.alts || []).length) return `В контактах несколько похожих: ${[c.name, ...c.alts.map(x => x.name)].slice(0, 4).join(", ")}. Кому написать? Скажите имя целиком.`;
    const ph = intlPhone(c.number);
    if (ph) {
      const url = app === "telegram" ? `tg://resolve?phone=${ph}&text=${encodeURIComponent(text)}` : `https://wa.me/${ph}?text=${encodeURIComponent(text)}`;
      if (D.openUrl(url)) return `Открыл чат с «${c.name}» в ${m.name}, текст уже в поле — осталось проверить и нажать «Отправить».`;
    }
  }
  for (const p of m.pkgs) if (D.shareTo && D.shareTo(p, text)) return `Открыл ${m.name} с текстом — выберите, кому отправить.`;
  D.share(text); return `${m.name} на телефоне не нашёлся — открыл выбор приложения.`;
}

/* мастер «Мозг» по плитке: account — вход на сайт, dwkey — ключ Dewiar, dewiar — сервер Dewiar по манифесту,
   server — свой сервер в сети, cloud — облачный сервис по ключу, иначе — файл настроек с компьютера */
function wizard(kind) {
  const w = $("#wz");
  if (kind === "account") {
    w.innerHTML = `<div class="card"><label class="f"><span>Логин на dewiar.pro</span><input id="w-login" autocapitalize="off" autocomplete="username" spellcheck="false"></label>
      <label class="f"><span>Пароль</span><input id="w-pass" type="password" autocomplete="current-password"></label>
      <details class="more"><summary>Другой сайт</summary><label class="f"><span>Адрес сайта</span><input id="w-site" inputmode="url" placeholder="dewiar.pro" value="${esc(S.account.server && S.account.server !== SITE ? S.account.server : "")}"></label></details>
      <button class="btn p w" id="w-go">Войти</button><div class="res" id="w-res"></div>
      <p class="hint">Пароль не сохраняется — телефон получает только ключ входа. Нет своей модели — подключатся модели Dewiar с зарядом в талерах; персонажам можно будет дать базы знаний сайта.</p></div>`;
    const go = async () => { const r = $("#w-res"); r.className = "res"; r.textContent = "вхожу…"; $("#w-go").disabled = true;
      try { const x = await accountLogin($("#w-site").value, $("#w-login").value, $("#w-pass").value);
        r.className = "res ok"; r.textContent = `Вы вошли: ${x.login}.` + (x.cloud && x.cloud.error ? " Модели Dewiar сейчас недоступны: " + x.cloud.error : x.activated ? ` Думают модели Dewiar, заряд ${x.cloud.percent}%.` : x.cloud ? " Модели Dewiar можно включить кнопкой." : "");
        toast("Аккаунт подключён"); setTimeout(renderSettings, 1600); }
      catch (e) { r.className = "res bad"; r.textContent = e.message; $("#w-go").disabled = false; } };
    $("#w-go").onclick = go; $("#w-pass").onkeydown = (e) => { if (e.key === "Enter") go(); };
    setTimeout(() => $("#w-login").focus(), 200);
  } else if (kind === "join") {
    // №216: на втором устройстве — не новая заявка (второй ключ — и ни заметок, ни блокнота друг у друга), а код
    w.innerHTML = `<div class="card have"><b>Dewiar уже есть на компьютере или другом телефоне?</b><p class="hint" style="margin:4px 0 10px">Не отправляйте новую заявку — введите код с того устройства: память, заметки, блокнот и счёт будут общими. Код там: «Мозг» → «Добавить устройство».</p><button class="btn w" id="w-have">Ввести код</button></div>
      <div class="card"><b>Подключить мозг Dewiar</b><p class="hint" style="margin:4px 0 8px">Без регистрации: напишите, как к вам обращаться и как связаться. Обычно всё подключается сразу; если заявку проверяют вручную — я сама скажу, когда готово. На счёте будет подарок, чтобы попробовать.</p>
      <label class="f"><span>Как к вам обращаться</span><input id="w-name" autocomplete="name"></label>
      <label class="f"><span>Как связаться: почта, Telegram или телефон</span><input id="w-contact" autocapitalize="off" spellcheck="false" placeholder="@ник или почта"></label>
      <label class="f"><span>Пара слов, зачем (необязательно)</span><input id="w-note" placeholder="например: попробовать помощника"></label>
      <button class="btn p w" id="w-go">Подключить</button><div class="res" id="w-res"></div>
      <p class="hint">Потом так же подключатся компьютер и другие телефоны — кодом из 6 цифр, данные и счёт будут общими.</p></div>`;
    $("#w-have").onclick = () => openBrain("dwkey");
    $("#w-go").onclick = async () => { const r = $("#w-res"); r.className = "res"; r.textContent = "отправляю…"; $("#w-go").disabled = true;
      try { const d = await joinSend($("#w-name").value, $("#w-contact").value, $("#w-note").value);
        r.className = "res ok"; r.textContent = d.text || "Заявка отправлена."; if (d.key) setTimeout(renderSettings, 1400); else setTimeout(renderSettings, 2500); }
      catch (e) { r.className = "res bad"; r.textContent = e.message; $("#w-go").disabled = false; } };
    setTimeout(() => $("#w-name").focus(), 200);
  } else if (kind === "dwkey") {
    w.innerHTML = `<div class="card"><label class="f"><span>Ключ Dewiar или код с другого устройства</span><input id="w-key" placeholder="dw-xxxxxx-… или 6 цифр" autocapitalize="off" autocomplete="off" spellcheck="false"></label>
      <button class="btn p w" id="w-go">Подключить</button><div class="res" id="w-res"></div>
      <p class="hint">Код из 6 цифр покажет ваше другое устройство, где Dewiar уже работает: «Устройства» → «Подключить ещё устройство» (на компьютере — в студии, на телефоне — в настройках). Удобнее — вкладка «Устройства» здесь: там и сканер.</p></div>`;
    $("#w-go").onclick = async () => { const r = $("#w-res"); r.className = "res"; r.textContent = "проверяю…";
      try { let k = $("#w-key").value.trim();
        if (/^\d[\d\s-]{4,8}\d$/.test(k)) { const d = await devClaim(k); r.className = "res ok"; r.textContent = devClaimText(d); setTimeout(renderSettings, 1800); return; }
        const c = await cloudConnect(k); r.className = "res ok"; r.textContent = `Подключено${c.label ? ": " + c.label : ""}. Заряд ${c.percent}%.`; toast("Мозг подключён"); setTimeout(renderSettings, 1400); }
      catch (e) { r.className = "res bad"; r.textContent = e.message; } };
  } else if (kind === "server") {
    w.innerHTML = `<div class="card"><label class="f"><span>Адрес сервера</span><input id="w-addr" placeholder="192.168.1.10 или 192.168.1.10:11434" inputmode="url"></label>
      <button class="btn p w" id="w-go">Найти</button><div class="res" id="w-res"></div><div id="w-found"></div>
      <p class="hint">Порт можно не указывать — проверю обычные: Ollama 11434, vLLM 8000, llama.cpp 8080, LM Studio 1234. Сервер дома доступен только в домашней сети (Wi-Fi).</p></div>`;
    $("#w-go").onclick = async () => { const r = $("#w-res"); r.className = "res"; r.textContent = "ищу…"; $("#w-found").innerHTML = "";
      try { const f = await probeServer($("#w-addr").value); r.className = "res ok"; r.textContent = `Нашёл: ${f.kind === "ollama" ? "Ollama" : "OpenAI-совместимый сервер"} — ${f.base}`;
        $("#w-found").innerHTML = `<label class="f"><span>Модель</span><select id="w-model">${f.models.map(m => `<option>${esc(m)}</option>`).join("")}</select></label><button class="btn p w" id="w-use">Подключить</button>`;
        $("#w-use").onclick = () => { S.llm = Object.assign({}, DEF.llm, { kind: f.kind, name: "Сервер " + f.base.replace(/^https?:\/\//, "").replace(/\/v1$/, ""), base_url: f.base, model: $("#w-model").value }); saveS(); toast("Мозг подключён"); renderSettings(); }; }
      catch (e) { r.className = "res bad"; r.textContent = e.message; } };
  } else if (kind === "cloud") {
    w.innerHTML = `<div class="card"><label class="f"><span>Сервис</span><select id="w-prov">${Object.entries(CLOUD).map(([k, v]) => `<option value="${k}">${v.name}</option>`).join("")}</select></label>
      <label class="f" id="w-url-f" style="display:none"><span>Адрес (OpenAI-совместимый)</span><input id="w-url" inputmode="url" autocapitalize="off" spellcheck="false" placeholder="https://api.example.ru/v1"></label>
      <label class="f"><span>Ключ</span><input id="w-key" type="password" placeholder="sk-…"></label><label class="f"><span>Модель</span><input id="w-model" autocapitalize="off" spellcheck="false"></label>
      <p class="hint" id="w-hint"></p><button class="btn p w" id="w-go">Подключить</button><div class="res" id="w-res"></div></div>`;
    const fill = () => { const k = $("#w-prov").value, c = CLOUD[k]; $("#w-model").value = c.model; $("#w-url-f").style.display = k === "custom" ? "" : "none";
      $("#w-hint").innerHTML = k === "custom" ? "Любой сервис, который говорит «как OpenAI»: LiteLLM, Kimi, агрегаторы. Адрес (обычно оканчивается на /v1) и имя модели — в документации сервиса."
        : `Ключ — на <a href="${c.key}">${c.key.replace("https://", "")}</a>.`; };
    $("#w-prov").onchange = fill; fill();
    $("#w-go").onclick = async () => { const k = $("#w-prov").value, c = CLOUD[k], r = $("#w-res"); const old = S.llm;
      const url = k === "custom" ? svcUrl($("#w-url").value) : c.url; let model = $("#w-model").value.trim();
      if (!url) { r.className = "res bad"; r.textContent = "Впишите адрес сервиса"; return; }
      if (c.rec && model === c.model) {          // имя по умолчанию не трогали — берём то, что у сервиса есть сейчас (имена меняются)
        r.className = "res"; r.textContent = "узнаю модели сервиса…";
        const ms = await svcModels(url, $("#w-key").value.trim());
        if (ms.length && !ms.includes(model)) { model = c.rec.find(m => ms.includes(m)) || ms.slice().sort()[0]; $("#w-model").value = model; }
      }
      if (!model) { r.className = "res bad"; r.textContent = "Впишите имя модели"; return; }
      let name = c.name; if (k === "custom") { try { name = new URL(url).host; } catch (e) { name = "Свой сервис"; } }
      const mk = (base) => Object.assign({}, DEF.llm, { kind: "openai", name, base_url: base, api_key: $("#w-key").value.trim(), model, disable_thinking: false });
      const ping = () => llmStream([{ role: "user", content: "Ответь одним словом: готово" }], null, null);
      S.llm = mk(url); r.className = "res"; r.textContent = "проверяю ключ…";
      try {
        try { await ping(); }
        catch (e) { if (k !== "custom" || /\/v1$/.test(url)) throw e; S.llm = mk(url + "/v1"); await ping(); }      // забыли /v1 — частая ошибка
        saveS(); r.className = "res ok"; r.textContent = "Готово — мозг подключён."; setTimeout(renderSettings, 1400); }
      catch (e) { S.llm = old; r.className = "res bad"; r.textContent = e.message; } };
  } else {
    w.innerHTML = `<div class="card"><b>Адрес от администратора</b><p class="hint" style="margin:4px 0 8px">Если администратор дал адрес своего сервера Dewiar — модель, слух и голос подключатся по нему сразу.</p>
      <label class="f"><span>Адрес сервера</span><input id="w-addr" placeholder="например: ai.company.ru" inputmode="url"></label>
      <label class="f"><span>Код доступа (если выдали)</span><input id="w-akey" type="password"></label><button class="btn p w" id="w-ago">Подключить</button><div class="res" id="w-ares"></div></div>
      <div class="card"><b>Файл настроек с компьютера</b><p class="hint" style="margin-top:4px">На компьютере: студия → «Подключение» → «Файл настроек» → отметьте «включить ключи доступа» → «Экспортировать…».
      Пришлите файл себе (например, в Telegram) и откройте его на телефоне — Dewiar подхватит настройки. Или вставьте содержимое файла сюда:</p>
      <label class="f"><textarea id="w-json" rows="5" style="width:100%;padding:12px;border-radius:14px;border:0;background:var(--field);color:var(--ink)" placeholder='{"dewiar": 1, …}'></textarea></label>
      <button class="btn p w" id="w-go">Применить</button><div class="res" id="w-res"></div></div>`;
    $("#w-go").onclick = () => { const r = $("#w-res"); try { const m = JSON.parse($("#w-json").value); applyConfig(m, ""); r.className = "res ok"; r.textContent = "Настройки применены."; setTimeout(renderSettings, 1400); }
      catch (e) { r.className = "res bad"; r.textContent = "Не получилось: " + e.message; } };
    $("#w-ago").onclick = async () => { const r = $("#w-ares"); r.className = "res"; r.textContent = "ищу сервер…";
      try { const m = await fetchManifest($("#w-addr").value); applyConfig(m, $("#w-akey").value.trim()); r.className = "res ok"; r.textContent = `Подключено: ${m.name || "сервер Dewiar"}.`; setTimeout(renderSettings, 1500); }
      catch (e) { r.className = "res bad"; r.textContent = e.message; } };
  }
}
function normAddr(a) { a = String(a || "").trim().replace(/\/+$/, ""); if (!a) throw new Error("укажите адрес"); if (!/^https?:\/\//.test(a)) a = (/^(\d+\.){3}\d+|^localhost|:\d+$/.test(a) ? "http://" : "https://") + a; return a; }
async function fetchManifest(addr) {
  const base = normAddr(addr);
  for (const u of base.endsWith(".json") ? [base] : [base + "/.well-known/dewiar.json", base + "/dewiar.json"]) {
    try { const r = await http("GET", u, { timeout: 10000 }); if (r.status === 200) { const d = JSON.parse(r.body); if (d.dewiar) return d; } } catch (e) { }
  }
  throw new Error("по этому адресу нет сервера Dewiar (нужен файл /.well-known/dewiar.json)");
}
// 127.0.0.1 / localhost на телефоне — это сам телефон (19.10: QR с компьютера дал адрес LM Studio 127.0.0.1:1234 — 16 сбоев)
const SELF_HOST_RX = /^https?:\/\/(?:127\.\d+\.\d+\.\d+|localhost|0\.0\.0\.0|\[::1\])(?::\d+)?(?:\/|$)/i;
const SELF_HOST_TEXT = "адрес 127.0.0.1 (localhost) на телефоне — это сам телефон, а не компьютер. Впишите адрес компьютера в домашней сети (например, 192.168.1.10:1234 — он виден в LM Studio или в «ipconfig»), а в LM Studio включите «Serve on Local Network» (в Ollama — OLLAMA_HOST=0.0.0.0).";
async function probeServer(addr) {
  let a = normAddr(addr).replace(/\/v1$/, "");
  if (!D.mock && SELF_HOST_RX.test(a + "/")) throw new Error(SELF_HOST_TEXT[0].toUpperCase() + SELF_HOST_TEXT.slice(1));
  const hasPort = /:\d+$/.test(a), cands = hasPort ? [a] : [a + ":11434", a + ":8000", a + ":8080", a + ":1234", a];
  for (const b of cands) {
    try { const r = await http("GET", b + "/api/tags", { timeout: 4000 }); if (r.status === 200) { const m = (JSON.parse(r.body).models || []).map(x => x.name); if (m.length) return { kind: "ollama", base: b + "/v1", models: m }; } } catch (e) { }
    try { const r = await http("GET", b + "/v1/models", { timeout: 4000 }); if (r.status === 200) { const m = (JSON.parse(r.body).data || []).map(x => x.id); if (m.length) return { kind: "openai", base: b + "/v1", models: m }; } } catch (e) { }
  }
  throw new Error("сервер не нашёлся. Телефон в той же сети Wi-Fi? Адрес и порт верные?");
}
/* Файл настроек или манифест сервера Dewiar (формат компьютера: llm.profiles, stt/tts.remote) → настройки телефона.
   ${KEY} в строках — место для кода доступа, который выдал администратор. */
/* Настройки по ссылке или из файла меняют, куда уходят голос и вопросы, — без спроса нельзя: ссылку dewiar://import
   может подсунуть любая страница, код или сообщение. Показываем, на какие серверы всё переедет. */
function cfgAsk(m) {
  const host = (u) => { try { return new URL(String(u)).host; } catch (e) { return String(u || "").slice(0, 60); } };
  const l = (m && m.llm) || {}, prof = (l.profiles || {})[l.active] || Object.values(l.profiles || {})[0] || {};
  const rows = [prof.base_url && "Мозг: " + host(prof.base_url), m && m.stt && m.stt.remote && m.stt.remote.base_url && "Распознавание речи: " + host(m.stt.remote.base_url),
                m && m.tts && m.tts.remote && m.tts.remote.base_url && "Голос: " + host(m.tts.remote.base_url),
                m && m.ha && m.ha.url && "Home Assistant: " + host(m.ha.url)].filter(Boolean);
  return confirm("Перенести настройки?\n\n" + (rows.join("\n") || "без серверов") + "\n\nСоглашайтесь, только если сами открыли этот код в своей студии Dewiar.");
}
/* Умный дом из кода «Перенести настройки» (№852, 18.11: «мозг перенёсся, а Home Assistant — нет»): Яндекс — токен,
   Home Assistant — адрес и токен; дальше они расходятся по своим устройствам, как при ручном подключении. */
function cfgHomesName(m) {
  const y = m && m.home && m.home.token, h = m && m.ha && m.ha.token;
  return y && h ? "умный дом Яндекса и Home Assistant" : h ? "Home Assistant" : "умный дом Яндекса";
}
function cfgHomes(m) {
  if (m && m.home && m.home.token) homeSet(String(m.home.token));
  if (!D.web && m && m.ha && m.ha.url && m.ha.token) {
    S.ha = { url: haUrl(m.ha.url), token: String(m.ha.token).trim(), at: Date.now() }; homeInfo = null; saveS();
    ownShare().catch(e => plog("info", "Home Assistant на свои устройства: " + e.message));
  }
}
function applyConfig(m, key) {
  const fill = (v) => typeof v === "string" ? v.replace(/\$\{KEY\}/g, key || "") : v;
  const l = m.llm || {}, prof = (l.profiles || {})[l.active] || Object.values(l.profiles || {})[0];
  if (!prof) throw new Error("в файле нет настроек модели");       // проверяем до правок: иначе слух и персонаж менялись бы, а мозг — нет
  if (prof) S.llm = Object.assign({}, DEF.llm, { kind: prof.kind === "ollama" ? "ollama" : "openai", name: fill(prof.name) || m.name || "", base_url: fill(prof.base_url), api_key: fill(prof.api_key || ""),
    model: fill(prof.model || ""), disable_thinking: prof.cloud ? false : prof.disable_thinking !== false, temperature: prof.temperature || 0.7,
    cloud: !!prof.cloud || /cloud\.php\?p=/.test(prof.base_url || ""), title: prof.title || "", economy: prof.cloud ? "" : fill(prof.economy || "") });
  if (m.stt && m.stt.engine === "remote" && m.stt.remote && m.stt.remote.base_url) S.stt = { engine: "server", url: fill(m.stt.remote.base_url), key: fill(m.stt.remote.api_key || ""), model: fill(m.stt.remote.model || "") };
  if (m.tts && m.tts.engine === "remote" && m.tts.remote && m.tts.remote.base_url) Object.assign(S.tts, { engine: "server", url: fill(m.tts.remote.base_url), key: fill(m.tts.remote.api_key || ""), model: fill(m.tts.remote.model || ""), voice: fill(m.tts.remote.voice || "") });
  if (m.persona && PERSONAS.some(p => p.id === m.persona)) S.persona = m.persona;
  if (m.user_name) S.user_name = m.user_name;
  saveS(); applyPersona();
}
function cmpVer(a, b) {
  const x = String(a).split(/[.-]/).map(n => parseInt(n) || 0), y = String(b).split(/[.-]/).map(n => parseInt(n) || 0);
  for (let i = 0; i < Math.max(x.length, y.length); i++) { if ((x[i] || 0) !== (y[i] || 0)) return (x[i] || 0) - (y[i] || 0); }
  return 0;
}
/* Обновление внутри приложения (18.10: «в Загрузках копятся версии, не каждый разберётся, где удалить»): «Обновить» —
   Dewiar сам качает новую версию в свою папку (Update.java, с проверкой sha256), открывает установщик Android, а
   после установки файл удаляет. Старые Dewiar-….apk, скачанные браузером раньше, — «Открыть Загрузки». Нет моста
   (старая сборка) — как раньше: ссылка для браузера. */
let updInfo = null, updWantInstall = false;
function updRender(html, cls) { const r = $("#upd-res"); if (r) { r.className = "res " + (cls || "ok"); r.innerHTML = html; updWire(); } }
function updWire() {
  const go = $("#upd-go"), inst = $("#upd-inst"), dl = $("#upd-dl");
  if (go) go.onclick = () => { if (!updInfo) return; updRender(`Скачиваю Dewiar ${esc(updInfo.version)}… <b id="upd-pct"></b>`); D.updateGet(updInfo.url, updInfo.sha || ""); };
  if (inst) inst.onclick = () => updInstall();
  if (dl) dl.onclick = () => { if (!D.openDownloads()) toast("Откройте «Файлы» → «Загрузки» и удалите Dewiar-….apk"); };
}
function updInstall() {
  const r = D.updateInstall();
  if (r === "perm") { updWantInstall = true; updRender(`Разрешите Dewiar устанавливать обновления (один раз) — вернитесь, и установка начнётся сама.<button class="btn w" id="upd-inst" style="margin-top:8px">Установить</button>`); }
  else if (r === "ok") updRender(`Открылась установка — нажмите «Обновить». Скачанный файл Dewiar потом удалит сам.`);
  else updRender(`Файл обновления пропал — нажмите «Обновить» ещё раз.<button class="btn w" id="upd-go" style="margin-top:8px">Обновить</button>`, "bad");
}
N.on("upd_progress", e => { const p = $("#upd-pct"); if (p) p.textContent = e.pct >= 0 ? e.pct + "%" : ""; });
N.on("upd_ready", () => { plog("info", "⬇️ обновление скачано — открываю установку"); updInstall(); });
N.on("upd_error", e => updRender(`Не скачалось: ${esc(e.error || "ошибка связи")}.<button class="btn w" id="upd-go" style="margin-top:8px">Попробовать ещё раз</button>`, "bad"));
document.addEventListener("visibilitychange", () => { if (!document.hidden && updWantInstall && D.updateCanInstall && D.updateCanInstall()) { updWantInstall = false; updInstall(); } });
const UPD_OLD = `<p class="hint" style="margin:8px 2px 0">Раньше обновления скачивал браузер — в «Загрузках» могли остаться старые Dewiar-….apk, их можно удалить.</p><button class="btn w" id="upd-dl" style="margin-top:6px">Открыть Загрузки</button>`;
/* «обновись» голосом: есть новее — открываем «О приложении» и запускаем обновление; нет — говорим, какая стоит.
   install=false («проверь обновления», «есть новая версия?») — только говорим и показываем «О приложении», без скачивания;
   детский режим — не скачиваем и настройки (PIN) не открываем: обновление ставит взрослый */
async function updateSay(install) {
  const mine = JSON.parse(D.info() || "{}").version || "?";
  // экзамен: проверка — по-настоящему (версия с сайта), а «О приложении» и скачивание — нет
  if (SANDBOX) SANDBOX.dev.push({ name: "app_update", args: install ? "install" : "check", argsObj: { action: install ? "install" : "check" }, t: Date.now() });
  try {
    const a = (JSON.parse((await http("GET", UPD_URL, { timeout: 10000 })).body || "{}") || {}).android;
    if (!a || cmpVer(a.version, mine) <= 0) return `У вас последняя версия — ${mine}.`;
    if (typeof kidsOn === "function" && kidsOn()) return `Есть новая версия ${a.version}. Обновление ставит взрослый.`;
    if (typeof D.handsState === "function" && D.handsState() !== "none" && !a.hands_apk)     // отчёт 835: «руки» не теряем
      return `Есть версия ${a.version}, но версии «с руками» ещё нет — обновлю, как только она появится.`;
    if (!install) {
      if (!SANDBOX) { openSettings("about"); setTimeout(() => { checkUpdate(true); }, 400); }
      return `Есть версия ${a.version}. Скажите «обновись» — обновлю.`;
    }
    if (SANDBOX) return `Есть новая версия ${a.version} — обновляю. Всё ваше сохранится.`;
    openSettings("about");
    setTimeout(() => { checkUpdate(true).then(() => { const g = $("#upd-go"); if (g) g.click(); }); }, 400);
    return `Есть новая версия ${a.version} — обновляю. Всё ваше сохранится.`;
  } catch (e) { return "Не получилось проверить обновление — нет связи с dewiar.pro. Попробуйте чуть позже."; }
}
async function checkUpdate(manual) {
  const r = $("#upd-res");
  try {
    const d = JSON.parse((await http("GET", UPD_URL, { timeout: 10000 })).body || "{}"), a = d.android;
    const newer = a && cmpVer(a.version, JSON.parse(D.info() || "{}").version || "0") > 0;
    const hands = typeof D.handsState === "function" && D.handsState() !== "none";     // стоит версия с «руками» — и обновляем её
    if (newer && hands && !a.hands_apk) {
      // отчёт 835 (17.11): «скачиваю версию с руками, приходит обновление — и руки слетают; после каждого обновления
      // скачивать заново» — в выпуске не было сборки с «руками», и ставилась обычная. Теперь ждём её, обычной не заменяем
      if (r) { r.className = "res"; r.textContent = `Есть Dewiar ${a.version}, но версии «с руками» ещё нет — обновлю, как только она появится. Обычная версия управление приложениями не умеет.`; }
      return false;
    }
    if (newer) {
      const url = UPD_URL.replace(/latest\.json$/, hands && a.hands_apk ? a.hands_apk : a.apk);
      updInfo = { version: a.version, url, sha: hands && a.hands_apk ? a.hands_sha256 : a.sha256 };
      if (r) {
        if (D.updateGet) updRender(`Есть Dewiar ${esc(a.version)}.<button class="btn w p" id="upd-go" style="margin-top:8px">Обновить</button>`);
        else { r.className = "res ok"; r.innerHTML = `Есть Dewiar ${esc(a.version)}. <a href="${esc(url)}">Скачать</a> — откройте файл и нажмите «Обновить».`; }
      } else {
        D.notify("Новая версия Dewiar " + a.version, "Ещё → О приложении → Обновить");
        // 29.10 (255 телефонов на 0.7.1: уведомление без разрешения пропадает молча) — и карточкой на главном экране, одной кнопкой
        if (!busy && state === "idle" && !($("#card") && $("#card").textContent.trim()) && S.updCardFor !== a.version) {
          S.updCardFor = a.version; saveS();
          showCard(`<div class="card upd"><b>Есть новая версия Dewiar ${esc(a.version)}</b><p class="hint" style="margin:4px 0 10px">Быстрее, с исправлениями. Всё ваше сохранится.</p>
            <div class="row2"><button class="btn p" id="updc-go" style="flex:1">Обновить</button><button class="btn" id="updc-x">Позже</button></div></div>`);
          $("#updc-go").onclick = () => { showCard(""); openSettings("about"); setTimeout(() => { checkUpdate(true).then(() => { const g = $("#upd-go"); if (g) g.click(); }); }, 400); };
          $("#updc-x").onclick = () => showCard("");
        }
      }
    } else if (manual && r) updRender("У вас последняя версия." + (D.openDownloads ? UPD_OLD : ""));
  } catch (e) { if (manual && r) { r.className = "res bad"; r.textContent = "Не проверилось: " + e.message; } }
}

/* ---------- кнопки и запуск ---------- */
/* Пауза конца фразы под манеру речи: человек нажал микрофон, пока модель ещё думает над только что сказанным (до 6 с), —
   значит, его оборвали: дальше ждём тишину дольше (S.stt.pauseExtra +150 мс, до +900 — Speech.java), а сказанное сейчас
   склеиваем с прошлым в один вопрос. Ответы без обрыва понемногу возвращают паузу (−10 мс). */
let lastStt = null, pausePrefix = null;
function pauseSync() { try { D.pauseExtra(+(S.stt.pauseExtra || 0)); } catch (e) { } }
function pauseCut() {
  if (!lastStt || lastStt.cut || state !== "thinking" || Date.now() - lastStt.at > 6000) return false;
  lastStt.cut = true; pausePrefix = { at: Date.now(), text: lastStt.text };
  S.stt.pauseExtra = Math.min(900, (+S.stt.pauseExtra || 0) + 150); saveS(); pauseSync();
  plog("info", `⏸ оборвали на полуслове — жду конца фразы дольше: +${S.stt.pauseExtra} мс`);
  toast(gfix("Понял — буду ждать, пока договорите"), 2500);
  return true;
}
function pauseOk() {
  if (!lastStt || lastStt.cut || lastStt.ok || Date.now() - lastStt.at > 180000 || !(+S.stt.pauseExtra > 0)) return;
  lastStt.ok = true; S.stt.pauseExtra = Math.max(0, +S.stt.pauseExtra - 10); saveS(); pauseSync();
}
setTimeout(pauseSync, 0);
/* Микрофон Bluetooth-наушников (BtMic.java, отчёт №51): подключены наушники с микрофоном — слушаем ими, а не телефоном */
function btMicSync() { try { if (D.btMic) D.btMic(S.btMic !== false); } catch (e) { } }
setTimeout(btMicSync, 0);
let btMicWarned = false;
N.on("stt_bt", e => {
  if (e.on) plog("info", "🎧 слушаю микрофоном Bluetooth-наушников");
  else { plog("warn", "🎧 микрофон наушников не включился — слушаю микрофоном телефона");
    if (!btMicWarned) { btMicWarned = true; toast("Микрофон наушников не включился — слушаю телефоном. Говорите ближе к телефону или переподключите наушники.", 6000); } }
});
let holdT = null, holdXY = null, holdSwallow = false;
const HOLD_MS = 320;
$("#mic").addEventListener("pointerdown", (e) => {
  if (state === "listening" || e.button > 0) return;            // слушаем — нажатие значит «хватит», как раньше
  holdXY = [e.clientX, e.clientY];
  try { $("#mic").setPointerCapture(e.pointerId); } catch (x) { }
  clearTimeout(holdT); holdT = setTimeout(holdStart, HOLD_MS);
});
$("#mic").addEventListener("pointermove", (e) => {
  if (!holdTalk || !holdXY) return;
  const far = Math.hypot(e.clientX - holdXY[0], e.clientY - holdXY[1]) > 110;
  if (far !== holdCancel) { holdCancel = far; $("#mic").classList.toggle("holdx", far); if (state === "listening") setState("listening"); if (far) D.vibrate(12); }
});
for (const t of ["pointerup", "pointercancel"]) $("#mic").addEventListener(t, () => { clearTimeout(holdT); holdT = null; if (holdTalk) holdEnd(); });
async function holdStart() {
  holdT = null; holdTalk = true; holdCancel = false; holdSwallow = true; dict = "";
  $("#mic").classList.add("hold"); D.vibrate(30);
  if (D.sttQuiet) D.sttQuiet(true);                 // без «тринька» распознавателя на каждой паузе (отзыв 13.10); начало — вибрацией
  if (state !== "idle") interrupt(true);
  plog("info", "🎙 держат кнопку — слушаю, пока не отпустят");
  await listen();
  if (!sttActive && holdTalk) { holdTalk = false; $("#mic").classList.remove("hold"); if (D.sttQuiet) D.sttQuiet(false); }   // не вышло начать (нет микрофона и т. п.)
}
function holdEnd() {
  const cancel = holdCancel;
  holdTalk = false; holdCancel = false; $("#mic").classList.remove("hold", "holdx");
  if (D.sttQuiet) D.sttQuiet(false);                // звук вернётся чуть позже — после последнего «тринька» (Speech.quiet)
  D.vibrate(cancel ? 12 : 22);                      // отпустили — коротко в руку: принято
  if (cancel) { stopListen(); setState("idle"); showYou(""); toast("Отменено"); plog("info", "🎙 отпустили в стороне — отменено"); return; }
  plog("info", `🎙 отпустили — отправляю (${(dict + " " + heardPartial).trim().length} зн.)`);
  if (sttActive) { sttUserStop = true; D.stopListen(); sttGuard(2500, "stop"); return; }     // распознаватель отдаст последнее — уйдёт всё вместе
  const t = dictTake(heardPartial); heardPartial = "";
  if (t) askHeard(t); else { setState("idle"); showYou(""); }
}
$("#mic").onclick = () => {
  if (holdSwallow) { holdSwallow = false; return; }            // это было удержание — уже обработано
  if (state === "thinking") pauseCut();
  if (state === "listening") {                    // «хватит слушать»: запись кончается сразу (stt_end продлит ожидание на распознавание); ни звука 2 с — заканчиваем сами
    if (!sttActive) { setState("idle"); return; }
    sttUserStop = true; D.stopListen(); sttGuard(2000, "stop"); return;            // сам закончил — длинная диктовка не продолжается
  }
  if (state !== "idle") interrupt(true); fsMark("mic"); listen(); };
$("#orbwrap").onclick = () => $("#mic").onclick();
/* №560 (05.11): «Стоп» — замолчать и не отвечать дальше, не включая микрофон (тем, кто пишет, а не говорит); Esc на
   клавиатуре (веб-версия, планшет с клавиатурой) — то же, если не закрывает лист или картинку (N.back) */
$("#stopx").onclick = (e) => { e.stopPropagation(); if (state === "thinking" || state === "speaking") { interrupt(); plog("info", "⏹ «Стоп» кнопкой"); } };
document.addEventListener("keydown", (e) => {
  if (e.key !== "Escape" || e.defaultPrevented || e.isComposing) return;
  if (/^(INPUT|TEXTAREA|SELECT)$/.test((document.activeElement || {}).tagName || "") && state === "idle") return;   // в поле ввода Esc — его дело
  if (N.back()) e.preventDefault();
});
new MutationObserver(() => document.body.classList.toggle("typing", $("#typebox").classList.contains("on")))
  .observe($("#typebox"), { attributes: true, attributeFilter: ["class"] });     // поле ввода открыто — сцена выше него (app.css)
$("#b-kb").onclick = () => { const b = $("#typebox"); b.classList.toggle("on"); if (b.classList.contains("on")) { typedGrow(); $("#typed").focus(); } };
/* Идея №126 (04.11): поле — многострочное, растёт вверх по мере набора до 40% высоты экрана; сцена с ответом поднимается
   над нижней панелью (--barh). Телефон (палец): Enter — новая строка, отправка — кнопкой; клавиатура компьютера (веб на
   Mac и ПК): Enter — отправить, Shift+Enter — новая строка. */
const TOUCH = !!(window.matchMedia && matchMedia("(pointer: coarse)").matches);
function typedGrow() {
  const t = $("#typed"); if (!t) return;
  t.style.height = "auto";
  const max = Math.round((window.visualViewport ? visualViewport.height : innerHeight) * 0.4);
  t.style.height = Math.min(Math.max(50, t.scrollHeight + 2), max) + "px";
  t.style.overflowY = t.scrollHeight + 2 > max ? "auto" : "hidden";
}
if (TOUCH) $("#typed").setAttribute("enterkeyhint", "enter");
$("#typed").addEventListener("input", typedGrow);
$("#typed").addEventListener("focus", typedGrow);
if (window.ResizeObserver) new ResizeObserver(() => document.documentElement.style.setProperty("--barh", $("#bar").offsetHeight + "px")).observe($("#bar"));
$("#talk-x").onclick = (e) => { e.stopPropagation(); talkDismiss(60); };
(() => {                                                  // смахнуть сказанное вбок — тоже убрать (вертикально — прокрутка, как была)
  const t = $("#talk"); let sw = null;
  t.addEventListener("touchstart", (e) => { const p = e.touches[0]; sw = p && !$("#talk-x").hidden ? { x: p.clientX, y: p.clientY } : null; }, { passive: true });
  t.addEventListener("touchmove", (e) => { if (!sw) return; const p = e.touches[0], dx = p.clientX - sw.x, dy = p.clientY - sw.y;
    if (Math.abs(dy) > 24 && Math.abs(dy) > Math.abs(dx)) { sw = null; t.style.transform = ""; return; }
    if (Math.abs(dx) > 12) { t.style.transform = `translateX(${dx}px)`; t.style.opacity = String(Math.max(.25, 1 - Math.abs(dx) / 260)); } }, { passive: true });
  t.addEventListener("touchend", (e) => { if (!sw) return; const p = e.changedTouches[0], dx = p.clientX - sw.x; sw = null;
    t.style.transform = ""; t.style.opacity = ""; if (Math.abs(dx) > 90) talkDismiss(dx > 0 ? 80 : -80); });
})();
/* Вложения: фото из галереи (уменьшается до 1280 точек) и текстовые файлы (до 30 000 знаков) — уходят модели вместе
   с вопросом (ask opts.attach). PDF, Word, Excel и PowerPoint — текстом (docText ниже, 19.11). */
let attached = [];
const ATT_MAX = 4, ATT_TEXT = 30000;
function shrinkImage(file, max = 1280) {
  return new Promise((res, rej) => {
    const u = URL.createObjectURL(file), im = new Image();
    im.onload = () => { const k = Math.min(1, max / Math.max(im.width, im.height)), c = document.createElement("canvas");
      c.width = Math.max(1, Math.round(im.width * k)); c.height = Math.max(1, Math.round(im.height * k));
      c.getContext("2d").drawImage(im, 0, 0, c.width, c.height); URL.revokeObjectURL(u); res(c.toDataURL("image/jpeg", 0.85)); };
    im.onerror = () => { URL.revokeObjectURL(u); rej(new Error("фото не открылось")); };
    im.src = u;
  });
}
/* Документы на телефоне (19.11, план «телефон читает документы»: раньше — «PDF и Word телефон пока не читает»). Как на
   компьютере (core/knowledge.extract, core/sheets.py): PDF — текстом (pdf.js, грузится только при первом PDF), Word
   (.docx), Excel (.xlsx), PowerPoint (.pptx), LibreOffice (.odt, .ods) — разбором XML внутри архива (распаковка —
   DecompressionStream браузера). Таблицы — по листам «## Лист «имя»» и строками «a | b | c», даты — ДД.ММ.ГГГГ. Скан PDF
   без текста — понятной просьбой прислать фото страницы. -> текст (может быть пустым). */
const DOC_RX = /\.(pdf|docx|xlsx|xlsm|pptx|odt|ods)$/i;
async function zipEntries(buf) {
  const v = new DataView(buf), u8 = new Uint8Array(buf);
  let e = -1;
  for (let i = buf.byteLength - 22; i >= Math.max(0, buf.byteLength - 66000); i--) if (v.getUint32(i, true) === 0x06054b50) { e = i; break; }
  if (e < 0) throw new Error("файл повреждён или это не документ Office");
  const n = v.getUint16(e + 10, true); let off = v.getUint32(e + 16, true); const out = {};
  const dec = new TextDecoder();
  for (let k = 0; k < n; k++) {
    if (v.getUint32(off, true) !== 0x02014b50) break;
    const method = v.getUint16(off + 10, true), csize = v.getUint32(off + 20, true), usize = v.getUint32(off + 24, true);
    const nl = v.getUint16(off + 28, true), xl = v.getUint16(off + 30, true), cl = v.getUint16(off + 32, true), lho = v.getUint32(off + 42, true);
    const name = dec.decode(u8.subarray(off + 46, off + 46 + nl));
    out[name] = { method, csize, usize, lho };
    off += 46 + nl + xl + cl;
  }
  out.__read = async (name) => {
    const z = out[name]; if (!z || z.usize > 64e6) return null;
    const s = z.lho + 30 + v.getUint16(z.lho + 26, true) + v.getUint16(z.lho + 28, true), data = u8.subarray(s, s + z.csize);
    if (z.method === 0) return dec.decode(data);
    if (z.method !== 8) return null;
    const st = new Blob([data]).stream().pipeThrough(new DecompressionStream("deflate-raw"));
    return await new Response(st).text();
  };
  return out;
}
const xmlUn = (t) => String(t || "").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&apos;/g, "'")
  .replace(/&#(\d+);/g, (_, d) => String.fromCodePoint(+d)).replace(/&#x([0-9a-f]+);/gi, (_, h) => String.fromCodePoint(parseInt(h, 16))).replace(/&amp;/g, "&");
const tagTexts = (xml, tag) => [...String(xml).matchAll(new RegExp(`<${tag}\\b[^>]*>([\\s\\S]*?)</${tag}>`, "g"))].map(m => xmlUn(m[1]));
function sheetsRender(sheets) {
  return sheets.map(([title, rows]) => {
    rows = rows.filter(r => r.some(Boolean)); if (!rows.length) return "";
    return `## Лист «${title}» · строк ${rows.length}\n` + rows.map(r => r.join(" | ")).join("\n");
  }).filter(Boolean).join("\n\n");
}
function xlsDate(v, d1904) {
  const f = +v; if (!isFinite(f)) return v;
  const d = new Date(Date.UTC(d1904 ? 1904 : 1899, d1904 ? 0 : 11, d1904 ? 1 : 30) + Math.round(f * 86400e3));
  const p = (x) => String(x).padStart(2, "0"), day = `${p(d.getUTCDate())}.${p(d.getUTCMonth() + 1)}.${d.getUTCFullYear()}`;
  return Math.abs(f - Math.floor(f)) < 1e-9 ? day : f < 1 ? `${p(d.getUTCHours())}:${p(d.getUTCMinutes())}` : `${day} ${p(d.getUTCHours())}:${p(d.getUTCMinutes())}`;
}
const xlsNum = (v) => { const f = +v; return !isFinite(f) ? v : (Number.isInteger(f) ? String(f) : String(+f.toPrecision(10))); };
async function xlsxText(z) {
  const shared = z["xl/sharedStrings.xml"] ? [...(await z.__read("xl/sharedStrings.xml")).matchAll(/<si\b[^>]*>([\s\S]*?)<\/si>/g)]
    .map(m => tagTexts(m[1].replace(/<rPh\b[\s\S]*?<\/rPh>/g, ""), "t").join("")) : [];
  const wb = await z.__read("xl/workbook.xml") || "", d1904 = /date1904="(1|true)"/.test(wb);
  const rels = {}; for (const m of String(await z.__read("xl/_rels/workbook.xml.rels") || "").matchAll(/<Relationship\b([^>]*)\/?>/g)) {
    const id = (m[1].match(/Id="([^"]+)"/) || [])[1], t = (m[1].match(/Target="([^"]+)"/) || [])[1];
    if (id && t) rels[id] = t.replace(/^\//, "").startsWith("xl/") ? t.replace(/^\//, "") : "xl/" + t.replace(/^\//, "");
  }
  const st = String(await z.__read("xl/styles.xml") || ""), custom = {};
  for (const m of st.matchAll(/<numFmt\b[^>]*numFmtId="(\d+)"[^>]*formatCode="([^"]*)"/g)) {
    const c = xmlUn(m[2]).replace(/"[^"]*"|\[[^\]]*\]|\\./g, "").toLowerCase(); custom[m[1]] = /[dmyдмг]/.test(c) && !/0[.,]0|#/.test(c);
  }
  const xfs = (st.match(/<cellXfs\b[^>]*>([\s\S]*?)<\/cellXfs>/) || [])[1] || "", dates = new Set();
  [...xfs.matchAll(/<xf\b([^>]*)\/?>/g)].forEach((m, i) => { const id = +((m[1].match(/numFmtId="(\d+)"/) || [])[1] || 0);
    if ((id >= 14 && id <= 22) || (id >= 45 && id <= 47) || custom[id]) dates.add(i); });
  const sheets = [];
  for (const m of wb.matchAll(/<sheet\b([^>]*)\/?>/g)) {
    if (/state="(hidden|veryHidden)"/.test(m[1])) continue;
    const nm = xmlUn((m[1].match(/name="([^"]*)"/) || [])[1] || ""), rid = (m[1].match(/r:id="([^"]+)"/) || [])[1], path = rels[rid];
    const x = path && await z.__read(path); if (!x) continue;
    const rows = [];
    for (const r of x.matchAll(/<row\b[^>]*>([\s\S]*?)<\/row>/g)) {
      const cells = [];
      for (const c of r[1].matchAll(/<c\b([^>]*?)(?:\/>|>([\s\S]*?)<\/c>)/g)) {
        const a = c[1], body = c[2] || "", ref = (a.match(/\br="([A-Z]+)\d+"/) || [])[1];
        const col = ref ? [...ref].reduce((s, ch) => s * 26 + ch.charCodeAt(0) - 64, 0) - 1 : cells.length; if (col >= 60) continue;
        const t = (a.match(/\bt="(\w+)"/) || [])[1] || "n"; let v = xmlUn((body.match(/<v\b[^>]*>([\s\S]*?)<\/v>/) || [])[1] || "");
        if (t === "s") v = shared[+v] || ""; else if (t === "inlineStr") v = tagTexts(body, "t").join("");
        else if (t === "b") v = v === "1" ? "да" : v === "0" ? "нет" : v;
        else if (t === "n" && v !== "") { const s = (a.match(/\bs="(\d+)"/) || [])[1]; v = s != null && dates.has(+s) ? xlsDate(v, d1904) : xlsNum(v); }
        cells[col] = String(v).replace(/\s*\n\s*/g, " ").replace(/\|/g, "/").trim();
      }
      rows.push(Array.from(cells, x => x || ""));
      if (rows.length >= 20000) break;
    }
    sheets.push([nm, rows]);
  }
  return sheetsRender(sheets);
}
async function odfText(z, calc) {
  const x = await z.__read("content.xml") || "";
  if (!calc) return tagTexts(x.replace(/<text:h\b/g, "<text:p").replace(/<\/text:h>/g, "</text:p>"), "text:p").map(t => t.replace(/<[^>]+>/g, "")).filter(Boolean).join("\n");
  const sheets = [];
  for (const t of x.matchAll(/<table:table\b([^>]*)>([\s\S]*?)<\/table:table>/g)) {
    const rows = [];
    for (const r of t[2].matchAll(/<table:table-row\b([^>]*?)(?:\/>|>([\s\S]*?)<\/table:table-row>)/g)) {
      const cells = [];
      for (const c of (r[2] || "").matchAll(/<table:(?:covered-)?table-cell\b([^>]*?)(?:\/>|>([\s\S]*?)<\/table:(?:covered-)?table-cell>)/g)) {
        const a = c[1]; let v = "";
        const dv = (a.match(/office:date-value="([^"]+)"/) || [])[1];
        if (dv) { const d = dv.match(/^(\d{4})-(\d\d)-(\d\d)(?:T(\d\d):(\d\d))?/); v = d ? `${d[3]}.${d[2]}.${d[1]}` + (d[4] && d[4] + d[5] !== "0000" ? ` ${d[4]}:${d[5]}` : "") : dv; }
        if (!v) v = tagTexts(c[2] || "", "text:p").map(s => s.replace(/<[^>]+>/g, "")).join(" ");
        const rep = Math.min(+((a.match(/number-columns-repeated="(\d+)"/) || [])[1] || 1), 60);
        for (let i = 0; i < rep && cells.length < 60; i++) cells.push(v.replace(/\|/g, "/").trim());
      }
      while (cells.length && !cells[cells.length - 1]) cells.pop();
      const rr = Math.min(+((r[1].match(/number-rows-repeated="(\d+)"/) || [])[1] || 1), cells.length ? 50 : 1);
      for (let i = 0; i < rr; i++) rows.push(cells);
      if (rows.length >= 20000) break;
    }
    sheets.push([xmlUn((t[1].match(/table:name="([^"]*)"/) || [])[1] || "Лист"), rows]);
  }
  return sheetsRender(sheets);
}
let pdfLib = null;
function pdfLoad() {
  if (pdfLib) return pdfLib;
  pdfLib = new Promise((ok, no) => {
    if (window.pdfjsLib) return ok(window.pdfjsLib);
    const s = document.createElement("script"); s.src = window.DEWIAR_PDFJS_SRC || "vendor/pdf.min.js";
    s.onload = () => { const L = window.pdfjsLib; if (!L) return no(new Error("чтение PDF не загрузилось"));
      L.GlobalWorkerOptions.workerSrc = s.src.replace(/pdf\.min\.js$/, "pdf.worker.min.js"); ok(L); };
    s.onerror = () => { pdfLib = null; no(new Error("чтение PDF не загрузилось")); };
    document.head.appendChild(s);
  });
  return pdfLib;
}
async function pdfText(buf) {
  const L = await pdfLoad();
  const doc = await L.getDocument({ data: new Uint8Array(buf), isEvalSupported: false, disableFontFace: true, useSystemFonts: false }).promise;
  const out = []; let len = 0;
  for (let i = 1; i <= Math.min(doc.numPages, 500) && len < 2e6; i++) {
    const tc = await (await doc.getPage(i)).getTextContent();
    let line = "", lines = [];
    for (const it of tc.items) { line += it.str; if (it.hasEOL) { lines.push(line); line = ""; } }
    if (line) lines.push(line);
    const t = lines.join("\n").replace(/[ \t]+\n/g, "\n").trim();
    if (t) { out.push(`— стр. ${i} —\n${t}`); len += t.length; }
  }
  return { text: out.join("\n\n"), pages: doc.numPages };
}
async function docText(f) {
  const ext = ((f.name || "").match(DOC_RX) || [])[1] || (/pdf/.test(f.type) ? "pdf" : "");
  const buf = await f.arrayBuffer();
  if (ext.toLowerCase() === "pdf") {
    const r = await pdfText(buf);
    if (!r.text.trim()) throw new Error(`в PDF нет текста — похоже, это скан (${r.pages} стр.). Пришлите фото нужной страницы — я её прочитаю`);
    return r.text;
  }
  const z = await zipEntries(buf), e = ext.toLowerCase();
  if (e === "docx") return tagTexts(await z.__read("word/document.xml") || "", "w:p").map(p => tagTexts(p, "w:t").join("")).filter(Boolean).join("\n");
  if (e === "xlsx" || e === "xlsm") return xlsxText(z);
  if (e === "pptx") {
    const sl = Object.keys(z).filter(n => /^ppt\/slides\/slide\d+\.xml$/.test(n)).sort((a, b) => +a.match(/(\d+)\.xml/)[1] - +b.match(/(\d+)\.xml/)[1]);
    const out = []; for (const [i, n] of sl.entries()) out.push(`## Слайд ${i + 1}\n` + tagTexts(await z.__read(n), "a:p").map(p => tagTexts(p, "a:t").join("")).filter(Boolean).join("\n"));
    return out.join("\n\n");
  }
  if (e === "odt" || e === "ods") return odfText(z, e === "ods");
  throw new Error("такой документ не открыть");
}
async function addAttach(f) {
  if (attached.length >= ATT_MAX) { toast(`Не больше ${ATT_MAX} вложений за раз`); return; }
  try {
    if (/^image\//.test(f.type)) attached.push({ kind: "image", name: f.name || "фото", url: await shrinkImage(f) });
    else if (/^text\/|json|csv|xml|markdown/.test(f.type) || /\.(txt|md|csv|json|log|xml|html?)$/i.test(f.name || "")) {
      const t = await f.text(); attached.push({ kind: "text", name: f.name || "файл", text: t.slice(0, ATT_TEXT), cut: t.length > ATT_TEXT });
    } else if (DOC_RX.test(f.name || "") || /pdf|officedocument|opendocument/.test(f.type)) {
      if (f.size > 25e6) { toast("Файл больше 25 МБ — пришлите часть или нужные страницы фото"); return; }
      toast("Читаю «" + (f.name || "документ") + "»…", 1500);
      const t = await docText(f);
      if (!t.trim()) { toast("В документе нет текста — пришлите фото нужной страницы"); return; }
      attached.push({ kind: "text", name: f.name || "документ", text: t.slice(0, ATT_TEXT), cut: t.length > ATT_TEXT });
    } else toast(/msword|ms-excel|ms-powerpoint/.test(f.type) || /\.(doc|xls|ppt)$/i.test(f.name || "") ? "Старый формат Office — сохраните как .docx, .xlsx или .pptx (или пришлите фото страницы)" : "Такой файл не открыть — подойдут фото, тексты, PDF, Word и Excel");
  } catch (e) { toast("Не получилось открыть: " + e.message); }
}
function renderAtts() {
  const box = $("#atts");
  box.innerHTML = attached.map((a, i) => `<div class="at${a.pasted ? " pasted" : ""}" data-i="${i}">${a.kind === "image" ? `<img src="${a.url}" alt="">` : `<span>${esc(a.name)}</span>`}<button data-i="${i}" title="Убрать">${X_SVG}</button></div>`).join("");
  $$("button", box).forEach(b => b.onclick = (ev) => { ev.stopPropagation(); attached.splice(+b.dataset.i, 1); renderAtts(); });
  $$(".at.pasted", box).forEach(d => d.onclick = () => {      // нажатие — вставленный текст обратно в поле
    const a = attached[+d.dataset.i], t = $("#typed"); attached.splice(+d.dataset.i, 1);
    t.value = a.text + (t.value.trim() ? "\n\n" + t.value : ""); typedGrow(); renderAtts(); t.focus(); });
}
/* Длинная вставка — вложением (№918, владелец 20.11), как на компьютере: поле — для вопроса, модель получает текст целиком. */
const PASTE_AS_FILE = 2000;
$("#typed").addEventListener("paste", (e) => {
  const txt = e.clipboardData && e.clipboardData.getData("text");
  if (!txt || txt.length <= PASTE_AS_FILE || attached.length >= ATT_MAX) return;
  e.preventDefault();
  attached.push({ kind: "text", name: "Вставленный текст", text: txt.slice(0, ATT_TEXT), cut: txt.length > ATT_TEXT, pasted: true });
  renderAtts(); $("#typebox").classList.add("on");
});
$("#b-att").onclick = () => $("#att-file").click();
$("#att-file").onchange = async (e) => {
  for (const f of Array.from(e.target.files || [])) await addAttach(f);
  e.target.value = ""; renderAtts(); $("#typebox").classList.add("on");
};
const sendTyped = () => {
  const t = $("#typed").value.trim(); if (!t && !attached.length) return;
  fsMark("type");
  const att = attached; attached = []; renderAtts();
  $("#typed").value = ""; typedGrow(); $("#typed").blur();
  ask(t || (att.some(a => a.kind === "image") ? "Посмотри, пожалуйста." : "Посмотри этот файл."), att.length ? { attach: att } : {});
};
$("#send").onclick = sendTyped;
$("#typed").onkeydown = (e) => {
  if (e.key !== "Enter" || e.shiftKey || e.isComposing || e.keyCode === 229 || TOUCH) return;    // новая строка
  e.preventDefault(); sendTyped();
};
N.on("intent", (e) => handleIntent(e));
N.on("htmlview", (e) => { const f = htmlViewSave; htmlViewSave = null; if (e.save && f) f(); });
// вернулись из настроек Android после «Включить» — карточка «Управлять приложениями» показывает новое состояние
N.on("resume", () => { if (tgHandOn()) tgHandLater(300); });
N.on("resume", () => { if (handsAsked && Date.now() - handsAsked < 10 * 60000 && $("#hands-card")) { $("#hands-card").innerHTML = handsCard(); wireHands(); } });
N.on("resume", () => { try { handsWatch(false); } catch (e) { } });
N.on("resume", () => { try { remLateWatch(false); if (setTab === "sound" && $("#rem-health") && $("#sh-set").classList.contains("on")) renderSettings(); } catch (e) { } });   // вернулись из настроек Android — карточка свежая
setTimeout(() => { try { remLateWatch(true); } catch (e) { } }, 3500);
setTimeout(() => { try { handsWatch(true); } catch (e) { } }, 2500);   // после приветствия: карточка не перебивает его
N.on("pause", () => { if (state === "listening") stopListen(), setState("idle"); });
/* Что пришло снаружи (MainActivity.handle): при запуске — через Dewiar.takeIntent(), когда страница уже открыта — событием
   intent. listen — кнопка помощника, type — ярлык «написать», say — текст из «Поделиться», import — файл настроек,
   link — ссылка dewiar:// (QR с настройками или адрес сервера). */
function handleIntent(e) {
  if (!e || !e.action) return;
  if (e.action === "listen") { closeSheets(); listen(); }
  else if (e.action === "say") {        // текст, которым поделилось другое приложение, — в поле ввода: отправляет сам человек
    closeSheets(); $("#typebox").classList.add("on"); $("#typed").value = String(e.text || "").slice(0, 4000); typedGrow(); setTimeout(() => $("#typed").focus(), 300); }
  else if (e.action === "type") { closeSheets(); $("#typebox").classList.add("on"); setTimeout(() => $("#typed").focus(), 300); }
  else if (e.action === "images") {     // фото из «Поделиться» — во вложения; подпись пишет сам человек («напомни завтра в 10»)
    closeSheets(); attached = attached.concat((e.images || []).map((url, i) => ({ kind: "image", name: "фото " + (i + 1), url }))).slice(0, ATT_MAX);
    renderAtts(); $("#typebox").classList.add("on"); if (e.text && !$("#typed").value) { $("#typed").value = String(e.text).slice(0, 2000); typedGrow(); }
    $("#typed").placeholder = "Например: напомни завтра в 10"; setTimeout(() => $("#typed").focus(), 300); }
  else if (e.action === "note") openNoteSoon(e.id);           // «Посмотреть вложения» в окне напоминания
  else if (e.action === "capture") captureStart();             // значок «Записать» на рабочем столе
  else if (e.action === "import") { try { const m = JSON.parse(e.text); if (!cfgAsk(m)) return; applyConfig(m, ""); showBot("Настройки с компьютера применены. Мозг: " + brainName() + "."); } catch (x) { showBot("Файл настроек не подошёл: " + x.message, "err"); } }
  else if (e.action === "link" && /^dewiar:\/\/import/.test(e.url || "")) {        // QR из студии на компьютере
    try {
      let c = (/[?&]c=([^&]+)/.exec(e.url) || [])[1] || ""; c = c.replace(/-/g, "+").replace(/_/g, "/"); while (c.length % 4) c += "=";
      const m = JSON.parse(decodeURIComponent(escape(atob(c))));
      if (!m.llm && ((m.home && m.home.token) || (m.ha && m.ha.token))) {          // только умный дом с компьютера
        if (!confirm(`Подключить на телефоне ${cfgHomesName(m)} — тот же, что на компьютере? Мозг и голос телефона не изменятся.`)) return;
        cfgHomes(m);
        showBot("Готово — умный дом подключён. Скажите: «включи свет в спальне»."); say("Готово! Умный дом подключён."); return;
      }
      if (!cfgAsk(m)) return;
      applyConfig(m, ""); cfgHomes(m);
      showBot(`Готово — настройки с компьютера перенесены. Мозг: ${brainName()}. Нажмите микрофон и спросите что-нибудь.`); say("Готово! Настройки перенесены.");
    } catch (x) { showBot("Код с настройками не подошёл: " + x.message, "err"); }
  }
  else if (e.action === "close") openClose("");                                     // нажали уведомление «Близких»
  else if (e.action === "work") openWork("");                                       // уведомление «Работы» (CloseWatch)
  else if (e.action === "link" && /^dewiar:\/\/home\?/.test(e.url || "")) homeClaimFlow(e.url);   // синхронизация по Wi-Fi (0.59)
  else if (e.action === "link" && /^dewiar:\/\/pair/.test(e.url || "")) devClaimFlow(e.url);      // код устройства (download.php?pair=)
  else if (e.action === "link" && /^dewiar:\/\/work/.test(e.url || "")) wkLink(e.url);         // приглашение на работу (download.php?work=)
  else if (e.action === "news") { closeSheets(); annCheck(true); }                   // уведомление объявления (CloseLive)
  else if (e.action === "close_call") {                                             // уведомление звонка близкого (CloseLive)
    clAutoAnswer = e.answer ? { pid: e.pid, until: Date.now() + 40000 } : null; clPoll(); }
  else if (e.action === "link" && /^dewiar:\/\/close/.test(e.url || "")) clAcceptLink(e.url);    // приглашение в «Близкие»
  else if (e.action === "link" && /^dewiar:\/\/ref/.test(e.url || "")) {            // приглашение друга: …/download.php?ref= → «Открыть в Dewiar»
    S.refPending = ((/[?&]c=([A-Za-z0-9]+)/.exec(e.url) || [])[1] || "").toUpperCase(); saveS();
    if (S.llm.cloud) refPendingUse();
    else showBot("Код приглашения сохранён. Подключите мозг Dewiar — и подарок придёт сам.");
  }
  else if (e.action === "link") { const m = /server=([^&]+)/.exec(e.url || ""); if (m) { openSettings("brain"); setTimeout(() => { const d = $(".brainalt"); if (d) d.open = true; $('.tile[data-w="pc"]').click(); $("#w-addr").value = decodeURIComponent(m[1]); }, 300); } }
}
