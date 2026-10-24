/* Змейка — садовая змейка на общем каркасе. */
(() => {
'use strict';
const A = Arcade;
/* Широкое окно (лист «Досуг» на компьютере) — своя раскладка 1280×720: поле по-настоящему широкое (20×14 клеток того же
   размера) во всю высоту между живыми изгородями; слева — таблички «Очки» и «Уровень», справа — «Фрукты», «Рекорд»
   и подсказка управления. Змейка стартует слева и ползёт вправо. Книжная — как прежде (15×24). */
const LAND = (() => { try { return innerWidth > (innerHeight - 110) * 1.15; } catch (e) { return false; } })();
const W = LAND ? 1280 : 720, H = LAND ? 720 : 1280;
const COLS = LAND ? 20 : 15, ROWS = LAND ? 14 : 24, CELL = 44;
const FX0 = (W - COLS * CELL) / 2, FY0 = LAND ? (H - ROWS * CELL) / 2 : 168;
const OUT = '#24502f';
const DIRS = { up: { x: 0, y: -1 }, down: { x: 0, y: 1 }, left: { x: -1, y: 0 }, right: { x: 1, y: 0 } };
const FRUITS = ['apple', 'strawberry', 'cherry', 'grape'];
let S = null, DECOR = null, FLIES = null;

const cx = (x) => FX0 + x * CELL + CELL / 2;
const cy = (y) => FY0 + y * CELL + CELL / 2;

/* ---------------- декор вокруг поля ---------------- */
function makeDecor() {
  const d = [];
  const flowerCols = ['#ff7aa8', '#ffd43b', '#ffffff', '#b38cff', '#ff9f5a'];
  if (LAND) {                                    // широкое окно: цветы и камешки на газонах слева и справа
    const fr = FX0 + COLS * CELL;
    for (const side of [0, 1]) {
      const x0 = side ? fr + 16 : 14, x1 = side ? W - 14 : FX0 - 16;
      for (let i = 0; i < 16; i++) d.push({ kind: 'flower', x: A.rand(x0, x1), y: A.rand(48, H - 48), r: A.rand(6, 10), c: A.pick(flowerCols), rot: Math.random() * 6 });
      for (let i = 0; i < 5; i++) d.push({ kind: 'pebble', x: A.rand(x0, x1), y: A.rand(56, H - 56), r: A.rand(5, 9) });
    }
    return d;
  }
  for (let i = 0; i < 22; i++) d.push({ kind: 'flower', x: A.rand(14, W - 14), y: A.rand(FY0 + ROWS * CELL + 14, H - 12), r: A.rand(7, 11), c: A.pick(flowerCols), rot: Math.random() * 6 });
  for (let i = 0; i < 10; i++) d.push({ kind: 'pebble', x: A.rand(14, W - 14), y: A.rand(FY0 + ROWS * CELL + 16, H - 10), r: A.rand(5, 9) });
  for (let i = 0; i < 14; i++) d.push({ kind: 'flower', x: A.rand(20, W - 20), y: A.rand(132, FY0 - 12), r: A.rand(6, 9), c: A.pick(flowerCols), rot: Math.random() * 6 });
  for (const side of [0, 1]) for (let i = 0; i < 8; i++) d.push({ kind: 'flower', x: side ? A.rand(W - FX0 + 4, W - 6) : A.rand(6, FX0 - 4), y: A.rand(FY0 + 20, FY0 + ROWS * CELL - 20), r: A.rand(5, 7), c: A.pick(flowerCols), rot: Math.random() * 6 });
  return d;
}
function drawFlower(ctx, f, t) {
  ctx.save(); ctx.translate(f.x, f.y); ctx.rotate(f.rot + Math.sin(t * 1.3 + f.x) * .08);
  ctx.fillStyle = f.c;
  for (let i = 0; i < 5; i++) { const a = i * Math.PI * 2 / 5; ctx.beginPath(); ctx.arc(Math.cos(a) * f.r * .7, Math.sin(a) * f.r * .7, f.r * .55, 0, Math.PI * 2); ctx.fill(); }
  ctx.beginPath(); ctx.arc(0, 0, f.r * .38, 0, Math.PI * 2); ctx.fillStyle = f.c === '#ffd43b' ? '#ff8a3d' : '#ffd43b'; ctx.fill();
  ctx.restore();
}

/* ---------------- фрукты ---------------- */
function drawFruit(ctx, kind, x, y, s, t) {
  ctx.save(); ctx.translate(x, y); ctx.scale(s, s);
  ctx.lineJoin = 'round'; ctx.lineCap = 'round'; ctx.strokeStyle = OUT; ctx.lineWidth = 2.6;
  // тень
  ctx.save(); ctx.globalAlpha = .18; ctx.fillStyle = '#1d3d1a'; ctx.beginPath(); ctx.ellipse(2, 18, 14, 4.5, 0, 0, Math.PI * 2); ctx.fill(); ctx.restore();
  if (kind === 'apple' || kind === 'gold') {
    const gold = kind === 'gold';
    const gr = ctx.createRadialGradient(-6, -6, 2, 0, 0, 20);
    gr.addColorStop(0, gold ? '#fff7c2' : '#ff9a8a'); gr.addColorStop(.5, gold ? '#ffcf3a' : '#ef3b3b'); gr.addColorStop(1, gold ? '#d99a00' : '#b31d2e');
    ctx.beginPath();
    ctx.moveTo(0, -10);
    ctx.bezierCurveTo(10, -18, 20, -8, 17, 4);
    ctx.bezierCurveTo(15, 14, 7, 18, 0, 15);
    ctx.bezierCurveTo(-7, 18, -15, 14, -17, 4);
    ctx.bezierCurveTo(-20, -8, -10, -18, 0, -10);
    ctx.fillStyle = gr; ctx.fill(); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(0, -10); ctx.quadraticCurveTo(1, -17, 4, -21); ctx.strokeStyle = '#6b4226'; ctx.lineWidth = 3; ctx.stroke();
    ctx.beginPath(); ctx.ellipse(9, -17, 7, 3.5, -.5, 0, Math.PI * 2); ctx.fillStyle = '#5ccf6b'; ctx.fill(); ctx.strokeStyle = OUT; ctx.lineWidth = 2; ctx.stroke();
    ctx.beginPath(); ctx.ellipse(-8, -3, 3, 5.5, .5, 0, Math.PI * 2); ctx.fillStyle = 'rgba(255,255,255,.7)'; ctx.fill();
    if (gold) {
      const tw = .6 + .4 * Math.sin(t * 8);
      ctx.save(); ctx.translate(12, -6); ctx.scale(tw, tw); A.star(ctx, 0, 0, 7, 4, .3); ctx.fillStyle = '#fff'; ctx.fill(); ctx.restore();
    }
  } else if (kind === 'strawberry') {
    ctx.beginPath();
    ctx.moveTo(0, 17);
    ctx.bezierCurveTo(-12, 10, -19, -2, -15, -9);
    ctx.bezierCurveTo(-10, -15, 10, -15, 15, -9);
    ctx.bezierCurveTo(19, -2, 12, 10, 0, 17);
    const gr = ctx.createLinearGradient(-10, -12, 10, 16);
    gr.addColorStop(0, '#ff6b6b'); gr.addColorStop(1, '#d81e4a');
    ctx.fillStyle = gr; ctx.fill(); ctx.stroke();
    ctx.fillStyle = '#ffe39a';
    for (const [sx, sy] of [[-8, -4], [0, -6], [8, -4], [-5, 3], [5, 3], [0, 10], [-10, -9], [10, -9]]) { ctx.beginPath(); ctx.ellipse(sx, sy, 1.3, 2, 0, 0, Math.PI * 2); ctx.fill(); }
    ctx.fillStyle = '#4fbf5c'; ctx.strokeStyle = OUT; ctx.lineWidth = 2;
    ctx.beginPath();
    for (let i = 0; i < 5; i++) { const a = Math.PI + i * Math.PI / 4; ctx.lineTo(Math.cos(a) * 11, -12 + Math.sin(a) * 6); ctx.lineTo(Math.cos(a + Math.PI / 8) * 4, -12 + Math.sin(a + Math.PI / 8) * 2); }
    ctx.closePath(); ctx.fill(); ctx.stroke();
  } else if (kind === 'cherry') {
    ctx.beginPath(); ctx.moveTo(-8, 4); ctx.quadraticCurveTo(-4, -12, 4, -19); ctx.moveTo(9, 6); ctx.quadraticCurveTo(8, -8, 4, -19);
    ctx.strokeStyle = '#6b4226'; ctx.lineWidth = 2.6; ctx.stroke();
    ctx.beginPath(); ctx.ellipse(10, -18, 7, 3.5, .4, 0, Math.PI * 2); ctx.fillStyle = '#5ccf6b'; ctx.fill(); ctx.strokeStyle = OUT; ctx.lineWidth = 2; ctx.stroke();
    for (const [bx, by] of [[-8, 8], [9, 10]]) {
      const gr = ctx.createRadialGradient(bx - 3, by - 3, 1, bx, by, 10);
      gr.addColorStop(0, '#ff8aa0'); gr.addColorStop(.5, '#e0213f'); gr.addColorStop(1, '#a3122c');
      ctx.beginPath(); ctx.arc(bx, by, 9, 0, Math.PI * 2); ctx.fillStyle = gr; ctx.fill(); ctx.lineWidth = 2.6; ctx.stroke();
      ctx.beginPath(); ctx.arc(bx - 3, by - 3, 2.2, 0, Math.PI * 2); ctx.fillStyle = 'rgba(255,255,255,.8)'; ctx.fill();
    }
  } else if (kind === 'grape') {
    ctx.beginPath(); ctx.moveTo(0, -12); ctx.lineTo(1, -20); ctx.strokeStyle = '#6b4226'; ctx.lineWidth = 3; ctx.stroke();
    ctx.beginPath(); ctx.ellipse(-8, -17, 7, 3.5, -.4, 0, Math.PI * 2); ctx.fillStyle = '#5ccf6b'; ctx.fill(); ctx.strokeStyle = OUT; ctx.lineWidth = 2; ctx.stroke();
    const balls = [[-9, -6], [0, -8], [9, -6], [-5, 3], [5, 3], [0, 12]];
    for (const [bx, by] of balls) {
      const gr = ctx.createRadialGradient(bx - 2, by - 2, 1, bx, by, 7);
      gr.addColorStop(0, '#d9b8ff'); gr.addColorStop(.55, '#8f5bd8'); gr.addColorStop(1, '#5a33a0');
      ctx.beginPath(); ctx.arc(bx, by, 6.5, 0, Math.PI * 2); ctx.fillStyle = gr; ctx.fill(); ctx.lineWidth = 2; ctx.strokeStyle = OUT; ctx.stroke();
    }
  }
  ctx.restore();
}
function drawRock(ctx, r) {
  const x = cx(r.x), y = cy(r.y), k = r.pop < 1 ? A.ease.outBack(r.pop) : 1;
  ctx.save(); ctx.translate(x, y); ctx.scale(k, k);
  ctx.globalAlpha = .2; ctx.fillStyle = '#1d3d1a'; ctx.beginPath(); ctx.ellipse(3, 14, 19, 6, 0, 0, Math.PI * 2); ctx.fill(); ctx.globalAlpha = 1;
  ctx.beginPath();
  ctx.moveTo(-18, 8); ctx.quadraticCurveTo(-20, -8, -8, -15); ctx.quadraticCurveTo(6, -21, 15, -10); ctx.quadraticCurveTo(22, 2, 16, 11); ctx.quadraticCurveTo(0, 18, -18, 8);
  const gr = ctx.createLinearGradient(-10, -16, 10, 14);
  gr.addColorStop(0, '#c9ced8'); gr.addColorStop(1, '#7f8796');
  ctx.fillStyle = gr; ctx.fill(); ctx.lineWidth = 3; ctx.strokeStyle = '#3d4250'; ctx.lineJoin = 'round'; ctx.stroke();
  ctx.beginPath(); ctx.moveTo(2, -12); ctx.lineTo(-1, -4); ctx.lineTo(4, 2); ctx.lineWidth = 2; ctx.stroke();
  ctx.beginPath(); ctx.ellipse(-8, -7, 5, 2.5, -.5, 0, Math.PI * 2); ctx.fillStyle = 'rgba(255,255,255,.55)'; ctx.fill();
  ctx.fillStyle = '#7ccf5a'; ctx.beginPath(); ctx.ellipse(12, -10, 5, 3, .3, 0, Math.PI * 2); ctx.fill();
  ctx.restore();
}

/* ---------------- состояние ---------------- */
function newSnake() {
  if (LAND) {                                    // широкое поле: слева посередине, головой вправо
    const sx = 5, sy = 7;
    const cur = [{ x: sx, y: sy }, { x: sx - 1, y: sy }, { x: sx - 2, y: sy }, { x: sx - 3, y: sy }];
    return { cur, prev: cur.map((c) => ({ ...c })), dir: 'right', queue: [], grow: 0, acc: 0, bulges: [] };
  }
  const sx = 7, sy = 16;
  const cur = [{ x: sx, y: sy }, { x: sx, y: sy + 1 }, { x: sx, y: sy + 2 }, { x: sx, y: sy + 3 }];
  return { cur, prev: cur.map((c) => ({ ...c })), dir: 'up', queue: [], grow: 0, acc: 0, bulges: [] };
}
function fresh(mode) {
  const s = { mode, score: 0, shown: 0, eaten: 0, stage: 1, snake: newSnake(), food: null, bonus: null, rocks: [], banner: null, dead: 0, blinkT: 2, tongue: 0, look: LAND ? { x: 1, y: 0 } : { x: 0, y: -1 }, bonusCount: 0 };
  S = s;
  spawnFood();
  return s;
}
const occupied = (x, y, skipTail) => {
  const body = skipTail ? S.snake.cur.slice(0, -1) : S.snake.cur;
  return body.some((c) => c.x === x && c.y === y) || S.rocks.some((r) => r.x === x && r.y === y);
};
function freeCell(minHeadDist = 0) {
  const h = S.snake.cur[0];
  for (let tries = 0; tries < 400; tries++) {
    const x = A.randInt(0, COLS - 1), y = A.randInt(0, ROWS - 1);
    if (occupied(x, y)) continue;
    if (S.food && S.food.x === x && S.food.y === y) continue;
    if (S.bonus && S.bonus.x === x && S.bonus.y === y) continue;
    if (Math.abs(x - h.x) + Math.abs(y - h.y) < minHeadDist) continue;
    return { x, y };
  }
  return null;
}
function spawnFood() {
  const c = freeCell(2) || { x: 0, y: 0 };
  S.food = { ...c, kind: A.pick(FRUITS), pop: 0, ph: Math.random() * 6 };
}
function spawnBonus() {
  const c = freeCell(4);
  if (c) S.bonus = { ...c, kind: 'gold', pop: 0, ph: 0, life: 6, max: 6 };
}
function addRocks(n) {
  const h = S.snake.cur[0], d = DIRS[S.snake.dir];
  for (let i = 0; i < n; i++) {
    const c = freeCell(5);
    if (!c) break;
    // не ставим камень прямо по курсу
    let inPath = false;
    for (let k = 1; k <= 4; k++) if (c.x === h.x + d.x * k && c.y === h.y + d.y * k) inPath = true;
    if (inPath) { i--; continue; }
    S.rocks.push({ ...c, pop: 0 });
  }
}
function banner(text, sub) { S.banner = { text, sub, t: 0 }; }

/* ---------------- экраны ---------------- */
function titleScreen(g) {
  fresh('title'); g.setPlaying(false);
  g.screen({
    kicker: Arcade.framed ? 'Досуг' : 'Аркада', title: 'Змейка',
    html: `<p>Собирайте фрукты в саду и растите. Не врезайтесь в себя, в забор и в камни.</p>${g.best ? `<p class="record">Рекорд: ${g.best.toLocaleString('ru-RU')}</p>` : ''}`,
    button: 'Играть', onGo: () => startGame(g)
  });
}
function startGame(g) {
  fresh('play');
  g.fx.clear(); g.setPlaying(true); g.playMusic();
  banner('Уровень 1', 'Приятного аппетита!');
}
function gameOver(g) {
  S.mode = 'over'; g.setPlaying(false); g.stopMusic(); g.sfx('lose');
  const rec = g.submit(S.score);
  g.screen({
    kicker: 'Змейка устала', title: 'Бум!',
    html: `<div class="score">${S.score.toLocaleString('ru-RU')}</div><p>${rec ? '<span class="record">Новый рекорд!</span>' : `Рекорд: ${g.best.toLocaleString('ru-RU')}`} · длина ${S.snake.cur.length}</p>`,
    button: 'Ещё раз', onGo: () => startGame(g),
    alt: { label: Arcade.framed ? 'К играм' : 'В аркаду', onGo: () => Arcade.home('../index.html') }
  });
}

/* ---------------- управление ---------------- */
const OPP = { up: 'down', down: 'up', left: 'right', right: 'left' };
function queueTurn(d) {
  const sn = S.snake;
  const last = sn.queue.length ? sn.queue[sn.queue.length - 1] : sn.dir;
  if (d === last || d === OPP[last] || sn.queue.length >= 2) return;
  sn.queue.push(d);
}
/* 24.10, владелец: «сложно играть, есть задержка между нажатием на телефоне»: смахивание засчитывалось, только когда палец
   отпустили. Теперь змейка поворачивает, пока палец ещё ведёт: прошёл почти клетку — поворот, и можно вести дальше. */
let drag = null;
function readInput(g) {
  const inp = g.input, p = inp.pointer;
  for (const d of ['up', 'down', 'left', 'right']) if (inp.pressed(d)) queueTurn(d);
  if (p.justDown) drag = { x: p.x, y: p.y, used: false };
  if (p.down && drag) {
    const dx = p.x - drag.x, dy = p.y - drag.y;
    if (Math.hypot(dx, dy) > CELL * .7) {
      queueTurn(Math.abs(dx) > Math.abs(dy) ? (dx > 0 ? 'right' : 'left') : (dy > 0 ? 'down' : 'up'));
      Object.assign(drag, { x: p.x, y: p.y, used: true });
    }
  }
  const dragged = drag && drag.used;
  if (p.justUp) drag = null;
  if (dragged) return;                                    // уже повернули по ходу пальца — отпускание не считаем
  if (inp.swipe) queueTurn(inp.swipe);
  if (inp.tap) {
    const hp = headPos();
    const dx = inp.tap.x - hp.x, dy = inp.tap.y - hp.y;
    const cur = S.snake.queue.length ? S.snake.queue[S.snake.queue.length - 1] : S.snake.dir;
    if (cur === 'up' || cur === 'down') queueTurn(dx < 0 ? 'left' : 'right');
    else if (Math.abs(dy) > 0) queueTurn(dy < 0 ? 'up' : 'down');
    void dx;
  }
}

/* ИИ для заставки */
function aiTurn() {
  const sn = S.snake, h = sn.cur[0];
  const target = S.bonus || S.food;
  const opts = ['up', 'down', 'left', 'right'].filter((d) => d !== OPP[sn.dir]);
  const safe = opts.filter((d) => { const nx = h.x + DIRS[d].x, ny = h.y + DIRS[d].y; return nx >= 0 && ny >= 0 && nx < COLS && ny < ROWS && !occupied(nx, ny, true); });
  if (!safe.length) return;
  safe.sort((a, b) => {
    const da = Math.abs(h.x + DIRS[a].x - target.x) + Math.abs(h.y + DIRS[a].y - target.y);
    const db = Math.abs(h.x + DIRS[b].x - target.x) + Math.abs(h.y + DIRS[b].y - target.y);
    return da - db + (Math.random() - .5) * .6;
  });
  sn.queue = [safe[0]];
}

/* ---------------- шаг змейки ---------------- */
function stepTime() {
  return Math.max(.068, .165 - S.snake.cur.length * .0022 - (S.stage - 1) * .006);
}
function step(g) {
  const sn = S.snake;
  if (S.mode === 'title') aiTurn();
  if (sn.queue.length) sn.dir = sn.queue.shift();
  const d = DIRS[sn.dir], h = sn.cur[0];
  const nx = h.x + d.x, ny = h.y + d.y;
  const willGrow = sn.grow > 0;
  const wall = nx < 0 || ny < 0 || nx >= COLS || ny >= ROWS;
  if (wall || occupied(nx, ny, !willGrow)) {
    if (S.mode === 'title') { const keep = S.score; fresh('title'); S.score = keep; return; }
    die(g, wall ? 'wall' : 'body');
    return;
  }
  sn.prev = sn.cur.map((c) => ({ ...c }));
  sn.cur.unshift({ x: nx, y: ny });
  if (willGrow) sn.grow--; else sn.cur.pop();
  for (const b of sn.bulges) b.p += 1;
  sn.bulges = sn.bulges.filter((b) => b.p < sn.cur.length);
  // еда
  if (S.food && S.food.x === nx && S.food.y === ny) eat(g, S.food, false);
  if (S.bonus && S.bonus.x === nx && S.bonus.y === ny) eat(g, S.bonus, true);
}
function eat(g, f, bonus) {
  const sn = S.snake, x = cx(f.x), y = cy(f.y);
  sn.grow += bonus ? 2 : 1;
  sn.bulges.push({ p: 0 });
  const pts = bonus ? 50 * S.stage : 10 * S.stage;
  if (S.mode === 'play') {
    S.score += pts;
    g.sfx('eat', { pitch: bonus ? 1.4 : A.rand(.9, 1.15) });
    if (bonus) g.sfx('coin');
    g.fx.burst(x, y, { n: bonus ? 22 : 12, colors: bonus ? ['#ffe066', '#fff', '#ffcf3a'] : ['#ff6b6b', '#ffd43b', '#fff', '#7ee08a'], speed: 300, size: 7, shape: bonus ? 'star' : 'circle', life: .55 });
    g.fx.ring(x, y, { r1: 60, color: bonus ? '#ffe066' : '#ffffff', width: 5 });
    g.fx.text(x, y - 20, '+' + pts, { color: bonus ? '#ffe066' : '#fff', size: bonus ? 40 : 30 });
  }
  if (bonus) { S.bonus = null; return; }
  S.eaten++;
  spawnFood();
  if (S.mode === 'play') {
    if (S.eaten % 5 === 0 && !S.bonus && Math.random() < .7) spawnBonus();
    if (S.eaten % 10 === 0) {
      S.stage++;
      addRocks(Math.min(3, 1 + Math.floor(S.stage / 2)));
      banner('Уровень ' + S.stage, 'В саду появились камни');
      g.sfx('power');
    }
  }
}
function die(g, why) {
  S.mode = 'dead'; S.dead = 0; S.deadWhy = why;
  g.stopMusic(); g.sfx('hurt'); g.shake(12, .35);
  const hp = headPos();
  g.fx.burst(hp.x, hp.y, { n: 18, colors: ['#ffffff', '#ffd43b', '#7ee08a'], speed: 320, size: 8, shape: 'star', life: .6 });
  g.fx.ring(hp.x, hp.y, { r1: 90, width: 6 });
}

/* ---------------- обновление ---------------- */
function update(g, dt) {
  if (S.banner) { S.banner.t += dt; if (S.banner.t > 2) S.banner = null; }
  S.shown += (S.score - S.shown) * Math.min(1, dt * 8);
  if (S.food) S.food.pop = Math.min(1, S.food.pop + dt * 3);
  for (const r of S.rocks) r.pop = Math.min(1, r.pop + dt * 2.5);
  if (S.bonus) {
    S.bonus.pop = Math.min(1, S.bonus.pop + dt * 3);
    if (S.mode === 'play' || S.mode === 'title') { S.bonus.life -= dt; if (S.bonus.life <= 0) { g.fx.burst(cx(S.bonus.x), cy(S.bonus.y), { n: 8, colors: ['#ffe066'], speed: 120, size: 5 }); S.bonus = null; } }
  }
  // моргание и язычок
  S.blinkT -= dt; if (S.blinkT < -.14) S.blinkT = A.rand(1.8, 4);
  S.tongue = (S.tongue + dt) % 2.2;
  const tgt = S.bonus || S.food, hp = headPos();
  if (tgt) { const dx = cx(tgt.x) - hp.x, dy = cy(tgt.y) - hp.y, l = Math.hypot(dx, dy) || 1; S.look.x += (dx / l - S.look.x) * Math.min(1, dt * 6); S.look.y += (dy / l - S.look.y) * Math.min(1, dt * 6); }

  if (S.mode === 'dead') {
    S.dead += dt;
    if (S.dead > 1.1) gameOver(g);
    return;
  }
  if (S.mode === 'over') return;
  if (S.mode === 'play') readInput(g);
  const sn = S.snake;
  sn.acc += dt;
  const st = S.mode === 'title' ? .12 : stepTime();
  while (sn.acc >= st && (S.mode === 'play' || S.mode === 'title')) { sn.acc -= st; step(g); }
}

/* ---------------- отрисовка ---------------- */
function headPos() {
  const sn = S.snake, k = S.mode === 'dead' || S.mode === 'over' ? 1 : A.clamp(sn.acc / (S.mode === 'title' ? .12 : stepTime()), 0, 1);
  const a = sn.prev[0] || sn.cur[0], b = sn.cur[0];
  return { x: A.lerp(cx(a.x), cx(b.x), k), y: A.lerp(cy(a.y), cy(b.y), k) };
}
function bodyPoints() {
  const sn = S.snake;
  const k = S.mode === 'dead' || S.mode === 'over' ? 1 : A.clamp(sn.acc / (S.mode === 'title' ? .12 : stepTime()), 0, 1);
  const pts = [];
  for (let i = 0; i < sn.cur.length; i++) {
    const to = sn.cur[i], from = sn.prev[i] || to;
    pts.push({ x: A.lerp(cx(from.x), cx(to.x), k), y: A.lerp(cy(from.y), cy(to.y), k) });
  }
  // хвост: дотягиваем до места, откуда уходит последний сегмент
  return pts;
}
function tracePath(ctx, pts) {
  ctx.beginPath();
  ctx.moveTo(pts[0].x, pts[0].y);
  if (pts.length === 1) { ctx.lineTo(pts[0].x + .1, pts[0].y); return; }
  for (let i = 1; i < pts.length - 1; i++) {
    const mx = (pts[i].x + pts[i + 1].x) / 2, my = (pts[i].y + pts[i + 1].y) / 2;
    ctx.quadraticCurveTo(pts[i].x, pts[i].y, mx, my);
  }
  const l = pts[pts.length - 1];
  ctx.lineTo(l.x, l.y);
}
function drawSnake(ctx, g) {
  const pts = bodyPoints(), sn = S.snake, t = g.t;
  if (!pts.length) return;
  ctx.lineCap = 'round'; ctx.lineJoin = 'round';
  // тень
  ctx.save(); ctx.translate(4, 7); ctx.globalAlpha = .18; tracePath(ctx, pts); ctx.strokeStyle = '#1d3d1a'; ctx.lineWidth = 36; ctx.stroke(); ctx.restore();
  // сужение к хвосту: рисуем хвост тоньше отдельными сегментами
  const n = pts.length;
  const widthAt = (i) => 34 - Math.max(0, i - (n - 6)) * 3;
  // контур
  for (const [w, col] of [[6, OUT], [0, '#5ccf6b']]) {
    for (let i = n - 1; i >= 1; i--) {
      ctx.beginPath();
      const a = pts[i], b = pts[i - 1];
      const pa = i < n - 1 ? { x: (a.x + pts[i + 1].x) / 2, y: (a.y + pts[i + 1].y) / 2 } : a;
      const mb = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
      ctx.moveTo(pa.x, pa.y); ctx.quadraticCurveTo(a.x, a.y, mb.x, mb.y);
      if (i === 1) ctx.lineTo(b.x, b.y);
      ctx.lineWidth = widthAt(i) + w; ctx.strokeStyle = col; ctx.stroke();
    }
    // утолщения от еды — часть тела, а не отдельные шарики
    for (const bl of sn.bulges) {
      const i = Math.min(n - 1, Math.floor(bl.p)), p = pts[i];
      const r = 21 - (bl.p / n) * 4;
      ctx.beginPath(); ctx.arc(p.x, p.y, r + w / 2, 0, Math.PI * 2); ctx.fillStyle = col; ctx.fill();
    }
  }
  // светлое брюшко
  if (n > 2) { ctx.save(); ctx.translate(-2, -3); tracePath(ctx, pts.slice(0, n - 2)); ctx.strokeStyle = '#a8ee7a'; ctx.lineWidth = 10; ctx.stroke(); ctx.restore(); }
  // узор — точки
  ctx.fillStyle = '#3fae55';
  for (let i = 1; i < n - 1; i++) {
    const a = pts[i], b = pts[i + 1];
    const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
    ctx.beginPath(); ctx.arc(mx + 5, my + 5, 3.4, 0, Math.PI * 2); ctx.fill();
  }
  // голова
  const hp = pts[0];
  const dir = DIRS[sn.dir];
  let ang = Math.atan2(dir.y, dir.x);
  if (n > 1) ang = Math.atan2(hp.y - pts[1].y, hp.x - pts[1].x) || ang;
  if (n > 1 && Math.hypot(hp.x - pts[1].x, hp.y - pts[1].y) < 1) ang = Math.atan2(dir.y, dir.x);
  let bump = 0;
  if (S.mode === 'dead' || S.mode === 'over') bump = Math.sin(Math.min(1, S.dead / .35) * Math.PI) * 10;
  ctx.save(); ctx.translate(hp.x + Math.cos(ang) * bump, hp.y + Math.sin(ang) * bump); ctx.rotate(ang);
  const dead = S.mode === 'dead' || S.mode === 'over';
  // язычок
  if (!dead && S.tongue < .35) {
    const out = Math.sin(S.tongue / .35 * Math.PI) * 18;
    ctx.beginPath(); ctx.moveTo(18, 0); ctx.lineTo(20 + out, 0); ctx.lineTo(24 + out, -5); ctx.moveTo(20 + out, 0); ctx.lineTo(24 + out, 5);
    ctx.strokeStyle = '#ff4f7b'; ctx.lineWidth = 3.5; ctx.lineCap = 'round'; ctx.stroke();
  }
  ctx.beginPath(); ctx.ellipse(2, 0, 26, 23, 0, 0, Math.PI * 2);
  const hg = ctx.createRadialGradient(-2, -8, 4, 0, 0, 28);
  hg.addColorStop(0, '#8deb8e'); hg.addColorStop(1, '#4cc15e');
  ctx.fillStyle = hg; ctx.fill(); ctx.lineWidth = 3.5; ctx.strokeStyle = OUT; ctx.stroke();
  // щёчки
  ctx.fillStyle = 'rgba(255,120,150,.55)';
  ctx.beginPath(); ctx.ellipse(10, -16, 5, 3, 0, 0, Math.PI * 2); ctx.ellipse(10, 16, 5, 3, 0, 0, Math.PI * 2); ctx.fill();
  // глаза
  const blink = S.blinkT < 0;
  const lx = S.look.x * Math.cos(-ang) - S.look.y * Math.sin(-ang), ly = S.look.x * Math.sin(-ang) + S.look.y * Math.cos(-ang);
  for (const sy of [-1, 1]) {
    const ex = 4, ey = sy * 10;
    if (dead) {
      ctx.strokeStyle = OUT; ctx.lineWidth = 3.5; ctx.lineCap = 'round';
      ctx.beginPath(); ctx.moveTo(ex - 5, ey - 5); ctx.lineTo(ex + 5, ey + 5); ctx.moveTo(ex + 5, ey - 5); ctx.lineTo(ex - 5, ey + 5); ctx.stroke();
      continue;
    }
    ctx.beginPath(); ctx.ellipse(ex, ey, 9, blink ? 1.6 : 9, 0, 0, Math.PI * 2); ctx.fillStyle = '#fff'; ctx.fill(); ctx.lineWidth = 2.6; ctx.strokeStyle = OUT; ctx.stroke();
    if (!blink) {
      ctx.beginPath(); ctx.arc(ex + lx * 3.5, ey + ly * 3.5, 4.8, 0, Math.PI * 2); ctx.fillStyle = OUT; ctx.fill();
      ctx.beginPath(); ctx.arc(ex + lx * 3.5 - 1.6, ey + ly * 3.5 - 1.8, 1.7, 0, Math.PI * 2); ctx.fillStyle = '#fff'; ctx.fill();
    }
  }
  // ноздри / улыбка
  ctx.fillStyle = OUT; ctx.beginPath(); ctx.arc(22, -4, 1.6, 0, Math.PI * 2); ctx.arc(22, 4, 1.6, 0, Math.PI * 2); ctx.fill();
  ctx.restore();
}

function drawField(ctx, g) {
  // фон сада
  const bg = ctx.createLinearGradient(0, 0, 0, H);
  bg.addColorStop(0, '#2f7d46'); bg.addColorStop(.12, '#4a9d4f'); bg.addColorStop(1, '#3f8f45');
  ctx.fillStyle = bg; ctx.fillRect(0, 0, W, H);
  if (LAND) landGarden(ctx);
  // шапка — живая изгородь
  else {
  ctx.fillStyle = '#2a6b3d';
  for (let x = -20; x < W + 40; x += 46) { ctx.beginPath(); ctx.arc(x, 128, 34, 0, Math.PI * 2); ctx.fill(); }
  ctx.fillStyle = '#34804a';
  for (let x = 3; x < W + 40; x += 46) { ctx.beginPath(); ctx.arc(x, 136, 26, 0, Math.PI * 2); ctx.fill(); }
  ctx.fillStyle = '#1f4f2f'; ctx.fillRect(0, 0, W, 110);
  const sky = ctx.createLinearGradient(0, 0, 0, 110);
  sky.addColorStop(0, '#1d4a2c'); sky.addColorStop(1, '#2a6b3d');
  ctx.fillStyle = sky; ctx.fillRect(0, 0, W, 112);
  }
  for (const d of DECOR) {
    if (d.kind === 'flower') drawFlower(ctx, d, g.t);
    else { ctx.beginPath(); ctx.ellipse(d.x, d.y, d.r, d.r * .7, 0, 0, Math.PI * 2); ctx.fillStyle = '#c9c2b5'; ctx.fill(); ctx.beginPath(); ctx.ellipse(d.x - d.r * .3, d.y - d.r * .25, d.r * .35, d.r * .2, 0, 0, Math.PI * 2); ctx.fillStyle = 'rgba(255,255,255,.6)'; ctx.fill(); }
  }
  // поле
  const fw = COLS * CELL, fh = ROWS * CELL;
  ctx.save();
  A.rr(ctx, FX0 - 8, FY0 - 8, fw + 16, fh + 16, 26); ctx.fillStyle = '#2b6a37'; ctx.fill();
  A.rr(ctx, FX0, FY0, fw, fh, 20); ctx.clip();
  ctx.fillStyle = '#8fd56b'; ctx.fillRect(FX0, FY0, fw, fh);
  ctx.fillStyle = '#84cc61';
  for (let y = 0; y < ROWS; y++) for (let x = (y & 1); x < COLS; x += 2) ctx.fillRect(FX0 + x * CELL, FY0 + y * CELL, CELL, CELL);
  // мягкая виньетка
  const vg = ctx.createRadialGradient(W / 2, FY0 + fh / 2, fh * .3, W / 2, FY0 + fh / 2, fh * .75);
  vg.addColorStop(0, 'rgba(255,255,220,.08)'); vg.addColorStop(1, 'rgba(20,60,20,.18)');
  ctx.fillStyle = vg; ctx.fillRect(FX0, FY0, fw, fh);
  // травинки
  ctx.strokeStyle = 'rgba(60,140,60,.35)'; ctx.lineWidth = 2; ctx.lineCap = 'round';
  for (let i = 0; i < 40; i++) {
    const gx = FX0 + ((i * 97) % fw), gy = FY0 + ((i * 211) % fh);
    ctx.beginPath(); ctx.moveTo(gx, gy); ctx.lineTo(gx - 3, gy - 7); ctx.moveTo(gx + 4, gy); ctx.lineTo(gx + 5, gy - 6); ctx.stroke();
  }
  ctx.restore();
  A.rr(ctx, FX0, FY0, fw, fh, 20); ctx.lineWidth = 4; ctx.strokeStyle = 'rgba(30,80,40,.6)'; ctx.stroke();
}
function drawFly(ctx, f, t) {
  const tt = t * .23 + f.ph;
  const x = W / 2 + Math.sin(tt * 1.3) * (LAND ? 560 : 300) + Math.sin(tt * 3.1) * 40;
  const y = (LAND ? H / 2 : 640) + Math.sin(tt * .9 + 1) * (LAND ? 300 : 520) + Math.cos(tt * 2.7) * 30;
  const flap = Math.abs(Math.sin(t * 14 + f.ph));
  ctx.save(); ctx.translate(x, y); ctx.rotate(Math.cos(tt * 1.3) * .4);
  ctx.globalAlpha = .9;
  for (const sx of [-1, 1]) {
    ctx.save(); ctx.scale(sx * (.3 + .7 * flap), 1);
    ctx.beginPath(); ctx.ellipse(8, -6, 9, 7, -.4, 0, Math.PI * 2); ctx.ellipse(7, 6, 6, 5, .4, 0, Math.PI * 2);
    ctx.fillStyle = f.c; ctx.fill(); ctx.lineWidth = 2; ctx.strokeStyle = OUT; ctx.stroke();
    ctx.restore();
  }
  ctx.beginPath(); ctx.ellipse(0, 0, 2.5, 9, 0, 0, Math.PI * 2); ctx.fillStyle = OUT; ctx.fill();
  ctx.restore(); ctx.globalAlpha = 1;
}
/* широкое окно: живые изгороди сверху и снизу во всю ширину */
function landGarden(ctx) {
  for (const [y0, k] of [[0, 1], [H, -1]]) {
    ctx.fillStyle = '#2a6b3d';
    for (let x = -20; x < W + 40; x += 46) { ctx.beginPath(); ctx.arc(x, y0 + k * 2, 30, 0, Math.PI * 2); ctx.fill(); }
    ctx.fillStyle = '#34804a';
    for (let x = 3; x < W + 40; x += 46) { ctx.beginPath(); ctx.arc(x, y0 + k * 8, 23, 0, Math.PI * 2); ctx.fill(); }
  }
}
/* деревянная табличка на двух столбиках — как вывеска «Змейка» */
function woodSign(ctx, x, y, w, h) {
  ctx.save(); ctx.globalAlpha = .2; ctx.fillStyle = '#1d3d1a'; ctx.beginPath(); ctx.ellipse(x + w / 2 + 4, y + h + 30, w * .42, 7, 0, 0, Math.PI * 2); ctx.fill(); ctx.restore();
  ctx.lineWidth = 4; ctx.strokeStyle = '#6b4226'; ctx.fillStyle = '#9a6537';
  for (const px of [x + w * .26, x + w * .74]) { A.rr(ctx, px - 6, y + h - 12, 12, 42, 5); ctx.fill(); ctx.stroke(); }
  A.rr(ctx, x, y, w, h, 20); ctx.fillStyle = '#c98a4b'; ctx.fill(); ctx.lineWidth = 5; ctx.strokeStyle = '#6b4226'; ctx.stroke();
  ctx.fillStyle = 'rgba(255,255,255,.18)'; A.rr(ctx, x + 10, y + 8, w - 20, 14, 7); ctx.fill();
}
function hudLand(ctx, g) {
  const LX = FX0 / 2, RX = W - FX0 / 2, sw = 164, lab = { size: 22, weight: 800, color: '#fff7e0', stroke: '#6b4226', strokeW: 6 };
  const sc = Math.round(S.shown).toLocaleString('ru-RU');
  woodSign(ctx, LX - sw / 2, 74, sw, 128);
  A.text(ctx, 'Очки', LX, 106, lab);
  A.text(ctx, sc, LX, 156, { size: sc.length > 5 ? 38 : 46, color: '#fff', stroke: OUT, strokeW: 9 });
  woodSign(ctx, LX - sw / 2, 270, sw, 116);
  A.text(ctx, 'Уровень', LX, 302, lab);
  A.text(ctx, String(S.stage), LX, 348, { size: 44, color: '#fff', stroke: OUT, strokeW: 9 });
  woodSign(ctx, RX - sw / 2, 74, sw, 128);
  A.text(ctx, 'Фрукты', RX, 106, lab);
  drawFruit(ctx, 'apple', RX - 36, 154, 1.1, g.t);
  A.text(ctx, '× ' + S.eaten, RX - 10, 156, { align: 'left', size: 38, color: '#fff', stroke: OUT, strokeW: 8 });
  woodSign(ctx, RX - sw / 2, 270, sw, 116);
  A.text(ctx, 'Рекорд', RX, 302, lab);
  const best = Math.max(g.best || 0, S.score).toLocaleString('ru-RU');
  A.text(ctx, best, RX, 348, { size: best.length > 5 ? 32 : 38, color: '#ffe066', stroke: OUT, strokeW: 8 });
  const tip = A.isTouch ? ['Проведите', 'пальцем'] : ['Стрелки', 'или WASD'];
  tip.forEach((l, i) => A.text(ctx, l, RX, 590 + i * 32, { size: 22, weight: 700, color: '#d8ffc2', stroke: OUT, strokeW: 6 }));
}
function drawHud(ctx, g) {
  if (LAND) hudLand(ctx, g);
  else {
  A.text(ctx, Math.round(S.shown).toLocaleString('ru-RU'), 32, 58, { align: 'left', size: 46, color: '#fff', stroke: OUT, strokeW: 9 });
  A.text(ctx, 'Уровень ' + S.stage, 34, 100, { align: 'left', size: 22, weight: 700, color: '#d8ffc2', stroke: OUT, strokeW: 6 });
  drawFruit(ctx, 'apple', W - 150, 60, 1.1, g.t);
  A.text(ctx, '× ' + S.eaten, W - 122, 62, { align: 'left', size: 38, color: '#fff', stroke: OUT, strokeW: 8 });
  }
  if (S.banner) {
    const t = S.banner.t, k = t < .35 ? A.ease.outBack(t / .35) : 1, a = t > 1.6 ? 1 - (t - 1.6) / .4 : 1;
    ctx.save(); ctx.globalAlpha = Math.max(0, a); ctx.translate(W / 2, H * .4); ctx.scale(k, k);
    A.text(ctx, S.banner.text, 0, 0, { size: 76, color: '#fff', stroke: OUT, strokeW: 14, weight: 900 });
    if (S.banner.sub) A.text(ctx, S.banner.sub, 0, 64, { size: 32, color: '#ffe066', stroke: OUT, strokeW: 8 });
    ctx.restore();
  }
}
function draw(ctx, g) {
  const t = g.t;
  drawField(ctx, g);
  for (const r of S.rocks) drawRock(ctx, r);
  if (S.food) {
    const f = S.food, k = A.ease.outBack(f.pop);
    drawFruit(ctx, f.kind, cx(f.x), cy(f.y) + Math.sin(t * 3 + f.ph) * 2.5, k, t);
  }
  if (S.bonus) {
    const b = S.bonus, x = cx(b.x), y = cy(b.y), frac = b.life / b.max;
    ctx.beginPath(); ctx.arc(x, y, 26, 0, Math.PI * 2); ctx.fillStyle = 'rgba(255,240,150,.35)'; ctx.fill();
    ctx.beginPath(); ctx.arc(x, y, 26, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * frac); ctx.lineWidth = 5; ctx.lineCap = 'round'; ctx.strokeStyle = frac < .3 && Math.floor(t * 8) % 2 ? '#fff' : '#ffcf3a'; ctx.stroke();
    drawFruit(ctx, 'gold', x, y + Math.sin(t * 4) * 2, A.ease.outBack(b.pop) * 1.05, t);
  }
  drawSnake(ctx, g);
  for (const f of FLIES) drawFly(ctx, f, t);
  if (S.mode !== 'title') drawHud(ctx, g);
  else {
    ctx.save(); ctx.translate(W / 2, LAND ? 48 : 62); ctx.rotate(Math.sin(t * 1.2) * .02);
    A.rr(ctx, -150, -40, 300, 80, 22); ctx.fillStyle = '#c98a4b'; ctx.fill(); ctx.lineWidth = 5; ctx.strokeStyle = '#6b4226'; ctx.stroke();
    ctx.fillStyle = 'rgba(255,255,255,.18)'; A.rr(ctx, -140, -32, 280, 16, 8); ctx.fill();
    A.text(ctx, 'Змейка', 0, 3, { size: 48, weight: 900, color: '#fff7e0', stroke: '#6b4226', strokeW: 8 });
    ctx.restore();
  }
}

A.game({
  id: 'snake', tone: 'light', title: 'Змейка', width: W, height: H, orientation: LAND ? 'landscape' : 'portrait', music: 'garden',
  help: {
    desktop: '<kbd>←</kbd> <kbd>→</kbd> <kbd>↑</kbd> <kbd>↓</kbd> или <kbd>W</kbd><kbd>A</kbd><kbd>S</kbd><kbd>D</kbd> — поворот · <kbd>P</kbd> пауза · <kbd>M</kbd> музыка',
    short: '<b>Стрелки</b> или <b>WASD</b> — поворот',
    touch: 'Проводите пальцем в нужную сторону — змейка повернёт'
  },
  init(g) { DECOR = makeDecor(); FLIES = [0, 1, 2].map((i) => ({ ph: i * 2.1, c: ['#ffd43b', '#ff8fc7', '#8fd3ff'][i] })); titleScreen(g); window.__snake = () => S; },
  update, draw
});
})();
