/* Реверси — чёрно-белая игра против Лиры (24.10, владелец: «какую-нибудь игру в чёрно-белом стиле или в нашем
   неоморфизме»). Доска — мягкий неоморфизм на жемчужно-сером, фишки — глянцевые чёрные (ваши) и перламутровые белые
   (Лира). Ход — поставить фишку так, чтобы зажать ряд фишек соперника: они переворачиваются. Нет хода — пропуск.
   Лира думает на 3 хода вперёд (на «полегче» — на один и иногда ошибается). Очки — фишки к концу, победа ×2. */
(() => {
'use strict';
const A = Arcade;
/* Широкое окно (лист «Досуг» на компьютере) — доска слева во всю высоту, справа название, счёт, слова Лиры и подсказка;
   узкое (телефон) — сверху вниз, как было. */
const LAND = (() => { try { return innerWidth > (innerHeight - 110) * 1.15; } catch (e) { return false; } })();
const W = LAND ? 1280 : 720, H = LAND ? 720 : 1280, N = 8;
const BG = '#e9ebef', DARK = '#c3c7cf', LIGHT = '#ffffff', INK = '#1d1f24', MUTED = 'rgba(29,31,36,.5)';
const BX = LAND ? 90 : 56, BY = LAND ? 60 : 330, SZ = LAND ? 600 : 608, CELL = SZ / N;
const L = LAND
  ? { title: [990, 104], cards: [[760, 168], [1000, 168]], cw: 220, disc: 50, num: 140, sub: 20, say: { x: 760, y: 356, w: 460, h: 96 }, sayT: 26, hintT: 22, tip: { x: 760, y: 536, w: 460, h: 124 } }
  : { title: [W / 2, 104], cards: [[W / 2 - 280, 168], [W / 2 + 20, 168]], cw: 260, disc: 56, num: 150, sub: 18, say: { x: 80, y: BY + SZ + 90, w: W - 160, h: 96 }, sayT: 28, hintT: 24, tip: null };
const DIRS = [[1, 0], [-1, 0], [0, 1], [0, -1], [1, 1], [1, -1], [-1, 1], [-1, -1]];
const WEIGHT = [
  [120, -20, 20, 5, 5, 20, -20, 120], [-20, -40, -5, -5, -5, -5, -40, -20], [20, -5, 15, 3, 3, 15, -5, 20], [5, -5, 3, 3, 3, 3, -5, 5],
  [5, -5, 3, 3, 3, 3, -5, 5], [20, -5, 15, 3, 3, 15, -5, 20], [-20, -40, -5, -5, -5, -5, -40, -20], [120, -20, 20, 5, 5, 20, -20, 120]];
const ME = 1, AI = 2;                     // 1 — чёрные (человек, ходит первым), 2 — белые (Лира)
let S = null, SC = 1;

function fresh(mode, easy) {
  const b = Array.from({ length: N }, () => Array(N).fill(0));
  b[3][3] = AI; b[4][4] = AI; b[3][4] = ME; b[4][3] = ME;
  S = { mode, easy, b, turn: ME, flip: {}, place: null, think: 0, pass: null, end: 0, last: null, say: '', sayT: 0, demo: 0 };
  return S;
}
function flips(b, x, y, p) {
  if (b[y][x]) return [];
  const o = 3 - p, out = [];
  for (const [dx, dy] of DIRS) {
    const run = []; let cx = x + dx, cy = y + dy;
    while (cx >= 0 && cy >= 0 && cx < N && cy < N && b[cy][cx] === o) { run.push([cx, cy]); cx += dx; cy += dy; }
    if (run.length && cx >= 0 && cy >= 0 && cx < N && cy < N && b[cy][cx] === p) out.push(...run);
  }
  return out;
}
function moves(b, p) { const m = []; for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) { const f = flips(b, x, y, p); if (f.length) m.push({ x, y, f }); } return m; }
const count = (b, p) => b.reduce((a, r) => a + r.filter((v) => v === p).length, 0);
function apply(b, m, p) { const nb = b.map((r) => r.slice()); nb[m.y][m.x] = p; for (const [x, y] of m.f) nb[y][x] = p; return nb; }
function evalB(b) {
  let s = 0;
  for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) if (b[y][x]) s += (b[y][x] === AI ? 1 : -1) * WEIGHT[y][x];
  return s + (moves(b, AI).length - moves(b, ME).length) * 8;
}
function minimax(b, depth, p, a, bb) {
  const ms = moves(b, p);
  if (!depth || (!ms.length && !moves(b, 3 - p).length)) {
    if (!ms.length && !moves(b, 3 - p).length) { const d = count(b, AI) - count(b, ME); return d * 1000; }
    return evalB(b);
  }
  if (!ms.length) return minimax(b, depth - 1, 3 - p, a, bb);
  if (p === AI) { let v = -Infinity; for (const m of ms) { v = Math.max(v, minimax(apply(b, m, p), depth - 1, ME, a, bb)); a = Math.max(a, v); if (a >= bb) break; } return v; }
  let v = Infinity; for (const m of ms) { v = Math.min(v, minimax(apply(b, m, p), depth - 1, AI, a, bb)); bb = Math.min(bb, v); if (a >= bb) break; } return v;
}
function aiPick(p) {
  const ms = moves(S.b, p); if (!ms.length) return null;
  if (S.easy && Math.random() < .3) return A.pick(ms);
  const depth = S.easy ? 1 : 3;
  let best = null, bv = -Infinity;
  for (const m of ms) {
    let v = p === AI ? minimax(apply(S.b, m, p), depth - 1, ME, -Infinity, Infinity) : -minimax(apply(S.b, m, p), depth - 1, AI, -Infinity, Infinity);
    v += Math.random() * 2;
    if (v > bv) { bv = v; best = m; }
  }
  return best;
}
const SAY = {
  corner: ['Угол мой!', 'Вот это ход.', 'Красиво, правда?'], good: ['Хм, интересно…', 'Неплохо!', 'Ой, ловко.'],
  pass: ['Мне некуда — хожу пропуском.', 'Пропускаю ход.'], youpass: ['Вам некуда ходить — пропуск.'], think: ['Так-так…', 'Думаю…', 'Секунду…']
};
function say(kind) { S.say = A.pick(SAY[kind]); S.sayT = 2.2; }
function play(g, m, p) {
  S.b[m.y][m.x] = p; S.place = { x: m.x, y: m.y, t: 0 }; S.last = { x: m.x, y: m.y };
  m.f.forEach(([x, y], i) => { S.b[y][x] = p; S.flip[y * N + x] = { t: -i * .05, to: p }; });
  if (S.mode === 'play') {
    g.sfx('pling', { pitch: p === ME ? 1 : .8, vol: .7 });
    if (m.f.length >= 5) g.sfx('coin');
    if (p === AI && (m.x % 7 === 0) && (m.y % 7 === 0)) say('corner');
    else if (p === ME && m.f.length >= 5) say('good');
    const cx = BX + (m.x + .5) * CELL, cy = BY + (m.y + .5) * CELL;
    g.fx.ring(cx, cy, { r1: 60, color: p === ME ? '#1d1f24' : '#ffffff', width: 4, life: .35 });
  }
  S.turn = 3 - p; S.think = 0;
  nextTurn(g);
}
function nextTurn(g) {
  const can = moves(S.b, S.turn).length, other = moves(S.b, 3 - S.turn).length;
  if (!can && !other) { S.end = .001; return; }
  if (!can) { if (S.mode === 'play') say(S.turn === AI ? 'pass' : 'youpass'); S.turn = 3 - S.turn; }
}

/* ---------------- экраны ---------------- */
function titleScreen(g) {
  fresh('title', false); g.setPlaying(false);
  g.screen({
    kicker: A.framed ? 'Досуг' : 'Аркада', title: 'Реверси',
    html: `<p>Вы — чёрные, Лира — белые. Ставьте фишку так, чтобы зажать ряд белых: они станут вашими. Углы — самые ценные.</p>${g.best ? `<p class="record">Рекорд: ${g.best.toLocaleString('ru-RU')}</p>` : ''}`,
    button: 'Играть', onGo: () => start(g, false), alt: { label: 'Полегче', onGo: () => start(g, true) }
  });
}
function start(g, easy) { fresh('play', easy); g.fx.clear(); g.setPlaying(true); g.playMusic(); S.say = easy ? 'Сыграем спокойно. Ваш ход!' : 'Ваш ход! Я играю белыми.'; S.sayT = 2.5; }
function finish(g) {
  S.mode = 'over'; g.setPlaying(false); g.stopMusic();
  const me = count(S.b, ME), ai = count(S.b, AI), win = me > ai;
  g.sfx(win ? 'win' : me === ai ? 'power' : 'lose');
  const sc = me * 100 * (win ? 2 : 1) * (S.easy ? 1 : 2);
  const rec = win && g.submit(sc);
  if (win) for (let k = 0; k < 5; k++) g.fx.burst(BX + Math.random() * SZ, BY + Math.random() * SZ, { n: 10, colors: ['#1d1f24', '#ffffff', '#9aa0aa'], speed: 300, size: 8, life: .9, gravity: 500, shape: 'star' });
  g.screen({
    kicker: `Вы ${me} : ${ai} Лира`, title: win ? (rec ? 'Новый рекорд!' : 'Победа!') : me === ai ? 'Ничья' : 'Лира выиграла',
    html: win ? `<div class="score">${sc.toLocaleString('ru-RU')}</div><p>${S.easy ? 'На «полегче». Попробуйте в полную силу!' : 'В полную силу — так держать!'}</p>` : `<p>${me === ai ? 'Поровну — красиво!' : 'Ещё партию? Возьмите углы — они не переворачиваются.'}</p>`,
    button: 'Ещё партию', onGo: () => start(g, S.easy), alt: { label: S.easy ? 'В полную силу' : 'Полегче', onGo: () => start(g, !S.easy) }
  });
}

/* ---------------- цикл ---------------- */
function update(g, dt) {
  for (const k in S.flip) { S.flip[k].t += dt / .32; if (S.flip[k].t >= 1) delete S.flip[k]; }
  if (S.place) { S.place.t += dt; if (S.place.t > .4) S.place = null; }
  if (S.sayT > 0) S.sayT -= dt;
  if (S.mode === 'over') return;
  if (S.end) { S.end += dt; if (S.end > .9) { if (S.mode === 'title') fresh('title', false); else finish(g); } return; }
  if (S.mode === 'title') { S.demo += dt; if (S.demo > .7) { S.demo = 0; const m = aiPick(S.turn); if (m) play(g, m, S.turn); else nextTurn(g); } return; }
  if (S.turn === AI) {
    S.think += dt;
    if (S.think > .25 && S.think - dt <= .25 && Math.random() < .25) say('think');
    if (S.think > .7) { const m = aiPick(AI); if (m) play(g, m, AI); }
    return;
  }
  const inp = g.input;
  if (inp.tap) {
    const x = Math.floor((inp.tap.x - BX) / CELL), y = Math.floor((inp.tap.y - BY) / CELL);
    if (x >= 0 && y >= 0 && x < N && y < N) {
      const f = flips(S.b, x, y, ME);
      if (f.length) play(g, { x, y, f }, ME); else g.sfx('click', { vol: .4 });
    }
  }
}

function disc(ctx, x, y, r, who, sx = 1) {
  ctx.save(); ctx.translate(x, y); ctx.scale(Math.max(.04, Math.abs(sx)), 1);
  ctx.shadowColor = 'rgba(0,0,0,.28)'; ctx.shadowBlur = 10 * SC; ctx.shadowOffsetX = 3 * SC; ctx.shadowOffsetY = 5 * SC;
  const gr = ctx.createRadialGradient(-r * .35, -r * .4, r * .1, 0, 0, r);
  if (who === ME) { gr.addColorStop(0, '#5a5e68'); gr.addColorStop(.45, '#26282e'); gr.addColorStop(1, '#0d0e11'); }
  else { gr.addColorStop(0, '#ffffff'); gr.addColorStop(.55, '#f1f2f5'); gr.addColorStop(1, '#c9ccd3'); }
  ctx.beginPath(); ctx.arc(0, 0, r, 0, Math.PI * 2); ctx.fillStyle = gr; ctx.fill();
  ctx.shadowColor = 'transparent';
  ctx.beginPath(); ctx.arc(0, 0, r * .72, 0, Math.PI * 2); ctx.lineWidth = 2; ctx.strokeStyle = who === ME ? 'rgba(255,255,255,.08)' : 'rgba(0,0,0,.06)'; ctx.stroke();
  ctx.beginPath(); ctx.ellipse(-r * .32, -r * .42, r * .3, r * .14, -.5, 0, Math.PI * 2); ctx.fillStyle = who === ME ? 'rgba(255,255,255,.25)' : 'rgba(255,255,255,.9)'; ctx.fill();
  ctx.restore();
}
function soft(ctx, x, y, w, h, r, d0, inset) {
  const d = d0 * SC; ctx.save();
  if (!inset) {
    ctx.shadowColor = DARK; ctx.shadowBlur = d * 1.8; ctx.shadowOffsetX = d * .7; ctx.shadowOffsetY = d * .7;
    A.rr(ctx, x, y, w, h, r); ctx.fillStyle = BG; ctx.fill();
    ctx.shadowColor = LIGHT; ctx.shadowOffsetX = -d * .7; ctx.shadowOffsetY = -d * .7; ctx.fill();
  } else {
    A.rr(ctx, x, y, w, h, r); ctx.fillStyle = '#e1e4e9'; ctx.fill(); ctx.clip();
    ctx.shadowColor = DARK; ctx.shadowBlur = d * 1.4; ctx.shadowOffsetX = d * .5; ctx.shadowOffsetY = d * .5;
    ctx.lineWidth = d0; ctx.strokeStyle = '#e1e4e9'; A.rr(ctx, x - d0 / 2, y - d0 / 2, w + d0, h + d0, r + d0 / 2); ctx.stroke();
    ctx.shadowColor = LIGHT; ctx.shadowOffsetX = -d * .5; ctx.shadowOffsetY = -d * .5; ctx.stroke();
  }
  ctx.restore();
}
function draw(ctx, g) {
  SC = g.scale;
  const t = g.t;
  ctx.fillStyle = BG; ctx.fillRect(0, 0, W, H);
  A.text(ctx, 'Реверси', L.title[0], L.title[1], { size: 62, weight: 900, color: INK });
  // счёт: вы и Лира
  const me = count(S.b, ME), ai = count(S.b, AI);
  for (const [i, who, name, n] of [[0, ME, 'Вы', me], [1, AI, 'Лира', ai]]) {
    const [x, y] = L.cards[i], cw = L.cw, on = S.turn === who && S.mode === 'play' && !S.end;
    soft(ctx, x, y, cw, 104, 30, on ? 9 : 5, false);
    if (on) { A.rr(ctx, x + 2, y + 2, cw - 4, 100, 28); ctx.lineWidth = 3; ctx.strokeStyle = 'rgba(29,31,36,.35)'; ctx.stroke(); }
    disc(ctx, x + L.disc, y + 52, 26, who);
    A.text(ctx, String(n), x + L.num, y + 46, { size: 44, weight: 900, color: INK });
    A.text(ctx, name + (on && !LAND ? (who === AI ? ' · думает' : ' · ваш ход') : ''), x + L.num, y + 82, { size: L.sub, weight: 600, color: MUTED });
  }
  if (L.tip) {                                   // широкое окно: памятка под счётом
    const r = L.tip;
    soft(ctx, r.x, r.y, r.w, r.h, 30, 4, true);
    A.text(ctx, 'Углы — самые ценные', r.x + r.w / 2, r.y + 46, { size: 26, weight: 700, color: INK });
    A.text(ctx, 'фишку в углу уже не перевернуть', r.x + r.w / 2, r.y + 84, { size: 21, weight: 600, color: MUTED });
  }
  // доска
  soft(ctx, BX - 18, BY - 18, SZ + 36, SZ + 36, 44, 14, false);
  soft(ctx, BX, BY, SZ, SZ, 30, 10, true);
  ctx.strokeStyle = 'rgba(29,31,36,.1)'; ctx.lineWidth = 2;
  for (let i = 1; i < N; i++) {
    ctx.beginPath(); ctx.moveTo(BX + i * CELL, BY + 10); ctx.lineTo(BX + i * CELL, BY + SZ - 10); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(BX + 10, BY + i * CELL); ctx.lineTo(BX + SZ - 10, BY + i * CELL); ctx.stroke();
  }
  for (const [dx, dy] of [[2, 2], [6, 2], [2, 6], [6, 6]]) { ctx.beginPath(); ctx.arc(BX + dx * CELL, BY + dy * CELL, 5, 0, Math.PI * 2); ctx.fillStyle = 'rgba(29,31,36,.25)'; ctx.fill(); }
  // подсказки ходов
  if (S.mode === 'play' && S.turn === ME && !S.end) {
    for (const m of moves(S.b, ME)) { ctx.beginPath(); ctx.arc(BX + (m.x + .5) * CELL, BY + (m.y + .5) * CELL, 8 + Math.sin(t * 4) * 1.5, 0, Math.PI * 2); ctx.fillStyle = 'rgba(29,31,36,.18)'; ctx.fill(); }
  }
  for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) {
    const v = S.b[y][x]; if (!v) continue;
    const f = S.flip[y * N + x], cx = BX + (x + .5) * CELL, cy = BY + (y + .5) * CELL;
    let who = v, sx = 1;
    if (f) { const k = A.clamp(f.t, 0, 1); sx = Math.cos(k * Math.PI); who = k < .5 ? 3 - f.to : f.to; }
    const pl = S.place && S.place.x === x && S.place.y === y ? A.ease.outBack(Math.min(1, S.place.t / .25)) : 1;
    disc(ctx, cx, cy - (f ? Math.sin(A.clamp(f.t, 0, 1) * Math.PI) * 10 : 0), CELL * .38 * pl, who, sx);
  }
  if (S.last && S.mode === 'play') { ctx.beginPath(); ctx.arc(BX + (S.last.x + .5) * CELL, BY + (S.last.y + .5) * CELL, 5, 0, Math.PI * 2); ctx.fillStyle = S.b[S.last.y][S.last.x] === ME ? 'rgba(255,255,255,.7)' : 'rgba(29,31,36,.5)'; ctx.fill(); }
  // Лира говорит — облачко внизу
  const sb = L.say, by = sb.y, bx = sb.x + sb.w / 2;
  if (S.sayT > 0 && S.say) {
    const a = Math.min(1, S.sayT / .3, (2.4 - S.sayT) / .2);
    ctx.save(); ctx.globalAlpha = Math.max(0, a);
    soft(ctx, sb.x, by, sb.w, sb.h, 34, 7, false);
    A.text(ctx, S.say, bx, by + 50, { size: L.sayT, weight: 600, color: INK });
    ctx.restore();
  } else if (S.mode === 'play') A.text(ctx, S.turn === ME ? 'Точки — куда можно поставить фишку' : 'Лира думает…', bx, by + 50, { size: L.hintT, weight: 500, color: MUTED });
}

A.game({
  id: 'reversi', tone: 'light', title: 'Реверси', width: W, height: H, orientation: LAND ? 'landscape' : 'portrait', music: 'garden',
  help: { desktop: 'Щелчок по клетке с точкой — поставить фишку · <kbd>P</kbd> пауза · <kbd>M</kbd> музыка', short: 'Щелчок по клетке с точкой', touch: 'Коснитесь клетки с точкой — там можно ходить' },
  init(g) { titleScreen(g); window.__reversi = () => S; },
  update, draw
});
})();
