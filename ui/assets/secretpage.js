/* Секретная страница сейфа — режим чтения (18.11, владелец: «красивее отображать как страничку, а не сырые данные»;
   на его снимке открытая страница показывала ключ подписи целиком). Один код для студии (ui/studio/vault.js) и телефона
   (android safe.js, копия — android/tools/www_assemble.sh): текст страницы остаётся обычным текстом, а читается как документ.

   Что узнаётся (текст не меняется, только показ):
   - «# Заголовок», «## …» и короткая строка, кончающаяся двоеточием, — заголовок раздела;
   - «- пункт», «* …», «• …», «1. …» — список;
   - «Название: значение» (также « = », « — ») — ряд: подпись слева, значение и «Скопировать»;
   - ```блок``` и JSON ({ … } с новой строки) — блок кода с кнопкой «Скопировать»;
   - ссылки http(s) — открываются; `код` — моноширинным.
   Секреты скрыты точками, пока не нажмёшь (15 с): значение у подписи «пароль», «token», «ключ», «sk»… и любая длинная
   «случайная» строка без пробелов (ключи API, токены). Имена файлов, адреса и пути — не секреты.

   SecretPage.render(text) -> { html, secrets }; SecretPage.bind(root, secrets, { copy(text, what), open(url) }). */
(function () {
  const SHOW_MS = 15000;
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const SECRET_KEY = /(парол|pass|pwd|\bpin\b|пин|(?:^|[^а-яё])код(?![а-яё])|token|токен|ключ|\bkey\b|api.?key|secret|секрет|^sk$|^private|приватн|seed|мнемон|фраз|cvv|cvc)/i;
  const PHRASE_KEY = /(seed|мнемон|фраз|passphrase)/i;               // у таких секрет — несколько слов через пробел
  const FILE_RX = /\.(json|txt|pdf|zip|png|jpe?g|gif|webp|md|py|js|ts|php|sh|pem|pub|key|crt|conf|ya?ml|toml|csv|xlsx?|docx?|dwr)$/i;

  /* «случайная» строка: без пробелов, не ссылка, не почта, не путь, не имя файла; буквы и цифры вперемешку, разнообразная */
  function looksSecret(w) {
    w = String(w || "");
    if (w.length < 20 || /\s/.test(w) || /:\/\//.test(w) || /^www\./i.test(w) || /^[^@\s]+@[^@\s]+\.[a-z]{2,}$/i.test(w)) return false;
    if (/^[~.]?\//.test(w) || FILE_RX.test(w) || /^\d[\d.:-]*$/.test(w)) return false;
    if (!/[A-Za-z]/.test(w) || !/\d/.test(w)) return false;
    const n = {}; for (const c of w) n[c] = (n[c] || 0) + 1;
    let h = 0; for (const c in n) { const p = n[c] / w.length; h -= p * Math.log2(p); }
    return h >= 3.6;
  }

  const ICON = {
    eye: '<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="2.8"/>',
    copy: '<rect x="8.5" y="8.5" width="11" height="11" rx="2.5"/><path d="M15.5 8.5V6.5a2 2 0 0 0-2-2h-7a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h2"/>',
  };
  const svg = (k) => `<svg viewBox="0 0 24 24" aria-hidden="true">${ICON[k]}</svg>`;

  function render(text) {
    const secrets = [];
    const dots = (v) => "•".repeat(Math.min(14, Math.max(8, Math.round(String(v).length / 3))));
    const sec = (v, what) => { secrets.push(v); const i = secrets.length - 1;
      return `<span class="sp-sec"><button type="button" class="sp-dots" data-show="${i}" aria-label="Показать: ${esc(what)} (скрыто)">${dots(v)}</button>`
        + `<button type="button" class="sp-ib" data-copy="${i}" data-what="${esc(what)}" aria-label="Скопировать: ${esc(what)}">${svg("copy")}</button></span>`; };
    const copyBtn = (v, what) => { secrets.push(v); return `<button type="button" class="sp-ib" data-copy="${secrets.length - 1}" data-what="${esc(what)}" aria-label="Скопировать: ${esc(what)}">${svg("copy")}</button>`; };
    /* строка текста: `код`, ссылки, длинные «случайные» строки — точками */
    const inline = (s) => String(s).split(/(`[^`]+`|\s+)/).map((p) => {
      if (!p) return "";
      if (/^\s+$/.test(p)) return p;
      if (/^`[^`]+`$/.test(p)) { const c = p.slice(1, -1); return looksSecret(c) ? sec(c, "секрет") : `<code>${esc(c)}</code>`; }
      const m = /^([("'«]*)(.*?)([)"'».,;:!?]*)$/.exec(p), core = m ? m[2] : p, pre = m ? m[1] : "", post = m ? m[3] : "";
      if (/^https?:\/\/\S+$/i.test(core)) return esc(pre) + `<a href="#" class="sp-a" data-url="${esc(core)}">${esc(core.replace(/^https?:\/\//i, "").replace(/\/$/, ""))}</a>` + esc(post);
      if (looksSecret(core)) return esc(pre) + sec(core, "секрет") + esc(post);
      return esc(p);
    }).join("");
    /* блок кода: строки целиком, строковые значения-секреты внутри — точками */
    const codeBlock = (lines) => {
      const raw = lines.join("\n");
      const body = lines.map((ln) => {
        const kv = /^(\s*"([^"]{1,40})"\s*:\s*)"(.*)"(,?)\s*$/.exec(ln);
        if (kv && (SECRET_KEY.test(kv[2]) && kv[3] && !/\s/.test(kv[3]) || looksSecret(kv[3]))) return esc(kv[1]) + '"' + sec(kv[3], kv[2]) + '"' + esc(kv[4]);
        return ln.split(/("[^"]*")/).map((p) => /^"[^"]*"$/.test(p) && looksSecret(p.slice(1, -1)) ? '"' + sec(p.slice(1, -1), "секрет") + '"' : esc(p)).join("");
      }).join("\n");
      return `<div class="sp-code"><pre>${body}</pre>${copyBtn(raw, "блок")}</div>`;
    };
    const out = [], src = String(text || "").replace(/\r\n?/g, "\n").split("\n");
    let list = null, para = [];
    const flushList = () => { if (list) { out.push(`<ul class="sp-ul">${list.join("")}</ul>`); list = null; } };
    const flushPara = () => { if (para.length) { out.push(`<p class="sp-p">${para.map(inline).join("<br>")}</p>`); para = []; } };
    const flush = () => { flushList(); flushPara(); };
    /* «Подпись: значение» -> ряд; null — не ряд */
    const row = (ln) => {
      const m = /^\s*([^:=—–\n]{1,40}?)\s*(?::|\s=|\s[—–])\s+(\S.*)$/.exec(ln);
      if (!m || /https?$/i.test(m[1]) || m[1].split(/\s+/).length > 5) return null;
      const k = m[1].trim(), v = m[2].trim();
      const hidden = SECRET_KEY.test(k) && (!/\s/.test(v) || PHRASE_KEY.test(k)) || looksSecret(v);
      const mono = !/\s/.test(v) || /^(ssh|scp|sudo|curl|git|docker|mysql|psql)\s/i.test(v);   // логин, адрес, команда — моноширинным; фраза — обычным
      return `<div class="sp-kv"><span class="sp-k">${inline(k)}</span><span class="sp-v">${hidden ? sec(v, k) : `<span class="sp-t${mono ? " mono" : ""}">${inline(v)}</span>${copyBtn(v, k)}`}</span></div>`;
    };
    for (let i = 0; i < src.length; i++) {
      const ln = src[i], t = ln.trim();
      if (/^```/.test(t)) {                                  // ```блок```
        flush(); const buf = [];
        for (i++; i < src.length && !/^```/.test(src[i].trim()); i++) buf.push(src[i]);
        out.push(codeBlock(buf)); continue;
      }
      if (t === "{" || t === "[") {                         // JSON с новой строки — до закрывающей скобки на том же отступе
        const ind = ln.length - ln.trimStart().length, close = t === "{" ? "}" : "]", buf = [ln];
        let j = i + 1;
        for (; j < src.length; j++) { buf.push(src[j]); const tt = src[j].trim();
          if ((tt === close || tt === close + ",") && src[j].length - src[j].trimStart().length <= ind) break; }
        if (j < src.length) { flush(); out.push(codeBlock(buf)); i = j; continue; }
      }
      if (!t) { flush(); continue; }
      let m = /^(#{1,3})\s+(.+)$/.exec(t);
      if (m) { flush(); out.push(`<h4 class="sp-h${m[1].length > 1 ? " sub" : ""}">${inline(m[2])}</h4>`); continue; }
      if (/^[^:]{1,60}:$/.test(t) && !/https?:$/i.test(t)) { flush(); out.push(`<h4 class="sp-h sub">${inline(t.slice(0, -1))}</h4>`); continue; }
      m = /^(?:[-*•]|\d{1,2}[.)])\s+(.+)$/.exec(t);
      if (m) { flushPara(); (list = list || []).push(`<li>${row(m[1]) || inline(m[1])}</li>`); continue; }
      const r = row(t);
      if (r) { flush(); out.push(r); continue; }
      flushList(); para.push(t);
    }
    flush();
    for (let i = 0; i < out.length; i++) {                 // подряд идущие ряды — одной группой с тонкими разделителями
      if (!out[i].startsWith('<div class="sp-kv">')) continue;
      let j = i; while (j + 1 < out.length && out[j + 1].startsWith('<div class="sp-kv">')) j++;
      out.splice(i, j - i + 1, `<div class="sp-kvs">${out.slice(i, j + 1).join("")}</div>`);
    }
    return { html: `<div class="sp">${out.join("") || '<p class="sp-p sp-empty">Страница пустая</p>'}</div>`, secrets };
  }

  function bind(root, secrets, hooks) {
    hooks = hooks || {};
    root.querySelectorAll("[data-show]").forEach((b) => {
      const v = secrets[+b.dataset.show], dots = b.textContent, label = b.getAttribute("aria-label");
      const hide = () => { clearTimeout(b._t); b.textContent = dots; b.classList.remove("on"); b.setAttribute("aria-label", label); };
      b.onclick = (e) => { e.preventDefault(); e.stopPropagation();
        if (b.classList.contains("on")) return hide();
        b.textContent = v; b.classList.add("on"); b.setAttribute("aria-label", label.replace(" (скрыто)", " (показано)"));
        clearTimeout(b._t); b._t = setTimeout(hide, SHOW_MS); };
    });
    root.querySelectorAll("[data-copy]").forEach((b) => b.onclick = (e) => { e.preventDefault(); e.stopPropagation();
      if (hooks.copy) hooks.copy(secrets[+b.dataset.copy], b.dataset.what || "");
      b.classList.add("done"); setTimeout(() => b.classList.remove("done"), 1200); });
    root.querySelectorAll(".sp-a").forEach((a) => a.onclick = (e) => { e.preventDefault(); e.stopPropagation(); if (hooks.open) hooks.open(a.dataset.url); });
  }

  /* оформление — здесь же, одно на студию и телефон; цвета — от окружающего текста (обе темы) */
  const CSS = `
.sp { font-size: 15px; line-height: 1.6; max-width: 72ch; overflow-wrap: anywhere; }
.sp > * + * { margin-top: 10px; }
.sp-h { margin: 18px 0 2px; font-size: 16px; font-weight: 700; letter-spacing: .005em; }
.sp-h.sub { font-size: 14.5px; }
.sp > .sp-h:first-child { margin-top: 0; }
.sp-p { margin: 0; }
.sp-empty { opacity: .6; }
.sp-ul { margin: 0; padding-left: 20px; } .sp-ul li + li { margin-top: 4px; } .sp-ul li::marker { color: currentColor; opacity: .45; }
.sp-kvs { border-radius: 14px; background: rgba(127,127,160,.09); padding: 2px 14px; }
.sp-kv { display: grid; grid-template-columns: minmax(96px, 26%) 1fr; gap: 2px 18px; align-items: center; min-height: 40px; padding: 5px 0; }
.sp-kv + .sp-kv { border-top: 1px solid rgba(127,127,160,.16); }
.sp-ul .sp-kv { display: flex; flex-wrap: wrap; gap: 4px 10px; min-height: 0; padding: 0; }
.sp-k { font-size: 13px; opacity: .62; }
.sp-v { display: flex; align-items: center; gap: 6px; min-width: 0; }
.sp-t { min-width: 0; }
.sp-t.mono { font-family: "JetBrains Mono", ui-monospace, Menlo, monospace; font-size: 13.5px; }
.sp code, .sp-dots { font-family: "JetBrains Mono", ui-monospace, Menlo, monospace; font-size: 13px; }
.sp code { padding: 1px 6px; border-radius: 6px; background: rgba(127,127,160,.14); }
.sp-a { color: inherit; text-decoration: underline; text-decoration-color: rgba(127,127,160,.6); text-underline-offset: 3px; }
.sp-sec { display: inline-flex; align-items: center; gap: 4px; vertical-align: middle; max-width: 100%; }
.sp-dots { border: 0; font-family: "JetBrains Mono", ui-monospace, monospace; color: inherit; cursor: pointer; padding: 2px 8px; border-radius: 8px; letter-spacing: .08em;
  background: rgba(127,127,160,.16); text-align: left; overflow-wrap: anywhere; max-width: 100%; }
.sp-dots.on { letter-spacing: 0; user-select: text; -webkit-user-select: text; }
.sp-dots:focus-visible, .sp-ib:focus-visible, .sp-a:focus-visible { outline: 2px solid currentColor; outline-offset: 2px; }
.sp-ib { flex: none; width: 28px; height: 28px; display: inline-grid; place-items: center; border: 0; border-radius: 8px; background: none; color: inherit; cursor: pointer; opacity: .55; }
.sp-ib:hover { opacity: 1; background: rgba(127,127,160,.16); } .sp-ib.done { opacity: 1; color: #2fae74; }
.sp-ib svg { width: 16px; height: 16px; fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
.sp-code { position: relative; border-radius: 14px; background: rgba(127,127,160,.1); }
.sp-code pre { margin: 0; padding: 12px 44px 12px 14px; font: 12.5px/1.6 "JetBrains Mono", ui-monospace, Menlo, monospace; white-space: pre-wrap; overflow-wrap: anywhere; }
.sp-code > .sp-ib { position: absolute; top: 6px; right: 6px; }
@media (max-width: 520px) { .sp-kv { grid-template-columns: 1fr; padding: 8px 0; } }
@media (hover: hover) { .sp-kv .sp-ib { opacity: 0; } .sp-kv:hover .sp-ib, .sp-kv .sp-ib:focus-visible, .sp-ib.done { opacity: .55; } .sp-kv .sp-ib:hover { opacity: 1; } }`;
  if (typeof document !== "undefined" && !document.getElementById("sp-css")) {
    const st = document.createElement("style"); st.id = "sp-css"; st.textContent = CSS; (document.head || document.documentElement).appendChild(st);
  }
  const api = { render, bind, looksSecret };
  if (typeof window !== "undefined") window.SecretPage = api;
  if (typeof module !== "undefined") module.exports = api;
})();
