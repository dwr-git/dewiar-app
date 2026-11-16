/* «Пульт Лиры» (1.0.6; макеты владельца 15.11 — артефакт «Пульт Лиры — макеты»): первая вкладка блокнота показывает,
   чем Лира занята прямо сейчас. Правило макетов: светится только настоящее — каждая точка — реальная заметка, каждая
   линия — «подняла это к ответу» (событие recall ядра), шаги — события tool. Нет работы — нет движения.
   Виды: думает (вопрос в центре, поднятые заметки тянутся к нему, шаги под ним) · тишина (созвездие заметок) · фон
   (дневник, Радар, «Дальше» — команда pult_data) · заявка с сайта (зелёная карточка сверху).
   Сам открывается, когда Лира начала думать или пришла заявка, если вы не печатаете (последняя клавиша > 5 с назад и
   ничего не выделено); ответила — через 4 с назад, на вашу вкладку, курсор на месте. Печатаете — пульт не перехватывает:
   на вкладке дышит точка, внизу листа — живая полоса «Открыть пульт». Сами открыли — остаётся, пока не уйдёте.
   Что показывать — шестерёнка на самой вкладке (ui.pult); выключить совсем — «Оформление» → «Пульт Лиры» (ui.pult_on).
   Первый раз — одна карточка «Это Пульт» (ui.pult_seen). Обводок нет: цвет, тень, свечение, прозрачность. */
(() => {
  const DEF = { thoughts: true, background: true, stars: true, auto: true, names: "hover", motion: "full" };
  const PU = { on: true, cfg: {}, seen: true, active: false, auto: false, touched: false, key: 0, state: "idle", was: "idle",
               q: "", steps: [], recall: null, data: null, at: 0, lead: null, leadTs: -1, backT: 0, who: "Лира", nodes: [] };
  const cfg = () => Object.assign({}, DEF, PU.cfg || {});
  const esc = (t) => String(t == null ? "" : t).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  const el = (s) => document.querySelector(s);
  const A = () => (window.pywebview && window.pywebview.api) || null;
  const calm = () => cfg().motion === "calm" || matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---------- разметка ---------- */
  const tab = document.createElement("button");
  tab.id = "pt-tab"; tab.className = "tab pt"; tab.type = "button"; tab.setAttribute("role", "tab"); tab.setAttribute("aria-selected", "false");
  tab.title = "Пульт — чем Лира занята прямо сейчас";
  tab.innerHTML = '<i class="pt-dot" aria-hidden="true"></i><span>Пульт</span>';
  el("#top").insertBefore(tab, el("#tabs"));
  const box = document.createElement("section");
  box.id = "pult"; box.setAttribute("aria-label", "Пульт Лиры");
  box.innerHTML = `
    <div class="pu-head"><p class="pu-st" aria-live="polite"><i class="pu-orb" aria-hidden="true"></i><b id="pu-who">Лира</b><span id="pu-what">на связи</span></p>
      <button class="ib" id="pu-gear" type="button" title="Что показывать на пульте" aria-label="Что показывать на пульте" aria-haspopup="dialog" aria-expanded="false"><svg viewBox="0 0 24 24"><path d="M4 7h9M17 7h3M4 17h3M11 17h9"/><circle cx="15" cy="7" r="2"/><circle cx="9" cy="17" r="2"/></svg></button></div>
    <div class="pu-lead" id="pu-lead" hidden></div>
    <div class="pu-stage" id="pu-stage">
      <svg id="pu-sky" aria-hidden="true"></svg>
      <div id="pu-names" aria-hidden="true"></div>
      <article class="pu-q" id="pu-q" hidden><p id="pu-qt"></p><ol id="pu-steps"></ol></article>
      <p class="pu-empty" id="pu-empty" hidden></p>
    </div>
    <div class="pu-cards" id="pu-cards"></div>
    <div class="pu-pop" id="pu-pop" role="dialog" aria-label="Что показывать на пульте" hidden></div>
    <div class="pu-ob" id="pu-ob" role="dialog" aria-labelledby="pu-ob-h" hidden>
      <div class="pu-ob-c"><i class="pu-orb big" aria-hidden="true"></i><h2 id="pu-ob-h">Это Пульт</h2>
        <p>Здесь видно, чем Лира занята прямо сейчас: какие заметки и факты она вспоминает к вашему вопросу, что делает по шагам, что записала в дневник и что нашла в Радаре.</p>
        <p>Пульт открывается сам, когда Лира думает, и возвращает на вашу вкладку, когда она ответила. Пока вы печатаете — не мешает.</p>
        <div class="pu-ob-b"><button type="button" class="pu-btn main" id="pu-ob-ok">Понятно</button><button type="button" class="pu-btn" id="pu-ob-set">Настроить</button></div></div>
    </div>`;
  el("#play").after(box);
  const strip = document.createElement("div");
  strip.id = "pu-strip"; strip.hidden = true; strip.setAttribute("aria-live", "polite");
  strip.innerHTML = '<i aria-hidden="true"></i><span id="pu-strip-t"></span><button type="button" id="pu-strip-go">Открыть пульт</button>';
  el("#foot").before(strip);

  /* ---------- режим ---------- */
  function sel() { try { const s = getSelection(); return s && s.rangeCount ? s.getRangeAt(0).cloneRange() : null; } catch (e) { return null; } }
  let keep = null;
  function enter(auto) {
    if (!PU.on || PU.active) { if (PU.active && !auto) { PU.auto = false; } return; }
    if (document.body.classList.contains("play")) { if (auto) return; window.padMode && padMode("notes"); }
    keep = ED.contains((getSelection() || {}).anchorNode || null) ? sel() : null;
    PU.active = true; PU.auto = !!auto; PU.touched = false;
    document.body.classList.add("pult");
    tab.classList.add("on"); tab.setAttribute("aria-selected", "true");
    strip.hidden = true;
    try { if (typeof saveNow === "function") saveNow(); } catch (e) { }
    const a = A(); if (a && a.pad_mode_mark) a.pad_mode_mark("pult");
    if (Date.now() - PU.at > 20000) load(); else draw();
    if (!PU.seen) setTimeout(onboard, auto ? 900 : 200);
  }
  function leave(restore) {
    clearTimeout(PU.backT);
    if (!PU.active) return;
    PU.active = false; PU.auto = false;
    document.body.classList.remove("pult");
    tab.classList.remove("on"); tab.setAttribute("aria-selected", "false");
    pop(false);
    const a = A(); if (a && a.pad_mode_mark && !document.body.classList.contains("play")) a.pad_mode_mark("notes");
    if (restore) setTimeout(() => { try { ED.focus({ preventScroll: true }); if (keep) { const s = getSelection(); s.removeAllRanges(); s.addRange(keep); } } catch (e) { } }, 60);
  }
  window.pultOpen = () => enter(false);
  tab.onclick = () => (PU.active ? (PU.auto = false, PU.touched = true) : enter(false));
  // своя вкладка, «+», «Досуг» — пульт уступает место
  el("#tabs").addEventListener("click", () => leave(false), true);
  for (const id of ["#b-new", "#b-play", "#b-list"]) { const b = el(id); if (b) b.addEventListener("click", () => leave(false), true); }
  const pm = window.padMode;
  window.padMode = (m) => { if (m === "pult") { enter(false); return; } if (PU.active) leave(m !== "play"); return pm(m); };
  box.addEventListener("pointerdown", () => { PU.touched = true; clearTimeout(PU.backT); });
  box.addEventListener("wheel", () => { PU.touched = true; clearTimeout(PU.backT); }, { passive: true });
  el("#pu-strip-go").onclick = () => enter(false);
  // печатают — пульт не перехватывает
  document.addEventListener("keydown", (e) => { if (!PU.active || e.target === ED) PU.key = Date.now(); if (PU.active && e.key === "Escape" && !el("#pu-ob").hidden) { e.stopPropagation(); onboardDone(); } }, true);
  ED.addEventListener("input", () => { PU.key = Date.now(); });
  const typing = () => {
    if (Date.now() - PU.key < 5000) return true;
    try { const s = getSelection(); return !!(s && !s.isCollapsed && ED.contains(s.anchorNode)); } catch (e) { return false; }
  };
  function maybeAuto(why) {
    if (!PU.on || PU.active || document.body.classList.contains("play") || el("#wrap").classList.contains("away")) return;   // лист убран — молчим
    if (why === "think" && !cfg().thoughts) return;
    if (!cfg().auto || typing()) { live(); return; }
    enter(true);
  }
  function live() {
    if (PU.active || !PU.on) return;
    const t = PU.lead && Date.now() - PU.lead.seen < 60000 ? `Заявка с сайта: ${PU.lead.name || "посетитель"}`
      : PU.state === "thinking" ? (PU.steps.length ? `${PU.who}: ${PU.steps[PU.steps.length - 1].t}` : `${PU.who} думает над вопросом`)
      : PU.state === "speaking" ? `${PU.who} отвечает` : "";
    tab.classList.toggle("live", !!t);
    strip.hidden = !t;
    if (t) el("#pu-strip-t").textContent = t;
  }
  function backSoon(ms) {
    clearTimeout(PU.backT);
    if (!PU.active || !PU.auto) return;
    PU.backT = setTimeout(() => { if (PU.active && PU.auto && !PU.touched && el("#pu-ob").hidden && el("#pu-pop").hidden) leave(true); }, ms);
  }

  /* ---------- данные ---------- */
  async function load() {
    try {
      const d = await core.call("pult_data");
      if (d && typeof d === "object") {
        PU.data = d; PU.at = Date.now();
        if (d.who) PU.who = d.who;
        if (PU.leadTs < 0) PU.leadTs = Math.max(0, ...(d.leads || []).map(x => +x.ts || 0));
      }
    } catch (e) { }
    draw();
  }
  core.on("heard", (e) => {
    const t = String((e && e.text) || "").split("\n\nВложения:")[0].trim();
    if (!t) return;
    PU.q = t.slice(0, 160); PU.steps = []; PU.recall = null;
    if (PU.active) draw();
  });
  core.on("recall", (e) => { PU.recall = { notes: (e && e.notes) || [], memory: (e && e.memory) || [] }; if (e && e.q && !PU.q) PU.q = e.q; if (PU.active) draw(); else live(); });
  core.on("tool", (e) => {
    if (!e || !e.title || PU.state === "idle") return;
    const name = String(e.name || ""), st = e.status || "run";
    const i = PU.steps.findIndex(x => x.n === name && x.s === "run");
    if (i >= 0) Object.assign(PU.steps[i], { t: String(e.title).slice(0, 80), s: st });
    else PU.steps.push({ n: name, t: String(e.title).slice(0, 80), s: st });
    PU.steps = PU.steps.slice(-5);
    if (PU.active) drawQ(); else live();
  });
  core.on("state", (e) => {
    const st = (e && e.state) || "idle";
    PU.was = PU.state; PU.state = st;
    if (st === "thinking" && PU.was !== "thinking") maybeAuto("think");
    if (st !== "thinking" && st !== "speaking" && (PU.was === "thinking" || PU.was === "speaking")) {
      backSoon(4000);
      setTimeout(() => { if (PU.state !== "thinking" && PU.state !== "speaking") { tab.classList.remove("live"); if (!(PU.lead && Date.now() - PU.lead.seen < 60000)) strip.hidden = true; } }, 4000);
      setTimeout(load, 1500);                           // ответила — в дневнике и «Дальше» могло появиться новое
    }
    head();
    if (PU.active) drawQ(); else live();
  });
  core.on("diary", () => { if (PU.active) load(); else PU.at = 0; });
  core.on("insight", () => { PU.at = 0; if (PU.active && PU.state === "idle") load(); });
  core.on("sitechat", (e) => {
    const r = ((e && e.recent) || [])[0];
    if (!r) return;
    const ts = +r.ts > 1e12 ? +r.ts / 1000 : +r.ts;
    if (PU.leadTs >= 0 && ts > PU.leadTs) {
      PU.leadTs = ts; PU.lead = { name: r.name || "", cid: r.cid || "", ts, seen: Date.now() };
      PU.at = 0;
      if (!PU.active) { maybeAuto("lead"); if (PU.active) backSoon(20000); } else load();
    } else if (PU.leadTs < 0) PU.leadTs = ts;
  });
  function applySettings(st) {
    const u = (st && st.ui) || {};
    PU.on = u.pult_on !== false;
    PU.cfg = (u.pult && typeof u.pult === "object") ? u.pult : {};
    PU.seen = !!u.pult_seen;
    tab.hidden = !PU.on;
    if (!PU.on) { leave(true); strip.hidden = true; }
    document.body.classList.toggle("pu-calm", calm());
    document.body.classList.toggle("pu-names", cfg().names === "always");
    if (PU.active) draw();
  }
  core.on("hello", (d) => { applySettings((d && d.settings) || {}); if (Q.get("mode") === "pult") enter(false); });
  core.on("settings", (e) => applySettings((e && e.settings) || e || {}));

  /* ---------- рисование ---------- */
  const WHAT = { thinking: "думает над вопросом", speaking: "отвечает", listening: "слушает", muted: "микрофон выключен", idle: "на связи" };
  function head() {
    el("#pu-who").textContent = PU.who;
    el("#pu-what").textContent = WHAT[PU.state] || WHAT.idle;
    box.dataset.st = PU.state;
  }
  const busy = () => PU.state === "thinking" || PU.state === "speaking";
  function hash(s) { let h = 2166136261; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); } return (h >>> 0) / 4294967296; }
  const norm = (s) => String(s || "").toLowerCase().replace(/ё/g, "е").replace(/\.md$/, "").trim();
  function layout(w, h) {
    // созвездия — папки заметок по кругу; внутри — спираль по свежести. Положение не прыгает от раза к разу (хэш имени)
    const notes = ((PU.data && PU.data.notes) || []).slice(0, 140).map(n => Object.assign({}, n));
    const rec = PU.recall ? PU.recall.notes.map(norm) : [];
    for (const r of PU.recall ? PU.recall.notes : []) if (!notes.some(n => norm(n.t) === norm(r))) notes.push({ t: r, f: "", m: Date.now() / 1000 });
    const groups = {};
    for (const n of notes) (groups[n.f || "·"] = groups[n.f || "·"] || []).push(n);
    const keys = Object.keys(groups).sort((a, b) => groups[b].length - groups[a].length);
    const cx = w / 2, cy = h / 2, rx = w * 0.36, ry = h * 0.34, now = Date.now() / 1000;
    const out = [];
    keys.forEach((k, gi) => {
      const ang = (gi / Math.max(1, keys.length)) * Math.PI * 2 + hash(k) * 0.6 - Math.PI / 2;
      const gx = keys.length === 1 ? cx : cx + Math.cos(ang) * rx, gy = keys.length === 1 ? cy : cy + Math.sin(ang) * ry;
      const g = groups[k].sort((a, b) => (b.m || 0) - (a.m || 0));
      const spread = Math.min(w, h) * (keys.length === 1 ? 0.42 : 0.17);
      g.forEach((n, i) => {
        const a = i * 2.39996 + hash(n.t) * 0.5, r = spread * Math.sqrt((i + 0.6) / Math.max(4, g.length));
        const age = Math.max(0, now - (n.m || 0)) / 86400;
        out.push({ t: n.t, f: n.f, p: n.p || "", x: Math.max(10, Math.min(w - 10, gx + Math.cos(a) * r)), y: Math.max(10, Math.min(h - 10, gy + Math.sin(a) * r)),
                   r: 1.6 + 2.6 * Math.exp(-age / 10), hot: rec.includes(norm(n.t)), fresh: age < 1, g: gi, i });
      });
    });
    return out;
  }
  function drawSky() {
    const st = el("#pu-stage"), svg = el("#pu-sky"), names = el("#pu-names");
    const w = st.clientWidth || 400, h = st.clientHeight || 260;
    svg.setAttribute("viewBox", `0 0 ${w} ${h}`); svg.setAttribute("width", w); svg.setAttribute("height", h);
    if (!cfg().stars) { svg.innerHTML = ""; names.innerHTML = ""; PU.nodes = []; return; }
    const ns = layout(w, h); PU.nodes = ns;
    const cx = w / 2, cy = h / 2, think = busy() && cfg().thoughts;
    let lines = "", dots = "", hot = "";
    // линии созвездий: каждая звезда — к ближайшей более свежей своей папки
    for (const n of ns) {
      if (!n.i) continue;
      let best = null, bd = 1e9;
      for (const m of ns) if (m.g === n.g && m.i < n.i) { const d = (m.x - n.x) ** 2 + (m.y - n.y) ** 2; if (d < bd) { bd = d; best = m; } }
      if (best && bd < (Math.min(w, h) * 0.22) ** 2) lines += `<path d="M${best.x.toFixed(1)} ${best.y.toFixed(1)}L${n.x.toFixed(1)} ${n.y.toFixed(1)}"/>`;
    }
    for (const n of ns) {
      if (n.hot && think) hot += `<path class="pu-ray" d="M${n.x.toFixed(1)} ${n.y.toFixed(1)}Q${((n.x + cx) / 2 + (n.y - cy) * 0.18).toFixed(1)} ${((n.y + cy) / 2 - (n.x - cx) * 0.18).toFixed(1)} ${cx} ${cy}"/>`;
      dots += `<circle class="${n.hot ? "hot" : n.fresh ? "fresh" : ""}" cx="${n.x.toFixed(1)}" cy="${n.y.toFixed(1)}" r="${(n.hot ? n.r + 2.2 : n.r).toFixed(1)}"/>`;
    }
    svg.innerHTML = `<g class="pu-ln">${lines}</g><g class="pu-rays">${hot}</g><g class="pu-dots">${dots}</g>`;
    // подписи: поднятые к ответу — всегда; остальные — при наведении (или все свежие, если «Названия — всегда»)
    const always = cfg().names === "always";
    names.innerHTML = ns.filter(n => n.hot || (always && n.fresh)).slice(0, 10)
      .map(n => `<span class="${n.hot ? "hot" : ""}" style="left:${n.x.toFixed(0)}px;top:${n.y.toFixed(0)}px">${esc(n.t)}</span>`).join("");
    const empty = el("#pu-empty");
    empty.hidden = !!ns.length || think;
    if (!ns.length) empty.textContent = "Заметок пока нет. Запишите что-нибудь — здесь появится созвездие ваших записей, а когда Лира думает, видно, что она вспоминает.";
  }
  let tip = null;
  el("#pu-stage").addEventListener("pointermove", (e) => {
    if (!PU.nodes.length) return;
    const r = el("#pu-stage").getBoundingClientRect(), x = e.clientX - r.left, y = e.clientY - r.top;
    let best = null, bd = 196;
    for (const n of PU.nodes) { const d = (n.x - x) ** 2 + (n.y - y) ** 2; if (d < bd) { bd = d; best = n; } }
    if (!tip) { tip = document.createElement("span"); tip.className = "tip"; el("#pu-names").appendChild(tip); }
    if (!tip.isConnected) el("#pu-names").appendChild(tip);
    tip.hidden = !best;
    if (best) { tip.textContent = best.t + (best.f ? ` · ${best.f}` : ""); tip.style.left = best.x.toFixed(0) + "px"; tip.style.top = best.y.toFixed(0) + "px"; }
  });
  el("#pu-stage").addEventListener("pointerleave", () => { if (tip) tip.hidden = true; });
  el("#pu-stage").addEventListener("click", () => {
    if (!tip || tip.hidden) return;
    const n = PU.nodes.find(x => tip.textContent.startsWith(x.t));
    const a = A();
    if (n && a && a.open_settings) a.open_settings("notes", n.t);
  });
  function drawQ() {
    head();
    const q = el("#pu-q"), think = busy() && cfg().thoughts && PU.q;
    q.hidden = !think;
    box.classList.toggle("thinking", !!think);
    if (!think) return;
    el("#pu-qt").textContent = PU.q;
    const mem = PU.recall && PU.recall.memory && PU.recall.memory.length ? [{ t: "Вспомнила из памяти: " + PU.recall.memory.slice(0, 2).join(", "), s: "done", k: "mem" }] : [];
    const nt = PU.recall && PU.recall.notes.length ? [{ t: (PU.recall.notes.length === 1 ? "Подняла заметку «" + PU.recall.notes[0] + "»" : "Подняла заметки: " + PU.recall.notes.length), s: "done", k: "mem" }] : [];
    const steps = nt.concat(mem, PU.steps.map(s => ({ t: s.t, s: s.s })));
    if (PU.state === "thinking" && !PU.steps.some(s => s.s === "run")) steps.push({ t: "Собираю ответ", s: "run" });
    if (PU.state === "speaking") steps.push({ t: "Отвечаю", s: "done" });
    el("#pu-steps").innerHTML = steps.slice(-5).map(s => `<li class="${s.s === "run" ? "run" : s.s === "error" ? "err" : "ok"}${s.k ? " " + s.k : ""}"><i aria-hidden="true"></i>${esc(s.t)}</li>`).join("");
  }
  const hhmm = (ts) => { try { return new Date(ts * 1000).toLocaleTimeString(window.dwLocale ? dwLocale() : "ru", { hour: "2-digit", minute: "2-digit" }); } catch (e) { return ""; } };
  const ago = (ts) => { const m = Math.round((Date.now() / 1000 - ts) / 60); return m < 2 ? "только что" : m < 60 ? `${m} мин назад` : `в ${hhmm(ts)}`; };
  function drawCards() {
    const d = PU.data || {}, c = cfg(), out = [];
    const lead = PU.lead || ((d.leads || [])[0] && Date.now() / 1000 - d.leads[0].ts < 3600 ? d.leads[0] : null);
    const lb = el("#pu-lead");
    lb.hidden = !lead;
    if (lead) {
      lb.innerHTML = `<p class="pu-k"><i class="pu-live" aria-hidden="true"></i>Заявка с сайта · ${esc(ago(lead.ts))}</p>
        <b>${esc(lead.name || "Посетитель сайта")}</b><span>Контакт и разговор — в «Клиентах»</span>
        <button type="button" class="pu-btn main" data-go="clients">Открыть в «Клиентах»</button>`;
    }
    if (c.background) {
      if (d.diary && d.diary.text) out.push(`<article class="pu-card diary"><p class="pu-k">Дневник${d.diary.at ? " · " + esc(d.diary.at) : ""}</p><p class="pu-dt">${esc(d.diary.text)}</p><button type="button" class="pu-a" data-go="diary">Весь дневник</button></article>`);
      const r = d.radar;
      if (r && (r.trend || (r.items || []).length)) {
        const top = (r.items || [])[0];
        out.push(`<article class="pu-card radar"><p class="pu-k">Радар${r.n ? " · " + r.n + " за сутки" : ""}</p>`
          + (r.trend ? `<p class="pu-tr"><svg viewBox="0 0 40 18" aria-hidden="true"><rect x="0" y="12" width="6" height="6" rx="2"/><rect x="8" y="10" width="6" height="8" rx="2"/><rect x="16" y="8" width="6" height="10" rx="2"/><rect x="24" y="4" width="6" height="14" rx="2"/><rect x="32" y="0" width="6" height="18" rx="2"/></svg><span>${r.trend.status === "new" ? "Новая тема" : "Растёт"} «${esc(r.trend.name)}»<small>${r.trend.day} за сутки</small></span></p>` : "")
          + (top ? `<p class="pu-ri">${esc(top.title)}${top.src ? `<small>${esc(top.src)}</small>` : ""}</p>` : "")
          + `<button type="button" class="pu-a" data-go="insight">Открыть Радар</button></article>`);
      }
      if ((d.next || []).length) out.push(`<article class="pu-card next"><p class="pu-k">Дальше</p><ul>${d.next.map(x => `<li><time>${esc(hhmm(x.at))}</time>${esc(x.text)}</li>`).join("")}</ul><button type="button" class="pu-a" data-go="reminders">Все дела</button></article>`);
    }
    el("#pu-cards").innerHTML = out.join("");
    box.classList.toggle("has-cards", !!out.length);
  }
  box.addEventListener("click", (e) => {
    const b = e.target.closest("[data-go]"); if (!b) return;
    const a = A(); if (a && a.open_settings) a.open_settings(b.dataset.go);
    if (b.dataset.go === "clients") PU.lead = null;
  });
  function draw() {
    if (!PU.active) return;
    head(); drawCards(); drawQ();
    requestAnimationFrame(drawSky);
  }
  window.addEventListener("resize", () => { if (PU.active) drawSky(); });

  /* ---------- что показывать (шестерёнка) ---------- */
  const OPTS = [
    ["thoughts", "Мысли при ответе", "вопрос, поднятые заметки и шаги"],
    ["background", "Фоновые дела", "дневник, Радар, что дальше"],
    ["stars", "Созвездие заметок", "все записи точками, по папкам"],
    ["auto", "Открываться самому", "когда Лира думает или пришла заявка"],
  ];
  function pop(on) {
    const p = el("#pu-pop"), g = el("#pu-gear");
    if (on === undefined) on = p.hidden;
    p.hidden = !on; g.setAttribute("aria-expanded", String(!!on));
    if (!on) return;
    const c = cfg();
    p.innerHTML = OPTS.map(([k, t, s]) => `<label class="pu-o"><span><b>${t}</b><small>${s}</small></span><input type="checkbox" data-o="${k}"${c[k] ? " checked" : ""}><i aria-hidden="true"></i></label>`).join("")
      + `<div class="pu-seg" role="radiogroup" aria-label="Названия заметок"><span>Названия</span><button type="button" role="radio" data-n="hover" aria-checked="${c.names !== "always"}">по наведению</button><button type="button" role="radio" data-n="always" aria-checked="${c.names === "always"}">свежие всегда</button></div>`
      + `<div class="pu-seg" role="radiogroup" aria-label="Движение"><span>Движение</span><button type="button" role="radio" data-m="full" aria-checked="${c.motion !== "calm"}">живое</button><button type="button" role="radio" data-m="calm" aria-checked="${c.motion === "calm"}">тихое</button></div>`
      + `<p class="pu-hint">Убрать пульт совсем — студия → «Оформление»</p>`;
  }
  function setCfg(patch) {
    PU.cfg = Object.assign({}, cfg(), patch);
    core.call("settings_save", { patch: { ui: { pult: PU.cfg } } }).catch(() => { });
    document.body.classList.toggle("pu-calm", calm());
    document.body.classList.toggle("pu-names", cfg().names === "always");
    draw();
  }
  el("#pu-gear").onclick = (e) => { e.stopPropagation(); pop(); };
  el("#pu-pop").addEventListener("change", (e) => { const k = e.target.dataset.o; if (k) setCfg({ [k]: e.target.checked }); });
  el("#pu-pop").addEventListener("click", (e) => {
    const b = e.target.closest("button"); if (!b) return;
    if (b.dataset.n) setCfg({ names: b.dataset.n }); else if (b.dataset.m) setCfg({ motion: b.dataset.m });
    b.parentElement.querySelectorAll("button").forEach(x => x.setAttribute("aria-checked", String(x === b)));
  });
  document.addEventListener("pointerdown", (e) => { if (!el("#pu-pop").hidden && !e.target.closest("#pu-pop, #pu-gear")) pop(false); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !el("#pu-pop").hidden) { e.stopPropagation(); pop(false); el("#pu-gear").focus(); } }, true);

  /* ---------- первый раз ---------- */
  function onboard() { if (!PU.active || PU.seen) return; el("#pu-ob").hidden = false; setTimeout(() => el("#pu-ob-ok").focus(), 60); }
  function onboardDone() {
    el("#pu-ob").hidden = true; PU.seen = true;
    core.call("settings_save", { patch: { ui: { pult_seen: true } } }).catch(() => { });
  }
  el("#pu-ob-ok").onclick = onboardDone;
  el("#pu-ob-set").onclick = () => { onboardDone(); pop(true); };

  head();
})();
