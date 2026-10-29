/* Студия → «Обучение» → «Видеоуроки» (0.69; владелец 29.10: «показывать их в приложении», видео — с его сервера).
   Сетка обложек с номером, названием и длительностью; нажали — плеер поверх (видео с dewiar.pro/dwrapp/academy/ или
   YouTube в браузере). Список — academy_list (cloud.php ?p=/academy: только уроки, чьё видео уже загружено). */
const LSN = { items: null };
const lsMin = (s) => s ? `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}` : "";

async function loadLessons() {
  const g = $("#ls-grid");
  if (!LSN.items) g.innerHTML = `<p class="ls-empty">Загружаю уроки…</p>`;
  try { LSN.items = (await core.call("academy_list")).items || []; }
  catch (e) { g.innerHTML = `<p class="ls-empty">Не получилось загрузить уроки: ${escH(e.message)}</p>`; return; }
  g.innerHTML = LSN.items.length ? LSN.items.map(l => `<button type="button" class="ls-card" data-id="${escH(l.id)}" aria-label="Урок ${l.n}: ${escH(l.title)}">`
      + `<span class="ls-pic"${l.poster ? ` style="background-image:url('${escH(l.poster)}')"` : ""}><i class="ls-play" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M8 5.5v13l11-6.5z"/></svg></i>${l.sec ? `<em>${lsMin(l.sec)}</em>` : ""}</span>`
      + `<span class="ls-txt"><small>Урок ${l.n}</small><b>${escH(l.title)}</b><span>${escH(l.about)}</span></span></button>`).join("")
    : `<p class="ls-empty">Уроки скоро появятся здесь — первый, «Совет ИИ», уже снят.</p>`;
  $$("#ls-grid .ls-card").forEach(b => b.onclick = () => lsPlay(LSN.items.find(x => x.id === b.dataset.id)));
}

function lsPlay(l) {
  if (!l) return;
  if (!l.video && l.youtube) { window.open(l.youtube, "_blank", "noopener"); return; }
  const d = $("#ls-dlg"), v = $("#ls-v");
  $("#ls-dt").textContent = `Урок ${l.n} · ${l.title}`;
  v.poster = l.poster || ""; v.src = l.video;
  d.showModal(); v.play().catch(() => {});
}

(function lsInit() {
  if (!$("#p-lessons")) return;
  const close = () => { const v = $("#ls-v"); v.pause(); v.removeAttribute("src"); v.load(); $("#ls-dlg").close(); };
  $("#ls-x").onclick = close;
  $("#ls-dlg").addEventListener("cancel", (e) => { e.preventDefault(); close(); });
  $("#ls-dlg").addEventListener("click", (e) => { if (e.target === $("#ls-dlg")) close(); });
  window.loadLessons = loadLessons;
})();
