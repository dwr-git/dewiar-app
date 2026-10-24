/* «Кто боится темноты» (24.10, владелец о концепте: «очень нравится… как же красиво будет. Делай»).
   Чёрно-белый ночной лес и один тёплый акцент — янтарь фонаря. Малыш Пип в ночном колпаке идёт домой с фонарём на
   палке. Тени в лесу не страшные, а стеснительные: на свету краснеют (янтарные чёрточки) и уступают дорогу со смешной
   репликой. Масло в фонаре тает — его пополняют светлячки. Пять участков: Опушка, Старый дуб, Прятки, Мостик, Домик.

   Как рисуется: мир дважды — тёмный прямо на холст, освещённый — в свой буфер, который вырезается кругами света с
   растровым краем (точки-полутон, как в концепте). Чёрные силуэты в обоих мирах одинаковы, поэтому рисуются один раз
   поверх: во тьме сливаются с фоном (видны только глаза), на свету — чёткие. Надписи — тоже дважды: белые во тьме,
   чёрные на свету (под тем же растром). Дальние слои — плитки, нарисованные один раз; земля — кусками, один раз.
   Управление: ← → (A D) — идти, мышь — куда светить, пробел или кнопка мыши (держать) — поднять фонарь (шире свет,
   масло быстрее); ↑ ↓ — наклонить свет без мыши. Телефон: левая половина экрана — идти (левее — назад, правее — вперёд),
   правая — вести пальцем свет, кнопка «выше» — поднять фонарь. Проверка: window.__dark() → состояние; .bot = true —
   игра проходит себя сама (.ts — ускорение). */
(() => {
'use strict';
const A = Arcade, SND = A.sound;
const LAND = (() => { try { return innerWidth > (innerHeight - 110) * 1.15; } catch (e) { return false; } })();
const W = LAND ? 1280 : 720, H = LAND ? 720 : 1280, TAU = Math.PI * 2;
const GY = LAND ? 596 : 930;                         // линия земли
const TOUCH = A.isTouch;
const clamp = (v, a, b) => (v < a ? a : v > b ? b : v), lerp = (a, b, t) => a + (b - a) * t;
const sm = (t) => { t = clamp(t, 0, 1); return t * t * (3 - 2 * t); }, eOut = (t) => 1 - (1 - clamp(t, 0, 1)) ** 3;
function rng(seed) { return () => { seed = (seed + 0x6D2B79F5) | 0; let t = Math.imul(seed ^ (seed >>> 15), 1 | seed); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
const AMB = '#ffb72b', BLK = '#0c0c0d', CREAM = '#f2eee5';
const rgb = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
const mix = (a, b, t) => { const x = rgb(a), y = rgb(b); return 'rgb(' + x.map((v, i) => Math.round(v + (y[i] - v) * t)).join(',') + ')'; };
const DARK = { id: 0, bg: '#0c0c0d', far: '#17171a', mid: '#121214', oak: '#141417', fig: '#131315', water: '#111114', rip: '#1e1e22' };
const LIT = { id: 1, bg: '#f2eee5', far: '#d3cdc1', mid: '#aaa497', oak: '#8d877c', fig: '#7a756c', water: '#c7c1b4', rip: '#9a948a' };

/* ---------------- раскладка: широкая (компьютер) и книжная (телефон) ---------------- */
const K = LAND ? {
  camK: .36, bx: 48, kick: 52, name: 96, dash: 110, hint: 146, kickS: 20, nameS: 40, hintS: 22, wrap: 700, tName: 40,
  q: [1222, 58], moon: [1092, 176], hudY: 676, oilW: 210, prog: [520, 760], speech: 24, sp2: 21,
  pad: { l: [96, 548], r: [250, 548], up: [1176, 532], rr: 52 }, capY: 470
} : {
  camK: .3, bx: 44, kick: 74, name: 126, dash: 144, hint: 188, kickS: 22, nameS: 46, hintS: 28, wrap: 630, tName: 40,
  q: [666, 72], moon: [612, 330], hudY: 1034, oilW: 230, prog: [44, 676], progY: 1092, speech: 30, sp2: 26,
  pad: { l: [100, 1196], r: [272, 1196], up: [604, 1190], rr: 62 }, capY: 760
};

/* ---------------- мир ---------------- */
const CH = [
  { n: 'Опушка', x: 0, tag: 'Тени тут вежливые. Просто очень стеснительные.' },
  { n: 'Старый дуб', x: 1800, tag: 'Под дубом живёт кто-то очень большой.' },
  { n: 'Прятки', x: 3300, tag: 'Кто-то хихикает в темноте…' },
  { n: 'Мостик', x: 4900, tag: 'Через ручей — по мостику.' },
  { n: 'Домик', x: 6350, tag: 'Вон окошко! Ещё чуть-чуть.' },
];
const GAP = [5440, 5990], HX = 7090, DOOR = 7020, WORLD = HX + 400, DIP = LAND ? 44 : 64;
const ground = (x) => GY + Math.sin(x * .006 + 1) * 8 + Math.sin(x * .021) * 3;
const gtop = (x) => { if (x > GAP[0] && x < GAP[1]) { const t = (x - GAP[0]) / (GAP[1] - GAP[0]); return ground(x) + DIP * Math.pow(Math.sin(t * Math.PI), .3); } return ground(x); };
const B0 = GAP[0] - 46, B1 = GAP[1] + 46;
const walkY = (x) => { if (x > B0 && x < B1) { const t = (x - B0) / (B1 - B0); return lerp(ground(B0), ground(B1), t) - Math.sin(t * Math.PI) * 16; } return ground(x); };
const FLIES = [[380, 150], [700, 70], [1150, 260], [910, 30, 'gift'], [2232, 372], [2480, 110], [3050, 230], [3450, 140], [3880, 290], [4300, 46], [5200, 240], [5715, -14]];
const EYES = [[260, 170, .9], [620, 330, .7], [990, 120, .8], [1250, 380, .6], [1700, 200, .9], [2040, 90, .7], [2440, 300, .8], [3150, 150, .9], [3420, 380, .6],
  [3960, 110, .8], [4320, 330, .7], [4800, 180, .9], [5040, 330, .8], [5360, 370, .6], [6080, 260, .8], [6250, 120, .9], [6560, 330, .7], [6660, 100, .8]];
const EYE_LINES = ['ой!', 'я не подглядывал', 'тсс…', 'какой яркий!', 'мы не страшные', 'щекотно!', 'я просто тут стою', 'уже ухожу!'];
const HSP = [{ x: 3600, m: 'stand' }, { x: 3980, m: 'hang' }, { x: 4340, m: 'bush' }, { x: 4690, m: 'grass' }];
const TRIO = [-170, 0, 170], TRIO_GO = [[-230, -330, 70, .55], [120, -420, 60, .5], [470, -36, 50, .62]];

/* ---------------- состояние ---------------- */
let S = null, GAME = null;
const T = { ptrs: new Map() };
function newState(mode) {
  S = {
    mode, t: 0, time: 0, cam: 0, oil: 100, count: 0, total: 12, ch: 0, chT: 0,
    pip: { x: 180, y: GY, face: 1, walking: false, ph: 0, blink: 2, raiseK: 0, alpha: 1, happy: 0, stepT: 0, shiver: 0 },
    aim: { x: 150, y: -40 }, aimMode: 'kb', elev: .28, mouse: null, mouseDown: false, lan: null, L: null, override: null,
    chars: [], flies: [], eyes: [], says: [], parts: [], decor: [],
    hint: '', hintPrev: '', hintF: 1, hintT: 0, cap: null, moved: 0, needRaise: false, trioPart: 0,
    rescue: 0, emptySaid: false, fade: 1, door: 0, outT: 0, bye: false, bot: false, ts: 1, sayCD: 0, bumpCD: 0,
    botSkip: new Set(), botFly: null, botFT: 0, ambT: 1, crT: 2, owlT: 9, spoke: false
  };
  T.ptrs.clear();
  return S;
}

/* ---------------- звук ---------------- */
const now = () => SND.now();
const snd = {
  step() { if (SND.ctx) SND.hiss(now(), .05, .016, 'lowpass', 600); },
  fly(i) { if (!SND.ctx) return; const t = now(), f = [523.3, 587.3, 659.3, 784, 880, 987.8, 1046.5, 1174.7, 1318.5, 1568, 1760, 2093][clamp(i, 0, 11)];
    SND.tone(f, t, 1.3, .07, 'sine'); SND.tone(f * 2, t, .5, .016, 'triangle'); SND.tone(f * 1.5, t + .08, .9, .022, 'sine'); },
  giggle(v = 1) { if (!SND.ctx) return; const t = now(); for (let k = 0; k < 3; k++) SND.tone(1150 + k * 110 + Math.random() * 60, t + k * .09, .07, .045 * v, 'sine', null, 1500); },
  oy() { if (!SND.ctx) return; const t = now(); SND.tone(760, t, .22, .055, 'sine', null, 430); },
  hat() { if (!SND.ctx) return; const t = now(); SND.tone(988, t, .25, .05, 'triangle'); SND.tone(1319, t + .12, .4, .045, 'sine'); },
  giant() { if (!SND.ctx) return; const t = now(); SND.tone(230, t, .5, .1, 'sine', null, 160, .03); SND.tone(345, t + .05, .45, .03, 'triangle', null, 240); },
  whoosh() { if (SND.ctx) { SND.hiss(now(), .45, .08, 'bandpass', 1300); SND.hiss(now() + .08, .5, .04, 'bandpass', 2600); } },
  scatter() { if (!SND.ctx) return; const t = now(); [784, 988, 1175, 1568].forEach((f, k) => SND.tone(f, t + k * .07, .16, .055, 'sine', null, f * 1.4)); },
  bump() { if (SND.ctx) SND.tone(120, now(), .16, .1, 'sine', null, 70); },
  raise() { if (SND.ctx) SND.hiss(now(), .3, .03, 'bandpass', 2200); },
  purr() { if (!SND.ctx) return; const t = now(); for (let k = 0; k < 9; k++) SND.tone(62 + Math.random() * 8, t + k * .055, .06, .07, 'triangle'); },
  sputter() { if (!SND.ctx) return; const t = now(); for (let k = 0; k < 3; k++) SND.hiss(t + k * .07, .05, .04, 'bandpass', 380 + Math.random() * 300); },
  chapter() { if (!SND.ctx) return; const t = now(); [[659.3, .04, 1.6], [987.8, .022, 1.2], [1318.5, .012, .8]].forEach(([f, v, d]) => SND.tone(f, t, d, v, 'sine')); },
  door() { if (!SND.ctx) return; const t = now(); SND.tone(160, t, .5, .03, 'sawtooth', null, 120, .05); [392, 493.9, 587.3, 784, 987.8, 1174.7].forEach((f, k) => { SND.tone(f, t + .3 + k * .12, 3, .05, 'sine'); SND.tone(f * 2, t + .3 + k * .12, 1.2, .01, 'triangle'); }); },
  snore() { if (!SND.ctx) return; const t = now(); SND.hiss(t, .9, .03, 'lowpass', 380); SND.tone(78, t, .8, .035, 'sine', null, 66, .3); },
  hoot() { if (!SND.ctx) return; const t = now(); SND.tone(392, t, .4, .05, 'sine', SND.mus, 360, .06); SND.tone(330, t + .5, .7, .05, 'sine', SND.mus, 300, .06); },
};
function ambience(dt) {
  if (!SND.ctx || !SND.musicOn) return;
  S.ambT -= dt; S.crT -= dt; S.owlT -= dt;
  if (S.ambT <= 0) {
    S.ambT = 2.8 + Math.random() * 2.2;
    const ch = [146.8, 174.6, 220, 261.6, 329.6, 392], f = A.pick(ch), t = now();
    SND.tone(f, t, 8, .028, 'sine', SND.mus, null, 2.6); SND.tone(f * 2.004, t + .3, 6, .007, 'triangle', SND.mus, null, 2.8);
    if (Math.random() < .3) SND.tone(A.pick(ch) * 4, t + 1.4, 2.2, .005, 'sine', SND.mus);
  }
  if (S.crT <= 0) { S.crT = 1.3 + Math.random() * 3; const t = now(), f = 4200 + Math.random() * 700; for (let k = 0; k < 3; k++) SND.tone(f, t + k * .06, .03, .005, 'sine', SND.mus); }
  if (S.owlT <= 0) { S.owlT = 16 + Math.random() * 16; snd.hoot(); }
}

/* ---------------- заготовки: растровый круг света, плитки, земля ---------------- */
const C = { sc: 0, tiles: [], chunks: {}, disc: null, lb: null, mb: null, glow: null, grain: null, vig: null };
const R0 = 200, RING = .34, DSZ = Math.ceil(2 * (R0 * (1 + RING) + 8)), TW = 1600, CW = 1024, GT = GY - 46;
const mkc = (w, h) => { const c = document.createElement('canvas'); c.width = Math.max(1, Math.round(w)); c.height = Math.max(1, Math.round(h)); return c; };
function ensure(sc) {
  if (C.sc === sc) return;
  C.sc = sc; C.chunks = {};
  C.lb = mkc(W * sc, H * sc); C.mb = mkc(W * sc, H * sc); C.lbx = C.lb.getContext('2d'); C.mbx = C.mb.getContext('2d');
  // круг света: сплошной диск и растровый край — точки к краю мельчают (как в концепте)
  const d = mkc(DSZ * sc, DSZ * sc), x = d.getContext('2d'); x.scale(sc, sc);
  const cx = DSZ / 2, ring = R0 * RING, ST = 10.5;
  x.fillStyle = '#000'; x.beginPath(); x.arc(cx, cx, R0, 0, TAU);
  for (let yy = cx - R0 - ring - ST, row = 0; yy < cx + R0 + ring + ST; yy += ST * .87, row++) {
    for (let xx = cx - R0 - ring - ST; xx < cx + R0 + ring + ST; xx += ST) {
      const px = xx + (row & 1 ? ST / 2 : 0), dd = Math.hypot(px - cx, yy - cx);
      if (dd < R0 - 3 || dd > R0 + ring) continue;
      const t = 1 - (dd - R0) / ring, r = ST * .62 * Math.pow(t, 1.15); if (r < .55) continue;
      x.moveTo(px + r, yy); x.arc(px, yy, r, 0, TAU);
    }
  }
  x.fill(); C.disc = d;
  C.tiles = [DARK, LIT].map((P) => ({ far: tile(P, 'far'), mid: tile(P, 'mid') }));
  if (!C.glow) {
    const g = mkc(128, 128), y = g.getContext('2d'), gr = y.createRadialGradient(64, 64, 0, 64, 64, 64);
    gr.addColorStop(0, 'rgba(255,183,43,1)'); gr.addColorStop(.22, 'rgba(255,183,43,.42)'); gr.addColorStop(.55, 'rgba(255,183,43,.1)'); gr.addColorStop(1, 'rgba(255,183,43,0)');
    y.fillStyle = gr; y.fillRect(0, 0, 128, 128); C.glow = g;
    const v = mkc(W / 2, H / 2), z = v.getContext('2d'), vg = z.createRadialGradient(W / 4, H / 4, Math.min(W, H) * .2, W / 4, H / 4, Math.max(W, H) * .52);
    vg.addColorStop(0, 'rgba(0,0,0,0)'); vg.addColorStop(1, 'rgba(0,0,0,.6)'); z.fillStyle = vg; z.fillRect(0, 0, W / 2, H / 2); C.vig = v;
  }
}
function tile(P, kind) {
  const sc = C.sc, cv = mkc(TW * sc, H * sc), x = cv.getContext('2d'); x.scale(sc, sc);
  if (kind === 'far') {
    if (P === DARK) { const r = rng(91); for (let i = 0; i < 70; i++) { const yy = r() * GY * .55; x.fillStyle = 'rgba(255,255,255,' + (.18 + r() * .5).toFixed(2) + ')'; x.fillRect(r() * TW, yy, 1.6, 1.6); } }
    const r = rng(7), trees = []; let tx = 50;
    while (tx < TW - 60) { trees.push([tx, 38 + r() * 76, r()]); tx += 180 + r() * 150; }
    x.fillStyle = P.far; x.strokeStyle = P.far; x.lineCap = 'round';
    for (const [t0, w, q] of trees) for (const o of [-TW, 0, TW]) { const X = t0 + o; if (X > -420 && X < TW + 420) trunk(x, X, w, q); }
  } else {
    const Y = (X) => GY - 24 - Math.sin(X / TW * TAU * 2 + .6) * 26 - Math.sin(X / TW * TAU * 7) * 7;
    x.fillStyle = P.mid; x.beginPath(); x.moveTo(0, H);
    for (let X = 0; X <= TW; X += 8) x.lineTo(X, Y(X));
    x.lineTo(TW, H); x.closePath(); x.fill();
    const r = rng(15);
    for (let i = 0; i < 9; i++) { const X = 60 + r() * (TW - 120), s = 14 + r() * 22; x.beginPath(); x.arc(X, Y(X) + 4, s, Math.PI, 0); x.arc(X + s * .9, Y(X) + 6, s * .7, Math.PI, 0); x.fill(); }
  }
  return cv;
}
function trunk(x, X, w, q) {
  const base = GY + 30;
  x.beginPath(); x.moveTo(X - w / 2, -2); x.bezierCurveTo(X - w * .3, base * .47, X - w * .7, base * .81, X - w * 1.3, base);
  x.lineTo(X + w * 1.3, base); x.bezierCurveTo(X + w * .7, base * .81, X + w * .3, base * .47, X + w / 2, -2); x.fill();
  const n = 2 + ((q * 3) | 0);
  for (let i = 0; i < n; i++) {
    const y = base * (.1 + .32 * ((q * 7.3 + i * .37) % 1)), s = (i + (q > .5 ? 1 : 0)) % 2 ? 1 : -1, len = 70 + w * (.7 + ((q * 13.1 + i * .61) % 1));
    x.lineWidth = Math.max(6, w * .16); x.beginPath(); x.moveTo(X, y + 24); x.quadraticCurveTo(X + s * len * .5, y + 18, X + s * len, y - len * .42); x.stroke();
    x.lineWidth *= .55; x.beginPath(); x.moveTo(X + s * len * .62, y + 6); x.quadraticCurveTo(X + s * len * .78, y - 10, X + s * len * .7, y - len * .5); x.stroke();
  }
}
function drawTile(c, cv, off) { for (let ox = -(((off % TW) + TW) % TW); ox < W; ox += TW) c.drawImage(cv, ox, 0, TW, H); }
function chunk(i) {
  let cv = C.chunks[i]; if (cv) return cv;
  const sc = C.sc, x0 = i * CW - 6, w = CW + 12; cv = mkc(w * sc, (H - GT) * sc);
  const x = cv.getContext('2d'); x.scale(sc, sc); x.translate(-x0, -GT);
  x.fillStyle = BLK; x.beginPath(); x.moveTo(x0, H + 2);
  for (let X = x0; X <= x0 + w; X += 4) x.lineTo(X, gtop(X));
  x.lineTo(x0 + w, H + 2); x.closePath(); x.fill();
  const r = rng(300 + i); x.strokeStyle = BLK; x.lineCap = 'round';
  for (let X = i * CW; X < (i + 1) * CW; X += 5 + r() * 7) {
    if (X > GAP[0] - 6 && X < GAP[1] + 6) continue;
    const y = gtop(X) + 2, h = 5 + r() * 12, lean = (r() - .5) * 8;
    x.lineWidth = 1.8 + r() * 1.2; x.beginPath(); x.moveTo(X, y); x.quadraticCurveTo(X + lean * .3, y - h * .6, X + lean, y - h); x.stroke();
  }
  C.chunks[i] = cv; return cv;
}
function drawGround(c) {
  const a = Math.floor(S.cam / CW), b = Math.floor((S.cam + W) / CW);
  for (let i = Math.max(0, a); i <= b; i++) c.drawImage(chunk(i), i * CW - 6, GT, CW + 12, H - GT);
}
function glow(c, x, y, r, a) { if (a <= .004) return; c.globalAlpha = Math.min(1, a); c.drawImage(C.glow, x - r, y - r, r * 2, r * 2); c.globalAlpha = 1; }
function ell(c, x, y, rx, ry, rot = 0) { c.beginPath(); c.ellipse(x, y, Math.max(.1, rx), Math.max(.1, ry), rot, 0, TAU); }
function blob(c, cx, base, w, h, wob, ph) {      // тень-«призрак»: круглая макушка, волнистый подол
  c.beginPath(); c.moveTo(cx - w / 2, base);
  c.bezierCurveTo(cx - w / 2 - 4, base - h * .55, cx - w * .42, base - h, cx, base - h);
  c.bezierCurveTo(cx + w * .42, base - h, cx + w / 2 + 4, base - h * .55, cx + w / 2, base);
  const n = 5; for (let i = n; i > 0; i--) { const a = cx - w / 2 + w * i / n, b = cx - w / 2 + w * (i - 1) / n; c.quadraticCurveTo((a + b) / 2, base + wob * (i % 2 ? 1 : -.2) + Math.sin(ph + i) * 2, b, base); }
  c.closePath();
}
function blade(c, x0, y0, x1, y1, bend, w) {
  const cx = (x0 + x1) / 2 + bend, cy = (y0 + y1) / 2, L = [], R = [];
  for (let i = 0; i <= 10; i++) {
    const t = i / 10, u = 1 - t, x = u * u * x0 + 2 * u * t * cx + t * t * x1, y = u * u * y0 + 2 * u * t * cy + t * t * y1;
    const dx = 2 * u * (cx - x0) + 2 * t * (x1 - cx), dy = 2 * u * (cy - y0) + 2 * t * (y1 - cy), l = Math.hypot(dx, dy) || 1, ww = w * (1 - t * .92) / 2;
    L.push([x - dy / l * ww, y + dx / l * ww]); R.push([x + dy / l * ww, y - dx / l * ww]);
  }
  c.beginPath(); c.moveTo(L[0][0], L[0][1]); L.forEach((p) => c.lineTo(p[0], p[1])); for (let i = R.length - 1; i >= 0; i--) c.lineTo(R[i][0], R[i][1]); c.closePath(); c.fill();
}

/* ---------------- глаза, румянец ---------------- */
function eyes(c, x1, y1, x2, y2, rx, ry, lx, ly, open = 1) {
  if (open < .08) { c.strokeStyle = '#fff'; c.lineWidth = 2.4; c.lineCap = 'round'; c.beginPath(); c.moveTo(x1 - rx, y1); c.lineTo(x1 + rx, y1); c.moveTo(x2 - rx, y2); c.lineTo(x2 + rx, y2); c.stroke(); return; }
  c.fillStyle = '#fff'; ell(c, x1, y1, rx, ry * open); c.fill(); ell(c, x2, y2, rx, ry * open); c.fill();
  c.fillStyle = BLK; const pr = rx * .5, ox = lx * rx * .42, oy = ly * ry * .35 * open;
  ell(c, x1 + ox, y1 + oy, pr, pr * Math.min(1, open * 1.3)); c.fill(); ell(c, x2 + ox, y2 + oy, pr, pr * Math.min(1, open * 1.3)); c.fill();
  if (open > .6) { c.fillStyle = '#fff'; ell(c, x1 + ox + pr * .4, y1 + oy - pr * .45, pr * .32, pr * .32); c.fill(); ell(c, x2 + ox + pr * .4, y2 + oy - pr * .45, pr * .32, pr * .32); c.fill(); }
}
function happyEyes(c, x1, y1, x2, y2, r, w = 3.6) {
  c.strokeStyle = '#fff'; c.lineWidth = w; c.lineCap = 'round';
  c.beginPath(); c.arc(x1, y1 + r * .4, r, Math.PI * 1.12, Math.PI * 1.88); c.stroke();
  c.beginPath(); c.arc(x2, y2 + r * .4, r, Math.PI * 1.12, Math.PI * 1.88); c.stroke();
}
function cheeks(c, xl, xr, y, a, n = 3, gap = 9, len = 11, w = 3.6) {
  if (a <= .02) return;
  c.save(); c.globalAlpha = Math.min(1, a); c.strokeStyle = AMB; c.lineWidth = w; c.lineCap = 'round'; c.beginPath();
  for (let i = 0; i < n; i++) { const o = (i - (n - 1) / 2) * gap; c.moveTo(xl + o + len * .25, y - len / 2); c.lineTo(xl + o - len * .25, y + len / 2); c.moveTo(xr + o + len * .25, y - len / 2); c.lineTo(xr + o - len * .25, y + len / 2); }
  c.stroke(); c.restore();
}

/* ---------------- тени-характеры ----------------
   Каждая: тело в своих координатах (0,0 — середина подола), лицо, точки «освещённости», нужная доля света, реплики.
   Состояния: wait (стоит на пути) → yield (стесняется и отходит вглубь леса) → aside (машет из-за деревьев). */
const SPEC = {
  gent: {
    hw: 52, h: 190, gap: 90, need: .6, dur: .9, aim: [2, -140], adx: 46, arise: 40, as: .6, block: true,
    first: 'о!', go: 'после вас', after: 'прошу-прошу', sfx: () => snd.hat(),
    pts: () => [[-14, -150], [18, -150], [2, -128], [2, -100], [2, -172]],
    body(x, c) {
      blob(x, 0, 4, 104, 190, 8, S.t * 1.5 + 1); x.fill();
      const k = sm(c.hat), hx = lerp(8, 70, k), hy = lerp(-196, -202, k);
      if (k > .02) { x.lineWidth = 16; x.lineCap = 'round'; x.strokeStyle = x.fillStyle; x.beginPath(); x.moveTo(40, -112); x.quadraticCurveTo(lerp(40, 84, k), -150, hx, hy); x.stroke(); }
      x.save(); x.translate(hx + 1, hy + lerp(-14, -40, k)); x.rotate(lerp(-.1, .16, k));
      x.fillRect(-23, -22, 46, 40); ell(x, 0, 18, 38, 7); x.fill(); x.restore();
    },
    face(x, c, lk) {
      if (c.blush > .45) happyEyes(x, -14, -150, 18, -150, 8, 4); else eyes(x, -14, -150, 18, -150, 6.5, 8, lk, .2, c.open);
      cheeks(x, -32, 36, -130, c.blush, 2, 9, 11, 3.5);
    },
    lit(x) { x.fillStyle = CREAM; x.beginPath(); x.moveTo(2, -98); x.lineTo(-12, -106); x.lineTo(-12, -90); x.closePath(); x.moveTo(2, -98); x.lineTo(16, -106); x.lineTo(16, -90); x.closePath(); x.fill(); },
  },
  shroom: {
    hw: 23, h: 62, need: .6, dur: .35, aim: [2, -36], block: false,
    pts: () => [[-6, -40], [10, -40], [2, -28]],
    body(x) { blob(x, 0, 2, 46, 62, 4, S.t * 2); x.fill(); x.fillStyle = x.fillStyle; ell(x, 20, -12, 6, 5); x.fill(); },
    face(x, c, lk) { if (c.duck > .5) happyEyes(x, -6, -38, 10, -38, 5, 2.6); else eyes(x, -6, -40, 10, -40, 6, 8, lk, .1, c.open); cheeks(x, -16, 20, -26, c.blush, 2, 6, 7, 2.6); },
  },
  giant: {
    hw: 111, h: 420, gap: 60, need: .9, dur: 1.1, aim: [0, -215], adx: 150, arise: 44, as: .55, block: true, raise: true,
    go: 'ой… не смотрите на меня', after: 'я тут посижу', sfx: () => snd.giant(),
    pts: () => { const p = []; for (const y of [-50, -125, -200, -275, -350, -410]) for (const xx of [-70, 0, 70]) p.push([xx, y]); return p; },
    body(x) {
      x.save(); x.scale(1.17, 1.17); blob(x, 0, 4, 190, 360, 10, S.t + 2); x.fill();
      x.lineWidth = 26; x.lineCap = 'round'; x.strokeStyle = x.fillStyle;
      x.beginPath(); x.moveTo(-92, -150); x.quadraticCurveTo(-90, -210, -50, -230); x.stroke();
      x.beginPath(); x.moveTo(92, -150); x.quadraticCurveTo(92, -210, 46, -228); x.stroke();
      ell(x, -38, -258, 30, 40, -.2); x.fill(); ell(x, 34, -256, 30, 40, .2); x.fill(); x.restore();
    },
    face(x, c) {
      x.save(); x.scale(1.17, 1.17);
      x.strokeStyle = '#2c2c2f'; x.lineWidth = 2; x.lineCap = 'round'; x.beginPath();
      for (const s of [-1, 1]) for (let i = 0; i < 3; i++) { x.moveTo(s * (26 + i * 12), -292); x.lineTo(s * (24 + i * 12), -276); }
      x.stroke();
      const o = c.peek; if (o > .05) { x.fillStyle = '#fff'; ell(x, -40, -262, 9, 4 * o, -.1); x.fill(); ell(x, 36, -260, 9, 4 * o, .1); x.fill();
        if (o > .5) { x.fillStyle = BLK; ell(x, -38, -262, 2.6, 2.6 * o); x.fill(); ell(x, 38, -260, 2.6, 2.6 * o); x.fill(); } }
      x.restore();
      cheeks(x, -76, 76, -253, c.blush, 3, 13, 15, 4.5);
    },
  },
  hide: {
    hw: 32, h: 150, gap: 110, need: .5, dur: .6, aim: [0, -110], adx: 60, arise: 36, as: .6, block: true,
    pts: () => [[-11, -108], [11, -108], [0, -126], [0, -90]],
    body(x, c) {
      blob(x, 0, 3, 64, 150, 6, S.t * 2.2); x.fill();
      x.beginPath(); x.moveTo(0, -150); x.lineTo(-22, -166); x.lineTo(-20, -138); x.closePath(); x.moveTo(0, -150); x.lineTo(22, -166); x.lineTo(20, -138); x.closePath(); x.fill(); ell(x, 0, -150, 5.5, 5.5); x.fill();
      x.lineWidth = 7; x.lineCap = 'round'; x.strokeStyle = x.fillStyle; const w = Math.sin(S.t * 3) * 3, up = c.blush > .3 ? 1 : 0;
      x.beginPath(); x.moveTo(-26, -70); x.quadraticCurveTo(-44, -84 - up * 10, -36 + up * 14, -100 - up * 12 + w); x.moveTo(26, -70); x.quadraticCurveTo(44, -84 - up * 10, 36 - up * 14, -100 - up * 12 - w); x.stroke();
    },
    face(x, c, lk) { if (c.blush > .55) happyEyes(x, -11, -110, 11, -110, 7, 3.2); else eyes(x, -11, -110, 11, -110, 7, 9, lk, .2, c.open); cheeks(x, -24, 24, -92, c.blush, 2, 7, 9, 3); },
  },
  trio: {
    hw: 31, h: 80, gap: 40, need: .6, dur: .7, aim: [0, -46], block: true, raise: true,
    pts: () => [[-9, -50], [9, -50], [0, -36]],
    body(x) { blob(x, 0, 2, 62, 80, 5, S.t * 2.6); x.fill(); x.lineWidth = 5; x.lineCap = 'round'; x.strokeStyle = x.fillStyle; x.beginPath(); x.moveTo(0, -78); x.quadraticCurveTo(10, -96, 2, -100); x.stroke(); },
    face(x, c, lk, j) { const b = c.kb[j]; if (b > .5) happyEyes(x, -9, -50, 9, -50, 5.5, 3); else eyes(x, -9, -50, 9, -50, 5.5, 7, lk, .2, c.open); cheeks(x, -20, 20, -36, b, 2, 6, 8, 2.8); },
  },
  sleepy: {
    hw: 80, h: 64, gap: 80, need: .6, dur: .9, aim: [-38, -28], adx: 40, arise: 34, as: .6, block: true,
    first: 'м-м?', go: 'ой… уже утро?', after: 'спокойной ночи…', sfx: () => snd.oy(),
    pts: () => [[-48, -32], [-28, -32], [-38, -20]],
    body(x, c) {
      const br = c.st === 'wait' && c.blush < .3 ? 1 + Math.sin(S.t * 1.7) * .05 : 1;
      x.save(); x.scale(1, br);
      x.beginPath(); x.moveTo(-82, 0); x.bezierCurveTo(-88, -42, -62, -64, -32, -62); x.bezierCurveTo(8, -60, 44, -46, 72, -30); x.quadraticCurveTo(90, -20, 82, 0); x.closePath(); x.fill();
      x.restore();
      x.beginPath(); x.moveTo(-60, -56); x.bezierCurveTo(-50, -84, -14, -86, -6, -60); x.closePath(); x.fill(); ell(x, -2, -54, 6, 6); x.fill();
    },
    face(x, c, lk) {
      if (c.blush > .35) { eyes(x, -48, -32, -28, -32, 6, 8, lk, .1, c.open); cheeks(x, -60, -16, -18, c.blush, 2, 6, 8, 2.8); }
      else { x.strokeStyle = '#fff'; x.lineWidth = 2.6; x.lineCap = 'round'; x.beginPath(); x.arc(-48, -36, 5, .3, Math.PI - .3); x.moveTo(-23, -34); x.arc(-28, -36, 5, .3, Math.PI - .3); x.stroke(); }
    },
  },
  cat: {
    hw: 36, h: 120, gap: 90, need: .5, dur: .8, aim: [4, -90], adx: 84, arise: 22, as: .82, block: true,
    first: 'мрр…', go: 'щекотно! проходи', after: 'мур', sfx: () => snd.purr(),
    pts: () => [[-4, -96], [16, -96], [6, -78], [2, -40]],
    body(x) {
      x.beginPath(); x.moveTo(-34, 0); x.bezierCurveTo(-40, -50, -26, -78, 0, -80); x.bezierCurveTo(26, -78, 40, -50, 36, 0); x.closePath(); x.fill();
      ell(x, 4, -98, 28, 24); x.fill();
      x.beginPath(); x.moveTo(-20, -112); x.lineTo(-22, -138); x.lineTo(-4, -120); x.closePath(); x.moveTo(14, -120); x.lineTo(26, -138); x.lineTo(28, -110); x.closePath(); x.fill();
      x.lineWidth = 9; x.lineCap = 'round'; x.strokeStyle = x.fillStyle; const s = Math.sin(S.t * 2) * 10;
      x.beginPath(); x.moveTo(30, -8); x.bezierCurveTo(62, -10, 70 + s * .3, -40, 56 + s, -70); x.stroke();
      ell(x, -14, -2, 11, 5); x.fill(); ell(x, 12, -2, 11, 5); x.fill();
    },
    face(x, c, lk) {
      if (c.blush > .45) happyEyes(x, -6, -98, 16, -98, 6, 3);
      else { x.fillStyle = '#fff'; ell(x, -6, -98, 6.5, 6 * c.open); x.fill(); ell(x, 16, -98, 6.5, 6 * c.open); x.fill();
        x.fillStyle = BLK; ell(x, -6 + lk * 2, -98, 1.8, 5 * c.open); x.fill(); ell(x, 16 + lk * 2, -98, 1.8, 5 * c.open); x.fill(); }
      cheeks(x, -16, 26, -86, c.blush, 2, 6, 8, 2.8);
    },
    lit(x) { x.strokeStyle = CREAM; x.lineWidth = 1.4; x.beginPath(); for (const s of [-1, 1]) for (let i = 0; i < 2; i++) { x.moveTo(5 + s * 14, -88 + i * 5); x.lineTo(5 + s * 34, -91 + i * 9); } x.stroke(); },
  },
};
function mk(kind, x, o = {}) {
  return Object.assign({ kind, x, st: 'wait', m: 0, cov: 0, blush: 0, k: 0, at: 0, hat: 0, peek: 0, pt: 0, part: 0, spot: 0, cd: 0, duck: 0, duckT: 0,
    gifted: false, open: 1, blink: 1 + Math.random() * 3, kb: [0, 0, 0], kcov: [0, 0, 0], kcd: [0, 0, 0], force: 0, giggleT: 2, edgeX: 0, afterT: 0 }, o);
}
function hideBase(i) { const s = HSP[i]; return s.m === 'hang' ? { X: s.x, B: ground(s.x) - 234, s: 1, sy: -1 } : { X: s.x, B: ground(s.x) + 3 + (s.m === 'grass' ? 86 : 0), s: 1, sy: 1 }; }
function tf(c) {
  const sp = SPEC[c.kind];
  if (c.kind === 'hide') {
    if (c.st === 'flee') { const a = hideBase(c.spot), b = hideBase(c.spot + 1), k = sm(c.k); return { X: lerp(a.X, b.X, k), B: lerp(a.B, b.B, k) - Math.sin(k * Math.PI) * 220, s: 1 - Math.sin(k * Math.PI) * .35, sy: lerp(a.sy, b.sy, k) }; }
    const b = hideBase(c.spot); if (c.st === 'wait') return b;
    const k = eOut(c.k); return { X: b.X + sp.adx * k, B: lerp(b.B, ground(b.X + sp.adx) + 3, k) - sp.arise * k, s: 1 - (1 - sp.as) * k, sy: lerp(b.sy, 1, Math.min(1, k * 2)) };
  }
  const k = c.st === 'wait' ? 0 : eOut(c.k), X = c.x + (sp.adx || 0) * k;
  return { X, B: ground(X) + 3 - (sp.arise || 0) * k + (c.kind === 'shroom' ? c.duck * 26 : 0), s: 1 - (1 - (sp.as || 1)) * k, sy: 1 };
}
function kidTf(c, j) {
  const x0 = c.x + TRIO[j], b0 = walkY(x0) + 2;
  if (c.st === 'wait') return { X: x0, B: b0, s: 1, sy: 1 };
  const k = c.st === 'aside' ? 1 : eOut(c.k), g = TRIO_GO[j];
  return { X: x0 + g[0] * k, B: b0 + g[1] * k - Math.sin(k * Math.PI) * g[2], s: lerp(1, g[3], k), sy: 1 };
}
const wpt = (t, lx, ly) => [t.X + lx * t.s, t.B + ly * t.s * t.sy];
function covOf(t, pts) { let n = 0; for (const [lx, ly] of pts) { const [x, y] = wpt(t, lx, ly); if (isLit(x, y)) n++; } return n / pts.length; }
function isLit(x, y) {
  const L = S.L; if (!L) return false;
  return (x - L.x) ** 2 + (y - L.y) ** 2 < (L.r * .97) ** 2 || (x - L.lx) ** 2 + (y - L.ly) ** 2 < (L.lr * .92) ** 2;
}
function blocks(c) { return SPEC[c.kind].block && c.st === 'wait'; }
function headPt(c) {
  const sp = SPEC[c.kind], t = tf(c);
  if (t.sy < 0) return [t.X, t.B - 34];
  return [t.X, t.B - (sp.h + 34) * t.s];
}

/* реплики */
function say(who, text, x, y, o = {}) {
  S.says = S.says.filter((s) => s.who !== who);
  S.says.push({ who, text, x, y, t: 0, life: o.life || 2.8, soft: !!o.soft, follow: o.follow || null });
}
function line(c, text, o = {}) { if (!text) return; const [x, y] = headPt(c); say(c.kind, text, x, y, Object.assign({ follow: c }, o)); }

/* ---------------- обновление теней ---------------- */
function updChar(c, dt) {
  const sp = SPEC[c.kind];
  c.blink -= dt; if (c.blink < -.13) c.blink = 2 + Math.random() * 3.5; c.open = c.blink < 0 ? .1 : 1;
  c.cd -= dt;
  if (c.kind === 'trio') return updTrio(c, dt);
  const t = tf(c); c.cov = covOf(t, sp.pts(c));
  const play = S.mode === 'play';
  const tgt = c.force ? 1 : c.cov > .2 ? 1 : 0;
  c.blush = clamp(c.blush + (tgt ? 3.2 : -1.1) * dt, 0, 1);
  c.edgeX = t.X - sp.hw * t.s - 34 - (sp.gap || 0);
  if (c.kind === 'gent') c.hat = c.force ? 1 : c.st === 'wait' ? clamp(c.m / sp.dur, 0, 1) * .8 : c.st === 'yield' ? 1 : clamp(1 - (c.afterT - 1.6) / .8, 0, 1);
  if (c.kind === 'giant') {
    c.pt += dt; const cyc = c.pt % 4.2, want = c.force ? .9 : c.cov > .25 ? .75 : (cyc > 2.4 && cyc < 3.7 ? 1 : .0);
    c.peek += (want - c.peek) * Math.min(1, dt * 6);
    if (play && c.st === 'wait' && c.cov >= .3 && c.cov < sp.need) { c.part += dt; if (c.part > .6 && c.cd <= 0) { line(c, A.pick(['ой… ой…', 'я очень большая…', 'ну совсем чуть-чуть…'])); snd.oy(); S.needRaise = true; c.cd = 3.4; } }
    else c.part = Math.max(0, c.part - dt);
  }
  if (c.kind === 'shroom') {
    c.duckT -= dt; c.duck = clamp(c.duck + (c.duckT > 0 ? 4 : -1.5) * dt, 0, 1);
    if (play && c.cov >= sp.need && c.duckT <= 0) { c.m += dt; if (c.m > sp.dur) { c.m = 0; c.duckT = 4; say('shroom', '— хи-хи —', t.X, t.B - 92, { soft: true }); snd.giggle();
      if (!c.gifted) { c.gifted = true; const f = S.flies.find((q) => q.gift); if (f) { f.st = 'idle'; f.wx = t.X; f.wy = t.B - 40; launch(f); } } } }
    return;
  }
  if (c.kind === 'hide' && play && c.st === 'wait' && c.spot > 0 && c.cov < .2) {
    c.giggleT -= dt; const near = Math.abs(S.pip.x - t.X) < (LAND ? 620 : 520);
    if (near && c.giggleT <= 0) { c.giggleT = 4.5; const [ex, ey] = wpt(t, 0, -110); say('hide', '— хи-хи —', ex + 40, ey - 40 * t.sy, { soft: true, life: 2 }); snd.giggle(.6); }
  }
  if (c.kind === 'sleepy' && play && c.st === 'wait' && c.cov < .2) {
    c.giggleT -= dt; if (c.giggleT <= 0 && Math.abs(S.pip.x - t.X) < (LAND ? 700 : 560)) { c.giggleT = 3.6; say('sleepy', 'хр-р… пс-с…', t.X + 20, t.B - 100, { soft: true, life: 2.2 }); snd.snore(); }
  }
  if (c.st === 'wait') {
    if (!play) return;
    if (c.cov >= sp.need) {
      if (c.m === 0 && c.cd <= 0) { const f = c.kind === 'hide' ? ['ай!', 'ой, нашёл…', 'опять нашёл!', 'ну ладно…'][c.spot] : sp.first; if (f) { line(c, f); c.cd = 3; snd.oy(); } }
      c.m += dt;
    } else c.m = Math.max(0, c.m - dt * .6);
    if (c.m >= sp.dur) done(c);
  } else if (c.st === 'yield' || c.st === 'flee') {
    c.k += dt / (c.st === 'flee' ? 1.05 : 1.3);
    if (c.k >= 1) {
      c.k = 1;
      if (c.st === 'flee') { c.spot++; c.st = 'wait'; c.m = 0; c.k = 0; c.giggleT = 1.2; }
      else c.st = 'aside';
    }
  } else if (c.st === 'aside') {
    c.afterT += dt;
    if (sp.after && c.afterT > 1.8 && !c.saidAfter) { c.saidAfter = true; const X = tf(c).X; if (X > S.cam + 40 && X < S.cam + W - 40) line(c, sp.after, { soft: true }); }
  }
}
function done(c) {
  const sp = SPEC[c.kind];
  c.m = 0; c.k = 0; c.afterT = 0; S.pip.happy = 2.6;
  if (c.kind === 'hide' && c.spot < HSP.length - 1) { c.st = 'flee'; line(c, ['хи-хи, догоняй!', 'а вот и нет!', 'а я в траве!'][c.spot]); snd.whoosh(); return; }
  c.st = 'yield';
  line(c, c.kind === 'hide' ? 'нашёл. проходи' : sp.go);
  if (sp.sfx) sp.sfx(); else snd.giggle();
  if (c.kind === 'giant') S.needRaise = false;
  const [x, y] = headPt(c); puff(x, y + 40, 10);
}
function updTrio(c, dt) {
  const sp = SPEC.trio, play = S.mode === 'play';
  let mn = 1, any = 0;
  for (let j = 0; j < 3; j++) {
    const t = kidTf(c, j), cv = covOf(t, sp.pts()); c.kcov[j] = cv; c.kcd[j] -= dt;
    mn = Math.min(mn, cv); if (cv >= sp.need) any++;
    c.kb[j] = clamp(c.kb[j] + ((c.force || cv > .2) ? 3.2 : -1.1) * dt, 0, 1);
    if (play && c.st === 'wait' && cv >= sp.need && c.kcd[j] <= 0) { c.kcd[j] = 3.2; say('trio' + j, ['хи-хи', 'ой', 'не я!'][j], t.X, t.B - 112, { soft: j !== 2, life: 2 }); if (j === 1) snd.oy(); else snd.giggle(.7); }
  }
  c.cov = mn; c.blush = Math.max(...c.kb);
  const t0 = kidTf(c, 0); c.edgeX = t0.X - sp.hw - 34 - sp.gap;
  if (!play) return;
  if (c.st === 'wait') {
    if (any && any < 3) S.trioPart += dt;
    if (mn >= sp.need) c.m += dt; else c.m = Math.max(0, c.m - dt * .6);
    if (c.m >= sp.dur) { c.st = 'yield'; c.k = 0; S.trioPart = 0; S.pip.happy = 2.6; const t = kidTf(c, 1); say('trio1', 'ой-ой-ой!', t.X, t.B - 120); snd.scatter(); puff(t.X, t.B - 50, 14); }
  } else if (c.st === 'yield') { c.k += dt / 1.2; if (c.k >= 1) { c.k = 1; c.st = 'aside'; } }
}

/* ---------------- светлячки, глаза, искры ---------------- */
function mkFly([x, h, kind]) { return { x, h, st: kind === 'gift' ? 'hidden' : 'idle', gift: kind === 'gift', ph: Math.random() * 6, lit: 0, wx: x, wy: ground(x) - h, t: 0 }; }
function launch(f) { const L = S.lan; f.st = 'go'; f.t = 0; f.sx = f.wx; f.sy = f.wy; f.cx = (f.wx + L.lx) / 2 + (Math.random() - .5) * 80; f.cy = Math.min(f.wy, L.ly) - 90 - Math.random() * 50; }
function updFlies(dt) {
  for (const f of S.flies) {
    f.ph += dt;
    if (f.st === 'idle') {
      f.wx = f.x + Math.sin(f.ph * 1.3) * 6; f.wy = ground(f.x) - f.h + Math.sin(f.ph * 1.9) * 5;
      if (S.mode === 'play' && isLit(f.wx, f.wy)) { f.lit += dt; if (f.lit > .22) launch(f); } else f.lit = Math.max(0, f.lit - dt);
    } else if (f.st === 'go') {
      f.t += dt; const k = sm(f.t / .9), L = S.lan, u = 1 - k;
      f.wx = u * u * f.sx + 2 * u * k * f.cx + k * k * L.lx; f.wy = u * u * f.sy + 2 * u * k * f.cy + k * k * L.ly;
      if (Math.random() < .6) S.parts.push({ x: f.wx, y: f.wy, vx: (Math.random() - .5) * 20, vy: 12, life: .5, max: .5, s: 2 });
      if (f.t >= .9) {
        f.st = 'got';
        if (f.rescue) S.oil = Math.min(100, S.oil + 32); else { S.count++; S.oil = Math.min(100, S.oil + 15); }
        snd.fly(S.count - 1); S.pip.happy = Math.max(S.pip.happy, 1.2);
        for (let i = 0; i < 12; i++) { const a = Math.random() * TAU, v = 40 + Math.random() * 90; S.parts.push({ x: L.lx, y: L.ly, vx: Math.cos(a) * v, vy: Math.sin(a) * v, life: .7, max: .7, s: 2.4 }); }
      }
    }
  }
  S.flies = S.flies.filter((f) => f.st !== 'got' || !f.rescue);
}
function updEyes(dt) {
  for (const e of S.eyes) {
    e.ph += dt; e.blink -= dt; if (e.blink < -.14) e.blink = 2 + Math.random() * 4;
    const x = e.x, y = ground(e.x) - e.h;
    if (S.mode !== 'title' && isLit(x, y)) {
      if (e.vis > .7 && S.mode === 'play' && S.sayCD <= 0 && Math.random() < .55) { say('eye', A.pick(EYE_LINES), x, y - 30, { life: 2.2 }); S.sayCD = 3.4; snd.oy(); }
      e.vis = Math.max(0, e.vis - dt * 6); e.hideT = 4 + Math.random() * 3;
    } else { e.hideT -= dt; if (e.hideT <= 0) e.vis = Math.min(1, e.vis + dt * 1.4); }
  }
}
function puff(x, y, n) { for (let i = 0; i < n; i++) { const a = Math.random() * TAU, v = 30 + Math.random() * 70; S.parts.push({ x, y, vx: Math.cos(a) * v, vy: Math.sin(a) * v - 20, life: .9, max: .9, s: 2.2 }); } }

/* ---------------- Пип и фонарь ---------------- */
function lantern() {
  const p = S.pip, k = sm(p.raiseK), f = p.face, bob = p.walking ? -Math.abs(Math.sin(p.ph)) * 4 : Math.sin(S.t * 2.2);
  const sw = Math.sin(S.t * 2.4) * .08 + (p.walking ? Math.sin(p.ph * .5) * .14 : 0);
  const hx = p.x + 40 * f, hy = p.y - 46 + bob, tx = hx + lerp(30, 9, k) * f, ty = hy - lerp(50, 104, k);
  return { hx, hy, tx, ty, lx: tx + Math.sin(sw) * 14, ly: ty + Math.cos(sw) * 14, sw, bob };
}
function computeLight() {
  const p = S.pip, L = S.lan = lantern(), k = sm(p.raiseK);
  const oilF = S.oil > 0 ? .52 + .48 * Math.min(1, S.oil / 30) : .38;
  const fl = 1 + .012 * Math.sin(S.t * 13) + .008 * Math.sin(S.t * 29.7) + (S.oil < 14 ? .045 * Math.sin(S.t * 37) * Math.sin(S.t * 5.3) : 0);
  const a = p.alpha;
  if (S.override) { const o = S.override; S.L = { x: o.x, y: o.y, r: o.r * fl, lx: L.lx, ly: L.ly, lr: 96 * fl }; return; }
  const reach = lerp(170, 260, k); let ax = S.aim.x, ay = S.aim.y; const m = Math.hypot(ax, ay); if (m > reach) { ax *= reach / m; ay *= reach / m; }
  S.L = { x: L.lx + ax, y: L.ly + ay, r: lerp(165, 250, k) * oilF * fl * a, lx: L.lx, ly: L.ly, lr: lerp(92, 104, k) * (S.oil > 0 ? 1 : .8) * fl * a };
}
function setAimWorld(wx, wy) { const L = S.lan || lantern(); S.aim.x = wx - L.lx; S.aim.y = wy - L.ly; }
function drawPip(c) {
  const p = S.pip; if (p.alpha <= .01) return;
  const f = p.face, L = S.lan, bob = L.bob, sh = p.shiver > 0 ? Math.sin(S.t * 60) * 1.4 * p.shiver : 0;
  c.save(); c.globalAlpha = p.alpha; c.translate(p.x + sh, p.y); c.scale(f, 1);
  c.fillStyle = BLK; c.strokeStyle = BLK; c.lineCap = 'round';
  const st = p.walking ? Math.sin(p.ph) * 8 : 0, lift = p.walking ? Math.max(0, Math.cos(p.ph)) * 3 : 0;
  ell(c, -12 + st, -4 - lift, 10, 6); c.fill(); ell(c, 14 - st, -4 - (p.walking ? Math.max(0, -Math.cos(p.ph)) * 3 : 0), 10, 6); c.fill();
  c.translate(0, bob);
  c.beginPath(); c.moveTo(-30, -8); c.bezierCurveTo(-36, -50, -26, -84, 0, -86); c.bezierCurveTo(26, -84, 36, -50, 30, -8); c.quadraticCurveTo(0, 0, -30, -8); c.fill();
  // колпак: кисточка свисает назад и покачивается
  const cs = (p.walking ? Math.sin(p.ph * .5) * 5 : Math.sin(S.t * 1.6) * 2);
  c.beginPath(); c.moveTo(-28, -70); c.bezierCurveTo(-20, -104, 18, -108, 26, -76); c.bezierCurveTo(4, -98, -30, -104, -44 + cs * .4, -80 + cs * .3); c.bezierCurveTo(-40, -76, -34, -72, -28, -70); c.fill();
  ell(c, -46 + cs * .5, -76 + cs * .4, 8, 8); c.fill();
  // рука, палка, шнурок
  const lx = (L.hx - p.x) * f, ly = L.hy - p.y - bob, tx = (L.tx - p.x) * f, ty = L.ty - p.y - bob, ox = (L.lx - p.x) * f, oy = L.ly - p.y - bob;
  c.lineWidth = 7; c.beginPath(); c.moveTo(22, -40); c.quadraticCurveTo(36, -46, lx, ly); c.stroke();
  c.lineWidth = 4; c.beginPath(); c.moveTo(lx - (tx - lx) * .2, ly - (ty - ly) * .2); c.lineTo(tx, ty); c.stroke();
  c.lineWidth = 2; c.beginPath(); c.moveTo(tx, ty); c.lineTo(ox, oy - 14); c.stroke();
  // глаза — огромные, смотрят туда, куда светит фонарь
  const am = Math.hypot(S.aim.x, S.aim.y) || 1, dx = S.aim.x / am * f, dy = S.aim.y / am, open = p.blink < 0 ? .12 : 1;
  c.fillStyle = '#fff'; ell(c, 2, -52, 9, 12 * open); c.fill(); ell(c, 22, -51, 8, 11 * open); c.fill();
  if (open > .5) { c.fillStyle = BLK; ell(c, 4 + dx * 3, -51 + dy * 4, 4.6, 4.6); c.fill(); ell(c, 24 + dx * 3, -50 + dy * 4, 4.2, 4.2); c.fill();
    c.fillStyle = '#fff'; ell(c, 5.5 + dx * 3, -53 + dy * 4, 1.5, 1.5); c.fill(); ell(c, 25.5 + dx * 3, -52 + dy * 4, 1.4, 1.4); c.fill(); }
  c.strokeStyle = '#fff'; c.lineWidth = 2;
  if (p.happy > 0) { c.beginPath(); c.arc(14, -34, 5, .2, Math.PI - .2); c.stroke(); }
  else { ell(c, 14, -30, 3, 3.6); c.stroke(); }
  c.restore();
}
function drawLantern(c) {
  const p = S.pip, L = S.lan; if (p.alpha <= .01) return;
  const x = L.lx, y = L.ly, a = p.alpha, oilF = S.oil > 0 ? .55 + .45 * Math.min(1, S.oil / 30) : .35;
  const fl = .9 + .1 * Math.sin(S.t * 17) * Math.sin(S.t * 7.3);
  glow(c, x, y, 150 * oilF, .28 * a * fl); glow(c, x, y, 64, .7 * a * oilF);
  c.save(); c.globalAlpha = a; c.translate(x, y); c.rotate(-L.sw * .6);
  c.fillStyle = BLK; c.beginPath(); c.moveTo(-11, -12); c.lineTo(11, -12); c.lineTo(9, 14); c.lineTo(-9, 14); c.closePath(); c.fill();
  c.fillRect(-14, -17, 28, 6); c.fillRect(-12, 13, 24, 5); c.beginPath(); c.arc(0, -19, 5, Math.PI, 0); c.lineWidth = 2; c.strokeStyle = BLK; c.stroke();
  const fs = (.75 + .25 * fl) * (S.oil > 0 ? 1 : .6);
  c.fillStyle = AMB; c.beginPath(); c.moveTo(0, 9 - 17 * fs); c.quadraticCurveTo(7 * fs, 2, 0, 9); c.quadraticCurveTo(-7 * fs, 2, 0, 9 - 17 * fs); c.fill();
  c.fillStyle = '#fff3cf'; ell(c, 0, 4, 2.2 * fs, 3.8 * fs); c.fill();
  c.restore();
}

/* ---------------- декорации ---------------- */
function buildDecor() {
  return [
    { k: 'sign', x: 520 }, { k: 'mush', x: 858 }, { k: 'stump', x: 1010 }, { k: 'oak', x: 2150 }, { k: 'stump', x: 2470 },
    { k: 'tree', x: 3740 }, { k: 'bush', x: 4352 }, { k: 'stump', x: 4800 }, { k: 'bridge' }, { k: 'reeds' }, { k: 'house' },
  ];
}
const LAYER = { oak: 'bg', sign: 'back', stump: 'back', tree: 'back', house: 'back', bridge: 'bridge', mush: 'front', bush: 'front', reeds: 'front' };
function decor(c, layer, P) {
  for (const d of S.decor) {
    if (LAYER[d.k] !== layer) continue;
    if (d.x != null && (d.x < S.cam - 600 || d.x > S.cam + W + 600)) continue;
    DRAW[d.k](c, d, P);
  }
}
const DRAW = {
  sign(c, d) { const x = d.x, y = ground(x); c.fillStyle = BLK; c.fillRect(x - 3, y - 112, 6, 116);
    c.beginPath(); c.moveTo(x - 40, y - 114); c.lineTo(x + 58, y - 116); c.lineTo(x + 78, y - 99); c.lineTo(x + 58, y - 82); c.lineTo(x - 40, y - 84); c.closePath(); c.fill(); },
  mush(c, d) { const x = d.x, y = ground(x); c.fillStyle = BLK; c.fillRect(x - 6, y - 38, 14, 42); c.beginPath(); c.ellipse(x + 1, y - 40, 34, 18, 0, Math.PI, 0); c.fill();
    c.fillRect(x - 40, y - 12, 6, 14); c.beginPath(); c.ellipse(x - 37, y - 12, 12, 7, 0, Math.PI, 0); c.fill(); },
  stump(c, d) { const x = d.x, y = ground(x); c.fillStyle = BLK; c.beginPath(); c.moveTo(x - 34, y + 2); c.lineTo(x - 26, y - 40); c.lineTo(x - 10, y - 46); c.lineTo(x + 4, y - 38); c.lineTo(x + 18, y - 48); c.lineTo(x + 26, y - 40); c.lineTo(x + 36, y + 2); c.closePath(); c.fill();
    c.lineWidth = 6; c.strokeStyle = BLK; c.lineCap = 'round'; c.beginPath(); c.moveTo(x + 22, y - 30); c.quadraticCurveTo(x + 40, y - 52, x + 54, y - 56); c.stroke(); },
  oak(c, d, P) {        // старый дуб — ближе дальнего леса, но ещё фон (свой цвет в каждом мире)
    const x = d.x, y = ground(x) + 6; c.fillStyle = P.oak; c.strokeStyle = P.oak; c.lineCap = 'round';
    c.beginPath(); c.moveTo(x - 150, y); c.bezierCurveTo(x - 80, y - 40, x - 66, y - 200, x - 64, y - 420); c.lineTo(x - 50, -10); c.lineTo(x + 54, -10); c.lineTo(x + 62, y - 420); c.bezierCurveTo(x + 66, y - 200, x + 86, y - 40, x + 160, y); c.closePath(); c.fill();
    c.lineWidth = 30; c.beginPath(); c.moveTo(x + 40, y - 330); c.quadraticCurveTo(x + 150, y - 360, x + 250, y - 330); c.stroke();
    c.lineWidth = 14; c.beginPath(); c.moveTo(x + 200, y - 344); c.quadraticCurveTo(x + 250, y - 400, x + 300, y - 410); c.stroke();
    c.lineWidth = 34; c.beginPath(); c.moveTo(x - 40, y - 470); c.quadraticCurveTo(x - 200, y - 500, x - 290, y - 590); c.stroke();
    c.fillStyle = P === DARK ? '#0d0d0f' : '#5e594f'; ell(c, x - 8, y - 230, 22, 34); c.fill();
  },
  tree(c, d) {          // близкое дерево с веткой над тропинкой (на ней висит Прятунья)
    const x = d.x, y = ground(x) + 4; c.fillStyle = BLK; c.strokeStyle = BLK; c.lineCap = 'round';
    c.beginPath(); c.moveTo(x - 70, y); c.bezierCurveTo(x - 34, y - 30, x - 30, y - 200, x - 34, y - 400); c.lineTo(x - 30, y - 900); c.lineTo(x + 26, y - 900); c.lineTo(x + 28, y - 400); c.bezierCurveTo(x + 30, y - 200, x + 36, y - 30, x + 76, y); c.closePath(); c.fill();
    blade(c, x + 10, y - 300, x + 330, y - 232, -30, 26);
    c.lineWidth = 5; c.beginPath(); c.moveTo(x + 180, y - 268); c.quadraticCurveTo(x + 200, y - 300, x + 230, y - 306); c.stroke();
    for (let i = 0; i < 11; i++) { const t = .2 + i * .07, bx = lerp(x + 10, x + 330, t), by = lerp(y - 300, y - 232, t), s = i % 2 ? 1 : -1; ell(c, bx + 6, by - 4 + s * 9, 11, 4.2, .35 + s * .55); c.fill(); }
  },
  bush(c, d) { const x = d.x, y = ground(x) + 4; c.fillStyle = BLK; c.beginPath();
    for (const [dx, dy, r] of [[-62, -26, 30], [-30, -56, 40], [12, -66, 40], [52, -46, 34], [74, -22, 26], [-6, -28, 44]]) { c.moveTo(x + dx + r, y + dy); c.arc(x + dx, y + dy, r, 0, TAU); }
    c.fill(); c.fillRect(x - 80, y - 24, 162, 26); },
  reeds(c) {
    c.fillStyle = BLK; const r = rng(55);
    for (const [x0, x1] of [[GAP[0] - 60, GAP[0] + 50], [GAP[1] - 50, GAP[1] + 60]]) for (let i = 0; i < 9; i++) {
      const x = lerp(x0, x1, r()), y = gtop(x) + 6, h = 50 + r() * 70, s = Math.sin(S.t * 1.3 + i) * 3;
      blade(c, x, y, x + s + (r() - .5) * 20, y - h, s, 4);
      if (r() < .45) { c.save(); c.translate(x + s, y - h * .86); A.rr(c, -4, -14, 8, 26, 4); c.fill(); c.restore(); }
    }
  },
  bridge(c) {
    c.fillStyle = BLK; c.strokeStyle = BLK; c.lineCap = 'round';
    c.beginPath(); c.moveTo(B0, walkY(B0)); for (let x = B0; x <= B1; x += 10) c.lineTo(x, walkY(x)); for (let x = B1; x >= B0; x -= 10) c.lineTo(x, walkY(x) + 10); c.closePath(); c.fill();
    c.lineWidth = 8; for (const x of [GAP[0] + 24, (GAP[0] + GAP[1]) / 2, GAP[1] - 24]) { c.beginPath(); c.moveTo(x, walkY(x) + 6); c.lineTo(x + 3, GY + DIP + 6); c.stroke(); }
    const posts = []; for (let x = B0 + 14; x <= B1 - 8; x += 93) posts.push(x);
    c.lineWidth = 5; posts.forEach((x) => { c.beginPath(); c.moveTo(x, walkY(x)); c.lineTo(x, walkY(x) - 34); c.stroke(); });
    c.lineWidth = 2.5; c.beginPath(); posts.forEach((x, i) => { const y = walkY(x) - 32; if (!i) c.moveTo(x, y); else { const px = posts[i - 1]; c.quadraticCurveTo((px + x) / 2, (walkY(px) + walkY(x)) / 2 - 20, x, y); } }); c.stroke();
  },
  house(c) {
    const x = HX, y = ground(HX) + 4; c.fillStyle = BLK; c.strokeStyle = BLK;
    c.lineWidth = 5; c.lineCap = 'round';
    for (let fx = x - 370; fx < x - 150; fx += 30) { const fy = ground(fx) + 2; c.beginPath(); c.moveTo(fx, fy); c.lineTo(fx, fy - 46); c.stroke(); c.beginPath(); c.moveTo(fx - 3, fy - 50); c.lineTo(fx, fy - 56); c.lineTo(fx + 3, fy - 50); c.fill(); }
    c.lineWidth = 3; c.beginPath(); c.moveTo(x - 372, ground(x - 372) - 34); c.lineTo(x - 150, ground(x - 150) - 34); c.moveTo(x - 372, ground(x - 372) - 16); c.lineTo(x - 150, ground(x - 150) - 16); c.stroke();
    c.fillRect(x - 122, y - 170, 240, 174);
    c.beginPath(); c.moveTo(x - 156, y - 160); c.lineTo(x - 4, y - 296); c.lineTo(x + 152, y - 160); c.closePath(); c.fill();
    c.fillRect(x + 56, y - 276, 30, 80); c.fillRect(x + 51, y - 284, 40, 11);
    c.fillRect(DOOR - 48, y - 12, 96, 13); c.fillRect(DOOR - 38, y - 23, 76, 12);
  },
};
function houseLights(c) {
  if (HX < S.cam - 400 || HX > S.cam + W + 400) return;
  const y = ground(HX) + 4, wx = HX + 50, wy = y - 112, fl = .92 + .08 * Math.sin(S.t * 2.1) * Math.sin(S.t * 5.3);
  glow(c, wx, wy, 190, .32 * fl + .25 * S.door); glow(c, wx, wy, 70, .5 * fl);
  c.fillStyle = AMB; c.fillRect(wx - 25, wy - 22, 50, 44);
  c.fillStyle = '#ffd98a'; c.fillRect(wx - 16, wy - 14, 32, 26);
  c.fillStyle = BLK; c.fillRect(wx - 2, wy - 22, 4, 44); c.fillRect(wx - 25, wy - 2, 50, 4); c.fillRect(wx - 30, wy + 22, 60, 6);
  c.fillRect(wx - 26, wy + 2, 9, 12); ell(c, wx - 21.5, wy + 2, 4.5, 2.5); c.fill();
  const dy = y - 23, dw = 23, dh = 70;
  if (S.door > .01) {
    c.save(); c.beginPath(); c.moveTo(DOOR - dw, dy); c.lineTo(DOOR - dw, dy - dh + dw); c.arc(DOOR, dy - dh + dw, dw, Math.PI, 0); c.lineTo(DOOR + dw, dy); c.closePath(); c.clip();
    c.fillStyle = 'rgba(255,183,43,' + S.door + ')'; c.fillRect(DOOR - dw, dy - dh, dw * 2, dh);
    c.fillStyle = BLK; c.fillRect(DOOR - dw + dw * 2 * sm(S.door) * .8, dy - dh, dw * 2, dh); c.restore();
    glow(c, DOOR, dy - 30, 170, .45 * S.door);
  } else { c.strokeStyle = '#1a1a1d'; c.lineWidth = 2; c.beginPath(); c.moveTo(DOOR - dw, dy); c.lineTo(DOOR - dw, dy - dh + dw); c.arc(DOOR, dy - dh + dw, dw, Math.PI, 0); c.lineTo(DOOR + dw, dy); c.stroke(); }
}
function litDetails(c, rect) {            // то, что видно только на свету: надпись на указателе, крапинки гриба, бабочка джентльмена
  for (const d of S.decor) {
    if (d.x == null || d.x < S.cam - 300 || d.x > S.cam + W + 300) continue;
    if (d.k === 'sign') { const x = d.x, y = ground(x); rect(x - 44 - S.cam, y - 120, 130, 44); c.fillStyle = CREAM; c.font = '800 21px ' + A.FONT; c.textAlign = 'left'; c.textBaseline = 'middle'; c.letterSpacing = '1px'; c.fillText('ДОМОЙ', x - 30, y - 99); c.letterSpacing = '0px'; }
    if (d.k === 'mush') { const x = d.x, y = ground(x); rect(x - 40 - S.cam, y - 64, 80, 34); c.fillStyle = CREAM; for (const [dx, dy, r] of [[-14, -48, 4], [4, -52, 5], [18, -45, 3], [-24, -42, 2.5]]) { ell(c, x + dx, y + dy, r, r); c.fill(); } }
  }
  for (const ch of S.chars) { const sp = SPEC[ch.kind]; if (!sp.lit || (ch.st !== 'wait' && ch.kind !== 'cat')) continue; const t = tf(ch); rect(t.X - S.cam - 60 * t.s, t.B - 130 * t.s, 120 * t.s, 140 * t.s); c.save(); c.translate(t.X, t.B); c.scale(t.s, t.s * t.sy); sp.lit(c, ch); c.restore(); }
}

/* ---------------- постройка мира и заставки ---------------- */
function buildWorld() {
  S.decor = buildDecor();
  S.chars = [mk('shroom', 884), mk('gent', 1400), mk('giant', 2800), mk('hide', HSP[0].x), mk('sleepy', 5150), mk('trio', 5730), mk('cat', 6890)];
  S.flies = FLIES.map(mkFly);
  S.eyes = EYES.map(([x, h, s]) => ({ x, h, s, vis: 1, hideT: 0, ph: Math.random() * 6, blink: Math.random() * 4, kind: Math.random() < .25 ? 'blink' : 'look' }));
  S.pip.x = 180; S.pip.y = walkY(180); S.cam = 0;
}
/* заставка и обложка — сцена из концепта: Пип со светом, джентльмен приподнимает шляпу, Громадина стесняется */
function stage(cover) {
  const o = LAND ? (cover ? 0 : -250) : 0;
  S.cam = 0; S.decor = []; S.flies = []; S.eyes = [];
  if (LAND) {
    S.pip.x = 556 + o; S.decor = [{ k: 'mush', x: 448 + o }, { k: 'sign', x: 692 + o }];
    S.chars = [mk('shroom', 474 + o), mk('gent', 362 + o, { force: 1 }), mk('giant', cover ? 880 : 1060, { force: 1 })];
    S.override = { x: 612 + o, y: 520, r: 252 };
    S.eyes = [[140, 130, 1.1], [196, 40, .8], [1090, 90, 1.1], [1150, 30, .9], [1210, 260, .8], [90, 300, .7], [1240, 180, .7], [760, 430, .8], [380, 380, .6]].map(([x, h, s], i) => ({ x: x + (i > 1 && i < 5 && !cover ? 60 : 0), h, s, vis: 1, hideT: 0, ph: i, blink: i * .7, kind: i % 3 === 1 ? 'blink' : 'look' }));
    S.flies = [[760, 130], [806, 160], [960, 130], [1010, 144], [1100, 130], [680, 198], [470 + o, 190]].map(([x, h]) => mkFly([x, h]));
    say('g1', 'после вас', 262 + o, ground(262) - 286, { life: 1e9 });
    say('g2', 'ой… не смотрите на меня', cover ? 900 : 1060, cover ? 244 : 150, { life: 1e9 });
    say('g3', '— хи-хи —', cover ? 1090 : 1160, cover ? 470 : 500, { life: 1e9, soft: true });
  } else {
    S.pip.x = 330; S.decor = [{ k: 'mush', x: 210 }, { k: 'sign', x: 470 }];
    S.chars = [mk('shroom', 236), mk('gent', 120, { force: 1 }), mk('giant', 600, { force: 1 })];
    S.override = { x: 380, y: GY - 110, r: 230 };
    S.eyes = [[80, 520, 1], [300, 640, .8], [560, 600, 1.1], [660, 760, .8], [150, 380, .9], [420, 470, .7], [640, 470, .7]].map(([x, h, s], i) => ({ x, h, s, vis: 1, hideT: 0, ph: i, blink: i * .7, kind: i % 3 === 1 ? 'blink' : 'look' }));
    S.flies = [[470, 250], [520, 300], [300, 330], [640, 230], [130, -200], [600, -170], [420, -260]].map(([x, h]) => mkFly([x, h]));
    for (const [x, h, sz] of [[230, -190, 1.1], [520, -250, .9], [90, -280, .8], [660, -300, .7]]) S.eyes.push({ x, h, s: sz, vis: 1, hideT: 0, ph: x, blink: x / 300, kind: 'look' });
    say('g3', '— хи-хи —', 520, GY + 200, { life: 1e9, soft: true });
    say('g1', 'после вас', 120, GY - 290, { life: 1e9 });
    say('g2', 'ой… не смотрите на меня', 470, GY - 520, { life: 1e9 });
  }
  S.pip.y = ground(S.pip.x); S.pip.face = 1; S.aim = { x: 60, y: -40 };
}

/* ---------------- подсказки ---------------- */
const HINTS = {
  walk: TOUCH ? 'Держите палец слева — Пип пойдёт. Водите пальцем справа — свет.' : '← → — идти. Мышь — куда светить.',
  shine: 'Посветите на тень: она застесняется и уступит дорогу.',
  giant: 'Посветите ей на лицо.',
  raise: TOUCH ? 'Она большая — поднимите фонарь: держите «выше».' : 'Она большая — поднимите фонарь: держите пробел.',
  hide: 'Прятунья убежала. Ищите в темноте её глаза — иногда и в траве.',
  sleepy: TOUCH ? 'Соня спит прямо на тропинке. Посветите пониже — ей в лицо.' : 'Соня спит прямо на тропинке. Посветите пониже — ей в лицо.',
  trio: 'Тройняшки стесняются только все вместе.',
  trioRaise: TOUCH ? 'Осветите всех троих сразу — держите «выше».' : 'Осветите всех троих сразу — держите пробел.',
  fly: 'Светлячки — масло для фонаря. Посветите на них.',
  oil: 'Масло кончается — ловите светом светлячков.',
};
const CTRL = TOUCH ? 'Слева — идти · справа — вести свет · «выше» — фонарь выше' : '← → — идти · мышь — светить · пробел — фонарь выше';
function nextBlocker() { let b = null; for (const c of S.chars) if (blocks(c) && c.edgeX > S.pip.x - 12 && (!b || c.edgeX < b.edgeX)) b = c; return b; }
function hintText() {
  const p = S.pip;
  if (S.mode !== 'play') return S.hint;
  if (S.oil < 16) return HINTS.oil;
  const b = nextBlocker();
  if (b && b.edgeX - p.x < (LAND ? 420 : 330)) {
    if (b.kind === 'giant') return S.needRaise ? HINTS.raise : HINTS.giant;
    if (b.kind === 'trio') return S.trioPart > .6 ? HINTS.trioRaise : HINTS.trio;
    if (b.kind === 'hide') return b.spot ? HINTS.hide : HINTS.shine;
    if (b.kind === 'sleepy') return HINTS.sleepy;
    return HINTS.shine;
  }
  if (S.moved < 160) return HINTS.walk;
  if (S.count === 0 && S.flies.some((f) => f.st === 'idle' && f.x > S.cam && f.x < S.cam + W)) return HINTS.fly;
  return CH[S.ch].tag;
}
function showCap() { S.cap = { t: 0, life: 7 }; }

/* ---------------- бот самопроверки ---------------- */
function botCtl(dt) {
  const p = S.pip, L = S.lan; let dir = 1, aim = null, raise = false;
  const b = nextBlocker(), near = b && b.edgeX - p.x < 520 ? b : null;
  let fly = null;
  for (const f of S.flies) if (f.st === 'idle' && !S.botSkip.has(f) && f.x > p.x - 200 && f.x < p.x + 420 && (!fly || Math.abs(f.x - p.x) < Math.abs(fly.x - p.x))) fly = f;
  if (fly) {
    if (S.botFly !== fly) { S.botFly = fly; S.botFT = 0; } S.botFT += dt; if (S.botFT > 7) S.botSkip.add(fly);
    aim = [fly.wx, fly.wy]; raise = Math.hypot(fly.wx - L.lx, fly.wy - L.ly) > 172;
    dir = fly.x > p.x + 140 ? 1 : fly.x < p.x - 150 ? -1 : 0;
  } else if (near) {
    if (near.kind === 'trio') { const t = kidTf(near, 1); aim = wpt(t, 0, -46); }
    else aim = wpt(tf(near), ...SPEC[near.kind].aim);
    raise = !!SPEC[near.kind].raise;
  } else aim = [p.x + 170, p.y - 130];
  return { dir, aim, raise };
}

/* ---------------- цикл ---------------- */
function sim(g, dt) {
  S.t += dt; const p = S.pip;
  if (S.mode !== 'end') S.fade = Math.max(0, S.fade - dt * 1.3);
  S.sayCD -= dt; S.bumpCD -= dt; S.chT += dt; S.hintF = Math.min(1, S.hintF + dt * 2.5);
  p.blink -= dt; if (p.blink < -.13) p.blink = 2.2 + Math.random() * 3; p.happy -= dt; p.shiver = Math.max(0, p.shiver - dt * 2);
  if (S.cap) { S.cap.t += dt; if (S.cap.t > S.cap.life) S.cap = null; }
  for (const s of S.says) s.t += dt; S.says = S.says.filter((s) => s.t < s.life);
  for (const q of S.parts) { q.life -= dt; q.vx *= 1 - dt * 2; q.vy *= 1 - dt * 2; q.x += q.vx * dt; q.y += q.vy * dt; } S.parts = S.parts.filter((q) => q.life > 0);
  if (S.mode === 'title') { computeLight(); for (const c of S.chars) updChar(c, dt); updFlies(dt); updEyes(dt); return; }
  if (S.mode === 'play') S.time += dt;
  ambience(dt);
  // ввод
  let dir = 0, raise = false;
  const inp = g.input;
  if (S.mode === 'play') {
    if (S.bot) { const b = botCtl(dt); dir = b.dir; raise = b.raise; if (b.aim) { S.aimMode = 'bot'; setAimWorld(b.aim[0], b.aim[1]); } }
    else {
      if (inp.down('left')) dir -= 1; if (inp.down('right')) dir += 1;
      for (const q of T.ptrs.values()) { if (q.zone === 'walk') dir = q.x < W / 4 ? -1 : 1; if (q.zone === 'up') raise = true; }
      raise = raise || inp.down('action') || S.mouseDown;
      if (inp.down('up') || inp.down('down')) { S.aimMode = 'kb'; S.elev = clamp(S.elev + (inp.down('up') ? 1 : -1) * 1.5 * dt, -1.1, 1.45); }
      if (inp.pressed('help')) showCap();
      if (S.aimMode === 'mouse' && S.mouse) setAimWorld(S.mouse.x + S.cam, S.mouse.y);
    }
  } else if (S.mode === 'outro') dir = p.x < DOOR - 2 ? 1 : 0;
  // ход
  p.walking = false;
  if (dir) {
    const sp = (S.mode === 'outro' ? 95 : 110) * dt; let nx = p.x + dir * sp;
    if (dir > 0 && S.mode === 'play') {
      const b = nextBlocker();
      if (b && nx > b.edgeX) { nx = Math.max(p.x, b.edgeX); if (p.x >= b.edgeX - .5) { p.shiver = 1; if (S.bumpCD <= 0) { S.bumpCD = 6; say('pip', 'брр…', p.x, p.y - 128, { soft: true, life: 1.6 }); snd.bump(); } } }
    }
    nx = clamp(nx, 70, DOOR);
    if (Math.abs(nx - p.x) > .01) { p.walking = true; p.ph += dt * 9; S.moved += Math.abs(nx - p.x); p.x = nx; p.stepT -= dt; if (p.stepT <= 0) { p.stepT = .33; snd.step(); } }
    p.face = dir;
  } else if ((S.aimMode === 'mouse' || S.aimMode === 'touch') && Math.abs(S.aim.x) > 50) p.face = Math.sign(S.aim.x);
  p.y = walkY(p.x);
  if (S.aimMode === 'kb') { S.aim.x = Math.cos(S.elev) * 160 * p.face; S.aim.y = -Math.sin(S.elev) * 160; }
  const was = p.raiseK; p.raiseK = clamp(p.raiseK + (raise ? 1 : -1) * dt * 4.5, 0, 1); if (was === 0 && p.raiseK > 0) snd.raise();
  // масло
  if (S.mode === 'play') {
    const o0 = S.oil; S.oil = Math.max(0, S.oil - lerp(1, 2.8, sm(p.raiseK)) * dt);
    if (o0 >= 14 && S.oil < 14) snd.sputter();
    if (S.oil <= 0) {
      S.rescue += dt;
      if (!S.emptySaid) { S.emptySaid = true; say('pip', 'светлячки, ау!', p.x, p.y - 130, { life: 2.4 }); snd.sputter(); }
      if (S.rescue > 1.8 && !S.flies.some((f) => f.rescue && f.st === 'go')) {
        S.rescue = 0; const f = { rescue: true, x: 0, h: 0, ph: 0, lit: 0, wx: p.x + (Math.random() < .5 ? -1 : 1) * W * .45, wy: GY - 320, t: 0 }; S.flies.push(f); launch(f);
      }
    } else { S.rescue = 0; if (S.oil > 20) S.emptySaid = false; }
  }
  computeLight();
  for (const c of S.chars) updChar(c, dt);
  updFlies(dt); updEyes(dt);
  // камера
  let ct = p.x - W * K.camK; const nb = nextBlocker();
  if (nb && nb.edgeX - p.x < W * .8) { const rx = nb.kind === 'trio' ? kidTf(nb, 2).X + 70 : tf(nb).X + SPEC[nb.kind].hw + 50; ct = Math.max(ct, Math.min(rx - W, p.x - 90)); }
  ct = clamp(ct, 0, WORLD - W); S.cam += (ct - S.cam) * Math.min(1, dt * 3.2);
  // участок
  let ci = 0; for (let i = 0; i < CH.length; i++) if (p.x >= CH[i].x) ci = i;
  if (ci !== S.ch) { S.ch = ci; S.chT = 0; snd.chapter(); }
  // подсказка
  S.hintT -= dt;
  if (S.hintT <= 0) { S.hintT = .3; const h = hintText(); if (h !== S.hint) { S.hintPrev = S.hint; S.hint = h; S.hintF = 0; } }
  if (!S.spoke && S.t > 1.4 && S.mode === 'play') { S.spoke = true; say('pip', 'я совсем не боюсь. почти.', p.x + 10, p.y - 130, { life: 3.2 }); }
  // домой
  if (S.mode === 'play' && p.x >= DOOR - 3) { S.mode = 'outro'; S.outT = 0; say('pip', 'я дома!', p.x, p.y - 130, { life: 2.4 }); }
  if (S.mode === 'outro' || S.mode === 'end') {
    S.outT += dt;
    if (S.outT > .5 && S.outT < 2.6) { if (S.door === 0) snd.door(); S.door = Math.min(1, S.door + dt * 1.6); }
    if (S.outT > 1.2) p.alpha = Math.max(0, p.alpha - dt * 1.5);
    if (S.outT > 2.6) S.door = Math.max(0, S.door - dt * 1.2);
    if (S.outT > 2.2 && !S.bye) {
      S.bye = true; const r = rng(77);
      for (let i = 0; i < 8; i++) S.eyes.push({ x: HX - 520 + r() * 900, h: 60 + r() * 330, s: .7 + r() * .5, vis: 0, hideT: .2 + i * .25, ph: i, blink: 1 + r() * 2, kind: 'happy' });
      setTimeout(() => S && S.bye && say('bye', 'спокойной ночи, Пип!', HX - 260, GY - 330, { life: 4 }), 900);
      setTimeout(() => S && S.bye && say('bye2', '— хи-хи —', HX + 230, GY - 240, { life: 3, soft: true }), 1900);
    }
    if (S.outT > 6.3 && S.mode === 'outro') finish();
  }
}
function update(g, dt) {
  const n = S.bot ? Math.max(1, S.ts | 0) : 1;
  for (let i = 0; i < n; i++) sim(g, dt);
}

/* ---------------- рисование ---------------- */
function lightBox() {
  const L = S.L; if (!L) return null;
  const e1 = L.r * (1 + RING) + 6, e2 = L.lr * (1 + RING) + 6, cx = S.cam;
  let x0 = Math.min(L.x - e1, L.lx - e2) - cx, x1 = Math.max(L.x + e1, L.lx + e2) - cx, y0 = Math.min(L.y - e1, L.ly - e2), y1 = Math.max(L.y + e1, L.ly + e2);
  x0 = clamp(Math.floor(x0), 0, W); x1 = clamp(Math.ceil(x1), 0, W); y0 = clamp(Math.floor(y0), 0, H); y1 = clamp(Math.ceil(y1), 0, H);
  if (x1 - x0 < 2 || y1 - y0 < 2 || (L.r < 2 && L.lr < 2)) return null;
  return { x: x0, y: y0, w: x1 - x0, h: y1 - y0 };
}
function disc(m, x, y, r) { if (r < 1) return; const k = r / R0, s = DSZ * k; m.drawImage(C.disc, x - s / 2, y - s / 2, s, s); }
function composite(c, bb) {
  const l = C.lbx, sc = C.sc, px = Math.floor(bb.x * sc), py = Math.floor(bb.y * sc), pw = Math.min(C.lb.width - px, Math.ceil(bb.w * sc) + 1), ph = Math.min(C.lb.height - py, Math.ceil(bb.h * sc) + 1);
  if (pw <= 0 || ph <= 0) return;
  l.save(); l.setTransform(1, 0, 0, 1, 0, 0); l.globalCompositeOperation = 'destination-in'; l.drawImage(C.mb, px, py, pw, ph, px, py, pw, ph); l.restore();
  c.save(); c.setTransform(1, 0, 0, 1, 0, 0); c.drawImage(C.lb, px, py, pw, ph, px, py, pw, ph); c.restore();
}
function moon(c) {
  const [x, y] = K.moon, gr = c.createRadialGradient(x, y, 20, x, y, 120);
  gr.addColorStop(0, 'rgba(255,255,255,.12)'); gr.addColorStop(1, 'rgba(255,255,255,0)'); c.fillStyle = gr; c.fillRect(x - 120, y - 120, 240, 240);
  c.save(); c.beginPath(); c.arc(x, y, 30, 0, TAU); c.clip(); c.beginPath(); c.rect(x - 32, y - 32, 64, 64); c.arc(x + 15, y - 11, 27, 0, TAU);
  c.fillStyle = '#e9e7e2'; c.fill('evenodd'); c.restore();
}
function bgPass(c, P) {
  const cam = S.cam;
  c.fillStyle = P.bg; c.fillRect(0, 0, W, H);
  drawTile(c, C.tiles[P.id].far, cam * .35);
  if (P === DARK) moon(c);
  if (P === LIT && S.L) {        // свет чуть теплее и ярче в середине
    const L = S.L, x = L.x - cam, gr = c.createRadialGradient(x, L.y, 0, x, L.y, Math.max(10, L.r * 1.2));
    gr.addColorStop(0, 'rgba(255,251,240,.55)'); gr.addColorStop(1, 'rgba(255,251,240,0)'); c.fillStyle = gr; c.fillRect(x - L.r * 1.2, L.y - L.r * 1.2, L.r * 2.4, L.r * 2.4);
  }
  drawTile(c, C.tiles[P.id].mid, cam * .65);
  c.save(); c.translate(-cam, 0);
  // ручей
  if (GAP[1] > cam - 50 && GAP[0] < cam + W + 50) {
    const wy = GY + DIP * .5; c.fillStyle = P.water; c.fillRect(GAP[0], wy, GAP[1] - GAP[0], DIP + 10);
    c.strokeStyle = P.rip; c.lineWidth = 2; c.beginPath();
    for (let i = 0; i < 7; i++) { const yy = wy + 6 + i * 5, x0 = GAP[0] + 40 + ((i * 97 + S.t * 18 * (i % 2 ? 1 : -1)) % 380 + 380) % 380; c.moveTo(x0, yy); c.lineTo(x0 + 26 + (i % 3) * 14, yy); }
    c.stroke();
  }
  decor(c, 'bg', P);
  for (const ch of S.chars) {
    if (ch.kind === 'trio') { if (ch.st !== 'wait') for (let j = 0; j < 3; j++) drawKid(c, ch, j, mix(BLK, P.fig, sm((ch.k - .2) / .8))); continue; }
    if (ch.st === 'wait' || ch.st === 'flee') continue;
    drawBody(c, ch, mix(BLK, P.fig, sm((ch.k - .2) / .8)));
  }
  c.restore();
}
function drawBody(c, ch, col) { const t = tf(ch); c.save(); c.translate(t.X, t.B); c.scale(t.s, t.s * t.sy); c.fillStyle = col; SPEC[ch.kind].body(c, ch); c.restore(); }
function drawFace(c, ch) {
  const t = tf(ch), lk = clamp((S.pip.x - t.X) / 220, -1, 1);
  c.save(); c.translate(t.X, t.B); c.scale(t.s, t.s * t.sy); SPEC[ch.kind].face(c, ch, lk * (t.sy < 0 ? 1 : 1)); c.restore();
}
function drawKid(c, ch, j, col) { const t = kidTf(ch, j); c.save(); c.translate(t.X, t.B); c.scale(t.s, t.s); c.fillStyle = col; SPEC.trio.body(c, ch); c.restore(); }
function kidFace(c, ch, j) { const t = kidTf(ch, j), lk = clamp((S.pip.x - t.X) / 200, -1, 1); c.save(); c.translate(t.X, t.B); c.scale(t.s, t.s); SPEC.trio.face(c, ch, lk, j); c.restore(); }
function drawEyes(c, low) {          // глаза в темноте (low — те, что в траве ниже земли: поверх неё)
  const cam = S.cam;
  for (const e of S.eyes) {
    if ((e.h < 0) !== low || e.vis <= .02 || e.x < cam - 50 || e.x > cam + W + 50) continue;
    const x = e.x, y = ground(e.x) - e.h, s = e.s, lk = clamp((S.pip.x - x) / 300, -1, 1);
    c.save(); c.globalAlpha = e.vis; c.translate(x, y); c.scale(s, s);
    if (e.kind === 'happy') happyEyes(c, -8, 0, 8, 0, 5, 2.6);
    else if (e.kind === 'blink' && Math.sin(e.ph * 1.3) > .2) { c.strokeStyle = '#fff'; c.lineWidth = 2.4; c.beginPath(); c.moveTo(-12, 0); c.lineTo(-4, 0); c.moveTo(4, 0); c.lineTo(12, 0); c.stroke(); }
    else eyes(c, -8, 0, 8, 0, 4.4, 5.6, lk, .1, e.blink < 0 ? .1 : 1);
    c.restore();
  }
}
function fgPass(c) {
  const cam = S.cam;
  c.save(); c.translate(-cam, 0);
  // лица теней, что уже отошли вглубь
  for (const ch of S.chars) {
    if (ch.kind === 'trio') { if (ch.st !== 'wait') for (let j = 0; j < 3; j++) kidFace(c, ch, j); continue; }
    if (ch.st === 'yield' || ch.st === 'aside') drawFace(c, ch);
  }
  drawEyes(c, false);
  decor(c, 'back');
  for (const ch of S.chars) {
    if (ch.kind === 'trio') continue;
    if (ch.st === 'wait' || ch.st === 'flee') { drawBody(c, ch, BLK); drawFace(c, ch); }
  }
  drawPip(c);
  drawGround(c);
  drawEyes(c, true);
  decor(c, 'bridge');
  for (const ch of S.chars) if (ch.kind === 'trio' && ch.st === 'wait') {
    for (let j = 0; j < 3; j++) drawKid(c, ch, j, BLK);
    c.strokeStyle = BLK; c.lineWidth = 6; c.lineCap = 'round'; c.beginPath();
    for (let j = 0; j < 2; j++) { const a = kidTf(ch, j), b = kidTf(ch, j + 1); c.moveTo(a.X + 28, a.B - 34); c.quadraticCurveTo((a.X + b.X) / 2, (a.B + b.B) / 2 - 22 + Math.sin(S.t * 3 + j) * 4, b.X - 28, b.B - 34); }
    c.stroke();
    for (let j = 0; j < 3; j++) kidFace(c, ch, j);
  }
  decor(c, 'front');
  houseLights(c);
  drawLantern(c);
  // светлячки и искры
  for (const f of S.flies) {
    if (f.st !== 'idle' && f.st !== 'go') continue;
    const fl = .75 + .25 * Math.sin(f.ph * 7 + f.x);
    glow(c, f.wx, f.wy, 30, .55 * fl); c.fillStyle = '#ffe2a0'; ell(c, f.wx, f.wy, 2.6, 2.6); c.fill();
  }
  for (const q of S.parts) { const a = q.life / q.max; glow(c, q.x, q.y, q.s * 5, a * .45); c.fillStyle = 'rgba(255,226,160,' + a.toFixed(2) + ')'; ell(c, q.x, q.y, q.s * .6, q.s * .6); c.fill(); }
  c.restore();
}
let GRAIN = null;
function grain(c) {
  if (!GRAIN) { const n = mkc(128, 128), x = n.getContext('2d'), d = x.createImageData(128, 128);
    for (let i = 0; i < d.data.length; i += 4) { const v = Math.random() * 255; d.data[i] = d.data[i + 1] = d.data[i + 2] = v; d.data[i + 3] = 20; }
    x.putImageData(d, 0, 0); GRAIN = c.createPattern(n, 'repeat'); }
  c.save(); c.globalCompositeOperation = 'overlay'; c.fillStyle = GRAIN; c.translate((S.t * 37 % 128) | 0, (S.t * 53 % 128) | 0); c.fillRect(-128, -128, W + 256, H + 256); c.restore();
  c.drawImage(C.vig, 0, 0, W, H);
}
function wrap(c, text, maxW) {
  const out = []; let line = '';
  for (const w of text.split(' ')) { const t = line ? line + ' ' + w : w; if (c.measureText(t).width > maxW && line) { out.push(line); line = w; } else line = t; }
  out.push(line); return out;
}
function txt(c, s, x, y, size, color, o = {}) {
  c.font = (o.w || 600) + ' ' + size + 'px ' + A.FONT; c.textAlign = o.al || 'left'; c.textBaseline = o.bl || 'alphabetic';
  if (o.ls) c.letterSpacing = o.ls + 'px';
  if (o.halo) { c.lineJoin = 'round'; c.lineWidth = o.hw || 6; c.strokeStyle = o.halo; c.strokeText(s, x, y); }
  c.fillStyle = color; c.fillText(s, x, y);
  if (o.ls) c.letterSpacing = '0px';
}
let OV = null;                       // где на свету есть надписи: только там второй раз кладём растр
function rect(x, y, w, h) { if (!OV) return; OV.x0 = Math.min(OV.x0, x); OV.y0 = Math.min(OV.y0, y); OV.x1 = Math.max(OV.x1, x + w); OV.y1 = Math.max(OV.y1, y + h); }
/* надписи поверх мира: lit=false — белые во тьме, lit=true — чёрные на свету (кладутся под тот же растр) */
function overPass(c, lit) {
  const cam = S.cam, ink = lit ? BLK : '#ffffff', soft = lit ? '#4b473f' : '#b9b9bf', halo = lit ? CREAM : null;
  c.save(); c.translate(-cam, 0);
  if (lit) litDetails(c, rect);
  c.globalAlpha = 1; c.restore();
  // заголовок/участок и подсказка — левый верх
  const bx = K.bx;
  if (S.mode === 'title') {
    txt(c, 'КТО БОИТСЯ ТЕМНОТЫ', bx, K.name, K.tName, ink, { w: 800, ls: LAND ? 4 : 3, halo, hw: 6 });
    c.fillStyle = AMB; c.fillRect(bx, K.dash, 30, 3);
    if (A.shot) { c.font = '500 ' + K.hintS + 'px ' + A.FONT; wrap(c, 'Свети фонариком — тени стесняются и уступают дорогу', K.wrap).forEach((l, i) => txt(c, l, bx, K.hint + i * (K.hintS + 8), K.hintS, soft, { w: 500, halo, hw: 6 })); }
    rect(bx - 8, K.name - K.tName, 660, K.tName + 80);
  } else {
    const a = sm(S.chT / .7);
    txt(c, 'ЧАСТЬ ' + (S.ch + 1) + ' ИЗ 5', bx, K.kick, K.kickS, lit ? '#6a655c' : '#8d8d93', { w: 600, ls: 3, halo, hw: 5 });
    c.globalAlpha = a; txt(c, CH[S.ch].n.toUpperCase(), bx + (1 - a) * -14, K.name, K.nameS, ink, { w: 800, ls: LAND ? 4 : 3, halo, hw: 6 }); c.globalAlpha = 1;
    c.fillStyle = AMB; c.fillRect(bx, K.dash, 30 * a, 3);
    c.font = '500 ' + K.hintS + 'px ' + A.FONT;
    const hf = S.hintF;
    const showT = hf < .5 && S.hintPrev ? S.hintPrev : S.hint, ha = hf < .5 && S.hintPrev ? 1 - hf * 2 : clamp((hf - .5) * 2, 0, 1) + (S.hintPrev ? 0 : 1);
    c.globalAlpha = clamp(ha, 0, 1); wrap(c, showT, K.wrap).forEach((l, i) => txt(c, l, bx, K.hint + i * (K.hintS + 8), K.hintS, soft, { w: 500, halo, hw: 6 })); c.globalAlpha = 1;
    rect(bx - 8, K.kick - K.kickS - 6, K.wrap + 20, K.hint - K.kick + K.hintS * 3 + 30);
    // «?»
    if (S.mode === 'play') { const [qx, qy] = K.q, pulse = S.cap ? 1 : .55; c.strokeStyle = lit ? BLK : 'rgba(255,255,255,' + pulse + ')'; c.lineWidth = 2; ell(c, qx, qy, 25, 25); c.stroke();
      txt(c, '?', qx, qy + 1, 26, lit ? BLK : 'rgba(255,255,255,' + (pulse + .3) + ')', { w: 700, al: 'center', bl: 'middle' }); rect(qx - 30, qy - 30, 60, 60); }
    // экранные кнопки (телефон)
    if (S.mode === 'play' && TOUCH && (LAND || !lit)) { pad(c, lit); rect(0, K.pad.l[1] - 70, W, 150); }
  }
  if (!lit && S.mode !== 'title' && S.mode !== 'end') hud(c);
}
/* Реплики — поверх обоих миров, на мягкой пилюле без растрового края: во тьме — ночная, на свету — бумажная.
   Прижаты к полю (16 px), не залезают на заголовок; одновременные не налезают — следующая уходит вверх. */
function speech(c) {
  if (S.mode === 'title' && !A.shot) return;            // на заставке их закрыла бы карточка
  const cam = S.cam, placed = [], top = (LAND ? 176 : 232);
  for (const s of S.says) {
    const a = clamp(Math.min(s.t / .2, (s.life - s.t) / .5), 0, 1); if (a <= 0) continue;
    let x = s.x, y = s.y - eOut(s.t / .5) * 10;
    if (s.follow && s.follow.kind !== 'trio') { const h = headPt(s.follow); x = h[0]; y = h[1] - eOut(s.t / .5) * 10; }
    if (x < cam - 60 || x > cam + W + 60) continue;      // говорящий за краем экрана — не приклеиваем реплику к краю
    const size = s.soft ? K.sp2 : K.speech;
    c.font = '600 ' + size + 'px ' + A.FONT; const w = c.measureText(s.text).width;
    const pw = w + size * 1.1, ph = size * 1.62;
    let sx = clamp(x - cam, 16 + pw / 2, W - 16 - pw / 2), sy = clamp(y - size * .35, top + ph / 2, H - 16 - ph / 2);
    for (let n = 0; n < 8; n++) {
      const hit = placed.find((r) => Math.abs(r.x - sx) < (r.w + pw) / 2 + 6 && Math.abs(r.y - sy) < (r.h + ph) / 2 + 4);
      if (!hit) break; sy = hit.y - (hit.h + ph) / 2 - 6;
    }
    sy = Math.max(sy, 16 + ph / 2);
    placed.push({ x: sx, y: sy, w: pw, h: ph });
    const lit = isLit(sx + cam, sy);
    c.save(); c.globalAlpha = a;
    A.rr(c, sx - pw / 2, sy - ph / 2, pw, ph, ph / 2);
    c.fillStyle = lit ? 'rgba(242,238,229,.93)' : 'rgba(12,12,13,.8)'; c.fill();
    c.strokeStyle = lit ? 'rgba(12,12,13,.12)' : 'rgba(255,255,255,.12)'; c.lineWidth = 1.2; c.stroke();
    txt(c, s.text, sx, sy + 1, size, s.soft ? (lit ? '#57534b' : '#b9b9bf') : (lit ? BLK : '#ffffff'), { al: 'center', bl: 'middle' });
    c.restore();
  }
}
function pad(c, lit) {
  const P = K.pad, ink = lit ? 'rgba(12,12,13,' : 'rgba(255,255,255,';
  let wl = 0, wr = 0, up = 0; for (const q of T.ptrs.values()) { if (q.zone === 'walk') { if (q.x < W / 4) wl = 1; else wr = 1; } if (q.zone === 'up') up = 1; }
  const chev = (x, y, d, on) => { c.strokeStyle = ink + (on ? .95 : .5) + ')'; c.lineWidth = 2; ell(c, x, y, 40, 40); c.stroke(); c.lineWidth = 4; c.lineCap = 'round'; c.lineJoin = 'round';
    c.beginPath(); c.moveTo(x + 6 * d, y - 13); c.lineTo(x - 7 * d, y); c.lineTo(x + 6 * d, y + 13); c.stroke(); if (on) { c.fillStyle = ink + '.12)'; ell(c, x, y, 40, 40); c.fill(); } };
  chev(P.l[0], P.l[1], 1, wl); chev(P.r[0], P.r[1], -1, wr);
  const [ux, uy] = P.up; c.strokeStyle = up ? AMB : ink + '.6)'; c.lineWidth = up ? 3 : 2; ell(c, ux, uy, P.rr, P.rr); c.stroke();
  if (up) { c.fillStyle = 'rgba(255,183,43,.14)'; ell(c, ux, uy, P.rr, P.rr); c.fill(); }
  c.lineWidth = 4; c.strokeStyle = up ? AMB : ink + '.85)'; c.beginPath(); c.moveTo(ux - 12, uy - 4); c.lineTo(ux, uy - 16); c.lineTo(ux + 12, uy - 4); c.stroke();
  txt(c, 'выше', ux, uy + 22, LAND ? 20 : 22, up ? AMB : ink + '.85)', { w: 600, al: 'center', bl: 'middle' });
  if (!LAND) {
    txt(c, 'идти', (P.l[0] + P.r[0]) / 2, P.l[1] + 70, 22, ink + '.55)', { w: 500, al: 'center' });
    txt(c, 'свет —', 448, uy - 6, 22, ink + '.55)', { w: 500, al: 'center' }); txt(c, 'ведите пальцем', 448, uy + 22, 22, ink + '.55)', { w: 500, al: 'center' });
  }
}
function hud(c) {
  const y = K.hudY, x = K.bx, low = S.oil < 20, bl = low ? .55 + .45 * Math.sin(S.t * 8) : 1;
  txt(c, 'МАСЛО В ФОНАРЕ', x, y - 14, 20, '#8d8d93', { w: 600, ls: 2 });
  c.strokeStyle = 'rgba(255,255,255,.85)'; c.lineWidth = 2; c.strokeRect(x, y - 2, K.oilW, 12);
  c.globalAlpha = bl; c.fillStyle = AMB; c.fillRect(x + 3, y + 1, (K.oilW - 6) * S.oil / 100, 6); c.globalAlpha = 1;
  const fx = W - K.bx;
  txt(c, 'СВЕТЛЯЧКИ', fx, y - 14, 20, '#8d8d93', { w: 600, ls: 2, al: 'right' });
  txt(c, S.count + ' / ' + S.total, fx, y + 22, LAND ? 30 : 34, '#ffffff', { w: 800, al: 'right' });
  // путь домой: участки, Пип, окошко
  const [p0, p1] = K.prog, py = LAND ? y + 4 : K.progY, k = clamp(S.pip.x / DOOR, 0, 1);
  c.strokeStyle = 'rgba(255,255,255,.22)'; c.lineWidth = 2; c.beginPath(); c.moveTo(p0, py); c.lineTo(p1, py); c.stroke();
  c.strokeStyle = 'rgba(255,255,255,.7)'; c.beginPath(); c.moveTo(p0, py); c.lineTo(lerp(p0, p1, k), py); c.stroke();
  for (let i = 1; i < CH.length; i++) { const tx = lerp(p0, p1, CH[i].x / DOOR); c.fillStyle = S.pip.x >= CH[i].x ? '#fff' : 'rgba(255,255,255,.35)'; c.fillRect(tx - 1, py - 5, 2, 10); }
  glow(c, p1 + 8, py, 22, .5); c.fillStyle = AMB; c.fillRect(p1 + 2, py - 6, 12, 12); c.fillStyle = BLK; c.fillRect(p1 + 7, py - 6, 2, 12); c.fillRect(p1 + 2, py - 1, 12, 2);
  c.fillStyle = '#fff'; ell(c, lerp(p0, p1, k), py, 6, 6); c.fill();
}
function caption(c) {
  if (!S.cap || S.mode !== 'play') return;
  const k = S.cap, a = clamp(Math.min(k.t / .3, (k.life - k.t) / .6), 0, 1), size = LAND ? 22 : 26;
  c.font = '600 ' + size + 'px ' + A.FONT;
  const lines = [...wrap(c, CTRL, W - 140), ...wrap(c, S.hint, W - 140)];
  const bw = Math.min(W - 60, Math.max(...lines.map((l) => c.measureText(l).width)) + 60), bh = lines.length * (size + 12) + 30, by = K.capY - bh / 2;
  c.save(); c.globalAlpha = a; A.rr(c, (W - bw) / 2, by, bw, bh, 20); c.fillStyle = 'rgba(12,12,13,.86)'; c.fill(); c.strokeStyle = 'rgba(255,183,43,.45)'; c.lineWidth = 1.5; c.stroke();
  lines.forEach((l, i) => txt(c, l, W / 2, by + 15 + size * .5 + 2 + i * (size + 12), size, i === 0 ? '#ffd98a' : '#f4f1ea', { al: 'center', bl: 'middle' }));
  c.restore();
}
function draw(c, g) {
  ensure(g.scale);
  if (!S.lan) computeLight();
  const sc = C.sc, L = S.L;
  bgPass(c, DARK);
  const bb = lightBox();
  if (bb) {
    const gb = Math.min(bb.y + bb.h, GY + DIP + 16) - bb.y, bg = gb > 2 ? { x: bb.x, y: bb.y, w: bb.w, h: gb } : null;
    const m = C.mbx; m.setTransform(sc, 0, 0, sc, 0, 0); m.clearRect(bb.x - 1, bb.y - 1, bb.w + 2, bb.h + 2);
    disc(m, L.lx - S.cam, L.ly, L.lr); disc(m, L.x - S.cam, L.y, L.r);
    const l = C.lbx; l.setTransform(sc, 0, 0, sc, 0, 0); l.clearRect(bb.x - 1, bb.y - 1, bb.w + 2, bb.h + 2);
    if (bg) { l.save(); l.beginPath(); l.rect(bg.x, bg.y, bg.w, bg.h); l.clip(); bgPass(l, LIT); l.restore(); composite(c, bg); }
  }
  fgPass(c);
  grain(c);
  overPass(c, false);
  if (bb) {
    const l = C.lbx; l.setTransform(sc, 0, 0, sc, 0, 0); l.clearRect(bb.x - 1, bb.y - 1, bb.w + 2, bb.h + 2);
    OV = { x0: 1e9, y0: 1e9, x1: -1e9, y1: -1e9 };
    l.save(); l.beginPath(); l.rect(bb.x, bb.y, bb.w, bb.h); l.clip(); overPass(l, true); l.restore();
    const x0 = Math.max(bb.x, Math.floor(OV.x0)), y0 = Math.max(bb.y, Math.floor(OV.y0)), x1 = Math.min(bb.x + bb.w, Math.ceil(OV.x1)), y1 = Math.min(bb.y + bb.h, Math.ceil(OV.y1));
    OV = null;
    if (x1 - x0 > 1 && y1 - y0 > 1) composite(c, { x: x0, y: y0, w: x1 - x0, h: y1 - y0 });
  }
  speech(c);
  caption(c);
  if (S.fade > 0) { c.fillStyle = 'rgba(0,0,0,' + S.fade + ')'; c.fillRect(0, 0, W, H); }
}

/* ---------------- экраны ---------------- */
function titleScreen(g) {
  newState('title'); stage(false); g.setPlaying(false); S.fade = 0;
  g.screen({
    kicker: A.framed ? 'Досуг' : 'Аркада', title: 'Кто боится темноты',
    html: '<p>Малыш Пип идёт домой через ночной лес. Тени тут не страшные, а стеснительные: посветите на них фонарём — покраснеют и уступят дорогу.</p><p>Масло в фонаре берегите — его пополняют светлячки.</p>' + (g.best ? '<p class="record">Рекорд: ' + g.best + '</p>' : ''),
    button: 'В путь', onGo: startPlay
  });
}
function startPlay() { newState('play'); buildWorld(); GAME.setPlaying(true); computeLight(); S.hint = HINTS.walk; }
function finish() {
  const g = GAME; if (S.mode !== 'outro') return; S.mode = 'end'; g.setPlaying(false);
  const score = S.count * 100 + Math.round(S.oil), rec = g.submit(score);
  const s = Math.round(S.time), mm = Math.floor(s / 60), ss = String(s % 60).padStart(2, '0');
  g.screen({
    kicker: 'Окошко светится', title: 'Пип дома',
    html: '<p>Тени машут вслед: «спокойной ночи!»</p><p class="score">' + score + '</p><p>Светлячки: ' + S.count + ' из ' + S.total + ' · время ' + mm + ':' + ss + '</p>' + (rec ? '<p class="record">Новый рекорд!</p>' : '<p>Рекорд: ' + g.best + '</p>'),
    button: 'Ещё раз', onGo: startPlay, alt: { label: A.framed ? 'К играм' : 'В аркаду', onGo: () => A.home('../index.html') }
  });
}

/* ---------------- касания и мышь (несколько пальцев сразу) ---------------- */
function setupPointers(g) {
  const cv = g.canvas;
  const lp = (e) => { const r = cv.getBoundingClientRect(); return { x: (e.clientX - r.left) / r.width * W, y: (e.clientY - r.top) / r.height * H }; };
  cv.addEventListener('pointerdown', (e) => {
    if (!S || S.mode !== 'play' || S.bot) return;
    const q = lp(e);
    if (Math.hypot(q.x - K.q[0], q.y - K.q[1]) < 44) { showCap(); return; }
    if (e.pointerType === 'mouse') { S.mouse = q; S.aimMode = 'mouse'; if (e.button === 0) S.mouseDown = true; return; }
    let zone = q.x < W / 2 ? 'walk' : 'aim';
    if (Math.hypot(q.x - K.pad.up[0], q.y - K.pad.up[1]) < K.pad.rr * 1.3) zone = 'up';
    T.ptrs.set(e.pointerId, { zone, x: q.x, y: q.y });
    if (zone === 'aim') S.aimMode = 'touch';
  });
  cv.addEventListener('pointermove', (e) => {
    if (!S) return; const q = lp(e);
    if (e.pointerType === 'mouse') { S.mouse = q; if (S.mode === 'play' && !S.bot) S.aimMode = 'mouse'; return; }
    const p = T.ptrs.get(e.pointerId); if (!p) return;
    if (p.zone === 'aim') { S.aim.x += (q.x - p.x) * 1.4; S.aim.y += (q.y - p.y) * 1.4; const m = Math.hypot(S.aim.x, S.aim.y); if (m > 260) { S.aim.x *= 260 / m; S.aim.y *= 260 / m; } }
    p.x = q.x; p.y = q.y;
  });
  const up = (e) => { if (!S) return; if (e.pointerType === 'mouse') { S.mouseDown = false; return; } T.ptrs.delete(e.pointerId); };
  cv.addEventListener('pointerup', up); cv.addEventListener('pointercancel', up);
  addEventListener('blur', () => { T.ptrs.clear(); if (S) S.mouseDown = false; });
}

A.game({
  id: 'dark', title: 'Кто боится темноты', width: W, height: H, orientation: LAND ? 'landscape' : 'portrait', tone: 'dark',
  keys: { Slash: 'help', KeyH: 'help' },
  help: { desktop: '<kbd>←</kbd> <kbd>→</kbd> — идти · мышь — куда светить · <kbd>Пробел</kbd> — поднять фонарь', short: '← → — идти · мышь — светить · пробел — фонарь выше', touch: 'Слева — идти · справа — вести свет · «выше» — поднять фонарь' },
  init(g) { GAME = g; setupPointers(g); titleScreen(g); window.__dark = () => S; window.__darkStage = (cover) => { newState('title'); stage(!!cover); S.fade = 0; }; },
  update, draw
});
})();
