/* Студия → «Близкие» → «Рядом»: радар, как на телефоне (android/assets/www/app.js, rad*). Компьютер сам не знает, где
   он, — центр радара ваш телефон: он присылает своё место своим устройствам (конверт mygeo), а близкие — тем, кому
   показывают себя (kind geo; core/close.py geo_state). Отсюда — смотреть, помахать 👋 (close_wave), написать, позвонить.
   Показать себя близким — на телефоне. */
const RD = { tab: "chat", sel: "", raf: 0 };
const RD_DIR = ["на север", "на северо-восток", "на восток", "на юго-восток", "на юг", "на юго-запад", "на запад", "на северо-запад"];
const RD_STALE = 15 * 60000;
function rdGeo(a, b) {
  const t = Math.PI / 180, f1 = a.lat * t, f2 = b.lat * t, df = (b.lat - a.lat) * t, dl = (b.lon - a.lon) * t;
  const h = Math.sin(df / 2) ** 2 + Math.cos(f1) * Math.cos(f2) * Math.sin(dl / 2) ** 2;
  const deg = Math.atan2(Math.sin(dl) * Math.cos(f2), Math.cos(f1) * Math.sin(f2) - Math.sin(f1) * Math.cos(f2) * Math.cos(dl)) / t;
  return [2 * 6371 * Math.asin(Math.min(1, Math.sqrt(h))), (deg + 360) % 360];
}
const rdKm = (km) => km < 0.05 ? "рядом" : km < 1 ? Math.round(km * 100) * 10 + " м" : (km < 10 ? km.toFixed(1).replace(".", ",") : Math.round(km).toLocaleString("ru-RU")) + " км";
const rdDir = (d) => RD_DIR[Math.round((((d % 360) + 360) % 360) / 45) % 8];
const rdAgo = (ts) => { const m = Math.max(0, Math.round((Date.now() - ts) / 60000)); return m < 2 ? "сейчас" : m < 60 ? m + " мин назад" : m < 1440 ? Math.round(m / 60) + " ч назад" : clTime(ts); };
const rdR = (km) => 46 + 132 * Math.max(0, Math.min(1, Math.log10(Math.max(km, 0.05) / 0.05) / Math.log10(600)));
const rdFirst = (n) => String(n || "").trim().split(/\s+/)[0] || "Без имени";
const RD_REDUCE = matchMedia("(prefers-reduced-motion: reduce)");

function rdTab(t) {
  RD.tab = t;
  $$("#cl-tabs button").forEach(b => { b.classList.toggle("on", b.dataset.t === t); b.setAttribute("aria-selected", String(b.dataset.t === t)); });
  $("#cl-near").hidden = t !== "near"; $(".cl-box").style.display = t === "chat" ? "" : "none";
  if ($("#cl-meet")) $("#cl-meet").hidden = t !== "meet";
  if (t === "near") nearRender();
  if (t === "meet" && window.meetOpen) meetOpen();
}
$$("#cl-tabs button").forEach(b => b.onclick = () => rdTab(b.dataset.t));

function rdPeople() {
  const st = CL.st || {}, g = st.geo || { people: {}, me: null };
  return (st.people || []).filter(p => g.people && g.people[p.pid]).map(p => {
    const o = { p, g: g.people[p.pid] }; if (g.me) [o.km, o.deg] = rdGeo(g.me, o.g); return o;
  }).sort((a, b) => (a.km ?? 1e9) - (b.km ?? 1e9));
}
function nearRender() {
  const box = $("#cl-near"); if (!box || box.hidden) return;
  const st = CL.st || { people: [] }, me = (st.geo || {}).me, ppl = rdPeople();
  if (!(st.people || []).length) {
    box.innerHTML = `<div class="nr-empty"><b>Сначала — близкие</b><span>На радаре — близкие, которые сами решили показать вам, где они. Пригласите близкого во вкладке «Переписка».</span></div>`;
    return;
  }
  const sel = ppl.find(o => o.p.pid === RD.sel && o.km != null) || ppl.find(o => o.km != null && Date.now() - o.g.ts < RD_STALE) || ppl.find(o => o.km != null) || ppl[0];
  if (sel) RD.sel = sel.p.pid;
  const rr = [0.3, 3, 30].map(rdR);
  const rings = rr.map(r => `<circle cx="180" cy="180" r="${r.toFixed(1)}"/>`).join("") + [["300 м", rr[0]], ["3 км", rr[1]], ["30 км", rr[2]]].map(([t, r]) => `<text x="${(180 - r + 5).toFixed(1)}" y="176">${t}</text>`).join("");
  const dots = ppl.filter(o => o.km != null).map(o => {
    const a = o.deg * Math.PI / 180, r = rdR(o.km), stale = Date.now() - o.g.ts > RD_STALE;
    return `<button class="rad-p${stale ? " stale" : ""}${o.p.pid === RD.sel ? " sel" : ""}" data-pid="${clEsc(o.p.pid)}" data-a="${o.deg}" style="--c:${clColor(o.p.pid)};left:${(180 + r * Math.sin(a)) / 3.6}%;top:${(180 - r * Math.cos(a)) / 3.6}%" aria-label="${clEsc(o.p.name)}: ${rdKm(o.km)} ${rdDir(o.deg)}">
      <i class="cl-ava" data-face="${clEsc(o.p.pid)}" data-v="${+o.p.face || 0}">${clEsc((o.p.name || "?")[0].toUpperCase())}</i><span><b>${clEsc(rdFirst(o.p.name))}</b>${rdKm(o.km)}${stale ? " · " + rdAgo(o.g.ts) : ""}</span></button>`;
  }).join("");
  let card;
  if (!me) card = `<div class="nr-card nr-need"><b>Центр радара — ваш телефон</b><span>Компьютер сам не знает, где он. Откройте на телефоне «Близкие» → «Рядом» — его место появится здесь, и будет видно, кто далеко, а кто рядом.</span></div>`;
  else if (!sel) card = `<div class="nr-card nr-need"><b>Пока никто не показал вам, где он</b><span>Показать себя близким и позвать их на радар — на телефоне: «Близкие» → «Рядом».</span></div>`;
  else {
    const p = sel.p, stale = Date.now() - sel.g.ts > RD_STALE;
    card = `<div class="nr-card" style="--c:${clColor(p.pid)}"><div class="h"><i class="cl-ava" data-face="${clEsc(p.pid)}" data-v="${+p.face || 0}">${clEsc((p.name || "?")[0].toUpperCase())}</i><div><b>${clEsc(p.name)}</b><small>${stale ? "последний раз — " + rdAgo(sel.g.ts) : "обновлено " + rdAgo(sel.g.ts)}</small></div></div>
      ${sel.km != null ? `<div class="nr-dist"><strong>${sel.g.acc > 500 && sel.km >= 0.05 ? "≈ " : ""}${rdKm(sel.km)}</strong><em>${sel.km < 0.05 ? "совсем рядом" : rdDir(sel.deg)}</em>${sel.km >= 0.05 ? `<svg class="rad-arr" viewBox="0 0 24 24" style="--deg:${sel.deg}deg" aria-hidden="true"><path d="M12 3 7 20l5-4 5 4z"/></svg>` : ""}</div>` : ""}
      <div class="nr-acts"><button class="btn primary nr-wave" id="nr-wave">👋 Помахать</button><button class="btn" id="nr-msg">Написать</button>${(p.devs || []).length ? `<button class="btn" id="nr-call">Позвонить</button>` : ""}</div></div>`;
  }
  const rest = (st.people || []).filter(p => !ppl.some(o => o.p.pid === p.pid));
  box.innerHTML = `<div class="nr-grid"><div class="nr-left"><div class="radar${me ? "" : " nome"}" id="nr-radar">
      <svg class="rad-rings" viewBox="0 0 360 360" aria-hidden="true">${rings}</svg><div class="rad-sweep" id="nr-sweep"></div>
      <div class="rad-n" style="left:50%;top:.5%" aria-hidden="true">С</div><div class="rad-me" title="Ваш телефон" data-face="${clEsc((st.me || {}).pid || "me")}" data-v="${+((st.me || {}).face) || 0}">Я</div>${dots}</div>
      <p class="hint nr-note">${me ? `Центр — ваш телефон · место ${rdAgo(me.ts) === "сейчас" ? "обновлено сейчас" : "обновлено " + rdAgo(me.ts)}` : "Центр — ваш телефон: откройте на нём «Близкие» → «Рядом»"}</p></div>
    <div class="nr-right">${card}
      ${rest.length ? `<h3>Ещё не на радаре</h3><div class="nr-rest">${rest.map(p => `<span><i class="cl-ava" style="--c:${clColor(p.pid)}" data-face="${clEsc(p.pid)}" data-v="${+p.face || 0}">${clEsc((p.name || "?")[0].toUpperCase())}</i>${clEsc(p.name)}</span>`).join("")}</div><p class="hint">Позвать на радар и показать себя — на телефоне.</p>` : ""}
      <p class="hint nr-priv">Места шифруются на телефонах — сервер Dewiar их не видит. Видно только расстояние и сторону, пока близкий сам разрешил.</p></div></div>`;
  clFaces(box);                                                  // фото близких (пакет 27.10: «на радаре — буквы»)
  $$("#nr-radar .rad-p").forEach(b => b.onclick = () => { RD.sel = b.dataset.pid; nearRender(); });
  if ($("#nr-wave")) $("#nr-wave").onclick = async (e) => { const b = e.currentTarget; b.disabled = true;
    try { await core.call("close_wave", { pid: RD.sel }); rdFly(RD.sel); toast(`Помахали: ${rdFirst(sel.p.name)} увидит и услышит 👋`); } catch (x) { toast(x.message, 4000); }
    setTimeout(() => { if (b.isConnected) b.disabled = false; }, 1500); };
  if ($("#nr-msg")) $("#nr-msg").onclick = () => { rdTab("chat"); clOpen(RD.sel); };
  if ($("#nr-call")) $("#nr-call").onclick = () => core.call("close_call", { pid: RD.sel, video: false }).then(r => toast("Звоню " + r.name + " — окно звонка открыто в браузере", 3000)).catch(x => toast(x.message, 4000));
  rdLoop();
}
function rdAt(pid) { const b = pid && $(`#nr-radar .rad-p[data-pid="${CSS.escape(pid)}"]`); return b ? [b.style.left, b.style.top] : ["50%", "50%"]; }
function rdFly(pid) {
  const R = $("#nr-radar"); if (!R) return;
  const [x, y] = rdAt(pid), h = document.createElement("div"); h.className = "rad-fly"; h.textContent = "👋"; R.appendChild(h);
  requestAnimationFrame(() => requestAnimationFrame(() => { h.style.left = x; h.style.top = y; }));
  setTimeout(() => { h.style.opacity = 0; rdRipple(pid, 1); setTimeout(() => h.remove(), 500); }, RD_REDUCE.matches ? 50 : 1100);
}
function rdRipple(pid, n) {
  const R = $("#nr-radar"); if (!R) return;
  const [x, y] = rdAt(pid);
  for (let i = 0; i < n; i++) setTimeout(() => { const r = document.createElement("div"); r.className = "rad-rip"; r.style.left = x; r.style.top = y;
    r.style.setProperty("--c", clColor(pid)); R.appendChild(r); setTimeout(() => r.remove(), 1500); }, i * 350);
}
function rdLoop() {                                       // луч: проходя над близким, «пингует» его
  if (RD.raf || RD_REDUCE.matches) return;
  const t0 = performance.now(), pinged = {};
  const tick = (t) => {
    const sw = $("#nr-sweep");
    if (!sw || $("#cl-near").hidden || document.hidden) { RD.raf = 0; return; }
    const a = ((t - t0) / 6000 * 360) % 360; sw.style.transform = `rotate(${a}deg)`;
    $$("#nr-radar .rad-p:not(.stale)").forEach(b => { const d = (+b.dataset.a - a + 360) % 360;
      if (d < 5 && !pinged[b.dataset.pid]) { pinged[b.dataset.pid] = 1; b.classList.remove("ping"); void b.offsetWidth; b.classList.add("ping"); }
      if (d > 30) pinged[b.dataset.pid] = 0; });
    RD.raf = requestAnimationFrame(tick);
  };
  RD.raf = requestAnimationFrame(tick);
}
core.on("close_geo", e => { if (CL.st) CL.st.geo = e.geo; nearRender(); });
core.on("close_wave", e => { if (!$("#cl-near").hidden) { rdRipple(e.pid, 3); toast(`${rdFirst(e.name)} машет вам 👋`, 3600); } });
core.on("close", () => nearRender());
