/* Свои окна вопроса вместо confirm()/prompt() браузера (21.10, Ubuntu: «окно выглядит пугающе» — системное окно WebKit
   с заголовком «JavaScript — file:///…?token=…»: и некрасиво, и показывает адрес страницы с ключом связи).
   ask(text, opts) -> Promise<bool>; askText(label, value, opts) -> Promise<string|null>. Кнопка подтверждения
   называется действием («Удалить», «Выключить»…), опасное — красным; Enter — да, Esc и щелчок мимо — нет.
   Тема — от страницы: переменные --ink, --muted, --glass… (студия, блокнот); своя запасная палитра — если их нет. */
(function () {
  const VERB = /^(Удалить|Убрать|Очистить|Выключить|Отключить|Сбросить|Отклонить|Выйти|Восстановить|Принять|Сделать|Вернуть|Перейти)/;
  const DANGER = /^(Удалить|Убрать|Очистить|Выключить|Отключить|Сбросить|Отклонить)/;
  let css = false;
  function style() {
    if (css) return; css = true;
    const s = document.createElement("style");
    s.textContent = `
      .dwq-back { position: fixed; inset: 0; z-index: 9999; display: grid; place-items: center; padding: 20px;
        background: rgba(10,12,20,.32); -webkit-backdrop-filter: blur(3px); backdrop-filter: blur(3px); opacity: 0; transition: opacity .15s; }
      .dwq-back.on { opacity: 1; }
      dialog.dwq-back { width: 100%; height: 100%; max-width: none; max-height: none; margin: 0; border: 0; color: inherit; }
      dialog.dwq-back::backdrop { background: transparent; }
      .dwq { width: min(420px, 100%); border-radius: 20px; padding: 20px 20px 16px; color: var(--ink, #ECEEF4);
        background: var(--dwq-bg, #1b1c27); box-shadow: 0 24px 60px -20px rgba(0,0,0,.55), 0 0 0 1px rgba(255,255,255,.06);
        font: 14.5px/1.5 "Manrope", "Ubuntu", "Segoe UI", sans-serif; transform: translateY(6px) scale(.985); transition: transform .18s cubic-bezier(.2,.8,.2,1); }
      .dwq-back.on .dwq { transform: none; }
      .dwq p { margin: 0 0 16px; white-space: pre-line; }
      .dwq input { width: 100%; margin: 0 0 16px; padding: 10px 12px; border-radius: 12px; border: 0; outline: none; font: inherit;
        color: inherit; background: rgba(127,127,127,.14); }
      .dwq input:focus { box-shadow: 0 0 0 2px var(--accent, #8B8CF7); }
      .dwq .row { display: flex; gap: 8px; justify-content: flex-end; }
      .dwq button { font: 600 14px/1 inherit; font-family: inherit; padding: 10px 16px; border-radius: 12px; border: 0; cursor: pointer;
        color: inherit; background: rgba(127,127,127,.14); }
      .dwq button:hover { background: rgba(127,127,127,.22); }
      .dwq button.yes { color: #fff; background: var(--accent, #6a7cf0); }
      .dwq button.yes.danger { background: #E5484D; }
      .dwq button:focus-visible { outline: 2px solid var(--accent, #8B8CF7); outline-offset: 2px; }
      body.light .dwq, .st-light .dwq, html.st-light .dwq { --dwq-bg: #f4f7fc; color: var(--ink, #24324a); box-shadow: 0 24px 60px -20px rgba(20,32,60,.35), 0 0 0 1px rgba(20,32,60,.06); }
      @media (prefers-reduced-motion: reduce) { .dwq-back, .dwq { transition: none; } }`;
    document.head.appendChild(s);
  }
  function open(text, opts, input) {
    if (window.DEWIAR_AUTO_ASK) return Promise.resolve(input ? (window.DEWIAR_AUTO_ASK === true ? input.value : window.DEWIAR_AUTO_ASK) : true);  // проверки (tests/)
    style();
    return new Promise((resolve) => {
      /* 30.10 (владелец: «Удалить все повторы» в календаре только затемняет экран — окошко вопроса под окном дня): окно дня —
         <dialog> в верхнем слое, его не перекрыть z-index. Если открыто такое окно — вопрос тоже <dialog>, showModal кладёт его поверх. */
      const top = typeof HTMLDialogElement === "function" && document.querySelector("dialog[open]");
      const back = document.createElement(top ? "dialog" : "div"); back.className = "dwq-back";
      const box = document.createElement("div"); box.className = "dwq"; box.setAttribute("role", "dialog"); box.setAttribute("aria-modal", "true");
      const p = document.createElement("p"); p.textContent = text; box.appendChild(p);
      let inp = null;
      if (input) { inp = document.createElement("input"); inp.value = input.value || ""; inp.spellcheck = false; if (opts && opts.ph) inp.placeholder = opts.ph; box.appendChild(inp); }
      const verb = (opts && opts.ok) || (String(text).match(VERB) || [])[1] || (input ? "Готово" : "Да");
      const row = document.createElement("div"); row.className = "row";
      const no = document.createElement("button"); no.textContent = (opts && opts.cancel) || "Отмена";
      const yes = document.createElement("button"); yes.textContent = verb; yes.className = "yes" + ((opts && opts.danger) ?? DANGER.test(verb) ? " danger" : "");
      if (opts && opts.only) no.style.display = "none";
      row.append(no, yes); box.appendChild(row); back.appendChild(box); document.body.appendChild(back);
      const prev = document.activeElement;
      if (top) { try { back.showModal(); } catch (e) { back.setAttribute("open", ""); } back.addEventListener("cancel", (e) => { e.preventDefault(); done(input ? null : false); }); }
      let fin = false;
      const done = (v) => { if (fin) return; fin = true; back.classList.remove("on"); document.removeEventListener("keydown", key, true);
        setTimeout(() => { if (top && back.open) { try { back.close(); } catch (e) { } } back.remove(); }, 160);
        try { prev && prev.focus && prev.focus(); } catch (e) { } resolve(v); };
      const key = (e) => { if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); done(input ? null : false); }
        else if (e.key === "Enter" && (!inp || document.activeElement === inp || document.activeElement === yes)) { e.preventDefault(); e.stopPropagation(); done(input ? inp.value : true); } };
      document.addEventListener("keydown", key, true);
      no.onclick = () => done(input ? null : false);
      yes.onclick = () => done(input ? inp.value : true);
      back.onmousedown = (e) => { if (e.target === back) done(input ? null : false); };
      requestAnimationFrame(() => { back.classList.add("on"); (inp || yes).focus(); if (inp) inp.select(); });
    });
  }
  window.ask = (text, opts) => open(text, opts, null);
  window.askText = (label, value, opts) => open(label, opts, { value });
  window.tell = (text) => open(text, { only: true, ok: "Понятно" }, null);
})();
