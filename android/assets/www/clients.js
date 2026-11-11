/* «Клиенты» и «Сделки» на телефоне и планшете (0.9.32; отчёты 657 и 658: «на планшете нет бизнес-инструментов», «думал,
   функционал будет как на компьютере»). Та же личная CRM, что на компьютере (core/clients.py, core/deals.py): карточка —
   кто, как связаться, история «о чём договорились», следующий шаг, сделки по этапам и «кто нам должен».

   Хранение — файл clients.json {clients: {cid: карточка}} (формат карточки — как на компьютере). Между устройствами —
   видом синхронизации client, только зашифрованными на устройстве или по домашнему Wi-Fi: это чужие телефоны и почты
   (cliChanOk). Правили на двух устройствах — cliMerge, тот же алгоритм, что clients.merge_cards на компьютере.
   Голосом — инструменты модели cliTools()/cliTool() (как work.js): записать о клиенте, что с ним, кто ждёт, сделки.
   Ядро app.js зовёт отсюда: openClients, cliSnap, cliApply, cliChanOk, cliTools, cliTool, cliHas. */
"use strict";
/* Тексты — из словарей (data/i18n/<язык>.json, ключи cli.*): приложение говорит на языке человека (0.89, английская версия). */
const cT = (k, p) => (typeof window.t === "function" ? window.t(k, p) : k);
const CLI_ST = { lead: 1, offer: 1, invoice: 1, paid: 1, lost: 1 };       // этапы сделки (названия — cliStN)
const cliStN = (k) => cT("cli.st." + k);
const CLI_OPEN = ["lead", "offer", "invoice"];
const CLI_KIND = { note: 1, call: 1, deal: 1, done: 1 };                   // вид записи истории (названия — cli.k.*)
const CLI_OWED_DAYS = 14, CLI_STUCK_DAYS = 7;
let CLI = null, cliView = { tab: "list", cid: "", q: "", edit: false, deal: false };

function cliLoad() {
  if (CLI) return CLI;
  try { CLI = JSON.parse(fileGet("clients.json") || "{}") || {}; } catch (e) { CLI = {}; }
  if (!CLI.clients || typeof CLI.clients !== "object") CLI.clients = {};
  return CLI;
}
function cliSave(sync) { fileSave("clients.json", JSON.stringify(cliLoad())); if (sync !== false && typeof syncSoon === "function") syncSoon(); }
const cliAll = () => Object.values(cliLoad().clients).sort((a, b) => (+b.updated || 0) - (+a.updated || 0));
const cliHas = () => Object.keys(cliLoad().clients).length > 0;
const cliNow = () => Date.now() / 1000;
const cliTitle = (c) => c.name + (c.company && c.company !== c.name ? ` («${c.company}»)` : "");
const cliNorm = (s) => String(s || "").replace(/\s+/g, " ").trim();
function cliCur() { const m = typeof money === "function" ? money() : []; const x = m.length ? m[m.length - 1] : null; return (x && x.currency) || "₽"; }
const cliLoc = () => (typeof dwLocale === "function" ? dwLocale() : "ru-RU");
const cliSum = (n, cur) => `${Math.round(+n || 0).toLocaleString(cliLoc())} ${cur || cliCur()}`;

/* ---------- слияние: как merge_cards в core/clients.py (результат одинаковый на обоих устройствах) ---------- */
function cliNum(x) { const n = parseFloat(x); return isFinite(n) ? n : 0; }
function cliMerge(a, b, cid) {
  a = a || {};
  const sig = (c) => { const nx = c.next && typeof c.next === "object" ? c.next : {};        // равное время правки — решает текст (как на компьютере)
    return ["name", "company", "phone", "email", "note"].map(k => String(c[k] || "")).concat([(c.tags || []).map(String).join(","), String(nx.what || ""), String(nx.at || "")]).join("|"); };
  const empty = !Object.keys(a).length;
  const ua = cliNum(a.updated), ub = cliNum(b.updated);
  const newer = empty || ub > ua || (ub === ua && sig(b) > sig(a)) ? b : a;
  const gone = [...new Set([].concat(a.gone || [], b.gone || []).map(String))].sort().slice(-200), gs = new Set(gone);
  const logs = {};
  [].concat(a.log || [], b.log || []).forEach(x => { if (!x || !x.id || gs.has(String(x.id))) return;
    const y = { id: String(x.id), ts: cliNum(x.ts), t: String(x.t || "").slice(0, 1000), kind: CLI_KIND[x.kind] ? x.kind : "note" }, o = logs[y.id];
    if (!o || y.ts > o.ts || (y.ts === o.ts && (y.t > o.t || (y.t === o.t && y.kind > o.kind)))) logs[y.id] = y; });   // одна запись в двух видах — одинаково везде
  const w = (y) => [Math.max(cliNum(y.u), cliNum(y.moved), cliNum(y.created)), cliNum(y.amount), ["stage", "title", "due", "note"].map(f => String(y[f] || "")).join("|")], deals = {};
  const gt = (x, y) => { for (let i = 0; i < 3; i++) { if (x[i] > y[i]) return true; if (x[i] < y[i]) return false; } return false; };
  [].concat(a.deals || [], b.deals || []).forEach(x => { if (!x || !x.id || gs.has(String(x.id))) return; const k = String(x.id);
    if (!deals[k] || gt(w(x), w(deals[k]))) deals[k] = Object.assign({}, x); });
  const out = { id: String(cid || newer.id || a.id || b.id || "") };
  [["name", 120], ["company", 120], ["phone", 60], ["email", 120], ["note", 2000]].forEach(([k, n]) => { out[k] = String(newer[k] || "").slice(0, n); });
  out.tags = (newer.tags || []).map(t => String(t).slice(0, 30)).filter(t => t.trim()).slice(0, 12);
  const cr = [cliNum(a.created), cliNum(b.created)].filter(Boolean);
  out.created = cr.length ? Math.min(...cr) : cliNum(newer.updated);
  out.updated = Math.max(ua, ub);
  out.log = Object.values(logs).sort((x, y) => x.ts - y.ts || (x.id < y.id ? -1 : x.id > y.id ? 1 : 0)).slice(-300);
  const nx = newer.next;
  out.next = nx && typeof nx === "object" && String(nx.what || "").trim() ? { what: String(nx.what || "").slice(0, 300), at: String(nx.at || "").slice(0, 20), rid: String(nx.rid || "").slice(0, 40) } : null;
  const ds = Object.values(deals).sort((x, y) => cliNum(x.created) - cliNum(y.created) || (String(x.id) < String(y.id) ? -1 : 1));
  if (ds.length) out.deals = ds;
  if (gone.length) out.gone = gone;
  return out;
}

/* ---------- синхронизация (ядро app.js: syncSnapshot, syncOne, syncApply) ---------- */
function cliChanOk(ch) { return !!ch && (!!ch.home || !!e2eKey(ch)); }      // чужие телефоны и почты — только зашифрованными
function cliSnap(out) {
  Object.values(cliLoad().clients).forEach(c => {
    const d = Object.assign({}, c, { log: (c.log || []).slice(-200) });
    out["client:" + c.id] = d;
    Object.defineProperty(d, "t", { value: Math.round(cliNum(c.updated) * 1000) || Date.now(), enumerable: false });
  });
}
function cliApply(id, d, del, ch) {
  if (!cliChanOk(ch) || !/^[0-9a-zA-Z_-]{1,40}$/.test(String(id))) return false;
  const st = cliLoad();
  if (del) { if (!st.clients[id]) return false; delete st.clients[id]; cliSave(false); cliRefresh(); return true; }
  if (!d || !cliNorm(d.name)) return false;
  const m = cliMerge(st.clients[id], d, id);
  if (st.clients[id] && JSON.stringify(m) === JSON.stringify(st.clients[id])) return true;
  st.clients[id] = m; cliSave(false); cliRefresh(); return true;
}

/* ---------- изменения (как в core/clients.py и core/deals.py) ---------- */
function cliGet(cid) { const c = cliLoad().clients[cid]; if (!c) throw new Error(cT("cli.err.no_client")); return c; }
function cliTouch(c) { c.updated = cliNow(); cliSave(); cliRefresh(); return c; }
function cliAdd(name, company, phone, email, note) {
  name = cliNorm(name).replace(/^[«"„']+|[»"“']+$/g, "");
  if (!name) throw new Error(cT("cli.err.name"));
  const id = Math.random().toString(16).slice(2, 10), ts = cliNow();
  const c = { id, name: name.slice(0, 120), company: cliNorm(company).slice(0, 120), phone: cliNorm(phone).slice(0, 60), email: cliNorm(email).slice(0, 120),
    note: String(note || "").slice(0, 2000), tags: [], created: ts, updated: ts, log: [], next: null };
  cliLoad().clients[id] = c; cliTouch(c); return c;
}
function cliNote(cid, text, kind) {
  text = cliNorm(text); if (!text) throw new Error(cT("cli.err.what_note"));
  const c = cliGet(cid); c.log = (c.log || []).concat([{ id: Math.random().toString(16).slice(2, 8), ts: cliNow(), t: text.slice(0, 1000), kind: CLI_KIND[kind] ? kind : "note" }]).slice(-300);
  return cliTouch(c);
}
function cliNext(cid, what, at) {
  const c = cliGet(cid); what = cliNorm(what);
  if (c.next && c.next.rid && D.alarmCancel) { try { D.alarmCancel(c.next.rid); } catch (e) { } }
  c.next = what ? { what: what.slice(0, 300), at: at ? cliIso(at) : "", rid: "" } : null;
  if (what && at && D.alarmSet) {                       // как на компьютере: напоминание «<что> — <клиент>» в «Делах»
    const rid = uid("r"); c.next.rid = rid;
    try { D.alarmSet(JSON.stringify({ id: rid, title: `${what[0].toUpperCase() + what.slice(1)} — ${cliTitle(c)}`, at: +at, kind: "reminder" })); } catch (e) { c.next.rid = ""; }
  }
  return cliTouch(c);
}
function cliNextDone(cid) {
  const c = cliGet(cid); if (!c.next) throw new Error(cT("cli.err.no_next"));
  cliNote(cid, cT("cli.done_prefix", { what: c.next.what }), "done"); return cliNext(cid, "", null);
}
function cliIso(d) { const p = (n) => String(n).padStart(2, "0"); d = new Date(+d); return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`; }
function cliDel(cid) { const c = cliGet(cid); if (c.next && c.next.rid && D.alarmCancel) { try { D.alarmCancel(c.next.rid); } catch (e) { } } delete cliLoad().clients[cid]; cliSave(); }
function cliDealAdd(cid, title, amount, stage, due) {
  const c = cliGet(cid); title = cliNorm(title); if (!title) throw new Error(cT("cli.err.deal_name"));
  stage = CLI_ST[stage] ? stage : "lead"; const ts = cliNow();
  const d = { id: Math.random().toString(16).slice(2, 8), title: title.slice(0, 160), amount: Math.round((+String(amount || 0).replace(/[^\d.,-]/g, "").replace(",", ".") || 0) * 100) / 100,
    cur: cliCur(), stage, due: cliDue(due), created: ts, moved: ts, paid: stage === "paid" ? ts : 0, note: "", u: ts };
  c.deals = (c.deals || []).concat([d]); cliNote(cid, cliDealLine(d, true), "deal"); return d;
}
function cliDealStage(cid, did, stage) {
  const c = cliGet(cid), d = (c.deals || []).find(x => x.id === did); if (!d) throw new Error(cT("cli.err.no_deal"));
  if (!CLI_ST[stage] || d.stage === stage) return d;
  d.stage = stage; d.moved = d.u = cliNow(); d.paid = stage === "paid" ? d.moved : 0;
  cliNote(cid, cliDealLine(d), "deal"); return d;
}
function cliDealDel(cid, did) {
  const c = cliGet(cid); c.deals = (c.deals || []).filter(x => x.id !== did); c.gone = (c.gone || []).concat([did]).slice(-200); cliTouch(c);
}
function cliDue(v) {
  v = String(v || "").trim(); if (!v) return "";
  if (/^\d{4}-\d{2}-\d{2}/.test(v)) return v.slice(0, 10);
  const w = typeof parseWhen === "function" ? parseWhen(v) : null; return w && w.at ? cliIso(w.at).slice(0, 10) : "";
}
const cliAmt = (d, sep) => (d.amount ? (sep || ", ") + cliSum(d.amount, d.cur) : "");
const cliDealLine = (d, isNew) => cT("cli.deal_line", { title: d.title, amount: cliAmt(d), stage: isNew ? cT("cli.deal_new", { stage: cliStN(d.stage).toLowerCase() }) : cliStN(d.stage).toLowerCase() });
function cliDealState(d) {
  const today = cliIso(Date.now()).slice(0, 10), days = Math.floor((cliNow() - (cliNum(d.moved) || cliNum(d.created) || cliNow())) / 86400);
  const overdue = d.stage === "invoice" && (d.due ? d.due < today : days > CLI_OWED_DAYS);
  const stuck = ["lead", "offer"].includes(d.stage) && days > CLI_STUCK_DAYS;
  return { overdue, stuck, days };
}
const cliDeals = () => cliAll().flatMap(c => (c.deals || []).map(d => Object.assign({}, d, { cid: c.id, client: cliTitle(c) }, cliDealState(d))));
function cliNextLate(c) { return !!(c.next && c.next.at && new Date(c.next.at) < new Date()); }

/* поиск клиента по словам: «Иванову», «Ромашка», «Иванов из Ромашки» (проще, чем find на компьютере) */
function cliFind(who, create) {
  const st = (w) => w.toLowerCase().replace(/ё/g, "\u0435").slice(0, Math.max(3, Math.min(5, w.length - 1)));
  const raw = cliNorm(who).replace(/[«»"„“]/g, ""), q = raw.split(/[^а-яёa-z0-9]+/i).filter(w => w.length > 1 && !/^(из|от|для|у|с|и|from|of|at)$/i.test(w)).map(st);
  if (!q.length) throw new Error(cT("cli.err.which"));
  const hits = cliAll().map(c => { const ws = (c.name + " " + (c.company || "")).split(/[^а-яёa-z0-9]+/i).filter(Boolean).map(st);
    return [q.filter(x => ws.some(y => y.startsWith(x) || x.startsWith(y))).length, c]; }).filter(h => h[0] > 0);
  if (hits.length) { const best = Math.max(...hits.map(h => h[0])), top = hits.filter(h => h[0] === best);
    if (top.length > 1) throw new Error(cT("cli.err.many", { list: top.slice(0, 4).map(h => cliTitle(h[1])).join(", ") }));
    return top[0][1]; }
  if (!create) throw new Error(cT("cli.err.missing", { who: raw }));
  const m = raw.match(/^(.+?)\s+(?:из|от|from)\s+(.+)$/i);
  return m ? cliAdd(m[1], m[2]) : cliAdd(raw);
}

/* ---------- лист «Клиенты» ---------- */
function openClients(cid) {
  if (typeof kidsOn === "function" && kidsOn()) return;
  cliView = { tab: cid ? "list" : cliView.tab || "list", cid: cid || "", q: "", edit: false, deal: false };
  if (!$("#sh-clients")) {
    const s = document.createElement("section"); s.className = "sheet tall"; s.id = "sh-clients"; s.setAttribute("aria-labelledby", "cli-h");
    s.innerHTML = `<div class="grab"></div><h2 id="cli-h">${esc(cT("cli.title"))}<button class="lnk" id="cli-new">${esc(cT("cli.new"))}</button></h2>
      <div class="tabs" id="cli-tabs"><button data-t="list" class="on">${esc(cT("cli.tab.list"))}</button><button data-t="deals">${esc(cT("cli.tab.deals"))}</button></div><div id="cli-body"></div>`;
    document.body.appendChild(s);
    s.querySelector("#cli-new").onclick = () => { cliView = Object.assign(cliView, { tab: "list", cid: "", edit: true }); cliRender(); };
    s.querySelectorAll("#cli-tabs button").forEach(b => b.onclick = () => { cliView = { tab: b.dataset.t, cid: "", q: "", edit: false, deal: false }; cliRender(); });
  }
  cliRender(); openSheet("#sh-clients");
}
function cliRefresh() { const s = $("#sh-clients"); if (s && s.classList.contains("on")) cliRender(); }
function cliLocked() {                                   // есть компьютер, а карточки к нему не ходят — сказать почему
  if (typeof syncCred !== "function" || !S.sync || !S.sync.on || !syncCred()) return "";
  const chans = typeof syncChans === "function" ? syncChans() : [];
  if (chans.some(cliChanOk)) return "";
  return `<div class="card cli-lock"><b>${esc(cT("cli.lock.h"))}</b><small class="hint">${esc(cT("cli.lock.p"))}</small>
    <button class="btn" id="cli-e2e">${esc(cT("cli.lock.btn"))}</button></div>`;
}
function cliRender() {
  const box = $("#cli-body"); if (!box) return;
  $$("#cli-tabs button").forEach(b => b.classList.toggle("on", b.dataset.t === cliView.tab));
  $("#cli-tabs").style.display = cliView.cid || cliView.edit ? "none" : "";          // .tabs — flex: атрибут hidden его не прячет
  $("#cli-new").style.display = cliView.cid || cliView.edit ? "none" : "";
  if (cliView.edit) return cliEditRender(box);
  if (cliView.cid && cliLoad().clients[cliView.cid]) return cliCardRender(box);
  cliView.cid = "";
  if (cliView.tab === "deals") return cliDealsRender(box);
  const q = cliView.q.toLowerCase(), all = cliAll().filter(c => !q || (c.name + " " + (c.company || "") + " " + (c.phone || "") + " " + (c.email || "")).toLowerCase().includes(q));
  const owed = {}; cliDeals().filter(d => d.stage === "invoice").forEach(d => { owed[d.cid] = (owed[d.cid] || 0) + (+d.amount || 0); });
  box.innerHTML = cliLocked() + (cliHas() ? `<input class="cli-q" id="cli-q" type="search" placeholder="${esc(cT("cli.search"))}" value="${esc(cliView.q)}" autocomplete="off">` : "")
    + (all.length ? `<div class="cli-list">${all.map(c => `<button class="cli-it" data-cid="${esc(c.id)}"><span class="cli-ava">${esc((c.name || "?").slice(0, 1).toUpperCase())}</span>
        <span class="cli-tx"><b>${esc(c.name)}</b><small>${esc([c.company && c.company !== c.name ? c.company : "", c.phone].filter(Boolean).join(" · ") || cT("cli.no_contacts"))}</small>
        ${c.next ? `<small class="cli-nx${cliNextLate(c) ? " late" : ""}">${esc(c.next.what)}${c.next.at ? " · " + esc(cliWhen(c.next.at)) : ""}</small>` : ""}</span>
        ${owed[c.id] ? `<span class="cli-owe">${esc(cliSum(owed[c.id]))}</span>` : ""}</button>`).join("")}</div>`
      : `<div class="cli-empty"><b>${esc(cT(cliView.q ? "cli.empty.none" : "cli.empty.h"))}</b><small>${esc(cT(cliView.q ? "cli.empty.none_p" : "cli.empty.p"))}</small></div>`);
  const qi = $("#cli-q"); if (qi) qi.oninput = () => { cliView.q = qi.value; const p = qi.selectionStart; cliRender(); const n = $("#cli-q"); if (n) { n.focus(); try { n.setSelectionRange(p, p); } catch (e) { } } };
  $$("#cli-body [data-cid]").forEach(b => b.onclick = () => { cliView.cid = b.dataset.cid; cliRender(); $("#sh-clients").scrollTop = 0; });
  const e2 = $("#cli-e2e"); if (e2) e2.onclick = () => { closeSheets(); setTimeout(() => openSettings("sync"), 60); };
}
function cliWhen(at) {
  const ds = /^\d{4}-\d{2}-\d{2}$/.test(String(at)), d = ds ? new Date(at + "T00:00") : new Date(at); if (isNaN(d)) return String(at);   // «оплатить до» — дата без времени
  const today = new Date(); today.setHours(0, 0, 0, 0); const day = Math.round((new Date(d).setHours(0, 0, 0, 0) - today) / 864e5);
  const tm = !ds && (d.getHours() || d.getMinutes()) ? ` ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}` : "";
  return (day === 0 ? cT("cli.today") : day === 1 ? cT("cli.tomorrow") : day === -1 ? cT("cli.yesterday") : d.toLocaleDateString(cliLoc(), { day: "numeric", month: "short" })) + tm;
}
function cliCardRender(box) {
  const c = cliLoad().clients[cliView.cid], cur = cliCur();
  const tel = c.phone ? c.phone.replace(/[^\d+]/g, "") : "";
  box.innerHTML = `<button class="lnk cli-back" id="cli-back">${esc(cT("cli.back_all"))}</button>
    <div class="card cli-head"><span class="cli-ava big">${esc((c.name || "?").slice(0, 1).toUpperCase())}</span><div class="cli-tx"><b>${esc(c.name)}</b>${c.company && c.company !== c.name ? `<small>${esc(c.company)}</small>` : ""}</div>
      <button class="btn" id="cli-edit">${esc(cT("cli.edit"))}</button></div>
    ${c.phone || c.email ? `<div class="cli-acts">${tel ? `<button class="btn" data-open="tel:${esc(tel)}">${esc(cT("cli.call", { v: c.phone }))}</button>` : ""}${c.email ? `<button class="btn" data-open="mailto:${esc(c.email)}">${esc(cT("cli.mail", { v: c.email }))}</button>` : ""}</div>` : ""}
    ${c.note ? `<p class="cli-note">${esc(c.note)}</p>` : ""}
    <h3>${esc(cT("cli.next_h"))}</h3>
    ${c.next ? `<div class="card cli-next${cliNextLate(c) ? " late" : ""}"><div class="cli-tx"><b>${esc(c.next.what)}</b><small>${c.next.at ? esc(cliWhen(c.next.at)) + (c.next.rid ? " · " + esc(cT("cli.next_remind")) : "") : esc(cT("cli.next_none"))}</small></div><button class="btn p" id="cli-ndone">${esc(cT("cli.done"))}</button></div>` : ""}
    <div class="row2 cli-nform"><input id="cli-nw" placeholder="${esc(cT(c.next ? "cli.next_ph_other" : "cli.next_ph"))}" maxlength="300"><input id="cli-nt" placeholder="${esc(cT("cli.when_ph"))}" maxlength="60"><button class="btn" id="cli-nset">${esc(cT("cli.set"))}</button></div>
    <h3>${esc(cT("cli.deals_h"))}</h3>
    ${(c.deals || []).filter(d => d.stage !== "lost" || cliNow() - cliNum(d.moved) < 30 * 86400).map(d => { const s = cliDealState(d);
      return `<div class="card cli-deal${s.overdue ? " late" : ""}"><div class="cli-tx"><b>${esc(d.title)}</b><small>${d.amount ? esc(cliSum(d.amount, d.cur || cur)) : esc(cT("cli.no_amount"))}${d.due ? " · " + esc(cT("cli.due", { date: cliWhen(d.due) })) : ""}${s.overdue ? " · " + esc(cT("cli.overdue")) : s.stuck ? " · " + esc(cT("cli.stuck")) : ""}</small></div>
        <select data-deal="${esc(d.id)}" aria-label="${esc(cT("cli.stage_aria", { title: d.title }))}">${Object.keys(CLI_ST).map(k => `<option value="${k}"${k === d.stage ? " selected" : ""}>${esc(cliStN(k))}</option>`).join("")}</select></div>`; }).join("") || `<p class="hint">${esc(cT("cli.deals_none"))}</p>`}
    ${cliView.deal ? `<div class="card cli-dform"><input id="cli-dt" placeholder="${esc(cT("cli.deal_title_ph"))}" maxlength="160"><div class="row2"><input id="cli-da" inputmode="decimal" placeholder="${esc(cT("cli.amount_ph", { cur }))}"><input id="cli-dd" placeholder="${esc(cT("cli.due_ph"))}"></div>
      <div class="row2"><select id="cli-ds">${Object.keys(CLI_ST).filter(k => k !== "lost").map(k => `<option value="${k}">${esc(cliStN(k))}</option>`).join("")}</select><button class="btn p" id="cli-dadd">${esc(cT("cli.deal_add"))}</button></div></div>`
      : `<button class="btn" id="cli-dnew">${esc(cT("cli.deal_new_btn"))}</button>`}
    <h3>${esc(cT("cli.log_h"))}</h3>
    <div class="row2 cli-lform"><input id="cli-lt" placeholder="${esc(cT("cli.log_ph"))}" maxlength="1000"><button class="btn" id="cli-lcall" title="${esc(cT("cli.log_call_title"))}">${esc(cT("cli.log_call"))}</button><button class="btn p" id="cli-ladd">${esc(cT("cli.log_add"))}</button></div>
    <div class="cli-log">${(c.log || []).slice().reverse().slice(0, 60).map(x => `<div class="cli-li k-${esc(x.kind)}"><small>${esc(new Date(x.ts * 1000).toLocaleDateString(cliLoc(), { day: "numeric", month: "short", year: "numeric" }))} · ${esc(cT("cli.k." + (CLI_KIND[x.kind] ? x.kind : "note")))}</small><span>${esc(x.t)}</span></div>`).join("") || `<p class="hint">${esc(cT("cli.log_empty"))}</p>`}</div>
    <div class="res" id="cli-res"></div>`;
  const res = (t, bad) => { const r = $("#cli-res"); if (r) { r.textContent = t; r.className = "res " + (bad ? "bad" : "ok"); } };
  const run = (f) => { try { f(); } catch (e) { res(String(e.message || e), true); } };
  $("#cli-back").onclick = () => { cliView.cid = ""; cliView.deal = false; cliRender(); };
  $("#cli-edit").onclick = () => { cliView.edit = true; cliRender(); };
  $$("#cli-body [data-open]").forEach(b => b.onclick = () => D.openUrl(b.dataset.open));
  const nd = $("#cli-ndone"); if (nd) nd.onclick = () => run(() => cliNextDone(c.id));
  $("#cli-nset").onclick = () => run(() => { const w = $("#cli-nw").value, t = $("#cli-nt").value.trim(); let at = null;
    if (t) { const p = parseWhen(t); if (!p || !p.at) throw new Error(cT("cli.err.when")); at = p.at; }
    if (!cliNorm(w)) throw new Error(cT("cli.err.what_do")); cliNext(c.id, w, at); });
  const dn = $("#cli-dnew"); if (dn) dn.onclick = () => { cliView.deal = true; cliRender(); const i = $("#cli-dt"); if (i) i.focus(); };
  const da = $("#cli-dadd"); if (da) da.onclick = () => run(() => { cliView.deal = false; cliDealAdd(c.id, $("#cli-dt").value, $("#cli-da").value, $("#cli-ds").value, $("#cli-dd").value); });
  $$("#cli-body [data-deal]").forEach(s => s.onchange = () => run(() => cliDealStage(c.id, s.dataset.deal, s.value)));
  $("#cli-ladd").onclick = () => run(() => cliNote(c.id, $("#cli-lt").value, "note"));
  $("#cli-lcall").onclick = () => run(() => cliNote(c.id, $("#cli-lt").value || cT("cli.log_call_def"), "call"));
}
function cliEditRender(box) {
  const c = cliView.cid ? cliLoad().clients[cliView.cid] : null, v = (k) => esc((c && c[k]) || "");
  box.innerHTML = `<button class="lnk cli-back" id="cli-back">${esc(cT(c ? "cli.back" : "cli.back_all"))}</button>
    <label class="f"><span>${esc(cT("cli.f.name"))}</span><input id="ce-name" maxlength="120" value="${v("name")}" autocapitalize="words"></label>
    <label class="f"><span>${esc(cT("cli.f.company"))}</span><input id="ce-company" maxlength="120" value="${v("company")}"></label>
    <div class="row2"><label class="f"><span>${esc(cT("cli.f.phone"))}</span><input id="ce-phone" type="tel" maxlength="60" value="${v("phone")}"></label>
      <label class="f"><span>${esc(cT("cli.f.email"))}</span><input id="ce-email" type="email" maxlength="120" value="${v("email")}" autocapitalize="off"></label></div>
    <label class="f"><span>${esc(cT("cli.f.note"))}</span><textarea id="ce-note" rows="3" maxlength="2000">${v("note")}</textarea></label>
    <div class="row2"><button class="btn p" id="ce-save">${esc(cT(c ? "cli.save" : "cli.add"))}</button>${c ? `<button class="btn bad" id="ce-del">${esc(cT("cli.del"))}</button>` : ""}</div><div class="res" id="cli-res"></div>`;
  $("#cli-back").onclick = () => { cliView.edit = false; cliRender(); };
  $("#ce-save").onclick = () => { try {
    const f = { name: $("#ce-name").value, company: $("#ce-company").value, phone: $("#ce-phone").value, email: $("#ce-email").value, note: $("#ce-note").value };
    if (!cliNorm(f.name)) throw new Error(cT("cli.err.need_name"));
    if (c) { ["name", "company", "phone", "email"].forEach(k => { c[k] = cliNorm(f[k]).slice(0, k === "phone" ? 60 : 120); }); c.note = String(f.note || "").slice(0, 2000); cliView.edit = false; cliTouch(c); }
    else { const n = cliAdd(f.name, f.company, f.phone, f.email, f.note); cliView.edit = false; cliView.cid = n.id; cliRender(); }
  } catch (e) { const r = $("#cli-res"); r.textContent = e.message; r.className = "res bad"; } };
  const del = $("#ce-del"); if (del) del.onclick = () => { if (del.dataset.sure) { cliDel(c.id); cliView = { tab: "list", cid: "", q: "", edit: false, deal: false }; cliRender(); }
    else { del.dataset.sure = "1"; del.textContent = cT("cli.del_sure"); } };
}
function cliDealsRender(box) {
  const ds = cliDeals(), cut = cliNow() - 30 * 86400;
  const col = (k) => ds.filter(d => d.stage === k && (CLI_OPEN.includes(k) || cliNum(d.moved) > cut));
  const sum = (xs) => xs.reduce((a, d) => a + (+d.amount || 0), 0);
  const owe = ds.filter(d => d.stage === "invoice"), late = owe.filter(d => d.overdue), stuck = ds.filter(d => d.stuck);
  box.innerHTML = cliLocked() + (ds.length ? `<div class="cli-sum"><div><b>${esc(cliSum(sum(owe)))}</b><small>${esc(cT("cli.owed", { n: owe.length }))}</small></div>
      <div class="${late.length ? "late" : ""}"><b>${late.length}</b><small>${esc(cT("cli.overdue_n"))}</small></div><div><b>${stuck.length}</b><small>${esc(cT("cli.stuck_n"))}</small></div></div>
    <div class="cli-board">${Object.keys(CLI_ST).map(k => { const xs = col(k); return `<section class="cli-col s-${k}"><h4>${esc(cliStN(k))}<span>${xs.length ? esc(cliSum(sum(xs))) : ""}</span></h4>
      ${xs.map(d => `<button class="cli-dc${d.overdue ? " late" : d.stuck ? " stuck" : ""}" data-cid="${esc(d.cid)}"><b>${esc(d.title)}</b><small>${esc(d.client)}${d.amount ? " · " + esc(cliSum(d.amount, d.cur)) : ""}${d.overdue ? " · " + esc(cT("cli.overdue")) : d.stuck ? " · " + esc(cT("cli.stuck")) : ""}</small></button>`).join("") || `<small class="hint">—</small>`}</section>`; }).join("")}</div>`
    : `<div class="cli-empty"><b>${esc(cT("cli.deals_empty_h"))}</b><small>${esc(cT("cli.deals_empty_p"))}</small></div>`);
  $$("#cli-body [data-cid]").forEach(b => b.onclick = () => { cliView.cid = b.dataset.cid; cliRender(); $("#sh-clients").scrollTop = 0; });
  const e2 = $("#cli-e2e"); if (e2) e2.onclick = () => { closeSheets(); setTimeout(() => openSettings("sync"), 60); };
}

/* ---------- голосом: инструменты модели (как на компьютере: client_note, client_info, client_next, deal_add, deal_stage, deals_list).
   Описания — по-английски: модели понимают их одинаково на любом языке разговора; ответы инструментов — из словарей. ---------- */
function cliTools() {
  if (typeof kidsOn === "function" && kidsOn()) return [];
  const S1 = { type: "string" }, O = (p, r) => ({ type: "object", properties: p, required: r || [] });
  return [
    { name: "client_note", description: "Clients (personal CRM): note something about a client — an agreement, a call, a remark. A missing client card is created automatically. who — the client in the user's words (\"John from Acme\"), text — what to note, kind — note or call; phone, email — if mentioned.",
      parameters: O({ who: S1, text: S1, kind: { type: "string", enum: ["note", "call"] }, phone: S1, email: S1 }, ["who", "text"]) },
    { name: "client_info", description: "What we know about a client: contacts, next step, deals, latest notes. For \"what's up with John?\".", parameters: O({ who: S1 }, ["who"]) },
    { name: "client_next", description: "A client's next step: what to do and when (when — in the user's words, e.g. \"Thursday at 11\"); with a time — a reminder is set. done: true — the step is done.",
      parameters: O({ who: S1, what: S1, when: S1, done: { type: "boolean" } }, ["who"]) },
    { name: "client_list", description: "Which clients are waiting: next steps, overdue ones, whom to call. q — optional name filter.", parameters: O({ q: S1 }) },
    { name: "deal_add", description: "A new deal for a client: title — what we sell, amount — sum, stage — lead, offer, invoice (invoice sent), paid; due — pay-by date in the user's words.",
      parameters: O({ who: S1, title: S1, amount: { type: "number" }, stage: { type: "string", enum: ["lead", "offer", "invoice", "paid"] }, due: S1 }, ["who", "title"]) },
    { name: "deal_stage", description: "A client's deal moved to another stage: \"Acme paid the invoice\" — paid, \"John declined\" — lost. deal — which deal in words (may be empty if the client has one).",
      parameters: O({ who: S1, deal: S1, stage: { type: "string", enum: ["lead", "offer", "invoice", "paid", "lost"] } }, ["who", "stage"]) },
    { name: "deals_list", description: "Deals: what owed — who owes us (invoice sent), stuck — stalled deals, all — all open deals.", parameters: O({ what: { type: "string", enum: ["owed", "stuck", "all"] } }) }];
}
async function cliTool(name, a) {
  const brief = "\n" + cT("cli.r.brief");
  try {
    if (name === "client_list") {
      const xs = cliAll().filter(c => !a.q || (c.name + " " + (c.company || "")).toLowerCase().includes(String(a.q).toLowerCase()));
      const wait = xs.filter(c => c.next).sort((x, y) => String(x.next.at || "9").localeCompare(String(y.next.at || "9")));
      return (wait.length ? cT("cli.r.next", { list: wait.slice(0, 12).map(c => `${cliTitle(c)} — ${c.next.what}${c.next.at ? " (" + cliWhen(c.next.at) + (cliNextLate(c) ? cT("cli.r.late") : "") + ")" : ""}`).join("; ") })
        : cT("cli.r.no_next", { n: xs.length })) + brief;
    }
    if (name === "deals_list") {
      const ds = cliDeals(), w = a.what || "owed";
      const xs = w === "owed" ? ds.filter(d => d.stage === "invoice") : w === "stuck" ? ds.filter(d => d.stuck) : ds.filter(d => CLI_OPEN.includes(d.stage));
      if (!xs.length) return cT(w === "owed" ? "cli.r.no_owed" : w === "stuck" ? "cli.r.no_stuck" : "cli.r.no_open");
      return xs.map(d => cT("cli.r.deal_item", { client: d.client, title: d.title, amount: cliAmt(d), stage: cliStN(d.stage).toLowerCase(), due: d.due ? cT("cli.r.due", { date: cliWhen(d.due) }) : "",
        flag: d.overdue ? cT("cli.r.overdue") : d.stuck ? cT("cli.r.stuck") : "" })).join("; ")
        + (w === "owed" ? ". " + cT("cli.r.owed_total", { sum: cliSum(xs.reduce((s, d) => s + (+d.amount || 0), 0)) }) : "") + brief;
    }
    const c = cliFind(a.who, name === "client_note" || name === "deal_add");
    if (name === "client_note") {
      if (a.phone && !c.phone) c.phone = cliNorm(a.phone).slice(0, 60);
      if (a.email && !c.email) c.email = cliNorm(a.email).slice(0, 120);
      cliNote(c.id, a.text, a.kind === "call" ? "call" : "note");
      return cT("cli.r.noted", { c: cliTitle(c) });
    }
    if (name === "client_info") {
      const ds = (c.deals || []).filter(d => CLI_OPEN.includes(d.stage));
      return [cliTitle(c) + (c.phone ? cT("cli.r.phone", { v: c.phone }) : "") + (c.email ? cT("cli.r.email", { v: c.email }) : "") + ".", c.note ? cT("cli.r.note", { v: c.note }) : "",
        c.next ? cT("cli.r.next1", { what: c.next.what, when: c.next.at ? cT("cli.r.at", { when: cliWhen(c.next.at) }) : "" }) : cT("cli.r.next0"),
        ds.length ? cT("cli.r.deals", { list: ds.map(d => `«${d.title}»${cliAmt(d, " ")} — ${cliStN(d.stage).toLowerCase()}`).join("; ") }) : "",
        (c.log || []).length ? cT("cli.r.last", { list: (c.log || []).slice(-3).map(x => x.t).join("; ") }) : ""].filter(Boolean).join("\n") + brief;
    }
    if (name === "client_next") {
      if (a.done) { cliNextDone(c.id); return cT("cli.r.next_done", { c: cliTitle(c) }); }
      let at = null; if (a.when) { const p = parseWhen(String(a.when)); if (!p || !p.at) return cT("cli.r.err_when"); at = p.at; }
      if (!cliNorm(a.what)) return cT("cli.r.err_what");
      cliNext(c.id, a.what, at);
      return cT("cli.r.next_set", { c: cliTitle(c), what: cliNorm(a.what), when: at ? cT("cli.r.at", { when: cliWhen(cliIso(at)) }) + cT("cli.r.remind") : "" });
    }
    if (name === "deal_add") {
      const d = cliDealAdd(c.id, a.title, a.amount, a.stage || "lead", a.due);
      return cT("cli.r.deal_added", { title: d.title, c: cliTitle(c), stage: cliStN(d.stage).toLowerCase(), amount: cliAmt(d), due: d.due ? cT("cli.r.due", { date: cliWhen(d.due) }) : "" });
    }
    if (name === "deal_stage") {
      const ds = c.deals || [], q = cliNorm(a.deal).toLowerCase();
      let d = q ? ds.find(x => x.title.toLowerCase().includes(q.slice(0, 5))) : null;
      if (!d) { const open = ds.filter(x => CLI_OPEN.includes(x.stage)); if (open.length === 1 || (!q && open.length)) d = open.sort((x, y) => cliNum(y.moved) - cliNum(x.moved))[0]; }
      if (!d) return cT("cli.r.no_deal", { c: cliTitle(c), have: ds.length ? cT("cli.r.have", { list: ds.map(x => "«" + x.title + "»").join(", ") }) : "" });
      cliDealStage(c.id, d.id, a.stage);
      return cT("cli.r.stage_set", { title: d.title, c: cliTitle(c), stage: cliStN(a.stage).toLowerCase() });
    }
  } catch (e) { return cT("cli.r.err", { e: e.message || e }); }
  return cT("cli.r.no_action");
}
