/* «Облако Лиры» — маленькая вкладка-флешка рядом с «Пультом» в блокноте у виджета (владелец 17.11: «не в Пульте, а
   рядом вкладка маленькая с иконкой флешки… закидывать, читать, скачивать»). Это окно в то же облако, что «Мои файлы»
   в студии (core/drive.py: drive_status, drive_open, knowledge_add; событие "drive"), — своего хранилища у вкладки нет.
   Нажали на флешку — вместо листа: шкала места, «бросьте файл сюда», все файлы плитками; нажали на плитку — открылся. */
(() => {
  const el = (s) => document.querySelector(s);
  const esc = (t) => String(t == null ? "" : t).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  const A = () => (window.pywebview && window.pywebview.api) || null;
  const K = { pdf: "PDF", doc: "DOC", sheet: "XLS", slides: "PPT", image: "IMG", text: "TXT" };
  const EXT = /\.(pdf|docx|odt|xlsx|pptx|txt|md|csv|html?|jpe?g|png|webp)$/i;
  const mb = (b) => b >= 1048576 ? (b / 1048576).toFixed(b >= 10485760 ? 0 : 1).replace(".", ",") + " МБ" : Math.max(1, Math.round(b / 1024)) + " КБ";
  const CL = { active: false, st: null, msg: "" };

  const tab = document.createElement("button");
  tab.id = "cl-tab"; tab.className = "tab cl"; tab.type = "button"; tab.setAttribute("role", "tab"); tab.setAttribute("aria-selected", "false");
  tab.title = "Облако Лиры — ваши файлы на всех устройствах"; tab.setAttribute("aria-label", "Облако Лиры");
  // облачко со стрелкой — тем же тонким штрихом, что и остальные значки блокнота (владелец 17.11 выбрал «вариант B с
  // облачком»: цветная флешка выглядела «не органично»); открыта — цвета Лиры
  tab.innerHTML = '<svg class="cl-usb" viewBox="0 0 24 24" aria-hidden="true"><path d="M7 18.5h10a4 4 0 0 0 .6-7.95A5.5 5.5 0 0 0 7 9.6a4.5 4.5 0 0 0 0 8.9z"/>'
    + '<path d="M12 16v-5m-2.2 2.1L12 10.9l2.2 2.2"/></svg>';
  const pt = el("#pt-tab");
  el("#top").insertBefore(tab, pt ? pt.nextSibling : el("#tabs"));

  const box = document.createElement("section");
  box.id = "cloud"; box.setAttribute("aria-label", "Облако Лиры");
  box.innerHTML = `
    <div class="cl-hd"><span class="cl-ico" aria-hidden="true"><svg viewBox="0 0 48 48"><defs><linearGradient id="cl-g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#8fd3ff"/><stop offset=".55" stop-color="#8b8cf7"/><stop offset="1" stop-color="#c58cf7"/></linearGradient></defs><path d="M14.5 37h20a8.5 8.5 0 0 0 1.3-16.9A11.5 11.5 0 0 0 13.6 18 9.5 9.5 0 0 0 14.5 37z" fill="url(#cl-g)"/><path d="M24 31v-9m-4 3.6 4-4 4 4" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg></span><div><b>Облако Лиры</b><small id="cl-sub">ваши файлы — на всех ваших устройствах</small></div>
      <span class="cl-used" id="cl-used"></span></div>
    <div class="cl-bar"><i id="cl-fill"></i></div>
    <label class="cl-drop" id="cl-drop" tabindex="0"><input type="file" id="cl-file" multiple hidden accept=".pdf,.docx,.odt,.xlsx,.pptx,.txt,.md,.csv,.html,.jpg,.jpeg,.png,.webp">
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 16V6m-4 4 4-4 4 4M5 15v2a3 3 0 0 0 3 3h8a3 3 0 0 0 3-3v-2"/></svg>
      <b id="cl-say">Бросьте файл сюда</b><small>или нажмите · PDF, Word, Excel, PowerPoint, текст, картинки до 25 МБ</small></label>
    <div class="cl-off" id="cl-off" hidden><p id="cl-off-t"></p><button type="button" class="cl-btn" id="cl-on">Открыть в студии</button></div>
    <div class="cl-grid" id="cl-grid"></div>
    <button type="button" class="cl-more" id="cl-more">Всё облако — в студии</button>`;
  (el("#pult") || el("#play")).after(box);

  function render() {
    const st = CL.st || { files: [] };
    el("#cl-off").hidden = !st.why; box.classList.toggle("off", !!st.why);
    if (st.why) el("#cl-off-t").textContent = st.why === "e2e" ? "Облако хранит файлы зашифрованными — ключ только у ваших устройств. Включите его в студии одной кнопкой." : "Облаку нужен мозг Dewiar или вход аккаунтом.";
    const q = st.quota || 0, u = st.used || 0;
    el("#cl-used").textContent = q ? `${mb(u)} из ${mb(q)}` : "";
    el("#cl-fill").style.width = q ? Math.min(100, Math.round(u / q * 100)) + "%" : "0";
    if (CL.msg) el("#cl-say").textContent = CL.msg;
    const busy = String(st.busy || "");
    el("#cl-grid").innerHTML = (st.files || []).map(f => {
      const moving = busy.startsWith("up:" + f.name + ":") || busy.startsWith("down:" + f.name + ":");
      return `<button type="button" class="cl-f k-${esc(f.kind)}${moving ? " moving" : ""}" data-f="${esc(f.name)}" title="${esc(f.name)}"><i>${K[f.kind] || "TXT"}</i>`
        + `<span>${esc(f.name)}</span><small>${mb(f.size || 0)}${f.here ? "" : " · скоро будет здесь"}</small></button>`; }).join("")
      || (st.why ? "" : `<p class="cl-empty">Пока пусто. Бросьте сюда инструкцию, договор или фото — и они будут на всех ваших устройствах, а Лира сможет по ним ответить.</p>`);
  }
  async function load(fresh) {
    try { CL.st = await core.call("drive_status", { fresh: !!fresh }); } catch (e) { CL.st = CL.st || { files: [] }; }
    if (CL.active) render();
  }
  function say(t) { CL.msg = t; const s = el("#cl-say"); if (s) s.textContent = t; clearTimeout(CL.t); CL.t = setTimeout(() => { CL.msg = ""; const x = el("#cl-say"); if (x) x.textContent = "Бросьте файл сюда"; }, 5000); }
  async function put(files) {
    for (const f of files) {
      if (!EXT.test(f.name)) { say(`«${f.name}» — такие файлы облако не берёт`); continue; }
      if (f.size > 25 * 1048576) { say(`«${f.name}» больше 25 МБ`); continue; }
      say(`Кладу «${f.name}» в облако…`);
      try {
        if (f.size > 11e6) {                       // большое окно ядру целиком не передаст — пусть ядро возьмёт файл с диска
          const a = A(), p = a && a.pick_file ? await a.pick_file(`Файл «${f.name}» (*${f.name.slice(f.name.lastIndexOf("."))})`) : "";
          if (!p) throw new Error("большой файл — выберите его ещё раз в окне");
          await core.call("drive_add_path", { path: p });
        } else {
          const b64 = await new Promise((ok, bad) => { const fr = new FileReader(); fr.onload = () => ok(fr.result); fr.onerror = bad; fr.readAsDataURL(f); });
          await core.call("knowledge_add", { name: f.name, b64 });
        }
        say(`«${f.name}» — в облаке, скоро будет на всех устройствах`);
      } catch (e) { say(`${f.name}: ${e.message}`); }
    }
    setTimeout(() => load(true), 1200);
  }

  function enter() {
    if (CL.active) return;
    if (window.pultLeave) pultLeave();
    if (document.body.classList.contains("play") && window.padMode) padMode("notes");
    CL.active = true; document.body.classList.add("cloud");
    tab.classList.add("on"); tab.setAttribute("aria-selected", "true");
    try { if (typeof saveNow === "function") saveNow(); } catch (e) { }
    render(); load(true);
  }
  function leave() {
    if (!CL.active) return;
    CL.active = false; document.body.classList.remove("cloud");
    tab.classList.remove("on"); tab.setAttribute("aria-selected", "false");
  }
  window.cloudLeave = leave;
  tab.onclick = () => (CL.active ? null : enter());
  el("#tabs").addEventListener("click", leave, true);
  for (const id of ["#b-new", "#b-play", "#b-list", "#pt-tab"]) { const b = el(id); if (b) b.addEventListener("click", leave, true); }
  el("#cl-file").onchange = (e) => { const fs = [...e.target.files]; e.target.value = ""; put(fs); };
  const drop = el("#cl-drop");
  drop.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); el("#cl-file").click(); } });
  box.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("over"); });
  box.addEventListener("dragleave", (e) => { if (!box.contains(e.relatedTarget)) drop.classList.remove("over"); });
  box.addEventListener("drop", (e) => { e.preventDefault(); drop.classList.remove("over");
    const fs = [...((e.dataTransfer && e.dataTransfer.files) || [])]; if (fs.length) put(fs); });
  el("#cl-grid").addEventListener("click", (e) => {
    const b = e.target.closest("[data-f]"); if (!b) return;
    core.call("drive_open", { name: b.dataset.f }).catch(er => say(er.message));
  });
  const studio = () => { const a = A(); if (a && a.open_settings) a.open_settings("docs"); };
  el("#cl-more").onclick = studio; el("#cl-on").onclick = studio;
  core.on("drive", (e) => { CL.st = e; if (CL.active) render(); });
  // перетащили файл на блокнот, когда открыт лист, — подсказать флешку (сам файл в заметку не вставляется)
  document.addEventListener("dragenter", (e) => { if (!CL.active && e.dataTransfer && [...(e.dataTransfer.types || [])].includes("Files")) tab.classList.add("hint"); });
  document.addEventListener("dragleave", (e) => { if (!e.relatedTarget) tab.classList.remove("hint"); });
  document.addEventListener("drop", () => tab.classList.remove("hint"));
  tab.addEventListener("dragover", (e) => { e.preventDefault(); });
  tab.addEventListener("drop", (e) => { e.preventDefault(); tab.classList.remove("hint"); const fs = [...((e.dataTransfer && e.dataTransfer.files) || [])];
    enter(); if (fs.length) put(fs); });
})();
