//@ Телефон и веб-версия, часть 13: заметки и деньги, заметка целиком, умный дом Яндекса, Home Assistant.
//@ Собирается в android/assets/www/app.js (tools/app_join.py) — порядок частей = порядок исполнения; шапка «//@» в app.js не попадает.
/* ---------- заметки и деньги — файлы notes.json и money.json в памяти приложения (Dewiar.files/saveFile);
   после каждой записи — синхронизация с компьютером (syncSoon) ---------- */
const notes = () => { try { return JSON.parse(fileGet("notes.json") || "[]"); } catch (e) { return []; } };
// напоминания телефона; в экзамене — его песочница (exam.js: EXAM.alarms), настоящие будильники не трогаем
const alarmsNow = () => (typeof EXAM !== "undefined" && EXAM ? EXAM.alarms.slice() : JSON.parse(D.alarms() || "[]"));
const NOTE_GENERIC = /^(?:заметк\w*|все|всё|мои|мой|моих|последн\w*|покажи|прочитай|список|какие|есть|что|там|записи|запис\w*|сохран\w*)$/;
const NOTES_SHOW_RX = /^(?:(?:покажи|открой|прочитай|выведи|какие|что)\s+)?(?:(?:у\s+меня\s+)?(?:есть\s+)?(?:в\s+)?)?(?:мои\s+|все\s+)?(?:заметк(?:и|ах))(?:\s+(?:у\s+меня|есть))?$/;
const NOTE_RX = /^(?:(?:запиши|запишите|сохрани|добавь|занеси|сделай|создай|оставь)(?:\s+(?:мне|себе|пожалуйста))*\s+)?(?:в\s+)?(?:заметк(?:а|у|и|ах)|новую\s+заметку)(?:\s+(?:что|о том,?\s+что))?\s*[:,—–-]?\s+(\S[\s\S]{2,})$/i;
/* -> текст ответа, если фраза — явная просьба записать заметку (и заметка записана), иначе "" */
/* «Запомни: в среду в 15:00 у меня встреча с подрядчиком» — сразу в память, без модели (как capture.py на компьютере).
   Экзамены 0.6.40: модель то вызывала remember без факта, то вместо памяти спрашивала про календарь — и через новый
   разговор на «что у меня в среду?» отвечала «пусто». День плана — точной датой: через неделю «в среду» уже другая. */
const FACT_RX = /^(?:(?:а|и|ну|пожалуйста|слушай)\s+)*запомни(?:те)?(?:\s*,?\s*(?:себе|мне|пожалуйста)(?![а-яё]))*\s*[:,.\-—]?\s*([\s\S]+)$/i;
const FACT_ME = LBRX("(?<![а-яё])(?:я|у меня|у нас|мне|нам|мы|мой|моя|моё|мое|мои|моего|моей|моим|мою|наш[а-яё]*)(?![а-яё])", "i");
const FACT_SKIP = /^(?:(?:для|на время|в рамках|пока идет|до конца)\s+(?:этого\s+|нашего\s+)?(?:разговор|беседы|чата|диалог)|это\b|вот это\b|то,? что\b|(?:про|о|об|обо)\s+)/i;
const DAY_WORD = LBRX("(?<![а-яё])(?:сегодня|завтра|послезавтра|(?:в|во|на)\\s+(?:понедельник|вторник|среду|четверг|пятницу|субботу|воскресенье)|\\d{1,2}\\s+(?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)|\\d{1,2}\\.\\d{1,2})(?![а-яё])", "i");
function factQuick(text) {
  const t = String(text || "").trim().replace(/^[А-ЯЁA-Z][а-яёa-z-]+\s*,\s*(?=\S)/, (m) => findPersona(m.replace(/[\s,]/g, ""), true) ? "" : m);
  const m = FACT_RX.exec(t); if (!m) return "";
  const body = m[1].trim().replace(/^(?:о\s+том\s*,?\s*)?что\s+/i, "").replace(/[.!…\s]+$/, "");
  if (body.length < 3 || body.length > 200 || FACT_SKIP.test(body) || !FACT_ME.test(body) || /\?$/.test(body)) return "";
  let day = null;
  if (DAY_WORD.test(body)) { const w = parseWhen(body); if (w && w.at && !w.rel) { day = new Date(w.at); day.setHours(0, 0, 0, 0); } }
  const fact = `Со слов пользователя: ${body}` + (day ? ` (на ${pad(day.getDate())}.${pad(day.getMonth() + 1)}.${day.getFullYear()}, ${WD[day.getDay()]})` : "") + ".";
  memAdd(fact);
  plog("info", "🧠 запомнила без модели" + (day ? ` (на ${day.getDate()} ${MON[day.getMonth()]})` : ""));
  if (SANDBOX) SANDBOX.dev.push({ name: "remember", args: fact, argsObj: { fact }, t: Date.now() });
  const she = persona().gender === "female" ? "Запомнила" : "Запомнил";
  const w = WD[day ? day.getDay() : 0], inDay = (w === "вторник" ? "во " : "в ") + ({ среда: "среду", пятница: "пятницу", суббота: "субботу" }[w] || w);
  return day ? `${she}: ${inDay}, ${day.getDate()} ${MON[day.getMonth()]}.` : `${she}.`;
}
/* Значок «Записать» (CaptureWidget): приложение открылось — сразу слушаем; сказанное — напоминание («напомни…»), заметка
   («запиши…») или мысль в «Заметки/Идеи» как есть, без модели. Записали — через пару секунд обратно на рабочий стол. */
let captureAt = 0, captureHome = 0;
function captureStart() {
  closeSheets(); captureAt = Date.now(); vCount("capture");
  showBot("Говорите — запишу в «Идеи». «Напомни завтра в 10…» — поставлю напоминание.");
  setTimeout(() => { if (state === "idle" || state === "speaking") listen(); }, 250);
}
function captureBack() {
  clearTimeout(captureHome);
  // ответ договорён (или текстом) — уходим на рабочий стол; человек начал что-то делать в приложении — остаёмся
  const t0 = Date.now(), tick = () => { if (Date.now() - lastUserAct < 1500 && Date.now() - t0 > 1500) return;
    if (state === "idle" && !busy) { try { D.home(); } catch (e) { } return; } if (Date.now() - t0 < 20000) captureHome = setTimeout(tick, 500); };
  captureHome = setTimeout(tick, 2600);
}
function ideaNote(text, att) {
  let body = String(text || "").trim().replace(/^[«"]|[»"]$/g, "");
  body = body ? body[0].toUpperCase() + body.slice(1) : "Фото";
  const words = body.replace(/[.!?…].*$/s, "").split(/\s+/), title = words.slice(0, 6).join(" ").replace(/[,:;—–-]+$/, "") + (words.length > 6 ? "…" : "");
  const files = noteAttSave(att || []); turnAtt = [];
  const n = notes(); n.push(Object.assign({ id: uid("n"), title, text: body, time: Date.now(), folder: "Идеи" }, files.length ? { att: files } : {})); saveNotes(n);
  plog("info", "💡 идея без модели: " + clip(title, 60));
  return `${persona().gender === "female" ? "Записала" : "Записал"} в «Идеи».`;
}
/* Папки заметок (№195, 22.10: «было бы удобно, если бы в заметках был функционал создания папок, особенно в мобильной
   версии»). Папка — поле folder заметки: с компьютера оно приходит путём («Заметки/Работа/…»), отсюда уходит туда же —
   компьютер переносит файл в эту папку (core/sync.py). Одна ступень: «Работа», «Блокнот», «Идеи». */
let ntFolder = "";                               // фильтр «Заметок»: "" — все
function noteFolders() {
  const set = new Set(notes().map(x => String(x.folder || "").trim()).filter(Boolean));
  return [...set].sort((a, b) => (a === "Блокнот" ? -1 : b === "Блокнот" ? 1 : a.localeCompare(b, "ru")));
}
function folderName(raw) {
  let f = String(raw || "").replace(/[\\/:*?"<>|«»]+/g, " ").replace(/\s+/g, " ").trim().slice(0, 40);
  if (!f) return "";
  const same = noteFolders().find(x => x.toLowerCase() === f.toLowerCase() || (f.length >= 5 && x.toLowerCase().slice(0, 5) === f.toLowerCase().slice(0, 5)));
  return same || f.charAt(0).toUpperCase() + f.slice(1);     // «в папку работу» → уже есть «Работа»
}
const NOTE_FOLDER_RX = /^(?:запиши|запишите|сохрани|добавь|занеси|положи)(?:\s+(?:мне|себе|пожалуйста))*\s+(?:в\s+)?(?:заметк[уи]\s+)?(?:в\s+)?папк[уеи]\s+«?([^:«»"\n]{1,40}?)»?\s*[:,—–-]\s*(\S[\s\S]{2,})$/i;
/* «Лира, запиши в книгу: герой проснулся рано утром…» (идеи пользователей 24.10: «отдельная папка для голосовых —
   пишу книгу, статью, стихи»): дословно, без модели, в конец заметки «Книга» в папке «Черновики» — со временем записи.
   Компьютер делает то же (core/engine_tools.py _draft_cmd), заметки синхронизируются. */
const DRAFT_KINDS = [["книг", "Книга"], ["стат", "Статья"], ["стих", "Стихи"], ["рассказ", "Рассказ"], ["роман", "Роман"], ["сценари", "Сценарий"],
  ["черновик", "Черновик"], ["песн", "Песня"], ["пост", "Пост"], ["сказк", "Сказка"], ["мемуар", "Мемуары"]];
const DRAFT_RX = /^(?:[А-ЯЁа-яёA-Za-z]+,\s*)?(?:запиши|допиши|добавь|занеси)\s+(?:в|во)\s+(?:мо[юйеи]\s+|наш[уеи]?\s+)?(книг[уеи]|стать[юи]|стих[иа]?|рассказ|роман|сценари[йи]|черновик|песн[юи]|пост|сказк[уи]|мемуары)(?:\s+[«"]([^»"]{2,40})[»"])?\s*(?:[:,—–-]\s*|\s+)(?:что\s+)?(\S[\s\S]{2,})$/i;
function draftQuick(text) {
  const m = DRAFT_RX.exec(String(text || "").trim()); if (!m) return "";
  const kind = m[1].toLowerCase().replace(/ё/g, "е"), title = (m[2] || "").trim() || DRAFT_KINDS.find(([k]) => kind.startsWith(k))[1];
  let body = m[3].trim(); body = body.charAt(0).toUpperCase() + body.slice(1); if (!/[.!?…»"]$/.test(body)) body += ".";
  const d = new Date(), stamp = `*${d.getDate()} ${MON[d.getMonth()]} ${d.getFullYear()}, ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}*`;
  const all = notes(), x = all.find(y => (y.folder || "") === "Черновики" && (y.title || "") === title);
  if (x && noteLocked(x.text)) return `Заметка «${title}» заперта — сначала откройте замок.`;
  if (x) { x.text = (x.text || "").replace(/\s+$/, "") + "\n\n" + stamp + "\n\n" + body; x.time = Date.now(); }
  else all.push({ id: uid("n"), title, text: stamp + "\n\n" + body, time: Date.now(), folder: "Черновики" });
  saveNotes(all);
  if (SANDBOX) SANDBOX.dev.push({ name: "save_note", args: title, t: Date.now() });
  const n = body.split(/\s+/).length, w = n % 10 === 1 && n % 100 !== 11 ? "слово" : n % 10 >= 2 && n % 10 <= 4 && !(n % 100 >= 12 && n % 100 <= 14) ? "слова" : "слов";
  const acc = { "Книга": "Книгу", "Статья": "Статью", "Песня": "Песню", "Сказка": "Сказку" }[title] || title;     // «в «Книгу»»
  return `${persona().gender === "female" ? "Записала" : "Записал"} в «${acc}» — ${n} ${w}.`;
}
function noteQuick(text, att) {
  const t = String(text || "").trim().replace(/^[А-ЯЁA-Z][а-яёa-z-]+\s*,\s*(?=\S)/, (m) => findPersona(m.replace(/[\s,]/g, ""), true) ? "" : m);
  const mf = NOTE_FOLDER_RX.exec(t);
  const m = mf ? [mf[0], mf[2]] : NOTE_RX.exec(t); if (!m) return "";
  const folder = mf ? folderName(mf[1]) : "";
  let body = m[1].trim().replace(/^[«"]|[»"]$/g, "");
  if (!/[а-яёa-z0-9]/i.test(body) || /^(?:что|как|где|сколько|покажи|прочитай)(?:\s|$)/i.test(body)) return "";   // «в заметках что?» — не запись
  body = body.charAt(0).toUpperCase() + body.slice(1);
  const words = body.replace(/[.!?…].*$/s, "").split(/\s+/), title = words.slice(0, 6).join(" ").replace(/[,:;—–-]+$/, "") + (words.length > 6 ? "…" : "");
  const files = noteAttSave(att || []); turnAtt = [];
  const n = notes(); n.push(Object.assign({ id: uid("n"), title, text: body, time: Date.now() }, files.length ? { att: files } : {}, folder ? { folder } : {})); saveNotes(n);
  plog("info", "📝 заметка без модели: " + clip(title, 60) + (folder ? ` → папка «${folder}»` : "") + (files.length ? ` + вложений ${files.length}` : ""));
  if (SANDBOX) SANDBOX.dev.push({ name: "save_note", args: title, t: Date.now() });      // экзамен: действие видно, как фонарик
  // без пересказа: название обрезано («…»), и вслух это звучало как оборванная фраза (отзыв 11.10)
  const pics = files.filter(f => f.type === "image").length;
  return `${persona().gender === "female" ? "Записала" : "Записал"} ${folder ? `в папку «${folder}»` : "в заметки"}` + (!files.length ? "." : files.length === 1 ? (pics ? " вместе с фото." : " вместе с файлом.") : ` — вложений: ${files.length}.`);
}
/* Напоминание с вложениями (идея 16.10: «на завтра напоминание, и чтобы там пара скриншотов, и удобно сразу посмотреть»):
   «напомни завтра в 10» + фото (скрепка или «Поделиться» из галереи) — заметка «Напоминания» с этими фото и напоминание
   с note = её id. В срок окно напоминания показывает «Посмотреть вложения» (AlarmActivity → openNote). Заметка уходит
   на компьютер синхронизацией, фото — зашифрованным каналом (noteAttShare), и там окно-будильник покажет их миниатюрами. */
const REMIND_GENERIC = /^(?:напоминание|(?:(?:об?|про)\s+)?(?:это|этом|этой|этого|них|ней|нем|нём|него|неё|нее)|(?:(?:об?|про)\s+)?(?:эт[а-яё]+\s+)?(?:скрин[а-яё]*|фот[а-яё]*|картинк[а-яё]*|снимк[а-яё]*|файл[а-яё]*))?$/i;
function remindNote(title, at, said, att) {
  const files = noteAttSave(att || []); if (!files.length) return null;
  const pics = files.filter(f => f.type === "image").length;
  let t = String(title || "").trim();
  if (REMIND_GENERIC.test(t)) t = pics === files.length ? "Посмотреть фото" : !pics ? "Посмотреть файлы" : "Посмотреть вложения";
  t = t[0].toUpperCase() + t.slice(1);
  const d = new Date(at), body = `Напоминание — ${d.getDate()} ${MON[d.getMonth()]} в ${pad(d.getHours())}:${pad(d.getMinutes())}.` + (said ? `\n\n«${String(said).trim()}»` : "");
  const n = { id: uid("n"), title: t, text: body, time: Date.now(), folder: "Напоминания", att: files };
  const all = notes(); all.push(n); saveNotes(all);
  plog("info", `📎 напоминание с вложениями (${files.length}) → заметка «${clip(t, 50)}»`);
  if (SANDBOX) SANDBOX.dev.push({ name: "save_note", args: t, t: Date.now() });
  return n;
}
function remindAttQuick(text, att) {
  const t = String(text || "").trim().replace(/^[А-ЯЁA-Z][а-яёa-z-]+\s*,\s*(?=\S)/, (m) => findPersona(m.replace(/[\s,]/g, ""), true) ? "" : m).toLowerCase().replace(/ё/g, "е");
  const m = t.match(/^напомни(?:те)?(?: мне)?\s+(.+)$/) || t.match(/^напоминай(?: мне)?\s+(.+)$/); if (!m) return null;
  const w = parseWhen(m[1]); if (!w) return null;
  let what = remindWhat(w.rest);
  const n = remindNote(what, w.at, text, att); if (!n) return null;
  turnAtt = [];
  const x = addAlarm(n.title, w.at, "reminder", w.repeat, n.id);
  const pics = n.att.filter(f => f.type === "image").length, many = n.att.length > 1;
  const tail = pics === n.att.length ? (many ? "Фото будут прямо в напоминании." : "Фото будет прямо в напоминании.") : (many ? "Файлы будут прямо в напоминании." : "Файл будет прямо в напоминании.");
  return { say: `Напомню ${repRu(w.repeat) ? repRu(w.repeat) + ", " : ""}${whenText(w.at)}: ${n.title[0].toLowerCase() + n.title.slice(1)}. ${tail}`, card: alarmCard(x) };
}
/* ---------- заметка целиком: открыть, поправить, фото и файлы (лист #sh-note) ----------
   Вложения — файлы natt-<id> во внутренней памяти (data: URL; фото сжаты shrinkImage), в заметке — только их список att.
   Синхронизация уносит на компьютер текст заметки; вложения — зашифрованным каналом своих устройств (noteAttShare). */
let turnAtt = [], turnAsk = "", noteCur = "", notePend = [];
// шапка заметки «---» (Obsidian, перенос из Google Keep; core/workspace.py note_front) — не показываем, при правке сохраняем
const NOTE_FRONT = /^\ufeff?(-{2,3})[ \t]*\n((?:[ \t]*(?:[\w\-а-яёА-ЯЁ]+[ \t]*:.*|-[ \t].*|)\n)*?)\1[ \t]*(?:\n|$)/;
const noteFront = (t) => { const m = NOTE_FRONT.exec(String(t || "")); return m && m[2].trim() ? m[0].replace(/\n?$/, "\n") : ""; };
const noteBody = (t) => String(t || "").slice(noteFront(t).length).replace(/^\s*#[^\n]*\n+(\*[^\n]*\*\n+)?/, "");   // заметка с компьютера: без шапки, заголовка и даты
/* Замок (владелец 05.11: «информация настолько важная, что переживаю — не сотру ли случайно»): «locked: true» в шапке
   заметки — то же поле, что на компьютере (core/workspace.py note_front_set), и уходит синхронизацией вместе с текстом.
   Запертую нельзя изменить и удалить — ни руками, ни Лирой; открыть замок — только кнопкой 🔒 у названия. */
const NOTE_LOCKED = "Заметка заперта — сначала откройте замок 🔒";
const noteLocked = (t) => /^\s*locked\s*:\s*(true|yes|1|да)\s*$/mi.test(noteFront(t));
function noteLockSet(t, on) {
  t = String(t || ""); const fr = noteFront(t); let rest = t.slice(fr.length);
  const lines = (fr ? fr.replace(/\n$/, "").split("\n").slice(1, -1) : []).filter(l => l.trim() && !/^\s*locked\s*:/i.test(l));
  if (on) lines.push("locked: true");
  if (!lines.length) return rest.replace(/^\n+/, "");
  return "---\n" + lines.join("\n") + "\n---\n" + (rest.startsWith("\n") ? rest : "\n" + rest);
}
// пришедшая с другого устройства — та же заметка, кроме замка (его открыли или заперли там руками)
const noteLockOnly = (a, b) => { const k = (t) => { const u = noteLockSet(t, false); return noteFront(u) + "|" + noteBody(u).replace(/\s+/g, " ").trim(); }; return k(a) === k(b); };
// строки-ссылки на вложения компьютера («![фото.jpg](Вложения/…)», «📎 [план.pdf](Вложения/…)», core/workspace.py NOTE_LINK_RX):
// в тексте на телефоне их не показываем, а при сохранении возвращаем в конец — иначе ссылки потерялись бы на компьютере
const NOTE_LINK_LINE = /^[ \t]*(?:📎\s*)?!?\[[^\]\n]*\]\(Вложения\/[^)\s]+\)[ \t]*$/gm;
const noteShown = (t) => noteBody(t).replace(NOTE_LINK_LINE, "").replace(/\n{3,}/g, "\n\n").trim();
/* Начало заметки в списке — без значков Markdown (№246: «в заметках на телефоне сырой маркдаун»; блокнот компьютера
   пишет **жирное**, ## заголовки, > цитаты): жирное и заголовки — жирным, пункты — «•», задачи — ☐/☑, схема — пометкой.
   opt.flat (список заметок, 03.11 — владелец: «одинокий „•“ на своей строке, пункты жирным»): одной строкой, как в
   Google Keep, — без жирного и курсива, пункты идут потоком через « · », заголовок — «Продукты:», пустые пункты пропущены.
   -> HTML не длиннее max видимых знаков. */
function mdPreview(t, max = 220, opt = {}) {
  const out = [], flat = !!opt.flat; let n = 0, fence = null, prevItem = false;
  const plain = (s) => s.replace(/!\[[^\]]*\]\([^)]*\)/g, "").replace(/\[([^\]]+)\]\([^)]*\)/g, "$1").replace(/==([^=]+)==/g, "$1");
  for (const raw of String(t || "").split("\n")) {
    if (n >= max) break;
    const l = raw.trim(); let m, s, bold = false;
    if (/^```/.test(l)) { if (fence === null) { fence = l.slice(3).trim(); if (fence === "mermaid") { if (flat && out.length) out.push(" "); out.push("◇ схема"); n += 8; prevItem = false; } } else fence = null; continue; }
    if (fence !== null || !l || /^(-{3,}|\*{3,}|_{3,})$/.test(l) || /^\|?\s*:?-{2,}/.test(l)) continue;
    if (/^(?:[-*+•]|\d+[.)])(?:\s*\[[ xX]?\])?$/.test(l)) continue;           // пустой пункт («•» или «-» без текста) — не показываем
    let item = false;
    if ((m = l.match(/^#{1,6}\s+(.*)$/))) { s = m[1]; bold = true; }
    else if ((m = l.match(/^[-*+]\s+\[([ xX])\]\s*(.*)$/))) { s = (m[1] === " " ? "☐ " : "☑ ") + m[2]; item = true; }
    else if ((m = l.match(/^(?:[-*+•]|\d+[.)])\s+(.*)$/))) { s = flat ? m[1] : "• " + m[1]; item = true; }
    else if ((m = l.match(/^>\s?(.*)$/))) s = m[1];
    else if (/^\|.*\|$/.test(l)) s = l.replace(/^\||\|$/g, "").split("|").map(c => c.trim()).filter(Boolean).join(" · ");
    else s = l;
    s = plain(s); if (!s.trim()) continue;
    // без «взгляда назад»: символ перед * — обратно; «**» и «__» — сначала, иначе от « **жирного**» оставалась одна «*»
    const vis = s.replace(/\*\*|__/g, "").replace(/(^|\s)[*_](?=\S)|(\S)[*_](?=\s|$|[.,!?:;])|`/g, "$1$2");
    let piece = vis.length > max - n ? vis.slice(0, Math.max(0, max - n)).replace(/\s+\S*$/, "") + "…" : null;
    n += vis.length + 1;
    if (flat) {                                     // одной строкой: пункты — через « · », заголовок — с двоеточием
      let h = esc(piece || vis).replace(/^([☐☑]) /, "$1\u00a0");     // значок дела не отрывается от текста
      if (bold && !piece && !/[.:!?…]$/.test(vis)) h += ":";
      if (out.length) out.push(prevItem || bold ? " · " : " ");
      out.push(h); prevItem = item;
      continue;
    }
    let h = esc(piece || s);
    if (!piece) h = h.replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>").replace(/\*\*/g, "").replace(/(^|[\s(«])[*_]([^*_\n]+)[*_](?=$|[\s.,!?:;)»])/g, "$1<i>$2</i>").replace(/`([^`]+)`/g, "$1");
    out.push(bold ? `<b>${h}</b>` : h);
  }
  return out.join(flat ? "" : " ");
}
const noteLinks = (t) => (String(t || "").match(NOTE_LINK_LINE) || []).map(x => x.trim());
const noteAttGet = (id) => fileGet("natt-" + id) || "";
const noteAttCount = (n) => (n.att || []).length || noteLinks(n.text).length;     // свои вложения или ссылки на вложения компьютера
function noteAttSave(list) {
  return (list || []).filter(a => a && (a.url || a.text != null)).slice(0, 12).map((a, i) => {
    const id = "na" + Date.now().toString(36) + i + Math.random().toString(36).slice(2, 5);
    const data = a.url || ("data:text/plain;charset=utf-8," + encodeURIComponent(a.text || ""));
    fileSave("natt-" + id, data);
    return { id, name: String(a.name || (a.kind === "image" ? "фото" : "файл")).slice(0, 120), type: a.kind === "image" || /^data:image\//.test(data) ? "image" : (a.type || "file"), size: Math.round(data.length * 0.75) };
  });
}
/* Удалить заметку: всегда спрашиваем, и ещё 8 секунд можно «Вернуть» — вместе с вложениями (отзыв 11.10: одно
   случайное нажатие — и заметки нет). Удалить — только из открытой заметки, крестика в списке нет. */
function noteDelete(id, ask) {
  const n = notes().find(x => x.id === id); if (!n) return;
  if (noteLocked(n.text)) { toast(NOTE_LOCKED, 3200); return; }      // замок (здесь или с компьютера): не удаляется
  if (ask && !confirm(`Удалить заметку «${n.title}»${(n.att || []).length ? " вместе с вложениями" : ""}?`)) return;
  const keep = (n.att || []).map(a => [a.id, noteAttGet(a.id)]);
  (n.att || []).forEach(a => fileSave("natt-" + a.id, ""));
  saveNotes(notes().filter(x => x.id !== id)); if (noteCur === id) { closeSheets(); renderDay(); openSheet("#sh-day"); } else renderDay();   // №342: не на главный экран
  if (ask) undoBar("Заметка удалена", () => {
    keep.forEach(([aid, data]) => fileSave("natt-" + aid, data));
    const all = notes(); if (!all.some(x => x.id === n.id)) { all.push(n); saveNotes(all); }
    renderDay(); toast("Заметка возвращена");
  });
}
function undoBar(text, onUndo, ms = 8000) {
  let el = $("#undo"); if (!el) { el = document.createElement("div"); el.id = "undo"; document.body.appendChild(el); }
  el.innerHTML = `<span>${esc(text)}</span><button>Вернуть</button>`; el.classList.add("on");
  clearTimeout(el._t); el._t = setTimeout(() => el.classList.remove("on"), ms);
  el.querySelector("button").onclick = () => { clearTimeout(el._t); el.classList.remove("on"); onUndo(); };
}
// заметка напоминания: может ещё не прийти с компьютера — синхронизируем и пробуем снова
async function openNoteSoon(id) {
  closeSheets();
  if (!notes().some(x => x.id === id)) { toast("Получаю заметку с вложениями…", 2500); try { await syncRun(true); } catch (e) { } }
  if (notes().some(x => x.id === id)) openNote(id); else toast("Заметка с вложениями ещё не пришла — проверьте, что компьютер включён", 4000);
}
/* Заметка на телефоне (владелец 27.10: «заметки — одна из важнейших частей Лиры… открывается только для правки в
   сыром Markdown — неудобно и некрасиво; при выборе папки — странные серые блоки»; №321, №342). Открытая заметка —
   сначала ЧТЕНИЕ: заголовок, папка и дата, текст оформлен (заголовки, жирный, списки, дела — галочкой можно отметить
   прямо здесь, цитаты, ссылки, таблицы, схемы), фото крупными плитками. «Править» — тот же лист в правке: заголовок,
   текст с мини-панелью (заголовок, жирный, пункт, дело), папка — чипами (свой выпадающий список WebView рисовал серые
   плашки), вложения с «×». Новая заметка — сразу правка. */
let noteMode = "view";
function openNote(id) { noteCur = id || ""; notePend = []; noteMode = id ? "view" : "edit"; renderNote(); openSheet("#sh-note"); if (!id) setTimeout(() => $("#nt-text") && $("#nt-text").focus(), 300); }
const NT_IC = {
  edit: '<svg viewBox="0 0 24 24"><path d="M4 20h4L19 9l-4-4L4 16v4z"/><path d="m13.5 6.5 4 4"/></svg>',
  share: '<svg viewBox="0 0 24 24"><path d="M12 15V4M8 8l4-4 4 4"/><path d="M5 12v6a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-6"/></svg>',
  del: '<svg viewBox="0 0 24 24"><path d="M4.5 7h15M9.5 7V5a1 1 0 0 1 1-1h3a1 1 0 0 1 1 1v2M6.5 7l1 12.5a1.5 1.5 0 0 0 1.5 1.4h6a1.5 1.5 0 0 0 1.5-1.4L17.5 7"/></svg>',
  fold: '<svg viewBox="0 0 24 24"><path d="M3.5 7.5A1.5 1.5 0 0 1 5 6h4.2l2 2H19a1.5 1.5 0 0 1 1.5 1.5v8A1.5 1.5 0 0 1 19 19H5a1.5 1.5 0 0 1-1.5-1.5z"/></svg>',
  photo: '<svg viewBox="0 0 24 24"><rect x="3.5" y="5.5" width="17" height="13" rx="2.5"/><circle cx="9" cy="10" r="1.6"/><path d="m4.5 17 5-4.5 4 3.5 2.5-2 3.5 3"/></svg>',
  file: '<svg viewBox="0 0 24 24"><path d="M14 3.5H7.5a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2h9a2 2 0 0 0 2-2V8z"/><path d="M14 3.5V8h4.5"/></svg>',
  x: '<svg viewBox="0 0 24 24"><path d="M6.5 6.5l11 11M17.5 6.5l-11 11"/></svg>',
  plus: '<svg viewBox="0 0 24 24"><path d="M12 5v14M5 12h14"/></svg>',
};
/* Текст заметки → HTML для чтения. Дела «- [ ]» — кнопками с номером строки (data-ln): нажали — галочка в тексте. */
function noteHtml(t) {
  const lines = String(t || "").split("\n"), out = [];
  let list = "", table = [], code = null, quote = [];
  const inl = (x) => esc(x).replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, (m, a, u) => `<a href="${u.replace(/"/g, "%22")}" data-url="${u.replace(/"/g, "%22")}">${a}</a>`)
    .replace(/(^|[\s(«])(https?:\/\/[^\s<»)]+)/g, (m, a, u) => `${a}<a href="${u}" data-url="${u}">${u.replace(/^https?:\/\/(www\.)?/, "").slice(0, 40)}</a>`)
    .replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>").replace(/__([^_]+)__/g, "<b>$1</b>").replace(/(^|[^*\w])\*([^*\n]+)\*/g, "$1<i>$2</i>")
    .replace(/~~([^~]+)~~/g, "<s>$1</s>").replace(/==([^=]+)==/g, "<mark>$1</mark>").replace(/`([^`]+)`/g, "<code>$1</code>");
  const flushList = () => { if (list) { out.push(`</${list}>`); list = ""; } };
  const flushQuote = () => { if (quote.length) { out.push(`<blockquote>${quote.map(inl).join("<br>")}</blockquote>`); quote = []; } };
  const flushTable = () => {
    if (!table.length) return;
    const rows = table.filter(r => !/^\|?\s*:?-{2,}/.test(r)).map(r => r.replace(/^\||\|$/g, "").split("|").map(c => c.trim().split(/<br\s*\/?>/i).map(inl).join("<br>")));   // перевод строки в ячейке — <br> (блокнот)
    out.push(`<div class="tbl"><table>${rows.map((r, i) => `<tr>${r.map(c => i ? `<td>${c}</td>` : `<th>${c}</th>`).join("")}</tr>`).join("")}</table></div>`);
    table = [];
  };
  lines.forEach((raw, ln) => {
    const l = raw.trim(); let m;
    if (/^```/.test(l)) {
      if (code === null) { flushList(); flushTable(); flushQuote(); code = { lang: l.slice(3).trim(), rows: [] }; }
      else { out.push(`<pre><code class="language-${code.lang.replace(/[^\w-]/g, "")}">${esc(code.rows.join("\n"))}</code></pre>`); code = null; }
      return;
    }
    if (code !== null) { code.rows.push(raw); return; }
    if (/^\|.*\|$/.test(l)) { flushList(); flushQuote(); table.push(l); return; }
    flushTable();
    if ((m = l.match(/^>\s?(.*)$/))) { flushList(); quote.push(m[1]); return; }
    flushQuote();
    if ((m = l.match(/^(#{1,6})\s+(.*)$/))) { flushList(); const h = Math.min(4, m[1].length + 1); out.push(`<h${h}>${inl(m[2])}</h${h}>`); }
    else if (/^(-{3,}|\*{3,}|_{3,})$/.test(l)) { flushList(); out.push("<hr>"); }
    else if ((m = l.match(/^[-*+]\s+\[([ xX])\]\s*(.*)$/))) {
      if (list !== "ul class=\"tasks\"") { flushList(); out.push('<ul class="tasks">'); list = "ul class=\"tasks\""; }
      const done = m[1] !== " ";
      out.push(`<li class="${done ? "done" : ""}"><button class="tk" data-ln="${ln}" aria-pressed="${done}" aria-label="${done ? "Сделано" : "Отметить"}"></button><span>${inl(m[2])}</span></li>`);
    }
    else if ((m = l.match(/^[-*+•]\s+(.*)$/))) { if (list !== "ul") { flushList(); out.push("<ul>"); list = "ul"; } out.push(`<li>${inl(m[1])}</li>`); }
    else if ((m = l.match(/^(\d+)[.)]\s+(.*)$/))) { if (list !== "ol") { flushList(); out.push(+m[1] > 1 ? `<ol start="${+m[1]}">` : "<ol>"); list = "ol"; } out.push(`<li>${inl(m[2])}</li>`); }
    else if (!l) { if (list && lines.slice(ln + 1).find(x => x.trim()) && /^\s*(?:[-*+•]|\d+[.)])\s/.test(lines.slice(ln + 1).find(x => x.trim()))) return; flushList(); }
    else { flushList(); out.push(`<p>${inl(l)}</p>`); }
  });
  if (code !== null) out.push(`<pre><code>${esc(code.rows.join("\n"))}</code></pre>`);
  flushList(); flushTable(); flushQuote();
  return out.join("") || '<p class="ntempty">Пустая заметка — нажмите «Править», чтобы написать.</p>';
}
const ntDate = (ms) => { const d = new Date(+ms || Date.now()), now = new Date(), t = `${pad(d.getHours())}:${pad(d.getMinutes())}`;
  if (d.toDateString() === now.toDateString()) return "сегодня в " + t;
  const y = new Date(now); y.setDate(now.getDate() - 1); if (d.toDateString() === y.toDateString()) return "вчера в " + t;
  return `${d.getDate()} ${MON[d.getMonth()]}${d.getFullYear() !== now.getFullYear() ? " " + d.getFullYear() : ""}, ${t}`; };
function renderNote() {
  const n = noteCur ? notes().find(x => x.id === noteCur) : null, att = (n ? n.att || [] : []).concat(notePend);
  if (!n) noteMode = "edit";
  const sh = $("#sh-note"); sh.classList.toggle("ntv", noteMode === "view"); sh.classList.toggle("nte", noteMode === "edit");
  const attHtml = (edit) => att.map(a => a.type === "image"
      ? `<div class="ntimg"><button class="ntopen" data-id="${esc(a.id)}" aria-label="Открыть фото ${esc(a.name)}"><img src="${a.data || noteAttGet(a.id)}" alt=""></button>${edit ? `<button class="ntrm" data-rm="${esc(a.id)}" aria-label="Убрать фото">${NT_IC.x}</button>` : ""}</div>`
      : `<div class="ntfile"><button class="ntopen" data-id="${esc(a.id)}">${NT_IC.file}<span>${esc(a.name)}</span><small>${fsize(a.size)}</small></button>${edit ? `<button class="ntrm" data-rm="${esc(a.id)}" aria-label="Убрать файл">${NT_IC.x}</button>` : ""}</div>`).join("");
  const view = (a) => a.type === "image" ? imgView(a.data || noteAttGet(a.id)) : noteFileSave(a);
  if (noteMode === "view") {
    const lk = noteLocked(n.text);
    $("#nt-h").textContent = n.title || "Заметка";
    const lb = $("#nt-lock"); lb.hidden = false; lb.classList.toggle("on", lk); lb.textContent = lk ? "🔒" : "🔓";
    lb.setAttribute("aria-pressed", String(lk)); lb.setAttribute("aria-label", lk ? "Открыть замок" : "Запереть заметку");
    $("#note-body").innerHTML = `<div class="ntmeta">${n.folder ? `<button class="ntchip" id="nt-gofold">${NT_IC.fold}${esc(n.folder)}</button>` : ""}<span>${esc(ntDate(n.time))}</span></div>
      <article class="ntread" id="nt-read">${noteHtml(noteShown(n.text))}</article>
      ${att.length ? `<div class="ntatt big">${attHtml(false)}</div>` : ""}
      ${lk ? `<div class="ntlocked">🔒 Заперта: не изменить и не удалить — ни здесь, ни голосом, ни на компьютере. Открыть — 🔒 у названия.</div>` : ""}
      <div class="ntbar"><button class="btn p${lk ? " off" : ""}" id="nt-edit">${NT_IC.edit}Править</button><button class="btn ic" id="nt-share" aria-label="Поделиться" title="Поделиться">${NT_IC.share}</button><button class="btn ic dl" id="nt-del" aria-label="Удалить" title="Удалить">${NT_IC.del}</button></div>`;
    if (window.DewiarRich) DewiarRich.diagrams($("#nt-read"));
    $$("#nt-read a[data-url]").forEach(a => a.onclick = (e) => { e.preventDefault(); D.openUrl(a.dataset.url); });
    $$("#nt-read .tk").forEach(b => b.onclick = () => {                       // дело отметили прямо в чтении
      const all = notes(), x = all.find(y => y.id === n.id); if (!x) return;
      if (noteLocked(x.text)) { toast(NOTE_LOCKED, 3200); return; }
      const shown = noteShown(x.text).split("\n"), i = +b.dataset.ln, line = shown[i] || "";
      shown[i] = /\[[ ]\]/.test(line) ? line.replace("[ ]", "[x]") : line.replace(/\[[xX]\]/, "[ ]");
      const fr = noteFront(x.text), head = String(x.text || "").slice(fr.length).match(/^\s*#[^\n]*\n+(\*[^\n]*\*\n+)?/), ln = noteLinks(x.text);
      x.text = fr + (head ? head[0] : "") + shown.join("\n") + (ln.length ? "\n\n" + ln.join("\n") : ""); x.time = Date.now(); saveNotes(all);
      const li = b.closest("li"), on = !li.classList.contains("done"); li.classList.toggle("done", on); b.setAttribute("aria-pressed", on);
    });
    $$("#note-body .ntopen").forEach(b => b.onclick = () => { const a = att.find(x => x.id === b.dataset.id); if (a) view(a); });
    $("#nt-edit").onclick = () => { if (lk) { toast(NOTE_LOCKED, 3200); return; } noteMode = "edit"; renderNote(); setTimeout(() => $("#nt-text") && $("#nt-text").focus(), 200); };
    $("#nt-lock").onclick = () => {                                          // 🔒 — запереть / открыть одним нажатием
      const all = notes(), x = all.find(y => y.id === n.id); if (!x) return;
      x.text = noteLockSet(x.text, !lk); x.time = Date.now(); saveNotes(all); renderDay(); renderNote();
      toast(lk ? "Замок открыт — заметку можно менять и удалять" : "Заперта — не изменится и не удалится, пока не откроете замок", 2600); };
    $("#nt-del").onclick = () => noteDelete(n.id, true);
    $("#nt-share").onclick = () => D.share((n.title ? n.title + "\n\n" : "") + noteShown(n.text));
    if ($("#nt-gofold")) $("#nt-gofold").onclick = () => { ntFolder = n.folder; closeSheets(); renderDay(); openSheet("#sh-day"); };
    return;
  }
  $("#nt-h").textContent = n ? "Правка" : "Новая заметка"; $("#nt-lock").hidden = true;
  const folds = noteFolders(), cur = n ? folderName(n.folder || "") : folderName(ntFolder || "");
  $("#note-body").innerHTML = `<input id="nt-title" placeholder="Заголовок" maxlength="120" value="${esc(n ? n.title : "")}" aria-label="Заголовок">
    <div class="ntmd" role="toolbar" aria-label="Оформление"><button data-md="h">Заголовок</button><button data-md="b"><b>Ж</b></button><button data-md="li">• Пункт</button><button data-md="task">☐ Дело</button></div>
    <textarea id="nt-text" placeholder="Текст заметки…" aria-label="Текст заметки">${esc(n ? noteShown(n.text) : "")}</textarea>
    <div class="ntlbl">${NT_IC.fold}Папка</div>
    <div class="ntfolds pick" id="nt-folds" role="radiogroup" aria-label="Папка">${["", ...folds.filter(f => f !== cur), ...(cur ? [cur] : [])].sort((a, b) => a === "" ? -1 : b === "" ? 1 : 0)
      .map(f => `<button role="radio" data-f="${esc(f)}" class="${f === cur ? "on" : ""}" aria-checked="${f === cur}">${f ? esc(f) : "Без папки"}</button>`).join("")}<button class="add" id="nt-newf">${NT_IC.plus}Новая</button></div>
    <input id="nt-folder" type="hidden" value="${esc(cur)}">
    <div class="ntatt">${attHtml(true)}</div>
    <div class="ntadd"><label class="btn">${NT_IC.photo}<input type="file" id="nt-photo" accept="image/*" multiple hidden>Фото</label><label class="btn">${NT_IC.file}<input type="file" id="nt-file" multiple hidden>Файл</label></div>
    <div class="ntbar">${n ? `<button class="btn" id="nt-cancel">Отмена</button>` : ""}<button class="btn p" id="nt-save">Сохранить</button></div>`;
  const ta = $("#nt-text"), grow = () => { ta.style.height = "auto"; ta.style.height = Math.min(Math.max(ta.scrollHeight + 2, 180), innerHeight * 0.55) + "px"; };
  ta.addEventListener("input", grow); setTimeout(grow, 0);
  $$("#nt-folds [data-f]").forEach(b => b.onclick = () => { $$("#nt-folds [data-f]").forEach(x => { x.classList.toggle("on", x === b); x.setAttribute("aria-checked", x === b); }); $("#nt-folder").value = b.dataset.f; });
  $("#nt-newf").onclick = () => {
    const box = $("#nt-folds"); if ($("#nt-fname")) { $("#nt-fname").focus(); return; }
    const i = document.createElement("input"); i.id = "nt-fname"; i.placeholder = "Название папки"; i.maxLength = 40; box.insertBefore(i, $("#nt-newf")); i.focus();
    let took = false;
    const take = () => { if (took || !i.isConnected) return; took = true; const v = folderName(i.value); if (!v) { i.remove(); return; }
      $$("#nt-folds [data-f]").forEach(x => { x.classList.remove("on"); x.setAttribute("aria-checked", false); });
      const b = document.createElement("button"); b.setAttribute("role", "radio"); b.dataset.f = v; b.textContent = v; b.className = "on"; b.setAttribute("aria-checked", true);
      b.onclick = () => { $$("#nt-folds [data-f]").forEach(x => { x.classList.toggle("on", x === b); x.setAttribute("aria-checked", x === b); }); $("#nt-folder").value = v; };
      i.replaceWith(b); $("#nt-folder").value = v; };
    i.onkeydown = (e) => { if (e.key === "Enter") { e.preventDefault(); take(); } }; i.onblur = take;
  };
  $$(".ntmd button").forEach(b => { b.onmousedown = (e) => e.preventDefault(); b.onclick = () => {
    const v = ta.value, a = ta.selectionStart, z = ta.selectionEnd, k = b.dataset.md;
    if (k === "b") { const sel = v.slice(a, z) || "жирный"; ta.setRangeText(`**${sel}**`, a, z, "end"); }
    else { const ls = v.lastIndexOf("\n", a - 1) + 1, pre = { h: "## ", li: "- ", task: "- [ ] " }[k], line = v.slice(ls);
      if (line.startsWith(pre)) ta.setRangeText("", ls, ls + pre.length, "end"); else ta.setRangeText(pre, ls, ls, "end"); }
    ta.focus(); grow(); }; });
  $$("#note-body .ntopen").forEach(b => b.onclick = () => { const a = att.find(x => x.id === b.dataset.id); if (a) view(a); });
  $$("#note-body .ntrm").forEach(b => b.onclick = () => {
    const id = b.dataset.rm; keepTyped();
    if (notePend.some(x => x.id === id)) notePend = notePend.filter(x => x.id !== id);
    else if (n) { const all = notes(), x = all.find(y => y.id === n.id); if (x) { x.att = (x.att || []).filter(a => a.id !== id); x.time = Date.now(); saveNotes(all); fileSave("natt-" + id, ""); } }
    renderNote(); restoreTyped();
  });
  const add = async (files, photo) => {
    for (const f of Array.from(files || [])) {
      if (f.size > 10 * 1024 * 1024) { toast(`«${f.name}» больше 10 МБ`); continue; }
      try {
        const url = photo || /^image\//.test(f.type) ? await shrinkImage(f) : await new Promise((ok, no) => { const r = new FileReader(); r.onload = () => ok(r.result); r.onerror = () => no(new Error("не прочитался")); r.readAsDataURL(f); });
        const one = { kind: /^data:image\//.test(url) ? "image" : "file", name: f.name || "файл", type: f.type, url };
        if (n) { const saved = noteAttSave([one]); const all = notes(); const x = all.find(y => y.id === n.id); if (x) { x.att = (x.att || []).concat(saved); x.time = Date.now(); saveNotes(all); } }
        else notePend.push({ id: uid("p"), name: one.name, type: one.kind === "image" ? "image" : (f.type || "file"), size: f.size, data: url, src: one });
      } catch (e) { toast("Не получилось добавить: " + e.message); }
    }
    keepTyped(); renderNote(); restoreTyped();
  };
  let typed = null; const keepTyped = () => { typed = { t: $("#nt-title").value, x: $("#nt-text").value, f: $("#nt-folder").value }; };
  const restoreTyped = () => { if (typed) { $("#nt-title").value = typed.t; $("#nt-text").value = typed.x; $("#nt-folder").value = typed.f;
    $$("#nt-folds [data-f]").forEach(x => { x.classList.toggle("on", x.dataset.f === typed.f); x.setAttribute("aria-checked", x.dataset.f === typed.f); }); grow(); } };
  $("#nt-photo").onchange = (e) => add(e.target.files, true);
  $("#nt-file").onchange = (e) => add(e.target.files, false);
  if ($("#nt-cancel")) $("#nt-cancel").onclick = () => { noteMode = "view"; notePend = []; renderNote(); };
  $("#nt-save").onclick = () => {
    if ($("#nt-fname")) $("#nt-fname").blur();
    const title = $("#nt-title").value.trim(), text = $("#nt-text").value.trim();
    if (!title && !text && !notePend.length) { toast("Пустая заметка"); return; }
    const all = notes(), t0 = title || text.split(/\n/)[0].replace(/^#+\s*|^[-*]\s+(\[[ xX]\]\s*)?/, "").slice(0, 60) || "Фото", fold = folderName($("#nt-folder").value);
    if (n && noteLocked((all.find(y => y.id === n.id) || {}).text)) { toast(NOTE_LOCKED, 3200); noteMode = "view"; renderNote(); return; }   // заперли на другом устройстве, пока правили
    if (n) { const x = all.find(y => y.id === n.id), ln = noteLinks(x && x.text); if (x) { x.title = t0; x.text = noteFront(x.text) + text + (ln.length ? "\n\n" + ln.join("\n") : ""); x.time = Date.now(); x.folder = fold; } }
    else { const id = uid("n"); all.push(Object.assign({ id, title: t0, text, time: Date.now() }, notePend.length ? { att: noteAttSave(notePend.map(p => p.src)) } : {}, fold ? { folder: fold } : {})); noteCur = id; }
    notePend = []; saveNotes(all); renderDay(); noteMode = "view"; renderNote(); toast("Заметка сохранена");
  };
}
function noteFileSave(a) {
  const d = noteAttGet(a.id), m = /^data:([^;,]*)(?:;[^;,=]+=[^;,]*)*(;base64)?,(.*)$/s.exec(d);
  if (!m) { toast("Файл не найден"); return; }
  const b64 = m[2] ? m[3] : btoa(unescape(encodeURIComponent(decodeURIComponent(m[3]))));
  const where = D.saveDownloadB64 ? D.saveDownloadB64(a.name, m[1] || "application/octet-stream", b64) : "";
  toast(where ? "Сохранено: " + where : "Не получилось сохранить", 3500);
}
/* Фото на весь экран (владелец 27.10: «нажал на фото — открылось на весь экран, и назад вернуться никак»): «×» в углу,
   нажатие по фото и кнопка «Назад» телефона закрывают просмотр (N.back), а лист заметки остаётся открытым. */
function imgView(src) {
  const v = $("#imgview"); $("img", v).src = src; v.classList.add("on");
  if (!$(".ivx", v)) { const x = document.createElement("button"); x.className = "ivx"; x.setAttribute("aria-label", "Закрыть фото"); x.innerHTML = NT_IC.x; v.appendChild(x); }
  v.onclick = () => imgViewClose();
}
function imgViewClose() { const v = $("#imgview"); if (!v.classList.contains("on")) return false; v.classList.remove("on"); $("img", v).src = ""; return true; }
const saveNotes = (n) => { fileSave("notes.json", JSON.stringify(n)); syncSoon(); if (n.some(x => (x.att || []).some(a => !a.pc))) noteAttSoon(); };
/* Фото и файлы заметок — на свои компьютеры (отзыв 11.10). Тем же зашифрованным каналом, что ключ умного дома: файл
   шифруется своим ключом и кладётся в облако (/close/file себе), ключ к нему — в конверте /close/self {natt}, который
   откроют только мои устройства (core/close.py _natt_add: к той же заметке, когда она придёт синхронизацией). Отправленное
   помечается a.pc (время; -1 — не отправить вовсе); нет связи или других устройств — попробуем при следующей проверке. */
var nattBusy = false, nattT = 0;               // var: saveNotes может позвать до этой строки
function noteAttSoon(ms) { clearTimeout(nattT); nattT = setTimeout(() => noteAttShare().catch(e => plog("info", "вложения заметок на компьютер: " + e.message)), ms || 4000); }
async function noteAttShare() {
  if (nattBusy || SANDBOX || !syncCred() || !DC()) return 0;
  const todo = notes().filter(n => (n.att || []).some(a => !a.pc)); if (!todo.length) return 0;
  nattBusy = true;
  try {
    const k = clKeys(); if (!clLoad().me.pid || Date.now() - (CLS.hello || 0) > 600000) await clHello();
    const t = {}; ((CLS.me || {}).devs || []).forEach(d => { if (d.pub && d.dev && d.dev !== k.dev) t[d.dev] = DC().b64d(d.pub); });
    if (!Object.keys(t).length || !CLS.me.pid) return 0;              // других своих устройств пока нет
    t[k.dev] = DC().b64d(k.pub);
    let sent = 0;
    for (const n of todo.slice(0, 3)) {                                // не больше трёх заметок за раз: у облака лимит конвертов в час
      const files = [], mark = {};
      for (const a of n.att.filter(a => !a.pc)) {
        const m = /^data:([^;,]*)(?:;[^;,=]+=[^;,]*)*(;base64)?,(.*)$/s.exec(noteAttGet(a.id));
        const bin = !m ? null : m[2] ? Uint8Array.from(atob(m[3]), c => c.charCodeAt(0)) : new TextEncoder().encode(decodeURIComponent(m[3]));
        if (!bin || !bin.length || bin.length > 10 * 1024 * 1024) { mark[a.id] = -1; continue; }
        const fk = DC().randomBytes(32);
        const d = await clReq("POST", "/close/file", clStdB64(DC().seal(fk, bin)), "&b64=1&to=" + encodeURIComponent(CLS.me.pid));
        files.push({ id: d.id, key: DC().b64e(fk), name: a.name, type: (m && m[1]) || a.type || "", size: bin.length, aid: a.id });
      }
      if (files.length) await clReq("POST", "/close/self", { env: DC().encryptFor({ natt: { note: n.id, title: n.title, files }, ts: Date.now() }, DC().b64d(k.priv), k.dev, t) });
      files.forEach(f => { mark[f.aid] = Date.now(); }); sent += files.length;
      const all = notes(), x = all.find(y => y.id === n.id);
      if (x) { (x.att || []).forEach(a => { if (mark[a.id]) a.pc = mark[a.id]; }); fileSave("notes.json", JSON.stringify(all)); }
    }
    if (sent) plog("info", `📎 вложения заметок — на свои компьютеры: ${sent}`);
    if (todo.length > 3) noteAttSoon(60000);
    return sent;
  } finally { nattBusy = false; }
}
const money = () => { try { return JSON.parse(fileGet("money.json") || "[]"); } catch (e) { return []; } };
const saveMoney = (m) => { fileSave("money.json", JSON.stringify(m)); syncSoon(); };
function periodStart(p) { const d = new Date(); d.setHours(0, 0, 0, 0);
  if (p === "week") d.setDate(d.getDate() - (d.getDay() + 6) % 7); else if (p === "month") d.setDate(1); else if (p === "year") { d.setMonth(0, 1); }
  return isoLocal(d).slice(0, 10); }
/* «Мой месяц с Лирой» (0.61, как core/month.py): «как прошёл мой месяц?», «итоги октября» — дела и деньги месяца, модель рассказывает тепло */
const MONTHS_NOM = ["январь", "февраль", "март", "апрель", "май", "июнь", "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь"];
/* данные месяца: ym — «2026-10» -> { y, mo, ym, title, done: {n, days, streak, best, by: [по дням], top}, money: {cur, exp, inc, cats: [[имя, сумма]]}, empty } */
function monthData(y, mo) {
  const a = new Date(y, mo, 1).getTime(), b = new Date(y, mo + 1, 1).getTime(), ym = `${y}-${pad(mo + 1)}`, nd = new Date(y, mo + 1, 0).getDate();
  const done = doneList().filter(x => x.at >= a && x.at < b).sort((p, q) => p.at - q.at), by = Array(nd).fill(0);
  done.forEach(x => { by[new Date(x.at).getDate() - 1]++; });
  let streak = 0, run = 0; by.forEach(n => { run = n ? run + 1 : 0; streak = Math.max(streak, run); });
  const bi = by.indexOf(Math.max(...by));
  const mm = money().filter(x => String(x.date || "").slice(0, 7) === ym), cur = {};
  mm.forEach(x => { const c = cur[x.currency] = cur[x.currency] || { inc: 0, exp: 0, cats: {} }; if (x.kind === "income") c.inc += x.amount; else { c.exp += x.amount; c.cats[x.category || "без категории"] = (c.cats[x.category || "без категории"] || 0) + x.amount; } });
  const main = Object.entries(cur).sort((p, q) => q[1].exp - p[1].exp)[0];
  return { y, mo, ym, title: MONTHS_NOM[mo], done: { n: done.length, days: by.filter(Boolean).length, streak, best: done.length ? [bi + 1, by[bi]] : null, by, top: done.slice(-5).map(x => x.title) },
    money: main ? { cur: main[0], exp: main[1].exp, inc: main[1].inc, cats: monCats(main[1].cats) } : null, all: cur,
    empty: !done.length && !mm.length };
}
function monthSummary(m) {
  const now = new Date(); let y = now.getFullYear(), mo = now.getMonth();
  m = String(m || "").trim();
  if (/^(prev|last|прошлый)$/i.test(m)) { mo--; if (mo < 0) { mo = 11; y--; } }
  else if (/^\d{4}-\d{2}$/.test(m)) { y = +m.slice(0, 4); mo = +m.slice(5) - 1; }
  else if (m && !/^(this|текущий|этот)$/i.test(m)) return "Ошибка: месяц — в виде 2026-10, или prev — прошлый.";
  const d = monthData(y, mo), dn = d.done;
  const L = [`[Мой месяц с Лирой — ${d.title} ${y}]`];
  if (dn.n) L.push(`Сделано дел: ${dn.n} (дней с делами — ${dn.days}, лучшая серия — ${dn.streak} дн. подряд, лучший день — ${dn.best[0]}-е: ${dn.best[1]}). Последние: ` + dn.top.map(t => `«${t}»`).join("; ") + ".");
  Object.entries(d.all).forEach(([c, v]) => L.push(`Деньги (${c}): расходы ${+v.exp.toFixed(2)}, доходы ${+v.inc.toFixed(2)}; больше всего — ` + Object.entries(v.cats).sort((p, q) => q[1] - p[1]).slice(0, 3).map(([k, s]) => `${k} ${+s.toFixed(2)}`).join(", ") + "."));
  if (L.length === 1) return L[0] + " Записей за этот месяц почти нет: дел и трат не было. Скажи об этом мягко и предложи отмечать сделанное («я позвонил в банк»).";
  return L.join("\n") + "\n\nРасскажи пользователю его месяц тепло и живо, своими словами, 4–6 предложений: главное число дел и чем он может гордиться (назови одно-два дела), куда ушли деньги (одной фразой, без нравоучений). В конце — одно доброе пожелание на следующий месяц. Без списков и без цифр подряд.";
}
/* Куда ушли деньги: четыре самые большие категории, остальные — одной строкой «Остальное», чтобы сумма строк сходилась
   с «потрачено» (отчёт №405, 29.10: «верх правильный, низ не добавлено» — показывались только три категории). */
function monCats(cats) {
  const all = Object.entries(cats).sort((p, q) => q[1] - p[1]);
  if (all.length <= 5) return all;
  return all.slice(0, 4).concat([["Остальное", all.slice(4).reduce((a, c) => a + c[1], 0), "rest"]]);
}
/* «Мой месяц» карточкой (0.61): «Всё» → «Мой месяц» — числа, календарь (гуще — больше дел), чем гордиться, куда ушли деньги */
let MON_AT = null;
const MON_N = (n, a, b, c) => { const x = n % 10, y = n % 100; return x === 1 && y !== 11 ? a : x >= 2 && x <= 4 && (y < 12 || y > 14) ? b : c; };
function monthHtml(d) {
  const dn = d.done, m = d.money, max = Math.max(1, ...dn.by), first = (new Date(d.y, d.mo, 1).getDay() + 6) % 7;
  const st = [];
  st.push([dn.n, MON_N(dn.n, "дело сделано", "дела сделано", "дел сделано"), dn.streak > 1 ? `серия — ${dn.streak} ${MON_N(dn.streak, "день", "дня", "дней")} подряд` : ""]);
  if (m && m.exp) st.push([Math.round(m.exp).toLocaleString("ru-RU"), `${esc(m.cur)} потрачено`, m.inc ? `пришло ${Math.round(m.inc).toLocaleString("ru-RU")}` : ""]);
  const tot = m ? m.cats.reduce((a, c) => a + c[1], 0) || 1 : 1, now = new Date(), isNow = d.y === now.getFullYear() && d.mo === now.getMonth();
  return `<div class="mon-nav"><button class="ib soft" id="mon-prev" aria-label="Прошлый месяц"><svg viewBox="0 0 24 24"><path d="m15 5-7 7 7 7"/></svg></button>
      <b>${d.title[0].toUpperCase() + d.title.slice(1)} ${d.y}</b><button class="ib soft" id="mon-next" aria-label="Следующий месяц" ${isNow ? "disabled" : ""}><svg viewBox="0 0 24 24"><path d="m9 5 7 7-7 7"/></svg></button></div>
    ${d.empty ? `<div class="card"><p class="hint" style="margin:0">За ${d.title} записей нет. Говорите Лире «я позвонил в банк», «потратил 300 на продукты» — и здесь соберётся ваш месяц.</p></div>` : `
    <div class="mon-sts">${st.map(([v, l, s]) => `<div><b>${v}</b><span>${l}</span>${s ? `<small>${esc(s)}</small>` : ""}</div>`).join("")}</div>
    <h3>Дела по дням</h3><div class="mon-cal" role="img" aria-label="Дела по дням: дней с делами — ${dn.days}">${["пн", "вт", "ср", "чт", "пт", "сб", "вс"].map(w => `<u>${w}</u>`).join("")}${"<b></b>".repeat(first)}${dn.by.map((n, i) => `<i class="lv${n ? Math.min(4, 1 + Math.floor(n / max * 3.999)) : 0}">${i + 1}</i>`).join("")}</div>
    ${dn.top.length ? `<h3>Чем можно гордиться</h3><ul class="mon-top">${dn.top.slice(-3).reverse().map(t => `<li>${esc(t)}</li>`).join("")}</ul>` : ""}
    ${m && m.cats.length ? `<h3>Куда ушли деньги</h3><div class="mon-bar">${m.cats.map((c, i) => `<i class="${c[2] ? "co" : "c" + i}" style="flex:${c[1] / tot}"></i>`).join("")}</div><ul class="mon-cats">${m.cats.map((c, i) => `<li><i class="${c[2] ? "co" : "c" + i}"></i>${esc(c[0])}<b>${Math.round(c[1]).toLocaleString("ru-RU")}</b></li>`).join("")}</ul>` : ""}
    <button class="btn p w" id="mon-say">Рассказать голосом</button>`}`;
}
function openMonth(ym) {
  if (!$("#sh-month")) { const s = document.createElement("section"); s.className = "sheet tall"; s.id = "sh-month"; s.setAttribute("aria-labelledby", "mon-h");
    s.innerHTML = `<div class="grab"></div><h2 id="mon-h">Мой месяц с Лирой</h2><div id="mon-body"></div>`; document.body.appendChild(s); }
  const now = new Date(); MON_AT = MON_AT && ym !== "now" ? MON_AT : [now.getFullYear(), now.getMonth()];
  const d = monthData(MON_AT[0], MON_AT[1]);
  $("#mon-body").innerHTML = monthHtml(d); openSheet("#sh-month");
  const go = (k) => { let [y, mo] = MON_AT; mo += k; if (mo < 0) { mo = 11; y--; } if (mo > 11) { mo = 0; y++; } MON_AT = [y, mo]; openMonth(); };
  $("#mon-prev").onclick = () => go(-1); $("#mon-next").onclick = () => go(1);
  if ($("#mon-say")) $("#mon-say").onclick = () => { closeSheets(); ask(`Как прошёл мой ${d.title} ${d.y}?`); };
}
function moneyLine(x) { return `${String(x.date).slice(8, 10)}.${String(x.date).slice(5, 7)} ${x.kind === "income" ? "+" : "−"}${x.amount} ${x.currency} ${x.note || x.category || ""}`.trim(); }
function moneyReport(p) {
  const from = periodStart(p), items = money().filter(x => x.date >= from), by = {};
  items.forEach(x => { const c = by[x.currency] = by[x.currency] || { inc: 0, exp: 0, cats: {} }; if (x.kind === "income") c.inc += x.amount; else { c.exp += x.amount; c.cats[x.category] = (c.cats[x.category] || 0) + x.amount; } });
  const name = { today: "сегодня", week: "за неделю", month: "за месяц", year: "за год" }[p] || "";
  const parts = Object.entries(by).map(([cur, c]) => `${cur}: доходы ${+c.inc.toFixed(2)}, расходы ${+c.exp.toFixed(2)}, остаток ${+(c.inc - c.exp).toFixed(2)}` +
    (Object.keys(c.cats).length ? "; по категориям: " + Object.entries(c.cats).sort((a, b) => b[1] - a[1]).map(([k, v]) => `${k} ${+v.toFixed(2)}`).join(", ") : ""));
  return { text: parts.length ? `Деньги ${name}. ` + parts.join(". ") : `Записей ${name} нет.`, by, items };
}

/* ---------- умный дом Яндекса (тот же дом, что у Алисы) ----------
   API api.iot.yandex.net с ключом OAuth (права iot:view, iot:control) из S.home.token. Простые команды («включи свет
   в спальне») — без модели (homeQuick), остальное — инструментом smart_home. */
const IOT = "https://api.iot.yandex.net/v1.0";
let homeInfo = null, homeT = 0;                    // список устройств и комнат — кэш на 2 минуты
async function homeReq(method, path, body) {
  const r = await http(method, IOT + path, { headers: { Authorization: "Bearer " + S.home.token, "Content-Type": "application/json" }, body, timeout: 12000 });
  if (r.status === 401) throw new Error("ключ умного дома больше не действует — подключите заново");
  if (r.status === 403) throw new Error("у ключа нет прав iot:view и iot:control");
  const d = JSON.parse(r.body || "{}"); if (d.status && d.status !== "ok") throw new Error(d.message || "умный дом ответил ошибкой"); return d;
}
async function homeYandex() {
  const d = await homeReq("GET", "/user/info"), rooms = {};
  (d.rooms || []).forEach(r => rooms[r.id] = r.name);
  return { rooms: d.rooms || [], scenarios: d.scenarios || [], devices: (d.devices || []).map(x => Object.assign(x, { room_name: rooms[x.room] || "" })) };
}
/* Оба дома как один (Яндекс и Home Assistant): не ответил один — работаем с другим; не ответили оба — ошибка первого. */
async function homeGet(force) {
  if (!force && homeInfo && Date.now() - homeT < 120000) return homeInfo;
  const out = { rooms: [], scenarios: [], devices: [] }; let err = null, got = 0;
  const add = (h) => { out.rooms.push(...h.rooms); out.scenarios.push(...h.scenarios); out.devices.push(...h.devices); got++; };
  if (S.home.token) { try { add(await homeYandex()); } catch (e) { err = e; } }
  if (haOn()) { try { add(await haInfo()); } catch (e) { err = err || e; } }
  if (!got && err) throw err;
  if (err) plog("info", "умный дом: " + err.message);
  homeInfo = out; homeT = Date.now();
  return homeInfo;
}
const HTYPES = { "свет": "devices.types.light", "ламп": "devices.types.light", "люстр": "devices.types.light", "торшер": "devices.types.light", "светильник": "devices.types.light",
  "ночник": "devices.types.light", "подсветк": "devices.types.light", "розетк": "devices.types.socket", "кондиционер": "devices.types.thermostat.ac", "обогреват": "devices.types.thermostat",
  "чайник": "devices.types.cooking.kettle", "пылесос": "devices.types.vacuum_cleaner", "телевизор": "devices.types.media_device.tv", "штор": "devices.types.openable.curtain",
  "увлажнител": "devices.types.humidifier", "вентилятор": "devices.types.fan" };
const HSKIP = new Set(["в", "во", "на", "мне", "пожалуйста", "у", "с", "и", "весь", "все", "всё", "везде", "всех", "сделай", "поставь"]);
const HGEN = new Set(["свет", "света", "устройства", "лампы", "лампочки"]);
const hw = (s) => String(s || "").toLowerCase().replace(/ё/g, "е").match(/[a-zа-я0-9]+/g) || [];
function hsim(a, b) { if (a === b) return true; if (a.length < 4 || b.length < 4) return false; let n = 0; while (n < Math.min(a.length, b.length) && a[n] === b[n]) n++; return n >= 4 && n >= Math.min(a.length, b.length) - 2; }
/* Устройства по словам: сначала по названию (в названной комнате, если она есть), потом по типу («свет», «розетка»),
   потом «весь …» — всё в комнате. hsim — то же слово в другом падеже. -> [] — не нашли (быстрая команда уступит модели). */
function homeMatch(target, info) {
  const all = hw(target), words = all.filter(w => !HSKIP.has(w)), allw = all.some(w => /^(весь|все|всё|везде|всех)$/.test(w));
  const rooms = info.rooms.filter(r => hw(r.name).some(a => words.some(b => hsim(a, b)))), rid = new Set(rooms.map(r => r.id));
  const rw = new Set(words.filter(b => rooms.some(r => hw(r.name).some(a => hsim(a, b))))), rest = words.filter(w => !rw.has(w));
  const inRoom = (d) => !rid.size || rid.has(d.room);
  const sc = info.devices.map(d => [hw(d.name).reduce((s, a) => s + rest.filter(b => !HGEN.has(b) && hsim(a, b)).length, 0), d]).filter(([s, d]) => s && inRoom(d));
  if (sc.length) { const top = Math.max(...sc.map(x => x[0])); return sc.filter(x => x[0] === top).map(x => x[1]); }
  const k = Object.keys(HTYPES).find(k => rest.some(w => w.startsWith(k)));
  if (k) return info.devices.filter(d => String(d.type).startsWith(HTYPES[k]) && inRoom(d));
  if (allw && rid.size) return info.devices.filter(d => rid.has(d.room));
  return [];
}
async function homeAct(devs, op, value) {
  const cap = (d, t, inst) => (d.capabilities || []).find(c => c.type === t && (!inst || ((c.parameters || {}).instance === inst) || ((c.state || {}).instance === inst)));
  const acts = [];
  devs.filter(d => d.src !== "ha").forEach(d => {
    const a = [], ON = "devices.capabilities.on_off", RG = "devices.capabilities.range";
    if (op === "on" || op === "off") { if (cap(d, ON)) a.push({ type: ON, state: { instance: "on", value: op === "on" } }); }
    else if (["brightness", "brighter", "dimmer"].includes(op)) { const c = cap(d, RG, "brightness"); if (c) { const cur = (c.state || {}).value || 50;
      a.push({ type: RG, state: { instance: "brightness", value: Math.max(1, Math.min(100, Math.round(op === "brightness" ? value : cur + (op === "brighter" ? 25 : -25)))) } }); if (cap(d, ON)) a.push({ type: ON, state: { instance: "on", value: true } }); } }
    else if (op === "temperature") { if (cap(d, RG, "temperature")) { a.push({ type: RG, state: { instance: "temperature", value: Math.round(value) } }); if (cap(d, ON)) a.push({ type: ON, state: { instance: "on", value: true } }); } }
    if (a.length) acts.push({ id: d.id, actions: a });
  });
  const ha = devs.filter(d => d.src === "ha"), nha = ha.length ? await haAct(ha, op, value) : 0;   // Home Assistant — своими службами
  if (!acts.length && !nha) throw new Error("эти устройства так не умеют");
  if (acts.length) await homeReq("POST", "/devices/actions", { devices: acts });
  homeT = 0; return acts.length + nha;
}
/* Датчики (отчёт №362, 27.10: «не может сказать температуру в спальне»): показания — в properties устройства. */
const HPROPS = { temperature: ["температура", "°"], humidity: ["влажность", "%"], co2_level: ["углекислый газ", " ppm"], pressure: ["давление", " мм рт. ст."],
  illumination: ["освещённость", " лк"], "pm2.5_density": ["пыль PM2.5", " мкг/м³"], battery_level: ["заряд", "%"], power: ["мощность", " Вт"] };
const HUNITS = { "unit.pressure.pascal": " Па", "unit.pressure.atm": " атм", "unit.pressure.bar": " бар", "unit.temperature.kelvin": " K" };
const hprops = (d) => (d.properties || []).filter(p => p.type === "devices.properties.float" && p.state && p.state.value != null)
  .map(p => ({ i: p.state.instance || (p.parameters || {}).instance, v: p.state.value, u: (p.parameters || {}).unit || "", t: p.last_updated }));
function hval(p, named) { const [n, u] = HPROPS[p.i] || [p.i, ""]; const r = Math.round(Number(p.v) * 10) / 10;
  const hu = p.u && !p.u.startsWith("unit.") ? (/^°[CС]$/.test(p.u) ? "°" : p.u === "%" ? "%" : " " + p.u) : "";   // единицы Home Assistant — как есть
  return (named ? n + " " : "") + String(r).replace(".", ",") + (HUNITS[p.u] || hu || u); }
/* Показания в комнате (или у устройства с таким названием): сначала датчики, по одному на вид. -> { found, vals } */
function homeRead(target, what, info) {
  const words = hw(target).filter(w => !HSKIP.has(w));
  const rid = new Set(info.rooms.filter(r => hw(r.name).some(a => words.some(b => hsim(a, b)))).map(r => r.id));
  const devs = info.devices.filter(d => hprops(d).length && (rid.size ? rid.has(d.room) : hw(d.name).some(a => words.some(b => hsim(a, b)))))
    .sort((a, b) => (String(b.type).startsWith("devices.types.sensor") ? 1 : 0) - (String(a.type).startsWith("devices.types.sensor") ? 1 : 0));
  const seen = new Set(), vals = [];
  devs.forEach(d => hprops(d).forEach(p => { if ((!what || p.i === what) && !seen.has(p.i)) { seen.add(p.i); vals.push(p); } }));
  return { found: rid.size > 0 || devs.length > 0, vals };
}
const HASK = "(температур[а-я]*|градус[а-я]*|влажност[а-я]*|углекисл[а-я]*(?: газ[а-я]*)?|co2|давлени[а-я]*)";
const HQ = "(?:а )?(?:какая |какой |какое |сколько |скажи |подскажи |узнай |проверь )?(?:сейчас )?(?:уровень )?";
function homeAsk(w) { return /^температур|^градус/.test(w) ? "temperature" : /^влажн/.test(w) ? "humidity" : /^углекисл|^co2/.test(w) ? "co2_level" : "pressure"; }
function homeParse(t) {
  let m;
  t = t.replace(/[?!.,]/g, " ").replace(/\s+/g, " ").trim();
  if ((m = t.match(new RegExp("^" + HQ + HASK + " (?:сейчас )?(?:воздуха )?((?:в|во|на|у) .+?)(?: сейчас)?$")))) return { op: "read", target: m[2], what: homeAsk(m[1]) };
  if ((m = t.match(new RegExp("^" + HQ + "((?:в|во|на|у) .+?) (?:сейчас )?(?:какая |какой |какое |сколько )?(?:уровень )?" + HASK + "(?: воздуха)?(?: сейчас)?$")))) return { op: "read", target: m[1], what: homeAsk(m[2]) };
  if ((m = t.match(/^(?:запусти|включи|активируй) сценари[йя] (.+)$/))) return { op: "scenario", target: m[1] };
  if ((m = t.match(/^(?:сделай )?(.+?) (?:на|в) (\d+|[а-я ]+?) ?(?:%|процент[а-яё]*)$/)) && wordsNum(m[2]) != null && !/громк|звук/.test(m[1])) return { op: "brightness", target: m[1], value: wordsNum(m[2]) };
  if ((m = t.match(/^(?:поставь )?(.*(?:кондиционер|обогреват|термостат)[а-яё]*.*?) (?:на )?(\d+|[а-я ]+?)(?: градус[а-яё]*)?$/)) && wordsNum(m[2]) >= 10 && wordsNum(m[2]) <= 35) return { op: "temperature", target: m[1], value: wordsNum(m[2]) };
  if ((m = t.match(/^(?:сделай )?(.*?) ?(ярче|поярче|темнее|потемнее|приглуши) ?(.*)$/)) && /свет|ламп|люстр|торшер/.test(t)) return { op: /ярче/.test(m[2]) ? "brighter" : "dimmer", target: (m[1] + " " + m[3]).trim() || "свет" };
  if ((m = t.match(/^(?:включи|зажги|открой|подними) (.+)$/))) return { op: "on", target: m[1] };
  if ((m = t.match(/^(?:выключи|отключи|погаси|потуши|закрой|опусти) (.+)$/))) return { op: "off", target: m[1] };
  return null;
}
async function homeQuick(t) {
  const c = homeParse(t); if (!c) return null;
  let info; try { info = await homeGet(); } catch (e) { return null; }
  try {
    if (c.op === "scenario") { const s = info.scenarios.find(s => hw(s.name).some(a => hw(c.target).some(b => hsim(a, b)))); if (!s) return null;
      if (s.src === "ha") await haScenario(s); else await homeReq("POST", `/scenarios/${s.id}/actions`, {}); return { say: `Запустил сценарий «${s.name}».` }; }
    if (c.op === "read") {
      const r = homeRead(c.target, c.what, info); if (!r.found) return null;     // «температура в Москве» — это погода, не дом
      const place = c.target[0].toUpperCase() + c.target.slice(1);
      if (!r.vals.length) return { say: `${place} нет датчика, который знает ${c.what === "temperature" ? "температуру" : (HPROPS[c.what] || ["это"])[0]}, — в умном доме я его не вижу.` };
      const v = r.vals[0], old = v.t && Date.now() / 1000 - v.t > 3 * 3600;
      return { say: `${place} ${hval(v, c.what !== "temperature")}.` + (old ? ` Это данные от ${new Date(v.t * 1000).toLocaleString("ru", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })} — датчик давно не присылал новых.` : "") };
    }
    const devs = homeMatch(c.target, info); if (!devs.length) return null;
    await homeAct(devs, c.op, c.value);
    const what = devs.length === 1 ? devs[0].name : devs.every(d => String(d.type).startsWith("devices.types.light")) ? "свет" : `${devs.length} устройства`;
    const verb = { on: "Включил", off: "Выключил", brighter: "Сделал ярче", dimmer: "Приглушил" }[c.op];
    return { say: c.op === "brightness" ? `${what[0].toUpperCase() + what.slice(1)} — ${c.value}%.` : c.op === "temperature" ? `${what} — ${c.value}°.` : `${verb}: ${what}.` };
  } catch (e) { return { say: "Умный дом: " + e.message }; }
}
async function homeTool(a) {
  const info = await homeGet();
  if (a.action === "list") return info.devices.map(d => `${d.name}${d.room_name ? " (" + d.room_name + ")" : ""}${hprops(d).length ? " — " + hprops(d).map(p => hval(p, true)).join(", ") : ""}`).join("; ") + (info.scenarios.length ? ". Сценарии: " + info.scenarios.map(s => s.name).join(", ") : "");
  if (a.action === "scenario") { const s = info.scenarios.find(s => hw(s.name).some(x => hw(a.target).some(y => hsim(x, y)))); if (!s) return "Нет такого сценария."; if (s.src === "ha") await haScenario(s); else await homeReq("POST", `/scenarios/${s.id}/actions`, {}); return `Запущен «${s.name}».`; }
  const devs = homeMatch(a.target || "", info); if (!devs.length) return "Не нашёл такого устройства. Есть: " + info.devices.map(d => d.name).join(", ");
  const n = await homeAct(devs, a.action, a.value); return `Готово: ${devs.map(d => d.name).join(", ")} (${n}).`;
}

/* ---------- Home Assistant на телефоне (28.10, как core/homeassistant.py) ----------
   Второй умный дом рядом с Яндексом: адрес HA и долгосрочный токен (S.ha {url, token, at}). Сущности HA приводятся к виду
   устройств Яндекса (haInfo: type, capabilities on_off/range, properties — показания датчиков; id «ha:<entity_id>»,
   src "ha"), комнаты — области HA (POST /api/template), сценарии — scene.* и script.*. Поэтому разбор фраз, поиск
   устройств и показаний (homeParse, homeMatch, homeRead) — общие; homeGet сливает оба дома, homeAct и запуск сценария
   отправляют каждое устройство в свой дом. Адрес в своей сети (192.168.…, *.local) — напрямую (D.http без прокси Dewiar).
   Токен — только в телефоне и своим устройствам конвертом (ownShare, сквозное шифрование), в отчётах — «***». */
const HA_TYPE = { light: "devices.types.light", switch: "devices.types.switch", input_boolean: "devices.types.switch", fan: "devices.types.fan",
  climate: "devices.types.thermostat", cover: "devices.types.openable", media_player: "devices.types.media_device", vacuum: "devices.types.vacuum_cleaner",
  humidifier: "devices.types.humidifier" };
const HA_PROP = { temperature: "temperature", humidity: "humidity", carbon_dioxide: "co2_level", pressure: "pressure", atmospheric_pressure: "pressure",
  illuminance: "illumination", battery: "battery_level", power: "power", pm25: "pm2.5_density" };
const haOn = () => !!(S.ha && S.ha.url && S.ha.token);
function haUrl(u) {                                 // «192.168.1.20» → «http://192.168.1.20:8123»; https и свой порт — как есть
  u = String(u || "").trim().replace(/\/+$/, "").replace(/\/api$/, "");
  if (!u) throw new Error("впишите адрес Home Assistant");
  if (!/^https?:\/\//i.test(u)) u = "http://" + u;
  const m = u.match(/^(https?:\/\/)([^/:]+)(:\d+)?(.*)$/i);
  if (m && !m[3] && /^http:/i.test(m[1]) && (/^\d+\.\d+\.\d+\.\d+$/.test(m[2]) || /\.local$/i.test(m[2]) || !m[2].includes("."))) u = m[1] + m[2] + ":8123" + m[4];
  return u;
}
async function haReq(method, path, body) {
  const r = await http(method, S.ha.url + path, { headers: { Authorization: "Bearer " + S.ha.token, "Content-Type": "application/json" }, body, timeout: 12000 });
  if (r.status === 401 || r.status === 403) throw new Error("Home Assistant не принял токен — создайте новый (профиль → «Безопасность» → «Долгосрочные токены доступа»)");
  if (!r.status) throw new Error("до Home Assistant не достучаться — телефон в той же сети, что и дом?");
  if (r.status >= 400) throw new Error("Home Assistant ответил ошибкой " + r.status);
  return r.body;
}
async function haInfo() {
  const states = JSON.parse(await haReq("GET", "/api/states") || "[]"), area = {}, rooms = [];
  try {        // области: «id|название|сущность,сущность» по строке
    const t = await haReq("POST", "/api/template", { template: "{% for a in areas() %}{{ a }}|{{ area_name(a) }}|{{ area_entities(a) | join(',') }}\n{% endfor %}" });
    String(t || "").split("\n").forEach(l => { const [id, name, ents] = l.split("|"); if (!id || !name) return; rooms.push({ id: "ha:" + id, name: name.trim() }); (ents || "").split(",").filter(Boolean).forEach(e => area[e.trim()] = "ha:" + id); });
  } catch (e) { plog("info", "Home Assistant: комнаты не прочитались — " + e.message); }
  const rname = Object.fromEntries(rooms.map(r => [r.id, r.name])), devices = [], scenarios = [];
  for (const s of states) {
    const [dom] = String(s.entity_id || "").split("."), a = s.attributes || {}, name = a.friendly_name || s.entity_id, room = area[s.entity_id] || "";
    if (dom === "scene" || dom === "script") { scenarios.push({ id: "ha:" + s.entity_id, name, src: "ha" }); continue; }
    const base = { id: "ha:" + s.entity_id, src: "ha", ent: s.entity_id, dom, name, room, room_name: rname[room] || "", capabilities: [], properties: [] };
    if (HA_TYPE[dom]) {
      const d = Object.assign(base, { type: HA_TYPE[dom] + (dom === "climate" && /cool/.test((a.hvac_modes || []).join(" ")) ? ".ac" : "") });
      d.capabilities.push({ type: "devices.capabilities.on_off", state: { instance: "on", value: !["off", "closed", "unavailable", "idle", "standby"].includes(s.state) } });
      if (dom === "light" && (a.supported_color_modes || []).some(m => m !== "onoff"))
        d.capabilities.push({ type: "devices.capabilities.range", parameters: { instance: "brightness" }, state: { instance: "brightness", value: a.brightness != null ? Math.round(a.brightness / 2.55) : null } });
      if (dom === "climate") {
        d.capabilities.push({ type: "devices.capabilities.range", parameters: { instance: "temperature" }, state: { instance: "temperature", value: a.temperature } });
        if (a.current_temperature != null) d.properties.push({ type: "devices.properties.float", parameters: { instance: "temperature", unit: a.temperature_unit || "°C" }, state: { instance: "temperature", value: +a.current_temperature } });
      }
      devices.push(d);
    } else if (dom === "sensor" && HA_PROP[a.device_class] && s.state !== "" && !isNaN(parseFloat(s.state))) {
      devices.push(Object.assign(base, { type: "devices.types.sensor", properties: [{ type: "devices.properties.float", parameters: { instance: HA_PROP[a.device_class], unit: a.unit_of_measurement || "" },
        state: { instance: HA_PROP[a.device_class], value: parseFloat(s.state) }, last_updated: s.last_updated ? Date.parse(s.last_updated) / 1000 : 0 }] }));
    }
  }
  return { rooms, scenarios, devices };
}
async function haAct(devs, op, value) {
  let n = 0;
  for (const d of devs) {
    let svc = null, data = { entity_id: d.ent };
    if (op === "on" || op === "off") svc = d.dom === "cover" ? (op === "on" ? "cover/open_cover" : "cover/close_cover") : `${d.dom === "vacuum" ? "vacuum" : d.dom}/${op === "on" ? (d.dom === "vacuum" ? "start" : "turn_on") : (d.dom === "vacuum" ? "return_to_base" : "turn_off")}`;
    else if (op === "brightness" && d.dom === "light") { svc = "light/turn_on"; data.brightness_pct = Math.max(1, Math.min(100, Math.round(value))); }
    else if ((op === "brighter" || op === "dimmer") && d.dom === "light") { svc = "light/turn_on"; data.brightness_step_pct = op === "brighter" ? 25 : -25; }
    else if (op === "temperature" && d.dom === "climate") { svc = "climate/set_temperature"; data.temperature = Math.round(value); }
    if (!svc) continue;
    await haReq("POST", "/api/services/" + svc, data); n++;
  }
  return n;
}
async function haScenario(s) { const [dom] = s.id.slice(3).split("."); await haReq("POST", `/api/services/${dom}/turn_on`, { entity_id: s.id.slice(3) }); }
async function haConnect(url, token) {
  const u = haUrl(url), t = String(token || "").trim();
  if (!/^[\w.-]{20,}$/.test(t)) throw new Error("токен — длинная строка из «Долгосрочных токенов доступа»");
  const r = await http("GET", u + "/api/", { headers: { Authorization: "Bearer " + t }, timeout: 10000 });
  if (r.status === 401 || r.status === 403) throw new Error("Home Assistant не принял токен");
  if (!r.status) throw new Error("до " + u + " не достучаться — телефон в той же сети, что и Home Assistant?");
  if (r.status >= 400) throw new Error("по этому адресу Home Assistant не отвечает (" + r.status + ")");
  S.ha = { url: u, token: t, at: Date.now() }; homeInfo = null; saveS();
  ownShare().catch(e => plog("info", "Home Assistant на свои устройства: " + e.message));
}
function haForget() { S.ha = { url: "", token: "", at: Date.now() }; homeInfo = null; saveS(); ownShare().catch(() => { }); }

