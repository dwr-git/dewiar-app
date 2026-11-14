/* Студия → «Работа» → «Радар» (docs/RADAR.md): Лира-аналитик ниши. Разметка — settings.html #p-insight, вид — insight.css,
   ядро — core/insight.py и engine_insight.py (команды insight_*). Все строки — словари (insight.*), русский и английский.
   Вкладки: «Пульс» (поле сигналов, бриф дня, тренды), «Лента», «Тренды», «Источники», «Разум», «Галактика», «Управление». */
(function () {
  const T = (k, p) => window.t("insight." + k, p);
  const RD = { tab: "pulse", d: {}, feed: { q: "", type: "", min: 0, sort: "new", watch: false }, tseg: "all", gal: null, galSel: -1, busy: false };
  const q = (s, el) => (el || document).querySelector(s);
  const qa = (s, el) => [...(el || document).querySelectorAll(s)];
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const call = (cmd, a) => core.call(cmd, a || {});
  const REDUCE = matchMedia("(prefers-reduced-motion: reduce)");
  const loc = () => (window.dwLocale ? dwLocale() : "ru-RU");
  const fmt = (n, d) => (n == null ? "—" : Number(n).toLocaleString(loc(), { maximumFractionDigits: d == null ? 1 : d }));

  /* Цвета — из переменных темы (insight.css): так «Радар» в любой теме студии из её же материала. Сигнал 0..10 —
     от светлого к глубокому фирменному синему (у тёмных тем — к яркому), срочное (от порога) — розовый. */
  const hexRGB = (h) => { h = String(h).trim().replace("#", ""); if (h.length === 3) h = h.replace(/./g, "$&$&"); const n = parseInt(h, 16) || 0; return [n >> 16 & 255, n >> 8 & 255, n & 255]; };
  let PAL = null;
  function pal() {
    if (PAL) return PAL;
    const cs = getComputedStyle(q("#p-insight")), v = (k) => cs.getPropertyValue(k).trim();
    PAL = { c0: hexRGB(v("--rd-c0")), c1: hexRGB(v("--rd-c1")), hot: v("--rd-hot"), ok: v("--rd-ok"), grid: v("--rd-grid"), label: v("--rd-label"),
      now: v("--rd-now"), ink: v("--ink") || "#1d2230", dim: v("--dim") || "rgba(0,0,0,.45)", light: document.documentElement.classList.contains("st-light"),
      cl: v("--rd-cl").split(",").map(x => x.trim()).filter(Boolean) };
    PAL.hotRGB = hexRGB(PAL.hot); PAL.c1hex = v("--rd-c1");
    return PAL;
  }
  const hotMin = () => (RD.st && RD.st.urgent_min) || 8.5;
  function sigRGB(s) {
    const P = pal(); s = Number(s) || 0;
    if (s >= hotMin()) return P.hotRGB;
    const f = Math.max(0, Math.min(1, s / hotMin()));
    return P.c0.map((v, k) => Math.round(v + (P.c1[k] - v) * f));
  }
  const sigColor = (s, al) => { const c = sigRGB(s); return al == null ? `rgb(${c})` : `rgba(${c},${al})`; };
  const clColor = (i) => { const c = pal().cl; return c[i % c.length] || "#4F6CF0"; };

  function ago(ts) {
    if (!ts) return T("never");
    const m = Math.max(0, Math.round((Date.now() / 1000 - ts) / 60));
    return m < 2 ? T("now") : m < 60 ? T("min_ago", { n: m }) : m < 1440 ? T("h_ago", { n: Math.round(m / 60) }) : T("d_ago", { n: Math.round(m / 1440) });
  }
  function spark(arr, color, w, h) {
    w = w || 100; h = h || 30;
    const v = (arr || []).map(Number), mx = Math.max(1, ...v), n = Math.max(1, v.length - 1);
    const pts = v.map((y, i) => [i * w / n, h - 3 - (y / mx) * (h - 6)]);
    const line = pts.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1)).join("");
    const id = "g" + Math.random().toString(36).slice(2, 8), last = pts[pts.length - 1] || [0, h];
    return `<svg class="rd-spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" aria-hidden="true"><defs><linearGradient id="${id}" x1="0" x2="0" y1="0" y2="1">
      <stop offset="0" stop-color="${color}" stop-opacity=".35"/><stop offset="1" stop-color="${color}" stop-opacity="0"/></linearGradient></defs>
      <path d="${line}L${w} ${h}L0 ${h}Z" fill="url(#${id})"/><path d="${line}" fill="none" stroke="${color}" stroke-width="1.6" vector-effect="non-scaling-stroke"/>
      <path d="M${last[0].toFixed(1)} ${last[1].toFixed(1)}h0" stroke="${color}" stroke-width="6" stroke-linecap="round" vector-effect="non-scaling-stroke"/></svg>`;
  }
  const stColor = (st) => { const P = pal(); return st === "new" ? P.c1hex : st === "up" ? P.hot : st === "down" ? P.dim : `rgb(${P.c0.map((v, k) => Math.round((v + P.c1[k]) / 2))})`; };
  const stText = (st) => T("st." + st);
  const typeText = (t) => T("type." + (t || "news"));
  function empty(title, text, btn) {
    return `<div class="rd-card rd-empty"><b>${esc(title)}</b>${esc(text)}${btn ? `<div style="margin-top:14px"><button class="btn primary rd-btn" data-go="sources">${esc(btn)}</button></div>` : ""}</div>`;
  }
  function bindGo(el) { qa("[data-go]", el).forEach(b => b.onclick = () => tab(b.dataset.go)); }
  function openUrl(u) { if (!/^https?:\/\//.test(u || "")) return; if (typeof openExt === "function") openExt(u); else window.open(u, "_blank", "noopener"); }

  /* ---------- шапка: счётчики ---------- */
  function chips(st) {
    if (!st) return;
    RD.st = st;
    q("#rd-room").dataset.run = st.running ? "1" : "";
    q("#rd-chips").innerHTML =
      `<span class="rd-chip"><i></i><b>${st.sources}</b> ${esc(T("chip.sources", { n: st.sources }))}</span>`
      + `<span class="rd-chip"><b>${st.day}</b> ${esc(T("chip.day"))}</span>`
      + `<span class="rd-chip"><i style="background:var(--rd-c0)"></i>${esc(T("chip.queue"))} <b>${st.queue}</b></span>`
      + `<span class="rd-chip">${esc(st.running ? T("run." + st.running.k, { x: st.running.x }) : T("chip.tick", { t: ago(st.last_tick) }))}</span>`
      + `<span class="rd-chip">${esc(T("chip.limit", { a: st.used_today, b: st.daily_max }))}</span>`
      + `<button class="btn rd-btn" id="rd-refresh">${esc(T("refresh"))}</button>`;
    q("#rd-refresh").onclick = async () => { try { await call("insight_refresh"); toast(T("refresh.started")); setTimeout(() => load(), 2500); } catch (e) { toast(e.message); } };
  }

  /* ---------- «Пульс» ---------- */
  function renderPulse(d) {
    const el = q("#rd-pulse");
    chips(d.stats);
    if (!d.stats.sources_all) {
      el.innerHTML = empty(T("empty.title"), T("empty.text"), T("empty.btn")); bindGo(el); return;
    }
    const b = d.brief && d.brief.headline ? d.brief : null;
    const tr = d.trends || [];
    el.innerHTML = `<div class="rd-card rd-field" id="rd-field"><h3>${esc(T("field.title"))} <small>${esc(T("field.week", { n: d.week }))}</small></h3>
        <div class="rd-legend">${esc(T("weak"))}<i></i>${esc(T("strong"))}<em>${esc(T("urgent.l"))}</em></div><canvas id="rd-fc" aria-label="${esc(T("field.title"))}" role="img"></canvas><div class="rd-tops" id="rd-tops"></div></div>
      <div class="rd-pulse">
        <div class="rd-card rd-brief">${b ? `<div class="meta"><span>${esc(T("brief.at", { t: ago(b.at) }))}</span><span>${esc(T("brief.n", { n: b.n }))}</span></div>
          <h2>${esc(b.headline)}</h2><ul>${(b.points || []).map(p => `<li>${esc(p)}</li>`).join("")}</ul>
          ${(b.main || []).length ? `<div class="rd-main"><span>${esc(T("brief.main"))}</span>${b.main.map((m, i) => `<div class="rd-mainit"><span class="n">${i + 1}</span><div>
            <b><a href="#" ${m.id ? `data-rid="${esc(m.id)}"` : `data-url="${esc(m.url)}"`}>${esc(m.title)}</a></b><p>${esc(m.why_brief || m.summary)}</p></div></div>`).join("")}</div>` : ""}`
          : `<div class="rd-empty"><b>${esc(T("brief.none"))}</b>${esc(T("brief.none.t"))}<div style="margin-top:14px"><button class="btn rd-btn" id="rd-mkbrief">${esc(T("brief.make"))}</button></div></div>`}
        </div>
        <div class="rd-side">${askCard(tr)}<div class="rd-card"><h3>${esc(T("trends"))} <small><a href="#" data-go="trends">${esc(T("all"))}</a></small></h3>
          ${tr.length ? tr.map(t => `<div class="rd-trend-row" data-tq="${esc(t.name)}"><div><b>${esc(t.name)}</b><small class="rd-st-${t.status}">${esc(stText(t.status))}</small>
            <small> · ${esc(T("srcs", { n: t.sources }))}</small></div>${spark(t.spark, stColor(t.status))}<span class="v">${t.day}</span></div>`).join("")
            : `<p class="rd-hint">${esc(T("trends.none"))}</p>`}</div></div>
      </div>`;
    bindGo(el);
    qa("[data-url]", el).forEach(a => a.onclick = (e) => { e.preventDefault(); openUrl(a.dataset.url); });
    qa("[data-tq]", el).forEach(r => r.onclick = () => { RD.feed.q = r.dataset.tq; tab("feed"); });
    const mk = q("#rd-mkbrief"); if (mk) mk.onclick = async () => { mk.disabled = true; try { await call("insight_brief"); toast(T("brief.making")); setTimeout(load, 6000); } catch (e) { toast(e.message); } };
    bindAsk(el);
    drawField(d.field || []);
  }

  /* «Спросите Лиру о теме» — прямо в «Пульсе» (владелец 12.11: строка «Спросите аналитика…» внизу была непонятной и
     неудобной): поле с кнопкой, три готовых вопроса из данных, ответ здесь же — по разобранному, со ссылками [n]. */
  const IC_SEND = '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12h13M13 6l6 6-6 6"/></svg>';
  function askCard(tr) {
    const up = (tr || []).find(t => t.status === "up" || t.status === "new");
    const sug = [T("ask.s1"), up ? T("ask.s2", { t: up.name }) : T("ask.s2b"), T("ask.s3")];
    return `<div class="rd-card rd-askc"><h3>${esc(T("ask.title"))}</h3><p class="rd-hint">${esc(T("ask.hint"))}</p>
      <form class="rd-askf" id="rd-askf"><input type="text" id="rd-ask-q" maxlength="500" placeholder="${esc(T("ask.ph"))}" aria-label="${esc(T("ask.title"))}">
        <button class="btn primary" type="submit" title="${esc(T("ask.btn"))}" aria-label="${esc(T("ask.btn"))}">${IC_SEND}</button></form>
      <div class="rd-sugg">${sug.map(x => `<button type="button" class="rd-sg">${esc(x)}</button>`).join("")}</div>
      <div class="rd-ans" id="rd-ans" aria-live="polite">${RD.ans ? ansHtml(RD.ans) : ""}</div></div>`;
  }
  function ansHtml(a) {
    if (a.wait) return `<div class="rd-wait"><i></i><i></i><i></i><span>${esc(T("ask.wait"))}</span></div>`;
    if (a.err) return `<p class="rd-aerr">${esc(a.err)}</p>`;
    // владелец 14.11: «как каша — сложно читать»: главное крупно, пункты с темой, «→ что сделать» отдельно
    const refs = (h) => h.replace(/\s*\[(\d{1,2})\]([.,;:!?)]?)/g, (m, n, p) => `<span class="rd-refw">\u00a0<a href="#" class="rd-ref" data-ref="${n}">${n}</a>${p}</span>`);
    const lines = esc(a.text).split(/\n+/).map(x => x.trim()).filter(Boolean);
    let body = "", list = [];
    const flush = () => { if (list.length) body += `<ul class="rd-alist">${list.join("")}</ul>`; list = []; };
    lines.forEach((x, i) => {
      if (/^[•\-*]\s*/.test(x)) {
        const t = x.replace(/^[•\-*]\s*/, ""), m = t.match(/^([^[]{2,64}?)(\s[—–-]\s|:\s)(.+)$/);
        list.push(`<li>${m ? `<b>${m[1]}</b>${m[2].trim() === ":" ? ": " : " — "}${refs(m[3])}` : refs(t)}</li>`); return;
      }
      flush();
      if (/^(→|->)\s*/.test(x)) body += `<p class="rd-anext">${refs(x.replace(/^(→|->)\s*/, ""))}</p>`;
      else body += `<p${i === 0 ? ' class="rd-alead"' : ""}>${refs(x)}</p>`;
    });
    flush();
    return `<div class="rd-aq">${esc(a.q)}</div><div class="rd-at">${body}</div>
      ${(a.refs || []).length ? `<ol class="rd-arefs">${a.refs.map(r => `<li value="${r.n}"><a href="#" data-url="${esc(r.url)}">${esc(r.title)}</a> <small>${esc(r.source || "")}</small></li>`).join("")}</ol>` : ""}
      <button type="button" class="rd-achat" id="rd-achat">${esc(T("ask.chat"))}</button>`;
  }
  async function askNow(v) {
    v = String(v || "").trim(); if (!v || (RD.ans && RD.ans.wait)) return;
    const box = () => q("#rd-ans");
    RD.ans = { q: v, wait: true }; if (box()) box().innerHTML = ansHtml(RD.ans);
    try { RD.ans = Object.assign({ q: v }, await call("insight_question", { q: v })); }
    catch (e) { RD.ans = { q: v, err: e.message || String(e) }; }
    if (box()) { box().innerHTML = ansHtml(RD.ans); bindAns(box()); }
  }
  function bindAns(b) {
    qa("[data-url]", b).forEach(a => a.onclick = (e) => { e.preventDefault(); openUrl(a.dataset.url); });
    qa("[data-ref]", b).forEach(a => a.onclick = (e) => { e.preventDefault(); const r = (RD.ans.refs || []).find(x => String(x.n) === a.dataset.ref); if (r) { if (r.id) rdRead(r.id); else openUrl(r.url); } });
    const c = q("#rd-achat", b); if (c) c.onclick = () => { const v = T("ask.prefix") + " " + RD.ans.q; if (typeof qaAsk === "function") qaAsk(v); else core.call("say", { text: v }).catch(() => {}); };
  }
  function bindAsk(el) {
    const f = q("#rd-askf", el); if (!f) return;
    f.onsubmit = (e) => { e.preventDefault(); const i = q("#rd-ask-q"); const v = i.value.trim(); if (!v) { i.focus(); return; } i.value = ""; askNow(v); };
    qa(".rd-sg", el).forEach(b => b.onclick = () => askNow(b.textContent));
    bindAns(q("#rd-ans", el));
  }

  function drawField(pts) {
    const cv = q("#rd-fc"); if (!cv) return;
    const box = cv.getBoundingClientRect(), dpr = window.devicePixelRatio || 1;
    cv.width = Math.max(1, box.width * dpr); cv.height = Math.max(1, box.height * dpr);
    const g = cv.getContext("2d"), W = box.width, H = box.height, L = 30, B = 22, Tp = 34, R = 10, C = pal();
    const X = (x) => L + (x / 7) * (W - L - R), Y = (s) => Tp + (1 - s / 10) * (H - Tp - B);
    // точки одного часа не ложатся друг на друга: лёгкий разброс по стабильному хешу
    const jit = (id, k) => { let h = 0; for (const c of id + k) h = (h * 31 + c.charCodeAt(0)) | 0; return ((h % 1000) / 1000 - .5); };
    const P = pts.map(p => ({ ...p, px: Math.max(L + 6, Math.min(W - R - 6, X(p.x) + jit(p.id, "x") * 18)), py: Y(p.s) + jit(p.id, "y") * 10, r: 3 + p.s * .55 }));
    const top = [...P].sort((a, b) => b.s - a.s).slice(0, 3);
    let t0 = performance.now(), hover = null;
    function frame(now) {
      g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, W, H);
      g.strokeStyle = C.grid; g.lineWidth = 1; g.fillStyle = C.dim; g.font = "11px Manrope, Ubuntu, sans-serif";
      [0, 5, 10].forEach(s => { g.beginPath(); g.moveTo(L, Y(s)); g.lineTo(W - R, Y(s)); g.stroke(); g.fillText(String(s), 6, Y(s) + 4); });
      for (let d = 0; d <= 7; d++) {
        g.beginPath(); g.moveTo(X(d), Tp); g.lineTo(X(d), H - B); g.stroke();
        if (d < 7) { const dt = new Date(Date.now() - (7 - d - .5) * 864e5); g.fillText(dt.toLocaleDateString(loc(), { weekday: "short", day: "numeric" }), X(d + .5) - 18, H - 6); }
      }
      // последние сутки — светлее: «сейчас»
      g.fillStyle = C.now; g.fillRect(X(6), Tp, X(7) - X(6), H - Tp - B);
      const k = REDUCE.matches ? 1 : Math.min(1, (now - t0) / 900);
      for (const p of P.slice().sort((a, b) => a.s - b.s)) {      // сильные — поверх слабых
        const r = p.r * (p === hover ? 1.4 : 1) * (0.4 + .6 * k), hot = p.s >= hotMin();
        if (hot) { g.fillStyle = sigColor(p.s, .16 * k); g.beginPath(); g.arc(p.px, p.py, r * 2.4, 0, 7); g.fill(); }
        g.fillStyle = sigColor(p.s, (.55 + p.s / 22) * k); g.beginPath(); g.arc(p.px, p.py, r, 0, 7); g.fill();
        g.strokeStyle = C.light ? `rgba(255,255,255,${.9 * k})` : `rgba(0,0,0,${.25 * k})`; g.lineWidth = 1.2; g.stroke();
      }
      // 13.11 (владелец: «в красивом блоке постоянно какие-то надписи — так и должно быть?»): подписи трёх сильнейших стопкой
      // в углу закрывали свежие точки и тянули линии через всё поле. Теперь у точки — только номер, сами заголовки — списком
      // под полем (#rd-tops): видно, что это «сильнейшее за неделю», и нажатием открывается статья.
      g.font = "700 11px Manrope, Ubuntu, sans-serif"; g.textAlign = "center"; g.textBaseline = "middle";
      top.forEach((p, i) => {
        const bx = Math.min(W - R - 9, p.px + p.r + 7), by = Math.max(Tp + 9, p.py - p.r - 7);
        g.globalAlpha = k; g.fillStyle = C.label; g.beginPath(); g.arc(bx, by, 9, 0, 7); g.fill();
        g.strokeStyle = sigColor(p.s, .8); g.lineWidth = 1.5; g.stroke();
        g.fillStyle = C.ink; g.fillText(String(i + 1), bx, by + .5); g.globalAlpha = 1;
      });
      g.textAlign = "start"; g.textBaseline = "alphabetic";
      if (k < 1) requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
    const tops = q("#rd-tops");
    if (tops) {
      tops.innerHTML = top.length ? `<span>${esc(T("field.tops"))}</span>` + top.map((p, i) => `<button type="button" data-rid="${esc(p.id)}"><b>${i + 1}</b><em>${esc(p.title)}</em><small>${esc(p.src || "")} · ${fmt(p.s)}</small></button>`).join("") : "";
      tops.querySelectorAll("button").forEach(b => b.onclick = () => rdRead(b.dataset.rid));
    }
    const tip = document.createElement("div"); tip.className = "rd-tip"; tip.hidden = true; q("#rd-field").appendChild(tip);
    const near = (e) => { const r = cv.getBoundingClientRect(), x = e.clientX - r.left, y = e.clientY - r.top; let best = null, bd = 18 * 18;
      for (const p of P) { const dd = (p.px - x) ** 2 + (p.py - y) ** 2; if (dd < bd) { bd = dd; best = p; } } return [best, x, y]; };
    cv.onmousemove = (e) => { const [p, x, y] = near(e); if (p !== hover) { hover = p; t0 = -1e9; requestAnimationFrame(frame); }
      if (!p) { tip.hidden = true; return; } tip.hidden = false; tip.innerHTML = `${esc(p.title)}<small>${esc(p.src)} · ${esc(T("signal"))} ${fmt(p.s)}</small>`;
      tip.style.left = Math.min(x + 26, cv.clientWidth - 330) + "px"; tip.style.top = (y + 18) + "px"; };
    cv.onmouseleave = () => { tip.hidden = true; hover = null; requestAnimationFrame(frame); };
    cv.onclick = (e) => { const [p] = near(e); if (p) rdRead(p.id); };
  }

  const IC_UP = '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M7 11v9H4v-9zM7 11l4-7c1.5 0 2.5 1 2.2 2.6L12.6 10H19a2 2 0 0 1 2 2.3l-1.2 6A2 2 0 0 1 17.8 20H7"/></svg>';
  const IC_DOWN = '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.8" style="transform:scaleY(-1)"><path d="M7 11v9H4v-9zM7 11l4-7c1.5 0 2.5 1 2.2 2.6L12.6 10H19a2 2 0 0 1 2 2.3l-1.2 6A2 2 0 0 1 17.8 20H7"/></svg>';
  /* ---------- «Лента» ---------- */
  function itemHtml(x) {
    return `<article class="rd-item" data-id="${esc(x.id)}"><span class="bar" style="background:${sigColor(x.signal)}"></span>
      <div><h4><a href="#" data-rid="${esc(x.id)}">${esc(x.title)}</a></h4>
        <p>${esc(x.summary)}${x.why ? ` <em>${esc(x.why)}</em>` : ""}</p>
        <div class="rd-meta"><span>${esc(x.src || "")}</span><span>${esc(ago(x.ts))}</span><span>${esc(typeText(x.type))}</span>
          ${(x.tags || []).map(t => `<span class="rd-tag" data-tag="${esc(t)}">#${esc(t)}</span>`).join("")}
          <button class="rd-fb ${x.fb > 0 ? "on" : ""}" data-fb="1" title="${esc(T("fb.up"))}" aria-label="${esc(T("fb.up"))}">${IC_UP}</button>
          <button class="rd-fb ${x.fb < 0 ? "on" : ""}" data-fb="-1" title="${esc(T("fb.down"))}" aria-label="${esc(T("fb.down"))}">${IC_DOWN}</button>
          <button class="rd-fb ${x.watch ? "on" : ""}" data-watch="1" title="${esc(T("watch"))}" aria-label="${esc(T("watch"))}">${x.watch ? "★" : "☆"}</button></div></div>
      <div class="rd-sig"><b style="color:${sigColor(x.signal)}">${fmt(x.signal)}</b><small>${esc(T("signal"))}</small></div></article>`;
  }
  async function renderFeed() {
    const el = q("#rd-feed"), f = RD.feed;
    if (!q("#rd-fq", el)) {
      el.innerHTML = `<div class="rd-filters"><input type="search" id="rd-fq" placeholder="${esc(T("feed.search"))}" aria-label="${esc(T("feed.search"))}">
        <select id="rd-ft" aria-label="${esc(T("feed.type"))}"><option value="">${esc(T("feed.anytype"))}</option>${["release", "analysis", "news", "practice", "incident", "opinion", "video", "research"].map(t => `<option value="${t}">${esc(typeText(t))}</option>`).join("")}</select>
        <select id="rd-fm" aria-label="${esc(T("feed.min"))}"><option value="0">${esc(T("feed.anymin"))}</option><option value="5">${esc(T("feed.min5"))}</option><option value="7">${esc(T("feed.min7"))}</option></select>
        <select id="rd-fs" aria-label="${esc(T("feed.sort"))}"><option value="new">${esc(T("feed.new"))}</option><option value="signal">${esc(T("feed.strong"))}</option></select>
        <label class="rd-tog"><span class="tg"><input type="checkbox" id="rd-fw"><i></i></span>${esc(T("watched"))}</label></div><div class="rd-items" id="rd-fl"></div>`;
      let tm = 0;
      q("#rd-fq").oninput = (e) => { clearTimeout(tm); tm = setTimeout(() => { f.q = e.target.value.trim(); renderFeed(); }, 250); };
      q("#rd-ft").onchange = (e) => { f.type = e.target.value; renderFeed(); };
      q("#rd-fm").onchange = (e) => { f.min = +e.target.value; renderFeed(); };
      q("#rd-fs").onchange = (e) => { f.sort = e.target.value; renderFeed(); };
      q("#rd-fw").onchange = (e) => { f.watch = e.target.checked; renderFeed(); };
    }
    const fq = q("#rd-fq"); if (fq.value.trim() !== (f.q || "")) fq.value = f.q;   // №670: не трогать то, что человек печатает (пробел в конце не съедать)
    let d; try { d = await call("insight_feed", f); } catch (e) { toast(e.message); return; }
    chips(d.stats);
    const box = q("#rd-fl");
    box.innerHTML = d.items.length ? d.items.map(itemHtml).join("") : (d.stats.sources_all ? `<div class="rd-card rd-empty">${esc(T("feed.empty"))}</div>` : empty(T("empty.title"), T("empty.text"), T("empty.btn")));
    bindGo(box);
    qa("[data-url]", box).forEach(a => a.onclick = (e) => { e.preventDefault(); openUrl(a.dataset.url); });
    qa("[data-tag]", box).forEach(a => a.onclick = () => { f.q = a.dataset.tag; renderFeed(); });
    qa(".rd-item", box).forEach(it => {
      const id = it.dataset.id;
      qa("[data-fb]", it).forEach(b => b.onclick = async () => { const v = b.classList.contains("on") ? 0 : +b.dataset.fb; await call("insight_mark", { id, fb: v }).catch(() => {});
        qa("[data-fb]", it).forEach(x => x.classList.toggle("on", +x.dataset.fb === v)); });
      const w = q("[data-watch]", it); w.onclick = async () => { const on = !w.classList.contains("on"); await call("insight_mark", { id, watch: on }).catch(() => {});
        w.classList.toggle("on", on); w.textContent = on ? "★" : "☆"; };
    });
    if (RD.focus) { const it = q(`.rd-item[data-id="${RD.focus}"]`, box); RD.focus = ""; if (it) { it.scrollIntoView({ block: "center", behavior: REDUCE.matches ? "auto" : "smooth" }); it.style.outline = "2px solid var(--accent)"; setTimeout(() => it.style.outline = "", 2400); } }
  }

  /* ---------- «Тренды» ---------- */
  async function renderTrends() {
    const el = q("#rd-trends");
    let d; try { d = await call("insight_trends"); } catch (e) { toast(e.message); return; }
    chips(d.stats);
    const list = d.trends.filter(t => RD.tseg === "all" || (RD.tseg === "topic" ? t.kind === "topic" : t.kind === "entity"));
    el.innerHTML = `<div class="rd-tbar"><div class="stabs rd-seg" role="tablist">
        ${[["all", "seg.all"], ["topic", "seg.topic"], ["entity", "seg.entity"]].map(([k, l]) => `<button data-s="${k}" class="${RD.tseg === k ? "on" : ""}">${esc(T(l))}</button>`).join("")}</div>
        <span class="rd-hint">${esc(T("trends.how"))}</span></div>
      ${list.length ? `<div class="rd-tgrid">${list.map(t => `<div class="rd-tcard" data-tq="${esc(t.name)}" tabindex="0"><div class="h"><b>${esc(t.name)}</b><small>${esc(T("impulse"))} ${t.impulse > 0 ? "+" : ""}${fmt(t.impulse, 2)}</small></div>
        <div class="st" style="color:${stColor(t.status)}">${esc(stText(t.status))}</div>${spark(t.spark, stColor(t.status), 120, 50)}
        <div class="rd-tnums"><div><b>${t.day}</b><small>${esc(T("t.day"))}</small></div><div><b>${fmt(t.norm, 2)}</b><small>${esc(T("t.norm"))}</small></div><div><b>${t.sources}</b><small>${esc(T("t.src"))}</small></div></div></div>`).join("")}</div>`
        : (d.stats.sources_all ? `<div class="rd-card rd-empty">${esc(T("trends.none"))}</div>` : empty(T("empty.title"), T("empty.text"), T("empty.btn")))}`;
    bindGo(el);
    qa("[data-s]", el).forEach(b => b.onclick = () => { RD.tseg = b.dataset.s; renderTrends(); });
    qa("[data-tq]", el).forEach(c => { c.onclick = () => { RD.feed.q = c.dataset.tq; tab("feed"); }; c.onkeydown = (e) => { if (e.key === "Enter") c.click(); }; });
  }

  /* ---------- «Источники» ---------- */
  const KIND = { rss: "RSS", site: "WEB", youtube: "YT", telegram: "TG", reddit: "RDT", github: "GH", vk: "VK", dzen: "DZN", article: "ART" };
  const IC = {
    crawl: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M20 12a8 8 0 1 1-2.3-5.7M20 4v5h-5"/></svg>',
    feed: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 6h16M4 12h16M4 18h10"/></svg>',
    del: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/></svg>' };
  /* состояние источника: ошибка с объяснением, «ничего не нашлось» с подсказкой, прочитан, ждёт */
  const why = (code) => T("src.why." + code.slice(1));
  function srcState(s) {
    if (s.err && s.err[0] === "@") return `<span class="rd-state err"><i></i>${esc(T("src.err"))}</span><small class="rd-why">${esc(why(s.err))}</small>`;
    if (s.err) return `<span class="rd-state err" title="${esc(s.err)}"><i></i>${esc(T("src.err"))}</span>`;
    if (s.last && s.found === 0) return `<span class="rd-state warn"><i></i>${esc(T("src.empty"))}</span><small class="rd-why">${esc(T(s.kind === "telegram" ? "src.empty.tg" : "src.empty.t"))}</small>`;
    if (s.last) return `<span class="rd-state"><i></i>${esc(T("src.read", { t: ago(s.last) }))}</span>`;
    return `<span class="rd-state wait"><i></i>${esc(T("src.wait"))}</span>`;
  }
  async function renderSources() {
    const el = q("#rd-sources");
    let d; try { d = await call("insight_sources"); } catch (e) { toast(e.message); return; }
    chips(d.stats);
    // студия не по-русски (0.96, владелец 13.11: «переходим на международные сервисы») — без VK и Дзена в подсказке; читать их Радар умеет
    const intl = !!(window.dwLang && dwLang() !== "ru");
    const kinds = ["site", "rss", "youtube", "telegram", ...(intl ? [] : ["vk", "dzen"]), "reddit", "github", "article"];
    const ph = intl ? "https://techcrunch.com/category/artificial-intelligence/&#10;https://www.youtube.com/@lexfridman&#10;r/LocalLLaMA"
      : "https://vc.ru/ai&#10;https://www.youtube.com/@lexfridman&#10;@ai_newz";
    el.innerHTML = `<div class="rd-two"><div class="rd-card"><h3>${esc(T("src.add"))}</h3><p class="rd-hint">${esc(T("src.add.t"))}</p>
        <div class="rd-kinds">${kinds.map(k => `<span>${esc(T("kind." + k))}</span>`).join("")}</div>
        <textarea id="rd-sa" placeholder="${ph}" aria-label="${esc(T("src.add"))}"></textarea>
        <div class="rd-row-end"><button class="btn primary rd-btn" id="rd-sab">${esc(T("src.add.btn"))}</button></div></div>
      <div class="rd-card"><h3>${esc(T("one"))}</h3><p class="rd-hint">${esc(T("one.t"))}</p><input type="url" id="rd-one" placeholder="https://…" style="width:100%" aria-label="${esc(T("one"))}">
        <div class="rd-row-end"><button class="btn rd-btn" id="rd-oneb">${esc(T("one.btn"))}</button></div><div id="rd-oner"></div></div></div>
      <div class="rd-card"><h3>${esc(T("src.mine"))} <small>${esc(T("src.active", { a: d.sources.filter(s => s.on !== false).length, b: d.sources.length }))}</small></h3>
        ${d.sources.length ? `<div style="overflow-x:auto"><table class="rd-srcs"><thead><tr><th></th><th>${esc(T("src.col.src"))}</th><th>${esc(T("src.col.state"))}</th><th>${esc(T("src.col.week"))}</th><th>${esc(T("src.col.avg"))}</th><th></th></tr></thead><tbody>
          ${d.sources.map(s => `<tr data-id="${esc(s.id)}" class="${s.on === false ? "off" : ""}"><td><span class="rd-kind">${esc(KIND[s.kind] || "WEB")}</span></td>
            <td class="nm"><b>${esc(s.name)}</b><small>${esc(s.url)}</small></td>
            <td>${srcState(s)}</td>
            <td>${s.week}</td><td>${s.avg == null ? "—" : fmt(s.avg)}</td>
            <td><div class="rd-acts"><label class="tg" title="${esc(T("src.on"))}"><input type="checkbox" data-on ${s.on === false ? "" : "checked"} aria-label="${esc(T("src.on"))}"><i></i></label>
              <button class="rd-ico" data-crawl title="${esc(T("src.crawl"))}" aria-label="${esc(T("src.crawl"))}">${IC.crawl}</button>
              <button class="rd-ico" data-feed title="${esc(T("src.feed"))}" aria-label="${esc(T("src.feed"))}">${IC.feed}</button>
              <button class="rd-ico" data-del title="${esc(T("src.del"))}" aria-label="${esc(T("src.del"))}">${IC.del}</button></div></td></tr>`).join("")}</tbody></table></div>`
          : `<p class="rd-hint">${esc(T("src.none"))}</p>`}</div>`;
    q("#rd-sab").onclick = async () => {
      const v = q("#rd-sa").value.trim(); if (!v) { q("#rd-sa").focus(); return; }
      try { const r = await call("insight_add", { text: v }); q("#rd-sa").value = r.bad.join("\n");
        toast(r.added.length ? T("src.added", { n: r.added.length }) : T("src.noadd"));
        const codes = Object.values(r.why || {}), plain = r.bad.filter(b => !(r.why || {})[b]);
        if (codes.length) toast(why("@" + codes[0]), 7000); else if (plain.length) toast(T("src.bad", { list: plain.slice(0, 3).join(", ") }), 4000);
        renderSources(); setTimeout(load, 8000); } catch (e) { toast(e.message); } };
    q("#rd-oneb").onclick = async () => {
      const u = q("#rd-one").value.trim(); if (!/^https?:\/\//.test(u)) { toast(T("one.bad")); q("#rd-one").focus(); return; }
      const b = q("#rd-oneb"); b.disabled = true; b.textContent = T("one.going");
      try { const r = await call("insight_one", { url: u }); q("#rd-oner").innerHTML = r.item ? `<div class="rd-items" style="margin-top:12px">${itemHtml(r.item)}</div>` : "";
        qa("[data-url]", q("#rd-oner")).forEach(a => a.onclick = (e) => { e.preventDefault(); openUrl(a.dataset.url); }); } catch (e) { toast(e.message, 4000); }
      b.disabled = false; b.textContent = T("one.btn"); };
    qa("tr[data-id]", el).forEach(tr => {
      const id = tr.dataset.id;
      q("[data-on]", tr).onchange = (e) => call("insight_src", { id, on: e.target.checked }).then(renderSources).catch(x => toast(x.message));
      q("[data-crawl]", tr).onclick = async () => { toast(T("src.crawling")); try { const r = await call("insight_src", { id, crawl: true });
        toast(r.err ? why(r.err) : r.found ? T("src.found", { n: r.found, m: r.new }) : T("src.found0"), r.err || !r.found ? 6000 : 3000); } catch (e) { toast(e.message, 4000); } renderSources(); };
      q("[data-feed]", tr).onclick = () => { RD.feed.q = q(".nm b", tr).textContent; tab("feed"); };
      q("[data-del]", tr).onclick = async () => { if (!(await ask(T("src.del.ask", { name: q(".nm b", tr).textContent }), { ok: T("src.del.ok") }))) return; await call("insight_src", { id, del: true }).catch(x => toast(x.message)); renderSources(); };
    });
  }

  /* ---------- «Разум» ---------- */
  async function renderMind() {
    const el = q("#rd-mind");
    let d; try { d = await call("insight_mind"); } catch (e) { toast(e.message); return; }
    const acc = d.accuracy || {}, rate = acc.rate == null ? null : Math.round(acc.rate * 100), C = 2 * Math.PI * 30;
    const open = (d.hyps || []).filter(h => h.state === "open");
    const P = pal(), nodes = [["mission", 50, 52, 26, P.c1hex], ["theses", 76, 26, 9, clColor(1)], ["hyps", 32, 20, 8, clColor(4)], ["lenses", 20, 70, 7, clColor(5)], ["watch", 66, 82, 8, clColor(3)]];
    el.innerHTML = `<div class="rd-mind"><div class="rd-card rd-constel"><svg viewBox="0 0 100 100" preserveAspectRatio="xMidYMid meet" role="img" aria-label="${esc(T("mind.map"))}">
        <defs><radialGradient id="rd-core"><stop offset="0" stop-color="${P.c1hex}" stop-opacity=".35"/><stop offset="1" stop-color="${P.c1hex}" stop-opacity="0"/></radialGradient></defs>
        ${[10, 18, 26].map(r => `<circle cx="50" cy="52" r="${r}" fill="none" stroke="${P.grid}" stroke-width=".3"/>`).join("")}
        ${nodes.slice(1).map(n => `<path d="M50 52 Q ${(50 + n[1]) / 2 + 6} ${(52 + n[2]) / 2 - 6} ${n[1]} ${n[2]}" stroke="${n[4]}" stroke-opacity=".45" stroke-width=".4" fill="none"/>`).join("")}
        <circle cx="50" cy="52" r="15" fill="url(#rd-core)"/>
        ${nodes.map(n => `<circle cx="${n[1]}" cy="${n[2]}" r="${n[3] / (n[0] === "mission" ? 3.2 : 2.6)}" fill="${n[4]}" stroke="${P.light ? "#fff" : "rgba(0,0,0,.3)"}" stroke-width=".6"/>
          <text x="${n[1]}" y="${n[2] + (n[0] === "mission" ? 13 : 7)}" text-anchor="middle" font-size="3.4" font-weight="600" font-family="Manrope, Ubuntu, sans-serif">${esc(T("mind.node." + n[0]))}</text>`).join("")}
      </svg></div>
      <div style="display:grid;gap:16px;align-content:start"><div class="rd-card rd-mission"><small>${esc(T("mind.mission.t"))}</small><b id="rd-mis">${esc(d.mission || T("mind.nomission"))}</b>
          <div style="display:flex;gap:8px;flex-wrap:wrap"><button class="btn rd-btn" id="rd-misb">${esc(T("mind.mission.edit"))}</button><span class="rd-chip">${esc(T("mind.v", { v: d.v }))}</span></div></div>
        <div class="rd-card"><div class="rd-acc"><svg viewBox="0 0 72 72" aria-hidden="true"><circle cx="36" cy="36" r="30" stroke="${P.grid}" stroke-width="6" fill="none"/>
          <circle cx="36" cy="36" r="30" stroke="${P.c1hex}" stroke-width="6" fill="none" stroke-linecap="round" stroke-dasharray="${C}" stroke-dashoffset="${C * (1 - (rate || 0) / 100)}" transform="rotate(-90 36 36)"/></svg>
          <div><b>${rate == null ? "—" : rate + "%"}</b><small>${esc(T("mind.acc", { a: acc.confirmed || 0, b: acc.refuted || 0 }))}</small></div></div>
          <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap"><button class="btn primary rd-btn" id="rd-evo">${esc(T("mind.evolve"))}</button><small style="color:var(--dim)">${esc(T("mind.evolve.t"))}</small></div></div></div></div>
      <div class="rd-mgrid"><div class="rd-card"><h3>${esc(T("mind.theses"))} <small>${esc(T("mind.n", { n: (d.theses || []).length }))}</small></h3>
          ${(d.theses || []).length ? d.theses.map(t => `<div class="rd-thesis">${esc(t.text)}<small>${t.refs.map(r => `<a href="#" data-url="${esc(r.url)}">${esc(r.title.slice(0, 60))}</a>`).join(" · ")}</small></div>`).join("") : `<p class="rd-hint">${esc(T("mind.theses.none"))}</p>`}</div>
        <div class="rd-card"><h3>${esc(T("mind.hyps"))} <small>${esc(T("mind.open", { n: open.length }))}</small></h3>
          ${(d.hyps || []).length ? d.hyps.slice().reverse().slice(0, 12).map(h => `<div class="rd-hyp"><span class="${h.state === "confirmed" ? "ok" : h.state === "refuted" ? "no" : ""}">${h.state === "confirmed" ? "✓" : h.state === "refuted" ? "✕" : "·"}</span><div>${esc(h.text)} <small>${h.due ? esc(T("mind.due", { d: h.due })) : ""}</small></div></div>`).join("") : `<p class="rd-hint">${esc(T("mind.hyps.none"))}</p>`}</div>
        <div class="rd-card"><h3>${esc(T("mind.watch"))}</h3>${(d.watch || []).length ? `<div class="rd-items">${d.watch.slice(0, 6).map(itemHtml).join("")}</div>` : `<p class="rd-hint">${esc(T("mind.watch.none"))}</p>`}</div>
        <div class="rd-card"><h3>${esc(T("mind.diary"))}</h3>${(d.diary || []).length ? `<div class="rd-diary">${d.diary.map(x => `<div>${esc(T("mind.diary.row", { v: x.v, t: ago(x.at), th: x.theses, h: x.new_hyps, c: x.closed }))}</div>`).join("")}</div>` : `<p class="rd-hint">${esc(T("mind.diary.none"))}</p>`}</div></div>`;
    qa("[data-url]", el).forEach(a => a.onclick = (e) => { e.preventDefault(); openUrl(a.dataset.url); });
    q("#rd-misb").onclick = async () => {
      const v = await askText(T("mind.mission.ask"), d.mission || "", { ok: T("save") }); if (v == null) return;
      try { await call("insight_mission", { text: v }); toast(T("saved")); renderMind(); } catch (e) { toast(e.message); } };
    q("#rd-evo").onclick = async () => { q("#rd-evo").disabled = true; try { await call("insight_evolve"); toast(T("mind.evolving")); setTimeout(renderMind, 9000); } catch (e) { toast(e.message); } };
  }

  /* ---------- galaxy ---------- */
  async function renderGalaxy() {
    const el = q("#rd-galaxy");
    let d; try { d = await call("insight_galaxy"); } catch (e) { toast(e.message); return; }
    if (!d.points.length) { el.innerHTML = RD.st && RD.st.sources_all ? `<div class="rd-card rd-empty">${esc(T("gal.none"))}</div>` : empty(T("empty.title"), T("empty.text"), T("empty.btn")); bindGo(el); return; }
    el.innerHTML = `<div class="rd-galaxy"><div class="rd-card rd-gstage"><canvas id="rd-gc" role="img" aria-label="${esc(T("gal.title"))}"></canvas><span class="rd-ghelp">${esc(T("gal.help"))}</span></div>
      <div class="rd-clust"><span class="rd-hint" style="margin:0">${esc(T("gal.count", { n: d.points.length, c: d.clusters.length }))}</span>
        ${d.clusters.map((c, i) => `<div class="rd-cl" data-c="${i}" tabindex="0"><b><i style="background:${clColor(i)}"></i>${esc(c.name)}</b>
          <small>${esc(T("gal.cl", { n: c.n, tags: c.tags.join(", ") }))}</small></div>`).join("")}</div></div>`;
    qa(".rd-cl", el).forEach(c => { c.onclick = () => { RD.galSel = RD.galSel === +c.dataset.c ? -1 : +c.dataset.c; qa(".rd-cl", el).forEach(x => x.classList.toggle("on", +x.dataset.c === RD.galSel)); };
      c.onkeydown = (e) => { if (e.key === "Enter") c.click(); }; });
    galaxy(d);
  }
  function galaxy(d) {
    const cv = q("#rd-gc"), box = cv.getBoundingClientRect(), dpr = window.devicePixelRatio || 1;
    cv.width = box.width * dpr; cv.height = box.height * dpr;
    const g = cv.getContext("2d"), W = box.width, H = box.height, nc = Math.max(1, d.clusters.length), Pl = pal();
    Pl.dust = Pl.light ? "#5b6785" : "#C9D4FF";
    const rnd = (s) => { let h = 2166136261; for (const c of s) h = Math.imul(h ^ c.charCodeAt(0), 16777619);
      h ^= h >>> 16; h = Math.imul(h, 2246822507); h ^= h >>> 13; h = Math.imul(h, 3266489909); h ^= h >>> 16; return (h >>> 0) / 4294967296; };
    // созвездие — центр на сфере; звезда — вокруг центра (гаусс), ярче — сильнее сигнал
    const C = d.clusters.map((c, i) => { const a = (i / nc) * Math.PI * 2, el = (i % 2 ? .45 : -.35); return [Math.cos(a) * Math.cos(el), Math.sin(el), Math.sin(a) * Math.cos(el)]; });
    const S = d.points.map(p => { const c = C[p.c] || [0, 0, 0], u = rnd(p.id + "a"), v = rnd(p.id + "b"), w = rnd(p.id + "c"), r = .2 + .3 * Math.sqrt(-2 * Math.log(u + 1e-6)) * .5;
      const th = v * Math.PI * 2, ph = Math.acos(2 * w - 1);
      return { ...p, x: c[0] * .62 + r * Math.sin(ph) * Math.cos(th), y: c[1] * .62 + r * Math.cos(ph), z: c[2] * .62 + r * Math.sin(ph) * Math.sin(th) }; });
    // звёздная пыль — глубина и масштаб (не материалы: без подсказок и кликов)
    const DUST = Array.from({ length: 520 }, (_, i) => { const u = rnd("d" + i + "u"), v = rnd("d" + i + "v"), w = rnd("d" + i + "w"), r = 1.05 * Math.cbrt(u);
      const th = v * Math.PI * 2, ph = Math.acos(2 * w - 1); return { x: r * Math.sin(ph) * Math.cos(th), y: r * Math.cos(ph) * .7, z: r * Math.sin(ph) * Math.sin(th), b: rnd("d" + i + "b") }; });
    let ry = .6, rx = -.25, drag = null, auto = !REDUCE.matches, zoom = 1, hover = null, last = 0;
    const tip = document.createElement("div"); tip.className = "rd-tip"; tip.hidden = true; cv.parentElement.appendChild(tip);
    function proj(p) {
      const cy = Math.cos(ry), sy = Math.sin(ry), cx = Math.cos(rx), sx = Math.sin(rx);
      let x = p.x * cy - p.z * sy, z = p.x * sy + p.z * cy, y = p.y * cx - z * sx; z = p.y * sx + z * cx;
      const k = 2.6 / (2.6 + z) * Math.min(W, H) * .5 * zoom; return [W / 2 + x * k, H / 2 + y * k, z, k];
    }
    function frame(now) {
      if (!cv.isConnected) return;
      if (auto && !drag) ry += Math.min(50, now - (last || now)) * .00008;
      last = now;
      g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, W, H);
      for (const p of DUST) { const [x, y, z] = proj(p); g.globalAlpha = Math.max(.04, (.18 + p.b * .3) * (1 - z * .5)) * (Pl.light ? .7 : 1); g.fillStyle = p.b > .75 ? Pl.c1hex : Pl.dust;
        g.beginPath(); g.arc(x, y, .9, 0, 7); g.fill(); }
      g.globalAlpha = 1;
      const P = S.map(p => { const [x, y, z, k] = proj(p); return { p, x, y, z, k }; }).sort((a, b) => b.z - a.z);
      const [cx0, cy0] = [W / 2, H / 2];
      g.lineWidth = .5;
      for (const o of P) {          // тонкие лучи к центру — «галактика»
        const dim = RD.galSel >= 0 && o.p.c !== RD.galSel;
        g.strokeStyle = clColor(o.p.c); g.globalAlpha = dim ? .02 : (Pl.light ? .09 : .07); g.beginPath(); g.moveTo(cx0, cy0); g.lineTo(o.x, o.y); g.stroke();
      }
      g.globalAlpha = 1;
      // орбиты — «радар» вокруг ядра: три кольца в плоскости галактики
      g.strokeStyle = Pl.grid; g.lineWidth = 1;
      for (const rr of [.38, .72, 1.05]) { g.beginPath(); for (let a = 0; a <= 64; a++) { const t = a / 64 * Math.PI * 2, [x, y] = proj({ x: Math.cos(t) * rr, y: 0, z: Math.sin(t) * rr });
        if (a) g.lineTo(x, y); else g.moveTo(x, y); } g.stroke(); }
      for (const o of P) {          // туманность созвездия — мягкое пятно его цвета под звёздами
        if (o.p.s < 7) continue; const dim = RD.galSel >= 0 && o.p.c !== RD.galSel, rgb = hexRGB(clColor(o.p.c)), R = 26 * o.k / (Math.min(W, H) * .5);
        const rg = g.createRadialGradient(o.x, o.y, 0, o.x, o.y, R); rg.addColorStop(0, `rgba(${rgb},${dim ? .02 : .1})`); rg.addColorStop(1, `rgba(${rgb},0)`);
        g.fillStyle = rg; g.beginPath(); g.arc(o.x, o.y, R, 0, 7); g.fill();
      }
      for (const o of P) {
        const dim = RD.galSel >= 0 && o.p.c !== RD.galSel, col = clColor(o.p.c), depth = Math.max(.3, Math.min(1, 1 - o.z * .45));
        const r = (2.2 + o.p.s * .5) * depth * (o.p === hover ? 1.7 : 1);
        g.globalAlpha = (dim ? .15 : 1) * depth;
        g.fillStyle = col; g.beginPath(); g.arc(o.x, o.y, r, 0, 7); g.fill();
        g.lineWidth = 1.2; g.strokeStyle = Pl.light ? "#fff" : "rgba(0,0,0,.35)"; g.stroke();
      }
      g.globalAlpha = 1;
      const core = g.createRadialGradient(cx0, cy0, 0, cx0, cy0, 30 * zoom), cr = Pl.c1;
      core.addColorStop(0, `rgba(${cr},.55)`); core.addColorStop(.35, `rgba(${cr},.16)`); core.addColorStop(1, `rgba(${cr},0)`);
      g.fillStyle = core; g.beginPath(); g.arc(cx0, cy0, 30 * zoom, 0, 7); g.fill();
      // имена созвездий — у их центров, плашкой
      g.font = "600 12px Manrope, Ubuntu, sans-serif"; g.textAlign = "center";
      d.clusters.forEach((c, i) => { if (RD.galSel >= 0 && RD.galSel !== i) return; const [x, y] = proj({ x: C[i][0] * .62, y: C[i][1] * .62 - .16, z: C[i][2] * .62 }), w = g.measureText(c.name).width;
        g.fillStyle = Pl.label; g.beginPath(); g.roundRect ? g.roundRect(x - w / 2 - 9, y - 13, w + 18, 21, 10) : g.rect(x - w / 2 - 9, y - 13, w + 18, 21); g.fill();
        g.fillStyle = clColor(i); g.beginPath(); g.arc(x - w / 2 - 1, y - 2.5, 3, 0, 7); g.fill();
        g.fillStyle = Pl.ink; g.fillText(c.name, x + 4, y + 2); });
      g.textAlign = "left";
      RD.galP = P;
      requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
    cv.onpointerdown = (e) => { drag = [e.clientX, e.clientY, ry, rx]; cv.setPointerCapture(e.pointerId); auto = false; };
    cv.onpointermove = (e) => {
      if (drag) { ry = drag[2] + (e.clientX - drag[0]) * .008; rx = Math.max(-1.2, Math.min(1.2, drag[3] + (e.clientY - drag[1]) * .008)); return; }
      const r = cv.getBoundingClientRect(), x = e.clientX - r.left, y = e.clientY - r.top; let best = null, bd = 12 * 12;
      for (const o of RD.galP || []) { const dd = (o.x - x) ** 2 + (o.y - y) ** 2; if (dd < bd) { bd = dd; best = o; } }
      hover = best ? best.p : null; tip.hidden = !best;
      if (best) { tip.innerHTML = `${esc(best.p.title)}<small>${esc((d.clusters[best.p.c] || {}).name || "")} · ${esc(best.p.src)}</small>`;
        tip.style.left = Math.min(x + 16, W - 340) + "px"; tip.style.top = (y + 16) + "px"; }
    };
    cv.onpointerup = () => { drag = null; };
    cv.onpointerleave = () => { tip.hidden = true; hover = null; };
    cv.onwheel = (e) => { e.preventDefault(); zoom = Math.max(.6, Math.min(2.6, zoom * (e.deltaY < 0 ? 1.1 : .9))); };
    cv.onclick = () => { if (hover) { RD.focus = hover.id; tab("feed"); } };
  }

  /* ---------- «Управление» ---------- */
  async function renderControl() {
    const el = q("#rd-control");
    let d; try { d = await call("insight_control"); } catch (e) { toast(e.message); return; }
    chips(d.stats);
    const c = d.conf, hrs = [...Array(24).keys()].map(h => `${String(h).padStart(2, "0")}:00`);
    const sel = (id, v) => `<select id="${id}">${hrs.map((h, i) => `<option value="${i}" ${+v === i ? "selected" : ""}>${h}</option>`).join("")}</select>`;
    el.innerHTML = `<div class="rd-card"><h3>${esc(d.stats.running ? T("ctl.running", { what: T("run." + d.stats.running.k, { x: d.stats.running.x }) }) : T("ctl.waiting"))}</h3>
        <p class="rd-hint">${esc(T("ctl.why"))}</p>
        <div class="rd-modes">${["always", "night", "pause"].map(m => `<button class="rd-mode ${c.mode === m ? "on" : ""}" data-m="${m}"><b>${esc(T("mode." + m))}</b><small>${esc(T("mode." + m + ".t"))}</small></button>`).join("")}</div></div>
      <div class="rd-two" style="margin-top:16px"><div class="rd-card"><h3>${esc(T("ctl.sched"))}</h3><div class="rd-form">
          <span>${esc(T("ctl.night"))}</span><span style="display:flex;gap:6px">${sel("rd-n0", c.night[0])}${sel("rd-n1", c.night[1])}</span>
          <span>${esc(T("ctl.daily"))}</span><input type="number" id="rd-dm" min="5" max="1000" value="${c.daily_max}">
          <span>${esc(T("ctl.tickday"))}</span><input type="number" id="rd-td" min="5" max="240" value="${c.tick_day}">
          <span>${esc(T("ctl.pertick"))}</span><input type="number" id="rd-pd" min="1" max="50" value="${c.per_tick_day}">
          <span>${esc(T("ctl.urgent"))}</span><input type="number" id="rd-um" min="5" max="10" step=".5" value="${c.urgent_min}">
          <span>${esc(T("ctl.brief"))}</span>${sel("rd-bh", c.brief_hour)}
          <label class="rd-tog" style="grid-column:1/-1"><span class="rd-sw"><input type="checkbox" id="rd-dl" ${c.day_long ? "checked" : ""}><i></i></span>${esc(T("ctl.daylong"))}</label>
          <span class="sub">${esc(T("ctl.cost"))}</span></div>
          <div class="rd-row-end"><button class="btn primary rd-btn" id="rd-cs">${esc(T("save"))}</button></div></div>
        <div class="rd-card"><h3>${esc(T("ctl.ticks"))}</h3>${(d.log || []).length ? `<div style="overflow-x:auto"><table class="rd-ticks"><thead><tr><th>${esc(T("ctl.t.at"))}</th><th>${esc(T("ctl.t.prof"))}</th><th>${esc(T("ctl.t.dur"))}</th><th>${esc(T("ctl.t.new"))}</th><th>${esc(T("ctl.t.done"))}</th></tr></thead><tbody>
          ${d.log.map(r => `<tr title="${esc(r.err || "")}"><td>${esc(ago(r.at))}</td><td>${esc(T("prof." + (r.profile || "day")))}</td><td>${fmt(r.dur, 0)} ${esc(T("sec"))}</td><td>${r.new}</td><td>${r.done}${r.err ? " ⚠" : ""}</td></tr>`).join("")}</tbody></table></div>` : `<p class="rd-hint">${esc(T("ctl.noticks"))}</p>`}</div></div>`;
    qa("[data-m]", el).forEach(b => b.onclick = () => call("insight_conf", { conf: { mode: b.dataset.m } }).then(renderControl).catch(e => toast(e.message)));
    q("#rd-cs").onclick = async () => {
      const n = (id) => +q(id).value;
      try { await call("insight_conf", { conf: { night: [n("#rd-n0"), n("#rd-n1")], daily_max: n("#rd-dm"), tick_day: n("#rd-td"), per_tick_day: n("#rd-pd"), urgent_min: n("#rd-um"),
        brief_hour: n("#rd-bh"), day_long: q("#rd-dl").checked } }); toast(T("saved")); renderControl(); } catch (e) { toast(e.message); } };
  }

  /* ---------- «читалка» материала (владелец 12.11: «статья интересная, а не сразу удаётся её найти — сразу бы прочитать»)
     Боковая панель: источник и время, сигнал, суть от Лиры и почему важно, текст статьи целиком (ядро читает страницу
     сейчас: insight_read), «Открыть оригинал», «Спросить Лиру», ☆. Открывается с материала в «Ленте», «Пульсе», точки
     поля сигналов, ссылки в ответе Лиры, карточки «Главной» и весточки виджета (studioGo("insight:<id>")). */
  let RR = null;
  function rrBox() {
    let d = q("#rd-reader");
    if (!d) {
      d = document.createElement("aside"); d.className = "drawer rd-reader"; d.id = "rd-reader";
      d.setAttribute("role", "dialog"); d.setAttribute("aria-modal", "true"); d.setAttribute("aria-labelledby", "rr-h");
      document.body.appendChild(d);
      document.addEventListener("keydown", (e) => { if (e.key === "Escape" && d.classList.contains("open")) rrClose(); });
    }
    return d;
  }
  function rrClose() { const d = q("#rd-reader"); if (d) d.classList.remove("open"); RR = null; }
  function rrParas(text) {
    return String(text || "").split(/\n+/).map(x => x.trim()).filter(Boolean).map(x => `<p>${esc(x)}</p>`).join("");
  }
  function rrHtml(x, wait) {
    const meta = [x.src, x.ts ? ago(x.ts) : "", x.type ? typeText(x.type) : ""].filter(Boolean).map(v => `<span>${esc(v)}</span>`).join("");
    const sig = x.signal == null ? "" : `<span class="rr-sig" style="--c:${sigColor(x.signal)}"><b>${fmt(x.signal)}</b>${esc(T("signal"))}</span>`;
    const text = wait ? `<p class="rr-wait"><i></i>${esc(T("read.loading"))}</p>`
      : x.text ? `${x.full ? "" : `<p class="rr-part">${esc(T("read.part"))}</p>`}<div class="rr-text">${rrParas(x.text)}</div>`
      : `<p class="rr-part">${esc(T("read.notext"))}</p>`;
    return `<button class="btn icon hx" id="rr-x" title="${esc(T("read.close"))}" aria-label="${esc(T("read.close"))}">✕</button>
      <div class="rr-meta">${meta}${sig}</div><h2 id="rr-h">${esc(x.title)}</h2>
      ${x.summary ? `<div class="rr-lira"><h4>${esc(T("read.lira"))}</h4><p>${esc(x.summary)}</p>${x.why ? `<h4>${esc(T("read.why"))}</h4><p>${esc(x.why)}</p>` : ""}
        ${(x.tags || []).length ? `<div class="rr-tags">${x.tags.map(t => `<span class="rd-tag" data-tag="${esc(t)}">#${esc(t)}</span>`).join("")}</div>` : ""}</div>` : ""}
      <div class="rr-acts">${x.url ? `<button class="btn primary rd-btn" id="rr-open">${esc(T("read.open"))}</button>` : ""}
        <button class="btn rd-btn" id="rr-ask">${esc(T("read.ask"))}</button>
        <button class="btn rd-btn rr-w ${x.watch ? "on" : ""}" id="rr-watch" aria-pressed="${x.watch ? "true" : "false"}">${x.watch ? "★" : "☆"} ${esc(T("watch"))}</button></div>
      <h4 class="rr-th">${esc(T("read.text"))}</h4>${text}`;
  }
  function rrBind(d, x) {
    q("#rr-x", d).onclick = rrClose;
    const o = q("#rr-open", d); if (o) o.onclick = () => openUrl(x.url);
    q("#rr-ask", d).onclick = () => { rrClose(); const v = T("read.q", { title: x.title }); if (RD.tab !== "pulse") { tab("pulse"); setTimeout(() => askNow(v), 450); } else askNow(v);
      setTimeout(() => { const a = q("#rd-ans"); if (a) a.scrollIntoView({ block: "center", behavior: REDUCE.matches ? "auto" : "smooth" }); }, 500); };
    const w = q("#rr-watch", d); w.onclick = async () => { const on = !w.classList.contains("on"); await call("insight_mark", { id: x.id, watch: on }).catch(() => {});
      x.watch = on; w.classList.toggle("on", on); w.setAttribute("aria-pressed", String(on)); w.textContent = (on ? "★ " : "☆ ") + T("watch"); };
    qa("[data-tag]", d).forEach(a => a.onclick = () => { rrClose(); RD.feed.q = a.dataset.tag; tab("feed"); });
  }
  async function rdRead(id, hint) {
    if (!id) return;
    const d = rrBox(), me = RR = { id };
    d.innerHTML = rrHtml(hint || { id, title: "" }, true); rrBind(d, hint || { id }); d.classList.add("open"); d.scrollTop = 0;
    let x; try { x = (await call("insight_read", { id })).item; } catch (e) { if (RR === me) { rrClose(); toast(e.message); } return; }
    if (RR !== me || !x) return;
    d.innerHTML = rrHtml(x, false); rrBind(d, x); setTimeout(() => { const b = q("#rr-open", d) || q("#rr-x", d); if (b) b.focus({ preventScroll: true }); }, 50);
  }
  window.rdRead = rdRead;
  // материал по ссылке data-rid — где бы он ни был в разделе (лента, бриф, «Наблюдаемое» в «Разуме»)
  q("#p-insight").addEventListener("click", (e) => { const a = e.target.closest("[data-rid]"); if (!a) return; e.preventDefault(); rdRead(a.dataset.rid); });
  // открыли студию прямо на материале (весточка виджета при закрытой студии): #insight:<id>
  setTimeout(() => { const m = /^#insight:([\w-]+)$/.exec(location.hash || ""); if (!m) return;
    const b = q('nav button[data-p="insight"]'); if (b) b.click(); setTimeout(() => rdRead(m[1]), 300); }, 400);

  /* ---------- вкладки, загрузка, вопрос ---------- */
  function tab(t) {
    RD.tab = t;
    qa("#rd-tabs button").forEach(b => { b.classList.toggle("on", b.dataset.t === t); b.setAttribute("aria-selected", String(b.dataset.t === t)); });
    qa(".rd-pane").forEach(p => { p.hidden = p.id !== "rd-" + t; });
    try { localStorage.setItem("rd_tab", t); } catch (e) { }
    load();
  }
  async function load() {
    if (!core.connected) return;
    const t = RD.tab;
    try {
      if (t === "pulse") renderPulse(await call("insight_pulse"));
      else if (t === "feed") await renderFeed();
      else if (t === "trends") await renderTrends();
      else if (t === "sources") await renderSources();
      else if (t === "mind") await renderMind();
      else if (t === "galaxy") await renderGalaxy();
      else if (t === "control") await renderControl();
    } catch (e) { toast(e.message); }
  }
  window.loadInsight = () => { try { const s = localStorage.getItem("rd_tab"); if (s && !RD.started) RD.tab = s; } catch (e) { } RD.started = true; tab(RD.tab); };
  qa("#rd-tabs button").forEach(b => b.onclick = () => tab(b.dataset.t));
  document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k" && q("#p-insight").classList.contains("cur")) {
      e.preventDefault(); const go = () => { const i = q("#rd-ask-q"); if (i) i.focus(); }; if (RD.tab !== "pulse") { tab("pulse"); setTimeout(go, 400); } else go(); }
  });
  core.on("insight", () => { if (q("#p-insight").classList.contains("cur") && (RD.tab === "pulse" || RD.tab === "feed")) load(); });
  // тема сменилась (светлая / тёмная / неоморфизм) — цвета холста заново; другие классы <html> не трогают раздел
  const skinSig = () => { const r = document.documentElement; return [r.dataset.skin, r.classList.contains("st-light"), r.classList.contains("st-neu")].join(); };
  let skinNow = skinSig();
  new MutationObserver(() => { const s = skinSig(); if (s === skinNow) return; skinNow = s; PAL = null;
    if (q("#p-insight").classList.contains("cur") && ["pulse", "trends", "mind", "galaxy", "feed"].includes(RD.tab)) load(); })
    .observe(document.documentElement, { attributes: true, attributeFilter: ["class", "data-skin"] });
  window.addEventListener("dw-lang", () => { if (q("#p-insight").classList.contains("cur")) { qa(".rd-pane").forEach(p => { p.innerHTML = ""; }); load(); } });
  let rt = 0; window.addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(() => { if (q("#p-insight").classList.contains("cur") && (RD.tab === "pulse" || RD.tab === "galaxy")) load(); }, 300); });
})();
