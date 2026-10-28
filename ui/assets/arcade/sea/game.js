/* «Морской бой» с Лирой (0.62; план «Идей Лиры»: «ещё одна игра в „Досуге“ — против Лиры»). Два моря 10×10: сверху
   (в широком окне — справа) море Лиры, по нему стреляете вы; ниже — ваш флот, по нему стреляет Лира. Флот — классика:
   четырёхпалубный, два трёхпалубных, три двухпалубных, четыре однопалубных; корабли не касаются друг друга, расставляются
   сами («Перемешать» — заново). Попал — стреляешь ещё; потопил — вокруг корабля открывается вода. Лира ищет «шахматкой»,
   а раненый корабль добивает по линии; на «полегче» стреляет наугад. Очки: меньше выстрелов — больше; в полную силу ×2.
   Голосом (0.63; план «Идей Лиры»: «„Б пять!“ — Лира ставит выстрел сама и отвечает голосом»): хозяин (телефон — app.js,
   компьютер — pad.js) присылает {arcade: 'heard', text}; разобрали клетку — выстрел, а итог хода (и выстрел Лиры) —
   одной фразой {arcade: 'say', text}. Кнопка микрофона вверху — {arcade: 'listen'}. Касаниями — молча, как раньше. */
(() => {
'use strict';
const A = Arcade;
const LAND = (() => { try { return innerWidth > (innerHeight - 110) * 1.15; } catch (e) { return false; } })();
const W = LAND ? 1280 : 720, H = LAND ? 720 : 1280, N = 10;
const BG = '#e6eef5', DEEP = '#bcd0e2', LIGHT = '#ffffff', INK = '#17324d', MUTED = 'rgba(23,50,77,.55)';
const SEA = '#d4e4f1', HULL = '#3d5a78', HIT = '#ff6a4d', SUNK = '#8a98a8';
const FLEET = [4, 3, 3, 2, 2, 2, 1, 1, 1, 1];
const LET = 'АБВГДЕЖЗИК';
// раскладка: море Лиры (цель) и своё
const L = LAND
  ? { T: { x: 700, y: 100, s: 540 }, M: { x: 90, y: 330, s: 300 }, title: [270, 96], say: { x: 60, y: 160, w: 420, h: 90 } }
  : { T: { x: 80, y: 280, s: 560 }, M: { x: 230, y: 950, s: 260 }, title: [W / 2, 96], say: { x: 70, y: 140, w: 580, h: 80 } };
let S = null, SC = 1, G = null;

/* флот: корабли не касаются (и углами) */
function place() {
  for (let tries = 0; tries < 200; tries++) {
    const b = Array.from({ length: N }, () => Array(N).fill(0)), ships = [];
    let okAll = true;
    for (const len of FLEET) {
      let put = false;
      for (let k = 0; k < 300 && !put; k++) {
        const hor = Math.random() < .5, x = Math.floor(Math.random() * (hor ? N - len + 1 : N)), y = Math.floor(Math.random() * (hor ? N : N - len + 1));
        const cells = Array.from({ length: len }, (_, i) => [x + (hor ? i : 0), y + (hor ? 0 : i)]);
        if (cells.every(([cx, cy]) => { for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) { const nx = cx + dx, ny = cy + dy; if (nx >= 0 && ny >= 0 && nx < N && ny < N && b[ny][nx]) return false; } return true; })) {
          const id = ships.length + 1; cells.forEach(([cx, cy]) => { b[cy][cx] = id; }); ships.push({ id, cells, hor, hits: 0 }); put = true;
        }
      }
      if (!put) { okAll = false; break; }
    }
    if (okAll) return { b, ships };
  }
  throw new Error('флот не расставился');
}
/* поле: s — 0 нет выстрела, 1 мимо, 2 попал */
function side() { const f = place(); return Object.assign(f, { shot: Array.from({ length: N }, () => Array(N).fill(0)), left: FLEET.length }); }
function fresh(mode, easy) {
  S = { mode, easy, me: side(), ai: side(), turn: 'me', think: 0, shots: 0, say: '', sayT: 0, fx: [], last: null, end: 0, aim: null, hunt: [] };
  return S;
}
/* выстрел по полю f в (x, y) -> 'miss' | 'hit' | 'sunk' | null (уже стреляли) */
function fire(f, x, y) {
  if (f.shot[y][x]) return null;
  const id = f.b[y][x];
  if (!id) { f.shot[y][x] = 1; return 'miss'; }
  f.shot[y][x] = 2;
  const sh = f.ships[id - 1]; sh.hits++;
  if (sh.hits < sh.cells.length) return 'hit';
  sh.sunk = true; f.left--;
  for (const [cx, cy] of sh.cells) for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
    const nx = cx + dx, ny = cy + dy; if (nx >= 0 && ny >= 0 && nx < N && ny < N && !f.shot[ny][nx]) f.shot[ny][nx] = 1;
  }
  return 'sunk';
}
/* Лира: добить раненого по линии, иначе — шахматка с учётом длины самого большого живого */
function aiPick() {
  const f = S.me, free = (x, y) => x >= 0 && y >= 0 && x < N && y < N && !f.shot[y][x];
  if (S.easy && Math.random() < .55) { const c = []; for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) if (free(x, y)) c.push([x, y]); return A.pick(c); }
  const wounded = []; for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) if (f.shot[y][x] === 2 && !f.ships[f.b[y][x] - 1].sunk) wounded.push([x, y]);
  if (wounded.length) {
    const c = [];
    if (wounded.length > 1) {
      const hor = wounded[0][1] === wounded[1][1];
      const xs = wounded.map(p => p[0]), ys = wounded.map(p => p[1]);
      if (hor) { c.push([Math.min(...xs) - 1, ys[0]], [Math.max(...xs) + 1, ys[0]]); } else { c.push([xs[0], Math.min(...ys) - 1], [xs[0], Math.max(...ys) + 1]); }
    } else { const [x, y] = wounded[0]; c.push([x + 1, y], [x - 1, y], [x, y + 1], [x, y - 1]); }
    const ok = c.filter(([x, y]) => free(x, y)); if (ok.length) return A.pick(ok);
  }
  const big = Math.max(...f.ships.filter(s => !s.sunk).map(s => s.cells.length));
  const score = [];                                  // сколько живых кораблей ещё может стоять через клетку
  for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) {
    if (!free(x, y)) continue;
    let v = 0;
    for (const len of f.ships.filter(s => !s.sunk).map(s => s.cells.length)) {
      for (let o = 0; o < len; o++) {
        if (Array.from({ length: len }, (_, i) => [x - o + i, y]).every(([a, b]) => free(a, b))) v++;
        if (len > 1 && Array.from({ length: len }, (_, i) => [x, y - o + i]).every(([a, b]) => free(a, b))) v++;
      }
    }
    if (big > 1 && (x + y) % 2) v *= .6;               // шахматка
    score.push([v + Math.random() * .5, x, y]);
  }
  score.sort((a, b) => b[0] - a[0]);
  return [score[0][1], score[0][2]];
}
const SAY = {
  hit: ['Ой! Попали.', 'Ранили!', 'Ай-ай.'], sunk: ['Потопили! Красиво.', 'Мой корабль на дне…', 'Эх, не уберегла.'],
  miss: ['Мимо!', 'Вода.', 'Не тут.'], myhit: ['Есть попадание!', 'Попала!'], mysunk: ['Ваш корабль потоплен!', 'На дно!'], mymiss: ['Промахнулась.', 'Мимо, ваш ход.'],
  think: ['Так-так…', 'Куда бы…', 'Хм…']
};
const say = (k) => { S.say = A.pick(SAY[k]); S.sayT = 2; };
/* ---------------- голос ---------------- */
const NAME = ['А', 'Бэ', 'Вэ', 'Гэ', 'Дэ', 'Е', 'Жэ', 'Зэ', 'И', 'Ка'];
const NUM = ['один', 'два', 'три', 'четыре', 'пять', 'шесть', 'семь', 'восемь', 'девять', 'десять'];
const spoken = (x, y) => `${NAME[x]} ${NUM[y]}`;
const LETW = { 'а': 0, 'б': 1, 'бэ': 1, 'бе': 1, 'в': 2, 'вэ': 2, 'ве': 2, 'г': 3, 'гэ': 3, 'ге': 3, 'д': 4, 'дэ': 4, 'де': 4, 'е': 5, 'ж': 6, 'жэ': 6, 'же': 6,
  'з': 7, 'зэ': 7, 'зе': 7, 'и': 8, 'к': 9, 'ка': 9, 'й': 9 };
const NUMW = { 'один': 1, 'одна': 1, 'раз': 1, 'два': 2, 'две': 2, 'три': 3, 'четыре': 4, 'пять': 5, 'шесть': 6, 'семь': 7, 'восемь': 8, 'девять': 9, 'десять': 10 };
/* «Б5», «бэ пять», «стреляю в дэ семь», «К-10» -> [x, y] или null; берём последнюю пару «буква, число» */
function cellOf(text) {
  const t = String(text || '').toLowerCase().replace(/ё/g, 'е').replace(/([а-я])(\d)/g, '$1 $2').replace(/[^а-я0-9]+/g, ' ').trim().split(' ');
  let out = null;
  for (let i = 0; i + 1 < t.length; i++) {
    const x = LETW[t[i]], n = /^\d+$/.test(t[i + 1]) ? +t[i + 1] : NUMW[t[i + 1]];
    if (x !== undefined && n >= 1 && n <= 10) out = [x, n - 1];
  }
  return out;
}
const vq = [];
function speak(text) { if (!S.voice || !A.framed) return; try { window.parent.postMessage({ arcade: 'say', text }, '*'); } catch (e) { /* хозяина нет */ } }
const flush = () => { if (vq.length) speak(vq.splice(0).join(' ')); };
const bubble = (t, s = 2.4) => { S.say = t; S.sayT = s; };
function heard(text) {
  if (!S || !G) return;
  S.voice = true;
  const t = String(text || '').toLowerCase();
  if (!t.trim()) { bubble('Не расслышала'); return speak('Не расслышала. Скажите клетку, например: «Бэ пять».'); }
  if (S.mode !== 'play') {
    if (/сыгра|игра|начн|давай|ещ[её]|партию|поехали|да\b/.test(t)) { if (G.screenOn) G.hideScreen(); start(G, /полегче|легк|спокой/.test(t) ? true : /полн|сильн/.test(t) ? false : !!S.easy); return speak('Ваш выстрел! Называйте клетку: буква и число.'); }
    return speak('Скажите «играем» — и начнём.');
  }
  if (/сда[юе]/.test(t)) { vq.length = 0; S.end = .4; return speak('Принято. Мои корабли теперь видны.'); }
  if (/сколько|остал/.test(t)) return speak(`У меня кораблей: ${S.ai.left}, у вас: ${S.me.left}.`);
  if (S.end) return;
  if (S.turn !== 'me') return speak('Подождите, я целюсь.');
  const c = cellOf(t);
  if (!c) { bubble('Какая клетка?'); return speak('Не поняла клетку. Скажите букву и число: например, «Дэ семь».'); }
  if (S.ai.shot[c[1]][c[0]]) { bubble(`${LET[c[0]]}${c[1] + 1}: уже стреляли`); return speak(`В ${spoken(c[0], c[1])} уже стреляли — выберите другую клетку.`); }
  shoot(G, c[0], c[1]);
}
addEventListener('message', (e) => { if (e.source === window.parent && e.data && e.data.arcade === 'heard') heard(e.data.text); });
/* выстрел игрока (касанием или голосом) -> итог; голосом — фраза: попали — «стреляйте ещё», мимо — ждём выстрела Лиры */
function shoot(g, x, y) {
  const res = fire(S.ai, x, y); if (!res) { g.sfx('click', { vol: .4 }); return null; }
  S.shots++; S.last = { who: 'me', x, y };
  boom(g, L.T, x, y, res);
  if (res === 'miss') { say('miss'); S.turn = 'ai'; S.think = 0; vq.push(`${spoken(x, y)} — мимо.`); }
  else {
    say(res === 'sunk' ? 'sunk' : 'hit'); if (res === 'sunk') g.sfx('coin'); if (S.ai.left === 0) S.end = 1.1;
    vq.push(S.ai.left === 0 ? 'Потопили мой последний корабль — вы победили!' : res === 'sunk' ? 'Потопили! Стреляйте ещё.' : 'Ранили! Стреляйте ещё.'); flush();
  }
  return res;
}
const cellAt = (r, px, py) => { const c = r.s / N, x = Math.floor((px - r.x) / c), y = Math.floor((py - r.y) / c); return x >= 0 && y >= 0 && x < N && y < N ? [x, y] : null; };
function boom(g, r, x, y, res) {
  const c = r.s / N, cx = r.x + (x + .5) * c, cy = r.y + (y + .5) * c;
  if (res === 'miss') { g.sfx('whoosh', { vol: .5 }); g.fx.ring(cx, cy, { r1: c * .9, color: '#7fb0d8', width: 3, life: .45 }); }
  else { g.sfx(res === 'sunk' ? 'boom' : 'hit'); g.fx.burst(cx, cy, { n: res === 'sunk' ? 26 : 12, colors: ['#ff6a4d', '#ffb347', '#ffd166'], speed: 260, size: 6, life: .7, gravity: 300 }); if (res === 'sunk') g.shake && g.shake(.25, 8); }
}

/* ---------------- экраны ---------------- */
function titleScreen(g) {
  fresh('title', false); g.setPlaying(false);
  g.screen({
    kicker: A.framed ? 'Досуг' : 'Аркада', title: 'Морской бой',
    html: `<p>Ваш флот уже на воде. Стреляйте по морю Лиры: попали — ещё выстрел, потопили — вокруг откроется вода. Кто первым потопит весь флот — победил.</p>${g.best ? `<p class="record">Рекорд: ${g.best.toLocaleString('ru-RU')}</p>` : ''}`,
    button: 'Играть', onGo: () => start(g, false), alt: { label: 'Полегче', onGo: () => start(g, true) }
  });
}
function start(g, easy) { const v = !!(S && S.voice); vq.length = 0; fresh('play', easy); S.voice = v; g.fx.clear(); g.setPlaying(true); g.playMusic(); S.say = easy ? 'Сыграем спокойно. Стреляйте первым!' : 'Ваш выстрел! Я спрятала флот.'; S.sayT = 2.6; }
function finish(g, win) {
  S.mode = 'over'; S.reveal = true; g.setPlaying(false); g.stopMusic();
  g.sfx(win ? 'win' : 'lose');
  const sc = win ? Math.max(1, 101 - S.shots) * 100 * (S.easy ? 1 : 2) : 0;
  const rec = win && g.submit(sc);
  if (win) for (let k = 0; k < 6; k++) g.fx.burst(L.T.x + Math.random() * L.T.s, L.T.y + Math.random() * L.T.s, { n: 12, colors: ['#ff6a4d', '#ffd166', '#7fb0d8', '#ffffff'], speed: 320, size: 8, life: 1, gravity: 480, shape: 'star' });
  g.screen({
    kicker: `Выстрелов: ${S.shots} · кораблей у вас: ${S.me.left}`, title: win ? (rec ? 'Новый рекорд!' : 'Победа!') : 'Лира победила',
    html: win ? `<div class="score">${sc.toLocaleString('ru-RU')}</div><p>${S.easy ? 'На «полегче». Попробуйте в полную силу!' : 'Флот Лиры на дне — адмирал!'}</p>` : `<p>Ещё партию? Совет: раненый корабль добивайте по линии.</p>`,
    button: 'Ещё партию', onGo: () => start(g, S.easy), alt: { label: S.easy ? 'В полную силу' : 'Полегче', onGo: () => start(g, !S.easy) }
  });
}

/* ---------------- цикл ---------------- */
function update(g, dt) {
  if (S.sayT > 0) S.sayT -= dt;
  if (S.mode === 'over') return;
  if (S.end) { S.end -= dt; if (S.end <= 0) finish(g, S.ai.left === 0); return; }
  if (S.mode === 'title') {                          // заставка: две Лиры стреляют сами
    S.think += dt; if (S.think > .35) { S.think = 0; const f = Math.random() < .5 ? S.ai : S.me, c = []; for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) if (!f.shot[y][x]) c.push([x, y]); if (c.length > 30) { const [x, y] = A.pick(c); fire(f, x, y); } else fresh('title', false); }
    return;
  }
  if (S.turn === 'ai') {
    S.think += dt;
    if (S.think > .3 && S.think - dt <= .3 && Math.random() < .3) say('think');
    if (S.think > .8) {
      S.think = 0; const [x, y] = aiPick(), res = fire(S.me, x, y); S.last = { who: 'ai', x, y };
      boom(g, L.M, x, y, res);
      const at = `Стреляю: ${spoken(x, y)} —`;
      if (res === 'miss') { say('mymiss'); S.turn = 'me'; vq.push(`${at} мимо. Ваш ход.`); flush(); }
      else { say(res === 'sunk' ? 'mysunk' : 'myhit'); if (S.me.left === 0) S.end = 1.1;
        vq.push(S.me.left === 0 ? `${at} потопила ваш последний корабль. Я победила!` : `${at} ${res === 'sunk' ? 'ваш корабль потоплен' : 'попала'}.`); if (S.me.left === 0) flush(); }
    }
    return;
  }
  const inp = g.input;
  if (inp.tap) {
    const c = cellAt(L.T, inp.tap.x, inp.tap.y); if (!c) return;
    shoot(g, c[0], c[1]);
  }
}

function soft(ctx, x, y, w, h, r, d0, inset) {
  const d = d0 * SC; ctx.save();
  if (!inset) {
    ctx.shadowColor = DEEP; ctx.shadowBlur = d * 1.8; ctx.shadowOffsetX = d * .7; ctx.shadowOffsetY = d * .7;
    A.rr(ctx, x, y, w, h, r); ctx.fillStyle = BG; ctx.fill();
    ctx.shadowColor = LIGHT; ctx.shadowOffsetX = -d * .7; ctx.shadowOffsetY = -d * .7; ctx.fill();
  } else {
    A.rr(ctx, x, y, w, h, r); ctx.fillStyle = SEA; ctx.fill(); ctx.clip();
    ctx.shadowColor = DEEP; ctx.shadowBlur = d * 1.4; ctx.shadowOffsetX = d * .5; ctx.shadowOffsetY = d * .5;
    ctx.lineWidth = d0; ctx.strokeStyle = SEA; A.rr(ctx, x - d0 / 2, y - d0 / 2, w + d0, h + d0, r + d0 / 2); ctx.stroke();
    ctx.shadowColor = LIGHT; ctx.shadowOffsetX = -d * .5; ctx.shadowOffsetY = -d * .5; ctx.stroke();
  }
  ctx.restore();
}
/* одно море: подписи, волны, корабли (свои — всегда, чужие — потопленные), выстрелы */
function board(ctx, g, r, f, mine, label) {
  const c = r.s / N, t = g.t;
  soft(ctx, r.x - 14, r.y - 14, r.s + 28, r.s + 28, 30, 10, false);
  soft(ctx, r.x, r.y, r.s, r.s, 20, 8, true);
  ctx.save(); A.rr(ctx, r.x, r.y, r.s, r.s, 20); ctx.clip();
  ctx.strokeStyle = 'rgba(255,255,255,.55)'; ctx.lineWidth = 1.5;          // лёгкая рябь
  for (let i = 0; i < 6; i++) { const yy = r.y + (i + .5) * r.s / 6 + Math.sin(t * .8 + i) * 4; ctx.beginPath(); for (let xx = 0; xx <= r.s; xx += 12) ctx.lineTo(r.x + xx, yy + Math.sin(xx / 30 + t * 1.6 + i) * 3); ctx.stroke(); }
  ctx.strokeStyle = 'rgba(23,50,77,.1)'; ctx.lineWidth = 1;
  for (let i = 1; i < N; i++) { ctx.beginPath(); ctx.moveTo(r.x + i * c, r.y); ctx.lineTo(r.x + i * c, r.y + r.s); ctx.stroke(); ctx.beginPath(); ctx.moveTo(r.x, r.y + i * c); ctx.lineTo(r.x + r.s, r.y + i * c); ctx.stroke(); }
  for (const sh of f.ships) {                       // корабли: капсулы по клеткам
    if (!mine && !sh.sunk) continue;
    const xs = sh.cells.map(p => p[0]), ys = sh.cells.map(p => p[1]), x0 = Math.min(...xs), y0 = Math.min(...ys);
    const w = (Math.max(...xs) - x0 + 1) * c, h = (Math.max(...ys) - y0 + 1) * c, pad = c * .14;
    A.rr(ctx, r.x + x0 * c + pad, r.y + y0 * c + pad, w - pad * 2, h - pad * 2, (Math.min(w, h) - pad * 2) / 2);
    ctx.fillStyle = sh.sunk ? SUNK : HULL; ctx.fill();
    if (!sh.sunk) { ctx.fillStyle = 'rgba(255,255,255,.25)'; A.rr(ctx, r.x + x0 * c + pad * 1.6, r.y + y0 * c + pad * 1.6, w - pad * 3.2, (h - pad * 3.2) * .38, c * .12); ctx.fill(); }
  }
  for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) {
    const s = f.shot[y][x], cx = r.x + (x + .5) * c, cy = r.y + (y + .5) * c;
    if (s === 1) { ctx.beginPath(); ctx.arc(cx, cy, c * .1, 0, Math.PI * 2); ctx.fillStyle = 'rgba(23,50,77,.35)'; ctx.fill(); }
    if (s === 2) {
      const sunk = f.ships[f.b[y][x] - 1].sunk;
      ctx.save(); ctx.translate(cx, cy); ctx.rotate(Math.PI / 4); ctx.fillStyle = sunk ? '#fff' : HIT;
      ctx.fillRect(-c * .26, -c * .06, c * .52, c * .12); ctx.fillRect(-c * .06, -c * .26, c * .12, c * .52); ctx.restore();
      if (!sunk) { ctx.beginPath(); ctx.arc(cx, cy, c * (.36 + Math.sin(t * 6 + x + y) * .04), 0, Math.PI * 2); ctx.strokeStyle = 'rgba(255,106,77,.5)'; ctx.lineWidth = 2; ctx.stroke(); }
    }
  }
  if (S.last && ((S.last.who === 'me') !== mine) && S.mode === 'play') { ctx.lineWidth = 3; ctx.strokeStyle = 'rgba(23,50,77,.55)'; A.rr(ctx, r.x + S.last.x * c + 3, r.y + S.last.y * c + 3, c - 6, c - 6, 8); ctx.stroke(); }
  ctx.restore();
  const fs = Math.max(13, c * .34);                  // А–К сверху, 1–10 слева
  for (let i = 0; i < N; i++) {
    A.text(ctx, LET[i], r.x + (i + .5) * c, r.y - 26, { size: fs, weight: 700, color: MUTED });
    A.text(ctx, String(i + 1), r.x - 30, r.y + (i + .5) * c + fs * .35, { size: fs, weight: 700, color: MUTED });
  }
  A.text(ctx, label, r.x + r.s / 2, r.y + r.s + (mine ? 44 : 50), { size: mine ? 22 : 26, weight: 700, color: INK });
}
function draw(ctx, g) {
  SC = g.scale;
  ctx.fillStyle = BG; ctx.fillRect(0, 0, W, H);
  A.text(ctx, 'Морской бой', L.title[0], L.title[1], { size: 56, weight: 900, color: INK });
  const aiLeft = S.ai.left, meLeft = S.me.left, on = S.mode === 'play' && !S.end;
  board(ctx, g, L.T, S.ai, !!S.reveal, `Море Лиры · кораблей: ${aiLeft}`);         // партия кончилась — где стояли корабли Лиры
  board(ctx, g, L.M, S.me, true, `Ваш флот · кораблей: ${meLeft}`);
  const sb = L.say, bx = sb.x + sb.w / 2;
  if (S.sayT > 0 && S.say) {
    const a = Math.min(1, S.sayT / .3, (2.2 - S.sayT) / .2);
    ctx.save(); ctx.globalAlpha = Math.max(0, a); soft(ctx, sb.x, sb.y, sb.w, sb.h, 30, 6, false);
    A.text(ctx, S.say, bx, sb.y + sb.h / 2 + 9, { size: 26, weight: 600, color: INK }); ctx.restore();
  } else if (on) A.text(ctx, S.turn === 'me' ? (S.voice ? 'Ваш выстрел — назовите клетку: «Бэ пять»' : 'Ваш выстрел — коснитесь клетки в море Лиры') : 'Лира целится…', bx, sb.y + sb.h / 2 + 9, { size: 22, weight: 600, color: MUTED });
}

A.game({
  id: 'sea', tone: 'light', title: 'Морской бой', width: W, height: H, orientation: LAND ? 'landscape' : 'portrait', music: 'garden',
  help: { desktop: 'Щелчок по клетке в море Лиры — выстрел · <kbd>P</kbd> пауза · <kbd>M</kbd> музыка', short: 'Щелчок по клетке — выстрел', touch: 'Коснитесь клетки в море Лиры — выстрел' },
  init(g) {
    G = g; titleScreen(g); window.__sea = () => S; window.__seaPick = () => aiPick(); window.__seaCell = cellOf;
    if (A.framed) {                                   // микрофон: хозяин слушает один раз и присылает {arcade: 'heard'}
      const b = document.createElement('button'); b.type = 'button'; b.className = 'tbtn icon'; b.id = 'seaMic';
      b.setAttribute('aria-label', 'Сказать ход голосом'); b.title = 'Сказать ход голосом: «Бэ пять»';
      b.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21"/></svg>';
      const m = document.getElementById('aMusic'); m.parentNode.insertBefore(b, m);
      b.addEventListener('click', () => { if (!S) return; S.voice = true; bubble('Слушаю…', 4); try { window.parent.postMessage({ arcade: 'listen' }, '*'); } catch (e) { /* хозяина нет */ } });
    }
  },
  update, draw
});
})();
