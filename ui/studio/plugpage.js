/* Страница плагина (03.11, владелец: «плагин включён, появляются команды для запуска, а должен быть целый раздел под плагин,
   где его можно настраивать и взаимодействовать. Каждый плагин — своя страничка в Лире: свой интерфейс, свои функции,
   настройки. А то Лира что-то начинает делать — и на этом всё, не работает НИЧЕГО»).
   Меню слева → группа «Плагины»: пункт на каждый установленный плагин (значок, название), появляется и исчезает при
   установке и удалении без перезапуска. Раздел p-plg один на все плагины — открывает его скрытая кнопка nav data-p="plg".
   Страница: шапка (значок, что делает, состояние серверов — с причиной и «Перезапустить», ролик) и вкладки:
     • своя страница плагина — ui.html во фрейме-песочнице (sandbox="allow-scripts", без same-origin; CSP без сети) с мостом
       window.dewiar: run(действие, аргументы) — только СВОИ действия плагина, settings()/saveSettings(), open(путь) — только
       файлы из папок плагина (проверяет ядро), openUrl(адрес) — http(s) в браузере по нажатию, ask(фраза) — в «Чат». Фрейм ушёл со своей страницы — мост молчит;
       у «Художника» вместо ui.html — его «Рисунки»;
     • «Сделать сейчас» — карточка на каждое действие (форма из inputSchema, человеческие подписи из plugin.json ui.tools),
       «Выполнить» зовёт ядро plugin_run напрямую, без модели; ответ — данными (таблицы, файлы с «Открыть», картинки),
       текст — Markdown; ошибка — словами; пока идёт — крутилка и секунды. Ниже — «Попросить Лиру» (ui.asks: форма →
       фраза в «Чат») и «Попробуйте сказать»;
     • «Настройки» — поля плагина (сохраняются сразу) и дела по расписанию;
     • «Файлы» — последние файлы плагина (plugin_files), открытие — plugin_open.
   Ядро: core/plugin_pages.py (команды plugin_page / plugin_run / plugin_restart / plugin_files / plugin_open / plugin_ui).
   Creator (03.11): плагин, сделанный Лирой по описанию (p.made), — вкладки «Изменить» (правка словами и «Версии» с откатом,
   plugin_change / plugin_restore / plugin_undo) и «Доступ» (какие данные Лиры странице разрешены — plugin_grant). Мост
   страницы шире: dewiar.store.get/set (своё хранилище), dewiar.data(область) — только объявленное в plugin.json и только
   после «Разрешить» человека, dewiar.theme(цвета) — у плагина с theme: true, по нажатию; dewiar.readUrl(адрес) — текст
   статьи (по нажатию; у плагина с доступом к данным — всегда с вопросом). Ядро — core/plugin_bridge.py, создание —
   studio/plugmake.js. */
const PLP = { known: {}, cur: "", page: null, tab: "", cat: [], nav: "", poll: 0, frameLoads: 0, busy: {}, asking: {} };
// данные Лиры, которые плагин может попросить (как plugins.DATA_SCOPES в ядре): что сказать человеку в вопросе
const PLP_SCOPES = { notes: ["заметки", "названия и текст ваших заметок"], reminders: ["напоминания и дела", "что и когда напомнить"],
  money: ["расходы и доходы", "суммы, категории и даты"], chat_stats: ["статистику разговоров", "сколько сообщений по дням и часам, с кем из персонажей и частые слова — без текста"],
  chat: ["текст переписки", "ваши сообщения и ответы Лиры целиком"] };
const plpEsc = (t) => String(t ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
// подписи, если плагин не дал своих (чтобы на странице не было сырых query, limit, path)
const PLP_WORDS = { query: "Запрос", q: "Слова", limit: "Сколько показать", path: "Файл или папка", folder: "Папка", file: "Файл", title: "Название",
  text: "Текст", name: "Имя", id: "Номер", url: "Адрес", size: "Размер", count: "Сколько", total: "Всего", items: "Список", note: "Заметка",
  stage: "Этап", city: "Город", date: "Дата", at: "Когда", from: "С", to: "По", price: "Цена", score: "Балл", error: "Ошибка", status: "Состояние",
  description: "Описание", email: "Почта", phone: "Телефон", saved: "Файл", page: "Страница", amount: "Сумма", currency: "Валюта" };
const plpWord = (k) => PLP_WORDS[k] || (String(k).replace(/[_-]+/g, " ").replace(/^./, c => c.toUpperCase()));
const plpPlugin = () => (PLP.page && PLP.page.plugin) || {};
// say — подсказка ответа для самой Лиры («скажи это одной фразой»), id — внутренний номер: человеку не показываем
// ctx — ключ, под которым лежат эти данные: «ranking.total» — «Балл», просто «total» — «Всего»
const plpLabel = (k, ctx) => { const l = ((plpPlugin().ui || {}).labels || {}); if (ctx && (ctx + "." + k) in l) return l[ctx + "." + k]; return k in l ? l[k] : (k === "say" || k === "id") ? "" : plpWord(k); };
const plpKind = { image: "🖼", page: "🌐", doc: "📄", media: "🎬", table: "📊", folder: "📁", file: "📎" };
const plpWhen = (s) => { const d = new Date(typeof s === "number" ? s * 1000 : s); return isNaN(d) ? "" : d.toLocaleString("ru-RU", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }); };
const plpSize = (n) => n > 1e6 ? (n / 1e6).toFixed(1).replace(".", ",") + " МБ" : n > 1e3 ? Math.round(n / 1e3) + " КБ" : (n || 0) + " Б";

/* ---------- меню: группа «Плагины» ---------- */
function plpNav(list) {
  if (Array.isArray(list)) PLP.cat = list;
  const box = $("#nav-plugins"), head = $("#nav-plg-h"); if (!box) return;
  const rank = typeof hmOrder === "function" ? hmOrder() : null;          // №558: в порядке значков на «Главной»
  const on = PLP.cat.filter(p => p.installed).map((p, i) => [p, i])
    .sort((a, b) => ((rank && rank["plg:" + a[0].id]) ?? 1e6) - ((rank && rank["plg:" + b[0].id]) ?? 1e6) || a[1] - b[1]).map(x => x[0]);
  const key = on.map(p => p.id + p.icon + p.name).join("|");
  box.hidden = !on.length; head.hidden = false;           // «Создать плагин» — всегда в группе
  if (key !== PLP.nav) {
    PLP.nav = key;
    box.innerHTML = on.map(p => `<button class="nav-g nav-plg" data-plg="${plpEsc(p.id)}" title="${plpEsc(p.tagline || p.name)}" style="--pc:${plpEsc(p.color)}"><i class="nav-gi emo nav-pi" aria-hidden="true">${plpEsc(p.icon)}</i><span>${plpEsc(p.name)}</span></button>`).join("");
    $$("#nav-plugins .nav-plg").forEach(b => b.onclick = () => plpOpen(b.dataset.plg));
  }
  plpNavCur();
  if (PLP.cur && $("#p-plg.cur") && !on.some(p => p.id === PLP.cur)) {      // удалили плагин, пока смотрели его страницу
    PLP.cur = ""; const b = $('nav button[data-p="skills"]'); if (b) b.click();
  }
}
function plpNavCur() { const here = !!$("#p-plg.cur"); $$("#nav-plugins .nav-plg").forEach(x => x.classList.toggle("cur", here && x.dataset.plg === PLP.cur)); }
function plpCatalog() { return core.call("plugins").then(r => { plpNav(r.plugins || []); return r; }).catch(() => {}); }
// каталог в «Плагинах» обновился (установили, удалили) — и меню тоже
if (typeof plgSet === "function") { const _plgSet = plgSet; plgSet = function (r) { _plgSet(r); plpNav((r && r.plugins) || PLP.cat); if (PLP.cur && $("#p-plg.cur") && r && r.plugins) plpRefresh(); }; }

function plpOpen(id, tab) {
  if (PLP.cur !== id) { PLP.tab = ""; PLP.page = null; }
  PLP.cur = id; if (tab) PLP.tab = tab;
  const b = $('nav button[data-p="plg"]'); if (b && !$("#p-plg.cur")) b.click();
  $("#p-plg").classList.add("cur"); plpNavCur();
  try { history.replaceState(null, "", "#plg:" + id); } catch (e) { }
  plpLoad();
}
window.plpOpen = plpOpen;
async function plpLoad() {
  const id = PLP.cur, box = $("#plp"); if (!id || !box) return;
  if (!PLP.page || PLP.page.plugin.id !== id) box.innerHTML = `<div class="plp-loading"><i class="plp-spin"></i> Открываю плагин…</div>`;
  let r;
  try { r = await core.call("plugin_page", { id }); } catch (e) { box.innerHTML = `<p class="plp-err">${plpEsc(e.message)}</p>`; return; }
  if (id !== PLP.cur) return;
  if (!r || !r.plugin) { box.innerHTML = `<p class="plp-err">Плагин не нашёлся — он установлен? Студия → «Плагины».</p>`; return; }   // старое ядро
  PLP.page = r; plpKnow(r); plpRender();
  clearTimeout(PLP.poll);
  if (r.state === "connecting") PLP.poll = setTimeout(() => { if ($("#p-plg.cur") && PLP.cur === id) plpRefresh(); }, 1500);
}
// без перерисовки форм и результатов: только шапка и состояние (сервер подключился, настройки поменяли)
async function plpRefresh() {
  const id = PLP.cur; let r;
  try { r = await core.call("plugin_page", { id }); } catch (e) { return; }
  if (id !== PLP.cur || !PLP.page || !r || !r.plugin) return;
  // перерисовать карточки — только на «Сделать сейчас» и когда действия плагина правда поменялись; своя страница (фрейм),
  // настройки и файлы не трогаем: сервер перезапускается после каждой настройки, а фрейм потерял бы, что в нём делали
  const sig = (p) => p.state + "|" + p.tools.map(t => t.name).join(",");
  const was = sig(PLP.page), wasOk = PLP.page.state === "ok";
  PLP.page = r; plpKnow(r);
  if (PLP.tab === "do" && was !== sig(r) && (r.state !== "connecting" || !wasOk)) plpRender(); else plpHead();
  clearTimeout(PLP.poll);
  if (r.state === "connecting") PLP.poll = setTimeout(() => { if ($("#p-plg.cur") && PLP.cur === id) plpRefresh(); }, 1500);
}

// действия плагина, которые уже видели: пока сервер перезапускается (новые настройки), список пуст, а мост своей страницы
// должен ждать сервер, а не отказывать (ядро всё равно пускает только к своим действиям плагина)
function plpKnow(r) { if (r && r.state === "ok" && r.plugin) PLP.known[r.plugin.id] = r.tools.map(t => t.name); }
/* ---------- шапка ---------- */
function plpState() {
  const r = PLP.page, p = r.plugin, n = r.tools.filter(t => !t.page_only && !t.hidden).length;
  if (!p.installed) return `<div class="plp-st off"><i></i><span>Не установлен</span><button class="btn small primary" id="plp-install">Установить</button></div>`;
  if (p.made && r.state === "none") { const v = (r.versions || {}).current || 1;
    return `<div class="plp-st ok"><i></i><span>Сделан Лирой · версия ${v}</span><button class="btn small ghost" data-goto="edit">Изменить словами</button></div>`; }
  if (r.state === "none") return `<div class="plp-st ok"><i></i><span>Работает через разговор с Лирой — ничего запускать не нужно</span></div>`;
  if (r.state === "connecting") return `<div class="plp-st wait"><i class="plp-spin"></i><span>Запускается…</span></div>`;
  if (r.state === "error") return `<div class="plp-st bad"><i></i><span><b>Не запустился.</b> ${plpEsc(r.error)}</span><button class="btn small" id="plp-restart">Перезапустить</button></div>`;
  return `<div class="plp-st ok"><i></i><span>Работает${n ? ` · ${n} ${n === 1 ? "действие" : n < 5 ? "действия" : "действий"}` : ""}</span><button class="btn small ghost" id="plp-restart" title="Остановить и запустить программу плагина заново">Перезапустить</button></div>`;
}
function plpHead() {
  const p = PLP.page.plugin, h = $("#plp-head"); if (!h) return;
  h.innerHTML = `<i class="plg-ic plp-ic" aria-hidden="true">${plpEsc(p.icon)}</i>
    <div class="plp-ht"><h1>${plpEsc(p.name)}</h1><p>${plpEsc(p.tagline)}</p>${plpState()}</div>
    <div class="plp-hb">${p.video ? `<button class="btn" id="plp-video">▶ Видеоурок</button>` : ""}<button class="btn ghost" id="plp-more" title="Описание, что внутри, удалить">О плагине</button></div>`;
  const rs = $("#plp-restart"); if (rs) rs.onclick = async () => {
    rs.disabled = true; rs.textContent = "Перезапускаю…";
    try { PLP.page = await core.call("plugin_restart", { id: p.id }); plpHead(); clearTimeout(PLP.poll); PLP.poll = setTimeout(plpRefresh, 1200); toast("Плагин перезапускается"); }
    catch (e) { toast(e.message); rs.disabled = false; rs.textContent = "Перезапустить"; } };
  const ins = $("#plp-install"); if (ins) ins.onclick = () => core.call("plugin_install", { id: p.id, values: {} }).then(r => { plgSet(r); toast(`«${p.name}» установлен`); plpLoad(); }).catch(e => toast(e.message));
  const v = $("#plp-video"); if (v) v.onclick = () => plpVideo(p);
  $$("#plp-head [data-goto]").forEach(b => b.onclick = () => plpTab(b.dataset.goto));
  $("#plp-more").onclick = () => { const b = $('nav button[data-p="skills"]'); if (b) b.click(); plgOpen = p.id; setTimeout(() => plgDrawer(p.id), PLG.length ? 0 : 400); if (!PLG.length) loadPlugins(); };
}
async function plpVideo(p) {
  if (/^https:\/\//.test(p.video)) { if (typeof openExt === "function") openExt(p.video); return; }
  try { const r = await core.call("academy_list"); const l = ((r && r.items) || []).find(x => x.id === p.video);
    if (l && typeof lsPlay === "function") return lsPlay(l); } catch (e) { }
  const b = $('nav button[data-p="lessons"]'); if (b) b.click();
}

/* ---------- страница и вкладки ---------- */
function plpTabs() {
  const r = PLP.page, p = r.plugin, tabs = [];
  if (p.page && p.installed) tabs.push(["page", (p.ui && p.ui.page_title) || "Своя страница"]);
  if (p.id === "artist" && p.installed) tabs.push(["art", "Рисунки"]);
  if (!p.made || r.tools.length || (p.ui && (p.ui.asks || []).length)) tabs.push(["do", "Сделать сейчас"]);
  if (p.made) tabs.push(["edit", "Изменить и версии"]);
  if ((p.data || []).length || p.theme) tabs.push(["access", "Доступ"]);
  if (p.settings.length || p.jobs.length) tabs.push(["set", "Настройки"]);
  if (!p.made || r.tools.length) tabs.push(["files", "Файлы"]);
  return tabs;
}
function plpRender() {
  const r = PLP.page, p = r.plugin, box = $("#plp");
  const tabs = plpTabs();
  if (!tabs.some(t => t[0] === PLP.tab)) PLP.tab = tabs[0][0];
  box.style.setProperty("--pc", p.color);
  box.innerHTML = `<header class="plp-head" id="plp-head"></header>
    <div class="stabs plp-tabs" role="tablist">${tabs.map(([k, t]) => `<button role="tab" data-tab="${k}" class="${k === PLP.tab ? "on" : ""}" aria-selected="${k === PLP.tab}">${plpEsc(t)}</button>`).join("")}</div>
    <div id="plp-body"></div>`;
  plpHead();
  $$("#plp .plp-tabs button").forEach(b => b.onclick = () => plpTab(b.dataset.tab));
  plpBody();
}
function plpTab(k) {
  PLP.tab = k; $$("#plp .plp-tabs button").forEach(x => { const on = x.dataset.tab === k; x.classList.toggle("on", on); x.setAttribute("aria-selected", on); }); plpBody();
}
function plpBody() {
  const b = $("#plp-body"); if (!b) return;
  if (PLP.tab === "page") return plpFrame(b);
  if (PLP.tab === "art") return plpArt(b);
  if (PLP.tab === "set") return plpSettings(b);
  if (PLP.tab === "files") return plpFiles(b);
  if (PLP.tab === "edit") return plpEdit(b);
  if (PLP.tab === "access") return plpAccess(b);
  return plpDo(b);
}

/* ---------- «Сделать сейчас» ---------- */
function plpDo(box) {
  const r = PLP.page, p = r.plugin, ui = p.ui || {};
  const tools = r.tools.filter(t => !t.hidden && !t.page_only);
  const asks = p.installed ? (ui.asks || []) : [];
  let h = "";
  if (tools.length) h += `<h2 class="plp-h2">Сделать сейчас <small>сразу, без разговора</small></h2><div class="plp-grid">${tools.map(plpToolCard).join("")}</div>`;
  else if (r.state === "connecting") h += `<p class="plp-loading"><i class="plp-spin"></i> Плагин запускается — его действия появятся здесь через несколько секунд.</p>`;
  else if (r.state === "error") h += `<div class="plp-err"><b>Действия плагина сейчас не работают.</b> ${plpEsc(r.error)} Нажмите «Перезапустить» вверху; если не поможет — откройте «О плагине».</div>`;
  if (asks.length) h += `<h2 class="plp-h2">Попросить Лиру <small>ответит в «Чате»</small></h2><div class="plp-grid">${asks.map((a, i) => plpAskCard(a, i)).join("")}</div>`;
  if (p.phrases.length) h += `<h2 class="plp-h2">Сказать Лире <small>${p.installed ? "нажмите — и фраза уйдёт в «Чат»" : "после установки"}</small></h2>
    <div class="plp-say">${p.phrases.map(t => `<button class="chip" data-say="${plpEsc(t)}" ${p.installed ? "" : "disabled"}>«${plpEsc(t)}»</button>`).join("")}</div>`;
  if (!h) h = `<p class="hint">У этого плагина пока нет действий.</p>`;
  box.innerHTML = h;
  $$("#plp-body .plp-tool").forEach(plpWireTool);
  $$("#plp-body .plp-ask").forEach(plpWireAsk);
  $$("#plp-body [data-say]").forEach(b => b.onclick = () => plpAsk(b.dataset.say));
}
function plpAsk(text) { if (typeof qaAsk === "function") qaAsk(text); else core.call("say", { text }).catch(() => {}); }

function plpProps(t) { const s = t.schema || {}; return Object.entries(s.properties || {}).filter(([k]) => t.fields[k] !== false || (s.required || []).includes(k)); }
function plpField(t, k, s, req) {
  const f = (t.fields || {})[k] || {}, id = `ppf-${t.name}-${k}`.replace(/[^\w-]/g, "_");
  const label = f.label || s.title || (s.description && s.description.length < 48 ? s.description.replace(/^./, c => c.toUpperCase()) : "") || plpWord(k);
  const hint = f.hint || (s.description && s.description.length >= 48 && !f.label ? s.description : "");
  const ph = f.placeholder || "";
  const lab = `<span class="plp-fl">${plpEsc(label)}${req ? ` <em title="обязательно">*</em>` : ""}</span>`;
  const hn = hint ? `<small class="plp-fh">${plpEsc(hint)}</small>` : "";
  const typ = Array.isArray(s.type) ? s.type.find(x => x !== "null") : s.type;
  if (s.enum) return `<label class="f">${lab}<select id="${id}" data-a="${plpEsc(k)}" data-t="enum">${req ? "" : `<option value="">— любой —</option>`}${s.enum.map(o => `<option ${String(o) === String(s.default ?? "") ? "selected" : ""}>${plpEsc(o)}</option>`).join("")}</select>${hn}</label>`;
  if (typ === "boolean") return `<div class="switch slim plp-sw"><div>${plpEsc(label)}${hint ? `<span>${plpEsc(hint)}</span>` : ""}</div><label class="tg"><input type="checkbox" id="${id}" data-a="${plpEsc(k)}" data-t="bool" ${s.default ? "checked" : ""}><i></i></label></div>`;
  if (typ === "integer" || typ === "number") return `<label class="f plp-num">${lab}<input type="number" id="${id}" data-a="${plpEsc(k)}" data-t="${typ}" ${s.minimum != null ? `min="${+s.minimum}"` : ""} ${s.maximum != null ? `max="${+s.maximum}"` : ""} value="${s.default ?? ""}" placeholder="${plpEsc(ph)}">${hn}</label>`;
  if (typ === "array") {
    const it = (s.items || {}).type || "string";
    return `<label class="f plp-wide">${lab}<textarea id="${id}" data-a="${plpEsc(k)}" data-t="list" data-it="${plpEsc(it)}" rows="3" placeholder="${plpEsc(ph || "по одному в строке")}"></textarea>${hn || `<small class="plp-fh">По одному в строке</small>`}</label>`;
  }
  if (typ === "object" && s.properties) {
    return `<fieldset class="plp-obj plp-wide" data-a="${plpEsc(k)}" data-t="obj"><legend>${plpEsc(label)}</legend>${Object.entries(s.properties).map(([kk, ss]) =>
      `<label class="f plp-num">${plpEsc(plpLabel(kk))}<input type="${ss.type === "number" || ss.type === "integer" ? "number" : "text"}" data-k="${plpEsc(kk)}" data-t="${plpEsc(ss.type || "string")}"></label>`).join("")}</fieldset>`;
  }
  if (typ === "object" || typ === "array") return `<label class="f plp-wide">${lab}<textarea id="${id}" data-a="${plpEsc(k)}" data-t="json" rows="3" placeholder="{ }"></textarea>${hn}</label>`;
  const pathy = f.kind === "path" || f.kind === "folder" || f.kind === "file" || /(^|_)(path|folder|dir|file)s?$/.test(k);
  if (pathy) return `<label class="f plp-wide">${lab}<span class="pld-dir"><input type="text" id="${id}" data-a="${plpEsc(k)}" data-t="str" placeholder="${plpEsc(ph)}">`
    + `${f.kind !== "folder" ? `<button class="btn small" type="button" data-pick="file">Файл…</button>` : ""}${f.kind !== "file" ? `<button class="btn small" type="button" data-pick="folder">Папка…</button>` : ""}</span>${hn}</label>`;
  const long = f.kind === "long" || (s.maxLength || 0) > 300 || /^(text|svg|code|prompt|body|content|description|html|markdown)$/.test(k);
  if (long) return `<label class="f plp-wide">${lab}<textarea id="${id}" data-a="${plpEsc(k)}" data-t="str" rows="4" placeholder="${plpEsc(ph)}"></textarea>${hn}</label>`;
  return `<label class="f">${lab}<input type="text" id="${id}" data-a="${plpEsc(k)}" data-t="str" placeholder="${plpEsc(ph)}" value="${plpEsc(s.default ?? "")}">${hn}</label>`;
}
function plpToolCard(t) {
  const req = (t.schema && t.schema.required) || [];
  const props = plpProps(t);
  return `<article class="plp-tool plp-card" data-tool="${plpEsc(t.name)}">
    <div class="plp-ct"><b>${plpEsc(t.title)}</b>${t.readonly ? "" : `<span class="plp-tag" title="Плагин что-то меняет или отправляет">меняет данные</span>`}</div>
    ${t.hint || t.description ? `<p class="plp-cd">${plpEsc(t.hint || t.description)}</p>` : ""}
    ${props.length ? `<div class="plp-form">${props.map(([k, s]) => plpField(t, k, s, req.includes(k))).join("")}</div>` : ""}
    <div class="plp-run"><button class="btn primary" data-run>${plpEsc(t.button || "Выполнить")}</button><span class="plp-busy" hidden><i class="plp-spin"></i><span>Выполняю…</span> <b>0 с</b></span><span class="plp-ms"></span></div>
    <div class="plp-out" aria-live="polite"></div></article>`;
}
function plpArgs(card, t) {
  const args = {}, req = (t.schema && t.schema.required) || [], miss = [];
  $$("[data-a]", card).forEach(el => {
    const k = el.dataset.a, typ = el.dataset.t; let v;
    if (typ === "bool") v = el.checked;                // всегда явно: иначе у сервера своё «по умолчанию» (only_new — да)
    else if (typ === "obj") { const o = {}; $$("[data-k]", el).forEach(x => { if (x.value.trim() === "") return; o[x.dataset.k] = /number|integer/.test(x.dataset.t) ? Number(x.value) : x.value; }); if (!Object.keys(o).length) { if (req.includes(k)) miss.push(k); return; } v = o; }
    else {
      const raw = el.value.trim();
      if (raw === "") { if (req.includes(k)) miss.push(k); return; }
      if (typ === "integer") v = parseInt(raw, 10); else if (typ === "number") v = Number(raw.replace(",", "."));
      else if (typ === "list") { v = raw.split(/\n|;/).map(x => x.trim()).filter(Boolean); if (/number|integer/.test(el.dataset.it)) v = v.map(Number); }
      else if (typ === "json") { try { v = JSON.parse(raw); } catch (e) { throw new Error(`«${plpLabel(k)}»: не получилось прочитать — проверьте скобки и кавычки`); } }
      else v = raw;
    }
    args[k] = v;
  });
  if (miss.length) { const el = $(`[data-a="${miss[0]}"]`, card); const lab = el && el.closest("label,fieldset"); throw new Error(`Заполните «${lab ? (lab.querySelector(".plp-fl,legend") || lab).textContent.replace("*", "").trim() : plpLabel(miss[0])}»`); }
  return args;
}
function plpWireTool(card) {
  const t = PLP.page.tools.find(x => x.name === card.dataset.tool); if (!t) return;
  $$("[data-pick]", card).forEach(b => b.onclick = async () => {
    const a = window.api && window.api(), inp = b.closest(".pld-dir").querySelector("input");
    const fn = b.dataset.pick === "folder" ? "pick_folder" : "pick_file";
    if (!a || !a[fn]) return toast("Выбор доступен в окне студии — или впишите путь вручную");
    const path = await a[fn](); if (path) inp.value = path;
  });
  $$("input[type=text], input[type=number]", card).forEach(i => i.onkeydown = (e) => { if (e.key === "Enter") { e.preventDefault(); $("[data-run]", card).click(); } });
  $("[data-run]", card).onclick = () => plpRun(card, t);
}
async function plpRun(card, t) {
  const out = $(".plp-out", card), btn = $("[data-run]", card), busy = $(".plp-busy", card), ms = $(".plp-ms", card);
  let args;
  try { args = plpArgs(card, t); } catch (e) { out.innerHTML = `<div class="plp-err plp-small">${plpEsc(e.message)}</div>`; return; }
  const pid = PLP.cur, t0 = Date.now();
  btn.disabled = true; busy.hidden = false; ms.textContent = ""; card.classList.add("busy");
  const tick = setInterval(() => { const s = Math.round((Date.now() - t0) / 1000); $("b", busy).textContent = s < 60 ? `${s} с` : `${Math.floor(s / 60)} мин ${s % 60} с`; }, 500);
  let r;
  try { r = await core.call("plugin_run", { id: pid, tool: t.name, args }); }
  catch (e) { r = { ok: false, is_error: true, error: e.message, parts: [], files: [] }; }
  clearInterval(tick); btn.disabled = false; busy.hidden = true; card.classList.remove("busy");
  if (PLP.cur !== pid || !card.isConnected) return;
  const sec = (Date.now() - t0) / 1000;
  ms.textContent = r.is_error ? "" : `Готово за ${sec < 1 ? "<1" : Math.round(sec)} с`;
  card.classList.add("has-out");
  out.innerHTML = plpResult(r);
  plpWireOut(out);
  if (!r.is_error && PLP.tab === "do") plpFilesQuiet();
}
function plpFilesQuiet() { core.call("plugin_files", { id: PLP.cur }).then(f => { if (PLP.page) PLP.page.files = f; }).catch(() => {}); }

/* ответ действия: данные — таблицами и списками, текст — Markdown, картинки, файлы — кнопками «Открыть» */
function plpResult(r) {
  if (r.is_error) return `<div class="plp-err"><b>Не получилось.</b> ${plpEsc(r.error || "Плагин не объяснил почему.")}</div>`;
  let h = "";
  const say = [];
  (r.parts || []).forEach(x => {
    if (x.type === "image") h += `<img class="plp-img" src="${plpEsc(x.src)}" alt="">`;
    else if (x.type === "text") h += `<div class="plp-md md">${typeof md === "function" ? md(x.text) : plpEsc(x.text)}</div>`;
    else if (x.type === "data") { if (x.data && typeof x.data === "object" && !Array.isArray(x.data) && typeof x.data.say === "string") say.push(x.data.say); h += plpData(x.data, 0); }
  });
  if ((r.files || []).length) h += `<div class="plp-rfiles">${r.files.map(f => f.preview
      ? `<button class="plp-rimg" data-open="${plpEsc(f.path)}" title="Открыть"><img src="${plpEsc(f.preview)}" alt=""><span>${plpEsc(f.name)}</span></button>`
      : `<button class="plp-file" data-open="${plpEsc(f.path)}"><i>${plpKind[f.kind] || "📎"}</i><span>${plpEsc(f.name)}</span><em>Открыть</em></button>`).join("")}</div>`;
  return h || `<p class="hint">Готово — плагин ничего не вернул.</p>`;
}
const plpIsUrl = (v) => typeof v === "string" && /^https?:\/\/\S+$/.test(v);
const plpIsPath = (v) => typeof v === "string" && v.length < 600 && (/^(\/|~\/)/.test(v) || /^[A-Za-z]:[\\/]/.test(v)) && !/\n/.test(v);
function plpVal(v, k) {
  if (v == null || v === "") return `<span class="plp-dim">—</span>`;
  if (typeof v === "boolean") return v ? "да" : "нет";
  if (typeof v === "number") return /score|match|total/.test(k || "") && v >= 0 && v <= 100 && !/^(total)$/.test(k) ? `<span class="plp-pill" style="--v:${Math.min(100, k === "score" && v <= 10 ? v * 10 : v)}">${v}</span>` : plpEsc(v.toLocaleString("ru-RU"));
  if (plpIsUrl(v)) return `<a href="${plpEsc(v)}" data-ext>${plpEsc(v.replace(/^https?:\/\/(www\.)?/, "").slice(0, 48))}${v.length > 60 ? "…" : ""}</a>`;
  if (plpIsPath(v)) return `<button class="plp-link" data-open="${plpEsc(v)}" title="${plpEsc(v)}">${plpEsc(v.split(/[\\/]/).filter(Boolean).pop() || v)}</button>`;
  if (Array.isArray(v)) return v.every(x => typeof x !== "object") ? (v.length ? v.map(x => `<span class="plp-tagv">${plpEsc(x)}</span>`).join(" ") : `<span class="plp-dim">—</span>`) : plpEsc(v.length) + " шт.";
  if (typeof v === "object") return Object.entries(v).filter(([kk]) => plpLabel(kk) !== "").map(([kk, vv]) => `${plpEsc(plpLabel(kk))}: ${typeof vv === "object" ? plpEsc(JSON.stringify(vv)) : plpEsc(vv)}`).join(" · ");
  const s = String(v);
  return s.length > 240 ? `<details class="plp-long"><summary>${plpEsc(s.slice(0, 120))}…</summary><div class="md">${typeof md === "function" ? md(s) : plpEsc(s)}</div></details>` : plpEsc(s);
}
function plpTable(rows, ctx) {
  const cols = [];
  rows.slice(0, 50).forEach(r => Object.keys(r || {}).forEach(k => { if (!cols.includes(k) && k !== "id" && plpLabel(k, ctx) !== "") cols.push(k); }));
  const use = cols.slice(0, 8);
  if (!rows.length) return `<p class="plp-empty">Пусто</p>`;
  return `<div class="plp-tw"><table class="plp-t"><thead><tr>${use.map(c => `<th>${plpEsc(plpLabel(c, ctx))}</th>`).join("")}</tr></thead><tbody>${rows.slice(0, 200).map(r =>
    `<tr>${use.map(c => `<td class="${typeof r[c] === "number" ? "n" : ""}">${plpVal(r[c], c)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>${rows.length > 200 ? `<p class="hint">Показаны первые 200 из ${rows.length}.</p>` : ""}`;
}
function plpData(d, depth, ctx) {
  if (d == null) return "";
  if (Array.isArray(d)) return d.length && d.every(x => x && typeof x === "object" && !Array.isArray(x)) ? plpTable(d, ctx) : `<div class="plp-chips">${plpVal(d)}</div>`;
  if (typeof d !== "object") return `<p>${plpVal(d)}</p>`;
  const ent = Object.entries(d).filter(([k]) => plpLabel(k, ctx) !== "" && k !== "error");
  const simple = ent.filter(([, v]) => v == null || typeof v !== "object" || (Array.isArray(v) && v.every(x => typeof x !== "object")));
  const big = ent.filter(x => !simple.includes(x));
  const longTxt = simple.filter(([, v]) => typeof v === "string" && (v.length > 240 || /\n/.test(v) && v.length > 80));
  const kv = simple.filter(x => !longTxt.includes(x));
  let h = "";
  if (kv.length) h += `<dl class="plp-kv">${kv.map(([k, v]) => `<div><dt>${plpEsc(plpLabel(k, ctx))}</dt><dd>${plpVal(v, k)}</dd></div>`).join("")}</dl>`;
  big.forEach(([k, v]) => { h += `<h4 class="plp-sub">${plpEsc(plpLabel(k, ctx))}${Array.isArray(v) ? ` <small>${v.length}</small>` : ""}</h4>` + (depth > 3 ? `<pre class="plp-pre">${plpEsc(JSON.stringify(v, null, 1))}</pre>` : plpData(v, depth + 1, k)); });
  longTxt.forEach(([k, v]) => { h += `<details class="plp-long"><summary>${plpEsc(plpLabel(k, ctx))}</summary><div class="md">${typeof md === "function" ? md(v) : plpEsc(v)}</div></details>`; });
  return h || `<p class="plp-empty">Пусто</p>`;
}
function plpWireOut(box) {
  $$("[data-open]", box).forEach(b => b.onclick = () => core.call("plugin_open", { id: PLP.cur, path: b.dataset.open }).catch(e => toast(e.message)));
  $$("a[data-ext]", box).forEach(a => a.onclick = (e) => { e.preventDefault(); if (typeof openExt === "function") openExt(a.getAttribute("href")); });
}

/* «Попросить Лиру»: форма → готовая фраза в «Чат» (плагины без своего кода тоже делают что-то по кнопке) */
function plpAskCard(a, i) {
  const fl = Object.entries(a.fields || {});
  return `<article class="plp-ask plp-card" data-i="${i}">
    <div class="plp-ct"><b>${plpEsc(a.title)}</b><span class="plp-tag lira">Лира</span></div>
    ${a.hint ? `<p class="plp-cd">${plpEsc(a.hint)}</p>` : ""}
    ${fl.length ? `<div class="plp-form">${fl.map(([k, f]) => f.kind === "long"
      ? `<label class="f plp-wide"><span class="plp-fl">${plpEsc(f.label)}</span><textarea data-q="${plpEsc(k)}" rows="3" placeholder="${plpEsc(f.placeholder)}"></textarea></label>`
      : `<label class="f"><span class="plp-fl">${plpEsc(f.label)}</span><input type="text" data-q="${plpEsc(k)}" placeholder="${plpEsc(f.placeholder)}"></label>`).join("")}</div>` : ""}
    <div class="plp-run"><button class="btn primary" data-askgo>${plpEsc(a.button || "Спросить Лиру")}</button><span class="plp-ms plp-prev"></span></div></article>`;
}
function plpWireAsk(card) {
  const a = ((PLP.page.plugin.ui || {}).asks || [])[+card.dataset.i]; if (!a) return;
  const text = () => a.say.replace(/\{([^{}]+)\}/g, (_, k) => { const el = $(`[data-q="${CSS.escape(k)}"]`, card); return el ? el.value.trim() : ""; }).replace(/\s+/g, " ").trim();
  const prev = () => { const p = $(".plp-prev", card); const empty = $$("[data-q]", card).some(el => !el.value.trim()); p.textContent = empty ? "" : "«" + text() + "»"; };
  $$("[data-q]", card).forEach(el => { el.oninput = prev; el.onkeydown = (e) => { if (e.key === "Enter" && el.tagName === "INPUT") { e.preventDefault(); $("[data-askgo]", card).click(); } }; });
  $("[data-askgo]", card).onclick = () => {
    const empty = $$("[data-q]", card).find(el => !el.value.trim());
    if (empty) { empty.focus(); toast("Заполните «" + empty.closest("label").querySelector(".plp-fl").textContent + "»"); return; }
    plpAsk(text());
  };
}

/* ---------- «Настройки» ---------- */
function plpSettings(box) {
  const p = PLP.page.plugin;
  box.innerHTML = `${p.settings.length ? `<div class="plp-card plp-set"><div class="row one">${p.settings.map(s => plgField(p, s).replace(/id="pls-/g, 'id="pps-')).join("")}</div>
      <p class="hint plp-saved" id="plp-saved">${p.installed ? "Меняется сразу — сохранять не нужно." : "Заполнится при установке."}</p></div>` : ""}
    ${p.jobs.length ? `<h2 class="plp-h2">Дела по расписанию <small>Лира делает сама и сообщает итог</small></h2><div class="plp-card">${p.jobs.map(j => `<div class="switch"><div>${plpEsc(j.title)}</div><label class="tg"><input type="checkbox" data-job="${plpEsc(j.id)}" ${j.on ? "checked" : ""} ${p.installed ? "" : "disabled"}><i></i></label></div>`).join("")}</div>` : ""}`;
  const vals = () => { const o = {}; $$("#plp-body [data-k]").forEach(el => { o[el.dataset.k] = el.type === "checkbox" ? el.checked : el.value; }); return o; };
  let t = 0;
  const saveNow = (msg) => { if (!p.installed) return; clearTimeout(t);
    t = setTimeout(() => core.call("plugin_values", { id: p.id, values: vals() }).then(r => { plgSet(r); const s = $("#plp-saved"); if (s) { s.textContent = msg || "Сохранено ✓"; s.classList.add("ok"); } }).catch(e => toast(e.message)), msg ? 0 : 600); };
  $$("#plp-body [data-k]").forEach(el => { el.addEventListener(el.tagName === "SELECT" || el.type === "checkbox" ? "change" : "input", () => saveNow()); });
  $$("#plp-body [data-pick]").forEach(b => b.onclick = async (ev) => {
    ev.preventDefault(); const a = window.api && window.api();
    if (!a || !a.pick_folder) return toast("Выбор папки доступен в окне студии — или впишите путь вручную");
    const path = await a.pick_folder(); if (!path) return;
    const inp = $(`#plp-body [data-k="${b.dataset.pick}"]`); if (inp) inp.value = path; saveNow("Папка выбрана и сохранена ✓");
  });
  $$("#plp-body [data-job]").forEach(c => c.onchange = () => core.call("plugin_job", { id: p.id, job: c.dataset.job, on: c.checked })
    .then(r => { plgSet(r); toast(c.checked ? "Дело включено — Лира сделает его сама" : "Дело выключено"); }).catch(e => toast(e.message)));
}

/* ---------- «Изменить и версии» (плагин, сделанный Лирой) ---------- */
const PLP_EDIT_IDEAS = ["Сделай всё крупнее", "Добавь график по неделям", "Поменяй цвета на спокойные", "Добавь кнопку «Очистить»", "Сделай компактнее"];
function plpEdit(box) {
  const r = PLP.page, p = r.plugin, vs = (r.versions || {}).items || [];
  box.innerHTML = `<div class="plp-card plp-edit">
      <h2 class="plp-h2" style="margin-top:0">Что поменять? <small>словами — Лира перепишет страницу, прежняя версия сохранится</small></h2>
      <div class="plp-ed-row"><textarea id="plp-ed-q" rows="2" placeholder="Например: сделай цифры крупнее и добавь график по неделям"></textarea>
        <button class="btn primary" id="plp-ed-go">Изменить</button></div>
      ${typeof pmkWho === "function" ? pmkWho("plp-ed-who") : ""}
      <div class="plp-say">${PLP_EDIT_IDEAS.map(t => `<button class="chip" data-idea="${plpEsc(t)}">${plpEsc(t)}</button>`).join("")}</div>
      <p class="plp-ed-st" id="plp-ed-st" aria-live="polite"></p>
    </div>
    <h2 class="plp-h2">Версии <small>хранятся ${(r.versions || {}).keep || 10} последних · вернуть можно любую</small></h2>
    <div class="plp-vers">${vs.map(x => `<div class="plp-ver${x.current ? " cur" : ""}"><b>${x.v}</b><span><em>${plpEsc(x.label || "Версия " + x.v)}</em><small>${plpEsc(plpWhen(x.at))}${x.code ? " · со своей программой" : ""}${x.to ? " · возврат" : ""}</small></span>
      ${x.current ? `<span class="plp-tag">сейчас</span>` : `<button class="btn small" data-v="${x.v}">Вернуть эту</button>`}</div>`).join("") || `<p class="hint">Версий пока нет.</p>`}</div>
    <div class="actions"><button class="btn ghost" id="plp-undo" ${vs.length > 1 ? "" : "disabled"}>↶ Вернуть как было</button></div>`;
  const st = $("#plp-ed-st"), go = $("#plp-ed-go"), q = $("#plp-ed-q");
  $$("#plp-body [data-idea]").forEach(b => b.onclick = () => { q.value = b.dataset.idea; q.focus(); });
  q.onkeydown = (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); go.click(); } };
  const done = (res, msg) => { toast(msg); PLP.tab = "page"; plpCatalog(); PLP.page = null; plpLoad(); };
  go.onclick = async () => {
    const text = q.value.trim(); if (!text) { q.focus(); return; }
    go.disabled = true; const t0 = Date.now();
    const tick = setInterval(() => { st.innerHTML = `<i class="plp-spin"></i> Лира переписывает плагин… ${Math.round((Date.now() - t0) / 1000)} с`; }, 500);
    try { const res = await core.call("plugin_change", { id: p.id, request: text, by: typeof pmkWhoVal === "function" ? pmkWhoVal("plp-ed-who") : "" }); clearInterval(tick); done(res, res.said || "Готово"); }
    catch (e) { clearInterval(tick); go.disabled = false; st.innerHTML = `<span class="plp-err plp-small">${plpEsc(e.message)}</span>`; }
  };
  $$("#plp-body [data-v]").forEach(b => b.onclick = async () => {
    b.disabled = true;
    try { const res = await core.call("plugin_restore", { id: p.id, v: +b.dataset.v }); done(res, res.said || "Вернула"); } catch (e) { b.disabled = false; toast(e.message); }
  });
  $("#plp-undo").onclick = async () => { try { const res = await core.call("plugin_undo", { id: p.id }); done(res, res.said || "Вернула как было"); } catch (e) { toast(e.message); } };
}

/* ---------- «Доступ»: какие данные Лиры странице плагина разрешены ---------- */
function plpAccess(box) {
  const r = PLP.page, p = r.plugin, g = r.grants || {};
  const theme = ((S && S.ui) || {}).plugin_theme;
  box.innerHTML = `${(p.data || []).length ? `<div class="plp-card"><h2 class="plp-h2" style="margin-top:0">Данные Лиры <small>плагин спрашивает при первом обращении; выбор можно поменять здесь</small></h2>
      ${(p.data || []).map(s => { const v = g[s]; const w = PLP_SCOPES[s] || [s, ""];
        return `<div class="switch plp-grant"><div>${plpEsc(w[0][0].toUpperCase() + w[0].slice(1))}<span>${plpEsc(w[1])} · ${v === true ? "разрешено" : v === false ? "запрещено" : "ещё не спрашивал"}</span></div><label class="tg"><input type="checkbox" data-scope="${plpEsc(s)}" ${v === true ? "checked" : ""}><i></i></label></div>`; }).join("")}
      <p class="hint">Страница плагина видит только то, что здесь включено. Ничего не уходит в интернет: у страницы нет сети.</p></div>` : ""}
    ${p.theme ? `<div class="plp-card"><h2 class="plp-h2" style="margin-top:0">Оформление студии <small>этот плагин может перекрасить студию — по вашему нажатию</small></h2>
      <p>${theme && theme.id === p.id ? "Сейчас студия — в цветах этого плагина." : theme ? `Сейчас — тема плагина «${plpEsc(theme.name)}».` : "Сейчас — обычное оформление."}</p>
      <div class="actions"><button class="btn" id="plp-th-reset" ${theme ? "" : "disabled"}>Сбросить тему</button></div></div>` : ""}`;
  $$("#plp-body [data-scope]").forEach(c => c.onchange = async () => {
    try { const res = await core.call("plugin_grant", { id: p.id, scope: c.dataset.scope, on: c.checked }); PLP.page.grants = res.grants; plpAccess(box); toast(c.checked ? "Разрешено" : "Доступ закрыт"); }
    catch (e) { toast(e.message); c.checked = !c.checked; }
  });
  const tr = $("#plp-th-reset"); if (tr) tr.onclick = async () => { if (typeof lookPtReset === "function") await lookPtReset(); plpAccess(box); };
}

/* ---------- «Файлы» ---------- */
async function plpFiles(box) {
  box.innerHTML = `<p class="plp-loading"><i class="plp-spin"></i> Смотрю файлы…</p>`;
  let f;
  try { f = await core.call("plugin_files", { id: PLP.cur, limit: 24 }); } catch (e) { box.innerHTML = `<p class="plp-err">${plpEsc(e.message)}</p>`; return; }
  if (PLP.tab !== "files") return;
  const items = f.items || [];
  box.innerHTML = `<div class="plp-fhead">${(f.folders || []).map(x => `<button class="btn small" data-open="${plpEsc(x.path)}" title="${plpEsc(x.path)}">📁 ${plpEsc(x.label)}</button>`).join("")}<button class="btn small ghost" id="plp-frel">Обновить</button></div>
    ${items.length ? `<div class="plp-flist">${items.map(x => `<button class="plp-frow" data-open="${plpEsc(x.path)}" title="${plpEsc(x.path)}"><i>${plpKind[x.kind] || "📎"}</i><span><b>${plpEsc(x.name)}</b><small>${plpEsc(x.folder)} · ${plpEsc(plpWhen(x.at))} · ${plpSize(x.size)}</small></span><em>Открыть</em></button>`).join("")}</div>`
      : `<div class="plp-none"><b>Файлов пока нет</b><span>Что плагин сохранит — появится здесь: новые сверху.</span></div>`}`;
  plpWireOut(box);
  $("#plp-frel").onclick = () => plpFiles(box);
}

/* ---------- «Рисунки» у «Художника» ---------- */
async function plpArt(box) {
  box.innerHTML = `<div class="actions" style="margin:0 0 16px"><button class="btn" id="plp-artdir">Открыть папку «Рисунки»</button><button class="btn ghost" id="plp-artall">Все рисунки</button></div><div class="art-grid" id="plp-art"></div>`;
  $("#plp-artdir").onclick = () => core.call("ws_open", { path: "Рисунки" }).catch(e => toast(e.message));
  $("#plp-artall").onclick = () => { const b = $('nav button[data-p="art"]'); if (b) { b.hidden = false; b.click(); } };
  let r = null; try { r = await core.call("art_list", { limit: 24 }); } catch (e) { $("#plp-art").innerHTML = `<p class="hint">${plpEsc(e.message)}</p>`; return; }
  const items = (r && r.items) || [], g = $("#plp-art"); if (!g) return;
  g.innerHTML = items.length ? items.map((w, i) => `<button class="art-w" type="button" data-i="${i}" title="Открыть в браузере"><span class="art-pv">${w.preview ? `<img src="${plpEsc(w.preview)}" alt="" loading="lazy">` : `<i aria-hidden="true">${w.kind === "animation" ? "▶" : "🎨"}</i>`}</span><b>${plpEsc(w.title)}</b><small>${w.kind === "animation" ? "анимация" : "рисунок"} · ${plpEsc(plpWhen(w.at))}</small></button>`).join("")
    : `<div class="plp-none"><b>Рисунков пока нет</b><span>Откройте «Сделать сейчас» → «Нарисовать» или скажите: «Нарисуй открытку для мамы».</span></div>`;
  $$("#plp-art .art-w").forEach(b => b.onclick = () => core.call("ws_open", { path: items[+b.dataset.i].page }).catch(e => toast(e.message)));
}

/* ---------- своя страница плагина: ui.html во фрейме-песочнице с мостом ---------- */
const PLP_TOKENS = ["--ink", "--muted", "--dim", "--line", "--field", "--panel", "--panel2", "--accent", "--bad", "--good", "--brand", "--glass2", "--soft", "--soft2"];
const PLP_KIT = `*{box-sizing:border-box}html,body{margin:0;background:transparent}body{font:14.5px/1.55 "Manrope","Ubuntu","Noto Sans","Segoe UI",system-ui,sans-serif;color:var(--ink);padding:2px 2px 24px}
h1,h2,h3{font-weight:650;letter-spacing:.01em;margin:0 0 8px}h1{font-size:22px}h2{font-size:16px}h3{font-size:14.5px}p{margin:0 0 10px}a{color:var(--accent)}
button,input,select,textarea{font:inherit;color:inherit}
.btn{border:0;background:var(--soft2,rgba(255,255,255,.1));padding:8px 16px;border-radius:12px;cursor:pointer;transition:background .2s,filter .2s}.btn:hover{filter:brightness(1.15)}
.btn.primary{background:var(--brand);color:#fff;font-weight:700}.btn.small{padding:4px 10px;font-size:12.5px}.btn.ghost{background:transparent;box-shadow:inset 0 0 0 1px var(--line)}.btn:disabled{opacity:.5;cursor:default}
input[type=text],input[type=search],input[type=number],select,textarea{width:100%;padding:9px 12px;border-radius:12px;border:0;background:var(--field);color:var(--ink);outline:none;box-shadow:inset 0 0 0 1px var(--line)}
input:focus,select:focus,textarea:focus{box-shadow:inset 0 0 0 1.5px var(--accent)}
textarea{resize:vertical;min-height:80px}select option{background:#1a1a2e;color:#F2F3FA}
.card{background:var(--panel);border-radius:18px;padding:16px 18px}.hint{font-size:12.5px;color:var(--dim)}.muted{color:var(--muted)}
.chip{border:0;border-radius:999px;padding:5px 12px;font-size:13px;cursor:pointer;background:var(--soft,rgba(255,255,255,.08))}.chip.on{background:var(--brand);color:#fff}
.pill{display:inline-block;border-radius:999px;padding:1px 9px;font-size:12px;font-weight:600;background:var(--soft,rgba(255,255,255,.08))}
table{border-collapse:collapse;width:100%;font-size:13px}th,td{text-align:left;padding:7px 8px;border-bottom:1px solid var(--line);vertical-align:top}th{color:var(--muted);font-weight:600}
@keyframes dwspin{to{transform:rotate(360deg)}}.spin{display:inline-block;width:14px;height:14px;border-radius:50%;border:2px solid var(--line);border-top-color:var(--accent);animation:dwspin .8s linear infinite;vertical-align:-2px}`;
function plpTheme() {
  const cs = getComputedStyle(document.documentElement);
  const vars = PLP_TOKENS.map(k => { const v = cs.getPropertyValue(k).trim(); return v ? `${k}:${v};` : ""; }).join("");
  return `:root{${vars}color-scheme:${cs.colorScheme || "dark"}}`;
}
/* тема студии поменялась (тема из плагина, сброс) — страница плагина во фрейме перекрашивается следом */
function plpFrameTheme() { const f = $("#plp-frame"); if (f && f.contentWindow) setTimeout(() => { try { f.contentWindow.postMessage({ __dwt: plpTheme() }, "*"); } catch (e) { } }, 30); }
window.plpFrameTheme = plpFrameTheme;
function plpSrcdoc(html, p) {
  const info = JSON.stringify({ id: p.id, name: p.name, icon: p.icon, color: p.color }).replace(/</g, "\\u003c");
  const bridge = `(()=>{let n=0;const w={};addEventListener("message",e=>{if(e.source!==parent)return;const d=e.data||{};if(typeof d.__dwt==="string"){let s=document.getElementById("dw-theme");if(!s){s=document.createElement("style");s.id="dw-theme";document.head.appendChild(s);}s.textContent=d.__dwt;return;}if(!d.__dwr||!w[d.rid])return;const x=w[d.rid];delete w[d.rid];d.ok?x[0](d.result):x[1](new Error(d.error||"ошибка"));});
const q=(op,args)=>new Promise((ok,no)=>{const rid=++n;w[rid]=[ok,no];parent.postMessage({__dw:1,rid,op,args:args||{}},"*");});
window.dewiar={plugin:${info},run:(tool,args)=>q("run",{tool,args:args||{}}),settings:()=>q("settings"),saveSettings:(values)=>q("save",{values}),open:(path)=>q("open",{path}),openUrl:(url)=>q("url",{url}),ask:(text)=>q("ask",{text}),toast:(text)=>q("toast",{text}),
store:{get:(key)=>q("store_get",{key}),set:(key,value)=>q("store_set",{key,value:value===undefined?null:value})},data:(scope)=>q("data",{scope}),theme:(vars)=>q("theme",{vars:vars||null}),readUrl:(url)=>q("read_url",{url})};
let lh=0;const post=()=>{const h=Math.ceil(document.documentElement.scrollHeight);if(Math.abs(h-lh)>2){lh=h;parent.postMessage({__dw:1,op:"height",h},"*");}};
try{new ResizeObserver(post).observe(document.documentElement);}catch(e){setInterval(post,500);}addEventListener("load",post);})();`;
  const head = `<meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline' https://cdn.jsdelivr.net/npm/ https://cdnjs.cloudflare.com/ajax/libs/; style-src 'unsafe-inline'; img-src data: blob:; font-src data:; media-src data: blob:; form-action 'none'; base-uri 'none'"><style>${plpTheme()}${PLP_KIT}</style><script>${bridge}</script>`;
  let body = String(html || "").replace(/^\ufeff?\s*<!doctype[^>]*>/i, "");
  // своё <meta http-equiv> плагина не должно ослабить наш CSP: CSP складываются, ослабить нельзя — но убираем на всякий случай;
  // и <meta refresh> — переход фрейма не туда, куда разрешено
  body = stripMetaEquiv(body);                                           // core.js: разбор, как у браузера (четвёртая рецензия)
  // наш CSP и мост — самыми первыми, до всего, что есть у страницы (третья рецензия: «после <head>» обходилось скриптом
  // до <head> или «<head>» в комментарии — и meta оказывалась в <body>, где CSP не действует)
  return "<!doctype html>" + head + body;
}
async function plpFrame(box) {
  const p = PLP.page.plugin;
  box.innerHTML = `<p class="plp-loading"><i class="plp-spin"></i> Открываю страницу плагина…</p>`;
  let r; try { r = await core.call("plugin_ui", { id: p.id }); } catch (e) { box.innerHTML = `<p class="plp-err">${plpEsc(e.message)}</p>`; return; }
  if (PLP.tab !== "page" || PLP.cur !== p.id) return;
  if (!r || !r.html) { box.innerHTML = `<p class="hint">У плагина нет своей страницы.</p>`; return; }
  box.innerHTML = "";
  const f = document.createElement("iframe");
  f.id = "plp-frame"; f.className = "plp-frame"; f.dataset.pid = p.id; f.title = p.name;
  f.setAttribute("sandbox", "allow-scripts");                      // без allow-same-origin: ни студии, ни ядра, ни хранилищ
  f.setAttribute("referrerpolicy", "no-referrer");
  PLP.frameLoads = 0;
  f.addEventListener("load", () => { PLP.frameLoads++; });            // второй load — фрейм ушёл со своей страницы: мост молчит
  f.srcdoc = plpSrcdoc(r.html, p);
  box.appendChild(f);
}
function plpFrameData(r) {
  const data = (r.parts || []).find(x => x.type === "data");
  return { ok: !r.is_error, error: r.error || "", data: data ? data.data : null,
    text: (r.parts || []).filter(x => x.type === "text").map(x => x.text).join("\n"), images: (r.parts || []).filter(x => x.type === "image").map(x => x.src),
    files: (r.files || []).map(f => ({ path: f.path, name: f.name, kind: f.kind })) };
}
/* ask и openUrl — только по нажатию человека. Нажатие во фрейме видно и студии (navigator.userActivation); нет его
   (страница сама решила написать Лире) или браузер окна этого не умеет — спросить человека, а не делать молча */
async function plpGesture(text, verb) {
  const ua = navigator.userActivation;
  if (ua && ua.isActive) return true;
  return typeof ask === "function" ? !!(await ask(text, { ok: verb })) : false;
}
/* dewiar.data(область): только объявленное в plugin.json; первый раз — вопрос человеку, ответ запоминается (plugin_grant).
   Запрещено раньше — без нажатия сразу отказ, по нажатию — спросить снова. Ядро проверяет разрешение ещё раз. */
async function plpData_(pid, scope) {
  const pl = PLP.page.plugin, w = PLP_SCOPES[scope];
  if (!w) throw new Error(`нет таких данных: «${scope}»`);
  if (!(pl.data || []).includes(scope)) throw new Error(`плагин не просит доступ к «${scope}» — добавьте его в plugin.json → data`);
  const g = PLP.page.grants || {};
  if (g[scope] !== true) {
    const ua = navigator.userActivation;
    if (g[scope] === false && !(ua && ua.isActive)) throw new Error(`доступ запрещён: ${w[0]} (вкладка «Доступ»)`);
    const key = pid + ":" + scope;                                    // два вызова подряд — один вопрос
    PLP.asking[key] = PLP.asking[key] || (async () => {
      const yes = typeof ask === "function" && !!(await ask(`Плагин «${pl.name}» просит доступ: ${w[0]} — ${w[1]}.\nСтраница плагина без сети: данные не уйдут в интернет. Разрешить?`, { ok: "Разрешить", cancel: "Не разрешать", danger: false }));
      const res = await core.call("plugin_grant", { id: pid, scope, on: yes });
      if (PLP.page && PLP.page.plugin.id === pid) PLP.page.grants = res.grants;
      return yes;
    })().finally(() => { setTimeout(() => { delete PLP.asking[key]; }, 0); });
    if (!await PLP.asking[key]) throw new Error(`человек не разрешил доступ: ${w[0]}`);
  }
  return core.call("plugin_data", { id: pid, scope });
}
window.addEventListener("message", async (e) => {
  const f = $("#plp-frame");
  if (!f || e.source !== f.contentWindow) return;                   // только наш фрейм — и только его окно
  const d = e.data; if (!d || d.__dw !== 1 || typeof d.op !== "string") return;
  if (PLP.frameLoads > 1 || f.dataset.pid !== PLP.cur || !PLP.page) return;
  if (d.op === "height") { f.style.height = Math.max(420, Math.min(20000, +d.h || 0) + 4) + "px"; return; }
  const pid = f.dataset.pid, a = (d.args && typeof d.args === "object") ? d.args : {};
  const reply = (ok, result, error) => { try { f.contentWindow.postMessage({ __dwr: 1, rid: d.rid, ok, result, error }, "*"); } catch (x) { } };
  try {
    if (d.op === "run") {
      const tool = String(a.tool || "");
      const names = PLP.page.tools.length ? PLP.page.tools.map(t => t.name) : (PLP.known[pid] || []);
      if (!names.includes(tool)) throw new Error(`«${tool}» — не действие этого плагина`);
      return reply(true, plpFrameData(await core.call("plugin_run", { id: pid, tool, args: (a.args && typeof a.args === "object") ? a.args : {} })));
    }
    const p = (PLP.cat.find(x => x.id === pid)) || PLP.page.plugin;
    if (d.op === "settings") return reply(true, { values: p.values || {}, fields: (p.settings || []).map(s => ({ key: s.key, label: s.label, type: s.type, options: s.options })) });
    if (d.op === "save") {
      const r = await core.call("plugin_values", { id: pid, values: Object.assign({}, p.values || {}, a.values || {}) }); plgSet(r);
      return reply(true, ((r.plugins || []).find(x => x.id === pid) || {}).values || {});
    }
    if (d.op === "open") return reply(true, !!(await core.call("plugin_open", { id: pid, path: String(a.path || "") })));
    if (d.op === "ask") {
      const t = String(a.text || "").trim().slice(0, 12000); if (!t) throw new Error("пустая фраза");     // читалка: «перескажи» с текстом статьи
      if (!await plpGesture(`Страница плагина «${PLP.page.plugin.name}» хочет спросить Лиру:\n«${t.slice(0, 300)}»`, "Спросить")) throw new Error("человек не разрешил");
      plpAsk(t); return reply(true, true);
    }
    if (d.op === "url") {                                           // страница тендера на площадке — в браузере, только http(s) и по нажатию
      const u = String(a.url || ""); if (!/^https?:\/\/[^\s"'<>]+$/.test(u) || u.length > 2000) throw new Error("это не адрес страницы");
      if (!await plpGesture(`Страница плагина «${PLP.page.plugin.name}» хочет открыть в браузере:\n${u.slice(0, 200)}`, "Открыть")) throw new Error("человек не разрешил");
      if (typeof openExt === "function") openExt(u); else window.open(u, "_blank", "noopener"); return reply(true, true);
    }
    if (d.op === "toast") { toast(String(a.text || "").slice(0, 160)); return reply(true, true); }
    if (d.op === "store_get") return reply(true, (await core.call("plugin_store", { id: pid, op: "get", key: a.key == null ? "" : String(a.key) })).value ?? null);
    if (d.op === "store_set") return reply(true, await core.call("plugin_store", { id: pid, op: "set", key: String(a.key ?? ""), value: a.value ?? null }));
    if (d.op === "data") return reply(true, await plpData_(pid, String(a.scope || "")));
    if (d.op === "theme") {
      const pl = PLP.page.plugin; if (!pl.theme) throw new Error("этот плагин не может менять оформление (нет \"theme\": true в plugin.json)");
      if (a.vars === null) { if (typeof lookPtReset === "function") await lookPtReset(true); else { await core.call("plugin_theme", { reset: true }); studioPluginTheme(null); } plpFrameTheme(); return reply(true, null); }
      if (!await plpGesture(`Плагин «${pl.name}» хочет перекрасить студию. Вернуть можно в «Оформлении» → «Сбросить тему».`, "Перекрасить")) throw new Error("человек не разрешил");
      const res = await core.call("plugin_theme", { id: pid, vars: a.vars || {} });
      if (S && S.ui) S.ui.plugin_theme = res.theme; if (window.studioPluginTheme) studioPluginTheme(res.theme); if (typeof lookPt === "function") lookPt(); plpFrameTheme();
      return reply(true, res.theme && res.theme.vars);
    }
    if (d.op === "read_url") {                                      // читалка: текст статьи по ссылке — по нажатию; есть доступ к данным — всегда с вопросом
      const u = String(a.url || "").trim(); if (!/^https?:\/\/[^\s"'<>]+$/.test(u) || u.length > 2000) throw new Error("это не адрес страницы");
      const risky = Object.values(PLP.page.grants || {}).some(Boolean);
      const q = `Плагин «${PLP.page.plugin.name}» хочет прочитать страницу:\n${u.slice(0, 200)}`;
      if (risky ? !(typeof ask === "function" && await ask(q, { ok: "Прочитать" })) : !await plpGesture(q, "Прочитать")) throw new Error("человек не разрешил");
      return reply(true, await core.call("plugin_fetch", { id: pid, url: u }));
    }
    throw new Error("мост не знает такой просьбы");
  } catch (err) { reply(false, null, err.message || String(err)); }
});

/* ---------- связь с ядром ---------- */
core.on("hello", () => { setTimeout(plpCatalog, 0);
  const m = /^#plg:([\w-]+)/.exec(location.hash || ""); if (m) setTimeout(() => plpOpen(m[1]), 300); })
  .on("settings", (e) => {                                          // установили или удалили плагин где угодно — меню догоняет
    const on = Object.keys(((e && e.settings && e.settings.plugins) || {}).on || {}).sort().join(",");
    const have = PLP.cat.filter(p => p.installed).map(p => p.id).sort().join(",");
    if (on !== have) plpCatalog();
  })
  .on("mcp", () => { if (PLP.cur && $("#p-plg.cur")) plpRefresh(); })
  // Лира сделала или изменила плагин (голосом, в чате или здесь): меню догоняет; голосом — сразу его страница
  .on("plugin_made", (e) => { plpCatalog().then(() => { if (!e || !e.id) return;
    if (e.open) { PLP.tab = ""; PLP.page = null; plpOpen(e.id); } else if (PLP.cur === e.id && $("#p-plg.cur")) { PLP.page = null; plpLoad(); } }); })
  .on("plugin_theme", (e) => { if (S && S.ui) S.ui.plugin_theme = e ? e.theme : null; if (window.studioPluginTheme) studioPluginTheme(e ? e.theme : null); if (typeof lookPt === "function") lookPt(); plpFrameTheme(); });
core.on("hello", () => { if (window.studioPluginTheme) studioPluginTheme(((S && S.ui) || {}).plugin_theme || null); });
document.addEventListener("click", (e) => { const b = e.target.closest && e.target.closest("nav button[data-p]"); if (b && b.dataset.p !== "plg") { clearTimeout(PLP.poll); setTimeout(plpNavCur, 0); } }, true);
// файл, брошенный мимо страницы плагина (на шапку, меню), окно студии не должно открыть вместо себя
["dragover", "drop"].forEach(ev => document.addEventListener(ev, (e) => { if ($("#p-plg.cur") && e.dataTransfer && [...(e.dataTransfer.types || [])].includes("Files")) e.preventDefault(); }));
