/* Пятнашки — головоломка в стиле Dewiar: мягкий неоморфизм «Небесного» (выпуклые плитки на светлом поле, тени вниз-
   вправо, блик вверх-влево). Плитка рядом с пустым местом едет туда по касанию или стрелке. Перемешано всегда решаемо
   (случайными ходами от собранного). 4×4 — классика, 3×3 — полегче. Очки: чем меньше ходов и времени, тем больше. */
(() => {
'use strict';
const A = Arcade;
/* Широкое окно (лист «Досуг» на компьютере) — своя раскладка 1280×720: поле посередине во всю высоту, слева —
   название, ходы, время и «Лира-значок», справа — образец «как собрать» и подсказка. Книжная — как была. */
const LAND = (() => { try { return innerWidth > (innerHeight - 110) * 1.15; } catch (e) { return false; } })();
const W = LAND ? 1280 : 720, H = LAND ? 720 : 1280;
const CL = 165, CR = W - 150;                   // широкая: середины левой и правой колонок (правая — чуть к краю, мимо карточки меню)
const BG = '#dbe5f1', DARK = '#b8c5d6', LIGHT = '#f7fbff', INK = '#24324a', MUTED = 'rgba(36,50,74,.55)', ACC = '#5b6cf0';
let S = null, SC = 1;          // SC — масштаб холста: тени холста не подчиняются transform, их умножаем сами

function solved(n) { return Array.from({ length: n * n }, (_, i) => (i + 1) % (n * n)); }
function fresh(n, mode) {
  const tiles = solved(n);
  const s = { n, mode, tiles, moves: 0, time: 0, anim: {}, won: 0, last: -1, hint: 0, done: false, shown: 0 };
  S = s;
  // перемешать: много случайных честных ходов (без отката назад) — всегда решаемо
  let z = tiles.indexOf(0), prev = -1;
  for (let k = 0; k < n * n * 40; k++) {
    const nb = neighbors(z).filter((i) => i !== prev);
    const t = A.pick(nb); tiles[z] = tiles[t]; tiles[t] = 0; prev = z; z = t;
  }
  if (isSolved()) return fresh(n, mode);
  return s;
}
function neighbors(i) {
  const n = S.n, x = i % n, y = (i / n) | 0, out = [];
  if (x > 0) out.push(i - 1); if (x < n - 1) out.push(i + 1); if (y > 0) out.push(i - n); if (y < n - 1) out.push(i + n);
  return out;
}
function isSolved() { return S.tiles.every((v, i) => v === (i + 1) % (S.n * S.n)); }
const geo = () => { const n = S.n, size = LAND ? 620 : 600, gap = n === 3 ? 22 : 18, cell = (size - gap * (n + 1)) / n; return { n, size, gap, cell, x0: (W - size) / 2, y0: LAND ? 50 : 330 }; };
const cellXY = (i) => { const g = geo(); return { x: g.x0 + g.gap + (i % g.n) * (g.cell + g.gap), y: g.y0 + g.gap + ((i / g.n) | 0) * (g.cell + g.gap) }; };

function slide(g, i) {
  if (S.done || S.mode !== 'play') return false;
  const z = S.tiles.indexOf(0);
  if (!neighbors(z).includes(i)) {
    // плитка в том же ряду или столбце, но не рядом — двигаем весь ряд к пустому месту
    const n = S.n, zx = z % n, zy = (z / n) | 0, ix = i % n, iy = (i / n) | 0;
    if (zx !== ix && zy !== iy) { g.sfx('click', { vol: .3 }); return false; }
    const step = zx === ix ? (iy > zy ? n : -n) : (ix > zx ? 1 : -1);
    let cur = z; while (cur !== i) { const nx = cur + step; moveOne(g, nx, cur); cur = nx; }
    return true;
  }
  moveOne(g, i, z); return true;
}
function moveOne(g, from, to) {
  const v = S.tiles[from];
  const a = cellXY(from), b = cellXY(to);
  S.anim[v] = { dx: a.x - b.x, dy: a.y - b.y, t: 0 };
  S.tiles[to] = v; S.tiles[from] = 0; S.moves++;
  g.sfx('bounce', { pitch: .8 + Math.random() * .3, vol: .5 });
  if (isSolved()) win(g);
}
function arrow(g, d) {
  // стрелка двигает плитку В пустое место: «←» — плитку справа от пустого влево
  const n = S.n, z = S.tiles.indexOf(0), zx = z % n, zy = (z / n) | 0;
  const t = d === 'left' && zx < n - 1 ? z + 1 : d === 'right' && zx > 0 ? z - 1 : d === 'up' && zy < n - 1 ? z + n : d === 'down' && zy > 0 ? z - n : -1;
  if (t >= 0) slide(g, t);
}
function score() { return Math.max(100, Math.round((S.n === 4 ? 6000 : 2500) - S.moves * 12 - S.time * 4)); }
function win(g) {
  S.done = true; S.won = 0; g.stopMusic(); g.sfx('win');
  const gg = geo();
  for (let k = 0; k < 6; k++) g.fx.burst(gg.x0 + Math.random() * gg.size, gg.y0 + Math.random() * gg.size, { n: 10, colors: [ACC, '#ff8fb8', '#ffd166', '#7ee0b8'], speed: 320, size: 8, life: .9, gravity: 500, shape: 'star' });
}

/* ---------------- экраны ---------------- */
function titleScreen(g) {
  fresh(4, 'title'); g.setPlaying(false);
  g.screen({
    kicker: A.framed ? 'Досуг' : 'Аркада', title: 'Пятнашки',
    html: `<p>Расставьте плитки по порядку: от 1 до 15, пустое место — в правом нижнем углу. Коснитесь плитки рядом с пустым местом — она сдвинется.</p>${g.best ? `<p class="record">Рекорд: ${g.best.toLocaleString('ru-RU')}</p>` : ''}`,
    button: 'Играть 4×4', onGo: () => start(g, 4), alt: { label: 'Полегче — 3×3', onGo: () => start(g, 3) }
  });
}
function start(g, n) { fresh(n, 'play'); g.fx.clear(); g.setPlaying(true); g.playMusic(); }
function over(g) {
  S.mode = 'over'; g.setPlaying(false);
  const sc = score(), rec = g.submit(sc);
  const mm = Math.floor(S.time / 60), ss = String(Math.floor(S.time % 60)).padStart(2, '0');
  g.screen({
    kicker: 'Собрано!', title: rec ? 'Новый рекорд!' : 'Красота!',
    html: `<div class="score">${sc.toLocaleString('ru-RU')}</div><p>ходов ${S.moves} · ${mm}:${ss}${rec ? '' : ` · рекорд ${g.best.toLocaleString('ru-RU')}`}</p>`,
    button: 'Ещё раз', onGo: () => start(g, S.n), alt: { label: S.n === 4 ? 'Полегче — 3×3' : 'Посложнее — 4×4', onGo: () => start(g, S.n === 4 ? 3 : 4) }
  });
}

/* ---------------- цикл ---------------- */
function update(g, dt) {
  for (const k in S.anim) { const a = S.anim[k]; a.t += dt / .12; if (a.t >= 1) delete S.anim[k]; }
  if (S.mode === 'title') {                        // заставка: плитки сами тихонько ходят
    S.hint += dt; if (S.hint > .55) { S.hint = 0; const z = S.tiles.indexOf(0), nb = neighbors(z).filter((i) => i !== S.last); const t = A.pick(nb); S.last = z; const v = S.tiles[t]; const a = cellXY(t), b = cellXY(z); S.anim[v] = { dx: a.x - b.x, dy: a.y - b.y, t: 0 }; S.tiles[z] = v; S.tiles[t] = 0; }
    return;
  }
  if (S.mode !== 'play') return;
  if (S.done) { S.won += dt; if (S.won > 1.3) over(g); return; }
  S.time += dt;
  const inp = g.input;
  for (const d of ['left', 'right', 'up', 'down']) if (inp.pressed(d)) arrow(g, d);
  if (inp.swipe) arrow(g, inp.swipe);
  if (inp.tap) {
    const gg = geo(), { x, y } = inp.tap;
    for (let i = 0; i < gg.n * gg.n; i++) { const c = cellXY(i); if (x >= c.x && x <= c.x + gg.cell && y >= c.y && y <= c.y + gg.cell && S.tiles[i]) { slide(g, i); break; } }
  }
}

/* мягкая выпуклая плитка: тень вниз-вправо, блик вверх-влево */
function neu(ctx, x, y, w, h, r, d0 = 10, pressed = false) {
  const d = d0 * SC;
  ctx.save();
  if (!pressed) {
    ctx.shadowColor = DARK; ctx.shadowBlur = d * 1.8; ctx.shadowOffsetX = d * .7; ctx.shadowOffsetY = d * .7;
    A.rr(ctx, x, y, w, h, r); ctx.fillStyle = BG; ctx.fill();
    ctx.shadowColor = LIGHT; ctx.shadowOffsetX = -d * .7; ctx.shadowOffsetY = -d * .7; ctx.fill();
  } else {
    A.rr(ctx, x, y, w, h, r); ctx.fillStyle = '#d3deeb'; ctx.fill();
    ctx.clip(); ctx.shadowColor = DARK; ctx.shadowBlur = d * 1.4; ctx.shadowOffsetX = d * .5; ctx.shadowOffsetY = d * .5;
    ctx.lineWidth = d0; ctx.strokeStyle = '#d3deeb'; A.rr(ctx, x - d0 / 2, y - d0 / 2, w + d0, h + d0, r + d0 / 2); ctx.stroke();
    ctx.shadowColor = LIGHT; ctx.shadowOffsetX = -d * .5; ctx.shadowOffsetY = -d * .5; ctx.stroke();
  }
  ctx.restore();
}
/* широкая раскладка: боковые колонки */
function sides(ctx, g) {
  const play = S.mode !== 'title';
  A.text(ctx, 'Пятнашки', CL, 104, { size: 50, weight: 900, color: INK });
  if (play) {
    const mm = Math.floor(S.time / 60), ss = String(Math.floor(S.time % 60)).padStart(2, '0');
    for (const [i, lbl, val] of [[0, 'ходов', String(S.moves)], [1, 'время', `${mm}:${ss}`]]) {
      const x = CL - 110, y = 168 + i * 132;
      neu(ctx, x, y, 220, 104, 28, 8);
      A.text(ctx, val, x + 110, y + 46, { size: 40, weight: 800, color: INK });
      A.text(ctx, lbl, x + 110, y + 84, { size: 21, weight: 500, color: MUTED });
    }
  } else {
    A.text(ctx, 'головоломка', CL - 8, 160, { size: 21, weight: 500, color: MUTED });
    A.text(ctx, 'в стиле Dewiar', CL - 8, 189, { size: 21, weight: 500, color: MUTED });
  }
  // справа: образец «как собрать» — плитки, что уже на месте, подсвечены
  const n = S.n, gs = 208, gx = CR - gs / 2, gy = 140, gp = n === 3 ? 12 : 10, gc = (gs - gp * (n + 1)) / n;
  A.text(ctx, 'как собрать', CR, 104, { size: 24, weight: 700, color: MUTED });
  neu(ctx, gx, gy, gs, gs, 26, 8, true);
  let home = 0;
  for (let i = 0; i < n * n - 1; i++) {
    const x = gx + gp + (i % n) * (gc + gp), y = gy + gp + ((i / n) | 0) * (gc + gp), ok = play && S.tiles[i] === i + 1;
    if (ok) home++;
    neu(ctx, x, y, gc, gc, n === 3 ? 16 : 12, 4);
    A.text(ctx, String(i + 1), x + gc / 2, y + gc / 2 + 1, { size: n === 3 ? 28 : 21, weight: 800, color: ok ? ACC : 'rgba(36,50,74,.7)' });
  }
  if (play) A.text(ctx, S.done ? 'Собрано!' : `на месте ${home} из ${n * n - 1}`, CR, gy + gs + 46, { size: S.done ? 30 : 23, weight: S.done ? 800 : 600, color: S.done ? ACC : INK });
  const tip = !play ? [] : S.done ? [] : A.isTouch ? ['Коснитесь плитки', 'рядом с пустым местом'] : ['Стрелки', 'или щелчок по плитке'];
  tip.forEach((l, i) => A.text(ctx, l, CR, 590 + i * 30, { size: 22, weight: 500, color: MUTED }));
}
function draw(ctx, g) {
  SC = g.scale;
  ctx.fillStyle = BG; ctx.fillRect(0, 0, W, H);
  const gg = geo(), t = g.t;
  // заголовок
  if (LAND) sides(ctx, g);
  else A.text(ctx, 'Пятнашки', W / 2, 120, { size: 64, weight: 900, color: INK });
  const mm = Math.floor(S.time / 60), ss = String(Math.floor(S.time % 60)).padStart(2, '0');
  if (LAND) { /* ходы и время — в левой колонке */ } else if (S.mode !== 'title') {
    for (const [i, lbl, val] of [[0, 'ходов', String(S.moves)], [1, 'время', `${mm}:${ss}`]]) {
      const x = W / 2 - 170 + i * 200;
      neu(ctx, x, 190, 140, 92, 26, 7);
      A.text(ctx, val, x + 70, 226, { size: 34, weight: 800, color: INK });
      A.text(ctx, lbl, x + 70, 262, { size: 18, weight: 500, color: MUTED });
    }
  } else A.text(ctx, 'головоломка в стиле Dewiar', W / 2, 186, { size: 24, weight: 500, color: MUTED });
  // поле — вдавленное
  neu(ctx, gg.x0, gg.y0, gg.size, gg.size, 40, 14, true);
  for (let i = 0; i < gg.n * gg.n; i++) {
    const v = S.tiles[i]; if (!v) continue;
    const c = cellXY(i), a = S.anim[v], k = a ? 1 - A.ease.outCubic(Math.min(1, a.t)) : 0;
    const x = c.x + (a ? a.dx * k : 0), y = c.y + (a ? a.dy * k : 0);
    const home = v === i + 1;
    neu(ctx, x, y, gg.cell, gg.cell, gg.n === 3 ? 34 : 28, gg.n === 3 ? 12 : 10);
    if (home && S.mode === 'play') { A.rr(ctx, x + gg.cell / 2 - 14, y + gg.cell - 22, 28, 6, 3); ctx.fillStyle = 'rgba(91,108,240,.45)'; ctx.fill(); }
    A.text(ctx, String(v), x + gg.cell / 2, y + gg.cell / 2 + 2, { size: gg.n === 3 ? 74 : 58, weight: 800, color: home && S.done ? ACC : INK });
  }
  // подсказка снизу
  const tip = S.mode === 'title' ? '' : S.done ? 'Собрано!' : A.isTouch ? 'Коснитесь плитки рядом с пустым местом' : 'Стрелки или щелчок по плитке';
  if (tip && !LAND) A.text(ctx, tip, W / 2, gg.y0 + gg.size + 70, { size: 24, weight: 500, color: MUTED });
  // маленький «Лира-значок»: мягкий кружок с улыбкой (широкая — внизу левой колонки)
  const bx = LAND ? CL : W / 2, by = (LAND ? 560 : H - 150) + Math.sin(t * 2) * 5;
  if (LAND) { ctx.save(); ctx.translate(bx, by); ctx.scale(1.3, 1.3); ctx.translate(-bx, -by); }
  ctx.save(); ctx.shadowColor = DARK; ctx.shadowBlur = 18 * SC; ctx.shadowOffsetX = 6 * SC; ctx.shadowOffsetY = 6 * SC;
  ctx.beginPath(); ctx.arc(bx, by, 46, 0, Math.PI * 2); ctx.fillStyle = BG; ctx.fill();
  ctx.shadowColor = LIGHT; ctx.shadowOffsetX = -6 * SC; ctx.shadowOffsetY = -6 * SC; ctx.fill(); ctx.restore();
  ctx.fillStyle = INK; for (const ex of [-14, 14]) { ctx.beginPath(); ctx.ellipse(bx + ex, by - 6, 4, Math.sin(t * 1.3) > .97 ? 1 : 6, 0, 0, Math.PI * 2); ctx.fill(); }
  ctx.beginPath(); ctx.arc(bx, by + 6, 12, .15 * Math.PI, .85 * Math.PI); ctx.lineWidth = 3.5; ctx.lineCap = 'round'; ctx.strokeStyle = INK; ctx.stroke();
  if (LAND) { ctx.restore(); A.text(ctx, S.done ? 'Ура, собрано!' : 'Лира болеет за вас', CL, 652, { size: 21, weight: 500, color: MUTED }); }
}

A.game({
  id: 'fifteen', tone: 'light', title: 'Пятнашки', width: W, height: H, orientation: LAND ? 'landscape' : 'portrait', music: 'garden',
  help: {
    desktop: '<kbd>←</kbd> <kbd>→</kbd> <kbd>↑</kbd> <kbd>↓</kbd> — двигать плитку в пустое место · или щелчок по плитке · <kbd>P</kbd> пауза · <kbd>M</kbd> музыка',
    short: '<b>Стрелки</b> или щелчок по плитке',
    touch: 'Коснитесь плитки рядом с пустым местом — или целого ряда'
  },
  init(g) { titleScreen(g); window.__fifteen = () => S; },
  update, draw
});
})();
