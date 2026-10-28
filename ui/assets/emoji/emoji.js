/* Смайлы Dewiar картинками (0.63; владелец 28.10: «смайлы в Близких и группах — ограниченное количество, не особо
   симпатичные»): Fluent Emoji 3D (Microsoft, MIT) — одинаково красиво в Ubuntu, Windows и на телефоне, где шрифт со
   смайлами свой или вовсе чёрно-белый. Данные — emoji-data.js (tools/emoji_build.py): 9 разделов, ~1650 смайлов,
   названия по-русски для поиска. Текст сообщений остаётся обычным Юникодом — картинки только при показе.

   DewiarEmoji.html(экранированный текст) — смайлы в тексте картинками; .img(смайл) — одна картинка;
   .only(текст) — только смайлы (крупно); .picker(узел, {onPick}) — выбор: «Недавние», разделы, поиск.
   Адрес картинок — window.DEWIAR_EMOJI_BASE (студия — assets/emoji/, телефон — emoji/).
   Регулярное выражение с \p{…} создаётся через new RegExp в try: старый Safari (веб-версия) его не знает — тогда
   смайлы остаются шрифтом, а страница работает. */
(function () {
  "use strict";
  const DATA = window.DEWIAR_EMOJI_DATA || [];
  const base = () => window.DEWIAR_EMOJI_BASE || "assets/emoji/";
  const norm = (s) => String(s || "").replace(/️/g, "");
  const map = new Map(), info = new Map();
  DATA.forEach(([, items]) => items.forEach((it) => { map.set(norm(it[0]), it[1]); info.set(it[1], it); }));
  let RX = null, MOD = null;
  try {
    RX = new RegExp("(?:\\p{Regional_Indicator}{2}|[#*0-9]\\uFE0F?\\u20E3|\\p{Extended_Pictographic}(?:\\uFE0F|\\p{Emoji_Modifier})?(?:\\u200D\\p{Extended_Pictographic}(?:\\uFE0F|\\p{Emoji_Modifier})?)*)", "gu");
    MOD = new RegExp("\\p{Emoji_Modifier}", "gu");
  } catch (e) { RX = null; }
  function keyOf(ch) {
    let n = norm(ch);
    if (map.has(n)) return map.get(n);
    if (MOD) { n = n.replace(MOD, ""); if (map.has(n)) return map.get(n); }   // оттенок кожи — основной картинкой
    return "";
  }
  function img(ch, cls) {
    const k = keyOf(ch);
    return k ? `<img class="${cls || "emj"}" src="${base()}img/${k}.webp" alt="${ch}" draggable="false" loading="lazy">` : ch;
  }
  function html(escaped) {
    if (!RX || !map.size) return String(escaped == null ? "" : escaped);
    return String(escaped == null ? "" : escaped).replace(RX, (m) => img(m));
  }
  function only(text) {
    const t = String(text || "").trim();
    if (!RX || !t || t.length > 40) return false;
    return t.replace(RX, "").replace(/[\s‍️]/g, "") === "" ;
  }

  /* ---------- выбор смайла ---------- */
  const RECENT = "dewiar_emoji_recent";
  const recent = () => { try { return JSON.parse(localStorage.getItem(RECENT) || "[]").filter((c) => keyOf(c)).slice(0, 32); } catch (e) { return []; } };
  const remember = (ch) => { try { localStorage.setItem(RECENT, JSON.stringify([ch].concat(recent().filter((x) => x !== ch)).slice(0, 32))); } catch (e) { } };
  const ICON = { "Смайлы": "😀", "Люди": "👋", "Природа": "🐱", "Еда": "🍕", "Места": "🏠", "Занятия": "⚽", "Предметы": "💡", "Символы": "❤️", "Флаги": "🏁" };
  const FIRST = ["👍", "❤️", "😂", "😊", "🙏", "🔥", "🎉", "😍", "🤝", "😢", "😮", "👋"];
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  function search(q) {
    q = String(q || "").toLowerCase().replace(/ё/g, "е").trim();
    if (!q) return [];
    const out = [];
    DATA.forEach(([, items]) => items.forEach((it) => {
      const hay = (it[2] + " " + it[3]).toLowerCase().replace(/ё/g, "е");
      if (hay.split(/[\s,]+/).some((w) => w.startsWith(q)) || hay.includes(q)) out.push(it[0]);
    }));
    return out.slice(0, 120);
  }
  /* el — пустой узел; opts.onPick(смайл). Вкладка и запрос живут в самом узле (перерисовка их не теряет). */
  function picker(el, opts) {
    opts = opts || {};
    const st = el._emo || (el._emo = { tab: -1, q: "" });
    const tabs = [[-1, "Недавние и частые", "🕘"]].concat(DATA.map(([n, items], i) => [i, n, ICON[n] && keyOf(ICON[n]) ? ICON[n] : items[0][0]]));
    const list = st.q ? search(st.q) : st.tab === -1 ? (recent().length ? recent() : FIRST) : (DATA[st.tab] ? DATA[st.tab][1].map((it) => it[0]) : []);
    el.classList.add("emo-pick");
    el.innerHTML = `<div class="emo-top"><input class="emo-q" type="search" placeholder="Найти смайл: сердце, смех, кот…" value="${esc(st.q)}" aria-label="Найти смайл"></div>`
      + `<div class="emo-tabs" role="tablist">${tabs.map(([i, n, ch]) => `<button type="button" role="tab" data-t="${i}" aria-selected="${!st.q && st.tab === i}" title="${esc(n)}">${img(ch, "emj")}</button>`).join("")}</div>`
      + `<div class="emo-g" role="tabpanel">${list.length ? list.map((ch) => `<button type="button" data-e="${esc(ch)}" title="${esc((info.get(keyOf(ch)) || [])[2] || ch)}">${img(ch, "emj")}</button>`).join("")
        : `<p class="emo-none">Не нашлось — попробуйте другое слово</p>`}</div>`;
    el.querySelectorAll("[data-t]").forEach((b) => b.onclick = () => { st.tab = +b.dataset.t; st.q = ""; picker(el, opts); });
    el.querySelectorAll("[data-e]").forEach((b) => b.onclick = () => { remember(b.dataset.e); if (opts.onPick) opts.onPick(b.dataset.e); });
    const q = el.querySelector(".emo-q");
    q.oninput = () => { const pos = q.selectionStart; st.q = q.value; picker(el, opts); const q2 = el.querySelector(".emo-q"); q2.focus(); try { q2.setSelectionRange(pos, pos); } catch (e) { } };
  }
  window.DewiarEmoji = { html, img, only, picker, keyOf, remember, recent, search, ready: !!(RX && map.size) };
})();
