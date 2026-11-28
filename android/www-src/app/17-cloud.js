//@ Телефон и веб-версия, часть 17: Dewiar Облако, заявка и перенос, приглашения, аккаунт dewiar.pro, Telegram.
//@ Собирается в android/assets/www/app.js (tools/app_join.py) — порядок частей = порядок исполнения; шапка «//@» в app.js не попадает.
/* ---------- Dewiar Облако (server/dwrapp/cloud.php): ключ dw-… или вход аккаунтом, заряд в талерах ----------
   Пути — параметром ?p=: /balance, /models, /usage, /topup, /netcfg, /report, /sync. Для модели base_url облака
   кончается на «?p=», и llmStream дописывает «/chat/completions» — выходит ?p=/chat/completions, как у OpenAI. */
const CLOUD_URL = window.DEWIAR_CLOUD_URL || "https://dewiar.pro/dwrapp/cloud.php";
let cloudInfo = null, cloudAt = 0;
const cloudBase = () => (S.llm.base_url || "").split("?")[0] || CLOUD_URL;
/* ---------- заявка на Dewiar из приложения и перенос кодом ----------
   joinSend — заявка без ключа (cloud.php ?p=/join); S.join {id, secret, base} хранит, чью заявку ждём; joinPoll — раз в
   минуту, пока приложение открыто, и при каждом открытии: одобрили — cloudConnect(ключ) и «Dewiar подключён».
   pairClaim — код из 6 цифр с другого устройства → тот же ключ (одни данные и заряд). */
async function joinSend(name, contact, note, opts = {}) {
  const base = CLOUD_URL.split("?")[0];
  const body = { name: String(name || "").trim(), contact: String(contact || "").trim(), note: String(note || "").trim(), device: opts.device || (D.web ? "веб-версия" : "телефон"), ids: joinIds() };
  if (opts.auto) body.auto = 1;
  const r = await http("POST", base + "?p=/join", { headers: { "Content-Type": "application/json" }, body, timeout: opts.auto ? 15000 : 20000 });
  let d = {}; try { d = JSON.parse(r.body || "{}"); } catch (e) { }
  if (r.status >= 400) throw new Error((d.error && d.error.message) || ("сервер ответил " + r.status));
  S.join = { id: d.id, secret: d.secret, base, at: Date.now(), auto: !!opts.auto }; saveS();
  if (d.key) await joinDone(d.key, d);
  return d;
}
async function joinPoll(force) {
  const j = S.join; if (!j || !j.id || S.llm.base_url && !S.llm.trial && !force) return null;
  const r = await http("GET", j.base + "?p=/join&id=" + encodeURIComponent(j.id) + "&s=" + encodeURIComponent(j.secret), { timeout: 15000 });
  let d = {}; try { d = JSON.parse(r.body || "{}"); } catch (e) { }
  if (r.status === 404) { S.join = null; saveS(); return { status: "gone", text: "Заявка не нашлась — отправьте новую." }; }
  if (r.status >= 400) throw new Error((d.error && d.error.message) || ("сервер ответил " + r.status));
  if (d.status === "ok" && d.key) await joinDone(d.key, d);
  if (d.status === "no") { S.join = null; saveS(); }
  return d;
}
async function joinDone(key, d) {
  const auto = !!(S.join && S.join.auto);
  await cloudConnect(key, S.join && S.join.base);
  S.join = null; if (auto) S.autoJoined = true; saveS();
  if (auto) {                      // автоподключение — тихо: человек, может, уже разговаривает; голосом — только если ждёт
    plog("info", `☁ автоподключение: мозг Dewiar подключён (${(d && d.gift) || "?"})`);
    toast(giftLine(d), 6000); netNote();
    if (!busy && state === "idle") showBot(gfix(`Я подключена к мозгу Dewiar и готова. Спросите меня что-нибудь!`));
    startCardCheck(); return;
  }
  const msg = gfix("Готово — Dewiar подключён" + (d && d.reply ? ` («${d.reply}»)` : "") + ". Спросите меня что-нибудь!");
  showBot(msg); toast(d && d.gift ? giftLine(d) : "Мозг подключён: модели Dewiar", 5000); say(msg);
  netNote();
}
/* «Сеть Лиры» включена по умолчанию у новых (14.11, вариант А) — честно, один раз, сразу после подключения мозга */
function netNote() {
  if (S.netShare !== true || S.netNoted) return;
  S.netNoted = Date.now(); saveS();
  setTimeout(() => toast("Общие вопросы без личного иногда отвечают компьютеры других людей — «Сеть Лиры». Выключить: ⚙ → Мозг.", 7000), 6500);
}
/* 0.82.1 (владелец 04.11: «много новых людей, а донатов нет — чтобы было понятно и просто»): вместо «бесплатный мозг — теперь
   умею всё» — честно: сколько примерно ответов в подарке и где пополнить; подарок здесь уже был — так и говорим. */
function giftLine(d) {
  d = d || {};
  if (d.gift === "again") return "Подключено — вернула ваш прежний ключ. Пополнить: ⚙ → Мозг";
  if (d.gift === "none") return "Подключено. Подарок на этом устройстве уже был — пополнить: ⚙ → Мозг";
  if (d.gift === "busy") return "Подключено. Сейчас подключается необычно много людей — подарок не выдан. Пополнить: ⚙ → Мозг";
  if (d.gift === "ip") return "Подключено. С этого адреса сегодня подключалось много людей — подарок меньше. Пополнить можно в ⚙ → Мозг";
  const n = +d.gift_turns || 0;
  return "Подключено. В подарок — " + (n ? `примерно ${n.toLocaleString("ru-RU")} ${turnsWord(n)}` : "несколько ответов") + ", дальше — пополнение в ⚙ → Мозг";
}
/* Постоянные номера этого устройства для /join (0.82.1): свой номер установки (S.inst — «Забыть ключ» его не сбрасывает) и
   номер Android от приложения (хэш ANDROID_ID — переживает переустановку). По ним сайт узнаёт устройство: прежний ключ
   вместо нового подарка. */
function joinIds() {
  if (!/^in-[0-9a-f]{24}$/.test(S.inst || "")) { S.inst = "in-" + Array.from({ length: 24 }, () => "0123456789abcdef"[Math.random() * 16 | 0]).join(""); saveS(); }
  let aid = ""; try { aid = String(JSON.parse(D.info() || "{}").aid || ""); } catch (e) { }
  return /^an-[0-9a-f]{40}$/.test(aid) ? [S.inst, aid] : [S.inst];
}
/* Автоподключение (0.69; владелец 29.10: «за наш счёт по умолчанию — важно, чтобы у пользователя всё работало сразу;
   взять хотя бы что-то для узнавания, контакт попросить позже»). Мозга нет, входа и заявки нет — заявка auto: модель
   телефона (или «веб-версия»), без контакта; сайт одобряет сам — ключ подключается сразу. Не чаще раза в час; нет сети —
   при следующем вопросе. S.autoJoin === false — выключено. Контакт — только по желанию самого человека («Мозг» → «Как к вам обращаться»). */
/* Контакт — только сам человек, когда захочет: «Мозг» → «Как к вам обращаться» и карточка пополнения. Сами не просим
   (владелец 24.11: «первый вход в Лиру должен быть простой, лёгкий, приятный.. ничего от пользователей просить и требовать
   не желательно»); до 1.0.69 после пяти ответов всплывало «Оставите контакт?». */
function contactCardHtml(ask) {
  return `<div class="card ctc"><b>${ask ? "Оставите контакт?" : "Как к вам обращаться"}</b><p class="hint" style="margin:4px 0 10px">Мозг Dewiar подключился сам, без анкеты. Если что-то сломается — разработчик сможет вам ответить. По желанию.</p>
    <input id="ct-name" class="grname" maxlength="80" placeholder="Имя"><input id="ct-contact" class="grname" maxlength="120" placeholder="Почта, Telegram или телефон" style="margin-top:8px">
    <div class="row2" style="margin-top:10px"><button class="btn p" id="ct-go" style="flex:1">Сохранить</button>${ask ? `<button class="btn" id="ct-x">Не сейчас</button>` : ""}</div>
    <p class="hint" style="margin:10px 0 0">Контакт видит только команда Dewiar; удалить — «Настройки» → «Сообщить о проблеме» со словами «Мои данные». <a href="${siteUrl("dwrapp/privacy")}">Политика конфиденциальности</a></p></div>`;
}
function contactWire() {
  const go = $("#ct-go"); if (!go) return;
  cloudGet(cloudBase(), S.llm.api_key, "/me/contact").then(d => { const n = $("#ct-name"), c = $("#ct-contact");
    if (n && !n.value && d.name && d.name !== "Без имени" && !/^(телефон|веб)/i.test(d.name)) n.value = d.name; if (c && !c.value) c.value = d.contact || ""; }).catch(() => {});
  if ($("#ct-x")) $("#ct-x").onclick = () => showCard("");
  go.onclick = async () => {
    const name = $("#ct-name") ? $("#ct-name").value.trim() : "", contact = $("#ct-contact").value.trim();
    if (!name && !contact) return toast("Напишите имя или контакт");
    go.disabled = true;
    try { await cloudPost("/me/contact", { name, contact }); S.contactDone = true; saveS(); toast("Сохранено — спасибо!", 3000); if ($("#ct-x")) showCard(""); if (go.closest(".pc-ct")) go.closest(".pc-ct").remove(); }
    catch (e) { toast(e.message, 4000); }
    go.disabled = false;
  };
}
let autoJoinBusy = null;
/* Автоподключение — в приложении (не в веб-версии: там и так сразу пробный разговор без входа, а ключ на каждый браузер —
   лишнее) и не в проверках в браузере без своего флага (window.DEWIAR_AUTOJOIN); S.autoJoin === false — выключено. */
const autoOk = () => S.autoJoin !== false && !S.forgotKey && !D.web && (!D.mock || !!window.DEWIAR_AUTOJOIN);
function autoJoin(why) {
  if (!autoOk() || loggedIn() || (S.llm.base_url && !S.llm.trial) || (S.join && S.join.id)) return Promise.resolve(false);
  if (Date.now() - (S.autoTried || 0) < 3600e3) return Promise.resolve(false);
  if (autoJoinBusy) return autoJoinBusy;
  S.autoTried = Date.now(); saveS();
  let info = {}; try { info = JSON.parse(D.info() || "{}"); } catch (e) { }
  const dev = D.web ? "веб-версия" + (navigator.userAgent.match(/iPhone|iPad|Macintosh|Android|Windows/) || [""])[0].replace(/^/, " ") : "телефон " + (info.device || "Android");
  autoJoinBusy = joinSend(D.web ? "Гость веб-версии" : (info.device || "Без имени"), "", "", { auto: true, device: dev.trim() })
    .then(d => { plog("info", `☁ автоподключение (${why}): заявка №${d.id} — ${d.key ? "ключ сразу" : "ждёт одобрения"}`); return !!d.key; })
    .catch(e => { plog("warn", "☁ автоподключение не вышло: " + e.message); return false; })
    .finally(() => { autoJoinBusy = null; });
  return autoJoinBusy;
}
async function pairClaim(code) {
  const r = await http("POST", CLOUD_URL.split("?")[0] + "?p=/pair/claim", { headers: { "Content-Type": "application/json" }, body: { code: String(code).replace(/\D/g, "") }, timeout: 15000 });
  let d = {}; try { d = JSON.parse(r.body || "{}"); } catch (e) { }
  if (r.status >= 400 || !d.key) throw new Error((d.error && d.error.message) || ("сервер ответил " + r.status));
  return d.key;
}
let joinTick = 0;
setInterval(() => { if (S.join && !appAway() && !busy && (!liteOn() || ++joinTick % 3 === 0)) joinPoll(false).catch(() => {}); }, 60000);
document.addEventListener("visibilitychange", () => { if (!document.hidden && S.join) setTimeout(() => joinPoll(false).catch(() => {}), 1500); });
async function cloudGet(base, key, path) {
  const r = await http("GET", base.split("?")[0] + "?p=" + path, { headers: { Authorization: "Bearer " + key }, timeout: 10000 });
  let d = {}; try { d = JSON.parse(r.body || "{}"); } catch (e) { }
  if (r.status >= 400) throw new Error((d.error && d.error.message) || ("облако ответило " + r.status));
  return d;
}
async function cloudPost(path, body) {
  const r = await http("POST", cloudBase() + "?p=" + path, { headers: { Authorization: "Bearer " + S.llm.api_key, "Content-Type": "application/json" }, body, timeout: 40000 });
  let d = {}; try { d = JSON.parse(r.body || "{}"); } catch (e) { }
  if (r.status >= 400) throw new Error((d.error && d.error.message) || ("облако ответило " + r.status));
  return d;
}
const RQ = { new: "на проверке", done: "зачислено", rejected: "отклонено" };
/* 1.0.31 «Баланс» (владелец 18.11): на сколько дней хватит, подарок месяца, свои лимиты, история — как в студии компьютера */
const daysWord = (n) => { const a = n % 10, b = n % 100; return a === 1 && b !== 11 ? "день" : a >= 2 && a <= 4 && (b < 12 || b > 14) ? "дня" : "дней"; };
function daysLine(c) {
  const n = c && c.days_left;
  if (n == null || n < 0) return "";
  return n > 365 ? " · при нынешних тратах — больше чем на год" : ` · при нынешних тратах — примерно на ${n.toLocaleString("ru-RU")} ${daysWord(n)}`;
}
function monthGiftLine(c) {
  const g = c && c.gift;
  if (!g || g.left == null) return "";
  const until = new Date(g.until + "T12:00").toLocaleDateString("ru-RU", { day: "numeric", month: "long" });
  const num = (v) => (+v).toLocaleString("ru-RU", { maximumFractionDigits: 2 });
  return ` Подарок месяца: осталось ${num(g.left)} из ${num(g.amount)} тал. до ${until} — не копится, тратится первым.`;
}
function limFill(l) {
  const box = $("#cl-lim"); if (!box) return;
  box.style.display = l ? "" : "none"; if (!l) return;
  const put = (el, v) => { if (el && document.activeElement !== el) el.value = +v > 0 ? String(+v).replace(".", ",") : ""; };
  put($("#cl-lim-d"), l.day); put($("#cl-lim-m"), l.month);
  const save = () => {
    const v = (el) => { const x = el.value.trim().replace(",", "."); return x === "" ? 0 : +x; };
    const day = v($("#cl-lim-d")), month = v($("#cl-lim-m"));
    if (!(day >= 0) || !(month >= 0)) { toast("Лимит — число талеров, например 0,5"); return; }
    cloudPost("/limits", { day, month }).then(r => toast(r.day || r.month ? "Лимит сохранён — для всех ваших устройств" : "Без лимита")).catch(e => toast(e.message));
  };
  $("#cl-lim-d").onchange = save; $("#cl-lim-m").onchange = save;
}
/* 1.0.32 автопополнение — как в студии компьютера: виден, только когда на сайте есть способ с сохранением карты */
const payLangOk = (m) => !m || !m.lang || (m.lang === "ru") === ((window.dwLang ? dwLang() : "ru") === "ru");
const numR = (v) => (+v || 0).toLocaleString("ru-RU", { maximumFractionDigits: 2 });
function autoFill(a) {
  const box = $("#cl-auto"); if (!box) return;
  box.style.display = a && a.available ? "" : "none"; if (!a || !a.available) return;
  $("#cl-auto-on").checked = !!a.on;
  const put = (el, v) => { if (el && document.activeElement !== el) el.value = String(v).replace(".", ","); };
  put($("#cl-auto-below"), a.below); put($("#cl-auto-amt"), a.amount); put($("#cl-auto-cap"), a.cap);
  $("#cl-auto-t").textContent = `Когда останется меньше ${numR(a.below)} тал. — пополним на ${numR(a.amount)} тал. (1 тал. = $1) с карты${a.card ? " " + a.card : ", которую сохраните при оплате"}, не больше ${numR(a.cap)} тал. в месяц. После каждого списания — строка в истории и чек на почту; выключить — здесь же.`;
  $("#cl-auto-st").textContent = a.stopped || (a.on ? `В этом месяце пополнено: ${numR(a.month_sum)} из ${numR(a.cap)} тал.` : "");
  $("#cl-auto-forget").hidden = !a.card;
  const save = (extra) => {
    const v = (id) => $(id).value.trim().replace(",", ".");
    cloudPost("/autopay", Object.assign({ on: $("#cl-auto-on").checked, below: v("#cl-auto-below"), amount: v("#cl-auto-amt"), cap: v("#cl-auto-cap") }, extra || {}))
      .then(r => { autoFill(r); if (r.need_card) { toast(r.message, 6000); if (r.setup && r.setup.url) D.openUrl(r.setup.url); } else toast(r.on ? "Автопополнение включено" : "Автопополнение выключено"); })
      .catch(e => toast(e.message));
  };
  $("#cl-auto-on").onchange = () => save();
  ["#cl-auto-below", "#cl-auto-amt", "#cl-auto-cap"].forEach(id => $(id).onchange = () => save());
  $("#cl-auto-forget").onclick = () => save({ forget: true, on: false });
}
const HK = { paid: "пополнение", gift: "подарок", burn: "остаток подарка сгорел", minus: "списано" };
function clHist(list) {
  const el = $("#cl-reqs"); if (!el || !(list || []).length) return;
  el.insertAdjacentHTML("beforeend", `<div class="cp-hh">История</div>` + list.map(h => `<div class="rqi ${esc(h.kind)}"><span>${new Date(h.ts * 1000).toLocaleDateString("ru-RU", { day: "numeric", month: "short" })} · ${esc(HK[h.kind] || h.kind)}</span><b>${h.amount > 0 ? "+" : "−"}${Math.abs(h.amount).toLocaleString("ru-RU", { maximumFractionDigits: 4 })}</b></div>`).join(""));
}
function clReqs(list) {
  const el = $("#cl-reqs"); if (!el) return;
  el.innerHTML = (list || []).map(r => `<div class="rqi ${esc(r.status)}"><span>${new Date(r.ts * 1000).toLocaleDateString("ru-RU", { day: "numeric", month: "short" })}${r.amount ? " · " + (+r.amount || 0) + " тал." + (rubText(+r.amount) ? " " + rubText(+r.amount) : "") : ""}${r.reply ? " · «" + esc(r.reply) + "»" : ""}</span><b>${RQ[r.status] || esc(r.status)}${r.status === "done" ? " +" + (+r.credited || 0) : ""}</b></div>`).join("");
}
/* «Оплатить картой» (ЮMoney, 03.11; владелец: «пришли оплаты — только номера карт и суммы, как найти этих людей?»): сервер
   отдаёт ссылку перевода с меткой человека DW-… (yoomoney.url), суммы и курс; сумма дописывается, страница ЮMoney — во внешнем
   браузере (на телефоне — Phone.openUrl, в веб-версии — новая вкладка), талеры зачисляются сами (cloud.php ym_notify) */
let ymCur = null, ymT = 0;
const ymTal = (y, s) => (Math.round(s * y.rate * 1e4) / 1e4).toLocaleString("ru-RU") + " тал.";
const ymStrip = (t) => {             // строки-ссылки для старых версий: для способов, у которых здесь есть свой блок, — прячем
  let s = String(t || "");
  if (ymCur) s = s.replace(/^[^\n]*\?p=\/pay\/card[^\n]*\n*/m, "");
  if (cxCur) s = s.replace(/^[^\n]*\?p=\/pay\/crypto[^\n]*\n*/m, "");
  return s;
};
function ymFill(y) {
  ymCur = y && y.url && payLangOk({ lang: "ru" }) ? y : null;      // ЮMoney — только в русской программе (владелец 18.11)
  const box = $("#cl-ym"); if (!box) return;
  box.style.display = ymCur ? "" : "none";
  if (!ymCur) return;
  $("#cl-ym-sums").innerHTML = (y.sums || []).map(s => `<button type="button" data-s="${+s}"><b>${(+s).toLocaleString("ru-RU")} ₽</b><small>${ymTal(y, +s)}</small></button>`).join("");
  $$("#cl-ym-sums button").forEach(b => b.onclick = () => ymPay(+b.dataset.s));
}
function ymPay(s) {
  const r = $("#cl-ym-res"), y = ymCur, lo = (y && y.min) || 10, hi = (y && y.max) || 100000;
  if (!y || !r) return;
  if (!(s >= lo && s <= hi)) { r.className = "res bad"; r.textContent = `Сумма — от ${lo} до ${hi.toLocaleString("ru-RU")} ₽`; return; }
  s = Math.round(s);
  if (!D.openUrl(y.url + "&sum=" + s)) { r.className = "res bad"; r.textContent = "Не открылся браузер — попробуйте ещё раз."; return; }
  r.className = "res ok"; r.textContent = `Открыла страницу ЮMoney: ${s.toLocaleString("ru-RU")} ₽ → ${ymTal(y, s)}. Оплатите — талеры придут сами.`;
  payWatch();
}
function payWatch() {                                 // ждём зачисления: 10 минут, раз в 20 секунд
  clearInterval(ymT); let k = 0; const was = +clBal || 0;
  ymT = setInterval(() => { if (++k > 30) { clearInterval(ymT); return payLate(); }
    cloudBalance(true).then(c => { cloudFill(c); if ($("#cl-pay") && $("#cl-pay").style.display !== "none") clPayLoad();
      if (+c.balance > was + 1e-6) { clearInterval(ymT); const r = $("#cl-ym-res"); if (r) { r.className = "res ok"; r.textContent = `Пришло: +${(Math.round((+c.balance - was) * 1e4) / 1e4).toLocaleString("ru-RU")} тал. Спасибо!`; } } }).catch(() => {}); }, 20000);
}
/* №544/№545 (04.11: «пополнил DW-…, ничего не пришло»): 10 минут после оплаты картой талеров нет — перевод мог уйти без
   номера DW-…: что делать — снимок оплаты заявкой, проверят вручную */
function pendingLine() { return "заявка на пополнение на проверке — обычно зачисляем в течение дня"; }
var clBal = 0;                                       // последний известный остаток — понять, что оплата пришла
function payLate() {
  const r = $("#cl-ym-res"); if (!r) return;
  r.className = "res bad"; r.textContent = "Талеры пока не пришли. Если вы оплатили — пришлите снимок оплаты ниже («Отправить заявку»): проверим вручную, обычно в течение дня.";
  const m = $("#cl-man"); if (m) { m.style.display = ""; const h = $("#cl-man-h"); if (h) h.style.display = ""; m.scrollIntoView({ block: "nearest", behavior: "smooth" }); }
}
/* Способы пополнения (03.11, владелец: «что-то на будущее, не привязанное к одному платёжному сервису, возможно даже
   криптовалютой»): сервер отдаёт pay — включённые способы в порядке владельца; блоки «Оплатить картой», «Криптой» и
   «Снимок оплаты» встают в этом порядке. «Криптой»: TON или USDT в сети TON на кошелёк владельца с комментарием DW-…
   (сайт сам видит перевод и зачисляет — cloud.php cx_poll); адрес, комментарий, QR и ссылка ton:// в кошелёк. */
let cxCur = null, cxAsset = "ton";
const payPick = (list, id) => (Array.isArray(list) ? list : []).find(m => m && m.id === id) || null;
const numRu = (v) => (+v || 0).toLocaleString("ru-RU", { maximumFractionDigits: 6 });
function payArrange(list) {
  const box = $("#cl-pay"), end = $("#cl-reqs"), map = { yoomoney: "#cl-ym", crypto: "#cl-cx", manual: "#cl-man" };
  if (!box || !end || !Array.isArray(list)) return;
  list.forEach(m => { const el = map[m.id] && $(map[m.id]); if (el) box.insertBefore(el, end); });
  const h = $("#cl-man-h"); if (h) h.style.display = list.some(m => m.id !== "manual") ? "" : "none";
}
function cxFill(x) {
  cxCur = x && x.address && (x.assets || []).length ? x : null;
  const box = $("#cl-cx"); if (!box) return;
  box.style.display = cxCur ? "" : "none";
  if (!cxCur) return;
  if (!cxCur.assets.some(a => a.id === cxAsset)) cxAsset = cxCur.assets[0].id;
  const a = cxCur.assets.find(z => z.id === cxAsset);
  $("#cl-cx-seg").innerHTML = cxCur.assets.length > 1 ? cxCur.assets.map(z => `<button type="button" data-a="${esc(z.id)}" class="${z.id === cxAsset ? "on" : ""}">${esc(z.name)}</button>`).join("") : "";
  $$("#cl-cx-seg button").forEach(b => b.onclick = () => { cxAsset = b.dataset.a; cxFill(cxCur); });
  $("#cl-cx-addr").textContent = cxCur.address; $("#cl-cx-code").textContent = cxCur.code;
  $("#cl-cx-warn").innerHTML = `<b>⚠ ${esc(cxCur.warn)}</b>` + (a.note ? `<span>${esc(a.name)} — ${esc(a.note)}.</span>` : "");
  $("#cl-cx-rate").textContent = `1 ${a.name} = ${numRu(a.rate)} тал. · от ${numRu(a.min)} ${a.name} · проверяем раз в ${cxCur.every || 2} мин.`;
  $("#cl-cx-qr").innerHTML = typeof qrcode === "function" && typeof clQr === "function" ? clQr(a.link) : "";
}
function cxCopy(what) { if (!cxCur) return; D.copy(cxCur[what]); toast(what === "code" ? `Комментарий ${cxCur.code} скопирован` : "Адрес скопирован"); }
function cxOpen() {
  const r = $("#cl-cx-res"), a = cxCur && cxCur.assets.find(z => z.id === cxAsset);
  if (!a || !r) return;
  if (!D.openUrl(a.link)) { r.className = "res bad"; r.textContent = "Кошелёк TON на этом устройстве не нашёлся — скопируйте адрес и комментарий в свой кошелёк."; return; }
  r.className = "res ok"; r.textContent = `Открыла кошелёк. Проверьте, что в комментарии стоит ${cxCur.code}, — талеры придут сами через несколько минут.`;
  payWatch();
}
async function clPayLoad() {
  try { const r = await cloudGet(cloudBase(), S.llm.api_key, "/topup");
    ymFill(r.yoomoney); cxFill(payPick(r.pay, "crypto")); payArrange(r.pay); clTopFill(r.text, r.code, r.rub); clReqs(r.requests); clHist(r.history); }
  catch (e) { if ($("#cl-top")) $("#cl-top").textContent = e.message; }
}
/* «Как пополнить» (0.82.1): текст владельца — шагом «1. Оплатите»; ссылки в нём нажимаются (и после «Обновить» — раньше
   cloudFill писал textContent, и ссылка становилась простым текстом); первая ссылка — крупной кнопкой «Перейти к оплате».
   Номер DW-… — не первой строкой, а мелко после шагов: «ваш номер для оплаты (если спросят)». */
let clRub = null;
const PAY_URL_RX = /(https?:\/\/[^\s<>"]+[^\s<>".,;:!?)»])/g;
function clTopFill(text, code, rub) {
  const el = $("#cl-top"); if (!el) return;
  if (rub !== undefined) clRub = +rub > 0 ? +rub : null;
  const t = ymStrip(text).replace(/^Ваш номер для оплаты:[^\n]*\n*/, "").trim();
  el.innerHTML = esc(t).replace(PAY_URL_RX, '<a href="#" data-ext="$1">$1</a>');
  $$("#cl-top a[data-ext]").forEach(x => x.onclick = (e) => { e.preventDefault(); D.openUrl(x.dataset.ext); });
  const url = (t.match(PAY_URL_RX) || [])[0], go = $("#cl-go");
  if (go) { go.hidden = !url; go.onclick = () => { if (url && !D.openUrl(url)) toast("Не открылся браузер — нажмите ссылку ниже"); }; }
  const cd = $("#cl-code"); if (cd) cd.innerHTML = code ? `Ваш номер для оплаты: <b>${esc(code)}</b> (если спросят)` : "";
  clRubShow();
}
const rubText = (tal) => clRub && tal > 0 ? "≈ " + Math.round(tal * clRub).toLocaleString("ru-RU") + " ₽" : "";
function clRubShow() { const a = $("#cl-amt"), r = $("#cl-rub"); if (a && r) r.textContent = rubText(+String(a.value).replace(",", ".") || 0); }
/* Открыть «Пополнить» откуда угодно (карточка после 402, предупреждение, значок баланса): «Мозг», панель уже раскрыта и
   прокручена к себе. Ключа нет — просто «Мозг». */
function openTopup() {
  showCard(""); openSettings("brain");
  let n = 0;
  const go = () => { const t = $("#cl-pay"); if (!t) { if (++n < 30 && S.llm.cloud) setTimeout(go, 100); return; }
    if (t.style.display === "none") { t.style.display = ""; clPayLoad(); }
    $("#cl-how") && $("#cl-how").classList.add("on");
    setTimeout(() => (t.querySelector(".pay-steps") ? $("#cl-how") : t).scrollIntoView({ behavior: "smooth", block: "start" }), 60); };
  setTimeout(go, 60);
}
const balShort = (b, text) => { const n = +b; if (!isFinite(n) || b == null) return String(text || "").replace(/\s*тал\.?$/, "");
  return (n >= 10 ? String(Math.floor(n)) : String(Math.floor(n * 10) / 10)).replace(".", ","); };
/* Значок баланса у имени персонажа (0.82.1): ниже ~30 % — маленькая плашка с процентом; нажали — «Пополнить». */
function balBadge(c) {
  const b = $("#bal"); if (!b) return;
  const pct = c ? Math.max(0, Math.min(100, +c.percent || 0)) : 100, on = !!c && S.llm.cloud && !c.frozen && (c.empty || pct < 30);
  b.hidden = !on; b.classList.toggle("empty", !!(c && c.empty));
  $("#who").classList.toggle("low", false);
  // 13.11 (владелец: «талеры в виджете — случайно или поехала вёрстка?»): у счёта сайта писали «1,7630 тал.» целиком —
  // плашка шире аватара и уезжала за край; теперь коротко — «1,8» (меньше 10 — с одной цифрой после запятой), «тал.» — в подсказке
  if (on) { $("#bal-t").textContent = c.site ? (c.empty ? "0" : balShort(c.balance, c.balance_text)) : pct + "%";
    b.title = b.ariaLabel = (c.empty ? "Талеры закончились" : c.site ? window.t("phone.bal.site", { b: c.balance_text || balShort(c.balance) }) : `Талеров осталось ${pct}%`) + " — пополнить"; }
}
/* Предупреждение заранее (0.82.1): один раз при ~30 % и один раз при ~10 % — Лира говорит, сколько примерно ответов осталось,
   и под фразой карточка с кнопкой «Пополнить» (и полями для контакта, если его ещё нет). Пополнили (≥ 50 %) — снова с начала. */
function payWarnCheck(c) {
  if (!c || c.site || c.frozen || c.empty || !S.llm.cloud || S.llm.account) return;
  const p = +c.percent || 0;
  if (p >= 50) { if (S.payWarn) { S.payWarn = 0; saveS(); } return; }
  const lvl = p <= 10 ? 10 : p <= 30 ? 30 : 0;
  if (!lvl || (S.payWarn && S.payWarn <= lvl)) return;
  S.payWarn = lvl; saveS();
  const n = +c.turns || 0, left = n ? `около ${n.toLocaleString("ru-RU")} ${turnsGen(n)}` : "совсем немного";
  const text = gfix((c.paid ? "Талеры заканчиваются" : "Подарок почти закончился") + ` — осталось ${left}. Пополнить можно кнопкой ниже.`);
  let k = 0;
  const run = () => { if ((busy || state !== "idle" || sayLeft > 0) && ++k < 120) { setTimeout(run, 1000); return; }
    plog("info", `☁ заряд ${p}% — предупредила (${lvl})`); showBot(text); showCard(payCardHtml(c, false)); payCardWire(); say(text); };
  setTimeout(run, 1500);
}
/* Карточка «Пополнить» под фразой Лиры: 402 (empty) или предупреждение; контакт — если его ещё не оставили (по желанию). */
function payCardHtml(c, empty) {
  const ask = !empty && S.autoJoined && !S.contactDone && !S.llm.account;     // при 402 главное — пополнить; контакт — в предупреждениях
  const n = +(c && c.turns) || 0;
  const sub = empty ? "Пополните — и я снова буду отвечать" : n ? `Осталось около ${n.toLocaleString("ru-RU")} ${turnsGen(n)}` : "Осталось совсем немного";
  return `<div class="card paycard${empty ? " empty" : ""}"><div class="pc-h"><span class="pc-ic"><svg viewBox="0 0 24 24"><rect x="3" y="6.5" width="18" height="12.5" rx="3"/><path d="M3 10.5h18M16.5 14.8h1.5"/><path d="M7 6.5 15.5 3.6a1.5 1.5 0 0 1 1.9 1l.6 1.9"/></svg></span>
    <div class="pc-t"><b>${empty ? "Пополнить талеры" : c && c.paid ? "Талеры заканчиваются" : "Подарок почти закончился"}</b><small>${esc(sub)}</small></div></div>
    <button class="btn p w" id="pc-go">Пополнить</button>${ask ? `<div class="pc-ct"><small>Контакт для разработчика — по желанию</small>
    <div class="row2"><input id="ct-contact" class="grname" maxlength="120" placeholder="Почта или Telegram" aria-label="Почта, Telegram или телефон"><button class="btn" id="ct-go">Сохранить</button></div></div>` : ""}</div>`;
}
/* Карточка под фразой: облик меньше (#stage.long), а прокрутка — к началу фразы Лиры (рецензия 04.11: «в самый низ» на
   360×780 прятало первую строку под «Нажмите или удерживайте»); не влезло всё — видна фраза и кнопка «Пополнить». */
function payCardWire() { const g = $("#pc-go"); if (g) g.onclick = openTopup; if ($("#ct-go")) contactWire();
  $("#stage").classList.add("long");
  requestAnimationFrame(() => requestAnimationFrame(() => { const t = $("#talk"), b = $("#bot"); if (!t || !b) return;
    t.scrollTop = Math.max(0, t.scrollTop + b.getBoundingClientRect().top - t.getBoundingClientRect().top - 6); })); }
async function cloudUsage() {
  try {
    const u = await cloudGet(cloudBase(), S.llm.api_key, "/usage"), days = u.days || [], mx = Math.max(1, ...days.map(d => d.answers));
    if (!$("#cl-use") || !days.length) return;
    $("#cl-use").innerHTML = `<div class="uh"><span>Две недели</span><span>${u.answers} ${turnsWord(u.answers)}</span></div><div class="ub">${days.map(d => `<i class="${d.answers ? "on" : ""}" style="height:${Math.max(6, d.answers / mx * 100)}%"></i>`).join("")}</div>`;
  } catch (e) { }
}
async function cloudBalance(force) {
  if (!S.llm.cloud) return null;
  if (!force && cloudInfo && Date.now() - cloudAt < 20000) return cloudInfo;
  const prev = cloudInfo;
  cloudInfo = await cloudGet(cloudBase(), S.llm.api_key, "/balance"); cloudAt = Date.now();
  if (prev && ((cloudInfo.low && !prev.low) || (cloudInfo.empty && !prev.empty)))          // один раз, когда стало мало; site — общий счёт с сайтом (вход аккаунтом)
    D.notify(cloudInfo.site ? (cloudInfo.empty ? "На счёте dewiar.pro закончились ИИ-талеры" : `На счёте dewiar.pro: ${cloudInfo.balance_text || cloudInfo.balance + " тал."}`)
      : cloudInfo.empty ? "Заряд Dewiar Облака закончился" : `Заряд Dewiar Облака: ${cloudInfo.percent}%`, cloudInfo.site ? "Пополнить — в личном кабинете на сайте" : "Настройки → Мозг → Пополнить");
  giftNote(cloudInfo); paidNote(cloudInfo); balBadge(cloudInfo); payWarnCheck(cloudInfo);
  return cloudInfo;
}
/* Подарок месяца пришёл (1.0.48, владелец 20.11: «при начислении сообщать… и что если не потратят, сгорит») — один раз
   за месяц, как на компьютере (cloud.gift_month_text). */
function giftNote(c) {
  const g = c && c.gift;
  if (!g || !(+g.left > 0) || !g.until || S.giftSeen === g.until) return;
  S.giftSeen = g.until; saveS();
  const u = new Date(g.until + "T12:00:00"), when = isNaN(u) ? "конца месяца" : u.toLocaleDateString("ru-RU", { day: "numeric", month: "long" });
  D.notify("Подарок месяца: " + String(+g.amount).replace(".", ",") + " талера", `Тратится первым; что не потратите до ${when}, сгорит — тогда же придёт новый.`);
}
/* Счёт пополнили (1.0.53, владелец 20.11: «как подарочные — и когда просто пополняет») — один тихий уведомлением: деньги
   дошли, сколько теперь. Первое знакомство (после обновления) — только запомнить: старое пополнение не новость. */
function paidNote(c) {
  if (!c || !("paid_last" in c)) return;
  const pl = c.paid_last, seen = S.paidSeen;
  if (!pl || !pl.ts) { if (seen === undefined) { S.paidSeen = 0; saveS(); } return; }
  if (seen === pl.ts) return;
  S.paidSeen = pl.ts; saveS();
  if (seen === undefined || Date.now() / 1000 - pl.ts > 3 * 86400) return;
  const n = (x) => String(Math.round(+x * 100) / 100).replace(".", ",");
  D.notify("Счёт пополнен: +" + n(pl.amount) + " тал.", "Теперь на счёте " + n(c.balance) + " тал." + (+c.turns > 0 ? ` — это примерно ${c.turns} ответов.` : ""));
}
/* Ключ Dewiar удалили или перевыпустили на сайте, а вход в аккаунт есть — не мучаем человека ошибкой: думаем по аккаунту. */
const keyGone = (m) => /ключ dewiar не найден|invalid_api_key|ключ отозван/i.test(String(m || ""));
async function fixDeadKey(msg) {
  if (!S.llm.cloud || S.llm.account || !loggedIn() || (msg !== undefined && !keyGone(msg))) return false;
  const sv = S.account.services || {};
  try { await cloudConnect(S.account.token, (S.accCloud && S.accCloud.base) || siteUrl(sv.cloud || "dwrapp/cloud.php"), { account: true }); }
  catch (e) { return false; }
  toast("Ключ Dewiar больше не действует — думаю по аккаунту " + (S.account.login || "dewiar.pro"), 4500);
  syncSoon();
  return true;
}
function forgetKey() {                          // «Забыть ключ»: есть аккаунт — думаем по нему, нет — мозг не подключён
  /* YouTube 27.10: «случайно нажал „Забыть ключ“ — не получается войти». Забытый ключ остаётся в «Прежних мозгах» (30 дней):
     вернуть — одной кнопкой «Вернуть»; убрать насовсем — корзиной там же. */
  if (S.llm.cloud && !S.llm.account && S.llm.api_key) {
    const keep = Object.assign({}, S.llm, { forgot: Date.now() });
    S.llmSaved = [keep].concat((S.llmSaved || []).filter(x => llmId(x) !== llmId(keep))).slice(0, 5);
  }
  if (loggedIn()) return fixDeadKey();
  // 0.82.1: «Забыть ключ» — значит, этот ключ не нужен: сами больше не подключаемся (раньше следующий вопрос подключал
  // новый ключ с новым подарком, а подтверждение говорило «не смогу отвечать»). Подключить снова — «Мозг», одной плиткой.
  S.forgotKey = Date.now();
  S.llm = Object.assign({}, DEF.llm); cloudInfo = null; S.accCloud = null;
  if (S.stt.engine === "server" && /cloud\.php/.test(S.stt.url || "") && !S.stt.from_account) S.stt = Object.assign({}, DEF.stt);
  saveS(); balBadge(null);
  return Promise.resolve(true);
}
const cloudWho = () => S.llm.account ? "по аккаунту " + (S.account.login || "") : "ключ …" + S.llm.api_key.slice(-4);
/* «около N …» — родительный падеж (рецензия 04.11: было «около 82 ответа»): «около 1 ответа», «около 82 ответов» */
const turnsGen = (n) => n % 10 === 1 && n % 100 !== 11 ? "ответа" : "ответов";
const turnsWord = (n) => { const a = n % 10, b = n % 100; return a === 1 && b !== 11 ? "ответ" : a >= 2 && a <= 4 && (b < 12 || b > 14) ? "ответа" : "ответов"; };
function cloudFill(c) {
  if (!c || !$("#cl-card")) return;
  const pct = Math.max(0, Math.min(100, c.percent || 0));
  $("#cl-card").className = "card cloudc" + (c.empty ? " empty" : c.low ? " low" : "");
  const bal = c.balance_text || (c.balance != null ? String(c.balance).replace(".", ",") + " тал." : "");
  $("#cl-pct").textContent = c.site ? bal : pct + "%"; $("#cl-fill").style.width = Math.max(pct, c.empty ? 0 : 2) + "%";
  $("#cl-sub").textContent = c.site ? "счёт dewiar.pro · " + (S.account.login || c.label || "") : S.llm.account ? cloudWho() : (c.label ? c.label + " · " : "") + cloudWho();
  $("#cl-turns").textContent = c.site ? (c.frozen ? "Доступ к ИИ на сайте приостановлен — напишите администратору." : c.empty ? "На счёте dewiar.pro закончились ИИ-талеры — пополните в личном кабинете."
      : `Общий счёт с сайтом: ${bal}` + (c.turns ? ` — примерно на ${c.turns.toLocaleString("ru-RU")} ${turnsWord(c.turns)}` : ""))
    : c.frozen ? "Ключ приостановлен — напишите администратору." : c.empty ? "Заряд закончился — пополните, и ассистент снова будет отвечать."
    : `Хватит примерно на ${c.turns.toLocaleString("ru-RU")} ${turnsWord(c.turns)}` + (c.low ? " — скоро понадобится пополнить" : "");
  const pt = (+c.per_taler) || (+c.balance > 0 && +c.turns > 0 ? Math.max(1, Math.round(c.turns / c.balance)) : 0);   // №542
  if ($("#cl-per")) $("#cl-per").textContent = (pt ? `1 талер ≈ ${pt.toLocaleString("ru-RU")} ${turnsWord(pt)} — длинные ответы и размышления дороже.` : "") + monthGiftLine(c);
  if (!c.empty && !c.frozen) $("#cl-turns").textContent += daysLine(c);
  limFill(c.limits); autoFill(c.autopay);
  if (c.pending) $("#cl-turns").textContent += " · " + pendingLine();     // №544/№545: заявка видна, со сроком
  clBal = +c.balance || 0;
  ymFill(c.yoomoney); cxFill(payPick(c.pay, "crypto")); payArrange(c.pay); clTopFill(c.topup, c.code, c.rub);
  if (typeof coPhoneFill === "function") coPhoneFill(c);          // «Компания»: кто платит, код от компании (23-company.js)
}
/* key — ключ dw-… или (account) токен входа на сайт: его регистр не трогаем. activate:false — только запомнить, своя модель остаётся. */
async function cloudConnect(key, base, opts = {}) {
  key = String(key || "").replace(/\s+/g, "").replace(/^[«"']|[»"']$/g, ""); base = (base || CLOUD_URL).split("?")[0];
  if (!opts.account) { key = key.toLowerCase(); if (!/^dw-/.test(key)) throw new Error("это не ключ Dewiar: он начинается с dw-. Вошли аккаунтом dewiar.pro — ключ не нужен"); }
  const info = await cloudGet(base, key, "/balance"), md = await cloudGet(base, key, "/models"), m = (md.data || [])[0];
  if (!m) throw new Error("в облаке пока нет доступных моделей — напишите администратору");
  if (opts.activate === false) { S.accCloud = { base, model: m.id, title: m.title || m.id, stt: !!md.stt, tts: !!md.tts }; saveS(); return info; }
  delete S.forgotKey;
  S.accCloud = opts.account ? { base, model: m.id, title: m.title || m.id, stt: !!md.stt, tts: !!md.tts } : null;
  S.llm = Object.assign({}, DEF.llm, { kind: "openai", name: "Dewiar Облако", base_url: base + "?p=", api_key: key, model: m.id, cloud: true, title: m.title || m.id,
    disable_thinking: false, account: !!opts.account, stt: !!md.stt, tts: !!md.tts });
  if (md.stt && !D.recognizer()) S.stt = { engine: "server", url: base + "?p=", key, model: "gigaam" };      // в телефоне нет своего распознавания
  if (!opts.account) S.sync = Object.assign({}, S.sync, { key });              // ключ — и для синхронизации: сменят мозг — синхронизация не пропадёт
  saveS(); cloudInfo = info; cloudAt = Date.now();
  if (S.refPending) setTimeout(refPendingUse, 500);            // пришли по приглашению — код введётся сам
  return info;
}

/* ---------- приглашения друзей (cloud.php ?p=/ref, /ref/use) ----------
   У каждого свой код и ссылка …/download.php?ref=КОД. Друг вводит код (или открывает ссылку → dewiar://ref?c=КОД) в первые
   дни — ему подарок сразу, вам — когда он попользуется облаком несколько дней. Код из ссылки, пока облако не подключено, ждёт
   в S.refPending и вводится сам после подключения (refPendingUse). */
let refInfo = null;
const talers = (x) => String(Math.round((+x || 0) * 100) / 100).replace(".", ",");
async function refLoad() {
  try { refInfo = await cloudGet(cloudBase(), S.llm.api_key, "/ref"); } catch (e) { return; }
  const d = refInfo, sub = $("#ref-sub"), more = $("#ref-more"); if (!sub || !more) return;
  sub.textContent = (d.bonus > 0 ? `Вам +${talers(d.bonus)} тал. за каждого, кто попользуется ${d.days} дн.` : "Поделитесь Dewiar с друзьями")
    + (d.bonus_new > 0 ? `, другу — +${talers(d.bonus_new)} сразу` : "") + ".";
  const list = d.invited || [];
  // всё о приглашённых — в «Близкие» → «Рефералы»; здесь — код, счёт и дорога туда
  more.innerHTML = `<button class="btn w refgo" id="ref-open" style="margin-top:10px"><span>Рефералы — созвездие и друзья</span><small>Мой код <b>${esc(d.code)}</b>${list.length ? ` · приглашено ${list.length}` + (d.earned > 0 ? `, получено ${talers(d.earned)} тал.` : "") : ""}</small></button>`;
  $("#ref-open").onclick = () => openRefs();
  refFresh(d);
}
function refFresh(d) {                       // новая золотая звезда с прошлого раза — звук «нашёл» и поздравление (один раз)
  let seen = []; try { seen = JSON.parse(localStorage.getItem("dw_refnet_seen") || "[]"); } catch (e) { }
  const fresh = (d.invited || []).filter(x => x.paid && !seen.includes(x.name + "|" + (x.since || ""))).length;
  if (!fresh) return;
  try { localStorage.setItem("dw_refnet_seen", JSON.stringify((d.invited || []).filter(x => x.paid).map(x => x.name + "|" + (x.since || "")).slice(-200))); } catch (e) { }
  try { scanChime(); } catch (e) { } toast(fresh === 1 ? "Ещё один друг засчитан — звезда загорелась!" : `Засчитано новых друзей: ${fresh}`, 3500);
}

/* «Близкие» → «Рефералы»: большое созвездие, ссылка и код, кто позвал вас и кого позвали вы. Первый уровень (в обе стороны):
   уже в «Близких» — «Написать» и «Позвонить»; нет — «Позвать в Близкие» (cloud.php ?p=/close/ref): друг увидит «… зовёт вас»
   и согласится или откажется. rid — знак связи от сервера (подделать нельзя). refMap — rid → {pid} | {offered}. */
let refMap = {}, refSel = null;
/* фото в созвездии (29.10, владелец: «чтобы и фото пользователя поддерживалось»): своё и тех, кто в «Близких» — тем же
   /close/face с кэшем, что и в списке; подгрузились новые — созвездие перерисовывается спокойно (без появления звёзд) */
const REF_IMG = {};
async function refImgs(d) {
  const st = clLoad(), want = [];
  if (st.me && st.me.pid && +st.me.face) want.push([st.me.pid, +st.me.face]);
  (d.invited || []).concat(d.by ? [d.by] : []).forEach(x => { const q = refPeer(x); if (q.pid && q.face) want.push([q.pid, q.face]); });
  let fresh = false;
  await Promise.all(want.filter(([pid]) => !REF_IMG[pid]).map(async ([pid, v]) => { const u = await clFace(pid, v); if (u) { REF_IMG[pid] = u; fresh = true; } }));
  if (fresh && refInfo === d && $("#rf-net")) refDraw(true);
}
async function refTab() {
  const box = $("#rf-body"); if (!box) return;
  if (!S.llm.cloud && !syncCred()) { box.innerHTML = `<div class="card"><b>Нужен Dewiar</b><p class="hint" style="margin:6px 0 10px">Приглашения работают через облако Dewiar: подключите мозг Dewiar или войдите аккаунтом dewiar.pro.</p><button class="btn p w" id="rf-brain">Подключить</button></div>`;
    $("#rf-brain").onclick = () => openSettings("brain"); return; }
  if (refInfo) refDraw(); else box.innerHTML = `<p class="hint" style="text-align:center;margin:30px 0">Загружаю созвездие…</p>`;
  try { refInfo = await cloudGet(cloudBase(), S.llm.api_key, "/ref"); } catch (e) { if (!refInfo) box.innerHTML = `<div class="card"><b>Не получилось</b><p class="hint" style="margin:4px 0 0">${esc(e.message)}</p></div>`; return; }
  const rids = (refInfo.invited || []).map(x => x.rid).concat(refInfo.by ? [refInfo.by.rid] : []).filter(Boolean);
  if (rids.length && syncCred()) { try { refMap = (await clReq("POST", "/close/refs", { rids })).map || {}; } catch (e) { } }
  if ($("#rf-body")) { refDraw(); refFresh(refInfo); }
}
function refPeer(x) {                         // друг в «Близких» — его имя оттуда и pid; иначе — как назвал сервер
  const m = (x && refMap[x.rid]) || {}, p = m.pid && clLoad().people.find(q => q.pid === m.pid);
  return { pid: p ? p.pid : "", name: p ? p.name : x.name, offered: !!m.offered, devs: p ? (p.devs || []).length : 0, face: p ? +p.face || 0 : 0 };
}
/* состояние приглашённого: засчитан; не засчитан (тот же интернет или устройство — защита от накруток); ждёт его
   первого пополнения или нового месяца (лимит наград); пробует Dewiar N из M дней */
const refState = (x) => x.paid ? "засчитан ✓" : x.why === "same" ? "не засчитан: тот же интернет или устройство" : x.why === "topup" ? "засчитается после его первого пополнения"
  : x.why === "cap" ? "засчитается в следующем месяце — лимит наград" : `пользуется ${+x.days || 0} из ${+x.need || 0} дн.`;
function refRow(x, key, sub) {
  const q = refPeer(x), col = window.DewiarRefNet ? DewiarRefNet.color(x.name) : clCol(x.name);   // цвет — как у звезды в созвездии
  const act = q.pid ? `<button class="ib soft" data-w="${esc(q.pid)}" title="Написать"><svg viewBox="0 0 24 24"><path d="M4 5.5h16v11H9l-5 4z"/></svg></button>`
      + (q.devs && window.DewiarCall ? `<button class="ib soft" data-c="${esc(q.pid)}" title="Позвонить"><svg viewBox="0 0 24 24"><path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2"/></svg></button>` : "")
    : q.offered ? `<em class="rfw">ждём ответа</em>` : `<button class="btn rfo" data-o="${esc(x.rid)}">Позвать в Близкие</button>`;
  return `<div class="rfp ${refSel === key ? "cur" : ""}" data-k="${key}"><i class="clava" style="--c:${col}"${q.pid && q.face ? ` data-face="${esc(q.pid)}" data-v="${q.face}"` : ""}>${esc((q.name || "?")[0].toUpperCase())}</i>
    <span><b>${esc(q.name)}</b><small>${sub}</small></span>${act}</div>`;
}
function refDraw(calm) {
  const d = refInfo, box = $("#rf-body"); if (!d || !box) return;
  if (calm === undefined) calm = !!$("#rf-net .rn");              // уже нарисовано — звёзды не появляются заново
  const list = d.invited || [];
  const rules = (d.bonus > 0 ? `Вам +${talers(d.bonus)} тал. за каждого друга, который попользуется Dewiar ${d.days} дн.` : "Поделитесь Dewiar с друзьями.")
    + (d.bonus_new > 0 ? ` Другу — +${talers(d.bonus_new)} тал. сразу.` : "");
  box.innerHTML = `<div id="rf-net" class="rfnet"></div>
    <div class="card rfinv"><div class="row2 rfcb"><div style="flex:1;min-width:0"><small class="hint" style="margin:0">Ваш код</small><b class="rfcode">${esc(d.code)}</b></div>
      <button class="ib soft" id="rf-copy" title="Скопировать ссылку"><svg viewBox="0 0 24 24"><rect x="8.5" y="8.5" width="12" height="12" rx="2.5"/><path d="M15.5 8.5V6a2.5 2.5 0 0 0-2.5-2.5H6A2.5 2.5 0 0 0 3.5 6v7A2.5 2.5 0 0 0 6 15.5h2.5"/></svg></button></div>
      <button class="btn p w" id="rf-share" style="margin-top:10px">Пригласить</button>
      <p class="hint" style="margin:8px 0 0">${esc(rules)}</p></div>
    ${d.by ? `<h3>Вас пригласил</h3>${refRow(d.by, "by", "с этого приглашения вы в Dewiar")}` : ""}
    <h3>Приглашённые${list.length ? ` · ${list.length}` : ""}</h3>
    ${list.length ? list.map((x, i) => refRow(x, i, refState(x) + (x.sub ? ` · позвал ещё ${x.sub}` : ""))).join("")
      : `<div class="card"><b>Пока никого</b><p class="hint" style="margin:4px 0 0">${esc(refEmpty(d))}</p></div>`}
    ${list.length && d.opened > list.length ? `<p class="hint" style="margin:6px 4px 0">${esc(refOpened(d))}</p>` : ""}
    <p class="hint" style="margin:10px 4px">Переписываться и созваниваться можно с теми, кого пригласили вы, и с тем, кто пригласил вас, — когда оба согласны: «Позвать в Близкие».</p>
    ${d.can_use ? `<details class="more" style="margin:4px 2px 0"><summary>Есть код приглашения?</summary><div class="row2" style="margin-top:6px"><input id="ref-code" placeholder="6 знаков" autocapitalize="characters" style="flex:1;padding:12px 14px;border-radius:14px;border:0;background:var(--field)"><button class="btn p" id="ref-use">Ввести</button></div><div class="res" id="ref-res"></div></details>` : ""}`;
  if (window.DewiarRefNet) {
    const st = clLoad(), me = st.me || {}, img = (pid) => pid && REF_IMG[pid] || "";
    const net = Object.assign({}, d, { invited: list.map(x => { const q = refPeer(x); return Object.assign({}, x, { label: q.name, close: q.pid, img: img(q.pid) }); }) });
    DewiarRefNet.render($("#rf-net"), net, { big: true, calm, light: document.body.classList.contains("light"), meImg: img(me.pid), byImg: d.by ? img(refPeer(d.by).pid) : "", me: (S.user_name || "Вы").slice(0, 7), by: d.by ? refPeer(d.by).name : "", sel: refSel,
      seenKey: "dw_refnet_seen_big", onPick: (i) => { refSel = refSel === i ? null : i; refDraw(true); const r = $(`.rfp[data-k="${i}"]`); if (r) r.scrollIntoView({ block: "nearest", behavior: "smooth" }); } });
  }
  clFacesFill(box); refImgs(d);
  $$(".rfp").forEach(r => r.onclick = (e) => { if (e.target.closest("button")) return; const k = r.dataset.k === "by" ? "by" : +r.dataset.k; refSel = refSel === k ? null : k; refDraw(true); });
  $$(".rfp [data-w]").forEach(b => b.onclick = () => { clTab = "close"; clCur = b.dataset.w; clRender(); });
  $$(".rfp [data-c]").forEach(b => b.onclick = () => clCall(b.dataset.c, false).catch(e => toast(e.message, 4000)));
  $$(".rfp [data-o]").forEach(b => b.onclick = async () => { b.disabled = true;
    try { clKeys(); if (!clLoad().me.pid) await clHello(); const r = await clReq("POST", "/close/ref", { rid: b.dataset.o });
      if (r.person) { clPeople(r); refMap[b.dataset.o] = { pid: r.person.pid }; toast(`${r.person.name} — в ваших близких: можно писать и звонить`, 3500); }
      else { refMap[b.dataset.o] = { offered: true }; toast("Позвали — когда друг согласится, он появится в «Близких»", 3500); }
      refDraw(true); } catch (e) { b.disabled = false; toast(e.message, 4000); } });
  $("#rf-share").onclick = () => refShare().catch(e => toast(e.message));
  $("#rf-copy").onclick = () => { D.copy(d.link); toast("Ссылка скопирована"); };
  if ($("#ref-use")) $("#ref-use").onclick = async () => { const r = $("#ref-res"); r.className = "res"; r.textContent = "проверяю…";
    try { const u = await refUse($("#ref-code").value); r.className = "res ok"; r.textContent = u.gift > 0 ? `Готово — вам +${talers(u.gift)} тал.` : "Готово — код принят."; cloudBalance(true).then(cloudFill).catch(() => { }); refInfo = null; setTimeout(refTab, 1500); }
    catch (e) { r.className = "res bad"; r.textContent = e.message; } };
}
/* «ссылку открыли» — сколько разных людей открыли страницу приглашения (сервер считает сам; превью мессенджеров — нет).
   Друг, который ставит Dewiar с того же телефона и входит, засчитывается без кода (cloud.php ref_auto). */
const refHow = (d) => `Кто поставит Dewiar с того же телефона и войдёт, появится здесь сам; ставят на компьютер или в другой сети — пусть введут код ${d.code}.`;
const refPeople = (n) => n + (n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20) ? " человека" : " человек");
const refOpened = (d) => `Ссылку открыли ${refPeople(+d.opened || 0)}. ` + refHow(d);
const refEmpty = (d) => d.opened > 0 ? `Ссылку открыли ${refPeople(+d.opened)}, но Dewiar по ней пока никто не подключил. ` + refHow(d)
  : "Нажмите «Пригласить» — ссылка с вашим кодом уйдёт в любой мессенджер. Друг, который поставит Dewiar по ней, появится здесь сам; каждый засчитанный — новая звезда.";
const refShareText = (d) => `Попробуй Dewiar — помощницу Лиру для телефона и компьютера: слышит по имени, отвечает голосом, помнит и напоминает. ${d.link}\nКод приглашения: ${d.code}`;
async function refShare() {
  const d = refInfo || await cloudGet(cloudBase(), S.llm.api_key, "/ref"); refInfo = d;
  D.share(refShareText(d));
}
async function refUse(code) {
  code = String(code || "").toUpperCase().replace(/[^A-Z0-9]/g, "");
  if (code.length < 4) throw new Error("Введите код из приглашения — 6 букв и цифр.");
  const u = await cloudPost("/ref/use", { code }); S.refPending = ""; saveS(); return u;
}
async function refPendingUse() {
  if (!S.refPending || !S.llm.cloud) return;
  try { const u = await refUse(S.refPending); if (u.gift > 0) { showBot(`Код приглашения принят — вам подарок +${talers(u.gift)} тал.`); } }
  catch (e) { if (!/сети|интернет|network/i.test(e.message)) { S.refPending = ""; saveS(); } }
}

/* ---------- аккаунт dewiar.pro: вход логином сайта, модели по аккаунту, Знания ----------
   Вход — dwrapp/login.php (выдаёт токен и список услуг services: cloud, stt…; приложение называет себя X-App-Id),
   Знания — synapbase/api_rag и api_scope. Пароль не хранится — только токен; 401 — вход устарел (accountExpired). */
const SITE = window.DEWIAR_SITE || "https://dewiar.pro", APP_ID = "dewiar-app";
const YANDEX_CID = "bd46169129964deea1f608cf45f7122a";   // приложение «Dewiar» на oauth.yandex.ru (iot:view, iot:control) — как в core/smarthome.py
const loggedIn = () => !!(S.account && S.account.token);
const siteHost = () => (S.account.server || SITE).replace(/^https?:\/\//, "");
function siteAddr(a) {
  a = String(a || "").trim().replace(/\/+$/, ""); if (!a) return SITE;
  if (!/^https?:\/\//.test(a)) a = "https://" + a;
  if (/^http:\/\//.test(a) && !/^http:\/\/(127\.|10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|localhost)/.test(a)) throw new Error("нужен адрес с https:// — иначе пароль ушёл бы открытым");
  return a;
}
const siteUrl = (p) => /^https?:/.test(p || "") ? p : (S.account.server || SITE) + "/" + String(p || "").replace(/^\/+/, "");
const siteHeaders = () => ({ "Content-Type": "application/json", "X-App-Id": APP_ID, Authorization: "Bearer " + S.account.token });
function accountExpired() {
  S.account = Object.assign({}, DEF.account, { server: S.account.server, login: S.account.login, problem: "Вход устарел — войдите в аккаунт заново (Настройки → Мозг)." });
  scopeCache = null; saveS();
}
function siteParse(r) {
  let d = {}; try { d = JSON.parse(r.body || "{}"); } catch (e) { if (r.status === 200) throw new Error("сайт ответил непонятно"); }
  if (r.status === 401) { accountExpired(); throw new Error("вход в аккаунт устарел — войдите заново: Настройки → Мозг"); }
  if (r.status === 429) throw new Error("слишком много вопросов подряд — сайт просит подождать");
  if (r.status !== 200) throw new Error((d.error && (d.error.message || d.error)) || "сайт ответил " + r.status);
  return d;
}
async function accountLogin(server, login, password) {
  server = siteAddr(server); login = String(login || "").trim();
  if (!login || !password) throw new Error("введите логин и пароль");
  applyProxy([server]);
  let r;
  try { r = await http("POST", server + "/dwrapp/login.php", { headers: { "Content-Type": "application/json", "X-App-Id": APP_ID }, body: { login, password }, timeout: 20000 }); }
  catch (e) { throw new Error(e.message + "." + blockedHint()); }
  let d = {}; try { d = JSON.parse(r.body || "{}"); } catch (e) { }
  if (r.status === 403 && /API-токен/.test(d.error || ""))     // старый login.php сайта не выдаёт токен сам — есть путь без него
    throw new Error("у этого аккаунта пока нет доступа для приложения (API-токена). Можно без него: «Мозг» → «Попробовать Dewiar» — "
      + "заявка, ключ придёт сам. Или попросите администратора сайта выдать токен");
  if (r.status !== 200 || !d.ok || !d.token)
    throw new Error(d.error || ({ 401: "неверный логин или пароль", 404: "на сайте нет входа для приложения (dwrapp/login.php)", 429: "слишком много попыток — подождите 15 минут" }[r.status] || "сайт ответил " + r.status));
  const sv = d.services || {};
  S.account = { server, login: (d.user && d.user.login) || login, token: d.token, user: d.user || {}, rag_url: d.rag_url || "/synapbase/api_rag", services: sv, problem: "", since: Date.now() };
  scopeCache = null; saveS();
  const out = { login: S.account.login, cloud: null, activated: false };
  trialOff();                                      // вошли — пробный разговор больше не нужен
  let ownKey = S.llm.cloud && !S.llm.account;
  const mine = !!S.llm.base_url && !S.llm.cloud;
  if (ownKey) {                                    // свой ключ dw- ещё действует? Удалённый на сайте — не держимся за него
    try { await cloudGet(cloudBase(), S.llm.api_key, "/balance"); } catch (e) { if (keyGone(e.message)) ownKey = false; }
  }
  // облако по аккаунту: свой рабочий ключ dw-… и своя модель остаются, облако — запасом. Адрес — из services, а если
  // сайт его не назвал (старый login.php) — обычный dwrapp/cloud.php; не ответило — ещё раз (первый запрос бывает долгим)
  for (let i = 0; i < 2 && !out.cloud; i++) {
    try { out.cloud = await cloudConnect(d.token, siteUrl(sv.cloud || "dwrapp/cloud.php"), { account: true, activate: !mine && !ownKey }); out.activated = !mine && !ownKey; }
    catch (e) { plog("warn", "облако по аккаунту: " + e.message); if (i) out.cloud = { error: e.message }; }
  }
  if (sv.stt && !D.recognizer() && S.stt.engine !== "server") S.stt = { engine: "server", url: siteUrl(sv.stt), key: d.token, model: "", from_account: true };
  saveS(); applyPersona();
  return out;
}
function accountLogout() {
  if (S.llm.cloud && S.llm.account) { S.llm = Object.assign({}, DEF.llm); cloudInfo = null; }
  if (S.stt.from_account) S.stt = Object.assign({}, DEF.stt);
  S.account = Object.assign({}, DEF.account, { server: S.account.server && S.account.server !== SITE ? S.account.server : "" });
  S.accCloud = null; scopeCache = null; saveS(); $("#who").classList.remove("low");
}
async function accountCheck() {                    // при запуске: вход ещё действует?
  if (!loggedIn()) return;
  try {
    const r = await http("GET", S.account.server + "/dwrapp/login.php", { headers: siteHeaders(), timeout: 15000 });
    if (r.status === 401) { accountExpired(); if (S.llm.account) toast("Вход в аккаунт dewiar.pro устарел — войдите заново", 4000); return; }
    if (r.status === 200) { const d = JSON.parse(r.body || "{}"); if (d.user) S.account.user = d.user; if (d.services) S.account.services = d.services; S.account.problem = ""; saveS(); }
  } catch (e) { }
  if (S.llm.cloud && !S.llm.account && loggedIn()) {        // свой ключ dw- удалили на сайте — сразу по аккаунту, без ошибок в разговоре
    try { await cloudGet(cloudBase(), S.llm.api_key, "/balance"); } catch (e) { await fixDeadKey(e.message); }
  }
}

/* базы сайта: свои папки, публичные библиотеки и их разделы */
let scopeCache = null;
const ragUrl = () => siteUrl(S.account.rag_url || "/synapbase/api_rag");
const scopeUrl = () => ragUrl().replace(/api_rag(\.php)?(?=$|\?)/, (m0, ext) => "api_scope" + (ext || ""));
async function siteScope(force) {
  if (!loggedIn()) throw new Error("нужен вход в аккаунт dewiar.pro: Настройки → Мозг");
  if (!force && scopeCache && Date.now() - scopeCache.t < 300000) return scopeCache.v;
  const d = siteParse(await http("POST", scopeUrl(), { headers: siteHeaders(), body: {}, timeout: 20000 }));
  const bases = [];
  for (const f of d.folders || []) bases.push({ kind: "folder", id: String(f.id), label: f.name || "Папка", docs: +f.doc_count || 0, group: "Мои папки" });
  for (const lib of d.libraries || []) {
    const lab = lib.label || "Публичная библиотека";
    bases.push({ kind: "library", id: String(lib.id), label: lab, docs: +lib.doc_count || 0, group: lab, whole: true });
    for (const f of lib.folders || []) bases.push({ kind: "library_folder", id: String(f.id), lib: String(lib.id), label: f.name || "Раздел", docs: +f.doc_count || 0, group: lab });
  }
  scopeCache = { t: Date.now(), v: { bases, docs: (d.docs || []).length } };
  return scopeCache.v;
}
const numId = (x) => /^\d+$/.test(String(x)) ? +x : x;
function ragOptions(b) {
  if (!b) return {};
  if (b.kind === "folder") return { bd_id: b.id };
  if (b.kind === "doc") return { doc_id: b.id };
  if (b.kind === "library") return { library_id: numId(b.id) };
  if (b.kind === "library_folder") { const o = { library_bd_id: b.id }; if (b.lib) o.library_id = numId(b.lib); return o; }
  return {};
}
function ragSources(meta, limit = 6) {
  const out = [];
  const walk = (x, depth) => {
    if (depth > 6 || out.length >= limit || !x) return;
    if (Array.isArray(x)) { x.forEach(v => walk(v, depth + 1)); return; }
    if (typeof x !== "object") return;
    const k = ["title", "doc_name", "document", "filename", "file_name", "name", "source"].find(k => typeof x[k] === "string" && x[k].trim());
    if (k && x[k].length < 200 && !out.includes(x[k].trim())) out.push(x[k].trim());
    Object.values(x).forEach(v => walk(v, depth + 1));
  };
  walk(meta, 0); return out;
}
function ragImages(d, limit = 4) {
  const out = [], base = (S.account.server || SITE).replace(/\/+$/, ""), rx = /\.(jpe?g|png|gif|webp)(\?|#|$)/i;
  const url = (p) => {
    p = String(p || "").trim().replace(/\\/g, "/"); if (!p) return "";
    const i = p.indexOf("user_uploads/"); if (i > 0) p = p.slice(i);
    if (/^https?:/.test(p)) return p;
    if (!/^(\/|user_uploads\/)/.test(p)) return "";
    return base + "/" + p.replace(/^\/+/, "");
  };
  const add = (u, title) => { if (u && !out.some(x => x.url === u)) out.push({ url: u, title: title || "" }); };
  for (const a of d.media_anchors || []) if (a && (a.media_type === "image" || rx.test(String(a.media_url || "")))) add(url(a.media_url || a.embed_url), a.title || a.description);
  const docs = (d.rag_meta || {}).retrieved_docs;
  for (const x of Array.isArray(docs) ? docs : []) {
    if (!x || typeof x !== "object") continue;
    const k = ["meta_path", "image_url", "media_url", "img_url", "image_path", "visual_path"].find(k => typeof x[k] === "string" && rx.test(x[k]));
    if (k) add(url(x[k]), x.name || x.doc_name);
  }
  return out.slice(0, limit);
}
async function ragRetrieve(question, b, hist) {
  const msgs = (hist || []).slice(-4).concat([{ role: "user", content: question }]);
  const d = siteParse(await http("POST", ragUrl(), { headers: siteHeaders(), timeout: 60000,
    body: { messages: msgs, stream: false, _sid: APP_ID, rag_options: Object.assign(ragOptions(b), { response_mode: "retrieval_only", history_depth: 4 }) } }));
  const ctx = String(d.ready_to_use_context || "").trim(), ans = (((d.choices || [])[0] || {}).message || {}).content || "";
  const found = !!ctx && !/ДАННЫЕ_НЕ_НАЙДЕНЫ/.test(ans);
  return { context: found ? ctx : "", sources: ragSources(d.rag_meta), images: ragImages(d), found };
}
const kbOf = (pid) => (S.kb || {})[pid || persona().id] || [];
/* У персонажа подключены базы сайта — ищем в них по вопросу и даём модели найденное (как на компьютере). */
async function personaKnowledge(text) {
  const bases = kbOf(), q = String(text || "").trim();
  if (!bases.length || !loggedIn() || q.length < 3) return "";
  const labels = bases.map(b => `«${b.label}»`).join(", ");
  showBot(`Ищу в ${labels}`, "wait");
  const hist = history.slice(-4).filter(m => (m.role === "user" || m.role === "assistant") && typeof m.content === "string").map(m => ({ role: m.role, content: m.content }));
  const got = await Promise.all(bases.map(b => ragRetrieve(q, b, hist).then(r => ({ b, r }), e => ({ b, err: e.message }))));
  const parts = [], empty = [], errs = [], srcs = []; let images = [];
  const per = Math.max(1500, Math.floor(7000 / bases.length));
  for (const { b, r, err } of got) {
    if (err) errs.push(`«${b.label}»: ${err}`);
    else if (r.found) { parts.push(`### Из «${b.label}»\n${r.context.slice(0, per)}`); images = images.concat(r.images); srcs.push(...r.sources); }
    else empty.push(`«${b.label}»`);
  }
  if (images.length) showImages(images);
  let out = "";
  if (parts.length) {
    out = "\n\nТВОЯ БАЗА ЗНАНИЙ (сайт Dewiar) — найдено по вопросу пользователя. Отвечай, опираясь на это: где уместно, приводи дословные цитаты "
      + "и называй источник (книга, глава и стих — или документ и страница). Не выдумывай того, чего в найденном нет; если найденное не отвечает "
      + "на вопрос — скажи об этом честно и бережно ответь от себя.\n\n" + parts.join("\n\n");
    if (srcs.length) out += "\n\nИсточники: " + [...new Set(srcs)].join("; ");
  } else if (empty.length) out = `\n\nВ твоей базе знаний (${empty.join(", ")}) по этому вопросу ничего не нашлось. Если отвечаешь от себя — так и скажи одной фразой.`;
  if (errs.length && !parts.length) out += `\n\nБаза знаний сейчас недоступна (${errs[0]}). Ответь от себя и коротко скажи, что база не ответила.`;
  return out;
}
function showImages(list) {
  showCard(`<div class="kbimgs">${list.map((x, i) => `<button class="kbimg" data-i="${i}" title="${esc(x.title)}"><img src="${esc(x.url)}" alt="" loading="lazy" onerror="this.parentNode.remove()"></button>`).join("")}</div>`);
  $$("#card .kbimg").forEach(b => b.onclick = () => D.openUrl(list[+b.dataset.i].url));
}
/* инструмент: вопрос к Знаниям сайта целиком (ответ пишет сайт) */
async function askKnowledge(question, baseName) {
  if (!loggedIn()) return "Нужен вход в аккаунт dewiar.pro (Настройки → Мозг → Аккаунт).";
  let b = null;
  if (baseName) {
    const want = baseName.toLowerCase().replace(/ё/g, "е").slice(0, 6);
    try { b = (await siteScope()).bases.find(x => x.label.toLowerCase().replace(/ё/g, "е").includes(want)) || null; } catch (e) { }
  }
  const body = { messages: [{ role: "user", content: question }], stream: false, _sid: APP_ID };
  if (b) body.rag_options = ragOptions(b);
  const d = siteParse(await http("POST", ragUrl(), { headers: siteHeaders(), body, timeout: 150000 }));
  const ans = ((((d.choices || [])[0] || {}).message || {}).content || "").trim();
  const imgs = ragImages(d); if (imgs.length) showImages(imgs);
  const src = ragSources(d.rag_meta);
  return (ans || "В Знаниях ничего не нашлось.") + (src.length ? "\n\nИсточники: " + src.join("; ") : "");
}

/* Знания персонажа — в листе «Кто отвечает» */
/* Редактор своего персонажа (лист #sh-pedit): облик из галереи — квадрат 384×384 по центру (JPEG ~40 КБ, хранится здесь же). */
const PE_COLORS = ["#9BD4FF", "#FF9BC8", "#B79BFF", "#7FE0B0", "#FFC46B", "#FF8A7A"];
let peAvatar = "";
function personaEditor(id) {
  const x = myPersonas().find(v => v.id === id) || { id: "", name: "", gender: "female", role: "", about: "", color: PE_COLORS[myPersonas().length % PE_COLORS.length], avatar: "" };
  peAvatar = x.avatar || "";
  $("#pe-h").textContent = x.id ? `Персонаж: ${x.name}` : "Свой персонаж";
  $("#pe-body").innerHTML = `<div class="card pe">
      <div class="pe-top"><label class="pe-ava" title="Облик: фото из галереи"><input type="file" id="pe-file" accept="image/*" hidden><span id="pe-img"></span><small>Облик</small></label>
        <div style="flex:1;min-width:0"><label class="f"><span>Имя — на него откликается</span><input id="pe-name" maxlength="24" value="${esc(x.name)}" placeholder="например, Меган" autocapitalize="words"></label>
        <div class="seg" id="pe-g"><button data-g="female" class="${x.gender === "female" ? "on" : ""}">Она</button><button data-g="male" class="${x.gender !== "female" ? "on" : ""}">Он</button></div></div></div>
      <label class="f"><span>Кто это — одной строкой</span><input id="pe-role" maxlength="60" value="${esc(x.role || "")}" placeholder="подруга, тренер по английскому, бизнес-советник"></label>
      <label class="f"><span>Характер и как говорит</span><textarea id="pe-about" rows="4" maxlength="1200" placeholder="Весёлая, отвечает коротко, любит шутить; разбирается в фитнесе и питании. Обращается на «ты».">${esc(x.about || "")}</textarea></label>
      <div class="pe-colors" id="pe-c">${PE_COLORS.map(c => `<button data-c="${c}" style="--c:${c}" class="${c === x.color ? "on" : ""}" aria-label="Цвет ${c}"></button>`).join("")}</div>
      <p class="hint" style="margin:6px 0 10px">Облик, имя и характер — на этом телефоне; с синхронизацией — и на компьютере. Голос — по полу: женский или мужской.</p>
      <button class="btn p w" id="pe-save">Сохранить</button>
      <button class="btn w" id="pe-kb" style="margin-top:8px">Знания: документы для ответов</button>
      ${x.id ? `<button class="btn w" id="pe-del" style="margin-top:8px">Удалить персонажа</button>` : ""}
      <div class="res" id="pe-res"></div></div>`;
  const showAva = () => { $("#pe-img").innerHTML = peAvatar ? `<img src="${peAvatar}" alt="">` : `<i>+</i>`; };
  showAva();
  $$("#pe-g button").forEach(b => b.onclick = () => $$("#pe-g button").forEach(z => z.classList.toggle("on", z === b)));
  $$("#pe-c button").forEach(b => b.onclick = () => $$("#pe-c button").forEach(z => z.classList.toggle("on", z === b)));
  $("#pe-file").onchange = async (ev) => {
    const f = ev.target.files && ev.target.files[0]; if (!f) return;
    try { peAvatar = await squareAvatar(f, 384); showAva(); } catch (e) { $("#pe-res").className = "res bad"; $("#pe-res").textContent = "Фото не открылось: " + e.message; }
  };
  /* 28.11 (человек на скриншоте: «добавить базу данных» в «Своём персонаже»): знания — тем же листом «Кто отвечает»,
     но отсюда одной кнопкой: сохранить персонажа и сразу открыть выбор его баз */
  $("#pe-kb").onclick = () => { if (!save(true)) return; $("#who").click();
    setTimeout(() => { const k = $("#pkb"); if (k) k.scrollIntoView({ block: "start", behavior: "smooth" }); if ($("#kb-edit")) kbPicker(S.persona); }, 350); };
  $("#pe-save").onclick = () => save(false);
  function save(quiet) {
    const name = $("#pe-name").value.trim().replace(/\s+/g, " "), r = $("#pe-res");
    if (!/^[A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё -]{1,23}$/.test(name)) { r.className = "res bad"; r.textContent = "Имя — буквами, от двух до 24: на него персонаж будет откликаться."; return false; }
    const clash = PERSONAS.find(p => p.id !== x.id && p.name.toLowerCase().replace(/ё/g, "е") === name.toLowerCase().replace(/ё/g, "е"));
    if (clash) { r.className = "res bad"; r.textContent = `Имя «${clash.name}» уже занято — выберите другое.`; return false; }
    const v = { id: x.id || uid("u"), name, gender: ($("#pe-g .on") || {}).dataset ? $("#pe-g .on").dataset.g : "female",
      role: $("#pe-role").value.trim(), about: $("#pe-about").value.trim(), color: ($("#pe-c .on") || { dataset: { c: PE_COLORS[0] } }).dataset.c, avatar: peAvatar };
    const l = myPersonas().filter(q => q.id !== v.id); l.push(v);
    try { prefSet("my_personas", JSON.stringify(l)); } catch (e) { r.className = "res bad"; r.textContent = "Не сохранилось: " + e.message; return false; }
    myPersonasApply(); S.persona = v.id; saveS(); applyPersona(); closeSheets(); syncSoon();
    showYou(""); showBot(`${v.name} — с вами. Зовите по имени.`); if (!quiet) say(gfix(`Привет! Это ${v.name}.`));
    return true;
  }
  if ($("#pe-del")) $("#pe-del").onclick = () => {
    if (!confirm(`Удалить персонажа «${x.name}»? Разговор и заметки останутся.`)) return;
    prefSet("my_personas", JSON.stringify(myPersonas().filter(q => q.id !== x.id)));
    myPersonasApply(); if (S.persona === x.id) { S.persona = PERSONAS[0].id; saveS(); applyPersona(); }
    closeSheets(); toast(`«${x.name}» удалён`); syncSoon();
  };
  openSheet("#sh-pedit");
}
// фото из галереи → квадрат size×size по центру (как облик), JPEG
function squareAvatar(file, size) {
  return new Promise((ok, bad) => {
    const u = URL.createObjectURL(file), im = new Image();
    im.onload = () => {
      const s = Math.min(im.naturalWidth, im.naturalHeight); if (!s) { bad(new Error("пустая картинка")); return; }
      const c = document.createElement("canvas"); c.width = c.height = size;
      // лицо обычно в верхней трети портрета — для высоких снимков берём квадрат чуть выше центра
      const sx = (im.naturalWidth - s) / 2, sy = im.naturalHeight > im.naturalWidth ? Math.max(0, (im.naturalHeight - s) * 0.3) : (im.naturalHeight - s) / 2;
      c.getContext("2d").drawImage(im, sx, sy, s, s, 0, 0, size, size);
      URL.revokeObjectURL(u); ok(c.toDataURL("image/jpeg", 0.86));
    };
    im.onerror = () => { URL.revokeObjectURL(u); bad(new Error("не картинка")); };
    im.src = u;
  });
}
function renderKbPanel() {
  const box = $("#pkb"); if (!box) return;
  const p = persona(), mine = kbOf(p.id);
  if (!loggedIn()) {
    box.innerHTML = `<div class="card kbc"><b>Знания персонажа</b><p class="hint" style="margin:6px 0 10px">Персонажу можно дать базы с сайта dewiar.pro — свои папки или раздел публичной библиотеки, например «Библию». Тогда он отвечает по источнику, с цитатами.</p>
      <button class="btn w" id="kb-login">Войти в аккаунт dewiar.pro</button></div>`;
    $("#kb-login").onclick = () => { openSettings("brain"); setTimeout(() => { const t = $('.tile[data-w="account"]'); if (t) t.click(); }, 250); };
    return;
  }
  box.innerHTML = `<div class="card kbc"><div class="row2"><div style="flex:1;min-width:0"><b>Знания · ${esc(p.name)}</b><small class="hint" style="margin:2px 0 0;display:block">${mine.length ? "Перед ответом ищет здесь" : "Базы сайта не подключены"}</small></div>
    <button class="btn" id="kb-edit">${mine.length ? "Изменить" : "Подключить"}</button></div>
    ${mine.length ? `<div class="chips">${mine.map(b => `<span class="chip">${esc(b.label)}</span>`).join("")}</div>` : ""}<div id="kb-pick"></div></div>`;
  $("#kb-edit").onclick = () => kbPicker(p.id);
}
async function kbPicker(pid) {
  const el = $("#kb-pick"); el.innerHTML = `<p class="hint">загружаю базы сайта…</p>`;
  let bases;
  try { bases = (await siteScope(true)).bases; } catch (e) { el.innerHTML = `<div class="res bad">${esc(e.message)}</div>`; return; }
  if (!bases.length) { el.innerHTML = `<p class="hint">На сайте пока нет ваших папок и публичных библиотек. Загрузите документы на dewiar.pro — и они появятся здесь.</p>`; return; }
  const key = (b) => b.kind + ":" + b.id, sel = new Set(kbOf(pid).map(key));
  const groups = []; for (const b of bases) { let g = groups.find(x => x.name === b.group); if (!g) groups.push(g = { name: b.group, items: [] }); g.items.push(b); }
  el.innerHTML = groups.map(g => `<div class="kbg">${esc(g.name)}</div>` + g.items.map(b => `<label class="kbi"><input type="checkbox" value="${esc(key(b))}" ${sel.has(key(b)) ? "checked" : ""}>
    <span>${esc(b.whole ? "Вся библиотека" : b.label)}</span><small>${+b.docs || 0} док.</small></label>`).join("")).join("")
    + `<p class="hint" style="margin:8px 0 0">До 6 баз. Чем точнее раздел, тем точнее ответы.</p>`;
  $$("input", el).forEach(i => i.onchange = () => {
    const on = $$("input:checked", el).map(x => x.value);
    if (on.length > 6) { i.checked = false; toast("Не больше 6 баз у одного персонажа"); return; }
    S.kb = S.kb || {}; S.kb[pid] = bases.filter(b => on.includes(key(b))).map(b => { const o = { kind: b.kind, id: b.id, label: b.whole ? b.group : b.label }; if (b.lib) o.lib = b.lib; return o; });
    saveS();
    const chips = $(".kbc .chips"), mine = S.kb[pid];
    $(".kbc .hint").textContent = mine.length ? "Перед ответом ищет здесь" : "Базы сайта не подключены";
    $("#kb-edit").textContent = mine.length ? "Изменить" : "Подключить";
    if (chips) chips.innerHTML = mine.map(b => `<span class="chip">${esc(b.label)}</span>`).join("");
    else if (mine.length) $(".kbc .row2").insertAdjacentHTML("afterend", `<div class="chips">${mine.map(b => `<span class="chip">${esc(b.label)}</span>`).join("")}</div>`);
  });
}

/* ---------- Telegram: общий бот Dewiar (dwrapp/tg.php на сайте, вход — аккаунтом) ----------
   Подключение — как на компьютере: телефон регистрирует код (setLinkCode) и открывает ссылку t.me/<бот>?start=<код>;
   кто нажал «Старт» — тот владелец. Компьютера нет — бот отвечает сам моделями Dewiar (заметки, списки, напоминания;
   сделанное приходит на телефон синхронизацией): для этого телефон отдаёт ему ключ и персонажа (dewiarSync с
   device=phone — «компьютер на связи» он не отмечает). Есть компьютер — главный он, телефон его настройки не трогает. */
const tgOn = () => loggedIn() && !!(S.account.services || {}).tg;
/* Имя общего бота Dewiar — с сайта (dwrapp/tg.php?health, без входа): кнопка «Открыть бота» на телефоне. */
let tgBotCache = null;
async function tgBotName() {
  if (tgBotCache !== null) return tgBotCache;
  const r = await http("GET", (loggedIn() ? siteUrl("dwrapp/tg.php") : CLOUD_URL.replace(/cloud\.php.*$/, "tg.php")) + "?health", { timeout: 10000 });
  let d = {}; try { d = JSON.parse(r.body || "{}"); } catch (e) { }
  tgBotCache = String(d.bot || "").replace(/^@/, "");
  return tgBotCache;
}
async function tgCall(m, body) {
  const r = await http("POST", siteUrl((S.account.services || {}).tg || "dwrapp/tg.php") + "?m=" + m, { headers: siteHeaders(), body: body || {}, timeout: 20000 });
  let d = {}; try { d = JSON.parse(r.body || "{}"); } catch (e) { }
  if (r.status === 401) throw new Error("вход в аккаунт устарел — войдите заново: Настройки → Мозг");
  if (r.status >= 400 || d.ok === false) throw new Error(d.description || "бот ответил " + r.status);
  return d.result;
}
async function tgSync() {
  if (!tgOn() || !(S.tg || {}).linked) return;
  const p = persona(), off = -new Date().getTimezoneOffset(), tz = (off >= 0 ? "+" : "-") + pad(Math.floor(Math.abs(off) / 60)) + ":" + pad(Math.abs(off) % 60);
  const base = (S.accCloud && S.accCloud.base) || siteUrl((S.account.services || {}).cloud || "dwrapp/cloud.php");
  try {
    await tgCall("dewiarSync", { device: "phone", key: S.account.token, cloud: base.split("?")[0], model: (S.llm.cloud && S.llm.account ? S.llm.model : (S.accCloud || {}).model) || "",
      voice: p.voice_remote || "", tz, persona: { name: p.name, gender: p.gender || "male", character: p.character || "" }, offline: true, voice_reply: true, sync_on: !!S.sync.on });
    S.tg.at = Date.now(); saveS();
  } catch (e) { plog("warn", "Telegram: " + e.message); }
}
/* Привязан ли бот у аккаунта. Бот один на все устройства аккаунта (03.11): его могли подключить на компьютере — телефон
   узнаёт сам при запуске и раз в 10 минут (раньше — только открыв «Ещё → Telegram», и «Отвечать с телефона» не включалось). */
async function tgStatus() { const r = await tgCall("dewiarStatus"); S.tg = Object.assign({}, S.tg, { linked: !!r.linked, bot: r.bot || "", name: r.name || "", st: Date.now() }); saveS();
  if (tgHandOn() && !tgHandT && !tgHandBusy) tgHandLater(500);
  return S.tg; }
async function tgLink(res) {
  const a = new Uint8Array(18); crypto.getRandomValues(a);
  const code = btoa(String.fromCharCode(...a)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");   // как secrets.token_urlsafe на компьютере
  const st = await tgStatus();
  if (!st.bot) throw new Error("на сайте не настроен бот Telegram");
  await tgCall("setLinkCode", { code, device: "phone" });     // «Готово» в Telegram скажет сам сервер — компьютеру не ждать
  D.openUrl("https://t.me/" + st.bot + "?start=" + code);
  res.className = "res"; res.textContent = "В Telegram нажмите «Старт» — жду…";
  for (let i = 0; i < 60; i++) {                   // 3 минуты: человек переключился в Telegram и вернулся
    await new Promise(r => setTimeout(r, 3000));
    if ((await tgStatus().catch(() => ({}))).linked) { await tgSync(); return true; }
  }
  throw new Error("не дождался «Старт» в Telegram — попробуйте ещё раз");
}

/* Телефон отвечает в Telegram, пока компьютер выключен (30.10, идея №67; пользователь: «мобилка постоянно в сети и Лира на
   ней — почему бы ей не отвечать?»). Включено «Отвечать с телефона» — телефон опрашивает бота (dewiarPhone): открыт — раз
   в 5 с, свёрнут — раз в 15 с (пока Android не усыпил приложение; значок «Dewiar на связи» держит его живым). Сообщение,
   пришедшее при выключенном компьютере, сервер держит для телефона до 25 с: телефон свободен (не говорит, не слушает) —
   забирает и отвечает своим мозгом (ключ сервиса не уходит на сервер), молча — ответ уходит в Telegram; не забрал — как
   раньше, отвечает сервер. Детский режим и экзамен — не отвечаем. */
let tgTurn = false, tgHandT = 0, tgHandBusy = false, tgLast = "";
const tgDone = [];
// включено по умолчанию (03.11: «нода на смартфоне ни разу не подхватила» — переключатель был выключен, а про него не знали)
const tgHandOn = () => tgOn() && !!(S.tg || {}).linked && (S.tg || {}).hand !== false && !kidsOn() && !SANDBOX;
function tgHandLater(ms) { clearTimeout(tgHandT); tgHandT = setTimeout(tgHandTick, ms); }
async function tgHandTick() {
  tgHandT = 0;
  if (!tgHandOn()) return;
  if (tgHandBusy) return tgHandLater(3000);
  tgHandBusy = true; let next = document.hidden ? 15000 : 5000;
  try {
    const r = await tgCall("dewiarPhone", { on: true, take: !busy && state === "idle", done: tgDone.splice(0) });
    for (const m of (r && r.take) || []) await tgHandle(m);
    if (tgDone.length) next = 200;                 // ответ готов — отдать сразу
  } catch (e) { plog("warn", "Telegram с телефона: " + e.message); next = 30000; }
  finally { tgHandBusy = false; }
  tgHandLater(next);
}
async function tgHandle(m) {
  for (let i = 0; i < 40 && (busy || state !== "idle"); i++) await sleep(1000);   // человек заговорил — дождаться
  const n0 = history.length; tgLast = ""; tgTurn = true;
  plog("info", `✈️ Telegram, компьютер выключен — отвечаю с телефона: ${clip(m.text)}`);
  try { await ask(m.text); } catch (e) { tgLast = "Не получилось ответить: " + (e.message || e); }
  finally { tgTurn = false; }
  const a = history.slice(n0).reverse().find(x => x.role === "assistant");
  const ans = String((a && a.content) || tgLast || "").trim();
  if (ans) tgDone.push({ id: m.id, answer: ans.slice(0, 4000) });    // нечего сказать — ответит сервер (tick, через пару минут)
}
async function tgHandSet(on) {
  S.tg = Object.assign({}, S.tg, { hand: !!on }); saveS();
  try { await tgCall("dewiarPhone", { on: !!on }); } catch (e) { plog("warn", "Telegram с телефона: " + e.message); }
  if (on) tgHandLater(500); else { clearTimeout(tgHandT); tgHandT = 0; }
}

