/* «Сотрудники» — поручения с телефона руководителя (0.56; владелец 28.10: «…управление поручениями с телефона руководителя»).

   Доска живёт на компьютере («Поручения», core/team.py, боты и приложение сотрудников). Он присылает своим устройствам
   снимок — конверт own {team: {company, boss, dev, at, members[], tasks[], repeats[], inbox[]}} (шифр на устройствах):
   после каждого изменения и по просьбе {want: ["team"]}. Отсюда — команды {team_cmd: {id, cmd, a, ts}}:
   assign {who, title, due, note} · accept / remind / cancel {id} · back {id, remark} · message {who, text}.
   Компьютер выполняет их у себя (сотрудник получает так же, как из студии) и отвечает {team_res: {id, ok, err}, team}.
   Пока ответа нет — на карточке «ждёт компьютер». Своя вкладка «Сотрудники» в листе «Работа» (work.js); голосом —
   team_status, team_assign, team_message. Детский режим прячет всё. Ядро зовёт: bsTake, bsHas, bsUnread, bsActive,
   bsPrompt, bsTools, bsTool, bsHtml, bsBind, bsAsk; work.js — вкладку BS_TAB. */
"use strict";
let BS = null, bsView = "tasks", bsOpenId = "", bsForm = null, bsOkShow = false;
const BS_TAB = "@boss";
const BS_ORDER = [["done", "Ждут вашей проверки"], ["late", "Просрочено"], ["work", "В работе"], ["new", "Новые"], ["moved", "Перенесено"]];
const BS_ONE = { new: "новое, ждёт «Беру»", work: "в работе", moved: "перенесено", done: "сделано, ждёт проверки", ok: "принято" };
const BS_DONE = { assign: "Поручение ушло", accept: "Принято — сотруднику ушло «спасибо»", back: "Вернули с замечанием", cancel: "Поручение снято",
  remind: "Напомнили", message: "Сообщение ушло" };

function bsLoad() {
  if (BS) return BS;
  try { BS = JSON.parse(fileGet("boss.json") || "{}") || {}; } catch (e) { BS = {}; }
  BS = Object.assign({ snap: null, pend: [], unread: 0, asked: 0 }, BS);
  return BS;
}
const bsSave = () => fileSave("boss.json", JSON.stringify(BS));
const bsHas = () => !kidsOn() && !!bsLoad().snap;
const bsUnread = () => bsHas() && bsLoad().unread > 0;
const bsSheetOn = () => $("#sh-work").classList.contains("on") && wkCur === BS_TAB && !document.hidden;
/* ждём ответа компьютера — почту проверяем часто (clActive) */
const bsActive = () => { const st = bsLoad(); return !kidsOn() && (st.pend.length > 0 || Date.now() - (st.asked || 0) < 120000 || ($("#sh-work").classList.contains("on") && wkCur === BS_TAB)); };
const bsSec = (ts) => (+ts || 0) * 1000;          // компьютер считает в секундах

/* ---------- с компьютера ---------- */
function bsTake(body) {
  if (!body || kidsOn()) return;
  const st = bsLoad(); let changed = false;
  const sn = body.team;
  if (sn && typeof sn === "object" && Array.isArray(sn.tasks) && +sn.at > +((st.snap || {}).at || 0)) {
    const old = st.snap;
    st.snap = { company: String(sn.company || ""), boss: String(sn.boss || ""), dev: String(sn.dev || ""), at: +sn.at,
      members: (sn.members || []).filter(m => m && m.id).slice(0, 100), tasks: sn.tasks.filter(t => t && t.id).slice(0, 150),
      repeats: (sn.repeats || []).slice(0, 30), inbox: (sn.inbox || []).filter(x => x && x.who).slice(-40) };
    if (old) bsNews(old, st.snap);
    changed = true;
  }
  const r = body.team_res;
  if (r && typeof r === "object" && r.id) {
    const p = st.pend.find(x => x.id === r.id);
    st.pend = st.pend.filter(x => x.id !== r.id);
    if (p) bsResult(p, r);
    changed = true;
  }
  if (!changed) return;
  bsSave(); wkBadge();
  if ($("#sh-work").classList.contains("on") && wkCur === BS_TAB) wkRender();
}
/* что нового с прошлого снимка: сотрудник написал, отметил «Сделано», перенёс — значок, а в фоне — уведомление */
function bsNews(old, now) {
  const top = Math.max(0, ...(old.inbox || []).map(x => +x.ts || 0));
  const was = Object.fromEntries((old.tasks || []).map(t => [t.id, t.state]));
  const lines = [];
  (now.inbox || []).filter(x => !x.out && +x.ts > top).forEach(x => lines.push(`${x.name}: ${x.t || "фото"}`));
  (now.tasks || []).forEach(t => {
    if (was[t.id] === t.state || !was[t.id]) return;
    if (t.state === "done") lines.push(`${t.name} — сделано: «${t.title}»`);
    else if (t.state === "moved") lines.push(`${t.name} переносит «${t.title}»${t.reason ? ": " + t.reason : ""}`);
    else if (t.state === "work" && was[t.id] === "new") lines.push(`${t.name} взял(а) «${t.title}»`);
  });
  if (!lines.length) return;
  if (!bsSheetOn()) BS.unread = (BS.unread || 0) + lines.length;
  if (document.hidden) D.notify("💼 " + (now.company || "Сотрудники"), lines.slice(-3).join("\n"));
}
function bsResult(p, r) {
  if (r.ok) { if (!document.hidden) toast(p.cmd === "assign" && r.name ? `Поручение ушло: ${r.name}` : BS_DONE[p.cmd] || "Готово"); return; }
  const what = { assign: `«${clip((p.a || {}).title || "", 40)}»`, message: "сообщение" }[p.cmd] || "команда";
  const t = `Компьютер не выполнил ${what}: ${r.err || "ошибка"}.`;
  if (document.hidden) D.notify("💼 Сотрудники", t);
  else { showBot(t, "err"); if (!busy && state === "idle") say(t); }
}

/* ---------- отсюда ---------- */
/* при запуске: доска старше 10 минут — попросить свежую; доски нет, а компьютер есть — спросить раз в сутки (вдруг вы руководитель) */
function bsBoot() {
  if (kidsOn() || !syncCred()) return;
  const st = bsLoad(), age = Date.now() - ((st.snap || {}).at || 0);
  const since = Date.now() - (st.asked || 0);
  if (st.snap ? age > 600000 && since > 600000 : since > 86400000 && devComputers().length > 0) bsAsk();
  wkBadge();
}
async function bsAsk(force) {
  const st = bsLoad();
  if (!syncCred() || (!force && Date.now() - (st.asked || 0) < 60000)) return;
  st.asked = Date.now(); bsSave();
  try { if (await devOwnSend({ want: ["team"] })) { clSchedule(); [5000, 12000].forEach(ms => setTimeout(clPoll, ms)); } } catch (e) { plog("info", "сотрудники: " + e.message); }
}
async function bsCmd(cmd, a) {
  const st = bsLoad();
  if (!st.snap) throw new Error("«Поручения» на компьютере ещё не прислали доску");
  const id = "c" + Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
  const ok = await devOwnSend({ team_cmd: { id, cmd, a, ts: Date.now() } });
  if (!ok) throw new Error("компьютер ещё не на связи — войдите в Dewiar на нём тем же аккаунтом");
  st.pend.push({ id, cmd, a, ts: Date.now() }); st.pend = st.pend.slice(-30);
  bsSave(); clSchedule(); [4000, 9000, 20000].forEach(ms => setTimeout(clPoll, ms));
  plog("info", `💼 сотрудники: ${cmd} → компьютер «${st.snap.dev || "?"}»`);
  return id;
}
const bsPendOf = (fn) => bsLoad().pend.filter(fn);
const bsLate = (p) => Date.now() - p.ts > 180000;
const bsPendTxt = (p) => bsLate(p) ? `ждёт компьютер «${esc(bsLoad().snap.dev || "")}» — выполнит, когда он будет на связи` : "отправлено на компьютер…";

/* «Анне», «Ивану Петрову» -> член команды (или null; двое — null, пусть уточнит компьютер) */
function bsWho(who) {
  const ms = ((bsLoad().snap || {}).members || []), w = String(who || "").toLowerCase().replace(/ё/g, "е");
  const byId = ms.find(m => m.id === who); if (byId) return { m: byId };
  const q = w.split(/[^а-яa-z]+/).filter(x => x.length > 1);
  if (!q.length) return { err: "кому?" };
  /* «Петру» — точно Пётр (слово начинается с имени), а «Петров» — лишь похоже (общее начало): точное важнее */
  const score = (m) => q.reduce((sum, wd) => sum + Math.max(0, ...m.name.toLowerCase().replace(/ё/g, "е").split(/[^а-яa-z]+/).filter(Boolean)
    .map(x => x === wd || (wd.startsWith(x) && wd.length - x.length <= 1) ? 2 : x.startsWith(wd.slice(0, Math.max(3, wd.length - 2))) ? 1 : 0)), 0);
  const sc = ms.map(m => [score(m), m]).filter(([n]) => n > 0), top = Math.max(0, ...sc.map(([n]) => n));
  const hits = sc.filter(([n]) => n === top).map(([, m]) => m);
  if (!hits.length) return { err: `в команде нет «${who}». В команде: ${ms.map(m => m.name).join(", ") || "пока никого"}` };
  return hits.length === 1 ? { m: hits[0] } : { many: hits };
}

/* ---------- вкладка «Сотрудники» ---------- */
function bsWhen(ms) { return ms ? wkWhen(ms) : ""; }
function bsHtml() {
  const st = bsLoad(), s = st.snap; if (!s) return "";
  if (st.unread && !document.hidden) { st.unread = 0; bsSave(); setTimeout(wkBadge, 0); }   // рисуем — значит, смотрят
  const open = s.tasks.filter(t => ["new", "work", "moved"].includes(t.state)).length, check = s.tasks.filter(t => t.state === "done").length;
  const on = s.members.filter(m => m.joined).length;
  const age = Date.now() - s.at, fresh = age < 120000 ? "только что" : bsWhen(s.at);
  const head = `<div class="wk-head bs-head"><b>${esc(s.company || "Сотрудники")}</b><small>${s.members.length ? `Сотрудников: ${s.members.length}, на связи ${on}` : "Сотрудников пока нет"}</small>`
    + `<small class="bs-src">Доска с компьютера «${esc(s.dev || "")}» · ${esc(fresh)} <button class="lnk" id="bs-ref">Обновить</button></small></div>`;
  const msgs = s.inbox.filter(x => !x.out).length;
  const seg = `<div class="seg bs-seg" role="tablist"><button role="tab" data-v="tasks" class="${bsView === "tasks" ? "on" : ""}" aria-selected="${bsView === "tasks"}">Поручения${open + check ? ` <em>${open + check}</em>` : ""}</button>`
    + `<button role="tab" data-v="msgs" class="${bsView === "msgs" ? "on" : ""}" aria-selected="${bsView === "msgs"}">Переписка${msgs ? ` <em>${msgs}</em>` : ""}</button></div>`;
  return head + seg + (bsView === "msgs" ? bsMsgsHtml(s) : bsTasksHtml(s))
    + `<p class="hint wk-foot">Поручения рассылает компьютер — отсюда вы ими управляете. Всё шифруется на ваших устройствах.</p>`;
}
function bsTasksHtml(s) {
  const pa = bsPendOf(p => p.cmd === "assign");
  let h = bsForm && bsForm.kind === "assign" ? bsAssignHtml(s) : `<button class="btn p w bs-new" id="bs-new"${s.members.length ? "" : " disabled"}>Поручить</button>`;
  if (!s.members.length) h += `<p class="hint">Добавьте сотрудников на компьютере: студия → «Поручения» → «Сотрудники».</p>`;
  if (pa.length) h += `<div class="wk-sec"><span>Отправляется</span><em>${pa.length}</em></div>` + pa.map(p => `<div class="card wk-task s-new bs-pend"><b>${esc(p.a.title)}</b>`
    + `<span class="wk-due">${esc(p.a.name || p.a.who)}${p.a.due ? " · срок " + esc(p.a.due) : ""}</span><p class="bs-wait">${bsPendTxt(p)}</p></div>`).join("");
  const used = new Set();
  for (const [k, title] of BS_ORDER) {
    const l = s.tasks.filter(t => !used.has(t.id) && (k === "late" ? t.late && ["new", "work", "moved"].includes(t.state) : t.state === k));
    l.forEach(t => used.add(t.id));
    if (l.length) h += `<div class="wk-sec"><span>${title}</span><em>${l.length}</em></div>` + l.map(bsCard).join("");
  }
  const ok = s.tasks.filter(t => t.state === "ok");
  if (ok.length) h += `<button class="wk-sec bs-oks" id="bs-oks" aria-expanded="${bsOkShow}"><span>Принято за две недели</span><em>${ok.length}</em><i>${bsOkShow ? "Свернуть" : "Показать"}</i></button>` + (bsOkShow ? ok.map(bsCard).join("") : "");
  if (!s.tasks.length && !pa.length && s.members.length) h += `<div class="card wk-none"><b>Поручений пока нет</b><p class="hint">Нажмите «Поручить» или скажите голосом — например, «поручи Анне обновить прайс до пятницы».</p></div>`;
  if (s.repeats.length) h += `<div class="wk-sec"><span>Повторяется</span><em>${s.repeats.length}</em></div><div class="card wk-reps">${s.repeats.map(r => `<p><b>${esc(r.title)}</b><span>${esc(r.name)} · ${esc(r.rule)}</span></p>`).join("")}</div>`;
  return h;
}
function bsCard(t) {
  const open = bsOpenId === t.id, f = bsForm && bsForm.id === t.id ? bsForm : null;
  const pend = bsPendOf(p => (p.a || {}).id === t.id).slice(-1)[0];
  const due = t.due_text ? ` · ${t.late ? "просрочено, " : "срок "}${esc(t.due_text)}` : "";
  let acts = "";
  if (open && !pend && !f) {
    if (t.state === "done") acts = `<button class="btn p" data-a="accept">Принять</button><button class="btn" data-a="back">Вернуть</button>`;
    else if (t.state !== "ok") acts = `<button class="btn" data-a="remind">Напомнить</button><button class="btn" data-a="write">Написать</button><button class="btn bs-del" data-a="cancel" aria-label="Снять поручение">Снять</button>`;
    else acts = `<button class="btn" data-a="write">Написать</button>`;
    acts = `<div class="wk-acts">${acts}</div>`;
  }
  const form = !f ? "" : `<div class="wk-form"><textarea id="bs-ftext" rows="2" maxlength="${f.kind === "back" ? 500 : 1000}" placeholder="${f.kind === "back" ? "Что поправить — сотрудник получит это" : `Сообщение для ${esc(t.name)}`}"></textarea>`
    + `<div class="row2"><button class="btn p" id="bs-fgo" style="flex:1">${f.kind === "back" ? "Вернуть" : "Отправить"}</button><button class="btn" id="bs-fx" aria-label="Отмена">✕</button></div><div class="res" id="bs-fres"></div></div>`;
  return `<div class="card wk-task bs-task s-${esc(t.state)}${t.late ? " late" : ""}${open ? " open" : ""}" data-t="${esc(t.id)}">`
    + `<button class="bs-tap" aria-expanded="${open}"><b>${esc(t.title)}</b><span class="wk-due${t.late ? " late" : ""}"><i class="bs-dot" style="background:${esc(bsColor(t.who))}"></i>${esc(t.name)}${due}</span></button>`
    + (open && t.note ? `<p class="wk-note">${esc(t.note)}</p>` : "")
    + (t.state === "done" && (t.report || t.photo) ? `<p class="wk-note bs-rep">«${esc(t.report || "без слов")}»${t.photo ? " · фото — на компьютере" : ""}</p>` : "")
    + (t.state === "moved" && t.reason ? `<p class="wk-note">Причина переноса: ${esc(t.reason)}</p>` : "")
    + (t.remark ? `<p class="wk-remark">Вы вернули: ${esc(t.remark)}</p>` : "")
    + (pend ? `<p class="bs-wait">${{ accept: "Принимаю", back: "Возвращаю", cancel: "Снимаю", remind: "Напоминаю", message: "Отправляю" }[pend.cmd] || "Отправляю"} — ${bsPendTxt(pend)}</p>` : "")
    + acts + form + `</div>`;
}
const bsColor = (mid) => ((((bsLoad().snap || {}).members || []).find(m => m.id === mid) || {}).color) || "var(--brand)";
function bsAssignHtml(s) {
  const ms = s.members.slice().sort((a, b) => (b.joined - a.joined) || a.name.localeCompare(b.name, "ru"));
  const chips = [["сегодня к 18", "Сегодня"], ["завтра к 12", "Завтра"], ["до пятницы", "До пятницы"], ["", "Без срока"]];
  return `<div class="card bs-form"><b class="bs-ft">Новое поручение</b>`
    + `<label class="f"><span>Кому</span><select id="bs-who">${ms.map(m => `<option value="${esc(m.id)}"${bsForm.who === m.id ? " selected" : ""}>${esc(m.name)}${m.role ? " — " + esc(m.role) : ""}${m.joined ? "" : " (ещё не вошёл)"}</option>`).join("")}</select></label>`
    + `<label class="f"><span>Что сделать</span><textarea id="bs-title" rows="2" maxlength="300" placeholder="Обновить прайс на сайте">${esc(bsForm.title || "")}</textarea></label>`
    + `<label class="f"><span>Срок</span><input id="bs-due" maxlength="60" placeholder="до пятницы, завтра к 12…" value="${esc(bsForm.due || "")}"></label>`
    + `<div class="bs-chips">${chips.map(([v, l]) => `<button class="bs-chip${(bsForm.due || "") === v ? " on" : ""}" data-due="${esc(v)}">${l}</button>`).join("")}</div>`
    + `<label class="f"><span>Подробности — по желанию</span><input id="bs-note" maxlength="500" placeholder="цены — из письма поставщика"></label>`
    + `<div class="row2"><button class="btn p" id="bs-ago" style="flex:1">Поручить</button><button class="btn" id="bs-ax">Отмена</button></div><div class="res" id="bs-ares"></div></div>`;
}
function bsMsgsHtml(s) {
  const pm = bsPendOf(p => p.cmd === "message");
  const items = s.inbox.slice(-30).map(x => ({ ...x, ts: bsSec(x.ts) })).concat(pm.map(p => ({ ts: p.ts, who: p.a.who, name: p.a.name || "", t: p.a.text, out: true, pend: p })));
  const ms = s.members.filter(m => m.joined);
  const f = bsForm && bsForm.kind === "reply" ? bsForm : null;
  let h = items.length ? `<div class="wk-feed bs-feed">${items.map((x, i) => `<p class="${x.out ? "out" : ""}${x.pend ? " pend" : ""}"><b>${x.out ? "Вы → " + esc(x.name) : esc(x.name)}</b><span>${esc(x.t || "фото")}${x.photo ? " · фото — на компьютере" : ""}</span>`
      + `<time>${x.pend ? bsPendTxt(x.pend) : bsWhen(x.ts)}</time>${!x.out && ms.some(m => m.id === x.who) ? `<button class="lnk" data-reply="${esc(x.who)}">Ответить</button>` : ""}</p>`).join("")}</div>`
    : `<div class="card wk-none"><b>Переписки пока нет</b><p class="hint">Когда сотрудник напишет вам не по поручению, сообщение появится здесь — и на компьютере.</p></div>`;
  if (ms.length) h += `<div class="wk-sec"><span>Написать сотруднику</span></div><div class="card wk-msg bs-msg"><select id="bs-mwho" aria-label="Кому">${ms.map(m => `<option value="${esc(m.id)}"${f && f.who === m.id ? " selected" : ""}>${esc(m.name)}</option>`).join("")}</select>`
    + `<textarea id="bs-mtext" rows="2" maxlength="1000" placeholder="Сообщение…"></textarea><button class="btn p w" id="bs-msend">Отправить</button><div class="res" id="bs-mres"></div></div>`;
  return h;
}
function bsBind() {
  const r = $("#bs-ref"); if (r) r.onclick = async () => { r.disabled = true; r.textContent = "Спрашиваю…"; await bsAsk(true); setTimeout(() => { if (r.isConnected) { r.disabled = false; r.textContent = "Обновить"; } }, 6000); };
  $$("#work-body .bs-seg [data-v]").forEach(b => b.onclick = () => { bsView = b.dataset.v; bsForm = null; wkRender(); });
  const nw = $("#bs-new"); if (nw) nw.onclick = () => { bsForm = { kind: "assign", due: "" }; wkRender(); setTimeout(() => { const t = $("#bs-title"); if (t) t.focus(); }, 60); };
  const oks = $("#bs-oks"); if (oks) oks.onclick = () => { bsOkShow = !bsOkShow; wkRender(); };
  $$("#work-body .bs-chips [data-due]").forEach(b => b.onclick = () => { bsKeep(); bsForm.due = b.dataset.due; wkRender(); });
  const ax = $("#bs-ax"); if (ax) ax.onclick = () => { bsForm = null; wkRender(); };
  const ago = $("#bs-ago"); if (ago) ago.onclick = async () => {
    bsKeep(); const res = $("#bs-ares"), f = bsForm;
    if (!f.title.trim()) { res.className = "res err"; res.textContent = "Напишите, что поручить"; $("#bs-title").focus(); return; }
    const m = bsLoad().snap.members.find(x => x.id === f.who);
    ago.disabled = true; res.className = "res"; res.textContent = "Отправляю…";
    try { await bsCmd("assign", { who: f.who, name: m ? m.name : "", title: f.title.trim(), due: (f.due || "").trim(), note: (f.note || "").trim() }); bsForm = null; wkRender(); toast("Отправлено на компьютер — он поручит"); }
    catch (e) { ago.disabled = false; res.className = "res err"; res.textContent = "Не ушло: " + e.message; }
  };
  $$("#work-body .bs-tap").forEach(b => b.onclick = () => { const id = b.closest(".bs-task").dataset.t; bsOpenId = bsOpenId === id ? "" : id; bsForm = null; wkRender(); });
  $$("#work-body .bs-task [data-a]").forEach(b => b.onclick = async () => {
    const id = b.closest(".bs-task").dataset.t, a = b.dataset.a, t = bsLoad().snap.tasks.find(x => x.id === id); if (!t) return;
    if (a === "back" || a === "write") { bsForm = { kind: a === "back" ? "back" : "msg", id, who: t.who }; wkRender(); setTimeout(() => { const x = $("#bs-ftext"); if (x) x.focus(); }, 60); return; }
    if (a === "cancel" && !confirm(`Снять поручение «${t.title}»? ${t.name} получит, что делать не нужно.`)) return;
    b.disabled = true;
    try { await bsCmd(a, { id }); wkRender(); } catch (e) { b.disabled = false; toast("Не ушло: " + e.message, 3500); }
  });
  const fx = $("#bs-fx"); if (fx) fx.onclick = () => { bsForm = null; wkRender(); };
  const fgo = $("#bs-fgo"); if (fgo) fgo.onclick = async () => {
    const f = bsForm, txt = $("#bs-ftext").value.trim(), res = $("#bs-fres"), t = bsLoad().snap.tasks.find(x => x.id === f.id) || {};
    if (!txt) { res.className = "res err"; res.textContent = f.kind === "back" ? "Напишите, что поправить" : "Напишите сообщение"; return; }
    fgo.disabled = true;
    try { if (f.kind === "back") await bsCmd("back", { id: f.id, remark: txt }); else await bsCmd("message", { who: f.who, name: t.name, text: txt }); bsForm = null; wkRender(); }
    catch (e) { fgo.disabled = false; res.className = "res err"; res.textContent = "Не ушло: " + e.message; }
  };
  $$("#work-body [data-reply]").forEach(b => b.onclick = () => {
    bsForm = { kind: "reply", who: b.dataset.reply }; wkRender();
    setTimeout(() => { const x = $("#bs-mtext"); if (x) { x.focus(); x.scrollIntoView({ block: "center", behavior: "smooth" }); } }, 60);
  });
  const ms = $("#bs-msend"); if (ms) ms.onclick = async () => {
    const who = $("#bs-mwho").value, txt = $("#bs-mtext").value.trim(), res = $("#bs-mres");
    if (!txt) { $("#bs-mtext").focus(); return; }
    const m = bsLoad().snap.members.find(x => x.id === who) || {};
    ms.disabled = true; res.className = "res"; res.textContent = "Отправляю…";
    try { await bsCmd("message", { who, name: m.name || "", text: txt }); bsForm = null; wkRender(); }
    catch (e) { ms.disabled = false; res.className = "res err"; res.textContent = "Не ушло: " + e.message; }
  };
}
function bsKeep() {                               // поля формы «Поручить» — в bsForm до перерисовки
  if (!bsForm || bsForm.kind !== "assign") return;
  const v = (id) => { const e = $(id); return e ? e.value : ""; };
  Object.assign(bsForm, { who: v("#bs-who"), title: v("#bs-title"), due: v("#bs-due"), note: v("#bs-note") });
}

/* ---------- голосом ---------- */
function bsPrompt() {
  if (!bsHas()) return "";
  const s = bsLoad().snap;
  return `ПОРУЧЕНИЯ СОТРУДНИКАМ (ты на телефоне руководителя; доска и рассылка — на компьютере «${s.dev}»): компания «${s.company}», сотрудники: `
    + (s.members.map(m => m.name + (m.role ? ` (${m.role})` : "")).join(", ") || "пока никого")
    + ". «Поручи Анне … до пятницы» — team_assign; «что с поручениями?», «что сделал Иван?» — team_status; «напиши/ответь Анне …» — team_message."
    + " Это поручения сотрудникам — не личные задачи и не напоминания.";
}
function bsTools() {
  if (!bsHas()) return [];
  return [{ name: "team_status", description: "Поручения сотрудникам: что поручено, кто взял, что сделано, просрочено, что написали сотрудники. who — по одному человеку (можно пусто).", parameters: O({ who: STR }) },
    { name: "team_assign", description: "Поручить сотруднику (уйдёт ему с компьютера руководителя). who — кому, title — что сделать, due — срок фразой («до пятницы», «завтра к 12», «каждый понедельник к 10» — повторять), note — подробности.", parameters: O({ who: STR, title: STR, due: STR, note: STR }, ["who", "title"]) },
    { name: "team_message", description: "Написать сотруднику не по поручению — ответить на его сообщение или сказать что-то. who — кому, text — что.", parameters: O({ who: STR, text: STR }, ["who", "text"]) }];
}
async function bsTool(name, a) {
  const s = bsLoad().snap; if (!s) return "Ошибка: «Поручения» на компьютере ещё не прислали доску.";
  if (name === "team_status") {
    let ts = s.tasks, ib = s.inbox.filter(x => !x.out);
    if (a.who) { const w = bsWho(a.who); if (w.err) return "Ошибка: " + w.err; const ids = (w.m ? [w.m] : w.many).map(m => m.id); ts = ts.filter(t => ids.includes(t.who)); ib = ib.filter(x => ids.includes(x.who)); }
    const rows = ts.map(t => `- ${t.name}: «${t.title}» — ${BS_ONE[t.state] || t.state}${t.due_text ? ", срок " + t.due_text : ""}${t.late ? " (просрочено)" : ""}${t.reason ? ", причина переноса: " + t.reason : ""}${t.state === "done" && t.report ? ", отчёт: " + t.report : ""}`);
    const msg = ib.slice(-3).map(x => `- ${x.name} написал(а): ${x.t || "фото"}`);
    return (rows.join("\n") || "Поручений нет.") + (msg.length ? "\nПоследние сообщения сотрудников:\n" + msg.join("\n") : "") + `\n(доска с компьютера «${s.dev}», ${bsWhen(s.at)}). Скажи коротко, своими словами.`;
  }
  const w = bsWho(a.who);
  if (w.err) return "Ошибка: " + w.err + ". Спроси, кому.";
  if (w.many) return `Ошибка: подходят ${w.many.map(m => m.name).join(" и ")} — спроси, кому именно.`;
  if (name === "team_assign") {
    if (!String(a.title || "").trim()) return "Ошибка: что поручить? Спроси.";
    await bsCmd("assign", { who: w.m.id, name: w.m.name, title: String(a.title).trim(), due: String(a.due || "").trim(), note: String(a.note || "").trim() });
    return `Отправлено на компьютер «${s.dev}» — оттуда поручение уйдёт: ${w.m.name}${w.m.joined ? "" : " (ещё не вошёл — получит после входа)"}. Если компьютер не сможет — скажу. Скажи коротко.`;
  }
  if (name === "team_message") {
    if (!String(a.text || "").trim()) return "Ошибка: что написать? Спроси.";
    if (!w.m.joined) return `Ошибка: ${w.m.name} ещё не вошёл(вошла) — сообщение не дойдёт.`;
    await bsCmd("message", { who: w.m.id, name: w.m.name, text: String(a.text).trim() });
    return `Отправлено: ${w.m.name} (через компьютер «${s.dev}»). Скажи коротко.`;
  }
  return "Ошибка: неизвестное действие.";
}
