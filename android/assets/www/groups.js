/* «Группы своих» в «Близких» (0.61; владелец 28.10: «небольшие группы своих — семья, друзья», «да, нужно будет»).
   Группа — до 12 человек: создаёт тот, кто зовёт, из своих близких; участники видят друг друга и пишут всем сразу, даже если
   не близкие между собой. Сервер (cloud.php /close/group, /close/gsend): состав и ящики; письмо — один конверт на все
   устройства участников (closecrypto encryptFor), сервер его не прочтёт. История — в close.json: hist[gid], у входящих
   from (pid) и who (имя). Голосом: «напиши в группу Семья: …» — close_send с именем группы. */
"use strict";
const GR_MAX = 12;
let grNew = null;                                   // мастер «Новая группа»: { name, pids: Set }
let grInfo = "";                                    // у какой группы открыт «Участники» (gid)
const grList = () => clLoad().groups || [];
const grOf = (gid) => grList().find(g => g.gid === gid) || null;
const grNames = (g) => (g.members || []).map(m => String(m.name || "").split(/\s+/)[0]).filter(Boolean);
function grMatch(who) {
  const w = String(who || "").toLowerCase().replace(/ё/g, "е").replace(/^(?:в\s+)?(?:групп[аеуы]|чат[еу]?)\s+/, "").replace(/[«»"]/g, "").trim();
  if (!w) return null;
  const n = (g) => String(g.name || "").toLowerCase().replace(/ё/g, "е");
  return grList().find(g => n(g) === w) || grList().find(g => w.length >= 3 && (n(g).startsWith(w) || w.startsWith(n(g)))) || null;
}
function grTargets(g) {
  const t = {}, add = (devs) => (devs || []).forEach(d => { if (d.pub) t[d.dev] = DC().b64d(d.pub); });
  (g.members || []).forEach(m => add(m.devs)); add((CLS.me || {}).devs); const k = clKeys(); t[k.dev] = DC().b64d(k.pub); return t;
}
/* открытый ключ отправителя письма в группу: участник может быть и не близким */
function grPubOf(gid, peer, dev) {
  const g = grOf(gid); const m = g && (g.members || []).find(x => x.pid === peer), d = m && (m.devs || []).find(x => x.dev === dev);
  return d ? DC().b64d(d.pub) : null;
}
async function grSend(gid, text, files, extra) {
  clLoad(); if (!CLS.me.pid || Date.now() - (CLS.hello || 0) > 600000) await clHello();
  const g = grOf(gid); if (!g) throw new Error("Такой группы больше нет.");
  if (!(g.members || []).some(m => (m.devs || []).length)) throw new Error(`В «${g.name}» ещё никто не открывал Dewiar — сообщение не дойдёт.`);
  const k = clKeys(), fl = [];
  for (const f of files || []) {
    if (f.bytes.length > 10 * 1024 * 1024) throw new Error(`«${f.name}» больше 10 МБ — такие пока не отправить.`);
    const fk = DC().randomBytes(32), blob = DC().seal(fk, f.bytes);
    const d = await clReq("POST", "/close/file", clStdB64(blob), "&b64=1&g=" + encodeURIComponent(gid));
    fl.push({ id: d.id, name: f.name, size: f.bytes.length, type: f.type || "", key: DC().b64e(fk) });
    if (typeof clIsImg === "function" && clIsImg(f)) await clImgPut(d.id, f.bytes, f.type);
  }
  const body = Object.assign({}, extra || {}, { t: String(text || "").trim(), ts: Date.now(), mid: Math.random().toString(36).slice(2, 12) + Date.now().toString(36), name: CLS.me.name || "", g: gid });
  if (fl.length) body.f = fl;
  if (!body.t && !fl.length) throw new Error("пустое сообщение");
  const d = await clReq("POST", "/close/gsend", { gid, env: DC().encryptFor(body, DC().b64d(k.priv), k.dev, grTargets(g)) });
  const it = { mid: body.mid, ts: body.ts, out: true, t: body.t, f: fl, sid: +d.id || 0 };   // sid — номер письма: «прочитали»
  if (body.rem) it.rem = { at: body.rem.at, id: grRemind(g, body.rem, "") };      // «напомни всем» — и мне
  clAdd(gid, it); plog("info", `💌 в группу «${g.name}» ← ${clip(body.t || "файл")}`);
  return Object.assign({ to: `в группу «${g.name}»` }, it);
}
/* реакция в группе: всем участникам, у себя — сразу */
async function grReact(gid, mid, e) {
  const g = grOf(gid); if (!g) throw new Error("Такой группы больше нет.");
  const was = (((clLoad().hist[gid] || []).find(x => x.mid === mid) || {}).rx || {}).me || "";
  clReAt(gid, mid, "me", e);
  try { const k = clKeys(), body = { re: mid, e, t: e, ts: Date.now(), mid: Math.random().toString(36).slice(2, 12) + Date.now().toString(36), name: CLS.me.name || "", g: gid };
    await clReq("POST", "/close/gsend", { gid, env: DC().encryptFor(body, DC().b64d(k.priv), k.dev, grTargets(g)) }); }
  catch (x) { clReAt(gid, mid, "me", was); throw x; }
}
const grRx = (m) => Object.values(m.rx || {}).filter(Boolean);
/* «прочитано» в группе: открыли переписку — сайту номер последнего входящего; у своих писем — кто уже прочитал */
function grSeen(gid) {
  const st = clLoad(), top = Math.max(0, ...(st.hist[gid] || []).filter(m => !m.out).map(m => +m.sid || 0));
  if (!top || top <= (+(st.readUp || {})[gid] || 0) || document.hidden) return;
  clReq("POST", "/close/gseen", { gid, upto: top }).then(() => { const s = clLoad(); s.readUp = Object.assign({}, s.readUp, { [gid]: top }); clSave(); }).catch(() => { });
}
function grReaders(g, m) {
  if (!m.out || !m.sid) return "";
  const mk = (clLoad().gmarks || {})[g.gid] || {}, who = (g.members || []).filter(p => (mk[p.pid] || 0) >= m.sid);
  if (!who.length) return "";
  return who.length === (g.members || []).length ? "прочитали все" : "прочитал" + (who.length > 1 ? "и" : "") + ": " + who.map(p => String(p.name || "").split(/\s+/)[0]).join(", ");
}
/* долгое нажатие в группе: реакции, «Переслать», «Удалить у меня» */
function grReBind(g, h) {
  let t = 0;
  const open = (el) => {
    clReClose(); const m = h[+el.dataset.i]; if (!m || !m.mid) return;
    D.vibrate(15);
    const pop = document.createElement("div"); pop.className = "clrepick"; pop.setAttribute("role", "menu");
    pop.innerHTML = `<div class="emos">${CL_EMO.map(e => `<button role="menuitem" data-e="${e}" class="${(m.rx || {}).me === e ? "on" : ""}" aria-label="Реакция ${e}">${clEmo(e)}</button>`).join("")}</div>
      <div class="acts"><button role="menuitem" class="fw">${AL_IC.fwd}Переслать</button><button role="menuitem" class="dl">Удалить у меня</button></div>`;
    document.body.appendChild(pop);
    const r = el.getBoundingClientRect(), w = pop.offsetWidth;
    pop.style.left = Math.max(8, Math.min(innerWidth - w - 8, m.out ? r.right - w : r.left)) + "px";
    pop.style.top = Math.max(8, r.top - pop.offsetHeight - 8) + "px";
    $(".fw", pop).onclick = () => { clReClose(); clFwdPick({ t: m.t || "", f: m.f || [] }); };
    $(".dl", pop).onclick = () => { clReClose(); clForget(g.gid, [m.mid]); clRender(); toast("Удалено на этом телефоне — у остальных осталось", 3000); };
    $$("button[data-e]", pop).forEach(b => b.onclick = async () => { const e = (m.rx || {}).me === b.dataset.e ? "" : b.dataset.e; clReClose();
      try { await grReact(g.gid, m.mid, e); } catch (x) { toast(x.message, 4000); } clRender(); });
    setTimeout(() => document.addEventListener("pointerdown", clReOut, true), 0);
  };
  $$("#cl-msgs .clm").forEach(el => {
    el.addEventListener("pointerdown", (e) => { if (e.target.closest(".clph, .clf")) return; clearTimeout(t); t = setTimeout(() => open(el), 450); });
    ["pointerup", "pointerleave", "pointercancel", "pointermove"].forEach(k => el.addEventListener(k, (e) => { if (k !== "pointermove" || Math.abs(e.movementY) + Math.abs(e.movementX) > 6) clearTimeout(t); }));
    el.addEventListener("contextmenu", (e) => { e.preventDefault(); open(el); });
  });
}
/* «Лира в группе»: напоминание у каждого участника. -> id будильника или "" */
function grRemind(g, rem, who) {
  const at = +(rem || {}).at;
  if (!at || at < Date.now() - 60000 || at > Date.now() + 366 * 864e5) return "";
  try { const x = addAlarm(`«${g ? g.name : "Группа"}»: ${String(rem.t || "напоминание").slice(0, 300)}${who ? ` (просит ${String(who).split(/\s+/)[0]})` : ""}`, new Date(at), "reminder", "", ""); syncSoon(); return x.id || ""; }
  catch (e) { plog("warn", "группа: напоминание не встало — " + e.message); return ""; }
}
/* входящее из clPoll: kind «grp» уже расшифровано */
function grIn(it, body) {
  const gid = String((it.env || {}).g || body.g || ""), g = grOf(gid);
  if (!gid) return false;
  if (body.re) {                                     // реакция в группе — значком у сообщения (rx[кто])
    const e = String(body.e || "").slice(0, 8);
    if (clReAt(gid, String(body.re), it.out ? "me" : it.peer, e) && !it.out) {
      if (clCur === gid && $("#sh-close").classList.contains("on")) clRender();
      else if (!document.hidden && e) toast(`${String(it.name || "Кто-то").split(/\s+/)[0]}: ${e} в «${g ? g.name : "группе"}»`, 2600);
    }
    return false;
  }
  const m = { mid: body.mid || String(it.id), ts: +body.ts || it.ts * 1000, out: !!it.out, t: String(body.t || "").slice(0, 20000),
    f: (body.f || []).filter(x => x && typeof x === "object").slice(0, 10), from: it.peer, who: it.name || body.name || "", sid: +it.id || 0 };
  const known = (clLoad().hist[gid] || []).some(x => x.mid === m.mid);
  if (body.rem && !m.out && !known) m.rem = { at: +body.rem.at, id: grRemind(g, body.rem, m.who) };   // «напомни всем» — встаёт само
  if (!clAdd(gid, m) || m.out) return false;
  const st = clLoad();
  if (!(clCur === gid && $("#sh-close").classList.contains("on"))) { st.unread[gid] = (st.unread[gid] || 0) + 1; clSave(); }
  const name = `${String(m.who || "Кто-то").split(/\s+/)[0]} в «${g ? g.name : "группе"}»`;
  clTell(name, m.rem && m.rem.id ? Object.assign({}, m, { t: `${m.t} — напомню ${whenText(new Date(m.rem.at))}` }) : m, gid);
  return true;
}
async function grOp(body, ok) {
  const d = await clReq("POST", "/close/group", body);
  const st = clLoad(); st.groups = d.groups || st.groups; clSave();
  if (ok) toast(ok);
  return d;
}
/* ---------- вид: список групп в «Близких», переписка группы, «Новая группа», «Участники» ---------- */
const GR_IC = '<svg viewBox="0 0 24 24"><circle cx="9" cy="9" r="3.2"/><path d="M3.5 19a5.5 5.5 0 0 1 11 0"/><circle cx="17" cy="10" r="2.6"/><path d="M15.5 14.6A4.6 4.6 0 0 1 21 19"/></svg>';
function grStack(g, n = 3) {
  const ms = (g.members || []).slice(0, n);
  return `<div class="grstack">${ms.map(m => clAvaH(m.pid, m.name, m.face)).join("")}${(g.members || []).length > n ? `<i class="clava more">+${g.members.length - n}</i>` : ""}</div>`;
}
/* Значок группы (0.68, владелец: «можно ли задавать иконку к самой группе»): эмодзи на мягкой плашке цвета группы;
   нет значка — лица участников, как раньше. Ставит создатель — в «Новой группе» и в «Участниках». */
const GR_ICONS = ["👨‍👩‍👧", "🏠", "❤️", "💼", "🎉", "⚽", "🎓", "🌿", "🐾", "✈️", "🍳", "🎵", "💡", "🛠️", "🎮", "☀️"];
const grAva = (g, n = 3) => g && g.icon ? `<i class="grico" style="--c:${clCol(g.gid || "g")}" aria-hidden="true">${esc(g.icon)}</i>` : grStack(g, n);
const grIconPick = (cur) => `<div class="gremos" role="radiogroup" aria-label="Значок группы"><button type="button" class="grem grem0${cur ? "" : " on"}" data-ic="" role="radio" aria-checked="${!cur}">Аа</button>${GR_ICONS.map(e => `<button type="button" class="grem${e === cur ? " on" : ""}" data-ic="${e}" role="radio" aria-checked="${e === cur}">${e}</button>`).join("")}</div>`;
function grIconWire(box, onPick) {
  $$(".grem", box).forEach(b => b.onclick = () => { $$(".grem", box).forEach(x => { x.classList.toggle("on", x === b); x.setAttribute("aria-checked", x === b); }); onPick(b.dataset.ic); });
}
function grListHtml(st) {
  const gs = st.groups || [];
  if (!st.people.length && !gs.length) return "";
  const last = (g) => { const l = (st.hist[g.gid] || []).slice(-1)[0]; return l ? esc((l.out ? "Вы: " : (String(l.who || "").split(/\s+/)[0] || "Кто-то") + ": ") + (l.t || "📎 " + ((l.f || [])[0] || {}).name))
    : esc(grNames(g).join(", ") || "пока только вы"); };
  return `<div class="grhead"><h3>Группы</h3><button class="btn sm" id="gr-new">${GR_IC}Новая группа</button></div>`
    + (gs.length ? gs.map(g => `<div class="clp grp" data-gid="${esc(g.gid)}">${grAva(g)}<span><b>${esc(g.name)}</b><small>${last(g)}</small></span>${st.unread[g.gid] ? `<em>${st.unread[g.gid]}</em>` : ""}</div>`).join("")
      : `<p class="hint grnone">Семья, друзья, соседи — пишите всем сразу. Создайте группу из своих близких.</p>`);
}
function grNewHtml(st) {
  const sel = grNew.pids;
  return `<div class="clh"><button class="ib soft" id="gr-x" aria-label="Назад"><svg viewBox="0 0 24 24"><path d="m15 5-7 7 7 7"/></svg></button><div style="flex:1"><b>Новая группа</b><small>до ${GR_MAX} человек вместе с вами</small></div></div>
    <input id="gr-name" class="grname" maxlength="40" placeholder="Название — например, Семья" value="${esc(grNew.name || "")}">
    <p class="hint" style="margin:14px 4px 8px">Значок</p>${grIconPick(grNew.icon || "")}
    <p class="hint" style="margin:14px 4px 8px">Кого позвать — из ваших близких${sel.size ? ` · выбрано ${sel.size}` : ""}</p>
    <div class="grpick">${st.people.map(p => `<label class="grpk${sel.has(p.pid) ? " on" : ""}"><input type="checkbox" data-pid="${esc(p.pid)}" ${sel.has(p.pid) ? "checked" : ""}>${clAvaH(p.pid, p.name, p.face)}<span>${esc(p.name)}</span><i class="grck"></i></label>`).join("")}</div>
    <button class="btn p w" id="gr-make" ${sel.size && (grNew.name || "").trim() ? "" : "disabled"}>Создать группу</button>
    <p class="hint" style="margin:10px 4px 0">Участники увидят друг друга — имя и фото — и смогут писать всем, даже если не знакомы между собой. Сообщения шифруются на устройствах.</p>`;
}
function grInfoHtml(st, g) {
  const add = g.mine ? st.people.filter(p => !(g.members || []).some(m => m.pid === p.pid)) : [];
  const ownerName = g.mine ? "вы" : ((g.members || []).find(m => m.pid === g.owner) || {}).name || "участник";
  return `<div class="clh"><button class="ib soft" id="gr-ix" aria-label="Назад"><svg viewBox="0 0 24 24"><path d="m15 5-7 7 7 7"/></svg></button><div style="flex:1;min-width:0"><b>${esc(g.name)}</b><small>${(g.members || []).length + 1} в группе · создал${g.mine ? "и вы" : "(а) " + esc(ownerName)}</small></div></div>
    ${g.mine ? `<div class="row2"><input id="gr-rn" class="grname" maxlength="40" value="${esc(g.name)}" aria-label="Название группы"><button class="btn sm" id="gr-rn-go">Переименовать</button></div>
      <p class="hint" style="margin:12px 4px 8px">Значок — увидят все в группе</p>${grIconPick(g.icon || "")}` : ""}
    <h3>Участники</h3>
    <div class="clp me">${clAvaH(st.me.pid || "me", st.me.name || "Я", st.me.face)}<span><b>Вы</b><small>${g.mine ? "создали группу" : "участник"}</small></span></div>
    ${(g.members || []).map(m => `<div class="clp">${clAvaH(m.pid, m.name, m.face)}<span><b>${esc(m.name)}</b><small>${m.pid === g.owner ? "создал(а) группу" : st.people.some(p => p.pid === m.pid) ? "ваш близкий" : "не в ваших близких — только в группе"}</small></span>${g.mine ? `<button class="btn sm ghost" data-drop="${esc(m.pid)}">Убрать</button>` : ""}</div>`).join("")}
    ${add.length && (g.members || []).length + 1 < GR_MAX ? `<h3>Позвать ещё</h3><div class="grpick">${add.map(p => `<label class="grpk"><input type="checkbox" data-add="${esc(p.pid)}">${clAvaH(p.pid, p.name, p.face)}<span>${esc(p.name)}</span><i class="grck"></i></label>`).join("")}</div><button class="btn w" id="gr-add" disabled>Позвать в группу</button>` : ""}
    <button class="btn w bad" id="gr-leave" style="margin-top:18px">${g.mine ? "Удалить группу" : "Выйти из группы"}</button>`;
}
function grThreadHtml(st, g) {
  const h = st.hist[g.gid] || [];
  const who = (m) => m.out ? "" : `<b class="grwho" style="color:${clCol(m.from || m.who)}">${esc(String(m.who || "Кто-то").split(/\s+/)[0])}</b>`;
  return `<div class="clh"><button class="ib soft" id="cl-back" aria-label="Назад"><svg viewBox="0 0 24 24"><path d="m15 5-7 7 7 7"/></svg></button>${grAva(g, 2)}
      <button class="grtitle" id="gr-info"><b>${esc(g.name)}</b><small>${esc(["вы"].concat(grNames(g)).join(", "))}</small></button>
      <button class="ib soft" id="cl-album" title="Фото и файлы" aria-label="Фото и файлы">${AL_IC.album}</button><button class="ib soft" id="gr-info2" aria-label="Участники">${GR_IC}</button></div>
    <div class="clmsgs" id="cl-msgs">${h.map((m, i) => `<div class="clm ${m.out ? "out" : ""}${grRx(m).length ? " rx" : ""}${clEmoOnly(m.t) ? " emo" : ""}" data-i="${i}">${who(m)}${m.t ? `<div>${clEmo(esc(m.t))}</div>` : ""}${(m.f || []).map((f, j) => clFileHtml(f, i, j)).join("")}${m.rem ? `<span class="grrem">⏰ напомню всем ${esc(whenText(new Date(m.rem.at)))}</span>` : ""}<time>${clTime(m.ts)}${m.pend ? clTick(m, g.gid) : grReaders(g, m) ? ` · ${esc(grReaders(g, m))}` : ""}</time>${grRx(m).length ? `<span class="clrx">${clEmo(esc(grRx(m).join("")))}</span>` : ""}</div>`).join("")
      || `<p class="hint" style="text-align:center;margin:24px 8px">Напишите первое сообщение всем — или скажите: «Напиши в группу ${esc(g.name)}: …»</p>`}</div>
    <div class="clatts" id="cl-atts">${clFiles.map((f, i) => `<span>${esc(f.name)} <button data-i="${i}">✕</button></span>`).join("")}</div>
    <div class="clemo" id="cl-emo" hidden>${clEmoHtml()}</div>
    <div class="clsend"><button class="ib att" id="cl-emo-b" aria-label="Эмодзи" aria-expanded="false"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8.5"/><path d="M8.5 14a4.2 4.2 0 0 0 7 0"/><path d="M9 9.6v.01M15 9.6v.01"/></svg></button><label class="ib att"><input type="file" id="cl-file" multiple hidden><svg viewBox="0 0 24 24"><path d="M20.5 11.5 12.6 19.4a5 5 0 0 1-7.1-7.1l8.3-8.3a3.4 3.4 0 0 1 4.8 4.8l-8.3 8.3a1.7 1.7 0 0 1-2.4-2.4l7.6-7.6"/></svg></label>
      <textarea id="cl-text" rows="1" placeholder="Сообщение всем…"></textarea><button class="ib" id="cl-go" aria-label="Отправить"><svg viewBox="0 0 24 24"><path d="M4 12 20 4l-6 16-2.5-6.5z"/></svg></button></div>`;
}
/* clRender зовёт это первым: true — нарисовано здесь (мастер, переписка группы или «Участники») */
function grRender(box) {
  const st = clLoad();
  if (grNew) {
    box.innerHTML = grNewHtml(st);
    $("#gr-x").onclick = () => { grNew = null; clRender(); };
    $("#gr-name").oninput = () => { grNew.name = $("#gr-name").value; $("#gr-make").disabled = !(grNew.pids.size && grNew.name.trim()); };
    grIconWire(box, (ic) => { grNew.icon = ic; });
    $$(".grpick input[data-pid]").forEach(c => c.onchange = () => {
      if (c.checked && grNew.pids.size + 2 > GR_MAX) { c.checked = false; return toast(`В группе — до ${GR_MAX} человек`); }
      c.checked ? grNew.pids.add(c.dataset.pid) : grNew.pids.delete(c.dataset.pid); grRender(box); });
    $("#gr-make").onclick = async () => { $("#gr-make").disabled = true;
      try { const d = await grOp({ op: "create", name: grNew.name.trim(), pids: [...grNew.pids], icon: grNew.icon || "" }, `Группа «${grNew.name.trim()}» создана`); grNew = null; clCur = d.gid; clRender(); }
      catch (e) { toast(e.message, 4000); $("#gr-make").disabled = false; } };
    clFacesFill(box); return true;
  }
  const g = clCur && clCur[0] === "g" ? grOf(clCur) : null;
  if (!g) return false;
  if (grInfo === g.gid) {
    box.innerHTML = grInfoHtml(st, g); clFacesFill(box);
    $("#gr-ix").onclick = () => { grInfo = ""; clRender(); };
    if (g.mine) grIconWire(box, (ic) => grOp({ op: "icon", gid: g.gid, icon: ic }, ic ? "Значок группы поставлен" : "Значок убран").then(() => clRender()).catch(e => toast(e.message, 4000)));
    if ($("#gr-rn-go")) $("#gr-rn-go").onclick = () => { const n = $("#gr-rn").value.trim(); if (n) grOp({ op: "rename", gid: g.gid, name: n }, "Переименовано").then(() => clRender()).catch(e => toast(e.message, 4000)); };
    $$("[data-drop]").forEach(b => b.onclick = () => { const m = g.members.find(x => x.pid === b.dataset.drop);
      if (confirm(`Убрать ${m ? m.name : "участника"} из «${g.name}»?`)) grOp({ op: "drop", gid: g.gid, pid: b.dataset.drop }, "Убран(а) из группы").then(() => clRender()).catch(e => toast(e.message, 4000)); });
    const sel = () => $$(".grpick input[data-add]:checked").map(c => c.dataset.add);
    $$(".grpick input[data-add]").forEach(c => c.onchange = () => { c.closest(".grpk").classList.toggle("on", c.checked); $("#gr-add").disabled = !sel().length; });
    if ($("#gr-add")) $("#gr-add").onclick = () => grOp({ op: "add", gid: g.gid, pids: sel() }, "Позвали в группу").then(() => clRender()).catch(e => toast(e.message, 4000));
    $("#gr-leave").onclick = () => {
      if (!confirm(g.mine ? `Удалить группу «${g.name}» у всех? Переписка на телефонах останется.` : `Выйти из «${g.name}»? Новые сообщения группы перестанут приходить.`)) return;
      grOp({ op: g.mine ? "delete" : "leave", gid: g.gid }, g.mine ? "Группа удалена" : "Вы вышли из группы").then(() => { grInfo = ""; clCur = ""; clRender(); }).catch(e => toast(e.message, 4000));
    };
    return true;
  }
  delete st.unread[g.gid]; clSave(); clBadge(); grSeen(g.gid);
  box.innerHTML = grThreadHtml(st, g);
  const msgs = $("#cl-msgs"); msgs.scrollTop = msgs.scrollHeight; clFacesFill($(".clh"));
  const h = st.hist[g.gid] || [];
  clImgFill(msgs, h, { gid: g.gid }); $("#cl-album").onclick = () => clAlbum({ gid: g.gid });
  $("#cl-back").onclick = () => { clCur = ""; clRender(); };
  $("#gr-info").onclick = $("#gr-info2").onclick = () => { grInfo = g.gid; clRender(); };
  $$("#cl-atts button").forEach(b => b.onclick = () => { clFiles.splice(+b.dataset.i, 1); clRender(); });
  $$(".clf").forEach(b => b.onclick = () => clSaveFile(g, h[+b.dataset.i], +b.dataset.j));
  $("#cl-file").onchange = () => { [...$("#cl-file").files].forEach(f => { if (f.size > 10 * 1024 * 1024) { toast(`«${f.name}» больше 10 МБ`); return; }
    const fr = new FileReader(); fr.onload = () => { clFiles.push({ name: f.name, type: f.type, bytes: new Uint8Array(fr.result) }); clRender(); }; fr.readAsArrayBuffer(f); }); };
  $("#cl-go").onclick = async () => { const t = $("#cl-text").value.trim(); if (!t && !clFiles.length) return; const b = $("#cl-go");
    if (!clFiles.length) return clSendSoon(g.gid, t, () => grSend(g.gid, t, []));
    b.disabled = true;
    try { await grSend(g.gid, t, clFiles); clFiles = []; clRender(); } catch (e) { toast(e.message, 4000); b.disabled = false; } };
  $("#cl-emo-b").onclick = () => { const e = $("#cl-emo"); e.hidden = !e.hidden; $("#cl-emo-b").setAttribute("aria-expanded", String(!e.hidden)); };
  clEmoBind();
  grReBind(g, h);
  return true;
}
function grBind() {
  $$(".clp.grp").forEach(b => b.onclick = () => { clCur = b.dataset.gid; grInfo = ""; clRender(); });
  const n = $("#gr-new");
  if (n) n.onclick = () => { if (!clLoad().people.length) return toast("Сначала пригласите близких — группа собирается из них", 4000); grNew = { name: "", pids: new Set() }; clRender(); };
}
