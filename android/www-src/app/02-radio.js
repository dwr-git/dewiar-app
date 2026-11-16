//@ Телефон и веб-версия, часть 02: радио: играет внутри приложения.
//@ Собирается в android/assets/www/app.js (tools/app_join.py) — порядок частей = порядок исполнения; шапка «//@» в app.js не попадает.
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
    if (!l.length) l = norm(window.RADIO_LIST);
    const fav = norm((typeof S !== "undefined" && S.radio_fav) || []), fu = new Set(fav.map(x => x.url));   // «Мои станции» (radiopage.js) — и голосом по названию
    return fav.concat(l.filter(x => !fu.has(x.url)));
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
  async function search(query, limit) {         // каталог radio-browser: ~50 000 станций, популярные сверху, нерабочие скрыты
    const ws = words(query).filter(w => !FILLER.has(w));
    let tag = ""; for (const w of ws) for (const k in GENRE_EN) if (!tag && w.startsWith(k)) tag = GENRE_EN[k];
    const p = new URLSearchParams({ limit: String(limit || 8), hidebroken: "true", order: "clickcount", reverse: "true" });
    if (tag) p.set("tag", tag); else if (ws.length) p.set("name", ws.join(" ")); else p.set("countrycode", "RU");
    let last = "";
    for (const base of API) {
      try {
        const r = await http("GET", base + "/json/stations/search?" + p, { headers: { "User-Agent": "Dewiar-Android (voice assistant)" }, timeout: 10000 });
        if (r.status !== 200) { last = "ответ " + r.status; continue; }
        return JSON.parse(r.body).filter(x => x.url_resolved || x.url).map(x => ({ name: String(x.name || "").trim(), url: x.url_resolved || x.url, tags: String(x.tags || ""), aliases: [],
          country: String(x.countrycode || ""), logo: /^https?:\/\//.test(String(x.favicon || "")) ? String(x.favicon) : "" }));
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
    if (cur && (!s0 || cur.url !== s0.url)) prevCur = cur;
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
  function remember(s) { played = [s.url, ...played.filter(u => u !== s.url)].slice(0, 8);
    if (prevCur && prevCur.url !== s.url && !backing) back = [...back.filter(x => x.url !== prevCur.url), prevCur].slice(-10); }
  /* идея №170 (09.11: «переключать треки в проигрывателе на телефоне»): «предыдущая» — станция, что играла до этой
     (стек back: каждая новая кладёт прежнюю; «назад» снимает) */
  let back = [], prevCur = null, backing = false;
  async function prev() {
    if (!cur && st.name) cur = list().find(x => x.name === st.name) || null;
    const s = back.pop();
    if (!s) return { ok: false, text: "Раньше этой ничего не играло — скажите «дальше» или назовите станцию." };
    backing = true; prevCur = null;
    try { const r = await playOne(s); if (!r.ok && !r.superseded) back.push(s); return r; } finally { backing = false; }
  }
  async function playOne(s) {                     // «Радио» (radiopage.js): нажали плитку — именно эта станция, без подмены
    const op = ++opSeq; usedAt = Date.now();
    const r = await start(s);
    if (r.state === "superseded" || op !== opSeq) return { ok: false, superseded: true, text: "" };
    if (r.state === "playing") { cur = s; remember(s); delete bad[s.url]; found = []; return { ok: true, station: s }; }
    bad[s.url] = Date.now(); D.radioStop();
    return { ok: false, text: `«${s.name}» не играет: ${r.error || "не отвечает"}. Попробуйте другую станцию.` };
  }
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
  return { play, playOne, search, next, prev, pause, resume, stop, on, playing, recent, render, refresh, match, list, resumeAfterTalk, state: () => st, current: () => cur, back: () => back.slice() };
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
/* id записи (заметка, трата, напоминание…): время и случайный хвост — две записи в одну миллисекунду («запиши 5 и 100»
   одной фразой) получали один id и затирали друг друга, а синхронизация теряла их (рецензия 04.11: из 40 трат — 8 id) */
const uid = (p) => (p || "") + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
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
/* №607 (07.11): «пришёл к другу — телефон в его Wi-Fi, интернет есть, а Лира не видит; на мобильном всё заработало». Адрес в
   домашней сети (компьютер, LM Studio, свой сервер) из чужой сети не виден — так и задумано. Где телефон сейчас -> "wifi" (в
   другой сети Wi-Fi: ни один его адрес не из сети этого адреса), "mobile" (Wi-Fi нет) или "" (та же сеть или не узнать). */
function lanAway(url) {
  const m = /^https?:\/\/(\d+\.\d+\.\d+)\.\d+/.exec(url || ""); if (!m || !D.lanIps) return "";
  let own = []; try { own = JSON.parse(D.lanIps() || "[]") || []; } catch (x) { return ""; }
  const wifi = own.filter(x => x && x.wifi && /^\d+\.\d+\.\d+\.\d+$/.test(x.ip || ""));
  if (!wifi.length) return own.length ? "mobile" : "";
  return wifi.some(x => x.ip.startsWith(m[1] + ".")) ? "" : "wifi";
}
function awayText(url) {
  const w = lanAway(url), host = (/^https?:\/\/([^/]+)/.exec(url || "") || [])[1] || "";
  if (!w) return "";
  return `${host} — адрес в домашней сети, а телефон сейчас ${w === "wifi" ? "в другой сети Wi-Fi (в гостях, на работе)" : "на мобильном интернете"}. `
    + "Так и задумано: напрямую телефон видит его только в той же сети Wi-Fi. Вне дома нужен путь через интернет — в «Мозге» выберите Dewiar Облако (или сервер с адресом в интернете)";
}
function netErr(e, url) {
  e = String(e || "");
  const home = HOME_URL.test(url || "");
  if (home && !/^https?:\/\/(?:127\.|localhost\b)/i.test(url || "") && /Unable to resolve|UnknownHost|No address|timeout|timed out|after \d+\s*ms|Load failed|Failed to fetch|ECONNREFUSED|refused|failed to connect|reset|closed|EOF|abort|unreachable|EHOSTUNREACH|ENETUNREACH/i.test(e)) {
    const aw = awayText(url); if (aw) return aw;
  }
  // №229 (24.10): «Failed to connect to /127.0.0.1:1234» — 127.0.0.1 на телефоне — это сам телефон, а LM Studio — на компьютере
  if (/^https?:\/\/(?:127\.|localhost\b)/i.test(url || "") && /refused|failed to connect|timeout|timed out/i.test(e))
    return "адрес 127.0.0.1 — это сам телефон, а модель работает на компьютере. В «Мозге» впишите адрес компьютера в домашней сети (например, 192.168.1.5:1234 — он есть в LM Studio или Ollama)";
  // YouTube 27.10: свой сервер с самоподписанным сертификатом — «Trust anchor for certification path not found»
  if (/Trust anchor|CertPathValidator|certification path|SSLHandshake|self.signed|CERT_/i.test(e))
    return "сертификат сервера не подписан известным центром (свой или самоподписанный). Поставьте его в телефон: Настройки → Безопасность → "
      + "Шифрование и учётные данные → Установить сертификат → «Сертификат ЦС» — и Dewiar будет ему доверять. Или откройте сервер по http в домашней сети";
  if (/Unable to resolve|UnknownHost|No address/i.test(e)) return home ? "домашний сервер не найден (возможно, вы не дома)" : "нет интернета или слабая связь";
  if (/timeout|timed out|after \d+\s*ms/i.test(e)) return home ? "домашний сервер долго не отвечает (возможно, вы не дома)" : (/dewiar\.pro/i.test(url || "") ? "сервер Dewiar долго не отвечает — слабая связь или сейчас много людей сразу" : "сервер долго не отвечает — похоже, слабая связь");
  // веб-версия (пакет 30.10, iPhone: «связь с мозгом: Load failed») — так Safari называет любой обрыв запроса
  if (/^(?:TypeError:\s*)?(?:Load failed|Failed to fetch|NetworkError.*)$/i.test(e.trim()))
    return home ? "домашний сервер не отвечает (возможно, вы не в домашней сети)" : "связь с сервером оборвалась — слабая связь или страница была свёрнута";
  if (/ECONNREFUSED|Connection refused|failed to connect|reset|closed|EOF|connection abort/i.test(e)) return home ? "домашний сервер не отвечает (возможно, вы не в домашней сети)" : "связь с сервером оборвалась";
  return e;
}

