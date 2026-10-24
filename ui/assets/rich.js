/* Богатые ответы — диаграммы и картинки в тексте ответа; один файл для виджета («Открыть целиком»), «Чата» студии и
   телефона (просьба 14.10: «может ли она показывать диаграммы, типа mermaid?», «пусть подтягивает изображения, о которых
   рассказывает»).
   Диаграммы: модель пишет ```mermaid … ```; любой наш Markdown превращает это в <pre><code>…</code></pre> — здесь такие
   блоки узнаются по первой строке (graph, flowchart, sequenceDiagram, mindmap…) и заменяются картинкой. Mermaid
   (vendor/mermaid.min.js, ~2,7 МБ, лицензия MIT) грузится только при первой диаграмме; готовые картинки кешируются по
   тексту, поэтому поток ответа их не перерисовывает. Не нарисовалось — остаётся текст схемы с подсказкой.
   Картинки: gallery(items) — HTML ленты миниатюр с подписью и ссылкой на источник (show_images: поисковик картинок,
   запасной — Wikimedia Commons). Миниатюра не загрузилась — убирается. */
(function () {
  const BASE = (() => { try { const s = document.currentScript && document.currentScript.src; return s ? s.replace(/[^/]*$/, "") : ""; } catch (e) { return ""; } })();
  const SRC = window.DEWIAR_MERMAID_SRC || BASE + "vendor/mermaid.min.js";
  const KW = /^\s*(?:%%[^\n]*\n\s*)*(?:graph|flowchart|sequenceDiagram|classDiagram|stateDiagram(?:-v2)?|erDiagram|gantt|pie|journey|gitGraph|mindmap|timeline|quadrantChart|xychart-beta|block-beta|sankey-beta|requirementDiagram|C4Context)\b/;
  const cache = new Map();
  let loading = null, n = 0, theme = "";
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  function darkAt(el) {                       // светлый текст вокруг — тёмная тема схемы
    try {
      const m = getComputedStyle(el).color.match(/\d+(\.\d+)?/g).map(Number);
      return (0.2126 * m[0] + 0.7152 * m[1] + 0.0722 * m[2]) / 255 > 0.5;
    } catch (e) { return true; }
  }
  function load(dark) {
    const want = dark ? "dark" : "default";
    if (!loading) {
      loading = new Promise((ok, bad) => {
        if (window.mermaid) return ok(window.mermaid);
        const s = document.createElement("script"); s.src = SRC; s.async = true;
        s.onload = () => (window.mermaid ? ok(window.mermaid) : bad(new Error("mermaid не загрузился")));
        s.onerror = () => bad(new Error("нет файла " + SRC));
        document.head.appendChild(s);
      });
    }
    return loading.then(m => {
      if (theme !== want) {
        theme = want;
        m.initialize({ startOnLoad: false, securityLevel: "strict", theme: want, fontFamily: "inherit",
                       flowchart: { htmlLabels: true, curve: "basis" }, mindmap: { padding: 12 } });
      }
      return m;
    });
  }
  function source(pre) {
    const code = pre.querySelector("code") || pre;
    let t = code.textContent || "";
    const lang = /language-mermaid|lang-mermaid|\bmermaid\b/.test(code.className || "") || pre.getAttribute("data-lang") === "mermaid";
    if (/^\s*mermaid\s*\n/.test(t)) t = t.replace(/^\s*mermaid\s*\n/, "");   // Markdown оставил имя языка в тексте
    return (lang || KW.test(t)) ? t.trim() : "";
  }
  function isDiagram(text) { return KW.test(String(text || "").replace(/^\s*mermaid\s*\n/, "")); }

  /** Заменить схемы Mermaid внутри root картинками. -> Promise (сколько нарисовано). */
  async function diagrams(root) {
    if (!root) return 0;
    let done = 0;
    for (const pre of [...root.querySelectorAll("pre")]) {
      if (pre.dataset.mmd) continue;
      const src = source(pre);
      if (!src) continue;
      pre.dataset.mmd = "wait";
      const dark = darkAt(pre.parentNode || root), key = (dark ? "d:" : "l:") + src;
      try {
        let svg = cache.get(key);
        if (!svg) {
          const m = await load(dark);
          if (m.parse && (await m.parse(src, { suppressErrors: true })) === false) throw new Error("в схеме ошибка");
          svg = (await m.render("dwmmd" + (++n), src)).svg;
          cache.set(key, svg);
        }
        if (!pre.isConnected) continue;
        const fig = document.createElement("div");
        fig.className = "dw-diagram"; fig.innerHTML = svg; fig.title = "Схема";
        fig.dataset.src = src;
        pre.replaceWith(fig);
        done++;
      } catch (e) {
        pre.dataset.mmd = "bad"; pre.title = "Схему не удалось нарисовать: " + (e && e.message || e);
        document.querySelectorAll('[id^="ddwmmd"], [id^="dwmmd"]').forEach(x => { if (!x.closest(".dw-diagram")) x.remove(); });   // мусор неудачной отрисовки
      }
    }
    return done;
  }

  const isCommons = (x) => x.source ? x.source === "commons" : /commons\.wikimedia\.org/.test(x.page || "");
  const siteOf = (x) => x.site || (() => { try { return new URL(x.page || x.full || x.src).hostname.replace(/^www\./, ""); } catch (e) { return ""; } })();
  function credit(list) {
    if (list.every(isCommons))
      return "Картинки: Wikimedia Commons" + (list.some(x => x.license) ? " · " + [...new Set(list.map(x => x.license).filter(Boolean))].slice(0, 3).join(", ") : "");
    const sites = [...new Set(list.map(siteOf).filter(Boolean))].slice(0, 3);
    return "Картинки из поиска" + (sites.length ? " · " + sites.join(", ") : "") + " — нажмите, чтобы открыть";
  }
  /** Лента картинок: [{src, full, page, title, author, license, site, source}] -> HTML (миниатюра — ссылка на источник). */
  function gallery(items, opts) {
    const list = (items || []).filter(x => x && x.src).slice(0, (opts && opts.max) || 6);
    if (!list.length) return "";
    return `<div class="dw-gallery">${list.map(x => `<a class="dw-pic" href="${esc(x.page || x.full || x.src)}" target="_blank" rel="noopener" data-full="${esc(x.full || x.src)}" data-src="${esc(x.src)}" title="${esc(x.title || "")}${x.author ? " — " + esc(x.author) : siteOf(x) ? " — " + esc(siteOf(x)) : ""}">`
      + `<img src="${esc(x.src)}" alt="${esc(x.title || "картинка")}" loading="lazy" referrerpolicy="no-referrer" onerror="this.parentNode.remove()"><span>${esc(x.title || "")}</span></a>`).join("")}`
      + `<small class="dw-credit">${esc(credit(list))}</small></div>`;
  }

  const css = document.createElement("style");
  css.textContent = `.dw-diagram{overflow-x:auto;margin:8px 0;padding:12px;border-radius:12px;background:rgba(127,127,127,.08);text-align:center}
.dw-diagram svg{max-width:100%;height:auto}
pre[data-mmd="bad"]{border-left:3px solid rgba(255,143,166,.7)}
.dw-gallery{display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:8px;margin:8px 0 4px}
.dw-pic{display:flex;flex-direction:column;gap:4px;text-decoration:none;color:inherit;border-radius:12px;overflow:hidden;background:rgba(127,127,127,.1)}
.dw-pic img{width:100%;aspect-ratio:4/3;object-fit:cover;display:block;background:rgba(127,127,127,.12)}
.dw-pic span{font-size:11.5px;line-height:1.3;padding:0 8px 7px;opacity:.8;overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}
.dw-credit{grid-column:1/-1;font-size:11px;opacity:.6}`;
  (document.head || document.documentElement).appendChild(css);

  window.DewiarRich = { diagrams, gallery, isDiagram, KW };
})();
