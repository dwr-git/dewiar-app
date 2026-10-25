/* Студия → «Близкие» → «Встречи» (22.10, владелец: «добавить и на компе, но чтобы работало с телефона — забавно и
   прикольно; и чтобы отличалось от радара»). Не прибор, а доска: люди рядом — бейджи «Привет, меня зовут…», как на
   конференции. Пространство то же, что у телефона (core: close_meet → cloud.php /meet/*): отметка с телефона видна здесь,
   помахать 👋, ответить, написать, заблокировать — отсюда. Отметиться с компьютера можно по месту телефона (свежее 30 минут);
   уже отмечены — изменить и продлить можно и без места. */
const MT = { d: null, err: "", menu: "", edit: false, hours: 2, timer: 0, busy: false, report: "" };

function meetOpen() { mtLoad(); }
async function mtLoad() {
  clearTimeout(MT.timer);
  try { MT.d = await core.call("close_meet", { path: "/meet/state" }); MT.err = ""; } catch (e) { MT.err = e.message; }
  mtRender();
  MT.timer = setTimeout(() => { const box = $("#cl-meet"); if (box && !box.hidden && !document.hidden) mtLoad(); }, 20000);
}
async function mtDo(path, body, btn) {
  if (btn) btn.disabled = true;
  try { const d = await core.call("close_meet", { path, body: body || {} }); MT.d = d; MT.err = ""; return d; }
  catch (e) { toast(e.message, 5000); throw e; }
  finally { if (btn && btn.isConnected) btn.disabled = false; mtRender(); }
}
const mtMin = (s) => Math.max(0, Math.round(s / 60));
const mtLeft = (u) => { const m = mtMin(u - Date.now() / 1000); return m >= 60 ? Math.floor(m / 60) + " ч" + (m % 60 ? " " + (m % 60) + " мин" : "") : m + " мин"; };
const mtAgo = (ts) => { const m = mtMin(Date.now() / 1000 - ts); return m < 2 ? "только что" : m < 60 ? m + " мин" : Math.floor(m / 60) + " ч " + (m % 60) + " мин"; };
const mtTilt = (mid) => ([...String(mid)].reduce((a, c) => a * 31 + c.charCodeAt(0), 7) % 7 - 3) * 0.6;   // у каждого бейджа — свой лёгкий наклон
function mtPhone() {                                     // место телефона: свежее — можно отметиться отсюда
  const g = ((CL.st || {}).geo || {}).me;
  return g && Date.now() - g.ts < 30 * 60000 ? g : null;
}

function mtRender() {
  const box = $("#cl-meet"); if (!box || box.hidden) return;
  if (MT.busy) return;                                   // пишут в анкету — не перерисовываем (опрос раз в 20 с)
  const d = MT.d;
  if (!d) {
    box.innerHTML = MT.err ? `<div class="mt-note"><b>Встречи не открылись</b><span>${clEsc(MT.err)}</span><button class="btn" id="mt-retry">Повторить</button></div>`
      : `<p class="hint" style="margin:30px;text-align:center">Загружаю…</p>`;
    if ($("#mt-retry")) $("#mt-retry").onclick = () => { MT.err = ""; mtRender(); mtLoad(); };
    return;
  }
  const me = d.me || {};
  if (!me.adult) {
    box.innerHTML = `<div class="mt-note mt-intro"><b>Знакомства там, где вы сейчас</b>
      <ul><li>Отметьтесь на концерте, выставке, в кафе — на 1–3 часа. С телефона или отсюда, по месту телефона.</li>
        <li>Рядом видят только имя, пару слов о вас и место. Ни фото, ни адреса, ни расстояния.</li>
        <li>Связь — только если вы помахали 👋 друг другу: тогда вы оба в «Близких», переписка шифруется.</li>
        <li>Ушли — отметка и все «помахал» стираются. Истории нет.</li></ul>
      <label class="mt-18"><input type="checkbox" id="mt-18"><span>Мне есть 18 лет, правила понятны</span></label>
      <button class="btn primary" id="mt-start" disabled>Начать</button></div>`;
    $("#mt-18").onchange = () => { $("#mt-start").disabled = !$("#mt-18").checked; };
    $("#mt-start").onclick = (e) => mtDo("/meet/rules", { adult: true }, e.currentTarget).catch(() => { });
    return;
  }
  if (me.ban_until) {
    box.innerHTML = `<div class="mt-note"><b>Встречи закрыты до ${new Date(me.ban_until * 1000).toLocaleDateString("ru-RU", { day: "numeric", month: "long" })}</b><span>На вас пожаловались несколько человек. Если это ошибка — «О программе» → «Сообщить о проблеме».</span></div>`;
    return;
  }
  const h = me.here;
  if (!h || MT.edit) return mtForm(box, h);
  const ppl = d.people || [], left = h.until - Date.now() / 1000, total = Math.max(1, h.until - h.since);
  const tags = ppl.map(x => {
    const cls = x.match ? " match" : x.waves_me ? " in" : x.waved ? " waved" : "";
    const band = x.match ? "Вы в «Близких»" : x.waves_me ? "👋 Машет вам" : "Привет, меня зовут";
    const act = x.match ? `<button class="btn primary sm" data-chat="${clEsc(x.pid)}">Написать</button>`
      : x.waved ? `<span class="mt-wait">Помахали — ждём ответа</span><button class="btn sm" data-undo="${clEsc(x.mid)}">Отменить</button>`
      : x.waves_me ? `<button class="btn primary sm" data-wave="${clEsc(x.mid)}">👋 Помахать в ответ</button>`
      : `<button class="btn sm" data-wave="${clEsc(x.mid)}">👋 Помахать</button>`;
    const menu = MT.menu === x.mid ? `<div class="mt-menu">${MT.report === x.mid
        ? `<input type="text" id="mt-why" maxlength="300" placeholder="Что случилось? Увидит только администратор"><button class="btn sm" data-report="${clEsc(x.mid)}">Отправить</button>`
        : `<button class="btn sm" data-block="${clEsc(x.mid)}">Заблокировать</button><button class="btn sm" data-rep="${clEsc(x.mid)}">Пожаловаться</button>`}</div>` : "";
    return `<article class="mt-tag${cls}" data-mid="${clEsc(x.mid)}" style="--c:${clColor(x.mid)};--r:${mtTilt(x.mid)}deg">
      <header>${band}</header>
      <div class="mt-body">${+x.face ? `<i class="mt-face cl-ava" data-face="${clEsc(x.mid)}" data-v="${+x.face}">${clEsc((x.name || "?").slice(0, 1).toUpperCase())}</i>` : ""}<b class="mt-nm">${clEsc(x.name)}</b>${x.about ? `<p class="mt-ab">${clEsc(x.about)}</p>` : ""}
        <small>${x.place ? clEsc(x.place) + " · " : ""}здесь ${mtAgo(x.since)}</small></div>
      <footer>${act}<button class="mt-more" data-m="${clEsc(x.mid)}" aria-label="Ещё: заблокировать, пожаловаться" aria-expanded="${MT.menu === x.mid}">⋯</button></footer>${menu}</article>`;
  }).join("");
  box.innerHTML = `<div class="mt-here" style="--left:${Math.max(0, Math.min(1, left / total))}">
      <div class="mt-pin" aria-hidden="true"></div>
      <div class="mt-hw"><b>Вы отмечены${h.place ? " · " + clEsc(h.place) : ""}</b><span>как ${clEsc(h.name)} · видно ещё ${mtLeft(h.until)}</span><i class="mt-fuse"></i></div>
      <div class="mt-ha">${left < 2.5 * 3600 ? `<button class="btn sm" id="mt-more1">+1 час</button>` : ""}<button class="btn sm" id="mt-edit">Изменить</button><button class="btn sm" id="mt-leave">Ушёл</button></div></div>
    <div class="mt-board${ppl.length ? "" : " empty"}">${tags || `<article class="mt-tag ghost"><header>Привет, меня зовут</header><div class="mt-body"><b class="mt-nm">…</b>
      <p class="mt-ab">Здесь появится тот, кто отметится рядом с вами</p></div></article>`}</div>
    <p class="hint mt-foot">${ppl.length ? "Рядом — " + ppl.length + ". " : ""}Видно только тех, кто отметился в пределах ~${d.radius_m || 700} м. Ни точного места, ни расстояния не видит никто. Обновляется само.</p>`;
  clFaces($("#cl-meet"), true);
  $("#mt-leave").onclick = (e) => mtDo("/meet/leave", {}, e.currentTarget).then(() => toast("Отметки больше нет — и всех «помахал» тоже")).catch(() => { });
  $("#mt-edit").onclick = () => { MT.edit = true; mtRender(); };
  if ($("#mt-more1")) $("#mt-more1").onclick = (e) => mtDo("/meet/here", { keep: true, name: h.name, about: h.about, place: h.place,
    hours: Math.min(d.max_h || 3, Math.ceil(left / 3600) + 1) }, e.currentTarget).then(() => toast("Продлили — видно ещё час")).catch(() => { });
  $$("#cl-meet [data-m]").forEach(b => b.onclick = () => { MT.menu = MT.menu === b.dataset.m ? "" : b.dataset.m; MT.report = ""; mtRender(); });
  $$("#cl-meet [data-wave]").forEach(b => b.onclick = () => { const tag = b.closest(".mt-tag"); mtHand(tag);
    mtDo("/meet/wave", { mid: b.dataset.wave }, b).then(r => {
      if (r.match) { const p = (r.people || []).find(x => x.pid === r.pid); toast(`Вы помахали друг другу — ${p ? p.name : "собеседник"} теперь в «Близких»`, 4500); loadClose(true); }
      else toast("👋 Помахали — увидит у себя");
    }).catch(() => { }); });
  $$("#cl-meet [data-undo]").forEach(b => b.onclick = () => mtDo("/meet/wave", { mid: b.dataset.undo, undo: 1 }, b).catch(() => { }));
  $$("#cl-meet [data-chat]").forEach(b => b.onclick = async () => { b.disabled = true; try { await loadClose(true); } catch (e) { } rdTab("chat"); clOpen(b.dataset.chat); });
  $$("#cl-meet [data-block]").forEach(b => b.onclick = () => {
    if (b.dataset.sure !== "1") { b.dataset.sure = "1"; b.textContent = "Точно? Не увидите друг друга"; return; }
    MT.menu = ""; mtDo("/meet/block", { mid: b.dataset.block }, b).then(() => toast("Заблокировано")).catch(() => { }); });
  $$("#cl-meet [data-rep]").forEach(b => b.onclick = () => { MT.report = b.dataset.rep; mtRender(); setTimeout(() => $("#mt-why") && $("#mt-why").focus(), 30); });
  $$("#cl-meet [data-report]").forEach(b => b.onclick = () => { const why = ($("#mt-why") || {}).value || "";
    MT.menu = MT.report = ""; mtDo("/meet/report", { mid: b.dataset.report, why }, b).then(() => toast("Спасибо. Жалоба отправлена — вы больше не увидите друг друга", 4000)).catch(() => { }); });
}

function mtHand(tag) {                                    // 👋 вылетает из бейджа — ответ на нажатие
  if (!tag || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const h = document.createElement("i"); h.className = "mt-fly"; h.textContent = "👋"; tag.appendChild(h); setTimeout(() => h.remove(), 1200);
}

function mtForm(box, h) {
  const g = mtPhone();
  if (!h && !g) {
    box.innerHTML = `<div class="mt-note mt-phone"><b>Отметьтесь с телефона — люди рядом появятся здесь</b>
      <span>Компьютер не знает, где вы. На телефоне: «Близкие» → «Встречи» → «Отметиться». Или откройте там «Рядом» — место телефона придёт сюда, и отметиться можно будет отсюда.</span>
      <button class="btn" id="mt-check">Проверить ещё раз</button></div>`;
    $("#mt-check").onclick = async () => { await loadClose(false); mtLoad(); };
    return;
  }
  const st = CL.st || {}, nm = (h && h.name) || String((st.me && st.me.name !== "Без имени" && st.me.name) || "").split(/\s+/)[0];
  box.innerHTML = `<div class="mt-form"><article class="mt-tag preview" style="--c:${clColor("me")};--r:-1.2deg"><header>Привет, меня зовут</header>
      <div class="mt-body"><b class="mt-nm" id="mt-pv-n">${clEsc(nm || "…")}</b><p class="mt-ab" id="mt-pv-a">${clEsc((h ? h.about : st.me && st.me.about) || "пара слов о вас")}</p><small id="mt-pv-p">${clEsc((h && h.place) || "где вы")}</small></div></article>
    <div class="mt-fields"><b class="mt-big">${h ? "Изменить отметку" : "Отметиться здесь"}</b>
      <label class="f"><span>Как вас называть</span><input type="text" id="mt-name" maxlength="24" placeholder="имя" value="${clEsc(nm)}"></label>
      <label class="f"><span>Пара слов о себе</span><input type="text" id="mt-about" maxlength="120" placeholder="например: впервые здесь, люблю джаз" value="${clEsc(((h ? h.about : st.me && st.me.about) || "").slice(0, 120))}"></label>
      <label class="f"><span>Где вы</span><input type="text" id="mt-place" maxlength="60" placeholder="концерт, выставка, кафе…" value="${clEsc((h && h.place) || "")}"></label>
      <div class="mt-hours" role="group" aria-label="Сколько видно">${[1, 2, 3].map(n => `<button class="${MT.hours === n ? "on" : ""}" data-h="${n}">${n} ч</button>`).join("")}</div>
      <div class="actions"><button class="btn primary" id="mt-go">${h ? "Сохранить" : "Отметиться"}</button>${h ? `<button class="btn" id="mt-cancel">Отмена</button>` : ""}</div>
      <p class="hint">${h ? "Место — прежнее." : "Место — вашего телефона, обновлено " + rdAgo(g.ts) + "."} Ссылки, ники и номера не нужны: контакт откроется сам, когда помашете друг другу.</p></div></div>`;
  MT.busy = false;
  const pv = () => { $("#mt-pv-n").textContent = $("#mt-name").value.trim() || "…"; $("#mt-pv-a").textContent = $("#mt-about").value.trim() || "пара слов о вас"; $("#mt-pv-p").textContent = $("#mt-place").value.trim() || "где вы"; };
  ["#mt-name", "#mt-about", "#mt-place"].forEach(s => { $(s).oninput = () => { MT.busy = true; pv(); }; });
  $$("#cl-meet .mt-hours button").forEach(b => b.onclick = () => { MT.hours = +b.dataset.h; $$("#cl-meet .mt-hours button").forEach(x => x.classList.toggle("on", x === b)); });
  if ($("#mt-cancel")) $("#mt-cancel").onclick = () => { MT.edit = MT.busy = false; mtRender(); };
  $("#mt-go").onclick = async (e) => {
    const name = $("#mt-name").value.trim();
    if (!name) { toast("Как вас называть? Достаточно имени."); $("#mt-name").focus(); return; }
    const b = e.currentTarget; b.disabled = true;
    try {      // не через mtDo: при ошибке («без ссылок и номеров») анкета остаётся с тем, что вписали
      MT.d = await core.call("close_meet", { path: "/meet/here", body: { keep: !!h, name, about: $("#mt-about").value.trim(), place: $("#mt-place").value.trim(), hours: MT.hours } });
      MT.edit = MT.busy = false; mtRender(); toast(h ? "Сохранено" : "Вы отмечены — рядом увидят ваш бейдж");
    } catch (x) { toast(x.message, 5000); b.disabled = false; }
  };
}
document.addEventListener("visibilitychange", () => { const box = $("#cl-meet"); if (!document.hidden && box && !box.hidden) mtLoad(); });
core.on("close_geo", () => mtRender());              // телефон прислал своё место — можно отметиться отсюда
