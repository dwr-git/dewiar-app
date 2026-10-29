/* «Бот в Telegram» → «Посты» и «Рубрики» (0.69; запрос бизнеса 29.10: «чтобы Лира писала в группы Telegram»).
   Где публикует — каналы (бот — администратор) и группы бота; «+ Канал» по @адресу. Новый пост: текст или «Придумать» по
   теме (пишет персонаж бота), опрос, куда, когда; «Опубликовать» / «Запланировать». Ниже — «Ждут одобрения» (то, что
   написала рубрика), «Запланированы», «Опубликованы» со ссылками. Рубрики — «по будням в 10:00 — тема», с одобрением или
   сразу. Новички — переключатель в «О чём бот». Ядро — pbot_posts.py: pbot_posts, pbot_post_add/edit/ok/del/write,
   pbot_chat_add/del, pbot_rubric_set/del, pbot_greet; событие «pbot_posts». */
const PP = { d: null, sel: new Set(), poll: false, rubOpen: false };
const PP_DAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];
const PP_ST = { wait: "Ждут одобрения", plan: "Запланированы", sent: "Опубликованы", failed: "Не ушли" };
const ppE = (t) => escH(t);
async function ppCall(cmd, args, ok) {
  try { const d = await core.call(cmd, args || {}); if (ok) toast(ok); if (d && d.posts) { PP.d = d; ppRender(); } return d; } catch (e) { toast(e.message, 4500); return null; }
}
function ppWhen(iso) {
  if (!iso) return "сейчас";
  const d = new Date(iso), now = new Date(), hm = d.toTimeString().slice(0, 5);
  const days = Math.round((new Date(d.getFullYear(), d.getMonth(), d.getDate()) - new Date(now.getFullYear(), now.getMonth(), now.getDate())) / 864e5);
  return days === 0 ? `сегодня в ${hm}` : days === 1 ? `завтра в ${hm}` : `${d.toLocaleDateString("ru-RU", { day: "numeric", month: "long" })} в ${hm}`;
}
const PP_IC = { channel: '<svg viewBox="0 0 24 24"><path d="M4 10v4h3l6 4V6L7 10zM16.5 8.5a5 5 0 0 1 0 7"/></svg>',
  group: '<svg viewBox="0 0 24 24"><circle cx="8" cy="9" r="3"/><circle cx="16.5" cy="9.5" r="2.5"/><path d="M2.5 19.5a5.5 5.5 0 0 1 11 0M13.5 18.5a4.5 4.5 0 0 1 8 0"/></svg>' };

async function ppLoad() {
  const on = PB.d && PB.d.connected;
  $("#bp-posts").hidden = $("#bp-rub").hidden = !on;
  if (!on) return;
  try { PP.d = await core.call("pbot_posts"); } catch (e) { return; }
  ppRender(); ppComp();
}

function ppRender() {
  const d = PP.d; if (!d) return;
  const chats = d.chats || [];
  PP.sel = new Set([...PP.sel].filter(id => chats.some(c => c.id === id)));
  if (!PP.sel.size && chats.some(c => c.can)) PP.sel.add(chats.find(c => c.can).id);
  $("#pp-stat").textContent = d.wait ? `ждут одобрения: ${d.wait}` : "";
  $("#pp-where").innerHTML = `<div class="pp-chats" role="group" aria-label="Куда публиковать">` + chats.map(c => `<button type="button" class="pp-chat${PP.sel.has(c.id) ? " on" : ""}${c.can ? "" : " no"}" data-id="${ppE(c.id)}" aria-pressed="${PP.sel.has(c.id)}" ${c.can ? "" : `disabled title="Бот не может здесь публиковать — сделайте его администратором"`}>`
      + `<i aria-hidden="true">${PP_IC[c.type === "channel" ? "channel" : "group"]}</i><span><b>${ppE(c.title)}</b><small>${c.type === "channel" ? "канал" : "группа"}${c.username ? " · @" + ppE(c.username) : ""}</small></span></button>`).join("")
    + `<form class="pp-add" id="pp-addf"><input type="text" id="pp-ref" placeholder="@канал или группа" aria-label="Адрес канала или группы" spellcheck="false"><button class="btn small" type="submit">Добавить</button></form></div>`
    + (chats.length ? "" : `<p class="co-tip">Добавьте бота в канал администратором с правом публиковать сообщения (или в группу) — он появится здесь сам. Или впишите @адрес.</p>`);
  $$("#pp-where .pp-chat").forEach(b => b.onclick = () => { const id = b.dataset.id; PP.sel.has(id) ? PP.sel.delete(id) : PP.sel.add(id); if (!PP.sel.size) PP.sel.add(id); ppRender(); });
  $("#pp-addf").onsubmit = (e) => { e.preventDefault(); const r = $("#pp-ref").value.trim(); if (r) ppCall("pbot_chat_add", { ref: r }, "Добавлено — можно публиковать"); };
  // посты по группам
  const groups = ["wait", "plan", "sent", "failed"].map(st => [st, (d.posts || []).filter(p => p.status === st)]).filter(([, ps]) => ps.length);
  $("#pp-list").innerHTML = groups.map(([st, ps]) => `<h4>${PP_ST[st]}</h4>` + ps.slice(0, st === "sent" ? 8 : 30).map(p => {
    const where = chats.filter(c => p.chats.includes(c.id)).map(c => c.title).join(", ") || "—";
    const meta = st === "sent" ? `${ppE(where)} · ${new Date((p.at_sent || p.created) * 1000).toLocaleString("ru-RU", { day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" })}`
      : `${ppE(where)} · ${ppE(st === "wait" && !p.at ? "после одобрения" : ppWhen(p.at))}${p.source === "rubric" ? " · рубрика «" + ppE(p.topic) + "»" : ""}`;
    const link = (p.sent || []).find(x => x.link);
    const acts = st === "wait" ? `<button class="btn small primary" data-ok="${ppE(p.id)}">${p.at && new Date(p.at) > new Date() ? "Одобрить" : "Опубликовать"}</button><button class="btn small" data-ed="${ppE(p.id)}">Править</button><button class="btn small" data-del="${ppE(p.id)}">Убрать</button>`
      : st === "plan" ? `<button class="btn small" data-ed="${ppE(p.id)}">Править</button><button class="btn small" data-del="${ppE(p.id)}">Отменить</button>`
      : st === "failed" ? `<button class="btn small" data-ok="${ppE(p.id)}" data-again="1">Ещё раз</button><button class="btn small" data-del="${ppE(p.id)}">Убрать</button>`
      : (link ? `<a class="btn small" href="${ppE(link.link)}" target="_blank" rel="noopener">Открыть</a>` : "");
    return `<article class="pp-post st-${st}"><div class="pp-body">${p.poll ? `<b class="pp-poll">Опрос: ${ppE(p.poll.question)}</b><small>${p.poll.options.map(ppE).join(" · ")}</small>` : ""}`
      + (p.text ? `<p>${ppE(p.text)}</p>` : "") + `<small class="pp-meta">${meta}</small>${p.err ? `<small class="pp-err">${ppE(p.err)}</small>` : ""}</div><div class="pp-acts">${acts}</div></article>`;
  }).join("")).join("") || `<p class="co-tip">Постов пока нет.</p>`;
  $$("#pp-list [data-ok]").forEach(b => b.onclick = () => ppCall(b.dataset.again ? "pbot_post_retry" : "pbot_post_ok", { id: b.dataset.ok }, "Готово"));
  $$("#pp-list [data-del]").forEach(b => b.onclick = async () => { if (await ask("Убрать этот пост? В Telegram он не уйдёт.", { ok: "Убрать" })) ppCall("pbot_post_del", { id: b.dataset.del }); });
  $$("#pp-list [data-ed]").forEach(b => b.onclick = async () => {
    const p = d.posts.find(x => x.id === b.dataset.ed); if (!p) return;
    const t = await askText("Текст поста", p.text, { ok: "Сохранить" }); if (t !== null && t !== undefined && t.trim() !== p.text) ppCall("pbot_post_edit", { id: p.id, text: t }, "Сохранено");
  });
  ppRubs();
  $("#pp-greet").checked = !!(d.greet && d.greet.on);
  $("#pp-greet-t").hidden = !(d.greet && d.greet.on);
  if (document.activeElement !== $("#pp-greet-t")) $("#pp-greet-t").value = (d.greet && d.greet.text) || "";
}

function ppComp() {
  $("#pp-comp").innerHTML = `<div class="pp-topic"><input type="text" id="pp-topic" maxlength="300" placeholder="О чём пост — например: как заваривать улун" aria-label="Тема поста"><button class="btn small" type="button" id="pp-write">Придумать</button></div>`
    + `<textarea id="pp-text" rows="5" maxlength="4096" placeholder="Текст поста — напишите сами или нажмите «Придумать»" aria-label="Текст поста"></textarea>`
    + `<div class="pp-pollf" id="pp-pollf" hidden><input type="text" id="pp-pq" maxlength="300" placeholder="Вопрос опроса" aria-label="Вопрос опроса"><textarea id="pp-po" rows="3" placeholder="Варианты — каждый с новой строки" aria-label="Варианты ответа"></textarea></div>`
    + `<div class="pp-row"><label class="pp-ck"><input type="checkbox" id="pp-isp"> Опрос</label><label class="pp-ck">Когда <input type="datetime-local" id="pp-at" aria-label="Когда опубликовать"></label><span style="flex:1"></span><button class="btn primary" type="button" id="pp-go">Опубликовать</button></div>`;
  $("#pp-isp").onchange = () => { $("#pp-pollf").hidden = !$("#pp-isp").checked; };
  $("#pp-at").oninput = () => { $("#pp-go").textContent = $("#pp-at").value ? "Запланировать" : "Опубликовать"; };
  $("#pp-write").onclick = async () => {
    const b = $("#pp-write"); b.disabled = true; b.textContent = "Пишу…";
    const title = (PP.d.chats.find(c => PP.sel.has(c.id)) || {}).title || "";
    try { const r = await core.call("pbot_post_write", { topic: $("#pp-topic").value.trim(), chat_title: title }); $("#pp-text").value = r.text; $("#pp-text").focus(); }
    catch (e) { toast(e.message, 4500); }
    b.disabled = false; b.textContent = "Придумать";
  };
  $("#pp-go").onclick = async () => {
    const text = $("#pp-text").value.trim(), poll = $("#pp-isp").checked ? { question: $("#pp-pq").value.trim(), options: $("#pp-po").value.split("\n").map(x => x.trim()).filter(Boolean) } : null;
    if (!text && !poll) return $("#pp-text").focus();
    const at = $("#pp-at").value, where = PP.d.chats.filter(c => PP.sel.has(c.id)).map(c => c.title).join(", ");
    if (!at && !(await ask(`Опубликовать сейчас в «${where}»?`, { ok: "Опубликовать" }))) return;
    const d = await ppCall("pbot_post_add", { text, poll, at, chats: [...PP.sel] }, at ? "Запланировано" : "Опубликовано");
    if (d) { $("#pp-text").value = ""; $("#pp-topic").value = ""; $("#pp-at").value = ""; $("#pp-isp").checked = false; $("#pp-pollf").hidden = true; $("#pp-go").textContent = "Опубликовать"; }
  };
}

function ppRubs() {
  const d = PP.d, rs = d.rubrics || [];
  const when = (r) => r.days.length === 7 ? "каждый день" : r.days.join() === "0,1,2,3,4" ? "по будням" : r.days.join() === "5,6" ? "по выходным" : r.days.map(i => PP_DAYS[i]).join(", ");
  $("#pp-rubs").innerHTML = rs.map(r => `<div class="pp-rub"><span><b>${ppE(r.topic)}</b><small>${when(r)} в ${ppE(r.time)} · ${r.approve ? "с одобрением" : "сразу"} · ${ppE(d.chats.filter(c => r.chats.includes(c.id)).map(c => c.title).join(", "))}</small></span>`
      + `<button class="btn small" data-rdel="${ppE(r.id)}" aria-label="Убрать рубрику «${ppE(r.topic)}»">Убрать</button></div>`).join("")
    + `<form class="pp-rubf" id="pp-rubf"><input type="text" id="pp-rt" maxlength="300" placeholder="Тема: совет дня о чае" aria-label="Тема рубрики">`
    + `<div class="pp-days" role="group" aria-label="Дни">${PP_DAYS.map((x, i) => `<button type="button" data-d="${i}" class="${i < 5 ? "on" : ""}" aria-pressed="${i < 5}">${x}</button>`).join("")}</div>`
    + `<div class="pp-row"><label class="pp-ck">В <input type="time" id="pp-rtime" value="10:00" aria-label="Время"></label><label class="pp-ck"><input type="checkbox" id="pp-rap" checked> С одобрением</label><span style="flex:1"></span><button class="btn small primary" type="submit">Добавить рубрику</button></div></form>`;
  $$("#pp-rubs [data-rdel]").forEach(b => b.onclick = () => ppCall("pbot_rubric_del", { id: b.dataset.rdel }, "Рубрика убрана"));
  $$("#pp-rubf .pp-days button").forEach(b => b.onclick = () => { b.classList.toggle("on"); b.setAttribute("aria-pressed", b.classList.contains("on")); });
  $("#pp-rubf").onsubmit = (e) => {
    e.preventDefault();
    const days = $$("#pp-rubf .pp-days button.on").map(b => +b.dataset.d);
    ppCall("pbot_rubric_set", { topic: $("#pp-rt").value.trim(), days, time: $("#pp-rtime").value, approve: $("#pp-rap").checked, chats: [...PP.sel] }, "Рубрика добавлена");
  };
}

(function ppInit() {
  if (!$("#bp-posts")) return;
  $("#pp-greet").onchange = (e) => ppCall("pbot_greet", { on: e.target.checked }, e.target.checked ? "Буду приветствовать новичков" : "");
  $("#pp-greet-t").onchange = (e) => ppCall("pbot_greet", { text: e.target.value }, "Сохранено");
  core.on("pbot_posts", (e) => { if (e && e.posts) { PP.d = e; if ($("#p-pbot").classList.contains("cur")) ppRender(); } });
  window.ppLoad = ppLoad;
})();
