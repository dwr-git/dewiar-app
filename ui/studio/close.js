/* Студия → «Близкие» (core/close.py): список близких, переписка, приглашение QR-кодом и ссылкой, принять ссылку.
   Данные — core.call("close_*"); новое приходит событиями close (состояние) и close_msg (входящее). Точка у пункта
   меню — есть непрочитанные. Отправка файла: файл из окна читается здесь и уходит base64 (files_b64), ядро шифрует его. */
const CL = { st: null, cur: "", hist: [], files: [], pick: null };          // pick — отмеченные mid в режиме «Выбрать», null — режим выключен
const clEsc = (t) => String(t == null ? "" : t).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const CL_COLORS = ["#9BD4FF", "#FFB547", "#3DF5C8", "#FF7AB6", "#B78CFF", "#9BE15D", "#7C8CFF", "#FF6B5A"];
const clColor = (pid) => CL_COLORS[[...String(pid)].reduce((a, c) => a + c.charCodeAt(0), 0) % CL_COLORS.length];
const clTime = (ts) => { const d = new Date(ts), now = new Date(); const hm = d.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
  return d.toDateString() === now.toDateString() ? hm : d.toLocaleDateString("ru-RU", { day: "numeric", month: "short" }) + ", " + hm; };
const clSize = (n) => n > 1048576 ? (n / 1048576).toFixed(1).replace(".", ",") + " МБ" : Math.max(1, Math.round(n / 1024)) + " КБ";

function clDot(st) {
  const n = ((st && st.people) || []).reduce((a, p) => a + (p.unread || 0), 0) + ((st && st.offers) || []).length;   // и «зовут в Близкие»
  $("#close-dot").classList.toggle("on", n > 0);
}
async function loadClose(hello) {
  try { CL.st = await core.call("close_state", { hello: !!hello }); }
  catch (e) { $("#cl-res").className = "res bad"; $("#cl-res").textContent = e.message; return; }
  clRender();
  const u = ((CL.st && CL.st.people) || []).find(p => p.unread);       // открыли раздел (или строку «💌» в виджете) — к непрочитанному
  if (u && u.pid !== CL.cur && !CL.pick) clOpen(u.pid);
}
function clRender() {
  const st = CL.st || { people: [] }, people = st.people || [];
  clDot(st);
  clMe(st.me || {});
  $("#cl-speak").checked = !(S && S.close && S.close.speak === false);
  const r = $("#cl-res");
  if (st.error) { r.className = "res bad"; r.textContent = st.error; } else if (r.classList.contains("bad")) { r.className = "res"; r.textContent = ""; }
  $("#cl-people").innerHTML = people.length ? people.map(p => `<button class="cl-p ${p.pid === CL.cur ? "cur" : ""}" data-pid="${clEsc(p.pid)}">
      <i class="cl-ava" style="--c:${clColor(p.pid)}" data-face="${clEsc(p.pid)}" data-v="${+p.face || 0}">${clEsc((p.name || "?").slice(0, 1).toUpperCase())}</i>
      <span><b>${clEsc(p.name)}</b><small>${p.last && (p.last.t || (p.last.f || []).length) ? clEsc((p.last.out ? "Вы: " : "") + (p.last.t || "📎 " + ((p.last.f[0] || {}).name || "файл"))) : "пока без сообщений"}</small></span>
      ${p.unread ? `<em>${p.unread}</em>` : ""}</button>`).join("")
    : `<p class="hint" style="margin:6px 2px 12px">Пока никого. Пригласите тех, с кем хотите переписываться через помощников.</p>`;
  $$("#cl-people .cl-p").forEach(b => b.onclick = () => clOpen(b.dataset.pid));
  clFaces($("#cl-people"));
  clOffers(st.offers || []);
  if (CL.cur && !people.some(p => p.pid === CL.cur)) CL.cur = "";
  if (!CL.cur && people.length && !$("#cl-invite").offsetParent) clOpen((people.find(p => p.unread) || people[0]).pid);   // пришли по строке «💌» виджета — сразу та переписка
  else clHead();
}
/* Зовут в «Близкие» из «Рефералов» (тот, кто пригласил вас в Dewiar, или кого пригласили вы) — согласие здесь */
function clOffers(list) {
  $("#cl-offers").innerHTML = list.map(o => `<div class="cl-of"><b>${clEsc(o.name)} зовёт вас в «Близкие»</b>
      <span>Вы связаны приглашением в Dewiar. Согласитесь — помощники смогут передавать друг другу сообщения, можно будет созваниваться.</span>
      <div class="actions" style="margin:8px 0 0"><button class="btn primary small" data-y="${clEsc(o.pid)}">Принять</button><button class="btn small" data-n="${clEsc(o.pid)}">Не сейчас</button></div></div>`).join("");
  $$("#cl-offers [data-y], #cl-offers [data-n]").forEach(b => b.onclick = async () => {
    const pid = b.dataset.y || b.dataset.n, yes = !!b.dataset.y; b.disabled = true;
    try { CL.st = await core.call("close_offer", { pid, yes }); clRender();
      if (yes) { const p = (CL.st.people || []).find(x => x.pid === pid); if (p) { toast(`${p.name} теперь в ваших близких`); clOpen(pid); } } }
    catch (e) { b.disabled = false; toast(e.message, 4000); }
  });
}
function clHead() {
  const p = ((CL.st && CL.st.people) || []).find(x => x.pid === CL.cur);
  $("#cl-empty").style.display = p ? "none" : ""; $("#cl-head").style.display = p ? "" : "none"; $("#cl-send").style.display = p && !CL.pick ? "" : "none";
  if (!p) { $("#cl-msgs").innerHTML = ""; return; }
  clAva($("#cl-ava"), p.pid, p.name, p.face);
  $("#cl-who").textContent = p.name;
  $("#cl-devs").textContent = (p.about ? p.about + " · " : "") + ((p.devs || []).length ? "устройств: " + p.devs.length + " · сообщения шифруются" : "ещё не открывал Dewiar после приглашения");
  $("#cl-devs").title = p.about || "";
  $("#cl-call").style.display = $("#cl-vcall").style.display = (p.devs || []).length ? "" : "none";
  $("#cl-pick").textContent = CL.pick ? "Готово" : "Удалить сообщения";
}
async function clOpen(pid) {
  if (CL.cur !== pid) clPickOff();
  CL.cur = pid; $("#cl-invite").style.display = "none"; clCardShow(false);
  $$("#cl-people .cl-p").forEach(b => b.classList.toggle("cur", b.dataset.pid === pid));
  clHead();
  try { CL.hist = await core.call("close_history", { pid, read: !document.hidden }); } catch (e) { CL.hist = []; }
  clMsgs();
}
/* «Отправлено» ✓, «Доставлено» ✓✓, «Прочитано» ✓✓ цветом (24.10, владелец: «не понятно, прочитал ли человек сообщение,
   дошло ли оно»). sid — номер письма в ящике близкого; marks — до какого номера его Dewiar забрал и открыл переписку. */
const CL_TICK = { sent: ["Отправлено — его Dewiar ещё не забирал почту", "M5 12.5l4 4 9-9"],
  dlv: ["Доставлено — ещё не прочитано", "M2.5 12.5l4 4 9-9M10.5 15.5l1 1 9-9"],
  read: ["Прочитано", "M2.5 12.5l4 4 9-9M10.5 15.5l1 1 9-9"] };
function clMark(m) {
  if (!m.out || !m.sid) return "";
  const p = ((CL.st && CL.st.people) || []).find(x => x.pid === CL.cur) || {}, mk = p.marks || [0, 0];
  return mk[1] >= m.sid ? "read" : mk[0] >= m.sid ? "dlv" : "sent";
}
const clTick = (m) => { const k = clMark(m); return k ? `<i class="cl-ck ${k}" title="${CL_TICK[k][0]}" aria-label="${CL_TICK[k][0]}"><svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="${CL_TICK[k][1]}"/></svg></i>` : ""; };
function clTicks() {                          // отметки сменились — только галочки, без перерисовки (не сбивать прокрутку)
  $$("#cl-msgs .cl-m.out").forEach(el => { const m = CL.hist[+el.dataset.i], t = $(".cl-ck", el); if (!m || !t) return;
    const k = clMark(m); if (k && !t.classList.contains(k)) t.outerHTML = clTick(m); });
}
/* эмодзи и реакции (отзыв 13.10): ряд над полем ввода — вставить; у сообщения — «☺» (и правая кнопка): реакция, та же — снять.
   Реакция уходит сообщением {re, e} (core/close.py react), у старых программ покажется просто «👍». */
const CL_EMO = ["👍", "🤝", "✋", "😁", "😊", "😂", "😳", "🤔", "😱", "❤️"];
/* Больше смайлов (24.10, владелец: «в раздел Близкие нужно больше смайлов»): вкладки по темам, первая — частые (они же
   реакции). Только эмодзи, которые есть и на старых телефонах и в Windows 10 (без новинок Unicode 14+). */
const CL_EMO_SETS = [["Частые", CL_EMO],
  ["Смайлы", ["😀", "😃", "😄", "😅", "🤣", "🙂", "😉", "😍", "🥰", "😘", "😋", "😎", "🤩", "🥳", "😌", "😏", "🤗", "🤭", "😇", "🙃", "😴", "🙄", "😬", "😮", "🤯", "😢", "😭", "🥺", "😤", "😡", "🥶", "🥵", "🤒", "🤧", "😷", "🤐"]],
  ["Жесты", ["👋", "👌", "✌️", "🤞", "🤙", "👏", "🙌", "🙏", "💪", "👎", "👉", "☝️", "🤷", "🤦", "🙈", "🙉", "🙊", "💃", "🕺", "👀"]],
  ["Сердца", ["🧡", "💛", "💚", "💙", "💜", "🖤", "🤍", "💔", "💕", "💖", "💘", "💋", "✨", "🔥", "⭐", "🌟", "💯", "🎉", "🎊", "🥂"]],
  ["Природа", ["☀️", "🌤️", "🌧️", "⛈️", "❄️", "🌈", "🌙", "🌸", "🌹", "🌷", "🌻", "🌿", "🍀", "🍁", "🐱", "🐶", "🐻", "🐰", "🦊", "🐼", "🐸", "🐝", "🦋", "🐟"]],
  ["Еда", ["☕", "🍵", "🍰", "🎂", "🍫", "🍪", "🍎", "🍓", "🍉", "🍌", "🍕", "🍔", "🍟", "🍝", "🥗", "🍲", "🥞", "🍷", "🍺", "🥤"]],
  ["Дела", ["🏠", "🚗", "🚕", "✈️", "🚆", "🏖️", "⚽", "🏃", "🎵", "🎮", "🎁", "📞", "📷", "💻", "📚", "📌", "💡", "⏰", "💤", "✅", "❌", "❓", "⚠️", "💰"]]];
let clEmoTab = 0;
function clEmoDraw() {
  const r = $("#cl-emo");
  r.innerHTML = `<div class="cl-emo-tabs" role="tablist">${CL_EMO_SETS.map(([n, l], i) => `<button role="tab" data-t="${i}" aria-selected="${i === clEmoTab}" title="${n}">${l[0]}<span>${n}</span></button>`).join("")}</div>`
    + `<div class="cl-emo-g" role="tabpanel">${CL_EMO_SETS[clEmoTab][1].map(e => `<button data-e="${e}" title="Вставить ${e}">${e}</button>`).join("")}</div>`;
  $$("#cl-emo [data-t]").forEach(b => b.onclick = () => { clEmoTab = +b.dataset.t; clEmoDraw(); });
  $$("#cl-emo button[data-e]").forEach(b => b.onclick = () => {            // вставить в текст там, где курсор
    const ta = $("#cl-text"), x = ta.selectionStart ?? ta.value.length, z = ta.selectionEnd ?? x;
    ta.value = ta.value.slice(0, x) + b.dataset.e + ta.value.slice(z); ta.selectionStart = ta.selectionEnd = x + b.dataset.e.length; ta.focus(); });
}
const clEmoOnly = (t) => !!t && t.length <= 12 && /^(?:\p{Extended_Pictographic}|\u200d|\ufe0f|\s)+$/u.test(t);
function clReClose() { $$(".cl-repick").forEach(x => x.remove()); }
function clRePick(el, m) {
  clReClose();
  const pop = document.createElement("div"); pop.className = "cl-repick"; pop.setAttribute("role", "menu");
  // реакции и «Удалить у меня» (отзыв 17.10: «в близких не вижу удаления сообщений») — как долгое нажатие на телефоне
  pop.innerHTML = CL_EMO.map(e => `<button role="menuitem" data-e="${e}" class="${(m.rx || {}).me === e ? "on" : ""}" title="Реакция ${e}">${e}</button>`).join("")
    + `<i class="cl-resep" aria-hidden="true"></i><button role="menuitem" class="cl-redel" title="Удалить у меня — у близкого сообщение останется" aria-label="Удалить у меня"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4.5 7h15M9.5 7V5a1 1 0 0 1 1-1h3a1 1 0 0 1 1 1v2M6.5 7l1 12.5a1.5 1.5 0 0 0 1.5 1.4h6a1.5 1.5 0 0 0 1.5-1.4L17.5 7"/></svg></button>`;
  document.body.appendChild(pop);
  const r = el.getBoundingClientRect(), w = pop.offsetWidth;
  pop.style.left = Math.max(8, Math.min(innerWidth - w - 8, m.out ? r.right - w : r.left)) + "px";
  pop.style.top = Math.max(8, r.top - pop.offsetHeight - 6) + "px";
  $(".cl-redel", pop).onclick = async () => {
    clReClose();
    try { const r = await core.call("close_forget", { pid: CL.cur, mids: [m.mid] }); CL.st = r.state || CL.st;
      CL.hist = await core.call("close_history", { pid: CL.cur }); clMsgs(); clRender(); toast("Удалено у вас — у близкого сообщение осталось", 2600); }
    catch (x) { toast(x.message, 4000); }
  };
  $$("button[data-e]", pop).forEach(b => b.onclick = async () => {
    const e = (m.rx || {}).me === b.dataset.e ? "" : b.dataset.e; clReClose();
    try { await core.call("close_react", { pid: CL.cur, mid: m.mid, e }); CL.hist = await core.call("close_history", { pid: CL.cur }); clMsgs(); }
    catch (x) { toast(x.message, 4000); }
  });
  setTimeout(() => document.addEventListener("pointerdown", function out(ev) { if (!ev.target.closest(".cl-repick")) { clReClose(); document.removeEventListener("pointerdown", out, true); } }, true), 0);
}
function clMsgs() {
  const box = $("#cl-msgs");
  box.innerHTML = CL.hist.map((m, i) => `<div class="cl-m ${m.out ? "out" : ""}${m.rx && (m.rx.me || m.rx.them) ? " rx" : ""}${clEmoOnly(m.t) ? " emo" : ""}" data-i="${i}">${m.t ? `<div class="tx">${clEsc(m.t)}</div>` : ""}
      ${(m.f || []).map(f => `<button class="cl-f" data-path="${clEsc(f.path || "")}" ${f.path ? "" : "disabled"}><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M6 3.5h8.5L19 8v12.5H6z"/><path d="M14 3.5V8h5"/></svg><span>${clEsc(f.name)}</span><small>${f.error ? "не скачался" : clSize(f.size || 0)}</small></button>`).join("")}
      <time>${clTime(m.ts)}${clTick(m)}</time>${m.rx && (m.rx.me || m.rx.them) ? `<span class="cl-rx">${clEsc([m.rx.them, m.rx.me].filter(Boolean).join(""))}</span>` : ""}
      ${m.mid ? `<button class="cl-reb" title="Реакция" aria-label="Реакция"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><circle cx="12" cy="12" r="8.5"/><path d="M8.5 14a4.2 4.2 0 0 0 7 0M9 9.6v.01M15 9.6v.01"/></svg></button>` : ""}</div>`).join("") || `<p class="hint" style="text-align:center;margin:30px 0">Напишите первое сообщение — или скажите помощнице: «Напиши ${clEsc((((CL.st || {}).people || []).find(x => x.pid === CL.cur) || {}).name || "")}, …»</p>`;
  $$("#cl-msgs .cl-f[data-path]").forEach(b => b.onclick = () => {
    const path = b.dataset.path, i = path.indexOf("/Близкие/"), rel = i >= 0 ? path.slice(path.lastIndexOf("Близкие/")) : "";
    if (rel) core.call("ws_open", { path: rel }).catch(e => toast(e.message));
  });
  if (CL.pick) { clPickWire(); return; }
  $$("#cl-msgs .cl-m").forEach(el => {
    const m = CL.hist[+el.dataset.i]; if (!m || !m.mid) return;
    const rb = $(".cl-reb", el); if (rb) rb.onclick = (e) => { e.stopPropagation(); clRePick(el, m); };
    el.addEventListener("contextmenu", (e) => { if (getSelection().toString()) return; e.preventDefault(); clRePick(el, m); });
  });
  box.scrollTop = box.scrollHeight;
}
/* «Выбрать» (отзыв 17.10: «очистить диалоги с близкими нельзя, или выборочно поудалять лишнее»): нажатием отмечают
   сообщения, «Удалить у меня» убирает их из переписки на этом компьютере (core/close.py forget). У близкого и на ваших
   других устройствах переписка остаётся — так и написано в подтверждении. «Отметить все» — очистить всю переписку. */
function clPickOn() {
  if (!CL.cur) return;
  CL.pick = new Set(); clReClose();
  $("#cl-chat").classList.add("picking"); $("#cl-selbar").hidden = false; $("#cl-send").style.display = "none"; $("#cl-emo").hidden = true;
  clMsgs(); clPickCount();
}
function clPickOff() {
  if (!CL.pick) return;
  CL.pick = null; $("#cl-chat").classList.remove("picking"); $("#cl-selbar").hidden = true;
  if (CL.cur) $("#cl-send").style.display = "";
  clMsgs();
}
function clPickCount() {
  const n = CL.pick ? CL.pick.size : 0, all = CL.hist.filter(m => m.mid).length;
  $("#cl-selnum").textContent = n ? `Отмечено: ${n}` : "Нажмите на сообщения, которые убрать";
  $("#cl-seldel").disabled = !n;
  $("#cl-seldel").textContent = n && n === all ? "Очистить переписку" : "Удалить у меня";
  $("#cl-selall").textContent = n && n === all ? "Снять отметки" : "Отметить все";
}
function clPickWire() {
  $$("#cl-msgs .cl-m").forEach(el => {
    const m = CL.hist[+el.dataset.i]; if (!m || !m.mid) return;
    el.tabIndex = 0; el.setAttribute("role", "checkbox");
    const set = () => { const on = CL.pick.has(m.mid); el.classList.toggle("sel", on); el.setAttribute("aria-checked", String(on)); };
    const flip = () => { if (CL.pick.has(m.mid)) CL.pick.delete(m.mid); else CL.pick.add(m.mid); set(); clPickCount(); };
    set();
    el.onclick = (e) => { e.preventDefault(); flip(); };
    el.onkeydown = (e) => { if (e.key === " " || e.key === "Enter") { e.preventDefault(); flip(); } };
  });
}
async function clPickDel() {
  const p = ((CL.st && CL.st.people) || []).find(x => x.pid === CL.cur); if (!p || !CL.pick || !CL.pick.size) return;
  const all = CL.pick.size === CL.hist.filter(m => m.mid).length, n = CL.pick.size;
  const what = all ? `всю переписку с «${p.name}»` : `${n} ${n % 10 === 1 && n % 100 !== 11 ? "сообщение" : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 12 || n % 100 > 14) ? "сообщения" : "сообщений"}`;
  if (!await ask(`Удалить ${what} на этом компьютере? У ${p.name} и на ваших других устройствах переписка останется.`)) return;
  try {
    const r = await core.call("close_forget", all ? { pid: p.pid } : { pid: p.pid, mids: [...CL.pick] });
    CL.st = r.state || CL.st; CL.hist = await core.call("close_history", { pid: p.pid });
    clPickOff(); clRender(); toast(all ? "Переписка очищена" : "Удалено");
  } catch (e) { toast(e.message, 4000); }
}
$("#cl-pick").onclick = () => { if (CL.pick) clPickOff(); else clPickOn(); clHead(); };
$("#cl-selx").onclick = () => { clPickOff(); clHead(); };
$("#cl-seldel").onclick = clPickDel;
$("#cl-selall").onclick = () => { const ids = CL.hist.filter(m => m.mid).map(m => m.mid);
  CL.pick = new Set(CL.pick && CL.pick.size === ids.length ? [] : ids); clPickWire(); clPickCount(); };
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && CL.pick && $("#p-close").classList.contains("cur")) clPickOff(); });
async function clSend() {
  const text = $("#cl-text").value.trim(), pid = CL.cur;
  if (!pid || (!text && !CL.files.length)) return;
  const b = $("#cl-go"); b.disabled = true;
  try {
    await core.call("close_send", { pid, text, files_b64: CL.files });
    $("#cl-text").value = ""; CL.files = []; clFiles();
    CL.hist = await core.call("close_history", { pid }); clMsgs();
  } catch (e) { toast(e.message, 4000); }
  b.disabled = false; $("#cl-text").focus();
}
function clFiles() {
  $("#cl-files").innerHTML = CL.files.map((f, i) => `<span>${clEsc(f.name)} <button data-i="${i}" title="Убрать">✕</button></span>`).join("");
  $$("#cl-files button").forEach(x => x.onclick = () => { CL.files.splice(+x.dataset.i, 1); clFiles(); });
}
async function clInvite(renew) {
  clCardShow(false);
  const r = $("#cl-res");
  try {
    const d = await core.call("close_invite", { renew: !!renew });
    const code = String(d.link || "").split("&from=")[0];        // в коде — короткая ссылка (без имени)
    const seal = window.DewiarCodes ? DewiarCodes.seal(code) : "";
    $("#cl-invite").style.display = ""; $("#cl-qr").innerHTML = seal || qrSvg(code); $("#cl-qr").classList.toggle("seal", !!seal); $("#cl-inv-link").textContent = d.link;
    $("#cl-inv-qr").textContent = seal ? "Показать обычный QR" : "";
    $("#cl-inv-qr").onclick = (e) => { e.preventDefault(); const isSeal = $("#cl-qr").classList.contains("seal");
      $("#cl-qr").innerHTML = isSeal ? qrSvg(code) : seal; $("#cl-qr").classList.toggle("seal", !isSeal); $("#cl-inv-qr").textContent = isSeal ? "Показать печать Dewiar" : "Показать обычный QR"; };
    $("#cl-inv-copy").onclick = () => navigator.clipboard.writeText(`Добавь меня в «Близкие» в Dewiar — наши помощники смогут передавать друг другу сообщения: ${d.link}`)
      .then(() => toast("Ссылка скопирована"), () => toast(d.link));
    r.className = "res"; r.textContent = "";
  } catch (e) { r.className = "res bad"; r.textContent = e.message; }
}
async function clAccept() {
  const link = $("#cl-link").value.trim(), r = $("#cl-res");
  if (!link) return;
  r.className = "res"; r.textContent = "проверяю приглашение…";
  try {
    const who = await core.call("close_peek", { link });
    if (!await ask(`Принять приглашение в «Близкие» от «${who.name}»? Ваши помощники смогут передавать друг другу сообщения.`)) { r.textContent = ""; return; }
    const p = await core.call("close_accept", { link });
    $("#cl-link").value = ""; r.className = "res ok"; r.textContent = `Готово — ${p.name || who.name} в ваших близких.`;
    await loadClose(); if (p.pid) clOpen(p.pid);
  } catch (e) { r.className = "res bad"; r.textContent = e.message; }
}

$("#cl-go").onclick = clSend;
/* окно студии снова на виду, открыта переписка — письма, пришедшие пока его не было видно, теперь прочитаны */
document.addEventListener("visibilitychange", () => { if (!document.hidden && CL.cur && $("#p-close").classList.contains("cur")) core.call("close_history", { pid: CL.cur }).catch(() => { }); });
$("#cl-emo-b").onclick = () => { const r = $("#cl-emo"); r.hidden = !r.hidden; $("#cl-emo-b").setAttribute("aria-expanded", String(!r.hidden)); };
clEmoDraw();
$("#cl-text").onkeydown = (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); clSend(); } };
$("#cl-file").onchange = () => {
  [...$("#cl-file").files].forEach(f => {
    if (f.size > 10 * 1024 * 1024) { toast(`«${f.name}» больше 10 МБ`); return; }
    const fr = new FileReader(); fr.onload = () => { CL.files.push({ name: f.name, b64: String(fr.result).split(",")[1] || "" }); clFiles(); }; fr.readAsDataURL(f);
  });
  $("#cl-file").value = "";
};
$("#cl-inv-go").onclick = () => clInvite(false);
$("#cl-inv-new").onclick = async () => { if (await ask("Сделать новую ссылку? Старая перестанет действовать — те, кто уже добавился, останутся в близких.")) clInvite(true); };
$("#cl-inv-x").onclick = () => { $("#cl-invite").style.display = "none"; clHead(); };
$("#cl-link-go").onclick = clAccept;
/* ---------- карточка «Я» (0.45, владелец: «возможность загрузить своё фото… которое увидят близкие и на встречах… фото, имя
   и может ещё что»). Фото сжимается здесь до 256×256 JPEG; хранится на dewiar.pro как аватар — видят близкие и, если
   включено, люди рядом во «Встречах». Фото других — core.call("close_face") с кэшем по номеру версии. ---------- */
CL.faces = {};
function clFaceGet(pid, v, meet) {
  const k = (meet ? "m" : "p") + pid + ":" + v;
  if (!CL.faces[k]) CL.faces[k] = core.call("close_face", { pid, v, meet: !!meet }).then(r => r.data || "").catch(() => "");
  return CL.faces[k];
}
function clAva(el, pid, name, face, meet) {
  if (!el) return;
  el.style.setProperty("--c", clColor(pid)); el.dataset.face = pid; el.dataset.v = +face || 0;
  if (!el.classList.contains("has-face") || !+face) { el.textContent = (name || "?").slice(0, 1).toUpperCase(); }
  if (!+face) { el.classList.remove("has-face"); el.style.backgroundImage = ""; return; }
  clFaceGet(pid, face, meet).then(d => { if (el.dataset.v !== String(+face)) return;
    if (d) { el.classList.add("has-face"); el.style.backgroundImage = `url("${d}")`; el.textContent = ""; } });
}
function clFaces(root, meet) { $$("[data-face]", root).forEach(el => clAva(el, el.dataset.face, el.textContent, el.dataset.v, meet)); }
function clMe(me) {
  const nm = me.name && me.name !== "Без имени" ? me.name : "";
  $("#cl-me-name").textContent = nm || "Ваше имя"; $("#cl-me-name").classList.toggle("ph", !nm);
  $("#cl-me-about").textContent = me.about || (me.face ? "" : "добавьте фото и пару слов о себе");
  clAva($("#cl-me-ava"), me.pid || "me", nm || "?", me.face);
  if ($("#cl-card").hidden) return;
  if (CL.cardFace === undefined) clAva($("#cl-card-ava"), me.pid || "me", nm || "?", me.face);
}
function clCardShow(on) {
  const c = $("#cl-card"); if (c.hidden === !on) return;
  c.hidden = !on; $("#cl-chat").style.display = on ? "none" : ""; $("#cl-me").setAttribute("aria-expanded", String(on));
  if (!on) { CL.cardFace = undefined; return; }
  $("#cl-invite").style.display = "none";
  const me = (CL.st && CL.st.me) || {};
  CL.cardFace = undefined;
  $("#cl-myname").value = me.name && me.name !== "Без имени" ? me.name : ""; $("#cl-about").value = me.about || "";
  $("#cl-about-n").textContent = $("#cl-about").value.length + " / 160";
  $("#cl-face-meet").checked = !!me.face_meet; $("#cl-card-res").textContent = ""; $("#cl-card-res").className = "res";
  $("#cl-card-ava").classList.remove("has-face"); $("#cl-card-ava").style.backgroundImage = "";
  clAva($("#cl-card-ava"), me.pid || "me", $("#cl-myname").value || "?", me.face);
  $("#cl-face-del").disabled = !me.face;
  $("#cl-myname").focus();
}
/* фото -> квадрат 256×256 из середины, JPEG ~85 % (≈ 20–40 КБ) */
async function clFacePrep(file) {
  if (!file || !/^image\//.test(file.type)) throw new Error("Это не картинка — выберите фото (JPEG, PNG…)");
  if (file.size > 20 * 1024 * 1024) throw new Error("Фото больше 20 МБ — выберите поменьше");
  const url = URL.createObjectURL(file);
  try {
    const img = await new Promise((ok, bad) => { const i = new Image(); i.onload = () => ok(i); i.onerror = () => bad(new Error("Фото не открылось — попробуйте другое")); i.src = url; });
    const s = Math.min(img.naturalWidth, img.naturalHeight), cv = document.createElement("canvas"); cv.width = cv.height = 256;
    const g = cv.getContext("2d"); g.imageSmoothingQuality = "high";
    g.drawImage(img, (img.naturalWidth - s) / 2, (img.naturalHeight - s) / 2, s, s, 0, 0, 256, 256);
    return cv.toDataURL("image/jpeg", 0.85);
  } finally { URL.revokeObjectURL(url); }
}
async function clFaceTake(file) {
  try {
    const d = await clFacePrep(file); CL.cardFace = d;
    const a = $("#cl-card-ava"); a.classList.add("has-face"); a.style.backgroundImage = `url("${d}")`; a.textContent = ""; $("#cl-face-del").disabled = false;
    $("#cl-card-res").className = "res"; $("#cl-card-res").textContent = "новое фото — нажмите «Сохранить»";
  } catch (e) { $("#cl-card-res").className = "res bad"; $("#cl-card-res").textContent = e.message; }
}
$("#cl-me").onclick = () => clCardShow($("#cl-card").hidden);
$("#cl-card-x").onclick = () => { clCardShow(false); clHead(); };
$("#cl-face-drop").onclick = () => $("#cl-face-file").click();
$("#cl-face-file").onchange = () => { const f = $("#cl-face-file").files[0]; $("#cl-face-file").value = ""; if (f) clFaceTake(f); };
$("#cl-face-del").onclick = () => { CL.cardFace = ""; const a = $("#cl-card-ava"); a.classList.remove("has-face"); a.style.backgroundImage = "";
  a.textContent = ($("#cl-myname").value || "?").slice(0, 1).toUpperCase(); $("#cl-face-del").disabled = true;
  $("#cl-card-res").className = "res"; $("#cl-card-res").textContent = "фото уберётся после «Сохранить»"; };
$("#cl-about").oninput = () => { $("#cl-about-n").textContent = $("#cl-about").value.length + " / 160"; };
$("#cl-myname").oninput = () => { if (!$("#cl-card-ava").classList.contains("has-face")) $("#cl-card-ava").textContent = ($("#cl-myname").value || "?").slice(0, 1).toUpperCase(); };
["dragenter", "dragover"].forEach(t => $("#cl-card").addEventListener(t, (e) => { if ([...(e.dataTransfer.items || [])].some(i => i.kind === "file")) { e.preventDefault(); $("#cl-card").classList.add("drop"); } }));
["dragleave", "drop"].forEach(t => $("#cl-card").addEventListener(t, (e) => { if (t === "dragleave" && $("#cl-card").contains(e.relatedTarget)) return; $("#cl-card").classList.remove("drop"); }));
$("#cl-card").addEventListener("drop", (e) => { const f = [...(e.dataTransfer.files || [])].find(x => /^image\//.test(x.type)); if (f) { e.preventDefault(); clFaceTake(f); } });
document.addEventListener("paste", (e) => {
  if ($("#cl-card").hidden || !$("#p-close").classList.contains("cur")) return;
  const f = [...((e.clipboardData && e.clipboardData.files) || [])].find(x => /^image\//.test(x.type));
  if (f) { e.preventDefault(); clFaceTake(f); }
});
$("#cl-card-save").onclick = async () => {
  const b = $("#cl-card-save"), r = $("#cl-card-res"), a = { name: $("#cl-myname").value.trim(), about: $("#cl-about").value.trim(), face_meet: $("#cl-face-meet").checked };
  if (CL.cardFace !== undefined) a.face = CL.cardFace;
  b.disabled = true; r.className = "res"; r.textContent = "сохраняю…";
  try { CL.st = await core.call("close_card", a); CL.cardFace = undefined; r.className = "res ok"; r.textContent = "Сохранено"; clRender(); $("#cl-face-del").disabled = !(CL.st.me || {}).face; }
  catch (e) { r.className = "res bad"; r.textContent = e.message; }
  b.disabled = false;
};
$("#cl-speak").onchange = () => core.call("close_speak", { on: $("#cl-speak").checked }).catch(() => {});
$("#cl-call").onclick = () => core.call("close_call", { pid: CL.cur, video: false }).then(r => toast("Звоню " + r.name + " — окно звонка открыто в браузере", 3000)).catch(e => toast(e.message, 4000));
$("#cl-vcall").onclick = () => core.call("close_call", { pid: CL.cur, video: true }).then(r => toast("Видеозвонок " + r.name + " — окно открыто в браузере", 3000)).catch(e => toast(e.message, 4000));
$("#cl-del").onclick = async () => {
  const p = ((CL.st && CL.st.people) || []).find(x => x.pid === CL.cur); if (!p) return;
  if (!await ask(`Убрать «${p.name}» из близких? Переписка у вас останется, но писать друг другу будет нельзя, пока не пригласите снова.`)) return;
  try { CL.st = await core.call("close_remove", { pid: p.pid }); CL.cur = ""; clRender(); } catch (e) { toast(e.message); }
};
core.on("close", e => { CL.st = e.state; if ($("#p-close").classList.contains("cur")) { clRender(); clTicks(); } else clDot(CL.st); })
  .on("close_msg", e => { if ($("#p-close").classList.contains("cur") && e.pid === CL.cur) clOpen(CL.cur); })
  .on("close_react", e => { if ($("#p-close").classList.contains("cur") && e.pid === CL.cur) clOpen(CL.cur); else if (e.e) toast(`${e.name || "Близкий"}: ${e.e} на ваше сообщение`, 2600); })
  .on("hello", () => core.call("close_state").then(st => { CL.st = st; clDot(st); }).catch(() => {}));
