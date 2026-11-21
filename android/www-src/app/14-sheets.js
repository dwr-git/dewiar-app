//@ Телефон и веб-версия, часть 14: листы снизу, дела и достижения, календарь, маршрут, «Что нового», сделанное, файлы задач, душа.
//@ Собирается в android/assets/www/app.js (tools/app_join.py) — порядок частей = порядок исполнения; шапка «//@» в app.js не попадает.
/* ---------- листы снизу (.sheet): открыть, закрыть, смахнуть вниз; за ними — содержимое каждого листа ---------- */
function openSheet(id) { closeSheets(true); hUse("sh:" + String(id).replace("#sh-", "").replace(/-/g, "_")); $(id).classList.add("on"); $("#dim").classList.add("on"); if (typeof courseSeen === "function") courseSeen(id.replace("#sh-", "")); }
function closeSheets(keepDim) {
  $$(".sheet.on").forEach(s => s.classList.remove("on")); if (!keepDim) $("#dim").classList.remove("on");
  if ($(".snd.play") && D.alarmSoundTry) { D.alarmSoundTry(""); $$(".snd.play").forEach(x => x.classList.remove("play")); }   // проба звука — смолкает с листом
  const lv = $("#lsn-v"); if (lv && !lv.paused) lv.pause();                                                                  // видеоурок — тоже
}
$("#dim").onclick = () => closeSheets();
let touchY = null;
document.addEventListener("touchstart", e => { const s = e.target.closest(".sheet"); touchY = s && s.scrollTop <= 0 ? e.touches[0].clientY : null; }, { passive: true });
document.addEventListener("touchend", e => { if (touchY != null && e.changedTouches[0].clientY - touchY > 90 && !document.body.classList.contains("tab")) closeSheets(); touchY = null; }, { passive: true });   // планшет: раздел — панель сбоку, жест вниз её не закрывает (крестик)
/* №93 (идея: «прокрутка плавная нужна, как будто телефон тупит»): пока листают лист, портрет под затемнением не рисуется
   (он притушен и почти не виден — а кадр облика занимал главный поток и заставлял заново размывать фон под листом);
   body.scrolling — метка «листают» для стилей и проверки. Слушатель пассивный, в нём только класс и таймер — без
   перерисовки на каждый шаг прокрутки. Остальное — в app.css: размытие только там, где оно видно, карточки вне экрана
   не рисуются. */
let scrollEnd = 0;
document.addEventListener("scroll", (e) => {
  const t = e.target; if (!t || !t.closest || !t.closest(".sheet")) return;
  if (scrollEnd) clearTimeout(scrollEnd);
  else { document.body.classList.add("scrolling"); if (orb) orb.paused = true; }
  scrollEnd = setTimeout(() => { scrollEnd = 0; document.body.classList.remove("scrolling"); if (orb) { orb.paused = false; orb._wake(); } }, 180);
}, { capture: true, passive: true });

/* персонаж */
let pEnts = [];
$("#who").onclick = () => {
  pEnts.forEach(e => e.dead = true); pEnts = [];
  $("#plist").innerHTML = PERSONAS.map(p => `<div class="pirow"><button class="pi${p.id === S.persona ? " on" : ""}" data-id="${p.id}"><canvas></canvas><span><b>${esc(p.name)}</b><small>${esc(p.role || "")}${p.tagline ? " · " + esc(p.tagline) : ""}</small></span></button>`
    + (p.custom ? `<button class="ib soft pedit" data-e="${esc(p.id)}" title="Изменить" aria-label="Изменить: ${esc(p.name)}"><svg viewBox="0 0 24 24"><path d="M4 20h4L19 9l-4-4L4 16z"/><path d="m13.5 6.5 4 4"/></svg></button>` : "") + `</div>`).join("")
    + (myPersonas().length < MY_MAX ? `<button class="btn w pnew" id="p-new">+ Свой персонаж</button>` : "")
    + galHtml();
  galWire();
  $$("#plist .pedit").forEach(b => b.onclick = () => personaEditor(b.dataset.e));
  if ($("#p-new")) $("#p-new").onclick = () => personaEditor("");
  $$("#plist .pi").forEach(b => {
    const p = PERSONAS.find(x => x.id === b.dataset.id);
    const e = new DewiarEntity($("canvas", b), { style: p.avatar && p.style !== "aura" ? "photo" : p.style, color: p.color, image: p.avatar || null, plate: true, ring: false });
    e.set({ state: "idle" }); pEnts.push(e);
    b.onclick = () => { S.persona = p.id; saveS(); applyPersona(); closeSheets(); showYou(""); showBot(`Теперь отвечает ${p.name}.`); say(`Привет! Это ${p.name}.`); };
  });
  renderLookPanel(); renderKbPanel(); renderMemPanel();
  openSheet("#sh-persona");
};
/* «Готовые персонажи» в листе «Кто отвечает»: карточка — облик, имя, роль, что умеет; «Выбрать» — в команду и сразу отвечает.
   Раздел свёрнут, пока ни одного не выбрали, — список своих наверху не теряется. */
function galHtml() {
  if (!PGALLERY.length) return "";
  const have = galIds();
  const card = (g) => { const on = have.includes(g.id), cur = on && S.persona === g.id;
    return `<div class="pg${on ? " in" : ""}" data-g="${esc(g.id)}" style="--c:${esc(g.color || "#8A9BFF")}">`
      + `<span class="pgava">${g.avatar && !(g.noface && !(on && !galNoFace().includes(g.id))) ? `<img src="${g.avatar}" alt="" loading="lazy" decoding="async">` : `<i>${esc(g.name.slice(0, 1))}</i>`}</span>`
      + `<span class="pgtx"><b>${esc(g.name)}</b>${g.role ? `<em>${esc(g.role)}</em>` : ""}<span class="pgtl">${esc(g.tagline || "")}</span></span>`
      + (cur ? `<span class="pgnow">Отвечает</span>` : on ? `<button class="btn pgoff" aria-label="Убрать из команды: ${esc(g.name)}">Убрать</button>`
        : `<button class="btn p pgon" aria-label="Выбрать: ${esc(g.name)}">Выбрать</button>`) + `</div>`; };
  return `<details class="pgal" id="p-gal"${have.length ? " open" : ""}><summary><b>Готовые персонажи</b><small>Юрист, врач, повар, тренер, учитель языков — выбрать одной кнопкой</small></summary>`
    + `<div class="pglist">${PGALLERY.map(card).join("")}</div>`
    + `<p class="hint">Характер и роль — те же, что на компьютере. Документы и «Знания» персонажу можно подключить ниже.</p></details>`;
}
function galWire() {
  $$("#plist .pg .pgon").forEach(b => b.onclick = (e) => {
    e.stopPropagation();
    const p = galAdd(b.closest(".pg").dataset.g); if (!p) return;
    closeSheets(); showYou(""); showBot(`${p.name} — с вами. Зовите по имени.`); say(gfix(`Привет! Это ${p.name}.`));
  });
  $$("#plist .pg .pgoff").forEach(b => b.onclick = (e) => {
    e.stopPropagation();
    const id = b.closest(".pg").dataset.g, g = PGALLERY.find(x => x.id === id);
    galRemove(id); toast(`«${g ? g.name : id}» больше не в команде`); $("#who").onclick();
  });
}
/* образы (1.0.55): у Лиры и Патрика — кружки образов и «Сама — по времени и сезону»; голосом — «смени образ» (11-commands) */
function renderLookPanel() {
  const box = $("#plook"); if (!box) return;
  const p = personaBase(), cur = lookOf(p), auto = !!((S.looks || {})[p.id] || {}).auto;
  if (!(p.looks || []).length || kidsOn()) { box.innerHTML = ""; return; }
  // кружки — один кадр и размер у всех (live/thumbs, tools/live_looks.py), обычный облик тоже
  const all = [{ id: "", name: "Обычная", img: `live/thumbs/${p.live}.webp` }].concat(p.looks.map(x => ({ id: x.id, name: x.name, img: `live/thumbs/${p.live}-${x.id}.webp` })));
  box.innerHTML = `<div class="card plook"><b>Образ ${esc(p.name === "Лира" ? "Лиры" : p.name === "Патрик" ? "Патрика" : p.name)}</b>`
    + `<div class="plg">${all.map(x => `<button class="${x.id === cur ? "on" : ""}" data-l="${esc(x.id)}"><img src="${x.img}" alt="" loading="lazy"><span>${esc(x.name)}</span></button>`).join("")}</div>`
    + `<div class="sw" style="margin:12px 0 0"><div>Сама — по времени и сезону<small>Вечером — домашний, зимой — зимний, каждый день — немного другая</small></div>`
    + `<label class="tg"><input type="checkbox" id="plook-auto" ${auto ? "checked" : ""}><i></i></label></div></div>`;
  $$("#plook .plg button").forEach(b => b.onclick = () => { setLook(b.dataset.l); renderLookPanel(); });
  $("#plook-auto").onchange = (e) => { setLook(undefined, e.target.checked); renderLookPanel(); };
}
/* своя память у персонажа (0.56): «Общая» — одна на всех, «Своя» — помнит только то, что рассказали ему (синхронизируется) */
function renderMemPanel() {
  const box = $("#pmem"); if (!box) return;
  const p = persona(), own = pmemOwn(p.name), n = memArr().length;
  box.innerHTML = `<div class="card pmemc"><div class="row2"><div style="flex:1;min-width:0"><b>Что помнит ${esc(p.name)}</b><small class="hint" style="display:block;margin:2px 0 0">${own ? `своя — другие персонажи её не видят · ${n} ${n % 10 === 1 && n % 100 !== 11 ? "запись" : [2, 3, 4].includes(n % 10) && ![12, 13, 14].includes(n % 100) ? "записи" : "записей"}` : "общая на всех персонажей"}</small></div></div>
    <div class="seg" id="pmem-seg" role="radiogroup" style="display:flex;margin-top:10px"><button role="radio" data-o="" class="${own ? "" : "on"}" aria-checked="${!own}" style="flex:1">Общая</button><button role="radio" data-o="1" class="${own ? "on" : ""}" aria-checked="${own}" style="flex:1">Своя</button></div></div>`;
  $$("#pmem-seg button").forEach(b => b.onclick = () => {
    const on = !!b.dataset.o; if (on === own) return;
    S.pmem = Object.assign({ own: [], at: 0, facts: {} }, S.pmem || {});
    S.pmem.own = (S.pmem.own || []).filter(x => x !== p.name).concat(on ? [p.name] : []); S.pmem.at = Date.now();
    saveS(); syncSoon(); renderMemPanel();
    toast(on ? `${p.name} теперь помнит своё: что расскажете ему, другие не узнают` : `${p.name} снова помнит общее`, 3500);
  });
}

/* разговор */
/* «Разговор» — лента и переписка (№528, 04.11, владелец: «в беседе хочется написать, но как?»): внизу листа поле, как в
   мессенджере, — «Напишите…», микрофон и «Отправить». Сказанное и ответ видны в ленте сразу: ответ — по мере прихода
   (тот же текст, что на главном экране, #you и #bot), а когда ход закончен — лента перерисовывается из истории. */
let histLive = false;                              // ход начат из «Разговора» — показываем его в ленте, пока он идёт
const histOpen = () => !!$("#sh-hist.on");
function histRender() {
  const h = history.slice(-40), list = $("#hlist");
  list.innerHTML = h.length ? h.map((m, i) => `<div class="msg ${m.role === "user" ? "u" : "a"}">${m.role === "user" ? `<div translate="no">${esc(m.content)}</div>`
      : `<div class="ans" translate="no">${mdAnswer(m.content)}${m.img && window.DewiarRich ? DewiarRich.gallery(m.img) : ""}</div>`}${m.role !== "user" ? `<small class="mrow">${m.who ? esc((PERSONAS.find(p => p.id === m.who) || {}).name || "") : ""}${speechText(String(m.content || "")) ? `<button class="mlisten" data-li="${i}" aria-label="Прослушать ответ">${LISTEN_IC}<span>Прослушать</span></button>` : ""}${String(m.content || "").trim() ? `<span class="macts"><button data-ma="copy" data-li="${i}" aria-label="Скопировать ответ" title="Скопировать">${ICON_COPY}</button><button data-ma="note" data-li="${i}" aria-label="В заметки" title="В заметки">${ICON_NOTE}</button><button data-ma="save" data-li="${i}" aria-label="Скачать ответ файлом" title="Скачать (.md)">${ICON_SAVE}</button></span>` : ""}</small>` : ""}</div>`).join("")
    : `<div class="empty">Разговор пуст. Напишите внизу или нажмите микрофон.</div>`;
  list.insertAdjacentHTML("beforeend", `<div id="hlive"></div>`);
  if (window.DewiarRich) DewiarRich.diagrams(list);
  wirePics(list);
  $$("#hlist .mlisten").forEach(b => b.onclick = () => listenToggle(b, String((h[+b.dataset.li] || {}).content || "")));
  $$("#hlist [data-ma]").forEach(b => b.onclick = () => ansAct(b.dataset.ma, String((h[+b.dataset.li] || {}).content || "")));   // №127
  histLiveShow();
}
const histBottom = () => { const sh = $("#sh-hist"); sh.scrollTop = sh.scrollHeight; };
/* идущий ход — под лентой: что сказали или написали и ответ, пока он приходит (до него — три точки) */
function histLiveShow() {
  const box = $("#hlive"); if (!box) return;
  if (!histLive) { box.innerHTML = ""; return; }
  const you = $("#you").textContent.replace(/^«|»$/g, "").trim(), bot = $("#bot").textContent.trim(), wait = !bot || $("#bot").className === "wait";
  const near = $("#sh-hist").scrollHeight - $("#sh-hist").scrollTop - $("#sh-hist").clientHeight < 120;   // читают выше — не дёргаем
  box.innerHTML = (you ? `<div class="msg u"><div translate="no">${esc(you)}</div></div>` : "")
    + (you || bot ? `<div class="msg a">${wait ? `<div class="hdots" aria-label="${esc(bot || "Думаю")}"><i></i><i></i><i></i></div>` : `<div class="ans">${esc(bot)}</div>`}</div>` : "");
  if (near) histBottom();
}
let histT = 0;
function histSoon() { clearTimeout(histT); histT = setTimeout(() => { if (!histOpen()) return; histLive = false; histRender(); histBottom(); }, 60); }   // ход записан в историю — он уже в ленте
for (const id of ["#you", "#bot"]) new MutationObserver(() => { if (histOpen() && histLive) histLiveShow(); })
  .observe($(id), { childList: true, characterData: true, subtree: true, attributes: true, attributeFilter: ["class"] });
$("#b-hist").onclick = () => {
  histLive = histLive && busy;
  histRender(); htypedGrow();
  openSheet("#sh-hist"); setTimeout(histBottom, 50);
};
function htypedGrow() {
  const t = $("#htyped"); if (!t) return;
  t.style.height = "auto";
  const max = Math.round((window.visualViewport ? visualViewport.height : innerHeight) * 0.3);
  t.style.height = Math.min(Math.max(44, t.scrollHeight + 2), max) + "px";
  t.style.overflowY = t.scrollHeight + 2 > max ? "auto" : "hidden";
  $("#hsend").disabled = !t.value.trim();
}
function histSend() {
  const t = $("#htyped").value.trim(); if (!t) return;
  $("#htyped").value = ""; htypedGrow();
  histLive = true; showYou(t); histLiveShow(); histBottom();
  ask(t);
}
$("#htyped").addEventListener("input", () => {        // поле растёт — последний ответ остаётся над ним, если смотрели вниз ленты
  const sh = $("#sh-hist"), near = sh.scrollHeight - sh.scrollTop - sh.clientHeight < 60;
  htypedGrow(); if (near) histBottom();
});
$("#htyped").onkeydown = (e) => {                    // как на главном экране: телефон — Enter — новая строка; клавиатура компьютера — отправить
  if (e.key !== "Enter" || e.shiftKey || e.isComposing || e.keyCode === 229 || (window.matchMedia && matchMedia("(pointer: coarse)").matches)) return;
  e.preventDefault(); histSend();
};
$("#hsend").onclick = histSend;
$("#hmic").onclick = () => { if (state === "idle") { histLive = true; showYou(""); } $("#mic").onclick(); };
$("#h-clear").onclick = () => { history = []; saveH(); convReset(); $("#b-hist").onclick(); toast("Начинаем заново"); };

/* мой день */
let dayTab = "rem";
$$("#ln-tabs button").forEach(b => b.onclick = () => { LN.tab = b.dataset.t; lnRender(); $("#sh-learn").scrollTop = 0; });
$$("#day-tabs button").forEach(b => b.onclick = () => { dayTab = b.dataset.t; $$("#day-tabs button").forEach(x => x.classList.toggle("on", x === b)); renderDay(); });
$("#b-day").onclick = () => { renderDay(); openSheet("#sh-day"); };
/* Голосом / текстом: в дороге, на встрече, в транспорте ответ удобнее читать. Микрофон работает как прежде —
   выключается только голос ответа; выбор помнится. */
function voiceBtn() {
  const b = $("#b-voice"), off = !!S.textMode;
  b.classList.toggle("off", off); b.setAttribute("aria-pressed", String(off));
  b.title = off ? "Отвечать голосом" : "Отвечать текстом, без голоса";
}
$("#b-voice").onclick = () => {
  S.textMode = !S.textMode; saveS(); voiceBtn();
  if (S.textMode) { stopVoice(); if (state === "speaking" && !busy) finishTurn(); }
  toast(S.textMode ? "Отвечаю текстом — голос выключен" : "Отвечаю голосом", 1800);
};
voiceBtn();
const X_SVG = '<svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6 6 18"/></svg>';
/* шапка «Дела»: сколько сделано сегодня, серия и значки (полученные — ярко, следующий в каждой группе — бледно, с прогрессом) */
/* 24.10, владелец: «первый блок размытый и не понятный — чуть чётче и понятнее»: без размытого свечения; сверху — сколько
   сделано и серия словами; ниже — ближайшие цели строками с полоской («Пятёрка — 5 дел за день · 3 из 5»); полученные
   значки — отдельной строкой «Ваши значки». */
function doneHead(s) {
  const goals = [], got = [];
  for (const g of ["day", "streak", "total"]) {
    const all = ACHIEVE.filter(a => a.g === g), next = all.find(a => achVal(a, s) < a.n);
    all.filter(a => achVal(a, s) >= a.n).forEach(a => got.push(`<button class="ach on" data-tip="${esc(a.icon + " " + a.name + " — " + a.what + " · получено")}">${a.icon}<span>${esc(a.name)}</span></button>`));
    if (next) { const v = Math.min(achVal(next, s), next.n);
      goals.push(`<button class="ach" data-tip="${esc(next.icon + " " + next.name + " — " + next.what + " · сейчас " + achVal(next, s) + " из " + next.n)}"><i>${next.icon}</i><span class="dg"><b>${esc(next.name)}</b><small>${esc(next.what)}</small><span class="dbar"><em style="width:${Math.round(v / next.n * 100)}%"></em></span></span><span class="dgn">${v}/${next.n}</span></button>`); }
  }
  const streak = s.streak >= 2 ? `🔥 Серия: ${s.streak} ${dnRu(s.streak)} подряд` : s.today ? "Первый день серии — завтра продолжим" : s.total ? "Отметьте сегодня дело — серия продолжится" : "Сделали дело — отметьте его";
  const sub = s.today ? `лучший день — ${s.bestDay} ${delaRu(s.bestDay)}, всего ${s.total}` : "голосом («я позвонила маме, отметь»), ✓ у напоминания или строкой ниже";
  return `<div class="donehd"><div class="dtop"><div class="dnum"><b>${s.today}</b><small>Сделано сегодня</small></div>`
    + `<div class="dside"><span class="dstreak">${streak}</span><small class="dsub">${esc(sub)}</small></div>`
    + `<button class="dwhy${doneWhy ? " on" : ""}" id="done-why" aria-label="Что это за награды" aria-expanded="${doneWhy}">?</button></div>`
    + (goals.length ? `<div class="dgoals"><small class="dlab">Следующие значки</small>${goals.join("")}</div>` : "")
    + (got.length ? `<div class="dgot"><small class="dlab">Ваши значки</small><div class="achs">${got.join("")}</div></div>` : "") + `</div>`
    + (doneWhy ? `<div class="donewhy" id="done-whybox"><b>Зачем это</b><p>Сделали дело — отметьте: скажите «я позвонила маме, отметь», нажмите ✓ у напоминания или впишите ниже. `
      + `Отмеченное попадает сюда, а за него — значки: за дела за день (3, 5, 7, 10), за дни подряд и за всё время. Яркие — уже ваши, бледные — следующие, `
      + `нажмите на значок — сколько осталось. Это просто чтобы видеть, сколько уже сделано, и радоваться: ничего не тратится, видите только вы.</p>`
      + `<button class="btn" id="done-whyok">Понятно</button></div>` : "")
    + `<form class="doneadd" id="done-add"><input placeholder="Что уже сделали?" maxlength="120" enterkeyhint="done" aria-label="Что сделали"><button class="ib" aria-label="Отметить сделанным">✓</button></form>`;
}
/* Карточка заметки в списке «Мой день» → «Заметки» (03.11, владелец прислал снимки: крупное фото выбивалось из ряда,
   «•» на отдельной строке, пункты жирным, 📎 и папка переезжали на новую строку). Как в Google Keep / Apple Notes:
   заголовок — до двух строк с многоточием, начало текста — до трёх строк одним потоком (mdPreview flat), ниже —
   мета-строка: когда, папка и вложения маленькими пилюлями. Фото — квадрат одного размера справа, фото несколько —
   счётчик на миниатюре. Длинный список не тормозит: карточки вне экрана не рисуются (content-visibility, app.css). */
const NT_CLIP = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20.5 11.5 12.4 19.6a5 5 0 0 1-7.1-7.1l8.5-8.5a3.3 3.3 0 0 1 4.7 4.7l-8.4 8.4a1.7 1.7 0 0 1-2.4-2.4l7.7-7.7"/></svg>';
function ntWhen(ms) {
  if (!+ms) return "";
  const d = new Date(+ms), now = new Date(), day = (x) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const k = Math.round((day(now) - day(d)) / 864e5);
  if (k === 0) return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
  if (k === 1) return "вчера";
  return `${d.getDate()} ${MON[d.getMonth()]}` + (d.getFullYear() !== now.getFullYear() ? ` ${d.getFullYear()}` : "");
}
function ntCard(x) {
  const imgs = (x.att || []).filter(a => a.type === "image"), src = imgs.length ? noteAttGet(imgs[0].id) : "", na = noteAttCount(x);
  const pv = mdPreview(noteShown(x.text), 200, { flat: true });
  // папка заметки с компьютера (№216: вкладки блокнота у виджета приходят заметками — «Главное» без пометки не узнать)
  const fold = x.folder && !ntFolder ? `<span class="ntf">${esc(String(x.folder).split("/").pop())}</span>` : "";
  const att = na ? `<span class="ntc" aria-label="Вложений: ${na}">${NT_CLIP}${na}</span>` : "", when = ntWhen(x.time);
  const meta = when || fold || att ? `<div class="ntm">${when ? `<span class="ntd">${esc(when)}</span>` : ""}${fold}${att}</div>` : "";
  return `<div class="it note${src ? " ph" : ""}" data-id="${esc(x.id)}"><div class="bd"><b class="ntt">${esc(x.title || "Без названия")}${noteLocked(x.text) ? ' <i class="ntlk" aria-label="заперта">🔒</i>' : ""}</b>`
    + (pv ? `<div class="ntpv">${pv}</div>` : "") + meta + `</div>`
    + (src ? `<span class="nthumb"><img src="${src}" alt="" loading="lazy" decoding="async">${imgs.length > 1 ? `<i class="ntn">${imgs.length}</i>` : ""}</span>` : "") + `</div>`;
}
/* «Мои файлы» с компьютера (0.98, владелец 14.11: «папка пользователя будет синхронизироваться при выключенном
   компьютере… изящное дешёвое решение»). Компьютер присылает уже прочитанный текст своих файлов («Знания» и свои папки,
   core/knowledge.shared) записями doc:<id файла>.<кусок> — сжатыми и только шифром своих устройств (core/sync.py
   _snap_docs). Здесь: оглавление docs.json {id: {name, path, mtime, size, n, have}} и куски doc-<id>.<i> как пришли
   (сжатые); поиск по словам (как core/knowledge, BM25) — в инструменте pc_documents, даже когда компьютер выключен;
   список — в «Заметках» отдельной папкой «Мои файлы», нажали — текст файла. Оригинал остаётся на компьютере. */
const DOC_F = "\u0001files";                     // «папка» в фильтре «Заметок» — не может совпасть с настоящей
function docIdx() { try { return JSON.parse(fileGet("docs.json") || "{}") || {}; } catch (e) { return {}; } }
const docCache = {};
function docApply(id, d, del) {
  const m = /^([0-9a-f]{12})\.(\d{1,4})$/.exec(String(id || "")); if (!m) return;
  const fid = m[1], i = +m[2], x = docIdx();
  if (del) {
    fileSave(`doc-${fid}.${i}`, "");
    const e = x[fid]; if (e) { e.have = (e.have || []).filter(k => k !== i); if (!e.have.length) delete x[fid]; }
  } else {
    const n = +d.n; if (typeof d.z !== "string" || !(n >= 1 && n <= 400) || i >= n) return;
    const was = x[fid], same = was && was.mtime === +d.mtime && was.size === +d.size && was.n === n;
    x[fid] = { name: String(d.name || "Файл").slice(0, 160), path: String(d.path || "").slice(0, 300), mtime: +d.mtime || 0, size: +d.size || 0, n,
      have: [...new Set((same ? was.have || [] : []).concat(i))], at: Date.now() };
    fileSave(`doc-${fid}.${i}`, d.z);
  }
  delete docCache[m[1]];
  fileSave("docs.json", JSON.stringify(x));
}
/* файлы, пришедшие целиком (все куски), — свежие первыми */
function docList() {
  return Object.entries(docIdx()).filter(([, e]) => e.n && (e.have || []).length >= e.n && [...Array(e.n).keys()].every(k => e.have.includes(k)))
    .map(([id, e]) => Object.assign({ id }, e)).sort((a, b) => b.mtime - a.mtime);
}
async function docInflate(z) {
  const bin = Uint8Array.from(atob(z), c => c.charCodeAt(0));
  const st = new Blob([bin]).stream().pipeThrough(new DecompressionStream("deflate"));
  return JSON.parse(await new Response(st).text());
}
/* отрывки файла (как в core/knowledge: ~900 знаков с нахлёстом) — из кэша или собрать из кусков */
async function docChunks(e) {
  if (docCache[e.id]) return docCache[e.id];
  let out = [];
  for (let i = 0; i < e.n; i++) { const z = fileGet(`doc-${e.id}.${i}`); if (!z) return []; out = out.concat(await docInflate(z)); }
  return (docCache[e.id] = out.map(String));
}
/* текст целиком: соседние отрывки перекрываются — нахлёст убираем */
function docJoin(ch) {
  let t = "";
  ch.forEach((c, i) => {
    if (!i) { t = c; return; }
    let cut = 0;
    for (let k = Math.min(220, c.length - 1); k >= 20; k--) if (t.endsWith(c.slice(0, k))) { cut = k; break; }
    t += (cut ? "" : "\n\n") + c.slice(cut);
  });
  return t;
}
const DOC_END = /(ами|ями|ого|его|ому|ему|ыми|ими|ах|ях|ов|ев|ей|ой|ий|ый|ая|яя|ое|ее|ые|ие|ую|юю|ом|ем|ам|ям|ть|ти|ла|ло|ли|ет|ит|ут|ют|ат|ят|ся|сь|а|я|о|е|ы|и|у|ю|ь)$/;
const docWords = (t) => String(t || "").toLowerCase().replace(/ё/g, "е").split(/[^a-zа-я0-9]+/).filter(Boolean).map(w => w.length > 4 ? w.replace(DOC_END, "") : w);
async function docSearch(query, limit = 5) {
  const q = [...new Set(docWords(query).filter(w => w.length > 2))]; if (!q.length) return [];
  const docs = [];
  for (const e of docList()) {
    let ch; try { ch = await docChunks(e); } catch (x) { plog("warn", "Мои файлы: не распаковался " + e.name); continue; }
    ch.forEach((c, i) => { const ws = docWords(e.name + " " + c), cnt = {}; ws.forEach(w => { cnt[w] = (cnt[w] || 0) + 1; }); docs.push({ e, i, c, cnt, len: ws.length }); });
  }
  if (!docs.length) return [];
  const N = docs.length, avg = docs.reduce((s, d) => s + d.len, 0) / N || 1;
  const idf = Object.fromEntries(q.map(w => { const df = docs.filter(d => d.cnt[w]).length; return [w, df ? Math.log(1 + (N - df + 0.5) / (df + 0.5)) : 0]; }));
  const scored = docs.map(d => ({ d, s: q.reduce((s, w) => { const f = d.cnt[w] || 0; return s + (f ? idf[w] * f * 2.2 / (f + 1.2 * (0.25 + 0.75 * d.len / avg)) : 0); }, 0) }))
    .filter(x => x.s > 0).sort((a, b) => b.s - a.s);
  const per = {}, out = [];
  for (const { d, s } of scored) { if ((per[d.e.id] = (per[d.e.id] || 0) + 1) > 2) continue; out.push({ id: d.e.id, name: d.e.name, path: d.e.path, text: d.c, score: +s.toFixed(2) }); if (out.length >= limit) break; }
  plog("info", `📚 Мои файлы: «${clip(query, 60)}» → ${out.map(x => x.name + " " + x.score).join(", ") || "ничего"} (файлов: ${docList().length})`);
  return out;
}
const docN = (n) => window.dwLang && !/^ru/.test(dwLang()) ? n + (n === 1 ? " file" : " files") : n + " " + (n % 10 === 1 && n % 100 !== 11 ? "файл" : n % 10 >= 2 && n % 10 <= 4 && !(n % 100 >= 12 && n % 100 <= 14) ? "файла" : "файлов");
const docSize = (b) => b > 1e6 ? (b / 1e6).toFixed(1).replace(".", ",") + " МБ" : Math.max(1, Math.round(b / 1e3)) + " КБ";
async function docOpen(id) {
  const e = docList().find(x => x.id === id); if (!e) { toast("Файл ещё не пришёл целиком"); return; }
  let text = ""; try { text = docJoin(await docChunks(e)); } catch (x) { toast("Не открылся: " + x.message); return; }
  const html = `<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${esc(e.name)}</title>`
    + `<style>body{font:16px/1.6 system-ui,sans-serif;margin:0;padding:18px 18px 40px;background:#fff;color:#1d1d24}h1{font-size:19px;margin:0 0 4px}`
    + `.m{color:#6b6b78;font-size:13px;margin-bottom:18px}p{margin:0 0 12px;white-space:pre-wrap;overflow-wrap:anywhere}@media(prefers-color-scheme:dark){body{background:#15151c;color:#e8e8f0}.m{color:#9a9ab0}}</style>`
    + `<h1>${esc(e.name)}</h1><div class="m">${esc(e.path)} · текст с компьютера, оригинал — на нём</div>`
    + text.split(/\n{2,}/).map(p => `<p>${esc(p)}</p>`).join("");
  openHtmlView(e.name, html, () => { const w = D.saveDownload ? D.saveDownload(e.name.replace(/\.[a-z0-9]+$/i, "") + ".txt", "text/plain", text) : ""; toast(w ? "Сохранено: " + w : "Не получилось сохранить", 3500); });
}
function docCard(e) {
  return `<div class="it note doc" data-doc="${esc(e.id)}"><div class="bd"><b class="ntt">${esc(e.name)}</b><div class="ntm"><span class="ntd">${esc(ntWhen(e.mtime * 1000) || "")}</span><span class="ntf">${esc(String(e.path).split("/").slice(0, -1).join("/") || "Мои файлы")}</span><span class="ntf">${docSize(e.size)}</span></div></div></div>`;
}
/* «Облако Лиры» на телефоне (1.0.23 · 0.9.53; владелец 17.11: «сетевая флешка — закидываешь, и открывается с любого
   устройства»). Те же файлы, что в «Моих файлах» компьютеров (core/drive.py, сервер cloud/drive.php): список, открыть сам
   файл (скачать, расшифровать, открыть приложением телефона), добавить с телефона, убрать отовсюду. Шифр — ключ
   синхронизации (e2eKey, 14-sync.js), как у заметок; без него облако просит включить шифрование. Http приложения —
   текстом, поэтому куски ходят base64 (?b64=1, X-Drive-B64). */
const DRV = { st: null, busy: "", at: 0 };
const DRV_PART = 2 * 1024 * 1024, DRV_MAX = 25 * 1024 * 1024;
const DRV_EXT = /\.(pdf|docx|odt|xlsx|pptx|txt|md|csv|html?|jpe?g|png|webp)$/i;
const DRV_MIME = { pdf: "application/pdf", docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document", odt: "application/vnd.oasis.opendocument.text",
  xlsx: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", pptx: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  txt: "text/plain", md: "text/markdown", csv: "text/csv", html: "text/html", htm: "text/html", jpg: "image/jpeg", jpeg: "image/jpeg", png: "image/png", webp: "image/webp" };
const drvExt = (n) => (String(n).split(".").pop() || "").toLowerCase();
const drvKind = (n) => { const e = drvExt(n); return e === "pdf" ? "pdf" : /^(docx|odt)$/.test(e) ? "doc" : /^(xlsx|csv)$/.test(e) ? "sheet" : e === "pptx" ? "slides" : /^(jpe?g|png|webp)$/.test(e) ? "image" : "text"; };
const DRV_K = { pdf: "PDF", doc: "DOC", sheet: "XLS", slides: "PPT", image: "IMG", text: "TXT" };
function drvHdr(c, more) { const h = Object.assign({ Authorization: "Bearer " + c.token }, more || {}); if (c.link && c.link !== c.token) h["X-Sync-Link"] = c.link;
  h["X-Drive-Dev"] = (syncSt() || {}).device || ""; return h; }
async function drvReq(method, path, opts) {
  const c = syncCred(); if (!c) throw new Error("нужен ключ Dewiar или вход");
  const r = await http(method, c.base + "?p=" + path, Object.assign({ timeout: 60000 }, opts, { headers: drvHdr(c, (opts || {}).headers) }));
  let d = {}; try { d = JSON.parse(r.body || "{}"); } catch (e) { d = {}; }
  if (r.status >= 400) throw new Error((d.error && d.error.message) || "облако ответило " + r.status);
  return d;
}
async function drvLoad() {
  const k = e2eKey();
  if (!syncCred()) return (DRV.st = { why: "nokey", files: [] });
  if (!k) return (DRV.st = { why: "e2e", files: [] });
  const d = await drvReq("GET", "/drive", { timeout: 20000 });
  d.files = (d.files || []).map(f => { try { return Object.assign(f, JSON.parse(DC().fromUtf8(DC().unseal(k, DC().b64d(f.meta))))); } catch (e) { return null; } })
    .filter(f => f && f.name);
  DRV.at = Date.now();
  return (DRV.st = d);
}
const drvHex = (b) => [...b].map(x => x.toString(16).padStart(2, "0")).join("");
async function drvOpen(id) {
  const f = ((DRV.st || {}).files || []).find(x => x.id === id), k = e2eKey(); if (!f || !k) return;
  try {
    const parts = [];
    for (let n = 0; n < (f.parts || 1); n++) {
      DRV.busy = `Скачиваю «${f.name}» — ${Math.round(n / (f.parts || 1) * 100)} %`; drvBar();
      parts.push(DC().unseal(k, DC().b64d((await drvReq("GET", `/drive/get&id=${f.id}&n=${n}&b64=1`)).b64.replace(/\+/g, "-").replace(/\//g, "_"))));
    }
    const all = new Uint8Array(parts.reduce((s, p) => s + p.length, 0)); let o = 0; parts.forEach(p => { all.set(p, o); o += p.length; });
    if (f.sha && drvHex(DC().sha256(all)).slice(0, 32) !== f.sha) throw new Error("файл пришёл испорченным — попробуйте ещё раз");
    const b64 = btoa(Array.from({ length: Math.ceil(all.length / 0x8000) }, (_, i) => String.fromCharCode.apply(null, all.subarray(i * 0x8000, (i + 1) * 0x8000))).join(""));
    const mime = DRV_MIME[drvExt(f.name)] || "application/octet-stream";
    const w = D.saveOpenB64 ? D.saveOpenB64(f.name, mime, b64) : D.saveDownloadB64 ? D.saveDownloadB64(f.name, mime, b64) : "";
    toast(w ? "Сохранено в " + w : "Не получилось сохранить файл", 3500);
  } catch (e) { toast("Облако: " + e.message, 4500); }
  DRV.busy = ""; drvBar();
}
async function drvAdd(files) {
  const k = e2eKey(); if (!k) { toast("Сначала включите шифрование — облако хранит файлы только им", 4000); return; }
  for (const file of files) {
    if (!DRV_EXT.test(file.name)) { toast(`«${file.name}» — такие файлы облако не берёт`, 3500); continue; }
    if (file.size > DRV_MAX) { toast(`«${file.name}» больше 25 МБ`, 3500); continue; }
    try {
      const data = new Uint8Array(await file.arrayBuffer());
      const meta = DC().b64e(DC().seal(k, DC().utf8(JSON.stringify({ name: file.name, sha: drvHex(DC().sha256(data)).slice(0, 32), mtime: Math.round(Date.now() / 1000) }))));
      const id = drvHex(DC().randomBytes(12)), of = Math.max(1, Math.ceil(data.length / DRV_PART));
      for (let n = 0; n < of; n++) {
        DRV.busy = `Отправляю «${file.name}» — ${Math.round(n / of * 100)} %`; drvBar();
        const sealed = DC().seal(k, data.subarray(n * DRV_PART, (n + 1) * DRV_PART));
        await drvReq("POST", `/drive/put&id=${id}&n=${n}&of=${of}`, { body: DC().b64e(sealed).replace(/-/g, "+").replace(/_/g, "/"), timeout: 120000,
          headers: Object.assign({ "Content-Type": "text/plain", "X-Drive-B64": "1" }, n === 0 ? { "X-Drive-Meta": meta, "X-Drive-Size": String(data.length) } : {}) });
      }
      toast(`«${file.name}» — в облаке, скоро будет и на компьютерах`, 3000);
    } catch (e) { toast("Облако: " + e.message, 4500); }
  }
  DRV.busy = ""; await drvLoad().catch(() => {}); renderDay();
}
async function drvDel(id) {
  const f = ((DRV.st || {}).files || []).find(x => x.id === id); if (!f) return;
  if (!confirm(`Убрать «${f.name}» из облака? Файл пропадёт на всех ваших устройствах.`)) return;
  try { await drvReq("POST", "/drive/del", { body: { id }, headers: { "Content-Type": "application/json" } }); } catch (e) { toast("Облако: " + e.message, 4000); }
  await drvLoad().catch(() => {}); renderDay();
}
function drvBar() { const b = $("#drv-busy"); if (b) { b.textContent = DRV.busy; b.hidden = !DRV.busy; } }
const drvMB = (b) => b >= 1048576 ? (b / 1048576).toFixed(b >= 10485760 ? 0 : 1).replace(".", ",") + " МБ" : Math.max(1, Math.round(b / 1024)) + " КБ";
function drvHtml() {
  const st = DRV.st;
  if (!st) return `<div class="drv"><p class="hint">Открываю облако…</p></div>`;
  if (st.why) return `<div class="drv off"><b>Облако Лиры</b><p class="hint">${st.why === "e2e" ? "Облако хранит файлы зашифрованными — ключ есть только у ваших устройств. Включите шифрование, и файлы с компьютера будут здесь."
    : "Облаку нужен ключ Dewiar или вход аккаунтом."}</p>${st.why === "e2e" ? `<button class="btn p" id="drv-on">Включить шифрование</button>` : ""}</div>`;
  const used = st.used || 0, quota = st.quota || 200 * 1048576, pct = Math.min(100, Math.round(used / quota * 100));
  return `<div class="drv"><div class="drv-top"><span class="drv-ico" aria-hidden="true">☁️</span><div><b>Облако Лиры</b><small>${drvMB(used)} из ${drvMB(quota)} · на всех устройствах</small></div></div>`
    + `<div class="drv-bar"><i style="width:${pct}%"></i></div>`
    + `<label class="btn w drv-add"><input type="file" id="drv-file" multiple hidden accept=".pdf,.docx,.odt,.xlsx,.pptx,.txt,.md,.csv,.html,.jpg,.jpeg,.png,.webp">Добавить файл</label>`
    + `<p class="hint drv-busy" id="drv-busy"${DRV.busy ? "" : " hidden"}>${esc(DRV.busy)}</p>`
    + (st.files.length ? `<div class="drv-grid">` + st.files.map(f => { const kd = drvKind(f.name);
        return `<div class="drv-f k-${kd}" data-drv="${esc(f.id)}"><span class="drv-k">${DRV_K[kd]}</span><b>${esc(f.name)}</b><small>${drvMB(f.size)}</small>`
          + `<button class="x" data-drvx="${esc(f.id)}" aria-label="Убрать «${esc(f.name)}»">${X_SVG}</button></div>`; }).join("") + `</div>`
      : `<p class="hint">Пока пусто. Добавьте файл здесь или на компьютере в «Мои файлы» — он появится на всех ваших устройствах.</p>`)
    + `</div>`;
}
function drvWire(box) {
  const f = $("#drv-file", box); if (f) f.onchange = (e) => { const fs = [...e.target.files]; e.target.value = ""; drvAdd(fs); };
  const on = $("#drv-on", box); if (on) on.onclick = () => { e2eEnable(true); DRV.st = null; renderDay(); };
  $$("[data-drv]", box).forEach(el => el.onclick = (e) => { if (!e.target.closest("[data-drvx]")) drvOpen(el.dataset.drv); });
  $$("[data-drvx]", box).forEach(b => b.onclick = (e) => { e.stopPropagation(); drvDel(b.dataset.drvx); });
  if (!DRV.st || Date.now() - DRV.at > 60000) drvLoad().then(() => { if (dayTab === "notes" && ntFolder === DOC_F) renderDay(); }).catch(e => { DRV.st = { why: "", files: [], used: 0, quota: 0, err: e.message }; });
}
// «Мой день» — какой сегодня день: «Среда, 15 октября» (просьба 15.10: «почему он не пишет число и день недели?»)
function dayDate(d = new Date()) { const w = WD[d.getDay()]; return `${w[0].toUpperCase()}${w.slice(1)}, ${d.getDate()} ${MON[d.getMonth()]}`; }
/* Имя дела по расписанию (№557, 05.11): компьютер присылает title («Дача: заморозки и полив»); старый компьютер — только
   поручение модели, тогда — его первая фраза без «(weather)» и ссылок, как core/tools.job_short */
function jobShort(j) {
  if (j && j.title) return String(j.title);
  let t = String((j && j.text) || "").replace(/https?:\/\/\S+/g, "").replace(/\s*\((?:[a-z][a-z0-9_]*(?:\s*[,/]\s*[a-z][a-z0-9_]*)*)\)/g, "").replace(/\s+/g, " ").trim();
  const cut = /[.!?…;]\s+(?=[А-ЯЁA-Z«"])/.exec(t); if (cut) t = t.slice(0, cut.index + 1);   // без «взгляда назад»: старый Safari
  t = t.replace(/^[\s.;,]+|[\s.;,]+$/g, "");
  if (t.length > 80) t = t.slice(0, 80).replace(/\s+\S*$/, "").replace(/[\s,;:—–-]+$/, "") + "…";
  return t || "Дело по расписанию";
}
/* ---------- «Платежи» с компьютера на телефоне (№891, 19.11: «на телефоне раздела платежей нет, и Лира о них не знает») ----------
   Счета (bill) и оплаты (pay) приходят синхронизацией и только читаются: ведёт их компьютер (core/payments.py). Здесь — во
   вкладке «Деньги» блоком «Платежи» (нового раздела нет) и справкой Лире, когда спрашивают про оплаты. Срок и статус — как
   payments.status на компьютере: оплачено в этом периоде / просрочено / скоро (до 3 дней) / ждёт. */
function payStore() { try { const x = JSON.parse(prefGet("pays") || "{}"); return { bills: x.bills || {}, pays: x.pays || {} }; } catch (e) { return { bills: {}, pays: {} }; } }
function payApply(kind, id, d, del) {
  const st = payStore(), box = kind === "bill" ? st.bills : st.pays;
  if (del || !d || !Object.keys(d).length) delete box[id]; else box[id] = d;
  prefSet("pays", JSON.stringify(st));
}
function payPeriod(b, now) { return b.kind === "yearly" ? String(now.getFullYear()) : `${now.getFullYear()}-${pad(now.getMonth() + 1)}`; }
function payDue(b, now) {
  const day = Math.max(1, Math.min(31, +b.day || 0)); if (!+b.day) return null;
  const m = b.kind === "yearly" ? Math.max(1, Math.min(12, +b.month || 1)) - 1 : now.getMonth();
  const last = new Date(now.getFullYear(), m + 1, 0).getDate();
  return new Date(now.getFullYear(), m, Math.min(day, last));
}
function payRows(now) {
  now = now || new Date();
  const st = payStore(), pays = Object.values(st.pays);
  return Object.entries(st.bills).filter(([, b]) => b && b.name && !b.archived).map(([id, b]) => {
    const per = payPeriod(b, now), p = pays.filter(x => x.bill === id && x.period === per && x.status !== "unpaid").sort((a, c) => String(c.date).localeCompare(String(a.date)))[0];
    const due = payDue(b, now), left = due ? Math.round((due - new Date(now.getFullYear(), now.getMonth(), now.getDate())) / 864e5) : null;
    const status = p ? "paid" : b.autopay ? "auto" : left === null ? "wait" : left < 0 ? "overdue" : left <= 3 ? "soon" : "wait";   // как payments.status
    return { id, b, p, due, left, status };
  }).sort((a, c) => ({ overdue: 0, soon: 1, wait: 2, auto: 3, paid: 4 })[a.status] - ({ overdue: 0, soon: 1, wait: 2, auto: 3, paid: 4 })[c.status] || ((a.due || 0) - (c.due || 0)));
}
function payDueText(r) {
  if (r.status === "paid") return `оплачено ${r.p.amount ? +(+r.p.amount).toFixed(2) + " " : ""}${r.p.date ? "· " + String(r.p.date).split("-").reverse().slice(0, 2).join(".") : ""}`.trim();
  if (r.status === "auto") return "автоплатёж";
  if (!r.due) return "без срока";
  const d = `до ${r.due.getDate()} ${MON[r.due.getMonth()]}`;
  return r.status === "overdue" ? `просрочено — было ${d.slice(3)}` : r.left === 0 ? "срок сегодня" : r.left === 1 ? "срок завтра" : d;
}
function payHtml() {
  const rows = payRows(); if (!rows.length) return "";
  const left = rows.filter(r => r.status !== "paid" && r.status !== "auto").length;
  return `<div class="bugh">Платежи · ${left ? "не оплачено " + left : "всё оплачено"}</div>` + rows.map(r => `<div class="it pay ${r.status}"><div class="tm" aria-hidden="true">${esc(r.b.icon || "🧾")}</div><div class="bd"><b>${esc(r.b.name)}</b><small>${esc(payDueText(r))}${r.b.amount && r.status !== "paid" ? " · обычно " + esc(String(r.b.amount)) : ""}</small></div>${r.status === "paid" ? `<span class="pok" aria-label="Оплачено">✓</span>` : ""}</div>`).join("")
    + `<p class="hint" style="margin:6px 4px 10px">Платежи ведутся на компьютере: студия → «Платежи». Здесь видно, что оплачено и какие сроки.</p>`;
}
/* справка Лире: спросили про оплаты — что и когда платить (с компьютера) */
const PAY_ASK = /платеж|платёж|оплат|заплатил|коммунал|квартплат|кредит|рассроч|сч[её]т(?:а|ов)? за|сроки? оплат|что (?:надо |нужно )?(?:платить|оплатить)|газ|свет за|интернет за|подписк/i;
function payContext(text) {
  if (!PAY_ASK.test(String(text || ""))) return "";
  const rows = payRows(); if (!rows.length) return "";
  return "Платежи человека (ведутся на компьютере, сюда приходят синхронизацией; менять — на компьютере, студия → «Платежи»): "
    + rows.map(r => `${r.b.name} — ${payDueText(r)}`).join("; ") + ".";
}

function renderDay() {
  const box = $("#day-body"), dd = $("#day-date");
  if (dd) dd.textContent = dayDate();
  if (dayTab === "rem") {
    const l = JSON.parse(D.alarms() || "[]").sort((a, b) => a.at - b.at), ds = doneStats();
    const jobs = (mind().jobs || []).filter(j => !j.paused);       // дела по расписанию — их делает компьютер (утренняя сводка, итоги)
    box.innerHTML = doneHead(ds)
      + (ds.items.length ? `<div class="bugh">Сделано сегодня</div>` + ds.items.slice().reverse().map(x => { const d = new Date(x.at);
          return `<div class="it dn"><div class="ok">✓</div><div class="bd"><b>${esc(x.title)}</b><small>${pad(d.getHours())}:${pad(d.getMinutes())}${x.src === "pc" ? " · на компьютере" : x.src === "alarm" ? " · из напоминания" : ""}</small></div><button class="x" data-undo="${esc(x.id)}" title="Снять отметку" aria-label="Снять отметку">${X_SVG}</button></div>`; }).join("") : "")
      + (l.length ? `<div class="bugh">Напоминания</div>` + l.map(x => { const d = new Date(x.at), task = x.kind !== "alarm" && x.kind !== "timer";
          const nt = x.note ? notes().find(n => n.id === x.note) : null, img = nt && (nt.att || []).find(a => a.type === "image");
          // №556: время — строкой-заголовком над текстом (а не столбиком слева): тексту — вся ширина, пункты — с новой строки
          return `<div class="it rem" data-edit="${esc(x.id)}"><div class="bd"><div class="rh"><span class="tm">${pad(d.getHours())}:${pad(d.getMinutes())}</span><small>${x.kind === "alarm" ? "⏰ будильник" : x.kind === "timer" ? "⏱ таймер" : "🔔"} · ${esc(whenText(d))}${x.repeat ? " · " + repRu(x.repeat) : ""}${x.note ? ` · <span class="ntc">📎${nt ? noteAttCount(nt) || "" : ""}</span>` : ""}</small></div><b>${esc(x.title)}</b></div>`
            + (img ? `<img class="nthumb rt" data-note="${esc(x.note)}" src="${noteAttGet(img.id)}" alt="">` : "")
            + (task ? `<button class="x ok" data-done="${esc(x.id)}" title="Сделано" aria-label="Сделано">✓</button>` : "") + `<button class="x" data-id="${esc(x.id)}" title="Удалить" aria-label="Удалить">${X_SVG}</button></div>`; }).join("")
      : jobs.length || ds.items.length ? "" : `<div class="empty">Напоминаний нет.<br>Скажите: «напомни завтра в 9 позвонить маме» или «будильник на 7».<br>Сделали дело — скажите «я позвонила маме, отметь» или впишите его выше.</div>`)
      + (jobs.length ? `<div class="bugh">По расписанию — делает компьютер</div>` + jobs.map(j => { const d = new Date(j.at);
          return `<div class="it job"><div class="tm">${pad(d.getHours())}:${pad(d.getMinutes())}</div><div class="bd"><b>${esc(jobShort(j))}</b><small>${esc(j.repeat || whenText(d))}</small></div></div>`; }).join("")
        + `<p class="hint" style="margin:6px 4px 0">Изменить или выключить — на компьютере: студия → «Напоминания».</p>` : "")
      + (remHealth() ? remHealthBrief() : D.exactAlarms() ? "" : `<div class="card"><b>Будильники могут опаздывать</b><p class="hint">Разрешите точное время: «Будильники и напоминания».</p><button class="btn p" onclick="Dewiar.openSettings('alarms')">Разрешить</button></div>`);
    $$("[data-id]", box).forEach(b => b.onclick = (e) => { e.stopPropagation(); D.alarmCancel(b.dataset.id); syncSoon(); renderDay(); });
    $$("[data-note]", box).forEach(b => b.onclick = (e) => { e.stopPropagation(); openNoteSoon(b.dataset.note); });
    $$("[data-edit]", box).forEach(r => r.onclick = (e) => { if (!e.target.closest("button, img")) remEdit(r.dataset.edit); });   // нажали — править руками
    $$("[data-done]", box).forEach(b => b.onclick = () => { const x = l.find(i => i.id === b.dataset.done); if (!x) return;
      if (!x.repeat) { D.alarmCancel(x.id); syncSoon(); } celebrate(Object.assign(doneAdd([{ title: x.title, rid: x.id }], "tap"), { closed: [] })); renderDay(); });
    $$("[data-undo]", box).forEach(b => b.onclick = () => { const x = doneUndo(b.dataset.undo); renderDay(); if (x) toast("Отметка снята: " + x.title, 2000); });
    $$(".ach", box).forEach(b => b.onclick = () => toast(b.dataset.tip, 2600));
    const why = $("#done-why", box), seen = () => { if (!S.doneWhySeen) { S.doneWhySeen = true; saveS(); } };
    if (why) why.onclick = () => { doneWhy = !doneWhy; seen(); renderDay(); };
    if ($("#done-whyok", box)) { seen(); $("#done-whyok", box).onclick = () => { doneWhy = false; renderDay(); }; }
    const f = $("#done-add", box);
    f.onsubmit = (e) => { e.preventDefault(); const t = $("input", f).value.trim(); if (!t) { $("input", f).focus(); return; } markDone([t], "tap"); renderDay(); };
  } else if (dayTab === "notes") {
    const docs = docList(), folds = noteFolders().concat(docs.length || syncCred() ? [DOC_F] : []); if (ntFolder && !folds.includes(ntFolder)) ntFolder = "";
    const n = ntFolder === DOC_F ? [] : notes().filter(x => !ntFolder || String(x.folder || "").trim() === ntFolder).sort((a, b) => (+b.time || 0) - (+a.time || 0));   // новые сверху — и с компьютера тоже
    const chips = folds.length ? `<div class="ntfolds" role="tablist" aria-label="Папки">${["", ...folds].map(f => `<button role="tab" data-f="${esc(f)}" class="${f === ntFolder ? "on" : ""}${f === DOC_F ? " docf" : ""}" aria-selected="${f === ntFolder}">${f === DOC_F ? "Мои файлы" : f ? esc(f) : "Все"}</button>`).join("")}</div>` : "";
    box.innerHTML = `<button class="btn p ntnew" id="nt-new">Новая заметка</button>` + chips + (ntFolder === DOC_F
      ? drvHtml() + `<p class="hint ntdoc">${docN(docs.length)} с компьютера — спросите: «что в договоре про сроки?», Лира найдёт и без компьютера.</p><div class="ntlist">` + docs.map(docCard).join("") + `</div>`
      : n.length ? `<div class="ntlist">` + n.map(ntCard).join("") + `</div>`
      : `<div class="empty">Заметок нет.<br>Скажите: «запиши в заметки: купить хлеб и молоко» — или нажмите «Новая заметка».</div>`);
    $("#nt-new").onclick = () => openNote("");
    $$(".ntfolds button", box).forEach(b => b.onclick = () => { ntFolder = b.dataset.f; renderDay(); });
    $$(".it.note:not(.doc)", box).forEach(el => el.onclick = () => openNote(el.dataset.id));
    $$(".it.doc", box).forEach(el => el.onclick = () => docOpen(el.dataset.doc));
    if (ntFolder === DOC_F) drvWire(box);
  } else if (dayTab === "made") {
    const l = apps().slice().reverse();
    box.innerHTML = tasksHtml() + (l.length ? `<div class="bugh">Сделано на телефоне</div>` + l.map(x => `<div class="it"><div class="bd" data-open="${esc(x.id)}"><b>${esc(x.title)}</b><small>${esc(whenText(new Date(x.ts)))} · ${Math.max(1, Math.round(x.size / 1024))} КБ · нажмите, чтобы открыть</small></div><button class="x" data-id="${esc(x.id)}">${X_SVG}</button></div>`).join("")
      : Object.keys(mind().tasks).length ? "" : `<div class="empty">Пока ничего не сделано.<br>Скажите: «сделай презентацию о погоде на завтра» или «сделай игру в крестики-нолики».</div>`);
    wireTasks(box, renderDay);
    $$("[data-open]", box).forEach(b => b.onclick = () => openApp(b.dataset.open));
    $$(".x", box).forEach(b => b.onclick = () => { fileSave("app-" + b.dataset.id + ".html", ""); fileSave("apps.json", JSON.stringify(apps().filter(x => x.id !== b.dataset.id))); renderDay(); });
  } else {
    const r = moneyReport("month"), c = r.by[CUR] || Object.values(r.by)[0] || { inc: 0, exp: 0 }, cur = r.by[CUR] ? CUR : (Object.keys(r.by)[0] || CUR);
    const items = money().slice(-30).reverse();
    box.innerHTML = `<div class="sum"><div><b style="color:var(--good)">${+c.inc.toFixed(2)}</b><small>доходы</small></div><div><b style="color:#FF8FA8">${+c.exp.toFixed(2)}</b><small>расходы</small></div><div><b>${+(c.inc - c.exp).toFixed(2)}</b><small>остаток, ${cur}</small></div></div>`
      + payHtml() + (payRows().length && items.length ? `<div class="bugh">Записи</div>` : "")
      + (items.length ? items.map(x => `<div class="it"><div class="tm" style="color:${x.kind === "income" ? "var(--good)" : "#FF8FA8"};font-size:15px">${x.kind === "income" ? "+" : "−"}${x.amount}</div><div class="bd"><b>${esc(x.note || x.category)}</b><small>${esc(x.category)} · ${esc(x.date)} · ${esc(x.currency)}</small></div><button class="x" data-id="${esc(x.id)}">${X_SVG}</button></div>`).join("")
      : `<div class="empty">Записей нет.<br>Скажите: «купил кофе за восемь пятьдесят».</div>`);
    $$(".x", box).forEach(b => b.onclick = () => { saveMoney(money().filter(x => x.id !== b.dataset.id)); try { famDelSpend(b.dataset.id); } catch (e) { } renderDay(); });
  }
}

/* ---------- дела: «сделано» и достижения (отзыв 13.10: «геймификация — выполнил 3 дела, значки и достижения, в конце дня
   "ты сегодня сделал 5–7 дел"»; отчёт №14: «Отметь как исполненное» — нечем было отметить).
   Журнал done.json: {id, title, at (мс), src: voice|tap|alarm|pc, rid — напоминание, если закрыто им}. Он же уходит в
   синхронизацию видом «done» (core/done.py на компьютере — тот же формат и те же достижения: меняешь здесь — меняй и там).
   Достижения не хранятся — считаются по журналу (doneStats): так они одинаковы на телефоне и компьютере. Дневные рубежи
   (3, 5, 7, 10 дел за день) поздравляют каждый день; значки (ACHIEVE) — один раз, когда получены впервые. */
const DONE_F = "done.json", DONE_MAX = 1500, DAY_MILES = [3, 5, 7, 10];
const ACHIEVE = [
  { id: "d3", g: "day", n: 3, icon: "🥉", name: "Тройка", what: "3 дела за день" },
  { id: "d5", g: "day", n: 5, icon: "🥈", name: "Пятёрка", what: "5 дел за день" },
  { id: "d10", g: "day", n: 10, icon: "🥇", name: "Десятка", what: "10 дел за день" },
  { id: "s3", g: "streak", n: 3, icon: "🔥", name: "Три дня подряд", what: "дела три дня подряд" },
  { id: "s7", g: "streak", n: 7, icon: "⭐", name: "Неделя", what: "дела семь дней подряд" },
  { id: "s30", g: "streak", n: 30, icon: "🏆", name: "Месяц", what: "дела тридцать дней подряд" },
  { id: "t10", g: "total", n: 10, icon: "✨", name: "Первые десять", what: "10 дел всего" },
  { id: "t50", g: "total", n: 50, icon: "💪", name: "Полсотни", what: "50 дел всего" },
  { id: "t100", g: "total", n: 100, icon: "💯", name: "Сотня", what: "100 дел всего" },
  { id: "t500", g: "total", n: 500, icon: "👑", name: "Пятьсот", what: "500 дел всего" }];
const achVal = (a, s) => a.g === "day" ? s.bestDay : a.g === "streak" ? s.bestStreak : s.total;
function doneList() { try { const l = JSON.parse(fileGet(DONE_F) || "[]"); return Array.isArray(l) ? l : []; } catch (e) { return []; } }
function saveDone(l) {
  l = l.filter(x => x && x.id && x.title && +x.at).sort((a, b) => a.at - b.at).slice(-DONE_MAX);
  fileSave(DONE_F, JSON.stringify(l)); return l;
}
const dayKey = (t) => { const d = new Date(t); return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()); };
const delaRu = (n) => n % 10 === 1 && n % 100 !== 11 ? "дело" : [2, 3, 4].includes(n % 10) && ![12, 13, 14].includes(n % 100) ? "дела" : "дел";
const dnRu = (n) => n % 10 === 1 && n % 100 !== 11 ? "день" : [2, 3, 4].includes(n % 10) && ![12, 13, 14].includes(n % 100) ? "дня" : "дней";
function doneStats(l = doneList(), now = Date.now()) {
  const by = {}; l.forEach(x => { const k = dayKey(x.at); by[k] = (by[k] || 0) + 1; });
  const today = dayKey(now);
  let streak = 0, d = new Date(now); d.setHours(12, 0, 0, 0);
  if (!by[today]) d = new Date(d.getTime() - 864e5);                 // сегодня ещё пусто — серия идёт со вчера
  while (by[dayKey(d)]) { streak++; d = new Date(d.getTime() - 864e5); d.setHours(12, 0, 0, 0); }
  let best = 0, run = 0, prev = null;
  for (const k of Object.keys(by).sort()) { const t = new Date(k + "T12:00").getTime(); run = prev !== null && Math.round((t - prev) / 864e5) === 1 ? run + 1 : 1; prev = t; best = Math.max(best, run); }
  const s = { today: by[today] || 0, items: l.filter(x => dayKey(x.at) === today), streak, bestStreak: best, bestDay: Math.max(0, ...Object.values(by)), total: l.length, byDay: by };
  s.earned = ACHIEVE.filter(a => achVal(a, s) >= a.n);
  return s;
}
/* Записать сделанное: list — [{title, rid}] или строки. -> {items, stats, fresh (новые значки), mile (дневной рубеж или 0)} */
function doneAdd(list, src = "tap", at = Date.now()) {
  const l = doneList(), before = doneStats(l, at), items = [];
  for (const it of [].concat(list)) {
    const o = typeof it === "string" ? { title: it } : it, title = String(o.title || "").replace(/\s+/g, " ").trim().slice(0, 120);
    if (!title) continue;
    const t = title[0].toUpperCase() + title.slice(1);
    items.push({ id: "d" + at.toString(36) + Math.random().toString(36).slice(2, 7), title: t, at: +o.at || at + items.length, src, rid: o.rid || "" });
  }
  const after = doneStats(saveDone(l.concat(items)), at);
  const fresh = ACHIEVE.filter(a => achVal(a, after) >= a.n && achVal(a, before) < a.n);
  const mile = DAY_MILES.filter(m => before.today < m && after.today >= m).pop() || 0;
  if (items.length) syncSoon();
  return { items, stats: after, fresh, mile };
}
function doneUndo(id) { const l = doneList(), x = l.find(i => i.id === id); if (!x) return null; saveDone(l.filter(i => i.id !== id)); syncSoon(); return x; }
// напоминание на сегодня, которое и есть это дело: «я позвонила Игорю» ↔ «позвонить Игорю» (основы слов по 4 буквы)
const stems = (t) => String(t || "").toLowerCase().replace(/ё/g, "е").split(/[^a-zа-я0-9]+/).filter(w => w.length > 2 && !/^(это|как|для|что|все|уже|мне|меня|надо|нужно|сделал[аи]?|сделать)$/.test(w)).map(w => w.slice(0, 4));
// в экзамене напоминания — его песочница (exam.js), не настоящие
const examOn = () => typeof EXAM !== "undefined" && !!EXAM;
function remDrop(id) { if (examOn()) { EXAM.alarms = EXAM.alarms.filter(x => x.id !== id); return; } D.alarmCancel(id); syncSoon(); }
// совпадение — и хотя бы одно не глаголом: «позвонил маме» ≠ «позвонить в банк» (общий только «позв»), как done._hit_ok
const VERB_END = /(?:ть|ться|ти|[аеиоуыяю]л|[аеиоуыяю]л[аи]|лся|лась|лись)$/;
function hitOk(title, said) {
  const words = String(title || "").toLowerCase().replace(/ё/g, "е").split(/[^a-zа-я0-9]+/).filter(w => w.length > 2 && !/^(это|как|для|что|все|уже|мне|меня|надо|нужно|сделал[аи]?|сделать)$/.test(w));
  if (!words.length) return 0;
  const hits = words.filter(w => said.includes(w.slice(0, 4))); if (!hits.length) return 0;
  const nouns = words.filter(w => !VERB_END.test(w));
  if (nouns.length && !hits.some(w => nouns.includes(w))) return 0;
  return hits.length / words.length;
}
// ahead — на сегодня не нашлось: и разовое на ближайшие 36 часов («я позвонил в банк» в 22:40, а план — на завтра в 13)
function remMatch(title, now = Date.now(), ahead = true) {
  const w = stems(title); if (!w.length) return null;
  const ends = [Math.max(new Date(now).setHours(23, 59, 59, 0), now + 3 * 3600e3)];   // поздно вечером — и сразу после полуночи
  if (ahead) { const tm = new Date(now + 864e5); tm.setHours(23, 59, 59, 0); ends.push(Math.max(now + 36 * 3600e3, +tm)); }   // и весь завтрашний день (экзамен 25.10)
  for (const end of ends) {
    let best = null, bs = 0;
    for (const x of alarmsNow()) {
      if (x.kind === "timer" || x.kind === "alarm" || (!x.repeat && x.at > end)) continue;
      const sc = hitOk(x.title, w);
      if (sc >= 0.5 && sc > bs) { best = x; bs = sc; }
    }
    if (best) return best;
  }
  return null;
}
/* Отметить дела (инструмент и кнопки): подходящее разовое напоминание на сегодня закрывается, повторяющееся остаётся. */
function markDone(titles, src) {
  const closed = [], list = [];
  for (const t of titles) {
    const m = remMatch(t);
    if (m) { if (!m.repeat) { remDrop(m.id); closed.push(m.title); } list.push({ title: m.title, rid: m.id }); }
    else list.push({ title: t });
  }
  const r = doneAdd(list, src); r.closed = closed;
  celebrate(r);
  return r;
}
function doneSay(r) {
  const s = r.stats, ach = r.fresh.map(a => `${a.icon} «${a.name}» — ${a.what}`).join("; ");
  return `Отмечено сделанным: ${r.items.map(x => "«" + x.title + "»").join(", ")}.` + (r.closed.length ? ` Напоминание закрыто: ${r.closed.join(", ")}.` : "")
    + ` Сегодня сделано ${s.today} ${delaRu(s.today)}` + (s.streak >= 2 ? `, ${s.streak} ${dnRu(s.streak)} подряд` : "") + ", всего " + s.total + "."
    + (ach ? ` Новое достижение: ${ach}.` : r.mile ? ` Рубеж дня: ${r.mile} ${delaRu(r.mile)}!` : "")
    + " Похвали коротко и тепло, одной фразой" + (ach ? ", назови достижение" : "") + "; не перечисляй дела заново.";
}
/* План дня и «сделано» — без модели, как core/dayplan.py (отзыв 17.10: «Запланируй на сегодня: в 13 позвонить в банк,
   в 16 тренировка, в 19 купить подарок маме» — «записала», а в «Делах» пусто: модель писала в календарь). Меняешь здесь —
   меняй и там. На каждое дело — напоминание; дело без времени — на 20:00; прошедшее время сегодня — на завтра. */
const PLAN_RX = /^\s*(?:[а-я]+,\s*)?(?:(?:а|и|ну|пожалуйста|слушай)\s+)*(?:(?:за|с)планируй(?:те)?(?:\s+(?:мне|нам))?(?:\s+(?:дела|задачи))?|(?:составь|запиши|сделай|создай)(?:те)?\s+(?:мне\s+)?план(?:\s+(?:дел|дня))?|(?:добавь|внеси|поставь|запиши)(?:те)?\s+(?:мне\s+)?в\s+(?:мой\s+)?план(?:\s+(?:дел|дня|на\s+день))?|(?:мой\s+|мои\s+)?(?:план|планы|дела|задачи)\s+(?=на\s+(?:сегодня|завтра|послезавтра|день)))([\s\S]*)$/;
const PLAN_NOT = /календар|встреч|созвон с|совещан|мероприят|отпуск|поездк|путешеств|бюджет|ремонт|свадьб|меню(?![а-я])/;
const PLAN_REMIND = /^\s*(?:[а-я]+,\s*)?(?:напомни(?:те)?|поставь(?:те)?\s+(?:мне\s+)?напоминани[яе])\s+([\s\S]*)$/;
const PLAN_TIME = /(?:^|[^а-я])(?:в|к|на)\s+\d{1,2}(?:[:.]\d{2})?(?:\s*(?:час[а-я]*|ч(?![а-я])))?(?:\s+(?:утра|дня|вечера|ночи))?|(?:^|[^а-я])(?:утром|днем|вечером)(?![а-я])/;
const PLAN_EVENING = 20;
function restoreCase(what, raw) {
  const o = {}; for (const w of String(raw || "").match(/[\p{L}\d-]+/gu) || []) { const k = w.toLowerCase().replace(/ё/g, "е"); if (!(k in o)) o[k] = w; }
  return String(what).split(" ").map(w => /^\d+$/.test(w) ? w : (o[w] || w)).join(" ");
}
const capFirst = (t) => t ? t[0].toUpperCase() + t.slice(1) : t;
// распознавание речи запятых не ставит: «в 13 позвонить в банк в 16 тренировка» — делим по времени, как dayplan._by_time
const PLAN_T = /(?:^|[^а-я])((?:в|к)\s+\d{1,2}(?:[:.]\d{2})?(?:\s+(?:часов|часа|час))?(?:\s+(?:утра|дня|вечера|ночи))?)(?![\d:])/g;
function planByTime(p) {
  const marks = [...p.matchAll(PLAN_T)].map(m => ({ start: m.index + m[0].length - m[1].length, end: m.index + m[0].length }));
  if (marks.length < 2) return [p];
  const cuts = marks[0].start === 0 ? marks.slice(1).map(m => m.start) : marks.slice(0, -1).map(m => m.end);
  const out = []; let last = 0;
  for (const c of cuts) { out.push(p.slice(last, c)); last = c; }
  out.push(p.slice(last));
  return out.map(x => x.replace(/^[\s.:—,-]+|[\s.:—,-]+$/g, "")).filter(Boolean);
}
function planParse(text, now = new Date()) {
  const raw = String(text || "").replace(/\s+/g, " ").trim();
  if (!raw || /\?\s*$/.test(raw) || raw.includes("\n\nВложения:")) return null;
  const t = raw.toLowerCase().replace(/ё/g, "е");
  let m = t.match(PLAN_RX), remind = false;
  if (!m) { m = t.match(PLAN_REMIND); remind = true; if (!m) return null; }
  let rest = m[1];
  if (PLAN_NOT.test(rest)) return null;
  let day = "";
  const dm = rest.slice(0, 40).match(/(?:^|[^а-я])(?:на\s+)?(сегодня|завтра|послезавтра|день)(?![а-я])/);
  if (dm) { day = dm[1] === "день" ? "" : dm[1]; rest = rest.slice(0, dm.index) + " " + rest.slice(dm.index + dm[0].length); }
  rest = rest.replace(/^\s*(?:мне|нам|такие|следующие|вот|дела|задачи)\s+/, " ").replace(/^[\s:—,.-]+|[\s:—,.-]+$/g, "");
  const segs = rest.split(/\s*(?:[,;\n]|\.\s+|\s—\s)\s*|\s+(?:и|а\s+потом|потом|затем|а)\s+(?=(?:в|к)\s+\d)/).map(x => (x || "").replace(/^[\s.:—-]+|[\s.:—-]+$/g, "")).filter(Boolean).flatMap(planByTime);
  if (!segs.length || segs.length > 12) return null;
  const timed = segs.filter(x => PLAN_TIME.test(x));
  if (remind && timed.length < 2) return null;              // одно «напомни…» — обычное напоминание (модель)
  if (!remind && !timed.length && segs.length < 2) return null;   // «запланируй отпуск» — не план дня
  const today = new Date(now); today.setHours(0, 0, 0, 0);
  const base = new Date(today.getTime() + ({ "завтра": 1, "послезавтра": 2 }[day] || 0) * 864e5);
  const items = [];
  for (let x of segs) {
    if (PLAN_TIME.test(x)) {
      x = x.replace(/(^|[^а-я])(в|к)\s+([1-7])(?![\d:.])(?!\s*(?:час[а-я]*\s+)?(?:утра|ночи))/, (_, a, b, h) => `${a}${b} ${+h + 12}`);   // «в 3 забрать детей» — 15:00
      const w = parseWhen((day && day !== "сегодня" ? day + " " : "") + x, now);
      if (!w || w.rel || w.repeat) return null;
      const what = remindWhat(w.rest).replace(/^(?:и|а|еще|также)\s+/, "");
      if (!what) return null;
      items.push({ text: capFirst(restoreCase(what, raw)), at: w.at, moved: w.at >= new Date(base.getTime() + 864e5) && !(day === "завтра" || day === "послезавтра") });
    } else {
      const what = x.replace(/^(?:и|а|еще|также)\s+/, "").trim();
      if (what.length < 3 || what.split(" ").length > 10) return null;
      let at = new Date(base); at.setHours(PLAN_EVENING, 0, 0, 0); let moved = false;
      if (at <= now) { at = new Date(at.getTime() + 864e5); moved = true; }
      items.push({ text: capFirst(restoreCase(what, raw)), at, moved, untimed: true });
    }
  }
  return { items, day: base, today };
}
function planSay(p, now = new Date()) {
  const loose = p.items.filter(x => x.untimed), items = p.items.filter(x => !x.untimed).sort((a, b) => a.at - b.at);
  const low = (x) => /^.[А-ЯЁA-Z]/.test(x.text) ? x.text : x.text[0].toLowerCase() + x.text.slice(1);
  const hm = (d) => pad(d.getHours()) + ":" + pad(d.getMinutes()), dk = (d) => Math.round((new Date(d).setHours(0, 0, 0, 0) - new Date(now).setHours(0, 0, 0, 0)) / 864e5);
  const dname = (d) => ({ 0: "сегодня", 1: "завтра", 2: "послезавтра" })[dk(d)] || `${d.getDate()} ${MON[d.getMonth()]}`;
  const all = items.concat(loose), days = [...new Set(all.map(x => dk(x.at)))];
  let out;
  if (days.length === 1) {
    const lst = items.map(x => `${hm(x.at)} — ${low(x)}`).concat(loose.length ? [loose.map(low).join(", ")] : []).join("; ");
    let head = all.length > 1 ? `Записал план на ${dname(all[0].at)}` : `Записал в план на ${dname(all[0].at)}`;
    if (all.some(x => x.moved) && p.day.getTime() === p.today.getTime()) head = `Сегодня это время уже прошло — записал план на ${dname(all[0].at)}`;
    out = `${head}: ${lst}.`;
  } else {
    const by = {}; all.slice().sort((a, b) => a.at - b.at).forEach(x => (by[dk(x.at)] = by[dk(x.at)] || []).push(x));
    out = "Записал план: " + Object.keys(by).sort().map(k => capFirst(dname(by[k][0].at)) + " — " + by[k].map(x => (x.untimed ? "" : hm(x.at) + " ") + low(x)).join("; ")).join(". ") + ".";
    if (all.some(x => x.moved)) out += " Что уже прошло сегодня — перенёс на завтра.";
  }
  if (loose.length) out += ` ${loose.length > 1 ? "Дела" : "Дело"} без времени — напомню в ${PLAN_EVENING}:00.`;
  return out + " Сделаете — скажите, и я отмечу.";
}
function planQuick(text) {                          // и в экзамене: экзамен идёт тем же путём, что человек (addAlarm — в песочницу)
  const p = planParse(text); if (!p) return null;
  const made = p.items.map(x => addAlarm(x.text, x.at, "reminder", ""));
  plog("info", "🗓 план дня (без модели): " + made.map(x => `${whenText(new Date(x.at))} ${x.title}`).join("; "));
  setTimeout(() => openDone(false), 400);           // сразу видно: «Мой день» → «Дела»
  return { say: planSay(p) };
}
const DONE_PAST = "[а-я]+(?:л|ла|ли|лся|лась|лись)";
const DONE_EXPLICIT = [
  /^(?:отметь(?:те)?|отмечай|поставь(?:те)?\s+(?:галочку|отметку))(?:\s+(?:мне|пожалуйста))?(?:\s*,?\s*что\s+)?(?:\s+(?:как|что)?\s*(?:сделанн[а-я]*|выполненн[а-я]*|исполненн[а-я]*|готов[а-я]*|сделано|выполнено))?\s*[:,—-]?\s*(?:что\s+)?(.+)$/,
  /^(?:готово|сделано|выполнено|галочка)\s*[,:—-]?\s+(.+)$/,
  /^(.+?)\s*[—:-]?\s+(?:готово|сделано|выполнено)$/,
  // экзамен 0.9.18: «Лира, я позвонила Игорю и сделала тренировку. Отметь как исполненное» — просьба отметить в конце
  /^(.+?)\s*[.,;!—-]?\s+(?:отметь(?:те)?|отмечай|засчитай)(?:\s+(?:мне|пожалуйста|это|их|всё|все|оба|обе))*(?:\s+(?:как|что)?\s*(?:сделанн[а-я]*|выполненн[а-я]*|исполненн[а-я]*|готов[а-я]*|сделано|выполнено))?$/];
const DONE_IMPLICIT = new RegExp("^(?:(?:ну|так|всё|все|итак|кстати)\\s*,?\\s+)?(?:я\\s+)?(?:уже\\s+|только\\s+что\\s+|сегодня\\s+)?(" + DONE_PAST + "(?:\\s.+)?)$");
const DONE_NOT = /(?:^|[^а-я])(?:не|вчера|завтра|хочу|хотел[аи]?|надо|нужно|буду|будем|собираюсь|планирую|может|если|забыл[аи]?|напомни|когда|зачем|почему|сколько|отмени|сними|убери)(?![а-я])/;
function doneParse(text) {
  const raw = String(text || "").replace(/\s+/g, " ").trim();
  let t = raw.toLowerCase().replace(/ё/g, "е").replace(/[\s.!]+$/, "");
  t = t.replace(/^([а-я]+),\s*(?=\S)/, (m0, w) => findPersona(w, true) ? "" : m0);
  if (!t || /\?$/.test(t) || t.length > 160) return null;
  if (/^(?:отметь|отмечай|поставь)/.test(t) && /(?:^|[^а-я])(?:не|ошибк|сним)|календар|карт[еуа]|заметк|будильник|напоминани/.test(t)) return null;
  let explicit = false, x = null;
  for (const rx of DONE_EXPLICIT) { const m = t.match(rx); if (m && m[1].trim()) { explicit = true; x = m[1]; break; } }
  if (x === null) {
    if (DONE_NOT.test(t) || t.split(" ").length > 12) return null;
    const m = t.match(DONE_IMPLICIT); if (!m) return null; x = m[1];
  } else if (/(?:^|[^а-я])(?:не|завтра|буду|надо|нужно)(?![а-я])/.test(x)) return null;
  const parts = x.split(new RegExp("\\s*[,;]\\s*|\\s+(?:и|а\\s+еще|а\\s+также|потом|еще)\\s+(?=(?:я\\s+)?" + DONE_PAST + "(?![а-я]))"));
  const items = parts.map(p => (p || "").replace(/^[\s.:—-]+|[\s.:—-]+$/g, "").replace(/^(?:(?:я|и|уже|еще|также)\s+)+/, "").replace(/\s+(?:уже|сегодня|только что|готово|сделано)$/, "").trim())
    .filter(p => p.length >= 3).map(p => capFirst(restoreCase(p, raw)));
  return items.length ? { items, explicit } : null;
}
function doneSpeak(r) {
  const n = r.stats.today, a = r.fresh[r.fresh.length - 1];
  let out = `Отметил ${r.items.map(x => "«" + x.title + "»").join(", ")}.`;
  out += a ? ` Сегодня уже ${n} ${delaRu(n)} — новое достижение «${a.name}»!` : r.mile ? ` Уже ${n} ${delaRu(n)} за сегодня — так держать!` : ` Сегодня ${n === 1 ? "это первое дело" : "уже " + n + " " + delaRu(n)}.`;
  if (r.stats.streak >= 2 && (a || r.mile || n === 1)) out += ` Серия — ${r.stats.streak} ${dnRu(r.stats.streak)} подряд.`;
  return out;
}
function doneQuick(text) {
  const d = doneParse(text); if (!d) return null;
  if (!d.explicit && !d.items.every(t => remMatch(t))) return null;   // «я позвонил в банк» — только если это дело из плана
  const r = markDone(d.items, "voice");
  plog("info", "✓ сделано (без модели): " + r.items.map(x => x.title).join("; "));
  if (SANDBOX) SANDBOX.dev.push({ name: "mark_done", args: d.items.join("; "), argsObj: { items: d.items }, t: Date.now() });   // экзамен: действие видно
  if ($("#sh-day.on") && dayTab === "rem") renderDay();
  return { say: doneSpeak(r) };
}
/* «Освободи место», «почисти телефон», «сколько места занимает Dewiar» (18.10) — без модели и без подсказки ей: чистить
   чужие приложения Android никому не даёт (с Android 6), поэтому честно: свой кэш чистим сами, а для остального
   открываем системное «Хранилище» — там Android показывает, что занимает место, и сам предлагает очистку.
   «Очисти память» сюда не входит — это про память помощницы. */
const FREE_RX = /^(?:(?:освободи|освободить|почисти|почистить|очисти|очистить|разгреби)\s+(?:мне\s+)?(?:место|телефон|хранилище|мусор|кэш|кеш)(?:\s+(?:на\s+)?телефон[еа]?)?|(?:мало|не\s+хватает|кончается|закончилось|заканчивается)\s+(?:места|память)(?:\s+(?:на\s+)?телефон[еа]?)?|сколько\s+(?:места\s+)?(?:занимает|весит)\s+(?:dewiar|девиар|приложение|ты)(?:\s+места)?)$/;
const mbRu = (b) => b >= 1e9 ? (b / 1e9).toFixed(1).replace(".", ",") + " ГБ" : Math.max(1, Math.round(b / 1e6)) + " МБ";
function freeSpaceQuick(t) {
  if (!FREE_RX.test(t) || !D.appSize || examOn()) return null;       // в экзамене настоящий кэш не трогаем
  let z = {}; try { z = JSON.parse(D.appSize() || "{}"); } catch (e) { }
  const asks = /^сколько/.test(t), total = (+z.cache || 0) + (+z.data || 0);
  if (asks) return { say: `Dewiar занимает около ${mbRu(total)}: ${mbRu(+z.data || 0)} — ваши заметки, настройки и журнал, ${mbRu(+z.cache || 0)} — временные файлы. Скажите «освободи место» — почищу временные.` };
  const freed = D.clearOwnCache ? +D.clearOwnCache() || 0 : 0;
  setTimeout(() => D.openStorage && D.openStorage(), 2500);
  plog("info", `🧹 освободи место: свой кэш −${mbRu(freed)}, открываю «Хранилище»`);
  return { say: `Почистил свои временные файлы — ${freed >= 1e6 ? "освободилось " + mbRu(freed) : "их почти не было"}. Открываю «Хранилище»: там Android покажет, что занимает место, и предложит очистку. Чужие приложения я чистить не могу — так устроен Android.` };
}
/* «Что я умею» (18.10: «у нас есть функции, про которые никто не знает») — data/tricks.json (tricks.js при сборке), те же
   фразы, что в студии. Нажатие — сказать фразу; фраза с «…» (дописать своё) — в поле ввода. Только то, что есть на телефоне. */
function openTricks() { renderTricks(); setTimeout(() => openSheet("#sh-tricks"), 30); }   // после клика: иначе тот же клик закрыл бы лист
function renderTricks() {
  const T = window.DEWIAR_TRICKS || { groups: [] }, box = $("#tricks-body");
  box.innerHTML = `<p class="hint" style="margin:0 2px 12px">Скажите или нажмите — так работает и голосом. Где «…» — допишите своё.</p>` + T.groups.map(g => {
    const it = g.items.filter(x => (x.where || []).includes("phone") && !x.key);
    return it.length ? `<div class="trg"><h3>${g.icon || ""} ${esc(g.name)}</h3><div class="card trl">${it.map(x =>
      `<button class="trk" ${x.fill ? `data-fill="1" data-say="${esc(x.say)}"` : `data-say="${esc(x.say)}"`}><b>«${esc(x.say)}»</b><small>${esc(x.what)}</small></button>`).join("")}</div></div>` : "";
  }).join("");
  $$(".trk", box).forEach(b => b.onclick = () => {
    const say = b.dataset.say;
    closeSheets();
    if (b.dataset.fill) { $("#typebox").classList.add("on"); $("#typed").value = say.replace(/…$/, " ").replace(/:\s*…?$/, ": "); typedGrow(); setTimeout(() => $("#typed").focus(), 250); return; }
    setTimeout(() => ask(say), 200);
  });
}
/* Праздник: короткий тост на каждое дело; рубеж дня и новый значок — конфетти, вибрация и карточка. */
function celebrate(r) {
  if (!r.items.length) return;
  const s = r.stats, big = r.fresh.length || r.mile;
  toast(`✓ ${r.items.length === 1 ? r.items[0].title : r.items.length + " " + delaRu(r.items.length)} — сегодня ${s.today}`, 2600);
  try { D.vibrate(big ? 60 : 25); } catch (e) { }
  if (!big) return;
  confetti();
  const a = r.fresh[r.fresh.length - 1];
  // отзыв 16.10: «нужен крестик, и чтобы по нажатию было понятно, что это за награды» — карточка ведёт в «Мой день» → «Дела»
  // (там все значки и объяснение), ✕ — убрать; пока объяснение не открывали, внизу подсказка «Что это за награды?»
  showCard(`<div class="achc" id="achc" role="button" tabindex="0" aria-label="Открыть дела и достижения">${a ? `<i>${a.icon}</i><div class="achb"><b>${esc(a.name)}</b><small>Новое достижение · ${esc(a.what)}</small>`
    : `<i>🎉</i><div class="achb"><b>${r.mile} ${delaRu(r.mile)} за сегодня</b><small>${s.streak >= 2 ? s.streak + " " + dnRu(s.streak) + " подряд · " : ""}так держать</small>`}`
    + `<em>${S.doneWhySeen ? "Все значки — в «Мой день»" : "Что это за награды? Нажмите"}</em></div><button class="achx" aria-label="Убрать">${X_SVG}</button></div>`);
  const c = $("#achc"); if (!c) return;
  c.onclick = (e) => { if (e.target.closest(".achx")) { e.stopPropagation(); showCard(""); return; } openDone(!S.doneWhySeen); };
  c.onkeydown = (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openDone(!S.doneWhySeen); } };
}
/* «Мой день» → «Дела»: сделанное, серия и все значки; why — сразу с объяснением, зачем это */
let doneWhy = false;
function openDone(why) {
  showCard(""); doneWhy = !!why;
  openSheet("#sh-day"); dayTab = "rem"; $$("#day-tabs button").forEach(x => x.classList.toggle("on", x.dataset.t === "rem")); renderDay();
}
function confetti() {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const box = document.createElement("div"); box.className = "confetti"; box.setAttribute("aria-hidden", "true");
  const col = ["#8B8CF7", "#4BE3A1", "#FFC978", "#FF8FA8", "#7FD4FF", "#fff"];
  for (let i = 0; i < 36; i++) {
    const p = document.createElement("i");
    p.style.cssText = `left:${(Math.random() * 100).toFixed(1)}%;background:${col[i % col.length]};animation-delay:${(Math.random() * .35).toFixed(2)}s;`
      + `--dx:${(Math.random() * 120 - 60).toFixed(0)}px;--r:${(Math.random() * 720 - 360).toFixed(0)}deg;width:${6 + (i % 3) * 2}px`;
    box.appendChild(p);
  }
  document.body.appendChild(box); setTimeout(() => box.remove(), 2200);
}
/* «Сделано ✓» в уведомлении напоминания (AlarmReceiver) — телефон кладёт в pref done_inbox, здесь забираем. */
function doneInbox() {
  let q = []; try { q = JSON.parse(prefGet("done_inbox") || "[]") || []; } catch (e) { }
  if (!q.length) return;
  let rest = []; try { rest = (JSON.parse(prefGet("done_inbox") || "[]") || []).filter(x => !q.some(y => y.id === x.id && y.at === x.at)); } catch (e) { }
  prefSet("done_inbox", JSON.stringify(rest));                       // уведомление могло добавить ещё одно, пока читали
  const r = doneAdd(q.map(x => ({ title: x.title, rid: x.id, at: +x.at || Date.now() })), "alarm");
  if (r.fresh.length || r.mile) celebrate(r);
  if ($("#sh-day.on") && dayTab === "rem") renderDay();
}
N.on("done_inbox", () => doneInbox());
function doneReport(days) {
  const d = Math.max(1, Math.min(60, +days || 1)), l = doneList(), s = doneStats(l), from = new Date(); from.setHours(0, 0, 0, 0); from.setDate(from.getDate() - d + 1);
  const it = l.filter(x => x.at >= from.getTime()), by = {};
  it.forEach(x => (by[dayKey(x.at)] = by[dayKey(x.at)] || []).push(x.title));
  const next = ["day", "streak", "total"].map(g => ACHIEVE.find(a => a.g === g && achVal(a, s) < a.n)).filter(Boolean);
  return (it.length ? (d === 1 ? `Сегодня сделано ${it.length} ${delaRu(it.length)}: ` + by[dayKey(Date.now())].join("; ")
      : `За ${d} ${dnRu(d)} сделано ${it.length} ${delaRu(it.length)}:\n` + Object.entries(by).map(([k, v]) => `${k.slice(8)}.${k.slice(5, 7)}: ${v.join("; ")}`).join("\n"))
    : (d === 1 ? "Сегодня пока ничего не отмечено." : `За ${d} ${dnRu(d)} ничего не отмечено.`))
    + `\nСерия: ${s.streak} ${dnRu(s.streak)} подряд (лучшая — ${s.bestStreak}). Всего: ${s.total}. Лучший день: ${s.bestDay}.`
    + `\nДостижения: ${s.earned.length ? s.earned.map(a => a.icon + " " + a.name).join(", ") : "пока нет"}.`
    + (next.length ? ` Следующие: ${next.map(a => `${a.icon} ${a.name} (${a.what}, сейчас ${achVal(a, s)})`).join("; ")}.` : "");
}
function donePrompt() { return doneRules() + " " + doneNow(); }
/* правила — в общей подсказке; сколько сделано сегодня — в личной справке (меняется с каждой отметкой) */
function doneRules() {
  return "ДЕЛА И ДОСТИЖЕНИЯ. «Запланируй на сегодня…», «план на день», «мои дела на завтра» — это дела, не календарь: на каждое дело — свой set_reminder с его временем. Встреча, запись к мастеру, дело со временем («запиши встречу с Ирой на вторник в 12», «завтра в 13 у меня массаж», «в 8:10 встреча с Максимом») — тоже дело: set_reminder на это время, не заметка; «напомни за день / за час» — ещё один set_reminder на то время. В календарь — только если прямо сказано «в календарь». Поставил(а) или отметил(а) дело — подтверди одной фразой только его; остальные дела и планы вслух не перечисляй, пока не спросят: рядом могут быть чужие люди (19.10: «перед клиентами начал вслух перечислять то, что касается только меня»). Пользователь говорит, что сделал дело («я позвонила Игорю и сделала тренировку», «отметь как исполненное», «готово, купил хлеб») — "
    + "вызови mark_done (каждое дело — отдельной строкой, коротко: «Позвонить Игорю», «Тренировка»), подходящее напоминание закроется само; потом похвали коротко, одной фразой. "
    + "Отметил по ошибке — mark_done с undo. «Что я сегодня сделал», «мои достижения» — done_report.";
}
function doneNow() {
  const s = doneStats();
  return `Дела сейчас: сегодня сделано ${s.today} ${delaRu(s.today)}` + (s.items.length ? ` (${s.items.slice(-6).map(x => x.title).join("; ")})` : "")
    + (s.streak >= 2 ? `, серия ${s.streak} ${dnRu(s.streak)} подряд` : "") + `, всего ${s.total}.`;
}

/* ---------- календарь телефона (Cal.java: Android-календарь — в нём Google и другие аккаунты человека, без паролей) ----------
   Читать — свободно (разрешение спрашивается при первом вопросе). Записать — только после «да» человека: calendar_add без
   confirmed ничего не пишет, а говорит модели, о чём спросить, и предупреждает о встречах в то же время. Нет доступа или
   календаря для записи — открываем окно новой встречи в приложении «Календарь», сохраняет человек. Чужое не правим.
   В экзамене — песочница EXAM.calendar: настоящий календарь не трогаем. */
const CAL_R = "android.permission.READ_CALENDAR", CAL_W = "android.permission.WRITE_CALENDAR";
const WD_SHORT = ["вс", "пн", "вт", "ср", "чт", "пт", "сб"];
function calParse(x) {                                       // «2026-10-15» (весь день) или «2026-10-15T15:00» (местное)
  const m = /^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{1,2}):(\d{2}))?/.exec(String(x || "").trim());
  if (!m) return null;
  const d = new Date(+m[1], +m[2] - 1, +m[3], m[4] ? +m[4] : 0, m[5] ? +m[5] : 0);
  return isNaN(d) ? null : { ms: d.getTime(), allDay: !m[4] };
}
function calWhen(e) {
  const b = new Date(e.begin), en = new Date(e.end), day = `${WD_SHORT[b.getDay()]} ${b.getDate()} ${MON[b.getMonth()]}`;
  if (e.all_day) return day + ", весь день";
  const same = en.toDateString() === b.toDateString();
  return `${day}, ${pad(b.getHours())}:${pad(b.getMinutes())}–${same ? "" : `${en.getDate()} ${MON[en.getMonth()]} `}${pad(en.getHours())}:${pad(en.getMinutes())}`;
}
const calLine = (e) => `${calWhen(e)} — ${e.title || "без названия"}${e.location ? ` (${e.location})` : ""}`;
/* -> встречи за период или null — доступа к календарю не дали */
async function calEvents(from, to) {
  if (examOn()) return (EXAM.calendar || []).filter(e => e.end > from && e.begin < to).sort((a, b) => a.begin - b.begin);
  if (typeof D.calEvents !== "function") return [];
  let r = JSON.parse(D.calEvents(JSON.stringify({ from, to })) || "{}");
  if (r.need) { if (!(await needPerm(r.need))) return null; r = JSON.parse(D.calEvents(JSON.stringify({ from, to })) || "{}"); }
  if (r.error) throw new Error("календарь не прочитался: " + r.error);
  return r.events || [];
}
/* Планы на дни [from, to) не из календаря: запомненное «со слов пользователя» с датой «(на ДД.ММ.ГГГГ» (factQuick, remember)
   и напоминания. Экзамен 0.6.42: «запомни: в среду встреча» запомнено, а на «что у меня в среду?» модель посмотрела только
   календарь — «пусто». -> текст для модели или "". */
function dayPlans(from, to) {
  const facts = memArr().filter(f => { const m = /\(на (\d\d)\.(\d\d)\.(\d{4})/.exec(f); if (!m) return false;
    const t = new Date(+m[3], +m[2] - 1, +m[1]).getTime(); return t >= from && t < to; });
  let rem = []; try { rem = alarmsNow().filter(x => x.at >= from && x.at < to).sort((x, y) => x.at - y.at); } catch (e) { }
  if (!facts.length && !rem.length) return "";
  return (facts.length ? "\nЕщё на эти дни — из памяти (пользователь сам просил запомнить): " + facts.map(f => f.replace(/^Со слов пользователя:\s*/, "")).join("; ") : "")
    + (rem.length ? "\nНапоминания: " + rem.slice(0, 10).map(x => `${pad(new Date(x.at).getHours())}:${pad(new Date(x.at).getMinutes())} — ${x.title}`).join("; ") : "")
    + "\nНазови и это — это тоже планы пользователя.";
}
// «что у меня в среду?», «какие планы на завтра?», «есть ли дела в пятницу?» -> dayPlans на этот день или ""
function agendaPlans(text) {
  const t = String(text || "");
  if (!/(?:что|какие|есть ли|чем)[^.!?]{0,40}(?:у меня|у нас|план|дел[ао]?(?![а-яё])|встреч|занят)|(?:мои|мой)\s+(?:планы|день|дела)/i.test(t)) return "";
  let d = dayOf(t);
  if (!d && /(?:по\s+плану|какие\s+(?:у\s+(?:меня|нас)\s+)?(?:планы|дела)|что\s+у\s+(?:меня|нас)\s+(?:сегодня|на\s+сегодня)?\s*$)/i.test(t.replace(/[?!.]+$/, ""))) { d = new Date(); d.setHours(0, 0, 0, 0); }   // «что у нас по плану?» — сегодня
  if (!d) return "";
  const today = new Date(); today.setHours(0, 0, 0, 0);
  // «в среду» в среду: и сегодня, и через неделю — «в среду в 15:00» после 15:00 запомнилось на следующую (тестер 28.10)
  const wk = d.getTime() === today.getTime() && /(?:в|во|на)\s+(?:воскресенье|понедельник|вторник|среду|четверг|пятницу|субботу)/i.test(t)
    ? dayPlans(d.getTime() + 7 * 864e5, d.getTime() + 8 * 864e5) : "";
  return (dayPlans(d.getTime(), d.getTime() + 864e5) + wk).replace(/(Назови и это — это тоже планы пользователя\.)([\s\S]*)\1/, "$2$1");
}
// «сегодня», «завтра», «послезавтра», «в/на среду» (ближайшая, сегодня — сегодня), «21 октября», «21.10» -> полночь дня или null
function dayOf(text) {
  const t = String(text || "").toLowerCase().replace(/ё/g, "е"), d = new Date(); d.setHours(0, 0, 0, 0);
  if (LBRX("(?<![а-я])послезавтра", "").test(t)) { d.setDate(d.getDate() + 2); return d; }
  if (LBRX("(?<![а-я])завтра", "").test(t)) { d.setDate(d.getDate() + 1); return d; }
  if (LBRX("(?<![а-я])сегодня", "").test(t)) return d;
  const wd = /(?:в|во|на)\s+(воскресенье|понедельник|вторник|среду|четверг|пятницу|субботу)/.exec(t);
  if (wd) { const n = ["воскресенье", "понедельник", "вторник", "среду", "четверг", "пятницу", "субботу"].indexOf(wd[1]); d.setDate(d.getDate() + (n - d.getDay() + 7) % 7); return d; }
  const dm = /(\d{1,2})\s+(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)/.exec(t) || /(\d{1,2})\.(\d{1,2})(?!\d)/.exec(t);
  if (dm) { const m = isNaN(+dm[2]) ? MON.indexOf(dm[2]) : +dm[2] - 1, x = new Date(d.getFullYear(), m, +dm[1]); if (x < d) x.setFullYear(x.getFullYear() + 1); return x; }
  return null;
}
async function calendarList(a) {
  const st = a.from ? calParse(a.from) : null, d0 = st ? new Date(st.ms) : new Date();
  const from = new Date(d0.getFullYear(), d0.getMonth(), d0.getDate()).getTime();
  const days = Math.max(1, Math.min(31, Math.round(+a.days || 1))), to = from + days * 864e5;
  const plans = a.query ? "" : dayPlans(from, to);
  let ev = await calEvents(from, to);
  if (ev === null && plans) return "Календарь телефона недоступен (нет разрешения)." + plans;
  if (ev === null) return "Доступ к календарю не разрешён. Скажи пользователю одной фразой: чтобы я видела календарь, разрешите доступ — спрошу снова при следующем вопросе. Не выдумывай встреч.";
  const q = String(a.query || "").toLowerCase().trim();
  if (q) { const w = stems(q); ev = ev.filter(e => { const t = (e.title + " " + e.location).toLowerCase(); return t.includes(q) || (w.length && stems(t).some(x => w.includes(x))); }); }
  const span = days === 1 ? `${WD[new Date(from).getDay()].replace(/а$/, "у")}, ${new Date(from).getDate()} ${MON[new Date(from).getMonth()]}` : `${days} дн. с ${new Date(from).getDate()} ${MON[new Date(from).getMonth()]}`;
  if (!ev.length) return `В календаре на ${span}${q ? ` по «${a.query}»` : ""} ничего нет.` + plans;
  return `Календарь на ${span}${q ? ` по «${a.query}»` : ""} (${ev.length}):\n` + ev.slice(0, 40).map(calLine).join("\n")
    + (ev.length > 40 ? `\n…и ещё ${ev.length - 40}.` : "") + plans + "\nРасскажи главное коротко, своими словами; не добавляй встреч, которых здесь нет.";
}
async function calendarAdd(a) {
  const st = calParse(a.start);
  if (!st) return "Ошибка: нужно начало — дата и время ГГГГ-ММ-ДДTЧЧ:ММ (или только дата — на весь день). Посчитай от текущей даты.";
  const title = String(a.title || "").replace(/\s+/g, " ").trim().slice(0, 200) || "Встреча";
  const mins = Math.max(5, Math.min(24 * 60, Math.round(+a.minutes || 60)));
  const e = { title, begin: st.ms, end: st.allDay ? st.ms + 864e5 : st.ms + mins * 6e4, all_day: st.allDay, location: String(a.location || "").trim().slice(0, 200) };
  if (!st.allDay && e.begin < Date.now() - 5 * 6e4) return `Ошибка: ${calWhen(e)} уже прошло — уточни у пользователя дату.`;
  const what = calLine(e);
  if (a.confirmed !== true) {
    let busy = [];
    try { busy = ((await calEvents(e.begin, e.end)) || []).filter(x => !x.all_day); } catch (x) { }
    return `Ещё не записано. Спроси пользователя одной фразой: «Записать в календарь: ${what}?»`
      + (busy.length ? ` Предупреди, что в это время уже есть: ${busy.slice(0, 3).map(x => x.title).join("; ")}.` : "")
      + " Только после его «да» вызови calendar_add снова с теми же данными и confirmed: true; без «да» не говори, что записала.";
  }
  if (examOn()) { (EXAM.calendar = EXAM.calendar || []).push(Object.assign({ id: uid("ec"), made: Date.now() }, e)); return `Записано в календарь: ${what}.`; }
  const insert = () => typeof D.calOpenInsert === "function" && D.calOpenInsert(JSON.stringify(e));
  let r = JSON.parse(D.calAdd(JSON.stringify(e)) || "{}");
  if (r.need) {
    if (await needPerm(r.need)) r = JSON.parse(D.calAdd(JSON.stringify(e)) || "{}");
    else return insert() ? `Доступа к календарю нет — открыла окно новой встречи (${what}). Скажи: проверьте и нажмите «Сохранить».` : "Ошибка: доступа к календарю нет.";
  }
  if (r.error === "no_calendar") return insert() ? `В телефоне нет календаря для записи — открыла окно новой встречи в «Календаре» (${what}). Скажи: проверьте и нажмите «Сохранить».` : "Ошибка: в телефоне нет календаря для записи — нужно приложение «Календарь» или аккаунт Google.";
  if (r.error) return "Ошибка: " + r.error;
  return `Записано в календарь «${r.calendar}»: ${what}${st.allDay ? "" : ". Календарь напомнит за 15 минут"}.`;
}

/* ---------- маршрут на карте (отзыв 13.10: «Лира берёт геоточку, открывает карту и предлагает короткий пешеходный маршрут
   дворами»). Куда — адрес, место, координаты или ссылка на карту (Яндекс, Google, geo:, короткая — по переадресации).
   Адрес → координаты через OpenStreetMap (Nominatim); маршрут строит приложение карт от того места, где человек сейчас —
   пешком оно и ведёт кратчайшим путём, дворами. Яндекс Карты, если стоят (иначе Google). Как core/route.py. ---------- */
const ROUTE_MODES = { walk: ["pd", "walking"], transit: ["mt", "transit"], car: ["auto", "driving"], bike: ["bc", "bicycling"] };
const ROUTE_RU = { walk: "пешком", transit: "на транспорте", car: "на машине", bike: "на велосипеде" };
const geoOk = (a, b) => a >= -90 && a <= 90 && b >= -180 && b <= 180 && !(a === 0 && b === 0);
function parseCoords(text) {
  let t = String(text || ""); try { t = decodeURIComponent(t); } catch (e) { }
  const NR = "(-?\\d{1,3}\\.\\d{3,})", AN = "(-?\\d{1,3}(?:\\.\\d+)?)";   // голые числа — с 3+ знаками; в ссылке — любые
  if (/yandex/i.test(t)) {                            // сначала сама точка (pt, «что здесь»), потом маршрут, потом центр карты
    for (const p of ["(?:[?&]pt=|whatshere\\[point\\]=)", "rtext=[^&]*~", "[?&]ll="]) {
      const m = t.match(LBRX(p + AN + "\\s*,\\s*" + AN));
      if (m) { const a = +m[1], b = +m[2]; if (p.startsWith("rtext")) return geoOk(a, b) ? [a, b] : null; return geoOk(b, a) ? [b, a] : null; }
    }
  }
  for (const p of ["geo:" + AN + ",\\s*" + AN, "@" + AN + "," + AN, "[?&](?:q|query|destination|daddr|ll)=" + AN + "\\s*,\\s*" + AN, "(?<![\\d.])" + NR + "\\s*[,; ]\\s*" + NR + "(?![\\d.])"]) {
    const m = t.match(LBRX(p)); if (m && geoOk(+m[1], +m[2])) return [+m[1], +m[2]];
  }
  return null;
}
const isShortMap = (t) => /https?:\/\/(?:yandex\.\w+\/maps\/-\/|maps\.app\.goo\.gl\/|goo\.gl\/maps\/|go\.2gis\.com\/)\S+/.test(String(t || ""));
async function geocode(q) {
  q = String(q || "").trim(); if (!q) return null;
  try {
    const r = await http("GET", "https://nominatim.openstreetmap.org/search?" + new URLSearchParams({ q, format: "jsonv2", limit: "1", "accept-language": "ru" }),
      { headers: { "User-Agent": "Dewiar/1 (https://dewiar.pro)" }, timeout: 12000 });
    const x = (JSON.parse(r.body || "[]") || [])[0]; if (!x) return null;
    const a = +x.lat, b = +x.lon; return geoOk(a, b) ? [a, b, String(x.display_name || q)] : null;
  } catch (e) { return null; }
}
function routeUrl(app, dest, origin, mode, scheme) {
  const [yrt, gm] = ROUTE_MODES[mode] || ROUTE_MODES.walk, pt = (p) => Array.isArray(p) ? `${(+p[0]).toFixed(6)},${(+p[1]).toFixed(6)}` : String(p);
  if (app === "yandex" && Array.isArray(dest) && (!origin || Array.isArray(origin)))
    return (scheme ? "yandexmaps://maps.yandex.ru/" : "https://yandex.ru/maps/") + `?rtext=${origin ? pt(origin) : ""}~${pt(dest)}&rtt=${yrt}`;
  if (app === "yandex") return (scheme ? "yandexmaps://maps.yandex.ru/" : "https://yandex.ru/maps/") + "?" + new URLSearchParams({ text: pt(dest) });
  const q = { api: "1", destination: pt(dest), travelmode: gm }; if (origin) q.origin = pt(origin);
  return "https://www.google.com/maps/dir/?" + new URLSearchParams(q);
}
async function routeTool(a) {
  const to = String(a.to || "").trim(); if (!to) return "Ошибка: не понял, куда — спроси адрес или место.";
  const mode = ROUTE_MODES[a.mode] ? a.mode : "walk";
  let apps = []; try { apps = JSON.parse(D.apps() || "[]"); } catch (e) { }
  const hasY = apps.some(n => /яндекс.?карты|yandex.?maps/i.test(n));
  const app = a.app === "google" || a.app === "yandex" ? a.app : (hasY || !apps.some(n => /^(карты|maps|google maps)$/i.test(n)) ? "yandex" : "google");
  let src = to;
  if (isShortMap(to)) { try { const r = await http("GET", to.match(/https?:\/\/\S+/)[0], { timeout: 12000 }); src = (r.url || "") + " " + (r.body || "").slice(0, 200000); } catch (e) { } }
  let c = parseCoords(src), name = c ? "" : to;
  if (!c && !/^https?:\/\//.test(to)) { const g = await geocode(to); if (g) { c = [g[0], g[1]]; name = g[2]; } }
  let o = null;
  if (a.from) { o = parseCoords(a.from); if (!o) { const g = await geocode(a.from); o = g ? [g[0], g[1]] : a.from; } }
  const dest = c || to, url = routeUrl(app, dest, o, mode, false);
  const opened = (app === "yandex" && hasY && D.openUrl(routeUrl(app, dest, o, mode, true))) || D.openUrl(url);
  const where = name ? name.split(",").slice(0, 3).join(",") : c ? `${c[0].toFixed(5)}, ${c[1].toFixed(5)}` : "";
  const appRu = app === "yandex" ? "Яндекс Картах" : "Google Картах";
  if (!opened) return "Ошибка: карта не открылась — скажи об этом и предложи открыть ссылку: " + url;
  if (!c && app === "yandex") return `Открыла поиск «${where}» в ${appRu}: точное место не нашлось — пусть выберет его на карте и нажмёт «Маршрут». Скажи это одной-двумя фразами.`;
  return `Открыла маршрут ${ROUTE_RU[mode]} до «${where}» в ${appRu}, от того места, где пользователь сейчас.`
    + (mode === "walk" ? " Пешком карта ведёт кратчайшим путём — и дворами, и тропинками; время в пути видно на карте." : "")
    + " Скажи коротко, одной-двумя фразами, что маршрут открыт; не выдумывай улицы и время.";
}

// «готово» о результате фоновой задачи, которой ещё нет; «сообщу, когда будет готово» — честно (как EARLY_DONE_RX в engine_brain.py)
function earlyDone(t) {
  t = String(t || "").toLowerCase();
  return LBRX("(?<![а-яё])(готово|готова|готов|сделал[аи]?|сделано|закончил[аи]?|вот\\s+(?:она|он|ваш[аи]?|тво[яй]|презентаци|отч[её]т|документ))(?![а-яё])", "").test(t)
    && !/сообщ|пришлю|когда\s+(?:будет|закончу|всё)|как\s+только|в\s+фоне|займ[её]т|начал|взял|приступ|уже\s+работа|работаю|передал/.test(t);
}
/* ---------- «Что нового» (отзыв 13.10: «что было в обновлении — непонятно, пришлось догадываться»). После обновления — лист
   с новым и тем, как попробовать (фраза в «» — нажмите, и Лира её услышит). Текст — data/whatsnew.json (тот же у компьютера,
   сборка кладёт его в whatsnew.js). Уже виденное — pref news_seen; новая установка листа не показывает. ---------- */
const verCmp = (a, b) => { const x = String(a || "").split(".").map(n => parseInt(n, 10)), y = String(b || "").split(".").map(n => parseInt(n, 10));   // «0.9.38-web» — 38, а не NaN (0.96)
  for (let i = 0; i < 3; i++) if ((x[i] || 0) !== (y[i] || 0)) return (x[i] || 0) - (y[i] || 0); return 0; };
function newsList(from, to, all) {
  return (window.DEWIAR_NEWS || []).filter(r => (!from || verCmp(r.phone, from) > 0) && verCmp(r.phone, to) <= 0)
    .map(r => Object.assign({}, r, { items: (r.items || []).filter(i => (i.where || ["phone"]).includes("phone")) })).filter(r => r.items.length).slice(0, all ? 500 : 3);
}
function newsShow(list, all) {
  if (!list.length) return false;
  let v = list[0].phone;                                   // версия — та, что стоит (в её выпуске новое могло быть только у компьютера)
  try { const cur = JSON.parse(D.info() || "{}").version; if (cur && verCmp(cur, v) > 0 && /^\d+\.\d+\.\d+$/.test(cur)) v = cur; } catch (e) { }
  // идея №57 (29.10): «Что нового» по всем выпускам — с заголовком версии над пунктами
  $("#news-body").innerHTML = `<p class="nwsub">${all ? `Все выпуски — ${list.length}, новые сверху` : `Dewiar ${esc(v)} — вот что появилось`}</p>` + list.map(r => (all ? `<h3 class="nwv">${esc(r.phone)}${r.date ? ` <small>${esc(new Date(r.date + "T12:00").toLocaleDateString("ru-RU", { day: "numeric", month: "long" }))}</small>` : ""}</h3>` : "") + r.items.map(i => {
    const ph = /^«(.+)»$/.exec(String(i.try || "").trim());
    return `<div class="nwi"><i aria-hidden="true">${esc(i.icon || "✨")}</i><div><b>${esc(i.title)}</b><p>${esc(i.text)}</p>`
      + (ph ? `<button class="nwtry" data-say="${esc(ph[1])}">Попробовать: «${esc(ph[1])}»</button>` : i.try ? `<small>${esc(i.try)}</small>` : "") + `</div></div>`; }).join("")).join("")
    + (kidsOn() ? "" : `<div class="nwidea"><span aria-hidden="true">💡</span><p>Что Лире уметь дальше? Поддержите голосом нужное или предложите своё.</p><button class="btn" id="nw-ideas">Идеи</button></div>`)
    + `<button class="btn p w" id="nw-ok">Понятно</button>`;
  $("#nw-ok").onclick = () => closeSheets();
  if ($("#nw-ideas")) $("#nw-ideas").onclick = () => { closeSheets(); setTimeout(() => openIdeas(), 200); };   // 0.61: «Что нового» → «Идеи Лиры»
  $$(".nwtry", $("#news-body")).forEach(b => b.onclick = () => { closeSheets(); if (state !== "idle") interrupt(true); ask(trL(b.dataset.say)); });
  openSheet("#sh-news");
  return true;
}
function newsCheck() {
  let v = ""; try { v = JSON.parse(D.info() || "{}").version || ""; } catch (e) { }
  if (!v) return false;
  const seen = prefGet("news_seen");
  if (seen === v) return false;
  prefSet("news_seen", v);
  if (!seen && !(S.llm.base_url || history.length)) return false;     // только что установили — новостей нет, есть знакомство
  if (seen && verCmp(v, seen) < 0) return false;
  if ($(".sheet.on") || busy) return false;
  plog("info", `✨ что нового: ${seen || "?"} → ${v}`);
  return newsShow(newsList(seen, v));
}

/* ---------- сделанное: мини-программы и страницы, которые ассистент сделал прямо на телефоне (make_app) ----------
   Программа сразу открывается на экране — иначе после «Готово» непонятно, где её взять; хранится в «Мой день» →
   «Сделанное» (последние 40: файлы app-<id>.html и список apps.json), её можно сохранить в «Загрузки».
   Показ — в отдельном окне без моста Dewiar (openHtmlView → HtmlView.java): код, написанный моделью, не достаёт до ключей и телефона. */
const apps = () => { try { return JSON.parse(fileGet("apps.json") || "[]") || []; } catch (e) { return []; } };
function saveApp(title, html) {
  const id = uid("a");
  fileSave("app-" + id + ".html", html);
  const l = apps().concat([{ id, title: String(title).slice(0, 60), ts: Date.now(), size: html.length }]);
  l.slice(0, -40).forEach(x => fileSave("app-" + x.id + ".html", ""));
  fileSave("apps.json", JSON.stringify(l.slice(-40)));
  return l[l.length - 1];
}
const appHtml = (id) => fileGet("app-" + id + ".html") || "";
function appCard(ap) {
  return `<div class="appc"><b>${esc(ap.title)}</b><small>сделано сейчас · откроется на весь экран</small><div class="row2"><button class="btn p" onclick="openApp('${ap.id}')">Открыть</button><button class="btn" onclick="saveAppDl('${ap.id}')">В «Загрузки»</button></div></div>`;
}
function openApp(id) {
  const ap = apps().find(x => x.id === id), html = appHtml(id);
  if (!ap || !html) { toast("Не нашёл — возможно, удалена"); return; }
  openHtmlView(ap.title, html, () => saveAppDl(id));
}
function saveAppDl(id) {
  const ap = apps().find(x => x.id === id), html = appHtml(id);
  if (!ap || !html) return;
  const name = (ap.title.replace(/[\\/:*?"<>|]/g, " ").trim() || "Dewiar") + ".html";
  const where = D.saveDownload ? D.saveDownload(name, "text/html", html) : "";
  toast(where ? "Сохранено: " + where + " — откроется в браузере" : "Не получилось сохранить", 3500);
}

/* ---------- файлы результатов задач: компьютер или облако кладут их в облако (?p=/files), здесь — открыть и сохранить.
   HTML (страница, презентация, программа) открывается тут же, в том же безопасном окне, что и «Сделанное»; остальное
   сохраняется в «Загрузки/Dewiar». ---------- */
/* Что открывается прямо в приложении: страницы — как есть, текст и код — моноширинным текстом, картинки — картинкой;
   остальное (pptx, docx, zip…) — «В «Загрузки»» и откроется в своей программе. */
const VIEWABLE = /\.(?:html?|md|txt|log|csv|tsv|json|ya?ml|srt|vtt|py|js|ts|css|sh|java|kt|c|cpp|h|go|rs|php|sql|xml|ini|toml|png|jpe?g|gif|webp|svg)$/i;
function fileViewHtml(name, b64, type) {
  const page = (body) => `<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><body style="margin:0;background:#101018;color:#e8e8f0;font:14px/1.5 system-ui">${body}</body>`;
  if (/\.html?$/i.test(name)) return b64text(b64);
  if (/\.(?:png|jpe?g|gif|webp|svg)$/i.test(name)) {
    const mime = type || (/\.svg$/i.test(name) ? "image/svg+xml" : /\.png$/i.test(name) ? "image/png" : /\.gif$/i.test(name) ? "image/gif" : /\.webp$/i.test(name) ? "image/webp" : "image/jpeg");
    return page(`<img src="data:${mime};base64,${b64}" style="display:block;max-width:100%;margin:0 auto">`);
  }
  return page(`<pre style="margin:0;padding:14px;white-space:pre-wrap;word-break:break-word;font:13px/1.45 ui-monospace,monospace">${esc(b64text(b64))}</pre>`);
}
function taskFiles(t) {
  const f = t.files || [];
  if (!f.length) return (t.outputs || []).length ? `<small class="hint">Файлы на компьютере: ${t.outputs.map(esc).join(", ")}</small>` : "";
  return `<div class="tfiles">${f.map(x => `<div class="tf"><span>${esc(x.title || x.name)}<small>${esc(x.name)} · ${fsize(x.size)}</small></span>`
    + (VIEWABLE.test(x.name) ? `<button class="btn p" data-fo="${esc(x.id)}" data-fn="${esc(x.name)}">Открыть</button>` : "")
    + `<button class="btn" data-fs="${esc(x.id)}" data-fn="${esc(x.name)}">В «Загрузки»</button></div>`).join("")}</div>`;
}
const fsize = (n) => n > 1048576 ? (n / 1048576).toFixed(1) + " МБ" : Math.max(1, Math.round((n || 0) / 1024)) + " КБ";
function wireFiles(root) {
  $$("[data-fo]", root).forEach(b => b.onclick = (e) => { e.stopPropagation(); taskFileOpen(b.dataset.fo, b.dataset.fn); });
  $$("[data-fs]", root).forEach(b => b.onclick = (e) => { e.stopPropagation(); taskFileSave(b.dataset.fs, b.dataset.fn); });
}
async function taskFileGet(id) {
  const c = syncCred(); if (!c) throw new Error("нет входа в аккаунт или ключа Dewiar");
  const r = await http("GET", c.base + "?p=/files&b64=1&id=" + encodeURIComponent(id), { headers: { Authorization: "Bearer " + c.token }, timeout: 60000 });
  let d = {}; try { d = JSON.parse(r.body || "{}"); } catch (e) { }
  if (r.status >= 400 || !d.b64) throw new Error((d.error && d.error.message) || "файл не скачался (" + r.status + ")");
  return d;
}
const b64text = (b) => { try { return decodeURIComponent(escape(atob(b))); } catch (e) { return atob(b); } };
async function taskFileOpen(id, name) {
  try { toast("Открываю…", 1200); const d = await taskFileGet(id); openHtmlView(name.replace(/\.html?$/i, ""), fileViewHtml(name, d.b64, d.type), () => taskFileSave(id, name, d)); }
  catch (e) { plog("warn", "файл задачи: " + e.message); toast("Не открылся: " + e.message, 4000); }
}
async function taskFileSave(id, name, got) {
  try {
    const d = got || await taskFileGet(id);
    const where = D.saveDownloadB64 ? D.saveDownloadB64(d.name || name, d.type || "application/octet-stream", d.b64)
      : (D.saveDownload ? D.saveDownload(d.name || name, d.type || "text/plain", b64text(d.b64)) : "");
    toast(where ? "Сохранено: " + where : "Не получилось сохранить", 3500);
  } catch (e) { plog("warn", "файл задачи: " + e.message); toast("Не сохранился: " + e.message, 4000); }
}
let htmlViewSave = null;
function openHtmlView(title, html, onSave) {
  // на телефоне — отдельное окно без моста Dewiar (HtmlView.java): мост виден во всех фреймах, iframe sandbox не защищает;
  // iframe ниже — в браузере (проверки и веб-версия): sandbox без allow-same-origin — у программы чужое происхождение, ключей сайта она не видит
  if (D.viewHtml && !D.mock) { htmlViewSave = onSave; if (D.viewHtml(String(title || ""), String(html || ""))) return; }
  let v = $("#appview");
  if (!v) { v = document.createElement("div"); v.id = "appview"; document.body.appendChild(v); }
  v.innerHTML = `<div class="avh"><b>${esc(title)}</b><button class="btn" id="av-dl">В «Загрузки»</button><button class="ib" id="av-x" title="Закрыть">${X_SVG}</button></div><iframe sandbox="allow-scripts allow-forms allow-modals" title="${esc(title)}"></iframe>`;
  $("iframe", v).srcdoc = html;
  v.classList.add("on");
  $("#av-x").onclick = () => { v.classList.remove("on"); v.innerHTML = ""; };
  $("#av-dl").onclick = onSave;
}
/* задача закончилась — карточка в разговоре: итог и файлы, чтобы не искать их по меню */
function taskDoneCard(id) {
  const t = mind().tasks[id]; if (!t) return;
  showCard(`<div class="appc task-done"><b>${t.status === "done" ? "✓" : "⚠"} ${esc(t.title)}</b><small>${t.status === "done" ? "задача готова" + (t.where === "cloud" ? " · сделано в облаке Dewiar" : " · сделано на компьютере") : esc(String(t.error || "не вышло").slice(0, 160))}</small>`
    + (t.result ? `<div class="tres">${mdLite(String(t.result).slice(0, 700))}</div>` : "") + taskFiles(t) + `</div>`);
  wireFiles($("#card"));
}

/* ---------- душа: дневник, душа персонажа, конституция, задачи (с компьютера) ---------- */
let soulTab = "diary";
$$("#soul-tabs button").forEach(b => b.onclick = () => { soulTab = b.dataset.t; $("#soul-body").dataset.edit = ""; $$("#soul-tabs button").forEach(x => x.classList.toggle("on", x === b)); renderSoul(); });
$("#b-soul").onclick = () => { renderSoul(); openSheet("#sh-soul"); syncSoon(); };

