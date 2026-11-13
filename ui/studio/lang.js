/* Студия → «Оформление» → «Язык программы» (0.88; владелец 11.11: «нет русского в системе — сразу английский, в
   настройках — переключение»). ui.lang: "auto" (как в системе) | "ru" | "en"; смена — сразу, без перезапуска
   (assets/i18n.js: dwSetLang). Ядро тоже знает язык: ответы Лиры и её подсказки — на нём (core/i18n.py). */
function langSync() {
  const v = (S && S.ui && S.ui.lang) || "auto";
  $$("#lang-seg [data-v]").forEach(b => b.setAttribute("aria-checked", String(b.dataset.v === v)));
  if (window.dwSetLang) dwSetLang(v, window.DW_SYS_LANG);
}
(function langInit() {
  // языки — из словарей (assets/i18n.js: dwLangs): новый data/i18n/<код>.json — и он сам появится здесь, своим именем
  const seg = $("#lang-seg");
  if (seg && window.dwLangs) for (const l of dwLangs()) {
    const b = document.createElement("button"); b.type = "button"; b.setAttribute("role", "radio"); b.dataset.v = l.code;
    b.setAttribute("aria-checked", "false"); b.lang = l.code; b.translate = false; b.textContent = l.name; seg.appendChild(b);   // имя языка — на нём самом
  }
  $$("#lang-seg [data-v]").forEach(b => b.onclick = () => {
    const v = b.dataset.v;
    if (S) S.ui = Object.assign({}, S.ui, { lang: v });
    langSync();
    core.call("settings_save", { patch: { ui: { lang: v } } }).catch(e => toast(e.message));
  });
  core.on("hello", (d) => { if (d && d.sys_lang) window.DW_SYS_LANG = d.sys_lang; setTimeout(langSync, 0); });
  core.on("settings", () => setTimeout(langSync, 0));
  window.addEventListener("dw-lang", () => {
    if (typeof ngApply === "function") ngApply();
    if (typeof hmRender === "function" && $("#p-home.cur")) hmRender();   // приветствие и дата — на новом языке
  });
})();
