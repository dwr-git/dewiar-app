/* Студия Dewiar, раздел «Поручения» (28.10, по макету «Dewiar — обучение и «Команда»», экраны Team и TeamChat; владелец
   выбрал название «Поручения» — «команда» путалась с командами голосом и «командой помощников»; внутри — team): поручения
   сотрудникам через бота компании в Telegram. Доска «Новые → В работе → Сделано → Перенесено», справа — карточка
   поручения: кто, срок, история (поручено, взял, сделано с фото, перенос с причиной), «Принять» и «Вернуть с замечанием».
   Без бота — три шага подключения. Ядро: team_get/connect/forget/set, team_member_add/del/code, team_assign {who, title,
   due, note}, team_accept/back/cancel/remind {id}, team_photo {name}; событие «team». */
let TM = null, TM_SEL = "", TM_TAB = "board", TM_CH = "tg";
const TM_CHN = { tg: "Telegram", max: "MAX" };
const tmChats = () => { const on = ((TM && TM.bots) || []).filter(b => b.connected).map(b => b.name); return on.length ? on.join(" и ") : "мессенджер"; };
const TM_COLS = [["new", "Новые"], ["work", "В работе"], ["done", "Сделано"], ["moved", "Перенесено"]];
const TM_EV = { assign: "Поручено", sent: "Ушло сотруднику", take: "Взял в работу", done: "Сделано", move: "Перенос", ok: "Принято",
  back: "Возвращено с замечанием", nudge: "Напоминание отправлено" };
const TM_WD = ["воскресенье", "понедельник", "вторник", "среда", "четверг", "пятница", "суббота"];
const TM_MON = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"];
const tmIni = (n) => (n || "?").split(/\s+/).filter(Boolean).slice(0, 2).map(w => w[0]).join("").toUpperCase();
const tmHM = (ts) => { const d = new Date(ts * 1000); return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`; };
const tmDay = (ts) => { const d = new Date(ts * 1000), t = new Date(); return d.toDateString() === t.toDateString() ? "" : `${d.getDate()} ${TM_MON[d.getMonth()]}, `; };
const tmFem = (n) => /[ая]$/i.test((n || "").split(/\s+/)[0] || "") && !/^(никита|илья|кузьма|фома|лука|савва)$/i.test((n || "").split(/\s+/)[0]);
const tmWord = (n, a, b, c) => `${n} ${typeof plural === "function" ? plural(n, a, b, c) : c}`;

async function tmCall(cmd, args, ok) {
  try { const d = await core.call(cmd, args || {}); if (d && d.members) { TM = d; tmRender(); } if (ok) toast(ok); return d; }
  catch (e) { toast(e.message, 3500); return null; }
}

function tmRender() {
  const d = TM; if (!d || !$("#p-team")) return;
  const on = !!d.connected;
  $("#tm-setup").hidden = on;
  $("#tm-tabs").hidden = !on; $("#tm-new").hidden = !on || !d.members.length;
  ["board", "people", "how"].forEach(t => { const w = $(t === "board" ? "#tm-boardwrap" : t === "people" ? "#tm-peoplewrap" : "#tm-howwrap"); w.hidden = !on || TM_TAB !== t; });
  $$("#tm-tabs button").forEach(b => b.classList.toggle("on", b.dataset.t === TM_TAB));
  $("#tm-h").textContent = on && d.company ? d.company : "Поручения";
  const now = new Date(), joined = d.members.filter(m => m.joined).length;
  $("#tm-sub").textContent = on
    ? (d.members.length ? `${tmWord(joined, "сотрудник", "сотрудника", "сотрудников")} на связи${d.members.length > joined ? ` · ещё ${d.members.length - joined} ждём` : ""} · сегодня ${TM_WD[now.getDay()]}, ${now.getDate()} ${TM_MON[now.getMonth()]}`
      : "Добавьте сотрудников — и поручайте голосом или кнопкой «Поручить».")
      + (d.problem ? ` · ⚠ ${d.problem}` : "")
    : "Поручения сотрудникам в Telegram или MAX: берут, делают с фото, переносят с причиной.";
  const dot = $("#team-dot"); if (dot) dot.classList.toggle("on", d.tasks.some(t => t.state === "done" || t.state === "moved"));
  if (!on) return;
  tmBoard(); tmDetail(); tmPeople(); tmHow();
  $("#tm-who").innerHTML = d.members.map(m => `<option value="${escH(m.id)}">${escH(m.name)}${m.joined ? "" : " (ещё не вошёл)"}</option>`).join("");
}

function tmCard(t) {
  const cls = ["tm-card", t.state, t.late ? "late" : "", t.id === TM_SEL ? "sel" : ""].filter(Boolean).join(" ");
  let due = t.due_text ? `до ${t.due_text}` : "без срока";
  if (t.state === "done") due = (t.report && t.report.photo) ? "сделано · фото" : "сделано";
  if (t.state === "ok") due = "принято";
  if (t.state === "moved") due = `на ${t.due_text}${t.reason ? ` · «${t.reason}»` : ""}`;
  return `<button class="${cls}" data-id="${escH(t.id)}"><span class="tm-ava" style="background:${escH(t.color)}" aria-hidden="true">${escH(tmIni(t.name))}</span>`
    + `<span class="tm-cbody"><small>${escH(t.name)}</small><b>${escH(t.title)}</b><em>${t.late ? "просрочено · " : ""}${escH(due)}</em></span></button>`;
}

function tmReps() {                                    // повторяющиеся поручения — полоской над доской, ✕ — больше не поручать
  const box = $("#tm-reps"), r = (TM && TM.repeats) || []; if (!box) return;
  box.hidden = !r.length;
  box.innerHTML = r.length ? `<b class="tm-rh">Повторяются</b>` + r.map(x => `<span class="tm-rep" title="Следующее — ${escH(x.next_text)}">`
    + `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 12a8 8 0 0 1 13.7-5.6L20 8.7M20 4v4.7h-4.7M20 12a8 8 0 0 1-13.7 5.6L4 15.3M4 20v-4.7h4.7"/></svg>`
    + `<span><b>${escH(x.title)}</b><small>${escH(x.name)} · ${escH(x.rule)}</small></span><button type="button" data-rx="${escH(x.id)}" aria-label="Больше не поручать: ${escH(x.title)}">×</button></span>`).join("") : "";
  $$("#tm-reps [data-rx]").forEach(b => b.onclick = async () => { if (await ask("Больше не поручать это по расписанию? Уже отправленные поручения останутся.")) tmCall("team_repeat_del", { id: b.dataset.rx }, "Повтор убран"); });
}
function tmBoard() {
  tmReps();
  const by = (s) => TM.tasks.filter(t => s === "done" ? (t.state === "done" || t.state === "ok") : t.state === s);
  $("#tm-board").innerHTML = TM_COLS.map(([s, name]) => {
    const list = by(s);
    const body = list.length ? list.map(tmCard).join("")
      : `<p class="tm-empty">${{ new: "Новых нет — поручите голосом или кнопкой «Поручить»", work: "Пока никто не взял", done: "Здесь появится сделанное", moved: "Переносов нет" }[s]}</p>`;
    return `<div class="tm-col ${s}"><div class="tm-ch"><b>${name}</b><span>${list.length}</span></div>${body}</div>`;
  }).join("");
  $$("#tm-board .tm-card").forEach(b => b.onclick = () => { TM_SEL = TM_SEL === b.dataset.id ? "" : b.dataset.id; tmBoard(); tmDetail(); });
}

function tmDetail() {
  const box = $("#tm-detail"), t = TM.tasks.find(x => x.id === TM_SEL);
  if (!t) {                                         // ничего не выбрано — сообщения от сотрудников
    const inbox = (TM.inbox || []).slice().reverse();
    box.innerHTML = `<h3>Сообщения от сотрудников</h3>` + (inbox.length
      ? `<ul class="tm-inbox">${inbox.map(x => `<li><b>${escH(x.name)}</b><small>${tmDay(x.ts)}${tmHM(x.ts)}</small><p>${escH(x.t || "фото")}</p>`
        + (x.photo ? `<button class="tm-thumb" data-photo="${escH(x.photo)}">Фото</button>` : "") + `</li>`).join("")}</ul>`
      : `<p class="tm-empty">Выберите поручение — здесь будет вся история: кто взял, отчёт и фото, переносы. А если сотрудник напишет боту не по кнопке — сообщение появится тут.</p>`);
    tmPhotos(box); return;
  }
  const m = TM.members.find(x => x.id === t.who) || {};
  const fem = tmFem(t.name);
  const evText = (e) => e.ev === "take" ? (fem ? "Взяла в работу" : "Взял в работу") : e.ev === "assign" && e.t === "голосом" ? "Поручено голосом" : TM_EV[e.ev] || e.ev;
  const log = (t.log || []).map(e => `<li class="ev-${escH(e.ev)}"><time>${tmDay(e.ts)}${tmHM(e.ts)}</time><div><b>${escH(evText(e))}</b>`
    + (e.t && e.ev !== "assign" ? `<p>${e.ev === "done" ? "«" + escH(e.t) + "»" : escH(e.t)}</p>` : "")
    + (e.ev === "done" && t.report && t.report.photo && t.state !== "work" ? `<button class="tm-thumb" data-photo="${escH(t.report.photo)}">Фото от сотрудника</button>` : "")
    + `</div></li>`).join("");
  const head = { new: "Новое · ждёт «Беру»", work: "В работе", done: "Сделано · ждёт вашей проверки", moved: "Перенесено", ok: "Принято" }[t.state];
  let acts = "";
  if (t.state === "done") acts = `<button class="btn primary" data-a="accept">Принять</button><button class="btn" data-a="back">Вернуть с замечанием</button>`;
  else if (t.state !== "ok") acts = `<button class="btn" data-a="remind">Напомнить</button><button class="btn danger" data-a="cancel">Снять поручение</button>`;
  box.innerHTML = `<small class="tm-state ${escH(t.state)}${t.late ? " late" : ""}">${t.late ? "Просрочено · " : ""}${head}</small>`
    + `<h3>${escH(t.title)}</h3>`
    + `<p class="tm-meta">${escH(t.name)}${m.role ? " · " + escH(m.role) : ""}${t.due_text ? ` · срок — ${escH(t.due_text)}` : ""}</p>`
    + (t.note ? `<p class="tm-note">${escH(t.note)}</p>` : "")
    + (!t.joined ? `<p class="tm-warn">${escH(t.name)} ещё не открыл${fem ? "а" : ""} приглашение — поручение уйдёт сразу после входа.</p>` : "")
    + `<ol class="tm-log">${log}</ol>`
    + (t.state === "done" || t.state === "ok" ? `<p class="tm-cal">В календаре: «✓ ${escH(t.title)} — ${escH(t.name)}»</p>` : "")
    + (acts ? `<div class="tm-acts">${acts}</div>` : "");
  tmPhotos(box);
  $$("#tm-detail [data-a]").forEach(b => b.onclick = async () => {
    const a = b.dataset.a;
    if (a === "accept") return tmCall("team_accept", { id: t.id }, "Принято — сотруднику ушло «спасибо»");
    if (a === "remind") return tmCall("team_remind", { id: t.id }, "Напомнила сотруднику");
    if (a === "cancel") { if (await ask(`Снять поручение «${t.title}»? Сотруднику придёт, что делать не нужно.`)) { TM_SEL = ""; tmCall("team_cancel", { id: t.id }, "Поручение снято"); } return; }
    if (a === "back") { const r = await askText("Что поправить? Сотрудник получит это в мессенджере", "", { ok: "Вернуть" }); if (r && r.trim()) tmCall("team_back", { id: t.id, remark: r.trim() }, "Вернула с замечанием"); }
  });
}

function tmPhotos(root) {
  $$("[data-photo]", root).forEach(b => b.onclick = async () => {
    const d = await tmCall("team_photo", { name: b.dataset.photo }); if (!d || !d.url) return;
    const dlg = $("#tm-photo"); dlg.querySelector("img").src = d.url; dlg.showModal();
  });
}

function tmPeople() {
  const d = TM;
  $("#tm-people").innerHTML = d.members.length ? d.members.map(m => {
    const st = m.joined ? `<span class="tm-chip ok">в ${escH(m.ch || "Telegram")}${m.tg ? " · @" + escH(m.tg) : ""}</span>`
      : m.link ? `<span class="tm-chip wait">ждём входа</span>` : `<span class="tm-chip wait">ссылка устарела</span>`;
    const ls = Object.entries(m.links || (m.link ? { tg: m.link } : {}));
    const link = !m.joined ? ls.map(([ch, url]) => `<div class="tm-link">${ls.length > 1 ? `<em>${TM_CHN[ch] || ch}</em>` : ""}<input type="text" readonly value="${escH(url)}" aria-label="Ссылка-приглашение ${TM_CHN[ch] || ch}"><button class="btn small" data-copy="${escH(url)}">Копировать</button></div>`).join("") : "";
    return `<li><span class="tm-ava" style="background:${escH(m.color)}" aria-hidden="true">${escH(tmIni(m.name))}</span>`
      + `<div class="tm-pbody"><b>${escH(m.name)}</b><small>${escH(m.role || "")}${m.role ? " · " : ""}${m.open ? tmWord(m.open, "открытое поручение", "открытых поручения", "открытых поручений") : "открытых поручений нет"}</small>${st}${link}</div>`
      + `<div class="tm-pacts">${!m.joined ? `<button class="btn small" data-code="${escH(m.id)}">Новая ссылка</button>` : ""}<button class="btn small danger" data-del="${escH(m.id)}" title="Убрать из команды">Убрать</button></div></li>`;
  }).join("") : `<li class="tm-empty">Пока никого. Добавьте первого сотрудника справа — и отправьте ему ссылку.</li>`;
  $$("#tm-people [data-copy]").forEach(b => b.onclick = async () => {
    try { await navigator.clipboard.writeText(b.dataset.copy); toast("Ссылка скопирована — отправьте её сотруднику"); }
    catch (e) { const i = b.parentNode.querySelector("input"); i.select(); toast("Выделила ссылку — нажмите Ctrl+C"); }
  });
  $$("#tm-people [data-code]").forEach(b => b.onclick = () => tmCall("team_member_code", { id: b.dataset.code }, "Новая ссылка готова, старая больше не работает"));
  $$("#tm-people [data-del]").forEach(b => b.onclick = async () => {
    const m = d.members.find(x => x.id === b.dataset.del);
    if (await ask(`Убрать ${m ? m.name : "сотрудника"} из команды? Открытые поручения закроются, бот перестанет ему отвечать.`)) tmCall("team_member_del", { id: b.dataset.del }, "Убрано");
  });
}

function tmHow() {
  const d = TM;
  if (document.activeElement !== $("#tm-company")) $("#tm-company").value = d.company || "";
  if (document.activeElement !== $("#tm-boss")) $("#tm-boss").value = d.boss || "";
  $("#tm-speak").checked = !!d.speak;
  if (document.activeElement !== $("#tm-digest")) $("#tm-digest").value = d.digest || "";
  // боты компании: подключённые — с «Отключить»; второй мессенджер — подключить здесь же
  $("#tm-bots").innerHTML = (d.bots || []).map(b => b.connected
      ? `<div class="tm-botline"><span><b>${escH(b.name)}</b> · @${escH(b.bot)}${b.running ? "" : " · не слушает"}${b.problem ? ` · ⚠ ${escH(b.problem)}` : ""}</span><button class="btn small danger" data-off="${b.ch}" type="button">Отключить</button></div>`
      : `<div class="tm-botline"><span><b>${escH(b.name)}</b> · не подключён</span><button class="btn small" data-on="${b.ch}" type="button">Подключить</button></div>`).join("");
  $$("#tm-bots [data-off]").forEach(x => x.onclick = async () => {
    if (await ask(`Отключить бота компании в ${TM_CHN[x.dataset.off]}? Сотрудники и поручения останутся; чтобы бот снова заработал, вставьте его токен.`)) tmCall("team_forget", { ch: x.dataset.off }, "Бот отключён");
  });
  $$("#tm-bots [data-on]").forEach(x => x.onclick = async () => {
    const tok = await askText(x.dataset.on === "max" ? "Токен бота MAX (business.max.ru → Чат-боты → Интеграция)" : "Токен бота Telegram (@BotFather → /newbot)", "", { ok: "Подключить" });
    if (tok && tok.trim()) tmCall("team_connect", { token: tok.trim(), ch: x.dataset.on }, `Бот подключён — теперь у сотрудников две ссылки на выбор`);
  });
}

async function tmLoad() {
  try { TM = await core.call("team_get"); } catch (e) { return; }
  if (!TM || !Array.isArray(TM.tasks)) { TM = null; return; }
  tmRender();
}
window.loadTeam = tmLoad;

if ($("#p-team")) {
  $$("#tm-tabs button").forEach(b => b.onclick = () => { TM_TAB = b.dataset.t; tmRender(); });
  $$("#tm-chs button").forEach(b => b.onclick = () => {
    TM_CH = b.dataset.ch; $$("#tm-chs button").forEach(x => x.classList.toggle("on", x === b));
    $("#tm-steps-tg").hidden = TM_CH !== "tg"; $("#tm-steps-max").hidden = TM_CH !== "max";
  });
  $("#tm-connect").onclick = async () => {
    const tok = $("#tm-token").value.trim(); if (!tok) { $("#tm-token").focus(); return; }
    const d = await tmCall("team_connect", { token: tok, ch: TM_CH }, "Бот подключён — добавьте сотрудников");
    if (d) { $("#tm-token").value = ""; TM_TAB = "people"; tmRender(); }
  };
  $("#tm-new").onclick = () => { const f = $("#tm-form"); TM_TAB = "board"; tmRender(); f.hidden = !f.hidden; if (!f.hidden) $("#tm-title").focus(); };
  $("#tm-fcancel").onclick = () => { $("#tm-form").hidden = true; };
  $("#tm-form").onsubmit = async (e) => {
    e.preventDefault();
    const title = $("#tm-title").value.trim(); if (!title) { $("#tm-title").focus(); return; }
    const who = $("#tm-who").value, m = TM.members.find(x => x.id === who);
    const d = await tmCall("team_assign", { who, title, due: $("#tm-due").value.trim(), note: $("#tm-note").value.trim() });
    if (d) toast(d.made && d.made.repeat ? `Буду поручать ${d.made.name} — ${d.made.rule}` : m && m.joined ? `Поручено — ${m.name} получит в ${m.ch || "мессенджере"}` : "Поручено — уйдёт, как только сотрудник откроет приглашение");
    if (d) { $("#tm-title").value = ""; $("#tm-due").value = ""; $("#tm-note").value = ""; $("#tm-form").hidden = true; }
  };
  $("#tm-pform").onsubmit = async (e) => {
    e.preventDefault();
    const name = $("#tm-pname").value.trim(); if (!name) { $("#tm-pname").focus(); return; }
    const d = await tmCall("team_member_add", { name, role: $("#tm-prole").value.trim() }, "Добавлено — скопируйте ссылку и отправьте сотруднику");
    if (d) { $("#tm-pname").value = ""; $("#tm-prole").value = ""; }
  };
  const save = (k) => () => tmCall("team_set", { [k]: $(`#tm-${k}`).value.trim() }, "Сохранено");
  $("#tm-company").onchange = save("company");
  $("#tm-boss").onchange = save("boss");
  $("#tm-speak").onchange = () => tmCall("team_set", { speak: $("#tm-speak").checked });
  $("#tm-digest").onchange = () => tmCall("team_set", { digest: $("#tm-digest").value }, $("#tm-digest").value ? `Итог дня — в ${$("#tm-digest").value}` : "Итог дня не присылаю");
  $("#tm-photo-x").onclick = () => $("#tm-photo").close();
  core.on("team", (e) => { TM = e; tmRender(); });
  core.on("hello", () => { if ($("#p-team").classList.contains("cur")) tmLoad(); });
}
