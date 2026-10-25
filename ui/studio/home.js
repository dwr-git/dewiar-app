/* Студия → «Главная» (24.10, владелец: «вот я внутри программы, как бы в её настройках… часть разделов — настройки, раз
   настроил и больше не идёшь, а часть — которыми пользуешься; сделать первичную красивую страничку с иконками, как на
   айфоне… главное — здесь же включить нужное и убрать ненужное»).
   Сверху — приветствие и «Сегодня» (ближайшее дело, письмо близкого, задача ждёт ответа, сделано сегодня); ниже —
   «Приложения» (значки; «Настроить главную» — показать или скрыть, перетащить), «Продолжить» (последний разговор и
   блокнот), «Настройка» (то, что настраивают один раз). Выбор значков — ui.home_apps (порядок и состав). */
/* рисунки — маленькие сцены из тонких линий на сетке 48×48 (24.10, владелец: «прекрасен»): ln — главный штрих, th — тонкие
   детали, sf — мягкая заливка, dt — точки, bg — подложка цвета плитки (чтобы детали не просвечивали), tx — цифра даты */
const HM_SVG = (g, d) => `<svg viewBox="0 0 48 48" class="hmx" style="--hg:url(#hg${g})">${d}</svg>`;
const HM_APPS = [
  { id: "chat", name: "Чат", sub: "с персонажами", g: 1, d: '<path class="sf" d="M6 12a6 6 0 0 1 6-6h16a6 6 0 0 1 6 6v9a6 6 0 0 1-6 6H17l-7 5.5V26.6A6 6 0 0 1 6 21z"/><path class="ln" d="M6 12a6 6 0 0 1 6-6h16a6 6 0 0 1 6 6v9a6 6 0 0 1-6 6H17l-7 5.5V26.6A6 6 0 0 1 6 21z"/><path class="ln" d="M23 30.5v.5a5 5 0 0 0 5 5h7l5.5 4.5V35.6A5 5 0 0 0 43 31v-6a5 5 0 0 0-5-5h-1.5"/><circle class="dt" cx="14" cy="16.5" r="1.7"/><circle class="dt" cx="20" cy="16.5" r="1.7"/><circle class="dt" cx="26" cy="16.5" r="1.7"/><path class="th" d="M29 31h7M29 34.5h4"/>' },
  { id: "close", name: "Близкие", sub: "переписка и звонки", g: 2, d: '<path class="sf" d="M17 40S5 32.6 5 23.5A6.5 6.5 0 0 1 17 20a6.5 6.5 0 0 1 12 3.5C29 32.6 17 40 17 40z"/><path class="ln" d="M17 40S5 32.6 5 23.5A6.5 6.5 0 0 1 17 20a6.5 6.5 0 0 1 12 3.5C29 32.6 17 40 17 40z"/><path class="sf2" d="M33 24s-8-4.8-8-10.4A4.4 4.4 0 0 1 33 11a4.4 4.4 0 0 1 8 2.6C41 19.2 33 24 33 24z"/><path class="ln" d="M33 24s-8-4.8-8-10.4A4.4 4.4 0 0 1 33 11a4.4 4.4 0 0 1 8 2.6C41 19.2 33 24 33 24z"/><path class="th" d="M10.5 24a3 3 0 0 1 3-2.5M40 32c1.6 1 2.6 2.6 2.8 4.5M37.5 35.5c.8.6 1.3 1.4 1.4 2.4"/><circle class="dt" cx="8" cy="12" r="1.4"/>' },
  { id: "calendar", name: "Календарь", sub: "события и дни", g: 3, d: `<rect class="sf" x="7" y="10" width="34" height="31" rx="7"/><rect class="ln" x="7" y="10" width="34" height="31" rx="7"/><path class="ln" d="M7 19h34M16 6v8M32 6v8"/><text class="tx" x="24" y="35.5" text-anchor="middle">${new Date().getDate()}</text><path class="th" d="M12 24h3M33 24h3"/>` },
  { id: "reminders", name: "Дела", sub: "и напоминания", g: 4, d: '<path class="sf" d="M13 32V22a11 11 0 0 1 22 0v10l3 4H10z"/><path class="ln" d="M13 32V22a11 11 0 0 1 22 0v10l3 4H10z"/><path class="ln" d="M20 40a4.2 4.2 0 0 0 8 0M24 8v3"/><path class="th" d="M6 18a17 17 0 0 1 5-8M42 18a17 17 0 0 0-5-8M3.5 21a21 21 0 0 1 3-10M44.5 21a21 21 0 0 0-3-10"/><circle class="bg" cx="36" cy="33.5" r="6.5"/><circle class="ln" cx="36" cy="33.5" r="6.5"/><path class="ln" d="M33.2 33.6l2 2 3.6-3.8"/>' },
  { id: "notes", name: "Заметки", sub: "поиск, фото, файлы", g: 5, d: '<rect class="sf" x="11" y="7" width="27" height="35" rx="4"/><rect class="ln" x="11" y="7" width="27" height="35" rx="4"/><path class="ln" d="M8 12h6M8 19h6M8 26h6M8 33h6"/><path class="th" d="M19 15h13M19 20h13M19 25h9"/><path class="bg" d="M27.5 37.5l13-13 3 3-13 13-4 1z"/><path class="ln" d="M27.5 37.5l13-13 3 3-13 13-4 1z"/><path class="th" d="M38 27l3 3"/>' },
  { id: "pay", name: "Платежи", sub: "счета и сроки", g: 7, d: '<path class="sf" d="M10 7.5A2.5 2.5 0 0 1 12.5 5h19A2.5 2.5 0 0 1 34 7.5V41l-3.6-2.6-3.6 2.6-3.6-2.6-3.6 2.6-3.6-2.6L10 41z"/><path class="ln" d="M10 7.5A2.5 2.5 0 0 1 12.5 5h19A2.5 2.5 0 0 1 34 7.5V41l-3.6-2.6-3.6 2.6-3.6-2.6-3.6 2.6-3.6-2.6L10 41z"/><path class="th" d="M15 12.5h14M15 17.5h9M15 22.5h11"/><path class="ln" d="M15 29h6"/><circle class="bg" cx="35.5" cy="31.5" r="7.5"/><circle class="ln" cx="35.5" cy="31.5" r="7.5"/><path class="ln" d="M32.2 31.6l2.3 2.3 4.2-4.4"/>' },
  { id: "vault", name: "Сейф", sub: "пароли и коды", g: 4, d: '<rect class="sf" x="9" y="20" width="30" height="22" rx="7"/><rect class="ln" x="9" y="20" width="30" height="22" rx="7"/><path class="ln" d="M16 20v-5.5a8 8 0 0 1 16 0V20"/><circle class="bg" cx="24" cy="30" r="3.4"/><circle class="ln" cx="24" cy="30" r="3.4"/><path class="ln" d="M24 33.4v3.6"/><path class="th" d="M14 26h3M31 26h3"/>' },
  { id: "tasks", name: "Задачи", sub: "большая работа", g: 6, d: '<rect class="sf" x="9" y="9" width="30" height="33" rx="5"/><rect class="ln" x="9" y="9" width="30" height="33" rx="5"/><path class="bg" d="M18 6.5h12a2 2 0 0 1 2 2V12H16V8.5a2 2 0 0 1 2-2z"/><path class="ln" d="M18 6.5h12a2 2 0 0 1 2 2V12H16V8.5a2 2 0 0 1 2-2z"/><path class="ln" d="M14.5 20l2 2 3.6-3.8M14.5 29l2 2 3.6-3.8"/><path class="th" d="M24 20.5h9M24 29.5h9"/><path class="ln" d="M15 37h18" opacity=".35"/><path class="ln" d="M15 37h11"/>' },
  { id: "play", name: "Досуг", sub: "игры на пару минут", g: 7, d: '<path class="sf" d="M15 15h18a10 10 0 0 1 9.6 12.8l-2.2 7.5a5 5 0 0 1-8.6 1.9L28 33h-8l-3.8 4.2a5 5 0 0 1-8.6-1.9l-2.2-7.5A10 10 0 0 1 15 15z"/><path class="ln" d="M15 15h18a10 10 0 0 1 9.6 12.8l-2.2 7.5a5 5 0 0 1-8.6 1.9L28 33h-8l-3.8 4.2a5 5 0 0 1-8.6-1.9l-2.2-7.5A10 10 0 0 1 15 15z"/><path class="ln" d="M15.5 21v7M12 24.5h7"/><circle class="dt" cx="31" cy="22.5" r="2"/><circle class="dt" cx="35" cy="26.5" r="2"/><path class="th" d="M24 6v4M18 8l2 3M30 8l-2 3"/>' },
  { id: "pad", name: "Блокнот", sub: "у виджета", g: 5, d: '<rect class="sf2" x="14" y="5" width="26" height="26" rx="4" transform="rotate(8 27 18)"/><path class="bg" d="M8 12h26v18L26 38H8z"/><path class="sf" d="M8 12h26v18L26 38H8z"/><path class="ln" d="M8 12h26v18L26 38H8z"/><path class="ln" d="M26 38v-8h8"/><path class="th" d="M13 19h16M13 24h11M13 29h7"/><circle class="dt" cx="21" cy="12" r="2.2"/>' },
  { id: "prompter", name: "Суфлёр", sub: "подсказки на встречах", g: 8, d: '<rect class="sf" x="5" y="8" width="38" height="24" rx="5"/><rect class="ln" x="5" y="8" width="38" height="24" rx="5"/><path class="th" d="M11 15h17M11 20h22M11 25h12"/><path class="ln" d="M35 13.5v4M33 15.5h4"/><path class="ln" d="M24 32v8M16 41h16"/><path class="th" d="M38 40a5 5 0 0 0 4-4.5"/>' },
  { id: "memory", name: "Память", sub: "что Лира знает", g: 1, d: '<circle class="sf" cx="24" cy="24" r="17"/><circle class="ln" cx="24" cy="24" r="17"/><ellipse class="th" cx="24" cy="24" rx="17" ry="7"/><ellipse class="th" cx="24" cy="24" rx="7" ry="17"/><path class="ln" d="M14 18l9 5 9-9M23 23l2 11 9-5M14 18l-1 12 12 4"/><circle class="dt" cx="14" cy="18" r="2.2"/><circle class="dt" cx="23" cy="23" r="2.6"/><circle class="dt" cx="32" cy="14" r="2"/><circle class="dt" cx="25" cy="34" r="2"/><circle class="dt" cx="34" cy="29" r="1.6"/><circle class="dt" cx="13" cy="30" r="1.6"/>' },
  { id: "folder", name: "Папка", sub: "файлы ассистента", g: 3, d: '<path class="bg" d="M12 22V7.5h17l5 5V22z"/><path class="ln" d="M12 22V7.5h17l5 5V22"/><path class="th" d="M29 7.5v5h5M16 12.5h8M16 16.5h13"/><path class="bg" d="M5 17a3 3 0 0 1 3-3h8l3.5 4H40a3 3 0 0 1 3 3v15a3 3 0 0 1-3 3H8a3 3 0 0 1-3-3z"/><path class="sf" d="M5 17a3 3 0 0 1 3-3h8l3.5 4H40a3 3 0 0 1 3 3v15a3 3 0 0 1-3 3H8a3 3 0 0 1-3-3z"/><path class="ln" d="M5 17a3 3 0 0 1 3-3h8l3.5 4H40a3 3 0 0 1 3 3v15a3 3 0 0 1-3 3H8a3 3 0 0 1-3-3z"/><path class="th" d="M20 31h8"/>' },
  { id: "ref", name: "Рефералы", sub: "приглашённые", g: 2, d: '<circle class="sf" cx="24" cy="24" r="8"/><circle class="ln" cx="24" cy="21.5" r="3.2"/><path class="ln" d="M18.5 30a5.5 5.5 0 0 1 11 0"/><path class="th" d="M17 18L11 12M31 18l6-6M17 31l-6 5M31 31l6 5"/><circle class="ln" cx="9" cy="10" r="3"/><circle class="ln" cx="39" cy="10" r="3"/><circle class="ln" cx="9" cy="38" r="3"/><circle class="ln" cx="39" cy="38" r="3"/><path class="dt" d="M39 18.5l.8 1.7 1.8.3-1.3 1.3.3 1.8-1.6-.9-1.6.9.3-1.8-1.3-1.3 1.8-.3z"/>' }];
// по умолчанию видно всё (у тех, кто ещё не настраивал, ничего не пропадает); скрытое с главной — скрыто и в меню слева
// (24.10, владелец: «если с главной отключаю „Рефералы“ — то и слева должно исчезать… иначе не решили нахлобученность»)
const HM_DEFAULT = ["chat", "close", "calendar", "reminders", "notes", "pay", "vault", "tasks", "play", "pad", "prompter", "memory", "folder", "ref"];
/* Новые приложения после выпуска (25.10: «Платежи», «Сейф») у тех, кто уже настраивал главную, — появляются сами, в конце:
   ui.home_known — какие значки человек уже видел, когда настраивал; кого там нет — новый. */
const HM_OLD = ["chat", "close", "calendar", "reminders", "notes", "tasks", "play", "pad", "prompter", "memory", "folder", "ref"];
const HM_NAV = { chat: ["chat"], close: ["close"], calendar: ["calendar"], reminders: ["reminders"], notes: ["notes"], tasks: ["tasks"],
  prompter: ["prompter"], memory: ["memory"], folder: ["folder"], ref: ["ref"], pay: ["pay"], vault: ["vault"] };
/* Два разных переключателя (24.10, владелец: «включить или нет вообще — или показать или скрыть, это разное»):
   — здесь, на «Главной», — только ПОКАЗАТЬ / СКРЫТЬ: значок и раздел в меню; сама функция работает (Лира помнит,
     письма близких приходят, напоминания звенят);
   — «Возможности» — ВКЛЮЧИТЬ / ВЫКЛЮЧИТЬ совсем (игры, суфлёр…): выключенное пропадает отовсюду само. */
const HM_FEAT = { play: "games", prompter: "prompter" };
const hmFeat = (id) => !HM_FEAT[id] || (((S && S.features) || {})[HM_FEAT[id]] !== false);
/** Меню слева — по главной: скрытый значок прячет свой раздел; открыт спрятанный раздел — на «Главную». */
function hmNav() {
  if (!S) return;
  const shown = hmApps();
  for (const [id, ps] of Object.entries(HM_NAV)) {
    const off = !shown.includes(id) || !hmFeat(id);
    for (const p of ps) { const b = $(`nav button[data-p="${p}"]`); if (b) b.hidden = off; }
  }
  const cur = $("nav button.cur");
  if (cur && cur.hidden) { const h = $('nav button[data-p="home"]'); if (h) h.click(); }
  $$("nav .ng").forEach(g => {                                   // заголовок группы, под которым всё скрыто, — тоже прочь
    let n = g.nextElementSibling, any = false;
    while (n && !n.classList.contains("ng")) { if (n.tagName === "BUTTON" && !n.hidden) any = true; n = n.nextElementSibling; }
    g.hidden = !any;
  });
}
window.hmNav = hmNav;

/* Группы меню сворачиваются (24.10, владелец: «„Настройка“, „Знания“ — сворачиваемыми, с запоминанием»): щелчок по
   заголовку; что свёрнуто — ui.nav_fold (в настройках, переживает перезапуск). Открытый раздел в свёрнутой группе
   остаётся виден — чтобы было понятно, где вы. */
const ngKey = (g) => g.dataset.k || (g.dataset.k = g.textContent.trim());
function ngApply() {
  const f = new Set(((S && S.ui) || {}).nav_fold || []);
  $$("nav .ng").forEach(g => {
    const on = f.has(ngKey(g));
    g.classList.toggle("fold", on); g.setAttribute("aria-expanded", String(!on));
    let n = g.nextElementSibling;
    while (n && !n.classList.contains("ng")) { if (n.tagName === "BUTTON") n.classList.toggle("folded", on && !n.classList.contains("cur")); n = n.nextElementSibling; }
  });
}
function ngToggle(g) {
  const f = new Set(((S && S.ui) || {}).nav_fold || []), k = ngKey(g);
  f.has(k) ? f.delete(k) : f.add(k);
  const list = [...f];
  if (S) S.ui = Object.assign({}, S.ui, { nav_fold: list });
  ngApply();
  core.call("settings_save", { patch: { ui: { nav_fold: list } } }).catch(() => { });
}
$$("nav .ng").forEach(g => {
  g.setAttribute("role", "button"); g.tabIndex = 0; g.title = "Свернуть или развернуть";
  g.onclick = () => ngToggle(g);
  g.onkeydown = (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); ngToggle(g); } };
});
document.addEventListener("click", (e) => { if (e.target.closest && e.target.closest("nav button[data-p]")) setTimeout(ngApply, 0); });
window.ngApply = ngApply;
const HM_SET = [["personas", "Персонажи"], ["brain", "Мозг"], ["ears", "Слух"], ["voice", "Голос"], ["look", "Оформление"], ["sound", "Звук и поведение"],
  ["hands", "Руки"], ["connect", "Подключение"], ["features", "Возможности"], ["dw", "Dewiar.pro"], ["safety", "Безопасность"], ["about", "О программе"]];
const HM = { edit: false, data: {} };
const hmEsc = (t) => String(t == null ? "" : t).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
/* Плагины на «Главной» (25.10, владелец: «может быть плагины также иметь возможность показывать на главной»): каждый
   установленный плагин — свой значок (его эмодзи и цвет); нажать — «Плагины», открыта его карточка (что сказать,
   настройки). Как и остальные значки, скрывается в «Настроить главную»; новый установленный — появляется сам. */
const hmAll = () => HM_APPS.concat((HM.plg || []).map(p => ({ id: "plg:" + p.id, name: p.name, sub: p.tagline || "плагин", plg: p })));
function hmApps() {
  const u = (S && S.ui) || {}, a = u.home_apps, all = hmAll(), plg = all.filter(x => x.plg).map(x => x.id);
  if (!Array.isArray(a) || !a.length) return HM_DEFAULT.filter(id => all.some(x => x.id === id)).concat(plg);
  const known = Array.isArray(u.home_known) && u.home_known.length ? u.home_known : HM_OLD;
  return a.filter(id => all.some(x => x.id === id)).concat(all.map(x => x.id).filter(id => !known.includes(id) && !a.includes(id)));
}
// personas — «let» из core.js, на window её нет: раньше здесь всегда выходила «Лира», даже у Патрика (отчёт 256).
const hmWho = (id) => {
  const all = (typeof personas !== "undefined" && Array.isArray(personas)) ? personas : [];
  const p = all.find(x => x.id === id) || (!id && all.find(x => x.id === (typeof active !== "undefined" ? active : ""))) || null;
  return (p && p.name) || (id ? id.charAt(0).toUpperCase() + id.slice(1) : "Ассистент");
};
function hmGreet() {
  const h = new Date().getHours(), name = String(((S && S.user_name) || "")).trim().split(/\s+/)[0];
  const w = h < 5 ? "Доброй ночи" : h < 12 ? "Доброе утро" : h < 18 ? "Добрый день" : "Добрый вечер";
  return name ? `${w}, ${name}` : w;
}
function hmDate() { const d = new Date(); const s = d.toLocaleDateString("ru-RU", { weekday: "long", day: "numeric", month: "long" }); return s[0].toUpperCase() + s.slice(1); }
async function loadHome() {
  hmRender();
  if (window.snLoad) snLoad();                          // «Слепок знаний» справа от приветствия (studio/snapshot.js)
  const now = new Date(), get = (c, a) => core.call(c, a).catch(() => null);
  const [cal, cl, tk, dn, ch, pad, py, pl] = await Promise.all([get("calendar_month", { year: now.getFullYear(), month: now.getMonth() + 1 }), get("close_state"),
    get("tasks_list"), get("done"), get("chat_list", { limit: 6 }), get("pad_tabs"), get("pay_overview"), get("plugins")]);
  HM.plg = ((pl && pl.plugins) || []).filter(p => p.installed);
  let padText = null;
  if (pad && pad.active) { const r = await get("pad_read", { name: pad.active }); padText = r ? { name: pad.active, text: r.text || "" } : null; }
  HM.data = { cal, cl, tk: Array.isArray(tk) ? tk : [], dn: dn && typeof dn === "object" ? dn : null, ch, pad: padText,
              py: py && Array.isArray(py.bills) ? py : null };   // старое ядро или заглушка — не массив
  hmRender();
}
function hmToday() {
  const { cal, cl, dn } = HM.data, tk = HM.data.tk || [], out = [], now = new Date(), key = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;   // местная дата, не UTC (после полуночи по Москве)
  const hm = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;
  const today = ((cal && cal.days && cal.days[key]) || []).filter(x => (x.type === "event" || x.type === "reminder") && !x.done && (x.time || "99") >= hm)
    .sort((a, b) => (a.time || "").localeCompare(b.time || ""));
  if (today[0]) out.push({ cls: "next", lab: "Дальше сегодня", b: `${today[0].time ? today[0].time + " — " : ""}${today[0].title}`, s: today.length > 1 ? `и ещё ${today.length - 1} сегодня` : "больше на сегодня ничего", go: today[0].type === "event" ? "calendar" : "reminders" });
  else out.push({ cls: "next", lab: "Сегодня", b: "Дел больше нет", s: "Скажите: «напомни через час…» — и я напомню", go: "reminders" });
  const un = ((cl && cl.people) || []).filter(p => p.unread);
  if (un.length) { const p = un[0], l = p.last && !p.last.out ? (p.last.t || "📎 файл") : "новое сообщение";
    out.push({ cls: "msg", lab: "Близкие", b: `💌 ${p.name}`, s: `«${String(l).slice(0, 60)}»${un.length > 1 ? ` · и ещё от ${un.length - 1}` : ""}`, go: "close" }); }
  const pyb = ((HM.data.py && HM.data.py.bills) || []).filter(b => !b.archived && ["overdue", "soon", "unpaid"].includes(b.now && b.now.s))
    .sort((a, b) => (a.now.s === "overdue" ? 0 : 1) - (b.now.s === "overdue" ? 0 : 1));
  if (pyb.length) { const b = pyb[0], late = b.now.s !== "soon";
    out.push({ cls: late ? "pay late" : "pay", lab: late ? "Не оплачено" : "Скоро срок оплаты", b: `${b.icon || "🧾"} ${b.name}`, s: (late ? "срок был " : "до ") + new Date(b.now.due + "T12:00").toLocaleDateString("ru-RU", { day: "numeric", month: "long" }) + (pyb.length > 1 ? ` · и ещё ${pyb.length - 1}` : ""), go: "pay" }); }
  const w = tk.find(t => t.status === "waiting");
  if (w) out.push({ cls: "task", lab: "Задача ждёт ответа", b: `⏳ ${w.title}`, s: w.question || "откройте и ответьте", go: "tasks" });
  if (dn) out.push({ cls: "done", lab: "Сделано сегодня", b: `${dn.today || 0} ${(dn.today || 0) % 10 === 1 && (dn.today || 0) % 100 !== 11 ? "дело" : [2, 3, 4].includes((dn.today || 0) % 10) && ![12, 13, 14].includes((dn.today || 0) % 100) ? "дела" : "дел"}`,
    s: dn.streak >= 2 ? `🔥 серия ${dn.streak} дн. подряд` : "отметьте сделанное — голосом или в «Делах»", go: "reminders" });
  return out.slice(0, 4);
}
function hmBadge(id) {
  const { cl } = HM.data, tk = HM.data.tk || [];
  if (id === "close") return ((cl && cl.people) || []).reduce((a, p) => a + (p.unread || 0), 0);
  if (id === "tasks") return tk.filter(t => t.status === "waiting").length;
  if (id === "pay") return ((HM.data.py && HM.data.py.bills) || []).filter(b => !b.archived && ["overdue", "soon", "unpaid"].includes(b.now && b.now.s)).length;
  return 0;
}
/* Начало листа блокнота на «Главной» — как в самом блокноте, а не сырой Markdown (25.10, владелец: «там сырой маркдаун
   с решётками»): заголовок, жирное, курсив, код, пункты, задачи, цитаты; схемы и картинки — короткой пометкой. */
function hmPadLines(text, max = 5) {
  const inl = (s) => hmEsc(s.length > 110 ? s.slice(0, 108).replace(/\s+\S*$/, "") + "…" : s)
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1").replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>").replace(/\*\*([^*]+)$/, "<strong>$1</strong>")
    .replace(/(^|[^*\w])\*([^*\n]+)\*/g, "$1<em>$2</em>").replace(/==([^=]+)==/g, "<mark>$1</mark>").replace(/`([^`]+)`/g, "<code>$1</code>");
  const out = []; let fence = null;
  for (const raw of String(text || "").split("\n")) {
    if (out.length >= max) break;
    const l = raw.trim(); let m;
    if (/^```/.test(l)) { if (fence === null) { fence = l.slice(3).trim(); if (fence === "mermaid") out.push('<p class="pv-x">◇ схема</p>'); } else fence = null; continue; }
    if (fence !== null || !l || /^(-{3,}|\*{3,})$/.test(l) || /^\|?\s*:?-{2,}/.test(l)) continue;
    if (/^!\[[^\]]*\]\([^)]*\)$/.test(l)) { out.push('<p class="pv-x">▣ картинка</p>'); continue; }
    if ((m = l.match(/^(#{1,6})\s+(.*)$/))) out.push(`<p class="pv-h${m[1].length > 1 ? " h2" : ""}">${inl(m[2])}</p>`);
    else if ((m = l.match(/^[-*+]\s+\[([ xX])\]\s*(.*)$/))) out.push(`<p class="pv-li pv-t${m[1] !== " " ? " done" : ""}"><i></i>${inl(m[2])}</p>`);
    else if ((m = l.match(/^(?:[-*+•]|\d+[.)])\s+(.*)$/))) out.push(`<p class="pv-li"><i></i>${inl(m[1])}</p>`);
    else if ((m = l.match(/^>\s?(.*)$/))) { if (m[1].trim()) out.push(`<p class="pv-q">${inl(m[1])}</p>`); }
    else if (/^\|.*\|$/.test(l)) out.push(`<p class="pv-x">${inl(l.replace(/^\||\|$/g, "").split("|").map(c => c.trim()).filter(Boolean).join(" · "))}</p>`);
    else out.push(`<p>${inl(l)}</p>`);
  }
  return out;
}
function hmRender() {
  const box = $("#hm-body"); if (!box) return;
  const all = hmAll(), shown = hmApps().filter(hmFeat), list = HM.edit ? shown.map(id => all.find(x => x.id === id)).concat(all.filter(x => !shown.includes(x.id) && hmFeat(x.id))) : shown.map(id => all.find(x => x.id === id));
  $("#hm-greet").textContent = hmGreet(); $("#hm-date").textContent = hmDate();
  const t = hmToday();
  $("#hm-today").innerHTML = t.map(c => `<button class="hm-card ${c.cls}" data-go="${c.go}"><small>${hmEsc(c.lab)}</small><b>${hmEsc(c.b)}</b><span>${hmEsc(c.s)}</span></button>`).join("");
  $("#hm-apps").classList.toggle("edit", HM.edit);
  $("#hm-apps").innerHTML = list.filter(Boolean).map(a => { const on = shown.includes(a.id), n = hmBadge(a.id);
    return `<div class="hm-app${on ? "" : " off"}" data-app="${hmEsc(a.id)}" ${HM.edit ? 'draggable="true"' : ""}><button class="hm-ic${a.plg ? " hm-isplg" : ""}" data-open="${hmEsc(a.id)}" title="${hmEsc(a.name)} — ${hmEsc(a.sub)}"${a.plg ? ` style="--pc:${hmEsc(a.plg.color || "#7c8cff")}"` : ""}>${a.plg ? `<i class="hm-plg" aria-hidden="true">${hmEsc(a.plg.icon || "🧩")}</i>` : HM_SVG(a.g, a.d)}${n && !HM.edit ? `<em>${n}</em>` : ""}</button>`
      + `<b>${hmEsc(a.name)}</b><small>${hmEsc(a.sub)}</small>${HM.edit ? `<label class="tg hm-tg" title="${on ? "Скрыть с главной и из меню (сама функция продолжит работать)" : "Показать на главной и в меню"}"><input type="checkbox" data-tg="${hmEsc(a.id)}" ${on ? "checked" : ""}><i></i></label>` : ""}</div>`; }).join("");
  $("#hm-edit").textContent = HM.edit ? "Готово" : "Настроить главную";
  $("#hm-edit-hint").hidden = !HM.edit;
  const ch = (HM.data.ch && HM.data.ch.items) || [], lastU = [...ch].reverse().find(x => x.role === "user"), lastA = [...ch].reverse().find(x => x.role === "assistant");
  $("#hm-chat").innerHTML = ch.length ? `<small>Последний разговор · ${new Date((lastA || lastU).ts * 1000).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })}</small>`
    + (lastU ? `<p class="u">Вы: ${hmEsc(lastU.text.slice(0, 120))}</p>` : "") + (lastA ? `<p>${hmEsc(hmWho(lastA.who) + ": " + lastA.text.slice(0, 220))}${lastA.text.length > 220 ? "…" : ""}</p>` : "")
    + `<button class="hm-more" data-go="chat">Продолжить в чате</button>` : `<small>Чат</small><p>Здесь появится последний разговор. Можно писать и голосом, и текстом.</p><button class="hm-more" data-go="chat">Открыть чат</button>`;
  const pd = HM.data.pad, lines = pd ? hmPadLines(pd.text) : [];
  $("#hm-pad").innerHTML = `<small>Блокнот${pd ? " · «" + hmEsc(pd.name) + "»" : ""}</small>` + (lines.length ? `<div class="hm-pv">${lines.join("")}</div>` : `<p>Блокнот у виджета — для мыслей на лету. Пишется само.</p>`)
    + `<button class="hm-more" data-pad="1">Открыть блокнот</button>`;
  $("#hm-set").innerHTML = HM_SET.map(([p, n]) => `<button class="hm-pill" data-go="${p}">${hmEsc(n)}</button>`).join("");
  hmWire();
}
function hmGo(p) { const b = $(`nav button[data-p="${p}"]`); if (b) b.click(); }
function hmOpen(id) {
  const a = window.pywebview && window.pywebview.api;
  if (id === "play") { if (a && a.play_open) a.play_open(""); else toast("Игры открываются у виджета: «Лира, давай поиграем»"); return; }
  if (id === "pad") { if (a && a.pad_toggle) a.pad_toggle("notes"); return; }
  if (id.startsWith("plg:")) { plgOpen = id.slice(4); hmGo("skills"); if (PLG.length) plgDrawer(plgOpen); return; }   // карточка плагина — в «Плагинах»
  hmGo(id);
}
function hmSave(list) {
  const known = hmAll().map(x => x.id);
  core.call("settings_save", { patch: { ui: { home_apps: list, home_known: known } } }).then(() => { S.ui = Object.assign({}, S.ui, { home_apps: list, home_known: known }); hmNav(); }).catch(e => toast(e.message));
  S.ui = Object.assign({}, S.ui, { home_apps: list, home_known: known }); hmNav();
}
function hmWire() {
  $$("#hm-body [data-go]").forEach(b => b.onclick = () => hmGo(b.dataset.go));
  $$("#hm-body [data-pad]").forEach(b => b.onclick = () => hmOpen("pad"));
  $$("#hm-apps [data-open]").forEach(b => b.onclick = () => { if (!HM.edit) hmOpen(b.dataset.open); });
  $$("#hm-apps [data-tg]").forEach(i => i.onchange = () => {
    const cur = hmApps(), id = i.dataset.tg, next = i.checked ? cur.concat(cur.includes(id) ? [] : [id]) : cur.filter(x => x !== id);
    if (!next.length) { i.checked = true; toast("Хотя бы один значок оставьте"); return; }
    hmSave(next); hmRender(); });
  if (!HM.edit) return;
  let drag = null;
  $$("#hm-apps .hm-app").forEach(el => {
    el.ondragstart = (e) => { drag = el.dataset.app; el.classList.add("drag"); e.dataTransfer.effectAllowed = "move"; };
    el.ondragend = () => { el.classList.remove("drag"); drag = null; };
    el.ondragover = (e) => { if (drag && drag !== el.dataset.app) { e.preventDefault(); el.classList.add("over"); } };
    el.ondragleave = () => el.classList.remove("over");
    el.ondrop = (e) => { e.preventDefault(); el.classList.remove("over"); const cur = hmApps(); if (!drag || !cur.includes(drag)) return;
      const to = el.dataset.app, list = cur.filter(x => x !== drag), i = list.indexOf(to);
      if (i < 0) return; list.splice(i, 0, drag); hmSave(list); hmRender(); };
  });
}
$("#hm-edit").onclick = () => { HM.edit = !HM.edit; hmRender(); };
const hmCur = () => $("#p-home").classList.contains("cur");
let hmT = 0; const hmSoon = () => { clearTimeout(hmT); hmT = setTimeout(() => { if (hmCur()) loadHome(); }, 400); };
core.on("hello", () => setTimeout(() => { hmNav(); ngApply(); }, 0)).on("settings", () => setTimeout(() => { hmNav(); ngApply(); }, 0)).on("hello", hmSoon).on("close", hmSoon).on("tasks", hmSoon).on("done", hmSoon);
setInterval(() => { if (hmCur() && !document.hidden) hmRender(); }, 60000);    // «Дальше сегодня» и приветствие — по часам
