/* Студия Dewiar, раздел «Музыка» (27.10): своя папка с музыкой, подборки и ведущий между треками.
   Команды ядра: mm_status, mm_list {what}, mm_play {what|path}, mm_ctl {act}, mm_folder {folder}, mm_scan, mm_fav {path,on};
   события: «mymusic» (что играет, сколько треков) и «radio» (играет / пауза). Голосом — engine_mymusic.py. */
let mmWhat = "", mmData = null, mmList = [];
const MM_CHIPS = [["", "Все треки"], ["любимое", "Любимое"], ["спокойное", "Спокойное"], ["для работы", "Для работы"], ["бодрое", "Бодрое"], ["русское", "Русское"]];
function mmNow(s) {
  const n = s && s.now, box = $("#mm-now");
  if (!box) return;
  box.classList.toggle("idle", !n);
  const cv = $("#mm-cover"), art = n && n.art ? n.art : "";
  cv.classList.toggle("art", !!art);                     // обложка из файла или папки альбома (№361); нет — как раньше
  cv.style.backgroundImage = art ? `url("${art.replace(/"/g, "%22")}")` : "";
  cv.textContent = art ? "" : n ? (n.artist || n.title || "♪").slice(0, 18) : "♪";
  $("#mm-np").innerHTML = n
    ? `<small>${s.paused ? "На паузе" : "Сейчас играет"}${s.what ? " · подборка «" + escH(s.what) + "»" : ""}</small><h2>${escH(n.title)}</h2>` +
      `<div class="ar">${escH([n.artist, n.album && "«" + n.album + "»", n.year].filter(Boolean).join(" · "))}</div>`
    : `<small>Тишина</small><h2>Выберите подборку</h2><div class="ar">или скажите: «Лира, поставь мою музыку»</div>`;
  $("#mm-pp").classList.toggle("playing", !!(n && !(s && s.paused)));
  $("#mm-pp").title = s && s.paused || !n ? "Играть" : "Пауза";
  if ($("#mm-time")) $("#mm-time").hidden = !n;
  if (s && s.vis) mmVisTake(s.vis);
  const f = $("#mm-heart"); f.hidden = !n; if (n) { f.classList.toggle("on", !!n.fav); f.title = n.fav ? "Убрать из любимого" : "В любимое"; }
}
function mmStats(s) {
  const st = s.stats || {};
  const parts = (s.folder || "").split(/[\\/]/).filter(Boolean);       // длинный путь — последние две папки, целиком — в подсказке
  $("#mm-folder").textContent = !s.folder ? "Папка не выбрана" : (parts.length > 2 ? "…/" : "") + parts.slice(-2).join("/");
  $("#mm-pick").title = s.folder ? s.folder + " — нажмите, чтобы выбрать другую" : "Выбрать папку с музыкой";
  $("#mm-folder").classList.toggle("empty", !s.folder);
  const pr = s.progress || {}, fmtN = (x) => Number(x || 0).toLocaleString("ru");
  // ход чтения (№361: «при сканировании сетевой папки было бы хорошо видеть прогресс»): ищем файлы — бегущая полоска
  // и сколько нашлось; читаем теги — настоящая полоска «340 из 1 240»
  $("#mm-stats").innerHTML = s.busy ? `<div class="wide mm-prog">${pr.phase === "tags" && pr.total
      ? `<span>Читаю треки: <b>${fmtN(pr.done)}</b> из ${fmtN(pr.total)}</span><i><u style="width:${Math.min(100, Math.round(pr.done / pr.total * 100))}%"></u></i>`
      : `<span>Ищу музыку в папке${pr.found ? `: нашлось <b>${fmtN(pr.found)}</b>` : "…"}</span><i class="run"><u></u></i>`}</div>` :
    [[st.tracks || 0, plural(st.tracks || 0, "трек", "трека", "треков")], [st.artists || 0, plural(st.artists || 0, "исполнитель", "исполнителя", "исполнителей")],
     [st.genres || 0, plural(st.genres || 0, "жанр", "жанра", "жанров")]].map(([n, l]) => `<div><b>${n}</b><small>${l}</small></div>`).join("");
}
function mmChips() {
  const art = (mmData && mmData.artists || []).slice(0, 8).map(a => [a, a]);
  $("#mm-chips").innerHTML = MM_CHIPS.concat(art).map(([k, l]) => `<button class="chip${k === mmWhat ? " on" : ""}" data-w="${escH(k)}">${escH(l)}</button>`).join("");
  $$("#mm-chips .chip").forEach(b => b.onclick = () => { mmWhat = b.dataset.w; mmChips(); mmLoadList(); });
}
function mmRenderList() {
  const now = mmData && mmData.now ? mmData.now.path : "";
  $("#mm-list").innerHTML = mmList.length ? mmList.slice(0, 200).map((t, i) => `<li class="${t.path === now ? "cur" : ""}" data-i="${i}">` +
    `<button class="mm-play" title="Играть с этого трека">▶</button><span class="tt"><b>${escH(t.title)}</b><small>${escH([t.artist, t.album].filter(Boolean).join(" · "))}</small></span>` +
    `<button class="mm-fav${t.fav ? " on" : ""}" title="${t.fav ? "Убрать из любимого" : "В любимое"}">♥</button></li>`).join("") +
    (mmList.length > 200 ? `<li class="more">и ещё ${mmList.length - 200}</li>` : "")
    : `<li class="more">${mmWhat === "любимое" ? "В любимом пока пусто: нажмите ♥ у песни или скажите «эту в любимое», когда она играет." : (mmData && mmData.stats && mmData.stats.tracks ? "В этой подборке ничего не нашлось." : "Выберите папку с музыкой — треки появятся здесь.")}</li>`;
  $$("#mm-list li[data-i]").forEach(li => {
    const t = mmList[+li.dataset.i];
    li.querySelector(".mm-play").onclick = () => core.call("mm_play", { what: mmWhat, path: t.path }).then(mmRefresh).catch(e => toast(e.message, 4000));
    li.querySelector(".mm-fav").onclick = () => core.call("mm_fav", { path: t.path, on: !t.fav }).then(() => { t.fav = !t.fav; mmRenderList(); mmRefresh(); }).catch(e => toast(e.message));
  });
}
async function mmLoadList() {
  try { mmList = await core.call("mm_list", { what: mmWhat }); } catch (e) { mmList = []; }
  $("#mm-play-all").textContent = mmWhat ? `Играть «${MM_CHIPS.find(c => c[0] === mmWhat) ? MM_CHIPS.find(c => c[0] === mmWhat)[1] : mmWhat}»` : "Играть всё вперемешку";
  mmRenderList();
}
async function mmRefresh() {
  try { mmData = await core.call("mm_status"); } catch (e) { return; }
  mmNow(mmData); mmStats(mmData); mmChips();
}
/* Плеер (27.10, владелец: «не хватает громкости, статуса проигранного, а это окошко фиолетовое — красивую анимацию под
   музыку; кнопочки симпатичнее»). mm_vis (~8 раз в секунду, пока играет и раздел открыт): ход трека, громкость и восемь
   полос спектра — ими дышит фон: три мягких пятна света (басы, середина, верх) и тонкие столбики снизу. */
const MMV = { pos: 0, dur: 0, at: 0, playing: false, bands: new Array(8).fill(0), sm: new Array(8).fill(0), vol: 0.8, local: false, drag: false, timer: 0, raf: 0, t0: performance.now() };
const mmFmt = (t) => { t = Math.max(0, Math.floor(t || 0)); return `${Math.floor(t / 60)}:${String(t % 60).padStart(2, "0")}`; };
function mmVisTake(v) {
  if (!v) return;
  Object.assign(MMV, { pos: +v.pos || 0, dur: +v.dur || 0, at: performance.now(), playing: !!v.playing, bands: v.bands || MMV.bands, local: !!v.local });
  if (!MMV.drag && typeof v.volume === "number" && $("#mm-vol")) { MMV.vol = v.volume; $("#mm-vol").value = Math.round(v.volume * 100); $("#mm-volv").textContent = Math.round(v.volume * 100) + "%"; }
  mmTime();
}
function mmTime() {
  if (!$("#mm-t0")) return;
  const pos = MMV.playing ? MMV.pos + (performance.now() - MMV.at) / 1000 : MMV.pos, d = MMV.dur;
  $("#mm-t0").textContent = mmFmt(d ? Math.min(pos, d) : pos);
  $("#mm-t1").textContent = d ? mmFmt(d) : "—";
  const f = d ? Math.min(100, pos / d * 100) : 0;
  $("#mm-fill").style.width = f + "%"; $("#mm-knob").style.left = f + "%";
  $("#mm-bar").disabled = !(d && MMV.local);
}
async function mmPoll() {
  clearTimeout(MMV.timer);
  const on = $("#p-music") && $("#p-music").classList.contains("cur") && !document.hidden;
  if (on) { try { mmVisTake(await core.call("mm_vis")); } catch (e) { /* ядро занято — в следующий раз */ } }
  MMV.timer = setTimeout(mmPoll, on && MMV.playing ? 120 : 1000);
}
function mmDraw(now) {
  const cv = $("#mm-vis"); if (!cv || !cv.isConnected) { MMV.raf = 0; return; }
  const box = cv.parentElement, dpr = Math.min(2, window.devicePixelRatio || 1), W = box.clientWidth, H = box.clientHeight;
  if (cv.width !== Math.round(W * dpr) || cv.height !== Math.round(H * dpr)) { cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr); }
  const g = cv.getContext("2d"); g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, W, H);
  for (let i = 0; i < 8; i++) { const b = MMV.playing ? MMV.bands[i] || 0 : 0; MMV.sm[i] += (b - MMV.sm[i]) * (b > MMV.sm[i] ? .45 : .12); }
  const still = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches, t = still ? 0 : (now - MMV.t0) / 1000;
  const low = (MMV.sm[0] + MMV.sm[1]) / 2, mid = (MMV.sm[2] + MMV.sm[3] + MMV.sm[4]) / 3, high = (MMV.sm[5] + MMV.sm[6] + MMV.sm[7]) / 3;
  const blob = (x, y, r, c, a) => { const gr = g.createRadialGradient(x, y, 0, x, y, r); gr.addColorStop(0, `rgba(${c},${a})`); gr.addColorStop(1, `rgba(${c},0)`); g.fillStyle = gr; g.fillRect(0, 0, W, H); };
  g.globalCompositeOperation = "lighter";
  blob(W * (.30 + .06 * Math.sin(t * .35)), H * (.55 + .12 * Math.cos(t * .27)), H * (.85 + .55 * low), "255,170,90", .16 + .32 * low);
  blob(W * (.62 + .08 * Math.cos(t * .22)), H * (.40 + .15 * Math.sin(t * .31)), H * (.95 + .45 * mid), "124,108,255", .18 + .30 * mid);
  blob(W * (.86 + .05 * Math.sin(t * .41)), H * (.70 + .10 * Math.sin(t * .19)), H * (.65 + .40 * high), "255,127,168", .10 + .30 * high);
  g.globalCompositeOperation = "source-over";
  const n = 56, bw = W / n;                                            // тонкие столбики спектра по низу
  for (let i = 0; i < n; i++) {
    const x = i / (n - 1) * 7, k = Math.floor(x), fr = x - k, v = (MMV.sm[k] || 0) * (1 - fr) + (MMV.sm[Math.min(7, k + 1)] || 0) * fr;
    const h = 3 + v * H * .3 * (.75 + .25 * Math.sin(i * 1.7 + t * 2));
    g.fillStyle = `rgba(255,255,255,${.05 + v * .12})`;
    const r = Math.min(3, bw * .3), x0 = i * bw + bw * .22, w = bw * .56, y0 = H - h;
    g.beginPath(); g.moveTo(x0, H); g.lineTo(x0, y0 + r); g.quadraticCurveTo(x0, y0, x0 + r, y0); g.lineTo(x0 + w - r, y0); g.quadraticCurveTo(x0 + w, y0, x0 + w, y0 + r); g.lineTo(x0 + w, H); g.fill();
  }
  if (MMV.playing) mmTime();
  MMV.raf = still ? 0 : requestAnimationFrame(mmDraw);
}
function mmVisStart() { if (!MMV.raf) MMV.raf = requestAnimationFrame(mmDraw); mmPoll(); }
function loadMyMusic() { mmVisStart(); mmRefresh().then(mmLoadList); if (typeof rcLoad === "function") rcLoad(); }
if ($("#p-music")) {
  core.on("mymusic", e => { if (!$("#p-music").classList.contains("cur")) return; mmData = Object.assign(mmData || {}, e); mmNow(mmData); mmStats(mmData); if (!e.busy) mmLoadList(); });
  core.on("radio", () => { if ($("#p-music").classList.contains("cur")) mmRefresh().then(mmRenderList); });
  $("#mm-pick").onclick = async () => {
    const a = window.api && window.api(); let p = "";
    if (a && a.pick_folder) p = await a.pick_folder(); else p = await askText("Полный путь к папке с музыкой:") || "";
    if (!p) return;
    try { await core.call("mm_folder", { folder: p }); toast("Читаю папку — это быстро", 2500); } catch (e) { toast(e.message, 4000); }
    mmRefresh();
  };
  $("#mm-rescan").onclick = () => core.call("mm_scan").then(() => { toast("Перечитываю папку", 2000); mmRefresh(); }).catch(e => toast(e.message));
  $("#mm-play-all").onclick = () => core.call("mm_play", { what: mmWhat }).then(mmRefresh).catch(e => toast(e.message, 4000));
  $("#mm-pp").onclick = () => core.call("mm_ctl", { act: mmData && mmData.now && !mmData.paused ? "pause" : "play" }).then(mmRefresh).catch(e => toast(e.message, 4000));
  $("#mm-next").onclick = () => core.call("mm_ctl", { act: "next" }).then(mmRefresh).catch(e => toast(e.message));
  $("#mm-prev").onclick = () => core.call("mm_ctl", { act: "prev" }).then(mmRefresh).catch(e => toast(e.message));
  if ($("#mm-vol")) {
  $("#mm-vol").oninput = () => { MMV.drag = true; $("#mm-volv").textContent = $("#mm-vol").value + "%"; };
  $("#mm-vol").onchange = () => core.call("mm_ctl", { act: "vol", v: +$("#mm-vol").value / 100 }).then(r => { MMV.drag = false; if (r && r.vis) mmVisTake(r.vis); })
    .catch(e => { MMV.drag = false; toast(e.message); });
  $("#mm-bar").onclick = (e) => { if (!MMV.dur || !MMV.local) return; const r = $("#mm-bar i").getBoundingClientRect();
    const t = Math.max(0, Math.min(1, (e.clientX - r.left) / r.width)) * MMV.dur;
    Object.assign(MMV, { pos: t, at: performance.now() }); mmTime();
    core.call("mm_ctl", { act: "seek", t }).then(r2 => { if (r2 && r2.vis) mmVisTake(r2.vis); }).catch(x => toast(x.message)); };
  $("#mm-bar").onkeydown = (e) => { if (!MMV.dur || !MMV.local || !/^Arrow(Left|Right)$/.test(e.key)) return; e.preventDefault();
    core.call("mm_ctl", { act: "seek", t: MMV.pos + (e.key === "ArrowRight" ? 10 : -10) }).then(r2 => { if (r2 && r2.vis) mmVisTake(r2.vis); }).catch(() => {}); };
  document.addEventListener("visibilitychange", () => { if (!document.hidden && $("#p-music").classList.contains("cur")) mmVisStart(); });
  }
  $("#mm-heart").onclick = () => { const n = mmData && mmData.now; if (n) core.call("mm_fav", { path: n.path, on: !n.fav }).then(() => mmRefresh().then(mmLoadList)).catch(e => toast(e.message)); };
}

/* Свои радиостанции (№359, 27.10: «Где можно добавлять потоки радио? В моём случае — радио нашего города»): список,
   «Включить», «×» (второе нажатие — убрать), добавить по названию и ссылке. Ядро: radio_custom_list/add/del/play. */
let rcAsk = "";
async function rcLoad() {
  if (!$("#rc-list")) return;
  let l = [];
  try { l = await core.call("radio_custom_list"); } catch (e) { $("#rc-list").innerHTML = `<li class="hint">${escH(e.message)}</li>`; return; }
  $("#rc-list").innerHTML = (l || []).length ? l.map(x => `<li><span><b>${escH(x.name)}</b><small>${escH(x.url)}</small></span>`
    + `<button class="btn small" data-rcp="${escH(x.url)}">Включить</button><button class="btn small${rcAsk === x.url ? " danger" : ""}" data-rcd="${escH(x.url)}" title="Убрать">${rcAsk === x.url ? "Убрать?" : "×"}</button></li>`).join("")
    : `<li class="hint" style="display:block">Своих станций пока нет — добавьте ниже или пришлите ссылку в чат.</li>`;
  $$("#rc-list [data-rcp]").forEach(b => b.onclick = () => core.call("radio_custom_play", { url: b.dataset.rcp }).then(() => toast("Включаю", 2000)).catch(e => toast(e.message, 4000)));
  $$("#rc-list [data-rcd]").forEach(b => b.onclick = async () => {
    if (rcAsk !== b.dataset.rcd) { rcAsk = b.dataset.rcd; rcLoad(); return; }
    rcAsk = ""; await core.call("radio_custom_del", { url: b.dataset.rcd }).catch(e => toast(e.message)); rcLoad();
  });
}
if ($("#rc-add")) {
  $("#rc-add").onsubmit = async (e) => {
    e.preventDefault();
    try { const st = await core.call("radio_custom_add", { name: $("#rc-name").value, url: $("#rc-url").value, play: true });
          toast(`«${st.name}» добавлена — включаю`, 3000); $("#rc-name").value = ""; $("#rc-url").value = ""; }
    catch (x) { toast(x.message, 4000); }
    rcLoad();
  };
  core.on("hello", () => { if ($("#p-music").classList.contains("cur")) rcLoad(); });
  core.on("radio", () => { if ($("#p-music").classList.contains("cur")) rcLoad(); });
}
