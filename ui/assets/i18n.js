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
  function setLang(v, sysl) {
    if (LANGS.includes(sysl)) sysLang = sysl;
    const l = pick(v);
    if (l === lang) return lang;
    lang = l; apply(document);
    try { window.dispatchEvent(new CustomEvent("dw-lang", { detail: { lang } })); } catch (e) { }
    return lang;
  }
  window.t = t;
  window.dwLang = () => lang;
  window.dwLocale = () => (lang === "en" ? "en-US" : lang === "ru" ? "ru-RU" : lang);   // даты и числа — Intl по коду языка
  window.dwLangs = () => LANGS.map(c => ({ code: c, name: (cat(c)["lang.name"]) || c }));
  window.dwSetLang = setLang;
  window.i18nApply = apply;
  const go = () => apply(document);
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", go); else go();
})();
