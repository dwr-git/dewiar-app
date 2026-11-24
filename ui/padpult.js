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
  const DEF = { thoughts: true, background: true, auto: true, motion: "full" };
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
      <svg id="pu-sky" aria-label="Циферблат дня: прошедшее слева, впереди справа"></svg>
      <div class="pu-center" id="pu-center"></div>
      <div class="pu-feed" id="pu-feed" hidden></div>
      <div id="pu-names"></div>
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
    if (window.cloudLeave) cloudLeave();
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
  window.pultLeave = () => leave(false);                // «Облако Лиры» — своя вкладка рядом (ui/padcloud.js)
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
  /* «Циферблат дня» (16.11, владелец о созвездии: «выглядит странно и как будто бесполезно… хочется красоты и интерактива»).
     Круг — сутки вокруг «сейчас»: «сейчас» всегда наверху, слева уходит прошедшее (12 ч), справа — что впереди (12 ч).
     Точки — настоящее: записи дневника (что Лира сделала), находки Радара, заявки с сайта, напоминания и дела. Наведите —
     что это, нажмите — откроется в студии. Думает — по кругу бежит свет, в центре вопрос и шаги. */
  const KIND = { diary: ["Дневник", "diary"], radar: ["Радар", "insight"], lead: ["Заявка с сайта", "clients"],
                 remind: ["Напоминание", "reminders"], job: ["Дело по расписанию", "reminders"] };
  // находка Радара — сразу статья в «читалке» (владелец 17.11: «из Пульта открывается просто Радар, а не статья»)
  const goOf = (x) => x.k === "radar" && x.id ? "insight:" + x.id : KIND[x.k][1];
  const H12 = 12 * 3600;
  const left = (ts) => { const m = Math.round((ts - Date.now() / 1000) / 60); if (m < 1) return "сейчас";
    const h = Math.floor(m / 60), mm = m % 60; return "через " + (h ? `${h} ч ` : "") + (mm || !h ? `${mm} мин` : "").trim(); };
  function dial() {
    const st = el("#pu-stage"), svg = el("#pu-sky");
    const w = st.clientWidth || 400, h = st.clientHeight || 260;
    const wide = w >= 600 && cfg().background;
    const S = Math.max(150, Math.min(h - 16, wide ? w * 0.48 : w - 24, 330));
    const cx = wide ? Math.min(w * 0.3, S / 2 + 28) : w / 2, cy = h / 2, R = S / 2 - 14;
    svg.setAttribute("viewBox", `0 0 ${w} ${h}`); svg.setAttribute("width", w); svg.setAttribute("height", h);
    box.style.setProperty("--pu-cx", cx.toFixed(0) + "px"); box.style.setProperty("--pu-r", R.toFixed(0) + "px");
    const now = Date.now() / 1000;
    // как обычные часы (владелец 16.11: «22:30 должно быть слева сверху»): 12 наверху, 3 справа, стрелка — «сейчас».
    // 10 утра и 10 вечера — одно место на циферблате, поэтому дорожки две: внешняя — следующие 12 ч, внутренняя — прошедшие
    const ang = (ts) => { const d = new Date(ts * 1000); return ((d.getHours() % 12) * 3600 + d.getMinutes() * 60 + d.getSeconds()) / H12 * 2 * Math.PI; };
    const pt = (a, r) => [cx + r * Math.sin(a), cy - r * Math.cos(a)];
    const arc = (a0, a1, r) => { const [x0, y0] = pt(a0, r), [x1, y1] = pt(a1, r); return `M${x0.toFixed(1)} ${y0.toFixed(1)}A${r} ${r} 0 ${Math.abs(a1 - a0) > Math.PI ? 1 : 0} 1 ${x1.toFixed(1)} ${y1.toFixed(1)}`; };
    const an = ang(now), RP = R - 22;                                                       // RP — дорожка прошлого
    // часы: штрих — каждый час, подпись — 12, 3, 6, 9
    let ticks = "", labels = "";
    for (let hr = 0; hr < 12; hr++) {
      const a = hr / 12 * 2 * Math.PI, big = hr % 3 === 0;
      const [x0, y0] = pt(a, R - 8), [x1, y1] = pt(a, R - (big ? 15 : 12));
      ticks += `<path d="M${x0.toFixed(1)} ${y0.toFixed(1)}L${x1.toFixed(1)} ${y1.toFixed(1)}" class="${big ? "big" : ""}"/>`;
      if (big) { const [lx, ly] = pt(a, R - 38); labels += `<text x="${lx.toFixed(1)}" y="${(ly + 4).toFixed(1)}">${hr || 12}</text>`; }
    }
    // впереди — ярче у стрелки и бледнее к концу полусуток; прошлое — так же внутри
    let fut = "", past = "";
    for (let i = 0; i < 12; i++) {
      const a0 = an + i / 12 * 2 * Math.PI, a1 = a0 + 2 * Math.PI / 12 - 0.004, o = (0.55 * (1 - i / 12) + 0.05).toFixed(2);
      fut += `<path d="${arc(a0, a1, R)}" style="stroke-opacity:${o}"/>`;
      past += `<path d="${arc(an - (i + 1) / 12 * 2 * Math.PI + 0.004, an - i / 12 * 2 * Math.PI, RP)}" style="stroke-opacity:${(o * 0.7).toFixed(2)}"/>`;
    }
    // точки дня: будущее — снаружи, прошедшее — на внутренней дорожке; близкие по времени — друг над другом
    const ev = ((PU.data && PU.data.day) || []).filter(x => KIND[x.k] && Math.abs(x.ts - now) < H12).map(x => Object.assign({}, x, { a: ang(x.ts) }));
    if (PU.lead && !ev.some(x => x.k === "lead" && Math.abs(x.ts - PU.lead.ts) < 60)) ev.push({ k: "lead", ts: PU.lead.ts, t: PU.lead.name || "Посетитель сайта", a: ang(PU.lead.ts) });
    ev.sort((x, y) => x.ts - y.ts);
    const placed = [];
    for (const x of ev) {
      const was = x.ts < now, r0 = was ? RP : R, step = was ? -9 : 12;
      let lift = 0; while (placed.some(p => p.was === was && Math.abs(Math.atan2(Math.sin(p.a - x.a), Math.cos(p.a - x.a))) * r0 < 13 && p.lift === lift)) lift++;
      x.was = was; x.lift = Math.min(lift, was ? 1 : 3); placed.push(x);
      [x.x, x.y] = pt(x.a, r0 + x.lift * step);
    }
    PU.nodes = ev;
    const [nx, ny] = pt(an, R), [hx, hy] = pt(an, RP - 6);
    const think = busy() && cfg().thoughts;
    svg.innerHTML = `<circle class="pu-face" cx="${cx}" cy="${cy}" r="${R - 4}"/>
      <g class="pu-past">${past}</g><g class="pu-fut">${fut}</g>
      <g class="pu-ticks">${ticks}</g><g class="pu-hours">${labels}</g>
      <path class="pu-hand" d="M${hx.toFixed(1)} ${hy.toFixed(1)}L${nx.toFixed(1)} ${ny.toFixed(1)}"/>
      ${think ? `<g class="pu-sweep" style="transform-origin:${cx}px ${cy}px"><path d="${arc(an - 0.9, an, R)}"/></g>` : ""}
      <g class="pu-ev">${ev.map((x, i) => `<g class="e ${x.k}${x.was ? " was" : ""}" data-i="${i}" tabindex="0" role="button" aria-label="${esc(hhmm(x.ts) + " · " + KIND[x.k][0] + ": " + x.t)}"><circle cx="${x.x.toFixed(1)}" cy="${x.y.toFixed(1)}" r="9" class="hit"/><circle cx="${x.x.toFixed(1)}" cy="${x.y.toFixed(1)}" r="${x.k === "lead" ? 6 : x.was ? 3.8 : 4.6}" class="dot"/></g>`).join("")}</g>
      <circle class="pu-now" cx="${nx.toFixed(1)}" cy="${ny.toFixed(1)}" r="6"/>`;
    // центр: время, что дальше; лента «Сегодня» справа на широком листе
    const nextOne = ev.find(x => x.ts > now);
    const c = el("#pu-center");
    c.hidden = think;
    c.innerHTML = `<b class="pu-time">${esc(hhmm(now))}</b>`
      + (nextOne ? `<span class="pu-nx"><i class="${nextOne.k}"></i>${esc(hhmm(nextOne.ts))} · ${esc(nextOne.t)}</span><small>${esc(left(nextOne.ts))}</small>`
                 : `<span class="pu-nx quiet">Впереди пусто — можно отдыхать</span>`);
    const f = el("#pu-feed");
    f.hidden = !wide;
    if (wide) {
      const past = ev.filter(x => x.ts <= now).reverse().slice(0, 5);
      f.innerHTML = `<p class="pu-k">Сегодня</p>` + (past.length ? `<ul>${past.map(x => `<li><button type="button" data-go="${esc(goOf(x))}"><time>${esc(hhmm(x.ts))}</time><i class="${x.k}"></i><span>${esc(x.t)}</span></button></li>`).join("")}</ul>`
        : quiet());
    }
    el("#pu-empty").hidden = true;
  }
  // тихо — вместо пустой ленты одна находка Радара с «Сутью от Лиры»; нет и её — как раньше
  function quiet() {
    const pk = PU.data && PU.data.radar && PU.data.radar.pick;
    if (!pk) return `<p class="pu-fe">Пока тихо. Всё, что Лира сделает за день, — запишет в дневник, и оно появится здесь и на круге.</p>`;
    return `<button type="button" class="pu-pick" data-go="${pk.id ? "insight:" + esc(pk.id) : "insight"}"><span class="pu-k radar">Из Радара${pk.src ? " · " + esc(pk.src) : ""}</span>`
      + `<b>${esc(pk.title)}</b><span>${esc(pk.gist)}</span><small>Открыть в Радаре</small></button>`;
  }
  let tip = null;
  function tipFor(g) {
    const x = g ? PU.nodes[+g.dataset.i] : null;
    if (!tip) { tip = document.createElement("div"); tip.className = "pu-tip"; tip.setAttribute("role", "tooltip"); el("#pu-names").appendChild(tip); }
    tip.hidden = !x;
    if (!x) return;
    const now = Date.now() / 1000;
    tip.innerHTML = `<p class="pu-k ${x.k}">${esc(KIND[x.k][0])} · ${esc(hhmm(x.ts))}</p><p>${esc(x.t)}</p>`
      + (x.src || x.ts > now ? `<small>${esc([x.src, x.ts > now ? left(x.ts) : ""].filter(Boolean).join(" · "))}</small>` : "");
    const st = el("#pu-stage"), tw = Math.min(240, st.clientWidth - 24);
    tip.style.width = tw + "px";
    tip.style.left = Math.max(12, Math.min(st.clientWidth - tw - 12, x.x - tw / 2)) + "px";
    tip.style.top = (x.y > st.clientHeight / 2 ? x.y - 14 : x.y + 14) + "px";
    tip.classList.toggle("up", x.y > st.clientHeight / 2);
  }
  el("#pu-stage").addEventListener("pointerover", (e) => tipFor(e.target.closest(".pu-ev .e")));
  el("#pu-stage").addEventListener("pointerleave", () => tipFor(null));
  el("#pu-stage").addEventListener("focusin", (e) => tipFor(e.target.closest(".pu-ev .e")));
  el("#pu-stage").addEventListener("focusout", () => tipFor(null));
  const goEv = (g) => { const x = g && PU.nodes[+g.dataset.i]; const a = A(); if (x && a && a.open_settings) a.open_settings(goOf(x)); };
  el("#pu-stage").addEventListener("click", (e) => goEv(e.target.closest(".pu-ev .e")));
  el("#pu-stage").addEventListener("keydown", (e) => { if ((e.key === "Enter" || e.key === " ") && e.target.closest(".pu-ev .e")) { e.preventDefault(); goEv(e.target.closest(".pu-ev .e")); } });
  setInterval(() => { if (PU.active && !document.hidden) dial(); }, 60000);   // стрелка «сейчас» идёт
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
    el("#pu-steps").innerHTML = steps.slice(-3).map(s => `<li class="${s.s === "run" ? "run" : s.s === "error" ? "err" : "ok"}${s.k ? " " + s.k : ""}"><i aria-hidden="true"></i>${esc(s.t)}</li>`).join("");
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
          + (top ? `<button type="button" class="pu-ri" data-go="${top.id ? "insight:" + esc(top.id) : "insight"}">${esc(top.title)}${top.src ? `<small>${esc(top.src)}</small>` : ""}</button>` : "")
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
    requestAnimationFrame(dial);
  }
  window.addEventListener("resize", () => { if (PU.active) dial(); });

  /* ---------- что показывать (шестерёнка) ---------- */
  const OPTS = [
    ["thoughts", "Мысли при ответе", "вопрос, поднятые заметки и шаги"],
    ["background", "Фоновые дела", "дневник, Радар, что дальше"],
    ["auto", "Открываться самому", "когда Лира думает или пришла заявка"],
  ];
  function pop(on) {
    const p = el("#pu-pop"), g = el("#pu-gear");
    if (on === undefined) on = p.hidden;
    p.hidden = !on; g.setAttribute("aria-expanded", String(!!on));
    if (!on) return;
    const c = cfg();
    p.innerHTML = OPTS.map(([k, t, s]) => `<label class="pu-o"><span><b>${t}</b><small>${s}</small></span><input type="checkbox" data-o="${k}"${c[k] ? " checked" : ""}><i aria-hidden="true"></i></label>`).join("")
      + `<div class="pu-seg" role="radiogroup" aria-label="Движение"><span>Движение</span><button type="button" role="radio" data-m="full" aria-checked="${c.motion !== "calm"}">живое</button><button type="button" role="radio" data-m="calm" aria-checked="${c.motion === "calm"}">тихое</button></div>`
      + `<p class="pu-hint">Убрать пульт совсем — студия → «Оформление»</p>`;
  }
  function setCfg(patch) {
    PU.cfg = Object.assign({}, cfg(), patch);
    core.call("settings_save", { patch: { ui: { pult: PU.cfg } } }).catch(() => { });
    document.body.classList.toggle("pu-calm", calm());
    draw();
  }
  el("#pu-gear").onclick = (e) => { e.stopPropagation(); pop(); };
  el("#pu-pop").addEventListener("change", (e) => { const k = e.target.dataset.o; if (k) setCfg({ [k]: e.target.checked }); });
  el("#pu-pop").addEventListener("click", (e) => {
    const b = e.target.closest("button"); if (!b) return;
    if (b.dataset.m) setCfg({ motion: b.dataset.m });
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
