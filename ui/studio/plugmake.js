/* «Создать плагин» (Creator, 03.11 — владелец: «у DeepSeek Creator Mode: человек описывает идею, агент пишет плагин и
   встраивает в интерфейс; сделайте не хуже»). Раздел p-plgnew (скрытая кнопка nav data-p="plgnew"; в меню — «✦ Создать
   плагин» в группе «Плагины» и кнопка в каталоге «Плагины»). Префикс pmk.
   Поле «Опишите, что нужно» + примеры идей → ядро plugin_make {describe, code} (core/plugin_maker.py: текущая модель пишет
   plugin.json + ui.html, проверка, одна повторная попытка) → плагин в меню и сразу его страница (plugpage.js plpOpen).
   «Своя программа на компьютере» — выключено; включить можно только через вопрос с объяснением.
   «Готовые — одним нажатием» — шаблоны data/plugin_templates (plugin_make {template}) без модели.
   «Сделанные Лирой» — их страницы; править — словами там же («Изменить и версии»). */
const PMK = { busy: false, tpls: null, t0: 0, tick: 0 };
const pmkEsc = (t) => String(t ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const PMK_IDEAS = [
  ["📊", "Статистика разговоров", "Панель статистики наших разговоров: сколько сообщений по дням, в какие часы я пишу чаще, с кем из персонажей и о чём — красивыми графиками"],
  ["✅", "Трекер привычек", "Трекер привычек: список привычек, отметка за сегодня одним нажатием, серия дней подряд и календарь месяца"],
  ["📖", "Читалка статей", "Читалка: вставляю текст или ссылку — чистый текст крупным шрифтом, время чтения, и кнопка «Перескажи» для Лиры"],
  ["🎨", "Переключатель темы", "Переключатель темы студии: несколько готовых палитр и подбор цветов по словам вроде «тёплый закат»"],
  ["🍅", "Таймер помидора", "Таймер «помидор»: 25 минут работы и 5 отдыха, большой круглый таймер, счётчик помидоров за день"],
  ["💸", "Расходы по категориям", "Панель расходов: траты по категориям за месяц кольцевой диаграммой и по неделям столбцами, самые крупные покупки"],
  ["🛒", "Покупки по отделам", "Список покупок по отделам магазина: добавить, отметить купленное, очистить купленное"],
  ["🖼", "Доска вдохновения", "Доска вдохновения: цитаты и цвета карточками, перетаскивать, закреплять любимое"],
];
const PMK_PLACE = ["Например: панель, где видно, сколько я трачу на кафе по неделям, с целью на месяц",
  "Например: трекер воды — стаканы за день и неделю, крупные кнопки",
  "Например: страница с моими напоминаниями на неделю в виде календаря",
  "Например: доска задач «Сделать — В работе — Готово» с перетаскиванием"];

function pmkRender() {
  const box = $("#pmk"); if (!box) return;
  box.innerHTML = `<header class="pmk-hero">
      <div class="pmk-glow" aria-hidden="true"><i></i><i></i><i></i></div>
      <div class="pmk-top"><span class="pmk-kick">✦ Плагины своими словами</span>
        <h1>Создать плагин</h1>
        <p>Опишите, что нужно, — Лира напишет страницу и встроит её в студию: появится в меню слева, в группе «Плагины». Поменять потом можно так же — словами, а прежние версии сохранятся.</p></div>
      <div class="pmk-box">
        <label class="pmk-l" for="pmk-q">Опишите, что нужно</label>
        <textarea id="pmk-q" rows="4" maxlength="3000" placeholder="${pmkEsc(PMK_PLACE[Math.floor(Date.now() / 6e4) % PMK_PLACE.length])}"></textarea>
        <div class="pmk-ideas" role="list" aria-label="Идеи">${PMK_IDEAS.map(([ic, t, d]) => `<button class="pmk-idea" role="listitem" data-d="${pmkEsc(d)}" title="${pmkEsc(d)}"><i aria-hidden="true">${ic}</i>${pmkEsc(t)}</button>`).join("")}</div>
        <div class="pmk-bar">
          <label class="pmk-code" title="По умолчанию плагин — только страница: без сети и без доступа к файлам">
            <span class="tg"><input type="checkbox" id="pmk-code"><i></i></span>
            <span><b>Своя программа на компьютере</b><small>Обычно не нужна. Только если плагину надо работать с файлами или интернетом.</small></span></label>
          ${pmkWho("pmk-who")}
          <button class="btn primary pmk-go" id="pmk-go"><span>✦</span> Создать плагин</button>
        </div>
        <div class="pmk-run" id="pmk-run" hidden aria-live="polite">
          <div class="pmk-sk" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i><i></i></div>
          <div class="pmk-rt"><b id="pmk-rt">Лира пишет плагин…</b><small>Обычно 20–60 секунд. Можно перейти в другой раздел — готовый плагин появится в меню сам.</small></div>
        </div>
        <div class="pmk-err" id="pmk-err" hidden role="alert"></div>
      </div>
    </header>
    <div class="pmk-cat" id="pmk-cat">
      <div><b>Готовые плагины Dewiar</b><small id="pmk-cat-names">Художник, Переводчик, Путешествия, Рекрутер, Тендеры и другие — уже собраны и проверены, ставятся одним нажатием.</small></div>
      <button class="btn" id="pmk-cat-go" type="button">🧩 Все плагины</button>
    </div>
    <div class="pmk-sec">
      <h2>Заготовки для своего плагина <small>Лира поставит сразу, без ожидания; потом их можно менять словами</small></h2>
      <div class="pmk-tpls" id="pmk-tpls"><p class="plp-loading"><i class="plp-spin"></i> Загружаю…</p></div>
    </div>
    <div class="pmk-sec" id="pmk-mine-sec">
      <h2>Сделанные Лирой <small>откройте — и меняйте словами: «сделай крупнее», «добавь график»</small></h2>
      <div class="pmk-mine" id="pmk-mine"></div>
    </div>
    <details class="pmk-how"><summary>Что умеет плагин и что ему нельзя</summary>
      <ul>
        <li><b>Страница в студии.</b> Плагин живёт в изолированном окне: у него нет интернета и доступа к студии, файлам и паролям.</li>
        <li><b>Своё хранилище.</b> Что вы отметили в плагине, сохраняется только для него.</li>
        <li><b>Данные Лиры — с вашего разрешения.</b> Заметки, напоминания, расходы, статистика разговоров или их текст — плагин спросит при первом обращении, а передумать можно на его странице, во вкладке «Доступ».</li>
        <li><b>Оформление.</b> Плагин-тема может перекрасить студию — по вашему нажатию; «Оформление» → «Сбросить тему» вернёт как было.</li>
        <li><b>Версии.</b> Каждая правка словами — новая версия; хранятся 10 последних, «Вернуть как было» — в один шаг.</li>
      </ul></details>`;
  const q = $("#pmk-q"), go = $("#pmk-go");
  $$("#pmk .pmk-idea").forEach(b => b.onclick = () => { q.value = b.dataset.d; q.focus(); q.setSelectionRange(q.value.length, q.value.length);
    $$("#pmk .pmk-idea").forEach(x => x.classList.toggle("on", x === b)); });
  q.onkeydown = (e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); go.click(); } };
  q.oninput = () => $$("#pmk .pmk-idea").forEach(x => x.classList.toggle("on", x.dataset.d === q.value));
  $("#pmk-code").onchange = async (e) => {
    if (!e.target.checked) return;
    const yes = typeof ask === "function" && await ask("Плагин сможет запускать свою программу на этом компьютере (Python): читать и писать файлы в своей папке, считать, ходить в интернет.\n\nВключайте, только если это правда нужно и вы доверяете описанию. Разрешить?", { ok: "Разрешить", danger: true });
    e.target.checked = !!yes;
  };
  go.onclick = pmkMake;
  pmkTpls(); pmkMine();
  if (PMK.busy) pmkBusy(true);
}
function pmkBusy(on) {
  const run = $("#pmk-run"), go = $("#pmk-go"); if (!run) return;
  run.hidden = !on; go.disabled = on; $("#pmk-q").readOnly = on;
  clearInterval(PMK.tick);
  if (on) {
    const say = () => { const s = Math.round((Date.now() - PMK.t0) / 1000), el = $("#pmk-rt"); if (!el) return;
      el.textContent = (s < 4 ? "Лира читает описание…" : s < 50 ? "Лира пишет страницу плагина…" : "Почти готово — проверяю и встраиваю…") + ` ${s} с`; };
    say(); PMK.tick = setInterval(say, 500);
  }
}
/* «Кто делает» (04.11, пользователь: «у Лиры модель слабее, а Патрик для таких дел настроен — не смог поручить ему»):
   плагин пишет модель выбранного персонажа (студия → «Персонажи» → «Мозг»); по умолчанию — тот, кто сейчас говорит. */
function pmkWho(id) {
  const list = (typeof personas !== "undefined" ? personas : []).filter(p => p && p.id && p.installed !== false);
  if (list.length < 2) return "";
  const profs = (S.llm || {}).profiles || {}, cur = S.persona;
  const brain = (p) => { try { return typeof brainOf === "function" && typeof brainName === "function" ? brainName(profs[brainOf(p.id)], brainOf(p.id)) : ""; } catch (e) { return ""; } };
  return `<label class="pmk-who" for="${id}"><span>Кто делает</span><select id="${id}">${list.map(p =>
    `<option value="${pmkEsc(p.id)}"${p.id === cur ? " selected" : ""}>${pmkEsc(p.name)}${brain(p) ? " — " + pmkEsc(brain(p)) : ""}</option>`).join("")}</select></label>`;
}
function pmkWhoVal(id) { const el = document.getElementById(id); return el ? el.value : ""; }
function pmkErr(msg) { const e = $("#pmk-err"); if (!e) return; e.hidden = !msg; e.innerHTML = msg ? `<b>Не получилось.</b> ${pmkEsc(msg)}` : ""; }
async function pmkMake() {
  const q = $("#pmk-q"), text = q.value.trim();
  pmkErr("");
  if (text.length < 6) { q.focus(); pmkErr("Опишите хотя бы одной фразой: что должно быть на странице и зачем."); return; }
  if (PMK.busy) return;
  PMK.busy = true; PMK.t0 = Date.now(); pmkBusy(true);
  let r;
  try { r = await core.call("plugin_make", { describe: text, code: !!($("#pmk-code") || {}).checked, by: pmkWhoVal("pmk-who") }); }
  catch (e) { PMK.busy = false; pmkBusy(false); pmkErr(e.message); return; }
  PMK.busy = false; pmkBusy(false);
  if ($("#pmk-q")) $("#pmk-q").value = "";
  pmkDone(r);
}
function pmkDone(r) {
  if (r.plugins && typeof plgSet === "function") plgSet({ plugins: r.plugins });
  toast(`Готово: «${r.name}» — в меню «Плагины»`);
  if (window.plpOpen) plpOpen(r.id, "page");
}
async function pmkTpls() {
  const box = $("#pmk-tpls"); if (!box) return;
  try { PMK.tpls = (await core.call("plugin_templates")).items || []; } catch (e) { box.innerHTML = `<p class="hint">${pmkEsc(e.message)}</p>`; return; }
  box.innerHTML = PMK.tpls.map(t => `<article class="pmk-tpl" style="--pc:${pmkEsc(t.color || "#8B8CF7")}" data-t="${pmkEsc(t.id)}">
      <div class="pmk-art pmk-art-${pmkEsc(t.id)}" aria-hidden="true">${pmkArt(t.id)}</div>
      <div class="pmk-tt"><i class="pmk-ic" aria-hidden="true">${pmkEsc(t.icon)}</i><b>${pmkEsc(t.name)}</b></div>
      <p>${pmkEsc(t.description || t.tagline)}</p>
      <div class="pmk-tb">${(t.data || []).length ? `<span class="pmk-need" title="Спросит разрешение при первом открытии">🔒 спросит: ${pmkEsc(t.data.map(s => typeof PLP_SCOPES !== "undefined" && PLP_SCOPES[s] ? PLP_SCOPES[s][0] : s).join(", "))}</span>` : t.theme ? `<span class="pmk-need">🎨 меняет цвета студии</span>` : `<span class="pmk-need">без доступа к данным</span>`}
        ${t.installed.length ? `<button class="btn small" data-open="${pmkEsc(t.installed[0])}">Открыть</button>` : `<button class="btn small primary" data-add="${pmkEsc(t.id)}">Добавить</button>`}</div></article>`).join("") || `<p class="hint">Готовых пока нет.</p>`;
  $$("#pmk-tpls [data-open]").forEach(b => b.onclick = () => window.plpOpen && plpOpen(b.dataset.open, "page"));
  $$("#pmk-tpls [data-add]").forEach(b => b.onclick = async () => {
    b.disabled = true; b.textContent = "Добавляю…";
    try { pmkDone(await core.call("plugin_make", { template: b.dataset.add })); }
    catch (e) { toast(e.message); b.disabled = false; b.textContent = "Добавить"; }
  });
}
function pmkArt(id) {
  if (id === "chat-stats") return `<svg viewBox="0 0 220 96" preserveAspectRatio="none"><g>${[22, 38, 30, 54, 46, 70, 58, 80, 64, 88, 72, 60].map((h, i) => `<rect x="${8 + i * 17.5}" y="${92 - h}" width="11" height="${h}" rx="3"/>`).join("")}</g><path d="M8 44 C40 30 70 52 100 34 S170 18 212 26" fill="none"/></svg>`;
  if (id === "reader") return `<div class="pmk-page"><b></b><i></i><i></i><i class="s"></i><i></i><i class="s2"></i></div>`;
  if (id === "theme") return `<div class="pmk-pal">${["#FF8A65", "#F6C177", "#9CCFD8", "#C4A7E7", "#31748F"].map(c => `<i style="background:${c}"></i>`).join("")}</div>`;
  return "";
}
function pmkMine() {
  const box = $("#pmk-mine"), sec = $("#pmk-mine-sec"); if (!box) return;
  const list = ((typeof PLP !== "undefined" && PLP.cat) || []).filter(p => p.made);
  sec.hidden = !list.length;
  box.innerHTML = list.map(p => `<button class="pmk-my" data-id="${pmkEsc(p.id)}" style="--pc:${pmkEsc(p.color)}"><i class="pmk-ic" aria-hidden="true">${pmkEsc(p.icon)}</i>
    <span><b>${pmkEsc(p.name)}</b><small>${pmkEsc(p.tagline || "")}</small></span><em>Открыть →</em></button>`).join("");
  $$("#pmk-mine .pmk-my").forEach(b => b.onclick = () => window.plpOpen && plpOpen(b.dataset.id, "page"));
}
window.pmkOpen = () => { const b = $('nav button[data-p="plgnew"]'); if (b) b.click(); };

/* меню: «✦ Создать плагин» в группе «Плагины» и кнопка в каталоге */
(() => {
  const n = $("#nav-plg-new"); if (n) n.onclick = window.pmkOpen;
  // 04.11 (владелец: «у нас же есть готовые плагины — переводчик, путешествия, художник, — где они?»): каталог готовых —
  // «Все плагины» в группе «Плагины» и полосой на странице «Создать плагин»
  const allGo = () => { const b = $('nav button[data-p="skills"]'); if (b) b.click(); };
  const na = $("#nav-plg-all"); if (na) na.onclick = allGo;
  document.addEventListener("click", (e) => { if (e.target.closest && e.target.closest("#pmk-cat-go")) allGo(); });
  const c = $("#plg-new"); if (c) c.onclick = window.pmkOpen;
  document.addEventListener("click", (e) => { const b = e.target.closest && e.target.closest("nav button[data-p]");
    if (b) setTimeout(() => { const nn = $("#nav-plg-new"); if (nn) nn.classList.toggle("cur", !!$("#p-plgnew.cur")); }, 0); }, true);
})();
secLazy("plgnew", pmkRender);
document.addEventListener("studio-sec", (e) => { if (e.detail === "plgnew" && PMK.tpls && !PMK.busy) { pmkTpls(); pmkMine(); } });
core.on("plugin_made", () => { if ($("#pmk-mine")) setTimeout(() => { pmkMine(); if (PMK.tpls) pmkTpls(); }, 300); });
