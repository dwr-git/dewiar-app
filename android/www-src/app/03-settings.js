//@ Телефон и веб-версия, часть 03: настройки (одна строка JSON в pref «settings») и отчёты разработчику.
//@ Собирается в android/assets/www/app.js (tools/app_join.py) — порядок частей = порядок исполнения; шапка «//@» в app.js не попадает.
/* ---------- настройки: одна строка JSON в pref "settings" (SharedPreferences, Bridge.java); чего нет — из DEF ---------- */
const DEF = {
  sync: { on: true },
  persona: "lira", user_name: "", follow: "ask",
  join: null,                                   // заявка на Dewiar из приложения: {id, secret, base} — ждём ключ (joinPoll)
  welcome: { on: true, seen: 0, at: 0 },        // «сам замечает»: seen — когда приложение последний раз было на экране, at — когда здоровались
  llm: { kind: "openai", name: "", base_url: "", api_key: "", model: "", disable_thinking: true, temperature: 0.7, cloud: false, title: "", account: false },
  stt: { engine: "system", url: "", key: "", model: "" },
  account: { server: "", login: "", token: "", user: {}, rag_url: "", services: {}, problem: "" },
  net: { proxy: "", dewiar: false, dewiar_secret: "", dewiar_at: 0, web_via: true },   // прокси для серверов Dewiar: свой или «прокси Dewiar»
  kb: {}, accCloud: null, tg: { linked: false },
  // голос: system — устройства (sys_voice — героинь и по умолчанию, sys_voice_m — героев; пусто — подберём сами), cloud — Dewiar,
  // server — свой OpenAI-совместимый сервер (voice / voice_m), eleven — ElevenLabs своим ключом (el_*)
  tts: { engine: "system", url: "", key: "", model: "", voice: "", voice_m: "", rate: 1.0, sys_voice: "", sys_voice_m: "",
         el_key: "", el_model: "eleven_flash_v2_5", el_voice_f: "", el_voice_m: "" },
  home: { token: "", client_id: "", at: 0 },
  ha: { url: "", token: "", at: 0 },                  // Home Assistant: адрес и долгосрочный токен (только в телефоне и своим устройствам)
  tries: null,                   // «Попробуйте сказать» на пустом экране у новичка: {n — сколько раз спросил сам, off — скрыл}
  memory: [], onboarded: false, textMode: false,   // textMode — отвечать только текстом (значок динамика вверху)
  relations: {},                 // кто есть кто в контактах: {жена: {name, number}} — «позвони жене» (doCall, REL)
  report: { auto: null },        // отчёты разработчику при сбое: null — ещё не спрашивали
  pulse: true, who: "", dev: "", // анонимный пульс для «Здоровья»; как подписать в «Помощниках проекта»; случайный номер установки
  complaints: [],                // мои жалобы: {id, s (секрет), base, note, ts, status, reply, fixed, reward, shot}
  // «Возможности» (24.10, владелец: «люди пугаются всего — опциональное включение функций»): у новых «Рядом» и «Встречи»
  // выключены, «Досуг» (игры) включён; у тех, кто уже пользуется, всё как было (ниже, после чтения настроек)
  features: { games: true, near: false, meet: false },
};
let S = (() => { try { return Object.assign({}, DEF, JSON.parse(prefGet("settings") || "{}")); } catch (e) { return Object.assign({}, DEF); } })();
for (const k of ["llm", "stt", "tts", "home", "account", "net", "tg"]) S[k] = Object.assign({}, DEF[k], S[k] || {});
{ let raw = {}; try { raw = JSON.parse(prefGet("settings") || "{}") || {}; } catch (e) { }
  if (!raw.features || typeof raw.features !== "object") S.features = Object.keys(raw).length ? { games: true, near: true, meet: true } : Object.assign({}, DEF.features); }
/* «Сеть Лиры» (владелец 14.11, вариант А: «на ноды ничего не приходит» — переключатель у всех был выключен): у НОВОЙ
   установки общие вопросы (без личного; имена и телефоны — метками) иногда отвечает Сеть; кто уже пользовался — как было.
   Честная строка — в «Мозге» у облака и в карточке «Сеть Лиры». */
{ let raw = {}; try { raw = JSON.parse(prefGet("settings") || "{}") || {}; } catch (e) { }
  if (!Object.keys(raw).length && S.netShare === undefined) S.netShare = true; }
/* Язык приложения (0.96): «auto» — по языку системы (русский — если система на русском, украинском, белорусском,
   казахском; есть словарь языка системы — он; иначе английский), или выбранный в «Оформлении». Кто пользовался до 0.96 —
   остаётся по-русски (как на компьютере в 0.88). Словари и перевод — те же, что у студии (assets/i18n.js). */
{ let raw = {}; try { raw = JSON.parse(prefGet("settings") || "{}") || {}; } catch (e) { }
  if (!S.lang) S.lang = Object.keys(raw).length ? "ru" : "auto"; }
function phoneSysLang() {
  // без телефона и без моста браузера (D.mock — проверки, файл в браузере) — русский, как раньше; проверка английского
  // ставит window.DW_SYS_LANG сама: у Chromium без экрана язык en-US, и все прежние проверки телефона стали бы английскими
  if (D.mock && !window.DW_SYS_LANG) return "ru";
  const RU = ["ru", "uk", "be", "kk"];
  const l = String(window.DW_SYS_LANG || (navigator.languages && navigator.languages[0]) || navigator.language || "ru").slice(0, 2).toLowerCase();
  if (RU.includes(l)) return "ru";
  // 15.11, №732 («проблема вернулась: язык распознавания английский, русскую речь не распознаёт, прошивка не русифицирована»):
  // Xiaomi и другие с глобальной прошивкой — система по-английски, а человек говорит по-русски. Как на компьютере (русская
  // раскладка): русский среди языков системы или часовой пояс России, Беларуси, Казахстана, Украины — русский
  if (!window.DW_SYS_LANG && l === "en") {
    const all = (navigator.languages || []).map(x => String(x).slice(0, 2).toLowerCase());
    let tz = ""; try { tz = Intl.DateTimeFormat().resolvedOptions().timeZone || ""; } catch (e) { }
    if (all.some(x => RU.includes(x)) || RU_TZ.test(tz)) return "ru";
  }
  return window.dwLangs && dwLangs().some(x => x.code === l) ? l : "en";
}
const RU_TZ = /^(Europe\/(Moscow|Minsk|Kaliningrad|Samara|Volgograd|Saratov|Ulyanovsk|Astrakhan|Kirov|Kiev|Kyiv|Simferopol)|Asia\/(Yekaterinburg|Omsk|Novosibirsk|Barnaul|Tomsk|Novokuznetsk|Krasnoyarsk|Irkutsk|Chita|Yakutsk|Khandyga|Vladivostok|Ust-Nera|Magadan|Sakhalin|Srednekolymsk|Kamchatka|Anadyr|Almaty|Qostanay|Aqtobe|Aqtau|Atyrau|Oral|Qyzylorda))$/;
if (window.dwSetLang) dwSetLang(S.lang || "auto", phoneSysLang());
const FEAT_OPTIN = { family: 1 };                           // эти — по желанию: пока не включили, выключены
const feat = (k) => { const v = (S.features || {})[k]; return v === undefined ? !FEAT_OPTIN[k] : v !== false; };   // «Возможности»: включено ли (нет ключа — да)
// 22.10: облако отклоняло chat_template_kwargs, а телефон сразу переходил на функции текстом и запоминал это — один раз
// проверим заново: теперь сначала пробуется запрос без chat_template_kwargs, с функциями полем (так они работают лучше)
// 22.10, вечер: настоящая причина — сайт превращал пустой {} в схеме функции в [] (cloud.php chat_schema_fix): ещё раз
if (S.llm.tools_prompt && !S.llm.rej_v3) { delete S.llm.tools_prompt; S.llm.rej_v3 = 1; }
applyProxy();                                      // прокси для серверов Dewiar — с первого запроса
function saveS() { llmRemember(); prefSet("settings", JSON.stringify(S)); applyProxy(); setTimeout(startCardCheck, 0); setTimeout(() => { try { noticeSync(); } catch (e) { } }, 0); }
/* Прежние мозги (отчёт №117, 19.10: «отправил настройки с компьютера — телефон не подключается, и на Dewiar не вернуться; на
   компьютере между моделями переключаюсь, на телефоне нет»). Подключили другой мозг — прежний запоминается (до 5) и в
   «Мозге» его можно вернуть одной кнопкой. Забыли ключ или вышли из аккаунта — облачные из списка уходят. */
function llmId(l) { return l && l.base_url && !l.trial ? (l.cloud ? "cloud|" + (l.account ? "acc" : l.api_key || "") : l.base_url.replace(/\/+$/, "") + "|" + (l.model || "")) : ""; }
let llmSeen = JSON.parse(JSON.stringify(S.llm || {}));
function llmRemember() {
  const a = llmId(llmSeen), b = llmId(S.llm);
  let list = Array.isArray(S.llmSaved) ? S.llmSaved : [];
  if (a !== b && a) {
    if (b || !llmSeen.cloud) list = [llmSeen].concat(list.filter(x => llmId(x) !== a));
    else list = list.filter(x => !x.cloud || x.forgot);     // облако «забыли» (ключ, выход) — не держим и прежние облачные (кроме забытого кнопкой: его можно вернуть)
  }
  S.llmSaved = list.filter(x => llmId(x) && llmId(x) !== b).slice(0, 5);
  llmSeen = JSON.parse(JSON.stringify(S.llm || {}));
}
/* Что можно вернуть: прежние мозги, а для тех, кто подключался до этого списка, — Dewiar Облако по ключу, что остался у слуха. */
function llmBack() {
  const out = (S.llmSaved || []).filter(x => !(x.cloud && x.account && !loggedIn()) && !(x.forgot && Date.now() - x.forgot > 30 * 864e5));
  if (!S.llm.cloud && !out.some(x => x.cloud) && /^dw-/.test(S.stt.key || "") && /cloud\.php/.test(S.stt.url || ""))
    out.push({ cloud: true, base_url: S.stt.url, api_key: S.stt.key, name: "Dewiar Облако", restore: "key" });
  return out;
}
function brainNameOf(l) { return l.cloud ? "Dewiar Облако" + (l.account ? " · по аккаунту" : l.forgot ? ` · забытый ключ …${String(l.api_key || "").slice(-4)}` : "") : `${l.name || l.base_url.replace(/^https?:\/\//, "")}${l.model ? " · " + l.model : ""}${l.got ? ` · с «${l.got}»` : ""}`; }
async function llmRestore(i) {
  const l = llmBack()[i]; if (!l) return;
  if (l.cloud) await cloudConnect(l.account ? S.account.token : l.api_key, l.base_url.split("?")[0], { account: !!l.account });
  else { S.llm = Object.assign({}, DEF.llm, l); delete S.llm.restore; delete S.llm.got; saveS(); }
  cloudInfo = l.cloud ? cloudInfo : null;
}
/* Первый запуск показывает «Подключить мозг Dewiar» / «У меня есть код». Подключились любым путём (вход аккаунтом, ключ,
   код с другого устройства, одобренная заявка) — карточка уходит, Лира говорит, что готова (отчёт №50, 13.10: вошёл
   логином и паролем, а на экране всё ещё «Подключить мозг Dewiar» — человек решил, что не подключился). */
/* №454 (01.11, телефон 0.9.16): «ИИ дописывает ответ — и его закрывает баннер „Готово, всё подключено…“». Искали любую
   .start в карточке, так же выглядят и карточки «Звук на нуле — включить и прочитать ответ» (volCard) и «В коде ссылка»:
   после ответа saveS() звал проверку, и она «убирала карточку первого запуска» — затирала ответ. Теперь только своя
   карточка первого запуска (data-first) — и ответ на экране не трогаем. */
function startCardCheck() {
  const c = $("#card [data-first], #card [onclick*='joinPoll']");
  if (!c || !((S.llm.base_url && !S.llm.trial) || loggedIn())) return;     // пробный разговор — ещё не «подключено»
  showCard("");
  if (!busy && state === "idle") greet(`Готово, всё подключено${loggedIn() ? " — аккаунт " + (S.account.login || "") : ""}. Нажмите на вопрос ниже — или на микрофон и говорите.`);
  plog("info", "🧠 мозг подключён — карточка первого запуска убрана");
}

/* ---------- отчёты разработчику: кнопка «Отправить отчёт» и тихая отправка при сбое (с согласия) — отчёт сразу виден
   в управлении на сайте. Журнал приложения — в памяти (последние 400 строк, сюда же идёт console.*); ошибки программы
   (не сеть) — предложение один раз, согласились — уходят сами: одна и та же не чаще раза в 12 ч, не больше 4 в сутки. ---------- */
/* Журнал переживает перезапуск приложения (файл plog.txt, пишется раз в несколько секунд): раньше отчёт после перезапуска
   был почти пустым. Отчёт ушёл — журнал начинается заново: в следующем отчёте только новое, а не старые, уже исправленные беды. */
const PLOG_F = "plog.txt";
const PLOG = (() => { try { return String(fileGet(PLOG_F) || "").split("\n").filter(Boolean).slice(-400); } catch (e) { return []; } })();
let plogT = 0;
function plogSave(now) {
  clearTimeout(plogT); plogT = 0;
  const w = () => { try { fileSave(PLOG_F, PLOG.join("\n")); } catch (e) { } };
  if (now) w(); else plogT = setTimeout(w, 4000);
}
function plog(level, ...a) {
  const one = (x) => x instanceof Error ? (x.stack || x.message) : typeof x === "string" ? x : (() => { try { return JSON.stringify(x); } catch (e) { return String(x); } })();
  PLOG.push(`${new Date().toTimeString().slice(0, 8)} ${level} ${a.map(one).join(" ")}`.replace(/\n/g, " ⏎ ").slice(0, 2000));
  if (PLOG.length > 400) PLOG.splice(0, PLOG.length - 400);
  if (!plogT) plogSave();
}
plog("INFO", `— запуск приложения ${new Date().toLocaleDateString("ru-RU")} —`);
// приложение уходит в фон или закрывается — журнал сразу на диск, не дожидаясь отложенной записи
addEventListener("pagehide", () => plogSave(true));
document.addEventListener("visibilitychange", () => { if (document.hidden && plogT) plogSave(true); });
document.addEventListener("visibilitychange", () => { if (document.hidden) plogSave(true); });
for (const [lv, fn] of [["INFO", "log"], ["WARNING", "warn"], ["ERROR", "error"]]) {
  const orig = (console[fn] || console.log).bind(console);
  console[fn] = (...a) => { try { plog(lv, ...a); } catch (e) { } orig(...a); };
}
const NETLIKE = /network|timeout|timed out|сеть|интернет|облако ответило|failed to fetch|отменено|abort|unable to resolve|connect/i;
// «Script error. (:0)» — браузер прячет подробности чужого скрипта (расширения браузера, переводчики, блокировщики):
// не наша ошибка и не понять, где она (пакет 27.10: 51 такой «сбой» веб-версии с шести устройств) — не шлём
// «ResizeObserver loop limit exceeded» / «…completed with undelivered notifications» — предупреждение браузера, что подгонка
// размеров не уложилась в один кадр; ничего не ломается (пакет 04.11: 8 «сбоев» с одного телефона) — тоже не шлём
const JS_NOISE = /^ResizeObserver loop/i;
window.addEventListener("error", (e) => { if (e.message && !JS_NOISE.test(e.message) && !(/^Script error\.?$/i.test(e.message) && !e.filename)) problem("js:" + e.message, `${e.message} (${String(e.filename || "").split("/").pop()}:${e.lineno || 0})`, e.error); });
window.addEventListener("unhandledrejection", (e) => {
  const m = String((e.reason && e.reason.message) || e.reason || "");
  // «No Listener: tabs:outgoing.message.ready», «Extension context invalidated» — сообщения расширений браузера, не наши (пакет 28.10)
  if (m && !NETLIKE.test(m) && !/No Listener: tabs:|Extension context|chrome-extension:|moz-extension:|runtime\.lastError/i.test(m)) problem("promise:" + m.slice(0, 80), "Promise: " + m, e.reason);
});
/* Сбои связи с мозгом: копятся (pref net_inc) и, как только связь вернулась, уходят разработчику одним отчётом —
   если отчёты разрешены (S.report.auto), не чаще раза в 6 часов. Так видно, что это было: слабая связь или сервер. */
/* count — посчитать в пульс (net_fail, причина, сбой): один раз на вопрос — в итоговом обработчике. Повторы внутри вопроса
   (round1: 2, 5, 10 с) пишутся только в журнал сбоев (отчёт) — раньше один потерянный вопрос давал до 5 «сбоев»
   (пакет 20.10: «15 сбоев» за минуту, «13,5 % неудачных» — завышено). */
function netIncident(e, count = true) {
  let l = []; try { l = JSON.parse(prefGet("net_inc") || "[]") || []; } catch (x) { }
  const c = navigator.connection || {};
  l.push({ ts: Date.now(), host: String(e.url || "").replace(/^https?:\/\//, "").split(/[/?]/)[0], err: String(e.raw || e.message || "").slice(0, 200),
           online: navigator.onLine, type: c.type || c.effectiveType || "" });
  prefSet("net_inc", JSON.stringify(l.slice(-30)));
  if (count) { hCount("net_fail"); hWhy(l[l.length - 1].err); hProblem(`связь с мозгом: ${l[l.length - 1].err}`); }
  plog("WARNING", `связь с мозгом: ${l[l.length - 1].host} — ${l[l.length - 1].err} (${l[l.length - 1].type || "сеть ?"})`);
}
const STALE_CONN = /unexpected end of stream|connection reset|broken pipe|ECONNRESET/i;
/* Повтор внутри вопроса помог — последние n сбоев помечены «прошло само»: в отчёт разработчику они не идут
   (пакет 22.10, №189: отчёт «Связь с мозгом: 1 сбой» про вопрос, на который ответ пришёл через 5 с). */
function netHealed(n) {
  let l = []; try { l = JSON.parse(prefGet("net_inc") || "[]") || []; } catch (x) { }
  for (let i = Math.max(0, l.length - n); i < l.length; i++) l[i].ok = true;
  prefSet("net_inc", JSON.stringify(l));
}
/* Совет к ошибке связи: Wi‑Fi подключён, а имя сайта то находится, то нет — сбоит DNS этой сети (пакет 25.10, №257:
   «всё время теряет связь и долго думает» — «Unable to resolve host dewiar.pro (wifi)» вперемешку с обрывами). */
function netHint() {
  let l = []; try { l = JSON.parse(prefGet("net_inc") || "[]") || []; } catch (x) { }
  const rec = l.filter(x => Date.now() - x.ts < 3 * 60e3 && x.online !== false);
  if (!rec.some(x => /Unable to resolve host|No address associated|UnknownHost/i.test(x.err || "") && !HOME_URL.test("http://" + x.host))) return "";
  return /wifi/i.test(rec.map(x => x.type).join(" "))
    ? ". Wi‑Fi подключён, но телефон то находит сервер, то нет — так бывает, когда у сети сбоит DNS или провайдер мешает связи с dewiar.pro. Помогает: в настройках Android найдите поиском «Частный DNS» и впишите dns.google; не помогло — мобильный интернет или VPN"
    : ". Телефон то находит сервер, то нет — похоже на сбой DNS или помехи у оператора. Помогает: в настройках Android найдите поиском «Частный DNS» и впишите dns.google; не помогло — другая сеть или VPN";
}
function netRecovered() {
  let l = []; try { l = JSON.parse(prefGet("net_inc") || "[]") || []; } catch (x) { }
  // прошло само при повторе, телефон был без сети или имя сайта не находилось (нет интернета) — это не сбой программы
  // (пакет 23.10, №208: «7 сбоев: Unable to resolve host … [none, офлайн]»)
  const own = (x) => x.ok || x.online === false || x.type === "none" || /Unable to resolve host|No address associated/i.test(x.err || "");
  if (l.length && l.every(own)) { prefSet("net_inc", "[]"); return; }
  l = l.filter(x => !own(x));
  if (!l.length || !(S.report || {}).auto) return;
  if (Date.now() - (+prefGet("net_rep") || 0) < 6 * 36e5) return;
  prefSet("net_rep", String(Date.now())); prefSet("net_inc", "[]");
  const hosts = [...new Set(l.map(x => x.host))].join(", ");
  reportSend("", true, `Связь с мозгом: ${l.length} сбоев (${hosts}) — ` + l.slice(-3).map(x => `${new Date(x.ts).toTimeString().slice(0, 5)} ${x.err.slice(0, 60)} [${x.type || "?"}${x.online ? "" : ", офлайн"}]`).join("; "))
    .catch(() => {});
}
function problem(sig, summary, err) {
  plog("ERROR", summary, err && err.stack ? err.stack : "");
  hProblem(summary);
  const auto = (S.report || {}).auto;
  if (auto === false) return;
  if (auto == null) { if (!problem.offered) { problem.offered = true; setTimeout(() => reportOffer(summary), 300); } return; }
  sig = String(sig).replace(/\d+/g, "#").slice(0, 160);
  let sent = {}; try { sent = JSON.parse(prefGet("rep_sent") || "{}") || {}; } catch (e) { }
  const now = Date.now(); for (const k in sent) if (now - sent[k] > 864e5) delete sent[k];
  if (now - (sent[sig] || 0) < 12 * 36e5 || Object.keys(sent).length >= 4) return;
  sent[sig] = now; prefSet("rep_sent", JSON.stringify(sent));
  problem.pending = (problem.pending || []).concat(summary);
  if (problem.pending.length > 1) return;                                // уже ждём — уйдёт одним отчётом
  setTimeout(() => { const sm = problem.pending.join(" | ").slice(0, 500); problem.pending = [];
    reportSend("", true, sm).catch(e => console.log("отчёт о сбое не ушёл: " + e.message)); }, window.DEWIAR_REPORT_WAIT || 15000);
}
function reportOffer(summary) {
  showCard(`<div class="repask"><b>Что-то пошло не так.</b> Отправлять разработчику отчёт о таких сбоях самому? В нём — журнал работы
    приложения и настройки без ключей и паролей. Так ошибки исправят быстрее.${summary ? `<small>${esc(String(summary).slice(0, 140))}</small>` : ""}
    <div class="row2"><button class="btn p" id="rq-yes">Отправлять</button><button class="btn" id="rq-no">Не надо</button></div></div>`);
  $("#rq-yes").onclick = () => { S.report = { auto: true }; saveS(); showCard(""); toast("Хорошо — при сбое отчёт уйдёт сам"); };
  $("#rq-no").onclick = () => { S.report = { auto: false }; saveS(); showCard(""); };
}
/* 1.0.29: почта и телефоны в отчёте — n***@домен и +*** ** 67 (Политика конфиденциальности); строки разговора в журнале */
const TALK_LINE_RX = /[❓📝⚡💬🔧📎🗣]|👥 \S+ передаёт вопрос/u;
function maskPersonal(t) {
  // без «взгляда назад» (старый Safari веб-версии не разбирает весь файл): символ перед — своей группой и обратно в замену
  return String(t || "").replace(/(^|[^\w.+-])([A-Za-z0-9])[A-Za-z0-9._%+-]*@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,})/g, "$1$2***@$3")
    .replace(/(^|[^\w.+\/:-])(\+\d[\d ()-]{8,18}\d|\(?\d{1,4}\)?(?:[ -]\(?\d{2,4}\)?){2,5})(?![\w.:\/])/g,
      (m, pre, num) => { const d = num.replace(/\D/g, ""); return d.length >= 10 && d.length <= 15 ? pre + "+*** ** " + d.slice(-2) : m; });
}
async function reportSend(note, auto, summary, extra) {
  let info = {}; try { info = JSON.parse(D.info() || "{}"); } catch (e) { }
  // в отчёт не попадает секретное: ключи, токены, пароли, прокси (в нём бывает логин) — звёздочками; ниже то же для текста журнала
  // номера установки (inst — по нему сайт возвращает прежний ключ, 0.82.1) и пульса (dev) — тоже: по ним узнают это устройство
  const mask = (o) => JSON.parse(JSON.stringify(o, (k, v) => (/key|token|pass|secret|auth|cookie|proxy/i.test(k) || /^(inst|dev)$/.test(k)) && v && typeof v !== "object" ? "***" : v));
  const st = Object.assign({}, S, { memory: `(записей: ${(S.memory || []).length})` });
  // пакет 04.11 (№529): «Дома по Wi-Fi» — ключ шифрования (k), токен (t) и номер связки (h) уходили в отчёт как есть
  if (S.sync && S.sync.home) st.sync = Object.assign({}, S.sync, { home: Object.assign({}, S.sync.home, { k: "***", t: "***", h: "***" }) });
  const errs = PLOG.filter(l => /^\S+ (ERROR|WARNING) /.test(l));
  // 1.0.29 (Политика конфиденциальности): «без фраз разговора» — строки с текстом человека и ответами не уходят
  const plog = extra && extra.talk === false ? PLOG.filter(l => !TALK_LINE_RX.test(l)) : PLOG;
  note = String(note || "").trim().slice(0, 2000);
  let text = [`Dewiar (телефон) ${info.version || ""} — отчёт ${new Date().toLocaleString("ru-RU")}`,
    `Android ${info.android || ""}; ${info.device || ""}; распознаватель: ${info.recognizer}; голос: ${info.tts}`,
    `TZ: ${(() => { try { return Intl.DateTimeFormat().resolvedOptions().timeZone; } catch (e) { return "?"; } })()} (UTC${(() => { const o = -new Date().getTimezoneOffset(); return (o >= 0 ? "+" : "-") + String(Math.floor(Math.abs(o) / 60)).padStart(2, "0") + String(Math.abs(o) % 60).padStart(2, "0"); })()}); UTC ${new Date().toISOString().slice(11, 16)}`, "",
    ...(note ? ["== Со слов человека", note, ""] : []),
    "== Состояние", JSON.stringify({ state, online: navigator.onLine, sync: syncStatus, cloud: cloudInfo, alarms: remHealth() || undefined, audio: audioInfo() }, null, 1), "",
    "== Настройки (без ключей)", JSON.stringify(mask(st), null, 1), "",
    ...(info.crash ? ["== Последнее падение приложения", info.crash, ""] : []),
    ...(errs.length ? ["== Ошибки (последние)", ...errs.slice(-40), ""] : []),
    "== Журнал (последние строки)", ...plog.slice(auto ? -200 : -400)].join("\n");
  text = text.replace(/(Bearer\s+)[\w.-]+/g, "$1***").replace(/\bdw-[a-z0-9]{4,}(?:-[a-z0-9]{2,})+/gi, "dw-***")
    // пакет 25.10, №256: токен умного дома целиком в журнале — JWT, ключи API, «токен: <длинное>» → ***
    .replace(/\beyJ[\w-]{6,}\.[\w-]{6,}\.[\w-]{6,}/g, "eyJ***").replace(/\b(sk-(?:ant-|proj-)?|ghp_|github_pat_|glpat-|hf_|AIza)[\w-]{12,}/g, "$1***")
    .replace(/\bbot\d{5,}:[\w-]{20,}/g, "bot***")
    .replace(/((?:токен\S*|token|api[_ -]?key|ключ\S*|secret|секрет\S*)(?:\s+api)?["']?\s*[:=]?\s*["'«]?)(?=[\w.+\/=-]*\d)(?=[\w.+\/=-]*[A-Za-z])[\w.+\/=-]{20,}/gi, "$1***");
  text = maskPersonal(text);                                 // почта и телефоны (как core/engine_base.mask_personal)
  // принимает облако (cloud.php ?p=/report): с аккаунтом или ключом — от их имени, без них — анонимно на общий адрес
  const c = syncCred(), base = (c ? c.base : CLOUD_URL).split("?")[0];
  const headers = { "Content-Type": "application/json" }; if (c) headers.Authorization = "Bearer " + c.token;
  const errLines = errs.filter(l => / ERROR /.test(l)).map(l => l.replace(/^\S+ ERROR /, ""));
  const body = { kind: auto ? "auto" : "manual", app: "phone", version: info.version || "", os: "Android " + (info.android || "") + webviewVer(), device: info.device || "",
    summary: String(summary || errLines.slice(-3).join("; ") || "").slice(0, 500), note, text };
  if (extra && extra.shot) body.shot = extra.shot;                 // жалоба: снимок экрана и подпись автора
  if (extra && extra.who) body.who = extra.who;
  let r; try { r = await http("POST", base + "?p=/report", { headers, body, timeout: extra && extra.shot ? 60000 : 40000 }); }
  catch (e) { throw new Error("не удалось отправить отчёт: " + netErr(e.message || e)); }
  let d = {}; try { d = JSON.parse(r.body || "{}"); } catch (e) { }
  if (r.status >= 400 || !d.ok) throw new Error("отчёт не принят: " + ((d.error && d.error.message) || ("сервер ответил " + r.status)));
  PLOG.length = 0;                                   // всё это уже у разработчика — следующий отчёт только о новом
  console.log(`🧾 Отчёт №${d.id} отправлен разработчику (${auto ? "сам, при сбое" : "кнопкой"}) — журнал начат заново`);
  plogSave(true);
  d.base = base;
  return d;
}
// приложение падало (Java записала причину), а отчёты разрешены — одно падение уходит один раз
setTimeout(() => {
  try {
    const i = JSON.parse(D.info() || "{}");
    if (!i.crash || !(S.report || {}).auto) return;
    const h = syncHash(i.crash);
    if (prefGet("rep_crash") === h) return;
    prefSet("rep_crash", h);
    reportSend("", true, "Падение приложения: " + String(i.crash).split("\n")[0]).catch(e => console.log("отчёт о падении не ушёл: " + e.message));
  } catch (e) { }
}, 20000);
