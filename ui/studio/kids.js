/* Студия Dewiar, раздел «Дети» (27.10, по макету «Dewiar — новые режимы»): детский режим — ребёнок, друг-персонаж,
   PIN родителя, что можно, время за день, отчёт. Ядро: kids_get, kids_set, kids_pin {pin, old}, kids_on {on, pin},
   kids_unlock {pin}, kids_lock; событие «kids». Пока режим включён и PIN не введён — студия закрыта заслонкой #kd-lock
   (ядро и само не даёт окнам менять настройки: engine_commands._kids_blocked). */
let KD = null, kdPinAsk = "";
const kdMin = (n) => `${n} ${plural(n, "минута", "минуты", "минут")}`;
function kdLock(d) {
  const l = $("#kd-lock"), lock = !!(d && d.locked);
  l.hidden = !lock;
  document.body.classList.toggle("kd-locked", lock);
  if (lock) { $("#kd-lava").src = d.friend || ""; setTimeout(() => $("#kd-lpin").focus(), 50); }
}
function kdRender() {
  const d = KD;
  if (!d || !$("#p-kids")) return;
  kdLock(d);
  const ch = d.child || {};
  const name = (ch.name || "").trim();
  // полоса состояния: выключен — что нужно, чтобы включить; включён — кто, сколько осталось, «Выключить»
  $("#kd-bar").className = "kd-bar" + (d.on ? " on" : "");
  $("#kd-bar").innerHTML = d.on
    ? `<div><b>Включён${name ? ": " + escH(name) : ""}</b><span>${d.can_talk ? `Осталось сегодня: ${kdMin(d.left)}` : escH(d.why)}. Отвечает ${escH(d.friend_name)}.</span></div>`
      + `<button class="btn" id="kd-off">Выключить</button>`
    : `<div><b>Выключен</b><span>${d.has_pin ? "Всё готово — можно включать." : "Сначала задайте PIN родителя — ниже, в карточке ребёнка."}</span></div>`
      + `<button class="btn primary" id="kd-onb">Включить детский режим</button>`;
  if ($("#kd-onb")) $("#kd-onb").onclick = () => d.has_pin ? kdCall("kids_on", { on: true }, `Детский режим включён. Отвечает ${d.friend_name}.`)
    : (toast("Сначала задайте PIN родителя — в карточке ребёнка", 3500), $("#kd-pnew") && $("#kd-pnew").focus());
  if ($("#kd-off")) $("#kd-off").onclick = () => kdCall("kids_on", { on: false }, "Детский режим выключен.");
  const edit = !d.on || d.unlocked;
  $("#kd-ava").textContent = (name || "?")[0].toUpperCase();
  if (document.activeElement !== $("#kd-name")) $("#kd-name").value = name;
  if (document.activeElement !== $("#kd-age")) $("#kd-age").value = ch.age || "";
  $("#kd-fava").src = d.friend || "";
  [$("#kd-name"), $("#kd-age"), $("#kd-wd"), $("#kd-we"), $("#kd-bed"), $("#kd-morn")].forEach(x => x.disabled = !edit);
  // PIN: задать (первый раз) или сменить
  $("#kd-pinrow").innerHTML = d.has_pin && kdPinAsk !== "change"
    ? `<span class="kd-dots" aria-label="PIN задан">••••</span><button class="btn small" id="kd-pinch">Изменить</button>`
    : `${d.has_pin ? `<input type="password" id="kd-pold" inputmode="numeric" maxlength="8" placeholder="Прежний" aria-label="Прежний PIN">` : ""}`
      + `<input type="password" id="kd-pnew" inputmode="numeric" maxlength="8" placeholder="${d.has_pin ? "Новый" : "4–8 цифр"}" aria-label="Новый PIN">`
      + `<button class="btn small primary" id="kd-pset">${d.has_pin ? "Сохранить" : "Задать PIN"}</button>`;
  if ($("#kd-pinch")) $("#kd-pinch").onclick = () => { kdPinAsk = "change"; kdRender(); };
  if ($("#kd-pset")) $("#kd-pset").onclick = async () => {
    try { KD = await core.call("kids_pin", { pin: $("#kd-pnew").value, old: $("#kd-pold") ? $("#kd-pold").value : "" }); kdPinAsk = ""; toast("PIN сохранён", 2500); kdRender(); }
    catch (e) { toast(e.message, 4000); }
  };
  // что можно
  const names = d.allow_names || {}, on = new Set(d.allow || []);
  $("#kd-allow").innerHTML = Object.keys(names).map(k => `<button class="chip${on.has(k) ? " on" : ""}" data-k="${escH(k)}" aria-pressed="${on.has(k)}"${edit ? "" : " disabled"}>${escH(names[k])}</button>`).join("");
  $$("#kd-allow .chip").forEach(b => b.onclick = () => {
    const s = new Set(KD.allow || []); s.has(b.dataset.k) ? s.delete(b.dataset.k) : s.add(b.dataset.k);
    kdCall("kids_set", { allow: [...s] });
  });
  // время
  const pct = d.limit ? Math.min(100, Math.round(d.used / d.limit * 100)) : 100;
  $("#kd-ring .fg").setAttribute("stroke-dasharray", `${pct} 100`);
  $("#kd-used").textContent = `${d.used} мин`;
  $("#kd-of").textContent = `сегодня из ${d.limit}`;
  [["#kd-wd", d.min_weekday], ["#kd-we", d.min_weekend], ["#kd-bed", d.bedtime], ["#kd-morn", d.morning]].forEach(([s, v]) => { if (document.activeElement !== $(s)) $(s).value = v ?? ""; });
  // отчёт: вне правил — сверху; о чём спрашивал — последние вопросы
  const r = d.report;
  $("#kd-report").innerHTML = !r ? `<p class="kd-note">Отчёт виден после PIN родителя.</p>`
    : (r.off.length ? `<div class="kd-off">${r.off.map(x => `<div><time>${escH(x.t)}</time> Вне правил: «${escH(x.q)}» — ${escH(d.friend_name)} отказал и предложил спросить вас.</div>`).join("")}</div>` : "")
      + (r.asked.length ? `<ul class="kd-asked">${r.asked.slice(-12).reverse().map(x => `<li><time>${escH(x.t)}</time>${escH(x.q)}</li>`).join("")}</ul>`
        : `<p class="kd-note">Сегодня ещё не разговаривали.</p>`);
}
async function kdCall(cmd, args, ok) {
  try { KD = Object.assign(KD || {}, await core.call(cmd, args)); if (ok) toast(ok, 2500); }
  catch (e) { toast(e.message, 4000); }
  kdLoad();
}
async function kdLoad() {
  try { KD = await core.call("kids_get"); } catch (e) { return; }
  kdRender();
}
window.loadKids = kdLoad;
if ($("#p-kids")) {
  const saveF = (f, v) => kdCall("kids_set", { [f]: v });
  $("#kd-name").onchange = () => kdCall("kids_set", { child: { name: $("#kd-name").value, age: $("#kd-age").value } });
  $("#kd-age").onchange = () => kdCall("kids_set", { child: { name: $("#kd-name").value, age: $("#kd-age").value } });
  $("#kd-wd").onchange = () => saveF("min_weekday", +$("#kd-wd").value || 0);
  $("#kd-we").onchange = () => saveF("min_weekend", +$("#kd-we").value || 0);
  $("#kd-bed").onchange = () => saveF("bedtime", $("#kd-bed").value);
  $("#kd-morn").onchange = () => saveF("morning", $("#kd-morn").value);
  $("#kd-lockf").onsubmit = async (e) => {
    e.preventDefault();
    try { KD = Object.assign(KD || {}, await core.call("kids_unlock", { pin: $("#kd-lpin").value })); $("#kd-lpin").value = ""; $("#kd-lerr").textContent = ""; kdLoad(); }
    catch (x) { $("#kd-lerr").textContent = x.message; $("#kd-lpin").select(); }
  };
  core.on("kids", (e) => { KD = Object.assign(KD || {}, e); kdRender(); });
  core.on("hello", () => kdLoad());
}
