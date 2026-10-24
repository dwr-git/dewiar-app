/* Студия Dewiar, раздел «Папка»: дерево папки ассистента и просмотр файла в его виде (страница, картинка, таблица,
   Markdown, звук, видео, текст документа), удаление в корзину, «Скачать» и PDF.
   Здесь же escH и md() — общие для всей студии: ими рисуют задачи, заметки, справку, обновления.
   Команды ядра: ws_tree, ws_read (текст до 300 000 знаков, PDF/Word — извлечённым текстом), ws_open, ws_export,
   ws_delete, ws_delete_dir. Картинки, страницы и медиа показываются прямо с диска по file:// (fileUrl).
   Файлы студии подключаются по порядку из ui/settings.html и делят одну глобальную область; при загрузке здесь
   ничего не вызывается — только объявления (OUT_ICON из tasks.js, openExt из links.js нужны при отрисовке). */
/* ---------- папка ассистента ---------- */
// escH — в core.js (24.10: нужен всем файлам студии; если этот файл не загрузится, остальные не должны падать)
/* Markdown -> HTML для текста, который пишет модель, пользователь или сайт. Безопасность: весь текст сначала проходит
   escH, разметка добавляется поверх; ссылки — только http(s), [[вики-ссылки]] — a.wl с href "wiki:…" (их ловит memory.js).
   Код в `…` прячется за метки \u0000n\u0000, чтобы *, _ и # внутри него не стали разметкой. */
function mdInline(t) {
  const codes = [];
  t = escH(t).replace(/`([^`]+)`/g, (_, c) => { codes.push(c); return `\u0000${codes.length - 1}\u0000`; });
  t = t.replace(/(^|\s)#([\p{L}\p{N}_-]{2,40})/gu, '$1<span class="tag">#$2</span>');
  t = t.replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>").replace(/(^|[^*])\*([^*\s][^*]*)\*/g, "$1<em>$2</em>")
       .replace(/(^|\W)_([^_]+)_(?=\W|$)/g, "$1<em>$2</em>").replace(/~~([^~]+)~~/g, "<s>$1</s>")
       .replace(/\[\[([^\]|]+)(?:\|([^\]]+))?\]\]/g, (_, a, b) => `<a class="wl" href="wiki:${encodeURIComponent(a.trim())}">${b || a}</a>`)
       .replace(/\[([^\]]+)\]\((https?:[^)\s]+)\)/g, '<a href="$2" target="_blank">$1</a>');
  return t.replace(/\u0000(\d+)\u0000/g, (_, i) => `<code>${codes[+i]}</code>`);
}
/* Блоки: ``` код, заголовки (не глубже h4), черта, таблицы | |, цитаты, списки и чек-листы [ ]/[x], абзацы */
function md(src) {
  const L = src.replace(/\r/g, "").split("\n"), out = [];
  let i = 0;
  while (i < L.length) {
    const l = L[i];
    if (/^```/.test(l)) { const buf = []; i++; while (i < L.length && !/^```/.test(L[i])) buf.push(L[i++]); i++;
      out.push(`<pre><code>${escH(buf.join("\n"))}</code></pre>`); continue; }
    let m;
    if ((m = l.match(/^(#{1,6})\s+(.*)/))) { const n = Math.min(4, m[1].length); out.push(`<h${n}>${mdInline(m[2])}</h${n}>`); i++; continue; }
    if (/^\s*([-*_])\s*\1\s*\1[\s\1]*$/.test(l)) { out.push("<hr>"); i++; continue; }
    if (/^\|.*\|\s*$/.test(l) && i + 1 < L.length && /^\|[\s:|-]+\|\s*$/.test(L[i + 1])) {
      const row = (r) => r.trim().replace(/^\||\|$/g, "").split("|").map(c => c.trim());
      const head = row(l); i += 2; const rows = [];
      while (i < L.length && /^\|.*\|\s*$/.test(L[i])) rows.push(row(L[i++]));
      out.push(`<table><tr>${head.map(h => `<th>${mdInline(h)}</th>`).join("")}</tr>${rows.map(r => `<tr>${r.map(c => `<td>${mdInline(c)}</td>`).join("")}</tr>`).join("")}</table>`); continue; }
    if (/^>\s?/.test(l)) { const buf = []; while (i < L.length && /^>\s?/.test(L[i])) buf.push(L[i++].replace(/^>\s?/, ""));
      out.push(`<blockquote>${md(buf.join("\n"))}</blockquote>`); continue; }
    if (/^\s*([-*+]|\d+[.)])\s+/.test(l)) {
      const ordered = /^\s*\d/.test(l), items = [];
      while (i < L.length && /^\s*([-*+]|\d+[.)])\s+/.test(L[i])) {
        let t = L[i++].replace(/^\s*([-*+]|\d+[.)])\s+/, "");
        const task = t.match(/^\[([ xXхХ])\]\s+(.*)/);   // и русская «х»
        items.push(task ? `<li class="task"><input type="checkbox" disabled ${task[1] !== " " ? "checked" : ""}>${mdInline(task[2])}</li>` : `<li>${mdInline(t)}</li>`);
      }
      out.push(`<${ordered ? "ol" : "ul"}>${items.join("")}</${ordered ? "ol" : "ul"}>`); continue; }
    if (!l.trim()) { i++; continue; }
    const buf = [];
    while (i < L.length && L[i].trim() && !/^(#{1,6}\s|```|>|\s*([-*+]|\d+[.)])\s+|\|)/.test(L[i])) buf.push(L[i++]);
    if (!buf.length) buf.push(L[i++]);
    out.push(`<p>${buf.map(mdInline).join("<br>")}</p>`);
  }
  return out.join("");
}
const FICON = { "Заметки": "📝", "Лаборатория": "🧪", "Дневник": "📔", "Память": "🧠" };
function ficon(n) {
  if (n.type === "dir") return FICON[n.name] || "📁";
  const e = n.name.split(".").pop().toLowerCase();
  return { md: "📄", txt: "📄", py: "🐍", sh: "⚙️", log: "📜", json: "🧾", csv: "📊" }[e] || OUT_ICON[e] || "📎";
}
// «Папка»: каждый формат — своим видом (страница — страницей, картинка — картинкой, таблица — таблицей), код — по кнопке
const FK = { page: ["html", "htm"], svg: ["svg"], img: ["png", "jpg", "jpeg", "gif", "webp", "bmp", "ico", "avif"],
             audio: ["mp3", "wav", "ogg", "oga", "m4a", "flac", "opus", "aac"], video: ["mp4", "webm", "mov", "m4v", "ogv"],
             table: ["csv", "tsv"], json: ["json"], md: ["md", "markdown"], doc: ["pdf", "docx", "odt"] };
function fkind(name) { const e = name.split(".").pop().toLowerCase(); return Object.keys(FK).find(k => FK[k].includes(e)) || "text"; }
/* Путь в папке ассистента -> file://; берёт корень из #f-root, который заполняет loadFolder(). # и ? кодируем —
   иначе они читаются как якорь и строка запроса. */
function fileUrl(rel) {
  const p = ($("#f-root").textContent.replace(/[\\/]+$/, "") + "/" + rel).replace(/\\/g, "/");
  return "file://" + (p.startsWith("/") ? "" : "/") + encodeURI(p).replace(/#/g, "%23").replace(/\?/g, "%3F");
}
/* CSV по правилам RFC 4180 (кавычки, "" внутри, переводы строк в ячейке); читаем не больше 501 строки — показ ограничен 500 */
function parseCsv(text, sep) {
  const rows = []; let row = [], cell = "", q = false;
  for (let i = 0; i < text.length && rows.length < 501; i++) {
    const c = text[i];
    if (q) { if (c === '"' && text[i + 1] === '"') { cell += '"'; i++; } else if (c === '"') q = false; else cell += c; }
    else if (c === '"') q = true;
    else if (c === sep) { row.push(cell); cell = ""; }
    else if (c === "\n" || c === "\r") { if (c === "\r" && text[i + 1] === "\n") i++; row.push(cell); rows.push(row); row = []; cell = ""; }
    else cell += c;
  }
  if (cell || row.length) { row.push(cell); rows.push(row); }
  return rows.filter(r => r.some(x => x.trim()));
}
function csvTable(text, name) {
  const first = text.split("\n")[0] || "";
  // разделитель — тот, что режет первую строку на больше частей (в русском Excel это «;»)
  const sep = /\.tsv$/i.test(name) ? "\t" : [";", ",", "\t"].sort((a, b) => first.split(b).length - first.split(a).length)[0];
  const rows = parseCsv(text, sep); if (!rows.length) return '<div class="fempty">Таблица пустая.</div>';
  const [h, ...body] = rows;
  return `<div class="ftable"><table><thead><tr>${h.map(x => `<th>${escH(x)}</th>`).join("")}</tr></thead><tbody>${body.slice(0, 500).map(r => `<tr>${r.map(x => `<td>${escH(x)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>${rows.length > 500 ? '<p class="hint">Показаны первые 500 строк.</p>' : ""}`;
}
function prettyJson(text) { try { return JSON.stringify(JSON.parse(text), null, 2); } catch (e) { return text; } }
let fOpen = new Set(["Заметки", "Дневник", "Память", "Лаборатория"]), fCur = "", fSync = [];
function fcount(n) { return n.type === "dir" ? n.children.reduce((a, c) => a + fcount(c), 0) : 1; }
function renderTree(items, box) {
  items.forEach(n => {
    const row = document.createElement("div");
    row.className = "node" + (n.path === fCur ? " cur" : "") + (fOpen.has(n.path) ? " open" : "");
    // как в ядре (workspace.remove_dir): главные папки не удаляются, папки задач — только из раздела «Задачи»
    const canDel = n.type === "dir" && n.path.includes("/") && !n.path.startsWith("Задачи/");
    row.innerHTML = `<span class="ch">${n.type === "dir" ? "▶" : ""}</span><span class="ic">${ficon(n)}</span><span class="n"></span>` +
      (fSync.includes(n.path) ? '<span class="sync" title="Общая с Obsidian: правки видны и там, и здесь">⇄</span>' : "") +
      (n.type === "dir" ? `<span class="cnt">${fcount(n) || ""}</span>` : "") + (canDel ? '<button class="del" title="Удалить папку (в корзину)">✕</button>' : "");
    $(".n", row).textContent = n.name.replace(/\.md$/, ""); row.title = n.path;
    if (canDel) $(".del", row).onclick = async (ev) => {
      ev.stopPropagation();
      if (!await ask(`Удалить папку «${n.name}» (${fcount(n)} файлов) в корзину?`)) return;
      try { await core.call("ws_delete_dir", { path: n.path }); toast("Папка — в корзине"); loadFolder(); } catch (e) { toast(e.message, 5000); }
    };
    box.appendChild(row);
    if (n.type === "dir") {
      const kids = document.createElement("div"); kids.className = "kids" + (fOpen.has(n.path) ? "" : " hide");
      renderTree(n.children, kids); box.appendChild(kids);
      row.onclick = () => { fOpen.has(n.path) ? fOpen.delete(n.path) : fOpen.add(n.path); row.classList.toggle("open"); kids.classList.toggle("hide"); };
    } else row.onclick = () => openFile(n.path);
  });
}
let fTree = null, fReq = 0;   // fTree — идущая загрузка дерева (её ждёт openFile), fReq — номер последнего чтения файла
async function loadFolder() {
  try {
    fTree = core.call("ws_tree");
    const t = await fTree;
    $("#f-root").textContent = t.root;
    const ob = t.obsidian || {};
    fSync = ob.connected ? ob.folders || [] : [];
    $("#f-sync").innerHTML = ob.connected ? `<span class="big">⇄</span><div class="t"><b>Заметки, Дневник и Память — общие с Obsidian</b><br>
      <span>Хранилище «${escH(ob.name)}» → папка <b>${escH(ob.folder)}</b>. Правите там — видно здесь, и наоборот. Заметку, положенную прямо в ${escH(ob.folder)}, ассистент найдёт в «Заметках».</span></div>
      ${ob.open ? `<button class="btn small" id="f-obs">Открыть в Obsidian</button>` : ""}` : "";
    if ($("#f-obs")) $("#f-obs").onclick = () => openExt(ob.open);
    const box = $("#f-tree"); box.innerHTML = "";
    renderTree(t.items, box);
    if (!fCur) { const readme = t.items.find(n => n.name === "README.md"); if (readme) openFile(readme.path); }
  } catch (e) { toast(e.message); }
}
async function openFile(path) {
  const req = ++fReq;
  fCur = path; $$("#f-tree .node").forEach(n => n.classList.toggle("cur", n.title === path));
  try {
    const f = await core.call("ws_read", { path });
    // из «Календаря» и «Памяти» файл открывают сразу после переключения на «Папку»: дерево ещё грузится, а без
    // корня (#f-root) ссылки file:// для страницы, картинки и звука получаются неверными — дожидаемся
    if (fTree) await fTree.catch(() => {});
    // пока читали, выбрали другой файл или этот же ещё раз — рисует только последний запрос (по номеру, не по пути:
    // при быстром А → Б → А старый ответ А иначе перекрыл бы новый)
    if (req !== fReq || fCur !== path) return;
    const name = path.split("/").pop(), kind = fkind(name), url = fileUrl(path);
    const when = new Date(f.mtime * 1000).toLocaleString("ru-RU", { day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" });
    const size = f.size > 1048576 ? (f.size / 1048576).toFixed(1) + " МБ" : f.size > 1024 ? Math.round(f.size / 1024) + " КБ" : (f.size || 0) + " Б";
    const code = () => `<pre class="code">${escH(kind === "json" ? prettyJson(f.text || "") : f.text || "")}</pre>`;
    const views = {                                            // вид → разметка; «Код» — исходный текст
      page: () => `<iframe class="fpage" src="${url}" sandbox="allow-scripts allow-same-origin allow-popups allow-forms"></iframe>`,
      svg: () => `<div class="fpic"><img src="${url}" alt=""></div>`,
      img: () => `<div class="fpic"><img src="${url}" alt=""></div>`,
      audio: () => `<div class="fplay"><div class="big">🎵</div><audio controls preload="metadata" src="${url}"></audio></div>`,
      video: () => `<div class="fplay"><video controls preload="metadata" src="${url}"></video></div>`,
      table: () => csvTable(f.text || "", name),
      md: () => `<div class="md">${md(f.text || "")}</div>`,
      doc: () => f.binary ? `<div class="fempty">Документ откройте в приложении.</div>`
        : `<p class="hint fnote">Текст документа — оформление и картинки видны в приложении.</p><div class="ftext">${escH(f.text || "")}</div>`,
      json: code, text: code,
    };
    const media = ["img", "audio", "video"].includes(kind), canCode = !f.binary && ["page", "svg", "table", "md"].includes(kind);
    const body = f.binary && !media ? `<div class="fempty">Этот файл открывается в своей программе — нажмите «Открыть».</div>` : views[kind]();
    const page = kind === "page", printable = page || /\.(md|txt)$/i.test(name);
    // «Удалить» нет у файлов, которые ядро ведёт само (README, «Обо мне», «Напоминания»), и у результатов задач
    $("#f-view").innerHTML = `<div class="fhead"><div class="t"><b></b><span>${escH(path)} · ${when} · ${size}${f.truncated ? " · показано начало" : ""}</span></div>
      <div class="fbtns">${canCode ? `<div class="seg" id="f-mode"><button class="on" data-m="view">${page ? "Страница" : "Вид"}</button><button data-m="code">Код</button></div>` : ""}
      ${["page", "img", "svg", "video"].includes(kind) ? '<button class="btn small" id="f-full" title="На весь экран">⛶</button>' : ""}
      <button class="btn small" id="f-app">Открыть</button>${["README.md", "Память/Обо мне.md", "Напоминания.md"].includes(path) || path.startsWith("Задачи/") ? "" : '<button class="btn small" id="f-del" title="В корзину">Удалить</button>'}<button class="btn small primary" id="f-dl">${page ? "Скачать HTML" : "Скачать"}</button>
      ${printable ? '<button class="btn small primary" id="f-pdf">PDF</button>' : ""}</div></div><div id="f-body">${body}</div>`;
    $("#f-view .fhead b").textContent = name;
    $("#f-app").onclick = () => core.call("ws_open", { path }).catch(e => toast(e.message));
    $$("#f-mode button").forEach(b => b.onclick = () => {
      $$("#f-mode button").forEach(x => x.classList.toggle("on", x === b));
      $("#f-body").innerHTML = b.dataset.m === "code" ? code() : views[kind]();
    });
    if ($("#f-full")) $("#f-full").onclick = () => { const el = $("#f-body").firstElementChild; if (el) (el.requestFullscreen || el.webkitRequestFullscreen || (() => {})).call(el); };
    const dl = async (fmt, b) => {
      const was = b.textContent; b.disabled = true; b.textContent = fmt === "pdf" ? "Делаю PDF…" : "Сохраняю…";
      try { const r = await core.call("ws_export", { path, fmt }); toast(`Сохранено в «${r.dir.split(/[\\/]/).pop()}»: ${r.name}`, 5000); }
      catch (e) { toast(e.message, 7000); }
      finally { b.disabled = false; b.textContent = was; }
    };
    $("#f-dl").onclick = () => dl(page ? "html" : "file", $("#f-dl"));
    if ($("#f-del")) $("#f-del").onclick = async () => {
      if (!await ask(`Удалить «${name}» в корзину?` + (fSync.some(f => path.startsWith(f + "/")) ? " Из Obsidian он тоже уйдёт в корзину." : ""))) return;
      try { await core.call("ws_delete", { path }); toast("Файл — в корзине"); fCur = "";
        $("#f-view").innerHTML = '<div class="fempty">Удалено. Выберите файл слева.</div>'; loadFolder(); }
      catch (e) { toast(e.message, 5000); }
    };
    if ($("#f-pdf")) $("#f-pdf").onclick = () => dl("pdf", $("#f-pdf"));
  } catch (e) { if (req === fReq) toast(e.message); }
}
