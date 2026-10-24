/* Судоку — спокойная головоломка: в каждой строке, столбце и квадрате 3×3 — цифры от 1 до 9 без повторов.
   Каждая задача новая (генератор с единственным решением), «Лёгкое» и «Среднее». Выберите клетку и цифру — касанием
   по панели внизу или клавишами 1–9 (стрелки — по клеткам, 0/Delete — стереть). Ошибка подсвечивается красным. */
(() => {
'use strict';
const A = Arcade;
/* Широкое окно (лист «Досуг» на компьютере) — своя раскладка 1280×720: поле слева во всю высоту, справа — название,
   время и ошибки, панель цифр 3×3 и «Стереть». Узкое (телефон) — сверху вниз, как было. */
const LAND = (() => { try { return innerWidth > (innerHeight - 110) * 1.15; } catch (e) { return false; } })();
const W = LAND ? 1280 : 720, H = LAND ? 720 : 1280;
const BX = LAND ? 58 : 36, BY = LAND ? 54 : 250, SZ = LAND ? 612 : 648, C = SZ / 9;
const PAD_Y = BY + SZ + 50, PAD_W = (W - 72) / 9;
/* кнопки цифр: «гнездо» (по нему попадание) и надписи; кнопка рисуется с отступом 4 по бокам */
const L = LAND ? {
  title: [728, 88], status: [730, 146], statusSize: 24,
  key: (k) => ({ x: 728 + (k % 3) * 166, y: 196 + ((k / 3) | 0) * 124, w: 166, h: 110 }), keyTxt: [48, 90], keySub: 20,
  erase: { x: 732, y: 586, w: 490, h: 80 }, eraseTxt: 42
} : {
  title: [BX, 96], status: [BX + 2, 160], statusSize: 26,
  key: (k) => ({ x: 36 + k * PAD_W, y: PAD_Y, w: PAD_W, h: 110 }), keyTxt: [46, 90], keySub: 18,
  erase: { x: W / 2 - 120, y: PAD_Y + 130, w: 240, h: 80 }, eraseTxt: 42
};
const inR = (x, y, r) => x >= r.x && x < r.x + r.w && y >= r.y && y < r.y + r.h;
const INK = '#2b3550', SOFT = '#eef2fa', ACC = '#5b6cf0', BAD = '#e5486a';
let S = null;

/* ---------------- генератор ---------------- */
function shuffle(a) { for (let i = a.length - 1; i > 0; i--) { const j = (Math.random() * (i + 1)) | 0; [a[i], a[j]] = [a[j], a[i]]; } return a; }
const ok = (b, i, v) => { const r = (i / 9) | 0, c = i % 9, br = r - r % 3, bc = c - c % 3;
  for (let k = 0; k < 9; k++) { if (b[r * 9 + k] === v || b[k * 9 + c] === v) return false; const rr = br + ((k / 3) | 0), cc = bc + k % 3; if (b[rr * 9 + cc] === v) return false; }
  return true; };
function fill(b) {
  const i = b.indexOf(0); if (i < 0) return true;
  for (const v of shuffle([1, 2, 3, 4, 5, 6, 7, 8, 9])) { if (ok(b, i, v)) { b[i] = v; if (fill(b)) return true; b[i] = 0; } }
  return false;
}
function countSol(b, limit = 2) {
  let best = -1, bestN = 10;
  for (let i = 0; i < 81; i++) if (!b[i]) { let n = 0; for (let v = 1; v <= 9; v++) if (ok(b, i, v)) n++; if (n < bestN) { bestN = n; best = i; if (n <= 1) break; } }
  if (best < 0) return 1;
  let cnt = 0;
  for (let v = 1; v <= 9 && cnt < limit; v++) if (ok(b, best, v)) { b[best] = v; cnt += countSol(b, limit - cnt); b[best] = 0; }
  return cnt;
}
function make(givens) {
  const sol = Array(81).fill(0); fill(sol);
  const puz = sol.slice();
  let left = 81;
  for (const i of shuffle([...Array(81).keys()])) {
    if (left <= givens) break;
    const keep = puz[i]; puz[i] = 0;
    if (countSol(puz.slice()) !== 1) puz[i] = keep; else left--;
  }
  return { sol, puz };
}

/* ---------------- состояние ---------------- */
function fresh(mode, level) {
  const { sol, puz } = make(level === 'easy' ? 40 : 31);
  S = { mode, level, sol, puz, cur: puz.slice(), sel: puz.indexOf(0), errs: 0, time: 0, bad: {}, pops: {}, done: 0, demo: 0 };
  return S;
}
function put(g, v) {
  const i = S.sel; if (i < 0 || S.puz[i] || S.done) return;
  if (v === 0) { S.cur[i] = 0; delete S.bad[i]; g.sfx('click', { vol: .4 }); return; }
  S.cur[i] = v; S.pops[i] = 0;
  if (v !== S.sol[i]) { S.bad[i] = true; S.errs++; g.sfx('hurt', { vol: .4, pitch: 1.4 }); g.shake(4, .12); return; }
  delete S.bad[i]; g.sfx('pling', { pitch: .9 + v * .04, vol: .6 });
  // заполнили строку, столбец или квадрат — искорки
  const r = (i / 9) | 0, c = i % 9, groups = [[...Array(9)].map((_, k) => r * 9 + k), [...Array(9)].map((_, k) => k * 9 + c),
    [...Array(9)].map((_, k) => (r - r % 3 + ((k / 3) | 0)) * 9 + (c - c % 3) + k % 3)];
  for (const gr of groups) if (gr.every((j) => S.cur[j] === S.sol[j])) for (const j of gr) g.fx.burst(BX + (j % 9 + .5) * C, BY + (((j / 9) | 0) + .5) * C, { n: 2, colors: [ACC, '#ffd166', '#7ee0b8'], speed: 120, size: 5, life: .5 });
  if (S.cur.every((x, j) => x === S.sol[j])) { S.done = .001; g.sfx('win'); g.stopMusic(); }
}

/* ---------------- экраны ---------------- */
function titleScreen(g) {
  fresh('title', 'easy'); g.setPlaying(false);
  g.screen({
    kicker: A.framed ? 'Досуг' : 'Аркада', title: 'Судоку',
    html: `<p>Заполните поле: в каждой строке, каждом столбце и каждом квадрате 3×3 — цифры от 1 до 9 без повторов. Каждый раз — новая задача.</p>${g.best ? `<p class="record">Рекорд: ${g.best.toLocaleString('ru-RU')}</p>` : ''}`,
    button: 'Лёгкое', onGo: () => start(g, 'easy'), alt: { label: 'Среднее', onGo: () => start(g, 'mid') }
  });
}
function start(g, level) { fresh('play', level); g.fx.clear(); g.setPlaying(true); g.playMusic(); }
function finish(g) {
  S.mode = 'over'; g.setPlaying(false);
  const sc = Math.max(100, Math.round((S.level === 'mid' ? 9000 : 5000) - S.time * 3 - S.errs * 300));
  const rec = g.submit(sc), mm = Math.floor(S.time / 60), ss = String(Math.floor(S.time % 60)).padStart(2, '0');
  for (let k = 0; k < 6; k++) g.fx.burst(BX + Math.random() * SZ, BY + Math.random() * SZ, { n: 12, colors: [ACC, '#ffd166', '#7ee0b8', '#ff8fb8'], speed: 320, size: 8, life: 1, gravity: 500, shape: 'star' });
  g.screen({
    kicker: 'Решено!', title: rec ? 'Новый рекорд!' : 'Отлично!',
    html: `<div class="score">${sc.toLocaleString('ru-RU')}</div><p>${mm}:${ss} · ошибок ${S.errs}${rec ? '' : ` · рекорд ${g.best.toLocaleString('ru-RU')}`}</p>`,
    button: 'Новая задача', onGo: () => start(g, S.level), alt: { label: S.level === 'easy' ? 'Посложнее' : 'Полегче', onGo: () => start(g, S.level === 'easy' ? 'mid' : 'easy') }
  });
}

/* ---------------- цикл ---------------- */
let digit = null;
addEventListener('keydown', (e) => {                       // цифры каркас не знает — ловим сами
  if (e.ctrlKey || e.metaKey || e.altKey) return;
  const m = /^(?:Digit|Numpad)(\d)$/.exec(e.code);
  if (m) { digit = +m[1]; e.preventDefault(); } else if (e.code === 'Delete' || e.code === 'Backspace') { digit = 0; e.preventDefault(); }
});
function update(g, dt) {
  for (const k in S.pops) { S.pops[k] += dt / .25; if (S.pops[k] >= 1) delete S.pops[k]; }
  if (S.mode === 'title') {                                  // заставка: клетки тихо заполняются сами
    S.demo += dt; if (S.demo > .18) { S.demo = 0; const e = S.cur.map((v, i) => (v ? -1 : i)).filter((i) => i >= 0); if (e.length) { const i = A.pick(e); S.cur[i] = S.sol[i]; S.pops[i] = 0; } else fresh('title', 'easy'); }
    return;
  }
  if (S.mode !== 'play') return;
  if (S.done) { S.done += dt; if (S.done > 1.2) finish(g); return; }
  S.time += dt;
  const inp = g.input;
  const mv = { left: -1, right: 1, up: -9, down: 9 };
  for (const d in mv) if (inp.pressed(d)) { const i = S.sel < 0 ? 40 : S.sel, r = (i / 9) | 0, c = i % 9;
    const nr = A.clamp(r + (d === 'up' ? -1 : d === 'down' ? 1 : 0), 0, 8), nc = A.clamp(c + (d === 'left' ? -1 : d === 'right' ? 1 : 0), 0, 8); S.sel = nr * 9 + nc; }
  if (digit !== null) { put(g, digit); digit = null; }
  if (inp.tap) {
    const { x, y } = inp.tap;
    if (x >= BX && x < BX + SZ && y >= BY && y < BY + SZ) { S.sel = ((y - BY) / C | 0) * 9 + ((x - BX) / C | 0); g.sfx('click', { vol: .3 }); }
    else if (LAND) { for (let k = 0; k < 9; k++) if (inR(x, y, L.key(k))) put(g, k + 1); if (inR(x, y, L.erase)) put(g, 0); }
    else if (y >= PAD_Y && y <= PAD_Y + 110) { const k = Math.floor((x - 36) / PAD_W); if (k >= 0 && k < 9) put(g, k + 1); }
    else if (y >= PAD_Y + 130 && y <= PAD_Y + 210 && x > W / 2 - 120 && x < W / 2 + 120) put(g, 0);
  }
}

/* ---------------- отрисовка ---------------- */
function draw(ctx, g) {
  const bg = ctx.createLinearGradient(0, 0, 0, H); bg.addColorStop(0, '#f3f6fd'); bg.addColorStop(1, '#e6ecfa');
  ctx.fillStyle = bg; ctx.fillRect(0, 0, W, H);
  A.text(ctx, 'Судоку', L.title[0], L.title[1], { align: 'left', size: 58, weight: 900, color: INK });
  if (S.mode !== 'title') {
    const mm = Math.floor(S.time / 60), ss = String(Math.floor(S.time % 60)).padStart(2, '0');
    A.text(ctx, `${S.level === 'easy' ? 'лёгкое' : 'среднее'} · ${mm}:${ss} · ошибок ${S.errs}`, L.status[0], L.status[1], { align: 'left', size: L.statusSize, weight: 600, color: 'rgba(43,53,80,.6)' });
  }
  const sel = S.sel, sr = (sel / 9) | 0, sc = sel % 9, sv = sel >= 0 ? S.cur[sel] : 0;
  ctx.save(); ctx.shadowColor = 'rgba(60,80,140,.18)'; ctx.shadowBlur = 30 * g.scale; ctx.shadowOffsetY = 10 * g.scale;
  A.rr(ctx, BX, BY, SZ, SZ, 26); ctx.fillStyle = '#fff'; ctx.fill(); ctx.restore();
  ctx.save(); A.rr(ctx, BX, BY, SZ, SZ, 26); ctx.clip();
  for (let i = 0; i < 81; i++) {
    const r = (i / 9) | 0, c = i % 9, x = BX + c * C, y = BY + r * C;
    const sameBox = sel >= 0 && ((r / 3) | 0) === ((sr / 3) | 0) && ((c / 3) | 0) === ((sc / 3) | 0);
    if (S.mode === 'play' && sel >= 0 && (r === sr || c === sc || sameBox)) { ctx.fillStyle = SOFT; ctx.fillRect(x, y, C, C); }
    if (S.mode === 'play' && sv && S.cur[i] === sv && !S.bad[i]) { ctx.fillStyle = 'rgba(91,108,240,.14)'; ctx.fillRect(x, y, C, C); }
    if (S.mode === 'play' && i === sel) { ctx.fillStyle = 'rgba(91,108,240,.26)'; ctx.fillRect(x, y, C, C); }
    if (S.bad[i]) { ctx.fillStyle = 'rgba(229,72,106,.13)'; ctx.fillRect(x, y, C, C); }
  }
  ctx.strokeStyle = 'rgba(43,53,80,.12)'; ctx.lineWidth = 2;
  for (let k = 1; k < 9; k++) if (k % 3) { ctx.beginPath(); ctx.moveTo(BX + k * C, BY); ctx.lineTo(BX + k * C, BY + SZ); ctx.stroke(); ctx.beginPath(); ctx.moveTo(BX, BY + k * C); ctx.lineTo(BX + SZ, BY + k * C); ctx.stroke(); }
  ctx.strokeStyle = 'rgba(43,53,80,.55)'; ctx.lineWidth = 4;
  for (const k of [3, 6]) { ctx.beginPath(); ctx.moveTo(BX + k * C, BY); ctx.lineTo(BX + k * C, BY + SZ); ctx.stroke(); ctx.beginPath(); ctx.moveTo(BX, BY + k * C); ctx.lineTo(BX + SZ, BY + k * C); ctx.stroke(); }
  for (let i = 0; i < 81; i++) {
    const v = S.cur[i]; if (!v) continue;
    const x = BX + (i % 9 + .5) * C, y = BY + (((i / 9) | 0) + .5) * C, p = S.pops[i] != null ? A.ease.outBack(S.pops[i]) : 1;
    ctx.save(); ctx.translate(x, y + 2); ctx.scale(p, p);
    A.text(ctx, String(v), 0, 0, { size: 46, weight: S.puz[i] ? 800 : 600, color: S.bad[i] ? BAD : S.puz[i] ? INK : ACC });
    ctx.restore();
  }
  ctx.restore();
  A.rr(ctx, BX, BY, SZ, SZ, 26); ctx.lineWidth = 4; ctx.strokeStyle = 'rgba(43,53,80,.55)'; ctx.stroke();
  // панель цифр: сколько каждой осталось
  if (S.mode !== 'title') {
    for (let k = 0; k < 9; k++) {
      const v = k + 1, left = 9 - S.cur.filter((x, i) => x === v && !S.bad[i]).length, r = L.key(k), x = r.x, ky = r.y;
      A.rr(ctx, x + 4, ky, r.w - 8, r.h, 22); ctx.fillStyle = left ? '#fff' : 'rgba(255,255,255,.4)'; ctx.fill();
      ctx.lineWidth = 2; ctx.strokeStyle = 'rgba(43,53,80,.08)'; ctx.stroke();
      A.text(ctx, String(v), x + r.w / 2, ky + L.keyTxt[0], { size: 46, weight: 800, color: left ? ACC : 'rgba(43,53,80,.25)' });
      A.text(ctx, left ? String(left) : '✓', x + r.w / 2, ky + L.keyTxt[1], { size: L.keySub, weight: 600, color: 'rgba(43,53,80,.45)' });
    }
    const e = L.erase;
    A.rr(ctx, e.x, e.y, e.w, e.h, 24); ctx.fillStyle = '#fff'; ctx.fill();
    A.text(ctx, '⌫  Стереть', e.x + e.w / 2, e.y + L.eraseTxt, { size: 28, weight: 700, color: INK });
  }
}

A.game({
  id: 'sudoku', tone: 'light', title: 'Судоку', width: W, height: H, orientation: LAND ? 'landscape' : 'portrait', music: 'garden',
  help: { desktop: '<kbd>1</kbd>–<kbd>9</kbd> — цифра · <kbd>←</kbd> <kbd>→</kbd> <kbd>↑</kbd> <kbd>↓</kbd> — клетка · <kbd>Delete</kbd> — стереть · <kbd>P</kbd> пауза · <kbd>M</kbd> музыка', short: 'Клетка — щелчком или стрелками, цифра — клавишами 1–9', touch: 'Коснитесь клетки, потом цифры внизу' },
  init(g) { titleScreen(g); window.__sudoku = () => S; },
  update, draw
});
})();
