/* Пять букв — угадайте слово из пяти букв за шесть попыток (как «Wordle»). После каждой попытки буквы окрашиваются:
   зелёная — на своём месте, жёлтая — есть в слове, но в другом месте, серая — нет. Клавиатура на экране и обычная.
   Стиль — мягкий «Небесный» Dewiar. Очки — серия угаданных подряд. */
(() => {
'use strict';
const A = Arcade;
/* Широкое окно (лист «Досуг» на компьютере) — своя раскладка 1280×720: плитки слева во всю высоту, справа — название,
   подсказка о цветах и клавиатура. Книжная — как прежде. */
const LAND = (() => { try { return innerWidth > (innerHeight - 110) * 1.15; } catch (e) { return false; } })();
const W = LAND ? 1280 : 720, H = LAND ? 720 : 1280, ROWS = 6, LEN = 5;
const WORDS = 'абзац автор агент адрес актер акула акция аллея алмаз ангел апорт арбуз арена афиша багаж бадья базар бакен балда балет банан банда банка баран барон басня батон башня берег бетон бидон бизон билет битва благо блеск блоха блюдо бобер бокал ботва бочка бровь бубен будка буква булка бурав буран бутон буфер бухта вагон вальс ванна варка ватка вафля вдова веник венок верба весло весна ветер ветка вечер взлет видео вилка вилла винил вирус вишня влага вобла вожак вождь вожжи вокал волна вопль ворон ворот ворох время вывод выдра вьюга газон гайка галка гамак гамма гараж гений герой гетры глина говор голос гомон гонец горка горох гость грань грива гриль гроза груша гряда гуашь губка гусли дамба дверь дебри дебют девиз декор диван дичок дождь доска драма древо дрова дубок дудка дуэль дымок дятел ежиха жажда жакет жених жетон живот жилет жираф забор завод загар заказ закат залив замок запас запах заряд зачет звено зверь зебра зелье земля зенит зерно зефир злато знамя игрок икона индюк искра кабан кадка казак кайма какао калач камин канат капля капот карта касса катер каток кашне каюта кварц кефир киоск кисет кисть класс клерк клоун книга кобра козел колос комар конек копия короб кость котел кофта кошка кража крона кросс крыло крыша кубик кукла кулак кулон купол кураж курок кусок кухня лазер лампа лапша ласка лента лесок лиана лидер лилия лимит лимон линия лодка ложка локон лотос лунка лучик лыжня магия майка майор малыш манго манеж марка маска масло мачта медик мелок метла метод метро мечта мираж миска модем мойка молот мороз мотив мотор мохер мышка мэрия мюсли набор навес навык нарды народ насос наука недра нерпа нефть нитка ножик ножны нолик норка норма носок оазис обзор образ обруч обувь овраг огонь океан оклад окрас олень опера опора орган осень отвар отдых отель отряд отчет охота очерк пакет палас палец палка панда папка парад парик парта парус паста пасха пауза пачка певец пемза пенал пепел перец песня петух печка пилот пирог пицца пламя плита повар поезд показ полка помпа порох почта право приют проза птица пудра пульс пурга пушка пчела пьеса радио разум рамка раунд рация ребус режим рейка роман рубин рубка рукав рулет ручей ручка рыбак рынок рысак сабля сайка салат салют самба сахар свеча свита сеанс север седло семья сетка сироп скала скрип слава слива слово смена смесь сокол сосна сотня спина спица спорт ссора стадо сталь старт стена стиль столб стриж ступа судно судья сукно сумка сфера сцена сырок табло тайга тайна такси танец тапок тачка театр тезис тембр тенор тепло терем тесто товар толпа точка трава тракт трель тропа туман тумба тунец тыква тюбик уголь удача узник уклон улица устье факел факир фасад ферма фильм финиш фокус форма фраза фрукт фужер хакер халва хвост химия холод хомяк хорал хорек хруст хурма цапля цифра чайка чалма чашка черта чехол чудак шалаш шапка шарик шахта шашка шланг шорох шпага шпиль шрифт штиль штора шутка шхуна щенок щиток экран эскиз ягода якорь ямщик ярлык ясень'.split(' ');
const BG = '#dbe5f1', DARK = '#b8c5d6', LIGHT = '#f7fbff', INK = '#24324a', MUTED = 'rgba(36,50,74,.55)';
const GOOD = '#4cbf8c', NEAR = '#f2b84b', NO = '#9aa7ba';
const KB = ['йцукенгшщзхъ', 'фывапролджэ', '↵ячсмитьбю⌫'];
const TX = LAND ? 60 : 110, TY = LAND ? 78 : 250, TS = LAND ? 84 : 92, TG = LAND ? 12 : 14;
const TR = LAND ? 20 : 22, TF = LAND ? 46 : 50;           // скругление и буква плитки
const P = { x: 600, w: 620 };                            // широкое окно: правая колонка
let S = null, SC = 1, KEYS = [];

function fresh(mode, streak = 0) {
  S = { mode, word: A.pick(WORDS), rows: [], cur: '', marks: [], keys: {}, flip: null, shake: 0, msg: '', msgT: 0, done: 0, win: false, streak, demo: 0 };
  return S;
}
function mark(guess, word) {
  const res = Array(LEN).fill('no'), left = {};
  for (let i = 0; i < LEN; i++) { if (guess[i] === word[i]) res[i] = 'good'; else left[word[i]] = (left[word[i]] || 0) + 1; }
  for (let i = 0; i < LEN; i++) if (res[i] !== 'good' && left[guess[i]]) { res[i] = 'near'; left[guess[i]]--; }
  return res;
}
const RANK = { no: 1, near: 2, good: 3 };
function submit(g) {
  if (S.flip || S.done) return;
  if (S.cur.length < LEN) { S.shake = .4; S.msg = 'Нужно пять букв'; S.msgT = 1.4; g.sfx('click'); return; }
  const m = mark(S.cur, S.word);
  S.rows.push(S.cur); S.marks.push(m); S.flip = { row: S.rows.length - 1, t: 0 };
  for (let i = 0; i < LEN; i++) { const ch = S.cur[i]; if ((RANK[m[i]] || 0) > (RANK[S.keys[ch]] || 0)) S.keys[ch] = m[i]; }
  S.cur = '';
}
function type(g, ch) {
  if (S.flip || S.done || S.mode !== 'play') return;
  if (ch === '⌫') { S.cur = S.cur.slice(0, -1); g.sfx('click', { vol: .3 }); return; }
  if (ch === '↵') return submit(g);
  if (S.cur.length < LEN) { S.cur += ch; g.sfx('click', { vol: .4, pitch: 1.2 }); }
}

/* ---------------- экраны ---------------- */
function titleScreen(g) {
  fresh('title'); g.setPlaying(false);
  g.screen({
    kicker: A.framed ? 'Досуг' : 'Аркада', title: 'Пять букв',
    html: '<p>Угадайте слово из пяти букв за шесть попыток. <b style="color:#3aa877">Зелёная</b> буква — на своём месте, <b style="color:#d79a22">жёлтая</b> — есть в слове, но не здесь.</p>' + (g.best ? '<p class="record">Лучшая серия: ' + g.best + '</p>' : ''),
    button: 'Играть', onGo: () => start(g, 0)
  });
}
function start(g, streak) { fresh('play', streak); g.fx.clear(); g.setPlaying(true); g.playMusic(); }
function finish(g) {
  S.mode = 'over'; g.setPlaying(false); g.stopMusic();
  const streak = S.win ? S.streak + 1 : 0, rec = S.win && g.submit(streak);
  g.screen({
    kicker: S.win ? 'Угадано с ' + S.rows.length + '-й попытки' : 'Не угадано', title: S.win ? (rec ? 'Новая серия!' : 'Здорово!') : S.word.toUpperCase(),
    html: S.win ? '<div class="score">' + streak + '</div><p>' + (streak > 1 ? 'угадано подряд' : 'первое в серии') + '</p>' : '<p>Это было слово «' + S.word + '». Попробуем другое?</p>',
    button: S.win ? 'Следующее слово' : 'Новое слово', onGo: () => start(g, streak), alt: { label: A.framed ? 'К играм' : 'В аркаду', onGo: () => A.home('../index.html') }
  });
}

/* ---------------- цикл ---------------- */
let typed = [];
const RU = {}; 'KeyQ й KeyW ц KeyE у KeyR к KeyT е KeyY н KeyU г KeyI ш KeyO щ KeyP з BracketLeft х BracketRight ъ KeyA ф KeyS ы KeyD в KeyF а KeyG п KeyH р KeyJ о KeyK л KeyL д Semicolon ж Quote э KeyZ я KeyX ч KeyC с KeyV м KeyB и KeyN т KeyM ь Comma б Period ю Backquote е'
  .split(' ').forEach((v, i, a) => { if (i % 2 === 0) RU[v] = a[i + 1]; });
addEventListener('keydown', (e) => {
  if (e.ctrlKey || e.metaKey || e.altKey) return;
  let k = (e.key || '').toLowerCase().replace('ё', 'е');
  if (!/^[а-я]$/.test(k) && RU[e.code]) k = RU[e.code];        // английская раскладка — буква по месту клавиши (ЙЦУКЕН)
  if (/^[а-я]$/.test(k)) { typed.push(k); e.preventDefault(); }
  else if (e.key === 'Backspace') { typed.push('⌫'); e.preventDefault(); }
  else if (e.key === 'Enter') typed.push('↵');
});
function update(g, dt) {
  if (S.shake > 0) S.shake -= dt; if (S.msgT > 0) S.msgT -= dt;
  if (S.flip) {
    S.flip.t += dt;
    const total = LEN * .18 + .3;
    if (S.flip.t >= total) {
      const m = S.marks[S.flip.row]; S.flip = null;
      if (m.every((x) => x === 'good')) { S.win = true; S.done = .001; g.sfx('win'); for (let i = 0; i < LEN; i++) g.fx.burst(TX + i * (TS + TG) + TS / 2, TY + (S.rows.length - 1) * (TS + TG) + TS / 2, { n: 8, colors: [GOOD, '#fff', NEAR], speed: 260, size: 7, shape: 'star', life: .8 }); }
      else if (S.rows.length >= ROWS) { S.done = .001; g.sfx('lose'); }
      else g.sfx('pling', { vol: .4 });
    } else if (Math.floor((S.flip.t - dt) / .18) !== Math.floor(S.flip.t / .18) && S.flip.t < LEN * .18) g.sfx('bounce', { pitch: 1 + Math.floor(S.flip.t / .18) * .08, vol: .35 });
  }
  if (S.mode === 'title') {
    S.demo += dt;
    if (!S.flip && S.demo > .35) { S.demo = 0; if (S.rows.length >= 3) fresh('title'); else if (S.cur.length < LEN) S.cur += (S.rows.length === 2 ? S.word : A.pick(WORDS))[S.cur.length]; else submit(g); }
    typed = []; return;
  }
  // GitHub #17 (24.10): после итога S.done оставался, и finish() звался каждый кадр — экран пересоздавался,
  // защита от раннего клика не истекала, и «Следующее слово» не срабатывало. Вне игры — ничего не делаем.
  if (S.mode !== 'play') { typed = []; return; }
  if (S.done) { S.done += dt; if (S.done > 1.3) finish(g); typed = []; return; }
  for (const ch of typed) type(g, ch); typed = [];
  const inp = g.input;
  if (inp.tap) for (const k of KEYS) if (inp.tap.x >= k.x && inp.tap.x <= k.x + k.w && inp.tap.y >= k.y && inp.tap.y <= k.y + k.h) { type(g, k.ch); break; }
}

function soft(ctx, x, y, w, h, r, d0, fill) {
  const d = d0 * SC; ctx.save();
  ctx.shadowColor = DARK; ctx.shadowBlur = d * 1.8; ctx.shadowOffsetX = d * .7; ctx.shadowOffsetY = d * .7;
  A.rr(ctx, x, y, w, h, r); ctx.fillStyle = fill || BG; ctx.fill();
  ctx.shadowColor = LIGHT; ctx.shadowOffsetX = -d * .7; ctx.shadowOffsetY = -d * .7; ctx.fill(); ctx.restore();
}
/* широкое окно: что значат цвета — три плитки с подписями */
function legend(ctx) {
  const cx = P.x + P.w / 2, y = 262, s = 60, gap = 190;
  [['К', GOOD, 'на своём месте'], ['О', NEAR, 'есть, но не здесь'], ['Т', NO, 'нет в слове']].forEach(([ch, col, cap], i) => {
    const x = cx + (i - 1) * gap;
    A.rr(ctx, x - s / 2, y, s, s, 16); ctx.fillStyle = col; ctx.fill();
    A.text(ctx, ch, x, y + s / 2 + 2, { size: 34, weight: 800, color: '#fff' });
    A.text(ctx, cap, x, y + s + 28, { size: 20, weight: 600, color: MUTED });
  });
}
function draw(ctx, g) {
  SC = g.scale; const t = g.t;
  ctx.fillStyle = BG; ctx.fillRect(0, 0, W, H);
  const hx = LAND ? P.x + P.w / 2 : W / 2, hy = LAND ? -2 : 0;      // шапка: в широком окне — над правой колонкой
  A.text(ctx, 'Пять букв', hx, 104 + hy, { size: 60, weight: 900, color: INK });
  A.text(ctx, S.mode === 'play' ? (S.streak ? 'серия: ' + S.streak : 'угадайте слово') : 'угадайте слово из пяти букв', hx, 172 + hy, { size: 24, weight: 500, color: MUTED });
  if (LAND) legend(ctx);
  for (let r = 0; r < ROWS; r++) {
    const word = r < S.rows.length ? S.rows[r] : r === S.rows.length ? S.cur : '';
    const sx = r === S.rows.length && S.shake > 0 ? Math.sin(S.shake * 60) * 10 * S.shake : 0;
    for (let i = 0; i < LEN; i++) {
      const x = TX + i * (TS + TG) + sx, y = TY + r * (TS + TG), ch = word[i] || '';
      let m = r < S.marks.length ? S.marks[r][i] : null, sy = 1;
      if (S.flip && S.flip.row === r) { const k = (S.flip.t - i * .18) / .3; if (k < 0) m = null; else if (k < 1) { sy = Math.abs(Math.cos(k * Math.PI)); if (k < .5) m = null; } }
      ctx.save(); ctx.translate(x + TS / 2, y + TS / 2); ctx.scale(1, Math.max(.05, sy)); ctx.translate(-x - TS / 2, -y - TS / 2);
      if (m) { A.rr(ctx, x, y, TS, TS, TR); ctx.fillStyle = m === 'good' ? GOOD : m === 'near' ? NEAR : NO; ctx.fill(); }
      else soft(ctx, x, y, TS, TS, TR, ch ? 9 : 5);
      if (ch) A.text(ctx, ch.toUpperCase(), x + TS / 2, y + TS / 2 + 3, { size: TF, weight: 800, color: m ? '#fff' : INK });
      ctx.restore();
    }
  }
  // клавиатура
  KEYS = [];
  const ky0 = LAND ? TY + ROWS * (TS + TG) - TG - 3 * 74 - 2 * 8 : TY + ROWS * (TS + TG) + 40, kh = LAND ? 74 : 78, kg = 8;
  const kcx = LAND ? P.x + P.w / 2 : W / 2, kww = LAND ? P.w : W - 40;
  KB.forEach((row, ri) => {
    const chars = [...row], kw = (kww - kg * 11) / 12;
    const wide = (ch) => (ch === '↵' || ch === '⌫') ? kw * 1.5 + kg / 2 : kw;
    const tot = chars.reduce((a, ch) => a + wide(ch), 0) + kg * (chars.length - 1);
    let x = kcx - tot / 2; const y = ky0 + ri * (kh + kg);
    for (const ch of chars) {
      const w = wide(ch), st = S.keys[ch];
      if (st) { A.rr(ctx, x, y, w, kh, 16); ctx.fillStyle = st === 'good' ? GOOD : st === 'near' ? NEAR : '#c3ccd9'; ctx.fill(); }
      else soft(ctx, x, y, w, kh, 16, 5);
      A.text(ctx, ch === '↵' ? '✓' : ch === '⌫' ? '⌫' : ch.toUpperCase(), x + w / 2, y + kh / 2 + 2, { size: (ch.length && /[а-я]/.test(ch) ? 30 : 34) - (LAND ? 2 : 0), weight: 700, color: st && st !== 'no' ? '#fff' : st === 'no' ? 'rgba(36,50,74,.45)' : INK });
      KEYS.push({ x, y, w, h: kh, ch }); x += w + kg;
    }
  });
  if (S.msgT > 0) { const a = Math.min(1, S.msgT / .3); ctx.globalAlpha = a; soft(ctx, hx - 170, 196 + hy, 340, 44, 22, 4); A.text(ctx, S.msg, hx, 219 + hy, { size: 22, weight: 700, color: INK }); ctx.globalAlpha = 1; }
}

A.game({
  id: 'words', tone: 'light', title: 'Пять букв', width: W, height: H, orientation: LAND ? 'landscape' : 'portrait', music: 'garden',
  keys: { Enter: 'none', Space: 'none', KeyA: 'none', KeyD: 'none', KeyW: 'none', KeyS: 'none', KeyZ: 'none', KeyX: 'none', KeyJ: 'none', KeyK: 'none', KeyL: 'none', KeyM: 'none', KeyP: 'none', ArrowLeft: 'none', ArrowRight: 'none', ArrowUp: 'none', ArrowDown: 'none' },
  help: { desktop: 'Печатайте слово — раскладка любая · <kbd>Enter</kbd> — проверить · <kbd>Backspace</kbd> — стереть', short: 'Печатайте слово и нажмите <b>Enter</b>', touch: 'Набирайте слово на клавиатуре внизу и нажмите ✓' },
  init(g) { titleScreen(g); window.__words = () => S; },
  update, draw
});
})();
