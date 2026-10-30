/* Студия → «Рефералы»: кого вы позвали в Dewiar — большим созвездием (assets/refnet.js, big), ссылка и код с печатью
   Dewiar, правила наград, «Есть код приглашения?» и список друзей. Первый уровень в обе стороны (кого пригласили вы и
   кто пригласил вас): уже в «Близких» — «Написать» и «Позвонить»; нет — «Позвать в Близкие» (core: close_ref → cloud.php
   ?p=/close/ref): друг увидит «… зовёт вас в «Близкие»» и согласится или откажется. rid — знак связи от сервера.
   RF.map — rid → {pid} (уже близкий) | {offered} (позвали, ждём ответа). */
const RF = { d: null, map: {}, sel: null };
/* 28.10 (владелец, Ubuntu): первый раз облако не ответило вовремя (первое соединение через прокси) — а на экране «Нужен
   вход в Dewiar», хотя вход есть. Теперь: сбой сети — ещё раз сам, тихо; не вышло — «Облако не ответило» и «Повторить»;
   «Нужен вход» — только когда входа и правда нет. */
async function loadRefs(again) {
  const res = $("#rf-res");
  if (!RF.d && !again) $("#rf-net").innerHTML = `<div class="rf-wait"><b>Открываю созвездие…</b><span>Спрашиваю облако Dewiar, кого вы пригласили.</span></div>`;
  try { RF.d = await core.call("ref_info"); }
  catch (e) {
    const login = /сначала подключите Dewiar|вход|ключ/i.test(e.message || "") && !/не ответил|timed? ?out|время|связ|прокси/i.test(e.message || "");
    if (!login && !again) { setTimeout(() => loadRefs(true), 1500); return; }
    $("#rf-net").innerHTML = login
      ? `<div class="rf-wait"><b>Нужен вход в Dewiar</b><span>Приглашения работают через облако Dewiar: войдите аккаунтом dewiar.pro или подключите ключ — раздел «Dewiar.pro».</span></div>`
      : `<div class="rf-wait"><b>Облако Dewiar не ответило</b><span>Так бывает при медленной сети. Попробуйте ещё раз.</span><button class="btn" id="rf-again">Повторить</button></div>`;
    if ($("#rf-again")) $("#rf-again").onclick = () => loadRefs();
    res.className = "res bad"; res.textContent = e.message; return;
  }
  res.className = "res"; res.textContent = "";
  rfRender();
  const rids = (RF.d.invited || []).map(x => x.rid).concat(RF.d.by ? [RF.d.by.rid] : []).filter(Boolean);
  try { if (rids.length) RF.map = await core.call("close_refs", { rids }); } catch (e) { RF.map = {}; }
  try { if (!CL.st || !CL.st.me) CL.st = await core.call("close_state"); } catch (e) { }
  rfRender();
}
function rfPeer(x) {                           // друг в «Близких» — его имя оттуда; иначе — как назвал сервер
  const m = (x && RF.map[x.rid]) || {}, p = m.pid && ((CL.st && CL.st.people) || []).find(q => q.pid === m.pid);
  return { pid: p ? p.pid : "", name: p ? p.name : x.name, offered: !!m.offered, devs: p ? (p.devs || []).length : 0 };
}
/* состояние приглашённого: засчитан; не засчитан (тот же интернет или устройство — защита от накруток); ждёт его
   первого пополнения или нового месяца (лимит наград); пробует Dewiar N из M дней */
const refState = (x) => x.paid ? "засчитан ✓" : x.why === "same" ? "не засчитан: тот же интернет или устройство" : x.why === "topup" ? "засчитается после его первого пополнения"
  : x.why === "cap" ? "засчитается в следующем месяце — лимит наград" : `пользуется ${+x.days || 0} из ${+x.need || 0} дн.`;
function rfRow(x, key, sub) {
  const q = rfPeer(x);
  const act = q.pid ? `<button class="btn small" data-w="${clEsc(q.pid)}">Написать</button>` + (q.devs ? `<button class="btn small" data-c="${clEsc(q.pid)}">Позвонить</button>` : "")
    : q.offered ? `<em class="rf-wt">ждём ответа</em>` : `<button class="btn small" data-o="${clEsc(x.rid)}">Позвать в Близкие</button>`;
  return `<div class="rf-p ${RF.sel === key ? "cur" : ""}" data-k="${key}"><i class="cl-ava" style="--c:${window.DewiarRefNet ? DewiarRefNet.color(x.name) : clColor(x.name)}">${clEsc((q.name || "?").slice(0, 1).toUpperCase())}</i>
    <span><b>${clEsc(q.name)}</b><small>${sub}</small></span>${act}</div>`;
}
/* «ссылку открыли» — сколько разных людей открыли страницу приглашения (сервер считает сам, превью мессенджеров — нет);
   поставивший Dewiar с того же устройства и вошедший засчитывается без кода (cloud.php ref_auto) */
const rfHow = (d) => `Кто поставит Dewiar с того же устройства и войдёт, появится здесь сам; ставят в другой сети или на другом устройстве — пусть введут код ${d.code}.`;
const rfPeople = (n) => n + (n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20) ? " человека" : " человек");
function rfRender() {
  const d = RF.d; if (!d) return;
  const list = d.invited || [], calm = !!$("#rf-net .rn");
  $("#rf-code").textContent = d.code; $("#rf-link").textContent = d.link;
  if (!$("#rf-qr").dataset.link || $("#rf-qr").dataset.link !== d.link) {     // печать Dewiar со ссылкой — навести камеру телефона
    const seal = window.DewiarCodes ? DewiarCodes.seal(d.link) : ""; $("#rf-qr").innerHTML = seal || qrSvg(d.link); $("#rf-qr").dataset.link = d.link; }
  $("#rf-rules").textContent = (d.bonus > 0 ? `Вам +${refTal(d.bonus)} тал. за каждого друга, который попользуется Dewiar ${d.days} дн.` : "Поделитесь Dewiar с друзьями.")
    + (d.bonus_new > 0 ? ` Другу — +${refTal(d.bonus_new)} тал. сразу, как подключит Dewiar.` : "");
  $("#rf-use").style.display = d.can_use ? "" : "none";
  if (window.DewiarRefNet) {
    const net = Object.assign({}, d, { invited: list.map(x => { const q = rfPeer(x); return Object.assign({}, x, { label: q.name, close: q.pid }); }) });
    const r = DewiarRefNet.render($("#rf-net"), net, { big: true, calm, light: document.documentElement.classList.contains("st-light"), me: "Вы", by: d.by ? rfPeer(d.by).name : "", sel: RF.sel, seenKey: "dw_refnet_seen",
      onPick: (i) => { RF.sel = RF.sel === i ? null : i; rfRender(); const row = $(`.rf-p[data-k="${i}"]`); if (row) row.scrollIntoView({ block: "nearest", behavior: "smooth" }); } });
    if (r.fresh) toast(r.fresh === 1 ? "Ещё один друг засчитан — звезда загорелась!" : `Засчитано новых друзей: ${r.fresh}`, 3500);
  }
  $("#rf-by").innerHTML = d.by ? `<h2>Вас пригласил</h2><div class="rf-list">${rfRow(d.by, "by", "с этого приглашения вы в Dewiar")}</div>` : "";
  $("#rf-h").textContent = list.length ? `Приглашённые · ${list.length}` : "Приглашённые";
  $("#rf-list").innerHTML = list.length ? list.map((x, i) => rfRow(x, i, refState(x) + (x.sub ? ` · позвал ещё ${x.sub}` : ""))).join("")
    : `<div class="rf-empty"><b>Пока никого</b><span>${clEsc(d.opened > 0 ? `Ссылку открыли ${rfPeople(+d.opened)}, но Dewiar по ней пока никто не подключил. ` + rfHow(d)
      : "Скопируйте приглашение или покажите печать. Друг, который поставит Dewiar по ссылке, появится здесь сам; каждый засчитанный — новая звезда.")}</span></div>`;
  if (list.length && d.opened > list.length) $("#rf-list").insertAdjacentHTML("beforeend", `<p class="hint rf-op">${clEsc(`Ссылку открыли ${rfPeople(+d.opened)}. ` + rfHow(d))}</p>`);
  $$(".rf-p").forEach(r => r.onclick = (e) => { if (e.target.closest("button")) return; const k = r.dataset.k === "by" ? "by" : +r.dataset.k; RF.sel = RF.sel === k ? null : k; rfRender(); });
  $$(".rf-p [data-w]").forEach(b => b.onclick = () => { $('nav button[data-p="close"]').click(); setTimeout(() => clOpen(b.dataset.w), 250); });
  $$(".rf-p [data-c]").forEach(b => b.onclick = () => core.call("close_call", { pid: b.dataset.c, video: false }).then(r => toast("Звоню " + r.name + " — окно звонка открыто в браузере", 3000)).catch(e => toast(e.message, 4000)));
  $$(".rf-p [data-o]").forEach(b => b.onclick = async () => {
    b.disabled = true;
    try {
      const r = await core.call("close_ref", { rid: b.dataset.o });
      if (r.person) { RF.map[b.dataset.o] = { pid: r.person.pid }; CL.st = await core.call("close_state"); toast(`${r.person.name} — в ваших близких: можно писать и звонить`, 3500); }
      else { RF.map[b.dataset.o] = { offered: true }; toast("Позвали — когда друг согласится, он появится в «Близких»", 3500); }
      rfRender();
    } catch (e) { b.disabled = false; toast(e.message, 4000); }
  });
}
$("#rf-copy").onclick = () => { const d = RF.d; if (!d) return;
  navigator.clipboard.writeText(`Попробуй Dewiar — помощницу Лиру для компьютера и телефона: ${d.link}\nКод приглашения: ${d.code}`).then(() => toast("Приглашение скопировано"), () => toast(d.link)); };
$("#rf-ugo").onclick = async () => {
  const r = $("#rf-res"); r.className = "res"; r.textContent = "проверяю…";
  try { const u = await core.call("ref_use", { code: $("#rf-ucode").value }); r.className = "res ok"; r.textContent = u.gift > 0 ? `Код принят — вам +${refTal(u.gift)} тал.` : "Код принят."; loadRefs(); }
  catch (e) { r.className = "res bad"; r.textContent = e.message; }
};
