/* Студия Dewiar, раздел «Душа»: вкладки «Дневник», «Душа» и «Конституция» (полоска вкладок — в core.js); в конце —
   кнопки над деревом «Папки» и переход к разделу по #имени в адресе.
   Команды ядра: diary_list, diary_write_now, soul_get/save/update, const_get/save/reset, ws_open, ws_set_path;
   события diary и soul перерисовывают открытую вкладку. Тексты — Markdown-файлы (core/diary.py, core/workspace.py,
   core/soul.py); разбор ниже опирается на их заголовки — менять формат в обоих местах.
   Файлы студии подключаются по порядку из ui/settings.html и делят одну глобальную область. Переход по #разделу
   выполняется при загрузке этого файла, до связи с ядром: S ещё пуст, и обработчик клика (core.js) останавливается
   на `if (!S) return` — поэтому функции из файлов ниже (personas.js и дальше) в этот момент не вызываются. */
/* ---------- дневник ассистента ---------- */
let dDays = [], dCur = "";
const WD = ["воскресенье", "понедельник", "вторник", "среда", "четверг", "пятница", "суббота"];
const MON = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"];
const MON3 = ["янв", "фев", "мар", "апр", "мая", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"];
function dDate(iso) { const [y, m, d] = iso.split("-").map(Number); return new Date(y, m - 1, d); }
/* Имя текущей личности — из подписи под логотипом («сейчас говорит …», её пишет personas.js) */
function curName() { return ($("#bsub").textContent.match(/говорит (.+)$/) || [])[1] || "ассистент"; }
function curA() {                                   // окончание глагола прошедшего времени по полу персонажа: «узнала», «узнал»
  try { const g = (personas.find(p => p.id === active) || {}).gender; return g === "female" ? "а" : g === "male" ? "" : "(а)"; } catch (e) { return "(а)"; }
}
/* Файл дня -> записи: дневные «### 14:20 · Имя» и ночная «## 🌙 Ночью — о прожитом дне · «Название» настроение»
   с хвостом «**На завтра:**» (пишет workspace.diary_night) */
function diarySections(text) {
  const body = text.replace(/^# .*\n/, ""), out = [];
  body.split(/\n(?=### |## )/).forEach(chunk => {
    const m = chunk.match(/^(#{2,3}) (.*)\n?([\s\S]*)$/); if (!m) { if (chunk.trim()) out.push({ head: "", body: chunk }); return; }
    out.push({ night: m[1] === "##" && m[2].startsWith("🌙"), head: m[2], body: m[3] });
  });
  return out;
}
/* 28.10, владелец: «дневник и душа — возможность править или удалять»: у каждой записи — «Поправить» и «Удалить»
   (ядро: diary_entry_save {day, i, text, title}, diary_entry_delete {day, i}; i — номер в diarySections) */
let dEdit = null;
const D_ED = '<path d="M4 20h4L19 9l-4-4L4 16z"/>', D_DEL = '<path d="M5 7h14M10 11v6M14 11v6M7 7l1 13h8l1-13M9 7V4h6v3"/>';
function renderDiaryDay(day) {
  dCur = day.day; $$("#d-days .dday").forEach(x => x.classList.toggle("cur", x.dataset.d === day.day));
  const d = dDate(day.day), page = $("#d-page"), secs = diarySections(day.text);
  const acts = (k) => `<div class="dent-act"><button class="dent-b" data-ed="${k}" title="Поправить" aria-label="Поправить запись">${SVG(D_ED)}</button>`
    + `<button class="dent-b" data-del="${k}" title="Удалить" aria-label="Удалить запись">${SVG(D_DEL)}</button></div>`;
  const parts = secs.map((s, k) => {
    if (dEdit && dEdit.day === day.day && dEdit.k === k) {
      const t = s.night ? (s.head.match(/«(.+?)»/) || [])[1] || "" : null;
      return `<div class="dentry edit${s.night ? " night" : ""}"><div class="dt">${s.night ? "🌙 Ночная запись" : escH(s.head || "Запись")} — правка</div>`
        + (t !== null ? `<input type="text" id="dent-title" maxlength="80" placeholder="Название" value="${escH(t)}">` : "")
        + `<textarea id="dent-text">${escH(s.body.trim())}</textarea><div class="actions"><button class="btn primary" id="dent-save">Сохранить</button>`
        + `<button class="btn" id="dent-cancel">Отмена</button>${s.night ? `<small class="hint">«**На завтра:**» и строки «- …» под ним — выводы, которые Лира держит в голове.</small>` : ""}</div></div>`;
    }
    if (s.night) {
      const t = s.head.match(/«(.+?)»\s*(.*)$/), [main, tom] = s.body.split(/\n\*\*На завтра:\*\*\n/);
      return `<div class="dentry night">${acts(k)}<div class="dt">🌙 Ночью — о прожитом дне${day.who ? " · пишет " + escH(day.who) : ""}</div>${t ? `<h3>${escH(t[1])}<span class="mood">${escH(t[2] || "")}</span></h3>` : ""}
        ${md(main.trim())}${tom ? `<div class="tom"><b>На завтра</b>${md(tom.trim())}</div>` : ""}</div>`;
    }
    return `<div class="dentry">${acts(k)}${s.head ? `<div class="dt">${escH(s.head)}</div>` : ""}${md(s.body.trim())}</div>`;
  }).join("");
  const i = dDays.findIndex(x => x.day === day.day), older = dDays[i + 1], newer = dDays[i - 1];
  page.innerHTML = `<div class="dhead"><div class="wd">${WD[d.getDay()]}</div><h2>${d.getDate()} ${MON[d.getMonth()]} ${d.getFullYear()}</h2><div class="orn">✦ ✦ ✦</div></div>${parts}
    <div class="dnav">${older ? `<button class="btn small" data-go="${older.day}">← ${dDate(older.day).getDate()} ${MON[dDate(older.day).getMonth()]}</button>` : "<span></span>"}
    ${newer ? `<button class="btn small" data-go="${newer.day}">${dDate(newer.day).getDate()} ${MON[dDate(newer.day).getMonth()]} →</button>` : ""}</div>`;
  $$("#d-page [data-go]").forEach(b => b.onclick = () => { dEdit = null; renderDiaryDay(dDays.find(x => x.day === b.dataset.go)); $("main").scrollTo({ top: 0, behavior: "smooth" }); });
  $$("#d-page [data-ed]").forEach(b => b.onclick = () => { dEdit = { day: day.day, k: +b.dataset.ed }; renderDiaryDay(day); const t = $("#dent-text"); if (t) { t.style.height = t.scrollHeight + 8 + "px"; t.focus(); } });
  $$("#d-page [data-del]").forEach(b => b.onclick = async () => {
    const s = secs[+b.dataset.del];
    if (!await ask(s.night ? "Удалить ночную запись? Её выводы «на завтра» тоже перестанут учитываться в разговоре." : "Удалить эту запись дневника?", { ok: "Удалить", danger: true })) return;
    try { await core.call("diary_entry_delete", { day: day.day, i: +b.dataset.del }); toast("Запись удалена"); dEdit = null; loadDiary(day.day); } catch (e) { toast(e.message); }
  });
  if ($("#dent-save")) {
    $("#dent-cancel").onclick = () => { dEdit = null; renderDiaryDay(day); };
    $("#dent-text").oninput = (e) => { e.target.style.height = "auto"; e.target.style.height = e.target.scrollHeight + 8 + "px"; };
    $("#dent-save").onclick = async () => {
      const a = { day: day.day, i: dEdit.k, text: $("#dent-text").value };
      if ($("#dent-title")) a.title = $("#dent-title").value;
      try { await core.call("diary_entry_save", a); toast("Сохранено"); dEdit = null; loadDiary(day.day); } catch (e) { toast(e.message, 4000); }
    };
  }
}
async function loadDiary(focus) {
  const name = curName();
  // дневник один на всю команду: днём пишет тот, кто говорил, ночью — тот, кто был с вами (подпись — у каждой записи);
  // раньше здесь стояло имя текущего персонажа, и записи Лиры выглядели записями Патрика (16.10)
  $("#d-lead").textContent = "Общий дневник ваших помощников: что было, что узнали о вас, о чём думали. Днём — короткие мысли " +
    "после разговоров, ночью — запись о прожитом дне и выводы на завтра. У каждой записи — кто её написал.";
  try {
    const r = await core.call("diary_list");
    dDays = r.days || [];
    const ins = r.insights || {};
    $("#d-ins").innerHTML = (ins.lines || []).length ? `<h3>🌙 Что учесть сегодня — выводы ночной записи${ins.who ? " · " + escH(ins.who) : ""}</h3>`
      + `<p class="hint" style="margin:0 0 6px">Ассистент держит это в голове в разговорах до послезавтра. Неверное — уберите «×»: запись в дневнике останется.</p>`
      + `<ul>${ins.lines.map((x, k) => `<li>${escH(x)} <button class="dins-x" data-i="${k}" title="Не учитывать в разговоре" aria-label="Убрать вывод">×</button></li>`).join("")}</ul>`
      + `<button class="btn small ghost" id="dins-all">Не учитывать ни один</button>` : "";
    $$("#d-ins .dins-x").forEach(b => b.onclick = async () => { await core.call("diary_insight_drop", { i: +b.dataset.i }).catch(e => toast(e.message)); loadDiary(dCur); });
    if ($("#dins-all")) $("#dins-all").onclick = async () => { await core.call("diary_insight_drop", {}).catch(e => toast(e.message)); toast("Выводы больше не подмешиваются в разговор"); loadDiary(dCur); };
    const box = $("#d-days"); box.innerHTML = "";
    dDays.forEach(x => {
      const d = dDate(x.day), el = document.createElement("div"); el.className = "dday"; el.dataset.d = x.day;
      el.innerHTML = `<div class="dn">${d.getDate()}<small>${MON3[d.getMonth()]}</small></div><b></b><span class="dm">${WD[d.getDay()]} · ${x.count} ${x.count === 1 ? "запись" : x.count < 5 ? "записи" : "записей"}${x.night ? " · 🌙" : ""}${x.who ? " " + escH(x.who) : ""}</span><span class="dp"></span>`;
      $("b", el).textContent = (x.title ? x.title + " " : x.night ? "" : "Мысли дня ") + (x.mood || "");
      if (!x.title && x.night) $("b", el).textContent = "Ночная запись";
      $(".dp", el).textContent = x.preview || "";
      el.onclick = () => renderDiaryDay(x); box.appendChild(el);
    });
    const pick = dDays.find(x => x.day === (focus || dCur)) || dDays[0];
    if (pick) renderDiaryDay(pick);
    else { box.innerHTML = '<div class="fempty" style="padding:30px 8px">Пока пусто</div>';
      $("#d-page").innerHTML = `<div class="fempty">Дневник пока пуст.<br><span class="hint">Поговорите с ${escH(name)} — ночью появится первая запись о прожитом дне.<br>Или нажмите «Записать о сегодняшнем дне», когда за день уже было о чём поговорить.</span></div>`; }
  } catch (e) { toast(e.message); }
}
$("#d-now").onclick = async () => {
  const b = $("#d-now"), was = b.textContent; b.disabled = true; b.textContent = `${curName()} пишет…`;
  try { const r = await core.call("diary_write_now"); toast(`Записано: «${r.title || "о сегодняшнем дне"}» ${r.mood || ""}`, 5000); loadDiary(r.day); }
  catch (e) { toast(e.message, 6000); }
  finally { b.disabled = false; b.textContent = was; }
};
/* ---------- душа персонажа ----------
   sWho — чья душа открыта (у каждой личности своя); первая строка «*…обновлено…*» в файле — подпись даты обновления */
let sWho = "", sEditing = false, cEditing = false;
function soulRender(r) {
  const name = r.name, a = curA();
  $("#s-lead").textContent = `${name} — автопортрет от первого лица: кто ${a === "а" ? "она" : a === "" ? "он" : "он(а)"}, что для ${a === "а" ? "неё" : "него"} важно, что ${a === "а" ? "она" : "он"} понял${a} о вас и как меняется. `
    + `Пишет и обновляет сам${a === "а" ? "а" : ""} — раз в неделю ночью, перечитав свой дневник. Можно читать и поправить: ваши правки сохранятся.`;
  const all = [...new Set([curName(), ...(r.souls || [])])];
  $("#s-who").innerHTML = all.map(n => `<button class="chip${n === name ? " on" : ""}" data-n="${escH(n)}">${escH(n)}</button>`).join("");
  $$("#s-who .chip").forEach(c => c.onclick = () => { sWho = c.dataset.n; sEditing = false; loadSoul(); });
  const page = $("#s-page");
  if (sEditing) {
    page.innerHTML = `<textarea id="s-text"></textarea><div class="actions" style="margin-top:12px"><button class="btn primary" id="s-save">Сохранить</button><button class="btn" id="s-cancel">Отмена</button>`
      + `${r.text ? `<button class="btn danger" id="s-del" style="margin-left:auto">Стереть душу</button>` : ""}</div>`;
    if ($("#s-del")) $("#s-del").onclick = async () => {
      if (!await ask(`Стереть душу ${name}? Она вырастет заново из дневника — сама раз в неделю или по кнопке «Обновить по дневнику».`, { ok: "Стереть", danger: true })) return;
      try { await core.call("soul_delete", { persona: name }); sEditing = false; loadSoul(); toast("Душа стёрта"); } catch (e) { toast(e.message); }
    };
    $("#s-text").value = r.text || `# Душа — ${name}\n\n## Кто я\n\n## Что для меня важно\n\n## Что я понял${a} о нас\n\n## Как я меняюсь\n`;
    $("#s-save").onclick = async () => { try { soulRender(await core.call("soul_save", { persona: name, text: $("#s-text").value })); sEditing = false; loadSoul(); toast("Сохранено"); } catch (e) { toast(e.message, 5000); } };
    $("#s-cancel").onclick = () => { sEditing = false; loadSoul(); };
    $("#s-edit").textContent = "Поправить"; return;
  }
  if (!r.text) {
    page.innerHTML = `<div class="dhead"><div class="wd">душа</div><h2>${escH(name)}</h2><div class="orn">✦ ✦ ✦</div></div>
      <div class="fempty">Души пока нет — она вырастет из дневника.<br><span class="hint">${r.nights >= 1 ? `В дневнике уже ${r.nights} ночн${r.nights === 1 ? "ая запись" : r.nights < 5 ? "ые записи" : "ых записей"} — нажмите «Обновить по дневнику», и ${escH(name)} напишет первую версию.`
        : `Когда в дневнике появятся ночные записи (после разговоров, ночью или по кнопке «Записать о сегодняшнем дне»), ${escH(name)} напишет свой автопортрет.`}</span></div>`;
    return;
  }
  const body = r.text.replace(/^# .*\n/, ""), upd = (body.match(/^\s*\*([^*\n]*обновлено[^*\n]*)\*/) || [])[1] || "";
  const parts = body.replace(/^\s*\*[^*\n]*обновлено[^*\n]*\*\s*/, "").split(/\n(?=## )/).map(ch => {
    const m = ch.match(/^## (.*)\n?([\s\S]*)$/);
    return m ? `<h2>${escH(m[1])}</h2><div class="dentry">${md(m[2].trim())}</div>` : (ch.trim() ? `<div class="dentry">${md(ch.trim())}</div>` : "");
  }).join("");
  page.innerHTML = `<div class="dhead"><div class="wd">душа</div><h2>${escH(name)}</h2><div class="orn">✦ ✦ ✦</div></div>${upd ? `<div class="upd">${escH(upd)}</div>` : ""}${parts}`;
}
async function loadSoul() {
  try { const r = await core.call("soul_get", { persona: sWho || "" }); sWho = r.name; soulRender(r); } catch (e) { toast(e.message); }
}
$("#s-edit").onclick = () => { sEditing = !sEditing; loadSoul(); };
$("#s-upd").onclick = async () => {
  const b = $("#s-upd"), was = b.textContent; b.disabled = true; b.textContent = `${sWho || curName()} перечитывает дневник…`;
  try { soulRender(await core.call("soul_update", { persona: sWho || "" })); toast("Душа обновлена"); }
  catch (e) { toast(e.message, 7000); } finally { b.disabled = false; b.textContent = was; }
};
core.on("soul", () => { if ($("#p-soul").classList.contains("cur")) loadSoul(); });
/* ---------- конституция ---------- */
function constRender(r) {
  const page = $("#c-page");
  if (cEditing) {
    page.innerHTML = `<textarea id="c-text"></textarea><div class="actions" style="margin-top:12px"><button class="btn primary" id="c-save">Сохранить</button><button class="btn" id="c-cancel">Отмена</button></div>`;
    $("#c-text").value = r.text || "";
    $("#c-save").onclick = async () => { try { cEditing = false; constRender(await core.call("const_save", { text: $("#c-text").value })); toast("Конституция сохранена"); } catch (e) { cEditing = true; toast(e.message, 5000); } };
    $("#c-cancel").onclick = () => { cEditing = false; loadConst(); };
    return;
  }
  // вступление — отдельным блоком, нумерованные принципы «1. …» — следом
  const body = (r.text || "").replace(/^# .*\n/, "").trim(), [intro, ...rest] = body.split(/\n(?=\d+\.\s)/);
  page.innerHTML = `<div class="dhead"><div class="wd">принципы</div><h2>Конституция</h2><div class="orn">✦ ✦ ✦</div></div>`
    + `<div class="dentry">${md(rest.length ? intro.trim() : body)}</div>` + (rest.length ? `<div class="dentry">${md(rest.join("\n"))}</div>` : "");
}
async function loadConst() { try { constRender(await core.call("const_get")); } catch (e) { toast(e.message); } }
$("#c-edit").onclick = () => { cEditing = !cEditing; loadConst(); };
$("#c-reset").onclick = async () => { if (!await ask("Вернуть исходную конституцию? Ваши правки пропадут.")) return; cEditing = false; try { constRender(await core.call("const_reset")); toast("Вернул исходную"); } catch (e) { toast(e.message); } };
core.on("diary", e => { if ($("#p-diary").classList.contains("cur")) loadDiary(e && e.day); });
/* ---------- «Папка»: кнопки над деревом ---------- */
$("#f-open").onclick = () => core.call("ws_open", {}).catch(e => toast(e.message));
$("#f-reload").onclick = loadFolder;
$("#f-move").onclick = async () => {
  const p = await askText("Путь к папке ассистента (пусто — ~/Dewiar):", $("#f-root").textContent);
  if (p === null) return;
  try { const r = await core.call("ws_set_path", { path: p }); toast("Папка: " + r); fCur = ""; loadFolder(); } catch (e) { toast(e.message); }
};
// студия открыта на нужном разделе: ui/app.py добавляет #раздел к адресу (open_settings("calendar") и т. п.)
// после всех скриптов студии: раньше раздел «Заметки» открывался пустым — notes.js ещё не загрузился (loadNotesPage is not defined)
document.addEventListener("DOMContentLoaded", () => { if (location.hash) { const b = $(`nav button[data-p="${location.hash.slice(1)}"]`); if (b) b.click(); } });
