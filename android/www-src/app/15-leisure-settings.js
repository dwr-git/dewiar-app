//@ Телефон и веб-версия, часть 15: «Досуг» и лист настроек.
//@ Собирается в android/assets/www/app.js (tools/app_join.py) — порядок частей = порядок исполнения; шапка «//@» в app.js не попадает.
/* ---------- «Досуг»: милые игры (24.10, владелец: «сидишь в очереди к врачу — „Лира, давай поиграем“ — и набор
   ненадоедающих миленьких игр прямо в интерфейсе Лиры») ----------
   Полка — лист «Досуг» (arcade/shelf.js — тот же список, что у компьютера), игра — во весь экран во фрейме (#gameov).
   «Игры» в игре (сообщение {arcade: 'home'}) и «Назад» телефона — снова полка; игра при этом выгружается (музыка
   не играет в фоне, рекорды игра хранит сама). Выключено в «Возможностях» — ни значка, ни листа. */
const ARC = "arcade/";
function playShelf() {
  if (!window.DewiarArcade) return;
  $("#play-body").innerHTML = `<p class="hint" style="margin:0 2px 12px">Игры на пару минут — касаниями, свайпами или с геймпада. Скажите «Лира, давай поиграем» — откроется эта полка.</p>`
    + `<div class="shelf">${DewiarArcade.html(ARC, { phone: true })}</div>`;
  $$("#play-body .ag").forEach(b => b.onclick = () => gameOpen(b.dataset.game));
}
function playOpen(game) {
  if (!feat("games")) { toast("«Досуг» выключен — включить: «Настройки» → «Возможности»", 4000); return false; }
  playShelf(); openSheet("#sh-play");
  const g = game && window.DewiarArcade && DewiarArcade.find(game);
  if (g && g.pc) toast(`«${g.name}» — пока только на компьютере: телефону эта игра тяжела`, 4500);
  else if (g) gameOpen(game);
  return true;
}
const gameOn = () => !$("#gameov").hidden;
/* «Морской бой» голосом (0.63): игра просит слушать ({arcade: 'listen'}) — слушаем один раз; пока она открыта, всё
   услышанное — ей ({arcade: 'heard'}, askHeard), а не модели; итог хода игра присылает ({arcade: 'say'}) — говорим. */
let gameCur = "";
const gameVoice = () => gameOn() && gameCur === "sea";
function gameHeard(t) { const f = $("#gamef"); setState("idle"); showYou(""); if (f.contentWindow) f.contentWindow.postMessage({ arcade: "heard", text: t || "" }, "*"); }
function gameOpen(id) {
  gameCur = id;
  if (state !== "idle") interrupt();                        // игра на весь экран — голос и прослушивание замолкают
  const f = $("#gamef"); f.src = DewiarArcade.url(ARC, id) + "?phone=1" + (document.body.classList.contains("light") ? "&light=1" : "");   // phone — без скруглений, кнопка «во весь экран»
  $("#gameov").hidden = false; closeSheets();
}
function gameClose(toShelf = true) {
  gameCur = "";
  const f = $("#gamef"); f.src = "about:blank"; $("#gameov").hidden = true; gameFull(false);
  if (toShelf && feat("games")) { playShelf(); openSheet("#sh-play"); }
}
let gameFullOn = false;
function gameFull(on) { if (gameFullOn === !!on) return; gameFullOn = !!on; document.body.classList.toggle("gamefull", gameFullOn); try { D.immersive(gameFullOn); } catch (e) { } }
window.addEventListener("message", (e) => { if (!e.data || e.source !== $("#gamef").contentWindow) return;
  if (e.data.arcade === "home") gameClose();
  else if (e.data.arcade === "full") gameFull(!!e.data.on);
  else if (e.data.arcade === "log") plog("warn", "🎮 игра: " + String(e.data.text || "").slice(0, 300));
  else if (e.data.arcade === "listen" && gameVoice()) { if (state !== "idle") interrupt(); listen(); }
  else if (e.data.arcade === "say" && gameVoice() && e.data.text) say(String(e.data.text).slice(0, 400)); });   // сбой или медленно — в журнал
$("#b-play").onclick = () => playOpen("");
/* «Возможности» (владелец 27.10: «выключил „Рядом“ и „Встречи“, а сердечко осталось — логика запутанная»): сердечко —
   это «Близкие» целиком (переписка и звонки), «Рядом» и «Встречи» — лишь вкладки внутри. Теперь у «Близких» свой
   переключатель (прячет сердечко), а вкладки — под ним, отступом. */
function featApply() { $("#b-close").hidden = !feat("close"); if (!feat("close") && $("#sh-close.on")) closeSheets();
  $("#b-play").hidden = true; /* 0.60: «Досуг» — в «Всё» */ document.body.classList.remove("has-play"); if (!feat("games") && gameOn()) gameClose(false); }
featApply();
/* Объявления для всех (24.10, владелец: «чтобы я для всех мог опубликовать, а у всех это на экранах всплыло»): кабинет →
   «Новости», здесь — ?p=/news без ключа раз в полчаса, при запуске и из уведомления службы «Близких» (CloseLive). Новое
   (номер больше S.annSeen) — карточка с фото, текстом и кнопкой ссылки, один раз; в разговоре и в игре — ждёт. */
let annAt = 0, annItems = [];
const annBase = () => { const c = syncCred(); return (c ? c.base : siteUrl("dwrapp/cloud.php")).split("?")[0]; };
async function annCheck(open) {
  if (!open && Date.now() - annAt < 30 * 60000) return; annAt = Date.now();
  try {
    const r = await http("GET", annBase() + "?p=/news", { timeout: 15000 });
    const d = JSON.parse(r.body || "{}"); annItems = (d.items || []).filter(n => n && n.id).sort((a, b) => b.id - a.id);
  } catch (e) { return; }
  const fresh = annItems.filter(n => n.id > (+S.annSeen || 0));
  if (open && annItems.length) annShow(fresh[0] || annItems[0]);
  else if (fresh.length && state === "idle" && !gameOn() && !$(".sheet.on")) annShow(fresh[0]);
}
function annShow(n) {
  const when = new Date(n.ts * 1000), esc = (t) => String(t || "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  $("#ann-body").innerHTML = (n.img ? `<img class="nw-img" src="${esc(annBase() + "?p=" + n.img)}" alt="">` : "")
    + `<p class="nw-k${n.level === "warn" ? " warn" : ""}">${n.level === "warn" ? "Предупреждение" : "Новость Dewiar"} · ${when.getDate()} ${MON_G[when.getMonth()]}</p>`
    + (n.title ? `<h2 id="an-h">${esc(n.title)}</h2>` : "") + (n.text ? `<p class="nw-t">${esc(n.text)}</p>` : "")
    + `<div class="nw-row">${n.link ? `<button class="btn pri" id="an-go">${esc(n.link_label || "Смотреть")}</button>` : ""}<button class="btn" id="an-ok">Понятно</button></div>`;
  const img = $("#ann-body .nw-img"); if (img) img.onerror = () => img.remove();
  // свои id: у «Что нового» тоже есть «Понятно» (#nw-ok) — если тот лист открывали, $("#nw-ok") находил его кнопку,
  // и «Понятно» объявления не закрывало ничего (№245)
  if ($("#an-go")) $("#an-go").onclick = () => D.openUrl(n.link);
  $("#an-ok").onclick = () => closeSheets();
  S.annSeen = Math.max(+S.annSeen || 0, n.id); saveS();
  openSheet("#sh-ann");
}
setTimeout(() => annCheck(false), 6000);
document.addEventListener("visibilitychange", () => { if (!document.hidden) setTimeout(() => annCheck(false), 1500); });
document.addEventListener("visibilitychange", () => { if (!document.hidden && clCur && $("#sh-close").classList.contains("on")) clSeen(clCur); });   // вернулись в открытую переписку — «прочитано»
setInterval(() => { if (!appAway()) annCheck(false); }, 5 * 60000);
const MON_G = MON;
function dayHuman(iso) { const d = new Date(iso + "T12:00"); if (isNaN(d)) return iso; const t = new Date(); const y = new Date(Date.now() - 864e5);
  const same = (a, b) => a.toDateString() === b.toDateString();
  return same(d, t) ? "Сегодня" : same(d, y) ? "Вчера" : `${d.getDate()} ${MON_G[d.getMonth()]}` + (d.getFullYear() !== t.getFullYear() ? ` ${d.getFullYear()}` : ""); }
function mdLite(t) {          // Markdown дневника → HTML: сначала экранируем, потом размечаем — пришедший текст не вставит свой HTML
  return esc(String(t || "").replace(/^# [^\n]*\n+/, "").replace(/\n{3,}/g, "\n\n").trim()).replace(/^## (.*)$/gm, "<h4>$1</h4>").replace(/^### (.*)$/gm, "<h5>$1</h5>")
    .replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>").replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<i>$2</i>").replace(/^_(.*)_$/gm, "<i>$1</i>").replace(/^- (.*)$/gm, "• $1").replace(/<\/(h4|h5)>\n+/g, "</$1>");
}
/* №586 (06.11): «возьми задачу» — «передана компьютеру, он уже берётся», а в «Задачах» пусто, и человек решил, что Лира
   врёт. Отправленная задача теперь видна сразу («ждёт, когда компьютер возьмёт»), пока её запись не пришла синхронизацией;
   не взяли за 10 минут — честно: компьютер выключен или Dewiar на нём не запущен; можно отдать облаку или убрать. */
const TASK_WAIT_MS = 10 * 60000;
function taskSentList() {
  const ts = Object.values(mind().tasks || {}), now = Date.now(), norm = (t) => String(t || "").toLowerCase().replace(/\s+/g, " ").trim().slice(0, 40);
  const left = qGet("tasksent").filter(x => now - (x.sent || 0) < 864e5 && !ts.some(t => norm(t.title) && (norm(t.title).startsWith(norm(x.title).slice(0, 25)) || norm(x.title).startsWith(norm(t.title).slice(0, 25)))));
  if (left.length !== qGet("tasksent").length) qSet("tasksent", left);
  return left;
}
function taskSentHtml(x) {
  const late = Date.now() - (x.sent || 0) > TASK_WAIT_MS;
  return `<div class="it tksent${late ? " late" : ""}"><div class="bd"><b>${esc(x.title)}</b><small>${late
    ? "Компьютер пока не взял задачу — он выключен или Dewiar на нём не запущен. Включите его — задача начнётся сама, или отдайте облаку Dewiar."
    : "⏳ Отправлена — ждёт, когда компьютер возьмёт (обычно меньше минуты)"}</small>${late ? `<div class="start"><button class="btn" data-tks-cloud="${esc(x.id)}">Сделать в облаке</button><button class="btn" data-tks-del="${esc(x.id)}">Убрать</button></div>` : ""}</div></div>`;
}
/* Задачи (большая работа на компьютере или в облаке) — в «Мой день» → «Сделанное»: там их и ищут, рядом со сделанным
   на телефоне. Поручить — taskToPc; ход и итог приходят синхронизацией (mind().tasks). */
function tasksHtml() {
  const m = mind(), on = !!(S.sync.on && syncChan());
  const ts = Object.entries(m.tasks).sort((a, b) => String(b[1].updated).localeCompare(String(a[1].updated))), q = qGet("taskq");
  if (!on) return `<div class="card"><b>Большие задачи</b><p class="hint">Презентации, отчёты, исследования делает компьютер с Dewiar или облако Dewiar — нужна синхронизация: тот же ключ Dewiar или вход аккаунтом, что на компьютере.</p><button class="btn p" id="so-sync">Открыть настройки</button></div>`;
  return `<div class="card"><label class="f"><span>Поручить большую задачу</span><textarea id="tk-goal" rows="4" placeholder="Например: «сделай презентацию о погоде на завтра» или «сравни 5 ноутбуков до 1500 рублей»"></textarea></label>
      <button class="btn p w" id="tk-go">Передать</button><p class="hint">${pcOnline() ? "Компьютер на связи — сделает он." : "Компьютер не на связи — сделает облако Dewiar: найдёт, напишет, соберёт файл. Программы на компьютере облако не запускает."}</p></div>`
    + q.map(x => `<div class="it"><div class="bd"><b>${esc(x.title)}</b><small>⏳ отправляю…</small></div></div>`).join("")
    + taskSentList().map(taskSentHtml).join("")
    + (ts.length ? `<div class="bugh">Задачи</div>` + ts.map(([id, t]) => `<details class="dday task ${esc(t.status || "")}"${t.status === "done" && (t.files || []).length ? " open" : ""}><summary><div class="bd"><b>${esc(t.title)}</b><small><span class="tst">${esc(TASK_RU[t.status] || t.status || "")}</span>${t.where === "cloud" ? " · в облаке" : ""}${t.activity && t.status === "running" ? " · " + esc(t.activity) : ""}</small></div></summary>
        <div class="dtext tk" translate="no">${t.question && t.status === "waiting" ? `<p><b>Вопрос:</b> ${esc(t.question)}</p>` : ""}${t.result ? `<p>${mdLite(t.result)}</p>` : `<p class="hint">${esc(t.goal || "")}</p>`}${t.error ? `<p style="color:#FF8FA8">${esc(t.error)}</p>` : ""}${taskFiles(t)}
        ${t.status === "waiting" && t.where !== "cloud" ? `<div class="tkans"><textarea rows="2" data-ans-t="${esc(id)}" placeholder="Ваш ответ — задача продолжит"></textarea><button class="btn p" data-ans="${esc(id)}">Ответить</button></div>` : ""}
        <button class="tkdel" data-del="${esc(id)}"><svg viewBox="0 0 24 24"><path d="M4.5 7h15M9.5 7V5a1 1 0 0 1 1-1h3a1 1 0 0 1 1 1v2M6.5 7l1 12.5a1.5 1.5 0 0 0 1.5 1.4h6a1.5 1.5 0 0 0 1.5-1.4L17.5 7"/></svg>Удалить задачу</button></div></details>`).join("") : "");
}
/* Удалить задачу, ответить на её вопрос — с телефона (24.10, владелец: «Лира замучила напоминанием про задачу
   „Исследование“… попросил удалить — она не умеет, на телефоне не понятно, где удалить»). Команда уходит компьютеру
   записью задачи с want (core/sync.py _task_want); у себя задача пропадает сразу и больше не возвращается (m.hid). */
function taskCmd(id, want, text) {
  const m = mind(), t = m.tasks[id];
  if (!t) throw new Error("такой задачи нет");
  const q = qGet("taskcmd").filter(x => !(x.id === id && x.want === want));
  q.push({ id, want, text: String(text || "").slice(0, 4000), ts: Date.now(), data: Object.assign({}, t, { chs: undefined }), chs: t.chs || [] });
  qSet("taskcmd", q);
  if (want === "delete") { delete m.tasks[id]; m.hid = Object.assign({}, m.hid, { [id]: Date.now() }); }
  else if (want === "answer") Object.assign(t, { status: "running", question: "" });
  saveMind(m); syncSoon();
  return t;
}
function taskFind(name) {
  const m = mind(), w = String(name || "").toLowerCase().trim(), all = Object.entries(m.tasks);
  return all.find(([, t]) => w && String(t.title || "").toLowerCase().includes(w)) || (all.filter(([, t]) => t.status === "waiting").length === 1 && !w ? all.find(([, t]) => t.status === "waiting") : null);
}
function wireTasks(box, again) {
  $$("[data-del]", box).forEach(b => b.onclick = (e) => { e.preventDefault(); const id = b.dataset.del, t = mind().tasks[id] || {};
    if (!confirm(`Удалить задачу «${t.title || ""}»? ${(t.files || []).length || (t.outputs || []).length ? "Её файлы на компьютере тоже удалятся. " : ""}Напоминаний о ней больше не будет.`)) return;
    try { taskCmd(id, "delete"); toast("Задача удалена"); again(); } catch (x) { toast(x.message); } });
  $$("[data-ans]", box).forEach(b => b.onclick = () => { const id = b.dataset.ans, ta = $(`[data-ans-t="${CSS.escape(id)}"]`, box), v = ta ? ta.value.trim() : "";
    if (!v) { if (ta) ta.focus(); return; }
    try { taskCmd(id, "answer", v); toast(pcOnline() ? "Ответ передан — задача продолжит" : "Ответ уйдёт, когда компьютер будет на связи", 3000); again(); } catch (x) { toast(x.message); } });
  // поле задачи — выше и растёт с текстом (владелец 29.10: «всё время хочется растянуть по высоте»)
  const tkG = $("#tk-goal");
  if (tkG) tkG.oninput = () => { tkG.style.height = "auto"; tkG.style.height = Math.min(Math.max(tkG.scrollHeight + 2, 120), innerHeight * 0.45) + "px"; };
  if ($("#tk-go")) $("#tk-go").onclick = () => { const g = $("#tk-goal").value.trim(); if (!g) return; try { taskToPc(g.slice(0, 60), g); toast(pcOnline() ? "Передано компьютеру" : "Делаю в облаке Dewiar — пришлю, когда будет готово", 3000); again(); } catch (e) { toast(e.message); } };
  if ($("#so-sync")) $("#so-sync").onclick = () => openSettings("more");
  $$("[data-tks-del]", box).forEach(b => b.onclick = () => { qSet("tasksent", qGet("tasksent").filter(x => x.id !== b.dataset.tksDel)); again(); });
  $$("[data-tks-cloud]", box).forEach(b => b.onclick = () => {      // компьютер так и не взял — облаку (новой заявкой только для облака)
    const x = qGet("tasksent").find(y => y.id === b.dataset.tksCloud); if (!x) return;
    qSet("tasksent", qGet("tasksent").filter(y => y.id !== x.id));
    // to «pc-cloud» — компьютеры её не берут (core/sync.py: чужой to), берёт исполнитель в облаке (cloud.php runner/pending)
    const q = qGet("taskq"); q.push({ id: "q" + Date.now().toString(36) + Math.random().toString(36).slice(2, 7), title: x.title, goal: x.goal, ts: Date.now(), cloud: true, to: "pc-cloud", from: devMyName() });
    qSet("taskq", q); syncSoon(); toast("Делаю в облаке Dewiar — пришлю, когда будет готово", 3000); again(); });
  wireFiles(box);
}
function renderSoul() {
  if (!["diary", "soul", "const"].includes(soulTab)) soulTab = "diary";      // «Задачи» переехали в «Мой день» → «Сделанное»
  const box = $("#soul-body"), m = mind(), on = !!(S.sync.on && syncChan());
  $$("#soul-tabs button").forEach(x => x.classList.toggle("on", x.dataset.t === soulTab));
  const off = on ? "" : `<div class="card"><b>Нужна синхронизация</b><p class="hint">Дневник и душу персонажей ведёт компьютер с Dewiar — они приходят сюда через синхронизацию. Нужен тот же ключ Dewiar или вход аккаунтом, что на компьютере.</p><button class="btn p" id="so-sync">Открыть настройки</button></div>`;
  if (soulTab === "diary") {
    // №904 (19.11, «открываю Душу — приложение замирает»): дневник за месяцы — сотни записей сразу целиком размечались в
    // страницу. Теперь — последние 30 дней («Показать ещё» — следующие), а текст дня размечается, только когда его открыли
    const days = Object.keys(m.diary).sort().reverse(), ins = m.insights, shown = +box.dataset.days || 30;
    const snip = (t) => { t = String(t || ""); return t.slice(0, 600).replace(/^#+ [^\n]*$/gm, "").replace(/[#*_]/g, "").replace(/\s+/g, " ").trim().slice(0, 120); };
    box.innerHTML = off + (ins && (ins.lines || []).length ? `<div class="card soulins"><small class="hint" style="margin:0">Выводы на завтра${ins.title ? " · «" + esc(ins.title) + "»" : ""}</small>${ins.lines.map(x => `<div>• ${esc(x)}</div>`).join("")}</div>` : "")
      + (days.length ? days.slice(0, shown).map(k => { const e = m.diary[k] || {}; const night = /## 🌙/.test(String(e.text || "").slice(0, 4000));
        return `<details class="dday" data-k="${esc(k)}"><summary><div class="tm">${esc(dayHuman(k))}</div><div class="bd"><b>${esc(e.title || (night ? "Ночная запись" : "Записи дня"))}</b><small>${esc(e.mood || "")}${e.mood ? " · " : ""}${esc(snip(e.text))}</small></div></summary><div class="dtext" translate="no"></div></details>`; }).join("")
        + (days.length > shown ? `<button class="btn w" id="so-more">Показать ещё (${days.length - shown})</button>` : "")
        : (on ? `<div class="empty">Дневник пока пуст.<br>Его ведёт ассистент на компьютере: ночью пишет о прожитом дне — о разговорах и там, и здесь.</div>` : ""));
    $$("details.dday", box).forEach(d => d.addEventListener("toggle", () => { const t = $(".dtext", d);
      if (d.open && t && !t.dataset.done) { t.dataset.done = "1"; t.innerHTML = mdLite(String((m.diary[d.dataset.k] || {}).text || "").slice(0, 60000)); } }));
    if ($("#so-more")) $("#so-more").onclick = () => { box.dataset.days = shown + 30; renderSoul(); };
  } else if (soulTab === "soul") {
    const p = persona(), names = [...new Set([p.name, ...Object.keys(m.souls)])];
    const cur = box.dataset.sname && names.includes(box.dataset.sname) ? box.dataset.sname : p.name;
    box.innerHTML = off + `<div class="card"><p class="hint" style="margin-top:0">Автопортрет, который персонаж пишет сам по своему дневнику (на компьютере — раз в неделю). Здесь его можно прочитать и поправить — правка уйдёт и на компьютер.</p>
      ${names.length > 1 ? `<div class="chips">${names.map(n => `<button class="chip${n === cur ? " on" : ""}" data-n="${esc(n)}">${esc(n)}</button>`).join("")}</div>` : ""}
      ${box.dataset.edit === "soul" ? `<label class="f"><span>Душа · ${esc(cur)}</span><textarea id="so-text" rows="14" placeholder="Душа появится, когда в дневнике наберётся пара ночных записей.">${esc((m.souls[cur] || {}).text || "")}</textarea></label>
      <div class="row2"><button class="btn p" id="so-save" style="flex:1">Сохранить</button><button class="btn" id="so-cancel" style="flex:1">Отмена</button></div>`
      : `${((m.souls[cur] || {}).text || "").trim() ? `<div class="dtext soulv" translate="no">${mdLite(m.souls[cur].text)}</div>` : `<div class="empty">Душа появится, когда в дневнике наберётся пара ночных записей.</div>`}
      <button class="btn w" id="so-edit">Изменить</button>`}</div>`;
    $$(".chip[data-n]", box).forEach(b => b.onclick = () => { box.dataset.sname = b.dataset.n; box.dataset.edit = ""; renderSoul(); });
    if ($("#so-edit")) $("#so-edit").onclick = () => { box.dataset.edit = "soul"; renderSoul(); };
    if ($("#so-cancel")) $("#so-cancel").onclick = () => { box.dataset.edit = ""; renderSoul(); };
    if ($("#so-save")) $("#so-save").onclick = () => { const mm = mind(); mm.souls[cur] = { text: $("#so-text").value, u: Date.now() }; saveMind(mm); syncSoon(); box.dataset.edit = ""; renderSoul(); toast("Душа сохранена"); };
  } else if (soulTab === "const") {
    box.innerHTML = off + `<div class="card"><p class="hint" style="margin-top:0">Принципы, которые все персонажи соблюдают всегда — с любым характером и настроением. Пишете вы; правка уйдёт и на компьютер.</p>
      ${box.dataset.edit === "const" ? `<label class="f"><span>Конституция</span><textarea id="co-text" rows="16" placeholder="Придёт с компьютера после синхронизации.">${esc(m.constitution || "")}</textarea></label>
      <div class="row2"><button class="btn p" id="co-save" style="flex:1">Сохранить</button><button class="btn" id="co-cancel" style="flex:1">Отмена</button></div>`
      : `${(m.constitution || "").trim() ? `<div class="dtext soulv" translate="no">${mdLite(m.constitution)}</div>` : `<div class="empty">Придёт с компьютера после синхронизации.</div>`}
      <button class="btn w" id="co-edit">Изменить</button>`}</div>`;
    if ($("#co-edit")) $("#co-edit").onclick = () => { box.dataset.edit = "const"; renderSoul(); };
    if ($("#co-cancel")) $("#co-cancel").onclick = () => { box.dataset.edit = ""; renderSoul(); };
    if ($("#co-save")) $("#co-save").onclick = () => { const mm = mind(); mm.constitution = $("#co-text").value; saveMind(mm); syncSoon(); box.dataset.edit = ""; renderSoul(); toast("Конституция сохранена"); };
  }
  if ($("#so-sync")) $("#so-sync").onclick = () => openSettings("more");
}

/* ---------- лист настроек: вкладки «Мозг», «Слух и голос», «Ещё»; разметка собирается строкой, обработчики вешаются
   после вставки; мастера подключения мозга (плитки data-w) — в wizard() ---------- */
const UPD_URL = "https://dewiar.pro/dwrapp/latest.json";
const CLOUD = {
  openrouter: { name: "OpenRouter", url: "https://openrouter.ai/api/v1", model: "google/gemini-2.5-flash", key: "https://openrouter.ai/settings/keys" },
  openai: { name: "OpenAI", url: "https://api.openai.com/v1", model: "gpt-4.1-mini", key: "https://platform.openai.com/api-keys" },
  deepseek: { name: "DeepSeek", url: "https://api.deepseek.com/v1", model: "deepseek-chat", key: "https://platform.deepseek.com/api_keys" },
  anthropic: { name: "Claude (Anthropic)", url: "https://api.anthropic.com/v1", model: "claude-sonnet-5-5", key: "https://platform.claude.com/settings/keys" },
  // признанные поставщики напрямую (20.10): официальные OpenAI-совместимые адреса; модель — первая из rec, что есть у сервиса
  gemini: { name: "Google Gemini", url: "https://generativelanguage.googleapis.com/v1beta/openai", model: "gemini-flash-latest", key: "https://aistudio.google.com/apikey",
            rec: ["gemini-flash-latest", "gemini-pro-latest", "gemini-flash-lite-latest"] },   // «-latest» — у Google всегда новейшая
  kimi: { name: "Kimi (Moonshot)", url: "https://api.moonshot.ai/v1", model: "kimi-latest", key: "https://platform.moonshot.ai/console/api-keys",
          rec: ["kimi-latest", "kimi-k2-turbo-preview", "kimi-k2-0905-preview", "moonshot-v1-32k"] },
  glm: { name: "GLM (Z.ai)", url: "https://api.z.ai/api/paas/v4", model: "glm-4.6", key: "https://z.ai/manage-apikey/apikey-list", rec: ["glm-4.6", "glm-4.5-air", "glm-4.5"] },
  qwen: { name: "Qwen (Alibaba)", url: "https://dashscope-intl.aliyuncs.com/compatible-mode/v1", model: "qwen-plus", key: "https://modelstudio.console.alibabacloud.com/",
          rec: ["qwen-plus", "qwen-flash", "qwen-max", "qwen3-max"] },
  mistral: { name: "Mistral", url: "https://api.mistral.ai/v1", model: "mistral-medium-latest", key: "https://console.mistral.ai/api-keys",
             rec: ["mistral-medium-latest", "mistral-small-latest", "mistral-large-latest"] },
  // GitHub #8 (24.10): OpenCode Go — свой OpenAI-совместимый адрес; модель — первая из списка сервера
  opencode: { name: "OpenCode Go", url: "https://opencode.ai/zen/go/v1", model: "", key: "https://opencode.ai" },
  xai: { name: "Grok (xAI)", url: "https://api.x.ai/v1", model: "grok-4-fast-non-reasoning", key: "https://console.x.ai",
         rec: ["grok-4-fast-non-reasoning", "grok-4-fast-reasoning", "grok-3-mini", "grok-4"] },
  // российские агрегаторы — оплата картой РФ (№141). Только давно работающие (AITunnel и Polza.ai убраны 20.10)
  proxyapi: { name: "ProxyAPI", url: "https://api.proxyapi.ru/openai/v1", model: "gpt-4.1-mini", key: "https://console.proxyapi.ru/keys" },
  vsegpt: { name: "VseGPT", url: "https://api.vsegpt.ru/v1", model: "openai/gpt-4.1-mini", key: "https://vsegpt.ru" },
  custom: { name: "Другой — по адресу", url: "", model: "", key: "" },      // любой OpenAI-совместимый: LiteLLM, Kimi, агрегаторы (комментарии 19.10)
};
/* Модели сервиса по ключу -> [] (не отдал — не беда). Gemini пишет «models/…» — без приставки; не для разговора — прочь. */
async function svcModels(url, key) {
  try {
    const r = await http("GET", url.replace(/\/+$/, "") + "/models", { headers: key ? { Authorization: "Bearer " + key } : {}, timeout: 15000 });
    if (r.status !== 200) return [];
    return ((JSON.parse(r.body) || {}).data || []).map(m => String(m.id || "").replace(/^models\//, ""))
      .filter(m => m && !/(^|[-_/])(tts|whisper|transcribe|dall-e|imagen|veo|moderation|aqa|embed\w*|rerank\w*)([-_.]|$)|image-|audio/i.test(m));
  } catch (e) { return []; }
}
/* Вписанный адрес сервиса: без хвоста /chat/completions, с https:// */
function svcUrl(raw) {
  let u = String(raw || "").trim().replace(/\/+$/, "").replace(/\/chat\/completions$/, "").replace(/\/models$/, "");
  return !u ? "" : /^https?:\/\//i.test(u) ? u : "https://" + u;
}
const ICON = {
  dewiar: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="3"/><path d="M12 3.5v5M12 15.5v5M3.5 12h5M15.5 12h5"/></svg>',
  server: '<svg viewBox="0 0 24 24"><rect x="4" y="3" width="16" height="7" rx="2"/><rect x="4" y="14" width="16" height="7" rx="2"/><path d="M8 6.5h.01M8 17.5h.01"/></svg>',
  cloud: '<svg viewBox="0 0 24 24"><path d="M7 18a4.5 4.5 0 0 1-.6-8.96A6 6 0 0 1 18 8.5a4.5 4.5 0 0 1-.5 9.5z"/></svg>',
  pc: '<svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8M12 16v4"/></svg>',
  key: '<svg viewBox="0 0 24 24"><circle cx="8" cy="15" r="4"/><path d="M10.8 12.2 20 3M16 7l3 3M14 9l2 2"/></svg>',
  user: '<svg viewBox="0 0 24 24"><circle cx="12" cy="8.5" r="4"/><path d="M4.5 20.5a7.5 7.5 0 0 1 15 0"/></svg>',
};
let setTab = "brain";
function openSettings(tab) { fsMark("settings"); if (kidsLocked()) { kidsPin(() => openSettings(tab)); return; } if (!$("#sh-set").classList.contains("on")) bugSnapTake(); setTab = tab || setTab; renderSettings(); openSheet("#sh-set"); }
$("#b-set").onclick = () => openSettings("menu");
if ($("#bal")) $("#bal").onclick = (e) => { e.stopPropagation(); openTopup(); };                // значок баланса у имени персонажа (0.82.1) — сразу «Пополнить»
/* «Всё» (0.60; владелец 28.10: «сверху иконок многовато»): Досуг, Душа, Работа, Идеи, обучение — плитками в одном листе,
   как «Главная» на компьютере; на панели остались звук, «Близкие», день, «Всё» и настройки. */
const APPS_IC = {
  pc: '<rect x="3" y="4.5" width="18" height="12" rx="2.2"/><path d="M8.5 20h7M12 16.5V20"/>',
  clients: '<circle cx="9" cy="8.5" r="3.5"/><path d="M2.8 19.5a6.2 6.2 0 0 1 12.4 0"/><path d="M16 5.2a3.5 3.5 0 0 1 0 6.6M17.6 14a6.2 6.2 0 0 1 3.6 5.5"/>',
  blog: '<path d="M6 3h9l4 4v14H6z"/><path d="M14 3v5h5M9 12h7M9 16h5"/>',
  play: '<path d="M7.5 7.5h9a4.5 4.5 0 0 1 4.3 5.8l-1.1 3.7a2.3 2.3 0 0 1-3.9.9L14 15.5h-4l-1.8 2.4a2.3 2.3 0 0 1-3.9-.9l-1.1-3.7a4.5 4.5 0 0 1 4.3-5.8z"/><path d="M8 10.5v3M6.5 12h3"/>',
  soul: '<path d="M10.5 2.8l1.9 5.5 5.6 1.9-5.6 1.9-1.9 5.6-1.9-5.6L3 10.2l5.6-1.9z"/><path d="M18.5 14.5l.9 2.4 2.4.9-2.4.9-.9 2.4-.9-2.4-2.4-.9 2.4-.9z"/>',
  work: '<rect x="3" y="7.5" width="18" height="12.5" rx="2.5"/><path d="M8.5 7.5V6a2 2 0 0 1 2-2h3a2 2 0 0 1 2 2v1.5M3 12.5h18"/>',
  ideas: '<path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-3.6 10.8c.7.5 1.1 1.3 1.1 2.2V16h5v-.1c0-.9.4-1.7 1.1-2.2A6 6 0 0 0 12 3z"/>',
  tricks: '<path d="M12 3.5l2.4 5.2 5.6.6-4.2 3.8 1.2 5.5L12 15.8l-5 2.8 1.2-5.5L4 9.3l5.6-.6z"/>',
  course: '<path d="M2.5 9 12 4.5 21.5 9 12 13.5z"/><path d="M6.5 11v4.5c0 1.4 2.5 3 5.5 3s5.5-1.6 5.5-3V11"/>',
  qa: '<circle cx="12" cy="12" r="8.5"/><path d="M9.6 9.5a2.5 2.5 0 0 1 4.8.9c0 1.7-2.4 2.2-2.4 3.6M12 16.8v.01"/>',
  kids: '<circle cx="12" cy="13" r="7.5"/><circle cx="9.3" cy="12" r="1.6"/><circle cx="14.7" cy="12" r="1.6"/><path d="M7 6.5 5.5 3.5M17 6.5l1.5-3M10.8 15.5h2.4"/>',
  news: '<path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M5.6 18.4l2.1-2.1M16.3 7.7l2.1-2.1"/>',
  month: '<rect x="3.5" y="5" width="17" height="15.5" rx="2.5"/><path d="M3.5 10h17M8 3v4M16 3v4"/><path d="M7.5 14h2M11 14h2M14.5 14h2M7.5 17h2M11 17h2"/>',
  senior: '<path d="M12 20.5s-7.5-4.6-7.5-10.2A4.3 4.3 0 0 1 12 7.6a4.3 4.3 0 0 1 7.5 2.7c0 5.6-7.5 10.2-7.5 10.2z"/><path d="M8.5 12.5h2l1-2 1.5 4 1-2h1.5"/>',
  radio: '<rect x="3" y="9" width="18" height="11" rx="3"/><path d="M7 9l9-5"/><circle cx="15.5" cy="14.5" r="2.5"/><path d="M6.5 13h3M6.5 16h3"/>',
  lessons: '<rect x="3" y="5" width="18" height="14" rx="3"/><path d="M10 9.2v5.6l4.8-2.8z"/>',
  safe: '<rect x="4" y="4" width="16" height="16" rx="3.5"/><circle cx="12" cy="12" r="3.6"/><path d="M12 8.4V7M12 17v-1.4M15.6 12H17M7 12h1.4M4 8h-1.5M4 16h-1.5"/>' };
function appsHtml() {
  const t = [];
  if (feat("games")) t.push(["play", "Досуг", "милые игры"]);
  if (kidsOn()) return `<div class="apps">${t.concat([["tricks", "Что я умею", "фразы-примеры"], ["kids", "Детский режим", "для взрослых"]]).map(([k, n, sub]) => `<button class="app a-${k}" data-app="${k}"><span class="ai"><svg viewBox="0 0 24 24">${APPS_IC[k]}</svg></span><b>${n}</b><small>${sub}</small></button>`).join("")}</div>`;
  if (typeof srOn === "function" && srOn()) {        // «Для старших»: только нужное, крупно
    t.push(["month", "Мой месяц", "дела и траты"], ["radio", "Радио", "станции и жанры"], ["senior", "Для старших", "лекарства и присмотр"], ["tricks", "Что я умею", "фразы-примеры"], ["lessons", "Видеоуроки", "мультфильмы по минуте"], ["qa", "Вопрос — ответ", "как сделать…"], ["news", "Что нового", "в этой версии"]);
    return `<div class="apps">${t.map(([k, n, sub]) => `<button class="app a-${k}" data-app="${k}"><span class="ai"><svg viewBox="0 0 24 24">${APPS_IC[k]}</svg></span><b>${n}</b><small>${sub}</small></button>`).join("")}</div>`;
  }
  if (!kidsOn()) t.push(["clients", window.t("apps.clients"), window.t("apps.clients_d")]);   // 0.9.32: отчёты 657, 658 — бизнес-инструменты и на телефоне
  if (!kidsOn() && typeof blogHas === "function" && blogHas()) t.push(["blog", window.t("phone.blog.title"), blogDraftsN() ? window.t("phone.blog.app_n", { n: blogDraftsN() }) : window.t("phone.blog.app_d")]);   // 0.93: статьи своего сайта
  if (!kidsOn()) t.push(["work", "Работа", wkJobs().length ? "поручения" : "для сотрудников"]);   // 28.10, владелец: «при чём здесь „по коду“»
  if (!kidsOn()) t.push(["ideas", "Идеи Лиры", "голосовать"]);
  if (!kidsOn()) t.push(["month", "Мой месяц", "дела и траты"]);
  if (!kidsOn()) t.push(["safe", "Сейф", "пароли с компьютера"]);       // 03.11: пароли — подглядеть с телефона (safe.js)
  t.push(["radio", "Радио", "станции и жанры"]);
  t.push(["course", "Курсы", "урок в день"], ["lessons", "Видеоуроки", "мультфильмы по минуте"], ["qa", "Вопрос — ответ", "как сделать…"]);
  t.push(["pc", window.t("apps.pc"), window.t("apps.pc_d")]);           // 0.9.32: что есть только на компьютере и как поручить ему отсюда (отчёт 658)
  // вычитание 28.11 (как «Ещё» в студии): «на раз» — в конце: душа, что я умею, режимы, что нового
  t.push(["soul", "Душа", "дневник и характер"], ["tricks", "Что я умею", "фразы-примеры"]);
  t.push(["senior", "Для старших", "для мамы и папы"], ["kids", "Детский режим", kidsOn() ? "включён" : "для ребёнка"], ["news", "Что нового", "в этой версии"]);
  return `<div class="apps">${t.map(([k, n, sub]) => `<button class="app a-${k}${k === "lessons" && lsnNew().length ? " new" : ""}" data-app="${k}"><span class="ai"><svg viewBox="0 0 24 24">${APPS_IC[k]}</svg></span><b>${n}</b><small>${sub}</small></button>`).join("")}</div>`;
}
/* Открыть раздел «Всё» по ключу — плитка листа «Всё» и меню слева на планшете (tablet.js). */
function appOpen(k) {
  ({ play: () => playOpen(""), soul: () => { renderSoul(); openSheet("#sh-soul"); syncSoon(); }, work: () => openWork("", !wkJobs().length),
      ideas: () => openIdeas(), safe: () => openSafe(), radio: () => openRadio(), month: () => openMonth("now"), senior: () => openSenior(), tricks: () => openTricks(), course: () => openLearn("course"), qa: () => openLearn("qa"), kids: () => openKids(), lessons: () => openLessons(),
      news: () => newsShow(newsList("", JSON.parse(D.info() || "{}").version || "9", true), true),
      clients: () => (typeof openClients === "function" ? openClients() : null), blog: () => (typeof openBlog === "function" ? openBlog() : null), pc: () => (typeof openPcInfo === "function" ? openPcInfo() : null) }[k] || (() => { }))();
}
function openApps() {
  $("#apps-body").innerHTML = appsHtml(); openSheet("#sh-apps");
  $$("#apps-body [data-app]").forEach(b => b.onclick = () => { const k = b.dataset.app; closeSheets(); setTimeout(() => appOpen(k), 60); });
}
$("#b-apps").onclick = () => openApps();
/* «Видеоуроки» (0.69; владелец 29.10: «показывать их в приложении»): мультфильмы ИИ Академии — с сайта (?p=/academy:
   только уроки, чьё видео уже загружено); плеер — прямо в листе, YouTube — в браузере. */
/* Чтобы про уроки узнали без надоеданий (29.10, владелец): раз в 12 часов — какие уроки есть; новые (ещё не открытые) —
   тихая точка на «Всё» и метка «новое» на плитке; открыли «Видеоуроки» — все увиденные отмечены (S.lsnSeen). */
const lsnNew = () => (S.lsnKnown || []).filter(id => !(S.lsnSeen || []).includes(id));
function lsnDot() { const b = $("#b-apps"); if (b) b.classList.toggle("has", !!lsnNew().length && !kidsOn()); }
async function lsnCheck() {
  if (Date.now() - (+S.lsnAt || 0) < 12 * 3600e3) return lsnDot();
  try { const r = await http("GET", annBase() + "?p=/academy" + (appEn() ? "&lang=en" : ""), { timeout: 15000 }); const it = JSON.parse(r.body || "{}").items;
    if (Array.isArray(it)) { S.lsnKnown = it.map(x => x.id); S.lsnAt = Date.now(); saveS(); } } catch (e) { }
  lsnDot();
}
setTimeout(() => lsnCheck(), 9000);
async function openLessons() {
  const box = $("#lessons-body"); box.innerHTML = `<p class="lsn-empty">Загружаю уроки…</p>`; openSheet("#sh-lessons");
  let items = [];
  try { const r = await http("GET", annBase() + "?p=/academy" + (appEn() ? "&lang=en" : ""), { timeout: 15000 }); items = (JSON.parse(r.body || "{}").items || []); }
  catch (e) { box.innerHTML = `<p class="lsn-empty">Нет связи с dewiar.pro — попробуйте позже.</p>`; return; }
  S.lsnKnown = items.map(x => x.id); S.lsnSeen = [...new Set((S.lsnSeen || []).concat(S.lsnKnown))]; S.lsnAt = Date.now(); saveS(); lsnDot();
  const m = (x) => x ? `${Math.floor(x / 60)}:${String(x % 60).padStart(2, "0")}` : "";
  box.innerHTML = `<div class="lsn-player" id="lsn-player" hidden><video id="lsn-v" controls playsinline preload="metadata"></video><b id="lsn-t"></b></div>`
    + (items.length ? items.map(l => `<button class="lsn" data-id="${esc(l.id)}"><span class="lsn-pic"${l.poster ? ` style="background-image:url('${esc(l.poster)}')"` : ""}><i aria-hidden="true">▶</i>${l.sec ? `<em>${m(l.sec)}</em>` : ""}</span>`
      + `<span class="lsn-x"><small>Урок ${l.n}</small><b>${esc(l.title)}</b><span>${esc(l.about)}</span></span></button>`).join("")
      : `<p class="lsn-empty">Уроки скоро появятся здесь.</p>`);
  $$("#lessons-body .lsn").forEach(b => b.onclick = () => {
    const l = items.find(x => x.id === b.dataset.id); if (!l) return;
    if (!l.video && l.youtube) return D.openUrl(l.youtube);
    const v = $("#lsn-v"); v.poster = l.poster || ""; v.src = l.video; $("#lsn-t").textContent = `Урок ${l.n} · ${l.title}`;
    // плеер — над списком: долистали до урока внизу и нажали — звук был, а видео — за краем экрана (владелец 20.11);
    // прокручиваем к плееру тот лист, что прокручивается на самом деле (scrollTop у #lessons-body ничего не делал)
    const pl = $("#lsn-player"); pl.hidden = false; pl.scrollIntoView({ block: "start", behavior: "smooth" }); v.play().catch(() => { });
  });
}

$("#r-pp").onclick = () => { D.vibrate(12); if (radio.state().state === "paused") radio.resume(); else radio.pause(); };
/* идея №170: ⏮ / ⏭ у радио над Лирой — предыдущая (что играла до этой) и следующая станция */
const rStep = (fn) => { D.vibrate(12); fn().then(r => { if (r && !r.ok && !r.superseded && r.text) toast(r.text.replace(/^Ошибка: /, ""), 3500); }); };
$("#r-prev").onclick = () => rStep(radio.prev);
$("#r-next").onclick = () => rStep(radio.next);
$("#r-x").onclick = () => { D.vibrate(12); radio.stop(); };

/* Что умеет облако Dewiar сейчас (распознавание, озвучка — /models): при запуске и при открытии настроек, чтобы
   включённая администратором озвучка заработала без повторного входа. */
async function cloudCaps() {
  const bases = [];
  if (loggedIn() && S.accCloud) bases.push([S.accCloud, S.accCloud.base, S.account.token]);
  if (S.llm.cloud) bases.push([S.llm, cloudBase(), S.llm.api_key]);
  for (const [o, base, key] of bases) {
    try { const md = await cloudGet(base, key, "/models"); o.stt = !!md.stt; o.tts = !!md.tts; } catch (e) { }
  }
  if (bases.length) saveS();
}
/* Вошли аккаунтом, а мозг не выбран (облако не ответило при входе, сайт не назвал облако) — подключить модели Dewiar
   по аккаунту. Тихо: при запуске, при открытии «Мозга» и перед вопросом. -> true, если мозг есть. */
let brainBusy = null;
/* Пробный разговор (0.38.99): веб-версия без входа и без ключа сразу говорит через ?p=/trial сайта — без действий, с
   пределом в час (cloud.php trial_handler). Вошли аккаунтом или подключили мозг — проба уходит сама (trialOff, cloudConnect). */
function trialOn() {
  // 0.69: и на телефоне — пока бесплатный мозг подключается сам (автоподключение), первый ответ — пробным разговором
  if (S.llm.trial) return true;
  if (loggedIn() || S.llm.base_url || (S.join && !S.join.auto) || !D.web && !autoOk()) return false;
  S.llm = Object.assign({}, S.llm, { kind: "openai", base_url: CLOUD_URL + "?p=/trial", api_key: "", model: "trial", name: "Пробный разговор", trial: true });
  saveS(); return true;
}
function trialOff() {
  if (!S.llm.trial) return;
  const { base_url, api_key, model, name, trial, kind, ...rest } = S.llm; S.llm = rest; saveS();
}
function ensureBrain() {
  if (S.llm.trial && loggedIn()) trialOff();       // вошли аккаунтом — проба больше не нужна, думают модели Dewiar по аккаунту
  if (S.llm.trial && !loggedIn()) autoJoin("вопрос в пробном разговоре").catch(() => {});   // полный мозг — подключится сам
  if (S.llm.base_url) return Promise.resolve(true);
  if (!loggedIn()) {        // 0.69: мозга нет — подключаемся сами, а не ждём анкеты; не успели за 6 с — этот ответ пробным разговором
    if (!autoOk()) return Promise.resolve(false);
    return Promise.race([autoJoin("вопрос без мозга").catch(() => false), new Promise(r => setTimeout(r, 6000))])
      .then(() => !!S.llm.base_url || trialOn());
  }
  if (!brainBusy) brainBusy = cloudConnect(S.account.token, (S.accCloud && S.accCloud.base) || siteUrl((S.account.services || {}).cloud || "dwrapp/cloud.php"), { account: true })
    .then(() => { plog("info", "мозг: модели Dewiar по аккаунту"); return true; }).catch(e => { plog("warn", "мозг по аккаунту: " + e.message); return false; })
    .finally(() => { brainBusy = null; });
  return brainBusy;
}
function openBrain(w) { openSettings("brain"); if (w) setTimeout(() => { const t = $(`.tile[data-w="${w}"]`); if (t) t.click(); }, 250); }
function startLogin() { openSettings("brain"); setTimeout(() => { const t = $('.tile[data-w="account"]'); if (t) t.click(); }, 250); }
function brainName() { if (S.llm.cloud) return "Dewiar Облако"; return S.llm.base_url ? `${S.llm.name || S.llm.base_url.replace(/^https?:\/\//, "")}${S.llm.model ? " · " + S.llm.model : ""}` : "не подключён"; }
/* Настройки (0.60; владелец 28.10: «сверху иконок многовато, а внутренние разделы перегружены — захожу в „Ещё“ и скроллю,
   скроллю»): меню по группам — строка с иконкой и тем, что сейчас выбрано; нажали — одна страница со стрелкой «назад».
   setTab — страница: menu | brain | voice | devices | look | sound | widget | lite | features | smart | telegram | assist |
   hands | bug | perms | privacy | about. Старые имена («more», «about», «alarms») ведут в меню или на свою страницу. */
const MORE_SECS = ["look", "sound", "widget", "lite", "features", "smart", "telegram", "assist", "hands", "bug", "perms", "privacy", "about"];
const SET_PAGES = ["menu", "brain", "voice", "devices", ...MORE_SECS];
const SET_ALIAS = { more: "menu", alarms: "sound", report: "bug", home: "smart", ha: "smart", tg: "telegram", sync: "devices" };
const SET_IC = {
  brain: '<path d="M9 4.5a3 3 0 0 0-3 3v.3A3 3 0 0 0 4 10.5a3 3 0 0 0 1 2.2A3 3 0 0 0 6.5 18 3 3 0 0 0 12 19V5.6A3 3 0 0 0 9 4.5zM15 4.5a3 3 0 0 1 3 3v.3a3 3 0 0 1 2 2.7 3 3 0 0 1-1 2.2A3 3 0 0 1 17.5 18 3 3 0 0 1 12 19"/>',
  voice: '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/>',
  devices: '<rect x="2.5" y="5" width="13" height="10" rx="1.8"/><path d="M6 19h6"/><rect x="15.5" y="9" width="6" height="11" rx="1.6"/>',
  look: '<circle cx="12" cy="12" r="8.5"/><path d="M12 3.5a8.5 8.5 0 0 0 0 17c1.4 0 1.8-1 1.3-2-.6-1.3.3-2.5 1.7-2.5h1.5a4 4 0 0 0 4-4"/><circle cx="8" cy="10" r="1"/><circle cx="12" cy="7.5" r="1"/>',
  sound: '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 8 3 8H3s3-1 3-8"/><path d="M10.3 20a1.9 1.9 0 0 0 3.4 0"/>',
  widget: '<rect x="4" y="4" width="16" height="16" rx="4.5"/><circle cx="12" cy="12" r="3.2"/>',
  lite: '<path d="M13 2.5 5 13.5h6l-1 8 8-11h-6z"/>',
  features: '<rect x="3.5" y="3.5" width="7" height="7" rx="1.8"/><rect x="13.5" y="3.5" width="7" height="7" rx="1.8"/><rect x="3.5" y="13.5" width="7" height="7" rx="1.8"/><path d="M17 13.5v7M13.5 17h7"/>',
  smart: '<path d="M3.5 11 12 4l8.5 7"/><path d="M5.5 9.5V20h13V9.5"/><path d="M10 20v-5h4v5"/>',
  telegram: '<path d="M21 4.5 2.8 11.4l5.6 2 2.2 6.6 3.3-4.1 4.9 3.6z"/><path d="m8.4 13.4 8.9-6.3-6.7 8.3"/>',
  assist: '<circle cx="12" cy="12" r="8.5"/><path d="M8.5 12.5 11 15l4.5-5"/>',
  hands: '<path d="M8 13V5.5a1.5 1.5 0 0 1 3 0V12M11 11.5V4a1.5 1.5 0 0 1 3 0v8M14 12V6a1.5 1.5 0 0 1 3 0v8.5a6 6 0 0 1-6 6h-.5a6 6 0 0 1-4.9-2.6L3.8 14a1.5 1.5 0 0 1 2.4-1.8L8 14.5"/>',
  bug: '<rect x="6.5" y="7" width="11" height="14.5" rx="5.5"/><path d="M8.8 7.6a3.2 3.2 0 0 1 6.4 0M12 11.5v10M6.5 12.5H2.5M21.5 12.5h-4M6.8 17.5 3 19.8M17.2 17.5l3.8 2.3"/>',
  ideas: '<path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-3.6 10.8c.7.5 1.1 1.3 1.1 2.2V16h5v-.1c0-.9.4-1.7 1.1-2.2A6 6 0 0 0 12 3z"/>',
  perms: '<rect x="5" y="10.5" width="14" height="10" rx="2.5"/><path d="M8.5 10.5V7.5a3.5 3.5 0 0 1 7 0v3"/>',
  privacy: '<path d="M12 3.2 5 6v5.6c0 4.2 2.9 7.7 7 9.2 4.1-1.5 7-5 7-9.2V6z"/>',
  about: '<circle cx="12" cy="12" r="8.5"/><path d="M12 11v5.5M12 7.6v.01"/>',
};
const SET_NAMES = { menu: "Настройки", brain: "Мозг", voice: "Слух и голос", devices: "Устройства", look: "Оформление", sound: "Звук напоминаний",
  widget: "Значок «Записать»", lite: "Лёгкий режим", features: "Возможности", smart: "Умный дом", telegram: "Telegram", assist: "Кнопка помощника",
  hands: "Управлять приложениями", bug: "Сообщить о проблеме", perms: "Разрешения", privacy: "Ваши данные", about: "О приложении" };
const setTitle = (k) => k === "privacy" && window.DEWIAR_PRIVACY ? DEWIAR_PRIVACY.title : SET_NAMES[k] || "Настройки";
function setMenuHtml(info) {
  const on = !!S.llm.base_url && !S.llm.trial, c = syncChan(), st = syncStatus;
  const skin = (PHONE_SKINS.find(x => x.id === lookSkin()) || {}).name || "";
  let snd = {}; try { snd = JSON.parse(D.alarmSound ? D.alarmSound() : "{}"); } catch (e) { }
  const sndName = snd.id === "custom" ? (snd.custom || "свой звук") : ((ALARM_SOUNDS.find(x => x[0] === (snd.id || "signature")) || [])[1] || "");
  const permsMissing = [MIC, NOTIF].filter(p => !D.has(p)).length + (D.exactAlarms && !D.exactAlarms() ? 1 : 0);
  const remBad = (() => { const rh = remHealth(); return rh ? remIssues(rh).filter(x => x[0] !== "battery").length + remLates(rh).n > 0 : false; })();
  let wg = {}; try { wg = JSON.parse(D.widgetState ? D.widgetState() : "{}") || {}; } catch (e) { }
  const sync = !c ? "не подключены" : !S.sync.on ? "синхронизация выключена" : st.ok === false ? "не синхронизировалось" : st.at ? "синхронизировано в " + pad(new Date(st.at).getHours()) + ":" + pad(new Date(st.at).getMinutes()) : c.home ? "по Wi-Fi" : "через dewiar.pro";
  const fOn = ["games", "close"].filter(k => feat(k)).length;
  const rows = [
    ["Главное", [["brain", on ? "думает: " + brainName() : S.llm.trial ? "пробный разговор" : "не подключён", !on && !S.llm.trial],
      ["voice", (S.tts.engine === "cloud" ? "голос Dewiar" : S.tts.engine === "eleven" ? "ElevenLabs" : S.tts.engine === "server" ? "свой сервер голоса" : "голос телефона") + " · скорость " + (+S.tts.rate || 1).toFixed(2)],
      ["devices", sync, st.ok === false]]],
    ["Вид и звук", [["look", skin], ...(D.web ? [] : [["sound", remBad ? "напоминания могут опаздывать" : sndName, remBad], ["widget", wg.on === undefined ? "" : wg.on ? (wg.placed ? "на рабочем столе" : "включён") : "выключен"]]),
      ["lite", liteOn() ? "включён" : S.lite === "off" ? "выключен" : "сам, по телефону"]]],
    ["Подключения", [["features", fOn ? "включено " + fOn + " из 2" : "всё выключено"], ...(D.web ? [] : [["smart", S.home.token ? "Яндекс подключён" : haOn() ? "Home Assistant" : "не подключён"]]),
      ["telegram", (S.tg || {}).linked ? "подключён" : "не подключён"], ...(D.web ? [] : [["assist", "долгое нажатие кнопки питания"], ["hands", ""]])]],
    ["Помощь и связь", [["bug", (S.complaints || []).length ? "ваших жалоб: " + S.complaints.length : "снимок экрана и пара слов"], ...(kidsOn() ? [] : [["ideas", "предложить и проголосовать"]]),
      ...(D.web ? [] : [["perms", permsMissing ? "нужно разрешить: " + permsMissing : "всё разрешено", permsMissing > 0]]), ["privacy", "что где хранится"],
      ["about", "Dewiar " + (info.version || "") + (info.crash ? " · была ошибка" : ""), !!info.crash]]]];
  return rows.map(([g, list]) => `<h3>${g}</h3><div class="card setmenu">${list.map(([k, sub, warn]) =>
    `<button class="setrow" ${k === "ideas" ? 'id="ideas-open"' : `data-st="${k}"`}><span class="si s-${k}"><svg viewBox="0 0 24 24">${SET_IC[k] || ""}</svg></span>`
    + `<span class="st"><b>${esc(k === "ideas" ? "Идеи Лиры" : setTitle(k))}</b>${sub ? `<small class="${warn ? "warn" : ""}">${esc(sub)}</small>` : ""}</span><svg class="chev" viewBox="0 0 24 24"><path d="m9.5 6 6 6-6 6"/></svg></button>`).join("")}</div>`).join("");
}
function renderSettings() {
  setTab = SET_ALIAS[setTab] || setTab;
  if (!SET_PAGES.includes(setTab)) setTab = "menu";   // «more», «alarms»… — меню (0.60: вместо длинной ленты «Ещё»)
  const info = JSON.parse(D.info() || "{}");
  const h = [];
  if (setTab === "menu") h.push(setMenuHtml(info));
  else h.push(`<div class="sethd"><button class="setback" data-st="menu" aria-label="Назад, ко всем настройкам"><svg viewBox="0 0 24 24"><path d="m14.5 6-6 6 6 6"/></svg></button><h2>${esc(setTitle(setTab))}</h2></div>`);
  $("#sh-set").classList.toggle("sub", setTab !== "menu");
  if (setTab === "brain") {
    if (loggedIn()) h.push(`<div class="card acc" id="acc-card"><div class="row2"><div class="acc-ava">${esc((S.account.login || "?").slice(0, 1).toUpperCase())}</div><div style="flex:1;min-width:0"><b>${esc(S.account.login)}</b>
      <small class="hint" style="margin:2px 0 0;display:block">Аккаунт ${esc(siteHost())}${S.account.problem ? " · " + esc(S.account.problem) : ""}</small></div><button class="btn" id="acc-out">Выйти</button></div>
      ${S.accCloud && !S.llm.cloud ? `<button class="btn p w" id="acc-use" style="margin-top:10px">Думать моделями Dewiar</button><p class="hint" style="margin:8px 0 0">Сейчас думает ваша модель. Модели Dewiar по аккаунту — с зарядом в талерах.</p>` : ""}
      <p class="hint" style="margin:10px 0 0">Знания сайта подключаются персонажу: нажмите имя персонажа вверху → «Знания». Или просто спросите: «что в моих документах про отпуск?»</p></div>`);
    else if (S.account.problem) h.push(`<div class="card"><div class="res bad" style="margin:0">${esc(S.account.problem)}</div></div>`);
    const on = !!S.llm.base_url && !S.llm.trial;   // пробный разговор на сайте — ещё не «подключено»: выбор мозга открыт
    if (S.llm.trial) h.push(`<div class="card"><small class="hint" style="margin:0">Сейчас</small><div style="font-weight:600">Пробный разговор</div>
      <small class="hint" style="margin:2px 0 0;display:block">Можно говорить без входа — несколько ответов в час и без дел (будильники, заметки, поиск). Подключите мозг Dewiar (на старте подарок) или войдите — и я смогу всё.</small></div>`);
    else h.push(`<div class="card brain ${on ? "ok" : ""}"><div class="row2"><div style="flex:1;min-width:0"><small class="hint" style="margin:0">${on ? "Подключено · думает" : "Мозг"}</small>
      <div style="font-weight:600">${esc(on ? brainName() : loggedIn() ? "подключаю модели Dewiar…" : "не подключён")}</div>
      ${on && S.llm.title ? `<small class="hint" style="margin:2px 0 0;display:block">${esc(S.llm.title)}${S.llm.cloud ? " · " + esc(cloudWho()) : ""}</small>` : ""}</div>
      ${on || loggedIn() ? `<button class="btn" id="br-test">Проверить</button>` : ""}</div><div class="res" id="br-res"></div></div>`);
    if (S.autoJoined && S.llm.cloud && !S.llm.account) { h.push(contactCardHtml(false)); setTimeout(contactWire, 0); }   // 0.69: имя и контакт — по желанию
    // №388/389 (28.10): «нет выбора мозга — только Dewiar, а на компьютере выбран ключ другого сервера» — взять мозги с
    // компьютера прямо здесь (раньше — только «Устройства» → «Мозги с другого устройства»); пришедшие — ниже, «Включить»
    if (syncCred() && !S.llm.trial) h.push(`<div class="card" id="br-pc"><div class="row2"><div style="flex:1;min-width:0"><b>Как на компьютере</b>
      <small class="hint" style="margin:2px 0 0;display:block">На компьютере своя модель или ключ сервиса? Возьмите их сюда — придут зашифрованными, включить можно ниже.</small></div>
      <button class="btn" id="br-pull">Взять</button></div><div class="res ${devBrainsGot.length ? "ok" : ""}" id="br-pull-res">${esc(devBrainsGot.map(x => `С «${x.from}»: ${x.names.join(", ")}`).join(" · "))}</div></div>`);
    const back = llmBack();
    // №254 (25.10): «как удалять однажды добавленные, но неработающие мозги? В списке только „Вернуть“» — рядом корзина:
    // первое нажатие спрашивает («Убрать»), второе убирает из списка. Ключ слуха (restore: "key") не убираем — им слышит телефон.
    if (back.length) h.push(`<div class="card" id="br-back"><small class="hint" style="margin:0">${back.some(l => l.got) ? "Другие мозги — включить одной кнопкой или убрать из списка" : "Прежние мозги — вернуть одной кнопкой или убрать из списка"}</small>${back.map((l, i) =>
      `<div class="row2 brb" style="margin-top:8px"><div style="flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(brainNameOf(l))}</div><button class="btn" data-back="${i}">${l.got ? "Включить" : "Вернуть"}</button>${l.restore ? "" : `<button class="btn brdel" data-forget="${i}" title="Убрать из списка" aria-label="Убрать «${esc(brainNameOf(l))}» из списка"><svg viewBox="0 0 24 24"><path d="M4.5 7h15M9.5 7V5a1 1 0 0 1 1-1h3a1 1 0 0 1 1 1v2M6.5 7l1 12.5a1.5 1.5 0 0 0 1.5 1.4h6a1.5 1.5 0 0 0 1.5-1.4L17.5 7"/></svg><span>Убрать</span></button>`}</div>`).join("")}<div class="res" id="br-back-res"></div></div>`);
    // экономный режим (0.63): свой ключ сервиса — простое отвечает недорогая модель того же сервиса (econModel)
    if (on && !S.llm.cloud) h.push(`<div class="card" id="br-econ"><div class="sw" style="margin:0"><div>Экономный режим<small>${S.llm.economy
      ? `Простые вопросы — ${esc(S.llm.economy)}, поручения и сложное — ${esc(S.llm.model || "основной модели")}.`
      : "Простые вопросы — недорогой модели того же сервиса, поручения и сложное — основной. Ответы те же, дешевле."}</small></div>
      <label class="tg"><input type="checkbox" id="br-econ-on" ${S.llm.economy ? "checked" : ""}><i></i></label></div><div class="res" id="br-econ-res"></div></div>`);
    if (on) h.push(`<div class="card"><div class="sw" style="margin:0"><div>Думать над сложными просьбами<small>Стихи, задачи, анализ, планы — сначала обдумывает: дольше, зато лучше. Простые вопросы — сразу.</small></div>
      <label class="tg"><input type="checkbox" id="br-think" ${S.llm.think !== "off" ? "checked" : ""}><i></i></label></div></div>`);
    // «Сеть Лиры» (04.11): общие вопросы — иногда видеокартам людей; по умолчанию выключено. Текст — ровно то, что делает фильтр сайта
    if (S.llm.cloud && !kidsOn()) h.push(`<div class="card" id="br-net"><div class="sw" style="margin:0"><div>Пускать мои общие вопросы в Сеть Лиры<small>Люди отдают свои видеокарты, и на общие вопросы вроде «почему небо голубое» иногда отвечает их компьютер. Узел получает только текст самого вопроса — без истории разговора, памяти, ключа и имени аккаунта; вопросы, похожие на личные (память, заметки, письма, деньги, близкие, здоровье, суд, адрес, имена людей и городов посреди фразы), и фото туда не уходят. Телефоны и почты в вопросе заменяются метками, но фильтр узнаёт не всё — не пишите в таких вопросах личного. Ответ узла со ссылками, номерами или просьбами о деньгах не принимается, а действия по его ответу программа выполняет только безопасные (поиск, погода, время). Правила подписаны сайтом Dewiar; ключ — у владельца.</small></div>
      <label class="tg"><input type="checkbox" id="br-net-on" ${S.netShare === true ? "checked" : ""}><i></i></label></div></div>`);
    if (S.llm.cloud) h.push(`<div class="card cloudc" id="cl-card"><div class="row2"><div style="flex:1"><b>Баланс</b><small class="hint" style="margin:2px 0 0;display:block" id="cl-sub">${esc(cloudWho())}</small></div><div class="cl-pct" id="cl-pct">…</div></div>
      <div class="cl-bar"><i id="cl-fill"></i></div><div class="hint" id="cl-turns" style="margin:0"></div><div class="hint" id="cl-per" style="margin:4px 0 0"></div>
      <details class="cl-lim" id="cl-lim" style="display:none;margin-top:8px"><summary>Мои лимиты</summary><small class="hint" style="display:block;margin:4px 0 6px">Не тратить больше — в день и в месяц, на всех ваших устройствах. Пусто — без лимита.</small>
        <div class="row2"><label class="f" style="flex:1;margin:0">В день, тал.<input id="cl-lim-d" inputmode="decimal" placeholder="без лимита"></label><label class="f" style="flex:1;margin:0">В месяц, тал.<input id="cl-lim-m" inputmode="decimal" placeholder="без лимита"></label></div></details>
      <details class="cl-lim" id="cl-auto" style="display:none;margin-top:8px"><summary>Автопополнение</summary>
        <div class="sw" style="margin:6px 0"><div><small id="cl-auto-t" style="display:block"></small></div><label class="tg"><input type="checkbox" id="cl-auto-on"><i></i></label></div>
        <div class="row2"><label class="f" style="flex:1;margin:0">Меньше, тал.<input id="cl-auto-below" inputmode="decimal"></label><label class="f" style="flex:1;margin:0">Пополнять на<input id="cl-auto-amt" inputmode="decimal"></label><label class="f" style="flex:1;margin:0">В месяц до<input id="cl-auto-cap" inputmode="decimal"></label></div>
        <small class="hint" id="cl-auto-st" style="display:block;margin-top:4px"></small><button class="btn" id="cl-auto-forget" style="margin-top:6px" hidden>Забыть карту</button></details>
      <div class="cl-co" id="cl-co" hidden><span id="cl-co-t"></span><button class="btn" id="cl-co-go" hidden>Выйти из компании</button></div>
      <details class="cl-lim" id="cl-join" hidden><summary>Код от компании</summary>
        <div class="row2" style="margin-top:6px"><input id="cl-join-code" placeholder="XXXX-XXXX" maxlength="9" autocomplete="off" autocapitalize="characters" spellcheck="false" aria-label="Код компании" style="flex:1"><button class="btn p" id="cl-join-go">Войти</button></div>
        <small class="hint" style="display:block;margin-top:4px">Код даёт руководитель. Ответы Лиры будет оплачивать компания, ваш баланс сохранится.</small><small class="hint" id="cl-join-res" style="display:block"></small></details>
      <div class="cl-use" id="cl-use"></div>
      <div class="row2" style="margin-top:10px"><button class="btn" id="cl-ref" style="flex:1">Обновить</button><button class="btn p" id="cl-how" style="flex:1">Пополнить</button></div>
      <div id="cl-pay" style="display:none;margin-top:12px"><div class="ym" id="cl-ym" style="display:none"><div class="ym-h"><b>Оплатить картой</b><span>Талеры зачислятся сами — через минуту после оплаты, снимок не нужен</span></div>
        <div class="ym-sums" id="cl-ym-sums"></div><div class="row2"><label class="f" style="flex:1;margin:0"><input id="cl-ym-own" inputmode="numeric" placeholder="своя сумма, ₽"></label><button class="btn p" id="cl-ym-go">Оплатить</button></div>
        <div class="res" id="cl-ym-res"></div></div>
        <div class="ym cx" id="cl-cx" style="display:none"><div class="ym-h"><b>Криптой · TON или USDT</b><span>Перевод в сети TON — талеры зачислятся сами через несколько минут</span></div>
        <div class="cx-seg" id="cl-cx-seg"></div><div class="cx-body"><div class="cx-qr" id="cl-cx-qr"></div><div class="cx-info">
        <div class="cx-f"><span>Адрес кошелька</span><code id="cl-cx-addr"></code><button class="btn" id="cl-cx-addr-cp">Скопировать</button></div>
        <div class="cx-f"><span>Комментарий — обязательно</span><code class="cx-code" id="cl-cx-code"></code><button class="btn" id="cl-cx-code-cp">Скопировать</button></div></div></div>
        <div class="cx-warn" id="cl-cx-warn"></div><p class="cx-rate" id="cl-cx-rate"></p><button class="btn p w" id="cl-cx-open">Открыть кошелёк</button><div class="res" id="cl-cx-res"></div></div>
        <div class="ym" id="cl-man"><div class="ym-h" id="cl-man-h" style="display:none;margin-bottom:8px"><b>Снимок оплаты администратору</b><span>Оплатите удобным способом и пришлите снимок — администратор зачислит</span></div>
        <ol class="pay-steps">
          <li><i>1</i><div class="ps-b"><b>Оплатите</b><button class="btn p w ps-go" id="cl-go" hidden>Перейти к оплате<svg viewBox="0 0 24 24"><path d="M7 17 17 7M9 7h8v8"/></svg></button>
            <div class="hint ps-own" id="cl-top"></div></div></li>
          <li><i>2</i><div class="ps-b"><b>Приложите снимок оплаты</b>
            <label class="cl-shot" id="cl-shot"><input type="file" id="cl-file" accept="image/*" hidden><svg viewBox="0 0 24 24"><rect x="3.5" y="5" width="17" height="14" rx="3"/><circle cx="9" cy="10" r="1.6"/><path d="m20.5 15.5-4.5-4.5-7.5 8"/></svg><span id="cl-shot-t">Выбрать снимок</span><img id="cl-img" alt=""></label>
            <div class="row2 ps-f"><label class="f" style="flex:1"><span>Сколько талеров</span><input id="cl-amt" inputmode="decimal" placeholder="напр. 5"><small class="ps-rub" id="cl-rub"></small></label>
            <label class="f" style="flex:1.4"><span>Комментарий</span><input id="cl-note" placeholder="как оплатили"></label></div></div></li>
          <li><i>3</i><div class="ps-b"><button class="btn p w" id="cl-send">Отправить заявку</button><small class="hint ps-when">Обычно зачисляем в течение дня — заряд пополнится сам.</small><div class="res" id="cl-res"></div></div></li>
        </ol><p class="hint ps-code" id="cl-code"></p></div><div id="cl-reqs"></div></div>
      <button class="btn w" id="cl-pair" style="margin-top:10px">Подключить ещё устройство</button>
      <div class="cl-foot">${loggedIn() && !S.llm.account ? `<button class="lnk" id="cl-acc">Думать по аккаунту</button>` : ""}<button class="lnk" id="cl-other">Подключить другой мозг</button>${S.llm.account ? "" : `<button class="lnk" id="cl-forget">Забыть ключ</button>`}</div></div>`);
    // приглашения друзей (cloud.php ?p=/ref): одна строка и «Пригласить»; список и чужой код — свёрнуты (refFill)
    if (S.llm.cloud) h.push(`<div class="card refc" id="ref-card"><div class="row2"><div style="flex:1"><b>Пригласить друга</b><small class="hint" id="ref-sub" style="margin:2px 0 0;display:block">Подарки вам и другу — талерами</small></div>
      <button class="btn p" id="ref-share">Пригласить</button></div><div id="ref-more"></div></div>`);
    if (S.join && S.join.id && !on) h.push(`<div class="card"><b>Заявка №${esc(S.join.id)} отправлена</b><p class="hint" style="margin:4px 0 10px">Как только её одобрят, всё подключится само — ничего вводить не нужно, я скажу. Можно закрыть приложение: проверю при следующем открытии.</p>
      <div class="row2"><button class="btn p" id="jn-check" style="flex:1">Проверить</button><button class="btn" id="jn-cancel" style="flex:1">Забыть заявку</button></div><div class="res" id="jn-res"></div></div>`);
    // сначала — то, что подходит любому человеку (бесплатная проба, код, аккаунт); своя модель и ключи сервисов —
    // свёрнуты в «Для опытных»: слова Ollama и OpenRouter новичка только пугали
    const tiles = `<p class="hint" style="margin:4px 2px 10px">«Мозг» — это то, чем помощница думает. Проще всего — облако Dewiar: на старте подарок, дальше — пополнение; поменять можно в любой момент.</p><div class="tiles">
      ${loggedIn() || S.join ? "" : `<button class="tile easy" data-w="join">${ICON.dewiar}<b>Подключить мозг Dewiar</b><small>Проще всего: имя и как с вами связаться — и всё. Без регистрации, на старте подарок</small></button>`}
      <button class="tile" data-w="dwkey">${ICON.key}<b>Код или ключ Dewiar</b><small>6 цифр с устройства, где Dewiar уже работает, или ключ dw-… от друга</small></button>
      ${loggedIn() ? "" : `<button class="tile" data-w="account">${ICON.user}<b>Аккаунт dewiar.pro</b><small>Только если команда Dewiar выдала вам логин — регистрации на сайте нет</small></button>`}</div>
      <details class="more pro"><summary>Для опытных: своя модель или ключ сервиса</summary><div class="tiles">
      <button class="tile" data-w="server">${ICON.server}<b>Своя модель</b><small>Ollama, LM Studio, vLLM — на вашем компьютере или сервере дома</small></button>
      <button class="tile" data-w="cloud">${ICON.cloud}<b>Ключ любимого сервиса</b><small>OpenAI, Claude, OpenRouter, DeepSeek или любой сервис по адресу — своим ключом</small></button>
      <button class="tile" data-w="pc">${ICON.pc}<b>Как на компьютере</b><small>Файл настроек из студии или адрес от администратора</small></button></div></details><div id="wz"></div>`;
    // мозг уже есть — другие способы свёрнуты: видно, что подключено, и не тянет нажать лишнее
    h.push(on || loggedIn() ? `<details class="more brainalt"><summary>Подключить другой мозг</summary>${tiles}</details>` : tiles);
    h.push(`<div class="card" id="px-card" style="margin-top:12px"><b>Сеть</b><p class="hint" style="margin:4px 0 10px">Провайдер блокирует dewiar.pro? Укажите прокси — через него пойдут только запросы к Dewiar (вход, модели, Знания), остальное — напрямую.</p>
      <div class="row2" style="align-items:flex-end"><label class="f" style="flex:1;min-width:0;margin:0"><span>Прокси</span><input id="px-in" placeholder="socks5://адрес:порт" autocapitalize="off" autocorrect="off" spellcheck="false" value="${esc(hideProxy(S.net.proxy))}"></label><button class="btn p" id="px-save">Сохранить</button></div>
      <div class="sw" style="margin-top:8px"><div>Использовать прокси Dewiar<small>Свой прокси не нужен — его выдаёт dewiar.pro, если вы вошли аккаунтом или подключили ключ. Только для серверов Dewiar.</small></div>
      <label class="tg"><input type="checkbox" id="px-dw" ${S.net.dewiar ? "checked" : ""}><i></i></label></div>
      <div class="sw" style="margin-top:8px"><div>Поиск и страницы через сервер Dewiar<small>Если провайдер режет поисковик или сайт — через сервер Dewiar (нужен вход или ключ). Выключите — только напрямую.</small></div>
      <label class="tg"><input type="checkbox" id="px-web" ${S.net.web_via !== false ? "checked" : ""}><i></i></label></div>
      <div class="res" id="px-res">${S.net.proxy ? "Запросы к Dewiar идут через ваш прокси." : S.net.dewiar && S.net.dewiar_secret ? "Запросы к Dewiar идут через прокси Dewiar." : ""}</div></div>`);
  } else if (setTab === "voice") {
    const voices = JSON.parse(D.voices() || "[]");
    h.push(`<h3>Слух</h3><div class="card">
      <label class="f"><span>Кто распознаёт речь</span><select id="stt-eng"><option value="system">${D.web ? "Этот браузер" : "Это устройство"}${info.recognizer ? "" : " (не найдено)"}</option>${cloudEars() ? `<option value="dewiar">Сервер Dewiar (GigaAM)</option>` : ""}<option value="server">Мой сервер распознавания</option></select></label>
      <div id="stt-srv"><label class="f"><span>Адрес (OpenAI-совместимый, …/v1)</span><input id="stt-url" placeholder="http://192.168.1.10:8090/v1" value="${esc(S.stt.url)}"></label>
      <div class="row2"><label class="f" style="flex:1"><span>Ключ</span><input id="stt-key" type="password" value="${esc(S.stt.key)}"></label><label class="f" style="flex:1"><span>Модель</span><input id="stt-model" placeholder="whisper-1" value="${esc(S.stt.model)}"></label></div></div>
      <div class="sw"><div>Микрофон Bluetooth-наушников<small>Наушники с микрофоном подключены — слушаю ими, а не телефоном: можно отойти от телефона.${D.btMicAvailable && D.btMicAvailable() ? " Сейчас подключены." : ""}</small></div>
      <label class="tg"><input type="checkbox" id="bt-mic" ${S.btMic !== false ? "checked" : ""}><i></i></label></div>
      ${D.web ? "" : `<div class="sw"><div>${appEn() ? "Понимать и русскую речь" : "Понимать английскую речь"}<small>${appEn() ? "Скажите по-русски — отвечу по-русски. Распознавание телефона само узнаёт язык фразы (Android 14 и новее, распознавание Google)." : "Скажите по-английски — отвечу по-английски и английским голосом. Распознавание телефона само узнаёт язык фразы (Android 14 и новее, распознавание Google)."}</small></div>
      <label class="tg"><input type="checkbox" id="lang2-en" ${S.lang2 === "en" ? "checked" : ""}><i></i></label></div>`}
      <p class="hint">${S.stt.auto ? "Распознавание этого устройства не отвечало — слушает сервер Dewiar. " : ""}${info.recognizer ? (D.web ? "Распознаёт сам браузер (Chrome, Edge) — через интернет. В Safari и на iPhone слушает сервер Dewiar — войдите аккаунтом или кодом." : "Распознавание устройства работает и без интернета, если скачан русский язык (Google → Распознавание речи офлайн).") : D.web && cloudEars() ? "В этом браузере нет распознавания речи — слушает сервер Dewiar." : D.web ? "В этом браузере нет распознавания речи — войдите аккаунтом dewiar.pro (слушать будет сервер Dewiar) или откройте Dewiar в Chrome или Safari." : cloudEars() ? "В устройстве нет распознавания речи — слушает сервер Dewiar." : "В устройстве нет распознавания речи — войдите аккаунтом dewiar.pro (слушать будет сервер Dewiar) или укажите свой сервер."}</p></div>
      <h3>Голос</h3><div class="card">
      <label class="f"><span>Кто говорит</span><select id="tts-eng"><option value="system">${D.web ? "Голос браузера" : "Голос устройства"}</option>${cloudVoice() ? `<option value="cloud">Голос Dewiar — у каждого персонажа свой</option>` : ""}<option value="eleven">ElevenLabs — своим ключом</option><option value="server">Голос моего сервера</option></select></label>
      <div id="tts-sys"><div class="row2"><label class="f" style="flex:1"><span>Голос героинь</span><select id="tts-voice"><option value="">Сам подберу</option>${voiceOpts(voices, S.tts.sys_voice)}</select></label>
        <label class="f" style="flex:1"><span>Голос героев</span><select id="tts-voice-m"><option value="">Сам подберу</option>${voiceOpts(voices, S.tts.sys_voice_m)}</select></label></div>
        <p class="hint" style="margin-top:0">${D.web ? "Голоса браузера — это голоса системы: в Windows, macOS и iOS есть русские женские и мужские — героям (Патрику, Джарвису, Агенту) достаётся мужской." : "Голосов устройства бывает несколько: у «Синтеза речи Google» есть и мужские — героям (Патрику, Джарвису, Агенту) достаётся мужской."}</p></div>
      <div id="tts-el"><label class="f"><span>Ключ ElevenLabs</span><input id="el-key" type="password" placeholder="sk_…" value="${esc(S.tts.el_key)}"></label>
        <div class="row2"><label class="f" style="flex:1"><span>Голос героинь (ID)</span><input id="el-vf" placeholder="${EL_VOICES.f} (Sarah)" value="${esc(S.tts.el_voice_f)}"></label>
          <label class="f" style="flex:1"><span>Голос героев (ID)</span><input id="el-vm" placeholder="${EL_VOICES.m} (George)" value="${esc(S.tts.el_voice_m)}"></label></div>
        <label class="f"><span>Модель</span><select id="el-model"><option value="eleven_flash_v2_5">Быстрая (Flash v2.5)</option><option value="eleven_multilingual_v2">Лучшее качество (Multilingual v2)</option></select></label>
        <p class="hint" style="margin-top:0">Ключ — на elevenlabs.io → Профиль → API Keys. Платите вы сами по тарифу ElevenLabs; ключ хранится только в этом телефоне. ID голоса — в «Voices» на сайте (кнопка «ID»).</p></div>
      <label class="f"><span>Скорость речи: <b id="rate-v">${(+S.tts.rate || 1).toFixed(2)}</b></span><input id="tts-rate" type="range" min="0.7" max="2" step="0.05" value="${+S.tts.rate || 1}"></label>
      ${(info.tts && !D.web) || D.mock || (D.web && ttsOk()) ? "" : cloudVoice() ? `<p class="hint">В ${D.web ? "этом браузере" : "устройстве"} нет русского голоса — говорит голос Dewiar.</p>` : D.web ? `<p class="hint">В этом браузере нет русского голоса — ответы текстом. Войдите аккаунтом dewiar.pro — заговорит голос Dewiar.</p>`
        : `<p class="hint">В устройстве нет русского голоса, поэтому ответы только текстом. Установите голос: «Синтез речи Google» из Play Маркета или бесплатный RHVoice (есть и для устройств без Google — в AppGallery и F-Droid), затем выберите его в настройках Android → «Синтез речи». <a href="#" id="tts-get">Открыть</a></p>`}</div>
      <div id="tts-srv"><label class="f"><span>Адрес (OpenAI-совместимый, …/v1)</span><input id="tts-url" placeholder="http://192.168.1.10:8091/v1" value="${esc(S.tts.url)}"></label>
      <div class="row2"><label class="f" style="flex:1"><span>Ключ</span><input id="tts-key" type="password" value="${esc(S.tts.key)}"></label><label class="f" style="flex:1"><span>Модель</span><input id="tts-model" placeholder="tts-1" value="${esc(S.tts.model)}"></label></div>
      <div class="row2"><label class="f" style="flex:1"><span>Голос героинь</span><input id="tts-v" placeholder="alloy" value="${esc(S.tts.voice)}"></label><label class="f" style="flex:1"><span>Голос героев</span><input id="tts-vm" placeholder="как у героинь" value="${esc(S.tts.voice_m)}"></label></div></div>
      <button class="btn w" id="tts-try">Послушать</button></div>
      <h3>Разговор</h3><div class="card">
      <label class="f"><span>Как вас зовут</span><input id="u-name" placeholder="необязательно" value="${esc(S.user_name)}"></label>
      <label class="f"><span>Слушать после ответа</span><select id="follow"><option value="ask">Только если ассистент спросил</option><option value="always">Всегда</option><option value="never">Нет</option></select></label>
      <div class="sw" style="margin-top:8px"><div>Сам замечает, что вы вернулись<small>Открыли приложение после перерыва — коротко скажет главное: что готово, что скоро; утром — сводка дня. Сказать нечего — промолчит.</small></div>
      <label class="tg"><input type="checkbox" id="wl-on" ${(S.welcome || {}).on !== false ? "checked" : ""}><i></i></label></div></div>`);
  } else if (MORE_SECS.includes(setTab)) {
    const cab = [];                                   // «Этот телефон в кабинете» — в «О приложении», после версии
    const opt = (list, cur) => list.map(([v, n]) => `<option value="${v}" ${v === cur ? "selected" : ""}>${n}</option>`).join("");
    // фон — плитками с живым образцом (тот же класс темы, что у экрана; кружок — материал её карточек), по группам
    // 30.10 (отзыв: «не видно, всё сразу»): сверху — какая тема сейчас и чем она хороша; плитки — ровной сеткой, как
    // были (группы с подписями пробовали — владелец: «удобно, но не так аккуратно»), порядок — по группам
    const skCur = PHONE_SKINS.find(x => x.id === lookSkin());
    const skBtn = (x) => `<button class="skm ${x.id === lookSkin() ? "on" : ""}" data-skin="${x.id}" role="radio" aria-checked="${x.id === lookSkin()}" title="${esc(x.group)} · ${esc(x.name)}"><i class="lk-prev skin-${x.id}"><b></b></i><span>${esc(x.name)}</span></button>`;
    if (setTab === "look") h.push(`<div class="card"><p class="sk-now" id="sk-now">${skCur ? `Сейчас — <b>${esc(skCur.name)}</b>${skCur.sub ? `<small>${esc(skCur.sub)}</small>` : ""}` : ""}</p>
      <div class="skins" role="radiogroup" aria-label="Тема">${PHONE_SKINS.map(skBtn).join("")}</div>
      <label class="f" style="margin-top:6px"><span>Когда говорит</span><select id="ap-fx">${opt([["bars", "Лучи"], ["pulse", "Пульс"], ["wave", "Волна"]], lookFx())}</select></label>
      <label class="f" style="margin-top:6px"><span>${esc(window.t("look.lang"))}</span><select id="ap-lang" translate="no">${opt([["auto", esc(window.t("lang.auto"))]].concat((window.dwLangs ? dwLangs() : []).map(l => [l.code, esc(l.name)])), S.lang || "auto")}</select></label>
      <div class="sw" style="margin-top:10px"><div>Портрет следит за наклоном<small class="hint" style="display:block;margin:2px 0 0">Наклоните телефон — персонаж чуть повернётся и посмотрит на вас. Камера не нужна.</small></div>
        <label class="tg"><input type="checkbox" id="ap-tilt" ${S.tilt === true ? "checked" : ""}><i></i></label></div></div>`);
    // «Возможности» (24.10): необязательное — по желанию; выключенное прячется, ничего не теряя
    const fsw = (id, k, t, x) => `<div class="sw" style="margin-top:8px"><div>${t}<small>${x}</small></div><label class="tg"><input type="checkbox" id="${id}" data-feat="${k}" ${feat(k) ? "checked" : ""}><i></i></label></div>`;
    if (setTab === "features") h.push(`<div class="card"><p class="hint" style="margin:0 0 4px">Включите только то, чем пользуетесь, — остальное не будет мешать. Выключенное ничего не теряет.</p>
      ${fsw("ft-games", "games", "Досуг — милые игры", "Сказки, головоломки, «Каляка», реверси против Лиры, аркады и «Выше облаков» с управлением наклоном; «Всё» (значок вверху) → «Досуг» или «Лира, давай поиграем»")}
      ${fsw("ft-close", "close", "Близкие — сердечко вверху", "Переписка и звонки с родными и друзьями, их помощники. Выключите — сердечко пропадёт; переписка сохранится")}
      <div class="fsub${feat("close") ? "" : " off"}" id="ft-sub"><small>Вкладки внутри «Близких»</small>
      ${fsw("ft-near", "near", "Рядом", "Где близкие, если они сами делятся местом")}
      ${fsw("ft-meet", "meet", "Встречи", "Знакомства с теми, кто рядом")}
      ${fsw("ft-fam", "family", "Семья — общий бюджет", "Траты за месяц у всей семьи, общий лимит и платежи. Позовут в семью — включится само")}</div></div>`);
    liteApply();
    if (setTab === "lite") h.push(`<div class="card"><label class="f" style="margin-top:0"><span>Для слабых телефонов и экономии батареи</span><select id="ap-lite">${opt([["auto", "Сам, когда нужно"], ["on", "Всегда"], ["off", "Никогда"]], S.lite || "auto")}</select></label>
      <p class="hint" id="lite-now" style="margin:6px 2px 0">${liteOn() ? `Сейчас включён: ${esc(liteWhyNow)}.` : "Сейчас выключен."} Портрет в покое неподвижен, проверки реже, «Близкие» без постоянной связи — раз в 15 минут.</p></div>`);
    // звук напоминаний: свои мягкие мелодии (Sounds.java, res/raw), системный или свой файл; ▶ — послушать
    const snd = (() => { try { return JSON.parse(D.alarmSound ? D.alarmSound() : "{}"); } catch (e) { return {}; } })();
    if (setTab === "sound" && D.notice) h.push(`<div class="card"><div class="sw" style="margin:0"><div>Лира заметила<small>Дождь или снег сегодня, жара, мороз, день рождения близкого — одно уведомление, когда есть повод; не чаще раза в день и не ночью.${S.notice && S.notice.on && !wqHome() ? " Скажите Лире свой город — и она будет предупреждать о погоде." : ""}</small></div>
      <label class="tg"><input type="checkbox" id="nt-on" ${S.notice && S.notice.on ? "checked" : ""}><i></i></label></div></div>`);
    // «Интересное в мире» (14.11): одна новость в сводке дня; темы — какие интересны (остальное подстроится по «👍 / Не моё»)
    if (setTab === "sound") { const wt = worldTaste().t; h.push(`<div class="card"><div class="sw" style="margin:0"><div>Интересное в мире<small>Одна любопытная новость в сводке дня — наука, космос, техника, природа… Под ней «Читать», «👍» и «Не моё» — Лира запоминает ваш вкус.</small></div>
      <label class="tg"><input type="checkbox" id="wn-on" ${worldTaste().on ? "checked" : ""}><i></i></label></div>
      <div class="wn-topics" id="wn-topics">${WORLD_TOPICS.map(([id, n]) => `<button type="button" data-t="${id}" class="${(+wt[id] || 0) > 0 ? "on" : (+wt[id] || 0) <= -2 ? "off" : ""}">${esc(trL(n))}</button>`).join("")}</div>
      <p class="hint" style="margin:6px 2px 0">Нажмите тему: интересно → не моё → всё равно.</p></div>`); }
    if (setTab === "sound") h.push(remHealthCard() + `<div class="card"><p class="hint" style="margin-top:0">Мягко и сначала тихо — громкость прибавляется за 20 секунд.</p>
      <div class="snds">${ALARM_SOUNDS.map(([id, n, sub]) => `<button class="snd ${id === (snd.id || "signature") ? "on" : ""}" data-snd="${id}"><i>${PLAY_SVG}</i><span><b>${n}</b><small>${sub}</small></span></button>`).join("")}
        <button class="snd ${snd.id === "custom" ? "on" : ""} ${snd.custom ? "" : "nofile"}" data-snd="custom"><i>${PLAY_SVG}</i><span><b>Свой звук</b><small id="snd-name">${snd.custom ? esc(snd.custom) : "Любая мелодия с телефона"}</small></span></button></div>
      <label class="btn w" id="snd-pick"><input type="file" id="snd-file" accept="audio/*" hidden>${snd.custom ? "Выбрать другой файл" : "Выбрать файл…"}</label><div class="res" id="snd-res"></div>
      ${D.alarmSoundSoft ? `<div class="sw" style="margin-top:12px"><div>Напоминания — громкостью уведомлений<small>Напоминания о делах звучат так громко, как уведомления телефона, — убавьте их кнопками громкости. Будильник и таймер остаются громкими.</small></div>
      <label class="tg"><input type="checkbox" id="snd-soft" ${snd.soft ? "checked" : ""}><i></i></label></div>` : ""}</div>`);
    if (setTab === "privacy" && window.DEWIAR_PRIVACY) h.push(`<div class="card priv">${DEWIAR_PRIVACY.items.map(([t, x]) => `<p><b>${esc(t)}.</b> ${esc(x)}</p>`).join("")}</div>`);
    if (setTab === "about") cab.push(`<h3>${D.web ? "Этот браузер" : "Этот телефон"} в кабинете</h3><div class="card"><p class="hint" style="margin-top:0">В кабинете облака (экзамен, здоровье) ${D.web ? "этот браузер" : "этот телефон"} —
      <b>${esc((info.device || "Телефон") + " · " + (info.version || "") + " · №" + devId().slice(-4))}</b>. Нет в списке — нажмите «Отметиться в кабинете»: появится через минуту.</p>
      <button class="btn w" id="dev-ping">Отметиться в кабинете</button><div class="res" id="dev-res"></div></div>`);
    const perms = [[MIC, "Микрофон"], [NOTIF, "Уведомления (напоминания)"], [CONTACTS, "Контакты (звонки по имени)"], [CALLP, "Звонки без лишнего нажатия"]];
    if (false) h.push(`<h3>Идеи Лиры</h3><div class="card idcard"><div class="row2"><span class="idbulb" aria-hidden="true">${IDEA_SVG}</span><p class="hint" style="margin:0;flex:1">Что Лире уметь дальше — решаем вместе: поддержите голосом нужное или предложите своё.</p></div>
      <button class="btn w" id="ideas-open" style="margin-top:10px">Открыть идеи</button></div>`);
    if (setTab === "bug") h.push(`<div class="card" id="bug-card"><p class="hint" style="margin-top:0">Напишите пару слов — разработчик увидит их вместе со снимком экрана и журналом работы (без ключей и паролей), ответит сюда, а когда исправит — я скажу. Голосом тоже можно: «сообщи об ошибке: …».</p>
      ${bugSnap && Date.now() - bugSnap.ts < 30 * 6e4 ? `<div class="bugsnap"><img src="data:image/jpeg;base64,${bugSnap.b64}" alt="Снимок экрана" id="bug-img"><label class="chk"><input type="checkbox" id="bug-use" checked><span>Приложить снимок экрана — каким он был до настроек</span></label></div>` : ""}
      <div class="bugpick" id="bug-pickbox">${bugPickHtml()}</div>
      <label class="f"><span>Что случилось</span><textarea id="rep-note" rows="3" maxlength="2000" placeholder="Например: «прошу другое радио — играет старое»"></textarea></label>
      <label class="f"><span>Как подписать вас в «Помощниках проекта» — необязательно</span><input id="bug-who" maxlength="40" value="${esc(S.who || "")}" placeholder="Имя или ник"></label>
      <label class="chk" style="margin:4px 0 10px"><input type="checkbox" id="bug-talk" checked><span>Приложить последние фразы разговора — помогают найти ошибку. Почта и телефоны скрываются</span></label>
      <button class="btn p w" id="rep-send">Отправить разработчику</button><div class="res" id="rep-res"></div>
      <div id="bug-mine">${complaintsHtml()}</div><div id="bug-thx"></div>
      <div class="sw" style="margin-top:8px"><div>Отправлять отчёт самому при сбое<small>Только при ошибках приложения, не чаще раза в полдня на одну и ту же</small></div>
      <label class="tg"><input type="checkbox" id="rep-auto" ${(S.report || {}).auto ? "checked" : ""}><i></i></label></div>
      <div class="sw"><div>Анонимный пульс для разработчика<small>Раз в несколько часов: версия, телефон, скорость запуска, сколько было сбоев — без разговоров, файлов и ключей</small></div>
      <label class="tg"><input type="checkbox" id="pulse-on" ${S.pulse !== false ? "checked" : ""}><i></i></label></div></div>
      `);
    if (setTab === "assist") h.push(`
      <div class="card"><p class="hint" style="margin-top:0">Назначьте Dewiar помощником телефона — тогда долгое нажатие кнопки питания (или «Домой») сразу его слушает.
      Настройки → Приложения → По умолчанию → <b>Цифровой помощник</b> → Dewiar.</p><button class="btn w" id="assist">Открыть настройки помощника</button></div>
      `);
    if (setTab === "hands") h.push(`
      <div class="card" id="hands-card">${handsCard()}</div>
      `);
    if (setTab === "telegram") h.push(`
      <div class="card" id="tg-card">${!tgOn() ? `<p class="hint" style="margin:0 0 10px">Бот Dewiar в Telegram подключается на компьютере: студия → «Подключение» → Telegram. Бот один для всех ваших устройств: пишите или присылайте голосовые — ответит компьютер, а когда он выключен — сервер Dewiar. На телефоне ничего настраивать не нужно.</p><button class="btn w" id="tg-bot" disabled>Открыть бота в Telegram</button>`
        : (S.tg || {}).linked ? `<div class="row2"><span class="res ok" style="flex:1;margin:0">Подключён${S.tg.name ? ": " + esc(S.tg.name) : ""}${S.tg.bot ? " · @" + esc(S.tg.bot) : ""}</span><button class="btn" id="tg-off">Отключить</button></div>
          <p class="hint" style="margin:8px 0 0">Пишите боту или присылайте голосовые — ответит ${esc(persona().name)}. Заметки, списки и напоминания из Telegram появятся здесь, в «Мой день». Компьютер с Dewiar включён — отвечает он.</p>${S.tg.bot ? `<button class="btn w" id="tg-open" style="margin-top:8px">Открыть бота</button>` : ""}
          <div class="sw" style="margin-top:12px"><div>Отвечать с телефона, когда компьютер выключен<small>Ответит ${esc(persona().name)} этого телефона своим мозгом, молча — ответ уйдёт в Telegram. Сразу — пока приложение открыто или в шторке значок «Dewiar на связи»; телефон уснул — ответит сервер Dewiar. Тратит немного заряда.</small></div>
          <label class="tg"><input type="checkbox" id="tg-hand" ${S.tg.hand !== false ? "checked" : ""}><i></i></label></div>`
        : `<p class="hint" style="margin:0 0 10px">Пишите и присылайте голосовые боту Dewiar в Telegram — ассистент ответит, даже когда телефон убран: поставит напоминание, запишет заметку, ответит голосом.</p><button class="btn p w" id="tg-go">Подключить Telegram</button>`}<div class="res" id="tg-res"></div></div>
      `);
    if (setTab === "smart") h.push(`
      <h3>Умный дом Яндекса</h3><div class="card">${S.home.token ? `<div class="row2"><span class="res ok" style="flex:1" id="home-st">Подключён</span><button class="btn" id="home-off">Отключить</button></div>` :
      `<p class="hint" style="margin-top:0">Тот же дом, что у Алисы: «включи свет в спальне», «кондиционер на 22».</p>
      <p class="hint">Уже подключён на компьютере? Если телефон с ним связан (один аккаунт или «Добавить устройство»), дом появится здесь сам в течение нескольких минут. Иначе: студия → «Подключение» → «Умный дом Яндекса» → «На телефон» — и скажите здесь «отсканируй код».</p>
      <p class="hint"><b>1.</b> «Получить ключ» → войдите в Яндекс тем же аккаунтом, что в «Доме с Алисой» → «Разрешить».<br><b>2.</b> Скопируйте ключ, который покажет Яндекс (начинается с y0_), и вставьте сюда.</p>
      <button class="btn w" id="home-auth" style="margin-bottom:10px">Получить ключ</button>
      <label class="f"><span>Ключ от Яндекса</span><input id="home-tok" type="password" placeholder="y0_…"></label><button class="btn p w" id="home-go">Подключить</button>`}<div class="res" id="home-res"></div></div>
      ${D.web ? "" : `<h3>Home Assistant</h3><div class="card">${haOn() ? `<div class="row2"><span class="res ok" style="flex:1" id="ha-st">Подключён: ${esc(S.ha.url)}</span><button class="btn" id="ha-off">Отключить</button></div>` :
      `<p class="hint" style="margin-top:0">Свой умный дом на Home Assistant — рядом с Яндексом: «включи свет в спальне», «какая температура на кухне», «запусти сценарий спокойной ночи».</p>
      <p class="hint">Токен: в Home Assistant — профиль (кружок с вашим именем внизу слева) → вкладка «Безопасность» → «Долгосрочные токены доступа» → «Создать токен». Подключён на компьютере — телефон получит его сам (конвертом, только своим устройствам).</p>
      <label class="f"><span>Адрес Home Assistant</span><input id="ha-url" placeholder="http://192.168.1.20:8123" value="${esc((S.ha || {}).url || "")}"></label>
      <label class="f"><span>Долгосрочный токен</span><input id="ha-tok" type="password" placeholder="eyJ…"></label><button class="btn p w" id="ha-go">Подключить</button>`}<div class="res" id="ha-res"></div></div>`}
      `);
    if (setTab === "widget") h.push(`
      <div class="card">${widgetCard()}</div>
      `);
    if (setTab === "__none") h.push(`
      <div class="card">${syncCard()}</div>
      `);
    if (setTab === "perms") h.push(`
      <div class="card">${perms.map(([p, n]) => `<div class="sw"><div>${n}</div>${D.has(p) ? `<span class="res ok" style="margin:0">есть</span>` : `<button class="btn" data-perm="${p}">Разрешить</button>`}</div>`).join("")}
      <div class="sw"><div>Точные будильники</div>${D.exactAlarms() ? `<span class="res ok" style="margin:0">есть</span>` : `<button class="btn" onclick="Dewiar.openSettings('alarms')">Разрешить</button>`}</div></div>
      `);
    if (setTab === "__none") h.push(`
      <div class="card"><p class="hint" style="margin:0 0 10px">Короткие фразы, которые я понимаю сразу: фонарик, радио, сканер кодов, таймер, план дня, «освободи место»… Нажмите любую — и я сделаю.</p>
        <button class="btn w p" id="tricks-open">Посмотреть</button></div>
      `);
    if (false) h.push(`
      ${kidsOn() ? "" : `<h3>Работа</h3><div class="card"><p class="hint" style="margin:0 0 10px">${wkJobs().length ? "Поручения: " + wkJobs().map(j => "«" + esc(j.team) + "»").join(", ") + ". Отдельно от личного; уйти можно в любой момент." : "Поручения с работы — отдельно от личного. Руководитель покажет печать Dewiar: наведите сканер, и поручения будут приходить сюда."}</p>
        <button class="btn w${wkJobs().length ? "" : " p"}" id="work-open">${wkJobs().length ? "Открыть «Работу»" : "Присоединиться по коду"}</button></div>`}
      `);
    if (setTab === "__none") h.push(`
      <div class="card"><p class="hint" style="margin:0 0 10px">${kidsOn() ? `Включён: говорит Совёнок Уго, сегодня ${kidsReport().used} из ${kidsLimit()} мин.` : "Ребёнок говорит с Совёнком Уго: сказки, загадки, «почему?» — только безопасное, время за день и отчёт вам. Выключить — только с PIN."}</p>
        <button class="btn w${kidsOn() ? "" : " p"}" id="kids-open">${kidsOn() ? "Отчёт и настройки" : "Настроить"}</button></div>
      `);
    if (setTab === "__none") h.push(`
      <div class="card"><p class="hint" style="margin:0 0 10px">Ответы на «как…» — с примерами фраз, и короткие курсы: урок в день, пять минут. Или просто спросите Лиру: «как…»</p>
        <div class="row2"><button class="btn" id="qa-open" style="flex:1">Вопрос — ответ</button><button class="btn p" id="course-open" style="flex:1">Курсы</button></div></div>
      `);
    if (setTab === "about") h.push(`
      <div class="card"><div>Dewiar ${esc(info.version || "")} · ${D.web ? "в браузере" : "Android " + esc(info.android || "")}</div><small class="hint" style="margin:2px 0 0;display:block">${esc(info.device || "")}</small>
      <div class="res" id="upd-res"></div><button class="btn w" id="upd-check" style="margin-top:6px">Проверить обновление</button>
      <button class="btn w" id="news-open" style="margin-top:8px">Что нового</button></div>
      <details class="danger"><summary>Начать с чистого листа</summary><p class="hint">Ассистент забудет разговор и всё, что запомнил о вас: имя, привычки, просьбы. Дневник, душа персонажей, напоминания и заметки останутся. Отменить нельзя.</p>
      <button class="btn w" id="reset">Забыть разговор и память</button></details>
      ${info.crash ? `<h3>Последняя ошибка</h3><div class="card"><div class="crash">${esc(info.crash)}</div><div class="row2" style="margin-top:8px"><button class="btn" id="cr-send" style="flex:1">Отправить</button><button class="btn" id="cr-clear" style="flex:1">Очистить</button></div></div>` : ""}`);
    h.push(...cab);
  }
  if (setTab === "devices") h.push(devHtml());       // «Устройства» (devices.js, 0.56)
  $("#set-body").innerHTML = h.join("");
  if (setTab === "devices") devBind();
  if (D.web) webTrimSettings();
  $$("[data-st]").forEach(b => b.onclick = () => { setTab = b.dataset.st; renderSettings(); });
  wireSettings(info);
}

function wireSettings(info) {
  const g = (id) => $("#" + id);
  if (g("dev-ping")) g("dev-ping").onclick = async () => { const r = g("dev-res"); r.className = "res"; r.textContent = "отправляю…";
    const ok = await pulseSend(); r.className = ok ? "res ok" : "res bad";
    r.textContent = ok ? "Готово — обновите список «Где» в кабинете." : (S.pulse === false ? "«Анонимный пульс» выключен — включите его ниже, и телефон появится." : "Не получилось — проверьте интернет."); };
  if ($("#ap-lang")) $("#ap-lang").onchange = (e) => { S.lang = e.target.value; saveS(); if (window.dwSetLang) dwSetLang(S.lang, phoneSysLang()); lang2Apply(); };
  $$(".skm").forEach(b => b.onclick = () => { S.skin = b.dataset.skin; saveS(); applyLook(); $$(".skm").forEach(x => { x.classList.toggle("on", x === b); x.setAttribute("aria-checked", String(x === b)); });
    const c = PHONE_SKINS.find(x => x.id === b.dataset.skin), n = $("#sk-now"); if (c && n) n.innerHTML = `Сейчас — <b>${esc(c.name)}</b>${c.sub ? `<small>${esc(c.sub)}</small>` : ""}`; });
  if (g("ap-fx")) g("ap-fx").onchange = () => { S.voice_fx = g("ap-fx").value; saveS(); applyLook(); };
  if (g("ap-tilt")) g("ap-tilt").onchange = () => { S.tilt = g("ap-tilt").checked; saveS(); tiltSync(); };
  $$("[data-feat]").forEach(x => x.onchange = () => { S.features = Object.assign({}, S.features || {}, { [x.dataset.feat]: x.checked }); saveS(); featApply();
    if (x.dataset.feat === "close" && g("ft-sub")) g("ft-sub").classList.toggle("off", !x.checked);
    toast(x.checked ? "Включено" : "Выключено — включить можно здесь же", 2200); });
  if (g("ap-lite")) g("ap-lite").onchange = () => { S.lite = g("ap-lite").value; saveS(); liteApply();
    g("lite-now").textContent = (liteOn() ? `Сейчас включён: ${liteWhyNow}.` : "Сейчас выключен.") + " Портрет в покое неподвижен, проверки реже, «Близкие» без постоянной связи — раз в 15 минут."; };
  // звук напоминаний: нажатие — выбрать и послушать (ещё раз — стоп); «Свой звук» без файла — сразу выбор файла
  const sndPlaying = (id) => $$(".snd").forEach(x => x.classList.toggle("play", x.dataset.snd === id));
  wireRemHealth();
  $$(".snd").forEach(b => b.onclick = () => {
    const id = b.dataset.snd;
    if (id === "custom" && b.classList.contains("nofile")) return g("snd-file").click();
    if (D.alarmSoundSet && D.alarmSoundSet(id)) $$(".snd").forEach(x => x.classList.toggle("on", x === b));
    sndPlaying(D.alarmSoundTry && D.alarmSoundTry(id) ? id : "");
  });
  // идея №72 (30.10: «в гарнитуре напоминание орёт в ухо, а будильник убавить — просплю»): напоминания — потоком уведомлений
  if (g("snd-soft")) g("snd-soft").onchange = () => { const on = D.alarmSoundSoft(g("snd-soft").checked); g("snd-soft").checked = on;
    toast(on ? "Напоминания — громкостью уведомлений, будильник — громкий" : "Напоминания — громко, как будильник", 2600); };
  if (g("snd-file")) g("snd-file").onchange = () => {
    const f = g("snd-file").files[0]; if (!f) return;
    if (f.size > 12 * 1024 * 1024) { g("snd-res").className = "res bad"; g("snd-res").textContent = "Файл больше 12 МБ — выберите покороче."; return; }
    g("snd-res").className = "res"; g("snd-res").textContent = "Сохраняю…";
    // мелодия из «Рингтонов» телефона приходит без имени файла (№753) — «Своя мелодия», а не номер
    const nm = /^\d*$/.test(f.name.replace(/\.[a-z0-9]+$/i, "")) ? "Своя мелодия" : f.name.replace(/\.[a-z0-9]+$/i, "");
    const fr = new FileReader();
    fr.onload = () => {
      const err = D.alarmSoundCustom ? D.alarmSoundCustom(String(fr.result).split(",")[1] || "", nm) : "нет на этом телефоне";
      if (err) { g("snd-res").className = "res bad"; g("snd-res").textContent = "Не подошёл: " + err + "."; return; }
      g("snd-res").className = "res ok"; g("snd-res").textContent = "Свой звук выбран.";
      const c = $('.snd[data-snd="custom"]'); c.classList.remove("nofile"); g("snd-name").textContent = nm;
      $$(".snd").forEach(x => x.classList.toggle("on", x === c));
      sndPlaying(D.alarmSoundTry && D.alarmSoundTry("custom") ? "custom" : "");
    };
    fr.readAsDataURL(f);
  };
  if (g("br-think")) g("br-think").addEventListener("change", () => { if (g("br-think").checked) delete S.llm.think; else S.llm.think = "off"; saveS(); });
  if (g("wn-on")) g("wn-on").addEventListener("change", () => { S.world = Object.assign(worldTaste(), { on: g("wn-on").checked }); saveS(); });
  document.querySelectorAll("#wn-topics button").forEach(b => b.onclick = () => {
    const w = worldTaste(), id = b.dataset.t, v = +w.t[id] || 0, nv = v > 0 ? -2 : v <= -2 ? 0 : 2;   // по кругу: интересно → не моё → всё равно
    if (nv) w.t[id] = nv; else delete w.t[id];
    S.world = w; saveS(); b.className = nv > 0 ? "on" : nv < 0 ? "off" : "";
  });
  if (g("nt-on")) g("nt-on").addEventListener("change", async () => { if (g("nt-on").checked) await needPerm("android.permission.POST_NOTIFICATIONS").catch(() => {}); noticeSet(g("nt-on").checked); });
  if (g("br-net-on")) g("br-net-on").addEventListener("change", () => { S.netShare = g("br-net-on").checked; saveS();
    toast(S.netShare ? "Общие вопросы иногда ответит Сеть Лиры — похожие на личные только сервер Dewiar" : "Всё отвечает сервер Dewiar", 3000); });
  if (setTab === "brain") {
    $$("#br-back [data-forget]").forEach(b => b.onclick = () => {
      if (!b.classList.contains("ask")) { $$("#br-back .brdel.ask").forEach(x => x.classList.remove("ask")); b.classList.add("ask"); clearTimeout(b._t); b._t = setTimeout(() => b.classList.remove("ask"), 4000); return; }
      const l = llmBack()[+b.dataset.forget]; if (!l) return;
      const id = llmId(l); S.llmSaved = (S.llmSaved || []).filter(x => llmId(x) !== id); saveS();
      toast(`«${brainNameOf(l)}» убран из списка`); renderSettings();
    });
    if (g("br-econ-on")) g("br-econ-on").onchange = async (ev) => {
      const r = g("br-econ-res"), cb = ev.target;
      if (!cb.checked) { S.llm.economy = ""; saveS(); toast("Экономный режим выключен"); renderSettings(); return; }
      cb.disabled = true; r.className = "res"; r.textContent = "ищу недорогую модель у сервиса…";
      try {
        let ms = [];
        if (isOllama()) { const x = await http("GET", ollamaRoot() + "/api/tags", { timeout: 10000 }); ms = (JSON.parse(x.body).models || []).map(m => m.name); }
        else { const x = await http("GET", llmBase() + "/models", { headers: llmHeaders(), timeout: 15000 }); ms = (JSON.parse(x.body).data || []).map(m => m.id); }
        const m = econSuggest(ms);
        if (!m) { cb.checked = false; r.className = "res bad"; r.textContent = "У этого сервиса не нашлось недорогой модели — экономить не на чем."; return; }
        S.llm.economy = m; saveS(); toast("Экономный режим: простое — " + m, 4000); renderSettings();
      } catch (e) { cb.checked = false; r.className = "res bad"; r.textContent = "Список моделей не пришёл: " + netErr(e.message || e); }
      finally { cb.disabled = false; }
    };
    if (g("br-pull")) g("br-pull").onclick = async () => {
      const r = g("br-pull-res"); g("br-pull").disabled = true; r.className = "res"; r.textContent = "Спрашиваю ваши устройства…";
      try { const ok = await devBrainsPull(); r.textContent = ok ? "Жду ответа — компьютер должен быть включён и Dewiar запущен (до 10 минут)." : devBrainsMiss(true); }
      catch (e) { r.className = "res bad"; r.textContent = netErr(e.message || e); } finally { g("br-pull").disabled = false; }
      setTimeout(() => clPoll().catch(() => { }), 4000);
    };
    $$("#br-back [data-back]").forEach(b => b.onclick = async () => {
      const r = g("br-back-res"); b.disabled = true; r.className = "res"; r.textContent = "подключаю…";
      try { await llmRestore(+b.dataset.back); toast("Мозг: " + brainName()); renderSettings(); }
      catch (e) { b.disabled = false; r.className = "res bad"; r.textContent = e.message; }
    });
    if (g("br-test")) g("br-test").onclick = async () => { const b = g("br-test"), r = g("br-res"); b.disabled = true; r.className = "res"; r.textContent = "спрашиваю модель…";
      try {
        if (!S.llm.base_url && !(await ensureBrain())) throw new Error("модели Dewiar по аккаунту сейчас не отвечают — проверьте интернет");
        const t0 = Date.now(); const x = await llmStream([{ role: "user", content: "Ответь одним словом: готово" }], null, null);
        r.className = "res ok"; r.textContent = `Работает: ответ за ${((Date.now() - t0) / 1000).toFixed(1)} с — «${x.text.trim().slice(0, 60)}»`;
        if (!g("cl-card") && S.llm.cloud) setTimeout(renderSettings, 1500);
      } catch (e) { r.className = "res bad"; r.textContent = e.message; } finally { b.disabled = false; } };
    if (!S.llm.base_url && loggedIn()) ensureBrain().then(ok => { if (ok && setTab === "brain" && $("#sh-set").classList.contains("on")) renderSettings(); });
    cloudCaps();
    $$(".tile").forEach(b => b.onclick = () => { $$(".tile").forEach(x => x.classList.toggle("on", x === b)); wizard(b.dataset.w); });
    if (g("jn-check")) g("jn-check").onclick = async () => { const r = g("jn-res"); r.className = "res"; r.textContent = "проверяю…";
      try { const d = await joinPoll(true); r.className = d && d.status === "no" ? "res bad" : "res ok"; r.textContent = (d && d.text) || "Пока ждёт проверки."; if (d && d.key) setTimeout(renderSettings, 1200); }
      catch (e) { r.className = "res bad"; r.textContent = e.message; } };
    if (g("jn-cancel")) g("jn-cancel").onclick = () => { S.join = null; saveS(); renderSettings(); };
    if (g("px-save")) g("px-save").onclick = () => saveProxy(g("px-in").value, g("px-res"), g("px-save"));
    if (g("px-web")) g("px-web").onchange = () => { S.net.web_via = g("px-web").checked; saveS(); toast(S.net.web_via ? "Запасной путь через Dewiar включён" : "Поиск и страницы — только напрямую"); };
    if (g("px-dw")) g("px-dw").onchange = async () => { const on = g("px-dw").checked, r = g("px-res"); S.net.dewiar = on; saveS();
      r.className = "res"; r.textContent = on ? "получаю прокси с dewiar.pro…" : "";
      const err = on ? await dwProxyFetch(true) : ""; applyProxy();
      r.className = "res " + (err ? "bad" : "ok"); r.textContent = !on ? "Прокси Dewiar выключен." : err ? "Прокси Dewiar: " + err : (S.net.proxy ? "Прокси Dewiar получен; сейчас главнее ваш прокси." : "Запросы к Dewiar идут через прокси Dewiar."); };
    if (g("acc-out")) g("acc-out").onclick = () => { if (!confirm("Выйти из аккаунта dewiar.pro? Модели и Знания по аккаунту отключатся.")) return; accountLogout(); toast("Вы вышли из аккаунта"); renderSettings(); };
    if (g("acc-use")) g("acc-use").onclick = async () => { const b = g("acc-use"); b.disabled = true;
      try { await cloudConnect(S.account.token, S.accCloud.base, { account: true }); toast("Думают модели Dewiar"); renderSettings(); } catch (e) { b.disabled = false; toast(e.message); } };
    if (g("ref-card")) { refLoad(); g("ref-share").onclick = () => refShare().catch(e => toast(e.message)); }
    if (g("cl-card")) {
      cloudFill(cloudInfo); cloudBalance(true).then(cloudFill).catch(async e => {
        if (await fixDeadKey(e.message)) { renderSettings(); return; }            // ключ удалён, а аккаунт есть — переключились сами
        g("cl-turns").textContent = e.message + (keyGone(e.message) ? " Нажмите «Забыть ключ»" + (loggedIn() ? " или «Думать по аккаунту»." : " и подключите мозг заново.") : ""); g("cl-pct").textContent = "—"; });
      if (g("cl-acc")) g("cl-acc").onclick = async () => { g("cl-acc").disabled = true; if (await fixDeadKey()) renderSettings(); else { g("cl-acc").disabled = false; toast("Не получилось подключиться по аккаунту — проверьте интернет"); } };
      if (g("cl-pair")) g("cl-pair").onclick = () => { setTab = "devices"; renderSettings(); setTimeout(devGive, 50); };   // 0.56: код — в «Устройствах»
      // «Забыть ключ» (0.82.1) — не красной кнопкой под «Пополнить», а ссылкой внизу карточки; подтверждение — как есть на деле
      if (g("cl-forget")) g("cl-forget").onclick = async () => {
        const k4 = String(S.llm.api_key || "").slice(-4);
        if (!confirm((loggedIn() ? `Забыть ключ Dewiar …${k4}? Думать буду по аккаунту ${S.account.login || ""}.`
          : `Забыть ключ Dewiar …${k4}? Пока не подключите другой мозг, я не смогу отвечать. Нового подарка не будет — он на этом устройстве уже был.`)
          + "\n\nТалеры останутся на ключе. Вернуть его — одной кнопкой: «Мозг» → «Прежние мозги» → «Вернуть».")) return;
        await forgetKey(); toast("Ключ забыт. Вернуть — «Прежние мозги» → «Вернуть»", 6000); renderSettings(); };
      if (g("cl-other")) g("cl-other").onclick = () => { const d = $(".brainalt"); if (d) { d.open = true; d.scrollIntoView({ behavior: "smooth", block: "start" }); } };
      g("cl-amt").oninput = clRubShow;
      // «Обновить» — заметно: что сейчас на счёте (раньше нажатие выглядело так, будто ничего не произошло)
      g("cl-ref").onclick = () => cloudBalance(true).then(c => { cloudFill(c); cloudUsage && cloudUsage();
        toast("Обновлено: " + (c.site ? (c.balance_text || c.balance + " тал.") + " на счёте dewiar.pro" : "заряд " + (c.percent ?? 0) + "%")); }).catch(e => toast(e.message));
      g("cl-how").onclick = () => { const t = g("cl-pay"), open = t.style.display === "none"; t.style.display = open ? "" : "none"; g("cl-how").classList.toggle("on", open); if (open) clPayLoad(); };
      g("cl-ym-go").onclick = () => ymPay(+String(g("cl-ym-own").value).replace(/\s/g, "").replace(",", "."));
      g("cl-cx-addr-cp").onclick = () => cxCopy("address"); g("cl-cx-code-cp").onclick = () => cxCopy("code"); g("cl-cx-open").onclick = cxOpen;
      cloudUsage();
      let img = "";
      g("cl-file").onchange = (e) => { const f = e.target.files[0]; if (!f) return; if (f.size > 6e6) { toast("Снимок больше 6 МБ"); return; }
        const fr = new FileReader(); fr.onload = () => { img = fr.result; g("cl-img").src = img; g("cl-shot").classList.add("has"); g("cl-shot-t").textContent = "Снимок приложен — заменить"; }; fr.readAsDataURL(f); };
      g("cl-send").onclick = async () => { const r = g("cl-res"), amount = +(g("cl-amt").value.replace(",", ".")) || 0;
        if (!amount && !img) { r.className = "res bad"; r.textContent = "Приложите снимок оплаты (шаг 2) — или напишите, сколько талеров"; return; }
        r.className = "res"; r.textContent = "отправляю…";
        try { const x = await cloudPost("/topup", { amount, note: g("cl-note").value.trim(), image: img }); r.className = "res ok"; r.textContent = "Заявка отправлена — после проверки заряд пополнится сам.";
          img = ""; g("cl-shot").classList.remove("has"); g("cl-shot-t").textContent = "Выбрать снимок"; g("cl-amt").value = ""; g("cl-note").value = ""; clRubShow(); clReqs(x.requests); }
        catch (e) { r.className = "res bad"; r.textContent = e.message; } };
    }
  } else if (setTab === "voice") {
    const sttDw = ((S.stt.engine === "server" && /cloud\.php/.test(S.stt.url || "")) || (S.stt.engine === "system" && !info.recognizer)) && cloudEars();
    if (g("wl-on")) g("wl-on").addEventListener("change", () => { S.welcome = Object.assign({}, S.welcome || {}, { on: g("wl-on").checked }); saveS(); });
    g("stt-eng").value = sttDw ? "dewiar" : S.stt.engine; g("tts-eng").value = S.tts.engine === "cloud" && !cloudVoice() ? "system" : S.tts.engine; g("follow").value = S.follow;
    const vis = () => { const te = g("tts-eng").value; g("stt-srv").style.display = g("stt-eng").value === "server" ? "" : "none";
      g("tts-srv").style.display = te === "server" ? "" : "none"; g("tts-el").style.display = te === "eleven" ? "" : "none";
      g("tts-sys").style.display = te === "system" || te === "cloud" ? "" : "none"; };
    g("el-model").value = S.tts.el_model || "eleven_flash_v2_5";
    vis();
    const saveV = () => { const se = g("stt-eng").value, ce = cloudEars();
      S.stt = se === "dewiar" && ce ? { engine: "server", url: ce.url, key: ce.key, model: "gigaam", from_account: loggedIn() }
        : { engine: se, url: se === "server" && /cloud\.php/.test(g("stt-url").value) ? "" : g("stt-url").value.trim(), key: g("stt-key").value.trim(), model: g("stt-model").value.trim() };
      Object.assign(S.tts, { engine: g("tts-eng").value, url: g("tts-url").value.trim(), key: g("tts-key").value.trim(), model: g("tts-model").value.trim(), sys_voice: g("tts-voice").value,
        sys_voice_m: g("tts-voice-m").value, voice: g("tts-v").value.trim(), voice_m: g("tts-vm").value.trim(), el_key: g("el-key").value.trim(),
        el_voice_f: g("el-vf").value.trim(), el_voice_m: g("el-vm").value.trim(), el_model: g("el-model").value, rate: +g("tts-rate").value });
      S.user_name = g("u-name").value.trim(); S.follow = g("follow").value; saveS(); vis(); g("rate-v").textContent = (+S.tts.rate).toFixed(2); };
    $$("#set-body input, #set-body select").forEach(x => x.onchange = saveV);
    g("bt-mic").onchange = () => { S.btMic = g("bt-mic").checked; saveS(); btMicSync(); };
    if (g("lang2-en")) g("lang2-en").onchange = () => { S.lang2 = g("lang2-en").checked ? "en" : ""; saveS(); lang2Apply(); };
    const rateFill = () => { const r = g("tts-rate"); r.style.setProperty("--p", ((r.value - r.min) / (r.max - r.min) * 100) + "%"); };
    rateFill();
    g("tts-rate").oninput = () => { g("rate-v").textContent = (+g("tts-rate").value).toFixed(2); rateFill(); };
    g("tts-try").onclick = () => { saveV(); say(`Привет! Это ${persona().name}. Так звучит мой голос.`); };
    if (g("tts-get")) g("tts-get").onclick = (e) => { e.preventDefault(); D.openSettings("tts") || D.openUrl("https://play.google.com/store/apps/details?id=com.google.android.tts"); };
  } else if (MORE_SECS.includes(setTab)) {
    if (g("assist")) g("assist").onclick = () => { if (!D.openSettings("assistant")) toast("Откройте: Настройки → Приложения → По умолчанию → Цифровой помощник"); };
    $$("[data-perm]").forEach(b => b.onclick = async () => { await needPerm(b.dataset.perm); renderSettings(); });
    if (g("home-go")) g("home-go").onclick = async () => { const r = g("home-res"); let tok = g("home-tok").value.trim(); const m = tok.match(/access_token=([^&\s]+)/); if (m) tok = m[1];
      if (/^[0-9a-f]{32}$/i.test(tok)) { r.className = "res bad"; r.textContent = "Это ClientID приложения, а не ключ. Нажмите «Получить ключ» → «Разрешить» — Яндекс покажет ключ (начинается с y0_)"; return; }
      if (tok.length < 20) { r.className = "res bad"; r.textContent = tok ? "Это не похоже на ключ — скопируйте его целиком (начинается с y0_)" : "Сначала «Получить ключ» — Яндекс покажет ключ, вставьте его сюда"; return; }
      const old = S.home.token; S.home.token = tok; r.className = "res"; r.textContent = "проверяю…";
      try { const i = await homeYandex(); homeSet(tok); r.className = "res ok"; r.textContent = `Готово: устройств ${i.devices.length}, сценариев ${i.scenarios.length}. Скажите «включи свет».`; setTimeout(renderSettings, 1800); }
      catch (e) { S.home.token = old; r.className = "res bad"; r.textContent = e.message; } };
    if (g("ha-go")) g("ha-go").onclick = async () => { const r = g("ha-res"); r.className = "res"; r.textContent = "проверяю…";
      try { await haConnect(g("ha-url").value, g("ha-tok").value); const i = await homeGet(true); r.className = "res ok"; r.textContent = `Готово: устройств ${i.devices.filter(d => d.src === "ha").length}`; setTimeout(renderSettings, 1500); }
      catch (e) { r.className = "res bad"; r.textContent = e.message; } };
    if (g("ha-off")) g("ha-off").onclick = () => { haForget(); renderSettings(); };
    if (g("home-auth")) g("home-auth").onclick = () => D.openUrl("https://oauth.yandex.ru/authorize?response_type=token&client_id=" + ((S.home.client_id || "").trim() || YANDEX_CID));
    if (g("home-off")) { homeGet().then(i => g("home-st") && (g("home-st").textContent = `Подключён: устройств ${i.devices.length}`)).catch(e => g("home-st") && (g("home-st").textContent = e.message));
      g("home-off").onclick = () => { homeSet(""); renderSettings(); }; }
    wireHands();
    if (g("tg-go")) g("tg-go").onclick = async () => { const b = g("tg-go"), r = g("tg-res"); b.disabled = true; r.className = "res"; r.textContent = "готовлю ссылку…";
      try { await tgLink(r); toast("Telegram подключён"); renderSettings(); } catch (e) { r.className = "res bad"; r.textContent = e.message; b.disabled = false; } };
    if (g("tg-off")) g("tg-off").onclick = async () => { if (!confirm("Отключить Telegram? Бот перестанет отвечать вам — и с компьютеров тоже: он один на все ваши устройства.")) return;
      try { await tgCall("dewiarUnlink"); S.tg = { linked: false }; saveS(); renderSettings(); } catch (e) { g("tg-res").className = "res bad"; g("tg-res").textContent = e.message; } };
    if (g("tg-open")) g("tg-open").onclick = () => D.openUrl("https://t.me/" + S.tg.bot);
    if (g("tg-hand")) g("tg-hand").onchange = () => { const on = g("tg-hand").checked; tgHandSet(on);
      toast(on ? "Компьютер выключен — в Telegram ответит телефон" : "Компьютер выключен — в Telegram отвечает сервер Dewiar", 2800); };
    if (g("tg-bot")) tgBotName().then(n => { const b = g("tg-bot"); if (!b) return; if (!n) { b.remove(); return; }
      b.disabled = false; b.textContent = "Открыть @" + n; b.onclick = () => D.openUrl("https://t.me/" + n); }).catch(() => { if (g("tg-bot")) g("tg-bot").remove(); });
    if (tgOn() && g("tg-card")) tgStatus().then(t => { if (!!t.linked !== !!$("#tg-off") && setTab === "telegram") renderSettings(); }).catch(() => {});
    if (g("upd-check")) g("upd-check").onclick = () => checkUpdate(true);
    if (g("news-open")) g("news-open").onclick = () => { closeSheets(); setTimeout(() => newsShow(newsList("", JSON.parse(D.info() || "{}").version || "9", true), true), 250); };
    if (g("qa-open")) g("qa-open").onclick = () => openLearn("qa");
    if (g("kids-open")) g("kids-open").onclick = () => openKids();
    if (g("work-open")) g("work-open").onclick = () => openWork("");
    if (g("course-open")) g("course-open").onclick = () => openLearn("course");
    if (g("tricks-open")) g("tricks-open").onclick = () => openTricks();
    if (g("cr-send")) g("cr-send").onclick = () => reportSend("Падение приложения", false, String(info.crash).split("\n")[0]).then(d => toast(`Отчёт №${d.id} отправлен — спасибо!`))
      .catch(e => { toast(e.message); D.share("Dewiar — ошибка:\n" + info.crash); });
    // отзыв 17.10: «непонятно, как добавить фото к жалобе» — кнопка «Добавить фото или скриншот» (галерея: свежие — первыми)
    const pickWire = () => { const f = g("bug-file"); if (f) f.onchange = async () => { const file = f.files && f.files[0]; f.value = ""; if (!file) return;
        try { bugPick = await shrinkImage(file, 1600); } catch (e) { toast(e.message); return; } g("bug-pickbox").innerHTML = bugPickHtml(); pickWire(); };
      const x = g("bug-pickx"); if (x) x.onclick = () => { bugPick = ""; g("bug-pickbox").innerHTML = bugPickHtml(); pickWire(); };
      const im = g("bug-pickimg"); if (im) im.onclick = () => imgView(bugPick); };
    if (g("bug-pickbox")) pickWire();
    if (g("rep-send")) g("rep-send").onclick = async () => { const b = g("rep-send"), r = g("rep-res"); b.disabled = true; r.className = "res"; r.textContent = "отправляю…";
      try {
        const d = await complaintSend(g("rep-note").value, g("bug-who").value, !!(g("bug-use") && g("bug-use").checked), "кнопкой",
          !g("bug-talk") || g("bug-talk").checked);
        r.className = "res ok"; r.textContent = `Жалоба №${d.id} у разработчика — спасибо! Ответ придёт сюда.`; g("rep-note").value = "";
        if (g("bug-mine")) g("bug-mine").innerHTML = complaintsHtml(); if (g("bug-img")) g("bug-img").parentNode.remove();
        if (g("bug-pickbox")) { g("bug-pickbox").innerHTML = bugPickHtml(); pickWire(); }
      } catch (e) { r.className = "res bad"; r.textContent = e.message; } finally { b.disabled = false; } };
    if (g("rep-auto")) g("rep-auto").onchange = () => { S.report = Object.assign({}, S.report, { auto: g("rep-auto").checked }); saveS(); };
    if (g("pulse-on")) g("pulse-on").onchange = () => { S.pulse = g("pulse-on").checked; saveS(); };
    if (g("bug-img")) g("bug-img").onclick = () => g("bug-img").classList.toggle("zoom");
    if (g("bug-thx")) thanksGet().then(th => { if (g("bug-thx") && th.length) g("bug-thx").innerHTML = `<div class="bugh">Помощники проекта — их жалобы сделали Dewiar лучше</div><div class="thx">`
      + th.slice(0, 30).map(p => `<span>${esc(p.name)}<b>${+p.n || 0}</b></span>`).join("") + "</div>"; }).catch(() => {});
    if (g("bug-mine") && (S.complaints || []).length) complaintsCheck().then(n => { if (n.length && g("bug-mine")) g("bug-mine").innerHTML = complaintsHtml(); }).catch(() => {});
    if (g("cr-clear")) g("cr-clear").onclick = () => { D.clearCrash(); renderSettings(); };
    if (g("reset")) g("reset").onclick = () => {                       // два вопроса подряд: случайным нажатием отношения с ассистентом не стереть
      if (!confirm(`Забыть разговор и всё, что ${persona().name} помнит о вас (${memArr().length} записей)?`)) return;
      if (!confirm("Точно? Это нельзя отменить. Память сотрётся и на компьютере после синхронизации.")) return;
      history = []; saveH(); convReset(); memArr().splice(0); saveS(); syncSoon(); toast("Забыл"); };
    if (g("wg-on")) g("wg-on").onchange = () => { try { D.widgetSet(g("wg-on").checked); } catch (e) { } renderSettings(); };
    $$("#wg-look button").forEach(b => b.onclick = () => { prefSet("widget_look", b.dataset.l); renderSettings(); toast("Значок на экране обновится сам"); });
    if (g("wg-pin")) g("wg-pin").onclick = () => { let ok = false; try { ok = D.widgetPin(); } catch (e) { }
      const r = g("wg-res"); r.className = "res" + (ok ? " ok" : ""); r.textContent = ok ? "Подтвердите на экране — и значок появится на рабочем столе" : "Добавьте вручную: долгое нажатие на рабочем столе → «Виджеты» → Dewiar"; };
    if (g("sy-open")) g("sy-open").onclick = () => { setTab = "devices"; renderSettings(); };
    if (g("sy-now")) g("sy-now").onclick = async () => { const r = g("sy-res"); r.className = "res"; r.textContent = "синхронизирую…"; await syncRun(true); renderSettings(); };
    if (g("sy-on")) g("sy-on").onchange = () => { S.sync.on = g("sy-on").checked; saveS(); if (S.sync.on) syncSoon(); renderSettings(); };
    if (g("sy-e2e")) g("sy-e2e").onchange = () => {
      const on = g("sy-e2e").checked;
      if (!on && !confirm("Выключить шифрование на этом устройстве? Свои изменения оно снова будет отправлять открытыми. На других устройствах выключите отдельно.")) { g("sy-e2e").checked = true; return; }
      e2eEnable(on); renderSettings(); };
  }
}

