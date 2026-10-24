/* Студия Dewiar: раздел «Календарь» (месяц, деньги, лента), окно установки обновления, «Dewiar на телефоне» (QR-коды),
   умный дом Яндекса и подключённые календари Google/Яндекс (ссылки iCal).
   Команды ядра: calendar_month, money_summary/list/add/delete, reminder_add/cancel, phone_config,
   home_connect/refresh/forget, cal_add/remove/toggle; события money_saved, reminders, note_saved (перерисовка
   календаря) и calendars. Ход установки обновления спрашиваем у окна (api().update_progress), а не у ядра: установку
   ведёт ui/app.py, ядро на это время останавливается или перезапускается.
   Файлы студии подключаются по порядку из ui/settings.html и делят одну глобальную область: qrPretty отсюда нужен
   links.js и dewiar.js, phFill/shFill/csFill зовёт dewiar.js после связи с ядром; escH, SVG, I_DEL — из файлов ниже,
   но нужны только при отрисовке. */
/* ---------- календарь, деньги, список ---------- */
const CT = { event: ["Встречи", "#4FC3FF"], reminder: ["Напоминания", "#FFC978"], money: ["Деньги", "#4BE3A1"], note: ["Заметки", "#8B8CF7"],
             diary: ["Дневник", "#5EE0B5"], task: ["Задачи", "#FF7AB6"] };
const MON_RU = ["январь", "февраль", "март", "апрель", "май", "июнь", "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь"];
const CUR_SIGN = { BYN: "руб.", RUB: "₽", USD: "$", EUR: "€", PLN: "zł", UAH: "₴", KZT: "₸", CNY: "¥" };
let calY = null, calM = null, calSel = "", calData = null, calOff = new Set(), calTab = "month", moPer = "month";
const isoD = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const parseD = (s) => { const [y, m, d] = s.split("-").map(Number); return new Date(y, m - 1, d); };
function fmtMoney(n, cur) {
  const s = Number(n).toLocaleString("ru-RU", { minimumFractionDigits: Number(n) % 1 ? 2 : 0, maximumFractionDigits: 2 });
  return `${s} ${CUR_SIGN[cur] || cur || ""}`.trim();
}
const itemColor = (it) => it.type === "money" ? (it.kind === "income" ? "#4BE3A1" : "#FF8FA8") : it.type === "event" && it.color ? it.color : (CT[it.type] || ["", "#aaa"])[1];
function itemText(it) {
  if (it.type === "money") return `${it.kind === "income" ? "+" : "−"}${fmtMoney(it.amount, it.currency)} ${it.title || ""}`;
  return `${it.time && (it.type === "reminder" || it.type === "event") ? it.time + " " : ""}${it.title || ""}`;
}
let calReq = 0;
async function loadCalendar() {
  if (calY === null) { const d = new Date(); calY = d.getFullYear(); calM = d.getMonth() + 1; calSel = isoD(d); }
  // GitHub #19 (24.10): ядро отвечает параллельно, и поздний ответ за ноябрь затирал октябрь выбранного 31-го —
  // «ничего нет». Применяем только ответ на последний запрос.
  const my = ++calReq;
  let d;
  try { d = await core.call("calendar_month", { year: calY, month: calM }); }
  catch (e) { if (my === calReq) $("#cal-grid").textContent = e.message; return; }
  if (my !== calReq) return;
  calData = d;
  renderCalFilter(); renderCal(); renderSide(); if (calTab === "feed") renderFeed();
  if (calTab === "money") loadMoney();
  if ($("#day-dlg").open) renderDay();
  sideWidth();
}
function renderCalFilter() {
  $("#cal-filter").innerHTML = Object.entries(CT).map(([k, [n, c]]) => `<button data-k="${k}" class="${calOff.has(k) ? "off" : ""}"><i style="background:${c}"></i>${n}</button>`).join("");
  $$("#cal-filter button").forEach(b => b.onclick = () => { const k = b.dataset.k; calOff.has(k) ? calOff.delete(k) : calOff.add(k); renderCalFilter(); renderCal(); renderSide(); if (calTab === "feed") renderFeed(); });
}
function dayItems(d) { return ((calData && calData.days[d]) || []).filter(it => !calOff.has(it.type)); }
function renderCal() {
  $("#cal-title").textContent = `${MON_RU[calM - 1]} ${calY}`;
  const first = new Date(calY, calM - 1, 1), off = (first.getDay() + 6) % 7, n = new Date(calY, calM, 0).getDate();
  const rows = Math.ceil((off + n) / 7), today = isoD(new Date());
  let html = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"].map(w => `<div class="wd">${w}</div>`).join("");
  const CAL_N = Math.max(4, Math.min(8, Math.floor((window.innerHeight - 380) / 5 / 17) - 1));   // высокий экран — больше дел в клетке
  for (let i = 0; i < rows * 7; i++) {
    const d = new Date(calY, calM - 1, 1 - off + i), k = isoD(d), inM = d.getMonth() === calM - 1;
    const its = inM ? dayItems(k) : [];
    // сумма дня в клетке — только в основной валюте (calData.currency), разные валюты не складываем
    let inc = 0, exp = 0; its.forEach(it => { if (it.type === "money" && it.currency === (calData.currency || it.currency)) it.kind === "income" ? inc += it.amount : exp += it.amount; });
    const sum = exp ? `<em style="color:#FFB3C3">−${Math.round(exp)}</em>` : inc ? `<em style="color:var(--good)">+${Math.round(inc)}</em>` : "";
    const evs = its.filter(it => it.type !== "money" || its.filter(x => x.type === "money").length <= 2);   // много трат — только сумма, без строк
    html += `<div class="day${inM ? "" : " out"}${k === today ? " today" : ""}${k === calSel ? " sel" : ""}" data-d="${k}"><div class="n"><b>${d.getDate()}</b>${sum}</div>` +
      evs.slice(0, CAL_N).map(it => `<div class="ev${it.done ? " done" : ""}" title="${escH(itemText(it))}"><i style="background:${itemColor(it)}"></i><span>${escH(it.type === "money" ? itemText(it) : it.title || "")}</span></div>`).join("") +
      (evs.length > CAL_N ? `<div class="more">ещё ${evs.length - CAL_N}</div>` : "") + `</div>`;
  }
  $("#cal-grid").innerHTML = html;
  $$("#cal-grid .day").forEach(el => el.onclick = () => {
    const d = el.dataset.d; calSel = d;
    if (el.classList.contains("out")) { const x = parseD(d); calY = x.getFullYear(); calM = x.getMonth() + 1; loadCalendar(); return; }
    $$("#cal-grid .day").forEach(x => x.classList.toggle("sel", x === el)); renderSide();
    openDay(d);                                                       // 24.10: день — крупно, поверх месяца
  });
}
function itemRow(it, withDate) {
  const el = document.createElement("div"); el.className = "cit";
  const sub = it.type === "money" ? it.category : it.type === "reminder" ? (it.done ? "прозвенело" : (it.repeat ? "повторяется" : "напоминание")) + (it.time ? " · " + it.time : "")
    : it.type === "event" ? (it.time ? `${it.time}–${it.end}` : "весь день") + " · " + (it.cal || "календарь") + (it.place ? " · " + it.place : "")
    : it.type === "note" ? "заметка" : it.type === "diary" ? "дневник ассистента" : "задача" + (it.status ? " · " + it.status.toLowerCase() : "");
  el.innerHTML = `<i style="background:${itemColor(it)}"></i><div class="t"><span></span><small></small></div>`;
  $(".t span", el).textContent = it.type === "money" ? (it.title || it.category) : it.title || "";
  $(".t small", el).textContent = (withDate ? parseD(withDate).toLocaleDateString("ru-RU", { day: "numeric", month: "short" }) + " · " : "") + sub;
  if (it.type === "money") el.insertAdjacentHTML("beforeend", `<span class="amt ${it.kind === "income" ? "inc" : "exp"}">${it.kind === "income" ? "+" : "−"}${escH(fmtMoney(it.amount, it.currency))}</span>`);
  if ((it.type === "money" || (it.type === "reminder" && !it.done && !it.repeat)) && it.id) {
    const x = document.createElement("button"); x.className = "x"; x.title = "Удалить"; x.textContent = "✕";
    x.onclick = async (ev) => { ev.stopPropagation();
      try { await core.call(it.type === "money" ? "money_delete" : "reminder_cancel", { id: it.id }); loadCalendar(); } catch (e) { toast(e.message); } };
    el.appendChild(x);
  }
  if (it.path) { el.classList.add("link"); el.onclick = () => { $('nav button[data-p="folder"]').click(); setTimeout(() => openFile(it.path), 250); }; }
  if (it.type === "task" && it.id) { el.classList.add("link"); el.onclick = () => { $('nav button[data-p="tasks"]').click(); setTimeout(() => openTask(it.id), 300); }; }
  return el;
}
function renderSide() {
  const side = $("#cal-side"), d = calSel; if (!d) { side.innerHTML = ""; return; }
  const its = dayItems(d), dt = parseD(d);
  // id не cs-list: так называется список подключённых календарей в настройках (csFill), а $ берёт первый в DOM
  side.innerHTML = `<h3><button class="linkb" id="cs-open" title="Открыть день крупно">${dt.toLocaleDateString("ru-RU", { weekday: "long", day: "numeric", month: "long" })}</button></h3><div id="cs-day"></div>
    <div class="k" style="margin-top:14px">Добавить на этот день</div>${addForm("cs")}<i class="calgrip" id="cal-grip" title="Потяните, чтобы сделать шире"></i>`;
  const box = $("#cs-day");
  if (!its.length) box.innerHTML = `<p class="hint">В этот день ничего нет.</p>`;
  its.forEach(it => box.appendChild(itemRow(it)));
  $("#cs-open").onclick = () => openDay(d);
  bindAdd("cs", d); bindGrip();
}
/* «Добавить на этот день»: напоминание и деньги — в столбце справа (cs) и в окне дня (dd) */
function addForm(p, wide) {
  if (wide) return `<div class="qadd wide">
      <div class="row2"><input type="time" id="${p}-time" value="10:00"><input type="text" id="${p}-text" placeholder="напомнить: позвонить Лёше" class="grow"><button class="btn small" id="${p}-rem">Напомнить</button></div>
      <div class="row2"><select id="${p}-kind"><option value="expense">Расход</option><option value="income">Доход</option></select><input type="number" id="${p}-amount" placeholder="сумма" min="0" step="0.01"><input type="text" id="${p}-note" placeholder="на что (кофе, такси…)" class="grow"><button class="btn small" id="${p}-money">Записать</button></div>
    </div>`;
  return `<div class="qadd">
      <div class="row2"><input type="time" id="${p}-time" value="10:00"><input type="text" id="${p}-text" placeholder="напомнить: позвонить Лёше"></div>
      <button class="btn small" id="${p}-rem">Напомнить</button>
      <div class="row2"><select id="${p}-kind"><option value="expense">Расход</option><option value="income">Доход</option></select><input type="number" id="${p}-amount" placeholder="сумма" min="0" step="0.01"></div>
      <input type="text" id="${p}-note" placeholder="на что (кофе, такси, зарплата…)">
      <button class="btn small" id="${p}-money">Записать деньги</button>
    </div>`;
}
function bindAdd(p, d) {
  $(`#${p}-rem`).onclick = async () => {
    const t = $(`#${p}-text`).value.trim(), tm = $(`#${p}-time`).value || "10:00"; if (!t) return $(`#${p}-text`).focus();
    if (new Date(`${d}T${tm}`) <= new Date()) return toast("Это время уже прошло — выберите позже");
    try { await core.call("reminder_add", { at: `${d} ${tm}`, text: t }); toast("Напоминание добавлено"); loadCalendar(); } catch (e) { toast(e.message); }
  };
  $(`#${p}-money`).onclick = async () => {
    const amt = parseFloat(($(`#${p}-amount`).value || "").replace(",", ".")); if (!(amt > 0)) return $(`#${p}-amount`).focus();
    try { await core.call("money_add", { kind: $(`#${p}-kind`).value, amount: amt, note: $(`#${p}-note`).value.trim(), date: d }); toast("Записано"); loadCalendar(); }
    catch (e) { toast(e.message); }
  };
}
/* Правый столбец тянется мышью за левый край (владелец 24.10: «пытаюсь сделать блок справа больше»); ширина — ui.cal_side_w.
   Месяц при этом не сжимается мельче читаемого: столбец 260…560 px. */
const SIDE_MIN = 260, SIDE_MAX = 560;
function sideWidth(w) {
  w = Math.round(Math.min(SIDE_MAX, Math.max(SIDE_MIN, w || (S && S.ui && S.ui.cal_side_w) || 290)));
  const wrap = $(".calwrap"); if (wrap) wrap.style.setProperty("--side", w + "px");
  return w;
}
function bindGrip() {
  const g = $("#cal-grip"); if (!g) return;
  g.onpointerdown = (e) => {
    e.preventDefault(); g.setPointerCapture(e.pointerId); g.classList.add("on");
    const x0 = e.clientX, w0 = $("#cal-side").getBoundingClientRect().width; let w = w0;
    g.onpointermove = (m) => { w = sideWidth(w0 + (x0 - m.clientX)); };
    g.onpointerup = g.onpointercancel = () => { g.onpointermove = g.onpointerup = g.onpointercancel = null; g.classList.remove("on");
      S.ui = Object.assign({}, S.ui, { cal_side_w: w }); save({ ui: { cal_side_w: w } }, true); };
  };
  g.ondblclick = () => { S.ui = Object.assign({}, S.ui, { cal_side_w: 290 }); sideWidth(290); save({ ui: { cal_side_w: 290 } }, true); };
}
/* День крупно (владелец 24.10: «хочется нажать на день и просмотреть подробнее»): окно поверх месяца — сначала то, что по
   времени, потом задачи, заметки, дневник, деньги с итогом; текст целиком. ← → — соседние дни, Esc — назад к месяцу. */
const DAY_GROUPS = [["Задачи", (it) => it.type === "task"], ["Заметки", (it) => it.type === "note"], ["Дневник", (it) => it.type === "diary"]];
function openDay(d) {
  calSel = d; const dlg = $("#day-dlg");
  renderDay(); if (!dlg.open) dlg.showModal(); $("#dd-title").focus();
}
async function dayShift(n) {
  const x = parseD(calSel); x.setDate(x.getDate() + n); const k = isoD(x);
  calSel = k;
  if (x.getFullYear() !== calY || x.getMonth() + 1 !== calM) { calY = x.getFullYear(); calM = x.getMonth() + 1; await loadCalendar(); }
  else { renderCal(); renderSide(); renderDay(); }
}
function renderDay() {
  const d = calSel, dt = parseD(d), its = dayItems(d), body = $("#dd-body");
  $("#dd-title").textContent = dt.toLocaleDateString("ru-RU", { weekday: "long", day: "numeric", month: "long" });
  const today = isoD(new Date()), rel = d === today ? "сегодня" : d === isoD(new Date(Date.now() + 864e5)) ? "завтра" : d === isoD(new Date(Date.now() - 864e5)) ? "вчера" : String(dt.getFullYear());
  let inc = 0, exp = 0; its.forEach(it => { if (it.type === "money" && it.currency === (calData.currency || it.currency)) it.kind === "income" ? inc += it.amount : exp += it.amount; });
  const money = [exp ? "расход " + fmtMoney(exp, calData.currency) : "", inc ? "доход " + fmtMoney(inc, calData.currency) : ""].filter(Boolean).join(", ");
  // plural — из memory.js (файлы студии делят одну глобальную область)
  $("#dd-sub").textContent = [rel, its.length ? its.length + " " + plural(its.length, "запись", "записи", "записей") : "пока пусто", money].filter(Boolean).join(" · ");
  body.innerHTML = "";
  const sec = (title, list, timed) => {
    if (!list.length) return;
    // div, не section: section в студии — это страницы, они скрыты, пока не открыты
    const s = document.createElement("div"); s.className = "dd-sec"; s.innerHTML = `<div class="k">${title}</div>`;
    list.forEach(it => { const el = itemRow(it); el.classList.add("big");
      if (timed) el.insertAdjacentHTML("afterbegin", `<b class="tm">${escH(it.time || "")}</b>`);
      if (el.onclick && el.classList.contains("link")) { const go = el.onclick; el.onclick = (e) => { $("#day-dlg").close(); go(e); }; }
      s.appendChild(el); });
    body.appendChild(s);
  };
  const timed = its.filter(it => (it.type === "event" || it.type === "reminder") && it.time).sort((a, b) => a.time.localeCompare(b.time));
  sec("По времени", timed, true);
  sec("Весь день", its.filter(it => (it.type === "event" || it.type === "reminder") && !it.time));
  DAY_GROUPS.forEach(([t, f]) => sec(t, its.filter(f)));
  sec("Деньги", its.filter(it => it.type === "money"));
  if (!its.length) body.innerHTML = `<p class="dd-empty">В этот день ничего нет. Добавьте напоминание ниже или скажите Лире: «напомни ${d === today ? "сегодня" : dt.toLocaleDateString("ru-RU", { day: "numeric", month: "long" })} в 18:00 позвонить маме».</p>`;
  $("#dd-add").innerHTML = addForm("dd", true); bindAdd("dd", d);
}
$("#dd-prev").onclick = () => dayShift(-1);
$("#dd-next").onclick = () => dayShift(1);
$("#dd-x").onclick = () => $("#day-dlg").close();
$("#day-dlg").addEventListener("click", (e) => { if (e.target === e.currentTarget) e.currentTarget.close(); });   // щелчок мимо окна
$("#day-dlg").addEventListener("keydown", (e) => {
  if (/^(INPUT|SELECT|TEXTAREA)$/.test(e.target.tagName)) return;
  if (e.key === "ArrowLeft") { e.preventDefault(); dayShift(-1); } else if (e.key === "ArrowRight") { e.preventDefault(); dayShift(1); }
});
function renderFeed() {
  // «Сегодня и дальше» — от сегодня вперёд (повторяющееся напоминание — только ближайший раз), «Было» — назад от сегодня;
  // всё в пределах загруженного месяца (calData)
  const box = $("#cal-feed"); box.innerHTML = "";
  const today = isoD(new Date()), all = Object.keys((calData && calData.days) || {}).sort();
  const seen = new Set();
  const block = (title, days) => {
    let first = true;
    days.forEach(d => {
      const its = dayItems(d).filter(it => !(it.type === "reminder" && it.repeat && it.id && d >= today && seen.has(it.id) ) || false);
      its.forEach(it => { if (it.type === "reminder" && it.repeat && it.id) seen.add(it.id); });
      if (!its.length) return;
      if (first) { box.insertAdjacentHTML("beforeend", `<h2 style="margin:18px 0 4px">${title}</h2>`); first = false; }
      const h = document.createElement("div"); h.className = "feedday";
      h.textContent = d === today ? "Сегодня" : parseD(d).toLocaleDateString("ru-RU", { weekday: "long", day: "numeric", month: "long" });
      box.appendChild(h); its.forEach(it => box.appendChild(itemRow(it)));
    });
    return !first;
  };
  const a = block("Сегодня и дальше", all.filter(d => d >= today)), b = block("Было", all.filter(d => d < today).reverse());
  if (!a && !b) box.innerHTML = `<p class="hint">В этом месяце пока ничего нет.</p>`;
}
/* Период вкладки «Деньги» -> [с, по] в виде "ГГГГ-ММ-ДД"; текущие периоды заканчиваются сегодняшним днём */
function perRange(p) {
  const t = new Date(), d0 = new Date(t.getFullYear(), t.getMonth(), t.getDate());
  if (p === "today") return [isoD(d0), isoD(d0)];
  if (p === "week") { const s = new Date(d0); s.setDate(s.getDate() - (s.getDay() + 6) % 7); return [isoD(s), isoD(d0)]; }
  if (p === "prev") { const s = new Date(t.getFullYear(), t.getMonth() - 1, 1), e = new Date(t.getFullYear(), t.getMonth(), 0); return [isoD(s), isoD(e)]; }
  if (p === "year") return [`${t.getFullYear()}-01-01`, isoD(d0)];
  if (p === "custom") return [$("#mo-from").value || isoD(new Date(t.getFullYear(), t.getMonth(), 1)), $("#mo-to").value || isoD(d0)];
  return [isoD(new Date(t.getFullYear(), t.getMonth(), 1)), isoD(d0)];
}
const CAT_COL = ["#8B8CF7", "#FF8FA8", "#FFC978", "#5EE0B5", "#4FC3FF", "#B78CFF", "#FF7AB6", "#9FE870", "#F59E6B", "#7DD3FC"];
async function loadMoney() {
  const [f, t] = perRange(moPer);
  let sm, list;
  try { [sm, list] = await Promise.all([core.call("money_summary", { from: f, to: t }), core.call("money_list", { from: f, to: t })]); }
  catch (e) { $("#mo-cards").textContent = e.message; return; }
  const main = sm.by_currency.find(c => c.currency === (calData && calData.currency)) || sm.by_currency[0] || { currency: (calData && calData.currency) || "BYN", income: 0, expense: 0, balance: 0, expense_cats: [] };
  const others = sm.by_currency.filter(c => c !== main);
  const extra = (k) => others.filter(c => c[k]).map(c => fmtMoney(c[k], c.currency)).join(" · ");
  $("#mo-cards").innerHTML =
    `<div class="mocard inc"><span>Доходы</span><b>${fmtMoney(main.income, main.currency)}</b>${extra("income") ? `<small>и ${extra("income")}</small>` : ""}</div>` +
    `<div class="mocard exp"><span>Расходы</span><b>${fmtMoney(main.expense, main.currency)}</b>${extra("expense") ? `<small>и ${extra("expense")}</small>` : ""}</div>` +
    `<div class="mocard"><span>Остаток</span><b>${fmtMoney(main.balance, main.currency)}</b><small>${sm.count} ${plural(sm.count, "запись", "записи", "записей")}</small></div>`;
  const cats = main.expense_cats || [], mx = Math.max(1, ...cats.map(c => c.sum));
  $("#mo-cats").innerHTML = cats.length ? cats.map((c, i) => `<div class="mocat"><div><b>${escH(c.name)}</b><span>${fmtMoney(c.sum, main.currency)} · ${Math.round(100 * c.sum / Math.max(1, main.expense))}%</span></div>
      <div class="bar"><b style="width:${Math.max(2, 100 * c.sum / mx)}%;background:${CAT_COL[i % CAT_COL.length]}"></b></div></div>`).join("")
    : `<p class="hint">Расходов за этот период нет. Скажите «купил кофе за 8 рублей» — и появятся здесь.</p>`;
  // по дням: столбики расходов, доходы — в подсказке; больше 92 дней (квартал) столбики сливаются — не рисуем
  const a = parseD(f), b = moPer === "month" ? new Date(a.getFullYear(), a.getMonth() + 1, 0) : parseD(t),
        nd = Math.round((b - a) / 864e5) + 1, svg = $("#mo-days");
  if (nd > 1 && nd <= 92) {
    const vals = []; for (let i = 0; i < nd; i++) { const d = new Date(a); d.setDate(d.getDate() + i); const v = sm.days[isoD(d)] || { expense: 0, income: 0 }; vals.push([isoD(d), v.expense, v.income]); }
    const m = Math.max(1, ...vals.map(v => v[1])), w = 600 / Math.max(nd, 14);
    svg.innerHTML = vals.map(([d, e, inc], i) => { const h = e ? Math.max(3, 80 * e / m) : 1.5;
      return `<rect x="${i * w + 1}" y="${86 - h}" width="${Math.max(1, w - 2)}" height="${h}" rx="2" fill="${e ? "#FF8FA8" : "rgba(255,255,255,.08)"}"><title>${d}: −${e}${inc ? ", +" + inc : ""}</title></rect>`; }).join("");
    svg.style.display = "";
  } else svg.style.display = "none";
  const box = $("#mo-list"); box.innerHTML = "";
  if (!list.length) box.innerHTML = `<p class="hint">Операций нет.</p>`;
  list.slice(0, 200).forEach(x => box.appendChild(itemRow({ type: "money", id: x.id, kind: x.kind, amount: x.amount, currency: x.currency, title: x.note, category: x.category }, x.date)));
  const allCats = ["Продукты", "Кафе и рестораны", "Транспорт", "Дом и связь", "Здоровье", "Одежда", "Развлечения", "Подарки", "Техника", "Учёба",
                   "Красота и спорт", "Дети", "Животные", "Зарплата", "Аванс", "Премия", "Подработка", "Возврат", "Другое"];
  $("#mo-cats-list").innerHTML = allCats.map(c => `<option value="${c}">`).join("");
  if (!$("#mo-date").value) $("#mo-date").value = isoD(new Date());
}
$$("#cal-tabs button").forEach(b => b.onclick = () => {
  calTab = b.dataset.ct; $$("#cal-tabs button").forEach(x => x.classList.toggle("on", x === b));
  ["month", "money", "feed"].forEach(k => $("#ct-" + k).style.display = k === calTab ? "" : "none");
  if (calTab === "money") loadMoney(); if (calTab === "feed") renderFeed();
});

$$("#mo-per button").forEach(b => b.onclick = () => {
  moPer = b.dataset.per; $$("#mo-per button").forEach(x => x.classList.toggle("on", x === b));
  $("#mo-custom").style.display = moPer === "custom" ? "inline-flex" : "none"; loadMoney();
});
$("#mo-from").onchange = $("#mo-to").onchange = () => loadMoney();
$("#mo-add").onclick = async () => {
  const amt = parseFloat(($("#mo-amount").value || "").replace(",", ".")); if (!(amt > 0)) return $("#mo-amount").focus();
  try { await core.call("money_add", { kind: $("#mo-kind").value, amount: amt, category: $("#mo-cat").value.trim(), note: $("#mo-note").value.trim(), date: $("#mo-date").value });
        $("#mo-amount").value = ""; $("#mo-note").value = ""; toast("Записано"); loadMoney(); loadCalendar(); }
  catch (e) { toast(e.message); }
};
$("#cal-prev").onclick = () => { calM--; if (calM < 1) { calM = 12; calY--; } loadCalendar(); };
$("#cal-next").onclick = () => { calM++; if (calM > 12) { calM = 1; calY++; } loadCalendar(); };
$("#cal-today").onclick = () => { calY = null; loadCalendar(); };
let calT = null;
const calRefresh = () => { if (!$("#p-calendar").classList.contains("cur")) return; clearTimeout(calT); calT = setTimeout(loadCalendar, 300); };
core.on("money_saved", calRefresh); core.on("reminders", calRefresh); core.on("note_saved", calRefresh);

/* ---------- обновление: окно с ходом установки (пароль → установка → перезапуск) ----------
   updShown держит полоску от отката назад: настоящий процент приходит редко, между ними она ползёт по времени. */
let updTimer = null, updShown = 0, updStart = 0;
function updShow(ver, stage, err, u) {
  const o = $("#upd");
  o.classList.add("on"); $("#upd-ver").textContent = ver ? `Dewiar ${ver}` : "Dewiar";
  if (!updStart) updStart = Date.now();
  const win = navigator.platform.startsWith("Win");
  const steps = { auth: 0, install: 1, restart: 2, error: -1 }, k = steps[stage] ?? 1;
  $$("#upd li").forEach((li, i) => { li.className = k < 0 ? (i === 0 ? "" : "") : i < k ? "done" : i === k ? "now" : ""; });
  const title = { auth: win ? "Запускаю установку…" : "Подтвердите установку паролем", install: "Устанавливаю новую версию",
                  restart: "Готово — перезапускаюсь", error: "Обновление не установилось" }[stage] || "Устанавливаю…";
  $("#upd-t").textContent = title;
  // Windows: установщик идёт тихо, без пароля; Linux: pkexec просит пароль своим окном
  const line = stage === "auth" && !win ? "GNOME показал окно для пароля — оно может быть за этим окном." :
               stage === "error" ? (err || "") : (u && u.line) || (stage === "install" ? "это займёт до минуты — можно продолжать работу" : "");
  $("#upd-line").textContent = line;
  const secs = Math.round((Date.now() - updStart) / 1000);
  let pct = stage === "restart" ? 100 : (u && u.pct) || 0;
  if (stage === "install") pct = Math.max(pct, Math.min(90, 8 + secs * 1.6));     // идёт — полоска не стоит на месте
  updShown = Math.max(stage === "error" ? 0 : updShown, pct);
  $("#upd-bar b").style.width = (stage === "auth" ? 4 : updShown) + "%";
  $("#upd-bar").classList.toggle("wait", stage === "auth");
  o.classList.toggle("bad", stage === "error");
  $("#upd-x").style.display = stage === "error" ? "" : "none";
}
function updPoll(ver) {
  clearInterval(updTimer);
  updTimer = setInterval(async () => {
    const x = api(); if (!x || !x.update_progress) return;
    try { const u = await x.update_progress(); if (!u || !u.stage) return;
          updShow(ver, u.stage, u.error, u); if (u.stage === "error") clearInterval(updTimer); } catch (e) {}
  }, 500);
}
$("#upd-x").onclick = () => { clearInterval(updTimer); updStart = 0; updShown = 0; $("#upd").classList.remove("on"); };

/* ---------- Dewiar на телефоне ---------- */
/* QR-код поаккуратнее: скруглённые точки и «глазки» (сканируется так же — тёмное на белом).
   ec — уровень коррекции ошибок: для длинного текста "L", иначе точек столько, что телефон не разберёт код с экрана.
   -> строка SVG; "" если библиотека assets/qrcode.js не загрузилась. */
function qrPretty(text, ec) {
  if (typeof qrcode !== "function") return "";
  const q = qrcode(0, ec || (text.length > 300 ? "L" : "M")); q.addData(text); q.make();
  const n = q.getModuleCount(), m = 1.5, W = n + m * 2;
  const eye = (r, c) => (r < 7 && c < 7) || (r < 7 && c >= n - 7) || (r >= n - 7 && c < 7);
  let dots = "";
  for (let r = 0; r < n; r++) for (let c = 0; c < n; c++) {
    if (!q.isDark(r, c) || eye(r, c)) continue;
    dots += `<rect x="${(c + m + 0.07).toFixed(2)}" y="${(r + m + 0.07).toFixed(2)}" width=".86" height=".86" rx=".3"/>`;
  }
  const eyeSvg = (r, c) => { const x = c + m, y = r + m;
    return `<rect x="${x + 0.5}" y="${y + 0.5}" width="6" height="6" rx="1.9" fill="none" stroke="#111" stroke-width="1"/>` +
           `<rect x="${x + 2}" y="${y + 2}" width="3" height="3" rx="1"/>`; };
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${W}" shape-rendering="geometricPrecision"><rect width="${W}" height="${W}" fill="#fff"/>` +
    `<g fill="#111">${dots}${eyeSvg(0, 0)}${eyeSvg(0, n - 7)}${eyeSvg(n - 7, 0)}</g></svg>`;
}
function qrSvg(text) { return qrPretty(text); }
/* Первый код — ссылка на Dewiar.apk; второй (c.url) переносит настройки и содержит ключи API открытым текстом,
   поэтому рисуется только по кнопке «Показать код». */
async function phFill() {
  try {
    const c = await core.call("phone_config");
    $("#ph-qr1").innerHTML = qrSvg(c.apk);
    $("#ph-note").textContent = (c.local_note ? c.local_note + " " : "") + (c.lan ? `Мозг «${c.brain}» — в домашней сети: телефон будет думать, пока он в этой же сети Wi-Fi. Вне дома — подключите в приложении облако по ключу.` : "");
    $("#ph-show").onclick = () => { const box = $("#ph-qr2"); box.classList.remove("ph-hide"); box.innerHTML = qrSvg(c.url);
      $("#ph-note").textContent = "В этом коде ключи доступа — не показывайте его посторонним. " + ($("#ph-note").textContent || ""); };
  } catch (e) { $("#ph-note").textContent = e.message; }
}

/* ---------- умный дом Яндекса ---------- */
const SH_ICON = { light: "💡", socket: "🔌", "thermostat": "🌡", cooking: "☕", vacuum_cleaner: "🧹", media_device: "📺", openable: "🪟", humidifier: "💧", purifier: "🍃", fan: "🌀" };
function shFill(h) {
  if (!h) return;
  $("#sh-setup").style.display = h.connected ? "none" : ""; $("#sh-on").style.display = h.connected ? "" : "none";
  // вход в Яндекс — через общее приложение Dewiar (или своё, если ClientID задан в «Своё приложение»)
  const a = $("#sh-auth"); a.href = h.auth_url || "https://oauth.yandex.ru/client/new/";
  a.textContent = h.auth_url ? "Получить ключ" : "Создать приложение Яндекса"; if (!h.auth_url) $("#sh-own").open = true;
  if (document.activeElement !== $("#sh-cid")) $("#sh-cid").value = (S.smarthome && S.smarthome.client_id) || "";
  if (h.connected) {
    if (h.error) { $("#sh-state").className = "res bad"; $("#sh-state").textContent = h.error; }
    else { $("#sh-state").className = "res ok"; $("#sh-state").textContent = `Подключён: устройств ${h.devices.length}, комнат ${h.rooms.length}, сценариев ${h.scenarios.length}`; }
    $("#sh-devs").innerHTML = (h.devices || []).map(d => { const k = Object.keys(SH_ICON).find(x => (d.type || "").includes(x));
      return `<span class="chip shd${d.on ? " on" : ""}" title="${d.on ? "включено" : "выключено"}">${k ? SH_ICON[k] + " " : ""}${escH(d.name)}${d.room ? ` <small style="opacity:.6">· ${escH(d.room)}</small>` : ""}</span>`; }).join("") +
      (h.scenarios || []).map(x => `<span class="chip shd scn">▶ ${escH(x)}</span>`).join("");
  }
}
$("#sh-go").onclick = async (ev) => { const r = $("#sh-res"); ev.target.disabled = true; r.className = "res"; r.textContent = "подключаю…";
  try { const h = await core.call("home_connect", { token: $("#sh-token").value }); $("#sh-token").value = "";
    if (h.client_saved) { S.smarthome = Object.assign({}, S.smarthome, { client_id: h.client_id }); shFill(h); r.className = "res ok";
      r.textContent = "Это ClientID приложения — запомнил. Теперь шаг 1: «Получить ключ» → «Разрешить», и вставьте ключ, который покажет Яндекс."; return; }
    shFill(h); r.className = "res ok"; r.textContent = "Готово! Скажите: «включи свет»."; }
  catch (e) { r.className = "res bad"; r.textContent = e.message; } finally { ev.target.disabled = false; } };
$("#sh-token").onkeydown = (e) => { if (e.key === "Enter") $("#sh-go").click(); };
$("#sh-auth").addEventListener("click", () => setTimeout(() => $("#sh-token").focus(), 400));
// своё приложение Яндекса: ClientID — 32 знака; пусто — общее приложение Dewiar
$("#sh-cid").onchange = async () => { const v = $("#sh-cid").value.trim().toLowerCase(), r = $("#sh-res");
  if (v && !/^[0-9a-f]{32}$/.test(v)) { r.className = "res bad"; r.textContent = "ClientID — 32 латинские буквы и цифры, как на странице приложения Яндекса"; return; }
  await save({ smarthome: { client_id: v } }, true); S.smarthome = Object.assign({}, S.smarthome, { client_id: v });
  shFill(await core.call("home_get")); r.className = "res ok"; r.textContent = v ? "ClientID сохранён — теперь «Получить ключ»." : "Используется общее приложение Dewiar."; };
$("#sh-refresh").onclick = () => core.call("home_refresh").then(shFill).catch(e => toast(e.message));
// умный дом — на телефон QR-кодом (только ключ дома; через сервер ключ не ходит): dewiar://import?c=… с одним «home»
$("#sh-phone").onclick = async () => { const box = $("#sh-qrbox"); if (box.style.display !== "none") { box.style.display = "none"; $("#sh-qr").innerHTML = ""; return; }
  try { const d = await core.call("phone_home"); $("#sh-qr").innerHTML = qrSvg(d.url); box.style.display = ""; } catch (e) { toast(e.message); } };
$("#sh-off").onclick = async () => { if (await ask("Отключить умный дом?")) core.call("home_forget").then(shFill).catch(e => toast(e.message)); };

/* ---------- календари Google/Яндекс ---------- */
const I_CAL = '<rect x="3.5" y="5" width="17" height="15.5" rx="2.5"/><path d="M3.5 10h17M8 3v4M16 3v4"/>';
function csFill(c) {
  const it = (c && c.items) || [];
  $("#cs-list").innerHTML = it.map(x => {
    const st = x.status || {}, when = st.time ? new Date(st.time).toLocaleString("ru-RU", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "";
    return `<div class="ritem" data-id="${escH(x.id)}"><div class="ico" style="background:${escH(x.color)}26;color:${escH(x.color)}">${SVG(I_CAL)}</div>
      <div class="rbody"><div class="rtext">${escH(x.name)}</div><div class="rmeta">${st.ok === false ? `<span style="color:var(--bad)">${escH(st.error || "не обновился")}</span>` :
        `<span>событий: ${st.count || 0}</span>${when ? `<span>обновлён ${escH(when)}</span>` : ""}`}<span>${escH(x.url)}</span></div></div>
      <label class="tg" title="Показывать"><input type="checkbox" data-c="on" ${x.enabled !== false ? "checked" : ""}><i></i></label>
      <div class="ract"><button data-c="del" title="Отключить календарь">${SVG(I_DEL)}</button></div></div>`; }).join("");
  $$("#cs-list [data-c=del]").forEach(b => b.onclick = async () => { const id = b.closest(".ritem").dataset.id; if (!await ask("Отключить этот календарь?")) return;
    try { csFill(await core.call("cal_remove", { id })); } catch (e) { toast(e.message); } });
  $$("#cs-list [data-c=on]").forEach(b => b.onchange = async () => { const id = b.closest(".ritem").dataset.id;
    try { csFill(await core.call("cal_toggle", { id, on: b.checked })); } catch (e) { toast(e.message); } });
}
$("#cs-add").onclick = async (ev) => {
  const r = $("#cs-res"), url = $("#cs-url").value.trim(); if (!url) { r.className = "res bad"; r.textContent = "Вставьте ссылку iCal"; return; }
  ev.target.disabled = true; r.className = "res"; r.textContent = "подключаю…";
  try { const c = await core.call("cal_add", { url }); csFill(c); $("#cs-url").value = ""; const x = c.items[c.items.length - 1];
        r.className = "res ok"; r.textContent = `Подключён «${x.name}»: событий ${(x.status || {}).count || 0}. Они уже в календаре студии.`; }
  catch (e) { r.className = "res bad"; r.textContent = e.message; } finally { ev.target.disabled = false; }
};
core.on("calendars", e => csFill(e));
