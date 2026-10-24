/* «Выше облаков» — милый вертикальный прыгун для «Досуга» Dewiar (24.10).
   Герой — Тимоша, сонный человечек в полосатой пижаме и ночном колпаке: хочет выспаться на луне. Прыгает сам на каждой
   опоре (сплющивается и тянется), игрок ведёт его влево-вправо: ←/→ или A/D, мышь (тянется к курсору), на телефоне —
   удержание левой/правой половины экрана или наклон (deviceorientation, включается сам при первом наклоне).
   Мир снизу вверх: луг → кроны → облака → закат → звёздная ночь с сонной луной. Стиль — бумажная аппликация: плоские
   листы цветной бумаги с мягкой тенью, светлой кромкой среза, тёмным нижним краем и зерном бумаги.
   Опоры: листик / веточка / облачко (обычные), сухой листик (хрусть — не держит), листик с крылышками (едет),
   одуванчик (на один прыжок); пружинка и шарик — выше; сонный жук в колпаке (сверху — отпрыгнуть, снизу — «ой»),
   ветерок; ягодки и звёздочки. Падение вниз — «Улетел!» (Тимоша раскрывает зонтик и мирно опускается, зевая).
   Производительность: каждая бумажная деталь вырезается один раз в свой холстик под текущий масштаб (spr), кадр только
   складывает готовые холсты; небо — один градиент, звёзды — готовая плитка, рамка широкого окна — один холст.
   Широкое окно: поле-колонка посередине «бумажной страницы», по бокам высотомер и счёт; книжное — во весь экран. */
(() => {
'use strict';
const A = Arcade, SND = A.sound, TAU = Math.PI * 2;
const Q = new URLSearchParams(location.search), COVER = Q.has('cover');
const LAND = COVER || (() => { try { return innerWidth > (innerHeight - 110) * 1.15; } catch (e) { return false; } })();
const W = COVER ? 1152 : LAND ? 1280 : 720, H = COVER ? 720 : LAND ? 720 : 1280;
/* мир: ширина 720 единиц в обоих видах (одинаковая игра); широкое окно показывает его в масштабе .8 (видно 900 ед.
   по высоте), книжное — 1:1 (1280 ед.). Обложка — крупно, во всю ширину. */
const WW = 720, K = COVER ? 1.6 : LAND ? .8 : 1, COLW = WW * K, COLX = (W - COLW) / 2, VH = H / K;
const clamp = A.clamp, lerp = A.lerp, FONT = A.FONT;
const sstep = (a, b, x) => { const t = clamp((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); };
const wrapD = (d) => { d = ((d % WW) + WW) % WW; return d > WW / 2 ? d - WW : d; };
const wrapX = (x) => ((x % WW) + WW) % WW;
function rng(seed) { let s = seed | 0; return () => { s = (s + 0x6D2B79F5) | 0; let t = Math.imul(s ^ (s >>> 15), 1 | s); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
const hash = (str) => { let h = 2166136261; for (let i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 16777619); } return h >>> 0; };
const INK = '#4a3550', INK2 = '#7c6679', CREAM = '#fffaf0', PAPER = '#f6ecdb', CORAL = '#ff7b6b';

/* ---------------- физика ---------------- */
const G = 2300, JUMP = 1180, SPRING = 1990, STOMP = 1460, HS = 650, BAL_V = 1020, BAL_T = 2.2, R = 30, HSC = 1.55, HR = R * HSC;   // HSC — масштаб Тимоши (1,55 ≈ на четверть крупнее первого варианта)
/* попадания растут вместе с героем: тапочки по краю опоры, сбор ягод и шарика, жук */
const FOOT = Math.round(13 * HSC), HIT = 47 * HSC, BUGHIT = 48 * HSC;

/* ---------------- высоты ---------------- */
const BIO = [
  { id: 'meadow', a: 0, name: 'Луг', short: 'луг', item: 'berry', skin: 'leaf', col: '#a9d97f' },
  { id: 'trees', a: 2600, name: 'В кронах', short: 'кроны', item: 'berry', skin: 'twig', col: '#6fbd72' },
  { id: 'clouds', a: 7000, name: 'Облака', short: 'облака', item: 'star', skin: 'cloud', col: '#9fd2f2' },
  { id: 'sunset', a: 13000, name: 'Закат', short: 'закат', item: 'star', skin: 'peach', col: '#f6a59c' },
  { id: 'night', a: 19500, name: 'Звёздная ночь', short: 'ночь', item: 'star', skin: 'lav', col: '#5b51a2' }
];
const TOP = 23000;                              // высотомер: шкала «до луны»
const bioAt = (alt) => { let i = 0; while (i < BIO.length - 1 && alt >= BIO[i + 1].a) i++; return i; };
const diffAt = (alt) => clamp(alt / 22000, 0, 1.3);   // выше луны (>22 км) растёт только доля едущих, одуванчиков и жуков
const hex = (s) => [1, 3, 5].map((i) => parseInt(s.slice(i, i + 2), 16));
const SKY = [
  [0, '#bfe5f0', '#d9efe8', '#f3f5dc'],
  [2400, '#a7dbee', '#c8ebe8', '#e8f5dc'],
  [6400, '#8ccaef', '#b8dff5', '#e5f3fb'],
  [11000, '#8dbfec', '#c4daf3', '#f5e6e6'],
  [13600, '#9b8ed2', '#f0a5ba', '#ffd2a5'],
  [17400, '#5f509f', '#b27cb2', '#f3a29a'],
  [20300, '#1d2152', '#2e2d67', '#4a3e7d']
].map(([a, ...cs]) => [a, cs.map(hex)]);
function skyAt(alt) {
  let i = 0; while (i < SKY.length - 2 && alt > SKY[i + 1][0]) i++;
  const [a0, c0] = SKY[i], [a1, c1] = SKY[i + 1], t = sstep(a0, a1, alt);
  return c0.map((c, k) => 'rgb(' + c.map((v, j) => Math.round(lerp(v, c1[k][j], t))).join(',') + ')');
}

/* ---------------- звуки ---------------- */
const now = () => SND.now();
const snd = {
  hop(k = 1) { if (!SND.ctx) return; const t = now(), p = k * (.94 + Math.random() * .12); SND.tone(330 * p, t, .14, .08, 'sine', null, 660 * p); SND.tone(990 * p, t + .015, .07, .018, 'triangle', null, 1500 * p); },
  spring() { if (!SND.ctx) return; const t = now(); SND.tone(250, t, .45, .09, 'triangle', null, 1050); for (let i = 0; i < 5; i++) SND.tone(520 + i * 130, t + i * .05, .08, .03, 'sine'); },
  crunch() { if (!SND.ctx) return; const t = now(); for (let i = 0; i < 6; i++) SND.hiss(t + i * .026 + Math.random() * .012, .04, .08, 'bandpass', 1500 + Math.random() * 2800); SND.tone(190, t, .07, .04, 'square', null, 90); },
  puff() { if (!SND.ctx) return; const t = now(); SND.hiss(t, .45, .05, 'bandpass', 1300); SND.tone(1200, t, .25, .018, 'sine', null, 1800); },
  pick(n) { if (!SND.ctx) return; const t = now(), st = [0, 2, 4, 7, 9, 12, 14, 16][Math.min(7, n)], f = 784 * Math.pow(2, st / 12); SND.tone(f, t, .12, .07, 'triangle'); SND.tone(f * 2, t + .05, .16, .028, 'sine'); },
  inflate() { if (!SND.ctx) return; const t = now(); SND.tone(240, t, .5, .06, 'sine', null, 640); SND.hiss(t, .35, .025, 'bandpass', 900); },
  pop() { if (!SND.ctx) return; const t = now(); SND.hiss(t, .12, .12, 'highpass', 1800); SND.tone(700, t, .08, .05, 'square', null, 200); },
  bonk() { if (!SND.ctx) return; const t = now(); SND.tone(520, t, .1, .07, 'triangle', null, 330); SND.tone(400, t + .1, .16, .06, 'triangle', null, 260); },
  stomp() { if (!SND.ctx) return; const t = now(); SND.tone(300, t, .12, .1, 'sine', null, 640); SND.tone(150, t + .02, .3, .022, 'sawtooth', null, 210); },
  oops() { if (!SND.ctx) return; const t = now(); SND.tone(1050, t, .8, .07, 'sine', null, 240); },
  wind() { if (!SND.ctx) return; SND.hiss(now(), 1.5, .05, 'bandpass', 520); },
  biome() { if (!SND.ctx) return; const t = now(); [659, 784, 988, 1319].forEach((f, i) => SND.tone(f, t + i * .09, .4, .035, 'sine')); }
};

/* ---------------- холсты-спрайты ---------------- */
let GAME = null, SS = 1;
const CACHE = new Map(); let cacheS = 0;
/* w×h — размер в единицах (мира при k=K, экрана при k=1), (ox, oy) — точка привязки внутри */
function spr(key, w, h, ox, oy, fn, k = K) {
  const sc = GAME ? GAME.scale : 1;
  if (sc !== cacheS) { CACHE.clear(); cacheS = sc; }
  const id = key + '@' + k;
  let e = CACHE.get(id);
  if (!e) {
    const s = k * sc, cv = document.createElement('canvas');
    cv.width = Math.max(1, Math.ceil(w * s)); cv.height = Math.max(1, Math.ceil(h * s));
    const c = cv.getContext('2d'); c.scale(s, s); c.translate(ox, oy); SS = s; fn(c);
    e = { cv, w, h, ox, oy }; CACHE.set(id, e);
  }
  return e;
}
const blit = (c, e, x, y) => c.drawImage(e.cv, x - e.ox, y - e.oy, e.w, e.h);

/* ---------------- бумага ---------------- */
let GR = null;
function grain() {
  if (GR) return GR;
  const n = 128, cv = document.createElement('canvas'); cv.width = cv.height = n;
  const x = cv.getContext('2d'), d = x.createImageData(n, n), r = rng(7);
  for (let i = 0; i < n * n; i++) { const v = r(), light = v > .5; d.data[i * 4] = d.data[i * 4 + 1] = d.data[i * 4 + 2] = light ? 255 : 80; d.data[i * 4 + 3] = Math.round(Math.abs(v - .5) * 2 * 30 * (r() < .2 ? 2 : 1)); }
  x.putImageData(d, 0, 0); GR = cv; return cv;
}
function grainFill(c, a = 1) {
  const p = c.createPattern(grain(), 'repeat');
  try { p.setTransform(new DOMMatrix().scale(1 / SS)); } catch (e) { /* старый браузер — зерно крупнее */ }
  c.globalAlpha = a; c.fillStyle = p; c.fillRect(-4000, -4000, 8000, 8000); c.globalAlpha = 1;
}
const BIG = new Path2D(); BIG.rect(-4000, -4000, 8000, 8000);
function band(c, path, dy, col) { const p = new Path2D(BIG); p.addPath(path, new DOMMatrix([1, 0, 0, 1, 0, dy])); c.fillStyle = col; c.fill(p, 'evenodd'); }
/* вырезанный лист бумаги: тень, заливка, светлая кромка сверху, тёмный край снизу, зерно */
function cut(c, path, fill, o = {}) {
  c.save();
  if (o.shadow !== false) { c.shadowColor = o.sc || 'rgba(74,42,80,.24)'; c.shadowBlur = (o.blur ?? 6) * SS; c.shadowOffsetY = (o.sy ?? 3) * SS; c.shadowOffsetX = (o.sx ?? 0) * SS; }
  c.fillStyle = fill; c.fill(path); c.restore();
  c.save(); c.clip(path);
  if (o.shade) band(c, path, -(o.sw || 5), o.shade);
  if (o.rim) band(c, path, o.rw || 2.4, o.rim);
  if (o.grain !== false) grainFill(c, o.ga ?? 1);
  c.restore();
}
const mid = (a, b) => [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
function smoothPath(pts) {
  const p = new Path2D(), n = pts.length; let m = mid(pts[n - 1], pts[0]); p.moveTo(m[0], m[1]);
  for (let i = 0; i < n; i++) { const a = pts[i], q = mid(a, pts[(i + 1) % n]); p.quadraticCurveTo(a[0], a[1], q[0], q[1]); }
  p.closePath(); return p;
}
function roundPoly(pts, rad) {
  const p = new Path2D(), n = pts.length, m0 = mid(pts[n - 1], pts[0]); p.moveTo(m0[0], m0[1]);
  for (let i = 0; i < n; i++) { const a = pts[i], m = mid(a, pts[(i + 1) % n]); p.arcTo(a[0], a[1], m[0], m[1], rad); }
  p.closePath(); return p;
}
function rrPath(x, y, w, h, r) { const p = new Path2D(); p.moveTo(x + r, y); p.arcTo(x + w, y, x + w, y + h, r); p.arcTo(x + w, y + h, x, y + h, r); p.arcTo(x, y + h, x, y, r); p.arcTo(x, y, x + w, y, r); p.closePath(); return p; }
function ell(cx, cy, rx, ry, rot = 0) { const p = new Path2D(); p.ellipse(cx, cy, rx, ry, rot, 0, TAU); return p; }
function circ(cx, cy, r) { const p = new Path2D(); p.arc(cx, cy, r, 0, TAU); return p; }
/* облако: плоское дно на y=h, бугры над линией base */
function cloudShape(w, h, r, base, bk) {
  const hw = w / 2, p = new Path2D(), n = Math.max(3, Math.round(w / 40)), seg = w / n, e0 = (h - base) * .4;
  p.moveTo(-hw + h * .4, h);
  p.quadraticCurveTo(-hw - 2, h, -hw, base + e0);
  let x = -hw;
  for (let i = 0; i < n; i++) {
    const x1 = -hw + seg * (i + 1), e = (i === 0 || i === n - 1) ? .7 : 1, bh = seg * (.45 + r() * .32) * e * bk;
    p.bezierCurveTo(x - 1, base - bh * 1.33, x1 + 1, base - bh * 1.33, x1, i === n - 1 ? base + e0 : base);
    x = x1;
  }
  p.quadraticCurveTo(hw + 2, h, hw - h * .4, h);
  p.closePath(); return p;
}
function txt(c, s, x, y, size, col, o = {}) {
  c.font = `${o.w || 800} ${size}px ${FONT}`; c.textAlign = o.align || 'left'; c.textBaseline = o.base || 'middle';
  if (o.halo) { c.lineJoin = 'round'; c.lineWidth = o.haloW || size * .22; c.strokeStyle = o.halo; c.strokeText(s, x, y); }
  c.fillStyle = col; c.fillText(s, x, y);
}

/* ---------------- опоры ---------------- */
const LEAF = [
  { f: '#9bd16c', rim: '#c6ec97', sh: '#77b552', vein: '#66a548' },
  { f: '#a9d873', rim: '#d0f0a2', sh: '#83bd57', vein: '#6eaa4c' },
  { f: '#8ccb6a', rim: '#bbe596', sh: '#6aad50', vein: '#5c9c45' }
];
const DRY = { f: '#eda65a', rim: '#fbd193', sh: '#c97f3c', vein: '#a9672b' };
function leafPts(w, r, dry) {
  const hw = w / 2, n = 18, pts = [];
  for (let i = 0; i <= n; i++) { const t = i / n; pts.push([-hw + w * t, 1.5 - Math.sin(t * Math.PI) * 2.6 + (r() - .5) * .8]); }
  for (let i = n - 1; i >= 1; i--) { const t = i / n, b = Math.sin(Math.pow(t, .85) * Math.PI); let y = 2 + b * 27 + (r() - .5); if (dry) y -= Math.abs(Math.sin(t * Math.PI * 3.5)) * 7 * b; pts.push([-hw + w * t, y]); }
  return pts;
}
function drawLeaf(c, w, v, dry) {
  const r = rng(hash('leaf' + w + v + dry)), pal = dry ? DRY : LEAF[v % 3], hw = w / 2;
  c.lineCap = 'round';
  c.strokeStyle = pal.vein; c.lineWidth = 3; c.beginPath(); c.moveTo(-hw + 3, 3); c.quadraticCurveTo(-hw - 8, 3, -hw - 11, -5); c.stroke();
  cut(c, smoothPath(leafPts(w, r, dry)), pal.f, { rim: pal.rim, shade: pal.sh, sw: 5, rw: 2.2 });
  const my = (t) => (1 - t) * (1 - t) * 4 + 2 * (1 - t) * t * 15 + t * t * 3;
  c.strokeStyle = pal.vein; c.lineWidth = 2; c.beginPath(); c.moveTo(-hw + 4, 4); c.quadraticCurveTo(0, 15, hw - 4, 3); c.stroke();
  c.lineWidth = 1.4; c.beginPath();
  for (let k = 1; k <= 5; k++) { const t = k / 6.3, x = -hw + w * t, y = my(t); c.moveTo(x, y); c.lineTo(x + w * .08, y + 9 * Math.sin(t * Math.PI)); }
  c.stroke();
  if (dry) {
    c.strokeStyle = '#8c5728'; c.lineWidth = 1.7; c.beginPath(); c.moveTo(w * .06, -1); c.lineTo(w * .02, 6); c.lineTo(w * .09, 10); c.lineTo(w * .03, 17); c.stroke();
    c.beginPath(); c.moveTo(-w * .26, 1); c.lineTo(-w * .3, 7); c.lineTo(-w * .24, 11); c.stroke();
  }
}
function smallLeaf(c, x, y, ang, len, pal) {
  c.save(); c.translate(x, y); c.rotate(ang);
  const p = new Path2D(); p.moveTo(0, 0); p.quadraticCurveTo(len * .5, -len * .32, len, 0); p.quadraticCurveTo(len * .5, len * .32, 0, 0); p.closePath();
  cut(c, p, pal.f, { rim: pal.rim, shade: pal.sh, sw: 2, rw: 1.4, blur: 3, sy: 2 });
  c.strokeStyle = pal.vein; c.lineWidth = 1; c.beginPath(); c.moveTo(1, 0); c.lineTo(len * .85, 0); c.stroke();
  c.restore();
}
function drawTwig(c, w, v) {
  const r = rng(hash('twig' + w + v)), hw = w / 2, pal = LEAF[(v + 1) % 3];
  smallLeaf(c, -hw + 16, 10, 1.9 + r() * .3, 26, pal);
  smallLeaf(c, hw - 20, 10, 1.1 - r() * .3, 28, pal);
  smallLeaf(c, -w * .06, 11, 1.55 + (r() - .5) * .4, 22, LEAF[v % 3]);
  const pts = [];
  for (let i = 0; i <= 10; i++) pts.push([-hw + w * i / 10, -1 + (r() - .5) * 1.4 + (i === 0 || i === 10 ? 3 : 0)]);
  for (let i = 10; i >= 0; i--) pts.push([-hw + w * i / 10, 14 + (r() - .5) * 1.4 - (i === 0 || i === 10 ? 2 : 0)]);
  cut(c, smoothPath(pts), '#c58e5d', { rim: '#e6b98c', shade: '#9b6a43', sw: 3.5, rw: 2 });
  c.strokeStyle = 'rgba(140,90,52,.55)'; c.lineWidth = 1.3; c.lineCap = 'round'; c.beginPath();
  for (let i = 0; i < 5; i++) { const x = -hw + 14 + r() * (w - 28); c.moveTo(x, 4 + r() * 2); c.lineTo(x + 10 + r() * 8, 4 + r() * 3); }
  c.stroke();
  c.fillStyle = '#a77246'; c.beginPath(); c.ellipse(w * .2, 5, 3.4, 2.4, 0, 0, TAU); c.fill();
  /* росток вверх на правом конце */
  c.strokeStyle = '#8bbf5e'; c.lineWidth = 2.2; c.beginPath(); c.moveTo(hw - 8, 0); c.quadraticCurveTo(hw - 4, -8, hw + 2, -11); c.stroke();
  smallLeaf(c, hw + 1, -11, -.5, 13, pal);
}
const CLOUDP = { cloud: ['#ffffff', '#ffffff', '#c9daf1', 'rgba(50,70,140,.34)'], peach: ['#ffe1d0', '#fff3ea', '#f0a596', 'rgba(150,60,80,.34)'], lav: ['#bcb4f2', '#dcd7fc', '#8c84d8', 'rgba(10,5,50,.5)'] };
function drawCloudPlat(c, w, v, skin) {
  const r = rng(hash(skin + w + v)), pal = CLOUDP[skin];
  cut(c, cloudShape(w, 25, r, 8, .46), pal[0], { rim: pal[1], shade: pal[2], sw: 7, sc: pal[3], sy: 4.5, blur: 6 });
  if (skin === 'lav') { c.fillStyle = '#ffd86b'; c.fill(starP(w * .18, 12, 6, 2.8, 1.2)); }
  if (skin === 'cloud' && v === 1) { c.fillStyle = 'rgba(255,170,190,.45)'; c.beginPath(); c.ellipse(w * .28, 14, 7, 3.5, 0, 0, TAU); c.fill(); }
}
/* одуванчики: три пушистые головки семян на одной кочке — на один прыжок */
function drawFluff(c, w, v) {
  const r = rng(hash('fluff' + w + v)), n = 3, gap = (w - 34) / (n - 1), rr = 19;
  cut(c, ell(0, 16, w / 2 - 12, 7), '#9fd07a', { rim: '#c3e8a0', shade: '#7fb75a', sw: 3, blur: 5, sy: 3, sc: 'rgba(60,80,40,.3)' });
  for (let i = 0; i < n; i++) {
    const x = -w / 2 + 17 + gap * i, y = 6 - (i === 1 ? 4 : 0) + (r() - .5) * 2;
    c.strokeStyle = '#86bb63'; c.lineWidth = 2.4; c.lineCap = 'round'; c.beginPath(); c.moveTo(x, y + 4); c.lineTo(x + (i - 1) * 2, 16); c.stroke();
    c.fillStyle = 'rgba(90,70,80,.14)'; c.beginPath(); c.arc(x + 1.5, y + 3, rr, 0, TAU); c.fill();
    c.fillStyle = 'rgba(255,253,246,.62)'; c.beginPath(); c.arc(x, y, rr - 2, 0, TAU); c.fill();
    const m = 24;
    c.strokeStyle = 'rgba(160,136,100,.6)'; c.lineWidth = .9; c.beginPath();
    for (let k = 0; k < m; k++) { const a = k / m * TAU + r() * .1; c.moveTo(x, y); c.lineTo(x + Math.cos(a) * (rr - 1), y + Math.sin(a) * (rr - 1)); }
    c.stroke();
    for (let k = 0; k < m; k++) { const a = k / m * TAU + .1; puff(c, x + Math.cos(a) * rr, y + Math.sin(a) * rr, 2.7); }
    c.fillStyle = '#d6b483'; c.beginPath(); c.arc(x, y, 2.4, 0, TAU); c.fill();
  }
}
const PW = 140, PH = 64, POX = 70 + 20, POY = 24;   // коробка спрайта опоры: ширина w+60
function platSpr(skin, w, v) {
  return spr('p:' + skin + w + ':' + v, w + 60, PH, w / 2 + 30, POY, (c) => {
    if (skin === 'leaf') drawLeaf(c, w, v, false);
    else if (skin === 'dry') drawLeaf(c, w, v, true);
    else if (skin === 'twig') drawTwig(c, w, v);
    else if (skin === 'fluff') drawFluff(c, w, v);
    else drawCloudPlat(c, w, v, skin);
  });
}
void PW; void POX;

/* ---------------- предметы и жители ---------------- */
function starP(cx, cy, r1, r2, rad) { const pts = []; for (let i = 0; i < 10; i++) { const a = -Math.PI / 2 + i * Math.PI / 5, r = i % 2 ? r2 : r1; pts.push([cx + Math.cos(a) * r, cy + Math.sin(a) * r]); } return roundPoly(pts, rad); }
function drawStar(c) {
  cut(c, starP(0, 1, 19, 9.5, 3.6), '#ffd04d', { rim: '#fff0a6', shade: '#efa92c', sw: 3.5, sc: 'rgba(120,70,20,.25)' });
  c.fillStyle = '#7a4a2a'; c.beginPath(); c.arc(-4.6, 1, 1.7, 0, TAU); c.arc(4.6, 1, 1.7, 0, TAU); c.fill();
  c.strokeStyle = '#7a4a2a'; c.lineWidth = 1.4; c.lineCap = 'round'; c.beginPath(); c.arc(0, 3.6, 2.4, .2 * Math.PI, .8 * Math.PI); c.stroke();
  c.fillStyle = 'rgba(255,130,120,.55)'; c.beginPath(); c.ellipse(-8, 5, 2.6, 1.6, 0, 0, TAU); c.ellipse(8, 5, 2.6, 1.6, 0, 0, TAU); c.fill();
}
function drawBerry(c) {
  const b = new Path2D(); b.moveTo(0, 17); b.bezierCurveTo(-15, 9, -18, -5, -10, -10); b.quadraticCurveTo(0, -14, 10, -10); b.bezierCurveTo(18, -5, 15, 9, 0, 17); b.closePath();
  cut(c, b, '#ff5d70', { rim: '#ff9ea9', shade: '#df4459', sw: 4, sc: 'rgba(120,20,40,.25)' });
  c.fillStyle = '#ffe49c';
  for (const [x, y] of [[-7, -3], [0, -5], [7, -3], [-4, 4], [4, 4], [0, 10], [-9, 4], [9, 4]]) { c.beginPath(); c.ellipse(x, y, 1.2, 1.8, 0, 0, TAU); c.fill(); }
  const pts = []; for (let i = 0; i < 10; i++) { const a = -Math.PI / 2 + i * Math.PI / 5, r = i % 2 ? 3.5 : 9.5; pts.push([Math.cos(a) * r, -11 + Math.sin(a) * r * .55]); }
  cut(c, roundPoly(pts, 1.5), '#6cc15a', { rim: '#9be088', shade: '#4f9e44', sw: 1.5, rw: 1, blur: 2, sy: 1 });
  c.strokeStyle = '#4f9e44'; c.lineWidth = 2.2; c.lineCap = 'round'; c.beginPath(); c.moveTo(0, -13); c.quadraticCurveTo(1, -19, 4, -21); c.stroke();
}
const itemSpr = (kind) => spr('i:' + kind, 56, 56, 28, 28, (c) => (kind === 'star' ? drawStar(c) : drawBerry(c)));
function drawBalloonBody(c) {
  cut(c, ell(0, -36, 25, 31), '#ff8ca2', { rim: '#ffbdc9', shade: '#e7687f', sw: 6, sc: 'rgba(130,30,60,.25)' });
  c.fillStyle = 'rgba(255,255,255,.6)'; c.beginPath(); c.ellipse(-9, -49, 5.5, 10, -.45, 0, TAU); c.fill();
  c.fillStyle = '#e7687f'; c.beginPath(); c.moveTo(0, -6); c.lineTo(-5, 1); c.lineTo(5, 1); c.closePath(); c.fill();
}
const balloonSpr = () => spr('balloon', 64, 84, 32, 76, drawBalloonBody);
function drawBugSpr(c, awake) {
  cut(c, circ(0, -8, 27), '#7f89e4', { rim: '#abb3f7', shade: '#5f68c6', sw: 6, sc: 'rgba(30,30,90,.3)' });
  c.strokeStyle = '#5a62b9'; c.lineWidth = 2; c.beginPath(); c.moveTo(0, -35); c.lineTo(0, 6); c.stroke();
  c.fillStyle = '#b5bbf8'; for (const [x, y, r] of [[-13, -18, 5], [12, -22, 4], [-16, -2, 4], [15, -5, 5], [-6, -28, 3]]) { c.beginPath(); c.arc(x, y, r, 0, TAU); c.fill(); }
  cut(c, circ(0, 12, 15), '#575ca6', { rim: '#7a7fc8', shade: '#3f4385', sw: 4, blur: 4 });
  if (awake) {
    c.fillStyle = '#fff'; c.beginPath(); c.arc(-6, 11, 4.4, 0, TAU); c.arc(6, 11, 4.4, 0, TAU); c.fill();
    c.fillStyle = '#2b2550'; c.beginPath(); c.arc(-6, 11, 2.1, 0, TAU); c.arc(6, 11, 2.1, 0, TAU); c.fill();
    c.fillStyle = '#2b2550'; c.beginPath(); c.ellipse(0, 19, 2.4, 2.8, 0, 0, TAU); c.fill();
  } else {
    c.strokeStyle = '#f4efff'; c.lineWidth = 2; c.lineCap = 'round'; c.beginPath(); c.arc(-6, 9, 3.8, .15 * Math.PI, .85 * Math.PI); c.stroke(); c.beginPath(); c.arc(6, 9, 3.8, .15 * Math.PI, .85 * Math.PI); c.stroke();
    c.beginPath(); c.arc(0, 17, 2.2, .1 * Math.PI, .9 * Math.PI); c.stroke();
  }
  c.fillStyle = 'rgba(255,150,190,.75)'; c.beginPath(); c.ellipse(-11, 16, 3.6, 2.2, 0, 0, TAU); c.ellipse(11, 16, 3.6, 2.2, 0, 0, TAU); c.fill();
  /* ночной колпак */
  const cap = new Path2D(); cap.moveTo(-15, 5); cap.bezierCurveTo(-14, -12, 6, -16, 16, -8); cap.quadraticCurveTo(26, -2, 29, 10); cap.quadraticCurveTo(19, 0, 12, 3); cap.quadraticCurveTo(0, 6, -15, 5); cap.closePath();
  cut(c, cap, '#fff1df', { shade: '#efcfb6', sw: 2.5, blur: 3, sy: 2 });
  c.save(); c.clip(cap); c.fillStyle = '#f69db3';
  for (let i = -3; i < 6; i++) { c.beginPath(); c.moveTo(-20 + i * 9, 12); c.lineTo(-14 + i * 9, 12); c.lineTo(-4 + i * 9, -18); c.lineTo(-10 + i * 9, -18); c.closePath(); c.fill(); }
  c.restore();
  cut(c, rrPath(-16, 1, 30, 7, 3.5), '#fff6ea', { shade: '#ead2bd', sw: 2, blur: 2, sy: 1.5 });
  cut(c, circ(29, 11, 5), '#ffffff', { shade: '#e6dfe8', sw: 2, blur: 2, sy: 1.5 });
}
const bugSpr = (awake) => spr('bug' + (awake ? 1 : 0), 84, 84, 40, 48, (c) => drawBugSpr(c, awake));

/* ---------------- Тимоша ----------------
   Сонный человечек в полосатой пижаме и длинном ночном колпаке с помпоном: тело-фасолинка, круглая голова, нос-картошка,
   глаза-точки, румянец, тонкие ручки-ножки и большие тапочки. Колпак болтается на пружинке (h.crest) и развевается
   в прыжке. Начало координат — у подошв, всё в бумажной аппликации: цветной лист + мягкая тень под ним. */
function puff(c, x, y, r) {
  c.fillStyle = 'rgba(90,60,70,.12)'; c.beginPath(); c.arc(x + .8, y + 1.6, r, 0, TAU); c.fill();
  c.fillStyle = '#fffdf6'; c.beginPath(); c.arc(x, y, r, 0, TAU); c.fill();
  c.strokeStyle = 'rgba(205,188,150,.8)'; c.lineWidth = .9; c.beginPath();
  for (let k = 0; k < 7; k++) { const a = k / 7 * TAU; c.moveTo(x + Math.cos(a) * r * .35, y + Math.sin(a) * r * .35); c.lineTo(x + Math.cos(a) * r * 1.05, y + Math.sin(a) * r * 1.05); }
  c.stroke();
}
const TM = { skin: '#ffd8b5', skinSh: '#f0b48f', skinHi: '#ffe9d4', nose: '#ffae8a', pj: '#dce9f8', pjSt: '#9dc3ea', pjSh: '#b3cbea', pjHi: '#eef5fd',
  cap: '#6070c8', capSh: '#4a58a8', capHi: '#8290de', brim: '#fff6e2', slip: '#f08a7e', slipSh: '#d46c62', slipHi: '#ffb2a6', line: '#3a2a45' };
function shadowFill(c, p, col, dx = 1.8, dy = 2.8, a = .17) { c.fillStyle = `rgba(80,40,70,${a})`; c.save(); c.translate(dx, dy); c.fill(p); c.restore(); c.fillStyle = col; c.fill(p); }
function limb(c, x0, y0, x1, y1, bend, col, w) { c.strokeStyle = col; c.lineWidth = w; c.lineCap = 'round'; c.beginPath(); c.moveTo(x0, y0); c.quadraticCurveTo((x0 + x1) / 2 + bend, (y0 + y1) / 2 + Math.abs(bend) * .3, x1, y1); c.stroke(); }
function hand(c, x, y) { c.fillStyle = 'rgba(80,40,70,.15)'; c.beginPath(); c.arc(x + .8, y + 1.4, 3.9, 0, TAU); c.fill(); c.fillStyle = TM.skin; c.beginPath(); c.arc(x, y, 3.9, 0, TAU); c.fill(); }
function slipper(c, x, y, dir, rot) {
  c.save(); c.translate(x, y); c.rotate(rot);
  const p = new Path2D(); p.ellipse(dir * 3, 0, 10.5, 5.6, 0, 0, TAU);
  shadowFill(c, p, TM.slip, 1.2, 2.2);
  c.save(); c.clip(p); band(c, p, -2.2, TM.slipSh); c.restore();
  c.fillStyle = TM.slipHi; c.beginPath(); c.ellipse(dir * 3, -2.4, 6, 1.6, 0, 0, TAU); c.fill();
  puff(c, dir * 10.5, -2.6, 3.3);                                      // помпончик на носке тапочка
  c.restore();
}
const BODY = (() => { const p = new Path2D(); p.moveTo(0, -46); p.bezierCurveTo(13, -46, 18.5, -32, 17.5, -21); p.bezierCurveTo(16.5, -11, 9, -9, 0, -9); p.bezierCurveTo(-9, -9, -16.5, -11, -17.5, -21); p.bezierCurveTo(-18.5, -32, -13, -46, 0, -46); return p; })();
function drawUmbrella(c, k, t, hx, hy) {
  const r = 46 * k, cx = hx, cy = -116 + (1 - k) * 40, sw = Math.sin(t * 1.4) * .06;
  c.save(); c.translate(cx, cy); c.rotate(sw);
  c.strokeStyle = '#8a5a48'; c.lineWidth = 2.6; c.lineCap = 'round';
  c.beginPath(); c.moveTo(0, -r * .02); c.lineTo(0, hy - cy + 6); c.arc(4, hy - cy + 6, 4, Math.PI, 0, true); c.stroke();   // ручка с крючком
  if (r > 4) {
    const n = 5, cap = new Path2D();
    cap.moveTo(-r, 0); cap.bezierCurveTo(-r, -r * .9, r, -r * .9, r, 0);
    for (let i = n - 1; i >= 0; i--) { const x0 = -r + (i + 1) * 2 * r / n, x1 = -r + i * 2 * r / n; cap.quadraticCurveTo((x0 + x1) / 2, -r * .2, x1, 0); }
    cap.closePath();
    shadowFill(c, cap, '#ff8f7d', 2, 4, .2);
    c.save(); c.clip(cap);
    c.fillStyle = '#fff1d8';
    for (let i = 1; i < n; i += 2) { const x0 = -r + i * 2 * r / n, x1 = x0 + 2 * r / n; c.beginPath(); c.moveTo(0, -r * .7); c.lineTo(x0, 0); c.lineTo(x1, 0); c.closePath(); c.fill(); }
    band(c, cap, -4, 'rgba(200,80,70,.25)');
    c.fillStyle = 'rgba(255,255,255,.45)'; c.beginPath(); c.ellipse(-r * .35, -r * .5, r * .22, r * .08, -.5, 0, TAU); c.fill();
    c.restore();
    c.fillStyle = '#8a5a48'; c.beginPath(); c.arc(0, -r * .68, 3, 0, TAU); c.fill();
  }
  c.restore();
}
function drawHero(c, h, t) {
  const face = h.face, d = h.dir || 1, lx = d * 2.6;
  const k = clamp(-h.vy / JUMP, 0, 1.6), fall = h.chute <= 0 && h.balT <= 0 && h.vy > 260, bal = h.balT > 0, umb = h.chute > 0;
  const rising = !bal && !umb && h.vy < -300, flail = h.dizzy > 0 || (fall && face === 'oops');
  c.save(); c.translate(h.x, h.y); c.scale(HSC, HSC);
  c.rotate(clamp(h.vx / HS, -1, 1) * .1 + (h.dizzy > 0 ? Math.sin(t * 18) * .12 : 0));
  let sy = 1 + h.sq, sx = 1 - h.sq * .9;
  if (h.vy < 0 && !bal) { const st = clamp(-h.vy / JUMP, 0, 1.6) * .05; sy *= 1 + st; sx *= 1 - st * .7; }
  c.scale(sx, sy);
  c.lineCap = 'round';
  /* поза: руки и ноги */
  let hl, hr;                                                       // кисти: [x, y]
  if (bal) { hl = [d * 23, -80]; hr = [d * 28, -74]; }                  // держится за нитку обеими руками
  else if (umb) { hl = [-d * 16, -26 + Math.sin(t * 2) * 1.5]; hr = [d * 25, -60]; }
  else if (flail) { hl = [-24, -48 + Math.sin(t * 24) * 7]; hr = [24, -48 + Math.sin(t * 24 + 2) * 7]; }
  else if (face === 'joy' && rising) { hl = [-21, -66]; hr = [21, -66]; } // восторг на пружинке — руки вверх
  else if (rising) { hl = [-23, -50]; hr = [23, -50]; }
  else if (fall) { hl = [-24, -40 + Math.sin(t * 9) * 3]; hr = [24, -40 - Math.sin(t * 9) * 3]; }
  else { hl = [-18, -23 + Math.sin(t * 3) * 1.5]; hr = [18, -23 - Math.sin(t * 3) * 1.5]; }
  const [hlx, hly] = d > 0 ? hl : [-hl[0], hl[1]], [hrx, hry] = d > 0 ? hr : [-hr[0], hr[1]];
  let fl, fr;                                                       // стопы
  if (rising) { fl = [-8, -9, -.2]; fr = [8, -9, .2]; }
  else if (fall || flail) { const w = Math.sin(t * 16) * 3; fl = [-13, -2 + w, -.35]; fr = [13, -2 - w, .35]; }
  else if (umb) { const w = Math.sin(t * 2.2) * 2; fl = [-9, -4 + w, -.15]; fr = [9, -4 - w, .15]; }
  else { fl = [-9, -5, 0]; fr = [9, -5, 0]; }
  /* шарик */
  if (bal) {
    const bx = d * 34 + Math.sin(t * 3) * 3, by = -142;
    c.strokeStyle = '#b9767f'; c.lineWidth = 1.6; c.beginPath(); c.moveTo(d * 25, -78); c.bezierCurveTo(d * 27, -96, bx - d * 6, by + 26, bx, by); c.stroke();
    blit(c, balloonSpr(), bx, by);
  }
  if (umb) drawUmbrella(c, h.chute, t, d * 25, -60);
  /* ножки и тапочки */
  limb(c, -6, -13, fl[0], fl[1] - 2, -2, TM.pjSt, 4.2);
  limb(c, 6, -13, fr[0], fr[1] - 2, 2, TM.pjSt, 4.2);
  slipper(c, fl[0], fl[1], d, fl[2]); slipper(c, fr[0], fr[1], d, fr[2]);
  /* тело-фасолинка в полосатой пижаме */
  shadowFill(c, BODY, TM.pj, 2.2, 3.4);
  c.save(); c.clip(BODY);
  c.fillStyle = TM.pjSt; for (let x = -17; x < 18; x += 7.5) c.fillRect(x + lx * .4, -48, 3.2, 42);
  band(c, BODY, -4.5, 'rgba(120,150,200,.35)'); band(c, BODY, 2.5, 'rgba(255,255,255,.5)');
  c.restore();
  c.fillStyle = '#fff'; for (const y of [-34, -25]) { c.beginPath(); c.arc(lx * .8, y, 1.9, 0, TAU); c.fill(); }
  /* ручки (рукава пижамы) и кисти */
  limb(c, -13, -38, hlx, hly, -d * 3, TM.pjSt, 4.4); limb(c, 13, -38, hrx, hry, d * 3, TM.pjSt, 4.4);
  hand(c, hlx, hly); hand(c, hrx, hry);
  /* голова */
  const hx = lx * .9, hy = -54;
  for (const sd of [-1, 1]) { c.fillStyle = TM.skinSh; c.beginPath(); c.arc(hx + sd * 16, hy + 1, 4, 0, TAU); c.fill(); }
  const head = circ(hx, hy, 16.5);
  shadowFill(c, head, TM.skin, 2, 3);
  c.save(); c.clip(head); band(c, head, -3.5, 'rgba(232,160,120,.45)'); c.restore();
  /* мордочка: глаза-точки, нос-картошка, румянец, рот */
  const ex = 5.6, ey = hy - 1;
  c.fillStyle = 'rgba(255,120,140,.5)'; c.beginPath(); c.ellipse(hx - 10.5, hy + 5, 3.8, 2.5, 0, 0, TAU); c.ellipse(hx + 10.5, hy + 5, 3.8, 2.5, 0, 0, TAU); c.fill();
  c.strokeStyle = TM.line; c.fillStyle = TM.line; c.lineWidth = 2;
  if (face === 'joy') {
    for (const sd of [-1, 1]) { c.beginPath(); c.arc(hx + sd * ex, ey + 1.5, 2.8, 1.1 * Math.PI, 1.9 * Math.PI); c.stroke(); }
  } else if (face === 'calm') {
    for (const sd of [-1, 1]) { c.beginPath(); c.arc(hx + sd * ex, ey - 1, 2.8, .15 * Math.PI, .85 * Math.PI); c.stroke(); }
  } else if (face === 'oops') {
    for (const sd of [-1, 1]) { c.fillStyle = '#fff'; c.beginPath(); c.arc(hx + sd * ex, ey - .5, 3.8, 0, TAU); c.fill(); c.lineWidth = 1.2; c.stroke(); c.fillStyle = TM.line; c.beginPath(); c.arc(hx + sd * ex + d * .6, ey - .5, 1.8, 0, TAU); c.fill(); }
  } else if (h.blink > 0 && h.blink < .12) {
    for (const sd of [-1, 1]) { c.beginPath(); c.moveTo(hx + sd * ex - 2.4, ey); c.lineTo(hx + sd * ex + 2.4, ey); c.stroke(); }
  } else {
    for (const sd of [-1, 1]) { c.beginPath(); c.arc(hx + sd * ex, ey, 2.2, 0, TAU); c.fill(); }
  }
  const nx = hx + d * 1.4, ny = hy + 3.5;
  c.fillStyle = 'rgba(200,110,80,.25)'; c.beginPath(); c.ellipse(nx + .8, ny + 1.2, 4.8, 3.9, 0, 0, TAU); c.fill();
  c.fillStyle = TM.nose; c.beginPath(); c.ellipse(nx, ny, 4.8, 3.9, d * .15, 0, TAU); c.fill();
  c.fillStyle = 'rgba(255,255,255,.6)'; c.beginPath(); c.ellipse(nx - 1.6, ny - 1.4, 1.5, 1, 0, 0, TAU); c.fill();
  const my = hy + 9.5;
  c.strokeStyle = TM.line; c.lineWidth = 1.7;
  if (face === 'joy') {                                                // восторг: рот нараспашку
    c.fillStyle = '#7a2f3d'; c.beginPath(); c.ellipse(hx + d, my + 1, 4.2, 4.4, 0, 0, TAU); c.fill();
    c.fillStyle = '#ff8c9b'; c.beginPath(); c.ellipse(hx + d, my + 3.2, 2.8, 1.8, 0, 0, TAU); c.fill();
  } else if (face === 'oops') {
    c.fillStyle = '#7a2f3d'; c.beginPath(); c.ellipse(hx + d, my + 1, 2.2, 2.6, 0, 0, TAU); c.fill();
  } else if (face === 'calm') {                                        // мирно зевает под зонтиком
    const yawn = Math.max(0, Math.sin(t * 1.3)) ** 2;
    c.fillStyle = '#7a2f3d'; c.beginPath(); c.ellipse(hx + d, my + 1, 2.4 + yawn * 1.6, .9 + yawn * 3.8, 0, 0, TAU); c.fill();
    if (yawn > .6) { c.fillStyle = '#8a93d8'; c.font = `900 10px ${FONT}`; c.fillText('z', hx - d * 24, hy - 4 - yawn * 5); c.font = `900 7px ${FONT}`; c.fillText('z', hx - d * 30, hy - 13 - yawn * 5); }
  } else { c.beginPath(); c.arc(hx + d, my - 1.5, 2.8, .2 * Math.PI, .8 * Math.PI); c.stroke(); }
  /* ночной колпак: болтается с задержкой, в прыжке развевается */
  const f = clamp(h.vy / 1200, 0, 1) * (umb ? .3 : 1);
  const th = -d * (1.0 + .5 * Math.min(1, k) - .75 * f) + h.crest * 1.3 + Math.sin(t * 15) * .1 * Math.min(1, k);
  const L = 31, mx = hx + d * .5, myy = hy - 15, tx = mx + Math.sin(th) * L, ty = myy - Math.cos(th) * L;
  const cone = new Path2D();
  cone.moveTo(hx - 15.5, hy - 7);
  cone.quadraticCurveTo(hx - 13 + (tx - mx) * .45, myy - 6 + (ty - myy) * .45, tx, ty);
  cone.quadraticCurveTo(hx + 13 + (tx - mx) * .55, myy - 2 + (ty - myy) * .55, hx + 15.5, hy - 7);
  cone.closePath();
  shadowFill(c, cone, TM.cap, 1.8, 2.6);
  c.save(); c.clip(cone); band(c, cone, -3, TM.capSh); band(c, cone, 2.4, TM.capHi);
  c.fillStyle = '#ffd65a'; for (const q of [.35, .68]) { const px = hx + (tx - hx) * q + (q - .5) * 4, py = hy - 10 + (ty - hy + 10) * q; c.fill(starP(px, py, 2.6, 1.2, 0)); }
  c.restore();
  const brim = rrPath(hx - 17, hy - 13, 34, 6.5, 3.2);
  shadowFill(c, brim, TM.brim, 1, 2);
  c.fillStyle = 'rgba(205,188,150,.45)'; c.fillRect(hx - 14.5, hy - 8.2, 29, 1);
  puff(c, tx, ty, 6.6);
  if (face === 'oops' && !umb) { c.fillStyle = '#a9dcff'; c.beginPath(); c.moveTo(hx + 18, hy - 12); c.quadraticCurveTo(hx + 23, hy - 4, hx + 18, hy - 2); c.quadraticCurveTo(hx + 13, hy - 4, hx + 18, hy - 12); c.fill(); }
  if (h.dizzy > 0) {
    c.fillStyle = '#ffd04d';
    for (let i = 0; i < 3; i++) { const a = t * 7 + i * 2.1; c.fill(starP(hx + Math.cos(a) * 22, hy - 30 + Math.sin(a) * 6, 5.5, 2.6, 1)); }
  }
  c.restore();
}

/* ---------------- пружинка ---------------- */
function drawSpring(c, x, y, ext) {
  const hg = 22 * (1 + ext), n = 4;
  c.lineCap = 'round';
  c.fillStyle = '#c4566a'; c.beginPath(); c.ellipse(x, y - 1, 15, 4, 0, 0, TAU); c.fill();
  for (let i = 0; i < n; i++) {
    const yy = y - 3 - hg * (i + .5) / n;
    c.strokeStyle = '#c4566a'; c.lineWidth = 3.4; c.beginPath(); c.ellipse(x, yy, 12, 4, 0, Math.PI, TAU); c.stroke();
    c.strokeStyle = '#ff8478'; c.lineWidth = 4; c.beginPath(); c.ellipse(x, yy, 12, 4, 0, 0, Math.PI); c.stroke();
    c.strokeStyle = 'rgba(255,255,255,.6)'; c.lineWidth = 1.3; c.beginPath(); c.ellipse(x, yy, 12, 4, 0, .3 * Math.PI, .55 * Math.PI); c.stroke();
  }
  const ty = y - 5 - hg;
  c.fillStyle = 'rgba(80,30,40,.18)'; c.beginPath(); c.ellipse(x + 1, ty + 3, 15, 6, 0, 0, TAU); c.fill();
  c.fillStyle = '#ffd25e'; c.beginPath(); c.ellipse(x, ty, 15, 6, 0, 0, TAU); c.fill();
  c.fillStyle = '#ffeaa0'; c.beginPath(); c.ellipse(x - 3, ty - 1.6, 8, 2.4, 0, 0, TAU); c.fill();
}

/* ---------------- декорации (дальний и средний планы) ---------------- */
function treeSpr(v) {
  return spr('d:tree' + v, 340, 560, 170, 150, (c) => {
    const r = rng(hash('tree' + v));
    const trunk = new Path2D(); trunk.moveTo(-20, 40); trunk.quadraticCurveTo(-14, 200, -26, 410); trunk.lineTo(26, 410); trunk.quadraticCurveTo(14, 200, 20, 40); trunk.closePath();
    cut(c, trunk, '#cfae8c', { rim: '#e3c8aa', shade: '#b8946f', sw: 4, sc: 'rgba(60,70,60,.14)' });
    c.strokeStyle = 'rgba(160,120,90,.4)'; c.lineWidth = 2; c.beginPath(); for (let i = 0; i < 6; i++) { const y = 90 + i * 50; c.moveTo(-8 + r() * 6, y); c.lineTo(-2 + r() * 8, y + 22); } c.stroke();
    const blobs = [[-80, 20, 82], [70, 10, 92], [0, -50, 98], [-30, 50, 90], [90, 70, 72], [-100, 80, 60]];
    const cols = ['#a9d596', '#b7dda3', '#c4e5b2'];
    blobs.forEach(([x, y, rr], i) => cut(c, circ(x + (r() - .5) * 10, y, rr), cols[i % 3], { rim: '#d3edc4', shade: '#98c787', sw: 7, sc: 'rgba(50,90,60,.16)', blur: 9 }));
    for (let i = 0; i < 9; i++) { const a = r() * TAU, d = r() * 90; c.fillStyle = r() < .5 ? '#ffc0c0' : '#fff2f2'; c.beginPath(); c.arc(Math.cos(a) * d, 10 + Math.sin(a) * d * .8, 5, 0, TAU); c.fill(); }
  });
}
function decorSpr(kind, v) {
  const r0 = rng(hash(kind + v));
  switch (kind) {
    case 'tree': return treeSpr(v);
    case 'cloudlet': return spr('d:cl' + v, 280, 120, 140, 70, (c) => softCloud(c, 220, 34, r0, 'rgba(255,255,255,.5)', 'rgba(255,255,255,.35)', 1.5));
    case 'fartree': return spr('d:ft' + v, 300, 300, 150, 150, (c) => {
      for (const [x, s] of [[-80, .8], [10, 1], [90, .7]]) {
        c.fillStyle = '#c9b9a6'; c.fillRect(x - 5, 20 * s, 10, 120);
        cut(c, circ(x, 0, 58 * s), '#c5e2cf', { shade: '#b0d3bd', sw: 6, sc: 'rgba(70,110,110,.1)', blur: 8, ga: .5 });
      }
    });
    case 'branch': return spr('d:br' + v, 380, 180, 10, 90, (c) => {
      try { c.filter = `blur(${(1.6 * SS).toFixed(1)}px)`; } catch (e) { /* без размытия */ }
      const p = new Path2D(); p.moveTo(-10, -14); p.quadraticCurveTo(150, -30, 300, -6); p.quadraticCurveTo(150, -12, -10, 14); p.closePath();
      c.fillStyle = 'rgba(214,190,160,.75)'; c.fill(p);
      c.fillStyle = 'rgba(190,226,172,.8)';
      for (let i = 0; i < 9; i++) { const x = 30 + i * 30, a = i % 2 ? -1.1 - r0() * .5 : 1.1 + r0() * .5, L = 30 + r0() * 10; c.save(); c.translate(x, -6 - x * .02); c.rotate(a); c.beginPath(); c.moveTo(0, 0); c.quadraticCurveTo(L * .5, -L * .34, L, 0); c.quadraticCurveTo(L * .5, L * .34, 0, 0); c.fill(); c.restore(); }
    });
    case 'bank': return spr('d:bk' + v, 600, 200, 300, 130, (c) => softCloud(c, 520, 60, r0, 'rgba(255,255,255,.4)', 'rgba(255,255,255,.3)', 3));
    case 'cloud': return spr('d:cd' + v, 420, 170, 210, 110, (c) => softCloud(c, 360, 50, r0, 'rgba(255,255,255,.58)', 'rgba(255,255,255,.4)', 2));
    case 'pinkcloud': return spr('d:pk' + v, 420, 170, 210, 110, (c) => softCloud(c, 360, 50, r0, 'rgba(255,214,200,.5)', 'rgba(255,238,228,.45)', 2));
    case 'bank2': return spr('d:b2' + v, 600, 200, 300, 130, (c) => softCloud(c, 520, 56, r0, 'rgba(255,222,206,.4)', 'rgba(255,240,232,.3)', 3));
    case 'streak': return spr('d:st' + v, 640, 110, 320, 55, (c) => {
      try { c.filter = `blur(${(3 * SS).toFixed(1)}px)`; } catch (e) { /* без размытия */ }
      c.fillStyle = 'rgba(255,214,192,.42)'; c.fill(rrPath(-280, -22, 460, 20, 10)); c.fill(rrPath(-120, 10, 400, 14, 7));
    });
    case 'birds': return spr('d:bd' + v, 200, 100, 100, 50, (c) => {
      c.strokeStyle = 'rgba(110,70,110,.6)'; c.lineWidth = 3; c.lineCap = 'round'; c.lineJoin = 'round';
      for (const [x, y, s] of [[-50, 10, 1], [0, -16, .8], [44, 6, .9]]) { c.beginPath(); c.moveTo(x - 14 * s, y - 4 * s); c.quadraticCurveTo(x - 6 * s, y - 9 * s, x, y); c.quadraticCurveTo(x + 6 * s, y - 9 * s, x + 14 * s, y - 4 * s); c.stroke(); }
    });
    case 'lavcloud': return spr('d:lv' + v, 420, 170, 210, 110, (c) => softCloud(c, 360, 50, r0, 'rgba(120,110,190,.42)', 'rgba(160,150,220,.3)', 2));
    case 'nfar': return spr('d:nf' + v, 600, 200, 300, 130, (c) => softCloud(c, 520, 56, r0, 'rgba(70,64,134,.45)', 'rgba(100,92,170,.25)', 3));
    case 'hills': return spr('d:hills', WW + 160, 420, (WW + 160) / 2, 0, (c) => {
      const r = rng(3), wv = (y0, amp, f, ph) => { const p = new Path2D(); p.moveTo(-WW, 420); for (let x = -(WW + 160) / 2; x <= (WW + 160) / 2; x += 20) p.lineTo(x, y0 - amp * Math.sin(x * f + ph) - amp * .4 * Math.sin(x * f * 2.3 + ph)); p.lineTo(WW, 420); p.closePath(); return p; };
      cut(c, wv(110, 40, .007, 1), '#d3eacb', { rim: '#e2f1dc', shade: '#c5e1bc', sw: 6, sc: 'rgba(60,110,90,.1)', blur: 10, ga: .5 });
      for (let i = 0; i < 6; i++) { const x = -330 + i * 130 + r() * 40, y = 120 - 30 * Math.sin(x * .007 + 1) + 6; c.fillStyle = '#c4b49c'; c.fillRect(x - 3, y - 26, 6, 26); cut(c, circ(x, y - 34, 16 + r() * 6), '#b8dca6', { shade: '#a5cf93', sw: 4, blur: 4, sy: 2, ga: .5 }); }
      /* домик вдали */
      cut(c, rrPath(150, 98, 46, 34, 3), '#fff6ea', { shade: '#eadfce', sw: 3, blur: 4, sy: 2 });
      const roof = new Path2D(); roof.moveTo(144, 100); roof.lineTo(173, 76); roof.lineTo(202, 100); roof.closePath(); cut(c, roof, '#f39b8e', { shade: '#d97b70', sw: 3, blur: 3, sy: 2 });
      c.fillStyle = '#ffd77a'; c.fillRect(160, 108, 9, 9);
      cut(c, wv(190, 30, .009, 3), '#bfe2ab', { rim: '#d4edc4', shade: '#acd698', sw: 6, sc: 'rgba(60,110,70,.12)', blur: 10, ga: .5 });
    });
    default: return null;
  }
}
/* дальние и средние облака — без тени и тёмного края, полупрозрачные и чуть размытые: фон не путается с опорами */
function softCloud(c, w, h, r, fill, rim, blur) {
  const p = cloudShape(w, h, r, 6, .62);
  c.save(); try { c.filter = `blur(${(blur * SS).toFixed(1)}px)`; } catch (e) { /* без размытия */ }
  c.fillStyle = fill; c.fill(p);
  c.restore();
  c.save(); c.clip(p); band(c, p, 4, rim); grainFill(c, .35); c.restore();
}
const DECOR = {
  far: [['cloudlet', 'cloudlet', null], ['fartree', 'cloudlet', 'fartree'], ['bank', 'cloudlet', 'bank'], ['streak', 'bank2', 'streak'], ['nfar', null, null]],
  mid: [['bfly', 'cloudlet', null, 'bfly'], ['tree', 'tree', 'branch', 'bfly'], ['cloud', 'cloud', null], ['pinkcloud', 'birds', 'pinkcloud'], ['lavcloud', null, 'lavcloud']]
};
const LAY = [{ key: 'far', p: .22, gap: [320, 480] }, { key: 'mid', p: .55, gap: [230, 380] }];
function drawBfly(c, d, Y, t) {
  const x = d.x + Math.sin(t * .7 + d.ph) * 70, y = Y + Math.cos(t * .9 + d.ph) * 34, f = .3 + .7 * Math.abs(Math.sin(t * 9 + d.ph));
  const cols = [['#ff9fb6', '#ffc5d3'], ['#ffd36b', '#ffe7a6'], ['#a7d8ff', '#d2ecff']][d.v % 3];
  c.save(); c.translate(x, y); c.rotate(Math.sin(t * 1.3 + d.ph) * .25);
  for (const s of [-1, 1]) {
    c.save(); c.scale(s * f, 1);
    c.fillStyle = 'rgba(80,40,80,.12)'; c.beginPath(); c.ellipse(9, -5, 10, 8, -.5, 0, TAU); c.fill();
    c.fillStyle = cols[0]; c.beginPath(); c.ellipse(8, -7, 10, 8, -.5, 0, TAU); c.fill();
    c.fillStyle = cols[1]; c.beginPath(); c.ellipse(7, 5, 6.5, 5, .5, 0, TAU); c.fill();
    c.restore();
  }
  c.strokeStyle = '#6b4a6b'; c.lineWidth = 3; c.lineCap = 'round'; c.beginPath(); c.moveTo(0, -8); c.lineTo(0, 8); c.stroke();
  c.restore();
}

/* земля луга со знаком «к луне» */
function groundSpr() {
  return spr('ground', WW, 620, 0, 160, (c) => {
    const r = rng(21);
    /* одуванчики-великаны по краям луга */
    for (const [x, hgt, bend] of [[64, 150, 14], [118, 104, -10], [WW - 70, 132, -12]]) {
      c.strokeStyle = '#7fb85a'; c.lineWidth = 4; c.lineCap = 'round'; c.beginPath(); c.moveTo(x, 10); c.quadraticCurveTo(x + bend, -hgt * .5, x + bend * .4, -hgt); c.stroke();
      const hx = x + bend * .4, hy = -hgt - 10;
      cut(c, circ(hx, hy, 23), 'rgba(255,255,255,.55)', { shadow: false, ga: .4 });
      for (let i = 0; i < 16; i++) { const a = i / 16 * TAU; c.strokeStyle = 'rgba(190,170,130,.6)'; c.lineWidth = 1; c.beginPath(); c.moveTo(hx, hy); c.lineTo(hx + Math.cos(a) * 21, hy + Math.sin(a) * 21); c.stroke(); puff(c, hx + Math.cos(a) * 22, hy + Math.sin(a) * 22, 4.2); }
      c.fillStyle = '#c99c64'; c.beginPath(); c.arc(hx, hy, 4, 0, TAU); c.fill();
    }
    /* дальний пригорок */
    const back = new Path2D(); back.moveTo(0, 600); back.lineTo(0, -10);
    for (let x = 0; x <= WW; x += 24) back.lineTo(x, -16 - 18 * Math.sin(x * .011 + 1) - 8 * Math.sin(x * .03));
    back.lineTo(WW, 600); back.closePath();
    cut(c, back, '#b3de8f', { rim: '#cdeba8', shade: '#9fd07c', sw: 6, sc: 'rgba(60,110,50,.16)', blur: 9 });
    /* знак-указатель */
    c.fillStyle = '#b98256'; c.fillRect(604, -112, 10, 124);
    c.fillStyle = 'rgba(80,40,30,.2)'; c.fillRect(614, -110, 3, 120);
    const sign = new Path2D(); sign.moveTo(566, -150); sign.lineTo(652, -150); sign.lineTo(652, -110); sign.lineTo(566, -110); sign.closePath();
    const arrow = new Path2D(); arrow.moveTo(609, -192); arrow.lineTo(636, -160); arrow.lineTo(582, -160); arrow.closePath();
    cut(c, arrow, '#ff8a7a', { rim: '#ffb1a5', shade: '#e2685c', sw: 3, blur: 4, sy: 2 });
    cut(c, sign, '#fff4dc', { rim: '#ffffff', shade: '#ecd9b9', sw: 3, blur: 5, sy: 3 });
    txt(c, 'к луне', 609, -129, 22, INK, { w: 800, align: 'center' });
    /* передний луг */
    const front = new Path2D(); front.moveTo(0, 600); front.lineTo(0, 4);
    for (let x = 0; x <= WW; x += 18) { front.quadraticCurveTo(x + 9, -6 - r() * 6, x + 18, 3 + r() * 2); }
    front.lineTo(WW, 600); front.closePath();
    cut(c, front, '#8fcb62', { rim: '#bce68f', shade: '#7cba55', sw: 5, sc: 'rgba(50,90,40,.24)', blur: 8, rw: 3 });
    const layer = (y0, col, sh) => { const p = new Path2D(); p.moveTo(0, 600); p.lineTo(0, y0); for (let x = 0; x <= WW; x += 30) p.quadraticCurveTo(x + 15, y0 - 10 + r() * 4, x + 30, y0 + r() * 4); p.lineTo(WW, 600); p.closePath(); cut(c, p, col, { shade: sh, sw: 4, sc: 'rgba(40,80,30,.2)', blur: 7 }); };
    layer(110, '#7dbb57', '#6fab4b'); layer(240, '#6eab4c', '#609a42'); layer(380, '#61a046', '#558f3d');
    /* ромашки, клевер, грибок */
    for (let i = 0; i < 16; i++) {
      const x = 20 + r() * (WW - 40), y = 20 + r() * 70; if (Math.abs(x - 360) < 50 && y < 40) continue;
      for (let k = 0; k < 6; k++) { const a = k / 6 * TAU; c.fillStyle = '#ffffff'; c.beginPath(); c.ellipse(x + Math.cos(a) * 5, y + Math.sin(a) * 5, 4.4, 2.4, a, 0, TAU); c.fill(); }
      c.fillStyle = '#ffcf4a'; c.beginPath(); c.arc(x, y, 3, 0, TAU); c.fill();
    }
    for (let i = 0; i < 10; i++) { const x = r() * WW, y = 140 + r() * 80; c.fillStyle = 'rgba(190,230,150,.7)'; for (let k = 0; k < 3; k++) { const a = k / 3 * TAU - Math.PI / 2; c.beginPath(); c.arc(x + Math.cos(a) * 4, y + Math.sin(a) * 4, 4, 0, TAU); c.fill(); } }
    c.fillStyle = '#f4e9d8'; c.fillRect(176, -12, 9, 16);
    const cap = new Path2D(); cap.moveTo(166, -10); cap.quadraticCurveTo(180, -32, 195, -10); cap.closePath();
    cut(c, cap, '#ff7b6b', { shade: '#df5d50', sw: 3, blur: 3, sy: 2 });
    c.fillStyle = '#fff'; c.beginPath(); c.arc(175, -17, 2.4, 0, TAU); c.arc(186, -15, 2, 0, TAU); c.fill();
  });
}
function sunSpr() {
  return spr('sun', 300, 300, 150, 150, (c) => {
    c.fillStyle = 'rgba(255,240,200,.35)'; c.beginPath(); c.arc(0, 0, 140, 0, TAU); c.fill();
    c.fillStyle = 'rgba(255,226,170,.45)'; c.beginPath(); c.arc(0, 0, 108, 0, TAU); c.fill();
    cut(c, circ(0, 0, 76), '#ffc45f', { rim: '#ffdc93', shade: '#f6a548', sw: 8, sc: 'rgba(200,90,60,.25)', blur: 14, ga: .6 });
  }, 1);
}
function moonSpr() {
  return spr('moon', 300, 300, 150, 150, (c) => {
    c.fillStyle = 'rgba(120,110,200,.18)'; c.beginPath(); c.arc(0, 0, 142, 0, TAU); c.fill();
    c.fillStyle = 'rgba(150,140,220,.18)'; c.beginPath(); c.arc(0, 0, 106, 0, TAU); c.fill();
    cut(c, circ(0, 0, 74), '#fff3cf', { rim: '#ffffff', shade: '#eed9a3', sw: 8, sc: 'rgba(0,0,30,.4)', blur: 18, ga: .6 });
    c.fillStyle = 'rgba(232,212,160,.55)';
    for (const [x, y, rr] of [[-34, -30, 11], [30, -40, 7], [40, 18, 9], [-46, 20, 6]]) { c.beginPath(); c.arc(x, y, rr, 0, TAU); c.fill(); }
    c.strokeStyle = '#b4935e'; c.lineWidth = 3.2; c.lineCap = 'round';
    c.beginPath(); c.arc(-20, -2, 9, .15 * Math.PI, .85 * Math.PI); c.stroke();
    c.beginPath(); c.arc(20, -2, 9, .15 * Math.PI, .85 * Math.PI); c.stroke();
    c.beginPath(); c.arc(0, 18, 7, .2 * Math.PI, .8 * Math.PI); c.stroke();
    c.fillStyle = 'rgba(255,160,150,.55)'; c.beginPath(); c.ellipse(-36, 14, 9, 5, 0, 0, TAU); c.ellipse(36, 14, 9, 5, 0, 0, TAU); c.fill();
  }, 1);
}
function starsSpr() {
  return spr('stars', COLW, H, 0, 0, (c) => {
    const r = rng(99);
    for (let i = 0; i < 90; i++) { c.fillStyle = `rgba(255,248,220,${.3 + r() * .6})`; c.beginPath(); c.arc(r() * COLW, r() * H, .8 + r() * 1.6, 0, TAU); c.fill(); }
    for (let i = 0; i < 14; i++) { c.fillStyle = r() < .5 ? '#fff3c4' : '#ffe08a'; c.fill(starP(r() * COLW, r() * H, 5 + r() * 3, 2.4, 1)); }
  }, 1);
}
function vignette() {
  return spr('vig', COLW, H, 0, 0, (c) => {
    const g = c.createRadialGradient(COLW / 2, H * .45, Math.min(COLW, H) * .35, COLW / 2, H * .5, Math.max(COLW, H) * .78);
    g.addColorStop(0, 'rgba(70,40,80,0)'); g.addColorStop(1, 'rgba(70,40,80,.16)');
    c.fillStyle = g; c.fillRect(0, 0, COLW, H);
  }, 1);
}
/* значки высот: луг, крона, облако, солнце, луна */
function drawIcon(c, i) {
  if (i === 0) { for (let k = 0; k < 6; k++) { const a = k / 6 * TAU; c.fillStyle = '#ffffff'; c.beginPath(); c.ellipse(Math.cos(a) * 9, Math.sin(a) * 9, 8, 4.6, a, 0, TAU); c.fill(); } cut(c, circ(0, 0, 6), '#ffcf4a', { blur: 2, sy: 1 }); return; }
  if (i === 1) { c.fillStyle = '#b98256'; c.fillRect(-3, 2, 6, 16); cut(c, circ(0, -6, 14), '#6fbd72', { rim: '#98d796', shade: '#58a35c', sw: 3, blur: 3, sy: 2 }); return; }
  if (i === 2) { cut(c, cloudShape(36, 9, rng(4), 0, .7), '#ffffff', { shade: '#d6e4f5', sw: 3, blur: 3, sy: 2, sc: 'rgba(60,80,140,.3)' }); return; }
  if (i === 3) { c.fillStyle = '#ffb36b'; for (let k = 0; k < 8; k++) { const a = k / 8 * TAU; c.save(); c.rotate(a); c.beginPath(); c.moveTo(13, -3); c.lineTo(19, 0); c.lineTo(13, 3); c.fill(); c.restore(); } cut(c, circ(0, 0, 10), '#ff9a6b', { rim: '#ffc19c', blur: 2, sy: 1 }); return; }
  const m = new Path2D(); m.arc(0, 0, 13, 0, TAU); const m2 = new Path2D(); m2.arc(6, -4, 11, 0, TAU);
  c.save(); const p = new Path2D(m); p.addPath(m2); c.save(); c.clip(p, 'evenodd'); cut(c, m, '#fff0b8', { rim: '#ffffff', shade: '#e7cf88', sw: 2, blur: 3, sy: 1 }); c.restore(); c.restore();
}
const iconSpr = (i) => spr('ico' + i, 48, 48, 24, 24, (c) => drawIcon(c, i), 1);

/* ---------------- состояние ---------------- */
const S = { mode: 'title', t: 0, speed: 1, bot: false, ctl: 'keys', tilt: 0, tiltRaw: 0, tiltN: 0, tiltN0: 0, tiltT0: null, tiltOk: false, bestAlt: 0 };
let RUN = 0;
function fresh() {
  Object.assign(S, {
    mode: 'title', t: 0, camY: -VH * .86, plats: [], items: [], bugs: [], winds: [], parts: [], far: [], mid: [],
    genY: 0, nextBalloon: 2500, nextBug: 3300, nextWind: 8200, maxAlt: 0, got: 0, streak: 0, streakT: 0, bio: 0,
    banner: null, tipT: 0, moved: 0, ground: true, dropT: 0, windNow: 0, windSeen: -1, shoot: null, shootT: 4, src: '',
    mouseSeen: false, botX: null, botSame: 0, botLast: null, jumps: 0, springs: 0, stomps: 0, bonks: 0, breaks: 0, balloons: 0, hopN: 0, ended: false
  });
  S.hero = { x: WW / 2, y: 0, ux: 0, vx: 0, vy: 0, wv: 0, dir: 1, sq: 0, sqv: 0, face: 'idle', faceT: 0, blink: 2.5, dizzy: 0, balT: 0, chute: 0, chuteOn: false, crest: 0, crestV: 0 };
  for (const L of LAY) S[L.key + 'Y'] = S.camY * L.p + VH + 240;
  S.far.push({ kind: 'hills', x: WW / 2, yl: S.camY * .22 + VH * .58, v: 0, flip: false, ph: 0 });
  gen(); decorGen();
}
function addPlat(x, y, type) {
  const alt = -y, d = diffAt(alt), bi = bioAt(alt + A.rand(-350, 350));
  const w = type === 'break' ? 118 : [136, 122, 108][Math.random() < d ? (Math.random() < d ? 2 : 1) : 0];
  const skin = type === 'break' ? 'dry' : type === 'once' ? 'fluff' : BIO[bi].skin;
  const p = { x, y, w, type, skin, v: (Math.random() * 3) | 0, vx: 0, t: 0, press: 0, bob: Math.random() * TAU, spring: null, balloon: null, broke: false, bt: 0, vanish: false, vt: 0, gone: false };
  if (type === 'move') { p.vx = (Math.random() < .5 ? -1 : 1) * lerp(70, 175, Math.min(1, d)); p.x = clamp(x, w / 2 + 8, WW - w / 2 - 8); }
  S.plats.push(p); return p;
}
/* лишняя опора между звеньями цепочки: ищем место, где она ни с кем не слипается */
function freeAt(x, y, w) {
  for (const p of S.plats) if (Math.abs(p.y - y) < 46 && Math.abs(wrapD(p.x - x)) < (p.w + w) / 2 + 24) return false;
  return true;
}
function addExtra(type, xc, y0, gap) {
  for (let i = 0; i < 6; i++) {
    const x = wrapX(xc + A.rand(170, 550)), y = y0 - gap * A.rand(.3, .7);
    if (freeAt(x, y, 122)) return addPlat(x, y, type);
  }
  return null;
}
function addItem(x, y, kind) {
  for (const p of S.plats) if (Math.abs(p.y - y) < 34 && Math.abs(wrapD(p.x - x)) < p.w / 2 + 22) return; S.items.push({ x, y, kind, ph: Math.random() * TAU, taken: false }); }
function gen() {
  while (S.genY > S.camY - 420) {
    const y0 = S.genY, alt = -y0, d = diffAt(alt);
    const dg = Math.min(1, d), gap = A.rand(lerp(74, 160, dg), lerp(108, 228, dg)), y = y0 - gap, x = A.rand(64, WW - 64);
    /* цепочка опор всегда проходима: обычные и едущие; одуванчики и сухие листики — только лишние, между ними,
       иначе после прыжка по одуванчику снизу не осталось бы пути наверх */
    const type = alt > 1300 && Math.random() < .08 + .24 * d ? 'move' : 'normal';
    const p = addPlat(x, y, type);
    if (alt > 4000 && Math.random() < .14 + .2 * d) addExtra('once', x, y0, gap);
    if (alt > 450 && Math.random() < .075) p.spring = { x: A.rand(-p.w / 2 + 24, p.w / 2 - 24), c: 0 };
    else if (type === 'normal' && alt > S.nextBalloon) { p.balloon = { off: A.rand(-16, 16), ph: Math.random() * TAU }; S.nextBalloon = alt + A.rand(3400, 5600); }
    if (alt < 6000 && Math.random() < .55 * (1 - alt / 6000)) addExtra('normal', x, y0, gap);
    if (alt > 650 && Math.random() < .12 + .3 * d) addExtra('break', x, y0, gap);
    const kind = BIO[bioAt(alt)].item;
    if (Math.random() < .14) { for (let k = -1; k <= 1; k++) addItem(wrapX(x + k * 46), y - 92 - (k ? 0 : 16), kind); }
    else if (Math.random() < .3) addItem(A.rand(50, WW - 50), y0 - gap * A.rand(.3, .8) - 30, kind);
    if (alt > S.nextBug && gap > 130 && Math.random() < .1 + .12 * d) {
      const bx = A.rand(90, WW - 90);
      S.bugs.push({ x: bx, x0: bx, y: y0 - gap * .5 - 12, y0: y0 - gap * .5 - 12, amp: A.rand(40, 110), sp: A.rand(.5, .9), ph: Math.random() * TAU, state: 'sleep', t: 0, at: 0, hitT: 0, vx: 0, vy: 0, dir: 1 });
      S.nextBug = alt + A.rand(900, 1700) * (1.3 - d * .6);
    }
    if (alt > S.nextWind) { const hh = A.rand(520, 760); S.winds.push({ y1: y, y0: y - hh, dir: Math.random() < .5 ? -1 : 1, ph: Math.random() * 10 }); S.nextWind = alt + hh + A.rand(2600, 4000); }
    S.genY = y;
  }
}
function decorGen() {
  for (const L of LAY) {
    const list = S[L.key], ky = L.key + 'Y';
    while (S[ky] > S.camY * L.p - 360) {
      S[ky] -= A.rand(L.gap[0], L.gap[1]);
      const yl = S[ky], altC = -(yl - VH * .5) / L.p - VH * .5 + A.rand(-450, 450);
      if (altC < 300 && L.key === 'far') continue;
      const kind = A.pick(DECOR[L.key][bioAt(Math.max(0, altC))]);
      if (!kind) continue;
      const edge = kind === 'tree' || kind === 'branch', flip = Math.random() < .5;
      const x = edge ? (flip ? WW + A.rand(-30, 30) : A.rand(-30, 30)) : A.rand(-30, WW + 30);
      list.push({ kind, x, yl, v: (Math.random() * 3) | 0, flip, ph: Math.random() * TAU });
    }
  }
}
function cleanup() {
  const lim = S.camY + VH + 700;
  S.plats = S.plats.filter((p) => p.y < lim && !p.gone && !(p.broke && p.bt > 1.6));
  S.items = S.items.filter((it) => it.y < lim && !it.taken);
  S.bugs = S.bugs.filter((b) => b.y < lim && !(b.state === 'away' && b.at > 3));
  S.winds = S.winds.filter((w) => w.y0 < lim);
  for (const L of LAY) S[L.key] = S[L.key].filter((d) => d.yl - S.camY * L.p < VH + 900);
  if (S.ground && S.camY + VH < -160) S.ground = false;
}
function windAt(y) {
  for (const w of S.winds) if (y > w.y0 && y < w.y1) return w.dir * Math.min(sstep(w.y0, w.y0 + 90, y), 1 - sstep(w.y1 - 90, w.y1, y));
  return 0;
}

/* ---------------- управление ---------------- */
function control(g) {
  const h = S.hero, inp = g.input, p = inp.pointer;
  if (S.bot) { S.src = 'bot'; return botCtl(); }
  let c = 0;
  if (inp.down('left')) c -= 1;
  if (inp.down('right')) c += 1;
  if (c) { S.src = 'keys'; return c; }
  if (A.isTouch) {
    /* телефон: либо наклон (без кнопок и половин экрана), либо касание половин — как выбрано в меню */
    if (S.ctl === 'tilt') { S.src = 'tilt'; const v = S.tilt, dz = TILT_DZ; return Math.abs(v) < dz ? 0 : clamp((v - Math.sign(v) * dz) / TILT_FULL, -1, 1); }
    if (p.down && p.type !== 'mouse') { S.src = 'touch'; return p.x < W / 2 ? -1 : 1; }
    S.src = ''; return 0;
  }
  if (p.type === 'mouse' && inp.mouseActive && S.mouseSeen) { S.src = 'mouse'; const d = clamp((p.x - COLX) / K, 0, WW) - h.x; return Math.abs(d) < 5 ? 0 : clamp(d / 70, -1, 1); }
  S.src = '';
  return 0;
}
/* ---- наклон телефона: главная изюминка на телефоне ----
   Выбор «Наклоном» / «Касанием» — в меню на старте и после партии, запоминается (hop.ctl). Мёртвая зона ±3°, полный
   ход — при наклоне ~17°, сглаживание ~0,15 с. На iOS разрешение спрашивается по нажатию «Начать». Если за 1,5 с после
   старта от датчика не пришло ни одного события — тихо переходим на касания и говорим об этом одной строкой. */
const TILT_DZ = 3, TILT_FULL = 14, TILT_WAIT = 1500, CTL_KEY = 'hop.ctl';
const HAS_TILT = A.isTouch && typeof window.DeviceOrientationEvent !== 'undefined';
function loadCtl() {
  let v = null; try { v = localStorage.getItem(CTL_KEY); } catch (e) { /* без хранилища */ }
  if (v === 'touch' || S.tiltDead) return 'touch';          // датчик уже молчал в этот раз — сразу касание
  return HAS_TILT ? 'tilt' : 'touch';
}
function saveCtl(v) { try { localStorage.setItem(CTL_KEY, v); } catch (e) { /* без хранилища — только на эту партию */ } }
function onTilt(e) {
  if (e.gamma == null) return;
  let v = e.gamma;
  const ang = (screen.orientation && screen.orientation.angle) || +window.orientation || 0;
  if (ang === 90) v = e.beta; else if (ang === -90 || ang === 270) v = -e.beta;
  if (!(v > -90 && v < 90)) return;
  S.tiltRaw = v; S.tiltN++;
}
function tiltFallback(msg) {
  if (S.ctl !== 'tilt') return;
  S.ctl = 'touch'; S.tiltT0 = null; S.tipT = 6; S.tiltDead = true;           // на эту партию; выбор в меню не трогаем
  GAME.tip(msg, 4200);
}
function askTilt() {
  S.tiltT0 = null; S.tiltN0 = S.tiltN; S.tiltOk = false;
  if (S.ctl !== 'tilt') return;
  try {
    const D = window.DeviceOrientationEvent;
    if (D && typeof D.requestPermission === 'function') {          // iOS: только по нажатию — «Начать» и есть нажатие
      D.requestPermission().then((r) => { if (r === 'granted') S.tiltT0 = performance.now(); else tiltFallback('Нет доступа к наклону — играем касанием'); })
        .catch(() => tiltFallback('Нет доступа к наклону — играем касанием'));
      return;
    }
  } catch (e) { /* нет датчика */ }
  S.tiltT0 = performance.now();
}
function tiltWatch() {
  if (S.ctl !== 'tilt' || S.tiltOk || S.tiltT0 == null) return;
  if (S.tiltN > S.tiltN0) { S.tiltOk = true; return; }
  if (performance.now() - S.tiltT0 > TILT_WAIT) tiltFallback('Наклон не отвечает — играем касанием');
}
function predictX(p, t) {
  if (p.type !== 'move') return p.x;
  const lo = p.w / 2 + 8, hi = WW - p.w / 2 - 8, L = hi - lo, per = 2 * L;
  let u = (p.x - lo) + p.vx * t; u = ((u % per) + per) % per; return lo + (u <= L ? u : per - u);
}
/* бот для самопроверки: из досягаемых опор — самая высокая (пружинка — с бонусом); сонных жуков облетает снизу */
function botCtl() {
  const h = S.hero;
  if (h.balT > 0) { S.botX = null; return 0; }
  let best = null, bs = -Infinity;
  for (const p of S.plats) {
    if (p.gone || p.broke || p.vanish || p.type === 'break') continue;
    const dy = p.y - h.y, disc = h.vy * h.vy + 2 * G * dy;
    if (disc < 0) continue;
    const t = (-h.vy + Math.sqrt(disc)) / G;
    if (t < .03) continue;
    let tx = predictX(p, t); if (p.spring) tx += p.spring.x;
    /* ветер учитываем, и путь «через край» тоже: против ветра бывает дальше, чем по ветру вокруг */
    const d1 = wrapD(tx - h.x), tt = Math.max(0, t - .14 - Math.min(.3, S.botSame * .06)), slack = p.spring ? 10 : p.w / 2 - 18;
    let dx = null;
    for (const d of [d1, d1 - Math.sign(d1 || 1) * WW]) {
      const v = HS + Math.sign(d) * (h.wv || 0);
      if (Math.abs(d) <= v * tt + slack && (dx == null || Math.abs(d) / v < Math.abs(dx) / (HS + Math.sign(dx) * (h.wv || 0)))) dx = d;
    }
    if (dx == null) continue;
    const sc = -p.y + (p.spring ? 260 : 0) - Math.abs(dx) * .05;
    if (sc > bs) { bs = sc; best = tx; S.botDx = dx; }
  }
  if (S.ground && h.y > -400 && best == null) { best = h.x; S.botDx = 0; }
  S.botX = best;
  let ctl = best == null ? 0 : clamp(S.botDx / 45, -1, 1);
  if (h.vy < 0 && S.botSame < 3) {                    // жука облетаем, но не бесконечно: после трёх прыжков на месте — напролом
    const u = -h.vy;
    for (const b of S.bugs) {
      if (b.state !== 'sleep') continue;
      const dy = (h.y - HR) - (b.y + 60), disc = u * u - 2 * G * Math.max(0, dy);
      if (dy < -120 || disc < 0) continue;                       // жук уже ниже или до него не долететь
      const t = dy <= 0 ? 0 : (u - Math.sqrt(disc)) / G;
      const fx = wrapX(b.x0 + Math.sin((b.t + t) * b.sp + b.ph) * b.amp), bx = wrapD(fx - (h.x + h.vx * t * .5));
      if (Math.abs(bx) < 110) ctl = bx > 0 ? -1 : 1;
    }
  }
  return ctl;
}

/* ---------------- ход игры ---------------- */
function joy(t) { const h = S.hero; if (h.face !== 'oops' || h.dizzy <= 0) { h.face = 'joy'; h.faceT = t; } }
function bounce(g, p) {
  const h = S.hero;
  let v = JUMP, spring = false;
  if (p && p.spring && Math.abs(wrapD(h.x - (p.x + p.spring.x))) < 26) { v = SPRING; spring = true; p.spring.c = 1; }
  h.vy = -v; h.sq = -.3; h.sqv = 0;
  if (spring) { snd.spring(); joy(1.1); S.springs++; } else snd.hop(1 + Math.min(.25, S.maxAlt / 90000));
  S.botSame = p && p === S.botLast ? S.botSame + 1 : 0; S.botLast = p;
  if (p) {
    p.press = 1;
    if (p.type === 'once') { p.vanish = true; p.vt = 0; snd.puff(); for (let i = 0; i < 14; i++) S.parts.push({ kind: 'seed', x: p.x + A.rand(-p.w / 2, p.w / 2), y: p.y + A.rand(-6, 14), vx: A.rand(-60, 60), vy: A.rand(-120, -30), life: A.rand(1.2, 2), max: 2, rot: A.rand(-.5, .5), vr: A.rand(-1, 1), s: A.rand(.8, 1.1) }); }
  }
  S.jumps++;
}
function breakPlat(p) {
  p.broke = true; p.bt = 0; S.breaks++; snd.crunch();
  const h = S.hero; if (S.mode === 'play') { h.face = 'oops'; h.faceT = .7; const [sx, sy] = scr(p.x, p.y - 30); GAME.fx.text(sx, sy, 'ой!', { size: Math.max(24, 30 * K), color: '#fff6d8', rise: 40 * K, life: .8 }); }
  for (let i = 0; i < 12; i++) S.parts.push({ kind: 'crumb', x: p.x + A.rand(-p.w / 2, p.w / 2), y: p.y + A.rand(0, 14), vx: A.rand(-90, 90), vy: A.rand(-160, 20), life: A.rand(.6, 1.1), max: 1.1, rot: A.rand(0, 6), vr: A.rand(-9, 9), s: A.rand(3, 6), col: A.pick(['#eab163', '#c98944', '#f9d79a']) });
}
function landCheck(g, py) {
  const h = S.hero;
  if (S.ground && py <= 0 && h.y >= 0) { h.y = 0; bounce(g, null); return; }
  for (const p of S.plats) {
    if (p.gone || p.broke || p.vanish) continue;
    if (py <= p.y + 2 && h.y >= p.y && Math.abs(wrapD(h.x - p.x)) <= p.w / 2 + FOOT) {
      if (p.type === 'break') { breakPlat(p); continue; }
      h.y = p.y; bounce(g, p); return;
    }
  }
}
const scr = (x, y) => [COLX + x * K, (y - S.camY) * K];
function touchStuff(g) {
  const h = S.hero, hy = h.y - HR;
  for (const it of S.items) {
    if (it.taken) continue;
    const dx = wrapD(it.x - h.x), dy = it.y - hy;
    if (dx * dx + dy * dy < HIT * HIT) {
      it.taken = true; S.got++; S.streak = S.streakT > 0 ? S.streak + 1 : 0; S.streakT = 1.4; snd.pick(S.streak); joy(.5);
      const [sx, sy] = scr(it.x, it.y);
      g.fx.burst(sx, sy, { n: 10, speed: 220 * K, size: 6 * K, colors: it.kind === 'star' ? ['#ffd04d', '#fff0a6', '#ffffff'] : ['#ff5d70', '#ffe49c', '#ffffff'], shape: 'star', life: .55 });
      g.fx.text(sx, sy - 20 * K, '+10', { size: Math.max(26, 34 * K), color: '#fff6d8', rise: 60 * K, life: .8 });
    }
  }
  for (const b of S.bugs) {
    if (b.state !== 'sleep' || b.hitT > 0) continue;
    const dx = wrapD(b.x - h.x), dy = b.y - hy;
    if (dx * dx + dy * dy > BUGHIT * BUGHIT) continue;
    if (h.balT > 0) { b.state = 'away'; b.vx = (dx >= 0 ? 1 : -1) * 260; b.vy = -120; continue; }
    if (h.vy > 0 && hy < b.y - 4) {
      h.vy = -STOMP; h.sq = -.25; b.state = 'away'; b.vx = (dx >= 0 ? 1 : -1) * 240; b.vy = -60; S.stomps++; snd.stomp(); joy(.8);
      const [sx, sy] = scr(b.x, b.y - 40); g.fx.text(sx, sy, 'ой!', { size: Math.max(24, 30 * K), color: '#d8dcff', rise: 40 * K, life: .9 });
    } else {
      h.vy = Math.max(h.vy, 160); h.vx = (dx >= 0 ? -1 : 1) * 220; h.dizzy = .7; h.face = 'oops'; h.faceT = .8; h.sq = .22; h.sqv = 0; b.hitT = .7; S.bonks++;
      snd.bonk(); g.shake(5, .2);
    }
  }
  for (const p of S.plats) {
    if (!p.balloon || p.broke || p.gone) continue;
    const bx = p.x + p.balloon.off, by = p.y - 70 + Math.sin(S.t * 2 + p.balloon.ph) * 4;
    const dx = wrapD(bx - h.x), dy = by - hy;
    if (dx * dx + dy * dy < HIT * HIT) { p.balloon = null; h.balT = BAL_T; h.chute = 0; snd.inflate(); joy(BAL_T); S.balloons++; }
  }
}
function simTitle(dt) {
  const h = S.hero;
  h.x = WW / 2 + Math.sin(S.t * .6) * 70; h.vx = Math.cos(S.t * .6) * 42; h.dir = h.vx >= 0 ? 1 : -1;
  h.vy += G * dt; h.y += h.vy * dt;
  if (h.y >= 0) { h.y = 0; h.vy = (S.hopN++ % 3 === 2) ? -820 : -560; h.sq = -.3; h.sqv = 0; if (S.hopN % 3 === 0) joy(.5); }
}
function simPlay(g, dt) {
  const h = S.hero, p = g.input.pointer;
  if (p.moved && p.type === 'mouse') S.mouseSeen = true;
  tiltWatch();
  const c = control(g);
  if (c) { S.moved += dt; if (S.moved > 1.6 && S.tipT > .6) S.tipT = .6; }
  const tv = c * HS * (h.dizzy > 0 ? .65 : 1);
  h.vx += (tv - h.vx) * Math.min(1, dt * (c ? 9 : 6));
  const wnd = windAt(h.y); S.windNow = wnd;
  if (wnd && S.windSeen !== S.winds.find((w) => h.y > w.y0 && h.y < w.y1)) { S.windSeen = S.winds.find((w) => h.y > w.y0 && h.y < w.y1); snd.wind(); }
  h.wv += (wnd * 250 - h.wv) * Math.min(1, dt * 2.5);
  const dx = (h.vx + h.wv) * dt; h.x = wrapX(h.x + dx); h.ux += dx;
  if (Math.abs(h.vx) > 30) h.dir = Math.sign(h.vx);
  const py = h.y;
  if (h.balT > 0) {
    h.balT -= dt; h.vy += (-BAL_V - h.vy) * Math.min(1, dt * 3);
    if (h.balT <= 0) {
      snd.pop(); h.vy = -900; joy(.6);
      for (let i = 0; i < 16; i++) S.parts.push({ kind: 'conf', x: h.x + h.dir * 34 * HSC, y: h.y - 150 * HSC, vx: A.rand(-220, 220), vy: A.rand(-260, 60), life: A.rand(.6, 1.1), max: 1.1, rot: A.rand(0, 6), vr: A.rand(-10, 10), s: A.rand(4, 7), col: A.pick(['#ff8ca2', '#ffd04d', '#ffffff', '#9fd2f2']) });
    }
  } else h.vy = Math.min(h.vy + G * dt, 1500);
  h.y += h.vy * dt;
  if (h.vy > 0 && h.balT <= 0) landCheck(g, py);
  touchStuff(g);
  const ty = h.y - VH * .45;
  if (ty < S.camY) S.camY += (ty - S.camY) * Math.min(1, dt * 12);
  S.maxAlt = Math.max(S.maxAlt, -h.y);
  gen(); decorGen(); cleanup();
  const bi = bioAt(-S.camY - VH * .5);
  if (bi > S.bio) { S.bio = bi; S.banner = { i: bi, t: 0 }; snd.biome(); }
  S.tipT -= dt;
  if (h.y > S.camY + VH + 60) startDrop(g);
}
function startDrop(g) {
  const h = S.hero;
  S.mode = 'drop'; S.dropT = 0; h.face = 'oops'; h.faceT = 99; h.balT = 0; h.dizzy = 0;
  snd.oops(); g.setPlaying(false); g.stopMusic();
}
function simDrop(g, dt) {
  const h = S.hero; S.dropT += dt;
  if (S.dropT > .65) { if (!h.chuteOn) { h.chuteOn = true; snd.puff(); } h.chute = Math.min(1, h.chute + dt * 2.4); }
  if (h.chuteOn) { h.vy += (95 - h.vy) * Math.min(1, dt * 3); h.vx = Math.sin(S.t * 1.4) * 40 + wrapD(WW * .5 - h.x) * .9; h.x = wrapX(h.x + h.vx * dt); if (h.chute >= 1 && S.dropT > 1.4) h.face = 'calm'; }
  else h.vy = Math.min(h.vy + G * dt, 1500);
  h.y += h.vy * dt;
  const follow = 1 - sstep(2.2, 3.4, S.dropT);
  S.camY += (h.y - VH * (LAND ? .24 : .21) - S.camY) * Math.min(1, dt * 4) * follow;
  if (S.dropT > 1.6 && S.mode === 'drop') endScreen();
}
function simWorld(dt) {
  const h = S.hero;
  for (const p of S.plats) {
    p.t += dt;
    if (p.type === 'move' && !p.broke) { p.x += p.vx * dt; const lo = p.w / 2 + 8, hi = WW - p.w / 2 - 8; if (p.x < lo) { p.x = lo; p.vx = Math.abs(p.vx); } else if (p.x > hi) { p.x = hi; p.vx = -Math.abs(p.vx); } }
    if (p.press > 0) p.press = Math.max(0, p.press - dt * 4);
    if (p.broke) p.bt += dt;
    if (p.vanish) { p.vt += dt; if (p.vt > .45) p.gone = true; }
    if (p.spring && p.spring.c > 0) p.spring.c = Math.max(0, p.spring.c - dt * 2.2);
  }
  for (const b of S.bugs) {
    b.t += dt; if (b.hitT > 0) b.hitT -= dt;
    if (b.state === 'sleep') { const nx = b.x0 + Math.sin(b.t * b.sp + b.ph) * b.amp; b.dir = nx >= b.x ? 1 : -1; b.x = wrapX(nx); b.y = b.y0 + Math.sin(b.t * 2.1 + b.ph) * 5; }
    else { b.at += dt; b.x += b.vx * dt; b.y += b.vy * dt; b.vy -= 160 * dt; b.dir = Math.sign(b.vx) || 1; }
  }
  for (const q of S.parts) {
    q.life -= dt; q.x += q.vx * dt; q.y += q.vy * dt; q.rot += q.vr * dt;
    const drag = q.kind === 'seed' ? 1.2 : .6; q.vx -= q.vx * drag * dt;
    q.vy += (q.kind === 'seed' ? -20 : q.kind === 'crumb' ? 900 : 700) * dt; if (q.kind === 'seed') q.vy -= q.vy * dt;
  }
  S.parts = S.parts.filter((q) => q.life > 0);
  if (S.streakT > 0) S.streakT -= dt;
  if (S.banner) { S.banner.t += dt; if (S.banner.t > 3) S.banner = null; }
  /* Тимоша: пружинистое сплющивание, колпак на пружинке, моргание, мимика */
  h.sqv += (-170 * h.sq - 13 * h.sqv) * dt; h.sq += h.sqv * dt;
  const ct = clamp(-h.vx / HS * .45 + clamp(h.vy / 1800, -.4, .4) * .25, -.6, .6);
  h.crestV += (-140 * (h.crest - ct) - 9 * h.crestV) * dt; h.crest += h.crestV * dt;
  h.blink -= dt; if (h.blink < 0) h.blink = A.rand(2, 4.2);
  if (h.dizzy > 0) h.dizzy -= dt;
  if (h.faceT > 0) { h.faceT -= dt; if (h.faceT <= 0 && S.mode === 'play') h.face = 'idle'; }
  if (S.mode === 'play' && h.faceT <= 0) h.face = h.vy > 1250 ? 'oops' : 'idle';
  /* падающая звезда ночью */
  if (S.shoot) { S.shoot.t += dt; if (S.shoot.t > 1) S.shoot = null; }
  else if (-S.camY > 19500) { S.shootT -= dt; if (S.shootT < 0) { S.shootT = A.rand(4, 8); S.shoot = { x: A.rand(.2, .9), y: A.rand(.05, .4), t: 0 }; } }
}
function update(g, dt) {
  if (COVER) { S.t += dt; simWorld(dt); return; }
  const p = g.input.pointer;
  if (S.mode === 'play' && !g.screenOn) {
    if (g.input.pressed('help') || (p.justDown && inHelp(p.x, p.y))) { openHelp(); return; }
  }
  if (g.screenOn && S.mode === 'play') return;          // открыта «?»: игра стоит
  const n = S.mode === 'play' ? Math.max(1, S.speed | 0) : 1;
  for (let i = 0; i < n; i++) {
    S.t += dt;
    S.tilt += (S.tiltRaw - S.tilt) * Math.min(1, dt * 7);
    if (S.mode === 'title') simTitle(dt);
    else if (S.mode === 'play') simPlay(g, dt);
    else simDrop(g, dt);
    simWorld(dt);
    if (S.mode !== 'play') break;
  }
}

/* ---------------- экраны ---------------- */
const ICONS = {};
function iconURL(key, w, h, ox, oy, fn) {
  if (ICONS[key]) return ICONS[key];
  const s = 2, cv = document.createElement('canvas'); cv.width = w * s; cv.height = h * s;
  const c = cv.getContext('2d'); c.scale(s, s); c.translate(ox, oy); const keep = SS; SS = s; fn(c); SS = keep;
  try { ICONS[key] = cv.toDataURL(); } catch (e) { ICONS[key] = ''; }
  return ICONS[key];
}
function helpHTML() {
  const sk = (k, fn) => iconURL(k, 76, 44, 38, 22, fn);
  const rows = [
    [sk('h1', (c) => { c.scale(.5, .5); drawLeaf(c, 110, 0, false); }), 'Листик и облачко держат'],
    [sk('h2', (c) => { c.scale(.5, .5); drawLeaf(c, 110, 1, true); }), 'Сухой листик — хрусть!'],
    [sk('h3', (c) => { c.translate(0, -3); c.scale(.5, .5); drawFluff(c, 110, 0); }), 'Одуванчик — на один прыжок'],
    [sk('h4', (c) => { c.translate(-14, 16); drawSpring(c, 0, 0, 0); c.translate(32, 2); c.scale(.6, .6); drawBalloonBody(c); }), 'Пружинка и шарик — выше!'],
    [sk('h5', (c) => { c.translate(0, 6); c.scale(.5, .5); drawBugSpr(c, false); }), 'Сонного жука — только сверху'],
    [sk('h6', (c) => { c.translate(-14, 0); c.scale(.7, .7); drawBerry(c); c.translate(40, 0); drawStar(c); }), 'Ягодки и звёздочки: +10']
  ];
  const ctl = A.isTouch ? ctlPic(S.ctl) : '<p><b>←&nbsp;→</b> или <b>A&nbsp;D</b>, или ведите мышью. За краем экрана Тимоша выглянет с другой стороны.</p>';
  return `${ctl}<div class="hop-help">${rows.map(([u, t]) => `<div><img src="${u}" alt="">${t}</div>`).join('')}</div>`;
}
function openHelp() {
  if (S.mode !== 'play' || GAME.screenOn) return;
  GAME.screen({ kicker: 'Подсказка', title: 'Как играть', html: helpHTML(), button: 'Понятно', keys: '', onGo: () => {} });
}
/* картинки-схемы управления (SVG с покачиванием) и выбор «Наклоном» / «Касанием» */
const TILT_TXT = 'Наклоняйте телефон — Тимоша полетит туда же', TOUCH_TXT = 'Держите палец слева или справа — Тимоша полетит туда же';
const SVG_TILT = `<svg class="hop-pic hop-tilt" viewBox="0 0 132 74" aria-hidden="true">
  <path class="ar l" d="M30 22 Q16 32 22 50" /><path class="ar l" d="M16 44 L22 51 L28 45" />
  <path class="ar r" d="M102 22 Q116 32 110 50" /><path class="ar r" d="M104 45 L110 51 L116 44" />
  <g class="ph"><rect x="48" y="6" width="36" height="62" rx="8" fill="#fffaf0" stroke="#4a3550" stroke-width="3"/>
  <rect x="53" y="13" width="26" height="45" rx="3" fill="#bfe5f0"/><path d="M53 50 h26 v5 a3 3 0 0 1 -3 3 h-20 a3 3 0 0 1 -3 -3z" fill="#9bd16c"/>
  <g class="ch"><path d="M60 39 Q63 27 74 30 Q68 31 72 39z" fill="#6070c8"/><circle cx="74" cy="30" r="2.4" fill="#fff6e2"/><circle cx="66" cy="42" r="6" fill="#ffd8b5"/><rect x="59" y="36.5" width="14" height="3" rx="1.5" fill="#fff6e2"/><circle cx="64" cy="42" r="1" fill="#3a2a45"/><circle cx="68.5" cy="42" r="1" fill="#3a2a45"/><ellipse cx="66.6" cy="44.3" rx="1.8" ry="1.4" fill="#ffae8a"/></g></g></svg>`;
const SVG_TOUCH = `<svg class="hop-pic hop-touch" viewBox="0 0 132 74" aria-hidden="true">
  <rect x="44" y="4" width="44" height="66" rx="9" fill="#fffaf0" stroke="#4a3550" stroke-width="3"/>
  <rect class="hl" x="49" y="10" width="17" height="54" rx="3"/><rect class="hr" x="66" y="10" width="17" height="54" rx="3"/>
  <path d="M66 12 V62" stroke="#4a3550" stroke-width="1.5" stroke-dasharray="3 3" opacity=".5"/>
  <circle class="fl" cx="57" cy="46" r="6.5"/><circle class="fr" cx="75" cy="46" r="6.5"/></svg>`;
function ctlPic(mode) { return `<div class="hop-ctlpic">${mode === 'tilt' ? SVG_TILT : SVG_TOUCH}<p class="hop-ctlnote">${mode === 'tilt' ? TILT_TXT : TOUCH_TXT}</p></div>`; }
function ctlChooser() {
  if (!A.isTouch) return '';
  return `<div class="hop-ctl" role="group" aria-label="Управление">
    <button type="button" data-ctl="tilt" aria-pressed="${S.ctl === 'tilt'}"${HAS_TILT ? '' : ' disabled title="Датчика наклона нет"'}>Наклоном</button>
    <button type="button" data-ctl="touch" aria-pressed="${S.ctl === 'touch'}">Касанием</button></div><div id="hopCtlPic">${ctlPic(S.ctl)}</div>`;
}
function bindChooser() {
  const ov = document.getElementById('aOverlay'); if (!ov) return;
  ov.querySelectorAll('.hop-ctl button').forEach((b) => b.addEventListener('click', () => {
    S.ctl = b.dataset.ctl; saveCtl(S.ctl); if (S.ctl === 'tilt') S.tiltDead = false;
    ov.querySelectorAll('.hop-ctl button').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
    const pic = document.getElementById('hopCtlPic'); if (pic) pic.innerHTML = ctlPic(S.ctl);
    if (SND.ctx) SND.play('click');
  }));
}
const LINES = [
  'Тимоша только разошёлся — попробуем ещё?',
  'Тимоша погулял по кронам деревьев.',
  'Тимоша потрогал настоящие облака!',
  'Тимоша видел закат сверху!',
  'Тимоша почти дотянулся до луны — ещё чуть-чуть, и выспится!'
];
function endScreen() {
  const g = GAME; S.mode = 'end';
  document.body.classList.add('hop-end');    // карточка итога — внизу поля: Тимоша под зонтиком виден над ней
  const m = Math.floor(S.maxAlt / 10), score = m + S.got * 10, rec = g.submit(score);
  if (S.maxAlt > S.bestAlt) { S.bestAlt = S.maxAlt; A.store.set('hop.bestAlt', Math.round(S.maxAlt)); }
  S.score = score;
  g.screen({
    kicker: 'Высота · ' + BIO[bioAt(S.maxAlt)].short, title: 'Улетел!',
    html: `<p>${LINES[bioAt(S.maxAlt)]}</p><p class="score">${score}</p><p class="sum">высота <b>${m}&nbsp;м</b> + собрано <b>${S.got}</b>&nbsp;×&nbsp;10</p><p>${rec ? '<span class="record">Новый рекорд!</span>' : 'рекорд — ' + g.best}</p>`,
    button: 'Ещё раз', keys: '', onGo: start, alt: { label: A.framed ? 'К играм' : 'В аркаду', onGo: () => A.home('../index.html') }
  });
  if (A.isTouch) { S.ctl = loadCtl(); document.querySelector('#aOverlay .card .row').insertAdjacentHTML('beforebegin', ctlChooser()); bindChooser(); }
}
function start() {
  document.body.classList.remove('hop-end');
  fresh(); RUN++; S.run = RUN; S.mode = 'play'; S.tipT = 7;
  const h = S.hero; h.vy = -JUMP; h.sq = -.3;
  GAME.setPlaying(true); GAME.playMusic(); GAME.fx.clear();
  askTilt();
}
function title() {
  fresh(); S.mode = 'title'; GAME.setPlaying(false);
  if (A.isTouch) S.ctl = loadCtl();
  GAME.screen({
    kicker: A.framed ? 'Досуг' : 'Аркада', title: 'Выше облаков',
    html: A.isTouch ? '<p>Сонный Тимоша хочет выспаться на луне. Прыгает он сам — а вы ведёте его всё выше.</p>' + ctlChooser()
      : '<p>Сонный Тимоша в пижаме хочет выспаться на луне. Прыгает он сам — а вы ведёте его по листикам, облачкам и пружинкам всё выше.</p>',
    button: 'Начать', keys: A.isTouch ? '' : undefined, onGo: start
  });
  bindChooser();
}

/* ---------------- рисование мира ---------------- */
function drawDecor(c, list, p) {
  for (const d of list) {
    const Y = d.yl + S.camY * (1 - p);
    if (Y - S.camY < -420 || Y - S.camY > VH + 420) continue;
    if (d.kind === 'bfly') { drawBfly(c, d, Y, S.t); continue; }
    const e = decorSpr(d.kind, d.v); if (!e) continue;
    if (d.flip && d.kind !== 'hills') { c.save(); c.translate(d.x, Y); c.scale(-1, 1); blit(c, e, 0, 0); c.restore(); }
    else blit(c, e, d.x, Y);
  }
}
const xsFor = (x, half) => (x - half < 0 ? [x, x + WW] : x + half > WW ? [x, x - WW] : [x]);
function drawPlats(c) {
  for (const p of S.plats) {
    const y = p.y + (p.press > 0 ? Math.sin(p.press * Math.PI) * 6 : 0) + ((p.skin === 'cloud' || p.skin === 'peach' || p.skin === 'lav') ? Math.sin(S.t * 1.5 + p.bob) * 1.5 : 0);
    const e = platSpr(p.skin, p.w, p.v);
    for (const x of xsFor(p.x, p.w / 2 + 40)) {
      if (p.broke) {
        const k = p.bt, fall = 300 * k * k + 40 * k;
        for (const s of [-1, 1]) {
          c.save(); c.globalAlpha = clamp(1.4 - k, 0, 1); c.translate(x + s * (8 + k * 50), y + fall); c.rotate(s * k * 1.6);
          const sw = e.cv.width / 2;
          c.drawImage(e.cv, s < 0 ? 0 : sw, 0, sw, e.cv.height, s < 0 ? -e.ox : 0, -e.oy, e.w / 2, e.h);
          c.restore();
        }
        continue;
      }
      if (p.vanish) { const k = p.vt / .45; c.save(); c.globalAlpha = 1 - k; c.translate(x, y); c.scale(1 + k * .25, 1 + k * .25); blit(c, e, 0, 0); c.restore(); continue; }
      if (p.type === 'move') {
        const f = .55 + .45 * Math.sin(S.t * 13 + p.bob);
        for (const s of [-1, 1]) {
          c.save(); c.translate(x + s * (p.w / 2 - 4), y + 2); c.scale(s, f);
          const wg = new Path2D(); wg.moveTo(0, 0); wg.quadraticCurveTo(12, -22, 30, -16); wg.quadraticCurveTo(22, -8, 26, -2); wg.quadraticCurveTo(14, -4, 0, 4); wg.closePath();
          c.fillStyle = 'rgba(70,60,110,.16)'; c.save(); c.translate(1, 3); c.fill(wg); c.restore();
          c.fillStyle = '#ffffff'; c.fill(wg); c.strokeStyle = 'rgba(160,170,210,.8)'; c.lineWidth = 1.2; c.beginPath(); c.moveTo(4, -2); c.quadraticCurveTo(14, -12, 24, -12); c.stroke();
          c.restore();
        }
      }
      blit(c, e, x, y);
      if (p.spring) { const k = p.spring.c; drawSpring(c, x + p.spring.x, y - 1, k > 0 ? Math.sin(k * Math.PI * 3) * .5 * k + k * .4 : 0); }
      if (p.balloon) {
        const bx = x + p.balloon.off, by = y - 52 + Math.sin(S.t * 2 + p.balloon.ph) * 4;
        c.strokeStyle = '#b9767f'; c.lineWidth = 1.6; c.lineCap = 'round'; c.beginPath(); c.moveTo(bx, by); c.bezierCurveTo(bx + 6, by + 14, bx - 6, y - 16, bx + 2, y + 2); c.stroke();
        blit(c, balloonSpr(), bx, by);
      }
    }
  }
}
function drawItems(c) {
  for (const it of S.items) {
    const e = itemSpr(it.kind), y = it.y + Math.sin(S.t * 2.4 + it.ph) * 4, sc = 1.22 + Math.sin(S.t * 3 + it.ph) * .06;
    for (const x of xsFor(it.x, 30)) { c.save(); c.translate(x, y); c.rotate(Math.sin(S.t * 1.7 + it.ph) * .12); c.scale(sc, sc); blit(c, e, 0, 0); c.restore(); }
  }
}
function drawBugs(c) {
  for (const b of S.bugs) {
    const awake = b.state === 'away' || b.hitT > 0, e = bugSpr(awake);
    for (const x of xsFor(b.x, 50)) {
      c.save(); c.translate(x, b.y); c.scale(b.dir, 1);
      if (b.state === 'away') c.rotate(Math.sin(b.at * 14) * .25);
      const f = Math.sin(S.t * (awake ? 30 : 7) + b.ph);
      for (const s of [-1, 1]) { c.save(); c.translate(s * 16, -24); c.rotate(s * (.5 + f * .25)); c.fillStyle = 'rgba(235,242,255,.7)'; c.strokeStyle = 'rgba(140,150,220,.7)'; c.lineWidth = 1.3; c.beginPath(); c.ellipse(s * 8, -6, 14, 8, 0, 0, TAU); c.fill(); c.stroke(); c.restore(); }
      blit(c, e, 0, 0);
      c.restore();
      if (b.state === 'sleep' && b.hitT <= 0) {
        for (let i = 0; i < 3; i++) {
          const k = (S.t * .5 + i / 3 + b.ph) % 1;
          c.globalAlpha = Math.sin(k * Math.PI) * .9;
          txt(c, 'z', x + 22 + k * 22 + Math.sin(k * 6) * 4, b.y - 42 - k * 44, 15 + k * 10, '#5b5fae', { w: 900, align: 'center', halo: 'rgba(255,255,255,.75)', haloW: 4 });
        }
        c.globalAlpha = 1;
      }
      if (b.hitT > 0) txt(c, 'мм?', x, b.y - 58, 22, '#4a4f9a', { w: 800, align: 'center', halo: 'rgba(255,255,255,.8)', haloW: 5 });
    }
  }
}
function drawParts(c) {
  for (const q of S.parts) {
    const a = clamp(q.life / q.max * 1.6, 0, 1); c.globalAlpha = a;
    if (q.kind === 'seed') {
      c.save(); c.translate(q.x, q.y); c.rotate(q.rot); c.scale(q.s, q.s);
      c.strokeStyle = 'rgba(190,165,120,.9)'; c.lineWidth = 1.2; c.beginPath(); c.moveTo(0, 8); c.lineTo(0, -4); c.stroke();
      c.fillStyle = '#b48b58'; c.beginPath(); c.ellipse(0, 9, 1.4, 2.4, 0, 0, TAU); c.fill();
      puff(c, 0, -6, 4.6); c.restore();
    } else {
      c.save(); c.translate(q.x, q.y); c.rotate(q.rot); c.fillStyle = q.col;
      if (q.kind === 'crumb') { c.beginPath(); c.moveTo(-q.s, q.s * .6); c.lineTo(0, -q.s); c.lineTo(q.s, q.s * .7); c.closePath(); c.fill(); }
      else c.fillRect(-q.s / 2, -q.s / 3, q.s, q.s * .66);
      c.restore();
    }
  }
  c.globalAlpha = 1;
}
function drawWinds(c) {
  for (const w of S.winds) {
    if (w.y1 < S.camY - 50 || w.y0 > S.camY + VH + 50) continue;
    const hgt = w.y1 - w.y0, n = 6;
    c.lineCap = 'round';
    for (let i = 0; i < n; i++) {
      const y = w.y0 + hgt * (i + .5) / n, sp = 260 + i * 37, len = 170 + (i % 3) * 40;
      const k = ((S.t * sp + i * 210 + w.ph * 100) % (WW + len + 200));
      const x0 = w.dir > 0 ? k - len - 100 : WW + 100 - k;
      c.strokeStyle = 'rgba(255,255,255,.72)'; c.lineWidth = 6;
      c.beginPath();
      for (let s = 0; s <= 12; s++) { const xx = x0 + len * s / 12, yy = y + Math.sin(xx * .03 + S.t * 3 + i) * 7; s ? c.lineTo(xx, yy) : c.moveTo(xx, yy); }
      c.stroke();
      const lx = x0 + len * (w.dir > 0 ? 1.05 : -.05);
      smallLeafQuick(c, lx, y + Math.sin(S.t * 4 + i) * 8, S.t * 4 * w.dir + i);
    }
    /* Ветерок — облачко с надутыми щеками у наветренного края */
    const fx = w.dir > 0 ? 58 : WW - 58, fy = (w.y0 + w.y1) / 2, puffK = 1 + Math.sin(S.t * 5) * .05;
    c.save(); c.translate(fx, fy); c.scale(-w.dir * puffK, puffK);
    blit(c, spr('windface', 120, 100, 60, 56, (cc) => {
      cut(cc, cloudShape(96, 28, rng(8), -6, .7), '#ffffff', { shade: '#dce8f6', sw: 5, sc: 'rgba(60,80,140,.22)' });
      cc.fillStyle = '#4a3550'; cc.beginPath(); cc.arc(-6, -6, 3, 0, TAU); cc.arc(12, -6, 3, 0, TAU); cc.fill();
      cc.fillStyle = 'rgba(255,150,170,.7)'; cc.beginPath(); cc.ellipse(-16, 4, 7, 4.5, 0, 0, TAU); cc.ellipse(22, 4, 7, 4.5, 0, 0, TAU); cc.fill();
      cc.fillStyle = '#c2463a'; cc.beginPath(); cc.ellipse(-27, 4, 4, 3.4, 0, 0, TAU); cc.fill();
    }), 0, 0);
    c.restore();
  }
}
function smallLeafQuick(c, x, y, rot) {
  c.save(); c.translate(x, y); c.rotate(rot);
  c.fillStyle = '#9bd16c'; c.beginPath(); c.moveTo(-8, 0); c.quadraticCurveTo(0, -6, 8, 0); c.quadraticCurveTo(0, 6, -8, 0); c.fill();
  c.restore();
}
function drawHeroAll(c) {
  const h = S.hero;
  for (const x of xsFor(h.x, Math.ceil(78 * HSC))) { if (x === h.x) drawHero(c, h, S.t); else { const k = h.x; h.x = x; drawHero(c, h, S.t); h.x = k; } }
}
function drawRecordLine(c) {
  if (S.bestAlt < 400 || S.mode === 'title') return;
  const y = -S.bestAlt;
  if (y < S.camY - 20 || y > S.camY + VH + 20) return;
  c.save(); c.setLineDash([16, 12]); c.lineWidth = 3; c.strokeStyle = 'rgba(255,255,255,.75)'; c.beginPath(); c.moveTo(0, y); c.lineTo(WW, y); c.stroke();
  c.setLineDash([]); c.restore();
}
function drawSky(c, alt) {
  const [s0, s1, s2] = skyAt(alt), gr = c.createLinearGradient(0, 0, 0, H);
  gr.addColorStop(0, s0); gr.addColorStop(.55, s1); gr.addColorStop(1, s2);
  c.fillStyle = gr; c.fillRect(COLX, 0, COLW, H);
  const nf = sstep(18200, 20800, alt);
  if (nf > .01) {
    const e = starsSpr(), off = ((-S.camY * .04) % H + H) % H;
    c.globalAlpha = nf; c.drawImage(e.cv, COLX, off - H, COLW, H); c.drawImage(e.cv, COLX, off, COLW, H);
    for (let i = 0; i < 12; i++) {
      const r = rng(500 + i), x = COLX + r() * COLW, y = r() * H, tw = .5 + .5 * Math.sin(S.t * (1.4 + r()) + i * 2);
      c.globalAlpha = nf * tw; c.fillStyle = '#fff6d0'; c.fill(new Path2D(`M${x} ${y - 9}Q${x} ${y} ${x + 9} ${y}Q${x} ${y} ${x} ${y + 9}Q${x} ${y} ${x - 9} ${y}Q${x} ${y} ${x} ${y - 9}Z`));
    }
    if (S.shoot) {
      const s = S.shoot, k = s.t, x = COLX + COLW * s.x - k * 260, y = H * s.y + k * 140;
      const gg = c.createLinearGradient(x, y, x + 120, y - 64); gg.addColorStop(0, 'rgba(255,248,220,.95)'); gg.addColorStop(1, 'rgba(255,248,220,0)');
      c.globalAlpha = nf * Math.sin(k * Math.PI); c.strokeStyle = gg; c.lineWidth = 3; c.lineCap = 'round'; c.beginPath(); c.moveTo(x, y); c.lineTo(x + 120, y - 64); c.stroke();
    }
    c.globalAlpha = 1;
  }
  const su = (alt - 10400) / 10000;
  if (su > -.1 && su < 1.15 && nf < .98) { c.globalAlpha = 1 - nf; blit(c, sunSpr(), COLX + COLW * .7, lerp(-.14, 1.14, su) * H); c.globalAlpha = 1; }
  if (alt > 17000) blit(c, moonSpr(), COLX + COLW * .3, lerp(-.3, .2, sstep(17000, 21500, alt)) * H);
}
function drawWorld(c) {
  const alt = -(S.camY + VH * .5);
  c.save(); c.beginPath(); c.rect(COLX, 0, COLW, H); c.clip();
  drawSky(c, alt);
  c.save(); c.translate(COLX, -S.camY * K); c.scale(K, K);
  drawDecor(c, S.far, .22);
  drawDecor(c, S.mid, .55);
  if (S.ground) blit(c, groundSpr(), 0, 0);
  drawWinds(c);
  drawRecordLine(c);
  drawPlats(c);
  drawItems(c);
  drawBugs(c);
  drawParts(c);
  drawHeroAll(c);
  c.restore();
  c.drawImage(vignette().cv, COLX, 0, COLW, H);
  c.restore();
}

/* ---------------- надписи поверх поля ---------------- */
function paperCard(c, x, y, w, h, o = {}) { cut(c, rrPath(x, y, w, h, o.r ?? 18), o.fill || CREAM, { rim: '#ffffff', shade: o.shade || '#efe1c8', sw: 4, sy: 4, blur: 12, sc: 'rgba(80,45,80,.22)', ga: .8 }); }
/* «?» */
const HELP = LAND ? { x: COLX + COLW + 76, y: 474, r: 40, hit: [COLX + COLW + 20, 420, 300, 110] } : { x: W - 62, y: 64, r: 40, hit: [W - 120, 6, 116, 116] };
function inHelp(x, y) { const [hx, hy, hw, hh] = HELP.hit; return x >= hx && x <= hx + hw && y >= hy && y <= hy + hh; }
function helpBtnSpr() {
  return spr('qbtn', 100, 100, 50, 50, (c) => {
    cut(c, circ(0, 0, HELP.r), CREAM, { rim: '#ffffff', shade: '#efe1c8', sw: 4, sy: 4, blur: 10, sc: 'rgba(80,45,80,.26)', ga: .8 });
    txt(c, '?', 0, 2, 44, CORAL, { w: 900, align: 'center' });
  }, 1);
}
/* рамка широкого окна: бумажная страница с окошком-колонкой, высотомер и карточки счёта */
const RX = COLX + COLW + 26, LC = COLX / 2;           // правая колонка карточек и середина левой
const TRK = { x: LC - 6, y0: 680, y1: 226, w: 40 };
const trackY = (alt) => TRK.y0 - clamp(alt / TOP, 0, 1) * (TRK.y0 - TRK.y1);
function frameSpr() {
  return spr('frame', W, H, 0, 0, (c) => {
    const r = rng(11), hole = new Path2D();
    hole.moveTo(COLX, -10);
    for (let y = 0; y <= H + 10; y += 22) hole.lineTo(COLX + (r() - .5) * 2.6, y);
    hole.lineTo(COLX + COLW, H + 10);
    for (let y = H + 10; y >= -10; y -= 22) hole.lineTo(COLX + COLW + (r() - .5) * 2.6, y);
    hole.closePath();
    const panel = new Path2D(); panel.rect(0, 0, W, H); panel.addPath(hole);
    c.save(); c.shadowColor = 'rgba(70,40,70,.42)'; c.shadowBlur = 20 * SS; c.fillStyle = PAPER; c.fill(panel, 'evenodd'); c.restore();
    c.save(); c.clip(panel, 'evenodd');
    c.fillStyle = 'rgba(230,212,184,.5)';
    for (let i = 0; i < 260; i++) { const x = r() * W, y = r() * H; if (x > COLX - 4 && x < COLX + COLW + 4) continue; c.beginPath(); c.arc(x, y, 1.6, 0, TAU); c.fill(); }
    const conf = ['#ffc6c0', '#cdeab4', '#c9e3f6', '#ffe3a0', '#e3d6f6'];
    for (let i = 0; i < 26; i++) { const x = r() < .5 ? r() * (COLX - 30) + 10 : COLX + COLW + 20 + r() * (COLX - 30), y = r() * H; c.save(); c.translate(x, y); c.rotate(r() * 6); c.fillStyle = conf[i % 5]; c.globalAlpha = .7; c.fillRect(-5, -3, 10, 6); c.restore(); }
    grainFill(c, .6);
    c.restore();
    c.strokeStyle = '#fffcf4'; c.lineWidth = 3; c.stroke(hole);
    /* левая сторона: название и высотомер */
    c.save(); c.translate(LC + 2, 104); c.rotate(-.025);
    paperCard(c, -150, -72, 300, 146, { r: 20 });
    txt(c, 'Выше', -124, -26, 54, CORAL, { w: 900 });
    txt(c, 'облаков', -124, 30, 54, INK, { w: 900 });
    c.fillStyle = '#ffd04d'; c.fill(starP(118, -40, 15, 7, 2.6));
    c.restore();
    const tp = rrPath(TRK.x - TRK.w / 2, TRK.y1 - 14, TRK.w, TRK.y0 - TRK.y1 + 28, TRK.w / 2);
    cut(c, tp, '#ffffff', { blur: 10, sy: 4, sc: 'rgba(80,45,80,.22)', grain: false });
    c.save(); c.clip(tp);
    for (let i = 0; i < BIO.length; i++) { const a0 = BIO[i].a, a1 = i < BIO.length - 1 ? BIO[i + 1].a : TOP + 3000; c.fillStyle = BIO[i].col; const top = i === BIO.length - 1 ? TRK.y1 - 30 : trackY(a1); c.fillRect(TRK.x - 30, top, 60, trackY(a0) - top + (i === 0 ? 30 : 0)); }
    band(c, tp, 3, 'rgba(255,255,255,.45)'); band(c, tp, -4, 'rgba(60,30,60,.12)'); grainFill(c, 1);
    c.restore();
    for (let i = 0; i < BIO.length; i++) {
      const a0 = BIO[i].a, a1 = i < BIO.length - 1 ? BIO[i + 1].a : TOP, y = (trackY(a0) + trackY(a1)) / 2;
      c.save(); c.translate(TRK.x - 62, y); drawIcon(c, i); c.restore();
      txt(c, BIO[i].short, TRK.x + 38, y + 1, 24, INK2, { w: 700 });
    }
    /* правая сторона: карточки */
    paperCard(c, RX, 36, 300, 150);
    txt(c, 'высота', RX + 28, 72, 24, INK2, { w: 700 });
    paperCard(c, RX, 206, 300, 108);
    txt(c, 'собрано', RX + 28, 238, 24, INK2, { w: 700 });
    paperCard(c, RX, 334, 300, 72);
    txt(c, 'рекорд', RX + 28, 371, 24, INK2, { w: 700 });
    txt(c, 'как играть', HELP.x + 58, HELP.y + 1, 26, INK, { w: 700 });
  }, 1);
}
function miniHero(c, x, y, s, face) {
  const h = { x: 0, y: 0, vx: 0, vy: 0, dir: 1, sq: 0, face, blink: S.hero.blink, dizzy: 0, balT: 0, chute: 0, crest: Math.sin(S.t * 2) * .08 };
  c.save(); c.translate(x, y); c.scale(s * 1.24 / HSC, s * 1.24 / HSC); drawHero(c, h, S.t); c.restore();   // на шкале — прежний размер
}
function drawPanels(c) {
  blit(c, frameSpr(), 0, 0);
  const m = Math.floor(S.maxAlt / 10);
  c.font = `900 66px ${FONT}`; const mw = c.measureText(String(m)).width;
  txt(c, String(m), RX + 28, 136, 66, INK, { w: 900 });
  txt(c, 'м', RX + 36 + mw, 146, 34, INK2, { w: 800 });
  const kind = BIO[bioAt(S.maxAlt)].item;
  c.save(); c.translate(RX + 46, 282); c.scale(1.15, 1.15); blit(c, itemSpr(kind), 0, 0); c.restore();
  txt(c, '× ' + S.got, RX + 80, 283, 44, INK, { w: 900 });
  txt(c, GAME.best ? String(GAME.best) : '—', RX + 274, 372, 32, CORAL, { w: 900, align: 'right' });
  blit(c, helpBtnSpr(), HELP.x, HELP.y);
  const hint = !A.isTouch ? ['← →  или мышь', 'Тимоша прыгает сам'] : S.ctl === 'tilt' ? ['Наклоняйте телефон', 'Тимоша полетит туда же'] : ['Держите палец', 'слева или справа'];
  txt(c, hint[0], RX + 150, 616, 28, INK, { w: 800, align: 'center' });
  txt(c, hint[1], RX + 150, 654, 24, INK2, { w: 600, align: 'center' });
  /* Тимоша на высотомере и флажок рекорда */
  if (S.bestAlt > 0) {
    const y = trackY(S.bestAlt);
    c.fillStyle = CORAL; c.beginPath(); c.moveTo(TRK.x - 24, y); c.lineTo(TRK.x - 46, y - 9); c.lineTo(TRK.x - 46, y + 9); c.closePath(); c.fill();
    c.fillStyle = '#b8563f'; c.fillRect(TRK.x - 24, y - 12, 3, 24);
  }
  const alt = S.mode === 'title' ? 0 : -S.hero.y;
  miniHero(c, TRK.x, trackY(Math.max(0, alt)) + 22, .62, S.hero.face);
}
function drawTag(c) {
  blit(c, spr('tag', 264, 136, 0, 0, (cc) => paperCard(cc, 6, 6, 248, 120, { r: 22 }), 1), 18, 18);
  const m = Math.floor(S.maxAlt / 10);
  c.font = `900 56px ${FONT}`; const mw = c.measureText(String(m)).width;
  txt(c, String(m), 46, 64, 56, INK, { w: 900 });
  txt(c, 'м', 54 + mw, 72, 30, INK2, { w: 800 });
  const kind = BIO[bioAt(S.maxAlt)].item;
  blit(c, itemSpr(kind), 62, 112);
  txt(c, '× ' + S.got, 90, 113, 32, INK, { w: 900 });
  blit(c, helpBtnSpr(), HELP.x, HELP.y);
}
function drawBanner(c) {
  const b = S.banner; if (!b) return;
  const a = b.t < .45 ? A.ease.outBack(b.t / .45) : b.t > 2.4 ? 1 - A.ease.inOutSine((b.t - 2.4) / .6) : 1;
  const cx = COLX + COLW / 2, cy = LAND ? 70 : 196, name = BIO[b.i].name;
  c.font = `900 34px ${FONT}`; const tw = c.measureText(name).width, w = tw + 112;
  c.save(); c.globalAlpha = clamp(a, 0, 1); c.translate(cx, cy - (1 - clamp(a, 0, 1)) * 30); c.rotate(-.02);
  const p = new Path2D(); p.moveTo(-w / 2 - 18, -30); p.lineTo(w / 2 + 18, -30); p.lineTo(w / 2 + 4, 0); p.lineTo(w / 2 + 18, 30); p.lineTo(-w / 2 - 18, 30); p.lineTo(-w / 2 - 4, 0); p.closePath();
  cut(c, p, BIO[b.i].col, { rim: 'rgba(255,255,255,.5)', shade: 'rgba(60,30,60,.18)', sw: 4, sy: 4, blur: 10, sc: 'rgba(70,40,80,.3)' });
  cut(c, rrPath(-w / 2 + 4, -24, w - 8, 48, 14), CREAM, { shadow: false, shade: '#efe1c8', sw: 3, ga: .8 });
  blit(c, iconSpr(b.i), -w / 2 + 38, 0);
  txt(c, name, -w / 2 + 64, 2, 34, INK, { w: 900 });
  c.restore();
}
function drawTip(c) {
  if (S.mode !== 'play' || S.tipT <= 0) return;
  const tilt = A.isTouch && S.ctl === 'tilt';
  const lines = !A.isTouch ? ['← → или мышь — ведите Тимошу'] : tilt ? ['Наклоняйте телефон —', 'Тимоша полетит туда же'] : ['Держите палец слева', 'или справа'];
  const a = clamp(S.tipT / .6, 0, 1) * clamp((7 - S.tipT) / .5, 0, 1), fs = LAND ? 26 : 30, lh = fs * 1.3, pic = A.isTouch ? 70 : 0;
  c.font = `700 ${fs}px ${FONT}`; const tw = Math.max(...lines.map((l) => c.measureText(l).width)), w = tw + 56 + pic, h = lines.length * lh + 30;
  const cx = COLX + COLW / 2, y = H - h - (LAND ? 26 : 70), tx = cx + pic / 2;
  c.save(); c.globalAlpha = a;
  blit(c, spr('tip' + lines.length + Math.round(w), w + 30, h + 30, 15, 15, (cc) => paperCard(cc, 0, 0, w, h, { r: 20 }), 1), cx - w / 2, y);
  lines.forEach((l, i) => txt(c, l, tx, y + 15 + lh * (i + .5) + 1, fs, INK, { w: 700, align: 'center' }));
  if (pic) phonePic(c, cx - w / 2 + 52, y + h / 2, tilt);
  c.restore();
}
/* маленький телефон в подсказке: качается (наклон) или мигает половинами (касание) */
function phonePic(c, x, y, tilt) {
  c.save(); c.translate(x, y + 30);
  if (tilt) c.rotate(Math.sin(S.t * 2.6) * .28);
  c.fillStyle = 'rgba(74,53,80,.18)'; c.fill(rrPath(-17, -58, 38, 62, 8));
  c.fillStyle = CREAM; c.strokeStyle = INK; c.lineWidth = 3; const ph = rrPath(-19, -60, 38, 62, 8); c.fill(ph); c.stroke(ph);
  c.fillStyle = '#bfe5f0'; c.fillRect(-14, -53, 28, 46);
  if (tilt) {
    const k = Math.sin(S.t * 2.6);
    const px = k * 8, py = -20;
    c.fillStyle = TM.cap; c.beginPath(); c.moveTo(px - 6, py - 4); c.quadraticCurveTo(px - 2, py - 15, px + 9, py - 12); c.quadraticCurveTo(px + 3, py - 10, px + 6, py - 4); c.fill();
    c.fillStyle = TM.brim; c.beginPath(); c.arc(px + 9, py - 12, 2.6, 0, TAU); c.fill();
    c.fillStyle = TM.skin; c.beginPath(); c.arc(px, py, 6, 0, TAU); c.fill();
    c.fillStyle = TM.brim; c.fillRect(px - 7, py - 6, 14, 3);
    c.fillStyle = TM.line; c.beginPath(); c.arc(px - 2.2, py, 1, 0, TAU); c.arc(px + 2.2, py, 1, 0, TAU); c.fill();
  } else {
    const left = Math.sin(S.t * 3) > 0;
    c.fillStyle = 'rgba(255,123,107,.55)'; c.fillRect(left ? -14 : 0, -53, 14, 46);
    c.fillStyle = CORAL; c.beginPath(); c.arc(left ? -7 : 7, -18, 5.5, 0, TAU); c.fill();
  }
  c.restore();
}
function drawRecordFlag(c) {
  if (S.bestAlt < 400 || S.mode === 'title') return;
  const sy = (-S.bestAlt - S.camY) * K;
  if (sy < 20 || sy > H - 10) return;
  const x = COLX + COLW - 12;
  c.save();
  cut(c, rrPath(x - 112, sy - 36, 108, 32, 12), CORAL, { rim: '#ffa79b', shade: '#e05d50', sw: 3, sy: 2, blur: 5 });
  txt(c, 'рекорд', x - 58, sy - 19, 21, '#fff', { w: 800, align: 'center' });
  c.restore();
}
function drawCoverTitle(c) {
  blit(c, spr('ctitle', 720, 280, 20, 20, (cc) => {
    cc.rotate(-.03);
    paperCard(cc, 20, 20, 650, 196, { r: 28 });
    txt(cc, 'Выше облаков', 54, 98, 74, INK, { w: 900 });
    txt(cc, 'прыг-скок до самой луны', 58, 168, 36, CORAL, { w: 800 });
    cc.fillStyle = '#ffd04d'; cc.fill(starP(640, 44, 24, 11, 4));
  }, 1), 40, 30);
}
function draw(c, g) {
  if (LAND && !COVER) { c.fillStyle = PAPER; c.fillRect(0, 0, W, H); }
  drawWorld(c);
  if (COVER) { drawCoverTitle(c); return; }
  drawRecordFlag(c);
  if (LAND) drawPanels(c);
  else if (S.mode !== 'title') drawTag(c);
  drawBanner(c);
  drawTip(c);
}

/* ---------------- обложка ---------------- */
function coverScene() {
  fresh(); S.mode = 'cover';
  const base = -12400; S.camY = base - VH; S.ground = false;
  S.plats = []; S.items = []; S.bugs = []; S.winds = []; S.far = []; S.mid = [];
  const P = (x, y, skin, w, v, o = {}) => { const p = { x, y: base + y, w, type: o.type || 'normal', skin, v, vx: 0, t: 0, press: 0, bob: 1, spring: o.spring || null, balloon: o.balloon || null, broke: false, bt: 0, vanish: false, vt: 0, gone: false }; S.plats.push(p); return p; };
  P(500, -50, 'cloud', 136, 0, { spring: { x: -14, c: 0 } });
  P(156, -100, 'peach', 122, 1, { balloon: { off: 0, ph: 0 } });
  P(640, -300, 'cloud', 108, 2, { type: 'move' });
  P(92, -44, 'fluff', 122, 0, { type: 'once' });
  P(676, -40, 'dry', 118, 1, { type: 'break' });
  for (const [x, y, k] of [[352, -238, 'star'], [392, -268, 'star'], [436, -284, 'star'], [262, -200, 'berry']]) S.items.push({ x, y: base + y, kind: k, ph: x, taken: false });
  S.bugs.push({ x: 640, x0: 640, y: base - 160, y0: base - 160, amp: 0, sp: 0, ph: 0, state: 'sleep', t: 0, at: 0, hitT: 0, vx: 0, vy: 0, dir: -1 });
  S.mid.push({ kind: 'cloud', x: 120, yl: S.camY * .55 + 300, v: 1, flip: false, ph: 0 }, { kind: 'pinkcloud', x: 660, yl: S.camY * .55 + 420, v: 0, flip: true, ph: 0 });
  S.far.push({ kind: 'bank2', x: 300, yl: S.camY * .22 + 380, v: 0, flip: false, ph: 0 }, { kind: 'streak', x: 560, yl: S.camY * .22 + 120, v: 1, flip: false, ph: 0 });
  Object.assign(S.hero, { x: 476, y: base - 196, vy: -420, vx: -60, dir: -1, face: 'joy', faceT: 99, sq: .08, crest: .45, crestV: 0 });
}

A.game({
  id: 'hop', tone: 'light', title: 'Выше облаков', width: W, height: H, orientation: LAND ? 'landscape' : 'portrait', music: 'sky',
  keys: { Slash: 'help', KeyH: 'help', KeyZ: 'none', KeyJ: 'none', KeyK: 'none', KeyX: 'none', KeyL: 'none', ShiftLeft: 'none' },
  help: {
    desktop: '<kbd>←</kbd> <kbd>→</kbd> или <kbd>A</kbd> <kbd>D</kbd> — влево-вправо · мышь — Тимоша тянется к курсору · <kbd>?</kbd> — подсказка',
    short: '← → или A D — влево-вправо · мышь — Тимоша тянется к курсору',
    touch: ''
  },
  init(g) {
    GAME = g;
    S.bestAlt = +A.store.get('hop.bestAlt', '0') || 0;
    /* надписи запекаются в холсты: как только кириллица Rubik загрузится — перезапечь (иначе останется запасной шрифт) */
    if (document.fonts && document.fonts.load) { document.fonts.load('900 40px Rubik', 'Выше облаков рекорд м').then(() => CACHE.clear()).catch(() => {}); document.fonts.ready.then(() => CACHE.clear()).catch(() => {}); }
    addEventListener('deviceorientation', onTilt);
    window.__hop = () => S;
    window.__hopHero = (c, h, t) => drawHero(c, Object.assign({ x: 0, y: 0, vx: 0, vy: 0, dir: 1, sq: 0, face: 'idle', blink: 3, dizzy: 0, balT: 0, chute: 0, crest: 0 }, h), t || 0);   // для галереи поз в самопроверке
    Object.assign(S, { W, H, WW, K, COLX, COLW, VH, LAND, JUMP, G, HS, BIO, HELP, HAS_TILT, TILT_DZ, FOOT, HSC });
    S.ctl = A.isTouch ? loadCtl() : 'keys';
    if (COVER) { coverScene(); return; }
    title();
  },
  update, draw
});
})();
