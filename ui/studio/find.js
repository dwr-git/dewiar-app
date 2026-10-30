/* Поиск по студии на «Главной» (30.10, владелец: «Лира у нас большая очень, много настроек и разделов. Может быть на
   „Главной“ добавить такую поисковую форму, чтобы прямо моментально можно было найти любой раздел или настройку? …где-то
   под слепком знаний»).
   Указатель собирается из самой студии — без ручных списков, новые настройки находятся сами:
   • разделы меню (название и подсказка у кнопки);
   • внутри раздела — заголовки, подписи полей, «раскрывашки» (h2/h3/summary/label) — переход к ним с подсветкой;
   • слова, которыми люди ищут (FD_SYN: «письма» → «Почта», «будильник» → «Дела»…);
   • статьи «Вопрос — ответ» (guide.json) — второй строкой.
   Ctrl+K (⌘K) — из любого места студии; стрелки и Enter — без мыши; Esc — закрыть. */
const FD = { idx: null, at: 0, hits: [], sel: 0, qa: null };
/* слова людей → [куда, название, слова]: «раздел» или «раздел#селектор» (перейти и подсветить); mail — карточка «Почта» */
const FD_SYN = [
  ["mail#hm-mail", "Последние письма", "почта письма входящие inbox email gmail яндекс почта mail"],
  ["connect#mail-box", "Подключить почту", "почта gmail пароль приложения smtp imap письмо ящик"],
  ["vault", "Пароли и пин-коды", "пароль пароли пин код домофон логин сейф секрет вайфай wifi"],
  ["reminders", "Будильник и напоминания", "будильник напомни напоминание таймер повтор дела"],
  // 30.10 (владелец: «нигде не могу звонки послушать… даже в поиске искал — ничего»)
  ["reminders#r-sound", "Звонок будильника — послушать и выбрать", "звук звуки звонок звонки мелодия мелодии рингтон сигнал послушать прослушать пульс будильник"],
  ["calendar", "Календарь и встречи", "календарь встреча событие дата день расписание"],
  ["voice", "Голос и скорость речи", "голос скорость речи быстрее медленнее громкость тембр озвучка"],
  ["ears", "Микрофон и распознавание", "микрофон слух распознавание не слышит имя обращение"],
  ["brain", "Модель ИИ и ключи", "модель мозг llm ключ api openai deepseek claude gpt ollama lm studio облако"],
  ["look", "Тема и оформление", "тема тёмная светлая оформление цвет фон шрифт виджет"],
  ["connect", "Telegram, умный дом, календари", "телеграм telegram бот умный дом алиса яндекс home assistant obsidian календарь ical"],
  ["dw", "Аккаунт dewiar.pro и баланс", "аккаунт вход баланс пополнить знания синхронизация dewiar.pro"],
  ["about", "Версия и обновление", "версия обновление обновить о программе отчёт ошибка"],
  ["home#sn", "Слепок знаний — копия всего", "слепок резервная копия бэкап перенести восстановить новый компьютер"],
  ["features", "Возможности: включить и выключить", "возможности включить выключить игры суфлёр функции"],
  ["personas", "Персонажи", "персонаж лира патрик характер имя создать"],
  ["lessons", "Видеоуроки", "уроки видео обучение академия как пользоваться"],
  ["devices", "Устройства и телефон", "телефон устройство подключить код синхронизация android iphone"],
];
const fdNorm = (s) => String(s || "").toLowerCase().replace(/ё/g, "е").replace(/[«»"“”„()]/g, " ").replace(/\s+/g, " ").trim();
/* грубое русское «по корню»: «письма» ~ «письмо», «пароли» ~ «пароль» — первые 4–5 букв длинного слова */
const fdStem = (w) => w.length >= 6 ? w.slice(0, 5) : w.length >= 4 ? w.slice(0, 4) : w;
function fdNavText(b) { return [...b.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent).join(" ").replace(/\s+/g, " ").trim() || b.textContent.trim(); }
function fdIndex() {
  if (FD.idx && Date.now() - FD.at < 30000) return FD.idx;
  const out = [], seen = new Set();
  const add = (o) => { const k = o.p + "|" + fdNorm(o.t); if (seen.has(k) || !o.t || o.t.length < 3) return; seen.add(k); out.push(o); };
  const navs = $$("nav button[data-p]").filter(b => !b.hidden && b.dataset.p !== "home");
  const names = {};
  navs.forEach(b => { names[b.dataset.p] = fdNavText(b); });
  names.home = "Главная";
  navs.forEach(b => add({ k: "sec", p: b.dataset.p, t: names[b.dataset.p], s: b.title || "", w: 3 }));
  for (const [go, t, words] of FD_SYN) {
    const p = go.split("#")[0], real = p === "mail" ? "home" : p;
    if (real !== "home" && !names[real]) continue;                       // раздел скрыт или выключен — не ведём туда
    if (p === "mail" && !(typeof HM !== "undefined" && HM.mail && HM.mail.on)) continue;
    add({ k: "syn", p: real, sel: go.includes("#") ? "#" + go.split("#")[1] : "", t, s: names[real] || "", words, w: 2 });
  }
  navs.forEach(b => {
    const sec = $("#p-" + b.dataset.p); if (!sec) return;
    $$("h2, h3, summary, label", sec).forEach(el => {
      if (el.closest("[hidden], dialog, .hm-apps, #hm-today, .dwq-back")) return;
      let t = el.tagName === "LABEL" ? ([...el.childNodes].find(n => n.nodeType === 3 && n.textContent.trim()) || el.querySelector("span") || {}).textContent : el.textContent;
      t = String(t || "").replace(/\s+/g, " ").trim().replace(/[:：]$/, "");
      if (!t || t.length > 70 || /^[\d\s.,:—-]+$/.test(t)) return;
      if (fdNorm(t) === fdNorm(names[b.dataset.p]) || fdNorm(names[b.dataset.p]).startsWith(fdNorm(t))) return;   // «Сейф» в разделе «Сейф паролей» — уже есть сам раздел
      add({ k: "set", p: b.dataset.p, el, t, s: names[b.dataset.p], w: el.tagName === "LABEL" ? 1 : 1.5 });
    });
  });
  FD.idx = out; FD.at = Date.now();
  return out;
}
function fdScore(o, q, qs) {
  const t = fdNorm(o.t), extra = fdNorm((o.words || "") + " " + o.s);
  let sc = 0;
  if (t === q) sc += 100;
  else if (t.startsWith(q)) sc += 60;
  else if (t.includes(q)) sc += 40;
  const tw = t.split(" "), ew = extra.split(" ");
  let all = true;
  for (const w of qs) {
    const st = fdStem(w);
    if (tw.some(x => x.startsWith(w))) sc += 14;
    else if (tw.some(x => x.startsWith(st))) sc += 10;
    else if (ew.includes(w)) sc += 25;                         // слово из словаря людей ровно такое («звуки», «мелодия»)
    else if (ew.some(x => x.startsWith(st))) sc += 6;
    else all = false;
  }
  if (!all) return 0;                                            // каждое слово запроса где-то должно найтись
  return sc * o.w;
}
async function fdQA() {
  if (FD.qa) return FD.qa;
  try { const a = await core.call("guide"); FD.qa = Array.isArray(a) ? a : []; } catch (e) { FD.qa = []; }
  return FD.qa;
}
function fdMark(t, q) {
  const n = fdNorm(t), i = q ? n.indexOf(q) : -1;
  if (i < 0 || n.length !== t.length) return escH(t);
  return escH(t.slice(0, i)) + "<mark>" + escH(t.slice(i, i + q.length)) + "</mark>" + escH(t.slice(i + q.length));
}
function fdIcon(p) {
  const b = $(`nav button[data-p="${p}"]`), s = b && b.querySelector("svg");
  return s ? s.outerHTML : '<svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="6.5"/><path d="m20 20-4.4-4.4"/></svg>';
}
async function fdRun() {
  const inp = $("#fd-q"), box = $("#fd-res"); if (!inp || !box) return;
  const raw = inp.value, q = fdNorm(raw);
  if (!q) { fdClose(); return; }
  const qs = q.split(" ").filter(Boolean);
  const hits = fdIndex().map(o => [fdScore(o, q, qs), o]).filter(x => x[0] > 0).sort((a, b) => b[0] - a[0]).map(x => x[1]);
  const top = []; const per = {};
  for (const h of hits) {                                        // не больше трёх строк из одного раздела — чтобы видеть разные
    per[h.p] = (per[h.p] || 0) + 1; if (per[h.p] > 3) continue;
    top.push(h); if (top.length >= 7) break;
  }
  const qa = (await fdQA()).map(x => [fdScore({ t: x.title || "", s: x.lead || "", words: (x.how || []).join(" "), w: 1 }, q, qs), x]).filter(x => x[0] > 0)
    .sort((a, b) => b[0] - a[0]).slice(0, 2).map(x => ({ k: "qa", p: "qa", id: x[1].id, t: x[1].title, s: "Вопрос — ответ" }));
  if (fdNorm($("#fd-q").value) !== q) return;                    // пока ждали — набрали дальше
  FD.hits = top.concat(qa); FD.sel = 0;
  box.hidden = false; $("#fd-q").setAttribute("aria-expanded", "true");
  box.innerHTML = FD.hits.length ? FD.hits.map((h, i) => `<button type="button" class="fd-row${i === 0 ? " on" : ""}${h.k === "qa" ? " qa" : ""}" role="option" id="fd-o${i}" aria-selected="${i === 0}" data-i="${i}">
      <i class="fd-ic" aria-hidden="true">${h.k === "qa" ? '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8.5"/><path d="M9.6 9.7a2.5 2.5 0 0 1 4.9.6c0 1.7-2.5 1.9-2.5 3.6"/><circle cx="12" cy="16.6" r=".6"/></svg>' : fdIcon(h.p)}</i>
      <span class="fd-t"><b>${fdMark(h.t, q)}</b><small>${escH(h.k === "sec" ? (h.s || "раздел") : h.k === "qa" ? "Вопрос — ответ" : h.s)}</small></span>
      <span class="fd-go" aria-hidden="true">↵</span></button>`).join("")
    + `<p class="fd-foot"><span>↑↓ — выбрать · Enter — открыть · Esc — закрыть</span></p>`
    : `<div class="fd-none"><b>Ничего не нашлось по «${escH(raw.trim())}»</b><span>Попробуйте другое слово — или спросите Лиру, она знает всё о программе.</span>
       <button type="button" class="btn small" id="fd-ask">Спросить Лиру</button></div>`;
  $("#fd-q").setAttribute("aria-activedescendant", FD.hits.length ? "fd-o0" : "");
  $$("#fd-res .fd-row").forEach(b => { b.onmousedown = (e) => e.preventDefault(); b.onclick = () => fdOpen(FD.hits[+b.dataset.i]); });
  if ($("#fd-ask")) { $("#fd-ask").onmousedown = (e) => e.preventDefault(); $("#fd-ask").onclick = () => { const t = raw.trim(); fdClose(true); if (typeof qaAsk === "function") qaAsk(`Где в программе: ${t}?`); }; }
}
function fdSel(d) {
  if (!FD.hits.length) return;
  FD.sel = (FD.sel + d + FD.hits.length) % FD.hits.length;
  $$("#fd-res .fd-row").forEach((b, i) => { b.classList.toggle("on", i === FD.sel); b.setAttribute("aria-selected", String(i === FD.sel)); });
  $("#fd-q").setAttribute("aria-activedescendant", "fd-o" + FD.sel);
  const r = $(`#fd-o${FD.sel}`); if (r) r.scrollIntoView({ block: "nearest" });
}
function fdClose(clear) {
  const box = $("#fd-res"); if (box) { box.hidden = true; box.innerHTML = ""; }
  const q = $("#fd-q"); if (q) { q.setAttribute("aria-expanded", "false"); if (clear) q.value = ""; }
  FD.hits = [];
}
/* открыть найденное: раздел; настройку — с прокруткой к ней и мягкой подсветкой (раскрыть <details>, если она внутри) */
function fdOpen(h) {
  if (!h) return;
  fdClose(true); $("#fd-q").blur();
  if (h.k === "qa") {
    hmGo("qa");
    setTimeout(async () => { if (typeof qaLoad === "function") await qaLoad(); if (typeof qaOpen === "function") qaOpen(h.id); }, 120);
    return;
  }
  if (h.p !== "home") hmGo(h.p);
  setTimeout(() => {
    let el = h.el || (h.sel && $(h.sel));
    if (!el) return;
    const det = el.closest("details"); if (det && !det.open) det.open = true;
    if (el.tagName === "SUMMARY" && el.parentElement) el.parentElement.open = true;
    const box = el.closest(".prof, .card, .hm-mail, .sn-wrap, details, .f, label") || el;
    box.scrollIntoView({ block: "center", behavior: "smooth" });
    box.classList.remove("fd-hl"); void box.offsetWidth; box.classList.add("fd-hl");
    setTimeout(() => box.classList.remove("fd-hl"), 2200);
    // курсор — только в поле ввода: на флажке или переключателе случайный пробел или стрелка меняли бы настройку
    // (30.10: «Текстовый режим» включился незаметно — голос пропал)
    const TXT = "input:not([type=hidden]):not([type=checkbox]):not([type=radio]):not([type=range]), select, textarea";
    const f = box.matches(TXT) ? box : box.querySelector(TXT);
    if (f && h.k === "set" && el.tagName === "LABEL") setTimeout(() => f.focus({ preventScroll: true }), 350);
  }, h.p === "home" ? 0 : 260);
}
function fdWire() {
  const q = $("#fd-q"); if (!q || q._fd) return; q._fd = 1;
  let t = 0;
  q.addEventListener("input", () => { clearTimeout(t); t = setTimeout(fdRun, 60); });
  q.addEventListener("focus", () => { FD.at = 0; if (q.value.trim()) fdRun(); });
  q.addEventListener("blur", () => setTimeout(() => { if (document.activeElement !== q) fdClose(); }, 120));
  q.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown") { e.preventDefault(); fdSel(1); }
    else if (e.key === "ArrowUp") { e.preventDefault(); fdSel(-1); }
    else if (e.key === "Enter") { e.preventDefault(); if (FD.hits.length) fdOpen(FD.hits[FD.sel]); else if ($("#fd-ask")) $("#fd-ask").click(); }
    else if (e.key === "Escape") { e.preventDefault(); if (q.value) { q.value = ""; fdClose(); } else q.blur(); }
  });
}
document.addEventListener("keydown", (e) => {                   // Ctrl+K / ⌘K — найти из любого места студии
  if (!((e.ctrlKey || e.metaKey) && !e.altKey && (e.key || "").toLowerCase() === "k" || (e.ctrlKey || e.metaKey) && e.code === "KeyK")) return;
  if ($(".dwq-back") || $("dialog[open]")) return;
  e.preventDefault();
  if (!$("#p-home").classList.contains("cur")) hmGo("home");
  setTimeout(() => { const q = $("#fd-q"); if (q) { q.focus(); q.select(); } }, 60);
});
fdWire();
window.fdWire = fdWire;
