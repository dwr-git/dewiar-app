/* Студия Dewiar, раздел «Рассылка» (0.69; запрос бизнеса 29.10: «начальник отправляет письма 10 сотрудникам или 100
   клиентам»). Слева — кому (клиентам с почтой, можно по метке; сотрудникам с почтой в карточке; своим списком) и само письмо
   с {имя}; справа — как его получит первый (собирает ядро — та же строка об отписке у рекламы) и «Отправить N письмам».
   Ниже — рассылки с ходом (событие «mailing»), «Остановить» / «Продолжить», и стоп-лист отписавшихся.
   Ядро — mailing.py: mailing_get, mailing_preview, mailing_draft, mailing_start/stop/forget, mailing_stopset. */
let MG = { src: "", kind: "work", info: null, prev: null, t: 0, busy: false, ask: "" };
const MG_ST = { draft: "черновик", sending: "идёт", waiting: "ждёт завтра", paused: "на паузе", stopped: "остановлена", done: "ушла" };
const mgWord = (n, a, b, c) => { const m = n % 10, h = n % 100; return `${n} ${m === 1 && h !== 11 ? a : m >= 2 && m <= 4 && (h < 10 || h >= 20) ? b : c}`; };
async function mgCall(cmd, args, ok) {
  try { const d = await core.call(cmd, args || {}); if (ok) toast(ok); return d; } catch (e) { toast(e.message, 3800); return null; }
}

async function loadMailing(src) {
  const d = await mgCall("mailing_get"); if (!d) return;
  MG.info = d.sources || {};
  const i = MG.info;
  $("#mg-nomail").hidden = !!i.mail;
  $("#mg-n-clients").textContent = i.clients ? String(i.clients) : "";
  $("#mg-n-team").textContent = i.team ? String(i.team) : "";
  const tag = $("#mg-tag"), cur = tag.value;
  tag.innerHTML = `<option value="">все клиенты с почтой</option>` + (i.tags || []).map(t => `<option value="${escH(t)}">${escH(t)}</option>`).join("");
  tag.value = (i.tags || []).includes(cur) ? cur : "";
  const bx = $("#mg-box"), bcur = bx.value;
  bx.innerHTML = (i.boxes || []).map((a, n) => `<option value="${n}">${escH(a)}</option>`).join("");
  if (bcur) bx.value = bcur;
  $("#mg-boxw").hidden = (i.boxes || []).length < 2;
  if (src) MG.src = src;
  if (!MG.src) MG.src = i.clients ? "clients" : i.team ? "team" : "list";
  mgSrc(MG.src, true);
  mgHist(d.list || []);
  const st = d.stop || [];
  $("#mg-stopn").textContent = st.length ? `(${st.length})` : "";
  if (document.activeElement !== $("#mg-stoplist")) $("#mg-stoplist").value = st.join("\n");
  mgPreview();
}

function mgSrc(s, quiet) {
  MG.src = s;
  $$("#mg-src button").forEach(b => { const on = b.dataset.s === s; b.classList.toggle("on", on); b.setAttribute("aria-checked", on); });
  $("#mg-tagw").hidden = s !== "clients" || !(MG.info && (MG.info.tags || []).length);
  $("#mg-listw").hidden = s !== "list";
  if (!quiet) mgPreview();
}

function mgKind(k) {
  MG.kind = k;
  $$("#mg-kind button").forEach(b => { const on = b.dataset.k === k; b.classList.toggle("on", on); b.setAttribute("aria-checked", on); });
  $("#mg-kindhint").textContent = k === "ads"
    ? "Только тем, кто согласился получать ваши новости. В конце письма — как отписаться; отписавшимся больше не пишу."
    : "Сотрудникам, партнёрам, клиентам по делу — без строки об отписке.";
  mgPreview();
}

const mgArgs = () => ({ source: MG.src, tag: $("#mg-tag").value, text: $("#mg-list").value, kind: MG.kind,
  subject: $("#mg-subj").value.trim(), body: $("#mg-body").value.trim(), box: $("#mg-boxw").hidden ? "" : $("#mg-box").value });

function mgPreview() {
  clearTimeout(MG.t);
  MG.t = setTimeout(async () => {
    const a = mgArgs(), d = await mgCall("mailing_preview", a); if (!d) return;
    MG.prev = d; mgShow(a, d);
  }, 250);
}

function mgShow(a, d) {
  const sk = d.skipped || {}, n = d.n || 0, i = MG.info || {};
  const empty = a.source === "clients" ? "В «Клиентах» ни у кого нет почты — допишите её в карточках."
    : a.source === "team" ? "У сотрудников не указана почта — «Поручения» → «Сотрудники» → «Почта»."
    : "Вставьте адреса — я сама отсею повторы и неверные.";
  const extra = [sk.dup ? `повторы убрала: ${sk.dup}` : "", sk.stop ? `отписавшихся пропущу: ${sk.stop}` : ""].filter(Boolean).join(", ");
  $("#mg-who").innerHTML = n ? `<b>${mgWord(n, "получатель", "получателя", "получателей")}</b>: ${escH((d.names || []).join(", "))}${n > (d.names || []).length ? " и другие" : ""}${extra ? `<br><span>${escH(extra)}</span>` : ""}`
    : `<span>${escH(empty)}</span>`;
  const s = d.sample;
  $("#mg-letter").innerHTML = s
    ? `<div class="mg-lh"><span>Кому</span><b>${escH(s.name ? `${s.name} <${s.to}>` : s.to)}</b></div>`
      + `<div class="mg-lh"><span>Тема</span><b>${escH(s.subject || "без темы")}</b></div><div class="mg-lb">${escH(s.body)}</div>`
    : `<p class="mg-lempty">${n ? "Напишите тему и текст — здесь появится письмо, каким его увидит первый получатель." : "Выберите, кому писать."}</p>`;
  const ready = n && a.subject && a.body && i.mail;
  const btn = $("#mg-send");
  btn.disabled = !ready || MG.busy;
  btn.textContent = n ? `Отправить ${mgWord(n, "письмо", "письма", "писем")}` : "Отправить";
  const days = Math.ceil(n / (i.day_max || 300));
  $("#mg-pace").textContent = !i.mail ? "Почта не подключена." : n
    ? `По одному, раз в несколько секунд — займёт около ${Math.max(1, Math.round(n * 8 / 60))} мин.` + (days > 1 ? ` Почта пропускает до ${i.day_max} писем в день — остальные уйдут в следующие дни сами.` : "") + " Итог пришлю."
    : "";
}

async function mgSend() {
  const a = mgArgs(), p = MG.prev || {};
  if (!p.n) return;
  const who = a.source === "clients" ? (a.tag ? `клиентам с меткой «${a.tag}»` : "клиентам") : a.source === "team" ? "сотрудникам" : "по списку";
  if (!(await ask(`Отправить «${a.subject}» — ${mgWord(p.n, "письмо", "письма", "писем")} ${who}? Каждому — своё, по одному; остановить можно в любой момент.`, { ok: "Отправить" }))) return;
  MG.busy = true; $("#mg-send").disabled = true;
  const d = await mgCall("mailing_draft", a);
  const r = d && await mgCall("mailing_start", { id: d.id }, "Рассылка пошла — ход ниже");
  MG.busy = false;
  if (r) { $("#mg-subj").value = ""; $("#mg-body").value = ""; }
  loadMailing();
}

function mgHist(ls) {
  $("#mg-histw").hidden = !ls.length;
  $("#mg-hist").innerHTML = ls.map(c => {
    const done = c.sent + c.failed, pct = c.total ? Math.round(done * 100 / c.total) : 0;
    const when = new Date(c.created * 1000).toLocaleString("ru-RU", { day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" });
    const acts = [];
    if (c.status === "sending" || c.status === "waiting") acts.push(`<button class="btn small" data-stop="${escH(c.id)}">Остановить</button>`);
    if (c.status === "stopped" || c.status === "paused" || c.status === "draft") acts.push(`<button class="btn small" data-go="${escH(c.id)}">${c.status === "draft" ? "Отправить" : "Продолжить"}</button>`);
    if (c.status !== "sending" && c.status !== "waiting") acts.push(`<button class="btn small" data-del="${escH(c.id)}" aria-label="Убрать из списка «${escH(c.subject)}»">Убрать</button>`);
    const errs = (c.errors || []).length ? `<details class="mg-err"><summary>Не дошло: ${c.failed}</summary><ul>${c.errors.map(e => `<li><b>${escH(e.email)}</b> — ${escH(e.err)}</li>`).join("")}</ul></details>` : "";
    return `<li class="mg-c st-${escH(c.status)}"><div class="mg-cmain"><b>${escH(c.subject)}</b>`
      + `<small>${escH(when)} · ${c.kind === "ads" ? "новости и реклама" : "деловое"} · <span class="mg-st">${escH(MG_ST[c.status] || c.status)}</span>${c.waiting ? " — " + escH(c.waiting) : ""}</small>`
      + `<div class="mg-bar" role="progressbar" aria-valuemin="0" aria-valuemax="${c.total}" aria-valuenow="${done}" aria-label="Отправлено ${c.sent} из ${c.total}"><i style="width:${pct}%"></i></div>`
      + `<small>ушло ${c.sent} из ${c.total}${c.failed ? `, не дошло ${c.failed}` : ""}</small>${errs}</div>`
      + `<div class="mg-cacts">${acts.join("")}</div></li>`;
  }).join("");
  $$("#mg-hist [data-stop]").forEach(b => b.onclick = () => mgCall("mailing_stop", { id: b.dataset.stop }, "Остановила — остальным не уйдёт").then(() => loadMailing()));
  $$("#mg-hist [data-go]").forEach(b => b.onclick = () => mgCall("mailing_start", { id: b.dataset.go }, "Продолжаю").then(() => loadMailing()));
  $$("#mg-hist [data-del]").forEach(b => b.onclick = () => mgCall("mailing_forget", { id: b.dataset.del }).then(() => loadMailing()));
}

(function mgInit() {
  $$("#mg-src button").forEach(b => b.onclick = () => mgSrc(b.dataset.s));
  $$("#mg-kind button").forEach(b => b.onclick = () => mgKind(b.dataset.k));
  for (const id of ["mg-list", "mg-subj", "mg-body"]) $("#" + id).addEventListener("input", mgPreview);
  for (const id of ["mg-tag", "mg-box"]) $("#" + id).addEventListener("change", mgPreview);
  $("#mg-ins").onclick = () => {
    const t = $("#mg-body"), at = t.selectionStart ?? t.value.length;
    t.value = t.value.slice(0, at) + "{имя}" + t.value.slice(t.selectionEnd ?? at); t.focus(); t.selectionStart = t.selectionEnd = at + 5; mgPreview();
  };
  $("#mg-send").onclick = mgSend;
  $("#mg-tomail").onclick = () => { const b = $('nav button[data-p="connect"]'); if (b) b.click(); setTimeout(() => { const m = $("#mail-box"); if (m) m.scrollIntoView({ block: "start" }); }, 150); };
  $("#mg-stopsave").onclick = () => mgCall("mailing_stopset", { emails: $("#mg-stoplist").value.split(/\s+/).filter(Boolean) }, "Сохранено").then(() => loadMailing());
  core.on("mailing", () => { if ($("#p-mailing").classList.contains("cur")) loadMailing(); });
  window.loadMailing = loadMailing;
  window.mgOpen = (src) => { const b = $('nav button[data-p="mailing"]'); if (b) { MG.src = src || MG.src; b.click(); } };
})();
