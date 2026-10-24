/* Кроссворд — каждый раз новый: Dewiar сам составляет сетку из ~12 слов со своими вопросами (банк ниже).
   Коснитесь клетки — подсветится слово и вопрос, печатайте буквы (клавиатура на экране или обычная, раскладка любая).
   Слово угадано — зеленеет; неверно заполненное — мигает. «Подсказка» открывает букву (их три). */
(() => {
'use strict';
const A = Arcade;
/* Широкое окно (лист «Досуг» на компьютере) — своя раскладка 1280×720: сетка слева во всю высоту, справа — заголовок,
   «Подсказка», вопрос, номера слов (по ним можно щёлкать) и экранная клавиатура. Книжная — как прежде. */
const LAND = (() => { try { return innerWidth > (innerHeight - 110) * 1.15; } catch (e) { return false; } })();
const W = LAND ? 1280 : 720, H = LAND ? 720 : 1280;
const P = { x: 708, w: 536 };                    // широкое окно: правая колонка
const BANK = [["арбуз", "Большая полосатая ягода с красной мякотью"], ["радуга", "Разноцветная дуга на небе после дождя"], ["кошка", "Домашнее животное, которое мурлычет"], ["собака", "Друг человека, который лает"], ["ромашка", "Белый полевой цветок с жёлтой серединкой"], ["елка", "Её наряжают к Новому году"], ["солнце", "Звезда, вокруг которой вращается Земля"], ["луна", "Спутник Земли"], ["облако", "Белое и пушистое плывёт по небу"], ["дождь", "Капли с неба"], ["снег", "Зимние белые хлопья"], ["мороз", "Сильный зимний холод"], ["весна", "Время года, когда тает снег"], ["осень", "Время года, когда листья желтеют"], ["лето", "Самое тёплое время года"], ["зима", "Время года с метелями"], ["книга", "Её читают, перелистывая страницы"], ["перо", "Им когда-то писали чернилами"], ["тетрадь", "В ней пишут школьники"], ["карандаш", "Им рисуют и пишут, его точат"], ["пианино", "Клавишный музыкальный инструмент"], ["гитара", "Шестиструнный музыкальный инструмент"], ["скрипка", "Её держат у плеча и играют смычком"], ["барабан", "По нему стучат палочками"], ["театр", "Здесь играют спектакли"], ["кино", "Здесь смотрят фильмы на большом экране"], ["музей", "Здесь хранят и показывают картины и древности"], ["парк", "Место для прогулок с деревьями и скамейками"], ["река", "Течёт от истока к устью"], ["озеро", "Водоём, окружённый сушей"], ["море", "Большой солёный водоём"], ["океан", "Самый большой водоём"], ["остров", "Суша, со всех сторон окружённая водой"], ["гора", "Высокая вершина над равниной"], ["вулкан", "Огнедышащая гора"], ["пустыня", "Песчаные просторы без воды"], ["лес", "Много деревьев вместе"], ["поле", "Ровное пространство, где растёт пшеница"], ["сад", "Место, где растут яблони и груши"], ["огород", "Здесь растут морковь и картошка"], ["морковь", "Оранжевый корнеплод, любимый зайцами"], ["капуста", "Из неё варят щи"], ["картофель", "Его копают осенью, второй хлеб"], ["помидор", "Красный овощ для салата"], ["огурец", "Зелёный овощ, бывает солёным"], ["яблоко", "Круглый фрукт, бывает антоновкой"], ["груша", "Фрукт, похожий на лампочку"], ["вишня", "Маленькая красная ягода с косточкой"], ["малина", "Ягода, из которой варят варенье от простуды"], ["клубника", "Красная ягода с семечками снаружи"], ["лимон", "Кислый жёлтый цитрус"], ["апельсин", "Оранжевый цитрус"], ["банан", "Жёлтый изогнутый тропический фрукт"], ["хлеб", "Его пекут из муки"], ["молоко", "Белый напиток от коровы"], ["сыр", "Из него делают бутерброды, бывает с дырками"], ["масло", "Его мажут на хлеб"], ["каша", "Её варят из крупы"], ["суп", "Первое блюдо, которое едят ложкой"], ["чай", "Горячий напиток из листьев"], ["кофе", "Бодрящий напиток из зёрен"], ["сахар", "Сладкий кристаллический продукт"], ["мед", "Сладкий продукт пчёл"], ["пирог", "Выпечка с начинкой"], ["торт", "Праздничный десерт со свечами"], ["конфета", "Сладость в фантике"], ["ложка", "Ею едят суп"], ["вилка", "Столовый прибор с зубчиками"], ["нож", "Им режут хлеб"], ["тарелка", "На неё кладут еду"], ["чашка", "Из неё пьют чай"], ["чайник", "В нём кипятят воду"], ["окно", "Через него смотрят на улицу"], ["дверь", "Через неё входят в дом"], ["стол", "За ним обедают"], ["стул", "На нём сидят"], ["диван", "Мягкая мебель для отдыха"], ["шкаф", "В нём хранят одежду"], ["лампа", "Она светит вечером"], ["зеркало", "В нём видно своё отражение"], ["часы", "Они показывают время"], ["телефон", "По нему звонят"], ["компьютер", "Умная машина с клавиатурой и экраном"], ["экран", "На нём показывают изображение"], ["письмо", "Его отправляют по почте"], ["почта", "Здесь отправляют посылки"], ["поезд", "Едет по рельсам"], ["самолет", "Летит по небу с пассажирами"], ["корабль", "Большое судно"], ["велосипед", "Двухколёсный транспорт с педалями"], ["автобус", "Городской транспорт с остановками"], ["метро", "Подземный городской поезд"], ["дорога", "По ней едут машины"], ["мост", "Переход через реку"], ["город", "Большой населённый пункт"], ["деревня", "Небольшое село"], ["улица", "Ряд домов по обе стороны дороги"], ["площадь", "Большое открытое место в центре города"], ["школа", "Здесь учатся дети"], ["учитель", "Он ведёт уроки"], ["врач", "Он лечит людей"], ["повар", "Он готовит еду"], ["пилот", "Он управляет самолётом"], ["художник", "Он рисует картины"], ["писатель", "Он пишет книги"], ["певец", "Он исполняет песни"], ["доктор", "Другое название врача"], ["мама", "Самый родной человек"], ["бабушка", "Мама мамы или папы"], ["дедушка", "Папа мамы или папы"], ["брат", "Сын тех же родителей"], ["сестра", "Дочь тех же родителей"], ["друг", "Близкий человек, с которым дружат"], ["семья", "Родители и дети вместе"], ["праздник", "Торжественный день"], ["подарок", "Его дарят на день рождения"], ["шарик", "Воздушный, бывает на празднике"], ["игрушка", "С ней играют дети"], ["кукла", "Игрушка для девочек"], ["мяч", "Его пинают в футболе"], ["футбол", "Игра с мячом и воротами"], ["хоккей", "Игра на льду с шайбой"], ["шахматы", "Игра с королём и ферзём"], ["лыжи", "На них катаются по снегу"], ["коньки", "На них катаются по льду"], ["санки", "На них катаются с горки"], ["зонт", "Защищает от дождя"], ["шапка", "Головной убор"], ["шарф", "Его повязывают на шею"], ["перчатки", "Одежда для рук"], ["сапоги", "Высокая обувь"], ["платье", "Женская одежда"], ["рубашка", "Одежда с воротником и пуговицами"], ["пуговица", "Ею застёгивают одежду"], ["ключ", "Им открывают замок"], ["замок", "Его закрывают ключом"], ["звезда", "Светится ночью на небе"], ["планета", "Земля — это…"], ["ракета", "На ней летят в космос"], ["космос", "Пространство за пределами Земли"], ["ветер", "Движение воздуха"], ["гроза", "Дождь с громом и молнией"], ["молния", "Вспышка во время грозы"], ["туман", "Густая дымка над землёй"], ["утро", "Начало дня"], ["вечер", "Конец дня"], ["ночь", "Время сна"], ["неделя", "Семь дней"], ["месяц", "Примерно тридцать дней"], ["год", "Двенадцать месяцев"], ["пчела", "Насекомое, которое делает мёд"], ["бабочка", "Насекомое с яркими крыльями"], ["муравей", "Трудолюбивый житель муравейника"], ["птица", "У неё есть крылья и перья"], ["ворона", "Чёрная каркающая птица"], ["сова", "Ночная птица с большими глазами"], ["орел", "Гордая хищная птица"], ["лебедь", "Белая птица с длинной шеей"], ["рыба", "Живёт в воде, дышит жабрами"], ["кит", "Самое большое животное в океане"], ["дельфин", "Умное морское животное"], ["медведь", "Хозяин леса, любит мёд"], ["волк", "Серый лесной хищник"], ["лиса", "Рыжая хитрая плутовка"], ["заяц", "Длинноухий прыгун"], ["ежик", "Колючий лесной житель"], ["белка", "Рыжая, прыгает по веткам с орешками"], ["лошадь", "Животное, на котором ездят верхом"], ["корова", "Даёт молоко"], ["коза", "Рогатая, тоже даёт молоко"], ["слон", "Животное с хоботом"], ["жираф", "Животное с самой длинной шеей"], ["тигр", "Полосатая большая кошка"], ["лев", "Царь зверей"], ["обезьяна", "Ловко лазает по деревьям, любит бананы"], ["черепаха", "Носит домик на спине"], ["змея", "Ползучее животное без ног"], ["роза", "Цветок с шипами"], ["тюльпан", "Весенний цветок из луковицы"], ["береза", "Дерево с белой корой"], ["дуб", "Могучее дерево с желудями"], ["сосна", "Хвойное дерево с длинными иглами"], ["песня", "Её поют"], ["сказка", "Волшебная история для детей"], ["загадка", "Её надо отгадать"], ["мечта", "То, чего очень хочется"], ["улыбка", "Радостное выражение лица"], ["смех", "Звук веселья"], ["сон", "Отдых ночью"], ["память", "Способность помнить"]];
const INK = '#2f2a4a', BG1 = '#fdf6ec', BG2 = '#f1ecff', ACC = '#7b6cf0', GOOD = '#3fb984', BAD = '#e5486a';
const KB = ['йцукенгшщзхъ', 'фывапролджэ', 'ячсмитьбю⌫'];
const RU = {}; 'KeyQ й KeyW ц KeyE у KeyR к KeyT е KeyY н KeyU г KeyI ш KeyO щ KeyP з BracketLeft х BracketRight ъ KeyA ф KeyS ы KeyD в KeyF а KeyG п KeyH р KeyJ о KeyK л KeyL д Semicolon ж Quote э KeyZ я KeyX ч KeyC с KeyV м KeyB и KeyN т KeyM ь Comma б Period ю Backquote е'
  .split(' ').forEach((v, i, a) => { if (i % 2 === 0) RU[v] = a[i + 1]; });
const GY = LAND ? 40 : 160, GH = 640;
const GX0 = 44, GW = 616;                       // широкое окно: место под сетку слева
let S = null, KEYS = [], HINT_BTN = null, CHIPS = [];

/* ---------------- составитель ---------------- */
function build() {
  for (let attempt = 0; attempt < 30; attempt++) {
    const pool = BANK.slice().sort(() => Math.random() - .5).filter((x) => x[0].length >= 4 && x[0].length <= 9);
    const cells = new Map(), words = [];
    const key = (x, y) => x + ',' + y;
    const at = (x, y) => cells.get(key(x, y));
    const canPlace = (w, x, y, dir) => {
      const dx = dir ? 0 : 1, dy = dir ? 1 : 0; let cross = 0;
      if (at(x - dx, y - dy) || at(x + dx * w.length, y + dy * w.length)) return -1;
      for (let i = 0; i < w.length; i++) {
        const cx = x + dx * i, cy = y + dy * i, c = at(cx, cy);
        if (c) { if (c.ch !== w[i] || c.dirs.includes(dir)) return -1; cross++; }
        else if (at(cx + dy, cy + dx) || at(cx - dy, cy - dx)) return -1;     // соседи сбоку — только на пересечениях
      }
      return cross;
    };
    const place = (w, clue, x, y, dir) => {
      const dx = dir ? 0 : 1, dy = dir ? 1 : 0;
      for (let i = 0; i < w.length; i++) { const k = key(x + dx * i, y + dy * i), c = cells.get(k); if (c) c.dirs.push(dir); else cells.set(k, { ch: w[i], dirs: [dir] }); }
      words.push({ w, clue, x, y, dir });
    };
    const first = pool.shift(); place(first[0], first[1], 0, 0, 0);
    for (const [w, clue] of pool) {
      if (words.length >= 13) break;
      if (words.some((o) => o.w === w)) continue;
      let best = null;
      for (const o of words) for (let i = 0; i < o.w.length; i++) for (let j = 0; j < w.length; j++) {
        if (o.w[i] !== w[j]) continue;
        const dir = 1 - o.dir, ox = o.x + (o.dir ? 0 : i), oy = o.y + (o.dir ? i : 0);
        const x = ox - (dir ? 0 : j), y = oy - (dir ? j : 0);
        const c = canPlace(w, x, y, dir); if (c < 1) continue;
        const xs = [...cells.keys()].map((k) => +k.split(',')[0]).concat([x, x + (dir ? 0 : w.length - 1)]);
        const ys = [...cells.keys()].map((k) => +k.split(',')[1]).concat([y, y + (dir ? w.length - 1 : 0)]);
        const span = Math.max(Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys)) + 1;
        if (span > 13) continue;
        const sc = c * 10 - span + Math.random();
        if (!best || sc > best.sc) best = { sc, x, y, dir };
      }
      if (best) place(w, clue, best.x, best.y, best.dir);
    }
    if (words.length < 9) continue;
    const xs = [...cells.keys()].map((k) => +k.split(',')[0]), ys = [...cells.keys()].map((k) => +k.split(',')[1]);
    const mx = Math.min(...xs), my = Math.min(...ys), cols = Math.max(...xs) - mx + 1, rows = Math.max(...ys) - my + 1;
    const grid = Array.from({ length: rows }, () => Array(cols).fill(null));
    for (const [k, c] of cells) { const [x, y] = k.split(',').map(Number); grid[y - my][x - mx] = { ch: c.ch, v: '', ok: false, hint: false, num: 0 }; }
    words.forEach((o) => { o.x -= mx; o.y -= my; });
    // номера — по порядку чтения
    let n = 0; const starts = new Map();
    for (let y = 0; y < rows; y++) for (let x = 0; x < cols; x++) if (words.some((o) => o.x === x && o.y === y)) { starts.set(x + ',' + y, ++n); grid[y][x].num = n; }
    words.forEach((o) => { o.num = starts.get(o.x + ',' + o.y); o.done = false; });
    words.sort((a, b) => a.dir - b.dir || a.num - b.num);
    return { grid, words, cols, rows };
  }
  return null;
}

function cellsOf(o) { return [...o.w].map((_, i) => ({ x: o.x + (o.dir ? 0 : i), y: o.y + (o.dir ? i : 0) })); }
function fresh(mode) {
  const b = build();
  S = { mode, ...b, cur: 0, pos: 0, hints: 3, time: 0, done: 0, flash: {}, demo: 0, solvedT: {} };
  if (LAND) {
    const cs = Math.min(64, Math.floor(GW / b.cols), Math.floor(GH / b.rows));
    S.cs = cs; S.gx = GX0 + (GW - cs * b.cols) / 2; S.gy = GY + (GH - cs * b.rows) / 2;
    return S;
  }
  const cs = Math.min(58, Math.floor((W - 60) / b.cols), Math.floor(GH / b.rows));
  S.cs = cs; S.gx = (W - cs * b.cols) / 2; S.gy = GY + (GH - cs * b.rows) / 2;
  return S;
}
const word = () => S.words[S.cur];
function selectAt(x, y) {
  const ws = S.words.map((o, i) => ({ o, i })).filter(({ o }) => cellsOf(o).some((c) => c.x === x && c.y === y));
  if (!ws.length) return;
  let pick = ws.find(({ i }) => i === S.cur);
  if (pick && ws.length > 1 && cellsOf(word())[S.pos] && cellsOf(word())[S.pos].x === x && cellsOf(word())[S.pos].y === y) pick = ws.find(({ i }) => i !== S.cur);
  pick = pick || ws.find(({ o }) => o.dir === (word() ? word().dir : 0)) || ws[0];
  S.cur = pick.i; S.pos = cellsOf(pick.o).findIndex((c) => c.x === x && c.y === y);
}
function nextWord(step = 1) {
  for (let k = 1; k <= S.words.length; k++) { const i = (S.cur + step * k + S.words.length * 2) % S.words.length; if (!S.words[i].done) { S.cur = i; S.pos = Math.max(0, cellsOf(S.words[i]).findIndex((c) => !S.grid[c.y][c.x].ok && !S.grid[c.y][c.x].v)); return; } }
}
function check(g) {
  for (const o of S.words) {
    if (o.done) continue;
    const cs = cellsOf(o), full = cs.every((c) => S.grid[c.y][c.x].v);
    if (!full) continue;
    if (cs.every((c) => S.grid[c.y][c.x].v === S.grid[c.y][c.x].ch)) {
      o.done = true; cs.forEach((c) => { S.grid[c.y][c.x].ok = true; }); S.solvedT[S.words.indexOf(o)] = 0;
      if (S.mode === 'play') { g.sfx('coin'); const m = cs[(cs.length / 2) | 0]; g.fx.burst(S.gx + (m.x + .5) * S.cs, S.gy + (m.y + .5) * S.cs, { n: 12, colors: [GOOD, '#fff', '#ffd166'], speed: 240, size: 7, shape: 'star', life: .7 }); }
    } else if (S.mode === 'play') { S.flash[S.words.indexOf(o)] = .6; g.sfx('hurt', { vol: .3, pitch: 1.3 }); }
  }
  if (S.words.every((o) => o.done) && !S.done) { S.done = .001; if (S.mode === 'play') { g.sfx('win'); g.stopMusic(); } }
}
function type(g, ch) {
  if (S.done || S.mode !== 'play') return;
  const cs = cellsOf(word());
  if (ch === '⌫') {
    let c = cs[S.pos]; if (c && !S.grid[c.y][c.x].v && S.pos > 0) { S.pos--; c = cs[S.pos]; }
    const cell = S.grid[c.y][c.x]; if (!cell.ok) cell.v = ''; g.sfx('click', { vol: .3 }); return;
  }
  const c = cs[S.pos], cell = S.grid[c.y][c.x];
  if (!cell.ok) cell.v = ch;
  g.sfx('click', { vol: .4, pitch: 1.15 });
  let p = S.pos + 1; while (p < cs.length && S.grid[cs[p].y][cs[p].x].ok) p++;
  S.pos = Math.min(p, cs.length - 1);
  const was = word(); check(g);
  if (was.done) nextWord(1);
}
function pickWord(g, i) {                       // широкое окно: щелчок по номеру слова
  const o = S.words[i]; if (!o || o.done) return;
  S.cur = i; S.pos = Math.max(0, cellsOf(o).findIndex((c) => !S.grid[c.y][c.x].ok && !S.grid[c.y][c.x].v));
  g.sfx('click', { vol: .3 });
}
function hint(g) {
  if (S.hints <= 0 || S.mode !== 'play' || S.done) return;
  const cs = cellsOf(word()), c = cs.find((q) => S.grid[q.y][q.x].v !== S.grid[q.y][q.x].ch) || cs[S.pos];
  const cell = S.grid[c.y][c.x]; if (cell.v === cell.ch) return;
  cell.v = cell.ch; cell.hint = true; S.hints--; g.sfx('pling');
  const was = word(); check(g); if (was.done) nextWord(1);
}

/* ---------------- экраны ---------------- */
function titleScreen(g) {
  fresh('title'); g.setPlaying(false);
  g.screen({
    kicker: A.framed ? 'Досуг' : 'Аркада', title: 'Кроссворд',
    html: '<p>Каждый раз — новый кроссворд из простых слов. Коснитесь клетки, прочитайте вопрос и впишите ответ. Три подсказки на партию.</p>' + (g.best ? '<p class="record">Рекорд: ' + g.best.toLocaleString('ru-RU') + '</p>' : ''),
    button: 'Играть', onGo: () => start(g)
  });
}
function start(g) { fresh('play'); g.fx.clear(); g.setPlaying(true); g.playMusic(); }
function finish(g) {
  S.mode = 'over'; g.setPlaying(false);
  const sc = Math.max(200, Math.round(1500 + S.words.length * 120 - (3 - S.hints) * 200 - S.time * 1.5)), rec = g.submit(sc);
  const mm = Math.floor(S.time / 60), ss = String(Math.floor(S.time % 60)).padStart(2, '0');
  for (let k = 0; k < 6; k++) g.fx.burst(Math.random() * W, GY + Math.random() * GH, { n: 12, colors: [ACC, GOOD, '#ffd166', '#ff8fb8'], speed: 320, size: 8, life: 1, gravity: 500, shape: 'star' });
  g.screen({
    kicker: 'Разгадано!', title: rec ? 'Новый рекорд!' : 'Браво!',
    html: '<div class="score">' + sc.toLocaleString('ru-RU') + '</div><p>слов ' + S.words.length + ' · ' + mm + ':' + ss + ' · подсказок ' + (3 - S.hints) + '</p>',
    button: 'Новый кроссворд', onGo: () => start(g), alt: { label: A.framed ? 'К играм' : 'В аркаду', onGo: () => A.home('../index.html') }
  });
}

/* ---------------- цикл ---------------- */
let typed = [];
addEventListener('keydown', (e) => {
  if (e.ctrlKey || e.metaKey || e.altKey) return;
  let k = (e.key || '').toLowerCase().replace('ё', 'е');
  if (!/^[а-я]$/.test(k) && RU[e.code]) k = RU[e.code];
  if (/^[а-я]$/.test(k)) { typed.push(k); e.preventDefault(); }
  else if (e.key === 'Backspace') { typed.push('⌫'); e.preventDefault(); }
  else if (e.key === 'Tab') { typed.push(e.shiftKey ? 'prev' : 'next'); e.preventDefault(); }
});
function update(g, dt) {
  for (const k in S.flash) { S.flash[k] -= dt; if (S.flash[k] <= 0) delete S.flash[k]; }
  for (const k in S.solvedT) S.solvedT[k] += dt;
  if (S.mode === 'title') {
    S.demo += dt;
    if (S.demo > .12) { S.demo = 0; const o = S.words.find((q) => !q.done); if (!o) return fresh('title');
      S.cur = S.words.indexOf(o); const c = cellsOf(o).find((q) => S.grid[q.y][q.x].v !== S.grid[q.y][q.x].ch);
      if (c) { S.grid[c.y][c.x].v = S.grid[c.y][c.x].ch; S.pos = cellsOf(o).indexOf(c); } check(g); }
    typed = []; return;
  }
  if (S.mode !== 'play') { typed = []; return; }
  if (S.done) { S.done += dt; if (S.done > 1.2) finish(g); typed = []; return; }
  S.time += dt;
  for (const ch of typed) { if (ch === 'next') nextWord(1); else if (ch === 'prev') nextWord(-1); else type(g, ch); }
  typed = [];
  const inp = g.input;
  if (inp.pressed('right')) S.pos = Math.min(S.pos + 1, word().w.length - 1);
  if (inp.pressed('left')) S.pos = Math.max(S.pos - 1, 0);
  if (inp.pressed('down')) nextWord(1);
  if (inp.pressed('up')) nextWord(-1);
  if (inp.tap) {
    const { x, y } = inp.tap;
    const gx = Math.floor((x - S.gx) / S.cs), gy = Math.floor((y - S.gy) / S.cs);
    if (gy >= 0 && gx >= 0 && gy < S.rows && gx < S.cols && S.grid[gy][gx]) { selectAt(gx, gy); g.sfx('click', { vol: .3 }); }
    else if (HINT_BTN && x >= HINT_BTN.x && x <= HINT_BTN.x + HINT_BTN.w && y >= HINT_BTN.y && y <= HINT_BTN.y + HINT_BTN.h) hint(g);
    else {
      let hit = false;
      for (const k of KEYS) if (x >= k.x && x <= k.x + k.w && y >= k.y && y <= k.y + k.h) { type(g, k.ch); hit = true; break; }
      if (!hit) for (const c of CHIPS) if (x >= c.x && x <= c.x + c.w && y >= c.y && y <= c.y + c.h) { pickWord(g, c.i); break; }
    }
  }
}

function wrapText(ctx, str, maxW, size) {
  ctx.font = '600 ' + size + 'px ' + A.FONT;
  const out = []; let line = '';
  for (const w of str.split(' ')) { const t = line ? line + ' ' + w : w; if (ctx.measureText(t).width > maxW && line) { out.push(line); line = w; } else line = t; }
  if (line) out.push(line); return out;
}
function drawGrid(ctx) {
  const cs = S.cs, cur = word(), curCells = cur ? cellsOf(cur) : [];
  for (let y = 0; y < S.rows; y++) for (let x = 0; x < S.cols; x++) {
    const c = S.grid[y][x]; if (!c) continue;
    const px = S.gx + x * cs, py = S.gy + y * cs;
    const inCur = curCells.some((q) => q.x === x && q.y === y), isPos = curCells[S.pos] && curCells[S.pos].x === x && curCells[S.pos].y === y;
    const flashing = S.words.some((o, i) => S.flash[i] && cellsOf(o).some((q) => q.x === x && q.y === y));
    A.rr(ctx, px + 2, py + 2, cs - 4, cs - 4, cs * .22);
    ctx.fillStyle = flashing && Math.floor(S.flash[Object.keys(S.flash)[0]] * 10) % 2 ? 'rgba(229,72,106,.25)' : c.ok ? 'rgba(63,185,132,.2)' : isPos && S.mode === 'play' ? 'rgba(123,108,240,.35)' : inCur && S.mode === 'play' ? 'rgba(123,108,240,.14)' : '#fff';
    ctx.fill(); ctx.lineWidth = 2; ctx.strokeStyle = 'rgba(47,42,74,.14)'; ctx.stroke();
    if (c.num) {
      if (LAND) A.text(ctx, String(c.num), px + 5 + cs * .04, py + 6 + cs * .12, { align: 'left', size: Math.max(13, cs * .25), weight: 700, color: 'rgba(47,42,74,.5)' });
      else A.text(ctx, String(c.num), px + 7, py + 13, { align: 'left', size: Math.max(11, cs * .22), weight: 700, color: 'rgba(47,42,74,.5)' });
    }
    if (c.v) A.text(ctx, c.v.toUpperCase(), px + cs / 2, py + cs / 2 + 3, { size: cs * .52, weight: 800, color: c.ok ? '#2b8c5f' : c.hint ? ACC : INK });
  }
}
/* клавиатура: ряды по центру cx, ширина ряда — ww */
function drawKeys(ctx, cx, ww, ky0, kh, kg, fs) {
  KEYS = [];
  KB.forEach((row, ri) => {
    const chars = [...row], kw = (ww - kg * 11) / 12;
    const wide = (ch) => (ch === '⌫' ? kw * 1.6 : kw);
    const tot = chars.reduce((a, ch) => a + wide(ch), 0) + kg * (chars.length - 1);
    let x = cx - tot / 2; const y = ky0 + ri * (kh + kg);
    for (const ch of chars) {
      const w = wide(ch);
      A.rr(ctx, x, y, w, kh, 14); ctx.fillStyle = '#fff'; ctx.fill(); ctx.lineWidth = 2; ctx.strokeStyle = 'rgba(47,42,74,.08)'; ctx.stroke();
      A.text(ctx, ch === '⌫' ? '⌫' : ch.toUpperCase(), x + w / 2, y + kh / 2 + 2, { size: fs, weight: 700, color: INK });
      KEYS.push({ x, y, w, h: kh, ch }); x += w + kg;
    }
  });
}
function arrow(ctx, x, y, dir, col) {               // маленькая стрелка «→» или «↓»
  ctx.save(); ctx.translate(x, y); if (dir) ctx.rotate(Math.PI / 2);
  ctx.strokeStyle = col; ctx.lineWidth = 3.5; ctx.lineCap = 'round'; ctx.lineJoin = 'round';
  ctx.beginPath(); ctx.moveTo(-10, 0); ctx.lineTo(10, 0); ctx.moveTo(3, -7); ctx.lineTo(10, 0); ctx.lineTo(3, 7); ctx.stroke();
  ctx.restore();
}
function drawLand(ctx, g) {
  const bg = ctx.createLinearGradient(0, 0, W, H); bg.addColorStop(0, BG1); bg.addColorStop(1, BG2);
  ctx.fillStyle = bg; ctx.fillRect(0, 0, W, H);
  // подложка под сетку — мягкая бумажная доска
  A.rr(ctx, GX0 - 16, GY - 16, GW + 32, GH + 32, 34); ctx.fillStyle = 'rgba(255,255,255,.42)'; ctx.fill();
  ctx.lineWidth = 2; ctx.strokeStyle = 'rgba(123,108,240,.10)'; ctx.stroke();
  drawGrid(ctx);
  const cur = word(), px = P.x, pw = P.w;
  // заголовок и счёт
  A.text(ctx, 'Кроссворд', px, 56, { align: 'left', size: 50, weight: 900, color: INK });
  const solved = S.words.filter((o) => o.done).length;
  A.text(ctx, 'слов ' + solved + ' из ' + S.words.length, px + 2, 104, { align: 'left', size: 24, weight: 600, color: 'rgba(47,42,74,.55)' });
  HINT_BTN = { x: px + pw - 204, y: 24, w: 204, h: 66 };
  if (S.mode !== 'title') {
    const hb = HINT_BTN, on = S.hints > 0;
    A.rr(ctx, hb.x, hb.y, hb.w, hb.h, 22); ctx.fillStyle = on ? '#fff' : 'rgba(255,255,255,.5)'; ctx.fill();
    ctx.lineWidth = 2; ctx.strokeStyle = 'rgba(47,42,74,.1)'; ctx.stroke();
    A.text(ctx, '💡 Подсказка ' + S.hints, hb.x + hb.w / 2, hb.y + hb.h / 2 + 2, { size: 22, weight: 700, color: on ? INK : 'rgba(47,42,74,.35)' });
  }
  // вопрос
  const qy = 134, qh = 160;
  A.rr(ctx, px, qy, pw, qh, 24); ctx.fillStyle = '#fff'; ctx.fill();
  if (cur && S.mode !== 'title') {
    A.text(ctx, cur.num + ' ' + (cur.dir ? 'по вертикали' : 'по горизонтали') + ' · ' + cur.w.length + ' букв', px + 24, qy + 32, { align: 'left', size: 20, weight: 700, color: ACC });
    const lines = wrapText(ctx, cur.clue, pw - 48, 28).slice(0, 3), ly = qy + 52 + (qh - 64 - lines.length * 34) / 2 + 17;
    lines.forEach((l, i) => A.text(ctx, l, px + 24, ly + i * 34, { align: 'left', size: 28, weight: 600, color: INK }));
  } else A.text(ctx, 'Новый кроссворд — каждый раз', px + pw / 2, qy + qh / 2, { size: 26, weight: 600, color: 'rgba(47,42,74,.5)' });
  // номера слов: по горизонтали и по вертикали
  CHIPS = [];
  const ch = 44, cg = 8, lx = 34;
  [0, 1].forEach((dir, ri) => {
    const list = S.words.map((o, i) => ({ o, i })).filter(({ o }) => o.dir === dir);
    const y = 320 + ri * (ch + 12);
    arrow(ctx, px + 14, y + ch / 2, dir, 'rgba(47,42,74,.4)');
    const cw = Math.min(54, (pw - lx - cg * (list.length - 1)) / Math.max(1, list.length));
    list.forEach(({ o, i }, k) => {
      const x = px + lx + k * (cw + cg), isCur = i === S.cur && S.mode === 'play';
      A.rr(ctx, x, y, cw, ch, 14);
      ctx.fillStyle = o.done ? 'rgba(63,185,132,.22)' : isCur ? ACC : '#fff'; ctx.fill();
      ctx.lineWidth = 2; ctx.strokeStyle = o.done ? 'rgba(63,185,132,.35)' : 'rgba(47,42,74,.08)'; ctx.stroke();
      A.text(ctx, String(o.num), x + cw / 2, y + ch / 2 + 2, { size: 22, weight: 800, color: o.done ? '#2b8c5f' : isCur ? '#fff' : INK });
      CHIPS.push({ x, y, w: cw, h: ch, i });
    });
  });
  // клавиатура
  drawKeys(ctx, px + pw / 2, pw, 476, 68, 8, 27);
}
function draw(ctx, g) {
  if (LAND) return drawLand(ctx, g);
  const bg = ctx.createLinearGradient(0, 0, 0, H); bg.addColorStop(0, BG1); bg.addColorStop(1, BG2);
  ctx.fillStyle = bg; ctx.fillRect(0, 0, W, H);
  A.text(ctx, 'Кроссворд', 36, 70, { align: 'left', size: 52, weight: 900, color: INK });
  const solved = S.words.filter((o) => o.done).length;
  A.text(ctx, 'слов ' + solved + ' из ' + S.words.length, 38, 122, { align: 'left', size: 24, weight: 600, color: 'rgba(47,42,74,.55)' });
  // подсказка
  HINT_BTN = { x: W - 36 - 210, y: 52, w: 210, h: 70 };
  if (S.mode !== 'title') {
    const hb = HINT_BTN, on = S.hints > 0;
    A.rr(ctx, hb.x, hb.y, hb.w, hb.h, 22); ctx.fillStyle = on ? '#fff' : 'rgba(255,255,255,.5)'; ctx.fill();
    ctx.lineWidth = 2; ctx.strokeStyle = 'rgba(47,42,74,.1)'; ctx.stroke();
    A.text(ctx, '💡 Подсказка ' + S.hints, hb.x + hb.w / 2, hb.y + hb.h / 2 + 2, { size: 22, weight: 700, color: on ? INK : 'rgba(47,42,74,.35)' });
  }
  // сетка
  const cur = word();
  drawGrid(ctx);
  // вопрос
  const qy = GY + GH + 24;
  A.rr(ctx, 30, qy, W - 60, 118, 24); ctx.fillStyle = '#fff'; ctx.fill();
  if (cur && S.mode !== 'title') {
    A.text(ctx, cur.num + ' ' + (cur.dir ? 'по вертикали' : 'по горизонтали') + ' · ' + cur.w.length + ' букв', 54, qy + 28, { align: 'left', size: 20, weight: 700, color: ACC });
    const lines = wrapText(ctx, cur.clue, W - 108, 28).slice(0, 2);
    lines.forEach((l, i) => A.text(ctx, l, 54, qy + 64 + i * 34, { align: 'left', size: 28, weight: 600, color: INK }));
  } else A.text(ctx, 'Новый кроссворд — каждый раз', W / 2, qy + 60, { size: 26, weight: 600, color: 'rgba(47,42,74,.5)' });
  // клавиатура
  drawKeys(ctx, W / 2, W - 40, qy + 140, 70, 7, 28);
}

A.game({
  id: 'crossword', tone: 'light', title: 'Кроссворд', width: W, height: H, orientation: LAND ? 'landscape' : 'portrait', music: 'garden',
  keys: { Enter: 'none', Space: 'none', KeyA: 'none', KeyD: 'none', KeyW: 'none', KeyS: 'none', KeyZ: 'none', KeyX: 'none', KeyJ: 'none', KeyK: 'none', KeyL: 'none', KeyM: 'none', KeyP: 'none' },
  help: { desktop: 'Щёлкните клетку и печатайте (раскладка любая) · <kbd>Tab</kbd> — следующее слово · <kbd>Backspace</kbd> — стереть', short: 'Щёлкните клетку и печатайте ответ', touch: 'Коснитесь клетки и набирайте ответ на клавиатуре внизу' },
  init(g) { titleScreen(g); window.__cross = () => S; },
  update, draw
});
})();
