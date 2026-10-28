/* Студия Dewiar, раздел «Семья» (27.10, по макету «Dewiar — новые режимы», экран Budget): общий бюджет с близкими.
   Ядро: fam_get (+ people — кого можно позвать из «Близких»), fam_invite/fam_accept/fam_leave {pid},
   fam_bill {name, amount, due, payer}, fam_paid {id, paid}, fam_bill_del {id}, fam_remind {id}, fam_limit {v},
   fam_share {on}; событие «family». Сами траты пишутся как обычно — в «Деньгах» или голосом (money.on_add → family). */
let FM = null;
const FM_COL = ["#8a9bff", "#ffc978", "#7ee8c8", "#ff9fb8", "#b7a0ff", "#9fd6ff"];
const FM_MON = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"];
const FM_MONTH = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"];
const fmNum = (n) => Number(n || 0).toLocaleString("ru-RU", { minimumFractionDigits: Number(n) % 1 ? 2 : 0, maximumFractionDigits: 2 });
const fmDay = (iso) => iso ? `${+iso.slice(8, 10)} ${FM_MON[+iso.slice(5, 7) - 1]}` : "";
const fmTime = (ts) => { const d = new Date(ts); return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`; };
const fmCur = () => { const c = (FM && FM.currency) || ""; return (typeof CUR_SIGN !== "undefined" && CUR_SIGN[c]) || c; };
function fmColor(pid) {                                   // цвет человека — по порядку в семье, «я» всегда первый
  const order = [""].concat((FM.members || []).filter(m => m.st === "joined").map(m => m.pid));
  const i = order.indexOf(pid); return FM_COL[(i < 0 ? order.length : i) % FM_COL.length];
}
/* Аватар человека (28.10, владелец: «аватарки грубовато смотрятся… поприятнее и попонятнее»): мягкий градиент его
   цвета, белая буква, светлая кромка вместо тёмной обводки; кто ещё не принял — пунктиром и бледнее. */
const fmAva = (name, pid, size) => `<span class="fm-ava${size ? " " + size : ""}" style="--c:${fmColor(pid)}" aria-hidden="true">${escH((name || "?").trim()[0] || "?").toUpperCase()}</span>`;

function fmRender() {
  const d = FM;
  if (!d || !d.month || !$("#p-family")) return;
  $("#fam-dot").classList.toggle("on", (d.members || []).some(m => m.st === "asked"));
  // месяц: итог, лимит, полоса по людям
  const mi = +d.month.slice(5, 7) - 1, lim = +d.limit || 0, base = Math.max(lim, d.total) || 1;
  const by = d.by.filter(v => v.sum > 0 || v.pid === "" || (d.members || []).some(m => m.pid === v.pid && m.st === "joined"));
  const over = lim && d.total > lim;
  $("#fm-month").innerHTML = `<div class="fm-mh"><div><small>Семья</small><h2>${FM_MONTH[mi]}</h2></div>`
    + (by.length > 1 ? `<div class="fm-stack" title="${escH(by.map(v => v.pid ? v.name : d.me).join(", "))}">${by.map(v => fmAva(v.pid ? v.name : d.me, v.pid)).join("")}</div>` : "") + `</div>`
    + `<div class="fm-total"><b>${fmNum(d.total)} <span>${escH(fmCur())}</span></b>`
    + `<label class="fm-lim">${lim ? (over ? `больше лимита на ${fmNum(d.total - lim)}` : `из ${fmNum(lim)} на месяц`) : "лимит на месяц"}`
    + `<input type="number" id="fm-limit" min="0" step="10" value="${lim || ""}" placeholder="не задан" aria-label="Лимит на месяц"></label></div>`
    + `<div class="fm-bar${over ? " over" : ""}" role="img" aria-label="${escH(by.map(v => `${v.pid ? v.name : "Я"} ${fmNum(v.sum)}`).join(", ") + (lim && !over ? `, остаток ${fmNum(lim - d.total)}` : ""))}">`
    + by.filter(v => v.sum > 0).map(v => `<i style="width:${(v.sum / base * 100).toFixed(2)}%;background:${fmColor(v.pid)}"></i>`).join("") + `</div>`
    + `<div class="fm-by">${by.map(v => `<div><span><i style="background:${fmColor(v.pid)}"></i>${escH(v.pid ? v.name : "Я")}</span><b>${fmNum(v.sum)}</b></div>`).join("")}</div>`
    + (d.active ? "" : `<p class="fm-note">Пока это только ваши траты. Пригласите близких — справа.</p>`);
  $("#fm-limit").onchange = () => fmCall("fam_limit", { v: +$("#fm-limit").value || 0 }, "Лимит сохранён — у всей семьи");
  // кто в семье
  const st = { invited: "ждём ответа", asked: "приглашает вас", joined: "в семье" };
  $("#fm-people").innerHTML = `<li>${fmAva(d.me, "")}<div><b>${escH(d.me)}</b><small>это вы</small></div></li>`
    + (d.members || []).map(m => `<li class="${m.st}">${fmAva(m.name, m.pid)}<div><b>${escH(m.name)}</b><small>${st[m.st] || ""}</small></div>`
      + (m.st === "asked" ? `<button class="btn small primary" data-acc="${escH(m.pid)}">Принять</button><button class="btn small" data-out="${escH(m.pid)}">Отказаться</button>`
        : `<button class="btn small" data-out="${escH(m.pid)}">${m.st === "joined" ? "Убрать" : "Отменить"}</button>`) + `</li>`).join("");
  $$("#fm-people [data-acc]").forEach(b => b.onclick = () => fmCall("fam_accept", { pid: b.dataset.acc }, "Вы в общем бюджете"));
  $$("#fm-people [data-out]").forEach(b => b.onclick = () => fmCall("fam_leave", { pid: b.dataset.out }));
  const taken = new Set((d.members || []).map(m => m.pid)), free = (d.people || []).filter(p => !taken.has(p.pid));
  $("#fm-pick").innerHTML = free.length ? free.map(p => `<option value="${escH(p.pid)}">${escH(p.name)}</option>`).join("")
    : `<option value="">${(d.people || []).length ? "все близкие уже приглашены" : "в «Близких» пока никого"}</option>`;
  $("#fm-inv-note").textContent = (d.people || []).length ? "Приглашение уходит сообщением в «Близких». Когда человек примет — траты и платежи станут общими."
    : "Пригласить можно тех, кто есть в «Близких»: сначала добавьте человека там.";
  $("#fm-share").checked = d.share !== false;
  // общие платежи: неоплаченные — сверху, с «Оплачено» и «Напомнить»
  const joinedNames = new Set((d.members || []).filter(m => m.st === "joined").map(m => m.name));
  $("#fm-bills").innerHTML = (d.bills || []).length ? d.bills.map(b => {
    const paid = !!b.paid_by, late = !paid && b.due && b.due < new Date().toISOString().slice(0, 10);
    const sub = paid ? `оплатил(а) ${escH(b.paid_by)}, ${fmDay(new Date(b.paid_at).toISOString().slice(0, 10))}`
      : [b.due ? `до ${fmDay(b.due)}` : "", b.payer ? `платит ${escH(b.payer)}` : ""].filter(Boolean).join(", ") || "кто платит — не выбрано";
    return `<li class="${paid ? "paid" : late ? "late" : "due"}"><span class="fm-ic" aria-hidden="true">${paid
      ? '<svg viewBox="0 0 24 24"><path d="M5 12l5 5L19 7"/></svg>' : '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8"/><path d="M12 8v4l2 2"/></svg>'}</span>`
      + `<div><b>${escH(b.name)}</b><small>${sub}</small></div>${b.amount ? `<b class="fm-amt">${fmNum(b.amount)}</b>` : ""}`
      + (paid ? `<button class="btn small" data-unpaid="${escH(b.id)}">Не оплачено</button>`
        : `<button class="btn small primary" data-paid="${escH(b.id)}">Оплачено</button>`
          + (joinedNames.has(b.payer) ? `<button class="btn small" data-rem="${escH(b.id)}">Напомнить</button>` : ""))
      + `<button class="fm-x" data-del="${escH(b.id)}" aria-label="Удалить «${escH(b.name)}»" title="Удалить">×</button></li>`;
  }).join("") : `<li class="fm-empty">Свет, газ, интернет — добавьте, кто и до какого числа платит. «Оплачено» увидят все.</li>`;
  $$("#fm-bills [data-paid]").forEach(b => b.onclick = () => fmCall("fam_paid", { id: b.dataset.paid, paid: true }, "Отмечено: оплачено"));
  $$("#fm-bills [data-unpaid]").forEach(b => b.onclick = () => fmCall("fam_paid", { id: b.dataset.unpaid, paid: false }));
  $$("#fm-bills [data-rem]").forEach(b => b.onclick = () => fmCall("fam_remind", { id: b.dataset.rem }, "Напоминание отправлено"));
  $$("#fm-bills [data-del]").forEach(b => b.onclick = () => fmCall("fam_bill_del", { id: b.dataset.del }, "Платёж удалён"));
  const payers = [d.me].concat([...joinedNames]), cur = $("#fm-bpayer").value;
  $("#fm-bpayer").innerHTML = payers.map(n => `<option>${escH(n)}</option>`).join("");
  if (payers.includes(cur)) $("#fm-bpayer").value = cur;
  // траты: сегодня, а если сегодня пусто — последние за месяц
  const list = (d.feed || []).length ? d.feed : (d.recent || []).slice(0, 10);
  $("#fm-feed").previousElementSibling.textContent = (d.feed || []).length ? "Сегодня" : "Последние траты";
  $("#fm-feed").innerHTML = list.length ? list.map(x => {
    const nm = x.who ? x.name : d.me, what = x.note || x.cat || "Расход";
    const when = x.date === new Date().toISOString().slice(0, 10) ? fmTime(x.ts) : fmDay(x.date);
    return `<li>${fmAva(nm, x.who || "", "sm")}<div><b>${escH(what[0].toUpperCase() + what.slice(1))}</b>`
      + `<small>${x.said ? `голосом: «${escH(x.said)}», ` : ""}${escH(x.who ? nm + ", " : "")}${when}</small></div><b class="fm-amt">${fmNum(x.amount)}</b></li>`;
  }).join("") : `<li class="fm-empty">Скажите «продукты 46,20» или запишите расход в «Деньгах» — он появится здесь.</li>`;
}
async function fmCall(cmd, args, ok) {
  try { FM = Object.assign(FM || {}, await core.call(cmd, args)); if (ok) toast(ok, 2500); }
  catch (e) { toast(e.message, 4000); }
  fmRender();
}
async function fmLoad() {
  try { FM = await core.call("fam_get"); } catch (e) { return; }
  fmRender();
}
window.loadFamily = fmLoad;
if ($("#p-family")) {
  $("#fm-invite").onclick = () => $("#fm-pick").value ? fmCall("fam_invite", { pid: $("#fm-pick").value }, "Приглашение отправлено")
    : toast((FM && (FM.people || []).length) ? "Все близкие уже приглашены" : "Сначала добавьте человека в «Близких»", 3500);
  $("#fm-share").onchange = () => fmCall("fam_share", { on: $("#fm-share").checked });
  $("#fm-add").onsubmit = (e) => {
    e.preventDefault();
    const name = $("#fm-bname").value.trim();
    if (!name) { toast("Назовите платёж: свет, газ, интернет…", 3000); $("#fm-bname").focus(); return; }
    fmCall("fam_bill", { name, amount: +$("#fm-bamt").value || 0, due: $("#fm-bdue").value, payer: $("#fm-bpayer").value }, "Платёж добавлен");
    $("#fm-bname").value = ""; $("#fm-bamt").value = ""; $("#fm-bdue").value = "";
  };
  core.on("family", (e) => { const people = FM && FM.people; FM = Object.assign({}, e, { people: people || [] }); fmRender(); });
  core.on("hello", () => fmLoad());
}
