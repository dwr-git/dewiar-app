/* «Плагины» (раздел p-skills): каталог готовых умений — навык + подключения (MCP) + настройки + фразы + дела по расписанию,
   одной кнопкой (core/plugins.py, команды ядра plugins / plugin_install / plugin_remove / plugin_values / plugin_job /
   plugin_zip / plugin_delete). Карточка → боковая панель #pld: что умеет, что сказать (нажатие копирует фразу),
   настройки, дела по расписанию (у каждого — свой переключатель), что внутри. «Как сделать свой плагин» — #plg-guide
   (data/plugins/README.md, простая разметка Markdown). */
let PLG = [], plgCat = "Все", plgOpen = "", plgGuide = "";
const plgEsc = (t) => String(t ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const plgUse = { web_search: "поиск в интернете", read_webpage: "чтение страниц", weather: "погода", world_time: "время в городах", calc: "калькулятор",
  set_reminder: "напоминания и таймеры", schedule_job: "дела по расписанию", save_note: "заметки", find_notes: "поиск по заметкам", read_file: "чтение файлов",
  search_documents: "поиск по документам" };

function loadPlugins() { core.call("plugins").then(plgSet).catch(e => { $("#plg-grid").innerHTML = `<p class="hint">${plgEsc(e.message)}</p>`; }); }
function plgSet(r) {
  PLG = r.plugins || []; if (r.guide) plgGuide = r.guide;
  if (r.skills && typeof renderSkills === "function") renderSkills(r.skills);
  if (typeof renderMcp === "function" && S && S.mcp) core.call("mcp_status").then(renderMcp).catch(() => {});
  plgRender(); if (plgOpen) plgDrawer(plgOpen);
}
function plgRender() {
  const cats = ["Все", ...new Set(PLG.map(p => p.category))];
  if (!cats.includes(plgCat)) plgCat = "Все";
  $("#plg-cats").innerHTML = cats.length > 2 ? cats.map(c => `<button class="chip ${c === plgCat ? "on" : ""}" role="tab" aria-selected="${c === plgCat}" data-c="${plgEsc(c)}">${plgEsc(c)}</button>`).join("") : "";
  $$("#plg-cats .chip").forEach(b => b.onclick = () => { plgCat = b.dataset.c; plgRender(); });
  const list = PLG.filter(p => plgCat === "Все" || p.category === plgCat);
  $("#plg-grid").innerHTML = list.map(p => `<button class="plg${p.installed ? " on" : ""}" data-id="${plgEsc(p.id)}" style="--pc:${plgEsc(p.color)}">
      <i class="plg-ic" aria-hidden="true">${plgEsc(p.icon)}</i>
      <span class="plg-t"><b>${plgEsc(p.name)}</b><small>${plgEsc(p.tagline)}</small></span>
      <span class="plg-st">${p.installed ? "Установлен" : plgEsc(p.category)}</span></button>`).join("")
    || `<p class="hint">Плагинов пока нет.</p>`;
  $$("#plg-grid .plg").forEach(b => b.onclick = () => plgDrawer(b.dataset.id));
}
function plgField(p, s) {
  const v = (p.values || {})[s.key] ?? s.default ?? "", id = `pls-${s.key}`;
  if (s.type === "select") return `<label class="f">${plgEsc(s.label)}<select id="${id}" data-k="${plgEsc(s.key)}">${s.options.map(o => `<option ${String(o) === String(v) ? "selected" : ""}>${plgEsc(o)}</option>`).join("")}</select></label>`;
  if (s.type === "toggle") return `<div class="switch"><div>${plgEsc(s.label)}${s.hint ? `<span>${plgEsc(s.hint)}</span>` : ""}</div><label class="tg"><input type="checkbox" id="${id}" data-k="${plgEsc(s.key)}" ${v ? "checked" : ""}><i></i></label></div>`;
  return `<label class="f">${plgEsc(s.label)}<input type="${s.type === "number" ? "number" : "text"}" id="${id}" data-k="${plgEsc(s.key)}" value="${plgEsc(v)}" placeholder="${plgEsc(s.placeholder || "")}"></label>`;
}
function plgValues() {
  const out = {}; $$("#pld [data-k]").forEach(el => { out[el.dataset.k] = el.type === "checkbox" ? el.checked : el.value; }); return out;
}
function plgDrawer(id) {
  const p = PLG.find(x => x.id === id), d = $("#pld"); if (!p) return;
  plgOpen = id;
  const uses = (p.uses || []).map(u => plgUse[u] || u);
  d.style.setProperty("--pc", p.color);
  d.innerHTML = `<button class="btn small ghost pld-x" id="pld-x" aria-label="Закрыть">✕</button>
    <div class="pld-h"><i class="plg-ic" aria-hidden="true">${plgEsc(p.icon)}</i><div><h1 id="pld-name">${plgEsc(p.name)}</h1><p>${plgEsc(p.tagline)}</p></div></div>
    <p class="pld-desc">${plgEsc(p.description)}</p>
    <div class="actions" style="margin:6px 0 4px">${p.installed
      ? `<span class="pld-ok">✓ Установлен — просто говорите</span>${(p.links || []).map((l, i) => `<button class="btn" data-link="${i}">${plgEsc(l.label)}</button>`).join("")}<button class="btn ghost" id="pld-rm">Удалить</button>`
      : `<button class="btn primary" id="pld-in">Установить</button>`}<span class="res" id="pld-res"></span></div>
    ${p.phrases.length ? `<h2>Попробуйте сказать</h2><div class="pld-ph">${p.phrases.map(t => `<button class="chip" data-t="${plgEsc(t)}" title="${p.installed ? "Спросить Лиру" : "Скопировать"}">«${plgEsc(t)}»</button>`).join("")}</div>` : ""}
    ${p.settings.length ? `<h2>Настройки</h2><div class="row one pld-set">${p.settings.map(s => plgField(p, s)).join("")}</div>
      ${p.installed ? `<div class="actions" style="margin-top:6px"><button class="btn" id="pld-save">Сохранить настройки</button></div>` : `<p class="hint">Заполнится при установке — поменять можно в любой момент.</p>`}` : ""}
    ${p.jobs.length ? `<h2>Дела по расписанию</h2><p class="hint" style="margin:-4px 0 6px">Помощница делает их сама и сообщает итог. Каждое — по желанию.</p>
      ${p.jobs.map(j => `<div class="switch"><div>${plgEsc(j.title)}</div><label class="tg"><input type="checkbox" data-job="${plgEsc(j.id)}" ${j.on ? "checked" : ""} ${p.installed ? "" : "disabled"}><i></i></label></div>`).join("")}
      ${p.installed ? "" : `<p class="hint">Включаются после установки.</p>`}` : ""}
    <h2>Что внутри</h2>
    <ul class="pld-in">
      ${p.skills.length ? `<li><b>Навык${p.skills.length > 1 ? "и" : ""}</b> ${p.skills.map(plgEsc).join(", ")} — инструкция, по которой помощница действует</li>` : ""}
      ${uses.length ? `<li><b>Умения помощницы</b> ${uses.map(plgEsc).join(", ")}</li>` : ""}
      ${p.mcp.length ? `<li><b>MCP-серверы</b> ${p.mcp.map(plgEsc).join(", ")} — появятся в списке ниже, их можно выключить</li>` : `<li><b>Ничего ставить не нужно</b> — работает сразу</li>`}
      <li><b>Версия</b> ${plgEsc(p.version)}${p.author ? " · " + plgEsc(p.author) : ""}${p.builtin ? "" : " · свой плагин"}</li>
    </ul>
    ${p.builtin ? "" : `<div class="actions"><button class="btn danger small" id="pld-del">Удалить файлы плагина</button></div>`}`;
  d.classList.add("open"); d.scrollTop = 0;
  const res = (t, ok) => { const r = $("#pld-res"); r.className = "res " + (ok ? "ok" : "bad"); r.textContent = t; };
  const run = (cmd, args, done) => core.call(cmd, args).then(r => { plgSet(r); if (done) toast(done); }).catch(e => res(e.message, false));
  $("#pld-x").onclick = plgClose;
  if ($("#pld-in")) $("#pld-in").onclick = () => { $("#pld-in").disabled = true; run("plugin_install", { id, values: plgValues() }, `«${p.name}» установлен`); };
  if ($("#pld-rm")) $("#pld-rm").onclick = async () => { if (!await ask(`Удалить плагин «${p.name}»? Его навыки и подключения уберутся, дела по расписанию — тоже.`)) return; run("plugin_remove", { id }, `«${p.name}» удалён`); };
  if ($("#pld-save")) $("#pld-save").onclick = () => run("plugin_values", { id, values: plgValues() }, "Настройки сохранены");
  if ($("#pld-del")) $("#pld-del").onclick = async () => { if (!await ask(`Удалить файлы плагина «${p.name}» с этого компьютера?`)) return; plgOpen = ""; plgClose(); run("plugin_delete", { id }, "Плагин удалён"); };
  $$("#pld [data-link]").forEach(b => b.onclick = () => core.call("ws_open", { path: p.links[+b.dataset.link].path }).catch(e => res(e.message, false)));
  $$("#pld [data-job]").forEach(c => c.onchange = () => run("plugin_job", { id, job: c.dataset.job, on: c.checked }, c.checked ? "Дело включено — помощница сделает его сама" : "Дело выключено"));
  // установлен — фраза сразу уходит Лире в чат (видно, как работает); нет — копируется
  $$("#pld .pld-ph .chip").forEach(b => b.onclick = () => { if (p.installed && typeof qaAsk === "function") { plgClose(); qaAsk(b.dataset.t); return; }
    try { navigator.clipboard.writeText(b.dataset.t); } catch (e) { } toast("Скопировано — скажите это вслух или вставьте в чат"); });
}
function plgClose() { plgOpen = ""; $("#pld").classList.remove("open"); }
// ушли в другой раздел (меню слева) — панель плагина не остаётся висеть поверх (31.10: «Подробнее» с «Главной» и обратно)
document.addEventListener("click", (e) => { const b = e.target.closest && e.target.closest("nav button[data-p]"); if (b && b.dataset.p !== "skills" && $("#pld").classList.contains("open")) plgClose(); }, true);
document.addEventListener("keydown", (e) => { if (e.key === "Escape") { if ($("#pld").classList.contains("open")) plgClose(); $("#plg-guide").classList.remove("open"); } });

/* «Как сделать свой плагин»: Markdown → HTML (заголовки, абзацы, списки, таблицы, код) — только для своего README */
function plgMd(md) {
  const out = [], lines = String(md || "").split("\n"); let i = 0;
  const inl = (t) => plgEsc(t).replace(/`([^`]+)`/g, "<code>$1</code>").replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>");
  while (i < lines.length) {
    const l = lines[i];
    if (/^```/.test(l)) { const b = []; i++; while (i < lines.length && !/^```/.test(lines[i])) b.push(lines[i++]); i++; out.push(`<pre>${plgEsc(b.join("\n"))}</pre>`); continue; }
    if (/^#{1,3} /.test(l)) { const n = l.match(/^#+/)[0].length; out.push(`<h${n}>${inl(l.slice(n + 1))}</h${n}>`); i++; continue; }
    if (/^\|/.test(l)) { const rows = []; while (i < lines.length && /^\|/.test(lines[i])) rows.push(lines[i++]);
      out.push("<table>" + rows.filter(r => !/^\|[-\s|]+\|$/.test(r)).map((r, k) => "<tr>" + r.split("|").slice(1, -1).map(c => k ? `<td>${inl(c.trim())}</td>` : `<th>${inl(c.trim())}</th>`).join("") + "</tr>").join("") + "</table>"); continue; }
    if (/^- /.test(l)) { const it = []; while (i < lines.length && /^(- |  )/.test(lines[i])) { if (/^- /.test(lines[i])) it.push(lines[i].slice(2)); else it[it.length - 1] += " " + lines[i].trim(); i++; }
      out.push("<ul>" + it.map(x => `<li>${inl(x)}</li>`).join("") + "</ul>"); continue; }
    if (!l.trim()) { i++; continue; }
    const p = []; while (i < lines.length && lines[i].trim() && !/^(#|```|\||- )/.test(lines[i])) p.push(lines[i++]);
    out.push(`<p>${inl(p.join(" "))}</p>`);
  }
  return out.join("");
}
$("#plg-guide-b").onclick = () => { const g = $("#plg-guide");
  g.innerHTML = `<button class="btn small ghost pld-x" id="plg-guide-x" aria-label="Закрыть">✕</button><div class="plg-md">${plgMd(plgGuide)}</div>`;
  $("#plg-guide-x").onclick = () => g.classList.remove("open"); g.classList.add("open"); g.scrollTop = 0; };
$("#plg-file").onchange = async (e) => {
  const f = e.target.files[0]; if (!f) return; e.target.value = "";
  const r = $("#plg-res"), buf = new Uint8Array(await f.arrayBuffer()); let bin = "";
  for (let i = 0; i < buf.length; i += 0x8000) bin += String.fromCharCode.apply(null, buf.subarray(i, i + 0x8000));
  core.call("plugin_zip", { zip_b64: btoa(bin) }).then(x => { plgSet(x); r.className = "res ok"; r.textContent = "Плагин установлен."; })
    .catch(x => { r.className = "res bad"; r.textContent = x.message; });
};
