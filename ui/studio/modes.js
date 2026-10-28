/* Режимы Лиры (0.58; владелец 28.10: «быстрые режимы — детский, для пожилых и обычный… исходя из режима понятно, что
   для детей и пожилых работа и клиенты не нужны… чтобы это легко делалось, понятно, чётко»).
   «Главная» → «Лира — для меня ▾»: три карточки — «Для меня», «Для ребёнка» (раздел «Дети», нужен PIN), «Для старших»
   (раздел «Для старших»: кто будет говорить, лекарства, кто присматривает; «Включить режим»).
   Ядро: mode_get, mode_set {mode}, senior_set {...}, senior_med_add {text, times}, senior_test, reminders, reminder_cancel
   (core/engine_senior.py, core/senior.py). Событие ядра «mode» — то же, что mode_get. */
const MD = { st: null };
const MD_NAME = { me: "для меня", kid: "для ребёнка", senior: "для старших" };
/* Карточки выбора — первый экран (28.10, владелец: «должно быть как можно красивее… самый первый экран должен нравиться;
   пока однообразно и нечитаемо»): у каждого режима свой мир — картинка на своём небе, обещание одной строкой и три
   коротких пункта вместо абзаца. Рисунки — белые линии на цвете (как значки «Главной», только крупно). */
const MD_CARDS = [
  { id: "me", t: "Для меня", p: "Всё, что умеет Лира, — для вас",
    li: ["Дела, календарь и заметки", "Документы, работа и клиенты", "Музыка, игры и всё остальное"],
    art: `<rect class="f" x="38" y="22" width="96" height="74" rx="12"/><rect x="38" y="22" width="96" height="74" rx="12"/><path d="M38 40h96M58 14v14M114 14v14"/>
      <g class="t"><path d="M52 54h10M70 54h10M88 54h10M106 54h10M52 66h10M70 66h10M88 66h10M52 78h10M70 78h10"/></g>
      <circle class="f2" cx="111" cy="72" r="9"/><circle cx="111" cy="72" r="9"/>
      <rect class="f" x="128" y="54" width="40" height="50" rx="7" transform="rotate(8 148 79)"/><rect x="128" y="54" width="40" height="50" rx="7" transform="rotate(8 148 79)"/>
      <g class="t" transform="rotate(8 148 79)"><path d="M136 66h24M136 74h24M136 82h16"/></g>
      <circle class="dot" cx="164" cy="32" r="3"/><path class="t" d="M164 20v6M164 38v6M152 32h6M170 32h6"/><circle class="dot" cx="26" cy="92" r="2.4"/>` },
  { id: "kid", t: "Для ребёнка", p: "Добрый и безопасный друг",
    li: ["Совёнок Уго — сказки и загадки", "Помогает с уроками, не решая за него", "Время и отчёт — вам, выход по PIN"],
    art: `<path class="f" d="M70 56a30 30 0 0 1 60 0v22c0 18-13.4 28-30 28s-30-10-30-28z"/><path d="M70 56a30 30 0 0 1 60 0v22c0 18-13.4 28-30 28s-30-10-30-28z"/>
      <path d="M74 38 66 20l18 10M126 38l8-18-18 10"/>
      <circle class="f2" cx="87" cy="60" r="11"/><circle cx="87" cy="60" r="11"/><circle class="f2" cx="113" cy="60" r="11"/><circle cx="113" cy="60" r="11"/>
      <circle class="dot" cx="88" cy="61" r="4"/><circle class="dot" cx="114" cy="61" r="4"/><path d="M95 74l5 6 5-6"/>
      <path class="t" d="M80 88c6 6 34 6 40 0M84 96c5 4 27 4 32 0"/>
      <path class="f2" d="M30 30a13 13 0 1 0 15 17 11 11 0 0 1-15-17z"/><path d="M30 30a13 13 0 1 0 15 17 11 11 0 0 1-15-17z"/>
      <path class="t" d="M160 26l2.4 5 5.6.8-4 3.9 1 5.5-5-2.6-5 2.6 1-5.5-4-3.9 5.6-.8zM150 80l1.6 3.4 3.8.5-2.7 2.6.6 3.7-3.3-1.8-3.3 1.8.6-3.7-2.7-2.6 3.8-.5z"/>
      <circle class="dot" cx="172" cy="58" r="2.4"/><circle class="dot" cx="22" cy="86" r="2"/>` },
  { id: "senior", t: "Для старших", p: "Забота о родителях",
    li: ["Крупно, просто, всё голосом", "Лекарства и стоп мошенникам", "Вам вечером — «всё хорошо»"],
    art: `<circle class="f" cx="150" cy="34" r="16"/><circle cx="150" cy="34" r="16"/><path class="t" d="M150 8v6M150 54v6M124 34h6M170 34h6M132 16l4 4M164 48l4 4M168 16l-4 4"/>
      <path class="f" d="M90 106S50 84 50 58a20 20 0 0 1 40-9 20 20 0 0 1 40 9c0 26-40 48-40 48z"/><path d="M90 106S50 84 50 58a20 20 0 0 1 40-9 20 20 0 0 1 40 9c0 26-40 48-40 48z"/>
      <path d="M62 66h12l6-12 9 24 6-12h18"/>
      <rect class="f2" x="140" y="74" width="34" height="14" rx="7" transform="rotate(-30 157 81)"/><rect x="140" y="74" width="34" height="14" rx="7" transform="rotate(-30 157 81)"/>
      <path transform="rotate(-30 157 81)" d="M157 74v14"/>
      <path class="f2" d="M22 74c0-3 2.2-5 5-5h4l3 7-3.4 2.6a20 20 0 0 0 9 9l2.6-3.4 7 3v4c0 2.8-2 5-5 5-12.4 0-22.2-10-22.2-22.2z"/><path d="M22 74c0-3 2.2-5 5-5h4l3 7-3.4 2.6a20 20 0 0 0 9 9l2.6-3.4 7 3v4c0 2.8-2 5-5 5-12.4 0-22.2-10-22.2-22.2z"/>
      <circle class="dot" cx="34" cy="30" r="2.4"/><circle class="dot" cx="184" cy="100" r="2"/>` }];

async function mdLoad() {
  try { MD.st = await core.call("mode_get"); } catch (e) { return; }
  mdChip(); if ($("#p-senior") && $("#p-senior").classList.contains("cur")) srRender();
}
function mdChip() {
  const b = $("#hm-mode"); if (!b || !MD.st) return;
  if (window.hmRender && $("#p-home") && $("#p-home").classList.contains("cur")) try { hmRender(); } catch (e) { }   // плитка «Режимы»: «сейчас: …»
  b.dataset.mode = MD.st.mode; $("span", b).textContent = "Лира — " + (MD_NAME[MD.st.mode] || MD_NAME.me);
  document.documentElement.classList.toggle("md-senior", MD.st.mode === "senior");
}
function mdOpen(first) {
  let d = $("#md-dlg");
  if (!d) { d = document.createElement("dialog"); d.className = "md-dlg"; d.id = "md-dlg"; d.setAttribute("aria-labelledby", "md-t"); document.body.appendChild(d); }
  const cur = (MD.st && MD.st.mode) || "me";
  d.innerHTML = `<div class="md-head"><h2 id="md-t">Для кого эта Лира?</h2>
      <p>Выберите — и Лира сама подстроит вид, голос и то, что умеет. Поменять можно в любой момент.</p></div>
    <div class="md-cards">${MD_CARDS.map(c => `<button type="button" class="md-card" data-m="${c.id}" aria-pressed="${c.id === cur}">
      <span class="md-art"><svg viewBox="0 0 200 120" aria-hidden="true">${c.art}</svg>${c.id === cur ? '<em>сейчас</em>' : ""}</span>
      <span class="md-txt"><b>${c.t}</b><strong>${c.p}</strong><ul>${c.li.map(x => `<li>${x}</li>`).join("")}</ul>
      <span class="md-go">${c.id === cur ? (c.id === "me" ? "Остаться" : "Настроить") : "Выбрать"}</span></span></button>`).join("")}</div>
    <button class="md-x" type="button" data-x aria-label="Закрыть">×</button>`;
  const x = $("[data-x]", d); if (x) x.onclick = () => d.close();
  d.onclick = (e) => { if (e.target === d) d.close(); };                    // нажали мимо карточек — закрыть
  d.onclose = () => { if (first) save({ ui: { mode_seen: 1 } }, true); };    // первый показ — один раз
  $$(".md-card", d).forEach(b => b.onclick = async () => {
    const m = b.dataset.m; d.close();
    if (m === cur) { if (m !== "me") mdGo(m === "kid" ? "kids" : "senior"); return; }
    if (m === "kid") { mdGo("kids"); toast("Задайте имя ребёнка и PIN — и включите режим", 4000); return; }
    if (m === "senior") { mdGo("senior"); return; }
    if (cur === "kid") { mdGo("kids"); toast("Детский режим выключается в «Детях» — с PIN родителя", 4500); return; }
    try { MD.st = await core.call("mode_set", { mode: "me" }); mdChip(); toast("Лира — снова для вас: всё как было", 3500); } catch (e) { toast(e.message, 4000); }
  });
  d.showModal();
  setTimeout(() => { const f = $(".md-card", d); if (f) f.focus(); }, 30);
}
function mdGo(p) { const b = $(`nav button[data-p="${p}"]`); if (b) b.click(); }

/* ---------- раздел «Для старших» ---------- */
let srMeds = [];
async function srLoad() {
  try { MD.st = await core.call("mode_get"); } catch (e) { return; }
  try { srMeds = ((await core.call("reminders")) || []).filter(x => x.care && !x.care_n); } catch (e) { srMeds = []; }
  mdChip(); srRender();
}
const srT = (ts) => new Date(ts * 1000).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
function srRender() {
  const st = MD.st || {}, c = st.senior || {}, on = st.mode === "senior", kid = st.mode === "kid";
  const who = (c.name || "").trim();
  $("#sr-bar").className = "sr-bar" + (on ? " on" : "");
  $("#sr-bar").innerHTML = on
    ? `<div><b>Режим «Для старших» включён${who ? " — " + escH(who) : ""}</b><span>Крупно, просто и всё голосом. Вернуть обычный вид — одной кнопкой.</span></div><button class="btn" type="button" id="sr-off">Вернуть обычный режим</button>`
    : `<div><b>${kid ? "Сейчас включён детский режим" : "Режим выключен"}</b><span>${kid ? "Сначала выключите его в «Детях» — с PIN родителя." : "Заполните, кто будет говорить и кто присматривает, — и включите. Всё, что было, вернётся одной кнопкой."}</span></div>
       <button class="btn primary" type="button" id="sr-on"${kid ? " disabled" : ""}>Включить режим</button>`;
  if ($("#sr-on")) $("#sr-on").onclick = async () => {
    try { await srSaveName(); MD.st = await core.call("mode_set", { mode: "senior" }); srRender(); mdChip(); toast("Готово: Лира стала проще и крупнее", 3500); } catch (e) { toast(e.message, 4000); } };
  if ($("#sr-off")) $("#sr-off").onclick = async () => {
    try { MD.st = await core.call("mode_set", { mode: "me" }); srRender(); mdChip(); toast("Вернула обычный режим — всё как было", 3500); } catch (e) { toast(e.message, 4000); } };
  const nm = $("#sr-name"); if (document.activeElement !== nm) nm.value = c.name || "";
  $$(".sr-seg [data-g]").forEach(b => { const v = b.dataset.g === (c.gender || "f"); b.classList.toggle("on", v); b.setAttribute("aria-checked", v); });
  if (document.activeElement !== $("#sr-eve")) $("#sr-eve").value = c.checkin || "20:00";
  $("#sr-noon").checked = c.noon !== false; $("#sr-scam").checked = c.scam !== false;
  const W = new Set(c.watchers || []), people = st.people || [];
  $("#sr-who").innerHTML = people.length ? people.map(p => `<label class="sr-p"><input type="checkbox" data-pid="${escH(p.pid)}"${W.has(p.pid) ? " checked" : ""}>
      <b>${escH(p.name)}</b><small>${p.ready ? "получит сообщения" : "ещё не открывал Dewiar после приглашения"}</small></label>`).join("")
    : `<p class="hint" style="margin:0">В «Близких» пока никого. Пригласите сына или дочь — им будут приходить сообщения. <button class="linkbtn" type="button" data-goto="close">Открыть «Близкие»</button></p>`;
  $$("#sr-who input[data-pid]").forEach(i => i.onchange = () => core.call("senior_set", { watchers: $$("#sr-who input[data-pid]:checked").map(x => x.dataset.pid) })
    .then(r => { MD.st = r; }).catch(e => toast(e.message)));
  $("#sr-meds").innerHTML = srMeds.length ? srMeds.map(m => `<div class="sr-med"><b>${escH(m.at_hm || "")}</b><span>${escH(m.text)}</span><small>${escH(m.repeat_text || "")}</small>
      <button class="btn small" type="button" data-rm="${escH(m.id)}" title="Больше не напоминать">Убрать</button></div>`).join("")
    : `<p class="hint" style="margin:0">Пока ничего. Добавьте, что и во сколько принимать, — или скажите Лире: «напоминай пить таблетку от давления в девять утра».</p>`;
  $$("#sr-meds [data-rm]").forEach(b => b.onclick = async () => { try { await core.call("reminder_cancel", { id: b.dataset.rm }); srLoad(); } catch (e) { toast(e.message); } });
  const t = (c.today || {}), talk = t.talk || [], meds = t.meds || [], al = t.alerts || [];
  const W2 = { taken: ["выпито", "ok"], missed: ["нет ответа", "bad"], snooze: ["отложено", ""], again: ["спросит ещё раз", ""] };
  $("#sr-today").innerHTML = (talk.length ? `<p class="sr-line ok">Говорили с Лирой${talk[0] === talk[1] ? " в " + srT(talk[0]) : ` — с ${srT(talk[0])} до ${srT(talk[1])}`}</p>`
      : `<p class="sr-line">Сегодня ещё не говорили</p>`)
    + meds.map(m => `<p class="sr-line ${(W2[m.res] || [])[1] || ""}">${escH(m.at || "")} · ${escH(m.text)} — ${(W2[m.res] || ["?"])[0]}</p>`).join("")
    + al.map(a => `<p class="sr-line bad">${srT(a.ts)} · похоже на мошенников: «${escH(String(a.text).slice(0, 80))}»</p>`).join("");
}
async function srSaveName() {
  const r = await core.call("senior_set", { name: $("#sr-name").value.trim() }); MD.st = r; return r;
}
$("#sr-name").onchange = () => srSaveName().catch(e => toast(e.message));
$$(".sr-seg [data-g]").forEach(b => b.onclick = () => core.call("senior_set", { gender: b.dataset.g }).then(r => { MD.st = r; srRender(); }).catch(e => toast(e.message)));
$("#sr-eve").onchange = () => core.call("senior_set", { checkin: $("#sr-eve").value || "20:00" }).then(r => { MD.st = r; }).catch(e => toast(e.message));
$("#sr-noon").onchange = () => core.call("senior_set", { noon: $("#sr-noon").checked }).catch(e => toast(e.message));
$("#sr-scam").onchange = () => core.call("senior_set", { scam: $("#sr-scam").checked }).catch(e => toast(e.message));
$("#sr-madd").onclick = async () => {
  const text = $("#sr-mtext").value.trim(), times = $("#sr-mtimes").value.split(/[,;\s]+/).map(x => x.trim()).filter(Boolean);
  if (!text) { toast("Напишите, что принять"); $("#sr-mtext").focus(); return; }
  if (!times.length) { toast("Напишите время, например 09:00"); $("#sr-mtimes").focus(); return; }
  try { await core.call("senior_med_add", { text, times }); $("#sr-mtext").value = ""; $("#sr-mtimes").value = ""; toast("Добавлено — Лира напомнит и спросит «выпили?»", 3500); srLoad(); }
  catch (e) { toast(e.message, 4000); }
};
$("#sr-test").onclick = async () => {
  const r = $("#sr-tres"); r.className = "res"; r.textContent = "отправляю…";
  try { const x = await core.call("senior_test"); r.className = "res ok"; r.textContent = `Отправлено: ${x.sent}`; } catch (e) { r.className = "res bad"; r.textContent = e.message; }
};
$("#hm-mode").onclick = () => mdOpen(false);
document.addEventListener("click", (e) => {
  if (!e.target.closest) return;
  if (e.target.closest('nav button[data-p="senior"]')) setTimeout(srLoad, 0);
  if (e.target.closest('nav button[data-p="home"]')) setTimeout(mdLoad, 0);      // детский режим включили в «Детях» — на «Главной» видно
});
if (window.core && core.on) core.on("mode", (st) => { MD.st = st; mdChip(); if ($("#p-senior").classList.contains("cur")) srRender(); });
/* Первый экран: новый человек (знакомство ещё не прошло, ui.mode_seen нет — ядро говорит first) — выбор режима сам, один раз */
setTimeout(async () => { await mdLoad();
  try { if (MD.st && MD.st.first && $("#p-home").classList.contains("cur") && !document.querySelector("dialog[open]")) mdOpen(true); } catch (e) { } }, 900);
