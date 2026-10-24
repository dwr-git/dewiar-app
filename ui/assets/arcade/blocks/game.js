/* Блоки — падающие фигурки из желейных кубиков на общем каркасе (shared/arcade.js).
   Собирайте целые ряды — они лопаются конфетти. Семь фигур мешком по семь (без долгих засух), призрак показывает, куда
   упадёт фигура, «Запас» откладывает фигуру на потом. Управление: стрелки (↑ — поворот), пробел — уронить, X — в запас;
   на телефоне — вести пальцем влево-вправо, коснуться — повернуть, смахнуть вниз — уронить, коснуться «Запаса». */
(() => {
'use strict';
const A = Arcade;
/* Широкое окно (лист «Досуг» на компьютере; 24.10, владелец: «Блоки выглядят странновато» — узкое поле посередине,
   мелкие надписи) — своя раскладка 1280×720: поле посередине во всю высоту, очки слева, «Дальше / Запас / Рекорд» справа. */
const LAND = (() => { try { return innerWidth > (innerHeight - 110) * 1.15; } catch (e) { return false; } })();
const W = LAND ? 1280 : 720, H = LAND ? 720 : 1280;
const COLS = 10, ROWS = 20, CELL = LAND ? 31 : 50;
const BX = LAND ? 485 : 34, BY = LAND ? 50 : 176;      // поле 310 × 620 (широкое) или 500 × 1000
const PX = BX + COLS * CELL + (LAND ? 52 : 22);        // правая колонка
const PW = LAND ? 236 : W - PX - 20;
const PN = LAND ? { next: [0, 196, 88, 158], hold: [216, 150], rec: [386, 130] } : { next: [0, 210, 95, 170], hold: [230, 150], rec: [410, 140] };
const INK = '#3b2a5c';
/* фигуры: клетки в повороте 0 на сетке 4×4; цвета — конфетные */
const SHAPES = {
  I: { c: ['#7fdcff', '#3fb3f0'], cells: [[0, 1], [1, 1], [2, 1], [3, 1]] },
  O: { c: ['#ffe58a', '#f5be2e'], cells: [[1, 0], [2, 0], [1, 1], [2, 1]] },
  T: { c: ['#d9a8ff', '#a66cf0'], cells: [[1, 0], [0, 1], [1, 1], [2, 1]] },
  S: { c: ['#a8f0a0', '#5fcf6a'], cells: [[1, 0], [2, 0], [0, 1], [1, 1]] },
  Z: { c: ['#ffa3b5', '#f2607e'], cells: [[0, 0], [1, 0], [1, 1], [2, 1]] },
  J: { c: ['#a3b8ff', '#5f7cf2'], cells: [[0, 0], [0, 1], [1, 1], [2, 1]] },
  L: { c: ['#ffc59a', '#f58c4a'], cells: [[2, 0], [0, 1], [1, 1], [2, 1]] }
};
const KINDS = Object.keys(SHAPES);
const LINE_PTS = [0, 100, 300, 500, 800];
let S = null, BG = null;

function rot(kind, r) {
  // поворот по часовой: (x, y) -> (n-1-y, x); I — в 4×4, остальные — в 3×3, O не крутится
  if (kind === 'O') return SHAPES.O.cells;
  const n = kind === 'I' ? 4 : 3;
  let cells = SHAPES[kind].cells;
  for (let i = 0; i < ((r % 4) + 4) % 4; i++) cells = cells.map(([x, y]) => [n - 1 - y, x]);
  return cells;
}
function bag() { const b = KINDS.slice(); for (let i = b.length - 1; i > 0; i--) { const j = (Math.random() * (i + 1)) | 0; [b[i], b[j]] = [b[j], b[i]]; } return b; }
function nextKind() { if (S.queue.length < 4) S.queue.push(...bag()); return S.queue.shift(); }
function fits(kind, r, px, py) {
  for (const [x, y] of rot(kind, r)) {
    const cx = px + x, cy = py + y;
    if (cx < 0 || cx >= COLS || cy >= ROWS) return false;
    if (cy >= 0 && S.board[cy][cx]) return false;
  }
  return true;
}
function spawn(kind) {
  const p = { kind, r: 0, x: kind === 'O' ? 3 : 3, y: -1, lock: 0, drop: 0 };
  if (!fits(p.kind, p.r, p.x, p.y)) { p.y = -2; if (!fits(p.kind, p.r, p.x, p.y)) return null; }
  return p;
}
function fresh(mode) {
  S = { mode, board: Array.from({ length: ROWS }, () => Array(COLS).fill(null)), queue: [], piece: null, hold: null, canHold: true,
    score: 0, shown: 0, lines: 0, level: 1, grav: 0, das: 0, dasDir: 0, clearing: null, banner: null, over: 0, combo: -1,
    drag: null, demoT: 0, pops: [] };
  S.piece = spawn(nextKind());
  return S;
}
const gravity = () => Math.max(.06, .85 * Math.pow(.84, S.level - 1));
function ghostY(p) { let y = p.y; while (fits(p.kind, p.r, p.x, y + 1)) y++; return y; }

/* ---------------- ходы ---------------- */
function move(g, dx) {
  const p = S.piece; if (!p || !fits(p.kind, p.r, p.x + dx, p.y)) return false;
  p.x += dx; p.lock = Math.min(p.lock, .25); g.sfx('click', { vol: .5 }); return true;
}
function turn(g, dir = 1) {
  const p = S.piece; if (!p || p.kind === 'O') return;
  const r = p.r + dir;
  for (const [kx, ky] of [[0, 0], [-1, 0], [1, 0], [-2, 0], [2, 0], [0, -1], [-1, -1], [1, -1]]) {
    if (fits(p.kind, r, p.x + kx, p.y + ky)) { p.r = r; p.x += kx; p.y += ky; p.lock = Math.min(p.lock, .25); g.sfx('bounce', { pitch: 1.3, vol: .6 }); return; }
  }
}
function hardDrop(g) {
  const p = S.piece; if (!p) return;
  const gy = ghostY(p), n = gy - p.y;
  p.y = gy; S.score += n * 2;
  g.sfx('land'); g.shake(4, .12);
  for (const [x, y] of rot(p.kind, p.r)) g.fx.burst(BX + (p.x + x + .5) * CELL, BY + (p.y + y + 1) * CELL, { n: 3, colors: SHAPES[p.kind].c, speed: 120, size: 5, life: .35, angle: Math.PI / 2, spread: 1.2 });
  lock(g);
}
function holdPiece(g) {
  if (!S.canHold || !S.piece) return;
  const cur = S.piece.kind;
  S.piece = S.hold ? spawn(S.hold) : spawn(nextKind());
  S.hold = cur; S.canHold = false; g.sfx('whoosh');
  if (!S.piece) gameOver(g);
}
function lock(g) {
  const p = S.piece;
  for (const [x, y] of rot(p.kind, p.r)) {
    const cx = p.x + x, cy = p.y + y;
    if (cy < 0) { S.piece = null; return toOver(g); }
    S.board[cy][cx] = { kind: p.kind, pop: 0 };
  }
  S.piece = null; S.canHold = true;
  const full = [];
  for (let y = 0; y < ROWS; y++) if (S.board[y].every(Boolean)) full.push(y);
  if (full.length) {
    S.clearing = { rows: full, t: 0 };
    S.combo++;
    const pts = LINE_PTS[full.length] * S.level + (S.combo > 0 ? 50 * S.combo * S.level : 0);
    S.score += pts;
    const cy = BY + (full.reduce((a, b) => a + b, 0) / full.length + .5) * CELL;
    if (S.mode === 'play') {
      g.sfx(full.length >= 4 ? 'win' : 'pling', { pitch: 1 + full.length * .08 });
      g.fx.text(BX + COLS * CELL / 2, cy, '+' + pts.toLocaleString('ru-RU'), { size: full.length >= 4 ? 48 : 36, color: '#fff' });
      if (full.length >= 4) { S.banner = { text: 'Четыре!', sub: 'Вот это ряд', t: 0 }; g.shake(10, .3); }
      else if (S.combo >= 2) S.banner = { text: 'Серия ×' + (S.combo + 1), sub: '', t: 0 };
    }
    for (const y of full) for (let x = 0; x < COLS; x++) {
      const k = S.board[y][x].kind;
      g.fx.burst(BX + (x + .5) * CELL, BY + (y + .5) * CELL, { n: 4, colors: [SHAPES[k].c[0], '#fff', SHAPES[k].c[1]], speed: 260, size: 7, life: .7, gravity: 600, shape: Math.random() < .5 ? 'square' : 'star' });
    }
  } else {
    S.combo = -1;
    if (S.mode === 'play') g.sfx('land', { vol: .6 });
    next(g);
  }
}
function next(g) {
  S.piece = spawn(nextKind());
  if (!S.piece) toOver(g);
}
function finishClear(g) {
  const rows = S.clearing.rows;
  S.board = S.board.filter((_, y) => !rows.includes(y));
  while (S.board.length < ROWS) S.board.unshift(Array(COLS).fill(null));
  const before = Math.floor(S.lines / 10);
  S.lines += rows.length;
  if (Math.floor(S.lines / 10) > before) { S.level++; if (S.mode === 'play') { S.banner = { text: 'Уровень ' + S.level, sub: 'Чуть быстрее', t: 0 }; g.sfx('power'); } }
  S.clearing = null;
  next(g);
}

/* ---------------- экраны ---------------- */
function titleScreen(g) {
  fresh('title'); g.setPlaying(false);
  g.screen({
    kicker: A.framed ? 'Досуг' : 'Аркада', title: 'Тетрис',
    html: `<p>Складывайте фигурки в целые ряды — ряд лопается, а вы получаете очки. Каждые десять рядов — чуть быстрее.</p>${g.best ? `<p class="record">Рекорд: ${g.best.toLocaleString('ru-RU')}</p>` : ''}`,
    button: 'Играть', onGo: () => startGame(g)
  });
}
function startGame(g) { fresh('play'); g.fx.clear(); g.setPlaying(true); g.playMusic(); S.banner = { text: 'Поехали!', sub: '', t: 0 }; }
function toOver(g) {
  if (S.mode === 'title') { fresh('title'); return; }
  S.mode = 'dead'; S.over = 0; g.stopMusic(); g.sfx('lose'); g.shake(10, .3);
}
function gameOver(g) {
  S.mode = 'over'; g.setPlaying(false);
  const rec = g.submit(S.score);
  g.screen({
    kicker: 'Места больше нет', title: rec ? 'Новый рекорд!' : 'Игра окончена',
    html: `<div class="score">${S.score.toLocaleString('ru-RU')}</div><p>${rec ? 'Так держать!' : `Рекорд: ${g.best.toLocaleString('ru-RU')}`} · рядов ${S.lines} · уровень ${S.level}</p>`,
    button: 'Ещё раз', onGo: () => startGame(g),
    alt: { label: A.framed ? 'К играм' : 'В аркаду', onGo: () => A.home('../index.html') }
  });
}

/* ---------------- ввод ---------------- */
const HOLD_BOX = { x: PX, y: BY + PN.hold[0], w: PW, h: PN.hold[1] };
function readInput(g, dt) {
  const inp = g.input, p = S.piece;
  if (!p) return;
  if (inp.pressed('up')) turn(g, 1);
  if (inp.pressed('action')) return hardDrop(g);
  if (inp.pressed('action2')) return holdPiece(g);
  // влево-вправо с автоповтором
  const dir = inp.down('left') ? -1 : inp.down('right') ? 1 : 0;
  if (dir && dir !== S.dasDir) { S.dasDir = dir; S.das = 0; move(g, dir); }
  else if (dir) { S.das += dt; while (S.das > .17) { S.das -= .05; if (!move(g, dir)) break; } }
  else S.dasDir = 0;
  if (inp.down('down')) { S.grav += dt * 18; }
  // касания: ведём пальцем — фигура за ним по клеткам, коснулись — поворот, смахнули вниз — уронить
  const pt = inp.pointer;
  if (pt.justDown) S.drag = { x0: pt.x, px: p.x, moved: false, y0: pt.y };
  if (pt.down && S.drag) {
    const want = S.drag.px + Math.round((pt.x - S.drag.x0) / (CELL * 1.05));
    if (Math.abs(pt.x - S.drag.x0) > 14) S.drag.moved = true;
    while (p.x < want && move(g, 1)) { /* */ }
    while (p.x > want && move(g, -1)) { /* */ }
    if (pt.y - S.drag.y0 > 60 && Math.abs(pt.y - S.drag.y0) > Math.abs(pt.x - S.drag.x0) * 1.4) { S.grav += dt * 14; S.drag.moved = true; }
  }
  if (inp.swipe === 'down') { S.drag = null; return hardDrop(g); }
  if (inp.tap) {
    const t = inp.tap;
    if (t.x >= HOLD_BOX.x && t.y >= HOLD_BOX.y && t.y <= HOLD_BOX.y + HOLD_BOX.h) holdPiece(g);
    else if (!S.drag || !S.drag.moved) turn(g, 1);
  }
  if (pt.justUp) S.drag = null;
}

/* ИИ заставки: ставит фигуру туда, где ниже и ровнее */
function demoMove() {
  const p = S.piece; if (!p) return;
  let best = null;
  for (let r = 0; r < 4; r++) for (let x = -2; x < COLS; x++) {
    if (!fits(p.kind, r, x, p.y)) continue;
    let y = p.y; while (fits(p.kind, r, x, y + 1)) y++;
    const cells = rot(p.kind, r).map(([cx, cy]) => [x + cx, y + cy]);
    const tmp = S.board.map((row) => row.map(Boolean));
    for (const [cx, cy] of cells) if (cy >= 0) tmp[cy][cx] = true;
    let holes = 0, hgt = 0, full = 0;
    for (let c = 0; c < COLS; c++) { let seen = false; for (let rr = 0; rr < ROWS; rr++) { if (tmp[rr][c]) { if (!seen) hgt += ROWS - rr; seen = true; } else if (seen) holes++; } }
    for (const row of tmp) if (row.every(Boolean)) full++;
    const sc = full * 8 - holes * 6 - hgt * .4 + Math.random() * .5;
    if (!best || sc > best.sc) best = { sc, r, x };
  }
  if (best) { p.r = best.r; p.x = best.x; }
}

/* ---------------- обновление ---------------- */
function update(g, dt) {
  S.shown += (S.score - S.shown) * Math.min(1, dt * 8);
  if (S.banner) { S.banner.t += dt; if (S.banner.t > 1.8) S.banner = null; }
  for (const row of S.board) for (const c of row) if (c && c.pop < 1) c.pop = Math.min(1, c.pop + dt * 6);
  if (S.mode === 'dead') { S.over += dt; if (S.over > 1) gameOver(g); return; }
  if (S.mode === 'over') return;
  if (S.clearing) { S.clearing.t += dt; if (S.clearing.t > .32) finishClear(g); return; }
  if (!S.piece) return;
  if (S.mode === 'title') {
    S.demoT += dt; if (S.demoT > .5) { S.demoT = 0; demoMove(); }
    S.grav += dt * 14;
  } else readInput(g, dt);
  const p = S.piece; if (!p) return;
  S.grav += dt;
  const gv = gravity();
  while (S.grav >= gv && S.piece) {
    S.grav -= gv;
    if (fits(p.kind, p.r, p.x, p.y + 1)) { p.y++; p.lock = 0; if (g.input.down('down') && S.mode === 'play') S.score += 1; }
    else break;
  }
  if (S.piece && !fits(p.kind, p.r, p.x, p.y + 1)) { p.lock += dt; if (p.lock > .5) lock(g); }
}

/* ---------------- отрисовка ---------------- */
function jelly(ctx, x, y, s, c, alpha = 1, wob = 0) {
  ctx.save(); ctx.globalAlpha = alpha; ctx.translate(x + s / 2, y + s / 2); if (wob) ctx.scale(1 + wob, 1 - wob);
  const h = s / 2 - 2;
  const gr = ctx.createLinearGradient(0, -h, 0, h); gr.addColorStop(0, c[0]); gr.addColorStop(1, c[1]);
  A.rr(ctx, -h, -h, h * 2, h * 2, s * .26); ctx.fillStyle = gr; ctx.fill();
  ctx.lineWidth = Math.max(1.8, s * .06); ctx.strokeStyle = 'rgba(59,42,92,.55)'; ctx.stroke();
  const k = s / 50;
  ctx.fillStyle = 'rgba(255,255,255,.55)'; A.rr(ctx, -h + 6 * k, -h + 5 * k, h * 1.1, s * .17, s * .09); ctx.fill();
  ctx.fillStyle = 'rgba(255,255,255,.8)'; ctx.beginPath(); ctx.arc(h - 9 * k, -h + 9 * k, 2.6 * Math.max(.6, k), 0, Math.PI * 2); ctx.fill();
  ctx.restore();
}
function mini(ctx, kind, cx, cy, s, alpha = 1) {
  if (!kind) return;
  const cells = rot(kind, 0), xs = cells.map((c) => c[0]), ys = cells.map((c) => c[1]);
  const w = (Math.max(...xs) - Math.min(...xs) + 1) * s, h = (Math.max(...ys) - Math.min(...ys) + 1) * s;
  for (const [x, y] of cells) jelly(ctx, cx - w / 2 + (x - Math.min(...xs)) * s, cy - h / 2 + (y - Math.min(...ys)) * s, s, SHAPES[kind].c, alpha);
}
function makeBg() {
  const dots = [];
  for (let i = 0; i < 26; i++) dots.push({ x: Math.random() * W, y: Math.random() * H, r: A.rand(10, 40), c: A.pick(['#ffd6ec', '#d6e4ff', '#fff2c9', '#dcfadf', '#ead6ff']), s: A.rand(.2, .6) });
  return dots;
}
function panel(ctx, x, y, w, h, title) {
  A.rr(ctx, x, y, w, h, 22); ctx.fillStyle = 'rgba(255,255,255,.72)'; ctx.fill();
  ctx.lineWidth = 3; ctx.strokeStyle = 'rgba(59,42,92,.15)'; ctx.stroke();
  A.text(ctx, title, x + w / 2, y + 26, { size: 21, weight: 700, color: '#8a7bb0' });
}
function draw(ctx, g) {
  const t = g.t;
  const bg = ctx.createLinearGradient(0, 0, 0, H); bg.addColorStop(0, '#f9e8ff'); bg.addColorStop(.55, '#e4ecff'); bg.addColorStop(1, '#fff1e2');
  ctx.fillStyle = bg; ctx.fillRect(0, 0, W, H);
  for (const d of BG) { ctx.globalAlpha = .55; ctx.beginPath(); ctx.arc(d.x, (d.y + t * d.s * 20) % (H + 80) - 40, d.r, 0, Math.PI * 2); ctx.fillStyle = d.c; ctx.fill(); }
  ctx.globalAlpha = 1;
  // заголовок и очки
  if (LAND) {                                        // слева от поля: очки крупно, уровень и ряды
    const sx = BX - 52;
    A.text(ctx, 'Очки', sx, BY + 26, { align: 'right', size: 22, weight: 700, color: '#8a7bb0' });
    A.text(ctx, Math.round(S.shown).toLocaleString('ru-RU'), sx, BY + 84, { align: 'right', size: 64, color: '#fff', stroke: INK, strokeW: 11, weight: 900 });
    A.text(ctx, 'Уровень ' + S.level, sx, BY + 150, { align: 'right', size: 26, weight: 800, color: '#6c5a94' });
    A.text(ctx, 'рядов ' + S.lines + (S.level < 99 ? ' · до следующего ' + (10 - S.lines % 10) : ''), sx, BY + 184, { align: 'right', size: 19, weight: 600, color: '#8a7bb0' });
  } else {
    A.text(ctx, Math.round(S.shown).toLocaleString('ru-RU'), BX, 66, { align: 'left', size: 54, color: '#fff', stroke: INK, strokeW: 10, weight: 900 });
    A.text(ctx, 'Уровень ' + S.level + ' · рядов ' + S.lines, BX + 2, 116, { align: 'left', size: 24, weight: 700, color: '#6c5a94' });
  }
  // поле
  const fr = LAND ? .7 : 1;
  A.rr(ctx, BX - 12 * fr, BY - 12 * fr, COLS * CELL + 24 * fr, ROWS * CELL + 24 * fr, 30 * fr); ctx.fillStyle = '#5b4a86'; ctx.fill();
  A.rr(ctx, BX - 4 * fr, BY - 4 * fr, COLS * CELL + 8 * fr, ROWS * CELL + 8 * fr, 24 * fr); ctx.fillStyle = '#463870'; ctx.fill();
  ctx.save(); A.rr(ctx, BX, BY, COLS * CELL, ROWS * CELL, 20 * fr); ctx.clip();
  ctx.fillStyle = '#3c2f62'; ctx.fillRect(BX, BY, COLS * CELL, ROWS * CELL);
  ctx.strokeStyle = 'rgba(255,255,255,.05)'; ctx.lineWidth = 2;
  for (let x = 1; x < COLS; x++) { ctx.beginPath(); ctx.moveTo(BX + x * CELL, BY); ctx.lineTo(BX + x * CELL, BY + ROWS * CELL); ctx.stroke(); }
  for (let y = 1; y < ROWS; y++) { ctx.beginPath(); ctx.moveTo(BX, BY + y * CELL); ctx.lineTo(BX + COLS * CELL, BY + y * CELL); ctx.stroke(); }
  const clearRows = S.clearing ? S.clearing.rows : [], ck = S.clearing ? S.clearing.t / .32 : 0;
  for (let y = 0; y < ROWS; y++) for (let x = 0; x < COLS; x++) {
    const c = S.board[y][x]; if (!c) continue;
    if (clearRows.includes(y)) {
      const s = CELL * (1 - ck * .9);
      ctx.save(); ctx.globalAlpha = 1 - ck * .7; jelly(ctx, BX + x * CELL + (CELL - s) / 2, BY + y * CELL + (CELL - s) / 2, s, ['#ffffff', SHAPES[c.kind].c[0]]); ctx.restore();
    } else jelly(ctx, BX + x * CELL, BY + y * CELL, CELL, SHAPES[c.kind].c, 1, (1 - c.pop) * .18);
  }
  const p = S.piece;
  if (p) {
    const gy = ghostY(p);
    for (const [x, y] of rot(p.kind, p.r)) {
      if (gy + y < 0) continue;
      A.rr(ctx, BX + (p.x + x) * CELL + CELL * .08, BY + (gy + y) * CELL + CELL * .08, CELL * .84, CELL * .84, CELL * .24);
      ctx.lineWidth = Math.max(2, CELL * .06); ctx.strokeStyle = SHAPES[p.kind].c[0]; ctx.globalAlpha = .55; ctx.stroke(); ctx.globalAlpha = 1;
    }
    const k = gravity(), smooth = fits(p.kind, p.r, p.x, p.y + 1) ? Math.min(1, S.grav / k) * .5 : 0;
    for (const [x, y] of rot(p.kind, p.r)) if (p.y + y + smooth > -1) jelly(ctx, BX + (p.x + x) * CELL, BY + (p.y + y + smooth) * CELL, CELL, SHAPES[p.kind].c);
  }
  ctx.restore();
  // правая колонка
  const pw = PW;
  panel(ctx, PX, BY, pw, PN.next[1], 'Дальше');
  mini(ctx, S.queue[0], PX + pw / 2, BY + PN.next[2], 34);
  mini(ctx, S.queue[1], PX + pw / 2, BY + PN.next[3], 22, .55);
  panel(ctx, HOLD_BOX.x, HOLD_BOX.y, HOLD_BOX.w, HOLD_BOX.h, 'Запас');
  if (S.hold) mini(ctx, S.hold, PX + pw / 2, HOLD_BOX.y + 88, 30, S.canHold ? 1 : .4);
  else A.text(ctx, A.isTouch ? 'коснитесь' : 'клавиша X', PX + pw / 2, HOLD_BOX.y + 92, { size: 18, weight: 500, color: '#a497c4' });
  panel(ctx, PX, BY + PN.rec[0], pw, PN.rec[1], 'Рекорд');
  A.text(ctx, (g.best || 0).toLocaleString('ru-RU'), PX + pw / 2, BY + PN.rec[0] + PN.rec[1] * .56, { size: 28, color: INK, weight: 800 });
  // милое облачко-маскот: смотрит на фигурку (широкое окно — слева, под очками)
  const mx = LAND ? BX - 190 : PX + pw / 2, my = (LAND ? BY + 470 : BY + 700) + Math.sin(t * 2) * 8;
  ctx.save(); ctx.translate(mx, my);
  ctx.fillStyle = '#fff'; for (const [ox, oy, r] of [[-30, 6, 28], [0, -10, 36], [30, 6, 28], [0, 14, 30]]) { ctx.beginPath(); ctx.arc(ox, oy, r, 0, Math.PI * 2); ctx.fill(); }
  const look = p ? A.clamp((BX + (p.x + 1.5) * CELL - mx) / 300, -1, 1) * 4 : 0;
  ctx.fillStyle = INK; for (const ex of [-14, 14]) { ctx.beginPath(); ctx.ellipse(ex + look, 0, 4.5, (Math.sin(t * 1.7) > .97 ? 1 : 6.5), 0, 0, Math.PI * 2); ctx.fill(); }
  ctx.fillStyle = '#ffb3c7'; for (const ex of [-24, 24]) { ctx.beginPath(); ctx.ellipse(ex, 12, 6, 3.5, 0, 0, Math.PI * 2); ctx.fill(); }
  ctx.beginPath(); ctx.arc(look, 10, 6, .15 * Math.PI, .85 * Math.PI); ctx.lineWidth = 3; ctx.strokeStyle = INK; ctx.lineCap = 'round'; ctx.stroke();
  ctx.restore();
  if (S.mode === 'title') {
    ctx.save(); ctx.translate(BX + COLS * CELL / 2, BY + ROWS * CELL * .38); ctx.rotate(Math.sin(t * 1.4) * .03);
    A.text(ctx, 'Тетрис', 0, 0, { size: 96, weight: 900, color: '#fff', stroke: INK, strokeW: 16 });
    ctx.restore();
  }
  if (S.banner) {
    const bt = S.banner.t, k = bt < .3 ? A.ease.outBack(bt / .3) : 1, a = bt > 1.4 ? 1 - (bt - 1.4) / .4 : 1;
    ctx.save(); ctx.globalAlpha = Math.max(0, a); ctx.translate(BX + COLS * CELL / 2, BY + ROWS * CELL * .38); ctx.scale(k, k);
    A.text(ctx, S.banner.text, 0, 0, { size: 64, color: '#fff', stroke: INK, strokeW: 12, weight: 900 });
    if (S.banner.sub) A.text(ctx, S.banner.sub, 0, 56, { size: 28, color: '#ffe58a', stroke: INK, strokeW: 7 });
    ctx.restore();
  }
}

A.game({
  id: 'blocks', tone: 'light', title: 'Тетрис', width: W, height: H, orientation: LAND ? 'landscape' : 'portrait', music: 'candy',
  help: {
    desktop: '<kbd>←</kbd> <kbd>→</kbd> — сдвиг · <kbd>↑</kbd> — поворот · <kbd>↓</kbd> — быстрее · <kbd>Пробел</kbd> — уронить · <kbd>X</kbd> — в запас · <kbd>P</kbd> пауза · <kbd>M</kbd> музыка',
    short: '<b>Стрелки</b> — двигать и крутить, <b>Пробел</b> — уронить',
    touch: 'Ведите пальцем — фигурка за ним, коснитесь — повернётся, смахните вниз — упадёт'
  },
  init(g) { BG = makeBg(); titleScreen(g); window.__blocks = () => S; },
  update, draw
});
})();
