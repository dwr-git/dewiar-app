/* Студия → «Сейф паролей» (0.45, владелец: «иконку-кнопку „Сейф паролей“ — чтобы удобно было действительно там сохранять
   пароли, и потом искать нужный пароль от нужного сервиса»). Ядро — core/vault.py (vault_list / reveal / put / delete):
   список приходит БЕЗ значений, пароль — только по vault_reveal, на 15 секунд на экране или в буфер обмена.
   Копирование — через окно (api.clip_secret): в буфер с пометкой «не в журнал буфера» (Windows) и стирание через 30 с, если
   там всё ещё этот пароль. Поиск — по названию, логину, сайту и заметке; Enter — скопировать первый найденный. */
const VL = { items: [], edit: null, loaded: false };
const VL_SHOW_MS = 15000, VL_CLIP_S = 30;
const vlNorm = (s) => String(s || "").toLowerCase().replace(/ё/g, "е").replace(/wi-?fi|вай-?\s?фа[а-я]*|вифи/g, "вайфай");
const vlCol = (s) => { const c = ["#5b8def", "#e0795a", "#2fae74", "#c98a1b", "#d4588f", "#4aa3a3", "#8a6ee0", "#d25b5b"];
  return c[[...vlNorm(s)].reduce((a, ch) => a + ch.charCodeAt(0), 0) % c.length]; };
const vlMono = (s) => { const w = String(s || "?").replace(/^(пароль|пин-?код|код|логин)\s+(от|для|к|на)?\s*/i, "").trim() || String(s || "?");
  return /^(wi-?fi|вай-?\s?фа)/i.test(w) ? "Wi" : w.slice(0, 1).toUpperCase(); };
const vlHost = (u) => { const m = /^(?:https?:\/\/)?([^/\s?#]+)/i.exec(String(u || "").trim()); return m ? m[1].replace(/^www\./, "") : ""; };
function vlMark(text, q) {
  const t = String(text || ""); if (!q) return escH(t);
  const i = vlNorm(t).indexOf(q); if (i < 0 || vlNorm(t).length !== t.length) return escH(t);
  return escH(t.slice(0, i)) + "<mark>" + escH(t.slice(i, i + q.length)) + "</mark>" + escH(t.slice(i + q.length));
}
const vlHits = (q) => VL.items.filter(x => !q || [x.name, x.login, x.url, x.note].some(f => vlNorm(f).includes(q)));

async function loadVaultPage() {
  try { VL.items = (await core.call("vault_list")).items || []; VL.loaded = true; }
  catch (e) { $("#vl-list").innerHTML = `<p class="res bad">${escH(e.message)}</p>`; return; }
  vlRender();
  if (!VL.edit) setTimeout(() => { if ($("#p-vault").classList.contains("cur")) $("#vl-q").focus(); }, 60);
}
function vlRender() {
  const q = vlNorm($("#vl-q").value.trim()), list = vlHits(q), box = $("#vl-list");
  if (!VL.items.length) {
    box.innerHTML = `<div class="vl-empty"><div class="vl-lock" aria-hidden="true"><svg viewBox="0 0 48 48"><rect x="10" y="21" width="28" height="21" rx="6"/><path d="M16 21v-5a8 8 0 0 1 16 0v5"/><circle cx="24" cy="31" r="2.6"/><path d="M24 33.6v3"/></svg></div>
      <b>В сейфе пока пусто</b><span>Нажмите «Добавить» — или скажите Лире: «запомни пароль от вайфая: …». Пароль будет здесь, вслух его никто не услышит.</span></div>`;
    return;
  }
  box.innerHTML = (list.length ? list.map(x => {
    const host = vlHost(x.url);
    return `<article class="vl-item" data-id="${escH(x.id)}">
      <i class="vl-mono" style="--c:${vlCol(x.name)}" aria-hidden="true">${escH(vlMono(x.name))}</i>
      <div class="vl-body"><b class="vl-name">${vlMark(x.name, q)}</b>
        <div class="vl-meta">${x.login ? `<button class="vl-login" data-v="login" title="Скопировать логин">${vlMark(x.login, q)}</button>` : ""}${host ? `<a href="#" class="vl-site" data-ext="${escH(/^https?:/i.test(x.url) ? x.url : "https://" + x.url)}" title="Открыть сайт">${vlMark(host, q)}</a>` : ""}${x.note ? `<span class="vl-note">${vlMark(x.note, q)}</span>` : ""}</div></div>
      <code class="vl-val" aria-label="пароль скрыт">${"•".repeat(Math.min(12, Math.max(6, x.length || 8)))}</code>
      <div class="vl-act"><button class="vl-ib" data-v="show" title="Показать на 15 секунд" aria-label="Показать пароль «${escH(x.name)}»">${SVG(I_EYE)}</button>
        <button class="vl-ib vl-copy" data-v="copy" title="Скопировать пароль — сотрётся из буфера через ${VL_CLIP_S} с" aria-label="Скопировать пароль «${escH(x.name)}»">${SVG(I_COPY)}</button>
        <button class="vl-ib" data-v="edit" title="Изменить" aria-label="Изменить «${escH(x.name)}»">${SVG('<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="m13.5 6.5 4 4"/>')}</button></div></article>`;
  }).join("") : `<p class="hint vl-none">Ничего не нашлось по «${escH($("#vl-q").value.trim())}». <a href="#" id="vl-add-q">Добавить такую запись</a></p>`)
    + `<p class="hint vl-count">${q ? `Найдено: ${list.length} из ${VL.items.length}${list.length ? " · Enter — скопировать первый" : ""}` : `Записей: ${VL.items.length}`}</p>`;
  $$("#vl-list .vl-item").forEach(row => {
    const x = VL.items.find(i => i.id === row.dataset.id);
    $$("[data-v]", row).forEach(b => b.onclick = (e) => { e.preventDefault(); vlAct(b.dataset.v, x, row); });
    const site = $(".vl-site", row); if (site) site.onclick = (e) => { e.preventDefault(); openExt(site.dataset.ext); };
  });
  if ($("#vl-add-q")) $("#vl-add-q").onclick = (e) => { e.preventDefault(); vlForm(null, $("#vl-q").value.trim()); };
}
async function vlCopy(text, what) {
  const a = window.pywebview && window.pywebview.api;
  let ok = false;
  try { if (a && a.clip_secret) ok = !!(await a.clip_secret(text, VL_CLIP_S)); } catch (e) { ok = false; }
  if (!ok) {                                                  // окна нет (браузер) — копирует страница и стирает сама
    await navigator.clipboard.writeText(text);
    setTimeout(async () => { try { if (await navigator.clipboard.readText() === text) await navigator.clipboard.writeText(""); } catch (e) { } }, VL_CLIP_S * 1000);
  }
  toast(`${what} скопирован — сотрётся из буфера через ${VL_CLIP_S} с`, 2600);
}
async function vlAct(v, x, row) {
  if (!x) return;
  try {
    if (v === "edit") return vlForm(x);
    if (v === "login") { await navigator.clipboard.writeText(x.login || ""); toast("Логин скопирован"); return; }
    const val = (await core.call("vault_reveal", { id: x.id })).value || "";
    if (v === "copy") { await vlCopy(val, "Пароль"); row.classList.add("copied"); setTimeout(() => row.classList.remove("copied"), 1200); return; }
    const el = $(".vl-val", row), dots = "•".repeat(Math.min(12, Math.max(6, x.length || 8)));
    if (el.classList.contains("shown")) { clearTimeout(el._t); el.textContent = dots; el.classList.remove("shown"); return; }
    el.textContent = val; el.classList.add("shown"); el.setAttribute("aria-label", "пароль показан");
    clearTimeout(el._t); el._t = setTimeout(() => { el.textContent = dots; el.classList.remove("shown"); el.setAttribute("aria-label", "пароль скрыт"); }, VL_SHOW_MS);
  } catch (e) { toast(e.message, 3500); }
}
/* надёжный пароль: 16 знаков, без похожих (0/O, 1/l/I), обязательно буквы обоих регистров, цифры и знак */
function vlGen(n = 16) {
  const L = "abcdefghijkmnpqrstuvwxyz", U = "ABCDEFGHJKLMNPQRSTUVWXYZ", D = "23456789", P = "!@#$%*-_+=?", all = L + U + D + P;
  const r = (s) => { const b = new Uint32Array(1); crypto.getRandomValues(b); return s[b[0] % s.length]; };
  const out = [r(L), r(U), r(D), r(P)]; while (out.length < n) out.push(r(all));
  for (let i = out.length - 1; i > 0; i--) { const b = new Uint32Array(1); crypto.getRandomValues(b); const j = b[0] % (i + 1); [out[i], out[j]] = [out[j], out[i]]; }
  return out.join("");
}
function vlStrength(p) {
  if (!p) return ["", ""];
  const kinds = [/[a-zа-яё]/, /[A-ZА-ЯЁ]/, /\d/, /[^\wа-яё]/i].filter(r => r.test(p)).length;
  if (/^\d{3,8}$/.test(p)) return ["pin", "пин-код или код — подходит для домофона и карты"];
  if (p.length >= 14 && kinds >= 3) return ["ok", "надёжный"];
  if (p.length >= 10 && kinds >= 2) return ["mid", "средний — лучше длиннее или со знаками"];
  return ["weak", "слабый — такой легко подобрать"];
}
function vlForm(x, name) {
  VL.edit = x ? x.id : "new";
  const f = $("#vl-form"); f.hidden = false;
  $("#vl-form-h").textContent = x ? "Изменить запись" : "Новая запись";
  $("#vl-name").value = x ? x.name : (name || ""); $("#vl-login").value = (x && x.login) || ""; $("#vl-url").value = (x && x.url) || "";
  $("#vl-note").value = (x && x.note) || ""; $("#vl-value").value = ""; $("#vl-value").type = "password"; $("#vl-eye").setAttribute("aria-pressed", "false");
  $("#vl-value").placeholder = x ? "оставьте пустым — пароль не изменится" : "";
  $("#vl-del").hidden = !x; $("#vl-res").textContent = ""; $("#vl-res").className = "res"; vlStr();
  f.scrollIntoView({ block: "nearest", behavior: "smooth" }); $(x ? "#vl-value" : "#vl-name").focus();
}
function vlFormClose() { VL.edit = null; $("#vl-form").hidden = true; $("#vl-value").value = ""; }
function vlStr() { const [k, t] = vlStrength($("#vl-value").value); const s = $("#vl-str"); s.className = "vl-str " + k; s.textContent = t; }
$("#vl-q").oninput = vlRender;
$("#vl-q").onkeydown = (e) => {
  if (e.key === "Escape" && $("#vl-q").value) { e.preventDefault(); $("#vl-q").value = ""; vlRender(); return; }
  if (e.key !== "Enter") return;
  e.preventDefault();
  const first = vlHits(vlNorm($("#vl-q").value.trim()))[0], row = first && $(`#vl-list .vl-item[data-id="${CSS.escape(first.id)}"]`);
  if (first && row) vlAct("copy", first, row);
};
$("#vl-add").onclick = () => vlForm(null, "");
$("#vl-cancel").onclick = vlFormClose;
$("#vl-value").oninput = vlStr;
$("#vl-eye").onclick = () => { const i = $("#vl-value"), on = i.type === "password"; i.type = on ? "text" : "password"; $("#vl-eye").setAttribute("aria-pressed", String(on)); };
$("#vl-gen").onclick = () => { const i = $("#vl-value"); i.value = vlGen(); i.type = "text"; $("#vl-eye").setAttribute("aria-pressed", "true"); vlStr(); i.focus(); };
$("#vl-form").onsubmit = async (e) => {
  e.preventDefault();
  const r = $("#vl-res"), a = { name: $("#vl-name").value.trim(), value: $("#vl-value").value, login: $("#vl-login").value.trim(),
    url: $("#vl-url").value.trim(), note: $("#vl-note").value.trim() };
  if (VL.edit && VL.edit !== "new") a.id = VL.edit;
  if (!a.name) { r.className = "res bad"; r.textContent = "Напишите, что это: «Почта», «Вайфай дома»…"; $("#vl-name").focus(); return; }
  if (!a.value && !a.id) { r.className = "res bad"; r.textContent = "Впишите пароль — или нажмите «Придумать»"; $("#vl-value").focus(); return; }
  if (!a.id && VL.items.some(x => vlNorm(x.name) === vlNorm(a.name)) && !await ask(`«${a.name}» уже есть в сейфе. Заменить пароль?`)) return;
  try { VL.items = (await core.call("vault_put", a)).items || VL.items; vlFormClose(); vlRender(); toast(a.id ? "Сохранено" : "В сейфе"); }
  catch (err) { r.className = "res bad"; r.textContent = err.message; }
};
$("#vl-del").onclick = async () => {
  const x = VL.items.find(i => i.id === VL.edit); if (!x) return;
  if (!await ask(`Удалить из сейфа «${x.name}»? Вернуть будет нельзя.`)) return;
  try { VL.items = (await core.call("vault_delete", { id: x.id })).items || []; vlFormClose(); vlRender(); toast("Удалено"); } catch (e) { toast(e.message); }
};
document.addEventListener("keydown", (e) => {                 // «/» или Ctrl+F в сейфе — к поиску
  if (!$("#p-vault").classList.contains("cur")) return;
  const typing = /^(INPUT|TEXTAREA)$/.test((document.activeElement || {}).tagName || "");
  if ((e.key === "/" && !typing) || ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "f")) { e.preventDefault(); $("#vl-q").focus(); $("#vl-q").select(); }
});
window.loadVaultPage = loadVaultPage;
