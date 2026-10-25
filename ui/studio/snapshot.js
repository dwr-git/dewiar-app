/* «Слепок знаний» на «Главной» (0.45.2, владелец: «одним нажатием выгрузить всё одним файлом… чтобы я был уверен,
   что у меня лежат бэкапы и в любой момент можно восстановить без перетирания данных»; макет утверждён 25.10).
   Кнопка справа от приветствия: когда был последний слепок (зелёная точка; старше недели — янтарная). Меню: закрытый
   .dwr (пароль; можно запомнить на этом компьютере — тогда и автокопия раз в неделю закрытая, с сейфом) или открытый
   .zip (Markdown и JSON — откроется без Dewiar); «Восстановить…» — окно: что внутри и как — «Добавить недостающее»
   (бережно, по умолчанию) или «Вернуть всё как было» (перед этим — слепок текущего). Ядро — core/backup.py,
   команды backup_info / backup_make / backup_inspect / backup_restore / backup_forget_pw / backup_open. */
const SN = { info: null, fmt: "dwr", open: false, pick: null, mode: "merge" };
const SN_I = {
  arch: '<svg viewBox="0 0 24 24"><path d="M4 7.5h16v3H4z"/><path d="M5.5 10.5V18a2 2 0 0 0 2 2h9a2 2 0 0 0 2-2v-7.5"/><path d="M10 14h4"/></svg>',
  lock: '<svg viewBox="0 0 24 24"><rect x="5" y="10.5" width="14" height="10" rx="2.5"/><path d="M8.5 10.5V7.5a3.5 3.5 0 0 1 7 0v3"/></svg>',
  open: '<svg viewBox="0 0 24 24"><path d="M4 7a2 2 0 0 1 2-2h4l2 2h6a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2z"/></svg>',
};
try { SN.fmt = localStorage.getItem("dw.snap.fmt") === "zip" ? "zip" : "dwr"; } catch (e) { }
const snEsc = (t) => String(t == null ? "" : t).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const snPl = (n, one, few, many) => { const a = Math.abs(n) % 100, b = a % 10; return n + " " + (a > 10 && a < 20 ? many : b === 1 ? one : b >= 2 && b <= 4 ? few : many); };
function snWhen(iso) {
  const d = new Date(iso); if (isNaN(d)) return "";
  const t = d.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" }), now = new Date(), y = new Date(now); y.setDate(now.getDate() - 1);
  if (d.toDateString() === now.toDateString()) return "сегодня в " + t;
  if (d.toDateString() === y.toDateString()) return "вчера в " + t;
  return d.toLocaleDateString("ru-RU", { day: "numeric", month: "long" }) + (d.getFullYear() !== now.getFullYear() ? " " + d.getFullYear() : "") + ", " + t;
}
const snLast = () => ((SN.info && SN.info.items) || []).find(x => x.label !== "до восстановления") || null;
const snOld = (x) => !x || Date.now() - new Date(x.time).getTime() > 7 * 864e5;
function snHas(x) {
  const s = x.stats || {}, c = x.counts || {}, out = [];
  if (s.notes != null) out.push(snPl(s.notes, "заметка", "заметки", "заметок")); else if (c.workspace) out.push(snPl(c.workspace, "файл", "файла", "файлов") + " заметок и папки");
  if (s.bills) out.push(snPl(s.bills, "счёт", "счёта", "счетов") + (s.pays ? " и " + snPl(s.pays, "оплата", "оплаты", "оплат") : ""));
  if (s.reminders) out.push(snPl(s.reminders, "дело", "дела", "дел"));
  if (s.personas) out.push(snPl(s.personas, "персонаж", "персонажа", "персонажей"));
  if (x.vault) out.push("сейф: " + x.vault);
  return out;
}
async function snLoad() {
  try { SN.info = await core.call("backup_info"); } catch (e) { SN.info = SN.info || null; }
  snChip(); if (SN.open) snPop();
}
function snChip() {
  const box = $("#sn"); if (!box) return;
  const x = snLast(), old = snOld(x);
  if (!$("#sn-chip")) {
    box.innerHTML = `<button class="sn-chip" id="sn-chip" aria-haspopup="dialog" aria-expanded="false"><i class="sn-ic">${SN_I.arch}</i><span><b>Слепок знаний</b><small></small></span></button><div class="sn-pop" id="sn-pop" role="dialog" aria-label="Слепок знаний" hidden></div>`;
    $("#sn-chip").onclick = () => snToggle(!SN.open);
  }
  $("#sn-chip").classList.toggle("old", old);
  $("#sn-chip small").innerHTML = `<i></i>${x ? snEsc(snWhen(x.time)) : "ещё не было — сделайте"}`;
  $("#sn-chip").title = x ? `Последний слепок — ${snWhen(x.time)}${old ? ". Пора сделать новый" : ""}` : "Слепков ещё нет";
}
function snToggle(on) {
  SN.open = on; $("#sn-pop").hidden = !on; $("#sn-chip").setAttribute("aria-expanded", String(on));
  if (on) { snPop(); snLoad(); }
}
function snPop() {
  const p = $("#sn-pop"); if (!p) return;
  const i = SN.info || {}, x = snLast(), old = snOld(x), dwr = SN.fmt === "dwr", typing = p.contains(document.activeElement) && document.activeElement.id === "sn-pw";
  if (typing) return;                                  // пароль вписывают — не перерисовываем под рукой
  const dir = i.dir || "", folder = dir.split(/[\\/]/).filter(Boolean).pop() || "Dewiar — копии";
  p.innerHTML = `<h3 class="sn-h">Слепок знаний<button class="hbtn" id="sn-help" title="Как работают слепки" aria-label="Как работают слепки">?</button></h3>
    <p class="sn-lead">Всё, что знает Лира, одним файлом: заметки, платежи, дела, календарь, память, персонажи и настройки.</p>
    <div class="sn-last${old ? " old" : ""}"><i></i><div><b>${x ? "Последний — " + snEsc(snWhen(x.time)) : "Слепков ещё не было"}</b>
      <small>${x ? snEsc(x.size_text) + " · " : ""}${i.auto === false ? "автокопия выключена" : "сам — раз в неделю, хранятся 4 последних"}</small></div></div>
    <div class="sn-kind" role="radiogroup" aria-label="Какой слепок">
      <button role="radio" aria-checked="${dwr}" class="${dwr ? "on" : ""}" data-f="dwr"><b>${SN_I.lock}Закрытый .dwr</b><small>под паролем, со всем — и с сейфом паролей</small></button>
      <button role="radio" aria-checked="${!dwr}" class="${!dwr ? "on" : ""}" data-f="zip"><b>${SN_I.open}Открытый .zip</b><small>заметки — Markdown, данные — JSON; откроется без Dewiar</small></button></div>
    ${dwr ? (i.pw ? `<div class="sn-saved">${SN_I.lock}<span>Пароль запомнен на этом компьютере</span><button class="sn-link" id="sn-forget">Забыть</button></div>`
      : `<label class="sn-pw"><input type="password" id="sn-pw" placeholder="пароль слепка" autocomplete="new-password" aria-label="Пароль слепка">
         <span class="sn-rem"><input type="checkbox" id="sn-rem" checked> запомнить на этом компьютере — и автокопия будет закрытой</span>
         <small>Без пароля слепок не открыть — запишите его в надёжное место.</small></label>`)
      : `<p class="sn-note">Паролей, ключей и сейфа в открытом слепке нет — они только в закрытом.</p>`}
    <button class="btn primary sn-go" id="sn-go">Сделать слепок</button>
    <p class="res" id="sn-res" aria-live="polite"></p>
    <div class="sn-sep"></div>
    <div class="sn-row"><button class="btn" id="sn-rest">Восстановить…</button><button class="btn" id="sn-dir">Папка со слепками</button></div>
    <p class="sn-foot" title="${snEsc(dir)}">Слепки лежат в папке «${snEsc(folder)}» в «Документах». Их можно скопировать на флешку или в облако.</p>`;
  $("#sn-help").onclick = () => { snToggle(false); if (window.showHelp) showHelp("snapshot"); };
  $$("#sn-pop [data-f]").forEach(b => b.onclick = () => { SN.fmt = b.dataset.f; try { localStorage.setItem("dw.snap.fmt", SN.fmt); } catch (e) { } snPop(); });
  if ($("#sn-forget")) $("#sn-forget").onclick = async () => { if (!await ask("Забыть пароль слепков на этом компьютере? Автокопия станет без сейфа и ключей, пока не зададите пароль снова.")) return;
    await core.call("backup_forget_pw").catch(() => { }); snLoad(); };
  if ($("#sn-pw")) $("#sn-pw").onkeydown = (e) => { if (e.key === "Enter") snMake(); };
  $("#sn-go").onclick = snMake;
  $("#sn-rest").onclick = () => { snToggle(false); snRestore(); };
  $("#sn-dir").onclick = () => core.call("backup_open").catch(e => toast(e.message));
}
async function snMake() {
  const r = $("#sn-res"), b = $("#sn-go"), i = SN.info || {}, a = { fmt: SN.fmt };
  if (SN.fmt === "dwr") {
    if (i.pw) a.saved = true;
    else {
      a.password = ($("#sn-pw") || {}).value || ""; a.remember = !!($("#sn-rem") || {}).checked;
      if (!a.password) { r.className = "res bad"; r.textContent = "Придумайте пароль — или выберите открытый .zip"; $("#sn-pw").focus(); return; }
    }
  }
  b.disabled = true; r.className = "res"; r.textContent = "делаю слепок…";
  try {
    const x = await core.call("backup_make", a);
    r.className = "res ok"; r.textContent = `Готово: ${x.size_text}${x.encrypted ? " · под паролем" : ""}`;
    toast(`Слепок знаний готов — ${x.name}`, 3500);
    await snLoad();
    const r2 = $("#sn-res"); if (r2) { r2.className = "res ok"; r2.textContent = `Готово: ${x.size_text}${x.encrypted ? " · под паролем" : ""}`; }
  } catch (e) { r.className = "res bad"; r.textContent = e.message; }
  finally { const g = $("#sn-go"); if (g) g.disabled = false; }
}
/* ---------- восстановление: выбрать слепок → что внутри и как ---------- */
function snDlg() {
  let d = $("#sn-dlg");
  if (!d) { d = document.createElement("dialog"); d.className = "nwdlg sn-dlg"; d.id = "sn-dlg"; d.setAttribute("aria-label", "Восстановить из слепка"); document.body.appendChild(d); }
  return d;
}
async function snRestore() {
  await snLoad();
  SN.pick = null; SN.mode = "merge";
  const d = snDlg(), items = ((SN.info && SN.info.items) || []).slice(0, 8);
  d.innerHTML = `<h3>Восстановить из слепка</h3><p class="sn-lead">Выберите слепок — покажу, что в нём, и спрошу, как восстановить.</p>
    <div class="sn-list">${items.map((x, k) => `<button class="sn-file" data-k="${k}"><i class="sn-ic${x.encrypted ? "" : " op"}">${x.format === "zip" ? SN_I.open : SN_I.arch}</i>
      <span><b>${snEsc(snWhen(x.time))}${x.auto ? " · автоматически" : x.label && x.label !== "слепок" && x.label !== "копия" ? " · " + snEsc(x.label) : ""}</b>
      <small>${snEsc(x.size_text)} · ${x.format === "zip" ? "открытый .zip" : x.encrypted ? "закрытый" : "без пароля"}${x.host && SN.info && x.host !== SN.info.host ? ` · с компьютера «${snEsc(x.host)}»` : ""}</small></span></button>`).join("")
      || `<p class="hint" style="margin:0">В папке слепков пока пусто.</p>`}</div>
    <div class="sn-act"><button class="btn" id="sn-other">Другой файл…</button><span style="flex:1"></span><button class="btn" id="sn-x">Отмена</button></div>`;
  $$("#sn-dlg [data-k]").forEach(b => b.onclick = () => snShow(items[+b.dataset.k]));
  $("#sn-x").onclick = () => d.close();
  $("#sn-other").onclick = async () => {
    const a = window.pywebview && window.pywebview.api;
    if (!a || !a.pick_file) { toast("Выбор файла доступен в окне студии"); return; }
    const p = await a.pick_file("Слепок Dewiar (*.dwr;*.zip;*.dwbak)"); if (!p) return;
    try { snShow(await core.call("backup_inspect", { path: p })); } catch (e) { toast(e.message, 4000); }
  };
  if (!d.open) d.showModal();
}
function snShow(x) {
  SN.pick = x;
  const d = snDlg(), day = new Date(x.time), dd = isNaN(day) ? "" : day.toLocaleDateString("ru-RU", { day: "numeric", month: "long" }),
    ddm = isNaN(day) ? "слепка" : String(day.getDate()).padStart(2, "0") + "." + String(day.getMonth() + 1).padStart(2, "0"),
    needPw = x.encrypted && !(SN.info && SN.info.pw);
  d.innerHTML = `<h3>Восстановить из слепка</h3>
    <div class="sn-file big"><i class="sn-ic${x.encrypted ? "" : " op"}">${x.format === "zip" ? SN_I.open : SN_I.arch}</i><span><b>${snEsc(x.name)}</b>
      <small>${snEsc(snWhen(x.time))}${x.host ? ` · компьютер «${snEsc(x.host)}»` : ""}${x.version ? " · Dewiar " + snEsc(x.version) : ""} · ${x.format === "zip" ? "открытый" : x.encrypted ? "закрытый" : "без пароля"}</small></span></div>
    <div class="sn-has">${snHas(x).map(t => `<span>${snEsc(t)}</span>`).join("")}</div>
    ${x.encrypted ? (needPw ? `<label class="sn-pw"><input type="password" id="sn-rpw" placeholder="пароль этого слепка" aria-label="Пароль слепка"></label>`
      : `<p class="sn-note">${SN_I.lock} Откроется запомненным паролем. Если слепок с другим паролем — <button class="sn-link" id="sn-askpw">ввести пароль</button></p>`) : ""}
    <div class="sn-way" role="radiogroup" aria-label="Как восстановить">
      <label class="${SN.mode === "merge" ? "on" : ""}"><input type="radio" name="sn-w" value="merge" ${SN.mode === "merge" ? "checked" : ""}><b>Добавить недостающее<em>бережно</em></b>
        <small>Ничего вашего не трогаю. Чего нет — добавлю; где отличается — положу рядом копией «(из слепка ${ddm})».</small></label>
      <label class="${SN.mode === "replace" ? "on" : ""}"><input type="radio" name="sn-w" value="replace" ${SN.mode === "replace" ? "checked" : ""}><b>Вернуть всё как было в слепке</b>
        <small>Всё станет как ${snEsc(dd || "в слепке")}. Перед этим сам сделаю слепок того, что сейчас, — вернуться можно будет.</small></label></div>
    <details class="sn-more"><summary>Чем отличаются способы и что будет с моими данными?</summary>
      <ul><li><b>Добавить недостающее</b> — ваше остаётся как есть. Заметки, которых нет, вернутся; если заметка с тем же именем отличается, вариант из слепка ляжет рядом с пометкой «(из слепка ${ddm})» — сравните и оставьте нужное. В платежах, делах и календаре допишутся только недостающие записи. Настройки и пароли в сейфе — ваши.</li>
      <li><b>Вернуть всё как было</b> — файлы из слепка заменят одноимённые. Ничего не удаляется, а перед этим сам сделаю слепок «до восстановления» — к нему можно вернуться тем же способом.</li>
      <li>После восстановления ассистент перезапустится на несколько секунд — так он перечитает данные.</li></ul></details>
    <p class="res" id="sn-rres" aria-live="polite"></p>
    <div class="sn-act"><button class="btn" id="sn-back">Назад</button><span style="flex:1"></span><button class="btn" id="sn-x">Отмена</button><button class="btn primary" id="sn-do">Восстановить</button></div>`;
  const verb = () => { $("#sn-do").textContent = SN.mode === "merge" ? "Добавить недостающее" : "Вернуть как было"; };
  $$("#sn-dlg input[name=sn-w]").forEach(r => r.onchange = () => { SN.mode = r.value; $$("#sn-dlg .sn-way label").forEach(l => l.classList.toggle("on", l.querySelector("input").checked)); verb(); });
  if ($("#sn-askpw")) $("#sn-askpw").onclick = () => { SN.info.pw = false; snShow(x); SN.info.pw = true; };
  $("#sn-back").onclick = snRestore;
  $("#sn-x").onclick = () => d.close();
  $("#sn-do").onclick = () => snDo(x); verb();
  if (!d.open) d.showModal();
  if ($("#sn-rpw")) $("#sn-rpw").focus();
}
async function snDo(x) {
  const r = $("#sn-rres"), b = $("#sn-do"), a = { path: x.path, mode: SN.mode };
  if (x.encrypted) { const pw = $("#sn-rpw"); if (pw) { a.password = pw.value; if (!a.password) { r.className = "res bad"; r.textContent = "Впишите пароль этого слепка"; pw.focus(); return; } } else a.saved = true; }
  b.disabled = true; r.className = "res"; r.textContent = SN.mode === "merge" ? "добавляю недостающее…" : "восстанавливаю…";
  try {
    const y = await core.call("backup_restore", a);
    const bits = y.mode === "merge"
      ? [y.files ? "добавлено файлов: " + y.files : "", y.merged ? "дополнено записей в данных: " + y.merged : "", y.beside ? "рядом копией: " + y.beside : "", y.vault ? "сейф: " + y.vault : ""].filter(Boolean)
      : ["восстановлено файлов: " + y.files, y.vault ? "сейф: " + y.vault : ""].filter(Boolean);
    r.className = "res ok"; r.textContent = (bits.length ? bits.join(" · ") : "всё уже было на месте") + ". Ассистент перезапускается…";
    b.textContent = "Готово";
  } catch (e) { r.className = "res bad"; r.textContent = e.message; b.disabled = false; }
}
document.addEventListener("mousedown", (e) => { if (SN.open && !e.target.closest("#sn")) snToggle(false); });
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && SN.open) { snToggle(false); $("#sn-chip").focus(); } });
window.snLoad = snLoad;
