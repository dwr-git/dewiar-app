/* Студия Dewiar, раздел «Персонажи»: карточки личностей, галерея специалистов, редактор (имя, слова вызова, характер,
   облик или фото, голос, базы знаний сайта Dewiar).
   Команды ядра: persona_set, persona_save, persona_delete, gallery, gallery_add, rag_scope, voice_test; список личностей
   приходит в hello и событии personas (dewiar.js) и рисуется renderPersonas(). Облики — DewiarEntity (assets/entities.js);
   у каждого свой цикл анимации — перед перерисовкой старые destroy(), иначе циклы копятся.
   Файлы студии подключаются по порядку из ui/settings.html и делят одну глобальную область; при загрузке здесь создаётся
   только облик предпросмотра (pv). S_voices, S_fx (dewiar.js), vkSpeakers (brain.js), startCalib (connect.js) нужны
   лишь при открытии редактора. */
/* ---------- персонажи ---------- */
function accent(color) { document.documentElement.style.setProperty("--persona", color); }   // интерфейс — в фирменных цветах, цвет персонажа — только у его облика
/* Перерисовать карточки и логотип по personas/active; подпись «сейчас говорит …» читает curName() в soul.js */
function renderPersonas() {
  entities.forEach(e => e.destroy()); entities = [];
  const g = $("#pgrid"); g.innerHTML = "";
  // №369 (28.10, Windows 10: «нет кнопки Добавить и Создать»): одна сломавшаяся карточка (облик не нарисовался) больше
  // не обрывает отрисовку — «Создать своего» и «Готовые персонажи» появляются всегда; плюс кнопки вверху раздела
  personas.forEach(p => { try {
    const c = document.createElement("div");
    c.className = "card" + (p.id === active ? " cur" : ""); c.style.setProperty("--c", p.color); c.tabIndex = 0;
    c.innerHTML = `${p.id === active ? '<span class="tag">активен</span>' : ""}<button class="btn small edit">Изменить</button><div class="disc"><canvas></canvas></div><h3></h3>${p.role ? '<span class="role"></span>' : ""}<p></p><ul class="sk"></ul>`;
    $("h3", c).textContent = p.name; $("p", c).textContent = p.tagline || ""; if (p.role) $(".role", c).textContent = p.role;
    const own = typeof brainOf === "function" ? brainOf(p.id) : "";
    if (own) { const m = document.createElement("span"); m.className = "pbrain"; m.title = "Свой мозг персонажа";
      m.textContent = "🧠 " + brainName(((S.llm || {}).profiles || {})[own], own); $("h3", c).after(m); }
    if (ownMem().includes(p.name)) { const m = document.createElement("span"); m.className = "pbrain"; m.title = "Своя память персонажа"; m.textContent = "🗂 своя память"; $("h3", c).after(m); }
    (p.skills || []).slice(0, 4).forEach(t => { const li = document.createElement("li"); li.textContent = t; $("ul.sk", c).appendChild(li); });
    const e = new DewiarEntity($("canvas", c), { style: p.avatar_url && p.style !== "aura" ? "photo" : p.style, color: p.color, image: p.avatar_url || null, live: p.live || "", still: true });
    e.calm = !!stTight; e.set({ state: "idle", level: 0 }); entities.push(e);   // оживает при наведении — иначе десяток анимаций грузит компьютер
    c.onclick = (ev) => { if (ev.target.closest(".edit")) return openEditor(p); core.call("persona_set", { id: p.id }).catch(err => toast(err.message)); };
    c.onkeydown = (ev) => { if (ev.key === "Enter") c.click(); };
    c.onmouseenter = () => e.set({ state: "speaking", level: 0.35 }); c.onmouseleave = () => e.set({ state: "idle", level: 0 });
    g.appendChild(c);
  } catch (err) { console.warn("персонаж", p && p.id, err); } });
  const n = document.createElement("div"); n.className = "card new"; n.tabIndex = 0;
  n.innerHTML = "<div><b>+</b>Создать своего<br><span class='hint'>имя, характер, голос, фото</span></div>";
  n.onclick = () => openEditor(null); g.appendChild(n);
  loadGallery();
  const cur = personas.find(p => p.id === active);
  if (cur) { accent(cur.color); brand.configure({ style: cur.avatar_url && cur.style !== "aura" ? "photo" : cur.style, color: cur.color, image: cur.avatar_url || null }); $("#bsub").textContent = `сейчас говорит ${cur.name}`; }
}

/* Компьютеру не хватает памяти (status.tight от ядра) — все облики студии почти неподвижны */
let stTight = false;
function studioTight(on) {
  stTight = !!on;
  [brand, pv, ...entities, ...galEnts, ...styleEnts].forEach(e => { if (e) e.calm = stTight; });
}

/* готовые персонажи: шаблоны (Агент, Джарвис, Эва, Кодер) и специалисты */
let galEnts = [];
async function loadGallery() {
  let items = [];
  const g = $("#ggrid");
  try { items = await core.call("gallery"); } catch (e) {
    g.innerHTML = `<p class="hint">Готовые персонажи не загрузились: ${escH(e.message)}. <button class="btn small" id="gal-retry">Ещё раз</button></p>`;
    $("#gal-retry").onclick = loadGallery; return;
  }
  galEnts.forEach(e => e.destroy()); galEnts = [];
  g.innerHTML = "";
  items.forEach(p => { try {
    const c = document.createElement("div"); c.className = "card gal" + (p.installed ? " have" : ""); c.style.setProperty("--c", p.color);
    c.innerHTML = `<div class="disc"><canvas></canvas></div><h3></h3><span class="role"></span><p></p><ul class="sk"></ul><button class="btn gbtn"></button>`;
    $("h3", c).textContent = p.name; $(".role", c).textContent = p.role; $("p", c).textContent = p.tagline;
    (p.skills || []).forEach(t => { const li = document.createElement("li"); li.textContent = t; $("ul.sk", c).appendChild(li); });
    const b = $(".gbtn", c); b.textContent = p.installed ? "В команде ✓" : "+ Добавить"; b.className = "btn gbtn" + (p.installed ? "" : " primary");
    b.onclick = async () => { if (p.installed) { core.call("persona_set", { id: p.id }).catch(e => toast(e.message)); return; }
      b.disabled = true; try { await core.call("gallery_add", { id: p.id }); toast(`${p.name} в команде — позовите: «${p.name}, …»`); } catch (e) { toast(e.message); b.disabled = false; } };
    const e = new DewiarEntity($("canvas", c), { style: p.avatar_url ? "photo" : p.style, color: p.color, image: p.avatar_url || null, live: p.live || "", still: true }); e.calm = !!stTight; e.set({ state: "idle", level: 0 }); galEnts.push(e);
    c.onmouseenter = () => e.set({ state: "speaking", level: 0.35 }); c.onmouseleave = () => e.set({ state: "idle", level: 0 });
    g.appendChild(c);
  } catch (err) { console.warn("готовый персонаж", p && p.id, err); } });
}
if ($("#pr-new")) {
  $("#pr-new").onclick = () => openEditor(null);
  $("#pr-gal").onclick = () => { const h = $("#ggrid"); if (h) h.previousElementSibling.previousElementSibling.scrollIntoView({ behavior: "smooth", block: "start" }); };
}

/* редактор */
let ed = null, pv = new DewiarEntity($("#pv"), { style: "nexus", color: "#8A9BFF" }), styleEnts = [];
function openEditor(p) {
  ed = p ? JSON.parse(JSON.stringify(p)) : { name: "", gender: "female", wake: [], tagline: "", character: "", style: "particles", color: COLORS[Math.floor(Math.random() * COLORS.length)], voice: { piper: "ru_RU-irina-medium", length_scale: 1, remote: "" } };
  ed.avatar_data = null;
  $("#dtitle").textContent = p ? p.name : "Новый персонаж";
  $("#e-name").value = ed.name; $("#e-gender").value = ed.gender || "neutral";
  $("#e-wake").value = (ed.wake || []).join(", "); $("#e-tag").value = ed.tagline || ""; $("#e-char").value = ed.character || "";
  $("#e-piper").innerHTML = Object.entries(S_voices).map(([k, v]) => `<option value="${k}">${v}</option>`).join("");
  // ползунок темпа: вправо — быстрее, а length_scale у Piper — длительность (меньше — быстрее), поэтому 2 − x
  $("#e-piper").value = ed.voice.piper; $("#e-len").value = 2 - (ed.voice.length_scale || 1); $("#e-remote").value = ed.voice.remote || "";
  $("#e-fx").innerHTML = S_fx.map(f => `<option value="${f.id}">${f.name} — ${f.description}</option>`).join(""); $("#e-fx").value = ed.voice.fx || "clear";
  $("#e-vosk").innerHTML = `<option value="auto">Автоматически по полу</option>` + vkSpeakers.map(v => `<option value="${v.id}">Голос ${v.id + 1} — ${v.gender === "male" ? "мужской" : "женский"}</option>`).join("") + `<option value="piper">Всегда Piper (как раньше)</option>`;
  $("#e-vosk").value = ed.voice.prefer === "piper" ? "piper" : (Number.isInteger(ed.voice.vosk) ? String(ed.voice.vosk) : "auto");
  voiceHint();
  $("#e-del").textContent = p && p.builtin ? "Сбросить к заводскому" : "Удалить"; $("#e-del").style.display = p ? "" : "none";
  $("#e-res").textContent = "";
  ed.knowledge = ed.knowledge || []; renderKb(false); renderBrain(); renderMem();
  renderStyles(); renderColors(); updatePreview();
  $("#drawer").classList.add("open"); $("#drawer").scrollTop = 0; $("#e-name").focus({ preventScroll: true });
}
/* Свой мозг у персонажа (27.10, №346 и YouTube: «разным персонажам — разных ИИ: один на GPT, второй на Gemini, третий
   на Claude»): чипы — «Как у всех» и все модели из «Мозга»; выбор сохраняется сразу (llm.persona[id]). */
function brainName(prof, id) {
  if (!prof) return "";
  if (prof.cloud) return prof.title || "Модели Dewiar";
  return prof.name || prof.model || id;
}
function brainOf(pid) {
  const own = ((S.llm || {}).persona || {})[pid] || "", profs = (S.llm || {}).profiles || {};
  return own && profs[own] ? own : "";
}
function renderBrain() {
  const box = $("#e-brain"); if (!box) return;
  const profs = (S.llm || {}).profiles || {}, act = (S.llm || {}).active || "", cur = ed && ed.id ? brainOf(ed.id) : "";
  if (!ed || !ed.id) { box.innerHTML = `<p class="hint" style="margin:0">Сначала сохраните персонажа — потом можно выбрать ему модель.</p>`; return; }
  const ids = Object.keys(profs);
  box.innerHTML = `<button role="radio" data-b="" class="bp${cur ? "" : " on"}" aria-checked="${!cur}"><b>Как у всех</b><small>${escH(brainName(profs[act], act) || "общий мозг не выбран")}</small></button>`
    + ids.map(id => `<button role="radio" data-b="${escH(id)}" class="bp${cur === id ? " on" : ""}" aria-checked="${cur === id}"><b>${escH(brainName(profs[id], id))}</b><small>${escH(profs[id].cloud ? "облако Dewiar" : (profs[id].model || "") + (profs[id].base_url ? " · " + profs[id].base_url.replace(/^https?:\/\//, "").split("/")[0] : ""))}</small></button>`).join("")
    + `<button class="bp add" id="e-brain-add"><b>＋ Другая модель</b><small>добавить в «Мозге»: GPT, Claude, Gemini, своя</small></button>`;
  $$("#e-brain [data-b]").forEach(b => b.onclick = async () => {
    const id = b.dataset.b;
    await save({ llm: { persona: { [ed.id]: id } } }, true);
    S.llm.persona = Object.assign({}, S.llm.persona || {}, { [ed.id]: id }); renderBrain(); renderPersonas();
    toast(id ? `${ed.name} думает моделью «${brainName(profs[id], id)}»` : `${ed.name} думает общим мозгом`);
  });
  $("#e-brain-add").onclick = () => { closeEditor(); const b = $('nav button[data-p="brain"]'); if (b) b.click(); };
}
/* Своя память у персонажа (0.56; письмо 28.10: «разные персонажи со своей памятью… пока это разные морды лица у одного»):
   «Общая» — одна «Обо мне» на всех; «Своя» — факты только его («Память/Персонажи/<имя>.md»), синхронизируется. */
const ownMem = () => ((S && S.persona_memory) || {}).own || [];
function renderMem() {
  const box = $("#e-mem"); if (!box) return;
  if (!ed || !ed.id) { box.innerHTML = `<p class="hint" style="margin:0">Сначала сохраните персонажа — потом можно дать ему свою память.</p>`; return; }
  const own = ownMem().includes(ed.name);
  box.innerHTML = `<button role="radio" data-m="" class="bp${own ? "" : " on"}" aria-checked="${!own}"><b>Общая</b><small>помнит то же, что и другие персонажи</small></button>`
    + `<button role="radio" data-m="1" class="bp${own ? " on" : ""}" aria-checked="${own}"><b>Своя</b><small>помнит только то, что рассказали ему</small></button>`;
  $$("#e-mem [data-m]").forEach(b => b.onclick = async () => {
    const on = !!b.dataset.m;
    try { const r = await core.call("persona_memory", { name: ed.name, own: on }); S.persona_memory = Object.assign({}, S.persona_memory || {}, { own: r.own }); }
    catch (e) { toast(e.message); return; }
    renderMem(); renderPersonas();
    toast(on ? `${ed.name} теперь помнит своё — смотреть: «Обо мне» → вкладка «${ed.name}»` : `${ed.name} снова помнит общее`);
  });
}
function closeEditor() { $("#drawer").classList.remove("open"); styleEnts.forEach(e => e.destroy()); styleEnts = []; ed = null; }
function updatePreview() {
  const img = ed.avatar_data || (ed.style === "photo" ? ed.avatar_url : null);
  pv.configure({ style: img && ed.style !== "aura" ? "photo" : ed.style, color: ed.color, image: img || null }); pv.set({ state: "listening", level: 0.2 });
  $$("#e-styles canvas").forEach((cv, i) => styleEnts[i] && styleEnts[i].configure({ color: ed.color }));
}
function renderStyles() {
  styleEnts.forEach(e => e.destroy()); styleEnts = [];
  $("#e-styles").innerHTML = "";
  Object.entries(STYLE_NAMES).forEach(([k, name]) => {
    const b = document.createElement("button"); b.className = ed.style === k && !ed.avatar_data ? "on" : "";
    b.innerHTML = "<canvas></canvas>" + name; $("#e-styles").appendChild(b);
    const e = new DewiarEntity($("canvas", b), { style: k, color: ed.color, ring: false, still: true }); styleEnts.push(e);
    b.onclick = () => { ed.style = k; ed.avatar_data = null; ed.avatar_url = ""; ed.avatar = ""; renderStyles(); updatePreview(); };
  });
}
function renderColors() {
  const w = $("#e-colors"); w.innerHTML = "";
  COLORS.forEach(c => { const b = document.createElement("button"); b.style.background = c; b.title = c; b.className = c.toLowerCase() === (ed.color || "").toLowerCase() ? "on" : ""; b.onclick = () => { ed.color = c; renderColors(); updatePreview(); }; w.appendChild(b); });
  const inp = document.createElement("input"); inp.type = "color"; inp.value = ed.color; inp.title = "Свой цвет";
  inp.oninput = () => { ed.color = inp.value; updatePreview(); }; w.appendChild(inp);
}
$("#e-photo").onchange = (ev) => {
  const f = ev.target.files[0]; if (!f) return;
  // анимация (GIF) — как есть, без пересжатия: холст оставил бы один кадр (письмо пользователя 23.10: «пропала анимация»).
  // Хранится в папке настроек (personas/<id>.avatar.gif) — обновления программы её не трогают
  if (/gif/.test(f.type)) {
    if (f.size > 5.5 * 1024 * 1024) { toast("Анимация больше 5,5 МБ — уменьшите её", 4000); ev.target.value = ""; return; }
    const r = new FileReader(); r.onload = () => { ed.avatar_data = r.result; if (ed.style !== "aura") ed.style = "photo"; renderStyles(); updatePreview(); };
    r.readAsDataURL(f); ev.target.value = ""; return;
  }
  // фото уходит в ядро data-URL одним сообщением (ядро принимает до 6 МБ) — поэтому уменьшаем до 768 px здесь
  const img = new Image(); img.onload = () => {          // до 768 px, с плавным уменьшением; PNG — с прозрачностью
    const s = Math.min(1, 768 / Math.max(img.width, img.height));
    let src = img, w = img.width, h = img.height;
    while (w / 2 >= img.width * s && w > 4) {           // уменьшаем ступенями по половине — без «лесенки» и мыла
      const half = document.createElement("canvas"); half.width = Math.round(w / 2); half.height = Math.round(h / 2);
      const hc = half.getContext("2d"); hc.imageSmoothingQuality = "high"; hc.drawImage(src, 0, 0, half.width, half.height);
      src = half; w = half.width; h = half.height;
    }
    const cv = document.createElement("canvas"); cv.width = Math.round(img.width * s); cv.height = Math.round(img.height * s);
    const cx = cv.getContext("2d"); cx.imageSmoothingQuality = "high"; cx.drawImage(src, 0, 0, cv.width, cv.height);
    const alpha = /png|webp/.test(f.type);
    const webp = alpha ? cv.toDataURL("image/webp", 0.92) : "";     // прозрачность — WebP (в 5–10 раз меньше PNG), нет — PNG
    ed.avatar_data = alpha ? (webp.startsWith("data:image/webp") ? webp : cv.toDataURL("image/png")) : cv.toDataURL("image/jpeg", 0.93); if (ed.style !== "aura") ed.style = "photo"; renderStyles(); updatePreview(); URL.revokeObjectURL(img.src);
  };
  img.src = URL.createObjectURL(f); ev.target.value = "";
};
$("#e-nophoto").onclick = () => { ed.avatar_data = null; ed.avatar = ""; ed.avatar_url = ""; if (ed.style === "photo") ed.style = "particles"; renderStyles(); updatePreview(); };
/* ---------- персонаж: базы знаний сайта ----------
   Папки пользователя и публичная библиотека на dewiar.pro (нужен вход в аккаунт); ed.knowledge — [{kind, id, label, lib?}],
   не больше шести — столько же оставляет ядро (core/personas.py). Список баз запрашивается один раз за сеанс (kbBases). */
let kbBases = null;
function kbKey(b) { return b.kind === "folder" ? `folder:${b.path}` : `${b.kind}:${b.id}`; }
function renderKb(open) {
  const box = $("#e-kb"); if (!box || !ed) return;
  const sel = ed.knowledge || [];
  box.innerHTML = `<div class="kbsel"></div><div class="actions" style="margin:0"><button class="btn small" id="kb-folder">Папка на компьютере…</button>`
    + `<button class="btn small" id="kb-pick">${open ? "Свернуть" : sel.some(b => b.kind !== "folder") ? "Изменить базы сайта" : "Базы с сайта…"}</button></div>`;
  const chips = $(".kbsel", box);
  if (!sel.length) chips.innerHTML = '<span class="hint" style="background:none;padding:0">Не подключено — персонаж отвечает по своим знаниям.</span>';
  sel.forEach((b, i) => { const c = document.createElement("span"); c.textContent = (b.kind === "folder" ? "📁 " : "") + b.label; if (b.path) c.title = b.path;
    const x = document.createElement("button"); x.textContent = "×"; x.title = "Отключить";
    x.onclick = () => { ed.knowledge.splice(i, 1); renderKb(open); }; c.appendChild(x); chips.appendChild(c); });
  $("#kb-pick").onclick = () => renderKb(!open);
  // YouTube 27.10: «нет возможности добавить знания из локальной папки, только с сервера»
  $("#kb-folder").onclick = async () => {
    const a = window.api && window.api(); let p = "";
    if (a && a.pick_folder) p = await a.pick_folder(); else p = await askText("Полный путь к папке с документами:") || "";
    if (!p) return;
    ed.knowledge = ed.knowledge || [];
    if (ed.knowledge.some(x => x.kind === "folder" && x.path === p)) return toast("Эта папка уже подключена");
    if (ed.knowledge.length >= 6) return toast("Не больше шести баз у одного персонажа");
    ed.knowledge.push({ kind: "folder", path: p, label: p.replace(/[\\/]+$/, "").split(/[\\/]/).pop() || p });
    renderKb(open); toast("Сохраните персонажа — папка прочитается в фоне, и он начнёт отвечать по ней", 4000);
  };
  if (!open) return;
  const list = document.createElement("div"); list.className = "kblist"; list.innerHTML = '<p class="hint" style="padding:8px">Загружаю базы с сайта…</p>'; box.appendChild(list);
  (kbBases ? Promise.resolve(kbBases) : core.call("rag_scope", { force: true })).then(r => {
    kbBases = r; list.innerHTML = "";
    if (!r.bases.length) { list.innerHTML = '<p class="hint" style="padding:8px">На сайте пока нет ни папок, ни публичной библиотеки.</p>'; return; }
    const have = new Set(sel.map(kbKey)); let g = null;
    r.bases.forEach(b => {
      if (b.group !== g) { g = b.group; const h = document.createElement("div"); h.className = "kbg"; h.textContent = g === "Мои папки" ? g : "Библиотека · " + g; list.appendChild(h); }
      const l = document.createElement("label"); l.className = "kbi";
      l.innerHTML = `<input type="checkbox"><span></span><em></em>`;
      $("span", l).textContent = b.whole ? "Вся библиотека" : b.label; $("em", l).textContent = `${b.docs} док.`;
      const cb = $("input", l); cb.checked = have.has(kbKey(b));
      cb.onchange = () => { ed.knowledge = (ed.knowledge || []).filter(x => kbKey(x) !== kbKey(b));
        if (cb.checked) { if (ed.knowledge.length >= 6) { cb.checked = false; return toast("Не больше шести баз у одного персонажа"); }
          ed.knowledge.push({ kind: b.kind, id: b.id, label: b.whole ? b.label : b.label, ...(b.lib ? { lib: b.lib } : {}) }); }
        renderKb(true); };
      list.appendChild(l);
    });
  }).catch(e => { list.innerHTML = ""; const p = document.createElement("p"); p.className = "hint"; p.style.padding = "8px";
    p.textContent = /вход|аккаунт/i.test(e.message) ? "Нужен вход в аккаунт Dewiar: «Dewiar.pro» → «Аккаунт dewiar.pro». После входа здесь появятся ваши папки и публичная библиотека." : e.message; list.appendChild(p); });
}
/* Какой голос на самом деле звучит (YouTube 27.10: «ставил голоса Денис, Руслан и Дмитрий — они одинаковые»): при
   голосах Vosk TTS выбор Piper ничего не менял — Piper звучал, только если Vosk недоступен. Теперь выбрали голос Piper —
   этот персонаж говорит им (Vosk для него — «Всегда Piper»), а строка под полями говорит, что слышно сейчас. */
function voiceHint() {
  const el = $("#e-vhint"); if (!el) return;
  const eng = (S.tts || {}).engine, pv = $("#e-piper").selectedOptions[0], pn = pv ? pv.textContent.replace(/\s*\(.*\)$/, "") : "Piper";
  el.textContent = eng === "remote" ? "Сейчас звучит голос сервера (поле «Голос на сервере»); Piper — запасной, если сервер молчит."
    : eng === "elevenlabs" ? "Сейчас звучит ElevenLabs; Piper — запасной."
    : eng === "off" ? "Голос выключен — студия → «Голос»."
    : eng === "vosk" && $("#e-vosk").value !== "piper" ? `Сейчас звучит Vosk TTS (${$("#e-vosk").selectedOptions[0] ? $("#e-vosk").selectedOptions[0].textContent.toLowerCase() : "по полу"}). Выберите голос Piper — персонаж заговорит им.`
    : `Сейчас звучит Piper — «${pn}».`;
}
$("#e-piper").onchange = () => {
  if ((S.tts || {}).engine === "vosk" && $("#e-vosk").value !== "piper") $("#e-vosk").value = "piper";
  voiceHint();
};
$("#e-vosk").onchange = voiceHint;
$("#e-cancel").onclick = closeEditor;
$("#e-save").onclick = async () => {
  const name = $("#e-name").value.trim(); if (!name) { $("#e-res").className = "res bad"; $("#e-res").textContent = "Введите имя"; return; }
  const wake = $("#e-wake").value.split(",").map(s => s.trim().toLowerCase()).filter(Boolean);
  const body = { id: ed.id, name, gender: $("#e-gender").value, wake: wake.length ? wake : [name.toLowerCase()], tagline: $("#e-tag").value.trim(),
    character: $("#e-char").value.trim() || `Тебя зовут ${name}. Ты дружелюбный голосовой помощник.`, style: ed.style, color: ed.color,
    voice: Object.assign({ piper: $("#e-piper").value, length_scale: +(2 - $("#e-len").value).toFixed(2), remote: $("#e-remote").value.trim(), fx: $("#e-fx").value },
      $("#e-vosk").value === "piper" ? { prefer: "piper" } : /^\d+$/.test($("#e-vosk").value) ? { vosk: +$("#e-vosk").value } : {}) };
  body.knowledge = ed.knowledge || [];
  if (ed.avatar_data) body.avatar_data = ed.avatar_data; else if (ed.style !== "photo") body.avatar = "";
  try {
    const r = await core.call("persona_save", { persona: body });
    ed.id = r.id;
    // слов вызова нет в словаре Vosk — ядро всё равно их узнает, но через GigaAM; говорим об этом, редактор не закрываем
    if (r.missing && r.missing.length) { $("#e-res").className = "res bad"; $("#e-res").textContent = `Сохранено. Слова «${r.missing.join(", ")}» нет в словаре быстрого распознавателя — имя будет узнавать точная модель GigaAM, это на долю секунды дольше.`; }
    else { toast("Персонаж сохранён"); closeEditor(); }
  } catch (e) { $("#e-res").className = "res bad"; $("#e-res").textContent = e.message; }
};
$("#e-teach").onclick = () => { if (ed && ed.id) { const id = ed.id; closeEditor(); startCalib(id); } else toast("Сначала сохраните персонажа"); };
$("#e-listen").onclick = () => {
  if (!(ed && ed.id)) return toast("Сначала сохраните персонажа");
  const v = $("#e-vosk").value, voice = Object.assign(v === "piper" ? { prefer: "piper" } : /^\d+$/.test(v) ? { vosk: +v, prefer: "" } : { prefer: "" },
    { piper: $("#e-piper").value, length_scale: +(2 - $("#e-len").value).toFixed(2) });   // слушаем выбранное, а не сохранённое
  core.call("voice_test", { persona: ed.id, fx: $("#e-fx").value, voice }).catch(e => toast(e.message));
};
$("#e-del").onclick = async () => {
  if (!ed || !ed.id) return;
  // заводского персонажа ядро не удаляет, а сбрасывает к исходному — текст вопроса соответствует кнопке
  if (!await ask(ed.builtin ? `Сбросить «${ed.name}» к заводским настройкам? Ваши правки пропадут.` : `Удалить персонажа «${ed.name}»? Это нельзя отменить.`)) return;
  try { await core.call("persona_delete", { id: ed.id }); closeEditor(); } catch (e) { toast(e.message); }
};
document.addEventListener("keydown", e => { if (e.key === "Escape") { if (ed) closeEditor(); $("#skd").classList.remove("open"); } });
/* закрыть панель персонажа: крестиком, щелчком мимо (по странице, не по карточкам) и переходом в другой раздел (№184) */
$("#e-x").onclick = () => closeEditor();
document.addEventListener("mousedown", (e) => { if (ed && e.target.closest("main") && !e.target.closest(".drawer, .dwq, .card, button")) closeEditor(); });
$$("nav button[data-p]").forEach(b => b.addEventListener("click", () => { if (ed) closeEditor(); $("#skd").classList.remove("open"); }));
