//@ Телефон и веб-версия, часть 17: «Близкие».
//@ Собирается в android/assets/www/app.js (tools/app_join.py) — порядок частей = порядок исполнения; шапка «//@» в app.js не попадает.
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
  CLS = Object.assign({ me: {}, people: [], groups: [], cursor: 0, hist: {}, unread: {}, invite: null, hello: 0, marks: {}, readUp: {} }, CLS);
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
  const st = clLoad(); st.me = d.me || {}; st.people = d.people || []; st.offers = d.offers || []; st.groups = d.groups || [];   // «Группы своих» (groups.js)
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
  if (!syncCred() || !DC() || (!at && !sk && !wants.length && !+(S.ha || {}).at)) return false;
  const k = clKeys(); if (!clLoad().me.pid || Date.now() - (CLS.hello || 0) > 600000) await clHello();
  const t = {}; ((CLS.me || {}).devs || []).forEach(d => { if (d.pub && d.dev && d.dev !== k.dev) t[d.dev] = DC().b64d(d.pub); });
  if (!Object.keys(t).length) return false;                         // других своих устройств пока нет
  t[k.dev] = DC().b64d(k.pub);
  const hat = D.web ? 0 : +(S.ha || {}).at || 0;                  // Home Assistant — адрес и токен, тоже только своим
  const body = Object.assign(at ? { home: { token: S.home.token || "", at } } : {}, hat ? { ha: { url: S.ha.url || "", token: S.ha.token || "", at: hat } } : {}, sk ? { sync_key: { k: sk.k, at: sk.at } } : {}, wants.length ? { want: wants } : {}, { ts: Date.now() });
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
/* «Дозор» сработал на компьютере (28.10, владелец: «показать на телефоне то, что увидел ИИ, — убедиться, что сработка
   не ложная»): карточка — что ждали, что Лира увидела, снимок экрана (файлом «себе», шифрованным) и две кнопки: «Верно» и
   «Не то — ждать дальше» (конверт своим устройствам watch_more: дозор снова на посту, ошибку Лира запомнит). */
function watchCard(p) {
  const esc2 = (t) => esc(String(t || ""));
  showCard(`<div class="card wcard"><small class="hint" style="margin:0">👁 Дозор на компьютере${p.dev ? " «" + esc2(p.dev) + "»" : ""}</small>
    <b>${esc2(p.what || p.text)}</b><p class="hint" style="margin:4px 0 8px">Лира увидела: ${esc2(p.note || "готово")}</p>
    ${p.shot ? `<div class="wshot" id="wshot"><span class="hint">Загружаю снимок экрана…</span></div>` : ""}
    <div class="row2" style="margin-top:10px"><button class="btn p" id="w-ok" style="flex:1">Верно</button><button class="btn" id="w-more" style="flex:1">Не то — ждать дальше</button></div></div>`);
  cardSticky = Date.now() + 10 * 60000;
  $("#w-ok").onclick = () => { cardSticky = 0; showCard(""); };
  $("#w-more").onclick = async () => {
    try { await devOwnSend({ watch_more: { id: p.wid, why: p.note || "" } }); toast("Дозор снова смотрит — эту ошибку Лира запомнила", 4000); }
    catch (e) { toast(netErr(e.message || e), 4000); }
    cardSticky = 0; showCard("");
  };
  if (p.shot && typeof clFileBytes === "function") clFileBytes(p.shot).then(b => {
    const box = $("#wshot"); if (!box) return;
    const u = clDataUrl(b, "image/jpeg"); box.innerHTML = `<img src="${u}" alt="Снимок экрана компьютера">`;
    box.onclick = () => imgView(u);                       // на весь экран — разглядеть
  }).catch(() => { const box = $("#wshot"); if (box) box.innerHTML = `<span class="hint">Снимок не загрузился</span>`; });
}
/* «Дозор» компьютера на телефоне (№468, 01.11: «Дозор включил на компьютере, на телефоне спрашиваю, как там статус, —
   Лира выдумывает что попало»). Телефон знал только «готово» (ping). Теперь компьютер (0.77+) шлёт снимок дозоров
   {watch: {dev, at, items}} — храним по компьютерам в pcwatch.json; вопрос про дозор — ответ по снимку без модели
   (pcWatchQuick) и просьба компьютеру прислать свежий. Снимка нет — честно: отсюда не видно, где посмотреть. */
const PCW_F = "pcwatch.json";
function pcWatchAll() { try { const d = JSON.parse(fileGet(PCW_F) || "{}"); return d && typeof d === "object" ? d : {}; } catch (e) { return {}; } }
function pcWatchTake(w) {
  if (!w || !Array.isArray(w.items)) return;
  const all = pcWatchAll(), dev = String(w.dev || "компьютер").slice(0, 60);
  all[dev] = Object.assign({}, all[dev], { at: +w.at || Date.now(), items: w.items.slice(0, 8).map(x => ({
    title: String(x.title || "").slice(0, 120), kind: String(x.kind || ""), status: String(x.status || ""), note: String(x.note || "").slice(0, 200),
    last: +x.last || 0, until: +x.until || 0, done_at: +x.done_at || 0, result: String(x.result || "").slice(0, 240), checks: +x.checks || 0 })) });
  fileSave(PCW_F, JSON.stringify(all));
  plog("info", `👁 Дозор с «${dev}»: идёт ${w.items.filter(x => x.status === "active").length}`);
}
function pcWatchPing(p, ts) {                                // «готово» — запомнить, даже если компьютер старый и снимков не шлёт
  const all = pcWatchAll(), dev = String(p.dev || "компьютер").slice(0, 60);
  all[dev] = Object.assign({ items: [] }, all[dev], { ping: { what: String(p.what || p.text || "").slice(0, 200), note: String(p.note || "").slice(0, 300), at: ts } });
  fileSave(PCW_F, JSON.stringify(all));
}
const PCW_RX = /(?:^|[^а-яё])дозор/i;
// просьба поставить или снять (повелительное: «включи дозор», а «я включил дозор — как там?» — вопрос о статусе)
const PCW_SET_RX = /(?:^|[^а-яё])(?:поставь|поставить|включи|включить|запусти|запустить|создай|создать|сделай|заведи|останови|остановить|выключи|выключить|отключи|отключить|сними|убери)\s+(?:мне\s+)?(?:\S+\s+)?дозор/i;
function pcWatchQuick(t) {
  t = String(t || "");
  if (!PCW_RX.test(t)) return null;
  setTimeout(() => { try { if (typeof devOwnSend === "function") devOwnSend({ want: ["watch"] }).catch(() => {}); } catch (e) { } }, 0);   // свежий снимок — на следующий вопрос
  if (PCW_SET_RX.test(t))
    return { say: "Дозор работает на компьютере: поставить или остановить его — там, скажите Лире на компьютере, например: «присмотри, когда закончится загрузка», или в студии → «Дозор». Когда сработает — пришлю сюда уведомление." };
  const all = pcWatchAll(), devs = Object.keys(all);
  const hm = (ms) => new Date(ms).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
  const ago = (ms) => { const m = Math.round((Date.now() - ms) / 60000); return m < 2 ? "только что" : m < 60 ? `${m} мин назад` : Date.now() - ms < 864e5 ? `в ${hm(ms)}` : new Date(ms).toLocaleDateString("ru-RU", { day: "numeric", month: "long" }); };
  const snap = devs.filter(d => all[d].at && Array.isArray(all[d].items));
  if (!snap.length) {
    const pg = devs.map(d => Object.assign({ dev: d }, all[d].ping || {})).filter(x => x.at).sort((a, b) => b.at - a.at)[0];
    return { say: "С телефона я не вижу, что сейчас делает Дозор на компьютере: компьютер присылает сюда только «готово», когда дозор сработал."
      + (pg ? ` Последнее такое — ${ago(pg.at)}${devs.length > 1 ? ` с «${pg.dev}»` : ""}: ${clip(pg.what || "дозор", 80)} — ${clip(pg.note || "готово", 120)}.` : " Сегодня таких сообщений не было — значит, дозор пока не сработал или не запущен.")
      + " Посмотреть сейчас — на компьютере: студия → «Дозор» или спросите Лиру там. Обновите Dewiar на компьютере — и я буду видеть дозоры отсюда." };
  }
  const ST = { active: "смотрит", done: "сработал", stopped: "остановлен", expired: "закончился по сроку", failed: "не смог проверять" };
  const qt = (x) => { const c = clip(x, 70); return /^[«"]/.test(c) ? c : `«${c}»`; };     // название уже в кавычках — не двоим
  const parts = [];
  for (const d of snap.sort((a, b) => all[b].at - all[a].at)) {
    const w = all[d], act = w.items.filter(x => x.status === "active"), fin = w.items.filter(x => x.status !== "active").sort((a, b) => b.done_at - a.done_at);
    const who = snap.length > 1 ? `На «${d}»: ` : "";
    const fresh = Date.now() - w.at < 15 * 60e3 ? "" : ` (по данным ${ago(w.at)})`;
    if (act.length) parts.push(who + `${act.length === 1 ? "идёт дозор" : `идут дозоры (${act.length})`}${fresh}: ` + act.slice(0, 3).map(x =>
      `${qt(x.title)} — ${ST.active}${x.last ? `, последняя проверка ${ago(x.last * 1000)}` : ""}${x.note ? `: ${clip(x.note, 90)}` : ""}${x.until ? `; до ${hm(x.until * 1000)}` : ""}`).join("; "));
    else parts.push(who + `сейчас дозоров нет${fresh}`);
    const f = fin[0];
    if (f && f.done_at && Date.now() - f.done_at * 1000 < 864e5) parts.push(`Последний: ${qt(f.title)} — ${ST[f.status] || f.status} ${ago(f.done_at * 1000)}${f.result ? `: ${clip(f.result, 100)}` : ""}`);
  }
  plog("info", "👁 про дозор — по снимку с компьютера, без модели");
  return { say: parts.join(". ").replace(/^./, c => c.toUpperCase()) + "." };
}
function ownApply(body) {
  if (body && body.natt) nattTake(body.natt);
  try { devBrainsOwn(body); } catch (e) { plog("warn", "мозги со своего устройства: " + e.message); }   // «Устройства» (devices.js)
  try { bsTake(body); } catch (e) { plog("warn", "сотрудники: " + e.message); }   // доска «Поручений» с компьютера (boss.js)
  if (body && body.morning && typeof body.morning === "object") mornTake(body.morning);   // «Утро с Лирой» с компьютера
  if (body && body.ping && typeof body.ping === "object" && Date.now() - (+body.ts || Date.now()) < 6 * 3600e3) {   // «Дозор» с компьютера: готово
    const t = String(body.ping.title || "Dewiar").slice(0, 80), x = String(body.ping.text || "").slice(0, 300);
    try { D.notify(t, x); } catch (e) { } toast(`${t}: ${x}`, 6000); plog("info", "👁 с компьютера: " + x.slice(0, 80));
    if (body.ping.wid) { watchCard(body.ping); pcWatchPing(body.ping, +body.ts || Date.now()); }
  }
  if (body && body.watch && typeof body.watch === "object") pcWatchTake(body.watch);   // №468: снимок «Дозора» с компьютера
  if (body && Array.isArray(body.want) && body.want.some(w => w !== "team") && (S.home.at || S.home.token || syncKeyGet())) setTimeout(() => ownShare().catch(() => { }), 0);   // другое моё устройство просит
  const skb = body && body.sync_key;
  if (skb && typeof skb === "object" && syncKeyAdopt(skb.k, skb.at)) {
    plog("info", "🔐 ключ шифрования синхронизации получен со своего устройства");
    const st = syncSt(); if (st && !st.e2eOffHere) { S.sync.e2e = true; saveS(); }
    if (st) { st.rev = 0; st.resealAll = true; st.locked = 0; prefSet("sync", JSON.stringify(st)); }
    syncSoon();
  }
  const ha = !D.web && body && body.ha;                              // Home Assistant с компьютера или другого телефона
  if (ha && typeof ha === "object" && +ha.at > +((S.ha || {}).at || 0) && (!ha.token || /^[\w.-]{20,}$/.test(String(ha.token)))) {
    S.ha = { url: String(ha.url || ""), token: String(ha.token || ""), at: +ha.at }; homeInfo = null; saveS();
    plog("info", "🏠 Home Assistant " + (ha.token ? "подключён" : "отключён") + " с другого своего устройства");
  }
  const h = !D.web && body && body.home; if (!h || typeof h !== "object") return;   // браузеру ключ дома ни к чему: Яндекс не пускает запросы со страниц (CORS)
  const tok = String(h.token || ""), at = +h.at || 0;
  if (at <= (+S.home.at || 0) || (tok && !/^[\w.-]{20,}$/.test(tok)) || tok === (S.home.token || "")) return;
  S.home.token = tok; S.home.at = at; homeInfo = null; saveS();
  plog("info", "🏠 умный дом Яндекса " + (tok ? "подключён" : "отключён") + " с другого своего устройства");
}
async function clHello() {
  const k = clKeys();
  // ver (30.10): версия программы — близкие видят, что у кого старая версия и почему группа не появилась
  const iv = String(clInfo().version || "").trim();
  clPeople(await clReq("POST", "/close/hello", { dev: k.dev, pub: k.pub, devname: (clInfo().device || "Телефон"), name: (S.close && S.close.name) || S.user_name || "",
    ...(iv ? { ver: (D.web || /-web$/.test(iv) ? "web " : "phone ") + iv } : {}) }));
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
  if ((kind || "msg") === "msg" && !extra && typeof grMatch === "function") { const g = String(who || "")[0] === "g" && grOf(who) || (!clMatch(who, CLS.people) && grMatch(who));
    if (g) return grSend(g.gid, text, files); }   // «напиши в группу Семья: …»
  const p = clPerson(who), k = clKeys();
  if (!(p.devs || []).length) throw new Error(`У ${p.name} Dewiar ещё не открывался после приглашения — сообщение дойдёт, когда откроет.`);
  const fl = [];
  for (const f of files || []) {                // {name, type, bytes: Uint8Array}
    if (f.bytes.length > 10 * 1024 * 1024) throw new Error(`«${f.name}» больше 10 МБ — такие пока не отправить.`);
    const fk = DC().randomBytes(32), blob = DC().seal(fk, f.bytes);
    const d = await clReq("POST", "/close/file", clStdB64(blob), "&b64=1&to=" + encodeURIComponent(p.pid));
    fl.push({ id: d.id, name: f.name, size: f.bytes.length, type: f.type || "", key: DC().b64e(fk) });
    if (typeof clIsImg === "function" && clIsImg(f)) await clImgPut(d.id, f.bytes, f.type);   // своё фото — сразу превью
  }
  const body = Object.assign({}, extra || {}, { t: String(text || "").trim(), ts: Date.now(), mid: Math.random().toString(36).slice(2, 12) + Date.now().toString(36), name: CLS.me.name || "" });
  if (fl.length) body.f = fl;
  if ((kind || "msg") === "msg" && !body.t && !fl.length) throw new Error("пустое сообщение");
  const env = DC().encryptFor(body, DC().b64d(k.priv), k.dev, clTargets(p));
  const d = await clReq("POST", "/close/send", { to: p.pid, env, kind: kind || "msg" });
  if ((kind || "msg") !== "msg") return d;
  const it = { mid: body.mid, ts: body.ts, out: true, t: body.t, f: fl, sid: +d.id || 0 };   // sid — номер письма у близкого: «доставлено», «прочитано»
  clAdd(p.pid, it); plog("info", `💌 близким: ${p.name} ← ${clip(body.t || "файл")}`); return Object.assign({ to: p.name }, it);
}
/* Отправка — сразу на экране (28.10, владелец: «в группу отправляет с ощутимой задержкой»): сообщение появляется мгновенно
   с часиками, поле пустеет; письмо (шифрование, сайт) уходит в фоне, потом на месте — настоящее, с галочкой. Не ушло —
   убираем и возвращаем текст в поле. Только текст: файлы ждут, как раньше. */
/* Файл в «Близкие» (30.10, Валера: «прикрепил фото, но вижу — не отправилось»): фото больше 1,5 МБ сжимается до 2560 px
   JPEG (снимок камеры 8 МБ base64 — запрос ~11 МБ, сайт его не примет); остальное — до 10 МБ как есть. */
function clFileTake(f, after) {
  const add = (it) => { clFiles.push(it); (after || clRender)(); };
  if (typeof clIsImg === "function" && clIsImg(f) && f.size > 1.5e6 && !/gif$/i.test(f.type || "")) {
    const fr = new FileReader();
    fr.onload = () => { const im = new Image();
      im.onload = () => { try { const k = Math.min(1, 2560 / Math.max(im.naturalWidth, im.naturalHeight)), c = document.createElement("canvas");
        c.width = Math.round(im.naturalWidth * k); c.height = Math.round(im.naturalHeight * k); c.getContext("2d").drawImage(im, 0, 0, c.width, c.height);
        const u = c.toDataURL("image/jpeg", 0.85), bin = atob(u.split(",")[1]), b = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) b[i] = bin.charCodeAt(i);
        add({ name: String(f.name || "фото").replace(/\.[a-z0-9]+$/i, "") + ".jpg", type: "image/jpeg", bytes: b }); }
        catch (e) { toast("Фото не сжалось — попробуйте другое", 3000); } };
      im.onerror = () => toast("Это фото не открылось — попробуйте другое", 3000); im.src = String(fr.result); };
    fr.readAsDataURL(f); return;
  }
  if (f.size > 10 * 1024 * 1024) { toast(`«${f.name}» больше 10 МБ`); return; }
  const fr = new FileReader(); fr.onload = () => add({ name: f.name, type: f.type, bytes: new Uint8Array(fr.result) }); fr.readAsArrayBuffer(f);
}
/* С файлами — тоже сразу пузырём «Отправляю…» с именами файлов; не ушло — пузырь уходит, файлы и текст возвращаются в поле
   и понятная причина (большой файл — так и сказать). */
async function clSendFiles(pid, t) {
  const files = clFiles; clFiles = [];
  const tmp = { mid: "tmp" + Date.now().toString(36), ts: Date.now(), out: true, t, pend: true, f: files.map(f => ({ name: f.name, size: f.bytes.length })) };
  clAdd(pid, tmp); $("#cl-text").value = ""; clRender();
  const drop = () => { const st = clLoad(); st.hist[pid] = (st.hist[pid] || []).filter(x => x.mid !== tmp.mid); clSave(); };
  try { await clSend(pid, t, files); drop(); clRender(); }
  catch (e) {
    drop(); clFiles = files.concat(clFiles); clRender();
    if ($("#cl-text") && !$("#cl-text").value) $("#cl-text").value = t;
    toast(/413|больш/i.test(e.message) ? "Файл слишком большой — до 10 МБ. Сожмите или отправьте поменьше." : "Не ушло: " + e.message + " — нажмите «Отправить» ещё раз", 5000);
  }
}
async function clSendSoon(pid, t, fn) {
  const tmp = { mid: "tmp" + Date.now().toString(36), ts: Date.now(), out: true, t, pend: true };
  clAdd(pid, tmp); $("#cl-text").value = ""; clRender();
  const drop = () => { const st = clLoad(); st.hist[pid] = (st.hist[pid] || []).filter(x => x.mid !== tmp.mid); clSave(); };
  try { await fn(); drop(); }
  catch (e) { drop(); toast(e.message, 4000); if ($("#cl-text") && !$("#cl-text").value) { clRender(); $("#cl-text").value = t; return; } }
  clRender();
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
/* Больше смайлов (24.10, владелец: «в раздел Близкие нужно больше смайлов»): вкладки по темам, первая — частые (они же
   реакции). Только эмодзи, которые есть и на старых телефонах и в Windows 10 (без новинок Unicode 14+). */
const CL_EMO_SETS = [["Частые", CL_EMO],
  ["Смайлы", ["😀", "😃", "😄", "😅", "🤣", "🙂", "😉", "😍", "🥰", "😘", "😋", "😎", "🤩", "🥳", "😌", "😏", "🤗", "🤭", "😇", "🙃", "😴", "🙄", "😬", "😮", "🤯", "😢", "😭", "🥺", "😤", "😡", "🥶", "🥵", "🤒", "🤧", "😷", "🤐"]],
  ["Жесты", ["👋", "👌", "✌️", "🤞", "🤙", "👏", "🙌", "🙏", "💪", "👎", "👉", "☝️", "🤷", "🤦", "🙈", "🙉", "🙊", "💃", "🕺", "👀"]],
  ["Сердца", ["🧡", "💛", "💚", "💙", "💜", "🖤", "🤍", "💔", "💕", "💖", "💘", "💋", "✨", "🔥", "⭐", "🌟", "💯", "🎉", "🎊", "🥂"]],
  ["Природа", ["☀️", "🌤️", "🌧️", "⛈️", "❄️", "🌈", "🌙", "🌸", "🌹", "🌷", "🌻", "🌿", "🍀", "🍁", "🐱", "🐶", "🐻", "🐰", "🦊", "🐼", "🐸", "🐝", "🦋", "🐟"]],
  ["Еда", ["☕", "🍵", "🍰", "🎂", "🍫", "🍪", "🍎", "🍓", "🍉", "🍌", "🍕", "🍔", "🍟", "🍝", "🥗", "🍲", "🥞", "🍷", "🍺", "🥤"]],
  ["Дела", ["🏠", "🚗", "🚕", "✈️", "🚆", "🏖️", "⚽", "🏃", "🎵", "🎮", "🎁", "📞", "📷", "💻", "📚", "📌", "💡", "⏰", "💤", "✅", "❌", "❓", "⚠️", "💰"]]];
let clEmoTab = 0;
/* смайлы картинками Fluent (0.63, ui/assets/emoji/emoji.js): выбор — «Недавние», разделы, поиск; в тексте — картинки */
const clEmo = (escaped) => window.DewiarEmoji ? DewiarEmoji.html(escaped) : escaped;
const clEmoNew = () => !!(window.DewiarEmoji && DewiarEmoji.ready);
const clEmoHtml = () => clEmoNew() ? "" : `<div class="clemo-tabs">${CL_EMO_SETS.map(([n, l], i) => `<button data-t="${i}" class="${i === clEmoTab ? "on" : ""}" aria-label="${n}">${l[0]}</button>`).join("")}</div>`
  + `<div class="clemo-g">${CL_EMO_SETS[clEmoTab][1].map(e => `<button data-e="${e}" aria-label="Вставить ${e}">${e}</button>`).join("")}</div>`;
function clEmoInsert(e) {
  const ta = $("#cl-text"), a = ta.selectionStart ?? ta.value.length, z = ta.selectionEnd ?? a;
  ta.value = ta.value.slice(0, a) + e + ta.value.slice(z); ta.selectionStart = ta.selectionEnd = a + e.length;
}
function clEmoBind() {
  if (clEmoNew() && $("#cl-emo")) return DewiarEmoji.picker($("#cl-emo"), { onPick: clEmoInsert });
  $$("#cl-emo [data-t]").forEach(b => b.onclick = () => { clEmoTab = +b.dataset.t; $("#cl-emo").innerHTML = clEmoHtml(); clEmoBind(); });
  $$("#cl-emo button[data-e]").forEach(b => b.onclick = () => {           // вставить в текст там, где курсор
    const ta = $("#cl-text"), a = ta.selectionStart ?? ta.value.length, z = ta.selectionEnd ?? a;
    ta.value = ta.value.slice(0, a) + b.dataset.e + ta.value.slice(z); ta.selectionStart = ta.selectionEnd = a + b.dataset.e.length; });
}
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
    if (wkJobs().length && Date.now() - (wkLoad().at || 0) > 3600000) await wkRefresh().catch(() => { });   // и работы: устройства руководителей
    const d = await clReq("GET", "/close/inbox", null, "&after=" + (+st.cursor || 0) + "&geo=1&gup=1");
    let got = 0, refreshed = false;
    for (const it of d.items || []) {
      if (it.kind === "ring") continue;                    // признак звонка — для службы CloseLive; сам звонок — в «sig»
      if (it.kind === "gup") { if (!refreshed) { refreshed = true; try { await clHello(); } catch (e) { } } continue; }   // группы изменились — список сразу (30.10)
      if (it.kind === "grp" && !refreshed && typeof grOf === "function" && !grOf(String((it.env || {}).g || ""))) {   // письмо раньше, чем узнали о группе
        refreshed = true; try { await clHello(); } catch (e) { } }
      if (it.kind === "workin" || it.kind === "workx") { wkKind(it); continue; }   // «Работа» (work.js): знаки сайта без шифра
      const env = it.env || {};
      const pubOf = () => clPubOf(it.peer, env.fd, it.out) || (it.kind === "work" && !it.out ? wkPub(it.peer, env.fd) : null)
        || (it.kind === "grp" && !it.out && typeof grPubOf === "function" ? grPubOf(String(env.g || ""), it.peer, env.fd) : null);   // участник группы — не обязательно близкий
      let pub = pubOf();
      if (!pub && !refreshed) { refreshed = true; try { await clHello(); if (it.kind === "work") await wkRefresh(); } catch (e) { } pub = pubOf(); }
      if (!pub) continue;
      let body; try { body = DC().decryptFrom(env, DC().b64d(k.priv), k.dev, pub); } catch (e) { plog("warn", "близкие: не открылось — " + e.message); continue; }
      if (it.kind === "sig") { try { clSig(it.peer, it.name, body.s || {}); } catch (e) { } continue; }
      if (it.kind === "grp") { try { if (grIn(it, body)) got++; } catch (e) { plog("warn", "группа: " + e.message); } continue; }   // «Группы своих» (groups.js)
      if (it.kind === "work") { try { wkKind(it, body); } catch (e) { plog("warn", "работа: " + e.message); } continue; }   // поручения руководителя
      if (it.kind === "geo") { if (!it.out) radTake(it.peer, it.name || "", body.g); continue; }   // место для радара «Рядом»
      if (it.kind === "own") { if (it.out && env.fd !== k.dev) ownApply(body); continue; }   // от своего же устройства
      if (it.kind === "fam") { try { famIn(it.peer, it.name || "", body, !!it.out); } catch (e) { plog("warn", "семья: " + e.message); } continue; }   // общий бюджет
      if (body.re) {                                        // реакция на сообщение — значком на нём, не новым сообщением
        const e = CL_EMO.includes(body.e) ? body.e : String(body.e || "").slice(0, 8);
        if (clReAt(it.peer, String(body.re), it.out ? "me" : "them", e) && !it.out) {
          if (clCur === it.peer && $("#sh-close").classList.contains("on")) clRender();
          else if (!document.hidden && e) toast(`${it.name || "Близкий"}: ${e} на ваше сообщение`, 2600);
        }
        continue;
      }
      const m = { mid: body.mid || String(it.id), ts: +body.ts || it.ts * 1000, out: !!it.out, t: String(body.t || "").slice(0, 20000), f: (body.f || []).filter(x => x && typeof x === "object").slice(0, 10), ...(body.wave ? { wave: 1 } : {}),
        sid: it.out ? (+it.rid || 0) : (+it.id || 0) };
      if (!clAdd(it.peer, m) || m.out) continue;
      got++;
      if (!(clCur === it.peer && $("#sh-close").classList.contains("on"))) { st.unread[it.peer] = (st.unread[it.peer] || 0) + 1; clSave(); }
      clTell(it.name || "Близкий", m, it.peer);
    }
    st.cursor = Math.max(+st.cursor || 0, +d.last || 0);
    let mk = false;                                       // мои письма у близких: доставлено / прочитано до номера
    if (d.marks && typeof d.marks === "object" && JSON.stringify(d.marks) !== JSON.stringify(st.marks || {})) { st.marks = d.marks; mk = true; }
    if (d.gmarks && typeof d.gmarks === "object" && !Array.isArray(d.gmarks) && JSON.stringify(d.gmarks) !== JSON.stringify(st.gmarks || {})) { st.gmarks = d.gmarks; mk = true; }   // «прочитали» в группах
    clSave(); clBadge(); clWatch();
    if ((got || (mk && clCur)) && $("#sh-close").classList.contains("on")) clRender();
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
  const c = syncCred(), st = clLoad(), j = c && (st.people.length || wkJobs().length) ? JSON.stringify({ base: c.base, token: c.token, link: c.link && c.link !== c.token ? c.link : "", cursor: +st.cursor || 0 }) : "";
  if (j !== clWatch.last) { clWatch.last = j; D.closeWatch(j); }
  const live = !!j && clLiveOn();                         // «на связи» — служба CloseLive: сообщения и звонки сразу
  if (D.closeLive && live !== clWatch.live) { clWatch.live = live; D.closeLive(live); }
}
const clActive = () => { const st = clLoad(); return st.people.length > 0 || wkJobs().length > 0 || Date.now() < devBrainsUntil || bsActive() || (st.invite && Date.now() / 1000 < (st.invite.expires || 0)); };
function clSchedule() {
  clearTimeout(clTimer);
  clTimer = setTimeout(async () => { if (!document.hidden || clFast) await clPoll(); clSchedule(); }, clFast ? 1200 : clActive() ? 6000 : 600000);   // во время звонка — и в фоне: отбой и «ответили» не должны теряться
}
function clPrompt() {
  const st = clLoad(); if (!st.people.length) return "";
  return "БЛИЗКИЕ (переписка с их помощниками Dewiar, сообщения шифруются): " + st.people.map(p => p.name).join(", ")
    + ". Кто-то из них (в любой форме имени: «Люде» = Людмила, «Исаевой Людмиле» = Людмила Исаева) — СНАЧАЛА через Dewiar: «напиши/передай/скажи» — close_send (дойдёт в его Dewiar, он услышит вслух), «позвони» — close_call (video true — «по видео»); «что мне писали», «что ответила мама» — close_read; «где мама?», «далеко ли Андрей?» — close_where (по радару «Рядом»; адресов не называй); «помаши маме» — close_wave. Только людям НЕ из этого списка — телефон (call) и мессенджеры."
    + ((st.groups || []).length ? " ГРУППЫ: " + st.groups.map(g => `«${g.name}»`).join(", ") + " — «напиши в группу …» / «напиши семье» (если так называется группа): close_send, to — название группы, письмо получат все." : "");
}
/* «Отправлено» ✓, «Доставлено» ✓✓, «Прочитано» ✓✓ мятным (24.10, владелец: «не понятно, прочитал ли человек сообщение,
   дошло ли оно»). sid — номер письма в ящике близкого (/close/send), marks[pid] = [забрал до, прочитал до] (/close/inbox). */
function clMark(m, pid) {
  if (m.out && m.pend) return "pend";
  if (!m.out || !m.sid) return "";
  const mk = (clLoad().marks || {})[pid] || [0, 0];
  return mk[1] >= m.sid ? "read" : mk[0] >= m.sid ? "dlv" : "sent";
}
const CL_TICK = { pend: ["Отправляю…", "M12 7v5l3 2M12 21a9 9 0 1 1 0-18 9 9 0 0 1 0 18z"], sent: ["Отправлено", "M5 12.5l4 4 9-9"], dlv: ["Доставлено", "M2.5 12.5l4 4 9-9M10.5 15.5l1 1 9-9"], read: ["Прочитано", "M2.5 12.5l4 4 9-9M10.5 15.5l1 1 9-9"] };
const clTick = (m, pid) => { const k = clMark(m, pid); return k ? `<i class="clck ${k}" aria-label="${CL_TICK[k][0]}"><svg viewBox="0 0 24 24"><path d="${CL_TICK[k][1]}"/></svg></i>` : ""; };
const CL_MARK_RU = { read: " [прочитано]", dlv: " [доставлено, ещё не прочитано]", sent: " [ещё не доставлено — его Dewiar не забирал почту]" };
/* переписку открыли (или помощница прочитала её вслух) — близкому «прочитано»: его письма до последнего номера */
function clSeen(pid) {
  const st = clLoad(), top = Math.max(0, ...(st.hist[pid] || []).filter(m => !m.out).map(m => +m.sid || 0));
  if (!top || top <= (+(st.readUp || {})[pid] || 0) || document.hidden) return;
  clReq("POST", "/close/seen", { peer: pid, upto: top }).then(() => { const s = clLoad(); s.readUp = Object.assign({}, s.readUp, { [pid]: top }); clSave(); }).catch(() => { });
}
function clRecent(who, n = 8) {
  const g = who && typeof grMatch === "function" ? (grOf(who) || (!clMatch(who, clLoad().people) && grMatch(who))) : null;
  if (g) {                                   // «что ответили в группе Семья?» — «кто что берёт?»: Лира собирает ответы
    const st = clLoad(), h = (st.hist[g.gid] || []).slice(-20); delete st.unread[g.gid]; clSave(); clBadge();
    return h.length ? `Группа «${g.name}» (участники: ${(g.members || []).map(m => m.name).join(", ")}):\n` + h.map(m => `${new Date(m.ts).toLocaleString("ru-RU", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })} ${m.out ? "вы" : m.who || "кто-то"}: ${m.t || ""}${(m.f || []).length ? " [файлы: " + m.f.map(x => x.name).join(", ") + "]" : ""}`).join("\n")
      : `В группе «${g.name}» сообщений пока нет.`;
  }
  const st = clLoad(), ps = who ? [clPerson(who)] : st.people, out = [];
  for (const p of ps) { (st.hist[p.pid] || []).slice(-n).forEach(m => out.push([m.ts, `${new Date(m.ts).toLocaleString("ru-RU", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })} ${m.out ? "вы → " + p.name : p.name}: ${m.t || ""}${(m.f || []).length ? " [файлы: " + m.f.map(x => x.name).join(", ") + "]" : ""}${m.rx && (m.rx.me || m.rx.them) ? ` [реакции: ${[m.rx.them && p.name + " " + m.rx.them, m.rx.me && "вы " + m.rx.me].filter(Boolean).join(", ")}]` : ""}${(st.marks || {})[p.pid] ? CL_MARK_RU[clMark(m, p.pid)] || "" : ""}`])); delete st.unread[p.pid]; clSeen(p.pid); }
  clSave(); clBadge(); out.sort((a, b) => a[0] - b[0]);
  return out.slice(-n * 2).map(x => x[1]).join("\n") || "Сообщений пока нет.";
}
async function clInvite(renew) {
  const d = await clReq("POST", "/close/invite", { renew: !!renew });
  clLoad().invite = { link: d.link, expires: d.expires }; clSave(); clSchedule(); return d;
}
async function clAcceptLink(link) {
  const t = clToken(link); if (!t) { showBot("Это не ссылка-приглашение в «Близкие».", "err"); return; }
  if (!syncCred()) { S.closePending = t; saveS(); showBot("Приглашение в «Близкие» сохранено. Подключите Dewiar (Настройки → Мозг → «Подключить мозг Dewiar») — и я его приму.", ""); return; }
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
    face: () => p.face ? clFace(p.pid, p.face) : "",             // фото близкого на экране звонка (пакет 27.10)
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
  DewiarCodes.scan({ title: "Наведите на код", sub: "QR, чек, штрихкод, Data Matrix, печать Dewiar", onError: (m) => showBot("Сканер: " + m, "err"),
    onResult: (txt, fmt) => { scanChime(); scanResult(txt, fmt); } });
}
/* №650 (11.11, McDuck: «сканер QR-кода чеков — и бухгалтерия расходов»): QR кассового чека России
   «t=20261111T1530&s=1234.00&fn=…&i=…&fp=…&n=1» — сумма и время покупки прямо в коде. Сканер узнаёт чек и предлагает
   «Записать трату» с датой чека (n=2 — возврат: доход); тот же чек второй раз не записывается. Товары по строкам — у
   ФНС, им нужен вход: в плане. */
function receiptQr(t) {
  const s = String(t || "").trim();
  if (!/(?:^|&)t=\d{8}T\d{4}/.test(s) || !/(?:^|&)s=\d/.test(s) || !/(?:^|&)fn=\d{6,}/.test(s)) return null;
  const p = {}; s.split("&").forEach(kv => { const i = kv.indexOf("="); if (i > 0) p[kv.slice(0, i).toLowerCase()] = kv.slice(i + 1); });
  const m = /^(\d{4})(\d\d)(\d\d)T(\d\d)(\d\d)/.exec(p.t || ""), sum = Math.round(parseFloat(String(p.s || "").replace(",", ".")) * 100) / 100;
  if (!m || !(sum > 0) || sum > 1e8) return null;
  return { date: `${m[1]}-${m[2]}-${m[3]}`, time: `${m[4]}:${m[5]}`, sum, kind: String(p.n) === "2" || String(p.n) === "3" ? "income" : "expense",
    id: `чек ${p.fn}/${p.i || "?"}/${p.fp || "?"}` };
}
/* №666 (12.11, Сергей, Беларусь): «при сканировании QR-кода не добавляет в расходы» — у белорусского электронного чека
   в QR только ссылка (r.eplus.by/…), суммы в коде нет. Сканер узнаёт такой чек, читает его страницу и предлагает
   «Записать трату» в белорусских рублях; страница не прочиталась — честно просит назвать сумму (не придумывает). */
const ERECEIPT = [{ rx: /(^|\.)eplus\.by$/i, cur: "BYN" }];
function ereceiptHost(url) {
  let h = ""; try { h = new URL(url).hostname; } catch (e) { return null; }
  return ERECEIPT.find(x => x.rx.test(h)) || null;
}
function ereceiptParse(html) {
  const t = String(html || "").replace(/<script[\s\S]*?<\/script>|<style[\s\S]*?<\/style>/gi, " ").replace(/<[^>]+>/g, " ").replace(/&nbsp;|&#160;/g, " ").replace(/\s+/g, " ");
  const m = /(?:ИТОГО(?:\s+К\s+ОПЛАТЕ)?|Итого(?:\s+к\s+оплате)?|К\s+оплате|Всего(?:\s+к\s+оплате)?|Сумма\s+(?:чека|покупки|оплаты))\s*[:=]?\s*(?:BYN|руб\.?|р\.)?\s*(\d{1,3}(?:[ \u00a0]?\d{3})*(?:[.,]\d{1,2})?)/.exec(t);
  if (!m) return null;
  const sum = Math.round(parseFloat(m[1].replace(/[ \u00a0]/g, "").replace(",", ".")) * 100) / 100;
  if (!(sum > 0) || sum > 1e7) return null;
  const d = /(\d{2})\.(\d{2})\.(\d{4})(?:\D{1,3}(\d{1,2}):(\d{2}))?/.exec(t), now = new Date();
  return { sum, date: d ? `${d[3]}-${d[2]}-${d[1]}` : now.toISOString().slice(0, 10), time: d && d[4] ? `${d[4].padStart(2, "0")}:${d[5]}` : `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}` };
}
async function ereceiptFlow(url, er) {
  showBot(window.t("scan.ereceipt.reading"));
  let rc = null;
  try { rc = ereceiptParse((await http("GET", url, { headers: { "User-Agent": "Mozilla/5.0 (Linux; Android 14) Dewiar" }, timeout: 15000 })).body); }
  catch (e) { plog("warn", "e-receipt: " + e.message); }
  if (!rc) {
    const msg = window.t("scan.ereceipt.nosum");
    showBot(msg); scanNote(window.t("scan.note.ereceipt_nosum", { url }));
    $("#card").innerHTML = `<div class="start"><button class="btn p" id="sc-open">${esc(window.t("scan.ereceipt.open"))}</button></div>`;
    $("#sc-open").onclick = () => D.openUrl(url);
    say(window.t("scan.ereceipt.nosum_say"));
    return;
  }
  return receiptOffer(Object.assign(rc, { kind: "expense", id: "e-receipt " + url.split("/").pop().slice(0, 40), cur: er.cur }));
}
/* Что показал сканер — в историю разговора: следующую просьбу («я сосканировал, что теперь?») модель понимает по нему,
   а не придумывает (№666: вписала трату с суммой прошлого дохода) */
function scanNote(text) {
  try { history.push({ role: "assistant", content: window.t("scan.note.prefix") + " " + String(text).slice(0, 600), who: persona().id, t: Date.now() }); saveH(); } catch (e) { }
}
const CUR_WORD = { RUB: ["₽", "money.word.RUB"], BYN: ["BYN", "money.word.BYN"] };
function receiptOffer(rc) {
  const [y, mo, d] = rc.date.split("-").map(Number), when = `${d} ${["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"][mo - 1]} ${rc.time}`;
  const amt = rc.sum.toLocaleString("ru-RU", { minimumFractionDigits: rc.sum % 1 ? 2 : 0, maximumFractionDigits: 2 });
  const cur = rc.cur || "RUB", [sym, wkey] = CUR_WORD[cur] || [cur, ""], word = wkey ? window.t(wkey) : cur;
  const have = money().some(x => String(x.note || "").includes(rc.id));
  showBot(`🧾 Чек на ${amt} ${sym} — ${when}${rc.kind === "income" ? " (возврат)" : ""}.` + (have ? " Этот чек уже записан в «Деньгах»." : ""));
  scanNote(window.t(have ? "scan.note.receipt_have" : "scan.note.receipt", { amt: `${amt} ${sym}`, when }));
  $("#card").innerHTML = `<div class="start">${have ? "" : `<button class="btn p" id="sc-rc">${rc.kind === "income" ? "Записать возврат" : "Записать трату"}</button>`}<button class="btn" id="sc-copy">Скопировать</button></div>`;
  $("#sc-copy").onclick = () => { D.copy(`${amt} ${sym}, ${when}`); toast("Скопировано"); };
  if (!have) $("#sc-rc").onclick = () => {
    const m = money(); if (m.some(x => String(x.note || "").includes(rc.id))) { toast("Этот чек уже записан"); return; }
    const x = { id: uid("m"), date: rc.date, kind: rc.kind, amount: rc.sum, currency: cur, category: rc.kind === "income" ? "Возврат" : "Покупки", note: rc.id };
    m.push(x); saveMoney(m);
    try { famShareSpend(x); } catch (e) { plog("warn", "семья: " + e.message); }
    $("#card").innerHTML = "";
    showBot(`Записала: ${rc.kind === "income" ? "+" : "−"}${amt} ${sym}, ${x.category}, ${when}. Категорию можно поправить словами: «это были продукты».`);
    scanNote(window.t("scan.note.saved", { amt: `${rc.kind === "income" ? "+" : "−"}${amt} ${sym}`, cat: x.category }));
    say(`Записала ${rc.kind === "income" ? "возврат" : "трату"} ${amt} ${word}.`);
  };
  say(`Чек на ${amt} ${word}.` + (have ? " Он уже записан." : " Записать трату?"));
}
function scanResult(txt, format) {
  const t = String(txt || "").trim();
  plog("info", "📷 код (" + (format || "?") + "): " + clip(t, 80));
  if (wkIsLink(t)) return wkLink(t);                      // печать «Работы» от руководителя (work.js)
  if (/^dewiar:\/\/home\?/.test(t)) return homeClaimFlow(t);     // «Дома по Wi-Fi» с экрана компьютера
  if (/^dewiar:\/\/pair|download\.php\?(?:.*&)?pair=\d{6}/.test(t)) return devClaimFlow(t);   // «Подключить ещё устройство» (devices.js)
  if (/^dewiar:\/\/close|[?&]close=/.test(t)) return clAcceptLink(t);
  if (/^dewiar:\/\/ref|download\.php\?(?:.*&)?ref=/.test(t)) { const c = (/[?&](?:c|ref)=([A-Za-z0-9]+)/.exec(t) || [])[1] || ""; return handleIntent({ action: "link", url: "dewiar://ref?c=" + c }); }
  if (/^dewiar:/.test(t)) return handleIntent({ action: "link", url: t });
  if (/^https?:\/\//i.test(t)) {
    const er = ereceiptHost(t);
    if (er) return ereceiptFlow(t, er);
    let host = t; try { host = new URL(t).hostname; } catch (e) { }
    showBot(`В коде ссылка: ${t}`);
    scanNote(window.t("scan.note.link", { url: t }));
    $("#card").innerHTML = `<div class="start"><button class="btn p" id="sc-open">Открыть ${esc(host)}</button><button class="btn" id="sc-copy">Скопировать</button></div>`;
    $("#sc-open").onclick = () => D.openUrl(t); $("#sc-copy").onclick = () => { D.copy(t); toast("Скопировано"); };
    say("В коде ссылка на " + host.replace(/^www\./, ""));
    return;
  }
  // штрихкод или Data Matrix товара — разбирать код здесь не нужно: модель знает, как устроены коды «Честного знака»
  // (01 — GTIN, 21 — серийный номер…), и сама найдёт товар в интернете по штрихкоду
  if (/^(ean|upc|datamatrix)/.test(format || "") && /^[\x1d\x20-\x7e]{8,}$/.test(t) && /\d{8}/.test(t)) {
    showYou(trL("📦 Что за товар?"));
    return ask(`Я отсканировал код на товаре (${format}): ${t.replace(/\x1d/g, "<GS>")}. Разбери его и найди в интернете по штрихкоду, `
      + `что это за товар — коротко. Не нашлось — так и скажи. Если это код «Честного знака», в конце одной фразой: подлинность `
      + `и историю упаковки показывает официальное приложение «Честный знак».`, { hidden: true });
  }
  const rc = receiptQr(t);
  if (rc) return receiptOffer(rc);
  showBot("В коде: " + t);
  scanNote(window.t("scan.note.text", { text: t }));
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
