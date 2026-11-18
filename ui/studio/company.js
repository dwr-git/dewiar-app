/* «Компания» в студии (пилот «А и Б вместе», владелец 18.11; сервер — server/dwrapp/cloud/company.php, ядро — cloud_company).
   Раздела в меню нет:
   - «Мозг» → «ИИ-баланс»: в компании — «за ИИ платит компания «…»» (сотруднику — баланс компании, свой лимит и потрачено; «Пополнить»
     прячется — пополняет руководитель); не в компании — «Код от компании» (войти по коду руководителя);
   - «Поручения» (вверху, только у руководителя): баланс компании (18.11: без «котла» и «доли» — партнёр не понял), места — кто сколько потратил за месяц и
     когда был на связи (разговоров не видно), лимит на человека, «Пригласить сотрудника» (код на 14 дней), «Убрать». */
(() => {                                                  // свои имена — внутри: в студии много общих (CO, coEsc…)
const COMP = { c: null, busy: false };
const coNum = (v, d = 2) => { const n = +v || 0; return (Math.abs(n) < 0.01 && n ? n.toFixed(4) : n.toFixed(d)).replace(/\.?0+$/, "").replace(".", ","); };
const coEsc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const coAgo = (t) => { if (!t) return "ещё не был"; const s = Date.now() / 1000 - t; if (s < 600) return "на связи"; if (s < 3600) return `${Math.round(s / 60)} мин назад`;
  if (s < 86400) return `${Math.round(s / 3600)} ч назад`; return new Date(t * 1000).toLocaleDateString("ru-RU", { day: "numeric", month: "long" }); };

/* подарок мест на этот месяц (только если у компании есть плата за места) — одной фразой; на пилоте его нет */
function coBonus(co) {
  return +co.seat_amt > 0 && +co.month_left > 0 ? ` Из них ${coNum(co.month_left)} — подарок за места на этот месяц, сгорит 1-го числа.` : "";
}

function coFill(c) {
  const co = c && c.connected ? c.company : null;
  COMP.c = co || null;
  const box = $("#cc-co"), join = $("#cc-join");
  if (!box || !join) return;
  join.hidden = !!co || !c || !c.connected || !!c.site || !!c.account;          // по аккаунту сайта в компанию не входят
  if ($("#cc-new-mvl")) $("#cc-new-mvl").hidden = !(c && +c.balance > 0);                // переносить нечего — галочки нет
  box.hidden = !co;
  if (co) {
    const lim = +co.lim || 0;
    $("#cc-sub").textContent = `Компания «${co.name}»` + (c.active ? " · отвечает облако" : "");
    $("#cc-co-t").textContent = co.role === "owner"
      ? `Вы — руководитель. На балансе компании — ${coNum(co.left)} тал.${+c.turns ? ` (≈ ${(+c.turns).toLocaleString("ru-RU")} ответов Лиры)` : ""}. С него идут ответы Лиры у всех ${co.seats_n} человек, пополняете вы.` + coBonus(co)
      : `За ответы Лиры платит компания «${co.name}». ` + (lim ? `Ваш лимит — ${coNum(lim)} тал. в месяц, потрачено ${coNum(co.spent_month)}.` : `Потрачено в этом месяце: ${coNum(co.spent_month)} тал.`)
        + " Ваш собственный баланс сохранится.";
    const go = $("#cc-co-go");
    go.textContent = co.role === "owner" ? "Места и приглашения" : "Выйти из компании";
    go.onclick = co.role === "owner" ? () => { const b = $('nav button[data-p="team"]'); if (b) { b.hidden = false; b.click(); } } : coLeave;
    if (co.role !== "owner") { $("#cc-top").style.display = "none"; const p = $("#cc-pay"); if (p) p.style.display = "none"; }
    else $("#cc-top").style.display = "";
  }
  // впервые увидели свою компанию (директор — после кабинета, сотрудник — после кода): набор «Для работы», раз и молча
  if (co && S && (S.ui || {}).co_seen !== co.id && typeof shApplyWork === "function" && $("nav button[data-p]")) {
    S.ui = Object.assign({}, S.ui, { co_seen: co.id });
    save({ ui: { co_seen: co.id } }, true).catch(() => {});
    shApplyWork();
  }
  coTeam();
}

async function coLeave() {
  if (!await ask(`Выйти из компании «${COMP.c.name}»? Ответы Лиры снова будет оплачивать ваш собственный баланс.`)) return;
  try { await core.call("cloud_company", { op: "leave" }); toast("Вы вышли из компании"); core.call("cloud_status", { refresh: true }).then(cloudFill).catch(() => {}); }
  catch (e) { toast(e.message); }
}

$("#cc-join-go") && ($("#cc-join-go").onclick = async () => {
  const r = $("#cc-join-res"), code = $("#cc-join-code").value.trim();
  if (!/^[A-Za-z0-9]{4}-?[A-Za-z0-9]{4}$/.test(code)) { r.className = "res bad"; r.textContent = "Код — 8 знаков, как его дал руководитель: XXXX-XXXX"; return; }
  $("#cc-join-go").disabled = true;
  try {
    const x = await core.call("cloud_company", { op: "join", code });
    r.className = "res ok"; r.textContent = x.message || "Вы в компании";
    $("#cc-join-code").value = "";
    setTimeout(() => core.call("cloud_status", { refresh: true }).then(cloudFill).catch(() => {}), 400);
  } catch (e) { r.className = "res bad"; r.textContent = e.message; }
  finally { $("#cc-join-go").disabled = false; }
});
/* «Создать компанию» (18.11, владелец: «минимум ручных настроек»): руководитель заводит её сам; по желанию его баланс — в котёл */
$("#cc-new-go") && ($("#cc-new-go").onclick = async () => {
  const r = $("#cc-new-res"), name = $("#cc-new-name").value.trim();
  if (name.length < 2) { r.className = "res bad"; r.textContent = "Напишите название компании"; $("#cc-new-name").focus(); return; }
  if (!await ask(`Создать компанию «${name}»? Вы станете её руководителем: ответы Лиры у вас и у сотрудников будут списываться с баланса компании`
    + ($("#cc-new-mv").checked ? ", а ваш нынешний баланс перейдёт на него." : ". Ваш баланс останется вашим, баланс компании пополняется оплатой."), { ok: "Создать" })) return;
  $("#cc-new-go").disabled = true;
  try {
    const x = await core.call("cloud_company", { op: "create", name, move: $("#cc-new-mv").checked });
    r.className = "res ok"; r.textContent = x.message || "Компания создана";
    $("#cc-new-name").value = "";
    setTimeout(() => core.call("cloud_status", { refresh: true }).then(cloudFill).catch(() => {}), 400);
  } catch (e) { r.className = "res bad"; r.textContent = e.message; }
  finally { $("#cc-new-go").disabled = false; }
});
$("#cc-new-name") && ($("#cc-new-name").onkeydown = (e) => { if (e.key === "Enter") { e.preventDefault(); $("#cc-new-go").click(); } });
$("#cc-join-code") && ($("#cc-join-code").onkeydown = (e) => { if (e.key === "Enter") { e.preventDefault(); $("#cc-join-go").click(); } });

/* ---------- «Поручения» → «Компания» (руководитель) ---------- */
function coTeam(force) {
  const box = $("#tm-co"); if (!box) return;
  const co = COMP.c;
  if (!co || co.role !== "owner") { box.hidden = true; box.innerHTML = ""; COMP.sig = ""; return; }
  box.hidden = false;
  // перерисовка — только когда данные изменились и человек ничего не вводит (баланс обновляется часто: иначе стирались бы
  // набранное имя в «Пригласить» и лимит в поле)
  const team = (typeof TM !== "undefined" && TM) || {}, mem = (team.members || []);
  const sig = JSON.stringify([co, mem.map(m => [m.id, m.name]), team.leads_to || "", COMP.sc && COMP.sc.remote ? [COMP.sc.remote.tg, COMP.sc.kb_chars] : 0]);
  if (!force) {
    if (sig === COMP.sig && box.innerHTML) return;
    if (box.contains(document.activeElement) && /^(INPUT|TEXTAREA)$/.test(document.activeElement.tagName)) return;
    if ($("#co-new") && !$("#co-new").hidden) return;
  }
  COMP.sig = sig;
  const seats = co.seats || [], inv = co.invites || [];
  const max = Math.max(0.0001, ...seats.map(s => +s.spent_month || 0), ...seats.map(s => +s.lim || +co.lim_default || 0));
  const left = +co.left || 0, full = Math.max(left, left + seats.reduce((a, s) => a + (+s.spent_month || 0), 0));
  box.innerHTML = coSteps(co, team) + `<div class="co-head">
      <div class="co-t"><b>Компания «${coEsc(co.name)}»</b><span>Один баланс на всю компанию: каждый просто пользуется Лирой, ответы списываются отсюда сами. Ниже — сколько потратил каждый; разговоров сотрудников здесь не видно.</span></div>
      <div class="co-left"><b>${coNum(left)}</b><span>тал. на балансе</span><i class="co-bar"><i style="width:${Math.max(left > 0 ? 2 : 0, Math.min(100, left / full * 100))}%"></i></i>
        ${coBonus(co) ? `<small>${coEsc(coBonus(co).trim())}</small>` : ""}</div>
    </div>
    <ul class="co-seats">${seats.map(s => { const lim = +s.lim || +co.lim_default || 0, sp = +s.spent_month || 0;
      return `<li data-k="${s.key}"><span class="co-who"><b>${coEsc(s.name)}</b><small>${s.role === "owner" && !/^руководител/i.test(s.name) ? "руководитель · " : ""}${coEsc(coAgo(s.seen))}</small></span>
        <span class="co-sp"><i class="co-bar${lim && sp >= lim ? " over" : ""}"><i style="width:${Math.min(100, sp / (lim || max) * 100)}%"></i></i><small>потратил ${coNum(sp)}${lim ? ` из ${coNum(lim)}` : ""} тал. за месяц</small></span>
        <span class="co-act">${s.role === "owner" ? "" : `<button class="btn small" data-lim="${s.key}" title="Лимит этого человека в месяц">${+s.lim ? "Лимит " + coNum(s.lim) : "Лимит"}</button><button class="btn small ghost" data-rm="${s.key}">Убрать</button>`}</span></li>`; }).join("")}</ul>
    ${inv.length ? `<p class="co-inv">Ждут входа: ${inv.map(i => `<span class="co-code" title="действует до ${new Date(i.until * 1000).toLocaleDateString("ru-RU")}"><code>${coEsc(i.code)}</code>${i.name ? " · " + coEsc(i.name) : ""}<button class="co-x" data-un="${coEsc(i.code)}" aria-label="Отменить код ${coEsc(i.code)}">×</button></span>`).join("")}</p>` : ""}
    <div class="co-acts"><button class="btn primary" id="co-inv">Пригласить сотрудника</button>
      <label class="co-dl">Лимит на человека в месяц <input type="text" id="co-dlim" inputmode="decimal" placeholder="без лимита" value="${+co.lim_default ? coNum(co.lim_default) : ""}"> тал.</label>
      <label class="co-dl" title="Заявка с сайта или из Telegram-бота станет поручением: связаться с клиентом в ближайшие 2 часа">Заявки клиентов — поручать
        <select id="co-leads"><option value="">никому, только в «Клиенты»</option>${mem.map(m => `<option value="${coEsc(m.id)}"${m.id === team.leads_to ? " selected" : ""}>${coEsc(m.name)}</option>`).join("")}</select></label></div>
    <div class="co-new" id="co-new" hidden></div>`;
  $("#co-inv").onclick = coInvite;
  $$("#tm-co [data-go]").forEach(b => b.onclick = () => coGo(b.dataset.go));
  $("#co-leads").onchange = async (e) => {
    const v = e.target.value;
    try { const r = await core.call("team_set", { leads_to: v }); if (typeof TM !== "undefined") TM = r; coTeam(true);
      toast(v ? `Заявки клиентов — поручением: ${(mem.find(m => m.id === v) || {}).name || ""}` : "Заявки — только в «Клиенты»"); }
    catch (x) { toast(x.message, 4000); }
  };
  $("#co-dlim").onchange = () => coOp({ op: "limit", lim: $("#co-dlim").value.replace(",", ".") || 0 }, "Лимит по умолчанию сохранён");
  $$("#tm-co [data-lim]").forEach(b => b.onclick = () => coLimit(+b.dataset.lim));
  $$("#tm-co [data-rm]").forEach(b => b.onclick = async () => { const s = seats.find(x => x.key === +b.dataset.rm);
    if (await ask(`Убрать «${s.name}» из компании? Его Лира снова будет тратить его собственный баланс.`)) coOp({ op: "remove", key: s.key }, "Место убрано"); });
  $$("#tm-co [data-un]").forEach(b => b.onclick = () => coOp({ op: "uninvite", code: b.dataset.un }, "Код отменён"));
}

/* «Запуск компании» (18.11, мастер «Лира для компании» из документа пилота): пять шагов — галочки по настоящим данным,
   кнопки ведут в те места, где это уже есть («Чат для сайта», приглашение, «Заявки — поручать»). Нового раздела нет;
   всё готово — одна строка. Состояние чата для сайта — sitechat_get один раз (и после его публикации). */
function coSteps(co, team) {
  const sc = COMP.sc;
  if (sc === undefined) { COMP.sc = null; core.call("sitechat_get", {}).then(d => { COMP.sc = d || {}; coTeam(true); }).catch(() => { COMP.sc = {}; }); }
  const r = (sc && sc.remote) || null;
  const steps = [
    ["Компания", `«${co.name}» заведена, на балансе — ${coNum(co.left)} тал.`, true, ""],
    ["Знания", r && (sc.kb_chars || r.kb_chars) ? "консультант знает цены и услуги — спросите его как клиент" : "впишите цены, услуги, адрес и часы работы — по ним Лира отвечает клиентам", !!(r && (sc.kb_chars || r.kb_chars)), "chat"],
    ["Каналы", r ? (r.tg ? `сайт и Telegram-бот ${r.tg}` : "ссылка и окно для сайта готовы; подключите и Telegram-бота") : "ссылка для сайта и свой бот в Telegram — клиенты пишут, Лира отвечает", !!(r && r.tg), "chat"],
    ["Люди", co.seats_n > 1 ? `в компании ${co.seats_n} — поручения и ответы Лиры за счёт компании` : "пригласите сотрудников — одна ссылка на каждого", co.seats_n > 1, "inv"],
    ["Заявки", team.leads_to ? `поручаются: ${((team.members || []).find(m => m.id === team.leads_to) || {}).name || ""}` : "выберите, кому поручать заявки клиентов", !!team.leads_to, "leads"],
  ];
  const n = steps.filter(x => x[2]).length;
  if (n === steps.length) return `<p class="cz-ready"><i aria-hidden="true"></i>Компания запущена: знания, каналы, люди и заявки на месте.</p>`;
  return `<div class="cz-steps"><div class="cz-steps-h"><b>Запуск компании</b><span>${n} из ${steps.length}</span></div><ol>`
    + steps.map(([t, d, done, go]) => `<li class="${done ? "on" : ""}"><i aria-hidden="true"></i><span><b>${t}</b><small>${coEsc(d)}</small></span>`
      + (!done && go ? `<button class="btn small" data-go="${go}">${go === "inv" ? "Пригласить" : go === "leads" ? "Выбрать" : "Открыть"}</button>` : "") + `</li>`).join("") + `</ol></div>`;
}
function coGo(go) {
  if (go === "chat") { COMP.sc = undefined; const n = $('nav button[data-p="sitechat"]'); if (n) { n.hidden = false; n.click(); } return; }
  if (go === "inv") { coInvite(); $("#co-new").scrollIntoView({ block: "center", behavior: "smooth" }); return; }
  if (go === "leads") { const s = $("#co-leads"); if (s) { s.scrollIntoView({ block: "center", behavior: "smooth" }); s.focus(); } }
}

async function coOp(args, msg) {
  if (COMP.busy) return; COMP.busy = true;
  try { const r = await core.call("cloud_company", args); if (r && r.company && !args.keep) { COMP.c = Object.assign({}, COMP.c, r.company); coTeam(true); } if (msg) toast(msg); return r; }
  catch (e) { toast(e.message, 4000); }
  finally { COMP.busy = false; }
}

/* «Пригласить сотрудника» (18.11: одно приглашение на всё): ссылка — сотрудник открывает её на телефоне, поручения приходят
   в «Работу», а ответы его Лиры идут с баланса компании (team_hire → /work/invite с местом компании). Только компьютер —
   «Код для компьютера» (8 знаков, вводится в «Мозге»). */
async function coInvite() {
  const box = $("#co-new");
  box.hidden = false;
  box.innerHTML = `<label class="f"><span>Кого приглашаете</span><input type="text" id="co-nm" placeholder="Иван, монтажник" maxlength="60"></label><button class="btn primary" id="co-mk">Получить ссылку</button>`;
  $("#co-nm").focus();
  const go = async () => {
    const raw = $("#co-nm").value.trim();
    if (!raw) { $("#co-nm").focus(); return; }
    const [name, role] = raw.split(/\s*,\s*/, 2);
    if (COMP.busy) return; COMP.busy = true; $("#co-mk").disabled = true;
    let r = null;
    try { r = await core.call("team_hire", { name, role: role || "" }); }
    catch (e) { toast(e.message, 4000); }
    finally { COMP.busy = false; if ($("#co-mk")) $("#co-mk").disabled = false; }
    const h = r && r.hired; if (!h || !h.link) return;
    const days = h.expires ? Math.max(1, Math.round((h.expires * 1000 - Date.now()) / 864e5)) : 14;
    box.innerHTML = `<div class="co-code-big co-link"><span>Приглашение · ${coEsc(h.name)} — ${days} дн., один раз</span><code>${coEsc(h.link)}</code><button class="btn small" id="co-cp">Скопировать</button></div>
      <p class="hint">Отправьте ссылку сотруднику в мессенджере. Откроет на телефоне — поручения будут приходить в «Работу», а ответы Лиры оплатит компания. Ничего устанавливать не обязательно: ссылка открывается и в браузере.</p>
      <div class="co-acts"><button class="btn small" id="co-done">Готово</button><button class="btn small ghost" id="co-pc">Работает только на компьютере?</button></div>`;
    $("#co-cp").onclick = () => navigator.clipboard.writeText(h.link).then(() => toast("Ссылка скопирована")).catch(() => {});
    $("#co-done").onclick = () => { box.hidden = true; coOp({ op: "info" }); };
    $("#co-pc").onclick = () => coPcCode(h.name);
  };
  $("#co-mk").onclick = go;
  $("#co-nm").onkeydown = (e) => { if (e.key === "Enter") { e.preventDefault(); go(); } };
}

/* сотрудник только с компьютером: код компании — вводится в «Мозге» («Код от компании») */
async function coPcCode(name) {
  const box = $("#co-new");
  const r = await coOp({ op: "invite", name, keep: true });
  if (!r || !r.code) return;
  box.innerHTML = `<div class="co-code-big"><span>Код для компьютера — 14 дней, один раз</span><code>${coEsc(r.code)}</code><button class="btn small" id="co-cp">Скопировать</button></div>
    <p class="hint">${coEsc(r.how || "")}</p><button class="btn small" id="co-done">Готово</button>`;
  $("#co-cp").onclick = () => navigator.clipboard.writeText(r.code).then(() => toast("Код скопирован")).catch(() => {});
  $("#co-done").onclick = () => { box.hidden = true; coOp({ op: "info" }); };
}

async function coLimit(key) {
  const s = (COMP.c.seats || []).find(x => x.key === key); if (!s) return;
  const li = $(`#tm-co li[data-k="${key}"] .co-act`);
  li.innerHTML = `<input type="text" class="co-limin" inputmode="decimal" placeholder="без лимита" value="${+s.lim ? coNum(s.lim) : ""}" aria-label="Лимит в месяц, талеров"><button class="btn small primary">Сохранить</button>`;
  const inp = $("input", li); inp.focus(); inp.select();
  const save = () => coOp({ op: "seat", key, lim: inp.value.replace(",", ".") || 0 }, "Лимит сохранён");
  $("button", li).onclick = save;
  inp.onkeydown = (e) => { if (e.key === "Enter") save(); if (e.key === "Escape") coTeam(); };
}
core.on("team", () => setTimeout(() => coTeam(), 0));
core.on("sitechat", (e) => { if (e && !(e.site || "")) { COMP.sc = e; coTeam(); } });   // опубликовали чат, подключили бота — галочки     // сотрудники изменились — список «Заявки клиентов — поручать»
window.coFill = coFill;
})();
