/* Студия → «Работа» → «Чат для сайта» (0.69; запрос бизнеса 29.10: «виджет на сайт и ссылка — отвечает Лира, переписка
   с лидами — в CRM»). Слева — кто отвечает (персонаж), что видит посетитель (название, первое сообщение, «оставить
   контакт»), что знает (о чём, знания, документы из папок персонажа, пределы). Справа — окно чата, каким его увидят (меняется
   на лету), «Опубликовать» / «Обновить на сайте»; после — ссылка, код для сайта, счётчики и последние заявки.
   Ядро — sitechat.py: sitechat_get {fresh}, sitechat_save {patch}, sitechat_publish {patch}, sitechat_forget, sitechat_poll;
   событие «sitechat». */
const SC = { d: null, t: 0 };
const scE = (t) => escH(t);

async function loadSitechat() {
  try { SC.d = await core.call("sitechat_get", { fresh: true }); } catch (e) { toast(e.message, 4000); return; }
  scFill(); scLive();
}

function scPersonas() { return (typeof personas !== "undefined" ? personas : []).filter(p => !p.kids); }

function scFill() {
  const d = SC.d;
  const ps = scPersonas(), cur = d.persona || (S && S.persona) || (ps[0] || {}).id;
  $("#sc-ps").innerHTML = ps.map(x => `<button type="button" role="radio" class="co-m${x.id === cur ? " on" : ""}" aria-checked="${x.id === cur}" data-id="${scE(x.id)}" style="--c:${scE(x.color || "#8B7CFF")}">`
    + (x.avatar_url ? `<i class="pic" aria-hidden="true" style="background-image:url('${String(x.avatar_url).replace(/'/g, "%27")}')"></i>` : `<i aria-hidden="true">${scE((x.name || "?")[0])}</i>`)
    + `<span><b>${scE(x.name)}</b><small>${scE((x.character || "").slice(0, 60))}</small></span></button>`).join("");
  SC.persona = cur;
  $$("#sc-ps .co-m").forEach(b => b.onclick = () => { SC.persona = b.dataset.id; $$("#sc-ps .co-m").forEach(x => { x.classList.toggle("on", x === b); x.setAttribute("aria-checked", x === b); }); scFold(); scDraft(); });
  const set = (id, v) => { if (document.activeElement !== $(id)) $(id).value = v == null ? "" : v; };
  set("#sc-title", d.title); set("#sc-greet", d.greeting); set("#sc-brief", d.brief); set("#sc-kb", d.kb); set("#sc-pi", d.per_ip); set("#sc-pd", d.per_day);
  $("#sc-ask").checked = !!d.ask_contact; $("#sc-fold").checked = !!d.folders;
  scFold(); scCount(); scPrev();
}

/* «Добавить документы из папок персонажа» — только если у выбранного персонажа есть папки со знаниями */
function scFold() {
  const p = scPersonas().find(x => x.id === SC.persona) || {}, fold = (p.knowledge || []).filter(b => b.kind === "folder");
  $("#sc-fold").disabled = !fold.length;
  $("#sc-foldtip").textContent = fold.length ? `${fold.map(b => b.label || b.path.split(/[\\/]/).pop()).join(", ")} — текст файлов уйдёт на сервер Dewiar вместе со знаниями` : "у этого персонажа нет папок со знаниями";
}

function scPatch() {
  return { persona: SC.persona, title: $("#sc-title").value.trim(), greeting: $("#sc-greet").value.trim(), brief: $("#sc-brief").value.trim(),
    kb: $("#sc-kb").value, ask_contact: $("#sc-ask").checked, folders: $("#sc-fold").checked && !$("#sc-fold").disabled,
    per_ip: +$("#sc-pi").value || 40, per_day: +$("#sc-pd").value || 500 };
}

function scCount() { const n = $("#sc-kb").value.length; $("#sc-kbn").textContent = n ? `· ${n.toLocaleString("ru-RU")} из 60 000 знаков` : ""; $("#sc-kbn").classList.toggle("over", n > 60000); }

/* тот же цвет, что увидят на сайте (sitechat.py readable): светлый цвет персонажа темнеем, пока белый на нём читается */
function scInk(hex) {
  let c = [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16));
  const lum = (c) => c.map(v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }).reduce((s, v, i) => s + v * [0.2126, 0.7152, 0.0722][i], 0);
  for (let i = 0; i < 40 && 1.05 / (lum(c) + 0.05) < 4.5; i++) c = c.map(v => Math.floor(v * 0.92));
  return "#" + c.map(v => v.toString(16).padStart(2, "0")).join("");
}

function scPrev() {
  const p = scPersonas().find(x => x.id === SC.persona) || {}, a = scPatch();
  const col = /^#[0-9a-fA-F]{6}$/.test(p.color || "") ? scInk(p.color) : "#6a5cf0";
  $("#sc-prev").style.setProperty("--sc", col);
  $("#sc-prev").innerHTML = `<div class="scp-win"><header><i class="scp-ava" ${p.avatar_url ? `style="background-image:url('${String(p.avatar_url).replace(/'/g, "%27")}')"` : ""}>${p.avatar_url ? "" : scE((p.name || "?")[0])}</i>`
    + `<div><b>${scE(p.name || "Консультант")}</b><small>${scE(a.title ? a.title + " · ИИ-помощник" : "ИИ-помощник · отвечает сразу")}</small></div></header>`
    + `<div class="scp-msgs"><p class="scp-a">${scE(a.greeting || "Здравствуйте! Чем помочь?")}</p><p class="scp-u">Сколько стоит доставка?</p>`
    + `<p class="scp-a scp-dim">Отвечу по вашим знаниям${a.ask_contact ? " — а если там нет ответа, предложу оставить контакт" : ""}.</p></div>`
    + `<div class="scp-in"><span>Ваш вопрос…</span><i>↑</i></div>${a.ask_contact ? `<small class="scp-lead">Оставить контакт</small>` : ""}</div>`
    + `<span class="scp-btn" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z"/></svg></span>`;
}

function scDraft() {
  scCount(); scPrev();
  clearTimeout(SC.t);
  SC.t = setTimeout(() => core.call("sitechat_save", { patch: scPatch() }).catch(() => {}), 600);
}

function scLive() {
  const d = SC.d, r = d.remote;
  $("#sc-live").hidden = !r;
  $("#sc-pub").textContent = r ? "Обновить на сайте" : "Опубликовать";
  $("#sc-err").hidden = !d.error; $("#sc-err").textContent = d.error ? "Сейчас: " + d.error : "";
  if (!d.signed) { $("#sc-err").hidden = false; $("#sc-err").textContent = "Нужен вход аккаунтом dewiar.pro или ключ Dewiar — студия → «Мозг». С него и платится за ответы."; }
  if (!r) return;
  $("#sc-link").value = r.link; $("#sc-open").href = r.link; $("#sc-code").value = r.embed;
  $("#sc-stats").innerHTML = `<span><b>${r.today || 0}</b>вопросов сегодня</span><span><b>${r.total || 0}</b>всего</span><span><b>${(d.recent || []).length}</b>заявок за сеанс</span>`;
  $("#sc-leads").innerHTML = (d.recent || []).map(x => `<li><b>${scE(x.name || x.contact)}</b><small>${scE(x.contact)} · ${new Date((x.ts || 0) * 1000).toLocaleString("ru-RU", { day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" })}</small><button class="btn small" data-cl="${scE(x.cid)}">В «Клиентах»</button></li>`).join("");
  $$("#sc-leads [data-cl]").forEach(b => b.onclick = () => { if (window.CR) CR.cur = b.dataset.cl; const n = $('nav button[data-p="clients"]'); if (n) n.click(); });
}

(function scInit() {
  if (!$("#p-sitechat")) return;
  for (const id of ["#sc-title", "#sc-greet", "#sc-brief", "#sc-kb", "#sc-pi", "#sc-pd"]) $(id).addEventListener("input", scDraft);
  for (const id of ["#sc-ask", "#sc-fold"]) $(id).addEventListener("change", scDraft);
  $("#sc-pub").onclick = async () => {
    const b = $("#sc-pub"); b.disabled = true; const was = b.textContent; b.textContent = "Отправляю…";
    try { SC.d = await core.call("sitechat_publish", { patch: scPatch() }); toast(was === "Опубликовать" ? "Чат готов — скопируйте ссылку или код для сайта" : "Обновлено на сайте", 3500); scLive(); }
    catch (e) { toast(e.message, 5000); }
    b.disabled = false; if (b.textContent === "Отправляю…") b.textContent = was;
  };
  $$("#p-sitechat [data-cp]").forEach(b => b.onclick = async () => {
    const i = $("#" + b.dataset.cp);
    try { await navigator.clipboard.writeText(i.value); toast("Скопировано"); } catch (e) { i.select(); toast("Выделила — нажмите Ctrl+C"); }
  });
  $("#sc-off").onclick = async () => {
    if (!await ask("Отключить чат на сайте? Кнопка исчезнет, ссылка перестанет работать. Клиенты в «Клиентах» останутся.", { ok: "Отключить" })) return;
    try { SC.d = await core.call("sitechat_forget"); toast("Чат отключён"); scLive(); } catch (e) { toast(e.message, 4000); }
  };
  core.on("sitechat", (e) => { if (e && "persona" in e) { SC.d = e; if ($("#p-sitechat").classList.contains("cur")) scLive(); } });
  window.loadSitechat = loadSitechat;
})();
