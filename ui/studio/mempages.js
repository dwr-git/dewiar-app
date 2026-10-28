/* Студия Dewiar, «Обо мне» → «Что ассистент помнит» (Память 2.0, 27.10): факты по людям и темам, с датами и метками
   «сейчас» (значение менялось — это новое, прежнее зачёркнуто ниже) и «через N дней» (день рождения скоро); поиск по
   смыслу — тот же, каким ассистент подбирает факты к вопросу (core/memory.py). Команды ядра: memory_view, memory_find,
   memory_add, memory_forget; «Править текстом» — прежний файл целиком (#me-mem, memory_get/memory_set в links.js). */
let mpxData = null, mpxCur = "", mpxAsk = -1, mpxWho = "";      // mpxWho — чья память: "" общая или имя персонажа со своей (0.56)
const MPX_GROUP = { me: "", people: "Люди", topics: "Темы" };
function mpxFacts(n) { return `${n} ${plural(n, "факт", "факта", "фактов")}`; }
function mpxStrip(v) {
  const last = v.last && v.last.pages && v.last.pages.length ? ` В последнем ответе по смыслу вопроса: <b>${v.last.pages.map(p => "«" + escH(p) + "»").join(", ")}</b>.` : "";
  $("#mpx-strip").innerHTML = !v.total ? `<span class="pill">Пока пусто</span>Скажите: «запомни, что у мамы день рождения 14 ноября» — факт появится здесь, на странице «Мама».`
    : v.fits ? `<span class="pill">В каждом ответе</span>Все ${mpxFacts(v.total)} — память небольшая, ассистент читает её целиком.${last}`
    : `<span class="pill">В каждом ответе</span>Главное о вас — <b>${mpxFacts(v.core)}</b> из ${v.total}; остальное ассистент подбирает к вопросу по смыслу — даже если спросили другими словами.${last}`;
}
function mpxPages() {
  const v = mpxData; let html = "", g = null;
  for (const p of v.pages) {
    if (p.group !== g) { g = p.group; if (MPX_GROUP[g]) html += `<div class="mpx-grp">${MPX_GROUP[g]}</div>`; }
    const soon = p.facts.some(f => (f.tags || []).some(t => t[0] === "soon"));
    html += `<button class="mpx-pg${p.key === mpxCur ? " on" : ""}" data-k="${escH(p.key)}"><i>${p.icon}</i><span><b>${escH(p.title)}</b>` +
      `<small>${mpxFacts(p.facts.length)}${soon ? " · скоро дата" : ""}</small></span></button>`;
  }
  $("#mpx-pages").innerHTML = html || `<p class="hint">Страницы появятся сами: «Мама», «Работа», «Здоровье» — по тому, что вы расскажете.</p>`;
  $$("#mpx-pages .mpx-pg").forEach(b => b.onclick = () => { mpxCur = b.dataset.k; mpxAsk = -1; $("#mpx-find").value = ""; mpxPages(); mpxCard(); });
}
function mpxFact(f, page) {
  const tags = (f.tags || []).map(t => `<span class="mpx-tag ${t[0]}">${escH(t[1])}</span>`).join("");
  const prev = (f.prev || []).length ? `<div class="mpx-prev">Раньше: ${f.prev.map(x => "<s>" + escH(x) + "</s>").join(" → ")}</div>` : "";
  const src = [f.date ? "записано " + f.date : "", page ? page : "", f.core ? "" : "к вопросу — по смыслу"].filter(Boolean).join(" · ");
  return `<div class="mpx-f" data-i="${f.i}"><div class="t">${escH(f.text)}${tags}</div>` +
    `<button class="mpx-del${mpxAsk === f.i ? " ask" : ""}" data-i="${f.i}" title="Забыть этот факт">${mpxAsk === f.i ? "Забыть?" : "×"}</button>${prev}<div class="src">${escH(src)}</div></div>`;
}
function mpxBind() {
  $$("#mpx-card .mpx-del").forEach(b => b.onclick = async () => {
    const i = +b.dataset.i;
    if (mpxAsk !== i) { mpxAsk = i; mpxCard(); return; }
    mpxAsk = -1;
    try { await core.call("memory_forget", { i, who: mpxWho }); toast("Забыл", 2000); } catch (e) { toast(e.message, 4000); }
    mpxLoad();
  });
}
function mpxCard() {
  const p = (mpxData.pages || []).find(x => x.key === mpxCur) || (mpxData.pages || [])[0];
  if (!p) { $("#mpx-card").innerHTML = `<div class="fempty">Ассистент ещё ничего о вас не запомнил.<br><span class="hint">Расскажите о себе или впишите факт ниже.</span></div>`; return; }
  mpxCur = p.key;
  $("#mpx-card").innerHTML = `<div class="mpx-ph"><i>${p.icon}</i><div><h3>${escH(p.title)}</h3><p>${mpxFacts(p.facts.length)} · новое сверху</p></div></div>` +
    `<div class="mpx-facts">${p.facts.map(f => mpxFact(f)).join("")}</div>`;
  mpxBind();
}
async function mpxFind(q) {
  if (!q.trim()) { mpxPages(); mpxCard(); return; }
  let r = [];
  try { r = await core.call("memory_find", { q, who: mpxWho }); } catch (e) { toast(e.message, 3000); return; }
  if ($("#mpx-find").value !== q) return;
  const all = Object.fromEntries((mpxData.pages || []).flatMap(p => p.facts.map(f => [f.i, f])));
  $("#mpx-card").innerHTML = `<div class="mpx-ph"><i>🔎</i><div><h3>«${escH(q)}»</h3><p>${r.length ? "Это ассистент взял бы к такому вопросу" : "Ничего похожего в памяти"}</p></div></div>` +
    `<div class="mpx-facts">${r.map(x => mpxFact(all[x.i] || { i: x.i, text: x.text }, x.icon + " " + x.page + (x.meaning ? " · по смыслу" : ""))).join("")}</div>`;
  $$("#mpx-pages .mpx-pg").forEach(b => b.classList.remove("on"));
  mpxBind();
}
/* своя память у персонажа: «Общая» и по вкладке на каждого персонажа со своей памятью (студия → «Персонажи» → «Память») */
function mpxWhoRender(own) {
  const box = $("#mpx-who"); if (!box) return;
  if (mpxWho && !own.includes(mpxWho)) mpxWho = "";
  box.hidden = !own.length;
  box.innerHTML = [["", "Общая"]].concat(own.map(n => [n, n])).map(([k, t]) => `<button role="tab" data-w="${escH(k)}" class="${k === mpxWho ? "on" : ""}" aria-selected="${k === mpxWho}">${escH(t)}</button>`).join("");
  $$("#mpx-who [data-w]").forEach(b => b.onclick = () => { mpxWho = b.dataset.w; mpxCur = ""; mpxLoad(); });
}
async function mpxLoad() {
  if (!$("#mpx-card")) return;
  try { const r = await core.call("memory_view", { who: mpxWho }); mpxData = Object.assign({ pages: [], total: 0, core: 0, fits: true }, r && typeof r === "object" ? r : {}); }
  catch (e) { $("#mpx-card").innerHTML = `<p class="res bad">${escH(e.message)}</p>`; return; }
  if (!Array.isArray(mpxData.pages)) mpxData.pages = [];               // старое ядро или проверка без памяти — пусто, а не ошибка
  mpxWhoRender(mpxData.own || []);
  mpxStrip(mpxData); mpxPages();
  const q = $("#mpx-find").value; q.trim() ? mpxFind(q) : mpxCard();
  core.call("memory_get", { who: mpxWho }).then(t => { $("#me-mem").value = t.trim(); }).catch(() => {});
}
if ($("#mpx-card")) {
  let tm = 0;
  $("#mpx-find").oninput = () => { clearTimeout(tm); tm = setTimeout(() => mpxFind($("#mpx-find").value), 220); };
  const add = async () => {
    const text = $("#mpx-new").value.trim(); if (!text) return;
    try { const r = await core.call("memory_add", { text, who: mpxWho }); toast(r || "Запомнил", 2500); $("#mpx-new").value = ""; } catch (e) { toast(e.message, 4000); return; }
    mpxCur = ""; mpxLoad();
  };
  $("#mpx-addgo").onclick = add;
  $("#mpx-new").onkeydown = (e) => { if (e.key === "Enter") { e.preventDefault(); add(); } };
  $("#mpx-raw").onclick = () => { const r = $("#me-raw"); r.hidden = !r.hidden; $("#mpx-raw").textContent = r.hidden ? "Править текстом" : "Скрыть текст"; if (!r.hidden) $("#me-mem").focus(); };
}
