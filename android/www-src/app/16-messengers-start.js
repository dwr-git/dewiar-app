//@ Телефон и веб-версия, часть 16: мессенджеры, кнопки и запуск.
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
function sendTo(app, text) {
  const m = MESSENGERS[app] || MESSENGERS.max; text = String(text || "").trim();
  if (!text) return "Нечего отправлять — скажите текст сообщения.";
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
                m && m.tts && m.tts.remote && m.tts.remote.base_url && "Голос: " + host(m.tts.remote.base_url)].filter(Boolean);
  return confirm("Перенести настройки?\n\n" + (rows.join("\n") || "без серверов") + "\n\nСоглашайтесь, только если сами открыли этот код в своей студии Dewiar.");
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
  if (state !== "idle") interrupt(true); listen(); };
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
   с вопросом (ask opts.attach). PDF и документы Word телефон пока не читает — честно говорим. */
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
async function addAttach(f) {
  if (attached.length >= ATT_MAX) { toast(`Не больше ${ATT_MAX} вложений за раз`); return; }
  try {
    if (/^image\//.test(f.type)) attached.push({ kind: "image", name: f.name || "фото", url: await shrinkImage(f) });
    else if (/^text\/|json|csv|xml|markdown/.test(f.type) || /\.(txt|md|csv|json|log|xml|html?)$/i.test(f.name || "")) {
      const t = await f.text(); attached.push({ kind: "text", name: f.name || "файл", text: t.slice(0, ATT_TEXT), cut: t.length > ATT_TEXT });
    } else toast(/pdf|word|officedocument/.test(f.type) ? "PDF и Word телефон пока не читает — пришлите фото страницы или текст" : "Такой файл не открыть — подойдут фото и текстовые файлы", 4000);
  } catch (e) { toast("Не получилось открыть: " + e.message); }
}
function renderAtts() {
  const box = $("#atts");
  box.innerHTML = attached.map((a, i) => `<div class="at">${a.kind === "image" ? `<img src="${a.url}" alt="">` : `<span>${esc(a.name)}</span>`}<button data-i="${i}" title="Убрать">${X_SVG}</button></div>`).join("");
  $$("button", box).forEach(b => b.onclick = () => { attached.splice(+b.dataset.i, 1); renderAtts(); });
}
$("#b-att").onclick = () => $("#att-file").click();
$("#att-file").onchange = async (e) => {
  for (const f of Array.from(e.target.files || [])) await addAttach(f);
  e.target.value = ""; renderAtts(); $("#typebox").classList.add("on");
};
const sendTyped = () => {
  const t = $("#typed").value.trim(); if (!t && !attached.length) return;
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
      if (!m.llm && m.home && m.home.token) {                                      // только умный дом с компьютера
        if (!confirm("Подключить на телефоне умный дом Яндекса — тот же, что на компьютере? Мозг и голос телефона не изменятся.")) return;
        homeSet(String(m.home.token));
        showBot("Готово — умный дом подключён. Скажите: «включи свет в спальне»."); say("Готово! Умный дом подключён."); return;
      }
      if (!cfgAsk(m)) return;
      applyConfig(m, ""); if (m.home && m.home.token) homeSet(String(m.home.token));
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
