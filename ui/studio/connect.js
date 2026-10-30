/* Студия Dewiar: «Подключение» (готовые настройки по адресу, ключу или файлу), «Навыки» и серверы MCP, «Научить имени»
   и монитор услышанного, мастер «Мозг» (где думает ассистент), «Проверить всё».
   Команды ядра: config_preview/apply/export, skill_*, skills_catalog, skills_folder, mcp_status, calib_start/cancel/reset,
   llm_models, llm_test, self_check; события calib (шаги обучения имени) и hearing (что распознано и чьё имя услышано).
   Файлы студии подключаются по порядку из ui/settings.html и делят одну глобальную область: при загрузке здесь
   заполняются подсказки мастера (IS_WIN, clHint() — объявлена выше вызова); S_presets (dewiar.js) нужен по клику.
   startCalib и wizardCheck отсюда зовут personas.js и brain.js. */
/* ---------- подключение ----------
   Сначала config_preview показывает, что изменится (lines, warnings, нужен ли ключ), и только «Применить» —
   config_apply; ядро отвечает полными настройками. */
function showPreview(pv) {
  if (!pv) return;
  $("#c-preview").style.display = ""; $("#c-name").textContent = pv.name;
  $("#c-lines").innerHTML = ""; pv.lines.forEach(l => { const li = document.createElement("li"); li.textContent = l; $("#c-lines").appendChild(li); });
  $("#c-warn").innerHTML = ""; pv.warnings.forEach(l => { const li = document.createElement("li"); li.textContent = l; $("#c-warn").appendChild(li); });
  $("#c-keyrow").style.display = pv.need_key ? "" : "none"; $("#c-keyhint").textContent = pv.key_hint || "";
  $("#c-res").textContent = "";
  $('nav button[data-p="connect"]').click();
}
async function preview(args) {
  const r = $("#c-res"); r.className = "res"; r.textContent = "ищу настройки…";
  try { showPreview(await core.call("config_preview", args)); } catch (e) { r.className = "res bad"; r.textContent = e.message; }
}
$("#c-go").onclick = () => preview({ address: $("#c-addr").value });
$("#c-addr").onkeydown = (e) => { if (e.key === "Enter") $("#c-go").click(); };
$("#c-cancel").onclick = () => { $("#c-preview").style.display = "none"; };
$("#c-apply").onclick = async () => {
  const r = $("#c-res");
  try { S = await core.call("config_apply", { key: $("#c-key").value }); $("#c-preview").style.display = "none";
        r.className = "res ok"; r.textContent = "Готово — всё настроено."; refreshStatic(); renderProfiles(); renderCurrent(); toast("Настройки применены"); }
  catch (e) { r.className = "res bad"; r.textContent = e.message; }
};
$("#c-file").onchange = async (ev) => {
  const f = ev.target.files[0]; ev.target.value = ""; if (!f) return;
  try { preview({ data: JSON.parse(await f.text()) }); } catch (e) { $("#c-res").className = "res bad"; $("#c-res").textContent = "Файл не читается: это не настройки Dewiar"; }
};
$("#c-export").onclick = async () => {
  try {
    const data = await core.call("config_export", { secrets: $("#c-secrets").checked });
    const text = JSON.stringify(data, null, 2), name = "dewiar-настройки.dewiar", a = api();
    if (a && a.save_file) { const where = await a.save_file(text, name); if (where) toast("Сохранено: " + where); return; }
    const link = document.createElement("a"); link.href = URL.createObjectURL(new Blob([text], { type: "application/json" })); link.download = name; link.click();
  } catch (e) { toast(e.message); }
};
function renderCurrent() {
  const p = S.provision || {};
  $("#c-current").textContent = p.url ? `Подключено: ${p.name || p.url} · обновляется с ${p.url} · применено ${p.applied}` : "";
}

/* ---------- навыки и MCP ---------- */
function renderSkills(list) {
  const box = $("#sklist"); box.innerHTML = "";
  list.filter(s => !s.plugin).forEach(s => {                 // навыки плагинов — в карточке своего плагина
    const el = document.createElement("div"); el.className = "tool";
    el.innerHTML = `<div><b></b>${s.builtin ? '<span class="risk" style="color:var(--muted);background:rgba(255,255,255,.05)">встроенный</span>' : ""}<div class="d"></div></div>
      <label class="tg"><input type="checkbox" ${s.enabled ? "checked" : ""}><i></i></label>
      <div style="display:flex;gap:6px"><button class="btn small" data-a="edit">Изменить</button>${s.builtin ? "" : '<button class="btn small" data-a="zip" title="Файл навыка — отправить другу или перенести на другой компьютер">Поделиться</button>'}</div>`;
    $("b", el).textContent = s.title; $(".d", el).textContent = s.description;
    $("input", el).onchange = (e) => core.call("skill_toggle", { name: s.name, on: e.target.checked }).then(renderSkills);
    $('[data-a="edit"]', el).onclick = () => openSkill(s.name);
    if (!s.builtin) $('[data-a="zip"]', el).onclick = () => downloadSkill(s.name);
    box.appendChild(el);
  });
}
function skillDone(r) { renderSkills(r.skills); $("#sk-res").className = "res ok"; $("#sk-res").textContent = `Навык «${r.name}» установлен.`; }
function skillErr(e) { $("#sk-res").className = "res bad"; $("#sk-res").textContent = e.message; }
$("#sk-urlgo").onclick = () => core.call("skill_install", { url: $("#sk-url").value.trim() }).then(skillDone).catch(skillErr);
$("#sk-file").onchange = async (ev) => {
  const f = ev.target.files[0]; ev.target.value = ""; if (!f) return;
  if (f.name.toLowerCase().endsWith(".md")) return core.call("skill_install", { text: await f.text() }).then(skillDone).catch(skillErr);
  // в base64 — кусками по 32 КБ: String.fromCharCode с аргументами на весь файл переполняет стек
  const u = new Uint8Array(await f.arrayBuffer()); let bin = "";
  for (let i = 0; i < u.length; i += 32768) bin += String.fromCharCode.apply(null, u.subarray(i, i + 32768));
  const b64 = btoa(bin);
  core.call("skill_install", { zip_b64: b64, name: f.name.replace(/\.zip$/i, "") }).then(skillDone).catch(skillErr);
};
/* редактор навыков: SKILL.md (название, описание, текст) и дополнительные файлы; skEdit.old — имя до правки (для
   переименования), у встроенного навыка пусто — сохранение создаёт вашу копию, встроенный не трогается */
let skEdit = null;
function fileRow(name = "", content = "") {
  const d = document.createElement("details"); d.className = "prof"; d.style.padding = "4px 14px"; d.open = !name;
  d.innerHTML = `<summary style="cursor:pointer;padding:6px 0"></summary><label class="f">Путь внутри навыка<input type="text" class="fn" placeholder="references/prices.md"></label>
    <label class="f" style="margin-top:8px">Содержимое<textarea class="fc" style="min-height:120px;font-family:ui-monospace,monospace;font-size:12.5px"></textarea></label>
    <button class="btn small danger" style="margin:8px 0">Убрать файл</button>`;
  $("summary", d).textContent = name || "новый файл"; $(".fn", d).value = name; $(".fc", d).value = content;
  $(".fn", d).oninput = () => $("summary", d).textContent = $(".fn", d).value || "новый файл";
  $(".btn", d).onclick = () => d.remove(); $("#skd-files").appendChild(d);
}
async function openSkill(name) {
  skEdit = { old: "" }; $("#skd-files").innerHTML = ""; $("#skd-res").textContent = ""; $("#skd-dres").textContent = ""; $("#skd-idea").value = "";
  if (name) {
    try {
      const s = await core.call("skill_get", { name }); skEdit = { old: s.builtin ? "" : s.name, builtin: s.builtin };
      $("#skd-title").textContent = s.builtin ? `Навык «${s.name}» (изменения сохранятся как ваша копия)` : `Навык «${s.name}»`;
      $("#skd-name").value = s.name; $("#skd-desc").value = s.description; $("#skd-body").value = s.body;
      Object.entries(s.files).forEach(([n, c]) => fileRow(n, c));
    } catch (e) { return toast(e.message); }
  } else { $("#skd-title").textContent = "Новый навык"; $("#skd-name").value = ""; $("#skd-desc").value = ""; $("#skd-body").value = ""; }
  $("#skd-del").style.display = name && !skEdit.builtin ? "" : "none";
  $("#skd").classList.add("open"); $("#skd").scrollTop = 0;
}
$("#sk-new").onclick = () => openSkill(null);
$("#skd-close").onclick = () => $("#skd").classList.remove("open");
$("#skd-addfile").onclick = () => fileRow();
$("#skd-draft").onclick = async (ev) => {
  const r = $("#skd-dres"); ev.target.disabled = true; r.className = "res"; r.textContent = "Ассистент пишет навык…";
  try { const d = await core.call("skill_draft", { idea: $("#skd-idea").value });
        // имя уже сохранённого навыка черновик не меняет — иначе сохранение станет переименованием
        if (!$("#skd-name").value || !skEdit.old) $("#skd-name").value = d.name; $("#skd-desc").value = d.description; $("#skd-body").value = d.body;
        r.className = "res ok"; r.textContent = "Готово — проверьте и сохраните."; }
  catch (e) { r.className = "res bad"; r.textContent = e.message; }
  ev.target.disabled = false;
};
$("#skd-save").onclick = async () => {
  const files = {}; $$("#skd-files details").forEach(d => { const n = $(".fn", d).value.trim(); if (n) files[n] = $(".fc", d).value; });
  try { const r = await core.call("skill_save", { name: $("#skd-name").value, description: $("#skd-desc").value, body: $("#skd-body").value, files, old_name: skEdit.old });
        skEdit.old = r.name; renderSkills(r.skills); $("#skd-res").className = "res ok"; $("#skd-res").textContent = `Сохранено — навык «${r.name}» уже работает.`; $("#skd-del").style.display = ""; }
  catch (e) { $("#skd-res").className = "res bad"; $("#skd-res").textContent = e.message; }
};
$("#skd-zip").onclick = () => { if (skEdit && skEdit.old) downloadSkill(skEdit.old); else toast("Сначала сохраните навык"); };
$("#skd-del").onclick = () => core.call("skill_remove", { name: skEdit.old }).then(l => { renderSkills(l); $("#skd").classList.remove("open"); }).catch(e => toast(e.message));
async function downloadSkill(name) {
  try {
    const r = await core.call("skill_export", { name }), a = api(), fname = `${name}.zip`;
    if (a && a.save_file_b64) { const w = await a.save_file_b64(r.zip_b64, fname); if (w) toast("Сохранено: " + w); return; }
    const l = document.createElement("a"); l.href = "data:application/zip;base64," + r.zip_b64; l.download = fname; l.click();
  } catch (e) { toast(e.message); }
}
async function openCatalog(url) {
  const box = $("#catlist"); box.innerHTML = '<p class="hint">Загружаю каталог…</p>';
  try {
    const items = await core.call("skills_catalog", url ? { url } : {}); box.innerHTML = "";
    if (!items.length) box.innerHTML = '<p class="hint">В каталоге пока пусто.</p>';
    items.forEach(x => { const el = document.createElement("div"); el.className = "tool";
      el.innerHTML = `<div><b></b><div class="d"></div></div><button class="btn small"></button>`;
      $("b", el).textContent = x.title; $(".d", el).textContent = x.description; const b = $(".btn", el);
      b.textContent = x.installed ? "Обновить" : "Установить";
      b.onclick = () => { b.disabled = true; core.call("skill_install", { url: x.url }).then(r => { renderSkills(r.skills); b.textContent = "Установлен"; }).catch(e => { b.disabled = false; toast(e.message); }); };
      box.appendChild(el); });
  } catch (e) { box.innerHTML = ""; const p = document.createElement("p"); p.className = "res bad"; p.textContent = e.message; box.appendChild(p); }
}
$("#cat-go").onclick = () => openCatalog($("#cat-url").value.trim());
$("#sk-folder").onclick = async () => { const a = api(); let p = ""; try { p = await core.call("skills_folder"); } catch (e) {}
  if (a && a.open_skills_folder) a.open_skills_folder(p); else if (p) toast("Папка навыков: " + p); };

const MCP_PRESETS = {
  "Файлы (домашняя папка)": { name: "files", cfg: { type: "stdio", command: "npx", args: ["-y", "@modelcontextprotocol/server-filesystem", "~"] } },
  "Память (граф знаний)": { name: "memory", cfg: { type: "stdio", command: "npx", args: ["-y", "@modelcontextprotocol/server-memory"] } },
  "Загрузка страниц (fetch)": { name: "fetch", cfg: { type: "stdio", command: "uvx", args: ["mcp-server-fetch"] } },
};
let mcpStatus = {};
/* mcp.servers ядро заменяет целиком (settings._merge), поэтому шлём весь словарь; статус спрашиваем чуть позже —
   ядро сначала переподключает серверы */
function saveServers(servers) { return save({ mcp: { servers } }).then(() => setTimeout(() => core.call("mcp_status").then(renderMcp), 400)); }
function renderMcp(st) {
  mcpStatus = st || mcpStatus;
  const box = $("#mcplist"), servers = S.mcp.servers || {}; box.innerHTML = "";
  if (!Object.keys(servers).length) box.innerHTML = '<p class="hint">Пока не подключено ни одного. Начните с готовых ниже — для них нужен Node.js (npx) или uv (uvx).</p>';
  Object.entries(servers).forEach(([n, c]) => {
    const s = mcpStatus[n] || {}, el = document.createElement("div"); el.className = "tool";
    const stTxt = c.enabled === false ? "выключен" : s.status === "ok" ? `подключён · инструментов: ${s.tools.length}` : s.status === "error" ? `ошибка: ${s.error}` : "подключаюсь…";
    el.innerHTML = `<div><b></b><div class="d"></div><div class="d" style="color:${s.status === "error" ? "var(--bad)" : s.status === "ok" ? "var(--good)" : "var(--muted)"}"></div></div>
      <label class="tg"><input type="checkbox" ${c.enabled === false ? "" : "checked"}><i></i></label>
      <label class="ask"><input type="checkbox" ${c.trust ? "checked" : ""}> доверять — не спрашивать разрешения</label>
      <button class="btn small danger" style="justify-self:end">Удалить</button>`;
    $("b", el).textContent = n; $$(".d", el)[0].textContent = c.type === "http" ? c.url : [c.command, ...(c.args || [])].join(" "); $$(".d", el)[1].textContent = stTxt;
    const [on, trust] = $$("input", el);
    on.onchange = () => { servers[n] = Object.assign({}, c, { enabled: on.checked }); saveServers(servers); };
    trust.onchange = () => { servers[n] = Object.assign({}, c, { trust: trust.checked }); saveServers(servers); };
    $(".btn", el).onclick = () => { delete servers[n]; saveServers(servers).then(() => renderMcp()); };
    box.appendChild(el);
  });
  const pr = $("#mcp-presets"); pr.innerHTML = "";
  Object.entries(MCP_PRESETS).forEach(([label, p]) => { if (servers[p.name]) return;
    const b = document.createElement("button"); b.className = "chip"; b.textContent = "+ " + label;
    b.onclick = () => { servers[p.name] = p.cfg; saveServers(servers).then(() => renderMcp()); }; pr.appendChild(b); });
}
$("#m-type").onchange = () => { const h = $("#m-type").value === "http"; $$(".m-http").forEach(x => x.style.display = h ? "" : "none"); $$(".m-stdio").forEach(x => x.style.display = h ? "none" : ""); };
$("#m-save").onclick = () => {
  const name = $("#m-name").value.trim().replace(/[^\w-]+/g, "_"), res = $("#m-res");
  if (!name) { res.className = "res bad"; res.textContent = "Введите название"; return; }
  let cfg;
  if ($("#m-type").value === "http") {
    if (!/^https?:\/\//.test($("#m-url").value.trim())) { res.className = "res bad"; res.textContent = "Нужен адрес вида https://…"; return; }
    cfg = { type: "http", url: $("#m-url").value.trim() };
    if ($("#m-tok").value) cfg.headers = { Authorization: "Bearer " + $("#m-tok").value };   // токен хранится в настройках, как ключи API
  } else {
    // команда делится на слова как в оболочке, но упрощённо: кавычки только целым словом, без экранирования
    const parts = $("#m-cmd").value.trim().match(/"[^"]*"|'[^']*'|\S+/g) || [];
    if (!parts.length) { res.className = "res bad"; res.textContent = "Введите команду запуска"; return; }
    const env = {}; $("#m-env").value.split(";").map(x => x.trim()).filter(Boolean).forEach(kv => { const i = kv.indexOf("="); if (i > 0) env[kv.slice(0, i).trim()] = kv.slice(i + 1).trim(); });
    cfg = { type: "stdio", command: parts[0].replace(/^["']|["']$/g, ""), args: parts.slice(1).map(x => x.replace(/^["']|["']$/g, "")), env };
  }
  const servers = S.mcp.servers || {}; servers[name] = cfg;
  saveServers(servers).then(() => { res.className = "res ok"; res.textContent = "Добавлен — подключаюсь…"; $("#mcp-add").open = false; renderMcp(); });
};

/* ---------- научить имени и монитор ----------
   Обучение: ядро просит сказать имя несколько раз (e.need) и запоминает его звучание вашим голосом — шаги приходят
   событием calib. Монитор: последние 30 услышанных фраз; e.name — id личности, чьё имя прозвучало, e.by — чем распознано. */
function fillNamePick() {
  const sel = $("#nm-p"); const cur = sel.value || active; sel.innerHTML = "";
  personas.forEach(p => { const o = document.createElement("option"); o.value = p.id; o.textContent = p.name + (p.taught ? " — выучено" : ""); sel.appendChild(o); });
  sel.value = personas.some(p => p.id === cur) ? cur : active;
}
function nmDots(n, need) { $("#nm-dots").innerHTML = ""; for (let i = 0; i < need; i++) { const d = document.createElement("i");
  d.style.cssText = `width:12px;height:12px;border-radius:50%;display:inline-block;border:1px solid var(--accent);background:${i < n ? "var(--accent)" : "transparent"}`; $("#nm-dots").appendChild(d); } }
function startCalib(pid) {
  $('nav button[data-p="ears"]').click(); if (pid) $("#nm-p").value = pid;
  core.call("calib_start", { persona: $("#nm-p").value }).catch(e => toast(e.message));
}
$("#nm-go").onclick = () => startCalib();
$("#nm-cancel").onclick = () => core.call("calib_cancel").then(() => { $("#nm-res").textContent = "Отменено."; $("#nm-cancel").style.display = "none"; $("#nm-go").disabled = false; nmDots(0, 3); });
$("#nm-forget").onclick = () => core.call("calib_reset", { persona: $("#nm-p").value }).then(() => { $("#nm-res").className = "res"; $("#nm-res").textContent = "Забыл. Можно научить заново."; });
core.on("calib", e => {
  const r = $("#nm-res");
  if (e.step === "listen") { $("#nm-go").disabled = true; $("#nm-cancel").style.display = ""; nmDots(0, e.need); r.className = "res"; r.textContent = `Скажите «${e.name}» — 1 из ${e.need}`; }
  if (e.step === "sample") { nmDots(e.n, e.need); r.className = "res"; r.textContent = e.n < e.need ? `Хорошо. Ещё раз «${e.name}» — ${e.n + 1} из ${e.need}` : "Запоминаю…"; }
  if (e.step === "done") { $("#nm-go").disabled = false; $("#nm-cancel").style.display = "none"; r.className = "res ok";
    r.textContent = `Готово: «${e.name}» узнаю по вашему голосу. Попробуйте: «${e.name}, привет».`; }
  if (e.step === "error") { $("#nm-go").disabled = false; $("#nm-cancel").style.display = "none"; r.className = "res bad"; r.textContent = e.error; nmDots(0, 3); }
});
core.on("hearing", e => {
  const box = $("#hear"); const empty = $("#hear-empty"); if (empty) empty.remove();
  const row = document.createElement("div"); row.style.cssText = "display:grid;grid-template-columns:52px 1fr auto;gap:10px;padding:6px 0;border-bottom:1px solid var(--line)";
  const who = e.name ? (personas.find(p => p.id === e.name) || {}).name || e.name : "";
  row.innerHTML = "<span class='hint'></span><span></span><span></span>";
  const [t, x, r] = row.children; t.textContent = new Date().toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  x.textContent = e.text || (e.full ? "—" : "речь без имени"); x.title = e.by;
  r.textContent = e.full ? "вопрос" : who ? `имя: ${who}` : "имени нет"; r.style.color = who ? "var(--good)" : "var(--muted)";
  box.prepend(row); while (box.children.length > 30) box.lastChild.remove();
});

/* ---------- мастер «Мозг»: где будет думать ассистент ---------- */
const IS_WIN = /Win/.test(navigator.platform || navigator.userAgent);   // подсказки по установке Ollama и голосу системы — свои для Windows
$$(".wtile").forEach(b => b.onclick = () => {
  const on = !b.classList.contains("cur");
  $$(".wtile").forEach(x => x.classList.remove("cur")); $$(".wpanel").forEach(x => x.classList.remove("on"));
  if (on) { b.classList.add("cur"); $("#w-" + b.dataset.w).classList.add("on"); if (b.dataset.w === "dwkey") dkAccFill(); const f = $("#w-" + b.dataset.w + " input"); if (f && !(b.dataset.w === "dwkey" && DW.acc && DW.acc.logged_in)) f.focus(); }
  $("#w-done").style.display = "none";
});
if (IS_WIN) { $$(".tts-sys").forEach(x => x.textContent = "Голос Windows"); $$(".tts-sys-d").forEach(x => x.textContent = "Встроенный голос системы («Ирина», «Павел»). Без скачивания — на крайний случай."); }
$("#lc-steps").innerHTML = IS_WIN
  ? `<li>Скачайте Ollama для Windows: <a href="https://ollama.com/download/windows" target="_blank">ollama.com/download</a> — и установите, как обычную программу.</li>
     <li>Откройте «Пуск» → «Командная строка» и выполните: <code>ollama pull qwen3:4b</code> — скачается модель (≈2,5 ГБ).</li>
     <li>Вернитесь сюда и нажмите «Найти Ollama или LM Studio».</li>`
  : `<li>Откройте терминал и выполните: <code>curl -fsSL https://ollama.com/install.sh | sh</code></li>
     <li>Затем скачайте модель: <code>ollama pull qwen3:4b</code> (≈2,5 ГБ).</li>
     <li>Вернитесь сюда и нажмите «Найти Ollama или LM Studio».</li>`;
$("#w-toconnect").onclick = (e) => { e.preventDefault(); $('nav button[data-p="connect"]').click(); };

/* Проверить профиль id настоящим запросом к модели и показать итог в мастере -> true, если ответила */
async function wizardCheck(id) {
  const box = $("#w-done"); box.style.display = ""; box.className = "wdone"; box.textContent = "Проверяю, как отвечает модель…";
  try {
    const r = await core.call("llm_test", { profile: S.llm.profiles[id] });
    if (r.ok) {
      box.innerHTML = `<b>Готово — мозг подключён.</b> Модель «${escH(r.model)}» ответила за ${(r.total_ms / 1000).toFixed(1)} с: «${escH(r.reply)}».<br>${r.ctx_note ? `<br><span class="warn">Учтите: ${escH(r.ctx_note)}.</span>` : ""}<br>Теперь скажите имя персонажа — например, «${escH((personas.find(p => p.id === active) || {}).name || "Агент")}» — и спросите что-нибудь.`;
    } else { box.className = "wdone bad"; box.textContent = "Модель не ответила: " + (r.error || "неизвестная ошибка"); }
    return r.ok;
  } catch (e) { box.className = "wdone bad"; box.textContent = "Модель не ответила: " + e.message; return false; }
}

/* Облачные сервисы: где взять ключ и какие модели советовать первыми (если они есть в списке сервиса).
   После проверки ключа сразу создаётся и включается профиль с первой рекомендованной моделью.
   19.10: кнопка «Подключить» не работала вовсе — у неё был тот же id, что у «Отправить» в «Близких» (cl-go), и
   обработчик доставался той кнопке; комментарии «почему нельзя подключить свой сервис». Теперь свои id (ck-…),
   DeepSeek и «Другой — по адресу»: любой OpenAI-совместимый сервис (LiteLLM, Kimi, агрегаторы) — адрес + ключ. */
const CLOUD = {
  openrouter: { hint: 'Ключ — на <a href="https://openrouter.ai/settings/keys" target="_blank">openrouter.ai → Settings → Keys</a>. Один ключ — сотни моделей, оплата с баланса.',
                rec: ["google/gemini-2.5-flash", "openai/gpt-4.1-mini", "anthropic/claude-haiku-4.5", "qwen/qwen3-235b-a22b-2507", "deepseek/deepseek-chat-v3.1"] },
  openai: { hint: 'Ключ — на <a href="https://platform.openai.com/api-keys" target="_blank">platform.openai.com/api-keys</a>.',
            rec: ["gpt-5-mini", "gpt-4.1-mini", "gpt-4o-mini", "gpt-5", "gpt-4.1"] },
  anthropic: { hint: 'Ключ — на <a href="https://console.anthropic.com/settings/keys" target="_blank">console.anthropic.com</a>.',
               rec: ["claude-haiku-4-5", "claude-sonnet-4-5", "claude-3-5-haiku-latest", "claude-sonnet-4-0"] },
  deepseek: { hint: 'Ключ — на <a href="https://platform.deepseek.com/api_keys" target="_blank">platform.deepseek.com</a>. Напрямую — дешевле, чем через посредников.',
              rec: ["deepseek-chat", "deepseek-reasoner"] },
  gemini: { hint: 'Ключ — в <a href="https://aistudio.google.com/apikey" target="_blank">Google AI Studio</a> («Get API key»). Есть бесплатный уровень.',
            rec: ["gemini-flash-latest", "gemini-2.5-flash", "gemini-flash-lite-latest", "gemini-pro-latest", "gemini-2.5-pro"] },
  kimi: { hint: 'Ключ — на <a href="https://platform.moonshot.ai/console/api-keys" target="_blank">platform.moonshot.ai</a>. Модели Kimi K2 — сильные в инструментах.',
          rec: ["kimi-latest", "kimi-k2-turbo-preview", "kimi-k2-0905-preview", "moonshot-v1-32k"] },
  glm: { hint: 'Ключ — на <a href="https://z.ai/manage-apikey/apikey-list" target="_blank">z.ai</a> («API Keys»). Модели GLM от Zhipu.',
         rec: ["glm-4.6", "glm-4.5-air", "glm-4.5"] },
  qwen: { hint: 'Ключ — в <a href="https://modelstudio.console.alibabacloud.com/" target="_blank">Alibaba Cloud Model Studio</a> («API Key», международный регион).',
          rec: ["qwen-plus", "qwen-flash", "qwen-max", "qwen3-max"] },
  mistral: { hint: 'Ключ — на <a href="https://console.mistral.ai/api-keys" target="_blank">console.mistral.ai</a>.',
             rec: ["mistral-medium-latest", "mistral-small-latest", "mistral-large-latest"] },
  xai: { hint: 'Ключ — на <a href="https://console.x.ai" target="_blank">console.x.ai</a>.',
         rec: ["grok-4-fast-non-reasoning", "grok-4-fast-reasoning", "grok-3-mini", "grok-4"] },
  proxyapi: { hint: 'Ключ — в кабинете <a href="https://console.proxyapi.ru/keys" target="_blank">ProxyAPI</a>. Модели OpenAI, оплата картой РФ.',
              rec: ["gpt-4.1-mini", "gpt-4o-mini", "gpt-5-mini"] },
  vsegpt: { hint: 'Ключ — на <a href="https://vsegpt.ru" target="_blank">vsegpt.ru</a> («Ключи API»). Много моделей, оплата картой РФ.',
            rec: ["openai/gpt-4.1-mini", "google/gemini-2.5-flash", "deepseek/deepseek-chat"] },
  custom: { hint: 'Любой сервис, который говорит «как OpenAI»: LiteLLM, Kimi, российские агрегаторы, свой прокси. Адрес обычно оканчивается на <code>/v1</code> — он есть в документации сервиса.',
            rec: [] },
};
/* Адрес, который вписали: без пробелов и хвоста /chat/completions, с https:// — -> строка или "" */
function ckUrl(raw) {
  let u = String(raw || "").trim().replace(/\/+$/, "").replace(/\/chat\/completions$/, "").replace(/\/models$/, "");
  if (!u) return "";
  if (!/^https?:\/\//i.test(u)) u = "https://" + u;
  return u;
}
function ckPreset(prov) {
  if (prov !== "custom") return Object.assign({}, S_presets[prov] || {});
  const url = ckUrl($("#ck-url").value);
  let host = url; try { host = new URL(url).host; } catch (e) { }
  return { name: host || "Свой сервис", kind: "openai", base_url: url };
}
function ckHint() { const prov = $("#ck-prov").value; $("#ck-hint").innerHTML = CLOUD[prov].hint; $("#ck-url-f").style.display = prov === "custom" ? "" : "none"; }
$("#ck-prov").onchange = ckHint; ckHint();
let ckId = null, ckSvc = "";
$("#ck-go").onclick = async (ev) => {
  const prov = $("#ck-prov").value, key = $("#ck-key").value.trim(), r = $("#ck-res"), btn = $("#ck-go");
  if (prov === "custom" && !ckUrl($("#ck-url").value)) { r.className = "res bad"; r.textContent = "Впишите адрес сервиса"; return; }
  if (!key) { r.className = "res bad"; r.textContent = "Вставьте ключ API"; return; }
  btn.disabled = true; r.className = "res"; r.textContent = "проверяю ключ…"; $("#ck-found").style.display = "none";
  const prof = Object.assign({ api_key: key, model: "" }, ckPreset(prov)); delete prof.models; delete prof.preset;
  if (!prof.base_url) {        // список сервисов приходит от ядра с «hello» — студия открылась раньше (пакет 22.10: KeyError 'base_url')
    btn.disabled = false; r.className = "res bad"; r.textContent = "Студия ещё не на связи с ядром — подождите секунду и нажмите снова"; return;
  }
  try {
    let models = [];
    try { models = await core.call("llm_models", { profile: prof }); }
    catch (e) {                                   // свой адрес без /v1 — частая ошибка: пробуем с /v1
      if (prov !== "custom" && CLOUD[prov].rec.length && !/401|403|ключ/i.test(e.message)) models = [];   // нет списка — не беда, проверка покажет
      else if (prov !== "custom" || /\/v1$/.test(prof.base_url)) throw e;
      else {
        const p2 = Object.assign({}, prof, { base_url: prof.base_url + "/v1" });
        models = await core.call("llm_models", { profile: p2 }); prof.base_url = p2.base_url;
      }
    }
    if (!models.length && CLOUD[prov].rec.length) models = CLOUD[prov].rec.slice();   // список не отдал (бывает у GLM) — проверим первую из советуемых
    if (!models.length) throw new Error("сервис не вернул список моделей");
    const rec = CLOUD[prov].rec.filter(m => models.includes(m));
    const side = (m) => /embed|rerank/i.test(m) ? 1 : 0;                   // поиск по смыслу — в конец, остальное по алфавиту
    const ordered = rec.concat(models.filter(m => !rec.includes(m)).sort((a, b) => side(a) - side(b) || a.localeCompare(b)));
    prof.model = ordered[0]; ckSvc = prof.name; prof.name = `${prof.name} — ${prof.model}`;
    ckId = uid(); S.llm.profiles[ckId] = prof;
    await save({ llm: { profiles: S.llm.profiles, active: ckId } }); renderProfiles();
    $("#ck-model").innerHTML = ordered.map(m => `<option value="${escH(m)}">${escH(m)}${rec.includes(m) ? " — рекомендую" : ""}</option>`).join("");
    $("#ck-found").style.display = ""; r.textContent = ""; $("#ck-key").value = "";
    await wizardCheck(ckId);
  } catch (e) { r.className = "res bad"; r.textContent = "Не получилось: " + e.message; }
  btn.disabled = false;
};
$("#ck-key").onkeydown = (e) => { if (e.key === "Enter") $("#ck-go").click(); };
$("#ck-use").onclick = async () => {
  if (!ckId || !S.llm.profiles[ckId]) return;
  const m = $("#ck-model").value, p = S.llm.profiles[ckId]; p.model = m; p.name = `${ckSvc || ckPreset($("#ck-prov").value).name} — ${m}`;
  await save({ llm: { profiles: S.llm.profiles, active: ckId } }); renderProfiles(); await wizardCheck(ckId);
};

/* ---------- «Проверить всё» ---------- */
$("#sc-go").onclick = async (ev) => {
  const box = $("#sc-list"); ev.target.disabled = true; box.innerHTML = '<div class="hint">Проверяю — несколько секунд…</div>';
  try {
    const list = await core.call("self_check");
    box.innerHTML = list.map(x => `<div class="scit${x.ok ? "" : x.warn ? " warn" : " bad"}"><i>${x.ok ? "✓" : x.warn ? "!" : "✕"}</i>
      <div><b>${escH(x.name)}</b><span>${escH(x.detail)}</span>${x.fix ? `<em>${escH(x.fix)}</em>` : ""}</div>
      ${!x.ok && x.page ? `<button class="btn small" data-go="${x.page}">Открыть</button>` : ""}</div>`).join("");
    $$("#sc-list [data-go]").forEach(b => b.onclick = () => $(`nav button[data-p="${b.dataset.go}"]`).click());
  } catch (e) { box.innerHTML = `<div class="res bad">${escH(e.message)}</div>`; }
  ev.target.disabled = false;
};
/* «Не мешать компьютеру уснуть» (идея №70) — только в Windows: в Linux открытый микрофон сну не мешает */
if ($("#sleep-sw")) $("#sleep-sw").hidden = !IS_WIN;
