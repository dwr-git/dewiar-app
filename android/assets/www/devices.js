/* «Устройства» на телефоне и в веб-версии (0.56; письмо пользователя 28.10: «хрен найдёшь, где эта синхронизация…
   если на мобилке как источник — «Синхронизация — сгенерировать код», если мобилку надо настроить — «ввести код или
   прочитать QR»… «Синхронизировать сейчас»… визуальное состояние подключённых юнитов»). Вкладка «Устройства» в
   настройках: это устройство (имя, синхронизация, «Синхронизировать сейчас», шифрование), «Подключить ещё устройство» —
   6 цифр и QR на 10 минут (подключилось — видно сразу), «Ввести код» и «Сканировать код», список всех устройств — вид,
   версия, «на связи сейчас / был … назад». Код не отнимает свой мозг: своя модель остаётся главной, ключ Dewiar — для
   синхронизации (S.sync.key) и запасом. Код от входа аккаунтом — вход тем же аккаунтом без пароля.
   Сайт: ?p=/pair/new, /pair/claim, /sync/devices, /sync/forget (cloud.php). Ядро app.js зовёт: devHtml, devBind, devMyName,
   devClaimFlow (сканер и ссылка dewiar://pair). */
"use strict";
let DEVS = null, devCode = null, devTick = 0, devPoll = 0;
const DEV_ONLINE = 180;
const DEV_APP = { pc: "Компьютер", phone: "Телефон", web: "В браузере", cloud: "Облако Dewiar" };
const DEV_IC = {
  home: '<path d="M3.5 11 12 4l8.5 7"/><path d="M5.5 9.5V20h13V9.5"/><path d="M9.2 14.6a4 4 0 0 1 5.6 0M10.8 16.6a1.6 1.6 0 0 1 2.4 0"/>',
  pc: '<rect x="3" y="4.5" width="18" height="12" rx="2"/><path d="M9 20h6M12 16.5V20"/>',
  phone: '<rect x="7" y="2.8" width="10" height="18.4" rx="2.4"/><path d="M11 18h2"/>',
  web: '<circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17M12 3.5c2.6 2.6 2.6 14.4 0 17M12 3.5c-2.6 2.6-2.6 14.4 0 17"/>',
  cloud: '<path d="M7.5 18.5h9a4 4 0 0 0 .4-8 5.5 5.5 0 0 0-10.6 1.4A3.3 3.3 0 0 0 7.5 18.5z"/>',
};
function devMyName() {
  if (S.sync && S.sync.name) return S.sync.name;
  try { const i = JSON.parse(D.info() || "{}"); return D.web ? "Браузер" + (/iPhone|iPad/.test(navigator.userAgent) ? " на iPhone" : /Mac/.test(navigator.userAgent) ? " на Mac" : "") : (i.device || "Телефон"); }
  catch (e) { return "Телефон"; }
}
const devAgo = (ts) => {
  const s = Math.max(0, Date.now() / 1000 - (ts || 0));
  if (!ts) return "ещё не был на связи";
  if (s < DEV_ONLINE) return "на связи сейчас";
  if (s < 3600) return `был ${Math.round(s / 60)} мин назад`;
  if (s < 86400) return `был ${Math.round(s / 3600)} ч назад`;
  if (s < 2 * 86400) return "был вчера";
  return "был " + new Date(ts * 1000).toLocaleDateString("ru-RU", { day: "numeric", month: "long" });
};
const devOn = (d) => d.me || Date.now() / 1000 - (d.seen || 0) < DEV_ONLINE;
const devOwnBrain = () => !!S.llm.base_url && !S.llm.trial && !S.llm.cloud;
function devHdr(c) { const h = { Authorization: "Bearer " + c.token, "Content-Type": "application/json" }; if (c.link && c.link !== c.token) h["X-Sync-Link"] = c.link; return h; }
async function devCall(method, path, body) {
  const c = syncCred(); if (!c) throw new Error("здесь ещё нет входа в Dewiar");
  const st = syncSt() || {}, r = await http(method, c.base + "?p=" + path + "&device=" + encodeURIComponent(st.device || ""), { headers: devHdr(c), body: body == null ? null : body, timeout: 20000 });
  let d = {}; try { d = JSON.parse(r.body || "{}"); } catch (e) { }
  if (r.status >= 400) throw new Error((d.error && d.error.message) || ("облако ответило " + r.status));
  return d;
}
async function devLoad() {
  if (!syncChan()) { DEVS = null; return; }
  if (syncChan().home) { DEVS = syncStatus.all || DEVS || []; return; }      // по Wi-Fi: список — из последнего обмена с компьютером
  try { DEVS = (await devCall("GET", "/sync/devices")).devices || []; } catch (e) { DEVS = DEVS || (syncStatus.all || null); }
}

function devHtml() {
  const c = syncChan(), s = syncStatus, t = s.at ? new Date(s.at) : null, list = DEVS || syncStatus.all || [];
  const me = { name: devMyName(), app: D.web ? "web" : "phone" };
  const others = list.filter(d => !d.me), on = others.filter(devOn).length;
  const stTxt = !c ? "Синхронизации нет: здесь ещё нет входа в Dewiar — введите код с другого устройства."
    : !S.sync.on ? "Синхронизация выключена." : s.ok === false ? "Не синхронизировалось: " + s.error : t ? `Синхронизировано в ${pad(t.getHours())}:${pad(t.getMinutes())}` : "Первая синхронизация — в течение минуты.";
  const rows = (list.length ? list : [Object.assign({ me: true, seen: 0, ver: "" }, me)]).map(d => {
    const app = d.app || "phone", live = devOn(d);
    return `<div class="dvr${live ? " on" : ""}"><span class="dvi"><svg viewBox="0 0 24 24">${DEV_IC[app] || DEV_IC.phone}</svg></span><div class="dvt"><b>${esc(d.me ? me.name : (d.name || DEV_APP[app]))}${d.me ? '<em>это устройство</em>' : ""}</b>`
      + `<small>${DEV_APP[app] || "Устройство"}${d.ver ? " · Dewiar " + esc(d.ver) : ""} · <i></i>${d.me ? "здесь" : devAgo(d.seen)}</small></div>`
      + (d.me || app === "cloud" || (c && c.home) ? "" : `<button class="lnk" data-dforget="${esc(d.id)}">Убрать</button>`) + `</div>`;
  }).join("");
  return `<div class="card dvme"><small class="hint" style="margin:0">Это устройство</small>
      <div class="row2"><b class="dvname" id="dv-name">${esc(me.name)}</b><button class="btn" id="dv-ren">Имя</button></div>
      <div class="res ${!c || !S.sync.on ? "" : s.ok === false ? "bad" : s.ok ? "ok" : ""}" id="dv-st" style="margin:6px 0 0">${esc(stTxt)}</div>
      ${c ? `<button class="btn p w" id="dv-now" style="margin-top:10px" ${S.sync.on ? "" : "disabled"}>Синхронизировать сейчас</button>
      <div class="sw" style="margin-top:10px"><div>Синхронизировать<small class="hint" style="display:block;margin:2px 0 0">${esc(c.via)}</small></div><label class="tg"><input type="checkbox" id="sy-on" ${S.sync.on ? "checked" : ""}><i></i></label></div>
      ${c.home ? `<p class="hint" style="margin:8px 0 0">Обмен идёт только по домашней сети и зашифрован ключом с экрана компьютера.</p>`
        : `<div class="sw" style="margin-top:6px"><div>Шифровать на устройстве<small class="hint" style="display:block;margin:2px 0 0">облако видит только шифротекст</small></div><label class="tg"><input type="checkbox" id="sy-e2e" ${S.sync.e2e && syncKeyGet() ? "checked" : ""} ${S.sync.on ? "" : "disabled"}><i></i></label></div>`}` : ""}</div>
    ${devWays(c)}
    <h3>Все устройства${others.length ? ` · на связи: ${on + 1} из ${others.length + 1}` : ""}</h3><div class="card dvlist" id="dv-list">${rows}</div>
    <p class="hint">Синхронизация идёт сама — раз в минуту и сразу после правок: напоминания, заметки и блокнот, расходы, память «Обо мне», душа, свои персонажи, дневник и задачи.</p>`;
}

/* «Как связать устройства» (0.59, владелец 28.10: «всё в одном месте… чётко, просто и понятно»): два способа —
   через dewiar.pro (везде) или дома по Wi-Fi (без интернета). Вкладка по умолчанию — «Дома по Wi-Fi», если
   телефон уже так связан, иначе dewiar.pro. Браузер (https) к компьютеру по http не ходит — там только dewiar.pro. */
let devWay = "";
function devGiveHtml(c) {
  return `<h3>Подключить ещё устройство</h3><div class="card" id="dv-give">
      ${c && c.home ? `<p class="hint" style="margin:0">Ещё один телефон — отсканируйте им код с компьютера: «Устройства» → «Дома по Wi-Fi».</p>`
      : c ? `<p class="hint" style="margin:0 0 10px">Компьютер или другой телефон станет той же Лирой: общая память, заметки, дела.</p>
        <div class="dvcode" id="dv-code" hidden><div class="dvqr" id="dv-qr"></div><b class="dvdig" id="dv-dig"></b><p class="hint" id="dv-left" style="margin:4px 0 0"></p>
        <p class="hint" style="margin:6px 0 0">На том устройстве: «Устройства» → «Ввести код». Телефон может навести сканер на квадрат.</p></div>
        <button class="btn p w" id="dv-give-go">Показать код</button><div class="res" id="dv-give-res"></div>`
      : `<p class="hint" style="margin:0">Здесь ещё нет входа в Dewiar. Если Dewiar уже работает на компьютере или другом телефоне — введите его код ниже. Если это первое устройство — подключите мозг во вкладке «Мозг».</p>`}</div>`;
}
function devWays(c) {
  if (D.web) return devGiveHtml(c) + devCloudMore(c);
  const way = devWay || (homeOn() ? "home" : "cloud");
  const tab = (id, ic, t, sub) => `<button role="tab" data-way="${id}" class="${way === id ? "on" : ""}" aria-selected="${way === id}"><svg viewBox="0 0 24 24">${ic}</svg><span><b>${t}</b><small>${sub}</small></span></button>`;
  return `<h3>Как связать устройства</h3><div class="dvways" role="tablist" aria-label="Способ синхронизации">
      ${tab("cloud", DEV_IC.cloud, "Через dewiar.pro", "везде, где есть интернет")}${tab("home", DEV_IC.home, "Дома по Wi-Fi", "без интернета")}</div>
    <p class="hint dvwnote">${way === "home" ? "Телефон связывается прямо с компьютером, когда вы дома в одной сети. В интернет ничего не уходит, обмен зашифрован ключом из кода. Вне дома правки копятся здесь и уходят, когда вернётесь."
      : "Телефоны и компьютеры связываются через ваш вход в Dewiar — синхронизация идёт в дороге, на работе и дома."}</p>`
    + (way === "home" ? devHomeHtml(c) : c && c.home ? `<div class="card"><p class="hint" style="margin:0">Сейчас телефон связан с «${esc((S.sync.home || {}).n || "компьютером")}» по Wi-Fi. Перейти на dewiar.pro — во вкладке «Дома по Wi-Fi»: «Отключить», потом подключитесь кодом здесь.</p></div>`
      : devGiveHtml(c) + devCloudMore(c));
}
function devCloudMore(c) {                          // «Ввести код» и «Мозги» — облачное; по Wi-Fi не нужны
  return `<h3>Ввести код</h3><div class="card" id="dv-take"><p class="hint" style="margin:0 0 10px">Dewiar уже есть на другом устройстве? Там: «Устройства» → «Подключить ещё устройство». ${devOwnBrain() ? "Ваша модель здесь останется главной." : ""}</p>
      <div class="row2"><input id="dv-in" class="dvin" inputmode="numeric" autocomplete="one-time-code" maxlength="7" placeholder="123 456" aria-label="Код из 6 цифр" style="flex:1;min-width:0;font-size:20px;letter-spacing:.12em;text-align:center"><button class="btn p" id="dv-take-go">Подключить</button></div>
      ${window.DewiarCodes && window.ZXing ? `<button class="btn w" id="dv-scan" style="margin-top:8px">Сканировать код с экрана</button>` : ""}<div class="res" id="dv-take-res"></div></div>
    <h3>Мозги с другого устройства</h3><div class="card"><p class="hint" style="margin:0 0 10px">Настроили модель на компьютере — возьмите её сюда: адрес, модель и ключ придут зашифрованными, только вашим устройствам. Своя модель останется; новые — в «Мозг» → «Прежние мозги».</p>
      <button class="btn w" id="dv-brains" ${c && !c.home ? "" : "disabled"}>Взять мозги</button><div class="res ${devBrainsGot.length ? "ok" : ""}" id="dv-brains-res">${esc(devBrainsGot.map(g => `С «${g.from}»: ${g.names.join(", ")}`).join(" · "))}</div></div>`;
}
/* «Компьютер дома — по Wi-Fi» (0.59): подключён — имя компьютера и «Отключить»; нет — «Сканировать код компьютера» */
function devHomeHtml(c) {
  const h = S.sync && S.sync.home;
  if (D.web) return "";                                   // браузер (https) не может ходить на компьютер по http — только приложение
  if (c && c.home) return `<div class="card dvhome on"><small class="hint" style="margin:0">Компьютер дома</small><div class="row2"><div><b>${esc(h.n || "Компьютер")}</b>
      <small class="hint" style="display:block;margin:2px 0 0">напрямую по Wi-Fi, без dewiar.pro</small></div>
      <button class="btn" id="dv-home-off">Отключить</button></div></div>`;
  return `<div class="card dvhome"><p class="hint" style="margin:0 0 10px">На компьютере: студия → «Устройства» → «Дома по Wi-Fi» → «Показать код для телефона».
      Телефон и компьютер — в одном Wi-Fi.</p>
      ${window.DewiarCodes && window.ZXing ? `<button class="btn w" id="dv-home-scan">Сканировать код компьютера</button>` : ""}</div>`;
}

function devBind() {
  const g = (id) => document.getElementById(id);
  if (g("dv-home-scan")) g("dv-home-scan").onclick = () => scanCode();
  $$(".dvways [data-way]").forEach(b => b.onclick = () => { devWay = b.dataset.way; renderSettings(); });
  if (g("dv-home-off")) g("dv-home-off").onclick = () => {
    if (!confirm(`Отключить синхронизацию с «${(S.sync.home || {}).n || "компьютером"}»? Всё, что уже здесь, останется на телефоне.`)) return;
    homeForget(); renderSettings(); toast("Отключено — данные остались на телефоне");
  };
  if (!DEVS && syncChan() && !devBind.loading) { devBind.loading = true; devLoad().finally(() => { devBind.loading = false; if (setTab === "devices" && $("#sh-set").classList.contains("on")) renderSettings(); }); }
  if (g("dv-ren")) g("dv-ren").onclick = () => {
    const n = prompt("Имя этого устройства — его увидят другие («Мой телефон», «Планшет»). Пусто — имя телефона.", (S.sync && S.sync.name) || "");
    if (n == null) return;
    S.sync = Object.assign({}, S.sync, { name: n.trim().slice(0, 40) }); saveS(); syncSoon(); renderSettings(); toast(n.trim() ? "Имя сохранено — другие увидят его после синхронизации" : "Имя — как у телефона");
  };
  if (g("dv-now")) g("dv-now").onclick = async () => { g("dv-now").disabled = true; g("dv-st").textContent = "Синхронизирую…"; await syncRun(true).catch(() => { }); await devLoad(); renderSettings(); };
  if (g("dv-give-go")) g("dv-give-go").onclick = () => devGive();
  if (g("sy-on")) g("sy-on").onchange = () => { S.sync.on = g("sy-on").checked; saveS(); if (S.sync.on) syncSoon(); renderSettings(); };
  if (g("sy-e2e")) g("sy-e2e").onchange = () => {
    const on = g("sy-e2e").checked;
    if (!on && !confirm("Выключить шифрование на этом устройстве? Свои изменения оно снова будет отправлять открытыми. На других устройствах выключите отдельно.")) { g("sy-e2e").checked = true; return; }
    e2eEnable(on); renderSettings(); };
  if (devCode && g("dv-code")) devShowCode();
  const inp = g("dv-in");
  if (inp) {
    inp.oninput = () => { const v = inp.value.replace(/\D/g, "").slice(0, 6); inp.value = v.length > 3 ? v.slice(0, 3) + " " + v.slice(3) : v; };
    inp.onkeydown = (e) => { if (e.key === "Enter") g("dv-take-go").click(); };
  }
  if (g("dv-take-go")) g("dv-take-go").onclick = async () => {
    const code = inp.value.replace(/\D/g, ""), r = g("dv-take-res");
    if (code.length !== 6) { r.className = "res bad"; r.textContent = "Нужны 6 цифр — они на экране другого устройства."; inp.focus(); return; }
    g("dv-take-go").disabled = true; r.className = "res"; r.textContent = "Подключаю…";
    try { const d = await devClaim(code); r.className = "res ok"; r.textContent = devClaimText(d); setTimeout(() => { if (setTab === "devices") renderSettings(); }, 2500); }
    catch (e) { r.className = "res bad"; r.textContent = netErr(e.message || e); } finally { g("dv-take-go").disabled = false; }
  };
  if (g("dv-scan")) g("dv-scan").onclick = () => scanCode();
  if (g("dv-brains")) g("dv-brains").onclick = async () => {
    const r = g("dv-brains-res"); g("dv-brains").disabled = true; r.className = "res"; r.textContent = "Спрашиваю ваши устройства…";
    try { const ok = await devBrainsPull(); r.textContent = ok ? "Жду ответа — устройство с мозгами должно быть включено (до 10 минут)." : "Других ваших устройств пока не видно — подключите их кодом выше."; }
    catch (e) { r.className = "res bad"; r.textContent = netErr(e.message || e); } finally { g("dv-brains").disabled = false; }
    setTimeout(() => clPoll().catch(() => { }), 4000);
  };
  $$("#dv-list [data-dforget]").forEach(b => b.onclick = async () => {
    const d = (DEVS || []).find(x => x.id === b.dataset.dforget);
    if (!confirm(`Убрать «${d ? d.name : "устройство"}» из списка? Если оно снова выйдет на связь — появится снова. Чтобы отключить насовсем, выйдите из Dewiar на нём.`)) return;
    try { DEVS = (await devCall("POST", "/sync/forget", { id: b.dataset.dforget })).devices || []; renderSettings(); toast("Убрано из списка"); } catch (e) { toast(e.message, 3500); }
  });
  clearInterval(devPoll);                                  // пока вкладка открыта — свежий список (с кодом — каждые 5 с: видно, что подключилось)
  let n = 0;
  devPoll = setInterval(async () => {
    if (setTab !== "devices" || !$("#sh-set").classList.contains("on")) { clearInterval(devPoll); return; }
    if (!devCode && ++n % 6) return;                       // без кода — раз в 30 с; код показали позже — частота сразу 5 с
    await devLoad();
    devFresh();
    if (document.activeElement !== inp) renderSettings();
  }, 5000);
}
/* код показан — подключилось ли новое устройство (зовут опрос вкладки и синхронизация, syncRun) */
function devFresh() {
  if (!devCode || !devCode.known) return false;
  const was = new Set(devCode.known), fresh = (DEVS || []).filter(d => !was.has(d.id) && !d.me);
  if (!fresh.length) return false;
  devCode = null; clearInterval(devTick);
  toast(`Подключилось: ${fresh.map(d => d.name || DEV_APP[d.app]).join(", ")} — теперь это одна Лира`, 4000); say("Готово, подключилось!");
  if (setTab === "devices" && $("#sh-set").classList.contains("on")) renderSettings();
  return true;
}
async function devGive() {
  const r = $("#dv-give-res"), c = syncCred(); if (!c) return;
  r.className = "res"; r.textContent = "получаю код…";
  try {
    const x = await http("POST", c.base + "?p=/pair/new", { headers: devHdr(c), body: {}, timeout: 40000 });
    let d = {}; try { d = JSON.parse(x.body || "{}"); } catch (e) { }
    if (x.status >= 400) throw new Error((d.error && d.error.message) || ("облако ответило " + x.status));
    if (!d.code) { r.textContent = d.text || "Код не выдан."; return; }
    devCode = { code: d.code, link: d.link || "dewiar://pair?c=" + d.code, account: !!d.account, until: Date.now() + (d.expires || 600) * 1000,
      known: (DEVS || []).map(x => x.id) };              // кто был до кода: новое — то, чего тут нет (список обновляет и синхронизация)
    r.textContent = ""; devShowCode(); devBind();
  } catch (e) { r.className = "res bad"; r.textContent = netErr(e.message || e); }
}
function devShowCode() {
  const box = $("#dv-code"); if (!box || !devCode) return;
  const seal = window.DewiarCodes ? DewiarCodes.seal(devCode.link) : "";
  $("#dv-qr").innerHTML = seal || (typeof qrcode === "function" ? clQr(devCode.link) : ""); $("#dv-qr").classList.toggle("seal", !!seal);
  $("#dv-dig").textContent = devCode.code.slice(0, 3) + " " + devCode.code.slice(3);
  box.hidden = false; $("#dv-give-go").textContent = "Новый код";
  const tick = () => { if (!devCode || !$("#dv-left")) { clearInterval(devTick); return; } const s = Math.round((devCode.until - Date.now()) / 1000);
    if (s <= 0) { devCode = null; clearInterval(devTick); box.hidden = true; $("#dv-give-go").textContent = "Показать код"; $("#dv-give-res").textContent = "Код устарел — покажите новый."; return; }
    $("#dv-left").textContent = `Действует ещё ${Math.floor(s / 60)}:${pad(s % 60)}${devCode.account ? " · войдёт тем же аккаунтом" : ""}`; };
  clearInterval(devTick); devTick = setInterval(tick, 1000); tick();
}

/* код с другого устройства -> это устройство — та же Лира. Своя модель — главной; ключ — для синхронизации и запасом. */
async function devClaim(code) {
  const r = await http("POST", CLOUD_URL.split("?")[0] + "?p=/pair/claim", { headers: { "Content-Type": "application/json" }, body: { code: String(code).replace(/\D/g, "") }, timeout: 15000 });
  let d = {}; try { d = JSON.parse(r.body || "{}"); } catch (e) { }
  if (r.status >= 400 || !d.key) throw new Error((d.error && d.error.message) || ("сервер ответил " + r.status));
  const own = devOwnBrain();
  if (d.account) {                                       // вход тем же аккаунтом — без пароля, токен пришёл по одноразовому коду
    S.account = Object.assign({}, DEF.account, { server: SITE, token: d.key, login: "", user: {}, services: {}, problem: "", since: Date.now() }); saveS();
    try { const x = await http("GET", SITE + "/dwrapp/login.php", { headers: siteHeaders(), timeout: 15000 });
      if (x.status === 200) { const u = JSON.parse(x.body || "{}"); S.account.user = u.user || {}; S.account.login = (u.user && u.user.login) || ""; S.account.services = u.services || {}; } } catch (e) { }
    trialOff(); saveS();
    try { await cloudConnect(d.key, siteUrl((S.account.services || {}).cloud || "dwrapp/cloud.php"), { account: true, activate: !own }); } catch (e) { plog("warn", "облако по аккаунту: " + e.message); }
  } else {
    S.sync = Object.assign({}, S.sync, { key: d.key, on: true }); saveS();   // синхронизация — этим ключом, даже если думает своя модель
    if (!own) await cloudConnect(d.key);
  }
  saveS(); applyPersona();
  const st = syncSt(); if (st) { st.rev = 0; prefSet("sync", JSON.stringify(st)); }   // всё с начала: память, заметки, дела — сюда
  DEVS = null; setTimeout(() => syncRun(true).catch(() => { }), 300);
  plog("info", "🔗 подключено к своему Dewiar кодом с другого устройства" + (d.account ? " (аккаунт)" : ""));
  return { account: !!d.account, brain_kept: own };
}
const devClaimText = (d) => (d.account ? "Готово — вход тем же аккаунтом. " : "Готово. ") + "Это устройство — та же Лира: память, заметки и дела придут в течение минуты." + (d.brain_kept ? " Ваша модель осталась главной." : "");
/* сканер (печать или QR со ссылкой …?pair=) и ссылка dewiar://pair?c= */
async function devClaimFlow(link) {
  const m = /[?&](?:pair|c)=(\d{6})/.exec(String(link || "")); if (!m) { showBot("Это не код подключения устройства.", "err"); return; }
  if (kidsOn()) { showBot("В детском режиме устройства подключает взрослый.", "err"); return; }
  if (!confirm("Подключить этот телефон к вашему Dewiar с другого устройства? Память, заметки и дела станут общими." + (devOwnBrain() ? " Ваша модель останется главной." : ""))) return;
  try { const d = await devClaim(m[1]); showBot(devClaimText(d)); say("Готово!"); }
  catch (e) { showBot("Не подключилось: " + netErr(e.message || e), "err"); }
}

/* задача названному компьютеру («Лира, на рабочем компьютере подготовь презентацию», письмо 28.10): свои компьютеры —
   из последнего обмена (на связи — синхронизировался за 3 минуты); не на связи — спросить: подождать или в облаке */
function devComputers() {
  return (DEVS || syncStatus.all || []).filter(d => d.app === "pc").map(d => ({ id: d.id, name: d.name || "Компьютер", on: Date.now() / 1000 - (d.seen || 0) < DEV_ONLINE, seen: d.seen || 0 }));
}
const devComputersText = () => { const c = devComputers(); return c.length > 1 || (c.length && c[0].name) ? " Компьютеры пользователя: " + c.map(x => `«${x.name}» (${x.on ? "на связи" : "не на связи"})`).join(", ") + "." : ""; };
function devFindComputer(name) {
  const norm = (t) => String(t || "").toLowerCase().replace(/ё/g, "е");
  const stop = new Set(["на", "в", "мой", "моем", "компьютер", "компьютере", "комп", "компе", "пк", "ноуте"]);
  const q = (norm(name).match(/[а-яa-z0-9]+/g) || []).filter(w => !stop.has(w)), comps = devComputers();
  const exact = comps.find(c => norm(c.name).trim() === norm(name).trim()); if (exact) return exact;
  let best = null, score = 0;
  for (const c of comps) { const ws = norm(c.name).match(/[а-яa-z0-9]+/g) || [];
    const sc = q.filter(w => ws.some(x => x.startsWith(w.slice(0, 4)) || w.startsWith(x.slice(0, 4)))).length;
    if (sc > score) { best = c; score = sc; } }
  return best;
}
function devTaskOn(a) {
  const c = devFindComputer(a.on), all = devComputers();
  if (!c) throw new Error(`не нашла компьютер «${a.on}» среди ваших: ${all.map(x => `«${x.name}»`).join(", ") || "компьютеров пока нет — подключите их в «Устройствах»"}`);
  const title = a.title || String(a.goal || "").slice(0, 60), goal = a.goal || a.title || "";
  if (!c.on && a.if_off !== "wait" && a.if_off !== "cloud") {
    const h = c.seen ? Math.round((Date.now() / 1000 - c.seen) / 3600) : 0;
    return `Компьютер «${c.name}» сейчас не на связи${h ? ` (был ${h} ч назад)` : ""}. Спроси коротко: сделать, когда он включится, или сейчас в облаке Dewiar? Потом снова start_task с тем же on и if_off: wait или cloud.`;
  }
  if (!c.on && a.if_off === "cloud") { taskToPc(title, goal); return `Задача «${title}» ушла в облако Dewiar — «${c.name}» не на связи. Ход и итог — в «Мой день» → «Сделанное». Скажи коротко, что взялась.`; }
  taskToPc(title, goal, c.id);
  return `Задача «${title}» передана компьютеру «${c.name}»` + (c.on ? " — он уже берётся." : " — он возьмётся, как только включится.") + " Результата ЕЩЁ НЕТ — скажи одной фразой, что передала.";
}

/* «Взять мозги с другого устройства» (письмо 28.10: «на компе настроил — другие надо легко подключить, свои мозги-модели»):
   просьба своим устройствам конвертом own {want: ["brains"]}; ответ {brains: {from, profiles}} — только им, зашифрованно.
   Своя модель остаётся; пришедшие — в «Прежние мозги» (вернуть одной кнопкой); мозга не было — первая станет главной. */
let devBrainsUntil = 0, devBrainsGot = [];
async function devOwnSend(body) {
  if (!syncCred() || !DC()) return false;
  const k = clKeys(); if (!clLoad().me.pid || Date.now() - (CLS.hello || 0) > 600000) await clHello();
  const t = {}; ((CLS.me || {}).devs || []).forEach(d => { if (d.pub && d.dev && d.dev !== k.dev) t[d.dev] = DC().b64d(d.pub); });
  if (!Object.keys(t).length) return false;
  t[k.dev] = DC().b64d(k.pub);
  await clReq("POST", "/close/self", { env: DC().encryptFor(Object.assign({ ts: Date.now() }, body), DC().b64d(k.priv), k.dev, t) });
  return true;
}
function devBrainsShare() {
  const local = (b) => /\/\/(?:localhost|127\.|0\.0\.0\.0)/.test(b || "");
  const all = [S.llm].concat(Array.isArray(S.llmSaved) ? S.llmSaved : []).filter(l => l && l.base_url && !l.cloud && !l.trial && !l.forgot && !local(l.base_url));
  const seen = new Set(), out = [];
  for (const l of all) { const id = l.base_url.replace(/\/+$/, "") + "|" + (l.model || ""); if (seen.has(id)) continue; seen.add(id);
    out.push({ name: l.name || "", kind: l.kind || "openai", base_url: l.base_url, api_key: l.api_key || "", model: l.model || "", title: l.title || "" }); }
  return out.length ? { from: devMyName(), at: Date.now(), profiles: out.slice(0, 12) } : null;
}
async function devBrainsPull() { devBrainsUntil = Date.now() + 600000; devBrainsGot = []; return devOwnSend({ want: ["brains"], from: devMyName() }); }
function devBrainsTake(b) {
  if (!b || !Array.isArray(b.profiles) || Date.now() > devBrainsUntil) return;
  const have = new Set([S.llm].concat(S.llmSaved || []).filter(Boolean).map(l => String(l.base_url || "").replace(/\/+$/, "") + "|" + (l.model || "")));
  const added = [];
  for (const pr of b.profiles.slice(0, 12)) {
    if (!pr || !/^https?:\/\//.test(pr.base_url || "")) continue;
    const id = String(pr.base_url).replace(/\/+$/, "") + "|" + (pr.model || ""); if (have.has(id)) continue; have.add(id);
    const l = Object.assign({}, DEF.llm, { kind: pr.kind || "openai", name: pr.name || pr.model || "Модель", base_url: pr.base_url, api_key: pr.api_key || "", model: pr.model || "", title: pr.title || "" });
    if (!S.llm.base_url || S.llm.trial) S.llm = l;                    // мозга не было — сразу думает пришедшим
    else S.llmSaved = [l].concat(S.llmSaved || []).slice(0, 8);
    added.push(l.name);
  }
  if (!added.length) return;
  saveS(); applyPersona(); devBrainsGot.push({ from: b.from || "", names: added });
  plog("info", "🧠 мозги со своего устройства «" + (b.from || "?") + "»: " + added.join(", "));
  toast(`С «${b.from || "другого устройства"}»: ${added.join(", ")}`, 4000);
  if (setTab === "devices" && $("#sh-set").classList.contains("on")) renderSettings();
}
function devBrainsOwn(body) {                                        // зовёт ownApply (app.js)
  if (body && Array.isArray(body.want) && body.want.includes("brains")) { const sh = devBrainsShare(); if (sh) devOwnSend({ brains: sh }).catch(() => { }); }
  if (body && body.brains) devBrainsTake(body.brains);
}
