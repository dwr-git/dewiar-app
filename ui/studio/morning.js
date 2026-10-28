/* «Утро с Лирой» на главной студии (0.57; core/morning.py). С 4 до 13 часов — над карточками «Сегодня»: погода
   крупно, и по строке на каждое, что ждёт: встречи и дела, сотрудники, клиенты, почта от людей, задачи. Строка ведёт
   в свой раздел. «Расскажи утро» — та же сводка голосом (job_run brief); «Каждое утро в …» — дело по расписанию
   (job_add, preset brief — та же карточка, что в «Делах по расписанию»); «Скрыть до завтра». Нет города — поле
   «Город для погоды». Данные — morning_get (погода и почта из кэша ядра, 20 минут). */
let MN = null, MN_BUSY = false;
const MN_SKY = [[/гроз/, "storm"], [/снег|крупа/, "snow"], [/дожд|ливн|морос/, "rain"], [/туман|изморозь/, "fog"], [/пасмур|облач/, "cloud"], [/ясно/, "sun"]];
const MN_ICON = {
  sun: '<circle cx="12" cy="12" r="4.2"/><path d="M12 2.5v2.2M12 19.3v2.2M4.6 4.6l1.6 1.6M17.8 17.8l1.6 1.6M2.5 12h2.2M19.3 12h2.2M4.6 19.4l1.6-1.6M17.8 6.2l1.6-1.6"/>',
  cloud: '<path d="M7 18.5a4.5 4.5 0 0 1-.6-9A6 6 0 0 1 18 10.5a4 4 0 0 1-.5 8H7z"/>',
  rain: '<path d="M7 15.5a4.5 4.5 0 0 1-.6-9A6 6 0 0 1 18 7.5a4 4 0 0 1-.5 8H7z"/><path d="M8.5 18.5l-1 2M12.5 18.5l-1 2M16.5 18.5l-1 2"/>',
  snow: '<path d="M7 15.5a4.5 4.5 0 0 1-.6-9A6 6 0 0 1 18 7.5a4 4 0 0 1-.5 8H7z"/><path d="M8 19.5h.01M12 20.5h.01M16 19.5h.01"/>',
  storm: '<path d="M7 15.5a4.5 4.5 0 0 1-.6-9A6 6 0 0 1 18 7.5a4 4 0 0 1-.5 8H7z"/><path d="M12.5 14l-2 3.5h3l-2 3.5"/>',
  fog: '<path d="M4 9h16M3 13h18M5 17h14"/>',
};
const MN_ROW = {
  today: ['<rect x="3.5" y="5" width="17" height="15.5" rx="2.5"/><path d="M3.5 10h17M8 3v4M16 3v4"/>', "calendar"],
  team: ['<rect x="3" y="7.5" width="18" height="12.5" rx="2.5"/><path d="M8.5 7.5V6a2 2 0 0 1 2-2h3a2 2 0 0 1 2 2v1.5M3 12.5h18"/>', "team"],
  clients: ['<circle cx="9" cy="8.5" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0M16 4.5a3.5 3.5 0 0 1 0 7M21.5 20a6.5 6.5 0 0 0-4-6"/>', "clients"],
  mail: ['<rect x="3" y="5" width="18" height="14" rx="2.5"/><path d="M3.5 6.5l8.5 6.5 8.5-6.5"/>', "connect"],
  tasks: ['<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>', "tasks"],
};
const mnE = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const mnDay = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`; };
const mnTime = () => { const h = new Date().getHours(); return h >= 4 && h < 13; };
const mnN = (n, one, few, many) => { const a = n % 10, b = n % 100; return `${n} ${a === 1 && b !== 11 ? one : a >= 2 && a <= 4 && (b < 12 || b > 14) ? few : many}`; };

/* «с Лирой», «с Патриком», «с Эвой» — имя в творительном падеже */
function mnWith(n) {
  n = String(n || "Лира");
  if (/[жшчщц]а$/i.test(n)) return n.slice(0, -1) + "ей";
  if (/а$/i.test(n)) return n.slice(0, -1) + "ой";
  if (/я$/i.test(n)) return n.slice(0, -1) + "ей";
  if (/[йь]$/i.test(n)) return n.slice(0, -1) + "ем";
  return /[бвгджзклмнпрстфхцчшщ]$/i.test(n) ? n + "ом" : n;
}
async function mnLoad(fresh) {
  const box = $("#hm-morning"); if (!box) return;
  if (!mnTime()) { box.hidden = true; return; }
  try { MN = await core.call("morning_get", fresh ? { fresh: true } : {}); } catch (e) { MN = null; }
  mnRender();
}
function mnRows(d) {
  const rows = [], t = d.today || {};
  const meet = t.meet || [], todo = t.todo || [];
  if (meet.length || todo.length) {
    const first = meet[0] || todo[0];
    rows.push(["today", meet.length ? mnN(meet.length, "встреча", "встречи", "встреч") + (todo.length ? ", " + mnN(todo.length, "дело", "дела", "дел") : "") : mnN(todo.length, "дело", "дела", "дел"),
      `${first.time ? first.time + " — " : ""}${first.title}`]);
  } else rows.push(["today", "День свободен", "встреч и дел на сегодня нет"]);
  const tm = d.team;
  if (tm && (tm.late.length || tm.check.length || tm.msgs.length)) {
    const b = [tm.late.length ? `${tm.late.length} просрочено` : "", tm.check.length ? `${tm.check.length} ждёт проверки` : "", tm.msgs.length ? mnN(tm.msgs.length, "сообщение", "сообщения", "сообщений") : ""].filter(Boolean).join(" · ");
    const x = tm.check[0] || tm.late[0];
    rows.push(["team", "Сотрудники: " + b, x ? `${x.name} — «${x.title}»` : `${tm.msgs[0].name}: ${tm.msgs[0].t}`]);
  }
  const c = d.clients;
  if (c && (c.over.length || c.today.length)) { const x = c.over[0] || c.today[0]; rows.push(["clients", c.over.length ? `Клиенты ждут: ${c.over.length}` : `Клиенты сегодня: ${c.today.length}`, `${x.name} — ${x.what}`]); }
  if (c && (c.owed || []).length) rows.push(["clients", `Должны, срок прошёл: ${c.owed.length}`, `${c.owed[0].name} — ${c.owed[0].what}`]);
  const m = d.mail;
  if (m && m.unread) rows.push(["mail", `Почта: ${m.unread}${m.more ? "+" : ""} ${mnN(m.unread, "новое", "новых", "новых").split(" ")[1]}`,
    m.people.length ? `${m.people[0].from} — «${m.people[0].subject}»${m.people.length > 1 ? ` и ещё ${m.people.length - 1} от людей` : ""}` : "только рассылки"]);
  const k = d.tasks;
  if (k && k.wait.length) rows.push(["tasks", "Задача ждёт ответа", `«${k.wait[0].title}»`]);
  else if (k && k.done.length) rows.push(["tasks", `Готово за ночь: ${k.done.length}`, k.done.map(x => `«${x}»`).join(", ")]);
  return rows;
}
function mnWeather(d) {
  const w = d.weather;
  if (!d.city) return `<div class="mn-w mn-city"><b>Погода</b><p>Скажите, где вы, — и утром я буду говорить погоду.</p>`
    + `<div class="mn-cin"><input id="mn-city" placeholder="Город, например Минск" maxlength="60" aria-label="Город для погоды"><button class="btn small primary" id="mn-cgo">Готово</button></div></div>`;
  if (!w) return `<div class="mn-w"><b class="mn-t">—</b><p>${mnE(d.city)}: прогноз сейчас не получить</p><button class="lnk" id="mn-cedit">Другой город</button></div>`;
  const sky = (MN_SKY.find(([rx]) => rx.test(w.sky_day || w.sky)) || [0, "cloud"])[1];
  return `<div class="mn-w sky-${sky}"><svg class="mn-sky" viewBox="0 0 24 24" aria-hidden="true">${MN_ICON[sky]}</svg>`
    + `<b class="mn-t">${w.now > 0 ? "+" : ""}${w.now}°</b><p class="mn-sk">${mnE(w.sky)}</p>`
    + (w.min != null ? `<p>днём ${w.min > 0 ? "+" : ""}${w.min}…${w.max > 0 ? "+" : ""}${w.max}°${w.rain != null && w.rain >= 30 ? `, осадки ${w.rain}%` : ""}</p>` : "")
    + `<button class="lnk mn-cname" id="mn-cedit" title="Сменить город">${mnE(w.city)}</button></div>`;
}
function mnRender() {
  const box = $("#hm-morning"); if (!box) return;
  const d = MN;
  if (!d || !mnTime() || ((d.settings || {}).hide === mnDay())) { box.hidden = true; return; }
  const nm = typeof hmWho === "function" ? hmWho("") : "Лира", who = mnWith(nm === "Ассистент" ? "Лира" : nm);
  const daily = d.daily;
  box.hidden = false;
  box.innerHTML = `<div class="mn-head"><h2>Утро с ${mnE(who)}</h2><button class="mn-x" id="mn-hide" title="Скрыть до завтра" aria-label="Скрыть до завтра">×</button></div>`
    + `<div class="mn-grid">${mnWeather(d)}<ul class="mn-rows">${mnRows(d).map(([k, b, s]) => `<li><button data-mgo="${MN_ROW[k][1]}"><svg viewBox="0 0 24 24" aria-hidden="true">${MN_ROW[k][0]}</svg><span><b>${mnE(b)}</b><small>${mnE(s)}</small></span></button></li>`).join("")}</ul></div>`
    + `<div class="mn-foot"><button class="btn primary" id="mn-say">Расскажи утро</button>`
    + `<label class="mn-daily"><span class="tg"><input type="checkbox" id="mn-dly"${daily ? " checked" : ""}><i></i></span>Каждое утро в <input id="mn-at" value="${mnE(daily ? daily.at_hm : "08:00")}" maxlength="5" inputmode="numeric" aria-label="Время сводки"> голосом</label>`
    + (!d.mail_on ? `<button class="lnk mn-mail" data-mgo="connect">Подключить почту — скажу о важных письмах</button>` : "") + `</div>`;
  $$("#hm-morning [data-mgo]").forEach(b => b.onclick = () => (typeof hmGo === "function" ? hmGo(b.dataset.mgo) : $(`nav button[data-p="${b.dataset.mgo}"]`).click()));
  $("#mn-hide").onclick = () => core.call("morning_set", { hide: mnDay() }).then(r => { MN = r; mnRender(); toast("Утро скрыто до завтра"); }).catch(e => toast(e.message));
  $("#mn-say").onclick = () => { if (MN_BUSY) return; MN_BUSY = true; setTimeout(() => { MN_BUSY = false; }, 4000);
    core.call("job_run", { task: "Утренняя сводка", brief: true, deliver: "voice" }).then(() => toast("Рассказываю…")).catch(e => toast(e.message)); };
  const cgo = $("#mn-cgo"); if (cgo) { const go = () => { const c = $("#mn-city").value.trim(); if (!c) return $("#mn-city").focus(); cgo.disabled = true;
    core.call("morning_set", { city: c }).then(r => { MN = r; mnRender(); if (!r.weather) toast(`«${c}» — прогноз не нашёлся, проверьте название`, 3500); }).catch(e => { cgo.disabled = false; toast(e.message); }); };
    cgo.onclick = go; $("#mn-city").onkeydown = (e) => { if (e.key === "Enter") go(); }; }
  const ce = $("#mn-cedit"); if (ce) ce.onclick = () => { MN = Object.assign({}, MN, { city: "", weather: null }); mnRender(); const i = $("#mn-city"); if (i) { i.value = (d.settings || {}).city || ""; i.focus(); } };
  const dl = $("#mn-dly"), at = $("#mn-at");
  const setDaily = async () => {
    try {
      if (MN.daily) await core.call("reminder_cancel", { id: MN.daily.id });
      if (dl.checked) {
        const m = at.value.trim().replace(/[.\-\s]/, ":").match(/^(\d{1,2})(?::(\d{2}))?$/);
        if (!m || +m[1] > 23 || +(m[2] || 0) > 59) { at.focus(); dl.checked = false; return toast("Время — например 8:00"); }
        const hm = `${m[1].padStart(2, "0")}:${m[2] || "00"}`;
        await core.call("job_add", { phrase: `каждый день в ${hm} делай утренняя сводка`, task: "Утренняя сводка", deliver: "voice", brief: true, preset: "brief" });
        toast(`Каждое утро в ${hm} — расскажу голосом`);
      } else toast("Утренняя сводка по расписанию выключена");
      MN = await core.call("morning_get"); mnRender();
    } catch (e) { toast(e.message); }
  };
  dl.onchange = setDaily; at.onchange = () => { if (dl.checked) setDaily(); };
}
