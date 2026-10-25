/* «Платежи» (25.10, владелец: «каждый месяц делаю оплаты коммунальных и вношу, за что и сколько заплатил… всегда можно
   вернуться и перепроверить»; «гибко и универсально»; «сколько за год оплатили — красивые графики»; «изображение
   прикрепить из буфера или перетаскиванием — платёжка, реквизиты»). Ядро — core/payments.py, команды pay_*.
   Три вида: «Месяц» — карточки счетов со статусом и кнопкой «Записать оплату»; «Год» — таблица счета × месяцы;
   «Аналитика» — итог года, кольцо по группам, столбцы по месяцам, счётчики (расход и цена единицы — два графика, не одна
   ось). Карточка счёта открывает панель: история, «Как платить» с вложениями, настройки. Цвет счёта — по его месту в
   списке (фиксированная очередь палитры, не по сумме). */
const PY = { tab: "month", ov: null, year: new Date().getFullYear(), cur: "", panel: "hist", grid: null, stats: null };
const PY_MON = ["янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"];
const PY_MONF = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"];
const PY_KIND_ICON = { meter: "🔥", fixed: "🌐", loan: "🏦", yearly: "📅", other: "🧾" };

const pyMoney = (n) => n == null || n === "" ? "" : Number(n).toLocaleString("ru-RU", { minimumFractionDigits: Number(n) % 1 ? 2 : 0, maximumFractionDigits: 2 });
const pyNum = (n) => n == null || n === "" ? "" : Number(n).toLocaleString("ru-RU", { maximumFractionDigits: 3 });
const pyDate = (iso) => { if (!iso) return ""; const [y, m, d] = String(iso).slice(0, 10).split("-"); return `${d}.${m}.${String(y).slice(2)}`; };
const pyDay = (iso) => { if (!iso) return ""; const d = new Date(iso + "T12:00"); return `${d.getDate()} ${["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"][d.getMonth()]}`; };
const pyBill = (id) => ((PY.ov && PY.ov.bills) || []).find(b => b.id === id);
const pySlot = (id) => { const i = ((PY.ov && PY.ov.bills) || []).findIndex(b => b.id === id); return (i < 0 ? 0 : i) % 8 + 1; };
const pyStatus = (st, b) => {
  if (!st) return ["", ""];
  if (st.s === "paid") return ["ok", `Оплачено${st.amount != null ? " · " + pyMoney(st.amount) : ""}`];
  if (st.s === "unpaid") return ["warn", "Не погашено"];
  if (st.s === "overdue") return ["bad", `Срок был ${pyDay(st.due)}`];
  if (st.s === "soon") { const d = Math.round((new Date(st.due + "T00:00") - new Date(new Date().toDateString())) / 864e5); return ["soon", d <= 0 ? "Срок сегодня" : d === 1 ? "Срок завтра" : `Срок ${pyDay(st.due)}`]; }
  if (st.s === "wait") return ["", b && b.autopay ? `Автооплата ${pyDay(st.due)}` : `До ${pyDay(st.due)}`];
  return ["", b && b.autopay ? "Автооплата" : "Срок не задан"];
};

async function loadPayPage() {
  try { PY.ov = await core.call("pay_overview"); } catch (e) { $("#py-body").innerHTML = `<p class="hint">${escH(e.message)}</p>`; return; }
  pyTabs(); pyRender();
}
function pyTabs() { $$("#py-tabs button").forEach(b => { const on = b.dataset.t === PY.tab; b.classList.toggle("on", on); b.setAttribute("aria-selected", String(on)); }); }
async function pyRender() {
  const box = $("#py-body"); if (!box || !PY.ov) return;
  if (!PY.ov.bills.length) {
    box.innerHTML = `<div class="py-empty"><div class="py-empty-ic">🧾</div><h3>Здесь будут ваши обязательные платежи</h3>
      <p>Газ, свет, вода, интернет, кредит — у каждого реквизиты, срок и история оплат с показаниями. Лира напомнит накануне срока,
      а через год покажет, сколько ушло на каждый.</p>
      <div class="py-empty-row"><button class="btn primary" id="py-first">Добавить первый платёж</button>
      <button class="btn" id="py-imp2">Перенести из органайзера</button></div>
      <p class="hint">Голосом: «Лира, добавь платёж: газ, до 25-го» — и потом «оплатил газ 47,84, показания 28135».</p></div>`;
    $("#py-first").onclick = () => pyBillForm(null); $("#py-imp2").onclick = pyImport;
    return;
  }
  if (PY.tab === "month") pyMonth(box);
  else if (PY.tab === "year") { box.innerHTML = '<p class="hint">Собираю таблицу…</p>'; PY.grid = await core.call("pay_grid", { year: PY.year }).catch(() => null); pyYear(box); }
  else { box.innerHTML = '<p class="hint">Считаю…</p>'; PY.stats = await core.call("pay_stats", { year: PY.year }).catch(() => null); pyStats(box); }
}

/* ---------- «Месяц»: карточки ---------- */
function pyMonth(box) {
  const live = PY.ov.bills.filter(b => !b.archived), now = new Date();
  const paid = live.filter(b => b.now.s === "paid"), sum = paid.reduce((a, b) => a + (b.now.amount || 0), 0);
  const seg = live.map(b => `<i class="s-${pyStatus(b.now, b)[0] || "wait"}" title="${escH(b.name)}: ${escH(pyStatus(b.now, b)[1])}"></i>`).join("");
  box.innerHTML = `<div class="py-sum glass"><div><small>${PY_MONF[now.getMonth()]} ${now.getFullYear()}</small>
      <b>Оплачено ${paid.length} из ${live.length}</b><span>${sum ? pyMoney(sum) + " за месяц · " : ""}${pyMoney(PY.ov.total_year)} за ${PY.ov.year} год</span></div>
      <div class="py-seg" role="img" aria-label="Оплачено ${paid.length} из ${live.length}">${seg}</div></div>
    <div class="py-cards">${live.map(pyCard).join("")}</div>
    ${PY.ov.bills.some(b => b.archived) ? `<details class="py-arch"><summary>В архиве: ${PY.ov.bills.filter(b => b.archived).length}</summary><div class="py-cards">${PY.ov.bills.filter(b => b.archived).map(pyCard).join("")}</div></details>` : ""}`;
  $$("#py-body .py-card").forEach(c => {
    c.onclick = (e) => { if (e.target.closest(".py-pay")) return; pyOpen(c.dataset.b); };
    c.onkeydown = (e) => { if (e.key === "Enter" && e.target === c) pyOpen(c.dataset.b); };
  });
  $$("#py-body .py-pay").forEach(b => b.onclick = (e) => { e.stopPropagation(); pyPayForm(b.dataset.b); });
}
function pyCard(b) {
  const [cls, txt] = pyStatus(b.now, b), l = b.last;
  const sub = l ? [l.reading != null ? `показание ${pyNum(l.reading)}` : "", l.used != null ? `расход ${pyNum(l.used)} ${escH(b.unit || "")}`.trim() : "",
    `последняя ${pyDate(l.date)}`].filter(Boolean).join(" · ") : "оплат ещё нет";
  return `<div class="py-card glass s-${cls || "wait"}" data-b="${escH(b.id)}" tabindex="0" role="button" style="--c: var(--ser-${pySlot(b.id)})" aria-label="${escH(b.name)}: ${escH(txt)}">
    <div class="py-top"><span class="py-ic" aria-hidden="true">${escH(b.icon || PY_KIND_ICON[b.kind] || "🧾")}</span><b>${escH(b.name)}</b>${b.autopay ? '<em class="py-auto" title="Автооплата">авто</em>' : ""}</div>
    <span class="py-st">${escH(txt)}</span><small>${sub}</small>
    ${b.kind === "loan" && b.left != null ? `<small>осталось ${pyMoney(b.left)} из ${pyMoney(b.total)}</small><span class="py-bar"><i style="width:${Math.max(0, Math.min(100, 100 - b.left / (b.total || 1) * 100))}%"></i></span>` : ""}
    <div class="py-foot"><span>${b.year_sum ? pyMoney(b.year_sum) + " за год" : ""}</span>${b.now.s === "paid" ? "" : `<button class="btn small py-pay" data-b="${escH(b.id)}">Записать оплату</button>`}</div></div>`;
}

/* ---------- «Год»: таблица ---------- */
function pyYear(box) {
  const g = PY.grid; if (!g) { box.innerHTML = '<p class="hint">Не получилось собрать таблицу.</p>'; return; }
  const tot = Array(12).fill(0);
  const rows = g.rows.map(r => {
    let sum = 0;
    const cells = r.bill.kind === "yearly" ? [`<td colspan="12" class="py-yc">${pyCell(r.cells[0], r.bill)}</td>`]
      : r.cells.map((c, i) => { if (c.s === "paid" && c.amount) { sum += c.amount; tot[i] += c.amount; } return `<td>${pyCell(c, r.bill, i)}</td>`; });
    if (r.bill.kind === "yearly" && r.cells[0].s === "paid" && r.cells[0].amount) sum += r.cells[0].amount;
    return `<tr><th scope="row"><span class="py-dot" style="--c: var(--ser-${pySlot(r.bill.id)})"></span>${escH(r.bill.icon || "")} ${escH(r.bill.name)}</th>${cells.join("")}<td class="py-tot">${sum ? pyMoney(sum) : ""}</td></tr>`;
  }).join("");
  box.innerHTML = `<div class="py-yhead"><button class="ib" id="py-yp" aria-label="Прошлый год">‹</button><b>${g.year}</b><button class="ib" id="py-yn" aria-label="Следующий год">›</button>
      <span class="py-legend"><i class="s-ok"></i>оплачено <i class="s-warn"></i>не погашено <i class="s-bad"></i>не оплачено в срок <i class="s-soon"></i>скоро срок</span></div>
    <div class="py-tw glass"><table class="py-grid"><thead><tr><th></th>${PY_MON.map(m => `<th>${m}</th>`).join("")}<th class="py-tot">за год</th></tr></thead>
    <tbody>${rows}</tbody><tfoot><tr><th scope="row">Всего</th>${tot.map(v => `<td>${v ? pyMoney(Math.round(v)) : ""}</td>`).join("")}<td class="py-tot">${pyMoney(Math.round(tot.reduce((a, b) => a + b, 0)))}</td></tr></tfoot></table></div>`;
  $("#py-yp").onclick = () => { PY.year--; pyRender(); };
  $("#py-yn").onclick = () => { PY.year++; pyRender(); };
  $$("#py-body .py-cell[data-b]").forEach(c => c.onclick = () => pyOpen(c.dataset.b));
}
function pyCell(c, b, i) {
  const map = { paid: ["ok", "✓"], unpaid: ["warn", "!"], overdue: ["bad", "✕"], missed: ["bad", "✕"], soon: ["soon", "•"] };
  const [cls, mark] = map[c.s] || ["", ""];
  const tip = `${b.name}${i != null ? " · " + PY_MONF[i].toLowerCase() : ""}: ` + ({ paid: "оплачено" + (c.amount != null ? " " + pyMoney(c.amount) : ""), unpaid: "не погашено",
    overdue: "не оплачено, срок прошёл", missed: "оплата не записана", soon: "скоро срок", future: "впереди", before: "платёж ещё не вели" }[c.s] || "без записи")
    + (c.used != null ? `, расход ${pyNum(c.used)}` : "");
  return `<span class="py-cell s-${cls || c.s}" data-b="${escH(b.id)}" title="${escH(tip)}">${mark ? `<i>${mark}</i>` : ""}${c.s === "paid" && c.amount != null ? `<small>${pyMoney(Math.round(c.amount))}</small>` : ""}</span>`;
}

/* ---------- «Аналитика» ---------- */
function pyStats(box) {
  const st = PY.stats; if (!st) { box.innerHTML = '<p class="hint">Не получилось посчитать.</p>'; return; }
  if (!st.total) {
    box.innerHTML = `<div class="py-yhead">${pyYearNav(st)}</div><div class="py-empty glass"><p>За ${st.year} год оплат ещё нет — графики появятся, как только запишете первые.
      Можно перенести историю из старого органайзера — кнопка вверху.</p></div>`;
    pyYearWire(); return;
  }
  const delta = st.total_prev && st.prev_months >= 6 ? (st.total - st.total_prev) / st.total_prev * 100 : null;   // прошлый год неполный — сравнение врёт
  box.innerHTML = `<div class="py-yhead">${pyYearNav(st)}</div>
    <div class="py-an">
      <div class="py-hero glass"><small>Обязательные платежи за ${st.year} год</small><b>${pyMoney(Math.round(st.total))}</b>
        ${delta != null ? `<span class="${delta > 0 ? "up" : "down"}">${delta > 0 ? "▲" : "▼"} ${Math.abs(delta).toFixed(0)}% к ${st.year - 1} (${pyMoney(Math.round(st.total_prev))})</span>` : `<span>в среднем ${pyMoney(Math.round(st.total / Math.max(1, st.months.filter(m => Object.keys(m.by).length).length)))} в месяц</span>`}
        <ol class="py-rank">${st.by_bill.map(x => `<li><span class="py-dot" style="--c: var(--ser-${pySlot(x.id)})"></span>${escH(x.icon || "")} ${escH(x.name)}<b>${pyMoney(Math.round(x.sum))}</b><em>${x.prev && st.prev_months >= 6 ? `${x.sum >= x.prev ? "+" : "−"}${pyMoney(Math.abs(Math.round(x.sum - x.prev)))}` : ""}</em></li>`).join("")}</ol></div>
      <div class="py-chart glass"><h3>На что уходит</h3>${pyDonut(st)}</div>
      <div class="py-chart glass py-wide"><h3>По месяцам</h3>${pyBars(st)}</div>
      ${st.meters.map(pyMeter).join("")}
    </div>`;
  pyYearWire(); pyTips();
}
const pyYearNav = (st) => `<button class="ib" id="py-yp" aria-label="Прошлый год">‹</button><b>${st.year}</b><button class="ib" id="py-yn" aria-label="Следующий год">›</button>`;
function pyYearWire() { $("#py-yp").onclick = () => { PY.year--; pyRender(); }; $("#py-yn").onclick = () => { PY.year++; pyRender(); }; }
function pyDonut(st) {
  const tot = st.by_group.reduce((a, b) => a + b.sum, 0) || 1, R = 70, C = 2 * Math.PI * R;
  let off = 0;
  const groups = (PY.ov.groups || []);
  const arcs = st.by_group.map(g => { const k = groups.indexOf(g.name); const len = g.sum / tot * C, gap = st.by_group.length > 1 ? 3 : 0;
    const s = `<circle r="${R}" cx="90" cy="90" fill="none" stroke="var(--ser-${(k < 0 ? 5 : k) % 8 + 1})" stroke-width="22" stroke-dasharray="${Math.max(0, len - gap)} ${C}" stroke-dashoffset="${-off}" data-tip="${escH(g.name)}: ${pyMoney(Math.round(g.sum))} (${Math.round(g.sum / tot * 100)}%)"/>`;
    off += len; return s; }).join("");
  return `<div class="py-donut"><svg viewBox="0 0 180 180" role="img" aria-label="Доли групп платежей"><g transform="rotate(-90 90 90)">${arcs}</g>
      <text x="90" y="86" text-anchor="middle" class="py-dt">${pyMoney(Math.round(tot))}</text><text x="90" y="106" text-anchor="middle" class="py-ds">за год</text></svg>
    <ul class="py-leg">${st.by_group.map(g => { const k = groups.indexOf(g.name); return `<li><span class="py-dot" style="--c: var(--ser-${(k < 0 ? 5 : k) % 8 + 1})"></span>${escH(g.name)}<b>${Math.round(g.sum / tot * 100)}%</b></li>`; }).join("")}</ul></div>`;
}
function pyBars(st) {
  const ids = st.by_bill.map(x => x.id), max = Math.max(1, ...st.months.map(m => Object.values(m.by).reduce((a, b) => a + b, 0)));
  const W = 1000, H = 220, pad = 34, bw = (W - pad) / 12, step = pyStep(max), top = Math.ceil(max / step) * step;
  let svg = `<svg viewBox="0 0 ${W} ${H + 24}" role="img" aria-label="Платежи по месяцам">`;
  for (let v = 0; v <= top; v += step) { const y = H - v / top * H + 4; svg += `<line x1="${pad}" x2="${W}" y1="${y}" y2="${y}" class="py-gl"/><text x="${pad - 6}" y="${y + 4}" text-anchor="end" class="py-ax">${v >= 1000 ? Math.round(v / 100) / 10 + "к" : v}</text>`; }
  st.months.forEach((m, i) => {
    let y = H + 4; const x = pad + i * bw + bw * .2, w = bw * .6;
    ids.forEach(id => { const v = m.by[id]; if (!v) return; const h = Math.max(2, v / top * H); y -= h;
      const b = st.by_bill.find(z => z.id === id);
      svg += `<rect x="${x}" y="${y + 1}" width="${w}" height="${Math.max(1, h - 2)}" rx="3" fill="var(--ser-${pySlot(id)})" data-tip="${escH(PY_MONF[i])}: ${escH(b ? b.name : "")} — ${pyMoney(v)}"/>`; });
    const sum = Object.values(m.by).reduce((a, b) => a + b, 0);
    svg += `<rect x="${pad + i * bw}" y="0" width="${bw}" height="${H + 4}" fill="transparent" data-tip="${escH(PY_MONF[i])}: всего ${pyMoney(Math.round(sum))}"/>`;
    svg += `<text x="${x + w / 2}" y="${H + 20}" text-anchor="middle" class="py-ax">${PY_MON[i]}</text>`;
  });
  return svg + `</svg><ul class="py-leg py-legh">${st.by_bill.map(x => `<li><span class="py-dot" style="--c: var(--ser-${pySlot(x.id)})"></span>${escH(x.name)}</li>`).join("")}</ul>`;
}
function pyStep(max) { const r = max / 4, p = Math.pow(10, Math.floor(Math.log10(r))); return [1, 2, 2.5, 5, 10].map(k => k * p).find(s => s >= r) || p * 10; }
function pyMeter(m) {
  const pts = m.points.filter(p => p.used != null || p.amount != null).slice(-14);
  if (pts.length < 2) return "";
  const W = 300, H = 110, n = pts.length, bw = W / n;
  const um = Math.max(1, ...pts.map(p => p.used || 0)), rates = pts.map(p => p.rate).filter(r => r != null), rmax = Math.max(...rates, 0) * 1.15 || 1, rmin = rates.length ? Math.min(...rates) * .85 : 0;
  const bars = pts.map((p, i) => p.used == null ? "" : `<rect x="${i * bw + bw * .18}" y="${H - p.used / um * H}" width="${bw * .64}" height="${Math.max(2, p.used / um * H)}" rx="3" fill="var(--ser-${pySlot(m.bill)})" data-tip="${pyDate(p.date)}: расход ${pyNum(p.used)} ${escH(m.unit)}${p.amount ? " · " + pyMoney(p.amount) : ""}"/>`).join("");
  const rp = pts.map((p, i) => p.rate == null ? null : [i * bw + bw / 2, H - (p.rate - rmin) / ((rmax - rmin) || 1) * (H - 10) - 5, p]).filter(Boolean);
  const line = rp.length > 1 ? `<path d="M${rp.map(q => q[0].toFixed(1) + " " + q[1].toFixed(1)).join(" L")}" class="py-ln"/>` + rp.map(q => `<circle cx="${q[0]}" cy="${q[1]}" r="4" class="py-pt" data-tip="${pyDate(q[2].date)}: ${q[2].rate.toLocaleString("ru-RU", { maximumFractionDigits: 4 })} за ${escH(m.unit || "единицу")}"/>`).join("") : "";
  const last = rates.length ? rates[rates.length - 1] : null, first = rates.length ? rates[0] : null;
  const labs = pts.map((p, i) => `<text x="${i * bw + bw / 2}" y="${H + 13}" text-anchor="middle" class="py-ax">${PY_MON[+p.date.slice(5, 7) - 1]}</text>`).join("");
  return `<div class="py-chart glass"><h3>${escH(m.icon || "")} ${escH(m.name)}</h3>
    <small class="py-cap">Расход${m.unit ? ", " + escH(m.unit) : ""}</small><svg viewBox="0 0 ${W} ${H + 16}" class="py-mini" role="img" aria-label="Расход по месяцам">${bars}${labs}</svg>
    ${rp.length > 1 ? `<small class="py-cap">Цена за ${escH(m.unit || "единицу")}${last && first ? ` · ${last >= first ? "выросла" : "снизилась"} на ${Math.abs((last - first) / first * 100).toFixed(0)}%` : ""}</small>
    <svg viewBox="0 0 ${W} ${H + 16}" class="py-mini" role="img" aria-label="Цена за единицу">${line}${labs}</svg>` : ""}</div>`;
}
let pyTipEl = null;
function pyTips() {
  if (!pyTipEl) { pyTipEl = document.createElement("div"); pyTipEl.className = "py-tip"; pyTipEl.hidden = true; document.body.appendChild(pyTipEl); }
  $$("#py-body [data-tip]").forEach(el => {
    el.onmousemove = (e) => { pyTipEl.textContent = el.dataset.tip; pyTipEl.hidden = false; pyTipEl.style.left = Math.min(innerWidth - pyTipEl.offsetWidth - 8, e.clientX + 14) + "px"; pyTipEl.style.top = (e.clientY - 34) + "px"; el.classList.add("hov"); };
    el.onmouseleave = () => { pyTipEl.hidden = true; el.classList.remove("hov"); };
  });
}

/* ---------- панель счёта: история, как платить, настройки ---------- */
async function pyOpen(id, panel) {
  const b = pyBill(id); if (!b) return;
  PY.cur = id; if (panel) PY.panel = panel;
  const pays = await core.call("pay_list", { bill: id }).catch(() => []);
  const d = $("#py-drawer");
  d.innerHTML = `<div class="py-dh"><span class="py-ic big">${escH(b.icon || "🧾")}</span><div><h2>${escH(b.name)}</h2><small>${escH((PY.ov.kinds[b.kind] || {}).title || "")}${b.day ? ` · срок ${b.day}-е${b.kind === "yearly" && b.month ? " " + PY_MONF[b.month - 1].toLowerCase() : ""}` : ""}${b.autopay ? " · автооплата" : ""}</small></div>
      <button class="ib" id="py-dx" aria-label="Закрыть">✕</button></div>
    <div class="py-dtabs" role="tablist">${[["hist", "История"], ["how", "Как платить"], ["set", "Настройки"]].map(([k, n]) => `<button role="tab" data-k="${k}" class="${PY.panel === k ? "on" : ""}">${n}</button>`).join("")}</div>
    <div class="py-dbody">${PY.panel === "hist" ? pyHist(b, pays) : PY.panel === "how" ? pyHow(b) : pySet(b)}</div>`;
  d.hidden = false; requestAnimationFrame(() => d.classList.add("on"));
  $("#py-dx").onclick = pyClose;
  $$("#py-drawer .py-dtabs button").forEach(t => t.onclick = () => { PY.panel = t.dataset.k; pyOpen(id); });
  pyDrawerWire(b, pays);
}
function pyClose() { const d = $("#py-drawer"); d.classList.remove("on"); setTimeout(() => { d.hidden = true; }, 200); PY.cur = ""; }
function pyHist(b, pays) {
  const unit = b.unit || "";
  return `<div class="py-dact"><button class="btn primary" id="py-dpay">Записать оплату</button></div>
    ${pays.length ? `<table class="py-hist"><thead><tr><th>Дата</th>${b.kind === "meter" ? "<th>Показание</th><th>Расход</th>" : ""}<th>Сумма</th><th></th></tr></thead><tbody>
    ${pays.map(p => `<tr class="${p.status === "unpaid" ? "unp" : ""}" data-p="${escH(p.id)}"><td>${pyDate(p.date)}${p.note ? `<small>${escH(p.note)}</small>` : ""}</td>
      ${b.kind === "meter" ? `<td>${pyNum(p.reading)}</td><td>${p.used != null ? pyNum(p.used) + " " + escH(unit) : ""}</td>` : ""}
      <td><b>${p.amount != null ? pyMoney(p.amount) : ""}</b>${p.status === "unpaid" ? '<small class="py-unp">не погашено</small>' : ""}</td>
      <td class="py-ra">${(p.att || []).length ? `<span class="py-clip" title="${escH(p.att.map(a => a.name).join(", "))}">📎${p.att.length}</span>` : ""}<button class="ib sm" data-edit="${escH(p.id)}" aria-label="Изменить">✎</button></td></tr>`).join("")}
    </tbody></table>` : `<p class="hint">Оплат ещё нет. Запишите кнопкой выше или голосом: «оплатил ${escH(b.name.toLowerCase())} …».</p>`}`;
}
function pyHow(b) {
  const pics = (b.att || []).filter(a => a.img), files = (b.att || []).filter(a => !a.img);
  return `<label class="py-f"><span>Как платить и реквизиты</span><textarea id="py-how" rows="7" placeholder="Например: ЕРИП → Коммунальные платежи → Газоснабжение → номер абонента 0000000">${escH(b.how || "")}</textarea></label>
    <label class="py-f"><span>Телефоны</span><input id="py-phones" value="${escH(b.phones || "")}" placeholder="для показаний и справок"></label>
    <div class="py-atts">${pics.map(a => `<figure data-a="${escH(a.id)}"><i data-img="${escH(a.path)}"></i><button class="nt-x" title="Убрать">×</button><figcaption>${escH(a.name)}</figcaption></figure>`).join("")}
      ${files.map(a => `<span class="nt-f" data-a="${escH(a.id)}" data-path="${escH(a.path)}">📎 ${escH(a.name)}<button class="nt-x" title="Убрать">×</button></span>`).join("")}</div>
    ${pyDrop("bill")}`;
}
function pySet(b) {
  const kinds = PY.ov.kinds, groups = PY.ov.groups;
  return `<div class="py-form">
    <label class="py-f"><span>Название</span><input id="py-sname" value="${escH(b.name)}" maxlength="60"></label>
    <label class="py-f"><span>Значок</span><input id="py-sicon" value="${escH(b.icon || "")}" maxlength="4" class="py-icin"></label>
    <label class="py-f"><span>Вид</span><select id="py-skind">${Object.entries(kinds).map(([k, v]) => `<option value="${k}" ${b.kind === k ? "selected" : ""}>${v.title}</option>`).join("")}</select></label>
    <label class="py-f"><span>Группа (для итогов)</span><select id="py-sgroup">${groups.map(g => `<option ${b.group === g ? "selected" : ""}>${g}</option>`).join("")}</select></label>
    <label class="py-f"><span>Срок — число месяца</span><input id="py-sday" type="number" min="1" max="31" value="${b.day || ""}" placeholder="например, 25"></label>
    <label class="py-f py-onlyy" ${b.kind === "yearly" ? "" : "hidden"}><span>Месяц (раз в год)</span><select id="py-smonth"><option value="">—</option>${PY_MONF.map((m, i) => `<option value="${i + 1}" ${b.month === i + 1 ? "selected" : ""}>${m}</option>`).join("")}</select></label>
    <label class="py-f py-onlym" ${b.kind === "meter" ? "" : "hidden"}><span>Единица счётчика</span><input id="py-sunit" value="${escH(b.unit || "")}" placeholder="м³, кВт·ч"></label>
    <label class="py-f"><span>Обычная сумма</span><input id="py-samount" type="number" step="0.01" value="${b.amount ?? ""}" placeholder="подставится в форму оплаты"></label>
    <label class="py-f py-onlyl" ${b.kind === "loan" ? "" : "hidden"}><span>Сумма кредита</span><input id="py-stotal" type="number" step="0.01" value="${b.total ?? ""}"></label>
    <label class="chk"><input type="checkbox" id="py-sauto" ${b.autopay ? "checked" : ""}><span>Автооплата — списывается само (о сроке не напоминать)</span></label>
    <label class="chk"><input type="checkbox" id="py-srem" ${b.remind !== false ? "checked" : ""}><span>Напоминать накануне и в день срока, пока не оплачено</span></label>
    <label class="py-f py-full"><span>Заметка</span><textarea id="py-snote" rows="2">${escH(b.note || "")}</textarea></label>
    <div class="py-dact"><button class="btn primary" id="py-ssave">Сохранить</button><button class="btn" id="py-sarch">${b.archived ? "Вернуть из архива" : "В архив"}</button><button class="btn danger" id="py-sdel">Удалить</button></div></div>`;
}
function pyDrop(target) {
  return `<label class="nt-drop py-drop" data-target="${target}"><input type="file" multiple hidden>
    <svg viewBox="0 0 24 24"><path d="m20.5 11.5-8.6 8.6a5.5 5.5 0 0 1-7.8-7.8l8.6-8.6a3.7 3.7 0 0 1 5.2 5.2l-8.6 8.6a1.8 1.8 0 0 1-2.6-2.6l8-8"/></svg>
    <span><b>${target === "bill" ? "Платёжка, реквизиты, памятка" : "Квитанция или скриншот оплаты"}</b> — вставьте снимок Ctrl+V, перетащите сюда или нажмите</span></label>`;
}
function pyFiles(files) {
  return Promise.all([...files].slice(0, 8).map(f => new Promise((ok) => { const r = new FileReader(); r.onload = () => ok({ name: f.name || "снимок.png", data: r.result }); r.onerror = () => ok(null); r.readAsDataURL(f); })))
    .then(l => l.filter(Boolean));
}
function pyDropWire(el, send) {
  if (!el) return;
  const inp = el.querySelector("input");
  inp.onchange = async () => { send(await pyFiles(inp.files)); inp.value = ""; };
  el.ondragover = (e) => { e.preventDefault(); el.classList.add("over"); };
  el.ondragleave = () => el.classList.remove("over");
  el.ondrop = async (e) => { e.preventDefault(); el.classList.remove("over"); send(await pyFiles(e.dataTransfer.files)); };
}
function pyPasteFiles(e) { const fs = [...((e.clipboardData && e.clipboardData.items) || [])].filter(i => i.kind === "file").map(i => i.getAsFile()).filter(Boolean); return fs; }
async function pyImgs(root) {
  for (const i of root.querySelectorAll("i[data-img]")) {
    core.call("pay_file", { path: i.dataset.img }).then(r => { i.style.backgroundImage = `url("${r.url}")`; i.onclick = () => pyLight(r.url); }).catch(() => { });
  }
}
function pyLight(url) {
  const o = document.createElement("div"); o.className = "py-light"; o.innerHTML = `<img src="${url}" alt=""><button class="ib" aria-label="Закрыть">✕</button>`;
  o.onclick = () => o.remove(); document.body.appendChild(o);
}
function pyDrawerWire(b, pays) {
  const d = $("#py-drawer");
  if (PY.panel === "hist") {
    $("#py-dpay").onclick = () => pyPayForm(b.id);
    $$("#py-drawer [data-edit]").forEach(x => x.onclick = () => pyPayForm(b.id, pays.find(p => p.id === x.dataset.edit)));
  } else if (PY.panel === "how") {
    const save = async () => { await core.call("pay_bill_save", { bill: { id: b.id, how: $("#py-how").value, phones: $("#py-phones").value } }).catch(e => toast(e.message)); pyReload(); };
    $("#py-how").onchange = save; $("#py-phones").onchange = save;
    const send = async (files) => { for (const f of files) await core.call("pay_attach", { target: "bill", id: b.id, name: f.name, data: f.data }).catch(e => toast(e.message)); await pyReload(); pyOpen(b.id); };
    pyDropWire(d.querySelector(".py-drop"), send);
    d.onpaste = async (e) => { const fs = pyPasteFiles(e); if (fs.length) { e.preventDefault(); send(await pyFiles(fs)); } };
    $$("#py-drawer .py-atts [data-a] .nt-x").forEach(x => x.onclick = async (e) => { e.stopPropagation(); await core.call("pay_detach", { target: "bill", id: b.id, aid: x.parentNode.dataset.a }); await pyReload(); pyOpen(b.id); });
    $$("#py-drawer .nt-f[data-path]").forEach(x => x.onclick = () => core.call("ws_open", { path: x.dataset.path }).catch(e => toast(e.message)));
    pyImgs(d);
  } else {
    $("#py-skind").onchange = () => { const k = $("#py-skind").value; $(".py-onlyy").hidden = k !== "yearly"; $(".py-onlym").hidden = k !== "meter"; $(".py-onlyl").hidden = k !== "loan"; };
    $("#py-ssave").onclick = async () => {
      try {
        await core.call("pay_bill_save", { bill: { id: b.id, name: $("#py-sname").value, icon: $("#py-sicon").value, kind: $("#py-skind").value, group: $("#py-sgroup").value,
          day: $("#py-sday").value, month: $("#py-smonth").value, unit: $("#py-sunit").value, amount: $("#py-samount").value, total: $("#py-stotal").value,
          autopay: $("#py-sauto").checked, remind: $("#py-srem").checked, note: $("#py-snote").value } });
        toast("Сохранено"); await pyReload(); pyOpen(b.id);
      } catch (e) { toast(e.message); }
    };
    $("#py-sarch").onclick = async () => { await core.call("pay_bill_save", { bill: { id: b.id, archived: !b.archived } }); pyClose(); pyReload(); };
    $("#py-sdel").onclick = async () => {
      if (!(await ask(`Удалить «${b.name}» вместе со всей историей оплат? Вложения останутся в папке ассистента.`, { yes: "Удалить" }))) return;
      await core.call("pay_bill_delete", { id: b.id }); pyClose(); pyReload();
    };
  }
}
async function pyReload() { PY.ov = await core.call("pay_overview").catch(() => PY.ov); if ($("#p-pay").classList.contains("cur")) pyRender(); }

/* ---------- формы: новый платёж и запись оплаты ---------- */
function pyModal(html) {
  const o = document.createElement("div"); o.className = "py-modal"; o.innerHTML = `<div class="py-mbox glass" role="dialog" aria-modal="true">${html}</div>`;
  document.body.appendChild(o); requestAnimationFrame(() => o.classList.add("on"));
  const close = () => { o.classList.remove("on"); setTimeout(() => o.remove(), 160); document.removeEventListener("keydown", key); };
  const key = (e) => { if (e.key === "Escape") close(); };
  document.addEventListener("keydown", key);
  o.onmousedown = (e) => { if (e.target === o) close(); };
  return [o, close];
}
function pyBillForm() {
  const kinds = PY.ov ? PY.ov.kinds : {};
  const [o, close] = pyModal(`<h2>Новый платёж</h2>
    <label class="py-f"><span>Название</span><input id="pb-name" placeholder="Газ, Электричество, Интернет, Кредит…" maxlength="60"></label>
    <div class="py-kinds" role="radiogroup">${Object.entries(kinds).map(([k, v], i) => `<label class="py-kind"><input type="radio" name="pb-kind" value="${k}" ${i === 0 ? "checked" : ""}><b>${v.icon} ${v.title}</b><small>${v.hint}</small></label>`).join("")}</div>
    <div class="py-two"><label class="py-f"><span>Срок — число месяца</span><input id="pb-day" type="number" min="1" max="31" placeholder="25"></label>
      <label class="chk"><input type="checkbox" id="pb-auto"><span>Автооплата</span></label></div>
    <label class="py-f"><span>Как платить (можно потом)</span><textarea id="pb-how" rows="3" placeholder="ЕРИП → … → номер абонента"></textarea></label>
    <div class="py-mact"><button class="btn" id="pb-no">Отмена</button><button class="btn primary" id="pb-ok">Добавить</button></div>`);
  const nm = o.querySelector("#pb-name"); nm.focus();
  nm.oninput = () => { const t = nm.value.toLowerCase(); const k = /газ|свет|электр|вод|тепл/.test(t) ? "meter" : /кредит|рассроч|ипотек/.test(t) ? "loan" : /страхов|налог|техосмотр/.test(t) ? "yearly" : null;
    if (k) o.querySelector(`input[name=pb-kind][value=${k}]`).checked = true; };
  o.querySelector("#pb-no").onclick = close;
  o.querySelector("#pb-ok").onclick = async () => {
    try {
      const b = await core.call("pay_bill_save", { bill: { name: nm.value, kind: o.querySelector("input[name=pb-kind]:checked").value, day: o.querySelector("#pb-day").value,
        autopay: o.querySelector("#pb-auto").checked, how: o.querySelector("#pb-how").value } });
      close(); await pyReload(); pyOpen(b.id, "hist");
    } catch (e) { toast(e.message); }
  };
  o.querySelector(".py-mbox").onkeydown = (e) => { if (e.key === "Enter" && e.target.tagName === "INPUT") o.querySelector("#pb-ok").click(); };
}
function pyPayForm(bid, p) {
  const b = pyBill(bid); if (!b) return;
  const today = new Date(), iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  const last = b.last && (!p || b.last.id !== p.id) ? b.last : null, meter = b.kind === "meter";
  const files = [];
  const [o, close] = pyModal(`<h2>${escH(b.icon || "")} ${escH(b.name)} — ${p ? "оплата" : "записать оплату"}</h2>
    <div class="py-two"><label class="py-f"><span>Дата</span><input id="pp-date" type="date" value="${p ? p.date : iso(today)}"></label>
      <label class="py-f"><span>Сумма</span><input id="pp-amount" type="number" step="0.01" inputmode="decimal" value="${p ? p.amount ?? "" : b.amount ?? ""}" placeholder="${last && last.amount ? "в прошлый раз " + pyMoney(last.amount) : ""}"></label></div>
    ${meter ? `<div class="py-two"><label class="py-f"><span>Показание счётчика</span><input id="pp-reading" type="number" step="any" value="${p ? p.reading ?? "" : ""}" placeholder="${last && last.reading != null ? "прошлое " + pyNum(last.reading) : ""}"></label>
      <label class="py-f"><span>Расход${b.unit ? ", " + escH(b.unit) : ""}</span><input id="pp-used" type="number" step="any" value="${p ? p.used ?? "" : ""}" placeholder="посчитается сам"></label></div>
      <p class="hint" id="pp-calc"></p>` : ""}
    <label class="py-f"><span>Заметка</span><input id="pp-note" value="${escH(p ? p.note || "" : "")}" placeholder="автооплата, по квитанции…"></label>
    <label class="chk"><input type="checkbox" id="pp-unpaid" ${p && p.status === "unpaid" ? "checked" : ""}><span>Не погашено (записать, что платёж не прошёл)</span></label>
    ${pyDrop("pay")}<div class="py-atts" id="pp-files">${p ? (p.att || []).map(a => `<span class="nt-f">📎 ${escH(a.name)}</span>`).join("") : ""}</div>
    <div class="py-mact">${p ? '<button class="btn danger" id="pp-del">Удалить</button><span style="flex:1"></span>' : ""}<button class="btn" id="pp-no">Отмена</button><button class="btn primary" id="pp-ok">${p ? "Сохранить" : "Записать"}</button></div>`);
  const amt = o.querySelector("#pp-amount"); (meter ? o.querySelector("#pp-reading") : amt).focus();
  const calc = () => { if (!meter) return; const r = parseFloat(o.querySelector("#pp-reading").value), prev = last && last.reading;
    const used = !isNaN(r) && prev != null && r >= prev ? r - prev : null, a = parseFloat(amt.value);
    o.querySelector("#pp-calc").textContent = used != null ? `Расход: ${pyNum(used)} ${b.unit || ""}${!isNaN(a) && used ? ` · ${(a / used).toLocaleString("ru-RU", { maximumFractionDigits: 4 })} за ${b.unit || "единицу"}` : ""}` : ""; };
  if (meter) { o.querySelector("#pp-reading").oninput = calc; amt.oninput = calc; calc(); }
  const showFiles = () => { o.querySelector("#pp-files").innerHTML = (p ? (p.att || []).map(a => `<span class="nt-f">📎 ${escH(a.name)}</span>`).join("") : "") + files.map(f => `<span class="nt-f">📎 ${escH(f.name)}</span>`).join(""); };
  pyDropWire(o.querySelector(".py-drop"), (l) => { files.push(...l); showFiles(); });
  o.onpaste = async (e) => { const fs = pyPasteFiles(e); if (fs.length) { e.preventDefault(); files.push(...await pyFiles(fs)); showFiles(); } };
  o.querySelector("#pp-no").onclick = close;
  if (p) o.querySelector("#pp-del").onclick = async () => { if (!(await ask("Удалить эту оплату?", { yes: "Удалить" }))) return; await core.call("pay_delete", { id: p.id }); close(); await pyReload(); if (PY.cur) pyOpen(PY.cur); };
  o.querySelector("#pp-ok").onclick = async () => {
    try {
      const v = (id) => { const x = o.querySelector(id); return x ? x.value : undefined; };
      const r = await core.call("pay_save", { pay: { id: p ? p.id : undefined, bill: b.id, date: v("#pp-date"), amount: v("#pp-amount"), reading: meter ? v("#pp-reading") : undefined,
        used: meter ? v("#pp-used") : undefined, note: v("#pp-note"), status: o.querySelector("#pp-unpaid").checked ? "unpaid" : "paid" } });
      for (const f of files) await core.call("pay_attach", { target: "pay", id: r.id, name: f.name, data: f.data }).catch(e => toast(e.message));
      close(); toast(r.status === "unpaid" ? "Записано: не погашено" : "Оплата записана"); await pyReload(); if (PY.cur) pyOpen(PY.cur);
    } catch (e) { toast(e.message); }
  };
  o.querySelector(".py-mbox").onkeydown = (e) => { if (e.key === "Enter" && e.target.tagName === "INPUT" && e.target.type !== "checkbox") o.querySelector("#pp-ok").click(); };
}

/* ---------- перенос из старого органайзера ---------- */
function pyImport() {
  const [o, close] = pyModal(`<h2>Перенести из органайзера</h2>
    <p class="hint">Вставьте всё, что вели раньше: разделы по платежам, строки «25.01.26 - 27214 (477 куб = 101.87)», реквизиты, телефоны.
      Я разложу это по платежам и месяцам — вы проверите и перенесёте. Ничего не сохранится, пока не нажмёте «Перенести».</p>
    <textarea id="pi-text" rows="10" placeholder="Вставьте текст сюда (Ctrl+V)"></textarea>
    <div class="py-mact"><button class="btn" id="pi-no">Отмена</button><button class="btn" id="pi-ai" title="Для неровных записей — разберёт модель (дольше)">Разобрать с Лирой</button><button class="btn primary" id="pi-go">Разобрать</button></div>
    <div id="pi-prev"></div>`);
  o.querySelector(".py-mbox").classList.add("wide");
  o.querySelector("#pi-text").focus();
  o.querySelector("#pi-no").onclick = close;
  const run = async (ai) => {
    const t = o.querySelector("#pi-text").value.trim(); if (!t) return toast("Сначала вставьте текст");
    const pv = o.querySelector("#pi-prev"); pv.innerHTML = `<p class="hint">${ai ? "Лира читает записи…" : "Разбираю…"}</p>`;
    let r; try { r = await core.call(ai ? "pay_import_ai" : "pay_import_parse", { text: t }); } catch (e) { pv.innerHTML = `<p class="hint">${escH(e.message)}</p>`; return; }
    const items = r.items || [];
    if (!items.length) { pv.innerHTML = '<p class="hint">Не нашла ни одной строки с датой — попробуйте «Разобрать с Лирой».</p>'; return; }
    pv.innerHTML = `<h3>Что получилось — проверьте названия</h3><div class="pi-list">${items.map((it, i) => `<div class="pi-it" data-i="${i}">
        <label class="chk"><input type="checkbox" class="pi-on" checked></label><input class="pi-name" value="${escH(it.name)}" maxlength="40">
        <select class="pi-kind">${Object.entries(PY.ov.kinds).map(([k, v]) => `<option value="${k}" ${it.kind === k ? "selected" : ""}>${v.title}</option>`).join("")}</select>
        <span class="pi-n">${it.pays.length} ${it.pays.length % 10 === 1 && it.pays.length % 100 !== 11 ? "оплата" : it.pays.length % 10 >= 2 && it.pays.length % 10 <= 4 && (it.pays.length % 100 < 10 || it.pays.length % 100 >= 20) ? "оплаты" : "оплат"}${it.pays.length ? ` · ${pyDate(it.pays[0].date)}–${pyDate(it.pays[it.pays.length - 1].date)}` : ""}</span>
        <details><summary>подробно</summary>${it.how ? `<pre>${escH(it.how)}</pre>` : ""}<table class="py-hist">${it.pays.map(p => `<tr><td>${pyDate(p.date)}</td><td>${pyNum(p.reading)}</td><td>${pyNum(p.used)}</td><td><b>${pyMoney(p.amount)}</b></td><td>${escH(p.note || "")}${p.status === "unpaid" ? " · не погашено" : ""}</td></tr>`).join("")}</table></details></div>`).join("")}</div>
      <div class="py-mact"><button class="btn primary" id="pi-apply">Перенести</button></div>`;
    pv.querySelector("#pi-apply").onclick = async () => {
      const use = [...pv.querySelectorAll(".pi-it")].map(el => { const it = items[+el.dataset.i]; return el.querySelector(".pi-on").checked ? Object.assign({}, it, { name: el.querySelector(".pi-name").value, kind: el.querySelector(".pi-kind").value }) : null; }).filter(Boolean);
      try { const res = await core.call("pay_import_apply", { items: use }); close(); toast(`Перенесено: платежей ${res.bills}, оплат ${res.pays}`, 3500); await pyReload(); }
      catch (e) { toast(e.message); }
    };
  };
  o.querySelector("#pi-go").onclick = () => run(false);
  o.querySelector("#pi-ai").onclick = () => run(true);
}

if ($("#p-pay")) {
  $$("#py-tabs button").forEach(b => b.onclick = () => { PY.tab = b.dataset.t; pyTabs(); pyRender(); });
  $("#py-add").onclick = () => pyBillForm();
  $("#py-imp").onclick = pyImport;
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && PY.cur && !document.querySelector(".py-modal")) pyClose(); });
}
core.on("pay_saved", () => { if ($("#p-pay") && $("#p-pay").classList.contains("cur") && !document.querySelector(".py-modal")) pyReload().then(() => { if (PY.cur) pyOpen(PY.cur); }); });
