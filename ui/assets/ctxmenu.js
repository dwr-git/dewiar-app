/* Своё меню правой кнопки: «Копировать», «Вырезать», «Вставить», «Выделить всё» (идея №112, 02.11: «в чате отключено
   контекстное меню для копирования, Ctrl+C неудобно»). Окна pywebview без отладки прячут меню WebView2/WebKit — здесь своё,
   только там, где есть что копировать или куда вставить; в остальных местах — ничего (как было). Окно может само решить,
   что делать с правой кнопкой (событие отменено раньше), — тогда не вмешиваемся. Тема — от страницы (--ink, --accent). */
(function () {
  let menu = null, css = false;
  function style() {
    if (css) return; css = true;
    const s = document.createElement("style");
    s.textContent = `
      .dwcm { position: fixed; z-index: 10000; min-width: 168px; padding: 5px; border-radius: 12px; color: var(--ink, #ECEEF4);
        background: var(--dwcm-bg, #1d1f2b); box-shadow: 0 16px 40px -12px rgba(0,0,0,.55), 0 0 0 1px rgba(255,255,255,.07);
        font: 13.5px/1.2 "Manrope", "Ubuntu", "Segoe UI", sans-serif; }
      .dwcm button { display: flex; justify-content: space-between; gap: 18px; width: 100%; padding: 8px 10px; border: 0; border-radius: 8px;
        background: transparent; color: inherit; font: inherit; text-align: left; cursor: pointer; }
      .dwcm button:hover, .dwcm button:focus-visible { outline: none; background: color-mix(in srgb, var(--accent, #8B8CF7) 22%, transparent); }
      .dwcm button[disabled] { opacity: .4; cursor: default; background: transparent; }
      .dwcm kbd { font: inherit; opacity: .5; }
      html.st-light .dwcm, body.light .dwcm { --dwcm-bg: #f7f9fd; color: var(--ink, #24324a); box-shadow: 0 16px 40px -12px rgba(20,32,60,.3), 0 0 0 1px rgba(20,32,60,.08); }`;
    document.head.appendChild(s);
  }
  const close = () => { if (menu) { menu.remove(); menu = null; } };
  const editable = (el) => el && (el.isContentEditable || (el.tagName === "TEXTAREA") || (el.tagName === "INPUT" && /^(text|search|email|url|tel|number|password|)$/i.test(el.type || "")));
  function selText(el) {
    if (el && (el.tagName === "TEXTAREA" || el.tagName === "INPUT")) {
      try { return el.value.slice(el.selectionStart, el.selectionEnd); } catch (e) { return ""; }
    }
    return String(getSelection() || "");
  }
  async function paste(el) {
    let t = "";
    try { t = await navigator.clipboard.readText(); } catch (e) { document.execCommand("paste"); return; }
    el.focus();
    if (!document.execCommand("insertText", false, t) && "value" in el) {
      const a = el.selectionStart, b = el.selectionEnd; el.value = el.value.slice(0, a) + t + el.value.slice(b);
      el.selectionStart = el.selectionEnd = a + t.length; el.dispatchEvent(new Event("input", { bubbles: true }));
    }
  }
  function copy(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).catch(() => document.execCommand("copy"));
    else document.execCommand("copy");
  }
  document.addEventListener("contextmenu", (e) => {
    if (e.defaultPrevented) return;
    const el = e.target.closest ? e.target.closest("input, textarea, [contenteditable=''], [contenteditable='true']") : null;
    const ed = editable(el) && !(el.readOnly || el.disabled), text = selText(el);
    if (!ed && !text) return;                                    // ни выделения, ни поля — меню не нужно
    e.preventDefault(); close(); style();
    menu = document.createElement("div"); menu.className = "dwcm"; menu.setAttribute("role", "menu");
    const mac = /Mac/.test(navigator.platform), k = (x) => `<kbd>${mac ? "⌘" : "Ctrl+"}${x}</kbd>`;
    const items = [
      ["Копировать", "C", !text, () => copy(text)],
      ...(ed ? [["Вырезать", "X", !text, () => { copy(text); el.focus(); document.execCommand("delete"); }],
                ["Вставить", "V", false, () => paste(el)]] : []),
      ["Выделить всё", "A", false, () => { if (el && "select" in el) { el.focus(); el.select(); } else getSelection().selectAllChildren(e.target.closest("p, li, div, section") || document.body); }],
    ];
    items.forEach(([t, key, off, fn]) => {
      const b = document.createElement("button"); b.type = "button"; b.setAttribute("role", "menuitem"); b.disabled = off;
      b.innerHTML = `<span>${t}</span>${k(key)}`; b.onmousedown = (ev) => ev.preventDefault();   // выделение не сбрасываем
      b.onclick = () => { close(); fn(); }; menu.appendChild(b);
    });
    document.body.appendChild(menu);
    const r = menu.getBoundingClientRect();
    menu.style.left = Math.max(4, Math.min(e.clientX, innerWidth - r.width - 4)) + "px";
    menu.style.top = Math.max(4, Math.min(e.clientY, innerHeight - r.height - 4)) + "px";
  });
  document.addEventListener("mousedown", (e) => { if (menu && !menu.contains(e.target)) close(); }, true);
  document.addEventListener("keydown", (e) => { if (menu && e.key === "Escape") { e.preventDefault(); close(); } }, true);
  addEventListener("blur", close); addEventListener("resize", close); document.addEventListener("scroll", close, true);
})();
