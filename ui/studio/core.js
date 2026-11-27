/* Студия Dewiar, основа: общее состояние, сохранение настроек и переключение разделов.
   S — снимок настроек из ядра (приходит в "hello" и событии "settings" — см. dewiar.js), personas/active/entities — личности.
   save(patch) шлёт core.call("settings_save", { patch }): ядро сливает частичный patch с настройками и возвращает их целиком.
   Клик по разделу слева подгружает его данные функциями из других файлов студии.
   ui/settings.html подключает файлы студии по порядку, и все они делят одну глобальную область: этот файл идёт первым,
   поэтому всё, что он вызывает сразу при загрузке, объявлено здесь же или раньше (assets/*.js); функции других файлов
   вызываются только из обработчиков кликов, когда всё уже загружено. */
const $ = (s, r = document) => r.querySelector(s), $$ = (s, r = document) => [...r.querySelectorAll(s)];
// экранирование для innerHTML — общее для всех файлов студии (здесь, в первом файле: 24.10 у человека «escH is not defined»
// при подключении по коду — общий помощник жил в folder.js и пропал вместе с ним)
/* Страница-результат (задача, «Папка»): только srcdoc без allow-same-origin и с CSP — у неё нет ни прав студии (ключ в
   адресе, core.call родителя), ни файлов компьютера (XHR к file://), ни сети. Ресурсы — только встроенные (data:, blob:);
   так страницу уже видели в Windows. Рецензия выпуска 5 (05.11): file:// + allow-same-origin отдавали странице студию. */
const SAFE_CSP = "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: blob:; font-src data:; " +
  "media-src data: blob:; form-action 'none'; frame-src 'none'; base-uri 'none'";
const SAFE_SANDBOX = "allow-scripts";
/* <meta http-equiv> страницы (refresh, свой CSP, set-cookie…) — прочь. Не регуляркой: четвёртая рецензия обошла её
   «>» внутри кавычек и сущностью в значении. Каждый «<meta» разбирается так, как его разберёт браузер (атрибуты, значения
   в кавычках и без), и тег с атрибутом http-equiv заменяется пробелом (не склеится в новый тег). Поиск — по всем вхождениям
   исходной строки, а не «с конца прошлого тега»: «<meta» внутри строки скрипта не спрячет настоящий тег за собой.
   Повторяем, пока что-то убирается. То же в Python: core/export.py, strip_meta_equiv. */
function stripMetaEquiv(html) {
  const WS = /[\t\n\f\r ]/;
  let s = String(html == null ? "" : html);
  for (let pass = 0; pass < 8; pass++) {
    const low = s.replace(/[A-Z]/g, c => c.toLowerCase()), cut = [];   // только A–Z, как браузер: «İ» — два знака (рецензия 5e)
    for (let j = low.indexOf("<meta"); j >= 0; j = low.indexOf("<meta", j + 5)) {
      const c = s[j + 5];
      if (c !== undefined && !WS.test(c) && c !== "/" && c !== ">") continue;
      let k = j + 5, end = -1, eq = false;
      while (k < s.length) {
        const ch = s[k];
        if (WS.test(ch) || ch === "/") { k++; continue; }
        if (ch === ">") { end = k + 1; break; }
        let n = s[k++];                                          // первый знак имени (и «=») — часть имени
        while (k < s.length && !WS.test(s[k]) && s[k] !== "/" && s[k] !== ">" && s[k] !== "=") n += s[k++];
        if (n.replace(/[A-Z]/g, c => c.toLowerCase()) === "http-equiv") eq = true;
        while (k < s.length && WS.test(s[k])) k++;
        if (s[k] === "=") {
          k++; while (k < s.length && WS.test(s[k])) k++;
          const q = s[k];
          if (q === '"' || q === "'") { const e = s.indexOf(q, k + 1); k = e < 0 ? s.length : e + 1; }
          else while (k < s.length && !WS.test(s[k]) && s[k] !== ">") k++;
        }
      }
      if (end < 0) { cut.push([j, s.length]); break; }       // тег не закрыт до конца: браузер его отбросит — и мы
      if (eq) cut.push([j, end]);
    }
    if (!cut.length) return s;
    let out = "", at = 0;
    cut.sort((x, y) => x[0] - y[0]).forEach(([a, b]) => { if (b <= at) return; out += s.slice(at, Math.max(at, a)) + " "; at = b; });
    s = out + s.slice(at);
  }
  return s;
}
/* CSP — самой первой строкой, до всего, что есть у страницы (третья рецензия): вставка «после <head>» обходилась —
   скрипт до <head>, «<head>» в комментарии или строке, и meta оказывалась в <body>, где CSP не действует. Шрифты
   предпросмотра сайтов приходят внутри страницы (data:, core/sites_render.py) — файлов с диска фрейму не нужно. */
function safeDoc(html) {
  const meta = `<meta http-equiv="Content-Security-Policy" content="${SAFE_CSP}">`;
  html = stripMetaEquiv(String(html || "").replace(/^\ufeff?\s*<!doctype[^>]*>/i, ""));
  return "<!doctype html>" + meta + html;
}
function safeFrame(html, cls) {                    // -> <iframe> (srcdoc ставится свойством — без экранирования в разметке)
  const f = document.createElement("iframe");
  f.setAttribute("sandbox", SAFE_SANDBOX);
  f.setAttribute("referrerpolicy", "no-referrer");
  if (cls) f.className = cls;
  f.srcdoc = safeDoc(html);
  return f;
}
function escH(t) { return String(t == null ? "" : t).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }
// ошибки страницы — в журнал ядра (в отчёт): какой файл не загрузился и почему видно сразу, без догадок
window.__jsErr = window.__jsErr || []; window.__jsErrAll = window.__jsErrAll || [];
/* 15.11 (№749: «Музыка: не открывает папки, не открывается выбор Радио», а в отчёте — ни одной ошибки страницы): ошибки
   уходили в журнал один раз, через 3 с после подключения, а случившиеся позже (раздел открыли потом) — терялись. Теперь
   каждая — в журнал ядра через 2 с (пачкой, не больше 30 за сеанс). */
let jsErrT = 0, jsErrSent = 0;
function jsErr(t) {
  window.__jsErr.push(String(t).slice(0, 300));
  if (window.__jsErrAll.length < 10) window.__jsErrAll.push(String(t).slice(0, 300));   // для плашки «не целиком» — и после отправки
  if (jsErrT || jsErrSent >= 30) return;
  jsErrT = setTimeout(() => {
    jsErrT = 0;
    if (!(window.core && core.connected) || !window.__jsErr.length) return;   // до связи — их отправит news.js после hello
    const errs = window.__jsErr.splice(0, 30 - jsErrSent); jsErrSent += errs.length;
    core.call("js_errors", { errors: errs }).catch(() => {});
  }, 2000);
}
window.addEventListener("error", (e) => { if (/^ResizeObserver loop/i.test(e.message || "")) return; if (e.target && e.target !== window) return; jsErr(`${e.message} @ ${(e.filename || "").split("/").pop()}:${e.lineno || 0}`); });
window.addEventListener("unhandledrejection", (e) => { const r = e.reason; if (!r || !(r instanceof Error) || !/TypeError|ReferenceError|SyntaxError|RangeError/.test(r.name)) return;
  jsErr(`${r.name}: ${r.message} @ ${String((r.stack || "").split("\n")[1] || "").trim().split("/").pop().replace(/\)$/, "")}`); });
// незагрузившийся файл (№747) ловит assets/boot.js — первый скрипт окна, раньше всех файлов
/* №530 (04.11, «раздел „Мозг“ после обновления пустой»): человек правил файлы программы сам, после обновления часть файлов
   студии не сошлась — скрипт упал ещё до подключения к ядру, и студия молча показывала пустые поля и «нет связи с ядром»,
   хотя ядро работало. Теперь связь отмечается отсюда (первый файл студии), а если основной файл студии (studio/dewiar.js)
   не дошёл до конца — вверху честная плашка: какой файл с ошибкой и что делать (переустановить поверх), а ошибки — в журнал ядра. */
function studioBroken() {
  if (window.__studioReady || document.getElementById("studio-broken")) return;
  const errs = (window.__jsErrAll || window.__jsErr || []).slice(0, 3);
  const file = (errs.map(e => (/ @ ([\w.-]+\.(?:js|html)):\d+/.exec(e) || [])[1]).find(Boolean)) || "";
  const b = document.createElement("div"); b.id = "studio-broken"; b.setAttribute("role", "alert");
  b.style.cssText = "position:fixed;left:50%;top:14px;transform:translateX(-50%);z-index:9999;max-width:min(760px,calc(100vw - 32px));"
    + "padding:12px 16px;border-radius:14px;background:#3a1f24;color:#ffe3e6;box-shadow:0 12px 34px -10px rgba(0,0,0,.6);font:13.5px/1.45 Manrope,'Segoe UI',sans-serif";
  b.innerHTML = `<b style="display:block;margin-bottom:4px">Студия загрузилась не целиком${file ? ` — ошибка в файле «${escH(file)}»` : ""}</b>`
    + "Ядро работает, но часть страницы не открылась. Так бывает, когда файлы программы изменены вручную или повреждены. "
    + "Переустановите Dewiar поверх — установщиком с dewiar.pro: настройки, заметки и память сохранятся."
    + (errs.length ? `<small style="display:block;margin-top:6px;opacity:.7;word-break:break-word">${escH(errs[0])}</small>` : "");
  document.body.appendChild(b);
  if (window.core && core.connected) core.call("js_errors", { errors: ["студия не загрузилась целиком", ...errs] }).catch(() => {});
}
if (window.core) core.on("hello", () => {
  const c = document.getElementById("conn"); if (c) { c.classList.add("ok"); c.querySelector("span").textContent = "ядро на связи"; }
  const check = () => setTimeout(studioBroken, 1500);
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", check); else check();
});
/* №566 (снимок): файл бросили мимо поля приёма — окно открывало его вместо студии (на Linux — «кракозябры» во всё окно,
   студию приходилось закрывать). Файл мимо поля: в «Чате» — во вложения сообщения, в других разделах — не открываем. */
const dropFiles = (e) => !!(e.dataTransfer && [...(e.dataTransfer.types || [])].includes("Files"));
document.addEventListener("dragover", (e) => { if (dropFiles(e) && !e.defaultPrevented) { e.preventDefault(); e.dataTransfer.dropEffect = document.querySelector("#p-chat.cur") ? "copy" : "none"; } });
document.addEventListener("drop", (e) => {
  if (!dropFiles(e) || e.defaultPrevented) return;
  e.preventDefault();
  const fs = [...(e.dataTransfer.files || [])];
  if (fs.length && document.querySelector("#p-chat.cur") && typeof chatAddFiles === "function") chatAddFiles(fs);
  else if (fs.length && typeof toast === "function") toast("Сюда файл не принять — перетащите его в «Чат» или в поле с пунктиром", 3500);
});
let S = null, personas = [], active = "lira", entities = [];
// логотип в меню виден всегда — в покой (~6 кадров/с) уже через 4 с тишины, а не через 20 (03.11: на слабом компьютере
// живой логотип один занимал до половины времени страницы)
const brand = new DewiarEntity($("#brand"), { style: "nexus", color: "#8A9BFF", ring: false, restAfter: 4000 });
const COLORS = ["#FFB547", "#3DF5C8", "#4FC3FF", "#9BD4FF", "#B78CFF", "#FF7AB6", "#FF6B5A", "#9BE15D", "#F5E663", "#7C8CFF", "#E6EEFF", "#16181D"];   // чёрный (владелец 22.11) — диск облика у него светлый (entities.js dark)
const STYLE_NAMES = { nexus: "Нейросфера", aura: "Сфера", holobrain: "Голограмма мозга", lattice: "Кристалл", orbital: "Орбиты", tactical: "Радар", rings: "Кольца", strings: "Струны", particles: "Частицы" };

function toast(t, ms) { const el = $("#toast"); el.textContent = t; el.classList.add("show"); clearTimeout(el._t); el._t = setTimeout(() => el.classList.remove("show"), ms || 1800); }
const get = (path) => path.split(".").reduce((o, k) => (o || {})[k], S);
function patchOf(path, v) { const keys = path.split("."), out = {}; let cur = out; keys.slice(0, -1).forEach(k => cur = cur[k] = {}); cur[keys.at(-1)] = v; return out; }
let saveT = {};
/* ядро вернуло пусто (сбой, старая версия) — прежние настройки остаются, а не S = null: иначе падает всё, что читает S (0.99: набор «Для себя» сохраняется сразу после hello) */
function save(patch, quiet) {
  return core.call("settings_save", { patch }).then(s => { S = s || S; if (!quiet) toast("Сохранено"); refreshStatic(); }).catch(e => toast(e.message));
}

/* «Безопасность» → «Ваши данные»: общий текст assets/privacy.js (тот же — на телефоне и у самой помощницы) */
if (window.DEWIAR_PRIVACY && $("#priv-box")) {
  const e = (t) => String(t).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  $("#priv-box").innerHTML = ($("#priv-box").closest("details") ? "" : `<h3 style="font-size:15px;margin-bottom:8px">${e(DEWIAR_PRIVACY.title)}</h3>`)
    + DEWIAR_PRIVACY.items.map(([t, x]) => `<p class="hint" style="margin:0 0 6px"><b style="color:var(--ink);font-weight:600">${e(t)}.</b> ${e(x)}</p>`).join("");
}

/* ---------- Лёгкая студия (03.11, группа: «программа становится перегруженной… полная оболочка Dewiar подтормаживает») ----------
   Раздел строит тяжёлое — данные из ядра, карточки, облики — при первом открытии, а не при запуске:
   secLazy(p, fn) — fn один раз, когда раздел p впервые открыт и связь с ядром уже есть (иначе — сразу после hello);
   secSeen(p) — открывался ли раздел; secOn(p) — виден сейчас (открыт, и окно не свёрнуто).
   secPoll(p, ms, fn) — опрос ядра, который идёт, только пока раздел виден: закрыли раздел или свернули окно — таймера нет,
   вернулись — опрос продолжается. window.studioSec — то же для проверок (tests/studio_light1103_test.py). */
const SEC = { seen: new Set(), lazy: {}, done: new Set(), polls: [] };
const secEl = (p) => document.getElementById("p-" + p);
const secOn = (p) => !document.hidden && !!secEl(p) && secEl(p).classList.contains("cur");
const secSeen = (p) => SEC.seen.has(p);
function secLazy(p, fn) {
  (SEC.lazy[p] = SEC.lazy[p] || []).push(fn);
  if (secSeen(p) && S) secLazyRun(p);
}
function secLazyRun(p) {
  if (!S) return;
  (SEC.lazy[p] || []).forEach(fn => { if (SEC.done.has(fn)) return; SEC.done.add(fn); try { fn(); } catch (e) { console.warn("раздел", p, e); jsErr(`раздел «${p}»: ${e && e.message} @ ${String((e && e.stack || "").split("\n")[1] || "").trim().split("/").pop().replace(/\)$/, "")}`); } });
}
/* связь с ядром появилась (hello): разделам, открытым раньше, — их первая загрузка */
function secHello() { SEC.seen.forEach(secLazyRun); }
function secPoll(p, ms, fn) { const o = { p, ms, fn, t: 0, busy: false }; SEC.polls.push(o); secPollRun(o); return o; }
function secPollRun(o) {
  if (!secOn(o.p)) { clearTimeout(o.t); o.t = 0; return; }
  if (o.t || o.busy) return;
  o.t = setTimeout(async () => {
    o.t = 0; if (!secOn(o.p)) return;
    o.busy = true; try { await o.fn(); } catch (e) { } o.busy = false;
    secPollRun(o);
  }, o.ms);
}
const secPollsKick = () => SEC.polls.forEach(secPollRun);
document.addEventListener("visibilitychange", secPollsKick);
function secOpen(p) {
  SEC.seen.add(p);
  secLazyRun(p);
  secPollsKick();
  document.dispatchEvent(new CustomEvent("studio-sec", { detail: p }));   // разделам со своей анимацией — продолжить
}
{ const c = document.querySelector("main section.cur"); if (c) SEC.seen.add(c.id.replace(/^p-/, "")); }   // «Главная» открыта сразу
window.studioSec = { seen: () => [...SEC.seen], polls: () => SEC.polls.filter(o => o.t || o.busy).map(o => o.p) };

/* «Облегчённый вид» (ui.studio_lite: "auto" | "on" | "off"; «Оформление» → «Скорость»). html.st-lite (theme.css): без
   размытия и «стекла» с неподвижным фоном, мягкие тени неоморфизма — короче, украшения без бесконечной анимации,
   облики персонажей — не чаще ~20 кадров/с. "auto" — сам, если компьютер слабый (мало ядер или памяти, «слабый» по
   оценке ядра) или кадры студии рисуются медленно. Последнее решение — в localStorage: theme.js ставит класс ещё в <head>,
   чтобы при запуске не было «тяжёлого» первого кадра. */
const LITE = { auto: false, why: "" };
try { if (localStorage.getItem("studio_lite_auto")) { LITE.auto = true; LITE.why = localStorage.getItem("studio_lite_auto"); } } catch (e) { }
function liteMode() { return (((S && S.ui) || {}).studio_lite) || "auto"; }
function liteOn() { const m = liteMode(); return m === "on" || (m === "auto" && LITE.auto); }
function studioLite() {
  if (!S) return;
  const on = liteOn();
  document.documentElement.classList.toggle("st-lite", on);
  if (window.DewiarEntity) DewiarEntity.lite = on;
  try { localStorage.setItem("studio_lite", on ? "1" : "0"); } catch (e) { }
  if (typeof liteRender === "function") liteRender();
}
function liteAuto(why) {
  if (LITE.auto || !why) return;
  LITE.auto = true; LITE.why = why;
  try { localStorage.setItem("studio_lite_auto", why); } catch (e) { }
  studioLite();
}
/* слабое железо: по браузеру — сразу; по оценке ядра (device.level) — из dewiar.js, когда пришло */
(() => {
  const n = navigator.hardwareConcurrency || 0, m = navigator.deviceMemory || 0;
  if ((n && n <= 2) || (m && m <= 2)) liteAuto(n && n <= 2 ? `${n} ${n === 1 ? "ядро" : "ядра"} процессора` : `${m} ГБ памяти`);
})();
/* медленные кадры: через 4 с после открытия — 90 кадров; если заметная доля дольше 50 мс — студии тяжело */
function liteProbe() {
  if (LITE.auto || document.hidden) return;
  let last = 0, n = 0, slow = 0;
  const step = (t) => {
    if (last) { n++; if (t - last > 50) slow++; }
    last = t;
    if (n < 90) return requestAnimationFrame(step);
    if (slow > 22) liteAuto("кадры рисуются медленно");
  };
  requestAnimationFrame(step);
}
setTimeout(liteProbe, 4000);
/* №1130 (27.11, CachyOS, NVIDIA, 16 ядер: «прокрутка и курсор в окнах приложения — пункт меню всплывает с сильной задержкой,
   фризы при вводе; процессор не загружен»). В простое кадры быстрые — замер выше молчит, а тяжело как раз при прокрутке:
   программная отрисовка перерисовывает фон и «стекло» на каждом шаге. Замер по делу — кадры первые 1,2 с прокрутки;
   медленно два раза подряд — облегчённый вид (одна заминка — не повод) */
const LITE_SCROLL = { busy: false, bad: 0, runs: 0 };
function liteScrollProbe() {
  if (LITE.auto || LITE_SCROLL.busy || LITE_SCROLL.runs >= 6 || document.hidden || liteMode() !== "auto") return;
  LITE_SCROLL.busy = true; LITE_SCROLL.runs++;
  let t0 = 0, last = 0, n = 0, slow = 0;
  const step = (t) => {
    if (!t0) t0 = t;
    if (last) { n++; if (t - last > 50) slow++; }
    last = t;
    if (t - t0 < 1200) return requestAnimationFrame(step);
    LITE_SCROLL.busy = false;
    if (n < 8 || slow / n > 0.3) { if (++LITE_SCROLL.bad >= 2) liteAuto("прокрутка рисуется медленно"); }
    else LITE_SCROLL.bad = 0;
  };
  requestAnimationFrame(step);
}
addEventListener("wheel", liteScrollProbe, { passive: true, capture: true });

/* навигация */
/* Вкладки вместо пунктов меню. «Душа» (дневник, душа, конституция, «Обо мне») была одним пунктом с вкладками; 19.11
   (владелец: «самые не популярные разделы… убрать лишнее, но элегантно, чтобы и было, но не мелькало») так же собраны:
   «Память и душа», «Обучение» (неделя с Лирой, видеоуроки, вопрос — ответ, что я умею), «Платежи» + «Семья»,
   «Dewiar.pro» + «Рефералы». Каждая страница остаётся своей <section>, сверху — полоска вкладок; вкладку открывает
   скрытая кнопка nav (.sub) с тем же data-p, а первый пункт группы слева возвращает на последнюю открытую вкладку
   (tab_<первый>). Скрытый на «Главной» или выключенный раздел — скрыт и во вкладках (navTabsSync). */
const NAV_TABS = [
  [["memory", "nav.memory", "Память"], ["diary", "nav.diary.tab", "Дневник"], ["soul", "nav.soul", "Душа"], ["const", "nav.const", "Конституция"], ["me", "nav.me", "Обо мне"]],
  [["course", "nav.course", "Неделя с Лирой"], ["lessons", "nav.lessons", "Видеоуроки"], ["qa", "nav.qa", "Вопрос — ответ"], ["tricks", "nav.tricks", "Что я умею"]],
  [["pay", "nav.pay", "Платежи"], ["family", "nav.family", "Семья"]],
  [["dw", "nav.dw", "Dewiar.pro"], ["ref", "nav.ref", "Рефералы"]]];
const navTabGroup = (p) => NAV_TABS.find(g => g.some(t => t[0] === p));
const lsGet = (k, d) => { try { return LS.get(k, d); } catch (e) { return d; } };   // LS объявлен позже, в memory.js
function navGo(p) { const b = $(`nav button[data-p="${p}"]`); if (!b) return; b._direct = true; b.click(); b._direct = false; }
const soulGo = navGo;                                      // прежнее имя
NAV_TABS.forEach(g => g.forEach(([p]) => {
  const sec = $("#p-" + p); if (!sec) return;
  const bar = document.createElement("div"); bar.className = "stabs ntabs";
  bar.innerHTML = g.map(([q, k, t]) => `<button type="button" data-go="${q}" data-i18n="${k}">${t}</button>`).join("");
  $$("button", bar).forEach(x => x.onclick = () => navGo(x.dataset.go));
  sec.insertBefore(bar, sec.firstChild);
}));
/* точка «новое» у спрятанного пункта («Семья»: зовут в семью) — на его вкладке и у первого пункта группы слева */
NAV_TABS.forEach(g => {
  const lead = $(`nav button[data-p="${g[0][0]}"]`), dots = g.slice(1).map(([p]) => [p, $(`nav button[data-p="${p}"] .ndot`)]).filter(x => x[1]);
  if (!lead || !dots.length) return;
  const mir = document.createElement("i"); mir.className = "ndot"; mir.setAttribute("aria-hidden", "true"); lead.appendChild(mir);
  const sync = () => {
    mir.classList.toggle("on", dots.some(([, d]) => d.classList.contains("on")) && !lead.querySelector(".ndot:not(:last-child).on"));
    dots.forEach(([p, d]) => $$(`.ntabs button[data-go="${p}"]`).forEach(x => x.classList.toggle("dot", d.classList.contains("on"))));
  };
  dots.forEach(([, d]) => new MutationObserver(sync).observe(d, { attributes: true, attributeFilter: ["class"] }));
});
/** Вкладки — по меню: скрытый раздел (на «Главной», в «Возможностях») — без вкладки; группа из одной — без полоски */
/* Раздел «по желанию» (HM_OPTIN, home.js: «Семья») ещё не включён — вкладка «+ Семья», как строка «+» в меню: нажали —
   включено и открыто (выключить — в «Возможностях») */
function navOptin(p) {
  if (typeof HM_NAV === "undefined" || typeof HM_OPTIN === "undefined") return "";
  const id = Object.keys(HM_NAV).find(a => HM_NAV[a].includes(p)), feat = id && HM_OPTIN[id] && HM_FEAT[id];
  if (!feat || ((S && S.features) || {})[feat] === true) return "";
  return typeof hmApps !== "function" || hmApps().includes(id) ? feat : "";
}
function navTabsSync() {
  NAV_TABS.forEach(g => {
    const opt = {}, vis = new Set(g.filter(([p], i) => { const b = $(`nav button[data-p="${p}"]`); if (!b) return false;
      if (i === 0 || !b.hidden) return true; return !!(opt[p] = navOptin(p)); }).map(t => t[0]));
    g.forEach(([p]) => { const bar = $(`#p-${p} > .ntabs`); if (!bar) return;
      $$("button", bar).forEach(x => { const q = x.dataset.go; x.hidden = !vis.has(q); x.classList.toggle("nopt", !!opt[q]);
        x.onclick = opt[q] ? async () => { await save({ features: { [opt[q]]: true } }, true);
          if (window.featuresApply) featuresApply(); toast(`«${x.textContent.trim()}»: включено — выключить можно в «Возможностях»`); navGo(q); }
          : () => navGo(q); });
      bar.hidden = vis.size < 2; });
  });
}
window.navTabsSync = navTabsSync;
$$("nav button[data-p]").forEach(b => b.onclick = () => {
  const tg = navTabGroup(b.dataset.p);
  if (tg && tg[0][0] === b.dataset.p && !b._direct) {          // первый пункт группы слева — вкладка, на которой были
    const t = lsGet("tab_" + b.dataset.p, b.dataset.p), tb = $(`nav button[data-p="${t}"]`);
    if (t !== b.dataset.p && tg.some(x => x[0] === t) && tb && !tb.hidden) return navGo(t);
  }
  $$("nav button").forEach(x => x.classList.toggle("cur", x === b));
  $$("section").forEach(s => s.classList.toggle("cur", s.id === "p-" + b.dataset.p));
  secOpen(b.dataset.p);
  if (core.connected) core.call("course_seen", { section: b.dataset.p }).catch(() => {});   // курс: «откройте …» — шаг засчитан
  if (tg) { $(`nav button[data-p="${tg[0][0]}"]`).classList.add("cur"); $$(".ntabs button").forEach(x => x.classList.toggle("on", x.dataset.go === b.dataset.p)); try { LS.set("tab_" + tg[0][0], b.dataset.p); } catch (e) { } }
  if (b.dataset.p === "soul") loadSoul();
  if (b.dataset.p === "const") loadConst();
  if (b.dataset.p === "ref") loadRefs();             // «Рефералы» — с облака, настройки не нужны
  if (b.dataset.p === "notes") loadNotesPage();      // «Заметки» — файлы папки ассистента
  if (b.dataset.p === "pay" && window.loadPayPage) loadPayPage();      // «Платежи» (studio/pay.js)
  if (b.dataset.p === "vault" && window.loadVaultPage) loadVaultPage();  // «Сейф паролей» (studio/vault.js)
  if (b.dataset.p === "music" && window.loadMyMusic) loadMyMusic();     // «Музыка» — своя папка (studio/mymusic.js)
  if (b.dataset.p === "kids" && window.loadKids) loadKids();             // «Дети» — детский режим (studio/kids.js)
  if (b.dataset.p === "family" && window.loadFamily) loadFamily();       // «Семья» — общий бюджет (studio/family.js)
  if (b.dataset.p === "clients" && window.loadClients) loadClients();     // «Клиенты» — личная CRM (studio/clients.js)
  if (b.dataset.p === "insight" && window.loadInsight) loadInsight();     // «Радар» — аналитик ниши (studio/insight.js)
  if (b.dataset.p === "mailing" && window.loadMailing) loadMailing();     // «Рассылка» — каждому своё письмо (studio/mailing.js)
  if (b.dataset.p === "sitechat" && window.loadSitechat) loadSitechat();  // «Чат для сайта» (studio/sitechat.js)
  if (b.dataset.p === "sites" && window.loadSites) loadSites();             // «Сайты» (studio/sites.js)
  if (b.dataset.p === "lessons" && window.loadLessons) loadLessons();     // «Видеоуроки» (studio/lessons.js)
  if (b.dataset.p === "team" && window.loadTeam) loadTeam();             // «Поручения» — сотрудникам (studio/team.js)
  if (b.dataset.p === "devices" && window.loadMyDevices) loadMyDevices();   // «Устройства» — все мои устройства (studio/devices.js)
  if (b.dataset.p === "council" && window.loadCouncil) loadCouncil();       // «Совет ИИ» (studio/council.js)
  if (b.dataset.p === "podcast" && window.loadPodcasts) loadPodcasts();    // «Подкасты» (studio/podcast.js)
  if (b.dataset.p === "pbot" && window.loadPbot) loadPbot();                // «Бот персонажа» (studio/pbot.js)
  if (b.dataset.p === "qa" && window.loadQA) loadQA();
  if (b.dataset.p === "course" && window.loadCourse) loadCourse();       // «Неделя с Лирой» — курс (studio/course.js)                   // «Вопрос — ответ» — руководство (studio/qa.js)
  if (b.dataset.p === "home" && window.loadHome) loadHome();   // «Главная» — и до настроек (S): карточки «Сегодня» свежие при каждом входе
  if (!S) return;                                    // данные подгрузятся после связи с ядром
  if (b.dataset.p === "sound") loadDevices();
  if (b.dataset.p === "about") core.call("status").then(renderStatus).catch(() => {});
  if (b.dataset.p === "skills") { loadPlugins(); core.call("skills").then(renderSkills).catch(() => {}); core.call("mcp_status").then(renderMcp).catch(() => {});
    if (S.skills && S.skills.catalog_url) { $("#cat-url").value = S.skills.catalog_url; openCatalog(); } }
  if (b.dataset.p === "me") loadMe();
  if (b.dataset.p === "docs") loadDocs();             // «Документы» — папки, по которым Лира ищет (studio/links.js)
  if (b.dataset.p === "tricks") loadTricks();       // «Что я умею» — data/tricks.json через ядро
  if (b.dataset.p === "memory") { loadNotes(); loadMemory(!!mNet); setTimeout(mPanes, 0); }   // обновление раз в 30 с — memory.js (secPoll)
  if (b.dataset.p === "voice") core.call("voices_warm").catch(() => {});
  if (b.dataset.p === "brain") core.call("cloud_status", { refresh: true }).then(cloudFill).catch(() => {});
  if (b.dataset.p === "dw") { dwLoad(); dwQr(); }
  if (b.dataset.p === "hands") { core.call("tools").then(renderTools).catch(() => {}); }
  if (b.dataset.p === "reminders") loadReminders();
  if (b.dataset.p === "servers") svLoad();
  if (b.dataset.p === "calendar") loadCalendar();
  if (b.dataset.p === "folder") loadFolder();
  if (b.dataset.p === "diary") loadDiary();
  if (b.dataset.p === "safety") { loadSafety(); loadVault(); loadBackups(); }
  if (b.dataset.p === "tasks") loadTasks();
  if (b.dataset.p === "prompter") loadMeetings();
  if (b.dataset.p === "about") core.call("update_status").then(u => { if (typeof renderUpdate === "function") renderUpdate(u); }).catch(() => {});   // №499: нажали раньше, чем загрузился tasks.js
  if (b.dataset.p === "voice") loadVosk();
  if (b.dataset.p === "look") loadLook();
  if (b.dataset.p === "close") loadClose(true);
  if (b.dataset.p === "chat" && typeof loadChat === "function") loadChat();   // №892: нажали раньше, чем загрузился chat.js
});
/* Идея №156 (11.2026): «кнопка „спрятать меню слева“ — чтобы раздел, например чат, был на всю ширину». Кнопка в углу меню
   прячет его, маленькая кнопка слева вверху — возвращает; Ctrl+B (и Ctrl+И в русской раскладке) — то же с клавиатуры.
   Выбор помнится (localStorage studio_nav_off; theme.js ставит html.nav-off ещё до первого кадра). */
function navToggle(off) {
  const root = document.documentElement;
  off = off === undefined ? !root.classList.contains("nav-off") : !!off;
  root.classList.toggle("nav-off", off);
  try { localStorage.setItem("studio_nav_off", off ? "1" : "0"); } catch (e) { }
  const h = $("#nav-hide"), s = $("#nav-show");
  if (h) h.setAttribute("aria-expanded", off ? "false" : "true");
  if (s) s.setAttribute("aria-expanded", off ? "false" : "true");
  const f = off ? s : h; if (f && document.activeElement && (document.activeElement === h || document.activeElement === s)) f.focus({ preventScroll: true });
  window.dispatchEvent(new Event("resize"));              // схемы, календарь и графики подстраиваются под новую ширину
}
if ($("#nav-hide")) $("#nav-hide").onclick = () => navToggle(true);
if ($("#nav-show")) $("#nav-show").onclick = () => navToggle(false);
navToggle(document.documentElement.classList.contains("nav-off"));
document.addEventListener("keydown", (e) => {
  if (!(e.ctrlKey || e.metaKey) || e.altKey || e.shiftKey || !(e.code === "KeyB" || (e.key || "").toLowerCase() === "b")) return;
  if (e.target && e.target.isContentEditable) return;      // в редакторе с оформлением Ctrl+B — «жирный»
  e.preventDefault(); navToggle();
});

/* «Назад», как в браузере (идея №190, 13.11: «перешёл по ссылке — не хватает вернуться, откуда пришёл»): боковая кнопка
   мыши «назад» и Alt+← возвращают в прошлый раздел студии — без новой кнопки на экране. Раздел помнит своё состояние сам
   (страница не перерисовывается заново, если её не открывали по-новому). */
const NAV_BACK = [];
let navBacking = false;
document.addEventListener("click", (e) => {
  const b = e.target && e.target.closest && e.target.closest("nav button[data-p]");
  if (!b || navBacking) return;
  const cur = document.querySelector("section.cur"), from = cur && cur.id.replace(/^p-/, "");
  setTimeout(() => { const now = document.querySelector("section.cur"), to = now && now.id.replace(/^p-/, "");
    if (from && to && from !== to && NAV_BACK[NAV_BACK.length - 1] !== from) { NAV_BACK.push(from); if (NAV_BACK.length > 30) NAV_BACK.shift(); } }, 0);
}, true);
function navBack() {
  const p = NAV_BACK.pop(); if (!p) return false;
  const b = $(`nav button[data-p="${p}"]`); if (!b) return false;
  navBacking = true; try { b._direct = true; b.click(); b._direct = false; } finally { navBacking = false; }
  return true;
}
window.navBack = navBack;
document.addEventListener("mouseup", (e) => { if (e.button === 3 && navBack()) e.preventDefault(); });
document.addEventListener("keydown", (e) => {
  if (e.altKey && !e.ctrlKey && !e.shiftKey && !e.metaKey && e.key === "ArrowLeft") {
    const t = e.target; if (t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))) return;
    if (navBack()) e.preventDefault();
  }
});
