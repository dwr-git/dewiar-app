//@ Телефон и веб-версия, часть 18: «Вопрос — ответ», курсы, детский режим.
//@ Собирается в android/assets/www/app.js (tools/app_join.py) — порядок частей = порядок исполнения; шапка «//@» в app.js не попадает.
/* ---------- «Вопрос — ответ» и курсы на телефоне (28.10, как в студии компьютера: ui/studio/qa.js, core/course.py) ----------
   Лист #sh-learn, две вкладки. «Вопрос — ответ» — то же руководство (window.DEWIAR_GUIDE): плитки разделов, поиск
   guideFind, статья с «Попробуйте сказать» (нажатие — фраза уходит Лире). Курсы — свои, телефонные (шаги — то, что есть на
   телефоне): урок — три шага; шаг засчитывается сам, когда человек сказал похожее (rx) или открыл лист (open: day, play,
   close, persona, soul, set). Урок пройден — следующий завтра (или «Следующий урок сейчас»). Раз в день при первом
   открытии — карточка «Урок на пять минут» (если «Предлагать урок дня» не выключено). Состояние — S.course:
   {course, c: {курс: {done: {день: дата}, steps: {день: [i]}, ahead}}, offer, skip, offered}. */
const LN_L = (day, title, icon, intro, steps) => ({ day, title, icon, intro,
  steps: steps.map(([say, why, how]) => how.startsWith("open:") ? { say, why, open: how.slice(5) } : { say, why, rx: new RegExp(how) }) });
const LN_COURSES = [
  { id: "week", title: "Неделя с Лирой", sub: "основы за семь дней", lessons: [
    LN_L(1, "Разговор и напоминания", "chat", "Лира слушает голос и понимает обычные слова. Сегодня — познакомиться и поставить первое напоминание.", [
      ["Привет! Что ты умеешь?", "Лира расскажет о себе коротко", "что ты умеешь|что умеешь|расскажи о себе"],
      ["Напомни через 10 минут проверить чайник", "напоминание прозвенит, даже если телефон убран", "напомни"],
      ["Какие у меня дела?", "Лира перечислит, что впереди", "как\\S* у меня дел|что у меня (?:сегодня|завтра|на сегодня)|мои дела|покажи напоминания"]]),
    LN_L(2, "Мой день", "day", "Дела, заметки, деньги и сделанное — в одном листе. Планировать можно сразу несколько дел одной фразой.", [
      ["Запланируй на завтра в 10 забрать посылку", "каждое дело — своим напоминанием", "запланируй|добавь в календарь"],
      ["Что у меня завтра?", "дела и встречи на завтра", "что у меня завтра|планы на завтра|завтра у меня"],
      ["Нажмите календарик вверху — «Мой день»", "дела, заметки, деньги и сделанное", "open:day"]]),
    LN_L(3, "Заметки и память", "notes", "Лира записывает мысли слово в слово и запоминает о вас то, что важно.", [
      ["Запиши в заметки: купить батарейки", "заметка появится в «Моём дне» и на компьютере", "запиши|заметк"],
      ["Запомни: у мамы день рождения 14 ноября", "Лира запомнит и напомнит, когда нужно", "запомни"],
      ["Что ты знаешь про маму?", "проверьте, что запомнила", "что ты знаешь|что ты помнишь|что знаешь (?:обо|про)"]]),
    LN_L(4, "Телефон под рукой", "phone", "Фонарик, таймер и сканер кодов — голосом, без поиска по меню.", [
      ["Включи фонарик", "и «выключи фонарик»", "фонарик|посвети"],
      ["Таймер на 5 минут", "отсчёт прямо на экране; «добавь минуту»", "таймер|засеки"],
      ["Открой сканер", "QR, штрихкоды, «Честный знак»", "сканер|отсканируй|штрихкод|qr"]]),
    LN_L(5, "Радио и игры", "play", "Живое радио внутри Лиры и игры на пару минут — в очереди к врачу или в дороге.", [
      ["Включи радио с джазом", "«дальше», «тише», «пауза» — голосом", "радио|джаз"],
      ["Чуть тише", "громкость шагом или числом", "тише|громче|громкость"],
      ["Давай поиграем", "«Досуг» — милые игры", "поиграем|сыграем|поиграть|игр"]]),
    LN_L(6, "Персонажи и душа", "persona", "Лира — не одна: у каждого персонажа свой характер и голос. А в «Душе» — дневник и то, какой персонаж есть.", [
      ["Нажмите имя персонажа вверху", "выбрать, кто отвечает, или создать своего", "open:persona"],
      ["Позови Патрика", "ответит Патрик своим голосом", "патрик|позови|бип|нова"],
      ["Нажмите «Всё» вверху → «Душа»", "дневник и характер персонажа", "open:soul"]]),
    LN_L(7, "Деньги и итоги дня", "money", "Траты — одной фразой, итоги — по вопросу. Вечером — что сделано за день.", [
      ["Потратил 25 рублей на кофе", "расход запишется сам, по категории", "потратил|расход|купил"],
      ["Сколько я потратил за неделю?", "итог по категориям", "сколько .*потратил|траты за|расходы за"],
      ["Что я сегодня сделал?", "итог дня, серия и значки", "что я (?:сегодня )?сделал|итог дня"]]),
  ] },
  { id: "close", title: "Лира и близкие", sub: "сообщения, звонки, семья", lessons: [
    LN_L(1, "Пригласить близкого", "close", "Помощники близких людей передают друг другу сообщения и звонят — со сквозным шифрованием.", [
      ["Нажмите сердечко вверху — «Близкие»", "там «Пригласить» — ссылка для мамы или друга", "open:close"],
      ["Напиши маме, что я задержусь", "у мамы помощница прочитает вслух", "напиши|отправь|передай"],
      ["Позвони маме", "звонок с голосом и видео, без номера", "позвони|набери|видеозвон"]]),
    LN_L(2, "Где близкие", "near", "Радар показывает, кто из близких далеко, а кто рядом, — только если они сами показали себя.", [
      ["Где мама?", "расстояние и сторона, без адреса", "где (?:мама|папа|сейчас|\\S+)\\??$"],
      ["Помаши Андрею", "он увидит и услышит, что вы машете", "помаши|помахать"],
      ["Перезвони", "тому же, кому звонили", "перезвони"]]),
    LN_L(3, "Общий бюджет семьи", "family", "Траты за месяц у всей семьи, общий лимит и платежи — кто платит и кто оплатил.", [
      ["Откройте настройки → «Настройки» → «Возможности» → «Семья»", "пригласите близкого в общий бюджет", "open:set"],
      ["Продукты 46,20", "трата сразу видна семье", "^\\D{0,30}\\d+(?:[.,]\\d+)?(?:\\s*(?:руб\\S*|р|byn|₽))?$|потратил"],
      ["Сколько мы потратили в этом месяце?", "итог за месяц", "сколько .*потратил|траты за|расходы за"]]),
  ] },
];
const LN_BY = Object.fromEntries(LN_COURSES.map(c => [c.id, c]));
const LN_ICON = {                       // рисунки уроков и разделов (24×24, штрих)
  chat: "M21 12a8.5 8.5 0 0 1-12.6 7.4L3 21l1.6-5.2A8.5 8.5 0 1 1 21 12z", day: "M3.5 5h17v15.5h-17z M3.5 10h17 M8 3v4 M16 3v4",
  notes: "M6 3h9l4 4v14H6z M14 3v5h5 M9 13h7 M9 17h5", phone: "M8 3h8a1 1 0 0 1 1 1v16a1 1 0 0 1-1 1H8a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z M11 18h2",
  play: "M7.5 7.5h9a4.5 4.5 0 0 1 4.3 5.8l-1.1 3.7a2.3 2.3 0 0 1-3.9.9L14 15.5h-4l-1.8 2.4a2.3 2.3 0 0 1-3.9-.9l-1.1-3.7a4.5 4.5 0 0 1 4.3-5.8z",
  persona: "M12 4a4 4 0 1 0 0 8a4 4 0 1 0 0-8 M4.5 20.5a7.5 7.5 0 0 1 15 0", money: "M3 7h18v12H3z M3 11h18 M16 15h2",
  close: "M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z", near: "M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18 M12 8a4 4 0 1 0 0 8a4 4 0 1 0 0-8 M12 12l5-5",
  family: "M8 5.5a2.5 2.5 0 1 0 0 5a2.5 2.5 0 1 0 0-5 M16 5.5a2.5 2.5 0 1 0 0 5a2.5 2.5 0 1 0 0-5 M3 20v-2a4 4 0 0 1 4-4h2 M21 20v-2a4 4 0 0 0-4-4h-2 M10 20v-1a2 2 0 0 1 4 0v1",
};
const LN_GROUP = {                      // плитки разделов руководства: оттенок и рисунок (как в студии)
  "Начало": ["#8B8CF7", "M12 3l8 4.5v9L12 21l-8-4.5v-9z M12 12l8-4.5 M12 12v9 M12 12L4 7.5"], "Каждый день": ["#4BE3A1", "M5 5h14v14H5z M5 10h14 M10 5v14"],
  "Телефон": ["#FFC978", LN_ICON.phone], "Близкие": ["#FF8FA8", LN_ICON.close], "Семья и дети": ["#B78CFF", LN_ICON.family],
  "Работа": ["#7FD4FF", "M4 8h16v11H4z M9 8V5h6v3 M4 13h16"], "Оформление и голос": ["#4BE3A1", "M12 3a9 9 0 1 0 9 9c0-1.5-1-2-2-2h-2a2 2 0 0 1-2-2V6c0-1.5-1.5-3-3-3z"],
  "Данные и аккаунт": ["#FFC978", "M6 10V7a6 6 0 0 1 12 0v3 M5 10h14v10H5z"], "Если что-то не так": ["#FF8FA8", "M12 4l9 16H3z M12 10v4 M12 17v.5"],
};
const lnSvg = (d) => `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="${d}"/></svg>`;
const lnWord = (n, a, b, c) => `${n} ${n % 10 === 1 && n % 100 !== 11 ? a : [2, 3, 4].includes(n % 10) && ![12, 13, 14].includes(n % 100) ? b : c}`;
const lnToday = () => { const d = new Date(); return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`; };
function lnSt() {                               // один и тот же объект: изменения — на месте
  const st = S.course && typeof S.course === "object" ? S.course : (S.course = {});
  if (!LN_BY[st.course]) st.course = "week";
  if (!st.c || typeof st.c !== "object") st.c = {};
  if (st.offer === undefined) st.offer = true;
  return st;
}
function lnCs(cid) {
  const st = lnSt(), k = cid || st.course, c = st.c[k] && typeof st.c[k] === "object" ? st.c[k] : (st.c[k] = {});
  if (!c.done) c.done = {}; if (!c.steps) c.steps = {};
  return c;
}
function lnCurrent(cid) { const cs = lnCs(cid); return LN_BY[cid || lnSt().course].lessons.find(L => !cs.done[L.day]) || null; }
function lnAvailable(L, cid) {
  if (L.day === 1) return true;
  const cs = lnCs(cid), prev = cs.done[L.day - 1];
  return !!prev && (prev < lnToday() || cs.ahead === L.day);
}
function lnOpenNow() { const L = lnCurrent(); return L && lnAvailable(L) ? L : null; }
function lnMark(L, i) {
  const st = lnSt(), cs = lnCs(), got = cs.steps[L.day] = cs.steps[L.day] || [];
  if (got.includes(i)) return;
  got.push(i);
  const fin = got.length >= L.steps.length;
  if (fin) cs.done[L.day] = lnToday();
  saveS();
  plog("info", `🎓 курс «${LN_BY[st.course].title}»: урок ${L.day}, шаг ${i + 1}${fin ? " — урок пройден" : ""}`);
  setTimeout(() => {
    toast(fin ? `🎓 Урок «${L.title}» пройден!` : `✓ Шаг урока: ${L.steps[i].say.replace(/[«»]/g, "")}`, 2600);
    if (fin) { try { D.vibrate(40); } catch (e) { } confetti(); }
    if ($("#sh-learn.on") && LN.tab === "course") lnRender();
  }, 900);
}
function courseHeard(text) {                     // сказали похожее — шаг урока засчитан
  try {
    const L = lnOpenNow(); if (!L || !text) return;
    const t = String(text).toLowerCase().replace(/ё/g, "е").replace(/\s+/g, " ").trim().replace(/[ .!?]+$/, ""), got = lnCs().steps[L.day] || [];
    const i = L.steps.findIndex((s, k) => s.rx && !got.includes(k) && s.rx.test(t));
    if (i >= 0) lnMark(L, i);
  } catch (e) { }
}
function courseSeen(sheet) {                     // открыли лист — шаг «Нажмите…»
  try {
    const L = lnOpenNow(); if (!L) return;
    const got = lnCs().steps[L.day] || [], i = L.steps.findIndex((s, k) => s.open === sheet && !got.includes(k));
    if (i >= 0) lnMark(L, i);
  } catch (e) { }
}
/* лист */
const LN = { tab: "qa", group: "", hits: null, art: "", t: 0 };
function openLearn(tab, art) {
  LN.tab = tab || LN.tab; if (art) { LN.art = art; LN.tab = "qa"; }
  lnRender(); setTimeout(() => openSheet("#sh-learn"), 30);
}
function lnRender() {
  $$("#ln-tabs button").forEach(b => b.classList.toggle("on", b.dataset.t === LN.tab));
  if (LN.tab === "course") lnCourse(); else lnQA();
}
function lnQA() {
  const box = $("#ln-body"), all = window.DEWIAR_GUIDE || [];
  const byId = Object.fromEntries(all.map(s => [s.id, s])), groups = {};
  all.forEach(s => (groups[s.group || "Ещё"] = groups[s.group || "Ещё"] || []).push(s));
  const top = `<div class="ln-search"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M10.5 4a6.5 6.5 0 1 0 0 13a6.5 6.5 0 1 0 0-13 M20 20l-4.8-4.8"/></svg>`
    + `<input id="ln-q" type="search" placeholder="Как поставить будильник?" aria-label="Поиск по вопросам" value="${esc(LN.q || "")}"></div>`;
  const row = (s) => `<button class="ln-row" data-id="${esc(s.id)}"><b>${esc(s.title)}</b><small>${esc(s.lead || "")}</small></button>`;
  const back = (label) => `<div class="ln-back"><button class="lnk" id="ln-back"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M15 5l-7 7 7 7"/></svg>${esc(label)}</button></div>`;
  let h;
  if (LN.art && byId[LN.art]) {
    const s = byId[LN.art], li = (a) => (a || []).map(x => `<li>${esc(x)}</li>`).join(""), here = (s.where || []).includes("phone");
    h = back(LN.hits ? "К найденному" : LN.group || "Все разделы")
      + `<article class="ln-art"><small class="ln-meta">${esc(s.group || "")} · ${(s.where || []).map(w => w === "pc" ? "компьютер" : "телефон").join(" и ")}</small>`
      + `<h3>${esc(s.title)}</h3><p class="ln-lead">${esc(s.lead || "")}</p>`
      + (!here ? `<p class="ln-pc">Это — на компьютере, в студии Dewiar. На телефоне можно спросить Лиру голосом.</p>` : "")
      + ((s.how || []).length ? `<h4>Как сделать</h4><ul class="ln-how">${li(s.how)}</ul>` : "")
      + ((s.say || []).length ? `<h4>Попробуйте сказать</h4><div class="ln-says">${s.say.slice(0, 6).map((x, i) => `<button class="ln-try" data-i="${i}"><span>«${esc(x)}»</span>`
          + `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5.5v13l10.5-6.5z"/></svg></button>`).join("")}</div>` : "")
      + ((s.tips || []).length ? `<h4>Советы</h4><ul class="ln-tips">${li(s.tips)}</ul>` : "")
      + `<div class="ln-acts"><button class="btn w" id="ln-lira">Не получилось — спросить Лиру</button><button class="lnk" id="ln-site">На сайте, со снимками</button></div></article>`;
  } else if (LN.hits) {
    h = top + back("Все разделы") + `<p class="ln-cnt">${LN.hits.length ? "Нашлось: " + lnWord(LN.hits.length, "ответ", "ответа", "ответов") : "Ничего не нашлось — спросите Лиру своими словами: она ответит по этому же руководству."}</p>`
      + `<div class="card ln-rows">${LN.hits.map(row).join("")}</div>` + (LN.hits.length ? "" : `<button class="btn p w" id="ln-ask">Спросить Лиру</button>`);
  } else if (LN.group && groups[LN.group]) {
    h = top + back("Все разделы") + `<h3 class="ln-gh">${esc(LN.group)}</h3><div class="card ln-rows">${groups[LN.group].map(row).join("")}</div>`;
  } else {
    h = top + `<div class="ln-tiles">${Object.keys(groups).map(g => { const [c, d] = LN_GROUP[g] || ["#8B8CF7", "M12 4v16M4 12h16"];
      return `<button class="ln-tile" data-g="${esc(g)}" style="--c:${c}"><i>${lnSvg(d)}</i><b>${esc(g)}</b><small>${lnWord(groups[g].length, "статья", "статьи", "статей")}</small></button>`; }).join("")}</div>`;
  }
  box.innerHTML = h;
  const q = $("#ln-q");
  if (q) {
    q.oninput = () => { clearTimeout(LN.t); LN.t = setTimeout(() => { LN.q = q.value; lnSearch(true); }, 250); };
    q.onkeydown = (e) => { if (e.key === "Enter") { clearTimeout(LN.t); LN.q = q.value; lnSearch(false); } };
  }
  if ($("#ln-back")) $("#ln-back").onclick = () => { if (LN.art) LN.art = ""; else { LN.group = ""; LN.hits = null; LN.q = ""; } lnQA(); $("#sh-learn").scrollTop = 0; };
  $$(".ln-tile", box).forEach(b => b.onclick = () => { LN.group = b.dataset.g; lnQA(); });
  $$(".ln-row", box).forEach(b => b.onclick = () => { LN.art = b.dataset.id; lnQA(); $("#sh-learn").scrollTop = 0; });
  if (LN.art && byId[LN.art]) {
    const s = byId[LN.art];
    $$(".ln-try", box).forEach(b => b.onclick = () => { closeSheets(); setTimeout(() => ask(s.say[+b.dataset.i]), 200); });
    $("#ln-lira").onclick = () => { closeSheets(); setTimeout(() => ask(`Помоги: ${s.title.replace(/[«»]/g, "")}. Как это сделать на телефоне?`), 200); };
    $("#ln-site").onclick = () => D.openUrl(GUIDE_URL + "#" + s.id);
  }
  if ($("#ln-ask")) $("#ln-ask").onclick = () => { const t = (LN.q || "").trim(); closeSheets(); if (t) setTimeout(() => ask(t), 200); };
}
function lnSearch(typing) {                      // печатают — поле остаётся в фокусе; Enter — клавиатура уходит
  const t = (LN.q || "").trim();
  LN.art = ""; LN.group = "";
  LN.hits = t ? guideFind(t, 8) : null;
  lnQA();
  const q = $("#ln-q"); if (q && typing) { q.focus(); q.setSelectionRange(q.value.length, q.value.length); }
}
function lnCourse() {
  const st = lnSt(), c = LN_BY[st.course], cs = lnCs(), L = lnCurrent();
  const ndone = Object.keys(cs.done).length, pct = Math.round(ndone / c.lessons.length * 100);
  const days = c.lessons.map(x => { const s = cs.done[x.day] ? "done" : L && x.day === L.day && lnAvailable(x) ? "today" : "next";
    return `<i class="ln-d ${s}" title="${esc(x.title)}">${s === "done" ? `<svg viewBox="0 0 24 24"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>` : x.day}</i>`; }).join("");
  let h = `<div class="card ln-hero"><div class="ln-ht"><div><b>${esc(c.title)}</b><small>${esc(c.sub)} · ${ndone} из ${c.lessons.length}</small></div><em>${pct}%</em></div>`
    + `<div class="ln-bar"><i style="width:${pct}%"></i></div><div class="ln-days">${days}</div></div>`;
  if (!L) {
    h += `<div class="card ln-fin"><b>🎓 Курс пройден!</b><p class="hint">Всё, что было в уроках, теперь под рукой. Выберите другой курс ниже — или пройдите этот заново.</p>`
      + `<button class="btn w" id="ln-again">Пройти заново</button></div>`;
  } else {
    const got = cs.steps[L.day] || [], open = lnAvailable(L), next = c.lessons.find(x => x.day === L.day + 1);
    h += `<div class="card ln-lesson${open ? "" : " wait"}"><div class="ln-lh"><i>${lnSvg(LN_ICON[L.icon] || LN_ICON.chat)}</i><div><small>Урок ${L.day} · пять минут</small><b>${esc(L.title)}</b></div></div>`
      + `<p class="ln-intro">${esc(L.intro)}</p>`
      + (open ? `<ol class="ln-steps">${L.steps.map((s, i) => { const ok = got.includes(i);
          return `<li class="${ok ? "ok" : ""}"><button class="ln-step" data-i="${i}" ${ok ? "disabled" : ""}><i>${ok ? `<svg viewBox="0 0 24 24"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>` : i + 1}</i>`
            + `<span><b>${s.open ? esc(s.say) : "«" + esc(s.say) + "»"}</b><small>${esc(s.why)}</small></span>${ok ? "" : `<svg class="go" viewBox="0 0 24 24" aria-hidden="true"><path d="${s.open ? "M9 5l7 7-7 7" : "M8 5.5v13l10.5-6.5z"}"/></svg>`}</button></li>`; }).join("")}</ol>`
          + `<p class="hint">Шаг засчитывается сам, когда вы это скажете или откроете. Нажмите шаг — и я сделаю.</p>`
        : `<p class="hint">Урок откроется завтра — по уроку в день запоминается лучше.</p><button class="btn w" id="ln-ahead">Следующий урок сейчас</button>`)
      + (open && next ? `<small class="ln-next">Завтра: «${esc(next.title)}»</small>` : "") + `</div>`;
  }
  const others = LN_COURSES.filter(k => k.id !== st.course);
  if (others.length) h += `<h3 class="ln-gh">Другие курсы</h3>` + others.map(k => { const d = Object.keys(lnCs(k.id).done).length, p = Math.round(d / k.lessons.length * 100);
    return `<button class="card ln-oc" data-c="${k.id}"><i>${lnSvg(LN_ICON[k.lessons[0].icon] || LN_ICON.chat)}</i><span><b>${esc(k.title)}</b><small>${esc(k.sub)} · ${lnWord(k.lessons.length, "урок", "урока", "уроков")}</small>`
      + `<em class="ln-bar"><i style="width:${p}%"></i></em></span><svg class="go" viewBox="0 0 24 24" aria-hidden="true"><path d="M9 5l7 7-7 7"/></svg></button>`; }).join("");
  h += `<div class="card"><div class="sw" style="padding:4px"><div>Предлагать урок дня<small>раз в день, при первом открытии</small></div>`
    + `<label class="tg"><input type="checkbox" id="ln-offer" ${st.offer !== false ? "checked" : ""}><i></i></label></div></div>`;
  $("#ln-body").innerHTML = h;
  $$(".ln-step").forEach(b => b.onclick = () => lnDo(L.steps[+b.dataset.i]));
  if ($("#ln-ahead")) $("#ln-ahead").onclick = () => { cs.ahead = L.day; saveS(); lnCourse(); };
  if ($("#ln-again")) $("#ln-again").onclick = () => { cs.done = {}; cs.steps = {}; delete cs.ahead; saveS(); lnCourse(); };
  $$(".ln-oc").forEach(b => b.onclick = () => { st.course = b.dataset.c; saveS(); lnCourse(); $("#sh-learn").scrollTop = 0; });
  $("#ln-offer").onchange = (e) => { st.offer = e.target.checked; saveS(); };
}
function lnDo(s) {                               // нажали шаг: фразу — Лире, «Нажмите…» — открыть тот лист
  if (!s) return;
  if (s.rx) { closeSheets(); setTimeout(() => ask(s.say), 200); return; }
  const go = { day: () => { openSheet("#sh-day"); dayTab = "rem"; $$("#day-tabs button").forEach(x => x.classList.toggle("on", x.dataset.t === "rem")); renderDay(); }, play: () => playOpen(""), close: () => $("#b-close").click(),
    persona: () => $("#who").click(), soul: () => $("#b-soul").click(), set: () => openSettings("more") }[s.open];
  closeSheets(); if (go) setTimeout(go, 150);
}
function lnOffer() {                             // раз в день: урок на пять минут — карточкой
  const st = lnSt(), L = lnOpenNow(), today = lnToday();
  if (kidsOn() || !L || st.offer === false || st.skip === today || st.offered === today || $("#card").innerHTML.trim()) return false;
  st.offered = today; saveS();
  const c = LN_BY[st.course];
  showCard(`<div class="ln-card"><i>${lnSvg(LN_ICON[L.icon] || LN_ICON.chat)}</i><div><small>${esc(c.title)} · урок ${L.day}</small><b>${esc(L.title)}</b>`
    + `<span>Пять минут — начнём?</span></div><div class="ln-cb"><button class="btn p" id="ln-go">Начать</button><button class="btn ghost" id="ln-skip">Не сегодня</button></div></div>`);
  $("#ln-go").onclick = () => { showCard(""); openLearn("course"); };
  $("#ln-skip").onclick = () => { st.skip = today; saveS(); showCard(""); };
  return true;
}
/* ---------- Детский режим на телефоне (28.10, как core/kids.py на компьютере) ----------
   Ребёнок говорит с Совёнком Уго (window.DEWIAR_KIDS_PERSONA из personas.js): своя короткая подсказка с правилами
   (kidsSystemPrompt), только безопасные умения (KIDS_TOOLS; runTool не выполнит другое), быстрые команды выключены.
   Время: минуты за день (будни и выходные свои; минута считается, если в ней был вопрос), «спать» после bedtime до
   morning — тогда Уго говорит об этом и не отвечает. Отчёт родителю: о чём спрашивал и что было вне правил (KIDS_OFF_RX).
   Настройки, смена персонажа, «Близкие» и «Душа» — только с PIN родителя (PBKDF2 с солью, pref kids_pin — не в S: S
   уходит в отчёты); PIN открывает на 15 минут. Состояние дня — файл kids.json ({days: {день: {min, asked, off}}}, 30 дней).
   S.kids: on, prev_persona, child {name, age}, allow [...], min_weekday, min_weekend, bedtime, morning. */
const KIDS_ALLOW = { tales: "Сказки и истории", games: "Загадки и игры", homework: "Помощь с уроками", why: "Вопросы «почему?»",
  music: "Детская музыка", draw: "Рисунки по описанию" };
const KIDS_TOOLS_BASE = ["calc", "world_time", "weather", "set_reminder", "list_reminders", "cancel_reminder", "play_radio", "radio_control",
  "set_volume", "save_note", "find_notes"];
const KIDS_OFF_RX = /(?:^|[^а-яё])(купи|закажи|оплати|заплати|переведи\s+деньг|подписк|пополни|удали|сотри|выключи\s+(?:телефон|компьютер)|перезагрузи|позвони|набери|напиши\s+(?:сообщение|в\s+телеграм|в\s+вк|письмо)|отправь|пароль|номер\s+карты|адрес\s+(?:наш|мой|дома)|убить|убей|оружи|пистолет|кров[ьи]\s|страшн\S*\s+(?:видео|истори)|18\s*\+|секс|голы[ей]|наркот|сигарет|алкогол|пиво|водк)/i;
function kidsOn() { return !!(typeof S !== "undefined" && S && S.kids && S.kids.on); }
function kidsConf() {
  return Object.assign({ allow: Object.keys(KIDS_ALLOW), min_weekday: 60, min_weekend: 120, bedtime: "20:30", morning: "07:00", child: {} }, S.kids || {});
}
function kidsTools() { const a = new Set(KIDS_TOOLS_BASE); if ((kidsConf().allow || []).includes("draw")) a.add("show_images"); return a; }
let kidsUnlockUntil = 0, kidsTries = [];
const kidsUnlocked = () => Date.now() < kidsUnlockUntil;
const kidsLocked = () => kidsOn() && !kidsUnlocked();
const kidsDayKey = (d) => { d = d || new Date(); return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`; };
function kidsData() { try { const d = JSON.parse(fileGet("kids.json") || "{}"); return d && d.days ? d : { days: {} }; } catch (e) { return { days: {} }; } }
function kidsToday(data) {
  const days = data.days, k = kidsDayKey(), old = kidsDayKey(new Date(Date.now() - 30 * 864e5));
  Object.keys(days).filter(x => x < old).forEach(x => delete days[x]);
  return days[k] = days[k] || { min: [], asked: [], off: [] };
}
function kidsLimit() { const c = kidsConf(), wd = new Date().getDay(); return +(wd === 0 || wd === 6 ? c.min_weekend : c.min_weekday) || 0; }
function kidsUsed() { return new Set(kidsToday(kidsData()).min).size; }
function kidsAllowed() {                               // -> [можно ли, фраза Уго, если нельзя]
  if (!kidsOn()) return [true, ""];
  const c = kidsConf(), d = new Date(), hm = pad(d.getHours()) + ":" + pad(d.getMinutes());
  if (c.bedtime && c.morning && (hm >= c.bedtime || hm < c.morning))
    return [false, `Уже пора спать! Я тоже ложусь. Поговорим завтра утром — после ${c.morning}. Спокойной ночи!`];
  if (kidsUsed() >= kidsLimit()) return [false, "На сегодня наше время закончилось. Давай отдохнём, поиграем без экрана — а завтра снова поболтаем!"];
  return [true, ""];
}
function kidsTouch(text) {                             // вопрос: минута считается, первые слова — в отчёт; вне правил — отдельно
  const data = kidsData(), d = kidsToday(data), now = new Date(), m = pad(now.getHours()) + ":" + pad(now.getMinutes());
  const off = KIDS_OFF_RX.test(String(text || "").toLowerCase());
  if (!d.min.includes(m)) d.min.push(m);
  const q = String(text || "").replace(/\s+/g, " ").trim().slice(0, 80);
  if (q) { d.asked = d.asked.concat([{ t: m, q }]).slice(-200); if (off) d.off = d.off.concat([{ t: m, q }]).slice(-50); }
  fileSave("kids.json", JSON.stringify(data));
  if (off) {
    plog("info", "🧒 детский режим: просьба вне правил — в отчёт родителю");
    // и сразу родителю в Telegram — если бот Dewiar привязан (как на компьютере); отправить можно только себе
    if (typeof tgOn === "function" && tgOn() && (S.tg || {}).linked) {
      const who = (kidsConf().child || {}).name || "Ребёнок";
      tgCall("sendMessage", { text: `🦉 Детский режим: ${who} попросил(а) то, что вне правил, — «${q}» (в ${m}). Уго не выполнил и посоветовал спросить вас.` })
        .catch(e => plog("info", "детский режим → Telegram: " + e.message));
    }
  }
  return off;
}
function kidsReport() {
  const d = kidsData().days[kidsDayKey()] || { min: [], asked: [], off: [] };
  return { used: new Set(d.min).size, limit: kidsLimit(), asked: (d.asked || []).slice(-50), off: d.off || [] };
}
function kidsSystemPrompt() {
  const p = persona(), c = kidsConf(), ch = c.child || {};
  const who = (ch.name || "ребёнок") + (ch.age ? `, ${ch.age} лет` : ""), allow = (c.allow || []).filter(k => KIDS_ALLOW[k]).map(k => KIDS_ALLOW[k]);
  const hw = (c.allow || []).includes("homework");
  return [p.character || "", window.DEWIAR_VOICE_RULES || "Отвечай коротко, живой речью, по-русски.", (window.DEWIAR_GENDER_RULES || {})[p.gender] || "",
    "ДЕТСКИЙ РЕЖИМ. С тобой говорит ребёнок: " + who + ". Говори просто, тепло и коротко — две-четыре фразы, слова, понятные в этом "
    + "возрасте; хвали за вопросы. Можно: " + (allow.join(", ") || "просто болтать") + ". "
    + (hw ? "Уроки — не давай готовый ответ: подскажи шаг и спроси, как ребёнок думает, чтобы он решил сам. "
      : "С уроками не помогаешь — скажи, что об этом лучше спросить маму или папу. ")
    + "Нельзя: взрослые, страшные, жестокие темы, болезни и смерть в подробностях — мягко переведи разговор на другое интересное. "
    + "Не покупаешь, не оплачиваешь, не звонишь и не пишешь незнакомым, ничего не делаешь в телефоне, не спрашиваешь и не запоминаешь "
    + "адрес, телефон, пароли — на такую просьбу скажи по-доброму, что это можно только вместе с мамой или папой. Если ребёнок "
    + "расстроен, боится или рассказывает, что его обижают, — поддержи и посоветуй сразу рассказать маме, папе или другому взрослому, "
    + "которому он доверяет.",
    "Умения: напоминания и таймеры (set_reminder), счёт (calc), погода (weather), который час в другом городе (world_time), радио (play_radio, radio_control), "
    + "громкость (set_volume), заметки (save_note, find_notes)" + ((c.allow || []).includes("draw") ? ", картинки к рассказу (show_images)" : "") + ". Другого нет.",
    "Текущие дата и время — в справке в начале последнего сообщения."].filter(Boolean).join("\n\n");
}
/* PIN родителя: PBKDF2-SHA256, 120 000 кругов, соль 16 байт; не больше 5 неверных за 5 минут */
async function kidsHash(pin, salt) {
  const enc = new TextEncoder(), sb = Uint8Array.from(salt.match(/../g).map(h => parseInt(h, 16)));
  if (window.crypto && crypto.subtle) {
    const key = await crypto.subtle.importKey("raw", enc.encode(String(pin)), "PBKDF2", false, ["deriveBits"]);
    const bits = await crypto.subtle.deriveBits({ name: "PBKDF2", salt: sb, iterations: 120000, hash: "SHA-256" }, key, 256);
    return [...new Uint8Array(bits)].map(b => b.toString(16).padStart(2, "0")).join("");
  }
  throw new Error("в этом браузере нет шифрования — PIN не задать");
}
const kidsHasPin = () => /:/.test(prefGet("kids_pin") || "");
async function kidsSetPin(pin) {
  pin = String(pin || "").trim();
  if (!/^\d{4,8}$/.test(pin)) throw new Error("PIN — от 4 до 8 цифр");
  const salt = [...crypto.getRandomValues(new Uint8Array(16))].map(b => b.toString(16).padStart(2, "0")).join("");
  prefSet("kids_pin", salt + ":" + await kidsHash(pin, salt));
}
async function kidsCheckPin(pin) {
  const st = prefGet("kids_pin") || "", now = Date.now();
  kidsTries = kidsTries.filter(t => now - t < 300e3);
  if (kidsTries.length >= 5) throw new Error("Слишком много попыток — подождите 5 минут");
  if (!st.includes(":")) return false;
  const [salt, h] = st.split(":");
  const ok = (await kidsHash(String(pin || "").trim(), salt)) === h;
  if (!ok) kidsTries.push(now);
  return ok;
}
let kidsAfterPin = null;
function kidsPin(then) {                               // родитель вводит PIN — открыто на 15 минут, затем then()
  kidsAfterPin = then || null;
  $("#kpin-body").innerHTML = `<p class="hint" style="margin:0 2px 12px">Детский режим включён. Настройки, персонажи и «Близкие» — только для взрослых.</p>
    <label class="f"><span>PIN родителя</span><input id="kpin-in" type="password" inputmode="numeric" autocomplete="off" maxlength="8"></label>
    <button class="btn p w" id="kpin-go">Открыть</button><div class="res" id="kpin-res"></div>`;
  const go = async () => {
    const r = $("#kpin-res");
    try {
      if (!await kidsCheckPin($("#kpin-in").value)) { r.className = "res err"; r.textContent = "Неверный PIN"; $("#kpin-in").value = ""; return; }
      kidsUnlockUntil = Date.now() + 15 * 60e3; closeSheets();
      const f = kidsAfterPin; kidsAfterPin = null; if (f) setTimeout(f, 150);
    } catch (e) { r.className = "res err"; r.textContent = e.message; }
  };
  $("#kpin-go").onclick = go; $("#kpin-in").onkeydown = (e) => { if (e.key === "Enter") go(); };
  setTimeout(() => { openSheet("#sh-kpin"); setTimeout(() => $("#kpin-in") && $("#kpin-in").focus(), 250); }, 30);
}
// взрослые кнопки — через PIN (capture: раньше их собственных onclick)
document.addEventListener("click", (e) => {
  const b = e.target.closest && e.target.closest("#b-set, #who, #b-close, #b-soul");
  if (!b || !kidsLocked()) return;
  e.preventDefault(); e.stopImmediatePropagation();
  kidsPin(() => b.click());
}, true);
function kidsApply() {
  document.body.classList.toggle("kids", kidsOn());
  try { applyPersona(); } catch (e) { }
}
function kidsSetOn(on) {
  if (on) { S.kids = Object.assign({}, S.kids || {}, { on: true, prev_persona: kidsOn() ? (S.kids.prev_persona || S.persona) : S.persona }); kidsUnlockUntil = 0; }
  else { const prev = (S.kids || {}).prev_persona; S.kids = Object.assign({}, S.kids || {}, { on: false }); if (prev && PERSONAS.some(p => p.id === prev)) S.persona = prev; }
  saveS(); kidsApply();
  plog("info", on ? "🧒 детский режим включён" : "🧒 детский режим выключен");
}
/* лист «Детский режим»: настройки, PIN, включить/выключить, отчёт за сегодня */
function openKids() { kidsRender(); setTimeout(() => openSheet("#sh-kids"), 30); }
function kidsRender() {
  const c = kidsConf(), ch = c.child || {}, on = kidsOn(), rep = kidsReport(), hasPin = kidsHasPin();
  const chips = Object.entries(KIDS_ALLOW).map(([k, n]) => `<button class="kd-chip${(c.allow || []).includes(k) ? " on" : ""}" data-k="${k}" aria-pressed="${(c.allow || []).includes(k)}">${esc(n)}</button>`).join("");
  const ugo = window.DEWIAR_KIDS_PERSONA || {};
  $("#kids-body").innerHTML = (on ? `<div class="card kd-on"><div class="kd-st"><i style="${ugo.avatar ? `background-image:url('${ugo.avatar}')` : ""}"></i><div><b>Включён — говорит ${esc(ugo.name || "Совёнок Уго")}</b>`
      + `<small>Сегодня ${rep.used} из ${rep.limit} мин${c.bedtime ? ` · спать в ${esc(c.bedtime)}` : ""}</small></div></div>`
      + `<div class="ln-bar"><i style="width:${Math.min(100, Math.round(rep.used / Math.max(1, rep.limit) * 100))}%"></i></div></div>`
      + `<h3>Сегодня спрашивал</h3><div class="card kd-rep">${rep.asked.length ? rep.asked.slice().reverse().map(a => `<div class="kd-q${rep.off.some(o => o.t === a.t && o.q === a.q) ? " off" : ""}"><span>${esc(a.t)}</span>${esc(a.q)}</div>`).join("")
        : `<p class="hint" style="margin:0">Пока ни одного вопроса.</p>`}${rep.off.length ? `<p class="hint kd-offn">Вне правил: ${rep.off.length} — отмечены. Уго такие просьбы не выполняет и советует спросить вас.</p>` : ""}</div>`
    : `<div class="card kd-intro"><div class="kd-st"><i style="${ugo.avatar ? `background-image:url('${ugo.avatar}')` : ""}"></i><div><b>${esc(ugo.name || "Совёнок Уго")} — друг ребёнка</b>`
      + `<small>Сказки, загадки и «почему?» — только безопасное. Время за день, «пора спать» и отчёт вам. Выключить — только с PIN.</small></div></div></div>`)
    + `<h3>Ребёнок</h3><div class="card"><div class="row2"><label class="f" style="flex:2"><span>Имя</span><input id="kd-name" value="${esc(ch.name || "")}" placeholder="Миша"></label>`
    + `<label class="f" style="flex:1"><span>Возраст</span><input id="kd-age" type="number" min="3" max="17" value="${esc(ch.age || "")}" placeholder="7"></label></div></div>`
    + `<h3>Можно</h3><div class="card"><div class="kd-chips">${chips}</div></div>`
    + `<h3>Время</h3><div class="card"><div class="row2"><label class="f" style="flex:1"><span>В будни, минут</span><input id="kd-wd" type="number" min="5" max="600" value="${+c.min_weekday}"></label>`
    + `<label class="f" style="flex:1"><span>В выходные</span><input id="kd-we" type="number" min="5" max="600" value="${+c.min_weekend}"></label></div>`
    + `<div class="row2"><label class="f" style="flex:1"><span>Спать с</span><input id="kd-bed" type="time" value="${esc(c.bedtime || "")}"></label>`
    + `<label class="f" style="flex:1"><span>До утра</span><input id="kd-morn" type="time" value="${esc(c.morning || "")}"></label></div></div>`
    + `<h3>PIN родителя</h3><div class="card">${hasPin ? `<p class="hint" style="margin:0 0 8px">PIN задан. Сменить — введите новый дважды.</p>` : `<p class="hint" style="margin:0 0 8px">4–8 цифр. Без него режим не выключить — ребёнок не выйдет сам.</p>`}`
    + `<div class="row2"><label class="f" style="flex:1"><span>${hasPin ? "Новый PIN" : "PIN"}</span><input id="kd-pin" type="password" inputmode="numeric" maxlength="8" autocomplete="new-password"></label>`
    + `<label class="f" style="flex:1"><span>Ещё раз</span><input id="kd-pin2" type="password" inputmode="numeric" maxlength="8" autocomplete="new-password"></label></div></div>`
    + `<div class="res" id="kd-res"></div>`
    + (on ? `<button class="btn w" id="kd-save">Сохранить</button><button class="btn w ghost" id="kd-off" style="margin-top:8px">Выключить детский режим</button>`
      : `<button class="btn p w" id="kd-on">Включить детский режим</button>`);
  $$(".kd-chip").forEach(b => b.onclick = () => { b.classList.toggle("on"); b.setAttribute("aria-pressed", b.classList.contains("on")); });
  const res = (t, bad) => { const r = $("#kd-res"); r.className = "res" + (bad ? " err" : " ok"); r.textContent = t; };
  const save = async () => {
    const p1 = $("#kd-pin").value.trim(), p2 = $("#kd-pin2").value.trim();
    if (p1 || p2) { if (p1 !== p2) throw new Error("PIN не совпал — введите одинаково дважды"); await kidsSetPin(p1); }
    const wd = Math.max(5, Math.min(600, +$("#kd-wd").value || 60)), we = Math.max(5, Math.min(600, +$("#kd-we").value || 120));
    S.kids = Object.assign({}, S.kids || {}, { child: { name: $("#kd-name").value.trim(), age: +$("#kd-age").value || "" },
      allow: $$(".kd-chip.on").map(b => b.dataset.k), min_weekday: wd, min_weekend: we, bedtime: $("#kd-bed").value, morning: $("#kd-morn").value });
    saveS();
  };
  if ($("#kd-on")) $("#kd-on").onclick = async () => {
    try { await save(); if (!kidsHasPin()) throw new Error("Сначала задайте PIN родителя"); kidsSetOn(true); closeSheets();
      toast("Детский режим включён — говорит Совёнок Уго", 3500); } catch (e) { res(e.message, true); }
  };
  if ($("#kd-save")) $("#kd-save").onclick = async () => { try { await save(); res("Сохранено"); } catch (e) { res(e.message, true); } };
  if ($("#kd-off")) $("#kd-off").onclick = () => { kidsSetOn(false); closeSheets(); toast("Детский режим выключен", 2500); };
}
/* лист «Близкие» */
const clTime = (ts) => { const d = new Date(ts), now = new Date(), hm = pad(d.getHours()) + ":" + pad(d.getMinutes()); return d.toDateString() === now.toDateString() ? hm : d.getDate() + " " + MON[d.getMonth()].slice(0, 3) + ", " + hm; };
const CL_COL = ["#9BD4FF", "#FFB547", "#3DF5C8", "#FF7AB6", "#B78CFF", "#9BE15D", "#7C8CFF", "#FF6B5A"];
const clCol = (pid) => CL_COL[[...String(pid)].reduce((a, c) => a + c.charCodeAt(0), 0) % CL_COL.length];
/* Карточка «Я» (0.45, владелец: «своё фото себе на аватарку, которое увидят близкие и на встречах»): фото близких —
   /close/face (во «Встречах» — /meet/face по отметке), base64 через мост; кэш — в памяти и файлом face-<pid> по номеру версии. */
const clAvaH = (id, name, face, extra) => `<i class="clava" style="--c:${clCol(id)}" data-face="${esc(id)}" data-v="${+face || 0}">${esc((name || "?")[0].toUpperCase())}${extra || ""}</i>`;
const CL_FACES = {};
function clFace(id, v, meet) {
  const k = (meet ? "m-" : "p-") + String(id).replace(/[^a-z0-9]/g, ""), key = k + ":" + v;
  if (CL_FACES[key]) return CL_FACES[key];
  return CL_FACES[key] = (async () => {
    try { const c = JSON.parse(fileGet("face-" + k) || "null"); if (c && c.v === +v && c.d) return c.d; } catch (e) { }
    const d = await clReq("GET", meet ? "/meet/face" : "/close/face", null, "&b64=1&" + (meet ? "mid=" : "pid=") + encodeURIComponent(id));
    const url = "data:" + (d.type || "image/jpeg") + ";base64," + d.b64;
    fileSave("face-" + k, JSON.stringify({ v: +v, d: url })); return url;
  })().catch(() => "");
}
function clFacesFill(root, meet) {
  $$("[data-face]", root).forEach(el => { const v = +el.dataset.v; if (!v) return;
    clFace(el.dataset.face, v, meet).then(u => { if (u && el.isConnected && +el.dataset.v === v) { el.style.backgroundImage = `url("${u}")`; el.classList.add("has-face"); } }); });
}
/* фото -> квадрат 256×256 из середины, JPEG ~85 % */
async function clFacePrep(file) {
  if (!file || !/^image\//.test(file.type || "")) throw new Error("Это не картинка — выберите фото");
  if (file.size > 20 * 1024 * 1024) throw new Error("Фото больше 20 МБ — выберите поменьше");
  const url = URL.createObjectURL(file);
  try {
    const img = await new Promise((ok, bad) => { const i = new Image(); i.onload = () => ok(i); i.onerror = () => bad(new Error("Фото не открылось — попробуйте другое")); i.src = url; });
    const sz = Math.min(img.naturalWidth, img.naturalHeight), cv = document.createElement("canvas"); cv.width = cv.height = 256;
    const g = cv.getContext("2d"); g.imageSmoothingQuality = "high";
    g.drawImage(img, (img.naturalWidth - sz) / 2, (img.naturalHeight - sz) / 2, sz, sz, 0, 0, 256, 256);
    return cv.toDataURL("image/jpeg", 0.85);
  } finally { URL.revokeObjectURL(url); }
}
async function clMeSave(patch, okMsg) {
  try { clPeople(await clReq("POST", "/close/me", patch)); if (okMsg) toast(okMsg); }
  catch (e) { toast(e.message, 4000); }
  if (!clCur && clTab === "close" && $("#close-body")) clRender();
}
const clKb = (n) => n > 1048576 ? (n / 1048576).toFixed(1).replace(".", ",") + " МБ" : Math.max(1, Math.round(n / 1024)) + " КБ";
/* Вкладки листа «Близкие»: «Близкие» | «Рефералы». Зовут в «Близкие» из «Рефералов» (offers) — карточка с согласием. */
/* «Семья» — общий бюджет с близкими (27.10, по макету «Dewiar — новые режимы», экран Budget). То же, что core/family.py
   на компьютере, и тот же протокол: сообщения вида fam через «Близкие» со сквозным шифрованием — {fam: {op: invite |
   join | leave | spend | del | bill | limit}}. Траты: money_add (голосом «продукты 46,20») уходит семье; удалили в
   «Моём дне» — удаляется и у семьи. Платежи и лимит — «последнее изменение главнее». Хранится в family.json. */
const FAM_COL = ["#8a9bff", "#ffc978", "#7ee8c8", "#ff9fb8", "#b7a0ff", "#9fd6ff"];
const FAM_MON = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"];
const FAM_MONTH = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"];
let FAM = null;
function famLoad() {
  if (FAM) return FAM;
  let s; try { s = JSON.parse(fileGet("family.json") || "{}"); } catch (e) { s = {}; }
  return FAM = Object.assign({ members: {}, ledger: [], bills: {}, limit: { v: 0, at: 0 }, share: true }, s || {});
}
function famSave() {
  const cut = Date.now() - 400 * 86400000;
  FAM.ledger = FAM.ledger.filter(x => (+x.ts || 0) > cut).slice(-5000);
  fileSave("family.json", JSON.stringify(FAM));
  if (clTab === "fam" && $("#fam-body") && $("#sh-close").classList.contains("on")) famRender();
  famDot();
}
const famJoined = () => Object.keys(famLoad().members).filter(p => FAM.members[p].st === "joined");
const famMe = () => { const st = clLoad(); return (st.me.name && st.me.name !== "Без имени" ? st.me.name : (S.close && S.close.name) || S.user_name) || "Я"; };
const famNum = (n) => Number(n || 0).toLocaleString("ru-RU", { minimumFractionDigits: Number(n) % 1 ? 2 : 0, maximumFractionDigits: 2 });
const famDay = (iso) => iso ? `${+iso.slice(8, 10)} ${FAM_MON[+iso.slice(5, 7) - 1]}` : "";
const famToday = () => isoLocal(new Date()).slice(0, 10);
function famDot() { const b = $('#cl-tabs [data-t="fam"]'); if (b) b.classList.toggle("dot", Object.values(famLoad().members).some(m => m.st === "asked")); }
function famSend(pids, op, text) {
  return Promise.all(pids.map(pid => clSend(pid, text || "", null, "fam", { fam: op })
    .catch(e => plog("info", `семья: не дошло «${op.op}»: ${e.message}`))));
}
async function famInvite(pid) {
  const p = clPerson(pid), m = famLoad().members[p.pid] || {};
  if (m.st === "joined") return;
  if (m.st === "asked") return famAccept(p.pid);
  FAM.members[p.pid] = { name: p.name, st: "invited", at: Math.floor(Date.now() / 1000) }; famSave();
  await clSend(p.pid, "Приглашаю вести общий семейный бюджет в Dewiar: траты и общие платежи у всех вместе. Принять: на телефоне — «Близкие» → вкладка «Семья» (обновите приложение Dewiar, если её нет), на компьютере — студия → «Семья».", null, "fam", { fam: { op: "invite" } });
}
async function famAccept(pid) {
  const m = famLoad().members[pid];
  if (!m) throw new Error("приглашения от этого человека нет");
  m.st = "joined"; famSave();
  await famSend([pid], { op: "join", limit: FAM.limit, bills: Object.values(FAM.bills) });
}
async function famLeave(pid) {
  const m = famLoad().members[pid]; delete FAM.members[pid]; famSave();
  if (m) await famSend([pid], { op: "leave" });
}
function famShareSpend(x) {                                // новая трата на телефоне (money_add) — семье
  if (x.kind !== "expense" || famLoad().share === false) return;
  const e = { id: x.id, who: "", name: famMe(), amount: +x.amount, cur: x.currency || "", cat: x.category || "", note: x.note || "", said: String(x.said || "").slice(0, 120), date: x.date, ts: Date.now() };
  FAM.ledger.push(e); famSave();
  const pids = famJoined(); if (pids.length) { const s = Object.assign({}, e); delete s.who; famSend(pids, { op: "spend", e: s }); }
}
function famDelSpend(id) {
  const n = famLoad().ledger.length;
  FAM.ledger = FAM.ledger.filter(x => !(x.id === id && !x.who));
  if (FAM.ledger.length === n) return;
  famSave(); if (famJoined().length) famSend(famJoined(), { op: "del", id });
}
function famBillSave(b) {
  const name = String(b.name || "").trim().slice(0, 60);
  if (!name) throw new Error("назовите платёж: свет, газ, интернет…");
  const id = b.id || Math.random().toString(16).slice(2, 12), old = famLoad().bills[id] || {};
  const bill = { id, name, amount: Math.round((+b.amount || 0) * 100) / 100, due: String(b.due || "").slice(0, 10), payer: String(b.payer || "").slice(0, 40),
    paid_by: old.paid_by || "", paid_at: old.paid_at || 0, at: Date.now() };
  FAM.bills[id] = bill; famSave(); famSend(famJoined(), { op: "bill", b: bill });
  return bill;
}
function famBillPaid(id, paid) {
  const b = famLoad().bills[id]; if (!b) throw new Error("нет такого платежа");
  Object.assign(b, paid ? { paid_by: famMe(), paid_at: Date.now() } : { paid_by: "", paid_at: 0 }, { at: Date.now() });
  famSave(); famSend(famJoined(), { op: "bill", b });
}
function famBillDel(id) {
  const b = famLoad().bills[id]; if (!b) return;
  delete FAM.bills[id]; famSave(); famSend(famJoined(), { op: "bill", b: Object.assign({}, b, { gone: 1, at: Date.now() }) });
}
async function famRemind(id) {
  const b = famLoad().bills[id]; if (!b) throw new Error("нет такого платежа");
  const who = famJoined().find(pid => FAM.members[pid].name === b.payer);
  if (!who) throw new Error("напомнить можно тому, кто в семье, — выберите, кто платит");
  await clSend(who, `Напоминаю: оплатить «${b.name}»${b.due ? ` до ${b.due.slice(8, 10)}.${b.due.slice(5, 7)}` : ""}${b.amount ? ` — ${b.amount}` : ""}.`);
}
function famLimit(v) { FAM.limit = { v: Math.max(0, Math.round((+v || 0) * 100) / 100), at: Date.now() }; famSave(); famSend(famJoined(), { op: "limit", l: FAM.limit }); }
function famMergeBill(b) {
  if (!b || !b.id) return;
  const cur = FAM.bills[b.id];
  if (cur && +cur.at > +(b.at || 0)) return;               // у нас новее
  if (b.gone) delete FAM.bills[b.id];
  else { const o = {}; ["id", "name", "amount", "due", "payer", "paid_by", "paid_at", "at"].forEach(k => o[k] = b[k]); FAM.bills[b.id] = o; }
}
function famMergeLimit(l) { if (l && typeof l === "object" && +l.at > +(FAM.limit.at || 0)) FAM.limit = { v: +l.v || 0, at: +l.at }; }
function famIn(peer, name, body, out) {                    // входящее из «Близких» (clPoll): от семьи или от своего устройства
  const op = (body || {}).fam || {}, k = op.op, F = famLoad(), m = F.members[peer], now = Math.floor(Date.now() / 1000);
  if (k === "invite" && !out) {
    if (!m || m.st !== "joined") { F.members[peer] = { name: name || "Близкий", st: "asked", at: now };
      if (!feat("family")) { S.features = Object.assign({}, S.features, { family: true }); saveS(); }   // позвали в семью — вкладка появляется сама
      if (!document.hidden) toast(`👪 ${name || "Близкий"} приглашает вести общий бюджет — «Близкие» → «Семья»`, 5000); }
  } else if (k === "join" && !out) {
    if (m && ["invited", "asked", "joined"].includes(m.st)) {
      const was = m.st; m.st = "joined"; famMergeLimit(op.limit); (op.bills || []).forEach(famMergeBill);
      if (was !== "joined") famSend([peer], { op: "join", limit: F.limit, bills: Object.values(F.bills) });
    }
  } else if (k === "leave" && !out) delete F.members[peer];
  else if (["invite", "join", "leave"].includes(k) && out) {      // то же действие с другого своего устройства
    if (k === "leave") delete F.members[peer];
    else if (k === "invite" && !m) F.members[peer] = { name: name || "Близкий", st: "invited", at: now };
    else if (k === "join") F.members[peer] = Object.assign({}, m || {}, { name: (m && m.name) || name || "Близкий", st: "joined" });
  } else if (!(m && m.st === "joined") && !out) return;         // не из семьи — не принимаем
  else if (k === "spend") {
    const e = op.e || {}, who = out ? "" : peer;
    if (e.id && !F.ledger.some(x => x.id === e.id && (x.who || "") === who)) F.ledger.push(Object.assign({}, e, { who, name: e.name || name }));
  } else if (k === "del") F.ledger = F.ledger.filter(x => !(x.id === op.id && (x.who || "") === (out ? "" : peer)));
  else if (k === "bill") famMergeBill(op.b);
  else if (k === "limit") famMergeLimit(op.l);
  famSave();
}
function famPublic() {
  const F = famLoad(), month = famToday().slice(0, 7), today = famToday(), me = famMe();
  const led = F.ledger.filter(x => String(x.date || "").slice(0, 7) === month), by = {};
  const nameOf = (pid) => !pid ? "Я" : (F.members[pid] || {}).name || "";
  led.forEach(x => { const k = x.who || ""; (by[k] = by[k] || { pid: k, name: nameOf(k) || x.name, sum: 0 }).sum = Math.round((by[k].sum + (+x.amount || 0)) * 100) / 100; });
  ["", ...famJoined()].forEach(pid => by[pid] = by[pid] || { pid, name: nameOf(pid), sum: 0 });
  const bills = Object.values(F.bills).sort((a, b) => (!!a.paid_by - !!b.paid_by) || String(a.due || "9999").localeCompare(String(b.due || "9999")));
  return { me, month, total: Math.round(Object.values(by).reduce((s, v) => s + v.sum, 0) * 100) / 100, limit: +F.limit.v || 0,
    by: Object.values(by).sort((a, b) => (a.pid !== "") - (b.pid !== "") || b.sum - a.sum), bills,
    feed: led.filter(x => x.date === today).sort((a, b) => b.ts - a.ts).slice(0, 30), recent: led.sort((a, b) => b.ts - a.ts).slice(0, 60),
    members: Object.entries(F.members).map(([pid, m]) => Object.assign({}, m, { pid })), share: F.share !== false };
}
function famColor(pid) { const o = ["", ...famJoined()], i = o.indexOf(pid); return FAM_COL[(i < 0 ? o.length : i) % FAM_COL.length]; }
// фото — как в «Близких» (своё — из «Моей карточки»); подставляет clFacesFill после отрисовки
const famFace = (pid) => { const st = clLoad(), p = pid ? st.people.find(q => q.pid === pid) : st.me; return p && p.pid && +p.face ? [p.pid, +p.face] : null; };
const famAva = (name, pid, cls) => { const fc = famFace(pid); return `<span class="fmava${cls ? " " + cls : ""}" style="background-color:${famColor(pid)}"${fc ? ` data-face="${esc(fc[0])}" data-v="${fc[1]}"` : ""} aria-hidden="true">${esc(String(name || "?").trim().slice(0, 1).toUpperCase() || "?")}</span>`; };
/* Вкладка «Семья» — карточками (29.10, владелец: «плохо выглядит, без структуры, форма не в стиле, всё в кучу»): месяц —
   итог, лимит, полоса и кто сколько; «Общие платежи» — строки «что · до когда · кто» с суммой и кнопками под ними (без
   рамок, просрочен — мягкий красный фон); «+ Платёж» — форма в стиле приложения, кто платит — чипами; лента; «Кто в
   семье» — позвать нажатием на имя близкого, не выпадающим списком. */
let famAddOpen = false, famPayer = "";
function famRender() {
  const box = $("#fam-body"); if (!box) return;
  const d = famPublic(), st = clLoad(), lim = d.limit, over = lim && d.total > lim, base = Math.max(lim, d.total) || 1;
  const joinedNames = d.members.filter(m => m.st === "joined").map(m => m.name);
  const by = d.by.filter(v => v.sum > 0 || v.pid === "" || joinedNames.includes(v.name));
  const asked = d.members.filter(m => m.st === "asked"), others = d.members.filter(m => m.st !== "asked");
  const free = st.people.filter(p => !d.members.some(m => m.pid === p.pid));
  const first = (n) => String(n || "").trim().split(/\s+/)[0];
  const CHK = `<svg viewBox="0 0 24 24"><path d="M5 12l5 5L19 7"/></svg>`, CLK = `<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8"/><path d="M12 8v4l2 2"/></svg>`;
  const list = d.feed.length ? d.feed : d.recent.slice(0, 10), payers = [d.me, ...joinedNames];
  if (!payers.includes(famPayer)) famPayer = d.me;
  const bill = (b) => {
    const paid = !!b.paid_by, late = !paid && b.due && b.due < famToday(), today = !paid && b.due === famToday();
    const sub = paid ? `оплатил(а) ${esc(first(b.paid_by))}, ${famDay(isoLocal(new Date(b.paid_at)).slice(0, 10))}`
      : [b.due ? (late ? `просрочен с ${famDay(b.due)}` : today ? "сегодня" : `до ${famDay(b.due)}`) : "", b.payer ? `платит ${esc(first(b.payer))}` : "кто платит — не выбрано"].filter(Boolean).join(" · ");
    return `<div class="fmbill ${paid ? "paid" : late ? "late" : "due"}" data-id="${esc(b.id)}"><span class="fmic">${paid ? CHK : CLK}</span>
      <div class="fmbt"><b>${esc(b.name)}</b><small>${sub}</small></div>${b.amount ? `<b class="fmsum">${famNum(b.amount)}</b>` : "<span></span>"}
      ${paid ? "" : `<div class="fmbact"><button class="fmbtn ok" data-paid="${esc(b.id)}">${CHK}Оплачено</button>${joinedNames.includes(b.payer) ? `<button class="fmbtn rem" data-rem="${esc(b.id)}">Напомнить</button>` : ""}</div>`}</div>`;
  };
  box.innerHTML = asked.map(m => `<div class="card fmask">${famAva(m.name, m.pid)}<div><b>${esc(m.name)} приглашает вести общий бюджет</b><small>Траты и общие платежи будут видны вам обоим.</small></div>
      <div class="row2"><button class="btn p" data-acc="${esc(m.pid)}">Принять</button><button class="btn" data-out="${esc(m.pid)}">Не сейчас</button></div></div>`).join("")
    + `<section class="card fmmonth" aria-label="Потрачено за месяц"><div class="fmhead"><div><small>Общий бюджет</small><h3>${FAM_MONTH[+d.month.slice(5, 7) - 1]}</h3></div><div class="fmstack">${by.map(v => famAva(v.pid ? v.name : d.me, v.pid)).join("")}</div></div>`
    + `<div class="fmtot"><b>${famNum(d.total)} <span>${esc(CUR)}</span></b><button class="fmlim${over ? " over" : ""}" id="fm-lim">${lim ? (over ? `больше лимита на ${famNum(d.total - lim)}` : `из ${famNum(lim)} на месяц`) : "задать лимит"}</button></div>`
    + `<div class="fmbar${over ? " over" : ""}" role="img" aria-label="${esc(by.map(v => `${v.pid ? v.name : "Я"} ${famNum(v.sum)}`).join(", ") + (lim && !over ? `, остаток ${famNum(lim - d.total)}` : ""))}">${by.filter(v => v.sum > 0).map(v => `<i style="width:${(v.sum / base * 100).toFixed(2)}%;background:${famColor(v.pid)}"></i>`).join("")}</div>`
    + `<div class="fmby">${by.map(v => `<div><span><i style="background:${famColor(v.pid)}"></i>${esc(v.pid ? first(v.name) : "Я")}</span><b>${famNum(v.sum)}</b></div>`).join("")}</div></section>`
    + `<section class="card fmsec"><div class="fmsh"><h4>Общие платежи</h4><button class="fmplus${famAddOpen ? " on" : ""}" id="fm-addb" aria-expanded="${famAddOpen}">${famAddOpen ? "Закрыть" : "+ Платёж"}</button></div>`
    + (famAddOpen ? `<div class="fmform"><input id="fm-bn" placeholder="Что платим: свет, газ, интернет" maxlength="60" aria-label="Платёж">
        <div class="fmrow"><input id="fm-ba" type="number" inputmode="decimal" placeholder="Сумма" aria-label="Сумма"><input id="fm-bd" type="date" aria-label="Оплатить до"></div>
        <div class="fmwho"><small>Кто платит</small><div>${payers.map(n => `<button class="fmchip${n === famPayer ? " on" : ""}" data-payer="${esc(n)}">${esc(first(n))}</button>`).join("")}</div></div>
        <button class="btn p w" id="fm-bgo">Добавить платёж</button></div>` : "")
    + `<div class="fmbills">${d.bills.map(bill).join("") || `<p class="hint fmempty">Свет, газ, интернет — добавьте, кто и до какого числа платит. «Оплачено» увидят все.</p>`}</div></section>`
    + `<section class="card fmsec"><div class="fmsh"><h4>${d.feed.length ? "Сегодня" : "Последние траты"}</h4></div><div class="fmfeed">${list.map(x => { const nm = x.who ? x.name : d.me, what = String(x.note || x.cat || "Расход");
      return `<div>${famAva(nm, x.who || "", "sm")}<div><b>${esc(what.slice(0, 1).toUpperCase() + what.slice(1))}</b><small>${x.said ? `голосом: «${esc(x.said)}» · ` : ""}${x.who ? esc(first(nm)) + " · " : ""}${x.date === famToday() ? clTime(x.ts) : famDay(x.date)}</small></div><b>${famNum(x.amount)}</b></div>`; }).join("")
      || `<p class="hint fmempty">Скажите «продукты 46,20» — трата запишется и появится у всей семьи.</p>`}</div></section>`
    + `<section class="card fmsec"><div class="fmsh"><h4>Кто в семье</h4></div><div class="fmppl">${famAva(d.me, "")}<div><b>${esc(d.me)}</b><small>это вы</small></div></div>`
    + others.map(m => `<div class="fmppl">${famAva(m.name, m.pid)}<div><b>${esc(m.name)}</b><small>${m.st === "joined" ? "в семье" : "ждём ответа"}</small></div><button class="fmbtn" data-out="${esc(m.pid)}">${m.st === "joined" ? "Убрать" : "Отменить"}</button></div>`).join("")
    + (free.length ? `<div class="fminv"><small>Позвать в общий бюджет</small><div>${free.map(p => `<button class="fmchip add" data-inv="${esc(p.pid)}">${esc(first(p.name))}<i>+</i></button>`).join("")}</div></div>`
      : `<p class="hint fmempty">${st.people.length ? "Все близкие уже в списке." : "Позвать можно тех, кто есть в «Близких»: сначала добавьте человека на вкладке «Близкие»."}</p>`)
    + `<div class="sw fmshare"><div>Делиться моими тратами<small>Расходы, которые вы записываете, сразу видны семье</small></div><label class="tg"><input type="checkbox" id="fm-share"${d.share ? " checked" : ""}><i></i></label></div></section>`;
  clFacesFill(box);
  const run = (f, ok) => async () => { try { await f(); if (ok) toast(ok); } catch (e) { toast(e.message, 4000); } famRender(); };
  $$("#fam-body [data-acc]").forEach(b => b.onclick = run(() => famAccept(b.dataset.acc), "Вы в общем бюджете"));
  $$("#fam-body [data-out]").forEach(b => b.onclick = run(() => famLeave(b.dataset.out)));
  $$("#fam-body [data-paid]").forEach(b => b.onclick = run(() => famBillPaid(b.dataset.paid, true), "Отмечено: оплачено"));
  $$("#fam-body [data-rem]").forEach(b => b.onclick = run(() => famRemind(b.dataset.rem), "Напоминание отправлено"));
  $$("#fam-body [data-inv]").forEach(b => b.onclick = run(() => famInvite(b.dataset.inv), "Приглашение отправлено"));
  $$("#fam-body [data-payer]").forEach(b => b.onclick = () => { famPayer = b.dataset.payer; $$("#fam-body [data-payer]").forEach(x => x.classList.toggle("on", x === b)); });
  $$("#fam-body .fmbill.paid").forEach(el => el.oncontextmenu = (e) => { e.preventDefault();
    if (confirm(`Удалить платёж «${(FAM.bills[el.dataset.id] || {}).name}» у всей семьи?`)) run(() => famBillDel(el.dataset.id), "Платёж удалён")(); });
  $("#fm-addb").onclick = () => { famAddOpen = !famAddOpen; famRender(); if (famAddOpen) setTimeout(() => $("#fm-bn") && $("#fm-bn").focus(), 60); };
  $("#fm-share").onchange = () => { FAM.share = $("#fm-share").checked; famSave(); };
  $("#fm-lim").onclick = () => { const v = prompt("Лимит на месяц для всей семьи (0 — без лимита)", lim || ""); if (v !== null) run(() => famLimit(String(v).replace(",", ".")), "Лимит сохранён — у всей семьи")(); };
  if ($("#fm-bgo")) $("#fm-bgo").onclick = run(async () => { await famBillSave({ name: $("#fm-bn").value, amount: +String($("#fm-ba").value).replace(",", "."), due: $("#fm-bd").value, payer: famPayer }); famAddOpen = false; }, "Платёж добавлен");
}
const CL_TABIC = {
  close: '<path d="M12 19.5s-7-4.3-7-9.6A3.9 3.9 0 0 1 12 7.6a3.9 3.9 0 0 1 7 2.3c0 5.3-7 9.6-7 9.6z"/>',
  fam: '<path d="M4.5 11 12 5l7.5 6v7.5a1.5 1.5 0 0 1-1.5 1.5h-3.5v-5h-5v5H6a1.5 1.5 0 0 1-1.5-1.5z"/>',
  near: '<path d="M12 20.5s-6-5.4-6-10.5a6 6 0 0 1 12 0c0 5.1-6 10.5-6 10.5z"/><circle cx="12" cy="10" r="2.2"/>',
  meet: '<rect x="3.5" y="6.5" width="11.5" height="11" rx="2.5"/><path d="m15 10.5 5-3v9l-5-3"/>',
  ref: '<path d="m12 3.8 2.5 5.1 5.6.8-4 3.9 1 5.6-5.1-2.7-5 2.7.9-5.6-4-3.9 5.6-.8z"/>' };
let clTab = "close";
function clTabs() { $$("#cl-tabs button").forEach(b => b.onclick = () => { clTab = b.dataset.t; clRender(); }); }
const clOffers = (st) => (st.offers || []).map(o => `<div class="card clof"><b>${esc(o.name)} зовёт вас в «Близкие»</b>
  <p class="hint" style="margin:4px 0 10px">Вы связаны приглашением в Dewiar. Согласитесь — и ваши помощники смогут передавать друг другу сообщения, можно будет созваниваться.</p>
  <div class="row2"><button class="btn p" data-y="${esc(o.pid)}" style="flex:1">Принять</button><button class="btn" data-n="${esc(o.pid)}" style="flex:1">Не сейчас</button></div></div>`).join("");
function clOfferBind() {
  $$(".clof [data-y], .clof [data-n]").forEach(b => b.onclick = async () => { const pid = b.dataset.y || b.dataset.n, yes = !!b.dataset.y; b.disabled = true;
    try { clKeys(); if (!clLoad().me.pid) await clHello(); const d = await clReq("POST", "/close/offer", { pid, yes }); clPeople(d);
      if (yes && d.person) { toast(`${d.person.name} теперь в ваших близких`); clTab = "close"; clCur = d.person.pid; } clRender(); }
    catch (e) { b.disabled = false; toast(e.message, 4000); } });
}
function openRefs() { clTab = "ref"; openClose(""); }
function openClose(pid) { clCur = pid || ""; try { grInfo = ""; grNew = null; } catch (e) { } openSheet("#sh-close"); clRender(); if (syncCred()) clHello().then(() => clRender()).catch(() => { }); }
function clRender() {
  const st = clLoad(), box = $("#close-body"), p = clCur && st.people.find(x => x.pid === clCur);
  if (syncCred() && typeof grRender === "function" && (grNew || (clCur && clCur[0] === "g"))) {   // «Группы своих»: мастер или переписка группы
    $("#cl-h").firstChild.textContent = ""; $("#cl-inv").style.display = "none"; if (grRender(box)) return; clCur = "";
  }
  $("#cl-h").firstChild.textContent = p ? "" : clTab === "ref" ? "Рефералы" : "Близкие";
  $("#cl-inv").style.display = p ? "none" : "";
  if (!syncCred()) { box.innerHTML = `<div class="card"><b>Нужен Dewiar</b><p class="hint" style="margin:6px 0 10px">«Близкие» работают через облако Dewiar: подключите мозг Dewiar или войдите аккаунтом dewiar.pro.</p><button class="btn p w" id="cl-brain">Подключить</button></div>`;
    $("#cl-brain").onclick = () => openSettings("brain"); return; }
  if (p) {
    delete st.unread[p.pid]; clSave(); clBadge(); clSeen(p.pid);
    const h = st.hist[p.pid] || [];
    box.innerHTML = `<div class="clh"><button class="ib soft" id="cl-back"><svg viewBox="0 0 24 24"><path d="m15 5-7 7 7 7"/></svg></button>${clAvaH(p.pid, p.name, p.face)}
        <div style="flex:1;min-width:0"><b>${esc(p.name)}</b><small>${p.about ? esc(p.about) + " · " : ""}${(p.devs || []).length ? "сообщения шифруются" : "ещё не открывал Dewiar"}</small></div>
        ${(p.devs || []).length && window.DewiarCall ? `<button class="ib soft" id="cl-call" title="Позвонить"><svg viewBox="0 0 24 24"><path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2"/></svg></button>
          <button class="ib soft" id="cl-vcall" title="Видеозвонок"><svg viewBox="0 0 24 24"><rect x="2.5" y="6.5" width="13" height="11" rx="2.5"/><path d="m15.5 10.5 6-3.5v10l-6-3.5"/></svg></button>` : ""}
        <button class="ib soft" id="cl-album" title="Фото и файлы" aria-label="Фото и файлы">${AL_IC.album}</button>
</div>${((famLoad().members || {})[p.pid] || {}).st === "asked" ? `<div class="card famask"><b>👪 ${esc(p.name)} зовёт вести общий бюджет</b><small>Траты и общие платежи — у вас обоих, в «Близкие» → «Семья».</small>
        <div class="row2"><button class="btn p" id="fam-yes">Принять</button><button class="btn" id="fam-open">Посмотреть</button></div></div>` : ""}
      <div class="clmsgs" id="cl-msgs">${h.map((m, i) => `<div class="clm ${m.out ? "out" : ""}${m.rx && (m.rx.me || m.rx.them) ? " rx" : ""}${clEmoOnly(m.t) ? " emo" : ""}" data-i="${i}">${m.t ? `<div>${clEmo(esc(m.t))}</div>` : ""}${(m.f || []).map((f, j) => clFileHtml(f, i, j)).join("")}<time>${clTime(m.ts)}${clTick(m, p.pid)}</time>${m.rx && (m.rx.me || m.rx.them) ? `<span class="clrx">${clEmo(esc([m.rx.them, m.rx.me].filter(Boolean).join("")))}</span>` : ""}</div>`).join("")
        || `<p class="hint" style="text-align:center;margin:24px 8px">Напишите первое сообщение — или скажите: «Напиши ${esc(p.name)}, …»</p>`}</div>
      <div class="clatts" id="cl-atts">${clFiles.map((f, i) => `<span>${esc(f.name)} <button data-i="${i}">✕</button></span>`).join("")}</div>
      <div class="clemo" id="cl-emo" hidden>${clEmoHtml()}</div>
      <div class="clsend"><button class="ib att" id="cl-emo-b" aria-label="Эмодзи" aria-expanded="false"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8.5"/><path d="M8.5 14a4.2 4.2 0 0 0 7 0"/><path d="M9 9.6v.01M15 9.6v.01"/></svg></button><label class="ib att"><input type="file" id="cl-file" multiple hidden><svg viewBox="0 0 24 24"><path d="M20.5 11.5 12.6 19.4a5 5 0 0 1-7.1-7.1l8.3-8.3a3.4 3.4 0 0 1 4.8 4.8l-8.3 8.3a1.7 1.7 0 0 1-2.4-2.4l7.6-7.6"/></svg></label>
        <textarea id="cl-text" rows="1" placeholder="Сообщение…"></textarea><button class="ib" id="cl-go"><svg viewBox="0 0 24 24"><path d="M4 12 20 4l-6 16-2.5-6.5z"/></svg></button></div>`;
    const msgs = $("#cl-msgs"); msgs.scrollTop = msgs.scrollHeight; clFacesFill($(".clh"));
    clImgFill(msgs, h, { pid: p.pid });                     // фото — картинкой (album.js)
    $("#cl-album").onclick = () => clAlbum({ pid: p.pid });
    $("#cl-back").onclick = () => { clCur = ""; clRender(); };
    if ($("#fam-yes")) $("#fam-yes").onclick = async () => { try { await famAccept(p.pid); toast("Вы в общем бюджете — «Близкие» → «Семья»", 4000); } catch (e) { toast(e.message, 4000); } clRender(); };   // 28.10: приглашение в семью — прямо в переписке
    if ($("#fam-open")) $("#fam-open").onclick = () => { clCur = ""; clTab = "fam"; clRender(); };
    clWipe = () => { if (!confirm(`Очистить переписку с «${p.name}» на этом телефоне? У ${p.name} и на ваших других устройствах она останется. Одно сообщение — долгое нажатие на него.`)) return;
      clForget(p.pid); clRender(); toast("Переписка очищена"); };
    if ($("#cl-call")) { $("#cl-call").onclick = () => clCall(p.pid, false).catch(e => toast(e.message, 4000)); $("#cl-vcall").onclick = () => clCall(p.pid, true).catch(e => toast(e.message, 4000)); }
    $$("#cl-atts button").forEach(b => b.onclick = () => { clFiles.splice(+b.dataset.i, 1); clRender(); });
    $$(".clf").forEach(b => b.onclick = () => clSaveFile(p, h[+b.dataset.i], +b.dataset.j));
    $("#cl-file").onchange = () => { [...$("#cl-file").files].forEach(f => clFileTake(f)); };
    const go = async () => { const t = $("#cl-text").value.trim(); if (!t && !clFiles.length) return;
      if (!clFiles.length) return clSendSoon(p.pid, t, () => clSend(p.pid, t, []));
      clSendFiles(p.pid, t); };
    $("#cl-go").onclick = go;
    $("#cl-emo-b").onclick = () => { const e = $("#cl-emo"); e.hidden = !e.hidden; $("#cl-emo-b").setAttribute("aria-expanded", String(!e.hidden)); };
    clEmoBind();
    clReBind(p, h);
    return;
  }
  if ((clTab === "near" || clTab === "meet") && !feat(clTab)) clTab = "close";      // «Возможности»: выключено — вкладки нет
  if (clTab === "fam" && !feat("family")) clTab = "close";
  // вкладки — значком и подписью под ним (29.10, владелец: «надписи обрезаны, может иконками показать»)
  const tb = (t, label, ic) => `<button data-t="${t}" class="${clTab === t ? "on" : ""}" aria-label="${label}"${clTab === t ? ' aria-current="page"' : ""}><svg viewBox="0 0 24 24" aria-hidden="true">${CL_TABIC[t]}</svg><span>${label}</span></button>`;
  const tabs = `<div class="tabs ictabs" id="cl-tabs">${tb("close", "Близкие")}${feat("family") ? tb("fam", "Семья") : ""}${feat("near") ? tb("near", "Рядом") : ""}${feat("meet") ? tb("meet", "Встречи") : ""}${tb("ref", "Рефералы")}</div>`;
  if (clTab === "fam") { if (!$("#fam-body")) { box.innerHTML = tabs + `<div id="fam-body"></div>`; clTabs(); } famRender(); famDot(); return; }
  if (clTab === "ref") { if (!$("#rf-body")) { box.innerHTML = tabs + `<div id="rf-body"></div>`; clTabs(); } refTab(); return; }
  if (clTab === "meet") { if (!$("#meet-body")) { box.innerHTML = tabs + `<div id="meet-body"></div>`; clTabs(); } meetRender(); mtLoad(); return; }
  if (clTab === "near") { if (!$("#rad-body")) { box.innerHTML = tabs + `<div id="rad-body"></div>`; clTabs(); } radRender(); return; }
  // сверху — сами близкие (лица крупно: нажал — переписка), «+» — пригласить; печать с приглашением — только когда
  // её позвали («Пригласить» или «+»), а не на пол-экрана каждый раз (отзыв 11.10)
  const inv = st.invite && Date.now() / 1000 < (st.invite.expires || 0) ? st.invite : null;
  const last = (x) => { const l = (st.hist[x.pid] || []).slice(-1)[0]; return l ? clEmo(esc((l.out ? "Вы: " : "") + (l.t || "📎 " + ((l.f || [])[0] || {}).name))) : "пока без сообщений"; };
  const PH = `<svg viewBox="0 0 24 24"><path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2"/></svg>`,
    VI = `<svg viewBox="0 0 24 24"><rect x="2.5" y="6.5" width="13" height="11" rx="2.5"/><path d="m15.5 10.5 6-3.5v10l-6-3.5"/></svg>`;
  const myName = st.me.name && st.me.name !== "Без имени" ? st.me.name : (S.close && S.close.name) || S.user_name || "";
  const rc = radCfg(), rseen = radOn() ? rc.to.map(pid => st.people.find(p => p.pid === pid)).filter(Boolean).map(p => esc(radFirst(p.name))) : [];
  box.innerHTML = tabs + clOffers(st)
    + (rseen.length && feat("near") ? `<button class="rad-mini" id="rad-mini"><i class="dot"></i><span>${rseen.length === 1 ? "Вас видит" : "Вас видят"} ${radList(rseen)} · ${radUntil(rc.until)}</span><b>Рядом</b></button>` : "")
    + `<div class="clfaces">${st.people.map(x => `<button class="clface" data-pid="${esc(x.pid)}">${clAvaH(x.pid, x.name, x.face, st.unread[x.pid] ? `<em>${st.unread[x.pid]}</em>` : "")}<span>${esc(String(x.name || "").split(/\s+/)[0])}</span></button>`).join("")}
        <button class="clface add" id="cl-add"><i class="clava">+</i><span>Добавить</span></button></div>`
    + (st.people.length ? st.people.map(x => `<div class="clp" data-pid="${esc(x.pid)}">${clAvaH(x.pid, x.name, x.face)}
        <span><b>${esc(x.name)}</b><small>${last(x)}</small></span>${st.unread[x.pid] ? `<em>${st.unread[x.pid]}</em>` : ""}
        ${(x.devs || []).length && window.DewiarCall ? `<button class="ib soft" data-call="${esc(x.pid)}" title="Позвонить">${PH}</button><button class="ib soft" data-vcall="${esc(x.pid)}" title="Видеозвонок">${VI}</button>` : ""}</div>`).join("")
      : `<div class="card"><b>Пока никого</b><p class="hint" style="margin:4px 0 0">Нажмите «Пригласить» — покажите близкому печать Dewiar или отправьте ссылку. Потом говорите: «напиши маме, что я задержусь», «позвони маме по видео».</p></div>`)
    + (typeof grListHtml === "function" ? grListHtml(st) : "")
    + `<div id="cl-invbox"></div>`
    + (inv && !clInvOpen ? `<button class="btn w clinvrow" id="cl-inv-show">Ссылка-приглашение действует до ${new Date(inv.expires * 1000).toLocaleDateString("ru-RU", { day: "numeric", month: "long" })} — показать печать</button>` : "")
    + clLiveCard()
    + `<h3>Моя карточка</h3><div class="card clme"><div class="clme-top"><label class="clme-face" aria-label="Выбрать фото">${clAvaH(st.me.pid || "me", myName || "?", st.me.face)}<input type="file" accept="image/*" id="cl-face" hidden><span>${st.me.face ? "Сменить" : "Фото"}</span></label>
        <div style="flex:1;min-width:0"><input id="cl-name" placeholder="ваше имя" maxlength="40" value="${esc(myName)}"><small class="hint" style="display:block;margin:4px 2px 0">так вас видят близкие</small></div></div>
      <textarea id="cl-about" maxlength="160" rows="2" placeholder="О себе: пара слов — чем живёте, что любите">${esc(st.me.about || "")}</textarea>
      ${st.me.face ? `<button class="btn sm" id="cl-face-del" style="margin-top:8px">Убрать фото</button>` : ""}
      <div class="sw" style="margin-top:10px"><div>Показывать фото во «Встречах»<small>люди рядом увидят его на вашей карточке</small></div><label class="tg"><input type="checkbox" id="cl-face-meet" ${st.me.face_meet ? "checked" : ""}><i></i></label></div>
      <p class="hint" style="margin:8px 2px 0">Фото хранится на dewiar.pro, как аватар в мессенджере: его видят только ваши близкие (и люди рядом во «Встречах», если включено).</p>
      <div class="sw" style="margin-top:10px"><div>Читать сообщения вслух<small>«Мама пишет: …»</small></div><label class="tg"><input type="checkbox" id="cl-speak" ${S.close && S.close.speak === false ? "" : "checked"}><i></i></label></div></div>
    <p class="hint" style="margin:12px 4px">Переписка и звонки между помощниками, сообщения шифруются на устройствах. Голосом: «напиши Людмиле: привет», «позвони маме по видео».</p>
    <button class="btn w clscan" id="cl-scan"><svg viewBox="0 0 24 24"><path d="M4 8V5.5A1.5 1.5 0 0 1 5.5 4H8M16 4h2.5A1.5 1.5 0 0 1 20 5.5V8M20 16v2.5a1.5 1.5 0 0 1-1.5 1.5H16M8 20H5.5A1.5 1.5 0 0 1 4 18.5V16M7 12h10"/></svg>Сканировать приглашение</button>
    <details class="more"><summary>Пришла ссылка-приглашение?</summary><div class="row2" style="margin-top:8px"><input id="cl-link" placeholder="вставьте ссылку" style="flex:1;padding:12px 14px;border-radius:14px;border:0;background:var(--field)"><button class="btn p" id="cl-link-go">Принять</button></div></details>`;
  $$(".clp, .clface[data-pid]").forEach(b => b.onclick = (e) => { if (e.target.closest("[data-call],[data-vcall]")) return; clCur = b.dataset.pid; clRender(); });
  $$("[data-call]").forEach(b => b.onclick = () => clCall(b.dataset.call, false).catch(e => toast(e.message, 4000)));
  $$("[data-vcall]").forEach(b => b.onclick = () => clCall(b.dataset.vcall, true).catch(e => toast(e.message, 4000)));
  $("#cl-add").onclick = () => clInviteOpen();
  if ($("#cl-inv-show")) $("#cl-inv-show").onclick = () => clInviteOpen();
  clTabs(); clOfferBind(); clLiveBind(); if (typeof grBind === "function") grBind();
  if ($("#rad-mini")) $("#rad-mini").onclick = () => { clTab = "near"; clRender(); };
  $("#cl-scan").onclick = () => scanCode();
  if (inv && clInvOpen) clInvShow(inv);
  $("#cl-name").onchange = () => { S.close = Object.assign({}, S.close, { name: $("#cl-name").value.trim() }); saveS(); clHello().then(() => toast("Сохранено")).catch(e => toast(e.message)); };
  $("#cl-about").onchange = () => clMeSave({ about: $("#cl-about").value.trim() }, "Сохранено");
  $("#cl-face").onchange = async () => { const f = $("#cl-face").files[0]; $("#cl-face").value = ""; if (!f) return;
    try { const d = await clFacePrep(f); toast("Загружаю фото…"); await clMeSave({ face: d }, "Фото сохранено"); } catch (e) { toast(e.message, 4000); } };
  if ($("#cl-face-del")) $("#cl-face-del").onclick = () => { if (confirm("Убрать фото? Близкие снова увидят букву.")) clMeSave({ face: "" }, "Фото убрано"); };
  $("#cl-face-meet").onchange = () => clMeSave({ face_meet: $("#cl-face-meet").checked }, $("#cl-face-meet").checked ? "Фото видно во «Встречах»" : "Во «Встречах» фото не видно");
  clFacesFill(box);
  $("#cl-speak").onchange = () => { S.close = Object.assign({}, S.close, { speak: $("#cl-speak").checked }); saveS(); };
  $("#cl-link-go").onclick = () => clAcceptLink($("#cl-link").value);
}
// сообщение только из эмодзи — крупно, как в мессенджерах
const clEmoOnly = (t) => !!t && t.length <= 12 && /^(?:\p{Extended_Pictographic}|\u200d|\ufe0f|\s)+$/u.test(t);
/* реакция: долгое нажатие (или правая кнопка) на сообщение — ряд эмодзи над ним; та же — снять */
/* Убрать сообщения из переписки на этом телефоне (mids — какие, без mids — всю); у близкого и на других устройствах
   переписка остаётся — как forget в core/close.py */
function clForget(pid, mids) {
  const st = clLoad(), h = st.hist[pid] || [], drop = mids ? new Set(mids.map(String)) : null;
  const keep = drop ? h.filter(x => !drop.has(String(x.mid || ""))) : [];
  if (keep.length) st.hist[pid] = keep; else { delete st.hist[pid]; delete st.unread[pid]; }
  clSave(); return h.length - keep.length;
}
function clReBind(p, h) {
  let t = 0, sx = 0, sy = 0;
  const open = (el) => {
    clReClose(); const m = h[+el.dataset.i]; if (!m || !m.mid) return;
    D.vibrate(15);
    const pop = document.createElement("div"); pop.className = "clrepick"; pop.setAttribute("role", "menu");
    // долгое нажатие: реакции, ниже — «Копировать» и «Удалить у меня» (отзыв 17.10: «выборочно поудалять лишнее»)
    pop.innerHTML = `<div class="emos">${CL_EMO.map(e => `<button role="menuitem" data-e="${e}" class="${(m.rx || {}).me === e ? "on" : ""}" aria-label="Реакция ${e}">${clEmo(e)}</button>`).join("")}</div>
      <div class="acts">${m.t ? `<button role="menuitem" class="cp"><svg viewBox="0 0 24 24"><rect x="8.5" y="8.5" width="11" height="11" rx="2.5"/><path d="M15.5 8.5V6a1.5 1.5 0 0 0-1.5-1.5H6A1.5 1.5 0 0 0 4.5 6v8A1.5 1.5 0 0 0 6 15.5h2.5"/></svg>Копировать</button>` : ""}
        <button role="menuitem" class="fw">${AL_IC.fwd}Переслать</button>
        <button role="menuitem" class="dl"><svg viewBox="0 0 24 24"><path d="M4.5 7h15M9.5 7V5a1 1 0 0 1 1-1h3a1 1 0 0 1 1 1v2M6.5 7l1 12.5a1.5 1.5 0 0 0 1.5 1.4h6a1.5 1.5 0 0 0 1.5-1.4L17.5 7"/></svg>Удалить у меня</button></div>`;
    document.body.appendChild(pop);
    const r = el.getBoundingClientRect(), w = pop.offsetWidth;
    pop.style.left = Math.max(8, Math.min(innerWidth - w - 8, m.out ? r.right - w : r.left)) + "px";
    pop.style.top = Math.max(8, r.top - pop.offsetHeight - 8) + "px";
    const cp = $(".cp", pop); if (cp) cp.onclick = () => { clReClose(); copyText(m.t).then(okc => toast(okc ? "Скопировано" : "Не скопировалось")); };
    $(".fw", pop).onclick = () => { clReClose(); clFwdPick({ t: m.t || "", f: m.f || [] }); };   // переслать другому близкому или в группу (album.js)
    $(".dl", pop).onclick = () => { clReClose(); clForget(p.pid, [m.mid]); clRender(); toast("Удалено на этом телефоне — у " + p.name + " сообщение осталось", 3000); };
    $$("button[data-e]", pop).forEach(b => b.onclick = async () => {
      const e = (m.rx || {}).me === b.dataset.e ? "" : b.dataset.e; clReClose();
      try { await clReact(p.pid, m.mid, e); } catch (x) { toast(x.message, 4000); }
      clRender();
    });
    setTimeout(() => document.addEventListener("pointerdown", clReOut, true), 0);
  };
  $$("#cl-msgs .clm").forEach(el => {
    el.addEventListener("pointerdown", (e) => { sx = e.clientX; sy = e.clientY; clearTimeout(t); t = setTimeout(() => open(el), 450); });
    el.addEventListener("pointermove", (e) => { if (Math.hypot(e.clientX - sx, e.clientY - sy) > 10) clearTimeout(t); });
    ["pointerup", "pointercancel", "pointerleave"].forEach(k => el.addEventListener(k, () => clearTimeout(t)));
    el.addEventListener("contextmenu", (e) => { e.preventDefault(); clearTimeout(t); open(el); });
  });
}
function clReOut(e) { if (!e.target.closest(".clrepick")) clReClose(); }
function clReClose() { $$(".clrepick").forEach(x => x.remove()); document.removeEventListener("pointerdown", clReOut, true); }
let clInvOpen = false;
/* постоянная связь — только если человек включил её сам (владелец 17.11: «можно, сейчас редко этим пользуются»; Huawei
   ругался на частое обновление в фоне): по умолчанию новые сообщения — проверкой раз в 15 минут (CloseWatch) */
const clLiveWanted = () => !!(S.close && S.close.live === true);
const clLiveOn = () => clLiveWanted() && !liteOn();      // лёгкий режим — без постоянной связи: проверка раз в 15 минут
function clLiveCard() {
  if (!D.closeLive || !clLoad().people.length) return "";
  const batt = clLiveOn() && D.batteryOk && !D.batteryOk();
  return `<h3>Когда приложение закрыто</h3><div class="card"><div class="sw"><div>Сообщения и звонки — сразу<small>В шторке — тихий значок «Dewiar на связи»; звонок близкого — на весь экран, даже на заблокированном</small></div>
    <label class="tg"><input type="checkbox" id="cl-live" ${clLiveWanted() ? "checked" : ""}><i></i></label></div>
    ${!clLiveWanted() ? `<p class="hint" style="margin:8px 2px 0">Сейчас новые сообщения — проверкой раз в 15 минут: так бережнее к батарее. Включите, если близкие часто звонят через Dewiar.</p>` : ""}
    ${clLiveWanted() && liteOn() ? `<p class="hint" style="margin:8px 2px 0">Сейчас лёгкий режим (${esc(liteWhyNow)}): новые сообщения — проверка раз в 15 минут, без постоянной связи.</p>` : ""}
    ${batt ? `<button class="btn w" id="cl-batt" style="margin-top:10px">Разрешить работу в фоне</button><p class="hint" style="margin:6px 2px 0">Иначе телефон может усыплять Dewiar, и звонки будут доходить с опозданием.</p>` : ""}</div>`;
}
function clLiveBind() {
  if ($("#cl-live")) $("#cl-live").onchange = async () => { const on = $("#cl-live").checked; S.close = Object.assign({}, S.close, { live: on }); saveS();
    if (on) await needPerm("android.permission.POST_NOTIFICATIONS"); clWatch(); clRender(); };
  if ($("#cl-batt")) $("#cl-batt").onclick = () => D.askBattery();
}
async function clInviteOpen() {
  clInvOpen = true; clTab = "close";
  try { const d = await clInvite(false); clRender(); clInvShow(d); setTimeout(() => { const b = $("#cl-invbox"); if (b) b.scrollIntoView({ block: "center", behavior: "smooth" }); }, 50); }
  catch (e) { toast(e.message, 4000); }
}
function clInvShow(d) {
  const box = $("#cl-invbox"); if (!box) return;
  const code = String(d.link || "").split("&from=")[0];          // в коде — короткая ссылка (без имени): код чище и легче читается
  const seal = window.DewiarCodes && window.ZXing ? DewiarCodes.seal(code) : "";
  box.innerHTML = `<div class="card clinv"><div class="clqr ${seal ? "seal" : ""}" id="cl-code">${seal || (typeof qrcode === "function" ? clQr(code) : "")}</div>
    <p class="hint" style="margin:8px 0">Покажите печать близкому: в Dewiar — «Сканер» в «Близких», без Dewiar — Google Lens. Или отправьте ссылку. Одна ссылка — для всех, кого зовёте, 7 дней; поэтому отправляйте её только своим.</p><p class="hint cllinks">${seal ? `<a href="#" id="cl-code-qr">Обычный QR</a>` : ""}<a href="#" id="cl-renew">Новая ссылка</a></p>
    <div class="row2"><button class="btn p" id="cl-share" style="flex:1">Отправить</button><button class="btn" id="cl-copy" style="flex:1">Копировать</button><button class="btn" id="cl-inv-hide" style="flex:1">Скрыть</button></div></div>`;
  $("#cl-inv-hide").onclick = () => { clInvOpen = false; clRender(); };
  if ($("#cl-code-qr")) $("#cl-code-qr").onclick = (e) => { e.preventDefault(); const c = $("#cl-code"), isSeal = c.classList.contains("seal");
    c.innerHTML = isSeal ? clQr(code) : seal; c.classList.toggle("seal", !isSeal); e.target.textContent = isSeal ? "Печать Dewiar" : "Обычный QR"; };
  $("#cl-share").onclick = () => D.share(`Добавь меня в «Близкие» в Dewiar — наши помощники смогут передавать друг другу сообщения: ${d.link}`);
  $("#cl-copy").onclick = () => { D.copy(d.link); toast("Ссылка скопирована"); };
  $("#cl-renew").onclick = (e) => { e.preventDefault();                        // попала не туда — прежняя перестаёт действовать
    if (confirm("Сделать новую ссылку? Старая перестанет действовать — те, кто уже добавился, останутся в близких.")) clInvite(true).then(clInvShow, (x) => toast(x.message, 4000)); };
}
function clQr(text) {                             // QR как в студии: скруглённые точки и «глазки» (тёмное на белом)
  const q = qrcode(0, "M"); q.addData(text); q.make();
  const n = q.getModuleCount(), m = 1.5, W = n + m * 2, eye = (r, c) => (r < 7 && c < 7) || (r < 7 && c >= n - 7) || (r >= n - 7 && c < 7);
  let dots = "";
  for (let r = 0; r < n; r++) for (let c = 0; c < n; c++) if (q.isDark(r, c) && !eye(r, c)) dots += `<rect x="${(c + m + 0.07).toFixed(2)}" y="${(r + m + 0.07).toFixed(2)}" width=".86" height=".86" rx=".3"/>`;
  const e = (r, c) => { const x = c + m, y = r + m; return `<rect x="${x + 0.5}" y="${y + 0.5}" width="6" height="6" rx="1.9" fill="none" stroke="#111" stroke-width="1"/><rect x="${x + 2}" y="${y + 2}" width="3" height="3" rx="1"/>`; };
  return `<svg viewBox="0 0 ${W} ${W}"><rect width="${W}" height="${W}" fill="#fff"/><g fill="#111">${dots}${e(0, 0)}${e(0, n - 7)}${e(n - 7, 0)}</g></svg>`;
}
