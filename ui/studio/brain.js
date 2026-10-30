/* Студия Dewiar: «Мозг» (профили моделей), простые поля настроек data-k, «Послушать» голос, звук и состояние,
   «Руки» (инструменты), «Напоминания» и готовые дела по расписанию.
   Поля с data-k="a.b.c" сохраняются сами (bindFields) и заполняются из S (refreshStatic — её зовёт save() после
   каждого сохранения). Команды ядра: llm_test, llm_models, discover, voice_test, vosk_voices, devices, tools,
   reminders, reminder_add/parse/update/cancel, job_add, job_run, alarm_test; события state (ход «Послушать»), reminders.
   Файлы студии подключаются по порядку из ui/settings.html и делят одну глобальную область; при загрузке здесь только
   вешаются обработчики. S_presets, S_fx (dewiar.js), wizardCheck (connect.js) нужны позже; RI отсюда берёт links.js. */
/* ---------- мозг ----------
   llm.profiles в patch ядро заменяет целиком (settings._merge: удалённый профиль не должен вернуться), поэтому
   любая правка профиля шлёт весь словарь S.llm.profiles. */
let openProf = null, profSig = "";
function uid() { return "p" + Math.random().toString(36).slice(2, 8); }
function renderProfiles() {
  const box = $("#profiles"); box.innerHTML = "";
  const profs = S.llm.profiles || {};
  profSig = JSON.stringify([S.llm.active, profs]);
  if (!Object.keys(profs).length) box.innerHTML = '<p class="hint" style="margin-bottom:10px">Пока ни одной — выберите выше, где будет думать ассистент.</p>';
  Object.entries(profs).forEach(([id, p]) => {
    const el = document.createElement("div"); el.className = "prof" + (S.llm.active === id ? " on" : "") + (openProf === id ? " open" : ""); el.dataset.id = id;
    el.innerHTML = `<div class="head"><input type="radio" name="act" ${S.llm.active === id ? "checked" : ""} title="Сделать активной"><div class="t"><b></b><small></small></div><span class="res"></span><button class="btn small">Настроить</button></div>
    <div class="body"><div class="row" style="margin-top:12px">
      <label class="f">Название<input type="text" data-f="name"></label>
      <label class="f">Протокол<select data-f="kind"><option value="openai">OpenAI-совместимый</option><option value="ollama">Ollama</option><option value="anthropic">Anthropic</option></select></label>
      <label class="f">Адрес сервера<input type="url" data-f="base_url"><span class="hint">Заполняется само при подключении; менять обычно не нужно.</span></label>
      <label class="f">API-ключ<input type="password" data-f="api_key" placeholder="для локальных не нужен"></label>
      <label class="f">Модель<input type="text" data-f="model" list="ml-${id}" placeholder="пусто — первая с сервера"><datalist id="ml-${id}"></datalist><span class="hint">Весь список — кнопка «Список моделей».</span></label>
      <div class="mpick" id="mp-${id}" hidden></div>
      ${p.cloud ? "" : `<div class="f econ"><span>Экономный режим</span><div class="econ-row"><input type="text" data-f="economy" list="ml-${id}" placeholder="выключен">
        <button class="btn small" data-a="econ">Подобрать</button></div><span class="hint">Недорогая модель того же сервиса для простых вопросов — «привет», «что такое…». Поручения, длинное и сложное — основной модели; не ответит — ответит основная.</span></div>`}
      <label class="f">Максимум токенов в ответе<input type="number" data-f="max_tokens" placeholder="600"></label>
      <label class="f">Температура<input type="number" step="0.1" min="0" max="2" data-f="temperature" placeholder="0.7"></label>
      <label class="f" style="justify-content:end"><span><input type="checkbox" data-f="disable_thinking"> отключать «размышления» (Qwen3 и подобные в vLLM)</span></label>
    </div><div class="actions"><button class="btn primary" data-a="test">Проверить</button><button class="btn" data-a="models">Список моделей</button><span style="flex:1"></span><button class="btn danger" data-a="del">Удалить</button></div></div>`;
    $("b", el).textContent = p.name || "Без названия";
    if (p.economy && !p.cloud) $("b", el).insertAdjacentHTML("afterend", `<em class="econ-tag" title="Простые вопросы — ${escH(p.economy)}">экономно</em>`);
    $("small", el).textContent = p.cloud ? `${S.cloud && S.cloud.account ? "по аккаунту dewiar.pro" : "по ключу …" + (p.api_key || "").slice(-4)} · ${p.title || p.model || ""}` : `${p.base_url || ""}${p.model ? " · " + p.model : ""}`;
    $$("[data-f]", el).forEach(inp => {
      const k = inp.dataset.f; if (inp.type === "checkbox") inp.checked = !!p[k]; else inp.value = p[k] ?? "";
      inp.onchange = () => { let v = inp.type === "checkbox" ? inp.checked : inp.value; if (inp.type === "number") v = v === "" ? null : +v; S.llm.profiles[id][k] = v; save({ llm: { profiles: S.llm.profiles } }, true).then(renderProfiles); };
    });
    $(".head input", el).onclick = (ev) => { ev.stopPropagation(); save({ llm: { active: id } }).then(renderProfiles); };
    $(".head .btn", el).onclick = (ev) => { ev.stopPropagation(); openProf = openProf === id ? null : id; renderProfiles(); };
    const res = $(".head .res", el);
    $('[data-a="test"]', el).onclick = async (ev) => {
      ev.target.disabled = true; res.className = "res"; res.textContent = "проверяю…";
      try { const r = await core.call("llm_test", { profile: S.llm.profiles[id] });
            if (r.ok) { res.className = "res ok"; res.textContent = `работает · модель «${r.model}»${r.api === "ollama" ? " (API Ollama)" : ""} · ответ за ${(r.total_ms / 1000).toFixed(1)} с: «${r.reply}»`;
                        if (r.ctx_note) { res.className = "res warn"; res.textContent += " · " + r.ctx_note; } }
            else { res.className = "res bad"; res.textContent = r.error || "модель не ответила"; } }
      catch (e) { res.className = "res bad"; res.textContent = e.message; }
      ev.target.disabled = false;
    };
    if ($('[data-a="econ"]', el)) $('[data-a="econ"]', el).onclick = async (ev) => {
      ev.target.disabled = true; res.className = "res"; res.textContent = "ищу недорогую модель…";
      try { const r = await core.call("llm_economy_suggest", { profile: S.llm.profiles[id] });
            if (r.model) { S.llm.profiles[id].economy = r.model; await save({ llm: { profiles: S.llm.profiles } }, true); renderProfiles(); toast("Экономный режим: простое — " + r.model); }
            else { res.className = "res bad"; res.textContent = r.error ? "список моделей не пришёл: " + r.error : "недорогой модели в списке не нашлось — впишите её сами"; } }
      catch (e) { res.className = "res bad"; res.textContent = e.message; }
      ev.target.disabled = false;
    };
    $('[data-a="models"]', el).onclick = async () => {
      // весь список — кнопками (№139, 20.10: подсказка поля показывает только модели, похожие на уже вписанную, — «не весь
      // список локальных моделей»); нажали — модель выбрана и сохранена
      try { const ms = await core.call("llm_models", { profile: S.llm.profiles[id] }); $(`#ml-${id}`, el).innerHTML = ms.map(m => `<option value="${escH(m)}">`).join("");
            const box = $(`#mp-${id}`, el), cur = S.llm.profiles[id].model || "";
            box.innerHTML = `<b>Модели на сервере · ${ms.length}</b>` + ms.map(m => `<button class="chip${m === cur ? " on" : ""}${/embed|rerank/i.test(m) ? " side" : ""}" data-m="${escH(m)}"${/embed|rerank/i.test(m) ? ' title="Для поиска по смыслу — разговаривать не умеет"' : ""}>${escH(m)}</button>`).join("");
            box.hidden = !ms.length; if (openProf !== id) { openProf = id; el.classList.add("open"); }
            $$("button", box).forEach(b => b.onclick = () => { S.llm.profiles[id].model = b.dataset.m; save({ llm: { profiles: S.llm.profiles } }, true).then(renderProfiles); toast("Модель: " + b.dataset.m); });
            res.className = "res ok"; res.textContent = ms.length ? `моделей: ${ms.length} — нажмите нужную` : "сервер не вернул ни одной модели";
            // №258 (25.10): в Ollama только nomic-embed-text, а qwen3 скачан в LM Studio — «выбора нет»; объясняем, где взять
            if (!ms.some(m => !/embed|rerank|ocr|whisper|tts|asr|speech|stt|clip|bge|e5-|guard|moderat/i.test(m))) {
              res.className = "res bad"; res.textContent = "Модели для разговора здесь нет…";
              core.call("llm_no_chat", { profile: S.llm.profiles[id], models: ms }).then(t => { res.textContent = t; }).catch(() => {});
            } }
      catch (e) { res.className = "res bad"; res.textContent = e.message; }
    };
    $('[data-a="del"]', el).onclick = () => { delete S.llm.profiles[id]; const patch = { llm: { profiles: S.llm.profiles } }; if (S.llm.active === id) patch.llm.active = Object.keys(S.llm.profiles)[0] || ""; save(patch).then(renderProfiles); };
    box.appendChild(el);
  });
  ownFbRender();
}
/* «Если своя модель не отвечает — отвечать через Dewiar» (29.10): виден, когда главная — своя модель (этот компьютер или
   сервер в своей сети); включили, а бесплатного мозга нет — ядро подключит его запасным (своя модель остаётся главной). */
function ownFbRender() {
  const w = $("#own-fb-w"); if (!w || !S || !S.llm) return;
  const p = (S.llm.profiles || {})[S.llm.active] || {};
  const host = String(p.base_url || "").toLowerCase().replace(/^\w+:\/\//, "").split("/")[0].split(":")[0];
  const own = !p.cloud && !!host && (/^(localhost|127\.|::1|0\.0\.0\.0)/.test(host) || /^(10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.)/.test(host) || host.endsWith(".local") || !host.includes("."));
  w.style.display = own ? "" : "none";
  $("#own-fb").checked = !!S.llm.own_fallback;
}
if ($("#own-fb")) $("#own-fb").onchange = async (ev) => {
  const on = ev.target.checked, r = $("#own-fb-res"); ev.target.disabled = true; r.className = "res"; r.textContent = on ? "подключаю…" : "";
  try { const d = await core.call("own_fallback", { on }); S.llm.own_fallback = d.on;
        r.className = "res " + (d.error ? "bad" : "ok");
        r.textContent = d.error || (!on ? "" : d.ready ? "готово: если своя модель не ответит, ответит Dewiar" : "заявка отправлена — подключится сам, как только сайт одобрит"); }
  catch (e) { r.className = "res bad"; r.textContent = e.message; ev.target.checked = !on; }
  ev.target.disabled = false;
};

/* GitHub #18 (24.10): событие settings (ядро само сменило модель — engine_brain) не перерисовывало «Мозг»: радиокнопка
   оставалась у прежней модели. Ничего не поменялось — не трогаем (список моделей и итог «Проверить» остаются); человек
   печатает в поле профиля — перерисовка сбила бы ввод: тогда только отметка. */
function profilesSync() {
  const box = $("#profiles"); if (!box || !S.llm || JSON.stringify([S.llm.active, S.llm.profiles || {}]) === profSig) return;
  const a = document.activeElement, ids = Object.keys((S.llm && S.llm.profiles) || {});
  const typing = a && box.contains(a) && a.matches("input,select,textarea") && a.type !== "radio";
  if (typing && ids.join() === $$(".prof", box).map(e => e.dataset.id).join()) {
    $$(".prof", box).forEach(e => { const on = e.dataset.id === S.llm.active; e.classList.toggle("on", on); $(".head input", e).checked = on; });
  } else renderProfiles();
}
function addProfile(preset, extra = {}) {
  if (!(S_presets[preset] || extra.base_url)) { toast("Студия ещё не на связи с ядром — попробуйте через секунду"); return Promise.resolve(); }
  const id = uid(); const p = Object.assign({ api_key: "", model: "" }, S_presets[preset], extra); delete p.models; delete p.preset;
  S.llm.profiles[id] = p; openProf = id;
  const patch = { llm: { profiles: S.llm.profiles } }; if (!S.llm.active) patch.llm.active = id;
  return save(patch).then(renderProfiles);
}
$("#discover").onclick = async () => {
  const r = $("#discres"); r.className = "res"; r.textContent = "ищу… (если стоит LM Studio — включаю его сервер, до минуты)";
  try {
    const found = await core.call("discover");
    if (!found.length) { r.className = "res bad"; r.textContent = "Не нашёл: Ollama и LM Studio не запущены. Как поставить — ниже."; $("#lc-how").open = true; return; }
    const known = Object.values(S.llm.profiles).map(p => p.base_url);
    let added = 0;
    for (const f of found) if (!known.includes(f.base_url)) { await addProfile(f.preset, { base_url: f.base_url, model: f.models[0] || "" }); added++; }
    const lm = found.find(f => f.started);
    r.className = "res ok"; r.textContent = `Найдено: ${found.map(f => f.name).join(", ")}${added ? ` — добавлено ${added}` : " — уже в списке"}.`
      + (lm ? ` Сервер LM Studio был выключен — включила${lm.models.length ? "" : "; загрузите в LM Studio модель"}.` : "");
    const loc = Object.entries(S.llm.profiles).find(([, p]) => p.base_url === found[0].base_url);
    if (loc) { if (S.llm.active !== loc[0]) { await save({ llm: { active: loc[0] } }); renderProfiles(); } await wizardCheck(loc[0]); }
  } catch (e) { r.className = "res bad"; r.textContent = e.message; }
};

/* ---------- простые поля ---------- */
/* Текстовые поля сохраняются через 600 мс после последней буквы, остальные — почти сразу; ползунок — без «Сохранено» */
function bindFields() {
  $$("[data-k]").forEach(inp => {
    const k = inp.dataset.k;
    inp.onchange = inp.oninput = () => {
      let v = inp.type === "checkbox" ? inp.checked : inp.value;
      if (inp.type === "number" || inp.type === "range") v = +v;
      if (inp.type === "range") $("#speedv").textContent = `×${v}`;
      clearTimeout(saveT[k]); saveT[k] = setTimeout(() => save(patchOf(k, v), inp.type === "range"), inp.type === "text" || inp.type === "url" || inp.type === "password" ? 600 : 50);
    };
  });
  $$("[data-eng]").forEach(o => $("input", o).onchange = () => {
    if (o.dataset.eng === "dewiar") return dwStt(true);             // «Сервер Dewiar» — облако или аккаунт (links.js)
    if (dwSttOn()) return dwStt(false, o.dataset.eng);              // уходим с сервера Dewiar — сразу на выбранное
    save({ stt: { engine: o.dataset.eng } });
  });
  $$("[data-tts]").forEach(o => $("input", o).onchange = () => {
    if (o.dataset.tts === "dewiar") return dwVoice(true);           // «Голос Dewiar» — облако или аккаунт (links.js)
    if (dwVoiceOn()) return dwVoice(false, o.dataset.tts);           // уходим с голоса Dewiar — сразу на выбранный
    save({ tts: { engine: o.dataset.tts } });
  });
  // «Язык Лиры» (28.10, владелец: «думал, будет выбор языка в настройках, русский по умолчанию, английский — в списке»):
  // список вместо переключателя «Понимать английскую речь»; English целиком (с меню) — когда переведём программу
  if ($("#lang-sel")) $("#lang-sel").onchange = () => save({ stt: { english: $("#lang-sel").value === "ru_en" } });
  // extra — тоже заменяется целиком (settings._merge), так что лишние ключи из поля убираются
  $("#ttsextra").onchange = () => { try { save({ tts: { remote: { extra: JSON.parse($("#ttsextra").value || "{}") } } }); } catch (e) { toast("Это не JSON"); } };
}
function refreshStatic() {
  if (window.studioSkin) studioSkin(get("ui.skin"));     // студия — в стиле виджета (studio/theme.js)
  featuresApply();
  if (window.DewiarZoom) { DewiarZoom.apply(get("ui")); if (window.zoomSync) zoomSync(); }   // масштаб и текст (look.js)
  const wf = $("#wf-box"); if (wf) wf.style.display = (+get("ui.widget_fail2") || 0) >= 2 ? "" : "none";
  $$("[data-k]").forEach(inp => {
    if (document.activeElement === inp) return;           // не перетираем поле, которое сейчас правят
    const v = get(inp.dataset.k); if (inp.type === "checkbox") inp.checked = !!v; else if (v !== undefined && v !== null) inp.value = v;
  });
  const ls = $("#lang-sel"); if (ls && document.activeElement !== ls) ls.value = get("stt.english") ? "ru_en" : "ru";
  $("#speedv").textContent = `×${S.tts.speed}`;
  const pl = $("#pause-learn"), px = +get("audio.end_silence_extra") || 0;          // подстройка паузы: сколько уже добавлено
  if (pl) {
    const pxx = Math.min(600, px);                        // выше +600 ядро не ждёт (№226), даже если выучено раньше
    pl.textContent = "Если вы продолжаете говорить сразу после того, как ассистент решил, что фраза закончена, — он начнёт ждать дольше; со временем вернётся к обычной паузе."
      + (pxx > 0 && get("audio.end_silence_auto") !== false ? ` Сейчас жду ${(+get("audio.end_silence_ms") || 650) + pxx} мс (+${pxx} под вашу речь). ` : "");
    if (pxx > 0 && get("audio.end_silence_auto") !== false) {   // №226: «добавка сама не уменьшается» — вернуть сразу
      const r = document.createElement("a"); r.href = "#"; r.id = "pause-reset"; r.textContent = "Вернуть обычную";
      r.onclick = (e) => { e.preventDefault(); e.stopPropagation(); save({ audio: { end_silence_extra: 0 } }); };
      pl.appendChild(r);
    }
  }
  // «Сервер Dewiar» — отдельный вариант: адрес и ключ подставлены из аккаунта, поля «своего сервера» человеку не показываем
  // (отзыв 17.10: «зачем пользователю эти данные? Он должен их вносить руками?»)
  const dws = typeof dwSttOn === "function" && dwSttOn(), eng = dws ? "dewiar" : S.stt.engine;
  $$("[data-eng]").forEach(o => { const on = eng === o.dataset.eng; o.classList.toggle("on", on); $("input", o).checked = on; });
  $$('#p-ears .sub').forEach(s => s.style.display = eng === s.dataset.for ? "" : "none");
  if (typeof renderSrvSttOpt === "function") renderSrvSttOpt();
  const dw = typeof dwVoiceOn === "function" && dwVoiceOn();
  $$("[data-tts]").forEach(o => { const on = dw ? o.dataset.tts === "dewiar" : S.tts.engine === o.dataset.tts; o.classList.toggle("on", on); $("input", o).checked = on; });
  $$('#p-voice .sub').forEach(s => s.style.display = !dw && S.tts.engine === s.dataset.for ? "" : "none");
  if (document.activeElement !== $("#ttsextra")) $("#ttsextra").value = JSON.stringify(S.tts.remote.extra || {});
  renderFx();
}
/* «Послушать»: кнопка сразу показывает, что происходит — готовлю → звучит → снова можно нажать.
   Ход берём из событий state ядра (speaking → idle); не пришли за 45 с — кнопку всё равно отпускаем. */
let previewing = null;
function previewVoice(b, args) {
  if (previewing) previewDone();
  previewing = b; b.classList.add("pv-wait"); b.classList.remove("pv-play");
  let tag = b.querySelector(".pv"); if (!tag) { tag = document.createElement("i"); tag.className = "pv"; b.appendChild(tag); }
  tag.textContent = " · готовлю…";
  clearTimeout(b._pvT); b._pvT = setTimeout(() => { if (previewing === b) previewDone(); }, 45000);
  core.call("voice_test", args).catch(e => { previewDone(); toast(e.message); });
}
function previewDone() {
  const b = previewing; if (!b) return; previewing = null;
  b.classList.remove("pv-wait", "pv-play"); const tag = b.querySelector(".pv"); if (tag) tag.remove();
}
core.on("state", e => {
  if (!previewing) return;
  if (e.state === "speaking") { previewing.classList.remove("pv-wait"); previewing.classList.add("pv-play"); const tag = previewing.querySelector(".pv"); if (tag) tag.textContent = " · звучит"; }
  else if (e.state === "idle" && previewing.classList.contains("pv-play")) previewDone();
});
let vkSpeakers = [];
async function loadVosk() {
  try {
    const r = await core.call("vosk_voices"); vkSpeakers = r.speakers || [];
    const box = $("#vk-list");
    // модель голосов Vosk скачивается один раз; пока качается — спрашиваем снова каждые 5 с
    if (!r.ready) { box.textContent = r.error ? `Не загрузились: ${r.error}. Пока говорит Piper.` : "Голоса скачиваются (один раз) — прогресс виден под виджетом. Пока говорит Piper."; if (r.loading) setTimeout(loadVosk, 5000); return; }
    box.innerHTML = `<p class="hint" style="margin-bottom:8px">Голоса модели — нажмите, чтобы послушать. Персонажам они раздаются по полу автоматически, поменять — в карточке персонажа.</p><div class="chips">` +
      vkSpeakers.map(v => `<button class="chip" data-vk="${v.id}">▶ Голос ${v.id + 1} · ${v.gender === "male" ? "мужской" : "женский"}</button>`).join("") + `</div>`;
    $$("#vk-list [data-vk]").forEach(b => b.onclick = () => previewVoice(b, { text: "Здравствуйте! Я ваш голосовой помощник. Чем могу помочь?", voice: { vosk: +b.dataset.vk, prefer: "" } }));
  } catch (e) { $("#vk-list").textContent = e.message; }
}
function renderFx() {
  const cur = S.tts.fx || "persona";
  const items = [{ id: "persona", name: "Как у персонажа", description: "у каждого своя обработка" }].concat(S_fx);
  // ▶ у каждого варианта — видно, что его можно послушать (отзыв 11.10: «как проверить звучание, непонятно»)
  $("#fxgrid").innerHTML = items.map(f => `<button data-fx="${f.id}" class="${f.id === cur ? "on" : ""}" title="Выбрать и послушать"><b><i class="fxp"></i>${f.name}</b><span>${f.description}</span></button>`).join("");
  $$("#fxgrid button").forEach(b => b.onclick = () => {
    save({ tts: { fx: b.dataset.fx } });
    previewVoice(b, { text: "Слушаю вас. Чем могу помочь?", fx: b.dataset.fx === "persona" ? null : b.dataset.fx });
  });
}
async function loadDevices() {
  try {
    const ds = await core.call("devices");
    const fill = (sel, kind) => { sel.innerHTML = '<option value="">Системный по умолчанию</option>' + ds.filter(d => d.kind === kind).map(d => `<option value="${d.name}"></option>`).join("");
      $$("option", sel).forEach((o, i) => { if (i) o.textContent = ds.filter(d => d.kind === kind)[i - 1].description; }); sel.value = get(sel.dataset.k) || ""; };
    fill($("#devin"), "source"); fill($("#devout"), "sink");
  } catch (e) { toast(e.message); }
}
/* «Скачано на этом компьютере» (отзыв 19.10: непонятно, что скачано, а что будет качаться): models_status — строки по
   моделям, models_get — скачать заранее; ход — по status.downloads («m:<ключ>»), итог — событием models. */
let mdlData = null;
const mdlEsc = (t) => String(t == null ? "" : t).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
function mdlRender(d) {
  mdlData = d || mdlData; if (!mdlData) return;
  const dl = (lastStatus && lastStatus.downloads) || {};
  for (const g of ["ears", "voice"]) {
    const box = $("#mdl-" + g); if (!box) continue;
    box.innerHTML = mdlData.items.filter(x => x.group === g).map(x => {
      const f = dl["m:" + x.key], pct = f != null && f < 1 ? Math.round(f * 100) : x.pct;
      const st = pct != null ? `<span class="bar"><i style="width:${pct}%"></i></span><span>скачивается${pct ? " " + pct + "%" : "…"}</span>`
        : x.installed ? `<span class="ok">✓ скачана</span><span>${x.mb} МБ</span>${x.used ? `<span class="use">· используется</span>` : ""}`
        : `<span>не скачана · ~${x.mb} МБ</span><button class="btn small" data-mget="${mdlEsc(x.key)}">Скачать</button>`;
      return `<div class="mdl-row"><b>${mdlEsc(x.title)}</b><small>${mdlEsc(x.about)}</small><div class="st">${st}</div></div>`;
    }).join("");
  }
  $$("[data-mget]").forEach(b => b.onclick = () => { b.disabled = true; b.textContent = "Начинаю…";
    core.call("models_get", { key: b.dataset.mget }).then(() => setTimeout(mdlLoad, 400)).catch(e => { toast(e.message); b.disabled = false; b.textContent = "Скачать"; }); });
}
function mdlLoad() { core.call("models_status").then(mdlRender).catch(() => {}); }
core.on("models", d => mdlRender(d));
["ears", "voice"].forEach(p => { const b = $(`nav button[data-p="${p}"]`); if (b) b.addEventListener("click", mdlLoad); });
let lastStatus = {};
function renderStatus(st) {
  lastStatus = st || lastStatus; st = lastStatus;
  if (typeof studioTight === "function" && st) studioTight(!!st.tight);   // мало памяти — облики студии почти неподвижны
  const rows = [["Связь с ядром", core.connected ? "есть" : "нет"], ["Эхоподавление", st.headphones ? "не нужно — наушники" : st.aec ? "работает" : "выключено — полудуплекс"], ["Микрофон", st.input || "—"],
    ["Распознавание", `${st.stt || "—"}${st.stt_ready === false ? " (загружается, пока Vosk)" : ""}`], ["Голос", st.tts || "—"], ["Модель", st.llm || "не выбрана"], ["Сейчас", [st.note, ...Object.values(st.loading || {}).map(x => "готовлю: " + x.t.toLowerCase()
      + (x.f != null && x.f < 1 ? ` ${Math.round(x.f * 100)}%` : "…"))].filter(Boolean).join(" · ") || "всё спокойно"]];
  $("#status").innerHTML = rows.map(([a, b]) => `<dt>${a}</dt><dd></dd>`).join("");
  $$("#status dd").forEach((d, i) => d.textContent = rows[i][1]);
  $("#aecst").textContent = st.headphones ? "Не нужно: включён режим наушников." : st.aec ? "Работает: ассистент не слышит сам себя, и его можно перебить голосом." : "Сейчас не работает — пока ассистент говорит, микрофон приглушается. В наушниках включите режим ниже.";
  $("#sttstat").textContent = st.stt ? `Сейчас: ${st.stt}${st.stt_ready === false ? " — загружается, пока работает Vosk" : ""}` : "";
  if (mdlData && Object.keys(st.downloads || {}).some(k => k.startsWith("m:"))) mdlRender();   // ход скачивания — сразу в строке
}

function renderTools(list) {
  const box = $("#toollist"); box.innerHTML = "";
  list.forEach(t => {
    const el = document.createElement("div"); el.className = "tool";
    el.innerHTML = `<div><b></b>${t.risk === "confirm" ? '<span class="risk">опасное</span>' : ""}<div class="d"></div></div>
      <label class="tg" title="Включено"><input type="checkbox" ${t.enabled ? "checked" : ""}><i></i></label>
      <label class="ask"><input type="checkbox" ${t.confirm ? "checked" : ""}> спрашивать разрешение</label>
      ${t.needs ? `<div class="need"><span></span><button class="btn small" data-go="${escH(t.page || "")}">Открыть</button></div>` : ""}`;
    $("b", el).textContent = t.title; $(".d", el).textContent = t.description;
    if (t.needs) { $(".need span", el).textContent = t.needs; $(".need button", el).onclick = () => { const b = $(`nav button[data-p="${t.page}"]`); if (b) b.click(); }; }
    const [on, ask] = $$("input", el);
    // №264 (25.10): «включаю — „Сохранено“, а переключатель не включается» — служба не подключена: не делаем вид, что
    // сохранили, а показываем, чего не хватает, и подсвечиваем подсказку
    on.onchange = () => {
      if (on.checked && t.needs) { on.checked = false; save({ tools: { enabled: { [t.name]: true } } }, true);
        const n = $(".need", el); n.classList.remove("flash"); void n.offsetWidth; n.classList.add("flash"); return; }
      save({ tools: { enabled: { [t.name]: on.checked } } }).then(() => core.call("tools").then(renderTools));
    };
    ask.onchange = () => save({ tools: { confirm: { [t.name]: ask.checked } } });
    box.appendChild(el);
  });
}
/* ---------- напоминания ---------- */
const RI = { pause: '<rect x="6" y="5" width="4" height="14" rx="1"/><rect x="14" y="5" width="4" height="14" rx="1"/>',
  play: '<path d="M7 5v14l11-7z"/>', edit: '<path d="M4 20h4L19 9l-4-4L4 16v4z"/><path d="m13.5 6.5 4 4"/>',
  del: '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-12M9 7V4h6v3"/>', ok: '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
  undo: '<path d="M9 14 4 9l5-5"/><path d="M4 9h10a6 6 0 0 1 0 12h-3"/>' };
let remItems = [];
function remGroup(x) {
  if (x.repeat) return "Повторяющиеся";
  const d = new Date(x.at), t = new Date(); const day = (a) => new Date(a.getFullYear(), a.getMonth(), a.getDate()).getTime();
  const diff = Math.round((day(d) - day(t)) / 864e5);
  return diff <= 0 ? "Сегодня" : diff === 1 ? "Завтра" : "Позже";
}
function renderReminders(items) {
  remItems = items || []; renderPresets(); const box = $("#r-list"); box.innerHTML = "";
  if (!remItems.length) { box.innerHTML = '<div class="rempty">Напоминаний пока нет.<br>Скажите «Агент, напомни через 20 минут выключить духовку» — или напишите выше.</div>'; return; }
  const groups = {}; remItems.forEach(x => (groups[remGroup(x)] = groups[remGroup(x)] || []).push(x));
  ["Сегодня", "Завтра", "Позже", "Повторяющиеся"].forEach(g => {
    if (!groups[g]) return;
    const h = document.createElement("div"); h.className = "rgroup"; h.textContent = g; box.appendChild(h);
    groups[g].forEach(x => {
      const el = document.createElement("div"); el.className = "ritem" + (x.paused ? " paused" : "");
      const kind = x.kind === "job" ? (x.brief ? "утренняя сводка" : "дело по расписанию") + ({ telegram: " · в Telegram", max: " · в MAX" }[x.deliver] || " · голосом")
                   : { alarm: "будильник", timer: "таймер" }[x.kind];
      el.innerHTML = `<div class="rtime"></div><div class="rbody"><div class="rtext"></div><div class="rmeta"></div></div><div class="ract"></div>`;
      $(".rtime", el).textContent = x.at_hm; $(".rtext", el).textContent = x.text;
      const meta = $(".rmeta", el); const w = document.createElement("span"); w.textContent = x.paused ? "на паузе" : x.when; meta.appendChild(w);
      if (x.repeat_text) { const b = document.createElement("span"); b.className = "rbadge"; b.textContent = "↻ " + x.repeat_text; meta.appendChild(b); }
      if (kind) { const b = document.createElement("span"); b.className = "rbadge k"; b.textContent = kind; meta.appendChild(b); }
      if (x.att && x.note) {                          // картинки и файлы напоминания — в его заметке; нажатие открывает её
        const b = document.createElement("button"); b.className = "rbadge ratt"; b.title = "Открыть вложения";
        b.innerHTML = `<svg viewBox="0 0 24 24"><path d="m20.5 11.5-8.6 8.6a5.5 5.5 0 0 1-7.8-7.8l8.6-8.6a3.7 3.7 0 0 1 5.2 5.2l-8.6 8.6a1.8 1.8 0 0 1-2.6-2.6l8-8"/></svg>${x.att}`;
        b.onclick = () => ntGoto(x.note); meta.appendChild(b); }
      const act = $(".ract", el);
      const btn = (icon, title, fn) => { const b = document.createElement("button"); b.title = title; b.innerHTML = `<svg viewBox="0 0 24 24">${RI[icon]}</svg>`; b.onclick = fn; act.appendChild(b); };
      if (x.repeat) btn(x.paused ? "play" : "pause", x.paused ? "Возобновить" : "Пауза", () => core.call("reminder_update", { id: x.id, patch: { paused: !x.paused } }).then(loadReminders).catch(e => toast(e.message)));
      if (x.kind !== "job" && x.kind !== "alarm" && x.kind !== "timer")
        btn("ok", "Сделано", () => core.call("done_reminder", { id: x.id }).then(() => loadReminders()).catch(e => toast(e.message)));
      btn("edit", "Изменить", () => editReminder(el, x));
      btn("del", "Удалить", () => core.call("reminder_cancel", { id: x.id }).then(() => { toast("Удалено"); loadReminders(); }).catch(e => toast(e.message)));
      box.appendChild(el);
    });
  });
}
function editReminder(el, x) {
  const body = $(".rbody", el); body.innerHTML = "";
  const t = document.createElement("input"); t.value = x.text; t.placeholder = "о чём напомнить";
  const w = document.createElement("input"); w.placeholder = "когда: «завтра в 10», «каждый день в 8» — пусто, чтобы не менять"; w.style.marginTop = "6px";
  body.appendChild(t); body.appendChild(w); t.focus();
  const save = () => { const patch = { text: t.value.trim() || x.text }; if (w.value.trim()) patch.when = w.value.trim();
    core.call("reminder_update", { id: x.id, patch }).then(() => { toast("Сохранено"); loadReminders(); }).catch(e => toast(e.message)); };
  [t, w].forEach(i => i.onkeydown = (e) => { if (e.key === "Enter") save(); if (e.key === "Escape") loadReminders(); });
  const act = $(".ract", el); act.innerHTML = ""; const ok = document.createElement("button"); ok.className = "btn primary"; ok.style.width = "auto"; ok.style.padding = "0 12px"; ok.textContent = "Сохранить"; ok.onclick = save; act.appendChild(ok);
}
/* ---------- готовые дела по расписанию ---------- */
const J_DAYS = { daily: "каждый день", weekdays: "по будням", fri: "по пятницам", sun: "по воскресеньям" };
const J_PRESETS = [
  { id: "brief", title: "Утренняя сводка", desc: "Дела и встречи на сегодня, погода, вчерашние траты — коротко, за минуту.", days: "daily", time: "08:00",
    task: "Утренняя сводка", brief: true, icon: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>' },
  { id: "fx", title: "Курс валют", desc: "Доллар и евро на сегодня по нацбанку вашей страны и насколько изменились со вчера.", days: "weekdays", time: "09:00",
    task: "Курс доллара и евро на сегодня (официальный, по нацбанку моей страны) и изменение со вчера", icon: '<path d="M4 17l5-5 4 4 7-8"/><path d="M15 8h5v5"/>' },
  { id: "evening", title: "Итог дня", desc: "Что сделано, сколько потрачено, что осталось и что запланировано на завтра.", days: "daily", time: "21:00",
    task: "Итог дня: что сделано из дел на сегодня, что осталось, сколько потрачено за день и что запланировано на завтра — коротко", icon: '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>' },
  { id: "week", title: "Итоги недели", desc: "По пятницам: что сделано за неделю, траты по категориям, планы на следующую.", days: "fri", time: "18:00",
    task: "Итоги недели: что я сделал за неделю, траты за неделю по категориям и что запланировано на следующую неделю", icon: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4M8 15l2 2 4-4"/>' },
  { id: "news", title: "Главные новости", desc: "Пять главных новостей утра — по одному предложению, без воды.", days: "daily", time: "08:30",
    task: "Главные новости утра: 5 самых важных, по одному предложению каждая, с упоминанием источника", icon: '<path d="M4 5h13v14H6a2 2 0 0 1-2-2V5z"/><path d="M17 9h3v8a2 2 0 0 1-2 2M8 9h5M8 13h5M8 17h3"/>' },
  { id: "weather", title: "Погода и что надеть", desc: "Погода на день: утром, днём, вечером — и нужен ли зонт.", days: "daily", time: "07:30",
    task: "Погода на сегодня в моём городе: утром, днём и вечером, будут ли осадки, нужен ли зонт и что надеть — коротко", icon: '<path d="M7 18a4.5 4.5 0 0 1-.6-9A6 6 0 0 1 18 10a4 4 0 0 1-.5 8H7z"/>' },
];
/* Включённое дело для готовой карточки: по preset, а у созданных без него — по тексту поручения */
function jobOf(p) { return remItems.find(x => x.kind === "job" && (x.preset === p.id || (!x.preset && x.text === p.task))); }
function renderPresets() {
  const box = $("#j-pre"); if (!box) return; box.innerHTML = "";
  J_PRESETS.forEach(p => {
    const on = jobOf(p);
    const el = document.createElement("div"); el.className = "jcard" + (on ? " on" : ""); el.dataset.id = p.id;
    el.innerHTML = `<svg viewBox="0 0 24 24">${p.icon}</svg><b></b><span></span>
      <div class="jrow"><input type="text" inputmode="numeric" maxlength="5" placeholder="чч:мм" title="Время, например 8:30"><select><option value="voice">голосом</option><option value="telegram">в Telegram</option><option value="max">в MAX</option></select></div>
      <div class="jact"><button class="btn"></button><button class="jtry" title="Выполнить один раз прямо сейчас">попробовать</button></div>`;
    $("b", el).textContent = p.title; $(":scope > span", el).textContent = p.desc;
    const tm = $("input", el), dv = $("select", el), go = $(".jact .btn", el);
    tm.value = on ? on.at_hm : p.time; dv.value = on ? (on.deliver || "voice") : "voice";
    if (on) { const st = document.createElement("div"); st.className = "jstate"; st.textContent = `✓ включено · ${on.repeat_text || J_DAYS[p.days]}`; el.insertBefore(st, $(".jrow", el)); }
    go.textContent = on ? "Выключить" : "Включить"; if (!on) go.classList.add("primary");
    const save = async () => {
      try {
        const m = (tm.value.trim() || p.time).replace(/[.\-\s]/, ":").match(/^(\d{1,2})(?::(\d{2}))?$/);
        if (!m || +m[1] > 23 || +(m[2] || 0) > 59) { tm.focus(); return toast("Время — например 8:30 или 21:00"); }
        const hm = `${m[1].padStart(2, "0")}:${m[2] || "00"}`;
        // расписание ядро разбирает из фразы, как сказанное голосом: «каждый день в 08:00 делай …»
        const r = await core.call("job_add", { phrase: `${J_DAYS[p.days]} в ${hm} делай ${p.title.toLowerCase()}`, task: p.task,
          deliver: dv.value, brief: !!p.brief, preset: p.id });
        // время или способ изменили — старое дело заменяем новым; снимаем его только после удачного job_add:
        // иначе отказ ядра (например, «Telegram ещё не подключён») оставит без дела вовсе
        // 0.74: такое же дело уже есть — ядро отдаёт его же (already), и его не снимаем
        if (on && on.id !== r.id) await core.call("reminder_cancel", { id: on.id });
        toast(r.already && !on ? `«${p.title}» уже есть — второе не завожу` : `«${p.title}» — ${r.repeat_text}`); loadReminders();
      } catch (e) { toast(e.message); }
    };
    go.onclick = async () => {
      if (on) { try { await core.call("reminder_cancel", { id: on.id }); toast(`«${p.title}» выключено`); loadReminders(); } catch (e) { toast(e.message); } return; }
      save();
    };
    [tm, dv].forEach(i => i.onchange = () => { if (on) save(); });
    tm.onkeydown = (e) => { if (e.key === "Enter") on ? save() : go.click(); };
    $(".jtry", el).onclick = () => core.call("job_run", { task: p.task, brief: !!p.brief, deliver: dv.value })
      .then(r => toast({ telegram: "Выполняю — пришлю в Telegram", max: "Выполняю — пришлю в MAX" }[r.deliver] || "Выполняю — скажу голосом")).catch(e => toast(e.message));
    box.appendChild(el);
  });
}
async function loadReminders() {
  try { renderDone(await core.call("done")); } catch (e) { $("#d-list").textContent = e.message; }
  try { renderReminders(await core.call("reminders")); } catch (e) { $("#r-list").textContent = e.message; }
}
/* ---------- дела: сделано сегодня, серия, значки и неделя (core/done.py; то же на телефоне — «Мой день» → «Дела») ---------- */
const dEsc = (t) => String(t == null ? "" : t).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const dela = (n) => n % 10 === 1 && n % 100 !== 11 ? "дело" : [2, 3, 4].includes(n % 10) && ![12, 13, 14].includes(n % 100) ? "дела" : "дел";
const dney = (n) => n % 10 === 1 && n % 100 !== 11 ? "день" : [2, 3, 4].includes(n % 10) && ![12, 13, 14].includes(n % 100) ? "дня" : "дней";
function renderDone(d) {
  if (!d) return;
  const head = $("#d-head"), max = Math.max(1, ...d.week.map(w => w.n)), WD = ["вс", "пн", "вт", "ср", "чт", "пт", "сб"];
  const chips = [];
  for (const g of ["day", "streak", "total"]) {
    const all = d.achievements.filter(a => a.group === g), next = all.find(a => !a.got);
    all.filter(a => a.got).forEach(a => chips.push(`<span class="dach on" title="${dEsc(a.what)} · получено">${a.icon} ${dEsc(a.name)}</span>`));
    if (next) chips.push(`<span class="dach" title="${dEsc(next.what)} · сейчас ${next.val} из ${next.n}">${next.icon} ${Math.min(next.val, next.n)}/${next.n}</span>`);
  }
  head.innerHTML = `<div class="dnum"><b>${d.today}</b><span>${d.today ? dela(d.today) + " сегодня" : "дел сегодня"}</span></div>`
    + `<div class="dmid"><div class="dstreak">${d.streak >= 2 ? `🔥 ${d.streak} ${dney(d.streak)} подряд` : d.today ? "Первый день серии" : d.total ? "Отметьте дело — серия продолжится" : "Сделали дело — отметьте его"}`
    + `<small>всего ${d.total} · лучший день ${d.best_day} · лучшая серия ${d.best_streak}</small></div><div class="dachs">${chips.join("")}</div></div>`
    + `<div class="dweek" aria-label="Дела за неделю">${d.week.map((w, i) => `<div title="${w.day}: ${w.n}"><i style="height:${Math.round(6 + 52 * w.n / max)}px"${i === 6 ? ' class="now"' : ""}></i><small>${WD[new Date(w.day + "T12:00").getDay()]}</small></div>`).join("")}</div>`;
  const box = $("#d-list"); box.innerHTML = "";
  if (d.items.length) { const h = document.createElement("div"); h.className = "rgroup"; h.textContent = "Сделано сегодня"; box.appendChild(h); }
  d.items.slice().reverse().forEach(x => {
    const el = document.createElement("div"); el.className = "ritem dn";
    const t = new Date(x.at);
    el.innerHTML = `<div class="dok"><svg viewBox="0 0 24 24">${RI.ok}</svg></div><div class="rbody"><div class="rtext"></div><div class="rmeta"><span></span></div></div><div class="ract"></div>`;
    $(".rtext", el).textContent = x.title;
    $(".rmeta span", el).textContent = `${String(t.getHours()).padStart(2, "0")}:${String(t.getMinutes()).padStart(2, "0")}` + (x.src && x.src !== "pc" ? " · на телефоне" : "");
    const b = document.createElement("button"); b.title = "Снять отметку"; b.innerHTML = `<svg viewBox="0 0 24 24">${RI.undo}</svg>`;
    b.onclick = () => core.call("done_undo", { id: x.id }).then(() => { toast("Отметка снята"); loadReminders(); }).catch(e => toast(e.message));
    $(".ract", el).appendChild(b); box.appendChild(el);
  });
}
function doneCelebrate(r) {
  if (!r || !r.added) return;
  const a = (r.fresh || [])[r.fresh.length - 1];
  toast(a ? `${a.icon} Новое достижение: ${a.name} — ${a.what}` : r.mile ? `🎉 ${r.mile} ${dela(r.mile)} за сегодня — так держать` : `✓ ${r.added.join(", ")} — сегодня ${r.today}`);
  if ((a || r.mile) && !matchMedia("(prefers-reduced-motion: reduce)").matches) { const h = $("#d-head"); h.classList.remove("cheer"); void h.offsetWidth; h.classList.add("cheer"); }
}
async function doneAdd() {
  const v = $("#d-phrase").value.trim(); if (!v) { $("#d-phrase").focus(); return; }
  try { await core.call("done_add", { title: v }); $("#d-phrase").value = ""; loadReminders(); } catch (e) { toast(e.message); }
}
$("#d-add").onclick = doneAdd;
$("#d-phrase").onkeydown = (e) => { if (e.key === "Enter") doneAdd(); };
// отметка любым путём — кнопкой, голосом («я позвонил в банк»), моделью — празднуем здесь один раз (отзыв 17.10: показать в видео)
core.on("done", e => { if (!$("#p-reminders").classList.contains("cur")) return; renderDone(e); if ((e.added || []).length) doneCelebrate(e); });
let rpT = null;
// пока пишут — показываем, как ядро поняло фразу (тот же разбор, что у голосовой команды)
$("#r-phrase").oninput = () => { clearTimeout(rpT); const v = $("#r-phrase").value.trim(); const el = $("#r-parse");
  if (!v) { el.textContent = ""; el.className = "rparse"; return; }
  rpT = setTimeout(() => core.call("reminder_parse", { phrase: v }).then(r => {
    if (!r) { el.className = "rparse bad"; el.textContent = "Не понял, когда напомнить — добавьте время: «в 18:00», «через час», «каждый понедельник в 10»"; return; }
    el.className = "rparse"; el.innerHTML = ""; const b = document.createElement("b"); b.textContent = r.when + (r.repeat_text ? ", " + r.repeat_text : "");
    el.append("⏰ ", b, " — " + r.text); }).catch(() => {}), 200); };
$("#r-phrase").onkeydown = (e) => { if (e.key === "Enter") $("#r-add").click(); };
$("#r-add").onclick = async () => { const v = $("#r-phrase").value.trim(); if (!v) return $("#r-phrase").focus();
  try { const r = await core.call("reminder_add", { phrase: v }); $("#r-phrase").value = ""; $("#r-parse").textContent = ""; toast(`Напомню ${r.when}`); loadReminders(); }
  catch (e) { $("#r-parse").className = "rparse bad"; $("#r-parse").textContent = e.message; } };
$("#r-listen").onclick = () => core.call("alarm_test", { sound: $("#r-sound").value }).catch(e => toast(e.message));
$("#r-try").onclick = () => core.call("reminder_add", { phrase: "через 10 секунд проверка будильника" }).then(() => { toast("Через 10 секунд прозвенит"); loadReminders(); }).catch(e => toast(e.message));
core.on("reminders", e => { if ($("#p-reminders").classList.contains("cur")) renderReminders(e.items); });

/* «Возможности» (24.10): выключенное прячется из меню — «Суфлёр» в списке разделов, «Рядом» и «Встречи» во вкладках
   «Близких». Открыта спрятанная вкладка — возвращаемся к переписке; открыт спрятанный раздел — к «Возможностям». */
/* «Возможности» (0.74; владелец 30.10: «немножко путает — включение и отключение того же суфлёра есть и на главной»).
   Было два переключателя в разных местах: здесь — «включить совсем», на главной — «показать значок». Теперь здесь оба
   сразу, тремя положениями: «Выключено» (features.X = false), «Без значка» (работает, значка на главной и раздела в меню
   нет — ui.home_apps без него), «На главной». Главная → «Настроить» меняет то же самое. */
const FT = [
  { k: "games", app: "play", name: "Досуг — игры на пару минут", sub: "Сказки, головоломки, слова и аркады. Кнопка с джойстиком у виджета или «Лира, давай поиграем»." },
  { k: "prompter", app: "prompter", name: "Суфлёр", sub: "Молчаливые подсказки на встречах и созвонах; на созвоне виджет сам предложит его включить." },
  { k: "clients", app: "clients", optin: 1, name: "Клиенты — личная CRM", sub: "Контакты, о чём договорились, следующий шаг с напоминанием. «Запиши: Иванов хочет 200 коробок». С ними — «Рассылка» и «Чат для сайта»." },
  { k: "team", app: "team", optin: 1, name: "Поручения сотрудникам", sub: "Поручения в Telegram с кнопками «Беру», «Сделано» с фото, «Перенести» с причиной; отметки в календаре." },
  { k: "family", app: "family", optin: 1, name: "Семья — общий бюджет", sub: "Траты за месяц у всей семьи, общий лимит и общие платежи. Позовут в семью — включится само." },
  { k: "near", name: "Рядом", sub: "«Близкие» → «Рядом»: на карте видно, кто из близких где, если они сами делятся местом." },
  { k: "meet", name: "Встречи", sub: "«Близкие» → «Встречи»: знакомства с людьми, которые сейчас рядом с вашим телефоном." }];
const FT_SAY = { off: "Не работает и нигде не показывается.", on: "Работает, но значка на главной и раздела в меню нет.", home: "Работает: значок — на главной, раздел — в меню." };
function ftState(f) {
  const v = (get("features") || {})[f.k], on = f.optin ? v === true : v !== false;
  if (!on) return "off";
  if (!f.app) return "home";
  return typeof hmApps === "function" && !hmApps().includes(f.app) ? "on" : "home";
}
function featuresRender() {
  const box = $("#ft-list"); if (!box) return;
  box.innerHTML = FT.map(f => {
    const st = ftState(f), opts = f.app ? [["off", "Выключено"], ["on", "Без значка"], ["home", "На главной"]] : [["off", "Выключено"], ["home", "Включено"]];
    return `<div class="ft" data-k="${f.k}"><div class="ft-t"><b>${escH(f.name)}</b><span>${escH(f.sub)}</span></div>
      <div class="ft-r"><div class="ft-seg" role="radiogroup" aria-label="${escH(f.name)}">${opts.map(([v, l]) => `<button type="button" role="radio" data-v="${v}" aria-checked="${v === st}">${l}</button>`).join("")}</div>
      <small class="ft-now">${f.app ? FT_SAY[st] : st === "off" ? FT_SAY.off : "Работает."}</small></div></div>`;
  }).join("");
  $$("#ft-list .ft-seg button").forEach(b => b.onclick = () => ftSet(FT.find(x => x.k === b.closest(".ft").dataset.k), b.dataset.v));
}
featuresRender();                                   // сразу, ещё до связи с ядром — потом перерисуется по настройкам
async function ftSet(f, st) {
  if (!f || ftState(f) === st) return;
  const patch = { features: { [f.k]: st !== "off" } };
  if (f.app && st !== "off" && typeof hmApps === "function") {
    const cur = hmApps(), list = st === "home" ? (cur.includes(f.app) ? cur : cur.concat([f.app])) : cur.filter(x => x !== f.app);
    if (list.join() !== cur.join()) patch.ui = { home_apps: list, home_known: typeof hmAll === "function" ? hmAll().map(x => x.id) : list };
  }
  await save(patch, true);
  toast(`«${f.name.split(" — ")[0]}»: ${st === "off" ? "выключено" : st === "on" ? "работает без значка" : f.app ? "на главной" : "включено"}`);
  featuresRender();
}
function featuresApply() {
  const f = get("features") || {}, on = (k) => f[k] !== false;
  const nb = $('nav button[data-p="prompter"]'); if (nb) nb.hidden = !on("prompter");
  const fb0 = $('nav button[data-p="family"]'); if (fb0) fb0.hidden = f.family !== true;   // «Семья» — по желанию (27.10)
  const tb0 = $('nav button[data-p="team"]'); if (tb0) tb0.hidden = f.team !== true;       // «Поручения» — по желанию (28.10)
  const cb0 = $('nav button[data-p="clients"]'); if (cb0) cb0.hidden = f.clients !== true;   // «Клиенты» — по желанию (28.10)
  const mb0 = $('nav button[data-p="mailing"]'); if (mb0) mb0.hidden = f.clients !== true && f.team !== true;   // «Рассылка» — рядом с ними (0.69)
  const sb0 = $('nav button[data-p="sitechat"]'); if (sb0) sb0.hidden = mb0 ? mb0.hidden : true;                // «Чат для сайта» — тоже
  for (const t of ["near", "meet"]) { const b = $(`#cl-tabs button[data-t="${t}"]`); if (b) b.hidden = !on(t); }
  const cur = $("#cl-tabs button.on");
  if (cur && cur.hidden && window.rdTab) rdTab("chat");
  if ((nb && nb.hidden && nb.classList.contains("cur")) || (fb0 && fb0.hidden && fb0.classList.contains("cur")) || (tb0 && tb0.hidden && tb0.classList.contains("cur")) || (mb0 && mb0.hidden && mb0.classList.contains("cur"))) { const fb = $('nav button[data-p="features"]'); if (fb) fb.click(); }
  if (window.hmNav) hmNav();                                     // меню — ещё и по «Главной» (home.js): скрытое там скрыто и тут
  featuresRender();
}
