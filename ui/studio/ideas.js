/* Студия → «Идеи Лиры» (0.59; владелец 28.10: «идеи — видеть красиво, за что проголосовали другие, есть ли уже в списке моя,
   если нет — добавить, и повлиять на рейтинг своим голосом; сделанные — с пагинацией и поиском»).
   Сверху — «Опишите идею»: по мере набора ищем похожие (поддержать голосом), нет — «Предложить идею». Ниже — вкладки «Будем
   делать» (по голосам), «Сделано» (с версией), «Мои» (свои — и на рассмотрении), поиск и страницы. Новое в плане с прошлого
   раза — пометка «новое» (localStorage id_seen) и точка в меню. Ядро: ideas_list {tab, q, page}, ideas_similar {q},
   ideas_vote {id, on}, ideas_new {title, text} — оно ходит на сайт (core/ideas.py). */
const ID = { tab: "plan", q: "", page: 1, d: null, seen: 0, simT: 0, findT: 0 };
try { ID.seen = +localStorage.getItem("id_seen") || 0; } catch (e) { }
const idEsc = (t) => typeof escH === "function" ? escH(t) : String(t == null ? "" : t).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const ID_VOTE = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5.5 5.5 13h4v5.5h5V13h4z"/></svg>';

async function loadIdeas(keep) {
  if (!keep) ID.page = 1;
  const list = $("#id-list");
  if (!ID.d) list.innerHTML = `<li class="id-empty">Загружаю идеи…</li>`;
  try { ID.d = await core.call("ideas_list", { tab: ID.tab, q: ID.q, page: ID.page }); }
  catch (e) { list.innerHTML = `<li class="id-empty bad">Идеи не загрузились: ${idEsc(e.message)}. Они живут на сайте Dewiar — нужен интернет.</li>`; $("#id-pager").innerHTML = ""; return; }
  idRender();
}
window.loadIdeas = loadIdeas;

function idItem(x) {
  const fresh = x.status !== "done" && x.plan_ts && x.plan_ts > ID.seen && ID.seen > 0;
  const chip = x.status === "doing" ? `<span class="id-chip doing">делаем</span>` : x.status === "done" ? `<span class="id-chip done">сделано${x.ver ? " в " + idEsc(x.ver) : ""}</span>`
    : x.status === "new" ? `<span class="id-chip wait">на рассмотрении</span>` : x.status === "no" ? `<span class="id-chip no">не будем</span>` : "";
  const can = ["plan", "doing", "new"].includes(x.status);
  return `<li class="id-it${x.voted ? " voted" : ""}${x.status === "done" ? " done" : ""}" data-id="${x.id}">
    <button class="id-vote" type="button" ${can ? "" : "disabled"} aria-pressed="${x.voted}" title="${!can ? (x.status === "done" ? "Уже сделано" : "") : x.voted ? "Снять голос" : "Поддержать — нужно и мне"}">${ID_VOTE}<b>${x.votes}</b></button>
    <div class="id-body"><div class="id-t">${idEsc(x.title)}${fresh ? '<span class="id-chip fresh">новое</span>' : ""}${x.mine ? '<span class="id-chip mine">ваша</span>' : ""}${chip}</div>
      ${x.body ? `<p class="id-d">${idEsc(x.body)}</p>` : ""}${x.reply ? `<p class="id-r">Ответ разработчика: ${idEsc(x.reply)}</p>` : ""}
      ${x.mine && x.status === "new" ? `<button type="button" class="id-del linkbtn">Убрать идею</button>` : ""}</div></li>`;
}
function idRender() {
  const d = ID.d || { items: [], counts: {}, pages: 1, page: 1 };
  ["plan", "done", "mine"].forEach(k => { const el = $("#id-n-" + k); if (el) el.textContent = d.counts[k] ? d.counts[k] : ""; });
  $$("#p-ideas .id-tabs [data-tab]").forEach(b => b.setAttribute("aria-selected", String(b.dataset.tab === ID.tab)));
  const empty = ID.q ? `По «${idEsc(ID.q)}» ничего — предложите это идеей сверху.` : ID.tab === "mine" ? "Вы ещё не предлагали идей. Напишите сверху, что Лире уметь, — разработчик увидит."
    : ID.tab === "done" ? "Здесь появятся идеи, которые уже сделаны, — с номером версии." : "Пока пусто — станьте первым: опишите идею сверху.";
  $("#id-list").innerHTML = d.items.length ? d.items.map(idItem).join("") : `<li class="id-empty">${empty}</li>`;
  $("#id-pager").innerHTML = d.pages > 1 ? Array.from({ length: d.pages }, (_, i) => i + 1).map(n =>
    `<button type="button" data-pg="${n}" ${n === d.page ? 'aria-current="page"' : ""}>${n}</button>`).join("") : "";
  idBind($("#id-list"));
  $$("#id-pager [data-pg]").forEach(b => b.onclick = () => { ID.page = +b.dataset.pg; loadIdeas(true); $("#p-ideas .id-bar").scrollIntoView({ block: "start", behavior: "smooth" }); });
  if (ID.tab === "plan" && d.now) { try { localStorage.setItem("id_seen", String(d.now)); } catch (e) { } const dot = $("#id-dot"); if (dot) dot.classList.remove("on"); }
}
function idBind(root) {
  $$(".id-vote", root).forEach(b => b.onclick = async () => {
    const li = b.closest("[data-id]"), id = +li.dataset.id, on = b.getAttribute("aria-pressed") !== "true", n = b.querySelector("b");
    b.disabled = true; b.setAttribute("aria-pressed", String(on)); li.classList.toggle("voted", on); n.textContent = Math.max(0, +n.textContent + (on ? 1 : -1));
    try { const r = await core.call("ideas_vote", { id, on }); n.textContent = r.votes;
      (ID.d.items || []).concat(ID.sim || []).forEach(x => { if (x.id === id) { x.votes = r.votes; x.voted = r.voted; } });
      if (on) { li.classList.add("pop"); setTimeout(() => li.classList.remove("pop"), 500); } }
    catch (e) { b.setAttribute("aria-pressed", String(!on)); li.classList.toggle("voted", !on); n.textContent = Math.max(0, +n.textContent + (on ? -1 : 1)); toast(e.message, 3500); }
    finally { b.disabled = false; }
  });
  $$(".id-d", root).forEach(p => p.onclick = () => p.classList.toggle("open"));
  // своя идея на рассмотрении — убрать (идея №84: «нечаянно нажал два раза — висят одинаковые»)
  $$(".id-del", root).forEach(b => b.onclick = async () => {
    const li = b.closest("[data-id]"), id = +li.dataset.id, x = ((ID.d && ID.d.items) || []).find(i => i.id === id);
    if (!await ask(`Убрать идею «${(x && x.title) || "№" + id}»? Разработчик её больше не увидит.`, { ok: "Убрать" })) return;
    try { await core.call("ideas_delete", { id }); toast("Идея убрана", 2200); loadIdeas(true); } catch (e) { toast(e.message, 3500); }
  });
}

/* «Опишите идею»: похожие — сразу, по мере набора; кнопка «Предложить» — когда написано хоть несколько слов */
$("#id-q").oninput = () => {
  const q = $("#id-q").value.trim();
  $("#id-new").hidden = q.length < 4; $("#id-res").textContent = "";
  clearTimeout(ID.simT);
  if (q.length < 4) { $("#id-sim").hidden = true; return; }
  ID.simT = setTimeout(async () => {
    let d; try { d = await core.call("ideas_similar", { q }); } catch (e) { return; }
    if ($("#id-q").value.trim() !== q) return;
    ID.sim = d.items || [];
    const box = $("#id-sim");
    box.hidden = !ID.sim.length;
    box.innerHTML = ID.sim.length ? `<p class="id-simh">Похоже, такая идея уже есть — поддержите её голосом:</p><ul class="id-list sm">${ID.sim.map(idItem).join("")}</ul>` : "";
    idBind(box);
    $("#id-send").textContent = ID.sim.length ? "Моя — другая, предложить" : "Предложить идею";
    $("#id-send").classList.toggle("primary", !ID.sim.length);
    $("#id-send-h").textContent = ID.sim.length ? "" : "Похожих нет — ваша будет первой.";
  }, 350);
};
$("#id-q").onkeydown = (e) => { if (e.key === "Enter") { e.preventDefault(); if (!$("#id-new").hidden) $("#id-body").focus(); } };
$("#id-send").onclick = async () => {
  const title = $("#id-q").value.trim(), text = $("#id-body").value.trim(), r = $("#id-res");
  if (title.length < 4) { r.className = "res bad"; r.textContent = "Напишите идею хотя бы в несколько слов."; return; }
  $("#id-send").disabled = true;
  try {
    const d = await core.call("ideas_new", { title, text });
    r.className = "res ok"; r.textContent = d.text || "Спасибо! Идея на рассмотрении.";
    $("#id-q").value = ""; $("#id-body").value = ""; $("#id-new").hidden = true; $("#id-sim").hidden = true;
    ID.tab = "mine"; ID.q = ""; $("#id-find").value = ""; loadIdeas();
  } catch (e) { r.className = "res bad"; r.textContent = e.message; }
  finally { $("#id-send").disabled = false; }
};
$$("#p-ideas .id-tabs [data-tab]").forEach(b => b.onclick = () => { ID.tab = b.dataset.tab; loadIdeas(); });
$("#id-find").oninput = () => { clearTimeout(ID.findT); ID.findT = setTimeout(() => { ID.q = $("#id-find").value.trim(); loadIdeas(); }, 300); };
document.addEventListener("click", (e) => { if (e.target.closest && e.target.closest('nav button[data-p="ideas"]')) setTimeout(() => loadIdeas(), 0); });
/* новое в плане с прошлого раза — точка в меню (раз в 6 часов, тихо) */
async function idDotCheck() {
  if (!ID.seen) return;
  try { const d = await core.call("ideas_list", { tab: "plan" }); const fresh = (d.items || []).some(x => x.plan_ts > ID.seen);
    const dot = $("#id-dot"); if (dot) dot.classList.toggle("on", fresh); } catch (e) { }
}
setTimeout(idDotCheck, 20000); setInterval(idDotCheck, 6 * 3600e3);
