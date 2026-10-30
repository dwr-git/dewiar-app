/* «Бот персонажа» (0.67; владелец 28.10: «персонаж, обученный на знаниях, — в телеграм-бот, а лучше если в группе
   работает»). Сверху — схема: люди (лично и в группе) → живой облик персонажа → его знания и мозг; ниже стена «не видит»
   (память, файлы, дела, переписка). Новый ответ — по проводам бегут огоньки. Слева — подключение (токен от @BotFather),
   кто отвечает, «О чём бот», группы и ограничения; справа — «Проверить ответ» (без Telegram) и что спрашивали.
   Ядро (core/pbot.py): pbot_get, pbot_connect {token}, pbot_set {patch}, pbot_forget, pbot_try {text}; событие «pbot». */
const PB = { d: null, ent: null, raf: 0, lv: 0, saveT: 0 };
const pbEsc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

async function loadPbot() {
  try { PB.d = await core.call("pbot_get"); } catch (e) { toast(e.message, 4000); return; }
  pbRender();
  if (window.ppLoad) ppLoad();                    // «Посты» и «Рубрики» (studio/pbot_posts.js)
}

function pbPersona() { const d = PB.d || {}; return (d.personas || []).find(p => p.id === d.persona) || (d.personas || [])[0] || { name: "Персонаж", color: "#8B7CFF" }; }

function pbRender() {
  const d = PB.d; if (!d) return;
  const p = pbPersona();
  $("#bp-setup").hidden = d.connected; $("#bp-bot").hidden = !d.connected;
  $("#bp-flow").classList.toggle("off", !d.connected || !d.on);
  $("#bp-flow").style.setProperty("--c", p.color || "#8B7CFF");
  $("#bp-who").textContent = p.name || "Персонаж";
  $("#bp-at").textContent = d.connected ? "@" + d.bot + (d.on ? "" : " · на паузе") : "бот ещё не подключён";
  $("#bp-kb").textContent = d.kb && d.kb.length ? d.kb.slice(0, 3).join(", ") + (d.kb.length > 3 ? ` и ещё ${d.kb.length - 3}` : "") : "не подключены — нажмите, чтобы подключить";
  $("#bp-n-kb").classList.toggle("dim", !(d.kb && d.kb.length));
  $("#bp-model").textContent = d.model || "общий";
  $("#bp-n-gr").classList.toggle("dim", !d.groups);
  $("#bp-gr-sub").textContent = d.groups ? "когда упомянут или ответят ему" : "выключено";
  if (d.connected) {
    $("#bp-name").textContent = "@" + d.bot;
    $("#bp-state").textContent = !d.on ? "на паузе — не отвечает" : d.running ? "работает, пока включён этот компьютер" : "запускается…";
    $("#bp-on").checked = !!d.on;
    $("#bp-open").href = "https://t.me/" + encodeURIComponent(d.bot);
    $("#bp-addgr").href = "https://t.me/" + encodeURIComponent(d.bot) + "?startgroup=1";
    $("#bp-problem").hidden = !d.problem; $("#bp-problem").textContent = d.problem ? "Сейчас: " + d.problem : "";
  }
  $("#bp-ps").innerHTML = (d.personas || []).map(x => `<button type="button" role="radio" class="co-m${x.id === p.id ? " on" : ""}" aria-checked="${x.id === p.id}" data-id="${pbEsc(x.id)}" style="--c:${pbEsc(x.color || "#8B7CFF")}">`
    + (x.avatar_url ? `<i class="pic" aria-hidden="true" style="background-image:url('${String(x.avatar_url).replace(/'/g, "%27")}')"></i>` : `<i aria-hidden="true">${pbEsc((x.name || "?")[0])}</i>`)
    + `<span><b>${pbEsc(x.name)}</b><small>${x.kb ? `знаний подключено: ${x.kb}` : "без знаний"}</small></span></button>`).join("");
  $$("#bp-ps .co-m").forEach(b => b.onclick = () => pbSet({ persona: b.dataset.id }));
  $("#bp-kbtip").innerHTML = d.kb && d.kb.length ? `Отвечает по знаниям: ${d.kb.map(pbEsc).join(", ")}.`
    : `Чтобы бот отвечал по вашим документам, дайте персонажу знания: <a href="#" id="bp-to-p">«Персонажи»</a> → ${pbEsc(p.name)} → «Знания».`;
  const tp = $("#bp-to-p"); if (tp) tp.onclick = (e) => { e.preventDefault(); pbToKb(); };
  const nk = $("#bp-n-kb"); nk.onclick = pbToKb; nk.onkeydown = (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pbToKb(); } };
  for (const [id, k] of [["#bp-brief", "brief"], ["#bp-welcome", "welcome"]]) if (document.activeElement !== $(id)) $(id).value = d[k] || "";
  $("#bp-groups").checked = !!d.groups;
  if (document.activeElement !== $("#bp-pu")) $("#bp-pu").value = d.per_user;
  if (document.activeElement !== $("#bp-pd")) $("#bp-pd").value = d.per_day;
  pbLog(d);
  pbEnt(p);
  requestAnimationFrame(pbWires);
}

/* «Знания» на схеме — кнопка (вопрос пользователя 29.10: «где подключаются Знания (RAG)?»): «Персонажи» → карточка этого
   персонажа открыта, раздел «Знания» перед глазами */
function pbToKb() {
  const id = pbPersona().id, b = $('nav button[data-p="personas"]'); if (b) b.click();
  let n = 0;
  const go = () => { const list = typeof personas !== "undefined" ? personas : [], p = list.find(x => x.id === id);
    if (p && typeof openEditor === "function") { openEditor(p); const k = $("#e-kb"); if (k) k.scrollIntoView({ block: "center" }); }
    else if (n++ < 20) setTimeout(go, 100); };
  setTimeout(go, 50);
}

function pbLog(d) {
  $("#bp-stat").textContent = d.connected ? `сегодня ${d.today} · всего ${d.total}` : "";
  $("#bp-chats").innerHTML = (d.chats || []).length ? `<span>Группы:</span>` + d.chats.map(c => `<em>${pbEsc(c.title)}</em>`).join("") : "";
  const when = (t) => new Date(t * 1000).toLocaleString("ru-RU", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
  $("#bp-log").innerHTML = (d.log || []).length ? d.log.map(x => `<li><div class="bp-lq"><b>${pbEsc(x.who)}</b>${x.chat ? `<span>в «${pbEsc(x.chat)}»</span>` : ""}<small>${when(x.t)}</small></div>`
    + `<p class="bp-bq">${pbEsc(x.q)}</p><p class="bp-ba">${pbEsc(x.a)}</p></li>`).join("")
    : `<li class="co-none">${d.connected ? "Пока никто не писал. Откройте бота в Telegram и спросите что-нибудь — вопрос и ответ появятся здесь." : "Здесь будут вопросы людей и ответы бота — видно, что спрашивают чаще всего."}</li>`;
}

/* живой облик в центре схемы: тот же, что в виджете; новый ответ — «говорит» пару секунд */
function pbEnt(p) {
  const key = p.id + "|" + (p.avatar_url ? 1 : 0) + p.color;
  if (PB.ent && PB.key === key) return;
  try { if (PB.ent) PB.ent.destroy(); } catch (e) { }
  PB.ent = null; PB.key = key;
  if (typeof DewiarEntity !== "function") return;
  try { PB.ent = new DewiarEntity($("#bp-ent"), { style: p.avatar_url && p.style !== "aura" ? "photo" : (p.style || "nexus"), color: p.color || "#8B7CFF", image: p.avatar_url || null, ring: false }); PB.ent.set({ state: "idle" }); } catch (e) { }
}
function pbPulse() {
  const f = $("#bp-flow"); f.classList.remove("pulse"); void f.offsetWidth; f.classList.add("pulse");
  PB.lv = 1; PB.t = performance.now();
  if (PB.ent) PB.ent.set({ state: "speaking" });
  if (!PB.raf) PB.raf = requestAnimationFrame(pbTick);
}
function pbTick() {
  const k = Math.max(0, PB.lv * Math.exp(-(performance.now() - PB.t) / 900));
  if (PB.ent) PB.ent.set({ level: Math.min(1, k * (0.6 + 0.4 * Math.abs(Math.sin(performance.now() / 120)))) });
  if (k < 0.03) { PB.raf = 0; if (PB.ent) PB.ent.set({ state: "idle", level: 0 }); return; }
  PB.raf = requestAnimationFrame(pbTick);
}

/* провода схемы: плавные кривые от карточек к облику; рисуются по фактическим местам (вёрстка меняется с шириной окна) */
function pbWires() {
  const f = $("#bp-flow"), svg = $("#bp-wires"); if (!f || !svg || !f.offsetWidth) return;
  const R = f.getBoundingClientRect(), orb = $(".bp-orb", f).getBoundingClientRect();
  const cx = orb.left + orb.width / 2 - R.left, cy = orb.top + orb.height / 2 - R.top, r = orb.width / 2 + 6;
  svg.setAttribute("viewBox", `0 0 ${R.width} ${R.height}`);
  const wire = (el, side, cls) => {
    const b = el.getBoundingClientRect();
    const x = side < 0 ? b.right - R.left + 4 : b.left - R.left - 4, y = b.top + b.height / 2 - R.top;
    const ex = cx + side * r * 0.96, ey = cy + (y - cy) * 0.28;
    const mx = (x + ex) / 2;
    const d = side < 0 ? `M${x},${y} C${mx},${y} ${mx},${ey} ${ex},${ey}` : `M${ex},${ey} C${mx},${ey} ${mx},${y} ${x},${y}`;
    return `<path class="bp-w ${cls}" d="${d}"/><path class="bp-w bp-run ${cls}" pathLength="100" d="${d}"/>`;
  };
  svg.innerHTML = wire($("#bp-n-dm"), -1, "in" + ($("#bp-n-dm").classList.contains("dim") ? " dim" : "")) + wire($("#bp-n-gr"), -1, "in" + ($("#bp-n-gr").classList.contains("dim") ? " dim" : ""))
    + wire($("#bp-n-kb"), 1, "out" + ($("#bp-n-kb").classList.contains("dim") ? " dim" : "")) + wire($("#bp-n-md"), 1, "out");
}
addEventListener("resize", () => { if ($("#p-pbot") && $("#p-pbot").classList.contains("cur")) pbWires(); });

async function pbSet(patch) {
  try { PB.d = Object.assign(PB.d || {}, await core.call("pbot_set", { patch })); pbRender(); } catch (e) { toast(e.message, 4000); }
}
function pbSaveSoon(patch) { clearTimeout(PB.saveT); PB.saveT = setTimeout(() => pbSet(patch()), 700); }

function pbBubble(cls, html) {
  const ch = $("#bp-chat"); const e = $(".bp-empty", ch); if (e) e.remove();
  ch.insertAdjacentHTML("beforeend", `<div class="bp-b ${cls}">${html}</div>`);
  ch.scrollTop = ch.scrollHeight;
  return ch.lastElementChild;
}
async function pbTry() {
  const q = $("#bp-q").value.trim(); if (q.length < 2) { $("#bp-q").focus(); return; }
  const p = pbPersona();
  $("#bp-q").value = ""; $("#bp-send").disabled = true;
  pbBubble("me", pbEsc(q));
  const a = pbBubble("bot", `<small>${pbEsc(p.name)}</small><span class="co-dots" style="--c:${pbEsc(p.color || "#8B7CFF")}"><i></i><i></i><i></i></span>`);
  try {
    const r = await core.call("pbot_try", { text: q });
    a.innerHTML = `<small>${pbEsc(p.name)}</small>` + pbEsc(r.answer).replace(/\n/g, "<br>");
    pbPulse();
  } catch (e) { a.classList.add("err"); a.innerHTML = `<small>${pbEsc(p.name)}</small>${pbEsc(e.message)}`; }
  $("#bp-send").disabled = false; $("#bp-chat").scrollTop = 1e6;
}

(function pbWire() {
  if (!$("#p-pbot")) return;
  $("#bp-connect").onclick = async () => {
    const t = $("#bp-token").value.trim(); if (!t) { $("#bp-token").focus(); return; }
    $("#bp-connect").disabled = true;
    try { PB.d = Object.assign(PB.d || {}, await core.call("pbot_connect", { token: t })); $("#bp-token").value = ""; pbRender(); toast("Бот подключён — напишите ему в Telegram", 3500); }
    catch (e) { toast(e.message, 5000); }
    $("#bp-connect").disabled = false;
  };
  $("#bp-token").onkeydown = (e) => { if (e.key === "Enter") $("#bp-connect").click(); };
  $("#bp-forget").onclick = async () => {
    if (!(await ask("Отключить бота? Он перестанет отвечать; настройки персонажа сохранятся.", { ok: "Отключить" }))) return;
    try { PB.d = Object.assign(PB.d || {}, await core.call("pbot_forget")); pbRender(); } catch (e) { toast(e.message); }
  };
  $("#bp-on").onchange = () => pbSet({ on: $("#bp-on").checked });
  $("#bp-groups").onchange = () => pbSet({ groups: $("#bp-groups").checked });
  $("#bp-brief").oninput = () => pbSaveSoon(() => ({ brief: $("#bp-brief").value }));
  $("#bp-welcome").oninput = () => pbSaveSoon(() => ({ welcome: $("#bp-welcome").value }));
  $("#bp-pu").onchange = () => pbSet({ per_user: +$("#bp-pu").value });
  $("#bp-pd").onchange = () => pbSet({ per_day: +$("#bp-pd").value });
  $("#bp-send").onclick = pbTry;
  $("#bp-q").onkeydown = (e) => { if (e.key === "Enter") pbTry(); };
})();

core.on("pbot", (e) => {                                 // бот ответил в Telegram — обновить ленту, огоньки по проводам
  if (!PB.d || !e) return;
  Object.assign(PB.d, e);
  if ($("#p-pbot").classList.contains("cur")) { pbLog(PB.d); pbPulse(); }
});
window.loadPbot = loadPbot;
