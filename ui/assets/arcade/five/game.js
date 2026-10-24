/* Пять в ряд (гомоку) против Лиры (24.10: идея людей — «5 в линию»; владелец: «сделать что-то для нас на её основе»).
   Доска 13×13 в мягком неоморфизме, камни — глянцевые чёрные (ваши) и перламутровые (Лира). Кто первым выстроит пять
   подряд — по горизонтали, вертикали или диагонали — тот и выиграл. Лира оценивает каждую точку рядом с камнями: свои
   «четвёрки» и «тройки» и ваши угрозы (на «полегче» — реже защищается). «↶ Ход назад» — отменить свой ход и ответ Лиры.
   Широкое окно — доска слева, счёт и кнопки справа; узкое (телефон) — сверху вниз. Рекорд — побед подряд. */
(() => {
'use strict';
const A = Arcade;
const LAND = (() => { try { return innerWidth > (innerHeight - 110) * 1.15; } catch (e) { return false; } })();
const W = LAND ? 1280 : 720, H = LAND ? 720 : 1280, N = 13;
const BG = '#e9ebef', DARK = '#c3c7cf', LIGHT = '#ffffff', INK = '#1d1f24', MUTED = 'rgba(29,31,36,.5)';
const L = LAND ? { bx: 74, by: 58, sz: 604, title: [990, 104], cards: [[740, 168], [990, 168]], undo: [740, 560, 230, 74], again: [990, 560, 230, 74], say: [990, 470] }
  : { bx: 50, by: 318, sz: 620, title: [360, 104], cards: [[80, 168], [380, 168]], undo: [60, 1012, 290, 82], again: [370, 1012, 290, 82], say: [360, 1160] };
const BX = L.bx, BY = L.by, SZ = L.sz, CELL = SZ / N;
const ME = 1, AI = 2, DIRS = [[1, 0], [0, 1], [1, 1], [1, -1]];
let S = null, SC = 1, streak = 0;

function fresh(mode, easy) {
  S = { mode, easy, b: Array.from({ length: N }, () => Array(N).fill(0)), turn: ME, hist: [], think: 0, end: 0, win: null, place: null, say: '', sayT: 0, demo: 0, hover: null };
  return S;
}
const inside = (x, y) => x >= 0 && y >= 0 && x < N && y < N;
/* линия через (x, y) для игрока p: длина и сколько концов открыто */
function run(b, x, y, dx, dy, p) {
  let c = 1, open = 0, cx = x + dx, cy = y + dy;
  while (inside(cx, cy) && b[cy][cx] === p) { c++; cx += dx; cy += dy; }
  if (inside(cx, cy) && !b[cy][cx]) open++;
  cx = x - dx; cy = y - dy;
  while (inside(cx, cy) && b[cy][cx] === p) { c++; cx -= dx; cy -= dy; }
  if (inside(cx, cy) && !b[cy][cx]) open++;
  return [c, open];
}
function shape(c, open) {
  if (c >= 5) return 1e6;
  if (c === 4) return open === 2 ? 6e4 : open === 1 ? 6e3 : 0;
  if (c === 3) return open === 2 ? 2500 : open === 1 ? 250 : 0;
  if (c === 2) return open === 2 ? 120 : open === 1 ? 18 : 0;
  return open === 2 ? 5 : 1;
}
function worth(b, x, y, p) { let s = 0; for (const [dx, dy] of DIRS) s += shape(...run(b, x, y, dx, dy, p)); return s; }
function fiveAt(b, x, y) {
  const p = b[y][x];
  for (const [dx, dy] of DIRS) {
    const cells = [[x, y]];
    let cx = x + dx, cy = y + dy; while (inside(cx, cy) && b[cy][cx] === p) { cells.push([cx, cy]); cx += dx; cy += dy; }
    cx = x - dx; cy = y - dy; while (inside(cx, cy) && b[cy][cx] === p) { cells.unshift([cx, cy]); cx -= dx; cy -= dy; }
    if (cells.length >= 5) return cells;
  }
  return null;
}
function aiPick() {
  const b = S.b, cand = [];
  if (!S.hist.length) return [N >> 1, N >> 1];
  for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) {
    if (b[y][x]) continue;
    let near = false;
    for (let dy = -2; dy <= 2 && !near; dy++) for (let dx = -2; dx <= 2; dx++) if (inside(x + dx, y + dy) && b[y + dy][x + dx]) { near = true; break; }
    if (!near) continue;
    const att = worth(b, x, y, AI), def = worth(b, x, y, ME);
    cand.push({ x, y, v: att * 1.15 + def * (S.easy ? .55 : 1) + Math.random() * 3 });
  }
  cand.sort((a, c) => c.v - a.v);
  const pick = S.easy && cand.length > 3 && Math.random() < .35 && cand[0].v < 5e4 ? cand[1 + ((Math.random() * 3) | 0)] : cand[0];
  return pick ? [pick.x, pick.y] : null;
}
const SAY = {
  block: ['Тут я поставлю заслон.', 'Э, нет — сюда не пущу!', 'Вижу вашу четвёрку!'], threat: ['Ой, у меня что-то вырисовывается…', 'Смотрите внимательнее!'],
  think: ['Так-так…', 'Хм…', 'Секунду…'], start: ['Ваш ход! Я играю белыми.', 'Начинайте — центр свободен.'], easy: ['Сыграем спокойно. Ваш ход!']
};
function say(kind) { S.say = A.pick(SAY[kind]); S.sayT = 2.4; }
function put(g, x, y, p) {
  S.b[y][x] = p; S.hist.push([x, y, p]); S.place = { x, y, t: 0 };
  if (S.mode === 'play') g.sfx('pling', { pitch: p === ME ? 1 : .8, vol: .7 });
  const f = fiveAt(S.b, x, y);
  if (f) { S.win = { p, cells: f, t: 0 }; S.end = .001; return; }
  if (S.hist.length >= N * N) { S.end = .001; return; }
  S.turn = 3 - p; S.think = 0;
}
function undo(g) {
  if (S.turn !== ME || S.end || !S.hist.length) return;
  const pop = () => { const [x, y] = S.hist.pop(); S.b[y][x] = 0; };
  if (S.hist[S.hist.length - 1][2] === AI) pop();                 // ответ Лиры
  if (S.hist.length && S.hist[S.hist.length - 1][2] === ME) pop(); // и свой ход
  S.turn = ME; g.sfx('click', { vol: .4 }); S.say = 'Отменили — ходите снова.'; S.sayT = 1.6;
}

/* ---------------- экраны ---------------- */
function titleScreen(g) {
  fresh('title', false); g.setPlaying(false);
  g.screen({
    kicker: A.framed ? 'Досуг' : 'Аркада', title: 'Пять в ряд',
    html: `<p>Вы — чёрные, Лира — белые. Ставьте камни по очереди: кто первым выстроит пять подряд — по горизонтали, вертикали или диагонали, — тот выиграл.</p>${g.best ? `<p class="record">Побед подряд: ${g.best}</p>` : ''}`,
    button: 'Играть', onGo: () => start(g, false), alt: { label: 'Полегче', onGo: () => start(g, true) }
  });
}
function start(g, easy) { fresh('play', easy); g.fx.clear(); g.setPlaying(true); g.playMusic(); say(easy ? 'easy' : 'start'); }
function finish(g) {
  S.mode = 'over'; g.setPlaying(false); g.stopMusic();
  const won = S.win && S.win.p === ME, draw = !S.win;
  streak = won ? streak + 1 : 0; const rec = won && g.submit(streak);
  g.sfx(won ? 'win' : draw ? 'power' : 'lose');
  if (won) for (let k = 0; k < 5; k++) g.fx.burst(BX + Math.random() * SZ, BY + Math.random() * SZ, { n: 10, colors: ['#1d1f24', '#ffffff', '#9aa0aa', '#ffd27a'], speed: 300, size: 8, life: .9, gravity: 500, shape: 'star' });
  g.screen({
    kicker: won ? `Побед подряд: ${streak}` : draw ? 'Доска заполнена' : 'Пять у Лиры', title: won ? (rec ? 'Новый рекорд!' : 'Победа!') : draw ? 'Ничья' : 'Лира выиграла',
    html: won ? `<p>${S.easy ? 'На «полегче». Попробуйте в полную силу!' : 'Пять в ряд — красиво!'}</p>` : `<p>${draw ? 'Ни у кого пяти — редкая партия.' : 'Следите за её «тройками» с открытыми концами — их надо закрывать сразу.'}</p>`,
    button: 'Ещё партию', onGo: () => start(g, S.easy), alt: { label: S.easy ? 'В полную силу' : 'Полегче', onGo: () => start(g, !S.easy) }
  });
}

/* ---------------- цикл ---------------- */
const hit = (r, x, y) => x >= r[0] && x <= r[0] + r[2] && y >= r[1] && y <= r[1] + r[3];
function cellAt(px, py) { const x = Math.round((px - BX - CELL / 2) / CELL), y = Math.round((py - BY - CELL / 2) / CELL); return inside(x, y) ? [x, y] : null; }
function update(g, dt) {
  if (S.place) { S.place.t += dt; if (S.place.t > .4) S.place = null; }
  if (S.win) S.win.t += dt;
  if (S.sayT > 0) S.sayT -= dt;
  if (S.mode === 'over') return;
  if (S.end) { S.end += dt; if (S.end > 1.4) { if (S.mode === 'title') fresh('title', false); else finish(g); } return; }
  if (S.mode === 'title') { S.demo += dt; if (S.demo > .5) { S.demo = 0; const m = aiPick(); if (m) { const p = S.turn; put(g, m[0], m[1], p); S.turn = 3 - p; } } return; }
  if (S.turn === AI) {
    S.think += dt;
    if (S.think > .3 && S.think - dt <= .3 && Math.random() < .2) say('think');
    if (S.think > .65) {
      const m = aiPick();
      if (m) {
        const block = worth(S.b, m[0], m[1], ME) >= 2500 && worth(S.b, m[0], m[1], AI) < 2500;
        put(g, m[0], m[1], AI);
        if (!S.end) { if (block && Math.random() < .6) say('block'); else if (worth(S.b, m[0], m[1], AI) >= 6e3 && Math.random() < .6) say('threat'); }
      }
    }
    return;
  }
  const inp = g.input, p = inp.pointer;
  S.hover = p.type === 'mouse' ? cellAt(p.x, p.y) : null;
  if (inp.tap) {
    const { x, y } = inp.tap;
    if (hit(L.undo, x, y)) return undo(g);
    if (hit(L.again, x, y)) { g.sfx('click', { vol: .4 }); return start(g, S.easy); }
    const c = cellAt(x, y);
    if (c && !S.b[c[1]][c[0]]) put(g, c[0], c[1], ME); else if (c) g.sfx('click', { vol: .3 });
  }
}

function stone(ctx, x, y, r, who, alpha = 1) {
  ctx.save(); ctx.globalAlpha = alpha; ctx.translate(x, y);
  ctx.shadowColor = 'rgba(0,0,0,.28)'; ctx.shadowBlur = 8 * SC; ctx.shadowOffsetX = 2 * SC; ctx.shadowOffsetY = 4 * SC;
  const gr = ctx.createRadialGradient(-r * .35, -r * .4, r * .1, 0, 0, r);
  if (who === ME) { gr.addColorStop(0, '#5a5e68'); gr.addColorStop(.45, '#26282e'); gr.addColorStop(1, '#0d0e11'); }
  else { gr.addColorStop(0, '#ffffff'); gr.addColorStop(.55, '#f1f2f5'); gr.addColorStop(1, '#c9ccd3'); }
  ctx.beginPath(); ctx.arc(0, 0, r, 0, Math.PI * 2); ctx.fillStyle = gr; ctx.fill();
  ctx.shadowColor = 'transparent';
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
function button(ctx, r, label, on) {
  soft(ctx, r[0], r[1], r[2], r[3], 24, on ? 7 : 3, false);
  A.text(ctx, label, r[0] + r[2] / 2, r[1] + r[3] / 2 + 2, { size: 24, weight: 700, color: on ? INK : 'rgba(29,31,36,.35)' });
}
function draw(ctx, g) {
  SC = g.scale;
  ctx.fillStyle = BG; ctx.fillRect(0, 0, W, H);
  A.text(ctx, 'Пять в ряд', L.title[0], L.title[1], { size: 58, weight: 900, color: INK });
  const cnt = (p) => S.hist.filter((h) => h[2] === p).length;
  for (const [i, who, name] of [[0, ME, 'Вы'], [1, AI, 'Лира']]) {
    const [x, y] = L.cards[i], on = S.turn === who && S.mode === 'play' && !S.end;
    soft(ctx, x, y, 230, 104, 30, on ? 9 : 5, false);
    if (on) { A.rr(ctx, x + 2, y + 2, 226, 100, 28); ctx.lineWidth = 3; ctx.strokeStyle = 'rgba(29,31,36,.35)'; ctx.stroke(); }
    stone(ctx, x + 52, y + 52, 24, who);
    A.text(ctx, name, x + 142, y + 42, { size: 30, weight: 800, color: INK });
    A.text(ctx, on ? (who === AI ? 'думает…' : 'ваш ход') : 'камней ' + cnt(who), x + 142, y + 78, { size: 18, weight: 600, color: MUTED });
  }
  if (LAND) {
    soft(ctx, 740, 300, 480, 120, 30, 4, true);
    A.text(ctx, 'Пять своих подряд —', 980, 342, { size: 24, weight: 700, color: INK });
    A.text(ctx, 'в любую сторону, даже наискосок', 980, 378, { size: 20, weight: 600, color: MUTED });
  }
  // доска
  soft(ctx, BX - 18, BY - 18, SZ + 36, SZ + 36, 40, 14, false);
  soft(ctx, BX, BY, SZ, SZ, 26, 10, true);
  const c0 = BX + CELL / 2, c1 = BX + SZ - CELL / 2, r0 = BY + CELL / 2, r1 = BY + SZ - CELL / 2;
  ctx.strokeStyle = 'rgba(29,31,36,.14)'; ctx.lineWidth = 2;
  for (let i = 0; i < N; i++) {
    ctx.beginPath(); ctx.moveTo(c0 + i * CELL, r0); ctx.lineTo(c0 + i * CELL, r1); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(c0, r0 + i * CELL); ctx.lineTo(c1, r0 + i * CELL); ctx.stroke();
  }
  for (const [dx, dy] of [[3, 3], [9, 3], [3, 9], [9, 9], [6, 6]]) { ctx.beginPath(); ctx.arc(c0 + dx * CELL, r0 + dy * CELL, 5, 0, Math.PI * 2); ctx.fillStyle = 'rgba(29,31,36,.28)'; ctx.fill(); }
  if (S.hover && S.mode === 'play' && S.turn === ME && !S.end && !S.b[S.hover[1]][S.hover[0]]) stone(ctx, c0 + S.hover[0] * CELL, r0 + S.hover[1] * CELL, CELL * .4, ME, .3);
  for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) {
    const v = S.b[y][x]; if (!v) continue;
    const pl = S.place && S.place.x === x && S.place.y === y ? A.ease.outBack(Math.min(1, S.place.t / .25)) : 1;
    stone(ctx, c0 + x * CELL, r0 + y * CELL, CELL * .42 * pl, v);
  }
  const last = S.hist[S.hist.length - 1];
  if (last && S.mode === 'play') { ctx.beginPath(); ctx.arc(c0 + last[0] * CELL, r0 + last[1] * CELL, 4.5, 0, Math.PI * 2); ctx.fillStyle = last[2] === ME ? 'rgba(255,255,255,.75)' : 'rgba(29,31,36,.55)'; ctx.fill(); }
  if (S.win) {                                   // пятёрка — светящейся линией
    const a = S.win.cells[0], b = S.win.cells[S.win.cells.length - 1], k = Math.min(1, S.win.t / .45);
    const x0 = c0 + a[0] * CELL, y0 = r0 + a[1] * CELL, x1 = c0 + b[0] * CELL, y1 = r0 + b[1] * CELL;
    ctx.save(); ctx.lineCap = 'round'; ctx.strokeStyle = S.win.p === ME ? 'rgba(255,196,90,.85)' : 'rgba(120,140,255,.85)'; ctx.lineWidth = 9;
    ctx.shadowColor = ctx.strokeStyle; ctx.shadowBlur = 18 * SC;
    ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x0 + (x1 - x0) * k, y0 + (y1 - y0) * k); ctx.stroke(); ctx.restore();
  }
  // кнопки
  if (S.mode !== 'title') { button(ctx, L.undo, '↶ Ход назад', S.turn === ME && !S.end && S.hist.length > 0); button(ctx, L.again, 'Новая партия', true); }
  // Лира говорит
  if (S.sayT > 0 && S.say) {
    const a = Math.min(1, S.sayT / .3); ctx.save(); ctx.globalAlpha = a;
    ctx.font = '600 24px ' + A.FONT; const w = ctx.measureText(S.say).width + 56, [sx, sy] = L.say;
    soft(ctx, sx - w / 2, sy - 34, w, 68, 34, 5, false);
    A.text(ctx, '«' + S.say + '»', sx, sy + 2, { size: 24, weight: 600, color: INK }); ctx.restore();
  }
}

A.game({
  id: 'five', tone: 'light', title: 'Пять в ряд', width: W, height: H, orientation: LAND ? 'landscape' : 'portrait', music: 'garden',
  keys: { KeyZ: 'none', Backspace: 'none' },
  help: { desktop: 'Щёлкните точку на доске — поставить камень · «↶ Ход назад» — отменить', short: 'Пять своих камней подряд', touch: 'Коснитесь точки на доске — поставить камень' },
  init(g) { titleScreen(g); window.__five = () => S; },
  update, draw
});
})();
