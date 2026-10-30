/* Студия Dewiar, раздел «Память»: карта памяти (граф), список заметок и редактор, поиск по записям.
   Команды ядра: memory_graph (узлы и связи со статистикой), ws_tree/ws_read/ws_write/ws_rename/ws_new_note/ws_delete/ws_open
   (заметки в папке ассистента), recall (поиск по тексту). Пока раздел открыт, core.js обновляет граф раз в 30 с
   (mTimer, loadMemory(true)). Здесь же объявлены LS (хранилище настроек окна), plural и MN_TEXT — ими пользуются и другие файлы.
   Файлы студии подключаются по порядку из ui/settings.html и делят одну глобальную область: при загрузке здесь
   вызывается mPanes() (объявлена выше вызова); escH, md, openFile, openExt, obLast — из файлов ниже, нужны только по клику. */
/* ---------- «Память»: граф (vis-network из assets/vendor, грузится при первом открытии раздела) ---------- */
const MK = { me: ["Вы", "#FFFFFF"], fact: ["Факты о вас", "#F6C177"], note: ["Заметки", "#8B8CF7"], diary: ["Дневник", "#4BE3A1"],
             doc: ["Документы", "#62B6FF"], task: ["Задачи", "#FF8FB1"], skill: ["Навыки", "#C792EA"], entity: ["Люди, места, темы", "#FFD580"],
             tag: ["Теги", "#9AA0B5"], hub: ["Разделы", "#5A5E8A"] };
let mNet = null, mData = null, mNodes = null, mEdges = null, mOff = new Set(), mTimer = 0;
function loadVis() {
  if (window.vis) return Promise.resolve();
  return new Promise((ok, bad) => { const s = document.createElement("script"); s.src = "assets/vendor/vis-network.min.js"; s.onload = ok; s.onerror = () => bad(new Error("не загрузилась библиотека графа")); document.head.appendChild(s); });
}
const plural = (n, a, b, c) => { const m10 = n % 10, m100 = n % 100; return m10 === 1 && m100 !== 11 ? a : m10 >= 2 && m10 <= 4 && (m100 < 10 || m100 >= 20) ? b : c; };
function renderMemStats(s) {
  const cards = [["fact", s.facts, plural(s.facts, "факт о вас", "факта о вас", "фактов о вас")], ["note", s.notes, plural(s.notes, "заметка", "заметки", "заметок")],
    ["diary", s.diary, plural(s.diary, "день в дневнике", "дня в дневнике", "дней в дневнике")], ["doc", s.docs, plural(s.docs, "документ", "документа", "документов")],
    ["task", s.tasks, plural(s.tasks, "задача", "задачи", "задач")], ["entity", s.entities, "людей, мест, тем"], ["hub", s.links, plural(s.links, "связь", "связи", "связей")]];
  $("#m-stats").innerHTML = cards.map(([k, n, l]) => `<div class="mstat"><b>${n}</b><span><i style="background:${MK[k][1]}"></i>${l}</span></div>`).join("") +
    `<div class="mstat up"><b>+${s.week}</b><span>за неделю</span></div>`;
  const g = s.growth || [], svg = $("#m-growth");
  const days = []; for (let i = 59; i >= 0; i--) { const d = new Date(Date.now() - i * 864e5); days.push(d.toISOString().slice(0, 10)); }
  const by = Object.fromEntries(g.map(x => [x.day, x.n])), mx = Math.max(1, ...days.map(d => by[d] || 0)), w = 600 / 60;
  svg.innerHTML = days.map((d, i) => { const v = by[d] || 0, h = v ? Math.max(3, 42 * v / mx) : 1.5;
    return `<rect x="${i * w + 1}" y="${46 - h}" width="${w - 2}" height="${h}" rx="2" fill="${v ? "#8B8CF7" : "rgba(127,127,140,.16)"}"><title>${d}: ${v}</title></rect>`; }).join("");
  $("#m-growth-t").textContent = `память растёт · ${s.days} ${plural(s.days, "день", "дня", "дней")} вместе`;
}
function renderLegend() {
  const kinds = [...new Set(mData.nodes.map(n => n.kind))].filter(k => MK[k] && k !== "me");
  $("#m-legend").innerHTML = kinds.map(k => `<button data-k="${k}" class="${mOff.has(k) ? "off" : ""}"><i style="background:${MK[k][1]}"></i>${MK[k][0]}</button>`).join("");
  $$("#m-legend button").forEach(b => b.onclick = () => { const k = b.dataset.k; mOff.has(k) ? mOff.delete(k) : mOff.add(k); renderLegend(); applyFilter(); });
}
function applyFilter() {
  if (!mNodes) return;
  mNodes.update(mData.nodes.map(n => ({ id: n.id, hidden: mOff.has(n.kind) })));
}
/* Карта похожа на мозг: у каждого узла свой оттенок цвета его раздела, связи — дугами с переливом от цвета к цвету
   (изгиб свой у каждой), толщина — сила связи; по связям бегут огоньки — как сигналы между нейронами.
   Оттенок и изгиб берутся из хэша id (FNV-1a), а не из случайного числа: при обновлении графа картина не меняется. */
const KHUE = { fact: 38, note: 245, diary: 152, doc: 205, task: 335, skill: 280, entity: 45, tag: 225 };
function hashN(str) { let h = 2166136261; for (const ch of str) { h ^= ch.charCodeAt(0); h = Math.imul(h, 16777619); } return (h >>> 0) / 4294967295; }
/* Светлые темы студии (30.10, владелец: «Память — в центре не в том стиле, можно под наш стиль?»): карта не тёмным пятном,
   а из того же материала, что панели: светлое поле, узлы — те же оттенки, но глубже (чтобы читались на светлом), подписи —
   тёмные с белой обводкой, свечение — мягкая тень. Тёмные темы — как было: «мозг» в ночи. */
const mLight = () => document.documentElement.classList.contains("st-light");
function nodeColor(n) {
  const L = mLight();
  if (n.kind === "me") return L ? "#5B5FE0" : "#FFFFFF";
  if (n.kind === "hub") return L ? "#A3A8CC" : "#6B6FA8";
  const base = KHUE[n.kind] ?? 260, r = hashN(n.id);
  return L ? `hsl(${Math.round(base + (r - 0.5) * 60 + 360) % 360}, ${62 + Math.round(r * 18)}%, ${50 + Math.round(r * 8)}%)`
    : `hsl(${Math.round(base + (r - 0.5) * 70 + 360) % 360}, ${70 + Math.round(r * 20)}%, ${58 + Math.round(r * 10)}%)`;
}
function nodeStyle(n) {
  const c = nodeColor(n), big = n.kind === "me" ? 30 : n.kind === "hub" ? 8 : n.kind === "skill" ? 7 : 9 + Math.min(24, Math.sqrt(n.degree || 1) * 5);
  const lab = n.label.length > 26 ? n.label.slice(0, 25) + "…" : n.label;
  const L = mLight(), quiet = n.kind === "hub" || n.kind === "skill";
  return { id: n.id, label: lab, title: undefined, shape: "dot", size: big, hidden: mOff.has(n.kind), _c: c,
    color: { background: n.ghost ? "rgba(139,140,247,.15)" : c, border: n.ghost ? c : c, highlight: { background: L ? c : "#fff", border: L ? "#fff" : c }, hover: { background: c, border: "#fff" } },
    borderWidth: n.ghost ? 1.5 : L ? 2 : 0, shapeProperties: { borderDashes: n.ghost ? [3, 3] : false },
    font: L ? { color: quiet ? "rgba(70,76,108,.62)" : "#2A2F47", size: n.kind === "me" ? 18 : quiet ? 10.5 : 12.5,
                face: "Manrope, Inter, system-ui, sans-serif", strokeWidth: 4, strokeColor: "rgba(255,255,255,.9)", vadjust: 1 }
      : { color: n.kind === "hub" ? "rgba(201,202,232,.7)" : n.kind === "skill" ? "rgba(225,226,240,.7)" : "#F2F3FA", size: n.kind === "me" ? 18 : quiet ? 10.5 : 12.5,
          face: "Manrope, Inter, system-ui, sans-serif", strokeWidth: 3, strokeColor: "rgba(10,10,20,.9)", vadjust: 1 },
    shadow: L ? { enabled: true, color: "rgba(70,80,150,.22)", size: n.kind === "me" ? 22 : n.kind === "hub" ? 4 : 10, x: 2, y: 3 }
      : { enabled: true, color: c, size: n.kind === "me" ? 40 : n.kind === "hub" ? 6 : 22, x: 0, y: 0 } };
}
function edgeStyle(e, i) {
  // Все связи — дугами (как волокна), у каждой свой изгиб и сторона: по хэшу пары узлов, поэтому картина не «прыгает»
  // от обновления к обновлению. Цвет — перелив от одного узла к другому; связи с разделами — тоньше и прозрачнее.
  const hub = e.kind === "hub", w = e.kind === "similar" ? 2 + e.w * 9 : e.kind === "wikilink" ? 4.5 : e.kind === "mention" ? 3 :
    e.kind === "time" ? 2 : hub ? 1.4 : 2.4;
  const r = hashN(e.from + "→" + e.to);
  return { id: "e" + i, from: e.from, to: e.to, width: w, _k: e.kind,
           color: { inherit: "both", opacity: (hub ? 0.42 : e.kind === "similar" ? 0.6 + e.w * 0.4 : 0.85) * (mLight() ? 0.7 : 1) },
           dashes: e.kind === "time",
           smooth: { enabled: true, type: r < 0.5 ? "curvedCW" : "curvedCCW", roundness: (hub ? 0.18 : 0.22) + (r < 0.5 ? r : r - 0.5) * 0.7 },
           length: hub ? 170 : 55 + (1 - (e.w || 0.5)) * 70, selectionWidth: 1.5, hoverWidth: 1 };
}
/* огоньки по связям: каждый кадр — точки на кривых (getPoint у ребра) */
let mPulse = null, mSparks = [];
/* ≤120 огоньков: каждый кадр перерисовывает весь граф, больше — заметная нагрузка; ~30 кадров/с, и только пока раздел виден */
function startPulses() {
  stopPulses();
  const all = mEdges.get(), main = all.filter(e => e._k !== "hub").map(e => e.id);
  const hubs = all.filter(e => e._k === "hub").map(e => e.id).sort(() => Math.random() - 0.5);
  const ids = main.slice(0, 120).concat(hubs.slice(0, Math.max(12, 60 - main.length)));   // мало заметок — огоньки и по разделам
  if (!ids.length) return;
  mSparks = ids.map(id => ({ id, t: Math.random(), v: 0.0025 + Math.random() * 0.004, dir: Math.random() < 0.5 ? 1 : -1 }));
  let last = 0;
  const loop = (ts) => {
    mPulse = requestAnimationFrame(loop);
    if (document.hidden || !$("#p-memory").classList.contains("cur") || ts - last < 33) return;
    last = ts; mSparks.forEach(s => { s.t += s.v * s.dir; if (s.t > 1 || s.t < 0) { s.dir *= -1; s.t = Math.max(0, Math.min(1, s.t)); } });
    mNet.redraw();
  };
  mPulse = requestAnimationFrame(loop);
}
function stopPulses() { if (mPulse) cancelAnimationFrame(mPulse); mPulse = null; mSparks = []; }
/* Анимация карты: на мощном компьютере — живая (огоньки, физика), на слабом (лёгкий режим, ≤2 ядра) — карта раскладывается
   один раз и замирает: перерисовка только когда двигаете или масштабируете сами. Выбор — кнопкой, запоминается. */
function memMotion() {
  const m = get("ui.memory_motion") || "auto";
  if (m === "on" || m === "off") return m === "on";
  return !(S && S.device && S.device.light) && (navigator.hardwareConcurrency || 4) > 2;
}
function memMotionUi() {
  const b = $("#m-motion"); if (!b) return;
  const on = memMotion(); b.classList.toggle("on", on); b.textContent = on ? "Анимация: вкл" : "Анимация: выкл";
}
function memMotionApply() {
  memMotionUi();
  if (!mNet) return;
  if (memMotion()) { mNet.setOptions({ physics: { enabled: true } }); startPulses(); }
  else { stopPulses(); mNet.setOptions({ physics: { enabled: false } }); mNet.redraw(); }
}
function drawSparks(ctx) {
  const body = mNet && mNet.body; if (!body) return;
  for (const s of mSparks) {
    const ed = body.edges[s.id]; if (!ed || !ed.edgeType || !ed.options || ed.options.hidden || !ed.from || !ed.to || ed.from.options.hidden || ed.to.options.hidden) continue;
    let pt; try { pt = ed.edgeType.getPoint(s.t); } catch (e) { continue; }
    const c = (s.dir > 0 ? ed.to : ed.from).options.color.background || "#fff";
    const g = ctx.createRadialGradient(pt.x, pt.y, 0, pt.x, pt.y, 7);
    g.addColorStop(0, mLight() ? "rgba(255,255,255,1)" : "rgba(255,255,255,.95)"); g.addColorStop(0.35, c); g.addColorStop(1, "rgba(255,255,255,0)");
    ctx.fillStyle = g; ctx.globalAlpha = 0.85; ctx.beginPath(); ctx.arc(pt.x, pt.y, 7, 0, Math.PI * 2); ctx.fill(); ctx.globalAlpha = 1;
  }
}
/* Правая панель: что за узел и его связи (кроме связей с разделами); ghost — [[ссылка]] на ещё не написанную заметку */
function showNode(id) {
  const n = mData.nodes.find(x => x.id === id); if (!n) return;
  const nb = mNet.getConnectedNodes(id).map(i => mData.nodes.find(x => x.id === i)).filter(x => x && x.kind !== "hub");
  const side = $("#m-side");
  side.innerHTML = `<div class="k">${(MK[n.kind] || ["", ""])[0]}${n.ghost ? " · ещё не написана" : ""}</div><h3></h3><div class="body"></div>` +
    (n.path ? `<button class="btn small" id="m-open">Открыть</button>` : "") +
    (nb.length ? `<div class="k" style="margin-top:14px">Связи · ${nb.length}</div><ul>${nb.slice(0, 30).map(x => `<li data-id="${escH(x.id)}"></li>`).join("")}</ul>` : "");
  $("h3", side).textContent = n.label; $(".body", side).textContent = n.title || "";
  $$("li", side).forEach(li => { const x = mData.nodes.find(y => y.id === li.dataset.id); li.textContent = x.label; li.onclick = () => focusNode(x.id); });
  const ob = $("#m-open"); if (ob) ob.onclick = () => { $('nav button[data-p="folder"]').click(); setTimeout(() => openFile(n.path), 250); };
}
function focusNode(id) { mNet.selectNodes([id]); mNet.focus(id, { scale: 1.25, animation: { duration: 600, easingFunction: "easeInOutQuad" } }); showNode(id); }
/* keep — обновить уже нарисованный граф на месте, без новой раскладки */
async function loadMemory(keep) {
  try {
    await loadVis();
    mData = await core.call("memory_graph");
    renderMemStats(mData.stats); renderLegend(); memMotionUi();
    const nodes = mData.nodes.map(nodeStyle), edges = mData.edges.map(edgeStyle);
    if (mNet && keep) {                     // обновление без «взрыва»: новые узлы появляются, старые на местах
      const have = new Set(mNodes.getIds()), want = new Set(nodes.map(n => n.id));
      mNodes.remove([...have].filter(i => !want.has(i))); mNodes.update(nodes);
      mEdges.clear(); mEdges.add(edges); if (memMotion()) startPulses(); return;
    }
    mNodes = new vis.DataSet(nodes); mEdges = new vis.DataSet(edges);
    if (mNet) mNet.destroy();
    mNet = new vis.Network($("#m-graph"), { nodes: mNodes, edges: mEdges }, {
      physics: { solver: "forceAtlas2Based", forceAtlas2Based: { gravitationalConstant: -48, centralGravity: 0.018, springLength: 65, springConstant: 0.07, damping: 0.45, avoidOverlap: 0.3 },
                 stabilization: { iterations: memMotion() ? 260 : 180, fit: true }, maxVelocity: 35, minVelocity: 0.5 },
      interaction: { hover: true, tooltipDelay: 120, navigationButtons: false, keyboard: false, zoomSpeed: 0.6 },
      nodes: { scaling: { label: { enabled: false } } }, edges: { selectionWidth: 2 } });
    mNet.on("afterDrawing", drawSparks);
    mNet.once("stabilizationIterationsDone", () => { if (memMotion()) startPulses(); else mNet.setOptions({ physics: { enabled: false } }); });
    mNet.on("click", p => { if (!p.nodes.length) return; const n = mData.nodes.find(x => x.id === p.nodes[0]);
      if (n && n.path && MN_TEXT.test(n.path) && !n.path.startsWith("obsidian:")) openNote(n.path, false); else showNode(p.nodes[0]); });
    mNet.on("doubleClick", p => { if (p.nodes.length) focusNode(p.nodes[0]); else mNet.fit({ animation: { duration: 600 } }); });
    mNet.once("stabilizationIterationsDone", () => mNet.fit({ animation: { duration: 700 } }));
  } catch (e) { $("#m-graph").innerHTML = `<p class="hint" style="padding:24px">${escH(e.message)}</p>`; }
}
/* тему поменяли — карта перекрашивается на месте, без новой раскладки */
new MutationObserver(() => {
  const L = mLight(); if (L === window._mLightWas) return; window._mLightWas = L;
  if (mNet && mData) { mNodes.update(mData.nodes.map(nodeStyle)); mEdges.update(mData.edges.map(edgeStyle)); mNet.redraw(); }
}).observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
/* ---------- «Память»: заметки слева, редактор справа ---------- */
/* localStorage есть не везде (окно студии на Linux открывает страницу как файл) — тогда помним в памяти до закрытия окна.
   Значения — строки. Хранит то, что касается только этого окна: ширину панелей, открытые папки, вкладку «Души». */
const LS = (() => { const mem = {}; let ls = null; try { ls = window.localStorage; ls.setItem("_t", "1"); ls.removeItem("_t"); } catch (e) { ls = null; }
  return { get: (k, d) => { try { const v = ls ? ls.getItem(k) : mem[k]; return v == null ? d : v; } catch (e) { return mem[k] == null ? d : mem[k]; } },
           set: (k, v) => { mem[k] = String(v); try { if (ls) ls.setItem(k, String(v)); } catch (e) {} } }; })();
let mnTab = "tree", mnTree = null, meCur = null, meDirty = false, meMode = "view";
const MN_DIRS = ["Заметки", "Дневник", "Память", "Входящие", "Финансы", "Задачи", "Знания", "Навыки"];
const MN_TEXT = /\.(md|txt)$/i;
function mnFiles(items, out = [], dir = "") {
  (items || []).forEach(n => { if (n.type === "dir") mnFiles(n.children, out, n.path); else if (MN_TEXT.test(n.name)) out.push({ ...n, dir }); });
  return out;
}
async function loadNotes() {
  try { mnTree = await core.call("ws_tree"); renderNotes(); } catch (e) { $("#mn-list").textContent = e.message; }
}
function mnItem(f) {
  const b = document.createElement("button"); b.className = "mn-item" + (meCur && meCur.path === f.path ? " cur" : ""); b.dataset.path = f.path;
  b.textContent = f.name.replace(MN_TEXT, "");
  if (mnTab === "new") { const sm = document.createElement("small"); sm.textContent = `${f.dir || "папка ассистента"} · ${new Date(f.mtime * 1000).toLocaleString("ru-RU", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}`; b.appendChild(sm); }
  b.onclick = () => openNote(f.path, true);
  return b;
}
function renderNotes() {
  const box = $("#mn-list"); box.innerHTML = ""; if (!mnTree) return;
  const q = $("#mn-filter").value.trim().toLowerCase();
  const all = mnFiles(mnTree.items).filter(f => !/^(Лаборатория|Навыки)\//.test(f.path) && f.name !== "README.md");   // служебное — не заметки
  const hit = (f) => !q || f.name.toLowerCase().includes(q);
  if (mnTab === "new") {
    all.filter(hit).sort((a, b) => b.mtime - a.mtime).slice(0, 80).forEach(f => box.appendChild(mnItem(f)));
  } else {
    const open = JSON.parse(LS.get("mn-open", '["Заметки"]'));
    const groups = {};
    all.filter(hit).forEach(f => { const top = f.path.includes("/") ? f.path.split("/")[0] : "Папка ассистента"; (groups[top] = groups[top] || []).push(f); });
    const order = Object.keys(groups).sort((a, b) => (MN_DIRS.indexOf(a) + 1 || 99) - (MN_DIRS.indexOf(b) + 1 || 99) || a.localeCompare(b, "ru"));
    order.forEach(g => {
      const isOpen = q || open.includes(g);
      const h = document.createElement("div"); h.className = "mn-dir" + (isOpen ? " open" : ""); h.innerHTML = "<i>▶</i><span></span><em></em>";
      $("span", h).textContent = g; $("em", h).textContent = groups[g].length;
      const kids = document.createElement("div"); kids.className = "mn-kids" + (isOpen ? "" : " hide");
      groups[g].sort((a, b) => a.path.localeCompare(b.path, "ru")).forEach(f => {
        const sub = f.dir && f.dir !== g ? f.dir.slice(g.length + 1) : "";
        const it = mnItem(f); if (sub) { const sm = document.createElement("small"); sm.textContent = sub; it.appendChild(sm); } kids.appendChild(it);
      });
      h.onclick = () => { const o = JSON.parse(LS.get("mn-open", '["Заметки"]')); const i = o.indexOf(g);
        if (i >= 0) o.splice(i, 1); else o.push(g); LS.set("mn-open", JSON.stringify(o)); renderNotes(); };
      box.appendChild(h); box.appendChild(kids);
    });
  }
  if (!box.children.length) box.innerHTML = `<p class="hint" style="padding:8px">${q ? "Ничего не нашлось." : "Заметок пока нет — нажмите «Новая заметка» или скажите: «запиши заметку…»."}</p>`;
}
$$(".mn-tabs button").forEach(b => b.onclick = () => { mnTab = b.dataset.t; $$(".mn-tabs button").forEach(x => x.classList.toggle("cur", x === b)); renderNotes(); });
$("#mn-filter").oninput = renderNotes;
function nodeOfPath(path) { return mData && mData.nodes.find(x => x.path === path); }
async function openNote(path, focusGraph) {
  if (meDirty && meCur && meCur.path !== path && !await ask("В заметке есть несохранённые изменения. Перейти без сохранения?")) return;
  try {
    const f = await core.call("ws_read", { path });
    meCur = { path, text: f.text || "", binary: f.binary, mtime: f.mtime }; meDirty = false;
    if (LS.get("m-right", "1") !== "1") { LS.set("m-right", "1"); mPanes(); }
    renderEditor();
    $$("#mn-list .mn-item").forEach(b => b.classList.toggle("cur", b.dataset.path === path));
    const n = nodeOfPath(path);
    if (n && mNet && focusGraph) { mNet.selectNodes([n.id]); mNet.focus(n.id, { scale: 1.1, animation: { duration: 500, easingFunction: "easeInOutQuad" } }); }
  } catch (e) { toast(e.message); }
}
function renderEditor() {
  const side = $("#m-side"), f = meCur; if (!f) return;
  // «Обо мне» и README ядро создаёт и читает по постоянному пути — их не переименовать и не удалить
  const name = f.path.split("/").pop(), fixed = f.path === "Память/Обо мне.md" || f.path === "README.md";
  side.innerHTML = `<div class="me-head"><input type="text" id="me-title" ${fixed ? "readonly" : ""}></div>
    <div class="me-tools"><div class="seg"><button data-m="view">Просмотр</button><button data-m="edit">Правка</button></div><span class="st" id="me-st"></span></div>
    ${f.binary ? '<div class="fempty">Это не текстовый файл.</div>' : '<textarea id="me-text" spellcheck="true"></textarea><div id="me-view" style="display:none"></div>'}
    <div class="me-foot"><button class="btn primary small" id="me-save">Сохранить</button><button class="btn small" id="me-app">Открыть в приложении</button>
      ${fixed ? "" : '<button class="btn small" id="me-del">В корзину</button>'}</div><div class="me-links" id="me-links"></div>`;
  $("#me-title").value = name.replace(MN_TEXT, ""); $("#me-title").title = f.path;
  const ta = $("#me-text");
  if (ta) { ta.value = f.text; ta.oninput = () => { meDirty = true; meState(); }; ta.onkeydown = (e) => { if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") { e.preventDefault(); meSave(); } }; }
  $$(".me-tools .seg button").forEach(b => b.onclick = () => { meMode = b.dataset.m; meModeApply(); });
  const vw = $("#me-view"); if (vw) vw.ondblclick = () => { meMode = "edit"; meModeApply(); const t = $("#me-text"); if (t) t.focus(); };
  meModeApply(); meState();
  $("#me-save").onclick = meSave;
  $("#me-app").onclick = () => core.call("ws_open", { path: f.path }).catch(e => toast(e.message));
  const del = $("#me-del"); if (del) del.onclick = async () => { if (!await ask(`Убрать заметку «${$("#me-title").value}» в корзину?`)) return;
    try { await core.call("ws_delete", { path: f.path }); toast("Заметка в корзине"); meCur = null; meDirty = false;
      $("#m-side").innerHTML = '<p class="hint">Заметка убрана в корзину. Выберите другую слева.</p>'; loadNotes(); loadMemory(true); } catch (e) { toast(e.message); } };
  $("#me-title").onkeydown = (e) => { if (e.key === "Enter") { e.preventDefault(); meSave(); } };
  const n = nodeOfPath(f.path), lk = $("#me-links");
  if (n && mNet) {
    const nb = mNet.getConnectedNodes(n.id).map(i => mData.nodes.find(x => x.id === i)).filter(x => x && x.kind !== "hub");
    if (nb.length) { lk.innerHTML = `<b>Связи · ${nb.length}</b><br>`; nb.slice(0, 40).forEach(x => { const sp = document.createElement("span"); sp.textContent = x.label;
      sp.onclick = () => x.path && MN_TEXT.test(x.path) ? openNote(x.path, true) : focusNode(x.id); lk.appendChild(sp); }); }
  }
}
function meModeApply() {
  $$(".me-tools .seg button").forEach(b => b.classList.toggle("cur", b.dataset.m === meMode));
  const ta = $("#me-text"), v = $("#me-view"); if (!ta) return;
  if (meMode === "view") { v.innerHTML = `<div class="md">${md(ta.value)}</div>`; v.style.display = ""; ta.style.display = "none";
  }
  else { v.style.display = "none"; ta.style.display = ""; }
}
function meState() { const st = $("#me-st"); if (!st || !meCur) return; st.classList.toggle("dirty", meDirty);
  st.textContent = meDirty ? "есть изменения · Ctrl+S" : "сохранено " + new Date((meCur.mtime || 0) * 1000).toLocaleString("ru-RU", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }); }
async function meSave() {
  if (!meCur || meCur.binary) return;
  try {
    let path = meCur.path; const title = $("#me-title").value.trim(), old = path.split("/").pop().replace(MN_TEXT, "");
    if (title && title !== old) { path = (await core.call("ws_rename", { path, title })).path; }   // сначала имя, потом текст — уже по новому пути
    const r = await core.call("ws_write", { path, text: $("#me-text").value });
    meCur = { ...meCur, path, text: $("#me-text").value, mtime: r.mtime }; meDirty = false; meState(); $("#me-title").title = path;
    toast("Сохранено"); loadNotes(); loadMemory(true);
  } catch (e) { toast(e.message); }
}
$("#mn-new").onclick = async () => {
  const title = await askText("Название новой заметки:", ""); if (title === null) return;
  try { const r = await core.call("ws_new_note", { title: title.trim() || "Новая заметка" }); await loadNotes(); await openNote(r.path, false); meMode = "edit"; meModeApply();
    const ta = $("#me-text"); if (ta) { ta.focus(); ta.selectionStart = ta.selectionEnd = ta.value.length; } loadMemory(true); } catch (e) { toast(e.message); }
};
document.addEventListener("click", (e) => {             // [[ссылка]] в заметке (a.wl из md(), href "wiki:…") — открыть ту заметку в «Памяти»
  const a = e.target.closest && e.target.closest("a.wl"); if (!a) return;
  e.preventDefault(); const t = decodeURIComponent((a.getAttribute("href") || "").slice(5));
  const n = mData && mData.nodes.find(x => x.label === t && x.path);
  if (!n) return toast(`Заметки «${t}» пока нет`);
  if (!$("#p-memory").classList.contains("cur")) $('nav button[data-p="memory"]').click();
  setTimeout(() => openNote(n.path, true), 200);
});
window.addEventListener("beforeunload", (e) => { if (meDirty) { e.preventDefault(); e.returnValue = ""; } });
$("#m-reload").onclick = () => { loadMemory(true); loadNotes(); };
/* Раскладка «список | граф | запись»: панели можно скрыть и растянуть; графу остаётся не меньше 360 px */
function mPanes() {
  const L = LS.get("m-left", "1") === "1", R = LS.get("m-right", "1") === "1", w = $(".mwrap");
  w.classList.toggle("no-left", !L); w.classList.toggle("no-right", !R);
  $("#mp-left").classList.toggle("on", L); $("#mp-right").classList.toggle("on", R);
  const W = w.clientWidth || 1400;
  const lw = Math.max(180, Math.min(520, +LS.get("m-lw", "270") || 270));
  const rw = Math.max(300, Math.min(W - (L ? lw : 0) - 360, +LS.get("m-rw", "0") || Math.max(380, Math.round(W * 0.3))));
  w.style.gridTemplateColumns = (L ? `${lw}px 12px ` : "") + "minmax(0, 1fr)" + (R ? ` 12px ${rw}px` : "");
  setTimeout(() => mNet && mNet.redraw(), 60);
}
/* тянем разделители: левый — ширина списка заметок, правый — ширина записи; запоминается */
[["#ms-l", "m-lw"], ["#ms-r", "m-rw"]].forEach(([sel, key]) => {
  const sp = $(sel);
  sp.onpointerdown = (e) => {
    e.preventDefault(); sp.setPointerCapture(e.pointerId); sp.classList.add("drag"); document.body.classList.add("mdrag");
    const rect = $(".mwrap").getBoundingClientRect();
    sp.onpointermove = (ev) => {
      const v = key === "m-lw" ? ev.clientX - rect.left - 6 : rect.right - ev.clientX - 6;
      LS.set(key, String(Math.round(v))); mPanes();
    };
    sp.onpointerup = () => { sp.onpointermove = null; sp.classList.remove("drag"); document.body.classList.remove("mdrag"); mNet && mNet.fit({ animation: { duration: 400 } }); };
  };
  sp.ondblclick = () => { LS.set(key, key === "m-lw" ? "270" : "0"); mPanes(); };      // двойной щелчок — ширина по умолчанию
});
window.addEventListener("resize", () => { if ($("#p-memory").classList.contains("cur")) mPanes(); });
$("#mp-left").onclick = () => { LS.set("m-left", LS.get("m-left", "1") === "1" ? "0" : "1"); mPanes(); };
$("#mp-right").onclick = () => { LS.set("m-right", LS.get("m-right", "1") === "1" ? "0" : "1"); mPanes(); };
mPanes();
$("#m-motion").onclick = async () => {
  const want = memMotion() ? "off" : "on";
  await save({ ui: { memory_motion: want } }, true);
  memMotionApply(); toast(want === "on" ? "Анимация включена" : "Анимация выключена — карта замерла, компьютеру легче");
};
$("#m-full").onclick = () => { const g = $("#m-graph"); (g.requestFullscreen || g.webkitRequestFullscreen || (() => {})).call(g); };
document.addEventListener("fullscreenchange", () => setTimeout(() => mNet && mNet.fit({ animation: { duration: 500 } }), 150));
$("#m-fit").onclick = () => mNet && mNet.fit({ animation: { duration: 600 } });
let mfT = null;
$("#m-find").oninput = () => {
  const q = $("#m-find").value.trim(); clearTimeout(mfT); if (!q || !mData) return;
  const n = mData.nodes.find(x => x.label.toLowerCase().includes(q.toLowerCase())); if (n) focusNode(n.id);
  mfT = setTimeout(() => core.call("recall", { query: q }).then(res => {          // поиск по тексту записей
    if (!res || !res.length || $("#m-find").value.trim() !== q) return;
    const side = $("#m-side"); side.innerHTML = `<div class="k">Нашлось в записях · ${res.length}</div>`;
    res.forEach(r => {
      const d = document.createElement("div"); d.className = "mhit"; d.innerHTML = "<b></b><span></span>";
      $("b", d).textContent = r.title; $("span", d).textContent = r.snippet.slice(0, 220) + (r.snippet.length > 220 ? "…" : "");
      d.onclick = () => { if (r.path.startsWith("obsidian:") && obLast && obLast.name) return openExt(`obsidian://open?vault=${encodeURIComponent(obLast.name)}&file=${encodeURIComponent(r.path.slice(9))}`);
        const node = mData.nodes.find(x => x.path === r.path); if (node) focusNode(node.id);
        else { $('nav button[data-p="folder"]').click(); setTimeout(() => openFile(r.path), 250); } };
      side.appendChild(d);
    });
  }).catch(() => {}), 300);
};
