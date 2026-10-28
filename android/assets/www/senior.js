/* «Для старших» на телефоне (0.62; план: «крупно и просто: лекарства с „выпили?“, „всё хорошо“ близким и защита от
   мошенников — прямо на телефоне бабушки»). Как core/senior.py на компьютере, только своими силами телефона:
   • Крупно и просто: класс body.senior — крупнее текст и кнопки; во «Всё» — только нужное; Лира говорит коротко и тепло.
   • Лекарства: «Добавить лекарство» — ежедневные напоминания; в окне напоминания кнопка «Выпил(а) ✓» (AlarmActivity) или
     голосом «выпила» — отмечено. Через 40 минут не отмечено — присматривающим сообщение через «Близкие».
   • «Всё хорошо» вечером (по умолчанию в 20:00) — сводка дня присматривающим; днём (с 12:00), если с утра тишина, — «может,
     позвоните?». Проверки идут, пока приложение живо (с «Сообщения и звонки — сразу» — почти всегда).
   • Мошенники: «звонят из банка, просят код из СМС», «внук попал в аварию» — сразу, без модели, твёрдое «стоп» и сообщение
     присматривающим.
   Настройки — S.senior: {on, name, gender f|m, watchers [pid], checkin "20:00", noon, scam, meds [{id, text, times, ids}]};
   день — pref senior_day: {d, talk [первое, последнее], sent [], alerts []}. */
"use strict";
const SR_MED = /таблет|лекарств|капл[иею]|капсул|укол|инсулин|давлени|сироп|мазь|витамин|пилюл/i;
const SR_TAKEN = /^(?:да,?\s+)?(?:я\s+)?(?:уже\s+)?(?:всё\s+|все\s+)?(?:выпил[аи]?|приняла?|принял[аи]?)(?![а-яё])/i;
const SR_SCAM = [
  /(?:позвонил\S*|звон(?:ят|ил\S*|ок)|пишут|написал\S*|прислал\S*|сообщени\S*).{0,70}?(?:банк|служб\S*\s+безопасност|полици|следовател|прокурат|фсб|мвд|центробанк|госуслуг|пенсионн\S*\s+фонд|сотовый\s+оператор|оператор\s+связи)/i,
  /(?:^|[^а-яё])код\S*\s+из\s+(?:смс|сообщени|sms)/i,
  /(?:назвать|назови|продиктова\S*|сказать|сообщить)\s+(?:им\s+)?(?:код|пароль|номер\s+карт|данные\s+карт|cvv|cvc)/i,
  /(?:безопасн\S+|резервн\S+|защищ[её]нн\S+)\s+сч[её]т/i,
  /(?:сын|дочь|дочка|внук|внучк\S*|племянни\S*|муж|жена).{0,50}?(?:попал\S*\s+(?:в\s+)?(?:авари|дтп|беду|полици|больниц)|сбил\S*|задержал\S*)/i,
  /(?:просят|просил\S*|требу\S+|сказали|велели)\s.{0,40}?(?:перевест\S*|перевод|отправить\s+деньг|снять\s+деньг|деньги|код|номер\s+карт|данные\s+карт|оформить\s+кредит)/i,
  /(?:выигр\S+|приз\S*|компенсаци\S*|выплат\S*).{0,50}?(?:оплат\S*|перевест\S*|комисси\S*|налог)/i];
const SR_NOT = /(?:^|[^а-яё])(?:что\s+такое|расскажи\s+(?:про|о)|как\s+(?:не\s+)?(?:попасть|распознать|защитить)|бывают\s+ли|почему)(?![а-яё])/i;
const SR_LATE = 40;                                // мин — лекарство не отмечено: сказать присматривающим
const srConf = () => Object.assign({ on: false, name: "", gender: "f", watchers: [], checkin: "20:00", noon: true, scam: true, meds: [] }, S.senior || {});
const srOn = () => !!(S.senior && S.senior.on) && !kidsOn();
const srG = (f, m) => srConf().gender === "m" ? m : f;
const srWho = () => (srConf().name || S.user_name || "").trim() || "ваш близкий";
const srDayKey = () => { const d = new Date(); return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`; };
function srDay() {
  let d = null; try { d = JSON.parse(prefGet("senior_day") || "null"); } catch (e) { }
  if (!d || d.d !== srDayKey()) d = { d: srDayKey(), talk: [], sent: [], alerts: [] };
  return d;
}
const srDaySave = (d) => prefSet("senior_day", JSON.stringify(d));
function srSave(patch) { S.senior = Object.assign(srConf(), patch || {}); saveS(); srApply(); syncSoon(); }
function srApply() { document.body.classList.toggle("senior", srOn()); }
function srWatchers() { const st = clLoad(), w = srConf().watchers || []; return st.people.filter(p => w.includes(p.pid)); }
async function srSend(text) {
  const ws = srWatchers(); let n = 0;
  for (const p of ws) { try { await clSend(p.pid, text); n++; } catch (e) { plog("warn", "для старших: не ушло " + p.name + " — " + e.message); } }
  return n;
}
/* ---------- лекарства ---------- */
const srTodayAt = (hm) => { const m = /^(\d{1,2})[:.](\d{2})$/.exec(String(hm || "").trim()); if (!m) return null; const d = new Date(); d.setHours(+m[1], +m[2], 0, 0); return d; };
function srMedAdd(text, times) {
  text = String(text || "").replace(/\s+/g, " ").trim().slice(0, 80);
  const ts = String(times || "").split(/[,;\s]+/).map(x => x.replace(".", ":")).filter(x => /^\d{1,2}:\d{2}$/.test(x)).map(x => x.padStart(5, "0")).slice(0, 6);
  if (text.length < 2 || !ts.length) throw new Error("Напишите лекарство и время — например «Таблетка от давления», «9:00, 21:00».");
  const ids = ts.map(t => { let at = srTodayAt(t); if (at < new Date()) at = new Date(at.getTime() + 864e5); return addAlarm(`Выпить: ${text}`, at, "reminder", "daily", "").id; });
  const meds = srConf().meds.concat([{ id: "m" + Date.now().toString(36), text, times: ts, ids }]);
  srSave({ meds }); return meds[meds.length - 1];
}
function srMedDel(id) {
  const m = srConf().meds.find(x => x.id === id); if (!m) return;
  (m.ids || []).forEach(a => { try { alarmCancelAll(a); } catch (e) { } });
  srSave({ meds: srConf().meds.filter(x => x.id !== id) });
}
/* лекарства на сегодня: [{med, time, at, rid, taken}] — отметка: «Выпил(а) ✓» в окне напоминания (Дела, rid) или голосом */
function srMedsToday() {
  const from = new Date(); from.setHours(0, 0, 0, 0);
  const done = doneList().filter(x => x.at >= from.getTime());
  const out = [];
  srConf().meds.forEach(m => (m.times || []).forEach((t, i) => {
    const at = srTodayAt(t), rid = (m.ids || [])[i] || "";
    out.push({ med: m, time: t, at, rid, taken: done.some(x => x.rid && x.rid === rid && x.at >= at.getTime() - 3600e3) });
  }));
  return out.sort((a, b) => a.at - b.at);
}
/* «выпила» голосом — ближайшее прошедшее неотмеченное лекарство (за 3 часа) */
function srTakenVoice() {
  const now = Date.now(), m = srMedsToday().filter(x => !x.taken && x.at.getTime() <= now + 15 * 6e4 && now - x.at.getTime() < 3 * 3600e3).pop();
  if (!m) return "";
  doneAdd([{ title: `Выпить: ${m.med.text}`, rid: m.rid, at: now }], "voice");
  return `Хорошо, отметила: ${m.med.text} в ${m.time} — ${srG("выпила", "выпил")}. Спасибо!`;
}
/* ---------- разговор: сказанное человеком (из ask) -> ответ без модели или "" ---------- */
function srHeard(text) {
  if (!srOn()) return "";
  const d = srDay(), t = Math.round(Date.now() / 1000); d.talk = [d.talk[0] || t, t]; srDaySave(d);
  const c = srConf(), s = String(text || "");
  if (c.scam && !SR_NOT.test(s) && SR_SCAM.some(rx => rx.test(s))) {
    const ws = srWatchers(), names = ws.map(p => p.name).join(", ");
    d.alerts.push({ ts: t, kind: "scam", text: s.slice(0, 200) }); srDaySave(d);
    if (ws.length) srSend(`⚠️ Это Лира, помощница. ${srWho()} ${srG("рассказала", "рассказал")}: «${s.trim().slice(0, 160)}». Похоже на мошенников — я сказала ничего не переводить и не называть коды. Позвоните ${srG("ей", "ему")}, пожалуйста.`);
    plog("info", "🛡 Для старших: похоже на мошенников" + (ws.length ? " — написала близким" : ""));
    const lead = c.name ? `${c.name}, стоп.` : "Стоп.";
    return `${lead} Это очень похоже на мошенников. Никому не называйте коды из СМС и данные карты и никуда не переводите деньги. Банк, полиция и врачи так не звонят. Если торопят и пугают — просто положите трубку.`
      + (ws.length ? ` Я уже написала ${names} — вам перезвонят.` : " Позвоните сейчас сыну или дочери и расскажите.");
  }
  if (SR_TAKEN.test(s.trim()) && s.length < 60) return srTakenVoice();
  return "";
}
function srPrompt() {
  if (!srOn()) return "";
  const n = srConf().name;
  return "РЕЖИМ «ДЛЯ СТАРШИХ». С тобой говорит пожилой человек" + (n ? `: ${n}, обращайся так` : "") + ". Говори просто, тепло и неторопливо: короткие фразы, обычные слова — без иностранных и технических терминов, без списков и значков. Числа, время и даты называй ясно. Если просят повторить или не поняли — терпеливо повтори другими словами. Перед любым действием (звонок, сообщение, покупка, удаление) переспроси. Никогда не советуй переводить деньги, называть коды из СМС, данные карты или пароли — если о таком просят по телефону, это мошенники: скажи об этом прямо и предложи позвонить детям. Если человек грустит или одинок — поддержи и предложи позвонить близким.";
}
/* ---------- раз в минуту: лекарства, днём «тишина», вечером «всё хорошо» ---------- */
function srSummary(d) {
  const who = srWho(), talk = d.talk || [], hm = (u) => new Date(u * 1000).toTimeString().slice(0, 5);
  const line = talk.length ? `${who} сегодня ${srG("говорила", "говорил")} со мной` + (hm(talk[0]) !== hm(talk[1]) ? ` — с ${hm(talk[0])} до ${hm(talk[1])}` : ` в ${hm(talk[0])}`)
    : `${who} сегодня со мной не ${srG("говорила", "говорил")}`;
  const meds = srMedsToday().filter(x => x.at <= new Date());
  const med = meds.map(x => `${x.time} ${x.med.text} — ${x.taken ? srG("выпила", "выпил") : srG("не отметила", "не отметил")}`).join("; ");
  const ok = talk.length && meds.every(x => x.taken);
  return "Это Лира, помощница. " + (ok ? "Всё хорошо. " : "") + line + "." + (med ? ` Лекарства: ${med}.` : "") + (ok ? "" : " Может, позвоните?");
}
async function srTick() {
  if (!srOn() || !srWatchers().length || !syncCred()) return;
  const c = srConf(), d = srDay(), now = new Date(), hm = now.getHours() * 60 + now.getMinutes();
  for (const x of srMedsToday()) {
    const key = "late:" + x.rid + ":" + x.time;
    if (!x.taken && now - x.at > SR_LATE * 6e4 && now - x.at < 6 * 3600e3 && !d.sent.includes(key)) {
      d.sent.push(key); srDaySave(d);
      await srSend(`Это Лира, помощница: ${srWho()} не ${srG("отметила", "отметил")} «${x.med.text}» в ${x.time} — я напомнила. Может, позвоните?`);
    }
  }
  if (c.noon && hm >= 12 * 60 && hm < 18 * 60 && !d.sent.includes("noon")) {
    d.sent.push("noon"); srDaySave(d);
    if (!d.talk.length && !srMedsToday().some(x => x.taken)) await srSend(`Это Лира, помощница: ${srWho()} сегодня ещё не ${srG("говорила", "говорил")} со мной. Может, позвоните?`);
  }
  const ck = srTodayAt(c.checkin || "20:00");
  if (ck && now >= ck && !d.sent.includes("eve")) { d.sent.push("eve"); srDaySave(d); await srSend(srSummary(d)); }
}
setInterval(() => { srTick().catch(e => plog("warn", "для старших: " + e.message)); }, 60000);
/* ---------- лист «Для старших» («Всё» → «Для старших») ---------- */
function srHtml() {
  const c = srConf(), st = clLoad(), today = srMedsToday();
  return `<p class="hint" style="margin-top:0">Для мамы, папы, бабушки: крупно и просто, лекарства с «выпили?», вечером — «всё хорошо» вам, и защита от мошенников. Обычно включают дети — прямо на телефоне родителей.</p>
    <div class="card"><div class="sw"><div>Включить «Для старших»<small>${c.on ? "крупнее, проще, Лира говорит неторопливо" : "сейчас обычный режим"}</small></div><label class="tg"><input type="checkbox" id="sr-on" ${c.on ? "checked" : ""}><i></i></label></div></div>
    <h3>Кто пользуется</h3><div class="card">
      <input id="sr-name" class="grname" maxlength="30" placeholder="Как обращаться — например, Мария Ивановна" value="${esc(c.name)}">
      <div class="tabs" id="sr-g" style="margin-top:10px"><button data-g="f" class="${c.gender !== "m" ? "on" : ""}">Она</button><button data-g="m" class="${c.gender === "m" ? "on" : ""}">Он</button></div></div>
    <h3>Кто присматривает</h3><div class="card">${st.people.length ? `<div class="grpick" style="margin:0">${st.people.map(p => `<label class="grpk${(c.watchers || []).includes(p.pid) ? " on" : ""}"><input type="checkbox" data-w="${esc(p.pid)}" ${(c.watchers || []).includes(p.pid) ? "checked" : ""}>${clAvaH(p.pid, p.name, p.face)}<span>${esc(p.name)}</span><i class="grck"></i></label>`).join("")}</div>
      <p class="hint" style="margin:10px 2px 0">Им Лира напишет через «Близкие»: не отмеченное лекарство, тишина с утра, «всё хорошо» вечером, мошенники.</p>
      <button class="btn w" id="sr-test" style="margin-top:10px" ${(c.watchers || []).length ? "" : "disabled"}>Проверить — отправить пробное сообщение</button>`
      : `<p class="hint" style="margin:0">Сначала добавьте сына или дочь в «Близкие» — им Лира будет писать.</p><button class="btn w" id="sr-close" style="margin-top:10px">Открыть «Близкие»</button>`}</div>
    <h3>Лекарства</h3><div class="card">
      ${c.meds.length ? c.meds.map(m => `<div class="srmed"><span><b>${esc(m.text)}</b><small>каждый день в ${m.times.join(", ")}</small>${today.filter(x => x.med.id === m.id && x.at <= new Date()).map(x => `<em class="${x.taken ? "ok" : ""}">сегодня в ${x.time}: ${x.taken ? "✓ " + srG("выпила", "выпил") : "не отмечено"}</em>`).join("")}</span><button class="btn sm ghost" data-md="${esc(m.id)}">Убрать</button></div>`).join("") : `<p class="hint" style="margin:0 0 8px">Лира напомнит и спросит «выпили?» — в окне напоминания будет кнопка «Выпил(а) ✓». Можно и сказать: «выпила».</p>`}
      <input id="sr-mt" class="grname" maxlength="80" placeholder="Лекарство — например, Таблетка от давления" style="margin-top:8px"><div class="row2" style="margin-top:8px"><input id="sr-mh" class="grname" placeholder="Время: 9:00, 21:00"><button class="btn" id="sr-madd">Добавить</button></div></div>
    <h3>Присмотр</h3><div class="card">
      <div class="sw"><div>Вечером — «всё хорошо»<small>сводка дня присматривающим в <input id="sr-ck" class="srck" value="${esc(c.checkin)}" maxlength="5" inputmode="numeric" aria-label="Время сводки"></small></div><label class="tg"><input type="checkbox" checked disabled><i></i></label></div>
      <div class="sw"><div>Если с утра тишина<small>в 12:00 — «может, позвоните?»</small></div><label class="tg"><input type="checkbox" id="sr-noon" ${c.noon ? "checked" : ""}><i></i></label></div>
      <div class="sw"><div>Защита от мошенников<small>«звонят из банка», «код из СМС» — сразу «стоп» и сообщение вам</small></div><label class="tg"><input type="checkbox" id="sr-scam" ${c.scam ? "checked" : ""}><i></i></label></div></div>
    <p class="hint" style="margin:12px 4px">Проверки идут, пока приложение работает. Чтобы и в фоне — «Близкие» → «Сообщения и звонки — сразу».</p>`;
}
function openSenior() {
  if (!$("#sh-senior")) { const s = document.createElement("section"); s.className = "sheet tall"; s.id = "sh-senior"; s.setAttribute("aria-labelledby", "sr-h");
    s.innerHTML = `<div class="grab"></div><h2 id="sr-h">Для старших</h2><div id="sr-body"></div>`; document.body.appendChild(s); }
  srRender(); openSheet("#sh-senior");
}
function srRender() {
  const box = $("#sr-body"); if (!box) return;
  box.innerHTML = srHtml(); clFacesFill(box);
  $("#sr-on").onchange = () => { srSave({ on: $("#sr-on").checked }); toast($("#sr-on").checked ? "«Для старших» включён — крупно и просто" : "Обычный режим"); srRender(); };
  $("#sr-name").onchange = () => srSave({ name: $("#sr-name").value.trim() });
  $$("#sr-g [data-g]").forEach(b => b.onclick = () => { srSave({ gender: b.dataset.g }); srRender(); });
  $$("#sr-body input[data-w]").forEach(x => x.onchange = () => { const w = new Set(srConf().watchers); x.checked ? w.add(x.dataset.w) : w.delete(x.dataset.w); srSave({ watchers: [...w] }); srRender(); });
  if ($("#sr-close")) $("#sr-close").onclick = () => openClose("");
  if ($("#sr-test")) $("#sr-test").onclick = async () => { const n = await srSend(`Это Лира, помощница. ${srWho()} ${srG("включила", "включил")} режим «Для старших» — сюда я буду писать, если что-то не так, и вечером — «всё хорошо».`); toast(n ? `Отправлено: ${n}` : "Не отправилось — проверьте интернет", 3500); };
  $("#sr-madd").onclick = () => { try { const m = srMedAdd($("#sr-mt").value, $("#sr-mh").value); toast(`Напомню: ${m.text} — в ${m.times.join(", ")}`, 3500); srRender(); } catch (e) { toast(e.message, 4500); } };
  $$("#sr-body [data-md]").forEach(b => b.onclick = () => { if (confirm("Убрать лекарство и его напоминания?")) { srMedDel(b.dataset.md); srRender(); } });
  $("#sr-ck").onchange = () => { const v = $("#sr-ck").value.trim().replace(".", ":"); if (/^\d{1,2}:\d{2}$/.test(v)) srSave({ checkin: v.padStart(5, "0") }); else toast("Время — например 20:00"); };
  $("#sr-noon").onchange = () => srSave({ noon: $("#sr-noon").checked });
  $("#sr-scam").onchange = () => srSave({ scam: $("#sr-scam").checked });
}
srApply();
