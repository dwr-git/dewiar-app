/* Слияние — головоломка «сложи одинаковые» (как 2048): смахните — все плитки едут в ту сторону, две одинаковые
   сливаются в одну вдвое больше. Цель — 2048 (можно играть и дальше). Плитки — пастельные «зефирки», крупные цифры.
   Отменить последний ход можно один раз за ход (кнопка «Назад» под полем или клавиша Z/Backspace). */
(() => {
'use strict';
const A = Arcade;
/* Широкое окно (лист «Досуг» на компьютере) — своя раскладка 1280×720: поле посередине во всю высоту, слева —
   название, счёт, рекорд и «2 + 2 = 4», справа — самая большая плитка, «Назад» и подсказка. Книжная — как была. */
const LAND = (() => { try { return innerWidth > (innerHeight - 110) * 1.15; } catch (e) { return false; } })();
const W = LAND ? 1280 : 720, H = LAND ? 720 : 1280, N = 4;
const BX = LAND ? 330 : 60, BY = LAND ? 50 : 360, SZ = LAND ? 620 : 600, GAP = 18, CELL = (SZ - GAP * (N + 1)) / N;
const CL = 165, CR = W - 165;                   // широкая: середины левой и правой колонок
const INK = '#4a3b2f';
const COLORS = {
  2: ['#fff6e8', '#f3e3c9'], 4: ['#ffeccf', '#f2d3a3'], 8: ['#ffd3a8', '#f6a96b'], 16: ['#ffbfa1', '#f2895e'], 32: ['#ffb0b9', '#ef6f84'],
  64: ['#ff9fb6', '#e8517a'], 128: ['#f9e39b', '#eec54a'], 256: ['#c9f0a8', '#82cf5f'], 512: ['#b5e6f7', '#5ab8e3'],
  1024: ['#c9c2ff', '#8a7bf0'], 2048: ['#ffe27a', '#ffb800'], big: ['#e0b3ff', '#a35cf0']
};
let S = null, ID = 1, UNDO_RECT = null;

function empty() { const out = []; for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) if (!S.grid[y][x]) out.push([x, y]); return out; }
function addTile() {
  const e = empty(); if (!e.length) return;
  const [x, y] = A.pick(e);
  S.grid[y][x] = { id: ID++, v: Math.random() < .9 ? 2 : 4, x, y, px: x, py: y, born: 0, merged: 0 };
}
function fresh(mode) {
  S = { mode, grid: Array.from({ length: N }, () => Array(N).fill(null)), score: 0, shown: 0, anim: 0, ghosts: [], won: false, over: 0, undo: null, demo: 0, best: 0 };
  addTile(); addTile();
  return S;
}
function snapshot() { return { grid: S.grid.map((r) => r.map((t) => t && { ...t })), score: S.score }; }
function slide(g, dir) {
  if (S.anim > 0) return false;
  const before = snapshot();
  const dx = dir === 'left' ? -1 : dir === 'right' ? 1 : 0, dy = dir === 'up' ? -1 : dir === 'down' ? 1 : 0;
  const xs = [...Array(N).keys()], ys = [...Array(N).keys()];
  if (dx > 0) xs.reverse(); if (dy > 0) ys.reverse();
  let moved = false, gained = 0; S.ghosts = [];
  for (const row of S.grid) for (const t of row) if (t) { t.px = t.x; t.py = t.y; t.merged = 0; t.born = 1; }
  const done = Array.from({ length: N }, () => Array(N).fill(false));
  for (const y of ys) for (const x of xs) {
    const t = S.grid[y][x]; if (!t) continue;
    let cx = x, cy = y;
    while (true) {
      const nx = cx + dx, ny = cy + dy;
      if (nx < 0 || ny < 0 || nx >= N || ny >= N) break;
      const o = S.grid[ny][nx];
      if (!o) { cx = nx; cy = ny; continue; }
      if (o.v === t.v && !done[ny][nx]) {
        S.grid[y][x] = null; o.v *= 2; o.merged = 1; done[ny][nx] = true; gained += o.v;
        S.ghosts.push({ v: t.v, px: x, py: y, x: nx, y: ny });
        moved = true; cx = null; break;
      }
      break;
    }
    if (cx === null) continue;
    if (cx !== x || cy !== y) { S.grid[y][x] = null; S.grid[cy][cx] = t; t.x = cx; t.y = cy; moved = true; }
  }
  if (!moved) return false;
  S.undo = before;
  S.score += gained; S.anim = 1;
  if (S.mode === 'play') {
    g.sfx(gained ? 'pling' : 'whoosh', { pitch: gained ? 1 + Math.log2(Math.max(2, gained)) * .03 : 1, vol: gained ? .7 : .4 });
    for (const gh of S.ghosts) {
      const c = cellXY(gh.x, gh.y), v = gh.v * 2;
      if (v >= 64) g.fx.burst(c.x + CELL / 2, c.y + CELL / 2, { n: 8, colors: (COLORS[v] || COLORS.big).concat('#fff'), speed: 220, size: 7, life: .5, shape: 'star' });
    }
    if (gained) { if (LAND) g.fx.text(CL, 150, '+' + gained, { size: 38, color: '#fff' }); else g.fx.text(BX + SZ / 2, BY - 40, '+' + gained, { size: 34, color: '#fff' }); }
  }
  setTimeout(() => { addTile(); if (!canMove()) S.over = .001; }, 110);
  return true;
}
function canMove() {
  if (empty().length) return true;
  for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) { const v = S.grid[y][x].v; if ((x < N - 1 && S.grid[y][x + 1].v === v) || (y < N - 1 && S.grid[y + 1][x].v === v)) return true; }
  return false;
}
const cellXY = (x, y) => ({ x: BX + GAP + x * (CELL + GAP), y: BY + GAP + y * (CELL + GAP) });
function maxTile() { let m = 0; for (const r of S.grid) for (const t of r) if (t && t.v > m) m = t.v; return m; }

/* ---------------- экраны ---------------- */
function titleScreen(g) {
  fresh('title'); g.setPlaying(false);
  g.screen({
    kicker: A.framed ? 'Досуг' : 'Аркада', title: 'Слияние',
    html: `<p>Смахивайте плитки: две одинаковые сливаются в одну — вдвое больше. Сумеете дойти до 2048?</p>${g.best ? `<p class="record">Рекорд: ${g.best.toLocaleString('ru-RU')}</p>` : ''}`,
    button: 'Играть', onGo: () => start(g)
  });
}
function start(g) { fresh('play'); g.fx.clear(); g.setPlaying(true); g.playMusic(); }
function gameOver(g) {
  S.mode = 'over'; g.setPlaying(false); g.stopMusic(); g.sfx('lose');
  const rec = g.submit(S.score);
  g.screen({
    kicker: 'Ходов больше нет', title: rec ? 'Новый рекорд!' : 'Красиво сложили!',
    html: `<div class="score">${S.score.toLocaleString('ru-RU')}</div><p>самая большая плитка — ${maxTile()}${rec ? '' : ` · рекорд ${g.best.toLocaleString('ru-RU')}`}</p>`,
    button: 'Ещё раз', onGo: () => start(g), alt: { label: A.framed ? 'К играм' : 'В аркаду', onGo: () => A.home('../index.html') }
  });
}
function undo(g) {
  if (!S.undo || S.anim > 0 || S.mode !== 'play') return;
  S.grid = S.undo.grid; S.score = S.undo.score; S.undo = null; S.over = 0;
  for (const r of S.grid) for (const t of r) if (t) { t.px = t.x; t.py = t.y; t.merged = 0; t.born = 1; }
  g.sfx('whoosh');
}

/* ---------------- цикл ---------------- */
function update(g, dt) {
  S.shown += (S.score - S.shown) * Math.min(1, dt * 10);
  if (S.anim > 0) S.anim = Math.max(0, S.anim - dt / .11);
  for (const r of S.grid) for (const t of r) if (t) { if (t.born < 1) t.born = Math.min(1, t.born + dt / .16); if (t.merged > 0) t.merged = Math.max(0, t.merged - dt / .22); }
  if (S.mode === 'over') return;
  if (S.over) { S.over += dt; if (S.over > .9) { if (S.mode === 'title') fresh('title'); else gameOver(g); } return; }
  if (S.mode === 'title') { S.demo += dt; if (S.demo > .45) { S.demo = 0; for (const d of A.pick([['down', 'left', 'right', 'up'], ['left', 'down', 'right', 'up']])) if (slide(g, d)) break; } return; }
  const inp = g.input;
  for (const d of ['left', 'right', 'up', 'down']) if (inp.pressed(d)) slide(g, d);
  if (inp.swipe) slide(g, inp.swipe);
  if (inp.pressed('undo')) undo(g);
  if (inp.tap && UNDO_RECT) { const { x, y } = inp.tap, u = UNDO_RECT; if (x >= u.x && x <= u.x + u.w && y >= u.y && y <= u.y + u.h) undo(g); }
  if (!S.won && maxTile() >= 2048) {
    S.won = true; g.sfx('win'); g.submit(S.score);
    for (let k = 0; k < 6; k++) g.fx.burst(BX + Math.random() * SZ, BY + Math.random() * SZ, { n: 12, colors: ['#ffe27a', '#ffb800', '#fff', '#ff9fb6'], speed: 340, size: 8, life: 1, gravity: 500, shape: 'star' });
    g.screen({ kicker: 'Ура!', title: '2048!', html: '<p>Вы собрали главную плитку. Можно играть дальше — до 4096.</p>', button: 'Играть дальше', onGo: () => { } });
  }
}

/* ---------------- отрисовка ---------------- */
function tile(ctx, v, x, y, s) {
  const c = COLORS[v] || COLORS.big;
  ctx.save(); ctx.translate(x + CELL / 2, y + CELL / 2); ctx.scale(s, s);
  ctx.shadowColor = 'rgba(120,80,40,.25)'; ctx.shadowBlur = 12 * S.sc; ctx.shadowOffsetY = 6 * S.sc;
  const gr = ctx.createLinearGradient(0, -CELL / 2, 0, CELL / 2); gr.addColorStop(0, c[0]); gr.addColorStop(1, c[1]);
  A.rr(ctx, -CELL / 2, -CELL / 2, CELL, CELL, 30); ctx.fillStyle = gr; ctx.fill();
  ctx.shadowColor = 'transparent';
  ctx.fillStyle = 'rgba(255,255,255,.55)'; A.rr(ctx, -CELL / 2 + 14, -CELL / 2 + 10, CELL - 60, 16, 8); ctx.fill();
  const str = String(v), size = str.length <= 2 ? 64 : str.length === 3 ? 54 : 42;
  A.text(ctx, str, 0, 4, { size, weight: 900, color: v <= 4 ? INK : '#fff', stroke: v <= 4 ? null : 'rgba(80,40,20,.35)', strokeW: 6 });
  ctx.restore();
}
/* широкая раскладка: боковые колонки (кнопка «Назад» рисуется в draw — там же, где книжная) */
function sides(ctx, g) {
  const demo = S.mode === 'title';                // на заставке плитки ходят сами — их счёт не показываем
  A.text(ctx, 'Слияние', CL, 102, { size: 54, weight: 900, color: INK });
  for (const [i, lbl, val] of [[0, 'счёт', demo ? 0 : Math.round(S.shown)], [1, 'рекорд', demo ? g.best || 0 : Math.max(g.best || 0, S.score)]]) {
    const x = CL - 120, y = 168 + i * 130;
    A.rr(ctx, x, y, 240, 112, 28); ctx.fillStyle = 'rgba(255,255,255,.75)'; ctx.fill();
    A.text(ctx, val.toLocaleString('ru-RU'), x + 120, y + 50, { size: 42, weight: 900, color: INK });
    A.text(ctx, lbl, x + 120, y + 90, { size: 21, weight: 600, color: 'rgba(74,59,47,.55)' });
  }
  // «2 2 → 4» — как сливаются плитки
  const my = 586, s2 = 56 / CELL, s4 = 68 / CELL;
  A.text(ctx, 'одинаковые', CL, 482, { size: 22, weight: 500, color: 'rgba(74,59,47,.55)' });
  A.text(ctx, 'сливаются', CL, 510, { size: 22, weight: 500, color: 'rgba(74,59,47,.55)' });
  tile(ctx, 2, CL - 86 - CELL / 2, my - CELL / 2, s2);
  tile(ctx, 2, CL - 26 - CELL / 2, my - CELL / 2, s2);
  A.text(ctx, '→', CL + 28, my + 1, { size: 30, weight: 900, color: 'rgba(74,59,47,.45)' });
  tile(ctx, 4, CL + 82 - CELL / 2, my - CELL / 2, s4);
  // справа: цель и самая большая плитка
  const m = maxTile() || 2;
  A.text(ctx, m >= 2048 ? 'Цель взята!' : 'Цель — 2048', CR, 102, { size: 34, weight: 900, color: m >= 2048 ? '#e09a00' : INK });
  A.rr(ctx, CR - 120, 168, 240, 242, 28); ctx.fillStyle = 'rgba(255,255,255,.5)'; ctx.fill();
  A.text(ctx, 'самая большая', CR, 200, { size: 21, weight: 600, color: 'rgba(74,59,47,.55)' });
  tile(ctx, m, CR - CELL / 2, 306 - CELL / 2, .88);
  const tip = A.isTouch ? ['Смахивайте', 'в любую сторону'] : ['Стрелки — сдвинуть', 'Z — назад'];
  tip.forEach((l, i) => A.text(ctx, l, CR, 616 + i * 30, { size: 22, weight: 500, color: 'rgba(74,59,47,.55)' }));
}
function draw(ctx, g) {
  S.sc = g.scale;
  const bg = ctx.createLinearGradient(0, 0, 0, H); bg.addColorStop(0, '#fff3e6'); bg.addColorStop(1, '#ffe4ec');
  ctx.fillStyle = bg; ctx.fillRect(0, 0, W, H);
  if (LAND) sides(ctx, g);
  else A.text(ctx, 'Слияние', BX, 112, { align: 'left', size: 64, weight: 900, color: INK });
  if (!LAND) for (const [i, lbl, val] of [[0, 'счёт', Math.round(S.shown)], [1, 'рекорд', Math.max(g.best || 0, S.score)]]) {
    const x = BX + i * 200, y = 170;
    A.rr(ctx, x, y, 180, 96, 26); ctx.fillStyle = 'rgba(255,255,255,.75)'; ctx.fill();
    A.text(ctx, val.toLocaleString('ru-RU'), x + 90, y + 42, { size: 34, weight: 900, color: INK });
    A.text(ctx, lbl, x + 90, y + 76, { size: 18, weight: 600, color: 'rgba(74,59,47,.55)' });
  }
  // отменить
  UNDO_RECT = LAND ? { x: CR - 120, y: 470, w: 240, h: 76 } : { x: W - BX - 150, y: 186, w: 150, h: 64 };
  const u = UNDO_RECT, can = S.undo && S.mode === 'play';
  A.rr(ctx, u.x, u.y, u.w, u.h, LAND ? 26 : 22); ctx.fillStyle = can ? '#ffffff' : 'rgba(255,255,255,.4)'; ctx.fill();
  A.text(ctx, '↶ Назад', u.x + u.w / 2, u.y + u.h / 2 + 2, { size: LAND ? 28 : 24, weight: 700, color: can ? INK : 'rgba(74,59,47,.35)' });
  // поле
  A.rr(ctx, BX, BY, SZ, SZ, 40); ctx.fillStyle = '#e8cfb8'; ctx.fill();
  for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) { const c = cellXY(x, y); A.rr(ctx, c.x, c.y, CELL, CELL, 28); ctx.fillStyle = 'rgba(255,255,255,.35)'; ctx.fill(); }
  const k = 1 - A.ease.outCubic(S.anim);
  for (const gh of S.ghosts) if (S.anim > 0) { const a = cellXY(gh.px, gh.py), b = cellXY(gh.x, gh.y); tile(ctx, gh.v, A.lerp(a.x, b.x, k), A.lerp(a.y, b.y, k), 1); }
  for (const r of S.grid) for (const t of r) {
    if (!t) continue;
    const a = cellXY(t.px, t.py), b = cellXY(t.x, t.y);
    const s = t.born < 1 ? A.ease.outBack(t.born) : t.merged > 0 && S.anim <= 0 ? 1 + Math.sin((1 - t.merged) * Math.PI) * .12 : 1;
    const v = t.merged > 0 && S.anim > 0 ? t.v / 2 : t.v;
    tile(ctx, v, A.lerp(a.x, b.x, S.anim > 0 ? k : 1), A.lerp(a.y, b.y, S.anim > 0 ? k : 1), s);
  }
  if (!LAND) A.text(ctx, A.isTouch ? 'Смахивайте в любую сторону' : 'Стрелки — сдвинуть плитки · Z — назад', W / 2, BY + SZ + 70, { size: 24, weight: 500, color: 'rgba(74,59,47,.55)' });
}

A.game({
  id: 'merge', tone: 'light', title: 'Слияние', width: W, height: H, orientation: LAND ? 'landscape' : 'portrait', music: 'candy', keys: { KeyZ: 'undo', Backspace: 'undo' },
  help: { desktop: '<kbd>←</kbd> <kbd>→</kbd> <kbd>↑</kbd> <kbd>↓</kbd> — сдвинуть · <kbd>Z</kbd> — назад · <kbd>P</kbd> пауза · <kbd>M</kbd> музыка', short: '<b>Стрелки</b> — сдвинуть плитки', touch: 'Смахивайте пальцем — плитки едут, одинаковые сливаются' },
  init(g) { titleScreen(g); window.__merge = () => S; },
  update, draw
});
})();
