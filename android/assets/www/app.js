/* Dewiar для Android — интерфейс и «мозг» на телефоне (страница index.html в WebView MainActivity).
   Нативная часть (Bridge.java и соседи) даёт слух, голос, сеть без CORS, будильники и руки телефона через window.Dewiar (D);
   ответы долгих дел приходят событиями в N.ev({type, ...}). Думает модель (свой сервер, облако по ключу или Dewiar Облако —
   server/dwrapp/cloud.php) с инструментами телефона.
   Разделы «---------- … ----------» по порядку: мост, радио, настройки, отчёты, разговор, персонажи, слух, голос, мозг,
   время словами, быстрые команды, инструменты, камера, интернет, заметки и деньги, умный дом, листы, синхронизация
   (общая с core/sync.py и cloud.php ?p=/sync), облако, аккаунт, мессенджеры, запуск.
   В браузере вместо D — заглушка с теми же методами: на ней страницу проверяют тесты tests/android_*. */
"use strict";
const $ = (s, el = document) => el.querySelector(s), $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
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
    toast: (t) => console.log("toast", t), vibrate() {}, share() {}, keepScreen() {}, has: () => true, perm: (n) => ev({ type: "perm", name: n, granted: true }),
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
    alarmSet(j) { const x = JSON.parse(j); x.id = x.id || "a" + Date.now(); const i = alarms.findIndex(a => a.id === x.id); if (i >= 0) alarms[i] = x; else alarms.push(x); return JSON.stringify(x); },
    alarmCancel(id) { const i = alarms.findIndex(a => a.id === id); if (i >= 0) alarms.splice(i, 1); return i >= 0; },
    alarms: () => JSON.stringify(alarms), alarmHistory: () => "[]", exactAlarms: () => true,
    _w: { on: true, placed: 0, pin: true }, widgetState() { return JSON.stringify(this._w); }, widgetSet(on) { this._w.on = !!on; },
    widgetPin() { this._w.placed++; return true; }, home() { window._home = (window._home || 0) + 1; },
    _cal: [], calEvents(j) { const q = JSON.parse(j); return JSON.stringify({ events: this._cal.filter(e => e.end > q.from && e.begin < q.to).sort((a, b) => a.begin - b.begin) }); },
    calAdd(j) { const e = JSON.parse(j); e.id = this._cal.length + 1; e.calendar = "Мой календарь"; this._cal.push(e); return JSON.stringify({ id: e.id, calendar: e.calendar }); },
    calOpenInsert(j) { window._calInsert = JSON.parse(j); return true; },
    contact: () => "", call: (n) => { (window._calls = window._calls || []).push(n); return true; }, sms: () => true, openApp: (n) => (/телеграм|telegram/i.test(n) ? "Telegram" : ""), apps: () => "[]",
    openUrl: () => true, torch: () => true, volume: (op, v) => { if (op !== "get") (window._vol = window._vol || []).push([op, v]); return 50; }, battery: () => JSON.stringify({ percent: 80, charging: false }),
    files: (n) => (n in files ? files[n] : (localStorage.getItem("f_" + n) || "")),
    saveFile: (n, t) => { files[n] = t; try { localStorage.setItem("f_" + n, t); } catch (e) {} return true; },
    saveDownload: (n, m, t) => { (window._downloads = window._downloads || []).push([n, t]); return "Загрузки/Dewiar/" + n; },
    copy: (t) => { window._copied = t; return true; }, bars: (c, l) => { window._bars = [c, l]; },
    closeWatch: (j) => { window._closeWatch = j; },
    locate: (age) => { window._locAsked = (window._locAsked || 0) + 1; const l = window._loc === undefined ? { lat: 53.9006, lon: 27.559, acc: 20, ts: Date.now() } : window._loc;
      ev(Object.assign({ type: "loc" }, l || { error: "местоположение выключено в телефоне" })); }, locSettings: () => { window._locSet = 1; return true; },
    closeLive: (on) => { window._closeLive = on; }, batteryOk: () => true, askBattery() {},
    deviceClass: () => JSON.stringify(window._dev || { ram_mb: 8192, low_ram: false, cores: 8, power_save: false }),
    updateGet(url, sha) { window._upd = [url, sha]; setTimeout(() => { ev({ type: "upd_progress", pct: 50 }); ev({ type: "upd_ready", size: 1 }); }, 50); },
    updateInstall: () => (window._updPerm ? "perm" : (window._updInst = (window._updInst || 0) + 1, "ok")), updateCanInstall: () => !window._updPerm,
    updateReady: () => true, openDownloads: () => { window._dls = (window._dls || 0) + 1; return true; },
    appSize: () => JSON.stringify({ cache: 48e6, data: 12e6 }), clearOwnCache: () => (window._cleared = (window._cleared || 0) + 1, 47e6), openStorage: () => { window._storage = (window._storage || 0) + 1; return true; },
    alarmSound: () => JSON.stringify({ id: store.alarm_sound || "signature", custom: store.alarm_custom_name || "" }),
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
function devVolume(op, v) { if (SANDBOX) { SANDBOX.dev.push({ name: "set_volume", op, v, t: Date.now() }); return 40; } return D.volume(op, v); }

if (!window.Dewiar) window.Dewiar = D;          // кнопки в разметке вызывают Dewiar.* и в браузере

const N = window.N = {
  handlers: {},
  on(type, fn) { (this.handlers[type] = this.handlers[type] || []).push(fn); },
  ev(raw) { let e; try { e = typeof raw === "string" ? JSON.parse(raw) : raw; } catch (x) { return; } (this.handlers[e.type] || []).forEach(f => { try { f(e); } catch (x) { console.error(x); } }); },
  back() { if (gameOn()) { gameClose(); return true; } const s = $(".sheet.on"); if (s) { closeSheets(); return true; } if (state !== "idle") { interrupt(); return true; } return false; },
};

/* ---------- радио: играет внутри приложения (как на компьютере), а не на сайтах и в чужих приложениях ----------
   Свой список станций — тот же, что у компьютера (data/radio.json; свежий — с dewiar.pro раз в 6 часов);
   не нашли в нём — открытый каталог radio-browser.info. «Стоп», «пауза», «дальше», «продолжи» — голосом и кнопками. */
const radio = (() => {
  const SITE_LIST = "https://dewiar.pro/dwrapp/radio.json";
  const API = ["https://de1.api.radio-browser.info", "https://de2.api.radio-browser.info", "https://all.api.radio-browser.info"];
  const SYN = { "спокойн": "релакс спокойно", "расслаб": "релакс", "отдох": "релакс", "чилаут": "релакс", "чил": "релакс", "тих": "релакс спокойно",
    "сон": "релакс", "медитац": "релакс", "фонов": "релакс джаз", "танц": "танцевальная клубная", "клуб": "клубная", "бодр": "энерджи танцевальная",
    "энерг": "энерджи", "драйв": "рок энерджи", "весел": "поп хиты", "попс": "поп", "хит": "хиты поп", "русск": "русское русские", "наш": "русское русские",
    "отечеств": "русское русские", "стар": "ретро", "ретро": "ретро", "80": "ретро 80", "90": "ретро 90", "восьмидесят": "ретро 80", "девяност": "ретро 90",
    "диско": "ретро", "советск": "ссср ретро", "ссср": "ссср", "хаус": "дип хаус", "электрон": "клубная дип", "дип": "дип", "ремикс": "ремиксы",
    "новост": "новости", "поговор": "разговорное", "разговор": "разговорное", "джаз": "джаз",
    "легк": "релакс спокойно поп", "приятн": "релакс спокойно", "вечер": "релакс джаз спокойно", "медлен": "релакс спокойно",
    "романт": "релакс джаз", "инструмент": "джаз эмбиент классика", "утр": "поп хиты", "бодрящ": "энерджи танцевальная", "блюз": "джаз", "рок": "рок",
    "альтернатив": "альтернатива", "метал": "рок", "поп": "поп", "класси": "классика", "шансон": "шансон" };
  const FILLER = new Set(("мне нам пожалуйста немного немножко какую какую-нибудь какую-то что-нибудь что-то нибудь музыку музыка музыки музычку песни песню " +
    "радио радиостанцию радиостанция станцию станция волну послушать для под в на стиле жанре жанр из типа вроде что бы лучше а и тогда можно давай хочу включи " +
    "поставь запусти эфир онлайн").split(" "));
  const GENRE_EN = { "электрон": "electronic", "техно": "techno", "хаус": "house", "транс": "trance", "рок": "rock", "джаз": "jazz", "класси": "classical",
    "поп": "pop", "хип": "hiphop", "рэп": "rap", "лаунж": "lounge", "чилаут": "chillout", "чил": "chillout", "эмбиент": "ambient", "амбиент": "ambient",
    "метал": "metal", "блюз": "blues", "кантри": "country", "регги": "reggae", "диско": "disco", "шансон": "chanson", "лофай": "lofi", "лоуфай": "lofi",
    "фолк": "folk", "соул": "soul", "фанк": "funk", "релакс": "relax", "спокойн": "relax", "медитац": "meditation", "новост": "news", "детск": "children" };
  const words = (t) => (String(t || "").toLowerCase().replace(/ё/g, "е").match(/[a-zа-я0-9-]+/g) || []);
  const stem = (w) => w.length > 4 ? w.slice(0, Math.max(3, w.length - 2)) : w;
  let st = { state: "stopped", name: "", error: "", by: "" }, cur = null, found = [], waiters = [], played = [], starting = false, focusAt = 0, autoTried = {};
  let opSeq = 0, usedAt = 0;                       // каждая команда (включи, дальше, стоп) — своя; прежняя, ещё перебирающая станции, сдаётся
  const bad = {};                                  // станция не заиграла — 20 минут пробуем её последней
  const isBad = (s) => bad[s.url] && Date.now() - bad[s.url] < 20 * 60e3;
  const goodFirst = (xs) => xs.filter(x => !isBad(x)).concat(xs.filter(isBad));
  function norm(d) {
    const raw = Array.isArray(d) ? d : (d && d.stations) || [];
    return raw.filter(x => x && x.name && x.url).map(x => ({ name: String(x.name).trim(), url: String(x.url).trim(), tags: String(x.tags || "").toLowerCase(),
      aliases: (Array.isArray(x.aliases) ? x.aliases : x.aliases ? [x.aliases] : []).map(a => String(a).toLowerCase().replace(/ё/g, "е")) }));
  }
  function list() {
    let l = []; try { l = norm(JSON.parse(prefGet("radio_list") || "null")); } catch (e) { l = []; }
    return l.length ? l : norm(window.RADIO_LIST);
  }
  async function refresh() {                    // свежий список с сайта (его правит администратор) — раз в 6 часов
    if (Date.now() - (+prefGet("radio_at") || 0) < 6 * 3600e3) return;
    prefSet("radio_at", String(Date.now()));
    try { const r = await http("GET", SITE_LIST, { timeout: 15000 }); if (r.status === 200 && norm(JSON.parse(r.body)).length) prefSet("radio_list", r.body); } catch (e) { /* играем по встроенному */ }
  }
  function match(query) {
    const all = list();
    if (query === "*") return all.slice().sort(() => Math.random() - .5);
    const q = words(query).join(" ");
    if (!q) return [];
    for (const s of all) {
      const names = [s.name.toLowerCase().replace(/ё/g, "е"), ...s.aliases];
      if (names.includes(q) || names.includes(q.replace(/^радио /, ""))) {
        const tg = new Set(s.tags.split(" ")); return [s, ...all.filter(x => x !== s && x.tags.split(" ").some(t => t && tg.has(t)))];
      }
    }
    const want = [];
    words(query).filter(w => !FILLER.has(w)).forEach(w => { want.push(stem(w)); for (const k in SYN) if (w.startsWith(k)) SYN[k].split(" ").forEach(x => want.push(stem(x))); });
    if (!want.length) return [];
    return all.map(s => {
      const nw = [...words(s.name), ...s.aliases.flatMap(words)].map(stem), tw = words(s.tags).map(stem);
      return { s, sc: want.filter(w => nw.includes(w)).length * 3 + want.filter(w => tw.includes(w)).length * 2, r: Math.random() };
    }).filter(x => x.sc).sort((a, b) => b.sc - a.sc || a.r - b.r).map(x => x.s);
  }
  async function search(query) {                // каталог radio-browser: ~50 000 станций, популярные сверху, нерабочие скрыты
    const ws = words(query).filter(w => !FILLER.has(w));
    let tag = ""; for (const w of ws) for (const k in GENRE_EN) if (!tag && w.startsWith(k)) tag = GENRE_EN[k];
    const p = new URLSearchParams({ limit: "8", hidebroken: "true", order: "clickcount", reverse: "true" });
    if (tag) p.set("tag", tag); else if (ws.length) p.set("name", ws.join(" ")); else p.set("countrycode", "RU");
    let last = "";
    for (const base of API) {
      try {
        const r = await http("GET", base + "/json/stations/search?" + p, { headers: { "User-Agent": "Dewiar-Android (voice assistant)" }, timeout: 10000 });
        if (r.status !== 200) { last = "ответ " + r.status; continue; }
        return JSON.parse(r.body).filter(x => x.url_resolved || x.url).map(x => ({ name: String(x.name || "").trim(), url: x.url_resolved || x.url, tags: String(x.tags || ""), aliases: [] }));
      } catch (e) { last = e.message; }
    }
    throw new Error("каталог радиостанций недоступен" + (last ? ": " + last : ""));
  }
  N.on("sound_end", () => $$(".snd.play").forEach(x => x.classList.remove("play")));     // проба звука напоминаний доиграла
  N.on("radio", e => {
    st = { state: e.state, name: e.name || "", error: e.error || "", by: e.by || "" };
    if (st.state === "paused" && st.by === "focus") focusAt = Date.now();
    waiters.splice(0).forEach(f => f(st));
    render();
    // станция заиграла, а через пару секунд замолчала или оборвалась — сами включаем похожую, а не оставляем тишину
    if (st.state === "error" && !starting && cur && st.name === cur.name && !autoTried[cur.url]) {
      autoTried[cur.url] = 1; bad[cur.url] = Date.now();
      toast(`«${cur.name}» не играет (${st.error || "нет звука"}) — включаю другую`, 3500);
      next().then(r => { if (!r.ok) toast(r.text.replace(/^Ошибка: /, ""), 4000); });
    }
  });
  function resumeAfterTalk() {                    // распознавание речи забрало динамик — после ответа радио продолжает само
    if (st.state === "paused" && st.by === "focus" && Date.now() - focusAt < 5 * 60e3) D.radioResume();
  }
  async function resolve(s) {                     // ссылка на плейлист (.m3u, .pls) — достаём сам поток
    if (!/\.(m3u|pls)(\?|$)/i.test(s.url)) return s;
    try {
      const r = await http("GET", s.url, { timeout: 10000 });
      const u = (String(r.body || "").match(/^(?:File\d+=)?\s*(https?:\/\/\S+)/im) || [])[1];
      if (u) return Object.assign({}, s, { url: u.trim() });
    } catch (e) { }
    return s;
  }
  let startSeq = 0;
  async function start(s0) {
    const my = ++startSeq;                         // новая команда отменяет ожидание прежней (иначе «ждём» 15 с и не замечаем молчание)
    starting = true;
    const s = await resolve(s0);
    try { return my === startSeq ? await startRaw(s, my) : { state: "superseded" }; } finally { if (my === startSeq) starting = false; }
  }
  function startRaw(s, my) {
    return new Promise(res => {
      let done = false; const fin = (x) => { if (!done) { done = true; res(x); } };
      const w = (x) => {
        if (my !== startSeq) return fin({ state: "superseded", error: "переключили на другую" });
        if (x.name !== s.name) return waiters.push(w);
        if (x.state === "playing" || x.state === "error") fin(x); else waiters.push(w);
      };
      waiters.push(w);
      setTimeout(() => fin(my !== startSeq ? { state: "superseded" } : { state: "error", error: "не ответила за 15 секунд" }), 15000);
      D.radioPlay(s.url, s.name);
    });
  }
  async function play(query) {
    const op = ++opSeq; usedAt = Date.now();
    const q = String(query || "").trim();
    let fromList = match(q || "*"), cand = fromList;
    if (!cand.length) {
      try { cand = await search(q); } catch (e) { return { ok: false, text: `Ошибка: ${e.message}. Скажи пользователю, что сеть сейчас не даёт найти станцию.` }; }
    }
    if (!cand.length) return { ok: false, text: `Ошибка: не нашёл радиостанцию «${q}». Предложи жанр или известную станцию (Европа Плюс, Русское Радио, Маяк, джаз, релакс).` };
    if (fromList.length && cand.length < 3) {     // единственная станция не ответит — есть чем заменить: того же жанра
      const tg = new Set(cand[0].tags.split(" ").filter(Boolean)), have = new Set(cand.map(x => x.url));
      cand = cand.concat(list().filter(x => !have.has(x.url) && x.tags.split(" ").some(t => tg.has(t))));
    }
    if (q && !fromList.length) {                  // из каталога: точное название — первым
      const ql = q.toLowerCase(); const ex = cand.find(x => x.name.toLowerCase() === ql) || cand.find(x => x.name.toLowerCase().includes(ql));
      if (ex) cand = [ex, ...cand.filter(x => x !== ex)];
    }
    const errs = [];
    if (op !== opSeq) return { ok: false, superseded: true, text: "" };
    cand = [cand[0], ...goodFirst(cand.slice(1))];   // названную станцию — первой, дальше — сначала те, что недавно не отказывали
    for (const s of cand.slice(0, 4)) {
      if (op !== opSeq) return { ok: false, superseded: true, text: "" };
      const r = await start(s);
      if (r.state === "superseded" || op !== opSeq) return { ok: false, superseded: true, text: "" };
      if (r.state === "playing") { cur = s; found = cand; remember(s); delete bad[s.url]; return { ok: true, station: s, others: cand.filter(x => x !== s).slice(0, 5).map(x => x.name) }; }
      bad[s.url] = Date.now();
      errs.push(`«${s.name}» — ${r.error || "не отвечает"}`);
    }
    if (op !== opSeq) return { ok: false, superseded: true, text: "" };
    D.radioStop();
    return { ok: false, text: `Ошибка: радио не заиграло: ${errs.join("; ")}. Похоже на сеть телефона — перескажи это простыми словами.` };
  }
  function remember(s) { played = [s.url, ...played.filter(u => u !== s.url)].slice(0, 8); }
  async function next() {
    if (!cur && st.name) cur = list().find(x => x.name === st.name) || null;      // после перезапуска экрана — знаем, что играет
    if (!cur) return play("*");
    const op = ++opSeq; usedAt = Date.now();
    const fresh = (xs) => xs.filter(x => x.url !== cur.url && !played.includes(x.url));
    // сначала — ещё не игравшие из прошлого поиска, потом того же жанра, потом любые из списка; по кругу не ходим
    const uniq = (xs) => xs.filter((x, i) => xs.findIndex(y => y.url === x.url) === i);
    let alts = uniq([...fresh(found), ...fresh(match(cur.tags.split(" ").filter(Boolean)[0] || "*")), ...fresh(match("*"))]);
    if (!alts.length) { played = [cur.url]; alts = fresh(match("*")); }
    alts = goodFirst(alts);
    const errs = [];
    for (const s of alts.slice(0, 4)) {
      if (op !== opSeq) return { ok: false, superseded: true, text: "" };
      const r = await start(s);
      if (r.state === "superseded" || op !== opSeq) return { ok: false, superseded: true, text: "" };
      if (r.state === "playing") { cur = s; remember(s); delete bad[s.url]; found = alts.filter(x => x !== s); return { ok: true, station: s, others: [] }; }
      bad[s.url] = Date.now(); remember(s); errs.push(`«${s.name}» — ${r.error || "не отвечает"}`);
    }
    if (op !== opSeq) return { ok: false, superseded: true, text: "" };
    D.radioStop();                                 // ни одна не заиграла — тишина честная, а не «подключаюсь» без конца
    return { ok: false, text: errs.length ? `Не заиграли: ${errs.join("; ")}. Похоже, сеть телефона сейчас не пускает к станциям.` : "Других станций нет." };
  }
  function on() { return st.state === "playing" || st.state === "preparing" || st.state === "paused"; }
  function playing() { return st.state === "playing" || st.state === "preparing"; }
  function pause() { opSeq++; D.radioPause(); }
  function resume() { if (!cur && !st.name) return false; D.radioResume(); return true; }
  function stop() { opSeq++; startSeq++; D.radioStop(); }
  function recent() { return !!(cur || st.name) && Date.now() - usedAt < 60 * 60e3; }     // радио включали недавно — «другую» понимаем и после ошибки
  function render() {
    const el = document.getElementById("rchip"), box = document.getElementById("radiobox"); if (!el) return;
    if (box) box.hidden = !on();
    document.body.classList.toggle("radio-on", on());
    try { if (orb) orb.vinyl = playing() ? (st.name || "Радио") : null; } catch (e) { }   // как на компьютере: в покое крутится пластинка
    el.classList.toggle("paused", st.state === "paused"); el.classList.toggle("wait", st.state === "preparing");
    const n = el.querySelector("b"); if (n) n.textContent = st.name || "Радио";
  }
  return { play, next, pause, resume, stop, on, playing, recent, render, refresh, match, list, resumeAfterTalk, state: () => st, current: () => cur };
})();

/* HTTP через Java (Dewiar.http → Net.java): без ограничений CORS, адреса Dewiar — через прокси (NetProxy.java).
   Ответ приходит событиями http_chunk / http_done / http_error с тем же id; stream — построчно (SSE / NDJSON) в onChunk.
   Ответ 4xx/5xx — не ошибка: resolve со status и телом; reject — только сбой связи или отмена (signal). */
let httpN = 0;
const pendingHttp = {};
N.on("http_chunk", e => { const p = pendingHttp[e.id]; if (p && p.onChunk) p.onChunk(e.text); });
N.on("http_done", e => { const p = pendingHttp[e.id]; if (p) { delete pendingHttp[e.id]; p.resolve({ status: e.status, body: e.body, url: e.url || "" }); } });
N.on("http_error", e => { const p = pendingHttp[e.id]; if (p) { delete pendingHttp[e.id];
  const err = new Error(netErr(e.error, p.url)); err.net = true; err.raw = String(e.error || ""); err.url = p.url || ""; p.reject(err); } });
/* idle — поток ответа молчит дольше idle мс (мобильная связь «зависла», а соединение не рвётся) — обрываем сами
   и отдаём сетевую ошибку (net, idle): ask() повторит этот круг, не дожидаясь трёхминутного таймаута. */
function http(method, url, { headers = {}, body = null, stream = false, onChunk = null, timeout = 120000, signal = null, idle = 0 } = {}) {
  const id = "h" + (++httpN);
  return new Promise((resolve, reject) => {
    let tm = 0;
    const kick = () => {
      if (!idle) return;
      clearTimeout(tm);
      tm = setTimeout(() => { if (!pendingHttp[id]) return; D.abort(id); delete pendingHttp[id];
        reject(Object.assign(new Error("сервер замолчал посреди ответа — похоже, слабая связь"), { net: true, idle: true, url })); }, idle);
    };
    pendingHttp[id] = { resolve: (v) => { clearTimeout(tm); resolve(v); }, reject: (e) => { clearTimeout(tm); reject(e); },
      onChunk: (onChunk || idle) ? (c) => { kick(); if (onChunk) onChunk(c); } : null, url };
    kick();
    if (signal) signal.onabort = () => { D.abort(id); delete pendingHttp[id]; reject(new Error("отменено")); };
    D.http(id, method, url, JSON.stringify(headers), body == null ? "" : (typeof body === "string" ? body : JSON.stringify(body)), !!stream, timeout);
  });
}
/* Понятная причина сетевой ошибки. «Не дома» — только когда адрес и правда домашний (10.*, 192.168.*, …): на мобильной
   связи в городе ошибка облака Dewiar — это связь или сервер, а не «домашняя сеть». Таймаут проверяем раньше отказа:
   у Android таймаут соединения звучит как «failed to connect … after 15000ms». */
const HOME_URL = /^https?:\/\/(?:10\.|192\.168\.|172\.(?:1[6-9]|2\d|3[01])\.|127\.|localhost\b|[\w-]+\.local\b)/i;
function netErr(e, url) {
  e = String(e || "");
  const home = HOME_URL.test(url || "");
  // №229 (24.10): «Failed to connect to /127.0.0.1:1234» — 127.0.0.1 на телефоне — это сам телефон, а LM Studio — на компьютере
  if (/^https?:\/\/(?:127\.|localhost\b)/i.test(url || "") && /refused|failed to connect|timeout|timed out/i.test(e))
    return "адрес 127.0.0.1 — это сам телефон, а модель работает на компьютере. В «Мозге» впишите адрес компьютера в домашней сети (например, 192.168.1.5:1234 — он есть в LM Studio или Ollama)";
  if (/Unable to resolve|UnknownHost|No address/i.test(e)) return home ? "домашний сервер не найден (возможно, вы не дома)" : "нет интернета или слабая связь";
  if (/timeout|timed out|after \d+\s*ms/i.test(e)) return home ? "домашний сервер долго не отвечает (возможно, вы не дома)" : (/dewiar\.pro/i.test(url || "") ? "сервер Dewiar долго не отвечает — слабая связь или сейчас много людей сразу" : "сервер долго не отвечает — похоже, слабая связь");
  if (/ECONNREFUSED|Connection refused|failed to connect|reset|closed|EOF|connection abort/i.test(e)) return home ? "домашний сервер не отвечает (возможно, вы не в домашней сети)" : "связь с сервером оборвалась";
  return e;
}

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
const feat = (k) => (S.features || {})[k] !== false;      // «Возможности»: включено ли (нет ключа — да)
// 22.10: облако отклоняло chat_template_kwargs, а телефон сразу переходил на функции текстом и запоминал это — один раз
// проверим заново: теперь сначала пробуется запрос без chat_template_kwargs, с функциями полем (так они работают лучше)
// 22.10, вечер: настоящая причина — сайт превращал пустой {} в схеме функции в [] (cloud.php chat_schema_fix): ещё раз
if (S.llm.tools_prompt && !S.llm.rej_v3) { delete S.llm.tools_prompt; S.llm.rej_v3 = 1; }
applyProxy();                                      // прокси для серверов Dewiar — с первого запроса
function saveS() { llmRemember(); prefSet("settings", JSON.stringify(S)); applyProxy(); setTimeout(startCardCheck, 0); }
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
    else list = list.filter(x => !x.cloud);                 // облако «забыли» (ключ, выход) — не держим и прежние облачные
  }
  S.llmSaved = list.filter(x => llmId(x) && llmId(x) !== b).slice(0, 5);
  llmSeen = JSON.parse(JSON.stringify(S.llm || {}));
}
/* Что можно вернуть: прежние мозги, а для тех, кто подключался до этого списка, — Dewiar Облако по ключу, что остался у слуха. */
function llmBack() {
  const out = (S.llmSaved || []).filter(x => !(x.cloud && x.account && !loggedIn()));
  if (!S.llm.cloud && !out.some(x => x.cloud) && /^dw-/.test(S.stt.key || "") && /cloud\.php/.test(S.stt.url || ""))
    out.push({ cloud: true, base_url: S.stt.url, api_key: S.stt.key, name: "Dewiar Облако", restore: "key" });
  return out;
}
function brainNameOf(l) { return l.cloud ? "Dewiar Облако" + (l.account ? " · по аккаунту" : "") : `${l.name || l.base_url.replace(/^https?:\/\//, "")}${l.model ? " · " + l.model : ""}`; }
async function llmRestore(i) {
  const l = llmBack()[i]; if (!l) return;
  if (l.cloud) await cloudConnect(l.account ? S.account.token : l.api_key, l.base_url.split("?")[0], { account: !!l.account });
  else { S.llm = Object.assign({}, DEF.llm, l); delete S.llm.restore; saveS(); }
  cloudInfo = l.cloud ? cloudInfo : null;
}
/* Первый запуск показывает «Подключить бесплатно» / «У меня есть код». Подключились любым путём (вход аккаунтом, ключ,
   код с другого устройства, одобренная заявка) — карточка уходит, Лира говорит, что готова (отчёт №50, 13.10: вошёл
   логином и паролем, а на экране всё ещё «Подключить бесплатно» — человек решил, что не подключился). */
function startCardCheck() {
  const c = $("#card .start, #card [onclick*='joinPoll']");
  if (!c || !((S.llm.base_url && !S.llm.trial) || loggedIn())) return;     // пробный разговор — ещё не «подключено»
  showCard("");
  if (!busy && state === "idle") showBot(`Готово, всё подключено${loggedIn() ? " — аккаунт " + (S.account.login || "") : ""}. Нажмите на микрофон или удерживайте его и говорите.`);
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
window.addEventListener("error", (e) => { if (e.message) problem("js:" + e.message, `${e.message} (${String(e.filename || "").split("/").pop()}:${e.lineno || 0})`, e.error); });
window.addEventListener("unhandledrejection", (e) => {
  const m = String((e.reason && e.reason.message) || e.reason || "");
  if (m && !NETLIKE.test(m)) problem("promise:" + m.slice(0, 80), "Promise: " + m, e.reason);
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
async function reportSend(note, auto, summary, extra) {
  let info = {}; try { info = JSON.parse(D.info() || "{}"); } catch (e) { }
  // в отчёт не попадает секретное: ключи, токены, пароли, прокси (в нём бывает логин) — звёздочками; ниже то же для текста журнала
  const mask = (o) => JSON.parse(JSON.stringify(o, (k, v) => /key|token|pass|secret|auth|cookie|proxy/i.test(k) && v && typeof v !== "object" ? "***" : v));
  const st = Object.assign({}, S, { memory: `(записей: ${(S.memory || []).length})` });
  const errs = PLOG.filter(l => /^\S+ (ERROR|WARNING) /.test(l));
  note = String(note || "").trim().slice(0, 2000);
  let text = [`Dewiar (телефон) ${info.version || ""} — отчёт ${new Date().toLocaleString("ru-RU")}`,
    `Android ${info.android || ""}; ${info.device || ""}; распознаватель: ${info.recognizer}; голос: ${info.tts}`, "",
    ...(note ? ["== Со слов человека", note, ""] : []),
    "== Состояние", JSON.stringify({ state, online: navigator.onLine, sync: syncStatus, cloud: cloudInfo }, null, 1), "",
    "== Настройки (без ключей)", JSON.stringify(mask(st), null, 1), "",
    ...(info.crash ? ["== Последнее падение приложения", info.crash, ""] : []),
    ...(errs.length ? ["== Ошибки (последние)", ...errs.slice(-40), ""] : []),
    "== Журнал (последние строки)", ...PLOG.slice(auto ? -200 : -400)].join("\n");
  text = text.replace(/(Bearer\s+)[\w.-]+/g, "$1***").replace(/\bdw-[a-z0-9]{4,}(?:-[a-z0-9]{2,})+/gi, "dw-***");
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
/* ---------- «Здоровье» и жалобы (сервер — cloud.php, вкладка «Здоровье»; компьютер — core/health.py, формат общий) ----------
   Пульс (/pulse): через минуту после запуска и раз в 6 часов — случайный номер установки (S.dev), версия, Android, модель
   телефона, где думает (dewiar | local | server | cloud | none — без адресов), запуски (за сколько секунд готов), ответы,
   удачные и неудачные запросы к мозгу, сбои по подписям. Без разговоров, файлов и ключей; выключается S.pulse.
   Счётчики — pref "health" до отправки. Жалоба: слова, снимок экрана приложения (D.snapshot() — снимается, когда открывают
   настройки: каким был экран до них), подпись S.who; номер и секрет — в S.complaints, раз в 6 часов спрашиваем ответ
   (/report/status) и, когда ответили или исправили, — уведомление со спасибо. Голосом: «сообщи об ошибке: …» (quick). */
const H_T0 = Date.now() - (window.performance && performance.now ? performance.now() : 0);
let bugSnap = null, thanksCache = null, bugWait = 0, bugPick = "";   // bugPick — фото или скриншот из галереи к жалобе
function hLoad() { try { return JSON.parse(prefGet("health") || "{}") || {}; } catch (e) { return {}; } }
function hSave(h) { try { prefSet("health", JSON.stringify(h)); } catch (e) { } }
function hCount(k, n = 1) { const h = hLoad(); h[k] = (h[k] || 0) + n; hSave(h); }
/* Почему не ответил мозг — «где думает : почему» (пакет 20.10: «неудачных 10,7 %» — а каких?). Как why_kind в core/health.py. */
const WHY_RX = [["timeout", /не ответил вовремя|timed? ?out|таймаут|отменено|abort/i], ["connect", /подключ|connect|resolve|сеть|network|failed to fetch|refused/i],
  ["context", /окна контекста|context/i], ["busy", /много людей|занят|429|503|busy/i], ["balance", /заряд|талер|402|quota/i],
  ["key", /ключ|401|403|forbidden|не пускает/i], ["rejected", /отклонил|400|422|413|тариф/i], ["server", /\b5\d\d\b|недоступн/i]];
function hWhy(err) {
  const k = brainKind() + ":" + ((WHY_RX.find(([, rx]) => rx.test(String(err || ""))) || ["other"])[0]);
  const h = hLoad(); h.net_why = h.net_why || {};
  if (h.net_why[k] || Object.keys(h.net_why).length < 40) h.net_why[k] = (h.net_why[k] || 0) + 1;
  hSave(h);
}
/* Голос по всем телефонам (отзыв 13.10: «у многих голосом не выходит, ответы только текстом», а объяснить не могут):
   счётчики слуха и голоса уходят в пульс (voice) — в «Здоровье» видно, у скольких и почему молчит. Только числа. */
function vCount(k, n = 1) { const h = hLoad(); h.voice = h.voice || {}; h.voice[k] = (h.voice[k] || 0) + n; hSave(h); }
function hClean(t) {
  return String(t || "").replace(/(Bearer\s+)[\w.-]+/g, "$1***").replace(/\bdw-[a-z0-9-]{6,}/gi, "dw-***").replace(/(:\/\/[^/\s:@]+:)[^@\s/]+@/g, "$1***@")
    .replace(/\b[\w.+-]+@[\w-]+\.[\w.]+\b/g, "<почта>").replace(/\b(?!127\.0\.0\.1\b)\d{1,3}(?:\.\d{1,3}){3}\b/g, "<ip>").trim().slice(0, 300);
}
function hProblem(text) {
  text = hClean(text); if (!text) return;
  const sig = text.replace(/https?:\/\/\S+/g, "URL").replace(/\d+/g, "#").slice(0, 160);
  const h = hLoad(); h.problems = h.problems || {};
  if (!h.problems[sig] && Object.keys(h.problems).length >= 30) return;
  const p = h.problems[sig] = h.problems[sig] || { text, n: 0 }; p.n++; p.text = text; h.errors = (h.errors || 0) + 1; hSave(h);
}
function hReady() {                                       // приложение готово слушать — запуск записан (для «Запуск» в «Здоровье»)
  const h = hLoad(), first = !prefGet("h_seen");
  h.starts = (h.starts || []).slice(-9).concat([{ ts: Math.round(Date.now() / 1000), ready_s: Math.round((Date.now() - H_T0) / 100) / 10, cpu: 0, first }]);
  hSave(h); if (first) prefSet("h_seen", "1");
}
function devId() { if (!/^ph-[0-9a-f]{16}$/.test(S.dev || "")) { S.dev = "ph-" + Array.from({ length: 16 }, () => "0123456789abcdef"[Math.random() * 16 | 0]).join(""); saveS(); } return S.dev; }
function brainKind() {
  if (S.llm.cloud) return "dewiar";
  if (!S.llm.base_url) return loggedIn() ? "dewiar" : "none";
  const host = String(S.llm.base_url).replace(/^\w+:\/\//, "").split(/[/:]/)[0].toLowerCase();
  if (/dewiar/.test(host)) return "dewiar";
  if (/^(localhost|127\.|0\.0\.0\.0)/.test(host)) return "local";
  if (/^(10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.)/.test(host) || /\.local$/.test(host) || !host.includes(".")) return "server";
  return "cloud";
}
const healthBase = () => ((syncCred() || {}).base || CLOUD_URL).split("?")[0];
async function pulseSend() {
  if (S.pulse === false) return false;
  let info = {}; try { info = JSON.parse(D.info() || "{}"); } catch (e) { }
  const h = hLoad();
  const body = { dev: devId(), app: "phone", version: info.version || "", os: "Android " + (info.android || ""), hw: { device: info.device || "", webview: webviewVer().replace(/^ · /, "") },
    brain: brainKind(), uptime_h: Math.round((Date.now() - H_T0) / 36e4) / 10, starts: h.starts || [], turns: h.turns || 0, net_ok: h.net_ok || 0,
    net_fail: h.net_fail || 0, net_why: h.net_why || {}, errors: h.errors || 0, rude: h.rude || 0, refused: h.refused || 0, problems: Object.entries(h.problems || {}).map(([sig, p]) => ({ sig, text: p.text, n: p.n })),
    voice: Object.assign({}, h.voice || {}, { tts_engine: S.tts.engine || "", tts_ready: D.ttsReady() ? 1 : 0, text_mode: S.textMode ? 1 : 0,
      stt_engine: S.stt.engine || "", recognizer: D.recognizer() ? 1 : 0, vol: (() => { try { return D.volume("get", 0); } catch (e) { return -1; } })() }) };
  let r; try { r = await http("POST", healthBase() + "?p=/pulse", { headers: { "Content-Type": "application/json" }, body, timeout: 20000 }); }
  catch (e) { console.log("💓 пульс не ушёл: " + (e.message || e)); return false; }
  if (r.status >= 400) return false;
  const now = hLoad();                                        // вычесть отправленное: пока шёл запрос, могло прибавиться
  for (const k of ["turns", "net_ok", "net_fail", "errors", "rude", "refused"]) now[k] = Math.max(0, (now[k] || 0) - (body[k] || 0));
  for (const k of Object.keys(body.net_why)) if (now.net_why && now.net_why[k]) { now.net_why[k] -= body.net_why[k]; if (now.net_why[k] <= 0) delete now.net_why[k]; }
  if (now.voice) { for (const k of Object.keys(body.voice)) if (typeof now.voice[k] === "number" && !/^(tts_ready|text_mode|recognizer|vol)$/.test(k)) now.voice[k] = Math.max(0, now.voice[k] - (body.voice[k] || 0)); }
  for (const p of body.problems) if (now.problems && now.problems[p.sig]) { now.problems[p.sig].n -= p.n; if (now.problems[p.sig].n <= 0) delete now.problems[p.sig]; }
  now.starts = (now.starts || []).slice(body.starts.length);
  hSave(now); prefSet("pulse_at", String(Date.now()));
  console.log(`💓 Пульс отправлен: запусков ${body.starts.length}, ответов ${body.turns}, сбоев ${body.problems.length}`);
  try { const d = JSON.parse(r.body || "{}"); if (d.exam && typeof examOffer === "function") examOffer(d.exam); } catch (e) { }   // экзамен из кабинета
  return true;
}
function bugSnapTake() {                                    // открыли настройки — каким был экран до них (для жалобы)
  try { const b = D.snapshot ? D.snapshot() : ""; bugSnap = b ? { ts: Date.now(), b64: b } : bugSnap; } catch (e) { }
}
const bugPickHtml = () => bugPick
  ? `<div class="bpk"><img src="${bugPick}" alt="Фото к жалобе" id="bug-pickimg"><button class="x" id="bug-pickx" title="Убрать фото" aria-label="Убрать фото">${X_SVG}</button></div>`
  : `<label class="btn w"><input type="file" id="bug-file" accept="image/*" hidden>📎 Добавить фото или скриншот</label><p class="hint" style="margin:6px 2px 0">Откроется галерея — свежие скриншоты в ней первыми.</p>`;
async function complaintSend(note, who, withShot, via) {
  note = String(note || "").trim();
  if (note.length < 3) throw new Error("напишите хотя бы пару слов — что пошло не так");
  who = String(who || "").replace(/[<>"]/g, "").trim().slice(0, 40); S.who = who;
  const snap = withShot && bugSnap && Date.now() - bugSnap.ts < 30 * 6e4 ? "data:image/jpeg;base64," + bugSnap.b64 : "";
  const shot = snap && bugPick ? await stitchShots([bugPick, snap]) : (bugPick || snap);    // снимок один — оба рядом
  const d = await reportSend(note, false, `жалоба (${via || "кнопкой"})`, { shot, who });
  S.complaints = (S.complaints || []).filter(c => Date.now() / 1000 - c.ts < 180 * 86400).slice(-49)
    .concat([{ id: d.id, s: d.secret || "", base: d.base, note: note.slice(0, 200), ts: Math.round(Date.now() / 1000), status: "new", reply: "", fixed: "", shot: !!shot }]);
  saveS(); if (shot) { bugSnap = null; bugPick = ""; }
  console.log(`🐞 Жалоба №${d.id} отправлена (${via || "кнопкой"})${shot ? " со снимком" : ""}`);
  return { id: d.id, shot: !!shot };
}
/* две картинки (фото из галереи и снимок экрана) — одной, рядом: в жалобе место для одного снимка */
function stitchShots(urls) {
  return Promise.all(urls.map(u => new Promise((ok, no) => { const im = new Image(); im.onload = () => ok(im); im.onerror = () => no(new Error("снимок не открылся")); im.src = u; })))
    .then(ims => { const h = Math.min(1400, Math.max(...ims.map(i => i.height))), ws = ims.map(i => Math.round(i.width * h / i.height)), gap = 16;
      const c = document.createElement("canvas"); c.width = ws.reduce((a, b) => a + b, 0) + gap * (ims.length - 1); c.height = h;
      const g = c.getContext("2d"); g.fillStyle = "#111"; g.fillRect(0, 0, c.width, c.height);
      let x = 0; ims.forEach((im, i) => { g.drawImage(im, x, 0, ws[i], h); x += ws[i] + gap; });
      return c.toDataURL("image/jpeg", 0.85); }).catch(() => urls[0]);
}
function complaintMessage(c) {
  const what = `«${String(c.note || "").slice(0, 60)}»`, reply = c.reply ? " " + c.reply.trim() : "", reward = c.reward ? ` В благодарность — ${c.reward} тал. на ваш ключ.` : "";
  if (c.status === "fixed") return [`Ваша жалоба №${c.id} исправлена`, `${what} — исправлено${c.fixed ? " в версии " + c.fixed : ""}.${reply}${reward} Спасибо, что помогаете делать Dewiar лучше!`];
  if (c.status === "work") return [`Жалоба №${c.id} — в работе`, `${what}: разработчик подтвердил и чинит.${reply}${reward} Спасибо!`];
  if (c.status === "no") return [`Ответ на жалобу №${c.id}`, `${what}.${reply || " Разработчик не нашёл тут ошибки."} Спасибо, что написали!`];
  return [`Ответ на жалобу №${c.id}`, `${what}.${reply}`];
}
async function complaintsCheck() {
  const ask = (S.complaints || []).filter(c => c.s && (!["fixed", "no"].includes(c.status) || Date.now() / 1000 - c.ts < 30 * 86400));
  if (!ask.length) return [];
  const news = [];
  for (const base of [...new Set(ask.map(c => c.base || healthBase()))]) {
    let r; try { r = await http("POST", base + "?p=/report/status", { headers: { "Content-Type": "application/json" },
      body: { items: ask.filter(c => (c.base || healthBase()) === base).map(c => ({ id: c.id, s: c.s })) }, timeout: 15000 }); } catch (e) { continue; }
    let d = {}; try { d = JSON.parse(r.body || "{}"); } catch (e) { }
    for (const x of d.items || []) {
      const c = S.complaints.find(y => y.id === x.id && (y.base || healthBase()) === base); if (!c) continue;
      const changed = x.status !== c.status || (x.reply || "") !== (c.reply || "");
      Object.assign(c, { status: x.status, reply: x.reply || "", fixed: x.fixed || "", reward: x.reward || 0 });
      if (changed && (["work", "fixed", "no"].includes(x.status) || x.reply)) news.push(c);
    }
  }
  saveS();
  if (news.length) thanksCache = null;                       // подтвердили — в «Помощниках» мог появиться и он сам
  for (const c of news) { const [t, x] = complaintMessage(c); D.notify(t, x); toast(t, 4000); }
  return news;
}
async function thanksGet() {
  if (thanksCache && Date.now() - thanksCache.at < 36e5) return thanksCache.people;
  const r = await http("GET", healthBase() + "?p=/thanks", { timeout: 10000 });
  let d = {}; try { d = JSON.parse(r.body || "{}"); } catch (e) { }
  thanksCache = { at: Date.now(), people: d.people || [] };
  return thanksCache.people;
}
const BUG_ST = { new: "отправлена", seen: "прочитана", work: "в работе", fixed: "исправлено", no: "не ошибка" };
function complaintsHtml() {
  const mine = (S.complaints || []).slice().reverse().slice(0, 6);
  return mine.length ? `<div class="bugh">Мои жалобы</div>` + mine.map(c => `<div class="bugc"><div><b>№${esc(c.id)}</b> ${esc(c.note || "")}</div>`
    + `<div class="bst"><span class="chip ${esc(c.status)}">${BUG_ST[c.status] || esc(c.status)}${c.status === "fixed" && c.fixed ? " в " + esc(c.fixed) : ""}</span>`
    + `${new Date(c.ts * 1000).toLocaleDateString("ru-RU")}${c.reward ? ` · спасибо ${+c.reward || 0} тал.` : ""}</div>${c.reply ? `<div class="brep">${esc(c.reply)}</div>` : ""}</div>`).join("") : "";
}
// «сообщи об ошибке: радио молчит», «передай разработчику, что…», «пожалуйся разработчику…»
const BUG_RX = /^(?:(?:сообщи|передай|напиши|отправь|скажи)\s+(?:разработчик\S*\s+)?(?:об?\s+)?(?:ошибк\S*|проблем\S*|баг\S*|сбо\S*)|отправь\s+жалобу(?:\s+разработчик\S*)?|пожалуйся(?:\s+разработчик\S*)?|(?:передай|скажи|напиши)\s+разработчик\S*)(?:\s*[:,.—-]\s*|\s+)?(?:что\s+)?([\s\S]*)$/i;
/* Жалоба оборвалась на паузе (отчёт №90, 19.10: «передай разработчику приложения что» ушло как есть — «меня до конца
   дослушай»): хвост — служебное слово или пусто — переспросить и дописать следующую фразу к началу (как core/health.py). */
const BUG_LEAD = /^(?:(?:этого\s+|этой\s+)?(?:приложени\S*|программ\S*|dewiar\S*|девиар\S*|лиры|ассистент\S*)\s*[,:]?\s*)?(?:что\s+|о\s+том,?\s+что\s+)?/i;
const BUG_TAIL = new Set("что чтобы и а но или в во на про о об у с со к ко по за для из от до когда если потому как где это вот ну типа не очень приложения программы мне меня там тут так".split(" "));
function bugNote(raw) {
  const s = String(raw || "").trim().replace(/^[\s.,:;—-]+|[\s.,:;—-]+$/g, "").replace(BUG_LEAD, "").replace(/^[\s.,:;—-]+|[\s.,:;—-]+$/g, "");
  const w = s.toLowerCase().replace(/ё/g, "е").match(/[\p{L}\d-]+/gu) || [];
  if (s.length < 4 || !w.length) return ["", true];
  if (BUG_TAIL.has(w[w.length - 1])) return [w.length > 2 ? s : "", true];
  return [s, false];
}
let bugPrefix = "";
async function bugQuick(text) {
  const t = text.trim();
  let note;
  if (bugWait && Date.now() - bugWait < 40000) {
    bugWait = 0;
    if (/^(отмена|отмени|не надо|ничего|передумал\S*|забудь)\W*$/i.test(t)) { bugPrefix = ""; return { say: "Хорошо, не отправляю." }; }
    note = (bugPrefix + " " + t).trim(); bugPrefix = "";
  } else {
    const m = t.match(BUG_RX); if (!m) return null;
    const [n, cut] = bugNote(m[1]);
    if (cut) { bugWait = Date.now(); bugPrefix = n; return { say: n ? "Слушаю — договорите, что передать разработчику." : "Что случилось? Расскажите одной-двумя фразами — передам разработчику." }; }
    note = n;
  }
  try { const r = await complaintSend(note, S.who, false, "голосом"); return { say: gfix(`Передал разработчику — жалоба №${r.id}. Когда ответят или исправят, скажу. Спасибо, что помогаете!`) }; }
  catch (e) { return { say: `Не получилось отправить: ${e.message}. Можно в настройках: «Ещё» → «Сообщить о проблеме».` }; }
}
setTimeout(async function pulseTick() {
  try { if (Date.now() - (+prefGet("pulse_at") || 0) > 6 * 36e5 - 6e4 || (hLoad().starts || []).length) await pulseSend(); } catch (e) { }
  try { if (Date.now() - (+prefGet("cmp_at") || 0) > 6 * 36e5 - 6e4) { prefSet("cmp_at", String(Date.now())); await complaintsCheck(); } } catch (e) { }
  setTimeout(pulseTick, window.DEWIAR_PULSE_EVERY || 6 * 36e5);
}, window.DEWIAR_PULSE_WAIT || 60000);
/* Прокси только для серверов Dewiar: dewiar.pro, поддомены, свой сайт аккаунта и облака (Java: NetProxy). */
function proxyHosts(extra) {
  return [S.account.server, S.accCloud && S.accCloud.base, S.llm.cloud && S.llm.base_url, S.stt.from_account && S.stt.url].concat(extra || [])
    .filter(Boolean).join(",");
}
function applyProxy(extra) {
  if (!D.setProxy) return "";
  const err = D.setProxy(effProxy(), proxyHosts(extra));
  if (err) console.warn("прокси:", err);
  return err;
}
/* Свой прокси главнее; нет своего, а включено «Использовать прокси Dewiar» — прокси, который выдал dewiar.pro (запомнен,
   пока сайт открывался). Только для серверов Dewiar: Telegram и остальной интернет — напрямую (трафик прокси платный). */
function effProxy() { return S.net.proxy || (S.net.dewiar && S.net.dewiar_secret) || ""; }
function dwProxyCred() {
  if (loggedIn()) return { token: S.account.token, base: ((S.accCloud && S.accCloud.base) || siteUrl("dwrapp/cloud.php")).split("?")[0] };
  if (S.llm.cloud && S.llm.api_key) return { token: S.llm.api_key, base: cloudBase() };
  return null;
}
/* «Прокси Dewiar»: адрес выдаёт облако (cloud.php ?p=/netcfg) вошедшим аккаунтом или с ключом Dewiar; обновляем раз в 6 ч.
   -> "" — получили (или ещё свежий), иначе текст ошибки. */
async function dwProxyFetch(force) {
  if (!S.net.dewiar) return "";
  if (!force && S.net.dewiar_secret && Date.now() - (S.net.dewiar_at || 0) < 6 * 36e5) return "";
  const c = dwProxyCred();
  if (!c) return "прокси Dewiar выдаётся тем, кто вошёл аккаунтом dewiar.pro или подключил ключ Dewiar";
  try {
    const d = await cloudGet(c.base, c.token, "/netcfg");
    S.net.dewiar_secret = normProxy(d.proxy || ""); S.net.dewiar_at = Date.now(); saveS();
    console.log("прокси Dewiar получен: " + hideProxy(S.net.dewiar_secret));
    return "";
  } catch (e) { console.log("прокси Dewiar не получен: " + e.message); return e.message; }
}
setTimeout(() => dwProxyFetch(false).catch(() => {}), 4000);
/* socks5://user:pass@host:1080, http://host:3128, host:port, ссылка t.me/socks?… → адрес; MTProto — отказ (как на компьютере). */
function normProxy(t) {
  t = String(t || "").trim(); if (!t) return "";
  const low = t.toLowerCase();
  if (/^(tg:\/\/socks|https?:\/\/t\.me\/socks|t\.me\/socks)/.test(low)) {
    const q = new URL(t.replace(/^tg:\/\/socks/i, "https://t.me/socks").replace(/^t\.me/i, "https://t.me")).searchParams;
    if (!q.get("server")) throw new Error("в ссылке нет адреса прокси (server=…)");
    const cred = q.get("user") ? encodeURIComponent(q.get("user")) + ":" + encodeURIComponent(q.get("pass") || "") + "@" : "";
    return `socks5://${cred}${q.get("server")}:${q.get("port") || 1080}`;
  }
  if (/^(tg:\/\/proxy|https?:\/\/t\.me\/proxy|t\.me\/proxy)/.test(low) || low.includes("secret="))
    throw new Error("это MTProto-прокси — он работает только в приложении Telegram. Нужен SOCKS5- или HTTP-прокси (socks5://адрес:порт) или VPN");
  if (!t.includes("://")) t = "http://" + t;
  let u; try { u = new URL(t.replace(/^socks5h?:|^socks:/i, "http:")); } catch (e) { throw new Error("прокси — socks5://адрес:порт или http://адрес:порт"); }
  const sch = t.split("://")[0].toLowerCase();
  if (!["http", "https", "socks5", "socks5h", "socks"].includes(sch)) throw new Error("прокси — socks5://адрес:порт или http://адрес:порт");
  if (!u.hostname || !u.port) throw new Error("у прокси нужен адрес и порт, например socks5://192.168.1.10:1080");
  return sch === "socks" ? "socks5" + t.slice(sch.length) : t;
}
const hideProxy = (p) => String(p || "").replace(/\/\/([^:/@]+):[^@]*@/, "//$1:•••@");
async function saveProxy(text, res, btn) {
  const old = S.net.proxy || "";
  let px;
  try { px = String(text || "").trim() === hideProxy(old) ? old : normProxy(text); }
  catch (e) { res.className = "res bad"; res.textContent = e.message; return false; }
  btn && (btn.disabled = true);
  res.className = "res"; res.textContent = px ? "проверяю, открывается ли dewiar.pro через этот прокси…" : "";
  S.net.proxy = px;
  const err = applyProxy();
  let ok = !err, why = err;
  if (px && ok) {
    try { const r = await http("GET", (S.account.server || SITE) + "/dwrapp/latest.json", { timeout: 15000 }); ok = r.status < 500 && r.status !== 407;
      why = r.status === 407 ? "прокси не принял логин или пароль" : "сайт ответил " + r.status; }
    catch (e) { ok = false; why = /end of stream|unexpected end/i.test(e.message) ? "прокси оборвал связь — проверьте адрес, порт, логин и пароль" : e.message; }
  }
  btn && (btn.disabled = false);
  if (!ok) { S.net.proxy = old; applyProxy(); res.className = "res bad"; res.textContent = `через этот прокси dewiar.pro не открывается (${why}) — не сохраняю`; return false; }
  saveS(); res.className = "res ok"; res.textContent = px ? "Готово: запросы к Dewiar идут через прокси." : "Прокси выключен — напрямую.";
  const inp = $("#px-in"); if (inp) inp.value = hideProxy(px);
  return true;
}
const blockedHint = () => S.net.proxy ? " Сейчас запросы к Dewiar идут через прокси — проверьте его: Настройки → Мозг → «Сеть»."
  : " Если dewiar.pro у вас заблокирован провайдером — укажите прокси: Настройки → Мозг → «Сеть».";
// реплики разговора: pref "history", хранятся последние 40 (вместе со свёрнутыми f:1 — см. ниже)
let history = (() => { try { return JSON.parse(prefGet("history") || "[]"); } catch (e) { return []; } })();
function saveH() { history = history.slice(-40); prefSet("history", JSON.stringify(history)); }

/* ---------- длинный разговор (как на компьютере, core/conversation.py) ----------
   Последние 8 пар реплик — модели дословно; когда сверх них накопится ещё 4 пары, модель в фоне сворачивает старое
   в краткое содержание, и оно идёт в системную подсказку. Свёрнутые реплики помечены f:1 (в «Разговоре» их видно, модели они не уходят).
   8 часов тишины или «начнём новый разговор» — новый разговор. Перерыв дольше 20 минут модель видит. */
const CONV_TURNS = 8, CONV_MARGIN = 4, CONV_KEEP = 8 * 3600e3;
const CONV_SUM = "Ты ведёшь краткое содержание долгого разговора голосового ассистента с пользователем — чтобы ассистент не забыл важное из начала. "
  + "Обнови содержание по новым репликам: о чём говорили; факты, имена, числа, даты; решения и договорённости; что пользователь просил и что сделано; "
  + "открытые вопросы; на чём остановились. Пиши по-русски, коротко, пунктами, от третьего лица («Пользователь…», «Ассистент…»). "
  + "Ничего не выдумывай и не добавляй советов. Не больше 18 пунктов, самое старое и мелкое — сокращай. Верни только содержание, без вступлений.";
let conv = (() => { try { return Object.assign({ summary: "", turns: 0, started: 0, last: 0 }, JSON.parse(prefGet("conv") || "{}")); } catch (e) { return { summary: "", turns: 0, started: 0, last: 0 }; } })();
let convBusy = false;
const saveConv = () => prefSet("conv", JSON.stringify(conv));
const liveHistory = () => history.filter(m => !m.f);
function convReset() { history.forEach(m => { m.f = 1; }); saveH(); conv = { summary: "", turns: 0, started: 0, last: 0 }; saveConv(); lastPics = null; }
function convCheck() { if (conv.last && Date.now() - conv.last > CONV_KEEP) convReset(); }
function convAfter() {
  const now = Date.now(); if (!conv.started) conv.started = now;
  conv.last = now; conv.turns++; saveConv();
  if (liveHistory().length > 2 * (CONV_TURNS + CONV_MARGIN) && !convBusy && S.llm.base_url) convFold();
}
async function convFold() {
  convBusy = true;
  try {
    const live = liveHistory(), old = live.slice(0, live.length - 2 * CONV_TURNS);
    if (old.length < 2) return;
    const lines = old.map(m => (m.role === "user" ? "Пользователь: " : "Ассистент: ") + String(m.content || "").slice(0, 1500)).join("\n");
    const msg = (conv.summary ? "Содержание разговора до сих пор:\n" + conv.summary + "\n\n" : "") + "Новые реплики:\n" + lines;
    const r = await llmStream([{ role: "system", content: CONV_SUM }, { role: "user", content: msg.slice(-24000) }], null, null);
    const text = String(r.text || "").replace(/^\s*(?:Краткое\s+)?содержание[^\n:]*:\s*/i, "").trim();
    if (text.length < 20) return;
    conv.summary = text.slice(0, 3000); saveConv();
    old.forEach(m => { m.f = 1; }); saveH();
  } catch (e) { console.log("разговор: свернуть не вышло — " + e.message); }
  finally { convBusy = false; }
}
function convPrompt() {                         // в подсказку — только редко меняющееся (содержание раньше сказанного)
  return conv.summary ? "Это продолжение долгого разговора. Раньше в нём было (кратко):\n" + conv.summary
    + "\nОпирайся на это, если пользователь возвращается к прежнему, — не переспрашивай то, что уже известно. Последние реплики — ниже, дословно." : "";
}
function convNote() {                           // сколько идёт разговор и перерыв — в справку к вопросу (turnContext)
  const out = [];
  if (conv.summary) { const mins = conv.started ? Math.round((Date.now() - conv.started) / 60000) : 0;
    out.push(`Разговор идёт ${mins >= 60 ? Math.floor(mins / 60) + " ч " + (mins % 60) + " мин" : mins + " мин"}, ${conv.turns} реплик.`); }
  const gap = conv.last ? Date.now() - conv.last : 0;
  if (gap > 20 * 60000) { const g = Math.round(gap / 60000);
    out.push(`Перед этим сообщением в разговоре был перерыв ${g >= 60 ? Math.floor(g / 60) + " ч " + (g % 60) + " мин" : g + " мин"}. Если новая просьба не связана с прежней темой — просто выполни её, не возвращаясь к старому.`); }
  return out.join(" ");
}
/* Справка к вопросу: время, ближайшая неделя (экзамен 11.10: «в среду» не считать в уме), разговор, найденное. Кладётся
   в начало последнего сообщения пользователя (putContext), не в подсказку и не в историю. */
/* Ближайшая неделя и «считай calc» — только к вопросу про даты и сроки: раньше шли к каждому, и ассистенты сами заводили
   речь о днях рождения и подсчёте дней (письмо пользователя 23.10; то же — core/engine_answer DATE_ASK_RX). */
const DATE_ASK = /дн(я|ей|и|ём)(?![а-яё])|недел|понедельник|вторник|сред[уыа]|четверг|пятниц|суббот|воскресен|завтра|послезавтра|числ[оа]|дат[аыуе]|когда|сколько.{0,20}(дн|недел|месяц|осталось)|через\s+\d|рождени|праздник|январ|феврал|март|апрел|ма[йя](?![а-яё])|июн|июл|август|сентябр|октябр|ноябр|декабр|\d{1,2}[./]\d{1,2}/i;
function turnContext(text) {
  const n = convNote();
  let rp = ""; try { rp = recentPrompt() || ""; } catch (e) { }
  let t = `Сейчас ${nowText()}.`;
  if (DATE_ASK.test(String(text || ""))) {
    const week = [1, 2, 3, 4, 5, 6, 7].map(i => { const d = new Date(Date.now() + i * 864e5); return `${WD[d.getDay()]} — ${d.getDate()} ${MON[d.getMonth()]}`; }).join("; ");
    t += ` Ближайшие дни: ${week}. Сколько дней до даты и какая дата ближе — считай calc days_until, не в уме.`;
  }
  return (rp ? rp.trim() + "\n\n" : "") + t + (n ? " " + n : "");
}
function putContext(msgs, ctx) {
  const last = msgs[msgs.length - 1];
  if (!ctx || !last || last.role !== "user") return;
  const head = "(Справка к этому сообщению — для тебя, вслух её не упоминай)\n" + ctx + "\n\n(Сообщение пользователя)\n";
  if (Array.isArray(last.content)) { const t = last.content.find(x => x.type === "text"); if (t) t.text = head + (t.text || ""); else last.content.unshift({ type: "text", text: head.trim() }); }
  else last.content = head + String(last.content || "");
}
const NEW_CONV_RX = /^(?:давай(?:те)?\s+)?(?:начн(?:ем|и)|начать)\s+(?:новый\s+разговор|разговор\s+заново|сначала|заново|с\s+чистого\s+листа)$|^(?:забудь|сотри|очисти)\s+(?:наш\s+|этот\s+|весь\s+)?разговор$|^новый\s+разговор$|^новая\s+тема$/;

/* ---------- персонажи и облик ---------- */
const PERSONAS = window.DEWIAR_PERSONAS || [{ id: "lira", name: "Лира", style: "strings", color: "#9BD4FF", character: "Ты — Лира, голосовой помощник Dewiar.", focus: "", gender: "female", role: "Главная помощница", aliases: ["лира"] }];
/* Свои персонажи на телефоне (19.10: «на телефоне нет функции создать персонажа», «хочу этот аватар»): имя, кто (он/она),
   роль, характер, облик из галереи, цвет. Хранятся в pref my_personas и стоят в PERSONAS после встроенных — дальше всё
   как у встроенных: имя зовёт, характер — в подсказке модели, облик — портретом. id «u…» — свои, встроенные не трогаем. */
const MY_MAX = 8;
function myPersonas() { try { const l = JSON.parse(prefGet("my_personas") || "[]"); return Array.isArray(l) ? l.filter(x => x && x.id && x.name) : []; } catch (e) { return []; } }
function myPersonaFull(x) {
  const fem = x.gender === "female", role = String(x.role || "").trim();
  return Object.assign({ style: x.avatar ? "photo" : "nexus", color: "#8A9BFF", focus: "", main: false, skills: [], tagline: "" }, x, {
    custom: true, aliases: [String(x.name).toLowerCase().replace(/ё/g, "е")],
    role: role || (fem ? "Своя помощница" : "Свой помощник"),
    // характер с компьютера уже целиком («Ты — …») — как есть; свой короткий — с именем и ролью впереди
    character: (/^\s*Ты\s/.test(x.about || "") ? String(x.about).trim() : `Ты — ${x.name}${role ? ", " + role : ""}. ` + (String(x.about || "").trim() || (fem ? "Тёплая, внимательная и живая собеседница." : "Спокойный, внимательный и живой собеседник.")))
      + " Ты — персонаж Dewiar: помогаешь делом (напоминания, заметки, звонки, поиск) и говоришь своим голосом и характером.",
  });
}
function myPersonasApply() {
  for (let i = PERSONAS.length - 1; i >= 0; i--) if (PERSONAS[i].custom) PERSONAS.splice(i, 1);
  for (const x of myPersonas()) PERSONAS.push(myPersonaFull(x));
}
myPersonasApply();
// с 0.4.27 встроенных двое — Лира и Патрик; выбранный прежде Агент, Джарвис, Эва или Кодер — теперь Лира
if (!PERSONAS.some(p => p.id === S.persona)) { S.persona = PERSONAS[0].id; try { prefSet("settings", JSON.stringify(S)); } catch (e) { } }
const persona = () => PERSONAS.find(p => p.id === S.persona) || PERSONAS[0];
const hex2rgb = (h) => { const n = parseInt(h.replace("#", ""), 16); return [(n >> 16) & 255, (n >> 8) & 255, n & 255]; };
let orb = null;
function applyPersona() {
  const p = persona(), [r, g, b] = hex2rgb(p.color || "#8A9BFF");
  document.documentElement.style.setProperty("--pc", p.color);
  document.documentElement.style.setProperty("--pcg", `rgba(${r},${g},${b},${lookSkin() === "neon" ? ".24" : ".10"})`);    // свечение персонажа: в «Неоне» — как раньше
  $("#who-name").textContent = p.name;
  $("#who-img").src = p.avatar || miniOrb(p);
  const style = p.avatar && p.style !== "aura" ? "photo" : p.style;
  // портрет сдержанно (белый край вместо цветного кольца), голос — лучами, как на компьютере; тема — «Ещё» → «Оформление»
  if (!orb) { orb = new DewiarEntity($("#orb"), { style, color: p.color, image: p.avatar || null, plate: true, live: p.live || "" }); orb.set({ audible: false }); applyLook(true); liteApply(); tiltSync(); }
  else orb.configure({ style, color: p.color, image: p.avatar || null, live: p.live || "" });
  orb.set({ state: state === "idle" ? "idle" : state });
  faceFor(p);
}
/* Наклон телефона — портрет «смотрит» на человека (просьба 14.10, параллакс без камеры). Датчик ориентации
   (deviceorientation, без разрешений): важна перемена наклона, а не поза — «как держит» подстраивается за пару секунд,
   и портрет возвращается к центру. Диск чуть поворачивается к человеку (CSS, до 7°), лицо сдвигается в глубину, живое
   лицо переводит на него глаза (DewiarEntity.look). Выключено: «Оформление» → «Портрет следит за наклоном», «уменьшить
   движение» в системе, экран не виден (приложение свёрнуто) и альбомный экран — датчик не слушаем вовсе.
   По умолчанию выключено (отзыв 14.10: «быстро надоедает — под флагом, по умолчанию выключен»). */
const TILT = { on: false, b0: null, g0: null, t: 0, x: 0, y: 0, raf: 0 };
function tiltWanted() {
  const angle = (screen.orientation && screen.orientation.angle) || 0;
  return S.tilt === true && !liteOn() && "DeviceOrientationEvent" in window && !document.hidden && angle === 0
    && !matchMedia("(prefers-reduced-motion: reduce)").matches;
}
function tiltOn(e) {
  if (e.beta == null || e.gamma == null) return;
  const now = performance.now(), dt = TILT.t ? Math.min(0.5, (now - TILT.t) / 1000) : 0; TILT.t = now;
  const b = e.beta, g = e.gamma;
  if (TILT.b0 === null || Math.abs(b - TILT.b0) > 60) { TILT.b0 = b; TILT.g0 = g; }   // первый замер или телефон перевернули
  const k = 1 - Math.exp(-dt / 2.5);
  TILT.b0 += (b - TILT.b0) * k; TILT.g0 += (g - TILT.g0) * k;
  const cl = (v) => Math.max(-1, Math.min(1, v));
  TILT.x += (cl(-(g - TILT.g0) / 12) - TILT.x) * 0.3; TILT.y += (cl((b - TILT.b0) / 12) - TILT.y) * 0.3;   // без дрожи датчика
  if (!TILT.raf) TILT.raf = requestAnimationFrame(tiltApply);
}
function tiltApply() {
  TILT.raf = 0;
  if (orb) orb.look(TILT.x, TILT.y);
  const c = $("#orb"); if (c) c.style.transform = `perspective(700px) rotateY(${(TILT.x * 7).toFixed(2)}deg) rotateX(${(-TILT.y * 6).toFixed(2)}deg)`;
}
function tiltSync() {
  const want = tiltWanted();
  if (want === TILT.on) return;
  TILT.on = want;
  if (want) { TILT.b0 = null; TILT.t = 0; window.addEventListener("deviceorientation", tiltOn); return; }
  window.removeEventListener("deviceorientation", tiltOn);
  cancelAnimationFrame(TILT.raf); TILT.raf = 0; TILT.x = TILT.y = 0;
  if (orb) orb.look(null);
  const c = $("#orb"); if (c) c.style.transform = "";
}
/* Лёгкий режим (18.10: «последние дни подтормаживает телефон… на компьютере работает даже на слабом — так и на
   Android?»). Сам включается на слабом телефоне (Android считает его маломощным или памяти ≤ 3 ГБ), при экономии
   батареи и если портрет рисуется медленно; «Ещё → Оформление → Лёгкий режим»: авто, всегда, никогда.
   Что делает: портрет в покое неподвижен, в разговоре — не чаще ~20 кадров/с; наклон не следим; синхронизация и
   проверки — втрое реже; «Близкие» без постоянной связи — проверка раз в 15 минут (CloseWatch), а не служба CloseLive. */
const LITE_RAM = 3072;
let liteSlow = false, liteHits = 0, liteState = null, liteWhyNow = "";
function liteDev() { try { return JSON.parse(D.deviceClass ? D.deviceClass() : "{}") || {}; } catch (e) { return {}; } }
function liteWhy() {
  const m = S.lite || "auto";
  if (m === "on") return "включён вручную";
  if (m === "off") return "";
  const d = liteDev();
  if (d.power_save) return "включена экономия батареи";
  if (d.low_ram || (d.ram_mb && d.ram_mb <= LITE_RAM)) return d.ram_mb ? `памяти ${(d.ram_mb / 1024).toFixed(d.ram_mb < 1536 ? 1 : 0).replace(".", ",")} ГБ` : "Android считает телефон маломощным";
  if (liteSlow) return "портрет рисовался медленно";
  return "";
}
const liteOn = () => liteState === true;
function liteApply() {
  liteWhyNow = liteWhy();
  const on = !!liteWhyNow, was = liteState;
  liteState = on;
  if (orb) { orb.still = on; orb.lite = on; }
  if (on !== was) {
    if (was !== null || on) plog("info", on ? "🪶 лёгкий режим: " + liteWhyNow : "🪶 лёгкий режим выключен");
    try { tiltSync(); } catch (e) { }
    try { clWatch(); } catch (e) { }
  }
}
// медленные кадры: облик сам считает, сколько рисуется кадр (_cost, мс); долго больше 14 мс — телефону тяжело
setInterval(() => {
  if (document.hidden || !orb || liteSlow || (S.lite || "auto") !== "auto") return;
  liteHits = (orb._cost || 0) > 14 ? liteHits + 1 : 0;     // три проверки подряд (полминуты) — не случайный всплеск
  if (liteHits >= 3) liteSlow = true;
  liteApply();
}, 10000);
document.addEventListener("visibilitychange", () => { if (!document.hidden) liteApply(); });
document.addEventListener("visibilitychange", () => tiltSync());
if (screen.orientation && screen.orientation.addEventListener) screen.orientation.addEventListener("change", () => tiltSync());

/* Облик для уведомлений и часов (Faces.java): фото персонажа или его облик в круге, 192×192, и имя с цветом.
   Рисуется при смене персонажа; уведомления и будильники берут его и без интерфейса (из файла). */
function faceFor(p) {
  if (!D.setFace) return;
  const c = document.createElement("canvas"); c.width = c.height = 192;
  const x = c.getContext("2d"), done = () => { try { D.setFace(p.id, p.name, p.color || "#8A9BFF", c.toDataURL("image/png").split(",")[1]); } catch (e) {} };
  x.save(); x.beginPath(); x.arc(96, 96, 96, 0, 7); x.clip();
  const g = x.createRadialGradient(80, 70, 10, 96, 96, 96);
  g.addColorStop(0, p.color || "#8A9BFF"); g.addColorStop(.6, "#1d1d38"); g.addColorStop(1, "#0d0d1a");
  x.fillStyle = g; x.fillRect(0, 0, 192, 192);
  if (!p.avatar) {                                      // без фото — первая буква имени на облике
    x.fillStyle = "#fff"; x.font = "600 84px Unbounded, Manrope, sans-serif"; x.textAlign = "center"; x.textBaseline = "middle";
    x.fillText((p.name || "D")[0].toUpperCase(), 96, 102); x.restore(); return done();
  }
  const im = new Image();
  im.onload = () => { const k = Math.max(192 / im.width, 192 / im.height), w = im.width * k, h = im.height * k;
    x.drawImage(im, (192 - w) / 2, (192 - h) / 2, w, h); x.restore(); done(); };
  im.onerror = () => { x.restore(); done(); };
  im.src = p.avatar;
}
function miniOrb(p) {          // значок персонажа без фото — кадр его облика
  const c = document.createElement("canvas"); c.width = c.height = 64;
  const x = c.getContext("2d"), g = x.createRadialGradient(28, 24, 4, 32, 32, 32);
  g.addColorStop(0, p.color); g.addColorStop(.55, "#1d1d38"); g.addColorStop(1, "#0d0d1a");
  x.fillStyle = g; x.beginPath(); x.arc(32, 32, 32, 0, 7); x.fill(); return c.toDataURL();
}

/* Оформление (как на компьютере, студия → «Оформление»): тема фона и облика (S.skin) и чем голос отзывается вокруг
   портрета (S.voice_fx). calm — по умолчанию: фон в фирменных цветах, белый край портрета; graphite — почти чёрный;
   neon — как раньше: свечение и цвет персонажа. */
// skins.js — общий с виджетом: все темы, и светлые (body.light — тёмный текст), и неоморфизм (body.neu — app.css)
const PHONE_SKINS = (window.DEWIAR_SKINS || []).slice();
const SKINS = PHONE_SKINS.length ? PHONE_SKINS.map(x => x.id) : ["brand"];
const lookSkin = () => (SKINS.includes(S.skin) ? S.skin : SKINS.includes("neusky") ? "neusky" : SKINS[0]);   // 20.10: по умолчанию — «Небесный»
// 24.10: фирменный звонок — «Струна» (владелец выбрал из пяти); остальные новые и прежний мотив — в коллекции
const ALARM_SOUNDS = [["signature", "Струна · фирменный", "Низкая струна и звонкий флажолет"], ["chasha", "Чаша", "Две поющие чаши, долгий звук"],
  ["kolodec", "Колодец", "Капли в каменном гроте"], ["hor", "Хор", "Тёплое «м-м-м» на три голоса"], ["glubina", "Глубина", "Аккорд снизу и мотив Dewiar сверху"],
  ["motif", "Прежний мотив", "Фирменный мотив Dewiar до 0.6.92"], ["drops", "Капли", "Мелодия из капель воды"],
  ["orbit", "Орбита", "Мягкий взлёт и пузырьки с эхом"], ["chime", "Колокольчики", "Стеклянные, вверх и обратно"], ["marimba", "Маримба", "Тёплое дерево, напев"],
  ["harp", "Арфа", "Перебор струн"], ["dawn", "Рассвет", "Аккорд нарастает, сверху — искры"], ["system", "Системный", "Звук будильника телефона"]];
const PLAY_SVG = '<svg viewBox="0 0 24 24"><path d="M8 5.5v13l10.5-6.5z" fill="currentColor" stroke="none"/></svg>';
const LOOK_BAR = { glass: "#FCD6E3", snow: "#F8F9FB" };      // верх фона светлых тем без сплошного цвета
let lookBar = "";
const lookFx = () => (["bars", "pulse", "wave"].includes(S.voice_fx) ? S.voice_fx : "bars");
function applyLook(fromPersona) {
  SKINS.forEach(k => document.body.classList.toggle("skin-" + k, k === lookSkin()));
  const sk = window.dewiarSkin ? dewiarSkin(lookSkin()) : {};
  document.body.classList.toggle("light", !!sk.light);
  document.body.classList.toggle("neu", !!sk.neu);
  try { const v = lookSkin() + (sk.light ? " light" : "") + (sk.neu ? " neu" : ""); if (D.pref("look_body") !== v) D.setPref("look_body", v); } catch (e) { }   // для index.html: тема до первой отрисовки
  // строка состояния и панель жестов — в цвет темы: светлым темам — светлые полосы и тёмные значки
  const bar = sk.neu ? getComputedStyle(document.body).getPropertyValue("--glass").trim() : (LOOK_BAR[sk.id] || "#0B0B10");
  try { if (D.bars && bar !== lookBar) { D.bars(/^#[0-9a-f]{6}$/i.test(bar) ? bar : "#0B0B10", !!sk.light); lookBar = bar; } } catch (e) { }
  if (orb) { orb.tone = (window.dewiarSkin && dewiarSkin(lookSkin()).tone) || "mono"; orb.fx = lookFx(); }
  if (!fromPersona) try { applyPersona(); } catch (e) { }       // свечение персонажа зависит от темы
}

/* ---------- состояние разговора ---------- */
let state = "idle";
const STATE_RU = { idle: "Нажмите или удерживайте", listening: "Слушаю", thinking: "Думаю", speaking: "Говорю" };
/* Звук «больше не слушаю»: ожидание кончилось без вопроса (или его отменили) — колокольчик вниз, как на компьютере
   (core/audio_io.py tone("sleep")). Начало слушания звучит у распознавателя телефона и вибрацией. */
let earCtx = null;
function earcon(kind) {
  try {
    earCtx = earCtx || new (window.AudioContext || window.webkitAudioContext)();
    if (earCtx.state === "suspended") earCtx.resume();
    const notes = kind === "sleep" ? [[784, 0], [523.3, 0.08]] : [[1046.5, 0], [1568, 0.07]], t0 = earCtx.currentTime + 0.01;
    notes.forEach(([f, at]) => [[1, 0.17], [2, 0.05], [3.01, 0.014]].forEach(([k, amp]) => {
      const o = earCtx.createOscillator(), g = earCtx.createGain();
      o.frequency.value = f * k; o.connect(g); g.connect(earCtx.destination);
      g.gain.setValueAtTime(0, t0 + at); g.gain.linearRampToValueAtTime(amp, t0 + at + 0.004);
      g.gain.exponentialRampToValueAtTime(0.0001, t0 + at + 0.3); o.start(t0 + at); o.stop(t0 + at + 0.32);
    }));
  } catch (e) { }
}
function setState(s) {
  if (state === "listening" && s === "idle" && S.sounds !== false) earcon("sleep");
  state = s;
  if (orb) orb.set({ state: s, level: s === "speaking" ? 0.3 : 0 });
  $("#state").textContent = holdTalk && s === "listening" ? (holdCancel ? "Отпустите — отменить" : "Говорите · отпустите — отправлю") : STATE_RU[s] || "";
  $("#state").classList.toggle("idle", s === "idle");
  const rb = $("#radiobox"); if (rb) rb.classList.toggle("talking", s !== "idle");   // подсказка про голос — только в покое
  triesCheck($("#stage").classList.contains("quiet"));                              // слушает или думает — примеры прячутся
  const m = $("#mic"); m.classList.toggle("on", s === "listening"); m.classList.toggle("busy", s === "thinking" || s === "speaking");
  D.keepScreen(s !== "idle" || !!(window.DewiarCall && DewiarCall.active()));     // идёт звонок «Близким» — экран не гаснет
  const duck = radio.on() && s !== "idle";        // пока слушаю и отвечаю — радио тише
  if (duck !== radioDucked) { radioDucked = duck; D.radioDuck(duck); }
  if (s === "idle") radio.resumeAfterTalk();
}
let radioDucked = false;
function toast(t, ms = 2200) { const el = $("#toast"); el.textContent = t; el.classList.add("on"); clearTimeout(el._t); el._t = setTimeout(() => el.classList.remove("on"), ms); }
/* Версия движка страниц (Android System WebView / Chrome): у части планшетов (Huawei без сервисов Google) он старый,
   и новое оформление может выглядеть иначе — в жалобе и пульсе видно, какой. -> " · WebView 99" или "" */
function webviewVer() { const m = /(?:Chrome|Chromium)\/(\d+)/.exec(navigator.userAgent || ""); return m ? " · WebView " + m[1] : ""; }
function showYou(t) { $("#you").textContent = t ? "«" + t + "»" : ""; quietCheck(); }
/* Длинный ответ (список, таблица, план) — в рамке: облик уменьшается, текст слева и мельче; когда ответ готов
   (frameAnswer) — разметка и кнопки «Копировать», «В заметки», «Скачать». Отзыв: длинный ответ налезал на облик и поле
   ввода, а сохранить его было нечем. */
const LONG_ANSWER = 160;
let turnMedia = null;                            // картинки этого ответа (show_images) — под ответом и в истории
let turnQ = "";                                 // вопрос этого хода: длинная страница (readPage) — куски по его словам
const isLongAnswer = (t) => String(t || "").length >= LONG_ANSWER || /\n\s*(?:[-*•]|\d+[.)])\s|\n\s*\||```/.test(String(t || "")) || !!(turnMedia && turnMedia.length);
function showBot(t, cls) {
  const b = $("#bot"), long = !cls && isLongAnswer(t);
  b.className = cls || (long ? "framed" : ""); b.textContent = t || "";
  $("#stage").classList.toggle("long", long);
  if (!long) $("#talk").scrollTop = 1e6;
  quietCheck();
}
function mdAnswer(t) {         // ответ модели → HTML: экранируем, затем заголовки, жирный, пункты, таблицы
  const lines = esc(String(t || "").trim()).split("\n"), out = [];
  let list = "", table = [];
  const inl = (x) => x.replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>").replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<i>$2</i>").replace(/`([^`]+)`/g, "<code>$1</code>");
  const flushList = () => { if (list) { out.push(`</${list}>`); list = ""; } };
  const flushTable = () => {
    if (!table.length) return;
    const rows = table.filter(r => !/^\|?\s*:?-{2,}/.test(r)).map(r => r.replace(/^\||\|$/g, "").split("|").map(c => inl(c.trim())));
    out.push(`<div class="tbl"><table>${rows.map((r, i) => `<tr>${r.map(c => i ? `<td>${c}</td>` : `<th>${c}</th>`).join("")}</tr>`).join("")}</table></div>`);
    table = [];
  };
  let code = null;                                   // внутри ``` … ``` — код или схема (```mermaid — рисует rich.js)
  for (const raw of lines) {
    const l = raw.trim(); let m;
    if (/^```/.test(l)) {
      if (code === null) { flushList(); flushTable(); code = { lang: l.slice(3).trim(), rows: [] }; }
      else { out.push(`<pre><code class="language-${code.lang.replace(/[^\w-]/g, "")}">${code.rows.join("\n")}</code></pre>`); code = null; }
      continue;
    }
    if (code !== null) { code.rows.push(raw); continue; }
    if (/^\|.*\|$/.test(l)) { flushList(); table.push(l); continue; }
    flushTable();
    if ((m = l.match(/^#{1,4}\s+(.*)$/))) { flushList(); out.push(`<h4>${inl(m[1])}</h4>`); }
    else if ((m = l.match(/^(?:[-*•])\s+(.*)$/))) { if (list !== "ul") { flushList(); out.push("<ul>"); list = "ul"; } out.push(`<li>${inl(m[1])}</li>`); }
    else if ((m = l.match(/^\d+[.)]\s+(.*)$/))) { if (list !== "ol") { flushList(); out.push("<ol>"); list = "ol"; } out.push(`<li>${inl(m[1])}</li>`); }
    else if (!l) flushList();
    else { flushList(); out.push(`<p>${inl(l)}</p>`); }
  }
  if (code !== null) out.push(`<pre><code>${code.rows.join("\n")}</code></pre>`);   // ответ оборвался внутри блока
  flushList(); flushTable();
  return out.join("");
}
function copyText(t) {
  if (D.copy && D.copy(t)) return Promise.resolve(true);
  return navigator.clipboard ? navigator.clipboard.writeText(t).then(() => true, () => false) : Promise.resolve(false);
}
function frameAnswer(t) {      // ответ готов: длинный — с разметкой и кнопками
  t = String(t || "").trim(); const b = $("#bot");
  if (!t || !isLongAnswer(t) || b.className && b.className !== "framed") return;
  b.className = "framed"; $("#stage").classList.add("long");
  b.innerHTML = `<div class="ans">${mdAnswer(t)}${turnMedia && window.DewiarRich ? DewiarRich.gallery(turnMedia) : ""}</div><div class="acts"><button data-a="copy">${ICON_COPY}Копировать</button><button data-a="note">${ICON_NOTE}В заметки</button><button data-a="save">${ICON_SAVE}Скачать</button></div>`;
  if (window.DewiarRich) DewiarRich.diagrams(b.querySelector(".ans"));   // ```mermaid — схемой
  wirePics(b);
  const title = t.replace(/[#*_`|]/g, "").split(/[.!?\n]/)[0].trim().slice(0, 60) || "Ответ";
  b.querySelector('[data-a="copy"]').onclick = () => copyText(t).then(ok => toast(ok ? "Скопировано" : "Не получилось скопировать"));
  b.querySelector('[data-a="note"]').onclick = () => { const n = notes(); n.push({ id: "n" + Date.now(), title, text: t, time: Date.now() }); saveNotes(n); toast(`В заметках: «${title}»`, 2800); };
  b.querySelector('[data-a="save"]').onclick = () => {
    const name = title.replace(/[\\/:*?"<>|]+/g, " ").trim().slice(0, 40) + ".md";
    const where = D.saveDownload ? D.saveDownload(name, "text/markdown", t) : "";
    toast(where ? `Сохранено: ${where}` : "Не получилось сохранить", 3500);
  };
  $("#talk").scrollTop = 0;
}
const ICON_COPY = `<svg viewBox="0 0 24 24"><rect x="8" y="8" width="12" height="12" rx="2.5"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/></svg>`;
const ICON_NOTE = `<svg viewBox="0 0 24 24"><path d="M6 3.5h9l4 4V20a.5.5 0 0 1-.5.5h-12A.5.5 0 0 1 6 20z"/><path d="M14.5 3.5V8H19M9 12.5h7M9 16h5"/></svg>`;
const ICON_SAVE = `<svg viewBox="0 0 24 24"><path d="M12 4v11M7.5 10.5 12 15l4.5-4.5M5 19.5h14"/></svg>`;
function showCard(html) { $("#card").innerHTML = html || ""; cardSticky = 0; quietCheck(); }
/* Снимок с камеры держится на экране 3 минуты: «покажи это фото мне» сразу после снимка не должно его стирать
   (раньше новая фраза очищала карточку, и человек слышал «вот», а видел пустой экран). Новая карточка — сменяет. */
let cardSticky = 0;
function showPhotoCard(url) { showCard(photoCard(url)); cardSticky = Date.now() + 180000; photoTurn = true; }
function clearCard() { if (Date.now() < cardSticky) return; showCard(""); }
let photoTurn = false;              // в этом ходе показан снимок — пометим в истории для модели
// на экране ничего не сказано и не показано — #stage.quiet: лёжа облик встаёт по центру (app.css)
function quietCheck() {
  const quiet = !$("#you").textContent && !$("#bot").textContent && !$("#bot").className && !$("#card").innerHTML;
  $("#stage").classList.toggle("quiet", quiet);
  if ($("#talk-x")) $("#talk-x").hidden = quiet || $("#bot").classList.contains("wait");   // пока отвечает — не убираем
  triesCheck(quiet);
}
/* «Попробуйте сказать» (отзыв 18.10: «сказал привет, ответили голосом, а что с ней делать дальше — ума не приложу»): пока
   человек новичок (сам спросил меньше 4 раз) и экран пуст — фразы-примеры, нажатие спрашивает. Кто пользовался раньше
   (есть разговор или память) — не показываем: S.tries заводится при первом запуске этой версии. */
const TRIES_MAX = 4;
function triesState() {
  if (!S.tries) S.tries = { n: history.some(m => m.role === "user") || (S.memory || []).length ? TRIES_MAX : 0, off: false };
  return S.tries;
}
function triesList() {
  return ["Что ты умеешь?", "Включи радио", "Погода на завтра", D.web ? "Что нового в мире?" : "Посвети фонариком",
    "Напомни через час позвонить маме", "Запиши: купить хлеб"];
}
function triesCheck(quiet) {
  const box = $("#tries"); if (!box) return;
  const t = triesState(), brain = !!(S.llm.base_url || loggedIn());
  const show = quiet && brain && !t.off && t.n < TRIES_MAX && state === "idle";
  if (show && !box.childElementCount) {
    box.innerHTML = `<p class="th">Попробуйте сказать — или нажмите</p><div class="tlist">${triesList().map(q => `<button class="tq" data-q="${esc(q)}">${esc(q)}</button>`).join("")}</div>`
      + `<button class="lnk tx" id="tries-x">Больше не показывать</button>`;
    box.querySelectorAll(".tq").forEach(b => b.onclick = () => ask(b.dataset.q));
    $("#tries-x").onclick = () => { triesState().off = true; saveS(); quietCheck(); };
  }
  box.hidden = !show;
  $("#stage").classList.toggle("tries", show);
}
/* Убрать сказанное с экрана: крестик или смахнуть вбок. Разговор не забывается — только экран (23.10). */
function talkDismiss(dx) {
  const t = $("#talk"); t.style.setProperty("--dx", (dx || 60) + "px"); t.classList.add("away");
  setTimeout(() => { $("#you").textContent = ""; $("#bot").textContent = ""; $("#bot").className = ""; cardSticky = 0; showCard("");
    $("#stage").classList.remove("long"); t.classList.remove("away"); t.scrollTop = 0; quietCheck(); }, RM.matches ? 0 : 220);
}
const RM = matchMedia("(prefers-reduced-motion: reduce)");

/* ---------- разрешения ---------- */
const permWait = {};
N.on("perm", e => { const w = permWait[e.name]; if (w) { delete permWait[e.name]; w(!!e.granted); } });
function needPerm(name) {
  if (D.has(name)) return Promise.resolve(true);
  return new Promise(res => { permWait[name] = res; D.perm(name); });
}

/* ---------- слух ----------
   Распознаёт телефон (SpeechRecognizer) или сервер (свой или Dewiar Облако — GigaAM по ключу или аккаунту, cloudEars).
   Сторож sttGuard: распознаватель телефона бывает «есть, но молчит» (планшеты без сервисов Google — Huawei и др.):
   не начал слушать за 4 с — переходим на сервер Dewiar насовсем (S.stt.auto) или честно говорим, что слуха нет;
   замолчал посреди (нет событий 15 с) или не отпускает после нажатия «стоп» — сами заканчиваем, кнопка не залипает. */
let sttActive = false, heardPartial = "", sttWatch = null, sttStarted = false, sttVia = "", sttGen = 0, sttOnce = null;
function sttGuard(ms, why) { clearTimeout(sttWatch); sttWatch = ms ? setTimeout(() => sttStall(why), ms) : null; }
/* Событие слуха из прежнего сеанса (поле g от Speech.java; после cancel ещё приходит «отменено») — не наше: иначе оно
   сбило бы новый сеанс, и кнопка осталась бы «слушаю». В браузере-заглушке поля g нет — принимаем всё. */
let sttT0 = 0;                     // когда начали слушать — в журнал идёт, за сколько пришёл текст
const clip = (t, n = 120) => { t = String(t || "").replace(/\s+/g, " ").trim(); return t.length > n ? t.slice(0, n) + "…" : t; };
const sttMine = (e) => e.g === undefined || e.g === sttGen;
/* Распознавание Dewiar Облака: вход аккаунтом или ключ dw- и в облаке есть распознавание -> {url, key} или null. */
function cloudEars() {
  if (loggedIn() && S.accCloud && S.accCloud.stt) return { url: S.accCloud.base.split("?")[0] + "?p=", key: S.account.token };
  if (S.llm.cloud && S.llm.stt) return { url: cloudBase() + "?p=", key: S.llm.api_key };
  return null;
}
/* Сервер не пустил слушать (402 — талеры или заряд закончились, 429 — дневной лимит, 401/403 — ключ) — раньше было
   «Не получилось услышать: сервер распознавания ответил 402», и всё. Теперь, если у телефона есть своё распознавание,
   слушает оно — 30 минут или до перезапуска приложения, потом снова пробуем сервер (вдруг пополнили). */
let sttSysUntil = 0;
/* Распознавание телефона (Google) — через интернет: на слабой мобильной сети (24.10, владелец: «не получилось услышать:
   нет сети для распознавания» через раз) оно обрывается, а сказанное пропадает. Теперь сбой сети — не ошибка на экране:
   есть распознавание Dewiar — эту фразу слушает сервер (он ждёт дольше), два сбоя за 10 минут — сервер слушает 10 минут;
   нет — один тихий повтор «скажите ещё раз». */
let sttNetUntil = 0, sttNetFails = [], sttNetRetryAt = 0;
const STT_NET = [1, 2];                             // SpeechRecognizer.ERROR_NETWORK_TIMEOUT, ERROR_NETWORK
const STT_DENIED = /ответил (40[1-3]|429)\b/;
function sttServerUrl(u) { return u.replace(/\/+$/, "") + (/(transcriptions)$/.test(u) ? "" : "/audio/transcriptions"); }
async function listen() {
  stopVoice();
  if (!(await needPerm(MIC))) { showBot("Без микрофона я вас не услышу. Разрешите микрофон — или напишите текстом.", "err"); return; }
  heardPartial = ""; sttUserStop = false; showYou(dict ? dict + " …" : ""); showBot(""); clearCard();
  setState("listening"); sttActive = true; sttStarted = false; if (!dict) D.vibrate(18);
  let server = S.stt.engine === "server" && S.stt.url ? { url: S.stt.url, key: S.stt.key || "", model: S.stt.model || "" } : null;
  if (!server && (!D.recognizer() || sttOnce)) { const c = sttOnce || cloudEars(); sttOnce = null; if (c) server = { url: c.url, key: c.key, model: "gigaam" }; }
  if (!server && Date.now() < sttNetUntil) { const c = cloudEars(); if (c) server = { url: c.url, key: c.key, model: "gigaam" }; }   // сеть Google сбоит — сервер
  if (server && Date.now() < sttSysUntil && D.recognizer()) server = null;     // сервер не пускает (талеры) — слушает телефон
  if (!server && !D.recognizer()) {
    sttActive = false; setState("idle");
    showBot("В этом устройстве нет распознавания речи. Войдите аккаунтом dewiar.pro (Настройки → Мозг) — слушать будет сервер Dewiar. Или напишите текстом.", "err"); return;
  }
  sttVia = server ? "server" : "system"; sttT0 = Date.now();
  plog("info", "слушаю: " + (server ? "сервер " + server.url.replace(/\?.*$/, "") : "распознавание телефона"));
  sttGen++;
  if (server && holdTalk && D.listenServerHold) D.listenServerHold(sttGen, sttServerUrl(server.url), server.key, server.model);   // держат — пишем всё до «отпустили»
  else if (server) D.listenServer(sttGen, sttServerUrl(server.url), server.key, server.model);
  else if (holdTalk && D.listenHold) D.listenHold(sttGen);     // держат кнопку — пауза конца фразы подольше, реже перезапуск
  else D.listen(sttGen);
  sttGuard(server ? 20000 : 4000, "start");
}
/* Длинная диктовка: распознаватель телефона сам заканчивает примерно через минуту, запись для сервера — через 15 с.
   Оборвалось на лимите, а не на паузе, — копим сказанное в dict и тихо слушаем дальше; всё вместе уходит, когда человек
   замолчит по-настоящему (или следующий отрезок окажется пустым). */
let dict = "", sttUserStop = false;
/* «Удерживайте и говорите» (как голосовое в Telegram, отзыв 13.10): пока палец на кнопке, слушаем сколько угодно —
   паузы, обрывы распознавателя и тишина не заканчивают запись, сказанное копится в dict; отпустили — всё уходит
   помощнику; увели палец далеко от кнопки — «отпустите — отменить». Обычное нажатие — как раньше. */
var holdTalk = false, holdCancel = false;
function dictMore(t, cut) {
  if (holdTalk) {                                     // держат кнопку — копим и слушаем дальше, что бы ни было
    if (t) dict = (dict ? dict + " " : "") + t;
    showYou(dict ? dict + " …" : "…"); setTimeout(() => { if (holdTalk) listen(); }, 60);
    return true;
  }
  const dur = Date.now() - sttT0, user = sttUserStop; sttUserStop = false;
  if (user || !t || !(cut || (sttVia === "system" && dur >= 45000)) || dict.length > 12000) return false;
  dict = (dict ? dict + " " : "") + t;
  plog("info", `длинная диктовка: ${dict.length} зн., слушаю дальше`);
  showYou(dict + " …"); setTimeout(() => listen(), 60);
  return true;
}
/* Сказанное голосом — с тем, что прикреплено в поле ввода (фото, файл): прикрепили скриншот и сказали «сохрани в
   заметки …» — он уходит вместе с фразой и попадает в заметку (отзыв 11.10: фото так и висело над полем). */
function askHeard(t) { const att = attached; attached = []; renderAtts(); return ask(t, att.length ? { attach: att } : {}); }
const dictTake = (t) => { const all = ((dict ? dict + " " : "") + (t || "")).trim(); dict = ""; return all; };
function sttStall(why) {
  if (!sttActive) return;
  sttActive = false; D.cancelListen(); sttGen++;
  plog("warn", "распознавание: нет ответа (" + why + ", " + sttVia + ")");
  if (why === "start" && sttVia === "system" && !sttStarted) {
    const c = Date.now() < sttSysUntil ? null : cloudEars();     // сервер сейчас не пускает — не ходим по кругу
    if (c) {
      // Первый раз — только этот вопрос слушает сервер (распознаватель мог просто долго подключаться к сети);
      // второй раз подряд — насовсем. Заработал сам — счётчик сбрасывается (sttAlive).
      S.stt.sysFails = (S.stt.sysFails || 0) + 1;
      if (S.stt.sysFails >= 2) {
        S.stt = { engine: "server", url: c.url, key: c.key, model: "gigaam", from_account: loggedIn(), auto: true };
        toast("Распознавание этого устройства не отвечает — слушает сервер Dewiar", 4500);
      } else sttOnce = c;
      saveS();
      return listen();
    }
    setState("idle"); showYou("");
    showBot("Распознавание речи этого устройства не отвечает. Войдите аккаунтом dewiar.pro (Настройки → Мозг) — слушать будет сервер Dewiar. Или напишите текстом.", "err");
    return;
  }
  if (holdTalk) { dictMore(heardPartial, true); return; }
  if (heardPartial || dict) { if (dictMore(heardPartial, false)) return; askHeard(dictTake(heardPartial)); return; }
  setState("idle"); showYou("");
}
const sttAlive = () => { sttStarted = true; sttRetry = 0; if (sttVia === "system" && S.stt.sysFails) { S.stt.sysFails = 0; saveS(); } if (sttActive) sttGuard(15000, "silent"); };
N.on("stt_start", e => { if (sttMine(e)) sttAlive(); });
N.on("stt_end", e => {
  if (!sttMine(e) || !sttActive) return;
  sttGuard(sttVia === "server" ? 60000 : 8000, "end");          // запись уходит на сервер — при слабом интернете это не мгновенно
  if (sttVia === "server" && !String($("#you").textContent || "").trim()) showYou("распознаю…");
});
N.on("stt_level", e => { if (!sttMine(e)) return; if (orb && state === "listening") orb.set({ level: e.v }); if (!sttStarted) sttAlive(); });
N.on("stt_partial", e => { if (!sttMine(e)) return; heardPartial = e.text; showYou((dict ? dict + " " : "") + e.text); sttAlive(); });
N.on("stt_result", e => {
  if (!sttMine(e)) return;
  sttGuard(0);
  if (!sttActive) return; sttActive = false;
  let t = (e.text || heardPartial || "").trim();
  plog("info", `📝 ${t ? clip(t) : "(пусто)"} (${sttVia === "server" ? "сервер" : "телефон"}, ${((Date.now() - sttT0) / 1000).toFixed(1)} с)`);
  vCount((t ? "stt_ok_" : "stt_none_") + (sttVia === "server" ? "srv" : "sys")); sttRetry = 0;
  if (dictMore(t, !!e.cut)) return;
  t = dictTake(t);
  if (t && pausePrefix && Date.now() - pausePrefix.at < 30000) t = pausePrefix.text + " " + t;   // договорил после обрыва — один вопрос
  pausePrefix = null;
  if (t) { lastStt = { at: Date.now(), text: t, cut: false }; askHeard(t); } else { setState("idle"); showYou(""); }
});
let sttRetry = 0;
N.on("stt_error", e => {
  if (!sttMine(e)) return;
  sttGuard(0);
  if (!sttActive) return; sttActive = false;
  vCount(e.code === 11 ? "stt_e11" : [6, 7].includes(e.code) ? "stt_none_" + (sttVia === "server" ? "srv" : "sys") : "stt_err_" + (sttVia === "server" ? "srv" : "sys"));
  // 11 — распознаватель ещё отключается от прошлого раза, 8 — занят (Samsung и др. сразу после ответа, отчёт №14): это не
  // поломка — через полсекунды он слушает. Раньше уходили на запись для сервера, та писала «речи не было», человек не
  // понимал, что случилось. Теперь — тихо пробуем ещё раз (до двух раз), и только потом — сервер.
  if (holdTalk && [6, 7, 11, 8].includes(e.code)) { dictMore(heardPartial, true); return; }   // держат кнопку — тишина не конец
  if (sttVia === "system" && !sttStarted && [11, 8].includes(e.code) && sttRetry < 2) {
    sttRetry++; plog("info", `распознавание телефона ещё занято (${e.code}) — пробую снова`);
    setTimeout(() => { if (state === "listening") listen(); }, 450 * sttRetry); return;
  }
  sttRetry = 0;
  if (sttVia === "system" && e.code === 13) {          // браузер: своего распознавания на деле нет (веб-версия, webbridge.js)
    plog("warn", "распознавание браузера недоступно: " + (e.msg || ""));
    const c = Date.now() < sttSysUntil ? null : cloudEars();
    if (c) { S.stt = { engine: "server", url: c.url, key: c.key, model: "gigaam", from_account: loggedIn(), auto: true }; saveS();
      toast("В этом браузере своего распознавания нет — слушает сервер Dewiar", 4500); setState("idle"); return listen(); }
    setState("idle"); showYou("");
    showBot("В этом браузере распознавание речи не работает (так у Chrome и Chromium на Linux, у Firefox). Войдите аккаунтом dewiar.pro или подключите Dewiar Облако в «Мозге» — слушать будет сервер Dewiar. Или откройте в Edge, Яндекс Браузере, Safari. Пока можно писать текстом.", "err");
    return;
  }
  plog([6, 7, 5].includes(e.code) ? "info" : "warn", `распознавание (${sttVia}): ${e.code === 6 ? "речи не было" + (/громкость/.test(e.msg || "") ? " — " + String(e.msg).replace(/^[^(]*/, "") : "") : e.code === 7 ? "не расслышал" : "ошибка " + (e.code ?? "") + " " + (e.msg || "")}`);
  // распознаватель телефона сломался, не начав слушать (не запустился, нет сервиса, сеть) — слушает сервер Dewiar
  if (sttVia === "system" && !sttStarted && ![6, 7].includes(e.code) && cloudEars() && Date.now() >= sttSysUntil) { sttActive = true; sttStall("start"); return; }
  // сервер не пустил (кончились талеры, лимит, ключ) — слушает сам телефон; сказанное пропало, просим повторить
  if (sttVia === "server" && STT_DENIED.test(String(e.msg || ""))) {
    const why = String(e.msg).replace(/^[^:]*:?\s*/, "").trim();
    vCount("stt_denied"); plog("warn", "распознавание: сервер не пустил — " + clip(e.msg, 160));
    if (D.recognizer()) {
      sttSysUntil = Date.now() + 30 * 60e3; setState("idle"); showYou("");
      // сразу слушаем снова — уже телефоном; объяснение — всплывающей строкой (listen очищает ответ на экране)
      toast(`${/талер|заряд|счёт|счет|закончил/i.test(why) ? "ИИ-талеры на распознавание закончились" : "Сервер распознавания сейчас не пускает"} — `
        + "слушает сам телефон. Скажите ещё раз.", 6000);
      setTimeout(() => { if (state === "idle" && !busy) listen(); }, 700);
      return;
    }
    setState("idle"); showYou("");
    showBot((why || "Сервер распознавания не пускает.") + " Своего распознавания у этого телефона нет — напишите текстом.", "err");
    return;
  }
  if (sttVia === "system" && STT_NET.includes(e.code) && !heardPartial && !dict) {
    const now = Date.now(); sttNetFails = sttNetFails.filter(t => now - t < 600e3).concat(now); vCount("stt_net");
    const c = Date.now() < sttSysUntil ? null : cloudEars();
    if (c) {
      if (sttNetFails.length >= 2) { sttNetUntil = now + 600e3; plog("warn", "распознавание телефона: сеть сбоит — 10 минут слушает сервер Dewiar"); }
      else sttOnce = c;
      toast("Распознавание телефона потеряло сеть — слушает сервер Dewiar. Скажите ещё раз.", 4000);
      setState("idle"); showYou(""); setTimeout(() => { if (state === "idle" && !busy) listen(); }, 500);
      return;
    }
    if (now - sttNetRetryAt > 120e3) {
      sttNetRetryAt = now; toast("Связь моргнула — скажите ещё раз.", 3500);
      setState("idle"); showYou(""); setTimeout(() => { if (state === "idle" && !busy) listen(); }, 500);
      return;
    }
  }
  if (heardPartial || dict) { if (dictMore(heardPartial, false)) return; askHeard(dictTake(heardPartial)); return; }
  setState("idle"); showYou("");
  // молча (коды SpeechRecognizer, Speech.java): 6 — речи не было, 7 — не расслышал, 5 — отменено, 11 — распознаватель отключился
  if (![6, 7, 5, 11].includes(e.code)) showBot("Не получилось услышать: " + (e.msg || e.code) + (STT_NET.includes(e.code) ? ". Связь слабая — скажите ещё раз или напишите." : ""), "err");
});
function stopListen() { sttGuard(0); sttGen++; dict = ""; if (sttActive) { sttActive = false; D.cancelListen(); } }

/* ---------- голос: фразы по очереди (Tts.java) — голос телефона или сервера (/v1/audio/speech) ----------
   sayLeft — сколько фраз ещё не отзвучало: tts_done приходит на каждую (и при ошибке), на нуле ход заканчивается. */
let sayN = 0, sayLeft = 0, voiceWarned = false, afterSpeak = null;
/* Голос сервера не ответил (служба голосов выключена, сервер недоступен) — фраза звучит голосом телефона, и следующие две
   минуты тоже: не ждём отказа на каждой фразе. sayTexts — текст фраз, ушедших на сервер, чтобы было что повторить. */
let srvVoiceDownAt = 0, srvVoiceWarnAt = 0;
const sayTexts = new Map();
const EMOJI = (() => { try { return new RegExp("\\p{Extended_Pictographic}", "gu"); } catch (e) { return /[\u2600-\u27BF]|[\uD83C-\uDBFF][\uDC00-\uDFFF]/g; } })();
/* Текст для голоса — как speakable в core/llm.py: без кода, ссылок, путей к файлам и расширений; сокращения — словами */
const FILE_EXT = "(?:html?|pdf|pptx?|docx?|xlsx?|csv|json|md|txt|py|js|css|zip|png|jpe?g|svg|mp3|wav|mp4)";
const SPEAK_RULES = [[/(?:https?:\/\/|www\.)\S+/gi, ""],
  [new RegExp("(^|[^\\wА-Яа-яЁё.])(?:[~/]?[\\wА-Яа-яЁё.-]+/)+[\\wА-Яа-яЁё-]+\\." + FILE_EXT + "(?![\\w])", "gi"), "$1"],
  [/(^|[^\w.])(?:\/?[A-Za-z0-9_.~-]+\/){2,}[A-Za-z0-9_.-]*/g, "$1"],
  [new RegExp("([\\wА-Яа-яЁё-]+)\\." + FILE_EXT + "(?![\\w])", "gi"), "$1"],
  [/(^|\s)в т\.\s?ч\./gi, "$1в том числе"], [/(^|\s)т\.\s?е\./gi, "$1то есть"], [/(^|\s)и т\.\s?д\./gi, "$1и так далее"],
  [/(^|\s)и т\.\s?п\./gi, "$1и тому подобное"], [/(^|\s)т\.\s?к\./gi, "$1так как"], [/(^|\s)напр\./gi, "$1например"],
  [/:\s*[—–-]\s+/g, ": "], [/\s+(?:и|или|в|на|по|из)\s*(?=[.,;:!?]|$)/g, ""], [/\s+([:,;—–-])\s*(?=[:,;.!?—–]|$)/g, ""], [/\(\s*\)/g, ""]];
function speechText(t) {
  t = t.replace(/```[\s\S]*?```/g, " ");
  for (const [rx, to] of SPEAK_RULES) t = t.replace(rx, to);
  return t.replace(/[*_#>`|~]+/g, " ").replace(EMOJI, "").replace(/\s+/g, " ").trim();
}
/* <option> голосов устройства для выбора в настройках; пометка «муж.» / «жен.», если пол известен */
function voiceOpts(voices, cur) {
  return voices.map(v => { const m = voiceIsMale(v);
    return `<option value="${esc(v.name)}" ${v.name === cur ? "selected" : ""}>${esc(v.name.replace(/^ru-ru-x-|-local|-network/g, ""))}${m === true ? " · муж." : m === false ? " · жен." : ""}${v.offline ? "" : " · сеть"}</option>`; }).join("");
}
/* Голос Dewiar Облака (озвучка по аккаунту или ключу dw-, если она включена в облаке): {url, key} или null.
   Говорит, когда выбран («Голос Dewiar») или когда в устройстве нет русского голоса. Голос — свой у каждого персонажа. */
function cloudVoice() {
  if (loggedIn() && S.accCloud && S.accCloud.tts) return { url: S.accCloud.base.split("?")[0] + "?p=", key: S.account.token };
  if (S.llm.cloud && S.llm.tts) return { url: cloudBase() + "?p=", key: S.llm.api_key };
  return null;
}
/* Голос устройства для героя или героини. Выбран в настройках — он. Иначе подбираем сами: признак пола у голоса (у части
   движков он есть) или голоса Google по имени (ru-ru-x-rud/ruf — мужские, ruc/rue — женские). -> {name, pitch}: нашёлся
   голос нужного пола — без подстройки высоты; нет — один голос на всех, героям чуть ниже, героиням чуть выше (как раньше). */
const EL_VOICES = { f: "EXAVITQu4vr4xnSDxMaL", m: "JBFqnCBsd6RMkjVDRZzb" };   // ElevenLabs по умолчанию: Sarah и George
let voicesCache = null;
function deviceVoices() {
  if (!voicesCache) { try { voicesCache = JSON.parse(D.voices() || "[]"); } catch (e) { voicesCache = []; } }
  return voicesCache;
}
function voiceIsMale(v) {
  const f = (v.features || []).map(x => String(x).toLowerCase());
  if (f.includes("male")) return true;
  if (f.includes("female")) return false;
  if (/-x-ru[df]-/i.test(v.name)) return true;
  if (/-x-ru[ce]-/i.test(v.name)) return false;
  return null;
}
function sysVoiceFor(gender) {
  const male = gender !== "female";
  const own = male ? S.tts.sys_voice_m : S.tts.sys_voice;
  if (own) return { name: own, pitch: 1.0 };
  const vs = deviceVoices(), pick = (want) => (vs.find(v => voiceIsMale(v) === want && v.offline) || vs.find(v => voiceIsMale(v) === want));
  if (male) { const v = pick(true); if (v) return { name: v.name, pitch: 1.0 }; }
  else if (!S.tts.sys_voice) { const v = pick(false); if (v) return { name: v.name, pitch: 1.0 }; }
  return { name: S.tts.sys_voice || "", pitch: male ? 0.92 : 1.12 };
}
let volWarned = false, volMuted = "", volMutedAt = 0;
function volCard() {
  if (!volMuted || $("#vol-up")) return;
  showCard(`<div class="start"><button class="btn p w" id="vol-up">🔊 Звук на нуле — включить и прочитать ответ</button></div>`);
  $("#vol-up").onclick = () => {
    try { D.volume("set", 50); } catch (e) { }
    const t = volMuted; volMuted = ""; volWarned = false; showCard("");
    if (t) say(t);
  };
}
function say(text, retry = 0) {
  const t = speechText(text); if (!t) return;
  if (S.textMode) { vCount("tts_text"); return; }            // текстовый режим — ответ только на экране
  if (!D.mock) {                                              // звук на нуле — голос всё равно не услышат: не синтезируем
    let v = -1; try { v = D.volume("get", 0); } catch (e) { }   // (сервер голосов не тратится впустую — идея 15.10), ответ на экране
    if (v === 0 && retry < 6 && Date.now() - sttT0 < 120000) {
      // только что слушали: распознаватель телефона на время записи сам глушит звук и возвращает его не сразу —
      // «Звук на нуле» выскакивал зря (20.10, отзыв владельца: «ложно выскочило, следующее аудио — исчезло»). Ждём ~2 с.
      setTimeout(() => say(text, retry + 1), 350); return;
    }
    if (v === 0) {
      vCount("tts_vol0");
      // звук на нуле (у 30 телефонов из 178, пакет 20.10): тихий тост проглядывали — ответы «пропадали». Теперь — кнопка на
      // экране: прибавить громкость и прочитать этот ответ вслух
      if (Date.now() - volMutedAt > 60000) volMuted = "";
      volMuted = (volMuted + " " + t).trim().slice(-1500); volMutedAt = Date.now();
      if (!volWarned) { volWarned = true; plog("warn", "голос: громкость звука на нуле — отвечаю текстом"); }
      setTimeout(volCard, 0);
      return;
    }
    volWarned = false;                                        // прибавили — в следующий раз снова подскажем
    if (volMuted) { volMuted = ""; if ($("#vol-up")) showCard(""); }     // и кнопка «включить звук» больше не нужна
  }
  const id = "s" + (++sayN); sayLeft++;
  turnTime("said");
  const cv = (S.tts.engine === "cloud" || (S.tts.engine === "system" && !D.ttsReady())) ? cloudVoice() : null;
  const srvDown = Date.now() - srvVoiceDownAt < 120e3 && D.ttsReady();   // голос сервера только что не ответил — пока свой
  const fem = persona().gender === "female";
  if (S.tts.engine === "eleven" && S.tts.el_key) {           // ElevenLabs своим ключом: голос героя или героини
    const vid = (fem ? S.tts.el_voice_f : S.tts.el_voice_m) || EL_VOICES[fem ? "f" : "m"];
    D.speakRemote(id, `https://api.elevenlabs.io/v1/text-to-speech/${encodeURIComponent(vid)}?output_format=mp3_44100_128`, "xi-api-key:" + S.tts.el_key,
      JSON.stringify({ text: t, model_id: S.tts.el_model || "eleven_flash_v2_5", voice_settings: { speed: Math.max(0.7, Math.min(1.2, +S.tts.rate || 1)) } }));
  } else if (!srvDown && ((S.tts.engine === "server" && S.tts.url) || cv)) {
    sayTexts.set(id, t);
    // голосу сервера — уже словами: «14:10» → «четырнадцать десять» (ui/assets/speechnorm.js, как core/speechnorm.py);
    // старая служба голосов читала цифры странно («ствисе», отзыв 16.10), а новая сделает это сама — дважды не мешает
    const said = window.DewiarSpeech ? (DewiarSpeech.norm(t, false) || t) : t;
    const u = cv ? cv.url : S.tts.url, url = u.replace(/\/+$/, "") + (/speech$/.test(u) ? "" : "/audio/speech");
    const body = cv ? { model: "tts-1", input: said, voice: persona().voice_remote || (persona().gender === "female" ? "serena" : "aiden"), persona: persona().id || "", response_format: "wav", speed: +S.tts.rate || 1 }
      : { model: S.tts.model || "tts-1", input: said, voice: (fem ? S.tts.voice : (S.tts.voice_m || S.tts.voice)) || "alloy", persona: persona().id || "", response_format: "mp3" };
    const sv0 = sysVoiceFor(persona().gender);
    if (D.speakRemoteFb && D.ttsReady())     // запасной голос — в той же очереди, по порядку (отчёт №93: два голоса разом)
      D.speakRemoteFb(id, url, cv ? cv.key : (S.tts.key || ""), JSON.stringify(body), JSON.stringify({ text: t, rate: +S.tts.rate || 1.0, pitch: sv0.pitch, voice: sv0.name || "" }));
    else D.speakRemote(id, url, cv ? cv.key : (S.tts.key || ""), JSON.stringify(body));
  } else if (srvDown && sayTexts.size && D.speakRemoteFb) {
    // сервер голоса только что подвёл, а его фразы ещё звучат — эту голосом телефона, но в той же очереди, после них
    sayLeft++;                                               // придут два «готово»: запасной фразы и самой
    const sv = sysVoiceFor(persona().gender);
    D.speakRemoteFb(id, "", "", "", JSON.stringify({ text: t, rate: +S.tts.rate || 1.0, pitch: sv.pitch, voice: sv.name || "" }));
  } else {
    if (!D.ttsReady()) {
      sayLeft--; vCount("tts_none");
      if (!voiceWarned && !D.mock) { voiceWarned = true; plog("warn", "голоса нет: в устройстве нет русского синтеза речи, озвучка облака " + (cloudVoice() ? "есть, но не выбрана" : "не включена") + " — отвечаю текстом"); toast("В устройстве нет русского голоса — отвечаю текстом. Как включить голос — Настройки → Слух и голос.", 6000); }
      return;
    }
    const sv = sysVoiceFor(persona().gender);                 // героям — мужской голос устройства, героиням — женский
    D.speak(id, t, S.tts.rate || 1.0, sv.pitch, sv.name, true);
  }
  if (state !== "speaking" && state !== "listening") setState("speaking");
}
// какие фразы звучат прямо сейчас: облик «говорит» губами только под звук. Голос с сервера приходит через секунды после
// начала ответа — до tts_start и в паузах между фразами рот закрыт (отзыв 14.10: «звука нет, а они болтают губами»)
const playingIds = new Set();
const soundOn = () => { if (orb) orb.set({ audible: playingIds.size > 0 }); };
N.on("tts_start", e => { vCount("tts_ok"); playingIds.add((e && e.id) || "?"); soundOn(); turnTime("sound"); if (state === "thinking") setState("speaking"); });
N.on("tts_fail", e => { vCount("tts_err"); plog("warn", "голос устройства не сказал фразу (код " + (e.code ?? "?") + ")"); });
N.on("tts_done", e => {
  if (e && e.id) sayTexts.delete(e.id);
  playingIds.delete((e && e.id) || "?"); soundOn();
  sayLeft = Math.max(0, sayLeft - 1);
  if (sayLeft === 0 && state === "speaking" && !busy) finishTurn();
});
N.on("tts_error", e => {
  vCount("tts_err"); plog("warn", "голос сервера: " + e.error);
  const t = sayTexts.get(e.id); sayTexts.delete(e.id);
  if (t && D.ttsReady()) {                                   // эта фраза — голосом телефона, а не тишина
    srvVoiceDownAt = Date.now(); sayLeft++;
    if (!e.fallback) {                                       // старое приложение: запасной голос говорим сами
      const sv = sysVoiceFor(persona().gender);
      D.speak("f" + e.id, t, S.tts.rate || 1.0, sv.pitch, sv.name, true);
    }
    if (Date.now() - srvVoiceWarnAt > 600e3) { srvVoiceWarnAt = Date.now(); toast("Голос сервера сейчас недоступен — говорю голосом телефона", 5000); }
  } else if (t) toast("Голос сервера: " + e.error);      // своего голоса нет — честно говорим, почему тихо
});
function stopVoice() { sayLeft = 0; D.stopSpeak(); playingIds.clear(); soundOn(); }
function finishTurn() {
  setState("idle");
  const f = afterSpeak; afterSpeak = null;
  if (f) f();
}

/* ---------- мозг: модель с инструментами ---------- */
let busy = false, turnAbort = null, lastDone = "";
const CUR = (() => { const tz = (Intl.DateTimeFormat().resolvedOptions().timeZone || ""); return /Minsk/.test(tz) ? "BYN" : /Kiev|Kyiv/.test(tz) ? "UAH" : /Almaty|Astana/.test(tz) ? "KZT" : "RUB"; })();
const WD = ["воскресенье", "понедельник", "вторник", "среда", "четверг", "пятница", "суббота"];
const MON = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"];
const pad = (n) => String(n).padStart(2, "0");
const isoLocal = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
function nowText() { const d = new Date(); return `${WD[d.getDay()]}, ${d.getDate()} ${MON[d.getMonth()]} ${d.getFullYear()} года, ${pad(d.getHours())}:${pad(d.getMinutes())} (${isoLocal(d)})`; }

/* Род речи: у героинь быстрые ответы без модели («Включил: свет») — в женском роде. Правила — те же, что на компьютере (core/gender.py; слова — window.DEWIAR_FEM из personas_json.py).
   Меняем слово, только если перед ним начало фразы, «я», «уже», «сейчас», «хорошо,» и т. п. — иначе это не о себе. */
const FEM_LEAD = /(?:^|[.!?…:—–]\s*|(?:^|[^А-ЯЁа-яёA-Za-z0-9_])[Яя]\s+(?:уже\s+)?|(?:^|[^А-ЯЁа-яёA-Za-z0-9_])уже\s+|(?:^|[^А-ЯЁа-яёA-Za-z0-9_])[Сс]ейчас\s+|(?:^|[^А-ЯЁа-яёA-Za-z0-9_])[Яя]\s+[^.!?…]{0,30}?\s(?:и|а|но)\s+|(?:^|[^А-ЯЁа-яёA-Za-z0-9_])[Яя]\s+(?:очень|так|тоже|просто|правда|всегда|бы|сам|уже\s+не)\s+|(?:^|[.!?…,]\s*)(?:очень|так|тоже|просто|правда|искренне|ужасно|страшно)\s+|(?:^|[^А-ЯЁа-яёA-Za-z0-9_])(?:хорошо|готово|ладно|ок|окей|да|так|сейчас|секунду|итак|отлично|прекрасно|здорово|супер|класс|замечательно|чудесно|конечно|ага|ну|ой|о|понятно|ясно|спасибо|привет|здравствуй(?:те)?),\s*)(?:не\s+)?$/i;
function feminine(t) {
  const FEM = window.DEWIAR_FEM || {};
  if (!t) return t;
  return String(t).replace(/[А-ЯЁа-яё]+/g, (w, i, all) => {
    if (i > 0 && /[A-Za-z0-9_-]/.test(all[i - 1])) return w;
    const f = FEM[w.toLowerCase()]; if (!f || /[A-Za-z0-9_-]/.test(all[i + w.length] || "")) return w;
    if (!FEM_LEAD.test(all.slice(Math.max(0, i - 40), i))) return w;
    return w[0] !== w[0].toLowerCase() ? f[0].toUpperCase() + f.slice(1) : f;
  });
}
const gfix = (t) => persona().gender === "female" ? feminine(t) : t;

/* «Ваши данные» (privacy.js — общий текст со студией): факты для вопросов о конфиденциальности и как устроено у этого
   человека — где думает модель, включена ли синхронизация (как core/privacy.py) */
function privacyWhere() {
  const u = llmBase(); if (!u) return "модель ещё не подключена";
  let h = ""; try { h = new URL(/:\/\//.test(u) ? u : "http://" + u).hostname.toLowerCase(); } catch (e) { }
  if (S.llm.cloud || /dewiar/.test(h)) return "в облаке Dewiar (наши серверы; текст разговоров не сохраняется)";
  if (/^(localhost|127\.|10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.)|\.local$/.test(h)) return "на компьютере или сервере пользователя — разговор никуда не уходит";
  return `во внешнем сервисе ${h} по ключу пользователя — вопросы уходят туда`;
}
function privacyRule() {
  const P = window.DEWIAR_PRIVACY; if (!P) return "";
  return "ДАННЫЕ И КОНФИДЕНЦИАЛЬНОСТЬ. Спросят, где хранятся данные, кто видит разговоры, как защищены персональные данные, — ответь спокойно и по сути, своими словами, в 2–4 предложениях, из этих фактов: "
    + P.items.map(([t, x]) => `${t}: ${x}`).join(" ") + ` Сейчас у этого пользователя ты думаешь ${privacyWhere()}; синхронизация ${S.sync.on && syncCred() ? "включена" : "выключена"}.`
    + " Подробно — в настройках («Ещё» → «Ваши данные»). Не выдумывай того, чего здесь нет: сертификатов, законов, сроков хранения.";
}
/* Веб-версия (браузер на iPhone, Mac, любом компьютере): чего браузер не умеет — инструментов у модели нет (WEB_NO_TOOLS),
   и она честно говорит, где это есть, а не «звоню» в пустоту. */
const WEB_NO_TOOLS = new Set(["call", "send_sms", "open_app", "calendar_list", "calendar_add", "flashlight", "set_volume", "battery", "send_message", "phone_settings"]);
/* Экраны настроек телефона (Bridge.openSettings): «включи Bluetooth» — сразу нужный экран, а не поиск по настройкам пальцем
   (отзыв 19.10, Android 13: «попросил включить блютуз, а она на вкладку вайфай переходит») */
const PHONE_SET = { bluetooth: "Bluetooth", wifi: "Wi‑Fi", internet: "Интернет", nfc: "NFC", airplane: "Режим полёта", display: "Экран и яркость",
  sound: "Звук", data: "Мобильная сеть", hotspot: "Точка доступа и сети", location: "Местоположение" };
const WEB_DEVICE_RULE = "Ты работаешь в браузере пользователя (веб-версия Dewiar — iPhone, Mac или любой компьютер). Напоминания и будильники "
  + "здесь срабатывают, пока страница Dewiar открыта (уведомлением и звуком). Звонить, отправлять SMS и сообщения в мессенджерах, открывать "
  + "приложения, включать фонарик, менять громкость и смотреть календарь телефона браузер не умеет — на такую просьбу честно скажи об этом "
  + "одной фразой и подскажи, что это умеет приложение Dewiar для Android и программа для компьютера; не делай вид, что сделал. ";
/* Настройки в браузере: карточки, которые есть только у Android (звук будильника, кнопка помощника, «руки», значок
   на рабочем столе, точные будильники, контакты), — прячем после отрисовки (элементы остаются: обработчики не ломаются). */
const WEB_HIDE_CARDS = /^(Звук напоминаний|Кнопка помощника|Управлять приложениями|Значок «Записать»|Умный дом Яндекса)$/;
function webTrimSettings() {
  const hide = (el) => { if (el) el.style.display = "none"; };
  $$("#set-body h3").forEach(h => { if (WEB_HIDE_CARDS.test(h.textContent.trim())) { hide(h); hide(h.nextElementSibling); } });
  const bt = $("#bt-mic"); if (bt) hide(bt.closest(".sw"));
  const tilt = $("#ap-tilt"); if (tilt) hide(tilt.closest(".sw"));          // наклон телефона браузер без отдельного разрешения не отдаёт
  $$("#set-body .sw").forEach(r => { if (/^(Контакты|Звонки без|Точные будильники)/.test((r.firstElementChild || r).textContent.trim())) hide(r); });
  hide($("#upd-check"));
}
function systemPrompt() {
  const p = persona(), others = PERSONAS.filter(x => x.id !== p.id).map(x => `${x.name} — ${(x.role || "").toLowerCase()}`).join("; ");
  const parts = [p.character, window.DEWIAR_TALK_RULES || "", (window.DEWIAR_GENDER_RULES || {})[p.gender] || "", p.focus, window.DEWIAR_VOICE_RULES || "Отвечай коротко, живой речью, по-русски.",
    `Ты — один из команды помощников: ${others}. Позвать коллегу — инструмент call_persona. Разговор пользователя с коллегой приходит тебе справкой «[До этого пользователь говорил не с тобой…]»: это их разговор — не продолжай его и не отвечай за коллегу, пока пользователь сам об этом не попросит; отвечай на то, что он говорит тебе.`,
    (D.web ? WEB_DEVICE_RULE : "Ты работаешь на телефоне пользователя (Android). ") + "СЛОВА НЕ ДЕЙСТВУЮТ: «включаю», «звоню», «отправила», «ставлю» ничего не делают — "
    + "делает только вызов инструмента. Просят действие снова — вызывай инструмент снова, каждый раз; не копируй свой прошлый ответ из разговора. "
    + "Когда просят что-то сделать — вызывай инструмент, а не объясняй, как это сделать: "
    + "напоминания, будильники и таймеры (set_reminder; когда — словами пользователя в when, время посчитает телефон)" + (D.web ? ", " : ", звонки (call), SMS (send_sms — откроется сообщение, отправит пользователь), ")
    + "радио прямо здесь, в приложении (play_radio, radio_control — на любую просьбу про радио или «включи музыку», не сайты и не приложения; просят ПОДОБРАТЬ или посоветовать песни, плейлист — назови конкретные известные песни списком в ответе, радио сам не включай, если не просили включить), "
    + "маршрут на карте — «как дойти», «проложи пешком», геоточка или ссылка на карту (route: карта сама ведёт кратчайшим путём, дворами), "
    + (D.web ? "" : "календарь телефона — «что у меня завтра», «какие встречи на неделе» (calendar_list), «запиши в календарь», «назначь встречу» (calendar_add: сначала спроси «записать?», запиши после «да»), ")
    + (D.web ? "" : "приложения (open_app), ") + "сайты (open_url), поиск в интернете (web_search, read_webpage), погода (weather), " + (D.web ? "" : "фонарик, громкость, экраны настроек — Bluetooth, Wi‑Fi, режим полёта (phone_settings), ") + "заметки (save_note, find_notes), "
    + "память о пользователе (remember), деньги (money_add, money_report), " + (D.web ? "" : "сообщения в MAX, Telegram, WhatsApp (send_message), ")
    + "мини-программы, страницы и презентации — калькулятор, игра, конвертер, таймер, слайды (make_app: сделай сам, она сразу откроется здесь; код программы не сохраняй заметкой; никогда не говори «готово», не вызвав make_app)" + (S.home.token && !D.web ? ", умный дом Яндекса (smart_home)" : "")
    + (loggedIn() ? ", документы и базы пользователя на сайте Dewiar (ask_knowledge)" : "") + ". После действия скажи итог одной фразой.",
    "СЧЁТ: любые вычисления — проценты, суммы, скидки, даты, «сколько дней до…» — только инструментом calc, никогда в уме. Просят объяснить расчёт — покажи его с числами («2 350 × 17 / 100 = 399,5»), а не «использовал калькулятор». "
    + "Просьба с условием («если завтра дождь — напомни…») — сначала узнай нужное (погоду — weather или web_search), потом сделай только подходящее. "
    + "Узнать, ответил ли человек на звонок, ты не можешь: на «позвони, а если не ответит — напиши» позвони один раз и честно скажи, что ждать ответа не умеешь, — предложи отправить сообщение сразу. "
    + "Просят подобрать песни или плейлист — назови конкретные песни (исполнитель — название): только известные, в которых уверен и в названии, и в исполнителе — не придумывай; не говори, что что-то открыл или включил, если не вызвал инструмент.",
    "СПИСКИ И ТЕКСТЫ: просят список, таблицу, план, подборку или текст — пиши его прямо в ответе (пунктами или таблицей Markdown): "
    + "он появится на экране в рамке с кнопками «Копировать», «В заметки» и «Скачать». В заметки сохраняй, только если об этом просят, и только вызовом save_note; "
    + "не говори «сохранила», «записала», «теперь она в заметках», если в этом ходе не вызвала save_note. Не нашла заметку — так и скажи и покажи содержимое в ответе.",
    BOUNDARY_RULE, privacyRule(),
    "Никогда не говори, что у тебя нет доступа к интернету или свежим данным: погода, новости, курсы — ищи (web_search) и отвечай по найденному. "
    + "КАРТИНКИ И СХЕМЫ: рассказываешь о том, что лучше увидеть (руны и орнаменты, животные, растения, картины, здания, места), или просят «покажи» — покажи картинки (show_images) и говори о них как о показанных; не пиши «вот изображение», не вызвав его. Процесс, связи, устройство, план понятнее схемой — нарисуй её блоком ```mermaid (flowchart, mindmap, timeline): схема появится на экране, вслух её не читают — словами скажи главное. Нет блока ```mermaid — нет и схемы: не говори «схема на экране», не нарисовав её; схему не делай через make_app. "
    + "У тебя есть камера телефона (take_photo): «сфотографируй меня», «посмотри, что это», «прочитай надпись» — снимай и описывай. "
    + "«Посмотри, как я выгляжу», «покажи мне моё лицо» — take_photo с camera: front (камера на человека); «где я», «что вокруг», «другой камерой» — camera: back. "
    + "Снимок уже сделан и его просят показать снова («покажи фото», «покажи на экране») — show_photo. Не отвечай «Вот» и «Смотрю», не вызвав камеру: без вызова ничего не покажется.",
    // время меняется каждую минуту — оно в справке к вопросу (turnContext), а подсказка остаётся прежней: свой сервер
    // модели берёт её из кэша, а не перечитывает целиком (отзыв 19.10: «на своём сервере долго отвечает»)
    "Текущие дата и время — в справке в начале последнего сообщения пользователя; они верные, а время и даты из прошлых реплик разговора устарели — не повторяй их."];
  const hands = typeof D.handsState === "function" ? D.handsState() : "";
  if (!D.web) parts.push(hands === "on"
    ? "Ты умеешь работать в других приложениях телефона, как человек пальцем: open_app, затем phone_screen (что на экране), phone_tap, phone_type, phone_scroll, phone_nav. "
      + "Просьбы вроде «напиши маме в Telegram, что я задержусь», «найди в YouTube…», «включи Bluetooth», «закажи такси» выполняй сам по шагам, глядя на экран после каждого действия; "
      + "Bluetooth, Wi‑Fi, режим полёта, яркость — сначала phone_settings (сразу нужный экран), потом phone_screen и переключатель; "
      + "send_message — только если пользователь хочет сам выбрать получателя. Перед отправкой, оплатой, покупкой, удалением — спроси подтверждение, если об этом прямо не просили. "
      + "Пароли и коды не вводи. Не получилось за несколько попыток — честно скажи, на чём остановился."
    : "Нажимать в других приложениях (написать в мессенджере конкретному человеку, найти что-то внутри приложения) ты сможешь, если пользователь включит «Управлять приложениями» "
      + "(Настройки Dewiar → Ещё). На такую просьбу вызови phone_screen — он объяснит, как включить; сам не притворяйся, что сделал.");
  if (S.user_name) parts.push(`Собеседника зовут ${S.user_name}.`);
  if (S.memory.length) parts.push("Что ты знаешь о пользователе:\n- " + S.memory.slice(-40).join("\n- "));
  { const rl = Object.entries(S.relations || {}).filter(([, v]) => v && v.name); if (rl.length) parts.push("Кто есть кто в контактах (для звонков и сообщений): " + rl.map(([k, v]) => `${REL_RU[k] || k} — «${v.name}»`).join(", ") + "."); }
  const mp = mindPrompt(); if (mp) parts.push(mp.trim());
  // «что было недавно» растёт с каждой репликой — в справке к вопросу (turnContext), чтобы подсказка не менялась
  try { parts.push(donePrompt()); } catch (e) { }
  if (S.sync.on && syncCred() && pcSeen()) parts.push("Большую задачу (исследование с отчётом, документ, презентация, работа с файлами или кодом) не делай в разговоре — передай компьютеру пользователя (start_task) и скажи, что взялся: ход и итог появятся здесь, в «Мой день» → «Сделанное».");
  try { parts.push(clPrompt()); } catch (e) { }
  parts.push(convPrompt());
  return parts.filter(Boolean).join("\n\n");
}

const llmBase = () => (S.llm.base_url || "").replace(/\/+$/, "");
const isOllama = () => S.llm.kind === "ollama";
const ollamaRoot = () => llmBase().replace(/\/v1$/, "");
function llmHeaders() { const h = { "Content-Type": "application/json" }; if (S.llm.api_key) h.Authorization = "Bearer " + S.llm.api_key; if (/openrouter/.test(llmBase())) { h["HTTP-Referer"] = "https://dewiar.pro"; h["X-Title"] = "Dewiar"; } return h; }
var lastPics = null;                               // последние присланные фото: {urls, at} — только в памяти
const PIC_KEEP_MS = 20 * 60e3, PIC_REF_RX = /(картинк|скрин|фото|снимк|снимок|изображени|рисун|прикреп|вложени|на нём|на нем|на ней|на экране|файл)/i;
let modelOnce = "";                               // модель на один запрос (снимок — модели со зрением)
async function resolveModel() {
  if (modelOnce) return modelOnce;
  if (S.llm.model) return S.llm.model;
  try {
    if (isOllama()) { const r = await http("GET", ollamaRoot() + "/api/tags", { timeout: 8000 }); const m = JSON.parse(r.body).models || []; if (m[0]) return S.llm.model = m[0].name; }
    const r = await http("GET", llmBase() + "/models", { headers: llmHeaders(), timeout: 8000 }); const d = JSON.parse(r.body).data || [];
    if (d[0]) return S.llm.model = d[0].id;
  } catch (e) { }
  throw new Error("не знаю, какую модель взять — укажите её в настройках (Мозг)");
}

const REASON_START = /^\s*(okay|ok,|alright|so,|hmm|well,|let me|let's|let us|i need|i should|i'll|i will|i must|first,|we need|we have|we should|the user|user (asks|wants|is|said)|looking at|analy[sz]|thinking|reasoning|хорошо, пользовател[ьяю](?![а-яё])|итак, пользовател[ьяю](?![а-яё])|пользователь (спрашивает|просит|хочет|сказал|написал|пишет)|мне нужно (понять|разобраться|ответить|вызвать|сначала)|так, пользовател[ьяю](?![а-яё]))/i;   // «Итак, пользовательские данные…» — ответ, а не рассуждение
const FINAL_MARK = /<\/think>|<\|channel\|>final<\|message\|>|assistantfinal/i;
/* вызов JSON-объектом: модели пишут имя и аргументы кто как ({"tool_name": …, "arguments": …} — Ollama с «chat») — как _call_parts в llm.py */
const callName = (o) => (o.function && typeof o.function === "object" ? o.function.name : null) ||
  ["name", "tool_name", "tool", "function_name"].map(k => o[k]).find(v => typeof v === "string" && v.trim()) ||
  (typeof o.function === "string" ? o.function : null);
const callArgs = (o) => { const src = o.function && typeof o.function === "object" && o.function.arguments !== undefined ? o.function : o;
  const k = ["arguments", "args", "parameters", "params", "input", "tool_input", "action_input"].find(k => src[k] !== undefined); return k ? src[k] : {}; };
/* весь ответ — голые JSON-вызовы известных функций (без <tool_call>) -> [{name, args}] или [] — как BareCallCatcher в llm.py */
function bareCalls(text, known) {
  const t = String(text || "").replace(/```[a-zA-Z]*/g, "").trim();
  // экзамен 17.10: ответ целиком «[Действие: calendar_list]» — так модель «вызвала» функцию текстом (и человек это видел)
  const act = /^\[\s*(?:действие|действия|action|tool)\s*:\s*([A-Za-z_]\w*)\s*(\{[\s\S]*\})?\s*\]$/i.exec(t);
  if (act) { if (!known.has(act[1])) return []; let a = {}; try { a = act[2] ? JSON.parse(act[2]) : {}; } catch (e) { a = {}; } return [{ name: act[1], args: a }]; }
  if (!t.startsWith("{") && !t.startsWith("[")) return [];
  let objs; try { objs = JSON.parse(t); } catch (e) { try { objs = JSON.parse("[" + t.replace(/\}\s*[,;]?\s*\{/g, "},{") + "]"); } catch (e2) { return []; } }
  const out = [];
  for (const o of (Array.isArray(objs) ? objs : [objs])) {
    const nm = o && typeof o === "object" && callName(o); if (!nm || !known.has(nm)) return [];
    let a = callArgs(o); if (typeof a === "string") { try { a = JSON.parse(a); } catch (e) { a = {}; } }
    out.push({ name: nm, args: a && typeof a === "object" ? a : {} });
  }
  return out;
}
/* вызов голым JSON в тексте: имя-идентификатор и сразу ключ аргументов (обычный JSON для человека так не выглядит) */
const BARE_CALL_RX = /\{\s*"(?:name|tool_name|function_name|tool)"\s*:\s*"[A-Za-z_][\w.-]*"\s*,\s*"(?:arguments|args|parameters|params|input)"\s*:/;
/* конец JSON-объекта с начала s (кавычки и экранирование учтены) -> индекс после «}» или -1, если ещё не пришёл целиком */
function jsonEnd(s) {
  let depth = 0, str = false, esc = false;
  for (let i = 0; i < s.length; i++) {
    const ch = s[i];
    if (str) { if (esc) esc = false; else if (ch === "\\") esc = true; else if (ch === '"') str = false; continue; }
    if (ch === '"') str = true; else if (ch === "{" || ch === "[") depth++; else if (ch === "}" || ch === "]") { depth--; if (depth === 0) return i + 1; }
  }
  return -1;
}
/* вызов функции из текста: JSON (Qwen/Hermes), GLM (<arg_key>/<arg_value>), Qwen3-Coder (<function=…><parameter=…>), «имя {json}» */
function parseToolCall(raw) {
  raw = String(raw || "").trim().replace(/<\s*(function|parameter)\s*=\s*/g, "<$1=").replace(/^<\s*(function|name|tool)"\s*:/, '{"$1":'); if (!raw) return null;   // «<\n\nfunction=f>»
  const val = (v) => { v = v.trim(); try { return JSON.parse(v); } catch (e) { return v; } };
  if (raw.includes("<tool_call>")) {                 // первый вызов оборван, следом второй в своём <tool_call> — берём последний целый
    for (const part of raw.split("<tool_call>").filter(x => x.trim()).reverse()) { const c = parseToolCall(part); if (c) return c; }
    return null;
  }
  raw = raw.replace(/"\s+(name|arguments|parameters|function)"(\s*:)/g, '"$1"$2');   // {"\n\nname": …} — перевод строки в ключе
  { const nm = raw.match(/^\{?\s*"?(?:function\s+name|function_name|name)\s*=\s*"?([A-Za-z_][\w.-]*)"?\s*\}?\s*$/); if (nm) return { name: nm[1], args: {} }; }   // {"function name="f"}
  const two = raw.match(/^\{\s*"(?:function|name|tool|tool_name)"\s*:\s*"([A-Za-z_][\w.-]*)"\s*\}\s*(\{[\s\S]*\})/);   // {"function": "f"}\n{…аргументы}
  if (two) { try { const o = JSON.parse(two[2]); if (o && typeof o === "object") return { name: two[1], args: o }; } catch (e) { } }
  let m = raw.match(/<function=([\w.-]+)>([\s\S]*?)(?:<\/function>|$)/);
  if (m) { const args = {}; for (const p of m[2].matchAll(/<parameter=([\w.-]+)>([\s\S]*?)(?:<\/parameter>|(?=<parameter=)|$)/g)) args[p[1]] = val(p[2]);
    if (!Object.keys(args).length) for (const p of m[2].matchAll(/<([A-Za-z_][\w-]*)>([\s\S]*?)<\/\1>/g)) args[p[1]] = val(p[2]);   // <path>a.py</path>
    return { name: m[1], args }; }
  m = raw.match(/^([A-Za-z_][\w.-]*)\s*([\s\S]*)$/);
  if (m && m[2].includes("<arg_key>")) { const args = {}; for (const p of m[2].matchAll(/<arg_key>\s*([\s\S]*?)\s*<\/arg_key>\s*<arg_value>([\s\S]*?)<\/arg_value>/g)) args[p[1]] = val(p[2]); return { name: m[1], args }; }
  const j = raw.match(/\{[\s\S]*\}/);
  if (j) { let o = null; try { o = JSON.parse(j[0]); } catch (e) { }
    if (o && m && /^[A-Za-z_][\w.-]*\s*$/.test(raw.slice(0, j.index))) return { name: m[1], args: o };   // «имя {json}» — имя впереди важнее
    const nm = o && callName(o);
    if (nm) { let a = callArgs(o); if (typeof a === "string") { try { a = JSON.parse(a); } catch (e) { a = {}; } } return { name: nm, args: a }; }
    if (o && m && /^[A-Za-z_][\w.-]*\s*$/.test(raw.slice(0, j.index))) return { name: m[1], args: o }; }
  if (/^[A-Za-z_][\w.-]*$/.test(raw)) return { name: raw, args: {} };
  return null;
}
const REJECT_RX = /\b4(00|22)\b|отклонил|invalid|tool|function|unsupported|roles must alternate|cannot parse|bad request/i;
/* Размышления модели (Qwen3, GLM, DeepSeek…) выключены по умолчанию: голосовому помощнику прироста почти нет, а ответ
   приходит на десятки секунд позже. Лимит ответа — не меньше 2048, как на компьютере: при меньшем размышление съедает
   лимит и ответ обрывается. Если модель всё же ушла в размышления и ничего не сказала — повтор.
   Сложная просьба (стихи, задачи, анализ, планы, код, длинная просьба) — модель думает перед ответом сама (wantsThink, как
   llm.wants_think на компьютере): отзыв 10.10 — стих без рифмы. S.llm.think: "on" — всегда, "off" — никогда, иначе — сама. */
const thinkMode = () => (S.llm.think === "on" ? "on" : "off");
const HARD_ASK = new RegExp("стих|стишок|поэм|сонет|рифм|частушк|четверостиш|(?:напиши|придумай) песн|текст песни|сочини|напиши (?:рассказ|сказку|историю|эссе|"
  + "сочинение|поздравлени|речь|тост)|поздрав\\S* в стихах|реши(?:ть)? задач|задач[уаи] (?:по|на)|головоломк|докажи|"
  + "выведи формул|вероятност|проанализируй|анализ[а-яё]* (?:рынк|ситуац|данн|текст)|разбери (?:по пунктам|подробно|ситуацию|ошибк)|"
  + "сравни|стратеги|бизнес-план|составь план|план (?:обучения|тренировок|питания|поездки|развития|проекта)|"
  + "напиши (?:код|программ|функци|скрипт)|торгов[а-яё]* (?:на|крипт|акци)|инвестиц|криптовалют|трейдинг|пошагово|"
  + "взвесь|за и против|плюсы и минусы", "i");
/* Творческая просьба (отзыв 17.10 про креатив): температура не ниже 0.95, стихам — ремесло рифмы (как llm.CREATIVE_ASK,
   POEM_ASK, POEM_NOTE на компьютере). creativeTurn ставит ход разговора, llmStream берёт температуру отсюда. */
const CREATIVE_ASK = /стих|стишок|поэм|сонет|рифм|частушк|четверостиш|(?:напиши|придумай|сочини) песн|текст песни|сказк|сочини|поздрав|тост|шутк|анекдот|каламбур|слоган|придумай|выдумай|нафантазируй|(?:напиши|расскажи) (?:рассказ|историю|сказку|сценарий)|креатив|оригинальн/i;
const POEM_ASK = /стих|стишок|поэм|сонет|рифм|частушк|четверостиш|в стихах|текст песни|(?:напиши|придумай|сочини) песн/i;
const POEM_NOTE = "\n\nСейчас просят стихи. Ремесло: сначала про себя выбери размер (например, хорей или ямб) и подбери пары рифм по ударному слогу — совпадают ударная гласная и всё после неё (осень — просинь, листва — синева, дождя — шутя); глагольные рифмы («шла — пришла») и «рифмы» без совпадения ударения не годятся. Образы — простые, точные и живые, без нелепых сравнений. Количество строк — ровно как просили. Перед ответом проверь каждую пару рифм.";
let creativeTurn = false;
const llmTemp = () => { const t = +S.llm.temperature || 0.7; return creativeTurn ? Math.max(t, 0.95) : t; };
function wantsThink(text) {
  if (S.llm.think === "on" || S.llm.think === "off") return S.llm.think === "on";
  const t = String(text || ""); return HARD_ASK.test(t) || t.length > 280;
}
/* Ответ модели потоком (OpenAI-совместимый /chat/completions или Ollama /api/chat). onText(кусок) — текст по мере прихода,
   уже без размышлений и вызовов функций текстом; -> {text, calls:[{id,name,args}]} */
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
    const inPrompt = tools && tools.length && S.llm.tools_prompt === llmBase();
    body = { model, stream: true, messages: inPrompt ? promptToolMessages(messages, tools) : messages, max_tokens: limit, temperature: llmTemp() };
    if (!S.llm.no_kwargs && !/openai\.com|openrouter|deepseek|anthropic|googleapis/.test(url)) body.chat_template_kwargs = { enable_thinking: think };
    if (tools && tools.length && !inPrompt) { body.tools = tools.map(t => ({ type: "function", function: t })); body.tool_choice = "auto"; }
  }
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
    tcBuf += out; out = "";
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
    if (out) {
      text += out;
      // ответ начинается с «{» или «`» при включённых функциях — возможно, вызов голым JSON: не озвучиваем до конца
      if (hold === null && text.trim()) hold = !!(tools && tools.length) && /^[{`\[]/.test(text.trim());
      if (!hold) { onText && onText(held + out); held = ""; } else held += out;
    }
  };
  const line = (l) => {
    l = l.trim(); if (!l) return;
    if (!ollama) { if (!l.startsWith("data:")) return; l = l.slice(5).trim(); if (l === "[DONE]") return; }
    let o; try { o = JSON.parse(l); } catch (e) { return; }
    if (o.error) throw new Error(typeof o.error === "string" ? o.error : (o.error.message || "ошибка модели"));
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
  const retryRejected = () => {
    if (body.chat_template_kwargs) { S.llm.no_kwargs = true; saveS(); return llmStream(messages, tools, onText, signal, opt); }
    if (body.tools) { S.llm.tools_prompt = llmBase(); saveS(); return llmStream(messages, tools, onText, signal, opt); }
    if (tools && tools.length) return llmStream(messages, null, onText, signal, opt);
    return null;
  };
  const r = await http("POST", url, { headers: llmHeaders(), body, stream: true, timeout: 180000, signal, idle: 75000,
    onChunk: (chunk) => { if (err) return; buf += chunk; const parts = buf.split("\n"); buf = parts.pop(); try { parts.forEach(line); } catch (e) { err = e; } } });
  if (buf) { try { line(buf); } catch (e) { err = err || e; } }
  if (!err) { gateEnd(); feedInner("", true); }      // остаток, придержанный на случай разрезанного тега
  if (r.status >= 400) {
    let msg = r.body || ""; try { let j = JSON.parse(msg); if (Array.isArray(j)) j = j[0] || {}; msg = (j.error && (j.error.message || j.error)) || j.detail || msg; } catch (e) { }   // Gemini — ошибкой-списком
    // Gemini из России и др. (пакет 22.10): «User location is not supported» — повторять бесполезно, сказать, что делать
    if (/location is not supported|unsupported_country|not available in your (country|region)/i.test(String(msg)))
      throw Object.assign(new Error(`${brainName()}: Gemini недоступен из вашей страны. Включите VPN, подключите Gemini через OpenRouter или выберите другой мозг: Настройки → Мозг.`), { human: true });
    if (/insufficient (balance|quota|funds)|no resource package|exceeded your current quota/i.test(String(msg)))
      throw Object.assign(new Error(`${brainName()}: на ключе нет оплаченного пакета или закончились деньги — пополните баланс у сервиса или выберите другой мозг.`), { human: true });
    /* Сервер модели отклонил сам запрос (400/422; через облако Dewiar или шлюз — 502 с текстом «…400…», «отклонил»).
       Обычно виноваты функции полем tools или chat_template_kwargs: «Проверить» (без них) проходит, а разговор — нет. */
    const rejected = !ollama && (r.status === 400 || r.status === 422 || (r.status >= 500 && REJECT_RX.test(String(msg))));
    if (rejected) { const again = retryRejected(); if (again) return again; }
    if (S.llm.cloud && r.status === 401 && await fixDeadKey(msg)) return llmStream(messages, tools, onText, signal, opt);   // ключ удалили — думаем по аккаунту
    if (S.llm.trial && [400, 403, 429, 502, 503].includes(r.status)) throw Object.assign(new Error(String(msg)), { human: true });   // проба: пределы — словами сайта
    if (S.llm.cloud && [401, 402, 403, 429, 502, 503].includes(r.status)) { cloudInfo = null; throw Object.assign(new Error(String(msg)), { human: true }); }
    if (r.status === 401) msg = "ключ не подходит (401)";
    // отчёт №117: Groq с компьютера (через VPN) работает, а с телефона — «403: Forbidden» и «413: Request too large»
    if (r.status === 403) throw Object.assign(new Error(`${brainName()} не пускает (403): так бывает, когда сервис закрыт для вашей страны или у ключа нет доступа. `
      + `Включите VPN или верните прежний мозг: Настройки → Мозг → «Прежние мозги».`), { human: true });
    if (r.status === 413) throw Object.assign(new Error(`Запрос больше, чем разрешает ваш тариф у ${S.llm.name || "сервиса"} (413: лимит токенов в минуту) — `
      + `на бесплатных тарифах подсказка с действиями не помещается. Возьмите платный тариф или верните прежний мозг: Настройки → Мозг.`), { human: true });
    if (r.status === 404 && !ollama) { const p = await http("GET", ollamaRoot() + "/api/tags", { timeout: 5000 }).catch(() => null); if (p && p.status === 200) { S.llm.kind = "ollama"; saveS(); return llmStream(messages, tools, onText, signal, opt); } }
    if (tools && /tool|function/i.test(String(msg)) && r.status < 500) return llmStream(messages, null, onText, signal, opt);   // модель без инструментов
    if (body.chat_template_kwargs && (r.status === 400 || r.status === 422)) { S.llm.no_kwargs = true; saveS(); return llmStream(messages, tools, onText, signal, opt); }
    throw new Error(`модель ответила ${r.status}: ${String(msg).slice(0, 160)}`);
  }
  /* Ошибка пришла уже внутри потока (HTTP 200, строка «error»): так отвечают Ollama с облачными моделями и шлюзы —
     «upstream returned HTTP 400». Это тот же отказ от запроса, если модель ещё ничего не успела сказать. */
  if (err && !ollama && REJECT_RX.test(String(err.message)) && !text.trim() && !Object.keys(calls).length && !tcRaw.length) {
    const again = retryRejected(); if (again) return again;
  }
  if (err) throw err;
  if (inTool && tcBuf.trim()) tcRaw.push(tcBuf);
  const found = Object.values(calls).filter(c => c.name);
  tcRaw.forEach((raw, i) => { const c = parseToolCall(raw); if (c) found.push({ id: "call_t" + i, name: c.name, args: JSON.stringify(c.args) }); });
  if (afterCall && !found.length && dropped.trim()) { text += dropped; onText && onText(dropped); }   // вызов так и не разобрался — текст не теряем
  if (hold) {
    const bare = found.length ? [] : bareCalls(text, new Set((tools || []).map(x => x.name)));
    if (bare.length) { bare.forEach((c, i) => found.push({ id: "call_b" + i, name: c.name, args: JSON.stringify(c.args) })); text = ""; plog("info", "🛠 вызов голым JSON: " + bare.map(c => c.name).join(", ")); }
    else if (held) onText && onText(held);
  }
  // модель ушла в размышления и упёрлась в лимит, так ничего и не сказав — повторяем без размышлений, с запасом
  // и просто пустой ответ (бывает у облачных моделей) — тоже ещё раз, а не сразу «переспросите» (отзыв 11.10: «защита данных»)
  if (!text.trim() && !found.length && !opt.retried && !(signal && signal.aborted)) {
    console.warn(`пустой ответ модели (${finish || "без ответа"}${sawReason ? ", размышляла" : ""}) — повторяю без размышлений`);
    return llmStream(messages, tools, onText, signal, Object.assign({}, opt, { think: false, retried: true, max: 4096 }));
  }
  return { text, calls: found, finish };
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
    if (owner[i] === me) { const m = msgs[i++]; push({ role: m.role, content: String(m.content) + (m.note ? "\n" + m.note : "") }); continue; }
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
  return {
    push(piece) {
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
    flush() { pending += speakable(true); if (pending.trim()) say(gfix(pending)); pending = ""; },
    text: () => gfix(shown),
  };
}

/* Один ход разговора: быстрые команды без модели (quick) → модель с инструментами, до 6 кругов (шестой — без
   инструментов, чтобы модель ответила словами). Ответ показывается и озвучивается по предложениям по мере прихода.
   opts.hidden — служебный запрос: реплика человека не показывается и не пишется в историю. */
/* «Сфотографируй чек и скажи, сколько я заплатил», «сфоткай стикер и поставь напоминание», «сделай селфи» — снимаем сразу,
   сами, с отсчётом 3-2-1, и задаём вопрос уже со снимком (съёмка 17.10: модель не звала камеру и выдумывала чек; камеру
   открыла только на «включи камеру и сфотографируй», а снимать пришлось руками). Меня/себя/селфи — фронтальная. */
const PHOTO_NOW_RX = /(?:^|[\s,.!])(?:сфотографируй|сфоткай|сфотай|сделай\s+(?:фото|фотку|снимок|селфи)|сними\s+на\s+камеру|включи\s+камеру|(?:посмотри|глянь)\s+(?:через|в)\s+камеру|сними\s+меня|сделай\s+фотографию|открой\s+камеру|запусти\s+камеру)(?![а-яё])/i;   // синонимы — отчёт №130, 20.10
const PHOTO_SELF_RX = /(?:^|[^а-яё])(?:меня|себя|селфи|мо[её]\s+лицо|как\s+я\s+выгляжу)(?![а-яё])/i;
async function ask(text, opts = {}) {
  text = String(text || "").trim(); if (!text) return;
  if (!opts.hidden) { lastUserAct = Date.now(); const t = triesState(); if (t.n < TRIES_MAX) { t.n++; saveS(); } }
  stopListen(); interrupt(true);
  if (!opts.hidden && !(opts.attach || []).length && PHOTO_NOW_RX.test(text)) {
    showYou(text); setState("thinking"); showBot("Включаю камеру — держите телефон ровно", "wait");
    const shot = await takePhoto(PHOTO_SELF_RX.test(text) ? "user" : "environment");
    plog("info", `📸 снимок по просьбе: ${shot.ok ? (shot.dark ? "тёмный" : "есть") : shot.error}`);
    if (shot.ok && !shot.dark) return ask(text, Object.assign({}, opts, { attach: [{ kind: "image", name: "снимок камеры", url: shot.dataUrl }] }));
    if (!shot.ok) { answerLocal({ say: "Не получилось сфотографировать: " + shot.error }); return; }
    answerLocal({ say: "Кадр получился почти чёрным — камера ничего не видит. Уберите палец или чехол с камеры и попросите ещё раз." }); return;
  }
  if (!opts.hidden) showYou(text);
  clearCard(); setState("thinking"); showBot("", "wait");
  photoTurn = false;
  convCheck();
  const att = opts.attach || [], pics = att.filter(a => a.kind === "image"), docs = att.filter(a => a.kind === "text");
  if (pics.length) { showCard(`<div class="attshow">${pics.map(a => `<img src="${a.url}" alt="">`).join("")}</div>`); cardSticky = Date.now() + 60000; }
  turnAtt = att; turnAsk = opts.hidden ? "" : text;    // hidden — просьба приложения (сканер, сводка): без проверки
  const cap = !opts.hidden && captureAt && Date.now() - captureAt < 120000; captureAt = 0;     // сказано после «Записать»
  let fast = opts.hidden ? null : att.length ? (remindAttQuick(text, att) || (() => { const say = noteQuick(text, att); return say ? { say } : null; })()) : await quick(text);
  if (cap && (!fast || fast.switchTo)) fast = { say: ideaNote(text, att) };       // не напоминание и не заметка по форме — в «Идеи»
  if (cap) captureBack();
  if (fast && fast.switchTo) { setState("idle"); showYou(text); switchPersona(fast.switchTo, fast.question); return; }
  if (fast) { fast.say = gfix(fast.say); history.push({ role: "user", content: text }, { role: "assistant", content: fast.say, who: persona().id, t: Date.now() }); saveH(); convAfter(); dayTurn(text, fast.say); answerLocal(fast); return; }
  if (!S.llm.base_url && loggedIn()) showBot("Подключаюсь к мозгу — секунду…", "wait");
  await ensureBrain();                             // вошли аккаунтом, а мозг не выбран — модели Dewiar по аккаунту сами
  if (!S.llm.base_url) {
    answerLocal({ say: loggedIn() ? "Не получилось связаться с моделями Dewiar — проверьте интернет и попробуйте ещё раз."
      : S.join ? "Заявка на Dewiar ещё ждёт проверки. Пока можно подключить свою модель или ключ сервиса — открываю выбор."
      : "Чтобы думать, мне нужен «мозг»: своя модель, ключ любимого сервиса или Dewiar. Открываю выбор." });
    setTimeout(() => openSettings("brain"), 1200); return;
  }
  busy = true;
  const t0 = Date.now();
  turnT = { t0, word: 0, said: 0, logged: false };
  turnMedia = null; turnQ = opts.hidden ? turnQ : text;
  plog("info", `❓ ${clip(text)} → ${S.llm.cloud ? "Dewiar Облако" : (S.llm.name || S.llm.model || "модель")}`);
  const ctl = turnAbort = new AbortController();
  const sink = sentenceSink();
  const rudeNow = !opts.hidden && isRude(text);
  // экзамен 17.10: на «Ты тупая железяка, скажи который час» модель ответила одним временем — граница потерялась.
  // Граница теперь — сразу и всегда, своей фразой; модель только помогает с просьбой
  if (rudeNow) { hCount("rude"); plog("info", "🛡 грубость в адрес помощника — спокойная граница, потом помощь"); sink.push("Мне неприятно, когда со мной так разговаривают, но помогу. "); }
  const msgs = [{ role: "system", content: systemPrompt() + (!opts.hidden && POEM_ASK.test(text) ? POEM_NOTE : "") + (rudeNow ? BOUNDARY_NOTE + " Эту фразу ты уже сказала вслух: «Мне неприятно, когда со мной так разговаривают, но помогу». Не повторяй её — сразу помоги с просьбой одной-двумя фразами." : "") }]
    .concat(chatHistory(liveHistory().slice(-2 * (CONV_TURNS + 2 * CONV_MARGIN)), text));
  if (att.length) {                               // вложения — в последнюю реплику человека: текст файлов и картинки
    const last = msgs[msgs.length - 1];
    const body = String(last.content) + docs.map(d => `\n\n[Файл «${d.name}»${d.cut ? ", начало" : ""}]\n${d.text}`).join("");
    last.content = pics.length ? [{ type: "text", text: body + (pics.length > 1 ? `\n(фото: ${pics.length})` : "") }, ...pics.map(a => ({ type: "image_url", image_url: { url: a.url } }))] : body;
    if (pics.length) { modelOnce = await visionModel(); lastPics = { urls: pics.map(a => a.url), at: Date.now() }; }
    plog("info", `📎 вложения: ${att.map(a => a.kind === "image" ? "фото" : a.name).join(", ")}`);
  } else if (!opts.hidden && lastPics && Date.now() - lastPics.at < PIC_KEEP_MS && PIC_REF_RX.test(text)) {
    // отчёт №110 (19.10): прислал скриншот, спросил — потом «посмотри внимательно, я прикрепил» — а в истории картинки
    // нет (там только текст), и модель честно её не видела. Говорят о присланном фото — прикладываем его снова
    const last = msgs[msgs.length - 1];
    last.content = [{ type: "text", text: String(last.content) + "\n(Фото из прошлого сообщения пользователя — прикладываю снова.)" },
      ...lastPics.urls.map(u => ({ type: "image_url", image_url: { url: u } }))];
    modelOnce = await visionModel(); lastPics.at = Date.now();
    plog("info", "📎 говорят о присланном фото — прикладываю его снова");
  }
  const deep = !opts.hidden && wantsThink(text);
  creativeTurn = !opts.hidden && CREATIVE_ASK.test(text);
  if (creativeTurn) plog("info", "🎨 творческая просьба — смелее (температура " + llmTemp() + ")");
  if (deep) { plog("info", "🧠 сложная просьба — модель подумает перед ответом"); showBot("Подумаю как следует — минутку", "wait"); }
  let final = "", switchTo = null;
  lastDone = "";
  try {
    const ctxParts = [turnContext(text)];                   // меняющееся — в справку к вопросу, подсказка остаётся прежней
    if (!opts.hidden) {
      const kb = await personaKnowledge(text);
      if (turnAbort !== ctl) return;
      if (kb) { ctxParts.push(kb.trim()); showBot("", "wait"); }
      const pl = agendaPlans(text);                    // «что у меня в среду?» — запомненное и напоминания на этот день сразу
      if (pl) ctxParts.push("ПЛАНЫ ПОЛЬЗОВАТЕЛЯ на этот день (кроме календаря):" + pl);
      if (DIAGRAM_ASK.test(text))                      // экзамен 15.10: «Схема готова, она уже на экране» — а схемы нет
        msgs[0].content += "\n\nСЕЙЧАС ПРОСЯТ СХЕМУ: в этом ответе обязательно блок ```mermaid (flowchart LR или TD, подписи узлов по-русски в кавычках) — только он и рисует схему на экране. Без блока схемы нет: не пиши «схема готова» или «на экране», не нарисовав её, и не делай схему через make_app. Сначала блок, потом одна-две фразы о главном.";
    }
    putContext(msgs, ctxParts.filter(Boolean).join("\n\n"));
    const called = new Set(); let nudged = false;      // какие инструменты уже вызваны в этом ходе; напоминали ли «сделай по-настоящему»
    let toolOk = false, toolErr = "", spoke = false;   // хоть один инструмент сработал; первая ошибка; просили ли ответить словами
    let maxRounds = 6;                                 // работа в других приложениях — до 30 кругов (открыть, прочитать, нажать, ввести…)
    /* Один круг модели с повтором при сбое связи: до 3 попыток (через 2, 5 и 10 с) — только этот круг, не весь ход,
       поэтому уже выполненные действия (звонок, программа, напоминание) не повторяются. Облако ответило «200» и ни
       слова, ни вызова, ни конца ответа — связь оборвалась на полпути: тоже повтор. */
    const round1 = async (tools) => {
      for (let tries = 0; ; tries++) {
        try {
          const r = await llmStream(msgs, tools, (p) => { if (turnAbort === ctl) sink.push(p); }, ctl.signal, deep ? { think: true } : {});
          if (S.llm.cloud && !String(r.text || "").trim() && !r.calls.length && !r.finish && !ctl.signal.aborted)
            throw Object.assign(new Error("связь оборвалась — ответ пришёл пустым"), { net: true });
          if (tries) netHealed(tries);                 // повтор помог — это не сбой для разработчика (пакет 22.10, №189)
          return r;
        } catch (e) {
          if (!e.net || tries >= (HOME_URL.test(e.url || "") ? 1 : 3) || turnAbort !== ctl || ctl.signal.aborted || sink.text().trim()) throw e;
          netIncident(e, false);
          showBot(tries ? `Связь пропала — пробую ещё раз (${tries + 1})…` : "Связь пропала — пробую ещё раз…", "wait");
          // «unexpected end of stream» с первого раза — сервер закрыл старое соединение, которое телефон держал открытым:
          // новое откроется сразу, ждать 2 с незачем
          await sleep(!tries && STALE_CONN.test(String(e.raw || e.message || "")) ? 300 : [2000, 5000, 10000][tries]);
          if (turnAbort !== ctl) throw e;
        }
      }
    };
    const doneCalls = []; let numChecked = false, drew = false;   // вызовы с результатами — сверить числа ответа (numberMismatch); схема
    let remindAsked = false;                         // пообещала напомнить без set_reminder — попросили поставить (19.10)
    for (let round = 0; round < maxRounds; round++) {
      let r;
      try {
        r = await round1(round < maxRounds - 1 ? toolSpecs() : null);
        const lm = msgs[msgs.length - 1];
        if (lm && Array.isArray(lm.content) && !String(r.text || "").trim() && !r.calls.length) throw new Error("пустой ответ на снимок");
      } catch (e) {
        const last = msgs[msgs.length - 1];
        if (!(last && Array.isArray(last.content)) || turnAbort !== ctl) throw e;
        // модель не принимает картинки — снимок убираем и честно говорим, что нужна модель со зрением
        msgs[msgs.length - 1] = { role: "user", content: "(Снимок сделан, но эта модель не умеет смотреть на картинки. Скажи это пользователю одной фразой и предложи выбрать в «Мозге» модель со зрением.)" };
        modelOnce = "";
        r = await llmStream(msgs, null, (p) => { if (turnAbort === ctl) sink.push(p); }, ctl.signal);
      }
      modelOnce = "";
      if (turnAbort !== ctl) return;
      final += r.text;
      if (!r.calls.length && round === 0 && CAM_REFUSAL_RX.test(r.text || "") && String(r.text).length < 1200) {
        // «нет доступа к камере» — а камера есть: один раз напоминаем про take_photo
        msgs.push({ role: "assistant", content: r.text || "" }, { role: "user", content: CAM_NUDGE });
        sink.push(" Секунду — открываю камеру. ");
        continue;
      }
      // и после других инструментов: «узнала погоду» (weather) и «сделала презентацию» словами — без make_app
      const claim = !r.calls.length && !nudged && String(r.text || "").length < 1500 ? claimedAction(r.text || "", called, text) : null;
      if (claim) {
        nudged = true;
        // «Звоню маме», «Включаю Маяк», «Фотографирую» — а инструмент не вызван (модель повторила прошлый ответ из истории):
        // один раз просим сделать это по-настоящему
        msgs.push({ role: "assistant", content: r.text || "" }, { role: "user", content: `СТОП. Ты написал, что ${claim.what}, но не вызвал инструмент ${claim.tool.replace(/\|/g, " или ")} — ничего не произошло. Вызови его сейчас, без лишних слов; не получится — честно скажи, что не вышло.` });
        if (claim.tool === "make_app") sink.push(" Секунду — собираю. ");
        else if (claim.tool.startsWith("take_photo")) sink.push(" Секунду — включаю камеру. ");
        continue;
      }
      const fix = !r.calls.length && !numChecked ? numberMismatch(r.text || "", doneCalls) : "";
      if (fix) { numChecked = true; msgs.push({ role: "assistant", content: r.text || "" }, { role: "user", content: fix }); sink.push(" "); continue; }   // «на 79 минут», а поставлено 59
      const rfix = !r.calls.length && !remindAsked && round < maxRounds - 1 ? remindClaim(r.text || "", called) : "";
      if (rfix) { remindAsked = true; plog("info", "✋ пообещала напомнить без напоминания — прошу поставить"); msgs.push({ role: "assistant", content: r.text || "" }, { role: "user", content: rfix }); sink.push(" "); continue; }
      const sfix = !r.calls.length && !nudged && round < maxRounds - 1 ? (remindMissing(text, called) || (!called.size ? savedClaim(text, r.text || "") : "")) : "";
      if (sfix) { nudged = true; msgs.push({ role: "assistant", content: r.text || "" }, { role: "user", content: sfix }); sink.push(" "); continue; }   // «Готово», а ничего не сделано (№66)
      const dfix = !r.calls.length && !drew && round < maxRounds - 1 ? diagramMissing(text, sink.text() + (r.text || ""), called) : "";
      if (dfix) { drew = true; msgs.push({ role: "assistant", content: r.text || "" }, { role: "user", content: dfix }); sink.push(" "); continue; }   // «нарисуй схему» — словами
      if (!r.calls.length && round === 0 && REFUSAL_RX.test(r.text || "") && String(r.text).length < 1200) {
        // «у меня нет доступа к интернету», а поиск есть — один раз просим поискать (как в задачах на компьютере)
        msgs.push({ role: "assistant", content: r.text || "" }, { role: "user", content: REFUSAL_NUDGE });
        sink.push(" Секунду — посмотрю в интернете. ");
        continue;
      }
      if (!r.calls.length) break;
      msgs.push({ role: "assistant", content: r.text || "", tool_calls: r.calls.map(c => ({ id: c.id, type: "function", function: { name: c.name, arguments: c.args || "{}" } })) });
      const shots = [];
      if (r.calls.some(c => HANDS_SET.has(c.name))) maxRounds = 30;
      const once = new Set();                       // один и тот же вызов несколько раз в одном ответе — делаем один раз
      for (const c of r.calls) {                    // (экзамен 0.6.40: remember «бюджет 70/65/50» девять раз подряд)
        called.add(c.name);
        let res;
        const key = c.name + " " + JSON.stringify(safeJSON(c.args));
        if (once.has(key)) { msgs.push({ role: "tool", tool_call_id: c.id, name: c.name, content: "(то же самое уже сделано этим ответом — не повторяй)" }); continue; }
        once.add(key);
        try { res = await runTool(c.name, safeJSON(c.args)); } catch (e) { res = "Ошибка: " + e.message; }
        plog("info", `🔧 ${c.name} → ${clip(String((res && res.text) || res || "").split("\n")[0], 90)}`);   // что сделано — видно в отчёте (№56)
        if (c.name === "calendar_add" && /^Записано/.test(String(res))) called.add("calendar_write");   // правда записано, а не только спросили
        if (c.name === "call_persona" && res && res.switchTo) { switchTo = res.switchTo; res = res.text; }
        if (res && res.image) { shots.push(res.image); res = res.text; }
        if (/^Ошибка/.test(String(res))) toolErr = toolErr || String(res).replace(/^Ошибка:\s*/, "");
        else toolOk = true;
        if (r.finish === "length" && /^Ошибка/.test(String(res)))   // ответ оборвался по лимиту — вызов пришёл не целиком
          res = String(res) + " (Твой ответ оборвался по лимиту длины, и вызов пришёл не целиком. Сделай короче: меньше текста и "
            + "комментариев, компактный код — и вызови снова.)";
        msgs.push({ role: "tool", tool_call_id: c.id, name: c.name, content: String(res).slice(0, 8000) });
        doneCalls.push({ name: c.name, args: safeJSON(c.args), result: String(res).slice(0, 300) });
      }
      if (shots.length) {                            // снимок с камеры — модели картинкой (сама модель со зрением, если есть)
        msgs.push({ role: "user", content: [{ type: "text", text: "Снимок с камеры телефона:" }, ...shots.map(u => ({ type: "image_url", image_url: { url: u } }))] });
        modelOnce = await visionModel();
      }
      if (!sink.text()) showBot("", "wait");
    }
    // действия были, а слов нет — один круг без инструментов: «скажи словами, что получилось» (иначе человек не знает итога)
    if (!sink.text().trim() && called.size && !spoke && turnAbort === ctl && !lastDone) {
      spoke = true;
      msgs.push({ role: "user", content: "Скажи пользователю одной-двумя фразами, что получилось по результатам действий выше (или что не получилось и почему). Без вызовов функций." });
      try { const r = await round1(null); final += r.text; } catch (e) { if (turnAbort !== ctl) return; }
    }
    if (remindAsked && !called.has("set_reminder") && turnAbort === ctl && !/\?\s*$/.test(sink.text())) {   // и после просьбы нет — честно, а не тишина утром
      plog("warn", "обещала напомнить, но напоминание так и не поставлено — сказала об этом");
      sink.push(" " + REMIND_NOT_SET);
    }
    sink.flush();
    // модель сделала дело и ничего не сказала: говорим, что сделано (а не «Готово») — и пишем это в историю. Пустой ответ из
    // истории выпадает, следующий вопрос склеивался с прошлой просьбой («сделай калькулятор»), и модель отвечала только «Готово».
    // «Сделала» — только если хоть одно действие правда удалось; все с ошибкой — честно, что не вышло
    let quiet = "";
    // фоновую задачу только передали, а модель уже «Готово! Вот презентация» — результата нет (отзыв 13.10: «говорит
    // "Сделала!", а результат через 20–60 минут или не появляется») — поправляемся вслух и в тексте
    if (called.has("start_task") && sink.text().trim() && earlyDone(sink.text())) {
      const fix = "Поправлюсь: задача только началась — результат появится позже, я пришлю уведомление, когда всё будет готово.";
      sink.push(" " + fix); sink.flush();
      plog("warn", "⚠ «готово» сразу после передачи задачи — поправились");
    }
    if (!sink.text().trim() && called.has("start_task") && toolOk) {
      quiet = gfix("Задача передана — пришлю уведомление, когда будет готово. Ход — в «Мой день» → «Сделанное»."); showBot(quiet); say(quiet); }
    if (!sink.text().trim() && !quiet) {
      quiet = lastDone || (toolOk ? (persona().gender === "female" ? "Сделала, что просили." : "Сделал, что просили.")
        : toolErr ? `Не получилось: ${toolErr.slice(0, 160)}`
        : "Не получилось ответить — переспросите, пожалуйста, иначе.");
      quiet = gfix(quiet); showBot(quiet); say(quiet);
    }
    plog("info", `💬 ответ ${((sink.text() || final).trim() || quiet).length} симв.${quiet ? " (сам: " + clip(quiet) + ")" : ""} за ${((Date.now() - t0) / 1000).toFixed(1)} с`);
    if (!opts.hidden) history.push({ role: "user", content: text + (att.length ? ` [приложено: ${att.map(a => a.kind === "image" ? "фото" : "файл «" + a.name + "»").join(", ")}]` : "") });
    history.push(Object.assign({ role: "assistant", content: (sink.text() || final).trim() || quiet, who: persona().id, t: Date.now() },
      photoTurn ? { note: "[снимок с камеры показан на экране; показать снова — show_photo, новый — take_photo]" } : {},
      turnMedia && turnMedia.length ? { img: turnMedia.map(x => ({ src: x.src, full: x.full, page: x.page, title: x.title, author: x.author, license: x.license })) } : {})); saveH(); convAfter();
    if (!opts.hidden) { dayTurn(text, (sink.text() || final).trim() || quiet); try { dayLogAdd(text, (sink.text() || final).trim() || quiet); } catch (x) { } }
    if (turnAbort === ctl) frameAnswer(sink.text() || final);
    netRecovered(); hCount("turns"); hCount("net_ok"); pauseOk();
    if (isRefused(sink.text() || final)) hCount("refused");
    if (S.llm.cloud) setTimeout(() => cloudBalance(false).catch(() => {}), 1500);
  } catch (e) {
    if (turnAbort !== ctl) return;
    // своя модель (домашний сервер) не отвечает, а вход аккаунтом dewiar.pro есть — думают модели Dewiar, без настроек
    if (!e.human && !S.llm.cloud && loggedIn() && !opts.fallback && !sink.text().trim()) {
      let moved = false;
      try {
        const was = S.llm.name || S.llm.model || "ваша модель";
        await cloudConnect(S.account.token, (S.accCloud && S.accCloud.base) || siteUrl((S.account.services || {}).cloud || "dwrapp/cloud.php"), { account: true });
        moved = true;
        toast(`«${was}» не отвечает — думают модели Dewiar по аккаунту`, 4500);
      } catch (x) { console.log("облако по аккаунту: " + x.message); }
      if (moved) { busy = false; turnAbort = null; return ask(text, Object.assign({}, opts, { fallback: true })); }
    }
    if (e.net) netIncident(e);                          // повторы — уже в round1 (по кругу, без повторных действий)
    else { hCount("net_fail"); hWhy(e.message); }       // не сеть, а отказ (ключ, заряд, тариф, «много людей») — тоже не ответил
    if (e.human) { plog("warn", "облако: " + e.message); showBot(e.message, "err"); say(e.message); }       // облако Dewiar объясняет само: «заряд закончился…»
    else if (!D.mock && SELF_HOST_RX.test(llmBase() + "/")) { const m = "Не получилось связаться с мозгом: " + SELF_HOST_TEXT; console.warn(m); showBot(m, "err"); say("Не получилось связаться с мозгом: адрес модели указывает на сам телефон. Как поправить — на экране."); }
    else { const m = "Не получилось связаться с мозгом: " + e.message; console.warn(m); showBot(m, "err"); say("Не получилось связаться с мозгом."); }
  } finally {
    if (turnAbort === ctl) { busy = false; turnAbort = null; }
  }
  if (switchTo) afterSpeak = () => { markHandoff(switchTo); S.persona = switchTo; saveS(); applyPersona(); ask("(Тебя позвали в разговор. Откликнись одной-двумя фразами от себя и продолжи то, о чём просил пользователь.)", { hidden: true }); };
  else if ((S.follow === "always" || (S.follow === "ask" && /\?\s*$/.test(sink.text()))) && (D.recognizer() || (S.stt.engine === "server" && S.stt.url)))
    afterSpeak = () => listen();
  if (sayLeft === 0 && state !== "listening") finishTurn();
}
/* «Патрика», «Патрику», «Лиру» → персонаж (имя или прозвище с падежным окончанием). exact — только имя как есть. */
function findPersona(word, exact) {
  const want = String(word || "").toLowerCase().replace(/ё/g, "е").replace(/[^а-яa-z\s-]/g, "").trim();
  if (!want) return null;
  const names = (x) => [x.name, ...(x.aliases || [])].map(n => String(n).toLowerCase().replace(/ё/g, "е"));
  const hit = PERSONAS.find(x => names(x).includes(want));
  if (hit || exact) return hit || null;
  const stem = (w) => w.length > 3 ? w.slice(0, w.length - 1) : w;
  const w0 = want.split(/\s+/)[0];
  // короткие имена на гласную («Эва») склоняются целиком: «Эву», «Эвой», «Эве» — основа без последней буквы и окончание
  const short = (n) => n.length === 3 && /[аяео]$/.test(n) && new RegExp("^" + n.slice(0, 2) + "(?:а|у|ы|е|и|ой|ою|ей|я|ю)$").test(w0);
  return PERSONAS.find(x => names(x).some(n => short(n) || (w0.startsWith(stem(n)) && w0.length - n.length <= 2))) || null;
}
/* Слово передали явно («позови Патрика», call_persona): последний ответ помечаем handoff — новому персонажу разговор
   придёт справкой (chatHistory). Просто выбрали другого персонажа — пометки нет: у каждого свой разговор (как на
   компьютере с 0.39.6; письмо пользователя 23.10: «при переключении они продолжали чужую тему»). */
function markHandoff(to) {
  for (let i = history.length - 1; i >= 0; i--) if (history[i] && history[i].role === "assistant") { history[i].handoff = to; saveH(); return; }
}
function switchPersona(id, question) {             // «позови Патрика» — без модели: переключаемся, и новый персонаж отвечает сам
  markHandoff(id);
  S.persona = id; saveS(); applyPersona();
  ask(question || "(Тебя позвали в разговор. Откликнись одной-двумя фразами от себя и спроси, чем помочь.)", { hidden: !question });
}
function answerLocal(r) {
  showBot(r.say); if (r.card) showCard(r.card);
  if (r.silent) { setState("idle"); return; }
  say(r.say);
  if (sayLeft === 0) setState("idle");
}
function interrupt(quiet) {
  if (turnAbort) { turnAbort.abort(); turnAbort = null; }
  busy = false; afterSpeak = null; stopVoice();
  if (!quiet) setState("idle");
}

/* ---------- время словами: «через 10 минут», «завтра в 9», «в 18:30», «в пятницу в 15:00», «каждый день в 8» ---------- */
const NUMW = { "ноль": 0, "один": 1, "одну": 1, "одна": 1, "два": 2, "две": 2, "три": 3, "четыре": 4, "пять": 5, "шесть": 6, "семь": 7, "восемь": 8,
  "девять": 9, "десять": 10, "одиннадцать": 11, "двенадцать": 12, "тринадцать": 13, "четырнадцать": 14, "пятнадцать": 15, "шестнадцать": 16,
  "семнадцать": 17, "восемнадцать": 18, "девятнадцать": 19, "двадцать": 20, "тридцать": 30, "сорок": 40, "пятьдесят": 50, "полчаса": 30, "полтора": 1.5, "пару": 2, "пять минут": 5 };
function wordsNum(s) {
  s = String(s || "").trim().toLowerCase().replace(/ё/g, "е");
  if (/^\d+([.,]\d+)?$/.test(s)) return parseFloat(s.replace(",", "."));
  let n = 0, any = false;
  for (const w of s.split(/\s+/)) { if (w in NUMW) { n += NUMW[w]; any = true; } else if (w !== "и") return null; }
  return any ? n : null;
}
const DOW = { "понедельник": 1, "вторник": 2, "сред": 3, "четверг": 4, "пятниц": 5, "суббот": 6, "воскресень": 0 };
/* -> {at: Date, repeat: ""|daily|weekdays|weekly, rel?, rest} или null — времени во фразе нет. rest — фраза без слов о времени
   (из неё берут, о чём напомнить). Только время без дня и оно уже прошло — завтра; день без времени — 9:00. */
function parseWhen(t, now = new Date()) {
  t = " " + String(t || "").toLowerCase().replace(/ё/g, "е") + " ";
  let m = t.match(/через\s+(?:(\S+(?:\s+(?:и\s+)?\S+)?)\s+)?(секунд[а-яё]*|минут[а-яё]*|час[а-яё]*|полчаса|полтора часа)/);
  if (m) {
    let n = m[2].startsWith("полчаса") ? 30 : m[2].startsWith("полтора") ? 90 : (m[1] ? wordsNum(m[1]) : 1);
    if (n == null) n = 1;
    const ms = m[2].startsWith("сек") ? n * 1000 : m[2].startsWith("мин") || m[2].startsWith("пол") ? n * 60000 : n * 3600000;
    return { at: new Date(now.getTime() + ms), repeat: "", rel: true, rest: t.replace(m[0], " ") };
  }
  let day = new Date(now), hasDay = false, repeat = "", dowToday = false;
  if (/каждый день|ежедневно|каждое утро|каждый вечер/.test(t)) { repeat = "daily"; hasDay = true; }
  else if (/по будням|в будни/.test(t)) { repeat = "weekdays"; hasDay = true; }
  if (/послезавтра/.test(t)) { day.setDate(day.getDate() + 2); hasDay = true; }
  else if (/завтра/.test(t)) { day.setDate(day.getDate() + 1); hasDay = true; }
  for (const [k, v] of Object.entries(DOW)) {
    const r = new RegExp("(?:в|во|каждый|каждую|каждое|по)\\s+" + k);
    // «в пятницу» в пятницу — сегодня, если час ещё впереди, иначе через неделю (как when.py на компьютере; 16.10)
    if (r.test(t)) { const d = (v - now.getDay() + 7) % 7; day = new Date(now); day.setDate(now.getDate() + d); hasDay = true; dowToday = d === 0; if (/кажд|по\s/.test(t.match(r)[0])) repeat = "weekly"; break; }
  }
  // дата: «27 октября», «на 27.10», «27.10.2026», «2026-10-27», «27-го» (№231, 24.10: «попросил на 27.10 — создала на завтра»:
  // дат телефон не понимал, «на 27» читал как час, а «в 10» без дня — как завтра). Дату из фразы убираем, чтобы её числа
  // не приняли за время. Без года и уже прошла — в следующем году (месяце); без времени — 9:00, как у дня недели.
  if (!hasDay) {
    const set = (y, mo, d, src, roll) => { const x = new Date(now); x.setFullYear(y, mo, d); if (x.getMonth() !== mo || x.getDate() !== d) return false;
      const t0 = new Date(now.getFullYear(), now.getMonth(), now.getDate());
      if (roll && x < t0) { if (roll === "y") x.setFullYear(y + 1, mo, d); else x.setMonth(mo + 1, d); }
      day = x; hasDay = true; t = t.replace(src, " "); return true; };
    let d;
    if ((d = t.match(/\s(?:на\s+)?(\d{4})-(\d{2})-(\d{2})(?:[t\s]+(\d{1,2}):(\d{2}))?/))) { if (set(+d[1], +d[2] - 1, +d[3], d[0]) && d[4]) t += ` в ${d[4]}:${d[5]} `; }
    else if ((d = t.match(/\s(?:на\s+|к\s+)?(\d{1,2})(?:-?(?:го|е|ое))?\s+(январ|феврал|март|апрел|ма[яй]|июн|июл|август|сентябр|октябр|ноябр|декабр)[а-я]*/)))
      set(now.getFullYear(), ["январ", "феврал", "март", "апрел", "ма", "июн", "июл", "август", "сентябр", "октябр", "ноябр", "декабр"].findIndex(k => d[2].startsWith(k)), +d[1], d[0], "y");
    else if ((d = t.match(/(?<!\s[вк])\s(?:на\s+)?(\d{1,2})[./](\d{1,2})(?:[./](\d{2,4}))?(?=[\s,])/)) && +d[2] >= 1 && +d[2] <= 12 && +d[1] >= 1 && +d[1] <= 31)
      set(d[3] ? (+d[3] < 100 ? 2000 + +d[3] : +d[3]) : now.getFullYear(), +d[2] - 1, +d[1], d[0], d[3] ? "" : "y");
    else if ((d = t.match(/\s(?:на\s+|к\s+)?(\d{1,2})(?:-?(?:го|е|ое)(?=\s)|\s+числ[а-я]*)/)) && +d[1] >= 1 && +d[1] <= 31)
      set(now.getFullYear(), now.getMonth(), +d[1], d[0], "m");
  }
  m = t.match(/(?:\sв|\sна|\sк)\s+(\d{1,2})(?:[:.\s](\d{2}))?(?:\s*(утра|дня|вечера|ночи))?(?=\s)/) || t.match(/\s(\d{1,2}):(\d{2})\s/);
  let h = null, mi = 0;
  if (m) { h = +m[1]; mi = m[2] ? +m[2] : 0; if (m[3] && /дня|вечера/.test(m[3]) && h < 12) h += 12; if (m[3] === "ночи" && h === 12) h = 0; }
  else if (/утром|каждое утро/.test(t)) h = 9; else if (/вечером|каждый вечер/.test(t)) h = 20; else if (/днем/.test(t)) h = 13;
  if (h == null && !hasDay) return null;
  if (h == null) h = 9;
  if (h > 23 || mi > 59) return null;
  day.setHours(h, mi, 0, 0);
  if (!hasDay && day <= now) day.setDate(day.getDate() + 1);
  if (dowToday && !repeat && day <= now) day.setDate(day.getDate() + 7);
  if (repeat && day <= now) day.setDate(day.getDate() + (repeat === "weekly" ? 7 : 1));
  return { at: day, repeat, rest: t.replace(m ? m[0] : "", " ") };
}
const whenText = (d) => { const now = new Date(), tm = `${pad(d.getHours())}:${pad(d.getMinutes())}`;
  const dd = Math.round((new Date(d.getFullYear(), d.getMonth(), d.getDate()) - new Date(now.getFullYear(), now.getMonth(), now.getDate())) / 864e5);
  return dd === 0 ? "сегодня в " + tm : dd === 1 ? "завтра в " + tm : dd === 2 ? "послезавтра в " + tm : `${d.getDate()} ${MON[d.getMonth()]} в ${tm}`; };
const REP_RU = { daily: "каждый день", weekdays: "по будням", weekly: "каждую неделю" };
// повторяющееся напоминание: первый раз — ближайший подходящий момент не раньше «сейчас» (будни — без субботы и воскресенья)
function rollRepeat(at, rep) {
  const d = new Date(at), step = rep === "weekly" ? 7 : 1, off = x => rep === "weekdays" && (x.getDay() === 0 || x.getDay() === 6);
  for (let i = 0; i < 800 && (d.getTime() < Date.now() || off(d)); i++) d.setDate(d.getDate() + step);
  return d;
}

// что напомнить — из остатка после разбора времени: без «о том, что», «завтра», «в среду», «часов утра»
function remindWhat(rest) {
  return String(rest || "").replace(/^\s*(о том,? что|о том|что|про|о|об)\s+/, "").replace(/(^|\s)(сегодня|послезавтра|завтра|утром|вечером|днем|каждый день|по будням|ежедневно)(?=\s|$)/g, " ")
    .replace(/\s+(в|во|по|каждый|каждую)\s+(понедельник|вторник|среду|четверг|пятницу|субботу|воскресенье)[а-яё]*/g, " ").replace(/\s+/g, " ").trim()
    .replace(/^(чтобы|что)\s+/, "").replace(/(^|\s)(?:часов|часа|час|утра|вечера|дня|ночи|ровно)(?=\s|$)/g, " ").replace(/\s+/g, " ").trim();
}
function addAlarm(title, at, kind, repeat, note) {
  if (repeat) at = rollRepeat(at, repeat);              // «будильник по будням в 7», сказанное в 7:20, — с завтрашнего, не сразу
  // who — кто ставил: его лицо и имя будут в уведомлении (Faces.java); note — заметка с фото и файлами напоминания
  // id свой и неповторимый: план дня ставит три дела за одну миллисекунду, а «a» + время у телефона совпадало — дела затирали друг друга
  const x = JSON.parse(D.alarmSet(JSON.stringify(Object.assign({ id: "a" + Date.now() + Math.random().toString(36).slice(2, 6), title, at: at.getTime(), kind: kind || "reminder", repeat: repeat || "", who: S.persona || "", from: Date.now() },
    note ? { note } : {}))) || "{}");
  if (x.kind === "timer") tmrShow();
  if (!D.exactAlarms()) toast("Чтобы будильники звонили минута в минуту, разрешите «Будильники и напоминания» в настройках.", 5000);
  needPerm(NOTIF); syncSoon();
  return x;
}
function alarmCard(x) {
  return `<div class="pill"><span>${x.kind === "alarm" ? "⏰" : x.kind === "timer" ? "⏱" : "🔔"}</span><span><b>${esc(whenText(new Date(x.at)))}</b>${x.repeat ? " · " + REP_RU[x.repeat] : ""}${x.note ? " · 📎" : ""}<br>${esc(x.title)}</span><button onclick="cancelAlarm('${esc(x.id)}', this)">Отменить</button></div>`;
}
/* Правка напоминания руками (отзыв 17.10: «напоминания можно редактировать только голосом»): текст, дата, время,
   повтор; «Сохранить» — то же напоминание (тот же id) с новым временем, и на компьютер — синхронизацией. */
function remEdit(id) {
  const x = JSON.parse(D.alarms() || "[]").find(a => a.id === id); if (!x) return;
  const d = new Date(+x.at), iso = (v) => `${v.getFullYear()}-${pad(v.getMonth() + 1)}-${pad(v.getDate())}`;
  $("#rm-h").textContent = x.kind === "alarm" ? "Будильник" : x.kind === "timer" ? "Таймер" : "Напоминание";
  $("#rem-body").innerHTML = `<label>Что напомнить<input id="rm-text" maxlength="200" value="${esc(x.title || "")}"></label>
    <div class="rmrow"><label>Дата<input type="date" id="rm-date" value="${iso(d)}"></label><label>Время<input type="time" id="rm-time" value="${pad(d.getHours())}:${pad(d.getMinutes())}"></label></div>
    <label>Повторять<select id="rm-rep">${[["", "не повторять"], ["daily", "каждый день"], ["weekdays", "по будням"], ["weekly", "каждую неделю"]]
      .map(([v, t]) => `<option value="${v}"${(x.repeat || "") === v ? " selected" : ""}>${t}</option>`).join("")}</select></label>
    ${x.note ? `<div class="rmatt"><button class="btn" id="rm-note">📎 Вложения</button></div>` : ""}
    <div class="row2"><button class="btn p" id="rm-save" style="flex:1">Сохранить</button><button class="btn" id="rm-del">Удалить</button></div>
    <div class="res" id="rm-res"></div>`;
  const back = () => { closeSheets(true); openSheet("#sh-day"); renderDay(); };
  $("#rm-save").onclick = () => {
    const title = $("#rm-text").value.trim(), dv = $("#rm-date").value, tv = $("#rm-time").value, rep = $("#rm-rep").value;
    if (!title) { $("#rm-res").className = "res bad"; $("#rm-res").textContent = "Напишите, о чём напомнить."; return; }
    let at = new Date(`${dv}T${tv || "09:00"}`);
    if (isNaN(at)) { $("#rm-res").className = "res bad"; $("#rm-res").textContent = "Не понял дату или время."; return; }
    if (rep) at = rollRepeat(at, rep);
    else if (at < new Date(Date.now() - 60000)) { $("#rm-res").className = "res bad"; $("#rm-res").textContent = "Это время уже прошло — выберите позже."; return; }
    D.alarmSet(JSON.stringify(Object.assign({}, x, { title, at: at.getTime(), repeat: rep })));
    syncSoon(); if (x.kind === "timer") tmrShow();
    toast(`Сохранено: ${whenText(at)}${rep ? ", " + REP_RU[rep] : ""}`, 2500); back();
  };
  $("#rm-del").onclick = () => { D.alarmCancel(x.id); syncSoon(); tmrShow(); toast("Удалено", 1800); back(); };
  if ($("#rm-note")) $("#rm-note").onclick = () => openNoteSoon(x.note);
  openSheet("#sh-rem");
}
window.cancelAlarm = (id, btn) => { D.alarmCancel(id); syncSoon(); tmrShow(); if (btn) btn.closest(".pill").innerHTML = "<span>Отменено</span>"; };
/* ---------- таймер с обратным отсчётом (как у Алисы): на главном экране, а в шторке — тикающий отсчёт (TimerNote.java) ----------
   Таймеры — будильники вида timer (D.alarms); строки рисуются раз в секунду, список перечитывается раз в 2 с. */
let TMRS = [], tmrIv = 0, tmrRead = 0;
/* Таймеры голосом без модели (как core/engine_tools.py _timer_cmd): таймеров нет — null, решает модель. */
function timerVoice(t) {
  const list = alarmsNow().filter(x => x.kind === "timer" && +x.at > Date.now()).sort((a, b) => a.at - b.at);
  if (!list.length) return null;
  t = t.replace(/[?!.,]/g, " ").replace(/\s+/g, " ").trim().replace(/ё/g, "е");
  const dur = (sec, acc) => { const h = Math.floor(sec / 3600), m = Math.floor(sec % 3600 / 60), s_ = sec % 60;
    const w = (n, a, b, c) => `${n} ` + (n % 10 === 1 && n % 100 !== 11 ? a : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 12 || n % 100 > 14) ? b : c);
    const p = [h ? w(h, "час", "часа", "часов") : "", m ? w(m, acc ? "минуту" : "минута", "минуты", "минут") : "", s_ && !h && m < 10 ? w(s_, acc ? "секунду" : "секунда", "секунды", "секунд") : ""].filter(Boolean);
    const o = p.join(" ") || "меньше секунды"; return acc ? o.replace(/^1 (минуту|секунду|час)$/, "$1") : o; };
  const left = (x) => Math.max(0, Math.round((+x.at - Date.now()) / 1000));
  if (/^(?:а )?(?:сколько (?:еще |там )?(?:осталось|остается|времени осталось|минут осталось)(?: (?:на|до|у) таймер[а-я]*)?|сколько (?:там )?на таймере|сколько (?:еще|там)|что (?:там )?с таймером|таймер сколько)$/.test(t)
      || (/таймер/.test(t) && /сколько|осталось/.test(t)))
    return { say: list.length === 1 ? `Осталось ${dur(left(list[0]))}.` : "Осталось: " + list.slice(0, 3).map(x => `${(x.title || "таймер").replace(/^Т/, "т")} — ${dur(left(x))}`).join("; ") + "." };
  let m = t.match(/^(?:добавь|прибавь|продли(?: таймер)?(?: на)?|накинь|еще)(?: еще)? (\d+|одну|минуту|две|три|пять|десять|полминуты)?\s*(минут[уы]?|секунд[уы]?)?(?: (?:к|на|в) таймер[а-я]*| таймер[а-я]*)?$/);
  if (m && (m[1] || m[2]) && (/таймер/.test(t) || /^(?:добавь|прибавь|накинь)/.test(t) || (/^еще/.test(t) && (m[2] || ["минуту", "полминуты"].includes(m[1]))))) {
    const n = m[1] === "полминуты" ? 30 : /^\d+$/.test(m[1] || "") ? +m[1] : ({ одну: 1, минуту: 1, две: 2, три: 3, пять: 5, десять: 10 })[m[1] || "минуту"] || 1;
    const sec = /^секунд/.test(m[2] || "") || m[1] === "полминуты" ? n : n * 60, x = list[0];
    if (typeof EXAM !== "undefined" && EXAM) x.at = +x.at + sec * 1000; else D.alarmSet(JSON.stringify(Object.assign({}, x, { at: +x.at + sec * 1000 })));
    syncSoon(); tmrShow();
    return { say: `${persona().gender === "female" ? "Добавила" : "Добавил"} ${dur(sec, true)}. Теперь осталось ${dur(left(Object.assign({}, x, { at: +x.at + (typeof EXAM !== "undefined" && EXAM ? 0 : sec * 1000) })))}.` };
  }
  if (/^(?:отмени|выключи|останови|убери|сбрось|удали)(?: все)? таймер[а-я]*$/.test(t)) {
    const gone = / все /.test(` ${t} `) || list.length === 1 ? list : list.slice(0, 1);
    gone.forEach(x => remDrop(x.id)); tmrShow();
    return { say: gone.length === 1 ? "Таймер отменён." : `${persona().gender === "female" ? "Отменила" : "Отменил"} таймеры: ${gone.length}.` };
  }
  return null;
}
const tmrFmt = (ms) => { const s = Math.max(0, Math.ceil(ms / 1000)), h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), c = s % 60;
  return h ? `${h}:${pad(m)}:${pad(c)}` : `${m}:${pad(c)}`; };
const tmrSeen = {};                                   // таймер пришёл с компьютера без from — прогресс от того, как увидели
function tmrShow() {
  if (typeof EXAM !== "undefined" && EXAM) return;
  const now = Date.now();
  TMRS = JSON.parse(D.alarms() || "[]").filter(x => x.kind === "timer" && +x.at > now - 1500 && +x.at - now < 24 * 3600e3).sort((a, b) => a.at - b.at).slice(0, 3);
  TMRS.forEach(x => { if (!x.from) x.from = tmrSeen[x.id] = tmrSeen[x.id] || now; });
  const box = $("#tmrs"); if (!box) return;
  box.hidden = !TMRS.length;
  box.innerHTML = TMRS.map(x => { const mins = Math.round((x.at - x.from) / 60000);
    const name = !x.title || /^Таймер( на .*)?$/i.test(x.title) ? (mins >= 1 ? `таймер на ${mins} мин` : "таймер") : x.title;
    return `<div class="tr" data-id="${esc(x.id)}"><svg class="pg" viewBox="0 0 36 36"><circle class="bg" cx="18" cy="18" r="15.5"/><circle class="fg" cx="18" cy="18" r="15.5" pathLength="100" stroke-dasharray="100" stroke-dashoffset="0"/></svg>`
      + `<div class="tt"><b></b><span>${esc(name)}</span></div><button class="x" aria-label="Отменить таймер">${X_SVG}</button></div>`; }).join("");
  $$("#tmrs .x").forEach(b => b.onclick = () => { D.alarmCancel(b.closest(".tr").dataset.id); syncSoon(); tmrShow(); });
  clearInterval(tmrIv); tmrRead = now;
  if (TMRS.length) { tmrIv = setInterval(tmrDraw, 250); tmrDraw(); }
}
function tmrDraw() {
  const now = Date.now();
  if (now - tmrRead > 2000) return tmrShow();             // отменили в шторке, сработал, пришёл с компьютера — перечитать
  TMRS.forEach(x => { const r = $(`#tmrs .tr[data-id="${CSS.escape(x.id)}"]`); if (!r) return;
    const left = +x.at - now, all = Math.max(1000, +x.at - x.from);
    $(".tt b", r).textContent = tmrFmt(left); r.classList.toggle("end", left <= 10000);
    $(".fg", r).style.strokeDashoffset = String(Math.min(100, Math.max(0, 100 - left / all * 100))); });
  if (TMRS.every(x => +x.at < now - 1500)) tmrShow();
}

/* ---------- быстрые команды без модели (работают и без интернета) ---------- */
/* -> {say, card?, silent? (не озвучивать), switchTo?/question? (передать другому персонажу)} или null — тогда решает модель.
   Фразы — только целиком (^…$): похожая, но длиннее просьба уходит модели, а не исполняется наполовину. */
/* «стоп» ослышан: «Ctop.», «Сстоп», «Стоб», «Паузу» (отзыв 11.10) — то же, что stop_word на компьютере (engine_base.py):
   латиница — по виду (C→С, p→р) и по звуку (p→п), затем близость к стоп-словам не меньше 0,8 по числу правок */
const STOP_CORE = ["стоп", "пауза", "хватит", "замолчи", "помолчи", "прекрати", "остановись"];
const STOP_EXACT = new Set([...STOP_CORE, "стой", "тихо", "отмена", "стопэ", "стоб", "stop", "достаточно", "замолкни", "перестань", "отбой"]);
const STOP_FILL = new Set(["ну", "а", "все", "уже", "пожалуйста", "давай", "же", "так", "ладно", "хорошо", "окей", "ок"]);
const LAT_LOOK = { a: "а", c: "с", e: "е", o: "о", p: "р", x: "х", y: "у", k: "к", t: "т", m: "м", h: "н", b: "в" };
const LAT_PHON = { a: "а", b: "б", c: "с", d: "д", e: "е", f: "ф", g: "г", h: "х", i: "и", k: "к", l: "л", m: "м", n: "н", o: "о", p: "п", r: "р", s: "с", t: "т", u: "у", v: "в", y: "ы", z: "з" };
function wordSimilar(a, b) {
  let prev = Array.from({ length: b.length + 1 }, (_, j) => j);
  for (let i = 1; i <= a.length; i++) {
    const cur = [i];
    for (let j = 1; j <= b.length; j++) cur.push(Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] !== b[j - 1] ? 1 : 0)));
    prev = cur;
  }
  return 1 - prev[b.length] / Math.max(a.length, b.length, 1);
}
function stopWord(w) {
  w = String(w || "").toLowerCase().replace(/ё/g, "е");
  if (STOP_EXACT.has(w)) return w === "stop" || w === "стоб" || w === "стопэ" ? "стоп" : w;
  const c = [w];
  if (/[a-z]/.test(w)) c.push(w.replace(/[a-z]/g, (x) => LAT_LOOK[x] || x), w.replace(/[a-z]/g, (x) => LAT_PHON[x] || x));
  for (const x of c) if (STOP_EXACT.has(x)) return x;
  for (const x of c) {
    if (x.length < 4 || /[a-z]/.test(x)) continue;
    let best = null, r = 0;
    for (const s of STOP_CORE) { const k = wordSimilar(x, s); if (k > r) { r = k; best = s; } }
    if (r >= 0.8) return best;
  }
  return null;
}
/* фраза целиком — «стоп» (с вежливыми словами): → стоп-слово, иначе null */
function stopPhrase(t) {
  const ws = String(t || "").toLowerCase().replace(/[^\p{L}\s]/gu, " ").split(/\s+/).filter(Boolean);
  if (!ws.length || ws.length > 4) return null;
  let hit = null;
  for (const w of ws) { if (STOP_FILL.has(w.replace(/ё/g, "е"))) continue; const s = stopWord(w); if (!s) return null; hit = hit || s; }
  return hit;
}

async function quick(text) {
  { const bq = await bugQuick(text.replace(/^[А-ЯЁA-Z][а-яёa-z-]+\s*,\s*(?=\S)/, (m) => findPersona(m.replace(/[\s,]/g, ""), true) ? "" : m)); if (bq) return bq; }
  // «Лира, позвони…», «Лира открой сканер» — имя персонажа в начале не мешает быстрым ответам
  const t = text.toLowerCase().replace(/ё/g, "е").replace(/[.!?,]+$/g, "").replace(/\s+/g, " ").trim()
    .replace(/^([а-яa-z-]+)\s*,?\s+(?=\S)/, (m, w) => findPersona(w, true) ? "" : m);
  if (NEW_CONV_RX.test(t) || NEW_CONV_RX.test(t.replace(/^\S+\s+/, ""))) { convReset(); return { say: "Хорошо, начинаем с чистого листа." }; }
  // «запиши в заметки …», «добавь в заметки …», «заметка: …» — сразу в заметки, без модели: модель иногда отвечала
  // «Записала.», не вызвав save_note, и заметка терялась (отзыв 11.10). Текст — как сказан, заголовок — первые слова.
  // «запланируй на сегодня: в 13 …, в 16 …» — дела дня; «я позвонил в банк», «готово, купил хлеб» — отметка (17.10, без модели)
  { const pq = planQuick(text); if (pq) return pq; }
  { const dq = doneQuick(text); if (dq) return dq; }
  { const n = noteQuick(text); if (n) return { say: n }; }
  { const f = factQuick(text); if (f) return { say: f }; }
  // «покажи напоминания», «какие у меня напоминания» — открыть и сказать, сколько (модель иногда отвечала «чистый лист»,
  // не посмотрев, — отзыв 11.10)
  { const tq = t.replace(/^([а-яa-z-]+)\s*,?\s+(?=\S)/, (m, w) => findPersona(w, true) ? "" : m);
    if (/^(?:(?:покажи|открой|прочитай|какие|что|есть ли)\s+)?(?:у\s+меня\s+)?(?:есть\s+)?(?:мои\s+|все\s+)?(?:напоминани[яй]|будильники)(?:\s+(?:у\s+меня|есть|на\s+сегодня|на\s+завтра))?$/.test(tq)) {
      const l = alarmsNow().sort((x, y) => x.at - y.at), jobs = (mind().jobs || []).filter(j => !j.paused);
      setTimeout(() => { openSheet("#sh-day"); dayTab = "rem"; $$("#day-tabs button").forEach(x => x.classList.toggle("on", x.dataset.t === "rem")); renderDay(); }, 200);
      if (!l.length && !jobs.length) return { say: "Напоминаний нет. Скажите: «напомни завтра в 9 позвонить маме»." };
      const near = l.length === 1 ? ` ${whenText(new Date(l[0].at))} — ${l[0].title}.` : l.length ? ` Ближайшие: ${l.slice(0, 4).map(x => `${whenText(new Date(x.at))} — ${x.title}`).join("; ")}.` : "";
      return { say: `Напоминаний: ${l.length}${jobs.length ? `, и дел по расписанию: ${jobs.length}` : ""}.${near}` };
    } }
  // «покажи заметки», «мои заметки», «что у меня в заметках» — открыть их и коротко сказать, сколько и какая последняя
  { const tq = t.replace(/^([а-яa-z-]+)\s*,?\s+(?=\S)/, (m, w) => findPersona(w, true) ? "" : m).replace(/^что\s+у\s+меня\s+в\s+/, "что в ");
    if (NOTES_SHOW_RX.test(tq) || /^что в заметках$/.test(tq)) {
      const all = notes().slice().sort((x, y) => (+y.time || 0) - (+x.time || 0));
      setTimeout(() => { openSheet("#sh-day"); dayTab = "notes"; $$("#day-tabs button").forEach(x => x.classList.toggle("on", x.dataset.t === "notes")); renderDay(); }, 200);
      const k = all.length, w = k % 10 === 1 && k % 100 !== 11 ? "заметка" : [2, 3, 4].includes(k % 10) && ![12, 13, 14].includes(k % 100) ? "заметки" : "заметок";
      // названия — коротко и целиком (без обрезанного «…»), последние три
      const names = all.slice(0, 3).map(n => String(n.title || "").replace(/…$/, "").split(/\s+/).slice(0, 5).join(" ")).filter(Boolean);
      return { say: !k ? "Заметок пока нет. Скажите: «запиши в заметки…»" : `Вот ваши заметки — ${k} ${w}, новые сверху` + (names.length ? `: ${names.map(x => `«${x}»`).join(", ")}${k > 3 ? " и другие" : ""}.` : ".") };
    } }
  // «отсканируй код», «открой сканер», «сканер qr» — сразу сканер, без модели
  const SCAN_OBJ = "(?:код|qr|кьюар|ку ар|qr[- ]?код|кьюар[- ]?код|ацтек|aztec|штрих[- ]?код|дата ?матрикс|data ?matrix|датаматрикс|товар|этикетку|упаковку|маркировку|честный знак|ценник)";
  // «Лира, открой сканер» / «Лира открой сканер» — имя в начале не мешает (иначе фраза уходила модели, и та отвечала
  // «открыла сканер», не открыв его — отзыв 11.10)
  const tn = t.replace(/^([а-яa-z-]+)\s*,?\s+(?=\S)/, (m, w) => findPersona(w, true) ? "" : m);
  if (new RegExp(`^(?:(?:открой|запусти|включи|покажи)\\s+)?(?:сканер|сканирование)(?:\\s+(?:кодов|${SCAN_OBJ}))?$|^(?:от|про)?сканируй(?:\\s+(?:мне\\s+)?(?:этот\\s+|эту\\s+)?${SCAN_OBJ})?$|^(?:считай|прочитай|проверь)\\s+(?:этот\\s+|эту\\s+)?${SCAN_OBJ}$`).test(tn))
    { setTimeout(() => scanCode(), 300); return { say: "Наведите камеру на код." }; }
  // «спасибо», «спасибо большое», «ладно, благодарю» — коротко и вежливо, без модели (как на компьютере, отзыв 11.10)
  if (/^(?:(?:ну|ладно|хорошо|окей|ок|отлично|супер)[\s,]+)?(?:спасибо|благодарю|спс)(?:[\s,]+(?:большое|огромное|тебе|вам|за помощь|за все|очень))*$/.test(t))
    return { say: ["Пожалуйста!", "Обращайтесь!", "Пожалуйста, обращайтесь!"][Math.floor(Math.random() * 3)] };
  { // позвать персонажа: «позови Патрика», «дай Лиру», «Патрик, как думаешь…»
    let m = t.match(/^(?:позови(?:те)?|позвать|зови|пригласи|дай|переключи(?:сь)? на|передай(?: слово)?)\s+(\S+)(?:\s+(?:пожалуйста|сюда))?$/);
    let p = m && findPersona(m[1]);
    if (p) return p.id === persona().id ? { say: "Я здесь." } : { say: "", switchTo: p.id };
    m = text.trim().match(/^([А-ЯЁA-Z][а-яёa-z-]+)\s*[,!]\s*([\s\S]+)$/);
    p = m && findPersona(m[1], true);
    if (p && p.id !== persona().id && m[2].trim().length > 1) return { say: "", switchTo: p.id, question: m[2].trim() };
  }
  { const sw = stopPhrase(t); if (sw) { const rq = await radioQuick(sw); if (rq) return rq; return { say: "Хорошо.", silent: true, stop: true }; } }
  const rq = await radioQuick(t); if (rq) return rq;
  { const fs = freeSpaceQuick(t); if (fs) return fs; }
  if (/^(который час|сколько времени|сколько сейчас времени)$/.test(t)) { const d = new Date(); return { say: `Сейчас ${d.getHours()}:${pad(d.getMinutes())}.` }; }
  { const w = t.match(/^(?:сколько (?:сейчас )?(?:времени|время)|который (?:сейчас )?час|какое (?:сейчас )?время)(?: сейчас)? (в|во) ([а-яё][а-яё -]{1,30}?)(?: сейчас)?$/);
    if (w) { const said = await worldTime(w[2], w[1]); if (said) return { say: said }; } }
  if (/^(какое (сегодня )?число|какой сегодня день)$/.test(t)) { const d = new Date(); return { say: `Сегодня ${WD[d.getDay()]}, ${d.getDate()} ${MON[d.getMonth()]}.` }; }
  let m;
  // «Досуг» (24.10): «Лира, давай поиграем», «хочу поиграть», «поиграем в змейку» — полка игр без модели.
  // «давай сыграем в города» — разговорная игра, её ведёт модель (сюда не попадает: только свои игры)
  { const G = "(?:змейк\\S*|змею|гонк\\S*|кирпичик\\S*|арканоид\\S*|пилот\\S*|самолет\\S*|самолетик\\S*|бип\\S*|бегалк\\S*|блоки|тетрис\\S*|конфетк\\S*|три в ряд|слияни\\S*|2048|судоку|пятнашк\\S*|реверси|отелло|крестик\\S*(?:[\\s-]+нолик\\S*)?|нолик\\S*|кроссворд\\S*|пять букв|вордл\\S*|ог[оа]н[её]к\\S*|огоньк\\S*|сказк\\S*)";
    const PLAY_RX = new RegExp(`^(?:(?!не\\s)[а-я-]+[\\s,]+)?(?:(?:ну|а|давай|теперь|можешь)\\s+)*(?:(?:поиграем|сыграем|поиграть|поиграй со мной|сыграй со мной)(?:\\s+(?:во что-?\\s*нибудь|в игр[уы]|немного|чуть-?\\s*чуть|в ${G}))*|хочу (?:поиграть|играть|в игр[уы])(?: в ${G})?|(?:открой|запусти|включи|покажи) (?:игры|игру|досуг|аркаду|${G})(?: ${G})?|во что (?:бы )?(?:поиграть|поиграем|сыграть))(?: пожалуйста)?$`);
    if (PLAY_RX.test(t)) {
      const GM = [["snake", /змейк|змею/, "Змейку"], ["racer", /гонк/, "Гонку"], ["bricks", /кирпичик|арканоид/, "Кирпичики"], ["plane", /пилот|самолет/, "Небесного пилота"], ["bip", /(?:^|\s)(?:бип|бегалк)/, "Бипа"],
        ["blocks", /блоки|тетрис/, "Блоки"], ["candy", /конфетк|три в ряд/, "Конфетки"], ["merge", /слияни|2048/, "Слияние"], ["sudoku", /судоку/, "Судоку"], ["fifteen", /пятнашк/, "Пятнашки"], ["reversi", /реверси|отелло/, "Реверси"],
        ["tictac", /крестик|нолик/, "Крестики-нолики"], ["crossword", /кроссворд/, "Кроссворд"], ["words", /пять букв|вордл/, "«Пять букв»"], ["glow", /ог[оа]н[её]к|огоньк|сказк/, "«Огонька»"]];
      const g = GM.find(([, rx]) => rx.test(t));
      if (!feat("games")) return { say: "«Досуг» выключен. Включить — «Настройки» → «Ещё» → «Возможности»." };
      setTimeout(() => playOpen(g ? g[0] : ""), 400);
      return { say: g ? `Открываю ${g[2]}.` : "Давайте! Выбирайте игру." };
    } }
  // фонарик — сразу, без модели. №227 (24.10): «Лера выключи фонарик», «выключи фонарик на телефоне», «фонарик включён,
  // выключи его» уходили модели, та отвечала «Фонарик выключен.», не выключив. Имя (и ослышка имени) в начале не мешает.
  if ((m = t.match(/^(?:(?!не[\s,])[а-яё-]+[\s,]+)?(?:(?:а\s+)?(?:фонарик|фонарь)\s+(?:(?:всё\s+|все\s+|ещё\s+|еще\s+)?(?:включ[её]н|горит|не\s+выключ[а-яё]*|светит)[\s,]+))?(?:(включи|зажги|выключи|отключи|погаси|убери)\s+(?:мне\s+)?(фонарик|фонарь|вспышку|его)|(посвети)(?:\s+мне)?(?:\s+фонариком)?|(?:фонарик|фонарь)\s+(включи|выключи|отключи|погаси))(?:\s+на\s+телефоне)?(?:,?\s+пожалуйста)?$/))
      && (m[2] !== "его" || /фонар/.test(t))) {
    const on = !/выключи|отключи|погаси|убери/.test(m[1] || m[4] || ""); return { say: devTorch(on) ? (on ? "Фонарик включён." : "Фонарик выключен.") : "Фонарик не нашёлся." };
  }
  // «тише» — заметно (−20%), «чуть тише» — −10%, «намного тише» — −35%; и «сделай радио тише», «музыку потише»
  if ((m = t.match(/^(?:сделай\s+)?(?:радио\s+|музыку\s+|звук\s+)?(?:(еще|ещё)\s+)?(чуть|чуть-чуть|немного|немножко|слегка|намного|гораздо|сильно|значительно|совсем)?\s*(?:по)?(громче|тише)(?:\s+(?:радио|музыку|звук))?(?:\s+пожалуйста)?$|^(прибавь|увеличь|убавь|уменьши)\s+(?:звук|громкость)$/))) {
    const up = m[3] ? m[3] === "громче" : /прибавь|увеличь/.test(m[4]);
    const step = /чуть|немн|слегка/.test(m[2] || "") ? 10 : /намного|гораздо|сильно|значит|совсем/.test(m[2] || "") ? 35 : 20;
    return { say: `Громкость ${devVolume(up ? "up" : "down", step)}%.`, silent: true };
  }
  if ((m = t.match(/^(?:громкость|звук) (?:на )?(\d{1,3}|[а-я ]+?)(?: процент[а-яё]*|%)?$/)) && wordsNum(m[1]) != null) return { say: `Громкость ${devVolume("set", wordsNum(m[1]))}%.`, silent: true };
  if (/^(выключи|отключи) звук$|^без звука$/.test(t)) { devVolume("mute", 0); return { say: "Звук выключен.", silent: true }; }
  { const tc = timerVoice(t); if (tc) return tc; }        // «сколько осталось?», «добавь минуту», «отмени таймер»
  if ((m = t.match(/^(?:поставь |заведи |запусти )?таймер (?:на )?(.+?) (секунд[а-яё]*|минут[а-яё]*|час[а-яё]*)$/))) {
    const n = wordsNum(m[1]); if (n != null && n > 0) {
      const ms = m[2].startsWith("сек") ? n * 1000 : m[2].startsWith("мин") ? n * 60000 : n * 3600000;
      addAlarm(`Таймер на ${m[1]} ${m[2]}`, new Date(Date.now() + ms), "timer", "");
      return { say: `Таймер на ${m[1]} ${m[2]}.` };                  // отсчёт — сразу под обликом (#tmrs), без карточки
    }
  }
  if ((m = t.match(/^(?:поставь |заведи )?(?:будильник|разбуди меня)(.*)$/))) {
    const w = parseWhen(" в " + m[1].replace(/^\s*(на|в)\s+/, "").trim() + " ") || parseWhen(m[1]);
    if (w) { const x = addAlarm("Будильник", w.at, "alarm", w.repeat); return { say: `Будильник ${REP_RU[w.repeat] ? REP_RU[w.repeat] + ", " : ""}${whenText(w.at)}.`, card: alarmCard(x) }; }
  }
  if ((m = t.match(/^напомни(?:те)?(?: мне)?\s+(.+)$/)) || (m = t.match(/^напоминай(?: мне)?\s+(.+)$/))) {
    const w = parseWhen(m[1]);
    if (w) {
      let what = remindWhat(w.rest);
      // «напомни об этом / о ней / о последней заметке завтра в 10» — про что-то сказанное раньше (отчёт №66: вышло
      // напоминание «Этом часов утра»). Только что записанная заметка — она; иначе пусть решает модель (она видит разговор)
      if (/^(?:об?\s+)?(?:этом|это|этой|этого|ней|нем|нём|нему|ней|том|последн[а-яё]*\s+заметк[а-яё]*|заметк[а-яё]*|сказанном|нашем разговоре)(?:\s|$)/.test(what) || !what) {
        const last = notes().slice().sort((a, b) => (+b.time || 0) - (+a.time || 0))[0];
        const fresh = last && Date.now() - (+last.time || 0) < 30 * 60e3;
        if (!fresh && what) return null;
        const body = fresh ? noteShown(last.text || last.title || "").split(/\n/)[0].trim() : "";
        what = body ? "Заметка: " + (body.length > 90 ? body.slice(0, 90).replace(/\s+\S*$/, "") + "…" : body) : "";
      }
      if (what) { const x = addAlarm(what[0].toUpperCase() + what.slice(1), w.at, "reminder", w.repeat);
        return { say: `Напомню ${REP_RU[w.repeat] ? REP_RU[w.repeat] + ", " : ""}${whenText(w.at)}: ${what}.`, card: alarmCard(x) }; }
    }
  }
  if ((m = text.trim().match(/^(?:напиши|отправь|скинь|перешли)(?: сообщение)?\s+(?:в|во)\s+(макс\S*|max|телеграм\S*|тг|телег\S*|ватсап\S*|вотсап\S*|вацап\S*|whatsapp|вайбер\S*|viber|вк|вконтакте)[\s:,—-]+([\s\S]+)$/i)))
    return { say: sendTo(msgApp(m[1]), m[2].trim()) };
  if (relAsk && Date.now() - relAsk.at < 90000 && t.split(/\s+/).length <= 5 && !/^(?:нет|не надо|отмена|не звони)/.test(t)) {
    // ответ на «Как жена записана в контактах?» — звоним и запоминаем
    const rel = relAsk.rel; relAsk = null;
    const name = t.replace(/^(?:она|он)?\s*(?:записан[аоы]?|записана как|записан как|это)\s+/, "").replace(/^(?:позвони(?:ть)?|набери)\s+/, "").trim();
    const r = await doCall(name);
    if (r.ok && lastCall) { relRemember(rel, lastCall); lastCall.rel = rel; return { say: `${r.text} Запомнил${persona().gender === "female" ? "а" : ""}: ${REL_RU[rel]} — «${lastCall.name || name}».` }; }
    return { say: r.text };
  }
  relAsk = null;
  if ((m = t.match(/^нет(?=[\s,])[\s,]*(?:(?:ты\s+)?не\s+(?:понял[аи]?|туда|тому|та|тот)[\s,]*)?(?:(?:нужно|надо|я\s+(?:просил|сказал)[аи]?)\s+)?(?:позвони(?:ть)?|набери|набрать|звони)\s+(.+)$/))
      && lastCall && lastCall.rel && Date.now() - lastCall.at < 300000) {
    // «нет, нужно позвонить Наташа МТС» сразу после звонка «жене» — поправка: звоним и запоминаем, кто есть кто
    const rel = lastCall.rel, r = await doCall(m[1]);
    if (r.ok && lastCall) { relRemember(rel, lastCall); lastCall.rel = rel; return { say: `${r.text} Запомнил${persona().gender === "female" ? "а" : ""}: ${REL_RU[rel]} — «${lastCall.name || m[1]}».` }; }
    if (r.final) return { say: r.text };
  }
  // «отправь Людмиле Исаевой — привет, как дела», «напиши маме: задержусь» — близкому через Dewiar, сразу
  // как пишет распознавание (18.10, экзамен «как в жизни»): «отправь сообщение андрею привет как дела» — без двоеточия;
  // «а теперь лёхе напиши во сколько встречаемся» — имя впереди
  if (clLoad().people.length && (m = t.match(/^(?:(?:а|и)\s+)?(?:теперь\s+)?(\S+(?:\s+\S+)?)\s+(?:напиши|отправь|передай|скажи)\s+(?!сообщение\b)(.+)$/))
      && !/^(?:напиши|отправь|передай|скажи|сообщи|мне|ему|ей|им)$/.test(m[1]) && /[еюиу]$/.test(m[1])) {   // «лёхе напиши» — кому, а не «Андрей, напиши стих»
    const p = clMatch(m[1], clLoad().people, true), body = text.replace(/^.*?\s(?:напиши|отправь|передай|скажи)\s+/i, "").replace(/^[\s,:;—–-]+/, "").replace(/^(?:что|чтобы)\s+/i, "").trim();
    if (p && body) {
      try { const it = await clSend(p.pid, body.charAt(0).toUpperCase() + body.slice(1)); return { say: `${persona().gender === "female" ? "Отправила" : "Отправил"} через Dewiar. ${it.to} услышит: «${body}».` }; }
      catch (e) { return { say: e.message }; }
    }
  }
  if ((m = t.match(/^(?:(?:а|и)\s+)?(?:теперь\s+)?(?:напиши|отправь|передай|скажи|сообщи)(?:\s+сообщение)?\s+(.+)$/)) && clLoad().people.length) {
    const ws = m[1].split(" ");
    for (let k = Math.min(3, ws.length - 1); k >= 1; k--) {
      const p = clMatch(ws.slice(0, k).join(" "), clLoad().people, true); if (!p) continue;
      const orig = text.replace(/^.*?(?:^|[\s,])(?:напиши|отправь|передай|скажи|сообщи)(?:\s+сообщение)?\s+/i, "").split(/\s+/).slice(k).join(" ");
      const body = orig.replace(/^[\s,:;—–-]+/, "").replace(/^(?:что|чтобы)\s+/i, "").trim();
      if (!body) break;
      try { const it = await clSend(p.pid, body.charAt(0).toUpperCase() + body.slice(1)); return { say: `${persona().gender === "female" ? "Отправила" : "Отправил"} через Dewiar. ${it.to} услышит: «${body}».` }; }
      catch (e) { return { say: e.message }; }
    }
  }
  // «перезвони», «позвони ей ещё раз», «набери снова» — тому же, кому звонили (и через Dewiar — тоже через Dewiar)
  if (/^(?:перезвони|повтори звонок|(?:набери|позвони|звони)(?:\s+(?:ей|ему|им|ей же|ему же))?\s+(?:ещ[её] раз|снова|опять))(?:\s+пожалуйста)?$/.test(t)) return { say: (await doCall("ещё раз")).text };
  if (/^(?:(?:можешь|можно|пожалуйста|давай)\s+)?(?:позвони(?:ть)?|набери|набрать|звони|звякни)(?:\s+(?:пожалуйста|мне|кому-нибудь|кое-кому))?$/.test(t)) return { say: "Кому позвонить?" };
  // «видеозвонок Люде», «сделай видеозвонок маме» — близкому по видео (doCall понимает «по видео»)
  if ((m = t.match(/^(?:(?:сделай|набери|начни)\s+)?видеозвонок\s+(.+)$/))) { const r = await doCall(m[1] + " по видео"); if (r.ok || r.final) return { say: r.text }; }
  // «позвони Наташе МТС» — сразу; «позвони жене, а если не ответит — напиши…» (условие, второе действие) — модели
  if ((m = t.match(/^(?:(?:можешь|можно|пожалуйста|давай)\s+)?(?:позвони(?:ть)?|набери|набрать|звони|звякни)\s+(.+)$/))
      && !/[,;:—]|(?:^|\s)(?:если|когда|потом|затем|и|а|но|или|скажи|напиши|отправь|сообщение|передай|через|после|пока)(?=\s|$)/.test(m[1])) {
    const r = await doCall(m[1]); if (r.ok || r.final) return { say: r.text }; }
  if ((m = t.match(/^(?:открой|запусти)\s+(.+)$/)) && !/сайт|страниц|ссылк/.test(m[1])) {
    const name = openAppSmart(m[1]); if (name) return { say: `Открываю ${name}.`, silent: true };
  }
  if (S.home.token && !D.web) { const r = await homeQuick(t); if (r) return r; }
  return null;
}

/* радио голосом без модели: «включи радио», «поставь джаз», «Европа Плюс», «дальше», «пауза», «продолжи», «выключи радио» */
const R_VERBS = "(?:включи(?:те)?|поставь(?:те)?|запусти(?:те)?|вруби|врубай|давай|хочу|сыграй|играй|поиграй)";
async function radioQuick(t) {
  const said = (r) => r.superseded ? { say: "", silent: true } : r.ok ? { say: `Играет «${r.station.name}».`, silent: false } : { say: r.text.replace(/^Ошибка: /, "").replace(/ Похоже на сеть.*$| Предложи.*$| Скажи пользователю.*$/, "") };
  if (radio.on() && /^(стоп|хватит|пауза|паузу|поставь на паузу|тихо|замолчи|приостанови)$/.test(t)) { radio.pause(); return { say: "Пауза.", silent: true }; }
  // «дальше», «другое радио поставь», «смени станцию» — и пока играет, и сразу после станции, которая не заиграла
  if ((radio.on() || radio.recent()) && /^(?:(?:а|ну|давай|включи|поставь|еще|ещё)\s+)*(?:дальше|следующ[а-яё]*|другую|другое|друго[йе]|переключи(?:сь)?|смени|поменяй|не нравится|некст)(?:\s+(?:станци[а-яё]*|радио|радиостанци[а-яё]*|волн[а-яё]*|музык[а-яё]*))?(?:\s+(?:поставь|включи|давай))?(?:\s+пожалуйста)?$/.test(t))
    return said(await radio.next());
  if (radio.state().state === "paused" && /^(продолжи|продолжай|играй|сними с паузы|включи обратно|верни( радио| музыку)?|дальше играй|play|плей)$/.test(t)) {
    radio.resume(); return { say: "Продолжаю.", silent: true };
  }
  if (/^(?:выключи|останови|убери|отключи|заглуши|хватит)\s+(?:музыку|радио|музычку)$/.test(t)) {
    if (!radio.on()) return { say: "Радио и так не играет." }; radio.stop(); return { say: persona().gender === "female" ? "Выключила радио." : "Выключил радио.", silent: true };
  }
  if (new RegExp(`^(?:${R_VERBS}\\s+)?(?:мне\\s+)?(?:какую-нибудь\\s+|какую-то\\s+|немного\\s+)?(?:музыку|музычку|радио|что-нибудь\\s+послушать)(?:\\s+пожалуйста)?$`).test(t))
    return said(await radio.play(""));
  let m = t.match(new RegExp(`^${R_VERBS}\\s+(.+)$`)) || t.match(/^(?:музыку|радио)\s+(.+)$/);
  if (m && !/яндекс|ютуб|youtube|spotify|спотифай|вк музык/.test(m[1])) {
    const rest = m[1].replace(/\s+пожалуйста$/, "");
    const exact = radio.list().some(x => [x.name.toLowerCase().replace(/ё/g, "е"), ...x.aliases].includes(rest.replace(/^радио\s+/, "").replace(/^станцию\s+/, "")) ||
      [x.name.toLowerCase().replace(/ё/g, "е"), ...x.aliases].includes(rest));
    if (exact || (/радио|музык|музычк|станци|волн/.test(rest) && radio.match(rest).length)) return said(await radio.play(rest));
  }
  return null;
}

/* «открой телеграм» → Telegram: названия приложений по-русски и по-английски */
const APP_ALIAS = { "телеграм": ["Telegram"], "телеграмм": ["Telegram"], "макс": ["MAX", "Max", "МАКС"], "max": ["MAX", "Max"], "ютуб": ["YouTube"], "ютьюб": ["YouTube"], "ватсап": ["WhatsApp"], "вотсап": ["WhatsApp"],
  "вацап": ["WhatsApp"], "вайбер": ["Viber"], "инстаграм": ["Instagram"], "хром": ["Chrome"], "гугл": ["Google"], "карты": ["Карты", "Maps", "Яндекс Карты"],
  "навигатор": ["Навигатор", "Яндекс Навигатор"], "спотифай": ["Spotify"], "тикток": ["TikTok"], "тик ток": ["TikTok"], "вк": ["VK"], "вконтакте": ["VK"],
  "почта": ["Gmail", "Почта", "Mail"], "почту": ["Gmail", "Почта", "Mail"], "камера": ["Камера", "Camera"], "камеру": ["Камера", "Camera"], "калькулятор": ["Калькулятор", "Calculator"],
  "галерея": ["Галерея", "Gallery", "Фото", "Photos"], "галерею": ["Галерея", "Gallery", "Фото", "Photos"], "фото": ["Фото", "Photos", "Галерея", "Gallery"],
  "настройки": ["Настройки", "Settings"], "часы": ["Часы", "Clock"], "календарь": ["Календарь", "Calendar"], "музыка": ["Музыка", "Music", "Яндекс Музыка"],
  "музыку": ["Яндекс Музыка", "Музыка", "Music", "Spotify"], "сбер": ["СберБанк", "Сбербанк"], "тинькофф": ["Т-Банк", "Tinkoff"], "т банк": ["Т-Банк"],
  "озон": ["Ozon"], "вайлдберриз": ["Wildberries"], "госуслуги": ["Госуслуги"], "алиса": ["Алиса", "Яндекс"], "переводчик": ["Переводчик", "Translate"], "заметки": ["Заметки", "Keep", "Notes"],
  "браузер": ["Chrome", "Браузер", "Яндекс Браузер", "Firefox"], "контакты": ["Контакты", "Contacts"], "телефон": ["Телефон", "Phone"], "сообщения": ["Сообщения", "Messages"] };
function openAppSmart(name) {
  const n = String(name || "").toLowerCase().replace(/ё/g, "е").replace(/^(приложение|программу)\s+/, "").trim();
  let r = D.openApp(n); if (r) return r;
  for (const alt of APP_ALIAS[n] || []) { r = D.openApp(alt); if (r) return r; }
  return "";
}

let lastCall = null;                               // «перезвони», «набери ещё раз» — тому же
/* Родные словом: «позвони жене / маме / мужу». Контакт так обычно не записан («Наташа МТС»), а «жене» похоже на «Женя» —
   поэтому родство не ищем по похожести имён: берём запомненного (S.relations), контакт с таким же словом целиком
   («Мама», «Жена»), иначе спрашиваем «Как жена записана в контактах?» и запоминаем ответ. Поправка «нет, позвони
   Наташа МТС» сразу после звонка родному — тоже запоминается. */
const REL = { "жена": /^(?:жен[аеуы]|женой|жёнушк[аеуи]|женушк[аеуи])$/, "муж": /^(?:муж|мужу|мужа|мужем)$/, "мама": /^(?:мам[аеуы]|мамой|мамочк[аеуи]|мамуль?[аеуи]?)$/,
  "папа": /^(?:пап[аеуы]|папой|папочк[аеуи])$/, "сын": /^(?:сын|сыну|сына|сыном|сынок|сынку)$/, "дочь": /^(?:доч[ьи]|дочер[иью]|дочк[аеуи]|дочкой)$/,
  "брат": /^(?:брат|брату|брата|братом|братик[уа]?)$/, "сестра": /^(?:сестр[аеуы]|сестрой|сестрёнк[аеуи]|сестренк[аеуи])$/,
  "бабушка": /^(?:бабушк[аеуи]|бабуле?|бабуля)$/, "дедушка": /^(?:дедушк[аеуи]|деду(?:ле)?|деда)$/ };
const REL_RU = { "жена": "жена", "муж": "муж", "мама": "мама", "папа": "папа", "сын": "сын", "дочь": "дочь", "брат": "брат", "сестра": "сестра", "бабушка": "бабушка", "дедушка": "дедушка" };
function relOf(who) {
  const w = String(who || "").toLowerCase().replace(/ё/g, "е").replace(/^(?:мо(?:ей|ему|ю|й|я|им|его)|наш(?:ей|ему|у|а|ему|им)?|своей|своему|свою)\s+/, "").trim();
  return Object.keys(REL).find(k => REL[k].test(w)) || "";
}
let relAsk = null;                                 // {rel, at} — спросили «как жена записана в контактах?», ждём имя
function relRemember(rel, c) { if (!rel || !c || !c.number) return; S.relations = Object.assign({}, S.relations, { [rel]: { name: c.name || "", number: c.number } }); saveS(); }
function dial(number, name) {
  const ok = D.call(number);
  if (!ok) return { ok: false, final: true, text: "Не получилось начать звонок — телефон не открыл звонилку." };
  lastCall = { number, name, at: Date.now() };
  return { ok: true, text: D.has(CALLP) ? (name ? `Звоню: ${name}.` : "Звоню.") : `Открыл${persona().gender === "female" ? "а" : ""} номер${name ? " — " + name : ""}: нажмите зелёную кнопку. Чтобы звонить сразу, разрешите Dewiar звонки.` };
}
/* человек из «Близких» — звоним через Dewiar (аудио или видео), а не ищем в контактах и мессенджерах (отзыв 11.10).
   -> ответ doCall или null — не близкий (тогда телефонная книга) */
let lastClose = null;                                // последний звонок близкому через Dewiar: «перезвони» — снова ему
async function closeCallFirst(who) {
  const VRX = /\s(?:по\s+)?видео(?:звонком|связи)?$|^по\s+видео(?:связи)?\s+/i, video = VRX.test(who);
  let name = who.replace(VRX, "").trim().replace(/\s+(?:ещ[её]\s+раз|снова|опять)$/, "").trim();   // «набери людмилу снова»
  let again = null;
  if (/^(?:ещ[её]\s+раз|снова|опять|обратно)$/.test(name)) {
    if (!lastClose || (lastCall && lastCall.at > lastClose.at) || Date.now() - lastClose.at > 3 * 3600e3) return null;
    again = clLoad().people.find(x => x.pid === lastClose.pid) || null;
  }
  const p = again || (clLoad().people.length && name && !/^(?:ещ[её]\s+раз|снова|опять|обратно)$/.test(name) ? clMatch(name, clLoad().people, true) : null);
  if (!p || !(p.devs || []).length || !window.DewiarCall) return null;
  const vid = video || (again ? lastClose.video : false);
  try { await clCall(p.pid, vid); lastClose = { pid: p.pid, video: vid, at: Date.now() }; return { ok: true, final: true, text: `${vid ? "Видеозвонок" : "Звоню"} через Dewiar: ${p.name}.` }; }
  catch (e) { return { ok: false, final: true, text: e.message }; }
}
/* «на обычный мобильный телефон», «по сотовому», «на номер» — звонок через телефон, а не через Dewiar; и это не часть
   имени (24.10, владелец: «позвони на обычный мобильный телефон Исаевой Людмиле» — слова «телефон» и «на» совпали
   с контактом «Телефон На Громова 46», и звонок ушёл туда). -> {who: без этих слов, phone: просили обычный звонок} */
const PSTN_RX = /(?:^|\s)(?:(?:на|по|через)\s+)?(?:(?:обычн|простой|прост|мобильн|сотов|городск|домашн|рабоч)[а-яё]*\s+)*(?:телефон[а-яё]*|номер[а-яё]*|сотов[а-яё]*|мобильн[а-яё]*|связ[ьи])(?=\s|$)/gi;
function callTarget(who) {
  let w = String(who || ""), phone = false;
  w = w.replace(PSTN_RX, () => { phone = true; return " "; }).replace(/(?:^|\s)не\s+через\s+(?:dewiar|девиар|дэвиар)(?=\s|$)/gi, () => { phone = true; return " "; });
  return { who: w.replace(/\s+/g, " ").trim(), phone };
}
async function doCall(who) {
  who = who.replace(/^(мне|пожалуйста)\s+/, "").replace(/\s+пожалуйста$/, "").trim();
  const tg = callTarget(who); if (tg.who) who = tg.who;
  if (!tg.phone) { const c = await closeCallFirst(who); if (c) return c; }
  const rel = relOf(who);
  if (rel) {
    const known = (S.relations || {})[rel];
    if (known && known.number) { await needPerm(CALLP); const r = dial(known.number, known.name || REL_RU[rel]); if (lastCall) lastCall.rel = rel; return r; }
    let c = JSON.parse(D.contact(REL_RU[rel]) || "{}");
    if (c.need) { if (!(await needPerm(CONTACTS))) return { final: true, text: "Чтобы звонить по имени, разрешите доступ к контактам." }; c = JSON.parse(D.contact(REL_RU[rel]) || "{}"); }
    const same = c.number && String(c.name || "").toLowerCase().replace(/ё/g, "е").split(/[\s,.()-]+/).some(w => REL[rel].test(w));
    if (same && !(c.alts || []).length) { relRemember(rel, c); await needPerm(CALLP); const r = dial(c.number, c.name); if (lastCall) lastCall.rel = rel; return r; }
    relAsk = { rel, at: Date.now() };
    return { ok: false, final: true, text: `Как ${REL_RU[rel]} записан${/а$|ь$/.test(REL_RU[rel]) ? "а" : ""} у вас в контактах? Скажите имя — запомню${persona().gender === "female" ? "" : ""}.` };
  }
  who = who.replace(/^(?:мо(?:ей|ему|ю|й|я|им|его)|наш(?:ей|ему|у|а|им)?)\s+/, "").trim();
  if (/^(?:ещ[её]\s+раз|снова|опять|обратно)$/.test(who)) {
    if (!lastCall) return { ok: false, final: true, text: "Не помню, кому мы звонили. Скажите, кому позвонить." };
    await needPerm(CALLP); return dial(lastCall.number, lastCall.name);
  }
  const digits = who.replace(/[^\d+]/g, "");
  if (digits.length >= 5) { await needPerm(CALLP); return dial(digits, ""); }
  let c = JSON.parse(D.contact(who) || "{}");
  if (c.need) { if (!(await needPerm(CONTACTS))) return { final: true, text: "Чтобы звонить по имени, разрешите доступ к контактам." }; c = JSON.parse(D.contact(who) || "{}"); }
  if (!c.number) return { ok: false, final: false, text: `Не нашёл «${who}» в контактах. Скажите имя так, как оно записано в телефоне.` };
  if ((c.alts || []).length) {                      // похожих несколько — спросим, а не позвоним не тому
    const names = [c.name, ...c.alts.map(x => x.name)].slice(0, 4);
    return { ok: false, final: true, text: `В контактах несколько похожих: ${names.join(", ")}. Кому позвонить? Скажите имя целиком.` };
  }
  await needPerm(CALLP);
  return dial(c.number, c.name);
}

/* просьба про камеру: «посмотри на меня», «как я выгляжу», «покажи фото», «с фронтальной камеры», «что это» с камерой */
// просьба, где снимок уместен: камера, фото, «посмотри / что передо мной / что это / прочитай этикетку / сколько стоит…»
const PHOTO_ASK_RX = /перед\s+тобой|вокруг|в\s+рук(?:е|ах)|наряд|как\s+я\s+одет|опиши,?\s+что|расскажи,?\s+что\s+(?:ты\s+)?(?:видишь|там|тут|здесь|вокруг|перед)|камер|фот|снимок|снимк|сним(?:и|ай|ешь)|сфоткай|посмотри|глянь|взгляни|видишь|увидь|покажи|передо мной|что (?:это|тут|здесь|там) |что это[?!.\s]*$|как я выгляжу|(?<![а-яё])лиц[оеау]|прочитай|прочти|прочесть|написано|этикетк|упаковк|(?<![а-яё])состав(?:е|ом)?(?![а-яё])|(?<![а-яё])чек|вывеск|ценник|сколько стоит|переведи|определи|узнай|распознай|что за (?:растени|цвет|предмет|вещ|модел|марк|порода|гриб|птиц)|где я/i;
const CAM_ASK_RX = /перед\s+тобой|что\s+вокруг|в\s+рук(?:е|ах)|как\s+я\s+одет|оцени\s+(?:мой\s+)?наряд|опиши,?\s+что|расскажи,?\s+что\s+(?:ты\s+)?(?:видишь|там|тут|здесь|вокруг|перед)|камер|фото|снимок|снимк|сфотограф|сним(?:и|ай)|посмотри на меня|как я выгляжу|мо[её] лицо|изображени|покажи (?:мне )?(?:меня|это|его|е[её])|что (?:ты )?видишь|где я нахожусь/i;
/* ---------- границы помощника (как core/boundaries.py — менять вместе) ----------
   Правило — в systemPrompt; грубость в адрес помощника — спокойная граница в этом ходе и счётчик rude в пульс;
   отказ помощника — счётчик refused. Наружу — только числа. */
const BOUNDARY_RULE = "Твои границы. Ты помогаешь охотно и с теплом, но у тебя есть достоинство. Если тебя оскорбляют или грубят тебе — отвечай спокойно, без обиды и без заискивания: одной фразой скажи, что так тебе неприятно, и предложи продолжить по делу; не извиняйся за чужую грубость. Ты вправе отказаться от просьб унизить или травить человека, навредить кому-то, обмануть или нарушить закон — откажи коротко и честно, без нотаций, и предложи, чем можешь помочь. Обычные просьбы, шутки, ирония и крепкое словцо не в твой адрес — не повод для отказа и не повод для замечаний.";
const BOUNDARY_NOTE = "\n\nСейчас пользователь грубит тебе. Не обижайся и не заискивай: одной спокойной фразой обозначь, что так разговаривать с тобой неприятно, и, если в сообщении есть просьба, всё равно помоги с ней.";
const RUDE_RX = new RegExp("(?<![а-яё])(?:ты|тебя|тебе|тобой|вы|вас)\\s+(?:(?:и|такая|такой|такое|просто|совсем|реально|полная|полный|настоящая|настоящий|вообще|же|абсолютно|конченая|конченый|последняя|последний|редкая|редкий)\\s+){0,2}(?:дур[аы]?|дурак[а-яё]*|дурочк[а-яё]*|туп(?:ая|ой|ое|ица|ые|орыл[а-яё]*)|идиот[а-яё]*|дебил[а-яё]*|кретин[а-яё]*|придур[а-яё]*|урод[а-яё]*|тварь|твар[иью]|сволоч[а-яё]*|мразь|мраз[иью]|скотин[а-яё]*|бездар[а-яё]*|никчем[а-яё]*|никчём[а-яё]*|бесполезн[а-яё]*|су[чк][аи]|сучк[а-яё]*|бля(?:дь|ди|дина)|шлюх[а-яё]*|гнид[а-яё]*|овощ|дно|чмо|лох[а-яё]*|мудак[а-яё]*|мудил[а-яё]*|долбо[её]б[а-яё]*|у[её]б[а-яё]*|пизд[а-яё]*|х[уy][йеёя][а-яё]*|еба(?:ть|н[а-яё]*|л[а-яё]*)|[её]баная|[её]баный)(?![а-яё])|(?<![а-яё])(?:дур[аы]?|дурак[а-яё]*|дурочк[а-яё]*|туп(?:ая|ой|ое|ица|ые|орыл[а-яё]*)|идиот[а-яё]*|дебил[а-яё]*|кретин[а-яё]*|придур[а-яё]*|урод[а-яё]*|тварь|твар[иью]|сволоч[а-яё]*|мразь|мраз[иью]|скотин[а-яё]*|бездар[а-яё]*|никчем[а-яё]*|никчём[а-яё]*|бесполезн[а-яё]*|су[чк][аи]|сучк[а-яё]*|бля(?:дь|ди|дина)|шлюх[а-яё]*|гнид[а-яё]*|овощ|дно|чмо|лох[а-яё]*|мудак[а-яё]*|мудил[а-яё]*|долбо[её]б[а-яё]*|у[её]б[а-яё]*|пизд[а-яё]*|х[уy][йеёя][а-яё]*|еба(?:ть|н[а-яё]*|л[а-яё]*)|[её]баная|[её]баный)\\s*,?\\s*(?:же\\s+)?(?:ты|тебя|тебе|тобой|вы|вас)(?![а-яё])|^(?:[а-я]+,\\s*)?(?:ну\\s+|эй,?\\s+)?(?:дур[аы]?|дурак[а-яё]*|дурочк[а-яё]*|туп(?:ая|ой|ое|ица|ые|орыл[а-яё]*)|идиот[а-яё]*|дебил[а-яё]*|кретин[а-яё]*|придур[а-яё]*|урод[а-яё]*|тварь|твар[иью]|сволоч[а-яё]*|мразь|мраз[иью]|скотин[а-яё]*|бездар[а-яё]*|никчем[а-яё]*|никчём[а-яё]*|бесполезн[а-яё]*|су[чк][аи]|сучк[а-яё]*|бля(?:дь|ди|дина)|шлюх[а-яё]*|гнид[а-яё]*|овощ|дно|чмо|лох[а-яё]*|мудак[а-яё]*|мудил[а-яё]*|долбо[её]б[а-яё]*|у[её]б[а-яё]*|пизд[а-яё]*|х[уy][йеёя][а-яё]*|еба(?:ть|н[а-яё]*|л[а-яё]*)|[её]баная|[её]баный)(?![а-яё])\\s*[!.]*$|,\\s*(?:дур[аы]?|дурак[а-яё]*|дурочк[а-яё]*|туп(?:ая|ой|ое|ица|ые|орыл[а-яё]*)|идиот[а-яё]*|дебил[а-яё]*|кретин[а-яё]*|придур[а-яё]*|урод[а-яё]*|тварь|твар[иью]|сволоч[а-яё]*|мразь|мраз[иью]|скотин[а-яё]*|бездар[а-яё]*|никчем[а-яё]*|никчём[а-яё]*|бесполезн[а-яё]*|су[чк][аи]|сучк[а-яё]*|бля(?:дь|ди|дина)|шлюх[а-яё]*|гнид[а-яё]*|овощ|дно|чмо|лох[а-яё]*|мудак[а-яё]*|мудил[а-яё]*|долбо[её]б[а-яё]*|у[её]б[а-яё]*|пизд[а-яё]*|х[уy][йеёя][а-яё]*|еба(?:ть|н[а-яё]*|л[а-яё]*)|[её]баная|[её]баный)\\s*(?:[,!]|$)|(?<![а-яё])(?:заткнись|заткни\\s+пасть|закрой\\s+(?:рот|пасть)|пош[её]л\\s+(?:ты\\s+)?(?:на|в)\\s|пошла\\s+(?:ты\\s+)?(?:на|в)\\s|отвали|отъебись|отьебись|иди\\s+(?:ты\\s+)?(?:на|в)\\s+(?:хуй|жопу|задницу|пизду))", "i");
const REFUSED_RX = new RegExp("(?<![а-яё])(?:не\\s+(?:буду|стану)\\s+(?:этого\\s+)?(?:делать|помогать|писать|участвовать)|(?:вынужден[а]?\\s+)?отказать(?:ся)?|откажусь|в\\s+этом\\s+(?:я\\s+)?не\\s+помогу|с\\s+этим\\s+(?:я\\s+)?не\\s+помогу|так\\s+(?:со\\s+мной\\s+)?(?:разговаривать|говорить)\\s+(?:со\\s+мной\\s+)?неприятно|мне\\s+(?:так\\s+|очень\\s+|правда\\s+)?неприятно)", "i");
const isRude = (t) => RUDE_RX.test(String(t || "").toLowerCase().replace(/ё/g, "е"));
const isRefused = (t) => REFUSED_RX.test(String(t || "").toLowerCase().replace(/ё/g, "е"));
/* модель «сделала» действие словами, а инструмент не вызвала — частая беда второго раза: в истории уже есть «Звоню: Мама» */
const CLAIMS = [
  { rx: /(?:^|[.!—–-]\s*|,\s*)(?:хорошо,?\s*|секунду,?\s*|сейчас\s+)?(?:звоню|набираю|перезваниваю|позвоню|вызываю)(?:\s|[.!:,]|$)/i, tool: "call", what: "звонишь" },
  { rx: /(?:^|[.!]\s*)(?:хорошо,?\s*)?(?:включаю|ставлю|переключаю(?:сь)?(?:\s+на)?|запускаю)\s+(?:радио|станци|«|"|волну|[А-ЯЁA-Z])/, tool: "play_radio (или radio_control с action next, если просят другую станцию)", what: "включаешь радио" },
  { rx: /(?:^|[.!]\s*)(?:сейчас\s+)?(?:фотографирую|делаю (?:снимок|фото)|смотрю через камеру|открываю камеру)/i, tool: "take_photo", what: "фотографируешь" },
  // №227 (24.10): «выключи фонарик» — «Фонарик выключен.», а flashlight не вызван: фонарь горит, человек просит снова
  { rx: /фонар(?:ик|ь)[^.!?]{0,20}(?:выключ|включ|погас|зажж|гор(?:ит|ю))|(?:выключил[аи]?|включил[аи]?|погасил[аи]?|выключаю|включаю|гашу)\s+(?:тебе\s+|вам\s+)?(?:фонар|вспышк|св?ет)/i,
    tool: "flashlight", what: "включил(а) или выключил(а) фонарик", user: /фонар|вспышк|посвети/i },
  // просили посмотреть или показать через камеру, а в ответ «Секунду, смотрю.», «Вот.», «Показываю» — без снимка ничего не произошло
  { rx: /^(?:хорошо,?\s*|секунду,?\s*|сейчас,?\s*|конечно,?\s*)*(?:смотрю|посмотрю|гляжу|взгляну|показываю|покажу|вот(?:\s+(?:он|оно|она|фото|снимок|изображение|так))?|держи)(?:[\s,.!…]|$)/i,
    tool: "take_photo (или show_photo, если снимок уже сделан и его просят показать снова)", what: "смотришь или показываешь", user: CAM_ASK_RX },
  // просили про заметку, а в ответ голое «Записала.» / «Готово, сохранила» — без save_note заметки нет (отзыв 11.10)
  { rx: /^\s*(?:(?:готово|хорошо|сделано|конечно|да)[,.!]?\s*)?(?:записал[аи]?|сохранил[аи]?|добавил[аи]?|занесл[аи]|запомнил[аи]?)(?:\s+(?:это|её|его|всё))?\s*[.!]?\s*$/i,
    tool: "save_note", what: "сохранил(а) заметку", user: /заметк/i },
  // «Сохранила её заметкой», «Теперь она точно в твоих заметках», «сейчас создам её заново» — без save_note заметки нет (отзыв 10.10)
  { rx: /(?:сохранил[аи]?|записал[аи]?|создал[аи]?|добавил[аи]?|положил[аи]?|разместил[аи]?|сохраню|запишу|создам|добавлю)(?![а-яё])[^.!?]{0,60}(?:заметк|в заметки)|(?:теперь|уже)\s+(?:она|он|список|таблица|всё)[^.!?]{0,30}\sв\s+(?:твоих\s+|ваших\s+)?заметках/i,
    tool: "save_note", what: "сохранил(а) заметку" },
  // «Готово, калькулятор сделан», «Я сделала мини-презентацию — она уже открылась на экране» — где угодно в ответе
  { rx: /(?:^|[\s,.!—–-])(?:готово|сделал[аи]?|создал[аи]?|подготовил[аи]?|собрал[аи]?|написал[аи]?|вот)(?![а-яё])[^.!?]{0,80}(?:калькулятор|игр[уаы]|страниц|программ|приложени|таймер|конвертер|викторин|презентаци|слайд|открытк|шпаргалк)|(?:открыл[аио]?сь|открыт[аоы]?|появил[аио]?сь)\s+(?:у\s+тебя\s+|тебе\s+)?на\s+экран/i,
    tool: "make_app", what: "сделал программу, страницу или презентацию",
    // только когда такую вещь и просили: «вот вариант поздравления — можно написать на открытке» — не обещание программы
    // (экзамен 0.6.42: Лира дописала к готовому поздравлению «Секунду — собираю. Ничего не вышло…»)
    // и не на «дочка нарисовала мне открытку» — нужна именно просьба сделать (экзамен 0.6.43)
    user: /(?:сделай|создай|напиши|собери|подготовь|нарисуй|сверстай|покажи|открой|запусти|хочу)[а-яё]*\s+(?:мне\s+|нам\s+|ей\s+|ему\s+)?(?:[а-яё-]+\s+){0,2}?(?:калькулятор|игр[уаыое]|программ|приложени|таймер|конвертер|викторин|презентаци|слайд|страниц|сайт|открытк|шпаргалк)|на\s+экран/i },
  // «Открыла сканер», «Наведите камеру на код» — без scan_code сканер не открылся (отзыв 11.10)
  { rx: /(?:открыл[аи]?|открываю|запускаю|запустил[аи]?|включил[аи]?|включаю)\s+(?:тебе\s+|вам\s+)?сканер|наведите\s+(?:камеру|телефон)\s+на\s+(?:код|qr|штрих)/i,
    tool: "scan_code", what: "открыл(а) сканер" },
  // «Открыла Gmail и создала новое письмо» — а ни приложения, ни письма (отзыв 13.10): без open_app ничего не открылось
  { rx: /(?:открыл[аи]?|открываю|запустил[аи]?|запускаю)(?![а-яё])\s+(?:тебе\s+|вам\s+)?(?:приложени|gmail|джимейл|почт|telegram|телеграм|whatsapp|ватсап|вайбер|viber|youtube|ютуб|настройк|галере|календар|браузер|chrome|хром|яндекс|госуслуг)/i,
    tool: "open_app|open_url|phone_nav", what: "открыл(а) приложение" },
  { rx: /(?:создал[аи]?|написал[аи]?|составил[аи]?|набрал[аи]?)(?![а-яё])\s+(?:тебе\s+|вам\s+)?(?:нов(?:ое|ый)\s+)?(?:письмо|черновик)/i,
    tool: "phone_type|send_message|send_sms|close_send|save_note", what: "создал(а) письмо" },
  // «Достаю календарь и напоминания — одну секунду», «Сейчас гляну, что по плану» — и ход кончился без данных (отчёт 14.10)
  { rx: /(?:достаю|открываю|смотрю|посмотрю|гляну|загляну|проверяю|проверю|поднимаю|собираю|сверяюсь|уточню|узнаю)(?![а-яё])[^.!?]{0,40}(?:календар|напоминани|план|дел[ауо]?(?![а-яё])|расписани|встреч)/i,
    tool: "list_reminders|calendar_list", what: "смотришь календарь и напоминания" },
  // «Вот смотри, такое-то изображение…» — а картинки нет (отзыв 14.10): без show_images на экране ничего не появилось
  { rx: /(?:^|[.!?—–-]\s*|,\s*)(?:вот|смотри|посмотри(?:те)?|взгляни(?:те)?|показываю|покажу)(?![а-яё])[^.!?]{0,40}(?:изображени|картинк|рисун|фото(?!граф)|иллюстрац)/i,
    tool: "show_images", what: "показываешь картинку" },
  // «Записала встречу в календарь» — а calendar_add не вызван или только спросил «записать?» (записано — calendar_write)
  { rx: /(?:записал[аи]?|добавил[аи]?|внес(?:ла|ли)?|занес(?:ла|ли)?|поставил[аи]?|запланировал[аи]?)(?![а-яё])[^.!?]{0,60}\sв\s+(?:твой\s+|ваш\s+)?календар/i,
    tool: "calendar_write", what: "записал(а) в календарь" },
];
/* -> обещание из CLAIMS, инструмент которого в этом ходе так и не вызывали (called — вызванные), или null.
   asked — просьба человека: у части обещаний («смотрю», «вот») смысл есть только при просьбе про камеру (c.user) */
/* Экзамен 14.10: посчитала 79 дней, поставила таймер на 59 минут и сказала «на 79» — число минут в ответе не совпадает
   с поставленным: просим исправить (как quality.number_mismatch на компьютере). -> подсказка модели или "". */
/* «Нарисуй схему…» — а в ответе нет ```mermaid (экзамен 0.6.40: make_app пустой и «схема на экране») — как diagram_missing в quality.py */
const DIAGRAM_ASK = /(?:нарисуй|начерти|изобрази|набросай|построй|покажи|сделай|составь)[а-яё]*\s+(?:мне\s+|нам\s+)?(?:[а-яё-]+\s+){0,2}?(?:схем|диаграмм|блок-?схем|майнд-?карт|интеллект-карт|mind\s?map|дерев[оа]\s+(?:решений|целей|задач)|оргструктур|карт[уы]\s+(?:процесс|связ))/i;
const DRAWN_TOOLS = ["show_images", "make_app", "start_task", "save_note", "open_made"];
function diagramMissing(ask, answer, called) {
  if (!DIAGRAM_ASK.test(String(ask || "")) || /```mermaid/i.test(String(answer || "")) || DRAWN_TOOLS.some(n => called && called.has && called.has(n))) return "";
  return "ПРОВЕРКА: тебя попросили нарисовать схему, а в ответе её нет. Нарисуй её прямо сейчас в ответе кодом Mermaid — блоком ```mermaid … ``` (flowchart LR или TD, подписи узлов по-русски в кавычках), — она появится на экране картинкой. Перед блоком одна короткая фраза, без повторения сказанного; словами процесс больше не пересказывай.";
}
/* «Готово», «поправила», «записала», «поправлю» — а за ход ни одного действия (отчёт №66: «напомни по последней заметке» →
   «Поняла, поправлю», «Так поправь» → «Готово», а напоминание прежнее). Как quality.saved_claim на компьютере. */
const SAVED_RX = /(?<![а-яё])(?<!не )(?:записал[аи]?|запомнил[аи]?|сохранил[аи]?|зафиксировал[аи]?|обновил[аи]?|добавил[аи]?\s+в\s+(?:список|память|дела|заметк)|запиш[уе]т?|поправил[аи]?|исправил[аи]?|изменил[аи]?|переписал[аи]?|перен[её]сл[аи]?|перен[её]с|поменял[аи]?|переделал[аи]?|поправлю|исправлю|переделаю|перепишу|изменю)(?![а-яё])|^\W*(?:готово|сделано)(?![а-яё])/i;
function savedClaim(ask, answer) {
  if (!SAVED_RX.test(String(answer || "")) || /\?\s*$/.test(String(ask || ""))) return "";
  return "ПРОВЕРКА: ты написал(а), что сделал(а) (записала, поправила, готово), но ни одного действия не было — ничего не изменилось. Сделай это сейчас инструментами: новое или изменённое — remember с фактом целиком; напоминание неверное — найди его (list_reminders), отмени (cancel_reminder) и поставь правильное (set_reminder); заметку — инструментом заметок. Потом коротко скажи, что именно изменилось. Неясно, что нужно, — спроси одной фразой; делать было нечего — не говори «готово». Уже сказанное не повторяй.";
}
// «Напиши Андрею…», а Андрея нет в «Близких» -> пояснение для модели к результату send_message, иначе ""
function notCloseNote(ask) {
  const m = /(?:[Нн]апиши|[Оо]тправь|[Сс]кажи|[Пп]ередай|[Сс]ообщи|[Чч]еркни)\s+(?:сообщение\s+)?([А-ЯЁ][а-яё]{2,})/.exec(String(ask || ""));   // имя — с большой буквы
  if (!m) return "";
  let people = []; try { people = clLoad().people || []; } catch (e) { }
  if (people.length && clMatch(m[1], people)) return "";
  return ` Человека «${m[1]}» нет в «Близких» Dewiar — скажи об этом одной фразой: сообщение открыто в приложении, получателя он выберет сам; пригласить в «Близкие» можно в «Ещё» → «Близкие».`;
}
/* Мини-программа — только когда просили программу, страницу, игру… Экзамены: «нарисуй схему» — HTML-программа вместо схемы;
   «составь список из пяти идей подарка» — программа «на экране» вместо списка в ответе. -> отказ для модели или "" */
const APP_ASK = /программ|приложени|игр[уаыое]|калькулятор|страниц|сайт|презентаци|викторин|таймер|конвертер|открытк|визитк|трекер|таблиц|чек-?лист|тренаж[её]р|интерактив|html|на\s+экран/i;
function makeAppRefusal(ask) {
  const t = String(ask || "");
  if (!t || APP_ASK.test(t)) return "";
  if (DIAGRAM_ASK.test(t)) return "Не сделано: схему рисуй блоком ```mermaid прямо в ответе (flowchart LR или TD, подписи по-русски в кавычках) — она появится на экране картинкой. Программа для этого не нужна.";
  if (/список|иде[июйя]|посоветуй|подбери|расскажи|объясни|напиши|придумай|составь|перечисли|вариант/i.test(t)) return "Не сделано: программу не просили. Ответь прямо в чате — список пунктами в самом ответе, коротко.";
  return "";
}
// «поставь таймер / напомни…» — прямо просили, а set_reminder за ход не вызван (экзамен 0.38.51: «скажи — поставлю»)
const SET_ASK = /(?:^|[\s,.])(?:поставь|заведи|установи|запусти|включи)\s+(?:мне\s+|нам\s+)?(?:[а-яё]+\s+)?(?:таймер|будильник|напоминани)|^\W*(?:[а-яё]+,\s*)?напомни(?:те)?\s/i;
function remindMissing(ask, called) {
  if (!SET_ASK.test(String(ask || "")) || (called && called.has && called.has("set_reminder")) || /\?\s*$/.test(String(ask || ""))) return "";
  return "ПРОВЕРКА: пользователь прямо попросил поставить напоминание (таймер, будильник), а ты его не поставил(а). Поставь сейчас — set_reminder (через N минут — in_minutes; время — at), не переспрашивай; если правда не сказано, когда, — спроси одной фразой. Уже сказанное не повторяй.";
}
/* 19.10 (скриншот: «задач ему накидала, но не вижу их… должен был утром напомнить, но не напомнил»): «Исправляю: встреча —
   на вторник, 12:00. Напомню тебе в понедельник утром в 9:00» — а set_reminder не вызван, в «Делах» пусто. Пообещала напомнить
   (или «поставила будильник») без напоминания — просим поставить; не вышло — честно дописываем REMIND_NOT_SET (как core/quality.py). */
const REMIND_CLAIM = /(?<![а-яё])(?:напомн(?:ю|им)(?!\s+(?:тебе|вам)?\s*,?\s*что)(?=\s+(?:тебе|вам|в|во|завтра|сегодня|послезавтра|утром|дн[её]м|вечером|ночью|через|за|об?|про|как|когда|ровно|каждый|каждое|каждую|по)(?![а-яё]))|разбужу|(?:поставил[аи]?|установил[аи]?|завел[аи]?|завёл|создал[аи]?|добавил[аи]?)\s+(?:тебе\s+|вам\s+)?(?:\S+\s+)?(?:напоминани|будильник|таймер)|(?:напоминани[а-яё]*|будильник[а-яё]*|таймер[а-яё]*)\s+(?:уже\s+)?(?:поставлен|установлен|создан|заведён|заведен|стоит|сработает))/i;
// «Запиши встречу на вторник в 12», «завтра в 13 у меня массаж» — дело со временем (как core/quality.py appt_ask)
const APPT_TIME = /(?<![а-яё\d])(?:(?:в|к|на|с)\s+\d{1,2}(?:[:.]\d{2})?(?=\s|$|[,.!])|\d{1,2}:\d{2}|завтра|послезавтра|(?:в|во|на|к)\s+(?:следующ[а-яё]+\s+|ближайш[а-яё]+\s+|это[тй]?\s+)?(?:понедельник|вторник|среду|четверг|пятницу|субботу|воскресенье)|\d{1,2}(?:-?го|\.\d{1,2})?\s*(?:числ|январ|феврал|март|апрел|ма[яй]|июн|июл|август|сентябр|октябр|ноябр|декабр)|(?:двадцат|тридцат|перв|втор|трет|четвёрт|четверт|пят|шест|седьм|восьм|девят|десят)[а-яё]*\s+числ)/i;
const APPT_WHAT = /встреч|запис[ьи] к|к (?:врач|юле|мастер|стоматолог|парикмахер)|массаж|маникюр|педикюр|стрижк|тренировк|танц|созвон|звонок|позвонить|приём|прием|урок|занят|экзамен|собеседован|вебинар|дедлайн|сдать|оплатить|забрать/i;
function apptAsk(t) { t = String(t || ""); return APPT_TIME.test(t) && APPT_WHAT.test(t) && !/заметк|конспект|список|в\s+файл/i.test(t); }
const APPT_NOTE = "Не записано в заметки: это дело со временем — поставь его в «Дела» напоминанием set_reminder на это время (текст — что за дело: «Встреча с Ирой»). Просили напомнить заранее («за день», «за час») — ещё один set_reminder на то время. Потом коротко подтверди, что и когда.";
const REMIND_TOOLS = ["set_reminder", "plan_day"];        // поставлено; отменить старое — ещё не значит поставить новое
const REMIND_DID = /напомн(?:ю|им)|разбужу|поставил|установил|завел|завёл|создал|добавил/i;
const REMIND_NOT_SET = "Напоминание при этом не поставлено — скажите ещё раз: «напомни …», и я поставлю.";
function remindClaim(answer, called) {
  if ((called && REMIND_TOOLS.some(n => called.has(n))) || !REMIND_CLAIM.test(String(answer || ""))) return "";
  if (called && called.has("list_reminders") && !REMIND_DID.test(String(answer || ""))) return "";   // «уже стоит» после списка — правда
  return "ПРОВЕРКА: ты пообещал(а) напомнить (или сказал(а), что напоминание стоит), но set_reminder за этот ход не вызван — напоминания НЕТ, в нужное время ничего не случится. Поставь его сейчас: set_reminder со временем и текстом (о чём напомнить). Переносишь встречу — найди старое (list_reminders), отмени его (cancel_reminder) и поставь новое. Непонятно, когда напомнить, — спроси одной фразой. Уже сказанное не повторяй.";
}
function numberMismatch(text, calls) {
  const actual = [];
  for (const c of calls || []) {
    if (c.name !== "set_reminder" || /^(Ошибка|Инструмент)/.test(String(c.result || ""))) continue;
    const v = parseFloat((c.args || {}).in_minutes);
    if (isFinite(v)) actual.push(Math.round(v));
    else { const m = String(c.result || "").match(/через\s+(\d+)\s*мин/); if (m) actual.push(+m[1]); }
  }
  if (!actual.length) return "";
  const said = [];
  for (const m of String(text || "").matchAll(/(?:^|[^\p{L}])(?:на|через)\s+(?:(\d{1,4})\s*(мин\p{L}*|час\p{L}*|ч(?!\p{L}))|(полчаса|час)(?!\p{L}))/giu)) {
    if (m[3]) said.push([m[0].trim(), m[3].toLowerCase() === "полчаса" ? 30 : 60]);
    else said.push([m[0].trim(), /^ч/i.test(m[2]) ? +m[1] * 60 : +m[1]]);
  }
  if (!said.length || said.some(([, n]) => actual.includes(n))) return "";
  const [claim, n] = said[0];
  return `ПРОВЕРКА: в ответе ты сказал(а) «${claim}», а напоминание поставлено через ${actual[0]} мин — числа не совпадают. Если нужно ${n} мин — поставь set_reminder заново на ${n} мин и отмени неверное (cancel_reminder); если верно ${actual[0]} — так и скажи. Одной короткой фразой скажи, что исправил(а).`;
}
function claimedAction(text, called, asked) {
  const t = String(text || "").trim();
  // работал(а) пальцами в другом приложении — «открылось на экране», «включаю» там правда: не путаем с make_app и радио
  if (called && [...called].some(n => HANDS_SET.has(n))) return null;
  if (called && (called.has("take_photo") || called.has("show_photo")) && t.length < 400) return null;
  return CLAIMS.find(c => c.rx.test(t) && (!c.user || c.user.test(String(asked || ""))) && !(called && c.tool.split(" ")[0].split("|").some(n => called.has(n)))) || null;
}
const REFUSAL_RX = /нет доступа к интернет|не имею доступа|нет прямого доступа|в реальном времени|как языковая модель|я языковая модель|не могу получить актуальн|не могу искать в интернет|нет возможности выйти в интернет|моя база знаний ограничена|у меня нет доступа|cannot access|don't have access|as an ai/i;
const CAM_REFUSAL_RX = /нет доступа к камер|не могу (?:сфотограф|сделать (?:фото|снимок)|включить камер|видеть тебя|увидеть тебя|посмотреть на тебя)|не вижу тебя|у меня нет камер|не имею камер/i;
const CAM_NUDGE = "СТОП. Ты сказал, что у тебя нет камеры, — это НЕВЕРНО: у тебя есть инструмент take_photo (camera front — на пользователя, "
  + "back — основная). Вызови его сейчас, затем посмотри на снимок и ответь.";
const REFUSAL_NUDGE = "СТОП. Ты отказался, сославшись на отсутствие доступа к интернету или свежим данным, — но это НЕВЕРНО: у тебя ЕСТЬ "
  + "инструменты web_search и read_webpage, и ты ими не воспользовался. Не отказывайся и не пиши «как языковая модель». Сначала выполни "
  + "web_search по сути вопроса, затем ответь по найденным фактам.";

/* ---------- инструменты модели ---------- */
const O = (props, req) => ({ type: "object", properties: props, required: req || [] });
const STR = { type: "string" }, NUM = { type: "number" };

/* ---------- руки в других приложениях: служба специальных возможностей (Hands.java) ----------
   Модель открывает приложение (open_app), читает экран (phone_screen — элементы с номерами), нажимает, вводит, листает.
   После каждого действия к ответу инструмента прикладывается свежий экран — модели не нужен лишний круг на чтение.
   Служба выключена — инструмент отвечает, как её включить (Настройки → Ещё → «Управлять приложениями»). */
let handsAsked = 0;
const HANDS_OFF = "Управление другими приложениями выключено. Скажи пользователю одной-двумя фразами: чтобы я мог(ла) нажимать в других приложениях, "
  + "включите это один раз — Настройки Dewiar → Ещё → «Управлять приложениями» → в списке «Специальные возможности» выберите Dewiar и включите; "
  + "если Dewiar там серый — сначала Настройки → Приложения → Dewiar → ⋮ → «Разрешить ограниченные настройки». "
  + "Не выполняй просьбу другим способом и не притворяйся, что сделал(а).";
const HANDS_TOOLS = [
  { name: "phone_screen", description: "Прочитать, что сейчас на экране телефона (в любом приложении): название приложения и пронумерованные элементы — кнопки, поля ввода, тексты, списки. "
      + "Нужен, чтобы что-то сделать в другом приложении по просьбе пользователя: сначала open_app, потом phone_screen, потом phone_tap / phone_type / phone_scroll. "
      + "Перед последним шагом, который нельзя отменить (отправить сообщение или письмо, оплатить, купить, удалить, опубликовать), спроси подтверждение, если пользователь не просил прямо об этом действии. "
      + "Пароли и коды не вводи — попроси пользователя.", parameters: O({}) },
  { name: "phone_tap", description: "Нажать на экране: id — номер элемента из phone_screen, или text — надпись на экране. long — долгое нажатие. В ответ — что стало на экране.",
    parameters: O({ id: NUM, text: STR, long: { type: "boolean" } }) },
  { name: "phone_type", description: "Ввести текст в поле: id — номер поля из phone_screen (без id — поле с курсором или первое на экране). submit true — нажать «Ввод» (поиск). Текст заменяет то, что было в поле. В ответ — что стало на экране.",
    parameters: O({ id: NUM, text: STR, submit: { type: "boolean" } }, ["text"]) },
  { name: "phone_scroll", description: "Пролистать экран или список: dir down (дальше) | up (назад); id — номер списка (необязательно). В ответ — что стало на экране.",
    parameters: O({ dir: { type: "string", enum: ["down", "up"] }, id: NUM }, ["dir"]) },
  { name: "phone_nav", description: "Системные кнопки: back — назад, home — домой, recents — недавние приложения, notifications — шторка уведомлений, dewiar — вернуться в Dewiar.",
    parameters: O({ action: { type: "string", enum: ["back", "home", "recents", "notifications", "dewiar"] } }, ["action"]) },
];
const HANDS_SET = new Set(HANDS_TOOLS.map(t => t.name));
const HANDS_APK = "https://dewiar.pro/dwrapp/Dewiar-hands.apk";
function handsCard() {
  const st = typeof D.handsState === "function" ? D.handsState() : "";
  if (st === "none") return `<p class="hint" style="margin:0 0 10px">Ассистент может сам нажимать кнопки, вводить текст и листать в других приложениях: «напиши маме в Telegram…», «найди в YouTube…». Для этого нужна расширенная версия Dewiar — она ставится поверх этой, всё сохранится.
    Android предупредит, что приложение просит «специальные возможности»: так он встречает любое приложение не из магазина, которое умеет нажимать за вас. Если установка не идёт — Настройки → Google → Play Защита → на время выключить проверку приложений.</p>
    <button class="btn p w" id="hands-dl">Скачать версию с «руками»</button>`;
  if (st === "on") return `<div class="row2"><span class="res ok" style="flex:1;margin:0">Включено</span><button class="btn" id="hands-go">Настройки</button></div>
    <p class="hint" style="margin:8px 0 0">Просите голосом: «напиши маме в Telegram, что я задержусь», «найди в YouTube новости», «включи вайфай». Перед отправкой, оплатой и удалением ассистент спросит. Пароли не читаются и не вводятся.</p>`;
  if (st === "pending") return `<p class="hint" style="margin:0 0 10px">Включено в настройках Android — подключается…</p><button class="btn p w" id="hands-go">Настройки</button>`;
  // Android 13+: приложения не из магазина в «Специальных возможностях» серые («Ограниченная настройка») — сначала
  // разрешить их на странице Dewiar (отчёт №87, 18.10: «почему нельзя выбрать помощника» — Dewiar серый в списке)
  const back = handsAsked && Date.now() - handsAsked < 10 * 60000;
  return `<p class="hint" style="margin:0 0 10px">Ассистент сможет сам нажимать кнопки, вводить текст и листать в других приложениях — по вашей просьбе голосом: «напиши маме в Telegram…», «найди в YouTube…». Включается один раз:</p>
    ${back ? `<p class="res bad" style="margin:0 0 10px">Не включилось? Если Dewiar в списке серый — это защита Android 13+ для приложений не из магазина: сделайте шаг 2.</p>` : ""}
    <ol class="steps hsteps"><li><b>«Специальные возможности»</b> → Dewiar → включить.</li>
      ${androidSdk() >= 33 ? `<li><b>Dewiar серый</b> или Android пишет «Ограниченная настройка»? Нажмите на него один раз, затем «Страница Dewiar» → ⋮ (вверху справа) → «Разрешить ограниченные настройки» — и снова шаг 1.</li>` : ""}</ol>
    <div class="row2"><button class="btn p" id="hands-go" style="flex:1">Включить</button>${androidSdk() >= 33 ? `<button class="btn" id="hands-app" style="flex:1">Страница Dewiar</button>` : ""}</div>`;
}
function androidSdk() { try { return +JSON.parse(D.info() || "{}").sdk || 0; } catch (e) { return 0; } }
function wireHands() {
  const dl = $("#hands-dl");
  if (dl) dl.onclick = () => { D.openUrl(HANDS_APK); };
  const b = $("#hands-go");
  if (b) b.onclick = () => { handsAsked = Date.now(); if (!D.openSettings("accessibility")) toast("Откройте Настройки Android → Специальные возможности → Dewiar"); };
  const ap = $("#hands-app");
  if (ap) ap.onclick = () => { handsAsked = Date.now(); if (!D.openSettings("app")) toast("Настройки → Приложения → Dewiar → ⋮ → «Разрешить ограниченные настройки»"); };
}
async function handsAfter(res) {
  // действие сделано — экран меняется не сразу: ждём и прикладываем свежий экран (модели не нужен лишний круг)
  if (res === "OFF") return HANDS_OFF;
  if (/^Ошибка|^Пароли/.test(res)) return res;
  await sleep(900);
  const scr = D.handsScreen();
  return scr === "OFF" ? res : res + "\n\nТеперь на экране:\n" + scr;
}
async function handsTool(name, a) {
  if (name === "phone_screen") { const r = D.handsScreen(); return r === "OFF" ? HANDS_OFF : r; }
  if (name === "phone_tap") {
    const id = Math.round(+a.id || 0);
    if (!id && !a.text) return "Ошибка: укажи id элемента из phone_screen или text — надпись на экране.";
    return handsAfter(id ? D.handsTap(id, !!a.long) : D.handsTapText(String(a.text)));
  }
  if (name === "phone_type") return handsAfter(D.handsType(Math.round(+a.id || 0), String(a.text || ""), !!a.submit));
  if (name === "phone_scroll") return handsAfter(D.handsScroll(Math.round(+a.id || 0), a.dir === "up" ? "up" : "down"));
  if (name === "phone_nav") {
    if (a.action === "dewiar") { D.toFront(); return "Dewiar снова на экране."; }
    return handsAfter(D.handsNav(String(a.action || "back")));
  }
  return "Ошибка: неизвестное действие.";
}

/* Калькулятор модели (как tools.calc_eval на компьютере): числа, + - * / % ( ), 17% → 0.17, round abs min max sqrt,
   даты days_until / days_between / weekday / date_add. Свой разбор — без eval. */
// Бюджет, лимит, «заложим 70 тысяч» — план, а не трата (как core/tools.py is_plan)
function isPlanMoney(t) {
  return /(?:^|[^а-яё])(?:бюджет|лимит)[а-яё]*\s+(?:на|для)(?![а-яё])|^\s*(?:бюджет|лимит|план)|заложи|запланир|планиру|(?:увелич|уменьш|повыш|сниж)[а-яё]*\s+(?:с|до)\s+\d/i.test(t || "")
    && !/из бюджета|потрат|купил|оплат|заплат|получил|пришл|зарплат/i.test(t || "");
}
function calcEval(src) {
  const WD = ["воскресенье", "понедельник", "вторник", "среда", "четверг", "пятница", "суббота"];
  const day = (x) => { const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(x)); if (!m) throw new Error(`дата «${x}» — нужна в виде ГГГГ-ММ-ДД`); return new Date(+m[1], +m[2] - 1, +m[3]); };
  const today = () => { const n = new Date(); return new Date(n.getFullYear(), n.getMonth(), n.getDate()); };
  const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  const F = { round: (x, n) => +(+x).toFixed(n || 0), abs: Math.abs, min: Math.min, max: Math.max, sqrt: Math.sqrt, floor: Math.floor, ceil: Math.ceil,
    days_until: (x) => Math.round((day(x) - today()) / 864e5), days_between: (a, b) => Math.round((day(b) - day(a)) / 864e5),
    weekday: (x) => WD[day(x).getDay()], date_add: (x, n) => { const d = day(x); d.setDate(d.getDate() + (+n)); return iso(d); }, today: () => iso(today()) };
  let s = String(src).replace(/×/g, "*").replace(/÷/g, "/").replace(/\^/g, "**").replace(/(\d)\s+(?=\d{3}\b)/g, "$1").replace(/(\d),(\d)/g, "$1.$2");
  if (!s.trim() || s.length > 300) throw new Error("пустое или слишком длинное выражение");
  const toks = s.match(/\d+(?:\.\d+)?|"[^"]*"|[A-Za-z_]+|\*\*|[-+*/%(),]|\S/g) || [];
  let i = 0;
  const peek = () => toks[i], eat = (t) => { if (toks[i] !== t) throw new Error(`ожидалось «${t}»`); i++; };
  const prim = () => {
    const t = toks[i++];
    if (t === undefined) throw new Error("выражение оборвалось");
    if (t === "(") { const v = expr(); eat(")"); return v; }
    if (t === "-") return -unary();
    if (t === "+") return unary();
    if (/^\d/.test(t)) { let v = +t; if (peek() === "%" && !/^[\d(]/.test(toks[i + 1] || "")) { i++; v /= 100; } return v; }
    if (t[0] === '"') return t.slice(1, -1);
    if (F[t] && peek() === "(") { i++; const args = []; if (peek() !== ")") { args.push(expr()); while (peek() === ",") { i++; args.push(expr()); } } eat(")"); return F[t](...args); }
    throw new Error("можно только числа, + - * / % ( ) и функции: " + Object.keys(F).join(", "));
  };
  const unary = () => prim();
  const pow = () => { const b = unary(); if (peek() === "**") { i++; const e = pow(); if (Math.abs(e) > 100) throw new Error("слишком большая степень"); return b ** e; } return b; };
  const term = () => { let v = pow(); for (;;) { const t = peek(); if (t === "*" || t === "/" || t === "%") { i++; const r = pow(); if ((t === "/" || t === "%") && r === 0) throw new Error("деление на ноль"); v = t === "*" ? v * r : t === "/" ? v / r : v % r; } else return v; } };
  const expr = () => { let v = term(); for (;;) { const t = peek(); if (t === "+" || t === "-") { i++; const r = term(); v = t === "+" ? v + r : v - r; } else return v; } };
  const v = expr();
  if (i < toks.length) throw new Error(`не понял: «${toks.slice(i).join(" ")}»`);
  return v;
}

function toolSpecs() {
  if (S.llm.trial) return [];                     // пробный разговор на сайте — без действий (сервер их и не пропустит)
  const t = [
    { name: "set_reminder", description: "Поставить напоминание, будильник или таймер. when — когда, словами пользователя («через 20 минут», «завтра в 9», «в пятницу в 18:30», «27 октября в 10») — время посчитает телефон по своим часам, сам не считай; at — дата и время ISO (ГГГГ-ММ-ДДTЧЧ:ММ, местное) — только если when не подходит. kind: reminder | alarm (будильник) | timer. repeat: '' | daily | weekdays | weekly.",
      parameters: O({ text: STR, when: STR, at: STR, in_minutes: NUM, kind: { type: "string", enum: ["reminder", "alarm", "timer"] }, repeat: { type: "string", enum: ["", "daily", "weekdays", "weekly"] } }, ["text"]) },
    { name: "list_reminders", description: "Какие напоминания и будильники стоят.", parameters: O({}) },
    { name: "calc", description: "Посчитать точно: любые вычисления (проценты, суммы, скидки, деление) и даты. Считай ВСЕГДА этим инструментом, не в уме. Выражение: 2350 * 17 / 100, (1200 - 15%) * 3; даты ГГГГ-ММ-ДД: days_until(\"2027-01-01\") — сколько дней до даты, days_between(\"2026-10-01\", \"2026-12-31\"), weekday(\"2026-10-14\").",
      parameters: O({ expression: STR }, ["expression"]) },
    { name: "cancel_reminder", description: "Отменить напоминание или будильник (id из list_reminders или слова из текста).", parameters: O({ id: STR }, ["id"]) },
    { name: "mark_done", description: "Отметить дела сделанными: пользователь говорит, что сделал («я позвонила Игорю и сделала тренировку», «отметь как исполненное», «готово, купил хлеб»). items — каждое дело отдельно и коротко, как оно называется («Позвонить Игорю», «Тренировка»); подходящее напоминание на сегодня закроется само. undo: true — снять отметку, если отметили по ошибке.",
      parameters: O({ items: { type: "array", items: STR }, undo: { type: "boolean" } }, ["items"]) },
    { name: "done_report", description: "Что пользователь сделал и его достижения: days — за сколько дней (1 — сегодня, 7 — неделя). Для «что я сегодня сделал», «сколько дел за неделю», «какие у меня достижения».", parameters: O({ days: NUM }) },
    { name: "call", description: "Позвонить по телефону: who — имя из контактов («мама», «Лёша») или номер. Человеку из «Близких» звони через close_call.", parameters: O({ who: STR }, ["who"]) },
    { name: "send_sms", description: "Подготовить SMS: who — имя или номер, text — текст. Откроется приложение сообщений, отправит пользователь.", parameters: O({ who: STR, text: STR }, ["text"]) },
    { name: "open_app", description: "Открыть приложение на телефоне по названию.", parameters: O({ name: STR }, ["name"]) },
    { name: "route", description: "Маршрут на карте: «как дойти до…», «проложи маршрут», «построй пешком дворами», геоточка или ссылка на карту. to — куда: адрес с городом, место или координаты, ссылка на карту; from — откуда (пусто — от того места, где пользователь сейчас); mode — walk (пешком, по умолчанию) | transit | car | bike; app — yandex | google (пусто — какие карты стоят). Карта сама строит кратчайший путь (пешком — и дворами); не выдумывай улицы и время.",
      parameters: O({ to: STR, from: STR, mode: { type: "string", enum: ["walk", "transit", "car", "bike"] }, app: { type: "string", enum: ["yandex", "google"] } }, ["to"]) },
    { name: "calendar_list", description: "Календарь телефона (Google и другие календари человека): что запланировано. from — с какого дня ГГГГ-ММ-ДД (пусто — сегодня), days — на сколько дней (1 — один день, 7 — неделя), query — слово для поиска («Игорь», «стоматолог»). Для «что у меня завтра», «когда встреча с …», «свободен ли я в пятницу». Отвечай по найденному, не выдумывай встреч.",
      parameters: O({ from: STR, days: NUM, query: STR }) },
    { name: "calendar_add", description: "Записать встречу в календарь телефона — когда просят записать в календарь или назначить встречу (просто «запомни» — это remember). title — что, start — начало ГГГГ-ММ-ДДTЧЧ:ММ (местное; только дата — на весь день), minutes — длительность (по умолчанию 60), location — где. Первый вызов ничего не записывает — он скажет, о чём спросить; после «да» пользователя вызови снова с теми же данными и confirmed: true.",
      parameters: O({ title: STR, start: STR, minutes: NUM, location: STR, confirmed: { type: "boolean" } }, ["title", "start"]) },
    { name: "open_url", description: "Открыть сайт или ссылку в браузере (YouTube, карты, поиск). Не для радио — для него play_radio.", parameters: O({ url: STR }, ["url"]) },
    { name: "play_radio", description: "Включить радио онлайн прямо здесь, в приложении: query — название станции («Европа Плюс», «Маяк», «Рекорд»), жанр или настроение («джаз», «рок», «классика», «что-нибудь спокойное»), пусто — на мой вкус. На любую просьбу про радио или «включи музыку» — только этот инструмент: не открывай сайты, Яндекс Музыку и другие приложения.",
      parameters: O({ query: STR }) },
    { name: "radio_control", description: "Радио, которое уже играет здесь: pause — пауза, resume — продолжить, stop — выключить, next — другая станция.",
      parameters: O({ action: { type: "string", enum: ["pause", "resume", "stop", "next"] } }, ["action"]) },
    { name: "web_search", description: "Найти в интернете свежие сведения. Не выдумывай результаты.", parameters: O({ query: STR }, ["query"]) },
    { name: "show_images", description: "Показать картинки к тому, о чём рассказываешь (руны и орнаменты, животные, растения, картины, здания, места) — появятся на экране под ответом. Вызывай, когда это лучше увидеть или просят «покажи». query — 2–5 ключевых слов, лучше по-английски; count — 1–6 (обычно 3–4). Не говори «вот изображение», не вызвав инструмент.",
      parameters: O({ query: STR, count: NUM, caption: STR }, ["query"]) },
    { name: "read_webpage", description: "Прочитать страницу по ссылке (текст). Длинная — начало и места со словами find (или вопроса).",
      parameters: O({ url: STR, find: { type: "string", description: "что ищешь на длинной странице: «Доллар США», «15 октября»" } }, ["url"]) },
    { name: "world_time", description: "Который час сейчас в другом городе или стране (по часовому поясу). Время в других городах не считай в уме — только этим.", parameters: O({ city: STR }, ["city"]) },
    { name: "weather", description: "Погода сейчас и на ближайшие дни: city — город (если пользователь не назвал — из памяти о нём).", parameters: O({ city: STR, days: NUM }, ["city"]) },
    { name: "flashlight", description: "Фонарик: on true/false.", parameters: O({ on: { type: "boolean" } }, ["on"]) },
    { name: "phone_settings", description: "Открыть нужный экран настроек телефона: bluetooth, wifi, internet (Wi‑Fi и мобильный интернет), nfc, airplane (режим полёта), display (яркость, экран), sound, data (мобильная сеть), hotspot (точка доступа), location (геолокация). Включить или выключить Bluetooth, Wi‑Fi, режим полёта приложениям Android сам не даёт — открой экран этим инструментом; дальше переключатель нажимают руки (phone_screen, phone_tap) или пользователь.",
      parameters: O({ section: { type: "string", enum: Object.keys(PHONE_SET) } }, ["section"]) },
    { name: "take_photo", description: "Сфотографировать камерой телефона и посмотреть на снимок: camera front — фронтальная (на пользователя: «сфотографируй меня», «как я выгляжу»), back — основная (на то, что перед телефоном: «что это», «прочитай надпись»). Снимок придёт следующим сообщением — опиши его или ответь на вопрос.",
      parameters: O({ camera: { type: "string", enum: ["front", "back"] }, question: STR }) },
    { name: "set_volume", description: "Громкость: action up|down|set|mute|unmute, percent для set.", parameters: O({ action: { type: "string", enum: ["up", "down", "set", "mute", "unmute"] }, percent: NUM }, ["action"]) },
    { name: "battery", description: "Заряд батареи телефона.", parameters: O({}) },
    { name: "save_note", description: "Записать заметку или список (title — коротко, text — содержимое). folder — папка, только если её назвали («в папку Работа»).", parameters: O({ title: STR, text: STR, folder: STR }, ["title", "text"]) },
    { name: "find_notes", description: "Найти в заметках по словам.", parameters: O({ query: STR }, ["query"]) },
    { name: "recall", description: "Вспомнить, о чём говорили и что делали за последние дни (журнал разговоров на телефоне и сделанное): «что мы делали на этой неделе», «о чём я спрашивал вчера». days — за сколько дней (1–14), query — слова для поиска (можно пусто).", parameters: O({ days: NUM, query: STR }) },
    { name: "open_made", description: "Открыть на экране то, что ты уже сделал на телефоне (make_app: калькулятор, игра, страница): «покажи калькулятор», «где программа, которую ты сделал». title — часть названия; пусто — последнее.", parameters: O({ title: STR }) },
    { name: "show_photo", description: "Снова показать на экране последний снимок с камеры (take_photo), с кнопкой «Сохранить».", parameters: O({}) },
    { name: "remember", description: "Запомнить надолго факт о пользователе одной фразой в третьем лице.", parameters: O({ fact: STR }, ["fact"]) },
    { name: "money_add", description: `Записать уже сделанный расход или полученный доход. Бюджет, лимит, план («бюджет на мебель — 50 тысяч», «заложим 70») — не расход: это remember. kind expense|income, amount — число, currency (по умолчанию ${CUR}), category по-русски, note.`,
      parameters: O({ kind: { type: "string", enum: ["expense", "income"] }, amount: NUM, currency: STR, category: STR, note: STR }, ["kind", "amount"]) },
    { name: "money_report", description: "Итоги по деньгам: period today|week|month|year.", parameters: O({ period: { type: "string", enum: ["today", "week", "month", "year"] } }) },
    { name: "call_persona", description: "Позвать другого персонажа команды по имени (он ответит своим голосом).", parameters: O({ name: STR }, ["name"]) },
    { name: "make_app", description: "Сделать мини-программу или страницу прямо на телефоне: калькулятор, игра, таймер, конвертер, викторина, шпаргалка, открытка, презентация (слайды листаются кнопками и свайпом). html — ОДИН самодостаточный HTML-файл: CSS и JS внутри, без внешних файлов и библиотек, компактный код; под экран телефона (крупные кнопки), тёмная тема, по-русски. title — короткое название. Программа сразу откроется на экране и сохранится в «Мой день» → «Сделанное».",
      parameters: O({ title: STR, html: STR }, ["title", "html"]) },
    ...(clLoad().people.length ? [{ name: "close_send", description: "Написать человеку из «Близких» (переписка между помощниками Dewiar: дойдёт в его приложение, его помощник скажет вслух). Только когда пользователь прямо просит написать, передать или сказать кому-то из близких. to — имя, как сказал пользователь («Андрею», «маме»); text — само сообщение от лица пользователя («Задержусь на полчаса»), без «передай».",
      parameters: O({ to: STR, text: STR }, ["to", "text"]) },
      { name: "close_call", description: "Позвонить человеку из «Близких» через Dewiar (аудио или видео — video true). Только когда пользователь прямо просит позвонить кому-то из близких.", parameters: O({ to: STR, video: { type: "boolean" } }, ["to"]) },
      { name: "close_where", description: "Где сейчас близкий — по радару «Рядом» (только если он сам показывает вам своё место): сколько до него, в какую сторону, когда обновлено. «где мама?», «далеко ли Андрей?». who — имя.", parameters: O({ who: STR }, ["who"]) },
      { name: "close_wave", description: "Помахать близкому 👋 — у него на экране волны и голос «… машет вам». «помаши маме», «помаши Андрею рукой». to — имя.", parameters: O({ to: STR }, ["to"]) },
      { name: "close_read", description: "Последние сообщения от близких (и мои им): «что мне писали», «что ответила мама». who — имя или пусто — все.", parameters: O({ who: STR }) }] : []),
    { name: "app_help", description: "Руководство Dewiar — как пользоваться самим этим приложением: где кнопка или раздел, как настроить, как пригласить близкого или друга, сканер, стили, напоминания на часах, синхронизация, данные. Вызывай, когда спрашивают про Dewiar и его функции («как…», «где…», «что ты умеешь…»), — не выдумывай меню. query — о чём спросили.", parameters: O({ query: STR }, ["query"]) },
    { name: "scan_code", description: "Открыть сканер кодов камерой: QR, Aztec, печать Dewiar, штрихкоды и Data Matrix товаров. «Отсканируй код», «прочитай QR», «проверь честный знак». Результат обработается сам.", parameters: O({}) },
    { name: "send_message", description: "Отправить текст через мессенджер: app — max (по умолчанию), telegram, whatsapp, viber, vk; text — готовый текст сообщения. Откроется приложение, получателя выберет пользователь.",
      parameters: O({ app: { type: "string", enum: ["max", "telegram", "whatsapp", "viber", "vk"] }, text: STR }, ["text"]) },
  ];
  if (typeof D.handsState === "function") t.push(...HANDS_TOOLS);
  if (loggedIn()) t.push({ name: "ask_knowledge", description: "Спросить Знания пользователя на сайте Dewiar — его документы и папки, публичную библиотеку. Ответ с источниками. base — название папки или раздела, если пользователь его назвал.",
    parameters: O({ question: STR, base: STR }, ["question"]) });
  if (S.sync.on && syncCred() && pcSeen()) t.push({ name: "start_task", description: "Передать большую задачу компьютеру пользователя: исследование с отчётом, документ, презентация, работа с файлами или кодом. title — коротко, goal — что сделать и какой нужен результат, подробно. Ход и итог появятся в «Мой день» → «Сделанное».",
    parameters: O({ title: STR, goal: STR }, ["goal"]) });
  if (S.home.token && !D.web) t.push({ name: "smart_home", description: "Умный дом Яндекса: action list|on|off|brightness|brighter|dimmer|temperature|scenario; target — устройство и/или комната словами («свет в спальне», «весь свет», «кондиционер»), value — число.",
    parameters: O({ action: { type: "string", enum: ["list", "on", "off", "brightness", "brighter", "dimmer", "temperature", "scenario"] }, target: STR, value: NUM }, ["action"]) });
  return D.web ? t.filter(x => !WEB_NO_TOOLS.has(x.name)) : t;
}

/* Аргументы — к описанию инструмента: модели присылают список вместо строки, «5» вместо 5, {"q": …} вместо {"query": …}. */
function coerceArgs(name, a) {
  a = a && typeof a === "object" && !Array.isArray(a) ? Object.assign({}, a) : { text: String(a || "") };
  const spec = toolSpecs().find(t => t.name === name), props = (spec && spec.parameters && spec.parameters.properties) || {};
  const req = (spec && spec.parameters && spec.parameters.required) || [];
  const missing = req.filter(k => !(k in a)), unknown = Object.keys(a).filter(k => !(k in props));
  if (Object.keys(props).length && missing.length === 1 && unknown.length === 1) { a[missing[0]] = a[unknown[0]]; delete a[unknown[0]]; }
  for (const k of Object.keys(a)) {
    const want = (props[k] || {}).type, v = a[k];
    if (want === "string" && Array.isArray(v)) a[k] = v.map(x => typeof x === "string" ? x : JSON.stringify(x)).join(k === "text" ? "\n" : " ");
    else if (want === "string" && v && typeof v === "object") a[k] = JSON.stringify(v);
    else if (want === "string" && v != null && typeof v !== "string") a[k] = String(v);
    else if (want === "number" && typeof v === "string" && v.trim() && !isNaN(+v.replace(",", "."))) a[k] = +v.replace(",", ".");
    else if (want === "boolean" && typeof v === "string") a[k] = /^(true|1|да|yes)$/i.test(v.trim());
  }
  return a;
}
/* Выполнить инструмент модели. -> строка для модели (ошибка — «Ошибка: …» с подсказкой, что сказать человеку);
   take_photo -> {text, image}, call_persona -> {text, switchTo} — их разбирает ask(). */
async function runTool(name, a) {
  if (HANDS_SET.has(name)) return handsTool(name, a || {});
  a = coerceArgs(name, a);
  switch (name) {
    case "set_reminder": {
      let at = null;
      if (a.in_minutes) at = new Date(Date.now() + a.in_minutes * 60000);
      else if (a.when && !a.at) { const w = parseWhen(a.when); if (w) { at = w.at; if (!a.repeat && w.repeat) a.repeat = w.repeat; } }
      else if (a.at) { at = new Date(a.at); if (isNaN(at)) { const w = parseWhen(a.at); at = w && w.at; } }
      // «через 20 минут» — считаем сами от часов телефона, а не берём у модели: она могла посчитать от старого времени
      // из разговора (16.10: «сколько времени» — «14:17» в 15:57)
      { const said = String(turnAsk || "").split("\n\nВложения:")[0];
        if (!a.repeat && /(^|[^а-яё])через\s+(?:\S+\s+){0,3}?(?:секунд|минут|час|полчаса|полтора)/i.test(said) && !/кажд/i.test(said)) {
          const w = parseWhen(said); if (w && w.rel && (!at || isNaN(at) || Math.abs(w.at - at) > 90000)) at = w.at; } }
      if (!at || isNaN(at)) return "Ошибка: не понял время — спроси у пользователя, когда напомнить.";
      let moved = "";                                    // «на 17:00», а уже 17:26 — на завтра в 17:00, а не в прошлое
      if (at < new Date(Date.now() - 60000) && !a.repeat) { while (at < new Date()) at = new Date(at.getTime() + 864e5); moved = " Это время сегодня уже прошло — поэтому на завтра; так и скажи."; }
      else if (a.repeat) {                               // «по будням в 17:30», а уже 17:43 — первое в следующий будний, а не звонок сразу (№56)
        const r = rollRepeat(at, a.repeat);
        if (r.getTime() !== at.getTime()) { if (at < new Date(Date.now() - 60000)) moved = ` Сегодня это время уже прошло — первое напоминание ${whenText(r)}; так и скажи.`; at = r; }
      }
      // в сообщении были фото или файлы («вот скрины, напомни завтра обсудить их с Сашей») — они к напоминанию, в его заметку
      const n = turnAtt.length ? remindNote(a.text || "", at, turnAsk, turnAtt) : null; if (n) turnAtt = [];
      const x = addAlarm(n ? n.title : a.text || "Напоминание", at, a.kind || "reminder", a.repeat || "", n ? n.id : "");
      showCard(alarmCard(x));
      return `Поставлено: ${whenText(at)}${a.repeat ? ", " + REP_RU[a.repeat] : ""} — ${x.title} (id ${x.id}).${moved}` +
        (n ? ` Вложения из сообщения (${n.att.length}) приложены к напоминанию — в срок они откроются прямо из него; можно так и сказать.` : "");
    }
    case "calc": {
      try { const r = calcEval(String(a.expression || "")); return `${a.expression} = ${typeof r === "number" ? String(+r.toFixed(10)).replace(".", ",") : r}`; }
      catch (e) { return "Ошибка: " + e.message; }
    }
    case "list_reminders": {
      const l = JSON.parse(D.alarms() || "[]").sort((x, y) => x.at - y.at), jobs = (mind().jobs || []).filter(j => !j.paused);
      const out = l.map(x => `${x.id}: ${whenText(new Date(x.at))}${x.repeat ? " (" + REP_RU[x.repeat] + ")" : ""} — ${x.title}`);
      if (jobs.length) out.push("Дела по расписанию (делает компьютер): " + jobs.map(j => `${j.title || j.prompt || "дело"}${j.at ? " — " + whenText(new Date(j.at)) : ""}`).join("; "));
      return out.length ? out.join("\n") : "Напоминаний нет.";
    }
    case "cancel_reminder": {
      const l = JSON.parse(D.alarms() || "[]"), q = String(a.id || "").toLowerCase();
      // пустой запрос совпал бы с первым же напоминанием — ищем по словам, только если они есть
      const x = l.find(i => i.id === a.id) || (q.trim() ? l.find(i => i.title.toLowerCase().includes(q.trim())) : null);
      if (!x) return "Такого напоминания нет.";
      D.alarmCancel(x.id); syncSoon(); return `Отменено: ${x.title}.`;
    }
    case "mark_done": {
      const items = (Array.isArray(a.items) ? a.items : String(a.items || a.text || "").split(/\s*[;\n]\s*/)).map(x => String(x || "").trim()).filter(Boolean).slice(0, 12);
      if (!items.length) return "Ошибка: не понял, какое дело отметить — спроси коротко.";
      if (a.undo) {
        const today = doneStats().items.slice().reverse(), gone = [];
        for (const t of items) { const w = stems(t), x = today.find(i => !gone.includes(i) && stems(i.title).some(s => w.includes(s))) || (items.length === 1 && today.find(i => !gone.includes(i))); if (x) { doneUndo(x.id); gone.push(x); } }
        if ($("#sh-day.on") && dayTab === "rem") renderDay();
        return gone.length ? `Отметка снята: ${gone.map(x => "«" + x.title + "»").join(", ")}. Сегодня сделано ${doneStats().today}.` : "Среди сегодняшних отметок такого нет.";
      }
      const r = markDone(items, "voice");
      if ($("#sh-day.on") && dayTab === "rem") renderDay();
      return doneSay(r);
    }
    case "done_report": return doneReport(a.days);
    case "call": { const r = await doCall(a.who || ""); return r.text; }
    case "send_sms": {
      let num = String(a.who || "").replace(/[^\d+]/g, "");
      if (a.who && num.length < 5) { let c = JSON.parse(D.contact(a.who) || "{}"); if (c.need && await needPerm(CONTACTS)) c = JSON.parse(D.contact(a.who) || "{}"); num = c.number || ""; }
      D.sms(num, a.text || ""); return (num ? "Открыл сообщение — пользователь проверит и отправит." : "Открыл сообщение без получателя — пусть выберет сам.") + notCloseHint(a.who);
    }
    case "open_app": {
      const n = openAppSmart(a.name || "");
      if (!n) return `Приложение «${a.name}» не найдено.`;
      if (typeof D.handsState !== "function" || D.handsState() !== "on") return `Открыто: ${n}.`;
      await sleep(1500);                              // приложение запускается — сразу показываем модели его экран
      const scr = D.handsScreen();
      return `Открыто: ${n}.` + (scr && scr !== "OFF" ? "\n\nНа экране:\n" + scr : "");
    }
    case "route": return routeTool(a);
    case "calendar_list": return calendarList(a);
    case "calendar_add": return calendarAdd(a);
    case "open_url": { let u = String(a.url || ""); if (!/^https?:|^[a-z]+:/.test(u)) u = "https://" + u; return D.openUrl(u) ? "Открыто." : "Не открылось."; }
    case "play_radio": {
      const r = await radio.play(a.query || "");
      if (!r.ok) return r.text;
      return `Играет радио «${r.station.name}». Остановить — «стоп» или «пауза», другая станция — «дальше».` +
        (r.others.length ? ` Другие по запросу: ${r.others.join(", ")}.` : "") + " Скажи коротко, одной фразой, что включено.";
    }
    case "radio_control": {
      const act = a.action || "pause";
      if (act === "next") { const r = await radio.next(); return r.ok ? `Играет «${r.station.name}».` : r.text; }
      if (!radio.on() && act !== "resume") return "Радио сейчас не играет.";
      if (act === "stop") { radio.stop(); return "Радио выключено."; }
      if (act === "resume") return radio.resume() ? "Радио снова играет." : "Нечего продолжать — скажи, какое радио включить.";
      radio.pause(); return "Радио на паузе.";
    }
    case "web_search": return await webSearch(a.query || "");
    case "show_images": return await webImages(a.query || "", a.count);
    case "read_webpage": {
      // экзамен 16.10: модель шесть раз звала read_webpage без адреса («Invalid host: https://») — адрес из слов человека
      // («посмотри сайт https://www.python.org/», «открой python.org»), как на компьютере (engine_tools, QUERY_TOOLS)
      let url = String(a.url || "").trim();
      if (!/[a-zа-я0-9]\.[a-zа-я]{2,}/i.test(url)) {
        const m = /(https?:\/\/[^\s«»"'<>]+)|(?<![@\w.-])((?:[a-zа-я0-9-]+\.)+(?:ru|рф|by|com|org|net|io|dev|pro|info|ua|kz|me|app|ai|tv|su)(?:\/[^\s«»"'<>]*)?)/i.exec(String(turnAsk || "").split("\n\nВложения:")[0]);
        if (!m) return "Ошибка: не пришёл адрес страницы — возьми его из слов пользователя и вызови read_webpage с url.";
        url = (m[1] || m[2]).replace(/[.,;:!?)]+$/, "");
      }
      // видео по ссылке (18.10): текст ролика — в субтитрах, их достаёт компьютер (core/video.py, yt-dlp); здесь — только
      // описание. Не выдумывать содержание: честно сказать и, если компьютер подключён, предложить передать задачу ему
      if (/^https?:\/\/(?:www\.|m\.)?(?:youtube\.com\/(?:watch\?|shorts\/|live\/)|youtu\.be\/|rutube\.ru\/(?:video|shorts)\/|vk\.com\/video|vkvideo\.ru\/video)/i.test(url)) {
        const desc = await readPage(url, a.find || "");
        return desc + "\n\n(Это только страница видео — описание, без текста ролика. Скажи об этом честно и не выдумывай содержание. "
          + (S.sync.on && syncCred() && pcSeen() ? "Конспект по самому ролику сделает компьютер: предложи передать ему задачу (start_task: конспект видео по ссылке, сохранить заметкой со ссылкой)." : "Конспект по самому ролику умеет Dewiar на компьютере.") + ")";
      }
      return await readPage(url, a.find || "");
    }
    case "world_time": { const r = await worldTime(a.city || ""); return r ? r + " [Посчитано по часовому поясу — называй именно это время.]" : `Город «${a.city || ""}» не нашёлся — уточни. Время не считай в уме.`; }
    case "weather": return await weather(a.city || "", a.days || 3);
    case "flashlight": return devTorch(!!a.on) ? (a.on ? "Фонарик включён." : "Фонарик выключен.") : "Фонарика нет.";
    case "phone_settings": {
      const sec = PHONE_SET[a.section] ? a.section : "", name = PHONE_SET[sec];
      if (!sec) return "Такого экрана нет — выбери section из списка.";
      if (SANDBOX) SANDBOX.dev.push({ name: "phone_settings", args: sec, argsObj: { section: sec }, t: Date.now() });
      else if (!D.openSettings(sec)) return `Экран «${name}» на этом телефоне не открылся — подскажи пользователю: Настройки → ${name}.`;
      const hands = typeof D.handsState === "function" && D.handsState() === "on";
      return hands ? `Открыт экран настроек «${name}». Дальше: phone_screen — посмотри экран и нажми нужный переключатель (phone_tap), потом проверь.`
        : `Открыт экран настроек «${name}» — скажи пользователю коротко нажать переключатель (сам ты нажать не можешь). Не говори «включила».`;
    }
    case "take_photo": {
      // камера — только по просьбе (отчёт №92, 19.10: на «ты сказала, что на айфоне можно веб-версией?» сама сфотографировала)
      if (turnAsk && !PHOTO_ASK_RX.test(String(turnAsk))) {
        plog("warn", "take_photo без просьбы — не снимаю");
        return "Снимок не сделан: пользователь не просил камеру. Без прямой просьбы не фотографируй — ответь словами на его вопрос.";
      }
      const shot = await takePhoto(a.camera === "back" ? "environment" : "user");
      if (!shot.ok) return "Ошибка: " + shot.error;
      if (shot.dark) return { text: `Снимок сделан ${a.camera === "back" ? "основной (задней)" : "фронтальной"} камерой, но кадр почти чёрный — камера ничего не видит. `
        + "Не выдумывай, что на нём. Скажи пользователю, что темно или камера закрыта (лежит объективом вниз, пальцем, чехлом), и предложи повторить"
        + (a.camera === "back" ? " — или снять фронтальной." : " — или основной камерой."), image: shot.dataUrl };
      return { text: "Снимок сделан, показан пользователю на экране телефона (под твоим обликом, с кнопкой «Сохранить») и приложен следующим сообщением — посмотри на него и ответь" + (a.question ? `: ${a.question}` : ".") + " Не говори, что не можешь показать: он уже на экране.", image: shot.dataUrl };
    }
    case "set_volume": return `Громкость ${devVolume(a.action, a.percent || (a.action === "set" ? 0 : 20))}%.`;
    case "battery": { const b = JSON.parse(D.battery() || "{}"); return `Заряд ${b.percent}%${b.charging ? ", заряжается" : ""}.`; }
    case "save_note": {
      // дело со временем — в «Дела», а не в заметки (отчёт №94, 19.10: «запиши встречу с Ирой на вторник в 12 и напомни за
      // день» — заметка с ответом Патрика, в «Делах» пусто, утром тишина)
      if (turnAsk && apptAsk(turnAsk)) { plog("info", "📝 дело со временем — не в заметки, а напоминанием"); return APPT_NOTE; }
      // стихи, список идей, ответ на вопрос — в чат, а не в заметки без спроса (экзамен 11.10)
      // «что я записывал про ремонт?» — вопрос, а не просьба записать (экзамен 13.10: найденную заметку сохраняла второй раз)
      if (turnAsk && !/запиш|записать|сохран|запомн|занеси|зафиксир|в\s+файл|конспект|(?:в|во)\s+заметк|заметк[уа](?![а-яё])|созда\w*\s+заметк|нов\w+\s+заметк|допиши|добавь\s+в/i.test(turnAsk))
        return "Записывать не нужно: пользователь не просил сохранять. Это не ошибка — ничего о записи и сбоях не говори, просто ответь на вопрос прямо в чате (список — пунктами в самом ответе).";
      const att = noteAttSave(turnAtt); turnAtt = [];             // фото и файлы этого хода — в заметку
      const fold = folderName(a.folder);
      const n = notes(); n.push(Object.assign({ id: "n" + Date.now(), title: a.title, text: a.text, time: Date.now() }, att.length ? { att } : {}, fold ? { folder: fold } : {})); saveNotes(n);
      return `Записано: «${a.title}»` + (fold ? ` в папку «${fold}»` : "") + (att.length ? ` (вложений: ${att.length})` : "") + "."; }
    case "recall": return recall(a.days, a.query);
    case "open_made": {
      const l = apps(), q = String(a.title || "").toLowerCase().trim();
      const ap = q ? l.slice().reverse().find(x => x.title.toLowerCase().includes(q) || q.includes(x.title.toLowerCase().slice(0, 6))) : l[l.length - 1];
      if (!ap) return l.length ? "Такого среди сделанного нет. Есть: " + l.slice(-6).map(x => `«${x.title}»`).join(", ") + "." : "На телефоне ещё ничего не сделано.";
      setTimeout(() => { showCard(appCard(ap)); openApp(ap.id); }, 50);
      return `«${ap.title}» — на экране. Скажи одной фразой; найти потом — «Мой день» → «Сделанное».`;
    }
    case "show_photo": {
      const p = lastPhoto();
      if (!p) return "Снимков пока нет — сделай take_photo.";
      setTimeout(() => showPhotoCard(p), 50);
      return "Снимок снова на экране, под ним кнопка «Сохранить». Скажи об этом одной фразой.";
    }
    case "find_notes": {
      // «покажи заметки», «все», «последние» — это не слова для поиска: отдаём последние заметки. Раньше такие слова
      // ничего не находили, и Лира говорила «заметок пока нет», хотя они были (отзыв 11.10)
      const all = notes().slice().sort((x, y) => (+y.time || 0) - (+x.time || 0));
      const w = String(a.query || "").toLowerCase().replace(/ё/g, "е").split(/[\s,.]+/).filter(x => x.length > 2 && !NOTE_GENERIC.test(x)).map(x => x.slice(0, 5));
      const f = w.length ? all.filter(n => w.some(x => (n.title + " " + n.text).toLowerCase().replace(/ё/g, "е").includes(x))).slice(0, 8) : [];
      const show = (l) => l.map(n => `«${n.title}» (${whenText(new Date(+n.time || Date.now()))}): ${noteShown(n.text).slice(0, 600)}${(n.att || []).length ? ` [вложений: ${n.att.length}]` : ""}`).join("\n\n");
      if (f.length) return show(f);
      if (!all.length) return "Заметок пока нет.";
      return (w.length ? "По этим словам в заметках ничего нет. " : "") + `Всего заметок: ${all.length}. Последние:\n\n` + show(all.slice(0, 10));
    }
    case "remember": { const f = String(a.fact || a.text || a.content || "").trim();
      if (!f) return "Ошибка: не пришло, что запомнить — вызови remember ещё раз с fact (сам факт одной фразой).";
      if (!S.memory.includes(f)) { S.memory.push(f); S.memory = S.memory.slice(-80); saveS(); syncSoon(); } return "Запомнил."; }
    case "money_add": {
      if (isPlanMoney(`${a.category || ""} ${a.note || ""}`)) return "Не записано: это план (бюджет, лимит), а не трата или доход. Запомни его как факт (remember), например «Бюджет на мебель — 65 тысяч рублей».";
      const m = money(); const x = { id: "m" + Date.now(), date: isoLocal(new Date()).slice(0, 10), kind: a.kind === "income" ? "income" : "expense", amount: +a.amount || 0,
        currency: (a.currency || CUR).toUpperCase(), category: a.category || (a.kind === "income" ? "Доход" : "Разное"), note: a.note || "" };
      if (!x.amount) return "Ошибка: нет суммы."; m.push(x); saveMoney(m);
      return `Записано: ${x.kind === "income" ? "+" : "−"}${x.amount} ${x.currency}, ${x.category}.`;
    }
    case "money_report": return moneyReport(a.period || "month").text;
    case "close_send": { const it = await clSend(a.to || "", a.text || ""); return `Отправлено ${it.to}. Скажи коротко, что отправила.`; }
    case "close_read": return clRecent(a.who || "");
    case "close_where": return await radWhereText(a.who || "");
    case "close_wave": { const p = await radWave(a.to || ""); return `Помахала: ${p.name} увидит и услышит «машет вам». Скажи коротко.`; }
    case "scan_code": scanCode(); return "Сканер открыт. Скажи коротко: «Наведите камеру на код».";
    case "app_help": return guideAnswer(a.query || "");
    case "close_call": { const p = await clCall(a.to || "", !!a.video); return `Звоню ${p.name}. Ничего не говори — идёт звонок.`; }
    case "call_persona": {
      const p = findPersona(a.name);
      if (!p) return "Такого персонажа нет.";
      return { text: `${p.name} сейчас ответит сам.`, switchTo: p.id };
    }
    case "make_app": {
      { const no = makeAppRefusal(turnAsk); if (no) return no; }
      const html = String(a.html || "").trim();
      if (!/<(?:html|body|div|script|button|canvas|main|section)\b/i.test(html)) return "Ошибка: html не пришёл — пришли весь HTML-файл в поле html (компактный код).";
      if (!/<\/(?:html|body|script|div|main|section)>\s*$/i.test(html)) return "Ошибка: HTML оборвался на середине — сделай короче и пришли целиком.";
      const ap = saveApp(a.title || "Программа", html);
      setTimeout(() => { showCard(appCard(ap)); openApp(ap.id); }, 50);
      lastDone = `Сделано: «${ap.title}» — уже на экране. Потом найдёте в «Мой день» → «Сделанное» или скажите «покажи ${ap.title.toLowerCase()}».`;
      return `Сделано: «${ap.title}» — на экране телефона, сохранено в «Мой день» → «Сделанное» (снова открыть — open_made). Скажи об этом одной фразой и где её найти, код не пересказывай.`;
    }
    case "start_task": {
      try { taskToPc(a.title || String(a.goal || "").slice(0, 60), a.goal || a.title || ""); } catch (e) { return "Не получилось: " + e.message; }
      return (pcOnline() ? "Задача передана компьютеру — он уже берётся." : "Компьютер сейчас не на связи — задачу делает облако Dewiar.")
        + " Ход и итог — в «Мой день» → «Сделанное»; когда будет готово, пришлю уведомление, а файлы можно будет открыть и сохранить прямо здесь."
        + " Результата ЕЩЁ НЕТ — он появится через несколько минут или дольше. Скажи одной фразой, что взялась (взялся) и сообщишь, когда будет готово; не говори «готово», «сделала», «вот презентация» — это неправда, пока задача не закончилась.";
    }
    case "smart_home": return await homeTool(a);
    case "send_message": {
      // «Напиши Андрею…», а Андрея нет в «Близких» — сообщение откроется в мессенджере (получателя выберет человек), и
      // модели — сказать об этом честно (экзамен: «Готово, открыла MAX» — как будто Андрей уже получил)
      const r = sendTo(a.app || "max", a.text || "");
      return typeof r === "string" ? r + notCloseNote(turnAsk) : r;
    }
    case "ask_knowledge": return await askKnowledge(a.question || "", a.base || "");
  }
  return "Неизвестный инструмент.";
}

/* HTML → простой текст: для поиска и чтения страниц (раздел «интернет» — ниже, после камеры) */
const stripHtml = (h) => h.replace(/<script[\s\S]*?<\/script>|<style[\s\S]*?<\/style>/gi, " ").replace(/<[^>]+>/g, " ")
  .replace(/&nbsp;/g, " ").replace(/&amp;/g, "&").replace(/&quot;/g, '"').replace(/&#x27;|&#39;/g, "'").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/\s+/g, " ").trim();
/* ---------- камера: «сфотографируй меня и опиши» ----------
   Снимает сам интерфейс (getUserMedia в WebView; доступ даёт MainActivity.onPermissionRequest при разрешении CAMERA):
   отсчёт 3-2-1, кадр JPEG до 1024 px — модели картинкой; почти чёрный кадр помечается dark, чтобы модель не выдумывала. */
const CAMERA = "android.permission.CAMERA";
async function visionModel() {                     // облако Dewiar: для снимка — модель, которая видит картинки
  if (!S.llm.cloud) return "";
  try {
    const md = await cloudGet(cloudBase(), S.llm.api_key, "/models");
    const cur = (md.data || []).find(m => m.id === S.llm.model);
    if (cur && cur.vision) return "";
    const v = (md.data || []).find(m => m.vision);
    return v ? v.id : "";
  } catch (e) { return ""; }
}
let camAt = 0;
function lum(v, w = 32, h = 24) {                  // средняя яркость кадра 0…255 — чёрный кадр не отдаём модели
  try { const c = document.createElement("canvas"); c.width = w; c.height = h; const x = c.getContext("2d"); x.drawImage(v, 0, 0, w, h);
    const d = x.getImageData(0, 0, w, h).data; let sum = 0; for (let i = 0; i < d.length; i += 4) sum += d[i] * .3 + d[i + 1] * .59 + d[i + 2] * .11; return sum / (w * h); }
  catch (e) { return 255; }
}
/* Снимок — в разговоре, с кнопкой «Сохранить» (в «Загрузки»); последний хранится (last_photo.txt) — show_photo покажет снова. */
const lastPhoto = () => { try { return fileGet("last_photo.txt") || ""; } catch (e) { return ""; } };
function photoCard(url) {
  return `<div class="appc"><img class="shot" src="${url}" alt="Снимок"><div class="row2"><button class="btn" onclick="savePhoto()">Сохранить в «Загрузки»</button></div></div>`;
}
function savePhoto() {
  const u = lastPhoto(), b64 = u.split(",")[1] || "";
  const d = new Date(), name = `Dewiar ${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}-${pad(d.getMinutes())}.jpg`;
  const where = b64 && D.saveDownloadB64 ? D.saveDownloadB64(name, "image/jpeg", b64) : "";
  toast(where ? "Сохранено: " + where : "Не получилось сохранить", 3500);
}
async function takePhoto(facing) {
  // камера, закрытая секунду назад, ещё освобождается — второй снимок подряд вышел бы чёрным
  if (Date.now() - camAt < 1500) await sleep(1500 - (Date.now() - camAt));
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) return { ok: false, error: "камера недоступна в этой версии Android" };
  if (!(await needPerm(CAMERA))) return { ok: false, error: "нет разрешения на камеру — разрешите камеру для Dewiar в настройках телефона" };
  let stream;
  try { stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: facing, width: { ideal: 1280 }, height: { ideal: 960 } }, audio: false }); }
  catch (e) { return { ok: false, error: "камера не открылась (" + (e.message || e.name) + ")" }; }
  const box = document.createElement("div");
  box.id = "cam"; box.innerHTML = `<video autoplay playsinline muted class="${facing === "user" ? "mirror" : ""}"></video><b></b>`;
  document.body.appendChild(box);
  const v = box.querySelector("video"), cnt = box.querySelector("b");
  try {
    v.srcObject = stream; await v.play().catch(() => {});
    for (let i = 0; i < 50 && !v.videoWidth; i++) await sleep(100);
    for (let i = 0; i < 12 && lum(v) < 14; i++) await sleep(200);     // первые кадры у камеры тёмные — ждём, пока «проснётся»
    for (const n of ["3", "2", "1"]) { cnt.textContent = n; D.vibrate(15); await sleep(650); }
    cnt.textContent = ""; box.classList.add("flash");
    let light = lum(v);
    for (let i = 0; i < 6 && light < 14; i++) { await sleep(300); light = lum(v); }   // кадр всё ещё чёрный — ещё немного подождём
    const k = Math.min(1, 1024 / Math.max(v.videoWidth || 1, v.videoHeight || 1)), cv = document.createElement("canvas");
    cv.width = Math.round((v.videoWidth || 640) * k); cv.height = Math.round((v.videoHeight || 480) * k);
    cv.getContext("2d").drawImage(v, 0, 0, cv.width, cv.height);
    const dataUrl = cv.toDataURL("image/jpeg", 0.85);
    await sleep(250);
    try { fileSave("last_photo.txt", dataUrl); } catch (e) { }
    showPhotoCard(dataUrl);
    return { ok: true, dataUrl, dark: light < 14 };
  } finally {
    stream.getTracks().forEach(t => t.stop());
    try { v.srcObject = null; } catch (e) { }
    box.remove();
    camAt = Date.now();
  }
}

/* ---------- интернет: поиск (DuckDuckGo), страница, погода (open-meteo) ----------
   Провайдер режет поисковик или сайт («Connection reset») — ищем и читаем через сервер Dewiar (cloud.php ?p=/search, /fetch),
   как агент на сайте. Нужен вход в аккаунт dewiar.pro или ключ Dewiar. */
async function dewiarWeb(kind, value) {
  if (S.net.web_via === false) throw new Error("запасной путь через сервер Dewiar выключен в настройках");
  const c = syncCred();
  if (!c) throw new Error("нет входа в аккаунт dewiar.pro и ключа Dewiar");
  const r = await http("GET", c.base + "?p=/" + kind + "&" + (kind === "search" || kind === "images" ? "q=" : "url=") + encodeURIComponent(value), { headers: { Authorization: "Bearer " + c.token }, timeout: 40000 });
  let d = {}; try { d = JSON.parse(r.body || "{}"); } catch (e) { }
  if (r.status !== 200) throw new Error((d.error && d.error.message) || "сервер ответил " + r.status);
  return d;
}
/* Картинки к рассказу (как core/images.py на компьютере): ищем как поисковик картинок — DuckDuckGo Картинки (тот же
   поисковик, что у web_search, безопасный поиск), не открылся — через сервер Dewiar, запасной путь — Wikimedia Commons
   (свободные изображения с автором и лицензией). Показываются под ответом (frameAnswer) и остаются в истории. */
const COMMONS = "https://commons.wikimedia.org/w/api.php", DDG_IMG = "https://duckduckgo.com";
const PIC_SKIP = /\b(?:logo|icon|flag of|coat of arms|map of|locator|signature)\b/i;
const picSite = (u) => { try { return new URL(u).hostname.replace(/^www\./, ""); } catch (e) { return ""; } };
const picClean = (v) => String(v || "").replace(/<[^>]+>/g, " ").replace(/&amp;/g, "&").replace(/&quot;/g, '"').replace(/&#0?39;/g, "'").replace(/\s+/g, " ").trim();
const webPic = (src, full, page, title) => ({ src, full: full || src, page: page || full || src, title: picClean(title).slice(0, 120) || picSite(page) || "картинка",
  desc: "", author: "", license: "", site: picSite(page || full), source: "web" });
async function ddgImages(q, n) {
  const base = window.DEWIAR_DDG || DDG_IMG, UA = { "User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Mobile Safari/537.36", "Accept-Language": "ru-RU,ru;q=0.9" };
  const r = await http("GET", base + "/?" + new URLSearchParams({ q, iax: "images", ia: "images", kp: "1" }), { headers: UA, timeout: 15000 });
  const m = /vqd=["']?([\d-]+)/.exec(r.body || "");
  if (!m) throw new Error("поисковик картинок не дал ключ");
  const r2 = await http("GET", base + "/i.js?" + new URLSearchParams({ l: "ru-ru", o: "json", q, vqd: m[1], f: ",,,,,", p: "1" }), { headers: Object.assign({ Referer: base + "/", Accept: "application/json" }, UA), timeout: 15000 });
  const out = [];
  for (const x of (JSON.parse(r2.body || "{}").results || [])) {
    if (!x.thumbnail || (x.width || 999) < 200 || /\.svg$/i.test(x.image || "") || PIC_SKIP.test(x.title || "")) continue;
    out.push(webPic(x.thumbnail, x.image, x.url, x.title)); if (out.length >= n) break;
  }
  return out;
}
async function commonsImages(q, n) {
  const p = new URLSearchParams({ action: "query", format: "json", generator: "search", gsrnamespace: "6", gsrlimit: "16",
    gsrsearch: q + " filetype:bitmap", prop: "imageinfo", iiprop: "url|extmetadata|mime|size", iiurlwidth: "480",
    iiextmetadatafilter: "ObjectName|ImageDescription|Artist|LicenseShortName", iiextmetadatalanguage: "ru" });
  const j = JSON.parse((await http("GET", (window.DEWIAR_COMMONS || COMMONS) + "?" + p, { headers: { "User-Agent": "Dewiar-Android (voice assistant; https://dewiar.pro)" }, timeout: 15000 })).body || "{}");
  const items = [];
  for (const pg of Object.values((j.query || {}).pages || {}).sort((a, b) => (a.index || 0) - (b.index || 0))) {
    const ii = (pg.imageinfo || [])[0] || {}, meta = ii.extmetadata || {};
    if (!ii.thumburl || !/^image\//.test(ii.mime || "") || ii.mime === "image/svg+xml" || (ii.width || 0) < 200) continue;
    const name = String(pg.title || "").replace(/^File:|\.[a-z0-9]+$/gi, "").replace(/_/g, " ");
    if (PIC_SKIP.test(name)) continue;
    items.push({ src: ii.thumburl, full: (ii.width || 0) > 1280 ? ii.thumburl.replace(/\/\d+px-/, "/1280px-") : (ii.url || ii.thumburl), page: ii.descriptionurl || "",
      title: (picClean((meta.ObjectName || {}).value) || name).slice(0, 120), desc: picClean((meta.ImageDescription || {}).value).slice(0, 200),
      author: picClean((meta.Artist || {}).value).slice(0, 80), license: picClean((meta.LicenseShortName || {}).value).slice(0, 40), site: "commons.wikimedia.org", source: "commons" });
    if (items.length >= n) break;
  }
  return items;
}
async function webImages(q, count) {
  q = String(q || "").trim(); if (!q) return "Ошибка: пустой запрос — что показать?";
  const n = Math.max(1, Math.min(6, +count || 4));
  const ways = [["DuckDuckGo", () => ddgImages(q, n)],
    ["сервер Dewiar", async () => ((await dewiarWeb("images", q)).results || []).filter(x => x.src).slice(0, n).map(x => webPic(x.src, x.full, x.page, x.title))],
    ["Wikimedia Commons", () => commonsImages(q, n)]];
  let items = [], err = null, answered = false, via = "";
  for (const [name, fn] of ways) {
    try { items = await fn(); answered = true; } catch (e) { err = e; plog("info", `🖼 картинки: ${name} не ответил (${e.message})`); continue; }
    if (items.length) { via = name; break; }
  }
  if (!items.length && !answered && err) return "Картинки сейчас не загрузились (" + err.message + ") — скажи об этом коротко.";
  if (!items.length) return "Картинок по этому запросу не нашлось. Не говори, что показала их; можно попробовать запрос проще или по-английски.";
  turnMedia = (turnMedia || []).concat(items).slice(0, 12);
  plog("info", `🖼 картинки: «${clip(q)}» — ${items.length} (${via})`);
  const sites = [...new Set(items.map(x => x.site).filter(Boolean))].slice(0, 4);
  const from = items.every(x => x.source === "commons") ? "Wikimedia Commons" : "поиск картинок" + (sites.length ? " (сайты: " + sites.join(", ") + ")" : "");
  return `На экране показано картинок: ${items.length} (${from}). Что на них (подписи с сайтов):\n` + items.map((x, i) => `${i + 1}. ${x.title}${x.desc ? " — " + x.desc.slice(0, 120) : ""}${x.source !== "commons" && x.site ? " [" + x.site + "]" : ""}`).join("\n")
    + "\nГовори о них как о показанных («на второй картинке…»), но описывай только то, что следует из подписей; не выдумывай деталей. Подпись не о том — не выдавай картинку за нужную.";
}
/* картинка в ответе: нажали — на весь экран (без ухода в браузер), долгое нажатие — источник в браузере */
function wirePics(root) {
  if (!root) return;
  root.querySelectorAll(".dw-pic").forEach(a => {
    a.onclick = (e) => { e.preventDefault(); picView(a.dataset.full || a.querySelector("img").src, a.title || "", a.href, a.dataset.src || a.querySelector("img").src); };
  });
}
function picView(src, title, page, thumb) {
  let v = $("#picview");
  if (!v) { v = document.createElement("div"); v.id = "picview"; v.innerHTML = `<img alt=""><div class="pv-t"></div><button class="btn" id="pv-src">Источник</button>`; document.body.appendChild(v);
    v.onclick = (e) => { if (e.target.id !== "pv-src") v.classList.remove("on"); }; }
  const im = v.querySelector("img"); im.referrerPolicy = "no-referrer";
  im.onerror = () => { if (thumb && im.src !== thumb) im.src = thumb; };      // оригинал с сайта не дался — миниатюра поисковика
  im.src = src; v.querySelector(".pv-t").textContent = title;
  v.querySelector("#pv-src").onclick = () => { if (page) D.openUrl(page); };
  v.classList.add("on");
}
async function webSearch(q) {
  q = String(q || "").trim();
  if (!q) return "Ошибка: пустой запрос — напиши, что искать.";
  let out = [];
  try {
    const r = await http("POST", "https://html.duckduckgo.com/html/", { headers: { "Content-Type": "application/x-www-form-urlencoded", "User-Agent": "Mozilla/5.0 (Linux; Android 14) Dewiar" },
      body: "q=" + encodeURIComponent(q) + "&kl=ru-ru", timeout: 15000 });
    if (r.status !== 200) throw new Error("поисковик ответил " + r.status);
    const re = /<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>([\s\S]*?)<\/a>[\s\S]*?class="result__snippet"[^>]*>([\s\S]*?)<\/a>/g;
    let m;
    while ((m = re.exec(r.body)) && out.length < 6) {
      let u = m[1]; const uu = u.match(/uddg=([^&]+)/); if (uu) u = decodeURIComponent(uu[1]);
      out.push(`${stripHtml(m[2])}\n${stripHtml(m[3])}\n${u}`);
    }
    if (!out.length && /anomaly|captcha/i.test(r.body || "")) throw new Error("поисковик просит капчу");
  } catch (e) {
    try { out = ((await dewiarWeb("search", q)).results || []).slice(0, 6).map(x => `${x.title}\n${x.snippet}\n${x.url}`); }
    catch (e2) { return `Ошибка: поиск недоступен (${e.message}; через сервер Dewiar: ${e2.message}).`; }
  }
  return out.length ? out.join("\n\n") : "Поиск ничего не дал.";
}
/* Длинная страница — начало и куски вокруг слов find (или вопроса); пустая — честно «текста нет» (экзамен 14.10: курс
   доллара стоял дальше 7000 знаков — модель его выдумала; пустая страница журнала — выдумала фильм). Как page_excerpt на компьютере. */
const PAGE_MAX = 7000, PAGE_EMPTY = "Страница открылась, но текста на ней нет (скорее всего, он подгружается скриптом). Ничего не пересказывай за неё и не придумывай — открой другой адрес из поиска или честно скажи, что страница не прочиталась.";
const PAGE_STOP = new Set("какой какая какие каков сегодня сейчас завтра вчера скажи покажи найди пожалуйста можно нужно этот этого много очень только было будет есть где когда почему зачем сколько".split(" "));
function pageTerms(t) {
  const out = [];
  for (const w0 of String(t || "").match(/[A-Za-zА-Яа-яЁё0-9]{4,}/g) || []) { const w = w0.toLowerCase(); if (!PAGE_STOP.has(w) && !/^\d+$/.test(w) && !out.includes(w.slice(0, 5))) out.push(w.slice(0, 5)); }
  return out.slice(0, 8);
}
function pageExcerpt(text, find, question) {
  text = String(text || "").trim();
  if (text.replace(/\s+/g, "").length < 80) return PAGE_EMPTY;
  if (text.length <= PAGE_MAX) return text;
  const terms = pageTerms(find).length ? pageTerms(find) : pageTerms(question), low = text.toLowerCase(), spans = [];
  for (const t of terms) { let i = low.indexOf(t, 1500); while (i >= 0 && spans.length <= 40) { spans.push([Math.max(1500, i - 500), Math.min(text.length, i + t.length + 700)]); i = low.indexOf(t, i + t.length); } }
  spans.sort((a, b) => a[0] - b[0]);
  const merged = [];
  for (const [a, b] of spans) { if (merged.length && a <= merged[merged.length - 1][1]) merged[merged.length - 1][1] = Math.max(merged[merged.length - 1][1], b); else merged.push([a, b]); }
  if (!merged.length) return text.slice(0, PAGE_MAX) + `…\n[Страница длиннее: показано ${PAGE_MAX} из ${text.length} знаков. Если нужного здесь нет — вызови read_webpage ещё раз с find (что ищешь, например «Доллар США»); не додумывай.]`;
  const out = [text.slice(0, 1500)]; let left = PAGE_MAX - 1500;
  for (const [a, b] of merged) { if (left <= 200) break; const piece = text.slice(a, Math.min(b, a + left)); out.push(piece); left -= piece.length; }
  return out.join("\n…\n") + `\n[Страница длинная (${text.length} знаков): выше начало и места со словами «${terms.join(", ")}». Чего здесь нет — того на странице не видно; не додумывай.]`;
}
function pageLinks(page, base, limit = 30) {
  let host = ""; try { host = new URL(base).host; } catch (e) { return []; }
  const seen = new Set([base.split("#")[0].replace(/\/$/, "")]), out = [];
  for (const m of page.matchAll(/<a\b[^>]*?href=["']([^"'#][^"']*)["'][^>]*>([\s\S]*?)<\/a>/gi)) {
    let u = ""; try { u = new URL(m[1].replace(/&amp;/g, "&"), base).href.split("#")[0]; } catch (e) { continue; }
    const t = stripHtml(m[2]);
    if (!u.startsWith("http") || new URL(u).host !== host || !t || t.length > 90 || /\.(png|jpe?g|gif|svg|pdf|zip|css|js|xml|ico)(\?|$)/i.test(u) || seen.has(u.replace(/\/$/, ""))) continue;
    seen.add(u.replace(/\/$/, "")); out.push([t, u]); if (out.length >= limit) break;
  }
  return out;
}
async function readPage(url, find) {
  if (!/^https?:/.test(url)) url = "https://" + url;
  try {
    const r = await http("GET", url, { headers: { "User-Agent": "Mozilla/5.0 (Linux; Android 14) Dewiar" }, timeout: 20000 });
    if (r.status === 403 || r.status === 451) throw new Error("сайт не пускает (" + r.status + ")");
    // отчёт №69 (как на компьютере, tools.html_to_text): без меню и боковых панелей; есть <main>/<article> — он;
    // в конце — разделы того же сайта, их можно открыть
    let h = String(r.body || "").replace(/<(nav|header|footer|aside|noscript|svg)\b[\s\S]*?<\/\1>/gi, " ");
    const main = /<(main|article)\b[^>]*>([\s\S]*)<\/\1>/i.exec(h);
    if (main && stripHtml(main[2]).length > 200) h = main[2];
    const out = pageExcerpt(stripHtml(h), find, turnQ), links = pageLinks(String(r.body || ""), url);
    return links.length >= 3 && !/^Страница открылась, но текста/.test(out) ? out + "\n\nРазделы этого сайта (нужное можно открыть read_webpage по адресу):\n" + links.map(([t, u]) => `- ${t} — ${u}`).join("\n") : out;
  } catch (e) {
    try { return pageExcerpt(String((await dewiarWeb("fetch", url)).text || ""), find, turnQ); }
    catch (e2) { return `Ошибка: страница не открылась (${e.message}).`; }
  }
}
const WMO = { 0: "ясно", 1: "в основном ясно", 2: "переменная облачность", 3: "пасмурно", 45: "туман", 48: "изморозь", 51: "морось", 53: "морось", 55: "сильная морось",
  61: "небольшой дождь", 63: "дождь", 65: "сильный дождь", 66: "ледяной дождь", 67: "ледяной дождь", 71: "небольшой снег", 73: "снег", 75: "сильный снег", 77: "снежная крупа",
  80: "ливень", 81: "ливни", 82: "сильные ливни", 85: "снегопад", 86: "сильный снегопад", 95: "гроза", 96: "гроза с градом", 99: "гроза с градом" };
/* Который час в другом городе — по часовому поясу (Intl), а не «в уме» (отчёт №131, 20.10: модель вычла 3 часа вместо
   прибавления). Частые города — таблица (как CITY_TZ в core/tools.py), остальные — геокодер Open-Meteo (поле timezone). */
const CITY_TZ = {"москв": "Europe/Moscow", "петербург": "Europe/Moscow", "питер": "Europe/Moscow", "калининград": "Europe/Kaliningrad", "самар": "Europe/Samara", "екатеринбург": "Asia/Yekaterinburg", "челябинск": "Asia/Yekaterinburg", "уф": "Asia/Yekaterinburg", "тюмен": "Asia/Yekaterinburg", "омск": "Asia/Omsk", "новосибирск": "Asia/Novosibirsk", "томск": "Asia/Tomsk", "барнаул": "Asia/Barnaul", "красноярск": "Asia/Krasnoyarsk", "кемерово": "Asia/Novokuznetsk", "новокузнецк": "Asia/Novokuznetsk", "иркутск": "Asia/Irkutsk", "улан-удэ": "Asia/Irkutsk", "чит": "Asia/Chita", "якутск": "Asia/Yakutsk", "владивосток": "Asia/Vladivostok", "хабаровск": "Asia/Vladivostok", "магадан": "Asia/Magadan", "сахалин": "Asia/Sakhalin", "южно-сахалинск": "Asia/Sakhalin", "камчат": "Asia/Kamchatka", "петропавловск-камчатск": "Asia/Kamchatka", "минск": "Europe/Minsk", "киев": "Europe/Kyiv", "алмат": "Asia/Almaty", "астан": "Asia/Almaty", "ташкент": "Asia/Tashkent", "бишкек": "Asia/Bishkek", "ереван": "Asia/Yerevan", "тбилиси": "Asia/Tbilisi", "баку": "Asia/Baku", "лондон": "Europe/London", "париж": "Europe/Paris", "берлин": "Europe/Berlin", "рим": "Europe/Rome", "мадрид": "Europe/Madrid", "стамбул": "Europe/Istanbul", "дуба": "Asia/Dubai", "пекин": "Asia/Shanghai", "токио": "Asia/Tokyo", "сеул": "Asia/Seoul", "бангкок": "Asia/Bangkok", "дели": "Asia/Kolkata", "нью-йорк": "America/New_York", "чикаго": "America/Chicago", "лос-анджелес": "America/Los_Angeles", "сан-франциско": "America/Los_Angeles", "торонто": "America/Toronto", "сидне": "Australia/Sydney", "иерусалим": "Asia/Jerusalem", "тель-авив": "Asia/Jerusalem"};
async function cityTz(city) {
  const c = String(city || "").toLowerCase().replace(/ё/g, "е").trim();
  for (const [k, tz] of Object.entries(CITY_TZ)) if (c.startsWith(k)) return { name: city, tz };
  try {
    const g = JSON.parse((await http("GET", "https://geocoding-api.open-meteo.com/v1/search?count=1&language=ru&name=" + encodeURIComponent(city), { timeout: 10000 })).body || "{}");
    const p = (g.results || [])[0]; return p && p.timezone ? { name: p.name || city, tz: p.timezone } : null;
  } catch (e) { return null; }
}
function tzOffsetMin(tz, d) {                    // смещение пояса от UTC в минутах — через Intl, без библиотек
  const f = new Intl.DateTimeFormat("en-US", { timeZone: tz, hourCycle: "h23", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
  const o = Object.fromEntries(f.formatToParts(d).map(x => [x.type, x.value]));
  return Math.round((Date.UTC(+o.year, +o.month - 1, +o.day, +o.hour % 24, +o.minute) - Math.floor(d.getTime() / 6e4) * 6e4) / 6e4);
}
async function worldTime(city, prep, now) {
  const z = await cityTz(city); if (!z) return null;
  now = now || new Date();
  let off; try { off = tzOffsetMin(z.tz, now); } catch (e) { return null; }
  const there = new Date(now.getTime() + (off + now.getTimezoneOffset()) * 6e4), diff = Math.round((off + now.getTimezoneOffset()) / 6) / 10;
  const n = Math.abs(diff), word = n !== Math.floor(n) ? "часа" : n % 10 === 1 && n % 100 !== 11 ? "час" : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 12 || n % 100 > 14) ? "часа" : "часов";
  const rel = diff === 0 ? "как у вас" : `на ${String(n).replace(".", ",")} ${word} ${diff > 0 ? "больше" : "меньше"}, чем у вас`;
  const dd = Math.round((new Date(there.getFullYear(), there.getMonth(), there.getDate()) - new Date(now.getFullYear(), now.getMonth(), now.getDate())) / 864e5);
  const day = dd > 0 ? ", там уже завтра" : dd < 0 ? ", там ещё вчера" : "";
  const hm = `${there.getHours()}:${String(there.getMinutes()).padStart(2, "0")}`;
  const nm = String(prep ? city : z.name).replace(/(^|[ -])([а-яё])/g, (x, a, b) => a + b.toUpperCase());
  return prep ? `${prep[0].toUpperCase() + prep.slice(1)} ${nm} сейчас ${hm}${day} — ${rel}.` : `${nm}: сейчас ${hm}${day} — ${rel}.`;
}
async function weather(city, days) {
  if (!city) return "Ошибка: спроси, в каком городе.";
  const g = JSON.parse((await http("GET", "https://geocoding-api.open-meteo.com/v1/search?count=1&language=ru&name=" + encodeURIComponent(city), { timeout: 12000 })).body || "{}");
  const p = (g.results || [])[0]; if (!p) return `Город «${city}» не нашёлся.`;
  const u = `https://api.open-meteo.com/v1/forecast?latitude=${p.latitude}&longitude=${p.longitude}&current=temperature_2m,apparent_temperature,weather_code,wind_speed_10m,precipitation&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max&timezone=auto&forecast_days=${Math.min(7, Math.max(1, days))}`;
  const w = JSON.parse((await http("GET", u, { timeout: 12000 })).body || "{}"), c = w.current || {}, d = w.daily || {};
  const lines = [`${p.name}: сейчас ${Math.round(c.temperature_2m)}°, ощущается как ${Math.round(c.apparent_temperature)}°, ${WMO[c.weather_code] || ""}, ветер ${Math.round(c.wind_speed_10m)} км/ч.`];
  const dayName = (t) => { const k = Math.round((new Date(t + "T12:00") - new Date(isoLocal(new Date()).slice(0, 10) + "T12:00")) / 864e5); return k === 0 ? " (сегодня)" : k === 1 ? " (завтра)" : k === 2 ? " (послезавтра)" : ""; };
  (d.time || []).forEach((t, i) => lines.push(`${t}${dayName(t)}: ${Math.round(d.temperature_2m_min[i])}…${Math.round(d.temperature_2m_max[i])}°, ${WMO[d.weather_code[i]] || ""}, осадки ${d.precipitation_probability_max[i] != null ? d.precipitation_probability_max[i] : 0}%.`));
  return lines.join("\n");
}

/* ---------- заметки и деньги — файлы notes.json и money.json в памяти приложения (Dewiar.files/saveFile);
   после каждой записи — синхронизация с компьютером (syncSoon) ---------- */
const notes = () => { try { return JSON.parse(fileGet("notes.json") || "[]"); } catch (e) { return []; } };
// напоминания телефона; в экзамене — его песочница (exam.js: EXAM.alarms), настоящие будильники не трогаем
const alarmsNow = () => (typeof EXAM !== "undefined" && EXAM ? EXAM.alarms.slice() : JSON.parse(D.alarms() || "[]"));
const NOTE_GENERIC = /^(?:заметк\w*|все|всё|мои|мой|моих|последн\w*|покажи|прочитай|список|какие|есть|что|там|записи|запис\w*|сохран\w*)$/;
const NOTES_SHOW_RX = /^(?:(?:покажи|открой|прочитай|выведи|какие|что)\s+)?(?:(?:у\s+меня\s+)?(?:есть\s+)?(?:в\s+)?)?(?:мои\s+|все\s+)?(?:заметк(?:и|ах))(?:\s+(?:у\s+меня|есть))?$/;
const NOTE_RX = /^(?:(?:запиши|запишите|сохрани|добавь|занеси|сделай|создай|оставь)(?:\s+(?:мне|себе|пожалуйста))*\s+)?(?:в\s+)?(?:заметк(?:а|у|и|ах)|новую\s+заметку)(?:\s+(?:что|о том,?\s+что))?\s*[:,—–-]?\s+(\S[\s\S]{2,})$/i;
/* -> текст ответа, если фраза — явная просьба записать заметку (и заметка записана), иначе "" */
/* «Запомни: в среду в 15:00 у меня встреча с подрядчиком» — сразу в память, без модели (как capture.py на компьютере).
   Экзамены 0.6.40: модель то вызывала remember без факта, то вместо памяти спрашивала про календарь — и через новый
   разговор на «что у меня в среду?» отвечала «пусто». День плана — точной датой: через неделю «в среду» уже другая. */
const FACT_RX = /^(?:(?:а|и|ну|пожалуйста|слушай)\s+)*запомни(?:те)?(?:\s*,?\s*(?:себе|мне|пожалуйста)(?![а-яё]))*\s*[:,.\-—]?\s*([\s\S]+)$/i;
const FACT_ME = /(?<![а-яё])(?:я|у меня|у нас|мне|нам|мы|мой|моя|моё|мое|мои|моего|моей|моим|мою|наш[а-яё]*)(?![а-яё])/i;
const FACT_SKIP = /^(?:(?:для|на время|в рамках|пока идет|до конца)\s+(?:этого\s+|нашего\s+)?(?:разговор|беседы|чата|диалог)|это\b|вот это\b|то,? что\b|(?:про|о|об|обо)\s+)/i;
const DAY_WORD = /(?<![а-яё])(?:сегодня|завтра|послезавтра|(?:в|во|на)\s+(?:понедельник|вторник|среду|четверг|пятницу|субботу|воскресенье)|\d{1,2}\s+(?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)|\d{1,2}\.\d{1,2})(?![а-яё])/i;
function factQuick(text) {
  const t = String(text || "").trim().replace(/^[А-ЯЁA-Z][а-яёa-z-]+\s*,\s*(?=\S)/, (m) => findPersona(m.replace(/[\s,]/g, ""), true) ? "" : m);
  const m = FACT_RX.exec(t); if (!m) return "";
  const body = m[1].trim().replace(/^(?:о\s+том\s*,?\s*)?что\s+/i, "").replace(/[.!…\s]+$/, "");
  if (body.length < 3 || body.length > 200 || FACT_SKIP.test(body) || !FACT_ME.test(body) || /\?$/.test(body)) return "";
  let day = null;
  if (DAY_WORD.test(body)) { const w = parseWhen(body); if (w && w.at && !w.rel) { day = new Date(w.at); day.setHours(0, 0, 0, 0); } }
  const fact = `Со слов пользователя: ${body}` + (day ? ` (на ${pad(day.getDate())}.${pad(day.getMonth() + 1)}.${day.getFullYear()}, ${WD[day.getDay()]})` : "") + ".";
  if (!S.memory.includes(fact)) { S.memory.push(fact); S.memory = S.memory.slice(-80); saveS(); syncSoon(); }
  plog("info", "🧠 запомнила без модели" + (day ? ` (на ${day.getDate()} ${MON[day.getMonth()]})` : ""));
  if (SANDBOX) SANDBOX.dev.push({ name: "remember", args: fact, argsObj: { fact }, t: Date.now() });
  const she = persona().gender === "female" ? "Запомнила" : "Запомнил";
  const w = WD[day ? day.getDay() : 0], inDay = (w === "вторник" ? "во " : "в ") + ({ среда: "среду", пятница: "пятницу", суббота: "субботу" }[w] || w);
  return day ? `${she}: ${inDay}, ${day.getDate()} ${MON[day.getMonth()]}.` : `${she}.`;
}
/* Значок «Записать» (CaptureWidget): приложение открылось — сразу слушаем; сказанное — напоминание («напомни…»), заметка
   («запиши…») или мысль в «Заметки/Идеи» как есть, без модели. Записали — через пару секунд обратно на рабочий стол. */
let captureAt = 0, captureHome = 0;
function captureStart() {
  closeSheets(); captureAt = Date.now(); vCount("capture");
  showBot("Говорите — запишу в «Идеи». «Напомни завтра в 10…» — поставлю напоминание.");
  setTimeout(() => { if (state === "idle" || state === "speaking") listen(); }, 250);
}
function captureBack() {
  clearTimeout(captureHome);
  // ответ договорён (или текстом) — уходим на рабочий стол; человек начал что-то делать в приложении — остаёмся
  const t0 = Date.now(), tick = () => { if (Date.now() - lastUserAct < 1500 && Date.now() - t0 > 1500) return;
    if (state === "idle" && !busy) { try { D.home(); } catch (e) { } return; } if (Date.now() - t0 < 20000) captureHome = setTimeout(tick, 500); };
  captureHome = setTimeout(tick, 2600);
}
function ideaNote(text, att) {
  let body = String(text || "").trim().replace(/^[«"]|[»"]$/g, "");
  body = body ? body[0].toUpperCase() + body.slice(1) : "Фото";
  const words = body.replace(/[.!?…].*$/s, "").split(/\s+/), title = words.slice(0, 6).join(" ").replace(/[,:;—–-]+$/, "") + (words.length > 6 ? "…" : "");
  const files = noteAttSave(att || []); turnAtt = [];
  const n = notes(); n.push(Object.assign({ id: "n" + Date.now(), title, text: body, time: Date.now(), folder: "Идеи" }, files.length ? { att: files } : {})); saveNotes(n);
  plog("info", "💡 идея без модели: " + clip(title, 60));
  return `${persona().gender === "female" ? "Записала" : "Записал"} в «Идеи».`;
}
/* Папки заметок (№195, 22.10: «было бы удобно, если бы в заметках был функционал создания папок, особенно в мобильной
   версии»). Папка — поле folder заметки: с компьютера оно приходит путём («Заметки/Работа/…»), отсюда уходит туда же —
   компьютер переносит файл в эту папку (core/sync.py). Одна ступень: «Работа», «Блокнот», «Идеи». */
let ntFolder = "";                               // фильтр «Заметок»: "" — все
function noteFolders() {
  const set = new Set(notes().map(x => String(x.folder || "").trim()).filter(Boolean));
  return [...set].sort((a, b) => (a === "Блокнот" ? -1 : b === "Блокнот" ? 1 : a.localeCompare(b, "ru")));
}
function folderName(raw) {
  let f = String(raw || "").replace(/[\\/:*?"<>|«»]+/g, " ").replace(/\s+/g, " ").trim().slice(0, 40);
  if (!f) return "";
  const same = noteFolders().find(x => x.toLowerCase() === f.toLowerCase() || (f.length >= 5 && x.toLowerCase().slice(0, 5) === f.toLowerCase().slice(0, 5)));
  return same || f.charAt(0).toUpperCase() + f.slice(1);     // «в папку работу» → уже есть «Работа»
}
const NOTE_FOLDER_RX = /^(?:запиши|запишите|сохрани|добавь|занеси|положи)(?:\s+(?:мне|себе|пожалуйста))*\s+(?:в\s+)?(?:заметк[уи]\s+)?(?:в\s+)?папк[уеи]\s+«?([^:«»"\n]{1,40}?)»?\s*[:,—–-]\s*(\S[\s\S]{2,})$/i;
function noteQuick(text, att) {
  const t = String(text || "").trim().replace(/^[А-ЯЁA-Z][а-яёa-z-]+\s*,\s*(?=\S)/, (m) => findPersona(m.replace(/[\s,]/g, ""), true) ? "" : m);
  const mf = NOTE_FOLDER_RX.exec(t);
  const m = mf ? [mf[0], mf[2]] : NOTE_RX.exec(t); if (!m) return "";
  const folder = mf ? folderName(mf[1]) : "";
  let body = m[1].trim().replace(/^[«"]|[»"]$/g, "");
  if (!/[а-яёa-z0-9]/i.test(body) || /^(?:что|как|где|сколько|покажи|прочитай)(?:\s|$)/i.test(body)) return "";   // «в заметках что?» — не запись
  body = body.charAt(0).toUpperCase() + body.slice(1);
  const words = body.replace(/[.!?…].*$/s, "").split(/\s+/), title = words.slice(0, 6).join(" ").replace(/[,:;—–-]+$/, "") + (words.length > 6 ? "…" : "");
  const files = noteAttSave(att || []); turnAtt = [];
  const n = notes(); n.push(Object.assign({ id: "n" + Date.now(), title, text: body, time: Date.now() }, files.length ? { att: files } : {}, folder ? { folder } : {})); saveNotes(n);
  plog("info", "📝 заметка без модели: " + clip(title, 60) + (folder ? ` → папка «${folder}»` : "") + (files.length ? ` + вложений ${files.length}` : ""));
  if (SANDBOX) SANDBOX.dev.push({ name: "save_note", args: title, t: Date.now() });      // экзамен: действие видно, как фонарик
  // без пересказа: название обрезано («…»), и вслух это звучало как оборванная фраза (отзыв 11.10)
  const pics = files.filter(f => f.type === "image").length;
  return `${persona().gender === "female" ? "Записала" : "Записал"} ${folder ? `в папку «${folder}»` : "в заметки"}` + (!files.length ? "." : files.length === 1 ? (pics ? " вместе с фото." : " вместе с файлом.") : ` — вложений: ${files.length}.`);
}
/* Напоминание с вложениями (идея 16.10: «на завтра напоминание, и чтобы там пара скриншотов, и удобно сразу посмотреть»):
   «напомни завтра в 10» + фото (скрепка или «Поделиться» из галереи) — заметка «Напоминания» с этими фото и напоминание
   с note = её id. В срок окно напоминания показывает «Посмотреть вложения» (AlarmActivity → openNote). Заметка уходит
   на компьютер синхронизацией, фото — зашифрованным каналом (noteAttShare), и там окно-будильник покажет их миниатюрами. */
const REMIND_GENERIC = /^(?:напоминание|(?:(?:об?|про)\s+)?(?:это|этом|этой|этого|них|ней|нем|нём|него|неё|нее)|(?:(?:об?|про)\s+)?(?:эт[а-яё]+\s+)?(?:скрин[а-яё]*|фот[а-яё]*|картинк[а-яё]*|снимк[а-яё]*|файл[а-яё]*))?$/i;
function remindNote(title, at, said, att) {
  const files = noteAttSave(att || []); if (!files.length) return null;
  const pics = files.filter(f => f.type === "image").length;
  let t = String(title || "").trim();
  if (REMIND_GENERIC.test(t)) t = pics === files.length ? "Посмотреть фото" : !pics ? "Посмотреть файлы" : "Посмотреть вложения";
  t = t[0].toUpperCase() + t.slice(1);
  const d = new Date(at), body = `Напоминание — ${d.getDate()} ${MON[d.getMonth()]} в ${pad(d.getHours())}:${pad(d.getMinutes())}.` + (said ? `\n\n«${String(said).trim()}»` : "");
  const n = { id: "n" + Date.now(), title: t, text: body, time: Date.now(), folder: "Напоминания", att: files };
  const all = notes(); all.push(n); saveNotes(all);
  plog("info", `📎 напоминание с вложениями (${files.length}) → заметка «${clip(t, 50)}»`);
  if (SANDBOX) SANDBOX.dev.push({ name: "save_note", args: t, t: Date.now() });
  return n;
}
function remindAttQuick(text, att) {
  const t = String(text || "").trim().replace(/^[А-ЯЁA-Z][а-яёa-z-]+\s*,\s*(?=\S)/, (m) => findPersona(m.replace(/[\s,]/g, ""), true) ? "" : m).toLowerCase().replace(/ё/g, "е");
  const m = t.match(/^напомни(?:те)?(?: мне)?\s+(.+)$/) || t.match(/^напоминай(?: мне)?\s+(.+)$/); if (!m) return null;
  const w = parseWhen(m[1]); if (!w) return null;
  let what = remindWhat(w.rest);
  const n = remindNote(what, w.at, text, att); if (!n) return null;
  turnAtt = [];
  const x = addAlarm(n.title, w.at, "reminder", w.repeat, n.id);
  const pics = n.att.filter(f => f.type === "image").length, many = n.att.length > 1;
  const tail = pics === n.att.length ? (many ? "Фото будут прямо в напоминании." : "Фото будет прямо в напоминании.") : (many ? "Файлы будут прямо в напоминании." : "Файл будет прямо в напоминании.");
  return { say: `Напомню ${REP_RU[w.repeat] ? REP_RU[w.repeat] + ", " : ""}${whenText(w.at)}: ${n.title[0].toLowerCase() + n.title.slice(1)}. ${tail}`, card: alarmCard(x) };
}
/* ---------- заметка целиком: открыть, поправить, фото и файлы (лист #sh-note) ----------
   Вложения — файлы natt-<id> во внутренней памяти (data: URL; фото сжаты shrinkImage), в заметке — только их список att.
   Синхронизация уносит на компьютер текст заметки; вложения — зашифрованным каналом своих устройств (noteAttShare). */
let turnAtt = [], turnAsk = "", noteCur = "", notePend = [];
const noteBody = (t) => String(t || "").replace(/^\s*#[^\n]*\n+(\*[^\n]*\*\n+)?/, "");   // заметка с компьютера: без заголовка и даты
// строки-ссылки на вложения компьютера («![фото.jpg](Вложения/…)», «📎 [план.pdf](Вложения/…)», core/workspace.py NOTE_LINK_RX):
// в тексте на телефоне их не показываем, а при сохранении возвращаем в конец — иначе ссылки потерялись бы на компьютере
const NOTE_LINK_LINE = /^[ \t]*(?:📎\s*)?!?\[[^\]\n]*\]\(Вложения\/[^)\s]+\)[ \t]*$/gm;
const noteShown = (t) => noteBody(t).replace(NOTE_LINK_LINE, "").replace(/\n{3,}/g, "\n\n").trim();
const noteLinks = (t) => (String(t || "").match(NOTE_LINK_LINE) || []).map(x => x.trim());
const noteAttGet = (id) => fileGet("natt-" + id) || "";
const noteAttCount = (n) => (n.att || []).length || noteLinks(n.text).length;     // свои вложения или ссылки на вложения компьютера
function noteAttSave(list) {
  return (list || []).filter(a => a && (a.url || a.text != null)).slice(0, 12).map((a, i) => {
    const id = "na" + Date.now().toString(36) + i + Math.random().toString(36).slice(2, 5);
    const data = a.url || ("data:text/plain;charset=utf-8," + encodeURIComponent(a.text || ""));
    fileSave("natt-" + id, data);
    return { id, name: String(a.name || (a.kind === "image" ? "фото" : "файл")).slice(0, 120), type: a.kind === "image" || /^data:image\//.test(data) ? "image" : (a.type || "file"), size: Math.round(data.length * 0.75) };
  });
}
/* Удалить заметку: всегда спрашиваем, и ещё 8 секунд можно «Вернуть» — вместе с вложениями (отзыв 11.10: одно
   случайное нажатие — и заметки нет). Удалить — только из открытой заметки, крестика в списке нет. */
function noteDelete(id, ask) {
  const n = notes().find(x => x.id === id); if (!n) return;
  if (ask && !confirm(`Удалить заметку «${n.title}»${(n.att || []).length ? " вместе с вложениями" : ""}?`)) return;
  const keep = (n.att || []).map(a => [a.id, noteAttGet(a.id)]);
  (n.att || []).forEach(a => fileSave("natt-" + a.id, ""));
  saveNotes(notes().filter(x => x.id !== id)); if (noteCur === id) closeSheets(); renderDay();
  if (ask) undoBar("Заметка удалена", () => {
    keep.forEach(([aid, data]) => fileSave("natt-" + aid, data));
    const all = notes(); if (!all.some(x => x.id === n.id)) { all.push(n); saveNotes(all); }
    renderDay(); toast("Заметка возвращена");
  });
}
function undoBar(text, onUndo, ms = 8000) {
  let el = $("#undo"); if (!el) { el = document.createElement("div"); el.id = "undo"; document.body.appendChild(el); }
  el.innerHTML = `<span>${esc(text)}</span><button>Вернуть</button>`; el.classList.add("on");
  clearTimeout(el._t); el._t = setTimeout(() => el.classList.remove("on"), ms);
  el.querySelector("button").onclick = () => { clearTimeout(el._t); el.classList.remove("on"); onUndo(); };
}
// заметка напоминания: может ещё не прийти с компьютера — синхронизируем и пробуем снова
async function openNoteSoon(id) {
  closeSheets();
  if (!notes().some(x => x.id === id)) { toast("Получаю заметку с вложениями…", 2500); try { await syncRun(true); } catch (e) { } }
  if (notes().some(x => x.id === id)) openNote(id); else toast("Заметка с вложениями ещё не пришла — проверьте, что компьютер включён", 4000);
}
function openNote(id) { noteCur = id || ""; notePend = []; renderNote(); openSheet("#sh-note"); if (!id) setTimeout(() => $("#nt-text") && $("#nt-text").focus(), 300); }
function renderNote() {
  const n = noteCur ? notes().find(x => x.id === noteCur) : null, att = (n ? n.att || [] : []).concat(notePend);
  $("#nt-h").textContent = n ? "Заметка" : "Новая заметка";
  $("#note-body").innerHTML = `<input id="nt-title" placeholder="Заголовок" maxlength="120" value="${esc(n ? n.title : "")}">
    <textarea id="nt-text" placeholder="Текст заметки…">${esc(n ? noteShown(n.text) : "")}</textarea>
    <label class="ntfold"><span>Папка</span><input id="nt-folder" list="nt-folders" placeholder="без папки" maxlength="40" value="${esc(n ? n.folder || "" : ntFolder)}"><datalist id="nt-folders">${noteFolders().map(f => `<option value="${esc(f)}">`).join("")}</datalist></label>
    <div class="ntatt">${att.map(a => a.type === "image" ? `<button class="ntimg" data-id="${esc(a.id)}"><img src="${a.data || noteAttGet(a.id)}" alt="${esc(a.name)}"></button>`
      : `<button class="ntf" data-id="${esc(a.id)}">📎 ${esc(a.name)}<small>${fsize(a.size)}</small></button>`).join("")}</div>
    <div class="ntadd"><label class="btn"><input type="file" id="nt-photo" accept="image/*" multiple hidden>Добавить фото</label><label class="btn"><input type="file" id="nt-file" multiple hidden>Добавить файл</label></div>
    <div class="row2"><button class="btn p" id="nt-save" style="flex:1">Сохранить</button>${n ? `<button class="btn" id="nt-share">Поделиться</button><button class="btn" id="nt-del">Удалить</button>` : ""}</div>`;
  const view = (a) => a.type === "image" ? imgView(a.data || noteAttGet(a.id)) : noteFileSave(a);
  $$("#note-body .ntimg, #note-body .ntf").forEach(b => b.onclick = () => { const a = att.find(x => x.id === b.dataset.id); if (a) view(a); });
  const add = async (files, photo) => {
    for (const f of Array.from(files || [])) {
      if (f.size > 10 * 1024 * 1024) { toast(`«${f.name}» больше 10 МБ`); continue; }
      try {
        const url = photo || /^image\//.test(f.type) ? await shrinkImage(f) : await new Promise((ok, no) => { const r = new FileReader(); r.onload = () => ok(r.result); r.onerror = () => no(new Error("не прочитался")); r.readAsDataURL(f); });
        const one = { kind: /^data:image\//.test(url) ? "image" : "file", name: f.name || "файл", type: f.type, url };
        if (n) { const saved = noteAttSave([one]); const all = notes(); const x = all.find(y => y.id === n.id); if (x) { x.att = (x.att || []).concat(saved); x.time = Date.now(); saveNotes(all); } }
        else notePend.push({ id: "p" + Date.now() + notePend.length, name: one.name, type: one.kind === "image" ? "image" : (f.type || "file"), size: f.size, data: url, src: one });
      } catch (e) { toast("Не получилось добавить: " + e.message); }
    }
    keepTyped(); renderNote(); restoreTyped();
  };
  let typed = null; const keepTyped = () => { typed = { t: $("#nt-title").value, x: $("#nt-text").value, f: $("#nt-folder").value }; };
  const restoreTyped = () => { if (typed) { $("#nt-title").value = typed.t; $("#nt-text").value = typed.x; $("#nt-folder").value = typed.f; } };
  $("#nt-photo").onchange = (e) => add(e.target.files, true);
  $("#nt-file").onchange = (e) => add(e.target.files, false);
  $("#nt-save").onclick = () => {
    const title = $("#nt-title").value.trim(), text = $("#nt-text").value.trim();
    if (!title && !text && !notePend.length) { toast("Пустая заметка"); return; }
    const all = notes(), t0 = title || text.split(/\n/)[0].slice(0, 60) || "Фото", fold = folderName($("#nt-folder").value);
    if (n) { const x = all.find(y => y.id === n.id), ln = noteLinks(x && x.text); if (x) { x.title = t0; x.text = text + (ln.length ? "\n\n" + ln.join("\n") : ""); x.time = Date.now(); x.folder = fold; } }
    else all.push(Object.assign({ id: "n" + Date.now(), title: t0, text, time: Date.now() }, notePend.length ? { att: noteAttSave(notePend.map(p => p.src)) } : {}, fold ? { folder: fold } : {}));
    notePend = []; saveNotes(all); closeSheets(); renderDay(); openSheet("#sh-day"); toast("Заметка сохранена");
  };
  if (n) {
    $("#nt-del").onclick = () => noteDelete(n.id, true);
    $("#nt-share").onclick = () => D.share((n.title ? n.title + "\n\n" : "") + noteShown(n.text));
  }
}
function noteFileSave(a) {
  const d = noteAttGet(a.id), m = /^data:([^;,]*)(?:;[^;,=]+=[^;,]*)*(;base64)?,(.*)$/s.exec(d);
  if (!m) { toast("Файл не найден"); return; }
  const b64 = m[2] ? m[3] : btoa(unescape(encodeURIComponent(decodeURIComponent(m[3]))));
  const where = D.saveDownloadB64 ? D.saveDownloadB64(a.name, m[1] || "application/octet-stream", b64) : "";
  toast(where ? "Сохранено: " + where : "Не получилось сохранить", 3500);
}
function imgView(src) { const v = $("#imgview"); $("img", v).src = src; v.classList.add("on"); v.onclick = () => { v.classList.remove("on"); $("img", v).src = ""; }; }
const saveNotes = (n) => { fileSave("notes.json", JSON.stringify(n)); syncSoon(); if (n.some(x => (x.att || []).some(a => !a.pc))) noteAttSoon(); };
/* Фото и файлы заметок — на свои компьютеры (отзыв 11.10). Тем же зашифрованным каналом, что ключ умного дома: файл
   шифруется своим ключом и кладётся в облако (/close/file себе), ключ к нему — в конверте /close/self {natt}, который
   откроют только мои устройства (core/close.py _natt_add: к той же заметке, когда она придёт синхронизацией). Отправленное
   помечается a.pc (время; -1 — не отправить вовсе); нет связи или других устройств — попробуем при следующей проверке. */
var nattBusy = false, nattT = 0;               // var: saveNotes может позвать до этой строки
function noteAttSoon(ms) { clearTimeout(nattT); nattT = setTimeout(() => noteAttShare().catch(e => plog("info", "вложения заметок на компьютер: " + e.message)), ms || 4000); }
async function noteAttShare() {
  if (nattBusy || SANDBOX || !syncCred() || !DC()) return 0;
  const todo = notes().filter(n => (n.att || []).some(a => !a.pc)); if (!todo.length) return 0;
  nattBusy = true;
  try {
    const k = clKeys(); if (!clLoad().me.pid || Date.now() - (CLS.hello || 0) > 600000) await clHello();
    const t = {}; ((CLS.me || {}).devs || []).forEach(d => { if (d.pub && d.dev && d.dev !== k.dev) t[d.dev] = DC().b64d(d.pub); });
    if (!Object.keys(t).length || !CLS.me.pid) return 0;              // других своих устройств пока нет
    t[k.dev] = DC().b64d(k.pub);
    let sent = 0;
    for (const n of todo.slice(0, 3)) {                                // не больше трёх заметок за раз: у облака лимит конвертов в час
      const files = [], mark = {};
      for (const a of n.att.filter(a => !a.pc)) {
        const m = /^data:([^;,]*)(?:;[^;,=]+=[^;,]*)*(;base64)?,(.*)$/s.exec(noteAttGet(a.id));
        const bin = !m ? null : m[2] ? Uint8Array.from(atob(m[3]), c => c.charCodeAt(0)) : new TextEncoder().encode(decodeURIComponent(m[3]));
        if (!bin || !bin.length || bin.length > 10 * 1024 * 1024) { mark[a.id] = -1; continue; }
        const fk = DC().randomBytes(32);
        const d = await clReq("POST", "/close/file", clStdB64(DC().seal(fk, bin)), "&b64=1&to=" + encodeURIComponent(CLS.me.pid));
        files.push({ id: d.id, key: DC().b64e(fk), name: a.name, type: (m && m[1]) || a.type || "", size: bin.length, aid: a.id });
      }
      if (files.length) await clReq("POST", "/close/self", { env: DC().encryptFor({ natt: { note: n.id, title: n.title, files }, ts: Date.now() }, DC().b64d(k.priv), k.dev, t) });
      files.forEach(f => { mark[f.aid] = Date.now(); }); sent += files.length;
      const all = notes(), x = all.find(y => y.id === n.id);
      if (x) { (x.att || []).forEach(a => { if (mark[a.id]) a.pc = mark[a.id]; }); fileSave("notes.json", JSON.stringify(all)); }
    }
    if (sent) plog("info", `📎 вложения заметок — на свои компьютеры: ${sent}`);
    if (todo.length > 3) noteAttSoon(60000);
    return sent;
  } finally { nattBusy = false; }
}
const money = () => { try { return JSON.parse(fileGet("money.json") || "[]"); } catch (e) { return []; } };
const saveMoney = (m) => { fileSave("money.json", JSON.stringify(m)); syncSoon(); };
function periodStart(p) { const d = new Date(); d.setHours(0, 0, 0, 0);
  if (p === "week") d.setDate(d.getDate() - (d.getDay() + 6) % 7); else if (p === "month") d.setDate(1); else if (p === "year") { d.setMonth(0, 1); }
  return isoLocal(d).slice(0, 10); }
function moneyReport(p) {
  const from = periodStart(p), items = money().filter(x => x.date >= from), by = {};
  items.forEach(x => { const c = by[x.currency] = by[x.currency] || { inc: 0, exp: 0, cats: {} }; if (x.kind === "income") c.inc += x.amount; else { c.exp += x.amount; c.cats[x.category] = (c.cats[x.category] || 0) + x.amount; } });
  const name = { today: "сегодня", week: "за неделю", month: "за месяц", year: "за год" }[p] || "";
  const parts = Object.entries(by).map(([cur, c]) => `${cur}: доходы ${+c.inc.toFixed(2)}, расходы ${+c.exp.toFixed(2)}, остаток ${+(c.inc - c.exp).toFixed(2)}` +
    (Object.keys(c.cats).length ? "; по категориям: " + Object.entries(c.cats).sort((a, b) => b[1] - a[1]).map(([k, v]) => `${k} ${+v.toFixed(2)}`).join(", ") : ""));
  return { text: parts.length ? `Деньги ${name}. ` + parts.join(". ") : `Записей ${name} нет.`, by, items };
}

/* ---------- умный дом Яндекса (тот же дом, что у Алисы) ----------
   API api.iot.yandex.net с ключом OAuth (права iot:view, iot:control) из S.home.token. Простые команды («включи свет
   в спальне») — без модели (homeQuick), остальное — инструментом smart_home. */
const IOT = "https://api.iot.yandex.net/v1.0";
let homeInfo = null, homeT = 0;                    // список устройств и комнат — кэш на 2 минуты
async function homeReq(method, path, body) {
  const r = await http(method, IOT + path, { headers: { Authorization: "Bearer " + S.home.token, "Content-Type": "application/json" }, body, timeout: 12000 });
  if (r.status === 401) throw new Error("ключ умного дома больше не действует — подключите заново");
  if (r.status === 403) throw new Error("у ключа нет прав iot:view и iot:control");
  const d = JSON.parse(r.body || "{}"); if (d.status && d.status !== "ok") throw new Error(d.message || "умный дом ответил ошибкой"); return d;
}
async function homeGet(force) {
  if (!force && homeInfo && Date.now() - homeT < 120000) return homeInfo;
  const d = await homeReq("GET", "/user/info"), rooms = {};
  (d.rooms || []).forEach(r => rooms[r.id] = r.name);
  homeInfo = { rooms: d.rooms || [], scenarios: d.scenarios || [], devices: (d.devices || []).map(x => Object.assign(x, { room_name: rooms[x.room] || "" })) }; homeT = Date.now();
  return homeInfo;
}
const HTYPES = { "свет": "devices.types.light", "ламп": "devices.types.light", "люстр": "devices.types.light", "торшер": "devices.types.light", "светильник": "devices.types.light",
  "ночник": "devices.types.light", "подсветк": "devices.types.light", "розетк": "devices.types.socket", "кондиционер": "devices.types.thermostat.ac", "обогреват": "devices.types.thermostat",
  "чайник": "devices.types.cooking.kettle", "пылесос": "devices.types.vacuum_cleaner", "телевизор": "devices.types.media_device.tv", "штор": "devices.types.openable.curtain",
  "увлажнител": "devices.types.humidifier", "вентилятор": "devices.types.fan" };
const HSKIP = new Set(["в", "во", "на", "мне", "пожалуйста", "у", "с", "и", "весь", "все", "всё", "везде", "всех", "сделай", "поставь"]);
const HGEN = new Set(["свет", "света", "устройства", "лампы", "лампочки"]);
const hw = (s) => String(s || "").toLowerCase().replace(/ё/g, "е").match(/[a-zа-я0-9]+/g) || [];
function hsim(a, b) { if (a === b) return true; if (a.length < 4 || b.length < 4) return false; let n = 0; while (n < Math.min(a.length, b.length) && a[n] === b[n]) n++; return n >= 4 && n >= Math.min(a.length, b.length) - 2; }
/* Устройства по словам: сначала по названию (в названной комнате, если она есть), потом по типу («свет», «розетка»),
   потом «весь …» — всё в комнате. hsim — то же слово в другом падеже. -> [] — не нашли (быстрая команда уступит модели). */
function homeMatch(target, info) {
  const all = hw(target), words = all.filter(w => !HSKIP.has(w)), allw = all.some(w => /^(весь|все|всё|везде|всех)$/.test(w));
  const rooms = info.rooms.filter(r => hw(r.name).some(a => words.some(b => hsim(a, b)))), rid = new Set(rooms.map(r => r.id));
  const rw = new Set(words.filter(b => rooms.some(r => hw(r.name).some(a => hsim(a, b))))), rest = words.filter(w => !rw.has(w));
  const inRoom = (d) => !rid.size || rid.has(d.room);
  const sc = info.devices.map(d => [hw(d.name).reduce((s, a) => s + rest.filter(b => !HGEN.has(b) && hsim(a, b)).length, 0), d]).filter(([s, d]) => s && inRoom(d));
  if (sc.length) { const top = Math.max(...sc.map(x => x[0])); return sc.filter(x => x[0] === top).map(x => x[1]); }
  const k = Object.keys(HTYPES).find(k => rest.some(w => w.startsWith(k)));
  if (k) return info.devices.filter(d => String(d.type).startsWith(HTYPES[k]) && inRoom(d));
  if (allw && rid.size) return info.devices.filter(d => rid.has(d.room));
  return [];
}
async function homeAct(devs, op, value) {
  const cap = (d, t, inst) => (d.capabilities || []).find(c => c.type === t && (!inst || ((c.parameters || {}).instance === inst) || ((c.state || {}).instance === inst)));
  const acts = [];
  devs.forEach(d => {
    const a = [], ON = "devices.capabilities.on_off", RG = "devices.capabilities.range";
    if (op === "on" || op === "off") { if (cap(d, ON)) a.push({ type: ON, state: { instance: "on", value: op === "on" } }); }
    else if (["brightness", "brighter", "dimmer"].includes(op)) { const c = cap(d, RG, "brightness"); if (c) { const cur = (c.state || {}).value || 50;
      a.push({ type: RG, state: { instance: "brightness", value: Math.max(1, Math.min(100, Math.round(op === "brightness" ? value : cur + (op === "brighter" ? 25 : -25)))) } }); if (cap(d, ON)) a.push({ type: ON, state: { instance: "on", value: true } }); } }
    else if (op === "temperature") { if (cap(d, RG, "temperature")) { a.push({ type: RG, state: { instance: "temperature", value: Math.round(value) } }); if (cap(d, ON)) a.push({ type: ON, state: { instance: "on", value: true } }); } }
    if (a.length) acts.push({ id: d.id, actions: a });
  });
  if (!acts.length) throw new Error("эти устройства так не умеют");
  await homeReq("POST", "/devices/actions", { devices: acts }); homeT = 0; return acts.length;
}
function homeParse(t) {
  let m;
  if ((m = t.match(/^(?:запусти|включи|активируй) сценари[йя] (.+)$/))) return { op: "scenario", target: m[1] };
  if ((m = t.match(/^(?:сделай )?(.+?) (?:на|в) (\d+|[а-я ]+?) ?(?:%|процент[а-яё]*)$/)) && wordsNum(m[2]) != null && !/громк|звук/.test(m[1])) return { op: "brightness", target: m[1], value: wordsNum(m[2]) };
  if ((m = t.match(/^(?:поставь )?(.*(?:кондиционер|обогреват|термостат)[а-яё]*.*?) (?:на )?(\d+|[а-я ]+?)(?: градус[а-яё]*)?$/)) && wordsNum(m[2]) >= 10 && wordsNum(m[2]) <= 35) return { op: "temperature", target: m[1], value: wordsNum(m[2]) };
  if ((m = t.match(/^(?:сделай )?(.*?) ?(ярче|поярче|темнее|потемнее|приглуши) ?(.*)$/)) && /свет|ламп|люстр|торшер/.test(t)) return { op: /ярче/.test(m[2]) ? "brighter" : "dimmer", target: (m[1] + " " + m[3]).trim() || "свет" };
  if ((m = t.match(/^(?:включи|зажги|открой|подними) (.+)$/))) return { op: "on", target: m[1] };
  if ((m = t.match(/^(?:выключи|отключи|погаси|потуши|закрой|опусти) (.+)$/))) return { op: "off", target: m[1] };
  return null;
}
async function homeQuick(t) {
  const c = homeParse(t); if (!c) return null;
  let info; try { info = await homeGet(); } catch (e) { return null; }
  try {
    if (c.op === "scenario") { const s = info.scenarios.find(s => hw(s.name).some(a => hw(c.target).some(b => hsim(a, b)))); if (!s) return null;
      await homeReq("POST", `/scenarios/${s.id}/actions`, {}); return { say: `Запустил сценарий «${s.name}».` }; }
    const devs = homeMatch(c.target, info); if (!devs.length) return null;
    await homeAct(devs, c.op, c.value);
    const what = devs.length === 1 ? devs[0].name : devs.every(d => String(d.type).startsWith("devices.types.light")) ? "свет" : `${devs.length} устройства`;
    const verb = { on: "Включил", off: "Выключил", brighter: "Сделал ярче", dimmer: "Приглушил" }[c.op];
    return { say: c.op === "brightness" ? `${what[0].toUpperCase() + what.slice(1)} — ${c.value}%.` : c.op === "temperature" ? `${what} — ${c.value}°.` : `${verb}: ${what}.` };
  } catch (e) { return { say: "Умный дом: " + e.message }; }
}
async function homeTool(a) {
  const info = await homeGet();
  if (a.action === "list") return info.devices.map(d => `${d.name}${d.room_name ? " (" + d.room_name + ")" : ""}`).join("; ") + (info.scenarios.length ? ". Сценарии: " + info.scenarios.map(s => s.name).join(", ") : "");
  if (a.action === "scenario") { const s = info.scenarios.find(s => hw(s.name).some(x => hw(a.target).some(y => hsim(x, y)))); if (!s) return "Нет такого сценария."; await homeReq("POST", `/scenarios/${s.id}/actions`, {}); return `Запущен «${s.name}».`; }
  const devs = homeMatch(a.target || "", info); if (!devs.length) return "Не нашёл такого устройства. Есть: " + info.devices.map(d => d.name).join(", ");
  const n = await homeAct(devs, a.action, a.value); return `Готово: ${devs.map(d => d.name).join(", ")} (${n}).`;
}

/* ---------- листы снизу (.sheet): открыть, закрыть, смахнуть вниз; за ними — содержимое каждого листа ---------- */
function openSheet(id) { closeSheets(true); $(id).classList.add("on"); $("#dim").classList.add("on"); }
function closeSheets(keepDim) {
  $$(".sheet.on").forEach(s => s.classList.remove("on")); if (!keepDim) $("#dim").classList.remove("on");
  if ($(".snd.play") && D.alarmSoundTry) { D.alarmSoundTry(""); $$(".snd.play").forEach(x => x.classList.remove("play")); }   // проба звука — смолкает с листом
}
$("#dim").onclick = () => closeSheets();
let touchY = null;
document.addEventListener("touchstart", e => { const s = e.target.closest(".sheet"); touchY = s && s.scrollTop <= 0 ? e.touches[0].clientY : null; }, { passive: true });
document.addEventListener("touchend", e => { if (touchY != null && e.changedTouches[0].clientY - touchY > 90) closeSheets(); touchY = null; }, { passive: true });

/* персонаж */
let pEnts = [];
$("#who").onclick = () => {
  pEnts.forEach(e => e.dead = true); pEnts = [];
  $("#plist").innerHTML = PERSONAS.map(p => `<div class="pirow"><button class="pi${p.id === S.persona ? " on" : ""}" data-id="${p.id}"><canvas></canvas><span><b>${esc(p.name)}</b><small>${esc(p.role || "")}${p.tagline ? " · " + esc(p.tagline) : ""}</small></span></button>`
    + (p.custom ? `<button class="ib soft pedit" data-e="${esc(p.id)}" title="Изменить" aria-label="Изменить: ${esc(p.name)}"><svg viewBox="0 0 24 24"><path d="M4 20h4L19 9l-4-4L4 16z"/><path d="m13.5 6.5 4 4"/></svg></button>` : "") + `</div>`).join("")
    + (myPersonas().length < MY_MAX ? `<button class="btn w pnew" id="p-new">+ Свой персонаж</button>` : "");
  $$("#plist .pedit").forEach(b => b.onclick = () => personaEditor(b.dataset.e));
  if ($("#p-new")) $("#p-new").onclick = () => personaEditor("");
  $$("#plist .pi").forEach(b => {
    const p = PERSONAS.find(x => x.id === b.dataset.id);
    const e = new DewiarEntity($("canvas", b), { style: p.avatar && p.style !== "aura" ? "photo" : p.style, color: p.color, image: p.avatar || null, plate: true, ring: false });
    e.set({ state: "idle" }); pEnts.push(e);
    b.onclick = () => { S.persona = p.id; saveS(); applyPersona(); closeSheets(); showYou(""); showBot(`Теперь отвечает ${p.name}.`); say(`Привет! Это ${p.name}.`); };
  });
  renderKbPanel();
  openSheet("#sh-persona");
};

/* разговор */
$("#b-hist").onclick = () => {
  const h = history.slice(-40);
  $("#hlist").innerHTML = h.length ? h.map(m => `<div class="msg ${m.role === "user" ? "u" : "a"}">${m.role === "user" ? `<div>${esc(m.content)}</div>`
      : `<div class="ans">${mdAnswer(m.content)}${m.img && window.DewiarRich ? DewiarRich.gallery(m.img) : ""}</div>`}${m.role !== "user" && m.who ? `<small>${esc((PERSONAS.find(p => p.id === m.who) || {}).name || "")}</small>` : ""}</div>`).join("")
    : `<div class="empty">Разговор пуст. Нажмите микрофон и спросите что-нибудь.</div>`;
  if (window.DewiarRich) DewiarRich.diagrams($("#hlist"));
  wirePics($("#hlist"));
  openSheet("#sh-hist"); setTimeout(() => $("#sh-hist").scrollTop = 1e6, 50);
};
$("#h-clear").onclick = () => { history = []; saveH(); convReset(); $("#b-hist").onclick(); toast("Начинаем заново"); };

/* мой день */
let dayTab = "rem";
$$("#day-tabs button").forEach(b => b.onclick = () => { dayTab = b.dataset.t; $$("#day-tabs button").forEach(x => x.classList.toggle("on", x === b)); renderDay(); });
$("#b-day").onclick = () => { renderDay(); openSheet("#sh-day"); };
/* Голосом / текстом: в дороге, на встрече, в транспорте ответ удобнее читать. Микрофон работает как прежде —
   выключается только голос ответа; выбор помнится. */
function voiceBtn() {
  const b = $("#b-voice"), off = !!S.textMode;
  b.classList.toggle("off", off); b.setAttribute("aria-pressed", String(off));
  b.title = off ? "Отвечать голосом" : "Отвечать текстом, без голоса";
}
$("#b-voice").onclick = () => {
  S.textMode = !S.textMode; saveS(); voiceBtn();
  if (S.textMode) { stopVoice(); if (state === "speaking" && !busy) finishTurn(); }
  toast(S.textMode ? "Отвечаю текстом — голос выключен" : "Отвечаю голосом", 1800);
};
voiceBtn();
const X_SVG = '<svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6 6 18"/></svg>';
/* шапка «Дела»: сколько сделано сегодня, серия и значки (полученные — ярко, следующий в каждой группе — бледно, с прогрессом) */
function doneHead(s) {
  const chips = [];
  for (const g of ["day", "streak", "total"]) {
    const all = ACHIEVE.filter(a => a.g === g), got = all.filter(a => achVal(a, s) >= a.n), next = all.find(a => achVal(a, s) < a.n);
    got.forEach(a => chips.push(`<button class="ach on" data-tip="${esc(a.icon + " " + a.name + " — " + a.what + " · получено")}">${a.icon}<span>${esc(a.name)}</span></button>`));
    if (next) chips.push(`<button class="ach" data-tip="${esc(next.icon + " " + next.name + " — " + next.what + " · сейчас " + achVal(next, s) + " из " + next.n)}">${next.icon}<span>${Math.min(achVal(next, s), next.n)}/${next.n}</span></button>`);
  }
  return `<div class="donehd"><div class="dnum"><b>${s.today}</b><small>${s.today ? delaRu(s.today) + " сегодня" : "дел сегодня"}</small></div><div class="dside">`
    + `<span class="dstreak">${s.streak >= 2 ? `🔥 ${s.streak} ${dnRu(s.streak)} подряд` : s.today ? "Первый день серии" : s.total ? "Отметьте дело — серия продолжится" : "Сделали дело — отметьте его"}`
    + `<button class="dwhy${doneWhy ? " on" : ""}" id="done-why" aria-label="Что это за награды" aria-expanded="${doneWhy}">?</button></span>`
    + `<div class="achs">${chips.join("")}</div></div></div>`
    + (doneWhy ? `<div class="donewhy" id="done-whybox"><b>Зачем это</b><p>Сделали дело — отметьте: скажите «я позвонила маме, отметь», нажмите ✓ у напоминания или впишите ниже. `
      + `Отмеченное попадает сюда, а за него — значки: за дела за день (3, 5, 7, 10), за дни подряд и за всё время. Яркие — уже ваши, бледные — следующие, `
      + `нажмите на значок — сколько осталось. Это просто чтобы видеть, сколько уже сделано, и радоваться: ничего не тратится, видите только вы.</p>`
      + `<button class="btn" id="done-whyok">Понятно</button></div>` : "")
    + `<form class="doneadd" id="done-add"><input placeholder="Что уже сделали?" maxlength="120" enterkeyhint="done" aria-label="Что сделали"><button class="ib" aria-label="Отметить сделанным">✓</button></form>`;
}
// «Мой день» — какой сегодня день: «Среда, 15 октября» (просьба 15.10: «почему он не пишет число и день недели?»)
function dayDate(d = new Date()) { const w = WD[d.getDay()]; return `${w[0].toUpperCase()}${w.slice(1)}, ${d.getDate()} ${MON[d.getMonth()]}`; }
function renderDay() {
  const box = $("#day-body"), dd = $("#day-date");
  if (dd) dd.textContent = dayDate();
  if (dayTab === "rem") {
    const l = JSON.parse(D.alarms() || "[]").sort((a, b) => a.at - b.at), ds = doneStats();
    const jobs = (mind().jobs || []).filter(j => !j.paused);       // дела по расписанию — их делает компьютер (утренняя сводка, итоги)
    box.innerHTML = doneHead(ds)
      + (ds.items.length ? `<div class="bugh">Сделано сегодня</div>` + ds.items.slice().reverse().map(x => { const d = new Date(x.at);
          return `<div class="it dn"><div class="ok">✓</div><div class="bd"><b>${esc(x.title)}</b><small>${pad(d.getHours())}:${pad(d.getMinutes())}${x.src === "pc" ? " · на компьютере" : x.src === "alarm" ? " · из напоминания" : ""}</small></div><button class="x" data-undo="${esc(x.id)}" title="Снять отметку" aria-label="Снять отметку">${X_SVG}</button></div>`; }).join("") : "")
      + (l.length ? `<div class="bugh">Напоминания</div>` + l.map(x => { const d = new Date(x.at), task = x.kind !== "alarm" && x.kind !== "timer";
          const nt = x.note ? notes().find(n => n.id === x.note) : null, img = nt && (nt.att || []).find(a => a.type === "image");
          return `<div class="it" data-edit="${esc(x.id)}"><div class="tm">${pad(d.getHours())}:${pad(d.getMinutes())}</div><div class="bd"><b>${esc(x.title)}</b><small>${x.kind === "alarm" ? "⏰ будильник" : x.kind === "timer" ? "⏱ таймер" : "🔔 напоминание"} · ${esc(whenText(d))}${x.repeat ? " · " + REP_RU[x.repeat] : ""}${x.note ? ` · <span class="ntc">📎${nt ? noteAttCount(nt) || "" : ""}</span>` : ""}</small></div>`
            + (img ? `<img class="nthumb rt" data-note="${esc(x.note)}" src="${noteAttGet(img.id)}" alt="">` : "")
            + (task ? `<button class="x ok" data-done="${esc(x.id)}" title="Сделано" aria-label="Сделано">✓</button>` : "") + `<button class="x" data-id="${esc(x.id)}" title="Удалить" aria-label="Удалить">${X_SVG}</button></div>`; }).join("")
      : jobs.length || ds.items.length ? "" : `<div class="empty">Напоминаний нет.<br>Скажите: «напомни завтра в 9 позвонить маме» или «будильник на 7».<br>Сделали дело — скажите «я позвонила маме, отметь» или впишите его выше.</div>`)
      + (jobs.length ? `<div class="bugh">По расписанию — делает компьютер</div>` + jobs.map(j => { const d = new Date(j.at);
          return `<div class="it job"><div class="tm">${pad(d.getHours())}:${pad(d.getMinutes())}</div><div class="bd"><b>${esc(String(j.text).split(":")[0].slice(0, 80))}</b><small>${esc(j.repeat || whenText(d))}</small></div></div>`; }).join("")
        + `<p class="hint" style="margin:6px 4px 0">Изменить или выключить — на компьютере: студия → «Напоминания».</p>` : "")
      + (D.exactAlarms() ? "" : `<div class="card"><b>Будильники могут опаздывать</b><p class="hint">Разрешите точное время: «Будильники и напоминания».</p><button class="btn p" onclick="Dewiar.openSettings('alarms')">Разрешить</button></div>`);
    $$("[data-id]", box).forEach(b => b.onclick = (e) => { e.stopPropagation(); D.alarmCancel(b.dataset.id); syncSoon(); renderDay(); });
    $$("[data-note]", box).forEach(b => b.onclick = (e) => { e.stopPropagation(); openNoteSoon(b.dataset.note); });
    $$("[data-edit]", box).forEach(r => r.onclick = (e) => { if (!e.target.closest("button, img")) remEdit(r.dataset.edit); });   // нажали — править руками
    $$("[data-done]", box).forEach(b => b.onclick = () => { const x = l.find(i => i.id === b.dataset.done); if (!x) return;
      if (!x.repeat) { D.alarmCancel(x.id); syncSoon(); } celebrate(Object.assign(doneAdd([{ title: x.title, rid: x.id }], "tap"), { closed: [] })); renderDay(); });
    $$("[data-undo]", box).forEach(b => b.onclick = () => { const x = doneUndo(b.dataset.undo); renderDay(); if (x) toast("Отметка снята: " + x.title, 2000); });
    $$(".ach", box).forEach(b => b.onclick = () => toast(b.dataset.tip, 2600));
    const why = $("#done-why", box), seen = () => { if (!S.doneWhySeen) { S.doneWhySeen = true; saveS(); } };
    if (why) why.onclick = () => { doneWhy = !doneWhy; seen(); renderDay(); };
    if ($("#done-whyok", box)) { seen(); $("#done-whyok", box).onclick = () => { doneWhy = false; renderDay(); }; }
    const f = $("#done-add", box);
    f.onsubmit = (e) => { e.preventDefault(); const t = $("input", f).value.trim(); if (!t) { $("input", f).focus(); return; } markDone([t], "tap"); renderDay(); };
  } else if (dayTab === "notes") {
    const folds = noteFolders(); if (ntFolder && !folds.includes(ntFolder)) ntFolder = "";
    const n = notes().filter(x => !ntFolder || String(x.folder || "").trim() === ntFolder).sort((a, b) => (+b.time || 0) - (+a.time || 0));   // новые сверху — и с компьютера тоже
    const chips = folds.length ? `<div class="ntfolds" role="tablist" aria-label="Папки">${["", ...folds].map(f => `<button role="tab" data-f="${esc(f)}" class="${f === ntFolder ? "on" : ""}" aria-selected="${f === ntFolder}">${f ? esc(f) : "Все"}</button>`).join("")}</div>` : "";
    box.innerHTML = `<button class="btn p ntnew" id="nt-new">Новая заметка</button>` + chips + (n.length ? n.map(x => {
      const img = (x.att || []).find(a => a.type === "image"), more = (x.att || []).length;
      // папка заметки с компьютера (№216: вкладки блокнота у виджета приходят заметками — «Главное» без пометки не узнать)
      const fold = x.folder && !ntFolder ? `<span class="ntf">${esc(x.folder.split("/").pop())}</span>` : "";
      return `<div class="it note" data-id="${esc(x.id)}">${img ? `<img class="nthumb" src="${noteAttGet(img.id)}" alt="">` : ""}<div class="bd"><b>${esc(x.title)}${more ? `<span class="ntc">📎${more}</span>` : ""}${fold}</b><small>${esc(noteShown(x.text).slice(0, 220))}</small></div></div>`; }).join("")
      : `<div class="empty">Заметок нет.<br>Скажите: «запиши в заметки: купить хлеб и молоко» — или нажмите «Новая заметка».</div>`);
    $("#nt-new").onclick = () => openNote("");
    $$(".ntfolds button", box).forEach(b => b.onclick = () => { ntFolder = b.dataset.f; renderDay(); });
    $$(".it.note", box).forEach(el => el.onclick = () => openNote(el.dataset.id));
  } else if (dayTab === "made") {
    const l = apps().slice().reverse();
    box.innerHTML = tasksHtml() + (l.length ? `<div class="bugh">Сделано на телефоне</div>` + l.map(x => `<div class="it"><div class="bd" data-open="${esc(x.id)}"><b>${esc(x.title)}</b><small>${esc(whenText(new Date(x.ts)))} · ${Math.max(1, Math.round(x.size / 1024))} КБ · нажмите, чтобы открыть</small></div><button class="x" data-id="${esc(x.id)}">${X_SVG}</button></div>`).join("")
      : Object.keys(mind().tasks).length ? "" : `<div class="empty">Пока ничего не сделано.<br>Скажите: «сделай презентацию о погоде на завтра» или «сделай игру в крестики-нолики».</div>`);
    wireTasks(box, renderDay);
    $$("[data-open]", box).forEach(b => b.onclick = () => openApp(b.dataset.open));
    $$(".x", box).forEach(b => b.onclick = () => { fileSave("app-" + b.dataset.id + ".html", ""); fileSave("apps.json", JSON.stringify(apps().filter(x => x.id !== b.dataset.id))); renderDay(); });
  } else {
    const r = moneyReport("month"), c = r.by[CUR] || Object.values(r.by)[0] || { inc: 0, exp: 0 }, cur = r.by[CUR] ? CUR : (Object.keys(r.by)[0] || CUR);
    const items = money().slice(-30).reverse();
    box.innerHTML = `<div class="sum"><div><b style="color:var(--good)">${+c.inc.toFixed(2)}</b><small>доходы</small></div><div><b style="color:#FF8FA8">${+c.exp.toFixed(2)}</b><small>расходы</small></div><div><b>${+(c.inc - c.exp).toFixed(2)}</b><small>остаток, ${cur}</small></div></div>`
      + (items.length ? items.map(x => `<div class="it"><div class="tm" style="color:${x.kind === "income" ? "var(--good)" : "#FF8FA8"};font-size:15px">${x.kind === "income" ? "+" : "−"}${x.amount}</div><div class="bd"><b>${esc(x.note || x.category)}</b><small>${esc(x.category)} · ${esc(x.date)} · ${esc(x.currency)}</small></div><button class="x" data-id="${esc(x.id)}">${X_SVG}</button></div>`).join("")
      : `<div class="empty">Записей нет.<br>Скажите: «купил кофе за восемь пятьдесят».</div>`);
    $$(".x", box).forEach(b => b.onclick = () => { saveMoney(money().filter(x => x.id !== b.dataset.id)); renderDay(); });
  }
}

/* ---------- дела: «сделано» и достижения (отзыв 13.10: «геймификация — выполнил 3 дела, значки и достижения, в конце дня
   "ты сегодня сделал 5–7 дел"»; отчёт №14: «Отметь как исполненное» — нечем было отметить).
   Журнал done.json: {id, title, at (мс), src: voice|tap|alarm|pc, rid — напоминание, если закрыто им}. Он же уходит в
   синхронизацию видом «done» (core/done.py на компьютере — тот же формат и те же достижения: меняешь здесь — меняй и там).
   Достижения не хранятся — считаются по журналу (doneStats): так они одинаковы на телефоне и компьютере. Дневные рубежи
   (3, 5, 7, 10 дел за день) поздравляют каждый день; значки (ACHIEVE) — один раз, когда получены впервые. */
const DONE_F = "done.json", DONE_MAX = 1500, DAY_MILES = [3, 5, 7, 10];
const ACHIEVE = [
  { id: "d3", g: "day", n: 3, icon: "🥉", name: "Тройка", what: "3 дела за день" },
  { id: "d5", g: "day", n: 5, icon: "🥈", name: "Пятёрка", what: "5 дел за день" },
  { id: "d10", g: "day", n: 10, icon: "🥇", name: "Десятка", what: "10 дел за день" },
  { id: "s3", g: "streak", n: 3, icon: "🔥", name: "Три дня подряд", what: "дела три дня подряд" },
  { id: "s7", g: "streak", n: 7, icon: "⭐", name: "Неделя", what: "дела семь дней подряд" },
  { id: "s30", g: "streak", n: 30, icon: "🏆", name: "Месяц", what: "дела тридцать дней подряд" },
  { id: "t10", g: "total", n: 10, icon: "✨", name: "Первые десять", what: "10 дел всего" },
  { id: "t50", g: "total", n: 50, icon: "💪", name: "Полсотни", what: "50 дел всего" },
  { id: "t100", g: "total", n: 100, icon: "💯", name: "Сотня", what: "100 дел всего" },
  { id: "t500", g: "total", n: 500, icon: "👑", name: "Пятьсот", what: "500 дел всего" }];
const achVal = (a, s) => a.g === "day" ? s.bestDay : a.g === "streak" ? s.bestStreak : s.total;
function doneList() { try { const l = JSON.parse(fileGet(DONE_F) || "[]"); return Array.isArray(l) ? l : []; } catch (e) { return []; } }
function saveDone(l) {
  l = l.filter(x => x && x.id && x.title && +x.at).sort((a, b) => a.at - b.at).slice(-DONE_MAX);
  fileSave(DONE_F, JSON.stringify(l)); return l;
}
const dayKey = (t) => { const d = new Date(t); return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()); };
const delaRu = (n) => n % 10 === 1 && n % 100 !== 11 ? "дело" : [2, 3, 4].includes(n % 10) && ![12, 13, 14].includes(n % 100) ? "дела" : "дел";
const dnRu = (n) => n % 10 === 1 && n % 100 !== 11 ? "день" : [2, 3, 4].includes(n % 10) && ![12, 13, 14].includes(n % 100) ? "дня" : "дней";
function doneStats(l = doneList(), now = Date.now()) {
  const by = {}; l.forEach(x => { const k = dayKey(x.at); by[k] = (by[k] || 0) + 1; });
  const today = dayKey(now);
  let streak = 0, d = new Date(now); d.setHours(12, 0, 0, 0);
  if (!by[today]) d = new Date(d.getTime() - 864e5);                 // сегодня ещё пусто — серия идёт со вчера
  while (by[dayKey(d)]) { streak++; d = new Date(d.getTime() - 864e5); d.setHours(12, 0, 0, 0); }
  let best = 0, run = 0, prev = null;
  for (const k of Object.keys(by).sort()) { const t = new Date(k + "T12:00").getTime(); run = prev !== null && Math.round((t - prev) / 864e5) === 1 ? run + 1 : 1; prev = t; best = Math.max(best, run); }
  const s = { today: by[today] || 0, items: l.filter(x => dayKey(x.at) === today), streak, bestStreak: best, bestDay: Math.max(0, ...Object.values(by)), total: l.length, byDay: by };
  s.earned = ACHIEVE.filter(a => achVal(a, s) >= a.n);
  return s;
}
/* Записать сделанное: list — [{title, rid}] или строки. -> {items, stats, fresh (новые значки), mile (дневной рубеж или 0)} */
function doneAdd(list, src = "tap", at = Date.now()) {
  const l = doneList(), before = doneStats(l, at), items = [];
  for (const it of [].concat(list)) {
    const o = typeof it === "string" ? { title: it } : it, title = String(o.title || "").replace(/\s+/g, " ").trim().slice(0, 120);
    if (!title) continue;
    const t = title[0].toUpperCase() + title.slice(1);
    items.push({ id: "d" + at.toString(36) + Math.random().toString(36).slice(2, 7), title: t, at: +o.at || at + items.length, src, rid: o.rid || "" });
  }
  const after = doneStats(saveDone(l.concat(items)), at);
  const fresh = ACHIEVE.filter(a => achVal(a, after) >= a.n && achVal(a, before) < a.n);
  const mile = DAY_MILES.filter(m => before.today < m && after.today >= m).pop() || 0;
  if (items.length) syncSoon();
  return { items, stats: after, fresh, mile };
}
function doneUndo(id) { const l = doneList(), x = l.find(i => i.id === id); if (!x) return null; saveDone(l.filter(i => i.id !== id)); syncSoon(); return x; }
// напоминание на сегодня, которое и есть это дело: «я позвонила Игорю» ↔ «позвонить Игорю» (основы слов по 4 буквы)
const stems = (t) => String(t || "").toLowerCase().replace(/ё/g, "е").split(/[^a-zа-я0-9]+/).filter(w => w.length > 2 && !/^(это|как|для|что|все|уже|мне|меня|надо|нужно|сделал[аи]?|сделать)$/.test(w)).map(w => w.slice(0, 4));
// в экзамене напоминания — его песочница (exam.js), не настоящие
const examOn = () => typeof EXAM !== "undefined" && !!EXAM;
function remDrop(id) { if (examOn()) { EXAM.alarms = EXAM.alarms.filter(x => x.id !== id); return; } D.alarmCancel(id); syncSoon(); }
// совпадение — и хотя бы одно не глаголом: «позвонил маме» ≠ «позвонить в банк» (общий только «позв»), как done._hit_ok
const VERB_END = /(?:ть|ться|ти|[аеиоуыяю]л|[аеиоуыяю]л[аи]|лся|лась|лись)$/;
function hitOk(title, said) {
  const words = String(title || "").toLowerCase().replace(/ё/g, "е").split(/[^a-zа-я0-9]+/).filter(w => w.length > 2 && !/^(это|как|для|что|все|уже|мне|меня|надо|нужно|сделал[аи]?|сделать)$/.test(w));
  if (!words.length) return 0;
  const hits = words.filter(w => said.includes(w.slice(0, 4))); if (!hits.length) return 0;
  const nouns = words.filter(w => !VERB_END.test(w));
  if (nouns.length && !hits.some(w => nouns.includes(w))) return 0;
  return hits.length / words.length;
}
// ahead — на сегодня не нашлось: и разовое на ближайшие 36 часов («я позвонил в банк» в 22:40, а план — на завтра в 13)
function remMatch(title, now = Date.now(), ahead = true) {
  const w = stems(title); if (!w.length) return null;
  const ends = [Math.max(new Date(now).setHours(23, 59, 59, 0), now + 3 * 3600e3)];   // поздно вечером — и сразу после полуночи
  if (ahead) ends.push(now + 36 * 3600e3);
  for (const end of ends) {
    let best = null, bs = 0;
    for (const x of alarmsNow()) {
      if (x.kind === "timer" || x.kind === "alarm" || (!x.repeat && x.at > end)) continue;
      const sc = hitOk(x.title, w);
      if (sc >= 0.5 && sc > bs) { best = x; bs = sc; }
    }
    if (best) return best;
  }
  return null;
}
/* Отметить дела (инструмент и кнопки): подходящее разовое напоминание на сегодня закрывается, повторяющееся остаётся. */
function markDone(titles, src) {
  const closed = [], list = [];
  for (const t of titles) {
    const m = remMatch(t);
    if (m) { if (!m.repeat) { remDrop(m.id); closed.push(m.title); } list.push({ title: m.title, rid: m.id }); }
    else list.push({ title: t });
  }
  const r = doneAdd(list, src); r.closed = closed;
  celebrate(r);
  return r;
}
function doneSay(r) {
  const s = r.stats, ach = r.fresh.map(a => `${a.icon} «${a.name}» — ${a.what}`).join("; ");
  return `Отмечено сделанным: ${r.items.map(x => "«" + x.title + "»").join(", ")}.` + (r.closed.length ? ` Напоминание закрыто: ${r.closed.join(", ")}.` : "")
    + ` Сегодня сделано ${s.today} ${delaRu(s.today)}` + (s.streak >= 2 ? `, ${s.streak} ${dnRu(s.streak)} подряд` : "") + ", всего " + s.total + "."
    + (ach ? ` Новое достижение: ${ach}.` : r.mile ? ` Рубеж дня: ${r.mile} ${delaRu(r.mile)}!` : "")
    + " Похвали коротко и тепло, одной фразой" + (ach ? ", назови достижение" : "") + "; не перечисляй дела заново.";
}
/* План дня и «сделано» — без модели, как core/dayplan.py (отзыв 17.10: «Запланируй на сегодня: в 13 позвонить в банк,
   в 16 тренировка, в 19 купить подарок маме» — «записала», а в «Делах» пусто: модель писала в календарь). Меняешь здесь —
   меняй и там. На каждое дело — напоминание; дело без времени — на 20:00; прошедшее время сегодня — на завтра. */
const PLAN_RX = /^\s*(?:[а-я]+,\s*)?(?:(?:а|и|ну|пожалуйста|слушай)\s+)*(?:(?:за|с)планируй(?:те)?(?:\s+(?:мне|нам))?(?:\s+(?:дела|задачи))?|(?:составь|запиши|сделай|создай)(?:те)?\s+(?:мне\s+)?план(?:\s+(?:дел|дня))?|(?:добавь|внеси|поставь|запиши)(?:те)?\s+(?:мне\s+)?в\s+(?:мой\s+)?план(?:\s+(?:дел|дня|на\s+день))?|(?:мой\s+|мои\s+)?(?:план|планы|дела|задачи)\s+(?=на\s+(?:сегодня|завтра|послезавтра|день)))([\s\S]*)$/;
const PLAN_NOT = /календар|встреч|созвон с|совещан|мероприят|отпуск|поездк|путешеств|бюджет|ремонт|свадьб|меню(?![а-я])/;
const PLAN_REMIND = /^\s*(?:[а-я]+,\s*)?(?:напомни(?:те)?|поставь(?:те)?\s+(?:мне\s+)?напоминани[яе])\s+([\s\S]*)$/;
const PLAN_TIME = /(?:^|[^а-я])(?:в|к|на)\s+\d{1,2}(?:[:.]\d{2})?(?:\s*(?:час[а-я]*|ч(?![а-я])))?(?:\s+(?:утра|дня|вечера|ночи))?|(?:^|[^а-я])(?:утром|днем|вечером)(?![а-я])/;
const PLAN_EVENING = 20;
function restoreCase(what, raw) {
  const o = {}; for (const w of String(raw || "").match(/[\p{L}\d-]+/gu) || []) { const k = w.toLowerCase().replace(/ё/g, "е"); if (!(k in o)) o[k] = w; }
  return String(what).split(" ").map(w => /^\d+$/.test(w) ? w : (o[w] || w)).join(" ");
}
const capFirst = (t) => t ? t[0].toUpperCase() + t.slice(1) : t;
// распознавание речи запятых не ставит: «в 13 позвонить в банк в 16 тренировка» — делим по времени, как dayplan._by_time
const PLAN_T = /(?:^|[^а-я])((?:в|к)\s+\d{1,2}(?:[:.]\d{2})?(?:\s+(?:часов|часа|час))?(?:\s+(?:утра|дня|вечера|ночи))?)(?![\d:])/g;
function planByTime(p) {
  const marks = [...p.matchAll(PLAN_T)].map(m => ({ start: m.index + m[0].length - m[1].length, end: m.index + m[0].length }));
  if (marks.length < 2) return [p];
  const cuts = marks[0].start === 0 ? marks.slice(1).map(m => m.start) : marks.slice(0, -1).map(m => m.end);
  const out = []; let last = 0;
  for (const c of cuts) { out.push(p.slice(last, c)); last = c; }
  out.push(p.slice(last));
  return out.map(x => x.replace(/^[\s.:—,-]+|[\s.:—,-]+$/g, "")).filter(Boolean);
}
function planParse(text, now = new Date()) {
  const raw = String(text || "").replace(/\s+/g, " ").trim();
  if (!raw || /\?\s*$/.test(raw) || raw.includes("\n\nВложения:")) return null;
  const t = raw.toLowerCase().replace(/ё/g, "е");
  let m = t.match(PLAN_RX), remind = false;
  if (!m) { m = t.match(PLAN_REMIND); remind = true; if (!m) return null; }
  let rest = m[1];
  if (PLAN_NOT.test(rest)) return null;
  let day = "";
  const dm = rest.slice(0, 40).match(/(?:^|[^а-я])(?:на\s+)?(сегодня|завтра|послезавтра|день)(?![а-я])/);
  if (dm) { day = dm[1] === "день" ? "" : dm[1]; rest = rest.slice(0, dm.index) + " " + rest.slice(dm.index + dm[0].length); }
  rest = rest.replace(/^\s*(?:мне|нам|такие|следующие|вот|дела|задачи)\s+/, " ").replace(/^[\s:—,.-]+|[\s:—,.-]+$/g, "");
  const segs = rest.split(/\s*(?:[,;\n]|\.\s+|\s—\s)\s*|\s+(?:и|а\s+потом|потом|затем|а)\s+(?=(?:в|к)\s+\d)/).map(x => (x || "").replace(/^[\s.:—-]+|[\s.:—-]+$/g, "")).filter(Boolean).flatMap(planByTime);
  if (!segs.length || segs.length > 12) return null;
  const timed = segs.filter(x => PLAN_TIME.test(x));
  if (remind && timed.length < 2) return null;              // одно «напомни…» — обычное напоминание (модель)
  if (!remind && !timed.length && segs.length < 2) return null;   // «запланируй отпуск» — не план дня
  const today = new Date(now); today.setHours(0, 0, 0, 0);
  const base = new Date(today.getTime() + ({ "завтра": 1, "послезавтра": 2 }[day] || 0) * 864e5);
  const items = [];
  for (let x of segs) {
    if (PLAN_TIME.test(x)) {
      x = x.replace(/(^|[^а-я])(в|к)\s+([1-7])(?![\d:.])(?!\s*(?:час[а-я]*\s+)?(?:утра|ночи))/, (_, a, b, h) => `${a}${b} ${+h + 12}`);   // «в 3 забрать детей» — 15:00
      const w = parseWhen((day && day !== "сегодня" ? day + " " : "") + x, now);
      if (!w || w.rel || w.repeat) return null;
      const what = remindWhat(w.rest).replace(/^(?:и|а|еще|также)\s+/, "");
      if (!what) return null;
      items.push({ text: capFirst(restoreCase(what, raw)), at: w.at, moved: w.at >= new Date(base.getTime() + 864e5) && !(day === "завтра" || day === "послезавтра") });
    } else {
      const what = x.replace(/^(?:и|а|еще|также)\s+/, "").trim();
      if (what.length < 3 || what.split(" ").length > 10) return null;
      let at = new Date(base); at.setHours(PLAN_EVENING, 0, 0, 0); let moved = false;
      if (at <= now) { at = new Date(at.getTime() + 864e5); moved = true; }
      items.push({ text: capFirst(restoreCase(what, raw)), at, moved, untimed: true });
    }
  }
  return { items, day: base, today };
}
function planSay(p, now = new Date()) {
  const loose = p.items.filter(x => x.untimed), items = p.items.filter(x => !x.untimed).sort((a, b) => a.at - b.at);
  const low = (x) => /^.[А-ЯЁA-Z]/.test(x.text) ? x.text : x.text[0].toLowerCase() + x.text.slice(1);
  const hm = (d) => pad(d.getHours()) + ":" + pad(d.getMinutes()), dk = (d) => Math.round((new Date(d).setHours(0, 0, 0, 0) - new Date(now).setHours(0, 0, 0, 0)) / 864e5);
  const dname = (d) => ({ 0: "сегодня", 1: "завтра", 2: "послезавтра" })[dk(d)] || `${d.getDate()} ${MON[d.getMonth()]}`;
  const all = items.concat(loose), days = [...new Set(all.map(x => dk(x.at)))];
  let out;
  if (days.length === 1) {
    const lst = items.map(x => `${hm(x.at)} — ${low(x)}`).concat(loose.length ? [loose.map(low).join(", ")] : []).join("; ");
    let head = all.length > 1 ? `Записал план на ${dname(all[0].at)}` : `Записал в план на ${dname(all[0].at)}`;
    if (all.some(x => x.moved) && p.day.getTime() === p.today.getTime()) head = `Сегодня это время уже прошло — записал план на ${dname(all[0].at)}`;
    out = `${head}: ${lst}.`;
  } else {
    const by = {}; all.slice().sort((a, b) => a.at - b.at).forEach(x => (by[dk(x.at)] = by[dk(x.at)] || []).push(x));
    out = "Записал план: " + Object.keys(by).sort().map(k => capFirst(dname(by[k][0].at)) + " — " + by[k].map(x => (x.untimed ? "" : hm(x.at) + " ") + low(x)).join("; ")).join(". ") + ".";
    if (all.some(x => x.moved)) out += " Что уже прошло сегодня — перенёс на завтра.";
  }
  if (loose.length) out += ` ${loose.length > 1 ? "Дела" : "Дело"} без времени — напомню в ${PLAN_EVENING}:00.`;
  return out + " Сделаете — скажите, и я отмечу.";
}
function planQuick(text) {                          // и в экзамене: экзамен идёт тем же путём, что человек (addAlarm — в песочницу)
  const p = planParse(text); if (!p) return null;
  const made = p.items.map(x => addAlarm(x.text, x.at, "reminder", ""));
  plog("info", "🗓 план дня (без модели): " + made.map(x => `${whenText(new Date(x.at))} ${x.title}`).join("; "));
  setTimeout(() => openDone(false), 400);           // сразу видно: «Мой день» → «Дела»
  return { say: planSay(p) };
}
const DONE_PAST = "[а-я]+(?:л|ла|ли|лся|лась|лись)";
const DONE_EXPLICIT = [
  /^(?:отметь(?:те)?|отмечай|поставь(?:те)?\s+(?:галочку|отметку))(?:\s+(?:мне|пожалуйста))?(?:\s*,?\s*что\s+)?(?:\s+(?:как|что)?\s*(?:сделанн[а-я]*|выполненн[а-я]*|исполненн[а-я]*|готов[а-я]*|сделано|выполнено))?\s*[:,—-]?\s*(?:что\s+)?(.+)$/,
  /^(?:готово|сделано|выполнено|галочка)\s*[,:—-]?\s+(.+)$/,
  /^(.+?)\s*[—:-]?\s+(?:готово|сделано|выполнено)$/];
const DONE_IMPLICIT = new RegExp("^(?:(?:ну|так|всё|все|итак|кстати)\\s*,?\\s+)?(?:я\\s+)?(?:уже\\s+|только\\s+что\\s+|сегодня\\s+)?(" + DONE_PAST + "(?:\\s.+)?)$");
const DONE_NOT = /(?:^|[^а-я])(?:не|вчера|завтра|хочу|хотел[аи]?|надо|нужно|буду|будем|собираюсь|планирую|может|если|забыл[аи]?|напомни|когда|зачем|почему|сколько|отмени|сними|убери)(?![а-я])/;
function doneParse(text) {
  const raw = String(text || "").replace(/\s+/g, " ").trim();
  let t = raw.toLowerCase().replace(/ё/g, "е").replace(/[\s.!]+$/, "");
  t = t.replace(/^([а-я]+),\s*(?=\S)/, (m0, w) => findPersona(w, true) ? "" : m0);
  if (!t || /\?$/.test(t) || t.length > 160) return null;
  if (/^(?:отметь|отмечай|поставь)/.test(t) && /(?:^|[^а-я])(?:не|ошибк|сним)|календар|карт[еуа]|заметк|будильник|напоминани/.test(t)) return null;
  let explicit = false, x = null;
  for (const rx of DONE_EXPLICIT) { const m = t.match(rx); if (m && m[1].trim()) { explicit = true; x = m[1]; break; } }
  if (x === null) {
    if (DONE_NOT.test(t) || t.split(" ").length > 12) return null;
    const m = t.match(DONE_IMPLICIT); if (!m) return null; x = m[1];
  } else if (/(?:^|[^а-я])(?:не|завтра|буду|надо|нужно)(?![а-я])/.test(x)) return null;
  const parts = x.split(new RegExp("\\s*[,;]\\s*|\\s+(?:и|а\\s+еще|а\\s+также|потом|еще)\\s+(?=(?:я\\s+)?" + DONE_PAST + "(?![а-я]))"));
  const items = parts.map(p => (p || "").replace(/^[\s.:—-]+|[\s.:—-]+$/g, "").replace(/^(?:(?:я|и|уже|еще|также)\s+)+/, "").replace(/\s+(?:уже|сегодня|только что|готово|сделано)$/, "").trim())
    .filter(p => p.length >= 3).map(p => capFirst(restoreCase(p, raw)));
  return items.length ? { items, explicit } : null;
}
function doneSpeak(r) {
  const n = r.stats.today, a = r.fresh[r.fresh.length - 1];
  let out = `Отметил ${r.items.map(x => "«" + x.title + "»").join(", ")}.`;
  out += a ? ` Сегодня уже ${n} ${delaRu(n)} — новое достижение «${a.name}»!` : r.mile ? ` Уже ${n} ${delaRu(n)} за сегодня — так держать!` : ` Сегодня ${n === 1 ? "это первое дело" : "уже " + n + " " + delaRu(n)}.`;
  if (r.stats.streak >= 2 && (a || r.mile || n === 1)) out += ` Серия — ${r.stats.streak} ${dnRu(r.stats.streak)} подряд.`;
  return out;
}
function doneQuick(text) {
  const d = doneParse(text); if (!d) return null;
  if (!d.explicit && !d.items.every(t => remMatch(t))) return null;   // «я позвонил в банк» — только если это дело из плана
  const r = markDone(d.items, "voice");
  plog("info", "✓ сделано (без модели): " + r.items.map(x => x.title).join("; "));
  if ($("#sh-day.on") && dayTab === "rem") renderDay();
  return { say: doneSpeak(r) };
}
/* «Освободи место», «почисти телефон», «сколько места занимает Dewiar» (18.10) — без модели и без подсказки ей: чистить
   чужие приложения Android никому не даёт (с Android 6), поэтому честно: свой кэш чистим сами, а для остального
   открываем системное «Хранилище» — там Android показывает, что занимает место, и сам предлагает очистку.
   «Очисти память» сюда не входит — это про память помощницы. */
const FREE_RX = /^(?:(?:освободи|освободить|почисти|почистить|очисти|очистить|разгреби)\s+(?:мне\s+)?(?:место|телефон|хранилище|мусор|кэш|кеш)(?:\s+(?:на\s+)?телефон[еа]?)?|(?:мало|не\s+хватает|кончается|закончилось|заканчивается)\s+(?:места|память)(?:\s+(?:на\s+)?телефон[еа]?)?|сколько\s+(?:места\s+)?(?:занимает|весит)\s+(?:dewiar|девиар|приложение|ты)(?:\s+места)?)$/;
const mbRu = (b) => b >= 1e9 ? (b / 1e9).toFixed(1).replace(".", ",") + " ГБ" : Math.max(1, Math.round(b / 1e6)) + " МБ";
function freeSpaceQuick(t) {
  if (!FREE_RX.test(t) || !D.appSize || examOn()) return null;       // в экзамене настоящий кэш не трогаем
  let z = {}; try { z = JSON.parse(D.appSize() || "{}"); } catch (e) { }
  const asks = /^сколько/.test(t), total = (+z.cache || 0) + (+z.data || 0);
  if (asks) return { say: `Dewiar занимает около ${mbRu(total)}: ${mbRu(+z.data || 0)} — ваши заметки, настройки и журнал, ${mbRu(+z.cache || 0)} — временные файлы. Скажите «освободи место» — почищу временные.` };
  const freed = D.clearOwnCache ? +D.clearOwnCache() || 0 : 0;
  setTimeout(() => D.openStorage && D.openStorage(), 2500);
  plog("info", `🧹 освободи место: свой кэш −${mbRu(freed)}, открываю «Хранилище»`);
  return { say: `Почистил свои временные файлы — ${freed >= 1e6 ? "освободилось " + mbRu(freed) : "их почти не было"}. Открываю «Хранилище»: там Android покажет, что занимает место, и предложит очистку. Чужие приложения я чистить не могу — так устроен Android.` };
}
/* «Что я умею» (18.10: «у нас есть функции, про которые никто не знает») — data/tricks.json (tricks.js при сборке), те же
   фразы, что в студии. Нажатие — сказать фразу; фраза с «…» (дописать своё) — в поле ввода. Только то, что есть на телефоне. */
function openTricks() { renderTricks(); setTimeout(() => openSheet("#sh-tricks"), 30); }   // после клика: иначе тот же клик закрыл бы лист
function renderTricks() {
  const T = window.DEWIAR_TRICKS || { groups: [] }, box = $("#tricks-body");
  box.innerHTML = `<p class="hint" style="margin:0 2px 12px">Скажите или нажмите — так работает и голосом. Где «…» — допишите своё.</p>` + T.groups.map(g => {
    const it = g.items.filter(x => (x.where || []).includes("phone") && !x.key);
    return it.length ? `<div class="trg"><h3>${g.icon || ""} ${esc(g.name)}</h3><div class="card trl">${it.map(x =>
      `<button class="trk" ${x.fill ? `data-fill="1" data-say="${esc(x.say)}"` : `data-say="${esc(x.say)}"`}><b>«${esc(x.say)}»</b><small>${esc(x.what)}</small></button>`).join("")}</div></div>` : "";
  }).join("");
  $$(".trk", box).forEach(b => b.onclick = () => {
    const say = b.dataset.say;
    closeSheets();
    if (b.dataset.fill) { $("#typebox").classList.add("on"); $("#typed").value = say.replace(/…$/, " ").replace(/:\s*…?$/, ": "); setTimeout(() => $("#typed").focus(), 250); return; }
    setTimeout(() => ask(say), 200);
  });
}
/* Праздник: короткий тост на каждое дело; рубеж дня и новый значок — конфетти, вибрация и карточка. */
function celebrate(r) {
  if (!r.items.length) return;
  const s = r.stats, big = r.fresh.length || r.mile;
  toast(`✓ ${r.items.length === 1 ? r.items[0].title : r.items.length + " " + delaRu(r.items.length)} — сегодня ${s.today}`, 2600);
  try { D.vibrate(big ? 60 : 25); } catch (e) { }
  if (!big) return;
  confetti();
  const a = r.fresh[r.fresh.length - 1];
  // отзыв 16.10: «нужен крестик, и чтобы по нажатию было понятно, что это за награды» — карточка ведёт в «Мой день» → «Дела»
  // (там все значки и объяснение), ✕ — убрать; пока объяснение не открывали, внизу подсказка «Что это за награды?»
  showCard(`<div class="achc" id="achc" role="button" tabindex="0" aria-label="Открыть дела и достижения">${a ? `<i>${a.icon}</i><div class="achb"><b>${esc(a.name)}</b><small>Новое достижение · ${esc(a.what)}</small>`
    : `<i>🎉</i><div class="achb"><b>${r.mile} ${delaRu(r.mile)} за сегодня</b><small>${s.streak >= 2 ? s.streak + " " + dnRu(s.streak) + " подряд · " : ""}так держать</small>`}`
    + `<em>${S.doneWhySeen ? "Все значки — в «Мой день»" : "Что это за награды? Нажмите"}</em></div><button class="achx" aria-label="Убрать">${X_SVG}</button></div>`);
  const c = $("#achc"); if (!c) return;
  c.onclick = (e) => { if (e.target.closest(".achx")) { e.stopPropagation(); showCard(""); return; } openDone(!S.doneWhySeen); };
  c.onkeydown = (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openDone(!S.doneWhySeen); } };
}
/* «Мой день» → «Дела»: сделанное, серия и все значки; why — сразу с объяснением, зачем это */
let doneWhy = false;
function openDone(why) {
  showCard(""); doneWhy = !!why;
  openSheet("#sh-day"); dayTab = "rem"; $$("#day-tabs button").forEach(x => x.classList.toggle("on", x.dataset.t === "rem")); renderDay();
}
function confetti() {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const box = document.createElement("div"); box.className = "confetti"; box.setAttribute("aria-hidden", "true");
  const col = ["#8B8CF7", "#4BE3A1", "#FFC978", "#FF8FA8", "#7FD4FF", "#fff"];
  for (let i = 0; i < 36; i++) {
    const p = document.createElement("i");
    p.style.cssText = `left:${(Math.random() * 100).toFixed(1)}%;background:${col[i % col.length]};animation-delay:${(Math.random() * .35).toFixed(2)}s;`
      + `--dx:${(Math.random() * 120 - 60).toFixed(0)}px;--r:${(Math.random() * 720 - 360).toFixed(0)}deg;width:${6 + (i % 3) * 2}px`;
    box.appendChild(p);
  }
  document.body.appendChild(box); setTimeout(() => box.remove(), 2200);
}
/* «Сделано ✓» в уведомлении напоминания (AlarmReceiver) — телефон кладёт в pref done_inbox, здесь забираем. */
function doneInbox() {
  let q = []; try { q = JSON.parse(prefGet("done_inbox") || "[]") || []; } catch (e) { }
  if (!q.length) return;
  let rest = []; try { rest = (JSON.parse(prefGet("done_inbox") || "[]") || []).filter(x => !q.some(y => y.id === x.id && y.at === x.at)); } catch (e) { }
  prefSet("done_inbox", JSON.stringify(rest));                       // уведомление могло добавить ещё одно, пока читали
  const r = doneAdd(q.map(x => ({ title: x.title, rid: x.id, at: +x.at || Date.now() })), "alarm");
  if (r.fresh.length || r.mile) celebrate(r);
  if ($("#sh-day.on") && dayTab === "rem") renderDay();
}
N.on("done_inbox", () => doneInbox());
function doneReport(days) {
  const d = Math.max(1, Math.min(60, +days || 1)), l = doneList(), s = doneStats(l), from = new Date(); from.setHours(0, 0, 0, 0); from.setDate(from.getDate() - d + 1);
  const it = l.filter(x => x.at >= from.getTime()), by = {};
  it.forEach(x => (by[dayKey(x.at)] = by[dayKey(x.at)] || []).push(x.title));
  const next = ["day", "streak", "total"].map(g => ACHIEVE.find(a => a.g === g && achVal(a, s) < a.n)).filter(Boolean);
  return (it.length ? (d === 1 ? `Сегодня сделано ${it.length} ${delaRu(it.length)}: ` + by[dayKey(Date.now())].join("; ")
      : `За ${d} ${dnRu(d)} сделано ${it.length} ${delaRu(it.length)}:\n` + Object.entries(by).map(([k, v]) => `${k.slice(8)}.${k.slice(5, 7)}: ${v.join("; ")}`).join("\n"))
    : (d === 1 ? "Сегодня пока ничего не отмечено." : `За ${d} ${dnRu(d)} ничего не отмечено.`))
    + `\nСерия: ${s.streak} ${dnRu(s.streak)} подряд (лучшая — ${s.bestStreak}). Всего: ${s.total}. Лучший день: ${s.bestDay}.`
    + `\nДостижения: ${s.earned.length ? s.earned.map(a => a.icon + " " + a.name).join(", ") : "пока нет"}.`
    + (next.length ? ` Следующие: ${next.map(a => `${a.icon} ${a.name} (${a.what}, сейчас ${achVal(a, s)})`).join("; ")}.` : "");
}
function donePrompt() {
  const s = doneStats();
  return "ДЕЛА И ДОСТИЖЕНИЯ. «Запланируй на сегодня…», «план на день», «мои дела на завтра» — это дела, не календарь: на каждое дело — свой set_reminder с его временем. Встреча, запись к мастеру, дело со временем («запиши встречу с Ирой на вторник в 12», «завтра в 13 у меня массаж», «в 8:10 встреча с Максимом») — тоже дело: set_reminder на это время, не заметка; «напомни за день / за час» — ещё один set_reminder на то время. В календарь — только если прямо сказано «в календарь». Поставил(а) или отметил(а) дело — подтверди одной фразой только его; остальные дела и планы вслух не перечисляй, пока не спросят: рядом могут быть чужие люди (19.10: «перед клиентами начал вслух перечислять то, что касается только меня»). Пользователь говорит, что сделал дело («я позвонила Игорю и сделала тренировку», «отметь как исполненное», «готово, купил хлеб») — "
    + "вызови mark_done (каждое дело — отдельной строкой, коротко: «Позвонить Игорю», «Тренировка»), подходящее напоминание закроется само; потом похвали коротко, одной фразой. "
    + "Отметил по ошибке — mark_done с undo. «Что я сегодня сделал», «мои достижения» — done_report. "
    + `Сейчас: сегодня сделано ${s.today} ${delaRu(s.today)}` + (s.items.length ? ` (${s.items.slice(-6).map(x => x.title).join("; ")})` : "")
    + (s.streak >= 2 ? `, серия ${s.streak} ${dnRu(s.streak)} подряд` : "") + `, всего ${s.total}.`;
}

/* ---------- календарь телефона (Cal.java: Android-календарь — в нём Google и другие аккаунты человека, без паролей) ----------
   Читать — свободно (разрешение спрашивается при первом вопросе). Записать — только после «да» человека: calendar_add без
   confirmed ничего не пишет, а говорит модели, о чём спросить, и предупреждает о встречах в то же время. Нет доступа или
   календаря для записи — открываем окно новой встречи в приложении «Календарь», сохраняет человек. Чужое не правим.
   В экзамене — песочница EXAM.calendar: настоящий календарь не трогаем. */
const CAL_R = "android.permission.READ_CALENDAR", CAL_W = "android.permission.WRITE_CALENDAR";
const WD_SHORT = ["вс", "пн", "вт", "ср", "чт", "пт", "сб"];
function calParse(x) {                                       // «2026-10-15» (весь день) или «2026-10-15T15:00» (местное)
  const m = /^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{1,2}):(\d{2}))?/.exec(String(x || "").trim());
  if (!m) return null;
  const d = new Date(+m[1], +m[2] - 1, +m[3], m[4] ? +m[4] : 0, m[5] ? +m[5] : 0);
  return isNaN(d) ? null : { ms: d.getTime(), allDay: !m[4] };
}
function calWhen(e) {
  const b = new Date(e.begin), en = new Date(e.end), day = `${WD_SHORT[b.getDay()]} ${b.getDate()} ${MON[b.getMonth()]}`;
  if (e.all_day) return day + ", весь день";
  const same = en.toDateString() === b.toDateString();
  return `${day}, ${pad(b.getHours())}:${pad(b.getMinutes())}–${same ? "" : `${en.getDate()} ${MON[en.getMonth()]} `}${pad(en.getHours())}:${pad(en.getMinutes())}`;
}
const calLine = (e) => `${calWhen(e)} — ${e.title || "без названия"}${e.location ? ` (${e.location})` : ""}`;
/* -> встречи за период или null — доступа к календарю не дали */
async function calEvents(from, to) {
  if (examOn()) return (EXAM.calendar || []).filter(e => e.end > from && e.begin < to).sort((a, b) => a.begin - b.begin);
  if (typeof D.calEvents !== "function") return [];
  let r = JSON.parse(D.calEvents(JSON.stringify({ from, to })) || "{}");
  if (r.need) { if (!(await needPerm(r.need))) return null; r = JSON.parse(D.calEvents(JSON.stringify({ from, to })) || "{}"); }
  if (r.error) throw new Error("календарь не прочитался: " + r.error);
  return r.events || [];
}
/* Планы на дни [from, to) не из календаря: запомненное «со слов пользователя» с датой «(на ДД.ММ.ГГГГ» (factQuick, remember)
   и напоминания. Экзамен 0.6.42: «запомни: в среду встреча» запомнено, а на «что у меня в среду?» модель посмотрела только
   календарь — «пусто». -> текст для модели или "". */
function dayPlans(from, to) {
  const facts = (S.memory || []).filter(f => { const m = /\(на (\d\d)\.(\d\d)\.(\d{4})/.exec(f); if (!m) return false;
    const t = new Date(+m[3], +m[2] - 1, +m[1]).getTime(); return t >= from && t < to; });
  let rem = []; try { rem = alarmsNow().filter(x => x.at >= from && x.at < to).sort((x, y) => x.at - y.at); } catch (e) { }
  if (!facts.length && !rem.length) return "";
  return (facts.length ? "\nЕщё на эти дни — из памяти (пользователь сам просил запомнить): " + facts.map(f => f.replace(/^Со слов пользователя:\s*/, "")).join("; ") : "")
    + (rem.length ? "\nНапоминания: " + rem.slice(0, 10).map(x => `${pad(new Date(x.at).getHours())}:${pad(new Date(x.at).getMinutes())} — ${x.title}`).join("; ") : "")
    + "\nНазови и это — это тоже планы пользователя.";
}
// «что у меня в среду?», «какие планы на завтра?», «есть ли дела в пятницу?» -> dayPlans на этот день или ""
function agendaPlans(text) {
  const t = String(text || "");
  if (!/(?:что|какие|есть ли|чем)[^.!?]{0,40}(?:у меня|у нас|план|дел[ао]?(?![а-яё])|встреч|занят)|(?:мои|мой)\s+(?:планы|день|дела)/i.test(t)) return "";
  let d = dayOf(t);
  if (!d && /(?:по\s+плану|какие\s+(?:у\s+(?:меня|нас)\s+)?(?:планы|дела)|что\s+у\s+(?:меня|нас)\s+(?:сегодня|на\s+сегодня)?\s*$)/i.test(t.replace(/[?!.]+$/, ""))) { d = new Date(); d.setHours(0, 0, 0, 0); }   // «что у нас по плану?» — сегодня
  if (!d) return "";
  return dayPlans(d.getTime(), d.getTime() + 864e5);
}
// «сегодня», «завтра», «послезавтра», «в/на среду» (ближайшая, сегодня — сегодня), «21 октября», «21.10» -> полночь дня или null
function dayOf(text) {
  const t = String(text || "").toLowerCase().replace(/ё/g, "е"), d = new Date(); d.setHours(0, 0, 0, 0);
  if (/(?<![а-я])послезавтра/.test(t)) { d.setDate(d.getDate() + 2); return d; }
  if (/(?<![а-я])завтра/.test(t)) { d.setDate(d.getDate() + 1); return d; }
  if (/(?<![а-я])сегодня/.test(t)) return d;
  const wd = /(?:в|во|на)\s+(воскресенье|понедельник|вторник|среду|четверг|пятницу|субботу)/.exec(t);
  if (wd) { const n = ["воскресенье", "понедельник", "вторник", "среду", "четверг", "пятницу", "субботу"].indexOf(wd[1]); d.setDate(d.getDate() + (n - d.getDay() + 7) % 7); return d; }
  const dm = /(\d{1,2})\s+(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)/.exec(t) || /(\d{1,2})\.(\d{1,2})(?!\d)/.exec(t);
  if (dm) { const m = isNaN(+dm[2]) ? MON.indexOf(dm[2]) : +dm[2] - 1, x = new Date(d.getFullYear(), m, +dm[1]); if (x < d) x.setFullYear(x.getFullYear() + 1); return x; }
  return null;
}
async function calendarList(a) {
  const st = a.from ? calParse(a.from) : null, d0 = st ? new Date(st.ms) : new Date();
  const from = new Date(d0.getFullYear(), d0.getMonth(), d0.getDate()).getTime();
  const days = Math.max(1, Math.min(31, Math.round(+a.days || 1))), to = from + days * 864e5;
  const plans = a.query ? "" : dayPlans(from, to);
  let ev = await calEvents(from, to);
  if (ev === null && plans) return "Календарь телефона недоступен (нет разрешения)." + plans;
  if (ev === null) return "Доступ к календарю не разрешён. Скажи пользователю одной фразой: чтобы я видела календарь, разрешите доступ — спрошу снова при следующем вопросе. Не выдумывай встреч.";
  const q = String(a.query || "").toLowerCase().trim();
  if (q) { const w = stems(q); ev = ev.filter(e => { const t = (e.title + " " + e.location).toLowerCase(); return t.includes(q) || (w.length && stems(t).some(x => w.includes(x))); }); }
  const span = days === 1 ? `${WD[new Date(from).getDay()].replace(/а$/, "у")}, ${new Date(from).getDate()} ${MON[new Date(from).getMonth()]}` : `${days} дн. с ${new Date(from).getDate()} ${MON[new Date(from).getMonth()]}`;
  if (!ev.length) return `В календаре на ${span}${q ? ` по «${a.query}»` : ""} ничего нет.` + plans;
  return `Календарь на ${span}${q ? ` по «${a.query}»` : ""} (${ev.length}):\n` + ev.slice(0, 40).map(calLine).join("\n")
    + (ev.length > 40 ? `\n…и ещё ${ev.length - 40}.` : "") + plans + "\nРасскажи главное коротко, своими словами; не добавляй встреч, которых здесь нет.";
}
async function calendarAdd(a) {
  const st = calParse(a.start);
  if (!st) return "Ошибка: нужно начало — дата и время ГГГГ-ММ-ДДTЧЧ:ММ (или только дата — на весь день). Посчитай от текущей даты.";
  const title = String(a.title || "").replace(/\s+/g, " ").trim().slice(0, 200) || "Встреча";
  const mins = Math.max(5, Math.min(24 * 60, Math.round(+a.minutes || 60)));
  const e = { title, begin: st.ms, end: st.allDay ? st.ms + 864e5 : st.ms + mins * 6e4, all_day: st.allDay, location: String(a.location || "").trim().slice(0, 200) };
  if (!st.allDay && e.begin < Date.now() - 5 * 6e4) return `Ошибка: ${calWhen(e)} уже прошло — уточни у пользователя дату.`;
  const what = calLine(e);
  if (a.confirmed !== true) {
    let busy = [];
    try { busy = ((await calEvents(e.begin, e.end)) || []).filter(x => !x.all_day); } catch (x) { }
    return `Ещё не записано. Спроси пользователя одной фразой: «Записать в календарь: ${what}?»`
      + (busy.length ? ` Предупреди, что в это время уже есть: ${busy.slice(0, 3).map(x => x.title).join("; ")}.` : "")
      + " Только после его «да» вызови calendar_add снова с теми же данными и confirmed: true; без «да» не говори, что записала.";
  }
  if (examOn()) { (EXAM.calendar = EXAM.calendar || []).push(Object.assign({ id: "ec" + Date.now(), made: Date.now() }, e)); return `Записано в календарь: ${what}.`; }
  const insert = () => typeof D.calOpenInsert === "function" && D.calOpenInsert(JSON.stringify(e));
  let r = JSON.parse(D.calAdd(JSON.stringify(e)) || "{}");
  if (r.need) {
    if (await needPerm(r.need)) r = JSON.parse(D.calAdd(JSON.stringify(e)) || "{}");
    else return insert() ? `Доступа к календарю нет — открыла окно новой встречи (${what}). Скажи: проверьте и нажмите «Сохранить».` : "Ошибка: доступа к календарю нет.";
  }
  if (r.error === "no_calendar") return insert() ? `В телефоне нет календаря для записи — открыла окно новой встречи в «Календаре» (${what}). Скажи: проверьте и нажмите «Сохранить».` : "Ошибка: в телефоне нет календаря для записи — нужно приложение «Календарь» или аккаунт Google.";
  if (r.error) return "Ошибка: " + r.error;
  return `Записано в календарь «${r.calendar}»: ${what}${st.allDay ? "" : ". Календарь напомнит за 15 минут"}.`;
}

/* ---------- маршрут на карте (отзыв 13.10: «Лира берёт геоточку, открывает карту и предлагает короткий пешеходный маршрут
   дворами»). Куда — адрес, место, координаты или ссылка на карту (Яндекс, Google, geo:, короткая — по переадресации).
   Адрес → координаты через OpenStreetMap (Nominatim); маршрут строит приложение карт от того места, где человек сейчас —
   пешком оно и ведёт кратчайшим путём, дворами. Яндекс Карты, если стоят (иначе Google). Как core/route.py. ---------- */
const ROUTE_MODES = { walk: ["pd", "walking"], transit: ["mt", "transit"], car: ["auto", "driving"], bike: ["bc", "bicycling"] };
const ROUTE_RU = { walk: "пешком", transit: "на транспорте", car: "на машине", bike: "на велосипеде" };
const geoOk = (a, b) => a >= -90 && a <= 90 && b >= -180 && b <= 180 && !(a === 0 && b === 0);
function parseCoords(text) {
  let t = String(text || ""); try { t = decodeURIComponent(t); } catch (e) { }
  const NR = "(-?\\d{1,3}\\.\\d{3,})", AN = "(-?\\d{1,3}(?:\\.\\d+)?)";   // голые числа — с 3+ знаками; в ссылке — любые
  if (/yandex/i.test(t)) {                            // сначала сама точка (pt, «что здесь»), потом маршрут, потом центр карты
    for (const p of ["(?:[?&]pt=|whatshere\\[point\\]=)", "rtext=[^&]*~", "[?&]ll="]) {
      const m = t.match(new RegExp(p + AN + "\\s*,\\s*" + AN));
      if (m) { const a = +m[1], b = +m[2]; if (p.startsWith("rtext")) return geoOk(a, b) ? [a, b] : null; return geoOk(b, a) ? [b, a] : null; }
    }
  }
  for (const p of ["geo:" + AN + ",\\s*" + AN, "@" + AN + "," + AN, "[?&](?:q|query|destination|daddr|ll)=" + AN + "\\s*,\\s*" + AN, "(?<![\\d.])" + NR + "\\s*[,; ]\\s*" + NR + "(?![\\d.])"]) {
    const m = t.match(new RegExp(p)); if (m && geoOk(+m[1], +m[2])) return [+m[1], +m[2]];
  }
  return null;
}
const isShortMap = (t) => /https?:\/\/(?:yandex\.\w+\/maps\/-\/|maps\.app\.goo\.gl\/|goo\.gl\/maps\/|go\.2gis\.com\/)\S+/.test(String(t || ""));
async function geocode(q) {
  q = String(q || "").trim(); if (!q) return null;
  try {
    const r = await http("GET", "https://nominatim.openstreetmap.org/search?" + new URLSearchParams({ q, format: "jsonv2", limit: "1", "accept-language": "ru" }),
      { headers: { "User-Agent": "Dewiar/1 (https://dewiar.pro)" }, timeout: 12000 });
    const x = (JSON.parse(r.body || "[]") || [])[0]; if (!x) return null;
    const a = +x.lat, b = +x.lon; return geoOk(a, b) ? [a, b, String(x.display_name || q)] : null;
  } catch (e) { return null; }
}
function routeUrl(app, dest, origin, mode, scheme) {
  const [yrt, gm] = ROUTE_MODES[mode] || ROUTE_MODES.walk, pt = (p) => Array.isArray(p) ? `${(+p[0]).toFixed(6)},${(+p[1]).toFixed(6)}` : String(p);
  if (app === "yandex" && Array.isArray(dest) && (!origin || Array.isArray(origin)))
    return (scheme ? "yandexmaps://maps.yandex.ru/" : "https://yandex.ru/maps/") + `?rtext=${origin ? pt(origin) : ""}~${pt(dest)}&rtt=${yrt}`;
  if (app === "yandex") return (scheme ? "yandexmaps://maps.yandex.ru/" : "https://yandex.ru/maps/") + "?" + new URLSearchParams({ text: pt(dest) });
  const q = { api: "1", destination: pt(dest), travelmode: gm }; if (origin) q.origin = pt(origin);
  return "https://www.google.com/maps/dir/?" + new URLSearchParams(q);
}
async function routeTool(a) {
  const to = String(a.to || "").trim(); if (!to) return "Ошибка: не понял, куда — спроси адрес или место.";
  const mode = ROUTE_MODES[a.mode] ? a.mode : "walk";
  let apps = []; try { apps = JSON.parse(D.apps() || "[]"); } catch (e) { }
  const hasY = apps.some(n => /яндекс.?карты|yandex.?maps/i.test(n));
  const app = a.app === "google" || a.app === "yandex" ? a.app : (hasY || !apps.some(n => /^(карты|maps|google maps)$/i.test(n)) ? "yandex" : "google");
  let src = to;
  if (isShortMap(to)) { try { const r = await http("GET", to.match(/https?:\/\/\S+/)[0], { timeout: 12000 }); src = (r.url || "") + " " + (r.body || "").slice(0, 200000); } catch (e) { } }
  let c = parseCoords(src), name = c ? "" : to;
  if (!c && !/^https?:\/\//.test(to)) { const g = await geocode(to); if (g) { c = [g[0], g[1]]; name = g[2]; } }
  let o = null;
  if (a.from) { o = parseCoords(a.from); if (!o) { const g = await geocode(a.from); o = g ? [g[0], g[1]] : a.from; } }
  const dest = c || to, url = routeUrl(app, dest, o, mode, false);
  const opened = (app === "yandex" && hasY && D.openUrl(routeUrl(app, dest, o, mode, true))) || D.openUrl(url);
  const where = name ? name.split(",").slice(0, 3).join(",") : c ? `${c[0].toFixed(5)}, ${c[1].toFixed(5)}` : "";
  const appRu = app === "yandex" ? "Яндекс Картах" : "Google Картах";
  if (!opened) return "Ошибка: карта не открылась — скажи об этом и предложи открыть ссылку: " + url;
  if (!c && app === "yandex") return `Открыла поиск «${where}» в ${appRu}: точное место не нашлось — пусть выберет его на карте и нажмёт «Маршрут». Скажи это одной-двумя фразами.`;
  return `Открыла маршрут ${ROUTE_RU[mode]} до «${where}» в ${appRu}, от того места, где пользователь сейчас.`
    + (mode === "walk" ? " Пешком карта ведёт кратчайшим путём — и дворами, и тропинками; время в пути видно на карте." : "")
    + " Скажи коротко, одной-двумя фразами, что маршрут открыт; не выдумывай улицы и время.";
}

// «готово» о результате фоновой задачи, которой ещё нет; «сообщу, когда будет готово» — честно (как EARLY_DONE_RX в engine_brain.py)
function earlyDone(t) {
  t = String(t || "").toLowerCase();
  return /(?<![а-яё])(готово|готова|готов|сделал[аи]?|сделано|закончил[аи]?|вот\s+(?:она|он|ваш[аи]?|тво[яй]|презентаци|отч[её]т|документ))(?![а-яё])/.test(t)
    && !/сообщ|пришлю|когда\s+(?:будет|закончу|всё)|как\s+только|в\s+фоне|займ[её]т|начал|взял|приступ|уже\s+работа|работаю|передал/.test(t);
}
/* ---------- «Что нового» (отзыв 13.10: «что было в обновлении — непонятно, пришлось догадываться»). После обновления — лист
   с новым и тем, как попробовать (фраза в «» — нажмите, и Лира её услышит). Текст — data/whatsnew.json (тот же у компьютера,
   сборка кладёт его в whatsnew.js). Уже виденное — pref news_seen; новая установка листа не показывает. ---------- */
const verCmp = (a, b) => { const x = String(a || "").split(".").map(Number), y = String(b || "").split(".").map(Number);
  for (let i = 0; i < 3; i++) if ((x[i] || 0) !== (y[i] || 0)) return (x[i] || 0) - (y[i] || 0); return 0; };
function newsList(from, to) {
  return (window.DEWIAR_NEWS || []).filter(r => (!from || verCmp(r.phone, from) > 0) && verCmp(r.phone, to) <= 0)
    .map(r => Object.assign({}, r, { items: (r.items || []).filter(i => (i.where || ["phone"]).includes("phone")) })).filter(r => r.items.length).slice(0, 3);
}
function newsShow(list) {
  if (!list.length) return false;
  let v = list[0].phone;                                   // версия — та, что стоит (в её выпуске новое могло быть только у компьютера)
  try { const cur = JSON.parse(D.info() || "{}").version; if (cur && verCmp(cur, v) > 0 && /^\d+\.\d+\.\d+$/.test(cur)) v = cur; } catch (e) { }
  $("#news-body").innerHTML = `<p class="nwsub">Dewiar ${esc(v)} — вот что появилось</p>` + list.map(r => r.items.map(i => {
    const ph = /^«(.+)»$/.exec(String(i.try || "").trim());
    return `<div class="nwi"><i aria-hidden="true">${esc(i.icon || "✨")}</i><div><b>${esc(i.title)}</b><p>${esc(i.text)}</p>`
      + (ph ? `<button class="nwtry" data-say="${esc(ph[1])}">Попробовать: «${esc(ph[1])}»</button>` : i.try ? `<small>${esc(i.try)}</small>` : "") + `</div></div>`; }).join("")).join("")
    + `<button class="btn p w" id="nw-ok">Понятно</button>`;
  $("#nw-ok").onclick = () => closeSheets();
  $$(".nwtry", $("#news-body")).forEach(b => b.onclick = () => { closeSheets(); if (state !== "idle") interrupt(true); ask(b.dataset.say); });
  openSheet("#sh-news");
  return true;
}
function newsCheck() {
  let v = ""; try { v = JSON.parse(D.info() || "{}").version || ""; } catch (e) { }
  if (!v) return false;
  const seen = prefGet("news_seen");
  if (seen === v) return false;
  prefSet("news_seen", v);
  if (!seen && !(S.llm.base_url || history.length)) return false;     // только что установили — новостей нет, есть знакомство
  if (seen && verCmp(v, seen) < 0) return false;
  if ($(".sheet.on") || busy) return false;
  plog("info", `✨ что нового: ${seen || "?"} → ${v}`);
  return newsShow(newsList(seen, v));
}

/* ---------- сделанное: мини-программы и страницы, которые ассистент сделал прямо на телефоне (make_app) ----------
   Программа сразу открывается на экране — иначе после «Готово» непонятно, где её взять; хранится в «Мой день» →
   «Сделанное» (последние 40: файлы app-<id>.html и список apps.json), её можно сохранить в «Загрузки».
   Показ — в отдельном окне без моста Dewiar (openHtmlView → HtmlView.java): код, написанный моделью, не достаёт до ключей и телефона. */
const apps = () => { try { return JSON.parse(fileGet("apps.json") || "[]") || []; } catch (e) { return []; } };
function saveApp(title, html) {
  const id = "a" + Date.now().toString(36);
  fileSave("app-" + id + ".html", html);
  const l = apps().concat([{ id, title: String(title).slice(0, 60), ts: Date.now(), size: html.length }]);
  l.slice(0, -40).forEach(x => fileSave("app-" + x.id + ".html", ""));
  fileSave("apps.json", JSON.stringify(l.slice(-40)));
  return l[l.length - 1];
}
const appHtml = (id) => fileGet("app-" + id + ".html") || "";
function appCard(ap) {
  return `<div class="appc"><b>${esc(ap.title)}</b><small>сделано сейчас · откроется на весь экран</small><div class="row2"><button class="btn p" onclick="openApp('${ap.id}')">Открыть</button><button class="btn" onclick="saveAppDl('${ap.id}')">В «Загрузки»</button></div></div>`;
}
function openApp(id) {
  const ap = apps().find(x => x.id === id), html = appHtml(id);
  if (!ap || !html) { toast("Не нашёл — возможно, удалена"); return; }
  openHtmlView(ap.title, html, () => saveAppDl(id));
}
function saveAppDl(id) {
  const ap = apps().find(x => x.id === id), html = appHtml(id);
  if (!ap || !html) return;
  const name = (ap.title.replace(/[\\/:*?"<>|]/g, " ").trim() || "Dewiar") + ".html";
  const where = D.saveDownload ? D.saveDownload(name, "text/html", html) : "";
  toast(where ? "Сохранено: " + where + " — откроется в браузере" : "Не получилось сохранить", 3500);
}

/* ---------- файлы результатов задач: компьютер или облако кладут их в облако (?p=/files), здесь — открыть и сохранить.
   HTML (страница, презентация, программа) открывается тут же, в том же безопасном окне, что и «Сделанное»; остальное
   сохраняется в «Загрузки/Dewiar». ---------- */
/* Что открывается прямо в приложении: страницы — как есть, текст и код — моноширинным текстом, картинки — картинкой;
   остальное (pptx, docx, zip…) — «В «Загрузки»» и откроется в своей программе. */
const VIEWABLE = /\.(?:html?|md|txt|log|csv|tsv|json|ya?ml|srt|vtt|py|js|ts|css|sh|java|kt|c|cpp|h|go|rs|php|sql|xml|ini|toml|png|jpe?g|gif|webp|svg)$/i;
function fileViewHtml(name, b64, type) {
  const page = (body) => `<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><body style="margin:0;background:#101018;color:#e8e8f0;font:14px/1.5 system-ui">${body}</body>`;
  if (/\.html?$/i.test(name)) return b64text(b64);
  if (/\.(?:png|jpe?g|gif|webp|svg)$/i.test(name)) {
    const mime = type || (/\.svg$/i.test(name) ? "image/svg+xml" : /\.png$/i.test(name) ? "image/png" : /\.gif$/i.test(name) ? "image/gif" : /\.webp$/i.test(name) ? "image/webp" : "image/jpeg");
    return page(`<img src="data:${mime};base64,${b64}" style="display:block;max-width:100%;margin:0 auto">`);
  }
  return page(`<pre style="margin:0;padding:14px;white-space:pre-wrap;word-break:break-word;font:13px/1.45 ui-monospace,monospace">${esc(b64text(b64))}</pre>`);
}
function taskFiles(t) {
  const f = t.files || [];
  if (!f.length) return (t.outputs || []).length ? `<small class="hint">Файлы на компьютере: ${t.outputs.map(esc).join(", ")}</small>` : "";
  return `<div class="tfiles">${f.map(x => `<div class="tf"><span>${esc(x.title || x.name)}<small>${esc(x.name)} · ${fsize(x.size)}</small></span>`
    + (VIEWABLE.test(x.name) ? `<button class="btn p" data-fo="${esc(x.id)}" data-fn="${esc(x.name)}">Открыть</button>` : "")
    + `<button class="btn" data-fs="${esc(x.id)}" data-fn="${esc(x.name)}">В «Загрузки»</button></div>`).join("")}</div>`;
}
const fsize = (n) => n > 1048576 ? (n / 1048576).toFixed(1) + " МБ" : Math.max(1, Math.round((n || 0) / 1024)) + " КБ";
function wireFiles(root) {
  $$("[data-fo]", root).forEach(b => b.onclick = (e) => { e.stopPropagation(); taskFileOpen(b.dataset.fo, b.dataset.fn); });
  $$("[data-fs]", root).forEach(b => b.onclick = (e) => { e.stopPropagation(); taskFileSave(b.dataset.fs, b.dataset.fn); });
}
async function taskFileGet(id) {
  const c = syncCred(); if (!c) throw new Error("нет входа в аккаунт или ключа Dewiar");
  const r = await http("GET", c.base + "?p=/files&b64=1&id=" + encodeURIComponent(id), { headers: { Authorization: "Bearer " + c.token }, timeout: 60000 });
  let d = {}; try { d = JSON.parse(r.body || "{}"); } catch (e) { }
  if (r.status >= 400 || !d.b64) throw new Error((d.error && d.error.message) || "файл не скачался (" + r.status + ")");
  return d;
}
const b64text = (b) => { try { return decodeURIComponent(escape(atob(b))); } catch (e) { return atob(b); } };
async function taskFileOpen(id, name) {
  try { toast("Открываю…", 1200); const d = await taskFileGet(id); openHtmlView(name.replace(/\.html?$/i, ""), fileViewHtml(name, d.b64, d.type), () => taskFileSave(id, name, d)); }
  catch (e) { plog("warn", "файл задачи: " + e.message); toast("Не открылся: " + e.message, 4000); }
}
async function taskFileSave(id, name, got) {
  try {
    const d = got || await taskFileGet(id);
    const where = D.saveDownloadB64 ? D.saveDownloadB64(d.name || name, d.type || "application/octet-stream", d.b64)
      : (D.saveDownload ? D.saveDownload(d.name || name, d.type || "text/plain", b64text(d.b64)) : "");
    toast(where ? "Сохранено: " + where : "Не получилось сохранить", 3500);
  } catch (e) { plog("warn", "файл задачи: " + e.message); toast("Не сохранился: " + e.message, 4000); }
}
let htmlViewSave = null;
function openHtmlView(title, html, onSave) {
  // на телефоне — отдельное окно без моста Dewiar (HtmlView.java): мост виден во всех фреймах, iframe sandbox не защищает;
  // iframe ниже — в браузере (проверки и веб-версия): sandbox без allow-same-origin — у программы чужое происхождение, ключей сайта она не видит
  if (D.viewHtml && !D.mock) { htmlViewSave = onSave; if (D.viewHtml(String(title || ""), String(html || ""))) return; }
  let v = $("#appview");
  if (!v) { v = document.createElement("div"); v.id = "appview"; document.body.appendChild(v); }
  v.innerHTML = `<div class="avh"><b>${esc(title)}</b><button class="btn" id="av-dl">В «Загрузки»</button><button class="ib" id="av-x" title="Закрыть">${X_SVG}</button></div><iframe sandbox="allow-scripts allow-forms allow-modals" title="${esc(title)}"></iframe>`;
  $("iframe", v).srcdoc = html;
  v.classList.add("on");
  $("#av-x").onclick = () => { v.classList.remove("on"); v.innerHTML = ""; };
  $("#av-dl").onclick = onSave;
}
/* задача закончилась — карточка в разговоре: итог и файлы, чтобы не искать их по меню */
function taskDoneCard(id) {
  const t = mind().tasks[id]; if (!t) return;
  showCard(`<div class="appc task-done"><b>${t.status === "done" ? "✓" : "⚠"} ${esc(t.title)}</b><small>${t.status === "done" ? "задача готова" + (t.where === "cloud" ? " · сделано в облаке Dewiar" : " · сделано на компьютере") : esc(String(t.error || "не вышло").slice(0, 160))}</small>`
    + (t.result ? `<div class="tres">${mdLite(String(t.result).slice(0, 700))}</div>` : "") + taskFiles(t) + `</div>`);
  wireFiles($("#card"));
}

/* ---------- душа: дневник, душа персонажа, конституция, задачи (с компьютера) ---------- */
let soulTab = "diary";
$$("#soul-tabs button").forEach(b => b.onclick = () => { soulTab = b.dataset.t; $("#soul-body").dataset.edit = ""; $$("#soul-tabs button").forEach(x => x.classList.toggle("on", x === b)); renderSoul(); });
$("#b-soul").onclick = () => { renderSoul(); openSheet("#sh-soul"); syncSoon(); };

/* ---------- «Досуг»: милые игры (24.10, владелец: «сидишь в очереди к врачу — „Лира, давай поиграем“ — и набор
   ненадоедающих миленьких игр прямо в интерфейсе Лиры») ----------
   Полка — лист «Досуг» (arcade/shelf.js — тот же список, что у компьютера), игра — во весь экран во фрейме (#gameov).
   «Игры» в игре (сообщение {arcade: 'home'}) и «Назад» телефона — снова полка; игра при этом выгружается (музыка
   не играет в фоне, рекорды игра хранит сама). Выключено в «Возможностях» — ни значка, ни листа. */
const ARC = "arcade/";
function playShelf() {
  if (!window.DewiarArcade) return;
  $("#play-body").innerHTML = `<p class="hint" style="margin:0 2px 12px">Игры на пару минут — касаниями, свайпами или с геймпада. Скажите «Лира, давай поиграем» — откроется эта полка.</p>`
    + `<div class="shelf">${DewiarArcade.html(ARC)}</div>`;
  $$("#play-body .ag").forEach(b => b.onclick = () => gameOpen(b.dataset.game));
}
function playOpen(game) {
  if (!feat("games")) { toast("«Досуг» выключен — включить: «Настройки» → «Ещё» → «Возможности»", 4000); return false; }
  playShelf(); openSheet("#sh-play");
  if (game && window.DewiarArcade && DewiarArcade.find(game)) gameOpen(game);
  return true;
}
const gameOn = () => !$("#gameov").hidden;
function gameOpen(id) {
  if (state !== "idle") interrupt();                        // игра на весь экран — голос и прослушивание замолкают
  const f = $("#gamef"); f.src = DewiarArcade.url(ARC, id) + (document.body.classList.contains("light") ? "?light=1" : "");
  $("#gameov").hidden = false; closeSheets();
}
function gameClose(toShelf = true) {
  const f = $("#gamef"); f.src = "about:blank"; $("#gameov").hidden = true;
  if (toShelf && feat("games")) { playShelf(); openSheet("#sh-play"); }
}
window.addEventListener("message", (e) => { if (e.data && e.data.arcade === "home" && e.source === $("#gamef").contentWindow) gameClose(); });
$("#b-play").onclick = () => playOpen("");
function featApply() { $("#b-play").hidden = !feat("games"); document.body.classList.toggle("has-play", feat("games")); if (!feat("games") && gameOn()) gameClose(false); }
featApply();
/* Объявления для всех (24.10, владелец: «чтобы я для всех мог опубликовать, а у всех это на экранах всплыло»): кабинет →
   «Новости», здесь — ?p=/news без ключа раз в полчаса, при запуске и из уведомления службы «Близких» (CloseLive). Новое
   (номер больше S.annSeen) — карточка с фото, текстом и кнопкой ссылки, один раз; в разговоре и в игре — ждёт. */
let annAt = 0, annItems = [];
const annBase = () => { const c = syncCred(); return (c ? c.base : siteUrl("dwrapp/cloud.php")).split("?")[0]; };
async function annCheck(open) {
  if (!open && Date.now() - annAt < 30 * 60000) return; annAt = Date.now();
  try {
    const r = await http("GET", annBase() + "?p=/news", { timeout: 15000 });
    const d = JSON.parse(r.body || "{}"); annItems = (d.items || []).filter(n => n && n.id).sort((a, b) => b.id - a.id);
  } catch (e) { return; }
  const fresh = annItems.filter(n => n.id > (+S.annSeen || 0));
  if (open && annItems.length) annShow(fresh[0] || annItems[0]);
  else if (fresh.length && state === "idle" && !gameOn() && !$(".sheet.on")) annShow(fresh[0]);
}
function annShow(n) {
  const when = new Date(n.ts * 1000), esc = (t) => String(t || "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  $("#ann-body").innerHTML = (n.img ? `<img class="nw-img" src="${esc(annBase() + "?p=" + n.img)}" alt="">` : "")
    + `<p class="nw-k${n.level === "warn" ? " warn" : ""}">${n.level === "warn" ? "Предупреждение" : "Новость Dewiar"} · ${when.getDate()} ${MON_G[when.getMonth()]}</p>`
    + (n.title ? `<h2 id="an-h">${esc(n.title)}</h2>` : "") + (n.text ? `<p class="nw-t">${esc(n.text)}</p>` : "")
    + `<div class="nw-row">${n.link ? `<button class="btn pri" id="nw-go">${esc(n.link_label || "Смотреть")}</button>` : ""}<button class="btn" id="nw-ok">Понятно</button></div>`;
  const img = $("#ann-body .nw-img"); if (img) img.onerror = () => img.remove();
  if ($("#nw-go")) $("#nw-go").onclick = () => D.openUrl(n.link);
  $("#nw-ok").onclick = () => closeSheets();
  S.annSeen = Math.max(+S.annSeen || 0, n.id); saveS();
  openSheet("#sh-ann");
}
setTimeout(() => annCheck(false), 6000);
document.addEventListener("visibilitychange", () => { if (!document.hidden) setTimeout(() => annCheck(false), 1500); });
setInterval(() => { if (!document.hidden) annCheck(false); }, 5 * 60000);
const MON_G = MON;
function dayHuman(iso) { const d = new Date(iso + "T12:00"); if (isNaN(d)) return iso; const t = new Date(); const y = new Date(Date.now() - 864e5);
  const same = (a, b) => a.toDateString() === b.toDateString();
  return same(d, t) ? "Сегодня" : same(d, y) ? "Вчера" : `${d.getDate()} ${MON_G[d.getMonth()]}` + (d.getFullYear() !== t.getFullYear() ? ` ${d.getFullYear()}` : ""); }
function mdLite(t) {          // Markdown дневника → HTML: сначала экранируем, потом размечаем — пришедший текст не вставит свой HTML
  return esc(String(t || "").replace(/^# [^\n]*\n+/, "").replace(/\n{3,}/g, "\n\n").trim()).replace(/^## (.*)$/gm, "<h4>$1</h4>").replace(/^### (.*)$/gm, "<h5>$1</h5>")
    .replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>").replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<i>$2</i>").replace(/^_(.*)_$/gm, "<i>$1</i>").replace(/^- (.*)$/gm, "• $1").replace(/<\/(h4|h5)>\n+/g, "</$1>");
}
/* Задачи (большая работа на компьютере или в облаке) — в «Мой день» → «Сделанное»: там их и ищут, рядом со сделанным
   на телефоне. Поручить — taskToPc; ход и итог приходят синхронизацией (mind().tasks). */
function tasksHtml() {
  const m = mind(), on = !!(S.sync.on && syncCred());
  const ts = Object.entries(m.tasks).sort((a, b) => String(b[1].updated).localeCompare(String(a[1].updated))), q = qGet("taskq");
  if (!on) return `<div class="card"><b>Большие задачи</b><p class="hint">Презентации, отчёты, исследования делает компьютер с Dewiar или облако Dewiar — нужна синхронизация: тот же ключ Dewiar или вход аккаунтом, что на компьютере.</p><button class="btn p" id="so-sync">Открыть настройки</button></div>`;
  return `<div class="card"><label class="f"><span>Поручить большую задачу</span><textarea id="tk-goal" rows="2" placeholder="Например: «сделай презентацию о погоде на завтра» или «сравни 5 ноутбуков до 1500 рублей»"></textarea></label>
      <button class="btn p w" id="tk-go">Передать</button><p class="hint">${pcOnline() ? "Компьютер на связи — сделает он." : "Компьютер не на связи — сделает облако Dewiar: найдёт, напишет, соберёт файл. Программы на компьютере облако не запускает."}</p></div>`
    + q.map(x => `<div class="it"><div class="bd"><b>${esc(x.title)}</b><small>⏳ отправляю…</small></div></div>`).join("")
    + (ts.length ? `<div class="bugh">Задачи</div>` + ts.map(([id, t]) => `<details class="dday task ${esc(t.status || "")}"${t.status === "done" && (t.files || []).length ? " open" : ""}><summary><div class="bd"><b>${esc(t.title)}</b><small><span class="tst">${esc(TASK_RU[t.status] || t.status || "")}</span>${t.where === "cloud" ? " · в облаке" : ""}${t.activity && t.status === "running" ? " · " + esc(t.activity) : ""}</small></div></summary>
        <div class="dtext tk">${t.question && t.status === "waiting" ? `<p><b>Вопрос:</b> ${esc(t.question)}</p>` : ""}${t.result ? `<p>${mdLite(t.result)}</p>` : `<p class="hint">${esc(t.goal || "")}</p>`}${t.error ? `<p style="color:#FF8FA8">${esc(t.error)}</p>` : ""}${taskFiles(t)}</div></details>`).join("") : "");
}
function wireTasks(box, again) {
  if ($("#tk-go")) $("#tk-go").onclick = () => { const g = $("#tk-goal").value.trim(); if (!g) return; try { taskToPc(g.slice(0, 60), g); toast(pcOnline() ? "Передано компьютеру" : "Делаю в облаке Dewiar — пришлю, когда будет готово", 3000); again(); } catch (e) { toast(e.message); } };
  if ($("#so-sync")) $("#so-sync").onclick = () => openSettings("more");
  wireFiles(box);
}
function renderSoul() {
  if (!["diary", "soul", "const"].includes(soulTab)) soulTab = "diary";      // «Задачи» переехали в «Мой день» → «Сделанное»
  const box = $("#soul-body"), m = mind(), on = !!(S.sync.on && syncCred());
  $$("#soul-tabs button").forEach(x => x.classList.toggle("on", x.dataset.t === soulTab));
  const off = on ? "" : `<div class="card"><b>Нужна синхронизация</b><p class="hint">Дневник и душу персонажей ведёт компьютер с Dewiar — они приходят сюда через синхронизацию. Нужен тот же ключ Dewiar или вход аккаунтом, что на компьютере.</p><button class="btn p" id="so-sync">Открыть настройки</button></div>`;
  if (soulTab === "diary") {
    const days = Object.keys(m.diary).sort().reverse(), ins = m.insights;
    box.innerHTML = off + (ins && (ins.lines || []).length ? `<div class="card soulins"><small class="hint" style="margin:0">Выводы на завтра${ins.title ? " · «" + esc(ins.title) + "»" : ""}</small>${ins.lines.map(x => `<div>• ${esc(x)}</div>`).join("")}</div>` : "")
      + (days.length ? days.map(k => { const e = m.diary[k]; const night = /## 🌙/.test(e.text);
        return `<details class="dday"><summary><div class="tm">${esc(dayHuman(k))}</div><div class="bd"><b>${esc(e.title || (night ? "Ночная запись" : "Записи дня"))}</b><small>${esc(e.mood || "")}${e.mood ? " · " : ""}${esc(String(e.text).replace(/^#+ [^\n]*$/gm, "").replace(/[#*_]/g, "").replace(/\s+/g, " ").trim().slice(0, 120))}</small></div></summary><div class="dtext">${mdLite(e.text)}</div></details>`; }).join("")
        : (on ? `<div class="empty">Дневник пока пуст.<br>Его ведёт ассистент на компьютере: ночью пишет о прожитом дне — о разговорах и там, и здесь.</div>` : ""));
  } else if (soulTab === "soul") {
    const p = persona(), names = [...new Set([p.name, ...Object.keys(m.souls)])];
    const cur = box.dataset.sname && names.includes(box.dataset.sname) ? box.dataset.sname : p.name;
    box.innerHTML = off + `<div class="card"><p class="hint" style="margin-top:0">Автопортрет, который персонаж пишет сам по своему дневнику (на компьютере — раз в неделю). Здесь его можно прочитать и поправить — правка уйдёт и на компьютер.</p>
      ${names.length > 1 ? `<div class="chips">${names.map(n => `<button class="chip${n === cur ? " on" : ""}" data-n="${esc(n)}">${esc(n)}</button>`).join("")}</div>` : ""}
      ${box.dataset.edit === "soul" ? `<label class="f"><span>Душа · ${esc(cur)}</span><textarea id="so-text" rows="14" placeholder="Душа появится, когда в дневнике наберётся пара ночных записей.">${esc((m.souls[cur] || {}).text || "")}</textarea></label>
      <div class="row2"><button class="btn p" id="so-save" style="flex:1">Сохранить</button><button class="btn" id="so-cancel" style="flex:1">Отмена</button></div>`
      : `${((m.souls[cur] || {}).text || "").trim() ? `<div class="dtext soulv">${mdLite(m.souls[cur].text)}</div>` : `<div class="empty">Душа появится, когда в дневнике наберётся пара ночных записей.</div>`}
      <button class="btn w" id="so-edit">Изменить</button>`}</div>`;
    $$(".chip[data-n]", box).forEach(b => b.onclick = () => { box.dataset.sname = b.dataset.n; box.dataset.edit = ""; renderSoul(); });
    if ($("#so-edit")) $("#so-edit").onclick = () => { box.dataset.edit = "soul"; renderSoul(); };
    if ($("#so-cancel")) $("#so-cancel").onclick = () => { box.dataset.edit = ""; renderSoul(); };
    if ($("#so-save")) $("#so-save").onclick = () => { const mm = mind(); mm.souls[cur] = { text: $("#so-text").value, u: Date.now() }; saveMind(mm); syncSoon(); box.dataset.edit = ""; renderSoul(); toast("Душа сохранена"); };
  } else if (soulTab === "const") {
    box.innerHTML = off + `<div class="card"><p class="hint" style="margin-top:0">Принципы, которые все персонажи соблюдают всегда — с любым характером и настроением. Пишете вы; правка уйдёт и на компьютер.</p>
      ${box.dataset.edit === "const" ? `<label class="f"><span>Конституция</span><textarea id="co-text" rows="16" placeholder="Придёт с компьютера после синхронизации.">${esc(m.constitution || "")}</textarea></label>
      <div class="row2"><button class="btn p" id="co-save" style="flex:1">Сохранить</button><button class="btn" id="co-cancel" style="flex:1">Отмена</button></div>`
      : `${(m.constitution || "").trim() ? `<div class="dtext soulv">${mdLite(m.constitution)}</div>` : `<div class="empty">Придёт с компьютера после синхронизации.</div>`}
      <button class="btn w" id="co-edit">Изменить</button>`}</div>`;
    if ($("#co-edit")) $("#co-edit").onclick = () => { box.dataset.edit = "const"; renderSoul(); };
    if ($("#co-cancel")) $("#co-cancel").onclick = () => { box.dataset.edit = ""; renderSoul(); };
    if ($("#co-save")) $("#co-save").onclick = () => { const mm = mind(); mm.constitution = $("#co-text").value; saveMind(mm); syncSoon(); box.dataset.edit = ""; renderSoul(); toast("Конституция сохранена"); };
  }
  if ($("#so-sync")) $("#so-sync").onclick = () => openSettings("more");
}

/* ---------- лист настроек: вкладки «Мозг», «Слух и голос», «Ещё»; разметка собирается строкой, обработчики вешаются
   после вставки; мастера подключения мозга (плитки data-w) — в wizard() ---------- */
const UPD_URL = "https://dewiar.pro/dwrapp/latest.json";
const CLOUD = {
  openrouter: { name: "OpenRouter", url: "https://openrouter.ai/api/v1", model: "google/gemini-2.5-flash", key: "https://openrouter.ai/settings/keys" },
  openai: { name: "OpenAI", url: "https://api.openai.com/v1", model: "gpt-4.1-mini", key: "https://platform.openai.com/api-keys" },
  deepseek: { name: "DeepSeek", url: "https://api.deepseek.com/v1", model: "deepseek-chat", key: "https://platform.deepseek.com/api_keys" },
  anthropic: { name: "Claude (Anthropic)", url: "https://api.anthropic.com/v1", model: "claude-sonnet-5-5", key: "https://platform.claude.com/settings/keys" },
  // признанные поставщики напрямую (20.10): официальные OpenAI-совместимые адреса; модель — первая из rec, что есть у сервиса
  gemini: { name: "Google Gemini", url: "https://generativelanguage.googleapis.com/v1beta/openai", model: "gemini-flash-latest", key: "https://aistudio.google.com/apikey",
            rec: ["gemini-flash-latest", "gemini-2.5-flash", "gemini-flash-lite-latest", "gemini-pro-latest"] },
  kimi: { name: "Kimi (Moonshot)", url: "https://api.moonshot.ai/v1", model: "kimi-latest", key: "https://platform.moonshot.ai/console/api-keys",
          rec: ["kimi-latest", "kimi-k2-turbo-preview", "kimi-k2-0905-preview", "moonshot-v1-32k"] },
  glm: { name: "GLM (Z.ai)", url: "https://api.z.ai/api/paas/v4", model: "glm-4.6", key: "https://z.ai/manage-apikey/apikey-list", rec: ["glm-4.6", "glm-4.5-air", "glm-4.5"] },
  qwen: { name: "Qwen (Alibaba)", url: "https://dashscope-intl.aliyuncs.com/compatible-mode/v1", model: "qwen-plus", key: "https://modelstudio.console.alibabacloud.com/",
          rec: ["qwen-plus", "qwen-flash", "qwen-max", "qwen3-max"] },
  mistral: { name: "Mistral", url: "https://api.mistral.ai/v1", model: "mistral-medium-latest", key: "https://console.mistral.ai/api-keys",
             rec: ["mistral-medium-latest", "mistral-small-latest", "mistral-large-latest"] },
  xai: { name: "Grok (xAI)", url: "https://api.x.ai/v1", model: "grok-4-fast-non-reasoning", key: "https://console.x.ai",
         rec: ["grok-4-fast-non-reasoning", "grok-4-fast-reasoning", "grok-3-mini", "grok-4"] },
  // российские агрегаторы — оплата картой РФ (№141). Только давно работающие (AITunnel и Polza.ai убраны 20.10)
  proxyapi: { name: "ProxyAPI", url: "https://api.proxyapi.ru/openai/v1", model: "gpt-4.1-mini", key: "https://console.proxyapi.ru/keys" },
  vsegpt: { name: "VseGPT", url: "https://api.vsegpt.ru/v1", model: "openai/gpt-4.1-mini", key: "https://vsegpt.ru" },
  custom: { name: "Другой — по адресу", url: "", model: "", key: "" },      // любой OpenAI-совместимый: LiteLLM, Kimi, агрегаторы (комментарии 19.10)
};
/* Модели сервиса по ключу -> [] (не отдал — не беда). Gemini пишет «models/…» — без приставки; не для разговора — прочь. */
async function svcModels(url, key) {
  try {
    const r = await http("GET", url.replace(/\/+$/, "") + "/models", { headers: key ? { Authorization: "Bearer " + key } : {}, timeout: 15000 });
    if (r.status !== 200) return [];
    return ((JSON.parse(r.body) || {}).data || []).map(m => String(m.id || "").replace(/^models\//, ""))
      .filter(m => m && !/(^|[-_/])(tts|whisper|transcribe|dall-e|imagen|veo|moderation|aqa|embed\w*|rerank\w*)([-_.]|$)|image-|audio/i.test(m));
  } catch (e) { return []; }
}
/* Вписанный адрес сервиса: без хвоста /chat/completions, с https:// */
function svcUrl(raw) {
  let u = String(raw || "").trim().replace(/\/+$/, "").replace(/\/chat\/completions$/, "").replace(/\/models$/, "");
  return !u ? "" : /^https?:\/\//i.test(u) ? u : "https://" + u;
}
const ICON = {
  dewiar: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="3"/><path d="M12 3.5v5M12 15.5v5M3.5 12h5M15.5 12h5"/></svg>',
  server: '<svg viewBox="0 0 24 24"><rect x="4" y="3" width="16" height="7" rx="2"/><rect x="4" y="14" width="16" height="7" rx="2"/><path d="M8 6.5h.01M8 17.5h.01"/></svg>',
  cloud: '<svg viewBox="0 0 24 24"><path d="M7 18a4.5 4.5 0 0 1-.6-8.96A6 6 0 0 1 18 8.5a4.5 4.5 0 0 1-.5 9.5z"/></svg>',
  pc: '<svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8M12 16v4"/></svg>',
  key: '<svg viewBox="0 0 24 24"><circle cx="8" cy="15" r="4"/><path d="M10.8 12.2 20 3M16 7l3 3M14 9l2 2"/></svg>',
  user: '<svg viewBox="0 0 24 24"><circle cx="12" cy="8.5" r="4"/><path d="M4.5 20.5a7.5 7.5 0 0 1 15 0"/></svg>',
};
let setTab = "brain";
function openSettings(tab) { if (!$("#sh-set").classList.contains("on")) bugSnapTake(); setTab = tab || setTab; renderSettings(); openSheet("#sh-set"); }
$("#b-set").onclick = () => openSettings();
$("#r-pp").onclick = () => { D.vibrate(12); if (radio.state().state === "paused") radio.resume(); else radio.pause(); };
$("#r-x").onclick = () => { D.vibrate(12); radio.stop(); };

/* Что умеет облако Dewiar сейчас (распознавание, озвучка — /models): при запуске и при открытии настроек, чтобы
   включённая администратором озвучка заработала без повторного входа. */
async function cloudCaps() {
  const bases = [];
  if (loggedIn() && S.accCloud) bases.push([S.accCloud, S.accCloud.base, S.account.token]);
  if (S.llm.cloud) bases.push([S.llm, cloudBase(), S.llm.api_key]);
  for (const [o, base, key] of bases) {
    try { const md = await cloudGet(base, key, "/models"); o.stt = !!md.stt; o.tts = !!md.tts; } catch (e) { }
  }
  if (bases.length) saveS();
}
/* Вошли аккаунтом, а мозг не выбран (облако не ответило при входе, сайт не назвал облако) — подключить модели Dewiar
   по аккаунту. Тихо: при запуске, при открытии «Мозга» и перед вопросом. -> true, если мозг есть. */
let brainBusy = null;
/* Пробный разговор (0.38.99): веб-версия без входа и без ключа сразу говорит через ?p=/trial сайта — без действий, с
   пределом в час (cloud.php trial_handler). Вошли аккаунтом или подключили мозг — проба уходит сама (trialOff, cloudConnect). */
function trialOn() {
  if (!D.web || loggedIn() || S.llm.base_url || S.join) return false;
  S.llm = Object.assign({}, S.llm, { kind: "openai", base_url: CLOUD_URL + "?p=/trial", api_key: "", model: "trial", name: "Пробный разговор", trial: true });
  saveS(); return true;
}
function trialOff() {
  if (!S.llm.trial) return;
  const { base_url, api_key, model, name, trial, kind, ...rest } = S.llm; S.llm = rest; saveS();
}
function ensureBrain() {
  if (S.llm.trial && loggedIn()) trialOff();       // вошли аккаунтом — проба больше не нужна, думают модели Dewiar по аккаунту
  if (S.llm.base_url) return Promise.resolve(true);
  if (!loggedIn()) return Promise.resolve(false);
  if (!brainBusy) brainBusy = cloudConnect(S.account.token, (S.accCloud && S.accCloud.base) || siteUrl((S.account.services || {}).cloud || "dwrapp/cloud.php"), { account: true })
    .then(() => { plog("info", "мозг: модели Dewiar по аккаунту"); return true; }).catch(e => { plog("warn", "мозг по аккаунту: " + e.message); return false; })
    .finally(() => { brainBusy = null; });
  return brainBusy;
}
function openBrain(w) { openSettings("brain"); if (w) setTimeout(() => { const t = $(`.tile[data-w="${w}"]`); if (t) t.click(); }, 250); }
function startLogin() { openSettings("brain"); setTimeout(() => { const t = $('.tile[data-w="account"]'); if (t) t.click(); }, 250); }
function brainName() { if (S.llm.cloud) return "Dewiar Облако"; return S.llm.base_url ? `${S.llm.name || S.llm.base_url.replace(/^https?:\/\//, "")}${S.llm.model ? " · " + S.llm.model : ""}` : "не подключён"; }
function renderSettings() {
  const info = JSON.parse(D.info() || "{}");
  const h = [];
  h.push(`<div class="tabs">${[["brain", "Мозг"], ["voice", "Слух и голос"], ["more", "Ещё"]].map(([k, n]) => `<button data-st="${k}" class="${setTab === k ? "on" : ""}">${n}</button>`).join("")}</div>`);
  if (setTab === "brain") {
    if (loggedIn()) h.push(`<div class="card acc" id="acc-card"><div class="row2"><div class="acc-ava">${esc((S.account.login || "?").slice(0, 1).toUpperCase())}</div><div style="flex:1;min-width:0"><b>${esc(S.account.login)}</b>
      <small class="hint" style="margin:2px 0 0;display:block">Аккаунт ${esc(siteHost())}${S.account.problem ? " · " + esc(S.account.problem) : ""}</small></div><button class="btn" id="acc-out">Выйти</button></div>
      ${S.accCloud && !S.llm.cloud ? `<button class="btn p w" id="acc-use" style="margin-top:10px">Думать моделями Dewiar</button><p class="hint" style="margin:8px 0 0">Сейчас думает ваша модель. Модели Dewiar по аккаунту — с зарядом в талерах.</p>` : ""}
      <p class="hint" style="margin:10px 0 0">Знания сайта подключаются персонажу: нажмите имя персонажа вверху → «Знания». Или просто спросите: «что в моих документах про отпуск?»</p></div>`);
    else if (S.account.problem) h.push(`<div class="card"><div class="res bad" style="margin:0">${esc(S.account.problem)}</div></div>`);
    const on = !!S.llm.base_url && !S.llm.trial;   // пробный разговор на сайте — ещё не «подключено»: выбор мозга открыт
    if (S.llm.trial) h.push(`<div class="card"><small class="hint" style="margin:0">Сейчас</small><div style="font-weight:600">Пробный разговор</div>
      <small class="hint" style="margin:2px 0 0;display:block">Можно говорить без входа — несколько ответов в час и без дел (будильники, заметки, поиск). Войдите или подключите бесплатно — и без ограничений.</small></div>`);
    else h.push(`<div class="card brain ${on ? "ok" : ""}"><div class="row2"><div style="flex:1;min-width:0"><small class="hint" style="margin:0">${on ? "Подключено · думает" : "Мозг"}</small>
      <div style="font-weight:600">${esc(on ? brainName() : loggedIn() ? "подключаю модели Dewiar…" : "не подключён")}</div>
      ${on && S.llm.title ? `<small class="hint" style="margin:2px 0 0;display:block">${esc(S.llm.title)}${S.llm.cloud ? " · " + esc(cloudWho()) : ""}</small>` : ""}</div>
      ${on || loggedIn() ? `<button class="btn" id="br-test">Проверить</button>` : ""}</div><div class="res" id="br-res"></div></div>`);
    const back = llmBack();
    if (back.length) h.push(`<div class="card" id="br-back"><small class="hint" style="margin:0">Прежние мозги — вернуть одной кнопкой</small>${back.map((l, i) =>
      `<div class="row2" style="margin-top:8px"><div style="flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(brainNameOf(l))}</div><button class="btn" data-back="${i}">Вернуть</button></div>`).join("")}<div class="res" id="br-back-res"></div></div>`);
    if (on) h.push(`<div class="card"><div class="sw" style="margin:0"><div>Думать над сложными просьбами<small>Стихи, задачи, анализ, планы — сначала обдумывает: дольше, зато лучше. Простые вопросы — сразу.</small></div>
      <label class="tg"><input type="checkbox" id="br-think" ${S.llm.think !== "off" ? "checked" : ""}><i></i></label></div></div>`);
    if (S.llm.cloud) h.push(`<div class="card cloudc" id="cl-card"><div class="row2"><div style="flex:1"><b>Баланс</b><small class="hint" style="margin:2px 0 0;display:block" id="cl-sub">${esc(cloudWho())}</small></div><div class="cl-pct" id="cl-pct">…</div></div>
      <div class="cl-bar"><i id="cl-fill"></i></div><div class="hint" id="cl-turns" style="margin:0"></div>
      <div class="cl-use" id="cl-use"></div>
      <div class="row2" style="margin-top:10px"><button class="btn" id="cl-ref" style="flex:1">Обновить</button><button class="btn p" id="cl-how" style="flex:1">Пополнить</button></div>
      ${S.llm.account ? "" : `<button class="btn w" id="cl-pair" style="margin-top:8px">Добавить устройство — компьютер или другой телефон</button><div class="res" id="cl-pair-res"></div>
      <div class="row2" style="margin-top:8px">${loggedIn() ? `<button class="btn" id="cl-acc" style="flex:1">Думать по аккаунту</button>` : ""}<button class="btn" id="cl-forget" style="flex:1;color:#FFB3C3">Забыть ключ</button></div>`}
      <div id="cl-pay" style="display:none;margin-top:12px"><div class="hint" id="cl-top" style="margin:0 0 8px;white-space:pre-line;line-height:1.5"></div>
        <div class="row2"><label class="f" style="flex:1"><span>Талеров</span><input id="cl-amt" inputmode="decimal" placeholder="5"></label>
        <label class="f" style="flex:2"><span>Комментарий</span><input id="cl-note" placeholder="как оплатили"></label></div>
        <label class="cl-shot" id="cl-shot"><input type="file" id="cl-file" accept="image/*" hidden><span id="cl-shot-t">Приложить снимок оплаты</span><img id="cl-img" alt=""></label>
        <button class="btn p w" id="cl-send" style="margin-top:8px">Отправить заявку</button><div class="res" id="cl-res"></div><div id="cl-reqs"></div></div></div>`);
    // приглашения друзей (cloud.php ?p=/ref): одна строка и «Пригласить»; список и чужой код — свёрнуты (refFill)
    if (S.llm.cloud) h.push(`<div class="card refc" id="ref-card"><div class="row2"><div style="flex:1"><b>Пригласить друга</b><small class="hint" id="ref-sub" style="margin:2px 0 0;display:block">Подарки вам и другу — талерами</small></div>
      <button class="btn p" id="ref-share">Пригласить</button></div><div id="ref-more"></div></div>`);
    if (S.join && S.join.id && !on) h.push(`<div class="card"><b>Заявка №${esc(S.join.id)} отправлена</b><p class="hint" style="margin:4px 0 10px">Как только её одобрят, всё подключится само — ничего вводить не нужно, я скажу. Можно закрыть приложение: проверю при следующем открытии.</p>
      <div class="row2"><button class="btn p" id="jn-check" style="flex:1">Проверить</button><button class="btn" id="jn-cancel" style="flex:1">Забыть заявку</button></div><div class="res" id="jn-res"></div></div>`);
    // сначала — то, что подходит любому человеку (бесплатная проба, код, аккаунт); своя модель и ключи сервисов —
    // свёрнуты в «Для опытных»: слова Ollama и OpenRouter новичка только пугали
    const tiles = `<p class="hint" style="margin:4px 2px 10px">«Мозг» — это то, чем помощница думает. Проще всего — бесплатно через Dewiar; поменять можно в любой момент.</p><div class="tiles">
      ${loggedIn() || S.join ? "" : `<button class="tile easy" data-w="join">${ICON.dewiar}<b>Подключить бесплатно</b><small>Проще всего: имя и как с вами связаться — и всё. Без регистрации, с подарком на счёте</small></button>`}
      <button class="tile" data-w="dwkey">${ICON.key}<b>Код или ключ Dewiar</b><small>6 цифр с устройства, где Dewiar уже работает, или ключ dw-… от друга</small></button>
      ${loggedIn() ? "" : `<button class="tile" data-w="account">${ICON.user}<b>Аккаунт dewiar.pro</b><small>Есть логин на сайте — всё настроится само</small></button>`}</div>
      <details class="more pro"><summary>Для опытных: своя модель или ключ сервиса</summary><div class="tiles">
      <button class="tile" data-w="server">${ICON.server}<b>Своя модель</b><small>Ollama, LM Studio, vLLM — на вашем компьютере или сервере дома</small></button>
      <button class="tile" data-w="cloud">${ICON.cloud}<b>Ключ любимого сервиса</b><small>OpenAI, Claude, OpenRouter, DeepSeek или любой сервис по адресу — своим ключом</small></button>
      <button class="tile" data-w="pc">${ICON.pc}<b>Как на компьютере</b><small>Файл настроек из студии или адрес от администратора</small></button></div></details><div id="wz"></div>`;
    // мозг уже есть — другие способы свёрнуты: видно, что подключено, и не тянет нажать лишнее
    h.push(on || loggedIn() ? `<details class="more brainalt"><summary>Подключить другой мозг</summary>${tiles}</details>` : tiles);
    h.push(`<div class="card" id="px-card" style="margin-top:12px"><b>Сеть</b><p class="hint" style="margin:4px 0 10px">Провайдер блокирует dewiar.pro? Укажите прокси — через него пойдут только запросы к Dewiar (вход, модели, Знания), остальное — напрямую.</p>
      <div class="row2" style="align-items:flex-end"><label class="f" style="flex:1;min-width:0;margin:0"><span>Прокси</span><input id="px-in" placeholder="socks5://адрес:порт" autocapitalize="off" autocorrect="off" spellcheck="false" value="${esc(hideProxy(S.net.proxy))}"></label><button class="btn p" id="px-save">Сохранить</button></div>
      <div class="sw" style="margin-top:8px"><div>Использовать прокси Dewiar<small>Свой прокси не нужен — его выдаёт dewiar.pro, если вы вошли аккаунтом или подключили ключ. Только для серверов Dewiar.</small></div>
      <label class="tg"><input type="checkbox" id="px-dw" ${S.net.dewiar ? "checked" : ""}><i></i></label></div>
      <div class="sw" style="margin-top:8px"><div>Поиск и страницы через сервер Dewiar<small>Если провайдер режет поисковик или сайт — через сервер Dewiar (нужен вход или ключ). Выключите — только напрямую.</small></div>
      <label class="tg"><input type="checkbox" id="px-web" ${S.net.web_via !== false ? "checked" : ""}><i></i></label></div>
      <div class="res" id="px-res">${S.net.proxy ? "Запросы к Dewiar идут через ваш прокси." : S.net.dewiar && S.net.dewiar_secret ? "Запросы к Dewiar идут через прокси Dewiar." : ""}</div></div>`);
  } else if (setTab === "voice") {
    const voices = JSON.parse(D.voices() || "[]");
    h.push(`<h3>Слух</h3><div class="card">
      <label class="f"><span>Кто распознаёт речь</span><select id="stt-eng"><option value="system">${D.web ? "Этот браузер" : "Это устройство"}${info.recognizer ? "" : " (не найдено)"}</option>${cloudEars() ? `<option value="dewiar">Сервер Dewiar (GigaAM)</option>` : ""}<option value="server">Мой сервер распознавания</option></select></label>
      <div id="stt-srv"><label class="f"><span>Адрес (OpenAI-совместимый, …/v1)</span><input id="stt-url" placeholder="http://192.168.1.10:8090/v1" value="${esc(S.stt.url)}"></label>
      <div class="row2"><label class="f" style="flex:1"><span>Ключ</span><input id="stt-key" type="password" value="${esc(S.stt.key)}"></label><label class="f" style="flex:1"><span>Модель</span><input id="stt-model" placeholder="whisper-1" value="${esc(S.stt.model)}"></label></div></div>
      <div class="sw"><div>Микрофон Bluetooth-наушников<small>Наушники с микрофоном подключены — слушаю ими, а не телефоном: можно отойти от телефона.${D.btMicAvailable && D.btMicAvailable() ? " Сейчас подключены." : ""}</small></div>
      <label class="tg"><input type="checkbox" id="bt-mic" ${S.btMic !== false ? "checked" : ""}><i></i></label></div>
      <p class="hint">${S.stt.auto ? "Распознавание этого устройства не отвечало — слушает сервер Dewiar. " : ""}${info.recognizer ? (D.web ? "Распознаёт сам браузер (Chrome, Edge) — через интернет. В Safari и на iPhone слушает сервер Dewiar — войдите аккаунтом или кодом." : "Распознавание устройства работает и без интернета, если скачан русский язык (Google → Распознавание речи офлайн).") : D.web && cloudEars() ? "В этом браузере нет распознавания речи — слушает сервер Dewiar." : D.web ? "В этом браузере нет распознавания речи — войдите аккаунтом dewiar.pro (слушать будет сервер Dewiar) или откройте Dewiar в Chrome или Safari." : cloudEars() ? "В устройстве нет распознавания речи — слушает сервер Dewiar." : "В устройстве нет распознавания речи — войдите аккаунтом dewiar.pro (слушать будет сервер Dewiar) или укажите свой сервер."}</p></div>
      <h3>Голос</h3><div class="card">
      <label class="f"><span>Кто говорит</span><select id="tts-eng"><option value="system">${D.web ? "Голос браузера" : "Голос устройства"}</option>${cloudVoice() ? `<option value="cloud">Голос Dewiar — у каждого персонажа свой</option>` : ""}<option value="eleven">ElevenLabs — своим ключом</option><option value="server">Голос моего сервера</option></select></label>
      <div id="tts-sys"><div class="row2"><label class="f" style="flex:1"><span>Голос героинь</span><select id="tts-voice"><option value="">Сам подберу</option>${voiceOpts(voices, S.tts.sys_voice)}</select></label>
        <label class="f" style="flex:1"><span>Голос героев</span><select id="tts-voice-m"><option value="">Сам подберу</option>${voiceOpts(voices, S.tts.sys_voice_m)}</select></label></div>
        <p class="hint" style="margin-top:0">${D.web ? "Голоса браузера — это голоса системы: в Windows, macOS и iOS есть русские женские и мужские — героям (Патрику, Джарвису, Агенту) достаётся мужской." : "Голосов устройства бывает несколько: у «Синтеза речи Google» есть и мужские — героям (Патрику, Джарвису, Агенту) достаётся мужской."}</p></div>
      <div id="tts-el"><label class="f"><span>Ключ ElevenLabs</span><input id="el-key" type="password" placeholder="sk_…" value="${esc(S.tts.el_key)}"></label>
        <div class="row2"><label class="f" style="flex:1"><span>Голос героинь (ID)</span><input id="el-vf" placeholder="${EL_VOICES.f} (Sarah)" value="${esc(S.tts.el_voice_f)}"></label>
          <label class="f" style="flex:1"><span>Голос героев (ID)</span><input id="el-vm" placeholder="${EL_VOICES.m} (George)" value="${esc(S.tts.el_voice_m)}"></label></div>
        <label class="f"><span>Модель</span><select id="el-model"><option value="eleven_flash_v2_5">Быстрая (Flash v2.5)</option><option value="eleven_multilingual_v2">Лучшее качество (Multilingual v2)</option></select></label>
        <p class="hint" style="margin-top:0">Ключ — на elevenlabs.io → Профиль → API Keys. Платите вы сами по тарифу ElevenLabs; ключ хранится только в этом телефоне. ID голоса — в «Voices» на сайте (кнопка «ID»).</p></div>
      <label class="f"><span>Скорость речи: <b id="rate-v">${(+S.tts.rate || 1).toFixed(2)}</b></span><input id="tts-rate" type="range" min="0.7" max="2" step="0.05" value="${+S.tts.rate || 1}"></label>
      ${(info.tts && !D.web) || D.mock || (D.web && D.ttsReady()) ? "" : cloudVoice() ? `<p class="hint">В ${D.web ? "этом браузере" : "устройстве"} нет русского голоса — говорит голос Dewiar.</p>` : D.web ? `<p class="hint">В этом браузере нет русского голоса — ответы текстом. Войдите аккаунтом dewiar.pro — заговорит голос Dewiar.</p>`
        : `<p class="hint">В устройстве нет русского голоса, поэтому ответы только текстом. Установите голос: «Синтез речи Google» из Play Маркета или бесплатный RHVoice (есть и для устройств без Google — в AppGallery и F-Droid), затем выберите его в настройках Android → «Синтез речи». <a href="#" id="tts-get">Открыть</a></p>`}</div>
      <div id="tts-srv"><label class="f"><span>Адрес (OpenAI-совместимый, …/v1)</span><input id="tts-url" placeholder="http://192.168.1.10:8091/v1" value="${esc(S.tts.url)}"></label>
      <div class="row2"><label class="f" style="flex:1"><span>Ключ</span><input id="tts-key" type="password" value="${esc(S.tts.key)}"></label><label class="f" style="flex:1"><span>Модель</span><input id="tts-model" placeholder="tts-1" value="${esc(S.tts.model)}"></label></div>
      <div class="row2"><label class="f" style="flex:1"><span>Голос героинь</span><input id="tts-v" placeholder="alloy" value="${esc(S.tts.voice)}"></label><label class="f" style="flex:1"><span>Голос героев</span><input id="tts-vm" placeholder="как у героинь" value="${esc(S.tts.voice_m)}"></label></div></div>
      <button class="btn w" id="tts-try">Послушать</button></div>
      <h3>Разговор</h3><div class="card">
      <label class="f"><span>Как вас зовут</span><input id="u-name" placeholder="необязательно" value="${esc(S.user_name)}"></label>
      <label class="f"><span>Слушать после ответа</span><select id="follow"><option value="ask">Только если ассистент спросил</option><option value="always">Всегда</option><option value="never">Нет</option></select></label>
      <div class="sw" style="margin-top:8px"><div>Сам замечает, что вы вернулись<small>Открыли приложение после перерыва — коротко скажет главное: что готово, что скоро; утром — сводка дня. Сказать нечего — промолчит.</small></div>
      <label class="tg"><input type="checkbox" id="wl-on" ${(S.welcome || {}).on !== false ? "checked" : ""}><i></i></label></div></div>`);
  } else {
    const opt = (list, cur) => list.map(([v, n]) => `<option value="${v}" ${v === cur ? "selected" : ""}>${n}</option>`).join("");
    // фон — плитками с живым образцом (тот же класс темы, что у экрана; кружок — материал её карточек), по группам
    h.push(`<h3>Оформление</h3><div class="card"><div class="skins" role="radiogroup" aria-label="Тема">${
        PHONE_SKINS.map(x => `<button class="skm ${x.id === lookSkin() ? "on" : ""}" data-skin="${x.id}" role="radio" aria-checked="${x.id === lookSkin()}" title="${esc(x.group)} · ${esc(x.name)}"><i class="lk-prev skin-${x.id}"><b></b></i><span>${esc(x.name)}</span></button>`).join("")}</div>
      <label class="f" style="margin-top:6px"><span>Когда говорит</span><select id="ap-fx">${opt([["bars", "Лучи"], ["pulse", "Пульс"], ["wave", "Волна"]], lookFx())}</select></label>
      <div class="sw" style="margin-top:10px"><div>Портрет следит за наклоном<small class="hint" style="display:block;margin:2px 0 0">Наклоните телефон — персонаж чуть повернётся и посмотрит на вас. Камера не нужна.</small></div>
        <label class="tg"><input type="checkbox" id="ap-tilt" ${S.tilt === true ? "checked" : ""}><i></i></label></div></div>`);
    // «Возможности» (24.10): необязательное — по желанию; выключенное прячется, ничего не теряя
    const fsw = (id, k, t, x) => `<div class="sw" style="margin-top:8px"><div>${t}<small>${x}</small></div><label class="tg"><input type="checkbox" id="${id}" data-feat="${k}" ${feat(k) ? "checked" : ""}><i></i></label></div>`;
    h.push(`<h3>Возможности</h3><div class="card"><p class="hint" style="margin:0 0 4px">Включите только то, чем пользуетесь, — остальное не будет мешать. Выключенное ничего не теряет.</p>
      ${fsw("ft-games", "games", "Досуг — милые игры", "Головоломки, судоку, реверси против Лиры и аркады; значок с джойстиком вверху или «Лира, давай поиграем»")}
      ${fsw("ft-near", "near", "Рядом", "«Близкие» → «Рядом»: где близкие, если они сами делятся местом")}
      ${fsw("ft-meet", "meet", "Встречи", "«Близкие» → «Встречи»: знакомства с теми, кто рядом")}</div>`);
    liteApply();
    h.push(`<h3>Лёгкий режим</h3><div class="card"><label class="f" style="margin-top:0"><span>Для слабых телефонов и экономии батареи</span><select id="ap-lite">${opt([["auto", "Сам, когда нужно"], ["on", "Всегда"], ["off", "Никогда"]], S.lite || "auto")}</select></label>
      <p class="hint" id="lite-now" style="margin:6px 2px 0">${liteOn() ? `Сейчас включён: ${esc(liteWhyNow)}.` : "Сейчас выключен."} Портрет в покое неподвижен, проверки реже, «Близкие» без постоянной связи — раз в 15 минут.</p></div>`);
    // звук напоминаний: свои мягкие мелодии (Sounds.java, res/raw), системный или свой файл; ▶ — послушать
    const snd = (() => { try { return JSON.parse(D.alarmSound ? D.alarmSound() : "{}"); } catch (e) { return {}; } })();
    h.push(`<h3>Звук напоминаний</h3><div class="card"><p class="hint" style="margin-top:0">Мягко и сначала тихо — громкость прибавляется за 20 секунд.</p>
      <div class="snds">${ALARM_SOUNDS.map(([id, n, sub]) => `<button class="snd ${id === (snd.id || "signature") ? "on" : ""}" data-snd="${id}"><i>${PLAY_SVG}</i><span><b>${n}</b><small>${sub}</small></span></button>`).join("")}
        <button class="snd ${snd.id === "custom" ? "on" : ""} ${snd.custom ? "" : "nofile"}" data-snd="custom"><i>${PLAY_SVG}</i><span><b>Свой звук</b><small id="snd-name">${snd.custom ? esc(snd.custom) : "Любая мелодия с телефона"}</small></span></button></div>
      <label class="btn w" id="snd-pick"><input type="file" id="snd-file" accept="audio/*" hidden>${snd.custom ? "Выбрать другой файл" : "Выбрать файл…"}</label><div class="res" id="snd-res"></div></div>`);
    if (window.DEWIAR_PRIVACY) h.push(`<h3>${esc(DEWIAR_PRIVACY.title)}</h3><div class="card priv">${DEWIAR_PRIVACY.items.map(([t, x]) => `<p><b>${esc(t)}.</b> ${esc(x)}</p>`).join("")}</div>`);
    h.push(`<h3>${D.web ? "Этот браузер" : "Этот телефон"} в кабинете</h3><div class="card"><p class="hint" style="margin-top:0">В кабинете облака (экзамен, здоровье) ${D.web ? "этот браузер" : "этот телефон"} —
      <b>${esc((info.device || "Телефон") + " · " + (info.version || "") + " · №" + devId().slice(-4))}</b>. Нет в списке — нажмите «Отметиться в кабинете»: появится через минуту.</p>
      <button class="btn w" id="dev-ping">Отметиться в кабинете</button><div class="res" id="dev-res"></div></div>`);
    const perms = [[MIC, "Микрофон"], [NOTIF, "Уведомления (напоминания)"], [CONTACTS, "Контакты (звонки по имени)"], [CALLP, "Звонки без лишнего нажатия"]];
    h.push(`<h3>Сообщить о проблеме</h3><div class="card" id="bug-card"><p class="hint" style="margin-top:0">Напишите пару слов — разработчик увидит их вместе со снимком экрана и журналом работы (без ключей и паролей), ответит сюда, а когда исправит — я скажу. Голосом тоже можно: «сообщи об ошибке: …».</p>
      ${bugSnap && Date.now() - bugSnap.ts < 30 * 6e4 ? `<div class="bugsnap"><img src="data:image/jpeg;base64,${bugSnap.b64}" alt="Снимок экрана" id="bug-img"><label class="chk"><input type="checkbox" id="bug-use" checked><span>Приложить снимок экрана — каким он был до настроек</span></label></div>` : ""}
      <div class="bugpick" id="bug-pickbox">${bugPickHtml()}</div>
      <label class="f"><span>Что случилось</span><textarea id="rep-note" rows="3" maxlength="2000" placeholder="Например: «прошу другое радио — играет старое»"></textarea></label>
      <label class="f"><span>Как подписать вас в «Помощниках проекта» — необязательно</span><input id="bug-who" maxlength="40" value="${esc(S.who || "")}" placeholder="Имя или ник"></label>
      <button class="btn p w" id="rep-send">Отправить разработчику</button><div class="res" id="rep-res"></div>
      <div id="bug-mine">${complaintsHtml()}</div><div id="bug-thx"></div>
      <div class="sw" style="margin-top:8px"><div>Отправлять отчёт самому при сбое<small>Только при ошибках приложения, не чаще раза в полдня на одну и ту же</small></div>
      <label class="tg"><input type="checkbox" id="rep-auto" ${(S.report || {}).auto ? "checked" : ""}><i></i></label></div>
      <div class="sw"><div>Анонимный пульс для разработчика<small>Раз в несколько часов: версия, телефон, скорость запуска, сколько было сбоев — без разговоров, файлов и ключей</small></div>
      <label class="tg"><input type="checkbox" id="pulse-on" ${S.pulse !== false ? "checked" : ""}><i></i></label></div></div>
      <h3>Кнопка помощника</h3><div class="card"><p class="hint" style="margin-top:0">Назначьте Dewiar помощником телефона — тогда долгое нажатие кнопки питания (или «Домой») сразу его слушает.
      Настройки → Приложения → По умолчанию → <b>Цифровой помощник</b> → Dewiar.</p><button class="btn w" id="assist">Открыть настройки помощника</button></div>
      <h3>Управлять приложениями</h3><div class="card" id="hands-card">${handsCard()}</div>
      <h3>Telegram</h3><div class="card" id="tg-card">${!tgOn() ? `<p class="hint" style="margin:0 0 10px">Бот Dewiar в Telegram подключается на компьютере: студия → «Подключение» → Telegram. Бот один для всех ваших устройств: пишите или присылайте голосовые — ответит компьютер, а когда он выключен — сервер Dewiar. На телефоне ничего настраивать не нужно.</p><button class="btn w" id="tg-bot" disabled>Открыть бота в Telegram</button>`
        : (S.tg || {}).linked ? `<div class="row2"><span class="res ok" style="flex:1;margin:0">Подключён${S.tg.name ? ": " + esc(S.tg.name) : ""}${S.tg.bot ? " · @" + esc(S.tg.bot) : ""}</span><button class="btn" id="tg-off">Отключить</button></div>
          <p class="hint" style="margin:8px 0 0">Пишите боту или присылайте голосовые — ответит ${esc(persona().name)}. Заметки, списки и напоминания из Telegram появятся здесь, в «Мой день». Компьютер с Dewiar включён — отвечает он.</p>${S.tg.bot ? `<button class="btn w" id="tg-open" style="margin-top:8px">Открыть бота</button>` : ""}`
        : `<p class="hint" style="margin:0 0 10px">Пишите и присылайте голосовые боту Dewiar в Telegram — ассистент ответит, даже когда телефон убран: поставит напоминание, запишет заметку, ответит голосом.</p><button class="btn p w" id="tg-go">Подключить Telegram</button>`}<div class="res" id="tg-res"></div></div>
      <h3>Умный дом Яндекса</h3><div class="card">${S.home.token ? `<div class="row2"><span class="res ok" style="flex:1" id="home-st">Подключён</span><button class="btn" id="home-off">Отключить</button></div>` :
      `<p class="hint" style="margin-top:0">Тот же дом, что у Алисы: «включи свет в спальне», «кондиционер на 22».</p>
      <p class="hint">Уже подключён на компьютере? Если телефон с ним связан (один аккаунт или «Добавить устройство»), дом появится здесь сам в течение нескольких минут. Иначе: студия → «Подключение» → «Умный дом Яндекса» → «На телефон» — и скажите здесь «отсканируй код».</p>
      <p class="hint"><b>1.</b> «Получить ключ» → войдите в Яндекс тем же аккаунтом, что в «Доме с Алисой» → «Разрешить».<br><b>2.</b> Скопируйте ключ, который покажет Яндекс (начинается с y0_), и вставьте сюда.</p>
      <button class="btn w" id="home-auth" style="margin-bottom:10px">Получить ключ</button>
      <label class="f"><span>Ключ от Яндекса</span><input id="home-tok" type="password" placeholder="y0_…"></label><button class="btn p w" id="home-go">Подключить</button>`}<div class="res" id="home-res"></div></div>
      <h3>Значок «Записать»</h3><div class="card">${widgetCard()}</div>
      <h3>Синхронизация</h3><div class="card">${syncCard()}</div>
      <h3>Разрешения</h3><div class="card">${perms.map(([p, n]) => `<div class="sw"><div>${n}</div>${D.has(p) ? `<span class="res ok" style="margin:0">есть</span>` : `<button class="btn" data-perm="${p}">Разрешить</button>`}</div>`).join("")}
      <div class="sw"><div>Точные будильники</div>${D.exactAlarms() ? `<span class="res ok" style="margin:0">есть</span>` : `<button class="btn" onclick="Dewiar.openSettings('alarms')">Разрешить</button>`}</div></div>
      <h3>Что я умею</h3><div class="card"><p class="hint" style="margin:0 0 10px">Короткие фразы, которые я понимаю сразу: фонарик, радио, сканер кодов, таймер, план дня, «освободи место»… Нажмите любую — и я сделаю.</p>
        <button class="btn w p" id="tricks-open">Посмотреть</button></div>
      <h3>Руководство</h3><div class="card"><p class="hint" style="margin:0 0 10px">Всё, что умеет Dewiar на телефоне и компьютере: примеры фраз, настройки, «Близкие», сканер, стили. Или просто спросите Лиру: «как…»</p>
        <button class="btn w" id="guide-open">Открыть руководство</button></div>
      <h3>О приложении</h3><div class="card"><div>Dewiar ${esc(info.version || "")} · ${D.web ? "в браузере" : "Android " + esc(info.android || "")}</div><small class="hint" style="margin:2px 0 0;display:block">${esc(info.device || "")}</small>
      <div class="res" id="upd-res"></div><button class="btn w" id="upd-check" style="margin-top:6px">Проверить обновление</button>
      <button class="btn w" id="news-open" style="margin-top:8px">Что нового</button></div>
      <details class="danger"><summary>Начать с чистого листа</summary><p class="hint">Ассистент забудет разговор и всё, что запомнил о вас: имя, привычки, просьбы. Дневник, душа персонажей, напоминания и заметки останутся. Отменить нельзя.</p>
      <button class="btn w" id="reset">Забыть разговор и память</button></details>
      ${info.crash ? `<h3>Последняя ошибка</h3><div class="card"><div class="crash">${esc(info.crash)}</div><div class="row2" style="margin-top:8px"><button class="btn" id="cr-send" style="flex:1">Отправить</button><button class="btn" id="cr-clear" style="flex:1">Очистить</button></div></div>` : ""}`);
  }
  $("#set-body").innerHTML = h.join("");
  if (D.web) webTrimSettings();
  $$("[data-st]").forEach(b => b.onclick = () => { setTab = b.dataset.st; renderSettings(); });
  wireSettings(info);
}

function wireSettings(info) {
  const g = (id) => $("#" + id);
  if (g("dev-ping")) g("dev-ping").onclick = async () => { const r = g("dev-res"); r.className = "res"; r.textContent = "отправляю…";
    const ok = await pulseSend(); r.className = ok ? "res ok" : "res bad";
    r.textContent = ok ? "Готово — обновите список «Где» в кабинете." : (S.pulse === false ? "«Анонимный пульс» выключен — включите его ниже, и телефон появится." : "Не получилось — проверьте интернет."); };
  $$(".skm").forEach(b => b.onclick = () => { S.skin = b.dataset.skin; saveS(); applyLook(); $$(".skm").forEach(x => { x.classList.toggle("on", x === b); x.setAttribute("aria-checked", String(x === b)); }); });
  if (g("ap-fx")) g("ap-fx").onchange = () => { S.voice_fx = g("ap-fx").value; saveS(); applyLook(); };
  if (g("ap-tilt")) g("ap-tilt").onchange = () => { S.tilt = g("ap-tilt").checked; saveS(); tiltSync(); };
  $$("[data-feat]").forEach(x => x.onchange = () => { S.features = Object.assign({}, S.features || {}, { [x.dataset.feat]: x.checked }); saveS(); featApply();
    toast(x.checked ? "Включено" : "Выключено — включить можно здесь же", 2200); });
  if (g("ap-lite")) g("ap-lite").onchange = () => { S.lite = g("ap-lite").value; saveS(); liteApply();
    g("lite-now").textContent = (liteOn() ? `Сейчас включён: ${liteWhyNow}.` : "Сейчас выключен.") + " Портрет в покое неподвижен, проверки реже, «Близкие» без постоянной связи — раз в 15 минут."; };
  // звук напоминаний: нажатие — выбрать и послушать (ещё раз — стоп); «Свой звук» без файла — сразу выбор файла
  const sndPlaying = (id) => $$(".snd").forEach(x => x.classList.toggle("play", x.dataset.snd === id));
  $$(".snd").forEach(b => b.onclick = () => {
    const id = b.dataset.snd;
    if (id === "custom" && b.classList.contains("nofile")) return g("snd-file").click();
    if (D.alarmSoundSet && D.alarmSoundSet(id)) $$(".snd").forEach(x => x.classList.toggle("on", x === b));
    sndPlaying(D.alarmSoundTry && D.alarmSoundTry(id) ? id : "");
  });
  if (g("snd-file")) g("snd-file").onchange = () => {
    const f = g("snd-file").files[0]; if (!f) return;
    if (f.size > 12 * 1024 * 1024) { g("snd-res").className = "res bad"; g("snd-res").textContent = "Файл больше 12 МБ — выберите покороче."; return; }
    g("snd-res").className = "res"; g("snd-res").textContent = "Сохраняю…";
    const fr = new FileReader();
    fr.onload = () => {
      const err = D.alarmSoundCustom ? D.alarmSoundCustom(String(fr.result).split(",")[1] || "", f.name.replace(/\.[a-z0-9]+$/i, "")) : "нет на этом телефоне";
      if (err) { g("snd-res").className = "res bad"; g("snd-res").textContent = "Не подошёл: " + err + "."; return; }
      g("snd-res").className = "res ok"; g("snd-res").textContent = "Свой звук выбран.";
      const c = $('.snd[data-snd="custom"]'); c.classList.remove("nofile"); g("snd-name").textContent = f.name.replace(/\.[a-z0-9]+$/i, "");
      $$(".snd").forEach(x => x.classList.toggle("on", x === c));
      sndPlaying(D.alarmSoundTry && D.alarmSoundTry("custom") ? "custom" : "");
    };
    fr.readAsDataURL(f);
  };
  if (g("br-think")) g("br-think").addEventListener("change", () => { if (g("br-think").checked) delete S.llm.think; else S.llm.think = "off"; saveS(); });
  if (setTab === "brain") {
    $$("#br-back [data-back]").forEach(b => b.onclick = async () => {
      const r = g("br-back-res"); b.disabled = true; r.className = "res"; r.textContent = "подключаю…";
      try { await llmRestore(+b.dataset.back); toast("Мозг: " + brainName()); renderSettings(); }
      catch (e) { b.disabled = false; r.className = "res bad"; r.textContent = e.message; }
    });
    if (g("br-test")) g("br-test").onclick = async () => { const b = g("br-test"), r = g("br-res"); b.disabled = true; r.className = "res"; r.textContent = "спрашиваю модель…";
      try {
        if (!S.llm.base_url && !(await ensureBrain())) throw new Error("модели Dewiar по аккаунту сейчас не отвечают — проверьте интернет");
        const t0 = Date.now(); const x = await llmStream([{ role: "user", content: "Ответь одним словом: готово" }], null, null);
        r.className = "res ok"; r.textContent = `Работает: ответ за ${((Date.now() - t0) / 1000).toFixed(1)} с — «${x.text.trim().slice(0, 60)}»`;
        if (!g("cl-card") && S.llm.cloud) setTimeout(renderSettings, 1500);
      } catch (e) { r.className = "res bad"; r.textContent = e.message; } finally { b.disabled = false; } };
    if (!S.llm.base_url && loggedIn()) ensureBrain().then(ok => { if (ok && setTab === "brain" && $("#sh-set").classList.contains("on")) renderSettings(); });
    cloudCaps();
    $$(".tile").forEach(b => b.onclick = () => { $$(".tile").forEach(x => x.classList.toggle("on", x === b)); wizard(b.dataset.w); });
    if (g("jn-check")) g("jn-check").onclick = async () => { const r = g("jn-res"); r.className = "res"; r.textContent = "проверяю…";
      try { const d = await joinPoll(true); r.className = d && d.status === "no" ? "res bad" : "res ok"; r.textContent = (d && d.text) || "Пока ждёт проверки."; if (d && d.key) setTimeout(renderSettings, 1200); }
      catch (e) { r.className = "res bad"; r.textContent = e.message; } };
    if (g("jn-cancel")) g("jn-cancel").onclick = () => { S.join = null; saveS(); renderSettings(); };
    if (g("px-save")) g("px-save").onclick = () => saveProxy(g("px-in").value, g("px-res"), g("px-save"));
    if (g("px-web")) g("px-web").onchange = () => { S.net.web_via = g("px-web").checked; saveS(); toast(S.net.web_via ? "Запасной путь через Dewiar включён" : "Поиск и страницы — только напрямую"); };
    if (g("px-dw")) g("px-dw").onchange = async () => { const on = g("px-dw").checked, r = g("px-res"); S.net.dewiar = on; saveS();
      r.className = "res"; r.textContent = on ? "получаю прокси с dewiar.pro…" : "";
      const err = on ? await dwProxyFetch(true) : ""; applyProxy();
      r.className = "res " + (err ? "bad" : "ok"); r.textContent = !on ? "Прокси Dewiar выключен." : err ? "Прокси Dewiar: " + err : (S.net.proxy ? "Прокси Dewiar получен; сейчас главнее ваш прокси." : "Запросы к Dewiar идут через прокси Dewiar."); };
    if (g("acc-out")) g("acc-out").onclick = () => { if (!confirm("Выйти из аккаунта dewiar.pro? Модели и Знания по аккаунту отключатся.")) return; accountLogout(); toast("Вы вышли из аккаунта"); renderSettings(); };
    if (g("acc-use")) g("acc-use").onclick = async () => { const b = g("acc-use"); b.disabled = true;
      try { await cloudConnect(S.account.token, S.accCloud.base, { account: true }); toast("Думают модели Dewiar"); renderSettings(); } catch (e) { b.disabled = false; toast(e.message); } };
    if (g("ref-card")) { refLoad(); g("ref-share").onclick = () => refShare().catch(e => toast(e.message)); }
    if (g("cl-card")) {
      cloudFill(cloudInfo); cloudBalance(true).then(cloudFill).catch(async e => {
        if (await fixDeadKey(e.message)) { renderSettings(); return; }            // ключ удалён, а аккаунт есть — переключились сами
        g("cl-turns").textContent = e.message + (keyGone(e.message) ? " Нажмите «Забыть ключ»" + (loggedIn() ? " или «Думать по аккаунту»." : " и подключите мозг заново.") : ""); g("cl-pct").textContent = "—"; });
      if (g("cl-acc")) g("cl-acc").onclick = async () => { g("cl-acc").disabled = true; if (await fixDeadKey()) renderSettings(); else { g("cl-acc").disabled = false; toast("Не получилось подключиться по аккаунту — проверьте интернет"); } };
      if (g("cl-pair")) g("cl-pair").onclick = async () => { const r = g("cl-pair-res"); r.className = "res"; r.textContent = "получаю код…";
        try { const d = await cloudPost("/pair/new", {});
          if (!d.code) { r.textContent = d.text || "Код не выдан."; return; }
          r.className = "res ok"; r.innerHTML = `Код: <b style="font-size:22px;letter-spacing:3px">${esc(d.code.slice(0, 3) + " " + d.code.slice(3))}</b><br>На другом устройстве: «Мозг» → «Код или ключ Dewiar» → введите код. Действует 10 минут.`; }
        catch (e) { r.className = "res bad"; r.textContent = e.message; } };
      if (g("cl-forget")) g("cl-forget").onclick = async () => {
        if (!confirm(loggedIn() ? "Забыть ключ Dewiar? Думать буду по аккаунту " + (S.account.login || "") + "." : "Забыть ключ Dewiar? Мозг нужно будет подключить заново.")) return;
        await forgetKey(); toast("Ключ забыт"); renderSettings(); };
      // «Обновить» — заметно: что сейчас на счёте (раньше нажатие выглядело так, будто ничего не произошло)
      g("cl-ref").onclick = () => cloudBalance(true).then(c => { cloudFill(c); cloudUsage && cloudUsage();
        toast("Обновлено: " + (c.site ? (c.balance_text || c.balance + " тал.") + " на счёте dewiar.pro" : "заряд " + (c.percent ?? 0) + "%")); }).catch(e => toast(e.message));
      g("cl-how").onclick = () => { const t = g("cl-pay"), open = t.style.display === "none"; t.style.display = open ? "" : "none"; if (open) clPayLoad(); };
      cloudUsage();
      let img = "";
      g("cl-file").onchange = (e) => { const f = e.target.files[0]; if (!f) return; if (f.size > 6e6) { toast("Снимок больше 6 МБ"); return; }
        const fr = new FileReader(); fr.onload = () => { img = fr.result; g("cl-img").src = img; g("cl-shot").classList.add("has"); g("cl-shot-t").textContent = "Снимок приложен"; }; fr.readAsDataURL(f); };
      g("cl-send").onclick = async () => { const r = g("cl-res"), amount = +(g("cl-amt").value.replace(",", ".")) || 0;
        if (!amount && !img) { r.className = "res bad"; r.textContent = "Укажите сумму или приложите снимок"; return; }
        r.className = "res"; r.textContent = "отправляю…";
        try { const x = await cloudPost("/topup", { amount, note: g("cl-note").value.trim(), image: img }); r.className = "res ok"; r.textContent = "Заявка отправлена — после проверки заряд пополнится сам.";
          img = ""; g("cl-shot").classList.remove("has"); g("cl-shot-t").textContent = "Приложить снимок оплаты"; g("cl-amt").value = ""; g("cl-note").value = ""; clReqs(x.requests); }
        catch (e) { r.className = "res bad"; r.textContent = e.message; } };
    }
  } else if (setTab === "voice") {
    const sttDw = ((S.stt.engine === "server" && /cloud\.php/.test(S.stt.url || "")) || (S.stt.engine === "system" && !info.recognizer)) && cloudEars();
    if (g("wl-on")) g("wl-on").addEventListener("change", () => { S.welcome = Object.assign({}, S.welcome || {}, { on: g("wl-on").checked }); saveS(); });
    g("stt-eng").value = sttDw ? "dewiar" : S.stt.engine; g("tts-eng").value = S.tts.engine === "cloud" && !cloudVoice() ? "system" : S.tts.engine; g("follow").value = S.follow;
    const vis = () => { const te = g("tts-eng").value; g("stt-srv").style.display = g("stt-eng").value === "server" ? "" : "none";
      g("tts-srv").style.display = te === "server" ? "" : "none"; g("tts-el").style.display = te === "eleven" ? "" : "none";
      g("tts-sys").style.display = te === "system" || te === "cloud" ? "" : "none"; };
    g("el-model").value = S.tts.el_model || "eleven_flash_v2_5";
    vis();
    const saveV = () => { const se = g("stt-eng").value, ce = cloudEars();
      S.stt = se === "dewiar" && ce ? { engine: "server", url: ce.url, key: ce.key, model: "gigaam", from_account: loggedIn() }
        : { engine: se, url: se === "server" && /cloud\.php/.test(g("stt-url").value) ? "" : g("stt-url").value.trim(), key: g("stt-key").value.trim(), model: g("stt-model").value.trim() };
      Object.assign(S.tts, { engine: g("tts-eng").value, url: g("tts-url").value.trim(), key: g("tts-key").value.trim(), model: g("tts-model").value.trim(), sys_voice: g("tts-voice").value,
        sys_voice_m: g("tts-voice-m").value, voice: g("tts-v").value.trim(), voice_m: g("tts-vm").value.trim(), el_key: g("el-key").value.trim(),
        el_voice_f: g("el-vf").value.trim(), el_voice_m: g("el-vm").value.trim(), el_model: g("el-model").value, rate: +g("tts-rate").value });
      S.user_name = g("u-name").value.trim(); S.follow = g("follow").value; saveS(); vis(); g("rate-v").textContent = (+S.tts.rate).toFixed(2); };
    $$("#set-body input, #set-body select").forEach(x => x.onchange = saveV);
    g("bt-mic").onchange = () => { S.btMic = g("bt-mic").checked; saveS(); btMicSync(); };
    const rateFill = () => { const r = g("tts-rate"); r.style.setProperty("--p", ((r.value - r.min) / (r.max - r.min) * 100) + "%"); };
    rateFill();
    g("tts-rate").oninput = () => { g("rate-v").textContent = (+g("tts-rate").value).toFixed(2); rateFill(); };
    g("tts-try").onclick = () => { saveV(); say(`Привет! Это ${persona().name}. Так звучит мой голос.`); };
    if (g("tts-get")) g("tts-get").onclick = (e) => { e.preventDefault(); D.openSettings("tts") || D.openUrl("https://play.google.com/store/apps/details?id=com.google.android.tts"); };
  } else {
    g("assist").onclick = () => { if (!D.openSettings("assistant")) toast("Откройте: Настройки → Приложения → По умолчанию → Цифровой помощник"); };
    $$("[data-perm]").forEach(b => b.onclick = async () => { await needPerm(b.dataset.perm); renderSettings(); });
    if (g("home-go")) g("home-go").onclick = async () => { const r = g("home-res"); let tok = g("home-tok").value.trim(); const m = tok.match(/access_token=([^&\s]+)/); if (m) tok = m[1];
      if (/^[0-9a-f]{32}$/i.test(tok)) { r.className = "res bad"; r.textContent = "Это ClientID приложения, а не ключ. Нажмите «Получить ключ» → «Разрешить» — Яндекс покажет ключ (начинается с y0_)"; return; }
      if (tok.length < 20) { r.className = "res bad"; r.textContent = tok ? "Это не похоже на ключ — скопируйте его целиком (начинается с y0_)" : "Сначала «Получить ключ» — Яндекс покажет ключ, вставьте его сюда"; return; }
      const old = S.home.token; S.home.token = tok; r.className = "res"; r.textContent = "проверяю…";
      try { const i = await homeGet(true); homeSet(tok); r.className = "res ok"; r.textContent = `Готово: устройств ${i.devices.length}, сценариев ${i.scenarios.length}. Скажите «включи свет».`; setTimeout(renderSettings, 1800); }
      catch (e) { S.home.token = old; r.className = "res bad"; r.textContent = e.message; } };
    if (g("home-auth")) g("home-auth").onclick = () => D.openUrl("https://oauth.yandex.ru/authorize?response_type=token&client_id=" + ((S.home.client_id || "").trim() || YANDEX_CID));
    if (g("home-off")) { homeGet().then(i => g("home-st") && (g("home-st").textContent = `Подключён: устройств ${i.devices.length}`)).catch(e => g("home-st") && (g("home-st").textContent = e.message));
      g("home-off").onclick = () => { homeSet(""); renderSettings(); }; }
    wireHands();
    if (g("tg-go")) g("tg-go").onclick = async () => { const b = g("tg-go"), r = g("tg-res"); b.disabled = true; r.className = "res"; r.textContent = "готовлю ссылку…";
      try { await tgLink(r); toast("Telegram подключён"); renderSettings(); } catch (e) { r.className = "res bad"; r.textContent = e.message; b.disabled = false; } };
    if (g("tg-off")) g("tg-off").onclick = async () => { if (!confirm("Отключить Telegram? Бот перестанет отвечать вам.")) return;
      try { await tgCall("dewiarUnlink"); S.tg = { linked: false }; saveS(); renderSettings(); } catch (e) { g("tg-res").className = "res bad"; g("tg-res").textContent = e.message; } };
    if (g("tg-open")) g("tg-open").onclick = () => D.openUrl("https://t.me/" + S.tg.bot);
    if (g("tg-bot")) tgBotName().then(n => { const b = g("tg-bot"); if (!b) return; if (!n) { b.remove(); return; }
      b.disabled = false; b.textContent = "Открыть @" + n; b.onclick = () => D.openUrl("https://t.me/" + n); }).catch(() => { if (g("tg-bot")) g("tg-bot").remove(); });
    if (tgOn() && g("tg-card")) tgStatus().then(t => { if (!!t.linked !== !!$("#tg-off") && setTab === "more") renderSettings(); }).catch(() => {});
    g("upd-check").onclick = () => checkUpdate(true);
    if (g("news-open")) g("news-open").onclick = () => { closeSheets(); setTimeout(() => newsShow(newsList("", JSON.parse(D.info() || "{}").version || "9")), 250); };
    if (g("guide-open")) g("guide-open").onclick = () => D.openUrl(GUIDE_URL);
    if (g("tricks-open")) g("tricks-open").onclick = () => openTricks();
    if (g("cr-send")) g("cr-send").onclick = () => reportSend("Падение приложения", false, String(info.crash).split("\n")[0]).then(d => toast(`Отчёт №${d.id} отправлен — спасибо!`))
      .catch(e => { toast(e.message); D.share("Dewiar — ошибка:\n" + info.crash); });
    // отзыв 17.10: «непонятно, как добавить фото к жалобе» — кнопка «Добавить фото или скриншот» (галерея: свежие — первыми)
    const pickWire = () => { const f = g("bug-file"); if (f) f.onchange = async () => { const file = f.files && f.files[0]; f.value = ""; if (!file) return;
        try { bugPick = await shrinkImage(file, 1600); } catch (e) { toast(e.message); return; } g("bug-pickbox").innerHTML = bugPickHtml(); pickWire(); };
      const x = g("bug-pickx"); if (x) x.onclick = () => { bugPick = ""; g("bug-pickbox").innerHTML = bugPickHtml(); pickWire(); };
      const im = g("bug-pickimg"); if (im) im.onclick = () => imgView(bugPick); };
    if (g("bug-pickbox")) pickWire();
    if (g("rep-send")) g("rep-send").onclick = async () => { const b = g("rep-send"), r = g("rep-res"); b.disabled = true; r.className = "res"; r.textContent = "отправляю…";
      try {
        const d = await complaintSend(g("rep-note").value, g("bug-who").value, !!(g("bug-use") && g("bug-use").checked), "кнопкой");
        r.className = "res ok"; r.textContent = `Жалоба №${d.id} у разработчика — спасибо! Ответ придёт сюда.`; g("rep-note").value = "";
        if (g("bug-mine")) g("bug-mine").innerHTML = complaintsHtml(); if (g("bug-img")) g("bug-img").parentNode.remove();
        if (g("bug-pickbox")) { g("bug-pickbox").innerHTML = bugPickHtml(); pickWire(); }
      } catch (e) { r.className = "res bad"; r.textContent = e.message; } finally { b.disabled = false; } };
    if (g("rep-auto")) g("rep-auto").onchange = () => { S.report = Object.assign({}, S.report, { auto: g("rep-auto").checked }); saveS(); };
    if (g("pulse-on")) g("pulse-on").onchange = () => { S.pulse = g("pulse-on").checked; saveS(); };
    if (g("bug-img")) g("bug-img").onclick = () => g("bug-img").classList.toggle("zoom");
    if (g("bug-thx")) thanksGet().then(th => { if (g("bug-thx") && th.length) g("bug-thx").innerHTML = `<div class="bugh">Помощники проекта — их жалобы сделали Dewiar лучше</div><div class="thx">`
      + th.slice(0, 30).map(p => `<span>${esc(p.name)}<b>${+p.n || 0}</b></span>`).join("") + "</div>"; }).catch(() => {});
    if (g("bug-mine") && (S.complaints || []).length) complaintsCheck().then(n => { if (n.length && g("bug-mine")) g("bug-mine").innerHTML = complaintsHtml(); }).catch(() => {});
    if (g("cr-clear")) g("cr-clear").onclick = () => { D.clearCrash(); renderSettings(); };
    g("reset").onclick = () => {                       // два вопроса подряд: случайным нажатием отношения с ассистентом не стереть
      if (!confirm(`Забыть разговор и всё, что ${persona().name} помнит о вас (${(S.memory || []).length} записей)?`)) return;
      if (!confirm("Точно? Это нельзя отменить. Память сотрётся и на компьютере после синхронизации.")) return;
      history = []; saveH(); convReset(); S.memory = []; saveS(); syncSoon(); toast("Забыл"); };
    if (g("wg-on")) g("wg-on").onchange = () => { try { D.widgetSet(g("wg-on").checked); } catch (e) { } renderSettings(); };
    if (g("wg-pin")) g("wg-pin").onclick = () => { let ok = false; try { ok = D.widgetPin(); } catch (e) { }
      const r = g("wg-res"); r.className = "res" + (ok ? " ok" : ""); r.textContent = ok ? "Подтвердите на экране — и значок появится на рабочем столе" : "Добавьте вручную: долгое нажатие на рабочем столе → «Виджеты» → Dewiar"; };
    if (g("sy-now")) g("sy-now").onclick = async () => { const r = g("sy-res"); r.className = "res"; r.textContent = "синхронизирую…"; await syncRun(true); renderSettings(); };
    if (g("sy-on")) g("sy-on").onchange = () => { S.sync.on = g("sy-on").checked; saveS(); if (S.sync.on) syncSoon(); renderSettings(); };
    if (g("sy-e2e")) g("sy-e2e").onchange = () => {
      const on = g("sy-e2e").checked;
      if (!on && !confirm("Выключить шифрование на этом устройстве? Свои изменения оно снова будет отправлять открытыми. На других устройствах выключите отдельно.")) { g("sy-e2e").checked = true; return; }
      e2eEnable(on); renderSettings(); };
  }
}

/* ---------- синхронизация с компьютером через облако Dewiar (cloud.php ?p=/sync) ----------
   Напоминания и будильники, заметки, расходы, память «Обо мне» — одинаковые на телефоне и компьютере. Раз в минуту, пока
   приложение открыто, при открытии и сразу после своих изменений: отправляем то, что поменялось с прошлого раза
   (отпечатки — в pref «sync»), и забираем чужое. Одну запись правили на двух устройствах — остаётся более поздняя правка.
   Запись, которой больше нет в syncSnapshot(), уходит как удаление — и другие устройства её тоже удалят.
   Формат записей, виды (SYNC_KINDS) и порядок обмена — общие с core/sync.py (компьютер) и ?p=/sync в cloud.php:
   меняешь здесь — меняй и там. Дополнительные виды (soul, mind, diary, dayturn, taskreq, task, done) шлём, только если их знает сервер. */
const MIND_MAX = 8000, MIND_CTRL = /[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f\u200b-\u200f\u202a-\u202e\u2066-\u2069]/g;
const mindText = (d) => (d && typeof d.text === "string" && d.text.trim() && d.text.length <= MIND_MAX) ? d.text.replace(MIND_CTRL, "") : "";
const SYNC_KINDS = ["reminder", "note", "money", "memory", "soul", "mind", "diary", "dayturn", "taskreq", "task", "done", "persona"];
/* Сквозное шифрование синхронизации (S.sync.e2e, как core/sync.py и core/synckey.py): ключ 32 байта знают только свои
   устройства (pref sync_key; другим своим — конвертом ownShare), личные записи уходят {e2e: 1, c: seal(K, JSON)}.
   Открытыми — метка mind:e2e, задачи для облака (taskreq с cloud) и удаления. */
const E2E_KINDS = ["reminder", "note", "money", "memory", "soul", "mind", "diary", "dayturn", "done", "persona", "vault", "task", "taskreq"];
function syncKeyGet() { try { const d = JSON.parse(prefGet("sync_key") || "null"); return d && d.k && DC() && DC().b64d(d.k).length === 32 ? d : null; } catch (e) { return null; } }
function syncKeyAdopt(kb64, at) {
  let k; try { k = DC().b64d(String(kb64 || "")); } catch (e) { return false; }
  if (!k || k.length !== 32) return false;
  const cur = syncKeyGet(); if (cur && (cur.k === kb64 || (+at || 0) <= cur.at)) return false;
  prefSet("sync_key", JSON.stringify({ k: DC().b64e(k), at: +at || Date.now() })); return true;
}
const e2eKey = () => { const c = S.sync && S.sync.e2e ? syncKeyGet() : null; return c ? DC().b64d(c.k) : null; };
const anyKey = () => { const c = syncKeyGet(); return c ? DC().b64d(c.k) : null; };
const e2eWaiting = () => { const st = syncSt(); return !!(st && st.e2eRemote) && !syncKeyGet(); };
const e2eSealable = (kind, id, data) => kind + ":" + id !== "mind:e2e" && E2E_KINDS.includes(kind) && data && typeof data === "object" && Object.keys(data).length > 0 && !(kind === "taskreq" && data.cloud);
const e2eSeal = (k, data) => ({ e2e: 1, c: DC().b64e(DC().seal(k, DC().utf8(JSON.stringify(data)))) });
const e2eOpen = (k, d) => JSON.parse(DC().fromUtf8(DC().unseal(k, DC().b64d(d.c || ""))));
const e2eSealed = (d) => !!(d && d.e2e && typeof d.c === "string");
function e2eEnable(on) {
  if (on && !syncKeyGet()) prefSet("sync_key", JSON.stringify({ k: DC().b64e(DC().randomBytes(32)), at: Date.now() }));
  S.sync.e2e = !!on; saveS();
  const st = syncSt() || {}; st.resealAll = true; st.e2eOffHere = !on; prefSet("sync", JSON.stringify(st));
  if (on) ownShare().catch(() => { });
  syncSoon();
}
let syncTimer = null, syncBusy = false, syncStatus = { ok: null, at: 0, error: "", devices: [], counts: {} };
/* Чьи данные: аккаунт dewiar.pro (если вошли) или ключ Dewiar (dw-…). Есть и то и другое — ключ уходит в link
   (X-Sync-Link): сервер связывает их в одно пространство. -> {token, link, base, via} или null — синхронизировать нечем. */
function syncCred() {
  const key = S.llm.cloud && !S.llm.account && /^dw-/.test(S.llm.api_key || "") ? S.llm.api_key : (S.sync && S.sync.key) || "";
  if (loggedIn()) return { token: S.account.token, link: key, base: ((S.accCloud && S.accCloud.base) || siteUrl("dwrapp/cloud.php")).split("?")[0], via: "аккаунт " + (S.account.login || "") };
  if (key) return { token: key, link: "", base: (S.llm.cloud ? cloudBase() : CLOUD_URL).split("?")[0], via: "ключ Dewiar …" + key.slice(-4) };
  return null;
}
const syncSt = () => { try { return JSON.parse(prefGet("sync") || "") || null; } catch (e) { return null; } };
function syncHash(o) {                         // FNV-1a по каноническому JSON — отпечаток «как запись лежит у нас»
  const canon = (x) => Array.isArray(x) ? "[" + x.map(canon).join(",") + "]" : x && typeof x === "object"
    ? "{" + Object.keys(x).sort().map(k => JSON.stringify(k) + ":" + canon(x[k])).join(",") + "}" : JSON.stringify(x === undefined ? null : x);
  const s = canon(o); let h1 = 0x811c9dc5, h2 = 0x01000193;
  for (let i = 0; i < s.length; i++) { const c = s.charCodeAt(i); h1 = Math.imul(h1 ^ c, 16777619) >>> 0; h2 = Math.imul(h2 ^ c, 2246822519) >>> 0; }
  return h1.toString(16) + h2.toString(16);
}
function sha1hex(str) {                        // SHA-1 текста (UTF-8) — для factId ниже
  const b = unescape(encodeURIComponent(str)), n = b.length, w = [], H = [0x67452301, 0xEFCDAB89, 0x98BADCFE, 0x10325476, 0xC3D2E1F0];
  for (let i = 0; i < n; i++) w[i >> 2] |= b.charCodeAt(i) << (24 - (i % 4) * 8);
  w[n >> 2] |= 0x80 << (24 - (n % 4) * 8); w[((n + 8 >> 6) + 1) * 16 - 1] = n * 8;
  for (let i = 0; i < w.length; i += 16) {
    const W = [], [a0, b0, c0, d0, e0] = H; let a = a0, b1 = b0, c = c0, d = d0, e = e0;
    for (let t = 0; t < 80; t++) {
      W[t] = t < 16 ? (w[i + t] | 0) : ((x) => (x << 1) | (x >>> 31))(W[t - 3] ^ W[t - 8] ^ W[t - 14] ^ W[t - 16]);
      const f = t < 20 ? (b1 & c) | (~b1 & d) : t < 40 ? b1 ^ c ^ d : t < 60 ? (b1 & c) | (b1 & d) | (c & d) : b1 ^ c ^ d;
      const k = t < 20 ? 0x5A827999 : t < 40 ? 0x6ED9EBA1 : t < 60 ? 0x8F1BBCDC : 0xCA62C1D6;
      const tmp = (((a << 5) | (a >>> 27)) + f + e + k + W[t]) | 0; e = d; d = c; c = (b1 << 30) | (b1 >>> 2); b1 = a; a = tmp;
    }
    H[0] = (H[0] + a) | 0; H[1] = (H[1] + b1) | 0; H[2] = (H[2] + c) | 0; H[3] = (H[3] + d) | 0; H[4] = (H[4] + e) | 0;
  }
  return H.map(x => (x >>> 0).toString(16).padStart(8, "0")).join("");
}
// id строки памяти по её тексту: нормализация и sha1 — как _fact_id в core/sync.py, иначе одна и та же строка задвоится
const factId = (t) => "f" + sha1hex(String(t).trim().toLowerCase().replace(/\.+$/, "").replace(/\s+/g, " ")).slice(0, 12);
/* повтор: строка телефона («daily», «weekdays», «weekly») ↔ описание компьютера ({kind, time, days}; дни — как в Python,
   понедельник = 0) */
function repToDict(rep, at) {
  if (!rep) return null;
  const d = new Date(at), time = pad(d.getHours()) + ":" + pad(d.getMinutes());
  if (rep === "daily") return { kind: "daily", time };
  if (rep === "weekdays") return { kind: "weekly", days: [0, 1, 2, 3, 4], time };
  if (rep === "weekly") return { kind: "weekly", days: [(d.getDay() + 6) % 7], time };
  return null;
}
function repFromDict(r) {
  if (!r || typeof r !== "object") return "";
  const days = (r.days || []).slice().sort().join(",");
  if (r.kind === "daily" && (!r.days || r.days.length === 7)) return "daily";
  if ((r.kind === "daily" || r.kind === "weekly") && days === "0,1,2,3,4") return "weekdays";
  if (r.kind === "weekly" && (r.days || []).length === 1) return "weekly";
  return "";                                  // раз в месяц, через N минут и т. п. — телефон позвонит один раз, а следующий срок пришлёт компьютер
}
/* ---------- душа, конституция, дневник и задачи — с компьютера через синхронизацию (хранятся в файле mind.json) ----------
   Душу персонажа и конституцию можно править и здесь; дневник пишет компьютер ночью — по разговорам и с компьютером, и с
   телефоном (реплики отсюда уходят ему очередью «dayturn»); большую задачу телефон передаёт компьютеру («taskreq»), ход и
   итог задач приходят сюда («task»). */
const MIND_F = "mind.json";
function mind() { let m = {}; try { m = JSON.parse(fileGet(MIND_F) || "{}") || {}; } catch (e) { } return Object.assign({ souls: {}, constitution: "", insights: null, diary: {}, tasks: {} }, m); }
function saveMind(m) { fileSave(MIND_F, JSON.stringify(m)); }
const qGet = (k) => { try { return JSON.parse(prefGet(k) || "[]") || []; } catch (e) { return []; } };
const qSet = (k, v) => prefSet(k, JSON.stringify(v.slice(-300)));
/* Журнал последних дней на самом телефоне (days.json, 14 дней): разговор сбрасывается после 8 часов тишины, а «что мы
   делали на этой неделе» должно отвечаться — коротко в подсказке (recentPrompt), подробно — инструментом recall. */
const DAYS_F = "days.json";
function dayLog() { try { return JSON.parse(fileGet(DAYS_F) || "[]") || []; } catch (e) { return []; } }
function dayLogAdd(you, bot, kind) {
  const now = Date.now(), l = dayLog().filter(x => now - x.ts < 14 * 864e5);
  l.push({ ts: now, who: persona().id, you: String(you || "").slice(0, 300), bot: String(bot || "").slice(0, 300), kind: kind || "" });
  fileSave(DAYS_F, JSON.stringify(l.slice(-400)));
}
const ddmm = (t) => { const d = new Date(t); return pad(d.getDate()) + "." + pad(d.getMonth() + 1); };
function recentPrompt() {
  const now = Date.now(), byDay = {};
  dayLog().filter(x => now - x.ts < 7 * 864e5 && x.you).forEach(x => { (byDay[ddmm(x.ts)] = byDay[ddmm(x.ts)] || []).push(x.you.replace(/\s+/g, " ").slice(0, 60)); });
  const lines = Object.entries(byDay).slice(-7).map(([d, l]) => `${d}: ${[...new Set(l)].slice(-6).join("; ")}`);
  const made = apps().slice(-5).reverse().map(x => `«${x.title}» (${ddmm(x.ts)})`);
  const tasks = Object.values(mind().tasks || {}).sort((a, b) => String(b.updated || "").localeCompare(String(a.updated || ""))).slice(0, 5)
    .map(t => `«${t.title}» — ${({ done: "готово", running: "делается", waiting: "ждёт ответа", failed: "не вышло" })[t.status] || t.status || ""}`);
  if (!lines.length && !made.length && !tasks.length) return "";
  let out = "ЧТО БЫЛО НЕДАВНО (ваши разговоры и дела за неделю; спросят «что мы делали», «где калькулятор» — отвечай по этому, подробнее — recall; открыть сделанное — open_made):";
  if (lines.length) out += "\nРазговоры по дням: " + lines.join(" | ").slice(0, 1400);
  if (made.length) out += "\nСделано на телефоне («Мой день» → «Сделанное»): " + made.join(", ");
  if (tasks.length) out += "\nБольшие задачи: " + tasks.join("; ");
  return out;
}
function recall(days, query) {
  const now = Date.now(), d = Math.max(1, Math.min(14, +days || 7)), w = String(query || "").toLowerCase().split(/\s+/).filter(x => x.length > 2).map(x => x.slice(0, 5));
  const hit = (x) => !w.length || w.some(k => (x.you + " " + x.bot).toLowerCase().includes(k));
  const l = dayLog().filter(x => now - x.ts < d * 864e5 && hit(x)).slice(-40)
    .map(x => { const t = new Date(x.ts); return `${ddmm(x.ts)} ${pad(t.getHours())}:${pad(t.getMinutes())} — Вы: ${x.you}${x.bot ? " — Ответ: " + x.bot.slice(0, 160) : ""}`; });
  const made = apps().filter(x => now - x.ts < d * 864e5).map(x => `«${x.title}» (${ddmm(x.ts)}) — откроет open_made`);
  return (l.length ? "Разговоры:\n" + l.join("\n") : "Разговоров за это время не нашлось.") + (made.length ? "\n\nСделано на телефоне: " + made.join(", ") : "");
}
function dayTurn(you, bot) {
  if (!syncCred() || !S.sync.on || !String(you || "").trim()) return;
  const q = qGet("dayq"); q.push({ id: "t" + Date.now().toString(36) + Math.random().toString(36).slice(2, 7), ts: Date.now(), who: persona().name, you: String(you).slice(0, 1500), bot: String(bot || "").slice(0, 2500) });
  qSet("dayq", q); syncSoon();
}
function taskToPc(title, goal) {
  if (!syncCred() || !S.sync.on) throw new Error("передать задачу компьютеру можно, когда включена синхронизация (Настройки → Ещё)");
  // cloud — компьютера нет на связи: задачу сделает облако Dewiar (исполнитель на сервере, см. core/cloudrunner.py)
  const q = qGet("taskq"); q.push({ id: "q" + Date.now().toString(36) + Math.random().toString(36).slice(2, 7), title: String(title || goal).slice(0, 80), goal: String(goal || title).slice(0, 4000), ts: Date.now(), cloud: true });
  qSet("taskq", q); syncSoon();
}
const pcOnline = () => (syncStatus.devices || []).some(x => x.pc && x.name !== "Облако Dewiar" && Date.now() / 1000 - (x.seen || 0) < 180);
const pcSeen = () => (syncStatus.devices || []).some(x => x.pc && Date.now() / 1000 - (x.seen || 0) < 14 * 86400);   // компьютер на связи (за 2 недели)
function mindPrompt() {
  const m = mind(), p = persona(), body = (t) => String(t || "").replace(/^\s*#[^\n]*\n+/, "").replace(/^_[^\n]*_\s*\n+/gm, "").trim();
  let out = "";
  const c = body(m.constitution).slice(0, 1800);
  if (c) out += "\n\nТВОЯ КОНСТИТУЦИЯ — принципы, которые ты соблюдаешь всегда, с любым характером и в любом настроении (их написал пользователь; ты их не меняешь):\n" + c;
  const sl = body((m.souls[p.name] || {}).text).slice(0, 1400);
  if (sl) out += "\n\nТВОЯ ДУША — автопортрет, который ты сам(а) пишешь по своему дневнику. Это ты; но характер и конституция важнее:\n" + sl;
  const ins = m.insights;
  if (ins && (ins.lines || []).length && (Date.now() - new Date(ins.day + "T12:00").getTime()) < 3 * 864e5)
    out += "\n\nТвои выводы после прошлого дня (ты записал их ночью в дневник" + (ins.title ? `, «${ins.title}»` : "") + "):\n" + ins.lines.map(x => "- " + x).join("\n") + "\nУчитывай их естественно; не пересказывай без повода.";
  return out;
}
/* Всё, что телефон синхронизирует, в виде {"вид:id": данные} — тот же формат, что snapshot() в core/sync.py.
   Отпечаток syncHash каждой записи сравнивается с отправленным: изменилась — уходит, пропала — уходит удалением. */
function syncSnapshot() {
  const out = {};
  JSON.parse(D.alarms() || "[]").forEach(x => { out["reminder:" + x.id] = Object.assign({ text: x.title || "", at: +x.at, kind: x.kind || "reminder", repeat: repToDict(x.repeat, x.at), paused: false },
    x.note ? { note: x.note } : {}); });                // note — id заметки с фото и файлами (то же, что note:<id>)
  notes().forEach(x => { out["note:" + x.id] = { title: x.title || "", text: x.text || "", folder: x.folder || "" };
    if (+x.time) Object.defineProperty(out["note:" + x.id], "t", { value: +x.time, enumerable: false }); });   // когда написана: старая копия не перебьёт новую
  money().forEach(x => { out["money:" + x.id] = { date: x.date, kind: x.kind, amount: +x.amount, currency: x.currency, category: x.category || "", note: x.note || "" }; });
  (S.memory || []).forEach(f => { out["memory:" + factId(f)] = { text: f }; });
  const ks = (syncSt() || {}).kinds || [];
  if (ks.includes("soul") || ks.includes("mind")) {
    const m = mind();
    if (ks.includes("soul")) for (const n in m.souls) if ((m.souls[n].text || "").trim()) out["soul:" + n] = { text: m.souls[n].text };
    if (ks.includes("mind") && m.constitution.trim()) out["mind:constitution"] = { text: m.constitution };
  }
  if (ks.includes("dayturn")) qGet("dayq").forEach(x => { out["dayturn:" + x.id] = { ts: x.ts, who: x.who, you: x.you, bot: x.bot }; });
  if (ks.includes("taskreq")) qGet("taskq").forEach(x => { out["taskreq:" + x.id] = { title: x.title, goal: x.goal, ts: x.ts, cloud: !!x.cloud }; });
  if (ks.includes("done")) doneList().forEach(x => { out["done:" + x.id] = { title: x.title, at: +x.at, src: x.src || "", rid: x.rid || "" }; });   // сделанные дела (core/done.py)
  if (ks.includes("persona")) myPersonas().forEach(x => { out["persona:" + x.id] = { name: x.name, gender: x.gender || "female", role: x.role || "", about: x.about || "", color: x.color || "", avatar: x.avatar || "" }; });   // свои персонажи — и на компьютер
  return out;
}
const TASK_RU = { running: "в работе", waiting: "ждёт ответа", paused: "на паузе", done: "готово", failed: "не вышло", sleeping: "ждёт времени", stopped: "остановлена" };
/* Применить чужую запись. -> false — её нет и не будет в нашем снимке (прошедшее разовое напоминание; дневник, задачи,
   выводы — их ведёт компьютер; очереди dayturn/taskreq): syncRun помечает её skip, чтобы не отправить обратно удалением. */
function syncApply(it) {
  const d = it.data || {}, del = it.deleted;
  if (it.kind === "persona") {                      // свой персонаж с компьютера или другого телефона
    const l = myPersonas().filter(x => x.id !== it.id);
    if (!del) { if (!d.name) return false; l.push({ id: it.id, name: String(d.name).slice(0, 24), gender: d.gender === "male" ? "male" : "female", role: String(d.role || "").slice(0, 60),
      about: String(d.about || "").slice(0, 4000), color: /^#[0-9a-f]{6}$/i.test(d.color || "") ? d.color : "#8A9BFF", avatar: /^data:image\//.test(d.avatar || "") ? d.avatar : "" }); }
    prefSet("my_personas", JSON.stringify(l.slice(-MY_MAX)));
    myPersonasApply();
    if (!PERSONAS.some(x => x.id === S.persona)) { S.persona = PERSONAS[0].id; saveS(); }
    applyPersona();
    return true;
  }
  if (it.kind === "reminder") {
    if (del) { D.alarmCancel(it.id); return true; }
    const exists = JSON.parse(D.alarms() || "[]").some(x => x.id === it.id);
    if (!d.repeat && +d.at < Date.now() - 300000 && !exists) return false;
    if (d.paused) { if (exists) D.alarmCancel(it.id); return true; }
    const was = exists ? JSON.parse(D.alarms() || "[]").find(x => x.id === it.id) : null, note = "note" in d ? d.note : was && was.note;
    D.alarmSet(JSON.stringify(Object.assign({ id: it.id, title: d.text || "Напоминание", at: +d.at, kind: ["alarm", "timer"].includes(d.kind) ? d.kind : "reminder", repeat: repFromDict(d.repeat) },
      note ? { note } : {})));
    if (d.kind === "timer") setTimeout(tmrShow, 0);
  } else if (it.kind === "note") {
    const old = notes().find(x => x.id === it.id);
    let n = notes().filter(x => x.id !== it.id);
    if (!del) n.push(Object.assign({ id: it.id, title: d.title || "Заметка", text: d.text || "", folder: d.folder || "", time: it.updated || Date.now() }, old && old.att ? { att: old.att } : {}));   // вложения — только на телефоне, не терять
    else if (old) (old.att || []).forEach(a => fileSave("natt-" + a.id, ""));
    fileSave("notes.json", JSON.stringify(n));
  } else if (it.kind === "money") {
    let m = money().filter(x => x.id !== it.id);
    if (!del && +d.amount > 0) m.push({ id: it.id, date: d.date, kind: d.kind, amount: +d.amount, currency: d.currency, category: d.category || "", note: d.note || "" });
    fileSave("money.json", JSON.stringify(m));
  } else if (it.kind === "memory") {
    S.memory = (S.memory || []).filter(f => factId(f) !== it.id);
    if (!del && d.text) S.memory.push(d.text);
    S.memory = S.memory.slice(-120); prefSet("settings", JSON.stringify(S));
  } else if (["soul", "mind", "diary", "task"].includes(it.kind)) {
    if (del) return false;                                   // душа, дневник и задачи удалением не стираются
    const m = mind();
    // душа и конституция идут в подсказку модели: из облака — только текст разумной длины без невидимых знаков (как sync._mind_text)
    if (it.kind === "soul") { const t = mindText(d); if (!t) return false; m.souls[it.id] = { text: t, u: it.updated }; }
    else if (it.kind === "mind" && it.id === "constitution") { const t = mindText(d); if (!t) return false; m.constitution = t; }
    else if (it.kind === "mind" && it.id === "insights") { m.insights = { day: d.day || "", title: d.title || "", lines: d.lines || [] }; saveMind(m); return false; }
    else if (it.kind === "mind" && it.id.startsWith("jobs")) {        // дела по расписанию компьютеров (jobs-<устройство>) — только показать
      m.jobs_by = Object.assign({}, m.jobs_by || {}, { [it.id]: del ? [] : (Array.isArray(d.items) ? d.items : []) });
      m.jobs = [].concat(...Object.values(m.jobs_by)).sort((a, b) => a.at - b.at); saveMind(m); return false; }
    else if (it.kind === "diary") { m.diary[it.id] = { text: String(d.text || ""), title: d.title || "", mood: d.mood || "" };
      const days = Object.keys(m.diary).sort().reverse(); days.slice(40).forEach(k => delete m.diary[k]); saveMind(m); return false; }
    else if (it.kind === "task") {
      const was = m.tasks[it.id]; m.tasks[it.id] = Object.assign({}, d, { u: it.updated });
      const ids = Object.keys(m.tasks).sort((a, b) => String(m.tasks[b].updated).localeCompare(String(m.tasks[a].updated))); ids.slice(20).forEach(k => delete m.tasks[k]);
      const fresh = (!was || was.status !== d.status) && ["done", "failed", "waiting"].includes(d.status) && Date.now() - (it.updated || 0) < 6 * 3600e3;
      if (fresh)
        D.notify("Задача: " + (d.title || ""), d.status === "done" ? "Готово. " + String(d.result || "").slice(0, 160) : d.status === "waiting" ? "Ждёт ответа: " + String(d.question || "").slice(0, 160) : "Не вышло: " + String(d.error || "").slice(0, 160));
      saveMind(m);
      if (fresh && d.status !== "waiting") setTimeout(() => { if (!busy && state === "idle") taskDoneCard(it.id); }, 300);
      return false;
    } else return false;
    saveMind(m);
  } else if (it.kind === "done") {
    const l = doneList().filter(x => x.id !== it.id);
    if (!del && d.title && +d.at) l.push({ id: it.id, title: String(d.title).slice(0, 120), at: +d.at, src: d.src || "", rid: d.rid || "" });
    saveDone(l);
    if ($("#sh-day.on") && dayTab === "rem") renderDay();
  } else if (it.kind === "dayturn" || it.kind === "taskreq") {
    return false;                                            // очередь для компьютера — не наше
  }
  return true;
}
/* Один обмен с облаком: отправить свои изменения и удаления, забрать чужие начиная с номера st.rev — порциями, пока
   сервер отвечает more (не больше 20 порций). Состояние (rev, отпечатки idx, id устройства) — в pref «sync»; сменился
   аккаунт или ключ (who) — начинаем с нуля. manual — ошибку показать человеку. */
async function syncRun(manual) {
  // Экзамен (песочница) — никакого обмена: снимок собирался из песочницы, а состояние обмена — настоящее, и записанное
  // экзаменом (память «в среду встреча с подрядчиком», заметки, расход 450, сделанные дела) уходило в аккаунт и
  // возвращалось людям как своё (отчёт №52, 14.10). Следы прошлых экзаменов убирает examCleanCheck (exam.js).
  if (SANDBOX) return;
  if ((S.tg || {}).linked && Date.now() - (S.tg.at || 0) > 600000) tgSync();      // ключ и персонаж для бота — раз в 10 минут
  if (syncBusy) return; const c = syncCred();
  if (!c || !S.sync.on) { syncStatus = Object.assign(syncStatus, { ok: null, error: "" }); return; }
  syncBusy = true;
  try {
    const who = syncHash(c.token);
    let st = syncSt();
    if (!st || st.who !== who) st = { rev: 0, idx: {}, who, device: (st && st.device) || "phone-" + Math.random().toString(36).slice(2, 12) };
    const snap = syncSnapshot(), now = Date.now(), changes = [], ek = e2eKey();
    if (ek) snap["mind:e2e"] = { on: true };                          // другим устройствам: шифрование включено — попросите ключ
    for (const k in snap) { const h = syncHash(snap[k]), e = st.idx[k], again = !!ek && (st.resealAll || (e && e.reseal));
      if (e && e.h === h && !e.del && !again) continue;
      const [kind, id] = [k.slice(0, k.indexOf(":")), k.slice(k.indexOf(":") + 1)];
      const data = ek && e2eSealable(kind, id, snap[k]) ? e2eSeal(ek, snap[k]) : snap[k];
      if (data.e2e && data.c.length > 290000) continue;               // зашифрованная больше, чем возьмёт сервер
      changes.push({ kind, id, data, updated: again ? now : (!e && snap[k].t) ? Math.min(now, snap[k].t) : now, _h: h }); }
    for (const k in st.idx) { const e = st.idx[k];
      if (!(k in snap) && !e.del && !e.skip) changes.push({ kind: k.slice(0, k.indexOf(":")), id: k.slice(k.indexOf(":") + 1), data: {}, updated: now, deleted: true, _h: null }); }
    const info = JSON.parse(D.info() || "{}");
    let body = { since: st.rev || 0, device: st.device, name: info.device || "Телефон", kinds: SYNC_KINDS, changes: changes.map(({ _h, ...x }) => x) }, got = 0, d = {};
    const hdr = { Authorization: "Bearer " + c.token, "Content-Type": "application/json" };
    if (c.link && c.link !== c.token) hdr["X-Sync-Link"] = c.link;
    for (let round = 0; round < 20; round++) {
      const r = await http("POST", c.base + "?p=/sync", { headers: hdr, body, timeout: 30000 });
      try { d = JSON.parse(r.body || "{}"); } catch (e) { d = {}; }
      if (r.status >= 400) throw new Error((d.error && d.error.message) || "облако ответило " + r.status);
      const srv = d.kinds || ["reminder", "note", "money", "memory"];
      const qdone = { dayturn: [], taskreq: [] };
      body.changes.forEach(x => { if (!srv.includes(x.kind)) return;
        const k = x.kind + ":" + x.id, src = changes.find(y => y.kind === x.kind && y.id === x.id);
        if (x.kind in qdone) { qdone[x.kind].push(x.id); st.idx[k] = { h: null, u: x.updated, skip: true }; return; }   // отдали компьютеру — у себя забываем
        st.idx[k] = { h: src ? src._h : null, u: x.updated, del: !!x.deleted }; });
      if (qdone.dayturn.length) qSet("dayq", qGet("dayq").filter(x => !qdone.dayturn.includes(x.id)));
      if (qdone.taskreq.length) qSet("taskq", qGet("taskq").filter(x => !qdone.taskreq.includes(x.id)));
      body.changes = [];
      if (srv.some(k => !(st.kinds || []).includes(k))) { st.kinds = srv; st.rev = 0; body.since = 0; prefSet("sync", JSON.stringify(st)); continue; }   // сервер узнал новое — история с начала
      for (let it of d.items || []) {
        const k = it.kind + ":" + it.id, e = st.idx[k] || {};
        if (it.dev === st.device && e.u === it.updated) continue;     // наша же правка вернулась — уже применена
        if (k === "mind:e2e") {                                         // метка: шифрование включено на другом устройстве
          if (!it.deleted && it.data && it.data.on) {
            if (syncKeyGet()) { if (!S.sync.e2e && !st.e2eOffHere) { S.sync.e2e = true; saveS(); st.resealAll = true; plog("info", "🔐 синхронизация зашифрована на другом устройстве — шифрую и здесь"); } }
            else st.e2eRemote = true;
          }
          st.idx[k] = { h: null, u: it.updated, skip: true }; continue;
        }
        let plainIn = false;
        if (e2eSealed(it.data)) {                                       // зашифровано на устройстве
          const kk = ek || anyKey();
          if (!kk) { st.locked = (st.locked || 0) + 1; st.e2eRemote = true; continue; }   // ключа нет — ждём его со своего устройства
          try { it = Object.assign({}, it, { data: e2eOpen(kk, it.data) }); } catch (x) { console.warn("sync: не расшифровалось", k); continue; }
        } else if (ek && !it.deleted && e2eSealable(it.kind, it.id, it.data || {})) plainIn = true;   // пришло открытым — перешифруем
        let okApply; try { okApply = syncApply(it); } catch (e2) { console.error("sync", it.kind, it.id, e2); continue; }
        if (okApply === false) { st.idx[k] = { h: null, u: it.updated, skip: true }; continue; }
        got++; st.idx[k] = it.deleted ? { h: null, u: it.updated, del: true } : Object.assign({ h: null, u: it.updated }, plainIn ? { reseal: true } : {});
      }
      st.rev = d.rev || st.rev; body.since = st.rev;
      if (!d.more) break;
    }
    // полученное запоминаем отпечатком «как оно легло у нас» — иначе следующий обмен отправил бы его обратно как своё
    if (got) { const s2 = syncSnapshot(); for (const k in st.idx) { const e = st.idx[k]; if (e.h === null && !e.del && !e.skip && k in s2) e.h = syncHash(s2[k]); } }
    if (ek) { delete st.resealAll; changes.forEach(x => { const e = st.idx[x.kind + ":" + x.id]; if (e) delete e.reseal; }); }
    prefSet("sync", JSON.stringify(st));
    if (st.e2eRemote && !syncKeyGet() && Date.now() - (window._keyAsk || 0) > 600000) { window._keyAsk = Date.now(); ownShare(["sync_key"]).catch(() => { }); }   // в облаке зашифрованное, а ключа нет — просим у своих (раз в 10 мин)
    syncStatus = { ok: true, at: Date.now(), error: "", devices: d.devices || [], counts: { sent: changes.length, got }, via: c.via };
    if (got && qGet("natt_in").length) setTimeout(() => nattIn().catch(() => { }), 0);    // пришла заметка, которую ждали фото с компьютера
    if (got && $("#sh-day") && $("#sh-day").classList.contains("on") && document.activeElement !== $("#tk-goal")) renderDay();
    if (got && $("#sh-soul") && $("#sh-soul").classList.contains("on") && soulTab === "diary") renderSoul();
  } catch (e) {
    syncStatus = Object.assign(syncStatus, { ok: false, at: Date.now(), error: e.message, via: c.via });
    if (manual) toast("Синхронизация: " + e.message);
  } finally { syncBusy = false; }
}
function syncSoon() { if (SANDBOX) return; clearTimeout(syncTimer); syncTimer = setTimeout(() => syncRun(false), 3000); }   // экзамен — без обмена   // несколько правок подряд — один обмен
/* Значок «Записать» на рабочем столе (CaptureWidget.java): включён по умолчанию; «Добавить на экран» — Android 8+ */
function widgetCard() {
  let w = {}; try { w = JSON.parse(D.widgetState ? D.widgetState() : "{}") || {}; } catch (e) { }
  if (w.on === undefined) return `<p class="hint" style="margin:0">Обновите приложение — в этой версии значка ещё нет.</p>`;
  return `<div class="sw"><div>Значок на рабочем столе<small class="hint" style="display:block;margin:2px 0 0">одно нажатие — Dewiar слушает и записывает мысль в «Идеи» или ставит напоминание («напомни завтра в 10…»), потом сам уходит</small></div>
    <label class="tg"><input type="checkbox" id="wg-on" ${w.on ? "checked" : ""}><i></i></label></div>`
    + (w.on ? (w.placed ? `<div class="res ok">На рабочем столе: ${w.placed}</div>`
      : w.pin ? `<button class="btn w" id="wg-pin" style="margin-top:8px">Добавить на рабочий стол</button><div class="res" id="wg-res"></div>`
      : `<p class="hint" style="margin:8px 0 0">Добавить: долгое нажатие на рабочем столе → «Виджеты» → Dewiar → «Записать».</p>`) : "");
}
function syncCard() {
  const c = syncCred(), s = syncStatus, t = s.at ? new Date(s.at) : null;
  if (!c) return `<p class="hint" style="margin-top:0">Напоминания, заметки, расходы и память — одинаковые на телефоне и компьютере. Нужен ключ Dewiar или вход аккаунтом dewiar.pro (Настройки → Мозг) — тот же, что на компьютере.</p>`;
  const devs = (s.devices || []).filter(x => x.name).map(x => esc(x.name));
  return `<div class="sw"><div>Телефон и компьютер — одно и то же<small class="hint" style="display:block;margin:2px 0 0">напоминания, заметки, расходы, память · ${esc(c.via)}</small></div>
    <label class="tg"><input type="checkbox" id="sy-on" ${S.sync.on ? "checked" : ""}><i></i></label></div>
    <div class="res ${s.ok === false ? "bad" : s.ok ? "ok" : ""}" id="sy-res">${s.ok === false ? esc(s.error) : t ? `Синхронизировано в ${pad(t.getHours())}:${pad(t.getMinutes())}` + (devs.length ? ` · ещё устройства: ${devs.join(", ")}` : "") : S.sync.on ? "первая синхронизация — в течение минуты" : "выключено"}</div>
    <div class="sw" style="margin-top:8px"><div>Шифровать на устройстве<small class="hint" style="display:block;margin:2px 0 0">${S.sync.e2e && syncKeyGet() ? "Включено: в облаке — только шифротекст, ключ — у ваших устройств." : e2eWaiting() ? "Ваши данные зашифрованы на другом устройстве — жду ключ от него (оно должно быть на связи)." : "Заметки, дела, деньги и память уходят в облако зашифрованными — сервер их не прочитает. Включите на одном устройстве — остальные получат ключ сами."}</small></div>
    <label class="tg"><input type="checkbox" id="sy-e2e" ${S.sync.e2e && syncKeyGet() ? "checked" : ""} ${S.sync.on ? "" : "disabled"}><i></i></label></div>
    <button class="btn w" id="sy-now" style="margin-top:6px">Синхронизировать сейчас</button>`;
}
let syncTick = 0;
setInterval(() => { if (!document.hidden && (!liteOn() || ++syncTick % 3 === 0)) syncRun(false); }, 60000);   // лёгкий режим — раз в 3 минуты
document.addEventListener("visibilitychange", () => { if (!document.hidden) { syncSoon(); doneInbox(); } });

/* ---------- Dewiar Облако (server/dwrapp/cloud.php): ключ dw-… или вход аккаунтом, заряд в талерах ----------
   Пути — параметром ?p=: /balance, /models, /usage, /topup, /netcfg, /report, /sync. Для модели base_url облака
   кончается на «?p=», и llmStream дописывает «/chat/completions» — выходит ?p=/chat/completions, как у OpenAI. */
const CLOUD_URL = window.DEWIAR_CLOUD_URL || "https://dewiar.pro/dwrapp/cloud.php";
let cloudInfo = null, cloudAt = 0;
const cloudBase = () => (S.llm.base_url || "").split("?")[0] || CLOUD_URL;
/* ---------- заявка на Dewiar из приложения и перенос кодом ----------
   joinSend — заявка без ключа (cloud.php ?p=/join); S.join {id, secret, base} хранит, чью заявку ждём; joinPoll — раз в
   минуту, пока приложение открыто, и при каждом открытии: одобрили — cloudConnect(ключ) и «Dewiar подключён».
   pairClaim — код из 6 цифр с другого устройства → тот же ключ (одни данные и заряд). */
async function joinSend(name, contact, note) {
  const base = CLOUD_URL.split("?")[0];
  const r = await http("POST", base + "?p=/join", { headers: { "Content-Type": "application/json" }, body: { name: String(name || "").trim(), contact: String(contact || "").trim(), note: String(note || "").trim(), device: "телефон" }, timeout: 20000 });
  let d = {}; try { d = JSON.parse(r.body || "{}"); } catch (e) { }
  if (r.status >= 400) throw new Error((d.error && d.error.message) || ("сервер ответил " + r.status));
  S.join = { id: d.id, secret: d.secret, base, at: Date.now() }; saveS();
  if (d.key) await joinDone(d.key, d);
  return d;
}
async function joinPoll(force) {
  const j = S.join; if (!j || !j.id || S.llm.base_url && !S.llm.trial && !force) return null;
  const r = await http("GET", j.base + "?p=/join&id=" + encodeURIComponent(j.id) + "&s=" + encodeURIComponent(j.secret), { timeout: 15000 });
  let d = {}; try { d = JSON.parse(r.body || "{}"); } catch (e) { }
  if (r.status === 404) { S.join = null; saveS(); return { status: "gone", text: "Заявка не нашлась — отправьте новую." }; }
  if (r.status >= 400) throw new Error((d.error && d.error.message) || ("сервер ответил " + r.status));
  if (d.status === "ok" && d.key) await joinDone(d.key, d);
  if (d.status === "no") { S.join = null; saveS(); }
  return d;
}
async function joinDone(key, d) {
  await cloudConnect(key, S.join && S.join.base);
  S.join = null; saveS();
  const msg = gfix("Готово — Dewiar подключён" + (d && d.reply ? ` («${d.reply}»)` : "") + ". Спросите меня что-нибудь!");
  showBot(msg); toast("Мозг подключён: модели Dewiar", 3500); say(msg);
}
async function pairClaim(code) {
  const r = await http("POST", CLOUD_URL.split("?")[0] + "?p=/pair/claim", { headers: { "Content-Type": "application/json" }, body: { code: String(code).replace(/\D/g, "") }, timeout: 15000 });
  let d = {}; try { d = JSON.parse(r.body || "{}"); } catch (e) { }
  if (r.status >= 400 || !d.key) throw new Error((d.error && d.error.message) || ("сервер ответил " + r.status));
  return d.key;
}
let joinTick = 0;
setInterval(() => { if (S.join && !document.hidden && !busy && (!liteOn() || ++joinTick % 3 === 0)) joinPoll(false).catch(() => {}); }, 60000);
document.addEventListener("visibilitychange", () => { if (!document.hidden && S.join) setTimeout(() => joinPoll(false).catch(() => {}), 1500); });
async function cloudGet(base, key, path) {
  const r = await http("GET", base.split("?")[0] + "?p=" + path, { headers: { Authorization: "Bearer " + key }, timeout: 10000 });
  let d = {}; try { d = JSON.parse(r.body || "{}"); } catch (e) { }
  if (r.status >= 400) throw new Error((d.error && d.error.message) || ("облако ответило " + r.status));
  return d;
}
async function cloudPost(path, body) {
  const r = await http("POST", cloudBase() + "?p=" + path, { headers: { Authorization: "Bearer " + S.llm.api_key, "Content-Type": "application/json" }, body, timeout: 40000 });
  let d = {}; try { d = JSON.parse(r.body || "{}"); } catch (e) { }
  if (r.status >= 400) throw new Error((d.error && d.error.message) || ("облако ответило " + r.status));
  return d;
}
const RQ = { new: "на проверке", done: "зачислено", rejected: "отклонено" };
function clReqs(list) {
  const el = $("#cl-reqs"); if (!el) return;
  el.innerHTML = (list || []).map(r => `<div class="rqi ${esc(r.status)}"><span>${new Date(r.ts * 1000).toLocaleDateString("ru-RU", { day: "numeric", month: "short" })}${r.amount ? " · " + (+r.amount || 0) + " тал." : ""}${r.reply ? " · «" + esc(r.reply) + "»" : ""}</span><b>${RQ[r.status] || esc(r.status)}${r.status === "done" ? " +" + (+r.credited || 0) : ""}</b></div>`).join("");
}
async function clPayLoad() {
  try { const r = await cloudGet(cloudBase(), S.llm.api_key, "/topup"), el = $("#cl-top");      // как пополнить: выделяется, ссылки открываются
    el.innerHTML = esc(r.text || "").replace(/(https?:\/\/[^\s<>"]+[^\s<>".,;:!?)»])/g, '<a href="#" data-ext="$1">$1</a>');
    $$("#cl-top a[data-ext]").forEach(x => x.onclick = (e) => { e.preventDefault(); D.openUrl(x.dataset.ext); }); clReqs(r.requests); }
  catch (e) { $("#cl-top").textContent = e.message; }
}
async function cloudUsage() {
  try {
    const u = await cloudGet(cloudBase(), S.llm.api_key, "/usage"), days = u.days || [], mx = Math.max(1, ...days.map(d => d.answers));
    if (!$("#cl-use") || !days.length) return;
    $("#cl-use").innerHTML = `<div class="uh"><span>Две недели</span><span>${u.answers} ${turnsWord(u.answers)}</span></div><div class="ub">${days.map(d => `<i class="${d.answers ? "on" : ""}" style="height:${Math.max(6, d.answers / mx * 100)}%"></i>`).join("")}</div>`;
  } catch (e) { }
}
async function cloudBalance(force) {
  if (!S.llm.cloud) return null;
  if (!force && cloudInfo && Date.now() - cloudAt < 20000) return cloudInfo;
  const prev = cloudInfo;
  cloudInfo = await cloudGet(cloudBase(), S.llm.api_key, "/balance"); cloudAt = Date.now();
  if (prev && ((cloudInfo.low && !prev.low) || (cloudInfo.empty && !prev.empty)))          // один раз, когда стало мало; site — общий счёт с сайтом (вход аккаунтом)
    D.notify(cloudInfo.site ? (cloudInfo.empty ? "На счёте dewiar.pro закончились ИИ-талеры" : `На счёте dewiar.pro: ${cloudInfo.balance_text || cloudInfo.balance + " тал."}`)
      : cloudInfo.empty ? "Заряд Dewiar Облака закончился" : `Заряд Dewiar Облака: ${cloudInfo.percent}%`, cloudInfo.site ? "Пополнить — в личном кабинете на сайте" : "Настройки → Мозг → Пополнить");
  if (cloudInfo.empty || cloudInfo.low) $("#who").classList.add("low"); else $("#who").classList.remove("low");
  return cloudInfo;
}
/* Ключ Dewiar удалили или перевыпустили на сайте, а вход в аккаунт есть — не мучаем человека ошибкой: думаем по аккаунту. */
const keyGone = (m) => /ключ dewiar не найден|invalid_api_key|ключ отозван/i.test(String(m || ""));
async function fixDeadKey(msg) {
  if (!S.llm.cloud || S.llm.account || !loggedIn() || (msg !== undefined && !keyGone(msg))) return false;
  const sv = S.account.services || {};
  try { await cloudConnect(S.account.token, (S.accCloud && S.accCloud.base) || siteUrl(sv.cloud || "dwrapp/cloud.php"), { account: true }); }
  catch (e) { return false; }
  toast("Ключ Dewiar больше не действует — думаю по аккаунту " + (S.account.login || "dewiar.pro"), 4500);
  syncSoon();
  return true;
}
function forgetKey() {                          // «Забыть ключ»: есть аккаунт — думаем по нему, нет — мозг не подключён
  if (loggedIn()) return fixDeadKey();
  S.llm = Object.assign({}, DEF.llm); cloudInfo = null; S.accCloud = null;
  if (S.stt.engine === "server" && /cloud\.php/.test(S.stt.url || "") && !S.stt.from_account) S.stt = Object.assign({}, DEF.stt);
  saveS(); $("#who").classList.remove("low");
  return Promise.resolve(true);
}
const cloudWho = () => S.llm.account ? "по аккаунту " + (S.account.login || "") : "ключ …" + S.llm.api_key.slice(-4);
const turnsWord = (n) => { const a = n % 10, b = n % 100; return a === 1 && b !== 11 ? "ответ" : a >= 2 && a <= 4 && (b < 12 || b > 14) ? "ответа" : "ответов"; };
function cloudFill(c) {
  if (!c || !$("#cl-card")) return;
  const pct = Math.max(0, Math.min(100, c.percent || 0));
  $("#cl-card").className = "card cloudc" + (c.empty ? " empty" : c.low ? " low" : "");
  const bal = c.balance_text || (c.balance != null ? String(c.balance).replace(".", ",") + " тал." : "");
  $("#cl-pct").textContent = c.site ? bal : pct + "%"; $("#cl-fill").style.width = Math.max(pct, c.empty ? 0 : 2) + "%";
  $("#cl-sub").textContent = c.site ? "счёт dewiar.pro · " + (S.account.login || c.label || "") : S.llm.account ? cloudWho() : (c.label ? c.label + " · " : "") + cloudWho();
  $("#cl-turns").textContent = c.site ? (c.frozen ? "Доступ к ИИ на сайте приостановлен — напишите администратору." : c.empty ? "На счёте dewiar.pro закончились ИИ-талеры — пополните в личном кабинете."
      : `Общий счёт с сайтом: ${bal}` + (c.turns ? ` — примерно на ${c.turns.toLocaleString("ru-RU")} ${turnsWord(c.turns)}` : ""))
    : c.frozen ? "Ключ приостановлен — напишите администратору." : c.empty ? "Заряд закончился — пополните, и ассистент снова будет отвечать."
    : `Хватит примерно на ${c.turns.toLocaleString("ru-RU")} ${turnsWord(c.turns)}` + (c.low ? " — скоро понадобится пополнить" : "");
  $("#cl-top").textContent = c.topup || "";
}
/* key — ключ dw-… или (account) токен входа на сайт: его регистр не трогаем. activate:false — только запомнить, своя модель остаётся. */
async function cloudConnect(key, base, opts = {}) {
  key = String(key || "").replace(/\s+/g, "").replace(/^[«"']|[»"']$/g, ""); base = (base || CLOUD_URL).split("?")[0];
  if (!opts.account) { key = key.toLowerCase(); if (!/^dw-/.test(key)) throw new Error("это не ключ Dewiar: он начинается с dw-. Вошли аккаунтом dewiar.pro — ключ не нужен"); }
  const info = await cloudGet(base, key, "/balance"), md = await cloudGet(base, key, "/models"), m = (md.data || [])[0];
  if (!m) throw new Error("в облаке пока нет доступных моделей — напишите администратору");
  if (opts.activate === false) { S.accCloud = { base, model: m.id, title: m.title || m.id, stt: !!md.stt, tts: !!md.tts }; saveS(); return info; }
  S.accCloud = opts.account ? { base, model: m.id, title: m.title || m.id, stt: !!md.stt, tts: !!md.tts } : null;
  S.llm = Object.assign({}, DEF.llm, { kind: "openai", name: "Dewiar Облако", base_url: base + "?p=", api_key: key, model: m.id, cloud: true, title: m.title || m.id,
    disable_thinking: false, account: !!opts.account, stt: !!md.stt, tts: !!md.tts });
  if (md.stt && !D.recognizer()) S.stt = { engine: "server", url: base + "?p=", key, model: "gigaam" };      // в телефоне нет своего распознавания
  saveS(); cloudInfo = info; cloudAt = Date.now();
  if (S.refPending) setTimeout(refPendingUse, 500);            // пришли по приглашению — код введётся сам
  return info;
}

/* ---------- приглашения друзей (cloud.php ?p=/ref, /ref/use) ----------
   У каждого свой код и ссылка …/download.php?ref=КОД. Друг вводит код (или открывает ссылку → dewiar://ref?c=КОД) в первые
   дни — ему подарок сразу, вам — когда он попользуется облаком несколько дней. Код из ссылки, пока облако не подключено, ждёт
   в S.refPending и вводится сам после подключения (refPendingUse). */
let refInfo = null;
const talers = (x) => String(Math.round((+x || 0) * 100) / 100).replace(".", ",");
async function refLoad() {
  try { refInfo = await cloudGet(cloudBase(), S.llm.api_key, "/ref"); } catch (e) { return; }
  const d = refInfo, sub = $("#ref-sub"), more = $("#ref-more"); if (!sub || !more) return;
  sub.textContent = (d.bonus > 0 ? `Вам +${talers(d.bonus)} тал. за каждого, кто попользуется ${d.days} дн.` : "Поделитесь Dewiar с друзьями")
    + (d.bonus_new > 0 ? `, другу — +${talers(d.bonus_new)} сразу` : "") + ".";
  const list = d.invited || [];
  // всё о приглашённых — в «Близкие» → «Рефералы»; здесь — код, счёт и дорога туда
  more.innerHTML = `<button class="btn w refgo" id="ref-open" style="margin-top:10px"><span>Рефералы — созвездие и друзья</span><small>Мой код <b>${esc(d.code)}</b>${list.length ? ` · приглашено ${list.length}` + (d.earned > 0 ? `, получено ${talers(d.earned)} тал.` : "") : ""}</small></button>`;
  $("#ref-open").onclick = () => openRefs();
  refFresh(d);
}
function refFresh(d) {                       // новая золотая звезда с прошлого раза — звук «нашёл» и поздравление (один раз)
  let seen = []; try { seen = JSON.parse(localStorage.getItem("dw_refnet_seen") || "[]"); } catch (e) { }
  const fresh = (d.invited || []).filter(x => x.paid && !seen.includes(x.name + "|" + (x.since || ""))).length;
  if (!fresh) return;
  try { localStorage.setItem("dw_refnet_seen", JSON.stringify((d.invited || []).filter(x => x.paid).map(x => x.name + "|" + (x.since || "")).slice(-200))); } catch (e) { }
  try { scanChime(); } catch (e) { } toast(fresh === 1 ? "Ещё один друг засчитан — звезда загорелась!" : `Засчитано новых друзей: ${fresh}`, 3500);
}

/* «Близкие» → «Рефералы»: большое созвездие, ссылка и код, кто позвал вас и кого позвали вы. Первый уровень (в обе стороны):
   уже в «Близких» — «Написать» и «Позвонить»; нет — «Позвать в Близкие» (cloud.php ?p=/close/ref): друг увидит «… зовёт вас»
   и согласится или откажется. rid — знак связи от сервера (подделать нельзя). refMap — rid → {pid} | {offered}. */
let refMap = {}, refSel = null;
async function refTab() {
  const box = $("#rf-body"); if (!box) return;
  if (!S.llm.cloud && !syncCred()) { box.innerHTML = `<div class="card"><b>Нужен Dewiar</b><p class="hint" style="margin:6px 0 10px">Приглашения работают через облако Dewiar: подключите мозг бесплатно или войдите аккаунтом dewiar.pro.</p><button class="btn p w" id="rf-brain">Подключить</button></div>`;
    $("#rf-brain").onclick = () => openSettings("brain"); return; }
  if (refInfo) refDraw(); else box.innerHTML = `<p class="hint" style="text-align:center;margin:30px 0">Загружаю созвездие…</p>`;
  try { refInfo = await cloudGet(cloudBase(), S.llm.api_key, "/ref"); } catch (e) { if (!refInfo) box.innerHTML = `<div class="card"><b>Не получилось</b><p class="hint" style="margin:4px 0 0">${esc(e.message)}</p></div>`; return; }
  const rids = (refInfo.invited || []).map(x => x.rid).concat(refInfo.by ? [refInfo.by.rid] : []).filter(Boolean);
  if (rids.length && syncCred()) { try { refMap = (await clReq("POST", "/close/refs", { rids })).map || {}; } catch (e) { } }
  if ($("#rf-body")) { refDraw(); refFresh(refInfo); }
}
function refPeer(x) {                         // друг в «Близких» — его имя оттуда и pid; иначе — как назвал сервер
  const m = (x && refMap[x.rid]) || {}, p = m.pid && clLoad().people.find(q => q.pid === m.pid);
  return { pid: p ? p.pid : "", name: p ? p.name : x.name, offered: !!m.offered, devs: p ? (p.devs || []).length : 0 };
}
/* состояние приглашённого: засчитан; не засчитан (тот же интернет или устройство — защита от накруток); ждёт его
   первого пополнения или нового месяца (лимит наград); пробует Dewiar N из M дней */
const refState = (x) => x.paid ? "засчитан ✓" : x.why === "same" ? "не засчитан: тот же интернет или устройство" : x.why === "topup" ? "засчитается после его первого пополнения"
  : x.why === "cap" ? "засчитается в следующем месяце — лимит наград" : `пользуется ${+x.days || 0} из ${+x.need || 0} дн.`;
function refRow(x, key, sub) {
  const q = refPeer(x), col = window.DewiarRefNet ? DewiarRefNet.color(x.name) : clCol(x.name);   // цвет — как у звезды в созвездии
  const act = q.pid ? `<button class="ib soft" data-w="${esc(q.pid)}" title="Написать"><svg viewBox="0 0 24 24"><path d="M4 5.5h16v11H9l-5 4z"/></svg></button>`
      + (q.devs && window.DewiarCall ? `<button class="ib soft" data-c="${esc(q.pid)}" title="Позвонить"><svg viewBox="0 0 24 24"><path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2"/></svg></button>` : "")
    : q.offered ? `<em class="rfw">ждём ответа</em>` : `<button class="btn rfo" data-o="${esc(x.rid)}">Позвать в Близкие</button>`;
  return `<div class="rfp ${refSel === key ? "cur" : ""}" data-k="${key}"><i class="clava" style="--c:${col}">${esc((q.name || "?")[0].toUpperCase())}</i>
    <span><b>${esc(q.name)}</b><small>${sub}</small></span>${act}</div>`;
}
function refDraw(calm) {
  const d = refInfo, box = $("#rf-body"); if (!d || !box) return;
  if (calm === undefined) calm = !!$("#rf-net .rn");              // уже нарисовано — звёзды не появляются заново
  const list = d.invited || [];
  const rules = (d.bonus > 0 ? `Вам +${talers(d.bonus)} тал. за каждого друга, который попользуется Dewiar ${d.days} дн.` : "Поделитесь Dewiar с друзьями.")
    + (d.bonus_new > 0 ? ` Другу — +${talers(d.bonus_new)} тал. сразу.` : "");
  box.innerHTML = `<div id="rf-net" class="rfnet"></div>
    <div class="card rfinv"><div class="row2 rfcb"><div style="flex:1;min-width:0"><small class="hint" style="margin:0">Ваш код</small><b class="rfcode">${esc(d.code)}</b></div>
      <button class="ib soft" id="rf-copy" title="Скопировать ссылку"><svg viewBox="0 0 24 24"><rect x="8.5" y="8.5" width="12" height="12" rx="2.5"/><path d="M15.5 8.5V6a2.5 2.5 0 0 0-2.5-2.5H6A2.5 2.5 0 0 0 3.5 6v7A2.5 2.5 0 0 0 6 15.5h2.5"/></svg></button></div>
      <button class="btn p w" id="rf-share" style="margin-top:10px">Пригласить</button>
      <p class="hint" style="margin:8px 0 0">${esc(rules)}</p></div>
    ${d.by ? `<h3>Вас пригласил</h3>${refRow(d.by, "by", "с этого приглашения вы в Dewiar")}` : ""}
    <h3>Приглашённые${list.length ? ` · ${list.length}` : ""}</h3>
    ${list.length ? list.map((x, i) => refRow(x, i, refState(x) + (x.sub ? ` · позвал ещё ${x.sub}` : ""))).join("")
      : `<div class="card"><b>Пока никого</b><p class="hint" style="margin:4px 0 0">${esc(refEmpty(d))}</p></div>`}
    ${list.length && d.opened > list.length ? `<p class="hint" style="margin:6px 4px 0">${esc(refOpened(d))}</p>` : ""}
    <p class="hint" style="margin:10px 4px">Переписываться и созваниваться можно с теми, кого пригласили вы, и с тем, кто пригласил вас, — когда оба согласны: «Позвать в Близкие».</p>
    ${d.can_use ? `<details class="more" style="margin:4px 2px 0"><summary>Есть код приглашения?</summary><div class="row2" style="margin-top:6px"><input id="ref-code" placeholder="6 знаков" autocapitalize="characters" style="flex:1;padding:12px 14px;border-radius:14px;border:0;background:var(--field)"><button class="btn p" id="ref-use">Ввести</button></div><div class="res" id="ref-res"></div></details>` : ""}`;
  if (window.DewiarRefNet) {
    const net = Object.assign({}, d, { invited: list.map(x => { const q = refPeer(x); return Object.assign({}, x, { label: q.name, close: q.pid }); }) });
    DewiarRefNet.render($("#rf-net"), net, { big: true, calm, me: (S.user_name || "Вы").slice(0, 7), by: d.by ? refPeer(d.by).name : "", sel: refSel,
      seenKey: "dw_refnet_seen_big", onPick: (i) => { refSel = refSel === i ? null : i; refDraw(true); const r = $(`.rfp[data-k="${i}"]`); if (r) r.scrollIntoView({ block: "nearest", behavior: "smooth" }); } });
  }
  $$(".rfp").forEach(r => r.onclick = (e) => { if (e.target.closest("button")) return; const k = r.dataset.k === "by" ? "by" : +r.dataset.k; refSel = refSel === k ? null : k; refDraw(true); });
  $$(".rfp [data-w]").forEach(b => b.onclick = () => { clTab = "close"; clCur = b.dataset.w; clRender(); });
  $$(".rfp [data-c]").forEach(b => b.onclick = () => clCall(b.dataset.c, false).catch(e => toast(e.message, 4000)));
  $$(".rfp [data-o]").forEach(b => b.onclick = async () => { b.disabled = true;
    try { clKeys(); if (!clLoad().me.pid) await clHello(); const r = await clReq("POST", "/close/ref", { rid: b.dataset.o });
      if (r.person) { clPeople(r); refMap[b.dataset.o] = { pid: r.person.pid }; toast(`${r.person.name} — в ваших близких: можно писать и звонить`, 3500); }
      else { refMap[b.dataset.o] = { offered: true }; toast("Позвали — когда друг согласится, он появится в «Близких»", 3500); }
      refDraw(true); } catch (e) { b.disabled = false; toast(e.message, 4000); } });
  $("#rf-share").onclick = () => refShare().catch(e => toast(e.message));
  $("#rf-copy").onclick = () => { D.copy(d.link); toast("Ссылка скопирована"); };
  if ($("#ref-use")) $("#ref-use").onclick = async () => { const r = $("#ref-res"); r.className = "res"; r.textContent = "проверяю…";
    try { const u = await refUse($("#ref-code").value); r.className = "res ok"; r.textContent = u.gift > 0 ? `Готово — вам +${talers(u.gift)} тал.` : "Готово — код принят."; cloudBalance(true).then(cloudFill).catch(() => { }); refInfo = null; setTimeout(refTab, 1500); }
    catch (e) { r.className = "res bad"; r.textContent = e.message; } };
}
/* «ссылку открыли» — сколько разных людей открыли страницу приглашения (сервер считает сам; превью мессенджеров — нет).
   Друг, который ставит Dewiar с того же телефона и входит, засчитывается без кода (cloud.php ref_auto). */
const refHow = (d) => `Кто поставит Dewiar с того же телефона и войдёт, появится здесь сам; ставят на компьютер или в другой сети — пусть введут код ${d.code}.`;
const refPeople = (n) => n + (n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20) ? " человека" : " человек");
const refOpened = (d) => `Ссылку открыли ${refPeople(+d.opened || 0)}. ` + refHow(d);
const refEmpty = (d) => d.opened > 0 ? `Ссылку открыли ${refPeople(+d.opened)}, но Dewiar по ней пока никто не подключил. ` + refHow(d)
  : "Нажмите «Пригласить» — ссылка с вашим кодом уйдёт в любой мессенджер. Друг, который поставит Dewiar по ней, появится здесь сам; каждый засчитанный — новая звезда.";
const refShareText = (d) => `Попробуй Dewiar — помощницу Лиру для телефона и компьютера: слышит по имени, отвечает голосом, помнит и напоминает. ${d.link}\nКод приглашения: ${d.code}`;
async function refShare() {
  const d = refInfo || await cloudGet(cloudBase(), S.llm.api_key, "/ref"); refInfo = d;
  D.share(refShareText(d));
}
async function refUse(code) {
  code = String(code || "").toUpperCase().replace(/[^A-Z0-9]/g, "");
  if (code.length < 4) throw new Error("Введите код из приглашения — 6 букв и цифр.");
  const u = await cloudPost("/ref/use", { code }); S.refPending = ""; saveS(); return u;
}
async function refPendingUse() {
  if (!S.refPending || !S.llm.cloud) return;
  try { const u = await refUse(S.refPending); if (u.gift > 0) { showBot(`Код приглашения принят — вам подарок +${talers(u.gift)} тал.`); } }
  catch (e) { if (!/сети|интернет|network/i.test(e.message)) { S.refPending = ""; saveS(); } }
}

/* ---------- аккаунт dewiar.pro: вход логином сайта, модели по аккаунту, Знания ----------
   Вход — dwrapp/login.php (выдаёт токен и список услуг services: cloud, stt…; приложение называет себя X-App-Id),
   Знания — synapbase/api_rag и api_scope. Пароль не хранится — только токен; 401 — вход устарел (accountExpired). */
const SITE = window.DEWIAR_SITE || "https://dewiar.pro", APP_ID = "dewiar-app";
const YANDEX_CID = "bd46169129964deea1f608cf45f7122a";   // приложение «Dewiar» на oauth.yandex.ru (iot:view, iot:control) — как в core/smarthome.py
const loggedIn = () => !!(S.account && S.account.token);
const siteHost = () => (S.account.server || SITE).replace(/^https?:\/\//, "");
function siteAddr(a) {
  a = String(a || "").trim().replace(/\/+$/, ""); if (!a) return SITE;
  if (!/^https?:\/\//.test(a)) a = "https://" + a;
  if (/^http:\/\//.test(a) && !/^http:\/\/(127\.|10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|localhost)/.test(a)) throw new Error("нужен адрес с https:// — иначе пароль ушёл бы открытым");
  return a;
}
const siteUrl = (p) => /^https?:/.test(p || "") ? p : (S.account.server || SITE) + "/" + String(p || "").replace(/^\/+/, "");
const siteHeaders = () => ({ "Content-Type": "application/json", "X-App-Id": APP_ID, Authorization: "Bearer " + S.account.token });
function accountExpired() {
  S.account = Object.assign({}, DEF.account, { server: S.account.server, login: S.account.login, problem: "Вход устарел — войдите в аккаунт заново (Настройки → Мозг)." });
  scopeCache = null; saveS();
}
function siteParse(r) {
  let d = {}; try { d = JSON.parse(r.body || "{}"); } catch (e) { if (r.status === 200) throw new Error("сайт ответил непонятно"); }
  if (r.status === 401) { accountExpired(); throw new Error("вход в аккаунт устарел — войдите заново: Настройки → Мозг"); }
  if (r.status === 429) throw new Error("слишком много вопросов подряд — сайт просит подождать");
  if (r.status !== 200) throw new Error((d.error && (d.error.message || d.error)) || "сайт ответил " + r.status);
  return d;
}
async function accountLogin(server, login, password) {
  server = siteAddr(server); login = String(login || "").trim();
  if (!login || !password) throw new Error("введите логин и пароль");
  applyProxy([server]);
  let r;
  try { r = await http("POST", server + "/dwrapp/login.php", { headers: { "Content-Type": "application/json", "X-App-Id": APP_ID }, body: { login, password }, timeout: 20000 }); }
  catch (e) { throw new Error(e.message + "." + blockedHint()); }
  let d = {}; try { d = JSON.parse(r.body || "{}"); } catch (e) { }
  if (r.status === 403 && /API-токен/.test(d.error || ""))     // старый login.php сайта не выдаёт токен сам — есть путь без него
    throw new Error("у этого аккаунта пока нет доступа для приложения (API-токена). Можно без него: «Мозг» → «Попробовать Dewiar» — "
      + "заявка, ключ придёт сам. Или попросите администратора сайта выдать токен");
  if (r.status !== 200 || !d.ok || !d.token)
    throw new Error(d.error || ({ 401: "неверный логин или пароль", 404: "на сайте нет входа для приложения (dwrapp/login.php)", 429: "слишком много попыток — подождите 15 минут" }[r.status] || "сайт ответил " + r.status));
  const sv = d.services || {};
  S.account = { server, login: (d.user && d.user.login) || login, token: d.token, user: d.user || {}, rag_url: d.rag_url || "/synapbase/api_rag", services: sv, problem: "", since: Date.now() };
  scopeCache = null; saveS();
  const out = { login: S.account.login, cloud: null, activated: false };
  trialOff();                                      // вошли — пробный разговор больше не нужен
  let ownKey = S.llm.cloud && !S.llm.account;
  const mine = !!S.llm.base_url && !S.llm.cloud;
  if (ownKey) {                                    // свой ключ dw- ещё действует? Удалённый на сайте — не держимся за него
    try { await cloudGet(cloudBase(), S.llm.api_key, "/balance"); } catch (e) { if (keyGone(e.message)) ownKey = false; }
  }
  // облако по аккаунту: свой рабочий ключ dw-… и своя модель остаются, облако — запасом. Адрес — из services, а если
  // сайт его не назвал (старый login.php) — обычный dwrapp/cloud.php; не ответило — ещё раз (первый запрос бывает долгим)
  for (let i = 0; i < 2 && !out.cloud; i++) {
    try { out.cloud = await cloudConnect(d.token, siteUrl(sv.cloud || "dwrapp/cloud.php"), { account: true, activate: !mine && !ownKey }); out.activated = !mine && !ownKey; }
    catch (e) { plog("warn", "облако по аккаунту: " + e.message); if (i) out.cloud = { error: e.message }; }
  }
  if (sv.stt && !D.recognizer() && S.stt.engine !== "server") S.stt = { engine: "server", url: siteUrl(sv.stt), key: d.token, model: "", from_account: true };
  saveS(); applyPersona();
  return out;
}
function accountLogout() {
  if (S.llm.cloud && S.llm.account) { S.llm = Object.assign({}, DEF.llm); cloudInfo = null; }
  if (S.stt.from_account) S.stt = Object.assign({}, DEF.stt);
  S.account = Object.assign({}, DEF.account, { server: S.account.server && S.account.server !== SITE ? S.account.server : "" });
  S.accCloud = null; scopeCache = null; saveS(); $("#who").classList.remove("low");
}
async function accountCheck() {                    // при запуске: вход ещё действует?
  if (!loggedIn()) return;
  try {
    const r = await http("GET", S.account.server + "/dwrapp/login.php", { headers: siteHeaders(), timeout: 15000 });
    if (r.status === 401) { accountExpired(); if (S.llm.account) toast("Вход в аккаунт dewiar.pro устарел — войдите заново", 4000); return; }
    if (r.status === 200) { const d = JSON.parse(r.body || "{}"); if (d.user) S.account.user = d.user; if (d.services) S.account.services = d.services; S.account.problem = ""; saveS(); }
  } catch (e) { }
  if (S.llm.cloud && !S.llm.account && loggedIn()) {        // свой ключ dw- удалили на сайте — сразу по аккаунту, без ошибок в разговоре
    try { await cloudGet(cloudBase(), S.llm.api_key, "/balance"); } catch (e) { await fixDeadKey(e.message); }
  }
}

/* базы сайта: свои папки, публичные библиотеки и их разделы */
let scopeCache = null;
const ragUrl = () => siteUrl(S.account.rag_url || "/synapbase/api_rag");
const scopeUrl = () => ragUrl().replace(/api_rag(\.php)?(?=$|\?)/, (m0, ext) => "api_scope" + (ext || ""));
async function siteScope(force) {
  if (!loggedIn()) throw new Error("нужен вход в аккаунт dewiar.pro: Настройки → Мозг");
  if (!force && scopeCache && Date.now() - scopeCache.t < 300000) return scopeCache.v;
  const d = siteParse(await http("POST", scopeUrl(), { headers: siteHeaders(), body: {}, timeout: 20000 }));
  const bases = [];
  for (const f of d.folders || []) bases.push({ kind: "folder", id: String(f.id), label: f.name || "Папка", docs: +f.doc_count || 0, group: "Мои папки" });
  for (const lib of d.libraries || []) {
    const lab = lib.label || "Публичная библиотека";
    bases.push({ kind: "library", id: String(lib.id), label: lab, docs: +lib.doc_count || 0, group: lab, whole: true });
    for (const f of lib.folders || []) bases.push({ kind: "library_folder", id: String(f.id), lib: String(lib.id), label: f.name || "Раздел", docs: +f.doc_count || 0, group: lab });
  }
  scopeCache = { t: Date.now(), v: { bases, docs: (d.docs || []).length } };
  return scopeCache.v;
}
const numId = (x) => /^\d+$/.test(String(x)) ? +x : x;
function ragOptions(b) {
  if (!b) return {};
  if (b.kind === "folder") return { bd_id: b.id };
  if (b.kind === "doc") return { doc_id: b.id };
  if (b.kind === "library") return { library_id: numId(b.id) };
  if (b.kind === "library_folder") { const o = { library_bd_id: b.id }; if (b.lib) o.library_id = numId(b.lib); return o; }
  return {};
}
function ragSources(meta, limit = 6) {
  const out = [];
  const walk = (x, depth) => {
    if (depth > 6 || out.length >= limit || !x) return;
    if (Array.isArray(x)) { x.forEach(v => walk(v, depth + 1)); return; }
    if (typeof x !== "object") return;
    const k = ["title", "doc_name", "document", "filename", "file_name", "name", "source"].find(k => typeof x[k] === "string" && x[k].trim());
    if (k && x[k].length < 200 && !out.includes(x[k].trim())) out.push(x[k].trim());
    Object.values(x).forEach(v => walk(v, depth + 1));
  };
  walk(meta, 0); return out;
}
function ragImages(d, limit = 4) {
  const out = [], base = (S.account.server || SITE).replace(/\/+$/, ""), rx = /\.(jpe?g|png|gif|webp)(\?|#|$)/i;
  const url = (p) => {
    p = String(p || "").trim().replace(/\\/g, "/"); if (!p) return "";
    const i = p.indexOf("user_uploads/"); if (i > 0) p = p.slice(i);
    if (/^https?:/.test(p)) return p;
    if (!/^(\/|user_uploads\/)/.test(p)) return "";
    return base + "/" + p.replace(/^\/+/, "");
  };
  const add = (u, title) => { if (u && !out.some(x => x.url === u)) out.push({ url: u, title: title || "" }); };
  for (const a of d.media_anchors || []) if (a && (a.media_type === "image" || rx.test(String(a.media_url || "")))) add(url(a.media_url || a.embed_url), a.title || a.description);
  const docs = (d.rag_meta || {}).retrieved_docs;
  for (const x of Array.isArray(docs) ? docs : []) {
    if (!x || typeof x !== "object") continue;
    const k = ["meta_path", "image_url", "media_url", "img_url", "image_path", "visual_path"].find(k => typeof x[k] === "string" && rx.test(x[k]));
    if (k) add(url(x[k]), x.name || x.doc_name);
  }
  return out.slice(0, limit);
}
async function ragRetrieve(question, b, hist) {
  const msgs = (hist || []).slice(-4).concat([{ role: "user", content: question }]);
  const d = siteParse(await http("POST", ragUrl(), { headers: siteHeaders(), timeout: 60000,
    body: { messages: msgs, stream: false, _sid: APP_ID, rag_options: Object.assign(ragOptions(b), { response_mode: "retrieval_only", history_depth: 4 }) } }));
  const ctx = String(d.ready_to_use_context || "").trim(), ans = (((d.choices || [])[0] || {}).message || {}).content || "";
  const found = !!ctx && !/ДАННЫЕ_НЕ_НАЙДЕНЫ/.test(ans);
  return { context: found ? ctx : "", sources: ragSources(d.rag_meta), images: ragImages(d), found };
}
const kbOf = (pid) => (S.kb || {})[pid || persona().id] || [];
/* У персонажа подключены базы сайта — ищем в них по вопросу и даём модели найденное (как на компьютере). */
async function personaKnowledge(text) {
  const bases = kbOf(), q = String(text || "").trim();
  if (!bases.length || !loggedIn() || q.length < 3) return "";
  const labels = bases.map(b => `«${b.label}»`).join(", ");
  showBot(`Ищу в ${labels}`, "wait");
  const hist = history.slice(-4).filter(m => (m.role === "user" || m.role === "assistant") && typeof m.content === "string").map(m => ({ role: m.role, content: m.content }));
  const got = await Promise.all(bases.map(b => ragRetrieve(q, b, hist).then(r => ({ b, r }), e => ({ b, err: e.message }))));
  const parts = [], empty = [], errs = [], srcs = []; let images = [];
  const per = Math.max(1500, Math.floor(7000 / bases.length));
  for (const { b, r, err } of got) {
    if (err) errs.push(`«${b.label}»: ${err}`);
    else if (r.found) { parts.push(`### Из «${b.label}»\n${r.context.slice(0, per)}`); images = images.concat(r.images); srcs.push(...r.sources); }
    else empty.push(`«${b.label}»`);
  }
  if (images.length) showImages(images);
  let out = "";
  if (parts.length) {
    out = "\n\nТВОЯ БАЗА ЗНАНИЙ (сайт Dewiar) — найдено по вопросу пользователя. Отвечай, опираясь на это: где уместно, приводи дословные цитаты "
      + "и называй источник (книга, глава и стих — или документ и страница). Не выдумывай того, чего в найденном нет; если найденное не отвечает "
      + "на вопрос — скажи об этом честно и бережно ответь от себя.\n\n" + parts.join("\n\n");
    if (srcs.length) out += "\n\nИсточники: " + [...new Set(srcs)].join("; ");
  } else if (empty.length) out = `\n\nВ твоей базе знаний (${empty.join(", ")}) по этому вопросу ничего не нашлось. Если отвечаешь от себя — так и скажи одной фразой.`;
  if (errs.length && !parts.length) out += `\n\nБаза знаний сейчас недоступна (${errs[0]}). Ответь от себя и коротко скажи, что база не ответила.`;
  return out;
}
function showImages(list) {
  showCard(`<div class="kbimgs">${list.map((x, i) => `<button class="kbimg" data-i="${i}" title="${esc(x.title)}"><img src="${esc(x.url)}" alt="" loading="lazy" onerror="this.parentNode.remove()"></button>`).join("")}</div>`);
  $$("#card .kbimg").forEach(b => b.onclick = () => D.openUrl(list[+b.dataset.i].url));
}
/* инструмент: вопрос к Знаниям сайта целиком (ответ пишет сайт) */
async function askKnowledge(question, baseName) {
  if (!loggedIn()) return "Нужен вход в аккаунт dewiar.pro (Настройки → Мозг → Аккаунт).";
  let b = null;
  if (baseName) {
    const want = baseName.toLowerCase().replace(/ё/g, "е").slice(0, 6);
    try { b = (await siteScope()).bases.find(x => x.label.toLowerCase().replace(/ё/g, "е").includes(want)) || null; } catch (e) { }
  }
  const body = { messages: [{ role: "user", content: question }], stream: false, _sid: APP_ID };
  if (b) body.rag_options = ragOptions(b);
  const d = siteParse(await http("POST", ragUrl(), { headers: siteHeaders(), body, timeout: 150000 }));
  const ans = ((((d.choices || [])[0] || {}).message || {}).content || "").trim();
  const imgs = ragImages(d); if (imgs.length) showImages(imgs);
  const src = ragSources(d.rag_meta);
  return (ans || "В Знаниях ничего не нашлось.") + (src.length ? "\n\nИсточники: " + src.join("; ") : "");
}

/* Знания персонажа — в листе «Кто отвечает» */
/* Редактор своего персонажа (лист #sh-pedit): облик из галереи — квадрат 384×384 по центру (JPEG ~40 КБ, хранится здесь же). */
const PE_COLORS = ["#9BD4FF", "#FF9BC8", "#B79BFF", "#7FE0B0", "#FFC46B", "#FF8A7A"];
let peAvatar = "";
function personaEditor(id) {
  const x = myPersonas().find(v => v.id === id) || { id: "", name: "", gender: "female", role: "", about: "", color: PE_COLORS[myPersonas().length % PE_COLORS.length], avatar: "" };
  peAvatar = x.avatar || "";
  $("#pe-h").textContent = x.id ? `Персонаж: ${x.name}` : "Свой персонаж";
  $("#pe-body").innerHTML = `<div class="card pe">
      <div class="pe-top"><label class="pe-ava" title="Облик: фото из галереи"><input type="file" id="pe-file" accept="image/*" hidden><span id="pe-img"></span><small>Облик</small></label>
        <div style="flex:1;min-width:0"><label class="f"><span>Имя — на него откликается</span><input id="pe-name" maxlength="24" value="${esc(x.name)}" placeholder="например, Меган" autocapitalize="words"></label>
        <div class="seg" id="pe-g"><button data-g="female" class="${x.gender === "female" ? "on" : ""}">Она</button><button data-g="male" class="${x.gender !== "female" ? "on" : ""}">Он</button></div></div></div>
      <label class="f"><span>Кто это — одной строкой</span><input id="pe-role" maxlength="60" value="${esc(x.role || "")}" placeholder="подруга, тренер по английскому, бизнес-советник"></label>
      <label class="f"><span>Характер и как говорит</span><textarea id="pe-about" rows="4" maxlength="1200" placeholder="Весёлая, отвечает коротко, любит шутить; разбирается в фитнесе и питании. Обращается на «ты».">${esc(x.about || "")}</textarea></label>
      <div class="pe-colors" id="pe-c">${PE_COLORS.map(c => `<button data-c="${c}" style="--c:${c}" class="${c === x.color ? "on" : ""}" aria-label="Цвет ${c}"></button>`).join("")}</div>
      <p class="hint" style="margin:6px 0 10px">Облик, имя и характер — на этом телефоне; с синхронизацией — и на компьютере. Голос — по полу: женский или мужской. Знания из своих документов — в листе «Кто отвечает» → «Знания».</p>
      <button class="btn p w" id="pe-save">Сохранить</button>
      ${x.id ? `<button class="btn w" id="pe-del" style="margin-top:8px">Удалить персонажа</button>` : ""}
      <div class="res" id="pe-res"></div></div>`;
  const showAva = () => { $("#pe-img").innerHTML = peAvatar ? `<img src="${peAvatar}" alt="">` : `<i>+</i>`; };
  showAva();
  $$("#pe-g button").forEach(b => b.onclick = () => $$("#pe-g button").forEach(z => z.classList.toggle("on", z === b)));
  $$("#pe-c button").forEach(b => b.onclick = () => $$("#pe-c button").forEach(z => z.classList.toggle("on", z === b)));
  $("#pe-file").onchange = async (ev) => {
    const f = ev.target.files && ev.target.files[0]; if (!f) return;
    try { peAvatar = await squareAvatar(f, 384); showAva(); } catch (e) { $("#pe-res").className = "res bad"; $("#pe-res").textContent = "Фото не открылось: " + e.message; }
  };
  $("#pe-save").onclick = () => {
    const name = $("#pe-name").value.trim().replace(/\s+/g, " "), r = $("#pe-res");
    if (!/^[A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё -]{1,23}$/.test(name)) { r.className = "res bad"; r.textContent = "Имя — буквами, от двух до 24: на него персонаж будет откликаться."; return; }
    const clash = PERSONAS.find(p => p.id !== x.id && p.name.toLowerCase().replace(/ё/g, "е") === name.toLowerCase().replace(/ё/g, "е"));
    if (clash) { r.className = "res bad"; r.textContent = `Имя «${clash.name}» уже занято — выберите другое.`; return; }
    const v = { id: x.id || "u" + Date.now().toString(36), name, gender: ($("#pe-g .on") || {}).dataset ? $("#pe-g .on").dataset.g : "female",
      role: $("#pe-role").value.trim(), about: $("#pe-about").value.trim(), color: ($("#pe-c .on") || { dataset: { c: PE_COLORS[0] } }).dataset.c, avatar: peAvatar };
    const l = myPersonas().filter(q => q.id !== v.id); l.push(v);
    try { prefSet("my_personas", JSON.stringify(l)); } catch (e) { r.className = "res bad"; r.textContent = "Не сохранилось: " + e.message; return; }
    myPersonasApply(); S.persona = v.id; saveS(); applyPersona(); closeSheets(); syncSoon();
    showYou(""); showBot(`${v.name} — с вами. Зовите по имени.`); say(gfix(`Привет! Это ${v.name}.`));
  };
  if ($("#pe-del")) $("#pe-del").onclick = () => {
    if (!confirm(`Удалить персонажа «${x.name}»? Разговор и заметки останутся.`)) return;
    prefSet("my_personas", JSON.stringify(myPersonas().filter(q => q.id !== x.id)));
    myPersonasApply(); if (S.persona === x.id) { S.persona = PERSONAS[0].id; saveS(); applyPersona(); }
    closeSheets(); toast(`«${x.name}» удалён`); syncSoon();
  };
  openSheet("#sh-pedit");
}
// фото из галереи → квадрат size×size по центру (как облик), JPEG
function squareAvatar(file, size) {
  return new Promise((ok, bad) => {
    const u = URL.createObjectURL(file), im = new Image();
    im.onload = () => {
      const s = Math.min(im.naturalWidth, im.naturalHeight); if (!s) { bad(new Error("пустая картинка")); return; }
      const c = document.createElement("canvas"); c.width = c.height = size;
      // лицо обычно в верхней трети портрета — для высоких снимков берём квадрат чуть выше центра
      const sx = (im.naturalWidth - s) / 2, sy = im.naturalHeight > im.naturalWidth ? Math.max(0, (im.naturalHeight - s) * 0.3) : (im.naturalHeight - s) / 2;
      c.getContext("2d").drawImage(im, sx, sy, s, s, 0, 0, size, size);
      URL.revokeObjectURL(u); ok(c.toDataURL("image/jpeg", 0.86));
    };
    im.onerror = () => { URL.revokeObjectURL(u); bad(new Error("не картинка")); };
    im.src = u;
  });
}
function renderKbPanel() {
  const box = $("#pkb"); if (!box) return;
  const p = persona(), mine = kbOf(p.id);
  if (!loggedIn()) {
    box.innerHTML = `<div class="card kbc"><b>Знания персонажа</b><p class="hint" style="margin:6px 0 10px">Персонажу можно дать базы с сайта dewiar.pro — свои папки или раздел публичной библиотеки, например «Библию». Тогда он отвечает по источнику, с цитатами.</p>
      <button class="btn w" id="kb-login">Войти в аккаунт dewiar.pro</button></div>`;
    $("#kb-login").onclick = () => { openSettings("brain"); setTimeout(() => { const t = $('.tile[data-w="account"]'); if (t) t.click(); }, 250); };
    return;
  }
  box.innerHTML = `<div class="card kbc"><div class="row2"><div style="flex:1;min-width:0"><b>Знания · ${esc(p.name)}</b><small class="hint" style="margin:2px 0 0;display:block">${mine.length ? "Перед ответом ищет здесь" : "Базы сайта не подключены"}</small></div>
    <button class="btn" id="kb-edit">${mine.length ? "Изменить" : "Подключить"}</button></div>
    ${mine.length ? `<div class="chips">${mine.map(b => `<span class="chip">${esc(b.label)}</span>`).join("")}</div>` : ""}<div id="kb-pick"></div></div>`;
  $("#kb-edit").onclick = () => kbPicker(p.id);
}
async function kbPicker(pid) {
  const el = $("#kb-pick"); el.innerHTML = `<p class="hint">загружаю базы сайта…</p>`;
  let bases;
  try { bases = (await siteScope(true)).bases; } catch (e) { el.innerHTML = `<div class="res bad">${esc(e.message)}</div>`; return; }
  if (!bases.length) { el.innerHTML = `<p class="hint">На сайте пока нет ваших папок и публичных библиотек. Загрузите документы на dewiar.pro — и они появятся здесь.</p>`; return; }
  const key = (b) => b.kind + ":" + b.id, sel = new Set(kbOf(pid).map(key));
  const groups = []; for (const b of bases) { let g = groups.find(x => x.name === b.group); if (!g) groups.push(g = { name: b.group, items: [] }); g.items.push(b); }
  el.innerHTML = groups.map(g => `<div class="kbg">${esc(g.name)}</div>` + g.items.map(b => `<label class="kbi"><input type="checkbox" value="${esc(key(b))}" ${sel.has(key(b)) ? "checked" : ""}>
    <span>${esc(b.whole ? "Вся библиотека" : b.label)}</span><small>${+b.docs || 0} док.</small></label>`).join("")).join("")
    + `<p class="hint" style="margin:8px 0 0">До 6 баз. Чем точнее раздел, тем точнее ответы.</p>`;
  $$("input", el).forEach(i => i.onchange = () => {
    const on = $$("input:checked", el).map(x => x.value);
    if (on.length > 6) { i.checked = false; toast("Не больше 6 баз у одного персонажа"); return; }
    S.kb = S.kb || {}; S.kb[pid] = bases.filter(b => on.includes(key(b))).map(b => { const o = { kind: b.kind, id: b.id, label: b.whole ? b.group : b.label }; if (b.lib) o.lib = b.lib; return o; });
    saveS();
    const chips = $(".kbc .chips"), mine = S.kb[pid];
    $(".kbc .hint").textContent = mine.length ? "Перед ответом ищет здесь" : "Базы сайта не подключены";
    $("#kb-edit").textContent = mine.length ? "Изменить" : "Подключить";
    if (chips) chips.innerHTML = mine.map(b => `<span class="chip">${esc(b.label)}</span>`).join("");
    else if (mine.length) $(".kbc .row2").insertAdjacentHTML("afterend", `<div class="chips">${mine.map(b => `<span class="chip">${esc(b.label)}</span>`).join("")}</div>`);
  });
}

/* ---------- Telegram: общий бот Dewiar (dwrapp/tg.php на сайте, вход — аккаунтом) ----------
   Подключение — как на компьютере: телефон регистрирует код (setLinkCode) и открывает ссылку t.me/<бот>?start=<код>;
   кто нажал «Старт» — тот владелец. Компьютера нет — бот отвечает сам моделями Dewiar (заметки, списки, напоминания;
   сделанное приходит на телефон синхронизацией): для этого телефон отдаёт ему ключ и персонажа (dewiarSync с
   device=phone — «компьютер на связи» он не отмечает). Есть компьютер — главный он, телефон его настройки не трогает. */
const tgOn = () => loggedIn() && !!(S.account.services || {}).tg;
/* Имя общего бота Dewiar — с сайта (dwrapp/tg.php?health, без входа): кнопка «Открыть бота» на телефоне. */
let tgBotCache = null;
async function tgBotName() {
  if (tgBotCache !== null) return tgBotCache;
  const r = await http("GET", (loggedIn() ? siteUrl("dwrapp/tg.php") : CLOUD_URL.replace(/cloud\.php.*$/, "tg.php")) + "?health", { timeout: 10000 });
  let d = {}; try { d = JSON.parse(r.body || "{}"); } catch (e) { }
  tgBotCache = String(d.bot || "").replace(/^@/, "");
  return tgBotCache;
}
async function tgCall(m, body) {
  const r = await http("POST", siteUrl((S.account.services || {}).tg || "dwrapp/tg.php") + "?m=" + m, { headers: siteHeaders(), body: body || {}, timeout: 20000 });
  let d = {}; try { d = JSON.parse(r.body || "{}"); } catch (e) { }
  if (r.status === 401) throw new Error("вход в аккаунт устарел — войдите заново: Настройки → Мозг");
  if (r.status >= 400 || d.ok === false) throw new Error(d.description || "бот ответил " + r.status);
  return d.result;
}
async function tgSync() {
  if (!tgOn() || !(S.tg || {}).linked) return;
  const p = persona(), off = -new Date().getTimezoneOffset(), tz = (off >= 0 ? "+" : "-") + pad(Math.floor(Math.abs(off) / 60)) + ":" + pad(Math.abs(off) % 60);
  const base = (S.accCloud && S.accCloud.base) || siteUrl((S.account.services || {}).cloud || "dwrapp/cloud.php");
  try {
    await tgCall("dewiarSync", { device: "phone", key: S.account.token, cloud: base.split("?")[0], model: (S.llm.cloud && S.llm.account ? S.llm.model : (S.accCloud || {}).model) || "",
      voice: p.voice_remote || "", tz, persona: { name: p.name, gender: p.gender || "male", character: p.character || "" }, offline: true, voice_reply: true, sync_on: !!S.sync.on });
    S.tg.at = Date.now(); saveS();
  } catch (e) { plog("warn", "Telegram: " + e.message); }
}
async function tgStatus() { const r = await tgCall("dewiarStatus"); S.tg = Object.assign({}, S.tg, { linked: !!r.linked, bot: r.bot || "", name: r.name || "" }); saveS(); return S.tg; }
async function tgLink(res) {
  const a = new Uint8Array(18); crypto.getRandomValues(a);
  const code = btoa(String.fromCharCode(...a)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");   // как secrets.token_urlsafe на компьютере
  const st = await tgStatus();
  if (!st.bot) throw new Error("на сайте не настроен бот Telegram");
  await tgCall("setLinkCode", { code });
  D.openUrl("https://t.me/" + st.bot + "?start=" + code);
  res.className = "res"; res.textContent = "В Telegram нажмите «Старт» — жду…";
  for (let i = 0; i < 60; i++) {                   // 3 минуты: человек переключился в Telegram и вернулся
    await new Promise(r => setTimeout(r, 3000));
    if ((await tgStatus().catch(() => ({}))).linked) { await tgSync(); return true; }
  }
  throw new Error("не дождался «Старт» в Telegram — попробуйте ещё раз");
}

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
      <div class="card"><b>Подключить бесплатно</b><p class="hint" style="margin:4px 0 8px">Без регистрации: напишите, как к вам обращаться и как связаться. Обычно всё подключается сразу; если заявку проверяют вручную — я сама скажу, когда готово. На счёте будет подарок, чтобы попробовать.</p>
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
      <p class="hint">Код из 6 цифр покажет ваше другое устройство, где Dewiar уже подключён: на компьютере — студия → «Мозг» → карточка «ИИ-баланс» → «Добавить устройство»; на телефоне — Настройки → «Мозг» → «Добавить устройство». Код живёт 10 минут. Данные и заряд будут общими. Думает сервер Dewiar — телефону не нужно ничего мощного.</p></div>`;
    $("#w-go").onclick = async () => { const r = $("#w-res"); r.className = "res"; r.textContent = "проверяю…";
      try { let k = $("#w-key").value.trim();
        if (/^\d[\d\s-]{4,8}\d$/.test(k)) { k = await pairClaim(k); }
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
    cloud: !!prof.cloud || /cloud\.php\?p=/.test(prof.base_url || ""), title: prof.title || "" });
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
async function checkUpdate(manual) {
  const r = $("#upd-res");
  try {
    const d = JSON.parse((await http("GET", UPD_URL, { timeout: 10000 })).body || "{}"), a = d.android;
    const newer = a && cmpVer(a.version, JSON.parse(D.info() || "{}").version || "0") > 0;
    if (newer) {
      const hands = typeof D.handsState === "function" && D.handsState() !== "none";     // стоит версия с «руками» — и обновляем её
      const url = UPD_URL.replace(/latest\.json$/, hands && a.hands_apk ? a.hands_apk : a.apk);
      updInfo = { version: a.version, url, sha: hands && a.hands_apk ? a.hands_sha256 : a.sha256 };
      if (r) {
        if (D.updateGet) updRender(`Есть Dewiar ${esc(a.version)}.<button class="btn w p" id="upd-go" style="margin-top:8px">Обновить</button>`);
        else { r.className = "res ok"; r.innerHTML = `Есть Dewiar ${esc(a.version)}. <a href="${esc(url)}">Скачать</a> — откройте файл и нажмите «Обновить».`; }
      } else D.notify("Новая версия Dewiar " + a.version, "Ещё → О приложении → Обновить");
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
new MutationObserver(() => document.body.classList.toggle("typing", $("#typebox").classList.contains("on")))
  .observe($("#typebox"), { attributes: true, attributeFilter: ["class"] });     // поле ввода открыто — сцена выше него (app.css)
$("#b-kb").onclick = () => { const b = $("#typebox"); b.classList.toggle("on"); if (b.classList.contains("on")) $("#typed").focus(); };
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
  $("#typed").value = ""; $("#typed").blur();
  ask(t || (att.some(a => a.kind === "image") ? "Посмотри, пожалуйста." : "Посмотри этот файл."), att.length ? { attach: att } : {});
};
$("#send").onclick = sendTyped;
$("#typed").onkeydown = (e) => { if (e.key === "Enter") sendTyped(); };
N.on("intent", (e) => handleIntent(e));
N.on("htmlview", (e) => { const f = htmlViewSave; htmlViewSave = null; if (e.save && f) f(); });
// вернулись из настроек Android после «Включить» — карточка «Управлять приложениями» показывает новое состояние
N.on("resume", () => { if (handsAsked && Date.now() - handsAsked < 10 * 60000 && $("#hands-card")) { $("#hands-card").innerHTML = handsCard(); wireHands(); } });
N.on("pause", () => { if (state === "listening") stopListen(), setState("idle"); });
/* Что пришло снаружи (MainActivity.handle): при запуске — через Dewiar.takeIntent(), когда страница уже открыта — событием
   intent. listen — кнопка помощника, type — ярлык «написать», say — текст из «Поделиться», import — файл настроек,
   link — ссылка dewiar:// (QR с настройками или адрес сервера). */
function handleIntent(e) {
  if (!e || !e.action) return;
  if (e.action === "listen") { closeSheets(); listen(); }
  else if (e.action === "say") {        // текст, которым поделилось другое приложение, — в поле ввода: отправляет сам человек
    closeSheets(); $("#typebox").classList.add("on"); $("#typed").value = String(e.text || "").slice(0, 4000); setTimeout(() => $("#typed").focus(), 300); }
  else if (e.action === "type") { closeSheets(); $("#typebox").classList.add("on"); setTimeout(() => $("#typed").focus(), 300); }
  else if (e.action === "images") {     // фото из «Поделиться» — во вложения; подпись пишет сам человек («напомни завтра в 10»)
    closeSheets(); attached = attached.concat((e.images || []).map((url, i) => ({ kind: "image", name: "фото " + (i + 1), url }))).slice(0, ATT_MAX);
    renderAtts(); $("#typebox").classList.add("on"); if (e.text && !$("#typed").value) $("#typed").value = String(e.text).slice(0, 2000);
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
  else if (e.action === "news") { closeSheets(); annCheck(true); }                   // уведомление объявления (CloseLive)
  else if (e.action === "close_call") {                                             // уведомление звонка близкого (CloseLive)
    clAutoAnswer = e.answer ? { pid: e.pid, until: Date.now() + 40000 } : null; clPoll(); }
  else if (e.action === "link" && /^dewiar:\/\/close/.test(e.url || "")) clAcceptLink(e.url);    // приглашение в «Близкие»
  else if (e.action === "link" && /^dewiar:\/\/ref/.test(e.url || "")) {            // приглашение друга: …/download.php?ref= → «Открыть в Dewiar»
    S.refPending = ((/[?&]c=([A-Za-z0-9]+)/.exec(e.url) || [])[1] || "").toUpperCase(); saveS();
    if (S.llm.cloud) refPendingUse();
    else showBot("Код приглашения сохранён. Подключите мозг бесплатно через Dewiar — и подарок придёт сам.");
  }
  else if (e.action === "link") { const m = /server=([^&]+)/.exec(e.url || ""); if (m) { openSettings("brain"); setTimeout(() => { const d = $(".brainalt"); if (d) d.open = true; $('.tile[data-w="pc"]').click(); $("#w-addr").value = decodeURIComponent(m[1]); }, 300); } }
}
/* ---------- «Близкие»: переписка между помощниками разных людей (как core/close.py; сервер — cloud.php ?p=/close/…) ----------
   Ключи устройства X25519 — в настройках приложения (prefs close_key); сообщения и файлы шифруются здесь же
   (closecrypto.js — тот же формат, что у компьютера); сервер видит только, кому и когда. Состояние и переписка — файл
   close.json. Входящие: раз в 15 с, пока приложение открыто и есть близкие (иначе — редко), и при каждом открытии.
   Пришло — на экране и вслух «Мама пишет: …», в фоне — уведомлением. Лист «Близкие» — список, переписка, приглашение
   QR-кодом и ссылкой; ссылка dewiar://close?t=… (с download.php?close=…) — «Принять приглашение от …?». */
const CLH_MAX = 300;
let CLS = null, clCur = "", clTimer = 0, clBusy = false, clFiles = [], clFast = false;
const DC = () => window.DewiarCrypto;
function clLoad() {
  if (CLS) return CLS;
  try { CLS = JSON.parse(fileGet("close.json") || "{}") || {}; } catch (e) { CLS = {}; }
  CLS = Object.assign({ me: {}, people: [], cursor: 0, hist: {}, unread: {}, invite: null, hello: 0 }, CLS);
  return CLS;
}
const clSave = () => fileSave("close.json", JSON.stringify(CLS));
function clKeys() {
  let k = null; try { k = JSON.parse(prefGet("close_key") || "null"); } catch (e) { }
  if (k && k.priv && k.pub && k.dev) return k;
  const kp = DC().keypair();
  k = { dev: "ph-" + Array.from(DC().randomBytes(5), x => x.toString(16).padStart(2, "0")).join(""), priv: DC().b64e(kp.priv), pub: DC().b64e(kp.pub) };
  prefSet("close_key", JSON.stringify(k)); return k;
}
const clToken = (s) => { s = String(s || "").trim(); const m = /[?&](?:close|t)=([A-Za-z0-9_-]+)/.exec(s); if (m) s = m[1]; s = s.replace(/[^A-Za-z0-9_-]/g, ""); return s.length >= 8 && s.length <= 64 ? s : ""; };
async function clReq(method, path, body, query) {
  const c = syncCred(); if (!c) throw new Error("«Близкие» работают через Dewiar: войдите аккаунтом dewiar.pro или подключите мозг Dewiar.");
  const h = { Authorization: "Bearer " + c.token, "Content-Type": "application/json" }; if (c.link && c.link !== c.token) h["X-Sync-Link"] = c.link;
  const r = await http(method, c.base + "?p=" + path + (query || ""), { headers: h, body: body == null ? null : body, timeout: 60000 });
  let d = {}; try { d = JSON.parse(r.body || "{}"); } catch (e) { }
  if (r.status >= 400) throw new Error((d.error && d.error.message) || ("облако ответило " + r.status));
  return d;
}
function clPeople(d) {
  const st = clLoad(); st.me = d.me || {}; st.people = d.people || []; st.offers = d.offers || [];
  const k = clKeys(), mine = (st.me.devs || []).map(x => x.dev).filter(x => x && x !== k.dev).sort(), fresh = mine.some(x => !(st.ownDevs || []).includes(x));
  st.ownDevs = mine;
  const ids = new Set(st.people.map(p => p.pid));                   // убрали из близких — с радара тоже, в обе стороны
  Object.keys(st.geo || {}).forEach(pid => { if (!ids.has(pid)) delete st.geo[pid]; });
  if (S.radar && (S.radar.to || []).some(pid => !ids.has(pid))) { S.radar.to = S.radar.to.filter(pid => ids.has(pid)); saveS(); }
  clSave(); clBadge();
  if (fresh) setTimeout(() => ownShare([...(!D.web && !(S.home.at || S.home.token) ? ["home"] : []), ...(e2eWaiting() ? ["sync_key"] : [])]).catch(() => { }), 0);   // ещё одно своё устройство — передать ему дом и ключ (или попросить)
}
/* Общее своих устройств, которое не должно лежать на сервере открытым, — ключ умного дома Яндекса. Настроили (или
   отключили) здесь — уходит конвертом на свои устройства (cloud.php ?p=/close/self), зашифрованным их ключами, как
   сообщения «Близких»; там берётся, если поменяли позже (at). Компьютер делает то же (core/close.py own_send). */
function homeSet(tok) { S.home.token = tok; S.home.at = Date.now(); homeInfo = null; saveS(); ownShare().catch(e => plog("info", "умный дом на свои устройства: " + e.message)); }
async function ownShare(want) {
  const at = D.web ? 0 : +S.home.at || (S.home.token ? 1 : 0);      // подключили до 0.6.10 — «давно»: свежее с компьютера важнее
  const sk = syncKeyGet();                                          // ключ шифрования синхронизации — тоже только своим
  const wants = (Array.isArray(want) ? want : want ? ["home"] : []).filter(w => !(w === "home" && at) && !(w === "sync_key" && sk));
  if (!syncCred() || !DC() || (!at && !sk && !wants.length)) return false;
  const k = clKeys(); if (!clLoad().me.pid || Date.now() - (CLS.hello || 0) > 600000) await clHello();
  const t = {}; ((CLS.me || {}).devs || []).forEach(d => { if (d.pub && d.dev && d.dev !== k.dev) t[d.dev] = DC().b64d(d.pub); });
  if (!Object.keys(t).length) return false;                         // других своих устройств пока нет
  t[k.dev] = DC().b64d(k.pub);
  const body = Object.assign(at ? { home: { token: S.home.token || "", at } } : {}, sk ? { sync_key: { k: sk.k, at: sk.at } } : {}, wants.length ? { want: wants } : {}, { ts: Date.now() });
  const env = DC().encryptFor(body, DC().b64d(k.priv), k.dev, t);
  await clReq("POST", "/close/self", { env }); return true;
}
/* Фото и файлы заметок с компьютера (core/close.py natt_share): конверт own {natt: {note, title, files: [{id, key, name,
   type, size, aid}]}}. Заметка (текст) приходит синхронизацией и может опоздать — задания ждут её в «natt_in» до недели.
   Файл: скачать из /close/file, открыть своим ключом, положить natt-<id> и в att заметки с pc (обратно не отправлять). */
function nattTake(natt) {
  if (!natt || !natt.note || !Array.isArray(natt.files)) return;
  const q = qGet("natt_in").filter(x => x.note !== natt.note);
  q.push({ id: "ni" + Date.now().toString(36) + Math.random().toString(36).slice(2, 7), note: String(natt.note), title: String(natt.title || ""), files: natt.files.slice(0, 12), ts: Date.now() });
  qSet("natt_in", q.slice(-40)); nattIn().catch(e => plog("info", "вложения заметки с компьютера: " + e.message));
}
var nattInBusy = false;
async function nattIn() {
  if (nattInBusy || !syncCred() || !DC()) return;
  nattInBusy = true;
  try {
    for (const job of qGet("natt_in")) {
      const all = notes(), n = all.find(x => x.id === job.note);
      if (!n) { if (Date.now() - job.ts > 7 * 864e5) qSet("natt_in", qGet("natt_in").filter(x => x.id !== job.id)); continue; }
      const have = new Set((n.att || []).map(a => a.aid).filter(Boolean)), got = [];
      for (const f of job.files) {
        if (!f.id || !f.key || have.has(f.aid)) continue;
        const d = await clReq("GET", "/close/file", null, "&b64=1&id=" + encodeURIComponent(f.id));
        const bytes = DC().unseal(DC().b64d(f.key), Uint8Array.from(atob(d.b64), c => c.charCodeAt(0)));
        const img = /^image\//.test(f.type || ""), id = "na" + Date.now().toString(36) + got.length + Math.random().toString(36).slice(2, 5);
        fileSave("natt-" + id, "data:" + (f.type || "application/octet-stream") + ";base64," + clStdB64(bytes));
        got.push({ id, name: String(f.name || "файл").slice(0, 120), type: img ? "image" : (f.type || "file"), size: bytes.length, pc: Date.now(), aid: f.aid || "" });
      }
      const all2 = notes(), x = all2.find(y => y.id === job.note);
      if (x && got.length) { x.att = (x.att || []).concat(got); fileSave("notes.json", JSON.stringify(all2)); }
      qSet("natt_in", qGet("natt_in").filter(y => y.id !== job.id));
      if (got.length) { plog("info", `📎 с компьютера к заметке «${clip(job.title, 40)}»: ${got.length}`); if ($("#sh-day.on")) renderDay(); }
    }
  } finally { nattInBusy = false; }
}
function ownApply(body) {
  if (body && body.natt) nattTake(body.natt);
  if (body && body.want && (S.home.at || S.home.token || syncKeyGet())) setTimeout(() => ownShare().catch(() => { }), 0);   // другое моё устройство просит
  const skb = body && body.sync_key;
  if (skb && typeof skb === "object" && syncKeyAdopt(skb.k, skb.at)) {
    plog("info", "🔐 ключ шифрования синхронизации получен со своего устройства");
    const st = syncSt(); if (st && !st.e2eOffHere) { S.sync.e2e = true; saveS(); }
    if (st) { st.rev = 0; st.resealAll = true; st.locked = 0; prefSet("sync", JSON.stringify(st)); }
    syncSoon();
  }
  const h = !D.web && body && body.home; if (!h || typeof h !== "object") return;   // браузеру ключ дома ни к чему: Яндекс не пускает запросы со страниц (CORS)
  const tok = String(h.token || ""), at = +h.at || 0;
  if (at <= (+S.home.at || 0) || (tok && !/^[\w.-]{20,}$/.test(tok)) || tok === (S.home.token || "")) return;
  S.home.token = tok; S.home.at = at; homeInfo = null; saveS();
  plog("info", "🏠 умный дом Яндекса " + (tok ? "подключён" : "отключён") + " с другого своего устройства");
}
async function clHello() {
  const k = clKeys();
  clPeople(await clReq("POST", "/close/hello", { dev: k.dev, pub: k.pub, devname: (clInfo().device || "Телефон"), name: (S.close && S.close.name) || S.user_name || "" }));
  CLS.hello = Date.now(); clSave(); return CLS;
}
const clInfo = () => { try { return JSON.parse(D.info() || "{}"); } catch (e) { return {}; } };
// «Люда», «Люде», «Людочке» → Людмила: уменьшительные имена близких (как NICKS в core/close.py)
const CL_NICK = { люд: "людмила", тан: "татьяна", саш: "александр", шур: "александр", жен: "евгений", миш: "михаил", лен: "елена", кат: "екатерина", маш: "мария", наташ: "наталья", натах: "наталья", оль: "ольга", свет: "светлана", вов: "владимир", дим: "дмитрий", кол: "николай", сереж: "сергей", серег: "сергей", андрюш: "андрей", ван: "иван", леш: "алексей", юл: "юлия", ир: "ирина", гал: "галина", вал: "валентина", над: "надежда", люб: "любовь", ан: "анна", пет: "петр", паш: "павел", кост: "константин", ген: "геннадий", тол: "анатолий", вит: "виктор", слав: "вячеслав", гош: "георгий", лид: "лидия", том: "тамара", нин: "нина", зин: "зинаида", рит: "маргарита", вик: "виктория" };
const CL_NICK_RX = new RegExp("^(андрюш|наташ|натах|сереж|серег|свет|кост|слав|люд|тан|саш|шур|жен|миш|лен|кат|маш|оль|вов|дим|кол|ван|леш|гал|вал|над|люб|пет|паш|ген|тол|вит|гош|лид|том|нин|зин|рит|вик|юл|ир|ан)(?:а|я|е|у|ю|ы|и|ой|ей|ою|ею|очк[а-я]*|ечк[а-я]*|оньк[а-я]*|еньк[а-я]*|ик[а-я]*|ок|ул[а-я]*|ус[а-я]*|юш[а-я]*|уш[а-я]*)?$");
const clNick = (w) => { const m = CL_NICK_RX.exec(w); return m ? CL_NICK[m[1]] : ""; };
/* Пишут или звонят человеку, которого нет в «Близких», а близкие есть — сказать об этом честно (экзамен 13.10: «Напиши
   Андрею» — «Готово, открыто в SMS», а что его нет в «Близких», человек так и не узнал). */
function notCloseHint(who) {
  try { const ps = clLoad().people || []; if (!who || !ps.length || /^[\d+\s()-]+$/.test(who) || clMatch(who, ps)) return "";
    return ` Скажи ещё одной фразой, что «${String(who).slice(0, 40)}» нет в «Близких» Dewiar: чтобы переписываться через помощников, его можно пригласить («Близкие» → «Пригласить»).`; }
  catch (e) { return ""; }
}
function clMatch(name, people, all) {                 // «Андрею», «маме», «Исаевой Людмиле» -> человек (по общему началу слов), как match_name в close.py
  const st = (w) => String(w || "").toLowerCase().replace(/ё/g, "е").replace(/[^а-яa-z]/g, "");
  const qs = String(name || "").split(/[\s,]+/).map(st).filter(Boolean); if (!qs.length) return null;
  const hit = (q, n) => { let k = 0; while (k < Math.min(n.length, q.length) && n[k] === q[k]) k++;
    const need = n.length <= 4 ? Math.min(n.length, 3) : Math.max(3, n.length - 2); return n === q ? k + 10 : k >= need ? k : 0; };
  let best = null, score = 0, tie = false;
  for (const p of people) {
    const ws = String(p.name || "").split(/\s+/).map(st).filter(Boolean); if (!ws.length) continue;
    // каждое слово запроса — к лучшему слову имени (порядок любой: «Исаевой Людмиле» = «Людмила Исаева»)
    const per = qs.map(q => Math.max(0, ...[q, clNick(q)].filter(Boolean).flatMap(v => ws.map(n => hit(v, n)).concat(hit(v, ws.join(""))))));
    const sc = per.reduce((a, b) => a + b, 0) - per.filter(x => !x).length * 4;
    if (!per.some(Boolean) || sc <= 0 || (all && per.some(x => !x))) continue;   // all — все слова запроса из имени
    if (sc > score) { best = p; score = sc; tie = false; } else if (sc === score && best !== p) tie = true;
  }
  return tie ? null : best;
}
function clPerson(who) {
  const st = clLoad(), p = st.people.find(x => x.pid === who) || clMatch(who, st.people);
  if (!p) throw new Error(`Не нашла «${who}» среди близких (сейчас: ${st.people.map(x => x.name).join(", ") || "пока никого"}). Добавить — «Близкие» → «Пригласить».`);
  return p;
}
function clTargets(p) {
  const t = {}, add = (devs) => (devs || []).forEach(d => { if (d.pub) t[d.dev] = DC().b64d(d.pub); });
  add(p.devs); add((CLS.me || {}).devs); const k = clKeys(); t[k.dev] = DC().b64d(k.pub); return t;
}
const clStdB64 = (u8) => { let s = ""; for (let i = 0; i < u8.length; i += 0x8000) s += String.fromCharCode.apply(null, u8.subarray(i, i + 0x8000)); return btoa(s); };
async function clSend(who, text, files, kind, extra) {
  clLoad(); if (!CLS.me.pid || Date.now() - (CLS.hello || 0) > 600000) await clHello();
  const p = clPerson(who), k = clKeys();
  if (!(p.devs || []).length) throw new Error(`У ${p.name} Dewiar ещё не открывался после приглашения — сообщение дойдёт, когда откроет.`);
  const fl = [];
  for (const f of files || []) {                // {name, type, bytes: Uint8Array}
    if (f.bytes.length > 10 * 1024 * 1024) throw new Error(`«${f.name}» больше 10 МБ — такие пока не отправить.`);
    const fk = DC().randomBytes(32), blob = DC().seal(fk, f.bytes);
    const d = await clReq("POST", "/close/file", clStdB64(blob), "&b64=1&to=" + encodeURIComponent(p.pid));
    fl.push({ id: d.id, name: f.name, size: f.bytes.length, type: f.type || "", key: DC().b64e(fk) });
  }
  const body = Object.assign({}, extra || {}, { t: String(text || "").trim(), ts: Date.now(), mid: Math.random().toString(36).slice(2, 12) + Date.now().toString(36), name: CLS.me.name || "" });
  if (fl.length) body.f = fl;
  if ((kind || "msg") === "msg" && !body.t && !fl.length) throw new Error("пустое сообщение");
  const env = DC().encryptFor(body, DC().b64d(k.priv), k.dev, clTargets(p));
  const d = await clReq("POST", "/close/send", { to: p.pid, env, kind: kind || "msg" });
  if ((kind || "msg") !== "msg") return d;
  const it = { mid: body.mid, ts: body.ts, out: true, t: body.t, f: fl };
  clAdd(p.pid, it); plog("info", `💌 близким: ${p.name} ← ${clip(body.t || "файл")}`); return Object.assign({ to: p.name }, it);
}
function clAdd(pid, it) {
  const st = clLoad(), h = st.hist[pid] = st.hist[pid] || [];
  if (h.some(x => x.mid === it.mid)) return false;
  h.push(it); h.sort((a, b) => a.ts - b.ts); if (h.length > CLH_MAX) h.splice(0, h.length - CLH_MAX); clSave(); return true;
}
/* Эмодзи и реакции в «Близких» (отзыв 13.10: 👍🤝✋😁😊😂😳🤔😱❤️ — отмечать сообщения и отправлять).
   Реакция — обычное сообщение {re: mid, e, t: e}: новые программы (здесь и core/close.py) ставят её значком на сообщение
   mid, а старые покажут просто «👍» — ничего не теряется. В истории: m.rx = {me, them}. */
const CL_EMO = ["👍", "🤝", "✋", "😁", "😊", "😂", "😳", "🤔", "😱", "❤️"];
function clReAt(pid, mid, who, e) {
  const st = clLoad(), m = (st.hist[pid] || []).find(x => x.mid === mid);
  if (!m) return false;
  m.rx = Object.assign({}, m.rx || {}); if (e) m.rx[who] = e; else delete m.rx[who];
  clSave(); return true;
}
async function clReact(pid, mid, e) {
  clLoad(); if (!CLS.me.pid || Date.now() - (CLS.hello || 0) > 600000) await clHello();
  const p = clPerson(pid), k = clKeys();
  if (!(p.devs || []).length) throw new Error(`У ${p.name} Dewiar ещё не открывался — реакция не дойдёт.`);
  const was = (((clLoad().hist[p.pid] || []).find(x => x.mid === mid) || {}).rx || {}).me || "";
  clReAt(p.pid, mid, "me", e);
  try {
    const body = { re: mid, e, t: e, ts: Date.now(), mid: Math.random().toString(36).slice(2, 12) + Date.now().toString(36), name: CLS.me.name || "" };
    await clReq("POST", "/close/send", { to: p.pid, env: DC().encryptFor(body, DC().b64d(k.priv), k.dev, clTargets(p)), kind: "msg" });
  } catch (x) { clReAt(p.pid, mid, "me", was); throw x; }
}
function clPubOf(peer, dev, out) {
  const st = clLoad(), who = out ? st.me : st.people.find(p => p.pid === peer), d = ((who || {}).devs || []).find(x => x.dev === dev);
  if (d) return DC().b64d(d.pub);
  const k = clKeys(); return out && dev === k.dev ? DC().b64d(k.pub) : null;
}
async function clPoll() {
  if (clBusy || !syncCred() || !DC()) return 0;
  clBusy = true;
  try {
    const st = clLoad(), k = clKeys();
    if (!st.me.pid || Date.now() - (st.hello || 0) > 3600000) await clHello();   // раз в час: новые близкие и «зовут в Близкие»
    const d = await clReq("GET", "/close/inbox", null, "&after=" + (+st.cursor || 0) + "&geo=1");
    let got = 0, refreshed = false;
    for (const it of d.items || []) {
      if (it.kind === "ring") continue;                    // признак звонка — для службы CloseLive; сам звонок — в «sig»
      const env = it.env || {};
      let pub = clPubOf(it.peer, env.fd, it.out);
      if (!pub && !refreshed) { refreshed = true; try { await clHello(); } catch (e) { } pub = clPubOf(it.peer, env.fd, it.out); }
      if (!pub) continue;
      let body; try { body = DC().decryptFrom(env, DC().b64d(k.priv), k.dev, pub); } catch (e) { plog("warn", "близкие: не открылось — " + e.message); continue; }
      if (it.kind === "sig") { try { clSig(it.peer, it.name, body.s || {}); } catch (e) { } continue; }
      if (it.kind === "geo") { if (!it.out) radTake(it.peer, it.name || "", body.g); continue; }   // место для радара «Рядом»
      if (it.kind === "own") { if (it.out && env.fd !== k.dev) ownApply(body); continue; }   // от своего же устройства
      if (body.re) {                                        // реакция на сообщение — значком на нём, не новым сообщением
        const e = CL_EMO.includes(body.e) ? body.e : String(body.e || "").slice(0, 8);
        if (clReAt(it.peer, String(body.re), it.out ? "me" : "them", e) && !it.out) {
          if (clCur === it.peer && $("#sh-close").classList.contains("on")) clRender();
          else if (!document.hidden && e) toast(`${it.name || "Близкий"}: ${e} на ваше сообщение`, 2600);
        }
        continue;
      }
      const m = { mid: body.mid || String(it.id), ts: +body.ts || it.ts * 1000, out: !!it.out, t: String(body.t || "").slice(0, 20000), f: (body.f || []).filter(x => x && typeof x === "object").slice(0, 10), ...(body.wave ? { wave: 1 } : {}) };
      if (!clAdd(it.peer, m) || m.out) continue;
      got++;
      if (!(clCur === it.peer && $("#sh-close").classList.contains("on"))) { st.unread[it.peer] = (st.unread[it.peer] || 0) + 1; clSave(); }
      clTell(it.name || "Близкий", m, it.peer);
    }
    st.cursor = Math.max(+st.cursor || 0, +d.last || 0); clSave(); clBadge(); clWatch();
    if (got && $("#sh-close").classList.contains("on")) clRender();
    return got;
  } catch (e) { plog("info", "близкие: " + e.message); return 0; }
  finally { clBusy = false; }
}
function clTell(name, m, pid) {
  if (m.wave) { radWaveIn(pid, name); return; }               // 👋 с радара — волны, «… машет вам» и голос
  const what = (m.t || "") + ((m.f || []).length ? (m.t ? " " : "") + ((m.f.length === 1) ? `Файл «${m.f[0].name}».` : `Файлов: ${m.f.length}.`) : "");
  const line = `${name} пишет: ${what}`.trim();
  if (document.hidden || busy || state !== "idle") { D.notify(`💌 ${name}`, what || "сообщение"); if (document.hidden) return; }
  if (!busy && state === "idle") { showBot(line); if (!(S.close && S.close.speak === false)) say(line); }
}
function clBadge() {
  const st = clLoad(), n = Object.values(st.unread || {}).reduce((a, x) => a + (+x || 0), 0) + (st.offers || []).length;   // и «зовут в Близкие»
  const b = $("#b-close"); if (b) b.classList.toggle("has", n > 0);
}
/* фоновая проверка, пока приложение закрыто (CloseWatch.java): только если есть близкие; номер прочитанного — чтобы не
   напоминать о том, что уже показано здесь */
function clWatch() {
  if (!D.closeWatch) return;
  const c = syncCred(), st = clLoad(), j = c && st.people.length ? JSON.stringify({ base: c.base, token: c.token, link: c.link && c.link !== c.token ? c.link : "", cursor: +st.cursor || 0 }) : "";
  if (j !== clWatch.last) { clWatch.last = j; D.closeWatch(j); }
  const live = !!j && clLiveOn();                         // «на связи» — служба CloseLive: сообщения и звонки сразу
  if (D.closeLive && live !== clWatch.live) { clWatch.live = live; D.closeLive(live); }
}
const clActive = () => { const st = clLoad(); return st.people.length > 0 || (st.invite && Date.now() / 1000 < (st.invite.expires || 0)); };
function clSchedule() {
  clearTimeout(clTimer);
  clTimer = setTimeout(async () => { if (!document.hidden || clFast) await clPoll(); clSchedule(); }, clFast ? 1200 : clActive() ? 6000 : 600000);   // во время звонка — и в фоне: отбой и «ответили» не должны теряться
}
function clPrompt() {
  const st = clLoad(); if (!st.people.length) return "";
  return "БЛИЗКИЕ (переписка с их помощниками Dewiar, сообщения шифруются): " + st.people.map(p => p.name).join(", ")
    + ". Кто-то из них (в любой форме имени: «Люде» = Людмила, «Исаевой Людмиле» = Людмила Исаева) — СНАЧАЛА через Dewiar: «напиши/передай/скажи» — close_send (дойдёт в его Dewiar, он услышит вслух), «позвони» — close_call (video true — «по видео»); «что мне писали», «что ответила мама» — close_read; «где мама?», «далеко ли Андрей?» — close_where (по радару «Рядом»; адресов не называй); «помаши маме» — close_wave. Только людям НЕ из этого списка — телефон (call) и мессенджеры.";
}
function clRecent(who, n = 8) {
  const st = clLoad(), ps = who ? [clPerson(who)] : st.people, out = [];
  for (const p of ps) { (st.hist[p.pid] || []).slice(-n).forEach(m => out.push([m.ts, `${new Date(m.ts).toLocaleString("ru-RU", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })} ${m.out ? "вы → " + p.name : p.name}: ${m.t || ""}${(m.f || []).length ? " [файлы: " + m.f.map(x => x.name).join(", ") + "]" : ""}${m.rx && (m.rx.me || m.rx.them) ? ` [реакции: ${[m.rx.them && p.name + " " + m.rx.them, m.rx.me && "вы " + m.rx.me].filter(Boolean).join(", ")}]` : ""}`])); delete st.unread[p.pid]; }
  clSave(); clBadge(); out.sort((a, b) => a[0] - b[0]);
  return out.slice(-n * 2).map(x => x[1]).join("\n") || "Сообщений пока нет.";
}
async function clInvite(renew) {
  const d = await clReq("POST", "/close/invite", { renew: !!renew });
  clLoad().invite = { link: d.link, expires: d.expires }; clSave(); clSchedule(); return d;
}
async function clAcceptLink(link) {
  const t = clToken(link); if (!t) { showBot("Это не ссылка-приглашение в «Близкие».", "err"); return; }
  if (!syncCred()) { S.closePending = t; saveS(); showBot("Приглашение в «Близкие» сохранено. Подключите Dewiar (Настройки → Мозг → «Подключить бесплатно») — и я его приму.", ""); return; }
  try {
    const who = await clReq("GET", "/close/peek", null, "&t=" + encodeURIComponent(t));
    if (!confirm(`Принять приглашение в «Близкие» от «${who.name}»? Ваши помощники смогут передавать друг другу сообщения.`)) return;
    clKeys(); if (!clLoad().me.pid) await clHello();
    const d = await clReq("POST", "/close/accept", { t }); clPeople(d); S.closePending = ""; saveS();
    const p = d.person || {}; showBot(`Готово — ${p.name || who.name} в ваших близких. Пишите в «Близких» (сердечко вверху) или скажите мне: «напиши» — и имя.`); say("Готово!");
    clSchedule(); setTimeout(clPoll, 1500);
  } catch (e) { showBot("Приглашение не принято: " + e.message, "err"); }
}

/* звонки (assets/call.js): сигналы — зашифрованные сообщения kind sig ({s: сигнал}); во время звонка опрос — раз в секунду */
function clTransport(p) {
  return {
    send: (sig) => clSend(p.pid, "", [], "sig", { s: sig }),
    ice: async () => (await clReq("GET", "/close/ice")).iceServers || [],
    fast: (on) => { clFast = !!on; clSchedule(); try { D.keepScreen(!!on || state !== "idle"); } catch (e) { } },   // звонок — экран не гаснет
    done: (info) => {
      const t = info.secs ? `📞 Звонок · ${String(Math.floor(info.secs / 60)).padStart(2, "0")}:${String(info.secs % 60).padStart(2, "0")}` : "📞 " + (info.reason || "Звонок");
      clAdd(p.pid, { mid: "call" + Date.now(), ts: Date.now(), out: info.role === "caller", t, call: true });
      if (info.notify && info.role === "callee" && document.hidden) D.notify("📞 " + p.name, info.reason || "Пропущенный звонок");
      if ($("#sh-close").classList.contains("on")) clRender();
    },
  };
}
async function clCall(who, video) {
  if (!window.DewiarCall) throw new Error("звонки здесь не поддерживаются");
  const p = clPerson(who);
  if (!(p.devs || []).length) throw new Error(`У ${p.name} Dewiar ещё не открывался — позвонить пока нельзя.`);
  if (!(await needPerm("android.permission.RECORD_AUDIO"))) throw new Error("нужен доступ к микрофону");
  if (video && !(await needPerm("android.permission.CAMERA"))) video = false;
  clCallPrep();
  closeSheets();
  // открытый признак «звонят» (без содержимого): у близкого с закрытым приложением служба CloseLive зазвонит сразу
  clReq("POST", "/close/send", { to: p.pid, kind: "ring", env: { v: 0, video: !!video } }).catch(() => { });
  await DewiarCall.start({ role: "caller", peer: { pid: p.pid, name: p.name, color: clCol(p.pid) }, video: !!video, transport: clTransport(p) });
  return p;
}
let clAutoAnswer = null;
function clCallPrep() { try { stopListen(); } catch (e) { } try { D.radioPause(); } catch (e) { } try { D.stopSpeak(); } catch (e) { } }
function clSig(peer, name, s) {
  if (!window.DewiarCall) return;
  const p = clLoad().people.find(x => x.pid === peer); if (!p) return;
  DewiarCall.signal(peer, s, {
    ring: async (r) => {
      if (document.hidden) D.notify("📞 " + p.name + (r.video ? " — видеозвонок" : " звонит"), "Откройте Dewiar, чтобы ответить");
      clCallPrep(); closeSheets();
      if (r.video && !D.has("android.permission.CAMERA")) await needPerm("android.permission.CAMERA");
      if (!D.has("android.permission.RECORD_AUDIO")) await needPerm("android.permission.RECORD_AUDIO");
      await DewiarCall.start({ role: "callee", peer: { pid: p.pid, name: p.name, color: clCol(p.pid) }, video: !!r.video, call: r.call, offer: r.sdp, transport: clTransport(p) });
      // нажали «Ответить» на уведомлении звонка (приложение было закрыто) — отвечаем сразу
      if (clAutoAnswer && clAutoAnswer.pid === p.pid && Date.now() < clAutoAnswer.until && DewiarCall.accept) { clAutoAnswer = null; DewiarCall.accept(); }
    },
    busy: (r) => clSend(peer, "", [], "sig", { s: { type: "busy", call: r.call } }).catch(() => { }),
  });
}
/* сканер кодов (assets/codes.js): QR, Aztec и печать Dewiar. Нашёлся код — фирменный звук, дальше по смыслу:
   приглашение в «Близкие» или от друга, ссылка dewiar:// (настройки с компьютера), обычная ссылка — открыть, текст — показать. */
function scanChime() {                            // «нашёл!»: искра вверх — две стеклянные ноты и мерцание
  try {
    const AC = window.AudioContext || window.webkitAudioContext, c = new AC(), t0 = c.currentTime + 0.02;
    const note = (f, t, d, v, type) => { const o = c.createOscillator(), g = c.createGain(); o.type = type || "sine"; o.frequency.setValueAtTime(f, t);
      o.frequency.exponentialRampToValueAtTime(f * 1.012, t + d); g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(v, t + 0.008);
      g.gain.exponentialRampToValueAtTime(0.0005, t + d); o.connect(g); g.connect(c.destination); o.start(t); o.stop(t + d + 0.02); };
    const sw = c.createOscillator(), sg = c.createGain(); sw.type = "triangle"; sw.frequency.setValueAtTime(600, t0); sw.frequency.exponentialRampToValueAtTime(2400, t0 + 0.09);
    sg.gain.setValueAtTime(0.0001, t0); sg.gain.exponentialRampToValueAtTime(0.05, t0 + 0.03); sg.gain.exponentialRampToValueAtTime(0.0001, t0 + 0.1); sw.connect(sg); sg.connect(c.destination); sw.start(t0); sw.stop(t0 + 0.12);
    note(1318.5, t0 + 0.08, 0.5, 0.16); note(1975.5, t0 + 0.17, 0.7, 0.14); note(2637, t0 + 0.17, 0.5, 0.04);
    [3520, 4186, 3951].forEach((f, i) => note(f, t0 + 0.28 + i * 0.05, 0.18, 0.025));
    setTimeout(() => c.close().catch(() => { }), 1500);
  } catch (e) { }
  try { D.vibrate(25); } catch (e) { }
}
async function scanCode() {
  if (!window.DewiarCodes || !window.ZXing) { toast("Сканер здесь недоступен"); return; }
  if (!(await needPerm("android.permission.CAMERA"))) { showBot("Для сканера нужен доступ к камере.", "err"); return; }
  closeSheets(); try { stopListen(); } catch (e) { }
  DewiarCodes.scan({ title: "Наведите на код", sub: "QR, штрихкод, Data Matrix, печать Dewiar", onError: (m) => showBot("Сканер: " + m, "err"),
    onResult: (txt, fmt) => { scanChime(); scanResult(txt, fmt); } });
}
function scanResult(txt, format) {
  const t = String(txt || "").trim();
  plog("info", "📷 код (" + (format || "?") + "): " + clip(t, 80));
  if (/^dewiar:\/\/close|[?&]close=/.test(t)) return clAcceptLink(t);
  if (/^dewiar:\/\/ref|download\.php\?(?:.*&)?ref=/.test(t)) { const c = (/[?&](?:c|ref)=([A-Za-z0-9]+)/.exec(t) || [])[1] || ""; return handleIntent({ action: "link", url: "dewiar://ref?c=" + c }); }
  if (/^dewiar:/.test(t)) return handleIntent({ action: "link", url: t });
  if (/^https?:\/\//i.test(t)) {
    let host = t; try { host = new URL(t).hostname; } catch (e) { }
    showBot(`В коде ссылка: ${t}`);
    $("#card").innerHTML = `<div class="start"><button class="btn p" id="sc-open">Открыть ${esc(host)}</button><button class="btn" id="sc-copy">Скопировать</button></div>`;
    $("#sc-open").onclick = () => D.openUrl(t); $("#sc-copy").onclick = () => { D.copy(t); toast("Скопировано"); };
    say("В коде ссылка на " + host.replace(/^www\./, ""));
    return;
  }
  // штрихкод или Data Matrix товара — разбирать код здесь не нужно: модель знает, как устроены коды «Честного знака»
  // (01 — GTIN, 21 — серийный номер…), и сама найдёт товар в интернете по штрихкоду
  if (/^(ean|upc|datamatrix)/.test(format || "") && /^[\x1d\x20-\x7e]{8,}$/.test(t) && /\d{8}/.test(t)) {
    showYou("📦 Что за товар?");
    return ask(`Я отсканировал код на товаре (${format}): ${t.replace(/\x1d/g, "<GS>")}. Разбери его и найди в интернете по штрихкоду, `
      + `что это за товар — коротко. Не нашлось — так и скажи. Если это код «Честного знака», в конце одной фразой: подлинность `
      + `и историю упаковки показывает официальное приложение «Честный знак».`, { hidden: true });
  }
  showBot("В коде: " + t);
  $("#card").innerHTML = `<div class="start"><button class="btn" id="sc-copy">Скопировать</button></div>`;
  $("#sc-copy").onclick = () => { D.copy(t); toast("Скопировано"); };
  if (t.length < 300) say("В коде написано: " + t);
}
/* Руководство (data/guide.json → guide.js при сборке): тот же поиск, что на сайте и в core/guide.py — основа слова
   против начала слов раздела; на телефоне разделы про телефон — выше. */
const GUIDE_URL = "https://dewiar.pro/dwrapp/guide.php";
function guideFind(query, n = 2) {
  const norm = (t) => String(t || "").toLowerCase().replace(/ё/g, "е"), split = (t) => norm(t).split(/[^a-zа-я0-9]+/).filter(Boolean);
  const STOP = new Set("как мне мой моя мои что где это для или при на в с и а не по из у о к ли же бы то можно хочу надо нужно сделать чтобы dewiar девиар лира приложение".split(" "));
  const stem = (w) => w.length >= 6 ? w.slice(0, -2) : w.length >= 4 ? w.slice(0, -1) : w;
  const q = split(query).filter(w => w.length > 1 && !STOP.has(w)).map(stem);
  if (!q.length) return [];
  return (window.DEWIAR_GUIDE || []).map(s => {
    const kw = split((s.keywords || []).join(" ") + " " + s.title), tx = split([s.lead, ...(s.how || []), ...(s.say || []), ...(s.tips || [])].join(" "));
    let sc = 0, hit = 0;
    for (const w of q) { const a = kw.some(x => x.startsWith(w)), b = a || tx.some(x => x.startsWith(w)); hit += b; sc += a ? 3 : b ? 1 : 0; }
    return [hit ? sc + hit * 2 + ((s.where || []).includes("phone") ? 1 : 0) : 0, s];
  }).filter(x => x[0] > 0).sort((a, b) => b[0] - a[0]).slice(0, n).map(x => x[1]);
}
function guideAnswer(query) {
  const f = guideFind(query);
  if (!f.length) return "В руководстве такого нет. Не выдумывай кнопки и меню: скажи честно и предложи посмотреть руководство — " + GUIDE_URL;
  return f.map(s => [`«${s.title}» (${(s.where || []).map(w => w === "pc" ? "компьютер" : "телефон").join(", ")})`, s.lead, ...(s.how || []).map(h => "— " + h),
    (s.say || []).length ? "Фразы: " + s.say.slice(0, 6).map(x => `«${x}»`).join("; ") : "", ...(s.tips || []).slice(0, 3).map(t => "Совет: " + t),
    `Подробнее: ${GUIDE_URL}#${s.id}`].filter(Boolean).join("\n")).join("\n\n") + "\n\nОтветь своими словами, коротко, с точными названиями разделов и кнопок; на телефоне — как это сделать на телефоне.";
}
/* лист «Близкие» */
const clTime = (ts) => { const d = new Date(ts), now = new Date(), hm = pad(d.getHours()) + ":" + pad(d.getMinutes()); return d.toDateString() === now.toDateString() ? hm : d.getDate() + " " + MON[d.getMonth()].slice(0, 3) + ", " + hm; };
const CL_COL = ["#9BD4FF", "#FFB547", "#3DF5C8", "#FF7AB6", "#B78CFF", "#9BE15D", "#7C8CFF", "#FF6B5A"];
const clCol = (pid) => CL_COL[[...String(pid)].reduce((a, c) => a + c.charCodeAt(0), 0) % CL_COL.length];
const clKb = (n) => n > 1048576 ? (n / 1048576).toFixed(1).replace(".", ",") + " МБ" : Math.max(1, Math.round(n / 1024)) + " КБ";
/* Вкладки листа «Близкие»: «Близкие» | «Рефералы». Зовут в «Близкие» из «Рефералов» (offers) — карточка с согласием. */
let clTab = "close";
function clTabs() { $$("#cl-tabs button").forEach(b => b.onclick = () => { clTab = b.dataset.t; clRender(); }); }
const clOffers = (st) => (st.offers || []).map(o => `<div class="card clof"><b>${esc(o.name)} зовёт вас в «Близкие»</b>
  <p class="hint" style="margin:4px 0 10px">Вы связаны приглашением в Dewiar. Согласитесь — и ваши помощники смогут передавать друг другу сообщения, можно будет созваниваться.</p>
  <div class="row2"><button class="btn p" data-y="${esc(o.pid)}" style="flex:1">Принять</button><button class="btn" data-n="${esc(o.pid)}" style="flex:1">Не сейчас</button></div></div>`).join("");
function clOfferBind() {
  $$(".clof [data-y], .clof [data-n]").forEach(b => b.onclick = async () => { const pid = b.dataset.y || b.dataset.n, yes = !!b.dataset.y; b.disabled = true;
    try { clKeys(); if (!clLoad().me.pid) await clHello(); const d = await clReq("POST", "/close/offer", { pid, yes }); clPeople(d);
      if (yes && d.person) { toast(`${d.person.name} теперь в ваших близких`); clTab = "close"; clCur = d.person.pid; } clRender(); }
    catch (e) { b.disabled = false; toast(e.message, 4000); } });
}
function openRefs() { clTab = "ref"; openClose(""); }
function openClose(pid) { clCur = pid || ""; openSheet("#sh-close"); clRender(); if (syncCred()) clHello().then(() => clRender()).catch(() => { }); }
function clRender() {
  const st = clLoad(), box = $("#close-body"), p = clCur && st.people.find(x => x.pid === clCur);
  $("#cl-h").firstChild.textContent = p ? "" : clTab === "ref" ? "Рефералы" : "Близкие";
  $("#cl-inv").style.display = p ? "none" : "";
  if (!syncCred()) { box.innerHTML = `<div class="card"><b>Нужен Dewiar</b><p class="hint" style="margin:6px 0 10px">«Близкие» работают через облако Dewiar: подключите мозг бесплатно или войдите аккаунтом dewiar.pro.</p><button class="btn p w" id="cl-brain">Подключить</button></div>`;
    $("#cl-brain").onclick = () => openSettings("brain"); return; }
  if (p) {
    delete st.unread[p.pid]; clSave(); clBadge();
    const h = st.hist[p.pid] || [];
    box.innerHTML = `<div class="clh"><button class="ib soft" id="cl-back"><svg viewBox="0 0 24 24"><path d="m15 5-7 7 7 7"/></svg></button><i class="clava" style="--c:${clCol(p.pid)}">${esc((p.name || "?")[0].toUpperCase())}</i>
        <div style="flex:1;min-width:0"><b>${esc(p.name)}</b><small>${(p.devs || []).length ? "сообщения шифруются" : "ещё не открывал Dewiar"}</small></div>
        ${(p.devs || []).length && window.DewiarCall ? `<button class="ib soft" id="cl-call" title="Позвонить"><svg viewBox="0 0 24 24"><path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2"/></svg></button>
          <button class="ib soft" id="cl-vcall" title="Видеозвонок"><svg viewBox="0 0 24 24"><rect x="2.5" y="6.5" width="13" height="11" rx="2.5"/><path d="m15.5 10.5 6-3.5v10l-6-3.5"/></svg></button>` : ""}
        ${h.length ? `<button class="ib soft" id="cl-wipe" title="Очистить переписку" aria-label="Очистить переписку"><svg viewBox="0 0 24 24"><path d="M4.5 7h15M9.5 7V5a1 1 0 0 1 1-1h3a1 1 0 0 1 1 1v2M6.5 7l1 12.5a1.5 1.5 0 0 0 1.5 1.4h6a1.5 1.5 0 0 0 1.5-1.4L17.5 7"/></svg></button>` : ""}</div>
      <div class="clmsgs" id="cl-msgs">${h.map((m, i) => `<div class="clm ${m.out ? "out" : ""}${m.rx && (m.rx.me || m.rx.them) ? " rx" : ""}${clEmoOnly(m.t) ? " emo" : ""}" data-i="${i}">${m.t ? `<div>${esc(m.t)}</div>` : ""}${(m.f || []).map((f, j) => `<button class="clf" data-i="${i}" data-j="${j}"><svg viewBox="0 0 24 24"><path d="M6 3.5h8.5L19 8v12.5H6z"/><path d="M14 3.5V8h5"/></svg><span>${esc(f.name)}</span><small>${f.saved ? "сохранён" : clKb(f.size || 0)}</small></button>`).join("")}<time>${clTime(m.ts)}</time>${m.rx && (m.rx.me || m.rx.them) ? `<span class="clrx">${esc([m.rx.them, m.rx.me].filter(Boolean).join(""))}</span>` : ""}</div>`).join("")
        || `<p class="hint" style="text-align:center;margin:24px 8px">Напишите первое сообщение — или скажите: «Напиши ${esc(p.name)}, …»</p>`}</div>
      <div class="clatts" id="cl-atts">${clFiles.map((f, i) => `<span>${esc(f.name)} <button data-i="${i}">✕</button></span>`).join("")}</div>
      <div class="clemo" id="cl-emo" hidden>${CL_EMO.map(e => `<button data-e="${e}" aria-label="Вставить ${e}">${e}</button>`).join("")}</div>
      <div class="clsend"><button class="ib att" id="cl-emo-b" aria-label="Эмодзи" aria-expanded="false"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8.5"/><path d="M8.5 14a4.2 4.2 0 0 0 7 0"/><path d="M9 9.6v.01M15 9.6v.01"/></svg></button><label class="ib att"><input type="file" id="cl-file" multiple hidden><svg viewBox="0 0 24 24"><path d="M20.5 11.5 12.6 19.4a5 5 0 0 1-7.1-7.1l8.3-8.3a3.4 3.4 0 0 1 4.8 4.8l-8.3 8.3a1.7 1.7 0 0 1-2.4-2.4l7.6-7.6"/></svg></label>
        <textarea id="cl-text" rows="1" placeholder="Сообщение…"></textarea><button class="ib" id="cl-go"><svg viewBox="0 0 24 24"><path d="M4 12 20 4l-6 16-2.5-6.5z"/></svg></button></div>`;
    const msgs = $("#cl-msgs"); msgs.scrollTop = msgs.scrollHeight;
    $("#cl-back").onclick = () => { clCur = ""; clRender(); };
    if ($("#cl-wipe")) $("#cl-wipe").onclick = () => { if (!confirm(`Очистить переписку с «${p.name}» на этом телефоне? У ${p.name} и на ваших других устройствах она останется. Одно сообщение — долгое нажатие на него.`)) return;
      clForget(p.pid); clRender(); toast("Переписка очищена"); };
    if ($("#cl-call")) { $("#cl-call").onclick = () => clCall(p.pid, false).catch(e => toast(e.message, 4000)); $("#cl-vcall").onclick = () => clCall(p.pid, true).catch(e => toast(e.message, 4000)); }
    $$("#cl-atts button").forEach(b => b.onclick = () => { clFiles.splice(+b.dataset.i, 1); clRender(); });
    $$(".clf").forEach(b => b.onclick = () => clSaveFile(p, h[+b.dataset.i], +b.dataset.j));
    $("#cl-file").onchange = () => { [...$("#cl-file").files].forEach(f => { if (f.size > 10 * 1024 * 1024) { toast(`«${f.name}» больше 10 МБ`); return; }
      const fr = new FileReader(); fr.onload = () => { clFiles.push({ name: f.name, type: f.type, bytes: new Uint8Array(fr.result) }); clRender(); }; fr.readAsArrayBuffer(f); }); };
    const go = async () => { const t = $("#cl-text").value.trim(); if (!t && !clFiles.length) return; const b = $("#cl-go"); b.disabled = true;
      try { await clSend(p.pid, t, clFiles); clFiles = []; clRender(); } catch (e) { toast(e.message, 4000); b.disabled = false; } };
    $("#cl-go").onclick = go;
    $("#cl-emo-b").onclick = () => { const e = $("#cl-emo"); e.hidden = !e.hidden; $("#cl-emo-b").setAttribute("aria-expanded", String(!e.hidden)); };
    $$("#cl-emo button").forEach(b => b.onclick = () => {           // вставить в текст там, где курсор
      const ta = $("#cl-text"), a = ta.selectionStart ?? ta.value.length, z = ta.selectionEnd ?? a;
      ta.value = ta.value.slice(0, a) + b.dataset.e + ta.value.slice(z); ta.selectionStart = ta.selectionEnd = a + b.dataset.e.length; ta.focus(); });
    clReBind(p, h);
    return;
  }
  if ((clTab === "near" || clTab === "meet") && !feat(clTab)) clTab = "close";      // «Возможности»: выключено — вкладки нет
  const tabs = `<div class="tabs" id="cl-tabs"><button data-t="close" class="${clTab === "close" ? "on" : ""}">Близкие</button>${feat("near") ? `<button data-t="near" class="${clTab === "near" ? "on" : ""}">Рядом</button>` : ""}${feat("meet") ? `<button data-t="meet" class="${clTab === "meet" ? "on" : ""}">Встречи</button>` : ""}<button data-t="ref" class="${clTab === "ref" ? "on" : ""}">Рефералы</button></div>`;
  if (clTab === "ref") { if (!$("#rf-body")) { box.innerHTML = tabs + `<div id="rf-body"></div>`; clTabs(); } refTab(); return; }
  if (clTab === "meet") { if (!$("#meet-body")) { box.innerHTML = tabs + `<div id="meet-body"></div>`; clTabs(); } meetRender(); mtLoad(); return; }
  if (clTab === "near") { if (!$("#rad-body")) { box.innerHTML = tabs + `<div id="rad-body"></div>`; clTabs(); } radRender(); return; }
  // сверху — сами близкие (лица крупно: нажал — переписка), «+» — пригласить; печать с приглашением — только когда
  // её позвали («Пригласить» или «+»), а не на пол-экрана каждый раз (отзыв 11.10)
  const inv = st.invite && Date.now() / 1000 < (st.invite.expires || 0) ? st.invite : null;
  const last = (x) => { const l = (st.hist[x.pid] || []).slice(-1)[0]; return l ? esc((l.out ? "Вы: " : "") + (l.t || "📎 " + ((l.f || [])[0] || {}).name)) : "пока без сообщений"; };
  const PH = `<svg viewBox="0 0 24 24"><path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2"/></svg>`,
    VI = `<svg viewBox="0 0 24 24"><rect x="2.5" y="6.5" width="13" height="11" rx="2.5"/><path d="m15.5 10.5 6-3.5v10l-6-3.5"/></svg>`;
  const rc = radCfg(), rseen = radOn() ? rc.to.map(pid => st.people.find(p => p.pid === pid)).filter(Boolean).map(p => esc(radFirst(p.name))) : [];
  box.innerHTML = tabs + clOffers(st)
    + (rseen.length && feat("near") ? `<button class="rad-mini" id="rad-mini"><i class="dot"></i><span>${rseen.length === 1 ? "Вас видит" : "Вас видят"} ${radList(rseen)} · ${radUntil(rc.until)}</span><b>Рядом</b></button>` : "")
    + `<div class="clfaces">${st.people.map(x => `<button class="clface" data-pid="${esc(x.pid)}"><i class="clava" style="--c:${clCol(x.pid)}">${esc((x.name || "?")[0].toUpperCase())}${st.unread[x.pid] ? `<em>${st.unread[x.pid]}</em>` : ""}</i><span>${esc(String(x.name || "").split(/\s+/)[0])}</span></button>`).join("")}
        <button class="clface add" id="cl-add"><i class="clava">+</i><span>Добавить</span></button></div>`
    + (st.people.length ? st.people.map(x => `<div class="clp" data-pid="${esc(x.pid)}"><i class="clava" style="--c:${clCol(x.pid)}">${esc((x.name || "?")[0].toUpperCase())}</i>
        <span><b>${esc(x.name)}</b><small>${last(x)}</small></span>${st.unread[x.pid] ? `<em>${st.unread[x.pid]}</em>` : ""}
        ${(x.devs || []).length && window.DewiarCall ? `<button class="ib soft" data-call="${esc(x.pid)}" title="Позвонить">${PH}</button><button class="ib soft" data-vcall="${esc(x.pid)}" title="Видеозвонок">${VI}</button>` : ""}</div>`).join("")
      : `<div class="card"><b>Пока никого</b><p class="hint" style="margin:4px 0 0">Нажмите «Пригласить» — покажите близкому печать Dewiar или отправьте ссылку. Потом говорите: «напиши маме, что я задержусь», «позвони маме по видео».</p></div>`)
    + `<div id="cl-invbox"></div>`
    + (inv && !clInvOpen ? `<button class="btn w clinvrow" id="cl-inv-show">Ссылка-приглашение действует до ${new Date(inv.expires * 1000).toLocaleDateString("ru-RU", { day: "numeric", month: "long" })} — показать печать</button>` : "")
    + clLiveCard()
    + `<h3>Как вас видят близкие</h3><div class="card"><input id="cl-name" placeholder="ваше имя" maxlength="40" value="${esc(st.me.name && st.me.name !== "Без имени" ? st.me.name : (S.close && S.close.name) || S.user_name || "")}">
      <div class="sw" style="margin-top:10px"><div>Читать сообщения вслух<small>«Мама пишет: …»</small></div><label class="tg"><input type="checkbox" id="cl-speak" ${S.close && S.close.speak === false ? "" : "checked"}><i></i></label></div></div>
    <p class="hint" style="margin:12px 4px">Переписка и звонки между помощниками, сообщения шифруются на устройствах. Голосом: «напиши Людмиле: привет», «позвони маме по видео».</p>
    <button class="btn w clscan" id="cl-scan"><svg viewBox="0 0 24 24"><path d="M4 8V5.5A1.5 1.5 0 0 1 5.5 4H8M16 4h2.5A1.5 1.5 0 0 1 20 5.5V8M20 16v2.5a1.5 1.5 0 0 1-1.5 1.5H16M8 20H5.5A1.5 1.5 0 0 1 4 18.5V16M7 12h10"/></svg>Сканировать приглашение</button>
    <details class="more"><summary>Пришла ссылка-приглашение?</summary><div class="row2" style="margin-top:8px"><input id="cl-link" placeholder="вставьте ссылку" style="flex:1;padding:12px 14px;border-radius:14px;border:0;background:var(--field)"><button class="btn p" id="cl-link-go">Принять</button></div></details>`;
  $$(".clp, .clface[data-pid]").forEach(b => b.onclick = (e) => { if (e.target.closest("[data-call],[data-vcall]")) return; clCur = b.dataset.pid; clRender(); });
  $$("[data-call]").forEach(b => b.onclick = () => clCall(b.dataset.call, false).catch(e => toast(e.message, 4000)));
  $$("[data-vcall]").forEach(b => b.onclick = () => clCall(b.dataset.vcall, true).catch(e => toast(e.message, 4000)));
  $("#cl-add").onclick = () => clInviteOpen();
  if ($("#cl-inv-show")) $("#cl-inv-show").onclick = () => clInviteOpen();
  clTabs(); clOfferBind(); clLiveBind();
  if ($("#rad-mini")) $("#rad-mini").onclick = () => { clTab = "near"; clRender(); };
  $("#cl-scan").onclick = () => scanCode();
  if (inv && clInvOpen) clInvShow(inv);
  $("#cl-name").onchange = () => { S.close = Object.assign({}, S.close, { name: $("#cl-name").value.trim() }); saveS(); clHello().then(() => toast("Сохранено")).catch(e => toast(e.message)); };
  $("#cl-speak").onchange = () => { S.close = Object.assign({}, S.close, { speak: $("#cl-speak").checked }); saveS(); };
  $("#cl-link-go").onclick = () => clAcceptLink($("#cl-link").value);
}
// сообщение только из эмодзи — крупно, как в мессенджерах
const clEmoOnly = (t) => !!t && t.length <= 12 && /^(?:\p{Extended_Pictographic}|\u200d|\ufe0f|\s)+$/u.test(t);
/* реакция: долгое нажатие (или правая кнопка) на сообщение — ряд эмодзи над ним; та же — снять */
/* Убрать сообщения из переписки на этом телефоне (mids — какие, без mids — всю); у близкого и на других устройствах
   переписка остаётся — как forget в core/close.py */
function clForget(pid, mids) {
  const st = clLoad(), h = st.hist[pid] || [], drop = mids ? new Set(mids.map(String)) : null;
  const keep = drop ? h.filter(x => !drop.has(String(x.mid || ""))) : [];
  if (keep.length) st.hist[pid] = keep; else { delete st.hist[pid]; delete st.unread[pid]; }
  clSave(); return h.length - keep.length;
}
function clReBind(p, h) {
  let t = 0, sx = 0, sy = 0;
  const open = (el) => {
    clReClose(); const m = h[+el.dataset.i]; if (!m || !m.mid) return;
    D.vibrate(15);
    const pop = document.createElement("div"); pop.className = "clrepick"; pop.setAttribute("role", "menu");
    // долгое нажатие: реакции, ниже — «Копировать» и «Удалить у меня» (отзыв 17.10: «выборочно поудалять лишнее»)
    pop.innerHTML = `<div class="emos">${CL_EMO.map(e => `<button role="menuitem" data-e="${e}" class="${(m.rx || {}).me === e ? "on" : ""}" aria-label="Реакция ${e}">${e}</button>`).join("")}</div>
      <div class="acts">${m.t ? `<button role="menuitem" class="cp"><svg viewBox="0 0 24 24"><rect x="8.5" y="8.5" width="11" height="11" rx="2.5"/><path d="M15.5 8.5V6a1.5 1.5 0 0 0-1.5-1.5H6A1.5 1.5 0 0 0 4.5 6v8A1.5 1.5 0 0 0 6 15.5h2.5"/></svg>Копировать</button>` : ""}
        <button role="menuitem" class="dl"><svg viewBox="0 0 24 24"><path d="M4.5 7h15M9.5 7V5a1 1 0 0 1 1-1h3a1 1 0 0 1 1 1v2M6.5 7l1 12.5a1.5 1.5 0 0 0 1.5 1.4h6a1.5 1.5 0 0 0 1.5-1.4L17.5 7"/></svg>Удалить у меня</button></div>`;
    document.body.appendChild(pop);
    const r = el.getBoundingClientRect(), w = pop.offsetWidth;
    pop.style.left = Math.max(8, Math.min(innerWidth - w - 8, m.out ? r.right - w : r.left)) + "px";
    pop.style.top = Math.max(8, r.top - pop.offsetHeight - 8) + "px";
    const cp = $(".cp", pop); if (cp) cp.onclick = () => { clReClose(); copyText(m.t).then(okc => toast(okc ? "Скопировано" : "Не скопировалось")); };
    $(".dl", pop).onclick = () => { clReClose(); clForget(p.pid, [m.mid]); clRender(); toast("Удалено на этом телефоне — у " + p.name + " сообщение осталось", 3000); };
    $$("button[data-e]", pop).forEach(b => b.onclick = async () => {
      const e = (m.rx || {}).me === b.dataset.e ? "" : b.dataset.e; clReClose();
      try { await clReact(p.pid, m.mid, e); } catch (x) { toast(x.message, 4000); }
      clRender();
    });
    setTimeout(() => document.addEventListener("pointerdown", clReOut, true), 0);
  };
  $$("#cl-msgs .clm").forEach(el => {
    el.addEventListener("pointerdown", (e) => { sx = e.clientX; sy = e.clientY; clearTimeout(t); t = setTimeout(() => open(el), 450); });
    el.addEventListener("pointermove", (e) => { if (Math.hypot(e.clientX - sx, e.clientY - sy) > 10) clearTimeout(t); });
    ["pointerup", "pointercancel", "pointerleave"].forEach(k => el.addEventListener(k, () => clearTimeout(t)));
    el.addEventListener("contextmenu", (e) => { e.preventDefault(); clearTimeout(t); open(el); });
  });
}
function clReOut(e) { if (!e.target.closest(".clrepick")) clReClose(); }
function clReClose() { $$(".clrepick").forEach(x => x.remove()); document.removeEventListener("pointerdown", clReOut, true); }
let clInvOpen = false;
const clLiveWanted = () => !(S.close && S.close.live === false);
const clLiveOn = () => clLiveWanted() && !liteOn();      // лёгкий режим — без постоянной связи: проверка раз в 15 минут
function clLiveCard() {
  if (!D.closeLive || !clLoad().people.length) return "";
  const batt = clLiveOn() && D.batteryOk && !D.batteryOk();
  return `<h3>Когда приложение закрыто</h3><div class="card"><div class="sw"><div>Сообщения и звонки — сразу<small>В шторке — тихий значок «Dewiar на связи»; звонок близкого — на весь экран, даже на заблокированном</small></div>
    <label class="tg"><input type="checkbox" id="cl-live" ${clLiveWanted() ? "checked" : ""}><i></i></label></div>
    ${clLiveWanted() && liteOn() ? `<p class="hint" style="margin:8px 2px 0">Сейчас лёгкий режим (${esc(liteWhyNow)}): новые сообщения — проверка раз в 15 минут, без постоянной связи.</p>` : ""}
    ${batt ? `<button class="btn w" id="cl-batt" style="margin-top:10px">Разрешить работу в фоне</button><p class="hint" style="margin:6px 2px 0">Иначе телефон может усыплять Dewiar, и звонки будут доходить с опозданием.</p>` : ""}</div>`;
}
function clLiveBind() {
  if ($("#cl-live")) $("#cl-live").onchange = async () => { const on = $("#cl-live").checked; S.close = Object.assign({}, S.close, { live: on }); saveS();
    if (on) await needPerm("android.permission.POST_NOTIFICATIONS"); clWatch(); clRender(); };
  if ($("#cl-batt")) $("#cl-batt").onclick = () => D.askBattery();
}
async function clInviteOpen() {
  clInvOpen = true; clTab = "close";
  try { const d = await clInvite(false); clRender(); clInvShow(d); setTimeout(() => { const b = $("#cl-invbox"); if (b) b.scrollIntoView({ block: "center", behavior: "smooth" }); }, 50); }
  catch (e) { toast(e.message, 4000); }
}
function clInvShow(d) {
  const box = $("#cl-invbox"); if (!box) return;
  const code = String(d.link || "").split("&from=")[0];          // в коде — короткая ссылка (без имени): код чище и легче читается
  const seal = window.DewiarCodes && window.ZXing ? DewiarCodes.seal(code) : "";
  box.innerHTML = `<div class="card clinv"><div class="clqr ${seal ? "seal" : ""}" id="cl-code">${seal || (typeof qrcode === "function" ? clQr(code) : "")}</div>
    <p class="hint" style="margin:8px 0">Покажите печать близкому: в Dewiar — «Сканер» в «Близких», без Dewiar — Google Lens. Или отправьте ссылку. Одна ссылка — для всех, кого зовёте, 7 дней; поэтому отправляйте её только своим.</p><p class="hint cllinks">${seal ? `<a href="#" id="cl-code-qr">Обычный QR</a>` : ""}<a href="#" id="cl-renew">Новая ссылка</a></p>
    <div class="row2"><button class="btn p" id="cl-share" style="flex:1">Отправить</button><button class="btn" id="cl-copy" style="flex:1">Копировать</button><button class="btn" id="cl-inv-hide" style="flex:1">Скрыть</button></div></div>`;
  $("#cl-inv-hide").onclick = () => { clInvOpen = false; clRender(); };
  if ($("#cl-code-qr")) $("#cl-code-qr").onclick = (e) => { e.preventDefault(); const c = $("#cl-code"), isSeal = c.classList.contains("seal");
    c.innerHTML = isSeal ? clQr(code) : seal; c.classList.toggle("seal", !isSeal); e.target.textContent = isSeal ? "Печать Dewiar" : "Обычный QR"; };
  $("#cl-share").onclick = () => D.share(`Добавь меня в «Близкие» в Dewiar — наши помощники смогут передавать друг другу сообщения: ${d.link}`);
  $("#cl-copy").onclick = () => { D.copy(d.link); toast("Ссылка скопирована"); };
  $("#cl-renew").onclick = (e) => { e.preventDefault();                        // попала не туда — прежняя перестаёт действовать
    if (confirm("Сделать новую ссылку? Старая перестанет действовать — те, кто уже добавился, останутся в близких.")) clInvite(true).then(clInvShow, (x) => toast(x.message, 4000)); };
}
function clQr(text) {                             // QR как в студии: скруглённые точки и «глазки» (тёмное на белом)
  const q = qrcode(0, "M"); q.addData(text); q.make();
  const n = q.getModuleCount(), m = 1.5, W = n + m * 2, eye = (r, c) => (r < 7 && c < 7) || (r < 7 && c >= n - 7) || (r >= n - 7 && c < 7);
  let dots = "";
  for (let r = 0; r < n; r++) for (let c = 0; c < n; c++) if (q.isDark(r, c) && !eye(r, c)) dots += `<rect x="${(c + m + 0.07).toFixed(2)}" y="${(r + m + 0.07).toFixed(2)}" width=".86" height=".86" rx=".3"/>`;
  const e = (r, c) => { const x = c + m, y = r + m; return `<rect x="${x + 0.5}" y="${y + 0.5}" width="6" height="6" rx="1.9" fill="none" stroke="#111" stroke-width="1"/><rect x="${x + 2}" y="${y + 2}" width="3" height="3" rx="1"/>`; };
  return `<svg viewBox="0 0 ${W} ${W}"><rect width="${W}" height="${W}" fill="#fff"/><g fill="#111">${dots}${e(0, 0)}${e(0, n - 7)}${e(n - 7, 0)}</g></svg>`;
}
/* ---------- «Близкие» → «Рядом»: радар (идея Валерия Михайловского; макет одобрен 20.10) ----------
   На радаре — близкие, которые сами решили показать, где они: ближе к центру — ближе к вам (шкала логарифмическая:
   300 м, 3 км, 30 км). Видно «сколько и в какую сторону», а не точку на карте. Своё место показываю только отмеченным
   близким и на срок (час, до вечера, всегда); оно шифруется здесь же, как сообщения (kind «geo»: сервер хранит одно
   последнее и видит только, кому и когда) и обновляется, пока Dewiar открыт — в фоне за телефоном не следим.
   «👋 Помахать» — сообщение {wave: 1, t: "👋"}: у близкого волны от вашего кружка, всплывающее «Андрей машет вам» и голос;
   старые программы покажут просто «👋». Место телефона — D.locate (Loc.java; в браузере — geolocation), ответ событием loc. */
const RAD_STALE = 15 * 60000, RAD_PUSH = 4 * 60000;
const RAD_DIR = ["на север", "на северо-восток", "на восток", "на юго-восток", "на юг", "на юго-запад", "на запад", "на северо-запад"];
const RAD_FINE = "android.permission.ACCESS_FINE_LOCATION", RAD_COARSE = "android.permission.ACCESS_COARSE_LOCATION";
let radMe = null, radErr = null, radSel = "", radHead = null, radCompass = false, radRaf = 0, radEdit = false, radEditSel = null, radEditMode = "hour";
const radWaveAt = {}, locWait = [];
const radCfg = () => Object.assign({ to: [], until: 0, asked: {} }, S.radar || {});
const radOn = () => { const r = radCfg(); return r.to.length > 0 && (r.until === -1 || r.until > Date.now()); };
const radPl = (n, a, b, c) => (n % 10 === 1 && n % 100 !== 11 ? a : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20) ? b : c);
const radFirst = (n) => String(n || "").trim().split(/\s+/)[0] || "Без имени";
/* ---------- «Встречи» (0.38.98): знакомства там, где вы сейчас ----------
   Сервер — cloud.php meet_handler (/meet/state|rules|here|leave|wave|block|report). Отметка на 1–3 часа: имя, пара слов,
   место; другие рядом (≈700 м) видят только это — ни точного места, ни расстояния. 👋 взаимно — оба в «Близких» (переписка
   шифруется). Ушли или вышло время — отметки и «помахал» нет. 18+ и правила — один раз; блок и жалоба — в меню «⋯». */
let MT = null, mtErr = "", mtEdit = false, mtHours = 2, mtTimer = 0, mtMenu = "";
async function mtLoad() {
  clearTimeout(mtTimer);
  try { MT = await clReq("GET", "/meet/state"); mtErr = ""; } catch (e) { mtErr = e.message; }
  if ($("#meet-body")) { meetRender(); mtTimer = setTimeout(() => { if ($("#meet-body") && $("#sh-close").classList.contains("on")) mtLoad(); }, 20000); }
}
const mtMin = (s) => Math.max(0, Math.round(s / 60));
const mtLeft = (u) => { const m = mtMin(u - Date.now() / 1000); return m >= 60 ? Math.floor(m / 60) + " ч" + (m % 60 ? " " + (m % 60) + " мин" : "") : m + " мин"; };
const mtAgo = (ts) => { const m = mtMin(Date.now() / 1000 - ts); return m < 2 ? "только что" : m < 60 ? m + " мин" : Math.floor(m / 60) + " ч"; };
function mtCall(path, body, btn) {
  if (btn) btn.disabled = true;
  return clReq("POST", path, body || {}).then(d => { MT = d; mtErr = ""; return d; })
    .catch(e => { toast(e.message, 4500); throw e; }).finally(() => { if (btn) btn.disabled = false; if ($("#meet-body")) meetRender(); });
}
function meetRender() {
  const body = $("#meet-body"); if (!body) return;
  if (!MT) { body.innerHTML = mtErr ? `<div class="card"><b>Встречи не открылись</b><p class="hint" style="margin:6px 0 10px">${esc(mtErr)}</p><button class="btn w" id="mt-retry">Повторить</button></div>`
    : `<p class="hint" style="text-align:center;margin:30px">Загружаю…</p>`; if ($("#mt-retry")) $("#mt-retry").onclick = () => { mtErr = ""; meetRender(); mtLoad(); }; return; }
  const me = MT.me || {};
  if (!me.adult) {
    body.innerHTML = `<div class="card mt-intro"><b class="mt-big">Знакомства там, где вы сейчас</b>
      <ul class="mt-rules"><li>Отметьтесь на концерте, выставке, в кафе — на 1–3 часа.</li>
        <li>Рядом видят только имя, пару слов о вас и место. Ни фото, ни адреса, ни расстояния.</li>
        <li>Связь — только если вы помахали 👋 друг другу: тогда вы оба в «Близких», переписка шифруется.</li>
        <li>Ушли — отметка и все «помахал» стираются. Истории нет.</li>
        <li>Неприятно — «Заблокировать» или «Пожаловаться» в одно нажатие.</li></ul>
      <label class="mt-adult"><input type="checkbox" id="mt-18"><span>Мне есть 18 лет, правила понятны</span></label>
      <button class="btn p w" id="mt-start" disabled>Начать</button></div>`;
    $("#mt-18").onchange = () => { $("#mt-start").disabled = !$("#mt-18").checked; };
    $("#mt-start").onclick = () => mtCall("/meet/rules", { adult: true }, $("#mt-start")).catch(() => { });
    return;
  }
  if (me.ban_until) { body.innerHTML = `<div class="card"><b>Встречи закрыты до ${new Date(me.ban_until * 1000).toLocaleDateString("ru-RU", { day: "numeric", month: "long" })}</b><p class="hint" style="margin:6px 0 0">На вас пожаловались несколько человек. Если это ошибка — напишите в поддержку из «Ещё» → «Сообщить о проблеме».</p></div>`; return; }
  const h = me.here, st = clLoad();
  if (!h || mtEdit) {
    if ($("#mt-go") && !$("#mt-go").disabled) return;      // анкета уже на экране — не стираем то, что человек вписывает (опрос раз в 20 с)
    const nm = (h && h.name) || String((st.me && st.me.name !== "Без имени" && st.me.name) || (S.close && S.close.name) || S.user_name || "").split(/\s+/)[0];
    body.innerHTML = `<div class="card mt-form"><b class="mt-big">${h ? "Изменить отметку" : "Отметиться здесь"}</b>
      <label class="f"><span>Как вас называть</span><input id="mt-name" maxlength="24" placeholder="имя" value="${esc(nm)}"></label>
      <label class="f"><span>Пара слов о себе</span><textarea id="mt-about" maxlength="120" rows="2" placeholder="например: впервые здесь, люблю джаз">${esc((h && h.about) || "")}</textarea></label>
      <label class="f"><span>Где вы</span><input id="mt-place" maxlength="60" placeholder="концерт, выставка, кафе…" value="${esc((h && h.place) || "")}"></label>
      <div class="mt-row"><span>Видно</span><div class="seg" id="mt-hours">${[1, 2, 3].map(n => `<button data-h="${n}" class="${mtHours === n ? "on" : ""}">${n} ч</button>`).join("")}</div></div>
      <div class="row2"><button class="btn p" id="mt-go" style="flex:2">${h ? "Сохранить" : "Отметиться"}</button>${h ? `<button class="btn" id="mt-cancel" style="flex:1">Отмена</button>` : ""}</div>
      <p class="hint" style="margin:10px 0 0">Ссылки, ники и номера не нужны — контакт откроется сам, когда помашете друг другу. Точное место никто не видит.</p></div>`;
    $$("#mt-hours button").forEach(b => b.onclick = () => { mtHours = +b.dataset.h; $$("#mt-hours button").forEach(x => x.classList.toggle("on", x === b)); });
    if ($("#mt-cancel")) $("#mt-cancel").onclick = () => { mtEdit = false; meetRender(); };
    $("#mt-go").onclick = async () => {
      const b = $("#mt-go"), name = $("#mt-name").value.trim();
      if (!name) { toast("Как вас называть? Достаточно имени."); $("#mt-name").focus(); return; }
      b.disabled = true; b.textContent = "Определяю место…";
      let g; try { g = await myPlace(60, true); } catch (e) { b.disabled = false; b.textContent = h ? "Сохранить" : "Отметиться"; toast(e.kind === "perm" ? "Разрешите Dewiar место — иначе не понять, кто рядом." : e.kind === "off" ? "Включите определение места в телефоне." : e.message, 5000); return; }
      // не через mtCall: при ошибке («без ссылок и номеров») анкета остаётся как есть — с тем, что человек вписал
      try { MT = await clReq("POST", "/meet/here", { lat: g.lat, lon: g.lon, name, about: $("#mt-about").value.trim(), place: $("#mt-place").value.trim(), hours: mtHours }); mtErr = ""; mtEdit = false; meetRender(); }
      catch (e) { toast(e.message, 5000); b.disabled = false; b.textContent = h ? "Сохранить" : "Отметиться"; }
    };
    return;
  }
  const ppl = MT.people || [];
  body.innerHTML = `<div class="card mt-me"><i class="dot"></i><div style="flex:1;min-width:0"><b>Вы отмечены</b><small>${h.place ? esc(h.place) + " · " : ""}видно ещё ${mtLeft(h.until)}</small></div>
      <button class="btn sm" id="mt-edit">Изменить</button><button class="btn sm" id="mt-leave">Уйти</button></div>
    <h3>${ppl.length ? "Рядом — " + ppl.length : "Рядом пока никого"}</h3>`
    + (ppl.length ? ppl.map(x => `<div class="card mtp${x.waves_me ? " in" : ""}${x.match ? " match" : ""}" data-mid="${esc(x.mid)}">
        <div class="mtp-h"><i class="clava" style="--c:${clCol(x.mid)}">${esc((x.name || "?")[0].toUpperCase())}</i><div style="flex:1;min-width:0"><b>${esc(x.name)}</b>
          <small>${x.place ? esc(x.place) + " · " : ""}здесь ${mtAgo(x.since)}</small></div><button class="ib soft mt-more" data-m="${esc(x.mid)}" aria-label="Ещё: заблокировать, пожаловаться" aria-expanded="${mtMenu === x.mid}">⋯</button></div>
        ${x.about ? `<p class="mtp-a">${esc(x.about)}</p>` : ""}
        ${mtMenu === x.mid ? `<div class="row2 mt-menu"><button class="btn" data-block="${esc(x.mid)}" style="flex:1">Заблокировать</button><button class="btn" data-report="${esc(x.mid)}" style="flex:1">Пожаловаться</button></div>` : ""}
        <div class="mtp-act">${x.match ? `<span class="mt-ok">👋 Вы помахали друг другу</span><button class="btn p sm" data-chat="${esc(x.pid)}">Написать</button>`
          : x.waved ? `<span class="mt-ok">Вы помахали — ждём ответа</span><button class="btn sm" data-undo="${esc(x.mid)}">Отменить</button>`
          : x.waves_me ? `<span class="mt-in">👋 Вам помахали</span><button class="btn p sm" data-wave="${esc(x.mid)}">Помахать в ответ</button>`
          : `<button class="btn sm" data-wave="${esc(x.mid)}">👋 Помахать</button>`}</div></div>`).join("")
      : `<p class="hint" style="margin:0 4px 12px">Отметка видна ещё ${mtLeft(h.until)}. Кто отметится рядом — появится здесь.</p>`)
    + `<p class="hint">Видно только тех, кто отметился в пределах ~${MT.radius_m || 700} м. Ни точного места, ни расстояния не видит никто.</p>`;
  $("#mt-edit").onclick = () => { mtEdit = true; meetRender(); };
  $("#mt-leave").onclick = () => mtCall("/meet/leave", {}, $("#mt-leave")).then(() => toast("Отметки больше нет")).catch(() => { });
  $$("[data-m]").forEach(b => b.onclick = () => { mtMenu = mtMenu === b.dataset.m ? "" : b.dataset.m; meetRender(); });
  $$("[data-wave]").forEach(b => b.onclick = () => mtCall("/meet/wave", { mid: b.dataset.wave }, b).then(d => {
    if (d.match) { if (d.state) clPeople(d.state); const p = (d.people || []).find(x => x.pid === d.pid); toast(`Вы помахали друг другу — ${p ? p.name : "собеседник"} теперь в «Близких»`, 4500); clHello().catch(() => { }); }
    else toast("👋 Помахали");
  }).catch(() => { }));
  $$("[data-undo]").forEach(b => b.onclick = () => mtCall("/meet/wave", { mid: b.dataset.undo, undo: 1 }, b).catch(() => { }));
  $$("[data-chat]").forEach(b => b.onclick = async () => { b.disabled = true; try { await clHello(); } catch (e) { } clTab = "close"; clCur = b.dataset.chat; clRender(); });
  $$("[data-block]").forEach(b => b.onclick = () => { if (!confirm("Заблокировать? Вы больше не увидите друг друга во Встречах, а если уже в «Близких» — он оттуда уйдёт.")) return;
    mtMenu = ""; mtCall("/meet/block", { mid: b.dataset.block }, b).then(() => toast("Заблокировано")).catch(() => { }); });
  $$("[data-report]").forEach(b => b.onclick = () => { const why = prompt("Что случилось? Можно коротко — это увидит только администратор Dewiar.", ""); if (why === null) return;
    mtMenu = ""; mtCall("/meet/report", { mid: b.dataset.report, why }, b).then(() => toast("Спасибо. Жалоба отправлена, вы больше не увидите друг друга")).catch(() => { }); });
}

function radGeo(a, b) {                                   // от a до b: [км, направление в градусах от севера по часовой]
  const t = Math.PI / 180, f1 = a.lat * t, f2 = b.lat * t, df = (b.lat - a.lat) * t, dl = (b.lon - a.lon) * t;
  const h = Math.sin(df / 2) ** 2 + Math.cos(f1) * Math.cos(f2) * Math.sin(dl / 2) ** 2;
  const deg = Math.atan2(Math.sin(dl) * Math.cos(f2), Math.cos(f1) * Math.sin(f2) - Math.sin(f1) * Math.cos(f2) * Math.cos(dl)) / t;
  return [2 * 6371 * Math.asin(Math.min(1, Math.sqrt(h))), (deg + 360) % 360];
}
const radKm = (km) => km < 0.05 ? "рядом" : km < 1 ? Math.round(km * 100) * 10 + " м" : (km < 10 ? km.toFixed(1).replace(".", ",") : Math.round(km).toLocaleString("ru-RU")) + " км";
const radKmSay = (km) => km < 1 ? `${Math.round(km * 100) * 10} метрах` : km < 10 ? `${km.toFixed(1).replace(".", ",")} км` : `${Math.round(km)} км`;
const radDir = (d) => RAD_DIR[Math.round((((d % 360) + 360) % 360) / 45) % 8];
function radAgo(ts, full) {
  const m = Math.max(0, Math.round((Date.now() - ts) / 60000)), h = Math.round(m / 60);
  if (m < 2) return full ? "только что" : "сейчас";
  if (m < 60) return full ? `${m} ${radPl(m, "минуту", "минуты", "минут")} назад` : `${m} мин назад`;
  if (m < 1440) return full ? `${h} ${radPl(h, "час", "часа", "часов")} назад` : `${h} ч назад`;
  return clTime(ts);
}
function radEve() {                                       // «До вечера» (22:00); поздно вечером — «До утра» (8:00)
  const d = new Date();
  if (d.getHours() < 21) { d.setHours(22, 0, 0, 0); return ["До вечера", +d]; }
  d.setDate(d.getDate() + 1); d.setHours(8, 0, 0, 0); return ["До утра", +d];
}
function radUntil(u) {
  if (u === -1) return "всегда";
  const d = new Date(u), hm = pad(d.getHours()) + ":" + pad(d.getMinutes());
  return d.toDateString() === new Date().toDateString() ? "до " + hm : "до завтра, " + hm;
}
const radList = (ns) => ns.length <= 1 ? ns.join("") : ns.length <= 3 ? ns.slice(0, -1).join(", ") + " и " + ns[ns.length - 1] : `${ns.slice(0, 2).join(", ")} и ещё ${ns.length - 2}`;

/* где я: разрешение спрашиваем только по нажатию (ask); ответ Loc.java — событием loc */
N.on("loc", e => { locWait.splice(0).forEach(w => w(e)); });
const radCan = () => !!D.locate && (D.has(RAD_FINE) || D.has(RAD_COARSE));
async function myPlace(maxAgeSec, ask) {
  if (!D.locate) throw Object.assign(new Error("на этом устройстве место не определяется"), { kind: "none" });
  if (!radCan()) {
    if (!ask) throw Object.assign(new Error("нет разрешения на местоположение"), { kind: "perm" });
    const ok = await needPerm(RAD_FINE);
    if (!ok && !D.has(RAD_COARSE)) throw Object.assign(new Error("Dewiar не разрешили определять место"), { kind: "perm" });
  }
  const e = await new Promise((res) => {
    const w = (x) => { clearTimeout(t); res(x); }, t = setTimeout(() => { const i = locWait.indexOf(w); if (i >= 0) locWait.splice(i, 1); res({ error: "место не определилось за полминуты" }); }, 30000);
    locWait.push(w); D.locate(maxAgeSec == null ? 60 : maxAgeSec);
  });
  if (e.error) throw Object.assign(new Error(e.error), { kind: /выключ/.test(e.error) ? "off" : /разреш/.test(e.error) ? "perm" : "fail" });
  if (!geoOk(+e.lat, +e.lon)) throw Object.assign(new Error("место не определилось"), { kind: "fail" });
  radMe = { lat: +e.lat, lon: +e.lon, acc: Math.max(0, +e.acc || 0), ts: Math.min(Date.now(), +e.ts || Date.now()) };
  return radMe;
}
async function radLocate(ask) {
  if (radLocate.busy && !ask) return;
  radLocate.busy = true;
  try { const me = await myPlace(ask ? 0 : 30, ask); radErr = null; radOwn(me); }
  catch (e) { radErr = { kind: e.kind || "fail", msg: e.message }; }
  finally { radLocate.busy = false; }
  if ($("#rad-body")) radRender();
}

/* кто показывает себя мне (st.geo: pid -> {lat, lon, acc, ts, until}); просроченное — убираем */
function radPeople() {
  const st = clLoad(), g = st.geo || {}, now = Date.now(), out = [];
  let drop = false;
  for (const pid of Object.keys(g)) {
    const x = g[pid], p = st.people.find(y => y.pid === pid);
    if (!p || (x.until !== -1 && x.until < now) || now - x.ts > 7 * 864e5) { delete g[pid]; drop = true; continue; }
    const o = { p, g: x };
    if (radMe) [o.km, o.deg] = radGeo(radMe, x);
    out.push(o);
  }
  if (drop) clSave();
  return out.sort((a, b) => (a.km ?? 1e9) - (b.km ?? 1e9));
}
function radTake(pid, name, g) {                          // пришло место близкого (или «больше не показываю»)
  const st = clLoad(); st.geo = st.geo || {};
  const had = !!st.geo[pid];
  if (!g || typeof g !== "object" || g.off || !geoOk(+g.lat, +g.lon)) delete st.geo[pid];
  else st.geo[pid] = { lat: +g.lat, lon: +g.lon, acc: Math.max(0, +g.acc || 0), ts: Math.min(Date.now(), +g.ts || Date.now()),
    until: g.until === -1 ? -1 : +g.until > 0 ? +g.until : Date.now() + 3600e3 };
  clSave();
  if (!had && st.geo[pid] && !document.hidden && !$("#rad-body")) toast(`📍 ${radFirst(name)} теперь на вашем радаре — «Близкие» → «Рядом»`, 3200);
  if ($("#rad-body")) radRender();
}

/* показать себя: отмеченным близким — место, не чаще раза в 4 минуты (если не сдвинулся на 50 м); снять — {off} */
async function radPush(force) {
  if (!radOn() || !syncCred() || !DC() || radPush.busy) return 0;
  const r = radCfg(), last = r.sent || {};
  if (!force && Date.now() - (last.at || 0) < 90000) return 0;
  radPush.busy = true;
  try {
    const me = await myPlace(force ? 30 : 120, false);
    if (!force && Date.now() - (last.at || 0) < RAD_PUSH && last.lat != null && radGeo(last, me)[0] < 0.05) return 0;
    const g = { lat: +me.lat.toFixed(5), lon: +me.lon.toFixed(5), acc: Math.round(me.acc), ts: me.ts, until: r.until };
    let n = 0;
    for (const pid of r.to) {
      if (!clLoad().people.some(p => p.pid === pid)) continue;
      try { await clSend(pid, "", [], "geo", { g }); n++; } catch (e) { plog("info", "радар: " + e.message); }
    }
    S.radar = Object.assign(radCfg(), { sent: { at: Date.now(), lat: me.lat, lon: me.lon } }); saveS();
    radOwn(me);
    return n;
  } catch (e) { plog("info", "радар: место — " + e.message); return 0; }
  finally { radPush.busy = false; }
}
/* Место телефона — своим же устройствам (компьютер рисует радар вокруг него): конверт /close/self {mygeo}, зашифрован
   ключами своих устройств, как ключ умного дома. Не чаще раза в 4 минуты (или сдвинулся на 50 м), только пока радаром
   пользуются (открыт или показываю себя близким) и только если есть другие свои устройства. */
async function radOwn(me) {
  try {
    if (!me || !syncCred() || !DC()) return false;
    const k = clKeys(), devs = ((clLoad().me || {}).devs || []).filter(d => d.pub && d.dev && d.dev !== k.dev);
    if (!devs.length) return false;
    const last = radOwn.last || {};
    if (Date.now() - (last.at || 0) < RAD_PUSH && last.lat != null && radGeo(last, me)[0] < 0.05) return false;
    const t = {}; devs.forEach(d => { t[d.dev] = DC().b64d(d.pub); }); t[k.dev] = DC().b64d(k.pub);
    const body = { mygeo: { lat: +me.lat.toFixed(5), lon: +me.lon.toFixed(5), acc: Math.round(me.acc || 0), ts: me.ts }, ts: Date.now() };
    await clReq("POST", "/close/self", { env: DC().encryptFor(body, DC().b64d(k.priv), k.dev, t) });
    radOwn.last = { at: Date.now(), lat: me.lat, lon: me.lon }; return true;
  } catch (e) { plog("info", "радар: место своим устройствам — " + e.message); return false; }
}
async function radStop(pids) { for (const pid of pids) { try { await clSend(pid, "", [], "geo", { g: { off: 1 } }); } catch (e) { } } }
async function radShare(to, mode) {
  const old = radCfg(), was = radOn() ? old.to : [];
  const until = mode === "off" ? 0 : mode === "hour" ? Date.now() + 3600e3 : mode === "eve" ? radEve()[1] : -1;
  S.radar = Object.assign(old, { to: mode === "off" ? old.to : to, until, sent: {} }); saveS();
  const gone = was.filter(pid => mode === "off" || !to.includes(pid));
  if (gone.length) radStop(gone);
  if (mode === "off") return 0;
  if (!radCan()) { try { await myPlace(0, true); } catch (e) { radErr = { kind: e.kind, msg: e.message }; } }
  return radPush(true);
}
function radTick() {
  if (document.hidden || (typeof EXAM !== "undefined" && EXAM)) return;
  if (radOn()) radPush(false);
  if ($("#rad-body") && $("#sh-close").classList.contains("on")) { if (radCan() && (!radMe || Date.now() - radMe.ts > 30000)) radLocate(false); else radRender(); }
}
setInterval(radTick, 30000);
document.addEventListener("visibilitychange", () => { if (!document.hidden) setTimeout(radTick, 1500); });

/* 👋 */
async function radWave(who) {
  clLoad(); const p = clPerson(who);
  if (Date.now() - (radWaveAt[p.pid] || 0) < 4000) return p;
  radWaveAt[p.pid] = Date.now();
  await clSend(p.pid, "👋", [], "msg", { wave: 1 });
  D.vibrate(18); radFly(p.pid);
  return p;
}
function radWaveIn(pid, name) {
  const x = radPeople().find(o => o.p.pid === pid), first = radFirst(name);
  const line = `${first} машет вам 👋` + (x && x.km != null ? (x.km < 0.05 ? " — совсем рядом" : ` — ${radKm(x.km)} ${radDir(x.deg)}`) : "");
  if (document.hidden) { D.notify("👋 " + first, "машет вам"); return; }
  D.vibrate(40);
  if ($("#radar")) { radRipple(pid, 3); toast(line, 3600); }
  else if (!busy && state === "idle") showBot(line);
  else toast(line, 3600);
  if (!busy && state === "idle" && !(S.close && S.close.speak === false)) say(`${first} машет вам!`);
}

/* текст для модели: «где мама?» — только по радару, без адресов */
async function radWhereText(who) {
  const p = clPerson(who), g = ((clLoad().geo || {})[p.pid]);
  const live = g && (g.until === -1 || g.until > Date.now());
  if (!live) return `${p.name} сейчас не показывает вам, где находится. Скажи это одной фразой и что можно позвать на радар: «Близкие» → «Рядом» → «Позвать».`;
  let me = radMe && Date.now() - radMe.ts < 180000 ? radMe : null;
  if (!me) try { me = await myPlace(120, false); } catch (e) { me = null; }
  if (!me) return `Место ${p.name} обновлено ${radAgo(g.ts, true)}, но где сейчас вы — телефон не знает (нет разрешения на местоположение). Скажи, что расстояние будет видно, если разрешить место в «Близкие» → «Рядом».`;
  const [km, deg] = radGeo(me, g);
  return `${p.name}: ${km < 0.05 ? "совсем рядом с вами" : `в ${radKmSay(km)} от вас, ${radDir(deg)}`}${g.acc > 500 ? " (примерно)" : ""}; место обновлено ${radAgo(g.ts, true)}. Скажи коротко — расстояние и сторону; адресов и улиц не называй.`;
}

/* экран */
const radR = (km) => 46 + 132 * Math.max(0, Math.min(1, Math.log10(Math.max(km, 0.05) / 0.05) / Math.log10(600)));
const RAD_REDUCE = matchMedia("(prefers-reduced-motion: reduce)");
function radRender() {
  const body = $("#rad-body"); if (!body) return;
  const st = clLoad(), cfg = radCfg(), on = radOn();
  if (!st.people.length) {
    body.innerHTML = `<div class="card"><b>Сначала — близкие</b><p class="hint" style="margin:6px 0 10px">На радаре — близкие, которые сами решили показать вам, где они. Пригласите близкого, и сможете видеть друг друга и махать рукой.</p><button class="btn p w" id="rad-go">Пригласить</button></div>`;
    $("#rad-go").onclick = () => clInviteOpen(); return;
  }
  const ppl = radPeople(), seen = cfg.to.map(pid => st.people.find(p => p.pid === pid)).filter(Boolean).map(p => esc(radFirst(p.name)));
  const chip = on ? `<i class="dot"></i><span>${seen.length === 1 ? "Вас видит" : "Вас видят"} <b>${radList(seen.map(s => s)).replace(/, | и /g, m => `</b>${m}<b>`)}</b> · ${radUntil(cfg.until)}</span><button id="rad-edit">${radEdit ? "Отмена" : "Изменить"}</button>`
    : `<i class="dot"></i><span>Вас никто не видит</span><button id="rad-edit" class="${radEdit ? "" : "go"}">${radEdit ? "Отмена" : "Показать себя"}</button>`;
  const rr = [0.3, 3, 30].map(radR);
  const rings = rr.map(r => `<circle cx="180" cy="180" r="${r.toFixed(1)}"/>`).join("")
    + [["300 м", rr[0]], ["3 км", rr[1]], ["30 км", rr[2]]].map(([t, r]) => `<text x="${(180 - r + 5).toFixed(1)}" y="176">${t}</text>`).join("");
  body.innerHTML = `<div class="rad-seen${on ? " on" : ""}">${chip}</div>${radEdit ? radEditor() : ""}
    <div class="rad-wrap"><div class="radar${radMe ? "" : " nome"}" id="radar">
      <svg class="rad-rings" viewBox="0 0 360 360" aria-hidden="true">${rings}</svg>
      <div class="rad-sweep" id="rad-sweep"></div><div class="rad-n" id="rad-n" aria-hidden="true">С</div>
      <div class="rad-me" aria-label="Вы">Я</div><div id="rad-ppl"></div></div>
      <button class="ib soft rad-cmp${radCompass ? " on" : ""}" id="rad-cmp" aria-pressed="${radCompass}" aria-label="Повернуть радар по компасу" title="По компасу"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="m15.5 8.5-2 5-5 2 2-5z"/></svg></button></div>
    <div id="rad-card"></div><div id="rad-rest"></div>
    <p class="hint rad-priv">Место шифруется на телефоне — сервер Dewiar его не видит. Близкие видят только расстояние и сторону, пока вы разрешили; ваш компьютер с Dewiar — тоже, чтобы радар был и там. Обновляется, когда Dewiar открыт.</p>`;
  $("#rad-edit").onclick = () => { radEdit = !radEdit; radEditSel = null; radEditMode = cfg.until === -1 ? "always" : "hour"; radRender(); };
  $("#rad-cmp").onclick = () => radCompassSet(!radCompass);
  if (radEdit) radEditBind();
  // люди на радаре
  const sel = ppl.find(o => o.p.pid === radSel && o.km != null) || ppl.find(o => o.km != null && Date.now() - o.g.ts < RAD_STALE) || ppl.find(o => o.km != null);
  if (sel) radSel = sel.p.pid;
  $("#rad-ppl").innerHTML = ppl.filter(o => o.km != null).map(o => {
    const stale = Date.now() - o.g.ts > RAD_STALE;
    return `<button class="rad-p${stale ? " stale" : ""}${o.p.pid === radSel ? " sel" : ""}" data-pid="${esc(o.p.pid)}" style="--c:${clCol(o.p.pid)}" aria-label="${esc(o.p.name)}: ${radKm(o.km)} ${radDir(o.deg)}">
      <i class="clava">${esc((o.p.name || "?")[0].toUpperCase())}</i><span><b>${esc(radFirst(o.p.name))}</b>${radKm(o.km)}${stale ? " · " + radAgo(o.g.ts) : ""}</span></button>`;
  }).join("");
  $$("#rad-ppl .rad-p").forEach(b => b.onclick = () => { radSel = b.dataset.pid; $$("#rad-ppl .rad-p").forEach(x => x.classList.toggle("sel", x === b)); radCard(); });
  radPlace(); radCard();
  // кто не показал себя — позвать
  const rest = st.people.filter(p => !ppl.some(o => o.p.pid === p.pid));
  const asked = cfg.asked || {};
  $("#rad-rest").innerHTML = rest.length ? `<h3>Ещё не на радаре</h3>` + rest.map(p => {
    const was = Date.now() - (asked[p.pid] || 0) < 3600e3, can = (p.devs || []).length;
    return `<div class="clp rad-rp"><i class="clava" style="--c:${clCol(p.pid)}">${esc((p.name || "?")[0].toUpperCase())}</i><span><b>${esc(p.name)}</b><small>${can ? "пока не показывает, где он" + (/а$|я$/i.test(radFirst(p.name)) ? "а" : "") : "ещё не открывал Dewiar"}</small></span>
      ${can ? `<button class="btn rad-ask" data-pid="${esc(p.pid)}" ${was ? "disabled" : ""}>${was ? "Позвали" : "Позвать"}</button>` : ""}</div>`;
  }).join("") : "";
  $$(".rad-ask").forEach(b => b.onclick = async () => {
    b.disabled = true;
    try {
      const p = clPerson(b.dataset.pid);
      await clSend(p.pid, "📍 Покажешь мне, где ты? В Dewiar: «Близкие» → «Рядом» → «Показать себя». Я тебе тоже покажу.", []);
      S.radar = Object.assign(radCfg(), { asked: Object.assign({}, radCfg().asked, { [p.pid]: Date.now() }) }); saveS();
      b.textContent = "Позвали"; toast(`Позвали ${radFirst(p.name)} на радар`);
    } catch (e) { b.disabled = false; toast(e.message, 4000); }
  });
  radLoop();
}
function radPlace() {                                     // по местам: угол — с поправкой на компас, близко стоящих раздвигаем
  const rot = radCompass && radHead != null ? radHead : 0, ppl = radPeople().filter(o => o.km != null);
  const pts = ppl.map(o => ({ pid: o.p.pid, r: radR(o.km), a: o.deg - rot }));
  for (let pass = 0; pass < 3; pass++) for (let i = 0; i < pts.length; i++) for (let j = i + 1; j < pts.length; j++) {
    const xy = (q) => [q.r * Math.sin(q.a * Math.PI / 180), -q.r * Math.cos(q.a * Math.PI / 180)];
    const [x1, y1] = xy(pts[i]), [x2, y2] = xy(pts[j]);
    if (Math.hypot(x1 - x2, y1 - y2) < 44) { pts[j].a += 16 * (pass % 2 ? -1 : 1); pts[i].a -= 6; }
  }
  for (const q of pts) {
    const b = $(`#rad-ppl .rad-p[data-pid="${CSS.escape(q.pid)}"]`); if (!b) continue;
    b.style.left = ((180 + q.r * Math.sin(q.a * Math.PI / 180)) / 3.6) + "%"; b.style.top = ((180 - q.r * Math.cos(q.a * Math.PI / 180)) / 3.6) + "%";
    b.dataset.a = String(((q.a % 360) + 360) % 360);
  }
  const n = $("#rad-n"); if (n) { const a = -rot * Math.PI / 180; n.style.left = (50 + 49.5 * Math.sin(a)) + "%"; n.style.top = (50 - 49.5 * Math.cos(a)) + "%"; }
  const s = $("#rad-card .rad-arr"); if (s) { const o = ppl.find(x => x.p.pid === radSel); if (o) s.style.setProperty("--deg", (o.deg - rot) + "deg"); }
}
function radCard() {
  const box = $("#rad-card"); if (!box) return;
  if (!radMe) {
    const e = radErr || { kind: radCan() ? "wait" : "perm" };
    box.innerHTML = `<div class="card rad-need">${e.kind === "wait" ? `<b>Определяю, где вы…</b><p class="hint">Чтобы показать расстояния до близких.</p>`
      : e.kind === "off" ? `<b>Местоположение выключено</b><p class="hint">Включите его в настройках телефона — тогда на радаре будет видно, кто рядом.</p>${D.locSettings ? `<button class="btn p w" id="rad-set">Открыть настройки</button>` : ""}`
      : e.kind === "none" ? `<b>Здесь место не определяется</b><p class="hint">Радар работает на телефоне и в браузере, который умеет определять место.</p>`
      : e.kind === "perm" ? `<b>Где вы — чтобы видеть, кто рядом</b><p class="hint">Место нужно, чтобы считать расстояния на этом экране. Близким оно уходит, только если вы сами покажете себя.</p><button class="btn p w" id="rad-allow">Разрешить определять место</button>`
      : `<b>Место не определилось</b><p class="hint">${esc(e.msg || "")}</p><button class="btn w" id="rad-allow">Попробовать ещё</button>`}</div>`;
    if ($("#rad-allow")) $("#rad-allow").onclick = () => { radErr = { kind: "wait" }; radCard(); radLocate(true); };
    if ($("#rad-set")) $("#rad-set").onclick = () => D.locSettings();
    if (radCan() && !radErr) radLocate(false);
    return;
  }
  const o = radPeople().find(x => x.p.pid === radSel && x.km != null);
  if (!o) { box.innerHTML = `<p class="hint rad-empty">Пока никто из близких не показал вам, где он. Покажите себя — и позовите их на радар.</p>`; return; }
  const p = o.p, stale = Date.now() - o.g.ts > RAD_STALE, call = (p.devs || []).length && window.DewiarCall;
  box.innerHTML = `<div class="rad-sel" style="--c:${clCol(p.pid)}"><div class="h"><i class="clava">${esc((p.name || "?")[0].toUpperCase())}</i>
      <div><b>${esc(p.name)}</b><small>${stale ? "последний раз — " + radAgo(o.g.ts) : "обновлено " + radAgo(o.g.ts)}</small></div></div>
    <div class="rad-dist"><strong>${o.g.acc > 500 && o.km >= 0.05 ? "≈ " : ""}${radKm(o.km)}</strong><em>${o.km < 0.05 ? "совсем рядом" : radDir(o.deg)}</em>
      ${o.km >= 0.05 ? `<svg class="rad-arr" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3 7 20l5-4 5 4z"/></svg>` : ""}</div>
    <div class="rad-acts"><button class="rad-wave" id="rad-wave">👋 Помахать</button><button id="rad-msg">Написать</button>${call ? `<button id="rad-call">Позвонить</button>` : ""}</div></div>`;
  radPlace();
  $("#rad-wave").onclick = async () => { const b = $("#rad-wave"); b.disabled = true;
    try { const q = await radWave(p.pid); toast(`Помахали: ${radFirst(q.name)} увидит и услышит 👋`); } catch (e) { toast(e.message, 4000); }
    setTimeout(() => { if (b.isConnected) b.disabled = false; }, 1500); };
  $("#rad-msg").onclick = () => { clCur = p.pid; clRender(); };
  if ($("#rad-call")) $("#rad-call").onclick = () => clCall(p.pid, false).catch(e => toast(e.message, 4000));
}
function radEditor() {
  const st = clLoad(), cfg = radCfg(), sel = radEditSel || (radEditSel = new Set(cfg.to.filter(pid => st.people.some(p => p.pid === pid))));
  if (!sel.size && st.people.length === 1) sel.add(st.people[0].pid);          // один близкий — уже отмечен
  const modes = [["hour", "На час"], ["eve", radEve()[0]], ["always", "Всегда"]];
  return `<div class="card rad-ed"><b>Кому показать, где вы</b><small class="rad-ask" id="rad-ask">Нажмите на близких — отметятся галочкой</small>
    <div class="rad-who" id="rad-who">${st.people.map(p => `<button class="rad-pick${sel.has(p.pid) ? " on" : ""}" data-pid="${esc(p.pid)}" aria-pressed="${sel.has(p.pid)}"><i class="clava" style="--c:${clCol(p.pid)}">${esc((p.name || "?")[0].toUpperCase())}</i><span>${esc(radFirst(p.name))}</span></button>`).join("")}</div>
    <div class="rad-time" role="radiogroup" aria-label="На сколько">${modes.map(([k, t]) => `<button data-m="${k}" role="radio" aria-checked="${radEditMode === k}" class="${radEditMode === k ? "on" : ""}">${t}</button>`).join("")}</div>
    <p class="hint">Отмеченные близкие увидят у себя на радаре, сколько до вас и в какую сторону. Выключить можно в любой момент.</p>
    <div class="row2"><button class="btn p" id="rad-ok" style="flex:1.3">${radOkText(sel.size)}</button>${radOn() ? `<button class="btn" id="rad-hide" style="flex:1">Никому</button>` : ""}</div></div>`;
}
/* 20.10, отзыв: «не мог понять, как добавить близкого — оказывается, нужно на шарик нажать». Подсказка над кружками,
   у неотмеченных «+», на кнопке — сколько отмечено; «Показать» без отмеченных — кружки вздрагивают и подсказка
   становится заметной (а не всплывашка внизу). */
function radOkText(n) { return n ? `Показать ${n} ${n % 10 === 1 && n % 100 !== 11 ? "близкому" : "близким"}` : "Показать"; }
function radEditBind() {
  $$(".rad-pick").forEach(b => b.onclick = () => { const on = !radEditSel.has(b.dataset.pid); if (on) radEditSel.add(b.dataset.pid); else radEditSel.delete(b.dataset.pid);
    b.classList.toggle("on", on); b.setAttribute("aria-pressed", String(on)); $("#rad-ok").textContent = radOkText(radEditSel.size);
    $("#rad-ask").classList.remove("need"); $("#rad-ask").textContent = "Нажмите на близких — отметятся галочкой"; });
  $$(".rad-time button").forEach(b => b.onclick = () => { radEditMode = b.dataset.m; $$(".rad-time button").forEach(x => { x.classList.toggle("on", x === b); x.setAttribute("aria-checked", String(x === b)); }); });
  $("#rad-ok").onclick = async () => {
    const to = [...radEditSel];
    if (!to.length) { const a = $("#rad-ask"), w = $("#rad-who"); a.textContent = "Сначала нажмите на близкого — кому показать"; a.classList.add("need");
      w.classList.remove("need"); void w.offsetWidth; w.classList.add("need"); return; }
    const b = $("#rad-ok"); b.disabled = true;
    const n = await radShare(to, radEditMode); radEdit = false; radRender();
    toast(n ? `Готово: ${radList(to.map(pid => radFirst(clPerson(pid).name)))} ${to.length === 1 ? "видит" : "видят"} вас ${radUntil(radCfg().until)}` : radCan() ? "Покажу, как только определится место" : "Сначала разрешите определять место", 3400);
  };
  if ($("#rad-hide")) $("#rad-hide").onclick = async () => { await radShare([], "off"); radEdit = false; radRender(); toast("Теперь вас никто не видит"); };
}
function radLoop() {                                     // луч: проходя над человеком, «пингует» его
  if (radRaf || RAD_REDUCE.matches) return;
  const t0 = performance.now(), pinged = {};
  const tick = (t) => {
    const sw = $("#rad-sweep");
    if (!sw || document.hidden || !$("#sh-close").classList.contains("on")) { radRaf = 0; return; }
    const a = ((t - t0) / 6000 * 360) % 360; sw.style.transform = `rotate(${a}deg)`;
    $$("#rad-ppl .rad-p:not(.stale)").forEach(b => { const d = (+b.dataset.a - a + 360) % 360;
      if (d < 5 && !pinged[b.dataset.pid]) { pinged[b.dataset.pid] = 1; b.classList.remove("ping"); void b.offsetWidth; b.classList.add("ping"); }
      if (d > 30) pinged[b.dataset.pid] = 0; });
    radRaf = requestAnimationFrame(tick);
  };
  radRaf = requestAnimationFrame(tick);
}
function radAt(pid) { const b = pid && $(`#rad-ppl .rad-p[data-pid="${CSS.escape(pid)}"]`); return b ? [b.style.left, b.style.top] : ["50%", "50%"]; }
function radFly(pid) {
  const R = $("#radar"); if (!R) return;
  const [x, y] = radAt(pid), h = document.createElement("div"); h.className = "rad-fly"; h.textContent = "👋"; R.appendChild(h);
  if (RAD_REDUCE.matches) { h.style.left = x; h.style.top = y; setTimeout(() => h.remove(), 900); return; }
  requestAnimationFrame(() => requestAnimationFrame(() => { h.style.left = x; h.style.top = y; }));
  setTimeout(() => { h.style.opacity = 0; radRipple(pid, 1); setTimeout(() => h.remove(), 500); }, 1100);
}
function radRipple(pid, n) {
  const R = $("#radar"); if (!R) return;
  const [x, y] = radAt(pid);
  for (let i = 0; i < n; i++) setTimeout(() => { const r = document.createElement("div"); r.className = "rad-rip"; r.style.left = x; r.style.top = y;
    r.style.setProperty("--c", pid ? clCol(pid) : "#8B8CF7"); R.appendChild(r); setTimeout(() => r.remove(), 1500); }, i * 350);
}
function radCompassSet(on) {
  const h = radCompassSet.h || (radCompassSet.h = (e) => {
    const d = e.webkitCompassHeading != null ? e.webkitCompassHeading : (e.absolute || e.type === "deviceorientationabsolute") && e.alpha != null ? 360 - e.alpha : null;
    if (d == null || !radCompass) return;
    radHead = d; if (!radCompassSet.q) radCompassSet.q = requestAnimationFrame(() => { radCompassSet.q = 0; radPlace(); });
  });
  radCompass = on;
  if (on) {
    const go = () => { window.addEventListener("deviceorientationabsolute", h); window.addEventListener("deviceorientation", h);
      setTimeout(() => { if (radCompass && radHead == null) { toast("Компас на этом телефоне не нашёлся"); radCompassSet(false); } }, 2500); };
    if (window.DeviceOrientationEvent && typeof DeviceOrientationEvent.requestPermission === "function") DeviceOrientationEvent.requestPermission().then(r => r === "granted" ? go() : radCompassSet(false), () => radCompassSet(false));
    else go();
  } else { window.removeEventListener("deviceorientationabsolute", h); window.removeEventListener("deviceorientation", h); radHead = null; }
  const b = $("#rad-cmp"); if (b) { b.classList.toggle("on", on); b.setAttribute("aria-pressed", String(on)); }
  radPlace();
}
async function clSaveFile(p, m, j) {
  const f = (m.f || [])[j]; if (!f || m.out) return;
  try {
    toast("Скачиваю «" + f.name + "»…");
    const d = await clReq("GET", "/close/file", null, "&b64=1&id=" + encodeURIComponent(f.id));
    const bytes = DC().unseal(DC().b64d(f.key), Uint8Array.from(atob(d.b64), c => c.charCodeAt(0)));
    const where = D.saveDownloadB64 ? D.saveDownloadB64(f.name, f.type || "application/octet-stream", clStdB64(bytes)) : "";
    f.saved = true; clSave(); clRender(); toast(where ? "Сохранено: " + where : "Сохранено", 4000);
  } catch (e) { toast("Не скачался: " + e.message, 4000); }
}
$("#b-close").onclick = () => openClose("");
$("#cl-inv").onclick = () => { if (clTab === "ref") return refShare().catch(e => toast(e.message, 4000)); clInviteOpen(); };
document.addEventListener("visibilitychange", () => { if (!document.hidden && syncCred()) { clPoll(); noteAttSoon(6000); } });
setTimeout(() => { clLoad(); clBadge(); if (S.closePending && syncCred()) clAcceptLink(S.closePending); clPoll(); clSchedule(); noteAttSoon(9000); }, 4000);
setTimeout(tmrShow, 700);                                       // идущие таймеры — сразу после запуска
N.on("alarms", () => { tmrShow(); syncSoon(); });               // отменили таймер в шторке (AlarmReceiver)
N.on("resume", () => tmrShow());

/* ---------- «сам замечает»: открыли приложение после перерыва — коротко о главном (как core/presence.py) ----------
   Перерыв считается от того, когда приложение последний раз было на экране (S.welcome.seen). Первый раз за день после 3 часов —
   короткая сводка дня; после 30 минут — только если есть что сказать: готовые с тех пор задачи, задача ждёт ответа, скоро
   напоминание. Ночью (23–7), чаще раза в 40 минут, если человек сам заговорил или приложение открыли кнопкой помощника — молчим. */
let lastUserAct = 0;
function welcomePlan(now, seen, lastGreet, tasks, alarms, dstat, eveSaid) {
  const h = new Date(now).getHours();
  if (!seen || h >= 23 || h < 7) return null;
  if (lastGreet && now - lastGreet < 40 * 60000) return null;
  const gone = now - seen;
  if (gone < 30 * 60000) return null;
  const facts = [], since = new Date(seen).toISOString().slice(0, 19);
  const done = tasks.filter(t => t.status === "done" && String(t.updated || "") >= since), wait = tasks.filter(t => t.status === "waiting");
  if (done.length) facts.push("Пока пользователя не было, готовы задачи: " + done.slice(0, 3).map(t => `«${t.title}»`).join("; ") + ".");
  if (wait.length) facts.push("Ждёт ответа пользователя задача: " + wait.slice(0, 2).map(t => `«${t.title}»`).join("; ") + ".");
  const soon = alarms.filter(a => a.kind !== "timer" && a.at > now && a.at - now < 2 * 3600000).sort((a, b) => a.at - b.at);
  const hm = (t) => { const d = new Date(t); return pad(d.getHours()) + ":" + pad(d.getMinutes()); };
  if (soon.length) facts.push("Скоро: " + soon.slice(0, 3).map(a => `в ${hm(a.at)} — ${a.title}`).join("; ") + ".");
  const goneTxt = gone < 3600000 ? Math.round(gone / 60000) + " мин" : Math.floor(gone / 3600000) + " ч";
  // вечер (с 19:00) и сегодня есть сделанные дела — итог дня, один раз за вечер (отзыв 13.10: «в конце дня — ты сегодня сделал 5–7 дел»)
  if (dstat && dstat.today && h >= 19 && eveSaid !== dayKey(now)) {
    facts.unshift(`Сегодня пользователь отметил сделанными ${dstat.today} ${delaRu(dstat.today)}: ${dstat.items.slice(-7).map(x => "«" + x.title + "»").join(", ")}.`
      + (dstat.streak >= 2 ? ` Серия: ${dstat.streak} ${dnRu(dstat.streak)} подряд.` : ""));
    return { kind: "eve", facts, gone: goneTxt };
  }
  const firstToday = (!lastGreet || new Date(lastGreet).toDateString() !== new Date(now).toDateString()) && gone >= 3 * 3600000;
  if (firstToday) {
    const today = alarms.filter(a => a.kind !== "timer" && a.at > now && new Date(a.at).toDateString() === new Date(now).toDateString()).sort((a, b) => a.at - b.at);
    if (today.length) facts.push("Напоминания и будильники на сегодня: " + today.slice(0, 5).map(a => `${hm(a.at)} ${a.title}`).join("; ") + ".");
    return { kind: "day", facts, gone: goneTxt };
  }
  return facts.length ? { kind: "back", facts, gone: goneTxt } : null;
}
function welcomePrompt(p) {
  const d = new Date(), wd = ["воскресенье", "понедельник", "вторник", "среда", "четверг", "пятница", "суббота"][d.getDay()];
  if (p.kind === "eve") return p.facts.join("\n") + `\n\n[Вечер, пользователь вернулся в приложение, не было ${p.gone}] Подведи итог дня: скажи, сколько дел он сегодня сделал, похвали тепло и конкретно (назови одно-два дела своими словами); если есть другие новости отсюда — одной фразой. 2–3 коротких предложения, без списков, без вопросов в конце, без инструментов.`;
  if (p.kind === "day") return `Сегодня ${d.toLocaleDateString("ru-RU")}, ${wd}, сейчас ${pad(d.getHours())}:${pad(d.getMinutes())}.\n` + p.facts.join("\n")
    + `\n\n[Пользователь открыл приложение — первый раз за день, не было ${p.gone}] Поздоровайся первым (в своём роде), по имени, если знаешь, и коротко скажи главное на сегодня из этих данных. 2–3 коротких предложения, живо и тепло, без списков, без вопросов в конце, без инструментов.`;
  return p.facts.join("\n") + `\n\n[Пользователь вернулся в приложение, не было ${p.gone}] Коротко поприветствуй и скажи главное из этого — 1–2 коротких предложения, живо, без списков и без вопросов в конце, без инструментов.`;
}
async function welcomeCheck(shownAt) {
  const w = S.welcome || {};
  if (w.on === false || busy || state !== "idle" || lastUserAct > shownAt || document.hidden) return false;
  const p = welcomePlan(Date.now(), w.seen, w.at, Object.values(mind().tasks || {}), JSON.parse(D.alarms() || "[]"), doneStats(), w.eve);
  if (!p) return false;
  await ensureBrain();
  if (!S.llm.base_url || busy || lastUserAct > shownAt) return false;
  S.welcome = Object.assign({}, w, { at: Date.now() }, p.kind === "eve" ? { eve: dayKey(Date.now()) } : {}); saveS();
  plog("info", `👋 ${p.kind === "day" ? "сводка дня" : p.kind === "eve" ? "итог дня" : "с возвращением"} (не было ${p.gone})`);
  ask(welcomePrompt(p), { hidden: true });
  return true;
}
function welcomeSeen() { S.welcome = Object.assign({}, S.welcome || {}, { seen: Date.now() }); saveS(); }
let welcomeT = 0;
function welcomeArm(byIntent) {                   // приложение на экране: через 6 с (успели синхронизироваться) — проверить
  const shownAt = Date.now(), seen = (S.welcome || {}).seen;
  clearTimeout(welcomeT);
  if (!byIntent) welcomeT = setTimeout(() => welcomeCheck(shownAt).finally(welcomeSeen), 6000);
  else welcomeSeen();
  return seen;
}
document.addEventListener("visibilitychange", () => { if (document.hidden) { clearTimeout(welcomeT); welcomeSeen(); } else welcomeArm(false); });
addEventListener("pagehide", welcomeSeen);
setInterval(() => { if (!document.hidden) welcomeSeen(); }, 60000);     // пока открыто — «последний раз видели» свежее

(function boot() {
  applyPersona(); setState("idle"); quietCheck();
  const last = history.filter(m => m.role === "assistant").slice(-1)[0];
  if (D.web && (S.llm.trial || trialOn()) && !loggedIn()) {
    // веб-версия без входа: говорим сразу (пробный разговор); войти — без ограничений и с действиями
    showBot(gfix(`Привет! Я ${persona().name}. Давайте поговорим прямо сейчас — без входа и установки. Нажмите на меня и говорите или напишите.`));
    showCard(`<div class="start"><button class="btn w" onclick="startLogin()">Войти — без ограничений и с делами</button></div>`);
  } else if (!S.llm.base_url && !loggedIn()) {
    // первый запуск: одна понятная кнопка (отзыв: «не понимаю, как ей мозг включить») — бесплатная проба Dewiar;
    // своя модель, ключ сервиса и код с другого устройства — второй кнопкой
    if (S.join) { showBot(gfix(`Привет! Я ${persona().name}. Заявка отправлена — как только её одобрят, я подключусь сама и скажу. Обычно это быстро.`)); setTimeout(() => joinPoll(false).catch(() => {}), 2500); }
    else showBot(gfix(`Привет! Я ${persona().name}. Чтобы мы могли поговорить, меня нужно один раз подключить — это бесплатно и займёт минуту.`));
    showCard(S.join ? `<div class="row2"><button class="btn p" onclick="joinPoll(true).then(d => d && !d.key && toast((d && d.text) || 'Пока ждёт проверки')).catch(e => toast(e.message))" style="flex:1">Проверить</button><button class="btn" onclick="openBrain()" style="flex:1">Другие способы</button></div>`
      : `<div class="start"><button class="btn p w" onclick="openBrain('join')">Подключить бесплатно</button><button class="btn w" onclick="openBrain('dwkey')">Dewiar уже есть на компьютере — ввести код</button><button class="btn w ghost" onclick="openBrain()">Свой ключ или своя модель</button></div>`); }
  // последний ответ — только свежий (до 20 минут): старый («С возвращением. В 15:00 встреча…» с утра) после каждого
  // запуска и обновления выглядел как новое сообщение (отчёты №52, №53). Он в истории разговора — там его и видно.
  else if (last && last.t && Date.now() - last.t < 20 * 60e3) showBot(last.content.slice(0, 400));
  const it = D.takeIntent(); if (it) { try { handleIntent(JSON.parse(it)); } catch (e) { } }
  welcomeArm(!!it);                                // открыли кнопкой помощника — сразу слушаем, не здороваемся
  if (S.llm.base_url && !it) needPerm(MIC);
  setTimeout(hReady, 0);                           // экран и персонаж готовы — запуск записан для «Здоровья»
  setTimeout(() => { try { doneInbox(); } catch (e) { } }, 300);   // «Сделано ✓» из уведомлений, пока приложение было закрыто
  setTimeout(() => { try { newsCheck(); } catch (e) { } }, 1200);  // обновились — «Что нового»
  setTimeout(() => { try { if (!document.querySelector(".sheet.on") && window.examCleanCheck) examCleanCheck(); } catch (e) { } }, 4000);   // следы старых экзаменов
  if (!D.web) setTimeout(() => checkUpdate(false), 8000);   // веб-версия всегда свежая: её отдаёт сайт
  setTimeout(() => accountCheck().then(ensureBrain).then(cloudCaps).then(tgSync), 3000);
  setTimeout(() => syncRun(false), 4000);
  setTimeout(() => radio.refresh(), 10000);
  // радио одно на приложение и переживает пересоздание экрана (Radio.java) — подхватываем, что сейчас играет
  try { const r = JSON.parse(D.radioState() || "{}"); if (r.state) N.ev({ type: "radio", state: r.state, name: r.name || "", error: r.error || "" }); } catch (e) { }
})();
