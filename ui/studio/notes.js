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

/* Шапка заметки «---» / «--» со строками «ключ: значение» (Obsidian, перенос из Google Keep) — как core/workspace.py
   note_front: не показывается, при правке сохраняется как была; метки (tags) и цвет — чипами (28.10, пользователь:
   «source: Google Keep, id: … — это не то»). */
const NT_FRONT = /^\ufeff?(-{2,3})[ \t]*\n((?:[ \t]*(?:[\w\-а-яёА-ЯЁ]+[ \t]*:.*|-[ \t].*|)\n)*?)\1[ \t]*(?:\n|$)/;
const NT_COLORS = { RED: "#e8505b", ORANGE: "#f2994a", YELLOW: "#e2b93b", GREEN: "#3fb27f", TEAL: "#2bb3a8", BLUE: "#4f8cf0", CERULEAN: "#3a7bd5",
  DARK_BLUE: "#3557a8", PURPLE: "#9b6bf2", PINK: "#ee6fae", BROWN: "#a77b5a", GRAY: "#8a93a6", GREY: "#8a93a6" };
function ntFront(text) {
  const m = NT_FRONT.exec(String(text || "")); if (!m || !m[2].trim()) return { raw: "", meta: {}, rest: String(text || "") };
  const meta = {}; let key = "";
  m[2].split("\n").forEach(l => { const li = /^\s*-\s+(.*)/.exec(l); if (li && key) { (meta[key + "[]"] = meta[key + "[]"] || []).push(li[1].trim()); return; }
    const kv = /^\s*([\w\-а-яёА-ЯЁ]+)\s*:\s*(.*)/.exec(l); if (kv) { key = kv[1].toLowerCase(); meta[key] = kv[2].trim(); } });
  let tags = [];
  ["tags", "tag", "labels", "метки"].forEach(k => { tags = tags.concat(meta[k + "[]"] || String(meta[k] || "").replace(/^\[|\]$/g, "").split(/[,;]/)); });
  tags = [...new Set(tags.map(x => String(x).trim().replace(/^["'#]+|["']+$/g, "")).filter(Boolean))];
  const col = /^([A-Za-z_]+)$/.exec(String(meta.color || "").trim()) || /(?:^|\b)(?:colou?r|цвет)\s*:?\s*([A-Za-zА-Яа-яЁё_]+)/i.exec(Object.entries(meta).filter(([, v]) => typeof v === "string").map(([k, v]) => k + ": " + v).join(" "));
  const yes = (v) => /^(true|yes|1|да)$/i.test(String(v || "").trim());
  return { raw: m[0].replace(/\n?$/, "\n"), meta: { tags, color: col && !/^(DEFAULT|NONE|WHITE)$/i.test(col[1]) ? col[1].toUpperCase() : "", source: meta.source || "",
    pinned: yes(meta.pinned), archived: yes(meta.archived), locked: yes(meta.locked) }, rest: String(text).slice(m[0].length) };
}
const ntColor = (c) => NT_COLORS[String(c || "").toUpperCase()] || "";
const ntChips = (tags, source) => (source ? `<i class="nt-chip">${escH(source)}</i>` : "") + (tags || []).map(t => `<i class="nt-chip nt-tag">#${escH(t)}</i>`).join("");

/* текст заметки → {title, date, body, att: [{img, name, link, line}], fm}; обратно — ntCompose */
function ntParse(path, text) {
  const F = ntFront(String(text || "").replace(/\r\n/g, "\n"));
  const lines = F.rest.replace(/^\n+/, "").split("\n"), att = [], body = [];
  let i = 0, title = path.split("/").pop().replace(/\.md$/, ""), date = "";
  if (/^#\s+/.test(lines[0] || "")) { title = lines[0].replace(/^#\s+/, "").trim() || title; i = 1; }
  while (i < lines.length && !lines[i].trim()) i++;
  if (/^\*[^*\n]+\*$/.test((lines[i] || "").trim())) { date = lines[i].trim(); i++; }
  for (; i < lines.length; i++) { const m = NT_LINK.exec(lines[i]); if (m) att.push({ img: !!m[1], name: m[2], link: m[3], line: lines[i].trim() }); else body.push(lines[i]); }
  return { title, date, body: body.join("\n").trim(), att, fm: F.raw, meta: F.meta };
}
const ntCompose = (d) => `${d.fm ? d.fm + "\n" : ""}# ${d.title}\n\n${d.date ? d.date + "\n\n" : ""}${d.body.trim()}\n${d.att.length ? "\n" + d.att.map(a => a.line).join("\n") + "\n" : ""}`;

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

/* «Заметки как Keep, только умнее» (0.58; 28.10, пользователь: «теги слева, цвет, закреплять вверху, поиск — визуально
   легко ориентироваться»; владелец: «полностью поддерживаю»). Над списком — фильтр: «Все», «Закреплённые», метки по
   числу заметок, «Архив». Закреплённые — сверху; архив — только в «Архиве». Вид — списком (с заметкой справа) или
   плитками (как Keep, цвет — фоном; заметка открывается поверх). Метки, цвет, «закрепить», «в архив» — в шапку заметки
   (core/workspace.py note_meta), так что их видит и Obsidian. */
NT.f = ""; NT.sort = (() => { try { return ["az", "color"].includes(localStorage.getItem("nt_sort")) ? localStorage.getItem("nt_sort") : "new"; } catch (e) { return "new"; } })();
NT.grid = (() => { try { return localStorage.getItem("nt_grid") === "1"; } catch (e) { return false; } })(); NT.allTags = false;
function ntFilters(all) {
  const box = $("#nt-filt"); if (!box) return;
  const live = all.filter(n => !n.archived), cnt = {};
  live.forEach(n => (n.tags || []).forEach(t => { cnt[t] = (cnt[t] || 0) + 1; }));
  const tags = Object.keys(cnt).sort((x, y) => cnt[y] - cnt[x] || x.localeCompare(y, "ru"));
  const pins = live.filter(n => n.pinned).length, arch = all.length - live.length, shown = NT.allTags ? tags : tags.slice(0, 14);
  const chip = (f, label, n, cls = "") => `<button type="button" class="nt-fc ${cls}${NT.f === f ? " on" : ""}" data-f="${escH(f)}">${label}${n != null ? `<small>${n}</small>` : ""}</button>`;
  box.innerHTML = chip("", "Все", live.length) + (pins ? chip("@pin", "Закреплённые", pins, "pin") : "")
    + shown.map(t => chip("#" + t, "#" + escH(t), cnt[t], "tag")).join("")
    + (tags.length > 14 ? `<button type="button" class="nt-fc more" data-more>${NT.allTags ? "свернуть" : "ещё " + (tags.length - 14)}</button>` : "")
    + (arch ? chip("@arch", "Архив", arch, "arch") : "");
  box.hidden = !all.length;
  $$("#nt-filt [data-f]").forEach(b => b.onclick = () => { NT.f = NT.f === b.dataset.f ? "" : b.dataset.f; ntLoad(); });
  const m = $("#nt-filt [data-more]"); if (m) m.onclick = () => { NT.allTags = !NT.allTags; ntFilters(all); };
}
async function ntLoad() {
  const q = $("#nt-q").value.trim(); let all = [];
  try { all = await core.call("notes_list", { q }); } catch (e) { $("#nt-list").innerHTML = `<p class="hint">${escH(e.message)}</p>`; return; }
  if (!Array.isArray(all)) all = [];
  NT.all = all; ntFilters(all);
  const f = NT.f, l = all.filter(n => f === "@arch" ? n.archived : !n.archived && (!f || (f === "@pin" ? n.pinned : (n.tags || []).includes(f.slice(1)))));
  NT.list = l;
  const nw = (k) => `${k} ${typeof plural === "function" ? plural(k, "заметка", "заметки", "заметок") : "заметок"}`;
  $("#nt-count").textContent = q || f ? `Найдено: ${l.length}` : l.length ? nw(l.length) : "";
  $(".nt-cols").classList.toggle("grid", NT.grid);
  $$("#nt-sort [data-s]").forEach(b => { const on = b.dataset.s === NT.sort; b.classList.toggle("on", on); b.setAttribute("aria-pressed", on); });
  $$("#nt-vw [data-v]").forEach(b => { const on = (b.dataset.v === "grid") === NT.grid; b.classList.toggle("on", on); b.setAttribute("aria-pressed", on); });
  const tg = (n, k) => (n.tags || []).slice(0, k).map(t => `<i class="nt-chip nt-tag">#${escH(t)}</i>`).join("");
  const lk = (n) => n.locked ? '<i class="nt-lock" title="Защищено от удаления"></i>' : "";
  const col = (n) => ntColor(n.color) ? ` style="--nc:${ntColor(n.color)}"` : "";
  // 28.10, владелец: «важнейший раздел… дизайн лучше»: список по дням («Сегодня», «Вчера», «На этой неделе», «Раньше»)
  const row = (n) => `<button class="nt-row ${n.path === NT.cur ? "cur" : ""}" data-p="${escH(n.path)}"${col(n)}>
      <span class="nt-rt"><b>${n.pinned ? '<i class="nt-pin" title="Закреплено"></i>' : ""}${ntMark(n.title, q)}${lk(n)}</b><small>${ntDate(n.mtime)}${n.folder ? `<i class="nt-chip">${escH(n.folder)}</i>` : ""}${tg(n, 3)}${n.att ? `<i class="nt-chip">📎 ${n.att}</i>` : ""}</small>
      <em>${ntMark(ntPlain(n.snippet), q) || "без текста"}</em></span>${n.img ? `<i class="nt-th" data-img="${escH(n.img)}"></i>` : ""}</button>`;
  const tile = (n) => `<button class="nt-tile ${n.path === NT.cur ? "cur" : ""}" data-p="${escH(n.path)}"${col(n)}>
      ${n.img ? `<i class="nt-ti" data-img="${escH(n.img)}"></i>` : ""}<b>${n.pinned ? '<i class="nt-pin" title="Закреплено"></i>' : ""}${ntMark(n.title, q)}${lk(n)}</b>
      <em>${ntMark(ntPlain(n.snippet), q) || "без текста"}</em>${(n.tags || []).length ? `<small>${tg(n, 4)}</small>` : ""}</button>`;
  const day0 = new Date(); day0.setHours(0, 0, 0, 0); const t0 = day0.getTime() / 1000;
  /* Порядок (29.10, владелец: «сортировка заметок или раскидывание по разделам»): «Новые» — по дням, «А–Я» — по названию,
     «По цвету» — цвет становится разделом. Закреплённые — всегда сверху; разделы по смыслу — метки в фильтре над списком. */
  const ci = (n) => { const i = NT_CORDER.indexOf(ntCkey(n.color)); return i < 0 ? 99 : i; };
  if (NT.sort === "az") l.sort((a, b) => (b.pinned - a.pinned) || a.title.localeCompare(b.title, "ru", { numeric: true, sensitivity: "base" }));
  else if (NT.sort === "color") l.sort((a, b) => (b.pinned - a.pinned) || ci(a) - ci(b) || (b.mtime || 0) - (a.mtime || 0));
  else l.sort((a, b) => (b.pinned - a.pinned) || (b.mtime || 0) - (a.mtime || 0));
  const pinH = (n) => n.pinned && f !== "@pin" ? "Закреплённые" : "";
  const bucket = NT.sort === "az" ? (n) => pinH(n) || (l.some(x => x.pinned) && f !== "@pin" ? "Остальные" : "")
    : NT.sort === "color" ? (n) => pinH(n) || (ntCkey(n.color) ? NT_CNAME2[ntCkey(n.color)] : "Без цвета")
    : (n) => pinH(n) || (m => m >= t0 ? "Сегодня" : m >= t0 - 86400 ? "Вчера" : m >= t0 - 6 * 86400 ? "На этой неделе" : "Раньше")(n.mtime || 0);
  const gh = (b, n) => `<div class="nt-gh"${NT.sort === "color" && !n.pinned && ntColor(n.color) ? ` style="--gc:${ntColor(n.color)}" data-c="1"` : ""}>${b}</div>`;
  let html = "", last = "";
  l.forEach(n => { const b = q ? "" : bucket(n); if (b && b !== last) { html += gh(b, n); last = b; } html += NT.grid ? tile(n) : row(n); });
  if (NT.grid) {                                   // плитки — колонками по группам: «Закреплённые» отдельно от остальных
    html = html.split(/(?=<div class="nt-gh")/).map(g => g.replace(/^(<div class="nt-gh"[^>]*>[^<]*<\/div>)?([\s\S]*)$/, (m0, h, rest) => (h || "") + `<div class="nt-masonry">${rest}</div>`)).join("");
  }
  $("#nt-list").innerHTML = l.length ? html
    : `<div class="nt-none">${q || f ? "Ничего не нашлось — попробуйте другое слово или «Все»." : "Заметок пока нет. Скажите помощнице: «запиши в заметки…» — или нажмите «Новая заметка». Есть заметки в Google Keep — «Перенести из Keep»."}</div>`;
  $$("#nt-list .nt-row, #nt-list .nt-tile").forEach(b => b.onclick = () => ntOpen(b.dataset.p));
  $$("#nt-list .nt-th, #nt-list .nt-ti").forEach(ntThumb);
  if (NT.grid) { ntMasonry(); return; }
  if (!NT.cur && l.length) ntOpen(l[0].path);
  else if (!l.length && !NT.cur) $("#nt-view").innerHTML = "";
}
/* Плитки по колонкам: столько колонок, сколько влезает по 250 px; каждая плитка — в самую короткую колонку (по
   настоящей высоте), порядок чтения — слева направо, сверху вниз, как в Keep. Ширина окна изменилась — заново. */
function ntMasonry(force) {
  $$("#nt-list .nt-masonry").forEach(box => {
    const tiles = [...box.querySelectorAll(".nt-tile")].sort((a, b) => (+a.dataset.i || 0) - (+b.dataset.i || 0));
    tiles.forEach((t, i) => { if (t.dataset.i == null) t.dataset.i = i; });
    const w = box.clientWidth || Math.max(280, innerWidth - 640);          // раздел ещё скрыт — по ширине окна
    const n = Math.max(1, Math.floor((w + 14) / (250 + 14)));             // столько же колонок и в маленькой группе — плитки одной ширины
    if (!force && box.dataset.n === String(n) && box.querySelector(".nt-mcol")) return;
    box.dataset.n = n; box.innerHTML = "";
    const cols = Array.from({ length: n }, () => box.appendChild(Object.assign(document.createElement("div"), { className: "nt-mcol" })));
    tiles.forEach(t => cols.reduce((a, c) => (c.offsetHeight < a.offsetHeight ? c : a)).appendChild(t));
  });
}
let ntRz = 0;
window.addEventListener("resize", () => { clearTimeout(ntRz); ntRz = setTimeout(() => { if (NT.grid && $("#nt-list")) ntMasonry(); }, 120); });
/* Под названием — «закрепить», цвет, метки и «в архив» (как в Keep); всё — в шапку заметки (note_meta) */
const NT_CNAMES = { RED: "Красный", ORANGE: "Оранжевый", YELLOW: "Жёлтый", GREEN: "Зелёный", TEAL: "Бирюзовый", BLUE: "Синий", DARK_BLUE: "Тёмно-синий",
  PURPLE: "Фиолетовый", PINK: "Розовый", BROWN: "Коричневый", GRAY: "Серый" };
const NT_CORDER = ["RED", "ORANGE", "YELLOW", "GREEN", "TEAL", "BLUE", "CERULEAN", "DARK_BLUE", "PURPLE", "PINK", "BROWN", "GRAY"];
const NT_CNAME2 = Object.assign({ CERULEAN: "Голубой" }, NT_CNAMES);
const ntCkey = (c) => { c = String(c || "").toUpperCase(); c = c === "GREY" ? "GRAY" : c; return NT_COLORS[c] ? c : ""; };
function ntMetaHtml(d) {
  const m = d.meta || {}, own = new Set(m.tags || []);
  const inline = [...new Set([...(d.body || "").replace(/```[\s\S]*?```|https?:\/\/\S+/g, " ").matchAll(/(?:^|[^\w\/#&=-])#([A-Za-zА-Яа-яЁё][\wА-Яа-яЁё\-\/]{1,40})/g)].map(x => x[1]))].filter(t => !own.has(t));
  const known = [...new Set((NT.all || []).flatMap(n => n.tags || []))].sort((x, y) => x.localeCompare(y, "ru"));
  return `<div class="nt-meta">
    <button type="button" class="nt-mb${m.pinned ? " on" : ""}" id="nt-pinb" aria-pressed="${!!m.pinned}" title="${m.pinned ? "Открепить" : "Закрепить сверху"}"><i class="nt-pin"></i>${m.pinned ? "Закреплено" : "Закрепить"}</button>
    <span class="nt-colw"><button type="button" class="nt-mb" id="nt-colb" aria-haspopup="true" aria-expanded="false" title="Цвет заметки"><i class="nt-dot"${ntColor(m.color) ? ` style="background:${ntColor(m.color)}"` : ""}></i>Цвет</button>
      <span class="nt-pal" id="nt-pal" hidden><button type="button" data-c="" title="Без цвета" class="none${!m.color ? " on" : ""}"></button>${Object.keys(NT_CNAMES).map(c => `<button type="button" data-c="${c}" title="${NT_CNAMES[c]}" style="background:${NT_COLORS[c]}"${m.color === c ? ' class="on"' : ""}></button>`).join("")}</span></span>
    <span class="nt-tags">${[...own].map(t => `<span class="nt-chip nt-tag">#${escH(t)}<button type="button" data-rt="${escH(t)}" aria-label="Убрать метку ${escH(t)}">×</button></span>`).join("")}${inline.map(t => `<span class="nt-chip nt-tag" title="метка в тексте">#${escH(t)}</span>`).join("")}
      <button type="button" class="nt-mb nt-tbtn" id="nt-tbtn" title="Добавить метку — по ней заметка найдётся в фильтре над списком"><i class="nt-hash">#</i>Метка</button>
      <input id="nt-tadd" class="nt-tin" list="nt-tlist" placeholder="название метки" maxlength="40" aria-label="Добавить метку" hidden><datalist id="nt-tlist">${known.map(t => `<option value="${escH(t)}">`).join("")}</datalist></span>
    <span class="nt-msp"></span>
    <button type="button" class="nt-mb${m.locked ? " on" : ""}" id="nt-lockb" aria-pressed="${!!m.locked}" title="${m.locked ? "Снять защиту — заметку снова можно удалить" : "Защитить от случайного удаления — ни из студии, ни голосом, ни с телефона"}"><i class="nt-lock"></i>${m.locked ? "Защищено" : "Защитить"}</button>
    <button type="button" class="nt-mb" id="nt-archb" title="${m.archived ? "Вернуть из архива" : "Убрать в архив — с глаз долой, поиск находит"}">${m.archived ? "Из архива" : "В архив"}</button></div>`;
}
async function ntMetaSet(patch, msg) {
  if (NT.ren) await NT.ren;
  await ntFlush();                                   // сначала набранный текст: иначе он лёг бы поверх со старой шапкой
  try { await core.call("note_meta", { path: NT.cur, patch }); } catch (e) { toast(e.message); return; }
  if (msg) toast(msg, 2200);
  const keep = NT.cur, ed = NT.edit; await ntOpen(keep, ed); ntLoad();        // в правке — остаёмся в правке
}
function ntMetaBind(d) {
  const m = d.meta || {};
  $("#nt-pinb").onclick = () => ntMetaSet({ pinned: !m.pinned }, m.pinned ? "Откреплено" : "Закреплено — теперь сверху");
  $("#nt-lockb").onclick = () => ntMetaSet({ locked: !m.locked }, m.locked ? "Защита снята — заметку можно удалить" : "Защищено — случайно не удалится");
  $("#nt-archb").onclick = () => ntMetaSet({ archived: !m.archived, pinned: false }, m.archived ? "Вернула из архива" : "В архиве — найти можно в «Архиве» над списком");
  const pal = $("#nt-pal"), cb = $("#nt-colb");
  cb.onclick = (e) => { e.stopPropagation(); pal.hidden = !pal.hidden; cb.setAttribute("aria-expanded", !pal.hidden); };
  $$("#nt-pal [data-c]").forEach(b => b.onclick = () => { pal.hidden = true; ntMetaSet({ color: b.dataset.c }); });
  $$("#nt-view [data-rt]").forEach(b => b.onclick = () => ntMetaSet({ tags: (m.tags || []).filter(t => t !== b.dataset.rt) }));
  const ti = $("#nt-tadd");
  const add = () => { const t = ti.value.trim().replace(/^#+/, "").replace(/[,;\[\]]/g, " ").trim(); if (!t) return; if ((m.tags || []).includes(t)) { ti.value = ""; return; }
    ntMetaSet({ tags: (m.tags || []).concat([t]) }); };
  /* «Метка» — кнопкой, как «Закрепить» и «Цвет» (28.10, владелец: «„метка“ выглядит грубо»): нажали — на её месте
     поле-пилюля, Enter — добавить, Esc или ушли пустым — снова кнопка */
  const tb = $("#nt-tbtn"), tOff = () => { ti.value = ""; ti.hidden = true; tb.hidden = false; };
  tb.onclick = () => { tb.hidden = true; ti.hidden = false; ti.focus(); };
  ti.onblur = () => setTimeout(() => { if (document.activeElement !== ti && !ti.value.trim()) tOff(); }, 150);
  ti.onkeydown = (e) => { if (e.key === "Enter") { e.preventDefault(); add(); } else if (e.key === "Escape") { e.preventDefault(); tOff(); tb.focus(); } };
  ti.onchange = () => { if ([...$("#nt-tlist").options].some(o => o.value === ti.value)) add(); };
}
document.addEventListener("click", (e) => { const p = $("#nt-pal"); if (p && !p.hidden && !e.target.closest(".nt-colw")) p.hidden = true; });

/* Ссылка отдельной строкой — карточкой: картинка, название, сайт (ядро: link_meta, с кэшем). YouTube — с обложкой. */
function ntCards() {
  $$("#nt-view .nt-body p").forEach(pp => {
    const a = pp.querySelector("a[data-ext]");
    if (!a || pp.children.length !== 1 || pp.textContent.trim() !== a.textContent.trim()) return;
    const url = a.dataset.ext, host = (() => { try { return new URL(url).host.replace(/^www\./, ""); } catch (e) { return url; } })();
    const card = document.createElement("a"); card.href = "#"; card.className = "nt-card"; card.dataset.ext = url;
    card.innerHTML = `<i class="nt-cimg"></i><span><b>${escH(a.textContent.trim() === url ? host : a.textContent.trim())}</b><small>${escH(host)}</small></span>`;
    card.onclick = (e) => { e.preventDefault(); openExt(url); };
    pp.replaceWith(card);
    core.call("link_meta", { url }).then(r => {
      if (!r) return;
      if (r.title) { $("b", card).textContent = r.title; $("small", card).textContent = (r.site || host) + (r.desc && r.video ? " · " + r.desc : ""); }
      if (r.image) { const i = $(".nt-cimg", card); i.style.backgroundImage = `url("${r.image.replace(/"/g, "%22")}")`; i.classList.add("on"); card.classList.toggle("vid", !!r.video); }
    }).catch(() => { });
  });
}
function ntCloseTile() { $(".nt-cols").classList.remove("open"); NT.cur = ""; NT.doc = null; $("#nt-view").innerHTML = ""; $$("#nt-list .cur").forEach(x => x.classList.remove("cur")); }
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && NT.grid && $(".nt-cols.open") && !NT.edit && !document.querySelector("dialog[open]")) ntCloseTile(); });

async function ntImg(path) {
  if (!NT.imgs[path]) NT.imgs[path] = core.call("note_file", { path }).then(r => r.url).catch(() => "");
  return NT.imgs[path];
}
/* Картинка заметки (29.10, владелец: «если прикреплена картинка — красиво в плитке или списком»): в плитке — во всю
   ширину в своих пропорциях (от 4:5 до 2:1, как в Keep), в списке — крупной миниатюрой. Картинки подгрузились —
   колонки плиток раскладываются заново по настоящей высоте. */
let ntReflow = 0;
async function ntThumb(el) {
  const tile = el.classList.contains("nt-ti"), done = (cls) => { el.classList.add(cls);
    if (tile) { clearTimeout(ntReflow); ntReflow = setTimeout(() => { if (NT.grid) ntMasonry(true); }, 60); } };
  const u = await ntImg(el.dataset.img); if (!u) { done("none"); return; }
  el.style.backgroundImage = `url("${u}")`;
  if (!tile) return;
  const im = new Image();
  im.onload = () => { if (im.naturalWidth) el.style.aspectRatio = String(Math.min(2, Math.max(0.8, im.naturalWidth / im.naturalHeight))); done("on"); };
  im.onerror = () => done("none");
  im.src = u;
}

async function ntOpen(path, edit) {
  await ntFlush();
  let d; try { d = await core.call("ws_read", { path }); } catch (e) { toast(e.message); return; }
  NT.cur = path; NT.edit = !!edit; NT.doc = Object.assign(ntParse(path, d.text), { mtime: d.mtime });
  $$("#nt-list .nt-row, #nt-list .nt-tile").forEach(b => b.classList.toggle("cur", b.dataset.p === path));
  $(".nt-cols").classList.toggle("open", NT.grid);                       // плитками — заметка открывается поверх
  ntShow();
}
function ntShow() {
  const d = NT.doc, path = NT.cur, v = $("#nt-view"); if (!d) { v.innerHTML = ""; return; }
  const pics = d.att.filter(a => a.img), files = d.att.filter(a => !a.img);
  const attHtml = (edit) => `${pics.length ? `<div class="nt-pics">${pics.map(a => `<figure data-i="${d.att.indexOf(a)}"><i data-img="${escH(ntAbs(path, a.link))}"></i>${edit ? `<button class="nt-x" title="Убрать">×</button>` : ""}</figure>`).join("")}</div>` : ""}
    ${files.length ? `<div class="nt-files">${files.map(a => `<span class="nt-f" data-i="${d.att.indexOf(a)}"><svg viewBox="0 0 24 24"><path d="M6 3.5h8.5L19 8v12.5H6z"/><path d="M14 3.5V8h5"/></svg>${escH(a.name)}${edit ? `<button class="nt-x" title="Убрать">×</button>` : ""}</span>`).join("")}</div>` : ""}`;
  if (!NT.edit) {
    v.innerHTML = `<div class="nt-top"><div><h2 class="nt-h">${escH(d.title)}</h2><small>${ntDate(d.mtime)}${ntDir(path) !== "Заметки" ? `<i class="nt-chip">${escH(ntDir(path).replace(/^Заметки\//, ""))}</i>` : ""}${ntChips((d.meta || {}).tags, (d.meta || {}).source && (d.meta || {}).source !== ntDir(path).replace(/^Заметки\//, "") ? d.meta.source : "")}</small></div>
        <span class="nt-act"><button class="btn primary" id="nt-edit">Изменить</button><button class="btn" id="nt-open" title="Открыть файл заметки в своей программе">В программе</button><button class="btn danger${(d.meta || {}).locked ? " nt-locked" : ""}" id="nt-del"${(d.meta || {}).locked ? ' title="Заметка защищена — сначала снимите защиту"' : ""}>${(d.meta || {}).locked ? '<i class="nt-lock"></i>' : ""}Удалить</button>${NT.grid ? '<button class="nt-close" type="button" id="nt-close" aria-label="Закрыть">×</button>' : ""}</span></div>
      ${ntMetaHtml(d)}
      <div class="nt-body"${ntCs() ? ` data-cs="${escH(ntCs())}"` : ""}>${ntRender(d.body) || `<p class="hint">Пустая заметка — нажмите «Изменить».</p>`}</div>${attHtml(false)}`;
    if (window.DewiarRich) DewiarRich.diagrams($("#nt-view .nt-body")).catch(() => { });   // ```mermaid — схемой
    $("#nt-edit").onclick = () => { NT.edit = true; ntShow(); setTimeout(() => $("#nt-text") && $("#nt-text").focus(), 50); };
    ntMetaBind(d); ntCards();
    if ($("#nt-close")) $("#nt-close").onclick = ntCloseTile;
    $("#nt-open").onclick = () => core.call("ws_open", { path }).catch(e => toast(e.message));
    $("#nt-del").onclick = ntDelete;
    $$("#nt-view a[data-ext]").forEach(a => a.onclick = (e) => { e.preventDefault(); openExt(a.dataset.ext); });
  } else {
    /* цвет, метку, «закрепить» и замок — сразу, и у новой заметки (29.10, владелец: «сразу присвоить цвет или тип») */
    v.innerHTML = `<div class="nt-top"><input id="nt-title" class="nt-tedit" value="${escH(d.title)}" maxlength="80" placeholder="Название" aria-label="Название заметки">
        <span class="nt-act"><span class="res" id="nt-res"></span><button class="btn primary" id="nt-done">Готово</button></span></div>
      ${ntMetaHtml(d)}
      <textarea id="nt-text" spellcheck="true" placeholder="Текст заметки. Списки — с «- », дела — «- [ ] »">${escH(d.body)}</textarea>
      ${attHtml(true)}
      <label class="nt-drop" id="nt-drop"><input type="file" id="nt-file" multiple hidden>
        <svg viewBox="0 0 24 24"><path d="m20.5 11.5-8.6 8.6a5.5 5.5 0 0 1-7.8-7.8l8.6-8.6a3.7 3.7 0 0 1 5.2 5.2l-8.6 8.6a1.8 1.8 0 0 1-2.6-2.6l8-8"/></svg>
        <span><b>Добавить фото или файл</b> — нажмите, перетащите сюда или вставьте снимок Ctrl+V</span></label>`;
    const t = $("#nt-text"), grow = () => { t.style.height = "auto"; t.style.height = Math.max(260, t.scrollHeight + 4) + "px"; };
    grow(); t.oninput = () => { grow(); d.body = t.value; ntDirty(); };
    $("#nt-title").onchange = ntRename;
    $("#nt-title").onkeydown = (e) => { if (e.key === "Enter") { e.preventDefault(); t.focus(); } };      // Enter — к тексту
    ntMetaBind(d);
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
function ntRename() { NT.ren = ntRename0().finally(() => { NT.ren = null; }); return NT.ren; }   // «Цвет» сразу после названия — дождётся
async function ntRename0() {
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
  const d = NT.doc;
  if (d && (d.meta || {}).locked) {                  // замок: не спрашиваем «удалить?» — подсказываем, где снять
    toast("Заметка защищена от удаления — снимите защиту кнопкой «Защищено»", 3600);
    const b = $("#nt-lockb"); if (b) { b.classList.remove("nt-nudge"); void b.offsetWidth; b.classList.add("nt-nudge"); b.focus(); }
    return;
  }
  if (!d || !await ask(`Удалить заметку «${d.title}»${d.att.length ? " вместе с вложениями" : ""}? Она уйдёт в корзину — оттуда её можно вернуть.`)) return;
  try { await core.call("ws_delete", { path: NT.cur }); NT.cur = ""; NT.doc = null; $("#nt-view").innerHTML = ""; ntLoad(); } catch (e) { toast(e.message); }
}
async function ntNew() {
  await ntFlush();
  try { const r = await core.call("ws_new_note", { title: "Новая заметка", folder: "Заметки", text: "" }); $("#nt-q").value = "";
    if (NT.f.startsWith("#")) await core.call("note_meta", { path: r.path, patch: { tags: [NT.f.slice(1)] } }).catch(() => { });   // открыта метка — новая заметка сразу с ней
    await ntOpen(r.path, true); ntLoad();
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
$$("#nt-sort [data-s]").forEach(b => b.onclick = () => { NT.sort = b.dataset.s; try { localStorage.setItem("nt_sort", NT.sort); } catch (e) { } ntLoad(); });
$$("#nt-vw [data-v]").forEach(b => b.onclick = () => { NT.grid = b.dataset.v === "grid"; try { localStorage.setItem("nt_grid", NT.grid ? "1" : "0"); } catch (e) { }
  if (!NT.grid) $(".nt-cols").classList.remove("open"); else ntCloseTile(); ntLoad(); });
/* Перенос из Google Keep: архив Google Takeout (zip) или распакованная папка — core/keep_import.py */
$("#nt-keep").onclick = async () => {
  const a = window.pywebview && window.pywebview.api; let path = "";
  if (a && a.pick_file) path = await a.pick_file("Архив Google Takeout (*.zip)");
  if (!path && !(a && a.pick_file)) path = await askText("Путь к архиву Google Takeout (.zip) или к распакованной папке:") || "";
  if (!path) return;
  toast("Переношу заметки из Keep…", 4000);
  try { const r = await core.call("notes_import_keep", { path }); NT.f = ""; await ntLoad();
    toast(r.added ? `Перенесено заметок: ${r.added}${r.skipped ? `, уже были: ${r.skipped}` : ""} — с метками, цветом и закреплёнными` : r.skipped ? `Все заметки уже перенесены (${r.skipped})` : "Заметок в архиве не нашлось", 6000); }
  catch (e) { toast(e.message, 6000); }
};
core.on("keep_import", (e) => toast(`Переношу из Keep: ${e.i} из ${e.n}…`, 2500));
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
