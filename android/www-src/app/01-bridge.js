//@ Телефон и веб-версия, часть 01: начало: помощники ($, esc, LBRX) и мост к телефону window.Dewiar (в браузере — заглушка, в веб-версии — webbridge.js).
//@ Собирается в android/assets/www/app.js (tools/app_join.py) — порядок частей = порядок исполнения; шапка «//@» в app.js не попадает.
/* Dewiar для Android — интерфейс и «мозг» на телефоне (страница index.html в WebView MainActivity).
   Нативная часть (Bridge.java и соседи) даёт слух, голос, сеть без CORS, будильники и руки телефона через window.Dewiar (D);
   ответы долгих дел приходят событиями в N.ev({type, ...}). Думает модель (свой сервер, облако по ключу или Dewiar Облако —
   server/dwrapp/cloud.php) с инструментами телефона.
   Разделы «---------- … ----------» по порядку: мост, радио, настройки, отчёты, разговор, персонажи, слух, голос, мозг,
   время словами, быстрые команды, инструменты, камера, интернет, заметки и деньги, умный дом, листы, синхронизация
   (общая с core/sync.py и cloud.php ?p=/sync), облако, аккаунт, мессенджеры, запуск.
   В браузере вместо D — заглушка с теми же методами: на ней страницу проверяют тесты tests/android_*. */
"use strict";
if (typeof window.t !== "function") window.t = (k) => k;   // словари языков (i18n.js) не подключены — например, в проверках: ключ вместо текста, без ошибки
const $ = (s, el = document) => el.querySelector(s), $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
/* Старый Safari (iPhone и Mac до 16.4) не знает «взгляда назад» (?<= ?<!) в регулярных выражениях: литерал с ним роняет
   весь файл при разборе (жалоба 28.10: «веб-версия не работает совсем, не отвечает»). Такие выражения — только через LBRX:
   точное выражение, а без поддержки — замена: «перед этим не символ C» (?<!C) → (?:^|(?!C)[\s\S]), (?<=C) → (?:(?=C)[\s\S])
   (для .test и групп — то же самое; совпадение лишь начинается на символ раньше), длинный «взгляд назад» — убран (чуть
   шире). Литералов с ним в веб-версии нет — следит tests/web_oldsafari1028_test.py. */
const LB_ONE = "\\[(?:[^\\]\\\\]|\\\\.)*\\]|\\\\.|[^()\\\\[|]";
const LBRX = (src, fl) => {
  try { return new RegExp(src, fl); } catch (e) {
    return new RegExp(String(src).replace(new RegExp("\\(\\?<!(" + LB_ONE + ")\\)", "g"), "(?:^|(?!$1)[\\s\\S])").replace(new RegExp("\\(\\?<=(" + LB_ONE + ")\\)", "g"), "(?:(?=$1)[\\s\\S])")
      .replace(/\(\?<[=!](?:[^()\\[]|\\.|\[(?:[^\]\\]|\\.)*\]|\((?:[^()\\]|\\.)*\))*\)/g, ""), fl);
  }
};
const MIC = "android.permission.RECORD_AUDIO", CONTACTS = "android.permission.READ_CONTACTS",
      CALLP = "android.permission.CALL_PHONE", NOTIF = "android.permission.POST_NOTIFICATIONS";

/* ---------- мост к телефону: window.Dewiar — методы Bridge.java (в браузере для проверки — заглушка) ----------
   Новый метод моста добавляй в обе стороны: в Bridge.java и в заглушку ниже. Ответы — строки (JSON строкой). */
/* Веб-версия (dewiar.pro/dwrapp/web/, android/web/webbridge.js) получает эту же заглушку и заменяет её методы
   возможностями браузера (window.DewiarWeb): D.web — правда, D.mock — нет. */
const D = window.Dewiar || (window.DewiarWeb || (s => s))((() => {
  const store = {}, files = {}, alarms = [];
  const ev = (o) => setTimeout(() => N.ev(JSON.stringify(o)), 0);
  return {
    mock: true, info: () => JSON.stringify({ version: "0.1.0-web", sdk: 0, recognizer: false, tts: false, crash: "" }),
    clearCrash() {}, takeIntent: () => "", pref: (k) => (k in store ? store[k] : (localStorage.getItem("p_" + k) || "")),
    setPref: (k, v) => { store[k] = v; try { localStorage.setItem("p_" + k, v); } catch (e) {} },
    toast: (t) => console.log("toast", t), vibrate() {}, share() {}, keepScreen() {}, immersive() {}, has: () => true, perm: (n) => ev({ type: "perm", name: n, granted: true }),
    openSettings: () => false, notify() {}, setFace(id, name, color, png) { (window._faces = window._faces || {})[id] = { name, color, png: png.length }; },
    http(id, method, url, headers, body, stream) {
      fetch(url, { method, headers: JSON.parse(headers || "{}"), body: body || undefined }).then(async r => {
        if (stream && r.ok && r.body) {
          const rd = r.body.getReader(), dec = new TextDecoder();
          for (;;) { const { value, done } = await rd.read(); if (done) break; ev({ type: "http_chunk", id, text: dec.decode(value) }); }
          ev({ type: "http_done", id, status: r.status, body: "" });
        } else ev({ type: "http_done", id, status: r.status, body: await r.text(), url: r.url });
      }).catch(e => ev({ type: "http_error", id, error: String(e) }));
    },
    snapshot: () => window._snap || "",
    abort() {}, setProxy(spec, hosts) { window._proxy = { spec, hosts }; return ""; }, recognizer: () => false, listen(g) { ev({ type: "stt_error", g, code: 9, msg: "нет микрофона в браузере" }); },
    listenServer(g) { this.listen(g); }, stopListen() {}, cancelListen() {}, pauseExtra(ms) { window._pause = ms; },
    speak(id) { ev({ type: "tts_start", id }); setTimeout(() => ev({ type: "tts_done", id }), 300); }, speakRemote(id) { this.speak(id); },
    stopSpeak() {}, voices: () => "[]", ttsReady: () => false,
    alarmSet(j) { const x = JSON.parse(j); x.id = x.id || uid("a"); const i = alarms.findIndex(a => a.id === x.id); if (i >= 0) alarms[i] = x; else alarms.push(x); return JSON.stringify(x); },
    alarmCancel(id) { const i = alarms.findIndex(a => a.id === id); if (i >= 0) alarms.splice(i, 1); return i >= 0; },
    alarms: () => JSON.stringify(alarms), alarmHistory: () => "[]", exactAlarms: () => true,
    alarmHealth: () => JSON.stringify(window._remHealth || { exact: true, fullscreen: true, notify: true, battery: true, sdk: 34, maker: "", mode: "clock", late: [] }),
    _w: { on: true, placed: 0, pin: true, look: "glass" }, widgetState() { return JSON.stringify(this._w); }, widgetSet(on) { this._w.on = !!on; },
    widgetPin() { this._w.placed++; return true; }, home() { window._home = (window._home || 0) + 1; },
    _cal: [], calEvents(j) { const q = JSON.parse(j); return JSON.stringify({ events: this._cal.filter(e => e.end > q.from && e.begin < q.to).sort((a, b) => a.begin - b.begin) }); },
    calAdd(j) { const e = JSON.parse(j); e.id = this._cal.length + 1; e.calendar = "Мой календарь"; this._cal.push(e); return JSON.stringify({ id: e.id, calendar: e.calendar }); },
    calOpenInsert(j) { window._calInsert = JSON.parse(j); return true; },
    contact: () => "", call: (n) => { (window._calls = window._calls || []).push(n); return true; }, sms: () => true, openApp: (n) => (/телеграм|telegram/i.test(n) ? "Telegram" : ""), apps: () => "[]",
    openUrl: () => true, torch: () => true, volume: (op, v) => { if (op !== "get") (window._vol = window._vol || []).push([op, v]); return 50; }, battery: () => JSON.stringify({ percent: 80, charging: false }),
    files: (n) => (n in files ? files[n] : (localStorage.getItem("f_" + n) || "")),
    saveFile: (n, t) => { files[n] = t; try { localStorage.setItem("f_" + n, t); } catch (e) {} return true; },
    saveDownload: (n, m, t) => { (window._downloads = window._downloads || []).push([n, t]); return "Загрузки/Dewiar/" + n; },
    copy: (t) => { window._copied = t; return true; }, secureScreen: (on) => { window._secure = !!on; }, bars: (c, l) => { window._bars = [c, l]; },
    closeWatch: (j) => { window._closeWatch = j; },
    locate: (age) => { window._locAsked = (window._locAsked || 0) + 1; const l = window._loc === undefined ? { lat: 53.9006, lon: 27.559, acc: 20, ts: Date.now() } : window._loc;
      ev(Object.assign({ type: "loc" }, l || { error: "местоположение выключено в телефоне" })); }, locSettings: () => { window._locSet = 1; return true; },
    closeLive: (on) => { window._closeLive = on; }, batteryOk: () => true, askBattery() {}, srPlan: (j) => { window._srPlan = j; window._srPlans = (window._srPlans || 0) + 1; },
    deviceClass: () => JSON.stringify(window._dev || { ram_mb: 8192, low_ram: false, cores: 8, power_save: false }),
    updateGet(url, sha) { window._upd = [url, sha]; setTimeout(() => { ev({ type: "upd_progress", pct: 50 }); ev({ type: "upd_ready", size: 1 }); }, 50); },
    updateInstall: () => (window._updPerm ? "perm" : (window._updInst = (window._updInst || 0) + 1, "ok")), updateCanInstall: () => !window._updPerm,
    updateReady: () => true, openDownloads: () => { window._dls = (window._dls || 0) + 1; return true; },
    appSize: () => JSON.stringify({ cache: 48e6, data: 12e6 }), clearOwnCache: () => (window._cleared = (window._cleared || 0) + 1, 47e6), openStorage: () => { window._storage = (window._storage || 0) + 1; return true; },
    alarmSound: () => JSON.stringify({ id: store.alarm_sound || "signature", custom: store.alarm_custom_name || "", soft: !!store.rem_soft }),
    alarmSoundSoft: (on) => (store.rem_soft = !!on),
    alarmSoundSet: (id) => { if (id === "custom" && !store.alarm_custom_name) return false; store.alarm_sound = id; return true; },
    alarmSoundTry: (id) => { const on = window._trying !== id; window._trying = on ? id : ""; return on; },
    alarmSoundCustom: (b64, name) => { if (!b64) return "пустой файл"; store.alarm_custom_name = name; store.alarm_sound = "custom"; return ""; },
    saveDownloadB64: (n, m, b) => { (window._downloads = window._downloads || []).push([n, new TextDecoder().decode(Uint8Array.from(atob(b), c => c.charCodeAt(0)))]); return "Загрузки/Dewiar/" + n; },
    shareTo: (pkg, t) => { window._shared = { pkg, text: t }; return true; },
    _radio: { state: "stopped", name: "", error: "", log: [] },
    radioPlay(url, name) { const r = this._radio; r.log.push("play " + name); Object.assign(r, { state: "preparing", name, error: "", url }); ev({ type: "radio", state: "preparing", name, error: "" });
      setTimeout(() => { if (r.url !== url || /slow/.test(url)) return; const bad = /bad|dead/.test(url); Object.assign(r, { state: bad ? "error" : "playing", error: bad ? "станция не отвечает (сеть)" : "" });
        ev({ type: "radio", state: r.state, name, error: r.error });
        if (/silent/.test(url)) setTimeout(() => { if (r.url !== url) return; Object.assign(r, { state: "error", error: "станция молчит — поток не идёт" }); ev({ type: "radio", state: "error", name, error: r.error }); }, 300);
      }, 60); },
    radioPause() { const r = this._radio; r.log.push("pause"); if (r.state === "playing") { r.state = "paused"; ev({ type: "radio", state: "paused", name: r.name, error: "", by: "user" }); } },
    radioResume() { const r = this._radio; r.log.push("resume"); if (r.state === "paused") { r.state = "playing"; ev({ type: "radio", state: "playing", name: r.name, error: "" }); } },
    _focusLoss() { const r = this._radio; if (r.state === "playing") { r.state = "paused"; ev({ type: "radio", state: "paused", name: r.name, error: "", by: "focus" }); } },
    radioStop() { const r = this._radio; r.log.push("stop"); r.url = ""; r.state = "stopped"; ev({ type: "radio", state: "stopped", name: r.name, error: "" }); },
    radioDuck(on) { this._radio.duck = on; }, radioVolume(v) { this._radio.volume = v; },
    mediaKey(act) { (window._media = window._media || []).push(act); return JSON.stringify({ sent: true, active: !!window._musicOn }); }, musicActive: () => !!window._musicOn,
    radioState() { const r = this._radio; return JSON.stringify({ state: r.state, name: r.name, error: r.error }); },
    // руки в других приложениях (Hands.java): в браузере выключены — проверки подменяют эти методы своими
    handsState: () => "", handsScreen: () => "OFF", handsTap: () => "OFF", handsTapText: () => "OFF", handsType: () => "OFF",
    handsScroll: () => "OFF", handsNav: () => "OFF", toFront() {},
  };
})());
/* Песочница экзамена (exam.js): пока она включена, настройки и файлы пишутся в память, а не на телефон; после экзамена
   приложение перезагружается и видит всё как было. Все записи и чтения настроек и файлов — только через эти четыре. */
let SANDBOX = null;
function prefSet(k, v) { if (SANDBOX) { SANDBOX.prefs[k] = v; return; } D.setPref(k, v); }
function prefGet(k) { return SANDBOX && k in SANDBOX.prefs ? SANDBOX.prefs[k] : D.pref(k); }
function fileSave(n, t) { if (SANDBOX) { SANDBOX.files[n] = t; return true; } return D.saveFile(n, t); }
function fileGet(n) { return SANDBOX && n in SANDBOX.files ? SANDBOX.files[n] : D.files(n); }
function devTorch(on) { if (SANDBOX) { SANDBOX.dev.push({ name: "flashlight", on: !!on, argsObj: { on: !!on }, t: Date.now() }); return true; } return D.torch(on); }
/* идея №170: медиа-клавиша плееру другого приложения (Яндекс Музыка, Spotify…); в экзамене — только записать */
function devMedia(act) { if (SANDBOX) { SANDBOX.dev.push({ name: "media_control", act, t: Date.now() }); return { sent: true, active: true }; }
  try { return JSON.parse(D.mediaKey(act) || "{}"); } catch (e) { return { sent: false }; } }
function devMusicActive() { if (SANDBOX) return false; try { return !!(D.musicActive && D.musicActive()); } catch (e) { return false; } }
function devVolume(op, v) { if (SANDBOX) { SANDBOX.dev.push({ name: "set_volume", op, v, t: Date.now() }); return 40; } return D.volume(op, v); }

if (!window.Dewiar) window.Dewiar = D;          // кнопки в разметке вызывают Dewiar.* и в браузере

const N = window.N = {
  handlers: {},
  on(type, fn) { (this.handlers[type] = this.handlers[type] || []).push(fn); },
  ev(raw) { let e; try { e = typeof raw === "string" ? JSON.parse(raw) : raw; } catch (x) { return; } (this.handlers[e.type] || []).forEach(f => { try { f(e); } catch (x) { console.error(x); } }); },
  back() { if (gameOn()) { gameClose(); return true; } if (imgViewClose()) return true;
    const pv = $("#picview"); if (pv && pv.classList.contains("on")) { pv.classList.remove("on"); return true; }
    const sn = $("#sh-note.on.nte"); if (sn && noteCur) { noteMode = "view"; notePend = []; renderNote(); return true; }   // правка → назад к чтению
    const s = $(".sheet.on"); if (s) { closeSheets(); return true; } if (state !== "idle") { interrupt(); return true; } return false; },
};
/* Приложение свёрнуто (MainActivity.onPause → событие «pause»): WebView не всегда ставит document.hidden, и фоновые опросы
   (синхронизация, радар, объявления…) шли раз в 30–60 с и в кармане — Huawei: «частое обновление данных в фоновом
   режиме» (владелец 17.11). Опросы по таймеру смотрят сюда; сообщения и звонки в фоне — служба CloseLive. */
let appPaused = false;
N.on("pause", () => { appPaused = true; });
N.on("resume", () => { appPaused = false; });
const appAway = () => document.hidden || appPaused;

