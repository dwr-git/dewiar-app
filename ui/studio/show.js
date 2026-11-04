/* Студия → «Оформление» → «Что показывать» (03.11, группа Telegram и идея №60: «программа становится перегруженной…
   скрывать ненужный функционал даже из интерфейса, чтобы не перегружать, или настраивать под себя — кому-то не нужен
   блок „Для ребёнка“, „Для старших“, Telegram, бизнес-функции»).
   Группы меню и разделы в них — переключателями, плюс три готовых набора: «Всё», «Для себя», «Минимум». Скрытое: нет в
   меню слева и на «Главной», раздел не загружается (данные и облики раздел берёт при первом открытии — core.js secLazy),
   но сама функция работает: напоминания звенят, письма близких приходят. Вернуть — здесь же или поиском на «Главной»
   (find.js: «раздел скрыт — показать?»).
   Хранение — общее с «Главная» → «Настроить» (home.js): раздел со значком на «Главной» скрыт = значка нет в ui.home_apps
   (HM_NAV), так «Главная» и меню всегда согласны; остальные разделы — ui.nav_hide (data-p кнопок; "plugins" — страницы
   плагинов). Выключенное в «Возможностях» (features) здесь видно отдельно, и его можно включить обратно.
   Группы и разделы берутся из самого меню (settings.html): новый раздел появится здесь сам. Меню прячет по классу .nh
   (а не атрибуту hidden — им управляют «Возможности» и «Главная»). */
const SH_LOCK = new Set(["home", "personas", "brain", "ears", "voice", "look", "sound", "hands", "skills", "features", "about"]);
const SH_SKIP = new Set(["home", "plg", "plgnew", "art"]);          // «Главная» — всегда; «Плагин» и «Рисунки» показывает сам плагин
const SH_APP = {};                                          // раздел → значок «Главной»
Object.entries(HM_NAV).forEach(([a, ps]) => ps.forEach(p => { SH_APP[p] = a; }));
/* готовые наборы — что скрыть (остальное показать) */
const SH_WORK = new Set(["team", "clients", "mailing", "sites", "sitechat", "prompter", "pbot", "ref"]);
const SH_MIN = new Set(["chat", "calendar", "reminders", "notes", "close", "memory", "qa", "dw"]);
const SH_SETS = [
  { id: "all", name: "Всё", sub: "Все разделы на виду", hide: () => false },
  { id: "self", name: "Для себя", sub: "Без работы и бизнеса: клиентов, рассылок, сайтов, суфлёра, ботов", hide: (p) => SH_WORK.has(p) },
  { id: "min", name: "Минимум", sub: "Чат, дела, календарь, заметки, близкие, память — и настройки", hide: (p) => !SH_MIN.has(p) },
];
const SH = { busy: false };

const shNavHide = () => new Set((((S && S.ui) || {}).nav_hide) || []);
const shName = (b) => [...b.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent).join(" ").replace(/\s+/g, " ").trim() || b.textContent.trim();
/** Почему раздел не виден: "user" — скрыт здесь или на «Главной»; "feature" — выключен в «Возможностях»; "" — виден */
function shHiddenBy(p) {
  if (SH_LOCK.has(p)) return "";
  if (shUserHidden(p)) return "user";
  return shFeat(p) ? "feature" : "";
}
window.shHiddenBy = shHiddenBy;
function shUserHidden(p) {
  if (shNavHide().has(p)) return true;
  const a = SH_APP[p];
  return !!a && typeof hmApps === "function" && !hmApps().includes(a);
}
/* выключено в «Возможностях»: имя функции (features.X) — её можно включить здесь; "~" — раздел появится вместе с другими */
function shFeat(p) {
  const f = (S && S.features) || {}, a = SH_APP[p];
  if (a && HM_FEAT[a] && !hmFeat(a)) return HM_FEAT[a];
  if (p === "mailing" || p === "sitechat") return f.clients !== true && f.team !== true ? "~" : "";
  return "";
}
/** Меню: скрытые здесь разделы и страницы плагинов — класс .nh (вызывает hmNav после своих правил) */
function shNav() {
  const nh = shNavHide();
  $$("nav button[data-p]").forEach(b => b.classList.toggle("nh", nh.has(b.dataset.p) && !SH_LOCK.has(b.dataset.p)));
  ["#nav-plg-h", "#nav-plugins", "#nav-plg-new", "#nav-plg-all"].forEach(s => { const e = $(s); if (e) e.classList.toggle("nh", nh.has("plugins")); });
}
window.shNav = shNav;

/* группы — по меню: заголовок .ng начинает группу; после «распорки» (.grow) — нижняя группа «Ещё» */
function shModel() {
  const out = []; let g = null;
  for (const el of $("nav").children) {
    if (el.classList.contains("ng")) {
      g = el.id === "nav-plg-h" ? null : { name: (el.dataset.k || el.textContent).trim(), items: [] };
      if (g) out.push(g);
      if (el.id === "nav-plg-h") {
        const on = (typeof PLP !== "undefined" && PLP.cat || []).filter(x => x.installed);
        if (on.length) out.push({ name: "Плагины", items: [{ p: "plugins", name: "Страницы плагинов", sub: on.map(x => x.name).join(", "), ic: (typeof ICONS !== "undefined" && ICONS.plg) || "" }] });
      }
      continue;
    }
    if (el.classList.contains("grow")) { g = { name: "Ещё", items: [] }; out.push(g); continue; }
    if (!g || el.tagName !== "BUTTON" || !el.dataset.p || el.classList.contains("sub") || SH_SKIP.has(el.dataset.p)) continue;
    const ic = el.querySelector("svg.ni");
    g.items.push({ p: el.dataset.p, name: shName(el), sub: el.title || "", lock: SH_LOCK.has(el.dataset.p), svg: ic ? ic.outerHTML : "" });
  }
  return out.filter(x => x.items.length);
}
const shHideable = () => shModel().flatMap(g => g.items).filter(i => !i.lock).map(i => i.p);
function shCurSet() {
  const items = shHideable(), hid = new Set(items.filter(shUserHidden));
  const s = SH_SETS.find(x => items.every(p => !!x.hide(p) === hid.has(p)));
  return s ? s.id : "";
}

/** Сохранить: hidden — какие разделы скрыть (из тех, что здесь есть); feats — что включить в «Возможностях»; play —
    значок «Досуг» на «Главной» (true/false; undefined — как есть) */
async function shSave(hidden, feats, play) {
  if (SH.busy) return;
  let apps = hmApps().slice();
  const nav = [];
  for (const p of hidden) {
    if (SH_LOCK.has(p)) continue;
    const a = SH_APP[p];
    if (a && HM_NAV[a].every(q => hidden.has(q))) { apps = apps.filter(x => x !== a); continue; }   // весь значок — с «Главной»
    nav.push(p);
  }
  for (const [a, ps] of Object.entries(HM_NAV)) if (ps.some(q => !hidden.has(q)) && !apps.includes(a)) apps.push(a);
  if (play === false) apps = apps.filter(x => x !== "play");
  if (play === true && !apps.includes("play")) apps.push("play");
  if (!apps.length) { toast("Хотя бы один раздел со значком на «Главной» оставьте"); shRender(); return; }
  const ui = { home_apps: apps, home_known: hmAll().map(x => x.id), nav_hide: nav };
  const patch = { ui };
  if (feats && Object.keys(feats).length) patch.features = feats;
  SH.busy = true;
  S.ui = Object.assign({}, S.ui, ui);
  if (patch.features) S.features = Object.assign({}, S.features, patch.features);
  hmNav(); shRender();
  try { await save(patch, true); }
  catch (e) { toast(e.message); }
  SH.busy = false;
  if (typeof featuresApply === "function") featuresApply(); else hmNav();
  if (typeof hmRender === "function" && typeof hmCur === "function" && hmCur()) hmRender();
  shRender();
}
function shHiddenNow() { return new Set(shHideable().filter(shUserHidden)); }
function shSet(p, on) {
  const h = shHiddenNow(), feats = {};
  if (on) { h.delete(p); const f = shFeat(p); if (f && f !== "~") feats[f] = true; }
  else h.add(p);
  return shSave(h, feats);
}
window.shShow = (p) => shSet(p, true);
function shGroup(name, on) {
  const g = shModel().find(x => x.name === name); if (!g) return;
  const h = shHiddenNow();
  g.items.filter(i => !i.lock).forEach(i => on ? h.delete(i.p) : h.add(i.p));
  return shSave(h);
}
function shPreset(id) {
  const s = SH_SETS.find(x => x.id === id); if (!s) return;
  const h = new Set(shHideable().filter(p => s.hide(p)));
  const left = shModel().flatMap(g => g.items).filter(i => !h.has(i.p)).length;
  toast(id === "all" ? "Всё снова на виду" : `Набор «${s.name}»: в меню ${left} ${plural(left, "раздел", "раздела", "разделов")}. Вернуть — здесь же`, 3200);
  return shSave(h, null, id === "min" ? false : id === "all" ? true : undefined);
}

function shRender() {
  const box = $("#sh-groups"); if (!box || !S) return;
  const model = shModel(), cur = shCurSet();
  const total = model.flatMap(g => g.items).length;
  $("#sh-sets").innerHTML = SH_SETS.map(s => {
    const n = model.flatMap(g => g.items).filter(i => i.lock || !s.hide(i.p)).length;
    return `<button type="button" class="sh-set" data-set="${s.id}" aria-pressed="${cur === s.id}"><b>${escH(s.name)}</b><span>${escH(s.sub)}</span><em>${n} ${plural(n, "раздел", "раздела", "разделов")}</em></button>`;
  }).join("");
  const hidN = shHideable().filter(shUserHidden).length;
  $("#sh-now").textContent = cur === "all" ? "Сейчас видно всё." : cur ? `Сейчас — «${SH_SETS.find(x => x.id === cur).name}»: скрыто ${hidN} из ${total}.`
    : `Сейчас — свой набор: скрыто ${hidN} из ${total}.`;
  box.innerHTML = model.map(g => {
    const its = g.items, free = its.filter(i => !i.lock);
    if (!free.length) return `<div class="sh-g lock"><div class="sh-gh"><b>${escH(g.name)}</b><small>всегда в меню</small></div>
      <p class="sh-locked">${its.map(i => escH(i.name)).join(" · ")}</p></div>`;
    const vis = its.filter(i => i.lock || (!shUserHidden(i.p) && !shFeat(i.p))).length, gon = free.some(i => !shUserHidden(i.p));
    return `<div class="sh-g${gon ? "" : " off"}" data-g="${escH(g.name)}"><div class="sh-gh"><b>${escH(g.name)}</b><small>${vis === its.length ? "все видны" : vis ? `видно ${vis} из ${its.length}` : "скрыта"}</small>
        <label class="tg" title="${gon ? "Скрыть всю группу" : "Показать всю группу"}"><input type="checkbox" data-sg="${escH(g.name)}" ${gon ? "checked" : ""} aria-label="Группа «${escH(g.name)}»"><i></i></label></div>
      <ul>${its.map(i => {
        const hid = !i.lock && shUserHidden(i.p), f = i.lock ? "" : shFeat(i.p), on = !hid && !f;
        const note = i.lock ? "всегда в меню" : f === "~" ? "Появится вместе с «Клиентами» или «Поручениями»" : f ? "Выключено в «Возможностях» — включите здесь" : "";
        return `<li class="sh-it${on ? "" : " off"}${i.lock ? " lock" : ""}"><i class="sh-ic" aria-hidden="true">${i.svg ? i.svg.replace('class="ni"', "") : ""}</i>
          <span class="sh-t"><b>${escH(i.name)}</b>${note ? `<small class="sh-note">${escH(note)}</small>` : i.sub ? `<small>${escH(i.sub)}</small>` : ""}</span>
          ${i.lock ? "" : `<label class="tg"><input type="checkbox" data-sp="${escH(i.p)}" ${on ? "checked" : ""} ${f === "~" ? "disabled" : ""} aria-label="${escH(i.name)}"><i></i></label>`}</li>`;
      }).join("")}</ul></div>`;
  }).join("");
  $$("#sh-sets .sh-set").forEach(b => b.onclick = () => shPreset(b.dataset.set));
  $$("#sh-groups [data-sg]").forEach(i => i.onchange = () => shGroup(i.dataset.sg, i.checked));
  $$("#sh-groups [data-sp]").forEach(i => i.onchange = () => shSet(i.dataset.sp, i.checked));
}
window.shRender = shRender;

/* «Скорость»: «Облегчённый вид» — сам / включён / выключен (core.js studioLite) */
function liteRender() {
  const seg = $("#lite-seg"); if (!seg || !S) return;
  const m = liteMode(), on = liteOn();
  $$("button", seg).forEach(b => b.setAttribute("aria-checked", String(b.dataset.v === m)));
  $("#lite-now").textContent = m === "auto" ? (on ? `Сейчас включён сам: ${LITE.why || "компьютеру тяжело"}.` : "Сейчас обычный вид — компьютер справляется. Станет тяжело — включится сам.")
    : on ? "Включён: без размытия и украшений, облики персонажей двигаются реже." : "Выключен: полный вид на любом компьютере.";
}
window.liteRender = liteRender;
if ($("#lite-seg")) $$("#lite-seg button").forEach(b => b.onclick = async () => {
  const v = b.dataset.v; if (v === liteMode()) return;
  S.ui = Object.assign({}, S.ui, { studio_lite: v }); studioLite();
  await save({ ui: { studio_lite: v } }, true);
  toast(v === "auto" ? "Облегчённый вид — сам, когда компьютеру тяжело" : v === "on" ? "Облегчённый вид включён" : "Облегчённый вид выключен");
});

document.addEventListener("studio-sec", (e) => { if (e.detail === "look") { shRender(); liteRender(); } });
core.on("settings", () => setTimeout(() => { if (secOn("look") && !SH.busy) shRender(); }, 0))
  .on("plugins", () => setTimeout(() => { shNav(); if (secOn("look")) shRender(); }, 0));
