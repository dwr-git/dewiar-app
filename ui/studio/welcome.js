/* Студия Dewiar: окно «Первые шаги» и раздел «Безопасность» (сейф и резервные копии).
   Первые шаги — три пункта (модель отвечает, имя слышно, Telegram подключён); llm_test, tg_get, say и события wake,
   telegram; выбор «потом / готово» хранится в настройке ui.welcome. Сейф: vault_list/put/delete/reveal; копии:
   backup_info/make/restore/inspect/open, папка копий — настройка backup.dir.
   Здесь же объявлены SVG() и значки I_* — ими пользуются файлы ниже (day.js — только при отрисовке).
   Файлы студии подключаются по порядку из ui/settings.html и делят одну глобальную область; wlcBoot зовёт dewiar.js
   после связи с ядром. */
/* ---------- первые шаги (первый запуск) ----------
   wlcHeard — ассистент уже слышал своё имя (событие wake) с момента открытия студии; ядро этого не помнит. */
let wlcEnt = null, wlcHeard = false;
function wlcSet(n, ok, text) {
  const el = $(`.wst[data-s="${n}"]`); if (!el) return;
  el.classList.toggle("ok", !!ok); if (text) el.querySelector("[data-t]").textContent = text;
}
async function wlcRefresh() {
  const prof = S && S.llm && S.llm.profiles && S.llm.profiles[S.llm.active];
  if (!prof) wlcSet(1, false, "Модель ещё не выбрана — выберите, где она будет работать.");
  else {
    wlcSet(1, false, `Проверяю «${prof.name || prof.model}»…`);
    // настоящий запрос к модели: проверяем, что она отвечает, а не только что настроена
    const r = await core.call("llm_test", { profile: prof }).catch(e => ({ error: e.message }));
    wlcBrainOk = !!r.ok;
    wlcSet(1, !!r.ok, r.ok ? `Подключён: ${prof.name || r.model} — отвечает за ${((r.total_ms || 0) / 1000).toFixed(1)} с.` : "Модель не отвечает — выберите другую или проверьте сервер.");
  }
  if (wlcHeard) wlcSet(2, true, "Слышу вас — имя работает.");
  const tg = await core.call("tg_get").catch(() => null);
  if (tg && tg.paired) wlcSet(3, true, `Подключён: @${tg.bot}.`);
  const n = $$(".wst.ok").length; $("#wlc-chip").textContent = `✨ Первые шаги · ${n} из 3`;
}
/* облик и имя текущего персонажа (Лира — с живым лицом) */
function wlcPersona() {
  const p = (typeof personas !== "undefined" && personas || []).find(x => x.id === S.persona) || {};
  $$("#wlc .wn").forEach(el => el.textContent = p.name || "Лира");
  wlcTries(p.name || "Лира");
  if (!$('.wst[data-s="2"]').classList.contains("ok")) $("#wlc-s2").textContent = `Скажите: «${p.name || "Лира"}, привет». Не откликается — научите имени.`;
  return p;
}
function wlcOpen() {
  $("#wlc").classList.add("on");
  const p = wlcPersona();
  const opt = { style: p.avatar_url && p.style !== "aura" ? "photo" : (p.style || "nexus"), color: p.color || "#8A9BFF", image: p.avatar_url || null, live: p.live || "" };
  if (!wlcEnt) wlcEnt = new DewiarEntity($("#wlc-ent"), opt); else wlcEnt.configure(opt);
  wlcEnt.set({ state: "idle", level: 0.2 }); wlcRefresh();
}
function introGo() { core.call("intro_start").then(ok => toast(ok === false ? "Знакомство уже идёт — смотрите виджет" : "Смотрите и слушайте виджет 👋")).catch(e => toast(e.message)); }
function wlcClose(done) {
  $("#wlc").classList.remove("on");
  if (done) { save({ ui: { welcome: "done" } }, true); $("#wlc-chip").classList.remove("on"); }
}
/* После связи с ядром: значок «Первые шаги» в меню, пока не нажато «Готово»; само окно — только если его не отложили
   и не идёт перенос настроек с другого устройства (pending_import или ?import= в адресе) — там своё окно. */
function wlcBoot(d) {
  const w = (S.ui || {}).welcome;
  if (w === "done") return;
  $("#wlc-chip").classList.add("on");
  if (w !== "later" && !d.pending_import && !new URLSearchParams(location.search).get("import")) wlcOpen();
}
$$("#wlc [data-go]").forEach(b => b.onclick = () => { wlcClose(false); save({ ui: { welcome: "later" } }, true); $(`nav button[data-p="${b.dataset.go}"]`).click(); });
$("#wlc-later").onclick = () => { wlcClose(false); save({ ui: { welcome: "later" } }, true); toast("Вернуться — «Первые шаги» внизу меню"); };
$("#wlc-done").onclick = () => wlcClose(true);
$("#wlc-chip").onclick = () => wlcOpen();
$("#wlc-intro").onclick = () => { wlcClose(false); introGo(); };
$("#ab-intro").onclick = introGo;
core.on("intro", e => { if (wlcEnt && e && e.step) wlcEnt.set({ state: e.step === "done" ? "idle" : "speaking" }); });
/* «Попробуйте сказать»: то, что работает сразу после подключения мозга, без настроек (отзыв 18.10: «сказал привет — а что
   делать дальше, ума не приложу»). {n} — имя персонажа. Нажали — фраза уходит ассистенту, ответ в виджете. */
const WLC_TRIES = ["{n}, что ты умеешь?", "Напомни через 10 минут позвонить маме", "Какая погода завтра?",
  "Включи спокойное радио", "Что нового в мире сегодня?", "Запиши заметку: купить хлеб"];
let wlcBrainOk = false;
function wlcTries(name) {
  const box = $("#wlc-tlist"); if (!box) return;
  box.innerHTML = WLC_TRIES.map(t => { const q = t.replace("{n}", name); return `<button class="tq" data-q="${escH(q)}" title="Отправить ассистенту"><i><svg viewBox="0 0 24 24"><path d="M8 5.5v13l10.5-6.5z"/></svg></i>${escH(q)}</button>`; }).join("");
  $$(".tq", box).forEach(b => b.onclick = () => {
    if (!wlcBrainOk) { toast("Сначала шаг 1 — выберите, кто будет думать"); return; }
    core.call("say", { text: b.dataset.q }).then(() => { b.classList.add("sent"); toast("Отправил ассистенту — ответ в виджете"); }).catch(e => toast(e.message));
  });
}
core.on("wake", e => { if (e && !wlcHeard) { wlcHeard = true; if ($("#wlc").classList.contains("on")) wlcSet(2, true, "Слышу вас — имя работает."); } });
core.on("telegram", e => { if (e && e.paired) wlcSet(3, true, `Подключён: @${e.bot}.`); });

/* ---------- безопасность: сейф и резервная копия ----------
   vault_list отдаёт только названия и длину значения; само значение приходит лишь по vault_reveal
   («Показать» — на 15 секунд, «Скопировать») и в разметку списка не попадает. */
const SVG = (d) => `<svg viewBox="0 0 24 24">${d}</svg>`;
const I_EYE = '<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="2.8"/>';
const I_COPY = '<rect x="8.5" y="8.5" width="11.5" height="11.5" rx="2.2"/><path d="M15.5 8.5V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v7.5a2 2 0 0 0 2 2h2.5"/>';
const I_DEL = '<path d="M4.5 7h15M10 11v6M14 11v6M6.5 7l1 12.5a1.5 1.5 0 0 0 1.5 1.4h6a1.5 1.5 0 0 0 1.5-1.4L17.5 7M9.5 7V4.8h5V7"/>';
const I_RESTORE = '<path d="M3.5 12a8.5 8.5 0 1 0 2.6-6.1"/><path d="M3.5 4.5v4h4"/>';
const I_KEY = '<circle cx="8" cy="15" r="4"/><path d="m10.8 12.2 8.7-8.7M16.5 6.5l2.5 2.5M14 9l2 2"/>';
const I_LOCK = '<rect x="5" y="10.5" width="14" height="10" rx="2.5"/><path d="M8.5 10.5V7.5a3.5 3.5 0 0 1 7 0v3"/>';
const I_BOX = '<path d="M4 7.5 12 4l8 3.5v9L12 20l-8-3.5z"/><path d="M4 7.5 12 11l8-3.5M12 11v9"/>';
/* «Безопасность» → карточка «Сейф»: сколько записей и кнопка в «Сейф паролей» (studio/vault.js, 0.45) */
async function loadVault() {
  try { const n = ((await core.call("vault_list")).items || []).length;
    $("#v-count").textContent = n ? `в сейфе: ${n}` : "пока пусто"; } catch (e) { $("#v-count").textContent = e.message; }
}
$("#v-open").onclick = () => { const b = $('nav button[data-p="vault"]'); if (b) b.click(); };
let bkInfo = null;
const bkDate = (iso) => { try { const d = new Date(iso); return d.toLocaleDateString("ru-RU", { day: "numeric", month: "long" }) + ", " + d.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" }); } catch (e) { return iso; } };
function renderBackups(info) {
  bkInfo = info; $("#bk-where").textContent = "Папка: " + info.dir;
  const it = info.items || [];
  $("#bk-list").innerHTML = it.length ? it.map(x => `<div class="ritem" data-path="${escH(x.path)}" data-enc="${x.encrypted ? 1 : 0}" data-time="${escH(x.time || "")}">
    <div class="ico${x.encrypted ? "" : " k"}">${SVG(x.encrypted ? I_LOCK : I_BOX)}</div>
    <div class="rbody"><div class="rtext">${escH(bkDate(x.time))}${x.auto ? " · автоматически" : x.label && x.label !== "копия" ? " · " + escH(x.label) : ""}</div>
    <div class="rmeta"><span>${escH(x.size_text)}</span><span>заметок и файлов: ${(x.counts || {}).workspace || 0}</span>${x.encrypted ? `<span class="rbadge">с паролем${x.vault ? " · сейф" : ""}</span>` : ""}${x.host && x.host !== info.host ? `<span class="rbadge k">с компьютера «${escH(x.host)}»</span>` : ""}</div></div>
    <div class="ract"><button data-b="restore" title="Восстановить из этой копии">${SVG(I_RESTORE)}</button></div></div>`).join("")
    : `<p class="hint" style="margin:0">Копий пока нет.</p>`;
  $$("#bk-list [data-b=restore]").forEach(b => b.onclick = () => { const r = b.closest(".ritem"); bkRestore(r.dataset.path, r.dataset.enc === "1", r.dataset.time); });
}
async function loadBackups() { try { renderBackups(await core.call("backup_info")); } catch (e) { $("#bk-res").className = "res bad"; $("#bk-res").textContent = e.message; } }
/* Восстановить из копии: ядро сначала сохраняет текущее состояние копией «до восстановления», затем перезапускается —
   восстановленные настройки читаются только при запуске. Сейф из копии с паролем заменяет здешний целиком (core/backup.py). */
async function bkRestore(path, enc, when) {
  const r = $("#bk-res"); let password = "";
  if (enc) { password = await askText("Пароль этой копии:") || ""; if (!password) return; }
  if (!await ask(`Восстановить из копии${when ? " от " + bkDate(when) : ""}?\n\nФайлы из копии заменят одноимённые; ничего не удаляется. Текущее состояние сначала сохранится отдельной копией. Ассистент перезапустится.`)) return;
  r.className = "res"; r.textContent = "восстанавливаю…";
  try { const x = await core.call("backup_restore", { path, password });
        r.className = "res ok"; r.textContent = `Восстановлено: ${x.files} файлов${x.vault ? ", сейф — " + x.vault : ""}. Ассистент перезапускается…`; }
  catch (e) { r.className = "res bad"; r.textContent = e.message; }
}
$("#bk-make").onclick = async (ev) => {
  const r = $("#bk-res"); ev.target.disabled = true; r.className = "res"; r.textContent = "делаю копию…";
  try { const x = await core.call("backup_make", { password: $("#bk-pass").value }); $("#bk-pass").value = "";
        r.className = "res ok"; r.textContent = `Готово: ${x.name} (${x.size_text})`; loadBackups(); }
  catch (e) { r.className = "res bad"; r.textContent = e.message; } finally { ev.target.disabled = false; }
};
$("#bk-open").onclick = () => core.call("backup_open").catch(e => toast(e.message));
$("#bk-dir").onclick = async () => { const a = api(); if (!a) return toast("Выбор папки доступен в окне студии"); const p = await a.pick_folder(); if (!p) return;
  await save({ backup: { dir: p } }, true); loadBackups(); };
$("#bk-file").onclick = async () => { const a = api(); if (!a || !a.pick_file) return toast("Выбор файла доступен в окне студии");
  const p = await a.pick_file("Слепок Dewiar (*.dwr;*.zip;*.dwbak)"); if (!p) return;
  try { const x = await core.call("backup_inspect", { path: p }); bkRestore(p, !!x.encrypted, x.time); } catch (e) { toast(e.message); } };
