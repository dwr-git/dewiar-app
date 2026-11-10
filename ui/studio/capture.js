/* Студия → «Звук и поведение» → «Закинуть идею одной клавишей»: включить, сменить сочетание, попробовать. Всё — через
   окно программы (Api.capture_status / capture_set / show_capture в ui/app.py): сочетание назначает интерфейс — на
   Windows RegisterHotKey, в GNOME своё сочетание клавиатуры (ui/hotkey.py). В браузере (студия без окна) — только подсказка. */
function capRender(st) {
  if (!st) { $("#cap-st").textContent = "Сочетание назначает окно программы — откройте студию из Dewiar, не из браузера."; return; }
  $("#cap-on").checked = !!st.on; $("#cap-key").value = st.key || "Ctrl+Alt+N";
  const el = $("#cap-st");
  el.className = "hint " + (st.error ? "bad" : st.works ? "ok" : "");
  el.textContent = st.error ? st.error : !st.on ? "Выключено." : st.works ? `${st.key} — ${st.how}` : (st.how || "Сочетание пока не работает.");
  $("#cap-cmdh").hidden = !st.on || st.works || !st.command; $("#cap-cmd").textContent = st.command || "";
}
async function capLoad() {
  const a = window.api && window.api();
  try { capRender(a && a.capture_status ? await a.capture_status() : null); } catch (e) { capRender(null); }
}
async function capSave() {
  const a = window.api && window.api(); if (!a || !a.capture_set) return capRender(null);
  $("#cap-st").className = "hint"; $("#cap-st").textContent = "…";
  try { capRender(await a.capture_set($("#cap-on").checked, $("#cap-key").value.trim())); } catch (e) { $("#cap-st").textContent = e.message; }
}
$("#cap-on").onchange = capSave;
$("#cap-key").onchange = capSave;
$("#cap-key").onkeydown = (e) => { if (e.key === "Enter") { e.preventDefault(); capSave(); } };
$("#cap-try").onclick = () => { const a = window.api && window.api(); if (a && a.show_capture) a.show_capture(); else toast("Окно открывается из программы Dewiar"); };
{ const b = $('nav button[data-p="sound"]'); if (b) b.addEventListener("click", capLoad); }
window.addEventListener("pywebviewready", () => { if ($("#p-sound").classList.contains("cur")) capLoad(); });
/* Идея №154: «Позвать Лиру» одной клавишей (Api.mic_status / mic_set; ui/hotkey.py kind="mic"). Сочетание можно не
   печатать, а нажать прямо в поле — оно впишется само (и в поле «Закинуть идею» тоже). */
function micRender(st) {
  if (!st) { $("#mic-st").textContent = "Сочетание назначает окно программы — откройте студию из Dewiar, не из браузера."; return; }
  $("#mic-on").checked = !!st.on; $("#mic-key").value = st.key || "Ctrl+Alt+Space"; $("#mic-act").value = st.action || "call";
  const el = $("#mic-st");
  el.className = "hint " + (st.error ? "bad" : st.works ? "ok" : "");
  el.textContent = st.error ? st.error : !st.on ? "Выключено." : st.works ? `${st.key} — ${st.how}` : (st.how || "Сочетание пока не работает.");
  $("#mic-cmdh").hidden = !st.on || st.works || !st.command; $("#mic-cmd").textContent = st.command || "";
}
async function micLoad() {
  const a = window.api && window.api();
  try { micRender(a && a.mic_status ? await a.mic_status() : null); } catch (e) { micRender(null); }
}
async function micSave() {
  const a = window.api && window.api(); if (!a || !a.mic_set) return micRender(null);
  $("#mic-st").className = "hint"; $("#mic-st").textContent = "…";
  try { micRender(await a.mic_set($("#mic-on").checked, $("#mic-key").value.trim(), $("#mic-act").value)); } catch (e) { $("#mic-st").textContent = e.message; }
}
// нажатое сочетание -> «Ctrl+Alt+Space» (по коду клавиши — раскладка не важна)
function keyCombo(e) {
  const mods = [e.ctrlKey && "Ctrl", e.altKey && "Alt", e.shiftKey && "Shift", e.metaKey && "Win"].filter(Boolean);
  const c = e.code || "";
  const key = c === "Space" ? "Space" : /^Key[A-Z]$/.test(c) ? c.slice(3) : /^Digit\d$/.test(c) ? c.slice(5) : /^F([1-9]|1[0-2])$/.test(c) ? c : "";
  return mods.length && key && !(mods.length === 1 && mods[0] === "Shift") ? mods.concat(key).join("+") : "";
}
[["#cap-key", capSave], ["#mic-key", micSave]].forEach(([sel, fn]) => {
  const inp = $(sel); if (!inp) return;
  inp.addEventListener("keydown", (e) => { const k = keyCombo(e); if (!k) return; e.preventDefault(); e.stopPropagation(); inp.value = k; fn(); }, true);
});
$("#mic-on").onchange = micSave;
$("#mic-key").onchange = micSave;
$("#mic-act").onchange = micSave;
{ const b = $('nav button[data-p="sound"]'); if (b) b.addEventListener("click", micLoad); }
window.addEventListener("pywebviewready", () => { if ($("#p-sound").classList.contains("cur")) micLoad(); });
