/* =====================================================================
   Аркада — общий каркас для игр.
   Даёт каждой игре: масштаб под любой экран (ПК, телефон, полный экран),
   ввод (клавиатура, мышь, касания, свайпы, геймпад), звук и музыку,
   эффекты (искры, всплывающие очки, кольца), экраны меню, рекорды.

   Как устроена игра:
     Arcade.game({
       id: 'plane', title: 'Небесный пилот',
       width: 720, height: 1280,          // логический размер поля
       orientation: 'portrait',           // для телефона в полноэкранном режиме
       music: 'sky',                      // мелодия из Arcade.SONGS
       help: { desktop: '...', touch: '...' },
       touch: { left: [{id:'left',label:'◀'}], right: [{id:'action',label:'Прыжок',big:true}] },
       init(g) {}, update(g, dt) {}, draw(ctx, g) {}
     });
===================================================================== */
(function () {
'use strict';
const A = window.Arcade = {};

/* ---------- хранилище ---------- */
A.store = {
  get(k, d) { try { const v = localStorage.getItem(k); return v == null ? d : v; } catch (e) { return d; } },
  set(k, v) { try { localStorage.setItem(k, String(v)); } catch (e) { /* без сохранения */ } }
};
A.best = (id) => +A.store.get('arcade.best.' + id, '0') || 0;

/* ---------- устройство ---------- */
A.isTouch = matchMedia('(pointer: coarse)').matches || (navigator.maxTouchPoints > 0 && !matchMedia('(pointer: fine)').matches);
A.reduceMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
const params = new URLSearchParams(location.search);
A.shot = params.has('shot');
/* Внутри Dewiar (блокнот у виджета на компьютере, «Досуг» на телефоне) игра — во фрейме: «Назад» и «В аркаду» не
   уходят со страницы, а просят хозяина показать полку игр (postMessage {arcade: 'home'}); «во весь экран» — тоже просьба хозяину (лист «Досуг» на весь экран, pad.js padFull; 24.10). */
if (params.get('light') === '1') document.documentElement.classList.add('light');
/* в приложении на телефоне (app.js gameOpen: ?phone=1): поле без скруглений и полей — экран маленький; «во весь экран» —
   просьба хозяину спрятать панели системы (24.10, владелец: «на телефоне скругления излишни», «не хватает „во весь экран“») */
A.phone = params.get('phone') === '1';
if (A.phone) document.documentElement.classList.add('phone');   // светлая тема Dewiar — arcade.css :root.light
A.framed = (() => { try { return window.self !== window.top; } catch (e) { return true; } })();
/* сбой игры — хозяину (телефон пишет его в свой журнал: так он попадёт в отчёт «Сообщить о проблеме») */
A.report = (text) => { if (A.framed) { try { window.parent.postMessage({ arcade: 'log', text: String(text).slice(0, 300) }, '*'); } catch (e) { /* хозяина нет */ } } };
addEventListener('error', (e) => A.report('ошибка: ' + (e.message || e) + (e.lineno ? ' (строка ' + e.lineno + ')' : '')));
addEventListener('unhandledrejection', (e) => A.report('ошибка: ' + ((e.reason && e.reason.message) || e.reason)));
A.home = (href) => { if (A.framed) { try { window.parent.postMessage({ arcade: 'home' }, '*'); } catch (e) { /* хозяина нет */ } } else location.href = href; };

/* ---------- математика ---------- */
A.rand = (a, b) => a + Math.random() * (b - a);
A.randInt = (a, b) => Math.floor(A.rand(a, b + 1));
A.pick = (arr) => arr[(Math.random() * arr.length) | 0];
A.clamp = (v, a, b) => (v < a ? a : v > b ? b : v);
A.lerp = (a, b, t) => a + (b - a) * t;
A.dist = (ax, ay, bx, by) => Math.hypot(ax - bx, ay - by);
A.ease = {
  outCubic: (t) => 1 - Math.pow(1 - t, 3),
  inOutSine: (t) => -(Math.cos(Math.PI * t) - 1) / 2,
  outBack: (t) => { const c1 = 1.70158, c3 = c1 + 1; return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2); },
  outElastic: (t) => (t === 0 || t === 1 ? t : Math.pow(2, -10 * t) * Math.sin((t * 10 - .75) * (2 * Math.PI) / 3) + 1)
};

/* ---------- рисование ---------- */
A.FONT = '"Rubik", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif';
A.rr = (ctx, x, y, w, h, r) => {
  r = Math.max(0, Math.min(r, w / 2, h / 2));
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
};
A.text = (ctx, str, x, y, o = {}) => {
  const size = o.size || 32;
  ctx.font = `${o.weight || 800} ${size}px ${A.FONT}`;
  ctx.textAlign = o.align || 'center';
  ctx.textBaseline = o.base || 'middle';
  if (o.stroke) {
    ctx.lineJoin = 'round';
    ctx.lineWidth = o.strokeW || Math.max(4, size * .22);
    ctx.strokeStyle = o.stroke;
    ctx.strokeText(str, x, y);
  }
  ctx.fillStyle = o.color || '#fff';
  ctx.fillText(str, x, y);
};
A.heart = (ctx, x, y, s, fill, line) => {
  ctx.save(); ctx.translate(x, y); ctx.scale(s / 32, s / 32);
  ctx.beginPath();
  ctx.moveTo(0, 10);
  ctx.bezierCurveTo(-26, -6, -14, -26, 0, -12);
  ctx.bezierCurveTo(14, -26, 26, -6, 0, 10);
  ctx.closePath();
  ctx.fillStyle = fill; ctx.fill();
  if (line) { ctx.lineWidth = 3.5; ctx.strokeStyle = line; ctx.lineJoin = 'round'; ctx.stroke(); }
  ctx.beginPath(); ctx.ellipse(-8, -10, 4, 2.6, -.6, 0, Math.PI * 2); ctx.fillStyle = 'rgba(255,255,255,.75)'; ctx.fill();
  ctx.restore();
};
A.star = (ctx, x, y, r, points = 5, inner = .5) => {
  ctx.beginPath();
  for (let i = 0; i < points * 2; i++) {
    const a = -Math.PI / 2 + i * Math.PI / points, rr = i % 2 ? r * inner : r;
    i ? ctx.lineTo(x + Math.cos(a) * rr, y + Math.sin(a) * rr) : ctx.moveTo(x + Math.cos(a) * rr, y + Math.sin(a) * rr);
  }
  ctx.closePath();
};

/* ---------- звук ---------- */
const S = A.sound = { ctx: null, master: null, sfx: null, mus: null, echo: null, pulse: null, noise: null, musicOn: A.store.get('arcade.music', '1') === '1' };
S.init = () => {
  if (S.ctx) { if (S.ctx.state === 'suspended') S.ctx.resume(); return; }
  const AC = window.AudioContext || window.webkitAudioContext;
  if (!AC) return;
  try {
    const c = S.ctx = new AC();
    S.master = c.createGain(); S.master.gain.value = .85;
    const comp = c.createDynamicsCompressor(); comp.threshold.value = -14; comp.ratio.value = 4;
    S.master.connect(comp); comp.connect(c.destination);
    S.sfx = c.createGain(); S.sfx.gain.value = .75; S.sfx.connect(S.master);
    S.mus = c.createGain(); S.mus.gain.value = S.musicOn ? .5 : 0; S.mus.connect(S.master);
    // мягкое эхо для музыки
    const d = c.createDelay(1); d.delayTime.value = .27;
    const fb = c.createGain(); fb.gain.value = .28;
    const lp = c.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = 2600;
    S.echo = c.createGain(); S.echo.gain.value = .35;
    S.echo.connect(d); d.connect(lp); lp.connect(fb); fb.connect(d); lp.connect(S.mus);
    const n = 32, re = new Float32Array(n), im = new Float32Array(n);
    for (let i = 1; i < n; i++) re[i] = 2 / (i * Math.PI) * Math.sin(i * Math.PI * .25);
    S.pulse = c.createPeriodicWave(re, im);
    S.noise = c.createBuffer(1, c.sampleRate, c.sampleRate);
    const ch = S.noise.getChannelData(0); for (let i = 0; i < ch.length; i++) ch[i] = Math.random() * 2 - 1;
  } catch (e) { S.ctx = null; }
};
S.now = () => (S.ctx ? S.ctx.currentTime : 0);
S.tone = (f, t, dur, vol, wave = 'triangle', dest, f2, attack = .006) => {
  if (!S.ctx) return;
  const o = S.ctx.createOscillator(), g = S.ctx.createGain();
  if (wave === 'pulse') o.setPeriodicWave(S.pulse); else o.type = wave;
  o.frequency.setValueAtTime(f, t);
  if (f2) o.frequency.exponentialRampToValueAtTime(Math.max(20, f2), t + dur);
  g.gain.setValueAtTime(.0001, t);
  g.gain.linearRampToValueAtTime(vol, t + attack);
  g.gain.exponentialRampToValueAtTime(.0001, t + dur);
  o.connect(g); g.connect(dest || S.sfx);
  o.start(t); o.stop(t + dur + .05);
  return g;
};
S.hiss = (t, dur, vol, type = 'highpass', freq = 3000, dest) => {
  if (!S.ctx) return;
  const s = S.ctx.createBufferSource(), f = S.ctx.createBiquadFilter(), g = S.ctx.createGain();
  s.buffer = S.noise; f.type = type; f.frequency.value = freq;
  g.gain.setValueAtTime(vol, t); g.gain.exponentialRampToValueAtTime(.0001, t + dur);
  s.connect(f); f.connect(g); g.connect(dest || S.sfx);
  s.start(t, Math.random() * .5); s.stop(t + dur + .05);
};
const lastPlay = {};
S.play = (name, o = {}) => {
  if (!S.ctx) return;
  const t = S.now(), p = o.pitch || 1, v = o.vol == null ? 1 : o.vol;
  if (lastPlay[name] && t - lastPlay[name] < (o.gap || .03)) return;
  lastPlay[name] = t;
  switch (name) {
    case 'shoot': S.tone(900 * p, t, .06, .045 * v, 'pulse', null, 600 * p); break;
    case 'hit': S.tone(260 * p, t, .08, .1 * v, 'square', null, 140 * p); S.hiss(t, .05, .08 * v, 'bandpass', 2400); break;
    case 'boom': S.hiss(t, .45, .35 * v, 'lowpass', 700); S.tone(130 * p, t, .4, .35 * v, 'sine', null, 38); break;
    case 'bigboom': S.hiss(t, .9, .45 * v, 'lowpass', 500); S.tone(90, t, .9, .45 * v, 'sine', null, 28); S.tone(180, t + .05, .6, .15 * v, 'square', null, 40); break;
    case 'coin': S.tone(988 * p, t, .07, .09 * v, 'square'); S.tone(1319 * p, t + .06, .16, .08 * v, 'triangle'); break;
    case 'power': [523, 659, 784, 1047, 1319].forEach((f, i) => S.tone(f * p, t + i * .055, .14, .08 * v, 'pulse')); break;
    case 'jump': S.tone(320 * p, t, .16, .12 * v, 'triangle', null, 720 * p); S.tone(640 * p, t, .1, .03 * v, 'pulse', null, 1300 * p); break;
    case 'land': S.tone(140 * p, t, .07, .12 * v, 'sine', null, 70); break;
    case 'bounce': S.tone(520 * p, t, .09, .1 * v, 'sine', null, 680 * p); break;
    case 'pling': S.tone(880 * p, t, .22, .1 * v, 'triangle'); S.tone(1760 * p, t, .12, .03 * v, 'sine'); break;
    case 'eat': S.tone(420 * p, t, .09, .12 * v, 'triangle', null, 900 * p); S.tone(1200 * p, t + .05, .08, .05 * v, 'sine'); break;
    case 'click': S.tone(1100, t, .04, .06 * v, 'square'); break;
    case 'hurt': S.tone(480 * p, t, .3, .14 * v, 'square', null, 110); break;
    case 'lose': [523, 466, 415, 349].forEach((f, i) => S.tone(f * p, t + i * .16, .22, .1 * v, 'triangle')); break;
    case 'win': [523, 659, 784, 1047, 784, 1047, 1319].forEach((f, i) => S.tone(f * p, t + i * .09, .2, .09 * v, 'pulse')); break;
    case 'whoosh': S.hiss(t, .3, .12 * v, 'bandpass', 900); break;
    case 'beep': S.tone(660 * p, t, .12, .1 * v, 'sine'); break;
    default: break;
  }
};

/* мелодии: 8 тактов по 8 восьмых */
const SEMI = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };
const nf = (n) => { const m = /^([A-G])(#?)(\d)$/.exec(n); return 440 * Math.pow(2, (12 * (+m[3] + 1) + SEMI[m[1]] + (m[2] ? 1 : 0) - 69) / 12); };
const song = (bpm, lead, bass, chords, opt = {}) => ({ bpm, lead: lead.map((n) => (n ? nf(n) : 0)), bass: bass.map(nf), chords: chords.map((c) => c.map(nf)), ...opt });
const C_ = ['C4', 'E4', 'G4'], F_ = ['F4', 'A4', 'C5'], G_ = ['G4', 'B4', 'D5'], Am = ['A4', 'C5', 'E5'], D_ = ['D4', 'F#4', 'A4'], Em = ['E4', 'G4', 'B4'], Dm = ['D4', 'F4', 'A4'], Bm = ['B3', 'D4', 'F#4'], B_ = ['B3', 'D#4', 'F#4'];
A.SONGS = {
  sky: song(150, [
    'G5','E5','G5','C6','B5','G5','A5','B5', 'C6','A5','F5','A5','C6','D6','C6','A5',
    'B5','G5','D5','G5','B5','C6','D6','B5', 'C6',0,'G5',0,'E5','G5','C6',0,
    'A5','C6','E6','C6','A5','E5','A5','C6', 'F5','A5','C6','F6','E6','C6','A5','F5',
    'G5','B5','D6','G6','F6','D6','B5','G5', 'C6','E6','G6','E6','C6',0,0,0
  ], ['C3','F2','G2','C3','A2','F2','G2','C3'], [C_, F_, G_, C_, Am, F_, G_, C_], { wave: 'pulse' }),
  neon: song(140, [
    'E5','A5','C6','B5','A5',0,'E5',0, 'F5','A5','C6','A5','G5',0,'F5',0,
    'E5','G5','C6','D6','E6',0,'D6','C6', 'B5',0,'G5',0,'D5','E5','G5',0,
    'A5',0,'A5','C6','B5','A5','G5','E5', 'F5',0,'F5','A5','G5','F5','E5','C5',
    'E5','G5','C6','G5','E6','D6','C6','G5', 'D6',0,'B5',0,'G5',0,0,0
  ], ['A2','F2','C3','G2','A2','F2','C3','G2'], [Am, F_, C_, G_, Am, F_, C_, G_], { wave: 'pulse' }),
  candy: song(132, [
    'G5','B5','D6','B5','G5',0,'D5',0, 'E5','G5','C6','G5','E5',0,'C5',0,
    'F#5','A5','D6','A5','F#5','A5','D6','F#6', 'G6',0,'D6',0,'B5',0,'G5',0,
    'E5','G5','B5','E6','D6','B5','G5','B5', 'C6','E6','G6','E6','C6','G5','E5','G5',
    'D6','C6','B5','A5','B5','C6','D6','F#6', 'G6','D6','B5','D6','G6',0,0,0
  ], ['G2','C3','D3','G2','E2','C3','D3','G2'], [G_, C_, D_, G_, Em, C_, D_, G_], { wave: 'square', leadVol: .045 }),
  garden: song(112, [
    'D5',0,'F5','A5','G5',0,'F5','E5', 'D5',0,'B4','D5','G5',0,0,0,
    'F5','E5','D5','F5','A5',0,'C6','A5', 'G5',0,'E5',0,'C5',0,0,0,
    'D5','F5','A5','D6','C6','A5','G5','F5', 'G5','B5','D6','B5','G5',0,'F5','G5',
    'A5',0,'E5','A5','C6','B5','A5','G5', 'F5','E5','D5',0,'D5',0,0,0
  ], ['D3','G2','D3','C3','D3','G2','A2','D3'], [Dm, G_, Dm, C_, Dm, G_, Am, Dm], { wave: 'triangle', leadVol: .11, drums: 'soft' }),
  road: song(168, [
    'E5','E5','G5','E5','B5','E5','A5','G5', 'E5','E5','G5','E5','C6','B5','G5','E5',
    'D5','D5','F#5','D5','A5','D5','B5','A5', 'F#5','D5','B4','D5','F#5','A5','B5',0,
    'E6','D6','B5','G5','E5','G5','B5','D6', 'C6','B5','G5','E5','C5','E5','G5','C6',
    'D6','C6','A5','F#5','D5','F#5','A5','C6', 'B5',0,'F#5',0,'D#5',0,'B4',0
  ], ['E2','C3','D3','B2','E2','C3','D3','B2'], [Em, C_, D_, Bm, Em, C_, D_, B_], { wave: 'pulse' })
};
const M = S.music = { timer: null, name: null, step: 0, next: 0 };
function musicStep(sg, i, t) {
  const beat = 60 / sg.bpm / 2, bar = i >> 3, s = i & 7;
  const f = sg.lead[i];
  if (f) {
    const g1 = S.tone(f, t, beat * .95, sg.leadVol || .055, sg.wave || 'pulse', S.mus);
    S.tone(f * 1.003, t, beat * .9, (sg.leadVol || .055) * .5, 'triangle', S.echo);
    void g1;
  }
  const chord = sg.chords[bar];
  S.tone(chord[s % 3] * (s & 4 ? 2 : 1), t, beat * .7, .028, 'sine', S.mus);
  S.tone(sg.bass[bar] * (s % 2 ? 2 : 1), t, beat * .85, .16, 'triangle', S.mus);
  if (sg.drums === 'soft') {
    if (s === 0 || s === 4) S.tone(120, t, .1, .18, 'sine', S.mus, 50);
    if (s % 2) S.hiss(t, .03, .012, 'highpass', 8000, S.mus);
  } else {
    if (s === 0 || s === 4 || s === 5) S.tone(150, t, .12, .3, 'sine', S.mus, 45);
    if (s === 2 || s === 6) S.hiss(t, .1, .07, 'bandpass', 1900, S.mus);
    S.hiss(t, .03, s % 2 ? .024 : .012, 'highpass', 7500, S.mus);
  }
}
M.start = (name) => {
  if (name) M.name = name;
  if (!S.ctx || !S.musicOn || M.timer || !M.name || !A.SONGS[M.name]) return;
  const sg = A.SONGS[M.name];
  M.next = S.ctx.currentTime + .08;
  M.timer = setInterval(() => {
    const beat = 60 / sg.bpm / 2;
    while (M.next < S.ctx.currentTime + .16) { musicStep(sg, M.step, M.next); M.next += beat; M.step = (M.step + 1) % 64; }
  }, 25);
};
M.stop = () => { clearInterval(M.timer); M.timer = null; };
S.setMusic = (on) => {
  S.musicOn = on; A.store.set('arcade.music', on ? '1' : '0');
  if (S.mus) S.mus.gain.setTargetAtTime(on ? .5 : 0, S.ctx.currentTime, .05);
  if (!on) M.stop();
};

/* ---------- эффекты ---------- */
class FX {
  constructor() { this.parts = []; this.texts = []; this.rings = []; }
  burst(x, y, o = {}) {
    const n = o.n || 14, sp = o.speed || 260, cols = o.colors || ['#fff'];
    for (let i = 0; i < n; i++) {
      const a = o.angle != null ? o.angle + A.rand(-1, 1) * (o.spread || .6) : Math.random() * Math.PI * 2;
      const s = A.rand(sp * .25, sp), life = A.rand((o.life || .6) * .6, o.life || .6);
      this.parts.push({ x, y, vx: Math.cos(a) * s, vy: Math.sin(a) * s, life, max: life, size: A.rand((o.size || 7) * .6, o.size || 7), color: A.pick(cols), g: o.gravity || 0, drag: o.drag == null ? 2.2 : o.drag, shape: o.shape || 'circle', rot: Math.random() * 6, vr: A.rand(-8, 8) });
    }
  }
  text(x, y, str, o = {}) { this.texts.push({ x, y, str, color: o.color || '#fff', size: o.size || 34, life: o.life || .9, max: o.life || .9, rise: o.rise || 70 }); }
  ring(x, y, o = {}) { this.rings.push({ x, y, r0: o.r0 || 8, r1: o.r1 || 80, life: o.life || .4, max: o.life || .4, color: o.color || '#fff', w: o.width || 6 }); }
  update(dt) {
    for (const p of this.parts) { p.life -= dt; p.vx -= p.vx * p.drag * dt; p.vy -= p.vy * p.drag * dt; p.vy += p.g * dt; p.x += p.vx * dt; p.y += p.vy * dt; p.rot += p.vr * dt; }
    this.parts = this.parts.filter((p) => p.life > 0);
    for (const t of this.texts) t.life -= dt;
    this.texts = this.texts.filter((t) => t.life > 0);
    for (const r of this.rings) r.life -= dt;
    this.rings = this.rings.filter((r) => r.life > 0);
  }
  draw(ctx) {
    for (const r of this.rings) {
      const k = 1 - r.life / r.max;
      ctx.globalAlpha = 1 - k;
      ctx.beginPath(); ctx.arc(r.x, r.y, A.lerp(r.r0, r.r1, A.ease.outCubic(k)), 0, Math.PI * 2);
      ctx.lineWidth = r.w * (1 - k * .7); ctx.strokeStyle = r.color; ctx.stroke();
    }
    for (const p of this.parts) {
      const k = p.life / p.max, s = p.size * (.4 + .6 * k);
      ctx.globalAlpha = Math.min(1, k * 1.6);
      ctx.fillStyle = p.color;
      if (p.shape === 'star') { ctx.save(); ctx.translate(p.x, p.y); ctx.rotate(p.rot); A.star(ctx, 0, 0, s * 1.3, 5, .45); ctx.fill(); ctx.restore(); }
      else if (p.shape === 'square') { ctx.save(); ctx.translate(p.x, p.y); ctx.rotate(p.rot); ctx.fillRect(-s / 2, -s / 2, s, s); ctx.restore(); }
      else if (p.shape === 'spark') { ctx.strokeStyle = p.color; ctx.lineWidth = s * .5; ctx.lineCap = 'round'; ctx.beginPath(); ctx.moveTo(p.x, p.y); ctx.lineTo(p.x - p.vx * .04, p.y - p.vy * .04); ctx.stroke(); }
      else { ctx.beginPath(); ctx.arc(p.x, p.y, s, 0, Math.PI * 2); ctx.fill(); }
    }
    for (const t of this.texts) {
      const k = 1 - t.life / t.max, sc = k < .25 ? A.ease.outBack(k / .25) : 1;
      ctx.globalAlpha = k > .7 ? 1 - (k - .7) / .3 : 1;
      ctx.save(); ctx.translate(t.x, t.y - t.rise * A.ease.outCubic(k)); ctx.scale(sc, sc);
      A.text(ctx, t.str, 0, 0, { size: t.size, color: t.color, stroke: 'rgba(30,20,60,.85)' });
      ctx.restore();
    }
    ctx.globalAlpha = 1;
  }
  clear() { this.parts.length = 0; this.texts.length = 0; this.rings.length = 0; }
}

/* ---------- иконки ---------- */
const svg = (p) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${p}</svg>`;
A.ICON = {
  back: svg('<path d="m15 18-6-6 6-6"/>'),
  pause: svg('<rect x="6" y="5" width="4" height="14" rx="1"/><rect x="14" y="5" width="4" height="14" rx="1"/>'),
  music: svg('<path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/><path class="off-only" d="M3 3l18 18"/>'),
  fs: svg('<path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/>'),
  home: svg('<path d="M3 11 12 4l9 7"/><path d="M5 10v10h5v-6h4v6h5V10"/>')
};

/* ---------- оболочка игры ---------- */
A.game = function (cfg) {
  const W = cfg.width, H = cfg.height, STEP = 1 / 60;
  const body = document.body;
  body.classList.add('game');
  if (A.shot) body.classList.add('shot');
  const help = A.isTouch ? '' : (cfg.help && cfg.help.desktop) || '';
  body.insertAdjacentHTML('afterbegin', `
    <header class="topbar">
      <a class="tbtn" id="aBack" href="${cfg.home || '../index.html'}">${A.ICON.back}<span class="lbl">${A.framed ? 'Игры' : 'Аркада'}</span></a>
      <h1>${cfg.title}</h1>
      <button type="button" class="tbtn icon" id="aPause" aria-label="Пауза" hidden>${A.ICON.pause}</button>
      <button type="button" class="tbtn icon" id="aMusic" aria-label="Музыка" aria-pressed="${S.musicOn}">${A.ICON.music}</button>
      <button type="button" class="tbtn icon" id="aFs" aria-label="На весь экран">${A.ICON.fs}</button>
    </header>
    <main class="stagewrap" id="aWrap">
      <div class="stage" id="aStage">
        <canvas id="aCanvas" tabindex="0" aria-label="${cfg.title}"></canvas>
        <div class="overlay" id="aOverlay" hidden></div>
        <div class="touchpad" id="aPad" hidden></div>
        <div class="tip" id="aTip" hidden></div>
      </div>
    </main>
    ${help ? `<p class="help">${help}</p>` : ''}`);
  const $ = (id) => document.getElementById(id);
  const wrap = $('aWrap'), stage = $('aStage'), canvas = $('aCanvas'), overlay = $('aOverlay'), padEl = $('aPad'), tip = $('aTip');
  const btnPause = $('aPause'), btnMusic = $('aMusic'), btnFs = $('aFs');
  // тон поля (24.10, владелец: «окна не подходят, белые размытые»): на тёмной игре экраны меню — тёмное стекло,
  // на светлой — светлое; не от темы Dewiar, а от самой игры (cfg.tone: 'dark' | 'light', по умолчанию — как тема)
  document.documentElement.classList.add('tone-' + (cfg.tone || (document.documentElement.classList.contains('light') ? 'light' : 'dark')));
  // телефон: тёмная игра (Бип, Огонёк) — и панель сверху тёмная, во весь экран одним цветом (на компьютере панель — в тон листа)
  if (A.phone && cfg.tone === 'dark') document.documentElement.classList.remove('light');
  if (A.framed) {
    body.classList.add('framed');
    $('aBack').addEventListener('click', (e) => { e.preventDefault(); A.home(cfg.home || '../index.html'); });
  }
  const ctx = canvas.getContext('2d');

  const g = {
    W, H, ctx, canvas, cfg, t: 0, frame: 0, paused: false, playing: false, screenOn: false,
    fx: new FX(), sound: S, best: A.best(cfg.id), shakeT: 0, shakeA: 0, scale: 1
  };

  /* --- ввод --- */
  const input = g.input = {
    held: {}, _p: {},
    pressed(n) { return !!this._p[n]; },
    down(n) { return !!this.held[n]; },
    pointer: { x: W / 2, y: H / 2, down: false, type: 'mouse', justDown: false, justUp: false, dx: 0, dy: 0, moved: false, sx: 0, sy: 0, t0: 0 },
    swipe: null, mouseActive: false
  };
  const KEYS = Object.assign({
    ArrowLeft: 'left', KeyA: 'left', ArrowRight: 'right', KeyD: 'right', ArrowUp: 'up', KeyW: 'up', ArrowDown: 'down', KeyS: 'down',
    Space: 'action', KeyZ: 'action', KeyJ: 'action', KeyK: 'action', KeyX: 'action2', KeyL: 'action2', ShiftLeft: 'action2',
    Enter: 'start', NumpadEnter: 'start', KeyP: 'pause', Escape: 'pause', KeyM: 'mute'
  }, cfg.keys || {});
  addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && document.documentElement.classList.contains('full') && A.framed) { e.preventDefault(); btnFs.click(); return; }   // Esc — сначала из полного экрана
    const a = KEYS[e.code];
    if (!a || e.ctrlKey || e.metaKey || e.altKey) return;
    const tag = (e.target && e.target.tagName) || '';
    if ((tag === 'BUTTON' || tag === 'A') && (e.code === 'Enter' || e.code === 'Space')) return;
    e.preventDefault();
    unlock();
    input.mouseActive = false;
    if (!e.repeat) {
      input._p[a] = true;
      if (a === 'pause') togglePause();
      if (a === 'mute') toggleMusic();
    }
    input.held[a] = true;
  });
  addEventListener('keyup', (e) => { const a = KEYS[e.code]; if (a) input.held[a] = false; });
  const toLogical = (e) => {
    const r = canvas.getBoundingClientRect();
    return { x: (e.clientX - r.left) / r.width * W, y: (e.clientY - r.top) / r.height * H };
  };
  canvas.addEventListener('pointerdown', (e) => {
    unlock(); canvas.focus({ preventScroll: true });
    const p = input.pointer, q = toLogical(e);
    try { canvas.setPointerCapture(e.pointerId); } catch (err) { /* ничего */ }
    Object.assign(p, { x: q.x, y: q.y, sx: q.x, sy: q.y, down: true, justDown: true, type: e.pointerType || 'mouse', t0: performance.now(), id: e.pointerId });
    if (p.type === 'mouse') input.mouseActive = true;
    e.preventDefault();
  });
  canvas.addEventListener('pointermove', (e) => {
    const p = input.pointer, q = toLogical(e);
    if (p.down && e.pointerId !== p.id) return;
    if (p.down) { p.dx += q.x - p.x; p.dy += q.y - p.y; }
    p.x = q.x; p.y = q.y; p.moved = true;
    if ((e.pointerType || 'mouse') === 'mouse') { p.type = 'mouse'; input.mouseActive = true; }
  });
  const up = (e) => {
    const p = input.pointer;
    if (!p.down || (e.pointerId != null && e.pointerId !== p.id)) return;
    const q = toLogical(e);
    p.down = false; p.justUp = true;
    const dx = q.x - p.sx, dy = q.y - p.sy, dist = Math.hypot(dx, dy), ms = performance.now() - p.t0;
    const th = Math.min(W, H) * .06;
    if (dist > th && ms < 600) input.swipe = Math.abs(dx) > Math.abs(dy) ? (dx > 0 ? 'right' : 'left') : (dy > 0 ? 'down' : 'up');
    else if (dist <= th && ms < 300) input.tap = { x: q.x, y: q.y };
  };
  canvas.addEventListener('pointerup', up);
  canvas.addEventListener('pointercancel', up);
  canvas.addEventListener('contextmenu', (e) => e.preventDefault());
  // экранные кнопки
  if (cfg.touch && A.isTouch) {
    padEl.hidden = false;
    const mk = (list) => {
      const grp = document.createElement('div'); grp.className = 'tp-group';
      (list || []).forEach((b) => {
        const el = document.createElement('button');
        el.type = 'button'; el.className = 'tp' + (b.big ? ' big' : ''); el.textContent = b.label; el.setAttribute('aria-label', b.aria || b.label);
        const on = (e) => { e.preventDefault(); unlock(); try { el.setPointerCapture(e.pointerId); } catch (err) { /* */ } input.held[b.id] = true; input._p[b.id] = true; el.classList.add('on'); };
        const off = () => { input.held[b.id] = false; el.classList.remove('on'); };
        el.addEventListener('pointerdown', on);
        ['pointerup', 'pointercancel', 'lostpointercapture'].forEach((ev) => el.addEventListener(ev, off));
        el.addEventListener('contextmenu', (e) => e.preventDefault());
        grp.appendChild(el);
      });
      return grp;
    };
    padEl.appendChild(mk(cfg.touch.left));
    padEl.appendChild(mk(cfg.touch.right));
  }
  g.showPad = (on) => { if (cfg.touch && A.isTouch && padEl.hidden === on) { padEl.hidden = !on; fit(); } };
  // геймпад
  const gpPrev = {};
  function pollPad() {
    let pads = []; try { pads = navigator.getGamepads ? navigator.getGamepads() || [] : []; } catch (e) { /* фрейм без права на геймпад */ }
    const cur = { left: false, right: false, up: false, down: false, action: false, action2: false, start: false };
    for (const p of pads) {
      if (!p) continue;
      const b = (i) => !!(p.buttons[i] && p.buttons[i].pressed), ax = p.axes[0] || 0, ay = p.axes[1] || 0;
      cur.left = cur.left || ax < -.4 || b(14); cur.right = cur.right || ax > .4 || b(15);
      cur.up = cur.up || ay < -.4 || b(12); cur.down = cur.down || ay > .4 || b(13);
      cur.action = cur.action || b(0); cur.action2 = cur.action2 || b(1) || b(2); cur.start = cur.start || b(9);
    }
    for (const k in cur) {
      if (cur[k] && !gpPrev[k]) { input._p[k] = true; if (k === 'start' && g.playing) togglePause(); input.mouseActive = false; }
      if (cur[k] !== !!gpPrev[k]) input.held[k] = cur[k];
      gpPrev[k] = cur[k];
    }
  }
  function endFrame() {
    input._p = {};
    const p = input.pointer; p.justDown = false; p.justUp = false; p.dx = 0; p.dy = 0; p.moved = false;
    input.swipe = null; input.tap = null;
  }

  /* --- звук --- */
  let unlocked = false;
  function unlock() {
    S.init();
    if (!unlocked && S.ctx) { unlocked = true; if (g.playing && !g.paused) M.start(); }
  }
  g.playMusic = () => { M.name = cfg.music; M.stop(); M.step = 0; M.start(cfg.music); };
  g.stopMusic = () => M.stop();
  g.sfx = (name, o) => S.play(name, o);
  function toggleMusic() { unlock(); S.setMusic(!S.musicOn); btnMusic.setAttribute('aria-pressed', String(S.musicOn)); if (S.musicOn && g.playing && !g.paused) M.start(cfg.music); }
  btnMusic.addEventListener('click', () => { toggleMusic(); canvas.focus(); });

  /* --- экраны --- */
  let goFn = null, shownAt = 0, altFn = null;
  g.screen = (o) => {
    goFn = o.onGo || null; altFn = o.alt ? o.alt.onGo : null; shownAt = performance.now();
    const keys = o.keys != null ? o.keys : (A.isTouch ? (cfg.help && cfg.help.touch) || '' : (cfg.help && cfg.help.short) || '');
    overlay.innerHTML = `<div class="card" role="dialog" aria-label="${o.title || ''}">
      ${o.kicker ? `<p class="kicker">${o.kicker}</p>` : ''}
      ${o.title ? `<h2>${o.title}</h2>` : ''}
      ${o.html || ''}
      <div class="row">
        ${o.button ? `<button type="button" class="go" id="aGo">${o.button}</button>` : ''}
        ${o.alt ? `<button type="button" class="ghost" id="aAlt">${o.alt.label}</button>` : ''}
      </div>
      ${keys ? `<div class="keys">${keys}</div>` : ''}
    </div>`;
    overlay.hidden = false; g.screenOn = true; g.showPad(false);
    const go = $('aGo'); if (go) go.addEventListener('click', () => { unlock(); fireGo(); });
    const alt = $('aAlt'); if (alt) alt.addEventListener('click', () => { unlock(); const f = altFn; g.hideScreen(); f && f(); });
    btnPause.hidden = true;
  };
  g.hideScreen = () => { overlay.hidden = true; overlay.innerHTML = ''; g.screenOn = false; g.showPad(true); canvas.focus({ preventScroll: true }); };
  function fireGo() {
    if (performance.now() - shownAt < 350) return;
    const f = goFn; goFn = null; S.play('click'); g.hideScreen(); f && f();
  }
  g.setPlaying = (on) => { g.playing = on; btnPause.hidden = !on; };
  g.submit = (score) => {
    const rec = score > g.best;
    if (rec) { g.best = score; A.store.set('arcade.best.' + cfg.id, score); }
    return rec;
  };
  g.shake = (amt = 8, time = .25) => { if (A.reduceMotion) return; g.shakeA = Math.max(g.shakeA, amt); g.shakeT = Math.max(g.shakeT, time); };
  g.tip = (text, ms = 2600) => { tip.textContent = text; tip.hidden = !text; clearTimeout(g._tipT); if (text) g._tipT = setTimeout(() => { tip.hidden = true; }, ms); };

  /* --- пауза --- */
  let pausedScreen = false;
  function togglePause() { if (g.paused) resume(); else pause(); }
  function pause() {
    if (!g.playing || g.paused || g.screenOn) return;
    g.paused = true; pausedScreen = true; M.stop();
    g.screen({ title: 'Пауза', html: '<p>Игра ждёт вас.</p>', button: 'Продолжить', onGo: resume, alt: { label: A.framed ? 'К играм' : 'В аркаду', onGo: () => A.home(cfg.home || '../index.html') } });
  }
  function resume() {
    if (!g.paused) return;
    g.paused = false;
    if (pausedScreen && g.screenOn) g.hideScreen();
    pausedScreen = false; btnPause.hidden = !g.playing;
    if (S.musicOn) M.start(cfg.music);
  }
  g.pause = pause; g.resume = resume;
  btnPause.addEventListener('click', () => pause());
  addEventListener('blur', () => { input.held = {}; pause(); });
  document.addEventListener('visibilitychange', () => { if (document.hidden) pause(); });

  /* --- полный экран --- */
  const fsOk = A.framed || (!!(document.fullscreenEnabled && document.documentElement.requestFullscreen));
  if (!fsOk) btnFs.hidden = true;
  let hostFull = false;
  btnFs.addEventListener('click', async () => {
    unlock();
    if (A.framed) {                                // во фрейме: на весь экран — просьба хозяину (телефон прячет панели, компьютер разворачивает лист «Досуг»)
      hostFull = !hostFull; btnFs.setAttribute('aria-pressed', String(hostFull)); document.documentElement.classList.toggle('full', hostFull);
      try { window.parent.postMessage({ arcade: 'full', on: hostFull }, '*'); } catch (e) { /* хозяина нет */ }
      setTimeout(fit, 250); canvas.focus(); return;
    }
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else {
        await document.documentElement.requestFullscreen({ navigationUI: 'hide' });
        if (A.isTouch && cfg.orientation && screen.orientation && screen.orientation.lock) screen.orientation.lock(cfg.orientation).catch(() => {});
      }
    } catch (e) { btnFs.hidden = true; }
    canvas.focus();
  });

  /* --- масштаб --- */
  function fit() {
    // горизонтальная игра на телефоне в портрете: кнопки уходят под поле, чтобы не закрывать его
    const below = !!(cfg.touch && A.isTouch && cfg.orientation === 'landscape' && innerHeight > innerWidth);
    if (below && padEl.parentNode !== wrap) { wrap.appendChild(padEl); padEl.classList.add('below'); wrap.classList.add('has-below'); }
    if (!below && padEl.parentNode !== stage) { stage.appendChild(padEl); padEl.classList.remove('below'); wrap.classList.remove('has-below'); }
    const cs = getComputedStyle(wrap);
    const aw = wrap.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
    const ah = wrap.clientHeight - parseFloat(cs.paddingTop) - parseFloat(cs.paddingBottom) - (below && !padEl.hidden ? padEl.offsetHeight + 8 : 0);
    const s = Math.max(.1, Math.min(aw / W, ah / H));
    const cw = Math.floor(W * s), ch = Math.floor(H * s);
    stage.style.width = cw + 'px'; stage.style.height = ch + 'px';
    const dpr = Math.min(window.devicePixelRatio || 1, 2.5, g.dprCap || (A.isTouch && cfg.touchDpr) || 9);   // cfg.touchDpr — тяжёлая графика на телефоне
    canvas.width = Math.round(cw * dpr); canvas.height = Math.round(ch * dpr);
    g.scale = canvas.width / W;
    const portraitPhone = A.isTouch && innerHeight > innerWidth;
    if (A.isTouch && cfg.orientation === 'landscape' && portraitPhone && !g._rotTold) { g._rotTold = true; g.tip('Поверните телефон — так будет крупнее', 4000); }
  }
  addEventListener('resize', fit);
  document.addEventListener('fullscreenchange', () => setTimeout(fit, 60));
  if (window.ResizeObserver) new ResizeObserver(fit).observe(wrap);

  /* --- цикл --- */
  let acc = 0, last = performance.now();
  function step() {
    pollPad();
    if (g.screenOn && goFn && (input.pressed('start') || input.pressed('action'))) { fireGo(); input._p = {}; }
    if (!g.paused) {
      g.frame++; g.t += STEP;
      cfg.update(g, STEP);
      g.fx.update(STEP);
      if (g.shakeT > 0) g.shakeT -= STEP; else g.shakeA = 0;
    }
    endFrame();
  }
  /* Поле не во всю ширину (книжная игра в широком окне «Досуга» на компьютере, 24.10: «игра должна занимать ширину
     блока») — пространство вокруг красится цветами краёв самого поля (раз в 1,5 с), рамка поля пропадает: игра словно
     разлита по всему окну, без «телефона посередине». */
  let tintAt = 0;
  let tintCv = null, tintCx = null;
  function tint(now) {
    if (A.shot || now - tintAt < 1500) return;
    tintAt = now;
    const free = wrap.clientWidth - stage.offsetWidth > 60 || wrap.clientHeight - stage.offsetHeight > 60;
    wrap.classList.toggle('tinted', free);
    if (!free) return;
    try {
      // края поля — через крошечный холст 2×6: getImageData прямо с поля (12 раз в 1,5 с) Chrome считал «частым чтением»
      // и переводил поле игры на процессор — на телефоне «Каляка» с тысячами линий начинала моргать и вставать (25.10)
      const cw = canvas.width, ch = canvas.height, stops = [];
      if (!tintCv) { tintCv = document.createElement('canvas'); tintCv.width = 2; tintCv.height = 6; tintCx = tintCv.getContext('2d', { willReadFrequently: true }); }
      tintCx.clearRect(0, 0, 2, 6);
      tintCx.drawImage(canvas, 0, 0, 4, ch, 0, 0, 1, 6); tintCx.drawImage(canvas, cw - 4, 0, 4, ch, 1, 0, 1, 6);
      const d = tintCx.getImageData(0, 0, 2, 6).data;
      for (let i = 0; i < 6; i++) {
        const a = d.subarray(i * 8, i * 8 + 4), b = d.subarray(i * 8 + 4, i * 8 + 8);
        stops.push('rgb(' + ((a[0] + b[0]) >> 1) + ',' + ((a[1] + b[1]) >> 1) + ',' + ((a[2] + b[2]) >> 1) + ')');
      }
      wrap.style.setProperty('--edge', 'linear-gradient(180deg,' + stops.join(',') + ')');
    } catch (e) { wrap.classList.remove('tinted'); }
  }
  /* Слабый телефон (25.10, владелец: «Каляка на телефоне — быстро моргает экран и подвисает»): 1) за кадр — не больше
     4 шагов игры: иначе медленный кадр копит шаги, следующий ещё медленнее, и игра «замерзает»; 2) кадры стабильно
     реже ~25 в секунду — рисуем в меньшем разрешении (ступенями до 1×), картинка чуть мягче, зато игра идёт. */
  let slowAt = performance.now(), slowN = 0, slowSum = 0;
  function frame(now) {
    const raw = now - last, dt = Math.min(.1, raw / 1000); last = now;
    acc += dt;
    let n = 0;
    while (acc >= STEP && n < 4) { step(); acc -= STEP; n++; }
    if (n === 4) acc = 0;
    if (A.isTouch && !document.hidden && raw < 1000) { slowN++; slowSum += raw; }
    if (now - slowAt > 2500) {
      const avg = slowN ? slowSum / slowN : 0, cur = Math.min(window.devicePixelRatio || 1, 2.5, g.dprCap || (A.isTouch && cfg.touchDpr) || 9);
      if (avg > 40 && cur > 1.01) { g.dprCap = Math.max(1, cur - .5); fit(); A.report && A.report('медленно: ' + Math.round(avg) + ' мс на кадр — разрешение ' + g.dprCap + '×'); }
      slowAt = now; slowN = 0; slowSum = 0;
    }
    ctx.setTransform(g.scale, 0, 0, g.scale, 0, 0);
    ctx.imageSmoothingEnabled = true;
    if (g.shakeT > 0 && !g.paused) ctx.translate(A.rand(-1, 1) * g.shakeA, A.rand(-1, 1) * g.shakeA);
    cfg.draw(ctx, g);
    g.fx.draw(ctx);
    tint(now);
    requestAnimationFrame(frame);
  }

  if (document.fonts && document.fonts.load) document.fonts.load(`800 32px Rubik`).catch(() => {});
  fit();
  cfg.init(g);
  requestAnimationFrame(frame);
  window.__game = g;
  return g;
};
})();
