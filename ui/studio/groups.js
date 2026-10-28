/* Студия → «Близкие» → «Группы своих» (0.61; core/close.py group/gsend, сервер /close/group). Слева под близкими — группы
   (стопка лиц, последнее сообщение, непрочитанное) и «Новая группа»; переписка группы — в том же окне, у чужих сообщений
   имя написавшего; шапка — название и участники, «Участники» открывают панель: позвать ещё, убрать (создатель),
   переименовать, удалить или выйти. Отправка — тот же close_send (pid = номер группы). */
const GR = { panel: "", pick: new Set() };
const grEsc = clEsc;
const grFirst = (n) => String(n || "").split(/\s+/)[0];
const grStack = (g, n = 3) => `<i class="cl-gstack">${(g.members || []).slice(0, n).map(m => `<i class="cl-ava" style="--c:${clColor(m.pid)}" data-face="${grEsc(m.pid)}" data-v="${+m.face || 0}">${grEsc((m.name || "?").slice(0, 1).toUpperCase())}</i>`).join("")}${(g.members || []).length > n ? `<i class="cl-ava more">+${g.members.length - n}</i>` : ""}</i>`;
const grOf = (gid) => (((CL.st || {}).groups) || []).find(g => g.gid === gid) || null;

function grSide(st) {
  const gs = st.groups || [];
  $("#cl-gh").hidden = !(st.people || []).length && !gs.length;
  $("#cl-groups").innerHTML = gs.length ? gs.map(g => `<button class="cl-p cl-g ${g.gid === CL.cur ? "cur" : ""}" data-gid="${grEsc(g.gid)}">${grStack(g, 2)}
      <span><b>${grEsc(g.name)}</b><small>${g.last && (g.last.t || (g.last.f || []).length) ? grEsc((g.last.out ? "Вы: " : grFirst(g.last.who || "Кто-то") + ": ") + (g.last.t || "📎 " + ((g.last.f[0] || {}).name || "файл"))) : grEsc((g.members || []).map(m => grFirst(m.name)).join(", "))}</small></span>
      ${g.unread ? `<em>${g.unread}</em>` : ""}</button>`).join("")
    : `<p class="hint cl-gnone">Семья, друзья — пишите всем сразу. Соберите группу из своих близких.</p>`;
  $$("#cl-groups .cl-g").forEach(b => b.onclick = () => clOpen(b.dataset.gid));
  clFaces($("#cl-groups"));
}
/* шапка переписки группы; true — это группа */
function grHead() {
  const g = grOf(CL.cur);
  if (!g) return false;
  $("#cl-empty").style.display = "none"; $("#cl-head").style.display = ""; $("#cl-send").style.display = CL.pick ? "none" : "";
  const ava = $("#cl-ava"); ava.className = "cl-ava cl-gava"; ava.style.removeProperty("--c"); ava.style.backgroundImage = ""; ava.removeAttribute("data-face");
  ava.innerHTML = grStack(g, 2); clFaces(ava);
  $("#cl-who").textContent = g.name;
  $("#cl-devs").textContent = ["вы"].concat((g.members || []).map(m => grFirst(m.name))).join(", ") + " · сообщения шифруются";
  $("#cl-devs").title = "";
  $("#cl-call").style.display = $("#cl-vcall").style.display = "none";
  $("#cl-del").style.display = "";
  $("#cl-del").textContent = "Участники";
  $("#cl-del").classList.remove("danger");
  $("#cl-del").onclick = () => grPanel("info");
  $("#cl-pick").textContent = CL.pick ? "Готово" : "Удалить сообщения";
  return true;
}
/* после переписки с человеком — кнопка снова «Убрать из близких» */
const grDelReset = () => { const b = $("#cl-del"); if (b.textContent !== "Убрать из близких") { b.textContent = "Убрать из близких"; b.classList.add("danger"); b.onclick = grDelPerson; } };
async function grDelPerson() {
  const p = ((CL.st && CL.st.people) || []).find(x => x.pid === CL.cur); if (!p) return;
  if (!await ask(`Убрать «${p.name}» из близких? Переписка у вас останется, но писать друг другу будет нельзя, пока не пригласите снова.`)) return;
  try { CL.st = await core.call("close_remove", { pid: p.pid }); CL.cur = ""; clRender(); } catch (e) { toast(e.message); }
}
function grPick(list, sel, attr) {
  return `<div class="cl-gpick">${list.map(p => `<label class="cl-gpk${sel.has(p.pid) ? " on" : ""}"><input type="checkbox" ${attr}="${grEsc(p.pid)}" ${sel.has(p.pid) ? "checked" : ""}>
    <i class="cl-ava" style="--c:${clColor(p.pid)}" data-face="${grEsc(p.pid)}" data-v="${+p.face || 0}">${grEsc((p.name || "?").slice(0, 1).toUpperCase())}</i><span>${grEsc(p.name)}</span><i class="cl-gck" aria-hidden="true"></i></label>`).join("")}</div>`;
}
/* панель вместо переписки: "new" — новая группа, "info" — участники, "" — закрыть */
function grPanel(kind) {
  GR.panel = kind;
  const box = $("#cl-gp");
  if (!kind) { if (!box.hidden) { box.hidden = true; $("#cl-chat").style.display = ""; } return; }
  clCardShow(false); $("#cl-invite").style.display = "none";
  box.hidden = false; $("#cl-chat").style.display = "none";
  const st = CL.st || {}, people = st.people || [];
  if (kind === "new") {
    GR.pick = new Set();
    box.innerHTML = `<h3>Новая группа</h3><p class="hint">До 12 человек вместе с вами. Участники увидят друг друга — имя и фото — и смогут писать всем, даже если не знакомы между собой. Сообщения шифруются на устройствах.</p>
      <label class="f"><span>Название</span><input type="text" id="gr-name" maxlength="40" placeholder="например, Семья"></label>
      <p class="hint" style="margin:14px 0 8px">Кого позвать — из ваших близких <b id="gr-n"></b></p>${grPick(people, GR.pick, "data-pid")}
      <div class="actions"><button class="btn primary" id="gr-make" disabled>Создать группу</button><button class="btn" id="gr-x">Отмена</button><span class="res" id="gr-res"></span></div>`;
    const upd = () => { $("#gr-make").disabled = !(GR.pick.size && $("#gr-name").value.trim()); $("#gr-n").textContent = GR.pick.size ? `· выбрано ${GR.pick.size}` : ""; };
    $$("#cl-gp input[data-pid]").forEach(c => c.onchange = () => {
      if (c.checked && GR.pick.size + 2 > 12) { c.checked = false; return toast("В группе — до 12 человек"); }
      c.checked ? GR.pick.add(c.dataset.pid) : GR.pick.delete(c.dataset.pid); c.closest(".cl-gpk").classList.toggle("on", c.checked); upd(); });
    $("#gr-name").oninput = upd; $("#gr-name").focus();
    $("#gr-x").onclick = () => { grPanel(""); clHead(); };
    $("#gr-make").onclick = async () => { $("#gr-make").disabled = true;
      try { const r = await core.call("close_group", { op: "create", name: $("#gr-name").value.trim(), pids: [...GR.pick] }); CL.st = r; grPanel(""); clRender(); toast(`Группа «${$("#gr-name") ? $("#gr-name").value.trim() : ""}» создана`); if (r.gid) clOpen(r.gid); }
      catch (e) { $("#gr-res").className = "res bad"; $("#gr-res").textContent = e.message; upd(); } };
    clFaces(box); return;
  }
  const g = grOf(CL.cur); if (!g) return grPanel("");
  const add = g.mine ? people.filter(p => !(g.members || []).some(m => m.pid === p.pid)) : [];
  GR.pick = new Set();
  const owner = g.mine ? "вы" : ((g.members || []).find(m => m.pid === g.owner) || {}).name || "участник";
  box.innerHTML = `<h3>${grEsc(g.name)}</h3><p class="hint">${(g.members || []).length + 1} в группе · создал${g.mine ? "и вы" : "(а) " + grEsc(owner)}</p>
    ${g.mine ? `<div class="actions" style="margin:4px 0 14px"><input type="text" id="gr-rn" maxlength="40" value="${grEsc(g.name)}" aria-label="Название группы" style="flex:1;min-width:0"><button class="btn" id="gr-rn-go">Переименовать</button></div>` : ""}
    <div class="cl-gmem"><div class="cl-gm"><i class="cl-ava" style="--c:${clColor((st.me || {}).pid || "me")}" data-face="${grEsc((st.me || {}).pid || "me")}" data-v="${+(st.me || {}).face || 0}">${grEsc(((st.me || {}).name || "Я").slice(0, 1).toUpperCase())}</i><span><b>Вы</b><small>${g.mine ? "создали группу" : "участник"}</small></span></div>
    ${(g.members || []).map(m => `<div class="cl-gm"><i class="cl-ava" style="--c:${clColor(m.pid)}" data-face="${grEsc(m.pid)}" data-v="${+m.face || 0}">${grEsc((m.name || "?").slice(0, 1).toUpperCase())}</i><span><b>${grEsc(m.name)}</b><small>${m.pid === g.owner ? "создал(а) группу" : people.some(p => p.pid === m.pid) ? "ваш близкий" : "не в ваших близких — только в группе"}</small></span>${g.mine ? `<button class="btn small" data-drop="${grEsc(m.pid)}">Убрать</button>` : ""}</div>`).join("")}</div>
    ${add.length && (g.members || []).length + 1 < 12 ? `<p class="hint" style="margin:16px 0 8px">Позвать ещё</p>${grPick(add, GR.pick, "data-add")}<button class="btn" id="gr-add" disabled>Позвать в группу</button>` : ""}
    <div class="actions" style="margin-top:18px"><button class="btn" id="gr-ix">К переписке</button><span style="flex:1"></span><button class="btn danger" id="gr-leave">${g.mine ? "Удалить группу" : "Выйти из группы"}</button></div>`;
  clFaces(box);
  const op = (a, ok) => core.call("close_group", Object.assign({ gid: g.gid }, a)).then(r => { CL.st = r; clRender(); if (ok) toast(ok); return r; }).catch(e => { toast(e.message, 4000); throw e; });
  $("#gr-ix").onclick = () => { grPanel(""); clHead(); };
  if ($("#gr-rn-go")) $("#gr-rn-go").onclick = () => { const n = $("#gr-rn").value.trim(); if (n) op({ op: "rename", name: n }, "Переименовано").then(() => grPanel("info")); };
  $$("#cl-gp [data-drop]").forEach(b => b.onclick = async () => { const m = g.members.find(x => x.pid === b.dataset.drop);
    if (await ask(`Убрать ${m ? m.name : "участника"} из «${g.name}»?`)) op({ op: "drop", pid: b.dataset.drop }, "Убран(а) из группы").then(() => grPanel("info")); });
  $$("#cl-gp input[data-add]").forEach(c => c.onchange = () => { c.checked ? GR.pick.add(c.dataset.add) : GR.pick.delete(c.dataset.add); c.closest(".cl-gpk").classList.toggle("on", c.checked); $("#gr-add").disabled = !GR.pick.size; });
  if ($("#gr-add")) $("#gr-add").onclick = () => op({ op: "add", pids: [...GR.pick] }, "Позвали в группу").then(() => grPanel("info"));
  $("#gr-leave").onclick = async () => {
    if (!await ask(g.mine ? `Удалить группу «${g.name}» у всех? Переписка у каждого останется.` : `Выйти из «${g.name}»? Новые сообщения группы перестанут приходить.`)) return;
    op({ op: g.mine ? "delete" : "leave" }, g.mine ? "Группа удалена" : "Вы вышли из группы").then(() => { grPanel(""); CL.cur = ""; clRender(); });
  };
}
$("#cl-gnew").onclick = () => { if (!((CL.st || {}).people || []).length) return toast("Сначала пригласите близких — группа собирается из них", 4000); grPanel("new"); };
/* шапка: у человека — «Убрать из близких», у группы — «Участники» */
const grHeadWas = clHead;
clHead = function () { if (!grOf(CL.cur)) { grDelReset(); const a = $("#cl-ava"); a.classList.remove("cl-gava"); if (a.querySelector(".cl-gstack")) a.innerHTML = ""; } return grHeadWas(); };
