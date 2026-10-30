/* «Идеи Лиры» на телефоне (0.59; владелец 28.10: «видеть идеи красиво, за что проголосовали другие, есть ли уже моя, если нет —
   добавить, и повлиять на рейтинг голосом; сделанные — со страницами и поиском»). Лист #sh-ideas из «Всё» и «Настройки» → «Идеи Лиры»:
   «Опишите идею» (похожие — сразу, поддержать голосом; нет — «Предложить»), вкладки «Будем делать» / «Сделано» / «Мои»,
   поиск, «Ещё» (страницы). Сайт: cloud.php ?p=/ideas, /ideas/similar, /ideas/vote, /ideas/new; голос — с устройства
   (X-Dewiar-Dev — devId(), сайт хранит отпечаток). Новое в плане с прошлого раза — «новое» (pref idea_seen). */
"use strict";
const IDEA_SVG = '<svg viewBox="0 0 24 24"><path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-3.6 10.8c.7.5 1.1 1.3 1.1 2.2V16h5v-.1c0-.9.4-1.7 1.1-2.2A6 6 0 0 0 12 3z"/></svg>';
const IDV = { tab: "plan", q: "", page: 1, items: [], d: null, sim: [], seen: +(prefGet("idea_seen") || 0), simT: 0, findT: 0, busy: false };
const ideaBase = () => CLOUD_URL.split("?")[0];
async function ideaCall(path, params, body) {
  const qs = Object.entries(params || {}).filter(([, v]) => v !== "" && v != null).map(([k, v]) => "&" + k + "=" + encodeURIComponent(v)).join("");
  const r = await http(body ? "POST" : "GET", ideaBase() + "?p=" + path + qs, { headers: { "X-Dewiar-Dev": devId(), "Content-Type": "application/json" }, body: body || null, timeout: 15000 });
  let d = {}; try { d = JSON.parse(r.body || "{}"); } catch (e) { }
  if (r.status >= 400) throw new Error((d.error && d.error.message) || "сайт ответил " + r.status);
  return d;
}
function ideaItem(x) {
  const fresh = x.status !== "done" && IDV.seen && x.plan_ts > IDV.seen;
  const chip = x.status === "doing" ? '<em class="idc ok">делаем</em>' : x.status === "done" ? `<em class="idc ok">сделано${x.ver ? " в " + esc(x.ver) : ""}</em>`
    : x.status === "new" ? '<em class="idc">на рассмотрении</em>' : x.status === "no" ? '<em class="idc">не будем</em>' : "";
  const can = ["plan", "doing", "new"].includes(x.status);
  return `<div class="idi${x.voted ? " on" : ""}" data-id="${x.id}"><button class="idv" ${can ? "" : "disabled"} aria-pressed="${!!x.voted}" aria-label="${x.voted ? "Снять голос" : "Поддержать"}"><svg viewBox="0 0 24 24"><path d="M12 5.5 5.5 13h4v5.5h5V13h4z"/></svg><b>${x.votes}</b></button>
    <div class="idt"><b>${esc(x.title)}</b><span class="idcs">${fresh ? '<em class="idc new">новое</em>' : ""}${x.mine ? '<em class="idc me">ваша</em>' : ""}${chip}</span>
      ${x.body ? `<p>${esc(x.body)}</p>` : ""}${x.reply ? `<p class="idr">Ответ разработчика: ${esc(x.reply)}</p>` : ""}
      ${x.mine && x.status === "new" ? `<button class="iddel">Убрать идею</button>` : ""}</div></div>`;
}
function ideasHtml() {
  const d = IDV.d || { counts: {} }, c = d.counts || {};
  const tab = (k, t) => `<button role="tab" data-itab="${k}" class="${IDV.tab === k ? "on" : ""}" aria-selected="${IDV.tab === k}"><span>${t}</span>${c[k] ? `<b>${c[k]}</b>` : ""}</button>`;
  const empty = IDV.q ? `По «${esc(IDV.q)}» ничего — предложите это сверху.` : IDV.tab === "mine" ? "Вы ещё не предлагали идей — напишите сверху, что Лире уметь."
    : IDV.tab === "done" ? "Здесь появятся сделанные идеи — с версией." : "Пока пусто — станьте первым.";
  return `<p class="hint" style="margin-top:0">Что Лире уметь дальше — решаем вместе. Поддержите голосом нужное: чем больше голосов, тем раньше возьмёмся.</p>
    <div class="idnew"><div class="idq">${IDEA_SVG}<input id="idq" maxlength="120" placeholder="Опишите идею — поищу похожие" value="${esc(IDV.draft || "")}"></div>
      <div id="idsim"></div><div id="idsend" ${((IDV.draft || "").length >= 4) ? "" : "hidden"}><textarea id="idbody" rows="2" maxlength="2000" placeholder="Подробнее (необязательно)"></textarea>
      <button class="btn p w" id="idgo">Предложить идею</button></div><div class="res" id="idres"></div></div>
    <div class="idtabs" role="tablist">${tab("plan", "В планах")}${tab("done", "Сделано")}${tab("mine", "Мои")}</div>
    <input id="idfind" class="idfind" placeholder="Поиск по идеям" value="${esc(IDV.q)}" aria-label="Поиск по идеям">
    <div id="idlist">${IDV.err ? `<div class="card"><p class="hint" style="margin:0">Идеи не загрузились: ${esc(IDV.err)}. Нужен интернет.</p></div>`
      : !IDV.d ? `<p class="hint">Загружаю…</p>` : IDV.items.length ? IDV.items.map(ideaItem).join("") : `<div class="card"><p class="hint" style="margin:0">${empty}</p></div>`}</div>
    ${IDV.d && IDV.page < (IDV.d.pages || 1) ? `<button class="btn w" id="idmore">Ещё идеи</button>` : ""}`;
}
async function ideasLoad(more) {
  if (!more) { IDV.page = 1; IDV.items = []; }
  try { const d = await ideaCall("/ideas", { tab: IDV.tab, q: IDV.q, page: IDV.page }); IDV.d = d; IDV.err = ""; IDV.items = more ? IDV.items.concat(d.items) : d.items;
    if (IDV.tab === "plan" && d.now) { prefSet("idea_seen", String(d.now)); } }
  catch (e) { IDV.err = netErr ? netErr(e.message || e) : String(e.message || e); }
  ideasRender();
}
function ideasRender() {
  const box = $("#ideas-body"); if (!box) return;
  const focus = document.activeElement && document.activeElement.id, pos = focus && document.activeElement.selectionStart;
  box.innerHTML = ideasHtml(); ideasBind();
  if (focus && $("#" + focus)) { const el = $("#" + focus); el.focus(); try { el.setSelectionRange(pos, pos); } catch (e) { } }
}
function ideasDelBind(root) {                          // своя идея на рассмотрении — убрать (идея №84)
  $$(".iddel", root).forEach(b => b.onclick = async () => {
    const id = +b.closest("[data-id]").dataset.id, x = IDV.items.find(i => i.id === id);
    if (!confirm(`Убрать идею «${(x && x.title) || "№" + id}»? Разработчик её больше не увидит.`)) return;
    try { await ideaCall("/ideas/delete", {}, { id }); IDV.items = IDV.items.filter(i => i.id !== id); toast("Идея убрана", 2200); ideasLoad(); } catch (e) { toast(e.message, 3500); }
  });
}
function ideasVoteBind(root) {
  $$(".idv", root).forEach(b => b.onclick = async () => {
    const it = b.closest("[data-id]"), id = +it.dataset.id, on = b.getAttribute("aria-pressed") !== "true", n = b.querySelector("b");
    b.disabled = true; b.setAttribute("aria-pressed", String(on)); it.classList.toggle("on", on); n.textContent = Math.max(0, +n.textContent + (on ? 1 : -1));
    try { const r = await ideaCall("/ideas/vote", {}, { id, on }); n.textContent = r.votes; IDV.items.concat(IDV.sim).forEach(x => { if (x.id === id) { x.votes = r.votes; x.voted = r.voted; } }); if (on) { try { D.vibrate && D.vibrate(15); } catch (e) { } } }
    catch (e) { b.setAttribute("aria-pressed", String(!on)); it.classList.toggle("on", !on); n.textContent = Math.max(0, +n.textContent + (on ? -1 : 1)); toast(e.message, 3500); }
    finally { b.disabled = false; }
  });
}
function ideasBind() {
  ideasVoteBind($("#idlist")); ideasDelBind($("#idlist"));
  $$("#ideas-body [data-itab]").forEach(b => b.onclick = () => { IDV.tab = b.dataset.itab; IDV.d = null; ideasRender(); ideasLoad(); });
  if ($("#idmore")) $("#idmore").onclick = () => { IDV.page++; ideasLoad(true); };
  $("#idfind").oninput = () => { clearTimeout(IDV.findT); IDV.findT = setTimeout(() => { IDV.q = $("#idfind").value.trim(); ideasLoad(); }, 350); };
  $("#idq").oninput = () => {
    const q = IDV.draft = $("#idq").value.trim(); $("#idsend").hidden = q.length < 4; $("#idres").textContent = "";
    clearTimeout(IDV.simT); if (q.length < 4) { $("#idsim").innerHTML = ""; return; }
    IDV.simT = setTimeout(async () => {
      let d; try { d = await ideaCall("/ideas/similar", { q }); } catch (e) { return; }
      if (($("#idq") || {}).value === undefined || $("#idq").value.trim() !== q) return;
      IDV.sim = d.items || [];
      $("#idsim").innerHTML = IDV.sim.length ? `<p class="hint" style="margin:10px 2px 6px">Похоже, такая уже есть — поддержите голосом:</p>${IDV.sim.map(ideaItem).join("")}` : "";
      ideasVoteBind($("#idsim"));
      $("#idgo").textContent = IDV.sim.length ? "Моя — другая, предложить" : "Предложить идею"; $("#idgo").classList.toggle("p", !IDV.sim.length);
    }, 400);
  };
  $("#idgo").onclick = async () => {
    const title = $("#idq").value.trim(), text = $("#idbody").value.trim(), r = $("#idres");
    if (title.length < 4) { r.className = "res bad"; r.textContent = "Напишите идею хотя бы в несколько слов."; return; }
    $("#idgo").disabled = true;
    try { const d = await ideaCall("/ideas/new", {}, { title, text, who: S.who || "", app: D.web ? "web" : "phone" });
      IDV.draft = ""; IDV.sim = []; IDV.tab = "mine"; IDV.q = ""; await ideasLoad(); const rr = $("#idres"); if (rr) { rr.className = "res ok"; rr.textContent = d.text || "Спасибо! Идея на рассмотрении."; } }
    catch (e) { r.className = "res bad"; r.textContent = e.message; $("#idgo").disabled = false; }
  };
}
/* голосом (0.61): «предложи идею: …» или «да, предложи» после «этого я пока не умею» — похожая есть: голос за неё; нет — новая */
async function ideaSuggest(title, text) {
  title = String(title || "").replace(/\s+/g, " ").trim().slice(0, 120);
  if (title.length < 4) return "Ошибка: скажи идею хотя бы в несколько слов.";
  try {
    const sim = ((await ideaCall("/ideas/similar", { q: title })).items || []).filter(x => ["plan", "doing", "new", "done"].includes(x.status));
    if (sim.length) { let x = sim[0];
      if (x.status === "done") return `Это уже сделано в версии ${x.ver || "новее"}: «${x.title}». Скажи об этом и предложи обновиться.`;
      if (!x.voted) x = Object.assign({}, x, await ideaCall("/ideas/vote", {}, { id: x.id, on: true }));
      return `Похожая идея уже есть: «${x.title}» — голос за неё отдан (голосов: ${x.votes}). Скажи коротко: такую уже предлагали, проголосовала; все идеи — «Всё» → «Идеи Лиры».`; }
    const d = await ideaCall("/ideas/new", {}, { title, text: String(text || "").slice(0, 2000), who: S.who || S.user_name || "", app: D.web ? "web" : "phone" });
    return `Идея «${d.item.title}» отправлена разработчику — на рассмотрении. Скажи коротко, что предложила; посмотреть — «Всё» → «Идеи Лиры».`;
  } catch (e) { return "Ошибка: идея не отправилась — " + (e.message || e) + ". Скажи об этом коротко."; }
}
function openIdeas() { openSheet("#sh-ideas"); IDV.d = null; ideasRender(); ideasLoad(); }
document.addEventListener("click", (e) => { if (e.target.closest && e.target.closest("#ideas-open")) openIdeas(); });
