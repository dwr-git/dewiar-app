/* «Совет ИИ» (0.67; владелец 28.10: «несколько персонажей с разными моделями — раздел, где выносим идею, а они все вместе
   отвечают, спорят и помогают; как живые, с красивой стильной анимацией; пусть пишут, но захватывающе и убедительно»).
   Слева — вопрос, кто за столом (персонаж и его модель), прошлые советы. Справа — «стол»: живые облики участников
   (DewiarEntity — те же, что в виджете), кто пишет — тот «говорит»: облик оживает, светится его цветом; шаги «Мнения →
   Спор → Итог»; ниже — лента: карточки участников пишутся на глазах, итог — отдельной карточкой.
   Ядро (core/council.py): council_members, council_start {q, pids}, council_stop, council_history; событие «council»
   {sid, phase, who, begin | start | delta | done (text, error) | end (summary, file, stopped, error)}. */
const CO = { ms: [], pick: [], sid: "", ents: {}, cards: {}, lv: {}, raf: 0, running: false, phase: "" };
const CO_EX = ["Стоит ли переходить на удалённую работу?", "Как за месяц подтянуть английский?", "Купить квартиру сейчас или копить дальше?",
  "Идея: кофейня у дома — взлетит?", "Как уговорить ребёнка меньше сидеть в телефоне?"];
const coEsc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const coM = (pid) => CO.ms.find(m => m.id === pid) || { id: pid, name: pid, color: "#8B7CFF", model: "" };
const coMd = (t) => coEsc(t).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").split(/\n{2,}/).map(p => `<p>${p.replace(/<\/b>\s*\n/g, "</b>").replace(/\n/g, "<br>")}</p>`).join("");
/* значок участника: своё фото персонажа — картинкой, иначе буква на его цвете */
const coAva = (m) => m.avatar_url ? `<i class="pic" aria-hidden="true" style="background-image:url('${String(m.avatar_url).replace(/'/g, "%27")}')"></i>` : `<i aria-hidden="true">${coEsc((m.name || "?")[0])}</i>`;

async function loadCouncil() {
  let d;
  try { d = await core.call("council_members"); } catch (e) { toast(e.message, 4000); return; }
  CO.ms = d.members || [];
  if (!CO.pick.length) CO.pick = (d.pick || []).slice();
  CO.pick = CO.pick.filter(id => CO.ms.some(m => m.id === id));
  coSetup(); coHist(d.history || []);
  if (d.state && !d.state.done && d.state.sid !== CO.sid) coResume(d.state);
  else if (!CO.sid) coSeats(CO.pick);
}

function coSetup() {
  $("#co-ex").innerHTML = CO_EX.map(x => `<button class="chip" type="button">${coEsc(x)}</button>`).join("");
  $$("#co-ex .chip").forEach(b => b.onclick = () => { $("#co-q").value = b.textContent; $("#co-q").focus(); });
  $("#co-ms").innerHTML = CO.ms.map(m => `<button type="button" class="co-m${CO.pick.includes(m.id) ? " on" : ""}" data-id="${coEsc(m.id)}" aria-pressed="${CO.pick.includes(m.id)}" style="--c:${coEsc(m.color)}">`
    + `${coAva(m)}<span><b>${coEsc(m.name)}</b><small>${coEsc(m.model || "общий мозг")}${m.own ? " · свой мозг" : ""}</small></span></button>`).join("");
  $$("#co-ms .co-m").forEach(b => b.onclick = () => {
    if (CO.running) return;
    const id = b.dataset.id, i = CO.pick.indexOf(id);
    if (i >= 0) CO.pick.splice(i, 1); else if (CO.pick.length < 5) CO.pick.push(id); else return toast("За столом — до пяти участников");
    coSetup(); coSeats(CO.pick);
  });
  $("#co-n").textContent = `${CO.pick.length} из ${CO.ms.length}`;
  const models = new Set(CO.pick.map(id => coM(id).model).filter(Boolean));
  $("#co-tip").innerHTML = CO.pick.length < 2 ? "Позовите хотя бы двоих."
    : models.size < 2 ? "Сейчас все думают одной моделью — спорят характеры. Разные модели интереснее: «Персонажи» → персонаж → «Свой мозг»."
    : `Думают разными моделями: ${[...models].map(coEsc).join(", ")}.`;
  $("#co-go").disabled = CO.running;
}

function coHist(list) {
  $("#co-hist").innerHTML = list.length ? list.map(h => `<li><button type="button" data-f="${coEsc(h.file)}"><b>${coEsc(h.title)}</b><small>${new Date(h.t * 1000).toLocaleString("ru-RU", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}</small></button></li>`).join("")
    : `<li class="co-none">Здесь появятся протоколы советов — их можно открыть и перечитать.</li>`;
  $$("#co-hist [data-f]").forEach(b => b.onclick = () => core.call("ws_open", { path: b.dataset.f }).catch(e => toast(e.message)));
}

/* стол: живые облики. Говорит (пришли новые слова) — облик «говорит» и светится; думает — «думает»; ждёт — покой */
function coSeats(pids) {
  Object.values(CO.ents).forEach(e => { try { e.destroy(); } catch (x) { } });
  CO.ents = {}; CO.lv = {};
  $("#co-seats").innerHTML = pids.map(id => { const m = coM(id);
    return `<div class="co-seat" data-id="${coEsc(id)}" style="--c:${coEsc(m.color)}"><div class="co-orb"><canvas aria-hidden="true"></canvas></div>`
      + `<b>${coEsc(m.name)}</b><small>${coEsc(m.model || "общий мозг")}</small><span class="co-st"></span></div>`; }).join("");
  $$("#co-seats .co-seat").forEach(el => {
    const m = coM(el.dataset.id), cv = $("canvas", el);
    if (typeof DewiarEntity !== "function") return;
    try { CO.ents[m.id] = new DewiarEntity(cv, { style: m.avatar_url && m.style !== "aura" ? "photo" : (m.style || "nexus"), color: m.color, image: m.avatar_url || null, live: m.live || "", ring: false }); CO.ents[m.id].set({ state: "idle" }); } catch (e) { }
  });
  $("#co-stage").classList.toggle("few", pids.length <= 2);
  if (!CO.raf) CO.raf = requestAnimationFrame(coTick);
}
function coSeat(pid, st) {
  const el = $(`#co-seats .co-seat[data-id="${CSS.escape(pid)}"]`); if (!el) return;
  el.classList.toggle("talk", st === "talk"); el.classList.toggle("think", st === "think"); el.classList.toggle("done", st === "done"); el.classList.toggle("fail", st === "fail");
  $(".co-st", el).textContent = st === "think" ? "думает…" : st === "talk" ? "пишет" : st === "fail" ? "не ответил(а)" : "";
  const e = CO.ents[pid]; if (e) e.set({ state: st === "talk" ? "speaking" : st === "think" ? "thinking" : "idle" });
}
function coTick() {                                     // голос облика — от того, сколько слов только что пришло
  const now = performance.now();
  for (const [pid, l] of Object.entries(CO.lv)) {
    const e = CO.ents[pid]; if (!e) continue;
    const v = Math.max(0, l.v * Math.exp(-(now - l.t) / 380));
    e.set({ level: Math.min(1, v + 0.12 * Math.abs(Math.sin(now / 140 + pid.length))) });
    if (v < 0.02 && now - l.t > 1500 && l.talk) { l.talk = false; coSeat(pid, "done"); }
  }
  CO.raf = document.hidden || !$("#p-council").classList.contains("cur") && !CO.running ? 0 : requestAnimationFrame(coTick);
}

function coPhase(ph) {
  CO.phase = ph;
  const order = ["r1", "r2", "sum"], i = order.indexOf(ph);
  $$("#co-steps li").forEach((li, k) => { li.classList.toggle("on", k === i); li.classList.toggle("past", i >= 0 && k < i || ph === "end"); });
  if (i >= 0 && !$(`#co-feed .co-div[data-ph="${ph}"]`)) {
    const t = { r1: "Мнения — каждый отвечает сам", r2: "Спор — отвечают друг другу", sum: "Итог совета" }[ph];
    $("#co-feed").insertAdjacentHTML("beforeend", `<div class="co-div" data-ph="${ph}"><span>${t}</span></div>`);
  }
}
function coCard(pid, ph) {
  const k = ph + ":" + pid; if (CO.cards[k]) return CO.cards[k];
  const m = coM(pid), sum = ph === "sum";
  $("#co-feed").insertAdjacentHTML("beforeend", `<article class="co-msg${sum ? " sum" : ""}" data-k="${coEsc(k)}" style="--c:${coEsc(m.color)}">`
    + `<header>${coAva(m)}<b>${coEsc(m.name)}</b><small>${sum ? "ведёт совет" : coEsc(m.model || "")}</small></header>`
    + `<div class="co-tx"><span class="co-dots" aria-label="думает"><i></i><i></i><i></i></span></div></article>`);
  const el = $(`#co-feed .co-msg[data-k="${CSS.escape(k)}"]`);
  CO.cards[k] = { el, text: "" };
  return CO.cards[k];
}
function coScroll() { const f = $("#co-feed"); const r = f.getBoundingClientRect(); if (r.bottom > innerHeight - 40) f.lastElementChild && f.lastElementChild.scrollIntoView({ block: "end", behavior: "smooth" }); }

async function coStart() {
  const q = $("#co-q").value.trim();
  if (q.length < 5) { toast("Напишите вопрос или идею — хотя бы пару слов"); $("#co-q").focus(); return; }
  let r; const go = $("#co-go"); go.disabled = true;           // не два совета от двойного нажатия
  try { r = await core.call("council_start", { q, pids: CO.pick }); } catch (e) { toast(e.message, 4500); return; } finally { go.disabled = false; }
  coBegin(r.sid, q, r.pids);
}
function coBegin(sid, q, pids) {
  CO.sid = sid; CO.cards = {}; CO.running = true; CO.phase = "";
  $("#co-feed").innerHTML = "";
  $("#co-qline").innerHTML = `<span>Вопрос совету</span>${coEsc(q)}`;
  $("#co-stage").classList.add("live");
  $("#co-stop").hidden = false;
  coSeats(pids); coSetup(); coPhase("r1");
}
function coResume(st) {                              // совет уже идёт (позвали голосом, студия открылась позже) — сказанное сразу
  coBegin(st.sid, st.q, st.pids);
  for (const ph of ["r1", "r2"]) {
    const any = st.pids.some(pid => (st.said[pid] || {})[ph]);
    if (!any) continue;
    coPhase(ph);
    st.pids.forEach(pid => { const t = (st.said[pid] || {})[ph]; if (!t) return; const c = coCard(pid, ph); c.text = t; $(".co-tx", c.el).innerHTML = `<p>${coEsc(t)}</p>`; });
  }
}

core.on("council", (e) => {
  if (e && e.open && e.sid !== CO.sid && $("#p-council")) {         // позвали голосом — подхватить идущий совет
    if ($("#p-council").classList.contains("cur")) loadCouncil();
    return;
  }
  if (!e || e.sid !== CO.sid) return;
  if (e.begin) { coPhase(e.phase); return; }
  if (e.phase === "end") {
    CO.running = false; $("#co-stop").hidden = true; $("#co-stage").classList.remove("live"); coPhase("end");
    Object.keys(CO.ents).forEach(pid => { if (!$(`#co-seats .co-seat[data-id="${CSS.escape(pid)}"]`).classList.contains("fail")) coSeat(pid, ""); });
    const end = document.createElement("div"); end.className = "co-end";
    end.innerHTML = (e.error ? `<p class="bad">${coEsc(e.error[0].toUpperCase() + e.error.slice(1))}.</p>` : e.stopped ? "<p>Совет остановлен.</p>" : "")
      + (e.file ? `<button class="btn small" type="button" data-f="${coEsc(e.file)}">Открыть протокол</button>` : "")
      + `<button class="btn small primary" type="button" data-new>Новый совет</button>`;
    $("#co-feed").appendChild(end);
    $("[data-f]", end) && ($("[data-f]", end).onclick = () => core.call("ws_open", { path: e.file }).catch(x => toast(x.message)));
    $("[data-new]", end).onclick = () => { $("#co-q").value = ""; $("#co-q").focus(); };
    coSetup(); core.call("council_history").then(coHist).catch(() => { });
    return;
  }
  if (e.phase === "docs") {           // 29.10: совет видит «Документы» человека и знания персонажей — видно, что нашлось
    const d = document.createElement("div"); d.className = "co-docs";
    const nm = (pid) => (CO.ms.find(m => m.id === pid) || {}).name || pid;
    d.innerHTML = (e.files && e.files.length ? `<p>Совет смотрит ваши документы: ${e.files.map(f => `<b>${coEsc(f)}</b>`).join(", ")}</p>` : "")
      + (e.members && e.members.length ? `<p>Со своими знаниями: ${e.members.map(p => coEsc(nm(p))).join(", ")}</p>` : "");
    $("#co-feed").appendChild(d); return;
  }
  const c = coCard(e.who, e.phase);
  if (e.start) { coSeat(e.who, "think"); return; }
  if (e.delta) {
    if (!c.text) $(".co-tx", c.el).innerHTML = "";
    c.text += e.delta;
    $(".co-tx", c.el).innerHTML = e.phase === "sum" ? coMd(c.text) : `<p>${coEsc(c.text)}</p>`;
    c.el.classList.add("typing");
    CO.lv[e.who] = { v: Math.min(1, 0.35 + e.delta.length / 60), t: performance.now(), talk: true };
    coSeat(e.who, "talk"); coScroll();
    if (!CO.raf) CO.raf = requestAnimationFrame(coTick);
    return;
  }
  if (e.done) {
    c.el.classList.remove("typing");
    if (e.error && !c.text) { c.el.classList.add("fail"); $(".co-tx", c.el).innerHTML = `<p class="co-err">Не ответил(а): ${coEsc(e.error)}</p>`; coSeat(e.who, "fail"); }
    else { if (e.text) $(".co-tx", c.el).innerHTML = e.phase === "sum" ? coMd(e.text) : `<p>${coEsc(e.text)}</p>`; }
  }
});
if ($("#co-go")) {
  $("#co-go").onclick = coStart;
  $("#co-q").addEventListener("keydown", (e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); coStart(); } });
  $("#co-stop").onclick = () => core.call("council_stop").catch(e => toast(e.message));
  document.addEventListener("visibilitychange", () => { if (!document.hidden && !CO.raf && Object.keys(CO.ents).length) CO.raf = requestAnimationFrame(coTick); });
}
window.loadCouncil = loadCouncil;
