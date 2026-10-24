/* Живые облики персонажей: каждая «сущность» рисует свой стиль на canvas, реагируя на состояние
   (idle/listening/thinking/speaking/muted/offline) и громкость 0…1 (микрофон или собственный голос).
   new DewiarEntity(canvas, {style, color, image, ring, plate}) → .set({state, level}), .configure(...), .destroy();
   снаружи можно выставить .paused (не рисовать), .vinyl = название станции (в покое — пластинка),
   .calm (реже кадры: созвон, мало памяти), .lite (лёгкий режим телефона: ~20 кадров/с), .still (в покое — неподвижный кадр, для страниц со многими обликами),
   .bold/.thick (плотнее линии — для иконки приложения).
   Стили — STYLES ниже; имена совпадают со style персонажей в core/personas.py и STYLE_NAMES в ui/studio/core.js.
   Используют виджет (ui/hud.html), студия и телефон: android/tools/build_apk.sh копирует этот файл в приложение.
   Только Canvas 2D; на слабом компьютере draw() сама рисует реже, чтобы окно не тормозило. */

(function () {
  const TAU = Math.PI * 2;
  const reduced = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;

  function rgb(hex) {
    const h = hex.replace("#", "");
    const n = parseInt(h.length === 3 ? h.split("").map(c => c + c).join("") : h, 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  }
  function rgba(c, a) { return `rgba(${c[0]},${c[1]},${c[2]},${Math.max(0, Math.min(1, a))})`; }
  function mix(c, w, k) { return c.map((v, i) => Math.round(v + (w[i] - v) * k)); }

  const STATE = {           // скорость анимации, яркость (k), цвет (sat: 0 — серый)
    idle:      { speed: 0.35, glow: 0.6, sat: 1 },
    listening: { speed: 0.8,  glow: 1.0, sat: 1 },
    thinking:  { speed: 2.6,  glow: 0.95, sat: 1 },
    speaking:  { speed: 1.0,  glow: 1.0, sat: 1 },
    muted:     { speed: 0.35, glow: 0.6, sat: 1 },     // микрофон выключен — как в покое: это видно по значку и подписи (отзыв 14.10)
    offline:   { speed: 0.08, glow: 0.3, sat: 0 },
  };

  // ---------- стили ----------
  // Каждый стиль — функция (g, e): g = {ctx, r — радиус облика, c — цвет [r,g,b], t — время анимации,
  // lv — громкость, k — яркость состояния}, e — сама сущность (состояние и кэш стиля в e._…).
  // Начало координат — центр canvas.

  // Знак Dewiar из живой нейросети: кольцо с прорезью, собранное из нейронов;
  // по связям бегут импульсы, срабатывание иногда цепочкой зажигает соседей,
  // вокруг плавают свободные нейроны и подключаются, оказавшись рядом.
  // rng — повторяемый генератор по зерну: сеть у знака всегда одна и та же.
  function rng(seed) { return () => { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
  const BM = { OUT: 0.62, IN: 0.31, SLOT: 0.078 };   // пропорции фавикона Dewiar: внутренний квадрат вдвое меньше внешнего
  function inMark(x, y, pad = 0) {
    const ax = Math.abs(x), ay = Math.abs(y);
    if (ax > BM.OUT - pad || ay > BM.OUT - pad) return false;
    if (ax < BM.IN + pad && ay < BM.IN + pad) return false;
    if (ax < BM.SLOT + pad && y < 0) return false;          // прорезь сверху
    return true;
  }
  function buildMark() {
    const R = rng(1790), nodes = [], edges = [], seen = new Set();
    const link = (a, b) => { const key = a < b ? a + "-" + b : b + "-" + a; if (a !== b && !seen.has(key)) { seen.add(key); edges.push([a, b]); } };
    // 1) контур знака — одна замкнутая линия (кольцо с прорезью), нейроны через равный шаг
    const O = BM.OUT, I = BM.IN, W = BM.SLOT;
    const poly = [[W, -O], [O, -O], [O, O], [-O, O], [-O, -O], [-W, -O], [-W, -I], [-I, -I], [-I, I], [I, I], [I, -I], [W, -I]];
    const corners = new Set();
    poly.forEach(([x0, y0], i) => {
      const [x1, y1] = poly[(i + 1) % poly.length], len = Math.hypot(x1 - x0, y1 - y0), n = Math.max(1, Math.round(len / 0.085));
      for (let j = 0; j < n; j++) {
        if (j === 0) corners.add(nodes.length);
        nodes.push({ x: x0 + (x1 - x0) * j / n, y: y0 + (y1 - y0) * j / n, ph: R() * 6.28, flash: 0, core: j === 0 });
      }
    });
    const nc = nodes.length;
    for (let i = 0; i < nc; i++) link(i, (i + 1) % nc);
    // 2) внутренняя сеть в теле кольца
    for (let k = 0; k < 4000 && nodes.length < nc + 62; k++) {
      const x = (R() * 2 - 1) * O, y = (R() * 2 - 1) * O;
      if (inMark(x, y, 0.04) && nodes.every(n => Math.hypot(n.x - x, n.y - y) > 0.062))
        nodes.push({ x, y, ph: R() * 6.28, flash: 0, core: false });
    }
    for (let a = nc; a < nodes.length; a++) {
      nodes.map((b, ib) => [ib, Math.hypot(nodes[a].x - b.x, nodes[a].y - b.y)]).filter(([ib, d]) => ib !== a && d < 0.2)
        .sort((p, q) => p[1] - q[1]).slice(0, 4).forEach(([ib]) => {
          const mx = (nodes[a].x + nodes[ib].x) / 2, my = (nodes[a].y + nodes[ib].y) / 2;
          if (inMark(mx, my, -0.005)) link(a, ib);
        });
    }
    const adj = nodes.map(() => []);
    edges.forEach(([a, b], n) => { adj[a].push(n); adj[b].push(n); });
    const floaters = Array.from({ length: 16 }, () => ({ a: R() * 6.28, r: 0.8 + R() * 0.16, w: (R() - 0.5) * 0.22, ph: R() * 6.28 }));
    return { nodes, edges, adj, floaters, pulses: [], lt: null, acc: 0, nc };
  }
  function brandmark(g, e) {
    const { ctx, r, c, t, lv, k } = g;
    const m = e._bm || (e._bm = buildMark());
    const dt = m.lt === null ? 0 : Math.max(0, Math.min(0.1, t - m.lt)); m.lt = t;
    const S = r * 1.05, P = (n) => [n.x * S, n.y * S], th = e.thick || 1;
    const white = mix(c, [255, 255, 255], 0.55);
    const halo = ctx.createRadialGradient(0, 0, 0, 0, 0, S * 0.9);
    halo.addColorStop(0, rgba(c, (0.1 + lv * 0.15) * k)); halo.addColorStop(1, rgba(c, 0));
    ctx.fillStyle = halo; ctx.beginPath(); ctx.arc(0, 0, S * 0.9, 0, TAU); ctx.fill();
    // связи
    ctx.lineWidth = 1;
    m.edges.forEach(([a, b]) => {
      const A = P(m.nodes[a]), B = P(m.nodes[b]), contour = a < m.nc && b < m.nc;
      ctx.lineWidth = (contour ? 1.4 : 0.8) * th;
      ctx.strokeStyle = rgba(contour ? white : c, (contour ? 0.42 : 0.14 + 0.08 * Math.sin(t * 0.7 + a)) * k);
      ctx.beginPath(); ctx.moveTo(A[0], A[1]); ctx.lineTo(B[0], B[1]); ctx.stroke();
    });
    // свободные нейроны
    m.floaters.forEach(f => {
      f.a += f.w * dt;
      const x = Math.cos(f.a) * f.r * S, y = Math.sin(f.a) * f.r * S;
      let best = null, bd = 1e9;
      m.nodes.forEach(n => { const q = P(n), d = Math.hypot(q[0] - x, q[1] - y); if (d < bd) { bd = d; best = q; } });
      if (bd < S * 0.3) {
        ctx.strokeStyle = rgba(c, (1 - bd / (S * 0.3)) * 0.35 * k);
        ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(best[0], best[1]); ctx.stroke();
      }
      ctx.fillStyle = rgba(white, (0.25 + 0.2 * Math.sin(t * 1.1 + f.ph)) * k);
      ctx.beginPath(); ctx.arc(x, y, 1.3 * th, 0, TAU); ctx.fill();
    });
    // импульсы: в покое редко, в речи и раздумьях — чаще
    const rate = 0.7 + lv * 9 + (e.state === "thinking" ? 7 : 0) + (e.state === "listening" ? 1.5 : 0);
    m.acc += dt * rate * (reduced ? 0.3 : 1);
    while (m.acc > 1 && m.pulses.length < 46) {
      m.acc -= 1;
      const n0 = Math.floor(Math.random() * m.nodes.length), ed = m.adj[n0];
      if (ed.length) m.pulses.push({ e: ed[Math.floor(Math.random() * ed.length)], from: n0, p: 0, v: 0.9 + Math.random() * 0.9, gen: 0 });
    }
    m.acc = Math.min(m.acc, 2);
    const next = [];
    m.pulses.forEach(pu => {
      pu.p += dt * pu.v * (e.state === "thinking" ? 2.2 : 1);
      const [a, b] = m.edges[pu.e], to = pu.from === a ? b : a;
      const A = P(m.nodes[pu.from]), B = P(m.nodes[to]);
      if (pu.p >= 1) {
        m.nodes[to].flash = 1;
        if (pu.gen < 5 && Math.random() < 0.55) {            // цепная реакция
          const opts = m.adj[to].filter(x => x !== pu.e);
          if (opts.length) next.push({ e: opts[Math.floor(Math.random() * opts.length)], from: to, p: 0, v: pu.v, gen: pu.gen + 1 });
        }
        return;
      }
      const x = A[0] + (B[0] - A[0]) * pu.p, y = A[1] + (B[1] - A[1]) * pu.p;
      const tx = A[0] + (B[0] - A[0]) * Math.max(0, pu.p - 0.35), ty = A[1] + (B[1] - A[1]) * Math.max(0, pu.p - 0.35);
      const gr = ctx.createLinearGradient(tx, ty, x, y);
      gr.addColorStop(0, rgba(white, 0)); gr.addColorStop(1, rgba(white, 0.9 * k));
      ctx.strokeStyle = gr; ctx.lineWidth = 1.8 * th; ctx.beginPath(); ctx.moveTo(tx, ty); ctx.lineTo(x, y); ctx.stroke();
      ctx.fillStyle = rgba([255, 255, 255], 0.95 * k); ctx.beginPath(); ctx.arc(x, y, 1.8 * th, 0, TAU); ctx.fill();
      next.push(pu);
    });
    m.pulses = next.slice(-60);
    // нейроны
    m.nodes.forEach(n => {
      n.flash = Math.max(0, n.flash - dt * 2.2);
      const [x, y] = P(n), tw = 0.55 + 0.45 * Math.sin(t * 1.3 + n.ph);
      const sz = ((n.core ? 2.4 : 1.5) + n.flash * 2.2 + lv * 0.8) * th;
      ctx.fillStyle = rgba(mix(white, [255, 255, 255], n.flash), (0.45 + 0.4 * tw + n.flash) * k);
      if (n.flash > 0.05 || n.core) { ctx.shadowColor = rgba(c, 1); ctx.shadowBlur = 6 + n.flash * 14; }
      ctx.beginPath(); ctx.arc(x, y, sz, 0, TAU); ctx.fill(); ctx.shadowBlur = 0;
    });
  }

  // Мозг со связями по мотивам фирменной картинки Dewiar: контур мозга, поверх него сеть нейронов;
  // по связям бегут импульсы, узлы вспыхивают, вокруг дрейфуют свободные нейроны и подключаются,
  // оказавшись рядом. Голос усиливает импульсы и свечение. В выборе студии (STYLE_NAMES) его нет, как и brandmark.
  const BRAIN = (() => {
    const R = rng(4234);
    const out = [];                                   // внешний контур: 12 долей, впадины сверху и снизу по центру
    for (let i = 0; i <= 240; i++) {
      const th = -Math.PI / 2 + i / 240 * TAU;
      const bump = Math.pow(Math.abs(Math.sin(6 * (th + Math.PI / 2))), 0.55);
      const ex = 0.62, ey = 0.50;
      const base = 1 / Math.sqrt(Math.pow(Math.cos(th) / ex, 2) + Math.pow(Math.sin(th) / ey, 2));
      const rr = base * (0.9 + 0.1 * bump) - (Math.abs(Math.cos(th)) < 0.13 ? 0.05 * (1 - Math.abs(Math.cos(th)) / 0.13) : 0);
      out.push([Math.cos(th) * rr, Math.sin(th) * rr * 0.98 + 0.02]);
    }
    const C = (pts, n = 40) => {                        // кубическая кривая Безье → точки
      const [a, b, c, d] = pts, o = [];
      for (let i = 0; i <= n; i++) {
        const t = i / n, u = 1 - t;
        o.push([u * u * u * a[0] + 3 * u * u * t * b[0] + 3 * u * t * t * c[0] + t * t * t * d[0],
                u * u * u * a[1] + 3 * u * u * t * b[1] + 3 * u * t * t * c[1] + t * t * t * d[1]]);
      }
      return o;
    };
    const mirror = (p) => p.map(([x, y]) => [-x, y]);
    const left = [
      C([[-0.02, -0.40], [-0.03, -0.22], [0.02, -0.10], [-0.03, 0.06]]),                 // продольная щель
      C([[-0.40, -0.26], [-0.30, -0.36], [-0.14, -0.30], [-0.16, -0.16]]),
      C([[-0.16, -0.16], [-0.18, -0.04], [-0.34, -0.02], [-0.36, -0.14]]),                 // завиток
      C([[-0.52, 0.02], [-0.42, 0.10], [-0.30, 0.06], [-0.22, 0.14]]),
      C([[-0.40, 0.28], [-0.30, 0.20], [-0.16, 0.26], [-0.10, 0.36]]),                     // височная доля
    ];
    const right = [
      C([[0.40, -0.24], [0.30, -0.36], [0.12, -0.28], [0.15, -0.14]]),
      C([[0.15, -0.14], [0.17, -0.02], [0.33, -0.04], [0.36, -0.16]]),
      C([[0.53, 0.00], [0.42, 0.12], [0.28, 0.04], [0.20, 0.16]]),
      C([[0.40, 0.29], [0.28, 0.20], [0.15, 0.27], [0.08, 0.37]]),
    ];
    const inner = left.concat(right);
    // узлы сети: на контуре, на извилинах и немного снаружи — как созвездие
    const nodes = [];
    const add = (x, y, core) => { if (nodes.every(n => Math.hypot(n.x - x, n.y - y) > 0.085)) nodes.push({ x, y, core, ph: R() * 6.28, flash: 0 }); };
    for (let i = 0; i < out.length; i += 14) add(out[i][0], out[i][1], true);
    inner.forEach(cv => { for (let j = 0; j <= 40; j += 10) add(cv[j][0], cv[j][1], j % 20 === 0); });
    for (let k = 0; k < 600 && nodes.length < 58; k++) {
      const a = R() * TAU, d = 0.12 + R() * 0.66;
      add(Math.cos(a) * d * 1.1, Math.sin(a) * d * 0.95, false);
    }
    const edges = [], seen = new Set();
    nodes.forEach((a, ia) => {
      nodes.map((b, ib) => [ib, Math.hypot(a.x - b.x, a.y - b.y)]).filter(([ib]) => ib !== ia)
        .sort((p, q) => p[1] - q[1]).slice(0, a.core ? 3 : 2).forEach(([ib, d]) => {
          const key = ia < ib ? ia + "-" + ib : ib + "-" + ia;
          if (d < 0.42 && !seen.has(key)) { seen.add(key); edges.push([ia, ib]); }
        });
    });
    const adj = nodes.map(() => []);
    edges.forEach(([a, b], n) => { adj[a].push(n); adj[b].push(n); });
    return { out, inner, nodes, edges, adj };
  })();

  function brain(g, e) {
    const { ctx, r, c, t, lv, k } = g;
    const B = BRAIN, S = r * 1.24;
    const m = e._br || (e._br = { pulses: [], acc: 0, lt: null, flash: B.nodes.map(() => 0),
      floaters: Array.from({ length: 9 }, (_, i) => ({ a: i * 0.7, r: 0.78 + (i % 3) * 0.06, w: (i % 2 ? 1 : -1) * (0.08 + i * 0.01) })) });
    const dt = m.lt === null ? 0 : Math.max(0, Math.min(0.1, t - m.lt)); m.lt = t;
    const breath = 1 + Math.sin(t * 1.1) * 0.012 + lv * 0.03;
    const P = (x, y) => [x * S * breath, y * S * breath];
    const white = mix(c, [255, 255, 255], 0.6);
    // свечение за мозгом
    const halo = ctx.createRadialGradient(0, 0, S * 0.1, 0, 0, S * 0.85);
    halo.addColorStop(0, rgba(c, (0.16 + lv * 0.22) * k)); halo.addColorStop(1, rgba(c, 0));
    ctx.fillStyle = halo; ctx.beginPath(); ctx.arc(0, 0, S * 0.85, 0, TAU); ctx.fill();
    // контур и извилины — толстой мягкой линией, как на логотипе
    const stroke = (pts, w, a) => {
      ctx.beginPath(); pts.forEach(([x, y], i) => { const q = P(x, y); ctx[i ? "lineTo" : "moveTo"](q[0], q[1]); });
      ctx.lineWidth = w; ctx.strokeStyle = rgba(white, a); ctx.stroke();
    };
    ctx.lineCap = "round"; ctx.lineJoin = "round";
    const bw = S * 0.062;
    ctx.save(); ctx.shadowColor = rgba(c, 0.9); ctx.shadowBlur = 8 + lv * 18;
    stroke(B.out, bw, (0.62 + lv * 0.25) * k);
    B.inner.forEach(cv => stroke(cv, bw * 0.8, (0.5 + lv * 0.25) * k));
    ctx.restore();
    if (e.state === "thinking") {                              // бегущий свет по контуру
      const n = B.out.length, i0 = Math.floor((t * 60) % n);
      const seg = []; for (let i = 0; i < 26; i++) seg.push(B.out[(i0 + i) % n]);
      stroke(seg, bw * 1.05, 0.85 * k);
    }
    // сеть поверх
    const white2 = mix(c, [255, 255, 255], 0.8);
    ctx.lineWidth = Math.max(0.7, S * 0.006);
    B.edges.forEach(([a, b]) => {
      const A = P(B.nodes[a].x, B.nodes[a].y), Bb = P(B.nodes[b].x, B.nodes[b].y);
      ctx.strokeStyle = rgba(white2, (0.3 + 0.1 * Math.sin(t * 0.9 + a)) * k);
      ctx.beginPath(); ctx.moveTo(A[0], A[1]); ctx.lineTo(Bb[0], Bb[1]); ctx.stroke();
    });
    m.floaters.forEach(f => {
      f.a += f.w * dt;
      const x = Math.cos(f.a) * f.r, y = Math.sin(f.a) * f.r * 0.9, q = P(x, y);
      let bi = -1, bd = 1e9; B.nodes.forEach((n, i) => { const d = Math.hypot(n.x - x, n.y - y); if (d < bd) { bd = d; bi = i; } });
      if (bd < 0.3) { const nb = P(B.nodes[bi].x, B.nodes[bi].y); ctx.strokeStyle = rgba(white2, (1 - bd / 0.3) * 0.35 * k);
        ctx.beginPath(); ctx.moveTo(q[0], q[1]); ctx.lineTo(nb[0], nb[1]); ctx.stroke(); }
      ctx.fillStyle = rgba(white2, 0.5 * k); ctx.beginPath(); ctx.arc(q[0], q[1], Math.max(1, S * 0.009), 0, TAU); ctx.fill();
    });
    // импульсы по связям с цепной реакцией
    const rate = 0.8 + lv * 10 + (e.state === "thinking" ? 8 : 0) + (e.state === "listening" ? 1.5 : 0);
    m.acc = Math.min(3, m.acc + dt * rate * (reduced ? 0.3 : 1));
    while (m.acc > 1 && m.pulses.length < 40) {
      m.acc -= 1;
      const n0 = Math.floor(Math.random() * B.nodes.length), ed = B.adj[n0];
      if (ed.length) m.pulses.push({ e: ed[Math.floor(Math.random() * ed.length)], from: n0, p: 0, v: 0.9 + Math.random(), gen: 0 });
    }
    const next = [];
    m.pulses.forEach(pu => {
      pu.p += dt * pu.v * (e.state === "thinking" ? 2 : 1.1);
      const [a, b] = B.edges[pu.e], to = pu.from === a ? b : a;
      if (pu.p >= 1) {
        m.flash[to] = 1;
        if (pu.gen < 4 && Math.random() < 0.5) {
          const opts = B.adj[to].filter(x => x !== pu.e);
          if (opts.length) next.push({ e: opts[Math.floor(Math.random() * opts.length)], from: to, p: 0, v: pu.v, gen: pu.gen + 1 });
        }
        return;
      }
      const A = P(B.nodes[pu.from].x, B.nodes[pu.from].y), Bb = P(B.nodes[to].x, B.nodes[to].y);
      const x = A[0] + (Bb[0] - A[0]) * pu.p, y = A[1] + (Bb[1] - A[1]) * pu.p;
      const tp = Math.max(0, pu.p - 0.3), tx = A[0] + (Bb[0] - A[0]) * tp, ty = A[1] + (Bb[1] - A[1]) * tp;
      const gr = ctx.createLinearGradient(tx, ty, x, y); gr.addColorStop(0, rgba(white2, 0)); gr.addColorStop(1, rgba(white2, 0.95 * k));
      ctx.strokeStyle = gr; ctx.lineWidth = Math.max(1.2, S * 0.012); ctx.beginPath(); ctx.moveTo(tx, ty); ctx.lineTo(x, y); ctx.stroke();
      next.push(pu);
    });
    m.pulses = next.slice(-50);
    B.nodes.forEach((n, i) => {
      m.flash[i] = Math.max(0, m.flash[i] - dt * 2);
      const q = P(n.x, n.y), f = m.flash[i], tw = 0.6 + 0.4 * Math.sin(t * 1.4 + n.ph);
      const rad = Math.max(1.3, S * (n.core ? 0.018 : 0.013)) * (1 + f * 0.9 + lv * 0.3);
      ctx.save(); ctx.shadowColor = rgba(c, 1); ctx.shadowBlur = 4 + f * 14;
      ctx.fillStyle = rgba(mix(white2, [255, 255, 255], f), Math.min(1, (0.55 + 0.35 * tw + f) * k));
      ctx.beginPath(); ctx.arc(q[0], q[1], rad, 0, TAU); ctx.fill(); ctx.restore();
    });
  }

  // Голографический мозг (Профессор) — облако нейронов в форме мозга (вид сбоку: лобная, височная доли,
  // мозжечок, ствол), медленно поворачивается; узлы связаны, по связям бегут импульсы.
  const HOLO = (() => {
    const R = rng(777), P = [];
    const gauss = () => { let u = 0, v = 0; while (!u) u = R(); while (!v) v = R(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(TAU * v); };
    const dir = () => { const a = [gauss(), gauss(), gauss()], n = Math.hypot(...a); return a.map(x => x / n); };
    // полушария: x — поперёк, y — вниз, z — вперёд
    const hemi = (side, n) => {
      for (let i = 0; i < n; i++) {
        let [dx, dy, dz] = dir();
        if (dx * side < -0.25) dx = -dx;                            // внутренняя сторона уплощена
        let rx = 0.44, ry = 0.62, rz = 0.92;
        if (dy > 0) ry *= 0.72 + 0.28 * Math.max(0, -dz);            // низ плоский, кроме затылка
        if (dz < 0) { rz *= 0.95; ry *= 1 - 0.1 * (-dz); }           // затылок уже
        if (dy > 0.15 && dz > -0.1 && dz < 0.75) { ry *= 1.18; rz *= 0.96; }  // височная доля
        const fold = 1 + 0.05 * Math.sin(dz * 11 + dy * 7) * Math.sin(dy * 9 - dx * 5);   // извилины
        const x = side * 0.25 + dx * rx * fold, y = -0.06 + dy * ry * fold, z = 0.06 + dz * rz * fold;
        if (Math.abs(x) < 0.03) continue;
        P.push({ x, y, z, part: 0 });
      }
    };
    hemi(-1, 330); hemi(1, 330);
    for (let i = 0; i < 90; i++) {                                     // мозжечок
      const [dx, dy, dz] = dir(); const f = 1 + 0.07 * Math.sin(dy * 22);
      P.push({ x: dx * 0.36 * f, y: 0.42 + dy * 0.17 * f, z: -0.62 + dz * 0.26 * f, part: 1 });
    }
    for (let i = 0; i < 28; i++) {                                     // ствол
      const a = R() * TAU, t = R();
      P.push({ x: Math.cos(a) * 0.1, y: 0.35 + t * 0.55, z: -0.26 - t * 0.12 + Math.sin(a) * 0.1, part: 2 });
    }
    const edges = [], seen = new Set();
    P.forEach((a, i) => {
      P.map((b, j) => [j, Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z)]).filter(([j]) => j !== i)
        .sort((u, v) => u[1] - v[1]).slice(0, 3).forEach(([j, d]) => {
          const key = i < j ? i + "-" + j : j + "-" + i;
          if (d < 0.2 && !seen.has(key)) { seen.add(key); edges.push([i, j]); }
        });
    });
    const adj = P.map(() => []);
    edges.forEach(([a, b], n) => { adj[a].push(n); adj[b].push(n); });
    const hubs = P.map((_, i) => i).filter(i => i % 17 === 0);
    return { P, edges, adj, hubs };
  })();

  function holobrain(g, e) {
    const { ctx, r, c, t, lv, k } = g;
    const H = HOLO, bold = e.bold || 1, S = r * 0.86 * (bold > 1 ? 1.12 : 1);
    const m = e._hb || (e._hb = { pulses: [], acc: 0, lt: null, flash: new Float32Array(H.P.length) });
    const dt = m.lt === null ? 0 : Math.max(0, Math.min(0.1, t - m.lt)); m.lt = t;
    const yaw = -1.25 + Math.sin(t * 0.22) * 0.75, pitch = 0.12 + Math.sin(t * 0.15) * 0.06;
    const cy = Math.cos(yaw), sy = Math.sin(yaw), cp = Math.cos(pitch), sp = Math.sin(pitch);
    const breath = 1 + Math.sin(t * 1.3) * 0.01 + lv * 0.035;
    const n = H.P.length, X = new Float32Array(n), Y = new Float32Array(n), Z = new Float32Array(n);
    for (let i = 0; i < n; i++) {
      const p = H.P[i];
      const x1 = p.x * cy + p.z * sy, z1 = -p.x * sy + p.z * cy;
      const y2 = p.y * cp - z1 * sp, z2 = p.y * sp + z1 * cp;
      const f = 2.8 / (2.8 - z2);                                        // лёгкая перспектива
      X[i] = x1 * S * f * breath; Y[i] = (y2 - 0.12) * S * f * breath; Z[i] = z2;
    }
    const white = mix(c, [255, 255, 255], 0.55);
    // свечение и «проектор» под мозгом
    const halo = ctx.createRadialGradient(0, -S * 0.05, 0, 0, -S * 0.05, S * 1.05);
    halo.addColorStop(0, rgba(c, (0.13 + lv * 0.2) * k)); halo.addColorStop(1, rgba(c, 0));
    ctx.fillStyle = halo; ctx.beginPath(); ctx.arc(0, 0, S * 1.05, 0, TAU); ctx.fill();
    ctx.strokeStyle = rgba(c, 0.18 * k); ctx.lineWidth = 1;
    ctx.beginPath(); ctx.ellipse(0, S * 0.9, S * 0.5, S * 0.075, 0, 0, TAU); ctx.stroke();
    // связи — три слоя глубины, по пути на слой (дёшево даже без видеокарты)
    const lw = Math.max(0.6, S * 0.0055);
    for (let b = 0; b < 3; b++) {
      ctx.beginPath();
      for (const [a, bb] of H.edges) {
        const zz = (Z[a] + Z[bb]) / 2, band = zz < -0.3 ? 0 : zz < 0.25 ? 1 : 2;
        if (band !== b) continue;
        ctx.moveTo(X[a], Y[a]); ctx.lineTo(X[bb], Y[bb]);
      }
      ctx.lineWidth = lw * bold; ctx.strokeStyle = rgba(white, Math.min(1, [0.07, 0.16, 0.3][b] * k * (1 + lv * 0.6) * bold)); ctx.stroke();
    }
    // нейроны
    for (let b = 0; b < 3; b++) {
      ctx.fillStyle = rgba(mix(white, [255, 255, 255], b * 0.25), [0.3, 0.55, 0.9][b] * k);
      const sz = Math.max(0.9, S * [0.008, 0.011, 0.015][b]) * bold;
      ctx.beginPath();
      for (let i = 0; i < n; i++) {
        const band = Z[i] < -0.3 ? 0 : Z[i] < 0.25 ? 1 : 2;
        if (band !== b) continue;
        ctx.moveTo(X[i] + sz, Y[i]); ctx.arc(X[i], Y[i], sz, 0, TAU);
      }
      ctx.fill();
    }
    // импульсы по связям с цепной реакцией
    const rate = 1 + lv * 12 + (e.state === "thinking" ? 10 : 0) + (e.state === "listening" ? 2 : 0);
    m.acc = Math.min(4, m.acc + dt * rate * (reduced ? 0.3 : 1));
    while (m.acc > 1 && m.pulses.length < 48) {
      m.acc -= 1;
      const n0 = H.hubs[Math.floor(Math.random() * H.hubs.length)], ed = H.adj[n0];
      if (ed.length) m.pulses.push({ e: ed[Math.floor(Math.random() * ed.length)], from: n0, p: 0, v: 1.2 + Math.random(), gen: 0 });
    }
    const next = [];
    ctx.lineWidth = Math.max(1.1, S * 0.011); ctx.lineCap = "round";
    for (const pu of m.pulses) {
      pu.p += dt * pu.v * (e.state === "thinking" ? 2.2 : 1.3);
      const [a, b] = H.edges[pu.e], to = pu.from === a ? b : a;
      if (pu.p >= 1) {
        m.flash[to] = 1;
        if (pu.gen < 6 && Math.random() < 0.7) {
          const opts = H.adj[to].filter(x => x !== pu.e);
          if (opts.length) next.push({ e: opts[Math.floor(Math.random() * opts.length)], from: to, p: 0, v: pu.v, gen: pu.gen + 1 });
        }
        continue;
      }
      const x = X[pu.from] + (X[to] - X[pu.from]) * pu.p, y = Y[pu.from] + (Y[to] - Y[pu.from]) * pu.p;
      const q = Math.max(0, pu.p - 0.45), tx = X[pu.from] + (X[to] - X[pu.from]) * q, ty = Y[pu.from] + (Y[to] - Y[pu.from]) * q;
      ctx.strokeStyle = rgba([255, 255, 255], 0.85 * k); ctx.beginPath(); ctx.moveTo(tx, ty); ctx.lineTo(x, y); ctx.stroke();
      next.push(pu);
    }
    m.pulses = next.slice(-70);
    ctx.save(); ctx.shadowColor = rgba(c, 1);
    for (let i = 0; i < n; i++) {
      const f = m.flash[i]; if (f <= 0.02) continue;
      m.flash[i] = Math.max(0, f - dt * 2.4);
      ctx.shadowBlur = 6 + f * 12; ctx.fillStyle = rgba([255, 255, 255], Math.min(1, f + 0.2) * k);
      ctx.beginPath(); ctx.arc(X[i], Y[i], Math.max(1.4, S * 0.02) * (0.6 + f), 0, TAU); ctx.fill();
    }
    ctx.restore();
    if (e.state === "thinking") {                                        // мягкая голографическая развёртка
      const yb = ((t * 0.7) % 1) * S * 1.8 - S * 0.95, hh = S * 0.22;
      const gb = ctx.createLinearGradient(0, yb - hh, 0, yb + hh);
      gb.addColorStop(0, rgba(c, 0)); gb.addColorStop(0.5, rgba(c, 0.07 * k)); gb.addColorStop(1, rgba(c, 0));
      ctx.fillStyle = gb; ctx.fillRect(-S * 1.2, yb - hh, S * 2.4, hh * 2);
    }
  }

  // «Сфера» (aura) — стеклянная сфера: пастельное свечение, кольцо с переливом, полупрозрачные лепестки, которые
  // медленно вращаются и набухают; в центре тёмный круг со строгой иконкой или фото персонажа
  // (поэтому при своём фото стиль aura не заменяют на photo). Сфера сама себе фон: без диска-подложки
  // и кольца состояния, рисуется только обычным наложением (без «lighter») — чисто и на прозрачном окне.
  // hueShift — тот же цвет, повёрнутый по оттенку на deg градусов (второй цвет перелива).
  function hueShift(c, deg) {
    let [r, g, b] = c.map(v => v / 255); const mx = Math.max(r, g, b), mn = Math.min(r, g, b), l = (mx + mn) / 2;
    let h = 0, s = 0;
    if (mx !== mn) { const d = mx - mn; s = l > 0.5 ? d / (2 - mx - mn) : d / (mx + mn);
      h = mx === r ? (g - b) / d + (g < b ? 6 : 0) : mx === g ? (b - r) / d + 2 : (r - g) / d + 4; h /= 6; }
    h = (h + deg / 360 + 1) % 1;
    const f = (p, q, t) => { t = (t + 1) % 1; return t < 1 / 6 ? p + (q - p) * 6 * t : t < 1 / 2 ? q : t < 2 / 3 ? p + (q - p) * (2 / 3 - t) * 6 : p; };
    const q = l < 0.5 ? l * (1 + s) : l + s - l * s, pp = 2 * l - q;
    return [f(pp, q, h + 1 / 3), f(pp, q, h), f(pp, q, h - 1 / 3)].map(v => Math.round(v * 255));
  }
  const BRAIN_ICON = [   // линейная иконка 100×100: слева извилины, справа схема
    "M50 17C44 10 33 11 30 19C21 17 14 25 17 34C9 38 8 50 15 55C10 63 15 73 24 73C26 82 35 87 43 82C46 87 50 87 50 87",
    "M50 17C56 10 67 11 70 19C79 17 86 25 83 34C91 38 92 50 85 55C90 63 85 73 76 73C74 82 65 87 57 82C54 87 50 87 50 87",
    "M50 17V87", "M30 19C33 27 28 32 22 33", "M17 34C25 37 29 45 24 52", "M24 73C27 64 35 63 38 57", "M39 30C44 36 39 44 43 49",
    "M50 30H61L67 24", "M50 44H73", "M50 58H60L67 65", "M50 72H63",
  ];
  const BRAIN_NODES = [[70, 21], [77, 44], [70, 68], [67, 72]];
  const _icon = typeof Path2D !== "undefined" ? BRAIN_ICON.map(d => new Path2D(d)) : [];

  function aura(g, e) {
    const { ctx, r, c, t, lv, k } = g;
    const warm = (() => { const [a, b2, d] = c; const mx = Math.max(a, b2, d); return mx === a || (mx === b2 && a > d); })();
    const icon = (e.bold || 1) > 1;                                  // плотный вариант для иконки приложения
    const c1 = c, c2 = hueShift(c, warm ? -48 : 58), R = r * (icon ? 1.1 : 0.74) * (1 + lv * 0.035 * (e.state === "speaking" ? 1 : 0.5));
    const sat = e.state === "offline" ? 0.25 : 1;
    // свечение: два пятна разных оттенков медленно обходят сферу — перелив
    for (const [col, ph, a] of [[c1, 0, 0.34], [c2, Math.PI, 0.3]]) {
      const ang = t * 0.35 + ph, ox = Math.cos(ang) * R * 0.22, oy = Math.sin(ang) * R * 0.22;
      const GR = icon ? 1.13 : 1.55;
      const gl = ctx.createRadialGradient(ox, oy, R * 0.5, ox, oy, R * GR);
      gl.addColorStop(0, rgba(col, a * k * sat * (1 + lv * 0.9))); gl.addColorStop(1, rgba(col, 0));
      ctx.fillStyle = gl; ctx.beginPath(); ctx.arc(ox, oy, R * GR, 0, TAU); ctx.fill();
    }
    // стеклянное тело
    const body = ctx.createRadialGradient(-R * 0.25, -R * 0.3, R * 0.1, 0, 0, R);
    body.addColorStop(0, rgba([255, 255, 255], 0.62 * sat + 0.2)); body.addColorStop(0.7, rgba(mix(c1, [255, 255, 255], 0.55), 0.38));
    body.addColorStop(1, rgba(mix(c2, [255, 255, 255], 0.3), 0.42));
    ctx.fillStyle = body; ctx.beginPath(); ctx.arc(0, 0, R, 0, TAU); ctx.fill();
    // лепестки
    ctx.save(); ctx.beginPath(); ctx.arc(0, 0, R * 0.985, 0, TAU); ctx.clip();
    const speed = e.state === "thinking" ? 0.9 : e.state === "listening" ? 0.35 : 0.16;
    e._ang = (e._ang || 0) + speed * (e._dt || 0.03);
    for (let i = 0; i < 5; i++) {
      const rot = i * Math.PI / 5 + e._ang * (i % 2 ? 1 : -0.7);
      const swell = 1 + 0.13 * Math.sin(t * 1.1 + i * 1.7) + lv * (e.state === "listening" ? 0.5 : 0.3);
      ctx.save(); ctx.rotate(rot);
      const a = R * 0.95, b = R * 0.36 * swell;
      const pg = ctx.createLinearGradient(0, -b, 0, b);
      pg.addColorStop(0, rgba([255, 255, 255], 0.5)); pg.addColorStop(0.5, rgba(mix(i % 2 ? c1 : c2, [255, 255, 255], 0.55), 0.12));
      pg.addColorStop(1, rgba([255, 255, 255], 0.35));
      ctx.fillStyle = pg; ctx.strokeStyle = rgba([255, 255, 255], 0.55); ctx.lineWidth = Math.max(0.8, R * 0.008);
      ctx.beginPath(); ctx.ellipse(0, 0, a, b, 0, 0, TAU); ctx.fill(); ctx.stroke();
      ctx.restore();
    }
    for (let i = 0; i < 3; i++) {                                   // мягкие «капли» в глубине
      const ang = t * (0.25 + i * 0.07) + i * 2.1, d = R * (0.55 + 0.1 * Math.sin(t * 0.7 + i));
      const x = Math.cos(ang) * d, y = Math.sin(ang) * d * 0.8, rr = R * 0.085;
      const dg = ctx.createRadialGradient(x, y, 0, x, y, rr);
      dg.addColorStop(0, rgba(mix(c1, [60, 70, 90], 0.5), 0.45)); dg.addColorStop(1, rgba(c1, 0));
      ctx.fillStyle = dg; ctx.beginPath(); ctx.arc(x, y, rr, 0, TAU); ctx.fill();
    }
    ctx.restore();
    // кольцо с переливом
    const ring = ctx.createLinearGradient(-R, 0, R, 0);
    ring.addColorStop(0, rgba(c2, 0.95)); ring.addColorStop(0.5, rgba(mix(c2, c1, 0.5), 0.7)); ring.addColorStop(1, rgba(c1, 0.95));
    ctx.save(); ctx.rotate(t * 0.2);
    ctx.strokeStyle = ring; ctx.lineWidth = R * 0.05 * (1 + lv * 0.6); ctx.beginPath(); ctx.arc(0, 0, R * 0.99, 0, TAU); ctx.stroke();
    if (e.state === "thinking") {                                   // перелив бежит по кольцу
      ctx.rotate(t * 2.6);
      ctx.strokeStyle = rgba([255, 255, 255], 0.9); ctx.lineWidth = R * 0.045; ctx.lineCap = "round";
      ctx.beginPath(); ctx.arc(0, 0, R * 0.99, 0, 0.9); ctx.stroke();
    }
    ctx.restore();
    // центр: тёмный круг и иконка (или фото персонажа)
    const CR = R * (icon ? 0.52 : 0.4);
    const sh = ctx.createRadialGradient(0, 0, CR * 0.9, 0, 0, CR * 1.35);
    sh.addColorStop(0, "rgba(10,12,20,0.35)"); sh.addColorStop(1, "rgba(10,12,20,0)");
    ctx.fillStyle = sh; ctx.beginPath(); ctx.arc(0, 0, CR * 1.35, 0, TAU); ctx.fill();
    ctx.save(); ctx.beginPath(); ctx.arc(0, 0, CR, 0, TAU); ctx.fillStyle = "#0B0C11"; ctx.fill(); ctx.clip();
    if (e.img && e.img.complete && e.img.naturalWidth) {
      const iw = e.img.naturalWidth, ih = e.img.naturalHeight, sc = Math.max(2 * CR / iw, 2 * CR / ih);
      ctx.drawImage(e.img, -iw * sc / 2, -ih * sc / 2, iw * sc, ih * sc);
    } else if (_icon.length) {
      const sz = CR * 1.5, pulse = 1 + (e.state === "speaking" ? lv * 0.06 : 0);
      ctx.save(); ctx.scale(sz / 100 * pulse, sz / 100 * pulse); ctx.translate(-50, -52);
      ctx.strokeStyle = "rgba(255,255,255,0.96)"; ctx.lineWidth = Math.max(3.2, 110 / sz); ctx.lineCap = "round"; ctx.lineJoin = "round";
      _icon.forEach(p2 => ctx.stroke(p2));
      ctx.fillStyle = "#0B0C11";
      BRAIN_NODES.forEach(([x, y]) => { ctx.beginPath(); ctx.arc(x, y, 3.6, 0, TAU); ctx.fill(); ctx.stroke(); });
      ctx.restore();
    }
    ctx.restore();
  }

  function lattice(g, e) {                       // кристалл-икосаэдр (Оскар)
    const { ctx, r, c, t, lv, k } = g;
    if (!e._ico) {
      const p = (1 + Math.sqrt(5)) / 2, v = [];
      [[-1, p, 0], [1, p, 0], [-1, -p, 0], [1, -p, 0], [0, -1, p], [0, 1, p], [0, -1, -p], [0, 1, -p], [p, 0, -1], [p, 0, 1], [-p, 0, -1], [-p, 0, 1]]
        .forEach(([x, y, z]) => { const n = Math.hypot(x, y, z); v.push([x / n, y / n, z / n]); });
      const ed = [];
      for (let i = 0; i < 12; i++) for (let j = i + 1; j < 12; j++) {
        const d = Math.hypot(v[i][0] - v[j][0], v[i][1] - v[j][1], v[i][2] - v[j][2]); if (d < 1.1) ed.push([i, j]);
      }
      e._ico = { v, ed };
    }
    const ay = t * 0.45, ax = 0.5 + Math.sin(t * 0.23) * 0.3, cy = Math.cos(ay), sy = Math.sin(ay), cx = Math.cos(ax), sx = Math.sin(ax);
    const R = r * (0.66 + lv * 0.06);
    const P = e._ico.v.map(([x, y, z]) => { const x1 = x * cy + z * sy, z1 = -x * sy + z * cy, y2 = y * cx - z1 * sx, z2 = y * sx + z1 * cx; return [x1 * R, y2 * R, z2]; });
    const inner = P.map(([x, y, z]) => [x * 0.48, y * 0.48, z]);
    const grd = ctx.createRadialGradient(0, 0, 0, 0, 0, R * 0.7);
    grd.addColorStop(0, rgba([255, 255, 255], (0.55 + lv * 0.4) * k)); grd.addColorStop(0.25, rgba(c, 0.45 * k)); grd.addColorStop(1, rgba(c, 0));
    ctx.fillStyle = grd; ctx.beginPath(); ctx.arc(0, 0, R * 0.7, 0, TAU); ctx.fill();
    const pulse = (t * 0.9) % 1;
    e._ico.ed.forEach(([i, j], n) => {
      const d = (P[i][2] + P[j][2] + 2) / 4;
      const hot = Math.max(0, 1 - Math.abs(((n / e._ico.ed.length) - pulse)) * 6) * (0.4 + lv);
      ctx.strokeStyle = rgba(mix(c, [255, 255, 255], hot * 0.6), (0.15 + d * 0.6 + hot * 0.5) * k);
      ctx.lineWidth = 0.8 + d * 1.2 + hot * 1.5;
      ctx.beginPath(); ctx.moveTo(P[i][0], P[i][1]); ctx.lineTo(P[j][0], P[j][1]); ctx.stroke();
      ctx.strokeStyle = rgba(c, (0.08 + d * 0.2) * k); ctx.lineWidth = 0.7;
      ctx.beginPath(); ctx.moveTo(inner[i][0], inner[i][1]); ctx.lineTo(inner[j][0], inner[j][1]); ctx.stroke();
    });
    P.forEach(([x, y, z], i) => {
      const d = (z + 1) / 2;
      ctx.strokeStyle = rgba(c, 0.12 * d * k); ctx.lineWidth = 0.6;
      ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(inner[i][0], inner[i][1]); ctx.stroke();
      ctx.fillStyle = rgba(mix(c, [255, 255, 255], 0.5 + d * 0.5), (0.3 + d * 0.7) * k);
      ctx.shadowColor = rgba(c, 1); ctx.shadowBlur = 6 + d * 10 + lv * 12;
      ctx.beginPath(); ctx.arc(x, y, 1.4 + d * 2.4 + lv * 2, 0, TAU); ctx.fill(); ctx.shadowBlur = 0;
    });
    for (let i = 0; i < 2; i++) {
      const q = (t * 0.3 + i / 2) % 1;
      ctx.strokeStyle = rgba(c, (1 - q) * 0.3 * k); ctx.lineWidth = 1;
      ctx.beginPath(); ctx.arc(0, 0, R * (1.02 + q * 0.3), 0, TAU); ctx.stroke();
    }
  }

  // Нейросфера (Агент; ею же нарисован значок студии). Узлы на сфере, каждый связан с ближайшими; по связям бегут импульсы и
  // зажигают следующие — цепочки «мыслей». Цвет — от цвета персонажа спереди к сдвинутому оттенку в глубине (у синего — фиолетовый).
  // Голос раздувает сферу и учащает импульсы, в раздумьях импульсов больше и они быстрее.
  function nexus(g, e) {
    const { ctx, r, c, t, lv } = g, k = Math.max(g.k, 0.82);   // в покое не тускнеет — «спит», но светится
    if (!e._nx) {
      const rnd = rng(7), N = 72, ga = Math.PI * (3 - Math.sqrt(5)), v = [];
      for (let i = 0; i < N; i++) {
        const y = 1 - (i + 0.5) / N * 2, rad = Math.sqrt(1 - y * y), th = ga * i;
        const j = 0.86 + rnd() * 0.14;
        v.push([Math.cos(th) * rad * j, y * j, Math.sin(th) * rad * j, rnd() * TAU]);
      }
      for (let i = 0; i < 10; i++) {                 // несколько узлов внутри — объём
        const a = rnd() * TAU, b = Math.acos(2 * rnd() - 1), q = 0.25 + rnd() * 0.35;
        v.push([Math.sin(b) * Math.cos(a) * q, Math.cos(b) * q, Math.sin(b) * Math.sin(a) * q, rnd() * TAU]);
      }
      const seen = new Set(), ed = [], nb = v.map(() => []);
      v.forEach((p, i) => {
        v.map((q, j) => [j, Math.hypot(p[0] - q[0], p[1] - q[1], p[2] - q[2])]).filter(([j]) => j !== i)
          .sort((a, b) => a[1] - b[1]).slice(0, i < N ? 3 : 4).forEach(([j]) => {
            const key = i < j ? i + ":" + j : j + ":" + i;
            if (!seen.has(key)) { seen.add(key); ed.push([Math.min(i, j), Math.max(i, j)]); }
            if (!nb[i].includes(j)) nb[i].push(j); if (!nb[j].includes(i)) nb[j].push(i);
          });
      });
      e._nx = { v, ed, nb, sig: [], rnd, lt: t, spawn: 0 };
    }
    const sc = Math.min(1.25, Math.max(0.38, r / 95)) * (e.bold || 1);   // мелкий значок — тоньше; иконке — жирнее
    const X = e._nx, dt = Math.max(0, Math.min(0.2, t - X.lt)); X.lt = t;
    const violet = hueShift(c, 58), front = hueShift(c, -22), white = [255, 255, 255];
    const ay = t * 0.32, ax = 0.35 + Math.sin(t * 0.17) * 0.25;
    const cy = Math.cos(ay), sy = Math.sin(ay), cx = Math.cos(ax), sx = Math.sin(ax);
    const R = r * (0.74 + lv * 0.07);
    const P = X.v.map(([x, y, z, ph]) => {
      const w = 1 + lv * 0.06 * Math.sin(ph + t * 5);
      const x1 = x * cy + z * sy, z1 = -x * sy + z * cy, y2 = y * cx - z1 * sx, z2 = y * sx + z1 * cx;
      return [x1 * R * w, y2 * R * w, z2];
    });
    const col = (d) => mix(violet, front, d);      // глубина 0 (сзади) … 1 (спереди) → violet…front
    // мягкое ядро
    const core = ctx.createRadialGradient(0, 0, 0, 0, 0, R * 0.95);
    core.addColorStop(0, rgba(mix(c, white, 0.3), (0.34 + lv * 0.3) * k));
    core.addColorStop(0.5, rgba(violet, 0.16 * k)); core.addColorStop(1, rgba(violet, 0));
    ctx.fillStyle = core; ctx.beginPath(); ctx.arc(0, 0, R * 0.95, 0, TAU); ctx.fill();
    // связи: сначала дальние
    ctx.lineCap = "round";
    const order = X.ed.map((ed, n) => [n, (P[ed[0]][2] + P[ed[1]][2]) / 2]).sort((a, b) => a[1] - b[1]);
    for (const [n, zz] of order) {
      const [i, j] = X.ed[n], d = (zz + 1) / 2;
      ctx.strokeStyle = rgba(col(d), (0.10 + d * 0.45) * k); ctx.lineWidth = (0.6 + d * 1.0) * sc;
      ctx.beginPath(); ctx.moveTo(P[i][0], P[i][1]); ctx.lineTo(P[j][0], P[j][1]); ctx.stroke();
    }
    // импульсы
    X.spawn += dt * (0.9 + lv * 5 + (e.state === "thinking" ? 3 : 0));
    while (X.spawn > 1 && X.sig.length < 26) {
      X.spawn -= 1; const a = Math.floor(X.rnd() * X.v.length), nb = X.nb[a];
      X.sig.push({ a, b: nb[Math.floor(X.rnd() * nb.length)], p: 0, life: 2 + Math.floor(X.rnd() * 3) });
    }
    X.spawn = Math.min(X.spawn, 1);
    const fire = new Map();
    X.sig = X.sig.filter(s => {
      s.p += dt * 1.6;
      if (s.p >= 1) {
        fire.set(s.b, 1);
        if (--s.life <= 0) return false;
        const nb = X.nb[s.b].filter(x => x !== s.a); s.a = s.b; s.b = nb.length ? nb[Math.floor(X.rnd() * nb.length)] : s.a; s.p = 0;
      }
      return true;
    });
    X.glow = X.glow || new Float32Array(X.v.length);
    for (let i = 0; i < X.glow.length; i++) X.glow[i] = Math.max(fire.get(i) || 0, X.glow[i] * Math.exp(-dt * 3.2));
    for (const s of X.sig) {
      const A = P[s.a], B = P[s.b], x = A[0] + (B[0] - A[0]) * s.p, y = A[1] + (B[1] - A[1]) * s.p;
      const d = ((A[2] + (B[2] - A[2]) * s.p) + 1) / 2;
      // светящийся след вдоль связи
      const tx = A[0] + (B[0] - A[0]) * Math.max(0, s.p - 0.35), ty = A[1] + (B[1] - A[1]) * Math.max(0, s.p - 0.35);
      const gr = ctx.createLinearGradient(tx, ty, x, y);
      gr.addColorStop(0, rgba(c, 0)); gr.addColorStop(1, rgba(mix(c, white, 0.6), (0.35 + d * 0.6) * k));
      ctx.strokeStyle = gr; ctx.lineWidth = (1 + d * 1.2) * sc;
      ctx.beginPath(); ctx.moveTo(tx, ty); ctx.lineTo(x, y); ctx.stroke();
      ctx.fillStyle = rgba(mix(c, white, 0.75), (0.5 + d * 0.5) * k);
      ctx.shadowColor = rgba(c, 1); ctx.shadowBlur = (8 + d * 8) * sc;
      ctx.beginPath(); ctx.arc(x, y, (1 + d * 1.4) * sc, 0, TAU); ctx.fill(); ctx.shadowBlur = 0;
    }
    // узлы, дальние — первыми
    const nodes = P.map((p, i) => [i, p]).sort((a, b) => a[1][2] - b[1][2]);
    for (const [i, [x, y, z]] of nodes) {
      const d = (z + 1) / 2, h = X.glow[i];
      const rr = (0.9 + d * 1.9 + h * 2.2) * sc;
      if (h > 0.05) {
        const hg = ctx.createRadialGradient(x, y, 0, x, y, rr * 5);
        hg.addColorStop(0, rgba(mix(c, white, 0.5), 0.5 * h * k)); hg.addColorStop(1, rgba(c, 0));
        ctx.fillStyle = hg; ctx.beginPath(); ctx.arc(x, y, rr * 5, 0, TAU); ctx.fill();
      }
      ctx.fillStyle = rgba(mix(col(d), white, 0.12 + d * 0.3 + h * 0.5), (0.3 + d * 0.7) * k);
      ctx.beginPath(); ctx.arc(x, y, rr, 0, TAU); ctx.fill();
    }
  }

  function orbital(g, e) {                       // Патрик: ядро и орбиты
    const { ctx, r, c, t, lv, k } = g;
    const core = r * (0.2 + lv * 0.1 + Math.sin(t * 2) * 0.01);
    const grd = ctx.createRadialGradient(0, 0, 0, 0, 0, core * 2.4);
    grd.addColorStop(0, rgba(mix(c, [255, 255, 255], 0.7), 0.95 * k));
    grd.addColorStop(0.35, rgba(c, 0.75 * k));
    grd.addColorStop(1, rgba(c, 0));
    ctx.fillStyle = grd; ctx.beginPath(); ctx.arc(0, 0, core * 2.4, 0, TAU); ctx.fill();
    const tilts = [0.35, 1.4, 2.5];
    tilts.forEach((tilt, i) => {
      const a = r * (0.62 + i * 0.1), b = a * (0.28 + 0.05 * i);
      ctx.save(); ctx.rotate(tilt + t * 0.05 * (i + 1));
      ctx.strokeStyle = rgba(c, 0.35 * k); ctx.lineWidth = 1.2;
      ctx.beginPath(); ctx.ellipse(0, 0, a, b, 0, 0, TAU); ctx.stroke();
      for (let j = 0; j < 2; j++) {
        const ph = t * (0.9 + i * 0.35) + j * Math.PI + i;
        const x = Math.cos(ph) * a, y = Math.sin(ph) * b;
        const s = 2.2 + lv * 3 + (Math.sin(ph) > 0 ? 1 : 0);
        ctx.fillStyle = rgba(mix(c, [255, 255, 255], 0.5), 0.95 * k);
        ctx.shadowColor = rgba(c, 1); ctx.shadowBlur = 10;
        ctx.beginPath(); ctx.arc(x, y, s, 0, TAU); ctx.fill(); ctx.shadowBlur = 0;
      }
      ctx.restore();
    });
  }

  function tactical(g, e) {                      // Кодер: гексагональный радар
    const { ctx, r, c, t, lv, k } = g;
    const hex = (R, rot = 0) => {
      ctx.beginPath();
      for (let i = 0; i <= 6; i++) { const a = rot + i * TAU / 6; ctx[i ? "lineTo" : "moveTo"](Math.cos(a) * R, Math.sin(a) * R); }
    };
    ctx.lineWidth = 1.5; ctx.strokeStyle = rgba(c, 0.8 * k); hex(r * 0.9, Math.PI / 6); ctx.stroke();
    ctx.lineWidth = 1; ctx.strokeStyle = rgba(c, 0.35 * k); hex(r * 0.8, Math.PI / 6); ctx.stroke();
    const sweep = (t * 1.2) % TAU;
    const cell = r * 0.11;
    for (let q = -6; q <= 6; q++) for (let s = -6; s <= 6; s++) {
      const x = cell * 1.5 * q, y = cell * Math.sqrt(3) * (s + q / 2);
      const d = Math.hypot(x, y); if (d > r * 0.72) continue;
      let da = (Math.atan2(y, x) - sweep) % TAU; if (da < 0) da += TAU;
      const lit = Math.max(0, 1 - da / 2.2) * (0.5 + lv) + 0.08 + (Math.sin(q * 3.1 + s * 1.7 + t) > 0.93 ? 0.5 : 0);
      ctx.strokeStyle = rgba(c, Math.min(1, lit) * k);
      ctx.save(); ctx.translate(x, y); hex(cell * 0.82); ctx.stroke(); ctx.restore();
    }
    const wedge = ctx.createConicGradient ? ctx.createConicGradient(sweep - 0.9, 0, 0) : null;
    if (wedge) {
      wedge.addColorStop(0, rgba(c, 0)); wedge.addColorStop(0.14, rgba(c, 0.28 * k)); wedge.addColorStop(0.145, rgba(c, 0));
      ctx.fillStyle = wedge; ctx.beginPath(); ctx.arc(0, 0, r * 0.74, 0, TAU); ctx.fill();
    }
    ctx.strokeStyle = rgba(c, 0.9 * k); ctx.lineWidth = 1.5;
    for (let i = 0; i < 4; i++) {
      const a = i * TAU / 4; ctx.beginPath();
      ctx.moveTo(Math.cos(a) * r * 0.94, Math.sin(a) * r * 0.94); ctx.lineTo(Math.cos(a) * r * 1.02, Math.sin(a) * r * 1.02); ctx.stroke();
    }
    ctx.fillStyle = rgba(c, (0.6 + lv * 0.4) * k); ctx.beginPath(); ctx.arc(0, 0, 3 + lv * 5, 0, TAU); ctx.fill();
  }

  function rings(g, e) {                          // Джарвис: сегментированные кольца
    const { ctx, r, c, t, lv, k } = g;
    const spec = [[0.92, 1, [2, 6], 0.25], [0.8, 3, [30, 10, 4, 10], -0.4], [0.66, 2, [60, 20], 0.7], [0.5, 1.5, [8, 8], -1.1]];
    spec.forEach(([rr, w, dash, sp], i) => {
      ctx.save(); ctx.rotate(t * sp);
      ctx.setLineDash(dash); ctx.lineWidth = w; ctx.strokeStyle = rgba(c, (0.35 + 0.15 * i + lv * 0.3) * k);
      ctx.beginPath(); ctx.arc(0, 0, r * rr, 0, TAU); ctx.stroke(); ctx.restore();
    });
    ctx.setLineDash([]);
    ctx.save(); ctx.rotate(-t * 0.9);
    ctx.lineWidth = 3; ctx.strokeStyle = rgba(mix(c, [255, 255, 255], 0.4), 0.9 * k);
    ctx.beginPath(); ctx.arc(0, 0, r * 0.74, 0, 0.9 + lv * 1.6); ctx.stroke();
    ctx.beginPath(); ctx.arc(0, 0, r * 0.74, Math.PI, Math.PI + 0.5 + lv); ctx.stroke(); ctx.restore();
    const core = r * (0.22 + lv * 0.12);
    const grd = ctx.createRadialGradient(0, 0, 0, 0, 0, core * 1.8);
    grd.addColorStop(0, rgba([255, 255, 255], 0.9 * k)); grd.addColorStop(0.3, rgba(c, 0.8 * k)); grd.addColorStop(1, rgba(c, 0));
    ctx.fillStyle = grd; ctx.beginPath(); ctx.arc(0, 0, core * 1.8, 0, TAU); ctx.fill();
    ctx.strokeStyle = rgba(c, 0.5 * k); ctx.lineWidth = 1;
    for (let i = 0; i < 60; i++) {
      const a = i * TAU / 60, l = i % 5 ? 0.03 : 0.07;
      ctx.beginPath(); ctx.moveTo(Math.cos(a) * r, Math.sin(a) * r); ctx.lineTo(Math.cos(a) * r * (1 - l), Math.sin(a) * r * (1 - l)); ctx.stroke();
    }
  }

  function strings(g, e) {                         // Лира: поющие струны
    const { ctx, r, c, t, lv, k } = g;
    ctx.strokeStyle = rgba(c, 0.55 * k); ctx.lineWidth = 1.2;
    ctx.beginPath(); ctx.arc(0, 0, r * 0.9, 0, TAU); ctx.stroke();
    ctx.save(); ctx.beginPath(); ctx.arc(0, 0, r * 0.86, 0, TAU); ctx.clip();
    const n = 11;
    for (let i = 0; i < n; i++) {
      const x = (i - (n - 1) / 2) * (r * 1.6 / n);
      const amp = r * (0.02 + lv * 0.16) * Math.sin(Math.PI * (i + 1) / (n + 1));
      const f = 1.5 + i * 0.35;
      ctx.beginPath();
      for (let y = -r; y <= r; y += 3) {
        const env = Math.cos((y / r) * Math.PI / 2);
        const dx = Math.sin(y / r * Math.PI * f + t * (3 + i * 0.4)) * amp * env;
        ctx[y === -r ? "moveTo" : "lineTo"](x + dx, y);
      }
      const bright = 0.35 + 0.5 * Math.abs(Math.sin(t * 0.8 + i));
      ctx.strokeStyle = rgba(mix(c, [255, 255, 255], bright * 0.4), (0.45 + bright * 0.45) * k);
      ctx.lineWidth = 1.4; ctx.shadowColor = rgba(c, 1); ctx.shadowBlur = 8; ctx.stroke();
    }
    ctx.restore(); ctx.shadowBlur = 0;
    for (let i = 0; i < 3; i++) {
      const rr = r * (0.9 + ((t * 0.25 + i / 3) % 1) * 0.12);
      ctx.strokeStyle = rgba(c, (1 - ((t * 0.25 + i / 3) % 1)) * 0.35 * k);
      ctx.beginPath(); ctx.arc(0, 0, rr, 0, TAU); ctx.stroke();
    }
  }

  function particles(g, e) {                       // Эва: живая сфера частиц
    const { ctx, r, c, t, lv, k } = g;
    if (!e._pts) {
      e._pts = []; const N = 260, ga = Math.PI * (3 - Math.sqrt(5));
      for (let i = 0; i < N; i++) {
        const y = 1 - (i / (N - 1)) * 2, rad = Math.sqrt(1 - y * y), th = ga * i;
        e._pts.push([Math.cos(th) * rad, y, Math.sin(th) * rad, Math.random() * TAU]);
      }
    }
    const ay = t * 0.5, ax = Math.sin(t * 0.3) * 0.4;
    const cy = Math.cos(ay), sy = Math.sin(ay), cx = Math.cos(ax), sx = Math.sin(ax);
    const R = r * 0.7;
    const pts = e._pts.map(([x, y, z, ph]) => {
      const x1 = x * cy + z * sy, z1 = -x * sy + z * cy;
      const y2 = y * cx - z1 * sx, z2 = y * sx + z1 * cx;
      const push = 1 + lv * 0.35 * (0.5 + 0.5 * Math.sin(ph + t * 6));
      return [x1 * R * push, y2 * R * push, z2];
    }).sort((a, b) => a[2] - b[2]);
    for (const [x, y, z] of pts) {
      const d = (z + 1) / 2;
      ctx.fillStyle = rgba(mix(c, [255, 255, 255], d * 0.5), (0.15 + d * 0.85) * k);
      ctx.beginPath(); ctx.arc(x, y, 0.8 + d * 2.1, 0, TAU); ctx.fill();
    }
    const grd = ctx.createRadialGradient(0, 0, 0, 0, 0, R * 0.9);
    grd.addColorStop(0, rgba(c, (0.25 + lv * 0.3) * k)); grd.addColorStop(1, rgba(c, 0));
    ctx.fillStyle = grd; ctx.beginPath(); ctx.arc(0, 0, R * 0.9, 0, TAU); ctx.fill();
  }

  // ---------- Живое лицо (из проекта Evo): портрет без зрачков + зрачки, рот и улыбка слоями поверх ----------
  // Глаза двигаются и моргают, рот открывается по голосу (несколько форм, плавный переход), в тишине иногда улыбается.
  // Слои лежат в папке live рядом с этим файлом (ui/assets/live, в телефоне — www/live): <имя>.webp — портрет 360×360
  // с белыми глазами, iris.png — зрачок, mouth-0..3 — рот (0 — закрыт), smile — улыбка. Координаты — в пикселях портрета.
  const LIVE_DIR = (() => { try { const src = document.currentScript && document.currentScript.src; return src ? src.replace(/[^/]*$/, "") + "live/" : "assets/live/"; } catch (x) { return "assets/live/"; } })();
  const LIVE_GEO = { eyes: [[141.1, 153.4], [205.2, 153.4]], iris: 14.4, mouth: [136.8, 180, 89.3, 69.1], crop: [0, 0, 360], moveX: 2.9, moveY: 1.45 };
  // свои цвета глаз (левый, правый на портрете), если общий iris.png не подходит; сейчас у всех — обычные глаза
  const LIVE_EYES = {};
  // Свой набор слоёв и геометрия (Патрик — tools/live_face.py): рот и улыбка <имя>-mouth-0..3 / <имя>-smile, маска
  // разреза глаз <имя>-eyes.png (зрачок рисуется только внутри неё — веки его прикрывают), цвет радужки, координаты.
  const LIVE_CONF = {
    // радужка — настоящая, вырезанная с портрета (iris: файлы), в покое лицо в точности как на фото; ходит чуть-чуть
    patrik: { own: true, mask: true, iris: ["patrik-iris-l.png", "patrik-iris-r.png"],
              geo: { eyes: [[140.8, 142.9], [206.5, 143.3]], iris: 12.0, mouth: [143.0, 201.0, 74.0, 44.0], moveX: 1.8, moveY: 0.5 } },
  };
  function irisOf(col) {                          // зрачок нужного цвета: чёрный центр, цветная радужка, блик
    const c = document.createElement("canvas"); c.width = c.height = 64;
    const x = c.getContext("2d"), g = x.createRadialGradient(32, 32, 0, 32, 32, 32);
    g.addColorStop(0, "#000"); g.addColorStop(0.34, "#060407"); g.addColorStop(0.46, col); g.addColorStop(0.78, col);
    g.addColorStop(1, "rgba(14,10,18,0.98)");
    x.fillStyle = g; x.beginPath(); x.arc(32, 32, 31, 0, TAU); x.fill();
    x.fillStyle = "rgba(255,255,255,0.4)"; x.beginPath(); x.arc(24, 23, 5, 0, TAU); x.fill();
    return c;
  }
  const LIVE_SETS = {};
  function liveSet(name) {                        // слои загружаются один раз на всё окно
    if (LIVE_SETS[name]) return LIVE_SETS[name];
    const C = LIVE_CONF[name] || {}, pre = C.own ? name + "-" : "";
    const L = LIVE_SETS[name] = { ready: false, failed: false, geo: Object.assign({}, LIVE_GEO, C.geo || {}) };
    const load = (f) => new Promise((ok, bad) => { const im = new Image(); im.onload = () => ok(im); im.onerror = bad; im.src = LIVE_DIR + f; });
    const cols = C.eyes || LIVE_EYES[name];
    Promise.all([load(name + ".webp"), load("iris.png"), load(pre + "smile.webp"), C.mask ? load(name + "-eyes.png") : Promise.resolve(null),
      C.iris ? Promise.all(C.iris.map(load)) : Promise.resolve(null), ...[0, 1, 2, 3].map(i => load(`${pre}mouth-${i}.webp`))])
      .then(([base, iris, smile, mask, own, ...mouths]) => Object.assign(L, { base, iris, smile, mask, mouths, ready: true,
        irises: own || (cols ? cols.map(irisOf) : [iris, iris]) }))
      .catch(() => { L.failed = true; });             // слоёв нет — остаётся обычное фото
    return L;
  }
  function liveFace(g, e, L) {
    const { ctx, r, c, t, lv, k } = g;
    const R = r * 0.78, now = performance.now(), dt = Math.min(0.1, e._dt || 0.016);
    const A = e._live || (e._live = { ex: 0, ey: 0, tx: 0, ty: 0, nextEye: now + 1500, blinkTill: 0, nextBlink: now + 2500 + Math.random() * 2500,
      smile: 0, smileTill: 0, mPrev: 0, mTarget: 0, mBlend: 1, nextMouth: 0, wasSpeaking: false, heard: 0 });
    const speaking = e.state === "speaking", thinking = e.state === "thinking";
    // глаза: говорит — прямо; думает — чуть вверх и в сторону; слушает — на вас; в покое — изредка осматривается
    // зритель известен (look) — смотрит на него: говорит и слушает — прямо на него, в покое — на него с редкими взглядами в сторону
    const vx = e._lx * L.geo.moveX * 0.45 * e.lookGain, vy = e._ly * L.geo.moveY * 0.45 * e.lookGain;   // _lx плавно уходит к 0
    if (speaking || e.state === "listening") { A.tx = vx; A.ty = vy; }
    else if (thinking) { A.tx = 0.9; A.ty = -0.9; }
    else if (e._looking && now <= A.nextEye) { A.tx = vx + (A.rx || 0) * 0.4; A.ty = vy + (A.ry || 0) * 0.4; }
    else if (now > A.nextEye) {
      A.rx = (Math.random() * 2 - 0.5) * L.geo.moveX / 2; A.ry = (Math.random() * 2 - 0.5) * L.geo.moveY / 2;
      A.tx = vx + A.rx * (e._looking ? 0.4 : 1); A.ty = vy + A.ry * (e._looking ? 0.4 : 1);
      if (!A.smileTill && Math.random() < 0.3) A.smileTill = now + 2000 + Math.random() * 2000;   // в тишине иногда улыбается
      A.nextEye = now + (Math.random() > 0.8 ? 500 : 3000 + Math.random() * 2000);
    }
    const ease = Math.min(1, dt * 10);
    A.ex += (A.tx - A.ex) * ease; A.ey += (A.ty - A.ey) * ease;
    if (now > A.nextBlink) { A.blinkTill = now + 110; A.nextBlink = now + 3200 + Math.random() * 3500; }
    // рот: говорит — меняем форму каждые ~110 мс по громкости, между формами — плавный переход.
    // Рот движется, только пока звук действительно идёт (e.sounding): голос с сервера приходит через 5–10 с после
    // «speaking» — всё это время рот закрыт (отзыв 14.10: «звука нет, а они болтают губами»). Уровень своего голоса
    // (компьютер) — ещё и в паузах между словами закрыт.
    if (e.level > 0.06) A.heard = now;
    const voiced = speaking && e.sounding(now) && (e._voiceSeen ? e.level > 0.04 : e._audibleKnown || now - A.heard > 1500 || e.level > 0.04);
    let want = A.mTarget;
    if (voiced) { if (now > A.nextMouth) { want = Math.random() < 0.12 ? 0 : 1 + Math.floor(Math.random() * 3); A.nextMouth = now + 90 + Math.random() * 60; } }
    else want = 0;
    if (want !== A.mTarget) { A.mPrev = A.mTarget; A.mTarget = want; A.mBlend = 0; }
    A.mBlend = Math.min(1, A.mBlend + dt * 9);
    if (A.wasSpeaking && !speaking && Math.random() < 0.5) A.smileTill = now + 1500;   // договорила — лёгкая улыбка
    A.wasSpeaking = speaking;
    if (A.smileTill && now > A.smileTill) A.smileTill = 0;
    const talking = A.mTarget !== 0 || (A.mPrev !== 0 && A.mBlend < 1);
    const smileGoal = !talking && A.smileTill && (e.state === "idle" || e.state === "listening") ? 1 : 0;
    A.smile += (smileGoal - A.smile) * Math.min(1, dt * 3);

    const neu = e.tone === "neu";
    ctx.save(); ctx.beginPath(); ctx.arc(0, 0, R, 0, TAU); ctx.clip();
    const G = L.geo, [cx0, cy0, cs] = G.crop;             // портрет целиком: видно причёску (хвостики Лиры), лицо не огромное
    // к зрителю — лёгкий сдвиг без увеличения: портрет целиком, кадр крупнее исходного (отзыв 14.10: «лицо стало крупнее,
    // еле вмещается в круге»); за краем кадра — тёмная подложка, при сдвиге в 3 % её не видно
    const gk = e.lookGain, z = 1, ox = e._lx * R * 0.03 * gk, oy = e._ly * R * 0.025 * gk;
    const sc = (2 * R) / cs * z, X = (x) => -R * z + ox + (x - cx0) * sc, Y = (y) => -R * z + oy + (y - cy0) * sc;
    ctx.imageSmoothingQuality = "high";
    const mono = e.tone === "mono" || e.tone === "ink" || e.tone === "neu";
    if (neu) {                                    // светлый неоморфизм (отзыв 18.10: «серо-грязно»): мягкий свет студии за
      // портретом — лицо светлее материала, без тени внутрь и без рамки; снизу портрет растворяется в выпуклом диске
      const lt = neuColors().light, sl = ctx.createRadialGradient(0, -R * 0.18, R * 0.05, 0, -R * 0.05, R * 1.02);
      sl.addColorStop(0, lt); sl.addColorStop(0.55, lt + "aa"); sl.addColorStop(1, lt + "00");
      ctx.fillStyle = sl; ctx.fillRect(-R, -R, 2 * R, 2 * R);
    } else if (mono) {                            // сдержанно: портрет на стекле — сквозь круг виден фон окна
      ctx.fillStyle = "rgba(255,255,255,.04)"; ctx.fillRect(-R, -R, 2 * R, 2 * R);
    } else {
      const bgr = ctx.createRadialGradient(0, -R * 0.2, R * 0.1, 0, 0, R);   // портрет на прозрачном фоне — подкладываем тёмный
      bgr.addColorStop(0, "#1c1c2a"); bgr.addColorStop(1, "#050508");
      ctx.fillStyle = bgr; ctx.fillRect(-R, -R, 2 * R, 2 * R);
    }
    ctx.drawImage(L.base, X(0), Y(0), L.base.naturalWidth * sc, L.base.naturalHeight * sc);
    if (now > A.blinkTill) {
      if (L.mask) {                               // зрачки — только внутри разреза глаз: веки прикрывают их сверху и снизу
        const W = L.base.naturalWidth, H = L.base.naturalHeight, f = 3;
        const oc = L._eyeCv || (L._eyeCv = document.createElement("canvas"));
        if (oc.width !== W * f) { oc.width = W * f; oc.height = H * f; }
        const o = oc.getContext("2d");
        o.globalCompositeOperation = "source-over"; o.clearRect(0, 0, oc.width, oc.height);
        G.eyes.forEach(([x, y], i) => o.drawImage(L.irises[i], (x + A.ex) * f, (y + A.ey) * f, G.iris * f, G.iris * f));
        o.globalCompositeOperation = "destination-in"; o.drawImage(L.mask, 0, 0, oc.width, oc.height);
        ctx.drawImage(oc, X(0), Y(0), W * sc, H * sc);
      } else {
        const s = G.iris * sc;
        G.eyes.forEach(([x, y], i) => ctx.drawImage(L.irises[i], X(x + A.ex), Y(y + A.ey), s, s));
      }
    }
    const [mx, my, mw, mh] = G.mouth, put = (im, a) => { if (a > 0.01) { ctx.globalAlpha = a; ctx.drawImage(im, X(mx), Y(my), mw * sc, mh * sc); } };
    if (talking) { put(L.mouths[A.mPrev], 1 - A.mBlend); put(L.mouths[A.mTarget], A.mBlend); }
    else { put(L.mouths[0], 1 - A.smile); put(L.smile, A.smile); }
    ctx.globalAlpha = 1;
    // нет связи — притушить ВЕСЬ портрет ровно одним слоем (раньше тускнело лицо, а губы и глаза, нарисованные поверх,
    // оставались яркими — выглядело жутковато). Микрофон выключен — не тушим: это и так видно по значку и подписи,
    // а тусклый виджет некрасив (отзыв 14.10: «микрофон часто выключаю, чтобы не слушала фон»)
    // светлый неоморфизм — не темним, а «уводим в материал»: тёмная пелена на светлом и делала облик серо-грязным
    if (e.state === "offline") { ctx.fillStyle = neu ? neuColors().glass + "8c" : "rgba(6,6,10,.45)"; ctx.fillRect(-R, -R, 2 * R, 2 * R); }
    const fade = ctx.createLinearGradient(0, R * 0.55, 0, R);   // низ портрета (обрез туловища) растворяется в фоне
    if (neu) {                                    // край без среза: плечи и низ мягко уходят в материал диска
      ctx.globalCompositeOperation = "destination-in";
      const m = ctx.createRadialGradient(0, -R * 0.12, R * 0.7, 0, -R * 0.12, R * 1.08);
      m.addColorStop(0, "rgba(0,0,0,1)"); m.addColorStop(1, "rgba(0,0,0,0)");
      ctx.fillStyle = m; ctx.fillRect(-R, -R, 2 * R, 2 * R);
      ctx.globalCompositeOperation = "source-over";
    }
    if (mono) {                                   // в прозрачность: внизу проступает фон окна, а не чёрное пятно
      fade.addColorStop(0, "rgba(0,0,0,0)"); fade.addColorStop(0.75, "rgba(0,0,0,.85)"); fade.addColorStop(1, "rgba(0,0,0,1)");
      ctx.globalCompositeOperation = "destination-out"; ctx.fillStyle = fade; ctx.fillRect(-R, R * 0.55, 2 * R, R * 0.45);
      ctx.globalCompositeOperation = "source-over";
    } else {
      fade.addColorStop(0, "rgba(5,5,8,0)"); fade.addColorStop(0.7, "rgba(5,5,8,0.85)"); fade.addColorStop(1, "rgba(5,5,8,1)");
      ctx.fillStyle = fade; ctx.fillRect(-R, R * 0.55, 2 * R, R * 0.45);
    }
    if (speaking || thinking) {                   // говорит/думает — лёгкий оттенок цвета персонажа
      ctx.globalCompositeOperation = "soft-light"; ctx.fillStyle = rgba(c, 0.12); ctx.fillRect(-R, -R, 2 * R, 2 * R);
      ctx.globalCompositeOperation = "source-over";
    }
    if (thinking) {                               // думает — бегущая полоса «скана»
      const band = ((t * 0.4) % 1) * 2.4 * R - 1.2 * R;
      const bg = ctx.createLinearGradient(0, band - 24, 0, band + 24);
      bg.addColorStop(0, rgba(c, 0)); bg.addColorStop(0.5, rgba(c, 0.18 * k)); bg.addColorStop(1, rgba(c, 0));
      ctx.fillStyle = bg; ctx.fillRect(-R, band - 24, 2 * R, 48);
    }
    ctx.restore();
    portraitRim(g, e, R);
  }

  // цвета неоморфной темы (skins.css: --neu-light, --glass) — читаем раз в секунду, а не каждый кадр
  let neuC = null, neuAt = 0;
  function neuColors() {
    const now = performance.now();
    if (!neuC || now - neuAt > 1000) {
      const cs = getComputedStyle(document.body), hx = (v, d) => (/^#[0-9a-f]{6}$/i.test(v.trim()) ? v.trim() : d);
      neuC = { light: hx(cs.getPropertyValue("--neu-light"), "#ffffff"), glass: hx(cs.getPropertyValue("--glass"), "#e4e9f0") }; neuAt = now;
    }
    return neuC;
  }

  /* Край портрета. Цветной (по умолчанию): кольцо цвета персонажа со свечением и пунктир. Сдержанный (tone "mono",
     виджет и телефон): портрет «утоплен» в стекло — внутренняя тень по краю и тонкий светлый край, как у фото на сайте;
     пока говорит — край чуть светлеет. */
  function portraitRim(g, e, R) {
    const { ctx, r, c, t, lv, k } = g;
    if (e.tone === "neu") return;                 // неоморфизм: ни тени внутрь, ни рамки — форму даёт сам материал
    if (e.tone === "ink") {                       // светлая тема: белая рамка и мягкая тень наружу, как у фото в Material
      const v = ctx.createRadialGradient(0, 0, R * 0.82, 0, 0, R);
      v.addColorStop(0, "rgba(0,0,0,0)"); v.addColorStop(1, "rgba(0,0,0,.22)");
      ctx.fillStyle = v; ctx.beginPath(); ctx.arc(0, 0, R, 0, TAU); ctx.fill();
      ctx.save(); ctx.shadowColor = "rgba(20,30,60,.22)"; ctx.shadowBlur = 14; ctx.shadowOffsetY = 3;
      ctx.lineWidth = 3; ctx.strokeStyle = "rgba(255,255,255,.95)";
      ctx.beginPath(); ctx.arc(0, 0, R + 1.5, 0, TAU); ctx.stroke(); ctx.restore();
      return;
    }
    if (e.tone === "mono") {
      // внутренняя тень у края, как inset 0 0 20px rgba(0,0,0,.5): мягко нарастает к кромке
      const v = ctx.createRadialGradient(0, 0, R * 0.8, 0, 0, R);
      v.addColorStop(0, "rgba(0,0,0,0)"); v.addColorStop(0.6, "rgba(0,0,0,.12)"); v.addColorStop(1, "rgba(0,0,0,.42)");
      ctx.fillStyle = v; ctx.beginPath(); ctx.arc(0, 0, R, 0, TAU); ctx.fill();
      const on = e.state === "speaking" ? lv : 0;
      ctx.lineWidth = 2; ctx.strokeStyle = `rgba(255,255,255,${(0.1 + on * 0.22).toFixed(3)})`;
      if (on) { ctx.shadowColor = "rgba(255,255,255,.35)"; ctx.shadowBlur = 4 + on * 12; }
      ctx.beginPath(); ctx.arc(0, 0, R + 1, 0, TAU); ctx.stroke(); ctx.shadowBlur = 0;
      return;
    }
    ctx.lineWidth = 2 + lv * 4; ctx.strokeStyle = rgba(c, (0.6 + lv * 0.4) * k);
    ctx.shadowColor = rgba(c, 1); ctx.shadowBlur = 12 + lv * 20;
    ctx.beginPath(); ctx.arc(0, 0, R + 2, 0, TAU); ctx.stroke(); ctx.shadowBlur = 0;
    ctx.save(); ctx.rotate(t * 0.6); ctx.setLineDash([3, 9]); ctx.lineWidth = 1; ctx.strokeStyle = rgba(c, 0.5 * k);
    ctx.beginPath(); ctx.arc(0, 0, r * 0.92, 0, TAU); ctx.stroke(); ctx.restore(); ctx.setLineDash([]);
  }

  /* «Лучи»: голос отзывается полосками вокруг портрета (как в первых версиях Dewiar). Уровня звука один, поэтому
     «спектр» складывается из медленных волн по кругу, а каждая полоска плавно догоняет свою длину. Слушает — короткие
     и тихие (откликаются на ваш голос), говорит — длинные. Один путь и одно свечение на кадр — дёшево. */
  function voiceBars(g, e) {
    const { ctx, r, c, t, lv } = g;
    const photoLike = e.style === "photo", R0 = photoLike ? r * 0.78 + r * 0.08 : r * 1.0;
    const N = 60, maxL = photoLike ? r * 0.2 : r * 0.14, speaking = e.state === "speaking";
    const B = e._bars && e._bars.length === N ? e._bars : (e._bars = new Array(N).fill(0));
    const amp = speaking ? lv : lv * 0.45;
    ctx.save(); ctx.lineCap = "round"; ctx.lineWidth = Math.max(2, r * 0.03);
    ctx.strokeStyle = rgba(c, speaking ? 0.85 : 0.5);
    if (speaking) { ctx.shadowColor = rgba(c, 0.6); ctx.shadowBlur = 8; }
    ctx.beginPath();
    for (let i = 0; i < N; i++) {
      const a = i / N * TAU - Math.PI / 2;
      const wave = Math.abs(Math.sin(i * 0.52 + t * 5.2) * 0.6 + Math.sin(i * 1.31 - t * 3.7) * 0.4 + Math.sin(i * 0.17 + t * 1.3) * 0.3);
      const want = 1.5 + maxL * amp * (0.2 + 0.8 * Math.min(1, wave));
      B[i] += (want - B[i]) * (want > B[i] ? 0.45 : 0.18);
      const x = Math.cos(a), y = Math.sin(a);
      ctx.moveTo(x * R0, y * R0); ctx.lineTo(x * (R0 + B[i]), y * (R0 + B[i]));
    }
    ctx.stroke(); ctx.restore();
  }

  /* «Пульс»: от портрета мягко расходятся три круга и светлое сияние — чем громче голос, тем шире и ярче. */
  function voicePulse(g, e) {
    const { ctx, r, c, t, lv } = g;
    const R0 = e.style === "photo" ? r * 0.8 : r * 1.0, span = r * 0.27, speaking = e.state === "speaking";
    const k = speaking ? 1 : 0.5;
    ctx.save();
    const gl = ctx.createRadialGradient(0, 0, R0, 0, 0, R0 + span);
    gl.addColorStop(0, rgba(c, (0.05 + 0.2 * lv) * k)); gl.addColorStop(1, rgba(c, 0));
    ctx.fillStyle = gl; ctx.beginPath(); ctx.arc(0, 0, R0 + span, 0, TAU); ctx.arc(0, 0, R0, 0, TAU, true); ctx.fill("evenodd");
    ctx.lineWidth = Math.max(1.5, r * 0.016);
    for (let i = 0; i < 3; i++) {
      const ph = (t * (speaking ? 0.5 : 0.3) + i / 3) % 1;
      ctx.strokeStyle = rgba(c, (1 - ph) * (0.2 + 0.6 * lv) * k);
      ctx.beginPath(); ctx.arc(0, 0, R0 + ph * span * (0.55 + 0.45 * lv), 0, TAU); ctx.stroke();
    }
    ctx.restore();
  }

  function photo(g, e) {                          // своё фото: голограмма
    const L = e.live ? liveSet(e.live) : null;
    if (L && L.ready) return liveFace(g, e, L);   // у персонажа есть живое лицо (Эва) — рисуем его
    const { ctx, r, c, t, lv, k } = g;
    const R = r * 0.78;
    ctx.save(); ctx.beginPath(); ctx.arc(0, 0, R, 0, TAU); ctx.clip();
    const busy = e.state === "speaking" || e.state === "thinking";
    if (e.img && e.img.complete && e.img.naturalWidth) {
      // чёткий портрет: заранее уменьшаем фото ступенями до нужного размера в пикселях экрана (кэш на размер)
      const dpr = window.devicePixelRatio || 1, px = Math.max(8, Math.round(2 * R * dpr));
      // анимация (GIF) — без кэша: кадр берётся каждый раз, иначе застыла бы на первом (письмо пользователя 23.10)
      const anim = /^data:image\/gif/.test(e.img.src);
      if (anim) {
        const iw = e.img.naturalWidth, ih = e.img.naturalHeight, sc = Math.max(px / iw, px / ih);
        e._ph = { px, src: e.img.src, canvas: e.img, w: iw * sc / px, h: ih * sc / px };
      } else if (!e._ph || e._ph.px !== px || e._ph.src !== e.img.src) {
        const iw = e.img.naturalWidth, ih = e.img.naturalHeight, sc = Math.max(px / iw, px / ih);
        let src = e.img, w = iw, h = ih;
        while (w / 2 >= iw * sc && w > 4) {             // ступени по половине, пока не дойдём до нужного размера
          const half = document.createElement("canvas"); half.width = Math.round(w / 2); half.height = Math.round(h / 2);
          const hc = half.getContext("2d"); hc.imageSmoothingQuality = "high"; hc.drawImage(src, 0, 0, half.width, half.height);
          src = half; w = half.width; h = half.height;
        }
        const out = document.createElement("canvas"); out.width = px; out.height = px;
        const oc = out.getContext("2d"); oc.imageSmoothingQuality = "high";
        oc.drawImage(src, (px - iw * sc) / 2, (px - ih * sc) / 2, iw * sc, ih * sc);
        e._ph = { px, src: e.img.src, canvas: out };
      }
      // «дрожание» фото, пока думает, убрано: выглядело как сбой (письмо пользователя 23.10)
      // фото всегда в полную яркость (без «пелены»); приглушаем только когда микрофон выключен или нет связи
      const sleeping = e.state === "offline";             // микрофон выключен — портрет в полную яркость
      ctx.globalAlpha = sleeping ? 0.6 : 1;
      ctx.imageSmoothingQuality = "high";
      const gk = e.lookGain, z = 1 + 0.035 * gk * e._la, ox = e._lx * R * 0.03 * gk, oy = e._ly * R * 0.025 * gk;   // своё фото: чуть крупнее (плавно) — край не виден
      if (anim) {
        const W = 2 * R * z * e._ph.w, H = 2 * R * z * e._ph.h;
        ctx.drawImage(e._ph.canvas, -W / 2 + ox, -H / 2 + oy, W, H);
      } else ctx.drawImage(e._ph.canvas, -R * z + ox, -R * z + oy, 2 * R * z, 2 * R * z);
      ctx.globalAlpha = 1;
      if (busy) {                                 // говорит/думает — лёгкий оттенок цвета персонажа
        ctx.globalCompositeOperation = "soft-light"; ctx.fillStyle = rgba(c, 0.14); ctx.fillRect(-R, -R, 2 * R, 2 * R);
        ctx.globalCompositeOperation = "source-over";
      }
    } else {
      ctx.fillStyle = rgba(c, 0.15); ctx.fillRect(-R, -R, 2 * R, 2 * R);
    }
    if (busy) {                                   // «голограмма» — только пока говорит или думает; в покое — чистое фото
      ctx.fillStyle = "rgba(0,0,0,0.08)";
      const off = (t * 20) % 4;
      for (let y = -R + off; y < R; y += 4) ctx.fillRect(-R, y, 2 * R, 1);
    }
    if (busy || !(e.img && e.img.complete)) {    // бегущая полоса «скана» — в работе или пока фото не загрузилось
      const band = ((t * 0.4) % 1) * 2.4 * R - 1.2 * R;
      const bg = ctx.createLinearGradient(0, band - 24, 0, band + 24);
      bg.addColorStop(0, rgba(c, 0)); bg.addColorStop(0.5, rgba(c, 0.2 * k)); bg.addColorStop(1, rgba(c, 0));
      ctx.fillStyle = bg; ctx.fillRect(-R, band - 24, 2 * R, 48);
    }
    ctx.restore();
    portraitRim(g, e, R);
  }

  // Пластинка: пока играет радио и ассистент молчит — вращается винил, на «яблоке» — цвет персонажа и название станции.
  function vinyl(g, e) {
    const { ctx, r, c } = g;
    const R = r * 1.08, now = performance.now() / 1000;
    const ang = (e._vang = ((e._vang || 0) + (e._dt || 0.016) * 1.9) % TAU);           // ≈ 18 об/мин — видно, что крутится
    ctx.save();
    ctx.shadowColor = "rgba(0,0,0,.6)"; ctx.shadowBlur = 18; ctx.shadowOffsetY = 4;
    const body = ctx.createRadialGradient(0, 0, R * 0.3, 0, 0, R);
    body.addColorStop(0, "#1b1b1f"); body.addColorStop(0.7, "#0e0e11"); body.addColorStop(1, "#050506");
    ctx.fillStyle = body; ctx.beginPath(); ctx.arc(0, 0, R, 0, TAU); ctx.fill();
    ctx.restore();
    ctx.save(); ctx.rotate(ang);
    for (let i = 0; i < 34; i++) {                      // дорожки
      const rr = R * (0.4 + i * 0.0168);
      ctx.strokeStyle = `rgba(255,255,255,${i % 5 === 0 ? 0.075 : 0.035})`; ctx.lineWidth = i % 5 === 0 ? 1.1 : 0.7;
      ctx.beginPath(); ctx.arc(0, 0, rr, 0, TAU); ctx.stroke();
    }
    ctx.strokeStyle = "rgba(255,255,255,.12)"; ctx.lineWidth = 1; ctx.beginPath(); ctx.arc(0, 0, R - 1, 0, TAU); ctx.stroke();
    // «яблоко» — вращается вместе с пластинкой
    const L = R * 0.34;
    const lab = ctx.createRadialGradient(-L * 0.3, -L * 0.3, L * 0.1, 0, 0, L);
    lab.addColorStop(0, rgba(mix(c, [255, 255, 255], 0.35), 1)); lab.addColorStop(1, rgba(c, 1));
    ctx.fillStyle = lab; ctx.beginPath(); ctx.arc(0, 0, L, 0, TAU); ctx.fill();
    ctx.strokeStyle = "rgba(0,0,0,.25)"; ctx.lineWidth = 1; ctx.beginPath(); ctx.arc(0, 0, L * 0.82, 0, TAU); ctx.stroke();
    const name = (e.vinyl || "").toUpperCase().slice(0, 22);
    if (name) {                                          // название станции по кругу
      ctx.fillStyle = "rgba(20,14,30,.85)"; ctx.font = `700 ${Math.max(7, L * 0.2)}px Manrope, sans-serif`;
      ctx.textAlign = "center"; ctx.textBaseline = "middle";
      const span = Math.min(TAU * 0.85, name.length * 0.26);
      for (let i = 0; i < name.length; i++) {
        const a = -Math.PI / 2 - span / 2 + (i + 0.5) * span / name.length;
        ctx.save(); ctx.rotate(a + Math.PI / 2); ctx.fillText(name[i], 0, -L * 0.6); ctx.restore();
      }
    }
    ctx.fillStyle = "#0b0b0e"; ctx.beginPath(); ctx.arc(0, 0, Math.max(2.5, R * 0.025), 0, TAU); ctx.fill();
    ctx.restore();
    // блик — неподвижный (свет падает сверху), поэтому кажется, что крутится сама пластинка
    ctx.save(); ctx.beginPath(); ctx.arc(0, 0, R, 0, TAU); ctx.arc(0, 0, L, 0, TAU, true); ctx.clip("evenodd");
    for (const [a0, w] of [[-0.95, 0.5], [2.2, 0.42]]) {
      const gx = Math.cos(a0) * R * 0.7, gy = Math.sin(a0) * R * 0.7;
      const gl = ctx.createRadialGradient(gx, gy, 0, gx, gy, R * w * 1.4);
      gl.addColorStop(0, `rgba(255,255,255,${0.10 + 0.03 * Math.sin(now * 2)})`); gl.addColorStop(1, "rgba(255,255,255,0)");
      ctx.fillStyle = gl; ctx.fillRect(-R, -R, 2 * R, 2 * R);
    }
    ctx.restore();
  }

  // Стили, чьё свечение складывается («lighter»); так рисуем только поверх непрозрачного диска (см. draw).
  const LIGHTER = new Set(["nexus", "holobrain", "orbital", "tactical", "rings", "strings", "particles", "lattice", "brandmark"]);
  const STYLES = { nexus, aura, holobrain, brain, brandmark, lattice, orbital, tactical, rings, strings, particles, photo };
  const VINYL_STATES = new Set(["idle", "muted"]);    // ассистент молчит — видна пластинка

  // кольцо состояния вокруг любой сущности
  function stateRing(g, e) {
    const { ctx, r, c, t, lv } = g;
    const R = r * 1.08;
    if (e.state === "speaking" || e.state === "listening") {
      if (e.fx === "bars") return voiceBars(g, e);
      if (e.fx === "pulse") return voicePulse(g, e);
    }
    if (e.state === "listening") {
      ctx.lineWidth = 2; ctx.strokeStyle = rgba(c, 0.35 + lv * 0.6);
      ctx.beginPath(); ctx.arc(0, 0, R + lv * 6, 0, TAU); ctx.stroke();
    } else if (e.state === "thinking") {
      ctx.lineWidth = 2.5;
      for (let i = 0; i < 3; i++) {
        const a = t * 3 + i * TAU / 3;
        ctx.strokeStyle = rgba(c, 0.8); ctx.beginPath(); ctx.arc(0, 0, R, a, a + 0.6); ctx.stroke();
      }
    } else if (e.state === "speaking") {
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      for (let i = 0; i <= 120; i++) {
        const a = i / 120 * TAU;
        const w = Math.sin(a * 8 + t * 7) * lv * 7 + Math.sin(a * 13 - t * 5) * lv * 4;
        ctx[i ? "lineTo" : "moveTo"](Math.cos(a) * (R + w), Math.sin(a) * (R + w));
      }
      ctx.strokeStyle = rgba(c, 0.75); ctx.stroke();
    } else if (e.state === "offline") {
      ctx.setLineDash([4, 6]); ctx.lineWidth = 1; ctx.strokeStyle = rgba(c, 0.5);
      ctx.beginPath(); ctx.arc(0, 0, R, 0, TAU); ctx.stroke(); ctx.setLineDash([]);
    }
  }

  class Entity {
    constructor(canvas, opts = {}) {
      this.canvas = canvas; this.ctx = canvas.getContext("2d");
      this.state = "idle"; this.level = 0; this.target = 0; this.t = Math.random() * 10;
      this.ring = opts.ring !== false;
      this.live = opts.live || "";
      this.plate = opts.plate !== false;
      this.still = !!opts.still;          // в покое — один кадр, без анимации (много обликов на одной странице студии)
      this.tone = opts.tone || "color";   // "mono" — сдержанно: белый край портрета и белые лучи вместо цвета персонажа
      this.fx = opts.fx || "wave";        // голос: "wave" — волна по кругу, "bars" — лучи вокруг портрета, "pulse" — расходящиеся круги
      this.voiceLevels = !!opts.voiceLevels;   // уровни своего голоса придут (виджет компьютера) — без них рот и волна молчат
      this.lookX = 0; this.lookY = 0; this._lx = 0; this._ly = 0; this._looking = false; this._la = 0;   // где зритель (look)
      this.lookGain = opts.lookGain || 1;   // сила эффекта: телефон — 1, виджет компьютера — 0.5 (крупный портрет, отзыв 14.10)
      this.configure(opts);
      this._last = performance.now(); this._frame = 0; this._calm = performance.now();
      /* Нагрузка в простое (отзыв 23.10: «в простое жрёт 20–40% процессора и 10–25% видеокарты»): кадр нужен не чаще,
         чем позволяет draw (minDt). Ждать дольше ~50 мс — таймером, а не 60 пробуждениями в секунду; set/look/configure
         будят сразу (_wake), так что на имя и голос облик откликается без задержки. */
      const loop = (now) => {
        if (this.dead) return;
        let wait = this.draw(now);
        if (wait === undefined) wait = this._mdt || 0;    // нарисовали — следующий кадр не раньше minDt
        if (wait > 50) this._sleep = setTimeout(() => { this._sleep = 0; requestAnimationFrame(loop); }, wait - 8);
        else requestAnimationFrame(loop);
      };
      this._loop = loop;
      requestAnimationFrame(loop);
    }
    _wake() {                                   // что-то изменилось — снова живой темп и кадр сразу
      this._calm = performance.now();
      if (this._sleep) { clearTimeout(this._sleep); this._sleep = 0; requestAnimationFrame(this._loop); }
    }
    configure({ style, color, image, live } = {}) {
      this._stillAt = performance.now() + 1500;
      if (this._loop) this._wake();             // после смены облика — дорисовать (фото и лица грузятся не сразу)
      if (live !== undefined) { this.live = live || ""; this._live = null; }   // живое лицо (слои из папки live)
      if (style) this.style = STYLES[style] ? style : "nexus";
      if (color) this.color = rgb(color);
      if (image !== undefined) {
        this.img = null;
        if (image) { this.img = new Image(); this.img.src = image; }
      }
    }
    /* Как узнать, что звук голоса идёт прямо сейчас (а не только состояние «speaking» — его ставят, ещё не получив звук):
       voice — уровень своего голоса (компьютер шлёт его, пока играет плеер): звучит, если уровень свежий (до 400 мс);
       audible — телефон сообщает начало и конец каждой фразы; opts.voiceLevels — уровни голоса придут точно (виджет
       компьютера): до первого из них — тишина. Ничего этого нет (облик в студии) — звучит всё время «speaking». */
    set({ state, level, voice, audible } = {}) {
      if (state && state !== this.state) { this._stillAt = performance.now() + 1200; this._wake(); }   // плавно вернуться в покой и замереть
      if (state) this.state = state;
      if (level !== undefined) this.target = level;
      if (voice && level !== undefined) { this._voiceAt = performance.now(); if (level > 0.02) this._voiceSeen = true; }
      if (audible !== undefined) { this._audibleKnown = true; this._audible = !!audible; }
    }
    /* Где зритель относительно портрета: x, y от −1 до 1 (x > 0 — справа, y > 0 — снизу). Телефон — по наклону
       (app.js tiltLook), виджет компьютера — по курсору. Портрет чуть сдвигается в глубину к зрителю, живое лицо
       переводит на него глаза; повернуть сам диск — дело страницы (CSS). look(null) — выключить. */
    look(x, y) {
      if (x === null || x === undefined) { this._looking = false; this.lookX = this.lookY = 0; return; }
      const cl = (v) => Math.max(-1, Math.min(1, +v || 0));
      this._looking = true; this.lookX = cl(x); this.lookY = cl(y); this._wake();
      this._stillAt = Math.max(this._stillAt || 0, performance.now() + 600);
    }
    sounding(now = performance.now()) {
      if (this._voiceSeen) return now - (this._voiceAt || 0) < 400;
      if (this._audibleKnown) return this._audible;
      return !this.voiceLevels;
    }
    draw(now) {
      if (this.paused) return 400;                           // окно спрятано — не рисуем (и проверяем редко)
      if (this.still && this.state === "idle" && now > this._stillAt) return 400;   // неподвижный кадр уже нарисован
      const cv = this.canvas, dpr = window.devicePixelRatio || 1;
      const w = cv.clientWidth, h = cv.clientHeight;
      if (!w || !h) return;
      const st = STATE[this.state] || STATE.idle;
      // экономим CPU: в покое (и под пластинку) ~25 кадров/с, без микрофона или связи ~8, в работе до ~70
      let minDt = this.vinyl && (this.state === "idle" || this.state === "muted") ? 40 :
        this.state === "offline" ? 120 : this.state === "idle" || this.state === "muted" ? 40 : 14;
      // слабый компьютер (или WebKit без ускорения): кадр рисуется долго — рисуем реже, чтобы кнопки не «залипали»
      if (this._cost > 6) minDt = Math.max(minDt, Math.min(120, this._cost * 6));
      if (this.calm) minDt = Math.max(minDt, this.state === "idle" ? 160 : 60);   // созвон: облик почти неподвижен, не мешаем
      if (this.lite) minDt = Math.max(minDt, 50);         // лёгкий режим телефона: не чаще ~20 кадров/с и в разговоре
      // глубокий покой: 20 с ничего не происходит (ни голоса, ни взгляда, ни пластинки) — облик дышит ~6 кадров/с, как
      // при созвоне (calm): движение медленное, глазу почти не заметно, а окну на рабочем столе — в 4 раза меньше работы
      const spinning = this.vinyl && VINYL_STATES.has(this.state);
      if ((this.state === "idle" || this.state === "muted" || this.state === "offline") && !spinning && !this._looking && this.target < 0.05 && now - this._calm > 20000)
        minDt = Math.max(minDt, 160);
      // допуск 8 мс: кадр экрана приходит не точно к сроку — без него лишнее пробуждение на каждый рисунок
      this._mdt = minDt;
      if (now - this._last < minDt - 8) return minDt - (now - this._last);
      const t0 = performance.now();
      const dt = Math.min(0.1, (now - this._last) / 1000); this._last = now;
      if (cv.width !== Math.round(w * dpr) || cv.height !== Math.round(h * dpr)) { cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr); }
      this.level += (this.target - this.level) * (this.target > this.level ? 0.5 : 0.12);
      const le = Math.min(1, dt * 5);                         // взгляд и сдвиг к зрителю — плавно
      this._lx += (this.lookX - this._lx) * le; this._ly += (this.lookY - this._ly) * le;
      this._la += ((this._looking ? 1 : 0) - this._la) * Math.min(1, dt * 1.5);   // увеличение для сдвига — появляется и уходит плавно (без рывка)
      this.t += dt * st.speed * (reduced ? 0.3 : 1);
      const ctx = this.ctx;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);
      ctx.translate(w / 2, h / 2);
      const c = st.sat ? this.color : mix(this.color, [150, 160, 175], 0.85);
      const PR = Math.min(w, h) / 2 - 1.5;                    // радиус диска-подложки
      // говорит — живая волна всегда (уровень звука бывает тихим или не приходит вовсе, а облик не должен «застывать»);
      // слушает — лёгкое дыхание. Так в виджете анимация такая же, как в студии при наведении на персонажа.
      // ответ готов, а звук ещё не пришёл (голос с сервера) или пауза между фразами — спокойное дыхание, как у «слушает»
      const sounding = this.state !== "speaking" || this.sounding(now);
      const lvE = this.state === "speaking" && !sounding ? Math.max(this.level * 0.5, 0.1 + 0.05 * Math.sin(this.t * 1.7)) :
        this.state === "speaking" ? Math.max(this.level, 0.3 + 0.1 * Math.sin(this.t * 2.3) + 0.05 * Math.sin(this.t * 5.1)) :
        this.state === "listening" ? Math.max(this.level, 0.08 + 0.05 * Math.sin(this.t * 1.7)) : this.level;
      const g = { ctx, r: PR * 0.8, c, t: this.t, lv: lvE, k: st.glow };
      // сдержанный тон: портрет, его край и лучи — холодный белый; абстрактные облики сохраняют цвет персонажа
      const gm = this.tone === "mono" || this.tone === "ink" || this.tone === "neu"
        ? Object.assign({}, g, { c: this.tone !== "mono" ? (st.sat ? [52, 58, 82] : [120, 126, 140]) : st.sat ? [226, 232, 244] : [150, 156, 168] }) : g;
      // Непрозрачный тёмный диск. Всё свечение рисуется ПО НЕМУ, а не по прозрачному окну:
      // иначе на рабочем столе с аппаратным ускорением свечение «пересвечивается» пятнами.
      // сдержанный портрет — без диска-подложки: портрет «на стекле», как в окне вокруг
      const plate = this.plate && this.style !== "aura" && !((this.tone === "mono" || this.tone === "ink" || this.tone === "neu") && this.style === "photo"), ringOn = this.ring && this.style !== "aura";
      this._dt = dt;
      if (plate) {
        const pg = ctx.createRadialGradient(0, -PR * 0.25, PR * 0.1, 0, 0, PR);
        if (this.tone === "mono" || this.tone === "ink" || this.tone === "neu") { pg.addColorStop(0, "#1f2029"); pg.addColorStop(0.75, "#14141b"); pg.addColorStop(1, "#0c0c11"); }
        else { pg.addColorStop(0, "#26264A"); pg.addColorStop(0.75, "#17172E"); pg.addColorStop(1, "#0D0D1A"); }
        ctx.fillStyle = pg; ctx.beginPath(); ctx.arc(0, 0, PR, 0, TAU); ctx.fill();
        ctx.save(); ctx.beginPath(); ctx.arc(0, 0, PR - 0.5, 0, TAU); ctx.clip();
      }
      const spin = this.vinyl && VINYL_STATES.has(this.state);
      ctx.globalCompositeOperation = plate && LIGHTER.has(this.style) && !spin ? "lighter" : "source-over";
      (spin ? vinyl : STYLES[this.style])(spin ? Object.assign({}, g, { c: this.color }) : this.style === "photo" ? gm : g, this);
      ctx.globalCompositeOperation = "source-over";
      if (ringOn && !spin) stateRing(gm, this);
      if (plate) {
        ctx.restore();                                   // без обводки диска — органичнее
      }
      this._cost = (this._cost || 0) * 0.9 + (performance.now() - t0) * 0.1;
    }
    destroy() { this.dead = true; }
  }

  window.DewiarEntity = Entity;
  window.DewiarStyles = Object.keys(STYLES);
})();
