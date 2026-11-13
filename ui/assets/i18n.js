/* Языки окон Dewiar (0.88; владелец 11.11: «ru.json, en.json — всё в отдельных файлах; нет русского в системе — сразу
   английский, в настройках — переключение»). Словари — data/i18n/<язык>.json, в окна их кладёт ui/assets/i18n.data.js
   (window.DW_I18N; собирает tools/i18n_build.py). Подключается сразу после boot.js — до разметки страницы.

   В разметке: <button data-i18n="nav.home">Главная</button> — текст элемента (первый текстовый узел: значки-точки внутри
   остаются); data-i18n-title / -placeholder / -aria-label — атрибуты. Русский в разметке = исходный (без вспышки),
   tests/i18n_test.py сверяет его с ru.json. В коде: t("ключ", {n: 3, name: "Анна"}); числа — формами CLDR
   (Intl.PluralRules), даты и числа — dwLocale().

   Язык: ?lang= в адресе окна (его ставит ui/app.py из settings ui.lang); нет — русский. Студия, получив настройки, зовёт
   dwSetLang(S.ui.lang, sys_lang ядра) — смена языка применяется без перезапуска (событие "dw-lang"). */
(function () {
  // языки — те, чьи словари есть (новый язык = новый data/i18n/<код>.json); нет строки — английская, затем русская
  const SRC = "ru", FB = "en", RTL = ["ar", "he", "fa", "ur"];
  const LANGS = [SRC].concat(Object.keys(window.DW_I18N || {}).filter(c => c !== SRC).sort());   // русский, затем по коду
  // «как в системе» решает ядро (core/i18n.py: язык интерфейса Windows, LANG) — оно же ставит ?lang= окну и присылает
  // sys_lang в «hello»; язык браузера не спрашиваем: у WebView он бывает другим, чем у системы
  let sysLang = "";
  try { sysLang = (window.dwQuery && window.dwQuery().get("lang")) || ""; } catch (e) { }
  const sys = () => (LANGS.includes(sysLang) ? sysLang : SRC);
  const pick = (v) => { v = String(v || "auto").toLowerCase(); return LANGS.includes(v) ? v : sys(); };
  let lang = sys();
  // перевод по тексту — отдельным файлом (i18n.tx.js, ~0,9 МБ): русским он не нужен. Язык окна не русский — грузим
  // сразу, вместе со страницей (document.write во время разбора — без вспышки русского); сменили язык позже — догружаем
  const TX_URL = (() => { try { return document.currentScript.src.replace(/i18n\.js(\?.*)?$/, "i18n.tx.js"); } catch (e) { return "assets/i18n.tx.js"; } })();
  let txLoading = null;
  if (lang !== SRC && !window.DW_TX && document.readyState === "loading") {
    try { document.write('<script src="' + TX_URL + '"><\/script>'); } catch (e) { }
  }
  function txFetch() {
    if (window.DW_TX) return Promise.resolve();
    if (!txLoading) txLoading = new Promise((ok) => {
      const s = document.createElement("script"); s.src = TX_URL; s.onload = s.onerror = () => ok();
      (document.head || document.documentElement).appendChild(s);
    });
    return txLoading;
  }
  const cat = (l) => ((window.DW_I18N || {})[l]) || {};
  const PR = {};
  const form = (l, n) => { try { return (PR[l] || (PR[l] = new Intl.PluralRules(l))).select(Number(n) || 0); } catch (e) { return "other"; } };
  function t(key, params) {
    params = params || {};
    let l = lang, v;
    for (const x of [lang, FB, SRC]) { v = cat(x)[key]; if (v != null) { l = x; break; } }
    if (v == null) return key;
    if (typeof v === "object") v = v[form(l, params.n)] || v.other || Object.values(v)[0] || key;
    return String(v).replace(/\{(\w+)\}/g, (m, k) => (k in params ? String(params[k]) : m));
  }
  const ATTRS = [["data-i18n-title", "title"], ["data-i18n-placeholder", "placeholder"], ["data-i18n-aria-label", "aria-label"]];
  function setText(el, s) {
    const tn = [...el.childNodes].find(n => n.nodeType === 3 && n.nodeValue.trim());
    if (tn) tn.nodeValue = tn.nodeValue.replace(tn.nodeValue.trim(), s);
    else el.insertBefore(document.createTextNode(s), el.firstChild);
  }
  function apply(root) {
    root = root || document;
    const all = root.querySelectorAll ? root.querySelectorAll("[data-i18n],[data-i18n-title],[data-i18n-placeholder],[data-i18n-aria-label]") : [];
    for (const el of all) {
      const k = el.getAttribute("data-i18n");
      if (k) setText(el, t(k));
      for (const [a, attr] of ATTRS) { const ak = el.getAttribute(a); if (ak) el.setAttribute(attr, t(ak)); }
    }
    if (document.documentElement) { document.documentElement.lang = lang; document.documentElement.dir = RTL.includes(lang) ? "rtl" : "ltr"; }
  }
  /* 0.95 — перевод по тексту (как gettext: русская строка сама и есть ключ). Словари data/i18n/text/<язык>.json
     {"Русский текст": "Text"} собираются в window.DW_TX. Когда язык не русский, всё, что попадает на страницу (разметка
     и то, что дорисовал код), сверяется с ними: текстовые узлы и title/placeholder/aria-label/alt, совпавшие целиком
     (пробелы не в счёт), меняются на перевод. Строки с «{1}», «{2}» — образцы: «Сохранено {1} из {2}» ловит
     «Сохранено 3 из 5». Своё содержимое людей (заметки, чат, поля ввода) не трогаем: внутри translate="no",
     contenteditable, textarea, input, pre, code — как есть. Вернулись к русскому — оригиналы восстанавливаются. */
  const TXA = ["title", "placeholder", "aria-label", "alt"];
  const nrm = (s) => String(s).replace(/\s+/g, " ").trim();
  const CYR = /[А-Яа-яЁё]/;
  const txOrig = new WeakMap(), txAttr = new WeakMap();
  let txFor = "", txMap = null, txPat = null, txObs = null, txDepth = 0;
  function txLoad() {
    if (txFor === lang) return txMap;
    txFor = lang; txMap = new Map(); txPat = new Map();
    const d = ((window.DW_TX || {})[lang]) || (lang !== SRC ? ((window.DW_TX || {})[FB]) || {} : {});
    for (const k in d) {
      const v = d[k];
      if (!v) continue;
      if (/\{\d\}/.test(k)) {                                   // образец: ключ корзины — начало строки до первой подстановки
        const head = k.split(/\{\d\}/)[0];
        const rx = new RegExp("^" + k.split(/(\{\d\})/).map(p => /^\{\d\}$/.test(p) ? "(.*?)" : p.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("") + "$");
        const order = (k.match(/\{\d\}/g) || []).map(x => x[1]);
        const b = head.length >= 3 ? head.slice(0, 3) : "";
        // мало своих букв («ещё {1}») — подстановка не должна быть русским текстом: иначе «ещё не было» станет «не было more»
        const weak = k.replace(/\{\d\}/g, "").replace(/[^A-Za-zА-Яа-яЁё]/g, "").length < 6;
        if (!txPat.has(b)) txPat.set(b, []);
        txPat.get(b).push([rx, order, v, weak, k.replace(/\{\d\}/g, "").length]);
      } else txMap.set(k, v);
    }
    // в корзине — сначала образцы с самым длинным своим текстом: «Сейчас включён сам: {1}.» раньше «{1} {2} процессора»
    for (const l of txPat.values()) l.sort((a, b) => b[4] - a[4]);
    return txMap;
  }
  function txSub(s) {                                         // кусок строки — со всеми правилами, но не глубже 4
    if (txDepth >= 4) return null;
    txDepth++;
    try { return txOf(s); } finally { txDepth--; }
  }
  function txOf(s, inner) {
    const k = nrm(s);
    if (!k || !CYR.test(k)) return null;
    const v = txMap.get(k);
    if (v != null) return v;
    for (const b of [k.slice(0, 3), ""]) {
      for (const [rx, order, tr, weak] of (txPat.get(b) || [])) {
        const m = k.match(rx);
        if (!m) continue;
        const got = {};
        let ok = true;
        order.forEach((n, i) => {
          let c = m[i + 1];
          if (CYR.test(c)) {                                // «Утро с Лирой», «2 ядра процессора»: подстановку тоже
            let t = null;
            if (txDepth < 4) { txDepth++; try { t = txOf(c); } finally { txDepth--; } }
            if (t != null) c = t; else if (weak) ok = false;
          }
          got[n] = c;
        });
        if (ok) return tr.replace(/\{(\d)\}/g, (x, n) => (n in got ? got[n] : x));
      }
    }
    if (inner) return null;
    let m = k.match(/^[«“"„](.+)[»”"“]([.,:;!?…]*)$/);              // «фраза» в кавычках, «→ пояснение», «• пункт»
    if (m) { const t = txOf(m[1], true); if (t != null) return "“" + t + "”" + m[2]; }
    m = k.match(/^([→—–·•]\s*)(.+)$/);
    if (m) { const t = txOf(m[2], true); if (t != null) return m[1] + t; }
    m = k.match(/^(.+?)\s*(\(\d+\))$/);                                // «Все вкладки (3)»
    if (m) { const t = txOf(m[1], true); if (t != null) return t + " " + m[2]; }
    m = k.match(/^(.+?)\s*([.:;,!?…]+)$/);                         // «Хранятся у вас.» — точка дописана кодом
    if (m) { const t = txOf(m[1], true); if (t != null) return t.replace(/[.:;,!?…]+$/, "") + m[2]; }
    // «3 дела», «0 дел»: число и слово, собранные кодом, — переводим слово; «ноябрь 2026» — тоже
    let nm = k.match(/^([\d][\d\s.,:]*)\s+([А-Яа-яЁё].*)$/);
    if (nm) { const t = txOf(nm[2], true); if (t != null) return nm[1] + " " + t; }
    nm = k.match(/^([А-Яа-яЁё][^:]{1,40}):\s+(.+)$/);                 // «Папка: …» — подпись и значение
    if (nm) { const t = txOf(nm[1] + ":", true) || txOf(nm[1], true); if (t != null) return t.replace(/:?$/, ":") + " " + nm[2]; }
    nm = k.match(/^([А-Яа-яЁё][А-Яа-яЁё ]*?)\s+(\d[\d.,:]*)$/);
    if (nm) { const t = txOf(nm[1], true); if (t != null) return t + " " + nm[2]; }
    // «Чат — с персонажами»: подпись, собранная из двух строк через тире
    const ds = k.split(" — ");
    if (ds.length > 1 && ds.length < 4) {
      const t = ds.map(txSub);
      if (t.every(v => v != null)) return t.join(" — ");
    }
    // текст, склеенный кодом из нескольких строк: «Включите — … Своей модели пока нет: …» — по предложениям,
    // самые длинные куски сначала
    const ss = k.replace(/([.!?…])\s+(?=[А-ЯЁA-Z«“"(])/g, "$1\u0001").split("\u0001");   // без «взгляда назад»: старый Safari его не знает
    if (ss.length > 1 && ss.length < 9 && k.length < 900) {
      const out = [];
      for (let i = 0; i < ss.length;) {
        let hit = null, j = ss.length;
        for (; j > i; j--) { if (j - i === ss.length) continue; hit = txSub(ss.slice(i, j).join(" ")); if (hit != null) break; }
        if (hit == null) return null;
        out.push(hit); i = j;
      }
      return out.join(" ");
    }
    return null;
  }
  const TX_NO = '[translate="no"],.notranslate';
  const TX_SKIP = '[contenteditable=""],[contenteditable="true"],textarea,pre,code,script,style';
  const txSkip = (el) => !!(el && el.closest && el.closest(TX_NO + "," + TX_SKIP));
  function txNode(n) {
    if (n.nodeType === 3) {
      if (n.nodeValue.length > 1500 || !CYR.test(n.nodeValue) || txSkip(n.parentElement)) return;   // длинное — содержимое, не подпись
      const v = txOf(n.nodeValue);
      if (v == null) return;
      let lead = n.nodeValue.match(/^\s*/)[0];
      const tail = n.nodeValue.match(/\s*$/)[0];
      // «…в разделе <a>«Подключение»</a>, и всё…» -> «…in the <a>“Connections”</a> section…»: перевод куска после тега
      // может начаться со слова там, где по-русски была запятая, — нужен пробел
      if (!lead && n.previousSibling && /^[,.;:)»!?]/.test(n.nodeValue.trim()) && /^[\w“"(]/.test(v)) lead = " ";
      txOrig.set(n, n.nodeValue);
      n.nodeValue = lead + v + tail;
      return;
    }
    if (n.nodeType !== 1 || (n.closest && n.closest(TX_NO))) return;
    txEl(n);                                                  // подписи поля ввода — да, его текст — нет
    if (txSkip(n)) return;
    const w = document.createTreeWalker(n, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT, {
      acceptNode: (c) => {
        if (c.nodeType !== 1) return NodeFilter.FILTER_ACCEPT;
        if (c.matches(TX_NO)) return NodeFilter.FILTER_REJECT;
        txEl(c);
        return c.matches(TX_SKIP) ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_SKIP;
      } });
    let c;
    while ((c = w.nextNode())) txNode(c);
  }
  function txEl(el) {
    for (const a of TXA) {
      const v0 = el.getAttribute && el.getAttribute(a);
      if (!v0 || !CYR.test(v0)) continue;
      const v = txOf(v0);
      if (v == null) continue;
      let o = txAttr.get(el);
      if (!o) txAttr.set(el, o = {});
      o[a] = v0;
      el.setAttribute(a, v);
    }
    if (el.tagName === "INPUT" && /^(button|submit|reset)$/i.test(el.type) && CYR.test(el.value)) {
      const v = txOf(el.value);
      if (v != null) { let o = txAttr.get(el); if (!o) txAttr.set(el, o = {}); o.value = el.value; el.value = v; }
    }
  }
  function txRestore(root) {
    const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
    let c;
    while ((c = w.nextNode())) {
      if (c.nodeType === 3) { if (txOrig.has(c)) { c.nodeValue = txOrig.get(c); txOrig.delete(c); } }
      else { const o = txAttr.get(c); if (o) { for (const a in o) { if (a === "value") c.value = o[a]; else c.setAttribute(a, o[a]); } txAttr.delete(c); } }
    }
  }
  function txStart() {
    const root = document.body;
    if (!root) return;
    if (lang === SRC) { if (txObs) { txObs.disconnect(); txObs = null; } txRestore(root); return; }
    if (!window.DW_TX) { txFetch().then(() => { if (lang !== SRC && window.DW_TX) { txFor = ""; txStart(); } }); return; }
    txLoad();
    txNode(root);
    if (document.title && CYR.test(document.title)) { const v = txOf(document.title); if (v != null) document.title = v; }
    if (txObs || !window.MutationObserver) return;
    txObs = new MutationObserver((list) => {
      for (const m of list) {
        if (m.type === "childList") m.addedNodes.forEach(txNode);
        else if (m.type === "characterData") txNode(m.target);
        else if (m.type === "attributes" && m.target.getAttribute) txEl(m.target);
      }
    });
    txObs.observe(root, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: TXA });
  }
  window.dwTx = (s) => { if (lang === SRC) return s; txLoad(); const v = txOf(s); return v == null ? s : v; };
  function setLang(v, sysl) {
    if (LANGS.includes(sysl)) sysLang = sysl;
    const l = pick(v);
    if (l === lang) return lang;
    lang = l; apply(document); txStart();
    try { window.dispatchEvent(new CustomEvent("dw-lang", { detail: { lang } })); } catch (e) { }
    return lang;
  }
  window.t = t;
  window.dwLang = () => lang;
  window.dwLocale = () => (lang === "en" ? "en-US" : lang === "ru" ? "ru-RU" : lang);   // даты и числа — Intl по коду языка
  window.dwLangs = () => LANGS.map(c => ({ code: c, name: (cat(c)["lang.name"]) || c }));
  window.dwSetLang = setLang;
  window.i18nApply = apply;
  const go = () => { apply(document); txStart(); };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", go); else go();
})();
