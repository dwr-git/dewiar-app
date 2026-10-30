/* Студия → «Близкие» → «Группы своих» (0.61; core/close.py group/gsend, сервер /close/group). Слева под близкими — группы
   (стопка лиц, последнее сообщение, непрочитанное) и «Новая группа»; переписка группы — в том же окне, у чужих сообщений
   имя написавшего; шапка — название и участники, «Участники» открывают панель: позвать ещё, убрать (создатель),
   переименовать, удалить или выйти. Отправка — тот же close_send (pid = номер группы). */
const GR = { panel: "", pick: new Set() };
const grEsc = clEsc;
const grFirst = (n) => String(n || "").split(/\s+/)[0];
const grStack = (g, n = 3) => `<i class="cl-gstack">${(g.members || []).slice(0, n).map(m => `<i class="cl-ava" style="--c:${clColor(m.pid)}" data-face="${grEsc(m.pid)}" data-v="${+m.face || 0}">${grEsc((m.name || "?").slice(0, 1).toUpperCase())}</i>`).join("")}${(g.members || []).length > n ? `<i class="cl-ava more">+${g.members.length - n}</i>` : ""}</i>`;
/* Значок группы (0.68, владелец: «можно ли задавать иконку к самой группе — было бы красивее»): эмодзи на мягкой плашке
   цвета группы — в меню слева, в списке и в шапке переписки; нет значка — как раньше (лица / буква). Ставит создатель. */
const GR_ICONS = ["👨‍👩‍👧", "🏠", "❤️", "💼", "🎉", "⚽", "🎓", "🌿", "🐾", "✈️", "🍳", "🎵", "💡", "🛠️", "🎮", "☀️"];
const grIco = (g, cls = "cl-gico") => `<i class="${cls}" style="--c:${clColor(g.gid || "g")}" aria-hidden="true">${grEsc(g.icon)}</i>`;
const grAva = (g, n = 2) => g && g.icon ? grIco(g) : grStack(g, n);
const grIconPick = (cur) => `<div class="gr-icons" role="radiogroup" aria-label="Значок группы"><button type="button" class="gr-ic gr-ic0${cur ? "" : " on"}" data-ic="" role="radio" aria-checked="${!cur}" title="Без значка — лица участников">Аа</button>${GR_ICONS.map(e => `<button type="button" class="gr-ic${e === cur ? " on" : ""}" data-ic="${e}" role="radio" aria-checked="${e === cur}">${e}</button>`).join("")}</div>`;
function grIconWire(box, onPick) {
  $$(".gr-ic", box).forEach(b => b.onclick = () => { $$(".gr-ic", box).forEach(x => { x.classList.toggle("on", x === b); x.setAttribute("aria-checked", x === b); }); onPick(b.dataset.ic); });
}
const grOf = (gid) => (((CL.st || {}).groups) || []).find(g => g.gid === gid) || null;

function grSide(st) {
  const gs = st.groups || [];
  $("#cl-gh").hidden = !(st.people || []).length && !gs.length;
  $("#cl-groups").innerHTML = gs.length ? gs.map(g => `<button class="cl-p cl-g ${g.gid === CL.cur ? "cur" : ""}" data-gid="${grEsc(g.gid)}" title="${grEsc(g.name)}">${grAva(g)}
      <span><b>${grEsc(g.name)}</b><small>${g.last && (g.last.t || (g.last.f || []).length) ? clEmo(grEsc((g.last.out ? "Вы: " : grFirst(g.last.who || "Кто-то") + ": ") + (g.last.t || "📎 " + ((g.last.f[0] || {}).name || "файл")))) : grEsc((g.members || []).map(m => grFirst(m.name)).join(", "))}</small></span>
      ${g.unread ? `<em>${g.unread}</em>` : ""}</button>`).join("")
    : `<p class="hint cl-gnone">Семья, друзья — пишите всем сразу. Соберите группу из своих близких.</p>`;
  $$("#cl-groups .cl-g").forEach(b => b.onclick = () => clOpen(b.dataset.gid));
  clFaces($("#cl-groups"));
  grNav(gs);
}
/* Группы — и в меню слева, под «Близкими» (28.10, владелец: «созданные группы должны появляться и слева под Близкими,
   красиво»): плашка с буквой названия (цвет группы; без обводок — владелец 28.10: «мелкие кружочки с толстой белой
   обводкой выбиваются из стиля»), название в строку, непрочитанные — числом; нажали — «Близкие» с этой группой. */
function grNav(gs) {
  const box = $("#nav-groups"); if (!box) return;
  box.hidden = !gs.length;
  box.innerHTML = gs.map(g => `<button class="nav-g${g.gid === CL.cur && $("#p-close.cur") ? " cur" : ""}" data-gid="${grEsc(g.gid)}" title="${grEsc(g.name)}">${g.icon ? grIco(g, "nav-gi emo") : `<i class="nav-gi" style="--c:${clColor(g.gid)}" aria-hidden="true">${grEsc((String(g.name || "Г").replace(/^(группа|group)\s+/i, "").trim()[0] || "Г").toUpperCase())}</i>`}<span>${grEsc(String(g.name || "").replace(/^(?:группа|group)\s+(?=\S)/i, "") || g.name)}</span>${g.unread ? `<em>${g.unread}</em>` : ""}</button>`).join("");
  $$("#nav-groups .nav-g").forEach(b => b.onclick = () => {
    const nb = $('nav button[data-p="close"]'); if (!$("#p-close.cur")) nb.click();
    $$("#nav-groups .nav-g").forEach(x => x.classList.toggle("cur", x === b));
    setTimeout(() => clOpen(b.dataset.gid), $("#p-close.cur") ? 0 : 60);
  });
  clFaces(box);
}
/* шапка переписки группы; true — это группа */
function grHead() {
  const g = grOf(CL.cur);
  if (!g) return false;
  $("#cl-empty").style.display = "none"; $("#cl-head").style.display = ""; $("#cl-send").style.display = CL.pick ? "none" : "";
  const ava = $("#cl-ava"); ava.className = "cl-ava cl-gava"; ava.style.removeProperty("--c"); ava.style.backgroundImage = ""; ava.removeAttribute("data-face");
  ava.innerHTML = grAva(g); clFaces(ava);
  $("#cl-who").textContent = g.name;
  $("#cl-devs").textContent = ["вы"].concat((g.members || []).map(m => grFirst(m.name))).join(", ") + " · сообщения шифруются";
  $("#cl-devs").title = "";
  $("#cl-call").style.display = $("#cl-vcall").style.display = "none";
  $("#cl-del").style.display = "";
  $("#cl-del").textContent = g.mine ? "Значок и участники" : "Участники";
  $("#cl-del").title = g.mine ? "Значок группы, название, участники" : "Кто в группе";
  $("#cl-del").classList.remove("danger");
  $("#cl-del").onclick = () => grPanel("info");
  /* 29.10, владелец: «не понимаю, как изменить иконку группы — искал внутри, нигде не вижу»: кнопка «Участники» уезжала
     за край узкой шапки. Теперь сама шапка группы (значок и название) — кнопка: нажали — значок, название, участники. */
  const hd = $("#cl-head");
  hd.classList.add("cl-ghead");
  hd.querySelector("div").setAttribute("role", "button"); hd.querySelector("div").tabIndex = 0;
  hd.querySelector("div").title = ava.title = g.mine ? "Изменить значок, название, участников" : "Кто в группе";
  ava.onclick = hd.querySelector("div").onclick = () => grPanel("info");
  hd.querySelector("div").onkeydown = (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); grPanel("info"); } };
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
/* Версия Dewiar у участника (30.10, владелец: «пишу в группу — ответа нет», а у Валеры старая программа: группы у него нет,
   письма группы ложатся ему лично). Сервер помнит версию каждого устройства (close_devs.ver: «pc 0.71.0», «phone 0.9.14»,
   «web 0.9.14-web», «pc?» — компьютер до 0.71, без номера). Группы видят компьютер 0.61+ и телефон 0.9.5+. -> {old, txt} */
const GR_MIN = { pc: [0, 61], phone: [0, 9, 5], web: [0, 9, 5] };
function grVer(m) {
  const fresh = ((m && m.devs) || []).filter(d => !d.seen || Date.now() / 1000 - d.seen < 30 * 86400);
  const lt = (a, b) => { for (let i = 0; i < Math.max(a.length, b.length); i++) { const x = a[i] || 0, y = b[i] || 0; if (x !== y) return x < y; } return false; };
  const known = fresh.map(d => /^(pc|phone|web) (\d+(?:\.\d+)*)/.exec(d.ver || "")).filter(Boolean);
  const old = fresh.length > 0 && known.length === fresh.length && known.every(k => lt(k[2].split(".").map(Number), GR_MIN[k[1]]));
  const txt = known.map(k => ({ pc: "компьютер", phone: "телефон", web: "браузер" })[k[1]] + " " + k[2]).join(", ");
  return { old, txt };
}
function grOldNote(g, ms) {                     // старой программе — личное письмо: группу она не покажет, а его — покажет
  ms.filter(m => grVer(m).old).forEach(m => core.call("close_send", { pid: m.pid,
    text: `Зову вас в группу «${g.name}» в «Близких». Ваша версия Dewiar групп ещё не знает — обновите Dewiar, и группа появится: https://dewiar.pro/dwrapp/download.php` }).catch(() => {}));
}
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
      <p class="hint" style="margin:14px 0 8px">Значок</p>${grIconPick("")}
      <p class="hint" style="margin:14px 0 8px">Кого позвать — из ваших близких <b id="gr-n"></b></p>${grPick(people, GR.pick, "data-pid")}
      <div class="actions"><button class="btn primary" id="gr-make" disabled>Создать группу</button><button class="btn" id="gr-x">Отмена</button><span class="res" id="gr-res"></span></div>`;
    const upd = () => { $("#gr-make").disabled = !(GR.pick.size && $("#gr-name").value.trim()); $("#gr-n").textContent = GR.pick.size ? `· выбрано ${GR.pick.size}` : ""; };
    $$("#cl-gp input[data-pid]").forEach(c => c.onchange = () => {
      if (c.checked && GR.pick.size + 2 > 12) { c.checked = false; return toast("В группе — до 12 человек"); }
      c.checked ? GR.pick.add(c.dataset.pid) : GR.pick.delete(c.dataset.pid); c.closest(".cl-gpk").classList.toggle("on", c.checked); upd(); });
    $("#gr-name").oninput = upd; $("#gr-name").focus();
    GR.icon = ""; grIconWire(box, (ic) => { GR.icon = ic; });
    $("#gr-x").onclick = () => { grPanel(""); clHead(); };
    $("#gr-make").onclick = async () => { $("#gr-make").disabled = true;
      try { const nm = $("#gr-name").value.trim(), r = await core.call("close_group", { op: "create", name: nm, pids: [...GR.pick], icon: GR.icon || "" }); CL.st = r; grPanel(""); clRender();
        const g2 = grOf(r.gid) || { name: nm, members: [] }, olds = (g2.members || []).filter(m => grVer(m).old);
        grOldNote(g2, g2.members || []);
        toast(`Группа «${nm}» создана` + (olds.length ? ` · у ${olds.map(m => grFirst(m.name)).join(", ")} старая версия Dewiar — им ушло личное письмо: пусть обновятся` : ""), olds.length ? 6000 : 2500); if (r.gid) clOpen(r.gid); }
      catch (e) { $("#gr-res").className = "res bad"; $("#gr-res").textContent = e.message; upd(); } };
    clFaces(box); return;
  }
  if (kind === "album") return grAlbum(box);
  if (kind === "fwd") return grFwdHtml(box);
  const g = grOf(CL.cur); if (!g) return grPanel("");
  const add = g.mine ? people.filter(p => !(g.members || []).some(m => m.pid === p.pid)) : [];
  GR.pick = new Set();
  const owner = g.mine ? "вы" : ((g.members || []).find(m => m.pid === g.owner) || {}).name || "участник";
  box.innerHTML = `<h3>${grEsc(g.name)}</h3><p class="hint">${(g.members || []).length + 1} в группе · создал${g.mine ? "и вы" : "(а) " + grEsc(owner)}</p>
    ${g.mine ? `<div class="actions" style="margin:4px 0 14px"><input type="text" id="gr-rn" maxlength="40" value="${grEsc(g.name)}" aria-label="Название группы" style="flex:1;min-width:0"><button class="btn" id="gr-rn-go">Переименовать</button></div>
      <p class="hint" style="margin:0 0 8px">Значок — увидят все в группе</p>${grIconPick(g.icon || "")}` : ""}
    <div class="cl-gmem"><div class="cl-gm"><i class="cl-ava" style="--c:${clColor((st.me || {}).pid || "me")}" data-face="${grEsc((st.me || {}).pid || "me")}" data-v="${+(st.me || {}).face || 0}">${grEsc(((st.me || {}).name || "Я").slice(0, 1).toUpperCase())}</i><span><b>Вы</b><small>${g.mine ? "создали группу" : "участник"}</small></span></div>
    ${(g.members || []).map(m => `<div class="cl-gm"><i class="cl-ava" style="--c:${clColor(m.pid)}" data-face="${grEsc(m.pid)}" data-v="${+m.face || 0}">${grEsc((m.name || "?").slice(0, 1).toUpperCase())}</i><span><b>${grEsc(m.name)}</b><small>${m.pid === g.owner ? "создал(а) группу" : people.some(p => p.pid === m.pid) ? "ваш близкий" : "не в ваших близких — только в группе"}${grVer(m).old ? ` · <em class="cl-gold">старая версия Dewiar — группу не видит, пусть обновится</em>` : grVer(m).txt ? " · " + grEsc(grVer(m).txt) : ""}</small></span>${g.mine ? `<button class="btn small" data-drop="${grEsc(m.pid)}">Убрать</button>` : ""}</div>`).join("")}</div>
    ${add.length && (g.members || []).length + 1 < 12 ? `<p class="hint" style="margin:16px 0 8px">Позвать ещё</p>${grPick(add, GR.pick, "data-add")}<button class="btn" id="gr-add" disabled>Позвать в группу</button>` : ""}
    <div class="actions" style="margin-top:18px"><button class="btn" id="gr-ix">К переписке</button><span style="flex:1"></span><button class="btn danger" id="gr-leave">${g.mine ? "Удалить группу" : "Выйти из группы"}</button></div>`;
  clFaces(box);
  const op = (a, ok) => core.call("close_group", Object.assign({ gid: g.gid }, a)).then(r => { CL.st = r; clRender(); if (ok) toast(ok); return r; }).catch(e => { toast(e.message, 4000); throw e; });
  $("#gr-ix").onclick = () => { grPanel(""); clHead(); };
  if (g.mine) grIconWire(box, (ic) => op({ op: "icon", icon: ic }, ic ? "Значок группы поставлен" : "Значок убран"));
  if ($("#gr-rn-go")) $("#gr-rn-go").onclick = () => { const n = $("#gr-rn").value.trim(); if (n) op({ op: "rename", name: n }, "Переименовано").then(() => grPanel("info")); };
  $$("#cl-gp [data-drop]").forEach(b => b.onclick = async () => { const m = g.members.find(x => x.pid === b.dataset.drop);
    if (await ask(`Убрать ${m ? m.name : "участника"} из «${g.name}»?`)) op({ op: "drop", pid: b.dataset.drop }, "Убран(а) из группы").then(() => grPanel("info")); });
  $$("#cl-gp input[data-add]").forEach(c => c.onchange = () => { c.checked ? GR.pick.add(c.dataset.add) : GR.pick.delete(c.dataset.add); c.closest(".cl-gpk").classList.toggle("on", c.checked); $("#gr-add").disabled = !GR.pick.size; });
  if ($("#gr-add")) $("#gr-add").onclick = () => { const added = [...GR.pick];
    op({ op: "add", pids: added }, "Позвали в группу").then(() => { const g2 = grOf(g.gid) || g; grOldNote(g2, (g2.members || []).filter(m => added.includes(m.pid))); grPanel("info"); }); };
  $("#gr-leave").onclick = async () => {
    if (!await ask(g.mine ? `Удалить группу «${g.name}» у всех? Переписка у каждого останется.` : `Выйти из «${g.name}»? Новые сообщения группы перестанут приходить.`)) return;
    op({ op: g.mine ? "delete" : "leave" }, g.mine ? "Группа удалена" : "Вы вышли из группы").then(() => { grPanel(""); CL.cur = ""; clRender(); });
  };
}
/* «прочитали» у своих писем в группе: участники, у кого отметка >= номер письма */
function grReadersPc(m) {
  const g = grOf(CL.cur); if (!g || !m.out || !m.sid) return "";
  const mk = g.marks || {}, who = (g.members || []).filter(p => (mk[p.pid] || 0) >= m.sid);
  if (!who.length) return "";
  return ` · <span class="cl-gread">${who.length === (g.members || []).length ? "прочитали все" : "прочитал" + (who.length > 1 ? "и" : "") + ": " + grEsc(who.map(p => grFirst(p.name)).join(", "))}</span>`;
}
/* «Фото и файлы» (0.62): альбом переписки — фото сеткой (скачанные — картинкой), файлы списком; «Переслать» у каждого */
const grIsImg = (f) => typeof clIsImg === "function" ? clIsImg(f) : /\.(jpe?g|png|webp|gif)$/i.test((f && f.name) || "");
function grAlbum(box) {
  const h = CL.hist || [], ph = [], fl = [];
  h.forEach((m, i) => (m.f || []).forEach((f, j) => (grIsImg(f) && f.path ? ph : fl).push([m, i, j, f])));
  const nm = (grOf(CL.cur) || ((CL.st || {}).people || []).find(p => p.pid === CL.cur) || {}).name || "";
  box.innerHTML = `<h3>Фото и файлы — ${grEsc(nm)}</h3><p class="hint">${ph.length} фото, ${fl.length} ${plural(fl.length, "файл", "файла", "файлов")}. Скачанное лежит в папке ассистента «Близкие».</p>`
    + (ph.length ? `<div class="cl-agrid">${ph.slice().reverse().map(([m, i, j, f]) => `<figure><button class="cl-ph" data-path="${grEsc(f.path)}" title="${grEsc(f.name)} — открыть"><img data-thumb="${grEsc(f.path)}" alt="${grEsc(f.name)}"></button><button class="btn small ghost" data-fw="${i}">Переслать</button></figure>`).join("")}</div>` : "")
    + (fl.length ? `<div class="cl-afiles">${fl.slice().reverse().map(([m, i, j, f]) => `<div class="cl-gm"><span><b>${grEsc(f.name)}</b><small>${m.out ? "вы" : grEsc(grFirst(m.who || nm))} · ${clTime(m.ts)} · ${clSize(f.size || 0)}${f.path ? "" : " · ещё не скачан"}</small></span>${f.path ? `<button class="btn small" data-open="${grEsc(f.path)}">Открыть</button>` : ""}<button class="btn small ghost" data-fw="${i}">Переслать</button></div>`).join("")}</div>` : "")
    + (!ph.length && !fl.length ? `<p class="hint">Здесь соберутся фото и файлы этой переписки.</p>` : "")
    + `<div class="actions" style="margin-top:14px"><button class="btn" id="gr-ax">К переписке</button></div>`;
  $$("#cl-gp img[data-thumb]").forEach(im => { const k = im.dataset.thumb;
    (CL.thumbs[k] = CL.thumbs[k] || core.call("close_thumb", { path: k }).then(r => r.data || "").catch(() => "")).then(d => { if (d) im.src = d; }); });
  const open = (path) => { const i = path.lastIndexOf("Близкие/"); if (i >= 0) core.call("ws_open", { path: path.slice(i) }).catch(e => toast(e.message)); };
  $$("#cl-gp [data-path]").forEach(b => b.onclick = () => open(b.dataset.path));
  $$("#cl-gp [data-open]").forEach(b => b.onclick = () => open(b.dataset.open));
  $$("#cl-gp [data-fw]").forEach(b => b.onclick = () => clFwd(h[+b.dataset.fw]));
  $("#gr-ax").onclick = () => { grPanel(""); clHead(); };
}
/* «Переслать»: кому — близкие и группы (кроме этой переписки) */
function clFwd(m) { GR.fwd = m; grPanel("fwd"); }
function grFwdHtml(box) {
  const st = CL.st || {}, m = GR.fwd || {}, files = (m.f || []).map(f => f.name);
  const to = [...(st.groups || []).map(g => ({ id: g.gid, name: g.name, sub: "группа", g })), ...(st.people || []).map(p => ({ id: p.pid, name: p.name, sub: "", p }))].filter(x => x.id !== CL.cur);
  box.innerHTML = `<h3>Переслать</h3><p class="hint">${m.t ? "«" + grEsc(String(m.t).slice(0, 120)) + "»" : ""}${files.length ? (m.t ? " и " : "") + grEsc(files.join(", ")) : ""}</p>`
    + `<div class="cl-gmem">${to.map(x => `<button class="cl-p" data-to="${grEsc(x.id)}">${x.g ? grAva(x.g) : `<i class="cl-ava" style="--c:${clColor(x.id)}" data-face="${grEsc(x.id)}" data-v="${+x.p.face || 0}">${grEsc((x.name || "?").slice(0, 1).toUpperCase())}</i>`}<span><b>${grEsc(x.name)}</b>${x.sub ? `<small>${x.sub}</small>` : ""}</span></button>`).join("") || `<p class="hint">Некому — пригласите ещё близких.</p>`}</div>`
    + `<div class="actions" style="margin-top:14px"><button class="btn" id="gr-fx">Отмена</button></div>`;
  clFaces(box);
  $("#gr-fx").onclick = () => { grPanel(""); clHead(); };
  $$("#cl-gp [data-to]").forEach(b => b.onclick = async () => {
    $$("#cl-gp [data-to]").forEach(x => x.disabled = true);
    try { const r = await core.call("close_forward", { pid: CL.cur, mid: m.mid, to: b.dataset.to }); toast(`Переслано ${r.to || b.querySelector("b").textContent}`, 3000); grPanel(""); clHead(); }
    catch (e) { toast(e.message, 4000); $$("#cl-gp [data-to]").forEach(x => x.disabled = false); }
  });
}
$("#cl-album").onclick = () => grPanel("album");
$("#cl-gnew").onclick = () => { if (!((CL.st || {}).people || []).length) return toast("Сначала пригласите близких — группа собирается из них", 4000); grPanel("new"); };
/* шапка: у человека — «Убрать из близких», у группы — «Участники» */
const grHeadWas = clHead;
clHead = function () { if (!grOf(CL.cur)) { grDelReset(); const a = $("#cl-ava"); a.classList.remove("cl-gava"); if (a.querySelector(".cl-gstack")) a.innerHTML = "";
  const hd = $("#cl-head"), w = hd.querySelector("div"); hd.classList.remove("cl-ghead"); a.onclick = w.onclick = w.onkeydown = null; a.title = w.title = ""; w.removeAttribute("role"); w.removeAttribute("tabindex"); $("#cl-del").title = ""; } return grHeadWas(); };
