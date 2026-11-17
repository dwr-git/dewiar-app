//@ Телефон и веб-версия, часть 19: «Рядом» и «Встречи».
//@ Собирается в android/assets/www/app.js (tools/app_join.py) — порядок частей = порядок исполнения; шапка «//@» в app.js не попадает.
/* ---------- «Близкие» → «Рядом»: радар (идея Валерия Михайловского; макет одобрен 20.10) ----------
   На радаре — близкие, которые сами решили показать, где они: ближе к центру — ближе к вам (шкала логарифмическая:
   300 м, 3 км, 30 км). Видно «сколько и в какую сторону», а не точку на карте. Своё место показываю только отмеченным
   близким и на срок (час, до вечера, всегда); оно шифруется здесь же, как сообщения (kind «geo»: сервер хранит одно
   последнее и видит только, кому и когда) и обновляется, пока Dewiar открыт — в фоне за телефоном не следим.
   «👋 Помахать» — сообщение {wave: 1, t: "👋"}: у близкого волны от вашего кружка, всплывающее «Андрей машет вам» и голос;
   старые программы покажут просто «👋». Место телефона — D.locate (Loc.java; в браузере — geolocation), ответ событием loc. */
const RAD_STALE = 15 * 60000, RAD_PUSH = 4 * 60000;
const RAD_DIR = ["на север", "на северо-восток", "на восток", "на юго-восток", "на юг", "на юго-запад", "на запад", "на северо-запад"];
const RAD_FINE = "android.permission.ACCESS_FINE_LOCATION", RAD_COARSE = "android.permission.ACCESS_COARSE_LOCATION";
let radMe = null, radErr = null, radSel = "", radHead = null, radCompass = false, radRaf = 0, radEdit = false, radEditSel = null, radEditMode = "hour";
const radWaveAt = {}, locWait = [];
const radCfg = () => Object.assign({ to: [], until: 0, asked: {} }, S.radar || {});
const radOn = () => { const r = radCfg(); return r.to.length > 0 && (r.until === -1 || r.until > Date.now()); };
const radPl = (n, a, b, c) => (n % 10 === 1 && n % 100 !== 11 ? a : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20) ? b : c);
const radFirst = (n) => String(n || "").trim().split(/\s+/)[0] || "Без имени";
/* ---------- «Встречи» (0.38.98): знакомства там, где вы сейчас ----------
   Сервер — cloud.php meet_handler (/meet/state|rules|here|leave|wave|block|report). Отметка на 1–3 часа: имя, пара слов,
   место; другие рядом (≈700 м) видят только это — ни точного места, ни расстояния. 👋 взаимно — оба в «Близких» (переписка
   шифруется). Ушли или вышло время — отметки и «помахал» нет. 18+ и правила — один раз; блок и жалоба — в меню «⋯». */
let MT = null, mtErr = "", mtEdit = false, mtHours = 2, mtTimer = 0, mtMenu = "";
async function mtLoad() {
  clearTimeout(mtTimer);
  try { MT = await clReq("GET", "/meet/state"); mtErr = ""; } catch (e) { mtErr = e.message; }
  if ($("#meet-body")) { meetRender(); mtTimer = setTimeout(() => { if ($("#meet-body") && $("#sh-close").classList.contains("on")) mtLoad(); }, 20000); }
}
const mtMin = (s) => Math.max(0, Math.round(s / 60));
const mtLeft = (u) => { const m = mtMin(u - Date.now() / 1000); return m >= 60 ? Math.floor(m / 60) + " ч" + (m % 60 ? " " + (m % 60) + " мин" : "") : m + " мин"; };
const mtAgo = (ts) => { const m = mtMin(Date.now() / 1000 - ts); return m < 2 ? "только что" : m < 60 ? m + " мин" : Math.floor(m / 60) + " ч"; };
function mtCall(path, body, btn) {
  if (btn) btn.disabled = true;
  return clReq("POST", path, body || {}).then(d => { MT = d; mtErr = ""; return d; })
    .catch(e => { toast(e.message, 4500); throw e; }).finally(() => { if (btn) btn.disabled = false; if ($("#meet-body")) meetRender(); });
}
function meetRender() {
  const body = $("#meet-body"); if (!body) return;
  if (!MT) { body.innerHTML = mtErr ? `<div class="card"><b>Встречи не открылись</b><p class="hint" style="margin:6px 0 10px">${esc(mtErr)}</p><button class="btn w" id="mt-retry">Повторить</button></div>`
    : `<p class="hint" style="text-align:center;margin:30px">Загружаю…</p>`; if ($("#mt-retry")) $("#mt-retry").onclick = () => { mtErr = ""; meetRender(); mtLoad(); }; return; }
  const me = MT.me || {};
  if (!me.adult) {
    body.innerHTML = `<div class="card mt-intro"><b class="mt-big">Знакомства там, где вы сейчас</b>
      <ul class="mt-rules"><li>Отметьтесь на концерте, выставке, в кафе — на 1–3 часа.</li>
        <li>Рядом видят только имя, пару слов о вас и место. Ни фото, ни адреса, ни расстояния.</li>
        <li>Связь — только если вы помахали 👋 друг другу: тогда вы оба в «Близких», переписка шифруется.</li>
        <li>Ушли — отметка и все «помахал» стираются. Истории нет.</li>
        <li>Неприятно — «Заблокировать» или «Пожаловаться» в одно нажатие.</li></ul>
      <label class="mt-adult"><input type="checkbox" id="mt-18"><span>Мне есть 18 лет, правила понятны</span></label>
      <button class="btn p w" id="mt-start" disabled>Начать</button></div>`;
    $("#mt-18").onchange = () => { $("#mt-start").disabled = !$("#mt-18").checked; };
    $("#mt-start").onclick = () => mtCall("/meet/rules", { adult: true }, $("#mt-start")).catch(() => { });
    return;
  }
  if (me.ban_until) { body.innerHTML = `<div class="card"><b>Встречи закрыты до ${new Date(me.ban_until * 1000).toLocaleDateString("ru-RU", { day: "numeric", month: "long" })}</b><p class="hint" style="margin:6px 0 0">На вас пожаловались несколько человек. Если это ошибка — напишите в поддержку из «Настройки» → «Сообщить о проблеме».</p></div>`; return; }
  const h = me.here, st = clLoad();
  if (!h || mtEdit) {
    if ($("#mt-go") && !$("#mt-go").disabled) return;      // анкета уже на экране — не стираем то, что человек вписывает (опрос раз в 20 с)
    const nm = (h && h.name) || String((st.me && st.me.name !== "Без имени" && st.me.name) || (S.close && S.close.name) || S.user_name || "").split(/\s+/)[0];
    body.innerHTML = `<div class="card mt-form"><b class="mt-big">${h ? "Изменить отметку" : "Отметиться здесь"}</b>
      <label class="f"><span>Как вас называть</span><input id="mt-name" maxlength="24" placeholder="имя" value="${esc(nm)}"></label>
      <label class="f"><span>Пара слов о себе</span><textarea id="mt-about" maxlength="120" rows="2" placeholder="например: впервые здесь, люблю джаз">${esc(((h ? h.about : st.me && st.me.about) || "").slice(0, 120))}</textarea></label>
      <label class="f"><span>Где вы</span><input id="mt-place" maxlength="60" placeholder="концерт, выставка, кафе…" value="${esc((h && h.place) || "")}"></label>
      <div class="mt-row"><span>Видно</span><div class="seg" id="mt-hours">${[1, 2, 3].map(n => `<button data-h="${n}" class="${mtHours === n ? "on" : ""}">${n} ч</button>`).join("")}</div></div>
      <div class="row2"><button class="btn p" id="mt-go" style="flex:2">${h ? "Сохранить" : "Отметиться"}</button>${h ? `<button class="btn" id="mt-cancel" style="flex:1">Отмена</button>` : ""}</div>
      <p class="hint" style="margin:10px 0 0">Ссылки, ники и номера не нужны — контакт откроется сам, когда помашете друг другу. Точное место никто не видит.</p></div>`;
    $$("#mt-hours button").forEach(b => b.onclick = () => { mtHours = +b.dataset.h; $$("#mt-hours button").forEach(x => x.classList.toggle("on", x === b)); });
    if ($("#mt-cancel")) $("#mt-cancel").onclick = () => { mtEdit = false; meetRender(); };
    $("#mt-go").onclick = async () => {
      const b = $("#mt-go"), name = $("#mt-name").value.trim();
      if (!name) { toast("Как вас называть? Достаточно имени."); $("#mt-name").focus(); return; }
      b.disabled = true; b.textContent = "Определяю место…";
      let g; try { g = await myPlace(60, true); } catch (e) { b.disabled = false; b.textContent = h ? "Сохранить" : "Отметиться"; toast(e.kind === "perm" ? "Разрешите Dewiar место — иначе не понять, кто рядом." : e.kind === "off" ? "Включите определение места в телефоне." : e.message, 5000); return; }
      // не через mtCall: при ошибке («без ссылок и номеров») анкета остаётся как есть — с тем, что человек вписал
      try { MT = await clReq("POST", "/meet/here", { lat: g.lat, lon: g.lon, name, about: $("#mt-about").value.trim(), place: $("#mt-place").value.trim(), hours: mtHours }); mtErr = ""; mtEdit = false; meetRender(); }
      catch (e) { toast(e.message, 5000); b.disabled = false; b.textContent = h ? "Сохранить" : "Отметиться"; }
    };
    return;
  }
  const ppl = MT.people || [];
  body.innerHTML = `<div class="card mt-me"><i class="dot"></i><div style="flex:1;min-width:0"><b>Вы отмечены</b><small>${h.place ? esc(h.place) + " · " : ""}видно ещё ${mtLeft(h.until)}</small></div>
      <button class="btn sm" id="mt-edit">Изменить</button><button class="btn sm" id="mt-leave">Уйти</button></div>
    <h3>${ppl.length ? "Рядом — " + ppl.length : "Рядом пока никого"}</h3>`
    + (ppl.length ? ppl.map(x => `<div class="card mtp${x.waves_me ? " in" : ""}${x.match ? " match" : ""}" data-mid="${esc(x.mid)}">
        <div class="mtp-h">${clAvaH(x.mid, x.name, x.face)}<div style="flex:1;min-width:0"><b>${esc(x.name)}</b>
          <small>${x.place ? esc(x.place) + " · " : ""}здесь ${mtAgo(x.since)}</small></div><button class="ib soft mt-more" data-m="${esc(x.mid)}" aria-label="Ещё: заблокировать, пожаловаться" aria-expanded="${mtMenu === x.mid}">⋯</button></div>
        ${x.about ? `<p class="mtp-a">${esc(x.about)}</p>` : ""}
        ${mtMenu === x.mid ? `<div class="row2 mt-menu"><button class="btn" data-block="${esc(x.mid)}" style="flex:1">Заблокировать</button><button class="btn" data-report="${esc(x.mid)}" style="flex:1">Пожаловаться</button></div>` : ""}
        <div class="mtp-act">${x.match ? `<span class="mt-ok">👋 Вы помахали друг другу</span><button class="btn p sm" data-chat="${esc(x.pid)}">Написать</button>`
          : x.waved ? `<span class="mt-ok">Вы помахали — ждём ответа</span><button class="btn sm" data-undo="${esc(x.mid)}">Отменить</button>`
          : x.waves_me ? `<span class="mt-in">👋 Вам помахали</span><button class="btn p sm" data-wave="${esc(x.mid)}">Помахать в ответ</button>`
          : `<button class="btn sm" data-wave="${esc(x.mid)}">👋 Помахать</button>`}</div></div>`).join("")
      : `<p class="hint" style="margin:0 4px 12px">Отметка видна ещё ${mtLeft(h.until)}. Кто отметится рядом — появится здесь.</p>`)
    + `<p class="hint">Видно только тех, кто отметился в пределах ~${MT.radius_m || 700} м. Ни точного места, ни расстояния не видит никто.</p>`;
  clFacesFill(body, true);
  $("#mt-edit").onclick = () => { mtEdit = true; meetRender(); };
  $("#mt-leave").onclick = () => mtCall("/meet/leave", {}, $("#mt-leave")).then(() => toast("Отметки больше нет")).catch(() => { });
  $$("[data-m]").forEach(b => b.onclick = () => { mtMenu = mtMenu === b.dataset.m ? "" : b.dataset.m; meetRender(); });
  $$("[data-wave]").forEach(b => b.onclick = () => mtCall("/meet/wave", { mid: b.dataset.wave }, b).then(d => {
    if (d.match) { if (d.state) clPeople(d.state); const p = (d.people || []).find(x => x.pid === d.pid); toast(`Вы помахали друг другу — ${p ? p.name : "собеседник"} теперь в «Близких»`, 4500); clHello().catch(() => { }); }
    else toast("👋 Помахали");
  }).catch(() => { }));
  $$("[data-undo]").forEach(b => b.onclick = () => mtCall("/meet/wave", { mid: b.dataset.undo, undo: 1 }, b).catch(() => { }));
  $$("[data-chat]").forEach(b => b.onclick = async () => { b.disabled = true; try { await clHello(); } catch (e) { } clTab = "close"; clCur = b.dataset.chat; clRender(); });
  $$("[data-block]").forEach(b => b.onclick = () => { if (!confirm("Заблокировать? Вы больше не увидите друг друга во Встречах, а если уже в «Близких» — он оттуда уйдёт.")) return;
    mtMenu = ""; mtCall("/meet/block", { mid: b.dataset.block }, b).then(() => toast("Заблокировано")).catch(() => { }); });
  $$("[data-report]").forEach(b => b.onclick = () => { const why = prompt("Что случилось? Можно коротко — это увидит только администратор Dewiar.", ""); if (why === null) return;
    mtMenu = ""; mtCall("/meet/report", { mid: b.dataset.report, why }, b).then(() => toast("Спасибо. Жалоба отправлена, вы больше не увидите друг друга")).catch(() => { }); });
}

function radGeo(a, b) {                                   // от a до b: [км, направление в градусах от севера по часовой]
  const t = Math.PI / 180, f1 = a.lat * t, f2 = b.lat * t, df = (b.lat - a.lat) * t, dl = (b.lon - a.lon) * t;
  const h = Math.sin(df / 2) ** 2 + Math.cos(f1) * Math.cos(f2) * Math.sin(dl / 2) ** 2;
  const deg = Math.atan2(Math.sin(dl) * Math.cos(f2), Math.cos(f1) * Math.sin(f2) - Math.sin(f1) * Math.cos(f2) * Math.cos(dl)) / t;
  return [2 * 6371 * Math.asin(Math.min(1, Math.sqrt(h))), (deg + 360) % 360];
}
const radKm = (km) => km < 0.05 ? "рядом" : km < 1 ? Math.round(km * 100) * 10 + " м" : (km < 10 ? km.toFixed(1).replace(".", ",") : Math.round(km).toLocaleString("ru-RU")) + " км";
const radKmSay = (km) => km < 1 ? `${Math.round(km * 100) * 10} метрах` : km < 10 ? `${km.toFixed(1).replace(".", ",")} км` : `${Math.round(km)} км`;
const radDir = (d) => RAD_DIR[Math.round((((d % 360) + 360) % 360) / 45) % 8];
function radAgo(ts, full) {
  const m = Math.max(0, Math.round((Date.now() - ts) / 60000)), h = Math.round(m / 60);
  if (m < 2) return full ? "только что" : "сейчас";
  if (m < 60) return full ? `${m} ${radPl(m, "минуту", "минуты", "минут")} назад` : `${m} мин назад`;
  if (m < 1440) return full ? `${h} ${radPl(h, "час", "часа", "часов")} назад` : `${h} ч назад`;
  return clTime(ts);
}
function radEve() {                                       // «До вечера» (22:00); поздно вечером — «До утра» (8:00)
  const d = new Date();
  if (d.getHours() < 21) { d.setHours(22, 0, 0, 0); return ["До вечера", +d]; }
  d.setDate(d.getDate() + 1); d.setHours(8, 0, 0, 0); return ["До утра", +d];
}
function radUntil(u) {
  if (u === -1) return "всегда";
  const d = new Date(u), hm = pad(d.getHours()) + ":" + pad(d.getMinutes());
  return d.toDateString() === new Date().toDateString() ? "до " + hm : "до завтра, " + hm;
}
const radList = (ns) => ns.length <= 1 ? ns.join("") : ns.length <= 3 ? ns.slice(0, -1).join(", ") + " и " + ns[ns.length - 1] : `${ns.slice(0, 2).join(", ")} и ещё ${ns.length - 2}`;

/* где я: разрешение спрашиваем только по нажатию (ask); ответ Loc.java — событием loc */
N.on("loc", e => { locWait.splice(0).forEach(w => w(e)); });
const radCan = () => !!D.locate && (D.has(RAD_FINE) || D.has(RAD_COARSE));
async function myPlace(maxAgeSec, ask) {
  if (!D.locate) throw Object.assign(new Error("на этом устройстве место не определяется"), { kind: "none" });
  if (!radCan()) {
    if (!ask) throw Object.assign(new Error("нет разрешения на местоположение"), { kind: "perm" });
    const ok = await needPerm(RAD_FINE);
    if (!ok && !D.has(RAD_COARSE)) throw Object.assign(new Error("Dewiar не разрешили определять место"), { kind: "perm" });
  }
  const e = await new Promise((res) => {
    const w = (x) => { clearTimeout(t); res(x); }, t = setTimeout(() => { const i = locWait.indexOf(w); if (i >= 0) locWait.splice(i, 1); res({ error: "место не определилось за полминуты" }); }, 30000);
    locWait.push(w); D.locate(maxAgeSec == null ? 60 : maxAgeSec);
  });
  if (e.error) throw Object.assign(new Error(e.error), { kind: /выключ/.test(e.error) ? "off" : /разреш/.test(e.error) ? "perm" : "fail" });
  if (!geoOk(+e.lat, +e.lon)) throw Object.assign(new Error("место не определилось"), { kind: "fail" });
  radMe = { lat: +e.lat, lon: +e.lon, acc: Math.max(0, +e.acc || 0), ts: Math.min(Date.now(), +e.ts || Date.now()) };
  return radMe;
}
async function radLocate(ask) {
  if (radLocate.busy && !ask) return;
  radLocate.busy = true;
  try { const me = await myPlace(ask ? 0 : 30, ask); radErr = null; radOwn(me); }
  catch (e) { radErr = { kind: e.kind || "fail", msg: e.message }; }
  finally { radLocate.busy = false; }
  if ($("#rad-body")) radRender();
}

/* кто показывает себя мне (st.geo: pid -> {lat, lon, acc, ts, until}); просроченное — убираем */
function radPeople() {
  const st = clLoad(), g = st.geo || {}, now = Date.now(), out = [];
  let drop = false;
  for (const pid of Object.keys(g)) {
    const x = g[pid], p = st.people.find(y => y.pid === pid);
    if (!p || (x.until !== -1 && x.until < now) || now - x.ts > 7 * 864e5) { delete g[pid]; drop = true; continue; }
    const o = { p, g: x };
    if (radMe) [o.km, o.deg] = radGeo(radMe, x);
    out.push(o);
  }
  if (drop) clSave();
  return out.sort((a, b) => (a.km ?? 1e9) - (b.km ?? 1e9));
}
function radTake(pid, name, g) {                          // пришло место близкого (или «больше не показываю»)
  const st = clLoad(); st.geo = st.geo || {};
  const had = !!st.geo[pid];
  if (!g || typeof g !== "object" || g.off || !geoOk(+g.lat, +g.lon)) delete st.geo[pid];
  else st.geo[pid] = { lat: +g.lat, lon: +g.lon, acc: Math.max(0, +g.acc || 0), ts: Math.min(Date.now(), +g.ts || Date.now()),
    until: g.until === -1 ? -1 : +g.until > 0 ? +g.until : Date.now() + 3600e3 };
  clSave();
  if (!had && st.geo[pid] && !document.hidden && !$("#rad-body")) toast(`📍 ${radFirst(name)} теперь на вашем радаре — «Близкие» → «Рядом»`, 3200);
  if ($("#rad-body")) radRender();
}

/* показать себя: отмеченным близким — место, не чаще раза в 4 минуты (если не сдвинулся на 50 м); снять — {off} */
async function radPush(force) {
  if (!radOn() || !syncCred() || !DC() || radPush.busy) return 0;
  const r = radCfg(), last = r.sent || {};
  if (!force && Date.now() - (last.at || 0) < 90000) return 0;
  radPush.busy = true;
  try {
    const me = await myPlace(force ? 30 : 120, false);
    if (!force && Date.now() - (last.at || 0) < RAD_PUSH && last.lat != null && radGeo(last, me)[0] < 0.05) return 0;
    const g = { lat: +me.lat.toFixed(5), lon: +me.lon.toFixed(5), acc: Math.round(me.acc), ts: me.ts, until: r.until };
    let n = 0;
    for (const pid of r.to) {
      if (!clLoad().people.some(p => p.pid === pid)) continue;
      try { await clSend(pid, "", [], "geo", { g }); n++; } catch (e) { plog("info", "радар: " + e.message); }
    }
    S.radar = Object.assign(radCfg(), { sent: { at: Date.now(), lat: me.lat, lon: me.lon } }); saveS();
    radOwn(me);
    return n;
  } catch (e) { plog("info", "радар: место — " + e.message); return 0; }
  finally { radPush.busy = false; }
}
/* Место телефона — своим же устройствам (компьютер рисует радар вокруг него): конверт /close/self {mygeo}, зашифрован
   ключами своих устройств, как ключ умного дома. Не чаще раза в 4 минуты (или сдвинулся на 50 м), только пока радаром
   пользуются (открыт или показываю себя близким) и только если есть другие свои устройства. */
async function radOwn(me) {
  try {
    if (!me || !syncCred() || !DC()) return false;
    const k = clKeys(), devs = ((clLoad().me || {}).devs || []).filter(d => d.pub && d.dev && d.dev !== k.dev);
    if (!devs.length) return false;
    const last = radOwn.last || {};
    if (Date.now() - (last.at || 0) < RAD_PUSH && last.lat != null && radGeo(last, me)[0] < 0.05) return false;
    const t = {}; devs.forEach(d => { t[d.dev] = DC().b64d(d.pub); }); t[k.dev] = DC().b64d(k.pub);
    const body = { mygeo: { lat: +me.lat.toFixed(5), lon: +me.lon.toFixed(5), acc: Math.round(me.acc || 0), ts: me.ts }, ts: Date.now() };
    await clReq("POST", "/close/self", { env: DC().encryptFor(body, DC().b64d(k.priv), k.dev, t) });
    radOwn.last = { at: Date.now(), lat: me.lat, lon: me.lon }; return true;
  } catch (e) { plog("info", "радар: место своим устройствам — " + e.message); return false; }
}
async function radStop(pids) { for (const pid of pids) { try { await clSend(pid, "", [], "geo", { g: { off: 1 } }); } catch (e) { } } }
async function radShare(to, mode) {
  const old = radCfg(), was = radOn() ? old.to : [];
  const until = mode === "off" ? 0 : mode === "hour" ? Date.now() + 3600e3 : mode === "eve" ? radEve()[1] : -1;
  S.radar = Object.assign(old, { to: mode === "off" ? old.to : to, until, sent: {} }); saveS();
  const gone = was.filter(pid => mode === "off" || !to.includes(pid));
  if (gone.length) radStop(gone);
  if (mode === "off") return 0;
  if (!radCan()) { try { await myPlace(0, true); } catch (e) { radErr = { kind: e.kind, msg: e.message }; } }
  return radPush(true);
}
function radTick() {
  if (appAway() || (typeof EXAM !== "undefined" && EXAM)) return;
  if (radOn()) radPush(false);
  if ($("#rad-body") && $("#sh-close").classList.contains("on")) { if (radCan() && (!radMe || Date.now() - radMe.ts > 30000)) radLocate(false); else radRender(); }
}
setInterval(radTick, 30000);
document.addEventListener("visibilitychange", () => { if (!document.hidden) setTimeout(radTick, 1500); });

/* 👋 */
async function radWave(who) {
  clLoad(); const p = clPerson(who);
  if (Date.now() - (radWaveAt[p.pid] || 0) < 4000) return p;
  radWaveAt[p.pid] = Date.now();
  await clSend(p.pid, "👋", [], "msg", { wave: 1 });
  D.vibrate(18); radFly(p.pid);
  return p;
}
function radWaveIn(pid, name) {
  const x = radPeople().find(o => o.p.pid === pid), first = radFirst(name);
  const line = `${first} машет вам 👋` + (x && x.km != null ? (x.km < 0.05 ? " — совсем рядом" : ` — ${radKm(x.km)} ${radDir(x.deg)}`) : "");
  if (document.hidden) { D.notify("👋 " + first, "машет вам"); return; }
  D.vibrate(40);
  if ($("#radar")) { radRipple(pid, 3); toast(line, 3600); }
  else if (!busy && state === "idle") showBot(line);
  else toast(line, 3600);
  if (!busy && state === "idle" && !(S.close && S.close.speak === false)) say(`${first} машет вам!`);
}

/* текст для модели: «где мама?» — только по радару, без адресов */
async function radWhereText(who) {
  const p = clPerson(who), g = ((clLoad().geo || {})[p.pid]);
  const live = g && (g.until === -1 || g.until > Date.now());
  if (!live) return `${p.name} сейчас не показывает вам, где находится. Скажи это одной фразой и что можно позвать на радар: «Близкие» → «Рядом» → «Позвать».`;
  let me = radMe && Date.now() - radMe.ts < 180000 ? radMe : null;
  if (!me) try { me = await myPlace(120, false); } catch (e) { me = null; }
  if (!me) return `Место ${p.name} обновлено ${radAgo(g.ts, true)}, но где сейчас вы — телефон не знает (нет разрешения на местоположение). Скажи, что расстояние будет видно, если разрешить место в «Близкие» → «Рядом».`;
  const [km, deg] = radGeo(me, g);
  return `${p.name}: ${km < 0.05 ? "совсем рядом с вами" : `в ${radKmSay(km)} от вас, ${radDir(deg)}`}${g.acc > 500 ? " (примерно)" : ""}; место обновлено ${radAgo(g.ts, true)}. Скажи коротко — расстояние и сторону; адресов и улиц не называй.`;
}

/* экран */
const radR = (km) => 46 + 132 * Math.max(0, Math.min(1, Math.log10(Math.max(km, 0.05) / 0.05) / Math.log10(600)));
const RAD_REDUCE = matchMedia("(prefers-reduced-motion: reduce)");
function radRender() {
  const body = $("#rad-body"); if (!body) return;
  const st = clLoad(), cfg = radCfg(), on = radOn();
  if (!st.people.length) {
    body.innerHTML = `<div class="card"><b>Сначала — близкие</b><p class="hint" style="margin:6px 0 10px">На радаре — близкие, которые сами решили показать вам, где они. Пригласите близкого, и сможете видеть друг друга и махать рукой.</p><button class="btn p w" id="rad-go">Пригласить</button></div>`;
    $("#rad-go").onclick = () => clInviteOpen(); return;
  }
  const ppl = radPeople(), seen = cfg.to.map(pid => st.people.find(p => p.pid === pid)).filter(Boolean).map(p => esc(radFirst(p.name)));
  const chip = on ? `<i class="dot"></i><span>${seen.length === 1 ? "Вас видит" : "Вас видят"} <b>${radList(seen.map(s => s)).replace(/, | и /g, m => `</b>${m}<b>`)}</b> · ${radUntil(cfg.until)}</span><button id="rad-edit">${radEdit ? "Отмена" : "Изменить"}</button>`
    : `<i class="dot"></i><span>Вас никто не видит</span><button id="rad-edit" class="${radEdit ? "" : "go"}">${radEdit ? "Отмена" : "Показать себя"}</button>`;
  const rr = [0.3, 3, 30].map(radR);
  const rings = rr.map(r => `<circle cx="180" cy="180" r="${r.toFixed(1)}"/>`).join("")
    + [["300 м", rr[0]], ["3 км", rr[1]], ["30 км", rr[2]]].map(([t, r]) => `<text x="${(180 - r + 5).toFixed(1)}" y="176">${t}</text>`).join("");
  body.innerHTML = `<div class="rad-seen${on ? " on" : ""}">${chip}</div>${radEdit ? radEditor() : ""}
    <div class="rad-wrap"><div class="radar${radMe ? "" : " nome"}" id="radar">
      <svg class="rad-rings" viewBox="0 0 360 360" aria-hidden="true">${rings}</svg>
      <div class="rad-sweep" id="rad-sweep"></div><div class="rad-n" id="rad-n" aria-hidden="true">С</div>
      <div class="rad-me" aria-label="Вы" data-face="${esc(st.me.pid || "me")}" data-v="${+st.me.face || 0}">Я</div><div id="rad-ppl"></div></div>
      <button class="ib soft rad-cmp${radCompass ? " on" : ""}" id="rad-cmp" aria-pressed="${radCompass}" aria-label="Повернуть радар по компасу" title="По компасу"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="m15.5 8.5-2 5-5 2 2-5z"/></svg></button></div>
    <div id="rad-card"></div><div id="rad-rest"></div>
    <p class="hint rad-priv">Место шифруется на телефоне — сервер Dewiar его не видит. Близкие видят только расстояние и сторону, пока вы разрешили; ваш компьютер с Dewiar — тоже, чтобы радар был и там. Обновляется, когда Dewiar открыт.</p>`;
  $("#rad-edit").onclick = () => { radEdit = !radEdit; radEditSel = null; radEditMode = cfg.until === -1 ? "always" : "hour"; radRender(); };
  $("#rad-cmp").onclick = () => radCompassSet(!radCompass);
  if (radEdit) radEditBind();
  // люди на радаре
  const sel = ppl.find(o => o.p.pid === radSel && o.km != null) || ppl.find(o => o.km != null && Date.now() - o.g.ts < RAD_STALE) || ppl.find(o => o.km != null);
  if (sel) radSel = sel.p.pid;
  $("#rad-ppl").innerHTML = ppl.filter(o => o.km != null).map(o => {
    const stale = Date.now() - o.g.ts > RAD_STALE;
    return `<button class="rad-p${stale ? " stale" : ""}${o.p.pid === radSel ? " sel" : ""}" data-pid="${esc(o.p.pid)}" style="--c:${clCol(o.p.pid)}" aria-label="${esc(o.p.name)}: ${radKm(o.km)} ${radDir(o.deg)}">
      ${clAvaH(o.p.pid, o.p.name, o.p.face)}<span><b>${esc(radFirst(o.p.name))}</b>${radKm(o.km)}${stale ? " · " + radAgo(o.g.ts) : ""}</span></button>`;
  }).join("");
  $$("#rad-ppl .rad-p").forEach(b => b.onclick = () => { radSel = b.dataset.pid; $$("#rad-ppl .rad-p").forEach(x => x.classList.toggle("sel", x === b)); radCard(); });
  radPlace(); radCard();
  // кто не показал себя — позвать
  const rest = st.people.filter(p => !ppl.some(o => o.p.pid === p.pid));
  const asked = cfg.asked || {};
  $("#rad-rest").innerHTML = rest.length ? `<h3>Ещё не на радаре</h3>` + rest.map(p => {
    const was = Date.now() - (asked[p.pid] || 0) < 3600e3, can = (p.devs || []).length;
    return `<div class="clp rad-rp">${clAvaH(p.pid, p.name, p.face)}<span><b>${esc(p.name)}</b><small>${can ? "пока не показывает, где он" + (/а$|я$/i.test(radFirst(p.name)) ? "а" : "") : "ещё не открывал Dewiar"}</small></span>
      ${can ? `<button class="btn rad-ask" data-pid="${esc(p.pid)}" ${was ? "disabled" : ""}>${was ? "Позвали" : "Позвать"}</button>` : ""}</div>`;
  }).join("") : "";
  $$(".rad-ask").forEach(b => b.onclick = async () => {
    b.disabled = true;
    try {
      const p = clPerson(b.dataset.pid);
      await clSend(p.pid, "📍 Покажешь мне, где ты? В Dewiar: «Близкие» → «Рядом» → «Показать себя». Я тебе тоже покажу.", []);
      S.radar = Object.assign(radCfg(), { asked: Object.assign({}, radCfg().asked, { [p.pid]: Date.now() }) }); saveS();
      b.textContent = "Позвали"; toast(`Позвали ${radFirst(p.name)} на радар`);
    } catch (e) { b.disabled = false; toast(e.message, 4000); }
  });
  clFacesFill(body);                                        // фото близких (и своё — в середине), как в списке «Близких»
  radLoop();
}
function radPlace() {                                     // по местам: угол — с поправкой на компас, близко стоящих раздвигаем
  const rot = radCompass && radHead != null ? radHead : 0, ppl = radPeople().filter(o => o.km != null);
  const pts = ppl.map(o => ({ pid: o.p.pid, r: radR(o.km), a: o.deg - rot }));
  for (let pass = 0; pass < 3; pass++) for (let i = 0; i < pts.length; i++) for (let j = i + 1; j < pts.length; j++) {
    const xy = (q) => [q.r * Math.sin(q.a * Math.PI / 180), -q.r * Math.cos(q.a * Math.PI / 180)];
    const [x1, y1] = xy(pts[i]), [x2, y2] = xy(pts[j]);
    if (Math.hypot(x1 - x2, y1 - y2) < 44) { pts[j].a += 16 * (pass % 2 ? -1 : 1); pts[i].a -= 6; }
  }
  for (const q of pts) {
    const b = $(`#rad-ppl .rad-p[data-pid="${CSS.escape(q.pid)}"]`); if (!b) continue;
    b.style.left = ((180 + q.r * Math.sin(q.a * Math.PI / 180)) / 3.6) + "%"; b.style.top = ((180 - q.r * Math.cos(q.a * Math.PI / 180)) / 3.6) + "%";
    b.dataset.a = String(((q.a % 360) + 360) % 360);
  }
  const n = $("#rad-n"); if (n) { const a = -rot * Math.PI / 180; n.style.left = (50 + 49.5 * Math.sin(a)) + "%"; n.style.top = (50 - 49.5 * Math.cos(a)) + "%"; }
  const s = $("#rad-card .rad-arr"); if (s) { const o = ppl.find(x => x.p.pid === radSel); if (o) s.style.setProperty("--deg", (o.deg - rot) + "deg"); }
}
function radCard() {
  const box = $("#rad-card"); if (!box) return;
  if (!radMe) {
    const e = radErr || { kind: radCan() ? "wait" : "perm" };
    box.innerHTML = `<div class="card rad-need">${e.kind === "wait" ? `<b>Определяю, где вы…</b><p class="hint">Чтобы показать расстояния до близких.</p>`
      : e.kind === "off" ? `<b>Местоположение выключено</b><p class="hint">Включите его в настройках телефона — тогда на радаре будет видно, кто рядом.</p>${D.locSettings ? `<button class="btn p w" id="rad-set">Открыть настройки</button>` : ""}`
      : e.kind === "none" ? `<b>Здесь место не определяется</b><p class="hint">Радар работает на телефоне и в браузере, который умеет определять место.</p>`
      : e.kind === "perm" ? `<b>Где вы — чтобы видеть, кто рядом</b><p class="hint">Место нужно, чтобы считать расстояния на этом экране. Близким оно уходит, только если вы сами покажете себя.</p><button class="btn p w" id="rad-allow">Разрешить определять место</button>`
      : `<b>Место не определилось</b><p class="hint">${esc(e.msg || "")}</p><button class="btn w" id="rad-allow">Попробовать ещё</button>`}</div>`;
    if ($("#rad-allow")) $("#rad-allow").onclick = () => { radErr = { kind: "wait" }; radCard(); radLocate(true); };
    if ($("#rad-set")) $("#rad-set").onclick = () => D.locSettings();
    if (radCan() && !radErr) radLocate(false);
    return;
  }
  const o = radPeople().find(x => x.p.pid === radSel && x.km != null);
  if (!o) { box.innerHTML = `<p class="hint rad-empty">Пока никто из близких не показал вам, где он. Покажите себя — и позовите их на радар.</p>`; return; }
  const p = o.p, stale = Date.now() - o.g.ts > RAD_STALE, call = (p.devs || []).length && window.DewiarCall;
  box.innerHTML = `<div class="rad-sel" style="--c:${clCol(p.pid)}"><div class="h">${clAvaH(p.pid, p.name, p.face)}
      <div><b>${esc(p.name)}</b><small>${stale ? "последний раз — " + radAgo(o.g.ts) : "обновлено " + radAgo(o.g.ts)}</small></div></div>
    <div class="rad-dist"><strong>${o.g.acc > 500 && o.km >= 0.05 ? "≈ " : ""}${radKm(o.km)}</strong><em>${o.km < 0.05 ? "совсем рядом" : radDir(o.deg)}</em>
      ${o.km >= 0.05 ? `<svg class="rad-arr" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3 7 20l5-4 5 4z"/></svg>` : ""}</div>
    <div class="rad-acts"><button class="rad-wave" id="rad-wave">👋 Помахать</button><button id="rad-msg">Написать</button>${call ? `<button id="rad-call">Позвонить</button>` : ""}</div></div>`;
  radPlace(); clFacesFill(box);
  $("#rad-wave").onclick = async () => { const b = $("#rad-wave"); b.disabled = true;
    try { const q = await radWave(p.pid); toast(`Помахали: ${radFirst(q.name)} увидит и услышит 👋`); } catch (e) { toast(e.message, 4000); }
    setTimeout(() => { if (b.isConnected) b.disabled = false; }, 1500); };
  $("#rad-msg").onclick = () => { clCur = p.pid; clRender(); };
  if ($("#rad-call")) $("#rad-call").onclick = () => clCall(p.pid, false).catch(e => toast(e.message, 4000));
}
function radEditor() {
  const st = clLoad(), cfg = radCfg(), sel = radEditSel || (radEditSel = new Set(cfg.to.filter(pid => st.people.some(p => p.pid === pid))));
  if (!sel.size && st.people.length === 1) sel.add(st.people[0].pid);          // один близкий — уже отмечен
  const modes = [["hour", "На час"], ["eve", radEve()[0]], ["always", "Всегда"]];
  return `<div class="card rad-ed"><b>Кому показать, где вы</b><small class="rad-ask" id="rad-ask">Нажмите на близких — отметятся галочкой</small>
    <div class="rad-who" id="rad-who">${st.people.map(p => `<button class="rad-pick${sel.has(p.pid) ? " on" : ""}" data-pid="${esc(p.pid)}" aria-pressed="${sel.has(p.pid)}"><i class="clava" style="--c:${clCol(p.pid)}">${esc((p.name || "?")[0].toUpperCase())}</i><span>${esc(radFirst(p.name))}</span></button>`).join("")}</div>
    <div class="rad-time" role="radiogroup" aria-label="На сколько">${modes.map(([k, t]) => `<button data-m="${k}" role="radio" aria-checked="${radEditMode === k}" class="${radEditMode === k ? "on" : ""}">${t}</button>`).join("")}</div>
    <p class="hint">Отмеченные близкие увидят у себя на радаре, сколько до вас и в какую сторону. Выключить можно в любой момент.</p>
    <div class="row2"><button class="btn p" id="rad-ok" style="flex:1.3">${radOkText(sel.size)}</button>${radOn() ? `<button class="btn" id="rad-hide" style="flex:1">Никому</button>` : ""}</div></div>`;
}
/* 20.10, отзыв: «не мог понять, как добавить близкого — оказывается, нужно на шарик нажать». Подсказка над кружками,
   у неотмеченных «+», на кнопке — сколько отмечено; «Показать» без отмеченных — кружки вздрагивают и подсказка
   становится заметной (а не всплывашка внизу). */
function radOkText(n) { return n ? `Показать ${n} ${n % 10 === 1 && n % 100 !== 11 ? "близкому" : "близким"}` : "Показать"; }
function radEditBind() {
  $$(".rad-pick").forEach(b => b.onclick = () => { const on = !radEditSel.has(b.dataset.pid); if (on) radEditSel.add(b.dataset.pid); else radEditSel.delete(b.dataset.pid);
    b.classList.toggle("on", on); b.setAttribute("aria-pressed", String(on)); $("#rad-ok").textContent = radOkText(radEditSel.size);
    $("#rad-ask").classList.remove("need"); $("#rad-ask").textContent = "Нажмите на близких — отметятся галочкой"; });
  $$(".rad-time button").forEach(b => b.onclick = () => { radEditMode = b.dataset.m; $$(".rad-time button").forEach(x => { x.classList.toggle("on", x === b); x.setAttribute("aria-checked", String(x === b)); }); });
  $("#rad-ok").onclick = async () => {
    const to = [...radEditSel];
    if (!to.length) { const a = $("#rad-ask"), w = $("#rad-who"); a.textContent = "Сначала нажмите на близкого — кому показать"; a.classList.add("need");
      w.classList.remove("need"); void w.offsetWidth; w.classList.add("need"); return; }
    const b = $("#rad-ok"); b.disabled = true;
    const n = await radShare(to, radEditMode); radEdit = false; radRender();
    toast(n ? `Готово: ${radList(to.map(pid => radFirst(clPerson(pid).name)))} ${to.length === 1 ? "видит" : "видят"} вас ${radUntil(radCfg().until)}` : radCan() ? "Покажу, как только определится место" : "Сначала разрешите определять место", 3400);
  };
  if ($("#rad-hide")) $("#rad-hide").onclick = async () => { await radShare([], "off"); radEdit = false; radRender(); toast("Теперь вас никто не видит"); };
}
function radLoop() {                                     // луч: проходя над человеком, «пингует» его
  if (radRaf || RAD_REDUCE.matches) return;
  const t0 = performance.now(), pinged = {};
  const tick = (t) => {
    const sw = $("#rad-sweep");
    if (!sw || document.hidden || !$("#sh-close").classList.contains("on")) { radRaf = 0; return; }
    const a = ((t - t0) / 6000 * 360) % 360; sw.style.transform = `rotate(${a}deg)`;
    $$("#rad-ppl .rad-p:not(.stale)").forEach(b => { const d = (+b.dataset.a - a + 360) % 360;
      if (d < 5 && !pinged[b.dataset.pid]) { pinged[b.dataset.pid] = 1; b.classList.remove("ping"); void b.offsetWidth; b.classList.add("ping"); }
      if (d > 30) pinged[b.dataset.pid] = 0; });
    radRaf = requestAnimationFrame(tick);
  };
  radRaf = requestAnimationFrame(tick);
}
function radAt(pid) { const b = pid && $(`#rad-ppl .rad-p[data-pid="${CSS.escape(pid)}"]`); return b ? [b.style.left, b.style.top] : ["50%", "50%"]; }
function radFly(pid) {
  const R = $("#radar"); if (!R) return;
  const [x, y] = radAt(pid), h = document.createElement("div"); h.className = "rad-fly"; h.textContent = "👋"; R.appendChild(h);
  if (RAD_REDUCE.matches) { h.style.left = x; h.style.top = y; setTimeout(() => h.remove(), 900); return; }
  requestAnimationFrame(() => requestAnimationFrame(() => { h.style.left = x; h.style.top = y; }));
  setTimeout(() => { h.style.opacity = 0; radRipple(pid, 1); setTimeout(() => h.remove(), 500); }, 1100);
}
function radRipple(pid, n) {
  const R = $("#radar"); if (!R) return;
  const [x, y] = radAt(pid);
  for (let i = 0; i < n; i++) setTimeout(() => { const r = document.createElement("div"); r.className = "rad-rip"; r.style.left = x; r.style.top = y;
    r.style.setProperty("--c", pid ? clCol(pid) : "#8B8CF7"); R.appendChild(r); setTimeout(() => r.remove(), 1500); }, i * 350);
}
function radCompassSet(on) {
  const h = radCompassSet.h || (radCompassSet.h = (e) => {
    const d = e.webkitCompassHeading != null ? e.webkitCompassHeading : (e.absolute || e.type === "deviceorientationabsolute") && e.alpha != null ? 360 - e.alpha : null;
    if (d == null || !radCompass) return;
    radHead = d; if (!radCompassSet.q) radCompassSet.q = requestAnimationFrame(() => { radCompassSet.q = 0; radPlace(); });
  });
  radCompass = on;
  if (on) {
    const go = () => { window.addEventListener("deviceorientationabsolute", h); window.addEventListener("deviceorientation", h);
      setTimeout(() => { if (radCompass && radHead == null) { toast("Компас на этом телефоне не нашёлся"); radCompassSet(false); } }, 2500); };
    if (window.DeviceOrientationEvent && typeof DeviceOrientationEvent.requestPermission === "function") DeviceOrientationEvent.requestPermission().then(r => r === "granted" ? go() : radCompassSet(false), () => radCompassSet(false));
    else go();
  } else { window.removeEventListener("deviceorientationabsolute", h); window.removeEventListener("deviceorientation", h); radHead = null; }
  const b = $("#rad-cmp"); if (b) { b.classList.toggle("on", on); b.setAttribute("aria-pressed", String(on)); }
  radPlace();
}
async function clSaveFile(p, m, j) {
  const f = (m.f || [])[j]; if (!f || m.out) return;
  try {
    toast("Скачиваю «" + f.name + "»…");
    const d = await clReq("GET", "/close/file", null, "&b64=1&id=" + encodeURIComponent(f.id));
    const bytes = DC().unseal(DC().b64d(f.key), Uint8Array.from(atob(d.b64), c => c.charCodeAt(0)));
    const where = D.saveDownloadB64 ? D.saveDownloadB64(f.name, f.type || "application/octet-stream", clStdB64(bytes)) : "";
    f.saved = true; clSave(); clRender(); toast(where ? "Сохранено: " + where : "Сохранено", 4000);
  } catch (e) { toast("Не скачался: " + e.message, 4000); }
}
$("#b-close").onclick = () => openClose("");
$("#cl-inv").onclick = () => { if (clTab === "ref") return refShare().catch(e => toast(e.message, 4000)); clInviteOpen(); };
document.addEventListener("visibilitychange", () => { if (!document.hidden && syncCred()) { clPoll(); noteAttSoon(6000); } });
/* ссылка-приглашение на работу в адресе (веб-версия: dwrapp/web/?work=… — «Работа без установки», 0.58) */
(() => { try { const m = /[?&#]work=([A-Za-z0-9_-]{8,64})/.exec(location.search + location.hash);
  if (m) {
    try { window.history.replaceState(null, "", location.pathname); } catch (e) { }   // history здесь — переписка; адресная строка — window.history
    S.workPending = m[1]; S.webWork = true; saveS();
  } } catch (e) { plog("warn", "работа по ссылке: " + e.message); } })();
setTimeout(() => { clLoad(); clBadge(); wkBadge(); if (S.closePending && syncCred()) clAcceptLink(S.closePending);
  if (S.workPending && (syncCred() || S.webWork)) wkLink("?work=" + S.workPending);
  else if (S.webWork && wkHas()) openWork("");                   // пришли ради работы — сразу «Работа»
  bsBoot(); clPoll(); clSchedule(); noteAttSoon(9000); }, 4000);
setTimeout(tmrShow, 700);                                       // идущие таймеры — сразу после запуска
N.on("alarms", () => { tmrShow(); syncSoon(); });               // отменили таймер в шторке (AlarmReceiver)
N.on("resume", () => tmrShow());

