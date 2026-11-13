/* Студия: «Чат» — вся переписка с персонажами (просьба 14.10: «на компьютере не понятно, где наша с Лирой переписка; на
   телефоне это есть»). Лента — из ядра (chat_list, core/chatlog.py): что человек сказал голосом или написал и что ответили,
   по дням, старые сверху; «Показать раньше» подгружает предыдущие. Новые реплики приходят событием chat; пока модель
   отвечает — живой пузырь из событий answer. Внизу — поле: написать текстом (то же, что сказать, — команда say).
   Пузыри — те же, что в «Близких» (.cl-m), чтобы переписка везде выглядела одинаково. */
const CH = { items: [], more: false, loaded: false, live: null, busy: false, view: {}, info: new Set(), editing: "", regen: "", threads: [], tid: "" };
function chatWho(pid) { return (personas || []).find(p => p.id === pid) || null; }
function chatDay(ts) {
  const d = new Date(ts * 1000), now = new Date(), y = new Date(now); y.setDate(now.getDate() - 1);
  if (d.toDateString() === now.toDateString()) return "Сегодня";
  if (d.toDateString() === y.toDateString()) return "Вчера";
  return d.toLocaleDateString("ru-RU", { day: "numeric", month: "long", year: d.getFullYear() === now.getFullYear() ? undefined : "numeric" });
}
const chatSize = (n) => n < 1024 * 1024 ? Math.max(1, Math.round(n / 1024)) + " КБ" : (n / 1048576).toFixed(1).replace(".", ",") + " МБ";
/* 0.86 (пользователь: «стандартные для всех чатов вещи — остановка, перегенерация, исправление и метрики»):
   «Ещё раз» кладёт новый ответ в ту же запись, прежние — в x.vars; листать ‹ 1/2 › — только просмотр (Лира продолжает
   от последнего варианта). chatShown — запись с тем вариантом, что сейчас на экране. */
function chatShown(x) {
  if (!x.vars || !x.vars.length) return x;
  const all = x.vars.concat([{ text: x.text, ts: x.ts, meta: x.meta, steps: x.steps, att: x.att, who: x.who }]);
  const n = Math.max(0, Math.min(all.length - 1, CH.view[x.id] ?? all.length - 1));
  return Object.assign({}, x, { text: "", meta: null, steps: null, att: null }, all[n], { id: x.id, role: x.role, _n: n, _of: all.length });
}
const CH_I = {
  copy: '<path d="M8.5 8.5h10v11h-10z"/><path d="M15.5 8.5v-3h-10v11h3"/>',
  again: '<path d="M19.5 12a7.5 7.5 0 1 1-2.2-5.3"/><path d="M19.5 4.5v4h-4"/>',
  info: '<circle cx="12" cy="12" r="8"/><path d="M12 11v5M12 8h.01"/>',
  edit: '<path d="M4.5 19.5h4l10-10-4-4-10 10z"/><path d="m13 7 4 4"/>',
  ok: '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
};
const chIco = (k) => `<svg viewBox="0 0 24 24" aria-hidden="true">${CH_I[k]}</svg>`;
const chSec = (v) => v == null ? "" : (v < 10 ? v.toFixed(1) : Math.round(v).toString()).replace(".", ",") + " с";
const chNum = (v) => Number(v).toLocaleString("ru-RU");
/* «Подробности» ответа: модель, первое слово, весь ответ (полоска: сколько ждали модель и сколько она писала), токены, персонаж */
function chatMeta(s) {
  const m = s.meta || {}, p = chatWho(s.who), rows = [];
  if (m.model) rows.push(["Модель", `<span class="ch-mono">${escH(m.model)}</span>`]);
  if (m.first != null) rows.push(["Первое слово", `через ${chSec(m.first)}`]);
  if (m.total != null) {
    const k = m.first != null && m.total > 0 ? Math.max(4, Math.min(96, m.first / m.total * 100)) : 0;
    rows.push(["Ответ целиком", `за ${chSec(m.total)}` + (k ? `<span class="ch-tl" role="img" aria-label="Ждали первое слово ${chSec(m.first)}, писала ответ ${chSec(m.total - m.first)}"><i style="width:${k.toFixed(1)}%"></i></span>` : "")]);
  }
  if (m.tin || m.tout) rows.push(["Токены", [m.tin ? `${chNum(m.tin)} на входе` : "", m.tout ? `${chNum(m.tout)} в ответе` : ""].filter(Boolean).join(", ")
    + (m.cached ? `<small>из них ${chNum(m.cached)} из кэша</small>` : "")]);
  rows.push(["Персонаж", `<i class="ch-dot" style="background:${escH((p && p.color) || "#8A9BFF")}"></i>${escH((p && p.name) || "Ассистент")}`]);
  if (m.stopped) rows.push(["Ход", "остановлен кнопкой «Стоп» — ответ неполный"]);
  return `<dl class="ch-meta" id="ch-meta-${escH(s.id)}">${rows.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("")}</dl>`;
}
/* кнопки под пузырём: у ответа — ‹ 1/2 ›, «Копировать», «Ещё раз» (последний ответ), «Подробности»; у своего последнего
   вопроса — «Изменить». У последних — видны всегда, у прежних — при наведении и с клавиатуры */
function chatActs(x, s, lastA, lastU) {
  if (x.role === "user") {
    if (!lastU || !x.text || CH.editing === x.id) return "";
    return `<div class="ch-acts out last"><button class="ch-a" type="button" data-edit="${escH(x.id)}" ${CH.busy ? "disabled" : ""}>${chIco("edit")}Изменить</button></div>`;
  }
  if (!s.text) return "";
  const id = escH(x.id), open = CH.info.has(x.id) && (s.meta || x.vars);
  const pg = s._of > 1 ? `<span class="ch-pg" role="group" aria-label="Варианты ответа"><button type="button" data-vp="${id}" data-d="-1" ${s._n === 0 ? "disabled" : ""} aria-label="Предыдущий вариант"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m14.5 6-6 6 6 6"/></svg></button><b>${s._n + 1} из ${s._of}</b><button type="button" data-vp="${id}" data-d="1" ${s._n === s._of - 1 ? "disabled" : ""} aria-label="Следующий вариант"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9.5 6 6 6-6 6"/></svg></button></span>` : "";
  return `<div class="ch-acts${lastA ? " last" : ""}">${pg}`
    + `<button class="ch-a" type="button" data-copy="${id}" title="Скопировать текст ответа">${chIco("copy")}<span>Копировать</span></button>`
    + (lastA ? `<button class="ch-a" type="button" data-regen="${id}" ${CH.busy ? "disabled" : ""} title="Спросить модель ещё раз тем же вопросом — новый ответ появится вариантом рядом">${chIco("again")}Ещё раз</button>` : "")
    + (s.meta ? `<button class="ch-a" type="button" data-info="${id}" aria-expanded="${open ? "true" : "false"}" aria-controls="ch-meta-${id}">${chIco("info")}Подробности</button>` : "")
    + `</div>${open && s.meta ? chatMeta(s) : ""}`;
}
function chatBubble(x0, lastWho, lastA, lastU) {
  const x = chatShown(x0);
  if (x.role === "user" && CH.editing === x.id) {
    return `<div class="cl-m out ch-editing" data-id="${escH(x.id)}"><textarea id="ch-edit" rows="2" aria-label="Исправить вопрос">${escH(x.text)}</textarea>`
      + `<div class="ch-edrow"><span>Ответ после вопроса заменится новым</span><button class="btn small" type="button" id="ch-ed-no">Отмена</button><button class="btn small primary" type="button" id="ch-ed-ok">Спросить заново</button></div></div>`;
  }
  if (x.role === "assistant" && CH.live && CH.regen === x.id) {      // «Ещё раз»: новый ответ пишется на месте прежнего
    return (lastWho !== (x.who || "") ? chatWhoHtml(x.who) : "") + chatLiveHtml();
  }
  return chatBubble1(x, lastWho) + chatActs(x0, x, lastA, lastU);
}
const chatWhoHtml = (pid) => { const p = chatWho(pid);
  return `<div class="ch-who"><i style="background:${escH((p && p.color) || "#8A9BFF")}"></i>${escH((p && p.name) || "Ассистент")}</div>`; };
function chatBubble1(x, lastWho) {
  const out = x.role === "user", p = out ? null : chatWho(x.who);
  const hm = new Date(x.ts * 1000).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
  // имя персонажа — над его первым ответом за день и когда отвечает другой персонаж (не над каждым ответом)
  const head = !out && lastWho !== (x.who || "")
    ? `<div class="ch-who"><i style="background:${escH((p && p.color) || "#8A9BFF")}"></i>${escH((p && p.name) || "Ассистент")}</div>` : "";
  const body = (out ? "" : chatSteps(x.steps, x.id)) + (!x.text ? "" : out ? `<div class="tx" translate="no">${escH(x.text)}</div>` : `<div class="tx md" translate="no">${md(x.text)}</div>`);
  // вложения: картинки — миниатюрами, файлы — плашками; нажать — открыть из «Входящих» папки ассистента
  // картинки к рассказу (show_images) — миниатюры со ссылкой на источник, лентой; свои вложения — из «Входящих»
  const web = (x.att || []).filter(a => a.kind === "image" && a.url && !a.path);
  const gal = web.length && window.DewiarRich ? DewiarRich.gallery(web.map(a => ({ src: a.thumb, page: a.url, full: a.full, title: a.name, author: a.author, license: a.license, site: a.site, source: a.source }))) : "";
  const att = (x.att || []).filter(a => !web.includes(a)).map(a => a.kind === "plugin"     // плагин, сделанный Лирой в этом ответе, — «Открыть»
    ? `<button class="ch-plg" data-plg="${escH(a.plugin || "")}" title="Открыть страницу плагина"><i aria-hidden="true">${escH(a.icon || "🧩")}</i><span><b>${escH(a.name)}</b><small>Плагин в студии</small></span><em>Открыть</em></button>`
    : a.kind === "image" && a.thumb
    ? `<button class="ch-img" data-path="${escH(a.path || "")}" title="${escH(a.name)} — открыть"><img src="${escH(a.thumb)}" alt="${escH(a.name)}"></button>`
    : `<button class="cl-f" data-path="${escH(a.path || "")}" data-key="${escH(a.key || "")}" title="${escH(a.label || a.name)}"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M6 3.5h8.5L19 8v12.5H6z"/><path d="M14 3.5V8h5"/></svg><span>${escH(a.name)}</span><small>${a.size ? chatSize(a.size) : ""}</small></button>`).join("");
  return `${head}<div class="cl-m${out ? " out" : ""}${gal ? " wide" : ""}" data-id="${escH(x.id)}">${x.via ? `<small class="ch-via">${x.via === "dev" ? "ответ разработчика" : "из мессенджера"}</small>` : ""}${att ? `<div class="ch-att">${att}</div>` : ""}${body}${gal}<time>${x.edited ? `<span class="ch-tag">изменено</span>` : ""}${x.meta && x.meta.stopped ? `<span class="ch-tag">остановлено</span>` : ""}${hm}${!out && x.text ? `<button class="ch-listen" data-listen="${escH(x.id)}" title="Прослушать ответ" aria-label="Прослушать ответ"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 9.5h3.5L12 5.5v13l-4.5-4H4z"/><path d="M15.5 9a4 4 0 0 1 0 6M18 6.5a7.5 7.5 0 0 1 0 11"/></svg>Прослушать</button>` : ""}</time></div>`;
}
/* Что сделано за ход (YouTube 26.10: «в чате не было информации о выполнении команды»): ✓ готово, ✕ не вышло (с причиной),
   «Разрешение: … — разрешено / отказано». Больше трёх — «ещё N» (раскрыть). */
const CH_OPEN = new Set();
const ST_ICON = { done: "✓", yes: "✓", error: "✕", no: "✕", ask: "?", run: "…" };
function chatSteps(steps, id) {
  if (!steps || !steps.length) return "";
  const open = CH_OPEN.has(id) || steps.length <= 4, list = open ? steps : steps.slice(-3);
  const row = (s) => `<div class="ch-st ${escH(s.s)}"><b aria-hidden="true">${ST_ICON[s.s] || "•"}</b><span>${escH(s.t)}${s.s === "yes" ? " — разрешено" : s.s === "no" ? " — отказано" : ""}</span>${s.e ? `<em>${escH(s.e)}</em>` : ""}</div>`;
  return `<div class="ch-steps">${open ? "" : `<button class="ch-more" data-open="${escH(id || "")}">ещё ${steps.length - 3} — показать</button>`}${list.map(row).join("")}</div>`;
}
/* Живой пузырь (пока модель отвечает). GitHub №22 (ALT Linux: «очень сильно тормозит, особенно окно чата»): раньше каждый
   кусок ответа заново собирал весь список (innerHTML всей ленты + схемы Mermaid) — на длинной переписке и слабой
   графике это десятки перерисовок в секунду. Теперь кусок меняет только живой пузырь, не чаще кадра; вся лента — когда
   ответ готов (событие chat). */
const chatLiveHtml = () => `<div class="cl-m ch-live${CH.live.media ? " wide" : ""}" id="ch-live">${chatLiveInner()}</div>`;
const chatLiveInner = () => chatSteps(CH.live.steps, "live") + (CH.live.text ? `<div class="tx md" translate="no">${md(CH.live.text)}</div>` : `<div class="ch-dots"><i></i><i></i><i></i></div>`)
  + (CH.live.media && window.DewiarRich ? DewiarRich.gallery(CH.live.media) : "");
let chLiveRaf = 0;
function chatLive() {
  if (!$("#p-chat").classList.contains("cur")) return;
  const el = $("#ch-live");
  if (!el || !CH.live) return chatRender("stay");          // первый кусок ответа — пузыря ещё нет: вся лента один раз
  if (chLiveRaf) return;
  chLiveRaf = requestAnimationFrame(() => { chLiveRaf = 0;
    const box = $("#ch-msgs"), el2 = $("#ch-live"); if (!box || !el2 || !CH.live) return;
    const atBottom = box.scrollHeight - box.scrollTop - box.clientHeight < 60;
    el2.classList.toggle("wide", !!CH.live.media); el2.innerHTML = chatLiveInner();
    if (atBottom) box.scrollTop = box.scrollHeight; });
}
function chatRender(keep) {
  const box = $("#ch-msgs"); if (!box) return;
  const atBottom = box.scrollHeight - box.scrollTop - box.clientHeight < 60, oldH = box.scrollHeight, oldTop = box.scrollTop;
  let html = CH.more ? `<button class="btn small ch-older" id="ch-older">Показать раньше</button>` : "", day = "", lastWho = null;
  // «Ещё раз» — у последнего ответа после последнего вопроса; «Изменить» — у последнего вопроса
  let iu = -1; CH.items.forEach((x, i) => { if (x.role === "user") iu = i; });
  let ia = -1; CH.items.forEach((x, i) => { if (x.role === "assistant" && i > iu && !x.via) ia = i; });
  if (iu < 0) ia = -1;
  const regenLive = CH.live && CH.regen && CH.items.some(x => x.id === CH.regen);
  CH.items.forEach((x, i) => {
    const d = chatDay(x.ts);
    if (d !== day) { html += `<div class="ch-day"><span>${escH(d)}</span></div>`; day = d; lastWho = null; }
    html += chatBubble(x, lastWho, i === ia, i === iu && !CH.live);
    if (x.role === "assistant") lastWho = x.who || "";
  });
  if (regenLive) { /* живой пузырь уже на месте прежнего ответа */ }
  else if (CH.live && lastWho === active) html += chatLiveHtml();
  else if (CH.live) {
    const p = chatWho(active);
    html += `<div class="ch-who"><i style="background:${escH((p && p.color) || "#8A9BFF")}"></i>${escH((p && p.name) || "Ассистент")}</div>` + chatLiveHtml();
  }
  $("#ch-empty").style.display = CH.items.length || CH.live ? "none" : "";
  box.innerHTML = html;
  if (keep === "older") box.scrollTop = box.scrollHeight - oldH + oldTop;   // подгрузили раньше — лента не прыгает
  else if (keep !== "stay" || atBottom) box.scrollTop = box.scrollHeight;
  const o = $("#ch-older"); if (o) o.onclick = chatOlder;
  $$("#ch-msgs .ch-more").forEach(b => b.onclick = () => { CH_OPEN.add(b.dataset.open); chatRender("stay"); });
  if (window.DewiarRich) DewiarRich.diagrams(box);      // ```mermaid в ответах — схемами
  $$("#ch-msgs [data-plg]").forEach(b => b.onclick = () => { if (window.plpOpen && b.dataset.plg) plpOpen(b.dataset.plg, "page"); });
  $$("#ch-msgs [data-path]").forEach(b => b.onclick = () => {
    if (b.dataset.key) core.call("knowledge_open_file", { key: b.dataset.key }).catch(e => { $("#ch-res").textContent = e.message; });   // источник ответа
    else if (b.dataset.path) core.call("ws_open", { path: b.dataset.path }).catch(e => { $("#ch-res").textContent = e.message; }); });
  const p = chatWho(active);
  $("#ch-text").placeholder = `Сообщение — ответит ${p ? p.name : "ассистент"}. Enter — отправить, Shift+Enter — новая строка`;
  chatEditWire();
  chatGoSync();
}
async function loadChat() {
  if (typeof chatTaskQLoad === "function") chatTaskQLoad();          // №551: ждущий вопрос задачи — сразу виден
  chatTmSync();
  try {
    const r = await core.call("chat_list", { limit: 80 });
    CH.items = r.items || []; CH.more = !!r.more; CH.loaded = true; CH.view = {}; CH.editing = ""; CH.regen = "";
  } catch (e) { $("#ch-res").textContent = e.message; }
  chatRender();
  chatThreadsLoad();
}
async function chatOlder() {
  if (!CH.items.length) return;
  const r = await core.call("chat_list", { before: CH.items[0].id, limit: 80 }).catch(() => null);
  if (!r) return;
  CH.items = (r.items || []).concat(CH.items); CH.more = !!r.more;
  chatRender("older");
}
core.on("chat", e => {
  const x = e.item; if (!x || !CH.loaded) return;
  const i = CH.items.findIndex(y => y.id === x.id);
  if (i >= 0) CH.items[i] = x; else CH.items.push(x);
  if (x.role === "assistant") { CH.live = null; if (CH.regen === x.id || i < 0) CH.regen = ""; delete CH.view[x.id]; }
  if ($("#p-chat").classList.contains("cur")) chatRender("stay");
  if (x.role === "user" && i < 0) { clearTimeout(CH.thT); CH.thT = setTimeout(chatThreadsLoad, 300); }   // название беседы — по первому вопросу
});
// вопрос исправили («Изменить» — здесь или в другом окне студии): запись — новым текстом, всё после неё — прочь
core.on("chat_cut", e => {
  const x = e.item; if (!x || !CH.loaded) return;
  const i = CH.items.findIndex(y => y.id === x.id);
  if (i >= 0) { CH.items[i] = x; CH.items.length = i + 1; }
  if (CH.editing === x.id) CH.editing = "";
  if ($("#p-chat").classList.contains("cur")) chatRender("stay");
});
// пока модель отвечает — живой пузырь (текст по мере ответа); готовый ответ придёт событием chat
core.on("answer", e => {
  if (!CH.loaded || e.done) return;
  CH.live = Object.assign(CH.live || {}, { text: e.text || "" });
  chatLive();
});
// картинки к рассказу появляются, пока персонаж ещё говорит, — сразу в живом пузыре
core.on("media", e => {
  if (!CH.loaded || e.source !== "pics") return;
  CH.live = Object.assign(CH.live || { text: "" }, { media: (CH.live && CH.live.media || []).concat(e.items || []).slice(0, 12) });
  chatLive();
});
// шаги хода — сразу в живом пузыре: «…» выполняется, ✓ / ✕ — итог
core.on("tool", e => {
  if (!CH.loaded || !e.title) return;
  CH.live = CH.live || { text: "" }; const st = CH.live.steps = CH.live.steps || [];
  const i = st.findIndex(s => s.s === "run" && s.n === e.name);
  const row = { t: e.title, s: e.status === "error" ? "error" : e.status === "done" ? "done" : "run", n: e.name, ...(e.error ? { e: e.error } : {}) };
  if (i >= 0) st[i] = row; else st.push(row);
  chatLive();
});
/* «Выполнить?» — прямо в «Чате» (тот же вопрос, что в виджете: ответ любой из сторон закрывает оба) */
function chatAsk(e) {
  const box = $("#ch-ask"); if (!box) return;
  if (!e) { box.hidden = true; box.innerHTML = ""; return; }
  box.innerHTML = `<div class="q">${escH(e.text || "Выполнить?")}</div><div class="row"><button class="btn primary small" data-a="yes">Выполнить</button>`
    + `<button class="btn small" data-a="no">Не надо</button>${e.always ? `<button class="btn small" data-a="always">Всегда для таких</button>` : ""}</div>`;
  box.hidden = false;
  $$("#ch-ask [data-a]").forEach(b => b.onclick = () => {
    const a = b.dataset.a; chatAsk(null);
    core.call("confirm_answer", a === "always" ? { ok: true, always: true } : { ok: a === "yes" }).catch(x => { $("#ch-res").textContent = x.message; });
  });
  const pg = $("#p-chat"); if (pg && pg.classList.contains("cur")) $("#ch-ask .btn.primary").focus({ preventScroll: true });
}
core.on("confirm", chatAsk).on("confirm_done", () => chatAsk(null));
/* №551 (04.11: «висит 2 часа, я спросил дать права — молчит»): задача спросила — вопрос виден и в «Чате», ответить можно
   кнопкой «Да»/«Нет» или словами; ответ уходит задаче (task_answer), а не новым вопросом в разговор */
const chTQ = { id: "" };
function chatTaskQ(t) {
  const box = $("#ch-tq"); if (!box) return;
  if (!t || t.status !== "waiting" || !t.question) {
    if (!t || t.id === chTQ.id) { box.hidden = true; box.innerHTML = ""; chTQ.id = ""; }
    return;
  }
  if (chTQ.id === t.id && !box.hidden) return;
  chTQ.id = t.id;
  box.innerHTML = `<div class="q">❓ Задача «${escH(t.title)}» спрашивает:\n${escH(t.question)}</div><div class="row">`
    + `<button class="btn primary small" data-v="Да">Да</button><button class="btn small" data-v="Нет">Нет</button>`
    + `<input id="ch-tqa" placeholder="Или ответьте словами…" aria-label="Ответ задаче"><button class="btn small" data-v="">Ответить</button></div>`;
  box.hidden = false;
  const send = (v) => {
    const text = (v || ($("#ch-tqa") || {}).value || "").trim(); if (!text) return;
    core.call("task_answer", { id: t.id, text }).then(() => { chatTaskQ(null); $("#ch-res").textContent = `Передала в задачу «${t.title}».`; })
      .catch(x => { $("#ch-res").textContent = x.message; });
  };
  box.querySelectorAll("[data-v]").forEach(b => b.onclick = () => send(b.dataset.v));
  $("#ch-tqa").onkeydown = (e) => { if (e.key === "Enter") send(""); };
}
core.on("task", e => chatTaskQ(e.task)).on("tasks", e => { const w = (e.tasks || []).find(x => x.status === "waiting"); chatTaskQ(w || null); });
// вопрос, заданный до открытия «Чата», — спрашиваем, только когда «Чат» открыли (лёгкая студия не грузит скрытое)
const chatTaskQLoad = () => core.call("tasks_list").then(list => chatTaskQ((list || []).find(x => x.status === "waiting") || null)).catch(() => {});
// текстовый режим: без микрофона и голоса (ядро запоминает прежний голос), «Выполнить?» — здесь, а не во всплывающем виджете
/* 30.10 (владелец, №421: «Лира перестала говорить» — режим включился случайным кликом): пока режим включён — строка
   над лентой с кнопкой «Включить голос»; включить — только после вопроса */
function chatTmSync() {
  const c = $("#ch-tm"), on = !!(typeof S !== "undefined" && S && S.ui && S.ui.text_mode);
  if (c) c.checked = on;
  let bar = $("#ch-tmbar");
  if (on && !bar) {
    bar = document.createElement("div"); bar.id = "ch-tmbar"; bar.className = "ch-tmbar"; bar.setAttribute("role", "status");
    bar.innerHTML = `<span><b>Текстовый режим</b> — голос и микрофон выключены, ответы только здесь.</span><button class="btn small" type="button">Включить голос</button>`;
    const box = $("#ch-box"); if (box) box.insertBefore(bar, box.children[1] || null);
    bar.querySelector("button").onclick = async () => { try { await core.call("text_mode", { on: false }); if (S && S.ui) S.ui.text_mode = false; chatTmSync();
      $("#ch-res").textContent = "Голос и микрофон снова включены."; } catch (x) { toast(x.message); } };
  }
  if (bar) bar.hidden = !on;
}
$("#ch-tm").onchange = async (e) => {
  const on = e.target.checked;
  if (on && !await ask("Включить текстовый режим? Голос и микрофон выключатся, ответы будут только текстом в «Чате». Вернуть — кнопкой «Включить голос».", { ok: "Включить", danger: false })) {
    e.target.checked = false; return;
  }
  try { await core.call("text_mode", { on }); if (S && S.ui) S.ui.text_mode = on; chatTmSync();
    $("#ch-res").textContent = on ? "Текстовый режим: микрофон и голос выключены, ответы и «Выполнить?» — здесь." : "Голос и микрофон снова включены."; }
  catch (x) { e.target.checked = !on; $("#ch-res").textContent = x.message; }
};
core.on("settings", () => setTimeout(chatTmSync, 0));
core.on("state", e => {
  const busy = e.state === "thinking" || e.state === "speaking";
  if (busy !== CH.busy) { CH.busy = busy; if (CH.loaded && $("#p-chat").classList.contains("cur")) chatRender("stay"); else chatGoSync(); }
  if (!CH.loaded) return;
  if (e.state === "thinking" && !CH.live) { CH.live = { text: "" }; if ($("#p-chat").classList.contains("cur")) chatRender("stay"); }
  if ((e.state === "idle" || e.state === "listening" || e.state === "muted") && CH.live && !CH.live.text && !CH.live.media) {
    CH.live = null; CH.regen = ""; if ($("#p-chat").classList.contains("cur")) chatRender("stay"); }
});
// перебили (голосом, «Стоп» в виджете): недописанный ответ ядро кладёт в ленту само («остановлено»), живой пузырь — прочь
core.on("interrupted", () => {
  if (!CH.loaded || !CH.live) return;
  setTimeout(() => { if (CH.live && !CH.busy) { CH.live = null; CH.regen = ""; if ($("#p-chat").classList.contains("cur")) chatRender("stay"); } }, 400);
});
/* вложения к сообщению: скрепка, перетащить в ленту, Ctrl+V; картинки уменьшаются до 1600 px (как в виджете),
   файлы — до 11 МБ; ядро кладёт всё во «Входящие» папки ассистента и показывает модели (текст документов, картинки) */
let chAtts = [];                                       // {kind: "image"|"file", name, b64, size, url?}
const CH_MAX = 11e6;
function chatShrink(file) {
  return new Promise((ok, bad) => {
    const img = new Image(); img.onerror = () => bad(new Error("это не картинка"));
    img.onload = () => { const k = Math.min(1, 1600 / Math.max(img.width, img.height)), c = document.createElement("canvas");
      c.width = Math.round(img.width * k); c.height = Math.round(img.height * k); c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
      URL.revokeObjectURL(img.src); ok(c.toDataURL("image/jpeg", 0.88)); };
    img.src = URL.createObjectURL(file);
  });
}
const chatB64 = (file) => new Promise((ok, bad) => { const r = new FileReader(); r.onload = () => ok(r.result); r.onerror = bad; r.readAsDataURL(file); });
async function chatAddFiles(list) {
  for (const f of list) {
    try {
      if (/^image\//.test(f.type) && !/svg/.test(f.type)) {
        const url = await chatShrink(f);
        chAtts.push({ kind: "image", name: (f.name || "картинка").replace(/\.\w+$/, "") + ".jpg", b64: url, url, size: Math.round(url.length * 0.75) });
      } else if (f.size > CH_MAX) $("#ch-res").textContent = `«${f.name}» больше 11 МБ — положите его в папку ассистента`;
      else chAtts.push({ kind: "file", name: f.name, b64: await chatB64(f), size: f.size });
    } catch (e) { $("#ch-res").textContent = `«${f.name}»: ${e.message}`; }
  }
  chAtts = chAtts.slice(0, 10);
  chatAttsRender();
}
function chatAttsRender() {
  $("#ch-atts").innerHTML = chAtts.map((a, i) => `<span class="ch-chip">${a.kind === "image" ? `<img src="${escH(a.url)}" alt="">` : `<i>${escH((a.name.split(".").pop() || "").slice(0, 4).toUpperCase())}</i>`}<b>${escH(a.name)}</b><button data-i="${i}" title="Убрать" aria-label="Убрать">✕</button></span>`).join("");
  $$("#ch-atts button").forEach(b => b.onclick = () => { chAtts.splice(+b.dataset.i, 1); chatAttsRender(); });
  chatGoSync();
}
function chatSend() {
  const t = $("#ch-text"), q = t.value.trim(); if (!q && !chAtts.length) return;
  const files = chAtts.map(a => ({ name: a.name, b64: a.b64 }));
  const atts = chAtts;
  t.value = ""; t.style.height = ""; chAtts = []; chatAttsRender(); $("#ch-res").textContent = "";
  if (!core.connected) $("#ch-res").textContent = "Нет связи с ядром — сообщение не потеряется: отправлю, как только ядро вернётся";
  core.sendLater("say", { text: q, files }).then(() => { if (/отправлю, как только/.test($("#ch-res").textContent)) $("#ch-res").textContent = ""; })
    .catch(e => {   // не дошло — текст обратно в поле, набирать заново не нужно (№200)
      if (!t.value.trim()) { t.value = q; t.dispatchEvent(new Event("input")); }
      if (!chAtts.length) { chAtts = atts; chatAttsRender(); }
      $("#ch-res").textContent = e.message + " — текст вернул в поле, отправьте ещё раз";
    });
}
$("#ch-file").onchange = (e) => { chatAddFiles([...e.target.files]); e.target.value = ""; };
$("#ch-text").addEventListener("paste", (e) => {
  const files = [...(e.clipboardData && e.clipboardData.items || [])].filter(x => x.kind === "file").map(x => x.getAsFile()).filter(Boolean);
  if (files.length) { e.preventDefault(); chatAddFiles(files); return; }
  // WebKitGTK часто не отдаёт странице картинку из буфера — спрашиваем окно (Api.clipboard_image, как в виджете)
  if (e.clipboardData && !e.clipboardData.getData("text")) { e.preventDefault(); chatClipImage(); }
});
async function chatClipImage() {
  const a = window.api && window.api(); let url = "";
  try { url = a && a.clipboard_image ? await a.clipboard_image() : ""; } catch (e) {}
  if (!url) { $("#ch-res").textContent = "В буфере обмена нет картинки — скопируйте снимок и вставьте ещё раз."; return; }
  chAtts.push({ kind: "image", name: "Снимок " + new Date().toLocaleTimeString("ru-RU").replace(/:/g, "-") + (/^data:image\/png/.test(url) ? ".png" : ".jpg"), b64: url, url,
                size: Math.round(url.length * 0.75) });
  chAtts = chAtts.slice(0, 10); chatAttsRender();
}
{ const box = $("#ch-box");
  box.addEventListener("dragover", (e) => { if ([...(e.dataTransfer.types || [])].includes("Files")) { e.preventDefault(); box.classList.add("over"); } });
  box.addEventListener("dragleave", (e) => { if (!box.contains(e.relatedTarget)) box.classList.remove("over"); });
  box.addEventListener("drop", (e) => { e.preventDefault(); box.classList.remove("over"); chatAddFiles([...(e.dataTransfer.files || [])]); }); }
/* «Отправить» ↔ «Стоп»: пока персонаж думает или говорит, а в поле пусто, кнопка останавливает ответ (команда stop — как
   «Стоп» в виджете, 0.85). Набрали новый вопрос — снова «Отправить»: новый вопрос сам перебьёт прежний ответ. */
const chatStopMode = () => CH.busy && !$("#ch-text").value.trim() && !chAtts.length;
function chatGoSync() {
  const b = $("#ch-go"); if (!b) return;
  const stop = chatStopMode();
  if (b.classList.contains("stop") === stop && b.dataset.ready) return;
  b.dataset.ready = "1";
  b.classList.toggle("stop", stop);
  b.innerHTML = stop ? `<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="7" y="7" width="10" height="10" rx="2.2"/></svg>Стоп` : "Отправить";
  b.title = stop ? "Остановить ответ (Esc)" : "Отправить (Enter)";
}
function chatStop() { core.call("stop").catch(e => { $("#ch-res").textContent = e.message; }); }
$("#ch-go").onclick = () => chatStopMode() ? chatStop() : chatSend();
$("#ch-text").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); chatSend(); }
  else if (e.key === "Escape" && CH.busy) { e.preventDefault(); chatStop(); }
});
$("#ch-text").addEventListener("input", (e) => { const t = e.target; t.style.height = ""; t.style.height = Math.min(160, t.scrollHeight) + "px"; chatGoSync(); });
$("#ch-clear").onclick = async () => {
  chatThreadsClose();
  if (!await ask("Очистить переписку этой беседы? Память ассистента и заметки это не трогает.")) return;
  await core.call("chat_clear").catch(() => {}); CH.items = []; CH.more = false; chatRender(); chatThreadsLoad();
};
core.on("hello", () => { if ($("#p-chat").classList.contains("cur")) loadChat(); });
/* «Прослушать» под ответом (идея №58, 29.10: «без очков не прочитать — переслушать проще»): голосом персонажа, который
   отвечал (voice_test с текстом), даже в режиме «только текстом»; нажали снова — «Стоп» (stop). */
document.addEventListener("click", (ev) => {
  const b = ev.target.closest && ev.target.closest(".ch-listen"); if (!b) return;
  ev.stopPropagation();
  if (b.classList.contains("on")) { core.call("stop").catch(() => {}); b.classList.remove("on"); b.lastChild.textContent = "Прослушать"; return; }
  const x0 = (CH.items || []).find(i => String(i.id) === b.dataset.listen); if (!x0) return;
  const x = chatShown(x0);
  $$(".ch-listen.on").forEach(o => { o.classList.remove("on"); o.lastChild.textContent = "Прослушать"; });
  b.classList.add("on"); b.lastChild.textContent = "Стоп";
  core.call("voice_test", { text: x.text, persona: x.who || undefined, listen: true }).catch(e => toast(e.message));
  clearTimeout(b._t); b._t = setTimeout(() => { b.classList.remove("on"); b.lastChild.textContent = "Прослушать"; }, Math.min(180000, 1500 + x.text.length * 75));
});
/* ---------- 0.86: кнопки под пузырями ---------- */
async function chatCopy(text) {
  try { await navigator.clipboard.writeText(text); return true; } catch (e) { }
  const t = document.createElement("textarea"); t.value = text; t.setAttribute("readonly", ""); t.style.cssText = "position:fixed;left:-9999px;top:0";
  document.body.appendChild(t); t.select(); let ok = false; try { ok = document.execCommand("copy"); } catch (e) { } t.remove(); return ok;
}
$("#ch-msgs").addEventListener("click", async (ev) => {
  const b = ev.target.closest && ev.target.closest("button"); if (!b || b.disabled) return;
  const find = (id) => CH.items.find(x => x.id === id);
  if (b.dataset.copy) {
    const x = find(b.dataset.copy); if (!x) return;
    const ok = await chatCopy(chatShown(x).text || "");
    const sp = b.querySelector("span"); if (!sp) return;
    b.classList.toggle("done", ok); sp.textContent = ok ? "Скопировано" : "Не вышло — выделите текст";
    b.querySelector("svg").innerHTML = ok ? CH_I.ok : CH_I.copy;
    clearTimeout(b._t); b._t = setTimeout(() => { b.classList.remove("done"); sp.textContent = "Копировать"; b.querySelector("svg").innerHTML = CH_I.copy; }, 1600);
  } else if (b.dataset.vp) {
    const x = find(b.dataset.vp); if (!x) return;
    const s = chatShown(x); CH.view[x.id] = Math.max(0, Math.min(s._of - 1, s._n + +b.dataset.d));
    chatRender("stay");
    const nb = $(`#ch-msgs [data-vp="${CSS.escape(x.id)}"][data-d="${b.dataset.d}"]`);
    (nb && !nb.disabled ? nb : $(`#ch-msgs [data-vp="${CSS.escape(x.id)}"]:not([disabled])`) || { focus() {} }).focus({ preventScroll: true });
  } else if (b.dataset.info) {
    const id = b.dataset.info; CH.info.has(id) ? CH.info.delete(id) : CH.info.add(id);
    chatRender("stay");
    const nb = $(`#ch-msgs [data-info="${CSS.escape(id)}"]`); if (nb) nb.focus({ preventScroll: true });
  } else if (b.dataset.regen) {
    const x = find(b.dataset.regen); if (!x) return;
    // в ответе были действия (напоминание, письмо…) — при повторе модель может сделать их ещё раз: спросить
    const acts = (x.steps || []).filter(st => st.s === "done" || st.s === "yes").map(st => st.t);
    if (acts.length && !await ask(`В этом ответе ${acts.length > 1 ? "были действия" : "было действие"}: ${acts.slice(0, 3).join("; ")}.\nПри повторе ${acts.length > 1 ? "они могут выполниться" : "оно может выполниться"} ещё раз. Спросить заново?`, { ok: "Спросить заново", danger: false })) return;
    CH.regen = x.id; CH.view[x.id] = undefined; $("#ch-res").textContent = "";
    core.call("chat_regen", { id: x.id }).catch(e => { CH.regen = ""; $("#ch-res").textContent = e.message; chatRender("stay"); });
  } else if (b.dataset.edit) {
    CH.editing = b.dataset.edit; chatRender("stay");
  }
});
function chatEditWire() {
  const t = $("#ch-edit"); if (!t) return;
  const fit = () => { t.style.height = ""; t.style.height = Math.min(240, t.scrollHeight + 2) + "px"; };
  fit(); t.oninput = fit;
  if (document.activeElement !== t) { t.focus({ preventScroll: true }); t.setSelectionRange(t.value.length, t.value.length); }
  const cancel = () => { CH.editing = ""; chatRender("stay"); $("#ch-text").focus({ preventScroll: true }); };
  const send = () => {
    const id = CH.editing, text = t.value.trim(); if (!text) return;
    const x = CH.items.find(y => y.id === id);
    if (x && text === (x.text || "").trim()) return cancel();
    $("#ch-ed-ok").disabled = true;
    core.call("chat_edit", { id, text }).catch(e => { $("#ch-res").textContent = e.message; $("#ch-ed-ok").disabled = false; });
  };
  t.onkeydown = (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); send(); }
    else if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); cancel(); }
  };
  $("#ch-ed-no").onclick = cancel; $("#ch-ed-ok").onclick = send;
}
// Esc в «Чате» (не в поле правки), пока персонаж отвечает, — «Стоп»
document.addEventListener("keydown", (e) => {
  if (e.key !== "Escape" || !CH.busy || e.defaultPrevented || !secOn("chat")) return;
  if (document.querySelector(".dwq-back") || CH.editing || ($("#ch-thp") && !$("#ch-thp").hidden)) return;
  chatStop();
});

/* ---------- 0.86: беседы и выгрузка (идея №145) ----------
   Список бесед — в выпадающем окне у названия текущей; «Новая беседа» — с чистого листа (прежняя остаётся в списке:
   открыть — прочитать и продолжить, у каждой — своя память модели). «Сохранить» — беседа файлом .md или .txt. */
const chThDate = (ts) => { const d = new Date(ts * 1000), now = new Date();
  if (d.toDateString() === now.toDateString()) return "сегодня, " + d.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
  return d.toLocaleDateString("ru-RU", { day: "numeric", month: "short", year: d.getFullYear() === now.getFullYear() ? undefined : "numeric" }); };
const chPl = (n) => n % 10 === 1 && n % 100 !== 11 ? "сообщение" : [2, 3, 4].includes(n % 10) && ![12, 13, 14].includes(n % 100) ? "сообщения" : "сообщений";
function chatThreadsLoad() { return core.call("chat_threads").then(r => chatThreadsSet(r.threads || [])).catch(() => {}); }
function chatThreadsSet(list) {
  const prev = CH.tid;
  CH.threads = list; const cur = list.find(t => t.active) || {};
  CH.tid = cur.id || "";
  const b = $("#ch-th b"); if (b) b.textContent = cur.title || "Новая беседа";
  const n = $("#ch-th small"); if (n) n.textContent = list.length > 1 ? `ещё ${list.length - 1}` : "";
  if (!$("#ch-thp").hidden) chatThreadsDraw();
  if (prev && CH.tid && prev !== CH.tid && CH.loaded) loadChat();            // беседу сменили в другом окне
}
core.on("chat_threads", e => chatThreadsSet(e.threads || []));
function chatThreadsDraw() {
  const box = $("#ch-thl");
  box.innerHTML = CH.threads.map(t => `<li class="${t.active ? "on" : ""}"><button type="button" class="ch-tho" data-open="${escH(t.id)}" ${t.active ? 'aria-current="true"' : ""}>`
    + `<b>${escH(t.title || "Новая беседа")}</b><small>${t.active ? "<em>открыта</em>" : ""}<span>${chThDate(t.last)}</span><span>${t.n} ${chPl(t.n)}</span></small></button>`
    + `<span class="ch-thx"><button type="button" data-ren="${escH(t.id)}" title="Переименовать" aria-label="Переименовать «${escH(t.title)}»">${chIco("edit")}</button>`
    + `<button type="button" data-del="${escH(t.id)}" title="Удалить" aria-label="Удалить «${escH(t.title)}»"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 7h14M10 7V5h4v2M7 7l1 12.5h8L17 7"/></svg></button></span></li>`).join("");
}
function chatThreadsOpen() {
  const p = $("#ch-thp"); if (!p.hidden) return chatThreadsClose();
  chatThreadsDraw(); p.hidden = false; $("#ch-th").setAttribute("aria-expanded", "true");
  chatThreadsLoad();
  const on = p.querySelector("li.on .ch-tho") || p.querySelector("button"); if (on) on.focus({ preventScroll: true });
}
function chatThreadsClose() { const p = $("#ch-thp"); if (!p || p.hidden) return; p.hidden = true; $("#ch-th").setAttribute("aria-expanded", "false"); }
async function chatThreadDo(cmd, args, msg) {
  chatThreadsClose();
  try { await core.call(cmd, args); if (msg) $("#ch-res").textContent = msg; } catch (e) { $("#ch-res").textContent = e.message; return; }
  await loadChat();
}
$("#ch-th").onclick = chatThreadsOpen;
$("#ch-new").onclick = () => chatThreadDo("chat_thread_new", {}, "").then(() => $("#ch-text").focus({ preventScroll: true }));
$("#ch-thp").addEventListener("click", async (e) => {
  const b = e.target.closest("button"); if (!b) return;
  const t = CH.threads.find(x => x.id === (b.dataset.open || b.dataset.ren || b.dataset.del));
  if (b.dataset.open) { if (t && !t.active) chatThreadDo("chat_thread_open", { id: t.id }, `Открыта беседа «${t.title}» — Лира помнит её.`); else chatThreadsClose(); }
  else if (b.dataset.ren && t) {
    const v = await askText("Название беседы", t.named ? t.title : "", { ok: "Переименовать", ph: t.title });
    if (v == null) return;
    core.call("chat_thread_rename", { id: t.id, title: v }).then(r => chatThreadsSet(r.threads || [])).catch(x => { $("#ch-res").textContent = x.message; });
  } else if (b.dataset.del && t) {
    if (!await ask(`Удалить беседу «${t.title}»? Её переписка и память о ней пропадут.` + (t.active ? " Откроется новая беседа." : ""))) return;
    chatThreadDo("chat_thread_delete", { id: t.id }, "Беседа удалена.");
  }
});
document.addEventListener("click", (e) => { const p = $("#ch-thp"); if (p && !p.hidden && !e.target.closest("#ch-thp, #ch-th, .dwq-back")) chatThreadsClose(); });
$("#ch-thp").addEventListener("keydown", (e) => {
  if (e.key === "Escape") { e.preventDefault(); chatThreadsClose(); $("#ch-th").focus(); }
  if (e.key === "ArrowDown" || e.key === "ArrowUp") {
    const all = [...$$("#ch-thp .ch-tho")], i = all.indexOf(document.activeElement);
    if (i >= 0) { e.preventDefault(); (all[i + (e.key === "ArrowDown" ? 1 : -1)] || all[i]).focus(); }
  }
});
// «Сохранить»: беседа файлом — Markdown (с оформлением) или простой текст
async function chatExport(fmt) {
  $("#ch-exp").open = false;
  try {
    const r = await core.call("chat_export", { id: CH.tid, fmt });
    const text = fmt === "txt" ? "﻿" + r.text : r.text;           // .txt с меткой UTF-8 — Блокнот Windows не путает кириллицу
    const bytes = new TextEncoder().encode(text); let bin = ""; bytes.forEach(c => bin += String.fromCharCode(c));
    const a = window.api && window.api();
    if (a && a.save_file_b64) { const w = await a.save_file_b64(btoa(bin), r.name); if (w) $("#ch-res").textContent = "Сохранено: " + w; return; }
    const l = document.createElement("a"); l.href = URL.createObjectURL(new Blob([text], { type: fmt === "txt" ? "text/plain" : "text/markdown" }));
    l.download = r.name; l.click(); setTimeout(() => URL.revokeObjectURL(l.href), 4000);
  } catch (e) { $("#ch-res").textContent = e.message; }
}
$$("#ch-exp [data-fmt]").forEach(b => b.onclick = () => chatExport(b.dataset.fmt));
document.addEventListener("click", (e) => { const d = $("#ch-exp"); if (d && d.open && !e.target.closest("#ch-exp")) d.open = false; });
