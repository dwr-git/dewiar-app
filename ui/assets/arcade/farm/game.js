/* «Хутор Одуванчик» — уютная пиксельная мини-RPG (24.10; концепт владелец утвердил: «очень нравится… как же красиво
   будет. Делай»). Малыш Тиша в оранжевой вязаной шапке и с корзинкой помогает соседям хутора до заката: у кого над
   головой пузырь — тому нужна помощь. Три дня по три поручения, монетки и сердечки за помощь, маленькие сюрпризы
   (письмо в ящике, тыква-великан, новый гость), вечером третьего дня — праздник урожая.
   Мир — пиксельная сетка 320×180 (широкое окно) или 180×320 (телефон), ×4: земля рисуется один раз в свой холст,
   живое — каждый кадр в маленький холст мира, который растягивается без сглаживания. Пузыри, значки и надписи —
   поверх, крупно. Управление: WASD/стрелки — идти, E/Enter/пробел — говорить и брать; щелчок или касание по месту —
   Тиша идёт сам (поиск пути), по соседу или предмету — подходит и делает; долгое касание — ведёт за пальцем. */
(() => {
'use strict';
const A = Arcade, SND = A.sound;
const LAND = (() => { try { return innerWidth > (innerHeight - 110) * 1.15; } catch (e) { return false; } })();
const W = LAND ? 1280 : 720, H = LAND ? 720 : 1280, PX = 4, WW = W / PX, WH = H / PX, BS = 5, TAU = Math.PI * 2;
const DAY_LEN = 150;                              // секунд от 8:00 до 20:00
const clamp = (v, a, b) => (v < a ? a : v > b ? b : v), lerp = (a, b, t) => a + (b - a) * t;
const dist = (ax, ay, bx, by) => Math.hypot(ax - bx, ay - by);
function rng(seed) { return () => { seed = (seed + 0x6D2B79F5) | 0; let t = Math.imul(seed ^ (seed >>> 15), 1 | seed); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
const mk = (w, h) => { const c = document.createElement('canvas'); c.width = Math.max(1, w); c.height = Math.max(1, h); return c; };
const FONT = A.FONT;

const C = {
  ol: '#3a2a3c', ol2: '#4b3346',
  g0: '#a6d86f', g1: '#86c45f', g2: '#68a854', g3: '#4d8a4c', g4: '#356b45', g5: '#24503d',
  d0: '#f3d9a2', d1: '#e2bd80', d2: '#c99863', d3: '#a5744c',
  s0: '#8f5f42', s1: '#744a35', s2: '#5a3829',
  w0: '#9fe0ee', w1: '#6cc2e0', w2: '#4a9bd0', w3: '#3a74b4', w4: '#2f5596',
  wd0: '#d99a5b', wd1: '#b4743f', wd2: '#86512f',
  r0: '#f0806a', r1: '#d65a55', r2: '#a8404c', r3: '#7c2f45',
  wl0: '#fbf1d8', wl1: '#ecd6a8', wl2: '#cdb084',
  st0: '#cfc8d6', st1: '#a59db4', st2: '#7c7590',
  sk: '#f8cfa6', sk2: '#e8a882', ck: '#ff9a94',
  hat: '#f28b3b', hat2: '#cf6430', cream: '#fff4dc',
  coat: '#ffd35c', coat2: '#e9a93b', teal: '#43b8a8', teal2: '#2c8a87',
  pk: '#ff9fc0', pk2: '#e66f9c', yl: '#ffe066', wh: '#fffaf0', lav: '#b9a2f0',
  car: '#ff9a3c', cab: '#b8e27a', cab2: '#86c45f', pum: '#ff9b3d', pum2: '#d96a2a',
  win: '#ffe7a0', win2: '#ffc960', paper: '#fff6e2', slot: '#efe0bf', ink: '#3a2a3c', muted: '#86677a'
};

/* ---------------- пиксельные спрайты ---------------- */
class Spr {
  constructor(w, h) { this.w = w; this.h = h; this.a = new Array(w * h).fill(null); }
  p(x, y, c) { x = Math.floor(x); y = Math.floor(y); if (x >= 0 && y >= 0 && x < this.w && y < this.h) this.a[y * this.w + x] = c; return this; }
  g(x, y) { if (x < 0 || y < 0 || x >= this.w || y >= this.h) return null; return this.a[y * this.w + x]; }
  r(x, y, w, h, c) { for (let j = 0; j < h; j++) for (let i = 0; i < w; i++) this.p(x + i, y + j, c); return this; }
  e(cx, cy, rx, ry, c, f) { for (let y = Math.floor(cy - ry - 1); y <= cy + ry + 1; y++) for (let x = Math.floor(cx - rx - 1); x <= cx + rx + 1; x++) { const dx = (x + .5 - cx) / rx, dy = (y + .5 - cy) / ry; if (dx * dx + dy * dy <= 1 && (!f || f(x, y))) this.p(x, y, c); } return this; }
  te(cx, cy, rx, ry, c) { for (let y = Math.floor(cy - ry - 1); y <= cy + ry + 1; y++) for (let x = Math.floor(cx - rx - 1); x <= cx + rx + 1; x++) { const dx = (x + .5 - cx) / rx, dy = (y + .5 - cy) / ry; if (dx * dx + dy * dy <= 1 && this.g(x, y) && this.g(x, y) !== C.ol) this.p(x, y, c); } return this; }
  tri(pts, c) { const [x0, y0] = pts[0], [x1, y1] = pts[1], [x2, y2] = pts[2]; const s = (ax, ay, bx, by, px, py) => (bx - ax) * (py - ay) - (by - ay) * (px - ax);
    for (let y = Math.floor(Math.min(y0, y1, y2)); y <= Math.max(y0, y1, y2); y++) for (let x = Math.floor(Math.min(x0, x1, x2)); x <= Math.max(x0, x1, x2); x++) { const px = x + .5, py = y + .5, a = s(x0, y0, x1, y1, px, py), b = s(x1, y1, x2, y2, px, py), d = s(x2, y2, x0, y0, px, py); if ((a >= 0 && b >= 0 && d >= 0) || (a <= 0 && b <= 0 && d <= 0)) this.p(x, y, c); } return this; }
  outline(c = C.ol) { const b = this.a.slice(); for (let y = 0; y < this.h; y++) for (let x = 0; x < this.w; x++) { if (b[y * this.w + x]) continue; for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) { const X = x + dx, Y = y + dy; if (X >= 0 && Y >= 0 && X < this.w && Y < this.h && b[Y * this.w + X]) { this.a[y * this.w + x] = c; break; } } } return this; }
  get cv() { if (!this._c) { const c = mk(this.w, this.h), x = c.getContext('2d'); for (let j = 0; j < this.h; j++) for (let i = 0; i < this.w; i++) { const v = this.a[j * this.w + i]; if (v) { x.fillStyle = v; x.fillRect(i, j, 1, 1); } } this._c = c; } return this._c; }
}
function pix(rows, map, ol = C.ol) {             // рисунок строками, с полем в 1 точку под обводку
  const s = new Spr(rows[0].length + 2, rows.length + 2);
  rows.forEach((r, j) => [...r].forEach((ch, i) => { if (map[ch]) s.p(i + 1, j + 1, map[ch]); }));
  if (ol) s.outline(ol);
  return s;
}

function heroSpr(back, step, blink) {
  const s = new Spr(20, 24), l1 = step === 1 ? 1 : 0, l2 = step === 2 ? 1 : 0;
  s.r(7, 18 - l1, 2, 3, '#5c4c86').r(11, 18 - l2, 2, 3, '#5c4c86');
  s.r(6, 21 - l1, 3, 2, C.wd2).r(11, 21 - l2, 3, 2, C.wd2);
  s.e(10, 16, 5, 4.2, C.coat).te(10, 18.6, 4.6, 1.4, C.coat2).r(10, 13, 1, 8, C.coat2);
  if (!back) s.p(9, 15, C.wh).p(9, 17, C.wh);
  s.r(4, 14, 2, 4, C.coat).p(4, 18, C.sk).p(5, 18, C.sk);
  s.r(14, 14, 2, 4, C.coat).p(14, 18, C.sk).p(15, 18, C.sk);
  if (back) s.e(10, 8.6, 6, 5.4, '#a8673d').te(10, 12.4, 5, 1.4, '#86512f');
  else s.e(10, 8.6, 6, 5.4, C.sk).te(10, 12.6, 5, 1.3, C.sk2);
  s.e(10, 6.4, 6.6, 4.6, C.hat, (x, y) => y < 7);
  for (let x = 4; x < 17; x += 2) s.p(x, 4, C.hat2);
  for (let x = 5; x < 17; x += 2) s.p(x, 2, C.hat2);
  s.r(3, 6, 14, 2, C.hat2).r(3, 6, 14, 1, '#e5773a');
  s.e(10, 1.2, 2.2, 1.8, C.cream);
  if (!back) {
    if (blink) s.r(7, 10, 1, 1, C.ol).r(12, 10, 1, 1, C.ol); else s.r(7, 9, 1, 2, C.ol).r(12, 9, 1, 2, C.ol);
    s.r(5, 11, 2, 1, C.ck).r(13, 11, 2, 1, C.ck).r(9, 12, 2, 1, '#c66a62');
  }
  s.r(4, 12, 12, 2, C.teal).r(4, 13, 12, 1, C.teal2);
  if (!back) s.r(13, 13, 2, 4, C.teal).p(14, 16, C.teal2); else s.r(5, 13, 2, 4, C.teal).p(5, 16, C.teal2);
  return s.outline();
}
function basketSpr(full) {
  const s = new Spr(10, 9);
  s.e(5, 3, 4, 3.2, C.wd1, (x, y) => y < 3); s.e(5, 3.2, 2.6, 2.2, null, (x, y) => y < 3);
  s.p(1, 3, C.wd1).p(9, 3, C.wd1).r(1, 3, 9, 5, C.wd0).r(1, 5, 9, 1, C.wd1).r(2, 4, 1, 1, C.wd1).r(6, 4, 1, 1, C.wd1);
  if (full) s.e(3.5, 3, 1.6, 1.3, C.car).e(7, 2.8, 1.6, 1.3, C.r1).p(4, 1, C.g1).p(7, 1, C.g2);
  return s.outline();
}
function moleSpr() {
  const m = new Spr(18, 22);
  m.e(9, 14, 7, 6.5, '#7d6a78').te(9, 17.5, 6.5, 2.4, '#69586a');
  m.e(9, 15.5, 4.5, 4.5, '#f2e3c4').r(5, 14, 8, 1, '#d0b896');
  m.e(9, 8, 6, 5.3, '#8a7686').te(9, 6, 4.8, 3, '#9b8796');
  m.e(9, 6.4, 6.6, 4.8, C.r1, (x, y) => y < 7).p(6, 3, C.wh).p(11, 3, C.wh).p(13, 5, C.wh).p(8, 5, C.wh).p(4, 6, C.wh);
  m.r(13, 6, 3, 2, C.r1).p(16, 8, C.r1).p(15, 9, C.r1);
  m.e(9, 10.4, 1.8, 1.3, C.pk).p(9, 10, C.wh);
  for (const ex of [6, 12]) m.p(ex - 1, 8, '#e8c25a').p(ex + 1, 8, '#e8c25a').p(ex, 7, '#e8c25a').p(ex, 9, '#e8c25a').p(ex, 8, C.ol);
  m.p(8, 8, '#e8c25a').p(10, 8, '#e8c25a').p(9, 8, '#e8c25a').p(4, 13, '#f2b6c8').p(14, 13, '#f2b6c8');
  m.r(2, 15, 3, 2, '#ead7cc').r(13, 15, 3, 2, '#ead7cc').r(5, 20, 3, 2, '#69586a').r(10, 20, 3, 2, '#69586a');
  return m.outline();
}
function sheepSpr(bell, wreath, blink) {
  const s = new Spr(24, 18), face = '#5b4f63';
  for (const [x, y, r] of [[7, 8, 4.5], [12, 6, 5], [17, 8, 4.5], [9, 11, 4.5], [15, 11, 4.5], [12, 10, 5]]) s.e(x, y, r, r * .9, C.wh);
  s.te(12, 13, 8, 2.2, '#e7e0ee').r(7, 14, 2, 4, face).r(15, 14, 2, 4, face);
  s.e(4, 9, 3.6, 3.4, face);
  if (blink) s.p(2, 9, C.ol).p(5, 9, C.ol); else s.p(2, 9, C.wh).p(2, 8, C.ol).p(3, 9, C.ol).p(5, 9, C.wh).p(5, 8, C.ol);
  s.e(4.5, 6, 2.2, 1.6, C.wh).p(1, 7, '#cfc3e0').p(8, 7, '#cfc3e0').p(4, 11, C.ck);
  if (wreath) s.p(2, 5, C.pk).p(3, 4, C.g2).p(4, 4, C.yl).p(5, 4, C.g2).p(6, 4, C.pk2).p(7, 5, C.yl).p(1, 6, C.g2).p(8, 6, C.g2);
  s.outline();
  if (bell) s.p(5, 13, C.yl).p(6, 13, C.yl).p(5, 14, '#d9a92c').p(6, 14, '#d9a92c').p(5, 12, '#8a5a20');
  return s;
}
function frogSpr(blink) {
  const f = new Spr(16, 14), gr = '#7fcf6a', gr2 = '#62b05a';
  f.e(8, 9, 6, 4.5, gr).e(5, 4, 2.6, 2.6, gr).e(11, 4, 2.6, 2.6, gr).te(8, 11, 5.5, 2, gr2);
  if (blink) f.r(4, 4, 3, 1, C.ol).r(10, 4, 3, 1, C.ol); else f.e(5, 4, 1.6, 1.6, C.wh).e(11, 4, 1.6, 1.6, C.wh).p(5, 4, C.ol).p(11, 4, C.ol);
  f.r(6, 9, 5, 1, C.ol2).p(3, 8, C.ck).p(13, 8, C.ck).r(2, 12, 4, 2, gr2).r(10, 12, 4, 2, gr2);
  f.e(8, 1.3, 3.5, 1.3, '#e8c25a');
  return f.outline();
}
function henSpr(ryaba, peck) {
  const s = new Spr(10, 10), b = ryaba ? '#f6e8d2' : C.wh;
  s.e(5, 6, 4, 3, b);
  if (!peck) s.e(7, 3, 2.2, 2.2, b).p(7, 0, C.r1).p(8, 1, C.r1).r(9, 3, 1, 1, C.car).p(7, 3, C.ol);
  else s.e(7.4, 5.6, 2.1, 2, b).p(7, 3, C.r1).p(8, 3, C.r1).r(9, 6, 1, 1, C.car).p(8, 5, C.ol);
  s.te(4, 7.5, 3, 1.2, '#e9e1d6').r(4, 9, 1, 1, C.car).r(6, 9, 1, 1, C.car).p(1, 4, b);
  if (ryaba) s.p(3, 5, '#a87c5a').p(5, 7, '#a87c5a').p(2, 7, '#a87c5a').p(6, 5, '#a87c5a').p(4, 6, '#c99a6e');
  return s.outline();
}
function chickSpr(step) {
  const s = new Spr(7, 7);
  s.e(3.5, 4, 3, 2.5, '#ffe066').e(4.6, 2.2, 1.8, 1.8, '#ffe066').p(6, 2, C.car).p(5, 2, C.ol).p(2, 4, '#f2c94c').p(3, 4, '#f2c94c');
  s.p(step ? 3 : 2, 6, C.car).p(step ? 4 : 5, 6, C.car);
  return s.outline('#a8792a');
}
function catSleepSpr() {
  const s = new Spr(16, 10);
  s.e(8, 6, 6, 3.5, C.car).te(8, 8, 5.5, 1.6, '#e07d2a').tri([[3, 4], [4, 0], [7, 3]], C.car).tri([[9, 3], [12, 0], [13, 4]], C.car);
  s.r(5, 5, 2, 1, C.ol).r(10, 5, 2, 1, C.ol).p(8, 6, C.pk2).r(13, 7, 3, 2, C.car);
  return s.outline();
}
function catSitSpr(closed) {
  const s = new Spr(15, 15), o = C.car, d = '#e07d2a';
  s.e(6.5, 11, 4.6, 3.6, o).e(6.5, 5.6, 4.4, 3.6, o);
  s.tri([[2, 3.6], [2.6, 0], [5.4, 2.6]], o).tri([[7.6, 2.6], [10.4, 0], [11, 3.6]], o).p(3, 1, C.pk).p(10, 1, C.pk);
  s.te(6.5, 13.4, 4.4, 1.3, d).e(6.5, 10.6, 2, 2.3, C.cream).p(6, 2, d).p(7, 2, d).p(6, 3, d);
  if (closed) s.r(3, 6, 2, 1, C.ol).r(8, 6, 2, 1, C.ol); else s.r(4, 5, 1, 2, C.ol).r(9, 5, 1, 2, C.ol);
  s.p(6, 7, C.pk2).p(7, 7, C.pk2).p(2, 8, C.ck).p(11, 8, C.ck).r(4, 14, 2, 1, C.cream).r(8, 14, 2, 1, C.cream);
  s.r(11, 12, 3, 1, o).r(13, 9, 1, 3, o).p(13, 9, d);
  return s.outline();
}
function hedgeSpr(apple, blink) {
  const s = new Spr(19, 14), b = '#8d6a55', b2 = '#6b4c3c';
  s.e(10.5, 8, 7.2, 4.8, b);
  for (let i = 0; i <= 12; i++) { const a = Math.PI + i / 12 * Math.PI * .95, x = 10.5 + Math.cos(a) * 8.2, y = 8 + Math.sin(a) * 5.8; if (i % 2 === 0) s.p(x, y, b2); }
  for (let y = 4; y < 12; y++) for (let x = 5; x < 18; x++) if (s.g(x, y) === b && (x * 2 + y * 3) % 5 === 0) s.p(x, y, b2);
  s.e(4.5, 9, 3.6, 3, '#f2d9b5').p(1, 9, C.ol).p(2, 9, '#e0bfa0').p(5, 10, C.ck);
  if (blink) s.r(3, 8, 2, 1, C.ol); else s.p(4, 8, C.ol).p(4, 7, C.ol);
  s.r(6, 12, 2, 1, b2).r(13, 12, 2, 1, b2);
  if (apple) s.e(11, 2.6, 2.2, 2, C.r1).p(10, 2, C.r0).p(11, 0, C.g2);
  return s.outline();
}
function duckSpr() {
  const s = new Spr(14, 11);
  s.e(6, 7, 5.5, 3.2, C.wh).e(10, 3.5, 2.6, 2.6, C.wh).r(12, 3, 2, 1, C.car).p(13, 4, C.car).p(10, 3, C.ol).te(5, 9, 5, 1.4, '#dfe7ee').p(2, 5, C.wh).p(1, 4, C.wh);
  return s.outline();
}
function scareSpr() {
  const s = new Spr(14, 26);
  s.r(6, 10, 2, 16, C.wd1).r(1, 12, 12, 2, C.wd1);
  for (let a = 0; a < 12; a++) s.e(7 + Math.cos(a / 12 * TAU) * 3.6, 6 + Math.sin(a / 12 * TAU) * 3.6, 1.8, 1.8, C.yl);
  s.e(7, 6, 3, 3, C.wd2).e(7, 6, 2, 2, C.wd1).p(6, 5, C.ol).p(8, 5, C.ol).p(6, 7, C.ol).p(7, 8, C.ol).p(8, 7, C.ol);
  s.e(4, 18, 2.4, 1.2, C.g2).e(10, 20, 2.4, 1.2, C.g2);
  return s.outline();
}
function mailSpr(flag) {
  const s = new Spr(11, 16);
  s.r(4, 6, 2, 10, C.wd1).r(1, 1, 8, 6, C.r1).e(5, 2, 4, 2, C.r1).r(1, 5, 8, 1, C.r2).r(2, 3, 5, 1, C.r2);
  if (flag) s.r(8, 0, 1, 4, C.wd2).r(8, 0, 3, 2, C.yl); else s.r(8, 4, 3, 1, C.wd2).r(9, 3, 2, 1, C.yl);
  return s.outline();
}
function canSpr(full) {
  return pix([
    '..kkk....',
    '.k...k...',
    'bbbbbbb..',
    'bBBBBBb.b',
    full ? 'bWBBBBbbb' : 'bBBBBBbbb',
    'bBBBBBb..',
    'bbbbbbb..',
  ], { k: C.st2, b: C.w2, B: C.w3, W: C.w0 });
}
function treeSpr(r, kind) {
  const w = Math.ceil(r * 2 + 6), h = Math.ceil(r * 2 + 14), s = new Spr(w, h), cx = w / 2;
  s.r(cx - 2, r * 1.6, 4, h - r * 1.6 - 1, C.wd1).r(cx - 2, r * 1.6, 1, h - r * 1.6 - 1, C.wd2);
  const c1 = kind ? '#5fa35a' : C.g3, c0 = kind ? '#8cc865' : C.g2;
  s.e(cx, r + 2, r, r * .9, c1).e(cx - r * .55, r * 1.25, r * .55, r * .5, c1).e(cx + r * .55, r * 1.25, r * .55, r * .5, c1);
  s.te(cx - r * .2, r * .95, r * .75, r * .62, c0).te(cx - r * .4, r * .6, r * .35, r * .28, kind ? '#b4e07a' : C.g1);
  return s.outline(C.g5);
}
function houseSpr() {
  const s = new Spr(84, 72), top = 6;
  s.r(10, 36, 64, 30, C.wl0); for (let j = 0; j < 5; j++) s.r(10, 40 + j * 6, 64, 1, C.wl1); s.r(10, 36, 64, 3, C.wl2);
  s.r(10, 36, 3, 30, C.wd1).r(71, 36, 3, 30, C.wd1).r(10, 64, 64, 4, C.st1); for (let i = 0; i < 8; i++) s.r(12 + i * 8, 64, 6, 2, C.st0);
  s.tri([[42, top], [0, 40], [84, 40]], C.r1);
  for (let row = 0; row < 8; row++) { const y = Math.round(top + 6 + row * 4.2); for (let x = 0; x < 84; x++) { if (s.g(x, y) === C.r1) { s.p(x, y, C.r2); if ((x + row * 3) % 6 === 0) s.p(x, y + 1, C.r2).p(x, y + 2, C.r2); } } }
  s.tri([[42, top + 3], [30, 22], [54, 22]], C.r0).r(0, 38, 84, 3, C.r3);
  s.e(42, 26, 5, 5, C.wd1).e(42, 26, 3.6, 3.6, C.win).r(42, 22, 1, 8, C.wd1).r(38, 26, 8, 1, C.wd1).p(40, 24, C.wh);
  s.r(58, 6, 9, 14, C.st1).r(57, 4, 11, 3, C.st2).r(59, 8, 2, 10, C.st0);
  s.r(35, 46, 14, 20, C.wd1).e(42, 47, 7, 5, C.wd1, (x, y) => y < 47).r(38, 46, 1, 20, C.wd2).r(42, 44, 1, 22, C.wd2).r(45, 46, 1, 20, C.wd2).p(46, 56, C.yl).p(46, 57, C.wd2);
  s.r(33, 65, 18, 2, C.st0);
  for (const wx of [16, 56]) {
    s.r(wx, 44, 13, 12, C.wd2).r(wx + 1, 45, 11, 10, C.win).r(wx + 1, 45, 11, 4, C.win2).r(wx + 6, 45, 1, 10, C.wd2).r(wx + 1, 49, 11, 1, C.wd2).p(wx + 2, 46, C.wh).p(wx + 3, 46, C.wh).p(wx + 2, 47, C.wh);
    s.r(wx - 1, 56, 15, 3, C.wd0).r(wx - 1, 58, 15, 1, C.wd2); for (let i = 0; i < 5; i++) { s.e(wx + 1 + i * 3, 55, 1.4, 1.4, i % 2 ? C.yl : C.pk); s.p(wx + 1 + i * 3, 56, C.g2); }
  }
  return s.outline();
}
function tableSpr() {
  const s = new Spr(26, 16);
  s.r(1, 7, 24, 3, '#fff1f4'); for (let i = 1; i < 25; i += 2) s.p(i, 8, C.pk); s.r(1, 10, 24, 1, '#e8c9d0');
  s.r(3, 11, 2, 5, C.wd1).r(21, 11, 2, 5, C.wd1);
  s.e(13, 5.5, 6, 2.6, '#f2b25a').te(13, 4.4, 5, 1.4, '#ffd07a').p(10, 4, C.wd1).p(13, 3, C.wd1).p(16, 4, C.wd1).p(12, 5, C.wd1);
  s.e(4.5, 5.5, 2, 1.8, '#d6e9f5').p(4, 4, C.r1).e(21, 5.4, 2.2, 2, C.car).p(21, 3, C.g2);
  return s.outline();
}
function carrotSpr(ripe) {
  const s = new Spr(7, 8);
  s.p(3, 0, C.g2).p(2, 1, C.g1).p(4, 1, C.g1).p(1, 2, C.g2).p(3, 2, C.g1).p(5, 2, C.g2).r(2, 3, 3, 1, C.g1);
  if (ripe) s.r(2, 4, 3, 2, C.car).p(3, 6, C.car).p(2, 4, '#ffc07a');
  return s.outline(C.g5);
}
function cabbageSpr() { const s = new Spr(10, 8); s.e(5, 4.2, 4, 3.3, C.cab2).e(5, 3.6, 2.8, 2.3, C.cab).p(5, 2, C.wh).r(2, 4, 1, 2, C.g2).r(7, 4, 1, 2, C.g2); return s.outline(C.g4); }
function pumpkinSpr(big) {
  const k = big ? 1.55 : 1, w = Math.round(12 * k), h = Math.round(10 * k), s = new Spr(w, h);
  s.e(w / 2, h * .56, 5 * k, 3.6 * k, C.pum).te(w / 2, h * .75, 4.5 * k, 1.6 * k, C.pum2).r(Math.round(3 * k), Math.round(3 * k), 1, Math.round(6 * k), C.pum2).r(w - 1 - Math.round(3 * k), Math.round(3 * k), 1, Math.round(6 * k), C.pum2);
  s.r(w / 2 - 1, 0, 2, Math.round(3 * k), C.g3).p(w / 2 + 1, 1, C.g2).p(w / 2 + 2, 1, C.g2).p(Math.round(4 * k), Math.round(4 * k), C.yl);
  if (big) s.p(Math.round(4 * k) + 1, Math.round(4 * k), C.yl).p(Math.round(4 * k), Math.round(4 * k) + 1, '#ffd07a');
  return s.outline(C.r3);
}
function peaSpr() { const s = new Spr(7, 8); s.r(3, 3, 1, 5, C.g3).e(2, 3, 1.6, 1.3, C.g1).e(5, 2.4, 1.6, 1.3, C.g1).e(3.5, 5, 1.6, 1.2, C.g2).p(1, 1, C.pk).p(5, 0, C.wh).p(6, 4, C.pk); return s.outline(C.g4); }

/* значки — и в пузырях, и в корзинке, и в списке поручений */
const ICON = {};
function buildIcons() {
  ICON.carrot = pix(['..g.g..', '...g...', '..ggg..', '..ooo..', '..oOo..', '...o...', '...o...'], { g: C.g2, o: C.car, O: '#ffc07a' }, C.g5);
  ICON.bell = pix(['...k...', '..yyy..', '.yWyyy.', '.yyyyy.', 'yyyyyyy', 'ddddddd', '...d...'], { k: '#8a5a20', y: C.yl, W: C.wh, d: '#d9a92c' }, '#8a5a20');
  ICON.hook = pix(['..rr..', '..ww..', '...k..', '...k..', 'k..k..', 'kk.k..', '.kkk..'], { r: C.r1, w: C.wh, k: '#8d8aa6' });
  ICON.fish = pix(['...bbb...b', '.bbbbbbbbb', 'bkbbbbbbb.', '.BBBBBBBbb', '...BBB...b'], { b: '#9cc4e4', B: '#6f9cc8', k: C.ol }, '#2f5596');
  ICON.apple = pix(['..kg..', '.rrrr.', 'rWrrrr', 'rrrrrr', 'rrrrRr', '.rRRr.'], { k: C.wd2, g: C.g2, r: C.r1, R: C.r2, W: '#ffb3a8' }, C.r3);
  ICON.dand = pix(['.w.w.w.', 'w.www.w', '.wwgww.', 'w.www.w', '.w.w.w.', '...k...', '..lk...', '...k...'], { w: C.wh, g: '#e9f2e0', k: C.g3, l: C.g2 }, '#8b8aa0');
  ICON.pumpkin = pix(['....gg....', '.oooooooo.', 'ooOoooOooo', 'ooOyooOooo', 'ooOoooOooo', '.ooOooOoo.', '..oooooo..'], { g: C.g3, o: C.pum, O: C.pum2, y: C.yl }, C.r3);
  ICON.letter = pix(['wwwwwwww', 'wcwwwwcw', 'wwcwwcww', 'wwwrrwww', 'wwwrrwww', 'wwwwwwww'], { w: C.wh, c: C.wl2, r: C.r1 });
  ICON.card = pix(['pppppppp', 'pwwwwwwp', 'pwrwrwwp', 'pwrrrwwp', 'pwwrwwwp', 'pppppppp'], { p: C.pk, w: C.wh, r: C.r1 });
  ICON.coin = pix(['.yyy.', 'yyWyy', 'yWyyy', 'yyyyd', '.ydd.'], { y: C.yl, W: C.wh, d: '#e9b23a' }, '#a8792a');
  ICON.heart = pix(['.rr.rr.', 'rWrrrrr', 'rrrrrrr', '.rrrrr.', '..rrr..', '...r...'], { r: C.r1, W: '#ffb3a8' }, C.r3);
  ICON.chick = pix(['...yy.', '..yyko', '.yyyy.', 'yyYyy.', '.yyyy.', '.o..o.'], { y: '#ffe066', Y: '#f2c94c', k: C.ol, o: C.car }, '#a8792a');
  ICON.can = canSpr(false); ICON.canFull = canSpr(true);
  ICON.water = pix(['...b...', '..bbb..', '..bWb..', '...b...', '.l...l.', '.ll.ll.', '..lkl..', '...k...'], { b: C.w2, W: C.w0, l: C.g1, k: C.g3 }, C.g5);
  ICON.check = pix(['.....tt', '....tt.', 't..tt..', 'tttt...', '.tt....'], { t: C.teal }, C.teal2);
  ICON.sun = pix(['....y....', '.y.....y.', '...yyy...', '..yyWyy..', 'y.yyyyy.y', '..yyyyy..', '...yyy...', '.y.....y.', '....y....'], { y: '#ffc94a', W: '#fff2b0' }, '#d9862c');
  ICON.moon = pix(['...mmm...', '..mmm....', '.mmm.....', '.mmm.....', '.mmm.....', '.mmmm....', '..mmmmm..', '...mmm...'], { m: '#ffe7a0' }, '#8a6aa8');
  ICON.zz = pix(['zzzz.....', '..z......', '.z...zzz.', 'zzzz..z..', '.....zzz.'], { z: C.wh }, '#6b5c8a');
  ICON.arrow = pix(['yyyyyyy', '.yyyyy.', '..yyy..', '...y...'], { y: '#ffd35c' });
  ICON.arrowW = pix(['wwwww', '.www.', '..w..'], { w: C.wh });
}

/* пиксельные цифры для пузырей (×3) */
const DIG = { x: ['...', 'x.x', '.x.', 'x.x', '...'], 2: ['xxx', '..x', 'xxx', 'x..', 'xxx'], 3: ['xxx', '..x', 'xxx', '..x', 'xxx'] };

/* ---------------- раскладки мира ----------------
   LAND — широкое окно (мир 320×180), иначе телефон (180×320). Координаты — в точках мира; «ноги» объектов. */
const K = LAND ? {
  house: [28, 38], door: [70, 114], doorHit: [60, 82, 80, 108],
  mailbox: [8, 97], mailStand: [26, 117], can: [97, 113],
  fence: [138, 52, 10], beds: [140, 76, [64, 84, 104], 12],
  mole: [132, 120], moleStand: [116, 122], scare: [226, 61],
  tree: [294, 114], treeStand: [294, 121], hedge: [268, 123], hedgeStand: [254, 125],
  pond: [276, 150, 50, 24], pondTap: [246, 140], pier: [208, 142], pierWalk: [208, 146, 236, 158],
  frog: [229, 151], frogStand: [215, 153], duck: [292, 150, 18, 8],
  sheep: [38, 148], sheepStand: [19, 149], hen: [96, 142], henArea: [80, 126, 112, 150],
  catRoof: [52, 54], catDoor: [46, 116], catStand: [46, 123],
  bell: [188, 138],
  dands: [[18, 128], [100, 146], [196, 124], [250, 100], [64, 134], [124, 80]],
  coins: [[152, 128], [244, 92], [126, 122], [58, 126], [204, 108], [176, 150], [118, 70], [254, 112], [16, 140], [86, 150], [232, 126]],
  table: [160, 146], lantW: 46, fest: { mole: [128, 148], cat: [196, 136], frog: [192, 150], sheep: [114, 163], hedge: [182, 164], hen: [100, 150], hen2: [214, 158], hero: [158, 164] },
  minY: 62, maxY: 156,
  blocks: [[0, 0, 330, 61], [28, 0, 112, 109], [10, 104, 20, 114], [136, 0, 222, 64], [140, 63, 216, 77], [140, 83, 216, 97], [140, 103, 216, 117],
    [222, 0, 240, 88], [124, 114, 140, 121], [27, 140, 50, 151], [289, 104, 300, 115], [223, 141, 238, 151], [106, 155, 210, 200]],
  paths: [[[150, 190], [150, 150], [120, 138], [76, 124], 8], [[130, 138], [160, 132], [175, 124], [205, 124], 6], [[76, 124], [70, 120], [70, 116], [70, 110], 6],
    [[140, 150], [110, 160], [60, 160], [18, 152], 5], [[176, 136], [192, 144], [202, 150], [214, 152], 5], [[118, 134], [124, 124], [128, 116], [130, 108], 4],
    [[205, 124], [230, 120], [250, 124], [262, 126], 4]],
  blobs: [[76, 120, 10]],
  trees: [[8, -8, 14], [30, -12, 16], [56, -14, 13], [122, -14, 15], [146, -10, 12], [170, -16, 14], [196, -12, 13], [226, -14, 16], [256, -10, 12], [284, -16, 15], [310, -8, 14], [-2, 40, 12], [316, 70, 9]],
  lilies: [[244, 145, 1], [306, 148, 0], [268, 164, 1], [296, 166, 0]],
  sun: [250, 6], noFlower: [[20, 30, 120, 118], [134, 46, 244, 120], [200, 120, 330, 180], [104, 150, 214, 180]]
} : {
  house: [2, 58], door: [44, 130], doorHit: [34, 102, 54, 124],
  mailbox: [92, 104], mailStand: [104, 124], can: [74, 134],
  fence: [88, 140, 10], beds: [92, 76, [154, 174, 194], 12],
  mole: [80, 196], moleStand: [63, 199], scare: null,
  tree: [150, 116], treeStand: [150, 124], hedge: [126, 122], hedgeStand: [114, 126],
  pond: [124, 262, 50, 22], pondTap: [96, 258], pier: [50, 250], pierWalk: [50, 254, 78, 266],
  frog: [72, 259], frogStand: [57, 262], duck: [140, 264, 18, 7],
  sheep: [32, 236], sheepStand: [12, 238], hen: [40, 192], henArea: [20, 160, 58, 206],
  catRoof: [26, 74], catDoor: [22, 134], catStand: [30, 138],
  bell: [154, 228],
  dands: [[16, 216], [96, 218], [164, 218], [40, 280], [128, 132], [12, 176]],
  coins: [[60, 166], [170, 232], [110, 238], [26, 262], [140, 220], [120, 134], [170, 126], [36, 216], [96, 280], [8, 196], [100, 96]],
  table: [88, 222], lantW: 36, fest: { mole: [60, 224], cat: [136, 230], frog: [116, 225], sheep: [36, 240], hedge: [62, 242], hen: [22, 220], hen2: [158, 236], hero: [90, 240] },
  minY: 86, maxY: 286,
  blocks: [[0, 0, 200, 85], [2, 0, 86, 127], [94, 112, 104, 121], [86, 138, 176, 152], [92, 153, 168, 167], [92, 173, 168, 187], [92, 193, 168, 207],
    [71, 190, 88, 197], [21, 224, 44, 237], [145, 106, 156, 117], [64, 250, 80, 260], [0, 288, 200, 400]],
  paths: [[[44, 128], [46, 160], [40, 190], [52, 214], 6], [[6, 236], [50, 212], [110, 212], [180, 216], 6], [[52, 214], [52, 236], [50, 250], [56, 258], 5],
    [[56, 132], [80, 128], [100, 128], [126, 130], 4]],
  blobs: [[44, 132, 8]],
  trees: [[8, 20, 13], [34, 16, 15], [62, 22, 12], [92, 14, 14], [120, 20, 13], [148, 16, 15], [176, 22, 12]],
  lilies: [[96, 256, 1], [158, 258, 0], [118, 276, 1], [148, 276, 0]],
  sun: [150, 6], noFlower: [[0, 50, 92, 128], [86, 96, 180, 212], [60, 236, 180, 290], [44, 246, 84, 270], [0, 0, 180, 70]]
};
const BED = { x: K.beds[0], w: K.beds[1], ys: K.beds[2], h: K.beds[3] };
const gapY = (i) => BED.ys[i] + BED.h + (BED.ys[1] - BED.ys[0] - BED.h) / 2 + .5;    // середина прохода под грядкой i
const below3 = BED.ys[2] + BED.h + 4;

/* ---------------- проходимость и поиск пути ---------------- */
const GW = Math.ceil(WW / 2), GH = Math.ceil(WH / 2), WALK = new Uint8Array(GW * GH);
function solid(x, y) {
  if (x < 3 || x > WW - 3 || y < K.minY || y > K.maxY) return true;
  for (const b of K.blocks) if (x >= b[0] && x < b[2] && y >= b[1] && y < b[3]) return true;
  const [cx, cy, rx, ry] = K.pond, pw = K.pierWalk;
  if (((x - cx) / (rx + 2)) ** 2 + ((y - cy) / (ry + 2)) ** 2 <= 1 && !(x >= pw[0] && x < pw[2] && y >= pw[1] && y < pw[3])) return true;
  return false;
}
function buildWalk() {
  for (let gy = 0; gy < GH; gy++) for (let gx = 0; gx < GW; gx++) {
    const x = gx * 2 + 1, y = gy * 2 + 1;
    WALK[gy * GW + gx] = !(solid(x, y) || solid(x - 4, y) || solid(x + 4, y) || solid(x, y - 2) || solid(x, y + 2) || solid(x - 4, y + 2) || solid(x + 4, y + 2)) ? 1 : 0;
  }
}
const cellAt = (x, y) => { const gx = Math.floor(x / 2), gy = Math.floor(y / 2); return gx < 0 || gy < 0 || gx >= GW || gy >= GH ? -1 : gy * GW + gx; };
const walkAt = (x, y) => { const c = cellAt(x, y); return c >= 0 && WALK[c] === 1; };
function nearestFree(x, y) {
  const gx0 = Math.floor(x / 2), gy0 = Math.floor(y / 2);
  for (let r = 0; r < 60; r++) {
    let best = -1, bd = 1e9;
    for (let dy = -r; dy <= r; dy++) for (let dx = -r; dx <= r; dx++) {
      if (Math.max(Math.abs(dx), Math.abs(dy)) !== r) continue;
      const gx = gx0 + dx, gy = gy0 + dy; if (gx < 0 || gy < 0 || gx >= GW || gy >= GH) continue;
      const i = gy * GW + gx; if (!WALK[i]) continue;
      const d = dx * dx + dy * dy; if (d < bd) { bd = d; best = i; }
    }
    if (best >= 0) return best;
  }
  return -1;
}
const cx2 = (i) => (i % GW) * 2 + 1, cy2 = (i) => Math.floor(i / GW) * 2 + 1;
function los(ax, ay, bx, by) { const n = Math.ceil(dist(ax, ay, bx, by)); for (let k = 1; k < n; k++) { const t = k / n; if (!walkAt(ax + (bx - ax) * t, ay + (by - ay) * t)) return false; } return true; }
const GS = new Float32Array(GW * GH), CAME = new Int32Array(GW * GH), SHUT = new Uint8Array(GW * GH);
function findPath(sx, sy, tx, ty) {
  let s = cellAt(sx, sy); if (s < 0 || !WALK[s]) s = nearestFree(sx, sy);
  const t = nearestFree(tx, ty); if (s < 0 || t < 0) return null;
  const exact = walkAt(tx, ty) && cellAt(tx, ty) === t;
  if (s === t) return exact ? [[tx, ty]] : [[cx2(t), cy2(t)]];
  GS.fill(1e9); CAME.fill(-1); SHUT.fill(0);
  const heap = [], hf = [];
  const push = (i, f) => { heap.push(i); hf.push(f); let k = heap.length - 1; while (k > 0) { const p = (k - 1) >> 1; if (hf[p] <= hf[k]) break; [heap[p], heap[k]] = [heap[k], heap[p]]; [hf[p], hf[k]] = [hf[k], hf[p]]; k = p; } };
  const pop = () => { const top = heap[0], li = heap.pop(), lf = hf.pop(); if (heap.length) { heap[0] = li; hf[0] = lf; let k = 0; for (;;) { const l = k * 2 + 1, r = l + 1; let m = k; if (l < heap.length && hf[l] < hf[m]) m = l; if (r < heap.length && hf[r] < hf[m]) m = r; if (m === k) break; [heap[m], heap[k]] = [heap[k], heap[m]]; [hf[m], hf[k]] = [hf[k], hf[m]]; k = m; } } return top; };
  const tgx = t % GW, tgy = Math.floor(t / GW), h = (i) => { const dx = Math.abs(i % GW - tgx), dy = Math.abs(Math.floor(i / GW) - tgy); return Math.max(dx, dy) + .414 * Math.min(dx, dy); };
  GS[s] = 0; push(s, h(s));
  let found = false;
  while (heap.length) {
    const c = pop(); if (SHUT[c]) continue; SHUT[c] = 1;
    if (c === t) { found = true; break; }
    const gx = c % GW, gy = Math.floor(c / GW);
    for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
      if (!dx && !dy) continue;
      const nx = gx + dx, ny = gy + dy; if (nx < 0 || ny < 0 || nx >= GW || ny >= GH) continue;
      const n = ny * GW + nx; if (!WALK[n] || SHUT[n]) continue;
      if (dx && dy && (!WALK[gy * GW + nx] || !WALK[ny * GW + gx])) continue;
      const g = GS[c] + (dx && dy ? 1.414 : 1);
      if (g < GS[n]) { GS[n] = g; CAME[n] = c; push(n, g + h(n)); }
    }
  }
  if (!found) return null;
  const cells = []; for (let c = t; c !== -1 && c !== s; c = CAME[c]) cells.push(c); cells.reverse();
  const pts = cells.map((c) => [cx2(c), cy2(c)]);
  if (exact) pts[pts.length - 1] = [tx, ty];
  const out = []; let ax = sx, ay = sy, i = 0;               // спрямляем: от точки — к самой дальней видимой
  while (i < pts.length) { let j = pts.length - 1; while (j > i && !los(ax, ay, pts[j][0], pts[j][1])) j--; out.push(pts[j]); ax = pts[j][0]; ay = pts[j][1]; i = j + 1; }
  return out;
}

/* ---------------- земля: рисуется один раз ---------------- */
let BG = null, WCV = null, WX = null, LIGHT = null;
const PROPS = [];                                 // высокие неподвижные вещи — рисуются по глубине вместе с живыми
const SH = {};
function shadowCv(rx, ry) {
  const k = rx + ':' + ry; if (SH[k]) return SH[k];
  const c = mk(rx * 2 + 2, ry * 2 + 2), x = c.getContext('2d'); x.fillStyle = 'rgba(29,59,51,.28)';
  for (let y = 0; y < c.height; y++) for (let X = 0; X < c.width; X++) { const dx = (X + .5 - rx - 1) / rx, dy = (y + .5 - ry - 1) / ry; if (dx * dx + dy * dy <= 1) x.fillRect(X, y, 1, 1); }
  return (SH[k] = c);
}
function bake() {
  const c = mk(WW, WH), g = c.getContext('2d'), r = rng(LAND ? 7 : 11), area = WW * WH / 57600;
  const P = (x, y, col) => { g.fillStyle = col; g.fillRect(Math.round(x), Math.round(y), 1, 1); };
  const R = (x, y, w, h, col) => { g.fillStyle = col; g.fillRect(Math.round(x), Math.round(y), Math.round(w), Math.round(h)); };
  R(0, 0, WW, WH, C.g1);
  for (let i = 0; i < 70 * area; i++) { const x = r() * WW, y = r() * WH, rx = 6 + r() * 16, ry = 3 + r() * 6, col = r() < .5 ? C.g0 : C.g2;
    for (let yy = -ry; yy <= ry; yy++) for (let xx = -rx; xx <= rx; xx++) if ((xx / rx) ** 2 + (yy / ry) ** 2 <= 1 && ((Math.round(xx + yy + x)) & 1) === 0 && r() < .5) P(x + xx, y + yy, col); }
  for (let i = 0; i < 260 * area; i++) { const x = r() * WW | 0, y = r() * WH | 0, col = r() < .6 ? C.g2 : C.g0; P(x, y, col); P(x + 2, y, col); P(x + 1, y - 1, col); }
  // тропинки
  const path = new Uint8Array(WW * WH);
  const blob = (cx, cy, rr) => { for (let y = Math.floor(cy - rr); y <= cy + rr; y++) for (let x = Math.floor(cx - rr); x <= cx + rr; x++) { if (x < 0 || y < 0 || x >= WW || y >= WH) continue; if ((x + .5 - cx) ** 2 + ((y + .5 - cy) * 1.25) ** 2 <= rr * rr) path[y * WW + x] = 1; } };
  const bez = (p0, p1, p2, p3, rr) => { for (let t = 0; t <= 1; t += .004) { const u = 1 - t; blob(u * u * u * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t * t * t * p3[0], u * u * u * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t * t * t * p3[1], rr + Math.sin(t * 23) * .8); } };
  K.paths.forEach((p) => bez(p[0], p[1], p[2], p[3], p[4])); K.blobs.forEach((b) => blob(...b));
  const at = (x, y) => x >= 0 && y >= 0 && x < WW && y < WH && path[y * WW + x];
  for (let y = 0; y < WH; y++) for (let x = 0; x < WW; x++) { if (!path[y * WW + x]) continue; const e = !at(x, y - 1) || !at(x, y + 1) || !at(x - 1, y) || !at(x + 1, y), e2 = !at(x, y + 2); P(x, y, e ? C.d2 : (e2 ? C.d1 : C.d0)); }
  for (let i = 0; i < 120 * area; i++) { const x = r() * WW | 0, y = r() * WH | 0; if (at(x, y) && at(x + 1, y)) P(x, y, r() < .5 ? C.d1 : C.d2); }
  for (let i = 0; i < 26 * area; i++) { const x = r() * WW | 0, y = r() * WH | 0; if (at(x, y) && at(x + 3, y) && at(x, y + 2)) { R(x, y, 2, 1, C.st0); P(x, y + 1, C.st1); P(x + 1, y + 1, C.st1); } }
  // пруд
  const [pcx, pcy, prx, pry] = K.pond;
  for (let y = Math.floor(pcy - pry - 3); y <= pcy + pry + 3; y++) for (let x = Math.floor(pcx - prx - 3); x <= pcx + prx + 3; x++) {
    const wob = Math.sin(x * .21) * 1.4 + Math.cos(y * .33) * 1.2, dx = (x + .5 - pcx) / (prx + wob), dy = (y + .5 - pcy) / (pry + wob * .6), d = dx * dx + dy * dy;
    if (d <= 1.18 && d > 1) P(x, y, C.d1); if (d <= 1.1 && d > 1) P(x, y, C.d2); if (d <= 1) P(x, y, d > .82 ? C.w1 : d > .4 ? C.w2 : C.w3); }
  K.lilies.forEach(([x, y, fl]) => { const s = new Spr(10, 7); s.e(5, 3.5, 4.5, 3, C.g2).e(5, 3, 3.5, 2.2, C.g1); s.tri([[5, 3.5], [9, 1], [9, 5]], null); for (let i = 0; i < 3; i++) s.p(6 + i, 3, null); s.outline(C.g4); if (fl) { s.e(3.5, 2.5, 1.6, 1.4, C.pk); s.p(3, 2, C.wh); } g.drawImage(s.cv, x, y); });
  { const s = new Spr(30, 20); for (let i = 0; i < 5; i++) { s.r(2 + i * 5, 4, 5, 10, i % 2 ? C.wd1 : C.wd0); s.r(2 + i * 5, 4, 1, 10, C.wd2); } s.r(1, 13, 28, 2, C.wd2).r(3, 15, 2, 5, C.wd2).r(25, 15, 2, 5, C.wd2); s.outline(); g.drawImage(s.cv, K.pier[0], K.pier[1]); }
  // огород: заборчик и грядки
  { const [fx, fy, n] = K.fence, s = new Spr(n * 8 + 3, 12);
    for (let i = 0; i <= n; i++) s.r(i * 8, 0, 3, 11, C.wd0).p(i * 8 + 2, 0, null).p(i * 8, 0, null).r(i * 8 + 2, 1, 1, 10, C.wd1);
    s.r(0, 3, n * 8 + 3, 2, C.wd0).r(0, 7, n * 8 + 3, 2, C.wd0).r(0, 4, n * 8 + 3, 1, C.wd1).r(0, 8, n * 8 + 3, 1, C.wd1); s.outline(C.wd2); g.drawImage(s.cv, fx, fy); }
  BED.ys.forEach((by) => { const s = new Spr(BED.w, BED.h); s.r(0, 0, BED.w, BED.h, C.s0); for (let j = 2; j < BED.h; j += 4) s.r(1, j, BED.w - 2, 1, C.s1); for (let i = 0; i < BED.w * BED.h / 12; i++) s.p(r() * BED.w, r() * BED.h, C.s2); s.r(0, BED.h - 1, BED.w, 1, C.s2); s.outline(C.s2); g.drawImage(s.cv, BED.x, by); });
  // тени высоких вещей
  const shade = (x, y, rx, ry) => g.drawImage(shadowCv(rx, ry), Math.round(x - rx - 1), Math.round(y - ry - 1));
  shade(K.house[0] + 44, K.house[1] + 68, 42, 6);
  // цветы, одуванчики (для красоты — не те, что собирать)
  const busy = (x, y) => at(x, y) || at(x, y + 3) || solid(x, y + 1) && !(y < K.minY) || K.noFlower.some((b) => x >= b[0] && x < b[2] && y >= b[1] && y < b[3]);
  for (let i = 0; i < 60 * area; i++) { const x = r() * WW | 0, y = r() * WH | 0; if (busy(x, y)) continue; const col = [C.wh, C.pk, C.lav, C.yl][i % 4]; P(x, y, col); P(x - 1, y + 1, col); P(x + 1, y + 1, col); P(x, y + 2, col); P(x, y + 1, C.yl); P(x, y + 3, C.g3); }
  for (let i = 0; i < 14 * area; i++) { const x = r() * WW | 0, y = r() * WH | 0; if (busy(x, y)) continue; P(x, y + 3, C.g3); P(x, y + 2, C.g3); for (const [dx, dy] of [[0, -1], [1, 0], [-1, 0], [0, 1], [1, 1], [-1, -1], [1, -1], [-1, 1]]) P(x + dx, y + dy, C.wh); P(x, y, '#e9f2e0'); }
  BG = c;
  // высокие вещи: дом, деревья по краям, пугало, почтовый ящик
  PROPS.length = 0;
  PROPS.push({ cv: houseSpr().cv, x: K.house[0], y: K.house[1], foot: K.house[1] + 67, id: 'house' });
  K.trees.forEach(([x, y, rr]) => { const s = treeSpr(rr, 0), w = s.w, h = s.h; g.drawImage(shadowCv(Math.round(rr * .9), 3), Math.round(x - rr * .9 - 1), Math.round(y + h - 8)); PROPS.push({ cv: s.cv, x: Math.round(x - w / 2), y: y - 4, foot: y - 4 + h - 1 }); });
  if (K.scare) { const s = scareSpr(); shade(K.scare[0] + 7, K.scare[1] + 25, 6, 2); PROPS.push({ cv: s.cv, x: K.scare[0], y: K.scare[1], foot: K.scare[1] + 25 }); }
  shade(K.mailbox[0] + 5, K.mailbox[1] + 15, 5, 2);
  shade(K.tree[0], K.tree[1], 15, 3);
  // свет: солнце с угла и мягкая виньетка — в свой холст
  LIGHT = mk(WW, WH); const lx = LIGHT.getContext('2d');
  const lg = lx.createRadialGradient(K.sun[0], K.sun[1], 10, K.sun[0], K.sun[1], Math.max(WW, WH) * .85); lg.addColorStop(0, 'rgba(255,236,170,.30)'); lg.addColorStop(1, 'rgba(255,236,170,0)'); lx.fillStyle = lg; lx.fillRect(0, 0, WW, WH);
  const vg = lx.createRadialGradient(WW / 2, WH / 2, Math.min(WW, WH) * .55, WW / 2, WH / 2, Math.max(WW, WH) * .62); vg.addColorStop(0, 'rgba(30,40,70,0)'); vg.addColorStop(1, 'rgba(30,40,70,.3)'); lx.fillStyle = vg; lx.fillRect(0, 0, WW, WH);
  WCV = mk(WW, WH); WX = WCV.getContext('2d'); WX.imageSmoothingEnabled = false;
}

/* ---------------- спрайты: собрать всё ---------------- */
const SP = {};
function buildSprites() {
  SP.hero = {}; for (const b of [0, 1]) for (const st of [0, 1, 2]) for (const bl of [0, 1]) SP.hero[b + '' + st + bl] = heroSpr(b, st, bl).cv;
  SP.basket = basketSpr(false).cv; SP.basketFull = basketSpr(true).cv;
  SP.mole = moleSpr().cv;
  SP.sheep = {}; for (const b of [0, 1]) for (const w of [0, 1]) for (const bl of [0, 1]) SP.sheep[b + '' + w + bl] = sheepSpr(b, w, bl).cv;
  SP.frog = [frogSpr(0).cv, frogSpr(1).cv];
  SP.hen = [henSpr(0, 0).cv, henSpr(0, 1).cv]; SP.ryaba = [henSpr(1, 0).cv, henSpr(1, 1).cv];
  SP.chick = [chickSpr(0).cv, chickSpr(1).cv];
  SP.catSleep = catSleepSpr().cv; SP.catSit = [catSitSpr(0).cv, catSitSpr(1).cv];
  SP.hedge = [hedgeSpr(0, 0).cv, hedgeSpr(0, 1).cv, hedgeSpr(1, 0).cv, hedgeSpr(1, 1).cv];
  SP.duck = duckSpr().cv;
  SP.mail = [mailSpr(0).cv, mailSpr(1).cv];
  SP.can = ICON.can.cv; SP.canFull = ICON.canFull.cv;
  SP.appleTree = treeSpr(16, 1); SP.table = tableSpr().cv;
  SP.carrot = [carrotSpr(0).cv, carrotSpr(1).cv]; SP.cabbage = cabbageSpr().cv;
  SP.pumpkin = pumpkinSpr(false).cv; SP.giant = pumpkinSpr(true).cv; SP.pea = peaSpr().cv;
  SP.portrait = { mole: SP.mole, sheep: SP.sheep['000'], frog: SP.frog[0], hen: SP.ryaba[0], cat: SP.catSit[0], hedge: SP.hedge[0], duck: SP.duck, hero: SP.hero['000'] };
}

/* ---------------- слова ---------------- */
const NAME = { mole: 'Бабушка Крот', sheep: 'Барашек Пух', frog: 'Лягушонок Квак', hen: 'Курочка Ряба', cat: 'Кот Рыжик', hedge: 'Ёжик Колючка', duck: 'Утка Кряка', hero: 'Тиша' };
const NAME_COL = { mole: '#a8404c', sheep: '#6b5ca5', frog: '#3f8a4c', hen: '#b8681e', cat: '#cf5a1a', hedge: '#86512f', duck: '#3a74b4', hero: '#cf6430' };
const FACE_BG = { mole: '#f6d9cf', sheep: '#e6e0f6', frog: '#dcf2cf', hen: '#fbe6c6', cat: '#ffe1c2', hedge: '#efdcc8', duck: '#d6ecf7', hero: '#ffe3c4' };
const L = {
  mole: { carrots: 'Тиша, голубчик! Принеси три морковки с верхней грядки — пирожки затеваю.', carrotsDone: 'Вот спасибо! Хрустят, как первый снег. Держи монетки на пряники.',
    water: 'Ростки на нижней грядке пить просят. Лейка — у крыльца, вода — в пруду.', waterDone: 'Глянь-ка, как вытянулись! Лёгкая у тебя рука, внучек.',
    pumpkin: 'Сегодня праздник! Для пирога нужна самая большая тыква. Донесёшь?', pumpkinDone: 'Ох, какая! Пирог будет на весь хутор — и ёжику останется.',
    idle: ['Под землёй, знаешь ли, тоже бывают пробки.', 'Морковка любит, когда с ней разговаривают.', 'Очки протру — и опять всё вижу. Почти.'] },
  sheep: { bell: 'Бе-е… Колокольчик потерялся. Без него я как облако без неба.', bellDone: 'Динь-динь! Теперь меня снова слышно. Бе-е-е-спасибо!',
    wreath: 'К празднику хочу венок из одуванчиков. Они пушистые — как я!', wreathDone: 'Ну как я тебе? Самый нарядный барашек на хуторе!',
    idle: ['Я не толстый — я пушистый.', 'Бе-е. Это значит «привет».', 'Динь! Это я просто так.'] },
  frog: { hook: 'Ква! Крючок утонул… Новый должны были прислать по почте.', hookDone: 'Ква-ква! Теперь рыбка клюнет. Ну, может, к обеду.',
    give: 'Поймал двух! Одну отнеси Рыжику — а то он так на меня смотрит…', idle: ['Тише… рыба думает.', 'Я не квакаю, я пою. Просто низким голосом.', 'Утка опять распугала всю рыбу.'] },
  hen: { chick: 'Ко-ко-ко! Считала цыплят — одного нет. Пересчитала — опять нет!', chick2: 'Он любит прятаться в капусте, проказник.',
    chickDone: 'Нашёлся! Спасибо, Тиша. Пойдём, горе моё, зёрнышки клевать.', idle: ['Ко-ко! Сначала было яйцо. Или я. Не помню.', 'Ко! Это по-нашему «хорошая погода».'] },
  cat: { fish: 'Мр-р… Мне бы рыбки. Я не ленюсь — я берегу силы на ужин.', fishDone: 'Мур-р-р. Ты лучший на этом хуторе. Ну, после меня.',
    sleep: 'Хр-р… мур-р… (кот спит и видит рыбу)', idle: ['Мр-р. Солнышко — моё.', 'Я сыт. Почти.'] },
  hedge: { apples: 'Здравствуйте! Я ёжик Колючка, пришёл на праздник. Достанешь пару яблок?', apples2: 'Яблоки высоко… Может, потрясти яблоню?',
    applesDone: 'Спасибо! Я не колючий — я с характером. И очень благодарный.', idle: ['Ф-ф-ф! Это я так радуюсь.', 'Пирог будет? Я подожду. Я терпеливый.'] },
  duck: { idle: ['Кря!', 'Кря-кря.', 'Кря? Кря.'] },
};
const SAY = {
  start1: A.isTouch ? 'Ого, у соседей над головами пузыри — им нужна помощь! Нажми на соседа, я подойду.' : 'Ого, у соседей над головами пузыри — им нужна помощь! Подойди и нажми E — или просто щёлкни по соседу.',
  start2: 'Новый день! В почтовом ящике что-то белеет, а курочка Ряба всполошилась.',
  start3: 'Сегодня праздник урожая! К вечеру все соберутся у дома. А тыква-то за ночь — во!',
  carrotEnough: 'Хватит — бабушке нужно три.', carrotLater: 'Пусть дозревает.',
  cabbage: ['Тут только капуста. Хрум.', 'Кочан-молчун. Цыплёнка нет.', 'Капуста. Очень капустная.'], cabbageNo: 'Капуста растёт. Ей хорошо.',
  chickFound: 'Пи! Нашёлся! Цыплёнок топает следом. Ведём его к маме.',
  pumpkinSmall: 'Тыквы ещё растут. К празднику будут — во!', pumpkinTake: 'Ух, тяжёлая! Несём бабушке.',
  sprouts: 'Ростки. Растут потихоньку.', sproutsNoCan: 'Ростки хотят пить. Нужна лейка — она у крыльца.', sproutsEmpty: 'Лейка пустая. Воды можно набрать в пруду.',
  sproutsDone: 'Ростки пьют… и растут на глазах! Надо сказать бабушке.', flowers: 'Горошек цветёт. Красота!',
  canTake: 'Лейка в руках. Теперь — за водой, к пруду.', canNo: 'Лейка. Сегодня поливать нечего.',
  pondFill: 'Буль-буль — полная лейка!', pondNo: 'Красивый пруд. Тут главная — утка Кряка.', pondFull: 'Лейка и так полная.',
  mailHook: 'Посылка для Квака! Внутри — новый крючок.', mailLetter: '«Приглашаем всех на праздник урожая! Ваш хутор Одуванчик». Ура!',
  mailCard: 'Открытка: «Тиша, ты наш герой! Бабушка Крот». И монетки внутри!', mailEmpty: 'Пусто. Только паучок здесь живёт.',
  treeGreen: 'Яблоки ещё зелёные — к празднику поспеют.', treeShaken: 'Остальные пусть висят — для птичек.', treeShake: 'Тряс-тряс — бум! Яблоки упали.',
  appleEnough: 'Ёжику хватит двух. Это пусть лежит.', dandEnough: 'На венок хватит трёх.', bellFound: 'Колокольчик! Динь-динь. Это Пуха.',
  scare: 'Подсолнух-сторож. Пугает ворон улыбкой.', door: 'Дома тепло. Но сначала — дела!', hen: 'Ко-ко!',
  dusk: 'Солнце садится. Дела подождут до завтра.', duskAll: 'Все соседи довольны! Пора домой — солнце садится.', fest: 'Вечер! Праздник начинается!',
  allDone: 'Все дела сделаны! Можно поискать монетки — они блестят в траве.', noWay: 'Туда не пройти.', far: 'Надо подойти поближе.', farKb: 'Подойди поближе к соседу или вещи — и нажми E.',
};
const DAYS = [
  { name: 'Знакомство', tasks: ['carrots', 'bell', 'hook'], next: 'Завтра в почтовый ящик придёт письмо, а курочка Ряба что-то всполошилась…' },
  { name: 'Хлопоты', tasks: ['chick', 'water', 'fish'], next: 'Завтра — праздник урожая! Говорят, на хутор придёт новый гость.' },
  { name: 'Праздник урожая', tasks: ['apples', 'wreath', 'pumpkin'] },
];
const TASKS = {
  carrots: { who: 'mole', text: 'Морковки для бабушки', icon: 'carrot', item: 'carrot', n: 3 },
  bell: { who: 'sheep', text: 'Колокольчик Пуха', icon: 'bell', item: 'bell', n: 1 },
  hook: { who: 'frog', text: 'Крючок для Квака', icon: 'hook', item: 'hook', n: 1 },
  chick: { who: 'hen', text: 'Цыплёнок Рябы', icon: 'chick', item: 'chick', n: 1 },
  water: { who: 'mole', text: 'Полить ростки', icon: 'water', n: 3 },
  fish: { who: 'cat', text: 'Рыбка для Рыжика', icon: 'fish', item: 'fish', n: 1 },
  apples: { who: 'hedge', text: 'Яблоки для ёжика', icon: 'apple', item: 'apple', n: 2 },
  wreath: { who: 'sheep', text: 'Венок для Пуха', icon: 'dand', item: 'dand', n: 3 },
  pumpkin: { who: 'mole', text: 'Тыква на пирог', icon: 'pumpkin', item: 'pumpkin', n: 1 },
};

/* ---------------- звук ---------------- */
const now = () => SND.now();
const VOICE = { mole: [260, 'triangle'], sheep: [470, 'triangle'], frog: [170, 'triangle'], hen: [820, 'square'], cat: [600, 'triangle'], hedge: [700, 'triangle'], duck: [380, 'square'], hero: [640, 'triangle'] };
const snd = {
  blip(who) { if (!SND.ctx) return; const [f, w] = VOICE[who] || VOICE.hero; SND.tone(f * (.85 + Math.random() * .4), now(), .055, w === 'square' ? .018 : .045, w); },
  pick() { if (!SND.ctx) return; const t = now(); SND.tone(620, t, .09, .08, 'triangle', null, 980); SND.tone(1320, t + .05, .1, .03, 'sine'); },
  thanks() { if (!SND.ctx) return; const t = now(); [523, 659, 784, 1047, 1319].forEach((f, i) => SND.tone(f, t + i * .07, .22, .06, 'triangle')); SND.tone(1568, t + .38, .5, .03, 'sine'); },
  coin() { SND.play('coin'); },
  step() { if (!SND.ctx) return; SND.hiss(now(), .04, .012, 'lowpass', 600); },
  creak() { if (!SND.ctx) return; const t = now(); SND.tone(220, t, .25, .03, 'sawtooth', null, 140, .03); SND.hiss(t + .15, .12, .03, 'highpass', 4000); },
  splash() { if (!SND.ctx) return; const t = now(); SND.hiss(t, .35, .09, 'lowpass', 1200); SND.tone(380, t, .2, .06, 'sine', null, 140); },
  pour() { if (!SND.ctx) return; const t = now(); for (let k = 0; k < 6; k++) SND.hiss(t + k * .1, .12, .035, 'bandpass', 1800 + Math.random() * 800); SND.tone(700, t + .5, .5, .03, 'sine', null, 1400); },
  rustle() { if (!SND.ctx) return; const t = now(); for (let k = 0; k < 5; k++) SND.hiss(t + k * .06, .1, .05, 'highpass', 2600 + k * 300); },
  thud() { if (!SND.ctx) return; SND.tone(160, now(), .16, .1, 'sine', null, 70); },
  bell() { if (!SND.ctx) return; const t = now(); [[1568, .05, 1.2], [2349, .02, .8], [3136, .012, .5]].forEach(([f, v, d]) => SND.tone(f, t, d, v, 'sine')); },
  cluck() { if (!SND.ctx) return; const t = now(); SND.tone(900, t, .07, .04, 'square', null, 700); SND.tone(980, t + .12, .09, .04, 'square', null, 640); },
  quack() { if (!SND.ctx) return; const t = now(); SND.tone(420, t, .13, .05, 'sawtooth', null, 300); SND.tone(400, t + .17, .15, .05, 'sawtooth', null, 280); },
  baa() { if (!SND.ctx) return; const t = now(); for (let k = 0; k < 5; k++) SND.tone(480 + (k % 2) * 30, t + k * .07, .09, .05, 'triangle'); },
  meow() { if (!SND.ctx) return; const t = now(); SND.tone(640, t, .18, .05, 'triangle', null, 900); SND.tone(880, t + .17, .25, .05, 'triangle', null, 560); },
  croak() { if (!SND.ctx) return; const t = now(); SND.tone(130, t, .16, .09, 'triangle', null, 96); SND.tone(140, t + .22, .2, .09, 'triangle', null, 92); },
  peep() { if (!SND.ctx) return; const t = now(); SND.tone(2200, t, .06, .03, 'sine', null, 2600); SND.tone(2300, t + .1, .06, .03, 'sine', null, 2700); },
  rooster() { if (!SND.ctx) return; const t = now(); SND.tone(520, t, .14, .05, 'square', null, 760); SND.tone(780, t + .16, .12, .05, 'square'); SND.tone(820, t + .3, .4, .05, 'square', null, 560); },
  birds() { if (!SND.ctx || !SND.musicOn) return; const t = now(), f = 2400 + Math.random() * 1400; for (let k = 0; k < 3; k++) SND.tone(f + k * 140, t + k * .08, .05, .012, 'sine', SND.mus, f * 1.2); },
  nope() { if (!SND.ctx) return; const t = now(); SND.tone(330, t, .14, .04, 'triangle', null, 290); SND.tone(262, t + .13, .2, .04, 'triangle', null, 240); },
  evening() { if (!SND.ctx) return; const t = now(); [392, 494, 587, 784, 988].forEach((f, k) => { SND.tone(f, t + k * .16, 2.2, .04, 'sine'); }); },
};
const CALL = { sheep: 'baa', frog: 'croak', hen: 'cluck', cat: 'meow', duck: 'quack' };

/* ---------------- состояние ---------------- */
let S = null, GAME = null;
function hero0() { return { x: K.door[0], y: K.door[1], dir: 'down', flip: false, moving: false, ph: 0, path: null, pending: null, blink: 2, stepT: 0, alpha: 1, think: 0, trail: [], hold: false }; }
function fresh() {
  S = { mode: 'title', day: 1, coins: 0, hearts: 0, dayCoins: 0, dayHearts: 0, t: 0, clock: .1, eve: 0, speed: 1,
    inv: {}, canFull: false, tasks: [], cap: null, banner: null, parts: [], flyers: [], smoke: [], rings: [], fade: 0, fadeTo: 0, fadeThen: null,
    hero: hero0(), npcs: {}, hens: [], spots: [], pops: [], idle: 0, kb: false, mark: null, dest: null, endT: 0, introT: 0, slotPop: {}, birdT: 3, total: { helped: 0 } };
  S.target = target; S.busy = busy; S.checkTexts = checkTexts;
  setupDay(1);
}
function setupDay(d) {
  const r = Math.random;
  Object.assign(S, { day: d, clock: 0, eve: 0, inv: {}, canFull: false, canHome: true, watered: d >= 3, cap: null, mark: null, dest: null, endT: 0, dayCoins: 0, dayHearts: 0,
    fishGiven: false, chickIn: d === 2 ? (r() * 6) | 0 : -1, applesDown: false, treeShake: 0, mail: ['hook', 'letter', 'card'][d - 1], mailOpen: 0, pumpkinTaken: false, pumpkinAtMole: false,
    sheepBell: d >= 2, sheepWreath: false, frogHook: d >= 2, hedgeApple: false, flash: 0, idle: 0, fest: false, slotPop: {}, parts: [], flyers: [], rings: [], pops: [] });
  S.tasks = DAYS[d - 1].tasks.map((id) => Object.assign({ id, done: false, flash: 0, asked: false }, TASKS[id]));
  S.carrots = [0, 1, 2, 3, 4, 5, 6, 7].map((i) => ({ i, ripe: d === 1 ? i !== 2 && i !== 6 : i % 3 === 1, gone: false }));
  S.bell = d === 1 ? { x: K.bell[0], y: K.bell[1] } : null;
  S.apples = [[-7, -2], [6, 1], [-1, 6]].map(([dx, dy], i) => ({ i, dx, dy, x: 0, y: 0, st: 'tree', vy: 0, gx: K.tree[0] + [-11, 10, -1][i], gy: K.tree[1] + [5, 6, 10][i] }));
  const dl = K.dands.slice().sort(() => r() - .5).slice(0, 4);
  S.dands = d === 3 ? dl.map(([x, y], i) => ({ i, x, y })) : [];
  const cl = K.coins.filter(([x, y]) => walkAt(x, y)).sort(() => r() - .5).slice(0, 3);
  S.coinsW = cl.map(([x, y], i) => ({ i, x, y, ph: r() * 6 }));
  // жители
  const n = (id, x, y, o) => Object.assign({ id, x, y, hop: 0, happy: 0, blink: 1 + r() * 3, flip: false }, o || {});
  S.npcs = { mole: n('mole', ...K.mole), sheep: n('sheep', ...K.sheep), frog: n('frog', ...K.frog), duck: n('duck', K.duck[0], K.duck[1], { a: r() * 6 }) };
  if (d === 2) S.npcs.cat = n('cat', ...K.catDoor, { sleep: false, sit: true });
  else S.npcs.cat = n('cat', ...(d === 1 ? K.catRoof : K.catDoor), { sleep: true, sit: d !== 1, roof: d === 1 });
  if (d === 3) S.npcs.hedge = n('hedge', ...K.hedge, { flip: true });
  const [ax0, ay0, ax1, ay1] = K.henArea;
  S.hens = [{ x: ax0 + 8, y: ay1 - 6, tx: 0, ty: 0, t: 0, peck: 0, flip: false, ryaba: false }, { x: K.hen[0], y: K.hen[1], tx: 0, ty: 0, t: 1, peck: 0, flip: true, ryaba: true }];
  S.npcs.hen = n('hen', K.hen[0], K.hen[1], { ref: S.hens[1] });
  S.chick = d === 3 ? { x: K.hen[0] - 8, y: K.hen[1] + 2, st: 'withHen', ph: 0 } : d === 2 ? { x: 0, y: 0, st: 'hide', ph: 0 } : null;
  S.hero = hero0();
  S.cabWiggle = 0;
}
const have = (it) => S.inv[it] || 0;
const taskOf = (who) => S.tasks.find((t) => t.who === who && !t.done);
const ready = (t) => (t.id === 'water' ? S.watered : have(t.item) >= t.n);

/* ---------------- слова на экране ---------------- */
function say(who, text, extra = 0) {
  if (!text) return;
  S.cap = { who, text, t: 0, life: 2.4 + text.length * .045 + extra, typed: 0 };
}
function think(text) { say('hero', text); }

/* ---------------- места, с которыми можно что-то сделать ---------------- */
const rect = (x, y, w, h) => [x, y, x + w, y + h];
function npcBox(n, w, h) { return [n.x - w / 2 - 3, n.y - h - 2, n.x + w / 2 + 3, n.y + 3]; }
function buildSpots() {
  const L2 = [], add = (o) => { o.fx = o.fx == null ? (o.hit[0] + o.hit[2]) / 2 : o.fx; o.fy = o.fy == null ? o.hit[3] : o.fy; L2.push(o); };
  const N = S.npcs;
  // жители
  const npcSpot = (id, w, h, stand, extraTop) => { const n = N[id]; if (!n) return; const b = npcBox(n, w, h); if (extraTop) b[1] -= extraTop; add({ id: 'npc:' + id, who: id, hit: b, fx: n.x, fy: n.y, top: n.y - h, stand, act: () => talk(id) }); };
  const bub = (id) => (bubbleOf(id) ? 18 : 0);
  npcSpot('mole', 18, 22, K.moleStand, bub('mole'));
  npcSpot('sheep', 24, 18, K.sheepStand, bub('sheep'));
  npcSpot('frog', 16, 14, K.frogStand, bub('frog'));
  if (N.hedge) npcSpot('hedge', 19, 14, K.hedgeStand, bub('hedge'));
  if (N.cat) { const c = N.cat; if (c.roof) add({ id: 'npc:cat', who: 'cat', hit: [c.x - 4, c.y - 4, c.x + 20, c.y + 14], fx: c.x + 8, fy: K.house[1] + 67, top: c.y - 2, stand: K.door, reach: 60, act: () => talk('cat') });
    else npcSpot('cat', 15, 15, K.catStand, bub('cat')); }
  { const h = S.hens[1]; add({ id: 'npc:hen', who: 'hen', hit: [h.x - 8, h.y - 12 - bub('hen'), h.x + 8, h.y + 3], fx: h.x, fy: h.y, top: h.y - 10, stand: [h.x + (h.x > WW / 2 ? -10 : 10), h.y + 2], act: () => talk('hen') }); }
  { const h = S.hens[0]; add({ id: 'hen0', hit: [h.x - 8, h.y - 12, h.x + 8, h.y + 3], fx: h.x, fy: h.y, top: h.y - 10, stand: [h.x, h.y + 3], act: () => { snd.cluck(); say('hen', SAY.hen); feathers(h.x, h.y - 6); } }); }
  { const d = N.duck; add({ id: 'duck', hit: [d.x - 9, d.y - 12, d.x + 9, d.y + 3], fx: d.x, fy: d.y, top: d.y - 11, stand: K.pondTap, reach: 80, act: () => talk('duck') }); }
  // грядки
  S.carrots.forEach((c) => { if (c.gone) return; const x = BED.x + 3 + c.i * 9, y = BED.ys[0] - 2; add({ id: 'carrot' + c.i, hit: [x - 1, y - 2, x + 8, y + 11], fx: x + 3, fy: y + 8, top: y, stand: [x + 3, gapY(0)], act: () => pickCarrot(c) }); });
  for (let i = 0; i < 6; i++) { const x = BED.x + 2 + i * 12, y = BED.ys[1] + 1; add({ id: 'cab' + i, hit: [x - 1, y - 2, x + 11, y + 10], fx: x + 5, fy: y + 8, top: y, stand: [x + 5, gapY(1)], act: () => cabbage(i) }); }
  if (S.day === 3 && !S.pumpkinTaken) { const x = BED.x + 4, y = BED.ys[2] - 4; add({ id: 'pumpkin', hit: [x - 2, y - 2, x + 21, y + 17], fx: x + 9, fy: y + 15, top: y, stand: [x + 9, below3], act: pickPumpkin }); }
  if (S.day !== 3) { const x = BED.x + 2, y = BED.ys[2]; add({ id: 'pumpkins', hit: [x - 2, y - 2, x + 30, y + 12], fx: x + 14, fy: y + 10, top: y, stand: [x + 14, below3], act: () => think(SAY.pumpkinSmall) }); }
  { const x = BED.x + 40, y = BED.ys[2]; add({ id: 'sprouts', hit: [x - 3, y - 4, x + 38, y + 13], fx: x + 17, fy: y + 10, top: y - 2, stand: [x + 17, below3], act: water }); }
  // вещи
  { const [x, y] = K.mailbox; add({ id: 'mail', hit: [x - 3, y - 3, x + 14, y + 17], fx: x + 5, fy: y + 15, top: y, stand: K.mailStand, act: openMail }); }
  if (S.canHome) { const [x, y] = K.can; add({ id: 'can', hit: [x - 8, y - 11, x + 8, y + 3], fx: x, fy: y, top: y - 8, stand: [x, y + 3], act: takeCan }); }
  { const [x, y] = K.tree; add({ id: 'tree', hit: [x - 19, y - 45, x + 19, y + 2], fx: x, fy: y, top: y - 45, stand: K.treeStand, act: shakeTree }); }
  { const [cx, cy, rx, ry] = K.pond; add({ id: 'pond', hit: [cx - rx + 6, cy - ry + 4, cx + rx, cy + ry], fx: K.pondTap[0], fy: K.pondTap[1], top: cy - ry, stand: null, near: (x, y) => ((x - cx) / (rx + 12)) ** 2 + ((y - cy) / (ry + 10)) ** 2 <= 1, act: pond, area: 1e5 }); }
  add({ id: 'door', hit: K.doorHit, fx: K.door[0], fy: K.door[1] - 2, top: K.doorHit[1], stand: K.door, act: () => think(SAY.door) });
  if (K.scare) { const [x, y] = K.scare; add({ id: 'scare', hit: [x - 1, y - 1, x + 15, y + 26], fx: x + 7, fy: y + 25, top: y, stand: [x + 7, y + 31], act: () => think(SAY.scare) }); }
  if (S.bell) add({ id: 'bell', hit: [S.bell.x - 7, S.bell.y - 8, S.bell.x + 7, S.bell.y + 4], fx: S.bell.x, fy: S.bell.y, top: S.bell.y - 6, stand: [S.bell.x, S.bell.y + 2], act: pickBell });
  S.apples.forEach((a) => { if (a.st !== 'ground') return; add({ id: 'apple' + a.i, hit: [a.x - 6, a.y - 8, a.x + 6, a.y + 4], fx: a.x, fy: a.y, top: a.y - 6, stand: [a.x, a.y + 2], act: () => pickApple(a) }); });
  S.dands.forEach((d) => add({ id: 'dand' + d.i, hit: [d.x - 6, d.y - 10, d.x + 6, d.y + 4], fx: d.x, fy: d.y, top: d.y - 9, stand: [d.x, d.y + 2], act: () => pickDand(d) }));
  S.coinsW.forEach((c) => add({ id: 'coin' + c.i, hit: [c.x - 6, c.y - 7, c.x + 6, c.y + 4], fx: c.x, fy: c.y, top: c.y - 5, stand: [c.x, c.y], act: () => pickCoin(c) }));
  if (S.chick && S.chick.st === 'hide') { /* цыплёнок — в капусте, место — кочан */ }
  S.spots = L2;
}
const spotById = (id) => S.spots.find((s) => s.id === id);

/* ---------------- действия ---------------- */
function give(item, n, wx, wy) {
  S.inv[item] = have(item) + n;
  const keys = Object.keys(S.inv), i = keys.indexOf(item), [sx, sy] = slotXY(i);
  S.flyers.push({ icon: item === 'can' && S.canFull ? 'canFull' : item, x0: wx * PX, y0: wy * PX, x1: sx, y1: sy, t: 0, dur: .55, end: () => { S.slotPop[item] = .35; } });
  snd.pick();
  const t = S.tasks.find((t) => t.item === item && !t.done); if (t) t.flash = 1;
}
function addCoins(n, wx, wy, label) {
  S.coins += n; S.dayCoins += n;
  const [px, py] = UI.purseCoin;
  for (let k = 0; k < Math.min(5, Math.ceil(n / 3)); k++) S.flyers.push({ icon: 'coin', x0: wx * PX + (Math.random() - .5) * 30, y0: wy * PX, x1: px, y1: py, t: -k * .07, dur: .6, end: () => { S.slotPop.coin = .3; } });
  S.pops.push({ n, tag: label || '', t: 0, life: 1.6 });
  snd.coin();
}
function talk(id) {
  const n = S.npcs[id]; if (!n) return;
  if (id !== 'cat' || !n.sleep) n.hop = 1;
  if (CALL[id]) snd[CALL[id]]();
  if (id === 'hen') feathers(n.ref.x, n.ref.y - 6);
  if (id === 'frog' && S.day === 2 && !S.fishGiven) {
    const ft = S.tasks.find((t) => t.id === 'fish');
    if (ft && !ft.done) { S.fishGiven = true; give('fish', 1, n.x, n.y - 10); say('frog', L.frog.give); return; }
  }
  if (id === 'cat' && n.sleep) { say('cat', L.cat.sleep); return; }
  const t = taskOf(id);
  if (t) { if (ready(t)) complete(t); else { say(id, t.asked && L[id][t.id + '2'] ? L[id][t.id + '2'] : L[id][t.id]); t.asked = true; } return; }
  say(id, A.pick(L[id].idle));
}
function complete(t) {
  t.done = true; t.flash = 1;
  if (t.item) { S.inv[t.item] -= t.n; if (S.inv[t.item] <= 0) delete S.inv[t.item]; }
  if (t.id === 'water') { delete S.inv.can; S.canFull = false; }
  const n = S.npcs[t.who], bx = t.who === 'hen' ? n.ref.x : n.x, by = t.who === 'hen' ? n.ref.y : n.y;
  n.hop = 1.2; n.happy = 3.2;
  const quick = S.clock < .5;
  addCoins(quick ? 15 : 10, bx, by - 26, quick ? 'быстро!' : '');
  S.hearts++; S.dayHearts++; S.slotPop.heart = .4;
  for (let k = 0; k < 6; k++) S.parts.push({ k: 'heart', x: bx + (Math.random() - .5) * 14, y: by - 14, vx: (Math.random() - .5) * 14, vy: -18 - Math.random() * 16, g: 0, life: 1.4, max: 1.4 });
  snd.thanks();
  if (t.id === 'bell') { S.sheepBell = true; snd.bell(); }
  if (t.id === 'hook') S.frogHook = true;
  if (t.id === 'chick') S.chick.st = 'toHen';
  if (t.id === 'fish') setTimeout(() => { if (S.npcs.cat) S.npcs.cat.sleep = true; }, 3500);
  if (t.id === 'apples') S.hedgeApple = true;
  if (t.id === 'wreath') S.sheepWreath = true;
  if (t.id === 'pumpkin') S.pumpkinAtMole = true;
  say(t.who, L[t.who][t.id + 'Done']);
  if (S.tasks.every((q) => q.done)) S.endT = 3.4;
}
function pickCarrot(c) {
  if (!c.ripe) return think(SAY.carrotLater);
  const t = S.tasks.find((q) => q.id === 'carrots');
  if (!t || t.done) return think(SAY.carrotLater);
  if (have('carrot') >= 3) return think(SAY.carrotEnough);
  c.gone = true; const x = BED.x + 6 + c.i * 9, y = BED.ys[0] + 2;
  dirt(x, y); give('carrot', 1, x, y);
}
function cabbage(i) {
  const x = BED.x + 7 + i * 12, y = BED.ys[1] + 5;
  for (let k = 0; k < 5; k++) S.parts.push({ k: 'leaf', x, y: y - 2, vx: (Math.random() - .5) * 30, vy: -20 - Math.random() * 20, g: 60, life: .8, max: .8 });
  snd.rustle(); S.cabShake = { i, t: .5 };
  if (S.chick && S.chick.st === 'hide' && i === S.chickIn) {
    S.chick.st = 'follow'; S.chick.x = x; S.chick.y = y + 6; S.inv.chick = 1; S.slotPop.chick = .35;
    const t = S.tasks.find((q) => q.id === 'chick'); if (t) t.flash = 1;
    snd.peep(); say('hero', SAY.chickFound); return;
  }
  think(S.day === 2 && S.chick && S.chick.st === 'hide' ? A.pick(SAY.cabbage) : SAY.cabbageNo);
}
function pickPumpkin() {
  if (S.pumpkinTaken) return;
  S.pumpkinTaken = true; dirt(BED.x + 12, BED.ys[2] + 8); give('pumpkin', 1, BED.x + 12, BED.ys[2]); think(SAY.pumpkinTake); snd.thud();
}
function water() {
  if (S.day === 3 || S.watered) return think(SAY.flowers);
  if (S.day === 1) return think(SAY.sprouts);
  if (!have('can')) return think(SAY.sproutsNoCan);
  if (!S.canFull) return think(SAY.sproutsEmpty);
  S.canFull = false; S.watered = true; S.growT = 0; snd.pour();
  const x = BED.x + 40, y = BED.ys[2];
  for (let k = 0; k < 26; k++) S.parts.push({ k: 'drop', x: x + Math.random() * 34, y: y - 10 - Math.random() * 6, vx: 0, vy: 30 + Math.random() * 30, g: 60, life: .5 + Math.random() * .4, max: .9 });
  const t = S.tasks.find((q) => q.id === 'water'); if (t) t.flash = 1;
  setTimeout(() => think(SAY.sproutsDone), 600);
}
function takeCan() {
  if (S.day !== 2 || S.watered) return think(SAY.canNo);
  S.canHome = false; give('can', 1, K.can[0], K.can[1] - 4); think(SAY.canTake);
  const t = S.tasks.find((q) => q.id === 'water'); if (t) t.flash = 1;
}
function pond() {
  if (have('can') && !S.canFull) {
    S.canFull = true; snd.splash(); ring(S.hero.x + (S.hero.flip ? -10 : 10), S.hero.y + 2);
    S.slotPop.can = .35; const t = S.tasks.find((q) => q.id === 'water'); if (t) t.flash = 1;
    return think(SAY.pondFill);
  }
  if (have('can')) return think(SAY.pondFull);
  ring(K.pondTap[0] + 8, K.pondTap[1] + 6); snd.splash(); think(SAY.pondNo);
}
function openMail() {
  snd.creak(); S.mailOpen = .8;
  const m = S.mail; S.mail = null;
  const [x, y] = K.mailbox;
  if (m === 'hook') { give('hook', 1, x + 5, y + 2); think(SAY.mailHook); }
  else if (m === 'letter') { addCoins(5, x + 5, y); think(SAY.mailLetter); }
  else if (m === 'card') { addCoins(5, x + 5, y); think(SAY.mailCard); }
  else think(SAY.mailEmpty);
}
function shakeTree() {
  S.treeShake = .7; snd.rustle();
  const [x, y] = K.tree;
  for (let k = 0; k < 8; k++) S.parts.push({ k: 'leaf', x: x + (Math.random() - .5) * 26, y: y - 30 + Math.random() * 12, vx: (Math.random() - .5) * 20, vy: 5 + Math.random() * 15, g: 20, life: 1.4, max: 1.4 });
  if (S.day !== 3) return think(SAY.treeGreen);
  if (S.applesDown) return think(SAY.treeShaken);
  S.applesDown = true;
  S.apples.forEach((a, i) => { a.st = 'fall'; a.x = x + a.dx; a.y = y - 27 + a.dy; a.vy = -20 - i * 6; });
  think(SAY.treeShake);
}
function pickApple(a) {
  const t = S.tasks.find((q) => q.id === 'apples');
  if (have('apple') >= 2 || !t || t.done) return think(SAY.appleEnough);
  a.st = 'got'; give('apple', 1, a.x, a.y - 3);
}
function pickDand(d) {
  const t = S.tasks.find((q) => q.id === 'wreath');
  if (have('dand') >= 3 || !t || t.done) return think(SAY.dandEnough);
  S.dands = S.dands.filter((q) => q !== d); give('dand', 1, d.x, d.y - 5);
  for (let k = 0; k < 6; k++) S.parts.push({ k: 'fluff', x: d.x, y: d.y - 6, vx: 6 + Math.random() * 14, vy: -6 - Math.random() * 10, g: -2, life: 2.2, max: 2.2 });
}
function pickBell() { const b = S.bell; S.bell = null; give('bell', 1, b.x, b.y - 2); snd.bell(); think(SAY.bellFound); }
function pickCoin(c) { S.coinsW = S.coinsW.filter((q) => q !== c); addCoins(3, c.x, c.y - 4); for (let k = 0; k < 6; k++) S.parts.push({ k: 'spark', x: c.x, y: c.y - 3, vx: (Math.random() - .5) * 40, vy: -Math.random() * 30, g: 40, life: .5, max: .5 }); }
function dirt(x, y) { for (let k = 0; k < 6; k++) S.parts.push({ k: 'dirt', x, y, vx: (Math.random() - .5) * 30, vy: -25 - Math.random() * 20, g: 120, life: .6, max: .6 }); }
function feathers(x, y) { for (let k = 0; k < 4; k++) S.parts.push({ k: 'feather', x, y, vx: (Math.random() - .5) * 26, vy: -14 - Math.random() * 10, g: 14, life: 1.2, max: 1.2 }); }
function ring(x, y) { S.rings.push({ x, y, t: 0 }); }

/* ---------------- Тиша идёт ---------------- */
function goTo(x, y, spotId) {
  const h = S.hero, p = findPath(h.x, h.y, x, y);
  if (!p) { h.path = null; h.pending = null; snd.nope(); return false; }
  h.path = p; h.pending = spotId || null;
  if (!spotId) S.dest = { x: p[p.length - 1][0], y: p[p.length - 1][1], t: 0 };
  return true;
}
function inReach(s) {
  const h = S.hero;
  if (s.near) return s.near(h.x, h.y);
  if (s.stand && dist(h.x, h.y, s.stand[0], s.stand[1]) <= 9) return true;
  return dist(h.x, h.y, s.fx, s.fy) <= (s.reach || 20);
}
function face(s) { const h = S.hero, dx = s.fx - h.x, dy = s.fy - h.y; if (Math.abs(dx) > Math.abs(dy) * .8) { h.dir = 'side'; h.flip = dx < 0; } else h.dir = dy < 0 ? 'up' : 'down'; }
function activate(s) {
  S.idle = 0; S.mark = null;
  if (inReach(s)) { face(s); s.act(); return; }
  const st = s.stand || nearestShore(s);
  if (!goTo(st[0], st[1], s.id)) think(SAY.noWay);
}
function nearestShore() { return K.pondTap; }
function arrive() {
  const h = S.hero; h.path = null;
  if (!h.pending) return;
  buildSpots();
  const s = spotById(h.pending); h.pending = null;
  if (!s) return;
  if (inReach(s) || (s.stand && dist(h.x, h.y, s.stand[0], s.stand[1]) <= 16)) { face(s); s.act(); }
  else think(SAY.far);
}
function nearestSpot() {
  const h = S.hero; let best = null, bd = 1e9;
  for (const s of S.spots) { if (!inReach(s)) continue; const d = s.near ? 30 : dist(h.x, h.y, s.fx, s.fy) - (s.id.startsWith('npc:') ? 10 : 0) + (s.id === 'hen0' || s.id === 'duck' || s.id === 'door' || s.id === 'scare' ? 10 : 0); if (d < bd) { bd = d; best = s; } }
  return best;
}

/* ---------------- подсказки ---------------- */
function nearestId(prefix) {
  const h = S.hero; let best = null, bd = 1e9;
  for (const s of S.spots) if (s.id.startsWith(prefix)) { const d = dist(h.x, h.y, s.fx, s.fy); if (d < bd) { bd = d; best = s.id; } }
  return best;
}
const HINT = {
  carrots: () => (have('carrot') >= 3 ? ['Морковки в корзинке — отнеси их бабушке Крот.', 'npc:mole'] : ['Морковки растут на верхней грядке. Нажми на морковку.', nearestCarrot()]),
  bell: () => (have('bell') ? ['Отнеси колокольчик барашку Пуху.', 'npc:sheep'] : ['Колокольчик блестит где-то в траве — ищи искорки.', 'bell']),
  hook: () => (have('hook') ? ['Отнеси крючок лягушонку Кваку на мостки.', 'npc:frog'] : ['Посылки приходят в почтовый ящик у дома.', 'mail']),
  chick: () => (have('chick') ? ['Цыплёнок топает за тобой! Веди его к курочке Рябе.', 'npc:hen'] : ['Ищи цыплёнка в капусте — один кочан шевелится.', 'cab' + S.chickIn]),
  water: () => (S.watered ? ['Расскажи бабушке Крот, что ростки политы.', 'npc:mole'] : !have('can') ? ['Лейка стоит у крыльца — возьми её.', 'can'] : !S.canFull ? ['Набери воды в пруду.', 'pond'] : ['Полей ростки на нижней грядке.', 'sprouts']),
  fish: () => (have('fish') ? ['Отнеси рыбку коту Рыжику.', 'npc:cat'] : ['Рыбку можно попросить у Квака на мостках.', 'npc:frog']),
  apples: () => (have('apple') >= 2 ? ['Отнеси яблоки ёжику Колючке.', 'npc:hedge'] : S.applesDown ? ['Подбери яблоки под яблоней.', nearestId('apple')] : ['Потряси яблоню — нажми на неё.', 'tree']),
  wreath: () => (have('dand') >= 3 ? ['Отнеси одуванчики Пуху.', 'npc:sheep'] : ['Одуванчики белеют на лугу — собери три.', nearestId('dand')]),
  pumpkin: () => (have('pumpkin') ? ['Неси тыкву бабушке Крот.', 'npc:mole'] : ['Самая большая тыква — на нижней грядке.', 'pumpkin']),
};
function nearestCarrot() { const h = S.hero; let best = null, bd = 1e9; S.carrots.forEach((c) => { if (c.gone || !c.ripe) return; const d = dist(h.x, h.y, BED.x + 6 + c.i * 9, BED.ys[0]); if (d < bd) { bd = d; best = 'carrot' + c.i; } }); return best; }
function hint() {
  for (const t of S.tasks) if (!t.done) { const [text, id] = HINT[t.id](); return { text, id }; }
  return { text: SAY.allDone, id: null };
}
function showHint() { const h = hint(); think(h.text); S.mark = h.id ? { id: h.id, t: 0 } : null; S.idle = 0; }
/* для самопроверки: куда нажать, чтобы сделать следующий шаг */
function target() {
  if (S.mode === 'fest') { if (S.festT < 2.6 || S.fade > .05) return null; const [x, y, w, h] = nextRect(); return { x: x + w / 2, y: y + h / 2, id: 'next' }; }
  if (S.mode !== 'play') return null;
  const h = hint(); if (!h.id) return null;
  const s = spotById(h.id); if (!s) return null;
  if (s.id === 'pond') return { x: K.pondTap[0] * PX + 20, y: K.pondTap[1] * PX + 16, id: s.id };
  return { x: (s.hit[0] + s.hit[2]) / 2 * PX, y: (Math.max(s.hit[1], s.fy - 12) + s.hit[3]) / 2 * PX, id: s.id };
}
function busy() { return S.mode !== 'play' || !!S.hero.path || !!S.hero.pending || S.fade > .02 || S.fadeTo > 0 || S.endT > 0; }

/* ---------------- день: начало и конец ---------------- */
function beginDay(d) {
  setupDay(d); buildSpots();
  S.mode = 'play'; S.fade = 1; S.fadeTo = 0;
  S.banner = { t: 0, title: 'День ' + d, sub: DAYS[d - 1].name };
  S.introT = 1.6;
  GAME.setPlaying(true); GAME.playMusic(); GAME.fx.clear();
  setTimeout(() => snd.rooster(), 500);
}
function startDusk(all) {
  if (S.mode !== 'play') return;
  S.mode = 'dusk'; S.duskT = 0; S.duskAll = all; S.mark = null; S.duskClock = S.clock;
  const h = S.hero; h.pending = null;
  if (S.day < 3) { say('hero', all ? SAY.duskAll : SAY.dusk); goTo(K.door[0], K.door[1]); S.dest = null; }
  else { say('hero', SAY.fest); h.path = null; }
}
function endDayScreen() {
  const g = GAME; S.mode = 'night'; g.setPlaying(false); g.stopMusic();
  const d = S.day, done = S.tasks.filter((t) => t.done).length;
  const rows = S.tasks.map((t) => `<li style="list-style:none;margin:2px 0">${t.done ? '✓' : '·'} ${t.text}</li>`).join('');
  g.screen({
    kicker: 'День ' + d + ' позади', title: done === 3 ? 'Все довольны!' : 'Вот и вечер',
    html: `<ul style="padding:0;margin:0 0 8px;font-size:16px">${rows}</ul><p>Монетки за день: <b>+${S.dayCoins}</b> · сердечки: <b>+${S.dayHearts}</b></p><p style="opacity:.8">${DAYS[d - 1].next}</p>`,
    button: 'Утро дня ' + (d + 1), keys: '', onGo: () => beginDay(d + 1)
  });
}
function finalScreen() {
  const g = GAME; S.mode = 'end'; g.setPlaying(false); g.stopMusic();
  document.body.classList.add('farm-final');          // карточка — к верху поля: праздник остаётся виден
  const rec = g.submit(S.coins), h = S.hearts;
  const line = h >= 9 ? 'Тиша помог всем соседям — все девять поручений!' : h >= 6 ? 'Тиша помог соседям ' + h + ' раз из девяти. Хутор доволен!' : 'Тиша помог соседям ' + h + ' раз из девяти. Завтра — новый день!';
  g.screen({
    kicker: 'Праздник урожая', title: 'Хутор сияет!',
    html: `<p>${line}</p><p class="score">${S.coins}</p><p>${rec ? '<span class="record">новый рекорд монеток!</span>' : 'монеток' + (g.best ? ' · рекорд ' + g.best : '')}</p>`,
    button: 'Ещё раз', keys: '', onGo: () => { document.body.classList.remove('farm-final'); fresh(); beginDay(1); }, alt: { label: A.framed ? 'К играм' : 'В аркаду', onGo: () => A.home('../index.html') }
  });
}
function festSetup() {
  const F = K.fest, N = S.npcs;
  for (const id of ['mole', 'cat', 'frog', 'sheep', 'hedge']) if (N[id] && F[id]) { N[id].x = F[id][0]; N[id].y = F[id][1]; N[id].sleep = false; N[id].sit = true; N[id].roof = false; N[id].flip = N[id].x > K.table[0]; }
  if (N.hedge) N.hedge.flip = false;
  S.hens[1].x = F.hen[0]; S.hens[1].y = F.hen[1]; S.hens[0].x = F.hen2[0]; S.hens[0].y = F.hen2[1];
  if (S.chick) { S.chick.x = F.hen[0] + 8; S.chick.y = F.hen[1] + 4; S.chick.st = 'withHen'; }
  S.hero.x = F.hero[0]; S.hero.y = F.hero[1]; S.hero.dir = 'up'; S.hero.path = null; S.carryShow = false;
  S.fest = true; S.festT = 0; S.clock = 1; S.eve = .72;
  S.banner = { t: .2, title: 'Праздник урожая', sub: 'Все соседи в сборе', line: 'Спасибо, Тиша!' };
}

/* ---------------- обновление ---------------- */
function input(g) {
  const inp = g.input, h = S.hero;
  if (S.mode === 'fest') {                    // праздник стоит, пока не нажмут «Дальше»
    if (S.festT > 2.5 && S.fade < .05 && (inp.tap || inp.pressed('action') || inp.pressed('start'))) { S.mode = 'endwait'; snd.pick(); finalScreen(); }
    return;
  }
  if (S.mode !== 'play' || S.fade > .3) return;
  let vx = (inp.down('right') ? 1 : 0) - (inp.down('left') ? 1 : 0), vy = (inp.down('down') ? 1 : 0) - (inp.down('up') ? 1 : 0);
  const p = inp.pointer;
  if (p.justDown) h.hold = !uiHit(p.x, p.y);
  if (!p.down) h.hold = false;
  if (!vx && !vy && p.down && h.hold && performance.now() - p.t0 > 300) {        // долгое касание — Тиша идёт за пальцем
    const dx = p.x / PX - h.x, dy = p.y / PX - (h.y - 8); if (Math.hypot(dx, dy) > 6) { vx = dx; vy = dy; }
  }
  if (vx || vy) {
    const l = Math.hypot(vx, vy), sp = (have('pumpkin') ? 38 : 48) / 60 * S.speed; h.path = null; h.pending = null; S.dest = null;
    const nx = h.x + vx / l * sp, ny = h.y + vy / l * sp;
    if (walkAt(nx, h.y)) h.x = nx; if (walkAt(h.x, ny)) h.y = ny;
    setDir(vx, vy); h.moving = true; h.kbMove = true; S.idle = 0; S.kb = !p.down; S.mark = null;
  } else h.kbMove = false;
  if (inp.pressed('action') || inp.pressed('start')) {
    S.kb = true; S.idle = 0;
    const s = nearestSpot();
    if (s) { h.path = null; face(s); s.act(); } else { snd.nope(); think(A.isTouch ? SAY.far : SAY.farKb); }
  }
  if (inp.tap) {
    const { x, y } = inp.tap; S.idle = 0; S.kb = false;
    const u = uiHit(x, y);
    if (u === 'help') { showHint(); return; }
    if (u) return;
    const wx = x / PX, wy = y / PX, pad = A.isTouch ? 4 : 1;
    const hits = S.spots.filter((s) => wx >= s.hit[0] - pad && wx <= s.hit[2] + pad && wy >= s.hit[1] - pad && wy <= s.hit[3] + pad);
    hits.sort((a, b) => area(a) - area(b));
    if (hits.length) activate(hits[0]);
    else { S.mark = null; if (!goTo(wx, wy)) think(SAY.noWay); }
  }
}
const area = (s) => s.area || (s.hit[2] - s.hit[0]) * (s.hit[3] - s.hit[1]);
function setDir(dx, dy) { const h = S.hero; if (Math.abs(dx) >= Math.abs(dy) * .9) { h.dir = 'side'; h.flip = dx < 0; } else h.dir = dy < 0 ? 'up' : 'down'; }

function step(dt) {
  S.t += dt;
  const h = S.hero;
  // затемнение
  if (S.fade !== S.fadeTo) { S.fade = S.fade < S.fadeTo ? Math.min(S.fadeTo, S.fade + dt * 1.6) : Math.max(S.fadeTo, S.fade - dt * 1.6); if (S.fade === S.fadeTo && S.fadeThen) { const f = S.fadeThen; S.fadeThen = null; f(); } }
  if (S.banner) { S.banner.t += dt; if (S.banner.t > 3.4) S.banner = null; }
  if (S.cap) { S.cap.t += dt; const n = Math.floor(S.cap.t * 55); if (n > S.cap.typed && n <= S.cap.text.length) { if ((n >> 2) !== (S.cap.typed >> 2) && S.cap.who !== 'hero') snd.blip(S.cap.who); S.cap.typed = n; } if (S.cap.t > S.cap.life) S.cap = null; }
  if (S.mark) { S.mark.t += dt; if (S.mark.t > 7) S.mark = null; }
  if (S.dest) { S.dest.t += dt; if (S.dest.t > .6 || !h.path) S.dest = null; }
  for (const k in S.slotPop) { S.slotPop[k] -= dt; if (S.slotPop[k] <= 0) delete S.slotPop[k]; }
  S.tasks.forEach((t) => { if (t.flash > 0) t.flash -= dt * .8; });
  if (S.mailOpen > 0) S.mailOpen -= dt;
  if (S.treeShake > 0) S.treeShake -= dt;
  if (S.cabShake) { S.cabShake.t -= dt; if (S.cabShake.t <= 0) S.cabShake = null; }
  // часы
  if (S.mode === 'play') {
    if (S.introT > 0) { S.introT -= dt; if (S.introT <= 0) say('hero', SAY['start' + S.day], S.day === 1 ? 2 : 0); }
    S.clock += dt / DAY_LEN; S.idle += dt;
    if (S.clock >= 1) { S.clock = 1; startDusk(false); }
    if (S.endT > 0) { S.endT -= dt; if (S.endT <= 0) startDusk(true); }
    if (S.idle > 14 && !S.cap && !h.path) { showHint(); S.idle = 0; }
  } else if (S.mode === 'dusk') {
    S.duskT += dt;
    S.clock = Math.min(1, S.clock + dt * .3);
    if (S.clock >= 1) S.eve = Math.min(1, S.eve + dt * .45);
    if (S.day < 3) {
      if (S.eve > .6 && !h.path && h.alpha > 0) h.alpha = Math.max(0, h.alpha - dt * 2);
      if ((S.eve >= 1 && h.alpha <= 0) || S.duskT > 12) { h.alpha = 0; S.mode = 'nightwait'; setTimeout(() => { if (S.mode === 'nightwait') { snd.evening(); endDayScreen(); } }, 700); }
    } else if (S.duskT > 2.2 && !S.fadeThen && !S.fest) {
      S.fadeTo = 1; S.fadeThen = () => { festSetup(); S.mode = 'fest'; S.fadeTo = 0; GAME.stopMusic(); setTimeout(() => SND.play('win'), 500); };
    }
  } else if (S.mode === 'fest') {
    S.festT += dt;
    if (Math.random() < dt * 3) S.parts.push({ k: 'fluff', x: Math.random() * WW, y: WH * (.3 + Math.random() * .6), vx: 6 + Math.random() * 10, vy: -4 - Math.random() * 6, g: -1, life: 3, max: 3 });
    /* праздник стоит, пока игрок не нажмёт «Дальше» (input) */
  }
  // герой
  const sp = (have('pumpkin') ? 38 : 48) * dt;
  if (h.path && h.path.length) {
    const [tx, ty] = h.path[0], dx = tx - h.x, dy = ty - h.y, d = Math.hypot(dx, dy);
    if (d <= sp) { h.x = tx; h.y = ty; h.path.shift(); } else { h.x += dx / d * sp; h.y += dy / d * sp; }
    setDir(dx, dy); h.moving = true;
    if (!h.path.length) { h.path = null; h.moving = false; arrive(); }
  } else if (!h.kbMove) h.moving = false;
  if (h.moving) { h.ph += dt * 9; h.stepT -= dt; if (h.stepT <= 0) { h.stepT = .28; snd.step(); } h.trail.push([h.x, h.y]); if (h.trail.length > 40) h.trail.shift(); }
  h.blink -= dt; if (h.blink < -.13) h.blink = 2 + Math.random() * 3.5;
  if (h.think > 0) h.think -= dt;
  // монетки подбираются на ходу
  if (S.mode === 'play') for (const c of S.coinsW.slice()) if (dist(h.x, h.y, c.x, c.y) < 7) pickCoin(c);
  // жители
  for (const id in S.npcs) { const n = S.npcs[id]; if (n.hop > 0) n.hop = Math.max(0, n.hop - dt * 1.6); if (n.happy > 0) { n.happy -= dt; if (Math.random() < dt * 2.5) S.parts.push({ k: 'heart', x: (n.ref ? n.ref.x : n.x) + (Math.random() - .5) * 10, y: (n.ref ? n.ref.y : n.y) - 18, vx: 0, vy: -16, g: 0, life: 1.2, max: 1.2 }); }
    n.blink -= dt; if (n.blink < -.14) n.blink = 2 + Math.random() * 4; }
  const du = S.npcs.duck; du.a += dt * .22; const nx = K.duck[0] + Math.cos(du.a) * K.duck[2], ny = K.duck[1] + Math.sin(du.a) * K.duck[3]; du.flip = nx < du.x; du.x = nx; du.y = ny;
  if (Math.random() < dt * .4) ring(du.x - (du.flip ? -6 : 6), du.y + 1);
  // курочки
  const [ax0, ay0, ax1, ay1] = K.henArea;
  S.hens.forEach((e, i) => {
    if (S.fest) { e.peck = (S.t * 2 + i) % 3 < .4 ? 1 : 0; return; }
    if (e.ryaba && S.day === 2 && !S.tasks[0].done) { e.flip = S.t % 3 < 1.5; e.peck = 0; return; }       // Ряба волнуется: крутит головой
    e.t -= dt;
    if (e.t <= 0) { e.t = 1.5 + Math.random() * 3; e.tx = ax0 + Math.random() * (ax1 - ax0); e.ty = ay0 + Math.random() * (ay1 - ay0); e.peckT = Math.random() < .5 ? 1.2 : 0; }
    if (e.peckT > 0) { e.peckT -= dt; e.peck = (e.peckT * 6 | 0) % 2; return; }
    e.peck = 0; const dx = e.tx - e.x, dy = e.ty - e.y, d = Math.hypot(dx, dy);
    if (d > 1) { e.x += dx / d * 12 * dt; e.y += dy / d * 12 * dt; e.flip = dx < 0; }
  });
  S.npcs.hen.x = S.hens[1].x; S.npcs.hen.y = S.hens[1].y;
  // цыплёнок
  const ch = S.chick;
  if (ch) {
    ch.ph += dt;
    let tx = null, ty = null;
    if (ch.st === 'follow') { const tr = h.trail, p = tr.length > 14 ? tr[tr.length - 14] : [h.x - 8, h.y + 2]; tx = p[0]; ty = p[1] + 1; }
    else if (ch.st === 'toHen' || ch.st === 'withHen') { const hn = S.hens[1]; tx = hn.x + (hn.flip ? 9 : -9); ty = hn.y + 2; if (ch.st === 'toHen' && dist(ch.x, ch.y, tx, ty) < 2) ch.st = 'withHen'; }
    if (tx != null) { const dx = tx - ch.x, dy = ty - ch.y, d = Math.hypot(dx, dy), v = ch.st === 'withHen' ? 14 : 62; if (d > 1.5) { ch.x += dx / d * Math.min(d, v * dt); ch.y += dy / d * Math.min(d, v * dt); ch.flip = dx < 0; ch.walk = true; } else ch.walk = false; }
    if (ch.st === 'hide' && Math.random() < dt * .25) S.cabWiggle = .5;
  }
  if (S.cabWiggle > 0) S.cabWiggle -= dt;
  // яблоки падают
  for (const a of S.apples) if (a.st === 'fall') { a.vy += 260 * dt; a.y += a.vy * dt; a.x = lerp(a.x, a.gx, dt * 3); if (a.y >= a.gy) { a.y = a.gy; a.x = a.gx; if (a.vy > 60) { a.vy = -a.vy * .3; snd.thud(); } else { a.st = 'ground'; a.vy = 0; } } }
  // дым из трубы, кольца на воде, частицы
  if (Math.random() < dt * 1.6) S.smoke.push({ x: K.house[0] + 62, y: K.house[1] + 2, t: 0, r: 2 });
  S.smoke.forEach((p) => { p.t += dt; p.y -= dt * 6; p.x += dt * 5 + Math.sin(S.t + p.t) * dt * 2; p.r = 2 + p.t * 1.1; }); S.smoke = S.smoke.filter((p) => p.t < 3);
  S.rings.forEach((r) => { r.t += dt; }); S.rings = S.rings.filter((r) => r.t < 1.4);
  S.parts.forEach((p) => { p.life -= dt; p.vy += (p.g || 0) * dt; p.x += p.vx * dt; p.y += p.vy * dt; if (p.k === 'fluff' || p.k === 'feather' || p.k === 'leaf') p.vx += Math.sin(S.t * 2 + p.y) * 8 * dt; });
  S.parts = S.parts.filter((p) => p.life > 0);
  S.pops.forEach((p) => { p.t += dt; }); S.pops = S.pops.filter((p) => p.t < p.life);
  S.flyers.forEach((f) => { f.t += dt; if (f.t >= f.dur && !f.done) { f.done = true; if (f.end) f.end(); } }); S.flyers = S.flyers.filter((f) => !f.done);
  if (S.mode === 'play' && S.growT != null) S.growT += dt;
  // птички днём
  S.birdT -= dt; if (S.birdT <= 0) { S.birdT = 4 + Math.random() * 6; if (S.eve < .3 && S.mode !== 'title') snd.birds(); }
  // колокольчик барашка иногда звенит
  if (S.sheepBell && S.mode === 'play' && Math.random() < dt * .12) { const n = S.npcs.sheep; S.parts.push({ k: 'note', x: n.x - 6, y: n.y - 14, vx: -4, vy: -12, g: 0, life: 1.4, max: 1.4 }); }
  buildSpots();
}
function update(g, dt) {
  if (!S) return;
  if (S.mode === 'title') { step(dt); return; }
  input(g);
  const n = Math.max(1, Math.round(S.speed || 1));
  for (let i = 0; i < n; i++) step(dt);
}

/* ---------------- рисование мира ---------------- */
function spr(cv, x, y, flip) {
  x = Math.round(x); y = Math.round(y);
  if (flip) { WX.save(); WX.translate(x + cv.width, y); WX.scale(-1, 1); WX.drawImage(cv, 0, 0); WX.restore(); } else WX.drawImage(cv, x, y);
}
function shadow(x, y, rx, ry) { WX.drawImage(shadowCv(rx, ry), Math.round(x - rx - 1), Math.round(y - ry - 1)); }
const hopY = (n) => (n.hop > 0 ? -Math.round(Math.abs(Math.sin(n.hop * Math.PI * 2)) * 3) : 0);
function renderWorld() {
  const w = WX;
  w.globalCompositeOperation = 'source-over'; w.globalAlpha = 1;
  w.drawImage(BG, 0, 0);
  // вода живёт
  const [pcx, pcy, prx, pry] = K.pond;
  w.fillStyle = C.w0;
  for (let i = 0; i < 9; i++) { const yy = pcy - pry * .6 + i * pry * .14, xx = pcx - prx * .55 + ((i * 37) % 60) / 60 * prx * 1.1 + Math.sin(S.t * .7 + i) * 3, l = 3 + (i % 3) * 2;
    if (((xx - pcx) / prx) ** 2 + ((yy - pcy) / pry) ** 2 < .8) w.fillRect(Math.round(xx), Math.round(yy), l, 1); }
  w.fillStyle = 'rgba(220,245,255,.8)';
  for (const r of S.rings) { const k = r.t / 1.4, rx = 2 + k * 9, ry = 1 + k * 3; w.globalAlpha = 1 - k; for (let a = 0; a < TAU; a += .35) w.fillRect(Math.round(r.x + Math.cos(a) * rx), Math.round(r.y + Math.sin(a) * ry), 1, 1); }
  w.globalAlpha = 1;
  const du = S.npcs.duck; spr(SP.duck, du.x - 7, du.y - 10 + Math.round(Math.sin(S.t * 2) * .6), du.flip); w.fillStyle = C.w0; w.fillRect(Math.round(du.x - 8), Math.round(du.y + 1), 16, 1);
  // удочка Квака
  const fr = S.npcs.frog;
  // всё по глубине
  const list = [];
  const add = (y, d) => list.push({ y, d });
  for (const p of PROPS) add(p.foot, () => w.drawImage(p.cv, p.x, p.y));
  // почтовый ящик
  { const [x, y] = K.mailbox; add(y + 15, () => { spr(SP.mail[S.mail ? 1 : 0], x, y - (S.mailOpen > 0 ? Math.round(Math.sin(S.mailOpen * 20) * .8) : 0));
    if (S.mail) { const k = (S.t * 1.3) % 3; if (k < .5) sparkle(x + 9, y - 2, k * 2); } }); }
  // лейка
  if (S.canHome) { const [x, y] = K.can; add(y, () => { shadow(x, y, 5, 1); spr(SP.can, x - 5, y - 8); }); }
  // яблоня
  { const [x, y] = K.tree, s = SP.appleTree, sh = S.treeShake > 0 ? Math.round(Math.sin(S.treeShake * 40)) : 0;
    add(y, () => { w.drawImage(s.cv, Math.round(x - s.w / 2) + sh, y - s.h + 1);
      S.apples.forEach((a) => { if (a.st === 'tree') { const ax = Math.round(x + a.dx) + sh, ay = y - 27 + a.dy; w.fillStyle = S.day === 3 ? C.r1 : '#a6d86f'; w.fillRect(ax, ay, 2, 2); w.fillStyle = S.day === 3 ? C.r0 : '#d6f0a0'; w.fillRect(ax, ay, 1, 1); w.fillStyle = S.day === 3 ? C.r3 : C.g4; w.fillRect(ax + 1, ay + 2, 1, 1); } }); }); }
  S.apples.forEach((a) => { if (a.st === 'fall' || a.st === 'ground') add(a.st === 'ground' ? a.y : a.gy, () => { if (a.st === 'ground') shadow(a.x, a.y, 3, 1); spr(ICON.apple.cv, a.x - 4, a.y - 7); }); });
  // грядки
  S.carrots.forEach((c) => { const x = BED.x + 3 + c.i * 9, y = BED.ys[0] - 2;
    if (c.gone) { add(y + 6, () => { w.fillStyle = C.s2; w.fillRect(x + 2, y + 5, 3, 1); w.fillRect(x + 3, y + 6, 1, 1); }); return; }
    add(y + 6, () => spr(SP.carrot[c.ripe ? 1 : 0], x, y + (c.ripe && S.mark && S.mark.id === 'carrot' + c.i ? Math.round(Math.sin(S.t * 10)) : 0))); });
  for (let i = 0; i < 6; i++) { const x = BED.x + 2 + i * 12, y = BED.ys[1] + 1, wig = (S.chick && S.chick.st === 'hide' && i === S.chickIn && S.cabWiggle > 0) || (S.cabShake && S.cabShake.i === i) ? Math.round(Math.sin(S.t * 40)) : 0;
    add(y + 7, () => spr(SP.cabbage, x + wig, y)); }
  if (S.day === 3) { if (!S.pumpkinTaken) add(BED.ys[2] + 11, () => spr(SP.giant, BED.x + 4, BED.ys[2] - 4)); }
  else { add(BED.ys[2] + 9, () => { spr(SP.pumpkin, BED.x + 2, BED.ys[2] - 1); spr(SP.pumpkin, BED.x + 17, BED.ys[2]); }); }
  { const gk = S.watered ? (S.growT != null ? clamp(S.growT / 1.2, 0, 1) : 1) : 0;
    add(BED.ys[2] + 8, () => { for (let i = 0; i < 6; i++) { const x = BED.x + 42 + i * 6, y = BED.ys[2] + 6;
      if (gk >= 1 || (gk > 0 && i / 6 < gk)) spr(SP.pea, x - 3, y - 7); else { w.fillStyle = C.g0; w.fillRect(x, y, 1, 1); w.fillRect(x + 1, y - 1, 1, 1); w.fillStyle = C.g1; w.fillRect(x - 1, y - 1, 1, 1); w.fillStyle = C.g2; w.fillRect(x, y + 1, 1, 1); } } }); }
  // вещи на земле
  if (S.bell) { const b = S.bell; add(b.y, () => { spr(ICON.bell.cv, b.x - 4, b.y - 8); w.fillStyle = C.g2; w.fillRect(b.x - 5, b.y - 2, 1, 2); w.fillRect(b.x + 4, b.y - 3, 1, 3); w.fillRect(b.x - 3, b.y - 1, 1, 1);
    const k = (S.t * 1.1) % 2.2; if (k < .6) sparkle(b.x + 3, b.y - 8, k / .6); }); }
  S.dands.forEach((d) => add(d.y, () => { spr(ICON.dand.cv, d.x - 4, d.y - 9 + Math.round(Math.sin(S.t * 1.5 + d.i) * .5)); }));
  S.coinsW.forEach((c) => add(c.y, () => { const k = (S.t * .9 + c.ph) % 3; spr(ICON.coin.cv, c.x - 3, c.y - 6 + (k < .3 ? -1 : 0)); if (k < .5) sparkle(c.x + 2, c.y - 6, k * 2); }));
  if (S.fest) { const [tx, ty] = K.table; add(ty, () => { shadow(tx, ty, 12, 2); spr(SP.table, tx - 13, ty - 15); }); }
  if (S.pumpkinAtMole && !S.fest) { const n = S.npcs.mole; add(n.y + 1, () => spr(SP.giant, n.x + 7, n.y - 13)); }
  if (S.pumpkinAtMole && S.fest) { const [tx, ty] = K.table; add(ty - 12, () => spr(SP.giant, tx - 9, ty - 26)); }
  // жители
  const N = S.npcs;
  { const n = N.mole; add(n.y, () => { shadow(n.x, n.y, 8, 2); spr(SP.mole, n.x - 9, n.y - 21 + hopY(n) + (S.t % 2.4 < 1.2 ? 0 : 0)); }); }
  { const n = N.sheep; add(n.y, () => { shadow(n.x, n.y + 1, 10, 2); spr(SP.sheep[(S.sheepBell ? 1 : 0) + '' + (S.sheepWreath ? 1 : 0) + (n.blink < 0 ? 1 : 0)], n.x - 12, n.y - 17 + hopY(n), n.flip); }); }
  { const n = fr; add(n.y, () => { spr(SP.frog[n.blink < 0 ? 1 : 0], n.x - 8, n.y - 13 + hopY(n));
    // удочка: тянется над водой; с крючком — леска и поплавок
    if (!S.fest) { w.fillStyle = C.wd2; for (let i = 0; i < 16; i++) w.fillRect(Math.round(n.x + 5 + i), Math.round(n.y - 6 - i * .7), 1, 1); }
    const ex = Math.round(n.x + 21), ey = Math.round(n.y - 17);
    if (S.fest) { /* на празднике Квак без удочки */ }
    else if (S.frogHook) { const by = Math.round(n.y + 3 + Math.sin(S.t * 2.2)); w.fillStyle = 'rgba(255,255,255,.7)'; for (let y = ey; y < by; y++) w.fillRect(ex, y, 1, 1); w.fillStyle = C.r1; w.fillRect(ex, by, 1, 1); w.fillStyle = C.wh; w.fillRect(ex, by + 1, 1, 1); }
    else { w.fillStyle = 'rgba(255,255,255,.5)'; w.fillRect(ex, ey, 1, 4); } }); }
  if (N.hedge) { const n = N.hedge; add(n.y, () => { shadow(n.x, n.y, 8, 2); spr(SP.hedge[(S.hedgeApple ? 2 : 0) + (n.blink < 0 ? 1 : 0)], n.x - 9, n.y - 13 + hopY(n), n.flip); }); }
  if (N.cat) { const n = N.cat;
    if (n.roof) add(K.house[1] + 67, () => { spr(SP.catSleep, n.x, n.y); zz(n.x + 14, n.y - 6); });
    else add(n.y, () => { shadow(n.x, n.y, 6, 2); spr(n.sleep && !S.fest ? SP.catSleep : SP.catSit[n.blink < 0 || n.sleep ? 1 : 0], n.x - (n.sleep && !S.fest ? 8 : 7), n.y - (n.sleep && !S.fest ? 9 : 14) + hopY(n), n.flip); if (n.sleep && !S.fest) zz(n.x + 6, n.y - 16); }); }
  S.hens.forEach((e) => add(e.y, () => { shadow(e.x, e.y, 4, 1); const n = e.ryaba ? N.hen : null; spr((e.ryaba ? SP.ryaba : SP.hen)[e.peck], e.x - 5, e.y - 9 + (n ? hopY(n) : 0), e.flip); }));
  if (S.chick && S.chick.st !== 'hide') { const c = S.chick; add(c.y, () => spr(SP.chick[c.walk ? (Math.floor(c.ph * 10) % 2) : 0], c.x - 3, c.y - 6 - (c.walk && Math.floor(c.ph * 10) % 2 ? 1 : 0), c.flip)); }
  // Тиша
  const h = S.hero;
  if (h.alpha > 0) add(h.y, () => {
    const back = h.dir === 'up', stp = h.moving ? [1, 0, 2, 0][Math.floor(h.ph) % 4] : 0, bob = stp ? -1 : 0, bl = !back && h.blink < 0 ? 1 : 0;
    w.globalAlpha = h.alpha;
    shadow(h.x, h.y, 7, 2);
    const flip = h.dir === 'side' ? h.flip : false, bx = flip ? h.x - 14 : h.x + 4;
    const basket = Object.keys(S.inv).some((k) => k !== 'pumpkin' && k !== 'chick') ? SP.basketFull : SP.basket;
    if (back) spr(basket, bx, h.y - 11 + bob, flip);
    spr(SP.hero[(back ? 1 : 0) + '' + stp + bl], h.x - 10, h.y - 23 + bob, flip);
    if (!back && !have('pumpkin')) spr(basket, bx, h.y - 11 + bob, flip);
    if (have('pumpkin')) spr(SP.giant, h.x - 9, h.y - 35 + bob);
    if (have('can') && !back) spr(S.canFull ? SP.canFull : SP.can, flip ? h.x + 3 : h.x - 13, h.y - 10 + bob, !flip);
    w.globalAlpha = 1;
  });
  list.sort((a, b) => a.y - b.y);
  for (const o of list) o.d();
  // дым
  for (const p of S.smoke) { const a = clamp(1 - p.t / 3, 0, 1) * .85; w.globalAlpha = a; w.fillStyle = p.t > 1.6 ? '#e6dcd0' : C.wh; w.beginPath(); w.arc(Math.round(p.x), Math.round(p.y), p.r, 0, TAU); w.fill(); }
  w.globalAlpha = 1;
  // частицы
  for (const p of S.parts) {
    const a = clamp(p.life / p.max * 1.6, 0, 1), x = Math.round(p.x), y = Math.round(p.y); w.globalAlpha = a;
    if (p.k === 'heart') { w.fillStyle = C.r1; w.fillRect(x - 1, y, 1, 1); w.fillRect(x + 1, y, 1, 1); w.fillRect(x - 1, y + 1, 3, 1); w.fillRect(x, y + 2, 1, 1); }
    else if (p.k === 'note') { w.fillStyle = C.yl; w.fillRect(x, y, 1, 3); w.fillRect(x + 1, y, 1, 1); w.fillRect(x - 1, y + 2, 1, 1); }
    else if (p.k === 'leaf') { w.fillStyle = (x + y) % 2 ? C.g2 : C.g1; w.fillRect(x, y, 2, 1); }
    else if (p.k === 'drop') { w.fillStyle = C.w1; w.fillRect(x, y, 1, 2); }
    else if (p.k === 'dirt') { w.fillStyle = C.s1; w.fillRect(x, y, 1, 1); }
    else if (p.k === 'fluff') { w.fillStyle = C.wh; w.fillRect(x, y, 1, 1); w.globalAlpha = a * .5; w.fillRect(x + 1, y + 1, 1, 1); }
    else if (p.k === 'feather') { w.fillStyle = C.wh; w.fillRect(x, y, 2, 1); }
    else if (p.k === 'spark') { w.fillStyle = C.yl; w.fillRect(x, y, 1, 1); }
  }
  w.globalAlpha = 1;
  // бабочки днём
  if (S.eve < .5) for (let i = 0; i < 2; i++) { const t = S.t * .35 + i * 3.1, x = WW * (.3 + .4 * (.5 + .5 * Math.sin(t * .7 + i))), y = (K.minY + 20) + (WH - K.minY - 40) * (.5 + .45 * Math.sin(t * 1.1 + i * 2)), op = Math.floor(S.t * 8 + i) % 2;
    w.fillStyle = i ? C.pk : C.yl; w.fillRect(Math.round(x) - 1 - op, Math.round(y), 1, 1 + op); w.fillRect(Math.round(x) + 1 + op, Math.round(y), 1, 1 + op); w.fillStyle = C.ol; w.fillRect(Math.round(x), Math.round(y), 1, 1); }
  // свет дня
  w.drawImage(LIGHT, 0, 0);
  const [r, g, b] = lightCol();
  if (r < 255 || g < 255 || b < 255) { w.globalCompositeOperation = 'multiply'; w.fillStyle = `rgb(${r},${g},${b})`; w.fillRect(0, 0, WW, WH); w.globalCompositeOperation = 'source-over'; }
  const sunset = clamp((S.clock - .78) / .22, 0, 1) * (1 - S.eve * .7);
  if (sunset > 0) { const gr = w.createRadialGradient(K.sun[0], WH * .1, 4, K.sun[0], WH * .1, Math.max(WW, WH)); gr.addColorStop(0, `rgba(255,170,110,${.35 * sunset})`); gr.addColorStop(1, 'rgba(255,170,110,0)'); w.globalCompositeOperation = 'screen'; w.fillStyle = gr; w.fillRect(0, 0, WW, WH); w.globalCompositeOperation = 'source-over'; }
  // огни вечером
  const night = clamp(S.eve * 1.2 + clamp((S.clock - .9) / .1, 0, 1) * .3, 0, 1);
  if (night > 0) {
    const [hx, hy] = K.house; w.globalCompositeOperation = 'lighter';
    for (const wx of [hx + 22, hx + 62]) glow(w, wx, hy + 50, 22, 255, 200, 110, .5 * night);
    glow(w, hx + 42, hy + 26, 12, 255, 200, 110, .4 * night);
    w.globalCompositeOperation = 'source-over'; w.globalAlpha = night;
    w.fillStyle = C.win2; for (const wx of [hx + 17, hx + 57]) w.fillRect(wx, hy + 45, 11, 10); w.fillStyle = C.win; for (const wx of [hx + 17, hx + 57]) w.fillRect(wx, hy + 45, 5, 4);
    w.globalAlpha = 1;
    if (S.fest) { w.globalCompositeOperation = 'lighter'; glow(w, K.table[0], K.table[1] - 10, 70, 255, 170, 90, .28 * night); w.globalCompositeOperation = 'source-over'; festLights(w, night); }
    for (let i = 0; i < 10; i++) { const t = S.t * .4 + i * 1.7, x = (i * 53 + Math.sin(t) * 14) % WW, y = K.minY + ((i * 37) % (WH - K.minY - 20)) + Math.cos(t * 1.3) * 6, a = (.5 + .5 * Math.sin(S.t * 3 + i * 2)) * night; w.globalAlpha = a; w.fillStyle = '#fff3a0'; w.fillRect(Math.round(x), Math.round(y), 1, 1); w.globalAlpha = a * .35; w.fillRect(Math.round(x) - 1, Math.round(y), 3, 1); w.fillRect(Math.round(x), Math.round(y) - 1, 1, 3); }
    w.globalAlpha = 1;
  }
  // куда идём: крестик на земле
  if (S.dest) { const k = S.dest.t / .6, x = Math.round(S.dest.x), y = Math.round(S.dest.y); w.globalAlpha = 1 - k; w.fillStyle = C.wh; const r2 = 2 + Math.round(k * 3); w.fillRect(x - r2, y, 1, 1); w.fillRect(x + r2, y, 1, 1); w.fillRect(x, y - Math.ceil(r2 / 2), 1, 1); w.fillRect(x, y + Math.ceil(r2 / 2), 1, 1); w.globalAlpha = 1; }
}
function glow(w, x, y, r, R, G, B, a) { const gr = w.createRadialGradient(x, y, 0, x, y, r); gr.addColorStop(0, `rgba(${R},${G},${B},${a})`); gr.addColorStop(1, `rgba(${R},${G},${B},0)`); w.fillStyle = gr; w.fillRect(x - r, y - r, r * 2, r * 2); }
function festLights(w, a) {
  const [tx, ty] = K.table, lw = K.lantW, x0 = tx - lw, x1 = tx + lw, top = ty - 30;
  w.fillStyle = C.wd2; w.fillRect(x0, top, 1, 30); w.fillRect(x1, top, 1, 30);
  const cols = ['#ffd35c', '#ff9fc0', '#9fe0ee', '#ffe066', '#b8e27a', '#ff9a3c', '#b9a2f0', '#ff9fc0', '#9fe0ee'];
  for (let i = 0; i <= lw * 2; i++) { const x = x0 + i, y = top + Math.round(Math.sin(i / (lw * 2) * Math.PI) * 7); w.fillStyle = C.ol2; w.fillRect(x, y, 1, 1); }
  const nl = Math.max(5, Math.round(lw / 5.5));
  for (let k = 0; k < nl; k++) { const i = lw * 2 * (k + .6) / (nl + .2), x = Math.round(x0 + i), y = top + Math.round(Math.sin(i / (lw * 2) * Math.PI) * 7) + 1, c = cols[k % cols.length]; w.fillStyle = c; w.fillRect(x - 1, y, 3, 3); w.fillStyle = C.wh; w.fillRect(x, y, 1, 1);
    w.globalCompositeOperation = 'lighter'; const R = parseInt(c.slice(1, 3), 16), G = parseInt(c.slice(3, 5), 16), B = parseInt(c.slice(5, 7), 16); glow(w, x, y + 1, 9, R, G, B, .45 * a * (.8 + .2 * Math.sin(S.t * 3 + k))); w.globalCompositeOperation = 'source-over'; }
}
function sparkle(x, y, k) { const w = WX, a = 1 - Math.abs(k * 2 - 1); w.globalAlpha = clamp(a + .2, 0, 1); w.fillStyle = C.wh; w.fillRect(x, y, 1, 1); w.fillStyle = C.yl; if (a > .3) { w.fillRect(x - 1, y, 1, 1); w.fillRect(x + 1, y, 1, 1); w.fillRect(x, y - 1, 1, 1); w.fillRect(x, y + 1, 1, 1); } if (a > .7) { w.fillRect(x - 2, y, 1, 1); w.fillRect(x + 2, y, 1, 1); w.fillRect(x, y - 2, 1, 1); w.fillRect(x, y + 2, 1, 1); } w.globalAlpha = 1; }
function zz(x, y) { const k = (S.t * .7) % 1; WX.globalAlpha = 1 - k; spr(ICON.zz.cv, x, y - Math.round(k * 4)); WX.globalAlpha = 1; }
function lightCol() {
  const keys = [[0, [255, 226, 206]], [.18, [255, 248, 236]], [.3, [255, 255, 255]], [.66, [255, 255, 255]], [.82, [255, 236, 208]], [.94, [255, 204, 166]], [1, [242, 176, 156]]];
  let c = keys[keys.length - 1][1];
  for (let i = 1; i < keys.length; i++) if (S.clock <= keys[i][0]) { const [t0, a] = keys[i - 1], [t1, b] = keys[i], k = (S.clock - t0) / (t1 - t0); c = a.map((v, j) => v + (b[j] - v) * k); break; }
  const e = S.eve, n = [112, 112, 172];
  return c.map((v, j) => Math.round(v + (n[j] - v) * e));
}

/* ---------------- пузыри над жителями ---------------- */
const BUB = {};
function bubbleCv(icon, n, style) {
  const key = icon + n + style; if (BUB[key]) return BUB[key];
  const ic = ICON[icon].cv, ck = style === 'ready' ? ICON.check.cv : null, extra = ck ? ck.width : n > 1 ? 8 : 0, w = ic.width + extra + 4, h = Math.max(ic.height, 9) + 4;
  const c = mk(w, h + 3), x = c.getContext('2d');
  const ol = style === 'ready' ? '#c46a16' : style === 'offer' ? '#3f8a4c' : C.ol, fill = style === 'ready' ? '#fff0b8' : style === 'offer' ? '#eefbe4' : C.wh;
  x.fillStyle = ol; x.fillRect(1, 0, w - 2, h); x.fillRect(0, 1, w, h - 2);
  x.fillStyle = fill; x.fillRect(2, 1, w - 4, h - 2); x.fillRect(1, 2, w - 2, h - 4);
  const tx = (w >> 1) - 2;
  x.fillStyle = fill; x.fillRect(tx + 1, h - 1, 2, 1);
  x.fillStyle = ol; x.fillRect(tx, h, 1, 1); x.fillRect(tx + 3, h - 1, 1, 2); x.fillRect(tx + 1, h + 1, 1, 1); x.fillRect(tx + 2, h + 1, 1, 1); x.fillRect(tx + 2, h + 2, 1, 1);
  x.fillStyle = fill; x.fillRect(tx + 1, h, 2, 1);
  x.drawImage(ic, 2, (h - ic.height) >> 1);
  if (ck) x.drawImage(ck, 2 + ic.width - 1, (h - ck.height) >> 1);
  else if (n > 1) { x.fillStyle = ol; const dx = 2 + ic.width, dy = (h - 5) >> 1; [DIG.x, DIG[n]].forEach((g, k) => g.forEach((row, j) => [...row].forEach((ch, i) => { if (ch === 'x') x.fillRect(dx + k * 4 + i, dy + j, 1, 1); }))); }
  return (BUB[key] = c);
}
function bubbleOf(id) {
  const n = S.npcs[id]; if (!n || S.mode === 'title' && false) return null;
  if (S.fest || S.mode === 'night' || S.mode === 'nightwait' || S.mode === 'end' || S.mode === 'endwait') return null;
  if (n.happy > 0) return ['heart', 1, 'love'];
  if (id === 'frog' && S.day === 2 && !S.fishGiven) { const ft = S.tasks.find((t) => t.id === 'fish'); if (ft && !ft.done) return ['fish', 1, 'offer']; }
  if (id === 'cat' && n.sleep) return null;
  const t = taskOf(id); if (!t) return null;
  return [t.icon, t.n > 1 && t.item ? t.n : 1, ready(t) ? 'ready' : 'ask'];
}
function npcHead(id) {
  const n = S.npcs[id];
  if (id === 'hen') return [n.ref.x, n.ref.y - 11 + hopY(n)];
  if (id === 'cat') return n.roof ? [n.x + 8, n.y - 1] : [n.x, n.y - (n.sleep ? 10 : 15) + hopY(n)];
  const hh = { mole: 22, sheep: 18, frog: 14, hedge: 14, duck: 11 }[id] || 16;
  return [n.x + (id === 'sheep' ? -6 : 0), n.y - hh + hopY(n)];
}
function drawBubbles(c) {
  c.imageSmoothingEnabled = false;
  const out = [];
  for (const id in S.npcs) { const b = bubbleOf(id); if (!b) continue; const cv = bubbleCv(...b), [hx, hy] = npcHead(id); const bob = b[2] === 'ready' ? Math.round(Math.abs(Math.sin(S.t * 5)) * -2) : Math.round(Math.sin(S.t * 2 + hx) * 1);
    out.push({ cv, x: Math.round(hx * PX - cv.width * BS / 2), y: Math.round(hy * PX - 6 - cv.height * BS + bob * BS) }); }
  out.sort((a, b) => a.y - b.y).forEach((o) => c.drawImage(o.cv, o.x, o.y, o.cv.width * BS, o.cv.height * BS));
  return out;
}
function drawMarkers(c) {
  if (S.mode !== 'play') return;
  const bounce = Math.round(Math.abs(Math.sin(S.t * 4)) * 3);
  let s = S.mark ? spotById(S.mark.id) : null, big = true;
  if (!s && !S.hero.path) { s = nearestSpot(); big = false; if (s && (s.id === 'pond' || (s.id.startsWith('npc:') && bubbleOf(s.who)))) s = null; }
  if (!s) return;
  let top = s.top;
  if (s.who && bubbleOf(s.who)) { const [, hy] = npcHead(s.who); top = hy - 22; }
  const cv = big ? ICON.arrow.cv : ICON.arrowW.cv, k = big ? BS : 4;
  const x = Math.round(s.fx * PX - cv.width * k / 2), y = Math.round(top * PX - cv.height * k - 8 - bounce * k);
  c.drawImage(cv, x, y, cv.width * k, cv.height * k);
}

/* ---------------- интерфейс ---------------- */
const UI = LAND ? {
  plaque: [20, 20, 316, 104], help: [1194, 30, 54, 50], cap: [354, 20, 488], capMin: 120, face: 72, capFs: 23, nameFs: 20,
  quests: [856, 20, 404], qHead: 62, qRow: 44, qFs: 22, qIcon: 4,
  inv: [436, 626, 5, 78, 64], invIcon: 4, purse: [1052, 626, 208, 82], purseCoin: [1084, 666], purseFs: 30,
  ctrl: [24, 692], banner: [640, 300, 440, 170]
} : {
  plaque: null, help: [628, 28, 58, 58], cap: [20, 16, 680], capMin: 244, face: 92, capFs: 27, nameFs: 25,
  quests: [20, 16, 680], qHead: 92, qRow: 46, qFs: 27, qIcon: 4,
  inv: [20, 1164, 5, 86, 76], invIcon: 5, purse: [482, 1164, 218, 100], purseCoin: [520, 1214], purseFs: 34,
  ctrl: null, banner: [360, 560, 520, 210]
};
function slotXY(i) { const [x, y, , st, sz] = UI.inv; return [x + 16 + i * st + sz / 2, y + 14 + sz / 2]; }
function questH() { return UI.qHead + S.tasks.length * UI.qRow + 14; }
function uiHit(x, y) {
  const inR = (r) => r && x >= r[0] && x < r[0] + r[2] && y >= r[1] && y < r[1] + r[3];
  if (inR(UI.help)) return 'help';
  if (UI.plaque && inR(UI.plaque)) return 'ui';
  if (inR([UI.quests[0], UI.quests[1], UI.quests[2], questH()])) return 'ui';
  const [ix, iy, n, st, sz] = UI.inv; if (inR([ix, iy, n * st + 22, sz + 28])) return 'ui';
  if (inR(UI.purse)) return 'ui';
  return null;
}
function pbox(c, x, y, w, h, fill = C.paper, edge = C.ol, sh = true) {
  if (sh) { c.fillStyle = 'rgba(40,25,50,.3)'; c.fillRect(x + 4, y + 8, w, h); }
  c.fillStyle = edge; c.fillRect(x + 4, y, w - 8, h); c.fillRect(x, y + 4, w, h - 8);
  c.fillStyle = fill; c.fillRect(x + 8, y + 4, w - 16, h - 8); c.fillRect(x + 4, y + 8, w - 8, h - 16);
}
function txt(c, s, x, y, size, color, o = {}) { c.font = `${o.w || 700} ${size}px ${FONT}`; c.textAlign = o.align || 'left'; c.textBaseline = o.base || 'alphabetic'; c.fillStyle = color; c.fillText(s, x, y); return c.measureText(s).width; }
function icon(c, name, x, y, k) { const cv = ICON[name].cv; c.drawImage(cv, Math.round(x), Math.round(y), cv.width * k, cv.height * k); return [cv.width * k, cv.height * k]; }
function iconC(c, name, cx, cy, k, pop = 0) { const cv = ICON[name].cv, s = k * (1 + pop); c.drawImage(cv, Math.round(cx - cv.width * s / 2), Math.round(cy - cv.height * s / 2), Math.round(cv.width * s), Math.round(cv.height * s)); }
function clockStr() { const m = Math.min(12 * 60, Math.floor(S.clock * 12 * 60 / 10) * 10), hh = 8 + Math.floor(m / 60), mm = m % 60; return hh + ':' + String(mm).padStart(2, '0'); }
function wrap(c, text, maxW) { const out = []; let line = ''; for (const wd of text.split(' ').filter(Boolean)) { const t = line ? line + ' ' + wd : wd; if (c.measureText(t).width > maxW && line) { out.push(line); line = wd; } else line = t; } out.push(line); return out; }
function drawHUD(c) {
  const fs = UI.qFs;
  // день и часы
  const dayIcon = S.clock > .9 || S.eve > 0 ? 'moon' : 'sun';
  if (LAND) {
    const [x, y, w, h] = UI.plaque; pbox(c, x, y, w, h);
    icon(c, dayIcon, x + 16, y + 16, 4);
    const tw = txt(c, 'День ' + S.day, x + 76, y + 50, 32, C.ink, { w: 800 }); txt(c, ' из 3', x + 76 + tw, y + 50, 21, C.muted, { w: 600 });
    progress(c, x + 76, y + 66, w - 172, 16);
    txt(c, clockStr(), x + w - 20, y + 83, 24, '#86512f', { w: 800, align: 'right' });
  } else {
    const [x, y, w] = UI.quests;
    pbox(c, x, y, w, questH());
    icon(c, dayIcon, x + 18, y + 16, 4);
    const tw = txt(c, 'День ' + S.day, x + 78, y + 52, 32, C.ink, { w: 800 }); txt(c, ' · ' + DAYS[S.day - 1].name, x + 78 + tw, y + 52, 24, C.muted, { w: 600 });
    txt(c, clockStr(), x + w - 92, y + 52, 28, '#86512f', { w: 800, align: 'right' });
    progress(c, x + 26, y + 72, w - 52, 12);
  }
  // поручения
  {
    const [x, y, w] = UI.quests;
    if (LAND) { pbox(c, x, y, w, questH()); txt(c, 'ПОРУЧЕНИЯ', x + 22, y + 44, 20, C.r2, { w: 900 }); txt(c, DAYS[S.day - 1].name.toLowerCase(), x + 166, y + 44, 20, '#86512f', { w: 700 }); }
    S.tasks.forEach((t, i) => {
      const ry = y + UI.qHead + i * UI.qRow;
      if (t.flash > 0) { c.fillStyle = `rgba(255,211,92,${.55 * t.flash})`; c.fillRect(x + 10, ry + 2, w - 20, UI.qRow - 4); }
      iconC(c, t.icon, x + 40, ry + UI.qRow / 2, UI.qIcon);
      const tx = x + 72, done = t.done, [hv, nd] = prog(t);
      c.font = `${done ? 600 : 700} ${fs}px ${FONT}`; let s = fs; while (c.measureText(t.text).width > w - 142 && s > 20) { s--; c.font = `700 ${s}px ${FONT}`; }
      const tw = txt(c, t.text, tx, ry + UI.qRow / 2 + s * .36, s, done ? '#a59db4' : C.ink, { w: done ? 600 : 700 });
      if (done) { c.fillStyle = '#a59db4'; c.fillRect(tx, ry + UI.qRow / 2 - 1, tw, 3); iconC(c, 'check', x + w - 40, ry + UI.qRow / 2, 4); }
      else txt(c, nd > 1 ? hv + '/' + nd : hv ? '1/1' : '0/1', x + w - 22, ry + UI.qRow / 2 + fs * .36, fs, hv >= nd ? C.teal2 : C.r2, { w: 800, align: 'right' });
    });
  }
  // «?»
  { const [x, y, w, h] = UI.help, pulse = S.idle > 9 && S.mode === 'play' ? Math.sin(S.t * 5) > 0 : false;
    pbox(c, x, y, w, h, pulse ? '#ffd35c' : C.paper); txt(c, '?', x + w / 2, y + h / 2 + 2, LAND ? 36 : 34, C.ink, { w: 900, align: 'center', base: 'middle' }); }
  // корзинка
  {
    const [x, y, n, st, sz] = UI.inv, keys = Object.keys(S.inv);
    pbox(c, x, y, n * st + 22, sz + 28);
    for (let i = 0; i < n; i++) {
      const sx = x + 16 + i * st, sy = y + 14, k = keys[i];
      c.fillStyle = k ? C.slot : '#f4e9d0'; c.fillRect(sx, sy, sz, sz);
      if (!k) { c.fillStyle = 'rgba(58,42,60,.08)'; c.fillRect(sx + sz / 2 - 3, sy + sz / 2 - 3, 6, 6); continue; }
      const pop = S.slotPop[k] ? Math.sin(S.slotPop[k] / .35 * Math.PI) * .25 : 0;
      iconC(c, k === 'can' && S.canFull ? 'canFull' : k, sx + sz / 2, sy + sz / 2 - 2, UI.invIcon, pop);
      if (S.inv[k] > 1) txt(c, String(S.inv[k]), sx + sz - 6, sy + sz - 6, LAND ? 20 : 24, C.ink, { w: 900, align: 'right' });
    }
  }
  // монетки и сердечки
  {
    const [x, y, w, h] = UI.purse; pbox(c, x, y, w, h);
    const pc = S.slotPop.coin ? Math.sin(S.slotPop.coin / .3 * Math.PI) * .3 : 0, ph = S.slotPop.heart ? Math.sin(S.slotPop.heart / .4 * Math.PI) * .3 : 0;
    const cy = y + h / 2 + 2, k = LAND ? 4 : 5;
    iconC(c, 'coin', x + (LAND ? 32 : 38), cy, k, pc); txt(c, String(S.coins), x + (LAND ? 56 : 66), cy + UI.purseFs * .36, UI.purseFs, C.ink, { w: 900 });
    iconC(c, 'heart', x + (LAND ? 140 : 150), cy, k, ph); txt(c, String(S.hearts), x + (LAND ? 164 : 178), cy + UI.purseFs * .36, UI.purseFs, C.ink, { w: 900 });
  }
  // строка управления (компьютер)
  if (UI.ctrl && !A.isTouch && S.day === 1) {
    const [x, y] = UI.ctrl; c.font = `700 20px ${FONT}`; c.textAlign = 'left'; c.lineJoin = 'round'; c.lineWidth = 5; c.strokeStyle = 'rgba(36,80,61,.75)';
    const s = 'WASD — идти · E — говорить'; c.strokeText(s, x, y); c.fillStyle = '#fff6e2'; c.fillText(s, x, y);
  }
  drawCaption(c);
}
function prog(t) {
  if (t.id === 'water') return [S.watered ? 3 : S.canFull ? 2 : have('can') ? 1 : 0, 3];
  return [Math.min(have(t.item), t.n), t.n];
}
function progress(c, x, y, w, h) {
  c.fillStyle = C.ol; c.fillRect(x, y, w, h); c.fillStyle = C.slot; c.fillRect(x + 3, y + 3, w - 6, h - 6);
  const k = clamp(S.clock, 0, 1), fw = Math.round((w - 6) * k);
  c.fillStyle = S.clock > .8 ? '#f0906a' : '#ffd35c'; c.fillRect(x + 3, y + 3, fw, h - 6);
  c.fillStyle = C.wh; c.fillRect(x + 3, y + 3, fw, 2);
}
/* раскладка реплики: окошко растёт по тексту — переносов столько, сколько нужно, ни одно слово не теряется */
function capLayout(c, text) {
  const [x, , w] = UI.cap, fs = UI.capFs, F = UI.face, tx = x + 20 + F + 18, maxW = w - (tx - x) - 22;
  c.font = `600 ${fs}px ${FONT}`; const lines = wrap(c, text, maxW);
  const need = 26 + UI.nameFs + 14 + lines.length * (fs + 8) + 16;
  return { tx, maxW, lines, need, h: Math.max(UI.capMin, need) };
}
/* для самопроверки: все реплики, подсказки и названия поручений помещаются целиком */
function checkTexts() {
  const c = mk(4, 4).getContext('2d'), out = [], all = [];
  const grab = (v) => { if (typeof v === 'string') all.push(v); else if (Array.isArray(v)) v.forEach(grab); else if (v && typeof v === 'object') Object.values(v).forEach(grab); };
  grab(L); grab(SAY);
  for (const k in HINT) { const m = HINT[k].toString().match(/'[^']*\s[^']*'/g) || []; m.forEach((q) => all.push(q.slice(1, -1))); }
  for (const text of all) {
    const { lines, maxW, h } = capLayout(c, text);
    c.font = `600 ${UI.capFs}px ${FONT}`;
    if (lines.join(' ') !== text.split(' ').filter(Boolean).join(' ')) out.push('потеря слов: ' + text);
    for (const ln of lines) if (c.measureText(ln).width > maxW + .5) out.push('строка шире окошка: ' + ln);
    if (UI.cap[1] + h > H * .42) out.push('окошко слишком высокое (' + Math.round(h) + '): ' + text);
  }
  for (const id in TASKS) { c.font = `700 20px ${FONT}`; if (c.measureText(TASKS[id].text).width > UI.quests[2] - 142) out.push('поручение не влезает: ' + TASKS[id].text); }
  return { n: all.length, fails: out };
}
function drawCaption(c) {
  const k = S.cap; if (!k) return;
  const a = clamp(Math.min(k.t / .18, (k.life - k.t) / .35), 0, 1); if (a <= 0) return;
  const [x, y, w] = UI.cap, fs = UI.capFs, F = UI.face, { tx, lines, need, h } = capLayout(c, k.text), oy = Math.max(0, Math.round((h - need) / 2 - 8));
  c.save(); c.globalAlpha = a;
  pbox(c, x, y, w, h);
  const fy = y + Math.max(20, Math.round((h - F) / 2)); c.fillStyle = FACE_BG[k.who] || C.slot; c.fillRect(x + 20, fy, F, F); c.fillStyle = 'rgba(58,42,60,.15)'; c.fillRect(x + 20, fy + F - 6, F, 6);
  const pv = SP.portrait[k.who]; if (pv) { const s = Math.max(1, Math.floor((F - 12) / Math.max(pv.width, pv.height))); c.imageSmoothingEnabled = false; c.drawImage(pv, Math.round(x + 20 + F / 2 - pv.width * s / 2), Math.round(fy + F - 6 - pv.height * s), pv.width * s, pv.height * s); }
  txt(c, NAME[k.who], tx, y + oy + 20 + UI.nameFs, UI.nameFs, NAME_COL[k.who] || C.ink, { w: 900 });
  let left = Math.min(k.text.length, Math.floor(k.t * 55));
  lines.forEach((ln, i) => { if (left <= 0) return; const s = ln.slice(0, left); left -= ln.length + 1; txt(c, s, tx, y + oy + 20 + UI.nameFs + 14 + fs + i * (fs + 8) - 4, fs, C.ink, { w: 600 }); });
  c.restore();
}
function drawFlyers(c) {
  for (const f of S.flyers) { if (f.t < 0) continue; const k = A.ease.inOutSine(clamp(f.t / f.dur, 0, 1)), x = lerp(f.x0, f.x1, k), y = lerp(f.y0, f.y1, k) - Math.sin(k * Math.PI) * 90; iconC(c, f.icon, x, y, LAND ? 4 : 5, Math.sin(k * Math.PI) * .2); }
}
function drawBanner(c) {
  const b = S.banner; if (!b) return;
  const t = b.t - .5; if (t < 0) return;
  const kin = A.ease.outBack(clamp(t / .45, 0, 1)), a = clamp((2.9 - t) / .4, 0, 1);
  const [cx, cy, w, h] = UI.banner;
  c.save(); c.globalAlpha = a; c.translate(cx, cy - (1 - kin) * 80); c.scale(.9 + .1 * kin, .9 + .1 * kin);
  pbox(c, -w / 2, -h / 2, w, h);
  c.fillStyle = C.coat; c.fillRect(-w / 2 + 16, -h / 2 + 16, 12, 12);
  txt(c, b.title, 0, -h * .08, LAND ? 56 : 64, C.ink, { w: 900, align: 'center' });
  txt(c, b.sub, 0, h * .18, LAND ? 26 : 30, C.r2, { w: 800, align: 'center' });
  txt(c, b.line || 'Помоги соседям до заката', 0, h * .36, LAND ? 20 : 24, C.muted, { w: 600, align: 'center' });
  c.restore();
}
function draw(c, g) {
  if (!S) return;
  renderWorld();
  c.imageSmoothingEnabled = false;
  c.drawImage(WCV, 0, 0, W, H);
  if (S.mode !== 'end' && S.mode !== 'endwait') drawBubbles(c);
  drawMarkers(c);
  if (S.cover) drawCover(c);
  else if (S.mode === 'play' || S.mode === 'dusk') drawHUD(c);
  else if (S.mode === 'fest' && S.cap) drawCaption(c);
  drawFlyers(c);
  drawPops(c);
  drawBanner(c);
  drawNext(c);
  if (S.fade > 0) { c.fillStyle = `rgba(36,24,52,${S.fade})`; c.fillRect(0, 0, W, H); }
  c.imageSmoothingEnabled = true;
}

/* всплывающая награда: бумажная табличка над головой Тиши, тёмные буквы — читается на любой траве */
function drawPops(c) {
  const h = S.hero; let k = 0;
  for (const p of S.pops) {
    const a = clamp(Math.min(p.t / .12, (p.life - p.t) / .35), 0, 1), sc = p.t < .22 ? A.ease.outBack(p.t / .22) : 1;
    const fs = LAND ? 28 : 34, main = '+' + p.n, sub = p.tag ? ' · ' + p.tag : '';
    c.font = `900 ${fs}px ${FONT}`; const w1 = c.measureText(main).width; c.font = `800 ${fs - 4}px ${FONT}`; const w2 = sub ? c.measureText(sub).width : 0;
    const ic = LAND ? 4 : 5, iw = ICON.coin.cv.width * ic, bw = Math.round(iw + w1 + w2 + 44), bh = fs + 26;
    const top = have('pumpkin') ? 40 : 30, cx = clamp(Math.round(h.x * PX), bw / 2 + 12, W - bw / 2 - 12), cy = Math.round((h.y - top) * PX - bh / 2 - 10 - p.t * 26 - k * (bh + 8));
    c.save(); c.globalAlpha = a; c.translate(cx, cy); c.scale(sc, sc);
    pbox(c, -bw / 2, -bh / 2, bw, bh);
    icon(c, 'coin', -bw / 2 + 14, -ICON.coin.cv.height * ic / 2, ic);
    const tx = -bw / 2 + 22 + iw;
    txt(c, main, tx, fs * .36, fs, C.ink, { w: 900 });
    if (sub) txt(c, sub, tx + w1, fs * .36, fs - 4, C.r2, { w: 800 });
    c.restore(); k++;
  }
}
/* «Дальше» на празднике */
function nextRect() { return LAND ? [520, 626, 240, 74] : [210, 1168, 300, 92]; }
function drawNext(c) {
  if (S.mode !== 'fest' || S.festT < 2.5 || S.fade > .05) return;
  const [x, y, w, h] = nextRect(), a = clamp((S.festT - 2.5) / .4, 0, 1), b = Math.round(Math.sin(S.t * 4) * 3);
  c.save(); c.globalAlpha = a;
  pbox(c, x, y + b, w, h, '#f28b3b'); txt(c, 'Дальше', x + w / 2, y + b + h / 2 + 2, LAND ? 30 : 36, C.wh, { w: 900, align: 'center', base: 'middle' });
  c.restore();
}

/* обложка (самопроверка снимает её с S.cover = true): кадр игры и табличка с названием */
function drawCover(c) {
  const x = LAND ? 96 : 40, y = 40, w = LAND ? 600 : 640, h = 150;
  pbox(c, x, y, w, h); c.fillStyle = C.coat; c.fillRect(x + 14, y + 14, 12, 12);
  txt(c, 'Хутор Одуванчик', x + 34, y + 84, 62, C.ink, { w: 900 });
  txt(c, 'помогай соседям до заката', x + 38, y + 124, 28, C.r2, { w: 700 });
}

/* ---------------- экраны ---------------- */
function titleScreen(g) {
  fresh(); g.setPlaying(false);
  g.screen({
    kicker: A.framed ? 'Досуг' : 'Аркада', title: 'Хутор Одуванчик',
    html: '<p>Малыш Тиша помогает соседям до заката. Пузырь над головой — значит, нужна помощь: найди, вырасти, принеси!</p><p style="opacity:.75">Три дня, у каждого свои поручения и сюрпризы.</p>',
    button: 'Начать', onGo: () => beginDay(1)
  });
}

A.game({
  id: 'farm', tone: 'light', title: 'Хутор Одуванчик', width: W, height: H, orientation: LAND ? 'landscape' : 'portrait', music: 'garden',
  keys: { KeyE: 'action', KeyZ: 'none', KeyJ: 'none', KeyK: 'none', KeyX: 'none', KeyL: 'none', ShiftLeft: 'none' },
  help: { desktop: '<kbd>WASD</kbd> или стрелки — идти · <kbd>E</kbd> — говорить и брать · щелчок — идти туда · <kbd>?</kbd> — подсказка', short: 'WASD — идти · E — говорить и брать · щелчок — идти туда', touch: 'Нажмите на место — Тиша пойдёт сам · на соседа или вещь — подойдёт и поможет' },
  init(g) {
    GAME = g; buildIcons(); buildSprites(); buildWalk(); bake();
    titleScreen(g); buildSpots();
    window.__farm = () => S;
  },
  update, draw
});
})();
