/* Лукошко — игра в духе карманных электронных игр с жидкокристаллическим экраном (27.10, владелец: «игра из детства —
   ловил яйца, падающие с полок… попробуем добавить такую?»). Свои герои: Кот с лукошком и четыре курочки на насестах.
   Яйца катятся по четырём жёлобам по шагам, как сегменты на экране; Кот ставит лукошко к одному из четырёх концов.
   Поймал — очко; упало — разбилось, цыплёнок убегает, это промах. Три промаха — конец. Каждые 100 очков промахи
   прощаются. «Игра А» — спокойнее, «Игра Б» — быстрее и больше яиц. Управление: стрелки (← → — сторона, ↑ ↓ — верх
   или низ), Q / A / P / L или 7 / 1 / 9 / 3 на цифровой клавиатуре, мышь и пальцы — четыре красные кнопки или четверть
   экрана. Широкое окно — устройство лёжа (кнопки по бокам), узкое (телефон) — стоя (кнопки под экраном). */
(() => {
'use strict';
const A = Arcade;
const LAND = (() => { try { return innerWidth > (innerHeight - 110) * 1.05; } catch (e) { return true; } })();
const W = LAND ? 1280 : 720, H = LAND ? 720 : 1280;
// экран устройства и где на нём логическое поле 880×500
const SCR = LAND ? { x: 210, y: 112, w: 860, h: 500 } : { x: 56, y: 150, w: 608, h: 346 };
const LW = 880, LH = 500, K = Math.min(SCR.w / LW, SCR.h / LH), OX = SCR.x + (SCR.w - LW * K) / 2, OY = SCR.y + (SCR.h - LH * K) / 2;
// кнопки: 0 — слева вверху, 1 — слева внизу, 2 — справа вверху, 3 — справа внизу
const BTN = LAND ? [{ x: 105, y: 290 }, { x: 105, y: 520 }, { x: 1175, y: 290 }, { x: 1175, y: 520 }].map((b) => Object.assign(b, { r: 58 }))
  : [{ x: 200, y: 760 }, { x: 200, y: 1010 }, { x: 520, y: 760 }, { x: 520, y: 1010 }].map((b) => Object.assign(b, { r: 96 }));
const INK = '#273027', GHOST = 'rgba(39,48,39,.075)';
// жёлоба: начало (у курочки) и конец (у лукошка); по 5 положений яйца
const RAMP = [{ x0: 70, y0: 150, x1: 300, y1: 218 }, { x0: 70, y0: 300, x1: 300, y1: 368 },
  { x0: 810, y0: 150, x1: 580, y1: 218 }, { x0: 810, y0: 300, x1: 580, y1: 368 }];
const STEPS = 5;
let S = null, G = null;

function fresh(mode, game) {
  S = { mode, game: game || 'A', score: 0, miss: 0, pose: 1, eggs: [], broken: [], tick: 0, nextT: 0, since: 0, flash: 0, catches: 0, shown: 0 };
}
const interval = () => Math.max(S.game === 'B' ? .17 : .22, (S.game === 'B' ? .5 : .66) - S.score * (S.game === 'B' ? .0032 : .0028));
const maxEggs = () => Math.min(S.game === 'B' ? 6 : 5, (S.game === 'B' ? 2 : 1) + Math.floor(S.score / (S.game === 'B' ? 20 : 25)));

/* ---------------- экраны ---------------- */
function titleScreen(g) {
  fresh('title'); g.setPlaying(false);
  g.screen({
    kicker: A.framed ? 'Досуг' : 'Аркада', title: 'Лукошко',
    html: `<p>Курочки несут яйца, яйца катятся по жёлобам. Кот с лукошком ловит их — подставьте лукошко к нужному жёлобу.</p>`
      + `<p>Три разбитых яйца — конец. Каждые 100 очков промахи прощаются.</p>${g.best ? `<p class="record">Рекорд: ${g.best.toLocaleString('ru-RU')}</p>` : ''}`,
    button: 'Игра А', onGo: () => startGame(g, 'A'), alt: { label: 'Игра Б — быстрее', onGo: () => startGame(g, 'B') }
  });
}
function startGame(g, game) {
  fresh('play', game);
  g.fx.clear(); g.setPlaying(true); g.playMusic();
  S.nextT = 1.0;
}
function gameOver(g) {
  S.mode = 'over'; g.setPlaying(false); g.stopMusic(); g.sfx('lose');
  const rec = g.submit(S.score);
  setTimeout(() => g.screen({
    kicker: 'Лукошко', title: S.score >= 100 ? 'Отличный улов!' : 'Три разбитых',
    html: `<div class="score">${S.score.toLocaleString('ru-RU')}</div><p>${rec ? '<span class="record">Новый рекорд!</span>' : `Рекорд: ${g.best.toLocaleString('ru-RU')}`} · игра ${S.game === 'A' ? 'А' : 'Б'}</p>`,
    button: 'Ещё раз', onGo: () => startGame(g, S.game),
    alt: { label: A.framed ? 'К играм' : 'В аркаду', onGo: () => A.home('../index.html') }
  }), 900);
}

/* ---------------- ход ---------------- */
function setPose(p) { if (S.pose !== p) { S.pose = p; G.sfx('click', { vol: .35 }); } }
function readInput(g) {
  const inp = g.input, p = inp.pointer;
  if (inp.pressed('lu')) setPose(0); if (inp.pressed('ld')) setPose(1); if (inp.pressed('ru')) setPose(2); if (inp.pressed('rd')) setPose(3);
  const side = () => (S.pose >= 2 ? 1 : 0), low = () => S.pose % 2;    // заново после каждой клавиши: «→» и «↑» вместе
  if (inp.pressed('left')) setPose(low()); if (inp.pressed('right')) setPose(2 + low());
  if (inp.pressed('up')) setPose(side() * 2); if (inp.pressed('down')) setPose(side() * 2 + 1);
  if (p.justDown) {                                  // кнопка рядом — она; иначе — четверть экрана
    let best = -1, bd = 1e9;
    BTN.forEach((b, i) => { const d = A.dist(p.x, p.y, b.x, b.y); if (d < b.r * 1.35 && d < bd) { bd = d; best = i; } });
    if (best < 0 && p.x > SCR.x && p.x < SCR.x + SCR.w && p.y > SCR.y && p.y < SCR.y + SCR.h) {
      best = (p.x > SCR.x + SCR.w / 2 ? 2 : 0) + (p.y > SCR.y + SCR.h / 2 ? 1 : 0);
    }
    if (best >= 0) { setPose(best); S.press = { i: best, t: .18 }; }
  }
}
function step(g) {
  S.tick++;
  g.sfx('click', { vol: .16, pitch: 1.6 });          // тиканье экрана — сухое, как у старых игр
  for (const e of S.eggs) e.pos++;
  for (const e of S.eggs.filter((x) => x.pos >= STEPS)) {
    S.eggs.splice(S.eggs.indexOf(e), 1);
    if (S.pose === e.ramp) {
      S.score++; S.catches++; g.sfx('coin', { vol: .6 });
      if (S.score % 100 === 0) { S.miss = 0; g.sfx('win'); S.flash = 1.4; }
    } else {
      S.miss++; g.sfx('hurt'); g.shake(6, .2);
      S.broken.push({ ramp: e.ramp, t: 0 });
      if (S.miss >= 3) { gameOver(g); return; }
    }
  }
  const n = maxEggs(), busy = new Set(S.eggs.filter((e) => e.pos === 0).map((e) => e.ramp));
  if (S.eggs.length < n && Math.random() < (S.eggs.length ? .55 : 1)) {
    const free = [0, 1, 2, 3].filter((r) => !busy.has(r) && !S.eggs.some((e) => e.ramp === r && e.pos <= 1));
    if (free.length) S.eggs.push({ ramp: A.pick(free), pos: 0 });
  }
}
function update(g, dt) {
  if (S.press) { S.press.t -= dt; if (S.press.t <= 0) S.press = null; }
  S.shown += (S.score - S.shown) * Math.min(1, dt * 12);
  for (const b of S.broken) b.t += dt;
  S.broken = S.broken.filter((b) => b.t < 1.6);
  if (S.flash > 0) S.flash -= dt;
  if (S.mode !== 'play' || g.paused || g.screenOn) return;
  readInput(g);
  S.nextT -= dt;
  if (S.nextT <= 0) { S.nextT += interval(); step(g); }
}

/* ---------------- рисунки ЖК-экрана (логическое поле 880×500) ---------------- */
function seg7(ctx, d, x, y, h, col) {               // цифра из семи сегментов
  const w = h * .52, t = h * .12, SEG = { a: [0, 0, 1, 0], b: [1, 0, 1, .5], c: [1, .5, 1, 1], d: [0, 1, 1, 1], e: [0, .5, 0, 1], f: [0, 0, 0, .5], g: [0, .5, 1, .5] };
  const ON = ['abcdef', 'bc', 'abged', 'abgcd', 'fgbc', 'afgcd', 'afgedc', 'abc', 'abcdefg', 'abcdfg'][d] || '';
  for (const k of 'abcdefg') {
    const [x0, y0, x1, y1] = SEG[k];
    ctx.fillStyle = ON.includes(k) ? col : GHOST;
    if (y0 === y1) A.rr(ctx, x + x0 * w + t * .6, y + y0 * h - t / 2, w - t * 1.2, t, t / 2);
    else A.rr(ctx, x + x0 * w - t / 2, y + y0 * h + t * .6, t, h / 2 - t * 1.2, t / 2);
    ctx.fill();
  }
}
function eggAt(r, pos) {
  const R = RAMP[r], k = (pos + .5) / STEPS;
  return { x: A.lerp(R.x0, R.x1, k), y: A.lerp(R.y0, R.y1, k) - 16, a: Math.atan2(R.y1 - R.y0, R.x1 - R.x0) };
}
function drawEgg(ctx, x, y, rot, col) {
  ctx.save(); ctx.translate(x, y); ctx.rotate(rot);
  ctx.beginPath(); ctx.ellipse(0, 0, 15, 11, 0, 0, Math.PI * 2); ctx.fillStyle = col; ctx.fill();
  if (col === INK) { ctx.beginPath(); ctx.ellipse(-4, -4, 4, 2.4, -.5, 0, Math.PI * 2); ctx.fillStyle = 'rgba(200,214,190,.5)'; ctx.fill(); }
  ctx.restore();
}
function drawRamp(ctx, R) {
  ctx.strokeStyle = INK; ctx.lineWidth = 6; ctx.lineCap = 'round';
  ctx.beginPath(); ctx.moveTo(R.x0, R.y0); ctx.lineTo(R.x1, R.y1); ctx.stroke();
  // столбики под жёлобом
  ctx.lineWidth = 4;
  for (const k of [.25, .7]) { const x = A.lerp(R.x0, R.x1, k), y = A.lerp(R.y0, R.y1, k); ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x, y + 36); ctx.stroke(); }
}
function drawHen(ctx, x, y, dir, col, t) {           // курочка на насесте (dir: 1 — смотрит вправо)
  ctx.save(); ctx.translate(x, y); ctx.scale(dir, 1); ctx.fillStyle = col; ctx.strokeStyle = col;
  ctx.beginPath(); ctx.ellipse(0, 0, 30, 21, -.1, 0, Math.PI * 2); ctx.fill();                       // туловище
  ctx.beginPath(); ctx.moveTo(-26, -6); ctx.lineTo(-44, -22); ctx.lineTo(-40, -2); ctx.lineTo(-48, 2); ctx.lineTo(-26, 8); ctx.fill();   // хвост
  const nod = Math.sin(t * 3) * 2;
  ctx.beginPath(); ctx.arc(24, -22 + nod, 12, 0, Math.PI * 2); ctx.fill();                           // голова
  ctx.beginPath(); ctx.moveTo(34, -24 + nod); ctx.lineTo(46, -20 + nod); ctx.lineTo(34, -16 + nod); ctx.fill();   // клюв
  for (const [cx, cy] of [[18, -36], [24, -38], [30, -35]]) { ctx.beginPath(); ctx.arc(cx, cy + nod, 4.5, 0, Math.PI * 2); ctx.fill(); }   // гребешок
  if (col === INK) { ctx.beginPath(); ctx.arc(27, -24 + nod, 2.4, 0, Math.PI * 2); ctx.fillStyle = '#c3cdb9'; ctx.fill(); }
  ctx.lineWidth = 3; ctx.strokeStyle = col;
  ctx.beginPath(); ctx.moveTo(-6, 20); ctx.lineTo(-6, 30); ctx.moveTo(8, 20); ctx.lineTo(8, 30); ctx.stroke();
  ctx.restore();
}
/* Кот с лукошком: side 0 — лукошко слева, 1 — справа; low — внизу (руки опущены) */
function drawCat(ctx, side, low, col) {
  const dir = side ? 1 : -1;
  ctx.save(); ctx.translate(440, 300); ctx.fillStyle = col; ctx.strokeStyle = col; ctx.lineCap = 'round'; ctx.lineJoin = 'round';
  // хвост
  ctx.lineWidth = 9; ctx.beginPath(); ctx.moveTo(-dir * 26, 70); ctx.quadraticCurveTo(-dir * 82, 76, -dir * 74, 20); ctx.stroke();
  // туловище и лапы
  ctx.beginPath(); ctx.ellipse(0, 52, 40, 54, 0, 0, Math.PI * 2); ctx.fill();
  ctx.lineWidth = 12; ctx.beginPath(); ctx.moveTo(-16, 98); ctx.lineTo(-22, 152); ctx.moveTo(16, 98); ctx.lineTo(22, 152); ctx.stroke();
  ctx.beginPath(); ctx.ellipse(-26, 156, 16, 8, 0, 0, Math.PI * 2); ctx.ellipse(26, 156, 16, 8, 0, 0, Math.PI * 2); ctx.fill();
  // голова
  const hx = dir * 6;
  ctx.beginPath(); ctx.arc(hx, -26, 38, 0, Math.PI * 2); ctx.fill();
  ctx.beginPath(); ctx.moveTo(hx - 34, -40); ctx.lineTo(hx - 28, -80); ctx.lineTo(hx - 6, -60); ctx.fill();
  ctx.beginPath(); ctx.moveTo(hx + 34, -40); ctx.lineTo(hx + 28, -80); ctx.lineTo(hx + 6, -60); ctx.fill();
  if (col === INK) {                                  // мордочка — светлыми штрихами по тёмному
    ctx.fillStyle = '#c6d0bc'; ctx.strokeStyle = '#c6d0bc';
    ctx.beginPath(); ctx.ellipse(hx - 13 + dir * 4, -32, 5, 7, 0, 0, Math.PI * 2); ctx.ellipse(hx + 13 + dir * 4, -32, 5, 7, 0, 0, Math.PI * 2); ctx.fill();
    ctx.beginPath(); ctx.moveTo(hx + dir * 4 - 4, -16); ctx.lineTo(hx + dir * 4 + 4, -16); ctx.lineTo(hx + dir * 4, -11); ctx.fill();
    ctx.lineWidth = 2.4; ctx.beginPath();
    ctx.moveTo(hx + dir * 4, -10); ctx.quadraticCurveTo(hx + dir * 4 - 7, -2, hx + dir * 4 - 12, -8);
    ctx.moveTo(hx + dir * 4, -10); ctx.quadraticCurveTo(hx + dir * 4 + 7, -2, hx + dir * 4 + 12, -8);
    for (const s of [-1, 1]) { ctx.moveTo(hx + s * 20, -14); ctx.lineTo(hx + s * 44, -18); ctx.moveTo(hx + s * 20, -9); ctx.lineTo(hx + s * 44, -6); }
    ctx.stroke(); ctx.fillStyle = col; ctx.strokeStyle = col;
  }
  // руки к лукошку
  const bx = dir * 118, by = low ? 74 : -78;
  ctx.lineWidth = 13;
  ctx.beginPath(); ctx.moveTo(dir * 22, 30); ctx.quadraticCurveTo(dir * 70, low ? 60 : -10, bx - dir * 20, by + 8); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(-dir * 18, 34); ctx.quadraticCurveTo(dir * 40, low ? 96 : 20, bx - dir * 26, by + 22); ctx.stroke();
  // лукошко
  ctx.beginPath(); ctx.moveTo(bx - 40, by); ctx.lineTo(bx + 40, by); ctx.lineTo(bx + 30, by + 34); ctx.quadraticCurveTo(bx, by + 42, bx - 30, by + 34); ctx.closePath(); ctx.fill();
  ctx.lineWidth = 5; ctx.beginPath(); ctx.arc(bx, by + 2, 34, Math.PI * 1.08, Math.PI * 1.92); ctx.stroke();
  if (col === INK) {
    ctx.strokeStyle = '#c6d0bc'; ctx.lineWidth = 2;
    for (let i = -2; i <= 2; i++) { ctx.beginPath(); ctx.moveTo(bx + i * 14, by + 4); ctx.lineTo(bx + i * 11, by + 34); ctx.stroke(); }
    ctx.beginPath(); ctx.moveTo(bx - 36, by + 16); ctx.lineTo(bx + 36, by + 16); ctx.stroke();
  }
  ctx.restore();
}
function drawChickAndShell(ctx, b, col) {
  const R = RAMP[b.ramp], gx = R.x1 + (R.x1 < 440 ? -6 : 6), gy = 452, dir = R.x1 < 440 ? -1 : 1;
  ctx.fillStyle = col;
  // скорлупки
  ctx.beginPath(); ctx.moveTo(gx - 26, gy); ctx.lineTo(gx - 20, gy - 12); ctx.lineTo(gx - 14, gy - 4); ctx.lineTo(gx - 8, gy - 13); ctx.lineTo(gx - 4, gy); ctx.fill();
  ctx.beginPath(); ctx.moveTo(gx + 4, gy); ctx.lineTo(gx + 8, gy - 11); ctx.lineTo(gx + 14, gy - 3); ctx.lineTo(gx + 20, gy - 12); ctx.lineTo(gx + 26, gy); ctx.fill();
  if (b.t > .3) {                                      // цыплёнок убегает — по шагам, как на ЖК
    const k = Math.min(3, Math.floor((b.t - .3) / .32)), cx = gx + dir * (34 + k * 30), cy = gy - 14;
    ctx.beginPath(); ctx.arc(cx, cy, 11, 0, Math.PI * 2); ctx.fill();
    ctx.beginPath(); ctx.arc(cx + dir * 9, cy - 10, 7, 0, Math.PI * 2); ctx.fill();
    ctx.beginPath(); ctx.moveTo(cx + dir * 15, cy - 11); ctx.lineTo(cx + dir * 21, cy - 9); ctx.lineTo(cx + dir * 15, cy - 7); ctx.fill();
    ctx.lineWidth = 2.5; ctx.strokeStyle = col; ctx.beginPath(); ctx.moveTo(cx - 3, cy + 10); ctx.lineTo(cx - 5 + (k % 2) * 4, cy + 17); ctx.moveTo(cx + 3, cy + 10); ctx.lineTo(cx + 5 - (k % 2) * 4, cy + 17); ctx.stroke();
  }
}
function drawMissIcon(ctx, x, y, col) {
  ctx.fillStyle = col;
  ctx.beginPath(); ctx.arc(x, y, 10, 0, Math.PI * 2); ctx.fill();
  ctx.beginPath(); ctx.arc(x + 9, y - 9, 6.5, 0, Math.PI * 2); ctx.fill();
  ctx.beginPath(); ctx.moveTo(x + 14, y - 10); ctx.lineTo(x + 20, y - 8); ctx.lineTo(x + 14, y - 6); ctx.fill();
}
function drawLCD(ctx, g) {
  const t = g.t;
  // фон ЖК: зеленовато-серый, лёгкое зерно и блик
  const bg = ctx.createLinearGradient(0, 0, 0, LH);
  bg.addColorStop(0, '#cdd6c3'); bg.addColorStop(1, '#b9c5b1');
  A.rr(ctx, 0, 0, LW, LH, 18); ctx.fillStyle = bg; ctx.fill();
  ctx.save(); A.rr(ctx, 0, 0, LW, LH, 18); ctx.clip();
  ctx.fillStyle = 'rgba(255,255,255,.18)'; ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(LW * .55, 0); ctx.lineTo(LW * .25, LH); ctx.lineTo(0, LH); ctx.fill();
  // земля и травка
  ctx.strokeStyle = INK; ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(20, 462); ctx.lineTo(LW - 20, 462); ctx.stroke();
  ctx.lineWidth = 2.5;
  for (const x of [120, 210, 640, 760, 400, 480]) { ctx.beginPath(); ctx.moveTo(x, 462); ctx.lineTo(x - 6, 450); ctx.moveTo(x + 6, 462); ctx.lineTo(x + 6, 448); ctx.moveTo(x + 12, 462); ctx.lineTo(x + 18, 451); ctx.stroke(); }
  // жёлоба и курочки
  RAMP.forEach((R, i) => { drawRamp(ctx, R); drawHen(ctx, R.x0 + (i < 2 ? -4 : 4), R.y0 - 34, i < 2 ? 1 : -1, INK, t + i); });
  // «призраки» всех положений — как настоящий ЖК: невыключенные сегменты видно чуть-чуть
  for (let r = 0; r < 4; r++) for (let p = 0; p < STEPS; p++) { const e = eggAt(r, p); drawEgg(ctx, e.x, e.y, p * 1.3, GHOST); }
  for (let p = 0; p < 4; p++) if (p !== S.pose) drawCat(ctx, p >= 2 ? 1 : 0, p % 2, GHOST);
  // счёт и промахи
  const sc = String(Math.max(0, Math.round(S.shown))).padStart(4, ' ');
  for (let i = 0; i < 4; i++) seg7(ctx, sc[i] === ' ' ? -1 : +sc[i], 372 + i * 38, 26, 54, sc[i] === ' ' ? GHOST : INK);
  for (let i = 0; i < 3; i++) drawMissIcon(ctx, 700 + i * 44, 50, i < S.miss ? INK : GHOST);
  ctx.font = `800 17px ${A.FONT}`; ctx.textAlign = 'left'; ctx.textBaseline = 'middle';
  ctx.fillStyle = S.game === 'A' && S.mode !== 'title' ? INK : GHOST; ctx.fillText('ИГРА\u2002А', 26, 488);
  ctx.textAlign = 'right'; ctx.fillStyle = S.game === 'B' && S.mode !== 'title' ? INK : GHOST; ctx.fillText('ИГРА\u2002Б', LW - 26, 488);
  // яйца, кот, разбитые
  for (const e of S.eggs) { const q = eggAt(e.ramp, e.pos); drawEgg(ctx, q.x, q.y, e.pos * 1.3, INK); }
  drawCat(ctx, S.pose >= 2 ? 1 : 0, S.pose % 2, INK);
  for (const b of S.broken) drawChickAndShell(ctx, b, INK);
  if (S.flash > 0 && Math.floor(S.flash * 6) % 2) { ctx.font = `900 30px ${A.FONT}`; ctx.textAlign = 'center'; ctx.fillStyle = INK; ctx.fillText('ПРОМАХИ ПРОЩЕНЫ', LW / 2, 108); }
  ctx.restore();
}

/* ---------------- корпус ---------------- */
function drawBody(ctx, g) {
  ctx.fillStyle = '#d9d4c9'; ctx.fillRect(0, 0, W, H);
  const pad = LAND ? 16 : 14;
  const gr = ctx.createLinearGradient(0, 0, 0, H);
  gr.addColorStop(0, '#f4f1ea'); gr.addColorStop(1, '#dcd7cc');
  A.rr(ctx, pad, pad, W - pad * 2, H - pad * 2, LAND ? 44 : 56); ctx.fillStyle = gr; ctx.fill();
  ctx.lineWidth = 3; ctx.strokeStyle = 'rgba(120,110,95,.35)'; ctx.stroke();
  // рамка экрана: тёмная полоса с надписью
  const fx = SCR.x - 26, fy = SCR.y - 50, fw = SCR.w + 52, fh = SCR.h + 80;
  A.rr(ctx, fx, fy, fw, fh, 26); ctx.fillStyle = '#3b3f4a'; ctx.fill();
  ctx.font = `900 ${LAND ? 26 : 30}px ${A.FONT}`; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillStyle = '#ff6b5a';
  ctx.fillText('Л У К О Ш К О', SCR.x + SCR.w / 2, fy + 26);
  ctx.save(); ctx.translate(OX, OY); ctx.scale(K, K); drawLCD(ctx, g); ctx.restore();
  // надпись внизу корпуса
  ctx.font = `800 ${LAND ? 22 : 26}px ${A.FONT}`; ctx.fillStyle = '#6d6658';
  ctx.fillText('Д Е В И А Р   ·   И Г Р А   А / Б', W / 2, LAND ? H - 46 : fy + fh + 40);
  // четыре кнопки
  const ARW = [-Math.PI * .75, Math.PI * .75, -Math.PI * .25, Math.PI * .25];   // куда смотрит лукошко: ↖ ↙ ↗ ↘
  BTN.forEach((b, i) => {
    const down = (S.press && S.press.i === i) || S.pose === i && S.mode === 'play' && false;
    ctx.save(); ctx.translate(b.x, b.y + (down ? 3 : 0));
    ctx.beginPath(); ctx.arc(0, 6, b.r + 6, 0, Math.PI * 2); ctx.fillStyle = 'rgba(80,70,60,.18)'; ctx.fill();
    ctx.beginPath(); ctx.arc(0, 0, b.r + 6, 0, Math.PI * 2); ctx.fillStyle = '#bdb6a8'; ctx.fill();
    const rg = ctx.createRadialGradient(-b.r * .3, -b.r * .35, b.r * .1, 0, 0, b.r);
    rg.addColorStop(0, down ? '#e2544a' : '#ff8a7a'); rg.addColorStop(1, down ? '#a8231c' : '#d7372e');
    ctx.beginPath(); ctx.arc(0, 0, b.r, 0, Math.PI * 2); ctx.fillStyle = rg; ctx.fill();
    // стрелка, куда смотрит лукошко
    const s = b.r * .34;
    ctx.save(); ctx.rotate(ARW[i]); ctx.fillStyle = 'rgba(255,255,255,.92)';
    ctx.beginPath(); ctx.moveTo(s * 1.1, 0); ctx.lineTo(s * .1, -s * .62); ctx.lineTo(s * .1, s * .62); ctx.closePath(); ctx.fill();
    ctx.lineWidth = s * .42; ctx.lineCap = 'round'; ctx.strokeStyle = 'rgba(255,255,255,.92)'; ctx.beginPath(); ctx.moveTo(-s * .85, 0); ctx.lineTo(s * .3, 0); ctx.stroke(); ctx.restore();
    ctx.restore();
  });
}
function draw(ctx, g) { drawBody(ctx, g); }

A.game({
  id: 'basket', tone: 'light', title: 'Лукошко', width: W, height: H, orientation: LAND ? 'landscape' : 'portrait', music: 'garden',
  keys: { KeyQ: 'lu', KeyA: 'ld', KeyP: 'ru', KeyL: 'rd', Numpad7: 'lu', Numpad1: 'ld', Numpad9: 'ru', Numpad3: 'rd', KeyW: 'up', KeyS: 'down', KeyD: 'right' },
  help: {
    desktop: '<kbd>←</kbd> <kbd>→</kbd> — сторона, <kbd>↑</kbd> <kbd>↓</kbd> — верх или низ · или <kbd>Q</kbd> <kbd>A</kbd> <kbd>P</kbd> <kbd>L</kbd> · мышью — красные кнопки · <kbd>P</kbd> пауза — <kbd>Esc</kbd>',
    short: '<b>Стрелки</b>, <b>Q A P L</b> или красные кнопки',
    touch: 'Нажимайте красные кнопки или ту четверть экрана, куда катится яйцо'
  },
  init(g) {
    G = g; fresh('title'); titleScreen(g);
    if (A.shot) {                                   // обложка для полки: игра в разгаре
      g.hideScreen(); fresh('shot', 'A'); S.score = S.shown = 37; S.miss = 1; S.pose = 2;
      S.eggs = [{ ramp: 0, pos: 1 }, { ramp: 3, pos: 3 }, { ramp: 2, pos: 4 }]; S.broken = [{ ramp: 1, t: .8 }];
    }
    window.__basket = { get S() { return S; }, step: () => step(g), start: (m) => { if (g.screenOn) g.hideScreen(); startGame(g, m || 'A'); } };
  },
  update, draw
});
})();
