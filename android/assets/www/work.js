/* «Работа» — режим «Сотрудник» (0.55; владелец 28.10: «сотрудник живой человек, он может использовать решение для себя,
   с близкими… а выполнять поручения до тех пор, пока работает на работе, он ведь может уволиться… механизм перепривязки,
   по коду-ссылке, ацтек коду… руководителем группы и в то же время выполнять указания вышестоящего… на двух работах»).

   Рабочее живёт отдельно от личного: файл work.json, свой лист #sh-work и портфель в верхней полосе (виден, только когда
   есть работа). Работ может быть несколько — по вкладке на каждую. Связь — та же, что у «Близких» (ключи телефона,
   cloud.php ?p=/close/*), но руководитель — не близкий: своя связь на сайте (?p=/work/*), конверты kind «work».
     руководитель → сюда: {t: "snap", team, boss, who, tasks[], repeats[], text, quiet} — его поручения целиком (core/team.py
       _app_snapshot) и текст уведомления («Новое поручение…», «Принято», напоминание за час);
     отсюда → руководителю: {t: "act", act: take | done | move | msg | hello, tid, text, photo {id, key}, due, why}.
   Фото к «Сделано» шифруется здесь же (как файлы «Близких») и лежит на сайте для компьютера руководителя.
   Вход — печать Dewiar или ссылка …/download.php?work=… (сканер, dewiar://work?t=…, вставить ссылку): ?p=/work/peek →
   «Присоединиться?» → ?p=/work/accept. Знак сайта «workx» — связь кончилась (убрали или вошли с другого аккаунта):
   работа со всем рабочим уходит с телефона, личное остаётся. «Уйти с этой работы» — ?p=/work/leave {pid}.
   Детский режим прячет всё рабочее. Ядро app.js зовёт отсюда: wkPub, wkKind, wkHas, wkPrompt, wkTools, wkTool, wkLink. */
"use strict";
let WKS = null, wkCur = "", wkForm = null, wkJoinT = null, wkShowFeed = false, wkAdd = false, wkGuest = null;
const WK_ST = { new: "Новые", work: "В работе", moved: "Перенесено", done: "Сделано", ok: "Принято" };
const WK_ORDER = ["new", "moved", "work", "done", "ok"];
const WK_ONE = { new: "новое", work: "в работе", moved: "перенесено", done: "сделано", ok: "принято" };
const WK_IC = '<svg viewBox="0 0 24 24"><rect x="3" y="7.5" width="18" height="12.5" rx="2.5"/><path d="M8.5 7.5V6a2 2 0 0 1 2-2h3a2 2 0 0 1 2 2v1.5M3 12.5h18M11 12.5v1.6h2v-1.6"/></svg>';

function wkLoad() {
  if (WKS) return WKS;
  try { WKS = JSON.parse(fileGet("work.json") || "{}") || {}; } catch (e) { WKS = {}; }
  WKS = Object.assign({ jobs: {}, at: 0, said: {} }, WKS);
  return WKS;
}
const wkSave = () => fileSave("work.json", JSON.stringify(WKS));
const wkJobs = () => Object.values(wkLoad().jobs).sort((a, b) => (a.since || 0) - (b.since || 0));
const wkHas = () => !kidsOn() && wkJobs().length > 0;
const wkToken = (s) => { const m = /[?&](?:work|t)=([A-Za-z0-9_-]{8,64})/.exec(String(s || "")); return m ? m[1] : ""; };
const wkIsLink = (s) => /^dewiar:\/\/work|download\.php\?(?:.*&)?work=/.test(String(s || "").trim());

/* связи с сайта: bosses — мои работы (ответ /work/peers, /work/accept, /work/leave). Работы, которой там нет, больше нет. */
function wkPeers(d, why) {
  const st = wkLoad(), seen = new Set();
  for (const b of (d && d.bosses) || []) {
    if (!b || !b.pid) continue;
    seen.add(b.pid);
    const j = st.jobs[b.pid] = Object.assign({ snap: { tasks: [], repeats: [] }, feed: [], unread: 0 }, st.jobs[b.pid] || {});
    Object.assign(j, { pid: b.pid, mid: b.mid || "", team: (j.snap && j.snap.team) || b.team || "Работа", who: (j.snap && j.snap.who) || b.who || "",
      boss: (j.snap && j.snap.boss) || b.name || "", since: +b.since || j.since || 0, devs: b.devs || [] });
  }
  Object.keys(st.jobs).forEach(pid => { if (!seen.has(pid)) wkDrop(pid, why || "gone"); });
  st.at = Date.now(); wkSave(); wkBadge();
}
async function wkRefresh() { if (!syncCred()) return; wkPeers(await clReq("GET", "/work/peers")); }
function wkDrop(pid, why) {
  const st = wkLoad(), j = st.jobs[pid]; if (!j) return;
  delete st.jobs[pid]; if (wkCur === pid) wkCur = ""; wkSave(); wkBadge();
  plog("info", `💼 работа «${j.team}» убрана с телефона (${why})`);
  if (why === "self") return;
  const t = why === "boss" ? `Вас убрали из поручений «${j.team}». Рабочее с телефона убрано — личное на месте.`
    : `Поручения «${j.team}» теперь приходят на другой аккаунт. Здесь рабочее убрано — личное на месте.`;
  if (document.hidden) D.notify("💼 " + j.team, t); else showBot(t);
  if ($("#sh-work").classList.contains("on")) wkRender();
}
/* ключ устройства руководителя — чтобы открыть его конверт (зовёт clPubOf) */
function wkPub(peer, dev) {
  const j = wkLoad().jobs[peer], d = ((j || {}).devs || []).find(x => x.dev === dev);
  return d && d.pub ? DC().b64d(d.pub) : null;
}
/* письмо из ящика (зовёт clPoll): workin/workx — знаки сайта без шифра (до расшифровки), work — открытый конверт body */
function wkKind(it, body) {
  if (it.kind === "workin") return;                         // «сотрудник вошёл» — это для руководителя (компьютер)
  if (it.kind === "workx") { if (!it.out && wkLoad().jobs[it.peer]) wkDrop(it.peer, ((it.env || {}).by === "boss") ? "boss" : "moved"); return; }
  if (it.kind === "work" && !it.out && body) wkIn(it.peer, it.name || "", body);   // свои действия (out) — уже на экране
}
function wkIn(peer, name, body) {
  if (!body || body.t !== "snap") return;
  const st = wkLoad();
  const j = st.jobs[peer] = st.jobs[peer] || { pid: peer, devs: [], feed: [], unread: 0, since: Math.floor(Date.now() / 1000) };
  const had = new Set(((j.snap || {}).tasks || []).map(t => t.id));
  j.snap = { team: String(body.team || ""), boss: String(body.boss || ""), who: String(body.who || ""),
    tasks: (Array.isArray(body.tasks) ? body.tasks : []).filter(t => t && t.id).slice(0, 200), repeats: (Array.isArray(body.repeats) ? body.repeats : []).slice(0, 50), ts: Date.now() };
  j.team = j.snap.team || j.team || "Работа"; j.boss = j.snap.boss || j.boss || name; j.who = j.snap.who || j.who || "";
  const text = String(body.text || "").trim().slice(0, 1000);
  const open = $("#sh-work").classList.contains("on") && wkCur === peer && !document.hidden;
  if (text && !body.quiet) {
    j.feed = (j.feed || []).concat([{ ts: +body.ts || Date.now(), t: text }]).slice(-60);
    if (!open) j.unread = (j.unread || 0) + 1;
    wkTell(j, text);
  }
  const fresh = j.snap.tasks.filter(t => !had.has(t.id) && t.state === "new").length;
  if (fresh && !open) j.unread = Math.max(j.unread || 0, 1);
  wkSave(); wkBadge();
  if ($("#sh-work").classList.contains("on")) wkRender();
}
function wkTell(j, text) {
  const line = `${j.team}: ${text}`;
  if (document.hidden || busy || state !== "idle") { D.notify("💼 " + j.team, text); if (document.hidden) return; }
  if (!busy && state === "idle") { showBot(line); if (!(S.close && S.close.speak === false)) say(line); }
}
function wkBadge() {
  const b = $("#b-work"); if (!b) return;
  const boss = typeof bsHas === "function" && bsHas();          // «Сотрудники» — руководителю (boss.js)
  b.hidden = !(wkHas() || boss);
  b.classList.toggle("has", wkJobs().some(j => j.unread > 0) || (boss && bsUnread()));
}

/* ---------- действия: конверт руководителю (и копия своим устройствам) ---------- */
async function wkSend(pid, body) {
  clLoad(); if (!CLS.me.pid || Date.now() - (CLS.hello || 0) > 600000) await clHello();
  let j = wkLoad().jobs[pid]; if (!j) throw new Error("этой работы на телефоне больше нет");
  if (!(j.devs || []).length) { await wkRefresh(); j = wkLoad().jobs[pid]; }
  if (!j) throw new Error("связь с этой работой кончилась");
  if (!(j.devs || []).length) throw new Error("компьютер руководителя ещё не выходил на связь — попробуйте чуть позже");
  const k = clKeys(), to = {}, add = (devs) => (devs || []).forEach(d => { if (d.pub) to[d.dev] = DC().b64d(d.pub); });
  add(j.devs); add((CLS.me || {}).devs); to[k.dev] = DC().b64d(k.pub);
  const env = DC().encryptFor(Object.assign({ t: "act", ts: Date.now(), mid: Math.random().toString(36).slice(2, 12) + Date.now().toString(36) }, body), DC().b64d(k.priv), k.dev, to);
  return clReq("POST", "/close/send", { to: pid, env, kind: "work" });
}
async function wkPhoto(pid, dataUrl) {          // фото «Сделано» — зашифровано здесь, ключ — в конверте руководителю
  const bin = Uint8Array.from(atob(String(dataUrl).split(",")[1] || ""), c => c.charCodeAt(0));
  if (!bin.length) return null;
  const fk = DC().randomBytes(32);
  const d = await clReq("POST", "/close/file", clStdB64(DC().seal(fk, bin)), "&b64=1&to=" + encodeURIComponent(pid));
  return { id: d.id, key: DC().b64e(fk) };
}
async function wkAct(pid, act, tid, extra) {
  const j = wkLoad().jobs[pid], t = j && ((j.snap || {}).tasks || []).find(x => x.id === tid);
  const body = Object.assign({ act, tid: tid || "" }, extra || {});
  if (extra && extra.photoUrl) { body.photo = await wkPhoto(pid, extra.photoUrl); delete body.photoUrl; }
  await wkSend(pid, body);
  if (t) {                                      // сразу на экране; снимок руководителя придёт следом и всё уточнит
    if (act === "take") t.state = "work";
    if (act === "done") { t.state = "done"; t.report = body.text || ""; }
    if (act === "move") { t.state = "moved"; t.due = body.due; t.reason = body.why; t.due_text = wkDue(body.due); t.late = false; }
    wkSave();
  }
  if (act === "msg") { j.feed = (j.feed || []).concat([{ ts: Date.now(), t: body.text || "Фото", out: true }]).slice(-60); wkSave(); }
  plog("info", `💼 ${j ? j.team : "работа"}: ${act}${t ? " «" + clip(t.title, 40) + "»" : ""}`);
}
function wkDue(iso) {
  const d = new Date(iso); if (isNaN(d)) return "";
  const t = new Date(), day = new Date(d.getFullYear(), d.getMonth(), d.getDate()), now = new Date(t.getFullYear(), t.getMonth(), t.getDate());
  const k = Math.round((day - now) / 864e5), hm = `${d.getHours()}:${String(d.getMinutes()).padStart(2, "0")}`;
  const MON = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"];
  return (k === 0 ? "сегодня" : k === 1 ? "завтра" : `${d.getDate()} ${MON[d.getMonth()]}`) + " к " + hm;
}

/* ---------- вход: печать, ссылка, dewiar://work?t= ---------- */
async function wkLink(link) {
  const t = wkToken(link); if (!t) { showBot("Это не приглашение в «Работу» — попросите у руководителя новый код.", "err"); return; }
  if (kidsOn()) { showBot("В детском режиме рабочие приглашения не принимаю.", "err"); return; }
  if (!syncCred()) { S.workPending = t; saveS(); wkGuest = { t }; wkJoinT = null; wkCur = ""; openWork("", true); return; }   // без входа — «Работа без установки» (0.58)
  try {
    const p = await clReq("GET", "/work/peek", null, "&t=" + encodeURIComponent(t));
    if (p.own) { showBot("Это ваше же приглашение — его открывает сотрудник на своём телефоне."); return; }
    wkJoinT = Object.assign({ t }, p); wkCur = ""; openWork("", true);
  } catch (e) { showBot("Приглашение не открылось: " + e.message, "err"); }
}
async function wkAccept() {
  const p = wkJoinT; if (!p) return;
  const r = $("#wk-jres"); if (r) { r.className = "res"; r.textContent = "Подключаю…"; }
  try {
    clKeys(); await clHello();                                // ключи телефона — на сайт: руководитель шифрует для них
    const d = await clReq("POST", "/work/accept", { t: p.t });
    wkJoinT = null; S.workPending = ""; saveS(); wkPeers(d);
    const j = wkJobs().find(x => x.team === (p.team || x.team) && x.boss === (p.boss || x.boss)) || wkJobs().slice(-1)[0];
    wkCur = j ? j.pid : ""; wkRender();
    if (j) wkSend(j.pid, { act: "hello" }).catch(() => { });
    say("Готово! Поручения с работы теперь здесь.");
    clSchedule(); setTimeout(clPoll, 2500);
  } catch (e) { if (r) { r.className = "res err"; r.textContent = e.message; } }
}
async function wkLeave(pid) {
  const j = wkLoad().jobs[pid]; if (!j) return;
  if (!confirm(`Уйти с работы «${j.team}»? Поручения перестанут приходить, всё рабочее исчезнет с телефона. Вернуться — по новому коду от руководителя.`)) return;
  try { const d = await clReq("POST", "/work/leave", { pid }); wkDrop(pid, "self"); wkPeers(d, "self"); toast(`Вы ушли из «${j.team}»`); wkRender(); }
  catch (e) { toast("Не получилось: " + e.message, 3500); }
}

/* ---------- «Работа без установки» (0.58; владелец 28.10): сотрудник без Dewiar открыл ссылку-приглашение — в браузере
   (веб-версия, dwrapp/web/?work=…) или в приложении без входа. Имя — и всё: сайт выдаёт ключ по приглашению (?p=/work/guest,
   без заявки и пароля), им же входим, принимаем приглашение — и сразу «Работа». Своя модель, если была, остаётся. ---------- */
function wkGuestHtml() {
  return `<div class="wk-hero join">${WK_IC}<small>Приглашение на работу</small><b>Поручения — прямо здесь</b>`
    + `<p>Ничего устанавливать и регистрировать не нужно: напишите, как вас зовут, — и поручения руководителя будут приходить сюда.</p></div>`
    + `<div class="card wk-terms"><p>✓ Руководитель видит только поручения: что вы взяли, сделали или перенесли, и что вы ему написали.</p>`
    + `<p>✓ Всё рабочее шифруется на ваших устройствах.</p><p>✓ Уйти можно в любой момент — рабочее исчезнет.</p></div>`
    + `<div class="card"><label class="f"><span>Как вас зовут</span><input id="wk-gname" maxlength="60" autocomplete="name" placeholder="Анна Ким" value="${esc(S.user_name || "")}"></label>`
    + `<button class="btn p w" id="wk-gok" style="margin-top:10px">Начать работу</button><div class="res" id="wk-gres"></div></div>`
    + `<p class="hint wk-foot">${D.web ? "Добавьте эту страницу на главный экран — так поручения будут под рукой. Уведомления приходят, пока страница открыта; приложение Dewiar присылает их всегда." : "Уже есть вход в Dewiar? Войдите в «Настройках» — и откройте ссылку снова."}</p>`;
}
function wkBindGuest() {
  const ok = $("#wk-gok"); if (!ok) return;
  const go = async () => {
    const name = $("#wk-gname").value.trim(), r = $("#wk-gres");
    if (!name) { r.className = "res err"; r.textContent = "Напишите имя — руководитель увидит, кто взял поручение"; $("#wk-gname").focus(); return; }
    ok.disabled = true; r.className = "res"; r.textContent = "Подключаю…";
    try {
      const base = CLOUD_URL.split("?")[0];
      const x = await http("POST", base + "?p=/work/guest", { headers: { "Content-Type": "application/json" }, body: { t: wkGuest.t, name }, timeout: 20000 });
      let d = {}; try { d = JSON.parse(x.body || "{}"); } catch (e) { }
      if (x.status >= 400 || !d.key) throw new Error((d.error && d.error.message) || ("сайт ответил " + x.status));
      if (!S.user_name) S.user_name = name;
      if (S.llm && S.llm.base_url && !S.llm.cloud) { S.sync = Object.assign({}, S.sync, { key: d.key }); saveS(); }   // своя модель остаётся
      else await cloudConnect(d.key, base);
      S.webWork = true; saveS();
      const t = wkGuest.t; wkGuest = null;
      const p = await clReq("GET", "/work/peek", null, "&t=" + encodeURIComponent(t));
      wkJoinT = Object.assign({ t }, p);
      await wkAccept();                                          // условия уже показаны — второй раз «Присоединиться» не спрашиваем
    } catch (e) { ok.disabled = false; r.className = "res err"; r.textContent = "Не получилось: " + e.message; }
  };
  ok.onclick = go; $("#wk-gname").onkeydown = (e) => { if (e.key === "Enter") go(); };
}

/* ---------- лист «Работа» ---------- */
function openWork(pid, join) {
  if (kidsOn()) return;
  if (!join) { wkJoinT = null; wkGuest = null; }
  wkAdd = false;
  const jobs = wkJobs(), boss = bsHas(), ok = (x) => x && (wkLoad().jobs[x] || (x === BS_TAB && boss));
  const first = boss && (bsUnread() || !jobs.some(j => j.unread)) ? BS_TAB : (jobs.find(j => j.unread) || jobs[0] || {}).pid || (boss ? BS_TAB : "");
  wkCur = ok(pid) ? pid : ok(wkCur) ? wkCur : first;
  wkForm = null; wkShowFeed = false; bsForm = null;
  wkRender(); openSheet("#sh-work");
  if (wkCur === BS_TAB && !join) { if (Date.now() - (bsLoad().snap || {}).at > 60000) bsAsk(); clSchedule(); }
  const j = wkLoad().jobs[wkCur];
  if (j && !join && Date.now() - (j.hi || 0) > 120000) { j.hi = Date.now(); wkSave(); wkSend(j.pid, { act: "hello" }).catch(() => { }); }   // свежий снимок
}
function wkRender() {
  const box = $("#work-body"); if (!box) return;
  const st = wkLoad(), jobs = wkJobs(), boss = bsHas();
  if (wkCur === BS_TAB && !boss) wkCur = (jobs[0] || {}).pid || "";
  const j = st.jobs[wkCur];
  $("#wk-join").style.display = jobs.length && !wkJoinT && !wkAdd && wkCur !== BS_TAB ? "" : "none";
  if (wkGuest) { $("#wk-join").style.display = "none"; box.innerHTML = wkGuestHtml(); wkBindGuest(); return; }
  if (wkJoinT) { box.innerHTML = wkJoinHtml(wkJoinT); wkBindJoin(); return; }
  /* вкладки: «Сотрудники» (вы — руководитель, boss.js) и по одной на каждую работу, где вы — сотрудник */
  const all = (boss ? [{ pid: BS_TAB, team: "Сотрудники", unread: bsUnread() }] : []).concat(jobs);
  const tabs = all.length > 1 ? `<div class="seg wk-tabs" role="tablist">${all.map(x => `<button role="tab" data-j="${esc(x.pid)}" class="${x.pid === wkCur ? "on" : ""}" aria-selected="${x.pid === wkCur}">${esc(x.team)}${x.unread ? " •" : ""}</button>`).join("")}</div>` : "";
  if (wkCur === BS_TAB && !wkAdd) { box.innerHTML = tabs + bsHtml(); wkTabsBind(); bsBind(); return; }
  if (!j || wkAdd) { box.innerHTML = wkEmptyHtml(); wkBindJoin(); return; }
  if (j.unread) { j.unread = 0; wkSave(); wkBadge(); }
  const tasks = (j.snap || {}).tasks || [], reps = (j.snap || {}).repeats || [];
  const since = j.since ? new Date(j.since * 1000).toLocaleDateString("ru-RU", { day: "numeric", month: "long" }) : "";
  const last = (j.feed || []).filter(x => !x.out).slice(-1)[0];
  const feed = wkShowFeed ? (j.feed || []).slice(-30) : last ? [last] : [];
  const groups = WK_ORDER.map(s => [s, tasks.filter(t => (s === "done" ? t.state === "done" || t.state === "ok" : t.state === s))]).filter(([s, l]) => l.length && s !== "ok");
  const open = tasks.filter(t => ["new", "work", "moved"].includes(t.state)).length;
  box.innerHTML = tabs
    + `<div class="wk-head"><b>${esc(j.team)}</b><small>${j.boss ? "Руководитель — " + esc(j.boss) : ""}${since ? (j.boss ? " · " : "") + "с " + since : ""}</small></div>`
    + (feed.length ? `<div class="wk-feed">${feed.map(x => `<p class="${x.out ? "out" : ""}"><span>${esc(x.t)}</span><time>${wkWhen(x.ts)}</time></p>`).join("")}${(j.feed || []).length > 1 ? `<button class="lnk" id="wk-feedall">${wkShowFeed ? "Свернуть" : "Вся переписка"}</button>` : ""}</div>` : "")
    + (groups.length ? groups.map(([s, l]) => `<div class="wk-sec"><span>${WK_ST[s]}</span><em>${l.length}</em></div>` + l.map(t => wkCard(t)).join("")).join("")
      : `<div class="card wk-none"><b>Поручений пока нет</b><p class="hint">Новые придут сюда — я скажу вслух. Спросить можно и голосом: «что мне поручили?»</p></div>`)
    + (reps.length ? `<div class="wk-sec"><span>Повторяется</span><em>${reps.length}</em></div><div class="card wk-reps">${reps.map(r => `<p><b>${esc(r.title)}</b><span>${esc(r.rule)}</span></p>`).join("")}</div>` : "")
    + `<div class="wk-sec"><span>Руководителю</span></div><div class="card wk-msg"><textarea id="wk-mtext" rows="2" maxlength="1000" placeholder="Сообщение руководителю…"></textarea>`
    + `<div class="row2"><label class="btn wk-ph"><input type="file" id="wk-mph" accept="image/*" hidden>${WK_CAM}<span>Фото</span></label><button class="btn p" id="wk-msend" style="flex:1">Отправить</button></div><img class="wk-thumb" id="wk-mimg" alt="" hidden><div class="res" id="wk-mres"></div></div>`
    + `<button class="btn w wk-leave" id="wk-leave">Уйти с этой работы</button>`
    + `<p class="hint wk-foot">Рабочее хранится отдельно от личного и шифруется на устройствах. ${open ? `Открытых поручений: ${open}.` : ""}</p>`;
  wkBind(j);
}
const WK_CAM = '<svg viewBox="0 0 24 24"><path d="M4 8.5h3l1.6-2.3h6.8L17 8.5h3a1 1 0 0 1 1 1V18a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9.5a1 1 0 0 1 1-1z"/><circle cx="12" cy="13.3" r="3.4"/></svg>';
function wkWhen(ts) {
  const d = new Date(ts), t = new Date(), hm = `${d.getHours()}:${String(d.getMinutes()).padStart(2, "0")}`;
  return d.toDateString() === t.toDateString() ? hm : d.toLocaleDateString("ru-RU", { day: "numeric", month: "short" }) + ", " + hm;
}
function wkCard(t) {
  const f = wkForm && wkForm.tid === t.id ? wkForm : null, done = t.state === "done" || t.state === "ok";
  const acts = done ? "" : f ? "" : `<div class="wk-acts">${t.state === "new" || t.state === "moved" ? `<button class="btn p" data-a="take">Беру</button>` : ""}`
    + `<button class="btn${t.state === "work" ? " p" : ""}" data-a="done">Сделано</button><button class="btn" data-a="move">Перенести</button></div>`;
  const form = !f ? "" : f.kind === "done"
    ? `<div class="wk-form"><textarea id="wk-ftext" rows="2" maxlength="1000" placeholder="Пара слов — что сделано (можно пропустить)"></textarea>`
      + `<div class="row2"><label class="btn wk-ph"><input type="file" id="wk-fph" accept="image/*" capture="environment" hidden>${WK_CAM}<span>${f.photo ? "Другое фото" : "Фото"}</span></label><button class="btn p" id="wk-fgo" style="flex:1">Отправить</button><button class="btn" id="wk-fx" aria-label="Отмена">✕</button></div>`
      + `<img class="wk-thumb" id="wk-fimg" alt="Фото к поручению"${f.photo ? ` src="${f.photo}"` : " hidden"}><div class="res" id="wk-fres"></div></div>`
    : `<div class="wk-form"><label class="f"><span>Новый срок</span><input type="datetime-local" id="wk-fdue" value="${esc(wkLocal(t.due, 1))}" min="${esc(wkLocal(""))}"></label>`
      + `<label class="f"><span>Причина</span><input id="wk-fwhy" maxlength="300" placeholder="клиент перенёс встречу"></label>`
      + `<div class="row2"><button class="btn p" id="wk-fgo" style="flex:1">Перенести</button><button class="btn" id="wk-fx" aria-label="Отмена">✕</button></div><div class="res" id="wk-fres"></div></div>`;
  const due = t.due_text ? `<span class="wk-due${t.late ? " late" : ""}">${t.late ? "просрочено · " : ""}${esc(t.due_text)}</span>` : "";
  return `<div class="card wk-task s-${esc(t.state)}${t.late ? " late" : ""}" data-t="${esc(t.id)}"><b>${esc(t.title)}</b>${due}`
    + (t.note ? `<p class="wk-note">${esc(t.note)}</p>` : "")
    + (t.remark ? `<p class="wk-remark">Вернули: ${esc(t.remark)}</p>` : "")
    + (t.state === "moved" && t.reason ? `<p class="wk-note">Причина переноса: ${esc(t.reason)}</p>` : "")
    + (done && t.report ? `<p class="wk-note">Ваш отчёт: ${esc(t.report)}</p>` : "")
    + (t.state === "ok" ? `<p class="wk-okd">Принято руководителем</p>` : "")
    + acts + form + `</div>`;
}
function wkLocal(iso, dayAhead) {               // значение для datetime-local: срок + сутки (переносят обычно вперёд) или «сейчас»
  let d = iso ? new Date(iso) : new Date(); if (isNaN(d)) d = new Date();
  if (dayAhead) { const n = new Date(); if (d < n) d = new Date(n.getFullYear(), n.getMonth(), n.getDate(), 18, 0); d = new Date(d.getTime() + 864e5); }
  const p = (x) => String(x).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
}
function wkTabsBind() {
  $$("#work-body .wk-tabs [data-j]").forEach(b => b.onclick = () => {
    wkCur = b.dataset.j; wkForm = null; wkShowFeed = false; bsForm = null; wkRender();
    if (wkCur === BS_TAB && Date.now() - (bsLoad().snap || {}).at > 60000) bsAsk();
  });
}
function wkBind(j) {
  wkTabsBind();
  const fa = $("#wk-feedall"); if (fa) fa.onclick = () => { wkShowFeed = !wkShowFeed; wkRender(); };
  $$("#work-body .wk-task [data-a]").forEach(b => b.onclick = async () => {
    const tid = b.closest(".wk-task").dataset.t, a = b.dataset.a;
    if (a === "take") {
      b.disabled = true;
      try { await wkAct(j.pid, "take", tid); toast("Взяли в работу — руководитель увидит"); } catch (e) { toast("Не ушло: " + e.message, 3500); }
      wkRender(); return;
    }
    wkForm = { tid, kind: a, photo: "" }; wkRender();
    const el = $(a === "done" ? "#wk-ftext" : "#wk-fwhy"); if (el) setTimeout(() => { el.focus(); el.scrollIntoView({ block: "center", behavior: "smooth" }); }, 60);
  });
  const fx = $("#wk-fx"); if (fx) fx.onclick = () => { wkForm = null; wkRender(); };
  const fph = $("#wk-fph"); if (fph) fph.onchange = async (e) => {
    const f = e.target.files && e.target.files[0]; if (!f) return;
    try { wkForm.photo = await shrinkImage(f, 1600); const im = $("#wk-fimg"); im.src = wkForm.photo; im.hidden = false; } catch (x) { toast(x.message); }
  };
  const go = $("#wk-fgo"); if (go) go.onclick = async () => {
    const r = $("#wk-fres"), f = wkForm; if (!f) return;
    let extra = {};
    if (f.kind === "done") extra = { text: $("#wk-ftext").value.trim(), photoUrl: f.photo || "" };
    else {
      const due = $("#wk-fdue").value, why = $("#wk-fwhy").value.trim();
      if (!due || isNaN(new Date(due))) { r.className = "res err"; r.textContent = "Выберите новый срок"; return; }
      if (!why) { r.className = "res err"; r.textContent = "Напишите причину — руководитель увидит её вместе с новым сроком"; $("#wk-fwhy").focus(); return; }
      extra = { due, why };
    }
    go.disabled = true; r.className = "res"; r.textContent = extra.photoUrl ? "Отправляю фото…" : "Отправляю…";
    try {
      await wkAct(j.pid, f.kind, f.tid, extra);
      wkForm = null; wkRender(); toast(f.kind === "done" ? "Отправлено — руководитель увидит «Сделано»" : "Перенос отправлен с причиной");
    } catch (e) { go.disabled = false; r.className = "res err"; r.textContent = "Не ушло: " + e.message; }
  };
  let mph = "";
  $("#wk-mph").onchange = async (e) => {
    const f = e.target.files && e.target.files[0]; if (!f) return;
    try { mph = await shrinkImage(f, 1600); const im = $("#wk-mimg"); im.src = mph; im.hidden = false; } catch (x) { toast(x.message); }
  };
  $("#wk-msend").onclick = async () => {
    const t = $("#wk-mtext").value.trim(), r = $("#wk-mres"); if (!t && !mph) { $("#wk-mtext").focus(); return; }
    $("#wk-msend").disabled = true; r.className = "res"; r.textContent = "Отправляю…";
    try { await wkAct(j.pid, "msg", "", { text: t, photoUrl: mph }); toast(`Отправлено — ${j.boss || "руководитель"} услышит`); wkRender(); }
    catch (e) { $("#wk-msend").disabled = false; r.className = "res err"; r.textContent = "Не ушло: " + e.message; }
  };
  $("#wk-leave").onclick = () => wkLeave(j.pid);
}
function wkEmptyHtml() {
  return `<div class="wk-hero">${WK_IC}<b>Поручения с работы — отдельно от личного</b>`
    + `<p>Руководитель добавит вас в Dewiar на своём компьютере и покажет печать — наведите на неё сканер. Или откройте ссылку, которую он прислал.</p></div>`
    + (syncCred() ? "" : `<p class="hint">Сначала войдите в Dewiar: Настройки → Мозг → «Подключить бесплатно».</p>`)
    + `<button class="btn p w" id="wk-scan">${WK_CAM}<span>Сканировать печать</span></button>`
    + `<div class="card wk-paste"><label class="f"><span>Или вставьте ссылку</span><input id="wk-plink" placeholder="https://dewiar.pro/…?work=…" autocomplete="off"></label><button class="btn w" id="wk-pgo">Открыть приглашение</button><div class="res" id="wk-pres"></div></div>`
    + `<p class="hint wk-foot">Уйдёте с работы — уйдёт и всё рабочее. Личное — заметки, напоминания, близкие — остаётся с вами. Работ может быть несколько.</p>`
    + (wkAdd ? `<button class="btn w" id="wk-back">Назад к поручениям</button>` : "");
}
function wkJoinHtml(p) {
  const days = p.expires ? Math.max(1, Math.round((p.expires * 1000 - Date.now()) / 864e5)) : 0;
  return `<div class="wk-hero join">${WK_IC}<small>Приглашение на работу</small><b>${esc(p.team || "Команда")}</b>`
    + `<p>${p.boss ? `${esc(p.boss)} зовёт вас` : "Вас зовут"}${p.who ? ` как «${esc(p.who)}»` : ""} получать поручения здесь, в «Работе».</p></div>`
    + `<div class="card wk-terms"><p>✓ Руководитель видит только поручения: что вы взяли, сделали или перенесли, и что вы ему написали.</p>`
    + `<p>✓ Ваши заметки, напоминания, близкие и разговоры с Лирой ему не видны.</p><p>✓ Уйти можно в любой момент — рабочее исчезнет с телефона.</p></div>`
    + `<button class="btn p w" id="wk-jok">Присоединиться</button><button class="btn w" id="wk-jno" style="margin-top:8px">Не сейчас</button><div class="res" id="wk-jres"></div>`
    + (days ? `<p class="hint wk-foot">Приглашение действует ещё ${days} ${days === 1 ? "день" : days < 5 ? "дня" : "дней"}.</p>` : "");
}
function wkBindJoin() {
  const ok = $("#wk-jok"); if (ok) ok.onclick = () => { ok.disabled = true; wkAccept().finally(() => { if ($("#wk-jok")) $("#wk-jok").disabled = false; }); };
  const no = $("#wk-jno"); if (no) no.onclick = () => { wkJoinT = null; if (wkHas() || bsHas()) wkRender(); else closeSheets(); };
  const bk = $("#wk-back"); if (bk) bk.onclick = () => { wkAdd = false; wkRender(); };
  const sc = $("#wk-scan"); if (sc) sc.onclick = () => scanCode();
  const pg = $("#wk-pgo"); if (pg) pg.onclick = () => {
    const v = $("#wk-plink").value.trim(), r = $("#wk-pres");
    if (!wkToken(v)) { r.className = "res err"; r.textContent = "Это не ссылка-приглашение на работу: в ней должно быть «work=»."; return; }
    wkLink(v);
  };
}

/* ---------- голосом ---------- */
function wkPrompt() {
  if (!wkHas()) return "";
  return "РАБОТА (поручения руководителей — раздел «Работа», отдельно от личного): " + wkJobs().map(j => `«${j.team}»${j.boss ? " (руководитель " + j.boss + ")" : ""}`).join(", ")
    + ". «Что мне поручили?», «что по работе?» — work_tasks; «беру …», «сделал(а) …», «перенеси … на … — причина …», «напиши руководителю …» — work_act."
    + " Личные дела и напоминания — не сюда; поручения руководителя не путай с личными задачами.";
}
function wkTools() {
  if (!wkHas()) return [];
  return [{ name: "work_tasks", description: "Поручения с работы (раздел «Работа»): что поручил руководитель, сроки, что просрочено. Для «что мне поручили», «что по работе», «что на сегодня по работе».", parameters: O({}) },
    { name: "work_act", description: "Ответить на поручение с работы: act take — «беру», done — «сделал(а)» (text — пара слов, что сделано), move — перенести (due — новый срок ГГГГ-ММ-ДДTЧЧ:ММ, why — причина, без неё не переносится), msg — написать руководителю (text). task — слова из названия поручения (для msg не нужно); team — какая работа, если их несколько.",
      parameters: O({ act: { type: "string", enum: ["take", "done", "move", "msg"] }, task: STR, text: STR, due: STR, why: STR, team: STR }, ["act"]) }];
}
function wkFind(task, team) {
  const st = (w) => w.toLowerCase().replace(/ё/g, "е").slice(0, 5);
  const q = String(task || "").split(/[^а-яёa-z0-9]+/i).filter(w => w.length > 2).map(st);
  let best = null, score = 0, tie = false;
  for (const j of wkJobs()) {
    if (team && !String(j.team).toLowerCase().includes(String(team).toLowerCase().slice(0, 5))) continue;
    for (const t of (j.snap || {}).tasks || []) {
      if (t.state === "done" || t.state === "ok") continue;
      const ws = String(t.title + " " + (t.note || "")).split(/[^а-яёa-z0-9]+/i).filter(Boolean).map(st);
      const sc = q.filter(w => ws.includes(w)).length;
      if (sc > score) { best = [j, t]; score = sc; tie = false; } else if (sc && sc === score) tie = true;
    }
  }
  return score && !tie ? best : null;
}
async function wkTool(name, a) {
  if (name === "work_tasks") {
    const out = wkJobs().map(j => {
      const ts = ((j.snap || {}).tasks || []).filter(t => ["new", "work", "moved"].includes(t.state));
      return `«${j.team}»: ` + (ts.length ? ts.map(t => `«${t.title}» — ${WK_ONE[t.state] || t.state}${t.due_text ? ", срок " + t.due_text : ""}${t.late ? " (просрочено)" : ""}${t.remark ? ", вернули: " + t.remark : ""}`).join("; ") : "открытых поручений нет");
    });
    return out.join("\n") + "\nСкажи коротко, своими словами.";
  }
  const act = String(a.act || "");
  let j, t = null;
  if (act === "msg") {
    j = wkJobs().find(x => a.team && String(x.team).toLowerCase().includes(String(a.team).toLowerCase().slice(0, 5))) || (wkJobs().length === 1 ? wkJobs()[0] : null);
    if (!j) return "Ошибка: работ несколько — спроси, какому руководителю написать: " + wkJobs().map(x => x.team).join(", ") + ".";
    if (!String(a.text || "").trim()) return "Ошибка: нет текста — спроси, что написать.";
    await wkAct(j.pid, "msg", "", { text: String(a.text).trim() }); return `Отправлено: ${j.boss || "руководителю"} («${j.team}»). Скажи коротко.`;
  }
  const hit = wkFind(a.task, a.team);
  if (!hit) return "Ошибка: не поняла, какое поручение. Открытые: " + wkJobs().flatMap(x => ((x.snap || {}).tasks || []).filter(t => ["new", "work", "moved"].includes(t.state)).map(t => `«${t.title}»`)).join(", ") + ". Спроси.";
  [j, t] = hit;
  if (act === "move") {
    const d = new Date(String(a.due || ""));
    if (!a.due || isNaN(d)) return "Ошибка: нужен новый срок — спроси, на когда перенести.";
    if (!String(a.why || "").trim()) return "Ошибка: без причины не переносится — спроси, почему.";
    await wkAct(j.pid, "move", t.id, { due: wkLocal(a.due), why: String(a.why).trim() }); return `Перенос «${t.title}» на ${wkDue(a.due)} отправлен с причиной. Скажи коротко.`;
  }
  if (act === "take") { await wkAct(j.pid, "take", t.id); return `«${t.title}» — в работе, руководитель увидит. Скажи коротко.`; }
  if (act === "done") { await wkAct(j.pid, "done", t.id, { text: String(a.text || "").trim() }); return `«${t.title}» — отмечено «Сделано», ушло руководителю. Если нужно фото — его можно приложить в «Работе». Скажи коротко.`; }
  return "Ошибка: неизвестное действие.";
}

$("#b-work").onclick = () => openWork("");
$("#wk-join").onclick = () => { wkAdd = true; wkForm = null; wkRender(); };
