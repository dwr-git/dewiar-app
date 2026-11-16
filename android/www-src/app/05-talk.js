//@ Телефон и веб-версия, часть 05: длинный разговор, персонажи и облик, состояние разговора, разрешения.
//@ Собирается в android/assets/www/app.js (tools/app_join.py) — порядок частей = порядок исполнения; шапка «//@» в app.js не попадает.
/* ---------- длинный разговор (как на компьютере, core/conversation.py) ----------
   Последние 8 пар реплик — модели дословно; когда сверх них накопится ещё 4 пары, модель в фоне сворачивает старое
   в краткое содержание, и оно идёт в системную подсказку. Свёрнутые реплики помечены f:1 (в «Разговоре» их видно, модели они не уходят).
   8 часов тишины или «начнём новый разговор» — новый разговор. Перерыв дольше 20 минут модель видит. */
const CONV_TURNS = 8, CONV_MARGIN = 4, CONV_KEEP = 8 * 3600e3;
const CONV_SUM = "Ты ведёшь краткое содержание долгого разговора голосового ассистента с пользователем — чтобы ассистент не забыл важное из начала. "
  + "Обнови содержание по новым репликам: о чём говорили; факты, имена, числа, даты; решения и договорённости; что пользователь просил и что сделано; "
  + "открытые вопросы; на чём остановились. Пиши по-русски, коротко, пунктами, от третьего лица («Пользователь…», «Ассистент…»). "
  + "Ничего не выдумывай и не добавляй советов. Не больше 18 пунктов, самое старое и мелкое — сокращай. Верни только содержание, без вступлений.";
let conv = (() => { try { return Object.assign({ summary: "", turns: 0, started: 0, last: 0 }, JSON.parse(prefGet("conv") || "{}")); } catch (e) { return { summary: "", turns: 0, started: 0, last: 0 }; } })();
let convBusy = false;
const saveConv = () => prefSet("conv", JSON.stringify(conv));
const liveHistory = () => history.filter(m => !m.f);
function convReset() { history.forEach(m => { m.f = 1; }); saveH(); conv = { summary: "", turns: 0, started: 0, last: 0 }; saveConv(); lastPics = null; }
function convCheck() { if (conv.last && Date.now() - conv.last > CONV_KEEP) convReset(); }
function convAfter() {
  const now = Date.now(); if (!conv.started) conv.started = now;
  conv.last = now; conv.turns++; saveConv();
  if (liveHistory().length > 2 * (CONV_TURNS + CONV_MARGIN) && !convBusy && S.llm.base_url) convFold();
}
async function convFold() {
  convBusy = true;
  try {
    const live = liveHistory(), old = live.slice(0, live.length - 2 * CONV_TURNS);
    if (old.length < 2) return;
    const lines = old.map(m => (m.role === "user" ? "Пользователь: " : "Ассистент: ") + String(m.content || "").slice(0, 1500)).join("\n");
    const msg = (conv.summary ? "Содержание разговора до сих пор:\n" + conv.summary + "\n\n" : "") + "Новые реплики:\n" + lines;
    const r = await llmStream([{ role: "system", content: CONV_SUM }, { role: "user", content: msg.slice(-24000) }], null, null);
    const text = String(r.text || "").replace(/^\s*(?:Краткое\s+)?содержание[^\n:]*:\s*/i, "").trim();
    if (text.length < 20) return;
    conv.summary = text.slice(0, 3000); saveConv();
    old.forEach(m => { m.f = 1; }); saveH();
  } catch (e) { console.log("разговор: свернуть не вышло — " + e.message); }
  finally { convBusy = false; }
}
function convPrompt() {                         // в подсказку — только редко меняющееся (содержание раньше сказанного)
  return conv.summary ? "Это продолжение долгого разговора. Раньше в нём было (кратко):\n" + conv.summary
    + "\nОпирайся на это, если пользователь возвращается к прежнему, — не переспрашивай то, что уже известно. Последние реплики — ниже, дословно." : "";
}
function convNote() {                           // сколько идёт разговор и перерыв — в справку к вопросу (turnContext)
  const out = [];
  if (conv.summary) { const mins = conv.started ? Math.round((Date.now() - conv.started) / 60000) : 0;
    out.push(`Разговор идёт ${mins >= 60 ? Math.floor(mins / 60) + " ч " + (mins % 60) + " мин" : mins + " мин"}, ${conv.turns} реплик.`); }
  const gap = conv.last ? Date.now() - conv.last : 0;
  if (gap > 20 * 60000) { const g = Math.round(gap / 60000);
    out.push(`Перед этим сообщением в разговоре был перерыв ${g >= 60 ? Math.floor(g / 60) + " ч " + (g % 60) + " мин" : g + " мин"}. Если новая просьба не связана с прежней темой — просто выполни её, не возвращаясь к старому.`); }
  return out.join(" ");
}
/* Справка к вопросу: время, ближайшая неделя (экзамен 11.10: «в среду» не считать в уме), разговор, найденное. Кладётся
   в начало последнего сообщения пользователя (putContext), не в подсказку и не в историю. */
/* Ближайшая неделя и «считай calc» — только к вопросу про даты и сроки: раньше шли к каждому, и ассистенты сами заводили
   речь о днях рождения и подсчёте дней (письмо пользователя 23.10; то же — core/engine_answer DATE_ASK_RX). */
const DATE_ASK = /дн(я|ей|и|ём)(?![а-яё])|недел|понедельник|вторник|сред[уыа]|четверг|пятниц|суббот|воскресен|завтра|послезавтра|числ[оа]|дат[аыуе]|когда|сколько.{0,20}(дн|недел|месяц|осталось)|через\s+\d|рождени|праздник|январ|феврал|март|апрел|ма[йя](?![а-яё])|июн|июл|август|сентябр|октябр|ноябр|декабр|\d{1,2}[./]\d{1,2}/i;
/* Память 2.0 (27.10, как на компьютере — core/memory.py): в подсказке — последние MEM_CORE фактов (подсказка не меняется
   от вопроса к вопросу), а более старые подбираются к вопросу по смыслу: общие основы слов, близкие слова («подарить» ↔
   «день рождения», «любит») и родство («маме» — всё о маме). Раньше старше 40-го факта модель не видела вовсе. */
const MEM_CORE = 30;
const MEM_SYN = ["подар день рожд юбил празд любит нрави мечта хочет", "здоров болит болез врач табле лекар давле аллер самоч",
  "работ должн профе начал колле офис зарпл", "машин авто водит права", "дом кварт живет живу адрес переех город",
  "еда кушат готов блюдо любим вкусн кофе чай", "деньг бюдже потра купит стоит цена копит", "учеба учит школ униве экзам урок",
  "отпус поезд путеш лете ехать отдых", "имя зовут звать", "возра лет год родил рожде", "собак пес кот кошк питом"].map(g => g.split(" "));
const MEM_KIN = { мам: "мам", мат: "мам", пап: "пап", отец: "пап", отц: "пап", жен: "жен", муж: "муж", сын: "сын", доч: "доч",
  брат: "брат", сест: "сест", бабу: "баб", деду: "дед", внук: "внук", внуч: "внук", друг: "друг", подру: "друг", колле: "колле",
  начал: "колле", собак: "собак", пес: "собак", щен: "собак", кот: "кот", кошк: "кот" };
const MEM_STOP = new Set("что как где когда кто мне меня мой моя мои это там тут для про она они его ее её был была было есть или если уже еще ещё".split(" "));
function memStems(t) { return String(t || "").toLowerCase().replace(/ё/g, "е").match(/[а-яa-z0-9]+/g)?.filter(w => w.length > 2 && !MEM_STOP.has(w)).map(w => w.slice(0, 5)) || []; }
function memKin(st) { const out = new Set(); st.forEach(w => { for (const k in MEM_KIN) if (w.startsWith(k)) out.add(MEM_KIN[k]); }); return out; }
/* своя память у персонажа (0.56; письмо 28.10: «разные персонажи со своей памятью… пока это разные морды лица у одного»):
   S.pmem = {own: [имена], at, facts: {имя: [факты]}} — синхронизируется видом pmemory (как core/sync.py). memArr() — память
   того, кто отвечает сейчас: своя, если включена, иначе общая S.memory. */
const pmemOwn = (name) => ((S.pmem || {}).own || []).includes(name);
function memArr() {
  const n = persona().name;
  if (!pmemOwn(n)) return S.memory || (S.memory = []);
  S.pmem = Object.assign({ own: [], at: 0, facts: {} }, S.pmem || {}); S.pmem.facts = S.pmem.facts || {};
  return S.pmem.facts[n] || (S.pmem.facts[n] = []);
}
function memAdd(f) { const m = memArr(); if (m.includes(f)) return false; m.push(f); if (m.length > 300) m.splice(0, m.length - 300); saveS(); syncSoon(); return true; }
const pmemId = (name, t) => "m" + sha1hex(String(name).trim().toLowerCase()).slice(0, 8) + "-" + (t ? factId(t) : "");
function memPick(text, limit = 8) {
  const mem = memArr();
  if (mem.length <= MEM_CORE) return [];
  const q = new Set(memStems(text)); if (!q.size) return [];
  const qx = new Set(); MEM_SYN.forEach(g => { if (g.some(w => [...q].some(x => x.startsWith(w) || w.startsWith(x)))) g.forEach(w => qx.add(w)); });
  const qk = memKin([...q]);
  return mem.slice(0, -MEM_CORE).map((f, i) => {
    const st = memStems(f); let sc = 0;
    st.forEach(w => { if (q.has(w)) sc += 1.5; else if ([...qx].some(x => w.startsWith(x))) sc += 0.6; });
    if (qk.size && [...memKin(st)].some(k => qk.has(k))) sc += 2;
    return { f, sc, i };
  }).filter(x => x.sc >= 1).sort((a, b) => b.sc - a.sc || b.i - a.i).slice(0, limit).map(x => x.f);
}
/* Второй язык — английский (28.10, как core/lang2.py): фраза по-английски — модель отвечает по-английски, голос телефона
   читает английским (D.speakLang), распознавание узнаёт язык само (Speech.java, lang2 = "en", Android 14+). */
const EN_COMMON = new Set(`the a an is are was were be been am i you he she it we they me my your his her our their what what's whats
how why when where who which can could would should will do does did don't dont not no yes please thanks thank hello hi hey
tell me about this that these those there here and or but with for from to of in on at by it's its let's lets
weather time today tomorrow good morning evening night play music turn set remind reminder call open stop`.split(/\s+/));
const EN_HINT = "Собеседник говорит по-английски — ответь по-английски, простым разговорным языком (если он сам не просит по-русски).";
function isEnglish(text) {
  const t = String(text || "");
  if (!t.trim() || /[А-Яа-яЁё]/.test(t)) return false;
  const w = (t.match(/[A-Za-z][A-Za-z'’]*/g) || []).map(x => x.toLowerCase().replace("’", "'"));
  const common = w.filter(x => EN_COMMON.has(x)).length;
  return (common >= 1 && w.length >= 2) || w.length >= 3;
}
/* 0.96: приложение по-английски — распознавание телефона слушает английский (D.sttLang1), «второй язык» — тогда русский */
function lang2Apply() {
  try { if (D.sttLang1) D.sttLang1(window.dwLang && dwLang() === "en" ? "en" : "ru"); if (D.sttLang2) D.sttLang2(S.lang2 || ""); } catch (e) { }
}
function turnContext(text) {
  const n = convNote();
  let rp = ""; try { rp = recentPrompt() || ""; } catch (e) { }
  let t = `Сейчас ${nowText()}.`;
  if (DATE_ASK.test(String(text || ""))) {
    const week = [1, 2, 3, 4, 5, 6, 7].map(i => { const d = new Date(Date.now() + i * 864e5); return `${WD[d.getDay()]} — ${d.getDate()} ${MON[d.getMonth()]}`; }).join("; ");
    t += ` Ближайшие дни: ${week}. Сколько дней до даты и какая дата ближе — считай calc days_until, не в уме.`;
  }
  if (isEnglish(text)) t += " " + EN_HINT;          // спросили по-английски — ответ по-английски (второй язык)
  let mp = []; try { mp = memPick(text); } catch (e) { }
  return (rp ? rp.trim() + "\n\n" : "") + t + (n ? " " + n : "")
    + (mp.length ? "\n\nИз памяти о пользователе (подобрано к этому вопросу — используй, если к месту):\n- " + mp.join("\n- ") : "");
}
function putContext(msgs, ctx) {
  const last = msgs[msgs.length - 1];
  if (!ctx || !last || last.role !== "user") return;
  const head = "(Справка к этому сообщению — для тебя, вслух её не упоминай)\n" + ctx + "\n\n(Сообщение пользователя)\n";
  if (Array.isArray(last.content)) { const t = last.content.find(x => x.type === "text"); if (t) t.text = head + (t.text || ""); else last.content.unshift({ type: "text", text: head.trim() }); }
  else last.content = head + String(last.content || "");
}
/* Личное (systemPersonal) — справкой в начало первого сообщения разговора (как llm.put_profile на компьютере). */
const PROFILE_HEAD = "(О пользователе и о тебе — справка от программы, вслух её не упоминай)\n", PROFILE_END = "\n\n(Дальше — разговор)\n";
function putProfile(msgs, text) {
  text = String(text || "").trim(); if (!text) return;
  const i = msgs.findIndex(m => m.role !== "system"); if (i < 0) return;
  const m = msgs[i], head = PROFILE_HEAD + text + PROFILE_END;
  if (m.role !== "user") { msgs.splice(i, 0, { role: "user", content: head.trim() }); return; }
  if (Array.isArray(m.content)) { const t = m.content.find(x => x.type === "text"); if (t) t.text = head + (t.text || ""); else m.content.unshift({ type: "text", text: head.trim() }); }
  else m.content = head + String(m.content || "");
}
const NEW_CONV_RX = /^(?:давай(?:те)?\s+)?(?:начн(?:ем|и)|начать)\s+(?:новый\s+разговор|разговор\s+заново|сначала|заново|с\s+чистого\s+листа)$|^(?:забудь|сотри|очисти)\s+(?:наш\s+|этот\s+|весь\s+)?разговор$|^новый\s+разговор$|^новая\s+тема$/;

/* ---------- персонажи и облик ---------- */
const PERSONAS = window.DEWIAR_PERSONAS || [{ id: "lira", name: "Лира", style: "strings", color: "#9BD4FF", character: "Ты — Лира, голосовой помощник Dewiar.", focus: "", gender: "female", role: "Главная помощница", aliases: ["лира"] }];
/* Свои персонажи на телефоне (19.10: «на телефоне нет функции создать персонажа», «хочу этот аватар»): имя, кто (он/она),
   роль, характер, облик из галереи, цвет. Хранятся в pref my_personas и стоят в PERSONAS после встроенных — дальше всё
   как у встроенных: имя зовёт, характер — в подсказке модели, облик — портретом. id «u…» — свои, встроенные не трогаем. */
const MY_MAX = 8;
function myPersonas() { try { const l = JSON.parse(prefGet("my_personas") || "[]"); return Array.isArray(l) ? l.filter(x => x && x.id && x.name) : []; } catch (e) { return []; } }
function myPersonaFull(x) {
  const fem = x.gender === "female", role = String(x.role || "").trim();
  return Object.assign({ style: x.avatar ? "photo" : "nexus", color: "#8A9BFF", focus: "", main: false, skills: [], tagline: "" }, x, {
    custom: true, aliases: [String(x.name).toLowerCase().replace(/ё/g, "е")],
    role: role || (fem ? "Своя помощница" : "Свой помощник"),
    // характер с компьютера уже целиком («Ты — …») — как есть; свой короткий — с именем и ролью впереди
    character: (/^\s*Ты\s/.test(x.about || "") ? String(x.about).trim() : `Ты — ${x.name}${role ? ", " + role : ""}. ` + (String(x.about || "").trim() || (fem ? "Тёплая, внимательная и живая собеседница." : "Спокойный, внимательный и живой собеседник.")))
      + " Ты — персонаж Dewiar: помогаешь делом (напоминания, заметки, звонки, поиск) и говоришь своим голосом и характером.",
  });
}
function myPersonasApply() {
  for (let i = PERSONAS.length - 1; i >= 0; i--) if (PERSONAS[i].custom) PERSONAS.splice(i, 1);
  for (const x of myPersonas()) PERSONAS.push(myPersonaFull(x));
}
/* Готовые персонажи (идея №56, 03.11: «на компьютере Фемида, Доктор, Джарвис… — а на телефоне только Лира, Патрик и свой»):
   те же шаблоны и специалисты, что в студии → «Персонажи» → «Готовые» (window.DEWIAR_GALLERY — personas.js, его собирает
   android/tools/personas_json.py из core/personas.py). «Выбрать» — персонаж встаёт в команду и сразу отвечает; «Убрать» —
   уходит. Список id — в pref gal_personas, только на этом телефоне: как и на компьютере, готовых синхронизация не переносит
   (у каждого устройства свой набор). Пакетов знаний компьютера здесь нет — специализация словами в подсказке (focus). */
const PGALLERY = window.DEWIAR_GALLERY || [];
function galIds() { try { const l = JSON.parse(prefGet("gal_personas") || "[]"); return Array.isArray(l) ? l.filter(id => PGALLERY.some(g => g.id === id)) : []; } catch (e) { return []; } }
function galApply() {
  for (let i = PERSONAS.length - 1; i >= 0; i--) if (PERSONAS[i].gallery) PERSONAS.splice(i, 1);
  const at = PERSONAS.findIndex(p => p.custom);
  const add = galIds().map(id => Object.assign({ main: false, skills: [], focus: "" }, PGALLERY.find(g => g.id === id), { gallery: true }));
  PERSONAS.splice(at < 0 ? PERSONAS.length : at, 0, ...add);       // после встроенных, перед своими
}
// -> персонаж, который теперь отвечает (или null — нет такого)
function galAdd(id) {
  const g = PGALLERY.find(x => x.id === id); if (!g) return null;
  const l = galIds(); if (!l.includes(id)) l.push(id);
  prefSet("gal_personas", JSON.stringify(l)); galApply();
  S.persona = id; saveS(); applyPersona();
  return PERSONAS.find(p => p.id === id) || null;
}
function galRemove(id) {
  prefSet("gal_personas", JSON.stringify(galIds().filter(x => x !== id))); galApply();
  if (S.persona === id) { S.persona = PERSONAS[0].id; saveS(); applyPersona(); }
}
galApply();
myPersonasApply();
// с 0.4.27 встроенных двое — Лира и Патрик; выбранный прежде Агент, Джарвис, Эва или Кодер — теперь Лира
if (!PERSONAS.some(p => p.id === S.persona)) { S.persona = PERSONAS[0].id; try { prefSet("settings", JSON.stringify(S)); } catch (e) { } }
const persona = () => (kidsOn() && window.DEWIAR_KIDS_PERSONA) || PERSONAS.find(p => p.id === S.persona) || PERSONAS[0];   // детский режим — Совёнок Уго
const hex2rgb = (h) => { const n = parseInt(h.replace("#", ""), 16); return [(n >> 16) & 255, (n >> 8) & 255, n & 255]; };
let orb = null;
function applyPersona() {
  const p = persona(), [r, g, b] = hex2rgb(p.color || "#8A9BFF");
  document.documentElement.style.setProperty("--pc", p.color);
  document.documentElement.style.setProperty("--pcg", `rgba(${r},${g},${b},${lookSkin() === "neon" ? ".24" : ".10"})`);    // свечение персонажа: в «Неоне» — как раньше
  $("#who-name").textContent = p.name;
  $("#who-img").src = p.avatar || miniOrb(p);
  const style = p.avatar && p.style !== "aura" ? "photo" : p.style;
  // портрет сдержанно (белый край вместо цветного кольца), голос — лучами, как на компьютере; тема — «Настройки» → «Оформление»
  if (!orb) { orb = new DewiarEntity($("#orb"), { style, color: p.color, image: p.avatar || null, plate: true, live: p.live || "", soft: !!p.kids }); orb.set({ audible: false }); applyLook(true); liteApply(); tiltSync(); }
  else orb.configure({ style, color: p.color, image: p.avatar || null, live: p.live || "", soft: !!p.kids });
  orb.set({ state: state === "idle" ? "idle" : state });
  faceFor(p);
}
/* Наклон телефона — портрет «смотрит» на человека (просьба 14.10, параллакс без камеры). Датчик ориентации
   (deviceorientation, без разрешений): важна перемена наклона, а не поза — «как держит» подстраивается за пару секунд,
   и портрет возвращается к центру. Диск чуть поворачивается к человеку (CSS, до 7°), лицо сдвигается в глубину, живое
   лицо переводит на него глаза (DewiarEntity.look). Выключено: «Оформление» → «Портрет следит за наклоном», «уменьшить
   движение» в системе, экран не виден (приложение свёрнуто) и альбомный экран — датчик не слушаем вовсе.
   По умолчанию выключено (отзыв 14.10: «быстро надоедает — под флагом, по умолчанию выключен»). */
const TILT = { on: false, b0: null, g0: null, t: 0, x: 0, y: 0, raf: 0 };
function tiltWanted() {
  const angle = (screen.orientation && screen.orientation.angle) || 0;
  return S.tilt === true && !liteOn() && "DeviceOrientationEvent" in window && !document.hidden && angle === 0
    && !matchMedia("(prefers-reduced-motion: reduce)").matches;
}
function tiltOn(e) {
  if (e.beta == null || e.gamma == null) return;
  const now = performance.now(), dt = TILT.t ? Math.min(0.5, (now - TILT.t) / 1000) : 0; TILT.t = now;
  const b = e.beta, g = e.gamma;
  if (TILT.b0 === null || Math.abs(b - TILT.b0) > 60) { TILT.b0 = b; TILT.g0 = g; }   // первый замер или телефон перевернули
  const k = 1 - Math.exp(-dt / 2.5);
  TILT.b0 += (b - TILT.b0) * k; TILT.g0 += (g - TILT.g0) * k;
  const cl = (v) => Math.max(-1, Math.min(1, v));
  TILT.x += (cl(-(g - TILT.g0) / 12) - TILT.x) * 0.3; TILT.y += (cl((b - TILT.b0) / 12) - TILT.y) * 0.3;   // без дрожи датчика
  if (!TILT.raf) TILT.raf = requestAnimationFrame(tiltApply);
}
function tiltApply() {
  TILT.raf = 0;
  if (orb) orb.look(TILT.x, TILT.y);
  const c = $("#orb"); if (c) c.style.transform = `perspective(700px) rotateY(${(TILT.x * 7).toFixed(2)}deg) rotateX(${(-TILT.y * 6).toFixed(2)}deg)`;
}
function tiltSync() {
  const want = tiltWanted();
  if (want === TILT.on) return;
  TILT.on = want;
  if (want) { TILT.b0 = null; TILT.t = 0; window.addEventListener("deviceorientation", tiltOn); return; }
  window.removeEventListener("deviceorientation", tiltOn);
  cancelAnimationFrame(TILT.raf); TILT.raf = 0; TILT.x = TILT.y = 0;
  if (orb) orb.look(null);
  const c = $("#orb"); if (c) c.style.transform = "";
}
/* Лёгкий режим (18.10: «последние дни подтормаживает телефон… на компьютере работает даже на слабом — так и на
   Android?»). Сам включается на слабом телефоне (Android считает его маломощным или памяти ≤ 3 ГБ), при экономии
   батареи и если портрет рисуется медленно; «Ещё → Оформление → Лёгкий режим»: авто, всегда, никогда.
   Что делает: портрет в покое неподвижен, в разговоре — не чаще ~20 кадров/с; наклон не следим; синхронизация и
   проверки — втрое реже; «Близкие» без постоянной связи — проверка раз в 15 минут (CloseWatch), а не служба CloseLive. */
const LITE_RAM = 3072;
let liteSlow = false, liteHits = 0, liteState = null, liteWhyNow = "";
function liteDev() { try { return JSON.parse(D.deviceClass ? D.deviceClass() : "{}") || {}; } catch (e) { return {}; } }
function liteWhy() {
  const m = S.lite || "auto";
  if (m === "on") return "включён вручную";
  if (m === "off") return "";
  const d = liteDev();
  if (d.power_save) return "включена экономия батареи";
  if (d.low_ram || (d.ram_mb && d.ram_mb <= LITE_RAM)) return d.ram_mb ? `памяти ${(d.ram_mb / 1024).toFixed(d.ram_mb < 1536 ? 1 : 0).replace(".", ",")} ГБ` : "Android считает телефон маломощным";
  if (liteSlow) return "портрет рисовался медленно";
  return "";
}
const liteOn = () => liteState === true;
function liteApply() {
  liteWhyNow = liteWhy();
  const on = !!liteWhyNow, was = liteState;
  liteState = on;
  if (orb) { orb.still = on; orb.lite = on; }
  document.body.classList.toggle("lite-ui", on);           // и листы без размытия фона (app.css, №93)
  if (on !== was) {
    if (was !== null || on) plog("info", on ? "🪶 лёгкий режим: " + liteWhyNow : "🪶 лёгкий режим выключен");
    try { tiltSync(); } catch (e) { }
    try { clWatch(); } catch (e) { }
  }
}
// медленные кадры: облик сам считает, сколько рисуется кадр (_cost, мс); долго больше 14 мс — телефону тяжело
setInterval(() => {
  if (document.hidden || !orb || liteSlow || (S.lite || "auto") !== "auto") return;
  liteHits = (orb._cost || 0) > 14 ? liteHits + 1 : 0;     // три проверки подряд (полминуты) — не случайный всплеск
  if (liteHits >= 3) liteSlow = true;
  liteApply();
}, 10000);
document.addEventListener("visibilitychange", () => { if (!document.hidden) liteApply(); });
document.addEventListener("visibilitychange", () => tiltSync());
if (screen.orientation && screen.orientation.addEventListener) screen.orientation.addEventListener("change", () => tiltSync());

/* Облик для уведомлений и часов (Faces.java): фото персонажа или его облик в круге, 192×192, и имя с цветом.
   Рисуется при смене персонажа; уведомления и будильники берут его и без интерфейса (из файла). */
function faceFor(p) {
  if (!D.setFace) return;
  const c = document.createElement("canvas"); c.width = c.height = 192;
  const x = c.getContext("2d"), done = () => { try { D.setFace(p.id, p.name, p.color || "#8A9BFF", c.toDataURL("image/png").split(",")[1]); } catch (e) {} };
  x.save(); x.beginPath(); x.arc(96, 96, 96, 0, 7); x.clip();
  const g = x.createRadialGradient(80, 70, 10, 96, 96, 96);
  g.addColorStop(0, p.color || "#8A9BFF"); g.addColorStop(.6, "#1d1d38"); g.addColorStop(1, "#0d0d1a");
  x.fillStyle = g; x.fillRect(0, 0, 192, 192);
  if (!p.avatar) {                                      // без фото — первая буква имени на облике
    x.fillStyle = "#fff"; x.font = "600 84px Unbounded, Manrope, sans-serif"; x.textAlign = "center"; x.textBaseline = "middle";
    x.fillText((p.name || "D")[0].toUpperCase(), 96, 102); x.restore(); return done();
  }
  const im = new Image();
  im.onload = () => { const k = Math.max(192 / im.width, 192 / im.height), w = im.width * k, h = im.height * k;
    x.drawImage(im, (192 - w) / 2, (192 - h) / 2, w, h); x.restore(); done(); };
  im.onerror = () => { x.restore(); done(); };
  im.src = p.avatar;
}
function miniOrb(p) {          // значок персонажа без фото — кадр его облика
  const c = document.createElement("canvas"); c.width = c.height = 64;
  const x = c.getContext("2d"), g = x.createRadialGradient(28, 24, 4, 32, 32, 32);
  g.addColorStop(0, p.color); g.addColorStop(.55, "#1d1d38"); g.addColorStop(1, "#0d0d1a");
  x.fillStyle = g; x.beginPath(); x.arc(32, 32, 32, 0, 7); x.fill(); return c.toDataURL();
}

/* Оформление (как на компьютере, студия → «Оформление»): тема фона и облика (S.skin) и чем голос отзывается вокруг
   портрета (S.voice_fx). calm — по умолчанию: фон в фирменных цветах, белый край портрета; graphite — почти чёрный;
   neon — как раньше: свечение и цвет персонажа. */
// skins.js — общий с виджетом: все темы, и светлые (body.light — тёмный текст), и неоморфизм (body.neu — app.css)
const PHONE_SKINS = (window.DEWIAR_SKINS || []).slice();
const SKINS = PHONE_SKINS.length ? PHONE_SKINS.map(x => x.id) : ["brand"];
const lookSkin = () => (SKINS.includes(S.skin) ? S.skin : SKINS.includes("neusky") ? "neusky" : SKINS[0]);   // 20.10: по умолчанию — «Небесный»
// 28.10: звонки — пять, выбрал владелец (звуки Android Open Source Project, Apache 2.0); фирменный — «Пульс».
// Прежние (Струна, Чаша, Колодец…) убраны: у кого были выбраны — звенит «Пульс» (Sounds.current).
const ALARM_SOUNDS = [["signature", "Пульс · фирменный", "Ритм с басом — бодро и собранно"], ["noon", "Полдень", "Светлый грув с ударными"],
  ["night", "Ночной город", "Глубокий бас и мерный ритм"], ["wave", "Волна", "Басовая, спокойная"], ["sparks", "Искры", "Яркая и бодрая"],
  ["system", "Системный", "Звук будильника телефона"]];
const PLAY_SVG = '<svg viewBox="0 0 24 24"><path d="M8 5.5v13l10.5-6.5z" fill="currentColor" stroke="none"/></svg>';
const LOOK_BAR = { glass: "#FCD6E3", snow: "#F8F9FB" };      // верх фона светлых тем без сплошного цвета
let lookBar = "";
const lookFx = () => (["bars", "pulse", "wave"].includes(S.voice_fx) ? S.voice_fx : "bars");
function applyLook(fromPersona) {
  SKINS.forEach(k => document.body.classList.toggle("skin-" + k, k === lookSkin()));
  const sk = window.dewiarSkin ? dewiarSkin(lookSkin()) : {};
  document.body.classList.toggle("light", !!sk.light);
  document.body.classList.toggle("neu", !!sk.neu);
  try { const v = lookSkin() + (sk.light ? " light" : "") + (sk.neu ? " neu" : ""); if (D.pref("look_body") !== v) D.setPref("look_body", v); } catch (e) { }   // для index.html: тема до первой отрисовки
  // строка состояния и панель жестов — в цвет темы: светлым темам — светлые полосы и тёмные значки
  const bar = sk.neu ? getComputedStyle(document.body).getPropertyValue("--glass").trim() : (LOOK_BAR[sk.id] || "#0B0B10");
  try { if (D.bars && bar !== lookBar) { D.bars(/^#[0-9a-f]{6}$/i.test(bar) ? bar : "#0B0B10", !!sk.light); lookBar = bar; } } catch (e) { }
  if (orb) { orb.tone = (window.dewiarSkin && dewiarSkin(lookSkin()).tone) || "mono"; orb.fx = lookFx(); }
  if (!fromPersona) try { applyPersona(); } catch (e) { }       // свечение персонажа зависит от темы
}

/* ---------- состояние разговора ---------- */
let state = "idle";
const STATE_RU = { idle: "Нажмите или удерживайте", listening: "Слушаю", thinking: "Думаю", speaking: "Говорю" };
/* Звук «больше не слушаю»: ожидание кончилось без вопроса (или его отменили) — колокольчик вниз, как на компьютере
   (core/audio_io.py tone("sleep")). Начало слушания звучит у распознавателя телефона и вибрацией. */
let earCtx = null;
function earcon(kind) {
  try {
    earCtx = earCtx || new (window.AudioContext || window.webkitAudioContext)();
    if (earCtx.state === "suspended") earCtx.resume();
    const notes = kind === "sleep" ? [[784, 0], [523.3, 0.08]] : [[1046.5, 0], [1568, 0.07]], t0 = earCtx.currentTime + 0.01;
    notes.forEach(([f, at]) => [[1, 0.17], [2, 0.05], [3.01, 0.014]].forEach(([k, amp]) => {
      const o = earCtx.createOscillator(), g = earCtx.createGain();
      o.frequency.value = f * k; o.connect(g); g.connect(earCtx.destination);
      g.gain.setValueAtTime(0, t0 + at); g.gain.linearRampToValueAtTime(amp, t0 + at + 0.004);
      g.gain.exponentialRampToValueAtTime(0.0001, t0 + at + 0.3); o.start(t0 + at); o.stop(t0 + at + 0.32);
    }));
  } catch (e) { }
}
function setState(s) {
  if (state === "listening" && s === "idle" && S.sounds !== false) earcon("sleep");
  state = s;
  if (orb) orb.set({ state: s, level: s === "speaking" ? 0.3 : 0 });
  $("#state").textContent = holdTalk && s === "listening" ? (holdCancel ? "Отпустите — отменить" : "Говорите · отпустите — отправлю") : STATE_RU[s] || "";
  $("#state").classList.toggle("idle", s === "idle");
  const sx = $("#stopx"); if (sx) sx.hidden = !(s === "thinking" || s === "speaking") || holdTalk;   // №560: «Стоп» без микрофона
  const rb = $("#radiobox"); if (rb) rb.classList.toggle("talking", s !== "idle");   // подсказка про голос — только в покое
  triesCheck($("#stage").classList.contains("quiet"));                              // слушает или думает — примеры прячутся
  const m = $("#mic"); m.classList.toggle("on", s === "listening"); m.classList.toggle("busy", s === "thinking" || s === "speaking");
  const hm = $("#hmic"); if (hm) { hm.classList.toggle("on", s === "listening"); hm.classList.toggle("busy", s === "thinking" || s === "speaking"); }
  D.keepScreen(s !== "idle" || !!(window.DewiarCall && DewiarCall.active()));     // идёт звонок «Близким» — экран не гаснет
  const duck = radio.on() && s !== "idle";        // пока слушаю и отвечаю — радио тише
  if (duck !== radioDucked) { radioDucked = duck; D.radioDuck(duck); }
  if (s === "idle") radio.resumeAfterTalk();
}
let radioDucked = false;
function toast(t, ms = 2200) { const el = $("#toast"); el.textContent = t; el.classList.add("on"); clearTimeout(el._t); el._t = setTimeout(() => el.classList.remove("on"), ms); }
/* Версия движка страниц (Android System WebView / Chrome): у части планшетов (Huawei без сервисов Google) он старый,
   и новое оформление может выглядеть иначе — в жалобе и пульсе видно, какой. -> " · WebView 99" или "" */
function webviewVer() { const m = /(?:Chrome|Chromium)\/(\d+)/.exec(navigator.userAgent || ""); return m ? " · WebView " + m[1] : ""; }
function showYou(t) { const en = !!(window.dwLang && dwLang() !== "ru"); $("#you").textContent = t ? (en ? "“" + t + "”" : "«" + t + "»") : ""; quietCheck(); }   // не по-русски — английские кавычки (0.96)
/* Длинный ответ (список, таблица, план) — в рамке: облик уменьшается, текст слева и мельче; когда ответ готов
   (frameAnswer) — разметка и кнопки «Копировать», «В заметки», «Скачать». Отзыв: длинный ответ налезал на облик и поле
   ввода, а сохранить его было нечем. */
const LONG_ANSWER = 160;
let turnMedia = null;                            // картинки этого ответа (show_images) — под ответом и в истории
let turnQ = "";                                 // вопрос этого хода: длинная страница (readPage) — куски по его словам
const isLongAnswer = (t) => String(t || "").length >= LONG_ANSWER || /\n\s*(?:[-*•]|\d+[.)])\s|\n\s*\||```/.test(String(t || "")) || !!(turnMedia && turnMedia.length);
function showBot(t, cls) {
  t = trL(t);
  if (tgTurn && t && cls !== "wait") tgLast = String(t);
  const b = $("#bot"), long = !cls && isLongAnswer(t);
  b.className = cls || (long ? "framed" : ""); b.textContent = t || "";
  $("#stage").classList.toggle("long", long);
  if (!long) $("#talk").scrollTop = 1e6;
  quietCheck();
}
function mdAnswer(t) {         // ответ модели → HTML: экранируем, затем заголовки, жирный, пункты, таблицы
  const lines = esc(String(t || "").trim()).split("\n"), out = [];
  let list = "", table = [];
  const inl = (x) => x.replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>").replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<i>$2</i>").replace(/`([^`]+)`/g, "<code>$1</code>");
  const flushList = () => { if (list) { out.push(`</${list}>`); list = ""; } };
  const flushTable = () => {
    if (!table.length) return;
    const rows = table.filter(r => !/^\|?\s*:?-{2,}/.test(r)).map(r => r.replace(/^\||\|$/g, "").split("|").map(c => inl(c.trim())));
    out.push(`<div class="tbl"><table>${rows.map((r, i) => `<tr>${r.map(c => i ? `<td>${c}</td>` : `<th>${c}</th>`).join("")}</tr>`).join("")}</table></div>`);
    table = [];
  };
  let code = null;                                   // внутри ``` … ``` — код или схема (```mermaid — рисует rich.js)
  for (const [ri, raw] of lines.entries()) {
    const l = raw.trim(); let m;
    if (/^```/.test(l)) {
      if (code === null) { flushList(); flushTable(); code = { lang: l.slice(3).trim(), rows: [] }; }
      else { out.push(`<pre><code class="language-${code.lang.replace(/[^\w-]/g, "")}">${code.rows.join("\n")}</code></pre>`); code = null; }
      continue;
    }
    if (code !== null) { code.rows.push(raw); continue; }
    if (/^\|.*\|$/.test(l)) { flushList(); table.push(l); continue; }
    flushTable();
    if ((m = l.match(/^#{1,4}\s+(.*)$/))) { flushList(); out.push(`<h4>${inl(m[1])}</h4>`); }
    else if ((m = l.match(/^(?:[-*•])\s+(.*)$/))) { if (list !== "ul") { flushList(); out.push("<ul>"); list = "ul"; } out.push(`<li>${inl(m[1])}</li>`); }
    // №275 (пакет 27.10): пункты через пустую строку шли каждый своим <ol> — «1, 1, 1»; теперь список продолжается,
    // а начатый не с единицы — с нужного номера
    else if ((m = l.match(/^(\d+)[.)]\s+(.*)$/))) { if (list !== "ol") { flushList(); out.push(+m[1] > 1 ? `<ol start="${+m[1]}">` : "<ol>"); list = "ol"; } out.push(`<li>${inl(m[2])}</li>`); }
    else if (!l) { const nx = lines.slice(ri + 1).find(x => x.trim()); if (!(list && nx && /^\s*(?:[-*•]|\d+[.)])\s/.test(nx))) flushList(); }
    else { flushList(); out.push(`<p>${inl(l)}</p>`); }
  }
  if (code !== null) out.push(`<pre><code>${code.rows.join("\n")}</code></pre>`);   // ответ оборвался внутри блока
  flushList(); flushTable();
  return out.join("");
}
function copyText(t) {
  if (D.copy && D.copy(t)) return Promise.resolve(true);
  return navigator.clipboard ? navigator.clipboard.writeText(t).then(() => true, () => false) : Promise.resolve(false);
}
function frameAnswer(t) {      // ответ готов: длинный — с разметкой и кнопками
  t = String(t || "").trim(); const b = $("#bot");
  if (!t || !isLongAnswer(t) || b.className && b.className !== "framed") return;
  b.className = "framed"; $("#stage").classList.add("long");
  b.innerHTML = `<div class="ans">${mdAnswer(t)}${turnMedia && window.DewiarRich ? DewiarRich.gallery(turnMedia) : ""}</div><div class="acts"><button data-a="copy">${ICON_COPY}Копировать</button><button data-a="note">${ICON_NOTE}В заметки</button><button data-a="save">${ICON_SAVE}Скачать</button></div>`;
  if (window.DewiarRich) DewiarRich.diagrams(b.querySelector(".ans"));   // ```mermaid — схемой
  wirePics(b);
  b.querySelector('[data-a="copy"]').onclick = () => ansAct("copy", t);
  b.querySelector('[data-a="note"]').onclick = () => ansAct("note", t);
  b.querySelector('[data-a="save"]').onclick = () => ansAct("save", t);
  $("#talk").scrollTop = 0;
}
/* Действия с ответом: «Скопировать», «В заметки», «Скачать» (.md) — у длинного ответа на главном экране и (идея №127,
   04.11: «в чате добавить кнопки… открыл чат — сделал то, что упустил сначала») у каждого ответа в «Разговоре». */
function ansTitle(t) { return String(t || "").replace(/[#*_`|>\[\]]/g, "").split(/[.!?\n]/)[0].trim().slice(0, 60) || "Ответ"; }
function ansAct(a, t) {
  t = String(t || "").trim(); if (!t) return;
  const title = ansTitle(t);
  if (a === "copy") return copyText(t).then(ok => toast(ok ? "Скопировано" : "Не получилось скопировать"));
  if (a === "note") {
    const n = notes();
    if (n.some(x => x.text === t)) return toast(`Уже в заметках: «${title}»`, 2600);     // нажали второй раз — не дублируем
    n.push({ id: uid("n"), title, text: t, time: Date.now() }); saveNotes(n); return toast(`В заметках: «${title}»`, 2800);
  }
  if (a === "save") {
    const name = title.replace(/[\\/:*?"<>|]+/g, " ").trim().slice(0, 40) + ".md";
    const where = D.saveDownload ? D.saveDownload(name, "text/markdown", t) : "";
    toast(where ? `Сохранено: ${where}` : "Не получилось сохранить", 3500);
  }
}
const ICON_COPY = `<svg viewBox="0 0 24 24"><rect x="8" y="8" width="12" height="12" rx="2.5"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/></svg>`;
const ICON_NOTE = `<svg viewBox="0 0 24 24"><path d="M6 3.5h9l4 4V20a.5.5 0 0 1-.5.5h-12A.5.5 0 0 1 6 20z"/><path d="M14.5 3.5V8H19M9 12.5h7M9 16h5"/></svg>`;
const ICON_SAVE = `<svg viewBox="0 0 24 24"><path d="M12 4v11M7.5 10.5 12 15l4.5-4.5M5 19.5h14"/></svg>`;
function showCard(html) { $("#card").innerHTML = html || ""; cardSticky = 0; quietCheck(); }
/* Снимок с камеры держится на экране 3 минуты: «покажи это фото мне» сразу после снимка не должно его стирать
   (раньше новая фраза очищала карточку, и человек слышал «вот», а видел пустой экран). Новая карточка — сменяет. */
let cardSticky = 0;
function showPhotoCard(url) { showCard(photoCard(url)); cardSticky = Date.now() + 180000; photoTurn = true; }
function clearCard() { if (Date.now() < cardSticky) return; showCard(""); }
let photoTurn = false;              // в этом ходе показан снимок — пометим в истории для модели
// на экране ничего не сказано и не показано — #stage.quiet: лёжа облик встаёт по центру (app.css)
function quietCheck() {
  const quiet = !$("#you").textContent && !$("#bot").textContent && !$("#bot").className && !$("#card").innerHTML;
  $("#stage").classList.toggle("quiet", quiet);
  if ($("#talk-x")) $("#talk-x").hidden = quiet || $("#bot").classList.contains("wait");   // пока отвечает — не убираем
  triesCheck(quiet);
}
/* «Попробуйте сказать» (отзыв 18.10: «сказал привет, ответили голосом, а что с ней делать дальше — ума не приложу»): пока
   человек новичок (сам спросил меньше 4 раз) и экран пуст — фразы-примеры, нажатие спрашивает. Кто пользовался раньше
   (есть разговор или память) — не показываем: S.tries заводится при первом запуске этой версии. */
const TRIES_MAX = 4;
function triesState() {
  if (!S.tries) S.tries = { n: history.some(m => m.role === "user") || (S.memory || []).length ? TRIES_MAX : 0, off: false };
  return S.tries;
}
function triesList() {
  return ["Что ты умеешь?", "Включи радио", "Погода на завтра", D.web ? "Что нового в мире?" : "Посвети фонариком",
    "Напомни через час позвонить маме", "Запиши: купить хлеб"];
}
function triesCheck(quiet) {
  const box = $("#tries"); if (!box) return;
  const t = triesState(), brain = !!(S.llm.base_url || loggedIn());
  const show = quiet && brain && !t.off && t.n < TRIES_MAX && state === "idle";
  if (show && !box.childElementCount) {
    box.innerHTML = `<p class="th">Попробуйте сказать — или нажмите</p><div class="tlist">${triesList().map(q => `<button class="tq" data-q="${esc(q)}">${esc(q)}</button>`).join("")}</div>`
      + `<button class="lnk tx" id="tries-x">Больше не показывать</button>`;
    box.querySelectorAll(".tq").forEach(b => b.onclick = () => ask(b.dataset.q));
    $("#tries-x").onclick = () => { triesState().off = true; saveS(); quietCheck(); };
  }
  box.hidden = !show;
  $("#stage").classList.toggle("tries", show);
}
/* Убрать сказанное с экрана: крестик или смахнуть вбок. Разговор не забывается — только экран (23.10). */
function talkDismiss(dx) {
  const t = $("#talk"); t.style.setProperty("--dx", (dx || 60) + "px"); t.classList.add("away");
  setTimeout(() => { $("#you").textContent = ""; $("#bot").textContent = ""; $("#bot").className = ""; cardSticky = 0; showCard("");
    $("#stage").classList.remove("long"); t.classList.remove("away"); t.scrollTop = 0; quietCheck(); }, RM.matches ? 0 : 220);
}
const RM = matchMedia("(prefers-reduced-motion: reduce)");

/* ---------- разрешения ---------- */
const permWait = {};
N.on("perm", e => { const w = permWait[e.name]; if (w) { delete permWait[e.name]; w(!!e.granted); } });
function needPerm(name) {
  if (D.has(name)) return Promise.resolve(true);
  return new Promise(res => { permWait[name] = res; D.perm(name); });
}

