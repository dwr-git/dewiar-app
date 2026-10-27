/* Студия Dewiar, «Неделя с Лирой» (27.10, по макету «Dewiar — обучение и «Команда»»): семь уроков по пять минут.
   Ядро (core/course.py): course_get, course_seen {section} (зовёт core.js при каждом переходе), course_ahead,
   course_offer {on}, course_skip, course_restart {day}; событие «course» — шаг засчитан, урок пройден. */
let CS = null;
const CS_ICON = {
  chat: "M5 6h14v9H9l-4 3.5z", play: "M7 9h10a4 4 0 0 1 3.8 5.2l-.8 2.6a2 2 0 0 1-3.4.7L14.5 15h-5l-2.1 2.5a2 2 0 0 1-3.4-.7l-.8-2.6A4 4 0 0 1 7 9z",
  near: "M12 12m-2 0a2 2 0 1 0 4 0a2 2 0 1 0-4 0 M12 12m-6 0a6 6 0 1 0 12 0a6 6 0 1 0-12 0", family: "M8 8a2.5 2.5 0 1 0 0-.1 M16 8a2.5 2.5 0 1 0 0-.1 M3 20v-2a4 4 0 0 1 4-4h2 M21 20v-2a4 4 0 0 0-4-4h-2",
  kids: "M7 10a5 5 0 0 1 10 0v4a5 5 0 0 1-10 0z M9.5 11v.1 M14.5 11v.1 M7.5 6 6 3.5 9.5 5 M16.5 6 18 3.5 14.5 5", tasks: "M6 5h12v15H6z M9 10l1.5 1.5L13 9 M9 15h6",
  folder: "M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z", connect: "M9 15l6-6 M7 11l-2 2a3 3 0 0 0 4 4l2-2 M17 13l2-2a3 3 0 0 0-4-4l-2 2",
  prompter: "M4 5h16v10H4z M8 9h8 M8 12h5 M12 15v4 M8 19h8", calendar: "M5 6h14v13H5z M5 10h14 M9 4v4 M15 4v4", notes: "M6 4h9l3 3v13H6z M9 11h6 M9 15h4",
  pay: "M6 4h12v16l-2.5-1.5L13 20l-2.5-1.5L8 20l-2-1.5z M9 9h6 M9 13h4", close: "M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z",
  personas: "M9 9a3 3 0 1 0 0-.1 M3.5 19a5.5 5.5 0 0 1 11 0 M16 8a2.5 2.5 0 1 0 0-.1 M15.5 13.5a4.5 4.5 0 0 1 5 4.5", hands: "M8 13V6a1.5 1.5 0 0 1 3 0v5 M11 11V5a1.5 1.5 0 0 1 3 0v6 M14 11V7a1.5 1.5 0 0 1 3 0v7a6 6 0 0 1-6 6h-1a6 6 0 0 1-5-2.7L3.5 14a1.5 1.5 0 0 1 2.4-1.8L8 14.5" };
function csRender() {
  const d = CS; if (!d || !Array.isArray(d.days) || !$("#p-course")) return;
  const L = d.lesson;
  $("#course-dot").classList.toggle("on", !!(L && L.open && !L.steps.some(s => s.done)));
  $("#cs-pt").innerHTML = `Пройдено <b>${d.done} из ${d.total}</b>`;
  $("#cs-fill").style.width = Math.round(d.done / d.total * 100) + "%";
  $("#cs-bar").setAttribute("aria-label", `Пройдено ${d.done} уроков из ${d.total}`);
  const st = { done: "Пройден", today: "Сегодня", next: "Впереди" };
  $("#cs-days").innerHTML = d.days.map(x => `<li class="${x.state}"><small>День ${x.day}</small><b>${escH(x.title)}</b><span>${st[x.state]}</span></li>`).join("");
  $("#cs-offer").checked = d.offer !== false;
  $("#cs-done").innerHTML = d.days.filter(x => x.state === "done").map(x => `<li><span>День ${x.day} — ${escH(x.title)}</span><button class="btn small" data-again="${x.day}">Повторить</button></li>`).join("")
    || `<li class="cs-none">Пока ни одного — начните с первого урока.</li>`;
  $("#cs-courses").innerHTML = (d.courses || []).map(c => `<button class="chip${c.id === d.course ? " on" : ""}" role="tab" aria-selected="${c.id === d.course}" data-c="${escH(c.id)}">${escH(c.title)} <small>${c.done}/${c.total}</small></button>`).join("");
  $$("#cs-courses [data-c]").forEach(b => b.onclick = () => csCall("course_pick", { id: b.dataset.c }));
  const other = (d.courses || []).filter(c => c.id !== d.course);
  $("#cs-after").innerHTML = other.map(c => `<button class="cs-oc" data-c="${escH(c.id)}"><b>${escH(c.title)}</b><small>${escH(c.sub)} · ${c.done ? `пройдено ${c.done} из ${c.total}` : `${c.total} ${plural(c.total, "урок", "урока", "уроков")}`}</small></button>`).join("")
    + `<small class="cs-soon">Скоро — «Лира для бизнеса»: команда, поручения сотрудникам в Telegram.</small>`;
  $$("#cs-after [data-c]").forEach(b => b.onclick = () => csCall("course_pick", { id: b.dataset.c }));
  const box = $("#cs-lesson");
  if (!L) {
    box.innerHTML = `<div class="cs-fin"><h2>Курс пройден</h2><p>Все уроки «${escH(d.title)}» позади. Любой урок можно повторить справа — или выберите другой курс.</p>
      <button class="btn" id="cs-restart">Пройти курс заново</button></div>`;
    $("#cs-restart").onclick = () => csCall("course_restart", {}, "Курс начат заново");
  } else {
    const icon = CS_ICON[L.icon] || CS_ICON.chat, all = L.steps.every(s => s.done);
    box.innerHTML = `<div class="cs-h"><i aria-hidden="true"><svg viewBox="0 0 24 24"><path d="${icon}"/></svg></i><div><small>${escH(d.title)} · день ${L.day} из ${d.total} · 5 минут</small><h2>${escH(L.title)}</h2></div></div>`
      + `<p class="cs-intro">${escH(L.intro)}</p>`
      + (L.open ? "" : `<p class="cs-wait">Сегодняшний урок пройден — этот откроется завтра. Не терпится? <button class="btn small" id="cs-ahead">Следующий урок сейчас</button></p>`)
      + `<ol class="cs-steps">${L.steps.map((s, i) => `<li class="${s.done ? "done" : i === L.steps.findIndex(x => !x.done) ? "now" : ""}"><span class="n">${s.done ? '<svg viewBox="0 0 24 24"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>' : i + 1}</span>`
        + `<div><b>${escH(s.say)}</b><small>${escH(s.why)}</small></div><em>${s.done ? "Сделано" : i === L.steps.findIndex(x => !x.done) ? "Ждём" : "Потом"}</em>`
        + (!s.done && s.open ? `<button class="btn small" data-open="${escH(s.open)}">Открыть</button>` : !s.done && L.open ? `<button class="cs-play" data-say="${i}" title="Отправить Лире" aria-label="Отправить Лире"><svg viewBox="0 0 24 24"><path d="M8 5.5v13l10.5-6.5z"/></svg></button>` : "")
        + `</li>`).join("")}</ol>`
      + `<div class="cs-acts">${all ? `<b class="cs-ok">Урок пройден — молодец!</b>` : `<button class="btn primary" id="cs-mic">Сказать Лире</button>`}`
      + `<span class="cs-tom">${L.tomorrow ? `Завтра: «${escH(L.tomorrow)}»` : "Это последний урок"}</span></div>`;
    if ($("#cs-ahead")) $("#cs-ahead").onclick = () => csCall("course_ahead", {}, "Открыт следующий урок");
    $$("#cs-lesson [data-open]").forEach(b => b.onclick = () => { const n = $(`nav button[data-p="${b.dataset.open}"]`); if (n) n.click(); });
    $$("#cs-lesson [data-say]").forEach(b => b.onclick = async () => {
      const s = L.steps[+b.dataset.say], phrase = s.say.replace(/^«|»$/g, "");
      b.disabled = true;
      try { await core.call("say", { text: phrase }); toast("Отправил Лире — смотрите виджет", 2500); } catch (e) { toast(e.message); }
      setTimeout(() => { b.disabled = false; }, 1500);
    });
    if ($("#cs-mic")) $("#cs-mic").onclick = () => core.call("ptt").then(() => toast("Слушаю — скажите фразу урока", 2500)).catch(e => toast(e.message));
  }
  $$("#cs-done [data-again]").forEach(b => b.onclick = () => csCall("course_restart", { day: +b.dataset.again }, "Урок можно пройти заново"));
}
async function csCall(cmd, args, ok) {
  try { CS = await core.call(cmd, args); if (ok) toast(ok, 2500); } catch (e) { toast(e.message, 4000); }
  csRender();
}
async function csLoad() { try { CS = await core.call("course_get"); } catch (e) { return; } csRender(); }
window.loadCourse = csLoad;
if ($("#p-course")) {
  $("#cs-offer").onchange = () => csCall("course_offer", { on: $("#cs-offer").checked });
  core.on("course", (e) => { CS = e; csRender(); });
  core.on("hello", () => csLoad());
}
