/* Студия → «Обучение» → «Видеоуроки» (0.69; владелец 29.10: «показывать их в приложении», видео — с его сервера).
   Сетка обложек с номером, названием и длительностью; нажали — плеер поверх (видео с dewiar.pro/dwrapp/academy/ или
   YouTube в браузере). Список — academy_list (cloud.php ?p=/academy: только уроки, чьё видео уже загружено). */
const LSN = { items: null, files: {} };
/* Файл урока — через ядро, на диск (academy_file; 30.10, владелец, Ubuntu: «„Смотреть“ — бесполезно, обложки нет; может,
   потому что я в подсети сайта?»). Окно грузит картинки и видео само, а изнутри сети сайта публичный домен часто не
   открывается; ядро знает рабочую дорогу (дома — напрямую). Скачали раз — дальше с диска. Не вышло — "" (берём ссылку). */
async function lsLocal(url) {
  if (!url || !/^https?:/i.test(url)) return "";
  if (LSN.files[url]) return LSN.files[url];
  try { const r = await core.call("academy_file", { url }); if (r && r.uri) return (LSN.files[url] = r.uri); } catch (e) { }
  return "";
}
function lsPosters(root) {
  $$("[data-poster]", root).forEach(async el => { const u = await lsLocal(el.dataset.poster); if (u) el.style.backgroundImage = `url('${u.replace(/'/g, "%27")}')`; });
}
/* Урок в «?» раздела (30.10, владелец: «выручает вопросик на каждой странице… что если бы сразу и видео подходящее
   смотреть? в каждом разделе минимум одно видео»). Какие разделы у урока — поле sections в academy/lessons.json на сайте
   (новый урок встаёт в свой раздел без обновления программы); у сайта старше 0.72 полей нет — эта запасная таблица. */
const LS_SECT = { "01-council": ["council"], "02-watch": ["watch"], "03-leads": ["sitechat", "clients"], "04-team": ["team"], "05-clients": ["clients"],
  "06-mailing": ["mailing"], "07-posts": ["pbot"], "08-prompter": ["prompter"], "09-docs": ["docs", "folder"], "10-mail": ["connect"],
  "11-jobs": ["reminders"], "12-morning": ["home", "calendar"], "13-money": ["pay", "family"], "14-tasks": ["tasks"] };
async function lsList() {
  if (Array.isArray(LSN.items)) return LSN.items;
  if (typeof HM !== "undefined" && HM.ac && HM.ac.d && Array.isArray(HM.ac.d.items)) return (LSN.items = HM.ac.d.items);
  try { LSN.items = (await core.call("academy_list")).items || []; } catch (e) { return []; }
  return LSN.items;
}
async function lsFor(section) {
  return (await lsList()).filter(l => (Array.isArray(l.sections) && l.sections.length ? l.sections : LS_SECT[l.id] || []).includes(section))
    .sort((a, b) => a.n - b.n);
}
const lsMin = (s) => s ? `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}` : "";

async function loadLessons() {
  const g = $("#ls-grid");
  if (!LSN.items) g.innerHTML = `<p class="ls-empty">Загружаю уроки…</p>`;
  try { LSN.items = (await core.call("academy_list")).items || []; }
  catch (e) { g.innerHTML = `<p class="ls-empty">Не получилось загрузить уроки: ${escH(e.message)}</p>`; return; }
  g.innerHTML = LSN.items.length ? LSN.items.map(l => `<button type="button" class="ls-card" data-id="${escH(l.id)}" aria-label="Урок ${l.n}: ${escH(l.title)}">`
      + `<span class="ls-pic"${l.poster ? ` data-poster="${escH(l.poster)}" style="background-image:url('${escH(l.poster)}')"` : ""}><i class="ls-play" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M8 5.5v13l11-6.5z"/></svg></i>${l.sec ? `<em>${lsMin(l.sec)}</em>` : ""}</span>`
      + `<span class="ls-txt"><small>Урок ${l.n}</small><b>${escH(l.title)}</b><span>${escH(l.about)}</span></span></button>`).join("")
    : `<p class="ls-empty">Уроки скоро появятся здесь — первый, «Совет ИИ», уже снят.</p>`;
  $$("#ls-grid .ls-card").forEach(b => b.onclick = () => lsPlay(LSN.items.find(x => x.id === b.dataset.id)));
  lsPosters(g);
}

/* посмотрели урок — на «Главной» его карточки больше нет (home.js hmLesson): отметка — время просмотра (плюс), показа — минус */
function lsSeen(id) {
  if (!S) return;
  const ui = (S && S.ui) || {}, m = Object.assign({}, ui.lessons_seen || {}, { [id]: Date.now() });
  S.ui = Object.assign({}, ui, { lessons_seen: m }); save({ ui: { lessons_seen: m } }, true);
}
async function lsPlay(l) {
  if (!l) return;
  lsSeen(l.id);
  if (!l.video && l.youtube) { window.open(l.youtube, "_blank", "noopener"); return; }
  const d = $("#ls-dlg"), v = $("#ls-v"), fail = $("#ls-fail");
  $("#ls-dt").textContent = `Урок ${l.n} · ${l.title}`;
  fail.hidden = true; v.hidden = false; LSN.cur = l;
  // 30.10: WebM (VP9) окно в Ubuntu играет без gstreamer1.0-libav — берём его, если сервер уже сделал копию и окно умеет
  const webm = !!(l.webm && v.canPlayType('video/webm; codecs="vp9, opus"'));
  const src = webm ? l.webm : l.video, load = $("#ls-load");
  v.poster = LSN.files[l.poster] || l.poster || ""; v.removeAttribute("src");
  if (!d.open) d.showModal();
  clearTimeout(LSN.t);
  if (!LSN.files[src] && load) { load.hidden = false; }
  const loc = await lsLocal(src);                         // через ядро: дома и в сети сайта — тоже играет
  if (load) load.hidden = true;
  if (LSN.cur !== l || !d.open) return;
  v.src = loc || src; v.play().catch(() => {});
  // окно программы не смогло: ошибка видео или за 8 секунд ни кадра (Ubuntu без gstreamer1.0-libav — чёрный экран)
  const linux = /Linux/i.test(navigator.userAgent) && !/Android/i.test(navigator.userAgent);
  const bad = (why) => { if (LSN.cur !== l || !d.open) return; clearTimeout(LSN.t); fail.hidden = false; v.pause();
    lsCodecBtn(linux);
    $("#ls-fail-why").textContent = why || (linux ? LS_CODEC_WHY : "Откройте его в браузере — там оно играет всегда."); };
  v.onerror = () => bad("");
  // 30.10: кодека нет — окно знает это сразу (canPlayType пустой), не ждём 8 секунд чёрного экрана
  if (linux && !webm && !v.canPlayType('video/mp4; codecs="avc1.42E01E"')) return bad("");
  LSN.t = setTimeout(() => { if (v.readyState < 2) bad(""); }, 8000);
  v.onloadeddata = () => clearTimeout(LSN.t);
}
/* Кнопка «Установить видеокодек» (30.10, владелец, Ubuntu: «не открывается видео, только в браузере»): система спросит пароль,
   поставит gstreamer1.0-libav — и «Перезапустить Dewiar», чтобы окно его увидело. */
const LS_CODEC_WHY = "Окну программы в Linux не хватает видеокодека — его можно поставить одной кнопкой (система спросит пароль от компьютера). Или смотрите в браузере.";
function lsCodecBtn(linux) {
  const b = $("#ls-codec"), a = window.api && window.api();
  if (!b) return;
  b.hidden = !(linux && a && a.install_codec);
  if (LSN.codec === "done") { b.textContent = "Перезапустить Dewiar"; return; }
  b.textContent = "Установить видеокодек"; b.disabled = false;
}
async function lsCodec() {
  const b = $("#ls-codec"), why = $("#ls-fail-why"), a = window.api && window.api();
  if (!a) return;
  if (LSN.codec === "done") { if (a.restart) a.restart("Видеокодек установлен — уроки откроются в окне программы."); return; }
  b.disabled = true; b.textContent = "Ставлю… введите пароль в окне системы";
  let r; try { r = await a.install_codec(); } catch (e) { r = { ok: false, error: String(e && e.message || e) }; }
  b.disabled = false;
  if (r && r.ok) { LSN.codec = "done"; b.textContent = "Перезапустить Dewiar"; why.textContent = "Видеокодек установлен. Перезапустите Dewiar — и уроки будут играть прямо здесь."; return; }
  b.textContent = "Установить видеокодек"; why.textContent = "Не получилось: " + ((r && r.error) || "неизвестная ошибка") + ". Пока можно смотреть в браузере.";
}

(function lsInit() {
  if (!$("#p-lessons")) return;
  if ($("#ls-dlg") && $("#ls-dlg").parentNode !== document.body) document.body.appendChild($("#ls-dlg"));
  if ($("#ls-codec")) $("#ls-codec").onclick = lsCodec;
  const close = () => { clearTimeout(LSN.t); if ($("#ls-load")) $("#ls-load").hidden = true; const v = $("#ls-v"); v.pause(); v.removeAttribute("src"); v.load(); $("#ls-dlg").close(); };
  $("#ls-x").onclick = close;
  $("#ls-ext").onclick = () => { const l = LSN.cur; if (!l) return; close(); const u = LSN.files[l.video] || l.video || l.youtube; if (typeof openExt === "function") openExt(u); else window.open(u, "_blank", "noopener"); };
  $("#ls-dlg").addEventListener("cancel", (e) => { e.preventDefault(); close(); });
  $("#ls-dlg").addEventListener("click", (e) => { if (e.target === $("#ls-dlg")) close(); });
  window.loadLessons = loadLessons;
})();
