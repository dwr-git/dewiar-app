/* Планшет — раскладка как на компьютере (телефон 0.9.32; отчёты 657 и 658, планшет Huawei: «меню на планшете обрезанное,
   нет бизнес-инструментов», «думал, на планшете функционал будет как на компьютере»; владелец 11.11: «пользователи на
   планшетах ждут функционал, похожий на компьютер»).

   Широкий экран (от 760 px в ширину и 560 в высоту — планшет в любом положении, раскрытый складной телефон): слева
   постоянное меню разделов (#rail) — как левое меню студии на компьютере; разделы открываются не листом снизу, а панелью
   справа (у панели — крестик), разговор с облаком остаётся на виду. Очень широкий (от 1100 px) — панель рядом с
   разговором, он сужается; уже — панель поверх разговора. Телефон в руке — всё как было (листы снизу).

   Меню собирается из того же списка, что лист «Всё» (appsHtml в app.js): детский режим, «Для старших», выключенные
   разделы — те же правила. Плюс «Разговор», «Мой день», «Близкие», «Настройки». Точки «новое» — как у кнопок сверху. */
"use strict";
const TAB_MQ = matchMedia("(min-width: 760px) and (min-height: 560px)");
const TAB_WIDE = matchMedia("(min-width: 1100px)");
const TAB_IC = {
  talk: '<path d="M21 12a8.5 8.5 0 0 1-12.6 7.4L3 21l1.6-5.2A8.5 8.5 0 1 1 21 12z"/>',
  day: '<rect x="3.5" y="5" width="17" height="15.5" rx="2.5"/><path d="M3.5 10h17M8 3v4M16 3v4"/>',
  close: '<path d="M12 20.5s-7.5-4.6-7.5-10.1A4.2 4.2 0 0 1 12 7.8a4.2 4.2 0 0 1 7.5 2.6c0 5.5-7.5 10.1-7.5 10.1z"/>',
  set: '<circle cx="12" cy="12" r="3"/><path d="M12 2.8v2.4M12 18.8v2.4M2.8 12h2.4M18.8 12h2.4M5.5 5.5l1.7 1.7M16.8 16.8l1.7 1.7M5.5 18.5l1.7-1.7M16.8 7.2l1.7-1.7"/>'
};
let tabCur = "talk", tabSig = "";
const tbT = (k, p) => (typeof window.t === "function" ? window.t(k, p) : k);      // тексты — из словарей (tab.*, pci.*)

const tabOn = () => document.body.classList.contains("tab");
/* Пункты меню: [ключ, название, подпись] — из листа «Всё» (те же правила режимов), сверху свои. */
function tabItems() {
  const box = document.createElement("div"); box.innerHTML = appsHtml();
  const apps = [...box.querySelectorAll("[data-app]")].map(b => [b.dataset.app, (b.querySelector("b") || {}).textContent || "", (b.querySelector("small") || {}).textContent || ""]);
  const head = [["talk", tbT("tab.talk"), ""], ["day", tbT("tab.day"), ""]];
  const cb = $("#b-close"); if (cb && !cb.hidden) head.push(["close", tbT("tab.close"), ""]);
  return { head, apps, tail: [["set", tbT("tab.set"), ""]] };
}
function tabIcon(k) { return TAB_IC[k] || (typeof APPS_IC !== "undefined" && APPS_IC[k]) || TAB_IC.talk; }
function tabRender() {
  const rail = $("#rail"); if (!rail) return;
  const it = tabItems(), sig = JSON.stringify(it);
  if (sig !== tabSig) {
    tabSig = sig;
    const btn = ([k, n, sub]) => `<button class="rl-i" data-k="${k}" title="${esc(sub ? n + " — " + sub : n)}"><svg viewBox="0 0 24 24" aria-hidden="true">${tabIcon(k)}</svg><span>${esc(n)}</span><i class="dot"></i></button>`;
    rail.innerHTML = `<div class="rl-brand">Dewiar</div><div class="rl-g">${it.head.map(btn).join("")}</div><div class="rl-g rl-apps">${it.apps.map(btn).join("")}</div><div class="rl-g">${it.tail.map(btn).join("")}</div>`;
    rail.querySelectorAll("[data-k]").forEach(b => b.onclick = () => tabGo(b.dataset.k));
  }
  rail.querySelectorAll("[data-k]").forEach(b => { b.classList.toggle("on", b.dataset.k === tabCur); b.setAttribute("aria-current", b.dataset.k === tabCur ? "page" : "false"); });
  tabDots();
}
/* точки «новое» — как у кнопок сверху: непрочитанное в «Близких», новые видеоуроки */
function tabDots() {
  const rail = $("#rail"); if (!rail) return;
  const set = (k, on) => { const b = rail.querySelector(`[data-k="${k}"]`); if (b) b.classList.toggle("has", !!on); };
  set("close", ($("#b-close") || { classList: { contains: () => false } }).classList.contains("has"));
  set("lessons", ($("#b-apps") || { classList: { contains: () => false } }).classList.contains("has"));
}
function tabGo(k) {
  const open = !!$(".sheet.on");
  if (k === tabCur && open && k !== "talk") { closeSheets(); return; }     // второе нажатие — закрыть раздел
  closeSheets(); tabCur = k; tabRender();
  if (k === "talk") return;
  const top = { day: "#b-day", close: "#b-close", set: "#b-set" }[k];
  setTimeout(() => { if (top) { const b = $(top); if (b) b.click(); } else appOpen(k); }, 30);
}
/* какой пункт меню подсветить для открытого листа (открыли кнопкой сверху, голосом, из другого раздела) */
const TAB_OF = { day: "day", close: "close", set: "set", soul: "soul", work: "work", ideas: "ideas", safe: "safe", radio: "radio", play: "play",
  tricks: "tricks", lessons: "lessons", kids: "kids", kpin: "kids", news: "news", month: "month", senior: "senior", clients: "clients", pc: "pc",
  hist: "talk", persona: "talk", pedit: "talk", pcinfo: "pc" };
function tabX(s) {                                     // крестик у панели (на телефоне его нет — лист закрывают жестом вниз)
  if (!s || s.querySelector(":scope > .shx")) return;
  const x = document.createElement("button"); x.className = "shx"; x.type = "button"; x.setAttribute("aria-label", tbT("tab.x")); x.title = tbT("tab.x");
  x.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 7l10 10M17 7 7 17"/></svg>';
  x.onclick = () => closeSheets(); s.insertBefore(x, s.firstChild);
}
/* лист открылся или закрылся (кнопкой сверху, голосом, «Назад») — меню и разговор подстраиваются */
function tabSheets() {
  const s = $(".sheet.on"), open = !!s;
  document.body.classList.toggle("pane", open);
  let k = "talk";
  if (s) {
    tabX(s);
    const id = (s.id || "").replace(/^sh-/, "");
    k = id === "learn" ? (($("#ln-tabs .on") || {}).dataset || {}).t === "course" ? "course" : "qa" : TAB_OF[id] || tabCur;
  }
  if (k !== tabCur) { tabCur = k; if (tabOn()) tabRender(); }
}
function tabApply() {
  const on = TAB_MQ.matches;
  document.body.classList.toggle("tab", on);
  document.body.classList.toggle("tab-wide", on && TAB_WIDE.matches);
  if (on) { tabSig = ""; tabRender(); }
  tabSheets();
}
(function tabInit() {
  const rail = document.createElement("nav"); rail.id = "rail"; rail.setAttribute("aria-label", tbT("tab.rail"));
  document.body.insertBefore(rail, $("#top"));
  $$(".sheet").forEach(tabX);
  const mo = new MutationObserver(() => tabSheets());
  $$(".sheet").forEach(s => mo.observe(s, { attributes: true, attributeFilter: ["class"] }));
  const os = openSheet, cs = closeSheets;             // листы, что строятся позже («Мой месяц», «Для старших»…), — через них
  openSheet = function (id) { const r = os.apply(this, arguments); const el = $(id); if (el && !el._tabObs) { el._tabObs = 1; mo.observe(el, { attributes: true, attributeFilter: ["class"] }); } tabSheets(); return r; };
  closeSheets = function () { const r = cs.apply(this, arguments); tabSheets(); return r; };
  const mb = new MutationObserver(() => { if (tabOn()) tabRender(); });       // точки и «Близкие» появились/скрылись
  ["#b-close", "#b-apps"].forEach(id => { const b = $(id); if (b) mb.observe(b, { attributes: true, attributeFilter: ["class", "hidden"] }); });
  (TAB_MQ.addEventListener ? TAB_MQ.addEventListener("change", tabApply) : TAB_MQ.addListener(tabApply));
  (TAB_WIDE.addEventListener ? TAB_WIDE.addEventListener("change", tabApply) : TAB_WIDE.addListener(tabApply));
  tabApply();
})();

/* «Компьютер» — что делает Dewiar на компьютере и как получить это отсюда (отчёт 658: «думал, на планшете функционал будет
   идентичный компьютеру»). Приложение — помощник в кармане; большие дела делает компьютер, и их можно поручать отсюда. */
function openPcInfo() {
  let s = $("#sh-pcinfo");
  if (!s) {
    s = document.createElement("section"); s.className = "sheet tall"; s.id = "sh-pcinfo"; s.setAttribute("aria-labelledby", "pci-h");
    s.innerHTML = `<div class="grab"></div><h2 id="pci-h">${esc(tbT("pci.h"))}</h2><div id="pci-body"></div>`;
    document.body.appendChild(s);
  }
  const pcs = (typeof syncStatus !== "undefined" && syncStatus.devices || []).filter(x => x.pc && Date.now() / 1000 - (x.seen || 0) < 14 * 86400);
  const on = pcs.length > 0;
  const li = (xs) => `<ul class="pci-l">${xs.map(([b, t]) => `<li><b>${esc(b)}</b><small>${esc(t)}</small></li>`).join("")}</ul>`;
  const I = (k) => [tbT("pci.i." + k), tbT("pci.i." + k + "_d")];
  $("#pci-body").innerHTML = `<div class="card pci-st${on ? " ok" : ""}"><b>${esc(on ? tbT("pci.on", { name: pcs[0].name || tbT("pci.pc") }) : tbT("pci.off"))}</b>
      <small class="hint">${esc(tbT(on ? "pci.on_p" : "pci.off_p"))}</small>
      ${on ? "" : `<button class="btn p" id="pci-dl">${esc(tbT("pci.dl"))}</button>`}</div>
    <h3>${esc(tbT("pci.ask_h"))}</h3>
    <p class="pci-p">${esc(tbT("pci.ask_p"))}</p>
    <h3>${esc(tbT("pci.here_h"))}</h3>
    ${li(["clients", "day", "close", "work", "safe", "soul"].map(I))}
    <h3>${esc(tbT("pci.only_h"))}</h3>
    ${li(["tasks", "sitechat", "mailing", "sites", "hands", "council"].map(I))}`;
  const dl = $("#pci-dl"); if (dl) dl.onclick = () => D.openUrl((typeof annBase === "function" ? annBase() : "https://dewiar.pro/dwrapp/cloud.php").replace(/cloud\.php.*$/, "download.php"));
  openSheet("#sh-pcinfo");
}
