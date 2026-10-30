/* «Мой месяц с Лирой» на главной студии (0.61; core/month.py). Первые 7 дней месяца — карточка о прошлом: лента дней
   (каждый день — квадратик, чем больше дел — тем гуще), крупные числа (дела, напоминания, траты, заметки, дневник),
   куда ушли деньги — одной строкой. «Рассказать голосом» — month_say (Лира рассказывает тепло, своими словами);
   «Скрыть» — month_hide до следующего месяца. Пустой месяц (ничего не было) — карточки нет. Голосом в любой день:
   «как прошёл мой месяц?» — инструмент month_summary. */
let MO = null, MO_BUSY = false;
const moE = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const moN = (n, one, few, many) => { const a = n % 10, b = n % 100; return a === 1 && b !== 11 ? one : a >= 2 && a <= 4 && (b < 12 || b > 14) ? few : many; };
const moMoney = (v) => Math.round(+v || 0).toLocaleString("ru-RU");
const moTime = () => new Date().getDate() <= 7;

async function moLoad(force) {
  const box = $("#hm-month"); if (!box) return;
  if (!moTime() && !force) { box.hidden = true; return; }
  try { MO = await core.call("month_get", {}); } catch (e) { MO = null; }
  moRender(force);
}
window.moLoad = moLoad;

function moRibbon(d) {
  const by = (d.done || {}).by_day || [], max = Math.max(1, ...by);
  const [y, m] = d.ym.split("-").map(Number), first = (new Date(y, m - 1, 1).getDay() + 6) % 7;   // понедельник — 0
  const cell = (n, i) => {
    const lv = n ? Math.min(4, 1 + Math.floor((n / max) * 3.999)) : 0;
    return `<i class="lv${lv}" data-d="${i + 1}" title="${i + 1} ${moE(d.in_gen || "")}: ${n ? n + " " + moN(n, "дело", "дела", "дел") : "без дел"}"></i>`;
  };
  return `<div class="mo-cal"><h3>Дела по дням</h3><div class="mo-rib" role="img" aria-label="Дела по дням: дней с делами — ${(d.done || {}).days || 0}">`
    + ["пн", "вт", "ср", "чт", "пт", "сб", "вс"].map(w => `<u>${w}</u>`).join("") + "<b></b>".repeat(first) + by.map(cell).join("") + `</div></div>`;
}
function moStats(d) {
  const st = [], dn = d.done || {}, m = d.money || {};
  if (dn.n) st.push([dn.n, moN(dn.n, "дело сделано", "дела сделано", "дел сделано"), dn.streak > 1 ? `лучшая серия — ${dn.streak} ${moN(dn.streak, "день", "дня", "дней")} подряд` : ""]);
  if ((d.rem || {}).n) st.push([d.rem.n, moN(d.rem.n, "напоминание", "напоминания", "напоминаний"), "прозвенело"]);
  if (m.n && m.expense) st.push([moMoney(m.expense), `${moE(m.cur)} потрачено`, m.income ? `пришло ${moMoney(m.income)}` : ""]);
  if ((d.notes || {}).n) st.push([d.notes.n, moN(d.notes.n, "заметка", "заметки", "заметок"), "новые и изменённые"]);
  if ((d.diary || {}).days) st.push([d.diary.days, moN(d.diary.days, "день", "дня", "дней") + " в дневнике", ""]);
  return st.slice(0, 4).map(([v, l, s]) => `<div class="mo-st"><b>${v}</b><span>${l}</span>${s ? `<small>${moE(s)}</small>` : ""}</div>`).join("");
}
function moRender(force) {
  const box = $("#hm-month"); if (!box) return;
  const d = MO;
  if (!d || d.empty || (d.hidden && !force) || (!moTime() && !force)) { box.hidden = true; return; }
  const nm = typeof hmWho === "function" ? hmWho("") : "Лира", who = typeof mnWith === "function" ? mnWith(nm === "Ассистент" ? "Лира" : nm) : "Лирой";
  const m = d.money || {}, cats = (m.cats || []).filter(c => c.sum > 0);
  const tot = cats.reduce((a, c) => a + c.sum, 0) || 1;
  const top = (d.done || {}).top || [];
  box.hidden = false;
  box.innerHTML = `<div class="mo-head"><div><h2>Ваш ${moE(d.title)} с ${moE(who)}</h2><p>Итоги месяца, ${d.year}</p></div>`
    + `<button class="mn-x" id="mo-hide" title="Скрыть до следующего месяца" aria-label="Скрыть до следующего месяца">×</button></div>`
    + `<div class="mo-sts">${moStats(d)}</div>`
    + `<div class="mo-grid">${moRibbon(d)}<div class="mo-right">${top.length ? `<h3>Чем можно гордиться</h3><ul class="mo-top">${top.slice(-3).reverse().map(t => `<li>${moE(t)}</li>`).join("")}</ul>` : ""}`
    + (cats.length ? `<h3>Куда ушли деньги</h3><div class="mo-bar" aria-hidden="true">${cats.map((c, i) => `<i class="${c.rest ? "co" : "c" + i}" style="flex:${c.sum / tot}"></i>`).join("")}</div>`
      + `<ul class="mo-cats">${cats.map((c, i) => `<li><i class="${c.rest ? "co" : "c" + i}"></i>${moE(c.name || "без категории")}<b>${moMoney(c.sum)}</b></li>`).join("")}</ul>` : "")
    + `</div></div><div class="mn-foot"><button class="btn primary" id="mo-say">Рассказать голосом</button>`
    + `<span class="hint">Спросите в любой день: «как прошёл мой месяц?»</span></div>`;
  $("#mo-hide").onclick = () => core.call("month_hide", { ym: d.ym }).then(() => { box.hidden = true; toast(`«Ваш ${d.title}» скрыт`); }).catch(e => toast(e.message));
  $("#mo-say").onclick = () => { if (MO_BUSY) return; MO_BUSY = true; setTimeout(() => { MO_BUSY = false; }, 5000);
    core.call("month_say", { ym: d.ym }).then(() => toast("Рассказываю…")).catch(e => toast(e.message)); };
}
