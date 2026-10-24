/* Студия → «Заметки» (отзыв 11.10: «заметки — мозг системы, должны быть под рукой»): все заметки папки ассистента
   (и с телефона), новые сверху; поиск на лету по названию, тексту и папке с подсветкой; заметка открывается для чтения
   (текст, фото, файлы), «Изменить» — правка на месте с автосохранением, фото и файлы: кнопкой, перетаскиванием или
   Ctrl+V. Вложения лежат рядом с заметкой («Вложения/<заметка>/…», core/workspace.py note_attach), в тексте — строка-
   ссылка в конце. Ядро: notes_list, ws_read, ws_write, ws_rename, ws_new_note, ws_delete, note_attach, note_file. */
const NT = { cur: "", list: [], edit: false, doc: null, t: 0, saveT: 0, imgs: {} };
const NT_LINK = /^\s*(?:📎\s*)?(!?)\[([^\]\n]*)\]\((Вложения\/[^)\s]+)\)\s*$/;
const ntDate = (s) => { const d = new Date(s * 1000), now = new Date();
  return d.toDateString() === now.toDateString() ? "сегодня, " + d.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })
    : d.toLocaleDateString("ru-RU", { day: "numeric", month: "short", year: d.getFullYear() === now.getFullYear() ? undefined : "numeric" }); };
function ntMark(t, q) {                                    // подсветить найденные слова (текст экранируется здесь)
  let h = escH(t); for (const w of String(q || "").toLowerCase().split(/\s+/).filter(x => x.length > 1))
    h = h.replace(new RegExp("(" + w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&").replace(/[её]/g, "[её]") + ")", "gi"), "<mark>$1</mark>");
  return h; }
const ntDir = (path) => path.split("/").slice(0, -1).join("/");
const ntAbs = (path, link) => ntDir(path) + "/" + decodeURIComponent(link);   // ссылка вложения → путь в папке ассистента

/* текст заметки → {title, date, body, att: [{img, name, link, line}]}; обратно — ntCompose */
function ntParse(path, text) {
  const lines = String(text || "").replace(/\r\n/g, "\n").split("\n"), att = [], body = [];
  let i = 0, title = path.split("/").pop().replace(/\.md$/, ""), date = "";
  if (/^#\s+/.test(lines[0] || "")) { title = lines[0].replace(/^#\s+/, "").trim() || title; i = 1; }
  while (i < lines.length && !lines[i].trim()) i++;
  if (/^\*[^*\n]+\*$/.test((lines[i] || "").trim())) { date = lines[i].trim(); i++; }
  for (; i < lines.length; i++) { const m = NT_LINK.exec(lines[i]); if (m) att.push({ img: !!m[1], name: m[2], link: m[3], line: lines[i].trim() }); else body.push(lines[i]); }
  return { title, date, body: body.join("\n").trim(), att };
}
const ntCompose = (d) => `# ${d.title}\n\n${d.date ? d.date + "\n\n" : ""}${d.body.trim()}\n${d.att.length ? "\n" + d.att.map(a => a.line).join("\n") + "\n" : ""}`;

/* Заметка — как в блокноте (25.10, владелец: «в заметках диаграммы сырые и нет цветовых схем»): полный Markdown
   (folder.js md: заголовки, цитаты, таблицы, код, задачи), схемы Mermaid картинкой (rich.js), ссылки — во внешнем браузере;
   цвета — та же схема, что выбрана в блокноте (ui.pad_colors, классы .nt-body[data-cs] в studio.css). */
function ntRender(text) {
  if (!String(text || "").trim()) return "";
  return md(String(text)).replace(/<a href="(https?:[^"]+)" target="_blank">/g, '<a href="#" data-ext="$1">')
    .replace(/(^|[\s>(«])(https?:\/\/[^\s<"]+[^\s<".,;:!?)»])/g, '$1<a href="#" data-ext="$2">$2</a>');   // голые ссылки — тоже ссылками
}
/* Строка-превью в списке — без значков Markdown: «**НА ПОНЕДЕЛЬНИК**» → «НА ПОНЕДЕЛЬНИК» */
function ntPlain(t) {
  return String(t || "").replace(/```\s*mermaid[\s\S]*?(```|$)/g, " ◇ схема ").replace(/```[\s\S]*?(```|$)/g, " ")
    .replace(/!\[[^\]]*\]\([^)]*\)/g, "").replace(/\[([^\]]+)\]\([^)]*\)/g, "$1").replace(/(^|\s)#{1,6}\s+/g, "$1")
    .replace(/(^|\s)>\s?/g, "$1").replace(/\[[ xXх]\]\s*/g, "").replace(/\*\*|__|`|==/g, "").replace(/(^|\s)[*_](\S[^*_]*?)[*_](?=\s|$|[.,!?:;])/g, "$1$2")
    .replace(/\s{2,}/g, " ").trim();
}
const ntCs = () => { try { return ((S && S.ui) || {}).pad_colors || ""; } catch (e) { return ""; } };

async function ntLoad() {
  const q = $("#nt-q").value.trim(); let l = [];
  try { l = await core.call("notes_list", { q }); } catch (e) { $("#nt-list").innerHTML = `<p class="hint">${escH(e.message)}</p>`; return; }
  NT.list = l;
  $("#nt-count").textContent = q ? `Найдено: ${l.length}` : l.length ? `Всего: ${l.length}` : "";
  $("#nt-list").innerHTML = l.length ? l.map(n => `<button class="nt-row ${n.path === NT.cur ? "cur" : ""}" data-p="${escH(n.path)}">
      <span class="nt-rt"><b>${ntMark(n.title, q)}</b><small>${ntDate(n.mtime)}${n.folder ? " · " + escH(n.folder) : ""}${n.att ? ` · 📎 ${n.att}` : ""}</small>
      <em>${ntMark(ntPlain(n.snippet), q) || "без текста"}</em></span>${n.img ? `<i class="nt-th" data-img="${escH(n.img)}"></i>` : ""}</button>`).join("")
    : `<div class="nt-none">${q ? "Ничего не нашлось — попробуйте другое слово." : "Заметок пока нет. Скажите помощнице: «запиши в заметки…» — или нажмите «Новая заметка»."}</div>`;
  $$("#nt-list .nt-row").forEach(b => b.onclick = () => ntOpen(b.dataset.p));
  $$("#nt-list .nt-th").forEach(ntThumb);
  if (!NT.cur && l.length) ntOpen(l[0].path);
  else if (!l.length && !NT.cur) $("#nt-view").innerHTML = "";
}
async function ntImg(path) {
  if (!NT.imgs[path]) NT.imgs[path] = core.call("note_file", { path }).then(r => r.url).catch(() => "");
  return NT.imgs[path];
}
async function ntThumb(el) { const u = await ntImg(el.dataset.img); if (u) el.style.backgroundImage = `url("${u}")`; }

async function ntOpen(path, edit) {
  await ntFlush();
  let d; try { d = await core.call("ws_read", { path }); } catch (e) { toast(e.message); return; }
  NT.cur = path; NT.edit = !!edit; NT.doc = Object.assign(ntParse(path, d.text), { mtime: d.mtime });
  $$("#nt-list .nt-row").forEach(b => b.classList.toggle("cur", b.dataset.p === path));
  ntShow();
}
function ntShow() {
  const d = NT.doc, path = NT.cur, v = $("#nt-view"); if (!d) { v.innerHTML = ""; return; }
  const pics = d.att.filter(a => a.img), files = d.att.filter(a => !a.img);
  const attHtml = (edit) => `${pics.length ? `<div class="nt-pics">${pics.map(a => `<figure data-i="${d.att.indexOf(a)}"><i data-img="${escH(ntAbs(path, a.link))}"></i>${edit ? `<button class="nt-x" title="Убрать">×</button>` : ""}</figure>`).join("")}</div>` : ""}
    ${files.length ? `<div class="nt-files">${files.map(a => `<span class="nt-f" data-i="${d.att.indexOf(a)}"><svg viewBox="0 0 24 24"><path d="M6 3.5h8.5L19 8v12.5H6z"/><path d="M14 3.5V8h5"/></svg>${escH(a.name)}${edit ? `<button class="nt-x" title="Убрать">×</button>` : ""}</span>`).join("")}</div>` : ""}`;
  if (!NT.edit) {
    v.innerHTML = `<div class="nt-top"><div><h2 class="nt-h">${escH(d.title)}</h2><small>${ntDate(d.mtime)}${ntDir(path) !== "Заметки" ? " · " + escH(ntDir(path).replace(/^Заметки\//, "")) : ""}</small></div>
        <span class="nt-act"><button class="btn primary" id="nt-edit">Изменить</button><button class="btn" id="nt-open" title="Открыть файл заметки в своей программе">В программе</button><button class="btn danger" id="nt-del">Удалить</button></span></div>
      <div class="nt-body"${ntCs() ? ` data-cs="${escH(ntCs())}"` : ""}>${ntRender(d.body) || `<p class="hint">Пустая заметка — нажмите «Изменить».</p>`}</div>${attHtml(false)}`;
    if (window.DewiarRich) DewiarRich.diagrams($("#nt-view .nt-body")).catch(() => { });   // ```mermaid — схемой
    $("#nt-edit").onclick = () => { NT.edit = true; ntShow(); setTimeout(() => $("#nt-text") && $("#nt-text").focus(), 50); };
    $("#nt-open").onclick = () => core.call("ws_open", { path }).catch(e => toast(e.message));
    $("#nt-del").onclick = ntDelete;
    $$("#nt-view a[data-ext]").forEach(a => a.onclick = (e) => { e.preventDefault(); openExt(a.dataset.ext); });
  } else {
    v.innerHTML = `<div class="nt-top"><input id="nt-title" class="nt-ti" value="${escH(d.title)}" maxlength="80" placeholder="Название">
        <span class="nt-act"><span class="res" id="nt-res"></span><button class="btn primary" id="nt-done">Готово</button></span></div>
      <textarea id="nt-text" spellcheck="true" placeholder="Текст заметки. Списки — с «- », дела — «- [ ] »">${escH(d.body)}</textarea>
      ${attHtml(true)}
      <label class="nt-drop" id="nt-drop"><input type="file" id="nt-file" multiple hidden>
        <svg viewBox="0 0 24 24"><path d="m20.5 11.5-8.6 8.6a5.5 5.5 0 0 1-7.8-7.8l8.6-8.6a3.7 3.7 0 0 1 5.2 5.2l-8.6 8.6a1.8 1.8 0 0 1-2.6-2.6l8-8"/></svg>
        <span><b>Добавить фото или файл</b> — нажмите, перетащите сюда или вставьте снимок Ctrl+V</span></label>`;
    const t = $("#nt-text"), grow = () => { t.style.height = "auto"; t.style.height = Math.max(260, t.scrollHeight + 4) + "px"; };
    grow(); t.oninput = () => { grow(); d.body = t.value; ntDirty(); };
    $("#nt-title").onchange = ntRename;
    $("#nt-done").onclick = async () => { await ntFlush(); NT.edit = false; ntShow(); ntLoad(); };
    $("#nt-file").onchange = () => { ntAdd([...$("#nt-file").files]); $("#nt-file").value = ""; };
    const drop = $("#nt-drop");
    drop.ondragover = (e) => { e.preventDefault(); drop.classList.add("over"); };
    drop.ondragleave = () => drop.classList.remove("over");
    drop.ondrop = (e) => { e.preventDefault(); drop.classList.remove("over"); ntAdd([...(e.dataTransfer.files || [])]); };
    $$("#nt-view .nt-x").forEach(b => b.onclick = (e) => { e.preventDefault(); e.stopPropagation(); const i = +b.parentElement.dataset.i; d.att.splice(i, 1); ntDirty(); ntShow(); });
  }
  $$("#nt-view .nt-pics i").forEach(async (el) => { const u = await ntImg(el.dataset.img); if (u) el.style.backgroundImage = `url("${u}")`; });
  $$("#nt-view .nt-pics figure, #nt-view .nt-f").forEach(el => el.addEventListener("click", (e) => {
    if (e.target.closest(".nt-x")) return; const a = d.att[+el.dataset.i]; if (a) core.call("ws_open", { path: ntAbs(path, a.link) }).catch(x => toast(x.message)); }));
}
function ntDirty() { const r = $("#nt-res"); if (r) { r.className = "res"; r.textContent = "…"; } clearTimeout(NT.saveT); NT.saveT = setTimeout(ntFlush, 700); }
async function ntFlush() {                                   // сохранить, если есть несохранённое (автосохранение)
  if (!NT.saveT || !NT.doc || !NT.cur) return; clearTimeout(NT.saveT); NT.saveT = 0;
  try { await core.call("ws_write", { path: NT.cur, text: ntCompose(NT.doc) });
    const r = $("#nt-res"); if (r) { r.className = "res ok"; r.textContent = "Сохранено"; } }
  catch (e) { const r = $("#nt-res"); if (r) { r.className = "res bad"; r.textContent = e.message; } }
}
async function ntRename() {
  const t = $("#nt-title").value.trim(); if (!t || t === NT.doc.title) return;
  await ntFlush();
  try { const r = await core.call("ws_rename", { path: NT.cur, title: t }); NT.cur = r.path; NT.doc.title = r.path.split("/").pop().replace(/\.md$/, "");
    NT.saveT = 1; await ntFlush(); ntLoad(); }
  catch (e) { toast(e.message); $("#nt-title").value = NT.doc.title; }
}
async function ntAdd(files) {
  for (const f of files) {
    if (f.size > 20 * 1048576) { toast(`«${f.name}» больше 20 МБ`); continue; }
    const b64 = await new Promise(res => { const fr = new FileReader(); fr.onload = () => res(String(fr.result).split(",")[1] || ""); fr.readAsDataURL(f); });
    try { const r = await core.call("note_attach", { path: NT.cur, name: f.name || "снимок.png", b64 });
      NT.doc.att.push({ img: r.kind === "image", name: r.name, link: (/\]\(([^)]+)\)/.exec(r.line) || [])[1], line: r.line }); }
    catch (e) { toast(e.message); }
  }
  NT.saveT = 1; await ntFlush(); ntShow();
}
async function ntDelete() {
  const d = NT.doc; if (!d || !await ask(`Удалить заметку «${d.title}»${d.att.length ? " вместе с вложениями" : ""}? Она уйдёт в корзину — оттуда её можно вернуть.`)) return;
  try { await core.call("ws_delete", { path: NT.cur }); NT.cur = ""; NT.doc = null; $("#nt-view").innerHTML = ""; ntLoad(); } catch (e) { toast(e.message); }
}
async function ntNew() {
  await ntFlush();
  try { const r = await core.call("ws_new_note", { title: "Новая заметка", folder: "Заметки", text: "" }); $("#nt-q").value = ""; await ntOpen(r.path, true); ntLoad();
    setTimeout(() => { const t = $("#nt-title"); if (t) { t.focus(); t.select(); } }, 80); } catch (e) { toast(e.message); }
}
function loadNotesPage() { ntLoad(); setTimeout(() => $("#nt-q").focus(), 60); }
/* открыть конкретную заметку (окно напоминания с картинками → ui/app.py open_note, или адрес ?note=…) */
async function ntGoto(path) {
  await ntFlush(); NT.cur = path; NT.doc = null; NT.edit = false;        // до перехода: список не откроет первую заметку вместо этой
  const b = $('nav button[data-p="notes"]'); if (b && !b.classList.contains("cur")) b.click();
  $("#nt-q").value = ""; await ntOpen(path); ntLoad();
}
window.ntGoto = ntGoto;
$("#nt-q").oninput = () => { clearTimeout(NT.t); NT.t = setTimeout(ntLoad, 180); };
$("#nt-add").onclick = ntNew;
document.addEventListener("paste", (e) => {                 // снимок из буфера — к открытой на правку заметке
  if (!NT.edit || !$("#p-notes").classList.contains("cur")) return;
  const fs = [...(e.clipboardData && e.clipboardData.files || [])].filter(f => /^image\//.test(f.type));
  if (fs.length) { e.preventDefault(); ntAdd(fs); }
});
/* голосом записали заметку, пока открыта эта страница, — список освежается сам и видно, что записано (пакет 22.10, №179:
   «непонятно, выполнена ли команда — страница не обновляется»). Правку на месте не перебиваем. */
let ntBump = 0;
function ntLive(e) {
  if (!$("#p-notes") || !$("#p-notes").classList.contains("cur") || NT.edit) return;
  if (e && e.title && e.kind !== "reminder") toast(`Заметка «${e.title}» сохранена`, 2600);
  clearTimeout(ntBump); ntBump = setTimeout(() => { NT.cur = (e && e.path) || NT.cur; ntLoad().then(() => { if (e && e.path) ntOpen(e.path); }).catch(() => { }); }, 300);
}
core.on("note_saved", ntLive);
core.on("notes_changed", () => ntLive(null));
