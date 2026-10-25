/* «Каляка» — тетрадка в клетку, мир нарисован синей шариковой ручкой (утверждённый концепт concept-2, 24.10:
   владелец — «очень нравится… как же красиво будет. Делай»). Человечек Каляка сам идёт по странице слева направо;
   игрок дорисовывает красной ручкой мостики, горки и лесенки — каждый штрих становится настоящей опорой. Чернил мало,
   поэтому каждая страница — маленькая головоломка: ямки, высокие ступеньки, спящий кот, кнопка и ворота, змей «ням?»,
   пружинка, коробки «хрупко!». Десять страниц, на каждой — звезда и две звёздочки-бонуса, за страницу — оценка.
   Управление: мышь/палец — рисовать; правая кнопка или «ластик» — стереть штрих; пробел или «Иди!» — Каляка пошёл
   (после запуска — «Заново»: страница переигрывается, рисунок остаётся). Упал — «ой!», и страница заново.
   Всё рисуется кодом: линии — из гладкого шума (как в концепте), бумага и земля — один раз в свой холст на страницу,
   живое (Каляка, кот, змей, звёзды) «дышит» — линии перерисовываются 8 раз в секунду, как в рисованном мультфильме. */
(() => {
'use strict';
const A = Arcade, SND = A.sound;
const LAND = (() => { try { return innerWidth > (innerHeight - 110) * 1.15; } catch (e) { return false; } })();
const W = LAND ? 1280 : 720, H = LAND ? 720 : 1280, TAU = Math.PI * 2;
const PARAMS = new URLSearchParams(location.search), COVER = PARAMS.has('cover');
/* мир страницы — 900×540 «клеточных» единиц; на экране это рамка-кадр (широкое окно — слева, кнопки справа;
   книжное — посередине, кнопки снизу). Рисование, физика и попадания — в единицах мира через одно и то же PAN. */
const LW = 900, LH = 540;
const PAN = LAND ? { x: 112, y: 122, k: 1.06 } : { x: 8, y: 298, k: 704 / 900 };
PAN.w = LW * PAN.k; PAN.h = LH * PAN.k;
const WM = LAND ? 1 : 1.3;                 // толщина линий мира: на телефоне кадр мельче — линии чуть толще
const INK = '#1d3a9e', INK2 = '#2b4fb8', RED = '#d8323a', PAPER = '#fbf9f1', SCRAP = '#fffdf7', MUTED = '#3c4a78';
const HANDF = '"Lora", Georgia, "Times New Roman", serif';
const clamp = (v, a, b) => (v < a ? a : v > b ? b : v), lerp = (a, b, t) => a + (b - a) * t, dist = (ax, ay, bx, by) => Math.hypot(ax - bx, ay - by);
const eOut = (t) => 1 - (1 - t) ** 3;

/* ---------------- линии «от руки» ---------------- */
function rng(seed) { return () => { seed = (seed + 0x6D2B79F5) | 0; let t = Math.imul(seed ^ (seed >>> 15), 1 | seed); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
const NZ = new Map();
function noise(seed) {
  let f = NZ.get(seed); if (f) return f;
  if (NZ.size > 4000) NZ.clear();
  f = noise0(seed); NZ.set(seed, f); return f;
}
function noise0(seed) {
  const r = rng(seed * 9973 + 17), f0 = .02 + r() * .03, f1 = (.02 + r() * .03) * 2, f2 = (.02 + r() * .03) * 3, f3 = (.02 + r() * .03) * 4, p0 = r() * 7, p1 = r() * 7, p2 = r() * 7, p3 = r() * 7;
  return (t) => (Math.sin(t * f0 + p0) + Math.sin(t * f1 + p1) * .5 + Math.sin(t * f2 + p2) * .33 + Math.sin(t * f3 + p3) * .25) / 1.6;
}
function resample(pts, step = 3) {
  const out = [];
  for (let i = 0; i < pts.length - 1; i++) { const a = pts[i], b = pts[i + 1], d = Math.hypot(b[0] - a[0], b[1] - a[1]), n = Math.max(1, Math.ceil(d / step));
    for (let k = 0; k < n; k++) { const t = k / n; out.push([a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t]); } }
  out.push(pts[pts.length - 1]); return out;
}
function smooth(pts, it = 2) {
  let p = pts;
  for (let k = 0; k < it; k++) { const q = [p[0]];
    for (let i = 0; i < p.length - 1; i++) { const a = p[i], b = p[i + 1]; q.push([a[0] * .75 + b[0] * .25, a[1] * .75 + b[1] * .25], [a[0] * .25 + b[0] * .75, a[1] * .25 + b[1] * .75]); }
    q.push(p[p.length - 1]); p = q; }
  return p;
}
const plen = (p) => { let s = 0; for (let i = 1; i < p.length; i++) s += Math.hypot(p[i][0] - p[i - 1][0], p[i][1] - p[i - 1][1]); return s; };
function wobble(base, n, amp) {
  let L = 0;
  return base.map((p, i) => { const j = i < base.length - 1 ? i + 1 : i - 1, s = i < base.length - 1 ? 1 : -1, nx = (base[j][0] - p[0]) * s, ny = (base[j][1] - p[1]) * s, l = Math.hypot(nx, ny) || 1;
    L += l; const off = n(L) * amp; return [p[0] - ny / l * off, p[1] + nx / l * off]; });
}
let R = rng(1);                            // случайность статичных слоёв (свой зерно на страницу)
/* «богатая» линия для статичных слоёв: прозрачность гуляет по длине — шарик ручки то жирнее, то суше */
function inkS(c, pts, o = {}) {
  const w = o.w || 2.3, col = o.col || INK, jit = o.jit ?? 1.3, passes = o.passes || 2, sm = o.smooth ?? 1, sd = o.seed ?? ((R() * 1e6) | 0);
  let base = sm ? smooth(pts, sm) : pts; base = resample(base, 2.5);
  if (base.length < 2) return;
  c.lineCap = 'round'; c.lineJoin = 'round'; c.strokeStyle = col;
  for (let pass = 0; pass < passes; pass++) {
    const q = wobble(base, noise(sd + pass * 31), jit * (pass ? 1.4 : 1));
    for (let i = 0; i < q.length - 1; i++) { c.globalAlpha = (pass ? .38 : .88) * (.78 + .22 * Math.sin(i * .13 + pass * 2 + sd % 7)); c.lineWidth = pass ? w * .55 : w;
      c.beginPath(); c.moveTo(q[i][0], q[i][1]); c.lineTo(q[i + 1][0], q[i + 1][1]); c.stroke(); }
    if (!pass && o.dot !== false) { c.globalAlpha = .8; c.fillStyle = col; c.beginPath(); c.arc(q[0][0], q[0][1], w * .75, 0, TAU); c.fill(); }
  }
  c.globalAlpha = 1;
}
/* быстрая линия для живого (каждый кадр): два прохода — основной и «сухой» след рядом */
function inkF(c, pts, o = {}) {
  const w = o.w || 2.3, col = o.col || INK, jit = o.jit ?? 1.1, sd = o.seed || 1, sm = o.smooth ?? 1;
  let base = sm ? smooth(pts, sm) : pts; base = resample(base, o.step || 3);
  if (base.length < 2) return;
  c.lineCap = 'round'; c.lineJoin = 'round'; c.strokeStyle = col;
  for (let pass = 0; pass < (o.passes || 2); pass++) {
    const q = wobble(base, noise(sd + pass * 31), jit * (pass ? 1.4 : 1));
    c.globalAlpha = (o.a ?? 1) * (pass ? .4 : .9); c.lineWidth = pass ? w * .55 : w;
    c.beginPath(); c.moveTo(q[0][0], q[0][1]); for (let i = 1; i < q.length; i++) c.lineTo(q[i][0], q[i][1]); c.stroke();
  }
  c.globalAlpha = 1;
}
function ovalPts(cx, cy, rx, ry, o = {}) {
  const pts = [], a0 = o.a0 ?? 0, over = o.over ?? .35, wob = o.wob ?? .05, n = noise(o.seed || 3);
  for (let a = 0; a <= TAU + over; a += o.da || .09) { const r = 1 + n(a * 60) * wob; pts.push([cx + Math.cos(a + a0) * rx * r, cy + Math.sin(a + a0) * ry * r]); }
  return pts;
}
const circS = (c, cx, cy, rx, ry, o = {}) => inkS(c, ovalPts(cx, cy, rx, ry, { a0: R() * TAU, seed: (R() * 1e5) | 0, ...o }), { smooth: 0, ...o });
const circF = (c, cx, cy, rx, ry, o = {}) => inkF(c, ovalPts(cx, cy, rx, ry, o), { smooth: 0, ...o });
function hatchS(c, path, box, o = {}) {
  c.save(); c.clip(path);
  const ang = o.ang ?? -.95, gap = o.gap || 9, ca = Math.cos(ang), sa = Math.sin(ang), D = Math.hypot(box[2], box[3]) / 2 + 10, cx = box[0] + box[2] / 2, cy = box[1] + box[3] / 2;
  for (let d = -D; d < D; d += gap * (.8 + R() * .4)) { const x0 = cx - sa * d - ca * D, y0 = cy + ca * d - sa * D, x1 = cx - sa * d + ca * D, y1 = cy + ca * d + sa * D;
    inkS(c, [[x0, y0], [x1, y1]], { w: o.w || 1.2, passes: 1, jit: .8, col: o.col || INK, dot: false, smooth: 0 }); }
  c.restore();
}
function hatchF(c, path, box, o = {}) {
  c.save(); c.clip(path);
  const ang = o.ang ?? .7, gap = o.gap || 5, ca = Math.cos(ang), sa = Math.sin(ang), D = Math.hypot(box[2], box[3]) / 2 + 4, cx = box[0] + box[2] / 2, cy = box[1] + box[3] / 2;
  c.strokeStyle = o.col || INK; c.lineWidth = o.w || 1.2; c.globalAlpha = o.a ?? .75; c.lineCap = 'round'; c.beginPath();
  let i = 0; for (let d = -D; d < D; d += gap) { const j = Math.sin(i++ * 1.7 + (o.seed || 0)) * 1.2; c.moveTo(cx - sa * d - ca * D, cy + ca * d - sa * D + j); c.lineTo(cx - sa * d + ca * D, cy + ca * d + sa * D - j); }
  c.stroke(); c.restore(); c.globalAlpha = 1;
}
function hand(c, t, x, y, size, o = {}) {
  c.save(); c.translate(x, y); if (o.rot) c.rotate(o.rot);
  c.font = `italic ${o.wt || 600} ${size}px ${HANDF}`; c.textAlign = o.align || 'left'; c.textBaseline = o.base || 'alphabetic';
  c.fillStyle = o.col || INK; c.globalAlpha = o.a ?? .92; c.fillText(t, 0, 0); c.restore();
}
const textW = (c, t, size, wt = 600) => { c.font = `italic ${wt} ${size}px ${HANDF}`; return c.measureText(t).width; };
function starPts(cx, cy, r1, r2, rot = 0) { const p = []; for (let i = 0; i <= 10; i++) { const a = -Math.PI / 2 + rot + i * Math.PI / 5, r = i % 2 ? r2 : r1; p.push([cx + Math.cos(a) * r, cy + Math.sin(a) * r]); } return p; }
const pathOf = (pts) => { const p = new Path2D(); p.moveTo(pts[0][0], pts[0][1]); for (let i = 1; i < pts.length; i++) p.lineTo(pts[i][0], pts[i][1]); p.closePath(); return p; };

/* ---------------- страницы ---------------- */
/* land — верхние края кусков земли слева направо (вниз — до низа листа); star — звезда (центр); bonus — две звёздочки;
   sol — решение (им проходит самопроверка; по «подсказке» показывается пунктиром). ink — запас чернил. */
const LEVELS = [
  { name: 'Ямка', hint: 'Нарисуй мостик через ямку и нажми «Иди!»', say: 'а он выдержит?..', ink: 470, start: 70,
    land: [[[-40, 418], [80, 420], [180, 414], [280, 418], [350, 421]], [[510, 416], [600, 412], [720, 417], [820, 413], [940, 415]]],
    star: [838, 362], bonus: [[430, 340], [660, 300]],
    sol: [[[336, 421], [430, 388], [524, 416]], [[582, 413], [660, 346], [738, 416]]],
    deco: [['sun', 770, 96], ['cloud', 300, 110, .9], ['cloud', 590, 180, .7], ['bird', 452, 112, 1], ['bird', 488, 92, .8], ['tree', 200], ['sign', 150, 'к звезде']] },
  { name: 'Ступенька', hint: 'Стена высоковата — нарисуй горку', say: 'высоко… я не прыгаю!', ink: 470, start: 70,
    land: [[[-40, 430], [120, 428], [260, 432], [436, 430]], [[432, 322], [560, 318], [700, 322], [940, 318]]],
    star: [840, 270], bonus: [[345, 318], [645, 216]],
    sol: [[[244, 432], [438, 318]], [[580, 320], [645, 258], [710, 320]]],
    deco: [['sun', 130, 92], ['cloud', 470, 110, .8], ['bird', 760, 110, 1], ['flower', 560], ['flower', 770], ['plane', 300, 150]] },
  { name: 'Две ямки', hint: 'Две ямки, а чернил мало — береги их', say: 'две ямки — два мостика?', ink: 430, start: 60,
    land: [[[-40, 420], [150, 422], [250, 418]], [[380, 372], [450, 368], [520, 372]], [[650, 420], [780, 416], [940, 420]]],
    star: [840, 368], bonus: [[315, 300], [585, 300]],
    sol: [[[240, 419], [315, 344], [388, 370]], [[512, 371], [585, 344], [660, 419]]],
    deco: [['sun', 450, 120], ['cloud', 160, 130, .8], ['cloud', 760, 150, .9], ['bird', 640, 96, .9], ['tree', 790]] },
  { name: 'Лесенка', hint: 'Ступеньки высокие — каждой нужна горка', say: 'я не умею прыгать!', ink: 660, start: 50,
    land: [[[-40, 450], [120, 448], [222, 450]], [[218, 382], [300, 380], [384, 382]], [[380, 312], [470, 310], [564, 312]], [[560, 240], [700, 238], [940, 240]]],
    star: [852, 190], bonus: [[262, 308], [720, 152]],
    sol: [[[130, 449], [222, 376], [268, 352]], [[300, 381], [384, 305]], [[484, 311], [566, 232]], [[650, 239], [720, 186], [790, 239]]],
    deco: [['sun', 110, 96], ['cloud', 420, 110, .8], ['bird', 560, 120, 1], ['bird', 590, 100, .7], ['flower', 830]] },
  { name: 'Кот спит', hint: 'Не разбуди кота — проведи Каляку над ним', say: 'тсс… котик спит', ink: 570, start: 60,
    land: [[[-40, 420], [200, 418], [460, 422], [640, 420]], [[742, 418], [940, 420]]],
    cat: { x: 415, y: 421 }, star: [845, 370], bonus: [[415, 256], [692, 306]],
    sol: [[[296, 420], [415, 306], [534, 421]], [[628, 421], [692, 352], [756, 418]]],
    deco: [['moon', 130, 100], ['cloud', 600, 120, .8], ['bird', 760, 110, .9], ['tree', 214], ['flower', 800]] },
  { name: 'Кнопка', hint: 'Ворота откроет кнопка на полке', say: 'закрыто?.. а кнопка — на полке!', ink: 440, start: 50,
    land: [[[-40, 430], [300, 428], [600, 432], [940, 430]]],
    blocks: [[250, 300, 470, 322]], button: { x0: 396, x1: 436, y: 300 }, gate: { x: 640, top: -20, bot: 430 },
    star: [850, 382], bonus: [[318, 248], [752, 312]],
    sol: [[[98, 429], [252, 298]], [[680, 430], [752, 360], [824, 430]]],
    deco: [['sun', 800, 100], ['cloud', 120, 120, .8], ['bird', 500, 110, 1], ['flower', 880]] },
  { name: 'Ням?', hint: 'Змей достанет всё, что ниже пунктира', say: 'он кусается?..', ink: 540, start: 60,
    land: [[[-40, 382], [150, 380], [300, 383]], [[650, 458], [780, 455], [940, 458]]],
    water: { x0: 300, x1: 650, surf: 478, reach: 420, sx: 470 },
    star: [850, 408], bonus: [[470, 296], [744, 350]],
    sol: [[[290, 383], [470, 340], [650, 392], [748, 402]]],
    deco: [['sun', 110, 96], ['cloud', 420, 120, .8], ['cloud', 760, 160, .7], ['bird', 600, 100, .9], ['tree', 190]] },
  { name: 'Пружинка', hint: 'Пружинка подбросит — нарисуй, куда приземлиться', say: 'это пружинка? уиии?', ink: 620, start: 50,
    land: [[[-40, 430], [150, 428], [262, 431]], [[700, 300], [800, 296], [940, 300]]],
    spring: { x0: 186, x1: 228, y: 420 }, star: [856, 250], bonus: [[284, 186], [770, 196]],
    sol: [[[318, 324], [706, 298]], [[716, 299], [770, 244], [824, 298]]],
    deco: [['sun', 560, 90], ['cloud', 90, 140, .8], ['bird', 430, 100, .9], ['flower', 880]] },
  { name: 'Хрупко!', hint: 'Коробка хрупкая — не роняй на неё Каляку', say: 'звезда — на коробке…', ink: 430, start: 50,
    land: [[[-40, 430], [200, 428], [330, 431]], [[452, 430], [700, 428], [940, 431]]],
    boxes: [{ x0: 590, y0: 360, x1: 770, y1: 429, label: 'не кантовать' }, { x0: 630, y0: 296, x1: 730, y1: 360, fragile: true, label: 'хрупко!' }],
    star: [722, 250], bonus: [[392, 312], [540, 256]],
    sol: [[[320, 431], [392, 356], [540, 304], [634, 294]]],
    deco: [['sun', 840, 100], ['cloud', 220, 120, .8], ['bird', 470, 110, 1], ['flower', 860], ['tree', 236]] },
  { name: 'Звезда', hint: 'Одной длинной линией — до самой звезды', say: 'последняя страница!', ink: 630, start: 50,
    land: [[[-40, 380], [150, 378], [262, 382]], [[520, 440], [600, 438], [700, 441], [940, 440]]],
    water: { x0: 262, x1: 520, surf: 476, reach: 418, sx: 390 }, cat: { x: 640, y: 439 },
    boxes: [{ x0: 770, y0: 378, x1: 880, y1: 439, fragile: true, label: 'хрупко!' }],
    star: [826, 326], bonus: [[392, 280], [640, 284]],
    sol: [[[252, 382], [392, 336], [520, 372], [640, 342], [774, 376]]],
    deco: [['moon', 700, 96], ['cloud', 150, 120, .8], ['bird', 480, 100, .9], ['bird', 510, 120, .7]] },
];
const N = LEVELS.length;

/* ---------------- физика ---------------- */
const KS = .86, HW = 8, BODY = 86, STEP = 12, SNAP = 9, SPEED = 105, GRAV = 1300, FRAG = 380, SPR_VY = -700, SPR_VX = 170, CENTER = 56, CATS = 1.25, SNS = 1.3;
function mkSeg(ax, ay, bx, by, tag) {
  const dx = bx - ax, dy = by - ay, fl = Math.abs(dx) > .01 && Math.abs(dy / dx) < 2.2;
  return { ax, ay, bx, by, x0: Math.min(ax, bx), x1: Math.max(ax, bx), m: Math.abs(dx) > .01 ? dy / dx : 0, floor: fl, tag };
}
function rectSegs(out, x0, y0, x1, y1, tag) { out.push(mkSeg(x0, y0, x1, y0, tag), mkSeg(x1, y0, x1, y1, tag), mkSeg(x1, y1, x0, y1, tag), mkSeg(x0, y1, x0, y0, tag)); }
function prep(L) {                         // контуры земли (сглаженные — как нарисованы) и неподвижные отрезки
  if (L._segs) return;
  L._lands = L.land.map((top) => { const p = smooth(top, 2), last = p[p.length - 1], first = p[0];
    return { top: p, poly: [...p, [last[0] + 3, LH + 60], [first[0] - 3, LH + 60]] }; });
  const s = [];
  for (const ld of L._lands) { const q = ld.poly; for (let i = 0; i < q.length; i++) { const a = q[i], b = q[(i + 1) % q.length]; s.push(mkSeg(a[0], a[1], b[0], b[1], 'land')); } }
  for (const b of L.blocks || []) rectSegs(s, b[0], b[1], b[2], b[3], 'land');
  L._segs = s;
}
function surfAt(segs, x, minY) {
  let best = Infinity, bs = null;
  for (const s of segs) { if (!s.floor || x < s.x0 || x > s.x1) continue; const y = s.ay + (x - s.ax) * s.m; if (y >= minY && y < best) { best = y; bs = s; } }
  return [best, bs];
}
function segX(p0x, p0y, p1x, p1y, s) {
  const q0x = s.ax, q0y = s.ay, q1x = s.bx, q1y = s.by, d = (p1x - p0x) * (q1y - q0y) - (p1y - p0y) * (q1x - q0x);
  if (Math.abs(d) < 1e-9) return false;
  const u = ((q0x - p0x) * (q1y - q0y) - (q0y - p0y) * (q1x - q0x)) / d, v = ((q0x - p0x) * (p1y - p0y) - (q0y - p0y) * (p1x - p0x)) / d;
  return u >= 0 && u <= 1 && v >= 0 && v <= 1;
}
const crosses = (segs, ax, ay, bx, by) => { for (const s of segs) if (segX(ax, ay, bx, by, s)) return s; return null; };
function wallHit(segs, x, nx, y) {
  const fx = nx + HW;
  if (crosses(segs, fx, y - STEP - 1, fx, y - BODY)) return true;
  for (const h of [STEP + 1, 34, 56, BODY]) if (crosses(segs, x + HW - .5, y - h, fx, y - h)) return true;
  return false;
}
function thin(raw, d) {                   // прореживание: пиксельная дрожь мыши не делает штрих «ступенчатым»
  const out = [raw[0]];
  for (let i = 1; i < raw.length - 1; i++) { const l = out[out.length - 1]; if (dist(l[0], l[1], raw[i][0], raw[i][1]) >= d) out.push(raw[i]); }
  out.push(raw[raw.length - 1]); return out;
}
function mkStroke(raw) {
  const pts = resample(smooth(thin(raw, 7), 3), 6), segs = [];
  for (let i = 1; i < pts.length; i++) segs.push(mkSeg(pts[i - 1][0], pts[i - 1][1], pts[i][0], pts[i][1], 'ink'));
  // «низ» мостика — сторона, куда смотрит нормаль вниз (для второй линии и досочек)
  let ny = 0; for (let i = 1; i < pts.length; i++) ny += pts[i][0] - pts[i - 1][0];
  return { pts, segs, len: plen(pts), seed: (Math.random() * 1e5) | 0, side: ny >= 0 ? 1 : -1 };
}
function violators(strokes, w) {
  const out = [];
  for (const st of strokes) { let low = null;
    for (const p of st.pts) if (p[0] > w.x0 + 6 && p[0] < w.x1 - 6 && p[1] > w.reach && (!low || p[1] > low[1])) low = p;
    if (low) out.push({ st, x: low[0], y: low[1] }); }
  return out;
}
function makeRun(L, strokes) {
  prep(L);
  const Rn = { L, strokes, t: 0, res: null, resT: 0, ev: [],
    k: { x: L.start, y: 0, vx: 0, vy: 0, mode: 'idle', ph: 0, blocked: 0, on: null, stepT: 0, landT: 9 },
    gate: L.gate ? { open: false, d: 0 } : null, btn: L.button ? { down: 0 } : null,
    boxes: (L.boxes || []).map((b) => ({ ...b, broken: false })), spring: L.spring ? { t: 9 } : null,
    snake: L.water ? { st: 'idle', t: 0, look: null, victims: null, target: null } : null,
    cat: L.cat ? { st: 'sleep', t: 0 } : null, got: (L.bonus || []).map(() => false) };
  Rn.k.y = surfAt(L._segs, L.start, -1e9)[0];
  return Rn;
}
function segsOf(Rn) {
  const L = Rn.L, out = L._segs.slice();
  for (const b of Rn.boxes) if (!b.broken) rectSegs(out, b.x0, b.y0, b.x1, b.y1, b.fragile ? 'fragile' : 'box');
  if (Rn.gate && Rn.gate.d < 1) { const g = L.gate, dy = -eOut(Rn.gate.d) * (g.bot - g.top + 40);
    out.push(mkSeg(g.x - 12, g.top + dy, g.x - 12, g.bot + dy, 'gate'), mkSeg(g.x + 12, g.top + dy, g.x + 12, g.bot + dy, 'gate')); }
  if (Rn.btn) { const b = L.button, h = Rn.btn.down ? 2 : 7; out.push(mkSeg(b.x0, b.y - h, b.x1, b.y - h, 'button')); }
  if (Rn.spring) { const s = L.spring; out.push(mkSeg(s.x0, s.y, s.x1, s.y, 'spring')); }
  for (const st of Rn.strokes) for (const s of st.segs) out.push(s);
  return out;
}
function launchRun(Rn) {
  Rn.k.mode = 'walk';
  if (Rn.snake) { const v = violators(Rn.strokes, Rn.L.water); if (v.length) { Rn.snake.st = 'wait'; Rn.snake.t = 0; Rn.snake.victims = v; Rn.snake.target = [v[0].x, v[0].y]; } }
}
function animRun(Rn, dt) {                 // то, что живёт и до запуска: ворота, пружинка, змей, кот
  Rn.t += dt;
  if (Rn.gate && Rn.gate.open && Rn.gate.d < 1) Rn.gate.d = Math.min(1, Rn.gate.d + dt * 1.3);
  if (Rn.spring) Rn.spring.t += dt;
  if (Rn.cat) Rn.cat.t += dt;
  const sn = Rn.snake;
  if (sn) { sn.t += dt;
    if (sn.st === 'wait' && sn.t > .35) { sn.st = 'lunge'; sn.t = 0; Rn.ev.push(['lunge']); }
    if (sn.st === 'lunge' && sn.t > .42 && sn.victims) { const vs = sn.victims; sn.victims = null;
      Rn.strokes = Rn.strokes.filter((s) => !vs.some((v) => v.st === s)); Rn.ev.push(['eat', vs]); }
    if (sn.st === 'lunge' && sn.t > 1) { sn.st = 'idle'; sn.t = 0; sn.target = null; } }
}
function stepRun(Rn, dt) {
  animRun(Rn, dt);
  const k = Rn.k, L = Rn.L;
  if (Rn.res) Rn.resT += dt;
  if (k.mode === 'walk' && !Rn.res) {
    const segs = segsOf(Rn), nx = k.x + SPEED * dt;
    k.ph += dt * 11; k.stepT -= dt; if (k.stepT <= 0) { k.stepT = Math.PI / 11; Rn.ev.push(['step']); }
    if (nx > LW - 14 || wallHit(segs, k.x, nx, k.y)) { k.blocked += dt; k.ph -= dt * 11; }
    else {
      k.blocked = 0;
      const [sy, ss] = surfAt(segs, nx, k.y - STEP);
      k.x = nx;
      if (sy <= k.y + SNAP) { k.y = sy; k.on = ss;
        if (ss && ss.tag === 'spring') { k.mode = 'air'; k.vy = SPR_VY; k.vx = SPR_VX; Rn.spring.t = 0; Rn.ev.push(['spring']); }
        if (ss && ss.tag === 'button' && !Rn.btn.down) { Rn.btn.down = 1; Rn.gate.open = true; Rn.ev.push(['button']); } }
      else { k.mode = 'air'; k.vx = SPEED; k.vy = 0; k.on = null; }
    }
  } else if (k.mode === 'air') {
    const segs = segsOf(Rn);
    k.vy += GRAV * dt;
    let nx = k.x + k.vx * dt, ny = k.y + k.vy * dt;
    if (k.vy < 0 && crosses(segs, k.x, k.y - BODY, nx, ny - BODY)) { k.vy = 0; ny = k.y; Rn.ev.push(['bonk']); }
    if (k.vx > 0 && (nx > LW - 14 || wallHit(segs, k.x, nx, k.y))) { nx = k.x; k.vx = 0; }
    let landed = false;
    if (k.vy >= 0) { const [sy, ss] = surfAt(segs, nx, k.y - 3);
      if (sy <= ny) { const v = k.vy; ny = sy; landed = true; k.x = nx; k.y = ny; k.vy = 0; k.on = ss; k.landT = 0;
        if (ss && ss.tag === 'fragile' && v > FRAG && !Rn.res) { const b = Rn.boxes.find((q) => q.fragile && !q.broken && nx >= q.x0 - 1 && nx <= q.x1 + 1);
          if (b) { b.broken = true; Rn.res = 'box'; k.mode = 'air'; k.vx = 0; Rn.ev.push(['break', b]); } }
        else if (!Rn.res) { k.mode = 'walk'; Rn.ev.push(['land', v]); }
        else k.mode = 'down'; } }
    if (!landed) { k.x = nx; k.y = ny; }
  }
  k.landT += dt;
  if (Rn.res) return;
  const cx = k.x, cy = k.y - CENTER;
  L.bonus.forEach((b, i) => { if (!Rn.got[i] && dist(cx, cy, b[0], b[1]) < 38) { Rn.got[i] = true; Rn.ev.push(['bonus', i]); } });
  const w = L.water, c = L.cat;
  if (dist(cx, cy, L.star[0], L.star[1]) < 35) { Rn.res = 'win'; k.mode = 'happy'; Rn.ev.push(['win']); }
  else if (c && k.x + HW > c.x - 36 * CATS && k.x - HW < c.x + 34 * CATS && k.y > c.y - 34 * CATS && k.y - BODY < c.y) { Rn.res = 'cat'; k.mode = 'scared'; Rn.cat.st = 'awake'; Rn.cat.t = 0; Rn.ev.push(['cat']); }
  else if (w && k.x > w.x0 && k.x < w.x1 && k.y > w.surf - 4) { Rn.res = 'water'; k.mode = 'sunk'; k.y = w.surf; Rn.snake.st = 'peek'; Rn.snake.t = 0; Rn.ev.push(['water']); }
  else if (k.y > LH + 40) { Rn.res = 'fall'; Rn.ev.push(['fall']); }
  else if (k.blocked > 1.1 || Rn.t > 45) { Rn.res = 'stuck'; k.mode = 'stuck'; Rn.ev.push(['stuck']); }
}
/* прогон без экрана — для проверок и подбора страниц: __doodle().sim(i, strokes) */
function sim(i, raws) {
  const L = LEVELS[i], strokes = raws.map((r) => mkStroke(r)), Rn = makeRun(L, strokes);
  launchRun(Rn);
  for (let n = 0; n < 60 * 50 && !(Rn.res && Rn.resT > .1); n++) { stepRun(Rn, 1 / 60); Rn.ev.length = 0; }
  return { res: Rn.res, got: Rn.got.slice(), t: +Rn.t.toFixed(2), x: Math.round(Rn.k.x), y: Math.round(Rn.k.y), ink: Math.round(strokes.reduce((s, q) => s + q.len, 0)), budget: L.ink };
}

/* ---------------- звук ---------------- */
const now = () => SND.now();
const snd = {
  scribble() { if (!SND.ctx) return; SND.hiss(now(), .07, .03, 'bandpass', 2600 + Math.random() * 1800); },
  rub() { if (!SND.ctx) return; SND.hiss(now(), .09, .05, 'lowpass', 900 + Math.random() * 300); },
  step() { if (!SND.ctx) return; SND.tone(160 + Math.random() * 40, now(), .05, .035, 'sine', null, 90); },
  fall() { if (!SND.ctx) return; const t = now(); SND.tone(720, t, .7, .07, 'triangle', null, 180, .02); },
  oi() { if (!SND.ctx) return; const t = now(); SND.tone(520, t, .12, .07, 'triangle', null, 700); SND.tone(640, t + .13, .2, .07, 'triangle', null, 380); },
  splash() { if (!SND.ctx) return; const t = now(); SND.hiss(t, .5, .14, 'lowpass', 1300); SND.tone(300, t, .3, .1, 'sine', null, 110); SND.hiss(t + .08, .8, .05, 'bandpass', 2600); },
  boing() { if (!SND.ctx) return; const t = now(); SND.tone(150, t, .45, .16, 'sine', null, 620); SND.tone(300, t + .02, .3, .04, 'triangle', null, 900); },
  meow() { if (!SND.ctx) return; const t = now(); SND.tone(620, t, .16, .07, 'triangle', null, 900, .03); SND.tone(900, t + .15, .35, .07, 'triangle', null, 520); },
  crack() { if (!SND.ctx) return; const t = now(); SND.hiss(t, .25, .2, 'bandpass', 1800); SND.tone(220, t, .2, .14, 'square', null, 90); for (let k = 0; k < 4; k++) SND.hiss(t + .05 + k * .05, .05, .08, 'highpass', 3000); },
  gate() { if (!SND.ctx) return; const t = now(); SND.tone(180, t, .6, .05, 'sawtooth', null, 260, .05); SND.hiss(t, .6, .03, 'bandpass', 700); },
  nope() { if (!SND.ctx) return; const t = now(); SND.tone(330, t, .16, .06, 'sine', null, 290); SND.tone(262, t + .15, .24, .06, 'sine', null, 240); },
  flip() { if (!SND.ctx) return; const t = now(); SND.hiss(t, .35, .08, 'bandpass', 1400); SND.hiss(t + .12, .3, .05, 'highpass', 3500); },
  stamp() { if (!SND.ctx) return; const t = now(); SND.tone(110, t, .18, .2, 'sine', null, 60); SND.hiss(t, .08, .1, 'lowpass', 900); },
};

/* ---------------- состояние ---------------- */
let GAME = null;
const S = { mode: 'title', li: 0, strokes: [], hist: [], cur: null, eraser: false, run: null, saved: null, res: [], fails: 0, t: 0, hintT: 0,
  bubbles: [], parts: [], flip: null, winT: 0, failT: 0, quipT: 7, stamp: null, ptr: null, hover: null, hoverMouse: false, inkShake: 0,
  demo: null, fontsOK: false, total: 0, blink: 3, scribT: 0, startSaid: false, ended: false, layers: {} };
const Q = [];
const LV = () => LEVELS[S.li];
const inkUsed = () => S.strokes.reduce((s, q) => s + q.len, 0) + (S.cur ? S.cur.len : 0);
const inkLeft = () => Math.max(0, LV().ink - inkUsed());

const QUIPS = {
  idle: ['а он выдержит?..', 'красненьким, пожалуйста', 'только не криво…', 'я подожду', 'а если в клеточку?', 'мама, я в тетрадке!', 'чур, не стирать меня'],
  go: ['пошёл!', 'топ-топ', 'вперёд!', 'ну, держите меня', 'иду-иду'],
  land: ['держит!', 'щекотно!', 'красота!', 'ух!'],
  fall: ['ой!', 'ой-ой!', 'мамочки…', 'ой!'],
  win: ['ура!', 'звёздочка!', 'дошёл!', 'я молодец?'],
};
function say(who, text, life = 2.6) {
  S.bubbles = S.bubbles.filter((b) => b.who !== who);
  S.bubbles.push({ who, text, t: 0, life, seed: (Math.random() * 1e4) | 0 });
}

/* ---------------- ход игры ---------------- */
function loadPage(i) {
  S.li = i; S.strokes = []; S.hist = []; S.cur = null; S.eraser = false; S.fails = 0; S.saved = null;
  S.run = makeRun(LEVELS[i], S.strokes); S.mode = 'edit'; S.bubbles = []; S.parts = []; S.stamp = null;
  S.hintT = i === 0 ? 7 : 0; S.quipT = 9; S.startSaid = false; S.pageT = 0;
}
function go() {
  if (S.mode !== 'edit') return;
  if (S.cur) endStroke();
  S.eraser = false;
  S.saved = S.strokes.slice();
  S.run = makeRun(LV(), S.strokes.slice()); launchRun(S.run);
  S.mode = 'run'; S.hintT = 0;
  A.sound.play('click'); say('kal', A.pick(QUIPS.go), 1.4);
}
function backToEdit() {
  S.strokes = S.saved || S.strokes; S.run = makeRun(LV(), S.strokes); S.mode = 'edit'; S.parts = S.parts.filter((p) => p.k === 'crumb');
  S.bubbles = S.bubbles.filter((b) => b.who === 'kal' && b.keep);
  if (S.fails === 2) say('kal', 'нажми «подсказка» — покажу', 3.5);
}
function finishStrokes() { S.cur = null; }
function pushHist() { S.hist.push(S.strokes.slice()); if (S.hist.length > 60) S.hist.shift(); }
function undo() { if (S.mode !== 'edit') return; if (S.cur) { S.cur = null; return; } if (!S.hist.length) { snd.nope(); return; } S.strokes = S.hist.pop(); snd.rub(); }
function clearAll() { if (S.mode !== 'edit') return; if (!S.strokes.length) return; pushHist(); for (const st of S.strokes) crumbsAlong(st.pts, 6); S.strokes = []; snd.rub(); }
function showHint() {
  if (S.mode === 'run' || S.mode === 'fail') return;
  S.hintT = 6; say('kal', A.pick(['вот так, например', 'попробуй вот так', 'по пунктиру!']), 2.4);
}
function crumbsAlong(pts, every = 3) {
  for (let i = 0; i < pts.length; i += every) { const p = pts[i]; S.parts.push({ k: 'crumb', x: p[0], y: p[1], vx: (Math.random() - .5) * 60, vy: -40 - Math.random() * 60, g: 420, life: .9, max: .9, rot: Math.random() * 3, col: Math.random() < .6 ? '#e4a4ae' : RED }); }
}
function beginStroke(q) { S.cur = { raw: [q], len: 0, out: false }; S.hintT = Math.min(S.hintT, S.li === 0 ? 1.5 : 0); }
function addPt(q) {
  const c = S.cur; if (!c) return;
  q = [clamp(q[0], 0, LW), clamp(q[1], 0, LH)];
  const last = c.raw[c.raw.length - 1], d = dist(last[0], last[1], q[0], q[1]);
  if (d < 3) return;
  const rem = inkLeft();
  if (rem <= .5) { if (!c.out) { c.out = true; S.inkShake = .5; snd.nope(); say('kal', 'чернила кончились!', 1.8); } return; }
  if (d > rem) q = [last[0] + (q[0] - last[0]) * rem / d, last[1] + (q[1] - last[1]) * rem / d];
  c.raw.push(q); c.len += Math.min(d, rem);
  S.scribT -= 1; if (S.scribT <= 0) { S.scribT = 4; snd.scribble(); }
}
function endStroke() {
  const c = S.cur; S.cur = null;
  if (!c || c.len < 14 || c.raw.length < 2) return;
  pushHist(); S.strokes.push(mkStroke(c.raw));
}
function eraseAt(q) {
  const r = 22 / PAN.k;
  const hit = S.strokes.filter((st) => st.pts.some((p, i) => i && segDist(q, st.pts[i - 1], p) < r));
  if (!hit.length) return;
  pushHist(); S.strokes = S.strokes.filter((s) => !hit.includes(s));
  for (const st of hit) crumbsAlong(st.pts, 4);
  snd.rub();
}
function segDist(p, a, b) { const dx = b[0] - a[0], dy = b[1] - a[1], l = dx * dx + dy * dy || 1, t = clamp(((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / l, 0, 1); return dist(p[0], p[1], a[0] + dx * t, a[1] + dy * t); }

function handleEvents(Rn, quiet) {
  const k = Rn.k, L = Rn.L;
  for (const [e, a] of Rn.ev) {
    if (e === 'step') { if (!quiet) snd.step(); }
    else if (e === 'land') { if (!quiet && a > 200) A.sound.play('land', { vol: .6 }); if (a > 260 && Math.random() < .5) say('kal', A.pick(QUIPS.land), 1.2); }
    else if (e === 'bonus') { const b = L.bonus[a]; if (!quiet) A.sound.play('pling', { pitch: 1 + a * .25 }); burst(b[0], b[1], 14, ['#f0b429', INK, RED]); }
    else if (e === 'spring') { if (!quiet) snd.boing(); say('kal', 'уиии!', 1.4); }
    else if (e === 'button') { if (!quiet) { A.sound.play('click'); snd.gate(); } say('kal', 'щёлк!', 1.2); }
    else if (e === 'bonk') { if (!quiet) A.sound.play('hit', { vol: .5 }); say('kal', 'бум!', 1); }
    else if (e === 'lunge') { if (!quiet) A.sound.play('whoosh'); }
    else if (e === 'eat') { if (!quiet) A.sound.play('eat'); say('snake', 'ням!', 1.6); for (const v of a) crumbsAlong(v.st.pts, 3); }
    else if (e === 'win') { onWin(Rn, quiet); }
    else if (e === 'fall') { onFail('fall', quiet); }
    else if (e === 'water') { onFail('water', quiet); }
    else if (e === 'cat') { onFail('cat', quiet); }
    else if (e === 'break') { onFail('box', quiet, a); }
    else if (e === 'stuck') { onFail('stuck', quiet); }
  }
  Rn.ev.length = 0;
}
function burst(x, y, n, cols) { for (let i = 0; i < n; i++) { const a = Math.random() * TAU, s = 60 + Math.random() * 140; S.parts.push({ k: 'spark', x, y, vx: Math.cos(a) * s, vy: Math.sin(a) * s, g: 0, drag: 3, life: .7, max: .7, col: A.pick(cols) }); } }
function onWin(Rn, quiet) {
  const L = Rn.L; burst(L.star[0], L.star[1], 26, ['#f0b429', INK, RED, '#7a9be0']);
  say('kal', A.pick(QUIPS.win), 2);
  if (S.mode === 'title') return;
  const stars = 1 + Rn.got.filter(Boolean).length;
  S.res[S.li] = stars; S.mode = 'win'; S.winT = 0;
  if (!quiet) A.sound.play('win');
  S.stamp = { t: 0, grade: stars === 3 ? '5' : stars === 2 ? '4' : '3', word: stars === 3 ? 'отлично!' : stars === 2 ? 'хорошо' : 'дошёл!' };
}
function onFail(kind, quiet, box) {
  const L = S.run.L;
  if (kind === 'fall') { if (!quiet) snd.fall(); say('kal', A.pick(QUIPS.fall), 2); }
  if (kind === 'water') { if (!quiet) snd.splash(); say('kal', 'буль! мокро!', 2); say('snake', 'ням?', 2.2); splash(S.run.k.x, L.water.surf); }
  if (kind === 'cat') { if (!quiet) snd.meow(); say('cat', 'мяу?!', 2); say('kal', 'ой!', 1.6); }
  if (kind === 'box') { if (!quiet) snd.crack(); say('kal', 'хрусь!', 2); boxBits(box); }
  if (kind === 'stuck') { if (!quiet) snd.nope(); say('kal', A.pick(['тупик…', 'хм, стенка', 'не пройти…']), 2); }
  if (kind !== 'fall' && kind !== 'stuck' && !quiet) setTimeout(() => snd.oi(), 260);
  if (S.mode === 'title') return;
  S.mode = 'fail'; S.failT = 0; S.fails++; S.failKind = kind;
}
function splash(x, y) { for (let i = 0; i < 18; i++) S.parts.push({ k: 'drop', x: x + (Math.random() - .5) * 20, y, vx: (Math.random() - .5) * 200, vy: -150 - Math.random() * 200, g: 900, life: .9, max: .9 }); }
function boxBits(b) { for (let i = 0; i < 16; i++) S.parts.push({ k: 'bit', x: lerp(b.x0, b.x1, Math.random()), y: lerp(b.y0, b.y1, Math.random()), vx: (Math.random() - .5) * 240, vy: -100 - Math.random() * 160, g: 900, life: 1.2, max: 1.2, rot: Math.random() * 6, vr: (Math.random() - .5) * 10, s: 8 + Math.random() * 10 }); }
function nextPage() {
  if (S.li + 1 < N) { S.flip = { t: 0, did: false, then: () => loadPage(S.li + 1) }; snd.flip(); }
  else finish();
}

/* ---------------- экраны ---------------- */
function startDemo() {
  const L = LEVELS[0]; S.li = 0; S.strokes = []; S.run = makeRun(L, S.strokes); S.demo = { t: 0, ph: 'draw', raw: smooth(L.sol[0], 0) }; S.bubbles = []; S.parts = []; S.stamp = null;
}
function titleScreen(g) {
  S.mode = 'title'; S.ended = false; g.setPlaying(false); startDemo();
  g.screen({
    kicker: A.framed ? 'Досуг' : 'Аркада', title: 'Каляка',
    html: '<p>Каляка идёт по тетрадке к звезде, а на пути — ямки, спящий кот и змей «ням?». Дорисуй красной ручкой мостики и горки: каждая линия держит! Только чернил мало.</p>',
    button: 'Начать', onGo: startGame
  });
}
function startGame() {
  const g = GAME; S.res = []; S.ended = false; S.demo = null; loadPage(0); g.setPlaying(true); g.playMusic();
}
function finish() {
  const g = GAME; if (S.ended) return; S.ended = true;
  S.mode = 'end'; g.setPlaying(false); g.stopMusic();
  const total = S.res.reduce((s, v) => s + (v || 0), 0); S.total = total;
  const rec = g.submit(total);
  const grades = S.res.map((v) => (v === 3 ? 5 : v === 2 ? 4 : 3)), avg = grades.reduce((s, v) => s + v, 0) / grades.length;
  g.screen({
    kicker: 'Тетрадка пройдена', title: 'Каляка дошёл!',
    html: `<p class="score">★ ${total} из ${N * 3}</p><p>Десять страниц, средняя оценка — ${avg.toFixed(1).replace('.', ',')}. ${total === N * 3 ? 'Все звёздочки до одной!' : 'Звёздочки-бонусы ещё можно собрать.'}</p>` +
      (rec ? '<p class="record">Новый рекорд!</p>' : g.best ? `<p>Рекорд: ★ ${g.best}</p>` : ''),
    button: 'Ещё раз', onGo: startGame, alt: { label: A.framed ? 'К играм' : 'В аркаду', onGo: () => A.home('../index.html') }
  });
}

/* ---------------- кнопки на листе ---------------- */
const UI = LAND ? {
  go: { x: 1088, y: 128, w: 176, h: 156 }, erase: { x: 1088, y: 304, w: 176, h: 74 }, undo: { x: 1088, y: 392, w: 176, h: 74 },
  clear: { x: 1088, y: 480, w: 176, h: 74 }, hint: { x: 1088, y: 568, w: 176, h: 74 },
  title: [124, 60, 40], sub: [126, 100, 23], inkBar: [836, 44, 224, 26], inkLbl: [822, 66, 24], stars: [[1122, 64], [1178, 64], [1234, 64]], starR: 22, page: [1176, 690, 22], bubble: 28, btnF: 27, goF: 50
} : {
  go: { x: 190, y: 852, w: 340, h: 150 }, erase: { x: 16, y: 1040, w: 166, h: 96 }, undo: { x: 190, y: 1040, w: 166, h: 96 },
  clear: { x: 364, y: 1040, w: 166, h: 96 }, hint: { x: 538, y: 1040, w: 166, h: 96 },
  title: [44, 146, 56], sub: [360, 780, 30], inkBar: [176, 214, 520, 32], inkLbl: [44, 240, 30], stars: [[556, 104], [614, 104], [672, 104]], starR: 25, page: [676, 1250, 26], bubble: 30, btnF: 28, goF: 62
};
const BTNS = ['go', 'erase', 'undo', 'clear', 'hint'];
function btnAt(p) { for (const id of BTNS) { const b = UI[id]; if (p[0] >= b.x - 6 && p[0] <= b.x + b.w + 6 && p[1] >= b.y - 6 && p[1] <= b.y + b.h + 6) return id; } return null; }
function btnOn(id) {
  if (S.mode === 'title' || S.mode === 'end' || S.flip) return false;
  if (id === 'go') return S.mode === 'edit' || S.mode === 'run' || S.mode === 'fail';
  if (id === 'hint') return S.mode === 'edit';
  if (id === 'undo') return S.mode === 'edit' && (S.hist.length > 0);
  if (id === 'clear') return S.mode === 'edit' && S.strokes.length > 0;
  return S.mode === 'edit';
}
function press(id) {
  if (!btnOn(id)) { if (id !== 'go') snd.nope(); return; }
  if (id === 'go') { if (S.mode === 'edit') go(); else { S.fails += S.mode === 'run' ? 0 : 0; backToEdit(); A.sound.play('click'); } }
  else if (id === 'erase') { S.eraser = !S.eraser; A.sound.play('click'); }
  else if (id === 'undo') undo();
  else if (id === 'clear') clearAll();
  else if (id === 'hint') showHint();
}
const inPanel = (p) => p[0] >= PAN.x && p[0] <= PAN.x + PAN.w && p[1] >= PAN.y && p[1] <= PAN.y + PAN.h;
const toL = (p) => [(p[0] - PAN.x) / PAN.k, (p[1] - PAN.y) / PAN.k];
const toS = (x, y) => [PAN.x + x * PAN.k, PAN.y + y * PAN.k];

function attachInput(g) {
  const cv = g.canvas;
  const pos = (e) => { const r = cv.getBoundingClientRect(); return [(e.clientX - r.left) / r.width * W, (e.clientY - r.top) / r.height * H]; };
  let active = null;
  cv.addEventListener('pointerdown', (e) => { if (active != null) return; active = e.pointerId; S.hoverMouse = e.pointerType === 'mouse'; Q.push({ t: 'down', p: pos(e), rmb: e.button === 2 }); });
  cv.addEventListener('pointermove', (e) => {
    S.hover = pos(e); S.hoverMouse = e.pointerType === 'mouse';
    if (e.pointerId !== active) return;
    const list = (e.getCoalescedEvents && e.getCoalescedEvents()) || [];
    for (const ce of (list.length ? list : [e])) Q.push({ t: 'move', p: pos(ce) });
  });
  const up = (e) => { if (e.pointerId !== active) return; active = null; Q.push({ t: 'up', p: pos(e) }); if (e.pointerType !== 'mouse') S.hover = null; };
  cv.addEventListener('pointerup', up); cv.addEventListener('pointercancel', up);
  cv.addEventListener('pointerleave', () => { if (active == null) S.hover = null; });
}
function handleInput(g) {
  for (const ev of Q.splice(0)) {
    if (ev.t === 'down') {
      const b = btnAt(ev.p);
      if (b) { S.ptr = 'ui'; press(b); continue; }
      S.ptr = null;
      if (S.mode !== 'edit' || S.flip || !inPanel(ev.p)) { if (S.mode === 'run' && inPanel(ev.p) && !S.bubbles.some((q) => q.who === 'kal')) say('kal', 'я уже иду!', 1.2); continue; }
      const q = toL(ev.p);
      if (ev.rmb || S.eraser) { S.ptr = 'erase'; eraseAt(q); } else { S.ptr = 'draw'; beginStroke(q); }
    } else if (ev.t === 'move') {
      if (S.ptr === 'draw' && S.mode === 'edit') addPt(toL(ev.p));
      else if (S.ptr === 'erase' && S.mode === 'edit') eraseAt(toL(ev.p));
    } else if (ev.t === 'up') {
      if (S.ptr === 'draw' && S.mode === 'edit') { addPt(toL(ev.p)); endStroke(); }
      S.ptr = null;
    }
  }
  const inp = g.input;
  if (S.flip || S.mode === 'title' || S.mode === 'end') return;
  if (inp.pressed('action') || inp.pressed('start')) press('go');
  if (inp.pressed('undo')) undo();
  if (inp.pressed('restart')) { if (S.mode === 'edit') clearAll(); else if (S.mode === 'run' || S.mode === 'fail') press('go'); }
  if (inp.pressed('erase')) press('erase');
  if (inp.pressed('hint')) press('hint');
  // курсор-ручка вместо стрелки — над листом, пока можно рисовать
  const pen = S.hoverMouse && S.hover && inPanel(S.hover) && S.mode === 'edit';
  const want = pen ? 'none' : (S.hover && btnAt(S.hover) && btnOn(btnAt(S.hover)) ? 'pointer' : '');
  if (g.canvas.style.cursor !== want) g.canvas.style.cursor = want;
}

/* ---------------- цикл ---------------- */
function update(g, dt) {
  S.t += dt; S.blink -= dt; if (S.blink < -.13) S.blink = 2 + Math.random() * 3;
  if (S.inkShake > 0) S.inkShake -= dt;
  if (S.hintT > 0 && S.mode === 'edit') S.hintT -= dt;
  for (const b of S.bubbles) b.t += dt;
  S.bubbles = S.bubbles.filter((b) => b.t < b.life);
  updParts(dt);
  if (S.flip) { const f = S.flip; f.t += dt * 1.7; if (f.t >= 1 && !f.did) { f.did = true; f.then(); } if (f.t >= 2) S.flip = null; }
  if (S.stamp) S.stamp.t += dt;
  if (S.mode === 'title') { demoStep(dt); Q.length = 0; return; }
  if (S.mode === 'end') { Q.length = 0; if (S.run) { stepRun(S.run, dt); handleEvents(S.run, true); } return; }
  handleInput(g);
  const Rn = S.run;
  if (S.mode === 'edit') {
    Rn.strokes = S.strokes; animRun(Rn, dt);
    S.pageT = (S.pageT || 0) + dt;
    if (!S.startSaid && S.pageT > .7 && !S.flip) { S.startSaid = true; say('kal', LV().say, 3.4); }
    if (Rn.snake) { const v = violators(S.strokes.concat(S.cur && S.cur.raw.length > 1 ? [{ pts: S.cur.raw }] : []), LV().water); Rn.snake.look = v.length ? [v[0].x, v[0].y] : null;
      if (v.length && !S.bubbles.some((b) => b.who === 'snake')) say('snake', 'ням-ням?', 1.8); }
    S.quipT -= dt;
    if (S.quipT <= 0) { S.quipT = 8 + Math.random() * 5; if (!S.bubbles.length && !S.cur) say('kal', A.pick(QUIPS.idle), 2.4); }
  } else if (S.mode === 'run' || S.mode === 'fail' || S.mode === 'win') {
    stepRun(Rn, dt); handleEvents(Rn, false);
    if (S.mode === 'fail') { S.failT += dt; if (S.failT > 1.7) backToEdit(); }
    if (S.mode === 'win') { S.winT += dt; if (S.winT > .55 && S.stamp && !S.stamp.snd) { S.stamp.snd = true; snd.stamp(); } if (S.winT > 2.7 && !S.flip) { S.mode = 'next'; nextPage(); } }
  }
}
function demoStep(dt) {
  const d = S.demo; if (!d) return; d.t += dt;
  const Rn = S.run;
  if (d.ph === 'draw') { animRun(Rn, dt);
    const L = LEVELS[0], full = resample(L.sol[0], 5), n = Math.floor(clamp((d.t - .8) / 1.6, 0, 1) * (full.length - 1)) + 1;
    S.cur = d.t > .8 ? { raw: full.slice(0, n), len: 0 } : null;
    if (d.t > 2.6) { S.cur = null; S.strokes = [mkStroke(L.sol[0])]; S.run = makeRun(L, S.strokes.slice()); launchRun(S.run); d.ph = 'run'; d.t = 0; } }
  else if (d.ph === 'run') { stepRun(Rn, dt); handleEvents(Rn, true); if (Rn.res && Rn.resT > 2.2) startDemo(); }
}
function updParts(dt) {
  for (const p of S.parts) { p.life -= dt; if (p.drag) { p.vx -= p.vx * p.drag * dt; p.vy -= p.vy * p.drag * dt; } p.vy += (p.g || 0) * dt; p.x += p.vx * dt; p.y += p.vy * dt; if (p.vr) p.rot += p.vr * dt; }
  S.parts = S.parts.filter((p) => p.life > 0);
}

/* ================= рисование ================= */
let NOISE = null;
function paperNoise(c) {
  if (!NOISE) { const n = document.createElement('canvas'); n.width = n.height = 160; const x = n.getContext('2d'), d = x.createImageData(160, 160), r = rng(5);
    for (let i = 0; i < d.data.length; i += 4) { const v = r() < .5 ? 0 : 255; d.data[i] = v; d.data[i + 1] = v; d.data[i + 2] = v - (v ? 30 : 0); d.data[i + 3] = 6 + r() * 12; }
    x.putImageData(d, 0, 0); NOISE = n; }
  c.save(); c.fillStyle = c.createPattern(NOISE, 'repeat'); c.fillRect(0, 0, W, H); c.restore();
}
function paper(c) {
  c.fillStyle = PAPER; c.fillRect(0, 0, W, H);
  paperNoise(c);
  c.strokeStyle = '#9fb6dd'; c.lineWidth = 1; c.globalAlpha = .5;
  const gx = LAND ? 104 : 22, gy = LAND ? 14 : 14;
  c.beginPath(); for (let x = gx; x < W; x += 30) { c.moveTo(x + .5, 0); c.lineTo(x + .5, H); } for (let y = gy; y < H; y += 30) { c.moveTo(0, y + .5); c.lineTo(W, y + .5); } c.stroke();
  c.globalAlpha = 1;
  // поля и дырочки
  c.strokeStyle = '#e58b8f'; c.lineWidth = 2; c.globalAlpha = .8; c.beginPath();
  if (LAND) { c.moveTo(92, 0); c.lineTo(92, H); } else { c.moveTo(0, 268); c.lineTo(W, 268); }
  c.stroke(); c.globalAlpha = 1;
  const holes = LAND ? [[44, 150], [44, 390], [44, 630]] : [[150, 32], [360, 32], [570, 32]];
  for (const [x, y] of holes) { const gr = c.createRadialGradient(x, y - 2, 2, x, y, 15); gr.addColorStop(0, '#c9c2b0'); gr.addColorStop(.75, '#ddd6c4'); gr.addColorStop(1, '#efe9da'); c.fillStyle = gr; c.beginPath(); c.arc(x, y, 12, 0, TAU); c.fill(); }
  // кофейное колечко
  const [rx, ry] = LAND ? [1190, 660] : [610, 1196];
  c.save(); c.globalAlpha = .14; c.strokeStyle = '#8a5a2b'; c.lineWidth = 7; c.beginPath(); c.ellipse(rx, ry, 74, 70, 0, 0, TAU); c.stroke(); c.lineWidth = 2; c.globalAlpha = .2; c.beginPath(); c.ellipse(rx, ry, 78, 74, 0, .4, 5.2); c.stroke(); c.restore();
}
function vignette(c) { const vg = c.createRadialGradient(W / 2, H / 2, Math.min(W, H) * .5, W / 2, H / 2, Math.max(W, H) * .75); vg.addColorStop(0, 'rgba(80,70,40,0)'); vg.addColorStop(1, 'rgba(80,70,40,.16)'); c.fillStyle = vg; c.fillRect(0, 0, W, H); }
function panelFrame(c) {
  const x0 = PAN.x, y0 = PAN.y, x1 = PAN.x + PAN.w, y1 = PAN.y + PAN.h;
  inkS(c, [[x0 - 6, y0 + 1], [x1 + 4, y0 - 1]], { w: 2.6, smooth: 0 }); inkS(c, [[x1 + 1, y0 - 6], [x1 - 1, y1 + 5]], { w: 2.6, smooth: 0 });
  inkS(c, [[x1 + 5, y1 + 1], [x0 - 4, y1 - 1]], { w: 2.6, smooth: 0 }); inkS(c, [[x0, y1 + 6], [x0 + 1, y0 - 4]], { w: 2.6, smooth: 0 });
}
function scrap(c, x, y, w, h, rot, tape = true) {
  c.save(); c.translate(x, y); c.rotate(rot);
  c.shadowColor = 'rgba(60,50,30,.2)'; c.shadowBlur = 12; c.shadowOffsetY = 4; c.fillStyle = SCRAP;
  c.beginPath(); c.moveTo(0, 3); c.lineTo(w, 0); c.lineTo(w + 3, h - 2); c.lineTo(4, h); c.closePath(); c.fill(); c.shadowColor = 'transparent';
  if (tape) { c.fillStyle = 'rgba(235,220,170,.72)'; c.save(); c.translate(-14, -8); c.rotate(-.5); c.fillRect(0, 0, 64, 22); c.restore(); c.save(); c.translate(w - 40, -14); c.rotate(.45); c.fillRect(0, 0, 64, 22); c.restore(); }
  c.restore();
}
function logo(c, x, y, s, rot = -.025) {         // клочок бумаги со скотчем: «Каляка» + строка «что делать»
  const sub0 = 'Дорисуй мостик красной ручкой — и Каляка дойдёт до звезды', w = LAND ? textW(c, sub0, 20 * s) + 64 * s : Math.min(540 * s, W - x - 30), h = (LAND ? 126 : 150) * s;
  scrap(c, x, y, w, h, rot);
  c.save(); c.translate(x, y); c.rotate(rot);
  c.font = `900 ${54 * s}px Unbounded, ${A.FONT}`; c.textBaseline = 'alphabetic'; c.textAlign = 'left'; c.fillStyle = INK; c.fillText('Каляка', 26 * s, 68 * s);
  c.lineWidth = 1.4; c.strokeStyle = INK; c.globalAlpha = .5; c.strokeText('Каляка', 30 * s, 72 * s); c.globalAlpha = 1;
  const sub = 'Дорисуй мостик красной ручкой — и Каляка дойдёт до звезды', fs = 20 * s;
  if (textW(c, sub, fs) < w - 50 * s) hand(c, sub, 28 * s, 104 * s, fs, { wt: 600, col: MUTED, a: 1 });
  else { hand(c, 'Дорисуй мостик красной ручкой —', 28 * s, 100 * s, fs, { wt: 600, col: MUTED, a: 1 }); hand(c, 'и Каляка дойдёт до звезды', 28 * s, 100 * s + fs * 1.25, fs, { wt: 600, col: MUTED, a: 1 }); }
  c.restore();
}

/* --- статичный слой страницы: бумага, кадр, земля, небо --- */
function layer(g) {
  const sc = g.scale, key = (S.mode === 'title' || COVER ? 't' : '') + S.li + ':' + sc + ':' + (S.fontsOK ? 1 : 0);
  if (S.layers.key === key) return S.layers.c;
  const cv = S.layers.c && S.layers.c._w === Math.round(W * sc) ? S.layers.c : document.createElement('canvas');
  cv.width = Math.round(W * sc); cv.height = Math.round(H * sc); cv._w = cv.width;
  const c = cv.getContext('2d'); c.setTransform(sc, 0, 0, sc, 0, 0);
  const L = LV(); prep(L); R = rng(101 + S.li * 31);
  paper(c);
  c.save(); c.beginPath(); c.rect(PAN.x, PAN.y, PAN.w, PAN.h); c.clip(); c.translate(PAN.x, PAN.y); c.scale(PAN.k, PAN.k);
  levelStatic(c, L);
  c.restore();
  panelFrame(c);
  outside(c, L);
  vignette(c);
  S.layers = { key, c: cv };
  return cv;
}
function outside(c, L) {
  if (S.mode === 'title' || COVER) return;
  const u = UI, i = S.li;
  if (LAND) {
    hand(c, (i + 1) + '. ' + L.name, u.title[0], u.title[1], u.title[2], { wt: 700 });
    hand(c, L.hint, u.sub[0], u.sub[1], u.sub[2], { wt: 500, col: MUTED, a: 1 });
    hand(c, 'чернила', u.inkLbl[0], u.inkLbl[1], u.inkLbl[2], { align: 'right' });
    hand(c, 'стр. ' + (i + 1) + ' из ' + N, u.page[0], u.page[1], u.page[2], { align: 'center', a: .8 });
  } else {
    hand(c, 'страница ' + (i + 1) + ' из ' + N, 44, 84, 30, { wt: 500, col: MUTED, a: 1 });
    hand(c, L.name, u.title[0], u.title[1], u.title[2], { wt: 700 });
    hand(c, 'чернила', u.inkLbl[0], u.inkLbl[1], u.inkLbl[2]);
    // зачёркнутая домашка внизу — для уюта
    hand(c, '№ ' + (i + 3) + '. Реши уравнение:', 44, 1196, 26, { wt: 500, a: .75 }); hand(c, '2 + x = 5', 60, 1236, 26, { wt: 500, a: .75 });
    inkS(c, [[40, 1188], [250, 1186], [330, 1189]], { w: 2, passes: 1, jit: 1.5 }); hand(c, 'x = 3', 200, 1236, 24, { a: .55 });
  }
}
function levelStatic(c, L) {
  const wm = WM;
  // небо
  for (const d of L.deco || []) {
    const [t, x, y, s] = d;
    if (t === 'sun') { circS(c, x, y, 30, 29, { w: 2.2 * wm }); for (let i = 0; i < 12; i++) { const a = i / 12 * TAU; inkS(c, [[x + Math.cos(a) * 40, y + Math.sin(a) * 40], [x + Math.cos(a) * (i % 2 ? 50 : 56), y + Math.sin(a) * (i % 2 ? 50 : 56)]], { w: 1.9 * wm, passes: 1, smooth: 0 }); }
      inkS(c, [[x - 13, y - 4], [x - 8, y - 8], [x - 3, y - 4]], { w: 1.7 * wm, passes: 1 }); inkS(c, [[x + 3, y - 4], [x + 8, y - 8], [x + 13, y - 4]], { w: 1.7 * wm, passes: 1 }); inkS(c, [[x - 9, y + 8], [x, y + 14], [x + 9, y + 8]], { w: 1.7 * wm }); }
    if (t === 'moon') { const pts = []; for (let a = -1.9; a <= 1.9; a += .08) pts.push([x + Math.cos(a) * 30, y + Math.sin(a) * 30]); for (let a = 1.6; a >= -1.6; a -= .08) pts.push([x + 12 + Math.cos(a) * 22, y + Math.sin(a) * 26]);
      inkS(c, pts, { w: 2.2 * wm, smooth: 0 }); inkS(c, [[x - 12, y - 2], [x - 6, y + 1]], { w: 1.6 * wm, passes: 1 }); hand(c, '★', x + 60, y - 10, 18, { a: .7 }); hand(c, '·', x - 70, y + 20, 30, { a: .7 }); }
    if (t === 'cloud') { const pts = []; for (let a = 0; a <= 6.6; a += .05) { const r = 1 + .16 * Math.abs(Math.sin(a * 3)); pts.push([x + Math.cos(a) * 58 * s * r, y + Math.sin(a) * 22 * s * r]); }
      c.fillStyle = PAPER; c.fill(pathOf(pts)); inkS(c, pts, { w: 2 * wm, smooth: 0 }); inkS(c, [[x - 40 * s, y + 8 * s], [x + 30 * s, y + 10 * s]], { w: 1.2 * wm, passes: 1 }); }
    if (t === 'bird') inkS(c, [[x - 12 * s, y - 4 * s], [x - 5 * s, y - 8 * s], [x, y], [x + 5 * s, y - 8 * s], [x + 12 * s, y - 4 * s]], { w: 1.8 * wm, passes: 1 });
    if (t === 'plane') { inkS(c, [[x, y], [x + 54, y - 16], [x + 24, y + 7], [x, y]], { w: 1.9 * wm, smooth: 0 }); inkS(c, [[x + 24, y + 7], [x + 20, y + 20], [x + 31, y + 2]], { w: 1.9 * wm, smooth: 0 });
      c.save(); c.setLineDash([6, 8]); c.strokeStyle = INK; c.globalAlpha = .55; c.lineWidth = 1.5 * wm; c.beginPath(); for (let k = 0; k <= 40; k++) { const tt = k / 40; c[k ? 'lineTo' : 'moveTo'](x - 10 - tt * 160, y + 8 + Math.sin(tt * 9) * 16 + tt * 30); } c.stroke(); c.restore(); }
  }
  // вода (статичная часть) — в яме
  const w = L.water;
  if (w) { c.save(); c.beginPath(); c.rect(w.x0, w.surf + 6, w.x1 - w.x0, LH); c.clip();
    for (let y = w.surf + 18, k = 0; y < LH; y += 13, k++) { let x = w.x0 + 4 + ((k * 37) % 40); while (x < w.x1 - 6) { const Lx = 40 + R() * 70, seg = []; for (let t = 0; t <= Lx; t += 5) seg.push([x + t, y + Math.sin((x + t) * .08 + k) * 3]); inkS(c, seg, { w: 1.3 * wm, passes: 1, smooth: 0, dot: false }); x += Lx + 14 + R() * 20; } }
    for (const [x, y] of [[w.x0 + 50, w.surf + 40], [w.x1 - 70, w.surf + 52]]) { const s = []; for (let a = 0; a < 5.5; a += .25) s.push([x + Math.cos(a) * (a * 2.4), y + Math.sin(a) * (a * 1.6)]); inkS(c, s, { w: 1.5 * wm, passes: 1, smooth: 0 }); }
    c.restore(); }
  // земля
  for (const ld of L._lands) {
    const p = pathOf(ld.poly), xs = ld.poly.map((q) => q[0]), x0 = Math.min(...xs), x1 = Math.max(...xs);
    c.fillStyle = PAPER; c.fill(p);
    hatchS(c, p, [x0, 200, x1 - x0, LH], { gap: 9, ang: -.95, w: 1.15 * wm });
    inkS(c, ld.top, { w: 2.6 * wm, smooth: 0 });
    const f = ld.top[0], l = ld.top[ld.top.length - 1];
    if (f[0] > -5) inkS(c, [[f[0], f[1]], [f[0] - 3, f[1] + 60], [f[0] + 4, f[1] + 140], [f[0] - 2, LH + 10]], { w: 2.4 * wm });
    if (l[0] < LW + 5) inkS(c, [[l[0], l[1]], [l[0] + 4, l[1] + 70], [l[0] - 3, l[1] + 150], [l[0] + 2, LH + 10]], { w: 2.4 * wm });
    // травка
    for (let x = x0 + 40 + R() * 40; x < x1 - 30; x += 90 + R() * 110) { if (x < 0 || x > LW) continue; const y = surfAt(L._segs, x, -1e9)[0]; if (!isFinite(y) || nearObj(L, x)) continue; tuft(c, x, y + 1, wm); }
  }
  for (const b of L.blocks || []) { const p = pathOf([[b[0], b[1]], [b[2], b[1]], [b[2], b[3]], [b[0], b[3]]]); c.fillStyle = PAPER; c.fill(p); hatchS(c, p, [b[0], b[1], b[2] - b[0], b[3] - b[1]], { gap: 7, ang: -.95, w: 1.1 * wm });
    inkS(c, [[b[0], b[1]], [b[2], b[1] + 1], [b[2] - 1, b[3]], [b[0] + 1, b[3] - 1], [b[0], b[1]]], { w: 2.4 * wm, smooth: 0 }); }
  // деревья, цветы, указатель
  for (const d of L.deco || []) {
    const [t, x] = d; if (!['tree', 'flower', 'sign'].includes(t)) continue;
    const y = surfAt(L._segs, x, -1e9)[0];
    if (t === 'tree') { inkS(c, [[x - 4, y], [x - 2, y - 56], [x - 6, y - 86]], { w: 2.4 * wm }); inkS(c, [[x + 8, y], [x + 6, y - 54], [x + 10, y - 84]], { w: 2.4 * wm }); inkS(c, [[x + 5, y - 48], [x + 22, y - 68]], { w: 1.9 * wm });
      const cr = []; for (let a = 0; a <= 6.8; a += .05) { const r = 1 + .13 * Math.sin(a * 7); cr.push([x + 2 + Math.cos(a) * 56 * r, y - 126 + Math.sin(a) * 44 * r]); }
      c.fillStyle = PAPER; c.fill(pathOf(cr)); inkS(c, cr, { w: 2.2 * wm, smooth: 0 });
      for (const [ax, ay] of [[-22, -130], [12, -148], [26, -112], [-8, -104], [-32, -110], [36, -138]]) circS(c, x + ax, y + ay, 4.5, 4.5, { w: 1.5 * wm, passes: 1 }); }
    if (t === 'flower') { inkS(c, [[x, y], [x + 2, y - 26]], { w: 1.8 * wm, passes: 1 }); for (let i = 0; i < 5; i++) { const a = i / 5 * TAU; circS(c, x + 2 + Math.cos(a) * 7, y - 30 + Math.sin(a) * 7, 4.5, 4.5, { w: 1.4 * wm, passes: 1 }); } circS(c, x + 2, y - 30, 3, 3, { w: 1.4 * wm, passes: 1 });
      inkS(c, [[x + 1, y - 12], [x + 10, y - 18], [x + 2, y - 15]], { w: 1.4 * wm, passes: 1 }); }
    if (t === 'sign') { inkS(c, [[x, y], [x + 1, y - 62]], { w: 2.4 * wm }); const sw = 112; c.fillStyle = PAPER; c.fillRect(x - 18, y - 92, sw, 34);
      inkS(c, [[x - 18, y - 92], [x + sw - 14, y - 92], [x + sw, y - 75], [x + sw - 14, y - 58], [x - 18, y - 58], [x - 18, y - 92]], { w: 2 * wm, smooth: 0 }); hand(c, d[2], x - 9, y - 67, 22, { wt: 600 }); }
  }
  // надписи у предметов
  if (L.water) { hand(c, 'ням-зона', w.x0 + 14, w.reach + 24, 22, { col: INK2, a: .75 }); }
  if (L.button) { const b = L.button; hand(c, 'жми', b.x0 - 8, b.y - 44, 24, { wt: 700, align: 'center', rot: -.12 }); inkS(c, [[b.x0 - 2, b.y - 38], [b.x0 + 10, b.y - 22], [b.x0 + 14, b.y - 14]], { w: 1.7 * wm, passes: 1 }); inkS(c, [[b.x0 + 8, b.y - 18], [b.x0 + 14, b.y - 13], [b.x0 + 16, b.y - 21]], { w: 1.7 * wm, passes: 1, smooth: 0 }); }
}
function nearObj(L, x) {
  if (L.cat && Math.abs(x - L.cat.x) < 70) return true;
  if (L.gate && Math.abs(x - L.gate.x) < 40) return true;
  if (L.spring && x > L.spring.x0 - 20 && x < L.spring.x1 + 20) return true;
  if (Math.abs(x - L.start) < 30) return true;
  for (const b of L.boxes || []) if (x > b.x0 - 15 && x < b.x1 + 15) return true;
  for (const d of L.deco || []) if ((d[0] === 'flower' || d[0] === 'tree' || d[0] === 'sign') && Math.abs(x - d[1]) < 30) return true;
  return false;
}
function tuft(c, x, y, wm) { inkS(c, [[x - 5, y], [x - 7, y - 9]], { w: 1.5 * wm, passes: 1, dot: false, smooth: 0 }); inkS(c, [[x, y], [x + 1, y - 12]], { w: 1.5 * wm, passes: 1, dot: false, smooth: 0 }); inkS(c, [[x + 5, y], [x + 8, y - 8]], { w: 1.5 * wm, passes: 1, dot: false, smooth: 0 }); }

/* --- живое --- */
const boil = (fps = 8) => Math.floor(S.t * fps) % 4;
function drawStroke(c, st, o = {}) {
  const pts = st.pts, b = boil(5), w = 4.2 * WM;
  inkF(c, pts, { w, col: o.col || RED, jit: .9, seed: st.seed + b, smooth: 0, step: 4, a: o.a });
  if (pts.length < 2 || o.thin) return;
  // вторая линия и досочки — штрих похож на мостик
  const off = [], side = st.side * 6.5;
  for (let i = 0; i < pts.length; i++) { const a = pts[Math.max(0, i - 1)], bb = pts[Math.min(pts.length - 1, i + 1)], dx = bb[0] - a[0], dy = bb[1] - a[1], l = Math.hypot(dx, dy) || 1; off.push([pts[i][0] - dy / l * side, pts[i][1] + dx / l * side]); }
  inkF(c, off, { w: 2.1 * WM, col: o.col || RED, jit: 1.1, seed: st.seed + 50 + b, smooth: 0, step: 5, passes: 1, a: (o.a ?? 1) * .85 });
  c.strokeStyle = o.col || RED; c.lineWidth = 1.8 * WM; c.globalAlpha = (o.a ?? 1) * .8; c.lineCap = 'round'; c.beginPath();
  let acc = 11; for (let i = 1; i < pts.length; i++) { acc += Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]); if (acc >= 20 && i < pts.length - 1) { acc = 0; c.moveTo(pts[i][0], pts[i][1] + 1); c.lineTo(off[i][0] + (b % 2), off[i][1]); } }
  c.stroke(); c.globalAlpha = 1;
}
function drawStar(c, x, y, r, o = {}) {
  const sd = (o.seed || 7) + boil(), rot = o.rot || 0, pts = starPts(x, y, r, r * .43, rot);
  const p = pathOf(pts); c.fillStyle = o.fill || PAPER; c.fill(p);
  if (o.hatch !== false) hatchF(c, p, [x - r, y - r, r * 2, r * 2], { gap: r > 20 ? 5 : 4, ang: .6, w: 1.1 * WM, col: o.hcol || INK, a: .7, seed: sd });
  inkF(c, pts, { w: (r > 20 ? 2.8 : 2) * WM, smooth: 0, seed: sd, col: o.col || INK, step: 4 });
  if (o.face) { c.fillStyle = PAPER; c.beginPath(); c.ellipse(x, y + 3, r * .4, r * .25, 0, 0, TAU); c.fill(); c.fillStyle = INK; c.beginPath(); c.arc(x - r * .17, y + 2, 2.2 * WM, 0, TAU); c.arc(x + r * .17, y + 2, 2.2 * WM, 0, TAU); c.fill();
    inkF(c, [[x - 3.5, y + 7], [x, y + 9.5], [x + 3.5, y + 7]], { w: 1.4 * WM, passes: 1, seed: sd + 3 }); }
  if (o.rays) for (let i = 0; i < 8; i++) { const a = i / 8 * TAU + .2 + Math.sin(S.t * 2) * .05, r1 = r * 1.35 + Math.sin(S.t * 3 + i) * 2, r2 = r * 1.7;
    inkF(c, [[x + Math.cos(a) * r1, y + Math.sin(a) * r1], [x + Math.cos(a) * r2, y + Math.sin(a) * r2]], { w: 1.7 * WM, passes: 1, smooth: 0, seed: sd + i }); }
}
const KWM = 1.5 * WM;                     // Каляка, кот и змей нарисованы в своём масштабе — линии толще, чтобы читались
function drawKal(c, k, o = {}) {
  const t = S.t, sd = 100 + boil() * 13; let n = 0;
  const Ln = (pts, w, ex = {}) => inkF(c, pts, { w: w * KWM, seed: sd + (n++) * 7, jit: .8, ...ex });
  const walk = k.mode === 'walk', happy = k.mode === 'happy', sunk = k.mode === 'sunk';
  const air = k.mode === 'air' || k.mode === 'down', scared = k.mode === 'scared' || k.mode === 'stuck' || (air && (k.vy > 260 || S.mode === 'fail'));
  const worry = !!o.worry;
  c.save(); c.translate(k.x, k.y); c.scale(KS, KS);
  if (sunk) { c.translate(0, -16 + Math.sin(t * 5) * 4); }
  let bob = walk ? -Math.abs(Math.sin(k.ph)) * 3.5 : happy ? -Math.abs(Math.sin(t * 8)) * 26 : Math.sin(t * 2) * .8;
  if (k.landT < .18) bob += Math.sin(k.landT / .18 * Math.PI) * 6;
  const hx = 6, hy = -90 + bob, hip = [1, -40 + bob];
  // ноги
  if (!sunk) {
    let feet;
    if (walk) feet = [0, 1].map((i) => { const f = k.ph + i * Math.PI; return [4 + 14 * Math.sin(f), -Math.max(0, Math.cos(f)) * 8]; });
    else if (air || scared) feet = [[-8, -6 + bob * .4], [14, -10 + bob * .4]];
    else if (happy) feet = [[-6, bob + 2], [12, bob]];
    else feet = [[-9, 0], [17, -1]];
    for (const [fx, fy] of feet) { const kx = (hip[0] + fx) / 2 + (air ? -6 : 5), ky = (hip[1] + fy) / 2 - 2;
      Ln([hip, [kx, ky], [fx, fy]], 2.6); Ln([[fx - 7, fy], [fx + 7, fy - 1]], 3.2, { smooth: 0 }); }
  }
  // тело
  Ln([[hx - 3, hy + 24], hip], 2.8);
  // руки
  const sh = [1, -62 + bob];
  let hands;
  if (scared || air) hands = [[[-12, -80 + bob], [-18, -98 + bob]], [[16, -80 + bob], [26, -96 + bob]]];
  else if (happy) { const w1 = Math.sin(t * 14) * 5; hands = [[[-14, -82 + bob], [-20 + w1, -104 + bob]], [[18, -82 + bob], [28 - w1, -104 + bob]]]; }
  else if (walk) { const a = Math.sin(k.ph) * .7; hands = [[[sh[0] + Math.sin(.4 + a) * 13, sh[1] + Math.cos(.4 + a) * 13], [sh[0] + Math.sin(.6 + a) * 26, sh[1] + Math.cos(.6 + a) * 25]],
    [[sh[0] + Math.sin(.2 - a) * 13, sh[1] + Math.cos(.2 - a) * 13], [sh[0] + Math.sin(.3 - a) * 26, sh[1] + Math.cos(.3 - a) * 25]]]; }
  else if (worry) hands = [[[-18, -82 + bob], [-13, -104 + bob]], [[22, -57 + bob], [38, -63 + bob]]];
  else hands = [[[-8, -52 + bob], [-15, -40 + bob]], [[12, -52 + bob], [20, -40 + bob]]];
  for (const [el, hd] of hands) Ln([sh, el, hd], 2.5);
  for (const [, hd] of hands) if (hd[1] < -80 + bob) { c.fillStyle = PAPER; c.beginPath(); c.arc(hd[0], hd[1] - 2, 4.5, 0, TAU); c.fill(); circF(c, hd[0], hd[1] - 2, 4.5, 4.5, { w: 1.8 * KWM * .8, passes: 1, seed: sd + 77 }); }
  // шарфик
  const mv = walk || air ? 1 : happy ? 1.4 : .3, fl = Math.sin(t * 12) * 3 * mv, fl2 = Math.sin(t * 12 + 1) * 5 * mv;
  Ln([[hx - 13, hy + 23], [hx + 11, hy + 24]], 4.2, { smooth: 0 });
  Ln([[hx - 10, hy + 25], [hx - 26, hy + 32 + fl], [hx - 42, hy + 27 + fl2]], 3.2, { col: RED });
  Ln([[hx - 11, hy + 28], [hx - 30, hy + 39 + fl2 * .6], [hx - 44, hy + 38 + fl]], 2.2, { col: RED });
  // голова
  c.fillStyle = PAPER; c.beginPath(); c.arc(hx, hy, 24, 0, TAU); c.fill();
  circF(c, hx, hy, 24, 23, { w: 2.6 * KWM, seed: sd + 5, over: .3 });
  const cs = []; for (let a = 0; a < 11; a += .3) cs.push([hx + 1 + Math.cos(a) * 6 + a * .5, hy - 25 - a * 3 + Math.sin(a) * 4.5 + (walk ? Math.sin(t * 10) * a * .15 : 0)]);
  Ln(cs, 2, { smooth: 0 });
  // глаза — следят за ручкой
  const lk = o.look || [0, 0], lx = clamp(lk[0], -2.5, 2.5), ly = clamp(lk[1], -2.5, 2.5);
  const open = S.blink < 0 && !scared ? .15 : 1, big = scared ? 1.3 : 1;
  c.fillStyle = INK;
  if (happy) { Ln([[hx + 1, hy - 1], [hx + 5, hy - 6], [hx + 9, hy - 1]], 1.8, { passes: 1 }); Ln([[hx + 12, hy], [hx + 16, hy - 5], [hx + 20, hy]], 1.8, { passes: 1 }); }
  else { c.beginPath(); c.ellipse(hx + 5 + lx, hy - 2 + ly, 3.2 * big, 4.8 * big * open, 0, 0, TAU); c.ellipse(hx + 16 + lx, hy - 1 + ly, 3.2 * big, 4.8 * big * open, 0, 0, TAU); c.fill();
    if (open > .5) { c.fillStyle = PAPER; c.beginPath(); c.arc(hx + 6 + lx, hy - 4 + ly, 1.3, 0, TAU); c.arc(hx + 17 + lx, hy - 3 + ly, 1.3, 0, TAU); c.fill(); } }
  // рот
  if (happy) Ln([[hx + 4, hy + 8], [hx + 11, hy + 15], [hx + 18, hy + 8]], 1.8, { passes: 1 });
  else if (scared || sunk) circF(c, hx + 11, hy + 12, 4.5, 5.5, { w: 1.7 * KWM, passes: 1, seed: sd + 9 });
  else circF(c, hx + 11, hy + 11, 3, 3.2, { w: 1.6 * KWM, passes: 1, seed: sd + 9 });
  // румянец и брови
  c.strokeStyle = INK2; c.lineWidth = 1.1 * KWM * .8; c.globalAlpha = .7; c.beginPath();
  for (let i = 0; i < 3; i++) { c.moveTo(hx - 11 + i * 3, hy + 10); c.lineTo(hx - 8 + i * 3, hy + 4); }
  for (let i = 0; i < 2; i++) { c.moveTo(hx + 21 + i * 3, hy + 9); c.lineTo(hx + 23 + i * 3, hy + 4); }
  c.stroke(); c.globalAlpha = 1;
  if (worry || scared) { Ln([[hx + 1, hy - 13], [hx + 7, hy - 10]], 1.5, { passes: 1 }); Ln([[hx + 14, hy - 10], [hx + 20, hy - 13]], 1.5, { passes: 1 }); }
  else { Ln([[hx + 1, hy - 11], [hx + 7, hy - 14]], 1.5, { passes: 1 }); Ln([[hx + 14, hy - 14], [hx + 20, hy - 11]], 1.5, { passes: 1 }); }
  if (worry || k.mode === 'stuck') Ln([[hx - 28, hy - 22], [hx - 32, hy - 13], [hx - 28, hy - 11], [hx - 26, hy - 15], [hx - 28, hy - 22]], 1.4, { passes: 1 });
  c.restore();
}
function drawCat(c, x, y, st) {
  const sd = 300 + boil() * 11, awake = st.st === 'awake', t = S.t, br = awake ? 0 : Math.sin(t * 2.2) * 1.5;
  let n = 0; const Ln = (pts, w, ex = {}) => inkF(c, pts, { w: w * KWM * .6, seed: sd + (n++) * 5, jit: .8, ...ex });
  c.save(); c.translate(x, y); c.scale(CATS, CATS); if (awake) { const j = Math.min(1, st.t * 4); c.translate(0, -Math.sin(j * Math.PI) * 26); }
  c.fillStyle = PAPER; c.beginPath(); c.ellipse(0, -16 - br * .5, 34, 17 + br, 0, 0, TAU); c.fill();
  Ln([[-34, -2], [-36, -18 - br], [-22, -31 - br], [0, -34 - br], [24, -30 - br], [34, -16], [30, -2]], 2.2);
  Ln([[-30, -24], [-30, awake ? -46 : -42], [-18, -32]], 2, { smooth: 0 }); Ln([[-14, -33], [-6, awake ? -50 : -46], [-2, -34]], 2, { smooth: 0 });
  if (awake) { circF(c, -23, -20, 4, 5, { w: 1.6 * KWM * .6, passes: 1, seed: sd + 40 }); circF(c, -9, -21, 4, 5, { w: 1.6 * KWM * .6, passes: 1, seed: sd + 41 }); c.fillStyle = INK; c.beginPath(); c.arc(-22, -19, 2, 0, TAU); c.arc(-8, -20, 2, 0, TAU); c.fill(); }
  else { Ln([[-26, -20], [-20, -17]], 1.6, { passes: 1 }); Ln([[-12, -21], [-6, -18]], 1.6, { passes: 1 }); }
  Ln([[30, -6], [48, -10 + Math.sin(t * 1.5) * 2], [54, -24], [44, -30]], 2);
  for (let i = 0; i < 4; i++) Ln([[2 + i * 7, -28 - br], [5 + i * 7, -20]], 1.2, { passes: 1, smooth: 0 });
  c.restore();
  if (!awake) for (let i = 0; i < 3; i++) { const ph = (t * .45 + i / 3) % 1, a = Math.sin(ph * Math.PI);
    hand(c, i === 2 ? 'Z' : 'z', x + 20 + ph * 44 + i * 4, y - 58 - ph * 64, 20 + i * 7, { wt: 600, a: a * .85 }); }
}
function drawSnake(c, w, sn) {
  const t = S.t, sd = 500 + boil() * 11, x = w.sx, wy = w.surf, S2 = .85;
  c.save(); c.translate(x, wy); c.scale(SNS, SNS); c.translate(-x, -wy);
  const loc = (p) => [x + (p[0] - x) / SNS, wy + (p[1] - wy) / SNS];
  let n = 0; const Ln = (pts, ww, ex = {}) => inkF(c, pts, { w: ww * KWM * .6, seed: sd + (n++) * 5, jit: .8, ...ex });
  const bob = Math.sin(t * 1.6) * 3;
  // горбики
  for (const [dx, r] of [[-62, 20], [-10, 22]]) { const top = wy - r * 1.3 + bob * .6; c.fillStyle = PAPER; c.beginPath(); c.ellipse(x + dx, wy, r, r * 1.3 - bob * .6, 0, Math.PI, 0); c.fill();
    Ln([[x + dx - r, wy + 2], [x + dx - r + 2, top + 10], [x + dx, top], [x + dx + r - 2, top + 10], [x + dx + r, wy + 2]], 2.4); circF(c, x + dx - 4, top + 5, 2.5, 2.5, { w: 1.2 * KWM * .6, passes: 1, seed: sd + 60 }); }
  // голова: дремлет у поверхности; в броске — к добыче
  let hx = x + 46, hy = wy - 44 + bob;
  if (sn.st === 'lunge' && sn.target) { const e = Math.sin(clamp(sn.t / 1, 0, 1) * Math.PI), tg = loc(sn.target); hx = lerp(hx, tg[0], e); hy = lerp(hy, tg[1] - 6, e); }
  if (sn.st === 'peek') hy -= 6;
  Ln([[x + 28, wy + 2], [(x + 28 + hx) / 2 + 6, (wy + hy) / 2 + 8], [hx - 14, hy + 12]], 2.6);
  Ln([[x + 40, wy + 2], [(x + 40 + hx) / 2 + 12, (wy + hy) / 2 + 12], [hx + 2, hy + 18]], 2.6);
  c.fillStyle = PAPER; c.beginPath(); c.ellipse(hx, hy, 26 * S2 * 1.1, 22 * S2 * 1.1, 0, 0, TAU); c.fill();
  circF(c, hx, hy, 26 * S2 * 1.1, 22 * S2 * 1.1, { w: 2.4 * KWM * .6, seed: sd + 70 });
  const lk0 = sn.look || sn.target, look = lk0 && loc(lk0), lx = look ? clamp((look[0] - hx) / 40, -2, 2) : Math.sin(t * .7) * 1.5, ly = look ? clamp((look[1] - hy) / 40, -1.5, 2) : 0;
  circF(c, hx - 8, hy - 5, 5.5, 6.5, { w: 1.5 * KWM * .6, passes: 1, seed: sd + 71 }); circF(c, hx + 9, hy - 5, 5.5, 6.5, { w: 1.5 * KWM * .6, passes: 1, seed: sd + 72 });
  c.fillStyle = INK; c.beginPath(); c.arc(hx - 7 + lx, hy - 4 + ly, 2.7, 0, TAU); c.arc(hx + 10 + lx, hy - 4 + ly, 2.7, 0, TAU); c.fill();
  if (sn.st === 'lunge' && sn.t > .2 && sn.t < .6) circF(c, hx + 1, hy + 9, 7, 6, { w: 1.6 * KWM * .6, passes: 1, seed: sd + 73 });
  else Ln([[hx - 5, hy + 8], [hx + 1, hy + 12], [hx + 7, hy + 8]], 1.6, { passes: 1 });
  Ln([[hx - 9, hy - 18], [hx - 13, hy - 30], [hx - 5, hy - 34], [hx - 5, hy - 26]], 1.8); Ln([[hx + 11, hy - 18], [hx + 15, hy - 30], [hx + 7, hy - 34], [hx + 7, hy - 26]], 1.8);
  c.strokeStyle = INK2; c.lineWidth = 1; c.globalAlpha = .7; c.beginPath(); for (const cx of [hx - 18, hx + 17]) for (let i = 0; i < 3; i++) { c.moveTo(cx - 4 + i * 3, hy + 6); c.lineTo(cx - 1 + i * 3, hy); } c.stroke(); c.globalAlpha = 1;
  c.restore();
  sn._head = [x + (hx - x) * SNS, wy + (hy - wy) * SNS];
}
function drawBox(c, b, i) {
  const sd = 700 + i * 20 + boil(4);
  c.fillStyle = PAPER; c.fillRect(b.x0, b.y0, b.x1 - b.x0, b.y1 - b.y0);
  inkF(c, [[b.x0, b.y0], [b.x1, b.y0 + 1], [b.x1 - 1, b.y1], [b.x0 + 1, b.y1 - 1], [b.x0, b.y0]], { w: 2.4 * WM, smooth: 0, seed: sd });
  const w = b.x1 - b.x0; inkF(c, [[b.x0 + w * .42, b.y0], [b.x0 + w * .42, b.y0 + 16]], { w: 1.4 * WM, passes: 1, smooth: 0, seed: sd + 1 }); inkF(c, [[b.x0 + w * .58, b.y0], [b.x0 + w * .58, b.y0 + 16]], { w: 1.4 * WM, passes: 1, smooth: 0, seed: sd + 2 });
  const fs = b.fragile ? 23 : 22;
  hand(c, b.label, (b.x0 + b.x1) / 2 + (b.fragile ? 8 : 0), b.y1 - 14, fs, { align: 'center', wt: 700 });
  if (b.fragile) { const gx = b.x0 + 15, gy = b.y0 + 22;     // бокальчик
    inkF(c, [[gx - 7, gy - 8], [gx - 6, gy], [gx, gy + 4], [gx + 6, gy], [gx + 7, gy - 8]], { w: 1.5 * WM, passes: 1, seed: sd + 3 }); inkF(c, [[gx, gy + 4], [gx, gy + 10], [gx - 5, gy + 11], [gx + 5, gy + 11]], { w: 1.4 * WM, passes: 1, seed: sd + 4, smooth: 0 }); }
  else { const ax = b.x0 + 14, ay = b.y0 + 20; inkF(c, [[ax, ay + 10], [ax, ay - 8]], { w: 1.5 * WM, passes: 1, seed: sd + 5, smooth: 0 }); inkF(c, [[ax - 5, ay - 3], [ax, ay - 9], [ax + 5, ay - 3]], { w: 1.5 * WM, passes: 1, seed: sd + 6, smooth: 0 }); }
}
function drawGate(c, L, Rn) {
  const g = L.gate, dy = -eOut(Rn.gate.d) * (g.bot - g.top + 40), sd = 800 + boil(4), x = g.x;
  c.save(); c.translate(0, dy);
  c.fillStyle = PAPER; c.fillRect(x - 12, g.top, 24, g.bot - g.top);
  const p = new Path2D(); p.rect(x - 12, g.top, 24, g.bot - g.top); hatchF(c, p, [x - 12, g.top, 24, g.bot - g.top], { gap: 7, ang: .9, w: 1.1 * WM, a: .55, seed: sd });
  inkF(c, [[x - 12, g.top], [x - 11, g.bot]], { w: 2.4 * WM, seed: sd, smooth: 0 }); inkF(c, [[x + 12, g.top], [x + 11, g.bot]], { w: 2.4 * WM, seed: sd + 1, smooth: 0 });
  for (let y = g.top + 30; y < g.bot; y += 46) inkF(c, [[x - 18, y], [x + 18, y + 3]], { w: 2 * WM, seed: sd + y, smooth: 0, passes: 1 });
  const ly = g.bot - 120; c.fillStyle = PAPER; c.fillRect(x - 14, ly - 12, 28, 24); inkF(c, [[x - 14, ly - 12], [x + 14, ly - 12], [x + 14, ly + 12], [x - 14, ly + 12], [x - 14, ly - 12]], { w: 2 * WM, smooth: 0, seed: sd + 3 });
  inkF(c, [[x - 8, ly - 12], [x - 8, ly - 22], [x, ly - 27], [x + 8, ly - 22], [x + 8, ly - 12]], { w: 2 * WM, seed: sd + 4 }); c.fillStyle = INK; c.beginPath(); c.arc(x, ly + 1, 2.6, 0, TAU); c.fill();
  c.restore();
  if (Rn.gate.d < .05) hand(c, 'закрыто', x + 22, g.bot - 150, 24, { wt: 700, rot: -.08 });
}
function drawButton(c, L, Rn) {
  const b = L.button, h = Rn.btn.down ? 3 : 8, sd = 850 + boil(4), cx = (b.x0 + b.x1) / 2, r = (b.x1 - b.x0) / 2;
  const pts = []; for (let a = Math.PI; a <= TAU + .01; a += .15) pts.push([cx + Math.cos(a) * r * .8, b.y + Math.sin(a) * h * 1.6]);
  c.fillStyle = Rn.btn.down ? '#f3c9cc' : '#f7d9db'; c.fill(pathOf([...pts, [b.x1, b.y], [b.x0, b.y]]));
  inkF(c, pts, { w: 2.2 * WM, col: RED, seed: sd, smooth: 0 }); inkF(c, [[b.x0 - 4, b.y], [b.x1 + 4, b.y]], { w: 2.4 * WM, seed: sd + 1, smooth: 0 });
}
function drawSpring(c, L, Rn) {
  const s = L.spring, sd = 900 + boil(4), k = Rn.spring.t < .35 ? Math.sin(Rn.spring.t / .35 * Math.PI) : 0, y0 = s.y + 10, top = s.y - k * 26, cx = (s.x0 + s.x1) / 2;
  const z = []; for (let i = 0; i <= 6; i++) z.push([cx + (i % 2 ? 12 : -12) * (i && i < 6 ? 1 : 0), lerp(y0, top, i / 6)]);
  inkF(c, z, { w: 2 * WM, seed: sd, smooth: 0 });
  inkF(c, [[s.x0 - 2, top], [s.x1 + 2, top - 1]], { w: 3.2 * WM, seed: sd + 1, smooth: 0, col: RED });
}
function drawWater(c, w) {
  const t = S.t, pts = []; for (let x = w.x0; x <= w.x1; x += 6) pts.push([x, w.surf + Math.sin(x * .09 + t * 2) * 4]);
  inkF(c, pts, { w: 2 * WM, smooth: 0, seed: 950 + boil(4) });
  // пунктир: досюда достаёт змей
  c.save(); c.setLineDash([3 * WM, 9 * WM]); c.strokeStyle = INK2; c.globalAlpha = .6; c.lineWidth = 1.8 * WM; c.beginPath();
  for (let x = w.x0 + 4; x <= w.x1 - 4; x += 5) { const y = w.reach + Math.sin(x * .05 + t) * 2; x === w.x0 + 4 ? c.moveTo(x, y) : c.lineTo(x, y); } c.stroke(); c.restore();
}
function drawTrajectory(c, L, Rn) {          // пружинка: пунктир — куда полетит Каляка (с учётом нарисованного)
  const s = L.spring, segs = segsOf(Rn); let x = s.x0 + 1, y = s.y, vx = SPR_VX, vy = SPR_VY;
  c.save(); c.fillStyle = INK; c.globalAlpha = .45;
  for (let i = 0; i < 200; i++) { const dt = 1 / 60; vy += GRAV * dt; const nx = x + vx * dt, ny = y + vy * dt;
    if (vy > 0) { const [sy] = surfAt(segs, nx, y - 3); if (sy <= ny) break; }
    x = nx; y = ny; if (y > LH + 10 || x > LW) break;
    if (i % 4 === 0) { c.beginPath(); c.arc(x, y - CENTER, 2 * WM, 0, TAU); c.fill(); } }
  c.restore();
}
function drawPen(c, x, y, eraser) {          // курсор: красная ручка (или ластик) — в экранных координатах
  c.save(); c.translate(x, y);
  if (eraser) { c.rotate(-.6); c.fillStyle = '#f2c2c8'; c.fillRect(-4, -12, 56, 24); c.strokeStyle = INK; c.lineWidth = 2; c.strokeRect(-4, -12, 56, 24); c.beginPath(); c.moveTo(18, -12); c.lineTo(18, 12); c.stroke(); c.restore(); return; }
  c.rotate(-2.35);
  const s = LAND ? .62 : .5;
  c.scale(s, s);
  const pen = new Path2D(); pen.moveTo(0, 0); pen.lineTo(16, -7); pen.lineTo(150, -9); pen.lineTo(150, 9); pen.lineTo(16, 7); pen.closePath();
  c.fillStyle = SCRAP; c.fill(pen); c.lineWidth = 2.4; c.strokeStyle = INK; c.lineJoin = 'round'; c.stroke(pen);
  c.beginPath(); c.moveTo(16, -7); c.lineTo(16, 7); c.moveTo(40, -8); c.lineTo(40, 8); c.stroke();
  c.save(); const pp = new Path2D(); pp.rect(40, -8, 110, 16); c.clip(pp); c.strokeStyle = RED; c.lineWidth = 1.6; c.beginPath(); for (let i = 30; i < 170; i += 7) { c.moveTo(i, -10); c.lineTo(i + 10, 10); } c.stroke(); c.restore();
  c.strokeStyle = INK; c.lineWidth = 2; c.beginPath(); c.moveTo(100, -9); c.lineTo(96, -18); c.lineTo(150, -18); c.lineTo(150, -9); c.stroke();
  c.fillStyle = RED; c.beginPath(); c.arc(0, 0, 3, 0, TAU); c.fill();
  c.restore();
}
function drawLevel(c, g) {
  const L = LV(), Rn = S.run; if (!Rn) return;
  c.save(); c.beginPath(); c.rect(PAN.x + 1, PAN.y + 1, PAN.w - 2, PAN.h - 2); c.clip(); c.translate(PAN.x, PAN.y); c.scale(PAN.k, PAN.k);
  if (L.water) { drawSnake(c, L.water, Rn.snake); drawWater(c, L.water); }
  if (L.spring && (S.mode === 'edit' || S.mode === 'title')) drawTrajectory(c, L, Rn);
  // подсказка пунктиром
  if (S.hintT > 0 && S.mode === 'edit') { const a = clamp(Math.min(S.hintT, 1), 0, 1) * (.55 + .2 * Math.sin(S.t * 5));
    c.save(); c.setLineDash([8 * WM, 9 * WM]); c.lineDashOffset = -S.t * 30; c.strokeStyle = RED; c.lineWidth = 3 * WM; c.globalAlpha = a; c.lineCap = 'round';
    for (const s of L.sol) { const p = smooth(s, 2); c.beginPath(); p.forEach((q, i) => (i ? c.lineTo(q[0], q[1]) : c.moveTo(q[0], q[1]))); c.stroke(); } c.restore(); }
  const strokes = S.mode === 'edit' || S.mode === 'title' && S.demo && S.demo.ph === 'draw' ? S.strokes : Rn.strokes;
  for (const st of strokes) drawStroke(c, st);
  if (S.cur && S.cur.raw.length > 1) drawStroke(c, { pts: S.cur.raw, seed: 3, side: 1 }, { thin: true });
  Rn.boxes.forEach((b, i) => { if (!b.broken) drawBox(c, b, i); });
  if (L.gate) drawGate(c, L, Rn);
  if (L.button) drawButton(c, L, Rn);
  if (L.spring) drawSpring(c, L, Rn);
  if (L.cat) drawCat(c, L.cat.x, L.cat.y, Rn.cat);
  // звёзды
  L.bonus.forEach((b, i) => { if (!Rn.got[i]) drawStar(c, b[0], b[1] + Math.sin(S.t * 2 + i) * 3, 15, { seed: 40 + i * 9, rot: Math.sin(S.t * 1.3 + i) * .15, hcol: RED }); });
  const won = Rn.res === 'win', sx = L.star[0], sy = L.star[1] + (won ? -Math.min(1, Rn.resT * 2) * 30 : Math.sin(S.t * 1.7) * 3);
  drawStar(c, sx, sy, 30, { face: true, rays: true, seed: 20, rot: won ? Rn.resT * 4 : Math.sin(S.t * .9) * .06 });
  // Каляка
  const k = Rn.k; let look = [0, 0];
  const tgt = S.cur ? S.cur.raw[S.cur.raw.length - 1] : (S.hover && inPanel(S.hover) && S.mode === 'edit' ? toL(S.hover) : null);
  if (tgt) look = [(tgt[0] - (k.x + 8)) / 60, (tgt[1] - (k.y - 65)) / 60];
  else if (k.mode === 'walk') look = [2, .5];
  if (k.y < LH + 120) drawKal(c, k, { look, worry: S.mode === 'edit' && S.bubbles.some((b) => b.who === 'kal' && /выдержит|высоко|кусается|кончились/.test(b.text)) });
  if (k.mode === 'sunk') { const w = L.water, pts = []; for (let x = k.x - 30; x <= k.x + 30; x += 5) pts.push([x, w.surf + Math.sin(x * .3 + S.t * 6) * 3]); c.fillStyle = PAPER; c.fillRect(k.x - 32, w.surf + 2, 64, 30); inkF(c, pts, { w: 2 * WM, smooth: 0, seed: 990 + boil() }); }
  drawPartsL(c);
  c.restore();
}
function drawPartsL(c) {
  for (const p of S.parts) { const a = clamp(p.life / p.max, 0, 1);
    if (p.k === 'crumb') { c.fillStyle = p.col; c.globalAlpha = a * .8; c.beginPath(); c.ellipse(p.x, p.y, 3.5 * WM, 2.2 * WM, p.rot, 0, TAU); c.fill(); }
    else if (p.k === 'spark') { c.strokeStyle = p.col; c.globalAlpha = a; c.lineWidth = 2.2 * WM; c.lineCap = 'round'; c.beginPath(); c.moveTo(p.x, p.y); c.lineTo(p.x - p.vx * .05, p.y - p.vy * .05); c.stroke(); }
    else if (p.k === 'drop') { c.strokeStyle = INK; c.globalAlpha = a; c.lineWidth = 1.6 * WM; c.beginPath(); c.arc(p.x, p.y, 3 * WM, 0, TAU); c.stroke(); }
    else if (p.k === 'bit') { c.save(); c.translate(p.x, p.y); c.rotate(p.rot); c.globalAlpha = a; c.fillStyle = PAPER; c.fillRect(-p.s / 2, -p.s / 2, p.s, p.s * .7); c.strokeStyle = INK; c.lineWidth = 1.8 * WM; c.strokeRect(-p.s / 2, -p.s / 2, p.s, p.s * .7); c.restore(); } }
  c.globalAlpha = 1;
}
/* --- пузыри реплик (в экранных координатах — шрифт одинаково крупный в обеих раскладках) --- */
function anchorOf(who) {
  const Rn = S.run, L = LV(); if (!Rn) return null;
  if (who === 'kal') { const k = Rn.k; return toS(k.x + 14, Math.min(k.y, LH + 10) - (k.mode === 'sunk' ? 60 : 92)); }
  if (who === 'snake' && L.water) { const h = Rn.snake._head || [L.water.sx + 46, L.water.surf - 44]; return toS(h[0] + 18, h[1] - 24); }
  if (who === 'cat' && L.cat) return toS(L.cat.x - 10, L.cat.y - 70);
  return null;
}
function drawBubbles(c) {
  const fs = UI.bubble;
  for (const b of S.bubbles) {
    const an = anchorOf(b.who); if (!an) continue;
    const a = clamp(Math.min(b.t / .15, (b.life - b.t) / .3), 0, 1), pop = b.t < .2 ? A.ease.outBack(b.t / .2) : 1;
    const tw = textW(c, b.text, fs), bw = tw + fs * 1.4, bh = fs * 1.75;
    let bx = an[0] + bw * .2, by = an[1] - bh * .9;
    bx = clamp(bx, bw / 2 + 10, W - bw / 2 - 10); by = clamp(by, bh / 2 + 8, H - bh / 2 - 8);
    c.save(); c.globalAlpha = a; c.translate(an[0], an[1]); c.scale(pop, pop); c.translate(-an[0], -an[1]);
    const pts = []; for (let q = 0; q <= 6.6; q += .07) pts.push([bx + Math.cos(q) * bw / 2 * (1 + Math.sin(q * 5) * .012), by + Math.sin(q) * bh / 2]);
    c.fillStyle = SCRAP; c.fill(pathOf(pts));
    const tx = clamp(an[0], bx - bw * .35, bx + bw * .35);
    c.fillStyle = SCRAP; c.beginPath(); c.moveTo(tx - 10, by + bh / 2 - 6); c.lineTo(an[0], an[1]); c.lineTo(tx + 10, by + bh / 2 - 6); c.fill();
    c.globalAlpha = a;
    inkF(c, pts, { w: 1.9, smooth: 0, seed: b.seed + boil(), jit: 1 });
    inkF(c, [[tx - 9, by + bh / 2 - 3], [an[0], an[1]], [tx + 9, by + bh / 2 - 4]], { w: 1.9, seed: b.seed + 1 + boil(), smooth: 0 });
    hand(c, b.text, bx, by + fs * .35, fs, { align: 'center', wt: 600, col: b.who === 'kal' ? INK : INK2, a: a });
    c.restore();
  }
}
/* --- кнопки и счётчики на листе --- */
function drawBtn(c, id, label, o = {}) {
  const b = UI[id], on = btnOn(id), sd = 1200 + BTNS.indexOf(id) * 17 + boil(3), hov = S.hover && S.hoverMouse && btnAt(S.hover) === id && on;
  c.save(); c.globalAlpha = on ? 1 : .38;
  const rot = ((BTNS.indexOf(id) * 37) % 5 - 2) * .006;
  c.translate(b.x + b.w / 2, b.y + b.h / 2); c.rotate(rot); if (hov) c.scale(1.03, 1.03); c.translate(-b.w / 2, -b.h / 2);
  c.shadowColor = 'rgba(60,50,30,.18)'; c.shadowBlur = 8; c.shadowOffsetY = 3; c.fillStyle = o.active ? '#fbe3e6' : SCRAP; c.fillRect(0, 0, b.w, b.h); c.shadowColor = 'transparent';
  if (o.active) { const p = new Path2D(); p.rect(0, 0, b.w, b.h); hatchF(c, p, [0, 0, b.w, b.h], { gap: 7, ang: .8, w: 1.2, col: RED, a: .35, seed: sd }); }
  inkF(c, [[2, 1], [b.w - 1, 3], [b.w + 1, b.h - 2], [1, b.h], [2, 1]], { w: 2, smooth: 0, seed: sd, jit: 1 });
  if (o.big) {
    hand(c, label, b.w / 2, b.h / 2 + o.size * .34, o.size, { align: 'center', wt: 700, col: o.col || RED, a: 1 });
    const pts = []; for (let q = 0; q <= 6.9; q += .08) pts.push([b.w / 2 + Math.cos(q - .4) * b.w * .44 * (1 + q * .01), b.h / 2 - 4 + Math.sin(q - .4) * b.h * .36 * (1 + q * .012)]);
    inkF(c, pts, { w: 2.4, col: o.col || RED, smooth: 0, seed: sd + 3, jit: 1.6 });
    if (o.sub) hand(c, o.sub, b.w / 2, b.h - 10, LAND ? 20 : 22, { align: 'center', wt: 500, col: MUTED, a: .85 });
  } else hand(c, label, b.w / 2, b.h / 2 + o.size * .34, o.size, { align: 'center', wt: 600, a: 1 });
  c.restore();
}
function drawHUD(c) {
  if (S.mode === 'title' || COVER) return;
  const u = UI, L = LV();
  // чернила
  const [ix, iy, iw, ih] = u.inkBar, sh = S.inkShake > 0 ? Math.sin(S.t * 60) * 4 * S.inkShake : 0, fr = inkLeft() / L.ink;
  c.save(); c.translate(sh, 0);
  c.save(); const ip = new Path2D(); ip.rect(ix, iy, iw * fr, ih); hatchF(c, ip, [ix, iy, iw, ih], { gap: 4, ang: .9, col: RED, w: 1.6, a: .9, seed: 3 }); c.restore();
  inkF(c, [[ix, iy], [ix + iw, iy - 1], [ix + iw + 1, iy + ih], [ix, iy + ih + 1], [ix, iy]], { w: 2, smooth: 0, seed: 1400 });
  inkF(c, [[ix + iw + 1, iy + 6], [ix + iw + 12, iy + 7], [ix + iw + 12, iy + ih - 5], [ix + iw + 1, iy + ih - 6]], { w: 2, smooth: 0, seed: 1401 });
  c.restore();
  // звёзды страницы: большая — дойти; две маленькие — бонусы этого прохода
  const got = S.run ? S.run.got : [], won = S.mode === 'win' || S.mode === 'next' || (S.res[S.li] && S.mode !== 'edit');
  u.stars.forEach(([x, y], i) => { const on = i === 0 ? won : got[i - 1];
    const pts = starPts(x, y, u.starR, u.starR * .43);
    if (on) { const p = pathOf(pts); c.fillStyle = '#fff3cf'; c.fill(p); hatchF(c, p, [x - u.starR, y - u.starR, u.starR * 2, u.starR * 2], { gap: 4, ang: .7, w: 1.3, col: i ? RED : INK, a: .85, seed: i }); }
    inkF(c, pts, { w: 2.2, smooth: 0, seed: 1500 + i * 3 + (on ? boil(4) : 0) }); });
  // кнопки
  const running = S.mode === 'run' || S.mode === 'fail';
  drawBtn(c, 'go', running ? 'Заново' : 'Иди!', { big: true, size: running ? u.goF * .7 : u.goF, col: running ? INK : RED, sub: running ? (LAND ? 'пробел — заново' : '') : (LAND ? 'пробел' : '') });
  drawBtn(c, 'erase', 'ластик', { size: u.btnF, active: S.eraser });
  drawBtn(c, 'undo', 'назад', { size: u.btnF });
  drawBtn(c, 'clear', 'очистить', { size: u.btnF });
  drawBtn(c, 'hint', 'подсказка', { size: u.btnF, active: S.fails >= 2 && S.mode === 'edit' && Math.sin(S.t * 4) > 0 });
  if (!LAND) { // строка-подсказка под кадром
    const tx = L.hint; c.save(); c.font = `italic 500 ${u.sub[2]}px ${HANDF}`; const words = tx.split(' '), lines = []; let line = '';
    for (const wd of words) { const tt = line ? line + ' ' + wd : wd; if (c.measureText(tt).width > 640 && line) { lines.push(line); line = wd; } else line = tt; } lines.push(line);
    lines.forEach((l, i) => hand(c, l, u.sub[0], u.sub[1] + i * (u.sub[2] + 8) - (lines.length - 1) * 10, u.sub[2], { align: 'center', wt: 500, col: MUTED, a: 1 })); c.restore();
  }
}
function drawStamp(c) {
  const s = S.stamp; if (!s || s.t < .5) return;
  const k = clamp((s.t - .5) / .25, 0, 1), sc = 1 + (1 - A.ease.outBack(k)) * 1.5, x = PAN.x + PAN.w * .5, y = PAN.y + (LAND ? 104 : 86);
  c.save(); c.translate(x, y); c.rotate(-.14); c.scale(sc, sc); c.globalAlpha = k;
  hand(c, s.grade, 0, 44, LAND ? 120 : 104, { align: 'center', wt: 700, col: RED, a: 1 });
  inkF(c, ovalPts(2, 4, 62, 66, { over: .5, seed: 9, da: .1 }), { w: 3, col: RED, smooth: 0, seed: 77, jit: 1.6 });
  hand(c, s.word, 0, LAND ? 104 : 96, LAND ? 32 : 30, { align: 'center', wt: 700, col: RED, a: 1, rot: .04 });
  c.restore();
}
function drawFlip(c, g) {
  const f = S.flip; if (!f) return;
  const t = f.t < 1 ? A.ease.inOutSine(f.t) : 1 - A.ease.inOutSine(f.t - 1), edge = W * (1 - t);
  if (t <= 0) return;
  // новый чистый лист наезжает справа (в первой половине), во второй — уезжает влево, открывая следующую страницу
  const x0 = f.t < 1 ? edge : 0, x1 = f.t < 1 ? W : W * t;
  c.save(); c.beginPath(); c.rect(x0, 0, x1 - x0, H); c.clip();
  c.fillStyle = PAPER; c.fillRect(x0, 0, x1 - x0, H); c.strokeStyle = '#9fb6dd'; c.globalAlpha = .5; c.lineWidth = 1; c.beginPath();
  for (let y = 14; y < H; y += 30) { c.moveTo(x0, y + .5); c.lineTo(x1, y + .5); } for (let x = (LAND ? 104 : 22); x < W; x += 30) if (x > x0 && x < x1) { c.moveTo(x + .5, 0); c.lineTo(x + .5, H); } c.stroke(); c.globalAlpha = 1;
  hand(c, f.t < 1 ? 'стр. ' + (S.li + 2) : '', (x0 + x1) / 2, H / 2, LAND ? 60 : 70, { align: 'center', wt: 700, a: .7 });
  c.restore();
  const ex = f.t < 1 ? x0 : x1, gr = c.createLinearGradient(ex - 30, 0, ex + 30, 0);
  gr.addColorStop(0, 'rgba(60,50,30,0)'); gr.addColorStop(.5, 'rgba(60,50,30,.22)'); gr.addColorStop(1, 'rgba(60,50,30,0)'); c.fillStyle = gr; c.fillRect(ex - 30, 0, 60, H);
}
function draw(c, g) {
  c.drawImage(layer(g), 0, 0, W, H);
  drawLevel(c, g);
  drawHUD(c);
  if (COVER) logo(c, 420, 140, .92, -.02);
  else if (S.mode === 'title') logo(c, LAND ? 150 : 36, LAND ? 22 : 46, LAND ? 1 : 1.18);
  if (S.mode === 'title' && !LAND) titleScene(c);
  drawBubbles(c);
  drawStamp(c);
  // курсор-ручка
  if (S.hoverMouse && S.hover && inPanel(S.hover) && S.mode === 'edit' && !S.flip) drawPen(c, S.hover[0], S.hover[1], S.eraser);
  if (S.mode === 'title' && S.demo && S.cur && S.cur.raw.length) { const p = S.cur.raw[S.cur.raw.length - 1], q = toS(p[0], p[1]); drawPen(c, q[0], q[1], false); }
  drawFlip(c, g);
}

/* книжная заставка: под карточкой меню — маленькая сценка (Каляка машет, мостик к звезде) */
let TS = null;
function titleScene(c) {
  if (!TS) TS = mkStroke([[214, 196], [330, 148], [452, 192]]);
  c.save(); c.translate(0, 1010); c.scale(1.08, 1.08);
  const gp = new Path2D(); gp.rect(30, 198, 180, 60); gp.rect(462, 196, 210, 60);
  hatchF(c, gp, [30, 196, 640, 60], { gap: 8, ang: -.95, w: 1.2, a: .6, seed: 2 });
  inkF(c, [[30, 198], [120, 196], [212, 199]], { w: 2.6, seed: 61, smooth: 0 }); inkF(c, [[462, 196], [560, 198], [672, 195]], { w: 2.6, seed: 62, smooth: 0 });
  inkF(c, [[212, 199], [214, 260]], { w: 2.2, seed: 63, smooth: 0 }); inkF(c, [[462, 196], [460, 260]], { w: 2.2, seed: 64, smooth: 0 });
  drawStroke(c, TS);
  drawStar(c, 590, 140, 30, { face: true, rays: true, seed: 20, rot: Math.sin(S.t * .9) * .06 });
  drawKal(c, { x: 120, y: 198, mode: 'happy', ph: 0, landT: 9, vy: 0 }, { look: [2, -1] });
  c.restore();
}

/* ---------------- обложка (?cover) ---------------- */
function coverSetup() {
  S.mode = 'cover'; S.li = 6; const L = LEVELS[6];
  S.strokes = L.sol.map((s) => mkStroke(s)); S.run = makeRun(L, S.strokes);
  S.run.k.x = 420; S.run.k.y = 352; S.run.k.mode = 'walk'; S.run.k.ph = 1.2; S.run.got[0] = false;
  S.bubbles = [{ who: 'kal', text: 'а он выдержит?..', t: 1, life: 1e9, seed: 4 }, { who: 'snake', text: 'ням?', t: 1, life: 1e9, seed: 8 }];
}

A.game({
  // touchDpr: тысячи штрихов за кадр — на телефоне плотность точек не больше 1,5 (25.10)
  id: 'doodle', title: 'Каляка', width: W, height: H, touchDpr: 1.5, orientation: LAND ? 'landscape' : 'portrait', tone: 'light', music: 'garden',
  keys: { KeyZ: 'undo', Backspace: 'undo', KeyR: 'restart', KeyE: 'erase', KeyH: 'hint', Slash: 'hint', KeyX: 'none', KeyJ: 'none', KeyK: 'none', KeyL: 'none', ShiftLeft: 'none', KeyA: 'none', KeyD: 'none', KeyW: 'none', KeyS: 'none' },
  help: { desktop: 'Рисуйте мышью · правая кнопка — стереть · <kbd>Пробел</kbd> — «Иди!» · <kbd>Z</kbd> — назад · <kbd>H</kbd> — подсказка', short: 'Мышь — рисовать · правая кнопка — стереть · пробел — «Иди!»', touch: 'Рисуйте пальцем · «ластик» — стереть · «Иди!» — в путь' },
  init(g) {
    GAME = g; attachInput(g);
    const ready = () => { S.fontsOK = true; };
    if (document.fonts && document.fonts.load) Promise.all([document.fonts.load('italic 600 30px Lora', 'Каляка ням'), document.fonts.load('900 54px Unbounded', 'Каляка')]).then(ready, ready); else ready();
    window.__doodle = () => S;
    Object.assign(S, { LEVELS, sim, PAN, UI, LAND, toS, W, H, api: { loadPage, go, press, startGame } });
    if (COVER) { coverSetup(); g.setPlaying(false); return; }
    titleScreen(g);
  },
  update(g, dt) { if (S.mode === 'cover') { S.t += dt; animRun(S.run, dt); S.run.ev.length = 0; return; } update(g, dt); },
  draw
});
})();
