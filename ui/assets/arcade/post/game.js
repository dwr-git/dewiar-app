/* «Колючая почта» — акварель и бумажная аппликация (по утверждённому концепту: слои акварельных заливок с рваным краем,
   multiply, зерно бумаги; жители и дома — фигурки из бумаги с мягкой тенью).
   Ёжик-почтальон разносит письма жителям круглой деревни. Адреса нет — на марке нарисован тот, кому письмо.
   Четыре дня, марки всё хитрее: портрет → силуэт → примета (шапка, хвост, очки) → загадка (любимая вещь).
   Солнце клонится — мягкий таймер: на закате день кончается, письма не теряются насовсем, просто не идут в зачёт.
   Ошибка — смешная реакция жителя («это не мне!»), верно — благодарность и подарок.
   Управление: щелчок/касание по дому — ёжик идёт по тропинке и вручает; письмо можно смахнуть к дому пальцем;
   стрелки — выбрать дом, Enter — вручить; «?» — подсказка.
   Рисование: фон (небо и земля с домами) — один раз в свои холсты по масштабу экрана; жители, ёжик, письмо, таблички —
   заготовки-спрайты; каждый кадр — только перемещения. */
(() => {
'use strict';
const A = Arcade, SND = A.sound;
const LAND = (() => { try { return innerWidth > (innerHeight - 110) * 1.15; } catch (e) { return false; } })();
const W = LAND ? 1280 : 720, H = LAND ? 720 : 1280, TAU = Math.PI * 2, PI = Math.PI;
const Q = new URLSearchParams(location.search), COVER = Q.has('cover'), DBG = Q.has('dbg');
const clamp = (v, a, b) => (v < a ? a : v > b ? b : v), lerp = (a, b, t) => a + (b - a) * t;
const eOut = (t) => 1 - (1 - t) ** 3, eIO = (t) => (t < .5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2);
const eBack = (t) => { const c1 = 1.70158, c3 = c1 + 1; return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2; };
const LINE = '#5a3f35', MUTE = '#8a7264', PAPER = '#f7f0e2', CARDC = '#fffaf0', SHC = 'rgba(70,45,30,.28)';
const F = A.FONT;

/* ---------------- случайность (сеяная — чтобы заготовки рисовались одинаково) ---------------- */
let seed = 21;
const rnd = () => { seed = (seed + 0x6D2B79F5) | 0; let t = Math.imul(seed ^ (seed >>> 15), 1 | seed); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
const reseed = (s) => { let h = 2166136261; for (const ch of String(s)) h = Math.imul(h ^ ch.charCodeAt(0), 16777619); seed = h | 0; };
const gauss = () => { let u = 0, v = 0; while (!u) u = rnd(); while (!v) v = rnd(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(TAU * v); };
const shuffle = (a) => { for (let i = a.length - 1; i > 0; i--) { const j = (Math.random() * (i + 1)) | 0; [a[i], a[j]] = [a[j], a[i]]; } return a; };

/* ---------------- акварель и бумага ---------------- */
function deform(pts, depth, vr) {
  let p = pts;
  for (let d = 0; d < depth; d++) {
    const q = [];
    for (let i = 0; i < p.length; i++) {
      const a = p[i], b = p[(i + 1) % p.length], mx = (a[0] + b[0]) / 2, my = (a[1] + b[1]) / 2, len = Math.hypot(b[0] - a[0], b[1] - a[1]);
      const nx = -(b[1] - a[1]) / (len || 1), ny = (b[0] - a[0]) / (len || 1), k = gauss() * vr * len * (a[2] || 1);
      q.push(a, [mx + nx * k, my + ny * k, ((a[2] || 1) + (b[2] || 1)) / 2 * (.7 + rnd() * .6)]);
    }
    p = q; vr *= .82;
  }
  return p;
}
function polyPath(p) { const P = new Path2D(); P.moveTo(p[0][0], p[0][1]); for (let i = 1; i < p.length; i++) P.lineTo(p[i][0], p[i][1]); P.closePath(); return P; }
function subdiv(poly, m = 36) {
  const out = [];
  for (let i = 0; i < poly.length; i++) { const a = poly[i], b = poly[(i + 1) % poly.length], n = Math.max(1, Math.ceil(Math.hypot(b[0] - a[0], b[1] - a[1]) / m)); for (let k = 0; k < n; k++) out.push([a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n, 1]); }
  return out;
}
function wash(c, poly, col, o = {}) {           // заливка: много полупрозрачных слоёв с рваным краем, multiply
  const layers = o.layers || 14, al = o.alpha || .055, base = deform(subdiv(poly, o.m || 36), 1, o.v0 ?? .3);
  c.save(); c.globalCompositeOperation = o.op || 'multiply'; c.fillStyle = col; c.strokeStyle = col; c.lineWidth = 1.2;
  for (let i = 0; i < layers; i++) { const p = polyPath(deform(base, 2, o.v || .32)); c.globalAlpha = al; c.fill(p); if (i % 6 === 0) { c.globalAlpha = al * 1.4; c.stroke(p); } }
  c.restore();
}
function lift(c, poly, o = {}) {                // «снять» краску — светлое пятно бумаги
  const base = deform(subdiv(poly, o.m || 24), 1, .2);
  c.save(); c.fillStyle = o.col || '#fbf6ec'; for (let i = 0; i < (o.n || 8); i++) { c.globalAlpha = o.a || .14; c.fill(polyPath(deform(base, 2, .25))); } c.restore();
}
const ellP = (cx, cy, rx, ry, n = 18) => Array.from({ length: n }, (_, i) => [cx + Math.cos(i / n * TAU) * rx, cy + Math.sin(i / n * TAU) * ry]);
const E = (cx, cy, rx, ry, a = 0) => { const p = new Path2D(); p.ellipse(cx, cy, Math.max(.1, rx), Math.max(.1, ry), a, 0, TAU); return p; };
const sk = (c) => { const m = c.getTransform(); return Math.hypot(m.a, m.b); };
function cut(c, path, col, o = {}) {            // бумажная фигурка: заливка с мягкой тенью, пятна краски внутри
  const k = sk(c);
  c.save();
  if (o.shadow !== false) { c.shadowColor = o.shc || SHC; c.shadowBlur = (o.blur ?? 7) * k; c.shadowOffsetX = (o.sx ?? 2) * k; c.shadowOffsetY = (o.sy ?? 4) * k; }
  c.fillStyle = col; c.fill(path); c.restore();
  if (o.stain) {
    c.save(); c.clip(path); const b = o.box;
    for (let i = 0; i < (o.n || 3); i++) { const cx = b[0] + rnd() * b[2], cy = b[1] + rnd() * b[3]; wash(c, ellP(cx, cy, b[2] * (.2 + rnd() * .25), b[3] * (.2 + rnd() * .25), 10), o.stain, { layers: 8, alpha: .07 }); }
    c.restore();
  }
  if (o.edge !== false) { c.save(); c.clip(path); c.strokeStyle = 'rgba(255,255,255,.28)'; c.lineWidth = 2.5; c.stroke(path); c.restore(); }
}
function pen(c, f, w = 2, col = LINE) { c.save(); c.strokeStyle = col; c.lineWidth = w; c.lineCap = 'round'; c.lineJoin = 'round'; c.beginPath(); f(c); c.stroke(); c.restore(); }
function dot(c, x, y, r, col) { c.fillStyle = col; c.beginPath(); c.arc(x, y, r, 0, TAU); c.fill(); }
function rrp(x, y, w, h, r) { const p = new Path2D(); r = Math.min(r, w / 2, h / 2); p.moveTo(x + r, y); p.arcTo(x + w, y, x + w, y + h, r); p.arcTo(x + w, y + h, x, y + h, r); p.arcTo(x, y + h, x, y, r); p.arcTo(x, y, x + w, y, r); p.closePath(); return p; }
function torn(x, y, w, h, j = 1.6) {            // полоска бумаги с рваными краями сверху и снизу
  const p = new Path2D(); p.moveTo(x, y + 2);
  for (let X = x; X <= x + w; X += 8) p.lineTo(X, y + Math.sin(X * 1.07) * j + Math.sin(X * .31) * j * .6);
  p.lineTo(x + w + 1, y + h);
  for (let X = x + w; X >= x; X -= 8) p.lineTo(X, y + h + Math.sin(X * 1.31) * j + Math.sin(X * .23) * j * .6);
  p.closePath(); return p;
}
const blush = (c, x, y, r) => wash(c, ellP(x, y, r, r * .6, 8), '#ee8f8f', { layers: 8, alpha: .12 });

/* ---------------- заготовки (спрайты) по масштабу экрана ---------------- */
let CS = 0, FONTS = false;
const CACHE = new Map();
function spr(key, box, s, fn) {
  const k = key + '@' + s.toFixed(3);
  let cv = CACHE.get(k);
  if (cv) return cv;
  cv = document.createElement('canvas'); const d = s * CS, [x0, y0, x1, y1] = box;
  cv.width = Math.max(1, Math.ceil((x1 - x0) * d)); cv.height = Math.max(1, Math.ceil((y1 - y0) * d));
  const x = cv.getContext('2d'); x.scale(d, d); x.translate(-x0, -y0);
  reseed(key); fn(x);
  cv._x = x0 * s; cv._y = y0 * s; cv._w = (x1 - x0) * s; cv._h = (y1 - y0) * s;
  CACHE.set(k, cv); return cv;
}
function put(c, cv, x = 0, y = 0) { c.drawImage(cv, x + cv._x, y + cv._y, cv._w, cv._h); }
const MEAS = document.createElement('canvas').getContext('2d');
function wrap(text, size, maxW, weight = 600) {
  MEAS.font = weight + ' ' + size + 'px ' + F; const out = []; let line = '';
  for (const w of text.split(' ')) { const t = line ? line + ' ' + w : w; if (MEAS.measureText(t).width > maxW && line) { out.push(line); line = w; } else line = t; }
  out.push(line); return out;
}
const tw = (t, size, weight = 600) => { MEAS.font = weight + ' ' + size + 'px ' + F; return MEAS.measureText(t).width; };
function txt(c, s, x, y, size, col = LINE, weight = 700, align = 'left', base = 'alphabetic') {
  c.font = weight + ' ' + size + 'px ' + F; c.textAlign = align; c.textBaseline = base; c.fillStyle = col; c.fillText(s, x, y);
}

/* ---------------- глаза и рты ---------------- */
function eye(c, x, y, r, o) {
  const e = o.eyes;
  if (e === 'blink' || e === 'sleep') pen(c, (q) => { q.moveTo(x - r * 1.2, y - r * .2); q.quadraticCurveTo(x, y + r, x + r * 1.2, y - r * .2); }, Math.max(1.3, r * .55));
  else if (e === 'happy') pen(c, (q) => { q.moveTo(x - r * 1.2, y + r * .5); q.quadraticCurveTo(x, y - r * 1.2, x + r * 1.2, y + r * .5); }, Math.max(1.3, r * .55));
  else {
    const rr = e === 'wide' ? r * 1.3 : r;
    if (e === 'wide') dot(c, x, y, rr * 1.45, '#fffaf0');
    c.fillStyle = '#3e2b26'; c.beginPath(); c.ellipse(x, y, rr * .85, rr, 0, 0, TAU); c.fill(); dot(c, x + rr * .3, y - rr * .38, rr * .34, '#fff');
  }
}
function mouth(c, x, y, w, o) {
  if (o.mood === 'happy') { const p = new Path2D(); p.moveTo(x - w, y - w * .2); p.quadraticCurveTo(x, y + w * 1.4, x + w, y - w * .2); p.closePath(); c.fillStyle = '#7a3f3a'; c.fill(p); c.save(); c.clip(p); dot(c, x, y + w * .8, w * .55, '#e8838a'); c.restore(); }
  else if (o.mood === 'no') { c.fillStyle = '#7a3f3a'; c.beginPath(); c.ellipse(x, y + w * .3, w * .38, w * .5, 0, 0, TAU); c.fill(); }
  else pen(c, (q) => { q.moveTo(x - w * .7, y); q.quadraticCurveTo(x, y + w * .7, x + w * .7, y); }, Math.max(1.2, w * .28));
}

/* ================= жители (фигурка во весь рост: ноги в (0,0), смотрит вправо) ================= */
const FIG = {
  mouse(c, o) {
    pen(c, (q) => { q.moveTo(-14, -10); q.bezierCurveTo(-50, -6, -62, -36, -46, -50); q.bezierCurveTo(-36, -60, -24, -50, -32, -42); }, 3.4, '#c4959c');
    cut(c, E(-9, -3, 9, 5), '#a898a6', { blur: 2, sy: 1 }); cut(c, E(13, -3, 9, 5), '#a898a6', { blur: 2, sy: 1 });
    cut(c, E(0, -28, 22, 27), '#c9bcc3', { stain: '#a898a6', box: [-22, -55, 44, 55], n: 2 });
    cut(c, E(6, -22, 12, 16), '#ece4e8', { shadow: false });
    cut(c, E(-8, -82, 15, 15), '#b8aab2', { blur: 3, sy: 2 }); cut(c, E(-8, -82, 9, 9), '#f0b3b4', { shadow: false });
    cut(c, E(23, -81, 14, 14), '#b8aab2', { blur: 3, sy: 2 }); cut(c, E(23, -81, 8.5, 8.5), '#f0b3b4', { shadow: false });
    cut(c, E(9, -58, 20, 18), '#c9bcc3', { blur: 4, sy: 2 });
    cut(c, E(24, -53, 10, 8), '#d8ced3', { shadow: false });
    eye(c, 5, -61, 2.8, o); eye(c, 17, -62, 2.8, o);
    dot(c, 33, -54, 3.4, '#e8838a');
    pen(c, (q) => { q.moveTo(30, -50); q.lineTo(45, -46); q.moveTo(30, -52); q.lineTo(46, -54); }, 1, 'rgba(90,63,53,.55)');
    mouth(c, 25, -46, 5, o); blush(c, 10, -50, 5);
    cut(c, E(17, -30, 6, 5), '#b8aab2', { blur: 2, sy: 1 });
  },
  snail(c, o) {
    { const p = new Path2D(); p.moveTo(-60, 0); p.bezierCurveTo(-60, -14, -20, -16, 20, -14); p.bezierCurveTo(30, -40, 34, -56, 40, -60); p.bezierCurveTo(56, -62, 62, -40, 52, -14); p.bezierCurveTo(56, -6, 50, 0, 40, 0); p.closePath(); cut(c, p, '#e9dc9a', { stain: '#c9b86a', box: [-60, -62, 120, 62], n: 2 }); }
    cut(c, E(-16, -40, 36, 34), '#f0a98a', { stain: '#d97b66', box: [-52, -74, 72, 68], n: 3 });
    pen(c, (q) => { let a = 0; q.moveTo(-16, -40); for (let i = 0; i < 60; i++) { a += .22; const r = a * 2.6; q.lineTo(-16 + Math.cos(a) * r, -40 + Math.sin(a) * r); } }, 2.4, '#b85a4c');
    pen(c, (q) => { q.moveTo(40, -58); q.lineTo(34, -82); q.moveTo(50, -58); q.lineTo(58, -80); }, 2.4);
    dot(c, 34, -84, 4.2, LINE); dot(c, 58, -82, 4.2, LINE);
    eye(c, 42, -42, 2.5, o); eye(c, 52, -42, 2.5, o);
    mouth(c, 47, -32, 5, o); blush(c, 38, -34, 5);
  },
  owl(c, o) {
    cut(c, E(-12, -3, 8, 4), '#e8a54a', { blur: 2, sy: 1 }); cut(c, E(12, -3, 8, 4), '#e8a54a', { blur: 2, sy: 1 });
    cut(c, E(0, -52, 46, 52), '#9a8aa8', { stain: '#6f5f80', box: [-46, -104, 92, 104], n: 3, blur: 8 });
    cut(c, E(0, -36, 28, 30), '#e7dcea', { shadow: false });
    for (let i = 0; i < 3; i++) pen(c, (q) => { q.moveTo(-10 + i * 10, -42 + (i % 2) * 6); q.quadraticCurveTo(-6 + i * 10, -38 + (i % 2) * 6, -2 + i * 10, -42 + (i % 2) * 6); }, 1.4, '#9a8aa8');
    { const p = new Path2D(); p.moveTo(-40, -82); p.lineTo(-36, -114); p.lineTo(-18, -96); p.closePath(); p.moveTo(40, -82); p.lineTo(36, -114); p.lineTo(18, -96); p.closePath(); cut(c, p, '#9a8aa8', { blur: 3 }); }
    cut(c, E(-17, -70, 16, 16), '#f6e3a8', { blur: 2, sy: 1 }); cut(c, E(17, -70, 16, 16), '#f6e3a8', { blur: 2, sy: 1 });
    if (o.eyes === 'sleep' || o.eyes === 'blink') pen(c, (q) => { q.arc(-17, -68, 8, PI * .1, PI * .9); q.moveTo(25, -68); q.arc(17, -68, 8, PI * .1, PI * .9); }, 2.2);
    else if (o.eyes === 'happy') pen(c, (q) => { q.arc(-17, -64, 8, PI * 1.1, PI * 1.9); q.moveTo(9.4, -66.5); q.arc(17, -64, 8, PI * 1.1, PI * 1.9); }, 2.2);
    else { const r = o.eyes === 'wide' ? 8.5 : 6.5; dot(c, -16, -69, r, '#3e2b26'); dot(c, 18, -69, r, '#3e2b26'); dot(c, -14, -72, 2.2, '#fff'); dot(c, 20, -72, 2.2, '#fff'); }
    { const p = new Path2D(); p.moveTo(-6, -58); p.lineTo(6, -58); p.lineTo(0, -46); p.closePath(); cut(c, p, '#e8a54a', { blur: 2, sy: 1 }); }
    if (o.mood === 'no') { c.fillStyle = '#7a3f3a'; c.beginPath(); c.ellipse(0, -40, 3, 4, 0, 0, TAU); c.fill(); }
    // ночной колпак со звёздами и месяцем — днём сова спит
    { const p = new Path2D(); p.moveTo(-34, -92); p.bezierCurveTo(-10, -142, 40, -132, 62, -92); p.bezierCurveTo(30, -112, 0, -102, -34, -92); p.closePath(); cut(c, p, '#7f9fc0', { blur: 4 });
      c.save(); c.clip(p); dot(c, -6, -108, 2.4, '#f6e3a8'); dot(c, 22, -116, 2, '#f6e3a8'); dot(c, 40, -104, 1.8, '#f6e3a8');
      c.fillStyle = '#f6e3a8'; c.beginPath(); c.arc(8, -112, 6, 0, TAU); c.arc(10.5, -114, 5, 0, TAU, true); c.fill('evenodd'); c.restore(); }
    cut(c, E(64, -88, 8, 8), '#fff6e6', { blur: 2 });
  },
  frog(c, o) {
    cut(c, E(-28, -9, 16, 9), '#6fa35f', { blur: 3 }); cut(c, E(28, -9, 16, 9), '#6fa35f', { blur: 3 });
    cut(c, E(0, -30, 36, 28), '#86bd70', { stain: '#5f9450', box: [-36, -58, 72, 56], n: 3 });
    cut(c, E(3, -21, 22, 14), '#dfeab0', { shadow: false });
    cut(c, E(-15, -55, 13, 12), '#86bd70', { blur: 3, sy: 2 }); cut(c, E(17, -55, 13, 12), '#86bd70', { blur: 3, sy: 2 });
    cut(c, E(-15, -56, 8.5, 8.5), '#fffaf0', { shadow: false }); cut(c, E(17, -56, 8.5, 8.5), '#fffaf0', { shadow: false });
    eye(c, -14, -55, 3.8, o); eye(c, 18, -55, 3.8, o);
    if (o.mood === 'happy') mouth(c, 2, -38, 12, o);
    else if (o.mood === 'no') { c.fillStyle = '#7a3f3a'; c.beginPath(); c.ellipse(2, -36, 5, 4, 0, 0, TAU); c.fill(); }
    else pen(c, (q) => { q.moveTo(-14, -39); q.quadraticCurveTo(2, -29, 20, -39); }, 2);
    blush(c, -22, -38, 5); blush(c, 26, -38, 5);
    { const p = new Path2D(); p.moveTo(2, -27); p.lineTo(-14, -35); p.lineTo(-14, -19); p.closePath(); p.moveTo(2, -27); p.lineTo(18, -35); p.lineTo(18, -19); p.closePath(); cut(c, p, '#e2665c', { blur: 2, sy: 1 }); }
    cut(c, E(2, -27, 4.5, 4.5), '#c94f48', { blur: 1, sy: 1 });
    cut(c, E(-12, -2, 9, 4.5), '#6fa35f', { blur: 2, sy: 1 }); cut(c, E(16, -2, 9, 4.5), '#6fa35f', { blur: 2, sy: 1 });
  },
  rabbit(c, o) {
    cut(c, E(-24, -16, 10, 10), '#fffaf3', { blur: 3 });
    cut(c, E(-8, -4, 14, 6), '#e6dccd', { blur: 2, sy: 1 }); cut(c, E(16, -4, 14, 6), '#e6dccd', { blur: 2, sy: 1 });
    cut(c, E(0, -30, 24, 29), '#efe6da', { stain: '#d9cbb8', box: [-24, -59, 48, 59], n: 2 });
    cut(c, E(6, -24, 13, 18), '#fffaf3', { shadow: false });
    cut(c, E(-2, -106, 9, 32, -.14), '#efe6da', { blur: 4 }); cut(c, E(-2, -104, 4.6, 23, -.14), '#f3b9b9', { shadow: false });
    cut(c, E(19, -104, 9, 32, .22), '#efe6da', { blur: 4 }); cut(c, E(19, -102, 4.6, 23, .22), '#f3b9b9', { shadow: false });
    cut(c, E(8, -66, 22, 20), '#efe6da', { blur: 4, sy: 2 });
    eye(c, 2, -69, 2.9, o); eye(c, 17, -70, 2.9, o);
    cut(c, E(27, -62, 4, 3), '#e8838a', { blur: 1, sy: 1 });
    c.fillStyle = '#fffaf3'; c.fillRect(22.5, -58, 6, 6); pen(c, (q) => { q.rect(22.5, -58, 6, 6); q.moveTo(25.5, -58); q.lineTo(25.5, -52); }, 1, 'rgba(90,63,53,.5)');
    if (o.mood !== 'idle') mouth(c, 18, -54, 4, o);
    blush(c, 12, -58, 5);
    pen(c, (q) => { q.moveTo(28, -60); q.lineTo(42, -63); q.moveTo(28, -58); q.lineTo(42, -56); }, 1, 'rgba(90,63,53,.5)');
    cut(c, E(15, -34, 6, 5), '#e6dccd', { blur: 2, sy: 1 });
  },
  squirrel(c, o) {
    const T = new Path2D();
    for (let i = 0; i <= 14; i++) { const t = i / 14, u = 1 - t;
      const x = u * u * u * -8 + 3 * u * u * t * -66 + 3 * u * t * t * -66 + t * t * t * -18, y = u * u * u * -12 + 3 * u * u * t * -20 + 3 * u * t * t * -96 + t * t * t * -104;
      const r = 9 + 15 * Math.sin(t * PI * .85); T.moveTo(x + r, y); T.arc(x, y, r, 0, TAU); }
    T.moveTo(-4, -96); T.arc(-10, -96, 10, 0, TAU);
    cut(c, T, '#cf7a42', { stain: '#a85a2e', box: [-90, -125, 90, 120], n: 3, blur: 6, edge: false });
    pen(c, (q) => { q.moveTo(-14, -16); q.bezierCurveTo(-56, -22, -58, -84, -22, -96); }, 5, 'rgba(240,180,120,.55)');
    cut(c, E(-6, -3, 9, 5), '#b8642f', { blur: 2, sy: 1 }); cut(c, E(14, -3, 9, 5), '#b8642f', { blur: 2, sy: 1 });
    cut(c, E(2, -28, 18, 25), '#d9844a', { stain: '#b8642f', box: [-18, -53, 36, 50], n: 2 });
    cut(c, E(8, -24, 10, 16), '#f6dcb5', { shadow: false });
    { const p = new Path2D(); p.moveTo(2, -70); p.lineTo(3, -92); p.lineTo(14, -74); p.closePath(); p.moveTo(16, -72); p.lineTo(24, -92); p.lineTo(26, -70); p.closePath(); cut(c, p, '#d9844a', { blur: 3 }); }
    pen(c, (q) => { q.moveTo(3, -92); q.lineTo(1, -98); q.moveTo(3, -92); q.lineTo(6, -98); q.moveTo(24, -92); q.lineTo(22, -99); q.moveTo(24, -92); q.lineTo(27, -98); }, 1.6, '#a85a2e');
    cut(c, E(13, -58, 17, 16), '#d9844a', { blur: 4, sy: 2 });
    cut(c, E(22, -53, 8, 6), '#f6dcb5', { shadow: false });
    eye(c, 8, -61, 2.7, o); eye(c, 20, -62, 2.7, o);
    dot(c, 29, -55, 2.6, '#3e2b26'); mouth(c, 24, -48, 4, o); blush(c, 12, -51, 4);
    ITEM.nut(c, 22, -34, .32);
    cut(c, E(18, -32, 5, 4), '#d9844a', { blur: 2, sy: 1 }); cut(c, E(26, -33, 5, 4), '#d9844a', { blur: 2, sy: 1 });
  },
  mole(c, o) {
    cut(c, E(-12, -3, 10, 5), '#e3a2a8', { blur: 2, sy: 1 }); cut(c, E(14, -3, 10, 5), '#e3a2a8', { blur: 2, sy: 1 });
    cut(c, E(0, -30, 30, 30), '#6b6880', { stain: '#4f4c63', box: [-30, -60, 60, 60], n: 3 });
    cut(c, E(6, -24, 17, 18), '#837f99', { shadow: false });
    cut(c, E(14, -55, 21, 18), '#6b6880', { blur: 4, sy: 2 });
    { const p = new Path2D(); p.moveTo(28, -60); p.quadraticCurveTo(48, -58, 49, -51); p.quadraticCurveTo(47, -45, 30, -47); p.closePath(); cut(c, p, '#f0b3b4', { blur: 2, sy: 1 }); }
    dot(c, 49, -53, 4.6, '#e07a85');
    if (o.mood !== 'idle') mouth(c, 32, -43, 4, o);
    // круглые очки
    c.fillStyle = 'rgba(225,240,250,.6)'; c.beginPath(); c.arc(8, -60, 8.5, 0, TAU); c.arc(26, -60, 8.5, 0, TAU); c.fill();
    if (o.eyes === 'blink' || o.eyes === 'happy') { eye(c, 8, -60, 2.2, o); eye(c, 26, -60, 2.2, o); } else { const r = o.eyes === 'wide' ? 2.6 : 1.9; dot(c, 9, -60, r, '#2a2020'); dot(c, 27, -60, r, '#2a2020'); }
    pen(c, (q) => { q.arc(8, -60, 8.5, 0, TAU); q.moveTo(34.5, -60); q.arc(26, -60, 8.5, 0, TAU); q.moveTo(16.5, -61); q.quadraticCurveTo(17, -64, 17.5, -61); q.moveTo(-0.5, -61); q.lineTo(-8, -64); }, 2.4, '#3e2b26');
    pen(c, (q) => { q.arc(8, -60, 5.5, PI * 1.1, PI * 1.5); q.moveTo(21.4, -62.6); q.arc(26, -60, 5.5, PI * 1.1, PI * 1.5); }, 1.4, 'rgba(255,255,255,.9)');
    cut(c, E(26, -22, 12, 7, -.5), '#f0b3b4', { blur: 2, sy: 1 }); cut(c, E(-20, -22, 12, 7, .5), '#f0b3b4', { blur: 2, sy: 1 });
    pen(c, (q) => { q.moveTo(33, -28); q.lineTo(37, -30); q.moveTo(35, -24); q.lineTo(39, -25); q.moveTo(-27, -28); q.lineTo(-31, -30); q.moveTo(-29, -24); q.lineTo(-33, -25); }, 1.3, '#c98088');
  },
};
// кадр «портрета» и «силуэта» (центр и радиус в координатах фигурки), голова для облачка
const FRAME = {
  mouse: { p: [8, -62, 30], s: [-6, -46, 56], head: [10, -60] }, snail: { p: [20, -48, 46], s: [0, -44, 66], head: [46, -48] },
  owl: { p: [8, -82, 50], s: [10, -66, 72], head: [10, -70] }, frog: { p: [2, -42, 38], s: [0, -34, 52], head: [2, -48] },
  rabbit: { p: [8, -86, 52], s: [0, -66, 72], head: [10, -68] }, squirrel: { p: [13, -66, 32], s: [-18, -56, 66], head: [14, -60] },
  mole: { p: [24, -55, 31], s: [8, -42, 54], head: [22, -56] },
};

/* ---------------- вещи: подарки и «загадки» (центр в 0,0, радиус ~40) ---------------- */
const ITEM = {
  cheese(c, x = 0, y = 0, s = 1) { c.save(); c.translate(x, y); c.scale(s, s);
    const p = new Path2D(); p.moveTo(-38, 18); p.lineTo(34, 18); p.lineTo(34, -6); p.lineTo(-38, -22); p.closePath(); cut(c, p, '#f3c95a', { stain: '#d9a83a', box: [-38, -22, 72, 40], n: 2, blur: 4 });
    const t = new Path2D(); t.moveTo(-38, -22); t.lineTo(34, -6); t.lineTo(20, -24); t.closePath(); cut(c, t, '#f8dc86', { blur: 2, sy: 1 });
    for (const [hx, hy, r] of [[-20, 0, 5], [4, 6, 6], [22, 2, 4], [-6, -10, 3]]) dot(c, hx, hy, r, '#d9a83a');
    c.restore(); },
  berry(c, x = 0, y = 0, s = 1) { c.save(); c.translate(x, y); c.scale(s, s);
    const p = new Path2D(); p.moveTo(0, 36); p.bezierCurveTo(-36, 10, -34, -26, 0, -22); p.bezierCurveTo(34, -26, 36, 10, 0, 36); cut(c, p, '#e2665c', { stain: '#b8404a', box: [-34, -26, 68, 62], n: 2, blur: 4 });
    for (let i = 0; i < 9; i++) { const a = i * 2.4, r = 6 + (i % 3) * 7; dot(c, Math.cos(a) * r * .8, 6 + Math.sin(a) * r * .9, 1.8, '#f8dc86'); }
    const l = new Path2D(); for (let i = 0; i < 5; i++) { const a = -PI / 2 + (i - 2) * .55; l.moveTo(0, -22); l.quadraticCurveTo(Math.cos(a) * 10 - 6, -22 + Math.sin(a) * 14, Math.cos(a) * 22, -22 + Math.sin(a) * 12 + 6); l.quadraticCurveTo(Math.cos(a) * 8 + 4, -20, 0, -22); }
    cut(c, l, '#7fa676', { blur: 2, sy: 1 }); pen(c, (q) => { q.moveTo(0, -26); q.quadraticCurveTo(2, -34, 8, -38); }, 3, '#6e9c63'); c.restore(); },
  moon(c, x = 0, y = 0, s = 1) { c.save(); c.translate(x, y); c.scale(s, s);
    const p = new Path2D(); p.arc(-4, 0, 30, 0, TAU); p.arc(10, -8, 25, 0, TAU, true); cut(c, p, '#f3c95a', { blur: 4 });
    for (const [sx, sy, r] of [[22, 16, 7], [30, -22, 5], [-26, -28, 4]]) { A.star(c, sx, sy, r, 5, .45); c.fillStyle = '#f8dc86'; c.fill(); }
    c.restore(); },
  lily(c, x = 0, y = 0, s = 1) { c.save(); c.translate(x, y); c.scale(s, s);
    const p = new Path2D(); p.moveTo(0, 8); p.arc(0, 8, 36, -PI / 2 + .25, -PI / 2 - .25 + TAU); p.closePath(); c.save(); c.scale(1, .62); cut(c, p, '#7fb069', { stain: '#5f9450', box: [-36, -28, 72, 72], n: 2, blur: 4 }); c.restore();
    for (let i = 0; i < 7; i++) { const a = -PI / 2 + (i - 3) * .42; const q = new Path2D(); q.ellipse(Math.cos(a) * 9, -4 + Math.sin(a) * 9, 6, 13, a + PI / 2, 0, TAU); cut(c, q, i % 2 ? '#f6c2cc' : '#fbe1e6', { blur: 2, sy: 1 }); }
    dot(c, 0, -6, 5, '#f3c95a'); c.restore(); },
  carrot(c, x = 0, y = 0, s = 1) { c.save(); c.translate(x, y); c.scale(s, s); c.rotate(.5);
    for (const [a, l] of [[-.5, 26], [0, 30], [.5, 24]]) { const q = new Path2D(); q.ellipse(Math.sin(a) * l * .5, -22 - Math.cos(a) * l * .5, 5, l * .5, a, 0, TAU); cut(c, q, '#7fa676', { blur: 2, sy: 1 }); }
    const p = new Path2D(); p.moveTo(-13, -20); p.quadraticCurveTo(0, -26, 13, -20); p.quadraticCurveTo(6, 16, 0, 40); p.quadraticCurveTo(-6, 16, -13, -20); cut(c, p, '#ec8a4a', { stain: '#c86f3c', box: [-13, -26, 26, 66], n: 2, blur: 4 });
    pen(c, (q) => { q.moveTo(-9, -6); q.lineTo(-3, -5); q.moveTo(4, 6); q.lineTo(9, 5); q.moveTo(-6, 18); q.lineTo(-1, 19); }, 1.4, '#c86f3c'); c.restore(); },
  nut(c, x = 0, y = 0, s = 1) { c.save(); c.translate(x, y); c.scale(s, s);
    const p = new Path2D(); p.moveTo(0, 32); p.bezierCurveTo(-30, 28, -32, -6, -22, -14); p.lineTo(22, -14); p.bezierCurveTo(32, -6, 30, 28, 0, 32); cut(c, p, '#c48a52', { stain: '#9a6542', box: [-30, -14, 60, 46], n: 2, blur: 3 });
    const h = new Path2D(); h.moveTo(-28, -10); h.bezierCurveTo(-26, -34, 26, -34, 28, -10); h.quadraticCurveTo(0, -2, -28, -10); cut(c, h, '#8a6a45', { blur: 2, sy: 1 });
    pen(c, (q) => { q.moveTo(-14, -18); q.lineTo(-10, -12); q.moveTo(0, -22); q.lineTo(0, -12); q.moveTo(14, -18); q.lineTo(10, -12); }, 1.4, '#6b4a3a');
    pen(c, (q) => { q.moveTo(-10, 6); q.quadraticCurveTo(-8, 18, 0, 26); }, 2, 'rgba(255,255,255,.35)'); c.restore(); },
  spade(c, x = 0, y = 0, s = 1) { c.save(); c.translate(x, y); c.scale(s, s); c.rotate(-.35);
    cut(c, rrp(-4, -42, 8, 46, 3), '#b07a55', { blur: 3, sy: 2 }); cut(c, rrp(-12, -48, 24, 8, 4), '#8a5c3e', { blur: 2, sy: 1 });
    const b = new Path2D(); b.moveTo(-15, 2); b.lineTo(15, 2); b.lineTo(15, 22); b.quadraticCurveTo(14, 38, 0, 44); b.quadraticCurveTo(-14, 38, -15, 22); b.closePath(); cut(c, b, '#9fb4c4', { stain: '#6f8aa0', box: [-15, 2, 30, 42], n: 2, blur: 4 });
    pen(c, (q) => { q.moveTo(-8, 10); q.lineTo(-6, 30); }, 2, 'rgba(255,255,255,.5)'); c.restore(); },
  feather(c, x = 0, y = 0, s = 1) { c.save(); c.translate(x, y); c.scale(s, s); c.rotate(.6);
    const p = new Path2D(); p.moveTo(0, -38); p.bezierCurveTo(22, -20, 18, 18, 2, 34); p.bezierCurveTo(-16, 16, -20, -18, 0, -38); cut(c, p, '#b7a8cf', { stain: '#8f7fae', box: [-20, -38, 42, 72], n: 2, blur: 3 });
    pen(c, (q) => { q.moveTo(0, -34); q.quadraticCurveTo(4, 0, 1, 42); for (let i = 0; i < 5; i++) { q.moveTo(2, -20 + i * 10); q.lineTo(12, -26 + i * 10); q.moveTo(1, -18 + i * 10); q.lineTo(-10, -24 + i * 10); } }, 1.4, '#6f5f80'); c.restore(); },
  button(c, x = 0, y = 0, s = 1) { c.save(); c.translate(x, y); c.scale(s, s);
    cut(c, E(0, 0, 30, 30), '#7f9fc0', { stain: '#4f79a8', box: [-30, -30, 60, 60], n: 2, blur: 4 }); pen(c, (q) => q.arc(0, 0, 22, 0, TAU), 2, 'rgba(255,255,255,.4)');
    for (const [bx, by] of [[-7, -7], [7, -7], [-7, 7], [7, 7]]) dot(c, bx, by, 4, '#355d8c'); c.restore(); },
  gift(c, x = 0, y = 0, s = 1) { c.save(); c.translate(x, y); c.scale(s, s);
    cut(c, rrp(-26, -14, 52, 42, 4), '#e2665c', { blur: 3, sy: 2 }); cut(c, rrp(-30, -24, 60, 14, 3), '#ec7d70', { blur: 2, sy: 1 });
    c.fillStyle = '#f3c95a'; c.fillRect(-5, -24, 10, 52);
    const b = new Path2D(); b.ellipse(-10, -30, 11, 6, -.5, 0, TAU); b.ellipse(10, -30, 11, 6, .5, 0, TAU); cut(c, b, '#f3c95a', { blur: 2, sy: 1 }); c.restore(); },
};
// примета на марке (центр 0,0, радиус ~48)
const DETAIL = {
  mouse(c) { cut(c, E(-46, 22, 30, 34), '#c9bcc3', { stain: '#a898a6', box: [-76, -12, 60, 68], n: 2 }); cut(c, E(-30, 46, 9, 5), '#a898a6', { blur: 2, sy: 1 });
    pen(c, (q) => { q.moveTo(-22, 24); q.bezierCurveTo(10, 30, 40, 10, 30, -16); q.bezierCurveTo(22, -36, -4, -30, 2, -12); q.quadraticCurveTo(6, -2, 14, -8); }, 5.5, '#c4959c'); },
  snail(c) { cut(c, E(0, 2, 40, 38), '#f0a98a', { stain: '#d97b66', box: [-40, -36, 80, 76], n: 3 }); pen(c, (q) => { let a = 0; q.moveTo(0, 2); for (let i = 0; i < 70; i++) { a += .2; const r = a * 2.6; q.lineTo(Math.cos(a) * r, 2 + Math.sin(a) * r); } }, 3, '#b85a4c'); },
  owl(c) { const p = new Path2D(); p.moveTo(-44, 26); p.bezierCurveTo(-20, -40, 30, -40, 44, 22); p.bezierCurveTo(14, 4, -14, 12, -44, 26); p.closePath(); cut(c, p, '#7f9fc0', { blur: 4 });
    c.save(); c.clip(p); dot(c, -14, 4, 3, '#f6e3a8'); dot(c, 18, -10, 2.6, '#f6e3a8'); dot(c, 30, 8, 2.2, '#f6e3a8'); c.fillStyle = '#f6e3a8'; c.beginPath(); c.arc(0, -8, 8, 0, TAU); c.arc(3.5, -10.5, 6.6, 0, TAU, true); c.fill('evenodd'); c.restore();
    cut(c, E(44, 26, 11, 11), '#fff6e6', { blur: 2 }); cut(c, rrp(-48, 22, 80, 14, 7), '#9fb8d6', { blur: 2, sy: 1 }); },
  frog(c) { const p = new Path2D(); p.moveTo(0, 0); p.lineTo(-40, -24); p.lineTo(-40, 24); p.closePath(); p.moveTo(0, 0); p.lineTo(40, -24); p.lineTo(40, 24); p.closePath(); cut(c, p, '#e2665c', { stain: '#b8404a', box: [-40, -24, 80, 48], n: 2 });
    pen(c, (q) => { q.moveTo(-30, -10); q.lineTo(-16, -4); q.moveTo(30, -10); q.lineTo(16, -4); }, 1.6, 'rgba(255,255,255,.45)'); cut(c, E(0, 0, 10, 10), '#c94f48', { blur: 2, sy: 1 });
    wash(c, [[-60, 32], [60, 32], [60, 60], [-60, 60]], '#86bd70', { layers: 6, alpha: .12 }); },
  rabbit(c) { for (const [x, a] of [[-16, -.18], [16, .22]]) { cut(c, E(x, -2, 14, 50, a), '#efe6da', { blur: 4 }); cut(c, E(x, 2, 7, 38, a), '#f3b9b9', { shadow: false }); } cut(c, E(0, 58, 40, 14), '#efe6da', { blur: 3 }); },
  squirrel(c) { const T = new Path2D(); for (let i = 0; i <= 14; i++) { const t = i / 14, u = 1 - t; const x = u * u * u * 26 + 3 * u * u * t * -40 + 3 * u * t * t * -44 + t * t * t * 6, y = u * u * u * 44 + 3 * u * u * t * 40 + 3 * u * t * t * -40 + t * t * t * -36; const r = 12 + 16 * Math.sin(t * PI * .85); T.moveTo(x + r, y); T.arc(x, y, r, 0, TAU); }
    T.moveTo(20, -32); T.arc(10, -32, 12, 0, TAU); cut(c, T, '#cf7a42', { stain: '#a85a2e', box: [-70, -56, 110, 116], n: 3, blur: 5, edge: false }); pen(c, (q) => { q.moveTo(20, 40); q.bezierCurveTo(-30, 34, -36, -26, 2, -36); }, 6, 'rgba(240,180,120,.55)'); },
  mole(c) { c.fillStyle = 'rgba(225,240,250,.75)'; c.beginPath(); c.arc(-21, 0, 18, 0, TAU); c.arc(21, 0, 18, 0, TAU); c.fill();
    pen(c, (q) => { q.arc(-21, 0, 18, 0, TAU); q.moveTo(39, 0); q.arc(21, 0, 18, 0, TAU); q.moveTo(-3, -2); q.quadraticCurveTo(0, -9, 3, -2); q.moveTo(-39, -2); q.lineTo(-50, -8); q.moveTo(39, -2); q.lineTo(50, -8); }, 5, '#3e2b26');
    pen(c, (q) => { q.arc(-21, 0, 11, PI * 1.1, PI * 1.5); q.moveTo(11, -3.5); q.arc(21, 0, 11, PI * 1.1, PI * 1.5); }, 2.4, 'rgba(255,255,255,.95)'); },
};

/* ---------------- жители деревни ---------------- */
const RES = [
  { id: 'squirrel', name: 'Белка', house: 'pinecone', gift: 'nut', gname: 'орешек', rebus: 'nut', yes: 'Цок! Моё! Лови орешек!', no: ['Цок-цок! Не мне!', 'Не моё! Беги дальше!'] },
  { id: 'mouse', name: 'Мышка', house: 'teapot', gift: 'cheese', gname: 'сыр', rebus: 'cheese', yes: 'Пи! Это мне! Держи сыр.', no: ['Пи-пи! Это не мне!', 'Не моё, честное мышиное!'] },
  { id: 'snail', name: 'Улитка', house: 'mushroom', gift: 'berry', gname: 'земляника', rebus: 'berry', yes: 'Мне?! Ура-а… медленное ура!', no: ['Э-то… не… мне…', 'Не мне. Но заходи ещё!'] },
  { id: 'owl', name: 'Сова', house: 'stump', gift: 'feather', gname: 'пёрышко', rebus: 'moon', yes: 'Ух ты… мне! Держи пёрышко.', no: ['Ух! Я сплю… Не мне!', 'Ху-у… Не моё. Доброй ночи!'] },
  { id: 'rabbit', name: 'Зайка', house: 'pumpkin', gift: 'carrot', gname: 'морковка', rebus: 'carrot', yes: 'Мне! Спасибо! Вот морковка.', no: ['Ой-ой! Это не мне!', 'Не-не-не, не моё!'] },
  { id: 'mole', name: 'Крот', house: 'hill', gift: 'button', gname: 'пуговка', rebus: 'spade', yes: 'Мне? Мне! Вот пуговка.', no: ['Мне? Ничего не вижу… А, нет.', 'Хм… нет, не моё.'] },
  { id: 'frog', name: 'Лягушка', house: 'can', gift: 'lily', gname: 'кувшинка', rebus: 'lily', yes: 'Ква! Моё! Вот кувшинка.', no: ['Ква! Не моё!', 'Ква-ква! Ищи другого!'] },
];
const RBY = Object.fromEntries(RES.map((r) => [r.id, r]));

/* ================= дома (основание по центру; житель — на стороне +x) ================= */
const HOUSE = {
  teapot: { anchor: [44, -84], doorX: 0, rs: .95, box: [-120, -168, 146, 6], draw(c) {
    const y = -72, T = '#6fa7a4', TD = '#3d7f84';
    { const p = new Path2D(); p.ellipse(-86, y, 30, 38, 0, 0, TAU); p.ellipse(-86, y, 17, 25, 0, 0, TAU); const k = sk(c); c.save(); c.shadowColor = SHC; c.shadowBlur = 6 * k; c.shadowOffsetY = 4 * k; c.fillStyle = '#5d9592'; c.fill(p, 'evenodd'); c.restore(); }
    { const p = new Path2D(); p.moveTo(66, y + 6); p.bezierCurveTo(102, y - 2, 112, y - 34, 130, y - 56); p.lineTo(142, y - 49); p.bezierCurveTo(126, y - 24, 118, y + 22, 72, y + 32); p.closePath(); cut(c, p, T, { blur: 5 }); }
    cut(c, E(0, -8, 48, 9), '#5d9592', { blur: 4 });
    cut(c, E(0, y, 82, 62), T, { stain: TD, box: [-82, y - 62, 164, 124], n: 4 });
    wash(c, ellP(-16, y + 22, 58, 26, 12), TD, { layers: 8, alpha: .06 });
    c.save(); c.clip(E(0, y, 82, 62)); c.fillStyle = '#f6e2b8'; c.fillRect(-90, y - 30, 180, 11); c.fillStyle = '#e88f6e'; for (let i = -6; i <= 6; i++) dot(c, i * 13, y - 24.5, 3); c.restore();
    cut(c, E(0, y - 60, 52, 15), '#e88f6e'); cut(c, E(0, y - 77, 8, 8), '#e88f6e');
    { const p = new Path2D(); p.moveTo(-18, -11); p.lineTo(-18, -44); p.arc(0, -44, 18, PI, 0); p.lineTo(18, -11); p.closePath(); cut(c, p, '#b07a55', { blur: 3, sy: 2 }); pen(c, (q) => { q.moveTo(0, -60); q.lineTo(0, -12); }, 1.5); dot(c, 11, -30, 2.6, '#f3c95a'); }
    cut(c, E(44, -84, 27, 27), '#fbefd0', { blur: 3, sy: 2 });
    ITEM.cheese(c, -58, -6, .36);                       // кусочек сыра у порога
  } },
  mushroom: { anchor: [8, -134], doorX: 0, rs: .9, box: [-112, -205, 112, 6], draw(c) {
    ITEM.berry(c, -72, -12, .32); ITEM.berry(c, -54, -6, .26);
    pen(c, (q) => { q.moveTo(-64, 0); q.quadraticCurveTo(-66, -14, -72, -22); q.moveTo(-60, 0); q.quadraticCurveTo(-56, -10, -54, -14); }, 2, '#6e9c63');
    { const p = new Path2D(); p.moveTo(-38, 0); p.bezierCurveTo(-42, -42, -33, -72, -29, -79); p.lineTo(29, -79); p.bezierCurveTo(33, -72, 42, -42, 40, 0); p.closePath(); cut(c, p, '#f6e7c8', { stain: '#e3c9a0', box: [-42, -80, 84, 80], n: 3 }); }
    { const p = new Path2D(); p.moveTo(-108, -72); p.bezierCurveTo(-108, -158, 108, -158, 108, -72); p.bezierCurveTo(72, -60, -72, -60, -108, -72); p.closePath(); cut(c, p, '#e2665c', { stain: '#b8404a', box: [-108, -140, 216, 80], n: 5, blur: 9 }); }
    for (const [dx, dy, r] of [[-65, -94, 12], [-22, -123, 9], [29, -110, 13], [72, -86, 9], [-84, -77, 6], [7, -82, 6]]) cut(c, E(dx, dy, r, r * .85), '#fff6e6', { blur: 2, sy: 1 });
    { const p = new Path2D(); p.moveTo(-16, 0); p.lineTo(-16, -24); p.arc(0, -24, 16, PI, 0); p.lineTo(16, 0); p.closePath(); cut(c, p, '#7f9fc0', { blur: 3, sy: 2 }); dot(c, 9, -10, 2.4, '#f3c95a'); }
    cut(c, E(-22, -52, 9, 9), '#fbefd0', { blur: 2, sy: 1 }); pen(c, (q) => { q.moveTo(-31, -52); q.lineTo(-13, -52); q.moveTo(-22, -61); q.lineTo(-22, -43); }, 1.4, '#b07a55');
    cut(c, rrp(56, -36, 5, 36, 2), '#8a6a55', { blur: 2 }); cut(c, rrp(46, -50, 26, 16, 3), '#4f79a8', { blur: 3 }); pen(c, (q) => { q.moveTo(51, -44); q.lineTo(67, -44); }, 1.6, '#2f4f78');
  } },
  stump: { anchor: [0, -101], doorX: 0, rs: .82, box: [-84, -232, 74, 6], draw(c) {
    pen(c, (q) => { q.moveTo(-50, -66); q.quadraticCurveTo(-64, -80, -78, -88); }, 3, '#8a5c3e');
    { const p = new Path2D(); p.arc(-82, -94, 9, 0, TAU); p.arc(-78, -97, 8, 0, TAU, true); cut(c, p, '#f3c95a', { blur: 2, sy: 1 }); }
    cut(c, E(-50, -4, 16, 8), '#a87b55', { blur: 3 }); cut(c, E(50, -4, 16, 8), '#a87b55', { blur: 3 });
    { const p = new Path2D(); p.moveTo(-52, 0); p.bezierCurveTo(-56, -40, -52, -78, -54, -100); p.lineTo(54, -100); p.bezierCurveTo(52, -78, 56, -40, 52, 0); p.closePath(); cut(c, p, '#b88760', { stain: '#8a5c3e', box: [-56, -100, 112, 100], n: 4 }); }
    pen(c, (q) => { q.moveTo(-36, -20); q.lineTo(-38, -70); q.moveTo(34, -14); q.lineTo(36, -60); }, 1.2, 'rgba(90,63,53,.35)');
    cut(c, E(0, -100, 54, 13), '#e9c99a', { blur: 4 });
    pen(c, (q) => { q.ellipse(0, -100, 34, 7.5, 0, 0, TAU); q.moveTo(14, -100); q.ellipse(0, -100, 14, 3, 0, 0, TAU); }, 1.2, '#a8735a');
    wash(c, [[-56, -98], [-20, -106], [-8, -94], [-36, -78], [-54, -64]], '#7fa676', { layers: 10, alpha: .08 });
    { const p = new Path2D(); p.moveTo(-19, 0); p.lineTo(-19, -36); p.arc(0, -36, 19, PI, 0); p.lineTo(19, 0); p.closePath(); cut(c, p, '#6b4a3a', { blur: 3, sy: 2 }); dot(c, 10, -16, 2.4, '#f3c95a'); }
    pen(c, (q) => { q.moveTo(34, -78); q.lineTo(34, -70); }, 1.4); cut(c, rrp(28, -70, 12, 15, 4), '#f3c95a', { blur: 2, sy: 1 });
  } },
  can: { anchor: [-14, -107], doorX: 0, rs: .95, box: [-160, -190, 100, 6], draw(c) {
    const C = '#8fb3c9', CD = '#5f87a3';
    wash(c, ellP(-124, 8, 44, 11, 16), '#7fb8d8', { layers: 10, alpha: .07 }); lift(c, ellP(-132, 6, 16, 4, 10), { n: 4, a: .3 });
    { const p = new Path2D(); p.moveTo(-134, 6); p.arc(-134, 6, 14, -PI / 2 + .3, -PI / 2 - .3 + TAU); p.closePath(); c.save(); c.translate(0, 3); c.scale(1, .45); c.translate(0, 3); cut(c, p, '#7fb069', { blur: 2, sy: 1 }); c.restore(); }
    { const p = new Path2D(); p.moveTo(-52, -30); p.lineTo(-124, -98); p.lineTo(-114, -110); p.lineTo(-54, -64); p.closePath(); cut(c, p, C, { blur: 5 }); }
    c.save(); c.translate(-122, -106); c.rotate(-.75); cut(c, E(0, 0, 17, 8), '#7ea3ba', { blur: 3 }); for (let i = -2; i <= 2; i++) dot(c, i * 5, 0, 1.4, '#4f6f86'); c.restore();
    { const k = sk(c); c.save(); c.shadowColor = SHC; c.shadowBlur = 5 * k; c.shadowOffsetY = 3 * k; c.strokeStyle = '#7ea3ba'; c.lineWidth = 11; c.lineCap = 'round'; c.beginPath(); c.moveTo(24, -104); c.bezierCurveTo(36, -148, 98, -140, 92, -86); c.bezierCurveTo(90, -64, 72, -52, 58, -48); c.stroke(); c.restore(); }
    { const p = new Path2D(); p.moveTo(-60, 0); p.lineTo(-56, -104); p.quadraticCurveTo(0, -112, 56, -104); p.lineTo(60, 0); p.quadraticCurveTo(0, 7, -60, 0); p.closePath(); cut(c, p, C, { stain: CD, box: [-60, -110, 120, 112], n: 4 }); }
    pen(c, (q) => { q.moveTo(-58, -22); q.quadraticCurveTo(0, -16, 58, -22); q.moveTo(-56, -88); q.quadraticCurveTo(0, -94, 56, -88); }, 3, 'rgba(255,255,255,.4)');
    cut(c, E(0, -104, 56, 10), '#a9c7d8', { blur: 2, sy: 1 }); cut(c, E(0, -104, 46, 6), '#5f87a3', { shadow: false });
    { const p = new Path2D(); p.moveTo(-18, -2); p.lineTo(-18, -40); p.arc(0, -40, 18, PI, 0); p.lineTo(18, -2); p.closePath(); cut(c, p, '#e8b84a', { blur: 3, sy: 2 }); dot(c, 10, -20, 2.4, '#8a5c3e'); }
    cut(c, E(36, -70, 11, 11), '#fbefd0', { blur: 2, sy: 1 }); pen(c, (q) => q.arc(36, -70, 11, 0, TAU), 1.6, '#5f87a3');
  } },
  pumpkin: { anchor: [34, -124], doorX: 0, rs: .95, box: [-150, -262, 100, 6], draw(c) {
    wash(c, ellP(-118, 2, 34, 8, 12), '#8a6447', { layers: 8, alpha: .08 });
    for (const [x, h] of [[-136, 12], [-118, 15], [-100, 11]]) { const p = new Path2D(); p.moveTo(x - 6, 0); p.lineTo(x + 6, 0); p.lineTo(x, h); p.closePath(); c.save(); c.translate(0, -h + 2); cut(c, p, '#ec8a4a', { blur: 2, sy: 1 }); c.restore();
      pen(c, (q) => { q.moveTo(x, -10); q.quadraticCurveTo(x - 10, -24, x - 12, -34); q.moveTo(x, -10); q.quadraticCurveTo(x + 2, -26, x + 4, -38); q.moveTo(x, -10); q.quadraticCurveTo(x + 10, -22, x + 14, -30); }, 2.6, '#6e9c63'); }
    const P = '#ec9a5c', PD = '#c86f3c';
    for (const [x, y, rx, ry] of [[-62, -56, 38, 54], [62, -56, 38, 54], [-32, -62, 44, 62], [32, -62, 44, 62], [0, -64, 44, 64]]) cut(c, E(x, y, rx, ry), P, { stain: PD, box: [x - rx, y - ry, rx * 2, ry * 2], n: 2, blur: 5 });
    pen(c, (q) => { q.moveTo(-20, -122); q.quadraticCurveTo(-36, -64, -22, -4); q.moveTo(20, -122); q.quadraticCurveTo(36, -64, 22, -4); }, 1.6, 'rgba(160,80,40,.35)');
    { const p = new Path2D(); p.moveTo(-6, -124); p.quadraticCurveTo(-8, -146, 6, -156); p.lineTo(12, -150); p.quadraticCurveTo(2, -142, 6, -124); p.closePath(); cut(c, p, '#7fa676', { blur: 3 }); }
    { const p = new Path2D(); p.ellipse(-22, -140, 16, 8, -.5, 0, TAU); cut(c, p, '#8cc07c', { blur: 2, sy: 1 }); }
    { const p = new Path2D(); p.moveTo(-15, -2); p.lineTo(-15, -36); p.arc(0, -36, 15, PI, 0); p.lineTo(15, -2); p.closePath(); cut(c, p, '#7fa676', { blur: 3, sy: 2 }); dot(c, 8, -18, 2.4, '#f3c95a'); }
    cut(c, E(-40, -82, 10, 10), '#fbefd0', { blur: 2, sy: 1 }); pen(c, (q) => { q.moveTo(-50, -82); q.lineTo(-30, -82); q.moveTo(-40, -92); q.lineTo(-40, -72); }, 1.4, '#c86f3c');
  } },
  pinecone: { anchor: [2, -170], doorX: 0, rs: .82, box: [-116, -290, 70, 6], draw(c) {
    { const p = new Path2D(); p.moveTo(-104, -2); p.quadraticCurveTo(-104, -30, -84, -30); p.quadraticCurveTo(-64, -30, -64, -2); p.closePath(); for (const [x, y] of [[-92, -30], [-80, -32], [-86, -38], [-74, -28]]) ITEM.nut(c, x, y, .17); cut(c, p, '#c9a06a', { blur: 3 });
      c.save(); c.clip(p); pen(c, (q) => { for (let x = -104; x < -60; x += 7) { q.moveTo(x, -30); q.lineTo(x + 6, 0); } }, 1, 'rgba(120,80,40,.35)'); c.restore(); }
    const shape = new Path2D(); shape.moveTo(0, -176); shape.bezierCurveTo(46, -170, 62, -90, 54, -30); shape.quadraticCurveTo(48, 0, 0, 0); shape.quadraticCurveTo(-48, 0, -54, -30); shape.bezierCurveTo(-62, -90, -46, -170, 0, -176); shape.closePath();
    cut(c, shape, '#b0794f', { stain: '#7d5236', box: [-60, -176, 120, 176], n: 4 });
    c.save(); c.clip(shape);
    for (let j = 0, y = -168; y < 0; y += 16, j++) for (let x = -72 + (j % 2) * 12; x <= 72; x += 24) { const p = new Path2D(); p.arc(x, y, 12, 0, PI); c.fillStyle = 'rgba(122,78,48,.45)'; c.fill(p); pen(c, (q) => q.arc(x, y + 1, 12, .2, PI - .2), 1.4, 'rgba(230,190,140,.5)'); }
    c.restore();
    { const p = new Path2D(); p.moveTo(-15, 0); p.lineTo(-15, -30); p.arc(0, -30, 15, PI, 0); p.lineTo(15, 0); p.closePath(); cut(c, p, '#6b4a3a', { blur: 3, sy: 2 }); dot(c, 8, -14, 2.4, '#f3c95a'); }
    cut(c, E(0, -96, 11, 11), '#fbefd0', { blur: 2, sy: 1 }); pen(c, (q) => q.arc(0, -96, 11, 0, TAU), 1.6, '#6b4a3a');
  } },
  hill: { anchor: [36, -98], doorX: -30, rs: .95, box: [-150, -178, 118, 6], draw(c) {
    ITEM.spade(c, -132, -26, .62);
    { const p = new Path2D(); p.moveTo(-118, 0); p.bezierCurveTo(-108, -68, -58, -106, 0, -106); p.bezierCurveTo(58, -106, 108, -68, 118, 0); p.quadraticCurveTo(0, 8, -118, 0); p.closePath(); cut(c, p, '#a07a58', { stain: '#7a5a3e', box: [-118, -106, 236, 108], n: 5, blur: 8 }); }
    wash(c, [[-70, -88], [-20, -104], [20, -104], [56, -96], [30, -84], [-30, -82]], '#7fa676', { layers: 10, alpha: .08 });
    pen(c, (q) => { for (const x of [-56, -40, -14, 4, 62, 76]) { q.moveTo(x, -92 + Math.abs(x) * .05); q.lineTo(x - 3, -104 + Math.abs(x) * .05); q.moveTo(x, -92 + Math.abs(x) * .05); q.lineTo(x + 4, -102 + Math.abs(x) * .05); } }, 1.6, '#6e9c63');
    for (const [x, y, r] of [[-80, -20, 6], [70, -30, 5], [90, -12, 7], [-48, -60, 4]]) cut(c, E(x, y, r, r * .7), '#c9bcb0', { blur: 2, sy: 1 });
    cut(c, E(-30, -38, 29, 29), '#c99d6a', { blur: 3, sy: 2 });
    cut(c, E(-30, -38, 23, 23), '#b07a55', { shadow: false }); pen(c, (q) => { q.moveTo(-38, -59); q.lineTo(-38, -17); q.moveTo(-22, -59); q.lineTo(-22, -17); }, 1.2, 'rgba(90,63,53,.45)'); dot(c, -16, -38, 2.6, '#f3c95a');
    c.fillStyle = '#3e2b26'; c.beginPath(); c.ellipse(36, -98, 26, 8, 0, 0, TAU); c.fill();
  } },
};

/* ---------------- раскладка: своя для широкого окна и для телефона ---------------- */
const K = LAND ? {
  hub: [640, 486], card: { x: 640, y: 626, w: 380, h: 182 }, hor: 286, q: [1234, 48], plate: [20, 16, 440, 92], cap: [482, 16, 696],
  sun: { x0: 80, x1: 1200, y0: 300, top: 124 }, pf: [330, 690], size: 23,
  houses: { squirrel: [128, 506, .86], mouse: [372, 348, .8], snail: [640, 320, .82], owl: [906, 348, .8], rabbit: [1150, 506, .86], frog: [264, 676, .92], mole: [1024, 682, .92] },
} : {
  hub: [360, 800], card: { x: 360, y: 1158, w: 604, h: 226 }, hor: 430, q: [664, 64], plate: [20, 20, 480, 104], cap: [20, 140, 680],
  sun: { x0: 50, x1: 670, y0: 448, top: 290 }, pf: [540, 1010], size: 29,
  houses: { mouse: [168, 566, .86], snail: [360, 532, .9], owl: [558, 566, .86], squirrel: [92, 806, .9], rabbit: [628, 806, .9], frog: [196, 1006, .98], mole: [530, 1010, .98] },
};
const pf = (y) => lerp(.8, 1.1, clamp((y - K.pf[0]) / (K.pf[1] - K.pf[0]), 0, 1));
const HS = RES.map((r, i) => {
  const def = HOUSE[r.house], [x, y, s] = K.houses[r.id], m = x > K.hub[0] + 10 ? -1 : 1;
  const dx = x + m * def.doorX * s, side = Math.sign(K.hub[0] - dx) || 1;
  const spot = [dx + side * 58 * s, y + 18 * s];
  const b = def.box, box = m > 0 ? [x + b[0] * s, y + b[1] * s, x + b[2] * s, y + b[3] * s] : [x - b[2] * s, y + b[1] * s, x - b[0] * s, y + b[3] * s];
  const ax = x + m * def.anchor[0] * s, ay = y + def.anchor[1] * s, rs = s * def.rs;
  const fr = FRAME[r.id].head, head = r.id === 'mouse' ? [ax, ay - 6 * rs] : r.id === 'mole' ? [ax + m * 22 * rs, ay - 40 * rs] : [ax + m * fr[0] * rs, ay + fr[1] * rs];
  return { i, id: r.id, r, def, x, y, s, m, spot, box, ax, ay, rs, head, cx: (box[0] + box[2]) / 2, cy: (box[1] + box[3]) / 2 };
});
// тропинки-лучи от площади к каждой двери (чуть изогнутые); ёжик ходит только по ним
for (const h of HS) {
  const [x0, y0] = K.hub, [x1, y1] = h.spot, mx = (x0 + x1) / 2, my = (y0 + y1) / 2, L = Math.hypot(x1 - x0, y1 - y0), nx = -(y1 - y0) / L, ny = (x1 - x0) / L, b = L * .09 * (h.i % 2 ? 1 : -1);
  const cx = mx + nx * b, cy = my + ny * b, pts = [], cum = [0];
  for (let i = 0; i <= 24; i++) { const t = i / 24, u = 1 - t; pts.push([u * u * x0 + 2 * u * t * cx + t * t * x1, u * u * y0 + 2 * u * t * cy + t * t * y1]); if (i) cum.push(cum[i - 1] + Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1])); }
  h.path = { pts, cum, len: cum[24] };
}
function posOn(sp, d) {
  if (sp < 0) return [K.hub[0], K.hub[1]];
  const P = HS[sp].path; d = clamp(d, 0, P.len); let i = 1; while (i < 24 && P.cum[i] < d) i++;
  const t = (d - P.cum[i - 1]) / ((P.cum[i] - P.cum[i - 1]) || 1); return [lerp(P.pts[i - 1][0], P.pts[i][0], t), lerp(P.pts[i - 1][1], P.pts[i][1], t)];
}

/* ================= ёжик-почтальон ================= */
function hogDraw(c, o) {                         // o: carry, mood ('n'|'happy'|'puff'), step (-1|0|1), blink
  c.save(); c.scale(.6, .6); c.translate(-8, -72);
  const st = o.step || 0, puff = o.mood === 'puff';
  cut(c, E(-30 + st * 10, 62 - (st > 0 ? 7 : 0), 18, 10), '#6b4a3a', { blur: 3 });
  cut(c, E(36 - st * 10, 64 - (st < 0 ? 7 : 0), 18, 10), '#6b4a3a', { blur: 3 });
  { const p = new Path2D(), N = 34; for (let i = 0; i <= N; i++) { const a = PI * .62 + i / N * PI * 1.25, r = i % 2 ? (puff ? 1.04 : 1) : (puff ? 1.62 : 1.26); const px = -6 + Math.cos(a) * 92 * r, py = 6 + Math.sin(a) * 70 * r; i ? p.lineTo(px, py) : p.moveTo(px, py); }
    p.lineTo(40, 60); p.closePath(); cut(c, p, '#8d6248', { stain: '#5e3d2c', box: [-110, -80, 200, 150], n: 5, blur: 10 }); }
  pen(c, (q) => { for (let i = 0; i < 9; i++) { const a = PI * .75 + i * .2, r0 = 50, r1 = puff ? 84 : 74; q.moveTo(-6 + Math.cos(a) * r0, 6 + Math.sin(a) * r0 * .76); q.lineTo(-6 + Math.cos(a) * r1, 6 + Math.sin(a) * r1 * .76); } }, 2, 'rgba(255,230,200,.25)');
  { const p = new Path2D(); p.moveTo(6, -56); p.bezierCurveTo(60, -66, 96, -30, 126, -6); p.bezierCurveTo(134, 2, 128, 12, 116, 14); p.bezierCurveTo(90, 22, 70, 60, 20, 64); p.bezierCurveTo(-10, 40, -14, -30, 6, -56); p.closePath(); cut(c, p, '#f1d6b0', { stain: '#eac39b', box: [-10, 10, 60, 50], n: 1 }); }
  cut(c, E(126, 2, 10, 9), '#3e2b26', { blur: 2, sy: 1 }); dot(c, 123, -1, 2.6, 'rgba(255,255,255,.7)');
  if (o.mood === 'happy') pen(c, (q) => { q.moveTo(63, -14); q.quadraticCurveTo(72, -26, 81, -14); }, 3.2, '#3e2b26');
  else if (o.blink) pen(c, (q) => { q.moveTo(64, -16); q.quadraticCurveTo(72, -11, 80, -16); }, 3, '#3e2b26');
  else if (puff) { dot(c, 72, -17, 11, '#fffaf0'); dot(c, 73, -17, 6, '#3e2b26'); dot(c, 75, -19, 2, '#fff');
    pen(c, (q) => { q.moveTo(96, -70); q.lineTo(108, -92); q.moveTo(116, -56); q.lineTo(138, -70); q.moveTo(124, -36); q.lineTo(146, -38); }, 4, '#5a3f35');
    const d = new Path2D(); d.moveTo(40, -40); d.quadraticCurveTo(30, -24, 40, -18); d.quadraticCurveTo(50, -24, 40, -40); cut(c, d, '#9fcbea', { blur: 2, sy: 1 }); }
  else { c.fillStyle = '#3e2b26'; c.beginPath(); c.ellipse(72, -16, 6, 8, 0, 0, TAU); c.fill(); dot(c, 74, -19, 2.2, '#fff'); }
  pen(c, (q) => { q.moveTo(62, puff ? -40 : -34); q.quadraticCurveTo(72, puff ? -46 : -38, 82, puff ? -42 : -34); }, 2);
  wash(c, ellP(70, 10, 14, 8, 10), '#ee8f8f', { layers: 10, alpha: .1 });
  if (o.mood === 'happy') { const p = new Path2D(); p.moveTo(94, 16); p.quadraticCurveTo(104, 30, 114, 14); p.closePath(); c.fillStyle = '#7a3f3a'; c.fill(p); }
  else if (puff) { c.fillStyle = '#7a3f3a'; c.beginPath(); c.ellipse(104, 20, 4, 5, 0, 0, TAU); c.fill(); }
  else pen(c, (q) => { q.moveTo(96, 18); q.quadraticCurveTo(104, 24, 112, 16); }, 2);
  cut(c, E(26, -44, 10, 12, -.4), '#e3b98e', { blur: 2, sy: 1 });
  if (!o.noCap) hogCap(c);
  pen(c, (q) => { q.moveTo(10, -46); q.quadraticCurveTo(-30, 0, -56, 30); }, 7, '#a86b3c');
  for (const [dx, a] of [[-90, -.2], [-76, .1], [-58, -.05]]) { c.save(); c.translate(dx, 6); c.rotate(a); cut(c, new Path2D('M-12 -26h28v26h-28z'), '#fffaf0', { blur: 3, sy: 1 }); c.restore(); }
  { const p = new Path2D(); p.moveTo(-104, 4); p.lineTo(-34, 4); p.lineTo(-38, 56); p.quadraticCurveTo(-70, 64, -100, 56); p.closePath(); cut(c, p, '#e8b84a', { stain: '#c99230', box: [-104, 4, 70, 60], n: 2 }); }
  { const p = new Path2D(); p.moveTo(-106, 2); p.lineTo(-32, 2); p.lineTo(-40, 28); p.quadraticCurveTo(-70, 36, -98, 28); p.closePath(); cut(c, p, '#d9a23a', { blur: 3 }); }
  cut(c, E(-69, 26, 6, 6), '#4f79a8', { blur: 2, sy: 1 });
  if (o.carry) {
    c.save(); c.translate(150, -58); c.rotate(-.18);
    cut(c, new Path2D('M-46 -32h92v64h-92z'), '#fffaf0', { blur: 8, sy: 5 });
    pen(c, (q) => { q.moveTo(-46, -32); q.lineTo(0, 6); q.lineTo(46, -32); }, 1.6, '#b8a58e');
    cut(c, new Path2D('M14 -26h28v32h-28z'), '#f6d3c0', { blur: 2, sy: 1 });
    pen(c, (q) => { q.moveTo(-36, 14); q.lineTo(-6, 14); q.moveTo(-36, 22); q.lineTo(-16, 22); }, 1.4, '#b8a58e');
    c.restore();
    cut(c, E(112, -42, 13, 11, -.5), '#e3b98e', { blur: 3 });
  } else cut(c, E(70, 44, 13, 11, .3), '#e3b98e', { blur: 3 });
  c.restore();
}
function hogCap(c) {
  { const p = new Path2D(); p.moveTo(2, -62); p.bezierCurveTo(6, -110, 80, -112, 88, -66); p.closePath(); cut(c, p, '#4f79a8', { stain: '#355d8c', box: [0, -110, 90, 50], n: 2 }); }
  { const p = new Path2D(); p.moveTo(60, -66); p.quadraticCurveTo(100, -74, 118, -58); p.quadraticCurveTo(96, -56, 60, -58); p.closePath(); cut(c, p, '#2f4f78', { blur: 3 }); }
  cut(c, new Path2D('M36 -92h18v12h-18z'), '#f3c95a', { blur: 2, sy: 1 }); pen(c, (q) => { q.moveTo(36, -92); q.lineTo(45, -85); q.lineTo(54, -92); }, 1.2, '#b07a55');
}
function hogBall(c) {                            // клубок: ёжик катится, когда идти далеко
  c.save(); c.scale(.6, .6);
  const p = new Path2D(), N = 44; for (let i = 0; i <= N; i++) { const a = i / N * TAU, r = i % 2 ? 60 : 80; i ? p.lineTo(Math.cos(a) * r, Math.sin(a) * r) : p.moveTo(Math.cos(a) * r, Math.sin(a) * r); }
  p.closePath(); cut(c, p, '#8d6248', { stain: '#5e3d2c', box: [-80, -80, 160, 160], n: 5, blur: 8 });
  pen(c, (q) => { for (let i = 0; i < 12; i++) { const a = i / 12 * TAU; q.moveTo(Math.cos(a) * 30, Math.sin(a) * 30); q.lineTo(Math.cos(a) * 66, Math.sin(a) * 66); } }, 2.2, 'rgba(255,230,200,.25)');
  cut(c, E(10, 26, 26, 18, .3), '#e8b84a', { blur: 3 }); cut(c, E(28, -8, 10, 9), '#f1d6b0', { blur: 2 });
  c.restore();
}

/* ================= марки и письмо ================= */
const KIND = { p: { bg: '#f6d3c0', name: 'портрет' }, s: { bg: '#dbe9d3', name: 'силуэт' }, d: { bg: '#d5e3ef', name: 'примета' }, r: { bg: '#f6e7b0', name: 'загадка' } };
function stampArt(c, who, kind, x, y, w, h) {
  c.save(); c.beginPath(); c.rect(x, y, w, h); c.clip();
  c.fillStyle = KIND[kind].bg; c.fillRect(x, y, w, h);
  const cx = x + w / 2, cy = y + h / 2;
  if (kind === 'p' || kind === 's') {
    const fr = FRAME[who][kind], z = Math.min(w, h) * .5 / fr[2];
    if (kind === 'p') { wash(c, ellP(cx, cy + h * .1, w * .38, h * .3, 12), '#f0b8a0', { layers: 6, alpha: .1 }); c.save(); c.translate(cx, cy); c.scale(z, z); c.translate(-fr[0], -fr[1]); FIG[who](c, { eyes: who === 'owl' ? 'sleep' : 'open', mood: 'idle' }); c.restore(); }
    else {
      lift(c, ellP(cx, cy - h * .05, w * .36, w * .36, 14), { n: 6, a: .2, col: '#f4f8ee' });
      const d = sk(c), tmp = document.createElement('canvas'); tmp.width = Math.ceil(w * d); tmp.height = Math.ceil(h * d);
      const t = tmp.getContext('2d'); t.scale(d, d); t.translate(w / 2, h / 2); t.scale(z * .92, z * .92); t.translate(-fr[0], -fr[1]); FIG[who](t, { eyes: 'open', mood: 'idle' });
      t.setTransform(1, 0, 0, 1, 0, 0); t.globalCompositeOperation = 'source-in'; t.fillStyle = '#4a3946'; t.fillRect(0, 0, tmp.width, tmp.height);
      c.drawImage(tmp, x, y, w, h);
    }
  } else if (kind === 'd') { const z = Math.min(w, h) * .5 / 54; c.save(); c.translate(cx, cy); c.scale(z, z); DETAIL[who](c); c.restore(); }
  else { const z = Math.min(w, h) * .5 / 46; c.save(); c.translate(cx, cy); c.scale(z, z); ITEM[RBY[who].rebus](c); c.restore(); }
  c.restore();
}
function stamp(c, who, kind, x, y, w, h) {
  cut(c, new Path2D(`M${x} ${y}h${w}v${h}h${-w}z`), '#fff7ea', { blur: 3, sy: 2 });
  const r = Math.max(2.6, w * .024), st = r * 2.6;
  c.fillStyle = CARDC;
  for (let X = x; X <= x + w + .1; X += w / Math.round(w / st)) { dot(c, X, y, r, CARDC); dot(c, X, y + h, r, CARDC); }
  for (let Y = y; Y <= y + h + .1; Y += h / Math.round(h / st)) { dot(c, x, Y, r, CARDC); dot(c, x + w, Y, r, CARDC); }
  const m = w * .085; stampArt(c, who, kind, x + m, y + m, w - m * 2, h - m * 2);
  pen(c, (q) => q.rect(x + m, y + m, w - m * 2, h - m * 2), 1, 'rgba(90,63,53,.25)');
}
const plural = (n, a, b, c5) => { const m10 = n % 10, m100 = n % 100; return m10 === 1 && m100 !== 11 ? a : m10 >= 2 && m10 <= 4 && (m100 < 10 || m100 >= 20) ? b : c5; };
function cardSpr(L, left) {
  const { w, h } = K.card;
  return spr('card:' + L.who + L.kind + left + (FONTS ? 'f' : 'n'), [-w / 2 - 24, -h / 2 - 24, w / 2 + 24, h / 2 + 30], 1, (c) => {
    cut(c, new Path2D(`M${-w / 2} ${-h / 2}h${w}v${h}h${-w}z`), CARDC, { blur: 12, sy: 6 });
    wash(c, [[-w / 2, -h / 2], [w / 2, -h / 2], [w / 2, h / 2], [-w / 2, h / 2]], '#f3e6cc', { layers: 4, alpha: .05, v0: .05, v: .05 });
    pen(c, (q) => { q.moveTo(-w / 2 + 2, -h / 2 + 2); q.lineTo(-w * .12, h * .06); q.lineTo(w * .16, -h * .14); }, 1.6, '#d8c7ab');
    const sh = h - (LAND ? 40 : 44), sw = sh * .86, sx = w / 2 - (LAND ? 22 : 26) - sw, sy = -h / 2 + (LAND ? 18 : 20);
    // штемпель
    pen(c, (q) => { q.arc(sx - 6, sy + sh * .62, sh * .26, 0, TAU); for (let i = 0; i < 3; i++) { const yy = sy + sh * .5 + i * 9; q.moveTo(sx - sh * .7, yy); q.bezierCurveTo(sx - sh * .55, yy - 6, sx - sh * .4, yy + 6, sx - sh * .22, yy); } }, 1.6, 'rgba(90,63,53,.25)');
    stamp(c, L.who, L.kind, sx, sy, sw, sh);
    const fs = LAND ? 34 : 40, lx = -w / 2 + (LAND ? 24 : 30);
    txt(c, 'Кому?', lx, -h / 2 + (LAND ? 74 : 82), fs, LINE, 700);
    pen(c, (q) => { q.moveTo(lx, -h / 2 + (LAND ? 92 : 102)); q.lineTo(sx - (LAND ? 70 : 90), -h / 2 + (LAND ? 92 : 102)); q.moveTo(lx, -h / 2 + (LAND ? 116 : 130)); q.lineTo(sx - (LAND ? 90 : 120), -h / 2 + (LAND ? 116 : 130)); }, 1.4, '#d8c7ab');
    const s2 = LAND ? 21 : 25, room = sx - lx - 14;
    let t2 = left > 0 ? 'в сумке ещё ' + left + ' ' + plural(left, 'письмо', 'письма', 'писем') : 'последнее письмо дня';
    if (tw(t2, s2) > room) t2 = left > 0 ? 'в сумке ещё ' + left : 'последнее письмо';
    txt(c, t2, lx, h / 2 - (LAND ? 22 : 26), s2, MUTE, 600);
  });
}
function envIcon(c, x, y, w, state) {           // маленький конверт: 0 — в сумке, 1 — доставлено, 2 — не успели
  const h = w * .68, p = new Path2D(`M${x - w / 2} ${y - h / 2}h${w}v${h}h${-w}z`);
  if (state === 1) { cut(c, p, '#fffaf0', { blur: 2, sy: 1 }); pen(c, (q) => { q.moveTo(x - w / 2, y - h / 2); q.lineTo(x, y + h * .05); q.lineTo(x + w / 2, y - h / 2); }, 1.2, '#c9b79e'); pen(c, (q) => { q.moveTo(x - w * .2, y + h * .1); q.lineTo(x - w * .02, y + h * .32); q.lineTo(x + w * .3, y - h * .2); }, 2.6, '#6e9c63'); }
  else if (state === 2) { c.fillStyle = 'rgba(90,63,53,.12)'; c.fill(p); }
  else { pen(c, (q) => { q.rect(x - w / 2, y - h / 2, w, h); q.moveTo(x - w / 2, y - h / 2); q.lineTo(x, y + h * .05); q.lineTo(x + w / 2, y - h / 2); }, 1.6, 'rgba(90,63,53,.45)'); }
}

/* ================= фон: небо и земля с домами — один раз ================= */
let BG = null;
function grain(cv, amt) {
  const x = cv.getContext('2d'), id = x.getImageData(0, 0, cv.width, cv.height), d = id.data, w = cv.width;
  for (let i = 0, p = 0; i < d.length; i += 4, p++) { if (!d[i + 3]) continue; const X = p % w, Y = (p / w) | 0; const n = (Math.random() - .5) * amt + Math.sin(X * .9 + Y * .3) * 1.5 + ((X * 7 + Y * 13) % 17 === 0 ? -5 : 0); d[i] += n; d[i + 1] += n; d[i + 2] += n * .9; }
  x.putImageData(id, 0, 0);
}
function makeBG() {
  const mk = (fn) => { const cv = document.createElement('canvas'); cv.width = Math.round(W * CS); cv.height = Math.round(H * CS); const x = cv.getContext('2d'); x.scale(CS, CS); fn(x); return cv; };
  const hor = K.hor;
  reseed('sky');
  const sky = mk((c) => {
    c.fillStyle = PAPER; c.fillRect(0, 0, W, H);
    wash(c, [[-40, -40], [W + 40, -40], [W + 40, hor - 40], [W * .7, hor - 10], [W * .3, hor - 28], [-40, hor]], '#9fcbea', { layers: 14, alpha: .032 });
    wash(c, [[-40, -40], [W + 40, -40], [W + 40, hor * .38], [W * .55, hor * .48], [-40, hor * .42]], '#8dbfe2', { layers: 10, alpha: .03 });
    wash(c, [[-40, hor - 10], [W * .3, hor - 26], [W * .7, hor - 16], [W + 40, hor - 30], [W + 40, hor + 70], [-40, hor + 80]], '#fbcfae', { layers: 10, alpha: .035 });
  });
  grain(sky, 13);
  reseed('land');
  const land = mk((c) => {
    // земля — непрозрачная основа ниже гребня холмов: за ней садится солнце
    const ridge = (x) => hor - 22 - Math.sin(x * .006 + 1) * 18 - Math.sin(x * .017 + 2) * 7;
    c.fillStyle = PAPER; c.beginPath(); c.moveTo(-10, H + 10); for (let x = -10; x <= W + 10; x += 10) c.lineTo(x, ridge(x)); c.lineTo(W + 10, H + 10); c.fill();
    const band = (y0, amp, f, ph, col, depth, o) => { const top = [], bot = []; for (let x = -60; x <= W + 60; x += 40) { const y = y0 - Math.sin(x * f + ph) * amp - Math.sin(x * f * 2.3 + ph * 2) * amp * .3; top.push([x, y]); bot.push([x, y + depth + Math.sin(x * .01 + ph) * 20]); } wash(c, [...top, ...bot.reverse()], col, o || { layers: 12, alpha: .04 }); };
    { const top = [], bot = []; for (let x = -60; x <= W + 60; x += 30) { top.push([x, ridge(x)]); bot.push([x, hor + 60]); } wash(c, [...top, ...bot.reverse()], '#a8cbd0', { layers: 12, alpha: .045 }); }
    // деревья за деревней
    const trees = LAND ? [[40, 0, 34], [210, 8, 26], [520, -6, 30], [770, -4, 26], [1060, 6, 32], [1250, 0, 28], [300, 10, 22], [960, 12, 20]] : [[30, 0, 30], [200, 6, 24], [470, 2, 26], [690, 0, 30], [600, 10, 20]];
    for (const [x, dy, r] of trees) { const y = hor + dy; wash(c, [[x - 3, y + 24], [x + 3, y + 24], [x + 3, y - 4], [x - 3, y - 4]], '#a0806a', { layers: 6, alpha: .1, m: 12 }); wash(c, ellP(x, y - r * .7, r, r * 1.05, 14), A.pick(['#8cc07c', '#97c487', '#86bb78']), { layers: 12, alpha: .055, m: 20 }); }
    band(hor + 40, 22, .006, 3, '#a9d48e', LAND ? 170 : 220, { layers: 12, alpha: .045 });
    band(hor + 120, 22, .005, 5, '#95c97c', LAND ? 200 : 300, { layers: 12, alpha: .045 });
    if (!LAND) band(820, 20, .007, 1, '#9dcd84', 260, { layers: 12, alpha: .045 });
    band(H - (LAND ? 140 : 280), 18, .008, 2, '#86bd70', LAND ? 160 : 300, { layers: 12, alpha: .045 });
    band(H - (LAND ? 40 : 90), 10, .01, 4, '#8cc276', 120, { layers: 10, alpha: .045 });
    for (let i = 0; i < (LAND ? 90 : 110); i++) { const x = rnd() * W, y = hor + 40 + rnd() * (H - hor - 40); c.save(); c.globalAlpha = .3; c.strokeStyle = '#5f8f52'; c.lineWidth = 1.4; c.beginPath(); c.moveTo(x, y); c.quadraticCurveTo(x + 2, y - 6, x + (rnd() - .5) * 6, y - 12); c.stroke(); c.restore(); }
    // круглая площадь и тропинки-лучи
    const [hx, hy] = K.hub, ps = pf(hy);
    for (const h of HS) {
      const P = h.path.pts, L = [], R = [];
      for (let i = 0; i < P.length; i++) { const a = P[Math.max(0, i - 1)], b = P[Math.min(P.length - 1, i + 1)], len = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1, nx = -(b[1] - a[1]) / len, ny = (b[0] - a[0]) / len, wd = 17 * pf(P[i][1]); L.push([P[i][0] + nx * wd, P[i][1] + ny * wd * .7]); R.push([P[i][0] - nx * wd, P[i][1] - ny * wd * .7]); }
      lift(c, [...L, ...R.reverse()], { n: 6, a: .16 });
    }
    lift(c, ellP(hx, hy + 8, 150 * ps, 56 * ps, 22), { n: 8, a: .18 });
    for (const h of HS) {
      const P = h.path.pts, L = [], R = [];
      for (let i = 0; i < P.length; i++) { const a = P[Math.max(0, i - 1)], b = P[Math.min(P.length - 1, i + 1)], len = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1, nx = -(b[1] - a[1]) / len, ny = (b[0] - a[0]) / len, wd = 15 * pf(P[i][1]); L.push([P[i][0] + nx * wd, P[i][1] + ny * wd * .7]); R.push([P[i][0] - nx * wd, P[i][1] - ny * wd * .7]); }
      wash(c, [...L, ...R.reverse()], '#f3cf96', { layers: 10, alpha: .05, m: 24 });
      wash(c, ellP(h.spot[0], h.spot[1] - 4, 44 * h.s, 15 * h.s, 14), '#f3cf96', { layers: 8, alpha: .06 });
    }
    wash(c, ellP(hx, hy + 8, 140 * ps, 50 * ps, 22), '#f3cf96', { layers: 10, alpha: .045, m: 24 });
    pen(c, (q) => q.ellipse(hx, hy + 8, 112 * ps, 38 * ps, 0, 0, TAU), 1.4, 'rgba(176,122,85,.25)');
    // почтовый ящик ёжика на площади
    c.save(); c.translate(hx - 118 * ps, hy - 6); c.scale(ps, ps);
    wash(c, ellP(4, 2, 30, 7, 10), '#5f8a58', { layers: 6, alpha: .07 });
    cut(c, rrp(-18, -66, 36, 66, 10), '#4f79a8', { stain: '#355d8c', box: [-18, -66, 36, 66], n: 2 }); cut(c, E(0, -66, 20, 9), '#3d6894', { blur: 3 });
    c.fillStyle = '#23384f'; c.fillRect(-11, -52, 22, 4);
    cut(c, E(0, -30, 9, 9), '#f3c95a', { blur: 2, sy: 1 }); pen(c, (q) => { q.moveTo(-5, -30); q.quadraticCurveTo(0, -36, 5, -30); }, 1.4, '#b07a55');
    cut(c, rrp(-21, -6, 42, 7, 3), '#355d8c', { blur: 2, sy: 1 });
    c.restore();
    // дома (по глубине)
    for (const h of [...HS].sort((a, b) => a.y - b.y)) {
      c.save(); c.translate(h.x, h.y); c.scale(h.m * h.s, h.s);
      wash(c, ellP(0, 2, 110, 14, 14), '#5f8a58', { layers: 8, alpha: .06 });
      reseed('house:' + h.id); h.def.draw(c); c.restore();
    }
    // цветы
    const fl = LAND ? [[40, 640], [86, 668], [150, 706], [420, 712], [870, 708], [1140, 600], [1196, 640], [1250, 690], [520, 420], [780, 410], [36, 380], [1240, 380], [470, 260 + 140]]
      : [[30, 960], [60, 1236], [670, 1220], [690, 960], [40, 700], [690, 700], [300, 660], [440, 670], [130, 1110], [600, 1100]];
    const cols = ['#e98a8a', '#f3c95a', '#b9a2d8', '#fff6e6', '#e98a8a'];
    for (const [x, y] of fl) { const col = A.pick(cols), s = pf(y) * .9; pen(c, (q) => { q.moveTo(x, y); q.quadraticCurveTo(x + 4, y + 16 * s, x, y + 32 * s); }, 2.2, '#6e9c63'); for (let i = 0; i < 5; i++) { const a = i / 5 * TAU; cut(c, E(x + Math.cos(a) * 8 * s, y + Math.sin(a) * 8 * s, 7 * s, 7 * s), col, { blur: 2, sy: 1 }); } cut(c, E(x, y, 5 * s, 5 * s), '#f3c95a', { blur: 1, sy: 1 }); }
  });
  grain(land, 13);
  BG = { sky, land };
}

/* ================= звук ================= */
const now = () => SND.now();
const snd = {
  knock() { if (!SND.ctx) return; const t = now(); for (const d of [0, .17]) { SND.tone(190, t + d, .09, .2, 'sine', null, 120); SND.hiss(t + d, .05, .07, 'lowpass', 900); } },
  paper() { if (!SND.ctx) return; SND.hiss(now(), .16, .05, 'bandpass', 2600); },
  roll() { if (!SND.ctx) return; const t = now(); SND.hiss(t, .5, .035, 'lowpass', 500); SND.tone(90, t, .4, .05, 'sine', null, 70); },
  pop() { if (!SND.ctx) return; SND.tone(520, now(), .08, .07, 'sine', null, 820); },
  yes() { if (!SND.ctx) return; const t = now(); [784, 988, 1175, 1568].forEach((f, i) => { SND.tone(f, t + i * .07, .4, .055, 'triangle'); SND.tone(f * 2, t + i * .07, .2, .012, 'sine'); }); },
  no() { if (!SND.ctx) return; const t = now(); SND.tone(330, t, .22, .09, 'sine', null, 190); SND.tone(250, t + .14, .3, .07, 'triangle', null, 150); },
  gift() { if (!SND.ctx) return; const t = now(); SND.tone(1319, t, .25, .05, 'sine'); SND.tone(1760, t + .09, .3, .04, 'sine'); },
  hint() { if (!SND.ctx) return; const t = now(); SND.tone(880, t, .3, .04, 'sine'); SND.tone(1320, t + .1, .35, .03, 'sine'); },
  dusk() { if (!SND.ctx) return; const t = now(); [392, 494, 587, 784].forEach((f, i) => SND.tone(f, t + i * .18, 1.6, .05, 'sine')); },
  dawn() { if (!SND.ctx) return; const t = now(); [523, 659, 784, 1047, 1319].forEach((f, i) => SND.tone(f, t + i * .09, .6, .045, 'triangle')); },
  voice(id, ok) {
    if (!SND.ctx) return; const t = now(), k = ok ? 1 : .8;
    if (id === 'mouse') { SND.tone(1900 * k, t, .07, .05, 'sine', null, 2400 * k); SND.tone(2100 * k, t + .1, .08, .05, 'sine', null, 2600 * k); }
    else if (id === 'snail') { SND.tone(330 * k, t, .6, .06, 'sine', null, 280 * k, .1); }
    else if (id === 'owl') { SND.tone(392 * k, t, .3, .08, 'sine', null, 360, .05); SND.tone(330 * k, t + .34, .45, .08, 'sine', null, 300, .05); }
    else if (id === 'frog') { SND.tone(140 * k, t, .14, .1, 'triangle', null, 100); SND.tone(150 * k, t + .18, .16, .1, 'triangle', null, 96); }
    else if (id === 'rabbit') { for (let i = 0; i < 3; i++) SND.tone(900 * k + i * 80, t + i * .06, .05, .04, 'sine'); }
    else if (id === 'squirrel') { for (let i = 0; i < 6; i++) SND.tone(2300 * k + Math.random() * 500, t + i * .045, .03, .035, 'square'); }
    else if (id === 'mole') { SND.tone(200 * k, t, .3, .07, 'triangle', null, 170 * k, .05); }
  },
};

/* ================= дни ================= */
const TAPW = A.isTouch ? 'Нажми на его дом или смахни письмо к нему.' : 'Щёлкни по его дому — ёжик отнесёт.';
const DAYS = [
  { name: 'Портреты', kinds: 'pppppp', len: 80, rule: 'Адреса нет — на марке нарисован получатель. ' + TAPW + ' Успей до заката!', idle: 'Посмотри на марку: кто на ней? Найди его в деревне.', next: 'Завтра на марках будут только тени — силуэты жителей.' },
  { name: 'Силуэты', kinds: 'sssssp', len: 80, rule: 'Сегодня на марках только тени. Чьи это уши, хвост, колпак?', idle: 'Сравни тень на марке с жителями: уши, хвост, панцирь…', next: 'Завтра — приметы: на марке одна деталь. Присмотрись к жителям!' },
  { name: 'Приметы', kinds: 'ddddsssd', len: 92, rule: 'На марке одна примета: колпак, хвост, очки, бантик… Чья она?', idle: 'Кто носит такую вещь? Посмотри на жителей поближе.', next: 'Завтра — загадки: на марке любимая вещь жителя. Запомни подарки!' },
  { name: 'Загадки', kinds: 'rrrrrddr', len: 96, rule: 'На марке — любимая вещь жителя. Вспомни подарки и что лежит у домов.', idle: 'Такие вещи лежат у домов и бывают в подарках. Чья эта?', next: '' },
];

/* ================= состояние ================= */
let S = null, GAME = null;
const hog = { sp: -1, d: 0, x: K.hub[0], y: K.hub[1], legs: [], roll: false, rot: 0, face: 1, ph: 0, carry: false, mood: 'n', moodT: 0, blink: 2, pop: 0, then: null, capY: 0 };
function fresh(mode) {
  S = { mode, day: 0, st: 'idle', t: 0, sun: .28, letters: [], li: 0, cur: null, marks: [], score: 0, mistakes: 0, delivered: 0, total: 0, gifts: 0, giftKinds: {}, perDay: [],
    cardK: 0, cardT: 0, drag: null, pd: null, target: -1, hover: -1, focus: -1, kb: false, idle: 0, help: false, cap: null, warned: false, sunset: false,
    rt: 0, bub: null, timers: [], flights: [], parts: [], leaves: [], hudBump: 0, tint: 0, dusk: 0, spd: 1, res: {}, banner: null, steam: 0, drops: 0 };
  for (const r of RES) S.res[r.id] = { blink: 1 + Math.random() * 4, anim: null };
  Object.assign(hog, { sp: -1, d: 0, x: K.hub[0], y: K.hub[1], legs: [], roll: false, face: 1, carry: false, mood: 'n', moodT: 0, pop: 0, then: null });
  S.hs = HS.map((h) => ({ id: h.id, x: Math.round(h.cx), y: Math.round(h.cy), box: h.box.map(Math.round), spot: h.spot.map(Math.round) }));
  S.cardAt = [K.card.x, K.card.y];
}
function startDay(d) {
  const D = DAYS[d];
  S.day = d; S.mode = 'play'; S.st = 'idle'; S.sun = 0; S.t = 0; S.li = 0; S.warned = false; S.sunset = false; S.dusk = 0;
  const kinds = [D.kinds[0], ...shuffle(D.kinds.slice(1).split(''))], pool = [];
  while (pool.length < kinds.length) { const add = shuffle(RES.map((r) => r.id)); if (pool.length && add[0] === pool[pool.length - 1]) add.push(add.shift()); pool.push(...add); }
  S.letters = kinds.map((k, i) => ({ who: pool[i], kind: k, tries: 0 }));
  S.marks = S.letters.map(() => 0);
  Object.assign(hog, { sp: -1, d: 0, legs: [], roll: false, carry: false, mood: 'n', then: null });
  S.banner = { t: 0, text: 'День ' + (d + 1) + ' · ' + D.name };
  snd.dawn();
  later(1.9, () => { if (S.mode === 'play' && S.day === d) { say(D.rule, 7); nextLetter(); } });
}
function nextLetter() {
  if (S.mode !== 'play') return;
  if (S.li >= S.letters.length || S.sunset || S.sun >= 1) { endDay(); return; }
  S.cur = S.letters[S.li]; S.st = 'choose'; S.cardK = 0; S.cardT = 0; S.idle = 0; S.help = false; S.focus = -1;
  snd.paper();
}
function say(text, sec = 6) { S.cap = { text, t: 0, life: sec }; }
function choose(h) {
  if (S.mode !== 'play' || S.st !== 'choose' || h < 0) return;
  S.st = 'go'; S.target = h; S.drag = null; S.idle = 0; hog.carry = true; hog.mood = 'n';
  route(h, () => arrive(h)); snd.paper();
}
function route(h, then) {
  hog.legs = [];
  if (h < 0) { if (hog.sp >= 0) hog.legs.push({ sp: hog.sp, to: 0 }); }
  else { if (hog.sp >= 0 && hog.sp !== h) hog.legs.push({ sp: hog.sp, to: 0 }); hog.legs.push({ sp: h, to: HS[h].path.len }); }
  let dist = 0, d = hog.d, sp = hog.sp; for (const L of hog.legs) { if (sp !== L.sp) { sp = L.sp; d = 0; } dist += Math.abs(L.to - d); d = L.to; }
  hog.then = then || null;
  if (!hog.legs.length) { const f = hog.then; hog.then = null; if (f) f(); return; }
  hog.roll = dist > 150; if (hog.roll) snd.roll();
}
function arrive(h) {
  const H0 = HS[h], R = H0.r, ok = S.cur && S.cur.who === R.id;
  hog.face = Math.sign(H0.head[0] - hog.x) || hog.face;
  S.st = 'react'; S.rt = 0; snd.knock();
  later(.38, () => {
    if (S.mode !== 'play') return;
    S.res[R.id].anim = { ok, t: 0 }; snd.voice(R.id, ok);
    S.bub = { h, text: ok ? R.yes : R.no[S.cur.tries % 2], t: 0, life: ok ? 1.8 : 1.7 };
    if (ok) {
      snd.yes(); hog.mood = 'happy'; hog.moodT = 1.4; hog.carry = false;
      const pts = (S.cur.tries ? 10 : 15); S.score += pts; S.delivered++; S.marks[S.li] = 1;
      S.flights.push({ k: 'env', x0: hog.x + hog.face * 50 * pf(hog.y), y0: hog.y - 60 * pf(hog.y), x1: H0.head[0], y1: H0.head[1], t: 0, dur: .35 });
      S.flights.push({ k: R.gift, x0: H0.head[0], y0: H0.head[1], x1: K.plate[0] + K.plate[2] - 52, y1: K.plate[1] + K.plate[3] - 30, t: -.45, dur: .8, land() { S.gifts++; S.giftKinds[R.gift] = (S.giftKinds[R.gift] || 0) + 1; S.hudBump = 1; snd.gift(); } });
      S.parts.push({ k: 'txt', x: H0.head[0] - (H0.head[0] < W / 2 ? 1 : -1) * 46 * H0.rs, y: H0.head[1] - 46 * H0.rs, s: '+' + pts, t: 0, life: 1.4 });
      confetti(H0.head[0], H0.head[1] - 10);
    } else {
      snd.no(); S.cur.tries++; S.mistakes++; hog.mood = 'puff'; hog.moodT = 1.5;
      S.parts.push({ k: 'txt', x: H0.head[0] - (H0.head[0] < W / 2 ? 1 : -1) * 40 * H0.rs, y: H0.head[1] - 46 * H0.rs, s: '?!', t: 0, life: 1.4 });
    }
    later(ok ? 1.25 : 1.15, () => {
      if (S.mode !== 'play') return;
      if (ok) { S.li++; S.cur = null; route(-1, () => { hog.face = 1; }); nextLetter(); }
      else { S.st = 'choose'; S.cardK = 0; S.cardT = 0; S.idle = 0; S.focus = -1; if (S.sunset || S.sun >= 1) endDay(); }
    });
  });
}
function later(sec, fn) { S.timers.push({ t: sec, fn }); }
function confetti(x, y) {
  const cols = ['#e2665c', '#f3c95a', '#7fb069', '#7f9fc0', '#f0a98a', '#b9a2d8'];
  for (let i = 0; i < 18; i++) { const a = -PI / 2 + (Math.random() - .5) * 2.2, v = 160 + Math.random() * 220; S.parts.push({ k: 'bit', x, y, vx: Math.cos(a) * v, vy: Math.sin(a) * v, rot: Math.random() * 6, vr: (Math.random() - .5) * 12, col: A.pick(cols), t: 0, life: 1 + Math.random() * .5, w: 6 + Math.random() * 5, h: 4 + Math.random() * 3 }); }
}
function endDay() {
  if (S.st === 'dusk' || S.mode !== 'play') return;
  S.st = 'dusk'; S.dusk = 0; S.cur && (S.cur = null); S.drag = null; S.bub = null; S.cap = null;
  for (let i = 0; i < S.marks.length; i++) if (!S.marks[i]) S.marks[i] = 2;
  hog.carry = false; route(-1, () => { hog.face = 1; });
  snd.dusk();
}
function dayScreen() {
  const g = GAME, d = S.day, D = DAYS[d], n = S.letters.length, got = S.marks.filter((m) => m === 1).length;
  const mist = S.letters.reduce((a, L) => a + L.tries, 0), bonus = got === n ? Math.round((1 - clamp(S.sun, 0, 1)) * 40) + 10 : 0;
  S.score += bonus; S.total += n; S.perDay.push({ got, n, mist });
  S.mode = 'screen'; g.setPlaying(false); g.stopMusic();
  const last = d === DAYS.length - 1;
  if (last) { finish(); return; }
  const head = got === n ? (mist ? 'Все письма дошли!' : 'Ни одной ошибки!') : 'Солнце село';
  g.screen({ kicker: 'Вечер · день ' + (d + 1) + ' из ' + DAYS.length, title: head,
    html: '<p' + PS + '>Доставлено <b>' + got + ' из ' + n + '</b>' + (mist ? ' · ошибок: ' + mist : '') + (bonus ? ' · за солнце +' + bonus : '') + '</p><p' + PS2 + '>' + D.next + '</p>',
    button: 'Утро!', onGo: () => { g.setPlaying(true); g.playMusic(); startDay(d + 1); }, keys: '' });
}
function finish() {
  const g = GAME, rec = g.submit(S.score);
  S.mode = 'end';
  const gl = Object.entries(S.giftKinds).map(([k, v]) => (RES.find((r) => r.gift === k).gname) + (v > 1 ? ' ×' + v : '')).join(', ');
  g.screen({ kicker: 'Колючая почта · четыре дня', title: S.delivered === S.total ? 'Все письма дома!' : 'Почта разнесена',
    html: '<p class="score" style="color:#5a3f35">' + S.score + '</p>' + (rec ? '<p class="record" style="color:#c0662a">Новый рекорд!</p>' : '<p' + PS2 + '>Рекорд: ' + g.best + '</p>') +
      '<p' + PS + '>Писем доставлено: <b>' + S.delivered + ' из ' + S.total + '</b> · ошибок: ' + S.mistakes + '</p>' + (gl ? '<p' + PS2 + '>Подарки в сумке: ' + gl + '.</p>' : ''),
    button: 'Ещё раз', onGo: () => newGame(g), alt: { label: A.framed ? 'К играм' : 'В аркаду', onGo: () => A.home('../index.html') }, keys: '' });
}
const PS = ' style="color:#5b4a42"', PS2 = ' style="color:#7a6a60"';
function newGame(g) { fresh('play'); g.fx.clear(); g.setPlaying(true); g.playMusic(); startDay(0); }
function titleScreen(g) {
  fresh('title'); g.setPlaying(false);
  g.screen({ kicker: A.framed ? 'Досуг' : 'Аркада', title: 'Колючая почта',
    html: '<p style="color:#5b4a42">Ёжик-почтальон разносит письма, но адресов на них нет — на марке нарисован тот, кому письмо.</p><p style="color:#5b4a42"><b>Посмотри на марку и отнеси письмо этому жителю.</b></p><p style="color:#7a6a60">Успей до заката. Четыре дня — и марки всё хитрее.</p>',
    button: 'Начать', onGo: () => newGame(g) });
}

/* ================= выбор дома: щелчок, касание, смахивание, клавиши ================= */
function hitHouse(x, y) {
  let best = -1, bd = 1e9;
  for (const h of HS) { const [x0, y0, x1, y1] = h.box; if (x >= x0 - 6 && x <= x1 + 6 && y >= y0 - 6 && y <= y1 + 20) { const d = Math.hypot(x - h.cx, y - h.cy); if (d < bd) { bd = d; best = h.i; } } }
  return best;
}
function cardRect() { const { x, y, w, h } = K.card; return [x - w / 2 - 10, y - h / 2 - 10, x + w / 2 + 10, y + h / 2 + 10]; }
const inRect = (r, x, y) => x >= r[0] && x <= r[2] && y >= r[1] && y <= r[3];
function pickSwipe(sx, sy, ex, ey) {
  const vx = ex - sx, vy = ey - sy, L = Math.hypot(vx, vy); if (L < 36) return -1;
  const on = hitHouse(ex, ey); if (on >= 0) return on;
  let best = -1, bs = 1e9;
  for (const h of HS) { const wx = h.cx - sx, wy = (h.y - 60 * h.s) - sy, wl = Math.hypot(wx, wy) || 1; const ang = Math.acos(clamp((vx * wx + vy * wy) / (L * wl), -1, 1)) * 180 / PI; const sc = ang + Math.hypot(ex - h.cx, ey - h.cy) / 40; if (ang < 40 && sc < bs) { bs = sc; best = h.i; } }
  return best;
}
const ORDER = [...HS].sort((a, b) => { const an = (h) => { let v = Math.atan2(h.cy - K.hub[1], h.cx - K.hub[0]); if (v > PI * .5) v -= TAU; return v; }; return an(a) - an(b); }).map((h) => h.i);
const QR = LAND ? 26 : 32;
function input(g) {
  const inp = g.input, p = inp.pointer;
  if (inp.pressed('hint')) giveHint();
  if (S.mode !== 'play') return;
  const can = S.st === 'choose';
  // клавиатура
  const mv = inp.pressed('left') || inp.pressed('up') ? -1 : inp.pressed('right') || inp.pressed('down') ? 1 : 0;
  if (mv && can) { S.kb = true; S.idle = 0; const k = ORDER.indexOf(S.focus); S.focus = ORDER[((k < 0 ? (mv > 0 ? -1 : 0) : k) + mv + ORDER.length) % ORDER.length]; snd.pop(); }
  if ((inp.pressed('start') || inp.pressed('action')) && can) { if (S.focus >= 0) choose(S.focus); else { S.kb = true; S.focus = ORDER[0]; say(A.isTouch ? 'Нажми на дом того, кто на марке.' : 'Стрелками выбери дом, Enter — вручить письмо.', 4); } }
  // мышь: подсветка дома под указателем
  if (inp.mouseActive && !p.down) { const h = hitHouse(p.x, p.y); S.hover = h; const over = h >= 0 || Math.hypot(p.x - K.q[0], p.y - K.q[1]) < QR + 6 || (can && inRect(cardRect(), p.x, p.y)); g.canvas.style.cursor = over ? 'pointer' : ''; } else if (!inp.mouseActive) S.hover = -1;
  // касание / щелчок / перетаскивание письма
  if (p.justDown) S.pd = { x: p.x, y: p.y, onCard: can && inRect(cardRect(), p.x, p.y), onQ: Math.hypot(p.x - K.q[0], p.y - K.q[1]) < QR + 10 };
  if (S.pd && p.down && S.pd.onCard && can) {
    const dx = p.x - S.pd.x, dy = p.y - S.pd.y;
    if (S.drag || Math.hypot(dx, dy) > 10) S.drag = { x: p.x, y: p.y, dx, dy, cand: pickSwipe(S.pd.x, S.pd.y, p.x, p.y) };
  }
  if (p.justUp && S.pd) {
    const pd = S.pd, dist = Math.hypot(p.x - pd.x, p.y - pd.y); S.pd = null;
    if (pd.onQ && dist < 30) { giveHint(); S.drag = null; return; }
    if (!can) { S.drag = null; return; }
    S.kb = false;
    if (pd.onCard) {
      const cand = dist > 36 ? pickSwipe(pd.x, pd.y, p.x, p.y) : -1; S.drag = null;
      if (cand >= 0) { S.flights.push({ k: 'card', x0: p.x, y0: p.y, x1: hog.x, y1: hog.y - 60, t: 0, dur: .28, L: S.cur }); choose(cand); }
      else if (dist <= 36) say(A.isTouch ? 'Смахни письмо к дому того, кто на марке, или нажми на дом.' : 'Щёлкни по дому того, кто на марке.', 4);
    } else {
      const h0 = hitHouse(pd.x, pd.y), h1 = hitHouse(p.x, p.y);
      if (dist < 40 && h1 >= 0) choose(h1);
      else if (dist >= 40 && h0 >= 0 && h0 === h1) choose(h1);
      else if (dist >= 60) { const c2 = pickSwipe(pd.x, pd.y, p.x, p.y); if (c2 >= 0) choose(c2); }
    }
  }
}
function giveHint() {
  if (S.mode !== 'play') return;
  snd.hint(); S.idle = Math.max(S.idle, 9.5);
  if (S.st === 'choose' && S.cur) { say(DAYS[S.day].idle, 6); S.help = true; } else say(DAYS[S.day].rule, 6);
}

/* ================= обновление ================= */
function update(g, dt0) {
  if (!S) return;
  const dt = dt0 * S.spd;
  S.t += dt; S.steam += dt; S.drops += dt;
  if (S.timers.length) { const due = S.timers.filter((q) => (q.t -= dt) <= 0); S.timers = S.timers.filter((q) => q.t > 0); due.forEach((q) => q.fn()); }
  if (!g.screenOn) input(g);
  // ёжик
  hog.blink -= dt; if (hog.blink < -.13) hog.blink = 2 + Math.random() * 3;
  if (hog.moodT > 0) { hog.moodT -= dt; if (hog.moodT <= 0) hog.mood = 'n'; }
  if (hog.pop > 0) hog.pop = Math.max(0, hog.pop - dt * 4);
  if (hog.legs.length) {
    const L = hog.legs[0]; if (hog.sp !== L.sp) { hog.sp = L.sp; hog.d = 0; }
    const sp = (hog.roll ? 640 : 230) * pf(hog.y), dir = Math.sign(L.to - hog.d), step = Math.min(Math.abs(L.to - hog.d), sp * dt);
    hog.d += dir * step; hog.ph += dt * 13;
    const [nx, ny] = posOn(hog.sp, hog.d); if (Math.abs(nx - hog.x) > .05) hog.face = Math.sign(nx - hog.x); hog.rot += step / (44 * pf(hog.y)) * hog.face; hog.x = nx; hog.y = ny;
    if (Math.abs(L.to - hog.d) < .01) { hog.legs.shift(); if (!hog.legs.length) { if (hog.roll) { hog.pop = 1; snd.pop(); } hog.roll = false; const f = hog.then; hog.then = null; if (f) f(); } }
  } else { const [nx, ny] = posOn(hog.sp, hog.d); hog.x = nx; hog.y = ny; }
  // жители
  for (const r of RES) { const R = S.res[r.id]; R.blink -= dt; if (R.blink < -.14) R.blink = 2 + Math.random() * 4; if (R.anim) { R.anim.t += dt; if (R.anim.t > 1.5) R.anim = null; } }
  if (S.bub) { S.bub.t += dt; if (S.bub.t > S.bub.life) S.bub = null; }
  if (S.cap) { S.cap.t += dt; if (S.cap.t > S.cap.life) S.cap = null; }
  if (S.banner) { S.banner.t += dt; if (S.banner.t > 2.2) S.banner = null; }
  if (S.hudBump > 0) S.hudBump = Math.max(0, S.hudBump - dt * 3);
  for (const f of S.flights) { f.t += dt; if (f.t >= f.dur && !f.done) { f.done = true; if (f.land) f.land(); } }
  S.flights = S.flights.filter((f) => !f.done);
  for (const q of S.parts) { q.t += dt; if (q.k === 'bit') { q.vy += 520 * dt; q.vx *= 1 - 1.6 * dt; q.x += q.vx * dt; q.y += q.vy * dt; q.rot += q.vr * dt; } }
  S.parts = S.parts.filter((q) => q.t < q.life);
  // листики и лепестки
  if (Math.random() < dt * .5 && S.leaves.length < 5) S.leaves.push({ x: -20, y: (LAND ? 160 : 300) + Math.random() * (LAND ? 300 : 500), vx: 40 + Math.random() * 40, ph: Math.random() * 6, rot: Math.random() * 6, col: A.pick(['#e8a54a', '#e2665c', '#f3c95a', '#f6c2cc']) });
  for (const l of S.leaves) { l.ph += dt; l.x += l.vx * dt; l.y += Math.sin(l.ph * 1.7) * 22 * dt + 10 * dt; l.rot += dt * 1.6; }
  S.leaves = S.leaves.filter((l) => l.x < W + 30);
  // письмо: выезжает снизу
  const show = S.mode === 'play' && S.st === 'choose' && S.cur;
  if (show) { S.cardT += dt; S.cardK = Math.min(1, S.cardK + dt * 2.6); } else S.cardK = Math.max(0, S.cardK - dt * 4);
  if (S.mode !== 'play') return;
  // солнце и день
  if (S.st !== 'dusk' && S.st !== 'idle') { S.sun = Math.min(1, S.sun + dt / DAYS[S.day].len);
    if (S.sun > .78 && !S.warned) { S.warned = true; say('Солнце клонится к закату — поторопись!', 4); }
    if (S.sun >= 1 && !S.sunset) { S.sunset = true; if (S.st === 'choose') endDay(); } }
  if (S.st === 'choose') { S.idle += dt; if (S.idle > 9 && !S.help) { S.help = true; say(DAYS[S.day].idle, 6); } }
  if (S.st === 'dusk') { S.dusk += dt; S.sun = Math.min(1.08, S.sun + dt * .25); if (S.dusk > 2 && !hog.legs.length) { S.st = 'idle'; dayScreen(); } }
}

/* ================= рисование ================= */
function sunPos() { const p = clamp(S.sun, 0, 1.1), s = K.sun; return [lerp(s.x0, s.x1, p), s.y0 - Math.sin(clamp(p, 0, 1) * PI) * (s.y0 - s.top) + Math.max(0, p - 1) * 300]; }
function drawSky(c) {
  c.drawImage(BG.sky, 0, 0, W, H);
  const [sx, sy] = sunPos(), ev = clamp((S.sun - .62) / .38, 0, 1);
  const sun = spr('sun', [-80, -80, 80, 80], 1, (x) => { const base = deform(subdiv(ellP(0, 0, 66, 66, 16), 20), 1, .2); x.save(); for (let i = 0; i < 8; i++) { x.globalAlpha = .16; x.fillStyle = '#fbf3e2'; x.fill(polyPath(deform(base, 2, .25))); } x.restore(); wash(x, ellP(0, 0, 58, 58, 16), '#ffd35e', { layers: 14, alpha: .07, m: 20, op: 'source-over' }); });
  const sun2 = spr('sun2', [-80, -80, 80, 80], 1, (x) => { wash(x, ellP(0, 0, 60, 60, 16), '#f59a5c', { layers: 14, alpha: .075, m: 20, op: 'source-over' }); });
  put(c, sun, sx, sy); if (ev > 0) { c.globalAlpha = ev; put(c, sun2, sx, sy); c.globalAlpha = 1; }
  // облака — «снятая» краска, медленно плывут
  const cl = LAND ? [[330, 196, 1, 6], [780, 110, .8, 4], [1180, 236, .7, 5]] : [[200, 330, .9, 5], [560, 230, .8, 4], [120, 180, .6, 3]];
  cl.forEach(([x, y, s, v], i) => { const cv = spr('cloud' + i, [-130, -60, 130, 50], s, (q) => { const pts = [[-96, 14], [-70, -14], [-24, -34], [30, -30], [66, -10], [100, 12], [20, 22], [-50, 22]]; const base = deform(subdiv(pts, 24), 1, .25); q.save(); for (let k = 0; k < 10; k++) { q.globalAlpha = .12; q.fillStyle = '#fbf6ec'; q.fill(polyPath(deform(base, 2, .3))); } q.restore(); wash(q, [[-80, 16], [90, 14], [60, 24], [-50, 26]], '#9db8d6', { layers: 6, alpha: .05, op: 'source-over' }); });
    const X = ((x + S.t * v) % (W + 300) + W + 300) % (W + 300) - 150; put(c, cv, X, y); });
}
function drawRes(c, h) {
  const R = S.res[h.id], an = R.anim, t = S.t + h.i;
  let dy = 0, rot = 0, sy = 1 + Math.sin(t * 2.2) * .018;
  let eyes = R.blink < 0 ? 'blink' : 'open', mood = 'idle';
  if (h.id === 'owl') eyes = 'sleep';
  if (an) { const k = an.t; mood = an.ok ? 'happy' : 'no'; eyes = an.ok ? 'happy' : 'wide';
    if (an.ok) { dy = -Math.abs(Math.sin(k * PI * 2.4)) * 16 * Math.max(0, 1 - k / 1.4); sy = 1 + Math.sin(k * PI * 4.8) * .05 * Math.max(0, 1 - k); }
    else rot = Math.sin(k * 24) * .13 * Math.max(0, 1 - k / 1.2); }
  const rs = h.rs * h.def.rs / h.def.rs, o = { eyes, mood };
  c.save(); c.translate(h.ax, h.ay);
  if (h.id === 'mouse') {
    const s = rs;
    const inner = spr('mouseIn:' + eyes + mood, [-30, -30, 30, 40], s, (q) => { cut(q, E(2, 26, 21, 16), '#c9bcc3', { blur: 3 }); cut(q, E(0, 6, 17, 15), '#c9bcc3', { blur: 3, sy: 2 }); cut(q, E(9, 11, 8, 6), '#d8ced3', { shadow: false }); eye(q, -5, 2, 2.5, o); eye(q, 6, 2, 2.5, o); dot(q, 17, 10, 3, '#e8838a'); mouth(q, 9, 15, 4.5, o); blush(q, -4, 11, 4);
      pen(q, (z) => { z.moveTo(15, 13); z.lineTo(27, 16); z.moveTo(15, 11); z.lineTo(27, 9); }, 1, 'rgba(90,63,53,.5)'); });
    const frame = spr('mouseFrame', [-34, -34, 40, 80], s, (q) => { pen(q, (z) => { z.moveTo(16, 22); z.bezierCurveTo(30, 34, 18, 50, 26, 62); z.quadraticCurveTo(32, 72, 24, 74); }, 2.8, '#c4959c'); pen(q, (z) => z.arc(0, 0, 26, 0, TAU), 4.5, '#b07a55'); });
    const ears = spr('mouseEars', [-30, -34, 30, 34], s, (q) => { cut(q, E(-12, -17, 10, 10), '#b8aab2', { blur: 2, sy: 1 }); cut(q, E(-12, -17, 6, 6), '#f0b3b4', { shadow: false }); cut(q, E(12, -18, 10, 10), '#b8aab2', { blur: 2, sy: 1 }); cut(q, E(12, -18, 6, 6), '#f0b3b4', { shadow: false });
      cut(q, E(-8, 24, 6, 4.5), '#b8aab2', { blur: 2, sy: 1 }); cut(q, E(8, 24, 6, 4.5), '#b8aab2', { blur: 2, sy: 1 }); });
    c.scale(h.m, 1); c.rotate(rot);
    c.save(); c.beginPath(); c.arc(0, 0, 25 * s, 0, TAU); c.clip(); c.fillStyle = '#fbefd0'; c.fillRect(-30 * s, -30 * s, 60 * s, 60 * s); put(c, inner, 0, dy * .5); c.restore();
    put(c, frame); put(c, ears, 0, dy * .5);
  } else if (h.id === 'mole') {
    const fig = spr('res:mole:' + eyes + mood, [-50, -110, 70, 10], rs, (q) => FIG.mole(q, o));
    const rim = spr('moleRim', [-32, -6, 32, 14], rs, (q) => { const p = new Path2D(); p.ellipse(0, 0, 27, 9, 0, 0, PI); p.ellipse(0, 1, 22, 5, 0, PI, 0, true); cut(q, p, '#8a6447', { blur: 3, sy: 2 }); });
    c.scale(h.m, 1);
    c.save(); c.beginPath(); c.rect(-60 * rs, -140 * rs, 140 * rs, 140 * rs); c.clip(); c.rotate(rot); c.scale(1, sy); put(c, fig, 0, 26 * rs + dy - (an && an.ok ? 8 * rs : 0)); c.restore();
    put(c, rim);
  } else {
    const box = { snail: [-70, -95, 70, 10], owl: [-56, -150, 80, 10], frog: [-50, -75, 50, 10], rabbit: [-40, -145, 50, 10], squirrel: [-80, -130, 45, 10] }[h.id];
    const fig = spr('res:' + h.id + ':' + eyes + mood, box, rs, (q) => FIG[h.id](q, o));
    c.scale(h.m, 1); c.rotate(rot); c.scale(1, sy); put(c, fig, 0, dy);
  }
  c.restore();
  if (h.id === 'owl' && !an) { const k = (S.t * .5) % 1; txt(c, 'з', h.ax + h.m * 50 * rs + k * 20 * h.m, h.ay - 120 * rs - k * 30, Math.round((LAND ? 20 : 24) + k * 6), 'rgba(111,95,128,' + (1 - k).toFixed(2) + ')', 700, 'center'); txt(c, 'з', h.ax + h.m * 66 * rs, h.ay - 140 * rs - k * 20, LAND ? 16 : 20, 'rgba(111,95,128,' + (.6 * (1 - k)).toFixed(2) + ')', 700, 'center'); }
}
function drawHog(c) {
  let s = pf(hog.y), x = hog.x, y = hog.y;
  if (S.mode === 'cover') { [x, y, s] = [372, 526, 1.04]; hog.carry = true; hog.face = 1; hog.ph = 1.2; }
  if (S.mode === 'title') { [x, y, s] = LAND ? [800, 706, 1.1] : [250, 1236, 1.45]; hog.carry = true; hog.face = 1; hog.ph = S.t * 9; }
  const walkingT = S.mode === 'title' || S.mode === 'cover';
  const sh = spr('hogShadow', [-80, -16, 80, 16], 1, (q) => wash(q, ellP(0, 0, 62, 10, 12), '#5f8a58', { layers: 8, alpha: .08, op: 'source-over' }));
  put(c, sh, 0 + x, y + 2 * s);
  if (hog.roll) {
    const ball = spr('hogBall', [-56, -56, 56, 56], 1, hogBall), cap = spr('hogCap', [-10, -120, 130, -50], 1, (q) => { q.scale(.6, .6); q.translate(-8, -72); hogCap(q); });
    const bob = Math.abs(Math.sin(hog.ph * .8)) * 6 * s;
    c.save(); c.translate(x, y - 44 * s); c.scale(s, s); c.rotate(hog.rot); put(c, ball); c.restore();
    c.save(); c.translate(x, y - 84 * s - bob); c.scale(s * hog.face, s); c.rotate(Math.sin(hog.ph) * .2); put(c, cap, -40, 30); c.restore();
    return;
  }
  const walking = hog.legs.length > 0 || walkingT, step = walking ? Math.round(Math.sin(hog.ph)) : 0, bob = walking ? -Math.abs(Math.sin(hog.ph)) * 4 : Math.sin(S.t * 2) * .8;
  const o = { carry: hog.carry, mood: hog.mood, step, blink: hog.blink < 0 && hog.mood === 'n' };
  const cv = spr('hog:' + (o.carry ? 1 : 0) + o.mood + step + (o.blink ? 1 : 0), [-80, -125, 140, 12], 1, (q) => hogDraw(q, o));
  const pop = hog.pop > 0 ? 1 + Math.sin(hog.pop * PI) * .12 : 1;
  c.save(); c.translate(x, y + bob * s); c.scale(s * hog.face * (2 - pop), s * pop); put(c, cv); c.restore();
}
function drawFocus(c, i, a, col = '#e2665c') {
  const h = HS[i], p = 1 + .05 * Math.sin(S.t * 5);
  c.save(); c.strokeStyle = col; c.globalAlpha = a; c.lineWidth = 3; c.setLineDash([9, 9]); c.lineDashOffset = -S.t * 18;
  c.beginPath(); c.ellipse(h.x, h.y + 2, 112 * h.s * p, 22 * h.s * p, 0, 0, TAU); c.stroke(); c.setLineDash([]); c.restore();
  const ty = h.head[1] - 62 * h.rs + Math.sin(S.t * 4) * 5, ax = h.head[0];
  const ar = spr('arrow:' + col, [-24, -30, 24, 12], 1, (q) => { const p2 = new Path2D(); p2.moveTo(-15, -20); p2.lineTo(15, -20); p2.lineTo(0, 4); p2.closePath(); cut(q, p2, col, { blur: 4, sy: 3 }); });
  c.globalAlpha = a; put(c, ar, ax, ty); c.globalAlpha = 1;
}
function drawCard(c) {
  const L = S.cur; if (!L || S.cardK <= 0) return;
  const left = S.letters.length - S.li - 1, cv = cardSpr(L, left), { x, y, h } = K.card, k = eBack(clamp(S.cardK, 0, 1));
  c.save();
  if (S.drag) { const z = clamp(1 - Math.hypot(S.drag.dx, S.drag.dy) / 300, .5, 1); c.translate(S.drag.x, S.drag.y - (1 - z) * 90); c.rotate(clamp(S.drag.dx / 600, -.25, .25)); c.scale(z, z); const pd = S.pd || { x, y }; c.translate(x - pd.x, y - pd.y); }
  else { const wob = S.cardT < 1.2 ? Math.sin(S.cardT * 9) * .02 * (1.2 - S.cardT) : 0; c.translate(x, y + (1 - k) * (h + 80)); c.rotate(-.025 + (1 - k) * .12 + wob); }
  put(c, cv); c.restore();
}
function drawFlights(c) {
  for (const f of S.flights) {
    if (f.t < 0) continue; const k = eIO(clamp(f.t / f.dur, 0, 1)), x = lerp(f.x0, f.x1, k), y = lerp(f.y0, f.y1, k) - Math.sin(k * PI) * 70;
    if (f.k === 'env' || f.k === 'card') { const ic = spr('envFly', [-30, -22, 30, 22], 1, (q) => { envIcon(q, 0, 0, 40, 1); }); c.save(); c.translate(x, y); c.rotate(k * 2); put(c, ic); c.restore(); }
    else { const s = LAND ? .5 : .6, ic = spr('gift:' + f.k, [-50, -50, 50, 50], s, (q) => ITEM[f.k](q)); c.save(); c.translate(x, y); c.scale(1 + Math.sin(k * PI) * .4, 1 + Math.sin(k * PI) * .4); put(c, ic); c.restore(); }
  }
}
function drawParts(c) {
  for (const q of S.parts) {
    const a = clamp(1 - q.t / q.life, 0, 1);
    if (q.k === 'bit') { c.save(); c.globalAlpha = Math.min(1, a * 2); c.translate(q.x, q.y); c.rotate(q.rot); c.fillStyle = q.col; c.fillRect(-q.w / 2, -q.h / 2, q.w, q.h); c.restore(); }
    else if (q.k === 'txt') { const k = q.t / q.life; c.globalAlpha = a; txt(c, q.s, q.x, q.y - eOut(k) * 40, LAND ? 30 : 36, q.s === '?!' ? '#c94f48' : '#4f8a46', 800, 'center'); c.globalAlpha = 1; }
  }
  for (const l of S.leaves) { c.save(); c.translate(l.x, l.y); c.rotate(l.rot); c.fillStyle = l.col; c.globalAlpha = .85; c.beginPath(); c.ellipse(0, 0, 9, 4, 0, 0, TAU); c.fill(); c.restore(); }
  c.globalAlpha = 1;
}
function drawBubble(c) {
  const b = S.bub; if (!b) return;
  const h = HS[b.h], size = K.size, lines = wrap(b.text, size, LAND ? 250 : 300), bw = Math.max(...lines.map((l) => tw(l, size))) + 36, bh = lines.length * size * 1.22 + 22;
  const side = COVER || h.head[0] < W / 2 ? 1 : -1;
  let bx = h.head[0] + side * (34 * h.rs) + (side > 0 ? 0 : -bw), by = h.head[1] - bh - 14;
  bx = clamp(bx, 10, W - bw - 10); by = clamp(by, LAND ? 112 : 132, H - bh - 10);
  const a = clamp(Math.min(b.t / .15, (b.life - b.t) / .25), 0, 1), sc = .85 + .15 * eBack(clamp(b.t / .25, 0, 1));
  const cv = spr('bub:' + b.text + side + (FONTS ? 'f' : 'n'), [-20, -20, bw + 20, bh + 40], 1, (q) => {
    const p = rrp(0, 0, bw, bh, 16), tx = side > 0 ? 22 : bw - 22;
    p.moveTo(tx - 10, bh - 2); p.lineTo(tx - side * 16, bh + 22); p.lineTo(tx + 10, bh - 2);
    cut(q, p, '#fffaf0', { blur: 8, sy: 4 });
    lines.forEach((l, i) => txt(q, l, bw / 2, 13 + size * .95 + i * size * 1.22, size, LINE, 600, 'center'));
  });
  c.save(); c.globalAlpha = a; c.translate(bx + (side > 0 ? 22 : bw - 22), by + bh + 20); c.scale(sc, sc); c.translate(-(bx + (side > 0 ? 22 : bw - 22)), -(by + bh + 20)); put(c, cv, bx, by); c.restore();
}
function drawHUD(c) {
  const [px, py, pw, ph] = K.plate, D = DAYS[S.day], big = LAND ? 27 : 32;
  const key = 'plate:' + S.day + ':' + S.marks.join('') + ':' + S.gifts + (FONTS ? 'f' : 'n');
  const plate = spr(key, [-16, -16, pw + 16, ph + 24], 1, (q) => {
    cut(q, torn(0, 0, pw, ph), '#fffaf0', { blur: 12, sy: 6 });
    cut(q, E(26, LAND ? 34 : 40, 11, 11), '#e2665c', { blur: 2, sy: 1 });
    txt(q, 'День ' + (S.day + 1) + ' · ' + D.name, 46, LAND ? 44 : 51, big, LINE, 700);
    const ew = LAND ? 28 : 34, gap = LAND ? 34 : 41, ey = ph - (LAND ? 25 : 28);
    S.marks.forEach((m, i) => envIcon(q, 32 + i * gap, ey, ew, m));
    ITEM.gift(q, pw - 92, ey - 2, LAND ? .42 : .5);
    txt(q, '× ' + S.gifts, pw - 66, ey + (LAND ? 9 : 10), LAND ? 25 : 30, LINE, 700);
  });
  const bump = 1 + S.hudBump * .06;
  c.save(); c.translate(px + pw - 70, py + ph - 26); c.scale(bump, bump); c.translate(-(px + pw - 70), -(py + ph - 26)); put(c, plate, px, py); c.restore();
  // «?»
  const qb = spr('qbtn' + (FONTS ? 'f' : 'n'), [-QR - 12, -QR - 12, QR + 12, QR + 16], 1, (q) => { cut(q, E(0, 0, QR, QR), '#fffaf0', { blur: 8, sy: 4 }); txt(q, '?', 0, 2, QR * 1.15, LINE, 800, 'center', 'middle'); });
  const pulse = S.idle > 8 && S.st === 'choose' ? 1 + Math.sin(S.t * 5) * .06 : 1;
  c.save(); c.translate(K.q[0], K.q[1]); c.scale(pulse, pulse); put(c, qb); c.restore();
  // строка-подсказка
  if (S.cap && !S.bub && !S.banner) {
    const k = S.cap, a = clamp(Math.min(k.t / .3, (k.life - k.t) / .5), 0, 1), size = K.size, [cx0, cy0, cw] = K.cap;
    const lines = wrap(k.text, size, cw - 50), bh = lines.length * size * 1.25 + 26, bw = Math.min(cw, Math.max(...lines.map((l) => tw(l, size))) + 50);
    const cv = spr('cap:' + k.text + (FONTS ? 'f' : 'n'), [-16, -16, bw + 16, bh + 24], 1, (q) => { cut(q, torn(0, 0, bw, bh, 1.4), '#fffaf0', { blur: 10, sy: 5 }); lines.forEach((l, i) => txt(q, l, bw / 2, 13 + size * .95 + i * size * 1.25, size, LINE, 600, 'center')); });
    c.globalAlpha = a; put(c, cv, cx0 + (cw - bw) / 2, cy0 + (1 - a) * -8); c.globalAlpha = 1;
  }
  if (S.banner) {
    const b = S.banner, a = clamp(Math.min(b.t / .35, (2.2 - b.t) / .45), 0, 1), size = LAND ? 52 : 60;
    const cv = spr('ban:' + b.text + (FONTS ? 'f' : 'n'), [-20, -20, tw(b.text, size, 700) + 100, size * 1.9 + 20], 1, (q) => { const bw = tw(b.text, size, 700) + 80; cut(q, torn(0, 0, bw, size * 1.7, 2.2), '#fffaf0', { blur: 14, sy: 7 }); txt(q, b.text, bw / 2, size * 1.2, size, LINE, 700, 'center'); });
    c.globalAlpha = a; put(c, cv, W / 2 - (tw(b.text, size, 700) + 80) / 2, (LAND ? 300 : 560) - (1 - a) * 20); c.globalAlpha = 1;
  }
}
function draw(c, g) {
  if (!S) return;
  const sc = g.scale * (COVER ? 1.5 : 1); if (sc !== CS) { CS = sc; CACHE.clear(); BG = null; }
  if (!BG) makeBG();
  if (COVER) { c.save(); c.translate(W / 2, H / 2); c.scale(1.5, 1.5); c.translate(-575, -318); }
  drawSky(c);
  c.drawImage(BG.land, 0, 0, W, H);
  // пар из носика чайника и капли из лейки
  const tp = HS.find((h) => h.id === 'mouse'), cn = HS.find((h) => h.id === 'frog');
  for (let i = 0; i < 3; i++) { const k = (S.steam * .35 + i / 3) % 1, x = tp.x + tp.m * (140 + k * 16) * tp.s, y = tp.y - (130 + k * 70) * tp.s; c.globalAlpha = .35 * Math.sin(k * PI); dot(c, x, y, (8 + k * 12) * tp.s, '#dfe8ee'); }
  for (let i = 0; i < 3; i++) { const k = (S.drops * .8 + i / 3) % 1, x = cn.x + cn.m * (-126 - i * 4) * cn.s, y = cn.y + (-100 + k * 100) * cn.s; c.globalAlpha = .7 * (1 - k); dot(c, x, y, 2.6 * cn.s, '#7fb8d8'); }
  c.globalAlpha = 1;
  // подсветка: фокус клавиатуры, мышь, перетаскивание, подсказка
  if (S.mode === 'play' && S.st === 'choose') {
    if (S.drag && S.drag.cand >= 0) { drawFocus(c, S.drag.cand, .95); const h = HS[S.drag.cand]; c.save(); c.strokeStyle = 'rgba(90,63,53,.5)'; c.lineWidth = 2.4; c.setLineDash([8, 10]); c.lineDashOffset = -S.t * 30; c.beginPath(); c.moveTo(S.drag.x, S.drag.y); c.quadraticCurveTo((S.drag.x + h.cx) / 2, Math.min(S.drag.y, h.cy) - 60, h.cx, h.box[1] + 30); c.stroke(); c.restore(); }
    else if (S.kb && S.focus >= 0) drawFocus(c, S.focus, .95);
    else if (S.hover >= 0) drawFocus(c, S.hover, .6, '#c99230');
    if (S.idle > 15 && S.cur) { const h = HS.find((q) => q.id === S.cur.who); for (let i = 0; i < 3; i++) { const a = S.t * 2 + i * 2.1, r = 40 * h.s; c.globalAlpha = .5 + .5 * Math.sin(S.t * 4 + i); A.star(c, h.head[0] + Math.cos(a) * r, h.head[1] - 20 + Math.sin(a) * r * .6, 6, 4, .4); c.fillStyle = '#f3c95a'; c.fill(); } c.globalAlpha = 1; }
  }
  for (const h of HS) drawRes(c, h);
  drawHog(c);
  drawParts(c);
  drawBubble(c);
  // вечер: тёплая дымка поверх мира
  const ev = clamp((S.sun - .6) / .4, 0, 1) * .3 + (S.st === 'dusk' || S.mode === 'screen' && S.day >= 0 && S.sun >= .99 ? .12 : 0);
  if (ev > 0) { c.save(); c.globalCompositeOperation = 'multiply'; c.fillStyle = 'rgba(250,170,130,' + ev.toFixed(3) + ')'; c.fillRect(0, 0, W, H); c.restore(); }
  if (S.mode === 'play' || S.mode === 'screen') drawHUD(c);
  drawCard(c);
  drawFlights(c);
  if (COVER) { c.restore(); drawCover(c); }
  if (DBG) { c.strokeStyle = 'red'; for (const h of HS) { c.strokeRect(h.box[0], h.box[1], h.box[2] - h.box[0], h.box[3] - h.box[1]); dot(c, h.spot[0], h.spot[1], 4, 'red'); } }
}
function drawCover(c) {
  c.save(); c.translate(100, 30);
  cut(c, torn(0, 0, 520, 128, 1.8), '#fffaf0', { blur: 12, sy: 6 }); cut(c, E(34, 58, 13, 13), '#e2665c', { blur: 2, sy: 1 });
  txt(c, 'Колючая почта', 60, 76, 54, LINE, 700); txt(c, 'Посмотри на марку — и отнеси письмо', 36, 110, 21, MUTE, 600);
  c.restore();
  const cv = cardSpr({ who: 'snail', kind: 'p' }, 4); c.save(); c.translate(1000, 590); c.rotate(.05); c.scale(1.05, 1.05); put(c, cv); c.restore();
}

A.game({
  id: 'post', title: 'Колючая почта', width: W, height: H, orientation: LAND ? 'landscape' : 'portrait', tone: 'light', music: 'garden',
  keys: { KeyA: 'none', KeyD: 'none', KeyW: 'none', KeyS: 'none', KeyH: 'hint', Slash: 'hint', KeyZ: 'none', KeyJ: 'none', KeyK: 'none', KeyX: 'none', KeyL: 'none', ShiftLeft: 'none' },
  help: { desktop: 'Щёлкните по дому того, кто на марке · стрелки — выбрать дом, <kbd>Enter</kbd> — вручить · <kbd>?</kbd> — подсказка', short: 'Щёлкните по дому того, кто на марке · стрелки и Enter', touch: 'Нажмите на дом того, кто на марке, или смахните письмо к нему' },
  init(g) {
    GAME = g; window.__post = () => S; window.__postHog = () => hog;
    if (document.fonts && document.fonts.load) Promise.all([document.fonts.load('700 30px Rubik'), document.fonts.load('600 24px Rubik'), document.fonts.load('800 30px Rubik')]).then(() => { FONTS = true; }).catch(() => { FONTS = true; });
    else FONTS = true;
    if (COVER) { fresh('play'); S.sun = .42; S.mode = 'cover'; S.bub = { h: 2, text: 'Это мне?!', t: .5, life: 1e9 }; return; }
    titleScreen(g);
  },
  update, draw,
});
})();
