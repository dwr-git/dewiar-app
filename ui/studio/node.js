/* Студия → «Нода Лиры» (0.87, владелец 11.11: «децентрализация спрятана далеко — нужен простой отдельный раздел»).
   Разметка — ui/settings.html #p-node, оформление — studio/node.css, ядро — core/liranode.py (команды lnode_info, lnode_check,
   lnode_join, lnode_set, lnode_stop, lnode_leave; событие lnode — состояние потока ноды).
   Сверху — «сердце» ноды (кольца сети, в центре — этот компьютер: светится, когда работает), состояние словами, одна кнопка
   и сколько заработано сегодня; ниже — «Подходит ли мой компьютер», «Как работать», счёт ноды с сайта и честный журнал. */
const ND = { d: null, check: null, when: "idle", share: "low", model: null, busy: false };
const ndTal = (x) => { const v = +x || 0; return v.toLocaleString("ru-RU", { maximumFractionDigits: v >= 10 ? 1 : v >= 1 ? 2 : 3 }); };
const ndPct = (x) => (Math.round((+x || 0) * 1000) / 10).toLocaleString("ru-RU") + " %";
const ndPl = (n, a, b, c) => { n = Math.abs(n) % 100; const m = n % 10; return n > 10 && n < 20 ? c : m === 1 ? a : m >= 2 && m <= 4 ? b : c; };
const ndTime = (t) => { const d = new Date(t * 1000), now = new Date();
  const hm = d.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
  return d.toDateString() === now.toDateString() ? hm : d.toLocaleDateString("ru-RU", { day: "numeric", month: "short" }) + ", " + hm; };

function ndSeg(id, v) { $$(`#${id} button`).forEach(b => { const on = b.dataset.v === v; b.classList.toggle("on", on); b.setAttribute("aria-checked", on ? "true" : "false"); }); }

/* состояние словами: что сейчас и почему */
function ndState(d) {
  const st = (d.status || {}).state || "off", why = (d.status || {}).why || "", site = ((d.site || {}).node) || {};
  if (!d.joined) return ["none", "Пока не нода", ND.check && ND.check.ok ? "Компьютер подходит — выберите, когда работать, и нажмите «Стать нодой»." : "Проверьте компьютер — и одной кнопкой станьте нодой."];
  if (!d.on) return ["off", "Выключена", "Вопросы сети отвечают серверы Dewiar. Включить — кнопкой ниже."];
  if (site.state === "wait" || /допуск/.test(why)) return ["wait", "Ждёт допуска", "Владелец Dewiar проверяет новые ноды: контрольные вопросы уже идут. Обычно — в течение дня."];
  if (st === "work") return ["work", "Отвечает", "Сейчас ваша модель отвечает на общий вопрос."];
  if (st === "ready") return ["work", "Работает", "На связи и ждёт вопроса. Вопросов в сети то больше, то меньше — это нормально."];
  if (st === "wait") return ["wait", "Пауза", why ? why[0].toUpperCase() + why.slice(1) + "." : "Ждёт подходящего момента."];
  if (st === "error") return ["err", "Не на связи", why || "нет связи с dewiar.pro"];
  return ["wait", "Запускается", "Проверяю подпись правил сети и условия."];
}

function ndRender() {
  const d = ND.d; if (!d) return;
  const [cls, title, why] = ndState(d), hero = $("#nd-hero");
  hero.dataset.st = cls;
  $("#nd-state").textContent = title; $("#nd-why").textContent = why;
  const go = $("#nd-go"), hint = $("#nd-go-hint");
  const canJoin = !!(ND.check && ND.check.ok && ND.model);
  if (!d.joined) { go.textContent = "Стать нодой"; go.disabled = ND.busy || !canJoin; hint.textContent = canJoin ? "ничего не начнётся без этой кнопки" : ND.check ? "компьютер пока не подходит — см. проверку ниже" : "сначала — «Проверить компьютер»"; }
  else if (d.on) { go.textContent = "Выключить"; go.disabled = ND.busy; hint.textContent = "сразу — вопросы ответят серверы Dewiar"; }
  else { go.textContent = "Включить"; go.disabled = ND.busy; hint.textContent = "условия и паузы — как вы выбрали"; }
  go.classList.toggle("primary", !go.disabled && (!d.joined || !d.on));     // неактивная — без заливки: читается в любой теме
  // заработок
  const site = d.site || {}, sn = site.node || null;
  $("#nd-earn").hidden = !d.joined;
  if (d.joined) {
    const est = +(site.est_day || 0);
    $("#nd-tal").textContent = (est > 0 ? "≈ " : "") + ndTal(est);
    $("#nd-tal-l").textContent = (est > 0 && est < 1 ? "талера" : ndPl(Math.round(est), "талер", "талера", "талеров")) + " сегодня";
    const today = sn ? sn.answers_day : d.today, unpaid = sn ? +sn.unpaid_day || 0 : 0;
    $("#nd-cnt").textContent = `${today} ${ndPl(today, "ответ", "ответа", "ответов")} сегодня` + (unpaid ? ` (без оплаты — ${unpaid})` : "")
      + ` · всего начислено ${ndTal(site.paid_total || 0)} тал.`;
  }
  ndSeg("nd-when", d.joined ? d.when : ND.when); ndSeg("nd-share", d.joined ? d.share : ND.share);
  const wt = d.when_text || {}, stt = d.share_text || {};
  $("#nd-when-t").textContent = wt[d.joined ? d.when : ND.when] || ""; $("#nd-share-t").textContent = stt[d.joined ? d.share : ND.share] || "";
  // счёт и журнал
  $("#nd-joined").hidden = !d.joined; $("#nd-leave-row").hidden = !d.joined;
  if (d.joined) {
    const kv = [];
    if (sn) {
      kv.push(["Принято сегодня", `${sn.answers_day} из ${sn.tried_day}` + (sn.bad_day ? ` · не принято ${sn.bad_day}` : "")
        + (sn.unpaid_day ? ` · без оплаты ${sn.unpaid_day}: спрашивающий платил подарочными талерами` : "")]);
      kv.push(["За 30 дней", `${sn.answers_30d} ${ndPl(sn.answers_30d, "ответ", "ответа", "ответов")}`]);
      kv.push(["Начислено всего", `${ndTal(sn.paid_total)} тал.` + (sn.waiting > 0 ? ` · ещё ${ndTal(sn.waiting)} ждут решения` : "")]);
      kv.push(["Доверие", String(sn.trust).replace(".", ",") + (sn.new ? " · новая нода: первые 7 дней ×0,5" : "") + (sn.trust < 0.5 ? " · ниже 0,5 — без начислений" : "")]);
      kv.push(["На сайте", sn.state_text]);
    } else if (site.error) kv.push(["Сайт", site.error]);
    kv.push(["Модель", d.model || "—"]);
    kv.push(["Доля ноде", site.share != null ? `${ndPct(site.share)} от того, что списали со спрашивающего за ваш ответ` : "владелец Dewiar ещё не задал — пока без начислений"]);
    $("#nd-kv").innerHTML = kv.map(([k, v]) => `<span>${escH(k)}</span><b>${escH(v)}</b>`).join("");
    $("#nd-kv-note").textContent = "Сегодняшние талеры — примерно: точно сайт посчитает завтра, за прошедшие сутки.";
    $("#nd-site-st").textContent = sn ? (sn.state === "on" ? "в сети" : sn.state === "wait" ? "ждёт допуска" : sn.state_text) : "—";
    $("#nd-site-st").className = "dws " + (sn && sn.state === "on" ? "ok" : sn ? "run" : "");
    const log = d.journal || [];
    $("#nd-log").innerHTML = log.length ? log.map(x => `<li class="${escH(x.kind)}"><time>${escH(ndTime(x.t))}</time><span>${escH(x.text)}</span></li>`).join("")
      : `<li class="info"><span>Пока пусто — первые записи появятся, когда нода возьмёт вопрос или встанет на паузу.</span></li>`;
  }
  // правила начисления — как подписаны
  const r = d.rules || {}, pay = r.pay || {};
  $("#nd-fp").textContent = r.fp ? ` (отпечаток ${r.fp} — сверьте с объявлением Dewiar)` : "";
  if (pay.coin) {
    $("#nd-pay-body").innerHTML = `<ul>${[`Считается: ${pay.what}.`, `Сколько: ${pay.formula}` + (pay.share != null ? `; доля сейчас — ${ndPct(pay.share)} (не больше ${ndPct(pay.share_max || 0.7)}).` : "; доля пока не задана — начислений нет."),
      `Когда: ${pay.when}; куда — ${pay.to}.`, pay.withdraw ? "" : "Вывода в деньги нет: талеры тратятся внутри Dewiar.", pay.own_questions === false ? "Свои вопросы на свою ноду не попадают." : ""]
      .filter(Boolean).map(x => `<li>${escH(x)}</li>`).join("")}</ul><p class="hint" style="margin:6px 0 0">Эти правила подписаны ключом Dewiar — программа приняла их, только проверив подпись.</p>`;
  } else if (r.error) $("#nd-pay-body").textContent = r.error;
  // точка в меню — нода работает
  const dot = $("#node-dot"); if (dot) dot.classList.toggle("on", !!(d.joined && d.on && cls === "work"));
}

function ndChecks(c) {
  const mark = { true: "✓", false: "✕", null: "!" };
  $("#nd-checks").innerHTML = (c.items || []).map(i => `<li class="${i.ok === true ? "ok" : i.ok === false ? "bad" : "warn"}"><i aria-hidden="true">${mark[String(i.ok)]}</i><div><b>${escH(i.title)}</b><span>${escH(i.text)}</span></div></li>`).join("");
  const st = $("#nd-check-st"); st.textContent = c.ok ? "подходит" : "пока нет"; st.className = "dws " + (c.ok ? "ok" : "bad");
  $("#nd-check-hint").hidden = true;
  // выбор модели — из найденных (без моделей для поиска и распознавания)
  const opts = [];
  (c.models || []).forEach(f => (f.models || []).filter(m => !/embed|whisper|rerank|tts/i.test(m)).forEach(m => opts.push({ base: f.base_url, model: m, app: f.name })));
  const sel = $("#nd-model");
  sel.innerHTML = opts.map((o, i) => `<option value="${i}">${escH(o.model)} — ${escH(o.app)}</option>`).join("");
  ND.opts = opts;
  const pi = c.pick ? opts.findIndex(o => o.base === c.pick.base && o.model === c.pick.model) : -1;
  if (pi >= 0) sel.value = String(pi);
  ND.model = pi >= 0 ? opts[pi] : opts[0] || null;
  $("#nd-model-f").hidden = opts.length < 2 || (ND.d && ND.d.joined);
}

async function ndLoad(fresh) {
  try { ND.d = await core.call("lnode_info", fresh ? { fresh: true } : {}); }
  catch (e) { $("#nd-why").textContent = e.message; return; }
  ndRender();
}

$("#nd-check").onclick = async (ev) => {
  const b = ev.target; b.disabled = true; b.textContent = "Проверяю…";
  $("#nd-checks").innerHTML = `<li class="warn"><i aria-hidden="true">…</i><div><b>Проверяю</b><span>ищу модель и задаю ей обычный вопрос — до 30 секунд</span></div></li>`;
  try { ND.check = await core.call("lnode_check", ND.model ? { base: ND.model.base, model: ND.model.model } : {}); ndChecks(ND.check); }
  catch (e) { $("#nd-checks").innerHTML = `<li class="bad"><i>✕</i><div><b>Не вышло</b><span>${escH(e.message)}</span></div></li>`; }
  b.disabled = false; b.textContent = "Проверить снова";
  ndRender();
};
$("#nd-model").onchange = (e) => { ND.model = (ND.opts || [])[+e.target.value] || null; };
$$("#nd-when button").forEach(b => b.onclick = async () => {
  ND.when = b.dataset.v;
  if (ND.d && ND.d.joined) { try { ND.d = Object.assign(ND.d, await core.call("lnode_set", { when: ND.when })); } catch (e) { toast(e.message); } }
  else if (ND.d) ND.d.when = ND.when;
  ndRender();
});
$$("#nd-share button").forEach(b => b.onclick = async () => {
  ND.share = b.dataset.v;
  if (ND.d && ND.d.joined) { try { ND.d = Object.assign(ND.d, await core.call("lnode_set", { share: ND.share })); } catch (e) { toast(e.message); } }
  else if (ND.d) ND.d.share = ND.share;
  ndRender();
});
$("#nd-go").onclick = async () => {
  const d = ND.d || {}, res = $("#nd-res");
  ND.busy = true; ndRender(); res.className = "res"; res.textContent = !d.joined ? "Подключаю ноду: приглашение, ключ ноды, подпись правил…" : "";
  try {
    if (!d.joined) {
      await core.call("lnode_join", { base: ND.model.base, model: ND.model.model, when: ND.when, share: ND.share });
      res.className = "res ok"; res.textContent = "Готово: вы — нода. Сначала владелец Dewiar допустит её, потом пойдут вопросы.";
    } else if (d.on) { await core.call("lnode_stop"); res.className = "res ok"; res.textContent = "Выключена. Вопросы отвечают серверы Dewiar."; }
    else { await core.call("lnode_set", { on: true }); res.className = "res ok"; res.textContent = "Включена."; }
  } catch (e) { res.className = "res bad"; res.textContent = e.message; }
  ND.busy = false;
  await ndLoad(true);
};
$("#nd-leave").onclick = async () => {
  if (!await ask("Перестать быть нодой? Ключ ноды сотрётся, накопленные талеры останутся. Вернуться можно в любой момент — с тем же доверием.")) return;
  try { await core.call("lnode_leave"); $("#nd-res").className = "res ok"; $("#nd-res").textContent = "Вы больше не нода."; }
  catch (e) { $("#nd-res").className = "res bad"; $("#nd-res").textContent = e.message; }
  ndLoad(true);
};
$("#nd-inv").onclick = async (ev) => {
  const b = ev.target; b.disabled = true;
  try {
    const d = await core.call("lnet_invite");
    $("#nd-inv-cmd").textContent = d.cmd; $("#nd-inv-cmd").hidden = false; $("#nd-inv-copy").hidden = false;
    $("#nd-res").className = "res ok";
    $("#nd-res").textContent = `Команда готова — вставьте её в терминал сервера до ${new Date(d.exp * 1000).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })}.`;
  } catch (e) { $("#nd-res").className = "res bad"; $("#nd-res").textContent = e.message; }
  b.disabled = false;
};
$("#nd-inv-copy").onclick = async () => {
  let okc = false; try { await navigator.clipboard.writeText($("#nd-inv-cmd").textContent); okc = true; } catch (e) { }
  toast(okc ? "Скопировано" : "Выделите команду и скопируйте (Ctrl+C)");
};
document.addEventListener("studio-sec", (e) => { if (e.detail === "node") ndLoad(true); });
core.on("lnode", (e) => { if (!ND.d) return; Object.assign(ND.d, e); ndRender(); });
core.on("hello", () => core.call("lnode_info", { lite: true }).then(d => { ND.d = Object.assign(ND.d || {}, d); ndRender(); }).catch(() => {}));
