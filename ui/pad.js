/* Блокнот у виджета: вкладки, правка «как выглядит», сохранение само (core/pad.py — команды pad_*), правки с других
   устройств — событие pad_changed (sync.py). Окно — ui/app.py (pad_open / pad_hide / pad_toggle). */
const $ = (s) => document.querySelector(s), $$ = (s) => [...document.querySelectorAll(s)];
const Q = new URLSearchParams(location.search);
const ED = $("#ed");
const P = { tabs: [], active: "", base: null, dirty: false, saving: false, loaded: false, t: 0, imgCache: {} };

/* ---------- тема и «выезд» ---------- */
function skin(id) {
  const sk = window.dewiarSkin ? dewiarSkin(id) : { id: "brand" };
  document.body.className = document.body.className.replace(/\b(skin-\S+|light|neu)\b/g, "").trim();
  document.body.classList.add("skin-" + sk.id);
  if (sk.light) document.body.classList.add("light");
  if (sk.neu) document.body.classList.add("neu");
  document.documentElement.style.background = getComputedStyle(document.body).getPropertyValue("--paper").trim() || (sk.light ? "#e7edf6" : "#12131b");
}
skin(Q.get("skin") || "");
window.padSide = (side) => { document.body.classList.toggle("side-left", side !== "right"); document.body.classList.toggle("side-right", side === "right"); };
/* окно = лист + зазор до виджета; в зазоре — защёлки (ui/app.py _pad_geom: side, gap, clips [[y, высота]]) */
window.padCfg = (c) => {
  c = c || {}; padSide(c.side || "left");
  const gap = +c.gap || 0, st = document.documentElement.style;
  st.setProperty("--gap-l", (c.side === "right" ? gap : 0) + "px"); st.setProperty("--gap-r", (c.side === "right" ? 0 : gap) + "px");
  $("#clips").innerHTML = (c.clips || []).map(([y, h]) => `<i class="clip" style="top:${y}px;height:${h}px;width:${gap + 10}px"></i>`).join("");
};
try { padCfg(JSON.parse(Q.get("cfg") || "null") || { side: Q.get("side") || "left" }); } catch (e) { padCfg({ side: Q.get("side") || "left" }); }
window.padShown = (side) => { if (side) padSide(side); document.body.classList.remove("snap"); $("#wrap").classList.add("away");
  requestAnimationFrame(() => requestAnimationFrame(() => { $("#wrap").classList.remove("away"); document.body.classList.add("snap"); }));
  setTimeout(() => { if (!document.body.classList.contains("play")) ED.focus(); }, 280); refresh(); };
window.padClose = async () => { gameStop(); await saveNow(); document.body.classList.remove("snap"); setTimeout(() => $("#wrap").classList.add("away"), 90);
  setTimeout(() => { const a = api(); if (a && a.pad_hide) a.pad_hide(); }, 320); };
$("#b-close").onclick = () => padClose();
/* ⇄ — лист на другую сторону от виджета; выбор запоминается (ui.pad_side). Владелец 24.10: «раньше был слева — можно
   переключать на одну или другую сторону?» Не помещается с той стороны (виджет у края экрана) — остаётся, где был. */
$("#b-side").onclick = async () => { const a = api(); if (!a || !a.pad_flip) return;
  const before = document.body.classList.contains("side-right") ? "right" : "left";
  try { const s = await a.pad_flip(); if (s === before) { const h = $("#hint"); h.textContent = "С той стороны не хватает места на экране — отодвиньте виджет от края"; setTimeout(() => { if (/места на экране/.test(h.textContent)) h.textContent = ""; }, 6000); }
    core.call("settings_save", { patch: { ui: { pad_side: s } } }).catch(() => { }); } catch (e) { } };

/* ---------- состояние внизу ---------- */
function status(t, cls) { $("#st").textContent = t; $("#foot").className = cls || ""; }

/* ---------- вкладки ---------- */
function drawTabs() {
  const box = $("#tabs");
  box.innerHTML = "";
  for (const t of P.tabs) {
    const el = document.createElement("div");
    el.className = "tab" + (t.name === P.active ? " on" : ""); el.setAttribute("role", "tab"); el.setAttribute("aria-selected", t.name === P.active);
    el.draggable = true; el.dataset.name = t.name; el.title = t.name + " — двойной щелчок: переименовать; перетащите, чтобы переставить";
    el.innerHTML = `<span></span><button class="x" title="Удалить вкладку" aria-label="Удалить вкладку"><svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6 6 18"/></svg></button>`;
    el.querySelector("span").textContent = t.name;
    el.onclick = (e) => { if (!e.target.closest(".x") && t.name !== P.active) openTab(t.name); };
    el.ondblclick = () => rename(el, t.name);
    el.querySelector(".x").onclick = (e) => { e.stopPropagation(); askDelete(t.name); };
    el.onauxclick = (e) => { if (e.button === 1) askDelete(t.name); };
    el.ondragstart = (e) => { e.dataTransfer.setData("text/x-pad-tab", t.name); e.dataTransfer.effectAllowed = "move"; };
    el.ondragover = (e) => { if ([...e.dataTransfer.types].includes("text/x-pad-tab")) { e.preventDefault(); el.classList.add("drop"); } };
    el.ondragleave = () => el.classList.remove("drop");
    el.ondrop = (e) => { e.preventDefault(); el.classList.remove("drop"); const from = e.dataTransfer.getData("text/x-pad-tab"); if (!from || from === t.name) return;
      const names = P.tabs.map(x => x.name).filter(n => n !== from); names.splice(names.indexOf(t.name), 0, from);
      P.tabs = names.map(n => P.tabs.find(x => x.name === n)); drawTabs(); core.call("pad_order", { names }).catch(() => {}); };
    box.appendChild(el);
  }
  const on = box.querySelector(".tab.on"); if (on) on.scrollIntoView({ block: "nearest", inline: "nearest" });
  tabsFit();
}
/* Не все вкладки влезли (24.10, владелец: «перед „Щитом“ ещё вкладка, но её не вижу и не понимаю, как на неё промотать…
   может, возле плюсика выпадающий список с вкладками»): край ряда тает там, где есть ещё вкладки, колёсико листает ряд,
   а у «+» появляется «⌄» — список всех вкладок; выбрали — она открылась и видна в ряду. */
function tabsFit() {
  const box = $("#tabs"), over = box.scrollWidth > box.clientWidth + 1;
  box.classList.toggle("more-l", over && box.scrollLeft > 1);
  box.classList.toggle("more-r", over && box.scrollLeft + box.clientWidth < box.scrollWidth - 1);
  $("#b-list").hidden = !over; $("#b-list").title = `Все вкладки (${P.tabs.length})`;
  if (!over) tlOpen(false);
}
function tlOpen(on) {
  const m = $("#tl"); m.classList.toggle("on", on); $("#b-list").classList.toggle("on", on); $("#b-list").setAttribute("aria-expanded", String(on));
  if (!on) return;
  m.innerHTML = "";
  for (const t of P.tabs) {
    const b = document.createElement("button"); b.setAttribute("role", "menuitem"); b.setAttribute("aria-current", String(t.name === P.active));
    b.innerHTML = "<i></i><span></span>"; b.querySelector("span").textContent = t.name; b.title = t.name;
    b.onmousedown = (e) => e.preventDefault();
    b.onclick = () => { tlOpen(false); if (t.name !== P.active) openTab(t.name); else ED.focus(); };
    m.appendChild(b);
  }
  const cur = m.querySelector('[aria-current="true"]'); if (cur) cur.scrollIntoView({ block: "nearest" });
}
$("#b-list").onmousedown = (e) => e.preventDefault();
$("#b-list").onclick = () => tlOpen(!$("#tl").classList.contains("on"));
$("#tl").addEventListener("keydown", (e) => {
  const items = [...$("#tl").querySelectorAll("button")], i = items.indexOf(document.activeElement);
  if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); const n = items[(i + (e.key === "ArrowDown" ? 1 : -1) + items.length) % items.length]; if (n) n.focus(); }
  if (e.key === "Escape") { e.stopPropagation(); tlOpen(false); $("#b-list").focus(); }
});
document.addEventListener("mousedown", (e) => { if ($("#tl").classList.contains("on") && !e.target.closest("#tl, #b-list")) tlOpen(false); });
$("#tabs").addEventListener("scroll", () => tabsFit(), { passive: true });
$("#tabs").addEventListener("wheel", (e) => {                 // колёсико над вкладками листает их вбок
  const box = $("#tabs"); if (box.scrollWidth <= box.clientWidth + 1 || e.ctrlKey) return;
  const d = Math.abs(e.deltaX) > Math.abs(e.deltaY) ? e.deltaX : e.deltaY; if (!d) return;
  e.preventDefault(); box.scrollLeft += d;
}, { passive: false });
try { new ResizeObserver(() => tabsFit()).observe($("#tabs")); } catch (e) { window.addEventListener("resize", () => tabsFit()); }
/* Что писать под листом: правду о синхронизации (№216, 23.10: «блокнот говорит, что синхронизировался с устройствами, а на
   андроиде ни блокнота, ни записей» — телефон был на своём ключе, в синхронизации компьютер был один). -> строка. */
let syncSt = null, syncAt = 0;
async function syncLine() {
  if (Date.now() - syncAt > 60000) { try { syncSt = await core.call("sync_status"); syncAt = Date.now(); } catch (e) { syncSt = null; } }
  const st = syncSt;
  if (!st) return "синхронизируется с вашими устройствами";
  if (!st.available || !st.on) return "только на этом компьютере — синхронизация выключена (студия → «Dewiar.pro»)";
  const devs = st.devices || [], phone = devs.some(d => !d.pc);
  if (!devs.length) return "других устройств пока нет — телефон добавляется кодом: студия → «Мозг» → «Добавить устройство»";
  return phone ? "на телефоне — «Мой день» → «Заметки», с пометкой «Блокнот»" : "синхронизируется с вашими устройствами";
}
async function refresh() {
  try {
    const r = await core.call("pad_tabs");
    P.tabs = r.tabs; if (!P.active || !P.tabs.some(t => t.name === P.active)) P.active = r.active;
    drawTabs();
    if (!P.loaded) await openTab(P.active, true);
  } catch (e) { status("Нет связи с Dewiar — " + e.message, "bad"); }
}
async function openTab(name, first) {
  if (!first) await saveNow();
  try {
    const r = await core.call("pad_read", { name });
    P.active = r.name; P.base = r.mtime; P.dirty = false; P.loaded = true;
    ED.innerHTML = PadMD.md2html(r.text); paint(); drawTabs();
    status(`${P.tabs.length > 1 ? `«${r.name}» · сохраняется` : "Сохраняется"} само · ${await syncLine()}`);
    if (!first) ED.focus();
  } catch (e) { status(e.message, "bad"); P.loaded = true; }
}
$("#b-new").onclick = () => newTab();
async function newTab() {
  await saveNow();
  try { const r = await core.call("pad_new", {}); P.tabs = r.tabs; P.active = r.created; drawTabs(); await openTab(r.created, true); ED.focus(); const el = $(`.tab.on`); if (el) rename(el, r.created); }
  catch (e) { status(e.message, "bad"); }
}
function rename(el, name) {
  const sp = el.querySelector("span"); const inp = document.createElement("input"); inp.value = name; sp.replaceWith(inp); inp.focus(); inp.select();
  let done = false;
  const fin = async (ok) => { if (done) return; done = true; const to = inp.value.trim();
    if (ok && to && to !== name) { try { await saveNow(); const r = await core.call("pad_rename", { name, to }); P.tabs = r.tabs; if (P.active === name) P.active = r.tabs.find(t => t.name === to.replace(/[\\/:*?"<>|#\[\]^]/g, " ").replace(/\s+/g, " ").trim().slice(0, 60))?.name || r.active; }
      catch (e) { status(e.message, "bad"); } }
    drawTabs(); };
  inp.onkeydown = (e) => { if (e.key === "Enter") fin(true); if (e.key === "Escape") fin(false); e.stopPropagation(); };
  inp.onblur = () => fin(true);
}
let askFn = null;
function askDelete(name) {
  $("#ask-t").textContent = P.tabs.length > 1 ? `Удалить вкладку «${name}»? Она уйдёт в корзину Dewiar.` : `Очистить «${name}»? Последнюю вкладку не удаляю.`;
  $("#ask").classList.add("on"); $("#ask-yes").focus();
  askFn = async () => { $("#ask").classList.remove("on");
    try { const r = await core.call("pad_delete", { name }); P.tabs = r.tabs; if (P.active === name || !P.tabs.some(t => t.name === P.active)) { P.loaded = false; P.active = r.active; } drawTabs();
      if (!P.loaded || P.active !== name) await openTab(P.active, true); } catch (e) { status(e.message, "bad"); } };
}
$("#ask-yes").onclick = () => askFn && askFn();
$("#ask-no").onclick = () => $("#ask").classList.remove("on");

/* ---------- сохранение ---------- */
function changed() { P.dirty = true; clearTimeout(P.t); P.t = setTimeout(saveNow, 700); status("Сохраняю…", "busy"); }
async function saveNow() {
  clearTimeout(P.t);
  if (!P.dirty || !P.active || P.saving) return;
  P.saving = true; P.dirty = false;
  const md = PadMD.html2md(ED);
  try {
    const r = await core.call("pad_write", { name: P.active, text: md, base: P.base });
    P.base = r.mtime;
    if (r.conflict) { status(`Её правили и на другом устройстве — их вариант сохранён во вкладке «${r.conflict}»`, "busy"); refresh(); }
    else status("Сохранено · " + await syncLine());
  } catch (e) { P.dirty = true; status("Не сохранилось: " + e.message, "bad"); }
  P.saving = false;
  if (P.dirty) changed();
}
ED.addEventListener("input", () => { P.lastInput = performance.now(); tidy(); ensureP(); changed(); });
ED.addEventListener("focus", ensureP);
window.addEventListener("beforeunload", () => { if (P.dirty) saveNow(); });
core.on("pad_changed", async (e) => {                 // правка с другого устройства
  if (e.deleted || e.name !== P.active) return refresh();
  if (P.dirty || document.activeElement === ED && Date.now() - lastKey < 4000) return;   // сейчас печатают — их вариант не перетирает
  const r = await core.call("pad_read", { name: P.active }).catch(() => null);
  if (r && r.mtime !== P.base) { P.base = r.mtime; ED.innerHTML = PadMD.md2html(r.text); paint(); status("Обновлено с другого устройства"); }
});
core.on("hello", (d) => { try { const u = (d && d.settings && d.settings.ui) || {}; if (u.skin) skin(u.skin); textSize(u.pad_text, true); gamesOn((d.settings || {}).features); } catch (e) { }
  if (P.loaded) { P.loaded = false; refresh(); } });
core.on("settings", (e) => { try { const st = (e && e.settings) || e || {}, u = st.ui || {}; if (u.skin) skin(u.skin); textSize(u.pad_text, true); gamesOn(st.features); } catch (x) { } });   // тему сменили в студии        // ядро перезапустилось — перечитать

/* ---------- картинки ---------- */
/* пустой лист — всегда с абзацем: иначе первая строка — голый текст без блока, и «- », «[] » не срабатывают (WebKitGTK) */
function ensureP() {
  if (!ED.firstElementChild || (ED.childNodes.length && [...ED.childNodes].every(n => n.nodeType === 3))) {
    const t = ED.textContent; ED.innerHTML = "<p>" + (t ? t.replace(/</g, "&lt;") : "<br>") + "</p>";
    if (document.activeElement === ED) { const r = document.createRange(); r.selectNodeContents(ED.firstChild); r.collapse(false); const sel = getSelection(); sel.removeAllRanges(); sel.addRange(r); }
  }
  blank();
}
function blank() { ED.classList.toggle("blank", !ED.textContent.trim() && !ED.querySelector("li, img, table, hr, pre")); }
function paint() {
  ensureP();
  for (const img of ED.querySelectorAll("img[data-src]:not([src])")) {
    const link = img.getAttribute("data-src");
    if (/^https?:/i.test(link)) { img.src = link; continue; }
    if (P.imgCache[link]) { img.src = P.imgCache[link]; continue; }
    core.call("pad_file", { link }).then(r => { P.imgCache[link] = r.url; img.src = r.url; }).catch(() => { img.alt = "картинка не найдена: " + link; });
  }
}
async function addImages(files) {
  for (const f of files) {
    if (!/^image\//.test(f.type)) continue;
    status("Кладу картинку…", "busy");
    const b64 = await new Promise((ok, bad) => { const r = new FileReader(); r.onload = () => ok(r.result); r.onerror = bad; r.readAsDataURL(f); });
    try {
      const name = f.name && f.name !== "image.png" ? f.name : "Снимок " + new Date().toLocaleString("ru-RU").replace(/[:/]/g, "-").replace(",", "") + ".png";
      const r = await core.call("pad_attach", { name: P.active, filename: name, b64 });
      const link = r.line.match(/\]\(([^)]+)\)/)[1];
      P.imgCache[link] = b64;
      insertHtml(`<p><img alt="" data-src="${link.replace(/"/g, "&quot;")}" src="${b64}"></p><p><br></p>`);
      const im = [...ED.querySelectorAll("img[data-src]")].find(i => i.getAttribute("data-src") === link);
      if (im) lastImg = { img: im, t: performance.now() };
      changed();
    } catch (e) { status("Картинка не легла: " + e.message, "bad"); }
  }
}
$("#file").onchange = (e) => { addImages([...e.target.files]); e.target.value = ""; };

/* ---------- вставка: картинки, таблицы, ссылки, Markdown ---------- */
function insertHtml(html) { ED.focus(); document.execCommand("insertHTML", false, html); }
/* 24.10, владелец (Ubuntu): «вставить скриншот из буфера — не работает»: WebKitGTK отдаёт странице при вставке только
   текст, картинки нет. Как у виджета (hud: pasteImage) — берём её у окна (Api.clipboard_image: буфер GTK, на Windows —
   Pillow) и кладём как файл. */
async function clipImage() {
  const a = window.pywebview && window.pywebview.api;
  const url = a && a.clipboard_image ? await a.clipboard_image().catch(() => "") : "";
  if (!url) { status("В буфере обмена нет картинки — скопируйте снимок экрана или фото и вставьте ещё раз.", "bad"); return false; }
  const blob = await (await fetch(url)).blob();
  addImages([new File([blob], "image.png", { type: blob.type || "image/png" })]);
  return true;
}
ED.addEventListener("paste", (e) => {
  const dt = e.clipboardData; if (!dt) return;
  const imgs = [...dt.files].filter(f => /^image\//.test(f.type))
    .concat([...(dt.items || [])].filter(x => x.kind === "file" && /^image\//.test(x.type)).map(x => x.getAsFile()).filter(Boolean));
  if (imgs.length) { e.preventDefault(); addImages(imgs.slice(0, dt.files.length || imgs.length)); return; }
  const html = dt.getData("text/html"), text = dt.getData("text/plain");
  e.preventDefault();
  if (!text && (!(html && html.trim()) || /^\s*(?:<meta[^>]*>\s*)?<img[^>]*>\s*$/i.test(html))) { clipImage(); return; }   // ни текста — значит, картинка
  const after = (h) => /<\/(table|pre|ul|ol|blockquote)>$/.test(h) ? h + "<p><br></p>" : h;   // после таблицы и списка — дальше обычной строкой
  if (html && !/^\s*$/.test(html)) { insertHtml(after(PadMD.md2html(PadMD.html2md(html)))); }      // сайт, Word, таблица — в наш вид, лишнее прочь
  else if (/^\s*https?:\/\/\S+\s*$/.test(text)) {
    const sel = getSelection(); const u = text.trim();
    if (sel && !sel.isCollapsed) document.execCommand("createLink", false, u); else insertHtml(`<a href="${u.replace(/"/g, "%22")}">${u.replace(/</g, "&lt;")}</a>&nbsp;`);
  } else if (/(^|\n)\s*([-*+] |\d+[.)] |#{1,3} |\|.*\||```|> )/.test(text) || /\[[^\]]+\]\(|\*\*/.test(text)) insertHtml(after(PadMD.md2html(text)));
  else document.execCommand("insertText", false, text);
  changed();
});
ED.addEventListener("drop", (e) => { const f = [...(e.dataTransfer?.files || [])].filter(x => /^image\//.test(x.type)); if (f.length) { e.preventDefault(); addImages(f); } });

/* ---------- клавиши и Markdown на лету ---------- */
let lastKey = 0;
const block = () => { let n = getSelection().anchorNode; while (n && n !== ED && !(n.nodeType === 1 && /^(P|DIV|H[1-6]|LI|BLOCKQUOTE|PRE)$/.test(n.tagName))) n = n.parentNode; return n === ED ? null : n; };
ED.addEventListener("keydown", (e) => {
  lastKey = Date.now();
  const k = e.key, mod = e.ctrlKey || e.metaKey;
  const si = selImg();
  if (si && (k === "Delete" || k === "Backspace")) { e.preventDefault(); imgRemove(si); return; }
  if (mod && !e.shiftKey && (k === "z" || k === "я") && lastImg && ED.contains(lastImg.img) && !(P.lastInput > lastImg.t + 50)) {
    e.preventDefault(); imgRemove(lastImg.img); return;             // отмена сразу после вставки картинки — убрать её
  }
  if (si && !mod && k.length === 1) imgSel(null);
  if (mod && (k === "b" || k === "и")) { e.preventDefault(); cmd("bold"); return; }
  if (mod && (k === "i" || k === "ш")) { e.preventDefault(); cmd("italic"); return; }
  if (mod && (k === "k" || k === "л")) { e.preventDefault(); cmd("link"); return; }
  if (mod && (k === "s" || k === "ы")) { e.preventDefault(); saveNow(); return; }
  if (k === "Tab") { const b = block(); if (b && b.tagName === "LI") { e.preventDefault(); document.execCommand(e.shiftKey ? "outdent" : "indent"); changed(); } else { e.preventDefault(); document.execCommand("insertText", false, "    "); } return; }
  if (k === "Enter" && !e.shiftKey) {
    const b = block();
    if (b && b.tagName === "LI" && b.classList.contains("task")) setTimeout(() => { const n = block(); if (n && n !== b && n.tagName === "LI") { n.classList.add("task"); n.setAttribute("data-done", "0"); } }, 0);
    if (b && b.tagName === "P" && /^```\s*$/.test(b.textContent)) { e.preventDefault(); b.outerHTML = "<pre><code>​</code></pre><p><br></p>"; changed(); return; }
    if (b && b.tagName === "P" && /^(-{3,}|\*{3,})$/.test(b.textContent.trim())) { e.preventDefault(); b.outerHTML = "<hr><p><br></p>"; const p = ED.querySelector("hr + p"); caretIn(p); changed(); return; }
  }
  if (k === " ") {                                   // «- », «1. », «[] », «# », «> » в начале строки
    ensureP();
    const b = block(); if (!b || b.tagName === "PRE") return;
    const sel = getSelection(); if (!sel.rangeCount) return;
    const r = sel.getRangeAt(0);
    const pre = r.cloneRange(); pre.selectNodeContents(b); pre.setEnd(r.endContainer, r.endOffset);
    const t = pre.toString();
    if (!/^(#{1,3}|[-*+]|1[.)]|\[\s?\]|-\s\[\s?\]|>)$/.test(t)) return;
    e.preventDefault();
    shortcut(b, t);
    changed();
  }
});
/* Markdown на лету — сами, через DOM: execCommand в WebKitGTK (Ubuntu) ставил список не туда, а текст оставался рядом */
function shortcut(b, t) {
  let left = t.length;                                // убрать «- » из начала строки
  const tw = document.createTreeWalker(b, NodeFilter.SHOW_TEXT);
  while (left > 0 && tw.nextNode()) { const n = tw.currentNode, k = Math.min(left, n.nodeValue.length); n.nodeValue = n.nodeValue.slice(k); left -= k; }
  const kids = [...b.childNodes].filter(n => !(n.nodeType === 3 && !n.nodeValue) && n.nodeName !== "BR");
  const fill = (el) => { kids.forEach(n => el.appendChild(n)); if (!el.textContent && !el.querySelector("img")) el.appendChild(document.createElement("br")); return el; };
  let target;
  if (b.tagName === "LI") {                           // уже в списке: «[] » — сделать задачей
    if (/\[/.test(t)) { b.classList.add("task"); b.setAttribute("data-done", "0"); }
    target = b;
  } else if (/^#/.test(t)) { target = fill(document.createElement("h" + t.length)); b.replaceWith(target); }
  else if (t === ">") { const q = document.createElement("blockquote"); target = fill(document.createElement("p")); q.appendChild(target); b.replaceWith(q); }
  else {
    const ol = /^1/.test(t), task = /\[/.test(t), li = fill(document.createElement("li"));
    if (task) { li.className = "task"; li.setAttribute("data-done", "0"); }
    const prev = b.previousElementSibling;
    if (prev && prev.tagName === (ol ? "OL" : "UL")) { prev.appendChild(li); b.remove(); }
    else { const list = document.createElement(ol ? "ol" : "ul"); list.appendChild(li); b.replaceWith(list); }
    target = li;
  }
  const rr = document.createRange(), first = (() => { const w = document.createTreeWalker(target, NodeFilter.SHOW_TEXT); return w.nextNode(); })();
  if (first) rr.setStart(first, 0); else rr.setStart(target, 0);
  rr.collapse(true); const sel = getSelection(); sel.removeAllRanges(); sel.addRange(rr);
  blank();
}
document.addEventListener("keydown", (e) => {
  document.body.classList.toggle("ctrl", e.ctrlKey || e.metaKey);
  if (e.key === "Escape") { if ($("#tl").classList.contains("on")) tlOpen(false); else if ($("#ask").classList.contains("on")) $("#ask").classList.remove("on"); else padClose(); }
  if ((e.ctrlKey || e.metaKey) && (e.key === "t" || e.key === "е")) { e.preventDefault(); newTab(); }
  if ((e.ctrlKey || e.metaKey) && e.key === "Tab") { e.preventDefault(); const i = P.tabs.findIndex(t => t.name === P.active); const n = P.tabs[(i + (e.shiftKey ? -1 : 1) + P.tabs.length) % P.tabs.length]; if (n) openTab(n.name); }
});
document.addEventListener("keyup", (e) => document.body.classList.toggle("ctrl", e.ctrlKey || e.metaKey));
function caretIn(el) { if (!el) return; const r = document.createRange(); r.selectNodeContents(el); r.collapse(true); const s = getSelection(); s.removeAllRanges(); s.addRange(r); }
function makeTasks() {
  const b = block();
  if (!b || b.tagName !== "LI") document.execCommand("insertUnorderedList");
  const li = block(); if (!li || li.tagName !== "LI") return;
  const list = li.parentNode;
  if (list.tagName === "OL") { const ul = document.createElement("ul"); ul.innerHTML = list.innerHTML; list.replaceWith(ul); }
  const cur = block(); if (cur && cur.tagName === "LI") { const on = cur.classList.contains("task"); cur.classList.toggle("task", !on); if (!on) cur.setAttribute("data-done", "0"); else cur.removeAttribute("data-done"); }
}
/* галочка: щелчок по квадратику слева от задачи; ссылка: Ctrl+щелчок — открыть */
ED.addEventListener("mousedown", (e) => {
  const li = e.target.closest && e.target.closest("li.task");
  if (li && e.clientX - li.getBoundingClientRect().left < 22) {
    e.preventDefault(); li.setAttribute("data-done", li.getAttribute("data-done") === "1" ? "0" : "1"); changed();
  }
});
ED.addEventListener("click", (e) => {
  const a = e.target.closest && e.target.closest("a[href]");
  if (a && (e.ctrlKey || e.metaKey)) { e.preventDefault(); const x = api(); const u = a.getAttribute("href"); if (/^https?:/i.test(u)) { if (x && x.open_url) x.open_url(u); else window.open(u, "_blank"); } }
  imgSel(e.target.tagName === "IMG" ? e.target : null);
});
/* Картинка: щелчок — рамка и «×»; Delete, Backspace или «×» — убрать; Ctrl+Z сразу после вставки — тоже. 24.10, владелец:
   «вставил скриншот из буфера, пробовал убрать Ctrl+Z, пробовал Delete — не получается»: рамка была только видом, а
   клавиши работали с курсором; отмену WebKit теряет, потому что картинка встаёт после загрузки файла. */
let lastImg = null;
const selImg = () => ED.querySelector("img.sel");
function imgSel(img) {
  ED.querySelectorAll("img.sel").forEach(i => { if (i !== img) i.classList.remove("sel"); });
  if (img) img.classList.add("sel");
  imgBtn();
}
function imgBtn() {
  const b = $("#imgx"), img = selImg();
  if (!img) { b.hidden = true; return; }
  const sh = $("#sheet"), r = img.getBoundingClientRect(), s = sh.getBoundingClientRect();
  b.style.top = (r.top - s.top + sh.scrollTop + 8) + "px"; b.style.left = (Math.max(r.left + 8, r.right - 38) - s.left + sh.scrollLeft) + "px"; b.hidden = false;
}
function imgRemove(img) {
  if (!img || !ED.contains(img)) return false;
  const p = img.closest("p, div:not(#ed), li, td, th");
  img.remove(); if (lastImg && lastImg.img === img) lastImg = null;
  if (p && ED.contains(p) && p.tagName === "P" && !p.textContent.trim() && !p.querySelector("img")) {
    const nx = p.nextElementSibling;
    if (nx && nx.tagName === "P" && !nx.textContent.trim() && !nx.querySelector("img")) { p.remove(); caretIn(nx); }
    else { p.innerHTML = "<br>"; caretIn(p); }
  }
  ensureP(); blank(); imgBtn(); changed(); status("Картинка убрана", "");
  return true;
}
$("#imgx").addEventListener("mousedown", (e) => e.preventDefault());
$("#imgx").onclick = () => imgRemove(selImg());
$("#sheet").addEventListener("scroll", () => { if (selImg()) imgBtn(); }, { passive: true });
addEventListener("resize", () => { if (selImg()) imgBtn(); });
ED.addEventListener("mouseover", (e) => { $("#hint").textContent = e.target.closest && e.target.closest("a[href]") ? "Ctrl+щелчок — открыть ссылку" : ""; });

/* ---------- панель ---------- */
async function cmd(c) {
  ED.focus();
  if (c === "h1" || c === "h2") { const b = block(); document.execCommand("formatBlock", false, b && b.tagName === c.toUpperCase() ? "p" : c); }
  else if (c === "bold" || c === "italic") document.execCommand(c);
  else if (c === "strike") document.execCommand("strikeThrough");
  else if (c === "ul") document.execCommand("insertUnorderedList");
  else if (c === "ol") document.execCommand("insertOrderedList");
  else if (c === "task") makeTasks();
  else if (c === "link") {
    const s = getSelection(); const txt = s ? s.toString() : ""; const keep = s && s.rangeCount ? s.getRangeAt(0).cloneRange() : null;
    const u = await askText("Адрес ссылки", /^https?:\/\//.test(txt) ? txt : "https://", { ok: "Вставить" }); if (!u || u === "https://") return;
    ED.focus(); if (keep) { s.removeAllRanges(); s.addRange(keep); }              // окно вопроса забрало выделение — вернуть
    if (s && !s.isCollapsed) document.execCommand("createLink", false, u); else insertHtml(`<a href="${u.replace(/"/g, "%22")}">${u.replace(/</g, "&lt;")}</a>&nbsp;`);
  } else if (c === "table") insertHtml("<table><thead><tr><th>Столбец</th><th>Столбец</th></tr></thead><tbody><tr><td><br></td><td><br></td></tr><tr><td><br></td><td><br></td></tr></tbody></table><p><br></p>");
  else if (c === "image") { $("#file").click(); return; }
  else if (c === "hr" || c === "quote") {            // 24.10, владелец: «не хватает разделителя-черты» — сами, через DOM (как shortcut)
    ensureP();
    const b = block(); let top = b; while (top && top.parentNode !== ED) top = top.parentNode;
    if (c === "hr") {
      const hr = document.createElement("hr"); let p = document.createElement("p"); p.innerHTML = "<br>";
      if (!top) { ED.appendChild(hr); ED.appendChild(p); }
      else {
        if (top.tagName === "P" && !top.textContent.trim() && !top.querySelector("img")) top.replaceWith(hr); else top.after(hr);
        const nx = hr.nextElementSibling;
        if (nx && nx.tagName === "P" && !nx.textContent.trim() && !nx.querySelector("img")) p = nx; else hr.after(p);
      }
      caretIn(p);
    } else if (b) {
      const q = b.closest("blockquote");
      if (q) { while (q.firstChild) q.parentNode.insertBefore(q.firstChild, q); q.remove(); }
      else { const t = b.tagName === "LI" ? b.parentNode : b; const nq = document.createElement("blockquote"); t.replaceWith(nq); nq.appendChild(t); caretIn(t.tagName === "P" ? t : b); }
    }
  }
  else if (c === "code") { const s = getSelection(); const t = s ? s.toString() : ""; if (t && !t.includes("\n")) insertHtml(`<code>${t.replace(/</g, "&lt;")}</code>&nbsp;`); else document.execCommand("formatBlock", false, "pre"); }
  tidy(); changed();
}
$$("#tools .tool").forEach(b => { b.onmousedown = (e) => e.preventDefault(); b.onclick = () => cmd(b.dataset.c); });
/* Chrome/WebKit при правке иногда оставляют <div> вместо <p> и <span style> — приводим к нашему виду */
function tidy() {
  for (const d of ED.querySelectorAll(":scope > div")) { const p = document.createElement("p"); p.innerHTML = d.innerHTML; d.replaceWith(p); }
  for (const p of ED.querySelectorAll(":scope > p")) {          // список или таблица внутри абзаца (так делает Chrome) — наружу; курсор остаётся
    const k = p.firstElementChild;
    if (k && p.childNodes.length === 1 && /^(UL|OL|TABLE|PRE|BLOCKQUOTE|H[1-3])$/.test(k.tagName)) p.replaceWith(k);
  }
  for (const s of ED.querySelectorAll("span[style], font")) s.replaceWith(...s.childNodes);
  for (const b of ED.querySelectorAll("b")) { const n = document.createElement("strong"); n.innerHTML = b.innerHTML; b.replaceWith(n); }
  for (const i of ED.querySelectorAll("i")) { const n = document.createElement("em"); n.innerHTML = i.innerHTML; i.replaceWith(n); }
  for (const s of ED.querySelectorAll("strike")) { const n = document.createElement("s"); n.innerHTML = s.innerHTML; s.replaceWith(n); }
}

/* ---------- размер текста (22.10): «Aa» на панели — ползунок 80–170 %, Ctrl + колёсико, Ctrl+= / Ctrl+− / Ctrl+0;
   хранится в настройках (ui.pad_text) — одинаковый на этом компьютере после перезапуска ---------- */
let PZ = 1, pzT = 0;
function textSize(v, quiet) {
  const n = Math.round(Math.max(0.8, Math.min(1.7, +v || 1)) * 100) / 100;
  if (quiet && n === PZ) return;
  PZ = n; document.documentElement.style.setProperty("--pz", n);
  $("#sz-r").value = Math.round(n * 100); $("#sz-v").textContent = Math.round(n * 100) + " %";
  if (!quiet) { clearTimeout(pzT); pzT = setTimeout(() => core.call("settings_save", { patch: { ui: { pad_text: n === 1 ? null : n } } }).catch(() => { }), 400); }
}
const szOpen = (on) => { $("#sz").classList.toggle("on", on); $("#b-size").classList.toggle("on", on); $("#b-size").setAttribute("aria-expanded", String(on)); };
$("#b-size").onmousedown = (e) => e.preventDefault();
$("#b-size").onclick = () => szOpen(!$("#sz").classList.contains("on"));
$("#sz-r").oninput = () => textSize($("#sz-r").value / 100);
$("#sz-m").onclick = () => textSize(PZ - 0.1);
$("#sz-p").onclick = () => textSize(PZ + 0.1);
$("#sz-v").onclick = () => textSize(1);
document.addEventListener("mousedown", (e) => { if ($("#sz").classList.contains("on") && !e.target.closest("#sz, #b-size")) szOpen(false); });
$("#sheet").addEventListener("wheel", (e) => { if (!(e.ctrlKey || e.metaKey)) return; e.preventDefault(); textSize(PZ + (e.deltaY < 0 ? 0.05 : -0.05)); }, { passive: false });
document.addEventListener("keydown", (e) => {
  if (!(e.ctrlKey || e.metaKey) || e.altKey) return;
  if (e.key === "=" || e.key === "+") { e.preventDefault(); textSize(PZ + 0.1); }
  else if (e.key === "-" || e.key === "_") { e.preventDefault(); textSize(PZ - 0.1); }
  else if (e.key === "0") { e.preventDefault(); textSize(1); }
}, true);
textSize(1, true);

/* ---------- размер листа (22.10: «как виджет — менять размер»): уголок внизу, дальний от виджета ----------
   Окно меняет размер на лету (Api.pad_resize), отпустили — размер в настройки (ui.pad_w, ui.pad_h при масштабе 100 %).
   Двойной щелчок — как задумано. */
(() => {
  const g = $("#grip"); let rs = null, raf = 0, last = null;
  g.addEventListener("pointerdown", async (ev) => {
    ev.preventDefault(); ev.stopPropagation();
    const a = api(); if (!a || !a.pad_resize) return;
    g.setPointerCapture(ev.pointerId); g.classList.add("on");
    rs = { sx: ev.screenX, sy: ev.screenY, left: document.body.classList.contains("side-left"), size: await a.pad_size() };
  });
  g.addEventListener("pointermove", (ev) => {
    if (!rs || !rs.size) return;
    const dx = ev.screenX - rs.sx;
    last = [Math.round(rs.size[0] + (rs.left ? -dx : dx)), Math.round(rs.size[1] + ev.screenY - rs.sy)];
    if (!raf) raf = requestAnimationFrame(() => { raf = 0; const a = api(); if (a && last) a.pad_resize(last[0], last[1], false); });
  });
  const save = (b) => { if (b) core.call("settings_save", { patch: { ui: { pad_w: b[0], pad_h: b[1] } } }).catch(() => { }); };
  const done = () => {
    if (!rs) return; rs = null; g.classList.remove("on");
    const a = api(); if (!a || !last) { last = null; return; }
    a.pad_resize(last[0], last[1], true).then(save).catch(() => { }); last = null;
  };
  g.addEventListener("pointerup", done); g.addEventListener("pointercancel", done);
  g.addEventListener("dblclick", (ev) => { ev.stopPropagation(); const a = api(); if (a && a.pad_resize) a.pad_resize(0, 0, true).then(save).catch(() => { }); });
})();

/* ---------- потянуть блокнот за пустое место наверху (вкладки, панель) — едет весь Dewiar ----------
   22.10, владелец: «можно всё перетягивать за виджет, но не за окошко блокнота, а интуитивно хочется». Двигаем карточку
   виджета (Api.move_to / на Windows drag_step — окно за курсором), блокнот едет за ней сам (_pad_follow_at). */
(() => {
  let mv = null, raf = 0;
  const free = (t) => !t.closest("button, input, select, a, .tab, [role=tab], #sz, #tl, #ed, #grip");
  for (const el of [$("#top"), $("#tools")]) {
    el.addEventListener("pointerdown", async (ev) => {
      if (ev.button !== 0 || !free(ev.target)) return;
      const a = api(); if (!a || !a.move_to || !a.get_pos) return;
      ev.preventDefault(); el.setPointerCapture(ev.pointerId);
      mv = { el, sx: ev.screenX, sy: ev.screenY, moved: false, pos: null, win: false };
      mv.pos = await a.get_pos("card").catch(() => null);
      if (a.drag_begin && /^Win/.test(navigator.platform)) mv.win = await a.drag_begin("card").catch(() => false);
    });
    el.addEventListener("pointermove", (ev) => {
      if (!mv || mv.el !== el) return;
      const dx = ev.screenX - mv.sx, dy = ev.screenY - mv.sy;
      if (!mv.moved && Math.hypot(dx, dy) > 4) { mv.moved = true; document.body.classList.add("moving"); }
      if (mv.moved && mv.pos && !raf) raf = requestAnimationFrame(() => { raf = 0; const a = api(); if (!a || !mv) return;
        if (mv.win) a.drag_step("card"); else a.move_to("card", mv.pos[0] + dx, mv.pos[1] + dy); });
    });
    const end = () => {
      if (!mv || mv.el !== el) return;
      const d = mv; mv = null; document.body.classList.remove("moving");
      const a = api();
      if (d.moved && a && a.save_pos) a.save_pos("card").then(p => core.call("settings_save", { patch: { ui: { hud_x: p[0], hud_y: p[1] } } })).catch(() => { });
    };
    el.addEventListener("pointerup", end); el.addEventListener("pointercancel", end);
  }
})();

try { document.execCommand("defaultParagraphSeparator", false, "p"); } catch (e) { }   // новый абзац — <p>, а не <div>
/* первое открытие */
const wait = setInterval(() => { if (core.connected) { clearInterval(wait); padShown(Q.get("side")); } }, 120);

/* ---------- «Досуг»: игры в том же листе (24.10, владелец: «людям нравится, как смотрится блокнот, — можно в него игры») ----------
   padMode('play') — полка игр (assets/arcade/shelf.js), выбрали — игра во фрейме; padMode('notes') — снова блокнот.
   Игра во фрейме не уходит со страницы: «Игры» в ней шлют {arcade: 'home'} — показываем полку. Ушли из «Досуга» или
   убрали лист — фрейм пустеет (музыка и игра останавливаются; рекорды игры хранит сама). Кнопка 🎮 — только если
   «Досуг» включён в «Возможностях» (features.games), сам режим открывают кнопка у виджета и «Лира, давай поиграем». */
const ARC = "assets/arcade/";
let GAMES_ON = true;
function gamesOn(f) { GAMES_ON = !(f && f.games === false); $("#b-play").hidden = !GAMES_ON; if (!GAMES_ON && document.body.classList.contains("play")) padMode("notes"); }
function shelfDraw() {
  if (!window.DewiarArcade) return;
  $("#shelf").innerHTML = DewiarArcade.html(ARC) + '<p class="tip">Стрелки или WASD — движение, пробел — действие, P — пауза, M — музыка. Геймпад подключается сам.</p>';
  $$("#shelf .ag").forEach(b => { b.onclick = () => gameOpen(b.dataset.game); });
}
function gameOpen(id) {
  const f = $("#game"), light = document.body.classList.contains("light");
  f.src = DewiarArcade.url(ARC, id) + (light ? "?light=1" : "");
  $("#play").classList.add("in");
  f.onload = () => { try { f.focus(); f.contentWindow.focus(); const c = f.contentDocument && f.contentDocument.querySelector("canvas"); if (c) c.focus(); } catch (e) { } };
}
function gameStop() { const f = $("#game"); if (f.getAttribute("src") && f.getAttribute("src") !== "about:blank") f.src = "about:blank"; $("#play").classList.remove("in"); }
window.padMode = (m) => {
  const play = m === "play" && GAMES_ON;
  if (play === document.body.classList.contains("play")) { if (play && $("#play").classList.contains("in")) { gameStop(); shelfDraw(); } return; }
  document.body.classList.toggle("play", play);
  $("#b-play").classList.toggle("on", play);
  if (play) { saveNow(); gameStop(); shelfDraw(); setTimeout(() => { const b = $("#shelf .ag"); if (b) b.focus(); }, 300); }
  else { gameStop(); setTimeout(() => ED.focus(), 120); }
  const a = window.pywebview && window.pywebview.api; if (a && a.pad_mode_mark) a.pad_mode_mark(play ? "play" : "notes");
};
window.addEventListener("message", (e) => { if (e.data && e.data.arcade === "home" && e.source === $("#game").contentWindow) { gameStop(); shelfDraw(); } });
$("#b-play").onclick = () => padMode("play");
$("#b-notes").onclick = () => padMode("notes");
window.padGame = (id) => { padMode("play"); if (id && window.DewiarArcade && DewiarArcade.find(id) && GAMES_ON) gameOpen(id); };
if (Q.get("mode") === "play") padGame(Q.get("game") || "");
