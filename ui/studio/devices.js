/* Студия, «Устройства» (0.56; письмо пользователя 28.10: «хрен найдёшь, где эта синхронизация… почему нельзя вынести
   синхронизацию отдельно… на компе настроил — другие компы надо легко подключить… «Синхронизировать сейчас»…
   визуальное состояние подключённых юнитов»). Одна страница: карта — Лира в середине, вокруг все ваши устройства (на
   связи — яркая линия); это устройство — имя, синхронизация, «Синхронизировать сейчас»; «Подключить ещё устройство» —
   6 цифр и QR на 10 минут (подключилось — видно сразу); «Ввести код»; список всех устройств — вид, версия, когда было на
   связи, «Убрать из списка». Ядро: devices_get {fresh}, device_rename {name}, device_forget {id}, pair_new, pair_claim
   {code}, sync_now, sync_set {on}, sync_e2e {on}. */
let DV = null, DV_CODE = null, DV_TICK = 0, DV_POLL = 0;
const DV_ONLINE = 180;                                   // на связи — синхронизировался за последние 3 минуты
const DV_APP = { pc: "Компьютер", phone: "Телефон", web: "В браузере", cloud: "Облако Dewiar" };
const DV_IC = {
  pc: '<rect x="3" y="4.5" width="18" height="12" rx="2"/><path d="M9 20h6M12 16.5V20"/>',
  phone: '<rect x="7" y="2.8" width="10" height="18.4" rx="2.4"/><path d="M11 18h2"/>',
  web: '<circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17M12 3.5c2.6 2.6 2.6 14.4 0 17M12 3.5c-2.6 2.6-2.6 14.4 0 17"/>',
  cloud: '<path d="M7.5 18.5h9a4 4 0 0 0 .4-8 5.5 5.5 0 0 0-10.6 1.4A3.3 3.3 0 0 0 7.5 18.5z"/>',
};
const dvAgo = (ts) => {
  const s = Math.max(0, Date.now() / 1000 - (ts || 0));
  if (!ts) return "ещё не был на связи";
  if (s < DV_ONLINE) return "на связи сейчас";
  if (s < 3600) return `был ${Math.round(s / 60)} мин назад`;
  if (s < 86400) return `был ${Math.round(s / 3600)} ч назад`;
  if (s < 2 * 86400) return "был вчера";
  if (s < 30 * 86400) return `был ${Math.round(s / 86400)} ${typeof plural === "function" ? plural(Math.round(s / 86400), "день", "дня", "дней") : "дн."} назад`;
  return "был " + new Date(ts * 1000).toLocaleDateString("ru-RU", { day: "numeric", month: "long" });
};
const dvOn = (d) => d.me || Date.now() / 1000 - (d.seen || 0) < DV_ONLINE;

async function loadMyDevices(fresh) {
  try { DV = await core.call("devices_get", { fresh: fresh !== false }); } catch (e) { toast(e.message, 3500); return; }
  dvRender();
  clearInterval(DV_POLL);
  DV_POLL = setInterval(() => { if (!$("#p-devices").classList.contains("cur")) { clearInterval(DV_POLL); return; } dvRefresh(); }, DV_CODE ? 5000 : 30000);
}
window.loadMyDevices = loadMyDevices;
async function dvRefresh() {
  // кто был до кода (список обновляет не только этот опрос — сравниваем с ним, а не с прошлым опросом)
  const was = new Set(DV_CODE && DV_CODE.known ? DV_CODE.known : ((DV && DV.devices) || []).map(d => d.id));
  try { DV = await core.call("devices_get", { fresh: true }); } catch (e) { return; }
  const fresh = (DV.devices || []).filter(d => !was.has(d.id) && !d.me);
  if (fresh.length && DV_CODE) {                         // по коду подключилось новое устройство — код больше не нужен
    toast(`Подключилось: ${fresh.map(d => d.name || DV_APP[d.app]).join(", ")} — теперь это одна Лира`, 4000);
    dvCodeHide();
  }
  dvRender();
}

function dvRender() {
  const d = DV; if (!d || !$("#p-devices")) return;
  const st = d.sync || {}, devs = d.devices || [];
  $("#dv-myname").textContent = d.me.name || "Этот компьютер";
  const t = st.at ? new Date(st.at * 1000).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" }) : "";
  $("#dv-sync-st").className = "dv-st " + (!st.available || !st.on ? "" : st.ok === false ? "bad" : st.ok ? "ok" : "");
  $("#dv-sync-st").textContent = !st.available ? "Синхронизации нет: здесь ещё нет входа в Dewiar — введите код с другого устройства или подключите Dewiar в «Мозге»."
    : !st.on ? "Синхронизация выключена." : st.ok === false ? "Не синхронизировалось: " + st.error : t ? `Синхронизировано в ${t}` : "Первая синхронизация — в течение минуты.";
  $("#dv-now").disabled = false; $("#dv-now").classList.toggle("ghost", !st.available || !st.on);   // не серая кнопка без объяснения: нажали — скажем, что сделать
  $("#dv-sync-on").checked = !!st.on; $("#dv-sync-on").disabled = !st.available;
  $("#dv-via").textContent = st.available ? (d.mode === "account" ? `по аккаунту${d.login ? " " + d.login : ""} на dewiar.pro` : "по ключу Dewiar") : "нужен вход в Dewiar";
  $("#dv-e2e").checked = !!(st.e2e || {}).on; $("#dv-e2e").disabled = !st.available || !st.on;
  // подключить ещё: есть вход — код; нет — подсказка
  $("#dv-give-go").disabled = false; $("#dv-give-go").classList.toggle("ghost", !d.can_pair);
  $("#dv-give-hint").textContent = d.can_pair ? "Покажите код другому компьютеру или телефону — он станет той же Лирой: общая память, заметки и дела."
    : "Здесь ещё нет входа в Dewiar. Если Dewiar уже работает на другом устройстве — введите его код справа. Если это первое устройство — подключите Dewiar в «Мозге».";
  const others = devs.filter(x => !x.me), on = others.filter(dvOn).length;
  $("#dv-count").textContent = others.length ? `ещё ${others.length} · на связи сейчас: ${on}` : "пока только это";
  $("#dv-list").innerHTML = devs.map(x => {
    const live = dvOn(x), app = x.app || "pc";
    return `<li class="${live ? "on" : ""}${x.me ? " me" : ""}"><span class="dv-ic ${escH(app)}"><svg viewBox="0 0 24 24">${DV_IC[app] || DV_IC.pc}</svg></span>`
      + `<div class="dv-row"><b>${escH(x.name || DV_APP[app])}${x.me ? '<em class="dv-chip">это устройство</em>' : ""}</b>`
      + `<small>${DV_APP[app] || "Устройство"}${x.home ? " · по Wi-Fi" : ""}${x.ver ? " · Dewiar " + escH(x.ver) : ""} · <span class="dv-dot"></span>${x.me ? "здесь" : dvAgo(x.seen)}</small></div>`
      + (x.me || app === "cloud" || x.home ? "" : `<button class="btn small" data-forget="${escH(x.id)}" type="button" title="Убрать из списка — выйдет на связь снова, появится снова">Убрать</button>`) + `</li>`;
  }).join("") || `<li class="dv-empty">Пока только это устройство. Подключите ещё одно кодом — и оно появится здесь.</li>`;
  $$("#dv-list [data-forget]").forEach(b => b.onclick = async () => {
    const x = devs.find(y => y.id === b.dataset.forget);
    if (!await ask(`Убрать «${x ? x.name : "устройство"}» из списка? Если оно снова выйдет на связь, то снова появится. Чтобы отключить насовсем — выйдите из Dewiar на нём.`, { ok: "Убрать" })) return;
    try { DV = await core.call("device_forget", { id: b.dataset.forget }); dvRender(); toast("Убрано из списка"); } catch (e) { toast(e.message, 3500); }
  });
  dvMap(devs);
  if (d.home) dvHome(d.home);
  dvWay(DV_WAY || ((d.home && d.home.on) || !d.can_pair ? "home" : "cloud"));
  const h = d.home || {};
  if (!st.available && h.on) {                             // входа в Dewiar нет, но телефон по Wi-Fi — синхронизация идёт
    const ht = h.at ? new Date(h.at * 1000).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" }) : "";
    $("#dv-sync-st").className = "dv-st " + (h.ok === false ? "bad" : h.ok ? "ok" : "");
    $("#dv-sync-st").textContent = h.ok === false ? "По Wi-Fi не синхронизировалось: " + h.error : (h.phones || []).length ? `Телефон по Wi-Fi${ht ? " · обмен в " + ht : ""}` : "Дома по Wi-Fi: включено — покажите телефону код ниже.";
    $("#dv-via").textContent = "через dewiar.pro — нужен вход; по Wi-Fi — включено ниже";
  }
}

/* карта: Лира в середине, устройства по кругу (0.66, владелец: «схему — немножко красивее и аккуратнее»; обводки он не
   любит): устройства — плитки с цветом своего вида (компьютер, телефон, браузер, облако) и белым значком, без рамок;
   на связи — точка-огонёк и плавная линия к Лире, по которой бегут искры; давно не было — бледная плитка и пунктир.
   Под плиткой — имя и состояние. Лира — светящийся шар с мягкими кругами вокруг. */
const DV_TONE = { pc: ["#9a8cff", "#6a55e6"], phone: ["#5fdcb6", "#1fa585"], web: ["#7fc8ff", "#4a86ee"], cloud: ["#a8c0ff", "#7b8ff5"] };
function dvMap(devs) {
  const W = 560, H = 390, cx = W / 2, cy = H / 2 + 2, n = Math.max(devs.length, 1), RX = 210, RY = 128, T = 50;
  const all = typeof personas !== "undefined" && Array.isArray(personas) ? personas : [];
  const who = all.find(p => p.id === (typeof active !== "undefined" && active ? active : S && S.persona)) || null;
  const nm = ((who && who.name) || "Лира").slice(0, 9);
  let lines = "", nodes = "", defs = "";
  devs.forEach((d, i) => {
    const a = -Math.PI / 2 + (2 * Math.PI * i) / n + (n === 2 ? Math.PI / 2 : 0);
    const x = cx + RX * Math.cos(a), y = cy + RY * Math.sin(a), on = dvOn(d), app = d.app || "pc", tone = DV_TONE[app] || DV_TONE.pc;
    // линия — мягкой дугой от края облика Лиры: середина чуть отведена в сторону, к Лире подходит не по прямой
    const L = Math.hypot(x - cx, y - cy) || 1, sx = cx + (x - cx) / L * 58, sy = cy + (y - cy) / L * 58;
    const mx = (sx + x) / 2 + (y - cy) * 0.1, my = (sy + y) / 2 - (x - cx) * 0.1;
    defs += `<linearGradient id="dvg${i}" gradientUnits="userSpaceOnUse" x1="${cx}" y1="${cy}" x2="${x}" y2="${y}"><stop offset="0" stop-color="#8b7cff"/><stop offset="1" stop-color="${tone[0]}"/></linearGradient>`
      + `<linearGradient id="dvt${i}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="${tone[0]}"/><stop offset="1" stop-color="${tone[1]}"/></linearGradient>`;
    const path = `M${sx.toFixed(1)} ${sy.toFixed(1)} Q${mx.toFixed(1)} ${my.toFixed(1)} ${x.toFixed(1)} ${y.toFixed(1)}`;
    lines += `<path d="${path}" class="dv-ln${on ? " on" : ""}" ${on ? `style="stroke:url(#dvg${i})"` : ""}/>` + (on ? `<path d="${path}" class="dv-spark" style="animation-delay:${(-i * 0.7).toFixed(1)}s"/>` : "");
    const label = (d.name || DV_APP[app]).slice(0, 18), sub = d.me ? "это устройство" : on ? "на связи" : dvAgo(d.seen);
    const below = y >= cy - 4, ly = below ? y + T / 2 + 18 : y - T / 2 - 22;
    nodes += `<g class="dv-node${on ? " on" : ""}${d.me ? " me" : ""}" transform="translate(${(x - T / 2).toFixed(1)} ${(y - T / 2).toFixed(1)})">`
      + (d.me ? `<circle cx="${T / 2}" cy="${T / 2 + 4}" r="${T * 0.62}" class="dv-halo" fill="${tone[0]}" filter="url(#dvblur)"/>` : "")
      + `<rect width="${T}" height="${T}" rx="16" fill="url(#dvt${i})" class="dv-tile"/>`
      + `<svg x="${(T - 24) / 2}" y="${(T - 24) / 2}" width="24" height="24" viewBox="0 0 24 24">${DV_IC[app] || DV_IC.pc}</svg>`
      + (on ? `<circle cx="${T - 4}" cy="4" r="7" class="dv-live-h"/><circle cx="${T - 4}" cy="4" r="4.2" class="dv-live"/>` : "") + `</g>`
      + `<text x="${x.toFixed(1)}" y="${ly.toFixed(1)}" class="dv-lbl">${escH(label)}</text>`
      + `<text x="${x.toFixed(1)}" y="${(ly + 14).toFixed(1)}" class="dv-sub${on ? " on" : ""}">${escH(sub)}</text>`;
  });
  $("#dv-map").innerHTML = `<div class="dv-mapin"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Ваши устройства вокруг ${escH(nm)}"><defs>`
    + `<radialGradient id="dvorb" cx="38%" cy="32%"><stop offset="0" stop-color="#c9c2ff"/><stop offset=".55" stop-color="#7d6df2"/><stop offset="1" stop-color="#4a3bc4"/></radialGradient>`
    + `<filter id="dvblur" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="9"/></filter><radialGradient id="dvhalo"><stop offset=".55" stop-color="#8b7cff" stop-opacity=".18"/><stop offset="1" stop-color="#8b7cff" stop-opacity="0"/></radialGradient>${defs}</defs>`
    + `<circle cx="${cx}" cy="${cy}" r="100" fill="url(#dvhalo)"/><circle cx="${cx}" cy="${cy}" r="66" class="dv-ring"/>`
    + lines + `<rect x="${cx - 32}" y="${cy + 52}" width="64" height="21" rx="10.5" class="dv-orbp"/><text x="${cx}" y="${cy + 66.5}" class="dv-orbt">${escH(nm)}</text>`
    + nodes + `</svg><canvas class="dv-ent" style="left:${(cx / W * 100).toFixed(2)}%;top:${(cy / H * 100).toFixed(2)}%;width:${(112 / W * 100).toFixed(2)}%" aria-hidden="true"></canvas></div>`;
  // в середине — сам облик персонажа (тот же, что в виджете: стиль, цвет, своё фото), а не шар с надписью (владелец 28.10)
  if (DV_ENT) { try { DV_ENT.destroy(); } catch (e) { } DV_ENT = null; }
  const cv = $("#dv-map .dv-ent");
  if (cv && typeof DewiarEntity === "function") {
    const p = who || {};
    try { DV_ENT = new DewiarEntity(cv, { style: p.avatar_url && p.style !== "aura" ? "photo" : (p.style || "nexus"), color: p.color || "#8B7CFF",
      image: p.avatar_url || null, live: p.live || "", ring: false, soft: !!p.kids }); DV_ENT.set({ state: "idle", level: 0 }); } catch (e) { DV_ENT = null; }
  }
}
let DV_ENT = null;

/* «Подключить ещё устройство»: код, QR (печать Dewiar или обычный), обратный отсчёт; подключилось — сразу видно */
function dvCodeHide() { clearInterval(DV_TICK); DV_CODE = null; $("#dv-code").hidden = true; $("#dv-give-go").textContent = "Показать код"; loadMyDevices(false); }
$("#dv-give-go").onclick = async (ev) => {
  const r = $("#dv-give-res");
  if (DV && !DV.can_pair) { r.className = "res bad"; r.textContent = "Сначала нужен вход в Dewiar: введите код с другого устройства справа или подключите Dewiar в «Мозге»."; return; }
  ev.target.disabled = true; r.className = "res"; r.textContent = "";
  try {
    const d = await core.call("pair_new");
    if (!d.code) { r.className = "res bad"; r.textContent = d.text || "Код не выдан."; return; }
    DV_CODE = { code: d.code, until: Date.now() + (d.expires || 600) * 1000, known: ((DV && DV.devices) || []).map(x => x.id) };
    $("#dv-digits").textContent = d.code.slice(0, 3) + " " + d.code.slice(3);
    const link = d.link || ("dewiar://pair?c=" + d.code), seal = window.DewiarCodes ? DewiarCodes.seal(link) : "";
    $("#dv-qr").innerHTML = seal || (typeof qrSvg === "function" ? qrSvg(link) : ""); $("#dv-qr").classList.toggle("seal", !!seal);
    $("#dv-code").hidden = false; ev.target.textContent = "Новый код";
    const tick = () => { const s = Math.round((DV_CODE.until - Date.now()) / 1000); if (s <= 0) { dvCodeHide(); r.className = "res"; r.textContent = "Код устарел — покажите новый."; return; }
      $("#dv-left").textContent = `Действует ещё ${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}${d.account ? " · новое устройство войдёт тем же аккаунтом" : ""}.`; };
    clearInterval(DV_TICK); DV_TICK = setInterval(tick, 1000); tick();
    loadMyDevices(false);                                 // чаще спрашивать, не подключилось ли
  } catch (e) { r.className = "res bad"; r.textContent = e.message; } finally { ev.target.disabled = false; }
};
$("#dv-codein").oninput = (e) => { const v = e.target.value.replace(/\D/g, "").slice(0, 6); e.target.value = v.length > 3 ? v.slice(0, 3) + " " + v.slice(3) : v; };
$("#dv-codein").onkeydown = (e) => { if (e.key === "Enter") $("#dv-take-go").click(); };
$("#dv-take-go").onclick = async (ev) => {
  const code = $("#dv-codein").value.replace(/\D/g, ""), r = $("#dv-take-res");
  if (code.length !== 6) { r.className = "res bad"; r.textContent = "Нужны 6 цифр — они на экране другого устройства."; $("#dv-codein").focus(); return; }
  ev.target.disabled = true; r.className = "res"; r.textContent = "Подключаю…";
  try {
    const d = await core.call("pair_claim", { code });
    $("#dv-codein").value = "";
    r.className = "res ok"; r.textContent = (d.account ? "Готово — вход тем же аккаунтом. " : "Готово. ") + "Это устройство — та же Лира: память, заметки и дела придут в течение минуты."
      + (d.brain_kept ? " Ваша модель осталась главной." : " Отвечают модели Dewiar.");
    setTimeout(() => loadMyDevices(true), 2500);
  } catch (e) { r.className = "res bad"; r.textContent = e.message; } finally { ev.target.disabled = false; }
};
$("#dv-rename").onclick = async () => {
  const n = await askText("Имя этого устройства — его увидят другие («Рабочий», «Домашний», «Ноутбук»)", (DV && DV.me.custom && DV.me.name) || "", { ok: "Сохранить" });
  if (n == null) return;
  try { DV = await core.call("device_rename", { name: n }); dvRender(); toast(n.trim() ? "Имя сохранено — другие увидят его после синхронизации" : "Имя — как у компьютера в системе"); } catch (e) { toast(e.message); }
};
$("#dv-now").onclick = async (ev) => {
  const st = (DV && DV.sync) || {};
  if (!st.available || !st.on) { toast(!st.available ? "Синхронизации пока нет: нужен вход в Dewiar — введите код с другого устройства" : "Синхронизация выключена — включите переключатель рядом", 4000); return; }
  ev.target.disabled = true; $("#dv-sync-st").textContent = "Синхронизирую…";
  try { await core.call("sync_now"); } catch (e) { toast(e.message); }
  await loadMyDevices(true);
};
$("#dv-sync-on").onchange = async (e) => { try { await core.call("sync_set", { on: e.target.checked }); } catch (x) { toast(x.message); } loadMyDevices(false); };
$("#dv-e2e").onchange = async (ev) => {
  const on = ev.target.checked;
  if (!on && !await ask("Выключить шифрование на этом компьютере? Свои изменения он снова будет отправлять открытыми. На других устройствах выключите отдельно.")) { ev.target.checked = true; return; }
  try { await core.call("sync_e2e", { on }); } catch (x) { toast(x.message); } loadMyDevices(false);
};

/* «Телефон по Wi-Fi — без dewiar.pro» (0.59, core/homehub.py): переключатель — компьютер слушает домашнюю сеть; «Показать
   код» — QR со ссылкой dewiar://home (адреса, номер ключа, ключ) на 10 минут; подключился — телефон в списке («Отключить»
   — ключ удалён). Ядро: home_get, home_set {on}, home_pair, home_forget {tid}. */
let DV_HOME = null, DV_HTICK = 0, DV_HPOLL = 0;
function dvHome(h) {
  if (!h || !$("#dv-home")) return;
  DV_HOME = h;
  $("#dv-home-on").checked = !!h.on; $("#dv-home").classList.toggle("on", !!h.on);
  const t = h.at ? new Date(h.at * 1000).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" }) : "";
  const r = $("#dv-home-res");
  if (!r.dataset.keep) { r.className = "res" + (h.on && h.ok === false ? " bad" : "");
    r.textContent = !h.on ? "" : !h.running ? "Не получилось слушать сеть — " + (h.error || "порт занят") : !h.ips.length ? "Этот компьютер сейчас не в домашней сети."
      : h.ok === false ? "Не синхронизировалось: " + h.error
      : `Включено${t ? " · обмен в " + t : ""} · адрес компьютера в сети: ${h.ips[0]}${h.win && !(h.phones || []).length ? ". Если Windows спросит про доступ к сети — разрешите для частной сети." : ""}`; }
  $("#dv-home-list").innerHTML = (h.phones || []).map(p => { const on = Date.now() / 1000 - (p.seen || 0) < DV_ONLINE;
    return `<li class="${on ? "on" : ""}"><span class="dv-ic phone"><svg viewBox="0 0 24 24">${DV_IC.phone}</svg></span><div class="dv-row"><b>${escH(p.name || "Телефон")}</b>`
      + `<small><span class="dv-dot"></span>${on ? "на связи сейчас" : dvAgo(p.seen)}</small></div><button class="btn small" type="button" data-hforget="${escH(p.tid)}">Отключить</button></li>`; }).join("");
  $$("#dv-home-list [data-hforget]").forEach(b => b.onclick = async () => {
    const p = (h.phones || []).find(x => x.tid === b.dataset.hforget);
    if (!await ask(`Отключить «${p ? p.name : "телефон"}»? Он больше не сможет синхронизироваться с этим компьютером, пока не отсканирует код заново. Его данные останутся у него.`, { ok: "Отключить" })) return;
    try { dvHome(await core.call("home_forget", { tid: b.dataset.hforget })); toast("Телефон отключён"); } catch (e) { toast(e.message); }
  });
}
/* способ связи: вкладки «Через dewiar.pro» / «Дома по Wi-Fi»; по умолчанию — включённый (Wi-Fi включён или входа в Dewiar нет) */
let DV_WAY = null;
try { DV_WAY = localStorage.getItem("dv-way"); } catch (e) { }
function dvWay(w, user) {
  if (!w) return;
  if (user) { DV_WAY = w; try { localStorage.setItem("dv-way", w); } catch (e) { } }
  $$("#dv-ways [data-way]").forEach(b => b.setAttribute("aria-selected", String(b.dataset.way === w)));
  $$("#dv-ways [data-for]").forEach(el => { el.hidden = el.dataset.for !== w; });
}
$$("#dv-ways [data-way]").forEach(b => b.onclick = () => dvWay(b.dataset.way, true));
function dvHomeCodeHide() { clearInterval(DV_HTICK); clearInterval(DV_HPOLL); $("#dv-home-code").hidden = true; $("#dv-home-go").textContent = "Показать код для телефона"; }
$("#dv-home-on").onchange = async (e) => {
  const on = e.target.checked;
  if (!on && !await ask("Выключить синхронизацию с телефоном по Wi-Fi? Телефоны перестанут получать изменения с этого компьютера. Данные останутся и там, и здесь.", { ok: "Выключить" })) { e.target.checked = true; return; }
  try { dvHome(await core.call("home_set", { on })); if (!on) dvHomeCodeHide(); } catch (x) { toast(x.message, 4000); e.target.checked = !on; }
};
$("#dv-home-go").onclick = async (ev) => {
  const r = $("#dv-home-res"); ev.target.disabled = true;
  try {
    const h = await core.call("home_pair"); dvHome(h);
    const p = h.pair, until = p.until * 1000, known = new Set((h.phones || []).map(x => x.tid + ":" + x.seen));
    $("#dv-home-qr").innerHTML = typeof qrSvg === "function" ? qrSvg(p.link) : "";
    $("#dv-home-code").hidden = false; ev.target.textContent = "Новый код";
    const tick = () => { const s = Math.round((until - Date.now()) / 1000); if (s <= 0) { dvHomeCodeHide(); r.textContent = "Код устарел — покажите новый."; return; }
      $("#dv-home-left").textContent = `Код действует ещё ${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}.`; };
    clearInterval(DV_HTICK); DV_HTICK = setInterval(tick, 1000); tick();
    clearInterval(DV_HPOLL);
    DV_HPOLL = setInterval(async () => {                 // подключился — видно сразу
      if (!$("#p-devices").classList.contains("cur")) { clearInterval(DV_HPOLL); return; }
      let x; try { x = await core.call("home_get"); } catch (e) { return; }
      const fresh = (x.phones || []).find(q => q.tid === p.tid);
      dvHome(x);
      if (fresh) { dvHomeCodeHide(); toast(`Подключился «${fresh.name || "телефон"}» — теперь это одна Лира`, 4000); loadMyDevices(false); }
    }, 3000);
  } catch (e) { r.className = "res bad"; r.textContent = e.message; } finally { ev.target.disabled = false; }
};

/* «Мозги с другого устройства»: просьба своим устройствам (конвертом, сквозное шифрование); кто на связи — пришлёт свои
   модели с ключами; приходят 10 минут — список «добавлено» обновляется событием «brains» */
let DV_BR = 0;
$("#dv-brains-go").onclick = async (ev) => {
  const r = $("#dv-brains-res"); ev.target.disabled = true; r.className = "res"; r.textContent = "Спрашиваю ваши устройства…";
  try {
    const d = await core.call("brains_pull");
    if (!d.sent) { r.className = "res bad"; r.textContent = "Других ваших устройств с Dewiar пока не видно — подключите их кодом выше, и пусть одно из них будет включено."; ev.target.disabled = false; return; }
    r.textContent = "Жду ответа — устройство с мозгами должно быть включено (до 10 минут)…";
    clearInterval(DV_BR); let n = 0;
    DV_BR = setInterval(async () => { if (++n > 120) { clearInterval(DV_BR); ev.target.disabled = false; if (!r.classList.contains("ok")) r.textContent = "Ответа не было — включите устройство с мозгами и попробуйте ещё раз."; return; }
      try { dvBrains(await core.call("brains_status")); } catch (e) { } }, 5000);
  } catch (e) { r.className = "res bad"; r.textContent = e.message; ev.target.disabled = false; }
};
function dvBrains(st) {
  const r = $("#dv-brains-res"); if (!r || !st || !(st.got || []).length) return;
  r.className = "res ok"; r.textContent = st.got.map(g => `С «${g.from}»: ${g.names.join(", ")}`).join(" · ") + ". Выбрать — в «Мозге».";
  $("#dv-brains-go").disabled = false; clearInterval(DV_BR);
}
core.on("brains", (e) => dvBrains(e.data));
