/* Найди пару (24.10: идея людей — «поиск двух одинаковых картинок среди закрытых: кликаешь — карточка разворачивается
   на секунду и снова закрывается»). Карточки рубашкой вверх; откройте две — одинаковые остаются открытыми, разные
   закрываются. Перед уровнем все карточки на миг показываются — «запомните». Наборы рисунков свои, нарисованы кодом:
   «Зверята», «Рожицы», «Знаки». Уровни растут: 6, 8, 10, 12 пар. Очки — за пары и за мало ходов; рекорд — сумма.
   Широкое окно — карточки шире в ряд, узкое (телефон) — столбцом. */
(() => {
'use strict';
const A = Arcade;
const LAND = (() => { try { return innerWidth > (innerHeight - 110) * 1.15; } catch (e) { return false; } })();
const W = LAND ? 1280 : 720, H = LAND ? 720 : 1280, TAU = Math.PI * 2;
const INK = '#2d2a4a', MUTED = 'rgba(45,42,74,.55)';
const LEVELS = LAND ? [[4, 3], [4, 4], [5, 4], [6, 4]] : [[3, 4], [4, 4], [4, 5], [4, 6]];
const SETS = [
  { name: 'Зверята', items: ['cat', 'fox', 'bear', 'bunny', 'frog', 'panda', 'owl', 'chick', 'pig', 'mouse', 'penguin', 'koala'] },
  { name: 'Рожицы', items: ['smile', 'wink', 'wow', 'love', 'sleepy', 'laugh', 'cool', 'tongue', 'shy', 'grumpy', 'stars', 'kiss'] },
  { name: 'Знаки', items: ['heart', 'star', 'moon', 'sun', 'drop', 'leaf', 'flower', 'cloud', 'bolt', 'crown', 'gem', 'note'] },
];
let S = null, total = 0;

/* ---------------- рисунки ---------------- */
const circ = (c, x, y, r, f) => { c.beginPath(); c.arc(x, y, r, 0, TAU); c.fillStyle = f; c.fill(); };
const ell = (c, x, y, rx, ry, f, rot = 0) => { c.beginPath(); c.ellipse(x, y, rx, ry, rot, 0, TAU); c.fillStyle = f; c.fill(); };
function eyes(c, r, dy = -.05, sp = .32, size = .1, col = '#2d2a4a') { circ(c, -r * sp, r * dy, r * size, col); circ(c, r * sp, r * dy, r * size, col); circ(c, -r * sp + r * .03, r * dy - r * .035, r * size * .35, '#fff'); circ(c, r * sp + r * .03, r * dy - r * .035, r * size * .35, '#fff'); }
function blush(c, r, y = .2, col = 'rgba(255,130,160,.55)') { ell(c, -r * .52, r * y, r * .14, r * .08, col); ell(c, r * .52, r * y, r * .14, r * .08, col); }
function smileM(c, r, y = .22, w = .2) { c.beginPath(); c.arc(0, r * y - r * w * .4, r * w, .2, Math.PI - .2); c.lineWidth = r * .06; c.lineCap = 'round'; c.strokeStyle = '#2d2a4a'; c.stroke(); }
function animal(c, k, r) {
  const ear = (x, y, rr, f, inner) => { circ(c, x, y, rr, f); if (inner) circ(c, x, y, rr * .55, inner); };
  const tri = (pts, f) => { c.beginPath(); pts.forEach(([x, y], i) => (i ? c.lineTo(x * r, y * r) : c.moveTo(x * r, y * r))); c.closePath(); c.fillStyle = f; c.fill(); };
  switch (k) {
    case 'cat': tri([[-.75, -.2], [-.6, -.95], [-.15, -.6]], '#f2a65a'); tri([[.75, -.2], [.6, -.95], [.15, -.6]], '#f2a65a'); tri([[-.6, -.35], [-.55, -.78], [-.3, -.55]], '#ffc9a3'); tri([[.6, -.35], [.55, -.78], [.3, -.55]], '#ffc9a3');
      circ(c, 0, .05, r * .78, '#f6b26b'); eyes(c, r, -.02); tri([[-.08, .14], [.08, .14], [0, .24]], '#ff8fa3'); blush(c, r, .3);
      c.strokeStyle = 'rgba(45,42,74,.5)'; c.lineWidth = r * .03; c.beginPath(); for (const s of [-1, 1]) { c.moveTo(s * r * .3, r * .26); c.lineTo(s * r * .78, r * .18); c.moveTo(s * r * .3, r * .32); c.lineTo(s * r * .78, r * .36); } c.stroke(); break;
    case 'fox': tri([[-.8, -.1], [-.62, -.95], [-.15, -.55]], '#ee7d3b'); tri([[.8, -.1], [.62, -.95], [.15, -.55]], '#ee7d3b'); tri([[-.66, -.6], [-.62, -.95], [-.45, -.7]], '#3d2b2b'); tri([[.66, -.6], [.62, -.95], [.45, -.7]], '#3d2b2b');
      circ(c, 0, 0, r * .74, '#f28c48'); tri([[-.74, .02], [0, .7], [.74, .02], [0, .25]], '#fff6ec'); eyes(c, r, -.12); circ(c, 0, r * .3, r * .08, '#3d2b2b'); break;
    case 'bear': ear(-r * .55, -r * .55, r * .25, '#a8754f', '#e5b98e'); ear(r * .55, -r * .55, r * .25, '#a8754f', '#e5b98e'); circ(c, 0, .05, r * .75, '#b98258'); ell(c, 0, r * .3, r * .32, r * .24, '#f0d1ae'); eyes(c, r, -.08); ell(c, 0, r * .2, r * .1, r * .07, '#3d2b2b'); smileM(c, r, .34, .1); break;
    case 'bunny': ell(c, -r * .3, -r * .62, r * .16, r * .42, '#e9e2f5', -.15); ell(c, r * .3, -r * .62, r * .16, r * .42, '#e9e2f5', .15); ell(c, -r * .3, -r * .62, r * .08, r * .3, '#ffc4d6', -.15); ell(c, r * .3, -r * .62, r * .08, r * .3, '#ffc4d6', .15);
      circ(c, 0, r * .18, r * .66, '#efe9f8'); eyes(c, r, .12, .28); ell(c, 0, r * .3, r * .07, r * .05, '#ff8fa3'); blush(c, r, .42); break;
    case 'frog': circ(c, -r * .38, -r * .42, r * .26, '#7dd36f'); circ(c, r * .38, -r * .42, r * .26, '#7dd36f'); ell(c, 0, r * .12, r * .82, r * .62, '#8ee07f'); circ(c, -r * .38, -r * .42, r * .15, '#fff'); circ(c, r * .38, -r * .42, r * .15, '#fff');
      circ(c, -r * .36, -r * .42, r * .08, '#2d2a4a'); circ(c, r * .4, -r * .42, r * .08, '#2d2a4a'); smileM(c, r, .2, .38); blush(c, r, .3); break;
    case 'panda': ear(-r * .56, -r * .56, r * .24, '#2d2a4a'); ear(r * .56, -r * .56, r * .24, '#2d2a4a'); circ(c, 0, .05, r * .78, '#d9d6e6'); circ(c, 0, .05, r * .74, '#fbfaff'); ell(c, -r * .3, -r * .02, r * .18, r * .22, '#2d2a4a', .4); ell(c, r * .3, -r * .02, r * .18, r * .22, '#2d2a4a', -.4);
      circ(c, -r * .28, -r * .02, r * .07, '#fff'); circ(c, r * .28, -r * .02, r * .07, '#fff'); ell(c, 0, r * .24, r * .1, r * .07, '#2d2a4a'); blush(c, r, .32); break;
    case 'owl': tri([[-.7, -.5], [-.55, -.9], [-.3, -.55]], '#9b7653'); tri([[.7, -.5], [.55, -.9], [.3, -.55]], '#9b7653'); ell(c, 0, .08 * r, r * .72, r * .8, '#a98260'); ell(c, 0, r * .35, r * .45, r * .42, '#e8d3b5');
      circ(c, -r * .3, -r * .15, r * .24, '#fff'); circ(c, r * .3, -r * .15, r * .24, '#fff'); circ(c, -r * .3, -r * .15, r * .12, '#2d2a4a'); circ(c, r * .3, -r * .15, r * .12, '#2d2a4a'); tri([[-.08, 0], [.08, 0], [0, .16]], '#f5a742'); break;
    case 'chick': ell(c, 0, -r * .72, r * .06, r * .16, '#ffcf3f'); circ(c, 0, r * .1, r * .74, '#ffd94a'); eyes(c, r, -.02, .28); tri([[-.12, .12], [.12, .12], [0, .3]], '#f39a2b'); blush(c, r, .28); break;
    case 'pig': tri([[-.7, -.3], [-.65, -.85], [-.25, -.62]], '#f7a8bd'); tri([[.7, -.3], [.65, -.85], [.25, -.62]], '#f7a8bd'); circ(c, 0, .05, r * .76, '#ffbdcd'); eyes(c, r, -.12);
      ell(c, 0, r * .22, r * .26, r * .18, '#f794ad'); circ(c, -r * .09, r * .22, r * .045, '#c35a7a'); circ(c, r * .09, r * .22, r * .045, '#c35a7a'); break;
    case 'mouse': ear(-r * .55, -r * .5, r * .32, '#b9bfcc', '#ffc4d6'); ear(r * .55, -r * .5, r * .32, '#b9bfcc', '#ffc4d6'); ell(c, 0, r * .12, r * .66, r * .6, '#c8cdd8'); eyes(c, r, .04, .26); circ(c, 0, r * .3, r * .08, '#ff8fa3');
      c.strokeStyle = 'rgba(45,42,74,.45)'; c.lineWidth = r * .025; c.beginPath(); for (const s of [-1, 1]) { c.moveTo(s * r * .15, r * .32); c.lineTo(s * r * .65, r * .26); c.moveTo(s * r * .15, r * .36); c.lineTo(s * r * .65, r * .42); } c.stroke(); break;
    case 'penguin': circ(c, 0, .05, r * .76, '#3a3f58'); ell(c, -r * .22, r * .12, r * .3, r * .42, '#fff'); ell(c, r * .22, r * .12, r * .3, r * .42, '#fff'); eyes(c, r, 0, .24); tri([[-.12, .16], [.12, .16], [0, .32]], '#f5a742'); blush(c, r, .34); break;
    case 'koala': ear(-r * .62, -r * .35, r * .32, '#a3a9b6', '#e6c9d2'); ear(r * .62, -r * .35, r * .32, '#a3a9b6', '#e6c9d2'); circ(c, 0, .05, r * .7, '#b3b9c6'); eyes(c, r, -.08, .3); ell(c, 0, r * .18, r * .16, r * .22, '#3d3b4f'); break;
  }
}
function face(c, k, r) {
  const col = { smile: '#ffd34d', wink: '#ffc94d', wow: '#ffb84d', love: '#ff9fb2', sleepy: '#b9c8ff', laugh: '#ffd34d', cool: '#7fd4ff', tongue: '#ffcf6b', shy: '#ffc2d1', grumpy: '#c9b6ff', stars: '#ffe066', kiss: '#ffb3c6' }[k];
  const g = c.createRadialGradient(-r * .3, -r * .35, r * .1, 0, 0, r * .8); g.addColorStop(0, '#ffffff'); g.addColorStop(.25, col); g.addColorStop(1, col);
  circ(c, 0, 0, r * .78, g);
  const line = (w = .06) => { c.lineWidth = r * w; c.lineCap = 'round'; c.strokeStyle = INK; };
  const arcEye = (x, up) => { c.beginPath(); c.arc(x * r, -r * .08, r * .1, up ? Math.PI + .3 : .3, up ? -.3 : Math.PI - .3); line(); c.stroke(); };
  const heart = (x, y, s, f) => { c.save(); c.translate(x * r, y * r); c.scale(s * r / 30, s * r / 30); c.beginPath(); c.moveTo(0, 3); c.bezierCurveTo(-8, -3, -4, -9, 0, -5); c.bezierCurveTo(4, -9, 8, -3, 0, 3); c.fillStyle = f; c.fill(); c.restore(); };
  switch (k) {
    case 'smile': eyes(c, r, -.1, .28, .09); smileM(c, r, .2, .26); blush(c, r, .2); break;
    case 'wink': circ(c, -r * .28, -r * .1, r * .09, INK); arcEye(.28, true); smileM(c, r, .2, .24); blush(c, r, .2); break;
    case 'wow': eyes(c, r, -.12, .28, .11); ell(c, 0, r * .3, r * .1, r * .14, INK); break;
    case 'love': heart(-.28, -.08, 1.1, '#e83e6c'); heart(.28, -.08, 1.1, '#e83e6c'); smileM(c, r, .2, .26); break;
    case 'sleepy': arcEye(-.28, false); arcEye(.28, false); ell(c, 0, r * .3, r * .08, r * .06, INK); A.text(c, 'z', r * .5, -r * .5, { size: r * .32, weight: 800, color: '#6c7bd8' }); break;
    case 'laugh': arcEye(-.28, true); arcEye(.28, true); c.beginPath(); c.arc(0, r * .12, r * .3, 0, Math.PI); c.closePath(); c.fillStyle = INK; c.fill(); ell(c, 0, r * .34, r * .14, r * .07, '#ff7b95'); break;
    case 'cool': c.fillStyle = INK; A.rr(c, -r * .58, -r * .24, r * .5, r * .26, r * .1); c.fill(); A.rr(c, r * .08, -r * .24, r * .5, r * .26, r * .1); c.fill(); c.fillRect(-r * .1, -r * .2, r * .2, r * .05); smileM(c, r, .26, .2); break;
    case 'tongue': eyes(c, r, -.1, .28, .09); smileM(c, r, .2, .26); ell(c, r * .05, r * .42, r * .12, r * .14, '#ff7b95'); break;
    case 'shy': arcEye(-.28, false); arcEye(.28, false); blush(c, r, .14, 'rgba(255,90,130,.7)'); smileM(c, r, .26, .12); break;
    case 'grumpy': eyes(c, r, -.06, .28, .08); line(.05); c.beginPath(); c.moveTo(-r * .42, -r * .3); c.lineTo(-r * .16, -r * .22); c.moveTo(r * .42, -r * .3); c.lineTo(r * .16, -r * .22); c.stroke(); c.beginPath(); c.arc(0, r * .42, r * .16, Math.PI + .5, -.5); c.stroke(); break;
    case 'stars': for (const s of [-1, 1]) star(c, s * r * .28, -r * .08, r * .16, '#ff8a3d'); smileM(c, r, .2, .26); break;
    case 'kiss': eyes(c, r, -.1, .28, .09); heart(.32, .3, .9, '#e83e6c'); line(.05); c.beginPath(); c.arc(-r * .02, r * .24, r * .06, -1.2, 1.2); c.stroke(); blush(c, r, .2); break;
  }
}
function star(c, x, y, r, f, n = 5) { c.beginPath(); for (let i = 0; i < n * 2; i++) { const a = -Math.PI / 2 + i * Math.PI / n, rr = i % 2 ? r * .45 : r; c.lineTo(x + Math.cos(a) * rr, y + Math.sin(a) * rr); } c.closePath(); c.fillStyle = f; c.fill(); }
function sign(c, k, r) {
  const grad = (a, b) => { const g = c.createLinearGradient(0, -r, 0, r); g.addColorStop(0, a); g.addColorStop(1, b); return g; };
  switch (k) {
    case 'heart': c.save(); c.scale(r / 10, r / 10); c.beginPath(); c.moveTo(0, 7); c.bezierCurveTo(-13, -1, -8, -12, 0, -5); c.bezierCurveTo(8, -12, 13, -1, 0, 7); c.fillStyle = grad('#ff9ab4', '#e83e6c'); c.fill(); c.restore(); break;
    case 'star': star(c, 0, 0, r * .8, grad('#ffe27a', '#ffb23e')); break;
    case 'moon': c.beginPath(); c.arc(0, 0, r * .7, .9, Math.PI * 2 - .9); c.arc(r * .32, -r * .1, r * .55, Math.PI * 2 - 1.2, 1.2, true); c.closePath(); c.fillStyle = grad('#ffeaa0', '#f6c64e'); c.fill(); break;
    case 'sun': c.strokeStyle = '#ffb23e'; c.lineWidth = r * .1; c.lineCap = 'round'; c.beginPath(); for (let i = 0; i < 8; i++) { const a = i * Math.PI / 4; c.moveTo(Math.cos(a) * r * .55, Math.sin(a) * r * .55); c.lineTo(Math.cos(a) * r * .8, Math.sin(a) * r * .8); } c.stroke(); circ(c, 0, 0, r * .42, grad('#ffe27a', '#ffa83a')); break;
    case 'drop': c.beginPath(); c.moveTo(0, -r * .8); c.bezierCurveTo(r * .55, -r * .1, r * .6, r * .7, 0, r * .7); c.bezierCurveTo(-r * .6, r * .7, -r * .55, -r * .1, 0, -r * .8); c.fillStyle = grad('#9fe2ff', '#3b9cf0'); c.fill(); ell(c, -r * .18, r * .2, r * .08, r * .16, 'rgba(255,255,255,.7)'); break;
    case 'leaf': c.save(); c.rotate(-.6); c.beginPath(); c.moveTo(0, -r * .8); c.quadraticCurveTo(r * .62, 0, 0, r * .8); c.quadraticCurveTo(-r * .62, 0, 0, -r * .8); c.fillStyle = grad('#9be37f', '#45b25a'); c.fill(); c.strokeStyle = 'rgba(255,255,255,.6)'; c.lineWidth = r * .05; c.beginPath(); c.moveTo(0, -r * .6); c.lineTo(0, r * .7); c.stroke(); c.restore(); break;
    case 'flower': for (let i = 0; i < 6; i++) { const a = i * Math.PI / 3; circ(c, Math.cos(a) * r * .38, Math.sin(a) * r * .38, r * .3, '#ffb3d0'); } circ(c, 0, 0, r * .26, '#ffd34d'); break;
    case 'cloud': c.scale(1.3, 1.3); circ(c, -r * .3, r * .1, r * .32, '#dfe9ff'); circ(c, r * .05, -r * .12, r * .42, '#eef3ff'); circ(c, r * .38, r * .12, r * .3, '#dfe9ff'); c.fillStyle = '#e6eeff'; c.fillRect(-r * .3, r * .1, r * .68, r * .32); eyes(c, r * .7, .25, .28, .09); break;
    case 'bolt': c.beginPath(); [[.15, -.85], [-.45, .1], [-.05, .1], [-.2, .85], [.45, -.15], [.05, -.15], [.25, -.85]].forEach(([x, y], i) => (i ? c.lineTo(x * r, y * r) : c.moveTo(x * r, y * r))); c.closePath(); c.fillStyle = grad('#fff07a', '#ffb23e'); c.fill(); break;
    case 'crown': c.beginPath(); [[-.7, .45], [-.7, -.3], [-.35, .05], [0, -.55], [.35, .05], [.7, -.3], [.7, .45]].forEach(([x, y], i) => (i ? c.lineTo(x * r, y * r) : c.moveTo(x * r, y * r))); c.closePath(); c.fillStyle = grad('#ffe27a', '#f0a830'); c.fill(); circ(c, 0, r * .22, r * .1, '#ff7b95'); circ(c, -r * .4, r * .25, r * .07, '#7fd4ff'); circ(c, r * .4, r * .25, r * .07, '#7fd4ff'); break;
    case 'gem': c.beginPath(); [[-.6, -.25], [-.3, -.6], [.3, -.6], [.6, -.25], [0, .7]].forEach(([x, y], i) => (i ? c.lineTo(x * r, y * r) : c.moveTo(x * r, y * r))); c.closePath(); c.fillStyle = grad('#c7b6ff', '#7b6cf0'); c.fill();
      c.strokeStyle = 'rgba(255,255,255,.6)'; c.lineWidth = r * .04; c.beginPath(); c.moveTo(-r * .6, -r * .25); c.lineTo(r * .6, -r * .25); c.moveTo(-r * .15, -r * .6); c.lineTo(0, r * .7); c.lineTo(r * .15, -r * .6); c.stroke(); break;
    case 'note': c.fillStyle = '#7b6cf0'; c.fillRect(r * .05, -r * .6, r * .1, r * .9); c.fillRect(r * .05, -r * .6, r * .4, r * .12); ell(c, -r * .12, r * .3, r * .24, r * .18, '#7b6cf0', -.4); break;
  }
}
function picture(c, set, k, r) { if (set === 0) animal(c, k, r); else if (set === 1) face(c, k, r); else sign(c, k, r); }

/* ---------------- партия ---------------- */
function layout(cols, rows) {
  const top = LAND ? 112 : 230, bot = LAND ? 24 : 120, side = LAND ? 60 : 36, gap = LAND ? 16 : 18;
  const cw = Math.min((W - side * 2 - gap * (cols - 1)) / cols, ((H - top - bot - gap * (rows - 1)) / rows) * .78);
  const ch = cw / .78, gw = cols * cw + (cols - 1) * gap, gh = rows * ch + (rows - 1) * gap;
  return { cw, ch, gap, x0: (W - gw) / 2, y0: top + (H - top - bot - gh) / 2 };
}
function fresh(mode, level = 0, setI = (Math.random() * 3) | 0) {
  const [cols, rows] = LEVELS[level % LEVELS.length], n = cols * rows / 2;
  const items = SETS[setI].items.slice().sort(() => Math.random() - .5).slice(0, n);
  const deck = items.concat(items).sort(() => Math.random() - .5);
  const L = layout(cols, rows);
  S = { mode, level, setI, cols, rows, L, cards: deck.map((k, i) => ({ k, i, open: 0, want: 0, done: false, pop: 0 })), sel: [], moves: 0, pairs: 0, n,
    wrongT: 0, peek: mode === 'play' ? 2.2 : 0, focus: 0, kb: false, end: 0, t: 0, demo: 0, combo: 0, score: 0 };
  return S;
}
function cardRect(i) { const { L, cols } = S, x = i % cols, y = (i / cols) | 0; return [L.x0 + x * (L.cw + L.gap), L.y0 + y * (L.ch + L.gap), L.cw, L.ch]; }
function flip(g, i) {
  const c = S.cards[i]; if (c.done || c.want || S.peek > 0 || S.end) return;
  if (S.sel.length === 2) { for (const j of S.sel) S.cards[j].want = 0; S.sel = []; S.wrongT = 0; }
  c.want = 1; S.sel.push(i); g.sfx('click', { vol: .4, pitch: 1.1 + S.sel.length * .1 });
  if (S.sel.length === 2) {
    S.moves++;
    const [a, b] = S.sel.map((j) => S.cards[j]);
    if (a.k === b.k) {
      a.done = b.done = true; a.pop = b.pop = .001; S.sel = []; S.pairs++; S.combo++;
      S.score += 100 + Math.min(4, S.combo - 1) * 25;
      g.sfx('coin'); for (const cc of [a, b]) { const [x, y, w, h] = cardRect(cc.i); g.fx.burst(x + w / 2, y + h / 2, { n: 10, colors: ['#ffd27a', '#ff9ab4', '#a9b8ff', '#fff'], speed: 220, size: 7, shape: 'star', life: .7 }); }
      if (S.pairs === S.n) S.end = .001;
    } else { S.wrongT = .9; S.combo = 0; g.sfx('hurt', { vol: .2, pitch: 1.4 }); }
  }
}

/* ---------------- экраны ---------------- */
function titleScreen(g) {
  fresh('title', 1); g.setPlaying(false);
  g.screen({
    kicker: A.framed ? 'Досуг' : 'Аркада', title: 'Найди пару',
    html: `<p>Под рубашками — зверята, рожицы и знаки, каждый по два. Откройте две карточки: одинаковые останутся открытыми, разные закроются. В начале уровня все на миг покажутся — запоминайте!</p>${g.best ? `<p class="record">Рекорд: ${g.best.toLocaleString('ru-RU')}</p>` : ''}`,
    button: 'Играть', onGo: () => { total = 0; start(g, 0); }
  });
}
function start(g, level) { fresh('play', level); g.fx.clear(); g.setPlaying(true); g.playMusic(); }
function levelDone(g) {
  S.mode = 'over'; g.setPlaying(false);
  const extra = Math.max(0, S.moves - S.n), bonus = Math.max(0, S.n * 40 - extra * 15), stars = extra <= S.n * .4 ? 3 : extra <= S.n ? 2 : 1;
  total += S.score + bonus; const rec = g.submit(total);
  for (let k = 0; k < 6; k++) g.fx.burst(Math.random() * W, H * .3 + Math.random() * H * .4, { n: 12, colors: ['#ffd27a', '#ff9ab4', '#a9b8ff', '#9be37f'], speed: 320, size: 8, life: 1, gravity: 500, shape: 'star' });
  g.sfx('win');
  g.screen({
    kicker: `Уровень ${S.level + 1} · ${SETS[S.setI].name}`, title: rec ? 'Новый рекорд!' : ['Неплохо!', 'Здорово!', 'Отличная память!'][stars - 1],
    html: `<p style="font-size:30px;margin:0 0 6px">${'★'.repeat(stars)}<span style="opacity:.25">${'★'.repeat(3 - stars)}</span></p><div class="score">${total.toLocaleString('ru-RU')}</div><p>ходов ${S.moves} · пар ${S.n}</p>`,
    button: 'Дальше', onGo: () => start(g, S.level + 1), alt: { label: 'Заново', onGo: () => { total = 0; start(g, 0); } }
  });
}

/* ---------------- цикл ---------------- */
function update(g, dt) {
  S.t += dt;
  for (const c of S.cards) { c.open += (c.want || c.done || S.peek > 0 ? 1 : -1) * dt * 5; c.open = Math.max(0, Math.min(1, c.open)); if (c.pop) { c.pop += dt * 2.5; if (c.pop >= 1) c.pop = 0; } }
  if (S.mode === 'title') { S.demo += dt; if (S.demo > .55) { S.demo = 0; const hidden = S.cards.filter((c) => !c.done && !c.want); if (!hidden.length) { fresh('title', 1, S.setI); return; }
      if (S.sel.length === 2) { for (const j of S.sel) S.cards[j].want = 0; S.sel = []; }
      const c = A.pick(hidden); c.want = 1; S.sel.push(c.i); if (S.sel.length === 2) { const [a, b] = S.sel.map((j) => S.cards[j]); if (a.k === b.k) { a.done = b.done = true; S.sel = []; } } } return; }
  if (S.mode !== 'play') return;
  if (S.peek > 0) { S.peek -= dt; return; }
  if (S.end) { S.end += dt; if (S.end > 1.1) levelDone(g); return; }
  if (S.wrongT > 0) { S.wrongT -= dt; if (S.wrongT <= 0) { for (const j of S.sel) S.cards[j].want = 0; S.sel = []; } }
  const inp = g.input;
  const mv = (dx, dy) => { S.kb = true; const x = (S.focus % S.cols + dx + S.cols) % S.cols, y = ((S.focus / S.cols | 0) + dy + S.rows) % S.rows; S.focus = y * S.cols + x; };
  if (inp.pressed('left')) mv(-1, 0); if (inp.pressed('right')) mv(1, 0); if (inp.pressed('up')) mv(0, -1); if (inp.pressed('down')) mv(0, 1);
  if (S.kb && (inp.pressed('action') || inp.pressed('start'))) flip(g, S.focus);
  if (inp.tap) { S.kb = false; for (const c of S.cards) { const [x, y, w, h] = cardRect(c.i); if (inp.tap.x >= x && inp.tap.x <= x + w && inp.tap.y >= y && inp.tap.y <= y + h) { flip(g, c.i); break; } } }
}
function drawCard(ctx, g, c) {
  const [x, y, w, h] = cardRect(c.i), k = A.ease ? A.ease.inOut ? A.ease.inOut(c.open) : c.open : c.open, sx = Math.cos(k * Math.PI), face = k > .5;
  const pop = c.pop ? 1 + Math.sin(c.pop * Math.PI) * .08 : 1, wrong = S.wrongT > 0 && S.sel.includes(c.i) && face ? Math.sin(S.t * 40) * 3 * Math.min(1, S.wrongT * 2) : 0;
  ctx.save(); ctx.translate(x + w / 2 + wrong, y + h / 2); ctx.scale(Math.max(.03, Math.abs(sx)) * pop, pop);
  ctx.shadowColor = 'rgba(80,60,140,.22)'; ctx.shadowBlur = 14 * g.scale; ctx.shadowOffsetY = 6 * g.scale;
  A.rr(ctx, -w / 2, -h / 2, w, h, Math.min(w, h) * .16);
  if (face) { ctx.fillStyle = c.done ? '#fffaf0' : '#ffffff'; ctx.fill(); ctx.shadowColor = 'transparent';
    if (c.done) { ctx.lineWidth = 3; ctx.strokeStyle = 'rgba(255,196,90,.7)'; ctx.stroke(); }
    picture(ctx, S.setI, c.k, Math.min(w, h) * .42);
  } else {
    const gr = ctx.createLinearGradient(-w / 2, -h / 2, w / 2, h / 2); gr.addColorStop(0, '#8b7cf6'); gr.addColorStop(1, '#e58fc6'); ctx.fillStyle = gr; ctx.fill(); ctx.shadowColor = 'transparent';
    ctx.save(); ctx.clip(); ctx.globalAlpha = .18; for (let yy = -h / 2 + 10; yy < h / 2; yy += 26) for (let xx = -w / 2 + ((yy / 26 | 0) % 2) * 13; xx < w / 2; xx += 26) star(ctx, xx, yy, 5, '#fff', 4); ctx.restore();
    ctx.lineWidth = 3; ctx.strokeStyle = 'rgba(255,255,255,.55)'; A.rr(ctx, -w / 2 + 6, -h / 2 + 6, w - 12, h - 12, Math.min(w, h) * .12); ctx.stroke();
    circ(ctx, 0, 0, Math.min(w, h) * .14, 'rgba(255,255,255,.85)'); star(ctx, 0, 0, Math.min(w, h) * .09, '#b48cf0');
  }
  ctx.restore();
  if (S.kb && S.focus === c.i && S.mode === 'play') { ctx.setLineDash([8, 7]); ctx.lineWidth = 3; ctx.strokeStyle = 'rgba(123,108,240,.8)'; A.rr(ctx, x - 6, y - 6, w + 12, h + 12, Math.min(w, h) * .18); ctx.stroke(); ctx.setLineDash([]); }
}
function draw(ctx, g) {
  const bg = ctx.createLinearGradient(0, 0, 0, H); bg.addColorStop(0, '#fbeffd'); bg.addColorStop(.5, '#eef0ff'); bg.addColorStop(1, '#fff3e6'); ctx.fillStyle = bg; ctx.fillRect(0, 0, W, H);
  for (let i = 0; i < 9; i++) { const x = (i * 263 + S.t * 8) % (W + 80) - 40, y = 60 + (i * 157) % (H - 120); ctx.globalAlpha = .18; circ(ctx, x, y, 14 + (i % 3) * 8, ['#ffc4d6', '#c9d4ff', '#ffe6a8'][i % 3]); } ctx.globalAlpha = 1;
  const tx = LAND ? 60 : W / 2, al = LAND ? 'left' : 'center';
  A.text(ctx, 'Найди пару', tx, LAND ? 58 : 100, { align: al, size: LAND ? 44 : 56, weight: 900, color: INK });
  if (S.mode !== 'title') {
    const info = `${SETS[S.setI].name} · уровень ${S.level + 1} · пар ${S.pairs} из ${S.n} · ходов ${S.moves}`;
    A.text(ctx, info, LAND ? W - 60 : W / 2, LAND ? 58 : 158, { align: LAND ? 'right' : 'center', size: LAND ? 22 : 24, weight: 600, color: MUTED });
  }
  for (const c of S.cards) drawCard(ctx, g, c);
  if (S.peek > 0 && S.mode === 'play') { const a = Math.min(1, S.peek * 2); A.text(ctx, 'Запомните!', W / 2, LAND ? 96 : 200, { size: LAND ? 26 : 32, weight: 800, color: `rgba(123,108,240,${a})` }); }
}

A.game({
  id: 'pairs', tone: 'light', title: 'Найди пару', width: W, height: H, orientation: LAND ? 'landscape' : 'portrait', music: 'candy',
  help: { desktop: 'Щёлкните карточку — откроется · стрелки и <kbd>Enter</kbd> — тоже', short: 'Откройте две одинаковые', touch: 'Коснитесь карточки — откроется' },
  init(g) { titleScreen(g); window.__pairs = () => S; window.__pairsDraw = (c, set, k, r) => picture(c, set, k, r); },
  update, draw
});
})();
