/* Студия Dewiar, разделы «Задачи» и обновление в «О программе».
   Задачи — долгие поручения мастерской (core/tasks.py): список, карточка с вкладками (план, блокнот, результаты, журнал,
   изменения кода, итог), просмотр и выгрузка результатов, «идеи» для пустой страницы. Команды ядра: tasks_list, task_get,
   task_create, task_tell, task_answer, task_resume/stop/accept/discard/delete, task_export, task_rewind, task_net, ws_open, ws_read;
   событие "task" перерисовывает раздел, пока он открыт. Обновление: renderUpdate() показывает update_status,
   ставит его окно (api().install_update), экран хода установки — updShow/updPoll в day.js.
   Файлы студии подключаются по порядку из ui/settings.html и делят одну глобальную область: при загрузке здесь
   вызываются только $/$$ из core.js; escH и md (folder.js) нужны лишь при отрисовке, когда всё уже загружено. */
/* ---------- задачи ---------- */
let tCur = "", tTab = "plan", tTimer = null;
const tsince = (iso) => { const d = new Date(iso); return isNaN(d) ? "" : d.toLocaleString("ru-RU", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }); };
function taskPin(id, on, pins) {
  const next = pins.filter(x => x !== id).concat(on ? [id] : []);
  S.ui = Object.assign({}, S.ui, { task_pins: next });                 // сразу — без ожидания ответа ядра
  save({ ui: { task_pins: next } }, true).then(loadTasks); loadTasks();
}
async function loadTasks() {
  try {
    let list = await core.call("tasks_list");
    const box = $("#t-list"); box.innerHTML = list.length ? "" : '<div class="fempty" style="padding:30px 8px">Пока пусто</div>';
    $("#t-box").style.display = list.length ? "" : "none";
    $("#t-ideas").style.display = list.length ? "none" : "";
    // №201 (24.10): «закреплять пин — видеть, что исполняется, а не скролить вверх и вниз»: закреплённые — сверху,
    // в порядке закрепления (ui.task_pins); булавка — при наведении, у закреплённых — всегда
    const ids = new Set(list.map(t => t.id)), pins = ((S.ui && S.ui.task_pins) || []).filter(id => ids.has(id));
    list = pins.map(id => list.find(t => t.id === id)).concat(list.filter(t => !pins.includes(t.id)));
    list.forEach(t => {
      const pinned = pins.includes(t.id);
      const el = document.createElement("div"); el.className = "titem" + (t.id === tCur ? " cur" : "") + (pinned ? " pinned" : "");
      const pr = t.progress && t.progress[1] ? t.progress[0] / t.progress[1] : 0;
      el.innerHTML = `<b></b><span><i class="badge ${t.status}">${t.status_ru}</i>${tsince(t.created)}${t.project ? " · код" : ""}${t.parent ? " · часть задачи" : ""}</span>` +
        (["running", "waiting", "sleeping"].includes(t.status) || pr ? `<i class="tbar${t.status === "running" ? " live" : ""}"><b style="width:${Math.max(3, (t.status === "done" ? 1 : pr) * 100)}%"></b></i>` : "");
      $("b", el).textContent = t.title; el.onclick = () => openTask(t.id);
      const pb = document.createElement("button"); pb.className = "tpin"; pb.type = "button";
      pb.title = pinned ? "Открепить" : "Закрепить сверху"; pb.setAttribute("aria-label", pb.title); pb.setAttribute("aria-pressed", String(pinned));
      pb.innerHTML = '<svg viewBox="0 0 24 24"><path d="M9 3.5h6l-1 5.5 3.5 3.5v1.5h-11V12.5L10 9z"/><path d="M12 14v6.5"/></svg>';
      pb.onclick = (e) => { e.stopPropagation(); taskPin(t.id, !pinned, pins); };
      el.appendChild(pb); box.appendChild(el);
    });
    if (!tCur && list.length) openTask(list[0].id);
    $("#t-llm").innerHTML = `<option value="">Та же, что для разговора</option>` + Object.entries(S.llm.profiles || {}).map(([k, p]) => `<option value="${k}">${escH(p.name || k)}</option>`).join("");
    $("#t-llm").value = S.tasks && S.tasks.llm || "";
    $("#t-judge").innerHTML = `<option value="">Та же, что для задач</option>` + Object.entries(S.llm.profiles || {}).map(([k, p]) => `<option value="${k}">${escH(p.name || k)}</option>`).join("");
    $("#t-judge").value = S.tasks && S.tasks.judge_llm || "";
    const bs = $("#t-budget"), bv = String(+(S.tasks && S.tasks.budget_tokens) || 0);   // выпуск 7: бюджет задачи в токенах
    if (![...bs.options].some(o => o.value === bv)) bs.add(new Option(`${Math.round(+bv / 1000)} тыс. токенов`, bv));
    bs.value = bv;
  } catch (e) { toast(e.message); }
}
function renderDiff(d) {
  return `<div class="diff">${d.split("\n").map(l => { const c = l.startsWith("diff --git") ? "file" : l.startsWith("@@") ? "hunk" : l.startsWith("+") && !l.startsWith("+++") ? "add" : l.startsWith("-") && !l.startsWith("---") ? "del" : "";
    return c === "file" ? `<div class="file">${escH(l.replace(/^diff --git a\/(.*) b\/.*/, "$1"))}</div>` : (l.startsWith("index ") || l.startsWith("+++") || l.startsWith("---")) ? "" : `<div class="${c}">${escH(l) || " "}</div>`; }).join("")}</div>`;
}
/* «Задачи на часы»: сколько идёт и сколько примерно осталось — по среднему времени на пункт плана (после двух пунктов) */
function tDur(m) { m = Math.max(0, Math.round(m)); return m < 60 ? `${m} мин` : `${Math.floor(m / 60)} ч${m % 60 ? " " + (m % 60) + " мин" : ""}`; }
function tEta(t, mins) {
  const p = t.progress || [0, 0];
  if (!p[1] || p[0] < 2 || p[0] >= p[1] || mins < 3) return "";
  const left = mins / p[0] * (p[1] - p[0]);
  return ` · осталось ≈ ${tDur(left < 60 ? Math.ceil(left / 5) * 5 : Math.ceil(left / 15) * 15)}`;
}
let tOpenedFor = "", tOutSel = "";   // для какой задачи уже выбрана вкладка по умолчанию; выбранный файл результата
/* план — живым чек-листом: сделано ✓, текущий пункт крутится, остальные ждут */
function renderPlan(text, live, activity) {
  const lines = (text || "").split("\n"), items = [], rest = [];
  lines.forEach(l => { const m = l.match(/^\s*[-*]\s*\[( |x|X)\]\s*(.*)$/); if (m) items.push({ done: m[1] !== " ", text: m[2] }); else if (!items.length) rest.push(l); });
  if (!items.length) return `<div class="md">${md(text || "План ещё не составлен.")}</div>`;
  const cur = live ? items.findIndex(x => !x.done) : -1, done = items.filter(x => x.done).length;
  return `<div class="md" style="margin-bottom:6px">${md(rest.join("\n").replace(/^#.*$/m, ""))}</div>
    <div class="pchk">${items.map((x, i) => `<div class="pi ${x.done ? "done" : i === cur ? "now" : ""}"><i></i><span>${md(x.text).replace(/^<p>|<\/p>\s*$/g, "")}</span></div>`).join("")}</div>
    ${live && activity ? `<div class="pnow"><i class="tspin"></i><span>${escH(activity)}</span></div>` : ""}
    <div class="hint" style="margin-top:8px">Выполнено ${done} из ${items.length}</div>`;
}
/* «Большие задачи», выпуск 4: список дел со статусами (задачи.json) вместо чек-листа — сделано ✓ с доказательством, в работе
   крутится, не сделать ✕ с причиной; ниже — критерии готовности (выпуск 3) с итогом проверки кодом перед «готово» */
const TODO_RU = { done: "сделано", in_progress: "в работе", pending: "ждёт", blocked: "не сделать" };
function renderTodos(t, live, activity) {
  const items = t.todos || [], crit = t.criteria || [];
  const done = items.filter(x => x.status === "done").length, blocked = items.filter(x => x.status === "blocked").length;
  const cls = (x) => x.status === "done" ? "done" : x.status === "in_progress" ? (live ? "now" : "ip") : x.status === "blocked" ? "blocked" : "";
  const fallback = !crit.length && ((t.plan || "").match(/Готово,? когда:?\**:?\s*(.+)/) || [])[1];
  return `<div class="pgoal">${md("**Цель:** " + (t.goal || "")).replace(/^<p>|<\/p>\s*$/g, "")}</div>
    <div class="pchk">${items.map(x => `<div class="pi ${cls(x)}" title="${TODO_RU[x.status] || ""}"><i></i><span><span>${md(x.text || "").replace(/^<p>|<\/p>\s*$/g, "")}</span>${x.evidence && ["done", "blocked"].includes(x.status) ? `<small>${escH(x.evidence)}</small>` : ""}</span></div>`).join("")}</div>
    ${live && activity ? `<div class="pnow"><i class="tspin"></i><span>${escH(activity)}</span></div>` : ""}
    <div class="hint" style="margin-top:8px">Выполнено ${done} из ${items.length}${blocked ? ` · не сделать: ${blocked}` : ""}</div>
    ${crit.length ? `<div class="pcrit-h">Готово, когда</div><div class="pcrit">${crit.map(c => `<div class="pc ${c.ok === true ? "ok" : c.ok === false ? "bad" : ""}"><b>${c.ok === true ? "✓" : c.ok === false ? "✕" : "·"}</b><span>${escH(c.label || "")}${c.ok === false && c.detail ? `<small>${escH(c.detail)}</small>` : ""}</span></div>`).join("")}</div>`
      : fallback ? `<div class="pcrit-h">Готово, когда</div><div class="pcrit"><div class="pc"><b>·</b><span>${escH(fallback.replace(/\*+/g, ""))}</span></div></div>` : ""}`;
}
/* «Большие задачи», выпуск 6: помощники задачи — кто что делает. Части — отдельные задачи (по поручению: формат результата,
   бюджет шагов), «Открыть» ведёт в их карточку; разведчик (explore) и проверяющий (verify) работают в потоке задачи с её
   правами и своим окном. Токены помощников входят в общий счёт задачи. */
const HLP_ICON = { part: '<path d="M10 3h4v3a2 2 0 1 0 4 0V3h3v7h-3a2 2 0 1 0 0 4h3v7h-7v-3a2 2 0 1 0-4 0v3H3v-7h3a2 2 0 1 0 0-4H3V3h7z"/>',
  explore: '<circle cx="10.5" cy="10.5" r="6"/><path d="M15 15l5.5 5.5"/>', verify: '<path d="M12 3l7 3v5c0 4.5-3 8.3-7 10-4-1.7-7-5.5-7-10V6l7-3z"/><path d="M8.5 12l2.5 2.5 4.5-5"/>' };
const HLP_RU = { part: "Часть", explore: "Разведчик", verify: "Проверяющий" };
const tTok = (n) => n >= 1e6 ? `${(n / 1e6).toFixed(1).replace(".0", "").replace(".", ",")} млн` : n >= 1000 ? `${Math.round(n / 1000)} тыс.` : String(n);
function renderHelpers(t) {
  const hs = t.helpers || []; if (!hs.length) return "";
  const busy = hs.filter(h => ["running", "waiting"].includes(h.status)).length, tok = hs.reduce((a, h) => a + (h.tokens || 0), 0);
  const row = (h) => {
    const st = h.kind === "verify" && h.status === "done" ? (h.verdict === "revise" ? "warn" : h.verdict === "ok" ? "ok" : "") : h.status;
    const what = h.kind === "part" ? h.what : h.what === "итог" ? "итог перед «готово»" : h.what;
    const note = h.kind === "verify" && h.verdict === "revise" && h.note ? h.note : h.kind === "part" && h.status === "running" ? h.activity : h.status === "failed" ? h.note : "";
    const meta = [h.kind === "verify" && h.status === "done" ? (h.verdict === "ok" ? "подтвердил" : h.verdict === "revise" ? "вернул на доработку" : "не решил") : h.status_ru,
      h.steps ? `шагов ${h.steps}${h.limit ? " из " + h.limit : ""}` : "", h.tokens ? `${tTok(h.tokens)} токенов` : ""].filter(Boolean).join(" · ");
    return `<div class="hlp ${h.kind} ${st}"><i class="hk${h.status === "running" ? " live" : ""}"><svg viewBox="0 0 24 24">${HLP_ICON[h.kind] || ""}</svg></i>
      <span><b>${escH(h.kind === "part" ? h.title : HLP_RU[h.kind] || h.kind)}</b>${h.kind === "part" ? `<u>часть</u>` : ""}<small>${escH(what || "")}</small>${note ? `<small class="hn">${escH(note)}</small>` : ""}</span>
      <em>${escH(meta)}</em>${h.task ? `<button class="btn small" data-hopen="${escH(h.task)}">Открыть</button>` : ""}</div>`;
  };
  return `<div class="pcrit-h">Помощники<span class="hsum">${busy ? `работают ${busy} · ` : ""}${hs.length} · ${tTok(tok)} токенов</span></div>
    <div class="helpers">${hs.slice(0, 12).map(row).join("")}</div>${hs.length > 12 ? `<p class="hint">И ещё ${hs.length - 12} — в журнале задачи.</p>` : ""}`;
}
/* «Большие задачи», выпуск 5: песочница кода и снимки outputs/ — «Откатить к шагу N» возвращает результаты к виду перед
   шагом N (лишнее уходит), текущий вид перед этим сохраняется снимком «перед откатом» — его можно вернуть. Пока задача
   работает, откатывать нельзя (ядро откажет): она пишет в те же файлы. */
const tKB = (b) => b >= 1048576 ? `${(b / 1048576).toFixed(1).replace(".0", "")} МБ` : b >= 1024 ? `${Math.round(b / 1024)} КБ` : `${b} байт`;
const tFiles = (n) => `${n} ${n % 10 === 1 && n % 100 !== 11 ? "файл" : [2, 3, 4].includes(n % 10) && ![12, 13, 14].includes(n % 100) ? "файла" : "файлов"}`;
const SBX_RU = { bwrap: ["Песочница", "Код задачи пишет только в её папку и не видит ваших личных папок."],
  landlock: ["Защита ядра", "Код задачи пишет только в её папку и не видит ваших личных папок (Landlock), но это не полная песочница — поэтому код и команды задачи запускаются с вашего разрешения. Полная — с bubblewrap."],
  guard: ["Охрана кода", "Защищает от случайных ошибок кода, но не от нарочного взлома — поэтому код и команды задачи запускаются только с вашего разрешения. Настоящая песочница появится, если поставить bubblewrap."],
  off: ["Без песочницы", "Код задачи запускается только с вашего разрешения."] };
function renderSnaps(t, live) {
  const sb = t.sandbox || {}, snaps = t.snaps || [], ru = SBX_RU[sb.mode];
  const head = ru ? `<div class="sbx${sb.mode === "bwrap" ? " real" : ""}"><b>${ru[0]}</b><span>${ru[1]}</span></div>
    <div class="switch slim"><div>Интернет для кода задачи<span>Скрипты и команды получат ${escH(sb.net_note || "сеть")}. Поиск и чтение страниц работают и без этого.</span></div><label class="tg"><input type="checkbox" id="t-net"${sb.net ? " checked" : ""}><i></i></label></div>` : "";
  if (!snaps.length) return head + `<div class="fempty">Снимков пока нет: перед каждой записью в результаты задача запоминает их, и испорченное можно вернуть.</div>`;
  return head + `<div class="pcrit-h">Снимки результатов</div><div class="snaps">${snaps.map(x => `<div class="snap${x.kind === "step" ? "" : " undo"}">
      <span><b>${x.kind === "step" ? `Перед шагом ${x.step}` : "Перед откатом"}</b><small>${escH(tsince(x.time))} · ${x.files ? `${tFiles(x.files)}, ${tKB(x.bytes)}` : "пусто"}${x.why && x.kind === "step" ? " · " + escH(x.why) : ""}</small></span>
      <button class="btn small" data-snap="${x.kind === "step" ? "s" + x.step : "q" + x.seq}"${live ? " disabled title=\"Сначала остановите задачу\"" : ""}>${x.kind === "step" ? `Откатить к шагу ${x.step}` : "Вернуть как было"}</button></div>`).join("")}</div>
    <p class="hint">Откат меняет только папку результатов (outputs). Текущий вид перед откатом тоже сохраняется — откат можно отменить.</p>`;
}
function wireSnaps(t) {
  if ($("#t-net")) $("#t-net").onchange = (e) => core.call("task_net", { id: t.id, on: e.target.checked }).then(() => openTask(t.id)).catch(err => toast(err.message));
  $$("#t-view [data-snap]").forEach(b => b.onclick = async () => {
    const k = b.dataset.snap, step = k[0] === "s" ? +k.slice(1) : null;
    if (!await ask(step !== null ? `Вернуть результаты к виду перед шагом ${step}? Текущий вид сохранится снимком.` : "Вернуть результаты к виду перед откатом?")) return;
    try { toast(await core.call("task_rewind", step !== null ? { id: t.id, step } : { id: t.id, seq: +k.slice(1) }), 6000); openTask(t.id); } catch (e) { toast(e.message, 7000); }
  });
}
const OUT_ICON = { html: "🌐", htm: "🌐", pdf: "📕", png: "🖼", jpg: "🖼", jpeg: "🖼", webp: "🖼", svg: "🖼", md: "📝", txt: "📝", srt: "💬",
                   csv: "📊", xlsx: "📊", docx: "📄", pptx: "📽", mp3: "🎵", wav: "🎵", mp4: "🎬", zip: "🗜" };
/* Результат показывается прямо с диска (file://): # и ? в имени файла иначе читаются как якорь и строка запроса;
   t.dir — абсолютный путь ядра, в Windows с буквой диска и «\» -> file:///C:/… */
function outUrl(t, rel) { const p = (t.dir + "/" + rel).replace(/\\/g, "/"); return "file://" + (p.startsWith("/") ? "" : "/") + encodeURI(p).replace(/#/g, "%23").replace(/\?/g, "%3F"); }
/* Картинки — с диска (file://; скрипты в <img> не работают). Windows: страницы студии отдаёт http://127.0.0.1 (ui/app.py,
   _url), а со страницы http браузер не загружает file:// — там SVG берём текстом, картинку покажет своя программа.
   Страницы (HTML) — всегда текстом в safeFrame (core.js). */
const OUT_FILE_OK = location.protocol === "file:";
function renderOutputs(t) {
  const outs = t.outputs || []; if (!outs.find(o => o.path === tOutSel)) tOutSel = (outs[outs.length - 1] || {}).path || "";
  return `<div class="outs">${outs.slice().reverse().map(o => { const ext = o.path.split(".").pop().toLowerCase();
      return `<button class="oi${o.path === tOutSel ? " on" : ""}" data-p="${escH(o.path)}"><b>${OUT_ICON[ext] || "📎"}</b><span>${escH(o.title || o.path)}<small>${escH(o.path)}</small></span></button>`; }).join("")}</div>
    <div class="opane"><div class="obar"><span id="o-name"></span><span style="flex:1"></span>
      <button class="btn small" id="o-full">На весь экран</button><button class="btn small" id="o-open">Открыть</button><button class="btn small" id="o-dir">Папка</button>
      <button class="btn small primary" id="o-dl">Скачать</button><button class="btn small primary" id="o-pdf">PDF</button></div>
      <div id="o-view"></div></div>`;
}
async function wireOutputs(t) {
  const rel = tOutSel; if (!rel) return;
  const dirRel = "Задачи/" + t.dir.replace(/\\/g, "/").split("/Задачи/").pop();   // ws_* принимают пути от корня папки ассистента
  $$("#t-view .oi").forEach(b => b.onclick = () => { tOutSel = b.dataset.p; openTask(t.id); });
  $("#o-name").textContent = rel;
  $("#o-open").onclick = () => core.call("ws_open", { path: dirRel + "/" + rel }).catch(e => toast(e.message));
  const ext0 = rel.split(".").pop().toLowerCase(), page = ["html", "htm"].includes(ext0);
  $("#o-dl").textContent = page ? "Скачать HTML" : "Скачать";
  $("#o-pdf").style.display = page || ext0 === "md" ? "" : "none";
  const dl = async (fmt, b) => {                      // копия в «Загрузки»; PDF печатает браузер компьютера без окон (core/export.py)
    const was = b.textContent; b.disabled = true; b.textContent = fmt === "pdf" ? "Делаю PDF…" : "Сохраняю…";
    try { const r = await core.call("task_export", { id: t.id, path: rel, fmt }); toast(`Сохранено в «${r.dir.split(/[\\/]/).pop()}»: ${r.name}`, 5000); }
    catch (e) { toast(e.message, 7000); }
    finally { b.disabled = false; b.textContent = was; }
  };
  $("#o-dl").onclick = () => dl(page ? "html" : "file", $("#o-dl"));
  $("#o-pdf").onclick = () => dl("pdf", $("#o-pdf"));
  $("#o-dir").onclick = () => core.call("ws_open", { path: dirRel + "/" + rel.split("/").slice(0, -1).join("/") }).catch(e => toast(e.message));
  const ext = rel.split(".").pop().toLowerCase(), v = $("#o-view");
  $("#o-full").style.display = ["html", "htm", "png", "jpg", "jpeg", "webp", "svg"].includes(ext) ? "" : "none";
  $("#o-full").onclick = () => { const el = v.firstElementChild; if (el) (el.requestFullscreen || el.webkitRequestFullscreen || (() => {})).call(el); };
  const openHint = `<p class="hint" style="padding:30px">Этот файл открывается в своей программе — нажмите «Открыть».</p>`;
  if (["html", "htm"].includes(ext)) {
    // на всех системах — текстом в srcdoc без allow-same-origin и с CSP (safeFrame, core.js): у страницы нет прав студии
    try {
      const f = await core.call("ws_read", { path: dirRel + "/" + rel });
      v.innerHTML = f.truncated ? '<p class="hint">Показано начало страницы — целиком она откроется по кнопке «Открыть».</p>' : "";
      v.prepend(safeFrame(f.text || ""));
    } catch (e) { v.innerHTML = `<p class="hint">${escH(e.message)}</p>`; }
  } else if (["png", "jpg", "jpeg", "webp", "svg", "gif"].includes(ext)) {
    if (OUT_FILE_OK) v.innerHTML = `<img src="${outUrl(t, rel)}" alt="">`;
    else if (ext === "svg") try {
      const f = await core.call("ws_read", { path: dirRel + "/" + rel });
      v.innerHTML = `<img alt="">`; $("img", v).src = URL.createObjectURL(new Blob([f.text || ""], { type: "image/svg+xml" }));
    } catch (e) { v.innerHTML = `<p class="hint">${escH(e.message)}</p>`; }
    else v.innerHTML = openHint;
  } else if (["md", "txt", "srt", "csv", "json", "py", "js", "css"].includes(ext)) {
    try { const f = await core.call("ws_read", { path: dirRel + "/" + rel }); v.innerHTML = ext === "md" ? `<div class="md otext">${md(f.text || "")}</div>` : `<pre class="otext"></pre>`; if (ext !== "md") $("pre", v).textContent = f.text || ""; }
    catch (e) { v.innerHTML = `<p class="hint">${escH(e.message)}</p>`; }
  } else v.innerHTML = openHint;
}
async function openTask(id) {
  tCur = id;
  try {
    const t = await core.call("task_get", { id });
    // карточка перерисовывается целиком на каждое событие задачи — запоминаем набранный текст и фокус полей
    const keep = tOpenedFor === id ? ["t-msg", "t-ans"].map(k => [k, $("#" + k) ? $("#" + k).value : "", document.activeElement && document.activeElement.id === k]) : [];
    const outs = t.outputs || [];
    const nbFacts = (t.notebook || "").split("\n").filter(l => /^\s*[-*]\s+\S/.test(l)).length;
    const tabs = [["plan", "План"]].concat(nbFacts ? [["notebook", `Блокнот (${nbFacts})`]] : []).concat(outs.length ? [["results", `Результаты (${outs.length})`]] : []).concat([["journal", "Журнал"]])
      .concat(t.project ? [["diff", `Изменения${t.changes ? " (" + t.changes.length + ")" : ""}`]] : []).concat([["snaps", `Снимки${(t.snaps || []).length ? " (" + t.snaps.length + ")" : ""}`]]).concat(t.summary ? [["summary", "Итог"]] : []);
    if (tOpenedFor !== id) { tOpenedFor = id; tTab = outs.length && t.status === "done" ? "results" : t.summary ? "summary" : "plan"; }
    if (!tabs.find(x => x[0] === tTab)) tTab = t.summary ? "summary" : "plan";
    const acts = [];
    if (t.status === "sleeping") acts.push(`<button class="btn primary" data-a="task_resume">Продолжить сейчас</button>`);
    if (["running", "waiting", "sleeping"].includes(t.status)) acts.push(`<button class="btn" data-a="task_stop">Остановить</button>`);
    if (["paused", "stopped", "failed"].includes(t.status)) acts.push(`<button class="btn primary" data-a="task_resume">Продолжить</button>`);
    if (t.project && t.changes && t.changes.length && !["running", "waiting", "sleeping"].includes(t.status)) acts.push(`<button class="btn primary" data-a="task_accept">Принять изменения</button><button class="btn" data-a="task_discard">Отклонить</button>`);
    acts.push(`<button class="btn danger" data-a="task_delete">Удалить</button>`);
    const prog = t.progress && t.progress[1] ? ` · план ${t.progress[0]}/${t.progress[1]}` : "";
    let body = "";
    if (tTab === "plan") body = ((t.todos || []).length ? renderTodos(t, ["running", "waiting"].includes(t.status), t.activity) : renderPlan(t.plan, ["running", "waiting"].includes(t.status), t.activity)) + renderHelpers(t);
    if (tTab === "results") body = renderOutputs(t);
    if (tTab === "notebook") body = `<div class="md">${md(t.notebook)}</div><p class="hint">Блокнот — память задачи: факты, номера, договорённости. Ассистент ведёт его сам и сверяется с ним на каждом шаге.</p>`;
    if (tTab === "journal") body = tJournal(t.journal);
    if (tTab === "summary") body = `<div class="md">${md(t.summary)}</div>`;
    if (tTab === "snaps") body = renderSnaps(t, ["running"].includes(t.status));
    if (tTab === "diff") body = t.diff ? renderDiff(t.diff) : `<div class="fempty">${t.code_state === "accepted" ? "Изменения уже перенесены в проект." : t.code_state === "discarded" ? "Изменения отклонены." : "Изменений пока нет."}</div>`;
    const pr = t.status === "done" ? 1 : (t.progress && t.progress[1] ? t.progress[0] / t.progress[1] : 0);
    const mins = Math.max(0, Math.round((Date.now() - new Date(t.created)) / 60000));
    const live = ["running", "waiting"].includes(t.status);
    $("#t-view").innerHTML = `<div class="fhead"><div class="t"><b></b><span><i class="badge ${t.status}">${t.status_ru}</i>шагов ${t.steps}${prog}${t.metrics ? " · " + escH(t.metrics) : ""}${t.budget_pct != null ? ` · <b class="tbud${t.budget_pct >= 80 ? " over" : t.budget_pct >= 50 ? " half" : ""}">бюджет ${t.budget_pct} %</b>` : ""}${t.project ? " · " + escH(t.project) : ""}</span></div></div>
      <div class="tprog${live ? " live" : ""}"><div class="bar"><b style="width:${Math.max(2, pr * 100)}%"></b></div>
        <div class="tline">${live ? `<i class="tspin"></i>` : ""}<span>${t.status === "done" ? "готово" : live ? (escH(t.activity) || "думает…") : t.status_ru}</span><em>${t.progress && t.progress[1] ? `${t.progress[0]} из ${t.progress[1]} пунктов плана · ` : ""}${live ? `идёт ${tDur(mins)}` + tEta(t, mins) : ""}</em></div></div>
      ${t.error ? `<p class="res bad" style="margin-bottom:10px">${escH(t.error)}</p>` : ""}
      ${t.status === "sleeping" ? `<div class="twait">⏳ <b>${escH(t.status_ru)}</b>${t.wait_reason ? " — " + escH(t.wait_reason) : ""}. Напишите задаче ниже — продолжит сразу.</div>` : ""}
      ${t.status === "waiting" ? `<div class="tq"><b>Вопрос:</b> ${escH(t.question)}<div class="actions" style="margin-top:8px"><input type="text" id="t-ans" placeholder="Ваш ответ" style="flex:1"><button class="btn primary" id="t-ansgo">Ответить</button></div></div>` : ""}
      <div class="tabs">${tabs.map(([k, n]) => `<button data-tab="${k}" class="${k === tTab ? "on" : ""}">${n}</button>`).join("")}</div>${body}
      ${t.status !== "waiting" ? `<div class="tmsg"><input type="text" id="t-msg" placeholder="${t.status === "done" ? "Дополнить задачу: что ещё сделать…" : "Написать задаче: новые сведения, уточнение, просьба…"}"><button class="btn" id="t-msggo">Отправить</button></div>` : ""}
      <div class="actions">${acts.join("")}</div>`;
    $("#t-view .fhead b").textContent = t.title;
    keep.forEach(([k, v, f]) => { const el = $("#" + k); if (el && v) el.value = v; if (el && f) el.focus(); });
    if ($("#t-msggo")) {
      const send = () => { const v = $("#t-msg").value.trim(); if (!v) return;
        core.call("task_tell", { id, text: v }).then(() => { toast("Передал задаче"); loadTasks(); openTask(id); }).catch(e => toast(e.message)); };
      $("#t-msggo").onclick = send; $("#t-msg").onkeydown = (e) => { if (e.key === "Enter") send(); };
    }
    if (tTab === "results") wireOutputs(t);
    if (tTab === "snaps") wireSnaps(t);
    $$("#t-view [data-tab]").forEach(b => b.onclick = () => { tTab = b.dataset.tab; openTask(id); });
    $$("#t-view [data-hopen]").forEach(b => b.onclick = () => { tTab = "plan"; openTask(b.dataset.hopen); });
    $$("#t-view [data-a]").forEach(b => b.onclick = async () => {
      if (b.dataset.a === "task_delete" && !await ask("Удалить задачу вместе с её папкой?")) return;
      if (b.dataset.a === "task_discard" && !await ask("Отклонить изменения? Рабочая копия будет удалена.")) return;
      try { const r = await core.call(b.dataset.a, { id }); if (typeof r === "string") toast(r); if (b.dataset.a === "task_delete") tCur = ""; loadTasks(); if (b.dataset.a !== "task_delete") openTask(id); else $("#t-view").innerHTML = ""; } catch (e) { toast(e.message); }
    });
    if ($("#t-ansgo")) $("#t-ansgo").onclick = () => core.call("task_answer", { id, text: $("#t-ans").value }).then(() => openTask(id)).catch(e => toast(e.message));
    $$("#t-list .titem").forEach(el => el.classList.toggle("cur", $("b", el).textContent === t.title));
  } catch (e) { toast(e.message); }
}
$("#t-new").onclick = () => { $("#t-form").style.display = ""; $("#t-goal").focus(); };
/* Идеи для первой задачи: пустая страница сразу показывает, на что способна мастерская.
   Поля: название, подпись, текст поручения (подставляется в форму), примерное время, содержимое SVG-значка 24×24. */
const T_IDEAS = [
  ["Презентация", "6 слайдов о вашем проекте — файл в «Результатах».", "Сделай презентацию на 6 слайдов о том, что умеет голосовой ассистент Dewiar: для кого он, главные возможности, как начать. Сохрани в папку «Результаты».", "~3 мин",
   '<rect x="3" y="4" width="18" height="12" rx="2"/><path d="M12 16v4M8 20h8M7 12l3-3 2 2 4-4"/>'],
  ["Сравнить и выбрать", "Таблица вариантов с плюсами, минусами и выводом.", "Сравни три хороших ноутбука до 1000 долларов для учёбы и работы: таблица с характеристиками, плюсы и минусы, и что выбрать. Оформи красивой страницей.", "~4 мин, нужен интернет",
   '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>'],
  ["Фильмы на вечер", "Подборка карточками: постер, год, о чём фильм.", "Подбери 8 фильмов на вечер в жанре фантастика — хорошие и не самые очевидные. Покажи красиво карточками: название, год, о чём, почему стоит посмотреть.", "~3 мин, нужен интернет",
   '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 9h18M7 5l2 4M12 5l2 4M17 5l2 4"/>'],
  ["Расходы за месяц", "Таблица Excel и диаграмма по категориям.", "Собери мои расходы и доходы за этот месяц в таблицу Excel: по дням и по категориям, с итогами и диаграммой. Сохрани в «Результаты».", "~2 мин",
   '<path d="M12 3v9l6 4"/><circle cx="12" cy="12" r="9"/>'],
  ["План поездки", "Маршрут по дням, бюджет и список вещей.", "Составь план поездки в Санкт-Петербург на 3 дня в октябре: маршрут по дням, где поесть, примерный бюджет и список вещей. Оформи страницей, которую удобно открыть с телефона.", "~4 мин, нужен интернет",
   '<path d="M9 18l-6 3V6l6-3 6 3 6-3v15l-6 3-6-3z"/><path d="M9 3v15M15 6v15"/>'],
  ["Калькулятор", "Готовая страница: ввели числа — получили ответ.", "Сделай калькулятор ипотеки отдельной страницей: сумма, ставка, срок, первый взнос — ежемесячный платёж, переплата и график платежей.", "~3 мин",
   '<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M8 7h8M8 11h2M12 11h2M16 11h0M8 15h2M12 15h2M16 15v3M8 18h6"/>'],
];
$("#t-ideas-grid").innerHTML = T_IDEAS.map((x, i) => `<button class="tidea" data-i="${i}"><svg viewBox="0 0 24 24">${x[4]}</svg><b>${x[0]}</b><span>${x[1]}</span><em>${x[3]}</em></button>`).join("");
$$("#t-ideas-grid .tidea").forEach(b => b.onclick = () => {
  const x = T_IDEAS[+b.dataset.i]; $("#t-form").style.display = ""; $("#t-goal").value = x[2]; $("#t-title").value = x[0];
  $("#t-form").scrollIntoView({ behavior: "smooth", block: "center" }); $("#t-goal").focus();
});
$("#t-cancel").onclick = () => { $("#t-form").style.display = "none"; };
$("#t-pick").onclick = async () => { const a = api(); if (!a) return toast("Выбор папки доступен в окне студии"); const p = await a.pick_folder(); if (p) $("#t-proj").value = p; };
/* Идея №164: файлы к новой задаче — скрепкой, перетаскиванием на форму или Ctrl+V в поле (как в «Чате»); ядро кладёт их во
   «Входящие» папки задачи (tasks._inbox_files), у документов рядом — их текст, и говорит задаче начать с них. */
let tAtts = [];
const T_FMAX = 11e6;
const tB64 = (file) => new Promise((ok, bad) => { const r = new FileReader(); r.onload = () => ok(r.result); r.onerror = bad; r.readAsDataURL(file); });
const tSize = (n) => n < 1024 * 1024 ? Math.max(1, Math.round(n / 1024)) + " КБ" : (n / 1048576).toFixed(1).replace(".", ",") + " МБ";
async function tAddFiles(list) {
  for (const f of list) {
    if (f.size > T_FMAX) { toast(`«${f.name}» больше 11 МБ — положите его в папку и дайте задаче папку`, 4000); continue; }
    try { tAtts.push({ name: f.name || "файл", size: f.size, img: /^image\//.test(f.type) ? URL.createObjectURL(f) : "", b64: await tB64(f) }); }
    catch (e) { toast(`«${f.name}»: ${e.message}`); }
  }
  tAtts = tAtts.slice(0, 10); tAttsRender();
}
function tAttsRender() {
  $("#t-atts").innerHTML = tAtts.map((a, i) => `<span class="ch-chip">${a.img ? `<img src="${escH(a.img)}" alt="">` : `<i>${escH((a.name.split(".").pop() || "").slice(0, 4).toUpperCase())}</i>`}<b title="${escH(a.name)}">${escH(a.name)}</b><small>${tSize(a.size)}</small><button type="button" data-i="${i}" title="Убрать" aria-label="Убрать ${escH(a.name)}">✕</button></span>`).join("")
    + (tAtts.length ? `<span class="t-atth">лягут во «Входящие» папки задачи</span>` : "");
  $$("#t-atts button").forEach(b => b.onclick = () => { const a = tAtts.splice(+b.dataset.i, 1)[0]; if (a && a.img) URL.revokeObjectURL(a.img); tAttsRender(); });
}
$("#t-file").onchange = (e) => { tAddFiles([...e.target.files]); e.target.value = ""; };
{ const f = $("#t-form");
  f.addEventListener("dragover", (e) => { if ([...(e.dataTransfer.types || [])].includes("Files")) { e.preventDefault(); f.classList.add("over"); } });
  f.addEventListener("dragleave", (e) => { if (!f.contains(e.relatedTarget)) f.classList.remove("over"); });
  f.addEventListener("drop", (e) => { if (!(e.dataTransfer.files || []).length) return; e.preventDefault(); f.classList.remove("over"); tAddFiles([...e.dataTransfer.files]); });
  $("#t-goal").addEventListener("paste", (e) => {
    const files = [...(e.clipboardData && e.clipboardData.items || [])].filter(x => x.kind === "file").map(x => x.getAsFile()).filter(Boolean);
    if (files.length) { e.preventDefault(); tAddFiles(files); }
  }); }
$("#t-go").onclick = async () => {
  const goal = $("#t-goal").value.trim(); if (!goal) return toast("Опишите, что сделать");
  const files = tAtts.map(a => ({ name: a.name, b64: a.b64 }));
  $("#t-go").disabled = true;
  try { const t = await core.call("task_create", { goal, title: $("#t-title").value.trim(), project: $("#t-proj").value.trim(), net: $("#t-netnew").checked, files });
    $("#t-form").style.display = "none"; $("#t-goal").value = ""; $("#t-netnew").checked = false; tAtts.forEach(a => a.img && URL.revokeObjectURL(a.img)); tAtts = []; tAttsRender();
    tCur = t.id; tTab = "plan"; loadTasks(); } catch (e) { toast(e.message); }
  finally { $("#t-go").disabled = false; }
};
$("#t-llm").onchange = () => save({ tasks: { llm: $("#t-llm").value } });
$("#t-judge").onchange = () => save({ tasks: { judge_llm: $("#t-judge").value } });
$("#t-budget").onchange = () => save({ tasks: { budget_tokens: +$("#t-budget").value } });
core.on("task", e => {                     // события идут потоком на каждый шаг — перерисовываем не чаще раза в 400 мс
  if (!$("#p-tasks").classList.contains("cur")) return;
  clearTimeout(tTimer); tTimer = setTimeout(() => { loadTasks(); if (tCur === e.task.id) openTask(tCur); }, 400);
});

/* ---------- обновления ---------- */
function renderUpdate(u) {
  if (!u) return;
  $("#ab-title").textContent = `Dewiar ${u.current}`;
  const a = u.available, d = u.downloading;
  const when = t => new Date(t * 1000).toLocaleString("ru-RU", { hour: "2-digit", minute: "2-digit", day: "numeric", month: "short" });
  // 0.82.2: скачивание идёт в фоне с ходом; фоновая проверка качает новую версию в своё (случайное) время — так и пишем
  $("#up-state").textContent = a ? `Доступна версия ${a.version}${a.date ? " от " + a.date : ""} — уже скачана и проверена.` :
    d ? `Скачиваю ${d.version} — ${d.pct | 0} %${d.from ? " (с " + d.from + ")" : ""}…` :
    !u.error && u.next && u.remote && u.next * 1000 > Date.now() ? `На сайте версия ${u.remote} — скачается сама около ${when(u.next)} (компьютеры качают в разное время, чтобы сайт не тормозил). Можно сейчас — «Проверить».` :
    u.error ? `Не удалось обновиться: ${u.error}` : u.checked ? `У вас последняя версия${u.remote ? " (на сайте — " + u.remote + ")" : ""}. Проверено ${new Date(u.checked * 1000).toLocaleString("ru-RU", { hour: "2-digit", minute: "2-digit", day: "numeric", month: "short" })}.` : "Проверка — через минуту после запуска и раз в 6 часов.";
  $("#up-notes").innerHTML = a && a.notes ? md(a.notes) : "";
  $("#up-install").style.display = a ? "" : "none";
  $("#up-install").onclick = async () => {
    const x = api(); if (!x) return toast("Обновление запускается из окна студии");
    // у окна нет install_update: оно запущено из ui/app.py без этого метода — нужен перезапуск интерфейса
    if (typeof x.install_update !== "function") { $("#up-state").textContent = "Закройте Dewiar (и виджет) и откройте снова — затем нажмите «Обновить»."; return; }
    updShow(a.version, "auth");
    try { const r = await x.install_update(a.path);
          if (!r.ok) return updShow(a.version, "error", r.error);
          if (r.started) updPoll(a.version); else updShow(a.version, "restart"); }
    catch (e) { updShow(a.version, "error", e.message); }
  };
}

/* Журнал задачи: сначала новое (идеи №81/82, 30.10: «когда шагов много, при входе видна первая запись — мотать вниз, чтобы
   увидеть, что происходит сейчас»). Записи — «**ЧЧ:ММ:СС** · …» (core/tasks.py journal); порядок — переключателем,
   выбор помнится на этом компьютере. */
const TJ_KEY = "dewiar_task_journal_order";
function tjOrder() { try { return localStorage.getItem(TJ_KEY) === "old" ? "old" : "new"; } catch (e) { return "new"; } }
function tJournal(text) {
  const raw = String(text || "").trim();
  if (!raw) return `<div class="fempty">Журнал пока пуст — записи появятся с первым шагом.</div>`;
  const parts = raw.split(/\n+(?=\*\*\d{1,2}:\d{2}:\d{2}\*\* · )/), ord = tjOrder();
  const list = ord === "new" ? parts.slice().reverse() : parts;
  return `<div class="tj-bar" role="group" aria-label="Порядок записей"><button type="button" class="tj-o${ord === "new" ? " on" : ""}" data-tj="new" aria-pressed="${ord === "new"}">Сначала новое</button>`
    + `<button type="button" class="tj-o${ord === "old" ? " on" : ""}" data-tj="old" aria-pressed="${ord === "old"}">По порядку</button><span>${parts.length} ${plural(parts.length, "запись", "записи", "записей")}</span></div>`
    + `<div class="md tj">${md(list.join("\n\n"))}</div>`;
}
document.addEventListener("click", (e) => {
  const b = e.target.closest && e.target.closest(".tj-o"); if (!b) return;
  try { localStorage.setItem(TJ_KEY, b.dataset.tj); } catch (x) { /* без памяти — только сейчас */ }
  const box = b.closest(".tj-bar").parentElement; if (tCur && typeof openTask === "function") openTask(tCur); else if (box) box.innerHTML = "";
});
