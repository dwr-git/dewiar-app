/* Студия → «Работа» → «Сайты» (03.11, владелец: «Лира должна научиться делать сайты… переделать сайт в любой момент —
   от структуры до дизайна — одной командой; публикация на dewiar.pro; посещаемость и аналитика — красивые»).
   Список: «Расскажите о своём деле» (Лира делает сайт по описанию), мои сайты карточками с живым превью, 11 шаблонов.
   Редактор: слева — разделы (перетаскивание, вариант вёрстки, фон, поля и карточки), оформление (палитры, шрифтовые
   пары, углы, шапка), шапка (логотип, знак, меню), контакты и описание для поисковиков; справа — живой предпросмотр
   (компьютер/телефон; щелчок по разделу открывает его настройку) и «Сказать Лире». «Верни как было», «История»,
   «Опубликовать» (имя.dewiar.pro, проверка занятости, QR). Вкладки: «Аналитика» (посещения по дням, откуда, страницы,
   устройства, заявки), «Заявки» (в «Клиентах»), «Продвижение» (проверка и «Попросить Лиру исправить»).
   Ядро — sites.py: sites_list, sites_meta, sites_get, sites_render, sites_template, sites_create, sites_apply, sites_say,
   sites_undo, sites_restore, sites_image, sites_open, sites_check, sites_suggest, sites_publish, sites_unpublish,
   sites_stats, sites_audit, sites_leads, sites_logos, sites_delete; событие «sites». */
const SITES = { meta: null, items: [], sid: "", cur: null, hist: [], page: 0, sel: "", open: "", dev: "pc", scroll: 0, tab: "edit", seg: "blocks", t: {}, days: 30, busy: false };
const stE = (t) => escH(t);
const stI = (p, cls = "") => `<svg class="i ${cls}" viewBox="0 0 24 24" aria-hidden="true">${p}</svg>`;
const ST_EG = ["Кофейня «Зерно» на Садовой, 5: кофе, завтраки, своя выпечка, с 8 до 22", "Мастер маникюра Алина, Казань, запись в Telegram @alina_nails",
  "Юрист по семейным делам, консультации онлайн и в Самаре", "Онлайн-курс рисования для начинающих, старт 1 декабря", "Ремонт квартир под ключ в Екатеринбурге"];

function stAgo(ts) {
  if (!ts) return "";
  const d = Date.now() / 1000 - ts;
  if (d < 90) return "только что";
  if (d < 3600) return `${Math.round(d / 60)} мин назад`;
  if (d < 86400) return `${Math.round(d / 3600)} ч назад`;
  return new Date(ts * 1000).toLocaleDateString("ru-RU", { day: "numeric", month: "long" });
}

async function loadSites() {
  try {
    if (!SITES.meta) SITES.meta = await core.call("sites_meta");
    const r = await core.call("sites_list"); SITES.items = r.items || []; SITES.signed = !!r.signed;
  } catch (e) { toast(e.message, 4000); return; }
  if (SITES.sid && SITES.items.some(x => x.id === SITES.sid)) { stOpen(SITES.sid, true); return; }
  stShowList();
}

/* ---------- список ---------- */
function stShowList() {
  SITES.sid = ""; SITES.cur = null;
  $("#st-ed").hidden = true; $("#st-list").hidden = false;
  $("#st-eg").innerHTML = ST_EG.map(t => `<button type="button" class="st-egb">${stE(t)}</button>`).join("");
  $$("#st-eg .st-egb").forEach(b => b.onclick = () => { $("#st-desc").value = b.textContent; $("#st-desc").focus(); });
  const mine = SITES.items;
  $("#st-mine").innerHTML = mine.length ? `<div class="st-h2"><h2>Мои сайты</h2><span>${mine.length === 1 ? "Один сайт" : mine.length + " " + (mine.length < 5 ? "сайта" : "сайтов")}</span></div>
    <div class="st-grid">${mine.map(x => `<button type="button" class="st-card" data-id="${stE(x.id)}"><span class="st-thumb"><iframe tabindex="-1" aria-hidden="true" sandbox="allow-same-origin" loading="lazy"></iframe></span>
      <span class="st-cb"><b>${stE(x.name)}</b><small>${stE(x.tagline || "")}</small><span class="st-cm">${stStateChip(x.published)}<em>${stE(stAgo(x.updated))}</em></span></span></button>`).join("")}</div>` : "";
  $$("#st-mine .st-card").forEach(b => b.onclick = () => stOpen(b.dataset.id));
  $("#st-tpls").innerHTML = (SITES.meta.templates || []).map(t => `<button type="button" class="st-tpl" data-t="${t.id}"><span class="st-thumb"><iframe tabindex="-1" aria-hidden="true" sandbox="allow-same-origin" loading="lazy"></iframe></span>
    <span class="st-cb"><b>${stE(t.title)}</b><small>${stE(t.sub)}</small></span></button>`).join("");
  $$("#st-tpls .st-tpl").forEach(b => b.onclick = () => stFromTemplate(b.dataset.t));
  stThumbs();
}

function stStateChip(p) {
  if (!p || !p.name) return `<span class="st-chip">Черновик</span>`;
  if (p.status === "blocked") return `<span class="st-chip bad">Заблокирован</span>`;
  return `<span class="st-chip live"><i></i>${stE(p.name)}.dewiar.pro</span>`;
}

/* превью карточек: страница 1280 px, уменьшенная до ширины карточки; по одной, чтобы список открывался сразу */
async function stThumbs() {
  const jobs = [...$$("#st-mine .st-card").map(b => ["sites_render", { id: b.dataset.id }, b]), ...$$("#st-tpls .st-tpl").map(b => ["sites_template", { template: b.dataset.t }, b])];
  const gen = (SITES.gen = (SITES.gen || 0) + 1);
  for (const [cmd, a, b] of jobs) {
    if (gen !== SITES.gen || $("#st-list").hidden) return;
    try { const r = await core.call(cmd, a); const f = b.querySelector("iframe"); f.srcdoc = r.html.replace(/<script>[\s\S]*?<\/script>/g, ""); stThumbFit(b); } catch (e) { }   // превью — без скрипта предпросмотра
  }
}
function stThumbFit(b) { const box = b.querySelector(".st-thumb"), f = b.querySelector("iframe"); if (box && f) f.style.transform = `scale(${box.clientWidth / 1280})`; }
window.addEventListener("resize", () => { $$("#p-sites .st-card, #p-sites .st-tpl").forEach(stThumbFit); stFit(); });

async function stCreate(a, btn) {
  const was = btn ? btn.textContent : "";
  if (btn) { btn.disabled = true; btn.textContent = a.describe ? "Лира делает сайт…" : "Создаю…"; }
  try {
    const r = await core.call("sites_create", a);
    SITES.items = (await core.call("sites_list")).items || [];
    stOpen(r.site.id, false, r);
    toast(a.describe ? "Сайт готов — меняйте что угодно фразой внизу" : "Готово — замените тексты своими или скажите Лире", 3500);
  } catch (e) { toast(e.message, 5000); }
  if (btn) { btn.disabled = false; btn.textContent = was; }
}
function stFromTemplate(tid) { stCreate({ template: tid }, null); }

/* ---------- редактор ---------- */
async function stOpen(id, keep, data) {
  try { data = data || await core.call("sites_get", { id }); } catch (e) { toast(e.message, 4000); return; }
  if (!keep || SITES.sid !== id) { SITES.page = 0; SITES.sel = ""; SITES.open = ""; SITES.scroll = 0; SITES.tab = "edit"; SITES.seg = "blocks"; }
  SITES.sid = id; SITES.cur = data.site; SITES.hist = data.history || [];
  $("#st-list").hidden = true; $("#st-ed").hidden = false;
  stTab(SITES.tab, true); stSeg(SITES.seg);
  stBar(); stSide(); stPreview();
}

function stBar() {
  const s = SITES.cur, p = s.published || {};
  if (document.activeElement !== $("#st-name")) $("#st-name").value = s.name || "";
  $("#st-state").outerHTML = `<span class="st-chip${p.status === "blocked" ? " bad" : p.name ? " live" : ""}" id="st-state">${p.status === "blocked" ? "Заблокирован" : p.name ? `<i></i><a href="${stE(p.url)}" target="_blank" rel="noopener">${stE(p.name)}.dewiar.pro</a>` : "Черновик"}</span>`;
  $("#st-pub").textContent = p.name ? "Обновить на сайте" : "Опубликовать";
  $("#st-pub").disabled = p.status === "blocked";
  $("#st-ban").hidden = p.status !== "blocked";
  $("#st-ban").innerHTML = p.status === "blocked" ? `<b>Сайт заблокирован администратором Dewiar</b><span>Причина: ${stE(p.reason || "нарушение правил")}. Посетители видят «Сайт заблокирован». Если это ошибка — напишите в поддержку («Сообщить о проблеме»).</span>` : "";
  $("#st-undo").disabled = (SITES.hist || []).length < 2;
}

function stPg() { return (SITES.cur.pages || [])[SITES.page] || (SITES.cur.pages || [])[0]; }
function stBlocks() { return (stPg() || {}).blocks || []; }
function stMetaB(t) { return (SITES.meta.blocks || {})[t] || { title: t, variants: {}, fields: [] }; }

async function stApply(ops, label, opt = {}) {
  try {
    const r = await core.call("sites_apply", { id: SITES.sid, ops, label: label || "", merge: !!opt.merge });
    SITES.cur = r.site; SITES.hist = r.history || [];
    stBar();
    if (!opt.soft) stSide();
    stPreview();
    return true;
  } catch (e) { toast(e.message, 4000); return false; }
}
/* правка текста: печатают — сохраняем через 600 мс, одной версией на поле */
function stLater(key, ops, label) {
  clearTimeout(SITES.t[key]);
  SITES.t[key] = setTimeout(() => stApply(ops(), label, { soft: true, merge: true }), 600);
}

/* предпросмотр */
async function stPreview() {
  const id = SITES.sid, pg = SITES.page;
  try {
    const r = await core.call("sites_render", { id, page: pg });
    if (id !== SITES.sid) return;
    $("#st-if").srcdoc = r.html;
  } catch (e) { toast(e.message, 3000); }
  stFit();
}
function stFit() {
  const fr = $("#st-frame"), f = $("#st-if"), w = $("#st-fwrap");
  if (!fr || !f || $("#st-ed").hidden) return;
  const W = fr.clientWidth, H = fr.clientHeight;
  if (SITES.dev === "phone") {
    const k = Math.min(1, (H - 28) / 760);
    w.className = "st-fwrap phone"; w.style.width = `${390 * k + 20}px`; w.style.height = `${760 * k + 20}px`;
    f.style.width = "390px"; f.style.height = "760px"; f.style.transform = `scale(${k})`;
  } else {
    const k = W / 1280;
    w.className = "st-fwrap"; w.style.width = "100%"; w.style.height = "100%";
    f.style.width = "1280px"; f.style.height = `${H / k}px`; f.style.transform = `scale(${k})`;
  }
}
window.addEventListener("message", (e) => {
  const d = e.data || {}, f = $("#st-if");
  if (!d.dwsite || !f || e.source !== f.contentWindow) return;
  if (d.dwsite === "ready") f.contentWindow.postMessage({ dwsite: "scrollTo", y: SITES.scroll, sel: SITES.sel }, "*");
  else if (d.dwsite === "scroll") SITES.scroll = d.y || 0;
  else if (d.dwsite === "pick") { SITES.sel = d.id; SITES.open = d.id; stSeg("blocks"); stBlocksList(); const row = $(`#st-blocks [data-uid="${d.id}"]`); if (row) row.scrollIntoView({ behavior: "smooth", block: "nearest" }); }
  else if (d.dwsite === "page") { const i = (SITES.cur.pages || []).findIndex((p, j) => (j === 0 ? "index" : p.slug) === d.slug); if (i >= 0) { SITES.page = i; SITES.scroll = 0; stSide(); stPreview(); } }
});

/* ---------- левая панель ---------- */
function stSeg(s) {
  SITES.seg = s;
  $$("#st-seg button").forEach(b => { b.classList.toggle("on", b.dataset.s === s); b.setAttribute("aria-selected", b.dataset.s === s); });
  $$("#p-sites .st-panel").forEach(p => p.hidden = p.dataset.s !== s);
}
function stSide() {
  stPages(); stBlocksList(); stLook(); stHead(); stInfo();
  const pgs = SITES.cur.pages || [];
  $("#st-page").hidden = pgs.length < 2;
  $("#st-page").innerHTML = pgs.map((p, i) => `<option value="${i}"${i === SITES.page ? " selected" : ""}>${stE(p.title || "Страница")}</option>`).join("");
}

function stPages() {
  const pgs = SITES.cur.pages || [];
  $("#st-pages").innerHTML = pgs.map((p, i) => `<button type="button" class="st-pg${i === SITES.page ? " on" : ""}" data-i="${i}">${stE(p.title || "Страница")}</button>`).join("")
    + `<button type="button" class="st-pg add" id="st-addpg" title="Новая страница" aria-label="Новая страница">${stI('<path d="M12 5v14M5 12h14"/>')}</button>`
    + (SITES.page > 0 ? `<button type="button" class="st-pg more" id="st-pgset">Переименовать или удалить</button>` : "");
  $$("#st-pages .st-pg[data-i]").forEach(b => b.onclick = () => { SITES.page = +b.dataset.i; SITES.scroll = 0; SITES.sel = ""; SITES.open = ""; stSide(); stPreview(); });
  $("#st-addpg").onclick = async () => {
    const t = await askText("Название новой страницы — например «Цены», «Доставка», «О нас»", "", { ok: "Добавить" });
    if (t && t.trim() && await stApply([{ op: "add_page", title: t.trim(), blocks: ["text", "lead"] }], `Новая страница «${t.trim()}»`)) { SITES.page = SITES.cur.pages.length - 1; stSide(); stPreview(); }
  };
  if ($("#st-pgset")) $("#st-pgset").onclick = async () => {
    const p = stPg(), t = await askText("Название страницы (пусто — удалить страницу)", p.title || "", { ok: "Готово" });
    if (t === null || t === undefined) return;
    if (!t.trim()) { if (await ask(`Удалить страницу «${p.title}» со всеми разделами? Вернуть можно из «Истории».`, { ok: "Удалить" })) { const i = SITES.page; SITES.page = 0; stApply([{ op: "remove_page", page: i }]); } }
    else stApply([{ op: "page", page: SITES.page, title: t.trim() }]);
  };
}

const ST_BICON = { hero: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M7 9h7M7 12.5h10M7 16h4"/>', about: '<circle cx="12" cy="8" r="3.5"/><path d="M5 20a7 7 0 0 1 14 0"/>',
  services: '<rect x="3" y="4" width="8" height="7" rx="1.5"/><rect x="13" y="4" width="8" height="7" rx="1.5"/><rect x="3" y="13" width="8" height="7" rx="1.5"/><rect x="13" y="13" width="8" height="7" rx="1.5"/>',
  prices: '<path d="M4 7h10M4 12h10M4 17h10"/><path d="M17 7h3M17 12h3M17 17h3"/>', features: '<path d="M12 3.5l2.4 5 5.4.6-4 3.7 1.1 5.4L12 15.5l-4.9 2.7 1.1-5.4-4-3.7 5.4-.6z"/>',
  steps: '<circle cx="5" cy="12" r="2"/><circle cx="12" cy="12" r="2"/><circle cx="19" cy="12" r="2"/><path d="M7 12h3M14 12h3"/>', gallery: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 16l5-5 4 4 3-3 6 6"/><circle cx="15.5" cy="8.5" r="1.5"/>',
  products: '<path d="M5 8h14l-1 12H6z"/><path d="M9 10V6.5a3 3 0 0 1 6 0V10"/>', schedule: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
  reviews: '<path d="M20.5 11.5a7.5 7.5 0 0 1-11.2 6.5L4 19.5l1.6-4.6A7.5 7.5 0 1 1 20.5 11.5z"/><path d="M9 10.5h.01M12 10.5h.01M15 10.5h.01"/>',
  team: '<circle cx="8" cy="8.5" r="3"/><circle cx="16.5" cy="9.5" r="2.5"/><path d="M2.5 19.5a5.5 5.5 0 0 1 11 0M14 14.5a4.5 4.5 0 0 1 7.5 3.5"/>', faq: '<circle cx="12" cy="12" r="8.5"/><path d="M9.6 9.4a2.5 2.5 0 0 1 4.8 1c0 1.7-2.4 2-2.4 3.6M12 17.2v.1"/>',
  links: '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>', cta: '<rect x="3" y="8" width="18" height="8" rx="4"/><path d="M9 12h6"/>',
  text: '<path d="M5 6h14M5 10h14M5 14h10M5 18h7"/>', contacts: '<path d="M12 21s-6.5-6.2-6.5-11a6.5 6.5 0 0 1 13 0c0 4.8-6.5 11-6.5 11z"/><circle cx="12" cy="10" r="2.4"/>',
  lead: '<rect x="4" y="4" width="16" height="16" rx="2.5"/><path d="M8 9h8M8 12.5h8"/><rect x="8" y="15" width="5" height="2" rx="1"/>' };

function stBlocksList() {
  const bl = stBlocks(), tones = SITES.meta.tones;
  $("#st-blocks").innerHTML = bl.map((b, j) => {
    const m = stMetaB(b.type), open = SITES.open === b.uid;
    return `<li class="st-b${open ? " open" : ""}${b.uid === SITES.sel ? " sel" : ""}${b.hidden ? " off" : ""}" data-uid="${stE(b.uid)}">
      <div class="st-bh"><span class="st-grip" title="Перетащите, чтобы поменять порядок" aria-hidden="true">${stI('<circle cx="9" cy="6" r="1"/><circle cx="15" cy="6" r="1"/><circle cx="9" cy="12" r="1"/><circle cx="15" cy="12" r="1"/><circle cx="9" cy="18" r="1"/><circle cx="15" cy="18" r="1"/>')}</span>
      <span class="st-bi tone-${stE(b.tone || "base")}" aria-hidden="true">${stI(ST_BICON[b.type] || ST_BICON.text)}</span>
      <button type="button" class="st-bt" aria-expanded="${open}"><b>${stE(b.nav || b.title || m.title)}</b><small>${stE(m.title)} · ${stE(m.variants[b.variant] || "")}</small></button>
      <button type="button" class="st-ib sm st-eye" title="${b.hidden ? "Показать на сайте" : "Скрыть с сайта"}" aria-label="${b.hidden ? "Показать" : "Скрыть"}">${stI(b.hidden ? '<path d="M3 3l18 18M10.6 6.2A9.9 9.9 0 0 1 12 6c5.5 0 9.5 6 9.5 6a17 17 0 0 1-2.7 3.2M6.6 7.7C4 9.3 2.5 12 2.5 12s4 6 9.5 6c1.6 0 3-.4 4.3-1"/>' : '<path d="M2.5 12S6.5 6 12 6s9.5 6 9.5 6-4 6-9.5 6-9.5-6-9.5-6z"/><circle cx="12" cy="12" r="2.8"/>')}</button>
      <button type="button" class="st-ib sm st-del" title="Убрать раздел" aria-label="Убрать раздел">${stI('<path d="M5 7h14M10 7V5h4v2M7 7l1 12.5h8L17 7"/>')}</button></div>
      ${open ? `<div class="st-bf">${stBlockForm(b, j)}</div>` : ""}</li>`;
  }).join("") || `<li class="st-empty">На странице пока нет разделов — добавьте первый.</li>`;
  $$("#st-blocks .st-b").forEach(li => {
    const uid = li.dataset.uid, b = bl.find(x => x.uid === uid);
    li.querySelector(".st-bt").onclick = () => { SITES.open = SITES.open === uid ? "" : uid; SITES.sel = uid; stBlocksList(); stShow(uid); };
    li.querySelector(".st-eye").onclick = () => stApply([{ op: "block", block: uid, hidden: !b.hidden }], b.hidden ? "Раздел показан" : "Раздел скрыт");
    li.querySelector(".st-del").onclick = async () => { if (await ask(`Убрать раздел «${b.nav || b.title || stMetaB(b.type).title}»? Вернуть можно кнопкой «Шаг назад».`, { ok: "Убрать" })) stApply([{ op: "remove_block", block: uid }]); };
    /* тянуть — за строку раздела (за поля формы — нельзя: в них выделяют текст мышью) */
    const bh = li.querySelector(".st-bh");
    bh.onmousedown = (e) => { if (!e.target.closest("button:not(.st-bt)")) li.draggable = true; };
    li.onmouseup = () => { li.draggable = false; };
    li.ondragstart = (e) => { if (!li.draggable) return; e.stopPropagation(); SITES.drag = uid; li.classList.add("drag"); e.dataTransfer.effectAllowed = "move"; try { e.dataTransfer.setData("text/plain", uid); } catch (x) { } };
    li.ondragend = () => { li.draggable = false; li.classList.remove("drag"); $$("#st-blocks .st-b").forEach(x => x.classList.remove("over-t", "over-b")); };
    li.ondragover = (e) => { if (!SITES.drag || SITES.drag === uid) return; e.preventDefault(); const r = li.getBoundingClientRect(), top = e.clientY < r.top + r.height / 2; li.classList.toggle("over-t", top); li.classList.toggle("over-b", !top); };
    li.ondragleave = () => li.classList.remove("over-t", "over-b");
    li.ondrop = (e) => {
      e.preventDefault(); const from = bl.findIndex(x => x.uid === SITES.drag); let to = bl.findIndex(x => x.uid === uid);
      const r = li.getBoundingClientRect(); if (e.clientY >= r.top + r.height / 2) to += 1; if (from < to) to -= 1;
      const u = SITES.drag; SITES.drag = ""; if (from !== to && from >= 0) stApply([{ op: "move_block", block: u, to }], "Порядок разделов");
    };
    if (li.querySelector(".st-bf")) stBlockWire(li, b);
  });
}
function stShow(uid) { const f = $("#st-if"); if (f && f.contentWindow) f.contentWindow.postMessage({ dwsite: "show", id: uid }, "*"); }

/* форма раздела: вариант вёрстки, фон, подпись в меню, поля, карточки */
function stField(key, label, kind, val, scope) {
  const id = `stf-${scope}-${key}`;
  if (kind === "text") return `<label class="st-f"><span>${stE(label)}</span><textarea id="${id}" data-k="${key}" rows="${String(val || "").length > 120 ? 5 : 3}">${stE(val || "")}</textarea></label>`;
  if (kind === "flag") return `<label class="st-flag"><input type="checkbox" data-k="${key}"${val ? " checked" : ""}><span>${stE(label)}</span></label>`;
  if (kind === "image") return `<div class="st-f st-img" data-k="${key}"><span>${stE(label)}</span><div class="st-imgrow">${val ? `<span class="st-imgok">${stI('<path d="M5 12.5l4 4 10-10"/>')}фото добавлено</span>` : `<span class="hint">нет — вместо фото узор в цветах сайта</span>`}
    <button type="button" class="btn small st-pick">${val ? "Заменить" : "Выбрать фото"}</button>${val ? `<button type="button" class="btn small st-noimg">Убрать</button>` : ""}</div></div>`;
  if (kind === "mark") return `<div class="st-f st-markf" data-k="${key}"><span>${stE(label)}</span><div class="st-marks sm">${Object.entries(SITES.meta.marks).map(([k, m]) => `<button type="button" class="st-mk${k === val ? " on" : ""}" data-v="${k}" title="${stE(m.title)}" aria-label="${stE(m.title)}">${m.svg}</button>`).join("")}</div></div>`;
  if (kind === "link") {
    const opts = [["lead", "к форме заявки"], ["contacts", "к контактам"], ["phone", "позвонить"]].concat(stBlocks().filter(b => !["lead", "contacts", "hero"].includes(b.type)).map((b, j) => ["#" + (b.id || "b" + stBlocks().indexOf(b)), "к разделу «" + (b.nav || b.title || stMetaB(b.type).title) + "»"]));
    const cur = val || "lead";
    return `<label class="st-f"><span>${stE(label)}</span><select data-k="${key}">${opts.map(([v, t]) => `<option value="${stE(v)}"${v === cur ? " selected" : ""}>${stE(t)}</option>`).join("")}${opts.some(o => o[0] === cur) ? "" : `<option value="${stE(cur)}" selected>${stE(cur)}</option>`}</select></label>`;
  }
  return `<label class="st-f"><span>${stE(label)}</span><input id="${id}" data-k="${key}" value="${stE(val || "")}"></label>`;
}
function stBlockForm(b) {
  const m = stMetaB(b.type), tones = SITES.meta.tones;
  let h = `<div class="st-row2"><label class="st-f"><span>Вёрстка</span><select data-x="variant">${Object.entries(m.variants).map(([k, t]) => `<option value="${k}"${k === b.variant ? " selected" : ""}>${stE(t)}</option>`).join("")}</select></label>
    <div class="st-f"><span>Фон раздела</span><div class="st-tones">${Object.entries(tones).map(([k, t]) => `<button type="button" class="st-tone tone-${k}${k === (b.tone || "base") ? " on" : ""}" data-v="${k}" title="${stE(t)}" aria-label="${stE(t)}"></button>`).join("")}</div></div></div>`;
  if (b.type !== "hero") h += `<label class="st-f"><span>Пункт меню (пусто — не в меню)</span><input data-x="nav" value="${stE(b.nav || "")}" maxlength="40"></label>`;
  h += m.fields.filter(f => !(b.type === "hero" && f[0] === "button2_to" && !b.button2)).map(([k, l, kind]) => stField(k, l, kind, b[k], b.uid)).join("");
  if (b.type === "reviews") h += `<p class="st-note">Только настоящие отзывы ваших клиентов. Пустой раздел на сайте не показывается.</p>`;
  if (m.items) {
    const [fields, addT] = m.items, its = b.items || [];
    h += `<div class="st-items"><div class="st-ih"><b>${stE(b.type === "gallery" ? "Фото" : "Карточки")}</b><span>${its.length}</span></div>` + its.map((x, i) => `<div class="st-it${x.todo ? " todo" : ""}" data-i="${i}">
      <div class="st-ith"><span>${stE(x.title || x.name || x.q || x.caption || x.time || (b.type === "gallery" ? `Фото ${i + 1}` : `Карточка ${i + 1}`))}</span>${x.todo ? `<em>заглушка — не публикуется, пока не замените</em>` : ""}
      <button type="button" class="st-ib sm st-iu" title="Выше" aria-label="Выше"${i === 0 ? " disabled" : ""}>${stI('<path d="M6 15l6-6 6 6"/>')}</button><button type="button" class="st-ib sm st-ix" title="Убрать" aria-label="Убрать">${stI('<path d="M6 6l12 12M18 6 6 18"/>')}</button></div>
      ${fields.map(([k, l, kind]) => stField(k, l, kind, x[k], `${b.uid}-${i}`)).join("")}</div>`).join("")
      + `<button type="button" class="st-add sm st-iadd">${stI('<path d="M12 5v14M5 12h14"/>')}${stE(addT)}</button></div>`;
  }
  return h;
}
function stBlockWire(li, b) {
  const uid = b.uid, box = li.querySelector(".st-bf");
  box.querySelector('[data-x="variant"]').onchange = (e) => stApply([{ op: "block", block: uid, variant: e.target.value }], "Вёрстка раздела");
  $$(".st-tone", box).forEach(t => t.onclick = () => stApply([{ op: "block", block: uid, tone: t.dataset.v }], "Фон раздела"));
  const nav = box.querySelector('[data-x="nav"]'); if (nav) nav.oninput = () => stLater(uid + "nav", () => [{ op: "block", block: uid, nav: nav.value }], `Меню: ${b.title || b.type}`);
  /* поля самого раздела (не карточек) */
  $$(":scope > .st-f [data-k], :scope > .st-row2 [data-k], :scope > .st-flag [data-k]", box).forEach(el => stWireField(el, (k, v, now) => {
    const o = { op: "block", block: uid }; o[k] = v;
    now ? stApply([o], `Раздел «${b.nav || b.title || b.type}»`) : stLater(uid + k, () => [o], `Текст: ${b.nav || b.title || b.type}`);
  }));
  $$(":scope > .st-img, :scope > .st-markf", box).forEach(el => stWireField(el, (k, v) => { const o = { op: "block", block: uid }; o[k] = v; stApply([o], "Картинка раздела"); }));
  /* карточки */
  $$(".st-it", box).forEach(it => {
    const i = +it.dataset.i;
    $$("[data-k]", it).forEach(el => stWireField(el, (k, v, now) => {
      const o = { op: "item", block: uid, index: i, data: { [k]: v } };
      now ? stApply([o], "Карточка") : stLater(`${uid}-${i}-${k}`, () => [o], `Карточка ${i + 1}: ${b.title || b.type}`);
    }));
    it.querySelector(".st-ix").onclick = () => stApply([{ op: "item", block: uid, index: i, remove: true }], "Карточка убрана");
    it.querySelector(".st-iu").onclick = () => { const its = (b.items || []).slice(); its.splice(i - 1, 0, its.splice(i, 1)[0]); stApply([{ op: "block", block: uid, items: its }], "Порядок карточек"); };
  });
  const add = box.querySelector(".st-iadd");
  if (add) add.onclick = () => { const f = stMetaB(b.type).items[0], d = {}; f.forEach(([k, l, kind]) => { if (kind === "line" || kind === "text") d[k] = ""; }); d[f[0][0]] = f[0][2] === "image" ? "" : "Новая"; stApply([{ op: "item", block: uid, data: d }], "Новая карточка"); };
}
/* одно поле: строки — по мере ввода; флаги, списки, фото, знаки — сразу */
function stWireField(el, put) {
  if (el.classList && el.classList.contains("st-img")) {
    const k = el.dataset.k;
    el.querySelector(".st-pick").onclick = () => stPickImage((name) => put(k, name, true));
    const no = el.querySelector(".st-noimg"); if (no) no.onclick = () => put(k, "", true);
    return;
  }
  if (el.classList && el.classList.contains("st-markf")) {
    const k = el.dataset.k;
    $$(".st-mk", el).forEach(m => m.onclick = () => put(k, m.dataset.v, true));
    return;
  }
  const k = el.dataset.k;
  if (el.type === "checkbox") el.onchange = () => put(k, el.checked, true);
  else if (el.tagName === "SELECT") el.onchange = () => put(k, el.value, true);
  else el.oninput = () => put(k, el.value, false);
}
function stPickImage(done) {
  const inp = document.createElement("input"); inp.type = "file"; inp.accept = "image/jpeg,image/png,image/webp";
  inp.onchange = () => {
    const f = inp.files[0]; if (!f) return;
    if (f.size > 25 * 1024 * 1024) { toast("Фото больше 25 МБ — выберите поменьше", 4000); return; }
    const rd = new FileReader();
    rd.onload = async () => { toast("Уменьшаю и добавляю фото…", 2500); try { const r = await core.call("sites_image", { id: SITES.sid, data: rd.result, alt: f.name.replace(/\.[^.]+$/, "") }); done(r.image); } catch (e) { toast(e.message, 4000); } };
    rd.readAsDataURL(f);
  };
  inp.click();
}

/* добавить раздел: сетка видов с пояснением */
function stAddPop() {
  const p = $("#st-addp");
  p.innerHTML = `<div class="st-popb"><div class="st-dh"><h3>Добавить раздел</h3><button class="st-ib" type="button" id="st-addx" aria-label="Закрыть">${stI('<path d="M6 6l12 12M18 6 6 18"/>')}</button></div>
    <div class="st-addg">${Object.entries(SITES.meta.blocks).map(([k, m]) => `<button type="button" class="st-addi" data-t="${k}"><span class="st-bi">${stI(ST_BICON[k] || ST_BICON.text)}</span><b>${stE(m.title)}</b><small>${stE(m.sub)}</small></button>`).join("")}</div></div>`;
  p.hidden = false;
  const close = () => { p.hidden = true; document.removeEventListener("keydown", esc); };
  const esc = (e) => { if (e.key === "Escape") close(); };
  document.addEventListener("keydown", esc);
  $("#st-addx").onclick = close; p.onclick = (e) => { if (e.target === p) close(); };
  $$("#st-addp .st-addi").forEach(b => b.onclick = async () => {
    close();
    const after = SITES.sel && stBlocks().some(x => x.uid === SITES.sel) ? SITES.sel : "";
    const before = new Set(stBlocks().map(x => x.uid));
    if (await stApply([{ op: "add_block", type: b.dataset.t, page: SITES.page, after }], `Раздел «${SITES.meta.blocks[b.dataset.t].title}»`)) {
      const nb = stBlocks().find(x => !before.has(x.uid)); if (nb) { SITES.open = SITES.sel = nb.uid; stBlocksList(); setTimeout(() => stShow(nb.uid), 400); }
    }
  });
}

/* оформление: палитры, шрифты, углы, шапка */
function stLook() {
  const th = SITES.cur.theme || {}, M = SITES.meta;
  $("#st-look").innerHTML = `<h4>Палитра</h4><div class="st-pals">${Object.entries(M.palettes).map(([k, p]) => `<button type="button" class="st-pal${k === th.palette ? " on" : ""}" data-v="${k}" aria-pressed="${k === th.palette}">
      <span class="st-sw" style="background:${p.bg}"><i style="background:${p.surface}"></i><i style="background:${p.accent}"></i><i style="background:${p.accent2}"></i><i style="background:${p.ink}"></i></span><span>${stE(p.title)}</span></button>`).join("")}</div>
    <div class="st-acc"><label class="st-f"><span>Свой цвет акцента</span><span class="st-colr"><input type="color" id="st-acc" value="${stE((th.colors || {}).accent || M.palettes[th.palette || "pistachio"].accent)}"><button type="button" class="btn small" id="st-accx"${(th.colors || {}).accent ? "" : " hidden"}>Как в палитре</button></span></label></div>
    <h4>Шрифты</h4><div class="st-fonts">${Object.entries(M.fonts).map(([k, f]) => `<button type="button" class="st-font${k === th.fonts ? " on" : ""}" data-v="${k}" aria-pressed="${k === th.fonts}">
      <span class="st-fa" style="font-family:${stE(f.head)};font-weight:${f.hw};${f.italic ? "font-style:italic;" : ""}">Аа</span><span><b>${stE(f.title)}</b><small>${stE(f.sub)}</small></span></button>`).join("")}</div>
    <h4>Углы</h4><div class="st-opts">${Object.entries(M.radii).map(([k, t]) => `<button type="button" class="st-opt rad-${k}${k === th.radius ? " on" : ""}" data-v="${k}"><i></i>${stE(t)}</button>`).join("")}</div>
    <h4>Шапка</h4><div class="st-opts">${Object.entries(M.headers).map(([k, t]) => `<button type="button" class="st-opt hdr-${k}${k === (th.header || "light") ? " on" : ""}" data-v="${k}"><i></i>${stE(t)}</button>`).join("")}</div>
    <h4>Другой дизайн целиком</h4><p class="hint">Тексты и разделы останутся — поменяются цвета, шрифты, меню и вёрстка.</p>
    <div class="st-redo">${M.templates.map(t => `<button type="button" class="st-chipb${t.id === SITES.cur.template ? " on" : ""}" data-v="${t.id}">${stE(t.title)}</button>`).join("")}</div>`;
  $$("#st-look .st-pal").forEach(b => b.onclick = () => stApply([{ op: "palette", name: b.dataset.v }], `Палитра «${M.palettes[b.dataset.v].title}»`));
  $$("#st-look .st-font").forEach(b => b.onclick = () => stApply([{ op: "fonts", name: b.dataset.v }], `Шрифт «${M.fonts[b.dataset.v].title}»`));
  $$("#st-look .rad-sharp, #st-look .rad-soft, #st-look .rad-round").forEach(b => b.onclick = () => stApply([{ op: "radius", name: b.dataset.v }], "Углы"));
  $$('#st-look [class*="hdr-"]').forEach(b => b.onclick = () => stApply([{ op: "header", value: b.dataset.v }], "Шапка"));
  $$("#st-look .st-redo .st-chipb").forEach(b => b.onclick = () => stApply([{ op: "template", id: b.dataset.v }], `Дизайн «${b.textContent}»`));
  $("#st-acc").onchange = (e) => stApply([{ op: "colors", accent: e.target.value }], "Свой цвет акцента");
  $("#st-accx").onclick = () => stApply([{ op: "palette", name: th.palette }], "Цвета палитры");
}

/* шапка: логотип и меню */
function stHead() {
  const s = SITES.cur, lg = s.logo || {}, M = SITES.meta, mn = s.menu || {};
  $("#st-head").innerHTML = `<h4>Логотип</h4>
    <label class="st-f"><span>Надпись</span><input id="st-lgt" value="${stE(lg.text || s.name || "")}" maxlength="60"></label>
    <label class="st-f"><span>Строка под надписью</span><input id="st-tag" value="${stE(s.tagline || "")}" maxlength="160"></label>
    <div class="st-opts st-lgs">${Object.entries(M.logo_styles).map(([k, t]) => `<button type="button" class="st-opt${k === (lg.style || "plain") && !lg.svg ? " on" : ""}" data-v="${k}">${stE(t)}</button>`).join("")}</div>
    <div class="st-f"><span>Знак</span><div class="st-marks">${Object.entries(M.marks).map(([k, m]) => `<button type="button" class="st-mk${k === lg.mark && !lg.svg ? " on" : ""}" data-v="${k}" title="${stE(m.title)}" aria-label="${stE(m.title)}">${m.svg}</button>`).join("")}</div></div>
    <div class="st-own" id="st-own"></div>
    <h4>Меню</h4><div class="st-menus">${Object.entries(M.menus).map(([k, t]) => `<button type="button" class="st-menu m-${k}${k === (mn.style || "top") ? " on" : ""}" data-v="${k}"><span class="st-mw"><i></i><i></i><i></i></span>${stE(t)}</button>`).join("")}</div>
    <label class="st-f"><span>Кнопка в шапке</span><input id="st-cta" value="${stE(mn.cta || "")}" maxlength="40" placeholder="Оставить заявку"></label>
    <p class="hint">Пункты меню — подписи разделов («Пункт меню» в настройке раздела). Несколько страниц — в меню страницы.</p>`;
  $("#st-lgt").oninput = (e) => stLater("lgt", () => [{ op: "logo", text: e.target.value }], "Надпись логотипа");
  $("#st-tag").oninput = (e) => stLater("tag", () => [{ op: "site", tagline: e.target.value }], "Строка под логотипом");
  $("#st-cta").oninput = (e) => stLater("cta", () => [{ op: "menu", cta: e.target.value }], "Кнопка в шапке");
  $$("#st-head .st-lgs .st-opt").forEach(b => b.onclick = () => stApply([{ op: "logo", style: b.dataset.v }], "Вид логотипа"));
  $$("#st-head > .st-f .st-mk").forEach(b => b.onclick = () => stApply([{ op: "logo", mark: b.dataset.v }], "Знак логотипа"));
  $$("#st-head .st-menu").forEach(b => b.onclick = () => stApply([{ op: "menu", style: b.dataset.v }], "Меню"));
  core.call("sites_logos").then(r => {
    const its = (r && r.items) || []; if (!its.length || !$("#st-own")) return;
    $("#st-own").innerHTML = `<div class="st-f"><span>Свой знак из «Рисунков»</span><div class="st-marks own">${its.map((x, i) => `<button type="button" class="st-mk" data-i="${i}" title="${stE(x.name)}">${x.svg}</button>`).join("")}</div></div>`;
    $$("#st-own .st-mk").forEach(b => b.onclick = () => stApply([{ op: "logo", svg: its[+b.dataset.i].svg }], "Свой знак"));
  }).catch(() => {});
}

/* контакты и описание для поисковиков */
function stInfo() {
  const s = SITES.cur, ct = s.contacts || {}, M = SITES.meta, d = (s.seo || {}).description || "", p = s.published || {};
  $("#st-info").innerHTML = `<h4>Контакты</h4><p class="hint">Появятся в разделах «Контакты», «Заявка» и в подвале. Адрес — со ссылкой на карту.</p>
    ${Object.entries(M.contacts).map(([k, t]) => `<label class="st-f"><span>${stE(t)}</span><input data-c="${k}" value="${stE(ct[k] || "")}" maxlength="200"></label>`).join("")}
    <h4>Для поисковиков и соцсетей</h4>
    <label class="st-f"><span>Название сайта</span><input id="st-sname" value="${stE(s.name || "")}" maxlength="80"></label>
    <label class="st-f"><span>Описание <small id="st-dn"></small></span><textarea id="st-desc2" rows="4" maxlength="300" placeholder="Что вы предлагаете, где и почему к вам: 120–160 знаков">${stE(d)}</textarea></label>
    <h4>Сайт</h4><div class="st-danger">${p.name ? `<button type="button" class="btn small" id="st-unpub">Снять с публикации</button>` : ""}<button type="button" class="btn small danger" id="st-delsite">Удалить сайт</button></div>`;
  const dn = () => { const n = $("#st-desc2").value.length; $("#st-dn").textContent = `${n} знаков${n < 120 ? " — лучше 120–160" : n > 170 ? " — длинновато" : " — хорошо"}`; };
  dn();
  $$("#st-info [data-c]").forEach(el => el.oninput = () => stLater("c" + el.dataset.c, () => [{ op: "contacts", [el.dataset.c]: el.value }], "Контакты"));
  $("#st-sname").oninput = (e) => stLater("sname", () => [{ op: "site", name: e.target.value }], "Название сайта");
  $("#st-desc2").oninput = (e) => { dn(); stLater("desc", () => [{ op: "site", description: e.target.value }], "Описание для поисковиков"); };
  if ($("#st-unpub")) $("#st-unpub").onclick = async () => {
    if (!await ask(`Снять сайт с ${p.name}.dewiar.pro? Адрес перестанет открываться, его сможет занять другой человек. Сам сайт останется здесь.`, { ok: "Снять" })) return;
    try { const r = await core.call("sites_unpublish", { id: SITES.sid }); SITES.cur = r.site; SITES.hist = r.history; stBar(); stInfo(); toast("Сайт снят с публикации"); } catch (e) { toast(e.message, 4000); }
  };
  $("#st-delsite").onclick = async () => {
    if (!await ask(`Удалить сайт «${s.name}» совсем${p.name ? " (и снять с dewiar.pro)" : ""}? Это не отменить.`, { ok: "Удалить" })) return;
    try { await core.call("sites_delete", { id: SITES.sid }); SITES.sid = ""; toast("Сайт удалён"); loadSites(); } catch (e) { toast(e.message, 4000); }
  };
}

/* ---------- «Сказать Лире», история, открыть ---------- */
async function stSay(text) {
  const b = $("#st-sayb"), inp = $("#st-sayt");
  if (!text) { inp.focus(); return; }
  b.disabled = true; inp.disabled = true; b.textContent = "Меняю…"; $("#st-say").classList.add("busy");
  try {
    const r = await core.call("sites_say", { id: SITES.sid, text });
    SITES.cur = r.site; SITES.hist = r.history || [];
    inp.value = ""; stBar(); stSide(); stPreview();
    toast(r.said || "Готово", 4000);
  } catch (e) { toast(e.message, 5000); }
  b.disabled = false; inp.disabled = false; b.textContent = "Изменить"; $("#st-say").classList.remove("busy");
}
function stHistory() {
  const d = $("#st-histd");
  $("#st-histl").innerHTML = (SITES.hist || []).map((h, i) => `<li${i === 0 ? ' class="now"' : ""}><span><b>${stE(h.label)}</b><small>${new Date(h.ts * 1000).toLocaleString("ru-RU", { day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" })}${i === 0 ? " · сейчас" : ""}</small></span>
    ${i === 0 ? "" : `<button type="button" class="btn small" data-v="${h.v}">Вернуть</button>`}</li>`).join("");
  $$("#st-histl [data-v]").forEach(b => b.onclick = async () => {
    try { const r = await core.call("sites_restore", { id: SITES.sid, v: +b.dataset.v }); SITES.cur = r.site; SITES.hist = r.history; stBar(); stSide(); stPreview(); stHistory(); toast("Вернула эту версию"); } catch (e) { toast(e.message, 4000); }
  });
  d.hidden = false;
}

/* ---------- публикация ---------- */
async function stPublish() {
  const p = SITES.cur.published || {};
  const box = $("#st-pubbox"), m = $("#st-pubm");
  const close = () => { m.hidden = true; };
  m.onclick = (e) => { if (e.target === m) close(); };
  if (p.name) {                                      // уже опубликован — просто обновить
    const b = $("#st-pub"); b.disabled = true; b.textContent = "Обновляю…";
    try { const r = await core.call("sites_publish", { id: SITES.sid, name: p.name }); SITES.cur = r.site; SITES.hist = r.history; toast(`Обновлено на ${p.name}.dewiar.pro`, 3500); }
    catch (e) { toast(e.message, 6000); }
    stBar(); return;
  }
  let sug = ""; try { sug = (await core.call("sites_suggest", { id: SITES.sid })).name || ""; } catch (e) { }
  box.innerHTML = `<div class="st-dh"><h3 id="st-pubh">Опубликовать сайт</h3><button class="st-ib" type="button" id="st-pubx" aria-label="Закрыть">${stI('<path d="M6 6l12 12M18 6 6 18"/>')}</button></div>
    <p class="hint">Выберите адрес — латиница, цифры и дефис. Сайт откроется у всех сразу, с телефона тоже.</p>
    <label class="st-addr"><span class="st-proto">https://</span><input id="st-pn" value="${stE(sug)}" maxlength="30" spellcheck="false" autocapitalize="off" aria-label="Имя сайта"><span class="st-dom">.dewiar.pro</span></label>
    <p class="st-chk" id="st-chk" aria-live="polite"></p>
    ${SITES.signed ? "" : `<p class="st-warn">Нужен вход аккаунтом dewiar.pro или ключ Dewiar — студия → «Мозг».</p>`}
    <p class="st-rules">Сайты на dewiar.pro проверяет администратор: обман, чужие данные и незаконное блокируются. В подвале каждого сайта — «Пожаловаться».</p>
    <div class="st-mact"><button class="btn" type="button" id="st-pubc">Отмена</button><button class="btn primary" type="button" id="st-pubgo" disabled>Опубликовать</button></div>`;
  m.hidden = false;
  $("#st-pubx").onclick = $("#st-pubc").onclick = close;
  const inp = $("#st-pn"), chk = $("#st-chk"), go = $("#st-pubgo");
  let t = 0, seq = 0;
  const check = async () => {
    const n = inp.value.trim().toLowerCase(), my = ++seq;
    if (!n) { chk.textContent = ""; go.disabled = true; return; }
    chk.className = "st-chk"; chk.textContent = "Проверяю…"; go.disabled = true;
    try {
      const r = await core.call("sites_check", { id: SITES.sid, name: n });
      if (my !== seq) return;
      chk.className = "st-chk " + (r.free ? "ok" : "bad");
      chk.textContent = r.free ? `${n}.dewiar.pro свободен` : (r.reason || "Это имя занято — попробуйте другое");
      go.disabled = !r.free;
    } catch (e) { if (my === seq) { chk.className = "st-chk bad"; chk.textContent = e.message; } }
  };
  inp.oninput = () => { inp.value = inp.value.toLowerCase().replace(/[^a-z0-9-]/g, ""); clearTimeout(t); t = setTimeout(check, 350); };
  check(); setTimeout(() => inp.focus(), 50);
  go.onclick = async () => {
    go.disabled = true; go.textContent = "Публикую…";
    try {
      const r = await core.call("sites_publish", { id: SITES.sid, name: inp.value.trim() });
      SITES.cur = r.site; SITES.hist = r.history; stBar(); stInfo();
      const url = r.site.published.url;
      box.innerHTML = `<div class="st-dh"><h3>Сайт опубликован</h3><button class="st-ib" type="button" id="st-pubx" aria-label="Закрыть">${stI('<path d="M6 6l12 12M18 6 6 18"/>')}</button></div>
        <div class="st-done"><div class="st-qr">${typeof qrPretty === "function" ? qrPretty(url) : ""}</div><div><a class="st-url" href="${stE(url)}" target="_blank" rel="noopener">${stE(url.replace("https://", ""))}</a>
        <p class="hint">Отправьте ссылку клиентам, поставьте в соцсети и на визитку; QR-код — распечатать у кассы. Заявки с формы придут в «Клиенты», посещения — во вкладке «Аналитика».</p>
        <div class="st-mact"><button class="btn" type="button" id="st-cp">Скопировать ссылку</button><a class="btn primary" href="${stE(url)}" target="_blank" rel="noopener">Открыть сайт</a></div></div></div>`;
      $("#st-pubx").onclick = close;
      $("#st-cp").onclick = async () => { try { await navigator.clipboard.writeText(url); toast("Ссылка скопирована"); } catch (e) { toast(url, 5000); } };
    } catch (e) { toast(e.message, 6000); go.disabled = false; go.textContent = "Опубликовать"; }
  };
}

/* ---------- вкладки ---------- */
function stTab(t, quiet) {
  SITES.tab = t;
  $$("#st-tabs button").forEach(b => { b.classList.toggle("on", b.dataset.t === t); b.setAttribute("aria-selected", b.dataset.t === t); });
  $$("#p-sites .st-pane").forEach(p => p.hidden = p.dataset.t !== t);
  if (t === "edit") setTimeout(stFit, 0);
  if (t === "stats") stStats();
  if (t === "leads") stLeads();
  if (t === "seo") stSeo();
}

/* «Аналитика»: просмотры и посетители по дням (линии, подсказка при наведении), откуда, страницы, устройства, заявки */
const ST_REF = [[/^$/, "Напрямую, по ссылке"], [/^#$/, "Внутри сайта"], [/(^|\.)yandex\.|ya\.ru$/, "Яндекс"], [/(^|\.)google\./, "Google"],
  [/(^|\.)(t\.me|telegram\.org|web\.telegram\.org)$/, "Telegram"], [/(^|\.)vk\.(com|ru)$/, "ВКонтакте"], [/(^|\.)ok\.ru$/, "Одноклассники"], [/whatsapp/, "WhatsApp"],
  [/instagram/, "Instagram"], [/(^|\.)mail\.ru$/, "Mail.ru"], [/2gis/, "2ГИС"], [/(^|\.)avito\.ru$/, "Авито"], [/bing\.com$/, "Bing"], [/(^|\.)dzen\.ru$/, "Дзен"]];
const stRef = (r) => { for (const [rx, t] of ST_REF) if (rx.test(r || "")) return t; return r; };
const stNum = (n) => Number(n || 0).toLocaleString("ru-RU");
async function stStats() {
  const box = $("#st-stats"), p = SITES.cur.published || {};
  if (!p.name) {
    box.innerHTML = `<div class="st-zero"><div class="st-zart" aria-hidden="true">${stI('<path d="M3 20h18"/><path d="M6 16v-4M10 16V8M14 16v-6M18 16V5"/>')}</div><h3>Посещения появятся после публикации</h3>
      <p>Сколько людей зашли, откуда — из Яндекса, Telegram или по ссылке, — с телефона или компьютера, какие страницы смотрят и сколько оставили заявок. Без cookie и без слежки за посетителями.</p>
      <button class="btn primary" type="button" id="st-zpub">Опубликовать сайт</button></div>`;
    $("#st-zpub").onclick = stPublish; return;
  }
  box.innerHTML = `<div class="st-loading">Загружаю посещения…</div>`;
  let d;
  try { d = await core.call("sites_stats", { id: SITES.sid, days: SITES.days, prev: true }); } catch (e) { box.innerHTML = `<div class="st-zero"><h3>Посещения не загрузились</h3><p>${stE(e.message)}</p><button class="btn" type="button" id="st-zre">Ещё раз</button></div>`; $("#st-zre").onclick = stStats; return; }
  if (d.blocked !== undefined && (d.blocked ? "blocked" : "live") !== (SITES.cur.published || {}).status) { SITES.cur.published = Object.assign({}, SITES.cur.published, { status: d.blocked ? "blocked" : "live", reason: d.reason || "" }); stBar(); }
  const all = d.days || [], cur = all.slice(-SITES.days), prev = all.slice(0, Math.max(0, all.length - SITES.days));
  const sum = (a, k) => a.reduce((s, x) => s + (x[k] || 0), 0);
  const v = sum(cur, "views"), u = sum(cur, "visitors"), l = sum(cur, "leads"), pv = sum(prev, "views"), pu = sum(prev, "visitors"), pl = sum(prev, "leads");
  const tr = (a, b) => !b ? (a ? `<em class="up">новое</em>` : "") : `<em class="${a >= b ? "up" : "down"}">${a >= b ? "+" : "−"}${Math.abs(Math.round((a - b) / b * 100))}%</em>`;
  const conv = u ? (l / u * 100) : 0;
  box.innerHTML = `<div class="st-shead"><div><h3>Посещаемость</h3><span class="hint">${stE(p.name)}.dewiar.pro · без cookie, посетитель — один раз в сутки</span></div>
      <div class="st-seg sm" id="st-per">${[7, 30, 90].map(n => `<button type="button" data-n="${n}" class="${n === SITES.days ? "on" : ""}">${n} дней</button>`).join("")}</div></div>
    <div class="st-kpis"><div><span>Просмотры</span><b>${stNum(v)}</b>${tr(v, pv)}</div><div><span>Посетители</span><b>${stNum(u)}</b>${tr(u, pu)}</div>
      <div><span>Заявки</span><b>${stNum(l)}</b>${tr(l, pl)}</div><div><span>Заявок на 100 посетителей</span><b>${conv ? conv.toFixed(conv < 10 ? 1 : 0).replace(".", ",") : "0"}</b><em class="mut">${u ? "из тех, кто зашёл" : "ещё нет данных"}</em></div></div>
    <div class="st-card2 st-chart"><div class="st-ch2"><b>По дням</b><span class="st-leg"><i class="s1"></i>Просмотры<i class="s2"></i>Посетители</span></div><div class="st-plot" id="st-plot"></div></div>
    <div class="st-cols"><div class="st-card2"><b class="st-ct">Откуда приходят</b><div id="st-refs"></div></div><div class="st-card2"><b class="st-ct">Популярные страницы</b><div id="st-pages2"></div></div>
      <div class="st-card2"><b class="st-ct">Устройства</b><div id="st-devs"></div></div></div>`;
  $$("#st-per button").forEach(b => b.onclick = () => { SITES.days = +b.dataset.n; stStats(); });
  stPlot($("#st-plot"), cur);
  stBars($("#st-refs"), (d.refs || []).map(r => [stRef(r.ref), r.views]), "Пока никто не заходил — поделитесь ссылкой.");
  const pageTitle = (slug) => { const i = slug === "index" ? 0 : (SITES.cur.pages || []).findIndex(x => x.slug === slug); return i >= 0 ? (SITES.cur.pages[i].title || slug) : slug; };
  stBars($("#st-pages2"), (d.pages || []).map(r => [pageTitle(r.page), r.views]), "Пока нет просмотров.");
  const dv = d.devices || {}, tot = (dv.phone || 0) + (dv.desktop || 0);
  $("#st-devs").innerHTML = tot ? `<div class="st-split"><i class="s1" style="flex:${dv.phone || 0}"></i><i class="s2" style="flex:${dv.desktop || 0}"></i></div>
    <div class="st-dl"><span><i class="s1"></i>С телефона <b>${Math.round((dv.phone || 0) / tot * 100)}%</b><small>${stNum(dv.phone)}</small></span><span><i class="s2"></i>С компьютера <b>${Math.round((dv.desktop || 0) / tot * 100)}%</b><small>${stNum(dv.desktop)}</small></span></div>` : `<p class="hint">Пока нет данных.</p>`;
}
function stBars(el, rows, empty) {
  const max = Math.max(1, ...rows.map(r => r[1]));
  el.innerHTML = rows.length ? `<ul class="st-bars">${rows.slice(0, 8).map(([t, n]) => `<li><span class="st-bl" title="${stE(t)}">${stE(t)}</span><span class="st-bt2"><i style="width:${Math.max(2, n / max * 100)}%"></i></span><b>${stNum(n)}</b></li>`).join("")}</ul>` : `<p class="hint">${stE(empty)}</p>`;
}
/* линии по дням: две серии на одной оси, сетка — волосяные линии, при наведении — вертикаль и подсказка */
function stPlot(el, days) {
  const W = Math.max(320, el.clientWidth || 800), H = 240, L = 40, R = 14, T = 14, B = 28;
  const mx = Math.max(4, ...days.map(d => Math.max(d.views, d.visitors)));
  const step = [1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000, 5000, 10000, 20000, 50000].find(s => mx / s <= 4) || Math.ceil(mx / 4);
  const top = Math.ceil(mx / step) * step, n = days.length;
  const x = (i) => L + (n < 2 ? (W - L - R) / 2 : i * (W - L - R) / (n - 1)), y = (v) => T + (H - T - B) * (1 - v / top);
  const line = (k) => days.map((d, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(d[k]).toFixed(1)}`).join("");
  let g = "";
  for (let v = 0; v <= top; v += step) g += `<path class="gl" d="M${L} ${y(v).toFixed(1)}H${W - R}"/><text class="ax" x="${L - 8}" y="${(y(v) + 3.5).toFixed(1)}" text-anchor="end">${v >= 10000 ? Math.round(v / 1000) + "K" : stNum(v)}</text>`;
  const lab = (i) => new Date(days[i].d + "T12:00").toLocaleDateString("ru-RU", { day: "numeric", month: "short" }).replace(".", "");
  const every = Math.ceil(n / 7);
  for (let i = 0; i < n; i += every) g += `<text class="ax" x="${x(i).toFixed(1)}" y="${H - 8}" text-anchor="middle">${lab(i)}</text>`;
  const area = line("views") + `L${x(n - 1).toFixed(1)} ${y(0)}L${x(0).toFixed(1)} ${y(0)}Z`;
  const last = n - 1;
  el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="Просмотры и посетители по дням">${g}
    <path class="ar1" d="${area}"/><path class="ln1" d="${line("views")}"/><path class="ln2" d="${line("visitors")}"/>
    <circle class="dt1" cx="${x(last).toFixed(1)}" cy="${y(days[last].views).toFixed(1)}" r="4.5"/><circle class="dt2" cx="${x(last).toFixed(1)}" cy="${y(days[last].visitors).toFixed(1)}" r="4.5"/>
    <g class="hov" hidden><path class="cross" d=""/><circle class="dt1" r="4.5"/><circle class="dt2" r="4.5"/></g><rect class="hit" x="${L}" y="${T}" width="${W - L - R}" height="${H - T - B}"/></svg>
    <div class="st-tip" hidden></div>
    <table class="st-sr"><caption>Посещения по дням</caption><tr><th>День</th><th>Просмотры</th><th>Посетители</th><th>Заявки</th></tr>${days.map(d => `<tr><td>${d.d}</td><td>${d.views}</td><td>${d.visitors}</td><td>${d.leads || 0}</td></tr>`).join("")}</table>`;
  const svg = el.querySelector("svg"), hov = svg.querySelector(".hov"), tip = el.querySelector(".st-tip");
  svg.querySelector(".hit").onmousemove = (e) => {
    const r = svg.getBoundingClientRect(), px = (e.clientX - r.left) * W / r.width;
    const i = Math.max(0, Math.min(n - 1, Math.round((px - L) / ((W - L - R) / Math.max(1, n - 1)))));
    const d = days[i]; hov.hidden = false;
    hov.querySelector(".cross").setAttribute("d", `M${x(i).toFixed(1)} ${T}V${H - B}`);
    const [c1, c2] = hov.querySelectorAll("circle"); c1.setAttribute("cx", x(i)); c1.setAttribute("cy", y(d.views)); c2.setAttribute("cx", x(i)); c2.setAttribute("cy", y(d.visitors));
    tip.hidden = false;
    tip.innerHTML = `<b>${new Date(d.d + "T12:00").toLocaleDateString("ru-RU", { weekday: "short", day: "numeric", month: "long" })}</b><span><i class="s1"></i>Просмотры <em>${stNum(d.views)}</em></span><span><i class="s2"></i>Посетители <em>${stNum(d.visitors)}</em></span>${d.leads ? `<span>Заявки <em>${d.leads}</em></span>` : ""}`;
    const tx = x(i) * r.width / W; tip.style.left = `${Math.min(r.width - 170, Math.max(0, tx + 12))}px`; tip.style.top = "10px";
  };
  svg.querySelector(".hit").onmouseleave = () => { hov.hidden = true; tip.hidden = true; };
}

/* «Заявки» */
async function stLeads() {
  const box = $("#st-leads");
  let its = [];
  try { its = (await core.call("sites_leads", { id: SITES.sid })).items || []; } catch (e) { }
  $("#st-nleads").textContent = its.length ? its.length : "";
  box.innerHTML = its.length ? `<div class="st-shead"><div><h3>Заявки с сайта</h3><span class="hint">Каждая — уже в «Клиентах» (знакомый по телефону или почте — записью в его историю). Приходят раз в 2 минуты.</span></div></div>
    <ul class="st-leadl">${its.map(x => `<li><span class="st-la">${stE((x.name || x.contact || "?").trim()[0] || "?").toUpperCase()}</span><span class="st-lw"><b>${stE(x.name || "Без имени")}</b><span>${stE(x.contact)}</span>${x.note ? `<q>${stE(x.note)}</q>` : ""}</span>
      <span class="st-lm"><small>${new Date((x.ts || 0) * 1000).toLocaleString("ru-RU", { day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" })}</small>${x.cid ? `<button type="button" class="btn small" data-cl="${stE(x.cid)}">Открыть в «Клиентах»</button>` : ""}</span></li>`).join("")}</ul>`
    : `<div class="st-zero"><div class="st-zart" aria-hidden="true">${stI('<rect x="4" y="4" width="16" height="16" rx="2.5"/><path d="M8 9h8M8 12.5h8"/><rect x="8" y="15" width="5" height="2" rx="1"/>')}</div><h3>Заявок пока нет</h3>
      <p>${(SITES.cur.published || {}).name ? "Когда посетитель оставит имя и телефон в форме, заявка появится здесь и в «Клиентах», а вам придёт уведомление." : "Опубликуйте сайт — заявки из формы будут приходить сюда и в «Клиенты»."}</p></div>`;
  $$("#st-leads [data-cl]").forEach(b => b.onclick = () => { if (window.CR) CR.cur = b.dataset.cl; const n = $('nav button[data-p="clients"]'); if (n) { n.hidden = false; n.click(); } });
}

/* «Продвижение»: проверка без внешних служб — что улучшить и «Попросить Лиру исправить» */
async function stSeo() {
  const box = $("#st-seo");
  box.innerHTML = `<div class="st-loading">Проверяю сайт…</div>`;
  let a;
  try { a = await core.call("sites_audit", { id: SITES.sid }); } catch (e) { box.innerHTML = `<div class="st-zero"><h3>Не проверилось</h3><p>${stE(e.message)}</p></div>`; return; }
  const bad = a.items.filter(x => !x.ok), good = a.items.filter(x => x.ok);
  $("#st-nseo").textContent = bad.filter(x => x.level === "важно").length || "";
  const ring = (s) => { const r = 52, c = 2 * Math.PI * r; return `<svg viewBox="0 0 128 128" class="st-ring" role="img" aria-label="${s} из 100"><circle cx="64" cy="64" r="${r}" class="bg"/><circle cx="64" cy="64" r="${r}" class="fg ${s >= 85 ? "ok" : s >= 60 ? "mid" : "low"}" stroke-dasharray="${(c * s / 100).toFixed(1)} ${c.toFixed(1)}" transform="rotate(-90 64 64)"/><text x="64" y="70" text-anchor="middle">${s}</text></svg>`; };
  const say = s => s >= 85 ? "Сайт готов к продвижению — осталось немного." : s >= 60 ? "Хорошая основа: поправьте отмеченное — и поисковикам, и людям станет понятнее." : "Начните с важного — это быстро, Лира поможет.";
  box.innerHTML = `<div class="st-seohd">${ring(a.score)}<div><h3>${stE(say(a.score))}</h3><p class="hint">Проверка без внешних служб: заголовки и описания страниц, главный заголовок, подписи к фото, вес, контакты и форма, карточка для соцсетей, заглушки.</p></div></div>
    ${bad.length ? `<h4 class="st-h4">Что улучшить</h4><ul class="st-chk2">${bad.map((x, i) => `<li class="${x.level === "важно" ? "hi" : ""}"><span class="st-ci" aria-hidden="true">${stI(x.level === "важно" ? '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5v5.5M12 16.4v.1"/>' : '<circle cx="12" cy="12" r="8.5"/><path d="M8.5 12h7"/>')}</span>
      <span class="st-cw"><b>${stE(x.title)}</b><span>${stE(x.detail)}</span></span>${x.fix ? `<button type="button" class="btn small" data-i="${i}">${x.title === "Сайт в интернете" ? "Опубликовать" : x.title === "Фото в галерее" ? "Добавить фото" : "Попросить Лиру исправить"}</button>` : ""}</li>`).join("")}</ul>` : ""}
    <details class="st-goodd"${bad.length ? "" : " open"}><summary>Уже хорошо — ${good.length}</summary><ul class="st-chk2 good">${good.map(x => `<li><span class="st-ci ok" aria-hidden="true">${stI('<path d="M5 12.5l4 4 10-10"/>')}</span><span class="st-cw"><b>${stE(x.title)}</b><span>${stE(x.detail)}</span></span></li>`).join("")}</ul></details>
    <div class="st-tips"><h4 class="st-h4">Где рассказать о сайте</h4><ul><li><b>Яндекс Бизнес и Карты, 2ГИС</b> — карточка с адресом, часами и ссылкой на сайт: по ним ищут «рядом».</li>
      <li><b>Соцсети и мессенджеры</b> — ссылка в профиле, закреплённый пост, подпись в каналах.</li><li><b>На месте</b> — QR-код на кассе, визитке, витрине (есть в окне после публикации).</li>
      <li><b>В письмах</b> — ссылка в подписи и в рассылке клиентам.</li></ul>
      <button type="button" class="btn" id="st-askl">Спросить Лиру, как продвигать</button></div>`;
  $$("#st-seo .st-chk2 [data-i]").forEach(b => b.onclick = async () => {
    const x = bad[+b.dataset.i];
    if (x.title === "Сайт в интернете") { stPublish(); return; }
    if (x.title === "Фото в галерее") { const g = stBlocks().find(q => q.type === "gallery"); stTab("edit"); stSeg("blocks"); if (g) { SITES.open = SITES.sel = g.uid; stBlocksList(); stShow(g.uid); } return; }
    b.disabled = true; b.textContent = "Лира исправляет…";
    try { const r = await core.call("sites_say", { id: SITES.sid, text: x.fix }); SITES.cur = r.site; SITES.hist = r.history; stBar(); stSide(); stPreview(); toast(r.said || "Исправлено", 4000); stSeo(); }
    catch (e) { toast(e.message, 5000); b.disabled = false; b.textContent = "Попросить Лиру исправить"; }
  });
  $("#st-askl").onclick = () => { if (typeof qaAsk === "function") qaAsk(`Оцени мой сайт «${SITES.cur.name}» и подскажи, как его продвигать`); };
}

(function stInit() {
  if (!$("#p-sites")) return;
  $("#st-ask").onsubmit = (e) => { e.preventDefault(); const d = $("#st-desc").value.trim(); if (!d) { $("#st-desc").focus(); toast("Опишите дело в паре фраз — чем занимаетесь, где, для кого"); return; } stCreate({ describe: d }, $("#st-make")); };
  $("#st-back").onclick = () => { SITES.sid = ""; loadSites(); };
  $("#st-name").oninput = (e) => stLater("name", () => [{ op: "site", name: e.target.value }], "Название сайта");
  $("#st-undo").onclick = async () => { try { const r = await core.call("sites_undo", { id: SITES.sid }); SITES.cur = r.site; SITES.hist = r.history; stBar(); stSide(); stPreview(); toast("Вернула как было"); } catch (e) { toast(e.message, 3000); } };
  $("#st-hist").onclick = stHistory;
  $("#st-histx").onclick = () => $("#st-histd").hidden = true;
  $("#st-histd").onclick = (e) => { if (e.target.id === "st-histd") $("#st-histd").hidden = true; };
  $("#st-open").onclick = () => core.call("sites_open", { id: SITES.sid }).then(() => toast("Открыла в браузере")).catch(e => toast(e.message, 4000));
  $("#st-pub").onclick = stPublish;
  $("#st-addb").onclick = stAddPop;
  $("#st-say").onsubmit = (e) => { e.preventDefault(); stSay($("#st-sayt").value.trim()); };
  $("#st-page").onchange = (e) => { SITES.page = +e.target.value; SITES.scroll = 0; stSide(); stPreview(); };
  $$("#st-seg button").forEach(b => b.onclick = () => stSeg(b.dataset.s));
  $$("#st-tabs button").forEach(b => b.onclick = () => stTab(b.dataset.t));
  $$("#p-sites .st-dev button").forEach(b => b.onclick = () => { SITES.dev = b.dataset.d; $$("#p-sites .st-dev button").forEach(x => { x.classList.toggle("on", x === b); x.setAttribute("aria-checked", x === b); }); stFit(); });
  core.on("sites", (e) => {
    if (!$("#p-sites").classList.contains("cur")) return;
    if (!SITES.sid) { core.call("sites_list").then(r => { SITES.items = r.items || []; if (!SITES.sid) stShowList(); }).catch(() => {}); return; }
    if (e && e.id === SITES.sid && !SITES.busy && document.activeElement && !/INPUT|TEXTAREA/.test(document.activeElement.tagName)) {
      core.call("sites_get", { id: SITES.sid }).then(r => { if (JSON.stringify(r.site) !== JSON.stringify(SITES.cur)) { SITES.cur = r.site; SITES.hist = r.history; stBar(); stSide(); stPreview(); } }).catch(() => {});
    }
  });
  window.loadSites = loadSites;
})();
