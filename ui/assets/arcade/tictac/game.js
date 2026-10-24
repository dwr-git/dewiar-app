/* Крестики-нолики на тетрадном листе (24.10, владелец: «где рисуешь крестик или нолик пальцами»).
   Нарисуйте в клетке крестик или нолик — пальцем или мышью; ваш рисунок и остаётся на листе. Первый знак раунда
   решает, кем вы играете (замкнутая петля — нолик, иначе крестик), Лира отвечает другим знаком — карандашом.
   Можно и просто коснуться клетки (знак нарисуется сам) или ходить стрелками и Enter. */
(() => {
'use strict';
const A = Arcade;
/* Широкое окно (лист «Досуг» на компьютере) — лист в клетку на всю ширину: поле 3×3 слева во всю высоту (линии поля
   легли на клетки тетради), справа название, счёт, подсказки и памятка «крестик — две черты, нолик — петля».
   Рисунок пальцем/мышью распознаётся по тем же BX/BY/CELL. Узкое (телефон) — как было. */
const LAND = (() => { try { return innerWidth > (innerHeight - 110) * 1.15; } catch (e) { return false; } })();
const W = LAND ? 1280 : 720, H = LAND ? 720 : 1280;
const PAPER = '#fbf9f2', LINE = 'rgba(80,130,210,.16)', MARGIN = 'rgba(226,90,110,.45)';
const PEN = '#2848b0', PENCIL = '#7a52c9', INK = '#283055';
const BX = LAND ? 110 : 90, BY = LAND ? 60 : 360, CELL = LAND ? 200 : 180;
const COL = 770, COL_W = 420;                 // правая колонка широкой раскладки (до красной черты полей)
const LINES = [[0, 1, 2], [3, 4, 5], [6, 7, 8], [0, 3, 6], [1, 4, 7], [2, 5, 8], [0, 4, 8], [2, 4, 6]];
const rnd = (a, b) => a + Math.random() * (b - a);
let S = null, T = { you: 0, lira: 0, draw: 0, streak: 0, sym: '', round: 0 };
let MINI = null;                              // наброски для памятки (только широкая раскладка — не трогаем случайность книжной)

/* ---------------- рисованные штрихи ---------------- */
function wobble(x1, y1, x2, y2, n, amp) {
  const pts = [], nx = -(y2 - y1), ny = x2 - x1, l = Math.hypot(nx, ny) || 1, bow = rnd(-amp, amp) * 1.5;
  for (let i = 0; i <= n; i++) {
    const t = i / n, j = (i && i < n ? rnd(-amp, amp) * .5 : 0) + Math.sin(t * Math.PI) * bow;
    pts.push([x1 + (x2 - x1) * t + nx / l * j, y1 + (y2 - y1) * t + ny / l * j]);
  }
  return pts;
}
function handX() {   // в долях клетки
  const a = rnd(-.04, .04);
  return [wobble(.24 + a, .22, .78, .8 + a, 7, .02), wobble(.78 - a, .2, .23, .78 - a, 7, .02)];
}
function handO() {
  const pts = [], a0 = rnd(0, 6.28), sw = Math.PI * 2 + rnd(.25, .5), rx = rnd(.27, .31), ry = rnd(.26, .3);
  for (let i = 0; i <= 30; i++) { const t = i / 30, a = a0 - sw * t, r = 1 + Math.sin(t * 9 + a0) * .03 + t * .04; pts.push([.5 + Math.cos(a) * rx * r, .5 + Math.sin(a) * ry * r]); }
  return [pts];
}
function strokeLen(p) { let s = 0; for (let i = 1; i < p.length; i++) s += Math.hypot(p[i][0] - p[i - 1][0], p[i][1] - p[i - 1][1]); return s; }
function closedLoop(st) {
  if (st.length !== 1) return false;
  const p = st[0]; if (p.length < 6) return false;
  const xs = p.map((q) => q[0]), ys = p.map((q) => q[1]);
  const size = Math.max(Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys));
  const gap = Math.hypot(p[0][0] - p[p.length - 1][0], p[0][1] - p[p.length - 1][1]);
  let turn = 0; for (let i = 2; i < p.length; i++) {
    const a1 = Math.atan2(p[i - 1][1] - p[i - 2][1], p[i - 1][0] - p[i - 2][0]), a2 = Math.atan2(p[i][1] - p[i - 1][1], p[i][0] - p[i - 1][0]);
    let d = a2 - a1; while (d > Math.PI) d -= 2 * Math.PI; while (d < -Math.PI) d += 2 * Math.PI; turn += d;
  }
  return gap < size * .5 || Math.abs(turn) > 4.6;
}
function drawStroke(ctx, pts, color, w, prog = 1, ox = 0, oy = 0, sc = 1) {
  if (pts.length < 2) return;
  const total = strokeLen(pts) * prog; let acc = 0;
  ctx.strokeStyle = color; ctx.lineWidth = w; ctx.lineCap = 'round'; ctx.lineJoin = 'round';
  ctx.beginPath(); ctx.moveTo(ox + pts[0][0] * sc, oy + pts[0][1] * sc);
  for (let i = 1; i < pts.length; i++) {
    const d = Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]);
    if (acc + d >= total) { const k = d ? (total - acc) / d : 0; ctx.lineTo(ox + (pts[i - 1][0] + (pts[i][0] - pts[i - 1][0]) * k) * sc, oy + (pts[i - 1][1] + (pts[i][1] - pts[i - 1][1]) * k) * sc); break; }
    acc += d; ctx.lineTo(ox + pts[i][0] * sc, oy + pts[i][1] * sc);
  }
  ctx.stroke();
}
function inkStrokes(ctx, strokes, color, w, prog, ox, oy, sc) {
  // перо — две проводки: основная и тонкая светлее, как шариковая ручка / карандаш
  const lens = strokes.map(strokeLen), all = lens.reduce((a, b) => a + b, 0) || 1; let left = prog * all;
  strokes.forEach((p, i) => {
    const pr = Math.max(0, Math.min(1, left / (lens[i] || 1))); left -= lens[i];
    if (pr <= 0) return;
    ctx.globalAlpha = .9; drawStroke(ctx, p, color, w, pr, ox, oy, sc);
    ctx.globalAlpha = .35; drawStroke(ctx, p, color, w * .45, pr, ox + 1.5, oy - 1, sc);
    ctx.globalAlpha = 1;
  });
}

/* ---------------- раунд ---------------- */
function fresh(mode) {
  T.round++;
  const grid = [];
  for (let i = 1; i < 3; i++) {
    grid.push(wobble(BX + i * CELL + rnd(-4, 4), BY - 14, BX + i * CELL + rnd(-4, 4), BY + 3 * CELL + 10, 9, 4));
    grid.push(wobble(BX - 14, BY + i * CELL + rnd(-4, 4), BX + 3 * CELL + 12, BY + i * CELL + rnd(-4, 4), 9, 4));
  }
  const liraFirst = mode === 'play' && T.round % 2 === 0;
  S = { mode, cells: Array(9).fill(null), grid, gridT: mode === 'title' ? 1 : 0, turn: liraFirst ? 'l' : 'p', think: liraFirst ? .9 : 0, cur: 4, keyed: false,
    stroke: null, pend: null, pendT: 0, over: null, overT: 0, line: null, msg: liraFirst ? 'Лира начинает' : (T.sym ? 'Ваш ход' : 'Нарисуйте крестик или нолик'), demo: 0 };
  if (liraFirst && !T.sym) T.sym = 'o';
  return S;
}
const liraSym = () => (T.sym === 'o' ? 'x' : 'o');
function cellAt(x, y) {
  const cx = Math.floor((x - BX) / CELL), cy = Math.floor((y - BY) / CELL);
  return cx >= 0 && cy >= 0 && cx < 3 && cy < 3 ? cy * 3 + cx : -1;
}
function winner(c) {
  for (const l of LINES) { const [a, b, d] = l; if (c[a] && c[b] && c[d] && c[a].who === c[b].who && c[a].who === c[d].who) return { who: c[a].who, line: l }; }
  return c.every(Boolean) ? { who: 'draw' } : null;
}
function put(g, i, who, strokes, sym) {
  S.cells[i] = { who, sym, strokes, prog: who === 'p' && strokes.drawn ? 1 : 0 };
  if (who === 'p') { g.sfx('click', { vol: .35, pitch: .8 }); S.turn = 'l'; S.think = rnd(.55, .9); S.msg = 'Лира думает…'; }
  else { S.turn = 'p'; S.msg = 'Ваш ход'; }
  const w = winner(S.cells);
  if (w) { S.over = w; S.overT = 0; S.turn = ''; if (w.line) S.line = { a: w.line[0], b: w.line[2], pts: null, prog: 0 }; result(g, w); }
}
function result(g, w) {
  if (S.mode !== 'play') return;
  if (w.who === 'p') { T.you++; T.streak++; g.submit(T.streak); S.msg = T.streak > 1 ? 'Вы выиграли! Подряд: ' + T.streak : 'Вы выиграли!'; g.sfx('win'); }
  else if (w.who === 'l') { T.lira++; T.streak = 0; S.msg = 'Лира выиграла'; g.sfx('hurt', { vol: .35, pitch: .8 }); }
  else { T.draw++; S.msg = 'Ничья — как и положено мастерам'; g.sfx('pling'); }
}
function commitPlayer(g) {
  const p = S.pend; S.pend = null; if (!p || S.cells[p.i]) return;
  let st = p.strokes, sym;
  const tiny = st.reduce((a, s) => a + strokeLen(s), 0) < CELL * .25;
  const looks = tiny ? '' : closedLoop(st) ? 'o' : st.length >= 2 ? 'x' : '';
  if (!T.sym) T.sym = looks || 'x';
  else if (looks && looks !== T.sym) {          // нарисован чужой знак — стираем и подсказываем
    S.msg = T.sym === 'x' ? 'Вы играете крестиками' : 'Вы играете ноликами'; S.warn = 1.6; g.sfx('click', { vol: .3, pitch: .6 }); return;
  }
  sym = T.sym;
  if (tiny) st = sym === 'x' ? handX() : handO();
  else { st = st.map((s) => s.map(([x, y]) => [(x - BX - (p.i % 3) * CELL) / CELL, (y - BY - Math.floor(p.i / 3) * CELL) / CELL])); st.drawn = true; }
  put(g, p.i, 'p', st, sym);
}
function liraMove() {
  const c = S.cells, free = c.map((v, i) => (v ? -1 : i)).filter((i) => i >= 0);
  const wins = (who) => free.find((i) => LINES.some((l) => l.includes(i) && l.filter((k) => k !== i).every((k) => c[k] && c[k].who === who)));
  let m = wins('l');
  if (m == null && Math.random() < .86) m = wins('p');
  if (m == null && !c[4] && Math.random() < .75) m = 4;
  if (m == null) { const cor = [0, 2, 6, 8].filter((i) => !c[i]); if (cor.length && Math.random() < .6) m = A.pick(cor); }
  if (m == null) m = A.pick(free);
  return m;
}

/* ---------------- экраны ---------------- */
function titleScreen(g) {
  T.round = 0; fresh('title'); g.setPlaying(false);
  g.screen({
    kicker: A.framed ? 'Досуг' : 'Аркада', title: 'Крестики-нолики',
    html: '<p>Рисуйте крестики или нолики прямо пальцем или мышью — Лира отвечает карандашом. Первый знак решает, кем вы играете. Можно и просто коснуться клетки.</p>' + (g.best ? '<p class="record">Побед подряд: ' + g.best + '</p>' : ''),
    button: 'Играть', onGo: () => { T = { you: 0, lira: 0, draw: 0, streak: 0, sym: '', round: 0 }; fresh('play'); g.setPlaying(true); g.playMusic(); }
  });
}

/* ---------------- цикл ---------------- */
function update(g, dt) {
  S.gridT = Math.min(1, S.gridT + dt * 1.6);
  if (S.warn > 0 && (S.warn -= dt) <= 0 && S.turn === 'p') S.msg = 'Ваш ход';
  for (const c of S.cells) if (c && c.prog < 1) c.prog = Math.min(1, c.prog + dt * 1.9);
  if (S.line) S.line.prog = Math.min(1, S.line.prog + dt * 2.2);
  if (S.mode === 'title') {
    S.demo += dt;
    if (S.demo > .8) { S.demo = 0; if (S.over) { fresh('title'); return; }
      const free = S.cells.map((v, i) => (v ? -1 : i)).filter((i) => i >= 0), who = S.turn === 'p' ? 'p' : 'l', i = A.pick(free);
      put(g, i, who, who === 'p' ? handX() : handO(), who === 'p' ? 'x' : 'o'); }
    return;
  }
  const inp = g.input, p = inp.pointer;
  if (S.over) {
    S.overT += dt;
    if (S.overT > 1 && (inp.tap || p.justDown || inp.pressed('action') || inp.pressed('start'))) { fresh('play'); g.sfx('click', { vol: .3 }); }
    return;
  }
  // ход игрока: рисунок
  if (S.turn === 'p') {
    if (p.justDown) {
      const i = cellAt(p.x, p.y);
      if (S.pend && i !== S.pend.i) commitPlayer(g);
      else if (i >= 0 && !S.cells[i]) { if (!S.pend) S.pend = { i, strokes: [] }; S.stroke = [[p.x, p.y]]; S.keyed = false; }
    } else if (p.down && S.stroke) {
      const last = S.stroke[S.stroke.length - 1];
      if (Math.hypot(p.x - last[0], p.y - last[1]) > 2.5) S.stroke.push([p.x, p.y]);
    }
    if (S.stroke && (p.justUp || !p.down)) {
      S.stroke.push([p.x, p.y]); S.pend.strokes.push(S.stroke); S.stroke = null;
      const one = S.pend.strokes.length === 1, loop = one && closedLoop(S.pend.strokes);
      S.pendT = S.pend.strokes.length >= 2 || loop || (one && strokeLen(S.pend.strokes[0]) < CELL * .25) ? .18 : .6;   // ждём второй штрих крестика
    }
    if (S.pend && !S.stroke) { S.pendT -= dt; if (S.pendT <= 0) commitPlayer(g); }
    // клавиатура
    const mv = (dx, dy) => { const x = (S.cur % 3 + dx + 3) % 3, y = (Math.floor(S.cur / 3) + dy + 3) % 3; S.cur = y * 3 + x; S.keyed = true; g.sfx('click', { vol: .2 }); };
    if (inp.pressed('left')) mv(-1, 0); if (inp.pressed('right')) mv(1, 0); if (inp.pressed('up')) mv(0, -1); if (inp.pressed('down')) mv(0, 1);
    if ((inp.pressed('action') || inp.pressed('start')) && !S.cells[S.cur] && !S.pend) { S.keyed = true; S.pend = { i: S.cur, strokes: [] }; commitPlayer(g); }
  } else if (S.turn === 'l') {
    S.think -= dt;
    if (S.think <= 0) { const sym = liraSym(); put(g, liraMove(), 'l', sym === 'x' ? handX() : handO(), sym); g.sfx('click', { vol: .25, pitch: 1.4 }); }
  }
}

/* текст в несколько строк по ширине; возвращает y под последней строкой */
function wrapText(ctx, str, x, y, maxW, lh, o) {
  ctx.font = `${o.weight || 800} ${o.size}px ${A.FONT}`;
  const lines = []; let cur = '';
  for (const w of String(str).split(' ')) { const t = cur ? cur + ' ' + w : w; if (cur && ctx.measureText(t).width > maxW) { lines.push(cur); cur = w; } else cur = t; }
  if (cur) lines.push(cur);
  lines.forEach((l, i) => A.text(ctx, l, x, y + i * lh, o));
  return y + lines.length * lh;
}
function drawSide(ctx) {
  const x0 = COL, soft = 'rgba(40,48,85,.5)';
  A.text(ctx, 'Крестики-нолики', x0, 98, { align: 'left', size: 44, weight: 900, color: INK });
  if (S.mode === 'play') {
    A.text(ctx, 'Вы', x0 + 2, 178, { align: 'left', size: 30, weight: 700, color: PEN });
    A.text(ctx, T.you + ' : ' + T.lira, x0 + 100, 178, { size: 40, weight: 900, color: INK });
    A.text(ctx, 'Лира', x0 + 156, 178, { align: 'left', size: 30, weight: 700, color: PENCIL });
    if (T.draw) A.text(ctx, 'ничьих ' + T.draw, x0 + COL_W, 178, { align: 'right', size: 22, weight: 600, color: 'rgba(40,48,85,.45)' });
    const col = S.warn > 0 ? '#c2410c' : S.over ? (S.over.who === 'p' ? PEN : S.over.who === 'l' ? PENCIL : INK) : INK;
    const y1 = wrapText(ctx, S.msg, x0, 280, COL_W, 44, { align: 'left', size: 34, weight: 800, color: col });
    const sub = S.over ? (S.overT > 1 ? 'Коснитесь листа — новый раунд' : '') : S.turn === 'p' ? (T.sym ? 'Вы играете ' + (T.sym === 'x' ? 'крестиками' : 'ноликами') + ' · рисуйте или коснитесь клетки' : 'Рисуйте прямо в клетке — пальцем или мышью') : '';
    if (sub) wrapText(ctx, sub, x0, y1 + 6, COL_W, 32, { align: 'left', size: 22, weight: 600, color: soft });
  }
  // памятка: как рисовать знаки (а когда знак выбран — чей какой)
  if (!MINI) MINI = { x: handX(), o: handO() };
  const pick = S.mode === 'play' && T.sym;
  [['x', 'крестик', 'две черты'], ['o', 'нолик', 'петля']].forEach(([sym, name, how], k) => {
    const bx = x0 + k * 214, by = 556, mine = pick && T.sym === sym;
    inkStrokes(ctx, MINI[sym], pick ? (mine ? PEN : PENCIL) : INK, 6, 1, bx, by, 84);
    A.text(ctx, name, bx + 96, by + 30, { align: 'left', size: 26, weight: 800, color: pick ? (mine ? PEN : PENCIL) : INK });
    A.text(ctx, pick ? (mine ? 'это вы' : 'это Лира') : how, bx + 96, by + 62, { align: 'left', size: 21, weight: 600, color: soft });
  });
}
function draw(ctx, g) {
  ctx.fillStyle = PAPER; ctx.fillRect(0, 0, W, H);
  ctx.lineWidth = 2; ctx.strokeStyle = LINE; ctx.beginPath();
  for (let x = 30; x < W; x += 40) { ctx.moveTo(x, 0); ctx.lineTo(x, H); }
  for (let y = 20; y < H; y += 40) { ctx.moveTo(0, y); ctx.lineTo(W, y); }
  ctx.stroke();
  ctx.strokeStyle = MARGIN; ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(W - 70, 0); ctx.lineTo(W - 70, H); ctx.stroke();
  if (LAND) drawSide(ctx); else A.text(ctx, 'Крестики-нолики', 50, 112, { align: 'left', size: 50, weight: 900, color: INK });
  if (S.mode === 'play' && !LAND) {
    A.text(ctx, 'Вы', 52, 196, { align: 'left', size: 30, weight: 700, color: PEN });
    A.text(ctx, T.you + ' : ' + T.lira, 150, 196, { size: 40, weight: 900, color: INK });
    A.text(ctx, 'Лира', 206, 196, { align: 'left', size: 30, weight: 700, color: PENCIL });
    if (T.draw) A.text(ctx, 'ничьих ' + T.draw, 640, 196, { align: 'right', size: 24, weight: 600, color: 'rgba(40,48,85,.45)' });
  }
  // сетка — проводится рукой при каждом раунде
  S.grid.forEach((l, k) => inkStrokes(ctx, [l], INK, 6, Math.max(0, Math.min(1, S.gridT * 4 - k * .6)), 0, 0, 1));
  // курсор клавиатуры
  if (S.mode === 'play' && S.turn === 'p' && S.keyed && !S.over) {
    const x = BX + (S.cur % 3) * CELL, y = BY + Math.floor(S.cur / 3) * CELL;
    ctx.setLineDash([10, 9]); ctx.strokeStyle = 'rgba(40,72,176,.45)'; ctx.lineWidth = 3; A.rr(ctx, x + 18, y + 18, CELL - 36, CELL - 36, 22); ctx.stroke(); ctx.setLineDash([]);
  }
  S.cells.forEach((c, i) => {
    if (!c) return;
    const ox = BX + (i % 3) * CELL, oy = BY + Math.floor(i / 3) * CELL;
    inkStrokes(ctx, c.strokes, c.who === 'p' ? PEN : PENCIL, c.who === 'p' ? 9 : 8, c.prog, ox, oy, CELL);
  });
  if (S.pend) S.pend.strokes.forEach((s) => inkStrokes(ctx, [s], PEN, 9, 1, 0, 0, 1));
  if (S.stroke) inkStrokes(ctx, [S.stroke], PEN, 9, 1, 0, 0, 1);
  if (S.line && S.over) {
    if (!S.line.pts) { const c = (i) => [BX + (i % 3 + .5) * CELL, BY + (Math.floor(i / 3) + .5) * CELL], a = c(S.line.a), b = c(S.line.b), dx = (b[0] - a[0]) * .18, dy = (b[1] - a[1]) * .18; S.line.pts = wobble(a[0] - dx, a[1] - dy, b[0] + dx, b[1] + dy, 10, 5); }
    inkStrokes(ctx, [S.line.pts], S.over.who === 'p' ? PEN : PENCIL, 10, S.line.prog, 0, 0, 1);
  }
  // подпись снизу
  const my = BY + 3 * CELL + 110;
  if (S.mode === 'play' && !LAND) {
    A.text(ctx, S.msg, W / 2 - 30, my, { size: 36, weight: 800, color: S.warn > 0 ? '#c2410c' : S.over ? (S.over.who === 'p' ? PEN : S.over.who === 'l' ? PENCIL : INK) : INK });
    const sub = S.over ? (S.overT > 1 ? 'Коснитесь листа — новый раунд' : '') : S.turn === 'p' ? (T.sym ? 'Вы играете ' + (T.sym === 'x' ? 'крестиками' : 'ноликами') + ' · рисуйте или коснитесь клетки' : 'замкнутая петля — нолик, две черты — крестик') : '';
    if (sub) A.text(ctx, sub, W / 2 - 30, my + 52, { size: 23, weight: 600, color: 'rgba(40,48,85,.5)' });
  }
}

A.game({
  id: 'tictac', tone: 'light', title: 'Крестики-нолики', width: W, height: H, orientation: LAND ? 'landscape' : 'portrait', music: 'garden',
  help: { desktop: 'Рисуйте мышью в клетке · стрелки и <kbd>Enter</kbd> — поставить знак', short: 'Нарисуйте знак в клетке', touch: 'Рисуйте пальцем крестик или нолик в клетке' },
  init(g) { titleScreen(g); window.__tictac = () => ({ S, T }); },
  update, draw
});
})();
