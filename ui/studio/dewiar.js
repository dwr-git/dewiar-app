/* Студия Dewiar: раздел «Dewiar.pro» (сводка по сервису карточками), Dewiar Облако по ключу (карточка в «Мозге», заряд,
   пополнение, расход), подключение своего сервера моделей — и запуск студии: обработчик события hello.
   Файлы студии подключаются по порядку из ui/settings.html и делят одну глобальную область; этот файл последний, поэтому
   всё, что нужно всем разделам при старте, — здесь: core.on("hello") раздаёт снимок состояния ядра (S, personas,
   пресеты, голоса) функциям всех файлов, а bindFields() в конце вешает обработчики на поля data-k.
   hello приходит при каждом переподключении к ядру — обработчик должен выдерживать повторный запуск.
   Команды ядра: device, sync_*, cloud_*, account_*, net*, av_*, update_*, rag_scope, probe_server, phone_config. */
/* ---------- Dewiar.pro: всё о сервисе на одной странице ----------
   DW — последние ответы ядра по каждой карточке; dwRender() рисует всё из DW, dwLoad(full) обновляет DW
   (full — «Проверить всё»: заново спросить сайт, сеть и антивирус). dwSet — значок состояния карточки. */
const DW = { acc: null, cloud: null, dev: null, av: null, tg: null, mx: null, upd: null, kb: null, checked: {} };
const dwSet = (id, cls, text) => { const e = $("#dws-" + id); if (!e) return; e.className = "dws " + (cls || ""); e.textContent = text; };
function dwSyncRender() {
  const s = DW.sync; if (!s) return;
  const t = s.at ? new Date(s.at * 1000) : null, devs = (s.devices || []).map(d => d.name).filter(Boolean);
  $("#dw-sync-on").checked = !!s.on; $("#dw-sync-on").disabled = !s.available;
  $("#dw-sync-via").textContent = s.available ? "по " + s.via : "нужен вход аккаунтом или ключ Dewiar (карточки выше)";
  $("#dw-sync-now").disabled = !s.available || !s.on;
  $("#dw-sync-st").textContent = !s.available ? "" : !s.on ? "выключено" : s.ok === false ? s.error
    : t ? `в ${t.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })}` + (devs.length ? ` · ещё: ${devs.join(", ")}` : " · других устройств пока нет") : "первая — в течение минуты";
  dwSet("sync", !s.available || !s.on ? "" : s.ok === false ? "bad" : s.ok ? "ok" : "", !s.available ? "нет входа" : !s.on ? "выключена" : s.ok === false ? "ошибка" : s.ok ? "работает" : "—");
  // шифрование на устройстве: включено, ждём ключ от своего устройства или выключено
  const e = s.e2e || {};
  $("#dw-e2e").checked = !!e.on; $("#dw-e2e").disabled = !s.available || !s.on;
  $("#dw-e2e-why").textContent = e.on ? "Включено: в облаке — только шифротекст; ключ — у ваших устройств. Новое устройство получит его само, когда эти будут на связи."
    : e.remote && !e.key ? `Ваши данные зашифрованы на другом устройстве — жду ключ от него (оно должно быть включено и на связи)${e.locked ? `; пока не открыто записей: ${e.locked}` : ""}.`
    : "Заметки, дела, деньги и память уходят в облако уже зашифрованными — ключ знают только ваши устройства, сервер dewiar.pro их не прочитает. Включите на одном — остальные получат ключ сами.";
}
$("#dw-e2e").onchange = async (ev) => {
  const on = ev.target.checked;
  if (!on && !await ask("Выключить шифрование на этом компьютере? Свои изменения он снова будет отправлять открытыми. На других устройствах выключите отдельно.")) { ev.target.checked = true; return; }
  ev.target.disabled = true;
  DW.sync = await core.call("sync_e2e", { on }).catch(x => (toast(x.message), DW.sync)); dwSyncRender();
};
$("#dw-sync-on").onchange = async (e) => { DW.sync = await core.call("sync_set", { on: e.target.checked }).catch(x => (toast(x.message), DW.sync)); dwSyncRender(); };
$("#dw-sync-now").onclick = async (e) => { e.target.disabled = true; $("#dw-sync-st").textContent = "синхронизирую…";
  DW.sync = await core.call("sync_now").catch(x => (toast(x.message), DW.sync)); dwSyncRender(); };
function dwRender() {
  dwSyncRender();
  const a = DW.acc || {}, c = DW.cloud || {}, d = DW.dev, st = (S && S.stt) || {}, tt = (S && S.tts) || {};
  // аккаунт
  $("#dw-acc-out").style.display = a.logged_in ? "none" : ""; $("#dw-acc-in").style.display = a.logged_in ? "" : "none";
  $("#dw-who").textContent = a.logged_in ? (a.user && a.user.login || a.login) : "";
  $("#dw-host").textContent = (a.server || "https://dewiar.pro").replace(/^https?:\/\//, "");
  if (!a.logged_in && a.login && !$("#dw-login").value) $("#dw-login").value = a.login;
  if (a.server && !/\/\/dewiar\.pro\/?$/.test(a.server)) $("#dw-server").placeholder = a.server;
  if (a.problem && !a.logged_in) { $("#dw-acc-res").className = "res bad"; $("#dw-acc-res").textContent = a.problem; }
  dwSet("acc", a.logged_in ? "ok" : a.problem ? "bad" : "", a.logged_in ? "вход выполнен" : a.problem ? "вход устарел" : "не выполнен");
  // модели
  const on = !!c.connected;
  $("#dw-cloud-on").style.display = on ? "" : "none"; $("#dw-cloud-off").style.display = on ? "none" : "";
  if (on) {
    // ключ облака показывает заряд в %, а вход аккаунтом (c.site) — общий счёт сайта в ИИ-талерах
    const err = c.error && c.percent === undefined, pct = Math.max(0, Math.min(100, c.percent ?? 0));
    const bal = c.balance_text || (c.balance != null ? String(c.balance).replace(".", ",") + " тал." : "");
    $("#dw-pct").textContent = err ? "—" : c.site ? bal : pct + "%"; $("#dw-fill").style.width = (err ? 0 : Math.max(pct, c.empty ? 0 : 2)) + "%";
    $("#dw-turns").textContent = err ? c.error : c.empty ? (c.site ? "на счёте закончились ИИ-талеры" : "заряд закончился")
      : c.site ? "общий счёт с сайтом" + (c.turns ? ` · примерно на ${c.turns.toLocaleString("ru-RU")} ${turnsWord(c.turns)}` : "") : `хватит примерно на ${(c.turns || 0).toLocaleString("ru-RU")} ${turnsWord(c.turns || 0)}`;
    $("#dw-cloud-who").textContent = (c.site ? "Счёт dewiar.pro" : c.account ? "По аккаунту dewiar.pro" : "Ключ …" + (c.tail || "")) + (c.active ? " · сейчас отвечают модели Dewiar" : " · сейчас отвечает ваша модель");
    $("#dw-cloud-use").style.display = c.active ? "none" : "";
    dwSet("cloud", err || c.frozen || c.empty ? "bad" : c.low ? "warn" : "ok", err ? "нет связи" : c.frozen ? "приостановлен" : c.empty ? "заряд 0" : c.low ? "мало заряда" : c.active ? "отвечают" : "в запасе");
  } else dwSet("cloud", a.logged_in ? "warn" : "", "не подключены");
  $("#dw-cloud-acc").style.display = !on && a.logged_in ? "" : "none";
  // речь на сервере
  const sttSrv = st.engine === "remote" && st.remote && (st.remote.cloud || st.remote.from_account);
  const canStt = !!(d && (d.cloud_stt || d.account_stt)), ttsSrv = tt.engine === "remote" && tt.remote && tt.remote.from_account;
  $("#dw-stt").checked = !!sttSrv; $("#dw-stt").disabled = !canStt && !sttSrv;
  $("#dw-stt-why").textContent = canStt || sttSrv ? "Быстро и точно даже на слабом компьютере; немного расходует заряд."
    : a.logged_in || (DW.cloud && DW.cloud.connected) ? "На сервере Dewiar распознавание речи сейчас не включено — компьютер распознаёт сам. Появится — переключатель станет доступен."
    : "Станет доступно после входа в аккаунт (или с ключом Dewiar).";
  const canTts = !!(a.logged_in && a.services && a.services.tts) || !!(d && d.cloud_tts);
  $("#dw-tts-row").style.display = canTts || ttsSrv ? "" : "none"; $("#dw-tts").checked = !!ttsSrv;
  dwSet("speech", sttSrv ? "ok" : canStt ? "" : "", sttSrv ? (ttsSrv ? "слух и голос" : "слух на сервере") : canStt ? "выключено"
    : a.logged_in || (DW.cloud && DW.cloud.connected) ? "нет на сервере" : "нужен вход");
  // знания
  const kbN = (personas || []).filter(p => (p.knowledge || []).length).length;
  if (!a.logged_in) { dwSet("kb", "", "нужен вход"); $("#dw-kb-text").textContent = "Ваши документы на dewiar.pro и публичная библиотека. Загружают их на сайте, ассистент ищет в них ответы. Нужен вход в аккаунт."; }
  else if (DW.kb && DW.kb.error) { dwSet("kb", "bad", "не отвечают"); $("#dw-kb-text").textContent = "Сайт Знаний не ответил: " + DW.kb.error + ". Нажмите «Проверить всё» ещё раз — если не поможет, проверьте «Сеть»."; }
  else {
    const n = DW.kb ? DW.kb.bases.length : null;
    dwSet("kb", n ? "ok" : n === 0 ? "warn" : "", n ? `баз: ${n}` : n === 0 ? "баз нет" : "подключены");
    $("#dw-kb-text").textContent = (n != null ? (n ? `Доступно баз: ${n} — ваши папки и разделы библиотеки.` : "На сайте пока нет ваших папок — загрузите документы на dewiar.pro.") : "Ваши документы и публичная библиотека.")
      + (kbN ? ` Базы подключены у персонажей: ${kbN}.` : " Подключите базу персонажу — он будет отвечать по ней, с цитатами.");
  }
  // мессенджеры
  const tg = DW.tg || {}, mx = DW.mx || {};
  $("#dw-tg").textContent = tg.paired ? `подключён: @${tg.bot}` : tg.connected ? "ждёт «Запустить» в Telegram" : "не подключён";
  $("#dw-mx").textContent = mx.paired ? "подключён" + (mx.bot ? ": " + mx.bot : "") : mx.connected ? "ждёт «Начать» в MAX" : "не подключён";
  $("#dw-tg-go").textContent = tg.paired ? "Настроить" : "Подключить"; $("#dw-mx-go").textContent = mx.paired ? "Настроить" : "Подключить";
  dwSet("chat", tg.paired || mx.paired ? "ok" : tg.connected || mx.connected ? "warn" : "", [tg.paired && "Telegram", mx.paired && "MAX"].filter(Boolean).join(" и ") || (tg.connected || mx.connected ? "ждут подтверждения" : "не подключены"));
  // компьютер
  if (d) {
    $("#dw-pc-kv").innerHTML = `<span>Память</span><div>${d.ram} ГБ${d.free ? ` (свободно ${d.free})` : ""}</div><span>Процессор</span><div>${d.cores} ${plural(d.cores, "ядро", "ядра", "ядер")}</div>`
      + `<span>Распознавание</span><div>${{ gigaam: "GigaAM (точное, тяжёлое)", vosk: "Vosk (лёгкое)", remote: "сервер" }[d.stt] || d.stt}</div><span>Голос</span><div>${{ vosk: "Vosk TTS", piper: "Piper (лёгкий)", remote: "сервер", espeak: "системный", off: "выключен" }[d.tts] || d.tts}</div>`;
    $("#dw-light").checked = !!d.light;
    $("#dw-pc-adv").textContent = d.advice || (d.level === "ok" ? "Мощности хватает — всё работает на этом компьютере." : "");
    dwSet("pc", d.level === "ok" ? "ok" : d.stt_server ? "ok" : "warn", d.level === "ok" ? "мощности хватает" : d.stt_server ? "слабый — помогает сервер" : d.level === "very_weak" ? "очень слабый" : "слабый");
    const weak = d.level !== "ok" && !d.stt_server, tight = !!(d.mem && d.mem.tight);
    $("#dw-weak").style.display = weak || tight ? "" : "none";
    if (tight && !weak) $("#dw-weak").innerHTML = `<b>Сейчас не хватает памяти</b><p>${escH(d.mem.text || "Открыто много других программ — окна и голос могут тормозить. Закройте лишнее.")}</p>`;
    if (tight) dwSet("pc", "warn", "мало свободной памяти");
    if (weak) $("#dw-weak").innerHTML = `<b>На этом компьютере мало мощности (${escH(d.why)})</b><p>${d.light ? "Включён лёгкий режим — ассистент работает, но распознаёт речь попроще." : "Ассистент может тормозить."}
      Чтобы стало быстро и точно, пусть думает и слушает сервер Dewiar:</p>
      <ol>${a.logged_in || d.cloud ? `<li>Включите ниже «Распознавать речь на сервере» — и всё.</li>` : `<li><a href="#" data-free>«Подключить бесплатно»</a> — без регистрации, за минуту (или войдите в аккаунт dewiar.pro ниже, если он у вас есть).</li><li>Готово: модели и распознавание речи включатся на сервере сами.</li>`}</ol>`;
    $("#dw-dot").classList.toggle("on", weak || tight);
  }
  // антивирус
  const av = DW.av;
  $("#dwc-av").style.display = av && av.supported ? "" : "none";
  if (av && av.supported) {
    const m = av.main || {}, adv = av.advice || {};
    $("#dw-av-text").textContent = (av.products || []).length ? `Установлен: ${(av.products || []).map(p => p.name + (p.on ? "" : " (выключен)")).join(", ")}.` + (av.missing.length ? " Часть файлов Dewiar пропала — похоже, антивирус убрал их в карантин." : " Если он мешает Dewiar (ложная тревога), добавьте папку в исключения:")
      : "Если антивирус мешает Dewiar (ложная тревога), добавьте папку в исключения:";
    $("#dw-av-path").textContent = (av.paths || [])[0] || "";
    $("#dw-av-steps").innerHTML = (adv.steps || []).slice(0, 3).map(x => `<li>${escH(x)}</li>`).join("");
    $("#dw-av-ex").style.display = adv.auto ? "" : "none";
    dwSet("av", av.missing.length ? "bad" : "ok", av.missing.length ? "убрал файлы" : (m.name || "в порядке"));
  }
  // сеть: если dewiar.pro не открывается напрямую — свой прокси или прокси Dewiar; px.dataset.dirty — поле правят, не перетираем
  const n = DW.net;
  if (n) {
    const px = $("#dw-px");
    if (document.activeElement !== px && !px.dataset.dirty) px.value = n.proxy || "";
    $("#dw-px-dw").checked = !!n.dewiar;
    $("#dw-rv").checked = n.reserve !== false;
    $("#dw-rv").disabled = !!(n.proxy || n.dewiar);        // свой прокси или прокси Dewiar включены — и так всё через прокси
    $("#dw-rv-hint").dataset.state = n.reserve_used ? "used" : n.reserve_ready ? "ready" : "";
    $("#dw-rv-hint").textContent = n.proxy || n.dewiar ? "Не нужен: запросы к Dewiar уже идут через прокси."
      : n.reserve_used ? "Сейчас работает: dewiar.pro напрямую не открывался — программа ходит через прокси Dewiar."
      : n.reserve_ready ? "Готов: если провайдер или сеть не пустят к dewiar.pro, программа сама пойдёт через прокси Dewiar и скажет об этом."
      : "Сначала — напрямую. Если провайдер или сеть не пускают к dewiar.pro, программа сама идёт через прокси Dewiar, полученный заранее (нужен вход аккаунтом или ключ Dewiar).";
    $("#dw-web").checked = !(S && S.net && S.net.web_via === false);   // S ещё не пришло — без падения (studio1022 моргал)
    const ck = n.check, viaOk = ck && ck.proxy && ck.proxy[0], dirOk = ck && ck.direct[0];
    if (ck) { $("#dw-net-res").className = "res " + (dirOk || viaOk ? "ok" : "bad"); $("#dw-net-res").textContent = ck.advice; }
    if (ck) dwSet("net", ck.proxy ? (viaOk ? "ok" : "bad") : (dirOk ? "ok" : "bad"), ck.proxy ? (viaOk ? "через прокси" : "прокси не работает") : (dirOk ? "напрямую" : "сайт не открывается"));
    else dwSet("net", n.on ? "ok" : "", n.on ? (n.via === "dewiar" ? "прокси Dewiar" : "через прокси") : "напрямую");
    if (n.dewiar_error) { $("#dw-net-res").className = "res bad"; $("#dw-net-res").textContent = "Прокси Dewiar: " + n.dewiar_error; }
  }
  // обновления
  const u = DW.upd;
  if (u) {
    $("#dw-upd-text").textContent = u.available ? `Доступна версия ${u.available.version} — уже скачана.` : `Dewiar ${u.current}` + (u.error ? ` · не проверилось: ${u.error}` : u.checked ? " — последняя версия." : "");
    $("#dw-upd-open").style.display = u.available ? "" : "none";
    dwSet("upd", u.available ? "warn" : u.error ? "bad" : "ok", u.available ? "есть новая" : u.error ? "ошибка" : "последняя");
  }
  // свёрнутый блок «Компьютер, сеть, антивирус и обновления»: в заголовке — их метки; что-то не так — раскрывается сам
  // (если человек сам его не сворачивал)
  const tech = ["pc", "net", "upd"].concat(av && av.supported ? ["av"] : []), more = $("#dw-more");
  const techBad = tech.filter(k => / (bad|warn)/.test($("#dws-" + k).className));
  $("#dw-more-sum").innerHTML = (techBad.length ? techBad : tech).map(k => $("#dws-" + k)).filter(e => e.textContent.trim() && e.textContent !== "—")
    .map(e => `<span class="${escH(e.className)}">${escH(e.textContent)}</span>`).join("");
  if (techBad.length && !more.dataset.user) more.open = true;
  const cards = ["acc", "cloud", "speech", "kb", "chat", "pc", "net", "upd"].concat(av && av.supported ? ["av"] : []);
  const okN = cards.filter(k => ($("#dws-" + k).className || "").includes(" ok")).length, badN = cards.filter(k => ($("#dws-" + k).className || "").includes(" bad")).length;
  $("#dw-sum").textContent = DW.checked.at ? `Работает ${okN} из ${cards.length}` + (badN ? ` · требует внимания: ${badN}` : "") + ` · проверено в ${new Date(DW.checked.at).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })}` : "";
}
/* Карточка «Рефералы» — только код, сколько приглашено и дорога в раздел «Рефералы» (studio/refs.js) */
const refTal = (x) => String(Math.round((+x || 0) * 100) / 100).replace(".", ",");
async function dwRef() {
  let d;
  try { d = await core.call("ref_info"); } catch (e) { dwSet("ref", "", "нужен вход"); $("#dw-ref-text").textContent = "Поделитесь Dewiar — подарки талерами и вам, и другу. Сначала войдите аккаунтом или подключите ключ Dewiar."; return; }
  const list = d.invited || [];
  dwSet("ref", list.some(x => x.paid) ? "ok" : list.length ? "run" : "", list.length ? `приглашено ${list.length}` : "никого");
  $("#dw-ref-text").textContent = `Ваш код — ${d.code}.` + (list.length ? ` Приглашено ${list.length}, засчитано ${list.filter(x => x.paid).length}` + (d.earned > 0 ? `, получено ${refTal(d.earned)} тал.` : ".")
    : d.bonus > 0 ? ` Вам +${refTal(d.bonus)} тал. за каждого друга, который попользуется Dewiar ${d.days} дн.` : "");
}
$("#dw-ref-open").onclick = () => $('nav button[data-p="ref"]').click();
async function dwLoad(full) {
  dwRef();
  const tasks = [core.call("device").then(x => DW.dev = x), core.call("sync_status").then(x => DW.sync = x), core.call("cloud_status", { refresh: !!full }).then(x => DW.cloud = x), core.call("update_status").then(x => DW.upd = x)];
  if (!DW.av || full) tasks.push(core.call("av_status").then(x => DW.av = x));
  if (full) tasks.push(core.call("account_check").then(x => DW.acc = x));
  // net_check — медленная проверка соединения; без full оставляем её прошлый результат
  tasks.push(core.call(full ? "net_check" : "net").then(x => DW.net = full || !DW.net || !DW.net.check ? x : Object.assign(x, { check: DW.net.check })));
  await Promise.all(tasks.map(t => t.catch(() => {})));
  if (DW.acc && DW.acc.logged_in && (full || !DW.kb)) DW.kb = await core.call("rag_scope", { force: !!full }).catch(e => ({ error: e.message, bases: [] }));
  if (full) DW.checked.at = Date.now();
  dwRender();
  dwMeLoad();
}
/* «Как к вам обращаться» (0.69): автоподключение без анкеты — имя и контакт оставляют здесь, когда захотят (core contact_get/set
   → cloud.php /me/contact). Карточка — только у подключённых сами; у вошедших аккаунтом и по заявке её нет. */
async function dwMeLoad() {
  const box = $("#dw-me"); if (!box) return;
  const c = (S && S.cloud) || {};
  if (!c.auto || !c.key) { box.hidden = true; return; }
  box.hidden = false;
  try {
    const d = await core.call("contact_get");
    if (!$("#dw-me-name").dataset.dirty) $("#dw-me-name").value = d.name && d.name !== "Без имени" ? d.name : "";
    if (!$("#dw-me-contact").dataset.dirty) $("#dw-me-contact").value = d.contact || "";
  } catch (e) { }
}
["#dw-me-name", "#dw-me-contact"].forEach(id => { const i = $(id); if (i) { i.oninput = () => { i.dataset.dirty = "1"; }; i.onkeydown = (e) => { if (e.key === "Enter") $("#dw-me-go").click(); }; } });
if ($("#dw-me-go")) $("#dw-me-go").onclick = async (ev) => {
  const b = ev.target, res = $("#dw-me-res"), name = $("#dw-me-name").value.trim(), contact = $("#dw-me-contact").value.trim();
  if (!name && !contact) { res.className = "res bad"; res.textContent = "Напишите имя или контакт"; return; }
  b.disabled = true; res.className = "res"; res.textContent = "сохраняю…";
  try { await core.call("contact_set", { name, contact }); res.className = "res ok"; res.textContent = "Сохранено — спасибо!";
    $("#dw-me-name").dataset.dirty = $("#dw-me-contact").dataset.dirty = ""; }
  catch (e) { res.className = "res bad"; res.textContent = e.message; }
  b.disabled = false;
};
$("#dw-px").oninput = () => { $("#dw-px").dataset.dirty = "1"; };
$("#dw-px").onkeydown = (e) => { if (e.key === "Enter") $("#dw-px-save").click(); };
$("#dw-px-save").onclick = async (ev) => {
  const b = ev.target, res = $("#dw-net-res"), v = $("#dw-px").value.trim();
  b.disabled = true; res.className = "res"; res.textContent = v ? "проверяю, открывается ли dewiar.pro через этот прокси…" : "выключаю прокси…";
  try { DW.net = await core.call("net_proxy", { proxy: v }); $("#dw-px").dataset.dirty = ""; dwRender(); }
  catch (e) { res.className = "res bad"; res.textContent = e.message; dwSet("net", "bad", "не сохранён"); }
  b.disabled = false;
};
$("#dw-px-dw").onchange = async (ev) => {
  const on = ev.target.checked, res = $("#dw-net-res");
  ev.target.disabled = true; res.className = "res"; res.textContent = on ? "получаю прокси с dewiar.pro и проверяю…" : "выключаю…";
  try { DW.net = await core.call("net_dewiar", { on }); dwRender(); }
  catch (e) { res.className = "res bad"; res.textContent = e.message; }
  ev.target.disabled = false;
};
$("#dw-web").onchange = (ev) => save({ net: { web_via: ev.target.checked } });
$("#dw-rv").onchange = async (ev) => {
  const on = ev.target.checked; ev.target.disabled = true;
  try { DW.net = Object.assign(DW.net || {}, await core.call("net_reserve", { on })); dwRender(); }
  catch (e) { $("#dw-net-res").className = "res bad"; $("#dw-net-res").textContent = e.message; }
  ev.target.disabled = false;
};
core.on("account", e => { DW.acc = e.account; DW.kb = null; if ($("#p-dw").classList.contains("cur")) dwLoad(); });
core.on("cloud", e => { DW.cloud = e; if ($("#p-dw").classList.contains("cur")) dwRender(); });
core.on("telegram", e => { DW.tg = e; dwRender(); });
core.on("max", e => { DW.mx = e; dwRender(); });
core.on("device", e => { DW.dev = e; dwRender(); });
core.on("update", e => { DW.upd = e.update; });
$("#dw-check").onclick = async (ev) => {
  ev.target.disabled = true; $("#dw-sum").textContent = "проверяю…";
  ["acc", "cloud", "speech", "kb", "chat", "pc", "net", "upd", "av"].forEach(k => dwSet(k, "run", "проверяю…"));
  try {
    await core.call("update_check").then(x => DW.upd = x).catch(() => {});
    await dwLoad(true);
    const c = DW.cloud || {};
    if (c.connected && c.active) {                      // модели Dewiar действительно отвечают? (профиль облака ядро ведёт под id "dewiar-cloud")
      dwSet("cloud", "run", "спрашиваю модель…");
      const r = await core.call("llm_test", { profile: S.llm.profiles["dewiar-cloud"] }).catch(e => ({ error: e.message }));
      if (!r || r.error || r.ok === false) { dwSet("cloud", "bad", "не отвечают"); $("#dw-cloud-res").className = "res bad"; $("#dw-cloud-res").textContent = (r && r.error) || "модель не ответила"; }
      else { $("#dw-cloud-res").className = "res ok"; $("#dw-cloud-res").textContent = "Модель ответила — всё работает."; }
    }
  } finally { ev.target.disabled = false; dwRender(); }
};
$("#dw-go").onclick = async () => {
  const login = $("#dw-login").value.trim(), password = $("#dw-pass").value, r = $("#dw-acc-res");
  // 6 цифр вместо логина или пароля — это код «Добавить устройство» с другого устройства, а не вход (пакет 22.10, №167:
  // «код у меня перед глазами» — пять раз «неверный логин или пароль», потом сайт закрыл вход на 15 минут)
  const code = /^\d{6}$/.test(login.replace(/[\s-]/g, "")) ? login.replace(/[\s-]/g, "") : "";   // в поле логина — 6 цифр: это код
  if (code) {
    $("#dw-go").disabled = true; r.className = "res"; r.textContent = "Это код с другого устройства — подключаю по нему…";
    try { await core.call("pair_claim", { code }); $("#dw-pass").value = ""; r.className = "res ok"; r.textContent = "Подключено по коду — как на том устройстве."; setTimeout(() => dwLoad(), 1500); }
    catch (e) { r.className = "res bad"; r.textContent = e.message + " (код живёт 10 минут: возьмите новый — «Устройства» → «Подключить ещё устройство» на том устройстве)"; }
    finally { $("#dw-go").disabled = false; }
    return;
  }
  if (!login || !password) { r.className = "res bad"; r.textContent = "Введите логин и пароль"; return; }
  $("#dw-go").disabled = true; r.className = "res"; r.textContent = "Вхожу…";
  // после входа ядро само подключает модели и Знания аккаунта — карточки перечитываем чуть позже
  try { const a = await core.call("account_login", { server: $("#dw-server").value.trim() || (DW.acc && DW.acc.server) || "", login, password }); $("#dw-pass").value = ""; renderAccount(a); DW.acc = a; r.className = "res ok"; r.textContent = "Вход выполнен — модели и Знания подключаются…"; setTimeout(() => dwLoad().then(() => { r.textContent = "Вход выполнен."; }), 2500); }
  catch (e) {
    r.className = "res bad"; r.textContent = e.message;
    const pc = String(password).replace(/[\s-]/g, "");
    if (/^\d{6}$/.test(pc) && /неверн|логин|пароль/i.test(e.message))     // в поле пароля — 6 цифр: может, это код с другого устройства
      try { await core.call("cloud_connect", { key: pc }); $("#dw-pass").value = ""; r.className = "res ok"; r.textContent = "Это был код с другого устройства — подключено по нему."; setTimeout(() => dwLoad(), 1500); } catch (x) { }
  } finally { $("#dw-go").disabled = false; }
};
$("#dw-pass").onkeydown = (e) => { if (e.key === "Enter") $("#dw-go").click(); };
$("#dw-out").onclick = async () => { if (await ask("Выйти из аккаунта dewiar.pro? Модели и Знания по аккаунту отключатся.")) core.call("account_logout").then(a => { renderAccount(a); DW.acc = a; DW.kb = null; $("#dw-acc-res").textContent = ""; dwLoad(); }).catch(e => toast(e.message)); };
$("#dw-cloud-use").onclick = () => $("#cc-use").click();
$("#dw-cloud-go").onclick = async (ev) => { const r = $("#dw-cloud-res"); ev.target.disabled = true; r.className = "res"; r.textContent = "подключаю по аккаунту…";
  try { await cloudUse(); r.className = "res ok"; r.textContent = "Модели Dewiar подключены — отвечают они."; dwLoad(); } catch (e) { r.className = "res bad"; r.textContent = e.message; } ev.target.disabled = false; };
$("#dw-topup").onclick = () => { $('nav button[data-p="brain"]').click(); setTimeout(() => { $("#cc-top").click(); $("#cloud-card").scrollIntoView({ behavior: "smooth" }); }, 200); };
$("#dw-key-go").onclick = async () => { const r = $("#dw-cloud-res"), key = $("#dw-key").value.trim(); if (!key) return; r.className = "res"; r.textContent = "проверяю ключ…";
  try { const c = await core.call("cloud_connect", { key }); DW.cloud = c; cloudFill(c); renderProfiles(); $("#dw-key").value = ""; r.className = "res ok"; r.textContent = "Ключ подключён."; dwLoad(); } catch (e) { r.className = "res bad"; r.textContent = e.message; } };
$("#dw-stt").onchange = async (e) => {
  const on = e.target.checked, d = DW.dev || {}, r = $("#dw-speech-res");
  try {
    if (on) await core.call(d.cloud_stt ? "cloud_stt" : "account_stt", { on: true });
    else await core.call((S.stt.remote || {}).cloud ? "cloud_stt" : "account_stt", { on: false });
    r.className = "res ok"; r.textContent = on ? "Речь распознаёт сервер Dewiar." : "Речь распознаёт этот компьютер.";
  } catch (x) { e.target.checked = !on; r.className = "res bad"; r.textContent = x.message; }
  dwLoad();
};
$("#dw-tts").onchange = async (e) => { const on = e.target.checked;
  const d = DW.dev || {}, how = on ? (d.account_tts ? "account_tts" : "cloud_tts") : (S.tts.remote || {}).cloud ? "cloud_tts" : "account_tts";
  try { await core.call(how, { on }); $("#dw-speech-res").className = "res ok"; $("#dw-speech-res").textContent = on ? "Голос — с сервера Dewiar." : "Голос — этого компьютера."; }
  catch (x) { e.target.checked = !on; toast(x.message); } dwLoad(); };
$("#dw-light").onchange = async (e) => { const on = e.target.checked;
  try { const r = await core.call("device_light", { on }); DW.dev = r; toast(on ? "Лёгкий режим включён" : "Лёгкий режим выключен" + (r.done && r.done.length ? ": " + r.done.join(", ") : "")); }
  catch (x) { e.target.checked = !on; toast(x.message); } dwRender(); };
$("#dw-ask").onclick = async () => { const q = $("#dw-q").value.trim(); if (!q) return; $("#dw-ask").disabled = true; $("#dw-ans").textContent = "Ищу в Знаниях…";
  try { const r = await core.call("account_ask", { question: q }); $("#dw-ans").textContent = r.answer + (r.sources.length ? "\n\nИсточники: " + r.sources.join("; ") : ""); }
  catch (e) { $("#dw-ans").textContent = e.message; } finally { $("#dw-ask").disabled = false; } };
$("#dw-q").onkeydown = (e) => { if (e.key === "Enter") $("#dw-ask").click(); };
$("#dw-more > summary").addEventListener("click", () => { $("#dw-more").dataset.user = "1"; });
$("#dw-tts-sec").onclick = (e) => { e.preventDefault(); $('nav button[data-p="voice"]').click(); };
$("#acc-goto-btn").onclick = () => { $('nav button[data-p="dw"]').click(); setTimeout(() => { const f = $("#dw-login"); if (f && f.offsetParent) f.focus(); }, 200); };
$("#dw-kb-persona").onclick = () => $('nav button[data-p="personas"]').click();
const dwGoCard = (id) => { $('nav button[data-p="connect"]').click(); setTimeout(() => $(id).scrollIntoView({ behavior: "smooth", block: "start" }), 150); };
$("#dw-tg-go").onclick = () => dwGoCard("#tg-box");
$("#dw-mx-go").onclick = () => dwGoCard("#mx-box");
$("#dw-av-copy").onclick = async () => { const p = (DW.av && DW.av.paths || [])[0] || ""; let okc = false;
  // в окне pywebview буфер обмена страницы бывает недоступен — тогда копирует ядро (av_copy)
  try { await navigator.clipboard.writeText(p); okc = true; } catch (e) { okc = !!(await core.call("av_copy").catch(() => null) || {}).ok; }
  $("#dw-av-res").className = okc ? "res ok" : "res"; $("#dw-av-res").textContent = okc ? "Путь скопирован — вставьте его в антивирусе (Ctrl+V)." : "Выделите путь выше и скопируйте (Ctrl+C)."; };
$("#dw-av-ex").onclick = async () => { const r = $("#dw-av-res");
  const x = await core.call("av_exclude").catch(e => ({ error: e.message }));
  r.className = x && x.ok ? "res ok" : "res bad"; r.textContent = x && x.ok ? "Открыла настройки Защитника. «Исключения» → «Добавить исключение» → «Папка» → Ctrl+V (путь уже скопирован)." : (x && x.error) || "Не получилось открыть настройки Защитника — Пуск → «Безопасность Windows»."; };
$("#dw-upd-go").onclick = () => { dwSet("upd", "run", "проверяю…"); core.call("update_check").then(u => { DW.upd = u; dwRender(); }).catch(e => toast(e.message)); };
$("#dw-upd-open").onclick = () => $('nav button[data-p="about"]').click();
async function dwQr() {
  try { const c = await core.call("phone_config"); $("#dw-qr").innerHTML = qrSvg(c.apk); } catch (e) { $("#dwc-phone").style.display = "none"; }
}

/* ---------- Dewiar Облако по ключу ----------
   Карточка в «Мозге» и значок заряда в меню (#nav-cloud); данные — cloud_status и событие cloud. */
const turnsWord = (n) => { const a = n % 10, b = n % 100; return a === 1 && b !== 11 ? "ответ" : a >= 2 && a <= 4 && (b < 12 || b > 14) ? "ответа" : "ответов"; };
function cloudFill(c) {
  const card = $("#cloud-card"), chip = $("#nav-cloud");
  if (!c || !c.connected) { card.style.display = "none"; chip.style.display = "none"; DW.cloud = c || null; dkAccFill(); return; }
  const pct = Math.max(0, Math.min(100, c.percent ?? 0)), err = c.error && c.percent === undefined;
  card.style.display = ""; chip.style.display = "";
  card.className = "cloudc" + (c.empty ? " empty" : c.low ? " low" : ""); chip.className = "cchip" + (c.empty ? " empty" : c.low ? " low" : "");
  const bal = c.balance_text || (c.balance != null ? String(c.balance).replace(".", ",") + " тал." : "");
  $("#cc-sub").textContent = (c.label ? c.label + " · " : "") + (c.site ? "счёт dewiar.pro" : c.account ? "по аккаунту dewiar.pro" : "ключ …" + (c.tail || "")) + (c.active ? " · отвечает облако" : "");
  $("#cc-pct").textContent = err ? "—" : c.site ? bal : pct + "%";
  $("#cc-fill").style.width = (err ? 0 : Math.max(pct, c.empty ? 0 : 2)) + "%";
  $("#cc-turns").textContent = err ? c.error
    : c.site ? (c.frozen ? "Доступ к ИИ на сайте приостановлен — напишите администратору." : c.empty ? "На счёте dewiar.pro закончились ИИ-талеры — пополните в личном кабинете."
      : `Общий счёт с сайтом dewiar.pro: на нём ${bal}` + (c.turns ? ` — примерно на ${c.turns.toLocaleString("ru-RU")} ${turnsWord(c.turns)}` : ""))
    : c.frozen ? "Ключ приостановлен — напишите администратору." : c.empty ? "Заряд закончился — пополните, и ассистент снова будет отвечать."
    : `Хватит примерно на ${c.turns.toLocaleString("ru-RU")} ${turnsWord(c.turns)}` + (c.low ? " — скоро понадобится пополнить" : "");
  if (c.error && !err) $("#cc-turns").textContent += ` · сейчас не обновилось: ${c.error}`;   // показано последнее известное — честно говорим
  topupText(c.topup || "");
  $("#cc-use").style.display = c.active ? "none" : "";
  // по аккаунту ключа нет — «Убрать ключ» только у своего ключа dw-
  $("#cc-off").style.display = c.account || c.site ? "none" : "";
  DW.cloud = Object.assign({}, DW.cloud, c); dkAccFill();
  $("i b", chip).style.width = (err ? 0 : pct) + "%"; $("em", chip).textContent = err ? "?" : c.site ? bal : pct + "%";
  chip.title = c.site ? `ИИ-баланс — ваш счёт на dewiar.pro: ${bal}. Нажмите — подробности и пополнение`
    : `ИИ-баланс: заряд моделей Dewiar ${pct}%` + (c.turns ? `, примерно на ${c.turns} ${turnsWord(c.turns)}` : "") + ". Нажмите — подробности и пополнение";
  $("#cc-top").textContent = c.pending ? `Пополнить · заявка на проверке` : "Пополнить";
  // расход и список моделей — отдельные запросы к сайту: при открытом «Мозге» не чаще раза в 15 с
  if ($("#p-brain").classList.contains("cur") && Date.now() - (cloudFill._t || 0) > 15000) { cloudFill._t = Date.now(); ccUsage(); ccOpts(); }
}
core.on("cloud", cloudFill);
$("#nav-cloud").onclick = () => $('nav button[data-p="brain"]').click();
$("#cc-top").onclick = () => { const t = $("#cc-pay"), open = t.style.display === "none"; t.style.display = open ? "" : "none"; if (open) cpLoad(); };
/* пополнение: сумма, комментарий, снимок оплаты → заявка администратору; снимок — data-URL, не больше 6 МБ */
let cpImage = "";
const RQ = { new: "на проверке", done: "зачислено", rejected: "отклонено" };
function cpList(reqs) {
  $("#cp-list").innerHTML = (reqs || []).map(r => `<div class="rqi ${r.status}"><span>${new Date(r.ts * 1000).toLocaleString("ru-RU", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}
    ${r.amount ? " · " + r.amount + " тал." : ""}${r.reply ? " · «" + escH(r.reply) + "»" : ""}</span><b>${RQ[r.status] || r.status}${r.status === "done" ? " +" + r.credited : ""}</b></div>`).join("");
}
async function cpLoad() { try { const r = await core.call("cloud_topup"); topupText(r.text || ""); cpList(r.requests); } catch (e) { $("#cc-topup").textContent = e.message; } }
/* Как пополнить (текст администратора): выделяется и копируется, ссылки открываются в браузере (отзыв 11.10: «нельзя
   выделить, ссылка на донаты не нажимается»). pywebview по умолчанию запрещает выделение — здесь оно включено (CSS). */
function topupText(t) {
  const el = $("#cc-topup");
  el.innerHTML = escH(t).replace(/(https?:\/\/[^\s<>"]+[^\s<>".,;:!?)»])/g, '<a href="#" data-ext="$1">$1</a>');
  $$("a[data-ext]", el).forEach(a => a.onclick = (e) => { e.preventDefault(); openExt(a.dataset.ext); });
}
function cpSet(file) {
  if (!file || !/^image\//.test(file.type)) return;
  if (file.size > 6 * 1024 * 1024) { toast("Снимок больше 6 МБ — сохраните его поменьше"); return; }
  const fr = new FileReader(); fr.onload = () => { cpImage = fr.result; $("#cp-img").src = cpImage; $("#cp-shot").classList.add("has"); $("#cp-shot-t").textContent = "Снимок приложен — нажмите, чтобы заменить"; };
  fr.readAsDataURL(file);
}
$("#cp-shot").onclick = () => $("#cp-file").click();
$("#cp-file").onchange = (e) => { cpSet(e.target.files[0]); e.target.value = ""; };
$("#cp-shot").ondragover = (e) => e.preventDefault();
$("#cp-shot").ondrop = (e) => { e.preventDefault(); cpSet(e.dataTransfer.files[0]); };
document.addEventListener("paste", (e) => {
  if ($("#cc-pay").style.display === "none") return;
  const it = [...(e.clipboardData || {}).items || []].find(x => x.type && x.type.startsWith("image/")); if (it) { cpSet(it.getAsFile()); e.preventDefault(); }
});
$("#cp-send").onclick = async (ev) => {
  const r = $("#cp-res"), amount = $("#cp-amount").value.trim().replace(",", "."), note = $("#cp-note").value.trim();
  if (!cpImage && !amount) { r.className = "res bad"; r.textContent = "Укажите сумму или приложите снимок оплаты"; return; }
  ev.target.disabled = true; r.className = "res"; r.textContent = "отправляю…";
  try {
    const x = await core.call("cloud_topup_send", { amount: +amount || 0, note, image: cpImage });
    r.className = "res ok"; r.textContent = "Заявка отправлена — после проверки заряд пополнится сам."; cpList(x.requests);
    cpImage = ""; $("#cp-img").removeAttribute("src"); $("#cp-shot").classList.remove("has"); $("#cp-shot-t").textContent = "Приложите снимок оплаты — нажмите сюда или вставьте Ctrl+V";
    $("#cp-amount").value = ""; $("#cp-note").value = "";
  } catch (e) { r.className = "res bad"; r.textContent = e.message; }
  ev.target.disabled = false;
};
/* расход за 2 недели — столбики (ответов в день), без денег */
async function ccUsage() {
  try {
    const u = await core.call("cloud_usage"), days = u.days || [], mx = Math.max(1, ...days.map(d => d.answers));
    if (!days.length) { $("#cc-usage").innerHTML = ""; return; }
    const wd = (d) => ["вс", "пн", "вт", "ср", "чт", "пт", "сб"][new Date(d + "T12:00").getDay()];
    $("#cc-usage").innerHTML = `<div class="uh"><span>Расход за две недели</span><span>${u.answers} ${turnsWord(u.answers)}</span></div>
      <div class="ub">${days.map(d => `<i class="${d.answers ? "on" : ""}" style="height:${Math.max(6, d.answers / mx * 100)}%" title="${d.date}: ${d.answers} ${turnsWord(d.answers)}${d.minutes ? ", " + d.minutes + " мин речи" : ""}, ${d.percent}% заряда"></i>`).join("")}</div>
      <div class="ud">${days.map(d => `<span>${wd(d.date)}</span>`).join("")}</div>${ccParts(u.parts)}`;
  } catch (e) { $("#cc-usage").innerHTML = ""; }
}
/* на что ушёл заряд (№145, 20.10: «подключил свои мозги, а баланс Dewiar всё равно тает» — это речь и голос Dewiar) */
function ccParts(p) {
  if (!p || !(p.chat + p.stt + p.tts)) return "";
  const own = !((S.llm.profiles || {})[S.llm.active] || {}).cloud, sttC = S.stt.engine === "remote" && !!(S.stt.remote || {}).cloud,
    ttsC = S.tts.engine === "remote" && !!(S.tts.remote || {}).cloud;
  const bits = [["ответы модели", p.chat], ["распознавание речи", p.stt], ["голос Dewiar", p.tts]].filter(x => x[1] > 0).map(x => `${x[0]} — ${x[1]} %`);
  const why = own && (sttC || ttsC) ? `<p class="hint" style="margin:6px 0 0">Отвечает ваша модель — это бесплатно. С заряда сейчас ${[sttC && "распознавание речи (\u00abСлух\u00bb)", ttsC && "голос Dewiar (\u00abГолос\u00bb)"].filter(Boolean).join(" и ")} — их можно переключить на этот компьютер.</p>` : "";
  return `<div class="uparts">На что ушёл заряд: ${bits.join(", ")}.</div>${why}`;
}
/* модель облака, запасной мозг, распознавание в облаке */
async function ccOpts() {
  const profs = S.llm.profiles || {};
  $("#cc-fb").innerHTML = `<option value="">Никто — скажет, что облако недоступно</option>` +
    Object.entries(profs).filter(([k, p]) => !p.cloud).map(([k, p]) => `<option value="${k}">${escH(p.name || k)}</option>`).join("");
  $("#cc-fb").value = S.llm.fallback || "";
  $("#cc-stt").checked = S.stt.engine === "remote" && !!(S.stt.remote || {}).cloud;
  try {
    const m = await core.call("cloud_models"), list = m.data || [];
    $("#cc-stt-w").style.display = m.stt ? "" : "none";
    $("#cc-model-w").style.display = list.length > 1 ? "" : "none";
    const cur = (profs["dewiar-cloud"] || {}).model;
    $("#cc-model").innerHTML = list.map(x => `<option value="${escH(x.id)}">${escH(x.title || x.id)}${x.note ? " — " + escH(x.note) : ""}${x.factor > 1 ? ` (расход ×${x.factor})` : ""}${x.vision ? " · видит картинки" : ""}</option>`).join("");
    if (cur) $("#cc-model").value = cur;
  } catch (e) { }
}
$("#cc-model").onchange = () => core.call("cloud_model", { id: $("#cc-model").value }).then(() => toast("Модель облака: " + $("#cc-model").selectedOptions[0].textContent)).catch(e => toast(e.message));
$("#cc-fb").onchange = () => core.call("cloud_fallback", { id: $("#cc-fb").value }).then(() => toast($("#cc-fb").value ? "Запасной мозг выбран" : "Без запасного мозга")).catch(e => toast(e.message));
$("#cc-stt").onchange = (e) => core.call("cloud_stt", { on: e.target.checked }).then(() => toast(e.target.checked ? "Речь распознаёт облако" : "Речь распознаёт этот компьютер")).catch(x => { toast(x.message); e.target.checked = !e.target.checked; });
$("#cc-ref").onclick = () => core.call("cloud_status", { refresh: true }).then(c => { cloudFill(c);       // «Обновить» — заметно, что сейчас на счёте
  toast(c.error ? "Не обновилось: " + c.error : "Обновлено: " + (c.site ? (c.balance_text || c.balance + " тал.") + " на счёте dewiar.pro" : "заряд " + (c.percent ?? 0) + "%")); }).catch(e => toast(e.message));
$("#cc-off").onclick = async () => { if (await ask("Убрать ключ Dewiar Облака с этого компьютера? Баланс на сервере сохранится — ключ можно вставить снова.")) core.call("cloud_forget").then(c => { cloudFill(c); renderProfiles(); }).catch(e => toast(e.message)); };
// «Пусть отвечает облако»: переподключение сохранённым ключом снова делает профиль облака активным
// своим ключом dw-… или входом аккаунтом — ядро знает, чем (cloud_connect use); профиль облака снова активный
async function cloudUse() { const r = await core.call("cloud_connect", { use: true }); DW.cloud = r; cloudFill(r); renderProfiles(); if ($("#p-dw").classList.contains("cur")) dwRender(); return r; }
$("#cc-use").onclick = async () => { try { await cloudUse(); toast("Отвечают модели Dewiar"); } catch (e) { toast(e.message); } };
/* «Подключить ещё устройство» (0.56): всё про устройства — в разделе «Устройства» (код и QR там же) */
const dvGo = (code) => { const b = document.querySelector('nav button[data-p="devices"]'); if (b) b.click(); if (code) setTimeout(() => { const g = $("#dv-give-go"); if (g && !g.disabled) g.click(); }, 600); };
$("#cc-pair").onclick = () => dvGo(true);
$("#dw-devs").onclick = () => dvGo(false);
/* «Попробовать без регистрации»: заявка — ключ придёт сам (ядро спрашивает раз в минуту, _join_loop) */
function joinFill() {
  const j = (S && S.cloud && S.cloud.join) || {}, a = DW.acc || {}, box = $("#dk-join"); if (!box) return;
  box.style.display = a.logged_in || (DW.cloud && DW.cloud.connected) ? "none" : "";
  if (j.id) $("#jn-res").innerHTML = `Заявка №${escH(String(j.id))} ждёт проверки — ключ придёт сюда сам. <a href="#" id="jn-check">Проверить</a> · <a href="#" id="jn-forget">забыть</a>`, $("#jn-res").className = "res ok";
  const ck = $("#jn-check"), fg = $("#jn-forget");
  if (ck) ck.onclick = async (e) => { e.preventDefault(); try { const d = await core.call("join_check"); toast(d.text || "Пока ждёт проверки"); } catch (x) { toast(x.message); } };
  if (fg) fg.onclick = async (e) => { e.preventDefault(); await core.call("join_forget"); S.cloud.join = {}; $("#jn-res").textContent = ""; };
}
$("#jn-go").onclick = async (ev) => {
  const r = $("#jn-res"); ev.target.disabled = true; r.className = "res"; r.textContent = "отправляю…";
  try { const d = await core.call("join_send", { name: $("#jn-name").value, contact: $("#jn-contact").value, note: $("#jn-note").value });
    r.className = "res ok"; r.textContent = d.text || "Заявка отправлена — ключ придёт сам.";
    if (d.status === "ok") toast("Dewiar подключён"); }
  catch (e) { r.className = "res bad"; r.textContent = e.message; ev.target.disabled = false; }
};
/* «Мозг» → «Модели Dewiar»: вошли аккаунтом — одна кнопка, ключ не нужен; не вошли — войти (раздел Dewiar.pro) */
function dkAccFill() {
  const a = DW.acc || {}, c = DW.cloud || {}, box = $("#dk-acc"); if (!box) return;
  joinFill();
  const on = c.connected && c.active && (c.account || c.site);
  box.className = "dk-acc" + (on ? " ok" : "");
  if (a.logged_in) {
    box.innerHTML = `<div>Вы вошли в аккаунт dewiar.pro как <b>${escH(a.user && a.user.login || a.login || "")}</b> — ключ не нужен.<br>`
      + (on ? "Сейчас отвечают модели Dewiar по вашему аккаунту." : "Модели Dewiar подключаются по этому входу одной кнопкой.") + `<span class="res" id="dk-acc-res"></span></div>`
      + (on ? "" : `<button class="btn primary" id="dk-acc-go">Думать моделями Dewiar</button>`);
    if (!on) $("#dk-acc-go").onclick = async (ev) => {
      const r = $("#dk-acc-res"); ev.target.disabled = true; r.className = "res"; r.textContent = "подключаю…";
      try { const c2 = await cloudUse(); r.className = "res ok"; r.textContent = "Готово."; await wizardCheck(c2.profile); dkAccFill(); }
      catch (e) { r.className = "res bad"; r.textContent = "Не получилось: " + e.message; ev.target.disabled = false; }
    };
  } else {
    box.innerHTML = `<div>Есть аккаунт на <b>dewiar.pro</b>? Войдите — модели подключатся сами, ключ не нужен.</div><button class="btn primary" id="dk-acc-in">Войти в аккаунт</button>`;
    $("#dk-acc-in").onclick = () => { $('nav button[data-p="dw"]').click(); setTimeout(() => { const f = $("#dw-login"); if (f) { f.scrollIntoView({ behavior: "smooth", block: "center" }); f.focus(); } }, 200); };
  }
  $("#dk-or").innerHTML = a.logged_in ? "Ключ от администратора (строка, которая начинается с <b>dw-</b>) нужен, только если вам выдали отдельный заряд:"
    : "Или ключ от администратора — строка, которая начинается с <b>dw-</b>:";
}
$("#dk-go").onclick = async (ev) => {
  const key = $("#dk-key").value.trim(), r = $("#dk-res");
  if (!key) { r.className = "res bad"; r.textContent = "Вставьте ключ (начинается с dw-) или код из 6 цифр с другого устройства"; return; }
  ev.target.disabled = true; r.className = "res"; r.textContent = "проверяю ключ…";
  let c = null;
  try { c = await core.call("cloud_connect", { key, url: $("#dk-url").value.trim() }); }
  catch (e) {
    r.className = "res bad"; r.textContent = "Не получилось: " + e.message;
    // №364 (27.10): «ввёл код — „не получилось, нет связи с ядром“». Связь со студией оборвалась посреди подключения —
    // но само подключение могло пройти: ждём ядро и спрашиваем, чем кончилось, а не пугаем «не получилось».
    if (/нет связи с ядром/.test(e.message)) {
      r.className = "res"; r.textContent = "связь с ядром прервалась — проверяю, подключилось ли…";
      for (let i = 0; i < 25 && !c; i++) {
        await new Promise(ok => setTimeout(ok, 1000));
        try { const s = await core.call("cloud_status"); if (s && s.connected) c = s; else if (s) break; } catch (x) { /* ядро ещё не вернулось */ }
      }
      if (!c) { r.className = "res bad"; r.textContent = "Связь с ядром прервалась, подключение не прошло. Нажмите «Подключить» ещё раз"
        + (/^\d[\d\s-]{4,8}\d$/.test(key) ? " — а если код уже не подходит, возьмите новый на том устройстве («Устройства» → «Подключить ещё устройство»)." : "."); }
    }
  }
  if (c) {
    $("#dk-key").value = ""; r.className = "res ok";
    r.textContent = `Подключено${c.label ? ": " + c.label : ""}${c.tail ? " · ключ …" + c.tail : ""}. Заряд ${c.percent ?? "—"}%.`;
    // подключение уже удалось — сбой перерисовки не выдаём за «не получилось» (24.10: так и было), а пишем в журнал
    try { cloudFill(c); renderProfiles(); await wizardCheck(c.profile); }
    catch (e) { console.error(e); window.__jsErr.push("после подключения: " + e.message); core.call("js_errors", { errors: window.__jsErr.splice(0) }).catch(() => {}); }
  }
  ev.target.disabled = false;
};
$("#dk-key").onkeydown = (e) => { if (e.key === "Enter") $("#dk-go").click(); };

/* ---------- свой сервер: адрес и порт ----------
   probe_server сам определяет, что отвечает по адресу (протокол, base_url, список моделей); профиль создаётся
   с disable_thinking, как пресет vLLM: модели с «размышлениями» (Qwen3 и подобные) иначе долго молчат перед ответом. */
let svFound = null;
$("#sv-go").onclick = async (ev) => {
  const r = $("#sv-res"); $("#sv-found").style.display = "none"; r.className = "res"; r.textContent = "ищу сервер…"; ev.target.disabled = true;
  try {
    svFound = await core.call("probe_server", { address: $("#sv-host").value, port: $("#sv-port").value });
    $("#sv-what").textContent = `Нашёл: ${svFound.server}`; r.textContent = "";
    $("#sv-model").innerHTML = ""; svFound.models.forEach(m => { const o = document.createElement("option"); o.value = o.textContent = m; $("#sv-model").appendChild(o); });
    $("#sv-model").value = svFound.model; $("#sv-found").style.display = "";
  } catch (e) { r.className = "res bad"; r.textContent = e.message; }
  ev.target.disabled = false;
};
$("#sv-host").onkeydown = $("#sv-port").onkeydown = (e) => { if (e.key === "Enter") $("#sv-go").click(); };
$("#sv-use").onclick = async () => {
  const id = uid(), host = $("#sv-host").value.trim().replace(/^https?:\/\//, "").replace(/[:/].*$/, "");
  S.llm.profiles[id] = { name: `Сервер ${host} — ${$("#sv-model").value}`, kind: svFound.kind, base_url: svFound.base_url,
                         api_key: "", model: $("#sv-model").value, disable_thinking: true };
  await save({ llm: { profiles: S.llm.profiles, active: id } });
  renderProfiles(); $("#sv-found").style.display = "none";
  $("#sv-res").textContent = "";
  await wizardCheck(id);
};

let S_presets = {}, S_voices = {}, S_fx = [];
core.on("hello", d => {
  S = d.settings; personas = d.personas; active = d.persona; S_presets = d.presets; S_voices = d.piper_voices; S_fx = d.voice_fx || [];
  $("#conn").classList.add("ok"); $("#conn span").textContent = "ядро на связи";
  $("#presets").innerHTML = ""; Object.entries(S_presets).forEach(([k, p]) => { const b = document.createElement("button"); b.className = "chip"; b.textContent = "+ " + p.name; b.onclick = () => addProfile(k); $("#presets").appendChild(b); });
  renderPersonas(); renderProfiles(); refreshStatic(); renderStatus(d.status); fillNamePick();
  renderCurrent();
  // раздел, открытый до связи с ядром (по #адресу или кликом), получает свои данные только теперь — кликаем снова
  const curNav = $("nav button.cur");
  if (curNav && ["skills", "hands", "sound", "about", "folder", "voice", "tasks", "me", "memory", "reminders", "calendar", "safety", "close"].includes(curNav.dataset.p)) curNav.click();
  renderUpdate(d.update);
  renderAccount(d.account);
  mlFill(d.mail);
  tgFill(d.telegram); mxFill(d.max);
  DW.acc = d.account; DW.tg = d.telegram; DW.mx = d.max; DW.upd = d.update;
  core.call("device").then(x => { DW.dev = x; dwRender(); }).catch(() => {});
  obFill(d.obsidian);
  core.call("cal_list").then(csFill).catch(() => {});
  core.call("home_get").then(shFill).catch(() => {});
  core.call("ha_get").then(haFill).catch(() => {});
  phFill();
  core.call("cloud_status").then(cloudFill).catch(() => {});
  if (d.account && d.account.logged_in) core.call("account_check").then(renderAccount).catch(() => {});
  loadVosk();
  const q = new URLSearchParams(location.search);
  // перенос настроек: ждущий в ядре импорт, файл (?import=) или адрес (?address=) из ссылки; нет ни модели, ни
  // #раздела — сразу в «Мозг», без модели ассистент не отвечает
  if (d.pending_import) showPreview(d.pending_import);
  else if (q.get("import")) preview({ path: q.get("import") });
  else if (/^dewiar:\/\/close/.test(q.get("address") || "")) {       // ссылка-приглашение в «Близкие» (браузер → dewiar://close?t=…)
    $('nav button[data-p="close"]').click(); $("#cl-link").value = q.get("address"); $(".cl-add").open = true; setTimeout(clAccept, 600); }
  else if (/^dewiar:\/\/ref/.test(q.get("address") || "")) {         // приглашение друга (dewiar://ref?c=КОД)
    $('nav button[data-p="dw"]').click(); setTimeout(() => { $("#dw-ref-use").open = true; $("#dw-ref-code").value = (/[?&]c=([A-Za-z0-9]+)/.exec(q.get("address")) || [])[1] || ""; }, 1200); }
  else if (q.get("address")) { $("#c-addr").value = q.get("address"); preview({ address: q.get("address") }); }
  else if (q.get("note") && !DW.noteShown) { DW.noteShown = true; ntGoto(q.get("note")); }    // заметка из окна напоминания
  else if (!S.llm.active && !location.hash) $('nav button[data-p="brain"]').click();
  wlcBoot(d);
})
.on("offline", () => { $("#conn").classList.remove("ok"); $("#conn span").textContent = "нет связи с ядром"; })
.on("voices", () => loadVosk())
.on("persona", e => { active = e.persona; renderPersonas(); })
.on("personas", e => { personas = e.personas; renderPersonas(); fillNamePick(); })
.on("settings", e => { S = e.settings; refreshStatic(); renderCurrent(); profilesSync(); })   // GitHub #18 (24.10)
.on("mcp", e => { if ($("#p-skills").classList.contains("cur")) renderMcp(e.status); })
.on("status", e => renderStatus(e.status));
bindFields();

/* «Подключить бесплатно» из текста (data-free): регистрации на dewiar.pro нет — там вход для тех, кому выдали аккаунт
   (жалобы №88–89 и комментарии 19.10: «как пройти регистрацию? только окно входа»). Ведём в «Мозг» → плитка. */
document.addEventListener("click", (e) => {
  const a = e.target.closest && e.target.closest("[data-free]");
  if (!a) return;
  e.preventDefault();
  $('nav button[data-p="brain"]').click();
  setTimeout(() => { const t = $('#wz [data-w="dwkey"]'); if (t) { t.click(); t.scrollIntoView({ block: "center", behavior: "smooth" }); } }, 80);
});

/* «Dewiar уже есть на другом устройстве?» (№216, 23.10: компьютер и телефон — каждый со своей заявкой «Подключить
   бесплатно», два ключа — и ни заметок, ни блокнота друг у друга): не новая заявка, а код с того устройства */
if ($("#dk-have-go")) $("#dk-have-go").onclick = () => { const k = $("#dk-key"); if (k) { k.scrollIntoView({ block: "center" }); k.focus(); } };
