//@ Телефон и веб-версия, часть 10: время словами, «Напоминания вовремя», таймер.
//@ Собирается в android/assets/www/app.js (tools/app_join.py) — порядок частей = порядок исполнения; шапка «//@» в app.js не попадает.
/* ---------- время словами: «через 10 минут», «завтра в 9», «в 18:30», «в пятницу в 15:00», «каждый день в 8» ---------- */
const NUMW = { "ноль": 0, "один": 1, "одну": 1, "одна": 1, "два": 2, "две": 2, "три": 3, "четыре": 4, "пять": 5, "шесть": 6, "семь": 7, "восемь": 8,
  "девять": 9, "десять": 10, "одиннадцать": 11, "двенадцать": 12, "тринадцать": 13, "четырнадцать": 14, "пятнадцать": 15, "шестнадцать": 16,
  "семнадцать": 17, "восемнадцать": 18, "девятнадцать": 19, "двадцать": 20, "тридцать": 30, "сорок": 40, "пятьдесят": 50, "полчаса": 30, "полтора": 1.5, "пару": 2, "пять минут": 5 };
function wordsNum(s) {
  s = String(s || "").trim().toLowerCase().replace(/ё/g, "е");
  if (/^\d+([.,]\d+)?$/.test(s)) return parseFloat(s.replace(",", "."));
  let n = 0, any = false;
  for (const w of s.split(/\s+/)) { if (w in NUMW) { n += NUMW[w]; any = true; } else if (w !== "и") return null; }
  return any ? n : null;
}
const DOW = { "понедельник": 1, "вторник": 2, "сред": 3, "четверг": 4, "пятниц": 5, "суббот": 6, "воскресень": 0 };
/* -> {at: Date, repeat: ""|daily|weekdays|weekly, rel?, rest} или null — времени во фразе нет. rest — фраза без слов о времени
   (из неё берут, о чём напомнить). Только время без дня и оно уже прошло — завтра; день без времени — 9:00. */
/* №350 (20.11): время, как его говорят: «без пяти шесть» (5:55), «без четверти восемь вечера» (19:45), «полшестого» и
   «в половине шестого» (5:30), «в четверть девятого» (8:15), «в 5 минут седьмого» (6:05) — к виду «в 5:55», дальше как
   обычно. Так же на компьютере (core/when.py _clock). «Без 5 рублей» — не время: после «без N» нужен час. */
// слова — одной строкой: это не надписи интерфейса, переводить их не нужно (счёт i18n_ratchet)
const ORDG = Object.fromEntries("первого второго третьего четвертого пятого шестого седьмого восьмого девятого десятого одиннадцатого двенадцатого"
  .split(" ").map((w, i) => [w, i + 1]));
const BEZW = Object.fromEntries("минуты:1 одной:1 двух:2 трех:3 четырех:4 пяти:5 шести:6 семи:7 восьми:8 девяти:9 десяти:10 пятнадцати:15 четверти:15 двадцати:20 тридцати:30 двадцати_пяти:25"
  .split(" ").map(x => x.split(":")).map(([w, n]) => [w.replace("_", " "), +n]));
function colloqTime(t) {
  const hm = (h, mi) => ` в ${h >= 13 ? h : (h || 12)}:${String(mi).padStart(2, "0")} `;
  t = t.replace(/\s(?:в\s+|к\s+)?без\s+(двадцати пяти|\d{1,2}|[а-я]+)(?:\s+минут[а-я]*)?\s+(\d{1,2}|час|[а-я]+)(?=\s)/g, (x, a, b) => {
    const n = /^\d+$/.test(a) ? +a : BEZW[a], h = /^час$/.test(b) ? 1 : /^\d+$/.test(b) ? +b : NUMW[b];
    return n && n < 60 && h && h <= 24 ? hm(h - 1, 60 - n) : x; });
  t = t.replace(/\s(?:в\s+)?(?:половин[еу]\s+|пол-?\s?)([а-я]+ого)(?=\s)/g, (x, o) => ORDG[o] ? hm(ORDG[o] - 1, 30) : x);
  t = t.replace(/\s(?:в\s+)?четверть\s+([а-я]+ого)(?=\s)/g, (x, o) => ORDG[o] ? hm(ORDG[o] - 1, 15) : x);
  return t.replace(/\s(?:в\s+)?(\d{1,2})\s+минут[а-я]*\s+([а-я]+ого)(?=\s)/g, (x, n, o) => ORDG[o] && +n > 0 && +n < 30 ? hm(ORDG[o] - 1, +n) : x);
}
function parseWhen(t, now = new Date(), again = false) {
  t = colloqTime(" " + String(t || "").toLowerCase().replace(/ё/g, "е") + " ");
  let m = t.match(/через\s+(?:(\S+(?:\s+(?:и\s+)?\S+)?)\s+)?(секунд[а-яё]*|минут[а-яё]*|час[а-яё]*|полчаса|полтора часа)/);
  if (m) {
    let n = m[2].startsWith("полчаса") ? 30 : m[2].startsWith("полтора") ? 90 : (m[1] ? wordsNum(m[1]) : 1);
    if (n == null) n = 1;
    const ms = m[2].startsWith("сек") ? n * 1000 : m[2].startsWith("мин") || m[2].startsWith("пол") ? n * 60000 : n * 3600000;
    return { at: new Date(now.getTime() + ms), repeat: "", rel: true, rest: t.replace(m[0], " ") };
  }
  let day = new Date(now), hasDay = false, repeat = "", dowToday = false;
  if (/каждый день|ежедневно|каждое утро|каждый вечер/.test(t)) { repeat = "daily"; hasDay = true; }
  else if (/по будням|в будни/.test(t)) { repeat = "weekdays"; hasDay = true; }
  const wdays = whenDays(t, repeat === "daily" ? [0, 1, 2, 3, 4, 5, 6] : repeat === "weekdays" ? [0, 1, 2, 3, 4] : null, again);
  let dset = null;
  if (wdays) { t = wdays.t; dset = wdays.days; repeat = repNorm(dset); hasDay = true;
    if (repeat === "weekly") { const d = (dset[0] + 1) % 7; day = new Date(now); day.setDate(now.getDate() + ((d - now.getDay() + 7) % 7)); dset = null; } }
  if (/послезавтра/.test(t)) { day.setDate(day.getDate() + 2); hasDay = true; }
  else if (/завтра/.test(t)) { day.setDate(day.getDate() + 1); hasDay = true; }
  for (const [k, v] of Object.entries(DOW)) {
    if (wdays) break;                                   // дни повтора уже из фразы («пн-чт», «кроме пятницы»)
    // «в следующий понедельник», «в ближайшую пятницу», «в эту среду», «на понедельник» (19.11, №897: «в следующий понедельник
    // в 13 часов» вставало на завтра — день со словом между «в» и днём не узнавался); «в пятницу на следующей неделе» — день той недели
    const r = new RegExp("(?:(?:\\sв|\\sво|\\sна|каждый|каждую|каждое|\\sпо)\\s+(?:(?:следующ|ближайш|эт[оуи])[а-я]*\\s+)?|\\s(?:следующ|ближайш)[а-я]*\\s+)" + k);
    // «в пятницу» в пятницу — сегодня, если час ещё впереди, иначе через неделю (как when.py на компьютере; 16.10)
    if (r.test(t)) { const w0 = t.match(r)[0]; let d = (v - now.getDay() + 7) % 7;
      if (/(?:на\s+)?следующей\s+неделе/.test(t)) d = 7 - (now.getDay() + 6) % 7 + (v + 6) % 7;     // понедельник следующей недели + день
      else if (/следующ/.test(w0) && d === 0) d = 7;
      day = new Date(now); day.setDate(now.getDate() + d); hasDay = true; dowToday = d === 0; if (/кажд|\sпо\s/.test(w0)) repeat = "weekly"; break; }
  }
  // дата: «27 октября», «на 27.10», «27.10.2026», «2026-10-27», «27-го» (№231, 24.10: «попросил на 27.10 — создала на завтра»:
  // дат телефон не понимал, «на 27» читал как час, а «в 10» без дня — как завтра). Дату из фразы убираем, чтобы её числа
  // не приняли за время. Без года и уже прошла — в следующем году (месяце); без времени — 9:00, как у дня недели.
  if (!hasDay) {
    const set = (y, mo, d, src, roll) => { const x = new Date(now); x.setFullYear(y, mo, d); if (x.getMonth() !== mo || x.getDate() !== d) return false;
      const t0 = new Date(now.getFullYear(), now.getMonth(), now.getDate());
      if (roll && x < t0) { if (roll === "y") x.setFullYear(y + 1, mo, d); else x.setMonth(mo + 1, d); }
      day = x; hasDay = true; t = t.replace(src, " "); return true; };
    let d;
    if ((d = t.match(/\s(?:на\s+)?(\d{4})-(\d{2})-(\d{2})(?:[t\s]+(\d{1,2}):(\d{2}))?/))) { if (set(+d[1], +d[2] - 1, +d[3], d[0]) && d[4]) t += ` в ${d[4]}:${d[5]} `; }
    else if ((d = t.match(/\s(?:на\s+|к\s+)?(\d{1,2})(?:-?(?:го|е|ое))?\s+(январ|феврал|март|апрел|ма[яй]|июн|июл|август|сентябр|октябр|ноябр|декабр)[а-я]*/)))
      set(now.getFullYear(), ["январ", "феврал", "март", "апрел", "ма", "июн", "июл", "август", "сентябр", "октябр", "ноябр", "декабр"].findIndex(k => d[2].startsWith(k)), +d[1], d[0], "y");
    else if ((d = t.match(LBRX("(?<!\\s[вк])\\s(?:на\\s+)?(\\d{1,2})[./](\\d{1,2})(?:[./](\\d{2,4}))?(?=[\\s,])", ""))) && +d[2] >= 1 && +d[2] <= 12 && +d[1] >= 1 && +d[1] <= 31)
      set(d[3] ? (+d[3] < 100 ? 2000 + +d[3] : +d[3]) : now.getFullYear(), +d[2] - 1, +d[1], d[0], d[3] ? "" : "y");
    else if ((d = t.match(/\s(?:на\s+|к\s+)?(\d{1,2})(?:-?(?:го|е|ое)(?=\s)|\s+числ[а-я]*)/)) && +d[1] >= 1 && +d[1] <= 31)
      set(now.getFullYear(), now.getMonth(), +d[1], d[0], "m");
  }
  m = t.match(/(?:\sв|\sна|\sк)\s+(\d{1,2})(?:[:.\s](\d{2}))?(?:\s*(утра|дня|вечера|ночи))?(?=\s)/) || t.match(/\s(\d{1,2}):(\d{2})\s/);
  let h = null, mi = 0;
  let bare = false;                                    // час без «утра/вечера» и без дня — утро или вечер решает напоминание
  if (m) { h = +m[1]; mi = m[2] ? +m[2] : 0; if (m[3] && /дня|вечера/.test(m[3]) && h < 12) h += 12; if (m[3] === "ночи" && h === 12) h = 0;
    bare = !m[3] && !hasDay && !repeat && h >= 1 && h <= 11 && !/утр|вечер|днем|ночью|\bрано\b|встаю|проснусь/.test(t); }
  else if (/утром|каждое утро/.test(t)) h = 9; else if (/вечером|каждый вечер/.test(t)) h = 20; else if (/днем/.test(t)) h = 13;
  if (h == null && !hasDay) return null;
  if (h == null) h = 9;
  if (h > 23 || mi > 59) return null;
  day.setHours(h, mi, 0, 0);
  if (!hasDay && day <= now) day.setDate(day.getDate() + 1);
  if (dowToday && !repeat && day <= now) day.setDate(day.getDate() + 7);
  if (repeat && day <= now) day.setDate(day.getDate() + (repeat === "weekly" ? 7 : 1));
  if (repeat) day = rollRepeat(day, repeat, now);       // первый раз — в подходящий день («кроме пятницы», сказанное в пятницу)
  return { at: day, repeat, rest: t.replace(m ? m[0] : "", " "), bare };
}
/* Напоминание «в 3» без части суток, когда 3:00 сегодня прошло, а 15:00 нет, — на 15:00, и сказать, как поправить (как на
   компьютере: when.py, guessed; №350: «надо, чтобы предлагала утро или вечер»). Будильник — как сказано. -> подсказка или "" */
function dayHalf(w, now = new Date()) {
  if (!w || !w.bare || w.rel) return "";
  const h = w.at.getHours(), pm = new Date(now); pm.setHours(h + 12, w.at.getMinutes(), 0, 0);
  if (h > 11 || w.at.getDate() === now.getDate() || pm <= now) return "";
  w.at = pm;
  const hm = h + (w.at.getMinutes() ? ":" + pad(w.at.getMinutes()) : "");
  return ` Если нужно в ${hm} утра — поправьте время в карточке.`;
}
const whenText = (d) => { const now = new Date(), tm = `${pad(d.getHours())}:${pad(d.getMinutes())}`;
  const dd = Math.round((new Date(d.getFullYear(), d.getMonth(), d.getDate()) - new Date(now.getFullYear(), now.getMonth(), now.getDate())) / 864e5);
  return dd === 0 ? "сегодня в " + tm : dd === 1 ? "завтра в " + tm : dd === 2 ? "послезавтра в " + tm : `${d.getDate()} ${MON[d.getMonth()]} в ${tm}`; };
/* №563: сколько осталось — часами и минутами: «1 ч 27 мин», а не «87 мин» (как when.span на компьютере) */
const spanRu = (mins) => { const t = Math.max(0, Math.round(mins)), h = Math.floor(t / 60), m = t % 60; return [h ? h + " ч" : "", m || !h ? m + " мин" : ""].filter(Boolean).join(" "); };
const REP_RU = { daily: "каждый день", weekdays: "по будням", weekly: "каждую неделю" };
/* Повтор по дням недели (30.10, владелец: «просил по будням, кроме пятницы» — на компьютере сделано в 0.71, а телефон
   такой повтор не понимал: звонил раз и ждал следующий срок от компьютера). Строка «d:0123» — дни как в Python
   (понедельник = 0): так же хранит Alarms.java и считает следующий раз, даже когда приложение закрыто. */
const DAYRX = "(?:понедельник[а-я]*|вторник[а-я]*|сред[аеуы][а-я]*|четверг[а-я]*|пятниц[а-я]*|суббот[а-я]*|воскресень[а-я]*|пн|вт|ср|чт|пт|сб|вс)";
const DAYP = [["понедельник", 0], ["вторник", 1], ["сред", 2], ["четверг", 3], ["пятниц", 4], ["суббот", 5], ["воскресень", 6]];
const DAYS2 = { "пн": 0, "вт": 1, "ср": 2, "чт": 3, "пт": 4, "сб": 5, "вс": 6 };
const wdN = (w) => { w = String(w || "").trim(); if (w in DAYS2) return DAYS2[w]; const f = DAYP.find(([p]) => w.startsWith(p)); return f ? f[1] : null; };
const daysIn = (s) => [...new Set((String(s).match(new RegExp(DAYRX, "g")) || []).map(wdN).filter(d => d != null))].sort();
/* дни -> строка повтора: все — daily, пн–пт — weekdays, один — weekly, иначе «d:…» */
function repNorm(days) {
  const d = [...new Set(days)].filter(x => x >= 0 && x <= 6).sort();
  if (!d.length) return "";
  if (d.length === 7) return "daily";
  if (d.join("") === "01234") return "weekdays";
  if (d.length === 1) return "weekly";
  return "d:" + d.join("");
}
/* строка повтора -> дни (понедельник = 0); weekly — день самого напоминания */
function repDays(rep, at) {
  if (rep === "daily") return [0, 1, 2, 3, 4, 5, 6];
  if (rep === "weekdays") return [0, 1, 2, 3, 4];
  if (rep === "weekly") return [(new Date(at || Date.now()).getDay() + 6) % 7];
  if (/^d:[0-6]+$/.test(rep || "")) return [...rep.slice(2)].map(Number);
  return [];
}
const DGEN = ["понедельника", "вторника", "среды", "четверга", "пятницы", "субботы", "воскресенья"];
const DACC = ["понедельник", "вторник", "среду", "четверг", "пятницу", "субботу", "воскресенье"];
const DDAT = ["понедельникам", "вторникам", "средам", "четвергам", "пятницам", "субботам", "воскресеньям"];
/* как сказать повтор: «по будням, кроме пятницы», «с понедельника по четверг», «по понедельникам и средам» */
function repRu(rep) {
  if (!rep) return "";
  if (REP_RU[rep]) return REP_RU[rep];
  const d = repDays(rep); if (!d.length) return "";
  const wd = [0, 1, 2, 3, 4], miss = wd.filter(x => !d.includes(x));
  if (d.every(x => x < 5) && d.length === 4) return `по будням, кроме ${DGEN[miss[0]]}`;
  if (d.length === 6) return `каждый день, кроме ${DGEN[[0, 1, 2, 3, 4, 5, 6].find(x => !d.includes(x))]}`;
  if (d.join("") === "56") return "по выходным";
  if (d.length >= 3 && d[d.length - 1] - d[0] === d.length - 1) return `${d[0] === 1 ? "со" : "с"} ${DGEN[d[0]]} по ${DACC[d[d.length - 1]]}`;
  return "по " + d.map(x => DDAT[x]).join(", ").replace(/, ([^,]+)$/, " и $1");
}
/* дни повтора из фразы (как _repeat и _except_days в core/when.py): диапазон «с понедельника по четверг» / «пн-чт»,
   «по выходным», «по понедельникам и средам»; потом «кроме пятницы», «но не в среду». -> {days, t} или null; найденное
   из фразы стёрто, чтобы «в среду» из «но не в среду» не приняли за день срабатывания */
function whenDays(t, base, again) {
  let days = base ? base.slice() : null, m;
  if ((m = t.match(new RegExp("\\s(?:каждую\\s+неделю\\s+)?со?\\s+(" + DAYRX + ")\\s+по\\s+(" + DAYRX + ")(?=[\\s,.])"))) ||
      (m = t.match(new RegExp("\\s(" + DAYRX + ")\\s*[-–—]\\s*(" + DAYRX + ")(?=[\\s,.])")))) {
    const a = wdN(m[1]), b = wdN(m[2]);
    if (a != null && b != null && a !== b) { days = []; for (let i = a; ; i = (i + 1) % 7) { days.push(i); if (i === b) break; } t = t.replace(m[0], " "); }
  } else if ((m = t.match(/\s(?:по\s+выходным|в\s+выходные|каждые\s+выходные)(?=[\s,.])/))) { days = [5, 6]; t = t.replace(m[0], " "); }
  else if ((m = t.match(/\s(?:кажд(?:ый|ую|ое)|по)\s+((?:(?:понедельник|вторник|сред|четверг|пятниц|суббот|воскресень)[а-я]*(?:\s*(?:,|и)\s*)?){2,})/))) {
    const d = daysIn(m[1]); if (d.length >= 2) { days = d; t = t.replace(m[0], " "); }
  }
  if ((m = t.match(new RegExp("(?:,\\s*|\\s)(?:кроме|за\\s+исключением|но\\s+не\\s+(?:в|во|по))\\s+(" + DAYRX + "(?:\\s*(?:,|и)\\s*" + DAYRX + ")*)(?=[\\s,.])")))) {
    const ex = daysIn(m[1]);
    if (ex.length && (days || again || /напоминай|кажд|ежедневно/.test(t))) {
      const left = (days || [0, 1, 2, 3, 4, 5, 6]).filter(d => !ex.includes(d));
      if (left.length) { days = left; t = t.replace(m[0], " "); }
    }
  }
  return days ? { days, t } : null;
}
// повторяющееся напоминание: первый раз — ближайший подходящий момент не раньше «сейчас» (будни — без субботы и воскресенья)
function rollRepeat(at, rep, now = Date.now()) {
  const set = /^d:/.test(rep || "") ? repDays(rep) : null;
  const d = new Date(at), step = rep === "weekly" ? 7 : 1, off = x => (rep === "weekdays" && (x.getDay() === 0 || x.getDay() === 6)) || (set && !set.includes((x.getDay() + 6) % 7));
  for (let i = 0; i < 800 && (d.getTime() < +now || off(d)); i++) d.setDate(d.getDate() + step);
  return d;
}

// что напомнить — из остатка после разбора времени: без «о том, что», «завтра», «в среду», «часов утра»
function remindWhat(rest) {
  return String(rest || "").replace(/^\s*(о том,? что|о том|что|про|о|об)\s+/, "").replace(/(^|\s)(сегодня|послезавтра|завтра|утром|вечером|днем|каждый день|по будням|ежедневно)(?=\s|$)/g, " ")
    .replace(/\s+(?:(?:в|во|по|на|каждый|каждую)(?:\s+(?:следующ|ближайш|эт[оуи])[а-яё]*)?|(?:следующ|ближайш)[а-яё]*)\s+(понедельник|вторник|сред|четверг|пятниц|суббот|воскресень)[а-яё]*/g, " ")
    .replace(/(^|\s)(?:на\s+)?следующей\s+неделе(?=\s|$)/g, " ").replace(/(^|\s)по выходным(?=\s|$)/g, " ")
    .replace(/\s+,/g, ",").replace(/,(\s*,)+/g, ",").replace(/^[\s,]+|[\s,]+$/g, "").replace(/\s+/g, " ").trim()
    .replace(/^(чтобы|что)\s+/, "").replace(/(^|\s)(?:часов|часа|час|утра|вечера|дня|ночи|ровно)(?=\s|$)/g, " ").replace(/\s+/g, " ").trim();
}
/* в «о чём напомнить» остались слова о дне, которые разбор не понял («через неделю в понедельник») — быстрый путь не угадывает
   дату, решает модель (как LEFT_DAY_RX в when.py; №897) */
const LEFT_DAY = /(^|[^а-я])(?:понедельник|вторник|сред[уаы]?(?![а-я])|четверг|пятниц|суббот|воскресень|следующ[а-я]*\s+(?:недел|месяц|год)|на\s+(?:этой|той|следующей)\s+неделе|через\s+(?:неделю|месяц|год)(?![а-я])|(?:после)?завтра(?![а-я])|сегодня(?![а-я])|\d{1,2}\s*(?:январ|феврал|март|апрел|ма[яй]|июн|июл|август|сентябр|октябр|ноябр|декабр))/;
function addAlarm(title, at, kind, repeat, note) {
  if (repeat) at = rollRepeat(at, repeat);              // «будильник по будням в 7», сказанное в 7:20, — с завтрашнего, не сразу
  // who — кто ставил: его лицо и имя будут в уведомлении (Faces.java); note — заметка с фото и файлами напоминания
  // id свой и неповторимый: план дня ставит три дела за одну миллисекунду, а «a» + время у телефона совпадало — дела затирали друг друга
  const x = JSON.parse(D.alarmSet(JSON.stringify(Object.assign({ id: "a" + Date.now() + Math.random().toString(36).slice(2, 6), title, at: at.getTime(), kind: kind || "reminder", repeat: repeat || "", who: S.persona || "", from: Date.now() },
    note ? { note } : {}))) || "{}");
  if (x.kind === "timer") tmrShow();
  if (!D.exactAlarms()) toast("Чтобы будильники звонили минута в минуту, разрешите «Будильники и напоминания» в настройках.", 5000);
  needPerm(NOTIF); syncSoon();
  return x;
}
function alarmCard(x) {
  return `<div class="pill"><span>${x.kind === "alarm" ? "⏰" : x.kind === "timer" ? "⏱" : "🔔"}</span><span><b>${esc(whenText(new Date(x.at)))}</b>${x.repeat ? " · " + repRu(x.repeat) : ""}${x.note ? " · 📎" : ""}<br>${esc(x.title)}</span><button onclick="cancelAlarm('${esc(x.id)}', this)">Отменить</button></div>`;
}
/* Правка напоминания руками (отзыв 17.10: «напоминания можно редактировать только голосом»): текст, дата, время,
   повтор; «Сохранить» — то же напоминание (тот же id) с новым временем, и на компьютер — синхронизацией. */
function remEdit(id) {
  const x = JSON.parse(D.alarms() || "[]").find(a => a.id === id); if (!x) return;
  const d = new Date(+x.at), iso = (v) => `${v.getFullYear()}-${pad(v.getMonth() + 1)}-${pad(v.getDate())}`;
  $("#rm-h").textContent = x.kind === "alarm" ? "Будильник" : x.kind === "timer" ? "Таймер" : "Напоминание";
  // №556 (05.11): «малое поле, мало символов — хочется как в заметках, с пунктами»: поле растёт, до 1000 знаков, «• Пункт»
  $("#rem-body").innerHTML = `<div class="rmhead"><label for="rm-text">Что напомнить</label><div class="ntmd rmmd" role="toolbar" aria-label="Оформление"><button type="button" data-md="li">• Пункт</button></div></div>
    <textarea id="rm-text" class="rmtext" maxlength="1000" rows="3" aria-label="Что напомнить">${esc(x.title || "")}</textarea>
    <div class="rmrow"><label>Дата<input type="date" id="rm-date" value="${iso(d)}"></label><label>Время<input type="time" id="rm-time" value="${pad(d.getHours())}:${pad(d.getMinutes())}"></label></div>
    <label>Повторять<select id="rm-rep">${[["", "не повторять"], ["daily", "каждый день"], ["weekdays", "по будням"], ["weekly", "каждую неделю"], ["d", "по дням недели…"]]
      .map(([v, t]) => `<option value="${v}"${((x.repeat || "").startsWith("d:") ? "d" : x.repeat || "") === v ? " selected" : ""}>${t}</option>`).join("")}</select></label>
    <div class="rmdays" id="rm-days" role="group" aria-label="Дни повтора"${(x.repeat || "").startsWith("d:") ? "" : " hidden"}>${["пн", "вт", "ср", "чт", "пт", "сб", "вс"].map((n, i) =>
      `<button type="button" class="rmd${repDays(x.repeat || "", x.at).includes(i) ? " on" : ""}" data-d="${i}" aria-pressed="${repDays(x.repeat || "", x.at).includes(i)}">${n}</button>`).join("")}</div>
    ${x.note ? `<div class="rmatt"><button class="btn" id="rm-note">📎 Вложения</button></div>` : ""}
    <div class="row2"><button class="btn p" id="rm-save" style="flex:1">Сохранить</button><button class="btn" id="rm-del">Удалить</button></div>
    <div class="res" id="rm-res"></div>`;
  const back = () => { closeSheets(true); openSheet("#sh-day"); renderDay(); };
  remTextWire($("#rm-text"), $(".rmmd button[data-md=li]"));
  // «по дням недели…» (30.10): кнопки дней — как в календаре студии; выбрали «по будням» и т. п. — кнопки прячутся
  $("#rm-rep").onchange = () => { const v = $("#rm-rep").value, box = $("#rm-days"); box.hidden = v !== "d";
    if (v === "d" && !$$("#rm-days .rmd.on").length) { const cur = repDays(x.repeat || "weekdays", x.at); $$("#rm-days .rmd").forEach(b => { const on = cur.includes(+b.dataset.d); b.classList.toggle("on", on); b.setAttribute("aria-pressed", String(on)); }); } };
  $$("#rm-days .rmd").forEach(b => b.onclick = () => { const on = !b.classList.contains("on"); b.classList.toggle("on", on); b.setAttribute("aria-pressed", String(on)); });
  $("#rm-save").onclick = () => {
    const title = $("#rm-text").value.trim(), dv = $("#rm-date").value, tv = $("#rm-time").value;
    let rep = $("#rm-rep").value;
    if (rep === "d") { rep = repNorm($$("#rm-days .rmd.on").map(b => +b.dataset.d));
      if (!rep) { $("#rm-res").className = "res bad"; $("#rm-res").textContent = "Выберите хотя бы один день."; return; } }
    if (!title) { $("#rm-res").className = "res bad"; $("#rm-res").textContent = "Напишите, о чём напомнить."; return; }
    let at = new Date(`${dv}T${tv || "09:00"}`);
    if (isNaN(at)) { $("#rm-res").className = "res bad"; $("#rm-res").textContent = "Не понял дату или время."; return; }
    if (rep) at = rollRepeat(at, rep);
    else if (at < new Date(Date.now() - 60000)) { $("#rm-res").className = "res bad"; $("#rm-res").textContent = "Это время уже прошло — выберите позже."; return; }
    D.alarmSet(JSON.stringify(Object.assign({}, x, { title, at: at.getTime(), repeat: rep })));
    syncSoon(); if (x.kind === "timer") tmrShow();
    toast(`Сохранено: ${whenText(at)}${rep ? ", " + repRu(rep) : ""}`, 2500); back();
  };
  $("#rm-del").onclick = () => { D.alarmCancel(x.id); syncSoon(); tmrShow(); toast("Удалено", 1800); back(); };
  if ($("#rm-note")) $("#rm-note").onclick = () => openNoteSoon(x.note);
  openSheet("#sh-rem");
}
/* Поле «Что напомнить» (№556): растёт с текстом (до половины экрана), «• Пункт» ставит/снимает пункт в начале строки,
   Enter в пункте — следующий пункт, Enter в пустом пункте — пункт снимается. */
function remTextWire(ta, li) {
  if (!ta) return;
  const grow = () => { ta.style.height = "auto"; ta.style.height = Math.min(Math.max(ta.scrollHeight + 2, 84), innerHeight * 0.5) + "px"; };
  ta.addEventListener("input", grow); setTimeout(grow, 0);
  ta.addEventListener("keydown", (e) => {
    if (e.key !== "Enter" || e.shiftKey) return;
    const v = ta.value, a = ta.selectionStart, ls = v.lastIndexOf("\n", a - 1) + 1, line = v.slice(ls, a);
    if (!/^• /.test(line)) return;
    e.preventDefault();
    if (line === "• ") ta.setRangeText("", ls, a, "end"); else ta.setRangeText("\n• ", a, ta.selectionEnd, "end");
    grow();
  });
  if (li) { li.onmousedown = (e) => e.preventDefault(); li.onclick = () => {
    const v = ta.value, a = ta.selectionStart, ls = v.lastIndexOf("\n", a - 1) + 1;
    if (v.slice(ls).startsWith("• ")) ta.setRangeText("", ls, ls + 2, "end");               // уже пункт — снять
    else if (a === v.length && v.slice(ls).trim()) ta.setRangeText("\n• ", a, a, "end");    // в конце текста — новый пункт ниже
    else ta.setRangeText("• ", ls, ls, "end");                                              // иначе — эта строка становится пунктом
    ta.focus(); grow(); }; }
}
/* Отменить — и все его отложенные копии (№339, пакет 27.10: «нажал „отложить на 10 минут“, потом „Отменить“ — стало
   „Отменено“, а через 3 минуты всё равно сработало»: «Отложить» заводит новое напоминание <id>-s<время>). */
function alarmCancelAll(id) {
  let list = []; try { list = JSON.parse(D.alarms() || "[]"); } catch (e) { }
  const base = String(id).replace(/-s\d+$/, "");
  [id, ...list.map(x => x.id).filter(x => x !== id && (x === base || String(x).startsWith(base + "-s")))].forEach(x => D.alarmCancel(x));
}
window.cancelAlarm = (id, btn) => { alarmCancelAll(id); syncSoon(); tmrShow(); if (btn) btn.closest(".pill").innerHTML = "<span>Отменено</span>"; };
/* ---------- «Напоминания вовремя» (0.87, владелец 11.11: «задачи ко времени иногда приходят на час позже, как будто
   телефон спал; разблокирую — не могу найти напоминание, музыка звучит») ----------
   Телефон говорит, что мешает звонить в срок (Dewiar.alarmHealth, Bridge.java): точные будильники, окно поверх
   блокировки (Android 14+ — отдельное разрешение), уведомления, экономия батареи, опоздания за 2 недели. По марке —
   где «Автозапуск» и батарея, с подписями как на экране (как в инструкции «Управлять приложениями», №144). Кнопки
   открывают нужный экран Android сразу. Карточка — в «Звук напоминаний», коротко — в «Дне», после опоздания — на главном. */
/* №820: звук телефона для отчёта — громкость, режим, голосовой канал гарнитуры (Bridge.audioInfo) */
function audioInfo() { try { return D.audioInfo ? JSON.parse(D.audioInfo() || "{}") : undefined; } catch (e) { return undefined; } }

function remHealth() {
  if (D.web || typeof D.alarmHealth !== "function") return null;
  try { const h = JSON.parse(D.alarmHealth() || "null"); return h && typeof h === "object" && "exact" in h ? h : null; } catch (e) { return null; }
}
const REM_BRANDS = {          // [название, шаги, кнопки [что открыть, подпись]]
  xiaomi: ["Xiaomi, Redmi, POCO", [
    "<b>«Автозапуск»</b> → включите Dewiar.",
    "Страница Dewiar → <b>«Контроль активности»</b> (на HyperOS — «Батарея») → <b>«Нет ограничений»</b>.",
    "Страница Dewiar → <b>«Другие разрешения»</b> → разрешите <b>«Экран блокировки»</b> и <b>«Всплывающие окна, когда приложение в фоне»</b>.",
    "В «Недавних» потяните карточку Dewiar вниз — появится <b>замок</b>: «очистка» не закроет напоминания."],
    [["autostart", "Автозапуск"], ["app", "Страница Dewiar"]]],
  samsung: ["Samsung", [
    "Страница Dewiar → <b>«Батарея»</b> → <b>«Без ограничений»</b>.",
    "Настройки → <b>«Батарея»</b> → <b>«Ограничения фонового режима»</b> → уберите Dewiar из <b>«Спящих»</b> и <b>«Глубоко спящих приложений»</b>.",
    "Там же выключите <b>«Переводить неиспользуемые приложения в спящий режим»</b>."],
    [["app", "Страница Dewiar"]]],
  huawei: ["Huawei, Honor", [
    "<b>«Запуск приложений»</b> → Dewiar → выключите «Автоматически» и включите все три: <b>«Автозапуск»</b>, <b>«Косвенный запуск»</b>, <b>«Работа в фоне»</b>.",
    "В «Недавних» потяните карточку Dewiar вниз — появится <b>замок</b>."],
    [["autostart", "Запуск приложений"]]],
  tecno: ["Tecno, Infinix, itel", [
    "<b>«Phone Master»</b> (Диспетчер телефона) → <b>«Автозапуск»</b> → включите Dewiar.",
    "Страница Dewiar → <b>«Батарея»</b> → <b>«Без ограничений»</b> (или «Не оптимизировать»).",
    "В «Недавних» закрепите Dewiar <b>замком</b> — иначе «очистка» закроет его вместе с напоминаниями."],
    [["autostart", "Автозапуск"], ["app", "Страница Dewiar"]]],
  oppo: ["OPPO, realme, OnePlus", [
    "Страница Dewiar → <b>«Использование батареи»</b> → включите <b>«Разрешить фоновую активность»</b> и <b>«Разрешить автозапуск»</b>."],
    [["app", "Страница Dewiar"]]],
  vivo: ["vivo, iQOO", [
    "Настройки → <b>«Батарея»</b> → <b>«Фоновое энергопотребление»</b> → разрешите Dewiar.",
    "<b>«Автозапуск»</b> → включите Dewiar."],
    [["autostart", "Автозапуск"], ["app", "Страница Dewiar"]]],
  "": ["", ["Страница Dewiar → <b>«Батарея»</b> → <b>«Без ограничений»</b> (или «Не оптимизировать»)."], [["app", "Страница Dewiar"]]],
};
function remBrand(maker) {
  const d = String(maker || "").toLowerCase();
  return /xiaomi|redmi|poco/.test(d) ? "xiaomi" : /samsung/.test(d) ? "samsung" : /huawei|honor/.test(d) ? "huawei" : /tecno|infinix|itel/.test(d) ? "tecno"
    : /oppo|realme|oneplus/.test(d) ? "oppo" : /vivo|iqoo/.test(d) ? "vivo" : "";
}
/* Опоздания за 2 недели: сработавшие позже срока сами (телефон придержал во сне) и пропущенные (выключен, сигнал сняли) */
function remLates(h) {
  const l = ((h && h.late) || []).filter(x => x.how !== "dropped" && +x.late >= 5 * 60000);
  return { n: l.length, max: l.reduce((m, x) => Math.max(m, +x.late), 0), slept: l.filter(x => !x.how).length, last: l.reduce((m, x) => Math.max(m, +x.time || 0), 0) };
}
const remSpan = (ms) => { const m = Math.round(ms / 60000); return m < 60 ? `${m} мин` : `${Math.floor(m / 60)} ч${m % 60 ? " " + (m % 60) + " мин" : ""}`; };
/* Что мешает: [ключ, заголовок, почему, кнопка, действие]; важное — первым */
function remIssues(h) {
  if (!h) return [];
  const out = [], sdk = +h.sdk || androidSdk();
  if (!h.notify || (sdk >= 33 && !D.has(NOTIF))) out.push(["notify", "Уведомления выключены", "Напоминание не покажется и не зазвучит.", "Включить"]);
  if (!h.exact) out.push(["exact", "Точное время выключено", "Android может задержать напоминание на час и больше. Включите «Будильники и напоминания» для Dewiar.", "Разрешить"]);
  if (!h.fullscreen) out.push(["fullscreen", "Окно поверх блокировки выключено", "Вместо окна с кнопками — только уведомление. Включите «Полноэкранные уведомления» для Dewiar.", "Разрешить"]);
  if (!h.battery) out.push(["battery", "Android экономит батарею на Dewiar", "Во сне телефон может придержать напоминание. Выберите «Без ограничений».", "Разрешить"]);
  return out;
}
function remHealthCard() {
  const h = remHealth(); if (!h) return "";
  const iss = remIssues(h), lt = remLates(h), b = REM_BRANDS[remBrand(h.maker)] || REM_BRANDS[""], key = remBrand(h.maker);
  const good = !iss.length && !lt.n;
  return `<div class="card remok" id="rem-health"><div class="rmst ${good ? "ok" : "bad"}"><i aria-hidden="true">${good ? "✓" : "!"}</i><div><b>${good ? "Напоминания придут вовремя" : "Напоминания могут опаздывать"}</b>
      <small>${good ? "Точное время, окно поверх блокировки и работа в фоне — всё разрешено." : lt.n ? `За две недели ${lt.n === 1 ? "одно напоминание пришло" : lt.n + " напоминаний пришли"} позже срока — до ${remSpan(lt.max)}. Телефон придерживает их, пока спит.` : "Исправьте пункты ниже — это минута."}</small></div></div>
    ${iss.map(([k, t, why, btn], i) => `<div class="sw rmiss"><div>${esc(t)}<small>${esc(why)}</small></div><button class="btn${i ? "" : " p"}" data-remfix="${k}">${esc(btn)}</button></div>`).join("")}
    <details class="hfaq rmbrand"${!good && (lt.n || !iss.length) ? " open" : ""}><summary>${key ? `Настройки ${esc(b[0])}` : "Если всё равно опаздывает"}</summary>
      <p>${key ? "Оболочка телефона усыпляет приложения сама, даже когда Android всё разрешил:" : "Некоторые телефоны усыпляют приложения сами:"}</p>
      <ol class="steps hguide">${b[1].map(s => `<li>${s}</li>`).join("")}</ol>
      <div class="row2">${b[2].map(([k, t], i) => `<button class="btn${i ? "" : " p"}" data-remfix="${k}" style="flex:1">${esc(t)}</button>`).join("")}</div>
    </details>
    <p class="hint" style="margin:10px 4px 6px">Звучащее напоминание останавливается кнопкой <b>«Стоп»</b> прямо в уведомлении — в шторке и на экране блокировки; смахнули уведомление — звук тоже смолкнет. Через 2 минуты звук затихает сам.</p>
    <button class="btn w" id="rem-try">Проверить: напомнить через минуту</button><div class="res" id="rem-res"></div></div>`;
}
/* Коротко — в «Дне»: только когда правда мешает (точное время, окно, уведомления) или уже опаздывали */
function remHealthBrief() {
  const h = remHealth(); if (!h) return "";
  const iss = remIssues(h).filter(x => x[0] !== "battery"), lt = remLates(h);
  if (!iss.length && !lt.n) return "";
  return `<div class="card rembrief"><b>Напоминания могут опаздывать</b><p class="hint">${esc(iss.length ? iss[0][1] + ". " + iss[0][2] : `За две недели напоминания приходили позже срока — до ${remSpan(lt.max)}.`)}</p>
    <button class="btn p" onclick="openSettings('sound')">Как исправить</button></div>`;
}
function remFix(k) {
  const back = () => setTimeout(() => { if (setTab === "sound" && $("#rem-health")) renderSettings(); }, 400);
  if (k === "notify") { if (!D.has(NOTIF)) needPerm(NOTIF).then(back); else D.openSettings("notifications"); }
  else if (k === "battery") D.askBattery();
  else if (!D.openSettings(k === "exact" ? "alarms" : k)) toast(k === "autostart" ? "Откройте Настройки → Приложения → Dewiar" : "Откройте Настройки → Приложения → Dewiar → Разрешения", 4000);
}
function wireRemHealth() {
  $$("[data-remfix]").forEach(b => b.onclick = () => remFix(b.dataset.remfix));
  const t = $("#rem-try");
  if (t) t.onclick = () => {
    addAlarm("Проверка напоминания — всё работает ✓", new Date(Date.now() + 60000), "reminder", "");
    $("#rem-res").className = "res ok"; $("#rem-res").textContent = "Через минуту зазвонит. Заблокируйте телефон и подождите — остановить можно кнопкой «Стоп» в уведомлении.";
  };
}
/* После опоздания (телефон придержал напоминание во сне) — один раз сказать на главном экране и предложить исправить */
function remLateWatch(boot) {
  const h = remHealth(); if (!h) return;
  const lt = remLates(h), iss = remIssues(h);
  if (boot) plog(iss.length || lt.n ? "warn" : "info", `⏰ напоминания: точное время — ${h.exact ? "да" : "нет"}, окно поверх блокировки — ${h.fullscreen ? "да" : "нет"}, `
    + `уведомления — ${h.notify ? "да" : "нет"}, батарея — ${h.battery ? "без ограничений" : "экономит"}, сигнал — ${h.mode || "—"}, опозданий за 2 недели — ${lt.n}${lt.n ? " (до " + remSpan(lt.max) + ")" : ""}`);
  if (!lt.slept || lt.last <= (S.remLateSeen || 0)) return;
  if (busy || $("#card").innerHTML || $(".sheet.on")) return;            // на свободный экран — или при следующем возвращении
  S.remLateSeen = lt.last; saveS();
  showCard(`<div class="card remlate"><p><b>Напоминание пришло позже срока — на ${remSpan(lt.max)}.</b> Телефон придержал его, пока спал. ${iss.length ? esc(iss[0][1]) + " — это и мешает." : "Поможет пара настроек телефона."}</p>
    <div class="row2"><button class="btn p" id="rl-fix" style="flex:1">Исправить</button><button class="btn" id="rl-no">Позже</button></div></div>`);
  $("#rl-fix").onclick = () => { showCard(""); openSettings("sound"); };
  $("#rl-no").onclick = () => showCard("");
}
/* ---------- таймер с обратным отсчётом (как у Алисы): на главном экране, а в шторке — тикающий отсчёт (TimerNote.java) ----------
   Таймеры — будильники вида timer (D.alarms); строки рисуются раз в секунду, список перечитывается раз в 2 с. */
let TMRS = [], tmrIv = 0, tmrRead = 0;
/* Таймеры голосом без модели (как core/engine_tools.py _timer_cmd): таймеров нет — null, решает модель. */
function timerVoice(t) {
  const list = alarmsNow().filter(x => x.kind === "timer" && +x.at > Date.now()).sort((a, b) => a.at - b.at);
  if (!list.length) return null;
  t = t.replace(/[?!.,]/g, " ").replace(/\s+/g, " ").trim().replace(/ё/g, "е");
  const dur = (sec, acc) => { const h = Math.floor(sec / 3600), m = Math.floor(sec % 3600 / 60), s_ = sec % 60;
    const w = (n, a, b, c) => `${n} ` + (n % 10 === 1 && n % 100 !== 11 ? a : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 12 || n % 100 > 14) ? b : c);
    const p = [h ? w(h, "час", "часа", "часов") : "", m ? w(m, acc ? "минуту" : "минута", "минуты", "минут") : "", s_ && !h && m < 10 ? w(s_, acc ? "секунду" : "секунда", "секунды", "секунд") : ""].filter(Boolean);
    const o = p.join(" ") || "меньше секунды"; return acc ? o.replace(/^1 (минуту|секунду|час)$/, "$1") : o; };
  const left = (x) => Math.max(0, Math.round((+x.at - Date.now()) / 1000));
  if (/^(?:а )?(?:сколько (?:еще |там )?(?:осталось|остается|времени осталось|минут осталось)(?: (?:на|до|у) таймер[а-я]*)?|сколько (?:там )?на таймере|сколько (?:еще|там)|что (?:там )?с таймером|таймер сколько)$/.test(t)
      || (/таймер/.test(t) && /сколько|осталось/.test(t)))
    return { say: list.length === 1 ? `Осталось ${dur(left(list[0]))}.` : "Осталось: " + list.slice(0, 3).map(x => `${(x.title || "таймер").replace(/^Т/, "т")} — ${dur(left(x))}`).join("; ") + "." };
  let m = t.match(/^(?:добавь|прибавь|продли(?: таймер)?(?: на)?|накинь|еще)(?: еще)? (\d+|одну|минуту|две|три|пять|десять|полминуты)?\s*(минут[уы]?|секунд[уы]?)?(?: (?:к|на|в) таймер[а-я]*| таймер[а-я]*)?$/);
  if (m && (m[1] || m[2]) && (/таймер/.test(t) || /^(?:добавь|прибавь|накинь)/.test(t) || (/^еще/.test(t) && (m[2] || ["минуту", "полминуты"].includes(m[1]))))) {
    const n = m[1] === "полминуты" ? 30 : /^\d+$/.test(m[1] || "") ? +m[1] : ({ одну: 1, минуту: 1, две: 2, три: 3, пять: 5, десять: 10 })[m[1] || "минуту"] || 1;
    const sec = /^секунд/.test(m[2] || "") || m[1] === "полминуты" ? n : n * 60, x = list[0];
    if (typeof EXAM !== "undefined" && EXAM) x.at = +x.at + sec * 1000; else D.alarmSet(JSON.stringify(Object.assign({}, x, { at: +x.at + sec * 1000 })));
    syncSoon(); tmrShow();
    return { say: `${persona().gender === "female" ? "Добавила" : "Добавил"} ${dur(sec, true)}. Теперь осталось ${dur(left(Object.assign({}, x, { at: +x.at + (typeof EXAM !== "undefined" && EXAM ? 0 : sec * 1000) })))}.` };
  }
  if (/^(?:отмени|выключи|останови|убери|сбрось|удали)(?: все)? таймер[а-я]*$/.test(t)) {
    const gone = / все /.test(` ${t} `) || list.length === 1 ? list : list.slice(0, 1);
    gone.forEach(x => remDrop(x.id)); tmrShow();
    return { say: gone.length === 1 ? "Таймер отменён." : `${persona().gender === "female" ? "Отменила" : "Отменил"} таймеры: ${gone.length}.` };
  }
  return null;
}
const tmrFmt = (ms) => { const s = Math.max(0, Math.ceil(ms / 1000)), h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), c = s % 60;
  return h ? `${h}:${pad(m)}:${pad(c)}` : `${m}:${pad(c)}`; };
const tmrSeen = {};                                   // таймер пришёл с компьютера без from — прогресс от того, как увидели
function tmrShow() {
  if (typeof EXAM !== "undefined" && EXAM) return;
  const now = Date.now();
  TMRS = JSON.parse(D.alarms() || "[]").filter(x => x.kind === "timer" && +x.at > now - 1500 && +x.at - now < 24 * 3600e3).sort((a, b) => a.at - b.at).slice(0, 3);
  TMRS.forEach(x => { if (!x.from) x.from = tmrSeen[x.id] = tmrSeen[x.id] || now; });
  const box = $("#tmrs"); if (!box) return;
  box.hidden = !TMRS.length;
  box.innerHTML = TMRS.map(x => { const mins = Math.round((x.at - x.from) / 60000);
    const name = !x.title || /^Таймер( на .*)?$/i.test(x.title) ? (mins >= 1 ? `таймер на ${spanRu(mins)}` : "таймер") : x.title;
    return `<div class="tr" data-id="${esc(x.id)}"><svg class="pg" viewBox="0 0 36 36"><circle class="bg" cx="18" cy="18" r="15.5"/><circle class="fg" cx="18" cy="18" r="15.5" pathLength="100" stroke-dasharray="100" stroke-dashoffset="0"/></svg>`
      + `<div class="tt"><b></b><span>${esc(name)}</span></div><button class="x" aria-label="Отменить таймер">${X_SVG}</button></div>`; }).join("");
  $$("#tmrs .x").forEach(b => b.onclick = () => { D.alarmCancel(b.closest(".tr").dataset.id); syncSoon(); tmrShow(); });
  clearInterval(tmrIv); tmrRead = now;
  if (TMRS.length) { tmrIv = setInterval(tmrDraw, 250); tmrDraw(); }
}
function tmrDraw() {
  const now = Date.now();
  if (now - tmrRead > 2000) return tmrShow();             // отменили в шторке, сработал, пришёл с компьютера — перечитать
  TMRS.forEach(x => { const r = $(`#tmrs .tr[data-id="${CSS.escape(x.id)}"]`); if (!r) return;
    const left = +x.at - now, all = Math.max(1000, +x.at - x.from);
    $(".tt b", r).textContent = tmrFmt(left); r.classList.toggle("end", left <= 10000);
    $(".fg", r).style.strokeDashoffset = String(Math.min(100, Math.max(0, 100 - left / all * 100))); });
  if (TMRS.every(x => +x.at < now - 1500)) tmrShow();
}

