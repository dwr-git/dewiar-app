/* ИИ-правка в блокноте (24.10, владелец: «выделяю фрагмент, правой клавишей — и там „перевести“, „переформулировать“,
   „проверить орфографию“, „упростить“, „саммари“, „структурировать“, „mermaid-диаграмма“… это был бы новый уровень»).

   Правая кнопка в листе (или ✨ на панели) — меню: есть выделение — действия над ним (с учётом всей вкладки), нет —
   над всей вкладкой и «написать / продолжить» там, где курсор. Shift + правая кнопка — обычное меню.
   Ответ модели (core/padai.py, событие pad_ai) пишется в карточку снизу по мере написания; текст в листе меняет только
   человек — «Заменить» / «Вставить ниже» / «Вставить сверху», и после этого работает Ctrl+Z (вставка — insertHTML).
   Схемы Mermaid в листе рисуются картинкой (DewiarRich), в файле остаются блоком ```mermaid; двойной щелчок — правка. */
(() => {
  const ED = document.querySelector("#ed");
  const sheet = document.querySelector("#sheet");
  const AI = { open: false, range: null, act: "", scope: "", lang: "en", ask: "", id: "", text: "", done: false, mode: "" };

  const LANGS = [["en", "английский"], ["ru", "русский"], ["de", "немецкий"], ["fr", "французский"], ["es", "испанский"],
    ["it", "итальянский"], ["zh", "китайский"], ["uk", "украинский"]];
  const NAMES = { rephrase: "Переформулировать", simplify: "Упростить", shorter: "Короче", longer: "Подробнее", fix: "Исправить ошибки",
    retell: "Пересказать своими словами", translate: "Перевод", ask: "Своя просьба", structure: "Структура", beautify: "Оформление",
    summary: "Краткое содержание", diagram: "Схема", write: "Новый текст", continue: "Продолжение" };
  const I = {
    spark: '<path d="M12 3.5l1.6 4.4 4.4 1.6-4.4 1.6L12 15.5l-1.6-4.4L6 9.5l4.4-1.6zM18.5 15l.8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8z"/>',
    pen: '<path d="M4 20h4L19 9l-4-4L4 16zM13.5 6.5l4 4"/>', simp: '<path d="M4 7h16M7 12h10M10 17h4"/>',
    short: '<path d="M4 8h16M4 12h10M4 16h6"/>', long: '<path d="M4 6h16M4 10h16M4 14h16M4 18h11"/>',
    fix: '<path d="M4 12.5l4.5 4.5L20 5.5"/>', tr: '<path d="M3.5 5.5h9M8 3.5v2M5.5 5.5c.5 3 2.5 5.5 5.5 7M10.5 5.5c-.5 3-2.8 6-6.5 8M12.5 20.5l4-9 4 9M13.8 17.5h5.4"/>',
    retell: '<path d="M5 18.5V7a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2H8.5z"/><path d="M9 10h6M9 13h3.5"/>',
    ask: '<path d="M12 20.5a8.5 8.5 0 1 0-7.4-4.3L3.5 20.5l4.3-1.1A8.5 8.5 0 0 0 12 20.5z"/><path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .8-1 1.5M12 16.5h.01"/>',
    struct: '<path d="M4 5h9M4 10h6M7 15h13M7 19.5h9M4 15h.01M4 19.5h.01"/>', beauty: '<path d="M5 19l9-9M14 5l1 2 2 1-2 1-1 2-1-2-2-1 2-1zM18.5 11.5l.6 1.4 1.4.6-1.4.6-.6 1.4-.6-1.4-1.4-.6 1.4-.6z"/>',
    sum: '<rect x="4.5" y="3.5" width="15" height="17" rx="2.5"/><path d="M8 8.5h8M8 12h8M8 15.5h5"/>',
    dia: '<rect x="3.5" y="4" width="7" height="5" rx="1.5"/><rect x="13.5" y="15" width="7" height="5" rx="1.5"/><rect x="13.5" y="4" width="7" height="5" rx="1.5"/><path d="M10.5 6.5h3M17 9v6"/>',
    write: '<path d="M14.5 4.5l5 5L9 20H4v-5z"/><path d="M4 20l5-5"/>', cont: '<path d="M4 12h12M12 7l5 5-5 5M20 5v14"/>',
    copy: '<rect x="8" y="8" width="12" height="12" rx="2.5"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/>',
    cut: '<circle cx="6.5" cy="17.5" r="2.5"/><circle cx="17.5" cy="17.5" r="2.5"/><path d="M8.5 16 18 4.5M15.5 16 6 4.5"/>',
    more: '<path d="m9 6 6 6-6 6"/>',
  };
  const svg = (k) => `<svg viewBox="0 0 24 24" aria-hidden="true">${I[k] || ""}</svg>`;
  const esc = (s) => String(s || "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  /* ---------- разметка: меню и карточка ---------- */
  const menu = document.createElement("div");
  menu.id = "aim"; menu.setAttribute("role", "menu"); menu.hidden = true;
  const card = document.createElement("div");
  card.id = "aip"; card.hidden = true; card.setAttribute("role", "dialog"); card.setAttribute("aria-label", "ИИ-правка");
  card.innerHTML = `<div class="aih"><span class="ait"></span><span class="ais"></span><button class="aix" title="Закрыть (Esc)" aria-label="Закрыть"><svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6 6 18"/></svg></button></div>
    <div class="aib" tabindex="0"></div><div class="aia"></div>`;
  document.body.appendChild(menu); document.body.appendChild(card);
  menu.addEventListener("mousedown", (e) => { if (!e.target.closest("input")) e.preventDefault(); });
  card.addEventListener("mousedown", (e) => { if (e.target.closest("button")) e.preventDefault(); });

  /* ---------- выделение и текст ---------- */
  function selRange() {
    const s = getSelection();
    if (!s || !s.rangeCount) return null;
    const r = s.getRangeAt(0);
    return ED.contains(r.commonAncestorContainer) ? r.cloneRange() : null;
  }
  const rangeMd = (r) => { const d = document.createElement("div"); d.appendChild(r.cloneContents()); return PadMD.html2md(d).trim(); };
  const docMd = () => PadMD.html2md(ED).trim();
  const cyr = (t) => (String(t).match(/[а-яё]/gi) || []).length > (String(t).match(/[a-z]/gi) || []).length;

  /* ---------- меню ---------- */
  function item(act, icon, label, extra) {
    return `<button role="menuitem" data-act="${act}"${extra || ""}>${svg(icon)}<span>${esc(label)}</span>${act === "tr" || act === "trdoc" ? svg("more") : ""}</button>`;
  }
  function openMenu(x, y, fromButton) {
    const r = selRange();
    const hasSel = !!(r && !r.collapsed && r.toString().trim());
    AI.range = r;
    const first = r && cyr(rangeMd(r) || docMd()) ? "en" : "ru";
    const langs = [...LANGS].sort((a, b) => (b[0] === first) - (a[0] === first));
    let h;
    if (hasSel) {
      h = `<div class="aig">Выделенное</div>` + item("rephrase", "pen", "Переформулировать") + item("simplify", "simp", "Упростить")
        + `<div class="airow">${item("shorter", "short", "Короче")}${item("longer", "long", "Подробнее")}</div>`
        + item("fix", "fix", "Исправить ошибки") + item("tr", "tr", "Перевести") + item("retell", "retell", "Пересказать своими словами")
        + item("diagram", "dia", "Схема по выделенному") + item("ask", "ask", "Своя просьба…")
        + `<i class="aisep"></i>` + item("copy", "copy", "Копировать") + item("cut", "cut", "Вырезать");
    } else {
      h = `<div class="aig">Вся вкладка</div>` + item("structure", "struct", "Структурировать") + item("beautify", "beauty", "Красиво оформить")
        + item("summary", "sum", "Краткое содержание") + item("fixdoc", "fix", "Проверить орфографию") + item("diagram", "dia", "Схема (Mermaid)")
        + item("trdoc", "tr", "Перевести вкладку") + `<i class="aisep"></i><div class="aig">Где курсор</div>`
        + item("write", "write", "Написать текст на тему…") + item("continue", "cont", "Продолжить текст");
    }
    h += `<div class="aisub" hidden>${langs.map(([k, n]) => `<button role="menuitem" data-lang="${k}">${esc(n[0].toUpperCase() + n.slice(1))}</button>`).join("")}<button role="menuitem" data-lang="?">Другой язык…</button></div>`;
    h += `<small class="aifoot">${fromButton ? "Выделите текст — будут действия над ним" : "Shift + правая кнопка — обычное меню"}</small>`;
    menu.innerHTML = h;
    menu.hidden = false;
    const w = menu.offsetWidth, hh = menu.offsetHeight;
    menu.style.left = Math.max(8, Math.min(x, innerWidth - w - 8)) + "px";
    menu.style.top = Math.max(8, Math.min(y, innerHeight - hh - 8)) + "px";
    AI.open = true;
    const b = menu.querySelector("[data-act]"); if (b) b.focus({ preventScroll: true });
  }
  function closeMenu() { menu.hidden = true; AI.open = false; }

  menu.addEventListener("click", async (e) => {
    const b = e.target.closest("button"); if (!b) return;
    if (b.dataset.lang) {
      let lang = b.dataset.lang;
      if (lang === "?") { closeMenu(); lang = await askText("На какой язык перевести?", "", { ok: "Перевести" }); if (!lang) return; lang = lang.trim().toLowerCase(); }
      closeMenu(); run("translate", { lang, scope: AI.trScope });
      return;
    }
    const act = b.dataset.act;
    if (act === "tr" || act === "trdoc") {
      AI.trScope = act === "tr" ? "sel" : "doc";
      const sub = menu.querySelector(".aisub"); sub.hidden = false;
      const r = b.getBoundingClientRect(), w = sub.offsetWidth;
      sub.style.left = (r.right + w + 8 < innerWidth ? r.width - 4 : -w + 4) + "px";
      sub.style.top = (b.offsetTop) + "px";
      const f = sub.querySelector("button"); if (f) f.focus();
      return;
    }
    closeMenu();
    if (act === "copy" || act === "cut") { restore(); document.execCommand(act); return; }
    if (act === "ask") { const q = await askText("Что сделать с выделенным?", "", { ok: "Сделать", ph: "например: сделай официальнее, добавь пример" }); if (q && q.trim()) run("ask", { ask: q.trim() }); return; }
    if (act === "write") { const q = await askText("О чём написать?", "", { ok: "Написать", ph: "например: письмо коллегам о переносе встречи" }); if (q && q.trim()) run("write", { ask: q.trim(), scope: "cursor" }); return; }
    if (act === "continue") { run("continue", { scope: "cursor" }); return; }
    if (act === "fixdoc") { run("fix", { scope: "doc" }); return; }
    if (act === "diagram") { const r = AI.range; run("diagram", { scope: r && !r.collapsed && r.toString().trim() ? "sel" : "doc" }); return; }
    run(act, { scope: ["structure", "beautify", "summary"].includes(act) ? "doc" : "sel" });
  });
  menu.addEventListener("keydown", (e) => {
    const list = [...menu.querySelectorAll("button:not([hidden])")].filter(b => b.offsetParent);
    const i = list.indexOf(document.activeElement);
    if (e.key === "ArrowDown") { e.preventDefault(); (list[i + 1] || list[0]).focus(); }
    else if (e.key === "ArrowUp") { e.preventDefault(); (list[i - 1] || list[list.length - 1]).focus(); }
    else if (e.key === "Escape") { e.preventDefault(); closeMenu(); restore(); }
  });
  document.addEventListener("mousedown", (e) => { if (AI.open && !menu.contains(e.target)) closeMenu(); });
  addEventListener("blur", () => { if (AI.open) closeMenu(); });
  /* правая кнопка по выделенному иногда сбрасывает выделение (щелчок в его край, WebKitGTK) — помним последнее и, если
     щёлкнули внутри него, возвращаем */
  let lastSel = null;
  document.addEventListener("selectionchange", () => { const r = selRange(); if (r && !r.collapsed && r.toString().trim()) lastSel = r; });
  const inRange = (r, x, y) => [...r.getClientRects()].some(q => x >= q.left - 2 && x <= q.right + 2 && y >= q.top - 2 && y <= q.bottom + 2);
  ED.addEventListener("contextmenu", (e) => {
    if (e.shiftKey || e.target.closest("a[href]") || e.target.closest("img")) return;    // обычное меню, ссылки и картинки — как было
    e.preventDefault();
    const cur = selRange();
    if ((!cur || cur.collapsed) && lastSel && ED.contains(lastSel.commonAncestorContainer) && inRange(lastSel, e.clientX, e.clientY)) {
      const s = getSelection(); s.removeAllRanges(); s.addRange(lastSel);
    }
    openMenu(e.clientX, e.clientY, false);
  });
  const btn = document.querySelector("#b-ai");
  if (btn) {
    btn.onmousedown = (e) => e.preventDefault();
    btn.onclick = () => { const r = btn.getBoundingClientRect(); openMenu(r.left, r.bottom + 6, true); };
  }

  function restore() {
    if (!AI.range) return;
    ED.focus({ preventScroll: true });
    const s = getSelection(); s.removeAllRanges(); s.addRange(AI.range);
  }

  /* ---------- запрос и карточка ---------- */
  async function run(act, o) {
    o = o || {};
    const scope = o.scope || "sel";
    let r = AI.range && ED.contains(AI.range.commonAncestorContainer) ? AI.range : null;
    if (scope === "cursor" && !r) { r = document.createRange(); r.selectNodeContents(ED); r.collapse(false); }
    const text = scope === "sel" && r ? rangeMd(r) : scope === "doc" ? docMd() : "";
    Object.assign(AI, { act, scope, range: r, lang: o.lang || "en", ask: o.ask || "", text: "", done: false, err: "" });
    showCard();
    try {
      const x = await core.call("pad_ai", { act, scope, text, doc: docMd(), lang: AI.lang, ask: AI.ask });
      AI.id = x.id;
    } catch (e) { AI.err = e.message || String(e); AI.done = true; drawCard(); }
  }
  function again() { run(AI.act, { scope: AI.scope, lang: AI.lang, ask: AI.ask }); }

  core.on("pad_ai", (e) => {
    if (!e || e.id !== AI.id || card.hidden) return;
    AI.text = e.text || AI.text; AI.done = !!e.done; AI.err = e.error || "";
    drawCard();
  });

  function title() {
    if (AI.act === "translate") { const n = (LANGS.find(l => l[0] === AI.lang) || [0, AI.lang])[1]; return "Перевод — " + n; }
    if (AI.act === "fix" && AI.scope === "doc") return "Орфография — вся вкладка";
    return NAMES[AI.act] + (AI.scope === "doc" && !["structure", "beautify", "summary"].includes(AI.act) ? " — вся вкладка" : "");
  }
  function showCard() { card.hidden = false; card.classList.add("on"); drawCard(); }
  function closeCard() {
    if (AI.id && !AI.done) core.call("pad_ai_stop", { id: AI.id }).catch(() => { });
    card.hidden = true; card.classList.remove("on"); AI.id = "";
  }
  function primary() {
    if (AI.act === "summary") return ["top", "Вставить сверху"];
    if (AI.scope === "cursor") return ["here", "Вставить"];
    if (AI.act === "diagram") return [AI.scope === "doc" ? "here" : "below", "Вставить схему"];
    if (AI.scope === "doc") return ["all", "Заменить всю вкладку"];
    return ["replace", "Заменить"];
  }
  function drawCard() {
    card.querySelector(".ait").innerHTML = svg("spark") + esc(title());
    card.querySelector(".ais").textContent = AI.err ? "" : AI.done ? "" : AI.text ? "пишу…" : "думаю…";
    card.classList.toggle("busy", !AI.done);
    const body = card.querySelector(".aib");
    if (AI.err) body.innerHTML = `<p class="aie">Не получилось: ${esc(AI.err)}</p>`;
    else if (!AI.text) body.innerHTML = `<div class="aisk"><i></i><i></i><i></i></div>`;
    else {
      const stick = body.scrollTop + body.clientHeight >= body.scrollHeight - 30;
      body.innerHTML = PadMD.md2html(AI.text);
      if (AI.done && window.DewiarRich) DewiarRich.diagrams(body).catch(() => { });
      if (stick && !AI.done) body.scrollTop = body.scrollHeight;
    }
    const [pk, pl] = primary();
    const acts = card.querySelector(".aia");
    if (!AI.done) { acts.innerHTML = `<button class="aib2" data-a="stop">Остановить</button>`; }
    else if (AI.err || !AI.text) { acts.innerHTML = `<button class="aib2 p" data-a="again">Ещё раз</button><button class="aib2" data-a="close">Закрыть</button>`; }
    else {
      acts.innerHTML = `<button class="aib2 p" data-a="${pk}">${pl}</button>`
        + (pk === "replace" || pk === "all" ? `<button class="aib2" data-a="below">Вставить ниже</button>` : "")
        + `<button class="aib2" data-a="copy" title="Копировать как Markdown">Копировать</button><button class="aib2" data-a="again" title="Другой вариант">Ещё вариант</button>`;
    }
  }
  card.querySelector(".aix").onclick = () => closeCard();
  card.querySelector(".aia").addEventListener("click", async (e) => {
    const b = e.target.closest("button"); if (!b) return;
    const a = b.dataset.a;
    if (a === "stop") { core.call("pad_ai_stop", { id: AI.id }).catch(() => { }); AI.done = true; drawCard(); return; }
    if (a === "close") { closeCard(); restore(); return; }
    if (a === "again") { again(); return; }
    if (a === "copy") {
      try { await navigator.clipboard.writeText(AI.text); b.textContent = "Скопировано"; }
      catch (err) { const t = document.createElement("textarea"); t.value = AI.text; document.body.appendChild(t); t.select(); document.execCommand("copy"); t.remove(); b.textContent = "Скопировано"; }
      return;
    }
    apply(a);
  });

  /* ---------- вставка в лист (insertHTML — работает Ctrl+Z) ---------- */
  const topBlock = (n) => { if (n === ED) return null; while (n && n.parentNode !== ED) n = n.parentNode; return n; };
  function htmlOf(md, inline) {
    const h = PadMD.md2html(md);
    if (inline) { const m = h.match(/^<p>([\s\S]*)<\/p>$/); if (m && !/<\/?(p|h\d|ul|ol|pre|table|blockquote|hr)\b/.test(m[1])) return m[1]; }
    return h;
  }
  function placeAfter(node) {        // новая пустая строка после блока (или в конце) и курсор в неё — insertHTML не склеит с соседним
    const p = document.createElement("p"); p.innerHTML = "<br>";
    if (node) node.after(p); else ED.appendChild(p);
    const r = document.createRange(); r.setStart(p, 0); r.collapse(true);
    const s = getSelection(); s.removeAllRanges(); s.addRange(r);
  }
  function apply(how) {
    const md = AI.text;
    ED.focus({ preventScroll: true });
    const s = getSelection();
    if (how === "all") {
      const r = document.createRange(); r.selectNodeContents(ED); s.removeAllRanges(); s.addRange(r);
      document.execCommand("insertHTML", false, htmlOf(md));
    } else if (how === "top") {
      const r = document.createRange(); r.setStart(ED, 0); r.collapse(true); s.removeAllRanges(); s.addRange(r);
      document.execCommand("insertHTML", false, htmlOf(md) + "<hr>");
    } else if (how === "replace" && AI.range) {
      s.removeAllRanges(); s.addRange(AI.range);
      const a = topBlock(AI.range.startContainer), b = topBlock(AI.range.endContainer);
      const inline = a && a === b && !/^(UL|OL|TABLE|PRE)$/.test(a.tagName) && !(AI.range.startOffset === 0 && AI.range.toString().trim() === a.textContent.trim());
      document.execCommand("insertHTML", false, htmlOf(md, inline));
    } else if (how === "below") {        // под выделенным; для всей вкладки — в конец
      placeAfter(AI.scope === "doc" || !AI.range ? null : topBlock(AI.range.endContainer));
      document.execCommand("insertHTML", false, htmlOf(md));
    } else {          // here — там, где курсор
      if (AI.range) { s.removeAllRanges(); s.addRange(AI.range); }
      const cur = AI.range ? topBlock(AI.range.endContainer) : null;
      if (!AI.range || (cur && cur.textContent.trim())) placeAfter(cur);     // курсора нет — в конец; строка с текстом — под ней
      document.execCommand("insertHTML", false, htmlOf(md));
    }
    // курсор остался в только что вставленной схеме — вывести за неё, иначе она не нарисуется (правят — не трогаем)
    const sel = getSelection(), at = sel.rangeCount ? sel.getRangeAt(0).startContainer : null;
    const pre = at && (at.nodeType === 1 ? at : at.parentNode).closest && (at.nodeType === 1 ? at : at.parentNode).closest('pre[data-lang="mermaid"]');
    if (pre) {
      let nx = pre.nextElementSibling;
      if (!nx || nx.tagName !== "P") { nx = document.createElement("p"); nx.innerHTML = "<br>"; pre.after(nx); }
      const r = document.createRange(); r.setStart(nx, 0); r.collapse(true); sel.removeAllRanges(); sel.addRange(r);
    }
    closeCard();
    if (window.padAfterAi) padAfterAi();
  }

  addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !card.hidden && !AI.open) { e.preventDefault(); closeCard(); restore(); }
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey) && !card.hidden && AI.done && AI.text) { e.preventDefault(); apply(primary()[0]); }
  }, true);

  /* ---------- схемы Mermaid в листе ---------- */
  window.padDiagrams = () => {
    if (!window.DewiarRich) return;
    const s = getSelection(), at = s && s.rangeCount ? s.getRangeAt(0).startContainer : null;
    for (const pre of ED.querySelectorAll('pre[data-lang="mermaid"]')) {
      if (at && pre.contains(at)) { pre.dataset.mmd = "edit"; continue; }                  // правят — не трогать
      if (pre.dataset.mmd === "edit" || (pre.dataset.mmd === "bad" && pre.dataset.was !== pre.textContent)) delete pre.dataset.mmd;
      pre.dataset.was = pre.textContent;
    }
    DewiarRich.diagrams(ED).then(() => {
      ED.querySelectorAll(".dw-diagram").forEach(d => { d.contentEditable = "false"; d.title = "Схема — двойной щелчок, чтобы править"; });
    }).catch(() => { });
  };
  ED.addEventListener("dblclick", (e) => {
    const d = e.target.closest && e.target.closest(".dw-diagram"); if (!d) return;
    const pre = document.createElement("pre"); pre.dataset.lang = "mermaid";
    const code = document.createElement("code"); code.textContent = d.dataset.src || ""; pre.appendChild(code);
    d.replaceWith(pre);
    const r = document.createRange(); r.selectNodeContents(code); r.collapse(false); const s = getSelection(); s.removeAllRanges(); s.addRange(r);
  });
  let dT = 0;
  document.addEventListener("selectionchange", () => {
    if (!ED.querySelector('pre[data-lang="mermaid"]')) return;
    clearTimeout(dT); dT = setTimeout(() => window.padDiagrams(), 600);
  });
  window.PadAI = { openMenu, run, apply, state: () => AI };
})();
