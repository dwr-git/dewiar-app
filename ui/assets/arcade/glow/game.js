/* «Огонёк» — маленькая сказка без слов (24.10, владелец: «нравятся игры типа Samorost — очень атмосферные…
   это должно круто выглядеть, красиво, атмосферно»). Силуэты на светящемся небе, туман, светлячки; три сцены —
   «Пруд», «Старое дерево», «Дом». Огонёк потерял свет: соберите девять светлячков и проводите его домой.
   Всё рисуется кодом (без картинок): дальние слои — заранее в свои холсты (по масштабу экрана), живое — каждый кадр.
   Касание по живому — действие; по земле — Огонёк идёт туда. Стрелки и Enter — выбрать и нажать.
   Звук — свой: тихий фон (пэд и сверчки, кнопка музыки) и отклики предметов. */
(() => {
'use strict';
const A = Arcade, SND = A.sound;
// Форма окна (24.10, владелец: «на компьютере игра должна занимать ширину блока»): широкое окно — сцены 1280×720,
// узкое (телефон) — 720×1280. Раскладка каждой сцены — своя для обеих форм (K в сценах).
const LAND = (() => { try { return innerWidth > (innerHeight - 110) * 1.15; } catch (e) { return false; } })();
const W = LAND ? 1280 : 720, H = LAND ? 720 : 1280, TAU = Math.PI * 2;
const clamp = (v, a, b) => (v < a ? a : v > b ? b : v), lerp = (a, b, t) => a + (b - a) * t;
const ease = (t) => (t < .5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2), eOut = (t) => 1 - (1 - t) ** 3;
const rgb = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
const mix = (a, b, t) => { const x = rgb(a), y = rgb(b); return 'rgb(' + x.map((v, i) => Math.round(v + (y[i] - v) * t)).join(',') + ')'; };
const rgba = (h, a) => 'rgba(' + rgb(h).join(',') + ',' + a + ')';
function rng(seed) { return () => { seed = (seed + 0x6D2B79F5) | 0; let t = Math.imul(seed ^ (seed >>> 15), 1 | seed); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
const GOLD = '#ffd27a', EYE = '#f4f0dc', WARM = '#ffb24d';

/* ---------------- палитры сцен ---------------- */
const PAL = [
  { name: 'Пруд', sky: [[0, '#151d38'], [.42, '#34416a'], [.7, '#8a7a9c'], [1, '#e7ad86']], hor: 800, haze: '#d9a58a', ink: '#0a0d15', chord: [196, 247, 294, 370, 440] },
  { name: 'Старое дерево', sky: [[0, '#0c1229'], [.5, '#22325a'], [.85, '#577191'], [1, '#93aec0']], hor: 1000, haze: '#8fa9bd', ink: '#070a12', chord: [174.6, 220, 261.6, 329.6, 392] },
  { name: 'Дом', sky: [[0, '#05081a'], [.45, '#121a3d'], [.8, '#35336a'], [1, '#9a78a6']], hor: 960, haze: '#9a7aa8', ink: '#05070e', chord: [196, 246.9, 293.7, 392, 493.9] },
];

/* ---------------- общее состояние ---------------- */
let G = null;
const hero = { x: -40, y: 950, tx: 0, face: 1, walking: false, ph: 0, blink: 3, then: null, think: 0, ride: false, alpha: 1, puff: 0, look: 0, step: 0 };
function newGame(mode) {
  G = { mode, si: 0, sc: null, swarm: [], flies: [], parts: [], fade: 1, fadeDir: -1, fadeThen: null, t: 0, idle: 0, kb: false, focus: 0,
    title: { text: '', t: 9 }, time: 0, count: 0, busy: false, ambT: 1, crT: 2, cache: {}, rings: [], cap: null, sparkT: 0 };
  Object.assign(hero, { x: -40, tx: -40, face: 1, walking: false, then: null, think: 0, ride: false, alpha: mode === 'title' ? 0 : 1, puff: 0 });
  enter(0);
}
function enter(i) {
  hero.ride = false; hero.walking = false; hero.then = null; hero.think = 0; if (G.mode === 'play') hero.alpha = 1;
  G.si = i; G.sc = SCENES[i](); G.flies = []; G.parts = []; G.rings = []; G.idle = 0; G.busy = false; G.focus = 0;
  G.sc.start();
  hero.y = G.sc.ground(hero.x);
  if (G.mode === 'play') G.title = { text: G.sc.pal.name, t: 0 };
}
function goScene(i) {
  G.busy = true; G.fadeDir = 1;
  G.fadeThen = () => { const sw = G.swarm; enter(i); G.swarm = sw; G.fadeDir = -1; };
}

/* ---------------- звук ---------------- */
const now = () => SND.now();
const snd = {
  chime(i) { if (!SND.ctx) return; const t = now(), f = [523.3, 587.3, 659.3, 784, 880, 1046.5, 1174.7, 1318.5, 1568][clamp(i, 0, 8)];
    SND.tone(f, t, 1.6, .07, 'sine'); SND.tone(f * 2, t, .7, .018, 'triangle'); SND.tone(f * 1.5, t + .09, 1.2, .025, 'sine'); },
  bell() { if (!SND.ctx) return; const t = now(); [[1318.5, .06, 2.2], [1975.5, .03, 1.4], [2637, .02, .9], [3520, .01, .5]].forEach(([f, v, d]) => SND.tone(f, t, d, v, 'sine'));
    SND.tone(1318.5 * 1.003, t + .25, 2, .03, 'sine'); },
  hoot() { if (!SND.ctx) return; const t = now(); SND.tone(392, t, .4, .1, 'sine', null, 360, .06); SND.tone(330, t + .5, .7, .1, 'sine', null, 300, .06); SND.tone(330, t + 1.35, .5, .05, 'sine', null, 296, .06); },
  splash() { if (!SND.ctx) return; const t = now(); SND.hiss(t, .5, .12, 'lowpass', 1300); SND.tone(320, t, .3, .1, 'sine', null, 110); SND.hiss(t + .08, .9, .05, 'bandpass', 2600); },
  rustle() { if (!SND.ctx) return; const t = now(); for (let k = 0; k < 4; k++) SND.hiss(t + k * .07, .12, .05, 'highpass', 2600 + k * 300); },
  croak() { if (!SND.ctx) return; const t = now(); SND.tone(130, t, .16, .09, 'triangle', null, 96); SND.tone(140, t + .22, .2, .09, 'triangle', null, 92); },
  snore() { if (!SND.ctx) return; const t = now(); SND.hiss(t, .8, .035, 'lowpass', 420); SND.tone(80, t, .7, .03, 'sine', null, 70, .3); },
  creak() { if (!SND.ctx) return; const t = now(); SND.tone(140, t, .5, .025, 'sawtooth', null, 95, .05); },
  thud() { if (!SND.ctx) return; const t = now(); SND.tone(120, t, .35, .25, 'sine', null, 45); SND.hiss(t, .15, .08, 'lowpass', 700); },
  snap() { if (!SND.ctx) return; const t = now(); for (let k = 0; k < 6; k++) SND.tone(2400 + Math.random() * 1600, t + k * .035, .05, .02, 'sine'); },
  whoosh() { if (!SND.ctx) return; const t = now(); SND.hiss(t, 1.2, .06, 'bandpass', 1500); SND.hiss(t + .1, 1.5, .03, 'bandpass', 3200); },
  flutter() { if (!SND.ctx) return; const t = now(); for (let k = 0; k < 10; k++) SND.hiss(t + k * .05, .04, .03, 'bandpass', 900); },
  nope() { if (!SND.ctx) return; const t = now(); SND.tone(330, t, .18, .05, 'sine', null, 290); SND.tone(262, t + .16, .25, .05, 'sine', null, 240); },
  step() { if (!SND.ctx) return; SND.hiss(now(), .05, .02, 'lowpass', 500); },
  bloom() { if (!SND.ctx) return; const t = now(); [392, 493.9, 587.3, 784, 987.8, 1174.7, 1568].forEach((f, k) => { SND.tone(f, t + k * .11, 3, .05, 'sine'); SND.tone(f * 2, t + k * .11, 1.2, .012, 'triangle'); }); },
};
function ambience(dt) {
  if (!SND.ctx || !SND.musicOn) return;
  G.ambT -= dt; G.crT -= dt;
  const ch = G.sc.pal.chord;
  if (G.ambT <= 0) {
    G.ambT = 2.6 + Math.random() * 1.8;
    const f = A.pick(ch), t = now();
    SND.tone(f, t, 7.5, .03, 'sine', SND.mus, null, 2.4);
    SND.tone(f * 2.003, t + .2, 6, .008, 'triangle', SND.mus, null, 2.6);
    if (Math.random() < .35) SND.tone(A.pick(ch) * 4, t + 1.5, 2.2, .006, 'sine', SND.mus);       // далёкая искра
  }
  if (G.crT <= 0 && G.si !== 1) {
    G.crT = 1.6 + Math.random() * 3.5;
    const t = now(), f = 4300 + Math.random() * 600;
    for (let k = 0; k < 3; k++) SND.tone(f, t + k * .065, .035, .006, 'sine', SND.mus);
  }
  if (G.crT <= 0 && G.si === 1) { G.crT = 3 + Math.random() * 4; SND.hiss(now(), 2.4, .012, 'bandpass', 500 + Math.random() * 300, SND.mus); }
}

/* ---------------- рисование: общее ---------------- */
function layer(i, k, fn, g) {     // холст слоя по масштабу экрана — рисуется один раз
  const sc = g.scale, key = i + ':' + k;
  let c = G.cache[key];
  if (!c || c._s !== sc) {
    c = document.createElement('canvas'); c.width = Math.round(W * sc); c.height = Math.round(H * sc); c._s = sc;
    const x = c.getContext('2d'); x.scale(sc, sc); fn(x); G.cache[key] = c;
  }
  return c;
}
function sky(c, P, stars) {
  const gr = c.createLinearGradient(0, 0, 0, P.hor); P.sky.forEach(([s, col]) => gr.addColorStop(s, col));
  c.fillStyle = gr; c.fillRect(0, 0, W, H);
  if (stars) { const r = rng(stars); for (let i = 0; i < 140; i++) { const y = r() * P.hor * .75, a = (1 - y / (P.hor * .75)) * .55 * r();
    c.fillStyle = 'rgba(255,248,230,' + a.toFixed(3) + ')'; c.beginPath(); c.arc(r() * W, y, r() < .1 ? 1.5 : .8, 0, TAU); c.fill(); } }
}
function ridge(c, r, y0, amp, color, trees = 0) {
  const ph = [r() * 6, r() * 6, r() * 6];
  const Y = (x) => y0 + Math.sin(x * .0055 + ph[0]) * amp + Math.sin(x * .016 + ph[1]) * amp * .45 + Math.sin(x * .047 + ph[2]) * amp * .12;
  c.fillStyle = color; c.beginPath(); c.moveTo(-10, H + 10);
  for (let x = -10; x <= W + 10; x += 6) c.lineTo(x, Y(x));
  c.lineTo(W + 10, H + 10); c.closePath(); c.fill();
  if (trees) for (let x = -20; x < W + 20; x += trees * (.5 + r())) {      // ели на гребне
    const h = trees * (1.4 + r() * 1.6), w = h * .3, y = Y(x) + 3;
    c.beginPath(); c.moveTo(x, y - h);
    for (let k = 1; k <= 4; k++) { c.lineTo(x + w * k / 4, y - h + h * k / 4); if (k < 4) c.lineTo(x + w * k / 4 * .35, y - h + h * k / 4 - h * .04); }
    for (let k = 4; k >= 1; k--) { if (k < 4) c.lineTo(x - w * k / 4 * .35, y - h + h * k / 4 - h * .04); c.lineTo(x - w * k / 4, y - h + h * k / 4); }
    c.closePath(); c.fill();
  }
  return Y;
}
function blade(c, x0, y0, x1, y1, bend, w) {      // сужающийся стебель/лист
  const cx = (x0 + x1) / 2 + bend, cy = (y0 + y1) / 2, L = [], R = [];
  for (let i = 0; i <= 12; i++) {
    const t = i / 12, u = 1 - t;
    const x = u * u * x0 + 2 * u * t * cx + t * t * x1, y = u * u * y0 + 2 * u * t * cy + t * t * y1;
    const dx = 2 * u * (cx - x0) + 2 * t * (x1 - cx), dy = 2 * u * (cy - y0) + 2 * t * (y1 - cy), l = Math.hypot(dx, dy) || 1, ww = w * (1 - t * .92) / 2;
    L.push([x - dy / l * ww, y + dx / l * ww]); R.push([x + dy / l * ww, y - dx / l * ww]);
  }
  c.beginPath(); c.moveTo(L[0][0], L[0][1]); L.forEach((p) => c.lineTo(p[0], p[1])); for (let i = R.length - 1; i >= 0; i--) c.lineTo(R[i][0], R[i][1]); c.closePath(); c.fill();
}
function grass(c, r, x0, x1, Y, color, n, hmax) {
  c.fillStyle = color;
  for (let i = 0; i < n; i++) { const x = lerp(x0, x1, r()), y = Y(x) + 3, h = 6 + r() * hmax; blade(c, x, y, x + (r() - .5) * h * .8, y - h, (r() - .5) * 8, 2.6 + r() * 2); }
}
function glow(c, x, y, r, col, a) {
  if (a <= 0.003) return;
  const gr = c.createRadialGradient(x, y, 0, x, y, r); gr.addColorStop(0, rgba(col, a)); gr.addColorStop(.35, rgba(col, a * .35)); gr.addColorStop(1, rgba(col, 0));
  c.save(); c.globalCompositeOperation = 'lighter'; c.fillStyle = gr; c.fillRect(x - r, y - r, r * 2, r * 2); c.restore();
}
function ell(c, x, y, rx, ry, rot = 0) { c.beginPath(); c.ellipse(x, y, Math.max(.1, rx), Math.max(.1, ry), rot, 0, TAU); }
function fog(c, P, y0, y1, n, a, seed) {
  const r = rng(seed);
  for (let i = 0; i < n; i++) {
    const w = 260 + r() * 300, sp = 6 + r() * 10, y = lerp(y0, y1, r()), x = ((r() * (W + w) + G.t * sp * (r() < .5 ? 1 : -1)) % (W + w * 2) + W + w * 2) % (W + w * 2) - w;
    c.save(); c.translate(x, y); c.scale(1, .22);
    const gr = c.createRadialGradient(0, 0, 0, 0, 0, w); gr.addColorStop(0, rgba(P.haze, a)); gr.addColorStop(1, rgba(P.haze, 0));
    c.fillStyle = gr; c.fillRect(-w, -w, w * 2, w * 2); c.restore();
  }
}
let GRAIN = null;
function finishFrame(c, g) {
  if (!GRAIN) { const n = document.createElement('canvas'); n.width = n.height = 128; const x = n.getContext('2d'), d = x.createImageData(128, 128);
    for (let i = 0; i < d.data.length; i += 4) { const v = Math.random() * 255; d.data[i] = d.data[i + 1] = d.data[i + 2] = v; d.data[i + 3] = 22; }
    x.putImageData(d, 0, 0); GRAIN = c.createPattern(n, 'repeat'); }
  c.save(); c.globalCompositeOperation = 'overlay'; c.fillStyle = GRAIN; c.translate((G.t * 37 % 128) | 0, (G.t * 53 % 128) | 0); c.fillRect(-128, -128, W + 256, H + 256); c.restore();
  const v = c.createRadialGradient(W / 2, H * .48, H * .3, W / 2, H * .5, H * .78); v.addColorStop(0, 'rgba(0,0,0,0)'); v.addColorStop(1, 'rgba(0,0,0,.6)');
  c.fillStyle = v; c.fillRect(0, 0, W, H);
}

/* ---------------- Огонёк ---------------- */
const SPEED = 170;
function walkTo(x, then) {
  const sc = G.sc; const tx = clamp(x, sc.minX(), sc.maxX());
  hero.tx = tx; hero.then = then || null;
  if (Math.abs(tx - hero.x) < 3) { hero.walking = false; const f = hero.then; hero.then = null; if (f) f(); }
  else hero.walking = true;
  return tx === x;
}
function bulb() { return [hero.x + 7 * hero.face, hero.y - 80]; }
function updHero(dt) {
  hero.blink -= dt; if (hero.blink < -.12) hero.blink = 2 + Math.random() * 3.5;
  if (hero.think > 0) hero.think -= dt; if (hero.puff > 0) hero.puff -= dt;
  if (hero.ride) return;
  if (hero.walking) {
    const d = hero.tx - hero.x, s = Math.sign(d);
    hero.face = s; hero.x += s * Math.min(Math.abs(d), SPEED * dt); hero.ph += dt * 10;
    hero.step -= dt; if (hero.step <= 0) { hero.step = .31; snd.step(); }
    if (Math.abs(hero.tx - hero.x) < .5) { hero.x = hero.tx; hero.walking = false; const f = hero.then; hero.then = null; if (f) f(); }
  }
  hero.y = G.sc.ground(hero.x);
}
function drawHero(c, P) {
  if (hero.alpha <= 0) return;
  const t = G.t, x = hero.x, y = hero.y, f = hero.face;
  const bob = hero.walking ? -Math.abs(Math.sin(hero.ph)) * 5 : Math.sin(t * 2.1) * 1.3;
  c.save(); c.globalAlpha = hero.alpha;
  c.strokeStyle = P.ink; c.fillStyle = P.ink; c.lineCap = 'round'; c.lineWidth = 5;
  const lg = hero.walking ? Math.sin(hero.ph) * 9 : 0;
  if (!hero.ride) { c.beginPath(); c.moveTo(x - 8, y - 16 + bob); c.lineTo(x - 8 - lg, y); c.moveTo(x + 8, y - 16 + bob); c.lineTo(x + 8 + lg, y); c.stroke(); }
  // тело — круглое, чуть приплюснутое
  ell(c, x, y - 34 + bob, 24, 22); c.fill();
  // шапочка-хохолок и усик со «светом»
  c.lineWidth = 3; c.beginPath(); c.moveTo(x + 3 * f, y - 54 + bob); c.quadraticCurveTo(x + 16 * f, y - 70 + bob, x + 7 * f + Math.sin(t * 2.6) * 2, y - 80 + bob); c.stroke();
  const [bx, by] = [x + 7 * f + Math.sin(t * 2.6) * 2, y - 80 + bob];
  ell(c, bx, by, 4.5, 4.5); c.fill();
  const lit = .12 + .88 * G.count / 9;
  glow(c, bx, by, 18 + 30 * lit, GOLD, .25 + .55 * lit);
  c.fillStyle = mix('#3a3324', GOLD, lit); ell(c, bx, by, 3.2, 3.2); c.fill();
  // глаза
  const open = hero.blink < 0 ? .12 : 1, ex = x + 6 * f, ey = y - 38 + bob;
  c.fillStyle = EYE;
  ell(c, ex - 8, ey, 6.2, 7.5 * open); c.fill(); ell(c, ex + 8, ey, 6.2, 7.5 * open); c.fill();
  if (open > .5) { c.fillStyle = P.ink; const lx = f * 2 + hero.look; ell(c, ex - 8 + lx, ey + 1, 2.8, 3.4); c.fill(); ell(c, ex + 8 + lx, ey + 1, 2.8, 3.4); c.fill(); }
  // задумался: три точки
  if (hero.think > 0) { const a = Math.min(1, hero.think * 2); for (let k = 0; k < 3; k++) { c.fillStyle = rgba(EYE, a * (.35 + .65 * ((t * 3 + k) % 3 < 1))); ell(c, x + 34 * f + k * 9 * f, y - 92, 3, 3); c.fill(); } }
  if (hero.puff > 0) for (let k = 0; k < 4; k++) { c.fillStyle = rgba(EYE, hero.puff * .3); ell(c, x + f * (30 + (1 - hero.puff) * 60 + k * 10), y - 40 - k * 3, 4 + k * 2, 3 + k); c.fill(); }
  c.restore();
}
/* светлячки: в мире (спят/проснулись/летят) и в свите Огонька */
function firefly(x, y, awake = false) { const f = { x, y, hx: x, hy: y, st: awake ? 'awake' : 'sleep', t: 0, ph: Math.random() * 6, a: 0 }; G.flies.push(f); return f; }
function release(f, delay = 0) {
  f.st = 'go'; f.t = -delay; f.sx = f.x; f.sy = f.y;
  f.cx = (f.x + hero.x) / 2 + (Math.random() - .5) * 120; f.cy = Math.min(f.y, hero.y - 80) - 120 - Math.random() * 80;
}
function updFlies(dt) {
  for (const f of G.flies) {
    f.ph += dt;
    if (f.st === 'sleep') { f.a = .06 + .05 * Math.sin(f.ph * 1.7); }
    else if (f.st === 'awake') { f.a = Math.min(1, f.a + dt * 1.5); f.x = f.hx + Math.sin(f.ph * 1.3) * 7; f.y = f.hy + Math.sin(f.ph * 1.9) * 5; }
    else if (f.st === 'stuck') { f.a = .85 + .15 * Math.sin(f.ph * 9); f.x = f.hx + (Math.random() - .5) * 2; f.y = f.hy + (Math.random() - .5) * 2; }
    else if (f.st === 'go') {
      f.t += dt; const k = clamp(f.t / 1.1, 0, 1), e = ease(k), [bx, by] = bulb();
      if (f.t < 0) continue; f.a = 1;
      const u = 1 - e; f.x = u * u * f.sx + 2 * u * e * f.cx + e * e * bx; f.y = u * u * f.sy + 2 * u * e * f.cy + e * e * by;
      if (Math.random() < .5) G.parts.push({ x: f.x, y: f.y, vx: 0, vy: 10, life: .5, max: .5, s: 2.5, col: GOLD, k: 'glow' });
      if (k >= 1) { f.st = 'got'; G.count++; G.swarm.push({ a: Math.random() * TAU, r: 16 + Math.random() * 22, sp: (.8 + Math.random()) * (Math.random() < .5 ? 1 : -1), h: Math.random() * 6 }); snd.chime(G.count - 1); G.idle = 0; }
    }
  }
  G.flies = G.flies.filter((f) => f.st !== 'got');
}
function drawFlies(c) {
  for (const f of G.flies) {
    const fl = .75 + .25 * Math.sin(f.ph * 7 + f.hx);
    glow(c, f.x, f.y, 26, GOLD, f.a * .55 * fl);
    c.fillStyle = rgba('#fff3c4', Math.min(1, f.a * 1.3)); ell(c, f.x, f.y, 2.4, 2.4); c.fill();
  }
  if (hero.alpha > 0) {
    const [bx, by] = bulb();
    for (const s of G.swarm) {
      s.a += s.sp * .016;
      const x = bx + Math.cos(s.a) * s.r, y = by - 8 + Math.sin(s.a) * s.r * .55 + Math.sin(G.t * 2 + s.h) * 4;
      s.x = x; s.y = y;
      glow(c, x, y, 18, GOLD, .4 * hero.alpha); c.fillStyle = rgba('#fff3c4', hero.alpha); ell(c, x, y, 2, 2); c.fill();
    }
  }
}
function updParts(dt) {
  for (const p of G.parts) {
    p.life -= dt; p.vy += (p.g || 0) * dt; p.x += p.vx * dt; p.y += p.vy * dt;
    if (p.k === 'seed') { p.vx += Math.sin(G.t * 1.5 + p.ph) * 14 * dt; p.vy += Math.cos(G.t * 1.1 + p.ph) * 8 * dt; p.rot += p.vr * dt; }
  }
  G.parts = G.parts.filter((p) => p.life > 0);
}
function drawParts(c) {
  for (const p of G.parts) {
    const a = clamp(p.life / p.max, 0, 1);
    if (p.k === 'glow') glow(c, p.x, p.y, p.s * 5, p.col, a * .45);
    else if (p.k === 'drop') { c.fillStyle = rgba(p.col, a * .8); ell(c, p.x, p.y, p.s, p.s); c.fill(); }
    else if (p.k === 'seed') {
      c.save(); c.translate(p.x, p.y); c.rotate(p.rot); c.strokeStyle = rgba('#e9e4f5', a * .75); c.lineWidth = 1;
      c.beginPath(); c.moveTo(0, 0); c.lineTo(0, 10); for (let k = 0; k < 6; k++) { const an = -Math.PI / 2 + (k - 2.5) * .35; c.moveTo(0, 0); c.lineTo(Math.cos(an) * 7, Math.sin(an) * 7); } c.stroke(); c.restore();
    } else if (p.k === 'strand') { c.strokeStyle = rgba('#dfe6ff', a * .3); c.lineWidth = 1; c.beginPath(); c.moveTo(p.x, p.y); c.lineTo(p.x + p.dx, p.y + p.dy); c.stroke(); }
  }
}
function ring(x, y, big = 1) { G.rings.push({ x, y, t: 0, big }); }
function drawRings(c, col) {
  for (const r of G.rings) { r.t += .016; const k = r.t / 2.2; if (k > 1) continue;
    c.strokeStyle = rgba(col, (1 - k) * .45); c.lineWidth = 1.6; ell(c, r.x, r.y, 10 + k * 90 * r.big, 3 + k * 20 * r.big); c.stroke(); }
  G.rings = G.rings.filter((r) => r.t < 2.2);
}

/* ================= Сцена 1: Пруд =================
   Раскладка K — под форму окна: LAND (широкое окно на компьютере) или портрет (телефон). */
function Pond() {
  const P = PAL[0], st = { moon: 0, cloudGo: 0, lily: 0, lilyDone: false, reeds: false, rustle: 0, frog: 'sleep', frogT: 0, snore: 0, snoreT: 1, bellT: 9, peek: 0 };
  const K = LAND ? {
    moon: [960, 140], wisps: [170, 330], far: [[330, 22, 0, .28], [392, 16, 9, .45]], millHill: [1110, 418, 96, 30], mill: [1110, 398],
    near: [[468, 12, 15, .66], [522, 7, 0, .84]], fog: [440, 552], pond: [700, 652, 300, 96], reflY: [566, 720],
    lilies: [[590, 612, 30], [810, 700, 26], [650, 694, 34], [905, 628, 22]], lily: [722, 656, 34], peek: [770, 668],
    gL: 562, gLog: 557, gR: 557, gx0: 548, gx1: 866, log: [542, 880, 557], bankL: 565, bankR: 845,
    bell: [516, 563, 508, 475], frog: [802, 559], jump: [742, 676], reeds: [240, 390], deco: [16, 120], f1: [288, 440], f2: [350, 414],
    heroIn: 440, maxX0: 732, exit: [1212, 520], exitTo: 1340, fgTop: 712, fgR: [1120, 1300, 220, 360], fgL: [-30, 120, 200, 330], fog2: [650, 720], tapY: 430, titleY: 112
  } : {
    moon: [520, 250], wisps: [380, 640], far: [[690, 22, 0, .28], [760, 16, 9, .45]], millHill: [612, 790, 90, 34], mill: [612, 768],
    near: [[850, 12, 15, .66], [912, 7, 0, .84]], fog: [820, 940], pond: [395, 1045, 250, 115], reflY: [962, 1150],
    lilies: [[300, 1010, 30], [470, 1092, 26], [350, 1118, 34], [560, 1030, 22]], lily: [398, 1056, 34], peek: [430, 1068],
    gL: 953, gLog: 948, gR: 948, gx0: 268, gx1: 548, log: [262, 560, 948], bankL: 285, bankR: 525,
    bell: [236, 954, 228, 866], frog: [482, 950], jump: [410, 1066], reeds: [38, 168], deco: null, f1: [84, 832], f2: [146, 806],
    heroIn: 190, maxX0: 412, exit: [690, 900], exitTo: 800, fgTop: 1160, fgR: [560, 760, 300, 520], fgL: [-30, 90, 240, 440], fog2: [1120, 1240], tapY: 760, titleY: 200
  };
  const r = rng(11), reeds = [];
  for (let i = 0; i < 14; i++) reeds.push({ x: K.reeds[0] + r() * (K.reeds[1] - K.reeds[0]), h: 90 + r() * 120, ph: r() * 6, cat: r() < .55, w: 3 + r() * 2 });
  if (K.deco) for (let i = 0; i < 9; i++) reeds.push({ x: K.deco[0] + r() * (K.deco[1] - K.deco[0]), h: 60 + r() * 110, ph: r() * 6, cat: r() < .4, w: 3 + r() * 2, deco: true });
  const fg = [];
  for (let i = 0; i < 9; i++) fg.push({ x: K.fgR[0] + r() * (K.fgR[1] - K.fgR[0]), h: K.fgR[2] + r() * (K.fgR[3] - K.fgR[2]), ph: r() * 6, w: 10 + r() * 8, b: (r() - .3) * 60 });
  for (let i = 0; i < 7; i++) fg.push({ x: K.fgL[0] + r() * (K.fgL[1] - K.fgL[0]), h: K.fgL[2] + r() * (K.fgL[3] - K.fgL[2]), ph: r() * 6, w: 10 + r() * 8, b: (r() - .7) * 60 });
  const MOON = K.moon, [px, py, prx, pry] = K.pond, [lx0, lx1, ly] = K.log, [bx0, by0, bx1, by1] = K.bell;
  let f1, f2, f3;
  const ground = (x) => (x < K.gx0 ? K.gL + Math.sin(x * .05) * 1.5 : x < K.gx1 ? K.gLog - Math.sin((x - K.gx0) / (K.gx1 - K.gx0) * Math.PI) * 5 : K.gR);
  const sc = {
    pal: P, ground, tapY: K.tapY, titleY: K.titleY,
    minX: () => 30, maxX: () => (st.frog === 'gone' ? K.exitTo : K.maxX0),
    start() { hero.x = -40; f1 = firefly(...K.f1); f2 = firefly(...K.f2); f3 = firefly(K.lily[0], K.lily[1] - 4);
      if (G.mode === 'play') { G.busy = true; walkTo(K.heroIn, () => { G.busy = false; say(HINTS.cloud, 7); }); } },
    done: () => st.reeds && st.lilyDone && st.frog === 'gone',
    hint() { return !st.moon ? 'cloud' : !st.reeds ? 'reeds' : !st.lilyDone ? 'lily' : st.frog === 'sleep' ? 'bell' : 'exit'; },
    spots() {
      return [
        { id: 'cloud', x: MOON[0] + st.cloudGo * 300, y: MOON[1] + 10, r: 110, on: !st.moon && !st.cloudGo, act() {
          st.cloudGo = .001; snd.whoosh(); } },
        { id: 'reeds', x: (K.reeds[0] + K.reeds[1]) / 2, y: K.gL - 110, r: 85, on: !st.reeds, walk: K.reeds[1] + 10, act() {
          st.rustle = 1.2; snd.rustle();
          if (st.moon > .5) { st.reeds = true; release(f1, .2); release(f2, .45); say(HINTS.lily, 5); } else { hero.think = 1.6; say(HINTS.dark, 5); } } },
        { id: 'lily', x: K.lily[0], y: K.lily[1], r: 52, on: !st.lilyDone, act() {
          ring(K.lily[0], K.lily[1], .7); SND.ctx && SND.hiss(now(), .3, .04, 'lowpass', 900);
          if (st.moon > .5) { st.lily = .001; st.lilyDone = true; setTimeout(() => release(f3), 500); setTimeout(() => { if (st.frog === 'sleep') say(HINTS.bell, 6); }, 1800); }
          else { hero.think = 1.2; say(HINTS.dark, 5); } } },
        { id: 'bell', x: bx1 + 10, y: by1 + 14, r: 50, on: st.frog === 'sleep', walk: bx0 - 22, act() {
          st.bellT = 0; snd.bell(); setTimeout(() => { if (st.frog === 'sleep') { st.frog = 'wake'; st.frogT = 0; snd.croak(); } }, 900); } },
        { id: 'frog', x: K.frog[0], y: K.frog[1] - 35, r: 52, on: st.frog === 'sleep', walk: K.maxX0, act() { st.snore = 1; snd.snore(); hero.think = 1.4; say(HINTS.frog, 5); } },
        { id: 'exit', x: K.exit[0], y: K.exit[1], r: 70, on: st.frog === 'gone', walk: K.exit[0], act() {
          if (sc.done()) { walkTo(K.exitTo, () => goScene(1)); G.busy = true; } else { hero.think = 1.6; snd.nope(); G.idle = 99; say(HINTS.more, 5); } } },
      ];
    },
    update(dt) {
      if (st.cloudGo) { st.cloudGo = Math.min(1, st.cloudGo + dt * .45); st.moon = eOut(clamp((st.cloudGo - .15) / .7, 0, 1));
        if (st.moon > .5 && f1.st === 'sleep') { f1.st = f2.st = 'awake'; say(HINTS.reeds, 6); } }
      if (st.rustle > 0) st.rustle -= dt;
      if (st.lily && st.lily < 1) st.lily = Math.min(1, st.lily + dt * 1.6);
      st.bellT += dt;
      if (st.frog === 'sleep') { st.snoreT -= dt; if (st.snoreT <= 0) { st.snoreT = 3.2; st.snore = .001; } if (st.snore) st.snore = st.snore >= 1 ? 0 : Math.min(1, st.snore + dt * .45); }
      if (st.frog === 'wake') { st.frogT += dt; if (st.frogT > .7) { st.frog = 'jump'; st.frogT = 0; G.busy = true; } }
      if (st.frog === 'jump') { st.frogT += dt * 1.25; if (st.frogT >= 1) { st.frog = 'gone'; G.busy = false; snd.splash(); ring(K.jump[0], K.jump[1] - 4, 1.3); ring(K.jump[0], K.jump[1] - 4, .7);
        for (let k = 0; k < 24; k++) G.parts.push({ x: K.jump[0], y: K.jump[1] - 6, vx: (Math.random() - .5) * 220, vy: -120 - Math.random() * 220, g: 600, life: .9, max: .9, s: 2 + Math.random() * 2, col: '#cfe0ff', k: 'drop' });
        if (sc.done()) say(HINTS.exit, 6); else if (!st.reeds || !st.lilyDone) say(HINTS.more, 6); } }
      if (st.frog === 'gone') st.peek += dt;
    },
    draw(c, g) {
      c.drawImage(layer(0, 0, (x) => { sky(x, P, 5); const r = rng(17);
        for (let i = 0; i < (LAND ? 10 : 7); i++) { const cx = r() * W, cy = K.wisps[0] + r() * (K.wisps[1] - K.wisps[0]), w = 160 + r() * 220; x.save(); x.translate(cx, cy); x.scale(1, .09 + r() * .05);
          const gr = x.createRadialGradient(0, 0, 0, 0, 0, w); gr.addColorStop(0, 'rgba(255,214,190,' + (.1 + r() * .08).toFixed(2) + ')'); gr.addColorStop(1, 'rgba(255,214,190,0)'); x.fillStyle = gr; x.fillRect(-w, -w, w * 2, w * 2); x.restore(); } }, g), 0, 0, W, H);
      // луна и туча
      const [mx, my] = MOON, mb = .25 + .75 * st.moon;
      glow(c, mx, my, 260, '#ffe8c4', .22 * mb); glow(c, mx, my, 110, '#fff2da', .35 * mb);
      c.fillStyle = mix('#8f8aa6', '#fbf3df', mb); ell(c, mx, my, 44, 44); c.fill();
      c.fillStyle = rgba('#b9a98f', .18 * mb); ell(c, mx - 12, my - 8, 9, 8); c.fill(); ell(c, mx + 14, my + 12, 6, 5); c.fill(); ell(c, mx + 6, my - 18, 4, 4); c.fill();
      const cg = st.cloudGo, cx = mx - 10 + ease(cg) * 330, ca = 1 - eOut(clamp((cg - .4) / .6, 0, 1));
      if (ca > 0) { c.save(); c.globalAlpha = ca;
        c.fillStyle = '#2a3150'; [[-70, 18, 46], [-25, -4, 58], [30, 6, 52], [78, 22, 38], [0, 30, 60]].forEach(([dx, dy, rr]) => { ell(c, cx + dx, my + dy + Math.sin(G.t * .4 + dx) * 2, rr, rr * .72); c.fill(); });
        c.strokeStyle = rgba('#ffe7c2', .25); c.lineWidth = 2; ell(c, cx - 25, my - 4, 58, 41.8); c.stroke(); c.restore(); }
      c.drawImage(layer(0, 1, (x) => { const r = rng(21);
        K.far.forEach(([y, a, t, d]) => ridge(x, r, y, a, mix(P.haze, P.ink, d), t));
        x.fillStyle = mix(P.haze, P.ink, .45); ell(x, ...K.millHill); x.fill(); }, g), 0, 0, W, H);
      mill(c, ...K.mill, mix(P.haze, P.ink, .45));
      c.drawImage(layer(0, 3, (x) => { const r = rng(22); K.near.forEach(([y, a, t, d]) => ridge(x, r, y, a, mix(P.haze, P.ink, d), t)); }, g), 0, 0, W, H);
      fog(c, P, K.fog[0], K.fog[1], LAND ? 7 : 5, .16, 3);
      // вода
      c.save(); c.beginPath(); c.ellipse(px, py, prx, pry, 0, 0, TAU); c.clip();
      const wg = c.createLinearGradient(0, py - pry - 5, 0, py + pry); wg.addColorStop(0, mix(P.haze, P.ink, .45)); wg.addColorStop(.35, mix('#34416a', P.ink, .5)); wg.addColorStop(1, P.ink);
      c.fillStyle = wg; c.fillRect(px - prx, py - pry - 10, prx * 2, pry * 2 + 20);
      if (st.moon > 0) for (let y = K.reflY[0]; y < K.reflY[1]; y += 6) { const k = (y - K.reflY[0]) / (K.reflY[1] - K.reflY[0]), w = (26 + Math.sin(G.t * 1.7 + y * .21) * 14) * (1 - k * .5);
        c.fillStyle = rgba('#fff1d4', st.moon * .5 * (1 - k)); c.fillRect(mx - 10 - w / 2 + Math.sin(G.t * 1.1 + y * .13) * 6, y, w, 2); }
      drawRings(c, '#e6ecff');
      K.lilies.forEach(([x, y, rr]) => lily(c, x, y, rr, 0, P));
      lily(c, ...K.lily, st.lily, P);
      if (st.frog === 'gone') { const pk = clamp(st.peek / 1.5 - .6, 0, 1), bob = Math.sin(G.t * 1.4) * 2, [qx, qy] = K.peek;     // лягушка выглядывает из воды
        c.fillStyle = P.ink; ell(c, qx, qy + bob, 22 * pk, 9 * pk); c.fill(); ell(c, qx - 10, qy - 7 + bob, 7 * pk, 7 * pk); c.fill(); ell(c, qx + 10, qy - 7 + bob, 7 * pk, 7 * pk); c.fill();
        c.fillStyle = rgba('#e3f28a', pk * .9); ell(c, qx - 10, qy - 8 + bob, 3, 2.4 * pk); c.fill(); ell(c, qx + 10, qy - 8 + bob, 3, 2.4 * pk); c.fill(); }
      c.restore();
      // берега и земля
      c.drawImage(layer(0, 2, (x) => { const r = rng(31), bL = K.bankL, bR = K.bankR, wb = py + pry + 20; x.fillStyle = mix(P.haze, P.ink, .93);
        x.beginPath(); x.moveTo(-10, H + 10); x.lineTo(-10, K.gL); for (let X = 0; X <= bL; X += 5) x.lineTo(X, ground(X) + (X > bL - 45 ? (X - (bL - 45)) ** 2 / 60 : 0)); x.quadraticCurveTo(bL - 35, wb - 60, bL - 115, wb); x.lineTo(-10, wb + 10); x.fill();
        x.beginPath(); x.moveTo(W + 10, H + 10); x.lineTo(W + 10, K.gR); for (let X = W; X >= bR; X -= 5) x.lineTo(X, K.gR + (X < bR + 45 ? (bR + 45 - X) ** 2 / 70 : 0)); x.quadraticCurveTo(bR + 35, wb - 70, bR + 95, wb - 10); x.lineTo(W + 10, wb); x.fill();
        x.fillStyle = P.ink; x.beginPath(); x.moveTo(-10, H + 10); x.lineTo(-10, K.fgTop - 10); for (let X = -10; X <= W + 10; X += 8) x.lineTo(X, K.fgTop + Math.sin(X * .02) * 14 + Math.sin(X * .07) * 5); x.lineTo(W + 10, H + 10); x.fill();
        grass(x, r, 0, bL - 5, ground, mix(P.haze, P.ink, .93), LAND ? 120 : 70, 22); grass(x, r, bR + 5, W, () => K.gR, mix(P.haze, P.ink, .93), LAND ? 80 : 50, 22);
        grass(x, r, -10, W + 10, (X) => K.fgTop + Math.sin(X * .02) * 14, P.ink, LAND ? 200 : 160, 40); }, g), 0, 0, W, H);
      // бревно
      const lm = (lx0 + lx1) / 2;
      c.fillStyle = mix(P.haze, P.ink, .88); c.beginPath(); c.moveTo(lx0, ly + 6); c.quadraticCurveTo(lm, ly - 13, lx1, ly + 2); c.lineTo(lx1, ly + 18); c.quadraticCurveTo(lm, ly + 3, lx0, ly + 22); c.closePath(); c.fill();
      if (st.moon) { c.strokeStyle = rgba('#ffe8c4', .3 * st.moon); c.lineWidth = 1.5; c.beginPath(); c.moveTo(lx0 + 4, ly + 5); c.quadraticCurveTo(lm, ly - 14, lx1 - 4, ly + 1); c.stroke(); }
      c.fillStyle = mix(P.haze, P.ink, .7); ell(c, lx1, ly + 10, 6, 8); c.fill();
      // колокольчик
      const sw = st.bellT < 3 ? Math.sin(st.bellT * 18) * Math.exp(-st.bellT * 1.6) * .5 : Math.sin(G.t * 1.2) * .04;
      c.fillStyle = mix(P.haze, P.ink, .9); blade(c, bx0, by0, bx1, by1, 10, 4);
      [[bx1, by1], [bx1 + 16, by1 + 30]].forEach(([bx, by], k) => { c.save(); c.translate(bx, by); c.rotate(sw * (k ? .7 : 1) + .15);
        c.fillStyle = mix('#a99ae0', P.ink, .35); c.beginPath(); c.moveTo(-3, 0); c.quadraticCurveTo(-10, 6, -11, 20); c.lineTo(-5, 17); c.lineTo(0, 22); c.lineTo(5, 17); c.lineTo(11, 20); c.quadraticCurveTo(10, 6, 3, 0); c.closePath(); c.fill();
        glow(c, 0, 14, 22, '#b7a8ff', .14 + (st.bellT < 2 ? .25 * (1 - st.bellT / 2) : 0)); c.restore(); });
      if (st.bellT < 1.8) for (let k = 0; k < 3; k++) { const q = st.bellT * 1.4 - k * .25; if (q > 0 && q < 1) { c.strokeStyle = rgba('#d8ceff', (1 - q) * .5); c.lineWidth = 2; c.beginPath(); c.arc(bx1 + 6, by1 + 14, 20 + q * 220, -.5, .4); c.stroke(); } }
      // лягушка
      if (st.frog !== 'gone') {
        let [fx, fy] = K.frog, rot = 0;
        if (st.frog === 'jump') { const k = st.frogT; fx = lerp(K.frog[0], K.jump[0], k); fy = lerp(K.frog[1], K.jump[1], k) - Math.sin(k * Math.PI) * 120; rot = -.6 + k * 1.2; }
        frog(c, fx, fy, st, rot, P);
      }
      // камыш с котиками
      for (const rd of reeds) { const s = Math.sin(G.t * 1.3 + rd.ph) * 4 + (st.rustle > 0 && !rd.deco ? Math.sin(G.t * 16 + rd.ph) * 9 * st.rustle : 0), y0 = ground(rd.x) + 2;
        c.fillStyle = mix(P.haze, P.ink, .9); blade(c, rd.x, y0, rd.x + s, y0 - rd.h, s * .3, rd.w);
        if (rd.cat) { c.save(); c.translate(rd.x + s * .97, y0 - rd.h * .86); c.rotate(s * .012); A.rr(c, -4.5, -16, 9, 30, 4.5); c.fill(); c.restore(); } }
      drawHero(c, P); drawFlies(c);
      if (st.frog === 'gone' && sc.done()) { const a = .4 + .3 * Math.sin(G.t * 3), [ex, ey] = K.exit; c.strokeStyle = rgba(GOLD, a); c.lineWidth = 3; c.beginPath(); c.moveTo(ex - 8, ey - 20); c.lineTo(ex + 6, ey - 6); c.lineTo(ex - 8, ey + 8); c.stroke(); }
      // передний план: большие листья осоки
      c.fillStyle = '#04060b';
      for (const b of fg) { const s = Math.sin(G.t * .9 + b.ph) * 6; blade(c, b.x, H + 20, b.x + b.b + s, H + 20 - b.h, b.b * .4 + s, b.w); }
      fog(c, P, K.fog2[0], K.fog2[1], 3, .07, 9);
    },
  };
  return sc;
}
function mill(c, x, y, col) {           // мельница на дальнем холме: крылья медленно вертятся, в окошке свет
  c.fillStyle = col; c.beginPath(); c.moveTo(x - 15, y + 4); c.lineTo(x - 9, y - 62); c.lineTo(x + 9, y - 62); c.lineTo(x + 15, y + 4); c.fill();
  c.beginPath(); c.moveTo(x - 12, y - 60); c.lineTo(x, y - 76); c.lineTo(x + 12, y - 60); c.fill();
  const a = G.t * .35; c.save(); c.translate(x, y - 64); c.rotate(a);
  for (let k = 0; k < 4; k++) { c.rotate(Math.PI / 2); c.fillRect(-1.5, 0, 3, 46); c.fillRect(1.5, 12, 7, 32); }
  c.restore(); c.fillStyle = col; ell(c, x, y - 64, 3.5, 3.5); c.fill();
  c.fillStyle = 'rgba(255,190,110,.9)'; c.fillRect(x - 2.5, y - 34, 5, 7); glow(c, x, y - 31, 20, WARM, .35 + .1 * Math.sin(G.t * 1.7));
}
function lily(c, x, y, r, flip, P) {
  const k = Math.cos(clamp(flip, 0, 1) * Math.PI);
  c.save(); c.translate(x, y); c.scale(1, Math.abs(k) * .3 + .02);
  c.fillStyle = k >= 0 ? mix('#3d5a48', P.ink, .55) : mix('#7a4b5c', P.ink, .4);
  c.beginPath(); c.moveTo(0, 0); c.arc(0, 0, r, .25, TAU - .1); c.closePath(); c.fill();
  c.strokeStyle = rgba('#d6e8c8', .12); c.lineWidth = 2; c.beginPath(); c.arc(0, 0, r, .25, TAU - .1); c.stroke();
  c.restore();
  if (flip > 0 && flip < 1) ring(x, y, .3);
}
function frog(c, x, y, st, rot, P) {
  c.save(); c.translate(x, y); c.rotate(rot); c.fillStyle = mix(P.haze, P.ink, .9);
  ell(c, 0, -20, 42, 22); c.fill();                         // тело
  ell(c, -26, -30, 22, 15); c.fill();                       // голова (смотрит влево)
  ell(c, 26, -8, 16, 10); c.fill();                         // задняя лапа
  ell(c, -36, -4, 10, 5); c.fill();
  ell(c, -32, -44, 9, 9); c.fill(); ell(c, -14, -46, 9, 9); c.fill();   // глаза-купола
  if (st.frog === 'sleep') { c.strokeStyle = rgba('#e6f0c0', .4); c.lineWidth = 2; c.beginPath(); c.arc(-32, -45, 5, .2, Math.PI - .2); c.moveTo(-9, -45); c.arc(-14, -46, 5, .2, Math.PI - .2); c.stroke(); }
  else { c.fillStyle = '#e3f28a'; ell(c, -32, -45, 5, 5); c.fill(); ell(c, -14, -47, 5, 5); c.fill(); c.fillStyle = P.ink; ell(c, -33, -45, 1.6, 4); c.fill(); ell(c, -15, -47, 1.6, 4); c.fill(); }
  c.restore();
  if (st.frog === 'sleep' && st.snore) { const s = st.snore, r = 4 + s * 15;
    c.fillStyle = rgba('#c9dcff', .08 + s * .05); c.strokeStyle = rgba('#e3ecff', .45 * (1 - s * .5)); c.lineWidth = 1.5;
    ell(c, x - 52 - r * .6, y - 24 - r * .3, r, r * .92); c.fill(); c.stroke(); }
}
/* y на верхнем краю ветки-кривой (квадратичная Безье p0-p1-p2) для заданного x */
function qy(p0, p1, p2, x) {
  let lo = 0, hi = 1;
  for (let i = 0; i < 30; i++) { const t = (lo + hi) / 2, X = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0]; if (X < x) lo = t; else hi = t; }
  const t = (lo + hi) / 2; return (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1];
}

/* ================= Сцена 2: Старое дерево ================= */
function Tree() {
  const P = PAL[1], st = { owl: 'sleep', owlT: 0, spider: 'web', spT: 0, web: 1, webDone: false, inB: false, rock: 'branch', rockT: 0, wob: 0, d: 0, lift: false, ferns: [] };
  const K = LAND ? {
    gy: 640, b1: [[170, 190], [520, 92], [1110, 70]], b2: [[176, 410], [300, 380], [480, 386]], hollow: [120, 250], web: [370, 486],
    pulley: 780, leaves: [800, 1150, 10, 70], moss: [260, 740], heroIn: 300, webWalk: 350, scare: 250, D: 366,
    trunks: 16, blobs: 70, shafts: [[760, 70, .09], [980, 40, .07], [560, 110, .05], [1180, 50, .06]], fog: [520, 632], fog2: [660, 720],
    shrooms: [60, 540, 575, 1010, 1220], ferns: 16, strip: 700, tapY: 400, titleY: 112
  } : {
    gy: 1062, b1: [[170, 300], [420, 210], [700, 196]], b2: [[176, 700], [300, 668], [420, 676]], hollow: [130, 566], web: [338, 812],
    pulley: 540, leaves: [540, 740, 110, 180], moss: [230, 560], heroIn: 250, webWalk: 330, scare: 230, D: 640,
    trunks: 10, blobs: 40, shafts: [[470, 60, .09], [600, 30, .07], [360, 110, .05]], fog: [900, 1040], fog2: [1150, 1260],
    shrooms: [60, 420, 455, 650], ferns: 10, strip: 1196, tapY: 760, titleY: 200
  };
  const r = rng(5); for (let i = 0; i < K.ferns; i++) st.ferns.push({ x: r() * W, h: (LAND ? 50 : 70) + r() * (LAND ? 70 : 90), ph: r() * 6, b: (r() - .5) * 50 });
  const [p0, p1, p2] = K.b1, bY = (x) => qy(p0, p1, p2, x);
  const PX = K.pulley, PY = bY(PX) + 22, WEB = K.web, B0 = K.gy, C0 = PY + 118, D = K.D;
  const R0 = [PX - 88, bY(PX - 88) - 10], R1 = [PX + 20, bY(PX + 20) - 12], LB = K.b2[2];
  let flies = [];
  const ground = () => K.gy;
  const sc = {
    pal: P, ground, tapY: K.tapY, titleY: K.titleY, minX: () => 40, maxX: () => PX + 150,
    start() { hero.x = -40; hero.ride = false; flies = [[-32, -30], [32, -14], [-12, 46]].map(([dx, dy]) => { const f = firefly(WEB[0] + dx, WEB[1] + dy); f.st = 'stuck'; return f; });
      G.busy = true; walkTo(K.heroIn, () => { G.busy = false; say(HINTS.owl, 7); }); },
    hint() { return st.spider !== 'gone' ? 'owl' : !st.webDone ? 'web' : !st.inB ? 'bucket' : 'rock'; },
    spots() {
      return [
        { id: 'owl', x: K.hollow[0], y: K.hollow[1] - 6, r: 64, on: true, act() { if (st.owl === 'awake') return; st.owl = 'awake'; st.owlT = 0; snd.hoot();
          if (st.spider !== 'gone') { setTimeout(() => { st.spider = 'flee'; st.spT = 0; }, 700); setTimeout(() => say(HINTS.web, 6), 2000); } } },
        { id: 'web', x: WEB[0], y: WEB[1], r: 90, on: !st.webDone, walk: K.webWalk, act() {
          if (st.spider === 'web') { st.spider = 'scare'; st.spT = 0; hero.think = 1.4; snd.nope(); walkTo(K.scare); say(HINTS.spider, 6); }
          else if (st.spider === 'gone') { st.webDone = true; st.web = .999; snd.snap(); flies.forEach((f, i) => release(f, i * .25)); setTimeout(() => say(HINTS.bucket, 6), 2200);
            for (let k = 0; k < 18; k++) { const a = Math.random() * TAU, l = 8 + Math.random() * 20; G.parts.push({ x: WEB[0] + Math.cos(a) * 40, y: WEB[1] + Math.sin(a) * 40, vx: (Math.random() - .5) * 30, vy: 20 + Math.random() * 40, g: 30, life: 1.6, max: 1.6, k: 'strand', dx: Math.cos(a + 1) * l, dy: Math.sin(a + 1) * l }); } } } },
        { id: 'bucket', x: PX - 20, y: B0 - 42, r: 58, on: !st.inB, walk: PX - 70, act() {
          if (!st.webDone) { hero.think = 1.6; hero.face = -1; G.idle = 99; snd.nope(); say(HINTS.more, 5); return; }
          st.inB = true; hero.ride = true; G.busy = false; snd.creak(); hopT = 0; setTimeout(() => say(HINTS.rock, 6), 900); } },
        { id: 'rock', x: R0[0], y: R0[1], r: 52, on: st.rock === 'branch', act() {
          if (!st.inB) { st.wob = 1; hero.think = 1.2; say(HINTS.rockEarly, 5); return; }
          st.rock = 'roll'; st.rockT = 0; G.busy = true; } },
      ];
    },
    update(dt) {
      if (st.owl === 'awake') { st.owlT += dt; if (st.owlT > 4) st.owl = 'sleep'; }
      if (st.spider === 'scare' || st.spider === 'flee') st.spT += dt;
      if (st.spider === 'scare' && st.spT > 1.6) st.spider = 'web';
      if (st.spider === 'flee' && st.spT > 1.4) st.spider = 'gone';
      if (st.web < 1 || st.webDone) st.web = Math.max(0, st.web - dt * .8);
      if (st.wob > 0) st.wob = Math.max(0, st.wob - dt * 1.5);
      if (st.inB && hopT < 1) { hopT = Math.min(1, hopT + dt * 2.2); hero.x = lerp(PX - 70, PX - 21, hopT); hero.y = lerp(B0, B0 - 22, hopT) - Math.sin(hopT * Math.PI) * 50; hero.face = 1; }
      if (st.rock === 'roll') { st.rockT += dt; if (st.rockT > 1.1) { st.rock = 'fall'; st.rockT = 0; } }
      if (st.rock === 'fall') { st.rockT += dt; if (st.rockT > .45) { st.rock = 'in'; snd.thud(); st.lift = true; snd.creak(); } }
      if (st.lift) { st.d = Math.min(D, st.d + dt * (60 + st.d * .45) * (LAND ? .75 : 1));
        if (Math.random() < dt * 3) snd.creak();
        if (st.d > D * .875 && !G.fadeThen) goScene(2); }
      if (st.inB && hopT >= 1) { hero.x = PX - 21; hero.y = B0 - st.d - 22; }
    },
    draw(c, g) {
      c.drawImage(layer(1, 0, (x) => { sky(x, P, 0); const r = rng(8);
        for (let i = 0; i < K.trunks; i++) { const X = 160 + r() * (W - 140), w = 16 + r() * 38, dep = .22 + r() * .4, gr = x.createLinearGradient(0, 0, 0, K.gy);
          gr.addColorStop(0, mix(P.haze, P.ink, Math.min(.95, dep + .3))); gr.addColorStop(.75, mix(P.haze, P.ink, dep)); gr.addColorStop(1, mix(P.haze, P.ink, Math.max(0, dep - .2)));
          x.fillStyle = gr; x.beginPath(); x.moveTo(X - w * .4, -10); x.lineTo(X + w * .4, -10); x.lineTo(X + w * .55 + 4, K.gy - 62); x.quadraticCurveTo(X + w, K.gy, X + w * 1.3, K.gy + 4); x.lineTo(X - w * 1.3, K.gy + 4); x.quadraticCurveTo(X - w, K.gy, X - w * .55 - 4, K.gy - 62); x.closePath(); x.fill();
          r(); r(); r(); }
        ridge(x, r, K.gy - 82, 10, mix(P.haze, P.ink, .5), 0);
        x.fillStyle = mix(P.haze, P.ink, .55); for (let i = 0; i < K.blobs; i++) { ell(x, r() * W, r() * (LAND ? 110 : 160) - 20, 60 + r() * 80, 40 + r() * 50); x.fill(); } }, g), 0, 0, W, H);
      // лучи луны сквозь листву
      c.save(); c.globalCompositeOperation = 'lighter';
      K.shafts.forEach(([x0, w, a], k) => { const aa = a * (.75 + .25 * Math.sin(G.t * .5 + k * 2)), L = K.gy + 40, dx = L * .3;
        const gr = c.createLinearGradient(x0, 0, x0 - dx * .8, L); gr.addColorStop(0, rgba('#cfe3ff', aa)); gr.addColorStop(1, rgba('#cfe3ff', 0));
        c.fillStyle = gr; c.beginPath(); c.moveTo(x0, -10); c.lineTo(x0 + w, -10); c.lineTo(x0 + w - dx, L); c.lineTo(x0 - dx - w, L); c.closePath(); c.fill(); });
      c.restore();
      fog(c, P, K.fog[0], K.fog[1], LAND ? 7 : 5, .14, 4);
      c.drawImage(layer(1, 1, (x) => { const r = rng(9), ink = mix(P.haze, P.ink, .92), gy = K.gy;
        x.fillStyle = ink;
        // ствол с корнями
        x.beginPath(); x.moveTo(-20, H); x.lineTo(-20, -20); x.lineTo(176, -20);
        for (let y = 0; y <= gy - 2; y += 20) x.lineTo(176 + Math.sin(y * .011) * 16 + (y > gy - 162 ? (y - (gy - 162)) ** 2 / 300 : 0), y);
        x.quadraticCurveTo(330, gy + 10, 380, gy + 13); x.lineTo(-20, gy + 48); x.fill();
        // ветви
        const br = ([a, b, cc], th) => { x.beginPath(); x.moveTo(a[0], a[1]); x.quadraticCurveTo(b[0], b[1], cc[0], cc[1]); x.lineTo(cc[0] + 4, cc[1] + th * .25); x.quadraticCurveTo(b[0] + 10, b[1] + th * .65, a[0] + 6, a[1] + th); x.fill(); };
        br(K.b1, 40); br(K.b2, 28);
        [[p2[0] - 100, 1], [p0[0] + 230, -1], [p2[0] - 10, 0]].forEach(([X, d]) => { const Y = bY(X); blade(x, X, Y + 8, X + 40 + d * 20, Y - 46 - d * 6, d * 10 - 10, 6); });
        // кора
        x.strokeStyle = 'rgba(160,190,220,.05)'; x.lineWidth = 2;
        for (let i = 0; i < 26; i++) { const X = r() * 150, Y = r() * (gy - 60); x.beginPath(); x.moveTo(X, Y); x.bezierCurveTo(X + 6, Y + 40, X - 6, Y + 80, X + 2, Y + 130); x.stroke(); }
        // дупло
        x.fillStyle = '#020307'; ell(x, K.hollow[0], K.hollow[1], 44, 60); x.fill();
        x.strokeStyle = 'rgba(170,200,230,.1)'; x.lineWidth = 3; ell(x, K.hollow[0], K.hollow[1], 46, 62); x.stroke();
        // листва над блоком
        x.fillStyle = ink; for (let i = 0; i < (LAND ? 44 : 30); i++) { const X = K.leaves[0] + r() * (K.leaves[1] - K.leaves[0]), Y = K.leaves[2] + r() * (K.leaves[3] - K.leaves[2]); ell(x, X, Y, 14 + r() * 24, 10 + r() * 14); x.fill(); }
        x.strokeStyle = ink; x.lineCap = 'round';                    // мох свисает с ветки
        for (let i = 0; i < (LAND ? 30 : 22); i++) { const X = K.moss[0] + r() * (K.moss[1] - K.moss[0]), Y = bY(X) + 18, L = 20 + r() * (LAND ? 50 : 70);
          x.lineWidth = 1.5 + r() * 2; x.beginPath(); x.moveTo(X, Y - 4); x.quadraticCurveTo(X + (r() - .5) * 14, Y + L * .5, X + (r() - .5) * 8, Y + L); x.stroke(); }
        // земля
        x.beginPath(); x.moveTo(-10, H + 10); x.lineTo(-10, gy + 4); for (let X = 0; X <= W + 10; X += 8) x.lineTo(X, gy + Math.sin(X * .03) * 2); x.lineTo(W + 10, H + 10); x.fill();
        grass(x, r, 0, W, () => gy + 1, ink, LAND ? 180 : 120, 24);
        // грибочки-светляки
        K.shrooms.forEach((X) => { const Y = gy + 1; x.fillStyle = ink; x.fillRect(X - 1.5, Y - 14, 3, 14); x.fillStyle = '#9fd8e0'; ell(x, X, Y - 15, 7, 4); x.fill();
          const gr = x.createRadialGradient(X, Y - 14, 0, X, Y - 14, 26); gr.addColorStop(0, 'rgba(160,230,240,.35)'); gr.addColorStop(1, 'rgba(160,230,240,0)'); x.fillStyle = gr; x.fillRect(X - 26, Y - 40, 52, 52); });
        x.fillStyle = P.ink; x.beginPath(); x.moveTo(-10, H + 10); x.lineTo(-10, K.strip - 6); for (let X = -10; X <= W + 10; X += 8) x.lineTo(X, K.strip + Math.sin(X * .025) * 16); x.lineTo(W + 10, H + 10); x.fill(); }, g), 0, 0, W, H);
      // сова
      const ow = st.owl === 'awake', puff = ow ? 1 + Math.max(0, .08 - st.owlT * .04) : 1;
      c.save(); c.translate(K.hollow[0], K.hollow[1] + 44); c.scale(puff, puff); c.fillStyle = '#151827';
      ell(c, 0, -12, 30, 40); c.fill();
      c.beginPath(); c.moveTo(-26, -40); c.lineTo(-20, -64); c.lineTo(-8, -46); c.moveTo(26, -40); c.lineTo(20, -64); c.lineTo(8, -46); c.fill();
      if (ow) { glow(c, -12, -32, 30, '#ffb347', .35); glow(c, 12, -32, 30, '#ffb347', .35);
        c.fillStyle = '#ffbe55'; ell(c, -12, -32, 10, 10); c.fill(); ell(c, 12, -32, 10, 10); c.fill(); c.fillStyle = '#120f0a'; ell(c, -12, -31, 4.5, 5.5); c.fill(); ell(c, 12, -31, 4.5, 5.5); c.fill(); }
      else { c.strokeStyle = rgba('#ffbe55', .55 + .2 * Math.sin(G.t)); c.lineWidth = 2.5; c.beginPath(); c.moveTo(-20, -32); c.quadraticCurveTo(-12, -28, -4, -32); c.moveTo(4, -32); c.quadraticCurveTo(12, -28, 20, -32); c.stroke(); }
      c.fillStyle = '#2a2a33'; c.beginPath(); c.moveTo(-3, -24); c.lineTo(3, -24); c.lineTo(0, -17); c.fill();
      c.restore();
      // паутина
      const wa = st.webDone ? st.web : 1;
      if (wa > 0) { c.save(); c.globalAlpha = wa; c.strokeStyle = 'rgba(214,226,255,.24)'; c.lineWidth = 1.1;
        const [wx, wy] = WEB, sp = [[-118, -40], [-110, 30], [-60, 92], [8, 100], [76, 70], [86, -6], [70, -110], [0, -132], [-70, -118]];
        sp.forEach(([dx, dy]) => { c.beginPath(); c.moveTo(wx, wy); c.lineTo(wx + dx, wy + dy); c.stroke(); });
        for (let k = 1; k <= 7; k++) { c.beginPath(); sp.forEach(([dx, dy], i) => { const q = k / 8 * (.85 + .15 * Math.sin(i * 3 + k)); const px = wx + dx * q, py = wy + dy * q + Math.sin(G.t + i) * .6; i ? c.lineTo(px, py) : c.moveTo(px, py); }); c.closePath(); c.stroke(); }
        c.restore(); }
      // паук
      if (st.spider !== 'gone') {
        let sx = WEB[0], sy = WEB[1];
        if (st.spider === 'scare') { const k = Math.sin(clamp(st.spT / 1.6, 0, 1) * Math.PI); sy += k * 110; sx -= k * 40; }
        if (st.spider === 'flee') { const k = ease(clamp(st.spT / 1.4, 0, 1)); sy = lerp(WEB[1], LB[1] + 10, k); sx = lerp(WEB[0], LB[0] - 40, k); }
        c.strokeStyle = 'rgba(214,226,255,.25)'; c.lineWidth = 1; c.beginPath(); c.moveTo(sx, LB[1]); c.lineTo(sx, sy); c.stroke();
        c.fillStyle = '#0d0f17'; c.strokeStyle = '#0d0f17'; c.lineWidth = 2.2;
        for (let k = 0; k < 4; k++) { const w = Math.sin(G.t * 9 + k) * 2; c.beginPath(); c.moveTo(sx, sy); c.lineTo(sx - 18 - k * 2, sy - 12 + k * 9 + w); c.lineTo(sx - 26, sy - 2 + k * 10); c.moveTo(sx, sy); c.lineTo(sx + 18 + k * 2, sy - 12 + k * 9 - w); c.lineTo(sx + 26, sy - 2 + k * 10); c.stroke(); }
        ell(c, sx, sy + 9, 11, 13); c.fill(); ell(c, sx, sy - 5, 7, 7); c.fill();
        c.fillStyle = st.spider === 'scare' ? '#ff6b6b' : 'rgba(255,120,120,.5)'; ell(c, sx - 3, sy - 6, 1.5, 1.5); c.fill(); ell(c, sx + 3, sy - 6, 1.5, 1.5); c.fill();
      }
      // блок, верёвки, ведро, корзина, камень
      const yB = B0 - st.d, yC = C0 + st.d, ang = st.d / 20;
      c.strokeStyle = '#2b3245'; c.lineWidth = 2.2; c.beginPath(); c.moveTo(PX - 21, PY); c.lineTo(PX - 21, yB - 82); c.moveTo(PX + 21, PY); c.lineTo(PX + 21, yC - 52); c.stroke();
      c.fillStyle = '#0d1019'; ell(c, PX, PY, 23, 23); c.fill(); c.strokeStyle = 'rgba(190,210,240,.2)'; c.lineWidth = 2; ell(c, PX, PY, 23, 23); c.stroke();
      c.beginPath(); for (let k = 0; k < 4; k++) { const a = ang + k * Math.PI / 4; c.moveTo(PX + Math.cos(a) * 18, PY + Math.sin(a) * 18); c.lineTo(PX - Math.cos(a) * 18, PY - Math.sin(a) * 18); } c.stroke();
      c.fillStyle = '#0d1019'; c.fillRect(PX - 4, PY - 38, 8, 36);
      // корзина-противовес
      c.save(); c.translate(PX + 21, yC); c.fillStyle = '#121624'; c.beginPath(); c.moveTo(-24, -40); c.lineTo(24, -40); c.lineTo(18, 0); c.lineTo(-18, 0); c.closePath(); c.fill();
      c.strokeStyle = 'rgba(190,210,240,.12)'; c.lineWidth = 1.5; for (let k = 1; k < 4; k++) { c.beginPath(); c.moveTo(-24 + k * 1.5, -40 + k * 10); c.lineTo(24 - k * 1.5, -40 + k * 10); c.stroke(); }
      c.strokeStyle = '#2b3245'; c.lineWidth = 2; c.beginPath(); c.arc(0, -40, 22, Math.PI, 0); c.stroke(); c.restore();
      // камень
      let rx = R0[0], ry = R0[1], rr = 0;
      if (st.rock === 'branch') { rx += Math.sin(G.t * 30) * 3 * st.wob; }
      if (st.rock === 'roll') { const k = clamp(st.rockT / 1.1, 0, 1) ** 1.6; rx = lerp(R0[0], R1[0], k); ry = lerp(R0[1], R1[1], k); rr = k * 4; }
      if (st.rock === 'fall') { const k = clamp(st.rockT / .45, 0, 1); rx = PX + 22; ry = lerp(R1[1], yC - 22, k * k); rr = 4 + k; }
      if (st.rock === 'in') { rx = PX + 21; ry = yC - 22; rr = -4; }
      if (st.rock === 'branch') glow(c, rx, ry - 6, 46, '#cfe3ff', .1 + .05 * Math.sin(G.t * 1.3));
      c.save(); c.translate(rx, ry); c.rotate(rr); c.fillStyle = '#2a3043'; c.beginPath(); [[-18, 2], [-12, -14], [4, -17], [17, -6], [16, 10], [-2, 16], [-15, 12]].forEach(([x, y], i) => (i ? c.lineTo(x, y) : c.moveTo(x, y))); c.closePath(); c.fill();
      c.strokeStyle = 'rgba(214,230,255,.45)'; c.lineWidth = 2; c.beginPath(); c.moveTo(-18, 2); c.lineTo(-12, -14); c.lineTo(4, -17); c.lineTo(17, -6); c.stroke(); c.restore();
      drawHero(c, P);
      // ведро (передняя стенка поверх Огонька)
      c.save(); c.translate(PX - 21, yB); c.fillStyle = '#141826'; c.beginPath(); c.moveTo(-34, -54); c.lineTo(34, -54); c.lineTo(27, 0); c.lineTo(-27, 0); c.closePath(); c.fill();
      c.strokeStyle = 'rgba(190,210,240,.16)'; c.lineWidth = 2; c.beginPath(); c.moveTo(-34, -54); c.lineTo(34, -54); c.moveTo(-31, -30); c.lineTo(31, -30); c.stroke();
      c.strokeStyle = '#2b3245'; c.beginPath(); c.arc(0, -54, 30, Math.PI, 0); c.stroke(); c.restore();
      drawFlies(c);
      // папоротники переднего плана
      c.fillStyle = '#03050a';
      for (const f of st.ferns) { const s = Math.sin(G.t * .8 + f.ph) * 5; for (let k = -2; k <= 2; k++) blade(c, f.x, H + 10, f.x + k * f.h * .35 + s, H + 10 - f.h * (1 - Math.abs(k) * .18), f.b * .3 + k * 10, 9); }
      fog(c, P, K.fog2[0], K.fog2[1], 3, .08, 12);
    },
  };
  let hopT = 0;
  return sc;
}

/* ================= Сцена 3: Дом ================= */
function Home() {
  const P = PAL[2], st = { dand: false, head: 1, moth: 'sleep', mothT: 0, lamp: 0, feeding: false, feedT: 0, light: 0, door: 0, end: 0, enter: false };
  const K = LAND ? {
    g0: 610, gA: 18, moon: [220, 160, 62], starsY: 330, milky: [W / 2, 170], far: [[390, 40, 0, .4], [462, 26, 8, .6]], shrooms: [[140, 532, 34], [1190, 515, 44], [1240, 548, 26], [560, 540, 22]],
    fog: [480, 600], fog2: [660, 720], strip: 706, hx: 870, capTop: 120, rim: 336, stemTop: 318, win: 440, lamp: [672, 410], head: [440, 432], moth: [794, 486],
    flyH: 330, flyA: 220, heroIn: 330, blades: [20, 90, 200], tapY: 380, titleY: 112
  } : {
    g0: 1012, gA: 22, moon: [170, 330, 66], starsY: 600, milky: [W / 2 + 60, 300], far: [[760, 40, 0, .4], [850, 26, 8, .6]], shrooms: [[90, 880, 34], [610, 870, 44], [680, 900, 26]],
    fog: [860, 990], fog2: [1160, 1260], strip: 1210, hx: 500, capTop: 452, rim: 668, stemTop: 650, win: 780, lamp: [300, 742], head: [160, 805], moth: [424, 880],
    flyH: 520, flyA: 150, heroIn: 220, blades: [12, 120, 280], tapY: 760, titleY: 200
  };
  const ground = (x) => K.g0 - Math.sin(x / W * Math.PI) * K.gA;
  const HX = K.hx, SB = ground(HX) - 8, LAMP = K.lamp, MOTH = K.moth, HEAD = K.head, DOOR = SB - 8;
  let dfl = [], mfly = null;
  const sc = {
    pal: P, ground, tapY: K.tapY, titleY: K.titleY, minX: () => 40, maxX: () => (st.door > .9 ? HX : HX - 80),
    start() { hero.x = -40; dfl = [firefly(HEAD[0] - 10, HEAD[1] - 9), firefly(HEAD[0] + 10, HEAD[1] + 7)]; G.busy = true; walkTo(K.heroIn, () => { G.busy = false; say(HINTS.dand, 7); }); },
    hint() { return !st.dand ? 'dand' : st.moth === 'sleep' ? 'moth' : 'lamp'; },
    spots() {
      return [
        { id: 'dand', x: HEAD[0], y: HEAD[1], r: 66, on: !st.dand, walk: HEAD[0] - 52, act() { hero.face = 1; hero.puff = 1; st.dand = true; snd.whoosh();
          setTimeout(() => { for (let k = 0; k < 46; k++) { const a = Math.random() * TAU, rr = Math.random() * 30; G.parts.push({ x: HEAD[0] + Math.cos(a) * rr, y: HEAD[1] + Math.sin(a) * rr, vx: 40 + Math.random() * 120, vy: -30 - Math.random() * 70, life: 4 + Math.random() * 3, max: 7, k: 'seed', rot: Math.random() * 6, vr: (Math.random() - .5) * 2, ph: Math.random() * 6 }); }
            st.head = 0; dfl.forEach((f, i) => release(f, .3 + i * .3)); setTimeout(() => say(HINTS.moth, 6), 2400); }, 350); } },
        { id: 'moth', x: MOTH[0], y: MOTH[1], r: 46, on: st.moth === 'sleep', walk: MOTH[0] - 52, act() { st.moth = 'fly'; st.mothT = 0; snd.flutter(); } },
        { id: 'lamp', x: LAMP[0], y: LAMP[1], r: 54, on: !st.feeding && st.lamp < 1, walk: LAMP[0], act() {
          if (G.count < 9) { hero.think = 1.6; snd.nope(); G.idle = 99; say(HINTS.lampEarly, 5); return; }
          st.feeding = true; G.busy = true; hero.face = 1; } },
      ];
    },
    update(dt) {
      if (st.moth === 'fly') { st.mothT += dt / 5.2;
        if (st.mothT >= 1) { st.moth = 'home'; const f = firefly(MOTH[0], MOTH[1] - 10, true); release(f, .2); setTimeout(() => { if (st.lamp < 1) say(HINTS.lamp, 6); }, 1800); }
        const p = mothPos(st.mothT); if (Math.random() < .6) G.parts.push({ x: p[0], y: p[1], vx: 0, vy: 6, life: 1.4, max: 1.4, s: 2.2, col: '#cfc6ff', k: 'glow' });
        if (Math.random() < dt * 4) snd.flutter(); }
      if (st.feeding) { st.feedT -= dt;
        if (st.feedT <= 0 && G.swarm.length) { st.feedT = .26; const s = G.swarm.pop(); const f = { x: s.x || hero.x, y: s.y || hero.y - 80, st: 'lamp', t: 0, sx: s.x || hero.x, sy: s.y || hero.y - 80, ph: 0, a: 1 }; mfly = mfly || []; mfly.push(f); }
        if (mfly) for (const f of mfly) { f.t += dt / .7; const k = ease(clamp(f.t, 0, 1)); f.x = lerp(f.sx, LAMP[0], k) + Math.sin(k * Math.PI) * 40; f.y = lerp(f.sy, LAMP[1], k) - Math.sin(k * Math.PI) * 50;
          if (f.t >= 1 && !f.done) { f.done = true; st.lamp = Math.min(1, st.lamp + 1 / 9); snd.chime(Math.round(st.lamp * 9) - 1); } }
        if (st.lamp >= .999 && !G.swarm.length) { st.feeding = false; st.light = .001; snd.bloom(); mfly = null; G.count = 9; } }
      if (st.light) { st.light = Math.min(1, st.light + dt * .5); if (st.light >= 1 && !st.door) st.door = .001; }
      if (st.door && st.door < 1) { st.door = Math.min(1, st.door + dt * .8); if (st.door >= 1) { snd.creak(); walkTo(HX - 3, () => { st.enter = true; }); } }
      if (st.enter) { hero.alpha = Math.max(0, hero.alpha - dt * 1.4); if (hero.alpha <= 0) { st.end += dt; if (st.end > 1.6 && G.mode === 'play') finish(); } }
    },
    draw(c, g) {
      c.drawImage(layer(2, 0, (x) => { sky(x, P, 77); const [mx0, my0] = K.milky; x.save(); x.translate(mx0, my0); x.rotate(-.42); x.scale(1, .2);
        const gr = x.createRadialGradient(0, 0, 0, 0, 0, 560); gr.addColorStop(0, 'rgba(205,195,255,.11)'); gr.addColorStop(.6, 'rgba(205,195,255,.04)'); gr.addColorStop(1, 'rgba(205,195,255,0)');
        x.fillStyle = gr; x.fillRect(-560, -560, 1120, 1120); x.restore();
        const r = rng(78); for (let i = 0; i < (LAND ? 360 : 260); i++) { const t = r() * 2 - 1, d = (r() - .5) * 120 * (1 - Math.abs(t) * .6); const X = mx0 + t * 520 * Math.cos(-.42) - d * Math.sin(-.42), Y = my0 + t * 520 * Math.sin(-.42) + d * Math.cos(-.42);
          x.fillStyle = 'rgba(240,236,255,' + (r() * .45).toFixed(2) + ')'; x.fillRect(X, Y, 1.2, 1.2); } }, g), 0, 0, W, H);
      // мерцающие звёзды
      const r = rng(99); for (let i = 0; i < (LAND ? 36 : 26); i++) { const x = r() * W, y = r() * K.starsY, a = .5 + .5 * Math.sin(G.t * (1 + r() * 2) + i); glow(c, x, y, 7, '#fff6e0', a * .5); }
      // луна
      const [mx, my, mr] = K.moon;
      glow(c, mx, my, 300, '#d9d2ff', .16); glow(c, mx, my, 120, '#fff7e6', .3);
      c.fillStyle = '#f3ecd6'; ell(c, mx, my, mr, mr); c.fill();
      c.fillStyle = 'rgba(160,150,190,.16)'; [[-20, -14, 14], [18, 20, 10], [26, -22, 7], [-8, 30, 6], [-34, 12, 5]].forEach(([dx, dy, rr]) => { ell(c, mx + dx, my + dy, rr, rr); c.fill(); });
      c.drawImage(layer(2, 1, (x) => { const r2 = rng(4); K.far.forEach(([y, a, t, d]) => ridge(x, r2, y, a, mix(P.haze, P.ink, d), t));
        x.fillStyle = mix(P.haze, P.ink, .7); K.shrooms.forEach(([X, Y, s]) => { x.fillRect(X - s * .12, Y - s * 1.6, s * .24, s * 1.6); ell(x, X, Y - s * 1.6, s * .8, s * .45); x.fill(); }); }, g), 0, 0, W, H);
      fog(c, P, K.fog[0], K.fog[1], LAND ? 7 : 5, .15, 6);
      c.drawImage(layer(2, 2, (x) => { const r3 = rng(13), ink = mix(P.haze, P.ink, .93), T = K.stemTop, ct = K.capTop, rim = K.rim;
        x.fillStyle = ink; x.beginPath(); x.moveTo(-10, H + 10); for (let X = -10; X <= W + 10; X += 6) x.lineTo(X, ground(X) + 2); x.lineTo(W + 10, H + 10); x.fill();
        grass(x, r3, -10, W + 10, ground, ink, LAND ? 220 : 150, 22);
        // гриб-дом: ножка
        const sh = SB + 8 - T;
        x.beginPath(); x.moveTo(HX - 60, SB + 8); x.bezierCurveTo(HX - 48, SB + 8 - sh * .29, HX - 70, T + sh * .31, HX - 48, T); x.lineTo(HX + 48, T); x.bezierCurveTo(HX + 66, T + sh * .31, HX + 48, SB + 8 - sh * .29, HX + 60, SB + 8); x.closePath(); x.fill();
        // шляпка
        x.beginPath(); x.moveTo(HX - 250, rim); x.bezierCurveTo(HX - 230, ct + 68, HX - 100, ct, HX, ct); x.bezierCurveTo(HX + 110, ct, HX + 235, ct + 68, HX + 248, rim);
        for (let X = HX + 248; X >= HX - 250; X -= 20) x.quadraticCurveTo(X - 10, rim + 16 + Math.sin(X) * 3, X - 20, rim);
        x.closePath(); x.fill();
        x.fillStyle = 'rgba(210,200,255,.07)'; [[-80, 68, 22], [20, 48, 16], [110, 108, 26], [-150, 148, 18], [190, 168, 12], [-20, 138, 12]].forEach(([dx, dy, s]) => { ell(x, HX + dx, ct + dy * (rim - ct) / 216, s, s * .7); x.fill(); });
        x.strokeStyle = 'rgba(210,200,255,.12)'; x.lineWidth = 2; x.beginPath(); x.moveTo(HX - 238, rim - 28); x.bezierCurveTo(HX - 200, ct + 68, HX - 80, ct + 14, HX, ct + 12); x.stroke();
        // ступеньки и шнурок фонаря
        x.fillStyle = ink; [[HX - 30, SB + 8, 60, 8], [HX - 22, SB, 44, 8]].forEach(([X, Y, w, h]) => x.fillRect(X, Y, w, h));
        x.strokeStyle = '#1c1d33'; x.lineWidth = 2; x.beginPath(); x.moveTo(LAMP[0], rim); x.lineTo(LAMP[0], LAMP[1] - 26); x.stroke();
        x.fillStyle = P.ink; x.beginPath(); x.moveTo(-10, H + 10); x.lineTo(-10, K.strip - 10); for (let X = -10; X <= W + 10; X += 8) x.lineTo(X, K.strip + Math.sin(X * .02) * 14); x.lineTo(W + 10, H + 10); x.fill(); }, g), 0, 0, W, H);
      // окно и дверь
      const L = st.light, WX = HX - 3, WY = K.win;
      if (L) { const wg = c.createRadialGradient(WX, WY + 4, 2, WX, WY, 26); wg.addColorStop(0, rgba('#fff1c9', L)); wg.addColorStop(.55, rgba('#ffc46b', L)); wg.addColorStop(1, rgba('#e0782e', L));
        c.fillStyle = '#0b0c18'; ell(c, WX, WY, 24, 24); c.fill(); c.fillStyle = wg; ell(c, WX, WY, 24, 24); c.fill();
        c.fillStyle = rgba('#7a3a1c', .35 * L); ell(c, WX - 8, WY + 8, 7, 9); c.fill();                // силуэт чашки на подоконнике — дома уютно
      } else { c.fillStyle = '#0b0c18'; ell(c, WX, WY, 24, 24); c.fill(); }
      c.strokeStyle = L ? '#2a1d22' : 'rgba(210,200,255,.14)'; c.lineWidth = 3; ell(c, WX, WY, 26, 26); c.stroke(); c.beginPath(); c.moveTo(WX - 24, WY); c.lineTo(WX + 24, WY); c.moveTo(WX, WY - 24); c.lineTo(WX, WY + 24); c.stroke();
      if (L) { glow(c, WX, WY, 120, WARM, .4 * L); }
      const door = () => { c.beginPath(); c.moveTo(HX - 28, DOOR); c.lineTo(HX - 28, DOOR - 56); c.arc(HX - 3, DOOR - 56, 25, Math.PI, 0); c.lineTo(HX + 22, DOOR); c.closePath(); };
      c.fillStyle = '#07080f'; door(); c.fill();
      if (st.door) { c.save(); door(); c.clip();
        c.fillStyle = rgba(WARM, .9 * st.door); c.fillRect(HX - 28, DOOR - 96, 50, 100); c.fillStyle = '#120d18'; c.fillRect(HX - 28 + 50 * st.door * .85, DOOR - 96, 50, 100); c.restore();
        glow(c, HX - 3, DOOR - 16, 160, WARM, .3 * st.door); }
      // фонарь
      const lb = st.lamp, [lx, ly] = LAMP, sw = Math.sin(G.t * .9) * .05;
      c.save(); c.translate(lx, ly - 26); c.rotate(sw); c.translate(0, 26);
      if (lb > 0) { glow(c, 0, 0, 60 + 160 * lb, GOLD, .2 + .45 * lb); }
      c.fillStyle = rgba('#ffd98a', .08 + .75 * lb); A.rr(c, -14, -18, 28, 36, 6); c.fill();
      c.strokeStyle = '#1c1d33'; c.lineWidth = 3; A.rr(c, -14, -18, 28, 36, 6); c.stroke(); c.beginPath(); c.moveTo(0, -18); c.lineTo(0, 18); c.stroke();
      c.fillStyle = '#1c1d33'; c.beginPath(); c.moveTo(-18, -18); c.lineTo(18, -18); c.lineTo(8, -28); c.lineTo(-8, -28); c.closePath(); c.fill(); c.fillRect(-12, 18, 24, 5);
      c.restore();
      if (L) glow(c, lx, ground(lx), 260, GOLD, .18 * L);
      // одуванчик
      const ds = Math.sin(G.t * .8) * 3, [hx0, hy0] = HEAD; c.fillStyle = mix(P.haze, P.ink, .9); blade(c, hx0 - 10, ground(hx0 - 10) + 2, hx0 + ds, hy0 + 7, 14, 4);
      if (st.head > 0) { c.strokeStyle = 'rgba(232,228,248,.55)'; c.lineWidth = 1; for (let k = 0; k < 60; k++) { const a = k * 2.4, l = 22 + (k % 3) * 4; c.beginPath(); c.moveTo(hx0 + ds, hy0); c.lineTo(hx0 + ds + Math.cos(a) * l, hy0 + Math.sin(a) * l); c.stroke(); c.fillStyle = 'rgba(240,236,255,.6)'; ell(c, hx0 + ds + Math.cos(a) * l, hy0 + Math.sin(a) * l, 1.6, 1.6); c.fill(); }
        glow(c, hx0 + ds, hy0, 46, '#e8e2ff', .12); }
      c.fillStyle = mix(P.haze, P.ink, .8); ell(c, hx0 + ds, hy0 + 1, 5, 5); c.fill();
      // мотылёк
      let mx2 = MOTH[0], my2 = MOTH[1], open = .1 + .05 * Math.sin(G.t * .7);
      if (st.moth === 'fly') { [mx2, my2] = mothPos(st.mothT); open = .5 + .5 * Math.sin(G.t * 30); }
      moth(c, mx2, my2, open, st.moth !== 'fly' ? 0 : Math.sin(G.t * 3) * .3);
      if (mfly) for (const f of mfly) if (!f.done) { glow(c, f.x, f.y, 22, GOLD, .6); c.fillStyle = '#fff3c4'; ell(c, f.x, f.y, 2.2, 2.2); c.fill(); }
      drawHero(c, P); drawFlies(c);
      // передний план
      c.fillStyle = '#020309'; const rr2 = rng(41), [nb, h0, h1] = K.blades;
      for (let i = 0; i < nb; i++) { const x = rr2() * W, h = h0 + rr2() * (h1 - h0), s = Math.sin(G.t * .7 + i) * 4; blade(c, x, H + 10, x + (rr2() - .5) * 90 + s, H + 10 - h, (rr2() - .5) * 40, 12); }
      fog(c, P, K.fog2[0], K.fog2[1], 3, .07, 15);
    },
  };
  function mothPos(t) { const e = ease(t); return [MOTH[0] + Math.sin(e * TAU * 1.5) * K.flyA * Math.sin(e * Math.PI), MOTH[1] - Math.sin(e * Math.PI) * K.flyH]; }
  return sc;
}
function moth(c, x, y, open, tilt) {
  c.save(); c.translate(x, y); c.rotate(tilt);
  const w = 6 + 18 * open;
  c.fillStyle = '#c9c0e6'; c.globalAlpha = .85;
  c.beginPath(); c.moveTo(0, -6); c.quadraticCurveTo(-w - 6, -18, -w, 6); c.quadraticCurveTo(-6, 4, 0, 6); c.closePath(); c.fill();
  c.beginPath(); c.moveTo(0, -6); c.quadraticCurveTo(w + 6, -18, w, 6); c.quadraticCurveTo(6, 4, 0, 6); c.closePath(); c.fill();
  c.fillStyle = '#6d6390'; ell(c, -w * .55, -2, 2.6 * open + .5, 2.6 * open + .5); c.fill(); ell(c, w * .55, -2, 2.6 * open + .5, 2.6 * open + .5); c.fill();
  c.globalAlpha = 1; c.fillStyle = '#2a2540'; ell(c, 0, 0, 3, 9); c.fill();
  c.strokeStyle = '#2a2540'; c.lineWidth = 1.2; c.beginPath(); c.moveTo(-1, -8); c.quadraticCurveTo(-6, -16, -9, -15); c.moveTo(1, -8); c.quadraticCurveTo(6, -16, 9, -15); c.stroke();
  glow(c, 0, 0, 30, '#d8d0ff', .12 + .1 * open);
  c.restore();
}

const SCENES = [Pond, Tree, Home];

/* Подсказки (24.10, владелец: «ничего не понятно, что делать, в чём смысл»): короткая строка внизу — что сейчас можно
   сделать. Сама — в начале сцены и после ошибки; по кнопке «?» — всегда; после 10 с без дела — снова. */
const HINTS = {
  cloud: 'Тучка закрыла луну, и светлячки спят. Нажмите на тучку.',
  dark: 'Темно — светлячки спят. Сначала пусть выглянет луна.',
  reeds: 'Луна разбудила светлячков в камышах. Нажмите на камыши.',
  lily: 'Ещё один светлячок прячется под кувшинкой на воде.',
  bell: 'Лягушка спит на мостике. Её разбудит звон колокольчика.',
  frog: 'Лягушка храпит и не пускает. Может, её что-то разбудит?',
  more: 'Огонёк собрал ещё не всех светлячков здесь.',
  exit: 'Путь свободен — нажмите справа, Огонёк пойдёт дальше.',
  owl: 'Паук стережёт светлячков в паутине. Кто его спугнёт? Разбудите сову в дупле.',
  spider: 'Паук не пускает. Нужен кто-то, кого он боится.',
  web: 'Паук убежал — нажмите на паутину и освободите светлячков.',
  bucket: 'Наверх — на подъёмнике. Нажмите на ведро.',
  rock: 'Нужен груз для подъёмника — столкните камень с ветки.',
  rockEarly: 'Камень легко качается… Но сначала сядьте в ведро.',
  dand: 'В одуванчике прячутся светлячки — сдуйте его.',
  moth: 'Ночная бабочка знает, где последний светлячок. Нажмите на неё.',
  lamp: 'Все девять здесь! Зажгите фонарь у дома.',
  lampEarly: 'Фонарю нужны все девять светлячков.',
};
function say(text, sec = 6) { if (G && G.mode === 'play' && text) G.cap = { text, t: 0, life: sec }; }


/* ---------------- экраны ---------------- */
let GAME = null;
function titleScreen(g) {
  newGame('title'); g.setPlaying(false);
  g.screen({
    kicker: A.framed ? 'Досуг' : 'Аркада', title: 'Огонёк',
    html: '<p>Огонёк потерял свой свет. Нажимайте на предметы и зверей — тучку, камыши, сову, цветы — и помогите ему собрать девять светлячков и вернуться домой.</p><p style="opacity:.75">Подсказка — кнопка <b>?</b> в углу. Лучше со звуком.</p>',
    button: 'Начать', onGo: () => { newGame('play'); g.setPlaying(true); }
  });
}
function finish() {
  const g = GAME; if (G.mode !== 'play') return; G.mode = 'end'; g.setPlaying(false);
  const s = Math.round(G.time), mm = Math.floor(s / 60), ss = String(s % 60).padStart(2, '0');
  g.screen({
    kicker: 'Конец сказки', title: 'Огонёк дома',
    html: '<p>Все девять светлячков нашли дорогу, и в окне теперь горит свет. Время: ' + mm + ':' + ss + '.</p>',
    button: 'Ещё раз', onGo: () => { newGame('play'); g.setPlaying(true); }, alt: { label: A.framed ? 'К играм' : 'В аркаду', onGo: () => A.home('../index.html') }
  });
}

/* ---------------- цикл ---------------- */
function spotsOn() { return G.sc.spots().filter((s) => s.on); }
function activate(s) {
  G.idle = 0;
  if (s.walk != null) { G.busy = true; walkTo(s.walk, () => { G.busy = false; hero.face = Math.sign(s.x - hero.x) || hero.face; s.act(); }); }
  else { hero.face = Math.sign(s.x - hero.x) || hero.face; s.act(); }
}
const QB = [W - 50, 52];                         // кнопка «?» в углу поля
function update(g, dt) {
  G.t += dt;
  if (G.fadeDir) { G.fade = clamp(G.fade + G.fadeDir * dt * 1.4, 0, 1); if (G.fade >= 1 && G.fadeThen) { const f = G.fadeThen; G.fadeThen = null; f(); } if (G.fade <= 0 && G.fadeDir < 0) G.fadeDir = 0; }
  if (G.mode === 'title') { G.sc.update(dt); updFlies(dt); updParts(dt); return; }
  if (G.mode === 'play' && !G.fadeThen) G.time += dt;
  G.title.t += dt; G.idle += dt;
  if (G.cap) { G.cap.t += dt; if (G.cap.t > G.cap.life) G.cap = null; }
  if (G.idle > 10 && !G.cap && !G.busy) { say(HINTS[G.sc.hint()], 6); G.idle = 4; }        // давно ничего — подскажем
  G.sparkT -= dt;
  if (G.sparkT <= 0 && !G.busy) { G.sparkT = 2.2;                                          // живое тихо искрится
    for (const s of spotsOn()) if (s.id !== 'exit') for (let k = 0; k < 2; k++) { const a = Math.random() * TAU, d = s.r * (.3 + Math.random() * .4);
      G.parts.push({ x: s.x + Math.cos(a) * d, y: s.y + Math.sin(a) * d * .7, vx: 0, vy: -10, life: 1.2, max: 1.2, s: 1.6, col: '#fff1c4', k: 'glow' }); } }
  ambience(dt);
  G.sc.update(dt); updHero(dt); updFlies(dt); updParts(dt);
  if (G.mode !== 'play' || G.busy || G.fadeThen) return;
  const inp = g.input, list = spotsOn().sort((a, b) => a.x - b.x);
  if (inp.pressed('left') || inp.pressed('right') || inp.pressed('up') || inp.pressed('down')) {
    G.kb = true; const d = inp.pressed('left') || inp.pressed('up') ? -1 : 1; G.focus = (G.focus + d + list.length) % Math.max(1, list.length); }
  if (G.kb && (inp.pressed('action') || inp.pressed('start')) && list[G.focus]) activate(list[G.focus]);
  if (inp.tap) {
    G.kb = false; const { x, y } = inp.tap;
    if (Math.hypot(x - QB[0], y - QB[1]) < 40) { say(HINTS[G.sc.hint()], 7); G.idle = 0; return; }     // «?» — подсказка
    const hit = list.filter((s) => Math.hypot(s.x - x, s.y - y) < s.r).sort((a, b) => Math.hypot(a.x - x, a.y - y) - Math.hypot(b.x - x, b.y - y))[0];
    if (hit) activate(hit);
    else if (y > G.sc.tapY) { G.idle = Math.min(G.idle, 4); if (!walkTo(x)) hero.think = .9; }
  }
}
function draw(c, g) {
  G.sc.draw(c, g);
  drawParts(c);
  // подсказка: после долгой паузы мягко светится то, что пора тронуть
  if (G.mode === 'play' && !G.busy) {
    const list = spotsOn().sort((a, b) => a.x - b.x);
    const show = (s, a) => { const p = 1 + .08 * Math.sin(G.t * 3); c.strokeStyle = rgba('#ffe6b0', a); c.lineWidth = 2; c.setLineDash([6, 8]); c.lineDashOffset = -G.t * 12; ell(c, s.x, s.y, s.r * .8 * p, s.r * .8 * p); c.stroke(); c.setLineDash([]); };
    if (G.kb && list[G.focus]) show(list[G.focus], .6);
    else if (G.cap) { const h = list.find((s) => s.id === G.sc.hint()); if (h) show(h, .3 + .2 * Math.sin(G.t * 2)); }
  }
  finishFrame(c, g);
  // название сцены
  if (G.mode === 'play' && G.title.t < 4) { const a = clamp(Math.min(G.title.t - .6, 3.4 - G.title.t), 0, 1);
    A.text(c, G.title.text, W / 2, G.sc.titleY, { size: 46, weight: 600, color: rgba(EYE, a * .85) });
    A.text(c, (G.si + 1) + ' из 3', W / 2, G.sc.titleY + 50, { size: 22, weight: 500, color: rgba(EYE, a * .45) }); }
  // подсказка строкой внизу: тёмное стекло, светлый текст
  if (G.mode === 'play' && G.cap) {
    const k = G.cap, a = clamp(Math.min(k.t / .4, (k.life - k.t) / .6), 0, 1), size = LAND ? 26 : 28;
    c.font = '600 ' + size + 'px ' + A.FONT; const lines = []; let line = '';
    for (const w of k.text.split(' ')) { const t = line ? line + ' ' + w : w; if (c.measureText(t).width > W - 160 && line) { lines.push(line); line = w; } else line = t; }
    lines.push(line);
    const bw = Math.min(W - 80, Math.max(...lines.map((l) => c.measureText(l).width)) + 64), bh = lines.length * (size + 10) + 28, by = H - bh - (LAND ? 26 : 70);
    c.save(); c.globalAlpha = a; A.rr(c, (W - bw) / 2, by, bw, bh, 22); c.fillStyle = 'rgba(12,14,30,.72)'; c.fill();
    c.strokeStyle = 'rgba(255,236,190,.22)'; c.lineWidth = 1.5; c.stroke();
    lines.forEach((l, i) => A.text(c, l, W / 2, by + 14 + size * .5 + 2 + i * (size + 10), { size, weight: 600, color: '#fff3d6' }));
    c.restore();
  }
  // «?» — подсказка
  if (G.mode === 'play') { const p = G.idle > 8 ? .5 + .3 * Math.sin(G.t * 4) : .35;
    c.fillStyle = 'rgba(12,14,30,.45)'; ell(c, QB[0], QB[1], 24, 24); c.fill(); c.strokeStyle = rgba('#fff1c4', p); c.lineWidth = 2; ell(c, QB[0], QB[1], 24, 24); c.stroke();
    A.text(c, '?', QB[0], QB[1] + 2, { size: 26, weight: 800, color: rgba('#fff1c4', p + .3) }); }
  // счётчик светлячков
  if (G.mode === 'play') for (let k = 0; k < 9; k++) { const x = 44 + k * 22, y = 56, on = k < G.count;
    if (on) glow(c, x, y, 16, GOLD, .5); c.fillStyle = on ? '#ffe7a8' : 'rgba(244,240,220,.16)'; ell(c, x, y, on ? 4 : 3, on ? 4 : 3); c.fill(); }
  if (G.fade > 0) { c.fillStyle = 'rgba(2,3,8,' + G.fade + ')'; c.fillRect(0, 0, W, H); }
}

A.game({
  id: 'glow', title: 'Огонёк', width: W, height: H, orientation: LAND ? 'landscape' : 'portrait', tone: 'dark',
  keys: { KeyA: 'none', KeyD: 'none', KeyW: 'none', KeyS: 'none' },
  help: { desktop: 'Щёлкайте по предметам и зверям · <kbd>?</kbd> в углу — подсказка · стрелки и <kbd>Enter</kbd> — выбрать', short: 'Нажимайте на предметы и зверей', touch: 'Касайтесь предметов и зверей · «?» — подсказка' },
  init(g) { GAME = g; titleScreen(g); window.__glow = () => ({ G, hero }); },
  update, draw
});
})();
