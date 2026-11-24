/* «Читать» — большой ответ по центру экрана (владелец 20.11: «большой вертикальный блок, однородный, читать сложно… кнопочку
   режим чтения — открывается по центру, красиво, удобно, максимально чётко, цветами… листать как странички… размер текста,
   как в текстовом редакторе»). Кнопка — у ответов длиннее CHR_MIN знаков, рядом с «Прослушать». Страницы — все большие ответы
   беседы (← →, стрелки клавиатуры), «2 из 5»; размер текста A−/A+ запоминается. Сплошной текст оживает сам: короткая
   строка без точки в конце или с ней («Слабости и противоречия.») — подзаголовок, «Kafka RF=1 на одном сервере: …» —
   выделенное начало пункта. Разметку модели (##, **, списки) показывает как есть — через тот же md(). */
const CHR_MIN = 600, CHR_SIZES = [15, 16.5, 18, 19.5, 21, 23];
const CHR = { pages: [], i: 0, size: (() => { try { return Math.min(5, Math.max(0, +localStorage.getItem("dw.rd.size") || 2)); } catch (e) { return 2; } })() };

function chrLively(text) {
  /* модель уже разметила (заголовки, списки, жирное) — не трогаем */
  if (/^\s*#{1,4}\s|\*\*[^*]+\*\*|^\s*(?:[-*•]|\d+[.)])\s/m.test(text)) return text;
  return String(text || "").split(/\n{2,}|\n(?=\S)/).map(p => {
    const t = p.trim(); if (!t) return "";
    if (t.length <= 60 && !/[,;]/.test(t) && /^[А-ЯЁA-Z]/.test(t) && !/[?!]$/.test(t) && t.split(/\s+/).length <= 7) return "### " + t.replace(/[.:]$/, "");
    const m = t.match(/^([^.:!?\n]{3,70}?):\s+(.+)$/s);                // «Память: в §8.2 всего…» — начало пункта жирным
    return m && m[1].split(/\s+/).length <= 9 ? `**${m[1]}:** ${m[2]}` : t;
  }).filter(Boolean).join("\n\n");
}
function chrPages() {
  const out = []; let q = "";
  (CH.items || []).forEach(x0 => {
    const x = typeof chatShown === "function" ? chatShown(x0) : x0;
    if (x.role === "user") q = x.text || "";
    else if (x.role === "assistant" && (x.text || "").length >= CHR_MIN) out.push({ id: String(x0.id), q, text: x.text, who: x.who, ts: x.ts });
  });
  return out;
}
function chrOpen(id) {
  CHR.pages = chrPages(); CHR.i = Math.max(0, CHR.pages.findIndex(p => p.id === String(id)));
  if (!CHR.pages.length) return;
  let ov = $("#chr-ov");
  if (!ov) {
    ov = document.createElement("div"); ov.id = "chr-ov"; ov.setAttribute("role", "dialog"); ov.setAttribute("aria-modal", "true");
    ov.innerHTML = `<button class="chr-nav prev" aria-label="Предыдущий ответ">‹</button><article class="chr-card"><header>
      <span class="chr-q"></span><span class="chr-n"></span><span class="chr-size"><button data-d="-1" aria-label="Мельче">A−</button><button data-d="1" aria-label="Крупнее">A+</button></span>
      <button class="chr-x" aria-label="Закрыть">✕</button></header><div class="chr-body md" translate="no"></div></article><button class="chr-nav next" aria-label="Следующий ответ">›</button>`;
    document.body.appendChild(ov);
    ov.addEventListener("click", (e) => {
      if (e.target === ov || e.target.closest(".chr-x")) return chrClose();
      if (e.target.closest(".chr-nav.prev")) return chrGo(-1);
      if (e.target.closest(".chr-nav.next")) return chrGo(1);
      const s = e.target.closest(".chr-size button");
      if (s) { CHR.size = Math.min(CHR_SIZES.length - 1, Math.max(0, CHR.size + +s.dataset.d)); try { localStorage.setItem("dw.rd.size", CHR.size); } catch (er) { } chrShow(false); }
    });
  }
  ov.classList.add("on"); chrShow(true);
}
function chrShow(top) {
  const p = CHR.pages[CHR.i], ov = $("#chr-ov"); if (!p || !ov) return;
  const who = typeof chatWho === "function" ? chatWho(p.who) : null;
  $(".chr-q", ov).textContent = p.q ? (p.q.length > 140 ? p.q.slice(0, 140).trim() + "…" : p.q) : ((who && who.name) || "");
  $(".chr-n", ov).textContent = CHR.pages.length > 1 ? `${CHR.i + 1} из ${CHR.pages.length}` : "";
  const b = $(".chr-body", ov); b.style.fontSize = CHR_SIZES[CHR.size] + "px"; b.innerHTML = md(chrLively(p.text));
  $(".chr-nav.prev", ov).hidden = CHR.i <= 0; $(".chr-nav.next", ov).hidden = CHR.i >= CHR.pages.length - 1;
  if (top) b.scrollTop = 0;
}
function chrGo(d) { const n = CHR.i + d; if (n < 0 || n >= CHR.pages.length) return; CHR.i = n; chrShow(true); }
function chrClose() { const ov = $("#chr-ov"); if (ov) ov.classList.remove("on"); }
document.addEventListener("keydown", (e) => {
  const ov = $("#chr-ov"); if (!ov || !ov.classList.contains("on")) return;
  if (e.key === "Escape") { e.preventDefault(); chrClose(); }
  else if (e.key === "ArrowLeft") { e.preventDefault(); chrGo(-1); }
  else if (e.key === "ArrowRight") { e.preventDefault(); chrGo(1); }
}, true);
document.addEventListener("click", (ev) => {
  const b = ev.target.closest && ev.target.closest(".ch-read"); if (!b) return;
  ev.stopPropagation(); chrOpen(b.dataset.read);
});
