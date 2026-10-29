/* «Клиенты» → «Сделки» и «кто нам должен» (0.58; core/deals.py). Вкладка «Сделки»: сверху — сколько нам должны
   (и сколько из этого просрочено), что зависло, сколько оплачено за 30 дней; ниже — доска по этапам: заявка →
   предложение → счёт → оплачено, у колонки — сумма. Карточка сделки: клиент, сумма, «оплатить до», метки «срок прошёл» и
   «без движения N дн.»; нажали — этапы одной кнопкой, «Открыть клиента», «Удалить». В карточке клиента — его сделки и
   «+ Сделка». Оплачено — в доходы «Денег» (переключатель «Оплаченное — в доходы»). Ядро: clients_deals,
   clients_deal_income {on}, client_deal_add / client_deal_set / client_deal_del. */
let DL = { board: null, open: "", adding: false, rem: null };      // rem — черновик «Напомнить об оплате» {did, cid, to, subject, body, mail}
const DL_ST = { lead: "Заявка", offer: "Предложение", invoice: "Счёт", paid: "Оплачено", lost: "Отказ" };
const DL_NEXT = { lead: "offer", offer: "invoice", invoice: "paid" };
const DL_NEXT_TXT = { lead: "Отправили предложение", offer: "Выставили счёт", invoice: "Оплачено" };
const dlMoney = (n, cur) => (typeof fmtMoney === "function" ? fmtMoney(n, cur || (calData && calData.currency) || "") : `${n} ${cur || ""}`);
const dlSums = (o) => Object.entries(o || {}).map(([c, v]) => dlMoney(v, c)).join(" + ") || "0";
const dlDate = (iso) => { if (!iso) return ""; const d = new Date(iso + "T12:00"); return d.toLocaleDateString("ru-RU", { day: "numeric", month: "long" }); };

async function dlLoad() {
  try { DL.board = await core.call("clients_deals"); } catch (e) { toast(e.message, 3500); return; }
  dlRender();
}
function dlTab(t) {
  $$("#cr-tabs button").forEach(b => b.classList.toggle("on", b.dataset.t === t));
  $(".cr-main").hidden = t !== "list"; $("#dl-wrap").hidden = t !== "deals";
  if ($("#crm-wrap")) $("#crm-wrap").hidden = t !== "crm";
  if (t === "deals") dlLoad(); else if (t === "crm") { if (window.crmLoad) crmLoad(); } else crLoad();
}
function dlRender() {
  const b = DL.board, box = $("#dl-wrap"); if (!b || !box) return;
  const owedN = b.cols.find(c => c.stage === "invoice").items.length, lost = b.cols.find(c => c.stage === "lost").items;
  box.innerHTML = `<div class="dl-sum">`
    + `<div class="dl-stat${b.n_overdue ? " late" : ""}"><small>Нам должны</small><b>${escH(dlSums(b.owed))}</b><span>${owedN ? `${owedN} ${plural(owedN, "счёт", "счёта", "счетов")}` : "выставленных счетов нет"}${b.n_overdue ? ` · срок прошёл: ${escH(dlSums(b.overdue))}` : ""}</span></div>`
    + `<div class="dl-stat${b.stuck ? " warn" : ""}"><small>Зависли</small><b>${b.stuck}</b><span>${b.stuck ? "без движения неделю и дольше" : "всё движется"}</span></div>`
    + `<div class="dl-stat ok"><small>Оплачено за 30 дней</small><b>${escH(dlSums(b.paid30))}</b><span><label class="dl-inc"><span class="tg"><input type="checkbox" id="dl-inc"${b.income ? " checked" : ""}><i></i></span>и в доходы «Денег»</label></span></div></div>`
    + (DL.adding ? dlAddHtml() : `<div class="dl-tools"><button class="btn primary dl-new" id="dl-new">+ Сделка</button><button class="btn" id="dl-csv" title="Все сделки — таблицей для Excel (Клиенты/Сделки ….csv)">Выгрузить в таблицу</button></div>`)
    + (DL.rem ? dlRemHtml(DL.rem) : "")
    + `<div class="dl-board">${b.cols.filter(c => c.stage !== "lost").map(c => `<div class="dl-col s-${c.stage}" role="group" aria-label="${escH(c.name)}">`
      + `<header><b>${escH(c.name)}${c.stage === "paid" ? " · 30 дней" : ""}</b><span>${c.items.length}</span></header><p class="dl-csum">${Object.keys(c.sum).length ? escH(dlSums(c.sum)) : "&nbsp;"}</p>`
      + (c.items.length ? c.items.map(dlCard).join("") : `<p class="dl-empty">${{ lead: "Новые заявки — голосом: «Ромашка хочет 200 коробок»", offer: "Отправили КП — здесь", invoice: "Счёт выставлен — ждём оплату", paid: "Оплаченное за месяц" }[c.stage]}</p>`)
      + `</div>`).join("")}</div>`
    + (lost.length ? `<p class="dl-lost">Отказы за 30 дней: ${lost.map(d => `${escH(d.client)} — «${escH(d.title)}»`).join("; ")}</p>` : "")
    + (!b.cols.some(c => c.items.length) ? `<p class="hint dl-hint">Скажите Лире: «Ромашке выставили счёт на 1200 за коробки, оплатить до пятницы» — сделка появится в «Счёт». «Кто нам должен?» — ответит.</p>` : "");
  dlBind();
}
function dlCard(d) {
  const open = DL.open === d.id;
  const flag = d.overdue ? `<em class="late">срок прошёл ${escH(dlDate(d.due))}</em>` : d.stuck ? `<em class="warn">без движения ${d.days} дн.</em>`
    : d.stage === "invoice" && d.due ? `<em>до ${escH(dlDate(d.due))}</em>` : "";
  const acts = !open ? "" : `<div class="dl-acts">${DL_NEXT[d.stage] ? `<button class="btn small primary" data-st="${DL_NEXT[d.stage]}">${DL_NEXT_TXT[d.stage]}</button>` : ""}`
    + Object.keys(DL_ST).filter(s => s !== d.stage && s !== DL_NEXT[d.stage]).map(s => `<button class="btn small" data-st="${s}">${DL_ST[s]}</button>`).join("")
    + (d.stage === "invoice" ? `<button class="btn small${d.overdue ? " primary" : ""}" data-rem>Напомнить об оплате</button>` : "")
    + `<button class="btn small ghost" data-edit>Сумма и срок</button><button class="btn small ghost" data-cl>Клиент</button><button class="btn small ghost danger" data-del>Удалить</button></div>`;
  const rem = d.reminded ? `<em class="rem">напомнили ${escH(new Date(d.reminded * 1000).toLocaleDateString("ru-RU", { day: "numeric", month: "long" }))}</em>` : "";
  return `<div class="dl-card${open ? " open" : ""}${d.overdue ? " late" : ""}" data-id="${escH(d.id)}" data-cid="${escH(d.cid)}"><button class="dl-tap" aria-expanded="${open}">`
    + `<b>${escH(d.title)}</b><span>${escH(d.client)}</span><span class="dl-amt">${d.amount ? escH(dlMoney(d.amount, d.cur)) : "сумма не указана"}</span>${flag}${rem}</button>${acts}</div>`;
}
/* «Напомнить об оплате»: черновик письма — правится здесь; «Отправить письмом» (почта подключена) или «Скопировать» */
function dlRemHtml(r) {
  return `<div class="dl-rem" id="dl-rem"><h3>Напомнить об оплате — ${escH(r.name || "")}</h3><label class="f"><span>Кому</span><input id="dl-rto" type="email" placeholder="почта клиента" value="${escH(r.to)}"></label>`
    + `<label class="f"><span>Тема</span><input id="dl-rsub" type="text" value="${escH(r.subject)}"></label>`
    + `<label class="f"><span>Письмо</span><textarea id="dl-rbody" rows="10">${escH(r.body)}</textarea></label>`
    + `<div class="actions" style="margin:6px 0 0">${r.mail ? `<button class="btn primary small" id="dl-rsend">Отправить письмом</button>` : ""}<button class="btn small${r.mail ? "" : " primary"}" id="dl-rcopy">Скопировать</button><button class="btn small ghost" id="dl-rx">Отмена</button></div>`
    + (r.mail ? "" : `<p class="hint" style="margin:6px 0 0">Почта не подключена — скопируйте текст в мессенджер клиента. Подключить: «Подключение» → «Почта».</p>`) + `</div>`;
}
function dlAddHtml() {
  const opts = (CR.list || []).map(c => `<option value="${escH(c.id)}">${escH(c.name)}${c.company && c.company !== c.name ? " («" + escH(c.company) + "»)" : ""}</option>`).join("");
  return `<form class="dl-add" id="dl-add"><select id="dl-cl" aria-label="Клиент">${opts || `<option value="">Сначала добавьте клиента</option>`}</select>`
    + `<input id="dl-t" maxlength="160" placeholder="Что продаём: коробки 200 шт" aria-label="Сделка"><input id="dl-a" inputmode="decimal" placeholder="Сумма" aria-label="Сумма">`
    + `<select id="dl-s" aria-label="Этап">${["lead", "offer", "invoice", "paid"].map(s => `<option value="${s}">${DL_ST[s]}</option>`).join("")}</select>`
    + `<input id="dl-d" type="date" aria-label="Оплатить до" title="Оплатить до (для счёта)"><button class="btn primary" type="submit">Добавить</button><button class="btn ghost" type="button" id="dl-x">Отмена</button></form>`;
}
function dlBind() {
  const nw = $("#dl-new"); if (nw) nw.onclick = async () => { if (!(CR.list || []).length) await crLoadList(); DL.adding = true; dlRender(); const t = $("#dl-t"); if (t) t.focus(); };
  const x = $("#dl-x"); if (x) x.onclick = () => { DL.adding = false; dlRender(); };
  const f = $("#dl-add"); if (f) f.onsubmit = async (e) => { e.preventDefault();
    const cid = $("#dl-cl").value; if (!cid) return toast("Сначала добавьте клиента — вкладка «Клиенты»");
    try { await core.call("client_deal_add", { id: cid, title: $("#dl-t").value.trim(), amount: $("#dl-a").value.trim(), stage: $("#dl-s").value, due: $("#dl-d").value });
      DL.adding = false; toast("Сделка добавлена"); dlLoad(); } catch (er) { toast(er.message, 3500); } };
  const inc = $("#dl-inc"); if (inc) inc.onchange = () => core.call("clients_deal_income", { on: inc.checked }).then(r => { DL.board = r; toast(inc.checked ? "Оплаченное — сразу в доходы" : "Оплаченное в доходы не пишется"); }).catch(e => toast(e.message));
  $$("#dl-wrap .dl-tap").forEach(b => b.onclick = () => { const id = b.closest(".dl-card").dataset.id; DL.open = DL.open === id ? "" : id; dlRender(); });
  $$("#dl-wrap .dl-card [data-st]").forEach(b => b.onclick = async () => {
    const c = b.closest(".dl-card");
    try { await core.call("client_deal_set", { id: c.dataset.cid, did: c.dataset.id, stage: b.dataset.st });
      toast(b.dataset.st === "paid" ? (DL.board.income ? "Оплачено — записала в доходы" : "Оплачено") : `→ ${DL_ST[b.dataset.st]}`); DL.open = ""; dlLoad(); }
    catch (e) { toast(e.message, 3500); }
  });
  $$("#dl-wrap .dl-card [data-edit]").forEach(b => b.onclick = async () => {
    const c = b.closest(".dl-card"), d = DL.board.cols.flatMap(x => x.items).find(x => x.id === c.dataset.id);
    const amt = await askText("Сумма сделки", d.amount ? String(d.amount) : "", { ok: "Дальше" }); if (amt === null || amt === undefined) return;
    const due = await askText("Оплатить до (например: 2026-11-05, «до пятницы»; пусто — без срока)", d.due || "", { ok: "Сохранить" }); if (due === null || due === undefined) return;
    try { await core.call("client_deal_set", { id: c.dataset.cid, did: c.dataset.id, amount: amt, due }); dlLoad(); } catch (e) { toast(e.message, 3500); }
  });
  $$("#dl-wrap .dl-card [data-rem]").forEach(b => b.onclick = async () => {
    const c = b.closest(".dl-card");
    try { DL.rem = Object.assign(await core.call("client_deal_remind", { id: c.dataset.cid, did: c.dataset.id }), { did: c.dataset.id, cid: c.dataset.cid }); dlRender(); const t = $("#dl-rbody"); if (t) t.focus(); }
    catch (e) { toast(e.message, 3500); }
  });
  const rx = $("#dl-rx"); if (rx) rx.onclick = () => { DL.rem = null; dlRender(); };
  const rs = $("#dl-rsend"); if (rs) rs.onclick = async () => { rs.disabled = true;
    try { await core.call("client_deal_remind_send", { id: DL.rem.cid, did: DL.rem.did, to: $("#dl-rto").value.trim(), subject: $("#dl-rsub").value, body: $("#dl-rbody").value });
      toast("Напоминание отправлено — отметила в истории клиента", 3500); DL.rem = null; DL.open = ""; dlLoad(); }
    catch (e) { toast(e.message, 4500); rs.disabled = false; } };
  const rc = $("#dl-rcopy"); if (rc) rc.onclick = async () => {
    try { await navigator.clipboard.writeText($("#dl-rbody").value); } catch (e) { }
    await core.call("client_deal_remind_send", { id: DL.rem.cid, did: DL.rem.did, how: "copy" }).catch(() => { });
    toast("Текст скопирован — вставьте в мессенджер клиента", 3500); DL.rem = null; DL.open = ""; dlLoad(); };
  const cv = $("#dl-csv"); if (cv) cv.onclick = async () => {
    try { const r = await core.call("clients_deals_export"); toast(`Сделок: ${r.n} — «${r.path}»`, 4000); core.call("ws_open", { path: r.path }).catch(() => { }); }
    catch (e) { toast(e.message, 3500); } };
  $$("#dl-wrap .dl-card [data-cl]").forEach(b => b.onclick = () => { CR.cur = b.closest(".dl-card").dataset.cid; dlTab("list"); });
  $$("#dl-wrap .dl-card [data-del]").forEach(b => b.onclick = async () => {
    const c = b.closest(".dl-card"); if (!await ask("Удалить сделку? В истории клиента записи останутся.", { ok: "Удалить", danger: true })) return;
    try { await core.call("client_deal_del", { id: c.dataset.cid, did: c.dataset.id }); DL.open = ""; dlLoad(); } catch (e) { toast(e.message); }
  });
}
/* в карточке клиента — его сделки (clients.js crCard) */
function dlClientHtml(c) {
  const ds = (c.deals || []).slice().reverse();
  return `<div class="cr-deals"><h3>Сделки</h3>${ds.length ? `<ul>${ds.map(d => `<li class="s-${escH(d.stage)}"><b>${escH(d.title)}</b>`
      + `<span>${d.amount ? escH(dlMoney(d.amount, d.cur)) : ""}${d.stage === "invoice" && d.due ? ` · до ${escH(dlDate(d.due))}` : ""}</span>`
      + `<select data-did="${escH(d.id)}" aria-label="Этап сделки">${Object.entries(DL_ST).map(([k, v]) => `<option value="${k}"${k === d.stage ? " selected" : ""}>${v}</option>`).join("")}</select></li>`).join("")}</ul>` : ""}`
    + `<form class="cr-dform" id="cr-dform"><input id="cr-dt" maxlength="160" placeholder="Новая сделка: что продаём"><input id="cr-da" inputmode="decimal" placeholder="Сумма"><button class="btn small" type="submit">+ Сделка</button></form></div>`;
}
function dlClientBind(c) {
  $$(".cr-deals select[data-did]").forEach(s => s.onchange = async () => {
    try { CR.card = await core.call("client_deal_set", { id: c.id, did: s.dataset.did, stage: s.value }); crCard(); toast(s.value === "paid" ? "Оплачено" : `→ ${DL_ST[s.value]}`); }
    catch (e) { toast(e.message, 3500); }
  });
  const f = $("#cr-dform"); if (f) f.onsubmit = async (e) => { e.preventDefault();
    const t = $("#cr-dt").value.trim(); if (!t) return $("#cr-dt").focus();
    try { CR.card = await core.call("client_deal_add", { id: c.id, title: t, amount: $("#cr-da").value.trim(), stage: "lead" }); crCard(); toast("Сделка добавлена — этап «Заявка»"); }
    catch (er) { toast(er.message, 3500); } };
}
if ($("#cr-tabs")) $$("#cr-tabs button").forEach(b => b.onclick = () => dlTab(b.dataset.t));
