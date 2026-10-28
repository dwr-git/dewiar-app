/* «Радио» на телефоне (0.65; как вкладка «Радио» в «Музыке» студии): «Всё» → «Радио» или нажать название станции над
   Лирой. Сверху — что играет (значок, ⏯, следующая, ♥); поиск по каталогу radio-browser; жанры; «Мои станции» (♥, они же —
   голосом по названию: radio.list() их знает) и «Популярные» — наш список. Нажали плитку — играет именно она (radio.playOne),
   нажали играющую — пауза. Значки станций — favicon из каталога: у найденных — сразу, у нашего списка — ищем в фоне раз в
   месяц (pref radio_logos); нет или не загрузился — буквы на цветной плашке.
   S.radio_fav: [{name, url, tags, logo}] — до 40, новые сверху. */
"use strict";
const RP = { q: "", res: null, busy: false, err: "", seq: 0, logoBusy: false };
const RP_HEART = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20s-7.5-4.6-7.5-10.2A4.3 4.3 0 0 1 12 7.2a4.3 4.3 0 0 1 7.5 2.6C19.5 15.4 12 20 12 20z"/></svg>';
const rpFavs = () => (Array.isArray(S.radio_fav) ? S.radio_fav : []).filter(x => x && x.url);
const rpKey = (n) => String(n || "").toLowerCase().replace(/ё/g, "е").replace(/радио|radio/g, "").replace(/[^0-9a-zа-я]+/g, "");
function rpLogos() { try { return JSON.parse(prefGet("radio_logos") || "{}") || {}; } catch (e) { return {}; } }
const rpLogoOf = (st) => st.logo || (rpLogos()[rpKey(st.name)] || {}).logo || "";
function rpGenres() {
  let g = []; try { g = (JSON.parse(prefGet("radio_list") || "null") || {}).genres || []; } catch (e) { g = []; }
  if (!g.length) g = (window.RADIO_LIST && window.RADIO_LIST.genres) || [];
  return g.filter(x => typeof x === "string").slice(0, 12);
}
const rpHue = (s) => { let h = 0; for (const c of String(s)) h = (h * 31 + c.codePointAt(0)) % 360; return h; };
function rpMono(name) {
  const w = String(name || "").replace(/[«»"'()]/g, " ").split(/[\s\-–—.]+/).filter(x => x && !/^(радио|radio|фм|fm|ру|ru)$/i.test(x));
  return ((w[0] || name || "?")[0] + (w[1] && /^[\p{L}\d]/u.test(w[1]) ? w[1][0] : "")).toUpperCase();
}
function rpLogo(st, big) {
  const l = rpLogoOf(st);
  return `<span class="rp-logo${big ? " big" : ""}" style="--h:${rpHue(st.name)}"><i>${esc(rpMono(st.name))}</i>${l ? `<img src="${esc(l)}" alt="" loading="lazy" referrerpolicy="no-referrer">` : ""}</span>`;
}
function rpLogoFix(root) {
  root.querySelectorAll(".rp-logo img").forEach(im => {
    const bad = () => im.remove(), ok = () => { if (im.naturalWidth < 8) bad(); else im.parentElement.classList.add("pic"); };
    if (im.complete) { if (im.naturalWidth) ok(); else bad(); } else { im.onload = ok; im.onerror = bad; }
  });
}
const rpTags = (st) => String(st.tags || "").replace(/,/g, " ").split(/\s+/).filter(Boolean).slice(0, 3).join(" ");
function rpNowUrl() { const st = radio.state(), c = radio.current(); return radio.on() && c && c.name === st.name ? c.url : ""; }
function rpTiles(list, empty) {
  const now = rpNowUrl(), paused = radio.state().state === "paused", fav = new Set(rpFavs().map(x => x.url));
  return list.length ? `<div class="rp-grid">${list.map((st, i) => `<div class="rp-t${st.url === now ? " on" + (paused ? " paused" : "") : ""}">`
    + `<button class="rp-play" data-i="${i}">${rpLogo(st)}<b>${esc(st.name)}</b><small>${esc(rpTags(st) || st.country || "")}</small>`
    + `<span class="rp-eq" aria-hidden="true"><i></i><i></i><i></i></span></button>`
    + `<button class="rp-fav${fav.has(st.url) ? " on" : ""}" data-f="${i}" aria-pressed="${fav.has(st.url)}" aria-label="${fav.has(st.url) ? "Убрать из моих станций" : "В мои станции"}">${RP_HEART}</button></div>`).join("")}</div>`
    : `<p class="rp-empty">${empty}</p>`;
}
function rpNow() {
  const st = radio.state(), c = radio.current();
  if (!radio.on() || !st.name) return "";
  const s = c && c.name === st.name ? c : { name: st.name, url: "", tags: "" };
  const fav = s.url && rpFavs().some(x => x.url === s.url);
  const sub = st.state === "preparing" ? "Подключаюсь…" : st.state === "paused" ? "На паузе" : "В эфире";
  return `<div class="rp-now">${rpLogo(s, true)}<div class="rp-np"><small>${st.state === "playing" ? '<span class="rp-live"></span>' : ""}${sub}</small><b>${esc(s.name)}</b></div>`
    + `<div class="rp-ctl"><button id="rp-pp" aria-label="${st.state === "paused" ? "Играть" : "Пауза"}">${st.state === "paused"
      ? '<svg viewBox="0 0 24 24"><path d="M8 5.6v12.8a.9.9 0 0 0 1.4.8l10-6.4a.9.9 0 0 0 0-1.6l-10-6.4A.9.9 0 0 0 8 5.6z"/></svg>'
      : '<svg viewBox="0 0 24 24" class="st"><path d="M8.5 5.5v13M15.5 5.5v13"/></svg>'}</button>`
    + `<button id="rp-next" aria-label="Другая станция"><svg viewBox="0 0 24 24"><path d="M5 6.2v11.6a.8.8 0 0 0 1.2.7l8.2-5.8a.8.8 0 0 0 0-1.4L6.2 5.5A.8.8 0 0 0 5 6.2z"/><path class="st" d="M17 5v14"/></svg></button>`
    + (s.url ? `<button id="rp-heart" class="${fav ? "on" : ""}" aria-pressed="${!!fav}" aria-label="${fav ? "Убрать из моих станций" : "В мои станции"}">${RP_HEART}</button>` : "") + `</div></div>`;
}
let RP_LISTS = { mine: [], top: [] };
function rpRender() {
  const box = $("#radio-body"); if (!box || !$("#sh-radio").classList.contains("on")) return;
  const keep = document.activeElement && document.activeElement.id === "rp-q";
  const g = rpGenres();
  const mine = rpFavs(), top = radio.list().filter(x => !mine.some(m => m.url === x.url));
  RP_LISTS = { mine, top: RP.busy ? [] : RP.res || top };
  box.innerHTML = rpNow()
    + `<form class="rp-find" id="rp-find"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="6.5"/><path d="m16 16 4.5 4.5"/></svg>`
    + `<input id="rp-q" type="search" enterkeyhint="search" placeholder="Станция, жанр или город" aria-label="Найти радиостанцию" value="${esc(RP.q)}" autocomplete="off"></form>`
    + `<div class="rp-chips">${[["", "Популярные"]].concat(g.map(x => [x, x[0].toUpperCase() + x.slice(1)])).map(([k, l]) =>
        `<button class="rp-chip${(RP.res || RP.busy ? RP.q.toLowerCase() === k : !k) ? " on" : ""}" data-g="${esc(k)}">${esc(l)}</button>`).join("")}</div>`
    + (mine.length ? `<h3 class="rp-h">Мои станции</h3><div data-l="mine">${rpTiles(mine, "")}</div>` : "")
    + `<h3 class="rp-h">${RP.busy ? `Ищу «${esc(RP.q)}»…` : RP.res ? `«${esc(RP.q[0].toUpperCase() + RP.q.slice(1))}»` : "Популярные"}</h3>`
    + `<div data-l="top">${RP.busy ? `<div class="rp-grid">${'<div class="rp-t sk"></div>'.repeat(6)}</div>`
      : rpTiles(RP_LISTS.top, RP.err ? esc(RP.err) : RP.res ? "Не нашлось — попробуйте по-другому: «Европа», «jazz», «Минск»." : "Список станций ещё не загрузился.")}</div>`
    + (mine.length ? "" : `<p class="rp-hint">♥ на станции — и она в «Моих станциях»; потом можно просто сказать: «включи …» и её название.</p>`);
  rpLogoFix(box);
  box.querySelectorAll("[data-l]").forEach(sec => {
    const L = RP_LISTS[sec.dataset.l] || [];
    sec.querySelectorAll(".rp-play").forEach(b => b.onclick = () => rpPlay(L[+b.dataset.i]));
    sec.querySelectorAll(".rp-fav").forEach(b => b.onclick = () => rpFav(L[+b.dataset.f]));
  });
  box.querySelectorAll(".rp-chip").forEach(b => b.onclick = () => rpSearch(b.dataset.g));
  $("#rp-find").onsubmit = (e) => { e.preventDefault(); $("#rp-q").blur(); rpSearch($("#rp-q").value); };
  $("#rp-q").oninput = () => { RP.q = $("#rp-q").value; if (!RP.q.trim() && RP.res) rpSearch(""); };
  if (keep) { const q = $("#rp-q"); q.focus(); try { q.setSelectionRange(q.value.length, q.value.length); } catch (e) { } }
  const pp = $("#rp-pp"); if (pp) pp.onclick = () => { D.vibrate(12); if (radio.state().state === "paused") radio.resume(); else radio.pause(); };
  const nx = $("#rp-next"); if (nx) nx.onclick = () => { D.vibrate(12); rpStep(); };
  const ht = $("#rp-heart"); if (ht) ht.onclick = () => { const c = radio.current(); if (c) rpFav(c); };
}
async function rpSearch(q) {
  q = String(q || "").trim(); RP.q = q;
  if (!q) { RP.res = null; RP.busy = false; RP.err = ""; rpRender(); return; }
  const my = ++RP.seq, low = q.toLowerCase().replace(/ё/g, "е");
  RP.busy = true; RP.err = ""; rpRender();
  const own = rpFavs().concat(radio.list()).filter((x, i, a) => a.findIndex(y => y.url === x.url) === i)
    .filter(x => (x.name + " " + x.tags).toLowerCase().replace(/ё/g, "е").includes(low));
  let found = [];
  try { found = await radio.search(q, 40); } catch (e) { if (!own.length) RP.err = "Каталог радиостанций сейчас не отвечает — проверьте интернет."; }
  if (my !== RP.seq) return;
  const seen = new Set(own.map(x => x.url)), names = new Set();
  RP.res = own.concat(found.filter(x => { const k = rpKey(x.name) || x.url; if (seen.has(x.url) || names.has(k)) return false; names.add(k); return true; })).slice(0, 40);
  RP.busy = false; rpRender();
}
async function rpPlay(st) {
  if (!st) return;
  D.vibrate(12);
  if (rpNowUrl() === st.url && radio.state().state !== "paused") { radio.pause(); return; }
  const r = await radio.playOne({ name: st.name, url: st.url, tags: rpTags(st), aliases: [], logo: rpLogoOf(st) });
  if (!r.ok && !r.superseded) toast(r.text, 4000);
  rpRender();
}
function rpFav(st) {
  if (!st || !st.url) return;
  const on = rpFavs().some(x => x.url === st.url);
  S.radio_fav = on ? rpFavs().filter(x => x.url !== st.url)
    : [{ name: String(st.name).slice(0, 80), url: st.url, tags: rpTags(st), logo: rpLogoOf(st) }].concat(rpFavs()).slice(0, 40);
  saveS(); D.vibrate(12);
  toast(on ? `«${st.name}» убрана из моих станций` : `«${st.name}» — в моих станциях`, 2200);
  rpRender();
}
function rpStep() {
  const all = RP_LISTS.mine.concat(RP_LISTS.top), u = rpNowUrl(), i = all.findIndex(x => x.url === u);
  if (!all.length || i < 0) { radio.next().then(rpRender); return; }
  rpPlay(all[(i + 1) % all.length]);
}
/* значки нашего списка: ищем станцию по названию в каталоге, по одной, раз в месяц на станцию */
async function rpLogoFill() {
  if (RP.logoBusy) return; RP.logoBusy = true;
  try {
    const lg = rpLogos(), now = Date.now(); let got = 0;
    for (const st of radio.list().slice(0, 40)) {
      const k = rpKey(st.name); if (!k || (lg[k] && now - lg[k].at < 30 * 86400e3)) continue;
      let rows = []; try { rows = await radio.search(st.name, 6); } catch (e) { break; }
      const best = rows.find(x => x.logo && rpKey(x.name) === k) || rows.find(x => x.logo && (rpKey(x.name).startsWith(k) || k.startsWith(rpKey(x.name) || "-")));
      lg[k] = { logo: best ? best.logo : "", at: now }; got += best ? 1 : 0;
      prefSet("radio_logos", JSON.stringify(lg));
    }
    if (got) rpRender();
  } finally { RP.logoBusy = false; }
}
function openRadio() { RP.res = null; RP.q = ""; RP.err = ""; openSheet("#sh-radio"); rpRender(); radio.refresh(); rpLogoFill(); }
N.on("radio", () => setTimeout(rpRender, 0));
document.addEventListener("click", (e) => { if (e.target.closest && e.target.closest("#rchip > b")) openRadio(); });
