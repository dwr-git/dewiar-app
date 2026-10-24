/* Небесный пилот — вертикальная стрелялка. */
(() => {
'use strict';
const A = Arcade;
/* Широкое окно (лист «Досуг» на компьютере) — своя раскладка 1280×720: небо во всю ширину, поле-«окошко» посередине во
   всю высоту (мир прежний, книжный 720×1280, только уменьшен), слева — очки, волна, залп и жизни крупно, справа —
   рекорд, подсказка управления и облачко-болельщик. Узкое окно (телефон) — как было. */
const LAND = (() => { try { return innerWidth > (innerHeight - 110) * 1.15; } catch (e) { return false; } })();
const W = 720, H = 1280;                                // мир игры — всегда книжный
const SW = LAND ? 1280 : W, SH = LAND ? 720 : H;        // холст
const FS = LAND ? SH / H : 1, FW = W * FS, FH = H * FS; // поле на холсте: во всю высоту, посередине
const FX = (SW - FW) / 2, FY = (SH - FH) / 2;
/* боковые колонки — у краёв: карточка меню в листе «Досуг» (~770 px) закрывает x ≈ 250…1030, y ≈ 175…550 */
const PW = 218, LCX = 26 + PW / 2, RCX = SW - 26 - PW / 2;
const OUT = '#2b2550';
let S = null;

/* ---------------- облака ---------------- */
function makeCloud(layer, y) {
  const s = [0.55, 0.85, 1.5][layer];
  const n = A.randInt(4, 6), blobs = [];
  for (let i = 0; i < n; i++) blobs.push({ dx: (i - (n - 1) / 2) * 34 + A.rand(-8, 8), dy: A.rand(-14, 10) - (i > 0 && i < n - 1 ? 14 : 0), r: A.rand(30, 46) });
  return { layer, s, x: A.rand(-60, W + 60), y: y == null ? A.rand(-200, H) : y, blobs, speed: [55, 120, 300][layer] };
}
function makeClouds() {
  const c = [];
  for (let i = 0; i < 7; i++) c.push(makeCloud(0));
  for (let i = 0; i < 5; i++) c.push(makeCloud(1));
  for (let i = 0; i < 2; i++) c.push(makeCloud(2));
  return c;
}
function drawCloud(ctx, c) {
  ctx.save(); ctx.translate(c.x, c.y); ctx.scale(c.s, c.s);
  ctx.globalAlpha = [0.55, 0.95, 0.38][c.layer];
  ctx.fillStyle = c.layer === 0 ? '#cfe9ff' : '#cfe0f7';
  for (const b of c.blobs) { ctx.beginPath(); ctx.arc(b.dx, b.dy + 10, b.r, 0, Math.PI * 2); ctx.fill(); }
  ctx.fillStyle = c.layer === 0 ? '#eaf6ff' : '#ffffff';
  for (const b of c.blobs) { ctx.beginPath(); ctx.arc(b.dx, b.dy, b.r, 0, Math.PI * 2); ctx.fill(); }
  ctx.restore(); ctx.globalAlpha = 1;
}

/* ---------------- самолёт ---------------- */
const HERO = { wing: '#fff3dc', stripe: '#ff6b4a', body: '#ff8a3d', hi: '#ffb27a', lo: '#e2582a', nose: '#ffd166', glass: '#5fd3ff' };
const GREEN = { wing: '#e9ffe0', stripe: '#3bbf6a', body: '#5fd17f', hi: '#a4f0b8', lo: '#2f9c55', nose: '#ffe36e', glass: '#ffd3f0' };
function drawPlane(ctx, x, y, o) {
  const c = o.c, bank = o.bank || 0, s = o.s || 1;
  ctx.save(); ctx.translate(x, y); ctx.rotate(o.rot || 0); ctx.scale(s, s);
  ctx.rotate(bank * .1);
  ctx.lineJoin = 'round'; ctx.lineCap = 'round'; ctx.strokeStyle = OUT; ctx.lineWidth = 4;
  const ws = 1 - Math.abs(bank) * .2;
  // крыло
  ctx.save(); ctx.scale(ws, 1);
  A.rr(ctx, -60, -8, 120, 30, 15); ctx.fillStyle = c.wing; ctx.fill();
  ctx.save(); ctx.clip();
  ctx.fillStyle = c.stripe; ctx.fillRect(-60, -8, 15, 30); ctx.fillRect(45, -8, 15, 30);
  ctx.fillStyle = 'rgba(255,255,255,.55)'; ctx.fillRect(-52, -3, 104, 5);
  ctx.fillStyle = 'rgba(0,0,0,.08)'; ctx.fillRect(-60, 14, 120, 8);
  ctx.restore();
  A.rr(ctx, -60, -8, 120, 30, 15); ctx.stroke();
  // хвост
  A.rr(ctx, -27, 32, 54, 15, 7); ctx.fillStyle = c.wing; ctx.fill(); ctx.stroke();
  ctx.restore();
  // фюзеляж
  const gr = ctx.createLinearGradient(-17, 0, 17, 0);
  gr.addColorStop(0, c.hi); gr.addColorStop(.45, c.body); gr.addColorStop(1, c.lo);
  ctx.beginPath(); ctx.ellipse(0, 2, 17, 47, 0, 0, Math.PI * 2); ctx.fillStyle = gr; ctx.fill(); ctx.stroke();
  // кабина
  const gg = ctx.createLinearGradient(0, -20, 0, 8);
  gg.addColorStop(0, '#e8fbff'); gg.addColorStop(1, c.glass);
  ctx.beginPath(); ctx.ellipse(0, -6, 9.5, 13, 0, 0, Math.PI * 2); ctx.fillStyle = gg; ctx.fill(); ctx.lineWidth = 3; ctx.stroke();
  ctx.beginPath(); ctx.ellipse(-3, -11, 2.4, 4.6, 0, 0, Math.PI * 2); ctx.fillStyle = 'rgba(255,255,255,.9)'; ctx.fill();
  // нос
  ctx.lineWidth = 4;
  ctx.beginPath(); ctx.arc(0, -43, 9, 0, Math.PI * 2); ctx.fillStyle = c.nose; ctx.fill(); ctx.stroke();
  // пропеллер
  ctx.save(); ctx.translate(0, -52);
  ctx.beginPath(); ctx.ellipse(0, 0, 32, 5, 0, 0, Math.PI * 2); ctx.fillStyle = 'rgba(255,255,255,.35)'; ctx.fill();
  ctx.scale(Math.cos(o.t * 47), 1);
  A.rr(ctx, -30, -3.5, 60, 7, 3.5); ctx.fillStyle = '#5b4a78'; ctx.fill();
  ctx.restore();
  ctx.restore();
}
function drawShadow(ctx, x, y, s, rx = 46, ry = 18) {
  ctx.save(); ctx.globalAlpha = .16; ctx.fillStyle = '#1b3a6b';
  ctx.beginPath(); ctx.ellipse(x + 44 * s, y + 70 * s, rx * s, ry * s, 0, 0, Math.PI * 2); ctx.fill();
  ctx.restore();
}

/* ---------------- враги ---------------- */
function drawBee(ctx, e, t) {
  ctx.save(); ctx.translate(e.x, e.y); ctx.rotate(Math.sin(t * 5 + e.ph) * .12);
  ctx.lineJoin = 'round'; ctx.strokeStyle = OUT; ctx.lineWidth = 3.5;
  const flap = .55 + .45 * Math.abs(Math.sin(t * 28 + e.ph));
  ctx.fillStyle = 'rgba(255,255,255,.8)';
  ctx.beginPath(); ctx.ellipse(-17, -20, 15, 11 * flap, -.5, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
  ctx.beginPath(); ctx.ellipse(17, -20, 15, 11 * flap, .5, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
  ctx.beginPath(); ctx.ellipse(0, 0, 27, 22, 0, 0, Math.PI * 2); ctx.fillStyle = '#ffd43b'; ctx.fill();
  ctx.save(); ctx.clip(); ctx.fillStyle = '#3a2a4a'; ctx.fillRect(-15, -30, 8, 60); ctx.fillRect(3, -30, 8, 60);
  ctx.fillStyle = 'rgba(255,255,255,.35)'; ctx.beginPath(); ctx.ellipse(-8, -10, 14, 6, -.2, 0, Math.PI * 2); ctx.fill(); ctx.restore();
  ctx.beginPath(); ctx.ellipse(0, 0, 27, 22, 0, 0, Math.PI * 2); ctx.stroke();
  // мордочка
  ctx.fillStyle = '#fff';
  ctx.beginPath(); ctx.arc(-9, 7, 6.5, 0, Math.PI * 2); ctx.arc(9, 7, 6.5, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = OUT; ctx.beginPath(); ctx.arc(-8, 9, 3.4, 0, Math.PI * 2); ctx.arc(10, 9, 3.4, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = '#ff8fb1'; ctx.beginPath(); ctx.arc(-17, 13, 3.5, 0, Math.PI * 2); ctx.arc(17, 13, 3.5, 0, Math.PI * 2); ctx.fill();
  ctx.restore();
}
function drawGrump(ctx, e, t) {
  ctx.save(); ctx.translate(e.x, e.y);
  const sq = 1 + Math.sin(t * 3 + e.ph) * .03;
  ctx.scale(sq, 2 - sq);
  const blobs = [[-34, 4, 30], [0, -10, 38], [34, 4, 30], [-16, 16, 28], [18, 16, 28]];
  ctx.fillStyle = '#b8c3df'; for (const [x, y, r] of blobs) { ctx.beginPath(); ctx.arc(x, y + 7, r, 0, Math.PI * 2); ctx.fill(); }
  ctx.fillStyle = '#eef2ff'; for (const [x, y, r] of blobs) { ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill(); }
  ctx.strokeStyle = OUT; ctx.lineWidth = 4; ctx.lineCap = 'round';
  ctx.beginPath(); ctx.moveTo(-26, -8); ctx.lineTo(-8, -2); ctx.moveTo(26, -8); ctx.lineTo(8, -2); ctx.stroke();
  ctx.fillStyle = OUT; ctx.beginPath(); ctx.arc(-14, 6, 5, 0, Math.PI * 2); ctx.arc(14, 6, 5, 0, Math.PI * 2); ctx.fill();
  ctx.beginPath(); ctx.arc(0, 30, 10, Math.PI * 1.15, Math.PI * 1.85); ctx.stroke();
  ctx.restore();
}
function drawBalloon(ctx, e, t) {
  ctx.save(); ctx.translate(e.x, e.y); ctx.rotate(Math.sin(t * 1.6 + e.ph) * .08);
  ctx.strokeStyle = OUT; ctx.lineWidth = 3; ctx.lineJoin = 'round';
  ctx.beginPath(); ctx.moveTo(0, 36); ctx.quadraticCurveTo(8, 50, 0, 62); ctx.stroke();
  A.rr(ctx, -15, 60, 30, 24, 6); ctx.fillStyle = '#ffd166'; ctx.fill(); ctx.stroke();
  ctx.fillStyle = '#ff6b8b'; ctx.fillRect(-3, 60, 6, 24); ctx.fillRect(-15, 69, 30, 6);
  const gr = ctx.createRadialGradient(-10, -14, 4, 0, 0, 40);
  gr.addColorStop(0, '#fff'); gr.addColorStop(.25, e.color); gr.addColorStop(1, e.dark);
  ctx.beginPath(); ctx.ellipse(0, 0, 31, 37, 0, 0, Math.PI * 2); ctx.fillStyle = gr; ctx.fill(); ctx.lineWidth = 4; ctx.stroke();
  ctx.beginPath(); ctx.moveTo(-6, 36); ctx.lineTo(6, 36); ctx.lineTo(0, 30); ctx.closePath(); ctx.fillStyle = e.dark; ctx.fill(); ctx.stroke();
  ctx.restore();
}
function drawBoss(ctx, b, t) {
  ctx.save(); ctx.translate(b.x, b.y);
  const bob = Math.sin(t * 2) * 6; ctx.translate(0, bob);
  ctx.lineJoin = 'round'; ctx.strokeStyle = OUT; ctx.lineWidth = 5;
  // винты
  for (const sx of [-1, 1]) {
    ctx.save(); ctx.translate(sx * 170, -6);
    A.rr(ctx, -16, -16, 32, 32, 10); ctx.fillStyle = '#7d5bd6'; ctx.fill(); ctx.stroke();
    ctx.beginPath(); ctx.ellipse(sx * 20, 0, 6, 36, 0, 0, Math.PI * 2); ctx.fillStyle = 'rgba(255,255,255,.35)'; ctx.fill();
    ctx.scale(1, Math.cos(t * 40 + sx)); A.rr(ctx, sx * 20 - 4, -34, 8, 68, 4); ctx.fillStyle = '#4b3b78'; ctx.fill();
    ctx.restore();
  }
  // плавники
  ctx.fillStyle = '#ff77c6';
  ctx.beginPath(); ctx.moveTo(-60, -60); ctx.lineTo(-100, -110); ctx.lineTo(-20, -70); ctx.closePath(); ctx.fill(); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(60, -60); ctx.lineTo(100, -110); ctx.lineTo(20, -70); ctx.closePath(); ctx.fill(); ctx.stroke();
  // корпус
  const gr = ctx.createLinearGradient(0, -80, 0, 80);
  gr.addColorStop(0, '#b796ff'); gr.addColorStop(.5, '#8a63f0'); gr.addColorStop(1, '#5a3cc0');
  ctx.beginPath(); ctx.ellipse(0, 0, 160, 76, 0, 0, Math.PI * 2); ctx.fillStyle = gr; ctx.fill(); ctx.stroke();
  ctx.save(); ctx.clip();
  ctx.fillStyle = 'rgba(255,255,255,.18)'; for (let i = -3; i <= 3; i++) ctx.fillRect(i * 44 - 3, -80, 6, 160);
  ctx.fillStyle = 'rgba(255,255,255,.35)'; ctx.beginPath(); ctx.ellipse(-50, -44, 70, 14, -.1, 0, Math.PI * 2); ctx.fill();
  ctx.restore();
  // гондола с пушками
  A.rr(ctx, -70, 52, 140, 44, 16); ctx.fillStyle = '#3f2f73'; ctx.fill(); ctx.stroke();
  for (let i = -2; i <= 2; i++) { ctx.beginPath(); ctx.arc(i * 26, 82, 8, 0, Math.PI * 2); ctx.fillStyle = b.charge > 0 && (i + 2) % 2 === 0 ? '#ff4f9a' : '#1d1638'; ctx.fill(); ctx.lineWidth = 3; ctx.stroke(); }
  // лицо
  ctx.lineWidth = 5;
  const blink = (t % 3.2) > 3.05;
  for (const sx of [-1, 1]) {
    ctx.beginPath(); ctx.ellipse(sx * 46, -2, 22, blink ? 3 : 20, 0, 0, Math.PI * 2); ctx.fillStyle = '#fff'; ctx.fill(); ctx.stroke();
    if (!blink) { ctx.beginPath(); ctx.arc(sx * 46 + b.look * 6, 4, 9, 0, Math.PI * 2); ctx.fillStyle = OUT; ctx.fill(); }
    ctx.beginPath(); ctx.moveTo(sx * 70, -30); ctx.lineTo(sx * 22, -16); ctx.stroke();
  }
  ctx.beginPath(); ctx.arc(0, 44, 22, Math.PI * 1.2, Math.PI * 1.8); ctx.stroke();
  if (b.flash > 0) { ctx.globalAlpha = b.flash * 4; ctx.beginPath(); ctx.ellipse(0, 0, 160, 76, 0, 0, Math.PI * 2); ctx.fillStyle = '#fff'; ctx.fill(); ctx.globalAlpha = 1; }
  ctx.restore();
}

/* ---------------- предметы ---------------- */
function drawItem(ctx, it, t) {
  ctx.save(); ctx.translate(it.x, it.y);
  ctx.lineJoin = 'round'; ctx.strokeStyle = OUT; ctx.lineWidth = 3.5;
  const pulse = 1 + Math.sin(t * 6 + it.ph) * .06;
  if (it.kind === 'coin') {
    ctx.scale(Math.max(.15, Math.abs(Math.cos(t * 4 + it.ph))), 1);
    ctx.beginPath(); ctx.arc(0, 0, 17, 0, Math.PI * 2); ctx.fillStyle = '#ffc93c'; ctx.fill(); ctx.stroke();
    ctx.beginPath(); ctx.arc(0, 0, 11, 0, Math.PI * 2); ctx.strokeStyle = '#e69b00'; ctx.lineWidth = 3; ctx.stroke();
    ctx.fillStyle = '#fff6c8'; ctx.beginPath(); ctx.ellipse(-5, -6, 3, 5, .4, 0, Math.PI * 2); ctx.fill();
  } else if (it.kind === 'power') {
    ctx.scale(pulse, pulse); ctx.rotate(Math.sin(t * 3) * .2);
    ctx.globalAlpha = .35; A.star(ctx, 0, 0, 38, 5, .5); ctx.fillStyle = '#fff3a0'; ctx.fill(); ctx.globalAlpha = 1;
    A.star(ctx, 0, 0, 27, 5, .5); ctx.fillStyle = '#ffd43b'; ctx.fill(); ctx.stroke();
    ctx.fillStyle = OUT; ctx.beginPath(); ctx.arc(-6, -2, 2.6, 0, Math.PI * 2); ctx.arc(6, -2, 2.6, 0, Math.PI * 2); ctx.fill();
    ctx.lineWidth = 2.5; ctx.beginPath(); ctx.arc(0, 2, 5, .2 * Math.PI, .8 * Math.PI); ctx.stroke();
  } else if (it.kind === 'heart') {
    ctx.scale(pulse, pulse); A.heart(ctx, 0, 4, 46, '#ff4f7b', OUT);
  } else if (it.kind === 'shield') {
    ctx.scale(pulse, pulse);
    ctx.beginPath(); ctx.arc(0, 0, 22, 0, Math.PI * 2); ctx.fillStyle = 'rgba(95,211,255,.45)'; ctx.fill(); ctx.strokeStyle = '#3bb8ff'; ctx.lineWidth = 4; ctx.stroke();
    ctx.beginPath(); ctx.moveTo(0, -11); ctx.lineTo(10, -6); ctx.lineTo(8, 6); ctx.lineTo(0, 12); ctx.lineTo(-8, 6); ctx.lineTo(-10, -6); ctx.closePath(); ctx.fillStyle = '#fff'; ctx.fill();
  }
  ctx.restore();
}

/* ---------------- состояние ---------------- */
function fresh() {
  return {
    mode: 'title', score: 0, shown: 0, lives: 3, power: 1, shield: 0, inv: 0, wave: 1, waveT: 0, spawnT: 1.2, boss: null, bosses: 0,
    p: { x: W / 2, y: H - 240, bank: 0, fireT: 0, vx: 0 },
    shots: [], foes: [], bullets: [], items: [], clouds: makeClouds(), banner: null, deadT: 0
  };
}
function banner(text, sub) { S.banner = { text, sub, t: 0 }; }

function startGame(g) {
  const keepClouds = S.clouds;
  S = fresh(); S.clouds = keepClouds; S.mode = 'play';
  g.fx.clear(); g.setPlaying(true); g.playMusic();
  banner('Волна 1', 'Поехали!');
}
function titleScreen(g) {
  S.mode = 'title'; g.setPlaying(false);
  g.screen({
    kicker: Arcade.framed ? 'Досуг' : 'Аркада', title: 'Небесный пилот',
    html: `<p>Пушки стреляют сами. Уворачивайтесь от снарядов, ловите звёзды — они усиливают залп.</p>${g.best ? `<p class="record">Рекорд: ${g.best.toLocaleString('ru-RU')}</p>` : ''}`,
    button: 'Взлететь', onGo: () => startGame(g)
  });
}
function gameOver(g) {
  S.mode = 'over'; g.setPlaying(false); g.stopMusic(); g.sfx('lose');
  const rec = g.submit(S.score);
  g.screen({
    kicker: 'Конец полёта', title: 'Посадка!',
    html: `<div class="score">${S.score.toLocaleString('ru-RU')}</div><p>${rec ? '<span class="record">Новый рекорд!</span>' : `Рекорд: ${g.best.toLocaleString('ru-RU')}`} · волна ${S.wave}</p>`,
    button: 'Ещё раз', onGo: () => startGame(g),
    alt: { label: Arcade.framed ? 'К играм' : 'В аркаду', onGo: () => Arcade.home('../index.html') }
  });
}

/* ---------------- спавн ---------------- */
function spawnPattern() {
  const w = S.wave;
  const pool = ['bees', 'bees', 'balloon'];
  if (w >= 1) pool.push('swoop');
  if (w >= 2) pool.push('beesV', 'cloud', 'dive');
  if (w >= 3) pool.push('swoop', 'cloud', 'dive', 'beesV');
  const kind = A.pick(pool), sp = 1 + (w - 1) * .07;
  if (kind === 'bees') {
    const n = Math.min(7, 4 + Math.floor(w / 2));
    for (let i = 0; i < n; i++) S.foes.push({ type: 'bee', x0: 90 + i * (W - 180) / (n - 1), x: 0, y: -50 - (i % 2) * 40, r: 26, hp: 1 + Math.floor(w / 4), speed: 190 * sp, amp: 50, ph: i * .7, t: 0, score: 100 });
  } else if (kind === 'beesV') {
    const cx = A.rand(200, W - 200);
    for (let i = 0; i < 7; i++) { const k = i - 3; S.foes.push({ type: 'bee', x0: cx + k * 60, x: 0, y: -50 - Math.abs(k) * 55, r: 26, hp: 1 + Math.floor(w / 4), speed: 210 * sp, amp: 18, ph: 0, t: 0, score: 100 }); }
  } else if (kind === 'swoop') {
    const left = Math.random() < .5, y0 = A.rand(80, 260);
    for (let i = 0; i < 4; i++) S.foes.push({ type: 'plane', x: left ? -80 - i * 110 : W + 80 + i * 110, y: y0, vx: (left ? 1 : -1) * 300 * sp, vy: 60, ay: 70, r: 34, hp: 2 + Math.floor(w / 3), t: 0, ph: i, shoot: A.rand(.6, 1.6), score: 200 });
  } else if (kind === 'dive') {
    for (let i = 0; i < 3; i++) S.foes.push({ type: 'plane', x: A.rand(100, W - 100), y: -80 - i * 160, vx: 0, vy: 300 * sp, ay: 0, r: 34, hp: 2 + Math.floor(w / 3), t: 0, ph: i, shoot: A.rand(.5, 1.2), score: 200 });
  } else if (kind === 'cloud') {
    S.foes.push({ type: 'grump', x: A.rand(140, W - 140), y: -90, stopY: A.rand(200, 360), r: 58, hp: 7 + w * 2, t: 0, ph: Math.random() * 6, shootT: 1.2, life: 9, score: 400 });
  } else if (kind === 'balloon') {
    const palette = [['#ff77c6', '#c43a8c'], ['#7c8cff', '#4250c9'], ['#4fe0c0', '#1f9c86'], ['#ffb347', '#d9771a']];
    const [color, dark] = A.pick(palette);
    S.foes.push({ type: 'balloon', x0: A.rand(120, W - 120), x: 0, y: -90, r: 34, hp: 4 + w, t: 0, ph: Math.random() * 6, color, dark, score: 150 });
  }
}
function spawnBoss() {
  S.bosses++;
  const hp = 140 + S.bosses * 70;
  S.boss = { type: 'boss', x: W / 2, y: -220, r: 130, hp, maxhp: hp, t: 0, atk: 1.8, mode: 0, look: 0, flash: 0, charge: 0, score: 5000 * S.bosses };
  S.foes.push(S.boss);
  banner('Босс!', 'Хмурый дирижабль');
  Arcade.sound.play('whoosh');
}

/* ---------------- обновление ---------------- */
function enemyShoot(e, speed, spread = 0, n = 1) {
  const a0 = Math.atan2(S.p.y - e.y, S.p.x - e.x);
  for (let i = 0; i < n; i++) {
    const a = a0 + (n > 1 ? (i - (n - 1) / 2) * spread : 0);
    S.bullets.push({ x: e.x, y: e.y + 20, vx: Math.cos(a) * speed, vy: Math.sin(a) * speed, r: 11, kind: 'orb' });
  }
}
function killFoe(g, e) {
  e.dead = true;
  S.score += e.score;
  const big = e.type === 'boss';
  g.fx.burst(e.x, e.y, { n: big ? 60 : 18, colors: ['#ffd43b', '#ff8a3d', '#fff', '#ff4f7b'], speed: big ? 700 : 380, size: big ? 16 : 9, life: big ? 1.1 : .55 });
  g.fx.burst(e.x, e.y, { n: big ? 20 : 6, colors: ['rgba(255,255,255,.9)', '#dfe7ff'], speed: 120, size: big ? 40 : 20, life: .8, drag: 3 });
  g.fx.ring(e.x, e.y, { r1: big ? 300 : 90, color: '#fff', width: big ? 14 : 6 });
  g.fx.text(e.x, e.y - 10, '+' + e.score, { color: '#ffe066', size: big ? 54 : 32 });
  g.sfx(big ? 'bigboom' : 'boom', { vol: big ? 1 : .6 });
  if (big) {
    g.shake(18, .8);
    for (let i = 0; i < 10; i++) S.items.push({ kind: 'coin', x: e.x + A.rand(-120, 120), y: e.y + A.rand(-40, 40), vy: A.rand(60, 160), ph: i });
    S.items.push({ kind: 'power', x: e.x, y: e.y, vy: 120, ph: 0 });
    if (S.lives < 3) S.items.push({ kind: 'heart', x: e.x + 60, y: e.y, vy: 120, ph: 1 });
    S.boss = null; S.wave++; S.waveT = 0; S.spawnT = 2.5;
    banner('Волна ' + S.wave, 'Дирижабль сбит!');
  } else {
    g.shake(3, .1);
    if (e.type === 'balloon') S.items.push({ kind: S.lives < 3 && Math.random() < .35 ? 'heart' : Math.random() < .2 ? 'shield' : 'power', x: e.x, y: e.y, vy: 110, ph: 0 });
    else if (Math.random() < (e.type === 'grump' ? 1 : .3)) S.items.push({ kind: 'coin', x: e.x, y: e.y, vy: 140, ph: Math.random() * 6 });
  }
}
function hurtPlayer(g) {
  const p = S.p;
  if (S.inv > 0 || S.mode !== 'play') return;
  if (S.shield > 0) {
    S.shield = 0; S.inv = 1; g.sfx('hit', { pitch: 1.6 });
    g.fx.ring(p.x, p.y, { r1: 140, color: '#5fd3ff', width: 10 });
    return;
  }
  S.lives--; S.power = Math.max(1, S.power - 1); S.inv = 2.2;
  g.sfx('hurt'); g.shake(14, .4);
  g.fx.burst(p.x, p.y, { n: 24, colors: ['#ff8a3d', '#ffd43b', '#fff'], speed: 420, size: 10, life: .6 });
  if (S.lives <= 0) {
    S.mode = 'dead'; S.deadT = 0; g.stopMusic(); g.sfx('bigboom');
    g.fx.burst(p.x, p.y, { n: 50, colors: ['#ff8a3d', '#ffd43b', '#fff', '#ff4f7b'], speed: 640, size: 14, life: 1 });
    g.fx.ring(p.x, p.y, { r1: 260, width: 12 });
  }
}
function collect(g, it) {
  const p = S.p;
  if (it.kind === 'coin') { S.score += 50; g.sfx('coin'); g.fx.text(it.x, it.y - 10, '+50', { color: '#ffe066', size: 26 }); }
  else if (it.kind === 'power') {
    if (S.power < 5) { S.power++; g.fx.text(p.x, p.y - 70, S.power === 5 ? 'МАКС!' : 'Залп +1', { color: '#ffd43b', size: 34 }); }
    else { S.score += 500; g.fx.text(p.x, p.y - 70, '+500', { color: '#ffd43b' }); }
    g.sfx('power');
  } else if (it.kind === 'heart') { S.lives = Math.min(5, S.lives + 1); g.sfx('power', { pitch: 1.2 }); g.fx.text(p.x, p.y - 70, 'Жизнь +1', { color: '#ff7a9a', size: 34 }); }
  else if (it.kind === 'shield') { S.shield = 10; g.sfx('power', { pitch: .8 }); g.fx.text(p.x, p.y - 70, 'Щит', { color: '#5fd3ff', size: 34 }); }
  g.fx.burst(it.x, it.y, { n: 10, colors: ['#fff', '#ffe066'], speed: 240, size: 6, shape: 'star', life: .5 });
}
const PATTERNS = {
  1: [[-12, 0, 0], [12, 0, 0]],
  2: [[0, -6, 0], [-16, 0, -.1], [16, 0, .1]],
  3: [[-10, -4, 0], [10, -4, 0], [-22, 0, -.17], [22, 0, .17]],
  4: [[-10, -4, 0], [10, -4, 0], [-22, 0, -.17], [22, 0, .17], [-52, 18, 0], [52, 18, 0]],
  5: [[0, -8, 0], [-12, -4, -.05], [12, -4, .05], [-24, 0, -.2], [24, 0, .2], [-52, 18, -.03], [52, 18, .03]]
};
function fire(g) {
  const p = S.p;
  for (const [ox, oy, a] of PATTERNS[S.power]) S.shots.push({ x: p.x + ox, y: p.y - 50 + oy, vx: Math.sin(a) * 1250, vy: -Math.cos(a) * 1250, a });
  g.sfx('shoot', { gap: .09, vol: .7 });
}

function updateClouds(dt, mul) {
  for (const c of S.clouds) {
    c.y += c.speed * dt * mul;
    if (c.y - 120 * c.s > H) { Object.assign(c, makeCloud(c.layer, -140 * c.s - A.rand(0, 200))); }
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
/* широкое окно: облака по сторонам от поля (в координатах холста) */
const SKY = [];
if (LAND) {
  for (let i = 0; i < 10; i++) {
    const c = makeCloud(i % 3 === 2 ? 1 : 0);
    c.x = skyX(i % 2 === 0); c.y = A.rand(-60, SH + 60);
    c.s *= .62; c.speed *= .32; SKY.push(c);
  }
}
function skyX(left) { return left ? A.rand(FX - 170, FX - 50) : A.rand(FX + FW + 50, FX + FW + 170); }   // между колонкой и полем
function updateSky(dt, mul) {
  for (const c of SKY) {
    c.y += c.speed * dt * mul;
    if (c.y - 90 * c.s > SH) { c.y = -90 * c.s - A.rand(0, 120); c.x = skyX(c.x < SW / 2); }
  }
}

function update(g, dt) {
  const inp = wIn(g.input), p = S.p;
  updateClouds(dt, S.mode === 'title' ? .6 : 1);
  if (LAND) updateSky(dt, S.mode === 'title' ? .6 : 1);
  if (S.banner) { S.banner.t += dt; if (S.banner.t > 2) S.banner = null; }
  S.shown += (S.score - S.shown) * Math.min(1, dt * 8);

  if (S.mode === 'title') {
    p.x = W / 2 + Math.sin(g.t * .9) * 40; p.y = H - 260 + Math.sin(g.t * 1.7) * 14; p.bank = Math.cos(g.t * .9) * .4;
    return;
  }
  if (S.mode === 'dead') {
    S.deadT += dt;
    updateWorld(g, dt);
    if (S.deadT > 1.4) gameOver(g);
    return;
  }
  if (S.mode !== 'play') { updateWorld(g, dt); return; }

  // управление
  const ox = p.x, oy = p.y;
  const kx = (inp.down('right') ? 1 : 0) - (inp.down('left') ? 1 : 0);
  const ky = (inp.down('down') ? 1 : 0) - (inp.down('up') ? 1 : 0);
  if (kx || ky) { const l = Math.hypot(kx, ky) || 1; p.x += kx / l * 620 * dt; p.y += ky / l * 620 * dt; }
  const ptr = inp.pointer;
  if (ptr.down && ptr.type !== 'mouse') { p.x += ptr.dx * 1.3; p.y += ptr.dy * 1.3; }
  else if (inp.mouseActive && !(kx || ky)) { const k = Math.min(1, dt * 11); p.x += (ptr.x - p.x) * k; p.y += (ptr.y - p.y) * k; }
  p.x = A.clamp(p.x, 46, W - 46); p.y = A.clamp(p.y, 150, H - 70);
  p.vx = (p.x - ox) / dt;
  p.bank += (A.clamp(p.vx / 700, -1, 1) - p.bank) * Math.min(1, dt * 10);
  void oy;

  if (S.inv > 0) S.inv -= dt;
  if (S.shield > 0) S.shield -= dt;
  p.fireT -= dt;
  if (p.fireT <= 0) { fire(g); p.fireT = S.power >= 5 ? .1 : .13; }

  // волны
  if (!S.boss) {
    S.waveT += dt;
    S.spawnT -= dt;
    if (S.spawnT <= 0) { spawnPattern(); S.spawnT = Math.max(1.1, 2.6 - S.wave * .14) + A.rand(0, .6); }
    if (S.waveT > 24) {
      S.wave++; S.waveT = 0;
      if (S.wave % 4 === 0) spawnBoss();
      else banner('Волна ' + S.wave);
    }
  }
  updateWorld(g, dt);
}

function updateWorld(g, dt) {
  const p = S.p;
  for (const s of S.shots) { s.x += s.vx * dt; s.y += s.vy * dt; }
  S.shots = S.shots.filter((s) => s.y > -60 && !s.hit);
  for (const e of S.foes) {
    e.t += dt;
    if (e.flash > 0) e.flash -= dt;
    if (e.type === 'bee') { e.y += e.speed * dt; e.x = e.x0 + Math.sin(e.t * 2.6 + e.ph) * e.amp; }
    else if (e.type === 'plane') {
      e.vy += e.ay * dt; e.x += e.vx * dt; e.y += e.vy * dt;
      e.shoot -= dt;
      if (e.shoot <= 0 && e.y > 40 && e.y < H * .6 && S.mode === 'play') { enemyShoot(e, 340 + S.wave * 12); e.shoot = 99; g.sfx('beep', { pitch: .8, vol: .5 }); }
    } else if (e.type === 'grump') {
      if (e.y < e.stopY && e.life > 0) e.y += 110 * dt;
      else { e.x += Math.sin(e.t * .8 + e.ph) * 60 * dt; e.life -= dt; if (e.life <= 0) e.y += 140 * dt; }
      e.shootT -= dt;
      if (e.shootT <= 0 && e.y > 0 && S.mode === 'play') {
        e.shootT = Math.max(.8, 1.6 - S.wave * .06);
        for (const dx of [-26, 26]) S.bullets.push({ x: e.x + dx, y: e.y + 40, vx: 0, vy: 300 + S.wave * 10, r: 10, kind: 'drop' });
      }
    } else if (e.type === 'balloon') { e.y += 85 * dt; e.x = e.x0 + Math.sin(e.t * 1.4 + e.ph) * 40; }
    else if (e.type === 'boss') updateBoss(g, e, dt);
  }
  S.foes = S.foes.filter((e) => !e.dead && e.y < H + 140 && e.x > -500 && e.x < W + 500);

  for (const b of S.bullets) { b.x += b.vx * dt; b.y += b.vy * dt; }
  S.bullets = S.bullets.filter((b) => b.y < H + 40 && b.y > -60 && b.x > -40 && b.x < W + 40 && !b.gone);

  for (const it of S.items) {
    const d = A.dist(it.x, it.y, p.x, p.y);
    if (S.mode === 'play' && d < 170) { const k = Math.min(1, dt * 7); it.x += (p.x - it.x) * k; it.y += (p.y - it.y) * k; }
    else it.y += it.vy * dt;
  }
  // столкновения: выстрелы по врагам
  for (const s of S.shots) {
    for (const e of S.foes) {
      if (e.dead || e.y < -40) continue;
      const rr = e.type === 'boss' ? 0 : e.r;
      const hitBoss = e.type === 'boss' && Math.abs(s.x - e.x) < 160 && Math.abs(s.y - e.y) < 80;
      if (hitBoss || (rr && A.dist(s.x, s.y, e.x, e.y) < rr + 8)) {
        s.hit = true; e.hp--; e.flash = .08;
        g.fx.burst(s.x, s.y + 6, { n: 3, colors: ['#fff', '#ffe066'], speed: 180, size: 4, life: .25 });
        if (e.hp <= 0) killFoe(g, e); else g.sfx('hit', { gap: .05, vol: .5 });
        break;
      }
    }
  }
  if (S.mode !== 'play') { S.items = S.items.filter((it) => it.y < H + 40); return; }
  // по игроку
  for (const b of S.bullets) if (A.dist(b.x, b.y, p.x, p.y) < 15 + b.r * .7) { b.gone = true; hurtPlayer(g); }
  for (const e of S.foes) {
    if (e.dead) continue;
    const hitBoss = e.type === 'boss' && Math.abs(p.x - e.x) < 150 && Math.abs(p.y - e.y) < 70;
    if (hitBoss || (e.type !== 'boss' && A.dist(e.x, e.y, p.x, p.y) < e.r * .75 + 18)) {
      hurtPlayer(g);
      if (e.type !== 'boss' && S.mode === 'play') { e.hp -= 3; if (e.hp <= 0) killFoe(g, e); }
    }
  }
  for (const it of S.items) if (!it.got && A.dist(it.x, it.y, p.x, p.y) < 44) { it.got = true; collect(g, it); }
  S.items = S.items.filter((it) => !it.got && it.y < H + 40);
}

function updateBoss(g, b, dt) {
  b.look = A.clamp((S.p.x - b.x) / 200, -1, 1);
  if (b.y < 250) { b.y += 160 * dt; return; }
  b.x = W / 2 + Math.sin(b.t * .55) * 190;
  if (b.charge > 0) b.charge -= dt;
  b.atk -= dt;
  if (b.atk <= .45 && b.charge <= 0 && b.atk > 0) b.charge = .45;
  if (b.atk <= 0 && S.mode === 'play') {
    const sp = 280 + S.bosses * 30;
    if (b.mode === 0) {
      for (let i = 0; i < 11; i++) { const a = Math.PI / 2 + (i - 5) * .16; S.bullets.push({ x: b.x, y: b.y + 80, vx: Math.cos(a) * sp, vy: Math.sin(a) * sp, r: 11, kind: 'orb' }); }
      b.atk = 1.6;
    } else if (b.mode === 1) {
      enemyShoot({ x: b.x - 52, y: b.y + 60 }, sp * 1.3, .14, 3); enemyShoot({ x: b.x + 52, y: b.y + 60 }, sp * 1.3, .14, 3);
      b.atk = 1.2;
    } else {
      const off = b.t * 1.3;
      for (let i = 0; i < 18; i++) { const a = off + i * Math.PI * 2 / 18; S.bullets.push({ x: b.x, y: b.y, vx: Math.cos(a) * sp * .8, vy: Math.sin(a) * sp * .8, r: 10, kind: 'orb' }); }
      b.atk = 1.9;
    }
    b.mode = (b.mode + 1) % 3;
    g.sfx('beep', { pitch: .6 });
  }
}

/* ---------------- отрисовка ---------------- */
function drawSky(ctx, g) {
  const gr = ctx.createLinearGradient(0, 0, 0, H);
  gr.addColorStop(0, '#4fb8ff'); gr.addColorStop(.55, '#9fe0ff'); gr.addColorStop(1, '#fff0d6');
  ctx.fillStyle = gr; ctx.fillRect(0, 0, W, H);
  if (LAND) return;                                     // солнце в широком окне — на холсте, справа вверху
  const sun = ctx.createRadialGradient(W - 120, 120, 10, W - 120, 120, 320);
  sun.addColorStop(0, 'rgba(255,255,240,.85)'); sun.addColorStop(.25, 'rgba(255,250,220,.35)'); sun.addColorStop(1, 'rgba(255,255,255,0)');
  ctx.fillStyle = sun; ctx.fillRect(0, 0, W, H);
}
function drawShot(ctx, s) {
  ctx.save(); ctx.translate(s.x, s.y); ctx.rotate(s.a || 0);
  ctx.fillStyle = 'rgba(255,214,90,.35)'; A.rr(ctx, -9, -20, 18, 40, 9); ctx.fill();
  ctx.fillStyle = '#fff7c2'; A.rr(ctx, -5, -16, 10, 32, 5); ctx.fill();
  ctx.strokeStyle = '#ff9f1c'; ctx.lineWidth = 2.5; ctx.stroke();
  ctx.restore();
}
function drawBullet(ctx, b, t) {
  if (b.kind === 'drop') {
    ctx.save(); ctx.translate(b.x, b.y);
    ctx.beginPath(); ctx.moveTo(0, -16); ctx.bezierCurveTo(12, 0, 12, 12, 0, 12); ctx.bezierCurveTo(-12, 12, -12, 0, 0, -16);
    ctx.fillStyle = '#4aa8ff'; ctx.fill(); ctx.strokeStyle = OUT; ctx.lineWidth = 3; ctx.stroke();
    ctx.fillStyle = 'rgba(255,255,255,.8)'; ctx.beginPath(); ctx.arc(-3, 2, 3, 0, Math.PI * 2); ctx.fill();
    ctx.restore(); return;
  }
  const pul = 1 + Math.sin(t * 20 + b.x) * .08;
  ctx.beginPath(); ctx.arc(b.x, b.y, b.r * 1.6 * pul, 0, Math.PI * 2); ctx.fillStyle = 'rgba(255,79,154,.25)'; ctx.fill();
  ctx.beginPath(); ctx.arc(b.x, b.y, b.r, 0, Math.PI * 2); ctx.fillStyle = '#ff4f9a'; ctx.fill(); ctx.strokeStyle = OUT; ctx.lineWidth = 3; ctx.stroke();
  ctx.beginPath(); ctx.arc(b.x - 2, b.y - 2, b.r * .42, 0, Math.PI * 2); ctx.fillStyle = '#fff'; ctx.fill();
}
function drawHud(ctx, g) {
  if (!LAND) {                                          // в широком окне очки, залп и жизни — на боковых панелях
    A.text(ctx, Math.round(S.shown).toLocaleString('ru-RU'), 30, 56, { align: 'left', size: 46, color: '#fff', stroke: OUT, strokeW: 9 });
    for (let i = 0; i < 5; i++) {
      A.rr(ctx, 32 + i * 30, 92, 24, 12, 6);
      ctx.fillStyle = i < S.power ? '#ffd43b' : 'rgba(43,37,80,.35)'; ctx.fill();
      ctx.lineWidth = 3; ctx.strokeStyle = OUT; ctx.stroke();
    }
    for (let i = 0; i < Math.max(3, S.lives); i++) A.heart(ctx, W - 46 - i * 50, 58, 44, i < S.lives ? '#ff4f7b' : 'rgba(43,37,80,.3)', OUT);
  }
  if (S.boss && S.boss.y > 100) {
    const b = S.boss, k = Math.max(0, b.hp / b.maxhp);
    A.rr(ctx, 120, 128, W - 240, 20, 10); ctx.fillStyle = 'rgba(43,37,80,.5)'; ctx.fill();
    A.rr(ctx, 120, 128, (W - 240) * k, 20, 10); ctx.fillStyle = '#ff4f9a'; ctx.fill();
    A.rr(ctx, 120, 128, W - 240, 20, 10); ctx.lineWidth = 4; ctx.strokeStyle = OUT; ctx.stroke();
  }
  if (S.banner) {
    const t = S.banner.t, k = t < .35 ? A.ease.outBack(t / .35) : 1, a = t > 1.6 ? 1 - (t - 1.6) / .4 : 1;
    ctx.save(); ctx.globalAlpha = Math.max(0, a); ctx.translate(W / 2, H * .36); ctx.scale(k, k);
    A.text(ctx, S.banner.text, 0, 0, { size: 82, color: '#fff', stroke: OUT, strokeW: 14, weight: 900 });
    if (S.banner.sub) A.text(ctx, S.banner.sub, 0, 70, { size: 34, color: '#ffe066', stroke: OUT, strokeW: 9 });
    ctx.restore();
  }
}

function drawWorld(ctx, g) {
  const t = g.t, p = S.p;
  drawSky(ctx, g);
  for (const c of S.clouds) if (c.layer < 2) drawCloud(ctx, c);
  for (const it of S.items) drawItem(ctx, it, t);
  for (const e of S.foes) if (e.type !== 'boss') drawShadow(ctx, e.x, e.y, .5, e.r, e.r * .4);
  if (S.mode !== 'dead' && S.mode !== 'over') drawShadow(ctx, p.x, p.y, 1);
  for (const e of S.foes) {
    if (e.type === 'bee') drawBee(ctx, e, t);
    else if (e.type === 'plane') drawPlane(ctx, e.x, e.y, { c: GREEN, t, s: .72, rot: Math.atan2(e.vy, e.vx) + Math.PI / 2 });
    else if (e.type === 'grump') drawGrump(ctx, e, t);
    else if (e.type === 'balloon') drawBalloon(ctx, e, t);
    else if (e.type === 'boss') drawBoss(ctx, e, t);
    if (e.flash > 0 && e.type !== 'boss') { ctx.globalAlpha = .55; ctx.beginPath(); ctx.arc(e.x, e.y, e.r, 0, Math.PI * 2); ctx.fillStyle = '#fff'; ctx.fill(); ctx.globalAlpha = 1; }
  }
  for (const s of S.shots) drawShot(ctx, s);
  if (S.mode !== 'dead' && S.mode !== 'over' && !(S.inv > 0 && Math.floor(t * 14) % 2 === 0)) {
    drawPlane(ctx, p.x, p.y, { c: HERO, t, bank: p.bank });
    if (S.shield > 0) {
      ctx.beginPath(); ctx.arc(p.x, p.y, 72 + Math.sin(t * 8) * 3, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(95,211,255,.18)'; ctx.fill(); ctx.lineWidth = 4; ctx.strokeStyle = S.shield < 2 && Math.floor(t * 8) % 2 ? 'rgba(95,211,255,.3)' : '#5fd3ff'; ctx.stroke();
    }
  }
  for (const b of S.bullets) drawBullet(ctx, b, t);
  for (const c of S.clouds) if (c.layer === 2) drawCloud(ctx, c);
  if (S.mode !== 'title') drawHud(ctx, g);
}
/* ---------------- широкое окно ---------------- */
const LABEL = { size: 24, weight: 700, color: 'rgba(43,37,80,.62)' };
function plate(ctx, x, y, w, h) {                      // мягкая «облачная» плашка под надписями
  A.rr(ctx, x, y, w, h, 28); ctx.fillStyle = 'rgba(255,255,255,.58)'; ctx.fill();
  ctx.lineWidth = 3; ctx.strokeStyle = 'rgba(255,255,255,.9)'; ctx.stroke();
}
function fitText(ctx, str, x, y, o, maxW) {             // крупное число, которое не вылезет за плашку
  ctx.font = `${o.weight || 800} ${o.size}px ${A.FONT}`;
  const w = ctx.measureText(str).width, k = w > maxW ? maxW / w : 1;
  A.text(ctx, str, x, y, Object.assign({}, o, { size: o.size * k, strokeW: (o.strokeW || 9) * Math.max(.7, k) }));
}
function keycap(ctx, x, y, label) {
  const s = 46;
  A.rr(ctx, x - s / 2, y - s / 2 + 5, s, s, 12); ctx.fillStyle = 'rgba(43,37,80,.25)'; ctx.fill();
  A.rr(ctx, x - s / 2, y - s / 2, s, s, 12); ctx.fillStyle = '#fff'; ctx.fill(); ctx.lineWidth = 3; ctx.strokeStyle = OUT; ctx.stroke();
  A.text(ctx, label, x, y + 1, { size: 24, weight: 800, color: OUT });
}
function drawFriend(ctx, x, y, look, t) {             // облачко-болельщик: смотрит на самолёт
  ctx.save(); ctx.translate(x, y);
  ctx.fillStyle = '#cfe0f7'; for (const [ox, oy, r] of [[-44, 10, 38], [0, -12, 50], [44, 10, 38], [0, 20, 40]]) { ctx.beginPath(); ctx.arc(ox, oy + 8, r, 0, Math.PI * 2); ctx.fill(); }
  ctx.fillStyle = '#fff'; for (const [ox, oy, r] of [[-44, 10, 38], [0, -12, 50], [44, 10, 38], [0, 20, 40]]) { ctx.beginPath(); ctx.arc(ox, oy, r, 0, Math.PI * 2); ctx.fill(); }
  const blink = (t % 3.6) > 3.45;
  ctx.fillStyle = OUT;
  for (const ex of [-17, 17]) { ctx.beginPath(); if (blink) ctx.ellipse(ex + look, 4, 7, 1.6, 0, 0, Math.PI * 2); else ctx.ellipse(ex + look, 2, 6.5, 8.5, 0, 0, Math.PI * 2); ctx.fill(); }
  if (!blink) { ctx.fillStyle = '#fff'; for (const ex of [-17, 17]) { ctx.beginPath(); ctx.arc(ex + look - 2, -1, 2.4, 0, Math.PI * 2); ctx.fill(); } }
  ctx.fillStyle = 'rgba(255,143,177,.6)'; ctx.beginPath(); ctx.arc(-34 + look, 18, 8, 0, Math.PI * 2); ctx.arc(34 + look, 18, 8, 0, Math.PI * 2); ctx.fill();
  ctx.beginPath(); ctx.arc(look, 16, 9, .15 * Math.PI, .85 * Math.PI); ctx.lineWidth = 3.5; ctx.strokeStyle = OUT; ctx.lineCap = 'round'; ctx.stroke();
  ctx.restore();
}
function drawRainbow(ctx, x, y, t) {
  ctx.save(); ctx.lineCap = 'butt';
  ['#ff8fb1', '#ffb35c', '#ffe066', '#8ce99a', '#74c0fc', '#b197fc'].forEach((c, i) => {
    ctx.beginPath(); ctx.arc(x, y, 92 - i * 11, Math.PI, Math.PI * 2); ctx.lineWidth = 11.5; ctx.strokeStyle = c; ctx.globalAlpha = .82; ctx.stroke();
  });
  ctx.globalAlpha = 1;
  for (const sx of [-1, 1]) {
    const cx = x + sx * 64, cy = y + 4 + Math.sin(t * 1.4 + sx) * 3;
    ctx.fillStyle = '#cfe0f7'; for (const [ox, oy, r] of [[-26, 6, 22], [0, -6, 28], [26, 6, 22]]) { ctx.beginPath(); ctx.arc(cx + ox, cy + oy + 6, r, 0, Math.PI * 2); ctx.fill(); }
    ctx.fillStyle = '#fff'; for (const [ox, oy, r] of [[-26, 6, 22], [0, -6, 28], [26, 6, 22]]) { ctx.beginPath(); ctx.arc(cx + ox, cy + oy, r, 0, Math.PI * 2); ctx.fill(); }
  }
  ctx.restore();
}
function drawLand(ctx, g) {
  const t = g.t, p = S.p;
  // небо во всю ширину — то же, что в поле
  const gr = ctx.createLinearGradient(0, 0, 0, SH);
  gr.addColorStop(0, '#4fb8ff'); gr.addColorStop(.55, '#9fe0ff'); gr.addColorStop(1, '#fff0d6');
  ctx.fillStyle = gr; ctx.fillRect(0, 0, SW, SH);
  const sun = ctx.createRadialGradient(SW - 110, 70, 10, SW - 110, 70, 300);
  sun.addColorStop(0, 'rgba(255,255,240,.85)'); sun.addColorStop(.25, 'rgba(255,250,220,.35)'); sun.addColorStop(1, 'rgba(255,255,255,0)');
  ctx.fillStyle = sun; ctx.fillRect(0, 0, SW, SH);
  for (const c of SKY) drawCloud(ctx, c);
  // поле: мир во всю высоту; вокруг — то же небо, чуть в дымке, края поля — мягкий свет
  ctx.fillStyle = 'rgba(255,255,255,.2)'; ctx.fillRect(0, 0, SW, SH);
  for (const [x0, dir] of [[FX, -1], [FX + FW, 1]]) {
    const sh = ctx.createLinearGradient(x0, 0, x0 + dir * 26, 0);
    sh.addColorStop(0, 'rgba(27,58,107,.16)'); sh.addColorStop(1, 'rgba(27,58,107,0)');
    ctx.fillStyle = sh; ctx.fillRect(Math.min(x0, x0 + dir * 26), 0, 26, SH);
  }
  ctx.save(); ctx.beginPath(); ctx.rect(FX, FY, FW, FH); ctx.clip();
  ctx.translate(FX, FY); ctx.scale(FS, FS);
  drawWorld(ctx, g);
  if (g.fxWorld) g.fxWorld(ctx);
  ctx.restore();
  ctx.fillStyle = 'rgba(255,255,255,.85)'; ctx.fillRect(FX - 3, 0, 3, SH); ctx.fillRect(FX + FW, 0, 3, SH);
  // слева: очки, волна, залп, жизни
  const lx = LCX, px = lx - PW / 2;
  plate(ctx, px, 26, PW, S.shield > 0 ? 556 : 480);
  A.text(ctx, 'Очки', lx, 66, LABEL);
  fitText(ctx, Math.round(S.shown).toLocaleString('ru-RU'), lx, 122, { size: 64, color: '#fff', stroke: OUT, strokeW: 12, weight: 900 }, PW - 30);
  A.text(ctx, 'Волна ' + S.wave, lx, 190, { size: 32, color: '#ffe066', stroke: OUT, strokeW: 9 });
  A.text(ctx, 'Залп', lx, 262, LABEL);
  for (let i = 0; i < 5; i++) {
    A.rr(ctx, lx - 93 + i * 38, 288, 34, 20, 10);
    ctx.fillStyle = i < S.power ? '#ffd43b' : 'rgba(43,37,80,.25)'; ctx.fill();
    ctx.lineWidth = 3.5; ctx.strokeStyle = OUT; ctx.stroke();
  }
  A.text(ctx, 'Жизни', lx, 366, LABEL);
  const n = Math.max(3, S.lives), hs = Math.min(58, 160 / (n - 1));
  for (let i = 0; i < n; i++) A.heart(ctx, lx + (i - (n - 1) / 2) * hs, 414, n > 3 ? 38 : 52, i < S.lives ? '#ff4f7b' : 'rgba(43,37,80,.28)', OUT);
  if (S.shield > 0) {
    A.text(ctx, 'Щит', lx, 482, { size: 24, weight: 700, color: '#1f86c9' });
    A.rr(ctx, lx - 88, 506, 176, 20, 10); ctx.fillStyle = 'rgba(43,37,80,.25)'; ctx.fill();
    A.rr(ctx, lx - 88, 506, 176 * Math.min(1, S.shield / 10), 20, 10); ctx.fillStyle = '#5fd3ff'; ctx.fill();
    A.rr(ctx, lx - 88, 506, 176, 20, 10); ctx.lineWidth = 3.5; ctx.strokeStyle = OUT; ctx.stroke();
  }
  // справа: рекорд, управление
  const rx = RCX, rp = rx - PW / 2;
  plate(ctx, rp, 26, PW, 140);
  A.text(ctx, 'Рекорд', rx, 66, LABEL);
  fitText(ctx, (g.best || 0).toLocaleString('ru-RU'), rx, 116, { size: 48, color: '#fff', stroke: OUT, strokeW: 10, weight: 900 }, PW - 30);
  plate(ctx, rp, 186, PW, 318);
  A.text(ctx, 'Полёт', rx, 224, LABEL);
  if (A.isTouch) {
    A.text(ctx, 'ведите', rx, 282, { size: 26, weight: 800, color: OUT });
    A.text(ctx, 'пальцем', rx, 316, { size: 26, weight: 800, color: OUT });
    A.text(ctx, 'по экрану', rx, 362, { size: 22, weight: 600, color: 'rgba(43,37,80,.75)' });
  } else {
    keycap(ctx, rx, 268, '↑');
    keycap(ctx, rx - 54, 322, '←'); keycap(ctx, rx, 322, '↓'); keycap(ctx, rx + 54, 322, '→');
    A.text(ctx, 'или мышь', rx, 382, { size: 24, weight: 800, color: OUT });
  }
  ctx.fillStyle = 'rgba(43,37,80,.14)'; ctx.fillRect(rx - 70, 414, 140, 2);
  A.text(ctx, 'Стрельба', rx, 444, LABEL);
  A.text(ctx, 'автоматическая', rx, 476, { size: 21, weight: 700, color: OUT });
  // слева внизу — радуга на облачках, справа — облачко-болельщик: смотрит на самолёт
  drawRainbow(ctx, LCX, 668, t);
  const fx = rx, fy = 618 + Math.sin(t * 1.6) * 7;
  drawFriend(ctx, fx, fy, A.clamp((FX + p.x * FS - fx) / 300, -1, 1) * 5, t);
}
function draw(ctx, g) {
  if (LAND) drawLand(ctx, g); else drawWorld(ctx, g);
}

A.game({
  id: 'plane', tone: 'light', title: 'Небесный пилот', width: SW, height: SH, orientation: LAND ? 'landscape' : 'portrait', music: 'sky',
  help: {
    desktop: '<kbd>←</kbd> <kbd>→</kbd> <kbd>↑</kbd> <kbd>↓</kbd> или мышь — полёт · стрельба автоматическая · <kbd>P</kbd> пауза · <kbd>M</kbd> музыка',
    short: '<b>Стрелки</b> или <b>мышь</b> — полёт, пушки стреляют сами',
    touch: 'Ведите пальцем по экрану — самолёт полетит следом'
  },
  init(g) {
    if (LAND) {                                         // эффекты — в координатах мира: рисуем их внутри поля, надписи крупнее
      const fxDraw = g.fx.draw.bind(g.fx), fxText = g.fx.text.bind(g.fx);
      g.fx.draw = () => {}; g.fxWorld = fxDraw;
      g.fx.text = (x, y, str, o = {}) => fxText(x, y, str, Object.assign({}, o, { size: (o.size || 34) * 1.35, rise: (o.rise || 70) * 1.2 }));
    }
    S = fresh(); window.__planeS = () => S; titleScreen(g);
  },
  update, draw
});
})();
