/* Кирпичики — конфетный арканоид. */
(() => {
'use strict';
const A = Arcade;
/* Широкое окно (лист «Досуг» на компьютере) — своя раскладка 1280×720: конфетный фон во всю ширину, поле между
   полосатыми бортиками посередине во всю высоту (мир прежний, книжный, без верхней полосы очков), слева — очки,
   уровень, жизни и бонусы, справа — рекорд, капсулы и управление. Узкое окно (телефон) — как было. */
const LAND = (() => { try { return innerWidth > (innerHeight - 110) * 1.15; } catch (e) { return false; } })();
const W = 720, H = 1280, OUT = '#2b2550';                // мир игры — всегда книжный
const SW = LAND ? 1280 : W, SH = LAND ? 720 : H;          // холст
const VY = LAND ? 110 : 0;                                // в широком окне мир виден с этой высоты (выше — бывшая полоса очков)
const FS = SH / (H - VY), FW = W * FS, FX = (SW - FW) / 2, FY = -VY * FS;
/* боковые колонки — у краёв: карточка меню в листе «Досуг» (~770 px) закрывает x ≈ 250…1030, y ≈ 175…550 */
const PW = 218, LCX = 26 + PW / 2, RCX = SW - 26 - PW / 2;
const COLS = 10, BW = 62, BH = 40, GAP = 6, LEFT = (W - (COLS * BW + (COLS - 1) * GAP)) / 2, TOP = 214;
const WALL = 14, TOPWALL = 150, PADDLE_Y = 1130, PADDLE_H = 36, BALL_R = 16;
const BASE_W = 150, WIDE_W = 236;

const COLORS = {
  r: ['#ffa3b8', '#ff5c85'], o: ['#ffc98a', '#ff922b'], y: ['#fff09a', '#fcc419'], g: ['#a6f0b0', '#40c057'],
  b: ['#b9e1ff', '#4dabf7'], p: ['#ddd0ff', '#9775fa'], m: ['#a9f5df', '#20c997']
};
const CHOC = ['#c99068', '#8a5a3b'], METAL = ['#f1f3f5', '#9aa3ad'];

/* Уровни: строчная буква — 1 удар, заглавная — 2 удара, # — шоколад (3 удара), X — металл (не ломается). */
const LEVELS = [
  { name: 'Радуга', map: [
    'rrrrrrrrrr',
    'oooooooooo',
    'yyyyyyyyyy',
    'gggggggggg',
    'bbbbbbbbbb',
    'pppppppppp'] },
  { name: 'Сердечко', map: [
    '.rr....rr.',
    'rrrr..rrrr',
    'rrRrrrrRrr',
    'rrrrrrrrrr',
    '.rrrrrrrr.',
    '..rrrrrr..',
    '...rrrr...',
    '....rr....'] },
  { name: 'Улыбка', map: [
    '..yyyyyy..',
    '.yyyyyyyy.',
    'yyBByyBByy',
    'yyBByyBByy',
    'yyyyyyyyyy',
    'yRyyyyyyRy',
    'yyRRRRRRyy',
    '.yyyyyyyy.',
    '..yyyyyy..'] },
  { name: 'Пришелец', map: [
    '..p....p..',
    '...p..p...',
    '..pPPPPp..',
    '.pp.pp.pp.',
    'pppppppppp',
    'p.pppppp.p',
    'p.p....p.p',
    '...pp.pp..'] },
  { name: 'Конфета', map: [
    'o........o',
    'oo.mmmm.oo',
    'oommMMmmoo',
    'oomM##Mmoo',
    'oommMMmmoo',
    'oo.mmmm.oo',
    'o........o'] },
  { name: 'Шахматы', map: [
    'r.o.y.g.b.',
    '.p.r.o.y.g',
    'b.p.r.o.y.',
    '.g.b.p.r.o',
    'y.g.b.p.r.',
    'YyGgBbPpRr'] },
  { name: 'Арка', map: [
    'bbbbbbbbbb',
    'bBBBBBBBBb',
    'bB......Bb',
    'bB.yyyy.Bb',
    'bB.y##y.Bb',
    'bB.yyyy.Bb',
    'XX......XX'] },
  { name: 'Замок', map: [
    'p.p.pp.p.p',
    'pppppppppp',
    'P#P#PP#P#P',
    'pppppppppp',
    'mmmmmmmmmm',
    '..XX..XX..',
    'MMMMMMMMMM'] }
];

let S = null;

/* ---------------- фон ---------------- */
const BUBBLES = Array.from({ length: 14 }, () => ({ x: A.rand(0, W), y: A.rand(0, H), r: A.rand(30, 90), sp: A.rand(10, 26), ph: A.rand(0, 6) }));
const SPRINKLES = Array.from({ length: 34 }, () => ({ x: A.rand(0, W), y: A.rand(0, H), rot: A.rand(0, 6), vr: A.rand(-.6, .6), sp: A.rand(14, 34), col: A.pick(['#ff8fb1', '#ffd43b', '#74c0fc', '#8ce99a', '#b197fc', '#ffa94d']) }));
function drawBackground(ctx, t) {
  const gr = ctx.createLinearGradient(0, 0, 0, H);
  gr.addColorStop(0, '#ffd6ec'); gr.addColorStop(.5, '#e7ddff'); gr.addColorStop(1, '#cfeaff');
  ctx.fillStyle = gr; ctx.fillRect(0, 0, W, H);
  for (const b of BUBBLES) {
    const y = ((b.y - t * b.sp) % (H + 200) + H + 200) % (H + 200) - 100, x = b.x + Math.sin(t * .5 + b.ph) * 20;
    const rg = ctx.createRadialGradient(x - b.r * .3, y - b.r * .3, 2, x, y, b.r);
    rg.addColorStop(0, 'rgba(255,255,255,.55)'); rg.addColorStop(.7, 'rgba(255,255,255,.12)'); rg.addColorStop(1, 'rgba(255,255,255,0)');
    ctx.fillStyle = rg; ctx.beginPath(); ctx.arc(x, y, b.r, 0, Math.PI * 2); ctx.fill();
  }
  ctx.globalAlpha = .55;
  for (const s of SPRINKLES) {
    const y = ((s.y - t * s.sp) % (H + 40) + H + 40) % (H + 40) - 20;
    ctx.save(); ctx.translate(s.x, y); ctx.rotate(s.rot + t * s.vr);
    A.rr(ctx, -9, -3, 18, 6, 3); ctx.fillStyle = s.col; ctx.fill(); ctx.restore();
  }
  ctx.globalAlpha = 1;
}
function drawRails(ctx) {
  const stripe = (x, y, w, h) => {
    ctx.save(); A.rr(ctx, x, y, w, h, Math.min(w, h) / 2); ctx.fillStyle = '#fff'; ctx.fill(); ctx.clip();
    ctx.fillStyle = '#ff7aa8';
    for (let k = -H; k < H + W; k += 26) { ctx.beginPath(); ctx.moveTo(x + k, y); ctx.lineTo(x + k + 12, y); ctx.lineTo(x + k + 12 - h - w, y + h + w); ctx.lineTo(x + k - h - w, y + h + w); ctx.closePath(); ctx.fill(); }
    ctx.restore();
    A.rr(ctx, x, y, w, h, Math.min(w, h) / 2); ctx.lineWidth = 3; ctx.strokeStyle = OUT; ctx.stroke();
  };
  stripe(0, TOPWALL - WALL, WALL, H - TOPWALL + WALL + 20);
  stripe(W - WALL, TOPWALL - WALL, WALL, H - TOPWALL + WALL + 20);
  stripe(0, TOPWALL - WALL, W, WALL);
}

/* ---------------- состояние ---------------- */
function fresh(attract) {
  return {
    attract, mode: attract ? 'attract' : 'play', score: 0, shown: 0, lives: 3, level: 0, combo: 0,
    bricks: [], balls: [], caps: [], banner: null, slowT: 0, speedUp: 0,
    P: { x: W / 2, y: PADDLE_Y, w: BASE_W, h: PADDLE_H, wideT: 0, stickyT: 0, squash: 0, happy: 0, sad: 0, vx: 0 }
  };
}
function loadLevel(i) {
  const L = LEVELS[i % LEVELS.length];
  S.bricks = [];
  L.map.forEach((row, r) => {
    for (let c = 0; c < COLS; c++) {
      const ch = row[c] || '.';
      if (ch === '.') continue;
      const b = { x: LEFT + c * (BW + GAP), y: TOP + r * (BH + GAP), w: BW, h: BH, bump: 0, seed: Math.random() * 1000, dead: false };
      if (ch === 'X') Object.assign(b, { hp: 1, max: 1, metal: true, col: METAL });
      else if (ch === '#') Object.assign(b, { hp: 3, max: 3, choc: true, col: CHOC });
      else if (COLORS[ch]) Object.assign(b, { hp: 1, max: 1, col: COLORS[ch] });
      else if (COLORS[ch.toLowerCase()]) Object.assign(b, { hp: 2, max: 2, col: COLORS[ch.toLowerCase()] });
      else continue;
      S.bricks.push(b);
    }
  });
  S.balls = []; S.caps = []; S.slowT = 0; S.speedUp = 0; S.combo = 0;
  S.P.wideT = 0; S.P.stickyT = 0;
  newStuckBall();
}
function newStuckBall() { S.balls.push({ x: S.P.x, y: S.P.y - S.P.h / 2 - BALL_R - 1, vx: 0, vy: 0, r: BALL_R, stuck: true, off: A.rand(-20, 20), trail: [] }); }
const baseSpeed = () => (640 + (S.level % LEVELS.length) * 22 + Math.floor(S.level / LEVELS.length) * 90) * (1 + S.speedUp) * (S.slowT > 0 ? .68 : 1);
function banner(text, sub) { S.banner = { text, sub, t: 0 }; }
function sfx(g, name, o) { if (!S.attract) g.sfx(name, o); }

function startGame(g) {
  S = fresh(false); loadLevel(0);
  g.fx.clear(); g.setPlaying(true); g.playMusic();
  banner('Уровень 1', LEVELS[0].name);
}
function nextLevel(g) {
  S.level++; S.mode = 'play'; loadLevel(S.level);
  g.setPlaying(true);
  const lp = Math.floor(S.level / LEVELS.length);
  banner('Уровень ' + (S.level + 1), LEVELS[S.level % LEVELS.length].name + (lp ? ' · быстрее!' : ''));
}
function titleScreen(g) {
  S = fresh(true); loadLevel(0);
  g.setPlaying(false);
  g.screen({
    kicker: Arcade.framed ? 'Досуг' : 'Аркада', title: 'Кирпичики',
    html: `<p>Отбивайте мячик и разбивайте сладкие кирпичики. Ловите капсулы — в них бонусы.</p>${g.best ? `<p class="record">Рекорд: ${g.best.toLocaleString('ru-RU')}</p>` : ''}`,
    button: 'Играть', onGo: () => startGame(g)
  });
}
function levelClear(g) {
  S.mode = 'clear'; g.setPlaying(false);
  const bonus = 500 + S.lives * 250;
  S.score += bonus;
  g.sfx('win');
  g.fx.burst(W / 2, H / 2, { n: 50, colors: ['#ff8fb1', '#ffd43b', '#74c0fc', '#8ce99a', '#b197fc'], speed: 700, size: 12, shape: 'star', life: 1.2, gravity: 300 });
  g.screen({
    kicker: 'Уровень ' + (S.level + 1), title: 'Чисто!',
    html: `<div class="score">${S.score.toLocaleString('ru-RU')}</div><p>Бонус за жизни: +${bonus.toLocaleString('ru-RU')}</p>`,
    button: 'Дальше', onGo: () => nextLevel(g)
  });
}
function gameOver(g) {
  S.mode = 'over'; g.setPlaying(false); g.stopMusic(); g.sfx('lose');
  const rec = g.submit(S.score);
  g.screen({
    kicker: 'Мячики закончились', title: 'Игра окончена',
    html: `<div class="score">${S.score.toLocaleString('ru-RU')}</div><p>${rec ? '<span class="record">Новый рекорд!</span>' : `Рекорд: ${g.best.toLocaleString('ru-RU')}`} · уровень ${S.level + 1}</p>`,
    button: 'Ещё раз', onGo: () => startGame(g),
    alt: { label: Arcade.framed ? 'К играм' : 'В аркаду', onGo: () => Arcade.home('../index.html') }
  });
}

/* ---------------- игра ---------------- */
function launch(g) {
  let any = false;
  for (const b of S.balls) {
    if (!b.stuck) continue;
    const k = A.clamp(b.off / (S.P.w / 2), -1, 1) * .55 + A.rand(-.08, .08);
    const sp = baseSpeed();
    b.vx = Math.sin(k) * sp; b.vy = -Math.cos(k) * sp; b.stuck = false; any = true;
  }
  if (any) sfx(g, 'bounce', { pitch: 1.3 });
}
function hitBrick(g, br, ball) {
  br.bump = 1;
  if (br.metal) {
    sfx(g, 'hit', { pitch: 2, vol: .5, gap: .04 });
    g.fx.burst(ball.x, ball.y, { n: 5, colors: ['#fff', '#dee2e6'], speed: 200, size: 4, shape: 'spark', life: .25 });
    return;
  }
  br.hp--;
  if (br.hp > 0) {
    sfx(g, 'pling', { pitch: .7, gap: .02 });
    g.fx.burst(ball.x, ball.y, { n: 6, colors: [br.col[0], '#fff'], speed: 200, size: 5, life: .3 });
    return;
  }
  br.dead = true;
  S.combo++;
  const pts = (br.choc ? 150 : br.max === 2 ? 100 : 50) + (S.combo - 1) * 10;
  if (!S.attract) S.score += pts;
  const cx = br.x + br.w / 2, cy = br.y + br.h / 2;
  sfx(g, 'pling', { pitch: Math.min(2.4, 1 + S.combo * .07), gap: .02 });
  g.fx.burst(cx, cy, { n: 12, colors: [br.col[0], br.col[1], '#fff'], speed: 320, size: 9, shape: 'square', life: .6, gravity: 700, drag: 1 });
  g.fx.burst(cx, cy, { n: 4, colors: ['#fff'], speed: 160, size: 6, shape: 'star', life: .4 });
  if (!S.attract) g.fx.text(cx, cy - 6, '+' + pts, { color: S.combo >= 5 ? '#ffe066' : '#fff', size: S.combo >= 5 ? 34 : 26, rise: 50 });
  if (S.combo > 0 && S.combo % 5 === 0) { g.shake(5, .15); if (!S.attract) g.fx.text(W / 2, PADDLE_Y - 200, 'Комбо ×' + S.combo + '!', { color: '#ff5c85', size: 44 }); }
  if (Math.random() < .14) {
    const types = ['wide', 'multi', 'slow', 'sticky', 'multi', 'wide'];
    if (S.lives < 5 && Math.random() < .25) types.push('life', 'life');
    S.caps.push({ x: cx, y: cy, type: A.pick(types), vy: 250, ph: Math.random() * 6 });
  }
}
function brickAt(ball) {
  const r = ball.r * .92;
  for (const br of S.bricks) {
    if (br.dead) continue;
    if (ball.x + r > br.x && ball.x - r < br.x + br.w && ball.y + r > br.y && ball.y - r < br.y + br.h) return br;
  }
  return null;
}
function ensureVertical(b) {
  const sp = Math.hypot(b.vx, b.vy) || 1;
  if (Math.abs(b.vy) < sp * .32) {
    b.vy = (b.vy >= 0 ? 1 : -1) * sp * .32;
    b.vx = Math.sign(b.vx || 1) * Math.sqrt(Math.max(0, sp * sp - b.vy * b.vy));
  }
}
function moveBall(g, b, dt) {
  const P = S.P;
  const dist = Math.hypot(b.vx, b.vy) * dt, n = Math.max(1, Math.ceil(dist / 5)), sdt = dt / n;
  for (let i = 0; i < n; i++) {
    b.x += b.vx * sdt;
    if (b.x < WALL + b.r) { b.x = WALL + b.r; b.vx = Math.abs(b.vx); sfx(g, 'bounce', { pitch: .8, vol: .5, gap: .05 }); }
    else if (b.x > W - WALL - b.r) { b.x = W - WALL - b.r; b.vx = -Math.abs(b.vx); sfx(g, 'bounce', { pitch: .8, vol: .5, gap: .05 }); }
    let br = brickAt(b);
    if (br) { b.x -= b.vx * sdt; b.vx = -b.vx; hitBrick(g, br, b); }
    b.y += b.vy * sdt;
    if (b.y < TOPWALL + b.r) { b.y = TOPWALL + b.r; b.vy = Math.abs(b.vy); sfx(g, 'bounce', { pitch: .8, vol: .5, gap: .05 }); }
    br = brickAt(b);
    if (br) { b.y -= b.vy * sdt; b.vy = -b.vy; hitBrick(g, br, b); ensureVertical(b); }
    // ракетка
    const top = P.y - P.h / 2;
    const prevBottom = b.y - b.vy * sdt + b.r;
    if (b.vy > 0 && prevBottom <= top + 1 && b.y + b.r >= top && Math.abs(b.x - P.x) <= P.w / 2 + b.r * .7) {
      b.y = top - b.r;
      const off = A.clamp((b.x - P.x) / (P.w / 2), -1, 1);
      S.speedUp = Math.min(.18, S.speedUp + .006);
      const sp = baseSpeed(), a = off * 1.08;
      b.vx = Math.sin(a) * sp; b.vy = -Math.cos(a) * sp;
      P.squash = 1; P.happy = .5; S.combo = 0;
      sfx(g, 'bounce', { pitch: 1 + Math.abs(off) * .2 });
      g.fx.burst(b.x, top, { n: 6, colors: ['#fff', '#d0bfff'], speed: 180, size: 5, angle: -Math.PI / 2, spread: 1.2, life: .3 });
      if (P.stickyT > 0) { b.stuck = true; b.off = b.x - P.x; b.vx = 0; b.vy = 0; return; }
    }
  }
}

/* широкое окно: касания и мышь — в координаты мира (поле уменьшено и сдвинуто) */
function wIn(inp) {
  if (!LAND) return inp;
  const p = inp.pointer, k = 1 / FS, wx = (x) => (x - FX) * k, wy = (y) => (y - FY) * k;
  return {
    down: (n) => inp.down(n), pressed: (n) => inp.pressed(n), swipe: inp.swipe,
    get mouseActive() { return inp.mouseActive; }, set mouseActive(v) { inp.mouseActive = v; },
    tap: inp.tap && { x: wx(inp.tap.x), y: wy(inp.tap.y) },
    pointer: Object.assign({}, p, { x: wx(p.x), y: wy(p.y), sx: wx(p.sx), sy: wy(p.sy), dx: p.dx * k, dy: p.dy * k })
  };
}

function update(g, dt) {
  const P = S.P, inp = wIn(g.input);
  if (S.banner) { S.banner.t += dt; if (S.banner.t > 2.2) S.banner = null; }
  S.shown += (S.score - S.shown) * Math.min(1, dt * 8);
  if (S.mode === 'over' || S.mode === 'clear') { tickFx(dt); return; }

  // ракетка
  const ox = P.x;
  if (S.attract) {
    const free = S.balls.filter((b) => !b.stuck);
    const tgt = free.length ? free.reduce((a, b) => (b.y > a.y ? b : a)) : null;
    const tx = tgt ? tgt.x + Math.sin(g.t * 1.3) * P.w * .3 : W / 2 + Math.sin(g.t) * 120;
    P.x += (tx - P.x) * Math.min(1, dt * 7);
    if (!free.length && g.t % 1.5 < dt) launch(g);
  } else {
    const kx = (inp.down('right') ? 1 : 0) - (inp.down('left') ? 1 : 0);
    if (kx) { P.x += kx * 980 * dt; inp.mouseActive = false; }
    const ptr = inp.pointer;
    if (ptr.down && ptr.type !== 'mouse') P.x += ptr.dx * 1.35;
    else if (inp.mouseActive && !kx) P.x += (ptr.x - P.x) * Math.min(1, dt * 22);
    if (inp.pressed('action') || inp.pressed('up') || inp.tap || (ptr.justDown && ptr.type === 'mouse')) launch(g);
  }
  const targetW = P.wideT > 0 ? WIDE_W : BASE_W;
  P.w += (targetW - P.w) * Math.min(1, dt * 10);
  P.x = A.clamp(P.x, WALL + P.w / 2 + 4, W - WALL - P.w / 2 - 4);
  P.vx = (P.x - ox) / dt;
  if (P.wideT > 0) P.wideT -= dt;
  if (P.stickyT > 0) { P.stickyT -= dt; if (P.stickyT <= 0) launch(g); }
  if (S.slowT > 0) S.slowT -= dt;
  P.squash = Math.max(0, P.squash - dt * 5);
  P.happy = Math.max(0, P.happy - dt);
  P.sad = Math.max(0, P.sad - dt);

  // мячи
  const sp = baseSpeed();
  for (const b of S.balls) {
    if (b.stuck) { b.x = P.x + b.off; b.y = P.y - P.h / 2 - b.r - 1; b.trail.length = 0; continue; }
    const cur = Math.hypot(b.vx, b.vy) || 1, k = 1 + (sp / cur - 1) * Math.min(1, dt * 4);
    b.vx *= k; b.vy *= k;
    moveBall(g, b, dt);
    b.trail.unshift({ x: b.x, y: b.y }); if (b.trail.length > 9) b.trail.pop();
  }
  const before = S.balls.length;
  S.balls = S.balls.filter((b) => b.y < H + 40);
  if (before && !S.balls.length) {
    if (S.attract) newStuckBall();
    else {
      S.lives--; P.sad = 1.2; P.wideT = 0; P.stickyT = 0; S.slowT = 0; S.combo = 0; S.speedUp = 0;
      g.sfx('hurt'); g.shake(10, .3);
      if (S.lives <= 0) { gameOver(g); return; }
      newStuckBall();
      g.fx.text(W / 2, PADDLE_Y - 160, 'Ой! Осталось ' + S.lives, { color: '#ff5c85', size: 40 });
    }
  }
  // капсулы
  for (const c of S.caps) {
    c.y += c.vy * dt;
    if (!c.got && c.y + 18 >= P.y - P.h / 2 && c.y - 18 <= P.y + P.h / 2 && Math.abs(c.x - P.x) < P.w / 2 + 32) { c.got = true; power(g, c); }
  }
  S.caps = S.caps.filter((c) => !c.got && c.y < H + 40);
  for (const br of S.bricks) if (br.bump > 0) br.bump = Math.max(0, br.bump - dt * 6);
  if (!S.bricks.some((b) => !b.dead && !b.metal)) {
    if (S.attract) loadLevel(0);
    else levelClear(g);
  }
  tickFx(dt);
}
function tickFx() { /* эффекты обновляет каркас */ }
const CAP = {
  wide: { col: '#4dabf7', label: 'Шире!' },
  multi: { col: '#ff5c85', label: 'Мячики!' },
  slow: { col: '#20c997', label: 'Медленнее' },
  sticky: { col: '#94d82d', label: 'Липучка' },
  life: { col: '#ff6b6b', label: 'Жизнь +1' }
};
function power(g, c) {
  const P = S.P;
  if (c.type === 'wide') P.wideT = 15;
  else if (c.type === 'slow') S.slowT = 10;
  else if (c.type === 'sticky') P.stickyT = 15;
  else if (c.type === 'life') S.lives = Math.min(5, S.lives + 1);
  else if (c.type === 'multi') {
    launch(g);
    const add = [];
    for (const b of S.balls) {
      if (S.balls.length + add.length >= 8) break;
      const sp = Math.hypot(b.vx, b.vy) || baseSpeed(), a = Math.atan2(b.vy, b.vx);
      for (const d of [-.45, .45]) add.push({ x: b.x, y: b.y, vx: Math.cos(a + d) * sp, vy: Math.sin(a + d) * sp, r: BALL_R, stuck: false, off: 0, trail: [] });
    }
    add.forEach(ensureVertical);
    S.balls.push(...add);
  }
  if (!S.attract) {
    S.score += 100;
    g.sfx('power');
    g.fx.text(c.x, P.y - 70, CAP[c.type].label, { color: CAP[c.type].col, size: 34 });
  }
  g.fx.burst(c.x, P.y - 20, { n: 12, colors: ['#fff', CAP[c.type].col], speed: 260, size: 7, shape: 'star', life: .5 });
}

/* ---------------- отрисовка ---------------- */
function drawBrick(ctx, b) {
  const s = 1 + b.bump * .12;
  ctx.save(); ctx.translate(b.x + b.w / 2, b.y + b.h / 2); ctx.scale(s, s);
  const x = -b.w / 2, y = -b.h / 2, w = b.w, h = b.h;
  let [c1, c2] = b.col;
  if (!b.metal && !b.choc && b.max === 2 && b.hp === 2) { c1 = c2; }
  const gr = ctx.createLinearGradient(0, y, 0, y + h);
  gr.addColorStop(0, c1); gr.addColorStop(1, c2);
  A.rr(ctx, x, y, w, h, 10); ctx.fillStyle = gr; ctx.fill();
  ctx.save(); A.rr(ctx, x, y, w, h, 10); ctx.clip();
  if (b.choc) {
    ctx.strokeStyle = 'rgba(70,40,25,.45)'; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(x + w / 3, y); ctx.lineTo(x + w / 3, y + h); ctx.moveTo(x + w * 2 / 3, y); ctx.lineTo(x + w * 2 / 3, y + h); ctx.moveTo(x, 0); ctx.lineTo(x + w, 0); ctx.stroke();
  }
  if (b.metal) {
    ctx.fillStyle = 'rgba(255,255,255,.55)';
    const sx = ((S ? performance.now() / 12 : 0) + b.seed) % 260 - 80;
    ctx.beginPath(); ctx.moveTo(x + sx, y); ctx.lineTo(x + sx + 14, y); ctx.lineTo(x + sx - 6, y + h); ctx.lineTo(x + sx - 20, y + h); ctx.closePath(); ctx.fill();
    ctx.fillStyle = '#6c757d';
    for (const [rx, ry] of [[x + 7, y + 7], [x + w - 7, y + 7], [x + 7, y + h - 7], [x + w - 7, y + h - 7]]) { ctx.beginPath(); ctx.arc(rx, ry, 2.6, 0, Math.PI * 2); ctx.fill(); }
  }
  ctx.fillStyle = 'rgba(255,255,255,.6)'; A.rr(ctx, x + 7, y + 4, w - 14, 7, 3.5); ctx.fill();
  ctx.fillStyle = 'rgba(0,0,0,.08)'; ctx.fillRect(x, y + h - 7, w, 7);
  if (b.hp < b.max) {
    ctx.strokeStyle = 'rgba(43,37,80,.65)'; ctx.lineWidth = 2.2; ctx.lineJoin = 'round';
    const r = (k) => ((Math.sin(b.seed * (k + 1) * 12.9898) * 43758.5453) % 1 + 1) % 1;
    const cracks = (b.max - b.hp) * 2;
    for (let i = 0; i < cracks; i++) {
      let px = x + w * (.2 + r(i) * .6), py = y + (i % 2 ? h : 0);
      ctx.beginPath(); ctx.moveTo(px, py);
      for (let j = 0; j < 3; j++) { px += (r(i * 7 + j) - .5) * 18; py += (i % 2 ? -1 : 1) * h * .3; ctx.lineTo(px, py); }
      ctx.stroke();
    }
  }
  ctx.restore();
  A.rr(ctx, x, y, w, h, 10); ctx.lineWidth = 3.5; ctx.strokeStyle = OUT; ctx.stroke();
  ctx.restore();
}
function drawPaddle(ctx, g) {
  const P = S.P, t = g.t;
  const sq = A.ease.outCubic(P.squash) * .22;
  ctx.save(); ctx.translate(P.x, P.y + sq * 8); ctx.scale(1 + sq * .5, 1 - sq);
  const w = P.w, h = P.h, x = -w / 2, y = -h / 2;
  ctx.globalAlpha = .18; ctx.fillStyle = OUT; A.rr(ctx, x + 6, y + 14, w, h, h / 2); ctx.fill(); ctx.globalAlpha = 1;
  const gr = ctx.createLinearGradient(0, y, 0, y + h);
  gr.addColorStop(0, '#a99bff'); gr.addColorStop(1, '#6a4fe0');
  A.rr(ctx, x, y, w, h, h / 2); ctx.fillStyle = gr; ctx.fill();
  ctx.save(); A.rr(ctx, x, y, w, h, h / 2); ctx.clip();
  ctx.fillStyle = '#ff8fb1'; ctx.fillRect(x, y, 26, h); ctx.fillRect(x + w - 26, y, 26, h);
  ctx.fillStyle = 'rgba(255,255,255,.5)'; A.rr(ctx, x + 18, y + 4, w - 36, 7, 3.5); ctx.fill();
  if (P.stickyT > 0) {
    ctx.fillStyle = '#a9e34b';
    ctx.fillRect(x, y, w, 7);
    for (let i = 0; i < 6; i++) { const dx = x + 20 + i * (w - 40) / 5, dl = 6 + Math.sin(t * 3 + i) * 3; ctx.beginPath(); ctx.ellipse(dx, y + 7, 4, dl, 0, 0, Math.PI * 2); ctx.fill(); }
  }
  ctx.restore();
  A.rr(ctx, x, y, w, h, h / 2); ctx.lineWidth = 4; ctx.strokeStyle = OUT; ctx.stroke();
  // мордочка
  const ball = S.balls.length ? S.balls.reduce((a, b) => (b.y > a.y ? b : a)) : null;
  const look = ball ? A.clamp((ball.x - P.x) / 200, -1, 1) * 3.5 : 0;
  ctx.lineWidth = 3; ctx.lineCap = 'round'; ctx.strokeStyle = OUT; ctx.fillStyle = OUT;
  for (const ex of [-14, 14]) {
    if (P.happy > 0) { ctx.beginPath(); ctx.arc(ex, 2, 5, Math.PI * 1.1, Math.PI * 1.9); ctx.stroke(); }
    else {
      ctx.beginPath(); ctx.ellipse(ex, -1, 5.5, 6.5, 0, 0, Math.PI * 2); ctx.fillStyle = '#fff'; ctx.fill();
      ctx.beginPath(); ctx.arc(ex + look, 0, 3, 0, Math.PI * 2); ctx.fillStyle = OUT; ctx.fill();
    }
  }
  ctx.beginPath();
  if (P.sad > 0) ctx.arc(0, 14, 6, Math.PI * 1.2, Math.PI * 1.8);
  else ctx.arc(0, 4, P.happy > 0 ? 7 : 5, Math.PI * .15, Math.PI * .85);
  ctx.stroke();
  ctx.fillStyle = 'rgba(255,120,160,.55)'; ctx.beginPath(); ctx.arc(-26, 6, 4, 0, Math.PI * 2); ctx.arc(26, 6, 4, 0, Math.PI * 2); ctx.fill();
  ctx.restore();
}
function drawBall(ctx, b) {
  for (let i = b.trail.length - 1; i >= 1; i--) {
    const p = b.trail[i], k = 1 - i / b.trail.length;
    ctx.globalAlpha = k * .35; ctx.beginPath(); ctx.arc(p.x, p.y, b.r * (.4 + .6 * k), 0, Math.PI * 2); ctx.fillStyle = '#ff8fb1'; ctx.fill();
  }
  ctx.globalAlpha = 1;
  const gr = ctx.createRadialGradient(b.x - 5, b.y - 5, 2, b.x, b.y, b.r);
  gr.addColorStop(0, '#ffffff'); gr.addColorStop(.6, '#ffe3ee'); gr.addColorStop(1, '#ffb3cc');
  ctx.beginPath(); ctx.arc(b.x, b.y, b.r, 0, Math.PI * 2); ctx.fillStyle = gr; ctx.fill(); ctx.lineWidth = 3.5; ctx.strokeStyle = OUT; ctx.stroke();
  ctx.beginPath(); ctx.ellipse(b.x - 4, b.y - 5, 3.5, 2.4, -.6, 0, Math.PI * 2); ctx.fillStyle = '#fff'; ctx.fill();
}
function drawCap(ctx, c, t) {
  const info = CAP[c.type];
  ctx.save(); ctx.translate(c.x, c.y); ctx.rotate(Math.sin(t * 4 + c.ph) * .12);
  ctx.globalAlpha = .3; ctx.beginPath(); ctx.arc(0, 0, 30 + Math.sin(t * 8) * 3, 0, Math.PI * 2); ctx.fillStyle = info.col; ctx.fill(); ctx.globalAlpha = 1;
  A.rr(ctx, -36, -19, 72, 38, 19);
  const gr = ctx.createLinearGradient(0, -19, 0, 19); gr.addColorStop(0, '#fff'); gr.addColorStop(.35, info.col); gr.addColorStop(1, info.col);
  ctx.fillStyle = gr; ctx.fill(); ctx.lineWidth = 3.5; ctx.strokeStyle = OUT; ctx.stroke();
  ctx.fillStyle = '#fff'; ctx.strokeStyle = '#fff'; ctx.lineWidth = 4; ctx.lineCap = 'round'; ctx.lineJoin = 'round';
  if (c.type === 'wide') {
    ctx.beginPath(); ctx.moveTo(-18, 0); ctx.lineTo(18, 0); ctx.moveTo(-11, -7); ctx.lineTo(-18, 0); ctx.lineTo(-11, 7); ctx.moveTo(11, -7); ctx.lineTo(18, 0); ctx.lineTo(11, 7); ctx.stroke();
  } else if (c.type === 'multi') {
    for (const dx of [-13, 0, 13]) { ctx.beginPath(); ctx.arc(dx, 0, 5.5, 0, Math.PI * 2); ctx.fill(); }
  } else if (c.type === 'slow') {
    ctx.lineWidth = 3; ctx.beginPath(); ctx.arc(0, 0, 11, 0, Math.PI * 2); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(0, -7); ctx.moveTo(0, 0); ctx.lineTo(5, 3); ctx.stroke();
  } else if (c.type === 'sticky') {
    ctx.beginPath(); ctx.moveTo(0, -12); ctx.bezierCurveTo(10, 0, 9, 11, 0, 11); ctx.bezierCurveTo(-9, 11, -10, 0, 0, -12); ctx.fill();
  } else if (c.type === 'life') {
    A.heart(ctx, 0, 3, 30, '#fff', null);
  }
  ctx.restore();
}
function drawHud(ctx, g) {
  if (LAND) return;                                       // в широком окне — на боковых панелях
  A.text(ctx, Math.round(S.shown).toLocaleString('ru-RU'), 26, 56, { align: 'left', size: 46, color: '#fff', stroke: OUT, strokeW: 9 });
  A.text(ctx, 'Уровень ' + (S.level + 1), W / 2, 56, { size: 28, color: '#fff', stroke: OUT, strokeW: 7, weight: 700 });
  for (let i = 0; i < Math.max(3, S.lives); i++) A.heart(ctx, W - 40 - i * 46, 58, 40, i < S.lives ? '#ff4f7b' : 'rgba(43,37,80,.25)', OUT);
  // таймеры бонусов
  const act = [];
  if (S.P.wideT > 0) act.push(['wide', S.P.wideT / 15]);
  if (S.P.stickyT > 0) act.push(['sticky', S.P.stickyT / 15]);
  if (S.slowT > 0) act.push(['slow', S.slowT / 10]);
  act.forEach(([type, k], i) => {
    const x = 40 + i * 54, y = 104;
    ctx.beginPath(); ctx.arc(x, y, 18, 0, Math.PI * 2); ctx.fillStyle = 'rgba(255,255,255,.7)'; ctx.fill();
    ctx.beginPath(); ctx.moveTo(x, y); ctx.arc(x, y, 18, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * k); ctx.closePath(); ctx.fillStyle = CAP[type].col; ctx.fill();
    ctx.beginPath(); ctx.arc(x, y, 18, 0, Math.PI * 2); ctx.lineWidth = 3; ctx.strokeStyle = OUT; ctx.stroke();
  });
}

function drawWorld(ctx, g) {
  const t = g.t;
  drawBackground(ctx, t);
  drawRails(ctx);
  for (const b of S.bricks) if (!b.dead) drawBrick(ctx, b);
  for (const c of S.caps) drawCap(ctx, c, t);
  drawPaddle(ctx, g);
  for (const b of S.balls) drawBall(ctx, b);
  if (!S.attract) {
    drawHud(ctx, g);
    if (S.mode === 'play' && S.balls.some((b) => b.stuck) && !g.paused) {
      ctx.globalAlpha = .6 + Math.sin(t * 5) * .4;
      A.text(ctx, A.isTouch ? 'Коснитесь, чтобы запустить' : 'Пробел или клик — запустить', W / 2, PADDLE_Y - 120, LAND ? { size: 38, color: '#fff', stroke: OUT, strokeW: 9, weight: 700 } : { size: 30, color: '#fff', stroke: OUT, strokeW: 7, weight: 700 });
      ctx.globalAlpha = 1;
    }
  }
  if (S.banner) {
    const bt = S.banner.t, k = bt < .35 ? A.ease.outBack(bt / .35) : 1, a = bt > 1.8 ? 1 - (bt - 1.8) / .4 : 1;
    ctx.save(); ctx.globalAlpha = Math.max(0, a); ctx.translate(W / 2, H * .62); ctx.scale(k, k);
    A.text(ctx, S.banner.text, 0, 0, { size: 76, color: '#fff', stroke: OUT, strokeW: 13, weight: 900 });
    if (S.banner.sub) A.text(ctx, S.banner.sub, 0, 64, { size: 34, color: '#ffe066', stroke: OUT, strokeW: 9 });
    ctx.restore();
  }
}
/* ---------------- широкое окно ---------------- */
const LBG = LAND ? {                                      // фон по сторонам поля — свои пузыри и посыпка
  bubbles: Array.from({ length: 16 }, () => ({ x: A.rand(0, SW), y: A.rand(0, SH), r: A.rand(24, 70), sp: A.rand(8, 20), ph: A.rand(0, 6) })),
  sprinkles: Array.from({ length: 46 }, () => ({ x: A.rand(0, SW), y: A.rand(0, SH), rot: A.rand(0, 6), vr: A.rand(-.6, .6), sp: A.rand(10, 26), col: A.pick(['#ff8fb1', '#ffd43b', '#74c0fc', '#8ce99a', '#b197fc', '#ffa94d']) }))
} : null;
const LABEL = { size: 23, weight: 700, color: 'rgba(43,37,80,.6)' };
function plate(ctx, x, y, w, h) {                        // сахарная плашка под надписями
  ctx.save(); ctx.globalAlpha = .1; ctx.fillStyle = OUT; A.rr(ctx, x + 3, y + 7, w, h, 28); ctx.fill(); ctx.restore();
  A.rr(ctx, x, y, w, h, 28); ctx.fillStyle = 'rgba(255,255,255,.66)'; ctx.fill();
  ctx.lineWidth = 3; ctx.strokeStyle = '#fff'; ctx.stroke();
}
function fitText(ctx, str, x, y, o, maxW) {               // крупное число, которое не вылезет за плашку
  ctx.font = `${o.weight || 800} ${o.size}px ${A.FONT}`;
  const w = ctx.measureText(str).width, k = w > maxW ? maxW / w : 1;
  A.text(ctx, str, x, y, Object.assign({}, o, { size: o.size * k, strokeW: (o.strokeW || 9) * Math.max(.7, k) }));
}
function keycap(ctx, x, y, label) {
  const s = 44;
  A.rr(ctx, x - s / 2, y - s / 2 + 5, s, s, 12); ctx.fillStyle = 'rgba(43,37,80,.22)'; ctx.fill();
  A.rr(ctx, x - s / 2, y - s / 2, s, s, 12); ctx.fillStyle = '#fff'; ctx.fill(); ctx.lineWidth = 3; ctx.strokeStyle = OUT; ctx.stroke();
  A.text(ctx, label, x, y + 1, { size: 23, weight: 800, color: OUT });
}
function drawCandy(ctx, x, y, t) {                        // конфетка-болельщица в фантике: смотрит на мячик
  const ball = S.balls.length ? S.balls.reduce((a, b) => (b.y > a.y ? b : a)) : null;
  const look = ball ? A.clamp((FX + ball.x * FS - x) / 300, -1, 1) * 4 : 0;
  ctx.save(); ctx.translate(x, y); ctx.rotate(Math.sin(t * 1.3) * .06);
  ctx.lineJoin = 'round'; ctx.strokeStyle = OUT; ctx.lineWidth = 4;
  for (const sx of [-1, 1]) {                             // хвостики фантика
    ctx.beginPath(); ctx.moveTo(sx * 46, 0); ctx.lineTo(sx * 84, -28 + Math.sin(t * 3) * 3); ctx.quadraticCurveTo(sx * 74, 0, sx * 84, 28 - Math.sin(t * 3) * 3); ctx.closePath();
    ctx.fillStyle = '#ffd6ec'; ctx.fill(); ctx.stroke();
  }
  const gr = ctx.createLinearGradient(0, -40, 0, 40); gr.addColorStop(0, '#ffa3b8'); gr.addColorStop(1, '#ff5c85');
  ctx.beginPath(); ctx.ellipse(0, 0, 56, 42, 0, 0, Math.PI * 2); ctx.fillStyle = gr; ctx.fill();
  ctx.save(); ctx.clip(); ctx.fillStyle = 'rgba(255,255,255,.45)';
  for (let k = -3; k <= 3; k++) { ctx.beginPath(); ctx.moveTo(k * 26 - 8, -44); ctx.lineTo(k * 26 + 4, -44); ctx.lineTo(k * 26 + 26, 44); ctx.lineTo(k * 26 + 14, 44); ctx.closePath(); ctx.fill(); }
  ctx.fillStyle = 'rgba(255,255,255,.6)'; ctx.beginPath(); ctx.ellipse(-18, -24, 20, 7, -.2, 0, Math.PI * 2); ctx.fill();
  ctx.restore();
  ctx.beginPath(); ctx.ellipse(0, 0, 56, 42, 0, 0, Math.PI * 2); ctx.stroke();
  const blink = (t % 3.4) > 3.25;
  for (const ex of [-16, 16]) {
    if (blink) { ctx.beginPath(); ctx.moveTo(ex - 6, 0); ctx.lineTo(ex + 6, 0); ctx.lineWidth = 3; ctx.stroke(); continue; }
    ctx.beginPath(); ctx.ellipse(ex, -2, 7, 8.5, 0, 0, Math.PI * 2); ctx.fillStyle = '#fff'; ctx.fill(); ctx.lineWidth = 2.5; ctx.stroke();
    ctx.beginPath(); ctx.arc(ex + look, 0, 4, 0, Math.PI * 2); ctx.fillStyle = OUT; ctx.fill();
  }
  ctx.fillStyle = 'rgba(255,255,255,.55)'; ctx.beginPath(); ctx.arc(-32, 12, 6, 0, Math.PI * 2); ctx.arc(32, 12, 6, 0, Math.PI * 2); ctx.fill();
  ctx.beginPath(); ctx.arc(0, 12, 8, .15 * Math.PI, .85 * Math.PI); ctx.lineWidth = 3.5; ctx.lineCap = 'round'; ctx.stroke();
  ctx.restore();
}
function drawLand(ctx, g) {
  const t = g.t;
  // конфетный фон во всю ширину
  const gr = ctx.createLinearGradient(0, 0, 0, SH);
  gr.addColorStop(0, '#ffd6ec'); gr.addColorStop(.5, '#e7ddff'); gr.addColorStop(1, '#cfeaff');
  ctx.fillStyle = gr; ctx.fillRect(0, 0, SW, SH);
  for (const b of LBG.bubbles) {
    const y = ((b.y - t * b.sp) % (SH + 160) + SH + 160) % (SH + 160) - 80, x = b.x + Math.sin(t * .5 + b.ph) * 14;
    const rg = ctx.createRadialGradient(x - b.r * .3, y - b.r * .3, 2, x, y, b.r);
    rg.addColorStop(0, 'rgba(255,255,255,.55)'); rg.addColorStop(.7, 'rgba(255,255,255,.12)'); rg.addColorStop(1, 'rgba(255,255,255,0)');
    ctx.fillStyle = rg; ctx.beginPath(); ctx.arc(x, y, b.r, 0, Math.PI * 2); ctx.fill();
  }
  ctx.globalAlpha = .5;
  for (const s of LBG.sprinkles) {
    const y = ((s.y - t * s.sp) % (SH + 30) + SH + 30) % (SH + 30) - 15;
    ctx.save(); ctx.translate(s.x, y); ctx.rotate(s.rot + t * s.vr);
    A.rr(ctx, -6, -2, 12, 4, 2); ctx.fillStyle = s.col; ctx.fill(); ctx.restore();
  }
  ctx.globalAlpha = 1;
  // поле: мир между бортиками, во всю высоту; мягкая тень вокруг
  for (const [x0, dir] of [[FX, -1], [FX + FW, 1]]) {
    const sh = ctx.createLinearGradient(x0, 0, x0 + dir * 22, 0);
    sh.addColorStop(0, 'rgba(43,37,80,.16)'); sh.addColorStop(1, 'rgba(43,37,80,0)');
    ctx.fillStyle = sh; ctx.fillRect(Math.min(x0, x0 + dir * 22), 0, 22, SH);
  }
  ctx.save(); ctx.beginPath(); ctx.rect(FX, 0, FW, SH); ctx.clip();
  ctx.translate(FX, FY); ctx.scale(FS, FS);
  drawWorld(ctx, g);
  if (g.fxWorld) g.fxWorld(ctx);
  ctx.restore();
  const playing = !S.attract;
  // слева: очки, уровень, жизни, бонусы
  const lx = LCX, lp = lx - PW / 2;
  plate(ctx, lp, 26, PW, 498);
  A.text(ctx, 'Очки', lx, 62, LABEL);
  fitText(ctx, Math.round(S.shown).toLocaleString('ru-RU'), lx, 114, { size: 62, color: '#fff', stroke: OUT, strokeW: 12, weight: 900 }, PW - 30);
  A.text(ctx, 'Уровень ' + (S.level + 1), lx, 174, { size: 30, color: '#fff', stroke: OUT, strokeW: 8, weight: 800 });
  A.text(ctx, LEVELS[S.level % LEVELS.length].name, lx, 208, { size: 22, weight: 700, color: '#e64980' });
  A.text(ctx, 'Жизни', lx, 262, LABEL);
  const n = Math.max(3, S.lives), hs = Math.min(56, 160 / (n - 1));
  for (let i = 0; i < n; i++) A.heart(ctx, lx + (i - (n - 1) / 2) * hs, 306, n > 3 ? 38 : 50, i < S.lives ? '#ff4f7b' : 'rgba(43,37,80,.25)', OUT);
  ctx.fillStyle = 'rgba(43,37,80,.12)'; ctx.fillRect(lx - 70, 346, 140, 2);
  A.text(ctx, 'Бонусы', lx, 374, LABEL);
  const act = [];
  if (playing && S.P.wideT > 0) act.push(['wide', S.P.wideT / 15]);
  if (playing && S.P.stickyT > 0) act.push(['sticky', S.P.stickyT / 15]);
  if (playing && S.slowT > 0) act.push(['slow', S.slowT / 10]);
  if (!act.length) A.text(ctx, 'ловите капсулы', lx, 414, { size: 20, weight: 600, color: 'rgba(43,37,80,.5)' });
  act.forEach(([type, k], i) => {
    const x = lp + 40, y = 414 + i * 38;
    ctx.beginPath(); ctx.arc(x, y, 15, 0, Math.PI * 2); ctx.fillStyle = 'rgba(255,255,255,.9)'; ctx.fill();
    ctx.beginPath(); ctx.moveTo(x, y); ctx.arc(x, y, 15, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * k); ctx.closePath(); ctx.fillStyle = CAP[type].col; ctx.fill();
    ctx.beginPath(); ctx.arc(x, y, 15, 0, Math.PI * 2); ctx.lineWidth = 3; ctx.strokeStyle = OUT; ctx.stroke();
    A.text(ctx, CAP[type].label, x + 28, y + 1, { align: 'left', size: 21, weight: 700, color: OUT });
  });
  drawCandy(ctx, lx, 624 + Math.sin(t * 1.7) * 6, t);
  // справа: рекорд, капсулы, управление
  const rx = RCX, rp = rx - PW / 2;
  plate(ctx, rp, 26, PW, 136);
  A.text(ctx, 'Рекорд', rx, 64, LABEL);
  fitText(ctx, (g.best || 0).toLocaleString('ru-RU'), rx, 112, { size: 46, color: '#fff', stroke: OUT, strokeW: 10, weight: 900 }, PW - 30);
  plate(ctx, rp, 180, PW, 300);
  A.text(ctx, 'Капсулы', rx, 216, LABEL);
  ['wide', 'multi', 'slow', 'sticky', 'life'].forEach((type, i) => {
    const y = 258 + i * 46;
    ctx.save(); ctx.translate(rp + 50, y); ctx.scale(.62, .62); drawCap(ctx, { type, x: 0, y: 0, ph: i }, t); ctx.restore();
    A.text(ctx, CAP[type].label, rp + 84, y + 1, { align: 'left', size: 21, weight: 700, color: OUT });
  });
  plate(ctx, rp, 498, PW, 196);
  A.text(ctx, 'Ракетка', rx, 532, LABEL);
  if (A.isTouch) {
    A.text(ctx, 'ведите пальцем', rx, 570, { size: 22, weight: 800, color: OUT });
    A.text(ctx, 'Запуск', rx, 622, LABEL);
    A.text(ctx, 'касание', rx, 658, { size: 22, weight: 800, color: OUT });
  } else {
    keycap(ctx, rp + 44, 574, '←'); keycap(ctx, rp + 94, 574, '→');
    A.text(ctx, 'мышь', rp + 128, 575, { align: 'left', size: 22, weight: 800, color: OUT });
    A.text(ctx, 'Запуск', rx, 626, LABEL);
    A.text(ctx, 'пробел или клик', rx, 660, { size: 21, weight: 800, color: OUT });
  }
}
function draw(ctx, g) {
  if (LAND) drawLand(ctx, g); else drawWorld(ctx, g);
}

A.game({
  id: 'bricks', tone: 'light', title: 'Кирпичики', width: SW, height: SH, orientation: LAND ? 'landscape' : 'portrait', music: 'candy',
  help: {
    desktop: 'Мышь или <kbd>←</kbd> <kbd>→</kbd> — ракетка · <kbd>Пробел</kbd> или клик — запуск · <kbd>P</kbd> пауза · <kbd>M</kbd> музыка',
    short: '<b>Мышь</b> или <b>стрелки</b> — ракетка, <b>Пробел</b> — запуск',
    touch: 'Ведите пальцем по экрану — ракетка поедет следом. Коснитесь, чтобы запустить мячик'
  },
  init(g) {
    if (LAND) {                                           // эффекты — в координатах мира: рисуем их внутри поля, надписи крупнее
      const fxDraw = g.fx.draw.bind(g.fx), fxText = g.fx.text.bind(g.fx);
      g.fx.draw = () => {}; g.fxWorld = fxDraw;
      g.fx.text = (x, y, str, o = {}) => fxText(x, y, str, Object.assign({}, o, { size: (o.size || 34) * 1.3, rise: (o.rise || 70) * 1.2 }));
    }
    titleScreen(g);
  },
  update, draw
});

window.__bricks = {
  get S() { return S; },
  clear() { S.bricks.forEach((b) => { if (!b.metal) b.dead = true; }); },
  drop(type) { S.caps.push({ x: S.P.x, y: S.P.y - 200, type, vy: 250, ph: 0 }); },
  loseBall() { S.balls.forEach((b) => { b.stuck = false; b.y = H + 100; }); }
};
})();
