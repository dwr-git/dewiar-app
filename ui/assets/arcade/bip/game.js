/* Бип — неоновые крыши. Платформер в гладкой векторной графике.

   УРОВНИ — просто строки текста (11 строк, ширина любая):
     #  крыша (земля)        =  блок
     -  тонкая платформа (на неё можно запрыгнуть снизу)
     ^  шипы                 *  кристалл
     e  глитч (враг)         S  пружина
     C  точка сохранения     E  портал выхода
     P  старт Бипа           .  пусто
   Прыжок берёт 2 клетки вверх и ~4 клетки в длину. */
(() => {
'use strict';
const A = Arcade;
const W = 1280, H = 720, T = 64, ROWS = 11, OY = 16;
const OUT = '#1d1838';

const LEVELS = [
    { name: 'Крыши на закате', map: [
      "",
      "",
      "............................................................*.*.*.*",
      "............................................................-------",
      "",
      "...............................................*",
      "............*........*.*.*.......*.............=...........................**...........*",
      ".....*.*.*...........-----......*.*...........==...........................--...........=......*.*",
      "..P.........=...............e...........^^...===..C.......S....e.....e..............e...=...e.......E",
      "################..##############...##################..###################....##########################",
      "################..##############...##################..###################....##########################"
    ]},
    { name: 'Неоновый рынок', map: [
      "",
      "",
      "...................................................................*.*.*.*",
      "..................................................................--------",
      "...............................****",
      "...................*...........----",
      ".................e........****.............**.......*..........................................*****.........****",
      ".............########.....----.............--.......=.................................#####...#######........----...........*",
      "..P...*.*.*..########............^^^..e.........C...=...e...e..S.^^^^^^^^^....e....e..#####...#######....^^........e..=..e.....E",
      "#####################...#################......############################################...######################################",
      "#####################...#################......############################################...######################################"
    ]},
    { name: 'Антенна над городом', map: [
      "",
      "",
      "................................................................*****",
      "...............................................................------",
      "................................**................................................................................................*..****",
      "............................*...--...*................................................................*.e......*..................=..----",
      "...............*........e...--......--......................................................e......*..----.*...--................==",
      "...........*.........######..............................*..............................########...--......--...................===",
      "..P..*.*.....#####...######^^^^^^^^^^..C....e.=.e.=..e......S...............e...e...^^..########...................C...^^^..e..====.......e..e....E",
      "##########...#####...###################################...###..........########################.................#####################################",
      "##########...#####...###################################...###..........########################.................#####################################"
    ]}
  ];

let S = null, G = null;

/* ---------------- уровень ---------------- */
function loadLevel(i) {
  const src = LEVELS[i].map;
  const L = { w: Math.max(...src.map((r) => r.length)), grid: [], gems: [], foes: [], springs: [], checks: [], exit: null, start: { c: 2, r: 8 } };
  for (let r = 0; r < ROWS; r++) {
    const row = src[r] || '';
    L.grid[r] = [];
    for (let c = 0; c < L.w; c++) {
      const ch = row[c] || '.';
      let tile = '.';
      if ('#=-^'.includes(ch)) tile = ch;
      else if (ch === '*') L.gems.push({ x: c * T + 32, y: r * T + 32, taken: false, ph: c * .7 });
      else if (ch === 'e') L.foes.push({ sx: c * T + 8, sy: r * T + 24, x: c * T + 8, y: r * T + 24, w: 48, h: 40, vx: -1.8, vy: 0, alive: true, dead: 0, ph: Math.random() * 6 });
      else if (ch === 'S') L.springs.push({ c, r, t: 0 });
      else if (ch === 'C') L.checks.push({ c, r, on: false });
      else if (ch === 'E') L.exit = { c, r };
      else if (ch === 'P') L.start = { c, r };
      L.grid[r][c] = tile;
    }
  }
  return L;
}
const tileAt = (c, r) => (c < 0 || c >= S.L.w ? '#' : r < 0 || r >= ROWS ? '.' : S.L.grid[r][c]);
const solid = (c, r) => { const t = tileAt(c, r); return t === '#' || t === '='; };
const oneway = (c, r) => tileAt(c, r) === '-';
const hit = (a, b) => a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y;

function moveX(e, dx) {
  e.x += dx;
  const top = Math.floor(e.y / T), bot = Math.floor((e.y + e.h - .01) / T);
  if (dx > 0) { const c = Math.floor((e.x + e.w - .01) / T); for (let r = top; r <= bot; r++) if (solid(c, r)) { e.x = c * T - e.w; return true; } }
  else if (dx < 0) { const c = Math.floor(e.x / T); for (let r = top; r <= bot; r++) if (solid(c, r)) { e.x = (c + 1) * T; return true; } }
  return false;
}
function moveY(e, dy) {
  const prevBottom = e.y + e.h;
  e.y += dy;
  const left = Math.floor(e.x / T), right = Math.floor((e.x + e.w - .01) / T);
  if (dy > 0) {
    const r = Math.floor((e.y + e.h - .01) / T);
    for (let c = left; c <= right; c++) if (solid(c, r) || (oneway(c, r) && prevBottom <= r * T + .01)) { e.y = r * T - e.h; return 'down'; }
  } else if (dy < 0) {
    const r = Math.floor(e.y / T);
    for (let c = left; c <= right; c++) if (solid(c, r)) { e.y = (r + 1) * T; return 'up'; }
  }
  return null;
}

/* ---------------- состояние ---------------- */
function newPlayer() { return { x: 0, y: 0, w: 40, h: 56, vx: 0, vy: 0, face: 1, ground: false, coyote: 0, buffer: 0, inv: 0, stun: 0, spring: false, anim: 0, prevBottom: 0, dying: false, hidden: false, sq: 0, blink: 0 }; }
function fresh() {
  return { mode: 'title', level: 0, score: 0, levelScore: 0, health: 3, gems: 0, gemsTotal: 0, camX: 0, L: null, cp: null, P: newPlayer(), banner: null, modeT: 0, bonus: 0, flash: 0 };
}
function setMode(m) { S.mode = m; S.modeT = 0; }
function spawn() {
  const p = S.P;
  Object.assign(p, { x: S.cp.c * T + 12, y: S.cp.r * T + 8, vx: 0, vy: 0, face: 1, ground: false, coyote: 0, buffer: 0, stun: 0, spring: false, dying: false, hidden: false, sq: 0 });
  p.prevBottom = p.y + p.h;
  for (const f of S.L.foes) if (f.alive) { f.x = f.sx; f.y = f.sy; f.vx = -1.8; f.vy = 0; }
}
const camTarget = () => A.clamp(S.P.x + S.P.w / 2 - W / 2 + S.P.face * 90, 0, S.L.w * T - W);

function startLevel(i) {
  S.level = i; S.levelScore = S.score; S.health = 3;
  S.L = loadLevel(i); S.cp = S.L.start; S.gems = 0; S.gemsTotal = S.L.gems.length;
  spawn(); S.camX = camTarget();
  setMode('play'); G.setPlaying(true); G.hideScreen(); G.playMusic(); G.fx.clear();
  S.banner = { text: 'Уровень ' + (i + 1), sub: LEVELS[i].name, t: 0 };
}
function titleScreen() {
  S.L = loadLevel(0); S.P.hidden = true; setMode('title'); G.setPlaying(false); G.stopMusic();
  G.screen({
    kicker: Arcade.framed ? 'Досуг' : 'Аркада', title: 'Бип',
    html: `<p>Маленький робот на неоновых крышах. Соберите кристаллы, прыгайте на глитчей и доберитесь до портала.</p>${G.best ? `<p class="record">Рекорд: ${G.best.toLocaleString('ru-RU')}</p>` : ''}`,
    button: 'Играть', onGo: () => { S.score = 0; startLevel(0); }
  });
}

/* ---------------- игра ---------------- */
function burstW(x, y, o) { G.fx.burst(x, y + OY, o); }
function hurt() {
  const p = S.P;
  if (p.inv > 0 || p.dying) return;
  S.health--; G.shake(12, .3); S.flash = .35;
  if (S.health <= 0) { die(); return; }
  G.sfx('hurt');
  p.inv = 1.5; p.vx = -p.face * 9.6; p.vy = -15.2; p.stun = 14; p.spring = true;
}
function die() {
  S.health = 0; G.sfx('lose'); G.stopMusic(); G.setPlaying(false);
  const p = S.P; p.dying = true; p.vy = -20; p.vx = 0;
  setMode('dying');
}
function pitFall() {
  S.health--; G.shake(10, .3); S.flash = .45;
  if (S.health <= 0) { S.health = 0; S.P.hidden = true; G.sfx('lose'); G.stopMusic(); G.setPlaying(false); setMode('dying'); return; }
  G.sfx('hurt'); spawn(); S.P.inv = 1.5; S.camX = camTarget();
}

function updateFoe(f, active) {
  if (!f.alive) { f.dead++; return; }
  if (Math.abs(f.x - S.camX - W / 2) > W * 1.2) return;
  f.vy = Math.min(f.vy + 1.28, 28);
  if (moveX(f, f.vx)) f.vx = -f.vx;
  const fr = moveY(f, f.vy);
  if (fr) f.vy = 0;
  if (fr === 'down') {
    const ax = f.vx > 0 ? f.x + f.w + 1 : f.x - 1, c = Math.floor(ax / T), feet = Math.floor((f.y + f.h + 1) / T), body = Math.floor((f.y + f.h - 1) / T);
    if (!(solid(c, feet) || oneway(c, feet)) || tileAt(c, body) === '^') f.vx = -f.vx;
  }
  void active;
}

function updatePlay(g) {
  const p = S.P, inp = g.input;
  const jumpHeld = inp.down('action') || inp.down('up');
  const jumpPressed = inp.pressed('action') || inp.pressed('up');
  const dir = p.stun > 0 ? 0 : (inp.down('right') ? 1 : 0) - (inp.down('left') ? 1 : 0);
  if (p.stun > 0) p.stun--;
  if (p.inv > 0) p.inv -= 1 / 60;
  const acc = p.ground ? 1.2 : .8, max = 8;
  if (dir) { p.vx += dir * acc; if (Math.abs(p.vx) > max) p.vx = Math.sign(p.vx) * max; p.face = dir; }
  else if (p.stun <= 0) { p.vx *= p.ground ? .7 : .93; if (Math.abs(p.vx) < .2) p.vx = 0; }
  if (jumpPressed) p.buffer = 7;
  p.coyote = p.ground ? 6 : p.coyote - 1;
  if (p.buffer > 0 && p.coyote > 0) {
    p.vy = -21.6; p.buffer = 0; p.coyote = 0; p.ground = false; p.spring = false; p.sq = -.22;
    g.sfx('jump'); burstW(p.x + p.w / 2 - S.camX, p.y + p.h, { n: 6, colors: ['#a9b4ff', '#e6e9ff'], speed: 160, size: 6, life: .35, angle: Math.PI / 2, spread: 1.4 });
  }
  if (p.buffer > 0) p.buffer--;
  if (!jumpHeld && p.vy < -8 && !p.spring) p.vy = -8;
  p.vy = Math.min(p.vy + 1.28, 28);
  if (p.vy >= 0) p.spring = false;

  p.prevBottom = p.y + p.h;
  if (moveX(p, p.vx)) p.vx = 0;
  const wasAir = !p.ground, fallSpeed = p.vy;
  const res = moveY(p, p.vy);
  p.ground = res === 'down';
  if (res) p.vy = 0;
  if (p.ground && wasAir) {
    p.sq = Math.min(.3, fallSpeed / 70);
    if (fallSpeed > 12) { g.sfx('land', { vol: .6 }); burstW(p.x + p.w / 2 - S.camX, p.y + p.h, { n: 8, colors: ['#a9b4ff', '#e6e9ff'], speed: 220, size: 6, life: .35, angle: -Math.PI / 2, spread: 1.5 }); }
  }
  p.sq *= .8;
  p.anim += Math.abs(p.vx) * .028;

  if (p.y > ROWS * T + 120) { pitFall(); return; }

  // шипы
  const c0 = Math.floor(p.x / T), c1 = Math.floor((p.x + p.w - .01) / T), r0 = Math.floor(p.y / T), r1 = Math.floor((p.y + p.h - .01) / T);
  for (let r = r0; r <= r1; r++) for (let c = c0; c <= c1; c++) {
    if (tileAt(c, r) === '^' && hit(p, { x: c * T + 8, y: r * T + 36, w: 48, h: 28 })) { hurt(); if (S.mode !== 'play') return; }
  }
  // пружины
  for (const s of S.L.springs) {
    const box = { x: s.c * T + 8, y: s.r * T + 28, w: 48, h: 36 };
    if (p.vy >= 0 && hit(p, box) && (p.prevBottom <= box.y + 32 || p.ground)) {
      p.vy = -33.6; p.spring = true; p.ground = false; p.y = box.y - p.h; s.t = 12; p.sq = -.35;
      g.sfx('bounce', { pitch: .7 }); g.sfx('jump', { pitch: 1.4 });
      burstW(s.c * T + 32 - S.camX, s.r * T + 30, { n: 12, colors: ['#f5a04a', '#ffe066', '#fff'], speed: 320, size: 7, life: .45 });
    }
    if (s.t > 0) s.t--;
  }
  // кристаллы
  for (const gm of S.L.gems) {
    if (!gm.taken && hit(p, { x: gm.x - 16, y: gm.y - 16, w: 32, h: 32 })) {
      gm.taken = true; S.gems++; S.score += 10; g.sfx('coin');
      burstW(gm.x - S.camX, gm.y, { n: 12, colors: ['#3bd5ff', '#c9f4ff', '#fff'], speed: 300, size: 6, shape: 'star', life: .5 });
      g.fx.text(gm.x - S.camX, gm.y + OY - 20, '+10', { color: '#7ee8ff', size: 30 });
    }
  }
  // точки сохранения
  for (const ch of S.L.checks) {
    if (!ch.on && hit(p, { x: ch.c * T, y: (ch.r - 1) * T, w: 64, h: 128 })) {
      S.L.checks.forEach((o) => (o.on = false)); ch.on = true; S.cp = { c: ch.c, r: ch.r }; g.sfx('power');
      burstW(ch.c * T + 40 - S.camX, ch.r * T - 20, { n: 18, colors: ['#47e6a0', '#c9f4ff', '#fff'], speed: 340, size: 7, life: .6 });
      g.fx.text(ch.c * T + 40 - S.camX, ch.r * T - 40 + OY, 'Сохранено', { color: '#7dffc4', size: 30 });
    }
  }
  // враги
  for (const f of S.L.foes) {
    updateFoe(f, true);
    if (!f.alive) continue;
    if (hit(p, f)) {
      if (p.vy > 0 && p.prevBottom <= f.y + 24) {
        f.alive = false; f.dead = 0; S.score += 50; g.sfx('bounce'); g.sfx('hit', { pitch: 1.4, vol: .6 }); g.shake(4, .12);
        p.vy = jumpHeld ? -24 : -16.8; p.spring = jumpHeld; p.sq = -.25;
        burstW(f.x + 24 - S.camX, f.y + 20, { n: 16, colors: ['#ff77c6', '#ffb3e1', '#fff', '#3bd5ff'], speed: 360, size: 8, life: .5 });
        g.fx.text(f.x + 24 - S.camX, f.y + OY - 10, '+50', { color: '#ff9ad5', size: 32 });
      } else { hurt(); if (S.mode !== 'play') return; }
    }
  }
  // портал
  const ex = S.L.exit;
  if (ex && hit(p, { x: ex.c * T + 8, y: (ex.r - 1) * T, w: 48, h: 128 })) {
    S.bonus = 100 + S.health * 50; S.score += S.bonus;
    g.sfx('win'); G.stopMusic(); setMode('portal'); g.setPlaying(false);
  }
  S.camX += (camTarget() - S.camX) * .1;
}

function update(g, dt) {
  S.modeT += dt;
  if (S.banner) { S.banner.t += dt; if (S.banner.t > 2.4) S.banner = null; }
  if (S.flash > 0) S.flash = Math.max(0, S.flash - dt * 1.8);
  if (S.P.blink > 0) S.P.blink -= dt; else if (Math.random() < .006) S.P.blink = .14;
  switch (S.mode) {
    case 'title':
      S.camX = (Math.sin(g.t / 9) * .5 + .5) * (S.L.w * T - W);
      for (const f of S.L.foes) updateFoe(f, false);
      {
        const p = S.P, px = S.camX + 470, c = Math.floor((px + 20) / T);
        let top = -1;
        for (let r = 3; r < ROWS; r++) { const tt = tileAt(c, r); if (tt === '#' || tt === '=' || tt === '-') { top = r; break; } }
        const dir = Math.cos(g.t / 9) >= 0 ? 1 : -1;
        if (top >= 0) { p.hidden = false; p.x = px; p.y = top * T - p.h; p.ground = true; p.vx = 4 * dir; p.face = dir; p.anim += .11; }
        else p.hidden = true;
      }
      break;
    case 'play': updatePlay(g); break;
    case 'dying': {
      const p = S.P;
      if (!p.hidden) { p.vy = Math.min(p.vy + 1, 24); p.y += p.vy; }
      if (S.modeT > 1.4) {
        setMode('over');
        g.screen({
          kicker: 'Уровень ' + (S.level + 1), title: 'Батарейка села',
          html: '<p>Уровень начнётся заново с полной батарейкой.</p>',
          button: 'Ещё раз', onGo: () => { S.score = S.levelScore; startLevel(S.level); },
          alt: { label: Arcade.framed ? 'К играм' : 'В аркаду', onGo: () => Arcade.home('../index.html') }
        });
      }
      break;
    }
    case 'portal': {
      const p = S.P, ex = S.L.exit, tx = ex.c * T + 12, ty = (ex.r - 1) * T + 36;
      p.x += (tx - p.x) * .12; p.y += (ty - p.y) * .12;
      if (S.modeT > .95) {
        const last = S.level === LEVELS.length - 1;
        if (last) {
          setMode('win');
          const rec = g.submit(S.score);
          g.screen({
            kicker: 'Финал', title: 'Город пройден!',
            html: `<div class="score">${S.score.toLocaleString('ru-RU')}</div><p>${rec ? '<span class="record">Новый рекорд!</span>' : `Рекорд: ${g.best.toLocaleString('ru-RU')}`}</p>`,
            button: 'Сыграть снова', onGo: () => { S.score = 0; startLevel(0); },
            alt: { label: Arcade.framed ? 'К играм' : 'В аркаду', onGo: () => Arcade.home('../index.html') }
          });
        } else {
          setMode('clear');
          g.screen({
            kicker: 'Уровень ' + (S.level + 1), title: 'Пройден!',
            html: `<p>Кристаллы: <b style="color:#7ee8ff">${S.gems} из ${S.gemsTotal}</b><br>Бонус за заряд: <b style="color:#ffe066">+${S.bonus}</b></p><div class="score">${S.score.toLocaleString('ru-RU')}</div>`,
            button: 'Дальше', onGo: () => startLevel(S.level + 1)
          });
        }
      }
      break;
    }
    default: break;
  }
}

/* ---------------- фон ---------------- */
let skyline = null;
function buildSkyline() {
  const R = 1.25, mk = (w, h) => { const c = document.createElement('canvas'); c.width = w * R; c.height = h * R; const x = c.getContext('2d'); x.scale(R, R); return [c, x]; };
  const rnd = mulberry(2024);
  const layer = (w, top0, top1, wmin, wmax, body, edge, winP, seedCols) => {
    const [c, x] = mk(w, 460);
    let px = 0;
    while (px < w) {
      const bw = wmin + rnd() * (wmax - wmin), top = top0 + rnd() * (top1 - top0);
      x.fillStyle = body; A.rr(x, px, top, bw, 470 - top, 6); x.fill();
      x.fillStyle = edge; x.fillRect(px + 4, top, bw - 8, 3);
      for (let wy = top + 18; wy < 450; wy += 22) for (let wx = px + 10; wx < px + bw - 16; wx += 18) {
        const q = rnd();
        if (q < winP) { x.fillStyle = seedCols[(rnd() * seedCols.length) | 0]; A.rr(x, wx, wy, 8, 11, 2); x.fill(); }
      }
      if (rnd() < .35) { const ax = px + 12 + rnd() * (bw - 24), ah = 18 + rnd() * 26; x.fillStyle = edge; x.fillRect(ax, top - ah, 3, ah); x.fillStyle = '#ff4d6d'; x.beginPath(); x.arc(ax + 1.5, top - ah, 4, 0, Math.PI * 2); x.fill(); }
      px += bw + 6 + rnd() * 18;
    }
    return { c, w };
  };
  skyline = {
    far: layer(1920, 120, 300, 70, 140, '#151233', '#2a2456', .22, ['rgba(120,140,255,.55)', 'rgba(255,119,198,.45)', 'rgba(255,224,102,.4)']),
    near: layer(1700, 180, 340, 90, 170, '#0e0c22', '#2a2350', .28, ['#2f6f8f', '#7a3f74', '#8a7a3a', '#3bd5ff', '#ff77c6', '#ffe066'])
  };
}
function mulberry(a) { return () => { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
const STARS = (() => { const r = mulberry(7); return Array.from({ length: 90 }, () => ({ x: r() * W, y: r() * 420, s: .6 + r() * 1.8, p: r() * 6.3, v: .5 + r() * 2 })); })();

function drawBackground(ctx, g) {
  const gr = ctx.createLinearGradient(0, 0, W, H);
  gr.addColorStop(0, '#0a0a0f'); gr.addColorStop(.5, '#1a1a2e'); gr.addColorStop(1, '#16213e');
  ctx.fillStyle = gr; ctx.fillRect(0, 0, W, H);
  const glow = (x, y, r, col) => { const rg = ctx.createRadialGradient(x, y, 0, x, y, r); rg.addColorStop(0, col); rg.addColorStop(1, 'rgba(0,0,0,0)'); ctx.fillStyle = rg; ctx.fillRect(0, 0, W, H); };
  glow(W * .4, H * .4, 620, 'rgba(120,219,255,.16)');
  glow(W * .8, H * .2, 620, 'rgba(255,119,198,.24)');
  glow(W * .2, H * .8, 620, 'rgba(120,119,198,.26)');
  for (const s of STARS) {
    const a = .35 + .65 * (Math.sin(g.t * s.v + s.p) * .5 + .5);
    ctx.globalAlpha = a; ctx.fillStyle = '#e8e6ff';
    ctx.beginPath(); ctx.arc(s.x, s.y, s.s, 0, Math.PI * 2); ctx.fill();
  }
  ctx.globalAlpha = 1;
  // планета
  const px = 1010 - S.camX * .02, py = 130;
  ctx.save(); ctx.translate(px, py); ctx.rotate(-.25);
  ctx.lineWidth = 7; ctx.strokeStyle = 'rgba(255,119,198,.75)';
  ctx.beginPath(); ctx.ellipse(0, 0, 98, 22, 0, Math.PI, Math.PI * 2); ctx.stroke();
  const pg = ctx.createRadialGradient(-20, -24, 6, 0, 0, 60);
  pg.addColorStop(0, '#c8c0ff'); pg.addColorStop(.5, '#7a6bd1'); pg.addColorStop(1, '#2c2a5e');
  ctx.beginPath(); ctx.arc(0, 0, 54, 0, Math.PI * 2); ctx.fillStyle = pg; ctx.fill();
  ctx.fillStyle = 'rgba(255,255,255,.12)'; ctx.beginPath(); ctx.ellipse(-6, -10, 40, 7, 0, 0, Math.PI * 2); ctx.fill();
  ctx.beginPath(); ctx.ellipse(0, 0, 98, 22, 0, 0, Math.PI); ctx.stroke();
  ctx.restore();
  // холмы
  const hx = S.camX * .12;
  ctx.beginPath(); ctx.moveTo(0, H);
  for (let x = 0; x <= W; x += 16) { const wx = x + hx; ctx.lineTo(x, 430 + Math.sin(wx / 210) * 34 + Math.sin(wx / 87 + 1) * 14); }
  ctx.lineTo(W, H); ctx.closePath();
  const hg = ctx.createLinearGradient(0, 380, 0, H); hg.addColorStop(0, '#2a2456'); hg.addColorStop(1, '#141233');
  ctx.fillStyle = hg; ctx.fill();
  if (!skyline) buildSkyline();
  const lay = (L, k, y) => { const off = -((S.camX * k) % L.w); for (let x = off; x < W; x += L.w) ctx.drawImage(L.c, x, y, L.w, 460); };
  lay(skyline.far, .22, 250);
  lay(skyline.near, .45, 300);
  const fog = ctx.createLinearGradient(0, 520, 0, H); fog.addColorStop(0, 'rgba(26,26,46,0)'); fog.addColorStop(1, 'rgba(60,40,110,.45)');
  ctx.fillStyle = fog; ctx.fillRect(0, 520, W, H - 520);
}

/* ---------------- тайлы ---------------- */
const hash = (a, b) => { let h = a * 374761393 + b * 668265263; h = (h ^ (h >>> 13)) * 1274126177; return ((h ^ (h >>> 16)) >>> 0) / 4294967296; };
function drawTiles(ctx, g) {
  const L = S.L, cam = S.camX;
  const c0 = Math.max(0, Math.floor(cam / T) - 1), c1 = Math.min(L.w - 1, Math.floor((cam + W) / T) + 1);
  // фасады
  for (let r = 0; r < ROWS; r++) for (let c = c0; c <= c1; c++) {
    const t = L.grid[r][c], x = c * T, y = r * T;
    if (t !== '#') continue;
    const top = tileAt(c, r - 1) !== '#';
    const fg = ctx.createLinearGradient(0, y, 0, y + T);
    fg.addColorStop(0, top ? '#1f2a52' : '#18213f'); fg.addColorStop(1, '#141b36');
    ctx.fillStyle = fg; ctx.fillRect(x, y, T + .5, T + .5);
    if (!top) {
      const h = hash(c, r);
      if (h < .45) {
        const col = h < .12 ? 'rgba(59,213,255,.75)' : h < .22 ? 'rgba(255,119,198,.7)' : h < .3 ? 'rgba(255,224,102,.6)' : 'rgba(120,130,200,.25)';
        ctx.fillStyle = col; A.rr(ctx, x + 14, y + 14, 14, 20, 3); ctx.fill(); A.rr(ctx, x + 36, y + 14, 14, 20, 3); ctx.fill();
      }
    } else {
      ctx.fillStyle = 'rgba(255,255,255,.04)'; ctx.fillRect(x, y + 18, T, 3);
    }
  }
  // неоновые кромки крыш
  for (let r = 0; r < ROWS; r++) {
    let run = -1;
    for (let c = c0; c <= c1 + 1; c++) {
      const isTop = c <= c1 && L.grid[r][c] === '#' && tileAt(c, r - 1) !== '#';
      if (isTop && run < 0) run = c;
      if (!isTop && run >= 0) {
        const x0 = run * T, x1 = c * T, y = r * T;
        ctx.fillStyle = 'rgba(59,213,255,.18)'; A.rr(ctx, x0 - 2, y - 6, x1 - x0 + 4, 16, 8); ctx.fill();
        ctx.fillStyle = '#3bd5ff'; A.rr(ctx, x0, y, x1 - x0, 6, 3); ctx.fill();
        ctx.fillStyle = '#c9f4ff'; ctx.fillRect(x0 + 6, y + 1, x1 - x0 - 12, 2);
        run = -1;
      }
    }
  }
  // боковые кромки
  for (let r = 0; r < ROWS; r++) for (let c = c0; c <= c1; c++) {
    if (L.grid[r][c] !== '#') continue;
    const x = c * T, y = r * T;
    if (tileAt(c - 1, r) !== '#' && tileAt(c - 1, r) !== '=') { ctx.fillStyle = 'rgba(102,126,234,.7)'; ctx.fillRect(x, y + 4, 3, T - 4); }
    if (tileAt(c + 1, r) !== '#' && tileAt(c + 1, r) !== '=') { ctx.fillStyle = 'rgba(0,0,0,.35)'; ctx.fillRect(x + T - 4, y + 4, 4, T - 4); }
  }
  for (let r = 0; r < ROWS; r++) for (let c = c0; c <= c1; c++) {
    const t = L.grid[r][c], x = c * T, y = r * T;
    if (t === '=') drawBlock(ctx, x, y, g.t);
    else if (t === '-') drawPlatform(ctx, x, y, tileAt(c - 1, r) === '-', tileAt(c + 1, r) === '-');
    else if (t === '^') drawSpikes(ctx, x, y);
  }
}
function drawBlock(ctx, x, y, t) {
  const gr = ctx.createLinearGradient(x, y, x, y + T);
  gr.addColorStop(0, '#4a50b0'); gr.addColorStop(1, '#2c3168');
  A.rr(ctx, x + 2, y + 2, T - 4, T - 4, 10); ctx.fillStyle = gr; ctx.fill();
  ctx.lineWidth = 2.5; ctx.strokeStyle = '#8f9bff'; ctx.stroke();
  ctx.fillStyle = 'rgba(255,255,255,.18)'; A.rr(ctx, x + 8, y + 6, T - 16, 6, 3); ctx.fill();
  const k = .75 + Math.sin(t * 3 + x * .01) * .25;
  ctx.save(); ctx.translate(x + 32, y + 34); ctx.rotate(Math.PI / 4);
  ctx.fillStyle = `rgba(255,119,198,${.25 * k})`; ctx.fillRect(-14, -14, 28, 28);
  ctx.fillStyle = '#ff77c6'; A.rr(ctx, -8, -8, 16, 16, 3); ctx.fill();
  ctx.fillStyle = '#ffd0ec'; ctx.fillRect(-5, -5, 5, 5);
  ctx.restore();
  ctx.fillStyle = '#b8c0ff';
  for (const [dx, dy] of [[10, 10], [54, 10], [10, 54], [54, 54]]) { ctx.beginPath(); ctx.arc(x + dx, y + dy, 2.5, 0, Math.PI * 2); ctx.fill(); }
}
function drawPlatform(ctx, x, y, joinL, joinR) {
  const x0 = x + (joinL ? 0 : 4), x1 = x + T - (joinR ? 0 : 4);
  ctx.fillStyle = 'rgba(169,180,255,.2)'; ctx.fillRect(x0, y - 4, x1 - x0, 24);
  const gr = ctx.createLinearGradient(0, y, 0, y + 16); gr.addColorStop(0, '#c9d0ff'); gr.addColorStop(.4, '#7c87f0'); gr.addColorStop(1, '#4b3f9a');
  ctx.fillStyle = gr; A.rr(ctx, x0, y, x1 - x0, 16, joinL && joinR ? 0 : 7); ctx.fill();
  ctx.fillStyle = '#2b2550'; ctx.fillRect(x + 12, y + 16, 5, 10); ctx.fillRect(x + T - 17, y + 16, 5, 10);
}
function drawSpikes(ctx, x, y) {
  for (let k = 0; k < 4; k++) {
    const sx = x + 2 + k * 15;
    ctx.beginPath(); ctx.moveTo(sx, y + T); ctx.lineTo(sx + 7.5, y + 30); ctx.lineTo(sx + 15, y + T); ctx.closePath();
    const gr = ctx.createLinearGradient(sx, 0, sx + 15, 0); gr.addColorStop(0, '#ffffff'); gr.addColorStop(.5, '#d6dbff'); gr.addColorStop(1, '#8a93d8');
    ctx.fillStyle = gr; ctx.fill();
    ctx.fillStyle = '#ff77c6'; ctx.beginPath(); ctx.moveTo(sx + 4.5, y + 39); ctx.lineTo(sx + 7.5, y + 30); ctx.lineTo(sx + 10.5, y + 39); ctx.closePath(); ctx.fill();
  }
  ctx.fillStyle = '#2c3168'; A.rr(ctx, x, y + T - 6, T, 6, 2); ctx.fill();
}
function drawSpring(ctx, s) {
  const x = s.c * T, y = s.r * T, comp = s.t > 0 ? Math.sin((s.t / 12) * Math.PI) : 0;
  const top = y + 26 + comp * 16;
  ctx.fillStyle = '#2c3168'; A.rr(ctx, x + 6, y + T - 12, T - 12, 12, 4); ctx.fill();
  ctx.lineWidth = 6; ctx.lineCap = 'round'; ctx.lineJoin = 'round';
  ctx.strokeStyle = '#f5a04a';
  ctx.beginPath();
  const n = 4, h = (y + T - 12) - (top + 10);
  for (let i = 0; i <= n; i++) { const yy = top + 10 + h * i / n, xx = x + 32 + (i % 2 ? 14 : -14); i ? ctx.lineTo(xx, yy) : ctx.moveTo(x + 32, yy); }
  ctx.stroke();
  const gr = ctx.createLinearGradient(0, top, 0, top + 12); gr.addColorStop(0, '#fff'); gr.addColorStop(1, '#a9b4ff');
  ctx.fillStyle = gr; A.rr(ctx, x + 6, top, T - 12, 12, 6); ctx.fill();
  ctx.fillStyle = '#ffe066'; ctx.beginPath(); ctx.arc(x + 32, top + 6, 3, 0, Math.PI * 2); ctx.fill();
}
function drawCheck(ctx, ch, t) {
  const x = ch.c * T, y = ch.r * T;
  ctx.fillStyle = '#2c3168'; A.rr(ctx, x + 6, y + T - 10, 34, 10, 4); ctx.fill();
  const pg = ctx.createLinearGradient(x + 18, 0, x + 26, 0); pg.addColorStop(0, '#e6e9ff'); pg.addColorStop(1, '#7c87f0');
  ctx.fillStyle = pg; A.rr(ctx, x + 18, y - 40, 7, T + 34, 3); ctx.fill();
  const col = ch.on ? '#47e6a0' : '#5a5f8f', col2 = ch.on ? '#a8ffd8' : '#7b80b0';
  ctx.beginPath(); ctx.moveTo(x + 25, y - 38);
  for (let i = 0; i <= 8; i++) { const fx = x + 25 + i * 5, fy = y - 38 + (ch.on ? Math.sin(t * 7 - i * .8) * 4 : i * .9); ctx.lineTo(fx, fy); }
  for (let i = 8; i >= 0; i--) { const fx = x + 25 + i * 5, fy = y - 12 + (ch.on ? Math.sin(t * 7 - i * .8) * 4 : i * .9); ctx.lineTo(fx, fy); }
  ctx.closePath();
  const fg = ctx.createLinearGradient(0, y - 38, 0, y - 12); fg.addColorStop(0, col2); fg.addColorStop(1, col);
  ctx.fillStyle = fg; ctx.fill();
  if (ch.on) { ctx.fillStyle = 'rgba(71,230,160,.18)'; ctx.beginPath(); ctx.arc(x + 45, y - 25, 34, 0, Math.PI * 2); ctx.fill(); }
  ctx.fillStyle = ch.on ? '#47e6a0' : '#7c87f0'; ctx.beginPath(); ctx.arc(x + 21.5, y - 44, 6, 0, Math.PI * 2); ctx.fill();
}
function drawPortal(ctx, ex, t) {
  const cx = ex.c * T + 32, cy = (ex.r - 1) * T + 64;
  const glow = ctx.createRadialGradient(cx, cy, 10, cx, cy, 110);
  glow.addColorStop(0, 'rgba(255,119,198,.35)'); glow.addColorStop(.5, 'rgba(102,126,234,.2)'); glow.addColorStop(1, 'rgba(0,0,0,0)');
  ctx.fillStyle = glow; ctx.fillRect(cx - 120, cy - 130, 240, 260);
  ctx.save(); ctx.translate(cx, cy);
  const inner = ctx.createRadialGradient(0, 0, 4, 0, 0, 56);
  inner.addColorStop(0, '#ffffff'); inner.addColorStop(.2, '#b9a6ff'); inner.addColorStop(.6, '#2a1f5c'); inner.addColorStop(1, '#0b0b14');
  ctx.beginPath(); ctx.ellipse(0, 0, 34, 58, 0, 0, Math.PI * 2); ctx.fillStyle = inner; ctx.fill();
  for (let i = 0; i < 14; i++) {
    const a = t * 2.2 + i * 2.4, rr = ((t * 30 + i * 9) % 50) / 50;
    ctx.globalAlpha = 1 - rr;
    ctx.fillStyle = i % 2 ? '#3bd5ff' : '#ff77c6';
    ctx.beginPath(); ctx.arc(Math.cos(a) * 30 * (1 - rr), Math.sin(a) * 52 * (1 - rr), 3, 0, Math.PI * 2); ctx.fill();
  }
  ctx.globalAlpha = 1;
  const cols = ['#3bd5ff', '#667eea', '#764ba2', '#ff77c6'];
  ctx.lineWidth = 9; ctx.lineCap = 'round';
  for (let i = 0; i < 8; i++) {
    const a0 = t * 2.5 + i * Math.PI / 4;
    ctx.strokeStyle = cols[i % 4];
    ctx.beginPath(); ctx.ellipse(0, 0, 36, 60, 0, a0, a0 + Math.PI / 4 - .12); ctx.stroke();
  }
  ctx.restore();
}
function drawGem(ctx, gm, t) {
  const bob = Math.sin(t * 2.6 + gm.ph) * 6, k = Math.cos(t * 2.8 + gm.ph);
  ctx.save(); ctx.translate(gm.x, gm.y + bob);
  const gl = ctx.createRadialGradient(0, 0, 2, 0, 0, 30); gl.addColorStop(0, 'rgba(59,213,255,.5)'); gl.addColorStop(1, 'rgba(59,213,255,0)');
  ctx.fillStyle = gl; ctx.fillRect(-30, -30, 60, 60);
  ctx.scale(Math.max(.18, Math.abs(k)), 1);
  ctx.beginPath(); ctx.moveTo(0, -20); ctx.lineTo(15, -5); ctx.lineTo(0, 20); ctx.lineTo(-15, -5); ctx.closePath();
  const gr = ctx.createLinearGradient(-15, -20, 15, 20); gr.addColorStop(0, '#e8fbff'); gr.addColorStop(.45, '#3bd5ff'); gr.addColorStop(1, '#2a6fd6');
  ctx.fillStyle = gr; ctx.fill();
  ctx.lineWidth = 2; ctx.strokeStyle = 'rgba(255,255,255,.8)'; ctx.stroke();
  ctx.beginPath(); ctx.moveTo(-15, -5); ctx.lineTo(15, -5); ctx.moveTo(0, -20); ctx.lineTo(k > 0 ? 5 : -5, -5); ctx.lineTo(0, 20); ctx.strokeStyle = 'rgba(255,255,255,.5)'; ctx.stroke();
  ctx.restore();
}
function drawGlitch(ctx, f, t) {
  const cx = f.x + 24, by = f.y + f.h;
  ctx.save(); ctx.translate(cx, by);
  let sx = 1 + Math.sin(t * 7 + f.ph) * .07, sy = 2 - sx, alpha = 1;
  if (!f.alive) { const k = Math.min(1, f.dead / 20); sx = 1 + k * .6; sy = .25; alpha = 1 - k; }
  ctx.globalAlpha = alpha;
  ctx.scale(sx * (f.vx > 0 ? -1 : 1), sy);
  const body = () => { ctx.beginPath(); ctx.moveTo(-30, 0); ctx.bezierCurveTo(-34, -52, 34, -52, 30, 0); ctx.quadraticCurveTo(0, 6, -30, 0); ctx.closePath(); };
  if ((t * 60 + f.ph * 40) % 140 < 6 && f.alive) { ctx.save(); ctx.translate(-5, 0); body(); ctx.fillStyle = 'rgba(59,213,255,.6)'; ctx.fill(); ctx.restore(); }
  body();
  const gr = ctx.createLinearGradient(0, -44, 0, 0); gr.addColorStop(0, '#ffb3e1'); gr.addColorStop(1, '#ff4fa8');
  ctx.fillStyle = gr; ctx.fill();
  ctx.lineWidth = 3; ctx.strokeStyle = '#a3236c'; ctx.stroke();
  ctx.fillStyle = 'rgba(255,255,255,.6)'; ctx.beginPath(); ctx.ellipse(-12, -30, 9, 5, -.5, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.ellipse(-10, -20, 7, 8, 0, 0, Math.PI * 2); ctx.ellipse(10, -20, 7, 8, 0, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = OUT; ctx.beginPath(); ctx.arc(-13, -19, 3.6, 0, Math.PI * 2); ctx.arc(7, -19, 3.6, 0, Math.PI * 2); ctx.fill();
  ctx.strokeStyle = OUT; ctx.lineWidth = 2.5; ctx.beginPath(); ctx.arc(-2, -9, 5, .15 * Math.PI, .85 * Math.PI); ctx.stroke();
  ctx.restore();
}
function drawBip(ctx, p, t, o = {}) {
  const cx = p.x + p.w / 2, by = p.y + p.h;
  const sq = p.sq || 0, sx = 1 + sq * .6, sy = 1 - sq;
  ctx.save(); ctx.translate(cx, by); ctx.scale(sx * (p.face < 0 ? -1 : 1), sy);
  if (o.spin) { ctx.translate(0, -40); ctx.rotate(o.spin); ctx.scale(o.k, o.k); ctx.translate(0, 40); }
  const moving = p.ground && Math.abs(p.vx) > 1, ph = p.anim * Math.PI;
  const air = !p.ground && !o.title;
  // ноги
  ctx.fillStyle = '#5b3f9e';
  for (const s of [-1, 1]) {
    const lift = moving ? Math.max(0, Math.sin(ph + (s > 0 ? Math.PI : 0))) * 7 : 0;
    const fx = s * 11 + (moving ? Math.cos(ph + (s > 0 ? Math.PI : 0)) * 6 : 0) + (air ? s * 3 : 0);
    ctx.beginPath(); ctx.ellipse(fx, -6 - lift - (air ? 4 : 0), 10, 7, 0, 0, Math.PI * 2); ctx.fill();
  }
  // руки
  const swing = moving ? Math.sin(ph) * .6 : air ? -1.6 : Math.sin(t * 2) * .1;
  ctx.fillStyle = '#7c87f0';
  for (const s of [-1, 1]) {
    ctx.save(); ctx.translate(s * 21, -28); ctx.rotate(s * (.3 + (air ? .9 : 0)) + (s > 0 ? swing : -swing) * .5);
    A.rr(ctx, -5, 0, 10, 18, 5); ctx.fill(); ctx.restore();
  }
  // тело
  const bg = ctx.createLinearGradient(0, -40, 0, -8); bg.addColorStop(0, '#8f9bff'); bg.addColorStop(1, '#5a52c9');
  A.rr(ctx, -21, -40, 42, 32, 12); ctx.fillStyle = bg; ctx.fill();
  ctx.fillStyle = 'rgba(255,255,255,.25)'; A.rr(ctx, -15, -37, 22, 6, 3); ctx.fill();
  const pulse = .6 + Math.sin(t * 5) * .4;
  ctx.fillStyle = `rgba(255,119,198,${.35 * pulse})`; ctx.beginPath(); ctx.arc(6, -23, 9, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = '#ff77c6'; ctx.beginPath(); ctx.arc(6, -23, 4.5, 0, Math.PI * 2); ctx.fill();
  // антенна
  ctx.strokeStyle = '#c9d0ff'; ctx.lineWidth = 3.5; ctx.lineCap = 'round';
  const sway = Math.sin(t * 4) * 3 - p.vx * .6;
  ctx.beginPath(); ctx.moveTo(0, -86); ctx.quadraticCurveTo(sway * .5, -96, sway, -104); ctx.stroke();
  const ag = ctx.createRadialGradient(sway, -106, 1, sway, -106, 18); ag.addColorStop(0, 'rgba(255,200,120,.9)'); ag.addColorStop(1, 'rgba(245,160,74,0)');
  ctx.fillStyle = ag; ctx.beginPath(); ctx.arc(sway, -106, 18, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = '#f5a04a'; ctx.beginPath(); ctx.arc(sway, -106, 6, 0, Math.PI * 2); ctx.fill();
  // голова
  const hg = ctx.createLinearGradient(0, -90, 0, -38); hg.addColorStop(0, '#ffffff'); hg.addColorStop(1, '#d9ddff');
  A.rr(ctx, -31, -90, 62, 52, 20); ctx.fillStyle = hg; ctx.fill();
  ctx.lineWidth = 3; ctx.strokeStyle = '#a9b4ff'; ctx.stroke();
  A.rr(ctx, -23, -81, 46, 32, 12); ctx.fillStyle = '#0b0b14'; ctx.fill();
  ctx.fillStyle = 'rgba(255,255,255,.12)'; A.rr(ctx, -19, -78, 20, 6, 3); ctx.fill();
  const blink = p.blink > 0, eh = blink ? 2.5 : 13, lx = 3 + (air ? 0 : 0);
  ctx.fillStyle = 'rgba(59,213,255,.3)';
  for (const ex of [-8 + lx, 9 + lx]) { A.rr(ctx, ex - 6, -65 - eh / 2 - 3, 12, eh + 6, 6); ctx.fill(); }
  ctx.fillStyle = '#3bd5ff';
  for (const ex of [-8 + lx, 9 + lx]) { A.rr(ctx, ex - 3.5, -65 - eh / 2, 7, eh, 3.5); ctx.fill(); }
  ctx.fillStyle = 'rgba(255,119,198,.45)'; ctx.beginPath(); ctx.ellipse(-24, -52, 4, 2.5, 0, 0, Math.PI * 2); ctx.ellipse(25, -52, 4, 2.5, 0, 0, Math.PI * 2); ctx.fill();
  ctx.restore();
}

/* ---------------- HUD ---------------- */
function drawHud(ctx) {
  for (let i = 0; i < 3; i++) A.heart(ctx, 44 + i * 46, 44, 40, i < S.health ? '#ff4f7b' : 'rgba(120,120,170,.35)', OUT);
  ctx.save(); ctx.translate(196, 44); ctx.beginPath(); ctx.moveTo(0, -16); ctx.lineTo(12, -4); ctx.lineTo(0, 16); ctx.lineTo(-12, -4); ctx.closePath();
  ctx.fillStyle = '#3bd5ff'; ctx.fill(); ctx.lineWidth = 3; ctx.strokeStyle = OUT; ctx.stroke(); ctx.restore();
  A.text(ctx, `${S.gems}/${S.gemsTotal}`, 220, 46, { align: 'left', size: 32, color: '#c9f4ff', stroke: OUT, strokeW: 7 });
  A.text(ctx, S.score.toLocaleString('ru-RU'), W - 32, 46, { align: 'right', size: 38, color: '#fff', stroke: OUT, strokeW: 8 });
  A.text(ctx, `Уровень ${S.level + 1}`, W / 2, 44, { size: 24, weight: 700, color: '#ffb3e1', stroke: OUT, strokeW: 6 });
  if (S.banner) {
    const t = S.banner.t, k = t < .35 ? A.ease.outBack(t / .35) : 1, a = t > 1.9 ? 1 - (t - 1.9) / .5 : 1;
    ctx.save(); ctx.globalAlpha = Math.max(0, a); ctx.translate(W / 2, H * .34); ctx.scale(k, k);
    A.text(ctx, S.banner.text, 0, 0, { size: 72, weight: 900, color: '#fff', stroke: OUT, strokeW: 12 });
    A.text(ctx, S.banner.sub, 0, 62, { size: 32, color: '#7ee8ff', stroke: OUT, strokeW: 8 });
    ctx.restore();
  }
}

function draw(ctx, g) {
  const t = g.t;
  drawBackground(ctx, g);
  ctx.save();
  ctx.translate(-Math.round(S.camX * 10) / 10, OY);
  drawTiles(ctx, g);
  for (const s of S.L.springs) drawSpring(ctx, s);
  for (const ch of S.L.checks) drawCheck(ctx, ch, t);
  if (S.L.exit) drawPortal(ctx, S.L.exit, t);
  for (const gm of S.L.gems) if (!gm.taken) drawGem(ctx, gm, t);
  for (const f of S.L.foes) if (f.alive || f.dead < 22) drawGlitch(ctx, f, t);
  const p = S.P;
  if (!p.hidden && !(p.inv > 0 && Math.floor(t * 12) % 2 === 0 && S.mode === 'play')) {
    if (S.mode === 'portal') { const k = Math.max(.05, 1 - S.modeT / .95); drawBip(ctx, p, t, { spin: S.modeT * 9, k }); }
    else drawBip(ctx, p, t, { title: S.mode === 'title' });
  }
  ctx.restore();
  if (S.mode !== 'title') drawHud(ctx);
  if (S.flash > 0) { ctx.fillStyle = `rgba(255,77,109,${S.flash * .6})`; ctx.fillRect(0, 0, W, H); }
}

A.game({
  id: 'bip', tone: 'dark', title: 'Бип', width: W, height: H, orientation: 'landscape', music: 'neon',
  help: {
    desktop: '<kbd>←</kbd> <kbd>→</kbd> бег · <kbd>Пробел</kbd> или <kbd>↑</kbd> прыжок · <kbd>P</kbd> пауза · <kbd>M</kbd> музыка',
    short: '<b>Стрелки</b> — бег, <b>Пробел</b> — прыжок',
    touch: 'Кнопки ◀ ▶ — бег, «Прыжок» — прыжок. Держите телефон горизонтально.'
  },
  touch: { left: [{ id: 'left', label: '◀', aria: 'Влево' }, { id: 'right', label: '▶', aria: 'Вправо' }], right: [{ id: 'action', label: '▲', aria: 'Прыжок', big: true }] },
  init(g) { G = g; S = fresh(); titleScreen(); g.showPad(false); },
  update, draw
});
window.__bip = { get S() { return S; }, startLevel: (i) => startLevel(i) };
})();
