//@ Телефон и веб-версия, часть 14: синхронизация с компьютером через облако.
//@ Собирается в android/assets/www/app.js (tools/app_join.py) — порядок частей = порядок исполнения; шапка «//@» в app.js не попадает.
/* ---------- синхронизация с компьютером через облако Dewiar (cloud.php ?p=/sync) ----------
   Напоминания и будильники, заметки, расходы, память «Обо мне» — одинаковые на телефоне и компьютере. Раз в минуту, пока
   приложение открыто, при открытии и сразу после своих изменений: отправляем то, что поменялось с прошлого раза
   (отпечатки — в pref «sync»), и забираем чужое. Одну запись правили на двух устройствах — остаётся более поздняя правка.
   Запись, которой больше нет в syncSnapshot(), уходит как удаление — и другие устройства её тоже удалят.
   Формат записей, виды (SYNC_KINDS) и порядок обмена — общие с core/sync.py (компьютер) и ?p=/sync в cloud.php:
   меняешь здесь — меняй и там. Дополнительные виды (soul, mind, diary, dayturn, taskreq, task, done) шлём, только если их знает сервер. */
const MIND_MAX = 8000, MIND_CTRL = /[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f\u200b-\u200f\u202a-\u202e\u2066-\u2069]/g;
const mindText = (d) => (d && typeof d.text === "string" && d.text.trim() && d.text.length <= MIND_MAX) ? d.text.replace(MIND_CTRL, "") : "";
const SYNC_KINDS = ["reminder", "note", "money", "memory", "soul", "mind", "diary", "dayturn", "taskreq", "task", "done", "persona", "pmemory", "safe", "client", "doc"];   // doc — «Мои файлы» с компьютера (0.98), только приходят   // client — «Клиенты» (clients.js), только зашифрованными   // safe — сейф шифром мастер-пароля (safe.js)
/* Сквозное шифрование синхронизации (S.sync.e2e, как core/sync.py и core/synckey.py): ключ 32 байта знают только свои
   устройства (pref sync_key; другим своим — конвертом ownShare), личные записи уходят {e2e: 1, c: seal(K, JSON)}.
   Открытыми — метка mind:e2e, задачи для облака (taskreq с cloud) и удаления. */
const E2E_KINDS = ["reminder", "note", "money", "memory", "soul", "mind", "diary", "dayturn", "done", "persona", "vault", "task", "taskreq", "pmemory", "safe", "client", "doc"];
function syncKeyGet() { try { const d = JSON.parse(prefGet("sync_key") || "null"); return d && d.k && DC() && DC().b64d(d.k).length === 32 ? d : null; } catch (e) { return null; } }
function syncKeyAdopt(kb64, at) {
  let k; try { k = DC().b64d(String(kb64 || "")); } catch (e) { return false; }
  if (!k || k.length !== 32) return false;
  const cur = syncKeyGet(); if (cur && (cur.k === kb64 || (+at || 0) <= cur.at)) return false;
  prefSet("sync_key", JSON.stringify({ k: DC().b64e(k), at: +at || Date.now() })); return true;
}
const e2eKey = (ch) => { const c = S.sync && S.sync.e2e && !(ch ? ch.home : !syncCred()) ? syncKeyGet() : null; return c ? DC().b64d(c.k) : null; };   // по Wi-Fi весь обмен и так зашифрован
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
/* «Дома по Wi-Fi» (0.59, core/homehub.py): синхронизация напрямую с компьютером дома, без dewiar.pro. Подключение — код с
   экрана компьютера («Устройства» → «Дома по Wi-Fi»): dewiar://home?u=адреса&t=номер ключа&k=ключ&h=узел&n=имя.
   S.sync.home {u: [адреса], t, k, h, n}. Каждый запрос — seal(K, {ts, n, body}) с заголовком X-Home, ответ — seal(K, …):
   соседи по Wi-Fi не прочтут и не подделают. Компьютер не в той же сети — обмен ждёт; правки копятся и уйдут потом. */
/* Чем синхронизироваться (syncChans): облако (syncCred), если есть вход, и компьютер по Wi-Fi, если подключён. До 04.11
   подключённый Wi-Fi выключал облако совсем — телефон видел только тот компьютер. Облачное — «Близкие», почта своих
   устройств, сотрудники, отчёты — по-прежнему только через syncCred(). */
function syncChans() {
  const out = [], cl = syncCred();
  if (cl) out.push(Object.assign({ key: "sync" }, cl));
  if (homeOn()) { const h = S.sync.home; out.push({ key: "sync_home:" + (h.h || h.t), home: true, token: "home:" + h.h + ":" + h.t, link: "", base: (h.u || [])[0] || "", via: `напрямую по Wi-Fi с «${h.n || "компьютер"}»` }); }
  return out;
}
/* Главный канал (04.11): вход в Dewiar есть — облако (Wi-Fi тогда запасной, см. syncRun), нет — Wi-Fi. via — оба словами. */
function syncChan() {
  const cs = syncChans(); if (!cs.length) return null;
  return cs.length > 1 ? Object.assign({}, cs[0], { via: cs[0].via + ` · дома ещё и по Wi-Fi с «${S.sync.home.n || "компьютер"}»`, both: true }) : cs[0];
}
const homeOn = () => !!(S.sync && S.sync.home && S.sync.home.t && S.sync.home.k);
function homeLinkParse(link) {
  const m = /^dewiar:\/\/home\?(.+)$/.exec(String(link || "").trim()); if (!m) return null;
  const q = {}; m[1].split("&").forEach(p => { const i = p.indexOf("="); if (i > 0) q[p.slice(0, i)] = decodeURIComponent(p.slice(i + 1)); });
  const u = String(q.u || "").split(",").filter(x => /^http:\/\/[\d.]+:\d+\/$/.test(x));
  if (!u.length || !/^[0-9a-f]{6,20}$/.test(q.t || "") || !q.k) return null;
  try { if (DC().b64d(q.k).length !== 32) return null; } catch (e) { return null; }
  return { u, t: q.t, k: q.k, h: String(q.h || "").replace(/[^0-9a-f]/g, "").slice(0, 20), n: String(q.n || "Компьютер").slice(0, 40) };
}
/* Роутер выдал компьютеру другой адрес (0.65; «Дома по Wi-Fi» дальше по списку): прежние адреса молчат — ищем узел в
   своей сети Wi-Fi. Только сеть телефона (/24 его адреса в Wi-Fi; на мобильной связи не ищем), порты — прежние и 8766;
   узнаём по /hello: {dewiar: "home", id} — id узла из кода. Не чаще раза в 10 минут, по 32 запроса разом. -> адрес или "". */
let homeSeekAt = 0;
async function homeSeek() {
  const h = S.sync && S.sync.home;
  if (!h || !h.h || Date.now() - homeSeekAt < 600e3) return "";
  let own = []; try { own = JSON.parse(D.lanIps ? D.lanIps() || "[]" : "[]"); } catch (e) { own = []; }
  const nets = [...new Set(own.filter(x => x && x.wifi).map(x => (/^(\d+\.\d+\.\d+)\.\d+$/.exec(x.ip) || [])[1]).filter(Boolean))].slice(0, 2);
  if (!nets.length) return "";
  homeSeekAt = Date.now();
  const ports = [...new Set((h.u || []).map(u => +((/:(\d+)\/$/.exec(u) || [])[1] || 0)).filter(Boolean).concat([8766]))].slice(0, 3);
  const cands = [];
  nets.forEach(n => { for (let i = 1; i < 255; i++) ports.forEach(pt => { const u = `http://${n}.${i}:${pt}/`; if (!(h.u || []).includes(u)) cands.push(u); }); });
  for (let i = 0; i < cands.length; i += 32) {
    const hit = await Promise.all(cands.slice(i, i + 32).map(async (u) => {
      try { const r = await http("GET", u + "hello", { timeout: 1500 }); const d = JSON.parse(r.body || "{}"); return r.status === 200 && d.dewiar === "home" && d.id === h.h ? u : ""; }
      catch (e) { return ""; } }));
    const f = hit.find(Boolean);
    if (f) { plog("info", "🏠 компьютер нашёлся по новому адресу в сети Wi-Fi"); return f; }
  }
  return "";
}
async function homePost(c, body, again) {          // c.quick — облако живо: только первый адрес и без поиска по сети
  const h = S.sync.home, k = DC().b64d(h.k), urls = c.quick ? [c.base] : [c.base].concat((h.u || []).filter(x => x !== c.base));
  let last = null;
  for (const u of urls) {
    const env = { ts: Date.now(), n: DC().b64e(DC().randomBytes(12)), body };
    let r; try { r = await http("POST", u + "sync", { headers: { "X-Home": h.t, "Content-Type": "text/plain" }, body: DC().b64e(DC().seal(k, DC().utf8(JSON.stringify(env)))), timeout: 30000 }); }
    catch (e) { last = e; continue; }
    if (r.status >= 400) { let d = {}; try { d = JSON.parse(r.body || "{}"); } catch (e) { } return { status: r.status, d }; }
    let d; try { d = JSON.parse(DC().fromUtf8(DC().unseal(k, DC().b64d(String(r.body || "").trim())))); }
    catch (e) { return { status: 502, d: { error: { message: "ответ компьютера не расшифровался — подключите телефон заново" } } }; }
    if (u !== h.u[0]) { h.u = [u].concat(h.u.filter(x => x !== u)); saveS(); }      // этот адрес ответил — он первый
    if (d.hub && Array.isArray(d.hub.urls) && d.hub.urls.length) { const nu = [h.u[0]].concat(d.hub.urls).filter((x, i, a) => a.indexOf(x) === i).slice(0, 6);
      if (nu.join() !== h.u.join()) { h.u = nu; saveS(); } if (d.hub.name && d.hub.name !== h.n) { h.n = d.hub.name; saveS(); } }
    return { status: 200, d };
  }
  if (!again && !c.quick) {                                      // прежние адреса молчат — может, у компьютера новый
    const f = await homeSeek();
    if (f) { h.u = [f].concat((h.u || []).filter(x => x !== f)).slice(0, 6); saveS(); return homePost(Object.assign({}, c, { base: f }), body, true); }
  }
  throw Object.assign(new Error(`компьютер «${h.n || "дома"}» не в этой сети — синхронизируется, когда телефон и компьютер будут в одном Wi-Fi`
    + (lanAway(c.base) === "wifi" ? " (сейчас телефон в другой сети Wi-Fi — в гостях напрямую компьютер не виден, так и задумано; связь везде — «Устройства» → «Через dewiar.pro»)" : "")), { home: true, net: true, cause: last });
}
async function homeClaim(link) {
  const p = homeLinkParse(link); if (!p) throw new Error("это не код компьютера для синхронизации по Wi-Fi");
  const was = S.sync && S.sync.home;
  S.sync = Object.assign({}, S.sync, { home: p, on: true }); saveS();
  try { await syncRun(true); const h = (syncStatus.chans || []).find(x => x.home);
    if (!h || h.ok !== true) throw new Error((h && h.error) || syncStatus.error || "компьютер не ответил"); }
  catch (e) { S.sync = Object.assign({}, S.sync, { home: was || null }); saveS(); throw e; }
  plog("info", "🏠 подключено к компьютеру по Wi-Fi: " + p.n);
  return p;
}
function homeForget() { S.sync = Object.assign({}, S.sync, { home: null }); saveS(); syncStatus = { ok: null, at: 0, error: "", devices: [], counts: {} }; DEVS = null; syncSoon(); }
async function homeClaimFlow(link) {
  if (kidsOn()) { showBot("В детском режиме устройства подключает взрослый.", "err"); return; }
  const p = homeLinkParse(link); if (!p) { showBot("Это не код компьютера для синхронизации по Wi-Fi.", "err"); return; }
  if (!confirm(`Синхронизировать этот телефон с компьютером «${p.n}» напрямую по Wi-Fi? Память, заметки и дела станут общими — без интернета и dewiar.pro.`)) return;
  showBot("Подключаюсь к компьютеру…");
  try { await homeClaim(link); showBot(`Готово — телефон и «${p.n}» теперь одна Лира. Синхронизация идёт сама, когда вы дома в одном Wi-Fi.`); say("Готово!"); }
  catch (e) { showBot("Не подключилось: " + (e.message || e) + ". Телефон и компьютер должны быть в одном Wi-Fi.", "err"); }
}
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
  if (/^d:[0-6]+$/.test(rep)) return { kind: "weekly", days: repDays(rep), time };
  return null;
}
function repFromDict(r) {
  if (!r || typeof r !== "object") return "";
  const days = (r.days || []).slice().sort().join(",");
  if (r.kind === "daily" && (!r.days || r.days.length === 7)) return "daily";
  if ((r.kind === "daily" || r.kind === "weekly") && days === "0,1,2,3,4") return "weekdays";
  if (r.kind === "weekly" && (r.days || []).length === 1) return "weekly";
  if ((r.kind === "weekly" || r.kind === "daily") && (r.days || []).length > 1) return repNorm(r.days);   // «пн–чт», «кроме пятницы» (30.10)
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
  if (tasks.length) out += "\nБольшие задачи: " + tasks.join("; ") + " (удалить — remove_task, ответить на вопрос задачи — answer_task)";
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
  if (!syncChan() || !S.sync.on || !String(you || "").trim()) return;
  const q = qGet("dayq"); q.push({ id: "t" + Date.now().toString(36) + Math.random().toString(36).slice(2, 7), ts: Date.now(), who: persona().name, you: String(you).slice(0, 1500), bot: String(bot || "").slice(0, 2500) });
  qSet("dayq", q); syncSoon();
}
function taskToPc(title, goal, to) {
  if (!syncChan() || !S.sync.on) throw new Error("передать задачу компьютеру можно, когда включена синхронизация (Настройки → Ещё)");
  // cloud — компьютера нет на связи: задачу сделает облако Dewiar (исполнитель на сервере, см. core/cloudrunner.py)
  const q = qGet("taskq"); q.push(Object.assign({ id: "q" + Date.now().toString(36) + Math.random().toString(36).slice(2, 7), title: String(title || goal).slice(0, 80), goal: String(goal || title).slice(0, 4000), ts: Date.now() },
    to ? { to, from: devMyName() } : { cloud: true }));       // to — названный компьютер (0.56): облако и другие компьютеры её не берут
  qSet("taskq", q); syncSoon();
}
const pcOnline = () => (syncStatus.devices || []).some(x => x.pc && x.name !== "Облако Dewiar" && Date.now() / 1000 - (x.seen || 0) < 180);
const pcSeen = () => (syncStatus.devices || []).some(x => x.pc && Date.now() / 1000 - (x.seen || 0) < 14 * 86400);   // компьютер на связи (за 2 недели)
const mindBody = (t) => String(t || "").replace(/^\s*#[^\n]*\n+/, "").replace(/^_[^\n]*_\s*\n+/gm, "").trim();
/* конституция — правила (честность, подтверждение необратимого, «не помогаю вредить»): в самой подсказке (systemStable) */
function mindConst() {
  const c = mindBody(mind().constitution).slice(0, 1800);
  return c ? "ТВОЯ КОНСТИТУЦИЯ — принципы, которые ты соблюдаешь всегда, с любым характером и в любом настроении (их написал пользователь; ты их не меняешь):\n" + c : "";
}
/* душа и выводы ночи — в личной справке (systemPersonal) */
function mindPrompt() {
  const m = mind(), p = persona(), body = mindBody;
  let out = "";
  const sl = body((m.souls[p.name] || {}).text).slice(0, 1400);
  if (sl) out += "\n\nТВОЯ ДУША — автопортрет, который ты сам(а) пишешь по своему дневнику. Это ты; но характер и конституция важнее:\n" + sl;
  const ins = m.insights;
  if (ins && (ins.lines || []).length && (Date.now() - new Date(ins.day + "T12:00").getTime()) < 3 * 864e5)
    out += "\n\nТвои выводы после прошлого дня (ты записал их ночью в дневник" + (ins.title ? `, «${ins.title}»` : "") + "):\n" + ins.lines.map(x => "- " + x).join("\n") + "\nУчитывай их естественно; не пересказывай без повода.";
  return out;
}
/* Всё, что телефон синхронизирует, в виде {"вид:id": данные} — тот же формат, что snapshot() в core/sync.py.
   Отпечаток syncHash каждой записи сравнивается с отправленным: изменилась — уходит, пропала — уходит удалением. */
function syncSnapshot(st) {
  const out = {};
  JSON.parse(D.alarms() || "[]").forEach(x => { out["reminder:" + x.id] = Object.assign({ text: x.title || "", at: +x.at, kind: x.kind || "reminder", repeat: repToDict(x.repeat, x.at), paused: false },
    x.note ? { note: x.note } : {}); });                // note — id заметки с фото и файлами (то же, что note:<id>)
  notes().forEach(x => { out["note:" + x.id] = { title: x.title || "", text: x.text || "", folder: x.folder || "" };
    if (+x.time) Object.defineProperty(out["note:" + x.id], "t", { value: +x.time, enumerable: false }); });   // когда написана: старая копия не перебьёт новую
  money().forEach(x => { out["money:" + x.id] = { date: x.date, kind: x.kind, amount: +x.amount, currency: x.currency, category: x.category || "", note: x.note || "" }; });
  (S.memory || []).forEach(f => { out["memory:" + factId(f)] = { text: f }; });
  const ks = ((st || syncSt()) || {}).kinds || [];
  if (ks.includes("client") && typeof cliSnap === "function") cliSnap(out);   // «Клиенты»: в канал без шифрования не уходят (syncOne)
  if (ks.includes("pmemory") && S.pmem) {                 // своя память персонажей и у кого она своя
    Object.entries(S.pmem.facts || {}).forEach(([n, fs]) => (fs || []).forEach(f => { out["pmemory:" + pmemId(n, f)] = { who: n, text: f }; }));
    if (+S.pmem.at > 0) out["pmemory:own"] = { names: S.pmem.own || [], at: +S.pmem.at };   // меняли хоть раз — иначе не перебивать чужое
  }
  if (ks.includes("soul") || ks.includes("mind")) {
    const m = mind();
    if (ks.includes("soul")) for (const n in m.souls) if ((m.souls[n].text || "").trim()) out["soul:" + n] = { text: m.souls[n].text };
    if (ks.includes("mind") && m.constitution.trim()) out["mind:constitution"] = { text: m.constitution };
  }
  if (ks.includes("dayturn")) qGet("dayq").forEach(x => { out["dayturn:" + x.id] = { ts: x.ts, who: x.who, you: x.you, bot: x.bot }; });
  if (ks.includes("taskreq")) qGet("taskq").forEach(x => { out["taskreq:" + x.id] = Object.assign({ title: x.title, goal: x.goal, ts: x.ts, cloud: !!x.cloud }, x.to ? { to: x.to, from: x.from || "" } : {}); });
  if (ks.includes("task")) qGet("taskcmd").forEach(x => { out["task:" + x.id] = Object.assign({}, x.data, { want: x.want, text: x.text, at: x.ts }); });   // «удалить», «ответ» — компьютеру
  if (ks.includes("done")) doneList().forEach(x => { out["done:" + x.id] = { title: x.title, at: +x.at, src: x.src || "", rid: x.rid || "" }; });   // сделанные дела (core/done.py)
  if (ks.includes("persona")) myPersonas().forEach(x => { out["persona:" + x.id] = { name: x.name, gender: x.gender || "female", role: x.role || "", about: x.about || "", color: x.color || "", avatar: x.avatar || "" }; });   // свои персонажи — и на компьютер
  if (ks.includes("safe") && typeof safeSnap === "function") safeSnap(out);   // сейф — как пришёл, шифром мастер-пароля
  return out;
}
const TASK_RU = { running: "в работе", waiting: "ждёт ответа", paused: "на паузе", done: "готово", failed: "не вышло", sleeping: "ждёт времени", stopped: "остановлена" };
/* Применить чужую запись. -> false — её нет и не будет в нашем снимке (прошедшее разовое напоминание; дневник, задачи,
   выводы — их ведёт компьютер; очереди dayturn/taskreq): syncRun помечает её skip, чтобы не отправить обратно удалением. */
function syncApply(it) {
  const d = it.data || {}, del = it.deleted;
  if (it.kind === "doc") { docApply(it.id, d, del); return false; }   // файлы ведёт компьютер: отсюда ни правок, ни удалений
  if (it.kind === "safe") return typeof safeApply === "function" ? safeApply(it) : false;
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
  } else if (it.kind === "client") {
    return typeof cliApply === "function" ? cliApply(it.id, d, del, syncChans().find(x => x.key === syncCurKey)) : false;
  } else if (it.kind === "pmemory") {
    S.pmem = Object.assign({ own: [], at: 0, facts: {} }, S.pmem || {});
    if (it.id === "own") { if (!del && Array.isArray(d.names) && +d.at > (+S.pmem.at || 0)) { S.pmem.own = d.names.map(String).slice(0, 40); S.pmem.at = +d.at; } }
    else if (del) { const pre = it.id.split("-")[0], fid = it.id.slice(pre.length + 1);
      Object.keys(S.pmem.facts).forEach(n => { if (pmemId(n, "").split("-")[0] === pre) S.pmem.facts[n] = S.pmem.facts[n].filter(f => factId(f) !== fid); }); }
    else if (d.who && d.text) { const n = String(d.who).slice(0, 40), fs = S.pmem.facts[n] || (S.pmem.facts[n] = []);
      if (!fs.some(f => factId(f) === factId(d.text))) fs.push(String(d.text)); if (fs.length > 300) fs.splice(0, fs.length - 300); }
    prefSet("settings", JSON.stringify(S));
  } else if (it.kind === "memory") {
    S.memory = (S.memory || []).filter(f => factId(f) !== it.id);
    if (!del && d.text) S.memory.push(d.text);
    S.memory = S.memory.slice(-300); prefSet("settings", JSON.stringify(S));
  } else if (["soul", "mind", "diary", "task"].includes(it.kind)) {
    if (del && it.kind === "task") { const m = mind(); if (m.tasks[it.id]) { delete m.tasks[it.id]; saveMind(m); } return false; }   // компьютер удалил задачу
    if (it.kind === "task" && ((mind().hid || {})[it.id] || (it.data || {}).want)) return false;   // удалили здесь / наша же команда
    if (del) return false;                                   // душа, дневник удалением не стираются
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
      const was = m.tasks[it.id], chs = [...new Set(((was && was.chs) || []).concat(syncCurKey ? [syncCurKey] : []))];   // каналы, откуда пришла: туда и «Удалить»
      m.tasks[it.id] = Object.assign({}, d, { u: it.updated }, chs.length ? { chs } : {});
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
/* Обмен по всем каналам (04.11, жалоба: «смартфон видит только тот компьютер, с которым синхронизировал по Wi-Fi»):
   вход в Dewiar есть — облако главный канал, «Дома по Wi-Fi» запасной; данные уходят во все доступные каналы, у каждого
   своё состояние (pref «sync» — облако, «sync_home:<узел>» — Wi-Fi: rev и отпечатки idx не сбрасываются при смене),
   а очереди (dayturn, taskreq, task) — только в первый удавшийся: их забирает компьютер, второй раз в дневнике не нужно.
   Облако — первым и под syncBusy; Wi-Fi — следом, под своим homeBusy: облако его не ждёт (рецензия 04.11). Облако живо —
   Wi-Fi пробуем только по первому адресу, 3 с (homeHello), без поиска по сети; не ответил — следующая попытка через
   5 минут. Облако не ответило по сети — его ответ мог потеряться, а записи дойти: очереди из того запроса по Wi-Fi в этот
   раз не шлём (иначе разговор дважды в дневнике), со второй такой неудачи — шлём (компьютер узнаёт повтор по id,
   core/sync.py _q_seen). manual — «Синхронизировать» руками: Wi-Fi полностью и ошибку показать. */
const SYNC_Q = ["dayturn", "taskreq", "task"];
let homeNextTry = 0, homeLastErr = "", homeQuickFail = false, homeBusy = null, syncCurKey = "";
const syncQTry = {};                                   // «вид:id» записи очереди → сколько раз облако не ответило на неё по сети
async function syncRun(manual) {
  // Экзамен (песочница) — никакого обмена: снимок собирался из песочницы, а состояние обмена — настоящее, и записанное
  // экзаменом (память «в среду встреча с подрядчиком», заметки, расход 450, сделанные дела) уходило в аккаунт и
  // возвращалось людям как своё (отчёт №52, 14.10). Следы прошлых экзаменов убирает examCleanCheck (exam.js).
  if (SANDBOX) return;
  if (tgOn() && Date.now() - ((S.tg || {}).st || 0) > 600000) tgStatus().catch(() => {});   // бот подключили на компьютере — узнать
  if ((S.tg || {}).linked && Date.now() - (S.tg.at || 0) > 600000) tgSync();      // ключ и персонаж для бота — раз в 10 минут
  if (!tgHandT && !tgHandBusy && tgHandOn()) tgHandLater(500);                     // «Отвечать с телефона» — опрос не уснул
  if (syncBusy) return; const chans = syncChans();
  if (!chans.length || !S.sync.on) { syncStatus = Object.assign(syncStatus, { ok: null, error: "" }); return; }
  syncBusy = true;
  const res = [], hold = new Set();
  try {
    for (const c of chans.filter(x => !x.home)) {
      try { res.push(Object.assign(await syncOne(c), { c })); }
      catch (e) { res.push({ c, err: e });
        (e.qids || []).forEach(k => { syncQTry[k] = (syncQTry[k] || 0) + 1; if (syncQTry[k] === 1) hold.add(k); }); }
    }
  } finally { syncBusy = false; }
  const hc = chans.find(x => x.home);
  if (hc) {
    const cloudOk = res.some(r => r.ok), quick = cloudOk && !manual;
    if (!manual && chans.length > 1 && Date.now() < homeNextTry && (cloudOk || !homeQuickFail)) res.push({ c: hc, skip: true });
    else if (homeBusy && !manual) res.push({ c: hc, skip: true });
    else {
      if (homeBusy) await homeBusy.catch(() => { });          // руками — дождаться начатого обмена по Wi-Fi и пройти заново
      const p = syncOne(Object.assign({}, hc, { quick }), { hold }); homeBusy = p;
      try { res.push(Object.assign(await p, { c: hc })); homeNextTry = 0; homeLastErr = ""; homeQuickFail = false; }
      catch (e) { res.push({ c: hc, err: e }); if (e.net && chans.length > 1) { homeNextTry = Date.now() + 300000; homeLastErr = e.message; homeQuickFail = quick; } }
      finally { if (homeBusy === p) homeBusy = null; }
    }
  }
  const good = res.filter(r => r.ok), first = good[0], bad = res.find(r => r.err);
  const merged = {}, devs = [];
  good.forEach(r => { (r.d.all || []).forEach(x => { if (!x || !x.id) return; const m = merged[x.id];
    if (!m) merged[x.id] = Object.assign({}, x); else { if ((+x.seen || 0) > (+m.seen || 0)) m.seen = x.seen; m.me = m.me || x.me; } });
    (r.d.devices || []).forEach(x => devs.push(x)); });
  const all = good.some(r => r.d.all) ? Object.values(merged).sort((x, y) => (y.me - x.me) || ((y.seen || 0) - (x.seen || 0))) : null;
  const chs = res.map(r => ({ home: !!r.c.home, via: r.c.via, ok: r.skip ? (homeLastErr ? false : null) : !!r.ok, error: r.err ? r.err.message : r.skip ? homeLastErr : "" }));
  if (first) {
    syncStatus = { ok: true, at: Date.now(), error: "", devices: devs, all, counts: good.reduce((o, r) => ({ sent: o.sent + r.sent, got: o.got + r.got }), { sent: 0, got: 0 }),
      via: syncChan().via, chans: chs };
    if (all) { DEVS = all; try { devFresh(); bsBoot(); } catch (e) { } }
    const got = good.reduce((n, r) => n + r.got, 0);
    if (got && qGet("natt_in").length) setTimeout(() => nattIn().catch(() => { }), 0);    // пришла заметка, которую ждали фото с компьютера
    if (got && $("#sh-day") && $("#sh-day").classList.contains("on") && document.activeElement !== $("#tk-goal")) renderDay();
    if (got && $("#sh-soul") && $("#sh-soul").classList.contains("on") && soulTab === "diary") renderSoul();
  } else if (bad) {
    syncStatus = Object.assign(syncStatus, { ok: false, at: Date.now(), error: bad.err.message, via: bad.c.via, chans: chs });
  }
  // облако не ответило, а по Wi-Fi всё прошло — так и сказать (было «Синхронизация: нет сети» при удачном обмене)
  if (manual && bad && !bad.err.home) toast(first ? `Синхронизировано по Wi-Fi с «${(S.sync.home || {}).n || "компьютером"}» — dewiar.pro сейчас не ответил` : "Синхронизация: " + bad.err.message);
}
/* Состояние обмена канала: облако — pref «sync» (там же шифрование: e2eRemote, resealAll), Wi-Fi — «sync_home:<узел>».
   Номер устройства один на все каналы. Прежние версии держали обмен по Wi-Fi в «sync» — переносим. */
function syncStFor(c) {
  const cl = syncSt();
  if (!c.home) return cl;
  let st = null; try { st = JSON.parse(prefGet(c.key) || "") || null; } catch (e) { st = null; }
  if (!st && cl && cl.who === syncHash(c.token)) {                 // до 0.83 Wi-Fi вёл «sync»: забираем его как есть
    st = cl; prefSet(c.key, JSON.stringify(cl));
    prefSet("sync", JSON.stringify({ rev: 0, idx: {}, who: "", device: cl.device, e2eOffHere: cl.e2eOffHere }));
  }
  return st;
}
const syncStOk = (x) => { const o = syncStFor(x); return o && o.who === syncHash(x.token) && o.idx ? o : null; };
function syncDevice() {
  const cl = syncSt() || {};
  if (cl.device) return cl.device;
  cl.device = "phone-" + Math.random().toString(36).slice(2, 12); cl.rev = cl.rev || 0; cl.idx = cl.idx || {}; cl.who = cl.who || "";
  prefSet("sync", JSON.stringify(cl)); return cl.device;
}
/* Новый канал (вход в Dewiar у того, кто был «Дома по Wi-Fi», или наоборот; перенос из «sync») раньше начинал с пустых
   отпечатков: всё уходило заново со временем «сейчас», перебивало правки других устройств и воскрешало удалённое
   (рецензия 04.11: расход, удалённый на «Рабочем», вернулся). Теперь его состояние засевается отпечатками другого канала
   (seed): ушло только то, что и правда изменилось, а из облака пришло всё, включая удаления. Чего в канале после полного
   первого обмена не оказалось, уходит туда со своим прежним временем (keep), а не «сейчас». */
function syncSeed(c, st) {
  for (const x of syncChans()) {
    if (x.key === c.key) continue;
    const o = syncStOk(x); if (!o) continue;
    let n = 0;
    for (const k in o.idx) { const e = o.idx[k], kind = k.slice(0, k.indexOf(":"));
      if (typeof e.h !== "string" || !e.h || e.h === "older" || e.del || e.skip || e.seed || SYNC_Q.includes(kind) || k === "mind:e2e") continue;
      st.idx[syncLocKey(o, k)] = { h: e.h, u: e.u, seed: 1 }; n++; }
    if (n) { st.seeding = 1; plog("info", `🔄 ${c.home ? "Wi-Fi" : "облако"}: начинаю с отпечатков другого канала (${n})`); }
    return;
  }
}
/* Одна заметка в разных каналах может жить под разными id: до 0.83 компьютер-мост давал заметке с телефона в облаке id
   по пути (f…), а на узле Wi-Fi у неё оставался id телефона (n…) — после входа «Покупки» задваивались на всех (рецензия
   04.11). У канала своя таблица st.ali {id в канале: id здесь}. Пришла незнакомая заметка, а здесь есть та же, которую
   этот канал ещё не знает (компьютер подсказал её второй id — aka, или совпали название, папка и текст), — склеиваем:
   дальше канал знает её под своим id, а сюда она ложится на ту же заметку. */
const noteBase = (t) => String(t || "").replace(/\s+/g, " ").trim().replace(/\s*\(\d{1,3}\)$/, "");   // «Список (2)» — имя файла было занято на компьютере
const noteNorm = (title, text) => { let t = String(text || "").replace(/\r\n?/g, "\n").trim(); const first = t.split("\n", 1)[0];
  if (/^# /.test(first) && noteBase(first.slice(2)) === noteBase(title)) t = t.slice(first.length).trim(); return t.replace(/\s+/g, " "); };   // компьютер дописывает «# Название»
function syncRemMap(st) { const r = {}; for (const [rem, loc] of Object.entries((st && st.ali) || {})) r[loc] = rem; return r; }
const syncRemKey = (k, rm) => k.startsWith("note:") && rm[k.slice(5)] ? "note:" + rm[k.slice(5)] : k;
const syncLocKey = (st, k) => k.startsWith("note:") && st.ali && st.ali[k.slice(5)] ? "note:" + st.ali[k.slice(5)] : k;
function syncSnapFor(st) {                              // снимок — в id этого канала
  const s = syncSnapshot(st), rm = syncRemMap(st); if (!Object.keys(rm).length) return s;
  const out = {}; for (const k in s) out[syncRemKey(k, rm)] = s[k]; return out;
}
function noteGlue(st, it, dup) {
  const d = it.data || {}, rm = syncRemMap(st), ali = st.ali || {}, known = (id) => { const e = st.idx["note:" + id]; return !!(e && !e.seed && e.keep === undefined); };
  const free = notes().filter(n => n.id !== it.id && !rm[n.id] && !ali[n.id] && !known(n.id));
  if (typeof d.aka === "string" && d.aka) { const a = free.find(n => n.id === d.aka); if (a) return a.id; }
  if (dup) return "";                                    // пришла раньше отдельной — склеиваем только по подсказке моста
  const w = noteNorm(d.title, d.text), t = noteBase(d.title), f = String(d.folder || "");
  const m = free.find(n => noteBase(n.title) === t && String(n.folder || "") === f && noteNorm(n.title, n.text) === w);
  return m ? m.id : "";
}
/* дома ли (облако живо — Wi-Fi не ждём): один быстрый запрос к первому адресу */
async function homeHello(u) {
  const h = S.sync.home; let ok = false;
  try { const r = await http("GET", u + "hello", { timeout: 3000 }); const d = JSON.parse(r.body || "{}"); ok = r.status === 200 && d.dewiar === "home" && (!h.h || d.id === h.h); }
  catch (e) { ok = false; }
  if (!ok) throw Object.assign(new Error(`компьютер «${h.n || "дома"}» не в этой сети — всё идёт через dewiar.pro`), { home: true, net: true });
}
/* Один обмен с каналом c: отправить свои изменения и удаления, забрать чужие начиная с номера st.rev — порциями, пока
   сервер отвечает more (не больше 20 порций). Сменился аккаунт или ключ (who) — состояние новое, засеянное другим каналом
   (syncSeed). Запись, которую другой канал видел в более новой версии (u), отсюда не применяем — старая копия с узла не
   перебьёт свежую из облака; наша версия уйдёт сюда следующим обменом — с временем той версии, а не «сейчас».
   opts.hold — записи очередей, которые сюда в этот раз не слать. -> {ok, d, sent, got} */
async function syncOne(c, opts) {
  opts = opts || {};
  const who = syncHash(c.token), device = syncDevice();
  let st = syncStFor(c);
  if (!st || st.who !== who) { st = Object.assign({ rev: 0, idx: {}, who, device }, !c.home && st ? { e2eOffHere: st.e2eOffHere } : {}); syncSeed(c, st); }
  st.device = device; st.idx = st.idx || {};
  const save = () => prefSet(c.key, JSON.stringify(st));
  const chans = syncChans();
  const others = chans.filter(x => x.key !== c.key).map(syncStOk).filter(Boolean).map(o => ({ o, rm: syncRemMap(o) }));
  const otherR = (lk) => others.map(({ o, rm }) => o.idx[syncRemKey(lk, rm)]).filter(e => e && e.r);   // r — пришло оттуда (время версии)
  const verOf = (lk, h) => { const e = otherR(lk).find(x => x.h === h && +x.u); return e ? +e.u : 0; };
  const snap = syncSnapFor(st), now = Date.now(), changes = [], ek = e2eKey(c);
  (opts.hold || []).forEach(k => { delete snap[k]; });
  const cliOk = typeof cliChanOk === "function" && cliChanOk(c);       // «Клиенты» — чужие телефоны и почты: только зашифрованными или по Wi-Fi
  if (!cliOk) for (const k in snap) if (k.startsWith("client:")) delete snap[k];
  // «удалить», «ответить» задаче — туда, откуда она пришла (задание, не переданное «Домашним», живёт только на узле)
  qGet("taskcmd").forEach(x => { const ch = (x.chs || []).filter(k => chans.some(y => y.key === k)); if (ch.length && !ch.includes(c.key)) delete snap["task:" + x.id]; });
  if (ek) snap["mind:e2e"] = { on: true };                          // другим устройствам: шифрование включено — попросите ключ
  for (const k in snap) { const h = syncHash(snap[k]), e = st.idx[k], again = !!ek && (st.resealAll || (e && e.reseal));
    if (e && e.h === h && !e.del && !again) continue;
    const [kind, id] = [k.slice(0, k.indexOf(":")), k.slice(k.indexOf(":") + 1)];
    const data = ek && e2eSealable(kind, id, snap[k]) ? e2eSeal(ek, snap[k]) : snap[k];
    if (data.e2e && data.c.length > 290000) continue;               // зашифрованная больше, чем возьмёт сервер
    // время версии, а не «сейчас», если здесь её не правили: та, которой не оказалось в канале (keep), или пришедшая другим
    const t = snap[k].t, upd = again ? now : (e && e.keep === h && +e.u) || verOf(syncLocKey(st, k), h) || ((!e || e.seed) && t ? Math.min(now, t) : now);
    changes.push({ kind, id, data, updated: upd, _h: h }); }
  for (const k in st.idx) { const e = st.idx[k];
    if (k in snap || e.del || e.skip || e.seed || (!cliOk && k.startsWith("client:"))) continue;   // шифрование выключили — это не удаление клиентов
    if (e.keep !== undefined) { delete st.idx[k]; continue; }      // в канале её и не было — удалять там нечего
    changes.push({ kind: k.slice(0, k.indexOf(":")), id: k.slice(k.indexOf(":") + 1), data: {}, updated: now, deleted: true, _h: null }); }
  const info = JSON.parse(D.info() || "{}");
  let body = { since: st.rev || 0, device, name: devMyName(), app: D.web ? "web" : "phone", ver: info.version || "", kinds: SYNC_KINDS, changes: changes.map(({ _h, ...x }) => x) }, got = 0, d = {}, kept = 0;
  const hdr = { Authorization: "Bearer " + c.token, "Content-Type": "application/json" };
  if (c.link && c.link !== c.token) hdr["X-Sync-Link"] = c.link;
  for (let round = 0; round < 20; round++) {
    let status;
    try {
      if (c.home) { if (round === 0 && c.quick) await homeHello(c.base); ({ status, d } = await homePost(c, body)); }
      else { let r; try { r = await http("POST", c.base + "?p=/sync", { headers: hdr, body, timeout: 30000 }); } catch (e) { throw Object.assign(e instanceof Error ? e : new Error(String(e)), { net: true }); }
        status = r.status; try { d = JSON.parse(r.body || "{}"); } catch (e) { d = {}; } }
    } catch (e) { if (e && e.net) e.qids = body.changes.filter(x => SYNC_Q.includes(x.kind)).map(x => x.kind + ":" + x.id); throw e; }   // ответ мог потеряться, а записи — дойти
    if (status >= 400) throw new Error((d.error && d.error.message) || (c.home ? "компьютер ответил " : "облако ответило ") + status);
    const srv = d.kinds || ["reminder", "note", "money", "memory"];
    const qdone = { dayturn: [], taskreq: [], task: [] };
    body.changes.forEach(x => { if (!srv.includes(x.kind)) return;
      const k = x.kind + ":" + x.id, src = changes.find(y => y.kind === x.kind && y.id === x.id);
      if (x.kind in qdone) { qdone[x.kind].push(x.id); st.idx[k] = { h: null, u: x.updated, skip: true }; return; }   // отдали компьютеру — у себя забываем
      st.idx[k] = { h: src ? src._h : null, u: x.updated, del: !!x.deleted }; });
    if (qdone.dayturn.length) qSet("dayq", qGet("dayq").filter(x => !qdone.dayturn.includes(x.id)));
    if (qdone.taskreq.length) {                    // №586: отданная задача видна, пока компьютер (или облако) её не возьмёт
      const gone = qGet("taskq").filter(x => qdone.taskreq.includes(x.id));
      qSet("taskq", qGet("taskq").filter(x => !qdone.taskreq.includes(x.id)));
      qSet("tasksent", qGet("tasksent").filter(x => !qdone.taskreq.includes(x.id)).concat(gone.map(x => Object.assign({}, x, { sent: Date.now() }))).slice(-20));
    }
    if (qdone.task.length) qSet("taskcmd", qGet("taskcmd").filter(x => !qdone.task.includes(x.id)));   // команда задаче ушла — дальше решает компьютер
    body.changes = [];
    if (srv.some(k => !(st.kinds || []).includes(k))) { st.kinds = srv; st.rev = 0; body.since = 0; save(); continue; }   // сервер узнал новое — история с начала
    for (let it of d.items || []) {
      const k = it.kind + ":" + it.id, e = st.idx[k] || {};
      if (it.dev === st.device && e.u === it.updated) continue;     // наша же правка вернулась — уже применена
      if (k === "mind:e2e") {                                         // метка: шифрование включено на другом устройстве
        if (!it.deleted && it.data && it.data.on) {
          if (syncKeyGet()) { if (!S.sync.e2e && !st.e2eOffHere) { S.sync.e2e = true; saveS(); st.resealAll = true; plog("info", "🔐 синхронизация зашифрована на другом устройстве — шифрую и здесь"); } }
          else st.e2eRemote = true;
        }
        st.idx[k] = { h: syncHash({ on: true }), u: it.updated, skip: true }; continue;   // у нас метка та же — не пересылать её туда-обратно
      }
      let plainIn = false;
      if (e2eSealed(it.data)) {                                       // зашифровано на устройстве
        const kk = ek || anyKey();
        if (!kk) { st.locked = (st.locked || 0) + 1; st.e2eRemote = true; continue; }   // ключа нет — ждём его со своего устройства
        try { it = Object.assign({}, it, { data: e2eOpen(kk, it.data) }); } catch (x) { console.warn("sync: не расшифровалось", k); continue; }
      } else if (ek && !it.deleted && e2eSealable(it.kind, it.id, it.data || {})) plainIn = true;   // пришло открытым — перешифруем
      let lk = syncLocKey(st, k), second = false, same = false;
      if (it.kind === "note" && lk === k) {
        if (syncRemMap(st)[it.id]) second = true;                     // та же заметка, а канал знает её под другим id — второе имя
        else if (!it.deleted) {
          // пришла раньше и легла отдельной (компьютер до 0.83), а теперь мост подсказал, что это та же (aka) — склеиваем,
          // лишнюю (без вложений) убираем
          const dupN = notes().find(n => n.id === it.id), g = dupN && (dupN.att || []).length ? "" : noteGlue(st, it, !!dupN);
          if (g) { const loc = notes().find(n => n.id === g) || {}, d0 = it.data || {};
            st.ali = Object.assign({}, st.ali, { [it.id]: g }); delete st.idx["note:" + g]; lk = "note:" + g;
            if (dupN) fileSave("notes.json", JSON.stringify(notes().filter(n => n.id !== it.id)));
            same = noteBase(loc.title) === noteBase(d0.title) && noteNorm(loc.title, loc.text) === noteNorm(d0.title, d0.text);   // та же — здешнюю не трогаем
            plog("info", `🔄 ${c.home ? "Wi-Fi" : "облако"}: заметка «${String(d0.title || "").slice(0, 40)}» — та же, что здесь, склеиваю`); }
        }
      }
      if (second && it.deleted) { st.idx[k] = { h: null, u: it.updated, skip: true }; continue; }   // второе имя удалили — заметку не трогаем
      if (otherR(lk).some(x => +x.u > +(it.updated || 0))) { st.idx[k] = { h: "older", u: it.updated }; continue; }   // другой канал уже дал новее — свою отправим сюда
      if (it.kind === "note" && !it.deleted && !same) {              // та же заметка в виде компьютера («# Название», « (2)») — здешнюю не трогаем
        const loc = notes().find(n => n.id === lk.slice(5)), d0 = it.data || {};
        same = !!loc && noteBase(loc.title) === noteBase(d0.title) && String(loc.folder || "") === String(d0.folder || "") && noteNorm(loc.title, loc.text) === noteNorm(d0.title, d0.text);
      }
      if (it.kind === "note") {                                       // 05.11: запертую здесь правка оттуда не перетирает
        const loc = notes().find(n => n.id === lk.slice(5)), d0 = it.data || {};
        // 14.11 (владелец: «несколько версий вкладки без возможности удалить»): пришла тоже запертая — там знали о замке,
        // это их последняя правка: обычный обмен (новее побеждает), без копии — иначе обе стороны множили копии
        if (loc && noteLocked(loc.text) && (it.deleted || (!noteLockOnly(loc.text, d0.text || "") && !noteLocked(d0.text || "")))) {
          if (!it.deleted && !same) {                                   // их правка — рядом копией, без замка; та же уже лежит — не дублируем
            const all = notes(), base = String(d0.title || loc.title || "Заметка").slice(0, 36), t2 = noteLockSet(d0.text || "", false);
            if (!all.some(n => String(n.title || "").startsWith(base + " (") && noteNorm(n.title, n.text) === noteNorm(n.title, t2))) {
              all.push({ id: uid("n"), title: `${base} (копия с другого устройства)`, text: t2, folder: d0.folder || loc.folder || "", time: Date.now() });
              fileSave("notes.json", JSON.stringify(all)); } }
          st.idx[k] = { h: "older", u: it.updated }; plog("info", `🔒 заметка «${clip(loc.title || "", 40)}» заперта — ${it.deleted ? "удаление" : "правка"} с другого устройства не принята`); continue;
        }
      }
      let okApply; syncCurKey = c.key;
      if (same) { got++; st.idx[k] = { h: null, u: it.updated, r: 1 }; syncCurKey = ""; continue; }
      try { okApply = syncApply(lk === k ? it : Object.assign({}, it, { id: lk.slice(lk.indexOf(":") + 1) })); } catch (e2) { console.error("sync", it.kind, it.id, e2); continue; }
      finally { syncCurKey = ""; }
      if (okApply === false || second) { st.idx[k] = { h: null, u: it.updated, skip: true }; continue; }
      got++; st.idx[k] = it.deleted ? { h: null, u: it.updated, del: true, r: 1 } : Object.assign({ h: null, u: it.updated, r: 1 }, plainIn ? { reseal: true } : {});
    }
    st.rev = d.rev || st.rev; body.since = st.rev;
    if (!d.more) {
      if (st.seeding) { for (const k in st.idx) { const e = st.idx[k]; if (e.seed) { st.idx[k] = { h: "", u: e.u, keep: e.h }; kept++; } } delete st.seeding; }   // в канале их нет — отправим
      break;
    }
  }
  // полученное запоминаем отпечатком «как оно легло у нас» — иначе следующий обмен отправил бы его обратно как своё
  if (got) { const s2 = syncSnapFor(st); for (const k in st.idx) { const e = st.idx[k]; if (e.h === null && !e.del && !e.skip && k in s2) e.h = syncHash(s2[k]); } }
  if (st.ali) for (const r in st.ali) { const e = st.idx["note:" + r]; if (e && e.del) delete st.ali[r]; }
  if (ek) { delete st.resealAll; changes.forEach(x => { const e = st.idx[x.kind + ":" + x.id]; if (e) delete e.reseal; }); }
  save();
  if (!c.home && st.e2eRemote && !syncKeyGet() && Date.now() - (window._keyAsk || 0) > 600000) { window._keyAsk = Date.now(); ownShare(["sync_key"]).catch(() => { }); }   // в облаке зашифрованное, а ключа нет — просим у своих (раз в 10 мин)
  if (!c.home && +d.box > (+clLoad().cursor || 0)) setTimeout(() => clPoll().catch(() => { }), 0);   // в ящике своих устройств новое — сразу
  if (kept && !opts.more) { const r2 = await syncOne(c, Object.assign({}, opts, { more: true })); return { ok: true, d: r2.d, sent: changes.length + r2.sent, got: got + r2.got }; }   // засев: недостающее — сразу
  return { ok: true, d, sent: changes.length, got };
}
function syncSoon() { if (SANDBOX) return; clearTimeout(syncTimer); syncTimer = setTimeout(() => syncRun(false), 3000); }   // экзамен — без обмена   // несколько правок подряд — один обмен
/* Значок «Записать» на рабочем столе (CaptureWidget.java): включён по умолчанию; «Добавить на экран» — Android 8+ */
/* Вид значка (25.10, владелец: «может стекло матовое… стильно и красиво»): pref widget_look, значок перерисовывается сразу */
const WG_LOOKS = [["glass", "Стекло", "матовое стекло — красиво на любых обоях"], ["light", "Светлый", "мягкий светлый, как тема «Небесный»"],
  ["dark", "Тёмный", "матово-чёрный"], ["theme", "Как тема", "светлый или тёмный — вслед за оформлением"]];
const wgLook = (w) => { const p = String(prefGet("widget_look") || ""); return WG_LOOKS.some(l => l[0] === p) ? p : "glass"; };
function widgetCard() {
  let w = {}; try { w = JSON.parse(D.widgetState ? D.widgetState() : "{}") || {}; } catch (e) { }
  if (w.on === undefined) return `<p class="hint" style="margin:0">Обновите приложение — в этой версии значка ещё нет.</p>`;
  return `<div class="sw"><div>Значок на рабочем столе<small class="hint" style="display:block;margin:2px 0 0">одно нажатие — Dewiar слушает и записывает мысль в «Идеи» или ставит напоминание («напомни завтра в 10…»), потом сам уходит</small></div>
    <label class="tg"><input type="checkbox" id="wg-on" ${w.on ? "checked" : ""}><i></i></label></div>`
    + (w.on && w.look ? `<div class="sw wglook"><div>Вид<small class="hint" style="display:block;margin:2px 0 0">${WG_LOOKS.find(l => l[0] === wgLook(w))[2]}</small></div>
    <div class="seg" id="wg-look" role="radiogroup" aria-label="Вид значка">${WG_LOOKS.map(([id, t]) => `<button role="radio" data-l="${id}" class="${wgLook(w) === id ? "on" : ""}" aria-checked="${wgLook(w) === id}">${t}</button>`).join("")}</div></div>` : "")
    + (w.on ? (w.placed ? `<div class="res ok">На рабочем столе: ${w.placed}</div>`
      : w.pin ? `<button class="btn w" id="wg-pin" style="margin-top:8px">Добавить на рабочий стол</button><div class="res" id="wg-res"></div>`
      : `<p class="hint" style="margin:8px 0 0">Добавить: долгое нажатие на рабочем столе → «Виджеты» → Dewiar → «Записать».</p>`) : "");
}
function syncCard() {                             // 0.56: синхронизация и подключение устройств — во вкладке «Устройства» (devices.js)
  const c = syncChan(), st = syncStatus, t = st.at ? new Date(st.at) : null;
  return `<p class="hint" style="margin-top:0">${!c ? "Телефон и компьютер — одна Лира: напоминания, заметки, расходы и память общие. Подключается кодом из 6 цифр."
    : !S.sync.on ? "Синхронизация выключена." : st.ok === false ? "Не синхронизировалось: " + esc(st.error) : t ? `Синхронизировано в ${pad(t.getHours())}:${pad(t.getMinutes())}.` : "Синхронизация включена."}</p>
    <button class="btn w p" id="sy-open">Устройства и синхронизация</button>`;
}
/* №329 (пакет 27.10): «невозможно найти, где создаётся код синхронизации» — кнопка была только в карточке баланса и
   пропадала, когда мозг свой. Теперь — и здесь, в «Синхронизации», с тем ключом, которым идёт синхронизация. */
let syncTick = 0;
setInterval(() => { if (!document.hidden && (!liteOn() || ++syncTick % 3 === 0)) syncRun(false); }, 60000);   // лёгкий режим — раз в 3 минуты
document.addEventListener("visibilitychange", () => { if (!document.hidden) { syncSoon(); doneInbox(); } });

