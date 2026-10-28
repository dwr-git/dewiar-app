/* Студия Dewiar, раздел «Клиенты» (28.10, владелец: «Лира как личная CRM»): слева — список с поиском (у кого прошёл срок
   следующего шага — сверху, с красной меткой), справа — карточка: имя и компания (правятся на месте), телефон и почта,
   «Следующий шаг» (что и когда — напоминание в «Делах»; «Сделано»), «Записать» (заметка, звонок, сделка) и история по
   дням. Ядро — clients.py: clients_list {q}, client_get/add/save/note/note_del/next/next_done/del; событие «clients». */
let CR = { list: [], cur: "", card: null, q: "", t: 0, kind: "note" };
const CR_KIND = { note: ["Заметка", "M5 4h10l4 4v12H5z M14 4v5h5"], call: ["Звонок", "M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2"],
  deal: ["Сделка", "M3 12l4-4 4 3 6-6 4 4-10 10z"], done: ["Сделано", "M5 12.5l4.5 4.5L19 7.5"] };
const CR_COL = ["#8B8CF7", "#4BE3A1", "#FFB547", "#FF8FA8", "#7FD4FF", "#B78CFF", "#9BE15D", "#FF8F6B"];
const crCol = (id) => CR_COL[[...String(id)].reduce((a, c) => a + c.charCodeAt(0), 0) % CR_COL.length];
const crIni = (n) => (n || "?").replace(/[«»"]/g, "").split(/\s+/).filter(Boolean).slice(0, 2).map(w => w[0]).join("").toUpperCase();
const CR_MON = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"];
function crWhen(iso) {
  if (!iso) return "";
  const d = new Date(iso), now = new Date(), hm = `${d.getHours()}:${String(d.getMinutes()).padStart(2, "0")}`;
  const days = Math.round((new Date(d.getFullYear(), d.getMonth(), d.getDate()) - new Date(now.getFullYear(), now.getMonth(), now.getDate())) / 864e5);
  return days === 0 ? `сегодня в ${hm}` : days === 1 ? `завтра в ${hm}` : days === -1 ? `вчера в ${hm}` : `${d.getDate()} ${CR_MON[d.getMonth()]} в ${hm}`;
}
const crDay = (ts) => { const d = new Date(ts * 1000), t = new Date(), y = new Date(Date.now() - 864e5);
  return d.toDateString() === t.toDateString() ? "Сегодня" : d.toDateString() === y.toDateString() ? "Вчера" : `${d.getDate()} ${CR_MON[d.getMonth()]}${d.getFullYear() !== t.getFullYear() ? " " + d.getFullYear() : ""}`; };
const crSvg = (d) => `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="${d}"/></svg>`;
async function crCall(cmd, args, ok) {
  try { const d = await core.call(cmd, args || {}); if (ok) toast(ok); return d; } catch (e) { toast(e.message, 3500); return null; }
}
async function crLoad() {
  const l = await crCall("clients_list", { q: CR.q }); if (!Array.isArray(l)) return;
  CR.list = l; crLeft();
  if (CR.cur && !l.some(x => x.id === CR.cur) && !CR.q) CR.cur = "";
  if (!CR.cur && l.length) CR.cur = l[0].id;
  if (CR.cur) crOpen(CR.cur); else crEmpty();
}
function crLeft() {
  const box = $("#cr-list"); if (!box) return;
  const over = CR.list.filter(x => x.overdue).length;
  $("#cr-sub").textContent = CR.list.length || CR.q
    ? `${typeof plural === "function" ? CR.list.length + " " + plural(CR.list.length, "клиент", "клиента", "клиентов") : CR.list.length}${over ? ` · ждут ответа: ${over}` : ""}`
    : "Кто это, как связаться, о чём договорились и что дальше — голосом или здесь.";
  const dot = $("#cr-dot"); if (dot) dot.classList.toggle("on", over > 0);
  box.innerHTML = CR.list.length ? CR.list.map(x => `<li><button class="cr-row${x.id === CR.cur ? " on" : ""}${x.overdue ? " late" : ""}" data-id="${escH(x.id)}">`
      + `<i class="cr-ava" style="--c:${crCol(x.id)}">${escH(crIni(x.name))}</i><span><b>${escH(x.name)}</b>`
      + `<small>${escH([x.company, x.next ? "→ " + x.next.what + (x.next.at ? ", " + crWhen(x.next.at) : "") : x.last].filter(Boolean).join(" · "))}</small></span>`
      + (x.overdue ? `<em>срок</em>` : "") + `</button></li>`).join("")
    : `<li class="cr-none">${CR.q ? "Никого не нашлось." : "Пока пусто."}</li>`;
  $$("#cr-list .cr-row").forEach(b => b.onclick = () => { CR.cur = b.dataset.id; $$("#cr-list .cr-row").forEach(x => x.classList.toggle("on", x === b)); crOpen(CR.cur); });
}
function crEmpty() {
  $("#cr-card").innerHTML = `<div class="cr-empty"><div class="cr-eico">${crSvg("M8.5 4a3.5 3.5 0 1 0 0 7a3.5 3.5 0 1 0 0-7 M2.5 20a6 6 0 0 1 12 0 M16 6.5a3 3 0 1 1 0 6 M17.5 14.5a5 5 0 0 1 4 5")}</div>`
    + `<h2>Первый клиент — одной фразой</h2><p>Скажите Лире — карточка заведётся сама, а договорённость попадёт в историю:</p>`
    + `<ul>${["Запиши: Иванов из «Ромашки» хочет 200 коробок до пятницы", "Перезвонить Иванову в четверг в 11", "Что у нас с Ивановым?", "Кому из клиентов надо перезвонить?"]
      .map(t => `<li>«${escH(t)}»</li>`).join("")}</ul><button class="btn primary" id="cr-new2">+ Клиент вручную</button></div>`;
  $("#cr-new2").onclick = crNew;
}
async function crOpen(id) {
  const c = await crCall("client_get", { id }); if (!c || c.id !== CR.cur) return;
  CR.card = c; crCard();
}
function crCard() {
  const c = CR.card, box = $("#cr-card"); if (!c || !box) return;
  const nx = c.next, groups = [];
  [...c.log].reverse().forEach(x => { const g = crDay(x.ts); const last = groups[groups.length - 1]; if (last && last[0] === g) last[1].push(x); else groups.push([g, [x]]); });
  box.innerHTML = `<header class="cr-head"><i class="cr-ava big" style="--c:${crCol(c.id)}">${escH(crIni(c.name))}</i><div class="cr-names">`
    + `<input class="cr-name" id="cr-name" value="${escH(c.name)}" maxlength="120" aria-label="Имя клиента">`
    + `<input class="cr-comp" id="cr-comp" value="${escH(c.company || "")}" maxlength="120" placeholder="Компания" aria-label="Компания"></div>`
    + `<button class="btn small ghost" id="cr-del" title="Удалить клиента">Удалить</button></header>`
    + `<div class="cr-contacts"><label>${crSvg(CR_KIND.call[1])}<input id="cr-phone" value="${escH(c.phone || "")}" maxlength="60" placeholder="Телефон" aria-label="Телефон"></label>`
    + `<label>${crSvg("M3 6h18v12H3z M3 7l9 6 9-6")}<input id="cr-email" type="email" value="${escH(c.email || "")}" maxlength="120" placeholder="Почта" aria-label="Почта"></label></div>`
    + `<div class="cr-next${c.overdue ? " late" : ""}"><h3>Следующий шаг</h3>`
    + (nx ? `<div class="cr-nx"><b>${escH(nx.what.charAt(0).toUpperCase() + nx.what.slice(1))}</b>${nx.at ? `<span>${c.overdue ? "срок прошёл · " : ""}${escH(crWhen(nx.at))}</span>` : ""}`
        + `<div class="cr-nxa"><button class="btn small primary" id="cr-ndone">Сделано</button><button class="btn small" id="cr-nedit">Изменить</button></div></div>` : "")
    + `<form class="cr-nform" id="cr-nform"${nx ? " hidden" : ""}><input id="cr-nwhat" maxlength="300" placeholder="Что сделать: перезвонить, отправить счёт…" value="${escH(nx ? nx.what : "")}">`
    + `<input id="cr-nwhen" type="datetime-local" value="${escH(nx && nx.at ? nx.at.slice(0, 16) : "")}" aria-label="Когда"><button class="btn small primary" type="submit">Поставить</button></form></div>`
    + (typeof dlClientHtml === "function" ? dlClientHtml(c) : "")
    + `<div class="cr-add"><div class="cr-kinds" role="radiogroup" aria-label="Что записать">${["note", "call", "deal"].map(k => `<button type="button" role="radio" data-k="${k}" aria-checked="${CR.kind === k}" class="${CR.kind === k ? "on" : ""}">${crSvg(CR_KIND[k][1])}${CR_KIND[k][0]}</button>`).join("")}</div>`
    + `<form class="cr-aform" id="cr-aform"><textarea id="cr-atext" rows="2" maxlength="1000" placeholder="О чём договорились, что хочет, что обещали"></textarea><button class="btn primary" type="submit">Записать</button></form></div>`
    + `<div class="cr-hist"><h3>История</h3>${groups.length ? groups.map(([g, xs]) => `<div class="cr-hday"><small>${escH(g)}</small>${xs.map(x => `<div class="cr-h ${escH(x.kind)}">`
        + `<i>${crSvg((CR_KIND[x.kind] || CR_KIND.note)[1])}</i><p>${escH(x.t)}</p><time>${new Date(x.ts * 1000).toTimeString().slice(0, 5)}</time>`
        + `<button class="cr-hx" data-n="${escH(x.id)}" title="Удалить запись" aria-label="Удалить запись">×</button></div>`).join("")}</div>`).join("")
      : `<p class="cr-hnone">Записей пока нет — запишите, о чём договорились, или скажите Лире.</p>`}</div>`
    + `<label class="cr-about"><span>О клиенте</span><textarea id="cr-note" rows="2" maxlength="2000" placeholder="Кто это, чем занимается, как лучше общаться">${escH(c.note || "")}</textarea></label>`;
  const save = (k, el) => el.onchange = async () => { const d = await crCall("client_save", { id: c.id, [k]: el.value }); if (d) { CR.card = Object.assign(CR.card, d); crLoadList(); } };
  save("name", $("#cr-name")); save("company", $("#cr-comp")); save("phone", $("#cr-phone")); save("email", $("#cr-email")); save("note", $("#cr-note"));
  $("#cr-del").onclick = async () => { if (!await ask(`Удалить «${c.name}» вместе с историей? Отменить нельзя.`, { ok: "Удалить", danger: true })) return; if (await crCall("client_del", { id: c.id }, "Клиент удалён")) { CR.cur = ""; crLoad(); } };
  $$(".cr-kinds button").forEach(b => b.onclick = () => { CR.kind = b.dataset.k; $$(".cr-kinds button").forEach(x => { x.classList.toggle("on", x === b); x.setAttribute("aria-checked", String(x === b)); }); $("#cr-atext").focus(); });
  $("#cr-aform").onsubmit = async (e) => { e.preventDefault(); const t = $("#cr-atext").value.trim(); if (!t) return $("#cr-atext").focus();
    const d = await crCall("client_note", { id: c.id, text: t, kind: CR.kind }); if (d) { CR.card = d; crCard(); crLoadList(); } };
  $("#cr-atext").onkeydown = (e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) $("#cr-aform").requestSubmit(); };
  $("#cr-nform").onsubmit = async (e) => { e.preventDefault(); const w = $("#cr-nwhat").value.trim(); if (!w) return $("#cr-nwhat").focus();
    const at = $("#cr-nwhen").value; const d = await crCall("client_next", { id: c.id, what: w, at: at || "" }, at ? "Напоминание поставлено" : ""); if (d) { CR.card = d; crOpen(c.id); crLoadList(); } };
  if ($("#cr-ndone")) $("#cr-ndone").onclick = async () => { const d = await crCall("client_next_done", { id: c.id }, "Отмечено"); if (d) { crOpen(c.id); crLoadList(); } };
  if ($("#cr-nedit")) $("#cr-nedit").onclick = () => { $("#cr-nform").hidden = false; $(".cr-nx").hidden = true; $("#cr-nwhat").focus(); };
  if (typeof dlClientBind === "function") dlClientBind(c);
  $$(".cr-hx").forEach(b => b.onclick = async () => { const d = await crCall("client_note_del", { id: c.id, nid: b.dataset.n }); if (d) { CR.card = d; crCard(); } });
}
async function crLoadList() { const l = await crCall("clients_list", { q: CR.q }); if (Array.isArray(l)) { CR.list = l; crLeft(); } }
async function crNew() {
  const name = await askText("Имя клиента или название компании", "", { ok: "Добавить" }); if (!name || !name.trim()) return;
  const c = await crCall("client_add", { name: name.trim() }); if (!c) return;
  CR.cur = c.id; CR.q = ""; if ($("#cr-q")) $("#cr-q").value = ""; await crLoad();
  setTimeout(() => { const i = $("#cr-comp"); if (i) i.focus(); }, 100);
}
window.loadClients = crLoad;
if ($("#p-clients")) {
  $("#cr-new").onclick = crNew;
  $("#cr-q").oninput = () => { clearTimeout(CR.t); CR.t = setTimeout(() => { CR.q = $("#cr-q").value.trim(); crLoad(); }, 220); };
  core.on("clients", () => { if ($("#p-clients").classList.contains("cur")) { crLoadList(); if (CR.cur) crOpen(CR.cur); } });
}
