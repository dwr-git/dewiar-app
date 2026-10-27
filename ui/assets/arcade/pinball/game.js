/* Звёздный пинбол (27.10, владелец: «рычажки справа и слева внизу, отбиваем шарик, а он выбивает разные очки… может
   быть попробуем и такую красоту возродить»). Ночной стол: три планеты-отбойника, звёзды-мишени, кометы, «Чёрная
   дыра», три верхние дорожки и созвездие Лиры посередине — пять его звёзд зажигаются заданиями; все пять — звездопад
   (ещё два мячика). Физика своя: 10 подшагов на кадр, шарик — круг, стенки — отрезки, флипперы — вращающиеся
   «капсулы» (скорость поверхности передаётся шарику). Широкое окно (лист «Досуг» на компьютере) — стол посередине,
   слева правила и рекорд, справа табло и задания; узкое (телефон) — стол во весь экран, табло сверху. */
(() => {
'use strict';
const A = Arcade;
const LAND = (() => { try { return innerWidth > (innerHeight - 110) * 1.15; } catch (e) { return false; } })();
const W = 720, H = 1280;                                  // стол — всегда книжный
const SW = LAND ? 1280 : 720, SH = LAND ? 720 : 1400;     // холст
const TS = LAND ? SH / H : 1, TX = LAND ? (SW - W * TS) / 2 : 0, TY = LAND ? 0 : 120;
const R = 14, G = 2050, VMAX = 3200, SUB = 10;
const C = { ink: '#f4efff', dim: '#9d93c9', mute: '#6c6396', gold: '#ffd166', pink: '#ff6fd0', cyan: '#6fe6ff', mint: '#63f2c4', violet: '#a98bff', deep: '#0c0726' };
const fmt = (n) => Math.round(n).toLocaleString('ru-RU');

/* ---------------- стол ---------------- */
const walls = [];
const seg = (ax, ay, bx, by, o) => walls.push(Object.assign({ ax, ay, bx, by, e: .42, rad: 0 }, o || {}));
const AC = { x: 360, y: 330, r: 330 };
const arcPts = [];
for (let i = 0; i <= 56; i++) { const a = -i / 56 * Math.PI; arcPts.push([AC.x + Math.cos(a) * AC.r, AC.y + Math.sin(a) * AC.r]); }
for (let i = 0; i < arcPts.length - 1; i++) seg(arcPts[i][0], arcPts[i][1], arcPts[i + 1][0], arcPts[i + 1][1], { e: .22, rail: 1 });
seg(690, 330, 690, 1320, { rail: 1 }); seg(30, 330, 30, 1320, { rail: 1 });
seg(640, 470, 640, 1320, { rail: 1 });                     // стенка канала запуска
{ const l = Math.hypot(50, 34); seg(690, 418, 640, 452, { one: { x: -34 / l, y: -50 / l }, gate: 1, e: .3 }); }   // калитка: вверх пропускает, назад — нет
seg(640, 1238, 690, 1238, { e: .05, plunger: 1 });
// низ: разделители дорожек, полы дорожек к флипперам
seg(100, 880, 100, 1320, { post: 1 }); seg(100, 1020, 218, 1079, { guide: 1 });   // пол кончается на макушке оси флиппера — без ямки, где шарик застревал
seg(570, 880, 570, 1320, { post: 1 }); seg(570, 1020, 452, 1079, { guide: 1 });
// рогатки: левая и правая (кикер — гипотенуза к центру)
const SLINGS = [{ a: [145, 880], b: [145, 1000], c: [205, 1035] }, { a: [525, 880], b: [525, 1000], c: [465, 1035] }];
SLINGS.forEach((s, i) => {
  seg(s.a[0], s.a[1], s.b[0], s.b[1], { e: .4, slingSide: 1 }); seg(s.b[0], s.b[1], s.c[0], s.c[1], { e: .4, slingSide: 1 });
  seg(s.a[0], s.a[1], s.c[0], s.c[1], { e: .5, sling: i });
});
// карманы мишеней: звёзды-мишени слева (опускаются), кометы справа (стоят)
seg(30, 520, 56, 550, { rail: 1 }); seg(56, 750, 30, 780, { rail: 1 });
seg(640, 520, 606, 552, { rail: 1 }); seg(606, 704, 640, 736, { rail: 1 });
const DROPS = [[558, 598], [606, 646], [654, 694], [702, 742]];
DROPS.forEach((y, i) => seg(56, y[0], 56, y[1], { drop: i, e: .3 }));
const STANDS = [[558, 598], [606, 646], [654, 694]];
STANDS.forEach((y, i) => seg(606, y[0], 606, y[1], { stand: i, e: .35 }));
// верхние дорожки
const LANE_X = [215, 295, 375, 455], LANE_C = [255, 335, 415], LANE_Y = 252;
LANE_X.forEach((x) => seg(x, 222, x, 290, { rad: 4, e: .3, lanePost: 1 }));
const BUMPERS = [{ x: 268, y: 440, r: 34, c: ['#ffb3ea', '#ff5cc8', '#6e1a63'] }, { x: 412, y: 440, r: 34, c: ['#b5f7ff', '#3fd2f2', '#0f4a6b'] },
  { x: 340, y: 556, r: 34, c: ['#ffe9a8', '#ffbf3c', '#7a4710'] }];
const HOLE = { x: 128, y: 452 };
const FLIP = [
  { px: 222, py: 1098, len: 100, r0: 17, r1: 9, side: 1, rest: .52, up: -.46, a: .52, w: 0 },
  { px: 448, py: 1098, len: 100, r0: 17, r1: 9, side: -1, rest: .52, up: -.46, a: .52, w: 0 }
];
// созвездие Лиры: Вега, ε (только рисунок), ζ, δ, γ (Сулафат), β (Шелиак)
const LYRA = { vega: [300, 690], eps: [348, 668], zeta: [318, 760], delta: [372, 784], gamma: [356, 876], beta: [300, 852] };
const LYRA_LINES = [['vega', 'eps'], ['vega', 'zeta'], ['zeta', 'delta'], ['delta', 'gamma'], ['gamma', 'beta'], ['beta', 'zeta']];
const STARS = [
  { k: 'vega', name: 'Вега', task: 'три верхние дорожки' },
  { k: 'zeta', name: 'Дзета', task: 'четыре звезды-мишени слева' },
  { k: 'delta', name: 'Дельта', task: 'три кометы справа' },
  { k: 'gamma', name: 'Сулафат', task: '«Чёрная дыра»' },
  { k: 'beta', name: 'Шелиак', task: '25 ударов по планетам' }
];

/* ---------------- состояние ---------------- */
let S = null, g0 = null;
function fresh() {
  return { mode: 'title', t: 0, score: 0, ball: 1, extra: 0, balls: [], lanes: [0, 0, 0], X: 1, drops: [0, 0, 0, 0], dropT: 0, stands: [0, 0, 0], standT: 0,
    bumps: 0, stars: [0, 0, 0, 0, 0], level: 1, kick: false, save: 0, saveArm: true, charge: 0, bonus: 0, msg: null, skill: -1, skillT: 0,
    fl: { b: [0, 0, 0], s: [0, 0], d: [0, 0, 0, 0], st: [0, 0, 0], lane: [0, 0, 0], hole: 0, kick: 0, star: [0, 0, 0, 0, 0] },
    waitT: 0, firstConst: true, nudgeT: 0, wasL: false, wasR: false, plungeHeld: false };
}
const newBall = () => ({ x: 665, y: 1238 - R, vx: 0, vy: 0, ready: true, lock: 0, noHole: 0, still: 0, trail: [] });

/* ---------------- ввод: клавиши, мышь, касания (оба флиппера сразу) ---------------- */
const touch = new Map();          // pointerId -> 'L' | 'R'
let mouseL = false, mouseR = false;
function bindPointers(g) {
  const cv = g.canvas;
  cv.addEventListener('pointerdown', (e) => {
    if (e.pointerType === 'mouse') { if (e.button === 2) mouseR = true; else mouseL = true; return; }
    const r = cv.getBoundingClientRect();
    touch.set(e.pointerId, e.clientX - r.left < r.width / 2 ? 'L' : 'R');
  });
  const up = (e) => {
    if (e.pointerType === 'mouse') { if (e.button === 2) mouseR = false; else mouseL = false; if (!e.buttons) { mouseL = mouseR = false; } return; }
    touch.delete(e.pointerId);
  };
  cv.addEventListener('pointerup', up); cv.addEventListener('pointercancel', up); cv.addEventListener('lostpointercapture', up);
  addEventListener('blur', () => { touch.clear(); mouseL = mouseR = false; });
}
const anyTouch = () => touch.size > 0;
const leftHeld = (g) => g.input.down('left') || mouseL || [...touch.values()].includes('L');
const rightHeld = (g) => g.input.down('right') || mouseR || [...touch.values()].includes('R');
const plungeHeld = (g) => g.input.down('action') || g.input.down('down') || mouseL || mouseR || anyTouch();

/* ---------------- игра ---------------- */
function titleScreen(g) {
  S = fresh();
  g.setPlaying(false);
  const list = STARS.map((s) => `<li><b>${s.name}</b> — ${s.task}</li>`).join('');
  g.screen({
    kicker: A.framed ? 'Досуг' : 'Аркада', title: 'Звёздный пинбол',
    html: `<p>Отбивайте шарик флипперами и зажигайте звёзды созвездия Лиры. Все пять — звездопад: на поле выйдут ещё два шарика.</p>
      <ul class="pb-stars">${list}</ul>${g.best ? `<p class="record">Рекорд: ${fmt(g.best)}</p>` : ''}`,
    button: 'Играть', onGo: () => startGame(g)
  });
}
function startGame(g) {
  S = fresh(); S.mode = 'play'; S.balls = [newBall()];
  g.setPlaying(true); g.playMusic(); g.fx.clear();
  say('Шарик 1', A.isTouch ? 'Держите палец — пружина сжимается' : 'Держите пробел — пружина сжимается');
  if (A.isTouch) g.tip('Левая половина экрана — левый флиппер, правая — правый', 4200);
}
function gameOver(g) {
  S.mode = 'over'; g.setPlaying(false); g.stopMusic(); g.sfx('lose');
  const rec = g.submit(S.score), lit = S.stars.filter(Boolean).length;
  g.screen({
    kicker: 'Шарики закончились', title: 'Игра окончена',
    html: `<div class="score">${fmt(S.score)}</div><p>${rec ? '<span class="record">Новый рекорд!</span>' : `Рекорд: ${fmt(g.best)}`}${S.level > 1 ? ` · созвездий: ${S.level - 1}` : lit ? ` · звёзд: ${lit} из 5` : ''}</p>`,
    button: 'Ещё раз', onGo: () => startGame(g),
    alt: { label: A.framed ? 'К играм' : 'В аркаду', onGo: () => A.home('../index.html') }
  });
}
function say(t, s) { S.msg = { t, s: s || '', life: 3.2 }; }
function add(g, pts, x, y, color) {
  pts = Math.round(pts * S.level);
  S.score += pts;
  if (x != null && pts >= 250) g.fx.text(x, y, '+' + fmt(pts), { color: color || C.gold, size: pts >= 5000 ? 40 : 28, life: .9, rise: 60 });
}

function star(g, i) {
  if (S.stars[i]) { add(g, 2000); return; }
  S.stars[i] = 1; S.fl.star[i] = 1.6;
  const p = LYRA[STARS[i].k];
  add(g, 2500, p[0], p[1] - 24, C.cyan);
  g.fx.burst(p[0], p[1], { n: 22, colors: ['#fff', C.cyan, C.gold], speed: 380, size: 7, shape: 'star', life: .9 });
  g.fx.ring(p[0], p[1], { r1: 90, color: C.cyan, width: 5, life: .6 });
  g.sfx('power');
  const n = S.stars.filter(Boolean).length;
  if (n === 5) constellation(g);
  else say('Звезда ' + STARS[i].name + '!', `Созвездие Лиры: ${n} из 5`);
}
function constellation(g) {
  add(g, 25000, 335, 760, C.gold);
  S.level++; S.stars = [0, 0, 0, 0, 0]; S.bumps = 0;
  const extra = S.firstConst; S.firstConst = false;
  if (extra) S.extra++;
  say('Созвездие Лиры!', extra ? 'Звездопад и ещё один шарик в запас' : 'Звездопад: ещё два шарика');
  g.sfx('win'); g.shake(10, .4);
  for (const k in LYRA) g.fx.burst(LYRA[k][0], LYRA[k][1], { n: 26, colors: ['#fff', C.gold, C.cyan, C.pink], speed: 520, size: 9, shape: 'star', life: 1.3, gravity: 200 });
  // звездопад: шарик из «Чёрной дыры» и шарик из канала запуска
  const b1 = { x: HOLE.x, y: HOLE.y, vx: 0, vy: 0, lock: .8, noHole: 0, still: 0, trail: [] };
  const b2 = newBall(); b2.ready = false; b2.vy = -2700;
  S.balls.push(b1, b2);
  S.save = Math.max(S.save, 10);
}
function laneHit(g, i) {
  S.fl.lane[i] = .5;
  if (S.skill === i && S.skillT > 0) { add(g, 5000, LANE_C[i], LANE_Y - 30, C.pink); say('Точный запуск!', '+' + fmt(5000 * S.level)); g.sfx('coin'); }
  S.skill = -1;
  if (S.lanes[i]) { add(g, 100); return; }
  S.lanes[i] = 1; add(g, 500, LANE_C[i], LANE_Y - 30); S.bonus += 100; g.sfx('pling', { pitch: 1 + i * .12 });
  if (S.lanes.every(Boolean)) {
    S.X = Math.min(5, S.X + 1); S.lanes = [0, 0, 0]; S.fl.lane = [1, 1, 1];
    add(g, 2500); say('Три дорожки!', 'Бонус в конце шарика ×' + S.X);
    star(g, 0);
  }
}
function dropHit(g, i, b) {
  if (S.drops[i]) return;
  S.drops[i] = 1; S.fl.d[i] = .4; add(g, 750, 92, (DROPS[i][0] + DROPS[i][1]) / 2, C.gold); S.bonus += 200; g.sfx('coin', { pitch: .9 + i * .08 });
  if (S.drops.every(Boolean)) {
    add(g, 5000); S.kick = true; S.fl.kick = 1; S.dropT = 1.4;
    say('Все звёзды-мишени!', 'Слева включилась пружина — спасёт шарик');
    star(g, 1);
  }
}
function standHit(g, i) {
  S.fl.st[i] = .45;
  if (S.stands[i]) { add(g, 250); g.sfx('hit', { pitch: 1.4 }); return; }
  S.stands[i] = 1; add(g, 1000, 576, (STANDS[i][0] + STANDS[i][1]) / 2, C.cyan); S.bonus += 200; g.sfx('pling', { pitch: 1.3 + i * .1 });
  if (S.stands.every(Boolean)) { add(g, 5000); S.standT = 1.2; say('Три кометы!', 'Звезда Дельта зажглась'); star(g, 2); }
}
function bumperHit(g, i) {
  S.fl.b[i] = .18; add(g, 100); S.bumps++; S.bonus += 20;
  g.sfx('bounce', { pitch: [1, 1.18, .86][i], gap: .02 });
  if (S.bumps === 25 && !S.stars[4]) star(g, 4);
  else if (!S.stars[4] && S.bumps % 5 === 0) say('Планеты: ' + S.bumps + ' из 25', 'Ещё — и зажжётся Шелиак');
}

function endBall(g) {
  const bonus = S.bonus * S.X + S.stars.filter(Boolean).length * 1000;
  if (bonus) S.score += bonus;
  S.ball++;
  S.X = 1; S.bonus = 0; S.kick = S.kick && false; S.saveArm = true;
  if (S.ball > 3 + S.extra) { gameOver(g); return; }
  S.mode = 'wait'; S.waitT = 1.6;
  say('Шарик ' + S.ball, bonus ? 'Бонус +' + fmt(bonus) : 'Ещё попытка');
  g.sfx('hurt');
}

/* ---------------- физика ---------------- */
let HX = 0, HY = 0;
function segHit(b, w) {
  const dx = w.bx - w.ax, dy = w.by - w.ay, l2 = dx * dx + dy * dy;
  let t = ((b.x - w.ax) * dx + (b.y - w.ay) * dy) / l2;
  t = t < 0 ? 0 : t > 1 ? 1 : t;
  const px = w.ax + dx * t, py = w.ay + dy * t, rr = R + w.rad;
  let nx = b.x - px, ny = b.y - py;
  const d2 = nx * nx + ny * ny;
  if (d2 >= rr * rr) return -1;
  const d = Math.sqrt(d2) || .0001; nx /= d; ny /= d;
  b.x = px + nx * rr; b.y = py + ny * rr;
  const vn = b.vx * nx + b.vy * ny;
  if (vn < 0) { b.vx -= (1 + w.e) * vn * nx; b.vy -= (1 + w.e) * vn * ny; }
  HX = nx; HY = ny;
  return vn < 0 ? -vn : 0;
}
function flipDir(f) { return f.side > 0 ? [Math.cos(f.a), Math.sin(f.a)] : [-Math.cos(f.a), Math.sin(f.a)]; }
function flipHit(b, f) {
  const [dx, dy] = flipDir(f);
  let t = ((b.x - f.px) * dx + (b.y - f.py) * dy) / f.len;
  t = t < 0 ? 0 : t > 1 ? 1 : t;
  const cx = f.px + dx * f.len * t, cy = f.py + dy * f.len * t, rad = f.r0 + (f.r1 - f.r0) * t, rr = R + rad;
  let nx = b.x - cx, ny = b.y - cy;
  const d2 = nx * nx + ny * ny;
  if (d2 >= rr * rr) return false;
  const d = Math.sqrt(d2) || .0001; nx /= d; ny /= d;
  b.x = cx + nx * rr; b.y = cy + ny * rr;
  const om = f.side > 0 ? f.w : -f.w, rx = cx - f.px, ry = cy - f.py;
  const sx = -om * ry, sy = om * rx;
  const vn = (b.vx - sx) * nx + (b.vy - sy) * ny;
  if (vn < 0) { const e = Math.abs(f.w) > 2 ? .38 : .22; b.vx -= (1 + e) * vn * nx; b.vy -= (1 + e) * vn * ny; }
  return true;
}
function moveFlip(f, held, h) {
  const target = held ? f.up : f.rest, sp = held ? 30 : 17;
  let na = f.a;
  if (na > target) na = Math.max(target, na - sp * h); else if (na < target) na = Math.min(target, na + sp * h);
  f.w = (na - f.a) / h; f.a = na;
}
function stepBall(g, b, h) {
  b.vy += G * h;
  // «Чёрная дыра» тянет к себе
  if (b.noHole <= 0) {
    const dx = HOLE.x - b.x, dy = HOLE.y - b.y, d = Math.hypot(dx, dy);
    if (d < 95 && d > .5) { const a = 7200 * (1 - d / 95); b.vx += dx / d * a * h; b.vy += dy / d * a * h; }
    if (d < 15 && Math.hypot(b.vx, b.vy) < 1500) {
      b.lock = 1.3; b.x = HOLE.x; b.y = HOLE.y; b.vx = b.vy = 0;
      S.fl.hole = 1.3; add(g, 3000, HOLE.x + 30, HOLE.y - 40, C.violet); S.bonus += 300;
      g.sfx('whoosh'); g.sound.tone(220, g.sound.now(), .9, .12, 'sine', null, 55);
      star(g, 3);
      return;
    }
  }
  const sp = Math.hypot(b.vx, b.vy);
  if (sp > VMAX) { b.vx *= VMAX / sp; b.vy *= VMAX / sp; }
  b.vx *= 1 - .1 * h; b.vy *= 1 - .1 * h;
  const py = b.y;
  b.x += b.vx * h; b.y += b.vy * h;
  for (const w of walls) {
    if (w.drop != null && S.drops[w.drop]) continue;
    if (w.one && (b.x - w.ax) * w.one.x + (b.y - w.ay) * w.one.y < 0) continue;
    const imp = segHit(b, w);
    if (imp < 0) continue;
    if (w.sling != null && imp > 140) {
      b.vx += HX * 760; b.vy += HY * 760; S.fl.s[w.sling] = .14; add(g, 30); g.sfx('hit', { pitch: 1.2 });
    } else if (w.drop != null && imp > 60) dropHit(g, w.drop, b);
    else if (w.stand != null && imp > 60) standHit(g, w.stand);
    else if (imp > 420 && (w.rail || w.post || w.slingSide || w.lanePost)) g.sfx('land', { vol: Math.min(1, imp / 1800), gap: .05 });
  }
  BUMPERS.forEach((p, i) => {
    const dx = b.x - p.x, dy = b.y - p.y, rr = p.r + R, d2 = dx * dx + dy * dy;
    if (d2 >= rr * rr) return;
    const d = Math.sqrt(d2) || 1, nx = dx / d, ny = dy / d;
    b.x = p.x + nx * rr; b.y = p.y + ny * rr;
    const vn = b.vx * nx + b.vy * ny;
    if (vn < 0) { b.vx -= 1.5 * vn * nx; b.vy -= 1.5 * vn * ny; }
    if (S.fl.b[i] <= .1) { b.vx += nx * 640; b.vy += ny * 640; bumperHit(g, i); g.fx.ring(p.x, p.y, { r0: p.r, r1: p.r + 34, color: p.c[1], width: 6, life: .3 }); }
  });
  for (const f of FLIP) flipHit(b, f);
  // верхние дорожки: шарик прошёл линию сверху вниз
  if (py < LANE_Y && b.y >= LANE_Y) for (let i = 0; i < 3; i++) if (b.x > LANE_X[i] && b.x < LANE_X[i + 1]) laneHit(g, i);
  // пружина в левой отводящей дорожке
  if (S.kick && b.x < 100 && b.y > 1150 && b.vy > 0) {
    S.kick = false; S.fl.kick = .8; b.vy = -2150; b.vx = 30; b.y = 1150;
    say('Пружина!', 'Шарик спасён'); g.sfx('jump', { pitch: .7 }); g.shake(6, .2);
  }
  if (b.y > H + 30) b.gone = true;
}

function update(g, dt) {
  if (!S) return;
  S.t += dt;
  for (const k of ['b', 's', 'd', 'st', 'lane', 'star']) S.fl[k] = S.fl[k].map((v) => Math.max(0, v - dt));
  S.fl.hole = Math.max(0, S.fl.hole - dt); S.fl.kick = Math.max(0, S.fl.kick - dt);
  if (S.msg && (S.msg.life -= dt) <= 0) S.msg = null;
  if (A.shot) return;
  const play = S.mode === 'play' && !g.screenOn;
  const L = play && leftHeld(g), Rh = play && rightHeld(g);
  if (L && !S.wasL) { S.lanes.push(S.lanes.shift()); g.sound.tone(150, g.sound.now(), .06, .09, 'square', null, 80); }
  if (Rh && !S.wasR) { S.lanes.unshift(S.lanes.pop()); g.sound.tone(170, g.sound.now(), .06, .09, 'square', null, 90); }
  S.wasL = L; S.wasR = Rh;
  if (S.mode === 'wait') {
    S.waitT -= dt;
    if (S.waitT <= 0) { S.mode = 'play'; S.balls = [newBall()]; }
  }
  if (S.mode !== 'play' && S.mode !== 'wait') { for (const f of FLIP) moveFlip(f, false, dt); return; }
  // таймеры
  if (S.save > 0) S.save -= dt;
  if (S.skillT > 0) S.skillT -= dt;
  if (S.dropT > 0 && (S.dropT -= dt) <= 0) S.drops = [0, 0, 0, 0];
  if (S.standT > 0 && (S.standT -= dt) <= 0) S.stands = [0, 0, 0];
  if (S.nudgeT > 0) S.nudgeT -= dt;
  // пружина запуска
  const ready = S.balls.find((b) => b.ready);
  const hold = play && plungeHeld(g);
  if (ready && hold) { S.charge = Math.min(1, S.charge + dt / .9); if (!S.plungeHeld) g.sfx('click'); }
  if (ready && !hold && S.plungeHeld && S.charge > .04) {
    ready.ready = false; ready.vy = -(1500 + 1500 * S.charge); ready.vx = 0;
    g.sfx('whoosh'); g.sound.tone(90 + S.charge * 60, g.sound.now(), .18, .14, 'sine', null, 40);
    if (S.saveArm) { S.save = 8; S.saveArm = false; }
    S.skill = A.randInt(0, 2); S.skillT = 4.5;
    S.charge = 0;
  }
  if (!ready) S.charge = 0;
  S.plungeHeld = hold;
  // встряхнуть (↑): раз в полторы секунды
  if (play && g.input.pressed('up') && S.nudgeT <= 0) {
    S.nudgeT = 1.5; g.shake(7, .18); g.sfx('land');
    for (const b of S.balls) if (!b.ready && !b.lock) { b.vx += A.rand(-160, 160); b.vy -= 220; }
  }
  const h = dt / SUB;
  for (let s = 0; s < SUB; s++) {
    for (let i = 0; i < 2; i++) moveFlip(FLIP[i], i ? Rh : L, h);
    for (const b of S.balls) if (!b.ready && !b.lock && !b.gone) stepBall(g, b, h);
    for (let i = 0; i < S.balls.length; i++) for (let j = i + 1; j < S.balls.length; j++) {
      const a = S.balls[i], c = S.balls[j];
      if (a.ready || c.ready || a.lock || c.lock) continue;
      const dx = c.x - a.x, dy = c.y - a.y, d = Math.hypot(dx, dy);
      if (d >= 2 * R || d < .01) continue;
      const nx = dx / d, ny = dy / d, o = (2 * R - d) / 2;
      a.x -= nx * o; a.y -= ny * o; c.x += nx * o; c.y += ny * o;
      const rv = (c.vx - a.vx) * nx + (c.vy - a.vy) * ny;
      if (rv < 0) { const j2 = -rv * .95; a.vx -= nx * j2; a.vy -= ny * j2; c.vx += nx * j2; c.vy += ny * j2; }
    }
  }
  for (const b of S.balls) {
    if (b.lock) {
      b.lock -= dt;
      if (b.lock <= 0) {
        b.lock = 0; b.noHole = .7; const dx = 330 - HOLE.x, dy = 1000 - HOLE.y, l = Math.hypot(dx, dy);
        b.vx = dx / l * 820; b.vy = dy / l * 820; g.sfx('jump', { pitch: .8 }); g.fx.ring(HOLE.x, HOLE.y, { r1: 70, color: C.violet, life: .4 });
      }
      continue;
    }
    if (b.noHole > 0) b.noHole -= dt;
    if (b.ready) continue;
    // снова лёг на пружину (слабый запуск)
    if (b.x > 640 && b.y > 1180 && Math.abs(b.vy) < 140) { Object.assign(b, { x: 665, y: 1238 - R, vx: 0, vy: 0, ready: true }); continue; }
    const sp = Math.hypot(b.vx, b.vy);
    const cradle = b.y > 1000 && (leftHeld(g) || rightHeld(g));          // шарик держат на поднятом флиппере — это нарочно
    b.still = sp < 18 && !cradle ? b.still + dt : 0;
    if (b.still > 2.2) { b.vy = b.y > 1000 ? -260 : -520; b.vx = A.rand(-200, 200); b.still = 0; }   // застрял — сам «встряхиваем» стол
    b.trail.push(b.x, b.y); if (b.trail.length > 16) b.trail.splice(0, 2);
  }
  const before = S.balls.length;
  S.balls = S.balls.filter((b) => !b.gone);
  if (S.mode === 'play' && before && !S.balls.length) {
    if (S.save > 0) { S.balls = [newBall()]; say('Страховка', 'Шарик вернулся — запускайте снова'); g.sfx('power', { pitch: .8 }); S.save = 0; S.saveArm = true; }
    else endBall(g);
  }
}

/* ---------------- рисование ---------------- */
let bg = null, bgScale = 0;
function rnd(seed) { let s = seed; return () => { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; }; }
function tablePath(c) {
  c.beginPath(); c.moveTo(30, 1280); c.lineTo(30, 330); c.arc(AC.x, AC.y, AC.r, Math.PI, 0); c.lineTo(690, 1280); c.closePath();
}
function buildBg(scale) {
  const cv = document.createElement('canvas');
  cv.width = Math.ceil(W * scale); cv.height = Math.ceil(H * scale);
  const c = cv.getContext('2d'); c.scale(scale, scale);
  // корпус стола — тёмный лиловый металл
  const rail = c.createLinearGradient(0, 0, W, 0);
  rail.addColorStop(0, '#1b1240'); rail.addColorStop(.04, '#3a2a78'); rail.addColorStop(.08, '#160e36');
  rail.addColorStop(.92, '#160e36'); rail.addColorStop(.96, '#3a2a78'); rail.addColorStop(1, '#1b1240');
  c.fillStyle = rail; c.fillRect(0, 0, W, H);
  c.save(); tablePath(c); c.clip();
  const sky = c.createLinearGradient(0, 0, 0, H);
  sky.addColorStop(0, '#120a3a'); sky.addColorStop(.45, '#1a0f4e'); sky.addColorStop(.8, '#0f1340'); sky.addColorStop(1, '#090726');
  c.fillStyle = sky; c.fillRect(0, 0, W, H);
  const neb = (x, y, r, col) => { const gr = c.createRadialGradient(x, y, 0, x, y, r); gr.addColorStop(0, col); gr.addColorStop(1, 'rgba(0,0,0,0)'); c.fillStyle = gr; c.fillRect(x - r, y - r, r * 2, r * 2); };
  neb(200, 360, 300, 'rgba(255,90,200,.20)'); neb(520, 700, 340, 'rgba(70,200,255,.16)'); neb(330, 780, 220, 'rgba(160,120,255,.22)');
  neb(150, 1000, 260, 'rgba(120,60,255,.14)'); neb(560, 260, 200, 'rgba(255,200,90,.10)');
  // небесная сетка — тонкие дуги, как на звёздной карте
  c.strokeStyle = 'rgba(180,160,255,.07)'; c.lineWidth = 1.5;
  for (let r = 160; r < 1100; r += 120) { c.beginPath(); c.arc(335, 1250, r, Math.PI * 1.05, Math.PI * 1.95); c.stroke(); }
  for (let a = 0; a < 9; a++) { const t = Math.PI * (1.08 + a * .105); c.beginPath(); c.moveTo(335, 1250); c.lineTo(335 + Math.cos(t) * 1300, 1250 + Math.sin(t) * 1300); c.stroke(); }
  const r = rnd(7);
  for (let i = 0; i < 260; i++) {
    const x = r() * W, y = r() * H, s = r() < .08 ? 1.8 : r() * 1.1 + .3;
    c.globalAlpha = .35 + r() * .55; c.fillStyle = r() < .2 ? '#ffe7b0' : r() < .4 ? '#c9e8ff' : '#fff';
    c.beginPath(); c.arc(x, y, s, 0, Math.PI * 2); c.fill();
  }
  c.globalAlpha = 1;
  // канал запуска
  c.fillStyle = 'rgba(6,4,22,.55)'; c.fillRect(640, 430, 50, 850);
  for (let y = 1150; y > 520; y -= 60) { c.strokeStyle = 'rgba(255,111,208,.22)'; c.lineWidth = 4; c.lineCap = 'round'; c.beginPath(); c.moveTo(653, y + 10); c.lineTo(665, y); c.lineTo(677, y + 10); c.stroke(); }
  // созвездие Лиры — линии и подпись
  c.strokeStyle = 'rgba(150,220,255,.28)'; c.lineWidth = 2; c.setLineDash([2, 7]); c.lineCap = 'round';
  for (const [a, b] of LYRA_LINES) { c.beginPath(); c.moveTo(LYRA[a][0], LYRA[a][1]); c.lineTo(LYRA[b][0], LYRA[b][1]); c.stroke(); }
  c.setLineDash([]);
  c.beginPath(); c.arc(330, 780, 150, 0, Math.PI * 2); c.strokeStyle = 'rgba(169,139,255,.16)'; c.lineWidth = 2; c.stroke();
  c.beginPath(); c.arc(330, 780, 162, 0, Math.PI * 2); c.strokeStyle = 'rgba(169,139,255,.08)'; c.lineWidth = 8; c.stroke();
  c.font = `italic 600 30px ${A.FONT}`; c.textAlign = 'center'; c.fillStyle = 'rgba(200,190,255,.32)'; c.fillText('Лира', 420, 930);
  // подписи у целей
  c.font = `500 15px ${A.FONT}`; c.fillStyle = 'rgba(210,200,255,.5)';
  c.save(); c.translate(90, 650); c.rotate(-Math.PI / 2); c.fillText('звёзды-мишени', 0, 0); c.restore();
  c.save(); c.translate(578, 628); c.rotate(Math.PI / 2); c.fillText('кометы', 0, 0); c.restore();
  c.fillText('чёрная дыра', HOLE.x + 6, HOLE.y + 58);
  c.fillText('страховка', 335, 1222);
  c.save(); c.translate(64, 1110); c.rotate(-Math.PI / 2); c.fillText('пружина', 0, 0); c.restore();
  // фартук внизу
  c.fillStyle = '#120b30';
  c.beginPath(); c.moveTo(100, 1020); c.lineTo(218, 1079); c.lineTo(218, 1280); c.lineTo(100, 1280); c.closePath(); c.fill();
  c.beginPath(); c.moveTo(570, 1020); c.lineTo(452, 1079); c.lineTo(452, 1280); c.lineTo(570, 1280); c.closePath(); c.fill();
  c.font = `700 15px ${A.FONT}`; c.fillStyle = 'rgba(169,139,255,.55)'; c.fillText('DEWIAR', 156, 1250); c.fillText('★ ★ ★', 514, 1250);
  c.restore();
  // стенки — неоновые трубки
  const tube = (list, col, wd) => {
    for (const pass of [[wd + 9, 'rgba(10,6,30,.9)', 0], [wd, col, 14], [Math.max(1.5, wd * .35), 'rgba(255,255,255,.75)', 0]]) {
      c.lineWidth = pass[0]; c.strokeStyle = pass[1]; c.shadowColor = col; c.shadowBlur = pass[2]; c.lineCap = 'round'; c.lineJoin = 'round';
      c.beginPath(); for (const w of list) { c.moveTo(w.ax, w.ay); c.lineTo(w.bx, w.by); } c.stroke();
    }
    c.shadowBlur = 0;
  };
  tube(walls.filter((w) => w.rail), '#9a7bff', 6);
  tube(walls.filter((w) => w.post || w.guide), '#ff7ad9', 5);
  tube(walls.filter((w) => w.lanePost), '#ffd166', 5);
  tube(walls.filter((w) => w.gate), '#6fe6ff', 4);
  // рогатки — тёмное стекло
  for (const s of SLINGS) {
    c.beginPath(); c.moveTo(...s.a); c.lineTo(...s.b); c.lineTo(...s.c); c.closePath();
    const gr = c.createLinearGradient(s.a[0], s.a[1], s.c[0], s.c[1]); gr.addColorStop(0, 'rgba(120,80,255,.35)'); gr.addColorStop(1, 'rgba(255,100,210,.25)');
    c.fillStyle = gr; c.fill(); c.lineWidth = 3; c.strokeStyle = 'rgba(200,180,255,.6)'; c.stroke();
  }
  // гнёзда огней дорожек и созвездия
  for (const x of LANE_C) { c.beginPath(); A.star(c, x, LANE_Y, 13, 5, .45); c.fillStyle = 'rgba(255,209,102,.13)'; c.fill(); c.lineWidth = 1.5; c.strokeStyle = 'rgba(255,209,102,.4)'; c.stroke(); }
  return cv;
}

function drawFlipper(c, f) {
  const [dx, dy] = flipDir(f), L = f.len;
  c.save(); c.translate(f.px, f.py); c.rotate(Math.atan2(dy, dx));
  c.beginPath();
  c.moveTo(0, -f.r0); c.lineTo(L, -f.r1); c.arc(L, 0, f.r1, -Math.PI / 2, Math.PI / 2); c.lineTo(0, f.r0); c.arc(0, 0, f.r0, Math.PI / 2, Math.PI * 1.5);
  c.closePath();
  const gr = c.createLinearGradient(0, -f.r0, 0, f.r0); gr.addColorStop(0, '#ffffff'); gr.addColorStop(1, '#c4b2ff');
  c.fillStyle = gr; c.fill(); c.lineWidth = 5; c.strokeStyle = '#ff5cc8'; c.stroke();
  c.beginPath(); c.arc(0, 0, 6, 0, Math.PI * 2); c.fillStyle = '#7a62d6'; c.fill();
  c.restore();
}
function glow(c, x, y, r, col, k) {
  if (k <= 0) return;
  const gr = c.createRadialGradient(x, y, 0, x, y, r);
  gr.addColorStop(0, col); gr.addColorStop(1, 'rgba(0,0,0,0)');
  c.globalAlpha = Math.min(1, k); c.fillStyle = gr; c.fillRect(x - r, y - r, r * 2, r * 2); c.globalAlpha = 1;
}
function drawBumper(c, p, i, t) {
  const f = S.fl.b[i] / .18, s = 1 + f * .1;
  glow(c, p.x, p.y, p.r * 2.4, p.c[1], .35 + f * .65);
  c.save(); c.translate(p.x, p.y); c.scale(s, s);
  // кольцо — задняя половина
  c.save(); c.rotate(-.35); c.beginPath(); c.ellipse(0, 0, p.r * 1.55, p.r * .42, 0, Math.PI, Math.PI * 2);
  c.lineWidth = 5; c.strokeStyle = 'rgba(255,255,255,.55)'; c.stroke(); c.restore();
  const gr = c.createRadialGradient(-p.r * .35, -p.r * .4, 2, 0, 0, p.r);
  gr.addColorStop(0, f > .2 ? '#fff' : p.c[0]); gr.addColorStop(.55, p.c[1]); gr.addColorStop(1, p.c[2]);
  c.beginPath(); c.arc(0, 0, p.r, 0, Math.PI * 2); c.fillStyle = gr; c.fill();
  c.save(); c.beginPath(); c.arc(0, 0, p.r, 0, Math.PI * 2); c.clip();
  c.globalAlpha = .25; c.fillStyle = '#fff'; for (let k = -2; k <= 2; k++) c.fillRect(-p.r, k * 11 - 3 + Math.sin(t + i) * 2, p.r * 2, 3); c.restore();
  c.globalAlpha = 1;
  // кольцо — передняя половина
  c.save(); c.rotate(-.35); c.beginPath(); c.ellipse(0, 0, p.r * 1.55, p.r * .42, 0, 0, Math.PI);
  c.lineWidth = 5; c.strokeStyle = f > .2 ? '#fff' : 'rgba(255,255,255,.85)'; c.stroke(); c.restore();
  c.restore();
}
function drawHole(c, t) {
  const x = HOLE.x, y = HOLE.y, lit = !S.stars[3];
  glow(c, x, y, 80, 'rgba(169,139,255,.55)', lit ? .55 + Math.sin(t * 4) * .25 : .25);
  c.save(); c.translate(x, y);
  for (let k = 0; k < 4; k++) {
    c.rotate(t * (1.6 + k * .4) % (Math.PI * 2) * .15 + k);
    c.beginPath(); c.ellipse(0, 0, 44 - k * 6, 16 - k * 2, 0, 0, Math.PI * 1.4);
    c.lineWidth = 3; c.strokeStyle = ['rgba(255,111,208,.7)', 'rgba(169,139,255,.8)', 'rgba(111,230,255,.7)', 'rgba(255,209,102,.6)'][k]; c.stroke();
  }
  c.restore();
  c.beginPath(); c.arc(x, y, 19, 0, Math.PI * 2); c.fillStyle = '#000'; c.fill();
  c.lineWidth = 2.5; c.strokeStyle = 'rgba(200,180,255,.9)'; c.stroke();
}
function drawBall(c, b) {
  if (b.trail.length > 4 && !b.ready) {
    c.globalCompositeOperation = 'lighter';
    for (let i = 0; i < b.trail.length; i += 2) { const k = i / b.trail.length; c.globalAlpha = k * .22; c.beginPath(); c.arc(b.trail[i], b.trail[i + 1], R * (.4 + k * .6), 0, Math.PI * 2); c.fillStyle = '#7fd9ff'; c.fill(); }
    c.globalAlpha = 1; c.globalCompositeOperation = 'source-over';
  }
  if (b.lock) { c.globalAlpha = .4 + Math.sin(S.t * 20) * .2; }
  const gr = c.createRadialGradient(b.x - 5, b.y - 6, 1, b.x, b.y, R);
  gr.addColorStop(0, '#ffffff'); gr.addColorStop(.35, '#dfe4ff'); gr.addColorStop(.75, '#8c90c4'); gr.addColorStop(1, '#3d3a6e');
  c.beginPath(); c.arc(b.x, b.y, R, 0, Math.PI * 2); c.fillStyle = gr; c.fill();
  c.beginPath(); c.ellipse(b.x + 3, b.y + 6, 7, 3, -.4, 0, Math.PI * 2); c.fillStyle = 'rgba(255,140,220,.35)'; c.fill();
  c.globalAlpha = 1;
}
function drawWorld(c, g) {
  const sc = g.scale * TS;
  if (!bg || Math.abs(bgScale - sc) > .01) { bg = buildBg(Math.min(sc, 2.5)); bgScale = sc; }
  c.drawImage(bg, 0, 0, W, H);
  const t = S.t, attract = S.mode === 'title';
  // созвездие: огни звёзд
  STARS.forEach((s, i) => {
    const p = LYRA[s.k], on = S.stars[i] || (attract && Math.floor(t * 3) % 5 === i), f = S.fl.star[i];
    glow(c, p[0], p[1], on ? 46 + f * 30 : 20, on ? 'rgba(160,230,255,.9)' : 'rgba(160,140,255,.35)', on ? .9 : .5);
    c.beginPath(); A.star(c, p[0], p[1], on ? 12 + f * 6 : 8, 4, .38); c.fillStyle = on ? '#fff' : 'rgba(200,190,255,.45)'; c.fill();
  });
  { const p = LYRA.eps; c.beginPath(); c.arc(p[0], p[1], 3, 0, Math.PI * 2); c.fillStyle = 'rgba(220,210,255,.7)'; c.fill(); }
  // огни верхних дорожек
  for (let i = 0; i < 3; i++) {
    const on = S.lanes[i] || S.fl.lane[i] > 0 || (attract && Math.floor(t * 4) % 3 === i), sk = S.skill === i && S.skillT > 0 && Math.floor(t * 8) % 2;
    if (on || sk) { glow(c, LANE_C[i], LANE_Y, 40, sk ? 'rgba(255,111,208,.9)' : 'rgba(255,209,102,.9)', .9); c.beginPath(); A.star(c, LANE_C[i], LANE_Y, 13, 5, .45); c.fillStyle = sk ? '#ffd0f1' : '#fff3c4'; c.fill(); }
  }
  // звёзды-мишени
  DROPS.forEach((y, i) => {
    const down = S.drops[i];
    if (down) { c.fillStyle = 'rgba(0,0,0,.4)'; c.fillRect(40, y[0], 16, y[1] - y[0]); return; }
    const f = S.fl.d[i];
    A.rr(c, 40, y[0], 16, y[1] - y[0], 4); c.fillStyle = f ? '#fff' : '#ffc94d'; c.fill(); c.lineWidth = 2; c.strokeStyle = '#7a4a10'; c.stroke();
    c.beginPath(); A.star(c, 48, (y[0] + y[1]) / 2, 6, 5, .45); c.fillStyle = '#7a4a10'; c.fill();
  });
  // кометы
  STANDS.forEach((y, i) => {
    const on = S.stands[i], f = S.fl.st[i];
    if (on || f) glow(c, 613, (y[0] + y[1]) / 2, 34, 'rgba(111,230,255,.9)', .8);
    A.rr(c, 606, y[0], 16, y[1] - y[0], 4); c.fillStyle = f ? '#fff' : on ? '#8ff0ff' : '#2d6f8e'; c.fill();
    c.lineWidth = 2; c.strokeStyle = '#0d3a52'; c.stroke();
  });
  // рогатки: вспышка резинки
  SLINGS.forEach((s, i) => {
    const f = S.fl.s[i] / .14;
    c.lineCap = 'round'; c.lineWidth = 7 + f * 4; c.strokeStyle = f > 0 ? '#ffffff' : '#ff6fd0';
    c.beginPath(); c.moveTo(...s.a); c.lineTo(...s.c); c.stroke();
    if (f > 0) glow(c, (s.a[0] + s.c[0]) / 2, (s.a[1] + s.c[1]) / 2, 70, 'rgba(255,111,208,.8)', f);
  });
  drawHole(c, t);
  BUMPERS.forEach((p, i) => drawBumper(c, p, i, t));
  // пружина слева и страховка
  { const on = S.kick, f = S.fl.kick; if (on || f) glow(c, 65, 1180, 36, 'rgba(255,111,208,.9)', on ? .6 + Math.sin(t * 6) * .3 : f);
    c.beginPath(); c.moveTo(65, 1166); c.lineTo(76, 1184); c.lineTo(54, 1184); c.closePath(); c.fillStyle = on ? '#fff' : 'rgba(255,111,208,.35)'; c.fill(); }
  { const on = S.save > 0 && (S.save > 2 || Math.floor(t * 6) % 2); if (on) { glow(c, 335, 1216, 60, 'rgba(99,242,196,.8)', .7); c.font = `700 15px ${A.FONT}`; c.textAlign = 'center'; c.fillStyle = '#c9ffee'; c.fillText('страховка', 335, 1222); } }
  // канал запуска: пружина
  const ch = S.charge, top = 1238 + ch * 34;
  c.strokeStyle = '#b9a6ff'; c.lineWidth = 3; c.beginPath();
  for (let k = 0; k <= 8; k++) { const y = top + 8 + (1280 - top - 8) * k / 8; c.lineTo(k % 2 ? 678 : 652, y); }
  c.stroke();
  A.rr(c, 646, top - 2, 38, 10, 4); c.fillStyle = '#ffd166'; c.fill();
  if (ch > 0) { A.rr(c, 694, 1270 - 200 * ch, 6, 200 * ch, 3); c.fillStyle = ch > .85 ? C.pink : C.gold; c.fill(); }
  // флипперы и шарики
  for (const f of FLIP) drawFlipper(c, f);
  for (const b of S.balls) drawBall(c, b);
}

function drawLed(c, x, y, w, h, text, sub) {
  A.rr(c, x, y, w, h, 12); c.fillStyle = '#07051a'; c.fill(); c.lineWidth = 2; c.strokeStyle = 'rgba(169,139,255,.35)'; c.stroke();
  c.save(); A.rr(c, x, y, w, h, 12); c.clip();
  c.fillStyle = 'rgba(255,255,255,.025)'; for (let yy = y + 2; yy < y + h; yy += 4) c.fillRect(x, yy, w, 1.5);
  c.restore();
  if (!text) return;
  c.textAlign = 'center'; c.textBaseline = 'middle';
  c.font = `800 ${sub ? 24 : 26}px ${A.FONT}`; c.fillStyle = C.gold; c.shadowColor = C.gold; c.shadowBlur = 10;
  c.fillText(text, x + w / 2, y + (sub ? h * .36 : h / 2));
  c.shadowBlur = 0;
  if (sub) { c.font = `500 18px ${A.FONT}`; c.fillStyle = '#ffe7b3'; c.fillText(sub, x + w / 2, y + h * .72); }
}
function ballsLeft() { return Math.max(0, 3 + S.extra - S.ball + (S.mode === 'play' || S.mode === 'wait' ? 0 : 1)); }
function drawHudTop(c) {                                  // телефон: табло над столом
  const gr = c.createLinearGradient(0, 0, 0, TY); gr.addColorStop(0, '#120a34'); gr.addColorStop(1, '#1d1150');
  c.fillStyle = gr; c.fillRect(0, 0, SW, TY);
  c.fillStyle = 'rgba(169,139,255,.5)'; c.fillRect(0, TY - 2, SW, 2);
  c.textBaseline = 'alphabetic'; c.textAlign = 'left';
  c.font = `800 44px ${A.FONT}`; c.fillStyle = C.ink; c.fillText(fmt(S.score), 24, 52);
  c.textAlign = 'right'; c.font = `600 20px ${A.FONT}`; c.fillStyle = C.dim;
  c.fillText((S.X > 1 ? '×' + S.X + '   ' : '') + (S.mode === 'title' ? '' : 'шарик ' + Math.min(S.ball, 3 + S.extra)), SW - 24, 30);
  for (let i = 0; i < ballsLeft(); i++) { c.beginPath(); c.arc(SW - 32 - i * 26, 50, 8, 0, Math.PI * 2); c.fillStyle = '#d9dcff'; c.fill(); }
  const m = S.msg;
  drawLed(c, 16, 66, SW - 32, 44, m ? m.t + (m.s ? ' · ' + m.s : '') : S.mode === 'title' ? 'Звёздный пинбол' : `Созвездие Лиры: ${S.stars.filter(Boolean).length} из 5`);
}
function drawPanels(c, g) {                               // широкое окно: слева правила, справа табло и задания
  const L0 = 28, LW = TX - 56, R0 = TX + W * TS + 28, RW = SW - R0 - 28;
  const bgr = c.createLinearGradient(0, 0, 0, SH); bgr.addColorStop(0, '#120a34'); bgr.addColorStop(1, '#0b0724');
  c.fillStyle = bgr; c.fillRect(0, 0, TX, SH); c.fillRect(TX + W * TS, 0, SW - TX - W * TS, SH);
  c.textBaseline = 'alphabetic';
  // слева — название и как играть
  c.textAlign = 'left'; c.font = `800 38px ${A.FONT}`; c.fillStyle = C.ink; c.fillText('Звёздный', L0, 210); c.fillText('пинбол', L0, 254);
  c.font = `500 17px ${A.FONT}`; c.fillStyle = C.dim;
  const how = A.isTouch ? ['Левая половина — левый флиппер,', 'правая — правый.', 'Держите палец — пружина сжимается.']
    : ['← и → или Z и / — флипперы', 'Пробел — пружина: держите и отпустите', '↑ — встряхнуть стол', 'Мышь: левая и правая кнопки'];
  how.forEach((s, i) => c.fillText(s, L0, 300 + i * 28));
  if (g.best) { c.font = `600 18px ${A.FONT}`; c.fillStyle = C.gold; c.fillText('Рекорд ' + fmt(g.best), L0, 300 + how.length * 28 + 26); }
  // справа — очки, шарики, сообщение, задания
  c.font = `500 17px ${A.FONT}`; c.fillStyle = C.dim; c.fillText('Очки', R0, 196);
  c.font = `800 46px ${A.FONT}`; c.fillStyle = C.ink; c.fillText(fmt(S.score), R0, 244);
  c.font = `600 18px ${A.FONT}`; c.fillStyle = C.dim;
  c.fillText((S.mode === 'title' ? '3 шарика' : 'шарик ' + Math.min(S.ball, 3 + S.extra)) + (S.X > 1 ? '  ·  бонус ×' + S.X : '') + (S.level > 1 ? '  ·  круг ' + S.level : ''), R0, 274);
  const m = S.msg;
  drawLed(c, R0, 292, RW, 70, m ? m.t : 'Созвездие Лиры', m ? m.s : `${S.stars.filter(Boolean).length} из 5 звёзд`);
  c.textAlign = 'left'; c.textBaseline = 'alphabetic';
  STARS.forEach((s, i) => {
    const y = 400 + i * 34, on = S.stars[i];
    c.beginPath(); A.star(c, R0 + 10, y - 6, on ? 10 : 8, 4, .38); c.fillStyle = on ? '#fff' : 'rgba(200,190,255,.35)'; c.fill();
    if (on) glow(c, R0 + 10, y - 6, 26, 'rgba(160,230,255,.8)', .7);
    c.font = `700 17px ${A.FONT}`; c.fillStyle = on ? C.cyan : C.ink; c.fillText(s.name, R0 + 30, y);
    c.font = `400 16px ${A.FONT}`; c.fillStyle = C.dim;
    const extra = i === 4 && !on ? ` · ${Math.min(S.bumps, 25)}/25` : '';
    const nw = (c.font = `700 17px ${A.FONT}`, c.measureText(s.name + ' ').width); c.font = `400 16px ${A.FONT}`;
    c.fillText('— ' + s.task.replace('25 ударов по планетам', 'удары по планетам') + extra, R0 + 30 + nw, y);
  });
}

function draw(ctx, g) {
  if (!S) return;
  ctx.fillStyle = C.deep; ctx.fillRect(0, 0, SW, SH);
  ctx.save(); ctx.translate(TX, TY); ctx.scale(TS, TS);
  drawWorld(ctx, g);
  if (g.fxWorld) g.fxWorld(ctx);
  ctx.restore();
  if (LAND) drawPanels(ctx, g); else drawHudTop(ctx);
}

/* ---------------- обложка (?shot) ---------------- */
function shotScene() {
  S = fresh(); S.mode = 'play'; S.score = 48250; S.stars = [1, 1, 0, 1, 0]; S.lanes = [1, 0, 1]; S.drops = [0, 1, 0, 0]; S.stands = [1, 0, 0]; S.X = 3;
  S.bumps = 14; S.kick = true; S.save = 5; S.msg = { t: 'Звезда Сулафат!', s: 'Созвездие Лиры: 3 из 5', life: 99 };
  S.fl.b[1] = .16;
  const b = newBall(); Object.assign(b, { x: 380, y: 610, vx: 300, vy: -900, ready: false });
  for (let i = 6; i > 0; i--) b.trail.push(b.x - 300 * i * .01, b.y + 900 * i * .01);
  S.balls = [b];
  FLIP[1].a = FLIP[1].up;
}

A.game({
  id: 'pinball', tone: 'dark', title: 'Звёздный пинбол', width: SW, height: SH, orientation: LAND ? 'landscape' : 'portrait', music: 'neon',
  keys: { KeyZ: 'left', ShiftLeft: 'left', Slash: 'right', ShiftRight: 'right', KeyX: 'up' },
  help: {
    desktop: '<kbd>←</kbd> <kbd>→</kbd> — флипперы · <kbd>Пробел</kbd> — пружина (держите и отпустите) · <kbd>↑</kbd> — встряхнуть · <kbd>P</kbd> пауза',
    short: '<b>←</b> и <b>→</b> — флипперы, <b>Пробел</b> — пружина',
    touch: 'Левая половина экрана — левый флиппер, правая — правый. Держите палец — пружина сжимается, отпустите — запуск'
  },
  init(g) {
    g0 = g;
    const fxDraw = g.fx.draw.bind(g.fx);                 // эффекты — в координатах стола
    g.fx.draw = () => {}; g.fxWorld = fxDraw;
    bindPointers(g);
    window.__pinball = { state: () => S, FLIP, HOLE };   // для проверок (tests/pinball1027_test.py)
    if (A.shot) { shotScene(); return; }
    titleScreen(g);
  },
  update, draw
});
})();
