/* Markdown ⇄ HTML для блокнота у виджета (ui/pad.html): вкладка хранится как обычный Markdown (её читают Obsidian,
   телефон и синхронизация), а правится сразу «как выглядит» — без режима просмотра.
   Понимает: заголовки # ## ###, абзацы (перевод строки внутри — как в Obsidian, строкой), списки - * + и 1. с
   вложенностью, задачи - [ ] / - [x], цитаты >, черту ---, блоки кода ```, таблицы | a | b |, картинки ![](…),
   ссылки [текст](адрес) и голые https://…, **жирный**, *курсив*, ~~зачёркнутый~~, ==выделенный==, `код`.
   html2md — обратно из того, что получилось в редакторе (contenteditable), и из вставленного HTML (сайты, Word,
   таблицы) — лишнее отбрасывается. Обе функции чистые: их проверяет tests/pad1020_test.py (туда-обратно без потерь). */
(function () {
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const safeUrl = (u) => /^(https?:|mailto:|tg:|obsidian:)/i.test(u) || /^[^:]*$/.test(u) ? u : "#";

  function inline(t) {
    const codes = [];
    t = String(t).replace(/`([^`\n]+)`/g, (_, c) => { codes.push(c); return "\u0000" + (codes.length - 1) + "\u0000"; });
    t = esc(t);
    t = t.replace(/!\[([^\]\n]*)\]\(([^)\s]+)\)/g, (_, a, u) => `<img alt="${a}" data-src="${esc(safeUrl(u.replace(/&amp;/g, "&")))}">`);
    t = t.replace(/\[([^\]\n]+)\]\(([^)\s]+)\)/g, (_, a, u) => `<a href="${esc(safeUrl(u.replace(/&amp;/g, "&")))}">${a}</a>`);
    t = t.replace(/(^|[\s(>])((?:https?:\/\/)[^\s<>()"]+[^\s<>()".,;:!?'])/g, (m, pre, u) => `${pre}<a href="${u}">${u}</a>`);
    t = t.replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>").replace(/__([^_\n]+)__/g, "<strong>$1</strong>");
    t = t.replace(/(^|[^*\w])\*([^*\n]+)\*(?![*\w])/g, "$1<em>$2</em>").replace(/(^|[^_\w])_([^_\n]+)_(?![_\w])/g, "$1<em>$2</em>");
    t = t.replace(/~~([^~\n]+)~~/g, "<s>$1</s>").replace(/==([^=\n]+)==/g, "<mark>$1</mark>");
    return t.replace(/\u0000(\d+)\u0000/g, (_, i) => `<code>${esc(codes[+i])}</code>`);
  }
  const LI = /^(\s*)([-*+]|\d+[.)])\s+(?:\[([ xX])\]\s+)?(.*)$/;
  const cells = (l) => l.trim().replace(/^\|/, "").replace(/\|$/, "").split(/(?<!\\)\|/).map(c => c.trim().replace(/\\\|/g, "|"));

  function md2html(md) {
    const L = String(md || "").replace(/\r\n?/g, "\n").split("\n");
    let out = "", i = 0;
    const isTableSep = (l) => /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/.test(l || "") && /\|/.test(l || "");
    while (i < L.length) {
      const l = L[i];
      if (!l.trim()) { i++; continue; }
      let m;
      if ((m = /^```\s*([\w+-]*)\s*$/.exec(l))) {                                 // блок кода
        const buf = []; i++;
        while (i < L.length && !/^```\s*$/.test(L[i])) buf.push(L[i++]);
        i++;
        out += `<pre data-lang="${esc(m[1])}"><code>${esc(buf.join("\n"))}</code></pre>`;
        continue;
      }
      if ((m = /^(#{1,3})\s+(.*)$/.exec(l))) { out += `<h${m[1].length}>${inline(m[2])}</h${m[1].length}>`; i++; continue; }
      if (/^\s*(-{3,}|\*{3,}|_{3,})\s*$/.test(l)) { out += "<hr>"; i++; continue; }
      if (/\|/.test(l) && isTableSep(L[i + 1])) {                                // таблица
        const head = cells(l); i += 2;
        let rows = "";
        while (i < L.length && /\|/.test(L[i]) && L[i].trim()) { rows += "<tr>" + cells(L[i]).map(c => `<td>${inline(c)}</td>`).join("") + "</tr>"; i++; }
        out += `<table><thead><tr>${head.map(c => `<th>${inline(c)}</th>`).join("")}</tr></thead><tbody>${rows}</tbody></table>`;
        continue;
      }
      if (/^\s*>/.test(l)) {                                                       // цитата
        const buf = [];
        while (i < L.length && /^\s*>/.test(L[i])) buf.push(L[i++].replace(/^\s*>\s?/, ""));
        out += `<blockquote>${md2html(buf.join("\n"))}</blockquote>`;
        continue;
      }
      if (LI.test(l)) {                                                            // списки (с вложенностью)
        const items = [];
        while (i < L.length && (m = LI.exec(L[i]))) {
          const ind = m[1].replace(/\t/g, "    ").length;
          items.push({ ind, ol: /\d/.test(m[2]), task: m[3] != null, done: /x/i.test(m[3] || ""), text: m[4], start: parseInt(m[2], 10) });
          i++;
          while (i < L.length && L[i].trim() && !LI.test(L[i]) && /^\s{2,}/.test(L[i])) items[items.length - 1].text += "\n" + L[i++].trim();
        }
        out += list(items, 0, items.length ? items[0].ind : 0).html;
        continue;
      }
      const buf = [];                                                              // абзац: строки — через перевод строки
      while (i < L.length && L[i].trim() && !/^(#{1,3}\s|```|\s*>)/.test(L[i]) && !LI.test(L[i]) && !(/\|/.test(L[i]) && isTableSep(L[i + 1]))
             && !/^\s*(-{3,}|\*{3,}|_{3,})\s*$/.test(L[i])) buf.push(L[i++]);
      out += `<p>${buf.map(inline).join("<br>")}</p>`;
    }
    return out;
  }
  function list(items, k, ind) {
    let html = "", j = k;
    const ol = items[k].ol;
    html += ol ? `<ol${items[k].start > 1 ? ` start="${items[k].start}"` : ""}>` : "<ul>";
    while (j < items.length && items[j].ind >= ind) {
      const it = items[j];
      if (it.ind > ind) { const sub = list(items, j, it.ind); html = html.replace(/<\/li>$/, "") + sub.html + "</li>"; j = sub.next; continue; }
      if (it.ol !== ol && j > k) break;
      const body = it.text.split("\n").map(inline).join("<br>") || "<br>";
      html += it.task ? `<li class="task" data-done="${it.done ? 1 : 0}">${body}</li>` : `<li>${body}</li>`;
      j++;
    }
    html += ol ? "</ol>" : "</ul>";
    if (j < items.length && items[j].ind >= ind && j > k) {                    // другой вид списка дальше — отдельным списком
      const rest = list(items, j, ind); return { html: html + rest.html, next: rest.next };
    }
    return { html, next: j };
  }

  /* ---------- обратно: DOM → Markdown ---------- */
  const BLOCK = /^(P|DIV|H[1-6]|UL|OL|LI|BLOCKQUOTE|PRE|TABLE|THEAD|TBODY|TR|HR|SECTION|ARTICLE|HEADER|FOOTER|FIGURE)$/;
  function inl(n) {
    if (n.nodeType === 3) return n.nodeValue.replace(/ /g, " ").replace(/\n+/g, " ");
    if (n.nodeType !== 1) return "";
    const t = n.tagName, kids = () => [...n.childNodes].map(inl).join("");
    if (t === "BR") return "\n";
    if (t === "IMG") { const s = n.getAttribute("data-src") || n.getAttribute("src") || ""; return s && !/^data:/.test(s) ? `![${(n.getAttribute("alt") || "").replace(/[\[\]]/g, "")}](${s})` : ""; }
    if (t === "A") { const h = n.getAttribute("href") || "", x = kids(); return !h || h === "#" ? x : (x.trim() === h ? h : `[${x.trim() || h}](${h.replace(/ /g, "%20")})`); }
    if (t === "STRONG" || t === "B") { const x = kids(); return x.trim() ? wrap(x, "**") : x; }
    if (t === "EM" || t === "I") { const x = kids(); return x.trim() ? wrap(x, "*") : x; }
    if (t === "S" || t === "DEL" || t === "STRIKE") { const x = kids(); return x.trim() ? wrap(x, "~~") : x; }
    if (t === "MARK") { const x = kids(); return x.trim() ? wrap(x, "==") : x; }
    if (t === "CODE") return "`" + n.textContent + "`";
    if (t === "SCRIPT" || t === "STYLE" || t === "TEMPLATE") return "";
    if (BLOCK.test(t)) return blocks(n).trim();                                  // блок внутри строки (вставка) — текстом
    return kids();
  }
  const wrap = (x, m) => { const a = x.match(/^\s*/)[0], b = x.match(/\s*$/)[0]; return a + m + x.trim() + m + b; };
  function blocks(root, depth = 0) {
    const parts = [];
    let line = "";
    const flush = () => { if (line.replace(/\n/g, "").trim()) parts.push(line.replace(/\n+$/, "")); line = ""; };
    for (const n of root.childNodes) {
      if (n.nodeType === 1 && BLOCK.test(n.tagName) && n.tagName !== "LI") { flush(); const b = block(n, depth); if (b !== null && b !== "") parts.push(b); }
      else line += inl(n);
    }
    flush();
    return parts.join("\n\n");
  }
  function block(n, depth) {
    const t = n.tagName;
    if (/^H[1-6]$/.test(t)) { const lv = Math.min(3, +t[1]); const x = [...n.childNodes].map(inl).join("").replace(/\n/g, " ").trim(); return x ? "#".repeat(lv) + " " + x : ""; }
    if (t === "HR") return "---";
    if (n.classList && n.classList.contains("dw-diagram")) return "```mermaid\n" + (n.getAttribute("data-src") || "").trim() + "\n```";   // схема в блокноте (padai.js)
    if (t === "PRE") { const c = n.textContent.replace(/\n$/, ""); return "```" + (n.getAttribute("data-lang") || "") + "\n" + c + "\n```"; }
    if (t === "BLOCKQUOTE") return blocks(n, depth).split("\n").map(l => "> " + l).join("\n");
    if (t === "UL" || t === "OL") return lst(n, 0);
    if (t === "TABLE") return table(n);
    return blocks(n, depth);                                                      // P, DIV и прочие — их содержимое
  }
  function lst(n, ind) {
    const ol = n.tagName === "OL"; let k = parseInt(n.getAttribute("start") || "1", 10) || 1;
    const out = [];
    for (const li of n.children) {
      if (li.tagName !== "LI") { if (li.tagName === "UL" || li.tagName === "OL") out.push(lst(li, ind + 2)); continue; }
      let text = "", subs = [];
      for (const c of li.childNodes) {
        if (c.nodeType === 1 && (c.tagName === "UL" || c.tagName === "OL")) subs.push(lst(c, ind + 2));
        else if (c.nodeType === 1 && BLOCK.test(c.tagName)) text += (text ? "\n" : "") + blocks(c);
        else text += inl(c);
      }
      const task = li.classList.contains("task");
      const mark = (ol ? `${k++}.` : "-") + (task ? (li.getAttribute("data-done") === "1" ? " [x]" : " [ ]") : "");
      const lines = text.replace(/\n+$/, "").split("\n");
      out.push(" ".repeat(ind) + mark + " " + (lines[0] || "") + lines.slice(1).map(l => "\n" + " ".repeat(ind + 2) + l).join(""));
      out.push(...subs);
    }
    return out.join("\n");
  }
  function table(n) {
    const rows = [...n.querySelectorAll("tr")].map(tr => [...tr.children].map(c => [...c.childNodes].map(inl).join("").replace(/\n/g, " ").replace(/\|/g, "\\|").trim()));
    if (!rows.length) return "";
    const w = Math.max(...rows.map(r => r.length));
    rows.forEach(r => { while (r.length < w) r.push(""); });
    return [rows[0], rows[0].map(() => "---"), ...rows.slice(1)].map(r => "| " + r.join(" | ") + " |").join("\n");
  }
  function html2md(rootOrHtml) {
    let root = rootOrHtml;
    if (typeof rootOrHtml === "string") { root = document.createElement("div"); root.innerHTML = rootOrHtml; }
    return blocks(root).replace(/\n{3,}/g, "\n\n").replace(/[ \t]+$/gm, "").trim() + "\n";
  }
  window.PadMD = { md2html, html2md, inline };
})();
