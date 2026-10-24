/* Гонка — бесконечная гонка с видом сверху. */
(() => {
'use strict';
const A = Arcade;
/* Широкое окно (лист «Досуг» на компьютере) — своя раскладка 1280×720: дорога посередине во всю высоту (мир прежний,
   книжный, только уменьшен), а лес, пляж и город продолжаются до краёв окна; слева — очки, метры, места и жизни,
   справа — спидометр, рекорд и управление. Узкое окно (телефон) — как было. */
const LAND = (() => { try { return innerWidth > (innerHeight - 110) * 1.15; } catch (e) { return false; } })();
const W = 720, H = 1280;                                   // мир игры — всегда книжный
const SW = LAND ? 1280 : W, SH = LAND ? 720 : H;           // холст
const VH = LAND ? 1200 : H;                                // в широком окне мир виден до этой высоты
const FS = SH / VH, FW = W * FS, FX = (SW - FW) / 2;
const GX0 = LAND ? -FX / FS - 12 : 0, GX1 = LAND ? W + FX / FS + 12 : W;   // земля — до краёв холста
/* боковые колонки — у краёв: карточка меню в листе «Досуг» (~770 px) закрывает x ≈ 250…1030, y ≈ 175…550 */
const PW = 218, LCX = 26 + PW / 2, RCX = SW - 26 - PW / 2;
const OUT = '#2b2550';
const ROAD_L = 150, ROAD_R = 570, LANE_W = 140;
const LANES = [220, 360, 500];
const PY = H - 270;                 // где едет игрок
const SEG_H = 320;
const PX_PER_M = 14;
const ZONES = ['forest', 'seaside', 'city'];
const ZONE_NAME = { forest: 'Лес', seaside: 'Побережье', city: 'Город' };
let S = null;

/* ---------------- окружение ---------------- */
let bridgeRun = 0;
function zoneAt(m) { return ZONES[Math.floor(m / 1000) % ZONES.length]; }
function makeSegment(y, meters) {
  const zone = zoneAt(meters);
  const seg = { y, zone, kind: 'normal', items: [], ph: Math.random() * 6 };
  if (zone === 'seaside') {
    if (bridgeRun > 0) { seg.kind = 'bridge'; bridgeRun--; }
    else if (Math.random() < .18) { seg.kind = 'bridge'; bridgeRun = A.randInt(2, 3); }
  } else bridgeRun = 0;
  const it = seg.items, R = A.rand, side = () => (Math.random() < .5 ? R(18, 128) : R(592, 702));
  if (zone === 'forest') {
    for (let i = 0; i < 6; i++) it.push({ t: 'flower', x: side(), y: R(10, 310), c: A.pick(['#ff77c6', '#ffd43b', '#ffffff', '#b39dff', '#ff8a5c']) });
    for (let i = 0; i < 2; i++) it.push({ t: 'bush', x: side(), y: R(20, 300), r: R(14, 20) });
    for (let i = 0; i < A.randInt(2, 4); i++) { const left = Math.random() < .5; it.push({ t: 'tree', x: left ? R(20, 105) : R(615, 700), y: R(30, 290), r: R(34, 50), c: A.pick(['#3fbf5f', '#4fcf6a', '#2fae5a', '#66d36e']) }); }
    if (Math.random() < .35) it.push({ t: 'fence', x: Math.random() < .5 ? 132 : 588 });
  } else if (zone === 'seaside') {
    if (seg.kind === 'bridge') {
      if (Math.random() < .6) it.push({ t: 'boat', x: Math.random() < .5 ? R(40, 100) : R(620, 680), y: R(60, 260), c: A.pick(['#ff6b6b', '#4f8bff', '#ffd43b']) });
    } else {
      for (let i = 0; i < A.randInt(1, 2); i++) it.push({ t: 'umbrella', x: R(30, 115), y: R(30, 290), c: A.pick(['#ff6b8b', '#4f8bff', '#ffb347', '#4fe0c0']) });
      if (Math.random() < .8) it.push({ t: 'palm', x: R(25, 110), y: R(40, 280), r: R(40, 52) });
      if (Math.random() < .45) it.push({ t: 'boat', x: R(640, 690), y: R(40, 280), c: A.pick(['#ff6b6b', '#4f8bff', '#ffd43b']) });
      if (Math.random() < .5) it.push({ t: 'buoy', x: R(625, 700), y: R(20, 300) });
    }
  } else {
    it.push({ t: 'house', x: 6, y: R(20, 60), w: 82, h: R(130, 220), c: A.pick(['#ff8a6b', '#7c8cff', '#ffc857', '#62d2a2', '#ff9ccf']) });
    it.push({ t: 'house', x: 632, y: R(20, 60), w: 82, h: R(130, 220), c: A.pick(['#ff8a6b', '#7c8cff', '#ffc857', '#62d2a2', '#ff9ccf']) });
    it.push({ t: 'lamp', x: 132, y: 40 }); it.push({ t: 'lamp', x: 588, y: 200 });
    if (Math.random() < .6) it.push({ t: 'potTree', x: Math.random() < .5 ? 112 : 608, y: R(120, 280) });
  }
  if (LAND) sideDecor(seg);
  return seg;
}
/* широкое окно: окрестности по сторонам от дороги (за краями книжного мира) */
function sideDecor(seg) {
  const it = seg.items, R = A.rand, L = () => R(GX0 + 30, -30), Rt = () => R(W + 30, GX1 - 30), any = () => (Math.random() < .5 ? L() : Rt());
  if (seg.zone === 'forest') {
    for (let i = 0; i < 16; i++) it.push({ t: 'flower', x: any(), y: R(10, 310), c: A.pick(['#ff77c6', '#ffd43b', '#ffffff', '#b39dff', '#ff8a5c']) });
    for (let i = 0; i < 4; i++) it.push({ t: 'bush', x: any(), y: R(20, 300), r: R(14, 22) });
    for (let i = 0; i < 9; i++) it.push({ t: 'tree', x: any(), y: R(20, 300), r: R(34, 54), c: A.pick(['#3fbf5f', '#4fcf6a', '#2fae5a', '#66d36e']) });
  } else if (seg.zone === 'seaside') {
    if (seg.kind === 'bridge') { for (let i = 0; i < 3; i++) it.push({ t: 'boat', x: any(), y: R(40, 280), c: A.pick(['#ff6b6b', '#4f8bff', '#ffd43b']) }); }
    else {
      for (let i = 0; i < 4; i++) it.push({ t: 'umbrella', x: L(), y: R(30, 290), c: A.pick(['#ff6b8b', '#4f8bff', '#ffb347', '#4fe0c0']) });
      for (let i = 0; i < 3; i++) it.push({ t: 'palm', x: L(), y: R(30, 290), r: R(40, 54) });
      for (let i = 0; i < 2; i++) it.push({ t: 'boat', x: Rt(), y: R(40, 280), c: A.pick(['#ff6b6b', '#4f8bff', '#ffd43b']) });
      for (let i = 0; i < 2; i++) it.push({ t: 'buoy', x: Rt(), y: R(20, 300) });
    }
  } else {
    for (let k = 0; k < 5; k++) {                         // кварталы: домики с просветами, между ними — деревца в кадках
      for (const side of [-1, 1]) {
        const x0 = side < 0 ? -44 - k * 156 : W + 44 + k * 156;
        if (Math.random() < .28) { it.push({ t: 'potTree', x: x0 + side * 50, y: R(50, 270) }); continue; }
        const w = R(92, 122);
        it.push({ t: 'house', x: side < 0 ? x0 - w : x0, y: R(12, 80), w, h: R(120, 200), c: A.pick(['#ff8a6b', '#7c8cff', '#ffc857', '#62d2a2', '#ff9ccf']) });
        if (Math.random() < .4) it.push({ t: 'potTree', x: x0 + side * w * .5, y: 296 });
      }
    }
  }
}
function drawGround(ctx, seg, t) {
  const y = seg.y;
  if (seg.zone === 'forest') {
    for (let i = 0; i < 4; i++) { ctx.fillStyle = i % 2 ? '#7ed957' : '#74cf4e'; ctx.fillRect(GX0, y + i * 80, GX1 - GX0, 81); }
  } else if (seg.zone === 'seaside') {
    if (seg.kind === 'bridge') drawWater(ctx, GX0, y, GX1 - GX0, SEG_H + 1, t, seg.ph);
    else {
      ctx.fillStyle = '#f7dc9a'; ctx.fillRect(GX0, y, ROAD_L - GX0, SEG_H + 1);
      ctx.fillStyle = '#f7dc9a'; ctx.fillRect(ROAD_R, y, 40, SEG_H + 1);
      drawWater(ctx, ROAD_R + 40, y, GX1 - ROAD_R - 40, SEG_H + 1, t, seg.ph);
      ctx.fillStyle = 'rgba(255,255,255,.75)';
      for (let k = 0; k < 4; k++) { const yy = y + k * 80 + 30 + Math.sin(t * 2 + k) * 6; ctx.beginPath(); ctx.ellipse(ROAD_R + 42, yy, 6, 26, 0, 0, Math.PI * 2); ctx.fill(); }
    }
  } else {
    ctx.fillStyle = '#b9e88f'; ctx.fillRect(GX0, y, GX1 - GX0, SEG_H + 1);
    ctx.fillStyle = '#dfe3ec'; ctx.fillRect(96, y, ROAD_L - 96, SEG_H + 1); ctx.fillRect(ROAD_R, y, 624 - ROAD_R, SEG_H + 1);
    ctx.strokeStyle = '#c4c9d6'; ctx.lineWidth = 2;
    for (let k = 0; k < 8; k++) { const yy = y + k * 40; ctx.beginPath(); ctx.moveTo(96, yy); ctx.lineTo(ROAD_L, yy); ctx.moveTo(ROAD_R, yy); ctx.lineTo(624, yy); ctx.stroke(); }
  }
}
function drawWater(ctx, x, y, w, h, t, ph) {
  ctx.fillStyle = '#4fc3f7'; ctx.fillRect(x, y, w, h);
  ctx.strokeStyle = 'rgba(255,255,255,.55)'; ctx.lineWidth = 3; ctx.lineCap = 'round';
  for (let k = 0, n = 6 * Math.max(1, Math.round(w / 700)); k < n; k++) {   // в широком окне вода шире — и волн больше
    const yy = y + 25 + (k % 6) * 55, xx = x + ((k * 53 + ph * 40) % Math.max(40, w - 40)) + Math.sin(t * 1.5 + k + ph) * 6;
    ctx.beginPath(); ctx.arc(xx, yy, 10, Math.PI * 1.1, Math.PI * 1.9); ctx.arc(xx + 18, yy, 10, Math.PI * 1.1, Math.PI * 1.9); ctx.stroke();
  }
}
function drawRoad(ctx, scroll, segs) {
  ctx.fillStyle = '#6b7086'; ctx.fillRect(ROAD_L, 0, ROAD_R - ROAD_L, H);
  ctx.fillStyle = 'rgba(255,255,255,.05)'; ctx.fillRect(ROAD_L + 20, 0, 40, H);
  // бордюр
  const off = scroll % 60;
  for (let y = -60 + off; y < H; y += 60) {
    for (const x of [ROAD_L - 12, ROAD_R]) {
      ctx.fillStyle = '#ff5a5a'; ctx.fillRect(x, y, 12, 30);
      ctx.fillStyle = '#ffffff'; ctx.fillRect(x, y + 30, 12, 30);
    }
  }
  // мосты: перила
  for (const s of segs) if (s.kind === 'bridge') {
    for (const x of [ROAD_L - 22, ROAD_R + 12]) {
      ctx.fillStyle = '#a7aec4'; ctx.fillRect(x, s.y, 10, SEG_H + 1);
      ctx.fillStyle = '#7d849e'; for (let k = 0; k < SEG_H; k += 40) ctx.fillRect(x - 2, s.y + k, 14, 8);
    }
  }
  // разметка
  const doff = scroll % 100;
  ctx.fillStyle = 'rgba(255,255,255,.9)';
  for (const lx of [ROAD_L + LANE_W, ROAD_L + LANE_W * 2]) for (let y = -100 + doff; y < H; y += 100) { A.rr(ctx, lx - 4, y, 8, 50, 4); ctx.fill(); }
  ctx.fillStyle = 'rgba(255,255,255,.75)'; ctx.fillRect(ROAD_L + 6, 0, 5, H); ctx.fillRect(ROAD_R - 11, 0, 5, H);
}
function drawDecor(ctx, seg, d, t) {
  const x = d.x, y = seg.y + d.y;
  ctx.lineJoin = 'round'; ctx.strokeStyle = OUT;
  switch (d.t) {
    case 'flower':
      ctx.fillStyle = d.c;
      for (let k = 0; k < 5; k++) { const a = k * 1.2566; ctx.beginPath(); ctx.arc(x + Math.cos(a) * 5, y + Math.sin(a) * 5, 4.2, 0, Math.PI * 2); ctx.fill(); }
      ctx.fillStyle = '#ffcc33'; ctx.beginPath(); ctx.arc(x, y, 3.4, 0, Math.PI * 2); ctx.fill();
      break;
    case 'bush':
      ctx.fillStyle = 'rgba(20,80,30,.22)'; ctx.beginPath(); ctx.ellipse(x + 6, y + 8, d.r * 1.6, d.r, 0, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = '#3bb05a'; ctx.lineWidth = 3;
      ctx.beginPath(); ctx.arc(x - d.r * .6, y, d.r, 0, Math.PI * 2); ctx.arc(x + d.r * .6, y, d.r, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
      ctx.fillStyle = '#58c975'; ctx.beginPath(); ctx.arc(x, y - d.r * .4, d.r * .9, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
      break;
    case 'tree': {
      ctx.fillStyle = 'rgba(20,80,30,.25)'; ctx.beginPath(); ctx.arc(x + 12, y + 14, d.r, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = d.c; ctx.lineWidth = 3.5; ctx.beginPath(); ctx.arc(x, y, d.r, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
      ctx.fillStyle = 'rgba(255,255,255,.22)';
      ctx.beginPath(); ctx.arc(x - d.r * .3, y - d.r * .3, d.r * .45, 0, Math.PI * 2); ctx.fill();
      ctx.beginPath(); ctx.arc(x + d.r * .35, y + d.r * .1, d.r * .25, 0, Math.PI * 2); ctx.fill();
      break;
    }
    case 'fence':
      ctx.fillStyle = '#c98a4f';
      ctx.fillRect(x - 2, seg.y, 4, SEG_H + 1);
      for (let k = 0; k < SEG_H; k += 32) { ctx.fillStyle = '#a86a35'; A.rr(ctx, x - 6, seg.y + k, 12, 12, 3); ctx.fill(); }
      break;
    case 'palm': {
      ctx.fillStyle = 'rgba(120,80,20,.2)'; ctx.beginPath(); ctx.arc(x + 14, y + 16, d.r * .8, 0, Math.PI * 2); ctx.fill();
      ctx.lineWidth = 3;
      for (let k = 0; k < 6; k++) {
        const a = k * Math.PI / 3 + .3 + Math.sin(t * 1.3 + x) * .05;
        ctx.save(); ctx.translate(x, y); ctx.rotate(a);
        ctx.beginPath(); ctx.ellipse(d.r * .5, 0, d.r * .55, 11, 0, 0, Math.PI * 2); ctx.fillStyle = k % 2 ? '#3fbf5f' : '#55d06f'; ctx.fill(); ctx.stroke();
        ctx.strokeStyle = 'rgba(30,90,40,.6)'; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(4, 0); ctx.lineTo(d.r * .95, 0); ctx.stroke();
        ctx.restore(); ctx.strokeStyle = OUT; ctx.lineWidth = 3;
      }
      ctx.fillStyle = '#8b5a2b'; ctx.beginPath(); ctx.arc(x, y, 9, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
      break;
    }
    case 'umbrella': {
      ctx.fillStyle = '#ffffff'; A.rr(ctx, x + 18, y + 10, 26, 46, 5); ctx.fill(); ctx.lineWidth = 2.5; ctx.stroke();
      ctx.fillStyle = d.c; ctx.fillRect(x + 18, y + 22, 26, 8); ctx.fillRect(x + 18, y + 38, 26, 8);
      ctx.fillStyle = 'rgba(120,80,20,.18)'; ctx.beginPath(); ctx.arc(x + 8, y + 10, 30, 0, Math.PI * 2); ctx.fill();
      for (let k = 0; k < 8; k++) {
        ctx.beginPath(); ctx.moveTo(x, y); ctx.arc(x, y, 30, k * Math.PI / 4, (k + 1) * Math.PI / 4); ctx.closePath();
        ctx.fillStyle = k % 2 ? '#ffffff' : d.c; ctx.fill();
      }
      ctx.lineWidth = 3; ctx.beginPath(); ctx.arc(x, y, 30, 0, Math.PI * 2); ctx.stroke();
      ctx.fillStyle = OUT; ctx.beginPath(); ctx.arc(x, y, 4, 0, Math.PI * 2); ctx.fill();
      break;
    }
    case 'boat': {
      const bob = Math.sin(t * 2 + x) * 3;
      ctx.save(); ctx.translate(x, y + bob);
      ctx.fillStyle = 'rgba(255,255,255,.5)'; ctx.beginPath(); ctx.ellipse(0, 36, 10, 16, 0, 0, Math.PI * 2); ctx.fill();
      ctx.beginPath(); ctx.moveTo(0, -36); ctx.quadraticCurveTo(22, -6, 16, 30); ctx.lineTo(-16, 30); ctx.quadraticCurveTo(-22, -6, 0, -36); ctx.closePath();
      ctx.fillStyle = '#ffffff'; ctx.fill(); ctx.lineWidth = 3; ctx.stroke();
      ctx.beginPath(); ctx.moveTo(0, -22); ctx.lineTo(14, 14); ctx.lineTo(0, 14); ctx.closePath(); ctx.fillStyle = d.c; ctx.fill(); ctx.stroke();
      ctx.restore();
      break;
    }
    case 'buoy':
      ctx.fillStyle = '#ff5a5a'; ctx.lineWidth = 3; ctx.beginPath(); ctx.arc(x, y + Math.sin(t * 2.4 + x) * 2, 10, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
      ctx.fillStyle = '#fff'; ctx.fillRect(x - 10, y - 2 + Math.sin(t * 2.4 + x) * 2, 20, 4);
      break;
    case 'house': {
      const w = d.w, h = d.h;
      ctx.fillStyle = 'rgba(30,30,60,.2)'; A.rr(ctx, x + 8, y + 10, w, h, 8); ctx.fill();
      A.rr(ctx, x, y, w, h, 8); ctx.fillStyle = d.c; ctx.fill(); ctx.lineWidth = 3.5; ctx.stroke();
      ctx.save(); A.rr(ctx, x, y, w, h, 8); ctx.clip();
      ctx.fillStyle = 'rgba(0,0,0,.14)'; ctx.fillRect(x + w / 2, y, w / 2, h);
      ctx.fillStyle = 'rgba(255,255,255,.18)'; for (let k = 10; k < h; k += 18) ctx.fillRect(x, y + k, w, 3);
      ctx.restore();
      ctx.beginPath(); ctx.moveTo(x + w / 2, y + 4); ctx.lineTo(x + w / 2, y + h - 4); ctx.stroke();
      ctx.fillStyle = '#8d6e63'; A.rr(ctx, x + w * .62, y + h * .2, 14, 14, 3); ctx.fill(); ctx.lineWidth = 2.5; ctx.stroke();
      break;
    }
    case 'lamp':
      ctx.fillStyle = 'rgba(255,240,150,.35)'; ctx.beginPath(); ctx.arc(x, y, 18, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = '#ffe680'; ctx.lineWidth = 3; ctx.beginPath(); ctx.arc(x, y, 8, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
      break;
    case 'potTree':
      ctx.fillStyle = '#c98a4f'; A.rr(ctx, x - 16, y - 16, 32, 32, 6); ctx.fill(); ctx.lineWidth = 3; ctx.stroke();
      ctx.fillStyle = '#4fcf6a'; ctx.beginPath(); ctx.arc(x, y, 18, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
      ctx.fillStyle = 'rgba(255,255,255,.25)'; ctx.beginPath(); ctx.arc(x - 5, y - 6, 7, 0, Math.PI * 2); ctx.fill();
      break;
    default: break;
  }
}

/* ---------------- машины ---------------- */
const COLORS = [['#4f8bff', '#8fb6ff', '#2f64d6'], ['#ffd43b', '#ffe68a', '#e0a800'], ['#5fd17f', '#a4f0b8', '#2f9c55'], ['#ff77c6', '#ffb3e0', '#d0469a'], ['#a78bfa', '#d3c4ff', '#7a5ad6'], ['#ff9f43', '#ffc58f', '#d97414'], ['#5ee0e6', '#b0f6f8', '#1fa8b0']];
const TYPES = {
  car: { w: 60, h: 104, sp: [300, 420] },
  van: { w: 66, h: 128, sp: [270, 340] },
  bus: { w: 72, h: 180, sp: [230, 280] },
  truck: { w: 72, h: 196, sp: [240, 300] },
  tractor: { w: 66, h: 96, sp: [140, 170] }
};
function newVehicle(lane, y) {
  const r = Math.random();
  const type = r < .5 ? 'car' : r < .66 ? 'van' : r < .78 ? 'bus' : r < .9 ? 'truck' : 'tractor';
  const T = TYPES[type];
  const col = type === 'tractor' ? ['#5fd17f', '#a4f0b8', '#2f9c55'] : type === 'bus' ? A.pick([COLORS[1], COLORS[0], COLORS[5]]) : A.pick(COLORS);
  return { type, x: LANES[lane], y, w: T.w, h: T.h, speed: A.rand(T.sp[0], T.sp[1]), col, lane, change: null, wantsChange: (type === 'car' || type === 'van') && Math.random() < .4, blink: 0, rot: 0, knock: null, passed: false };
}
function wheels(ctx, w, h, list) {
  ctx.fillStyle = '#2b2550';
  for (const [wx, wy, ww, wh] of list) { A.rr(ctx, wx, wy, ww, wh, 4); ctx.fill(); }
  void w; void h;
}
function bodyGrad(ctx, w, c) {
  const gr = ctx.createLinearGradient(-w / 2, 0, w / 2, 0);
  gr.addColorStop(0, c[1]); gr.addColorStop(.45, c[0]); gr.addColorStop(1, c[2]);
  return gr;
}
function glass(ctx, x, y, w, h, r) {
  const gr = ctx.createLinearGradient(0, y, 0, y + h);
  gr.addColorStop(0, '#8fd8ff'); gr.addColorStop(1, '#3b5aa8');
  A.rr(ctx, x, y, w, h, r); ctx.fillStyle = gr; ctx.fill(); ctx.lineWidth = 3; ctx.stroke();
  ctx.fillStyle = 'rgba(255,255,255,.55)'; A.rr(ctx, x + 4, y + 3, Math.max(4, w * .28), Math.max(3, h - 6), 3); ctx.fill();
}
function drawVehicle(ctx, v, t, o = {}) {
  const w = v.w, h = v.h;
  ctx.save(); ctx.translate(v.x, v.y); ctx.rotate(v.rot || 0);
  if (o.alpha != null) ctx.globalAlpha = o.alpha;
  ctx.lineJoin = 'round'; ctx.strokeStyle = OUT;
  // тень
  ctx.fillStyle = 'rgba(20,20,50,.22)'; A.rr(ctx, -w / 2 + 7, -h / 2 + 10, w, h, 18); ctx.fill();
  if (v.type === 'tractor') {
    wheels(ctx, w, h, [[-w / 2 - 10, 4, 18, 40], [w / 2 - 8, 4, 18, 40], [-w / 2 - 2, -h / 2 + 8, 10, 22], [w / 2 - 8, -h / 2 + 8, 10, 22]]);
    A.rr(ctx, -w / 2 + 8, -h / 2, w - 16, h * .55, 12); ctx.fillStyle = bodyGrad(ctx, w, v.col); ctx.fill(); ctx.lineWidth = 4; ctx.stroke();
    ctx.fillStyle = 'rgba(0,0,0,.18)'; for (let k = 0; k < 4; k++) ctx.fillRect(-12, -h / 2 + 10 + k * 10, 24, 4);
    A.rr(ctx, -w / 2 + 4, -h * .02, w - 8, h * .5, 10); ctx.fillStyle = '#ffd43b'; ctx.fill(); ctx.stroke();
    glass(ctx, -w / 2 + 12, h * .04, w - 24, h * .3, 8);
    ctx.fillStyle = '#555'; ctx.beginPath(); ctx.arc(14, -h / 2 + 14, 5, 0, Math.PI * 2); ctx.fill();
    if (Math.floor(t * 6) % 2) { ctx.fillStyle = 'rgba(80,80,80,.35)'; ctx.beginPath(); ctx.arc(16, -h / 2 + 2, 6, 0, Math.PI * 2); ctx.fill(); }
    ctx.restore(); return;
  }
  // колёса
  const wy1 = -h / 2 + Math.min(18, h * .14), wy2 = h / 2 - Math.min(18, h * .14) - 24;
  wheels(ctx, w, h, [[-w / 2 - 5, wy1, 10, 24], [w / 2 - 5, wy1, 10, 24], [-w / 2 - 5, wy2, 10, 24], [w / 2 - 5, wy2, 10, 24]]);
  if (v.type === 'truck') wheels(ctx, w, h, [[-w / 2 - 5, wy2 - 34, 10, 24], [w / 2 - 5, wy2 - 34, 10, 24]]);
  if (v.type === 'truck') {
    const cab = 58;
    A.rr(ctx, -w / 2 + 2, -h / 2, w - 4, cab, 14); ctx.fillStyle = bodyGrad(ctx, w, v.col); ctx.fill(); ctx.lineWidth = 4; ctx.stroke();
    glass(ctx, -w / 2 + 10, -h / 2 + 10, w - 20, 18, 6);
    A.rr(ctx, -w / 2, -h / 2 + cab + 4, w, h - cab - 4, 8); ctx.fillStyle = '#f4f2ff'; ctx.fill(); ctx.stroke();
    ctx.fillStyle = v.col[0]; ctx.fillRect(-w / 2 + 4, -h / 2 + cab + 30, w - 8, 12);
    ctx.fillStyle = 'rgba(0,0,0,.07)'; for (let k = -h / 2 + cab + 14; k < h / 2 - 8; k += 22) ctx.fillRect(-w / 2 + 4, k, w - 8, 3);
  } else if (v.type === 'bus') {
    A.rr(ctx, -w / 2, -h / 2, w, h, 16); ctx.fillStyle = bodyGrad(ctx, w, v.col); ctx.fill(); ctx.lineWidth = 4; ctx.stroke();
    glass(ctx, -w / 2 + 8, -h / 2 + 8, w - 16, 20, 7);
    ctx.fillStyle = 'rgba(255,255,255,.55)'; A.rr(ctx, -w / 2 + 12, -h / 2 + 38, w - 24, h - 56, 10); ctx.fill();
    ctx.fillStyle = 'rgba(43,37,80,.35)'; A.rr(ctx, -14, -10, 28, 34, 5); ctx.fill(); A.rr(ctx, -14, 40, 28, 24, 5); ctx.fill();
  } else {
    const r = v.type === 'van' ? 16 : 22;
    A.rr(ctx, -w / 2, -h / 2, w, h, r); ctx.fillStyle = bodyGrad(ctx, w, v.col); ctx.fill(); ctx.lineWidth = 4; ctx.stroke();
    ctx.fillStyle = 'rgba(255,255,255,.3)'; A.rr(ctx, -w / 2 + 8, -h / 2 + 6, w - 16, h * .14, 8); ctx.fill();
    if (o.stripes) { ctx.fillStyle = 'rgba(255,255,255,.9)'; ctx.fillRect(-9, -h / 2 + 3, 6, h - 6); ctx.fillRect(3, -h / 2 + 3, 6, h - 6); }
    glass(ctx, -w / 2 + 8, -h * .2, w - 16, h * .19, 9);
    A.rr(ctx, -w / 2 + 9, h * .0, w - 18, v.type === 'van' ? h * .34 : h * .22, 9); ctx.fillStyle = o.stripes ? v.col[0] : v.col[1]; ctx.fill(); ctx.lineWidth = 3; ctx.stroke();
    if (o.stripes) { ctx.fillStyle = 'rgba(255,255,255,.9)'; ctx.fillRect(-9, 2, 6, h * .22 - 4); ctx.fillRect(3, 2, 6, h * .22 - 4); }
    glass(ctx, -w / 2 + 10, v.type === 'van' ? h * .36 : h * .26, w - 20, h * .1, 6);
    if (o.spoiler) { A.rr(ctx, -w / 2 - 4, h / 2 - 12, w + 8, 12, 5); ctx.fillStyle = v.col[2]; ctx.fill(); ctx.lineWidth = 3; ctx.stroke(); }
  }
  // фары
  ctx.fillStyle = '#fff3a8';
  ctx.beginPath(); ctx.ellipse(-w / 2 + 12, -h / 2 + 5, 7, 4, 0, 0, Math.PI * 2); ctx.ellipse(w / 2 - 12, -h / 2 + 5, 7, 4, 0, 0, Math.PI * 2); ctx.fill();
  if (o.lights) { ctx.fillStyle = 'rgba(255,245,170,.25)'; ctx.beginPath(); ctx.moveTo(-w / 2 + 6, -h / 2); ctx.lineTo(-w / 2 - 14, -h / 2 - 90); ctx.lineTo(w / 2 + 14, -h / 2 - 90); ctx.lineTo(w / 2 - 6, -h / 2); ctx.fill(); }
  ctx.fillStyle = '#ff4f5e';
  A.rr(ctx, -w / 2 + 5, h / 2 - 7, 14, 6, 3); ctx.fill(); A.rr(ctx, w / 2 - 19, h / 2 - 7, 14, 6, 3); ctx.fill();
  // поворотники
  if (v.blink && Math.floor(t * 5) % 2 === 0) {
    const sx = v.blink > 0 ? w / 2 : -w / 2;
    ctx.fillStyle = '#ffb000';
    for (const yy of [-h / 2 + 10, h / 2 - 10]) { ctx.beginPath(); ctx.arc(sx, yy, 7, 0, Math.PI * 2); ctx.fill(); }
    ctx.fillStyle = 'rgba(255,176,0,.35)';
    for (const yy of [-h / 2 + 10, h / 2 - 10]) { ctx.beginPath(); ctx.arc(sx, yy, 14, 0, Math.PI * 2); ctx.fill(); }
  }
  ctx.restore();
}
const PLAYER_COL = ['#ff4d4d', '#ff9a8a', '#d12f3a'];

/* ---------------- предметы ---------------- */
function drawItem(ctx, it, t) {
  ctx.save(); ctx.translate(it.x, it.y);
  ctx.lineJoin = 'round'; ctx.strokeStyle = OUT; ctx.lineWidth = 3.5;
  const pulse = 1 + Math.sin(t * 6 + it.ph) * .07;
  ctx.fillStyle = 'rgba(20,20,50,.18)'; ctx.beginPath(); ctx.ellipse(6, 10, 18, 8, 0, 0, Math.PI * 2); ctx.fill();
  if (it.kind === 'coin') {
    ctx.scale(Math.max(.15, Math.abs(Math.cos(t * 4 + it.ph))), 1);
    ctx.beginPath(); ctx.arc(0, 0, 18, 0, Math.PI * 2); ctx.fillStyle = '#ffc93c'; ctx.fill(); ctx.stroke();
    ctx.beginPath(); ctx.arc(0, 0, 11, 0, Math.PI * 2); ctx.strokeStyle = '#e69b00'; ctx.lineWidth = 3; ctx.stroke();
    ctx.fillStyle = '#fff6c8'; ctx.beginPath(); ctx.ellipse(-5, -6, 3, 5, .4, 0, Math.PI * 2); ctx.fill();
  } else if (it.kind === 'nitro') {
    ctx.scale(pulse, pulse);
    ctx.globalAlpha = .35; ctx.beginPath(); ctx.arc(0, 0, 36, 0, Math.PI * 2); ctx.fillStyle = '#7ad8ff'; ctx.fill(); ctx.globalAlpha = 1;
    A.rr(ctx, -15, -26, 30, 52, 12); const gr = ctx.createLinearGradient(-15, 0, 15, 0); gr.addColorStop(0, '#7ad8ff'); gr.addColorStop(1, '#2f7de0'); ctx.fillStyle = gr; ctx.fill(); ctx.stroke();
    A.rr(ctx, -7, -34, 14, 10, 3); ctx.fillStyle = '#c9d3ea'; ctx.fill(); ctx.stroke();
    ctx.fillStyle = '#ffd43b'; ctx.beginPath(); ctx.moveTo(3, -16); ctx.lineTo(-8, 3); ctx.lineTo(0, 3); ctx.lineTo(-4, 18); ctx.lineTo(8, -2); ctx.lineTo(0, -2); ctx.closePath(); ctx.fill(); ctx.lineWidth = 2; ctx.stroke();
  } else if (it.kind === 'shield') {
    ctx.scale(pulse, pulse);
    ctx.beginPath(); ctx.arc(0, 0, 24, 0, Math.PI * 2); ctx.fillStyle = 'rgba(95,211,255,.45)'; ctx.fill(); ctx.strokeStyle = '#3bb8ff'; ctx.lineWidth = 4; ctx.stroke();
    ctx.beginPath(); ctx.moveTo(0, -12); ctx.lineTo(11, -6); ctx.lineTo(9, 7); ctx.lineTo(0, 13); ctx.lineTo(-9, 7); ctx.lineTo(-11, -6); ctx.closePath(); ctx.fillStyle = '#fff'; ctx.fill();
  }
  ctx.restore();
}

/* ---------------- состояние ---------------- */
function fresh() {
  const segs = [];
  for (let y = H - SEG_H + 40; y > -SEG_H * 2; y -= SEG_H) segs.push(makeSegment(y, 0));
  return {
    mode: 'title', dist: 0, speed: 560, score: 0, shown: 0, bonus: 0, lives: 3, inv: 0, nitro: 0, shield: false,
    p: { x: LANES[1], vx: 0, tilt: 0, aiLane: 1, puffT: 0, offroad: false },
    segs, cars: [], items: [], lines: [], nextCar: 300, nextCoins: 900, nextNitro: 3000, nextShield: 5200, zoneIdx: 0, banner: null, deadT: 0, coins: 0
  };
}
const meters = () => Math.floor(S.dist / PX_PER_M);
function banner(text, sub) { S.banner = { text, sub, t: 0 }; }

function startGame(g) {
  S = fresh(); S.mode = 'play';
  g.fx.clear(); g.setPlaying(true); g.playMusic();
  banner('Старт!', ZONE_NAME.forest);
}
function titleScreen(g) {
  S.mode = 'title'; g.setPlaying(false);
  g.screen({
    kicker: Arcade.framed ? 'Досуг' : 'Аркада', title: 'Гонка',
    html: `<p>Объезжайте машины, собирайте монетки и баллоны нитро. Проскочили впритирку — получите бонус.</p>${g.best ? `<p class="record">Рекорд: ${g.best.toLocaleString('ru-RU')}</p>` : ''}`,
    button: 'Поехали', onGo: () => startGame(g)
  });
}
function gameOver(g) {
  S.mode = 'over'; g.setPlaying(false); g.stopMusic(); g.sfx('lose');
  const rec = g.submit(S.score);
  g.screen({
    kicker: 'Финиш', title: 'Приехали!',
    html: `<div class="score">${S.score.toLocaleString('ru-RU')}</div><p>${rec ? '<span class="record">Новый рекорд!</span>' : `Рекорд: ${g.best.toLocaleString('ru-RU')}`} · ${meters().toLocaleString('ru-RU')} м</p>`,
    button: 'Ещё раз', onGo: () => startGame(g),
    alt: { label: Arcade.framed ? 'К играм' : 'В аркаду', onGo: () => Arcade.home('../index.html') }
  });
}

/* ---------------- спавн ---------------- */
function laneOf(v) { return A.clamp(Math.round((v.x - LANES[0]) / LANE_W), 0, 2); }
function lanesNear(y, span) {
  const set = new Set();
  for (const c of S.cars) {
    if (c.knock) continue;
    if (Math.abs(c.y - y) < span + c.h / 2) { set.add(laneOf(c)); if (c.change) set.add(c.change.to); }
  }
  return set;
}
function spawnCar() {
  const y = -140;
  const order = [0, 1, 2].sort(() => Math.random() - .5);
  for (const lane of order) {
    const near = lanesNear(y, 330);
    if (near.has(lane)) continue;
    near.add(lane);
    if (near.size >= 3) continue;
    const v = newVehicle(lane, y);
    v.y = -v.h / 2 - 20;
    S.cars.push(v);
    return true;
  }
  return false;
}
function spawnCoins() {
  const lane = A.randInt(0, 2);
  if (lanesNear(-300, 380).has(lane)) return;
  for (let i = 0; i < 5; i++) S.items.push({ kind: 'coin', x: LANES[lane], y: -60 - i * 90, ph: i * .6 });
}
function spawnItem(kind) {
  const free = [0, 1, 2].filter((l) => !lanesNear(-80, 200).has(l));
  const lane = free.length ? A.pick(free) : A.randInt(0, 2);
  S.items.push({ kind, x: LANES[lane], y: -80, ph: 0 });
}

/* ---------------- обновление ---------------- */
/* широкое окно: касания и мышь — в координаты мира (поле уменьшено и сдвинуто) */
function wIn(inp) {
  if (!LAND) return inp;
  const p = inp.pointer, k = 1 / FS, wx = (x) => (x - FX) * k, wy = (y) => y * k;
  return {
    down: (n) => inp.down(n), pressed: (n) => inp.pressed(n), swipe: inp.swipe,
    get mouseActive() { return inp.mouseActive; }, set mouseActive(v) { inp.mouseActive = v; },
    tap: inp.tap && { x: wx(inp.tap.x), y: wy(inp.tap.y) },
    pointer: Object.assign({}, p, { x: wx(p.x), y: wy(p.y), sx: wx(p.sx), sy: wy(p.sy), dx: p.dx * k, dy: p.dy * k })
  };
}

function update(g, dt) {
  const inp = wIn(g.input), p = S.p;
  if (S.banner) { S.banner.t += dt; if (S.banner.t > 2) S.banner = null; }
  S.shown += (S.score - S.shown) * Math.min(1, dt * 8);
  if (S.mode === 'over') return;
  if (S.mode === 'dead') {
    S.deadT += dt; S.speed = Math.max(0, S.speed - 900 * dt);
    scroll(g, dt);
    if (S.deadT > 1.3) gameOver(g);
    return;
  }

  const m = meters();
  const base = 540 + Math.min(760, m * .32);
  let target = base;
  if (S.mode === 'play') {
    // управление
    const kx = (inp.down('right') ? 1 : 0) - (inp.down('left') ? 1 : 0);
    const ox = p.x;
    if (kx) p.vx = A.clamp(p.vx + kx * 3200 * dt, -640, 640);
    else p.vx -= p.vx * Math.min(1, dt * 9);
    p.x += p.vx * dt;
    const ptr = inp.pointer;
    if (ptr.down && ptr.type !== 'mouse') p.x += ptr.dx * 1.35;
    else if (inp.mouseActive && !kx) p.x += (ptr.x - p.x) * Math.min(1, dt * 9);
    p.x = A.clamp(p.x, ROAD_L - 26, ROAD_R + 26);
    const realVx = (p.x - ox) / dt;
    p.tilt += (A.clamp(realVx / 800, -1, 1) - p.tilt) * Math.min(1, dt * 10);
    if (inp.down('up')) target *= 1.12;
    if (inp.down('down')) target *= .7;
    if (S.nitro > 0) { S.nitro -= dt; target *= 1.55; }
    if (S.inv > 0) S.inv -= dt;
  } else {
    // ИИ для заставки
    target = 600;
    let best = p.aiLane, bestGap = -1;
    for (let l = 0; l < 3; l++) {
      let gap = 2000;
      for (const c of S.cars) if (!c.knock && laneOf(c) === l && c.y < PY + 60) gap = Math.min(gap, PY - (c.y + c.h / 2));
      if (l === p.aiLane) gap += 150;
      if (gap > bestGap) { bestGap = gap; best = l; }
    }
    p.aiLane = best;
    const ox = p.x;
    p.x += (LANES[best] - p.x) * Math.min(1, dt * 4);
    p.tilt += (A.clamp((p.x - ox) / dt / 800, -1, 1) - p.tilt) * Math.min(1, dt * 10);
  }
  p.offroad = p.x < ROAD_L + 18 || p.x > ROAD_R - 18;
  if (p.offroad) target *= .62;
  S.speed += (target - S.speed) * Math.min(1, dt * (target < S.speed ? 3 : 1.4));

  // выхлоп
  p.puffT -= dt;
  if (p.puffT <= 0) {
    p.puffT = S.nitro > 0 ? .03 : .08;
    for (const sx of [-14, 14]) g.fx.burst(p.x + sx, PY + 58, { n: 1, angle: Math.PI / 2, spread: .3, speed: 160, size: S.nitro > 0 ? 9 : 7, colors: S.nitro > 0 ? ['#7ad8ff', '#ffffff', '#ffd43b'] : ['rgba(255,255,255,.85)', 'rgba(220,225,240,.8)'], life: .4, drag: 1.5 });
  }
  if (p.offroad && Math.random() < .5) g.fx.burst(p.x + A.rand(-25, 25), PY + 40, { n: 1, angle: Math.PI / 2, spread: .8, speed: 200, size: 6, colors: ['#c9a36b', '#8bc34a', '#e0c48c'], life: .35 });

  scroll(g, dt);

  // спавн
  if (S.dist > S.nextCar) { if (spawnCar()) S.nextCar = S.dist + A.rand(260, 420) * (1 + Math.max(0, 1 - m / 2500) * .4); else S.nextCar = S.dist + 80; }
  if (S.dist > S.nextCoins) { spawnCoins(); S.nextCoins = S.dist + A.rand(700, 1200); }
  if (S.dist > S.nextNitro) { spawnItem('nitro'); S.nextNitro = S.dist + A.rand(3000, 4200); }
  if (S.dist > S.nextShield) { spawnItem('shield'); S.nextShield = S.dist + A.rand(5000, 7000); }

  if (S.mode === 'play') {
    collide(g);
    S.score = meters() + S.bonus;
    const zi = Math.floor(meters() / 1000);
    if (zi !== S.zoneIdx) { S.zoneIdx = zi; const z = zoneAt(meters()); banner(ZONE_NAME[z], (zi * 1000).toLocaleString('ru-RU') + ' м'); g.sfx('power', { pitch: .8, vol: .6 }); }
  }
  // линии скорости
  if (S.nitro > 0 && S.mode === 'play') for (let i = 0; i < 2; i++) S.lines.push({ x: A.rand(20, W - 20), y: A.rand(-200, H * .6), l: A.rand(80, 200), life: .35 });
  for (const l of S.lines) { l.y += 2400 * dt; l.life -= dt; }
  S.lines = S.lines.filter((l) => l.life > 0);
}

function scroll(g, dt) {
  const dy = S.speed * dt;
  S.dist += dy;
  for (const s of S.segs) s.y += dy;
  S.segs = S.segs.filter((s) => s.y < H + 10);
  while (S.segs[S.segs.length - 1].y > -SEG_H * 1.5) {
    const top = S.segs[S.segs.length - 1].y - SEG_H;
    const mAt = (S.dist + (PY - top - SEG_H / 2)) / PX_PER_M;
    S.segs.push(makeSegment(top, mAt));
  }
  for (const it of S.items) it.y += dy;
  S.items = S.items.filter((it) => it.y < H + 60 && !it.got);
  for (const c of S.cars) {
    if (c.knock) {
      c.x += c.knock.vx * dt; c.y += (S.speed * .6 + c.knock.vy) * dt; c.rot += c.knock.vr * dt; c.knock.a -= dt * 1.2;
      continue;
    }
    c.y += (S.speed - c.speed) * dt;
    // перестроение
    if (c.wantsChange && !c.change && c.y > 60 && c.y < H * .5) {
      const opts = [c.lane - 1, c.lane + 1].filter((l) => l >= 0 && l <= 2);
      const to = A.pick(opts);
      const busy = S.cars.some((o) => o !== c && !o.knock && (laneOf(o) === to || (o.change && o.change.to === to)) && Math.abs(o.y - c.y) < 260);
      c.wantsChange = false;
      if (!busy) { c.change = { to, from: c.x, t: 0 }; c.blink = to > c.lane ? 1 : -1; }
    }
    if (c.change) {
      c.change.t += dt;
      if (c.change.t > .9) {
        const k = Math.min(1, (c.change.t - .9) / .9);
        c.x = A.lerp(c.change.from, LANES[c.change.to], A.ease.inOutSine(k));
        c.rot = Math.sin(k * Math.PI) * .12 * Math.sign(LANES[c.change.to] - c.change.from);
        if (k >= 1) { c.lane = c.change.to; c.change = null; c.blink = 0; c.rot = 0; }
      }
    }
  }
  S.cars = S.cars.filter((c) => c.y - c.h / 2 < H + 40 && (!c.knock || c.knock.a > 0));
}

function collide(g) {
  const p = S.p;
  const pw = 52, ph = 96;
  const px0 = p.x - pw / 2, px1 = p.x + pw / 2, py0 = PY - ph / 2, py1 = PY + ph / 2;
  for (const c of S.cars) {
    if (c.knock) continue;
    const cw = c.w - 8, ch = c.h - 10;
    const hit = px0 < c.x + cw / 2 && px1 > c.x - cw / 2 && py0 < c.y + ch / 2 && py1 > c.y - ch / 2;
    if (hit) {
      const dir = Math.sign(c.x - p.x) || A.pick([-1, 1]);
      c.knock = { vx: dir * 520, vy: -200, vr: dir * 7, a: 1 };
      c.passed = true;
      if (S.nitro > 0 || S.shield || S.inv > 0) {
        if (S.nitro > 0) { S.bonus += 100; g.fx.text(c.x, c.y - 30, 'Бам! +100', { color: '#7ad8ff', size: 34 }); g.sfx('hit', { pitch: .8 }); }
        else if (S.shield) { S.shield = false; S.inv = 1; g.sfx('hit', { pitch: 1.5 }); g.fx.ring(p.x, PY, { r1: 150, color: '#5fd3ff', width: 10 }); }
        g.fx.burst((c.x + p.x) / 2, (c.y + PY) / 2, { n: 12, colors: ['#fff', '#ffd43b'], speed: 360, size: 6, shape: 'spark', life: .4 });
        g.shake(5, .15);
        continue;
      }
      S.lives--; S.inv = 1.8; S.speed *= .55;
      g.sfx('boom'); g.shake(16, .4);
      g.fx.burst((c.x + p.x) / 2, (c.y + PY) / 2, { n: 26, colors: ['#ff8a3d', '#ffd43b', '#fff', '#ff4f7b'], speed: 460, size: 10, life: .6 });
      g.fx.burst((c.x + p.x) / 2, (c.y + PY) / 2, { n: 8, colors: ['rgba(255,255,255,.9)', '#dfe7ff'], speed: 140, size: 24, life: .7, drag: 3 });
      g.fx.ring(p.x, PY, { r1: 120, width: 8 });
      if (S.lives <= 0) {
        S.mode = 'dead'; S.deadT = 0; g.stopMusic(); g.sfx('bigboom');
        g.fx.burst(p.x, PY, { n: 40, colors: ['#ff8a3d', '#ffd43b', '#fff'], speed: 600, size: 13, life: 1 });
        return;
      }
      continue;
    }
    if (!c.passed && c.y - c.h / 2 > py1) {
      c.passed = true;
      const gap = Math.abs(c.x - p.x) - (c.w / 2 + pw / 2);
      if (gap >= -4 && gap < 26 && S.inv <= 0) {
        S.bonus += 50;
        g.fx.text(p.x, PY - 90, 'Впритирку! +50', { color: '#ffe066', size: 32 });
        const sx = (c.x + p.x) / 2;
        g.fx.burst(sx, PY, { n: 10, colors: ['#ffe066', '#fff'], speed: 320, size: 5, shape: 'spark', life: .35 });
        g.sfx('coin', { pitch: 1.3, vol: .7 });
      }
    }
  }
  for (const it of S.items) {
    if (it.got || A.dist(it.x, it.y, p.x, PY) > 58) continue;
    it.got = true;
    if (it.kind === 'coin') { S.bonus += 25; S.coins++; g.sfx('coin'); g.fx.text(it.x, it.y - 20, '+25', { color: '#ffe066', size: 28 }); }
    else if (it.kind === 'nitro') { S.nitro = 3.2; g.sfx('power'); g.sfx('whoosh'); g.fx.text(p.x, PY - 100, 'Нитро!', { color: '#7ad8ff', size: 40 }); g.shake(4, .2); }
    else if (it.kind === 'shield') { S.shield = true; g.sfx('power', { pitch: .8 }); g.fx.text(p.x, PY - 100, 'Щит', { color: '#5fd3ff', size: 36 }); }
    g.fx.burst(it.x, it.y, { n: 10, colors: ['#fff', '#ffe066'], speed: 240, size: 6, shape: 'star', life: .5 });
  }
}

/* ---------------- отрисовка ---------------- */
function drawHud(ctx, g) {
  if (!LAND) drawGauges(ctx);                               // в широком окне — на боковых панелях
  drawBanner(ctx);
}
function drawGauges(ctx) {
  A.text(ctx, Math.round(S.shown).toLocaleString('ru-RU'), 28, 56, { align: 'left', size: 46, color: '#fff', stroke: OUT, strokeW: 9 });
  A.text(ctx, meters().toLocaleString('ru-RU') + ' м', 30, 104, { align: 'left', size: 28, color: '#ffe066', stroke: OUT, strokeW: 7 });
  for (let i = 0; i < 3; i++) A.heart(ctx, W - 46 - i * 50, 58, 44, i < S.lives ? '#ff4f7b' : 'rgba(43,37,80,.35)', OUT);
  speedo(ctx, W - 92, H - 84, 64);
  if (S.nitro > 0) {
    A.rr(ctx, 30, 130, 180, 16, 8); ctx.fillStyle = 'rgba(43,37,80,.45)'; ctx.fill();
    A.rr(ctx, 30, 130, 180 * Math.min(1, S.nitro / 3.2), 16, 8); ctx.fillStyle = '#7ad8ff'; ctx.fill();
    A.rr(ctx, 30, 130, 180, 16, 8); ctx.lineWidth = 3.5; ctx.strokeStyle = OUT; ctx.stroke();
  }
}
function speedo(ctx, cx, cy, r, big) {                      // спидометр (в широком окне — крупнее, с подписями крупнее)
  const kmh = Math.round(S.speed / 5);
  ctx.save();
  ctx.beginPath(); ctx.arc(cx, cy, r + 10, 0, Math.PI * 2); ctx.fillStyle = 'rgba(20,18,45,.72)'; ctx.fill();
  ctx.lineWidth = 4; ctx.strokeStyle = OUT; ctx.stroke();
  const a0 = Math.PI * .8, a1 = Math.PI * 2.2, k = A.clamp(S.speed / 2100, 0, 1);
  ctx.lineCap = 'round';
  ctx.beginPath(); ctx.arc(cx, cy, r - 6, a0, a1); ctx.lineWidth = 10; ctx.strokeStyle = 'rgba(255,255,255,.15)'; ctx.stroke();
  ctx.beginPath(); ctx.arc(cx, cy, r - 6, a0, a0 + (a1 - a0) * k); ctx.strokeStyle = S.nitro > 0 ? '#7ad8ff' : k > .75 ? '#ff4f7b' : '#ffd43b'; ctx.stroke();
  const na = a0 + (a1 - a0) * k;
  ctx.beginPath(); ctx.moveTo(cx, cy); ctx.lineTo(cx + Math.cos(na) * (r - 18), cy + Math.sin(na) * (r - 18)); ctx.lineWidth = 4; ctx.strokeStyle = '#fff'; ctx.stroke();
  ctx.beginPath(); ctx.arc(cx, cy, 6, 0, Math.PI * 2); ctx.fillStyle = '#fff'; ctx.fill();
  if (big) {
    A.text(ctx, String(kmh), cx, cy + r * .5, { size: 32, color: '#fff' });
    A.text(ctx, 'км/ч', cx, cy + r * .5 + 30, { size: 20, weight: 600, color: 'rgba(255,255,255,.75)' });
  } else {
    A.text(ctx, String(kmh), cx, cy + 30, { size: 24, color: '#fff' });
    A.text(ctx, 'км/ч', cx, cy + 52, { size: 13, weight: 500, color: 'rgba(255,255,255,.7)' });
  }
  ctx.restore();
}
function drawBanner(ctx) {
  if (S.banner) {
    const t = S.banner.t, kk = t < .35 ? A.ease.outBack(t / .35) : 1, a = t > 1.6 ? 1 - (t - 1.6) / .4 : 1;
    ctx.save(); ctx.globalAlpha = Math.max(0, a); ctx.translate(W / 2, H * .3); ctx.scale(kk, kk);
    A.text(ctx, S.banner.text, 0, 0, { size: 76, color: '#fff', stroke: OUT, strokeW: 14, weight: 900 });
    if (S.banner.sub) A.text(ctx, S.banner.sub, 0, 64, { size: 32, color: '#ffe066', stroke: OUT, strokeW: 9 });
    ctx.restore();
  }
}

function drawWorld(ctx, g) {
  const t = g.t, p = S.p;
  for (const s of S.segs) drawGround(ctx, s, t);
  drawRoad(ctx, S.dist, S.segs);
  for (const s of S.segs) for (const d of s.items) if (d.t !== 'tree' && d.t !== 'palm' && d.t !== 'house') drawDecor(ctx, s, d, t);
  for (const it of S.items) drawItem(ctx, it, t);
  for (const c of S.cars) drawVehicle(ctx, c, t, { alpha: c.knock ? Math.max(0, c.knock.a) : null });
  if (S.mode !== 'dead' && S.mode !== 'over' && !(S.inv > 0 && Math.floor(t * 14) % 2 === 0)) {
    drawVehicle(ctx, { type: 'car', x: p.x, y: PY, w: 62, h: 108, col: PLAYER_COL, rot: p.tilt * .14 }, t, { stripes: true, spoiler: true, lights: S.nitro > 0 });
    if (S.shield) {
      ctx.beginPath(); ctx.ellipse(p.x, PY, 62 + Math.sin(t * 8) * 3, 82, 0, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(95,211,255,.16)'; ctx.fill(); ctx.lineWidth = 4; ctx.strokeStyle = '#5fd3ff'; ctx.stroke();
    }
  }
  for (const s of S.segs) for (const d of s.items) if (d.t === 'tree' || d.t === 'palm' || d.t === 'house') drawDecor(ctx, s, d, t);
  if (S.lines.length) {
    ctx.strokeStyle = 'rgba(255,255,255,.75)'; ctx.lineCap = 'round';
    for (const l of S.lines) { ctx.globalAlpha = l.life / .35; ctx.lineWidth = 4; ctx.beginPath(); ctx.moveTo(l.x, l.y); ctx.lineTo(l.x, l.y + l.l); ctx.stroke(); }
    ctx.globalAlpha = 1;
  }
  if (S.mode !== 'title') drawHud(ctx, g);
}
/* ---------------- широкое окно ---------------- */
const LABEL = { size: 22, weight: 700, color: 'rgba(43,37,80,.6)' };
const ZONE_COL = { forest: '#40c057', seaside: '#4dabf7', city: '#ff922b' };
function plate(ctx, x, y, w, h) {                           // наклейка, как машинки: белая, с обводкой и тенью
  ctx.fillStyle = 'rgba(20,20,50,.22)'; A.rr(ctx, x + 7, y + 10, w, h, 24); ctx.fill();
  A.rr(ctx, x, y, w, h, 24); ctx.fillStyle = 'rgba(255,255,255,.92)'; ctx.fill();
  ctx.lineWidth = 4; ctx.strokeStyle = OUT; ctx.lineJoin = 'round'; ctx.stroke();
}
function fitText(ctx, str, x, y, o, maxW) {                 // крупное число, которое не вылезет за наклейку
  ctx.font = `${o.weight || 800} ${o.size}px ${A.FONT}`;
  const w = ctx.measureText(str).width, k = w > maxW ? maxW / w : 1;
  A.text(ctx, str, x, y, Object.assign({}, o, { size: o.size * k, strokeW: (o.strokeW || 9) * Math.max(.7, k) }));
}
function keycap(ctx, x, y, label) {
  const s = 42;
  A.rr(ctx, x - s / 2, y - s / 2 + 5, s, s, 11); ctx.fillStyle = 'rgba(43,37,80,.25)'; ctx.fill();
  A.rr(ctx, x - s / 2, y - s / 2, s, s, 11); ctx.fillStyle = '#fff'; ctx.fill(); ctx.lineWidth = 3; ctx.strokeStyle = OUT; ctx.stroke();
  A.text(ctx, label, x, y + 1, { size: 22, weight: 800, color: OUT });
}
function drawLight(ctx, x, y, t) {                          // светофорчик-болельщик: моргает огоньками и глазками
  ctx.save(); ctx.translate(x, y); ctx.lineJoin = 'round'; ctx.strokeStyle = OUT;
  ctx.fillStyle = 'rgba(20,20,50,.22)'; ctx.beginPath(); ctx.ellipse(12, 108, 36, 10, 0, 0, Math.PI * 2); ctx.fill();
  A.rr(ctx, -7, 50, 14, 58, 5); ctx.fillStyle = '#7d849e'; ctx.fill(); ctx.lineWidth = 3.5; ctx.stroke();
  A.rr(ctx, -40, -104, 80, 160, 26); ctx.fillStyle = '#ffd43b'; ctx.fill(); ctx.lineWidth = 4; ctx.stroke();
  ctx.fillStyle = 'rgba(255,255,255,.45)'; A.rr(ctx, -31, -94, 12, 56, 6); ctx.fill();
  const on = Math.floor(t / 1.2) % 3;
  ['#ff5a5a', '#ffb000', '#40c057'].forEach((c, i) => {
    const cy = -78 + i * 32;
    if (i === on) { ctx.fillStyle = c; ctx.globalAlpha = .3; ctx.beginPath(); ctx.arc(0, cy, 19, 0, Math.PI * 2); ctx.fill(); ctx.globalAlpha = 1; }
    ctx.beginPath(); ctx.arc(0, cy, 12, 0, Math.PI * 2); ctx.fillStyle = i === on ? c : 'rgba(43,37,80,.28)'; ctx.fill(); ctx.lineWidth = 3; ctx.stroke();
  });
  const blink = (t % 3.3) > 3.15;
  ctx.fillStyle = OUT;
  for (const ex of [-14, 14]) { ctx.beginPath(); if (blink) ctx.ellipse(ex, 22, 6, 1.6, 0, 0, Math.PI * 2); else ctx.ellipse(ex, 20, 5, 6.5, 0, 0, Math.PI * 2); ctx.fill(); }
  ctx.fillStyle = 'rgba(255,120,120,.55)'; ctx.beginPath(); ctx.arc(-26, 32, 5.5, 0, Math.PI * 2); ctx.arc(26, 32, 5.5, 0, Math.PI * 2); ctx.fill();
  ctx.beginPath(); ctx.arc(0, 30, 7, .15 * Math.PI, .85 * Math.PI); ctx.lineWidth = 3; ctx.lineCap = 'round'; ctx.stroke();
  ctx.restore();
}
function drawLand(ctx, g) {
  const t = g.t;
  // мир: дорога посередине, окрестности — до краёв
  ctx.save(); ctx.beginPath(); ctx.rect(0, 0, SW, SH); ctx.clip();
  ctx.translate(FX, 0); ctx.scale(FS, FS);
  drawWorld(ctx, g);
  if (g.fxWorld) g.fxWorld(ctx);
  ctx.restore();
  // слева: очки, метры, места, жизни
  const lx = LCX, lp = lx - PW / 2, m = S.mode === 'title' ? 0 : meters();
  plate(ctx, lp, 26, PW, 476);
  A.text(ctx, 'Очки', lx, 60, LABEL);
  fitText(ctx, Math.round(S.shown).toLocaleString('ru-RU'), lx, 110, { size: 58, color: '#fff', stroke: OUT, strokeW: 11, weight: 900 }, PW - 30);
  fitText(ctx, m.toLocaleString('ru-RU') + ' м', lx, 162, { size: 30, color: '#ffe066', stroke: OUT, strokeW: 8 }, PW - 30);
  const z = zoneAt(m), next = ZONES[(ZONES.indexOf(z) + 1) % ZONES.length];
  A.text(ctx, ZONE_NAME[z], lx, 212, { size: 26, weight: 800, color: OUT });
  A.rr(ctx, lx - 84, 236, 168, 14, 7); ctx.fillStyle = 'rgba(43,37,80,.14)'; ctx.fill();
  A.rr(ctx, lx - 84, 236, Math.max(14, 168 * (m % 1000) / 1000), 14, 7); ctx.fillStyle = ZONE_COL[z]; ctx.fill();
  A.rr(ctx, lx - 84, 236, 168, 14, 7); ctx.lineWidth = 3; ctx.strokeStyle = OUT; ctx.stroke();
  A.text(ctx, 'дальше: ' + ZONE_NAME[next], lx, 272, { size: 20, weight: 600, color: 'rgba(43,37,80,.65)' });
  A.text(ctx, 'Жизни', lx, 322, LABEL);
  for (let i = 0; i < 3; i++) A.heart(ctx, lx + (i - 1) * 56, 364, 50, i < S.lives ? '#ff4f7b' : 'rgba(43,37,80,.25)', OUT);
  ctx.fillStyle = 'rgba(43,37,80,.12)'; ctx.fillRect(lx - 70, 404, 140, 2);
  if (S.nitro > 0) {
    A.text(ctx, 'Нитро!', lx, 436, { size: 24, weight: 800, color: '#1c7ed6' });
    A.rr(ctx, lx - 84, 458, 168, 18, 9); ctx.fillStyle = 'rgba(43,37,80,.18)'; ctx.fill();
    A.rr(ctx, lx - 84, 458, 168 * Math.min(1, S.nitro / 3.2), 18, 9); ctx.fillStyle = '#7ad8ff'; ctx.fill();
    A.rr(ctx, lx - 84, 458, 168, 18, 9); ctx.lineWidth = 3; ctx.strokeStyle = OUT; ctx.stroke();
  } else {
    ctx.save(); ctx.translate(lx - 44, 452); drawItem(ctx, { kind: 'coin', x: 0, y: 0, ph: 0 }, t); ctx.restore();
    A.text(ctx, '× ' + S.coins, lx - 16, 453, { align: 'left', size: 28, weight: 800, color: OUT });
    if (S.shield) {
      ctx.save(); ctx.translate(lx + 70, 452); ctx.scale(.8, .8); drawItem(ctx, { kind: 'shield', x: 0, y: 0, ph: 0 }, t); ctx.restore();
    }
  }
  drawLight(ctx, lx, 600, t);
  // справа: спидометр, рекорд, управление
  const rx = RCX, rp = rx - PW / 2;
  speedo(ctx, rx, 112, 78, true);
  plate(ctx, rp, 222, PW, 122);
  A.text(ctx, 'Рекорд', rx, 256, LABEL);
  fitText(ctx, (g.best || 0).toLocaleString('ru-RU'), rx, 302, { size: 42, color: '#fff', stroke: OUT, strokeW: 10, weight: 900 }, PW - 30);
  plate(ctx, rp, 366, PW, 300);
  A.text(ctx, 'Управление', rx, 400, LABEL);
  if (A.isTouch) {
    A.text(ctx, 'ведите пальцем', rx, 452, { size: 22, weight: 800, color: OUT });
    A.text(ctx, 'влево-вправо', rx, 484, { size: 22, weight: 800, color: OUT });
    A.text(ctx, 'в любом месте', rx, 526, { size: 20, weight: 600, color: 'rgba(43,37,80,.65)' });
    A.text(ctx, 'экрана', rx, 554, { size: 20, weight: 600, color: 'rgba(43,37,80,.65)' });
  } else {
    keycap(ctx, rp + 40, 448, '←'); keycap(ctx, rp + 88, 448, '→');
    A.text(ctx, 'руль', rp + 120, 449, { align: 'left', size: 22, weight: 800, color: OUT });
    keycap(ctx, rp + 40, 504, '↑');
    A.text(ctx, 'газ', rp + 72, 505, { align: 'left', size: 22, weight: 800, color: OUT });
    keycap(ctx, rp + 40, 560, '↓');
    A.text(ctx, 'тормоз', rp + 72, 561, { align: 'left', size: 22, weight: 800, color: OUT });
    A.text(ctx, 'мышь — тоже руль', rx, 622, { size: 20, weight: 600, color: 'rgba(43,37,80,.65)' });
  }
}
function draw(ctx, g) {
  if (LAND) drawLand(ctx, g); else drawWorld(ctx, g);
}

A.game({
  id: 'racer', tone: 'light', title: 'Гонка', width: SW, height: SH, orientation: LAND ? 'landscape' : 'portrait', music: 'road',
  help: {
    desktop: '<kbd>←</kbd> <kbd>→</kbd> или мышь — руль · <kbd>↑</kbd> газ · <kbd>↓</kbd> тормоз · <kbd>P</kbd> пауза · <kbd>M</kbd> музыка',
    short: '<b>Стрелки</b> или <b>мышь</b> — руль, <b>↑ ↓</b> — газ и тормоз',
    touch: 'Ведите пальцем влево-вправо в любом месте экрана — машина повторит'
  },
  init(g) {
    if (LAND) {                                             // эффекты — в координатах мира: рисуем их внутри мира, надписи крупнее
      const fxDraw = g.fx.draw.bind(g.fx), fxText = g.fx.text.bind(g.fx);
      g.fx.draw = () => {}; g.fxWorld = fxDraw;
      g.fx.text = (x, y, str, o = {}) => fxText(x, y, str, Object.assign({}, o, { size: (o.size || 34) * 1.3, rise: (o.rise || 70) * 1.2 }));
    }
    S = fresh(); titleScreen(g);
  },
  update, draw
});
window.__racer = () => S;
})();
