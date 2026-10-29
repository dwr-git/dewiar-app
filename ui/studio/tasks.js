/* Студия Dewiar, разделы «Задачи» и обновление в «О программе».
   Задачи — долгие поручения мастерской (core/tasks.py): список, карточка с вкладками (план, блокнот, результаты, журнал,
   изменения кода, итог), просмотр и выгрузка результатов, «идеи» для пустой страницы. Команды ядра: tasks_list, task_get,
   task_create, task_tell, task_answer, task_resume/stop/accept/discard/delete, task_export, ws_open, ws_read;
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
      el.innerHTML = `<b></b><span><i class="badge ${t.status}">${t.status_ru}</i>${tsince(t.created)}${t.project ? " · код" : ""}</span>` +
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
const OUT_ICON = { html: "🌐", htm: "🌐", pdf: "📕", png: "🖼", jpg: "🖼", jpeg: "🖼", webp: "🖼", svg: "🖼", md: "📝", txt: "📝", srt: "💬",
                   csv: "📊", xlsx: "📊", docx: "📄", pptx: "📽", mp3: "🎵", wav: "🎵", mp4: "🎬", zip: "🗜" };
/* Результат показывается прямо с диска (file://): # и ? в имени файла иначе читаются как якорь и строка запроса;
   t.dir — абсолютный путь ядра, в Windows с буквой диска и «\» -> file:///C:/… */
function outUrl(t, rel) { const p = (t.dir + "/" + rel).replace(/\\/g, "/"); return "file://" + (p.startsWith("/") ? "" : "/") + encodeURI(p).replace(/#/g, "%23").replace(/\?/g, "%3F"); }
/* Windows: страницы студии отдаёт http://127.0.0.1 (ui/app.py, _url), а со страницы http браузер не загружает file://
   («Not allowed to load local resource») — там страницу и SVG берём текстом через ws_read, картинку покажет своя программа */
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
    if (OUT_FILE_OK) v.innerHTML = `<iframe src="${outUrl(t, rel)}" sandbox="allow-scripts allow-same-origin allow-popups allow-forms"></iframe>`;
    else try {
      const f = await core.call("ws_read", { path: dirRel + "/" + rel });
      v.innerHTML = `<iframe sandbox="allow-scripts allow-popups allow-forms"></iframe>${f.truncated ? '<p class="hint">Показано начало страницы — целиком она откроется по кнопке «Открыть».</p>' : ""}`;
      $("iframe", v).srcdoc = f.text || "";
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
      .concat(t.project ? [["diff", `Изменения${t.changes ? " (" + t.changes.length + ")" : ""}`]] : []).concat(t.summary ? [["summary", "Итог"]] : []);
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
    if (tTab === "plan") body = renderPlan(t.plan, ["running", "waiting"].includes(t.status), t.activity);
    if (tTab === "results") body = renderOutputs(t);
    if (tTab === "notebook") body = `<div class="md">${md(t.notebook)}</div><p class="hint">Блокнот — память задачи: факты, номера, договорённости. Ассистент ведёт его сам и сверяется с ним на каждом шаге.</p>`;
    if (tTab === "journal") body = `<div class="md">${md(t.journal)}</div>`;
    if (tTab === "summary") body = `<div class="md">${md(t.summary)}</div>`;
    if (tTab === "diff") body = t.diff ? renderDiff(t.diff) : `<div class="fempty">${t.code_state === "accepted" ? "Изменения уже перенесены в проект." : t.code_state === "discarded" ? "Изменения отклонены." : "Изменений пока нет."}</div>`;
    const pr = t.status === "done" ? 1 : (t.progress && t.progress[1] ? t.progress[0] / t.progress[1] : 0);
    const mins = Math.max(0, Math.round((Date.now() - new Date(t.created)) / 60000));
    const live = ["running", "waiting"].includes(t.status);
    $("#t-view").innerHTML = `<div class="fhead"><div class="t"><b></b><span><i class="badge ${t.status}">${t.status_ru}</i>шагов ${t.steps}${prog}${t.project ? " · " + escH(t.project) : ""}</span></div></div>
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
    $$("#t-view [data-tab]").forEach(b => b.onclick = () => { tTab = b.dataset.tab; openTask(id); });
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
$("#t-go").onclick = async () => {
  const goal = $("#t-goal").value.trim(); if (!goal) return toast("Опишите, что сделать");
  try { const t = await core.call("task_create", { goal, title: $("#t-title").value.trim(), project: $("#t-proj").value.trim() });
    $("#t-form").style.display = "none"; $("#t-goal").value = ""; tCur = t.id; tTab = "plan"; loadTasks(); } catch (e) { toast(e.message); }
};
$("#t-llm").onchange = () => save({ tasks: { llm: $("#t-llm").value } });
core.on("task", e => {                     // события идут потоком на каждый шаг — перерисовываем не чаще раза в 400 мс
  if (!$("#p-tasks").classList.contains("cur")) return;
  clearTimeout(tTimer); tTimer = setTimeout(() => { loadTasks(); if (tCur === e.task.id) openTask(tCur); }, 400);
});

/* ---------- обновления ---------- */
function renderUpdate(u) {
  if (!u) return;
  $("#ab-title").textContent = `Dewiar ${u.current}`;
  const a = u.available;
  $("#up-state").textContent = a ? `Доступна версия ${a.version}${a.date ? " от " + a.date : ""} — уже скачана и проверена.` :
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
