/* Студия → «Главная» (24.10, владелец: «вот я внутри программы, как бы в её настройках… часть разделов — настройки, раз
   настроил и больше не идёшь, а часть — которыми пользуешься; сделать первичную красивую страничку с иконками, как на
   айфоне… главное — здесь же включить нужное и убрать ненужное»).
   Сверху — приветствие и «Сегодня» (ближайшее дело, письмо близкого, задача ждёт ответа, сделано сегодня); ниже —
   «Приложения» (значки; «Настроить главную» — показать или скрыть, перетащить), «Продолжить» (последний разговор и
   блокнот), «Настройка» (то, что настраивают один раз). Выбор значков — ui.home_apps (порядок и состав). */
const HM_SVG = (g, d) => `<svg viewBox="0 0 24 24" stroke="url(#hg${g})" fill="none" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">${d}</svg>`;
const HM_APPS = [
  { id: "chat", name: "Чат", sub: "с персонажами", g: 1, d: '<path d="M5 18.5V7a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2H8.5z"/><path d="M9 10h6M9 13h3.5"/>' },
  { id: "close", name: "Близкие", sub: "переписка и звонки", g: 2, d: '<path d="M12 19s-7-4.3-7-9.2A3.8 3.8 0 0 1 12 7.6a3.8 3.8 0 0 1 7 2.2C19 14.7 12 19 12 19z"/>' },
  { id: "calendar", name: "Календарь", sub: "события и дни", g: 3, d: '<rect x="4" y="5.5" width="16" height="14" rx="2.5"/><path d="M4 10h16M8.5 3.5v4M15.5 3.5v4M8 14h2M12 14h2"/>' },
  { id: "reminders", name: "Дела", sub: "и напоминания", g: 4, d: '<path d="M6.5 16V11a5.5 5.5 0 0 1 11 0v5l1.5 2h-14zM10 20.5h4"/>' },
  { id: "notes", name: "Заметки", sub: "поиск, фото, файлы", g: 5, d: '<path d="M6.5 3.5h8L18.5 7.5v13h-12z"/><path d="M14.5 3.5v4h4M9.5 12h6M9.5 15.5h4"/>' },
  { id: "tasks", name: "Задачи", sub: "большая работа", g: 6, d: '<path d="M9 6.5h11M9 12h11M9 17.5h11M4 6.5l1.2 1.2L7.5 5.4M4.5 12h2M4.5 17.5h2"/>' },
  { id: "play", name: "Досуг", sub: "игры на пару минут", g: 7, d: '<path d="M7.5 7.5h9a4.5 4.5 0 0 1 4.3 5.8l-1.1 3.7a2.3 2.3 0 0 1-3.9.9L14 15.5h-4l-1.8 2.4a2.3 2.3 0 0 1-3.9-.9l-1.1-3.7a4.5 4.5 0 0 1 4.3-5.8z"/><path d="M8 10.5v3M6.5 12h3M15.5 11h.01M17.5 13h.01"/>' },
  { id: "pad", name: "Блокнот", sub: "у виджета", g: 5, d: '<rect x="5" y="3.5" width="14" height="17" rx="2.5"/><path d="M8.5 8h7M8.5 11.5h7M8.5 15h4"/>' },
  { id: "prompter", name: "Суфлёр", sub: "подсказки на встрече", g: 8, d: '<rect x="3.5" y="5" width="17" height="11" rx="2.5"/><path d="M7 9h10M7 12h6M9 20h6M12 16v4"/>' },
  { id: "memory", name: "Память", sub: "что Лира знает", g: 1, d: '<circle cx="6" cy="6.5" r="2"/><circle cx="18" cy="7.5" r="2"/><circle cx="12" cy="17.5" r="2"/><path d="M7.6 7.8 10.6 15.6M16.5 9 13.3 15.8M8 6.8l8 .5"/>' },
  { id: "folder", name: "Папка", sub: "файлы ассистента", g: 3, d: '<path d="M4 7.5a1.5 1.5 0 0 1 1.5-1.5H10l2 2h6.5A1.5 1.5 0 0 1 20 9.5v8a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 17.5z"/>' },
  { id: "ref", name: "Рефералы", sub: "приглашённые друзья", g: 2, d: '<circle cx="12" cy="12" r="2.2"/><circle cx="5" cy="6" r="1.6"/><circle cx="19" cy="6.5" r="1.6"/><circle cx="6" cy="18.5" r="1.6"/><circle cx="18.5" cy="18" r="1.6"/><path d="M6.3 7.1 10.4 10.6M17.7 7.6l-4 3.1M7.4 17.5l3.1-3.8M17.2 17l-3.4-3.3"/>' }];
const HM_DEFAULT = ["chat", "close", "calendar", "reminders", "notes", "tasks", "play", "pad"];
const HM_SET = [["personas", "Персонажи"], ["brain", "Мозг"], ["ears", "Слух"], ["voice", "Голос"], ["look", "Оформление"], ["sound", "Звук и поведение"],
  ["hands", "Руки"], ["connect", "Подключение"], ["features", "Возможности"], ["dw", "Dewiar.pro"], ["safety", "Безопасность"], ["about", "О программе"]];
const HM = { edit: false, data: {} };
const hmEsc = (t) => String(t == null ? "" : t).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
function hmApps() { const a = ((S && S.ui) || {}).home_apps; return Array.isArray(a) && a.length ? a.filter(id => HM_APPS.some(x => x.id === id)) : HM_DEFAULT.slice(); }
function hmGreet() {
  const h = new Date().getHours(), name = String(((S && S.user_name) || "")).trim().split(/\s+/)[0];
  const w = h < 5 ? "Доброй ночи" : h < 12 ? "Доброе утро" : h < 18 ? "Добрый день" : "Добрый вечер";
  return name ? `${w}, ${name}` : w;
}
function hmDate() { const d = new Date(); const s = d.toLocaleDateString("ru-RU", { weekday: "long", day: "numeric", month: "long" }); return s[0].toUpperCase() + s.slice(1); }
async function loadHome() {
  hmRender();
  const now = new Date(), get = (c, a) => core.call(c, a).catch(() => null);
  const [cal, cl, tk, dn, ch, pad] = await Promise.all([get("calendar_month", { year: now.getFullYear(), month: now.getMonth() + 1 }), get("close_state"),
    get("tasks_list"), get("done"), get("chat_list", { limit: 6 }), get("pad_tabs")]);
  let padText = null;
  if (pad && pad.active) { const r = await get("pad_read", { name: pad.active }); padText = r ? { name: pad.active, text: r.text || "" } : null; }
  HM.data = { cal, cl, tk: Array.isArray(tk) ? tk : [], dn: dn && typeof dn === "object" ? dn : null, ch, pad: padText };   // старое ядро или заглушка — не массив
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
  return 0;
}
function hmRender() {
  const box = $("#hm-body"); if (!box) return;
  const shown = hmApps(), list = HM.edit ? shown.map(id => HM_APPS.find(x => x.id === id)).concat(HM_APPS.filter(x => !shown.includes(x.id))) : shown.map(id => HM_APPS.find(x => x.id === id));
  $("#hm-greet").textContent = hmGreet(); $("#hm-date").textContent = hmDate();
  const t = hmToday();
  $("#hm-today").innerHTML = t.map(c => `<button class="hm-card ${c.cls}" data-go="${c.go}"><small>${hmEsc(c.lab)}</small><b>${hmEsc(c.b)}</b><span>${hmEsc(c.s)}</span></button>`).join("");
  $("#hm-apps").classList.toggle("edit", HM.edit);
  $("#hm-apps").innerHTML = list.filter(Boolean).map(a => { const on = shown.includes(a.id), n = hmBadge(a.id);
    return `<div class="hm-app${on ? "" : " off"}" data-app="${a.id}" ${HM.edit ? 'draggable="true"' : ""}><button class="hm-ic" data-open="${a.id}" title="${hmEsc(a.name)} — ${hmEsc(a.sub)}">${HM_SVG(a.g, a.d)}${n && !HM.edit ? `<em>${n}</em>` : ""}</button>`
      + `<b>${hmEsc(a.name)}</b><small>${hmEsc(a.sub)}</small>${HM.edit ? `<label class="tg hm-tg" title="${on ? "Скрыть с главной" : "Показать на главной"}"><input type="checkbox" data-tg="${a.id}" ${on ? "checked" : ""}><i></i></label>` : ""}</div>`; }).join("");
  $("#hm-edit").textContent = HM.edit ? "Готово" : "Настроить главную";
  $("#hm-edit-hint").hidden = !HM.edit;
  const ch = (HM.data.ch && HM.data.ch.items) || [], lastU = [...ch].reverse().find(x => x.role === "user"), lastA = [...ch].reverse().find(x => x.role === "assistant");
  $("#hm-chat").innerHTML = ch.length ? `<small>Последний разговор · ${new Date((lastA || lastU).ts * 1000).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })}</small>`
    + (lastU ? `<p class="u">Вы: ${hmEsc(lastU.text.slice(0, 120))}</p>` : "") + (lastA ? `<p>${hmEsc((lastA.who || "Лира") + ": " + lastA.text.slice(0, 220))}${lastA.text.length > 220 ? "…" : ""}</p>` : "")
    + `<button class="hm-more" data-go="chat">Продолжить в чате</button>` : `<small>Чат</small><p>Здесь появится последний разговор. Можно писать и голосом, и текстом.</p><button class="hm-more" data-go="chat">Открыть чат</button>`;
  const pd = HM.data.pad, lines = pd ? pd.text.split("\n").map(s => s.replace(/^#+\s*|^[-*]\s+|^\d+\.\s+|^\[[ x]\]\s*/g, "").trim()).filter(Boolean) : [];
  $("#hm-pad").innerHTML = `<small>Блокнот${pd ? " · «" + hmEsc(pd.name) + "»" : ""}</small>` + (lines.length ? `<b>${hmEsc(lines[0].slice(0, 60))}</b><ul>${lines.slice(1, 4).map(l => `<li>${hmEsc(l.slice(0, 70))}</li>`).join("")}</ul>` : `<p>Блокнот у виджета — для мыслей на лету. Пишется само.</p>`)
    + `<button class="hm-more" data-pad="1">Открыть блокнот</button>`;
  $("#hm-set").innerHTML = HM_SET.map(([p, n]) => `<button class="hm-pill" data-go="${p}">${hmEsc(n)}</button>`).join("");
  hmWire();
}
function hmGo(p) { const b = $(`nav button[data-p="${p}"]`); if (b) b.click(); }
function hmOpen(id) {
  const a = window.pywebview && window.pywebview.api;
  if (id === "play") { if (a && a.play_open) a.play_open(""); else toast("Игры открываются у виджета: «Лира, давай поиграем»"); return; }
  if (id === "pad") { if (a && a.pad_toggle) a.pad_toggle("notes"); return; }
  hmGo(id);
}
function hmSave(list) { core.call("settings_save", { patch: { ui: { home_apps: list } } }).then(() => { S.ui = Object.assign({}, S.ui, { home_apps: list }); }).catch(e => toast(e.message)); S.ui = Object.assign({}, S.ui, { home_apps: list }); }
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
core.on("hello", hmSoon).on("close", hmSoon).on("tasks", hmSoon).on("done", hmSoon);
setInterval(() => { if (hmCur() && !document.hidden) hmRender(); }, 60000);    // «Дальше сегодня» и приветствие — по часам
