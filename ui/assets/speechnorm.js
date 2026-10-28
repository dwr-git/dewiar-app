/* Текст для русского синтеза речи — то же, что core/speechnorm.py (числа словами, даты и время, суммы, проценты, латиница
   русскими буквами), чтобы телефон отдавал серверу голоса уже «читаемый» текст и не зависел от того, обновлена ли служба
   голосов (отзыв 16.10: «спросил время — написала 14:10, а произнесла „ствисе“»). Меняешь здесь — меняй и там:
   tests/speechnorm_js_test.py сверяет оба на одних фразах. window.DewiarSpeech.norm(text, latin = true). */
(function () {
  /* Старый Safari (iPhone и Mac до 16.4) не знает «взгляда назад» (?<= ?<!) в регулярных выражениях — литерал с ним
     ронял весь файл, а с ним и веб-версию (жалоба 28.10: «не работает совсем, не отвечает»). Здесь его нет: символ перед
     совпадением проверяет lbReplace — ровно как движок (не подошло — ищем со следующей позиции; alt — другая ветка
     выражения на том же месте). Результат тот же, что у core/speechnorm.py (tests/speechnorm_js_test.py). */
  function lbReplace(t, re, ok, fn, alt) {
    let out = "", last = 0, m; re.lastIndex = 0;
    while ((m = re.exec(t)) !== null) {
      const i = m.index;
      if (!ok(i ? t[i - 1] : "", m)) {
        if (alt) { alt.lastIndex = i; const a = alt.exec(t); if (a) { out += t.slice(last, i) + fn(...a); last = re.lastIndex = i + a[0].length; continue; } }
        re.lastIndex = i + 1; continue;
      }
      out += t.slice(last, i) + fn(...m); last = i + m[0].length;
      re.lastIndex = m[0].length ? last : i + 1;
    }
    return out + t.slice(last);
  }
  const isSp = (c) => c === "" || /\s/.test(c), isLat = (c) => /[A-Za-z]/.test(c), isNum = (c) => /[\d.,:]/.test(c), isDig = (c) => /\d/.test(c);
  const ONES = ["ноль", "один", "два", "три", "четыре", "пять", "шесть", "семь", "восемь", "девять", "десять", "одиннадцать",
    "двенадцать", "тринадцать", "четырнадцать", "пятнадцать", "шестнадцать", "семнадцать", "восемнадцать", "девятнадцать"];
  const ONES_F = { 1: "одна", 2: "две" };
  const TENS = ["", "", "двадцать", "тридцать", "сорок", "пятьдесят", "шестьдесят", "семьдесят", "восемьдесят", "девяносто"];
  const HUND = ["", "сто", "двести", "триста", "четыреста", "пятьсот", "шестьсот", "семьсот", "восемьсот", "девятьсот"];
  const SCALES = [[1e12, ["триллион", "триллиона", "триллионов"], false], [1e9, ["миллиард", "миллиарда", "миллиардов"], false],
    [1e6, ["миллион", "миллиона", "миллионов"], false], [1000, ["тысяча", "тысячи", "тысяч"], true]];
  const W = "0-9A-Za-z_А-Яа-яЁё";                       // \w Python (с кириллицей): в JS \w — только латиница
  const inW = (c) => c !== "" && new RegExp(`[${W}]`).test(c);

  function plural(n, f) { n = Math.abs(n) % 100; if (n >= 11 && n <= 14) return f[2]; return n % 10 === 1 ? f[0] : n % 10 >= 2 && n % 10 <= 4 ? f[1] : f[2]; }
  function under1000(n, fem) {
    const out = [];
    if (n >= 100) { out.push(HUND[Math.floor(n / 100)]); n %= 100; }
    if (n >= 20) { out.push(TENS[Math.floor(n / 10)]); n %= 10; }
    if (n || !out.length) out.push(fem && ONES_F[n] ? ONES_F[n] : ONES[n]);
    return out.filter(w => w && !(w === "ноль" && out.length > 1));
  }
  function numberWords(n, fem) {
    n = Math.trunc(+n);
    if (n < 0) return "минус " + numberWords(-n, fem);
    if (n === 0) return "ноль";
    let words = [];
    for (const [value, forms, female] of SCALES) {
      if (n >= value) {
        const k = Math.floor(n / value);
        if (k > 1) words = words.concat(k < 1000 ? under1000(k, female) : numberWords(k).split(" "));
        words.push(plural(k, forms));
        n %= value;
      }
    }
    if (n) words = words.concat(under1000(n, fem));
    return words.join(" ");
  }
  const LETTER = { a: "эй", b: "би", c: "си", d: "ди", e: "и", f: "эф", g: "джи", h: "эйч", i: "ай", j: "джей", k: "кей", l: "эл", m: "эм",
    n: "эн", o: "оу", p: "пи", q: "кью", r: "ар", s: "эс", t: "ти", u: "ю", v: "ви", w: "дабл-ю", x: "экс", y: "уай", z: "зед" };
  const TR2 = [["sch", "ш"], ["sh", "ш"], ["ch", "ч"], ["th", "т"], ["ph", "ф"], ["ck", "к"], ["oo", "у"], ["ee", "и"], ["ea", "и"],
    ["ou", "ау"], ["qu", "кв"], ["kh", "х"], ["zh", "ж"], ["ya", "я"], ["yu", "ю"], ["yo", "ё"], ["ts", "ц"]];
  const TR1 = { a: "а", b: "б", c: "к", d: "д", e: "е", f: "ф", g: "г", h: "х", i: "и", j: "дж", k: "к", l: "л", m: "м", n: "н", o: "о",
    p: "п", q: "к", r: "р", s: "с", t: "т", u: "у", v: "в", w: "в", x: "кс", y: "и", z: "з" };
  const KNOWN = { linux: "линукс", ubuntu: "убунту", windows: "виндоус", telegram: "телеграм", max: "макс", dewiar: "дэвиаар",
    youtube: "ютуб", google: "гугл", yandex: "яндекс", wifi: "вай-фай", "wi-fi": "вай-фай", ok: "окей", email: "имейл", sudo: "судо",
    python: "пайтон", chrome: "хром", obsidian: "обсидиан", android: "андроид", iphone: "айфон", bluetooth: "блютус", hdmi: "эйч-ди-эм-ай",
    jazz: "джаз", relax: "релакс", fm: "эф-эм" };
  function latinWord(w) {
    const low = w.toLowerCase();
    if (KNOWN[low]) return KNOWN[low];
    if ((w === w.toUpperCase() && w.length <= 6) || w.length === 1) return [...low].map(c => LETTER[c] || c).join("-");
    let out = "", i = 0;
    while (i < low.length) {
      const t2 = TR2.find(([a]) => low.startsWith(a, i));
      if (t2) { out += t2[1]; i += t2[0].length; } else { out += TR1[low[i]] || low[i]; i++; }
    }
    return out;
  }
  function num(s) {
    if (s.includes(":")) {
      const [h, mi] = s.split(":");
      return numberWords(+h) + (mi.startsWith("0") && mi !== "00" ? " ноль " + numberWords(+mi) : mi === "00" ? "" : " " + numberWords(+mi));
    }
    const parts = s.split(/[.,]/);
    if (parts.length === 1) return s.length <= 15 ? numberWords(+s) : [...s].map(c => numberWords(+c)).join(" ");
    return parts.map(p => p ? numberWords(+p) : "").join(" точка ");
  }
  const FRAC = { 1: ["десятая", "десятых", "десятых"], 2: ["сотая", "сотых", "сотых"] };
  const MONEY = { rub: [["рубль", "рубля", "рублей"], ["копейка", "копейки", "копеек"]], usd: [["доллар", "доллара", "долларов"], ["цент", "цента", "центов"]],
    eur: [["евро", "евро", "евро"], ["цент", "цента", "центов"]] };
  function money(n, k, cur) {
    n = +n; const [rub, kop] = MONEY[cur];
    let out = `${numberWords(n)} ${plural(n, rub)}`;
    if (k && +k.padEnd(2, "0")) { const kk = +k.padEnd(2, "0"); out += ` ${numberWords(kk, cur === "rub")} ${plural(kk, kop)}`; }
    return out;
  }
  const MONTHS = "января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря", MONTH_LIST = MONTHS.split("|");
  const ORD = { 1: "перв", 2: "втор", 3: "трет", 4: "четвёрт", 5: "пят", 6: "шест", 7: "седьм", 8: "восьм", 9: "девят", 10: "десят",
    11: "одиннадцат", 12: "двенадцат", 13: "тринадцат", 14: "четырнадцат", 15: "пятнадцат", 16: "шестнадцат", 17: "семнадцат",
    18: "восемнадцат", 19: "девятнадцат", 20: "двадцат", 30: "тридцат", 40: "сороков", 50: "пятидесят", 60: "шестидесят",
    70: "семидесят", 80: "восьмидесят", 90: "девяност", 100: "сот" };
  const ORD_END = { m_nom: ["ый", "ой", "ий"], n_nom: ["ое", "ое", "ье"], gen: ["ого", "ого", "ьего"], dat: ["ому", "ому", "ьему"],
    prep: ["ом", "ом", "ьем"], ins: ["ым", "ым", "ьим"], f_nom: ["ая", "ая", "ья"], f_gen: ["ой", "ой", "ьей"], pl: ["ые", "ые", "ьи"] };
  function ordinalWords(n, form = "n_nom") {
    n = Math.trunc(+n);
    let last = n % 100 < 20 ? n % 100 : (n % 10 || n % 100);
    if (n % 100 >= 20 && n % 10) last = n % 10;
    if (!last || !ORD[last]) { if (n % 100 === 0 && n % 1000) last = 100; else return null; }
    let head = n - last ? numberWords(n - last) : "";
    const stem = ORD[last], i = stem === "трет" ? 2 : ["втор", "шест", "седьм", "восьм", "сороков"].includes(stem) ? 1 : 0;
    const word = stem + ORD_END[form][i];
    if (head.endsWith("сто") && last === 100) head = head.slice(0, -3).trim();
    return (head + " " + word).trim();
  }
  const NOT_FEM = new Set(["часа", "дня", "года", "раза", "рубля", "доллара", "человека", "шага", "градуса", "процента", "километра", "метра",
    "литра", "килограмма", "грамма", "пункта", "этажа", "балла", "урока", "вопроса", "ответа", "файла", "месяца", "мужчина", "папа"]);
  const NOT_NEUT = new Set(["кофе", "евро", "кино", "метро", "пальто", "радио", "фото"]);
  function agree(n, word) {
    const w = word.toLowerCase(), k = n % 10, k2 = n % 100;
    if ((k2 >= 11 && k2 <= 14) || (k !== 1 && k !== 2)) return numberWords(n);
    if (k === 1 && /[ая]$/.test(w) && !NOT_FEM.has(w)) return numberWords(n, true);
    if (k === 2 && /[ыи]$/.test(w) && !NOT_FEM.has(w)) return numberWords(n, true);
    if (k === 1 && /[ую]$/.test(w)) return numberWords(n).replace(/один$/, "одну");
    if (k === 1 && /[ое]$/.test(w) && !NOT_NEUT.has(w)) return numberWords(n).replace(/один$/, "одно");
    return numberWords(n);
  }
  const caseOf = (pre) => { const p = (pre || "").trim().toLowerCase();
    return ["до", "с", "со", "от", "после", "около", "начиная с", "кроме"].includes(p) ? "gen" : ["к", "ко", "по"].includes(p) ? "dat" : "n_nom"; };
  const PRE = "((?:до|с|со|от|после|около|к|ко|по|на|в)\\s+)?", preOk = (c, m) => m[1] ? isSp(c) : !isNum(c);   // перед предлогом — пробел или начало

  // Римские цифры (пакет 27.10) — как roman_norm в core/speechnorm.py: «XIX век», «Пётр I», «Ступень I», «Екатерины II»
  const ROMAN = /^M{0,3}(?:CM|CD|D?C{0,3})(?:XC|XL|L?X{0,3})(?:IX|IV|V?I{0,3})$/, RV = { I: 1, V: 5, X: 10, L: 50, C: 100, D: 500, M: 1000 };
  const R_FEM = new Set(["часть", "ступень", "глава", "книга", "серия", "война", "олимпиада", "категория", "группа", "степень", "четверть",
    "половина", "лига", "конференция", "дума", "республика", "симфония", "соната", "партия", "редакция", "мировая",
    "екатерина", "елизавета", "анна", "мария", "империя", "династия", "эпоха", "фаза", "стадия", "очередь"]);
  const R_FEM_GEN = new Set(["екатерины", "елизаветы", "анны", "марии", "части", "главы", "книги", "серии", "войны", "степени", "стадии", "фазы"]);
  const R_NEUT = new Set(["издание", "тысячелетие", "собрание", "поколение", "царство", "отделение"]);
  const R_SKIP = new Set(["размер", "размера", "размеры", "размеров", "витамин", "витамина", "группы", "класс"]);
  function romanValue(s) {
    if (!s || !ROMAN.test(s)) return 0;
    const v = [...s].map(c => RV[c]);
    return v.reduce((a, x, i) => a + (i + 1 < v.length && x < v[i + 1] ? -x : x), 0);
  }
  const romanOk = (r) => romanValue(r) && (r.length > 1 || "IVX".includes(r));
  function romanNorm(t) {
    t = lbReplace(t, /((?:в|во)\s+)?([IVXLCDM]+)(?:\s*[-–—]\s*([IVXLCDM]+))?\s+(век(?:а|у|е|ом|ов|ах)?|вв?\.)(?![а-яё])/gi, (c, m) => m[1] ? isSp(c) : !isLat(c), (m, pre, a, b, w) => {
      pre = pre || ""; let wl = w.toLowerCase().replace(/\.$/, "");
      if (pre && wl === "в") { wl = "веке"; w = "веке"; } else if (pre && wl === "вв") { wl = "веках"; w = "веках"; }
      let form = { "век": "m_nom", "века": "gen", "веку": "dat", "веке": "prep", "веком": "ins", "веков": "gen", "веках": "prep", "в": "m_nom", "вв": "pl" }[wl] || "m_nom";
      if (b && form === "m_nom") form = "pl";
      if (!romanOk(a) || (b && !romanOk(b))) return m;
      let word = { "в": "век", "вв": "века" }[wl] || w;
      if (form === "pl" && (wl === "век" || wl === "в")) word = "века";
      let head = ordinalWords(romanValue(a), form);
      if (b) head += " — " + ordinalWords(romanValue(b), form);
      return `${pre}${head} ${word}`;
    });
    return lbReplace(t, /([А-ЯЁа-яё]+)\s+([IVXLCDM]+)(?![A-Za-z0-9])(?!\s+[A-Za-z])/g, (c) => !isLat(c), (m, w, r) => {
      const lw = w.toLowerCase(), up = w[0] !== w[0].toLowerCase();
      if (!romanOk(r) || R_SKIP.has(lw)) return m;
      const form = R_FEM.has(lw) ? "f_nom" : R_FEM_GEN.has(lw) ? "f_gen" : R_NEUT.has(lw) ? "n_nom" : up && /[ая]$/.test(lw) ? "gen"
        : up && /[ую]$/.test(lw) ? "dat" : up && /(?:ом|ем|ём)$/.test(lw) ? "ins" : up && /е$/.test(lw) ? "prep" : "m_nom";
      return `${w} ${ordinalWords(romanValue(r), form)}`;
    });
  }
  function norm(text, latin = true) {
    let t = romanNorm(String(text == null ? "" : text));
    for (let i = 0; i < 3; i++) t = lbReplace(t, /(\d{1,3})[   ](?=\d{3}(?!\d))/g, (c) => !/[\d.,]/.test(c), (m, a) => a);
    t = t.replace(/(\d+)(?:[.,](\d{1,2}))?\s*(?:руб(?:л[а-яё]*)?\.?|₽|р\.|BYN|RUB)(?![а-яёА-ЯЁA-Za-z])/g, (m, n, k) => money(n, k, "rub"));
    t = t.replace(/\$\s*(\d+)(?:[.,](\d{1,2}))?|(\d+)(?:[.,](\d{1,2}))?\s*(?:\$|долл\.|USD)/g, (m, n, k, n2, k2) => money(n || n2, k || k2, "usd"));
    t = t.replace(/(\d+)(?:[.,](\d{1,2}))?\s*(?:€|EUR)/g, (m, n, k) => money(n, k, "eur"));
    t = lbReplace(t, /(\d{1,9}),(\d{1,2})(?!\d|[.,]\d)/g, (c) => !isNum(c), (m, a, b) => `${numberWords(+a, true)} и ${numberWords(+b, true)} ${plural(+b, FRAC[b.length])}`);
    for (const [re, w] of [[/\s*=\s*(?=[-−]?\d)/g, " равно "], [/\s+[-−–]\s+(?=\d)/g, " минус "], [/\s*\+\s*(?=\d)/g, " плюс "],
      [/\s*[×*]\s*(?=\d)/g, " умножить на "], [/\s*÷\s*(?=\d)/g, " разделить на "]]) t = lbReplace(t, re, isDig, () => w);   // «12 - 10 = 2» — словами
    t = t.replace(/https?:\/\/\S+/g, "ссылка");
    if (latin) t = lbReplace(t, new RegExp(`(?=[${W}]*\\d)(?=[${W}]*[A-Za-z])[A-Za-z0-9_]{4,}(?![${W}])`, "g"), (c) => !inW(c), () => " ");
    t = lbReplace(t, /(?=(\d))|(?=([A-Za-z]))/g, (c, m) => m[1] !== undefined ? isLat(c) : isDig(c), () => " ");
    t = lbReplace(t, /\+(?=\d)/g, (c) => !inW(c) && c !== "-", () => "плюс ");
    t = lbReplace(t, /[-−](?=\d)/g, (c) => !inW(c) && c !== "-", () => "минус ");
    t = t.replace(/(\d+)\s*%/g, (m, n) => `${numberWords(+n)} ${plural(+n, ["процент", "процента", "процентов"])}`);
    t = t.replace(/(\d+)\s*°\s*[CС]?(?![A-Za-zА-Яа-яЁё])/g, (m, n) => `${numberWords(+n)} ${plural(+n, ["градус", "градуса", "градусов"])}`);
    t = lbReplace(t, /((?:до|с|со|от|после|около|к|ко|по)\s+)?(\d{1,2})\.(\d{1,2})\.(\d{4})(?![\d.,]\d)/gi, preOk,
      (m, pre, d, mo, y) => { d = +d; mo = +mo; if (!(d >= 1 && d <= 31 && mo >= 1 && mo <= 12)) return m; const f = caseOf(pre);
        return `${pre || ""}${ordinalWords(d, f) || numberWords(d)} ${MONTH_LIST[mo - 1]} ${ordinalWords(+y, "gen") || numberWords(+y)} года`; });
    t = lbReplace(t, /(\d{3,4})\s+(год|года|году|годом|годе)(?![а-яё])/g, (c) => !isNum(c), (m, n, g) => {
      const form = { "год": "m_nom", "года": "gen", "году": "prep", "годом": "ins", "годе": "prep" }[g.toLowerCase()] || "m_nom";
      return `${ordinalWords(+n, form) || numberWords(+n)} ${g}`; });
    t = lbReplace(t, new RegExp(PRE + "(\\d{1,2})\\s+(" + MONTHS + ")(?![а-яё])", "gi"), preOk, (m, pre, n, mon) => {
      n = +n; const w = n >= 1 && n <= 31 ? ordinalWords(n, caseOf(pre)) : null; return `${pre || ""}${w || numberWords(n)} ${mon}`; });
    t = lbReplace(t, /(\d{1,15})(?![\d.,:])(\s+)([А-Яа-яЁё]+)/g, (c) => !isNum(c), (m, n, sp, w) => agree(+n, w) + sp + w);
    t = lbReplace(t, new RegExp(`([01]?\\d|2[0-3]):[0-5]\\d(?![${W}])|\\d+(?:[.,]\\d+)*`, "g"), (c, m) => m[1] === undefined || !inW(c), (m) => num(m), /\d+(?:[.,]\d+)*/y);
    if (!latin) return end(t.replace(/№/g, "номер ").replace(/[ \t]+/g, " ").trim());
    t = t.replace(/[A-Za-z]+(?:-[A-Za-z]+)?/g, (m) => latinWord(m));
    t = t.replace(/&/g, " и ").replace(/\+/g, " плюс ").replace(/=/g, " равно ").replace(/№/g, "номер ");
    t = t.replace(/[^А-Яа-яЁё ,.!?:;—\-«»"()']+/g, " ");
    return end(t.replace(/\s+/g, " ").trim());
  }
  // фраза без точки в конце — с точкой: иначе голос сервера глотал последнее слово («…равно два» — без «два»)
  const end = (t) => t && /[0-9A-Za-zА-Яа-яЁё»)"']$/.test(t) ? t + "." : t;
  window.DewiarSpeech = { norm, numberWords, ordinalWords };
})();
