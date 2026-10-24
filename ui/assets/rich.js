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
  /* Оформление схем (25.10, владелец: «смотрится нечитаемой… сделать более красивую, скруглить углы, небольшая тень…
     должно смотреться красиво и стильно»): своя палитра от цвета оформления вокруг (--acc) вместо жёлто-сиреневой
     по умолчанию, шрифт как у текста, плотнее отступы; блоки скруглены, с мягкой тенью (CSS ниже). */
  const hex = (c) => "#" + c.map(v => Math.round(Math.max(0, Math.min(255, v))).toString(16).padStart(2, "0")).join("");
  const mix = (a, b, k) => a.map((v, i) => v * k + b[i] * (1 - k));
  function rgbOf(el, expr, fb) {
    try {
      const s = document.createElement("span"); s.style.color = expr; s.style.display = "none"; el.appendChild(s);
      const m = getComputedStyle(s).color.match(/[\d.]+/g).map(Number); s.remove();
      if (m.length > 3 && m[3] === 0) return fb;
      return m.slice(0, 3);
    } catch (e) { return fb; }
  }
  function palette(el, dark) {
    const acc = rgbOf(el, "var(--acc, var(--accent, " + (dark ? "#8b8cf7" : "#4f6cf0") + "))", dark ? [139, 140, 247] : [79, 108, 240]);
    const ink = dark ? [234, 237, 245] : [36, 50, 74], bg = dark ? [30, 33, 45] : [255, 255, 255];
    const warm = [224, 137, 79], green = [63, 154, 106];
    const v = {
      darkMode: dark, background: hex(bg), fontFamily: "inherit", fontSize: "14px",
      primaryColor: hex(mix(acc, bg, dark ? 0.22 : 0.09)), primaryBorderColor: hex(mix(acc, bg, dark ? 0.6 : 0.45)), primaryTextColor: hex(ink),
      secondaryColor: hex(mix(warm, bg, dark ? 0.24 : 0.13)), secondaryBorderColor: hex(mix(warm, bg, 0.55)), secondaryTextColor: hex(ink),
      tertiaryColor: hex(mix(green, bg, dark ? 0.22 : 0.1)), tertiaryBorderColor: hex(mix(green, bg, 0.5)), tertiaryTextColor: hex(ink),
      lineColor: hex(mix(ink, bg, dark ? 0.5 : 0.42)), textColor: hex(ink), titleColor: hex(ink),
      mainBkg: hex(mix(acc, bg, dark ? 0.22 : 0.09)), nodeBorder: hex(mix(acc, bg, dark ? 0.6 : 0.45)), nodeTextColor: hex(ink),
      clusterBkg: hex(mix(acc, bg, dark ? 0.08 : 0.035)), clusterBorder: hex(mix(acc, bg, dark ? 0.3 : 0.22)),
      edgeLabelBackground: dark ? "#25283a" : "#f4f7fb",            // как подложка карточки (.dw-diagram) noteBkgColor: hex(mix(warm, bg, dark ? 0.24 : 0.13)), noteBorderColor: hex(mix(warm, bg, 0.55)), noteTextColor: hex(ink),
      actorBkg: hex(mix(acc, bg, dark ? 0.22 : 0.09)), actorBorder: hex(mix(acc, bg, dark ? 0.6 : 0.45)), actorTextColor: hex(ink), actorLineColor: hex(mix(ink, bg, 0.35)),
      signalColor: hex(mix(ink, bg, 0.75)), signalTextColor: hex(ink), labelBoxBkgColor: hex(mix(acc, bg, dark ? 0.22 : 0.09)), labelBoxBorderColor: hex(mix(acc, bg, 0.45)),
      labelTextColor: hex(ink), loopTextColor: hex(ink), activationBkgColor: hex(mix(acc, bg, 0.18)), activationBorderColor: hex(mix(acc, bg, 0.5)),
    };
    return v;
  }
  function load(dark, vars) {
    const want = (dark ? "dark|" : "light|") + (vars ? vars.primaryColor + vars.primaryBorderColor : "");
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
        m.initialize({ startOnLoad: false, securityLevel: "strict", theme: "base", themeVariables: vars, fontFamily: "inherit",
                       flowchart: { htmlLabels: true, curve: "basis", padding: 12, nodeSpacing: 34, rankSpacing: 40, diagramPadding: 6 },
                       sequence: { actorMargin: 40, boxMargin: 8, noteMargin: 8, messageMargin: 30, mirrorActors: false },
                       mindmap: { padding: 12 } });
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
      const host = pre.parentNode || root, dark = darkAt(host), vars = palette(host, dark);
      const key = (dark ? "d:" : "l:") + vars.primaryColor + ":" + src;
      try {
        let svg = cache.get(key);
        if (!svg) {
          const m = await load(dark, vars);
          if (m.parse && (await m.parse(src, { suppressErrors: true })) === false) throw new Error("в схеме ошибка");
          svg = (await m.render("dwmmd" + (++n), src)).svg;
          cache.set(key, svg);
        }
        if (!pre.isConnected) continue;
        const fig = document.createElement("div");
        fig.className = "dw-diagram" + (dark ? " dark" : ""); fig.innerHTML = svg; fig.title = "Схема — двойной щелчок откроет крупно";
        fig.dataset.src = src;
        dress(fig);
        pre.replaceWith(fig);
        done++;
      } catch (e) {
        pre.dataset.mmd = "bad"; pre.title = "Схему не удалось нарисовать: " + (e && e.message || e);
        document.querySelectorAll('[id^="ddwmmd"], [id^="dwmmd"]').forEach(x => { if (!x.closest(".dw-diagram")) x.remove(); });   // мусор неудачной отрисовки
      }
    }
    return done;
  }

  /* Готовая картинка: блоки скруглить; размер — по смыслу: маленькая схема в натуральную величину, большая вписывается в
     ширину, но не мельче ~60 % (иначе текст не прочесть) — дальше листается вбок; «⤢» и двойной щелчок — смотреть крупно. */
  function dress(fig) {
    const svg = fig.querySelector("svg"); if (!svg) return;
    svg.querySelectorAll(".node rect, rect.basic, rect.label-container, .actor, rect.note, rect.labelBox").forEach(r => {
      if (!+r.getAttribute("rx")) { r.setAttribute("rx", 9); r.setAttribute("ry", 9); }
    });
    svg.querySelectorAll(".cluster rect").forEach(r => { r.setAttribute("rx", 12); r.setAttribute("ry", 12); });
    const vb = (svg.getAttribute("viewBox") || "").split(/[\s,]+/).map(Number), W = vb[2] || 0;
    if (W > 0) { svg.style.maxWidth = Math.round(W) + "px"; svg.style.minWidth = Math.round(Math.min(W, W * 0.6)) + "px"; }
    svg.removeAttribute("height");
    if (!fig.querySelector(".dw-zoom")) {
      const b = document.createElement("button");
      b.type = "button"; b.className = "dw-zoom"; b.title = "Смотреть крупно"; b.setAttribute("aria-label", "Смотреть схему крупно");
      b.setAttribute("contenteditable", "false");
      b.innerHTML = '<svg viewBox="0 0 24 24"><path d="M14 4h6v6M10 20H4v-6M20 4l-7 7M4 20l7-7"/></svg>';
      fig.appendChild(b);
    }
  }
  /* Крупный просмотр (владелец 25.10: «и во весь экран может быть даже просмотр»): на всё окно, колёсико и щипок —
     масштаб, перетаскивание — сдвиг, «По размеру», Esc — закрыть. */
  function view(fig) {
    const src = fig.querySelector("svg"); if (!src) return;
    const dark = darkAt(fig.parentNode || document.body);
    const ov = document.createElement("div");
    ov.className = "dw-view" + (dark ? " dark" : ""); ov.setAttribute("role", "dialog"); ov.setAttribute("aria-label", "Схема крупно"); ov.tabIndex = -1;
    ov.innerHTML = '<div class="dw-stage"></div><div class="dw-vbar"><button type="button" data-z="-" aria-label="Мельче">−</button>'
      + '<button type="button" data-z="fit">По размеру</button><button type="button" data-z="+" aria-label="Крупнее">+</button>'
      + '<button type="button" data-z="x" aria-label="Закрыть">✕</button></div>';
    const stage = ov.firstChild, svg = src.cloneNode(true);
    svg.removeAttribute("style"); stage.appendChild(svg);
    const vb = (src.getAttribute("viewBox") || "0 0 400 300").split(/[\s,]+/).map(Number), W = vb[2] || 400, H = vb[3] || 300;
    svg.setAttribute("width", W); svg.setAttribute("height", H);
    document.body.appendChild(ov);
    let k = 1, x = 0, y = 0;
    const put = () => { svg.style.transform = `translate(${x}px, ${y}px) scale(${k})`; };
    const fit = () => {
      const r = ov.getBoundingClientRect();
      k = Math.max(0.2, Math.min((r.width - 48) / W, (r.height - 110) / H, 2.2));
      x = (r.width - W * k) / 2; y = Math.max(24, (r.height - 70 - H * k) / 2); put();
    };
    const zoom = (f, cx, cy) => {
      const r = ov.getBoundingClientRect(); cx = cx == null ? r.width / 2 : cx - r.left; cy = cy == null ? r.height / 2 : cy - r.top;
      const nk = Math.max(0.15, Math.min(6, k * f)); x = cx - (cx - x) * nk / k; y = cy - (cy - y) * nk / k; k = nk; put();
    };
    const close = () => { ov.remove(); document.removeEventListener("keydown", key, true); };
    const key = (e) => {
      if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); close(); }
      else if (e.key === "+" || e.key === "=") zoom(1.2); else if (e.key === "-") zoom(1 / 1.2); else if (e.key === "0") fit();
    };
    document.addEventListener("keydown", key, true);
    ov.querySelector(".dw-vbar").onclick = (e) => {
      const z = e.target.closest("button"); if (!z) return;
      if (z.dataset.z === "x") close(); else if (z.dataset.z === "fit") fit(); else zoom(z.dataset.z === "+" ? 1.25 : 0.8);
    };
    ov.addEventListener("wheel", (e) => { e.preventDefault(); zoom(Math.exp(-e.deltaY * 0.0016), e.clientX, e.clientY); }, { passive: false });
    const pts = new Map(); let last = null, dist = 0, moved = false;
    stage.addEventListener("pointerdown", (e) => { stage.setPointerCapture(e.pointerId); pts.set(e.pointerId, [e.clientX, e.clientY]); last = [e.clientX, e.clientY]; moved = false;
      if (pts.size === 2) { const [a, b] = [...pts.values()]; dist = Math.hypot(a[0] - b[0], a[1] - b[1]); } });
    stage.addEventListener("pointermove", (e) => {
      if (!pts.has(e.pointerId)) return;
      pts.set(e.pointerId, [e.clientX, e.clientY]);
      if (pts.size === 2) {
        const [a, b] = [...pts.values()], d = Math.hypot(a[0] - b[0], a[1] - b[1]);
        if (dist) zoom(d / dist, (a[0] + b[0]) / 2, (a[1] + b[1]) / 2); dist = d; return;
      }
      x += e.clientX - last[0]; y += e.clientY - last[1]; last = [e.clientX, e.clientY]; moved = true; put();
    });
    const up = (e) => { pts.delete(e.pointerId); dist = 0; if (pts.size === 1) last = [...pts.values()][0]; };
    stage.addEventListener("pointerup", up); stage.addEventListener("pointercancel", up);
    stage.addEventListener("click", (e) => { if (!moved && e.target === stage) close(); });
    fit(); ov.focus();
  }
  document.addEventListener("click", (e) => {
    const b = e.target.closest && e.target.closest(".dw-zoom"); if (!b) return;
    e.preventDefault(); e.stopPropagation(); view(b.closest(".dw-diagram"));
  }, true);
  document.addEventListener("dblclick", (e) => {
    const f = e.target.closest && e.target.closest(".dw-diagram"); if (!f || e.target.closest(".dw-zoom")) return;
    if (!f.isConnected || f.closest('[contenteditable="true"]')) return;   // блокнот: двойной щелчок — править текст схемы
    e.preventDefault(); view(f);
  });
  document.addEventListener("mousedown", (e) => { if (e.target.closest && e.target.closest(".dw-zoom")) e.preventDefault(); }, true);

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
  css.textContent = `.dw-diagram{position:relative;overflow-x:auto;margin:10px 0;padding:18px 16px;border-radius:16px;text-align:center;
background:rgba(255,255,255,.55);box-shadow:inset 0 0 0 1px rgba(36,50,74,.08),0 6px 18px -12px rgba(20,30,60,.25);scrollbar-width:thin}
.dw-diagram.dark{background:rgba(255,255,255,.045);box-shadow:inset 0 0 0 1px rgba(255,255,255,.07)}
.dw-diagram .labelBkg{border-radius:6px}
.dw-diagram svg{width:100%;height:auto;display:block;margin:0 auto}
.dw-diagram .node rect,.dw-diagram .node polygon,.dw-diagram .node circle,.dw-diagram .node path.basic,.dw-diagram .actor,.dw-diagram rect.note,
.dw-view .node rect,.dw-view .node polygon,.dw-view .node circle,.dw-view .actor{filter:drop-shadow(0 1.5px 2.5px rgba(20,30,60,.13))}
.dw-zoom{position:absolute;top:8px;right:8px;width:30px;height:30px;border:0;border-radius:9px;display:grid;place-items:center;cursor:pointer;
color:inherit;background:rgba(127,127,127,.14);opacity:.45;transition:opacity .15s}
.dw-zoom svg{width:15px;height:15px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
.dw-diagram:hover .dw-zoom,.dw-zoom:focus-visible{opacity:.85}.dw-zoom:hover{opacity:1;background:rgba(127,127,127,.24)}
@media (hover:none){.dw-zoom{opacity:.7}}
.dw-view{position:fixed;inset:0;z-index:2147483000;background:#eef2f8;color:#24324a;overflow:hidden;border-radius:var(--r,0);outline:none;
animation:dwIn .16s ease-out}.dw-view.dark{background:#161925;color:#eceef4}
@keyframes dwIn{from{opacity:0}}@media (prefers-reduced-motion:reduce){.dw-view{animation:none}}
.dw-stage{position:absolute;inset:0;cursor:grab;touch-action:none}.dw-stage:active{cursor:grabbing}
.dw-stage svg{position:absolute;left:0;top:0;transform-origin:0 0;max-width:none!important}
.dw-vbar{position:absolute;left:50%;bottom:16px;transform:translateX(-50%);display:flex;gap:4px;padding:5px;border-radius:14px;
background:rgba(255,255,255,.86);box-shadow:0 10px 30px -10px rgba(20,30,60,.35),inset 0 0 0 1px rgba(36,50,74,.1);backdrop-filter:blur(10px)}
.dw-view.dark .dw-vbar{background:rgba(38,42,58,.9);box-shadow:0 10px 30px -10px rgba(0,0,0,.6),inset 0 0 0 1px rgba(255,255,255,.08)}
.dw-vbar button{min-width:34px;height:32px;padding:0 10px;border:0;border-radius:10px;background:none;color:inherit;font-family:inherit;font-size:13px;font-weight:600;line-height:1;cursor:pointer}
.dw-vbar button:hover,.dw-vbar button:focus-visible{background:rgba(127,127,127,.16);outline:none}
pre[data-mmd="bad"]{border-left:3px solid rgba(255,143,166,.7)}
.dw-gallery{display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:8px;margin:8px 0 4px}
.dw-pic{display:flex;flex-direction:column;gap:4px;text-decoration:none;color:inherit;border-radius:12px;overflow:hidden;background:rgba(127,127,127,.1)}
.dw-pic img{width:100%;aspect-ratio:4/3;object-fit:cover;display:block;background:rgba(127,127,127,.12)}
.dw-pic span{font-size:11.5px;line-height:1.3;padding:0 8px 7px;opacity:.8;overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}
.dw-credit{grid-column:1/-1;font-size:11px;opacity:.6}`;
  (document.head || document.documentElement).appendChild(css);

  window.DewiarRich = { diagrams, gallery, isDiagram, KW };
})();
