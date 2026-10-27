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
  $("#mm-pp").textContent = s && s.paused || !n ? "▶" : "⏸";
  $("#mm-pp").title = s && s.paused || !n ? "Играть" : "Пауза";
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
function loadMyMusic() { mmRefresh().then(mmLoadList); if (typeof rcLoad === "function") rcLoad(); }
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
