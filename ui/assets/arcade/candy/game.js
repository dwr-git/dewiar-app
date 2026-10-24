/* Конфетки — «три в ряд»: поменяйте местами две соседние конфеты, чтобы собрать три и больше одинаковых в ряд —
   они лопаются, сверху падают новые, бывают каскады. 25 ходов на партию, звёзды за очки. Управление: потянуть конфету
   к соседу (или коснуться одной, потом соседней); с клавиатуры — стрелки и пробел (выбрать, затем стрелка — куда). */
(() => {
'use strict';
const A = Arcade;
/* Широкое окно (лист «Досуг» на компьютере) — своя раскладка 1280×720: доска посередине во всю высоту, слева —
   название, очки, ходы и конфетки-друзья, справа — банка звёзд, рекорд и подсказка. Книжная — как была. */
const LAND = (() => { try { return innerWidth > (innerHeight - 110) * 1.15; } catch (e) { return false; } })();
const W = LAND ? 1280 : 720, H = LAND ? 720 : 1280, N = 8, CELL = LAND ? 74 : 80, BX = (W - N * CELL) / 2, BY = LAND ? 64 : 330;
const CL = 165, CR = W - 165;                   // широкая: середины левой и правой колонок
const INK = '#5a2a4a';
const KINDS = [
  { c: ['#ff8fab', '#e83e6c'], shape: 'heart' }, { c: ['#ffd56b', '#f5a623'], shape: 'star' }, { c: ['#9ee6a0', '#3fbf6a'], shape: 'drop' },
  { c: ['#8ecbff', '#3c8ef0'], shape: 'round' }, { c: ['#cfa8ff', '#8a52e8'], shape: 'gem' }, { c: ['#ffb38a', '#f2713a'], shape: 'square' }
];
const MOVES = 25, STARS = [1500, 3000, 5000];
let S = null, ID = 1;

const rnd = () => (Math.random() * KINDS.length) | 0;
function cellAt(x, y) { return x >= 0 && y >= 0 && x < N && y < N ? S.g[y][x] : null; }
function fresh(mode) {
  S = { mode, g: [], score: 0, shown: 0, moves: MOVES, sel: null, cur: { x: 3, y: 3 }, phase: 'idle', t: 0, swap: null, chain: 0, drag: null, over: 0, demo: 0, hint: 0, hintAt: null, starsShown: 0 };
  do {
    S.g = Array.from({ length: N }, (_, y) => Array.from({ length: N }, (_, x) => ({ id: ID++, k: rnd(), oy: 0, pop: -1 })));
    for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) while (matchAt(x, y)) S.g[y][x].k = rnd();
  } while (!findMove());
  return S;
}
function matchAt(x, y) {
  const k = S.g[y][x].k;
  return (x >= 2 && S.g[y][x - 1].k === k && S.g[y][x - 2].k === k) || (y >= 2 && S.g[y - 1][x].k === k && S.g[y - 2][x].k === k);
}
function findMatches() {
  const hit = new Set();
  for (let y = 0; y < N; y++) { let run = 1; for (let x = 1; x <= N; x++) { if (x < N && S.g[y][x] && S.g[y][x - 1] && S.g[y][x].k === S.g[y][x - 1].k) run++; else { if (run >= 3) for (let k = x - run; k < x; k++) hit.add(y * N + k); run = 1; } } }
  for (let x = 0; x < N; x++) { let run = 1; for (let y = 1; y <= N; y++) { if (y < N && S.g[y][x] && S.g[y - 1][x] && S.g[y][x].k === S.g[y - 1][x].k) run++; else { if (run >= 3) for (let k = y - run; k < y; k++) hit.add(k * N + x); run = 1; } } }
  return hit;
}
function swapCells(a, b) { const t = S.g[a.y][a.x]; S.g[a.y][a.x] = S.g[b.y][b.x]; S.g[b.y][b.x] = t; }
function findMove() {
  for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) for (const [dx, dy] of [[1, 0], [0, 1]]) {
    const b = { x: x + dx, y: y + dy }; if (b.x >= N || b.y >= N) continue;
    swapCells({ x, y }, b); const ok = findMatches().size > 0; swapCells({ x, y }, b);
    if (ok) return { a: { x, y }, b };
  }
  return null;
}
function trySwap(g, a, b) {
  if (S.phase !== 'idle' || Math.abs(a.x - b.x) + Math.abs(a.y - b.y) !== 1 || b.x < 0 || b.y < 0 || b.x >= N || b.y >= N) return;
  S.sel = null; S.hint = 0; S.hintAt = null;
  S.phase = 'swap'; S.t = 0; S.swap = { a, b, back: false };
  g.sfx('whoosh', { vol: .5 });
}
function afterSwap(g) {
  const { a, b, back } = S.swap;
  swapCells(a, b);
  if (back) { S.phase = 'idle'; S.swap = null; return; }
  const hit = findMatches();
  if (!hit.size) { S.swap = { a, b, back: true }; S.phase = 'swap'; S.t = 0; g.sfx('click', { vol: .5 }); return; }   // не сложилось — едут обратно (сетка уже поменяна; в конце вернётся)
  S.swap = null; if (S.mode === 'play') S.moves--; S.chain = 0;
  startClear(g, hit);
}
function startClear(g, hit) {
  S.chain++;
  const pts = hit.size * 20 * S.chain + (hit.size >= 5 ? 200 : hit.size === 4 ? 60 : 0);
  if (S.mode === 'play') S.score += pts;
  let sx = 0, sy = 0;
  for (const i of hit) {
    const x = i % N, y = (i / N) | 0, c = S.g[y][x]; c.pop = 0; sx += x; sy += y;
    if (S.mode === 'play') g.fx.burst(BX + (x + .5) * CELL, BY + (y + .5) * CELL, { n: 5, colors: [KINDS[c.k].c[0], '#fff', KINDS[c.k].c[1]], speed: 240, size: 7, life: .55, shape: Math.random() < .5 ? 'star' : 'circle' });
  }
  if (S.mode === 'play') {
    g.sfx('pling', { pitch: 1 + S.chain * .12, vol: .7 });
    g.fx.text(BX + (sx / hit.size + .5) * CELL, BY + (sy / hit.size + .5) * CELL, '+' + pts, { size: 30 + Math.min(4, S.chain) * 4, color: '#fff' });
    if (S.chain >= 3) { g.sfx('coin'); g.fx.text(W / 2, LAND ? BY + 60 : BY - 30, ['Сладко!', 'Вкусно!', 'Конфетно!', 'Ого-го!'][Math.min(3, S.chain - 3)], { size: 52, color: '#ffe066' }); }
  }
  S.phase = 'clear'; S.t = 0;
}
function collapse() {
  for (let x = 0; x < N; x++) {
    let write = N - 1;
    for (let y = N - 1; y >= 0; y--) { const c = S.g[y][x]; if (c && c.pop < 0) { if (write !== y) { S.g[write][x] = c; c.oy -= (write - y); S.g[y][x] = null; } write--; } else if (c) S.g[y][x] = null; }
    let k = 1;
    for (let y = write; y >= 0; y--) { S.g[y][x] = { id: ID++, k: rnd(), oy: -(write + 1) - .25 * (k - 1), pop: -1 }; k++; }   // новые — сверху, лесенкой
  }
  S.phase = 'fall'; S.t = 0;
}

/* ---------------- экраны ---------------- */
function titleScreen(g) {
  fresh('title'); g.setPlaying(false);
  g.screen({
    kicker: A.framed ? 'Досуг' : 'Аркада', title: 'Конфетки',
    html: `<p>Меняйте соседние конфеты местами — три одинаковых в ряд лопаются. ${MOVES} ходов, звёзды за очки.</p>${g.best ? `<p class="record">Рекорд: ${g.best.toLocaleString('ru-RU')}</p>` : ''}`,
    button: 'Играть', onGo: () => start(g)
  });
}
function start(g) { fresh('play'); g.fx.clear(); g.setPlaying(true); g.playMusic(); }
const stars = () => STARS.filter((s) => S.score >= s).length;
function finish(g) {
  S.mode = 'over'; g.setPlaying(false); g.stopMusic();
  const st = stars(), rec = g.submit(S.score);
  g.sfx(st ? 'win' : 'lose');
  g.screen({
    kicker: 'Ходы закончились', title: rec ? 'Новый рекорд!' : st === 3 ? 'Сладкая победа!' : st ? 'Вкусно!' : 'Ещё разок?',
    html: `<div class="score">${S.score.toLocaleString('ru-RU')}</div><p style="font-size:30px;margin:0 0 6px">${'★'.repeat(st)}${'☆'.repeat(3 - st)}</p><p>${st < 3 ? `до следующей звезды — ${(STARS[st] - S.score).toLocaleString('ru-RU')}` : 'все три звезды!'}</p>`,
    button: 'Ещё раз', onGo: () => start(g), alt: { label: A.framed ? 'К играм' : 'В аркаду', onGo: () => A.home('../index.html') }
  });
}

/* ---------------- цикл ---------------- */
function cellOf(p) { const x = Math.floor((p.x - BX) / CELL), y = Math.floor((p.y - BY) / CELL); return x >= 0 && y >= 0 && x < N && y < N ? { x, y } : null; }
function input(g) {
  const inp = g.input, pt = inp.pointer;
  if (pt.justDown) { const c = cellOf(pt); S.drag = c ? { c, sx: pt.x, sy: pt.y, used: false } : null; }
  if (pt.down && S.drag && !S.drag.used) {
    const dx = pt.x - S.drag.sx, dy = pt.y - S.drag.sy;
    if (Math.hypot(dx, dy) > CELL * .4) { S.drag.used = true; const c = S.drag.c; trySwap(g, c, Math.abs(dx) > Math.abs(dy) ? { x: c.x + Math.sign(dx), y: c.y } : { x: c.x, y: c.y + Math.sign(dy) }); }
  }
  if (inp.tap) {
    const c = cellOf(inp.tap);
    if (c) { if (S.sel && Math.abs(S.sel.x - c.x) + Math.abs(S.sel.y - c.y) === 1) trySwap(g, S.sel, c); else { S.sel = (S.sel && S.sel.x === c.x && S.sel.y === c.y) ? null : c; g.sfx('click', { vol: .4 }); } }
  }
  if (pt.justUp) S.drag = null;
  const D = { left: [-1, 0], right: [1, 0], up: [0, -1], down: [0, 1] };
  for (const d in D) if (inp.pressed(d)) {
    if (S.sel) trySwap(g, S.sel, { x: S.sel.x + D[d][0], y: S.sel.y + D[d][1] });
    else S.cur = { x: A.clamp(S.cur.x + D[d][0], 0, N - 1), y: A.clamp(S.cur.y + D[d][1], 0, N - 1) };
  }
  if (inp.pressed('action')) { S.sel = S.sel ? null : { ...S.cur }; g.sfx('click', { vol: .4 }); }
}
function update(g, dt) {
  S.shown += (S.score - S.shown) * Math.min(1, dt * 8);
  S.t += dt;
  if (S.mode === 'over') return;
  if (S.phase === 'swap' && S.t >= .16) afterSwap(g);
  else if (S.phase === 'clear' && S.t >= .22) collapse();
  else if (S.phase === 'fall') {
    let moving = false;
    for (const row of S.g) for (const c of row) if (c && c.oy < 0) { c.oy = Math.min(0, c.oy + dt * 14); moving = moving || c.oy < 0; }
    if (!moving) {
      if (S.mode === 'play') g.sfx('land', { vol: .3 });
      const hit = findMatches();
      if (hit.size) startClear(g, hit);
      else {
        S.phase = 'idle';
        if (!findMove()) { fresh(S.mode === 'play' ? 'play' : 'title'); }        // ходов нет — перемешиваем доску
        if (S.mode === 'play') {
          const st = stars(); if (st > S.starsShown) { S.starsShown = st; g.sfx('power'); g.fx.text(W / 2, BY + N * CELL / 2, '★'.repeat(st), { size: 90, color: '#ffd84d', life: 1.2 }); }
          if (S.moves <= 0) S.over = .001;
        }
      }
    }
  }
  if (S.over) { S.over += dt; if (S.over > .8 && S.phase === 'idle') finish(g); return; }
  if (S.mode === 'title') { S.demo += dt; if (S.demo > 1.1 && S.phase === 'idle') { S.demo = 0; const m = findMove(); if (m) trySwap(g, m.a, m.b); } return; }
  if (S.phase === 'idle') {
    input(g);
    S.hint += dt; if (S.hint > 6 && !S.hintAt) S.hintAt = findMove();
  }
}

/* ---------------- отрисовка ---------------- */
function candy(ctx, k, x, y, s, t) {
  const K = KINDS[k], r = CELL * .36;
  ctx.save(); ctx.translate(x, y); ctx.scale(s, s);
  ctx.shadowColor = 'rgba(90,40,70,.25)'; ctx.shadowBlur = 8 * S.sc; ctx.shadowOffsetY = 4 * S.sc;
  const gr = ctx.createRadialGradient(-r * .35, -r * .45, r * .1, 0, 0, r * 1.2); gr.addColorStop(0, K.c[0]); gr.addColorStop(1, K.c[1]);
  ctx.fillStyle = gr; ctx.beginPath();
  if (K.shape === 'heart') { ctx.moveTo(0, r * .9); ctx.bezierCurveTo(-r * 1.4, 0, -r * .7, -r * 1.1, 0, -r * .45); ctx.bezierCurveTo(r * .7, -r * 1.1, r * 1.4, 0, 0, r * .9); }
  else if (K.shape === 'star') A.star(ctx, 0, 0, r * 1.08, 5, .55);
  else if (K.shape === 'drop') { ctx.moveTo(0, -r * 1.05); ctx.bezierCurveTo(r * .9, -r * .1, r * .95, r * .95, 0, r * .95); ctx.bezierCurveTo(-r * .95, r * .95, -r * .9, -r * .1, 0, -r * 1.05); }
  else if (K.shape === 'gem') { ctx.moveTo(0, -r); ctx.lineTo(r, -r * .2); ctx.lineTo(0, r); ctx.lineTo(-r, -r * .2); ctx.closePath(); }
  else if (K.shape === 'square') A.rr(ctx, -r * .85, -r * .85, r * 1.7, r * 1.7, r * .45);
  else ctx.arc(0, 0, r * .92, 0, Math.PI * 2);
  ctx.fill(); ctx.shadowColor = 'transparent';
  ctx.lineWidth = 3; ctx.strokeStyle = 'rgba(90,40,70,.35)'; ctx.stroke();
  ctx.beginPath(); ctx.ellipse(-r * .3, -r * .4, r * .28, r * .14, -.5, 0, Math.PI * 2); ctx.fillStyle = 'rgba(255,255,255,.75)'; ctx.fill();
  // милое личико
  ctx.fillStyle = 'rgba(70,25,50,.8)';
  const blink = Math.sin(t * 1.7 + k * 1.3) > .985 ? .2 : 1;
  for (const ex of [-r * .25, r * .25]) { ctx.beginPath(); ctx.ellipse(ex, r * .05, r * .07, r * .1 * blink, 0, 0, Math.PI * 2); ctx.fill(); }
  ctx.beginPath(); ctx.arc(0, r * .2, r * .13, .15 * Math.PI, .85 * Math.PI); ctx.lineWidth = 2.5; ctx.strokeStyle = 'rgba(70,25,50,.8)'; ctx.stroke();
  ctx.restore();
}
/* широкая раскладка: боковые колонки */
function card(ctx, x, y, w, h, val, lbl, vs = 44) {
  A.rr(ctx, x, y, w, h, 30); ctx.fillStyle = 'rgba(255,255,255,.8)'; ctx.fill();
  A.text(ctx, val, x + w / 2, y + h * .44, { size: vs, weight: 900, color: INK });
  A.text(ctx, lbl, x + w / 2, y + h * .8, { size: 21, weight: 600, color: 'rgba(90,42,74,.55)' });
}
function sides(ctx, g, t) {
  const play = S.mode !== 'title';
  // слева: название, очки и ходы, конфетки-друзья
  A.text(ctx, 'Конфетки', CL, 104, { size: 50, weight: 900, color: '#fff', stroke: INK, strokeW: 10 });
  if (play) {
    card(ctx, CL - 120, 162, 240, 112, Math.round(S.shown).toLocaleString('ru-RU'), 'очки');
    card(ctx, CL - 120, 294, 240, 112, String(S.moves), S.moves <= 5 && S.mode === 'play' ? 'ходов — скоро конец' : 'ходов');
  } else {
    A.text(ctx, 'три в ряд', CL, 164, { size: 26, weight: 700, color: 'rgba(90,42,74,.6)' });
  }
  const bob = (k) => Math.sin(t * 2.2 + k) * 6;
  candy(ctx, 1, CL - 80, 574 + bob(1), 1.25, t);
  candy(ctx, 2, CL + 82, 580 + bob(2.4), 1.2, t);
  candy(ctx, 0, CL, 530 + bob(0), 1.75, t);
  // справа: банка звёзд, рекорд, подсказка
  const px = CR - 125, top = 64, ph = 384;
  A.rr(ctx, px, top, 250, ph, 30); ctx.fillStyle = 'rgba(255,255,255,.8)'; ctx.fill();
  A.text(ctx, 'звёзды', CR, top + 38, { size: 22, weight: 700, color: 'rgba(90,42,74,.55)' });
  const bx = px + 52, bw = 28, by0 = top + 84, by1 = top + ph - 34, bh = by1 - by0, k = Math.min(1, S.shown / STARS[2]);
  A.rr(ctx, bx, by0, bw, bh, bw / 2); ctx.fillStyle = 'rgba(255,225,238,.9)'; ctx.fill();
  if (k > 0) {
    const fh = Math.max(bw, bh * k);
    A.rr(ctx, bx, by1 - fh, bw, fh, bw / 2); const gr = ctx.createLinearGradient(0, by1, 0, by0); gr.addColorStop(0, '#ff8fab'); gr.addColorStop(1, '#ffd56b'); ctx.fillStyle = gr; ctx.fill();
  }
  for (const s of STARS) {
    const y = by1 - bh * s / STARS[2] + (s === STARS[2] ? 14 : 0), got = S.shown >= s;
    ctx.fillStyle = 'rgba(255,255,255,.95)'; ctx.fillRect(bx + 4, y - 1.5, bw - 8, 3);
    A.star(ctx, bx + bw + 40, y, 21, 5, .5); ctx.fillStyle = got ? '#ffd84d' : '#fff'; ctx.fill(); ctx.lineWidth = 3; ctx.strokeStyle = INK; ctx.stroke();
    A.text(ctx, s.toLocaleString('ru-RU'), bx + bw + 74, y + 1, { align: 'left', size: 26, weight: 800, color: got ? INK : 'rgba(90,42,74,.45)' });
  }
  card(ctx, px, 472, 250, 104, Math.max(g.best || 0, S.mode === 'title' ? 0 : S.score).toLocaleString('ru-RU'), 'рекорд', 38);
  const tip = A.isTouch ? ['Потяните конфету', 'к соседке'] : ['Перетащите конфету', 'или щёлкните', 'две соседние'];
  tip.forEach((l, i) => A.text(ctx, l, CR, 618 + i * 28 - (tip.length - 2) * 14, { size: 21, weight: 500, color: 'rgba(90,42,74,.6)' }));
}
function draw(ctx, g) {
  S.sc = g.scale; const t = g.t;
  const bg = ctx.createLinearGradient(0, 0, 0, H); bg.addColorStop(0, '#ffe3ef'); bg.addColorStop(1, '#e9e1ff');
  ctx.fillStyle = bg; ctx.fillRect(0, 0, W, H);
  for (let i = 0; i < (LAND ? 28 : 18); i++) { ctx.globalAlpha = .35; ctx.beginPath(); ctx.arc((i * 137) % W, (i * 271 + t * 12) % H, 10 + (i % 4) * 6, 0, Math.PI * 2); ctx.fillStyle = ['#fff', '#ffd1e3', '#d9ccff'][i % 3]; ctx.fill(); }
  ctx.globalAlpha = 1;
  if (LAND) sides(ctx, g, t);
  else A.text(ctx, 'Конфетки', W / 2, 96, { size: 62, weight: 900, color: '#fff', stroke: INK, strokeW: 12 });
  if (!LAND && S.mode !== 'title') {
    for (const [i, lbl, val] of [[0, 'очки', Math.round(S.shown).toLocaleString('ru-RU')], [1, 'ходов', String(S.moves)]]) {
      const x = i ? W / 2 + 20 : W / 2 - 260, y = 150;
      A.rr(ctx, x, y, 240, 96, 30); ctx.fillStyle = 'rgba(255,255,255,.8)'; ctx.fill();
      A.text(ctx, val, x + 120, y + 42, { size: 38, weight: 900, color: INK });
      A.text(ctx, lbl, x + 120, y + 78, { size: 18, weight: 600, color: 'rgba(90,42,74,.55)' });
    }
    // полоска до звёзд
    const pw = N * CELL, k = Math.min(1, S.shown / STARS[2]);
    A.rr(ctx, BX, 266, pw, 22, 11); ctx.fillStyle = 'rgba(255,255,255,.6)'; ctx.fill();
    if (k > 0) { A.rr(ctx, BX, 266, Math.max(22, pw * k), 22, 11); const gr = ctx.createLinearGradient(BX, 0, BX + pw, 0); gr.addColorStop(0, '#ff8fab'); gr.addColorStop(1, '#ffd56b'); ctx.fillStyle = gr; ctx.fill(); }
    for (const s of STARS) { const x = BX + pw * s / STARS[2]; A.star(ctx, Math.min(x, BX + pw - 6), 277, 16, 5, .5); ctx.fillStyle = S.shown >= s ? '#ffd84d' : 'rgba(255,255,255,.9)'; ctx.fill(); ctx.lineWidth = 2.5; ctx.strokeStyle = INK; ctx.stroke(); }
  }
  // доска
  A.rr(ctx, BX - 14, BY - 14, N * CELL + 28, N * CELL + 28, 34); ctx.fillStyle = 'rgba(255,255,255,.55)'; ctx.fill();
  for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) { A.rr(ctx, BX + x * CELL + 3, BY + y * CELL + 3, CELL - 6, CELL - 6, 18); ctx.fillStyle = (x + y) % 2 ? 'rgba(255,255,255,.55)' : 'rgba(255,240,248,.8)'; ctx.fill(); }
  ctx.save(); A.rr(ctx, BX - 4, BY - 4, N * CELL + 8, N * CELL + 8, 26); ctx.clip();
  const sw = S.phase === 'swap' && S.swap ? S.swap : null, sk = sw ? A.ease.inOutSine(Math.min(1, S.t / .16)) : 0;
  for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) {
    const c = S.g[y][x]; if (!c) continue;
    let px = x, py = y + c.oy;
    if (sw) { if (sw.a.x === x && sw.a.y === y) { px = A.lerp(x, sw.b.x, sk); py = A.lerp(y, sw.b.y, sk); } else if (sw.b.x === x && sw.b.y === y) { px = A.lerp(x, sw.a.x, sk); py = A.lerp(y, sw.a.y, sk); } }
    let s = 1;
    if (c.pop >= 0) { s = 1 + Math.sin(Math.min(1, S.t / .22) * Math.PI) * .25 - Math.min(1, S.t / .22) * .9; }
    if (S.sel && S.sel.x === x && S.sel.y === y) s = 1.1 + Math.sin(t * 8) * .05;
    const hint = S.hintAt && ((S.hintAt.a.x === x && S.hintAt.a.y === y) || (S.hintAt.b.x === x && S.hintAt.b.y === y));
    candy(ctx, c.k, BX + (px + .5) * CELL, BY + (py + .5) * CELL + (hint ? Math.sin(t * 9) * 4 : 0), Math.max(0, s), t);
  }
  ctx.restore();
  if (S.sel) { A.rr(ctx, BX + S.sel.x * CELL + 2, BY + S.sel.y * CELL + 2, CELL - 4, CELL - 4, 20); ctx.lineWidth = 4; ctx.strokeStyle = '#fff'; ctx.stroke(); }
  if (S.mode === 'play' && !g.input.mouseActive && !A.isTouch) { A.rr(ctx, BX + S.cur.x * CELL + 4, BY + S.cur.y * CELL + 4, CELL - 8, CELL - 8, 18); ctx.lineWidth = 3; ctx.setLineDash([8, 6]); ctx.strokeStyle = INK; ctx.stroke(); ctx.setLineDash([]); }
  if (!LAND) A.text(ctx, A.isTouch ? 'Потяните конфету к соседке' : 'Перетащите конфету или щёлкните две соседние', W / 2, BY + N * CELL + 70, { size: 24, weight: 500, color: 'rgba(90,42,74,.6)' });
}

A.game({
  id: 'candy', tone: 'light', title: 'Конфетки', width: W, height: H, orientation: LAND ? 'landscape' : 'portrait', music: 'candy',
  help: { desktop: 'Перетащите конфету к соседней · или <kbd>←</kbd><kbd>→</kbd><kbd>↑</kbd><kbd>↓</kbd> и <kbd>Пробел</kbd> · <kbd>P</kbd> пауза · <kbd>M</kbd> музыка', short: 'Перетащите конфету к соседней', touch: 'Потяните конфету к соседке — три одинаковых лопнут' },
  init(g) { titleScreen(g); window.__candy = () => S; },
  update, draw
});
})();
