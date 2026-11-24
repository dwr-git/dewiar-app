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
  const mb = (b) => !b ? "0 МБ" : b >= 1048576 ? (b / 1048576).toFixed(b >= 10485760 ? 0 : 1).replace(".", ",") + " МБ" : Math.max(1, Math.round(b / 1024)) + " КБ";
  const CL = { active: false, st: null, msg: "", ask: null };

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
    <div class="cl-hd"><span class="cl-ico" aria-hidden="true"><svg class="cl-ring" viewBox="0 0 56 56"><defs><linearGradient id="cl-g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#8fd3ff"/><stop offset=".55" stop-color="#8b8cf7"/><stop offset="1" stop-color="#c58cf7"/></linearGradient></defs>
        <circle class="cl-rt" cx="28" cy="28" r="25"/><circle class="cl-rf" id="cl-ring" cx="28" cy="28" r="25" stroke="url(#cl-g)"/></svg>
        <svg class="cl-cloud" viewBox="0 0 48 48"><path d="M14.5 37h20a8.5 8.5 0 0 0 1.3-16.9A11.5 11.5 0 0 0 13.6 18 9.5 9.5 0 0 0 14.5 37z" fill="url(#cl-g)"/><path d="M24 31v-9m-4 3.6 4-4 4 4" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg></span>
      <div class="cl-tt"><b>Облако Лиры</b><small id="cl-sub">ваши файлы — на всех ваших устройствах</small></div>
      <span class="cl-used" id="cl-used"><b id="cl-used-n"></b><small id="cl-used-q"></small></span></div>
    <div class="cl-off" id="cl-off" hidden><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="10.5" width="14" height="10" rx="2.5"/><path d="M8.5 10.5V8a3.5 3.5 0 0 1 7 0v2.5"/></svg>
      <p id="cl-off-t"></p><button type="button" class="cl-btn" id="cl-on">Включить</button></div>
    <label class="cl-drop" id="cl-drop" tabindex="0"><input type="file" id="cl-file" multiple hidden accept=".pdf,.docx,.odt,.xlsx,.pptx,.txt,.md,.csv,.html,.jpg,.jpeg,.png,.webp">
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 16V6m-4 4 4-4 4 4M5 15v2a3 3 0 0 0 3 3h8a3 3 0 0 0 3-3v-2"/></svg>
      <b id="cl-say">Перетащите файл сюда</b><small>или нажмите, чтобы выбрать, или Ctrl+V · PDF, Word, Excel, PowerPoint, текст, картинки до 25 МБ</small>
      <em class="cl-why">Инструкция, договор, фото — откроются на всех ваших устройствах, а Лира ответит по ним</em></label>
    <div class="cl-grid" id="cl-grid"></div>
    <button type="button" class="cl-more" id="cl-more">Всё облако — в студии</button>`;
  (el("#pult") || el("#play")).after(box);

  function render() {
    const st = CL.st || { files: [] };
    // выключено — короткая строка с одной кнопкой, а поле приёма остаётся (владелец 17.11: «когда пусто — понятный блок
    // загрузки нажатием или перетаскиванием»): файл ляжет здесь и уйдёт в облако, как только его включат
    el("#cl-off").hidden = !st.why; box.classList.toggle("off", !!st.why);
    if (st.why && !CL.kept) el("#cl-off-t").textContent = st.why === "e2e" ? "Облако выключено — файлы пока только на этом компьютере. Шифруются на ваших устройствах, сервер их не прочтёт." : "Облаку нужен мозг Dewiar или вход аккаунтом.";
    el("#cl-on").textContent = st.why === "e2e" ? "Включить" : "Открыть студию";
    // ещё не сверились с облаком (открыли сразу после запуска) — не «пусто»: запомненные файлы и «сверяю с облаком…»,
    // а если их нет — три мерцающие плитки (владелец 18.11: «секунд 10 ничего, переживал, что файлы потерялись»)
    const checking = !CL.st || !!st.checking, none = !(st.files || []).length;
    box.classList.toggle("empty", none && !checking);
    box.classList.toggle("checking", checking);
    el("#cl-sub").textContent = checking ? "сверяю с облаком…" : "ваши файлы — на всех ваших устройствах";
    const q = st.quota || 0, u = st.used || 0;
    // место — кольцом вокруг облачка (владелец 17.11: «серую длинную полосу — симпатичнее, живее»): занятое светится
    // цветами Лиры, а число — крупно справа, как в ролике урока
    el("#cl-used").hidden = !q || (!CL.st || st.checking) && !u; el("#cl-used-n").textContent = mb(u); el("#cl-used-q").textContent = q ? "из " + mb(q) : "";
    const C = 2 * Math.PI * 25, pct = q ? Math.min(1, u / q) : 0, ring = el("#cl-ring");
    ring.style.strokeDasharray = `${C}`; ring.style.strokeDashoffset = `${C * (1 - (pct && Math.max(pct, 0.03)))}`;
    box.classList.toggle("full", pct > 0.9);
    if (CL.msg) el("#cl-say").textContent = CL.msg;
    const busy = String(st.busy || "");
    // убрать файл — и здесь, как в студии (владелец 18.11): «×» на плитке, подтверждение — прямо в плитке, без окон
    el("#cl-grid").innerHTML = (st.files || []).map(f => {
      const moving = busy.startsWith("up:" + f.name + ":") || busy.startsWith("down:" + f.name + ":");
      if (CL.ask === f.name) return `<div class="cl-f ask k-${esc(f.kind)}" data-ask="${esc(f.name)}"><span>Убрать «${esc(f.name)}»?</span>`
        + `<small>Пропадёт на всех ваших устройствах, здесь — в корзину</small><div class="cl-ask"><button type="button" class="cl-yes" data-yes>Убрать</button>`
        + `<button type="button" class="cl-no" data-no>Отмена</button></div></div>`;
      return `<div role="button" tabindex="0" class="cl-f k-${esc(f.kind)}${moving ? " moving" : ""}" data-f="${esc(f.name)}" title="${esc(f.name)}"><i>${K[f.kind] || "TXT"}</i>`
        + `<span>${esc(f.name)}</span><small>${mb(f.size || 0)}${f.here ? "" : " · скоро будет здесь"}</small>`
        + (moving ? "" : (f.here ? `<button type="button" class="cl-dl" data-dl aria-label="Скачать «${esc(f.name)}»" title="Скачать — сохранить копию в папку">`
          + '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 4v11m-4.5-4.5L12 15l4.5-4.5M5 19h14"/></svg></button>' : "")
          + `<button type="button" class="cl-x" data-x aria-label="Убрать «${esc(f.name)}»" title="Убрать отовсюду">×</button>`) + `</div>`; }).join("")
      || (checking ? '<div class="cl-f cl-sk" aria-hidden="true"></div>'.repeat(3) : "");
    el("#cl-grid").setAttribute("aria-busy", checking ? "true" : "false");
  }
  async function load(fresh) {
    try { CL.st = await core.call("drive_status", { fresh: !!fresh }); } catch (e) { CL.st = CL.st || { files: [] }; }
    if (CL.active) render();
  }
  function say(t) { CL.msg = t; const s = el("#cl-say"); if (s) s.textContent = t; clearTimeout(CL.t); CL.t = setTimeout(() => { CL.msg = ""; const x = el("#cl-say"); if (x) x.textContent = "Перетащите файл сюда"; }, 5000); }
  // что бросили: сами файлы, а если система отдала только ссылки file://… (17.11, владелец: «перетягиваю pdf — ничего не
  // происходит»; так бывает на Linux под Wayland, из браузера и некоторых файловых менеджеров) — пути, их ядро возьмёт с диска
  const dropped = (e) => {
    const dt = e.dataTransfer || {}, files = [...(dt.files || [])];
    const uris = files.length ? "" : String((dt.getData && dt.getData("text/uri-list")) || "");
    const paths = uris.split(/\r?\n/).map(u => u.trim()).filter(u => /^file:\/\//i.test(u)).map(u => {
      const p = decodeURIComponent(u.replace(/^file:\/\/(localhost)?/i, "")); return /^\/[A-Za-z]:\//.test(p) ? p.slice(1) : p; });
    return { files, paths, types: [...(dt.types || [])].join(",") };
  };
  async function put(files, paths, types) {
    if (!files.length && !(paths || []).length) {
      // страница файла не получила — на Linux его следом отдаст окно (ui/app.py _drop_hook → dwNativeDrop); не дождались —
      // подсказка и строка в журнал, что пришло вместо файла
      clearTimeout(CL.missT);
      CL.missT = setTimeout(() => {
        say("Файл не дошёл до окна — нажмите сюда и выберите его");
        try { core.call("js_errors", { errors: [`cloud (pad): drop without a file, got: ${types || "nothing"}`] }).catch(() => {}); } catch (e) { }
      }, 1600);
      return;
    }
    clearTimeout(CL.missT); CL.lastDrop = Date.now();
    // владелец 17.11: «обязательно включать? пусть включается само, если человек кладёт файл» — положил файл в облако,
    // значит, облако ему нужно: включаем шифрование сами (как кнопка «Включить»), без лишнего шага
    const st = await core.call("drive_status", {}).catch(() => CL.st);   // свежее: вкладку могли открыть только что
    if (st && st.why === "e2e") {
      try { await core.call("sync_e2e", { on: true }); CL.st = Object.assign({}, CL.st, { why: "" }); render(); say("Облако включено — кладу файл…"); }
      catch (e) { /* не вышло — файл всё равно ляжет здесь, а облако подскажет кнопкой */ }
    }
    for (const p of paths || []) {
      const n = p.split(/[\\/]/).pop();
      if (!EXT.test(n)) { say(`«${n}» — такие файлы облако не берёт`); continue; }
      say(`Кладу «${n}» в облако…`);
      try { await core.call("drive_add_path", { path: p }); say(`«${n}» — в облаке, скоро будет на всех устройствах`); }
      catch (e) { say(`${n}: ${e.message}`); }
    }
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
    // облако выключено (зона приёма скрыта) — сказать там, где видно: файл здесь, в облако уйдёт после включения
    if (CL.st && CL.st.why) { CL.kept = true; el("#cl-off-t").textContent = "Файл сохранён на этом компьютере. В облако и на другие устройства он уйдёт, как только облако включите."; }
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
  // файл, брошенный на окно, отдало само окно (Linux: GTK видит адреса file://, а страница — не всегда; ui/app.py
  // _drop_hook): страница его уже приняла — ничего; облако открыто или файл бросили на облачко — кладём по путям
  window.dwNativeDrop = (paths) => {
    if (Date.now() - (CL.lastDrop || 0) < 3000 || !Array.isArray(paths) || !paths.length) return;
    if (!CL.active && !CL.missT) return;              // бросили на лист заметки — это не облаку
    if (!CL.active) enter();
    put([], paths);
  };
  tab.onclick = () => (CL.active ? null : enter());
  el("#tabs").addEventListener("click", leave, true);
  for (const id of ["#b-new", "#b-play", "#b-list", "#pt-tab"]) { const b = el(id); if (b) b.addEventListener("click", leave, true); }
  el("#cl-file").onchange = (e) => { const fs = [...e.target.files]; e.target.value = ""; if (fs.length) put(fs, []); };
  const drop = el("#cl-drop");
  drop.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); el("#cl-file").click(); } });
  box.addEventListener("dragover", (e) => { e.preventDefault(); if (e.dataTransfer) e.dataTransfer.dropEffect = "copy"; drop.classList.add("over"); });
  box.addEventListener("dragleave", (e) => { if (!box.contains(e.relatedTarget)) drop.classList.remove("over"); });
  box.addEventListener("drop", (e) => { e.preventDefault(); drop.classList.remove("over"); const d = dropped(e); put(d.files, d.paths, d.types); });
  // Ctrl+V: файл, скопированный в проводнике (Ctrl+C), — тоже в облако (17.11: на Windows перетаскивание не доходило)
  document.addEventListener("paste", (e) => {
    if (!CL.active) return;
    const cd = e.clipboardData || {}, fs = [...(cd.files || [])];
    const d = fs.length ? { files: fs, paths: [] } : dropped({ dataTransfer: cd });
    if (!d.files.length && !d.paths.length) return;
    e.preventDefault(); put(d.files, d.paths);
  });
  el("#cl-grid").addEventListener("click", async (e) => {
    if (e.target.closest("[data-no]")) { CL.ask = null; render(); return; }
    if (e.target.closest("[data-yes]")) {
      const name = e.target.closest("[data-ask]").dataset.ask;
      CL.ask = null;
      try { CL.st = await core.call("drive_remove", { name }); render(); say(`«${name}» убран из облака`); }
      catch (er) { render(); say(er.message); }
      return;
    }
    const b = e.target.closest("[data-f]"); if (!b) return;
    if (e.target.closest("[data-x]")) { CL.ask = b.dataset.f; render(); const y = el("#cl-grid [data-no]"); if (y) y.focus(); return; }
    if (e.target.closest("[data-dl]")) {            // копия файла — куда человек выберет (окно «Сохранить»)
      const a = A(), name = b.dataset.f;
      try {
        const src = await core.call("drive_path", { name });
        const to = a && a.save_copy ? await a.save_copy(src, name) : "";
        if (to) say(`«${name}» сохранён: ${to}`);
      } catch (er) { say(er.message); }
      return;
    }
    core.call("drive_open", { name: b.dataset.f }).catch(er => say(er.message));
  });
  el("#cl-grid").addEventListener("keydown", (e) => {
    if (e.key === "Escape" && CL.ask) { CL.ask = null; render(); return; }
    if ((e.key === "Enter" || e.key === " ") && e.target.matches && e.target.matches(".cl-f[data-f]")) { e.preventDefault(); e.target.click(); }
  });
  const studio = () => { const a = A(); if (a && a.open_settings) a.open_settings("docs"); };
  el("#cl-more").onclick = studio;
  // «Включить» — прямо здесь, как кнопка в студии (sync_e2e): ключ шифрования создаётся на этом устройстве
  el("#cl-on").onclick = () => {
    if (!CL.st || CL.st.why !== "e2e") return studio();
    el("#cl-on").disabled = true;
    core.call("sync_e2e", { on: true }).then(() => { CL.kept = false; say("Облако включено — файлы уже летят"); setTimeout(() => load(true), 1500); })
      .catch(e => { el("#cl-off-t").textContent = e.message; }).finally(() => { el("#cl-on").disabled = false; });
  };
  core.on("drive", (e) => { CL.st = e; if (CL.active) render(); });
  // перетащили файл на блокнот, когда открыт лист, — подсказать флешку (сам файл в заметку не вставляется)
  document.addEventListener("dragenter", (e) => { if (!CL.active && e.dataTransfer && [...(e.dataTransfer.types || [])].includes("Files")) tab.classList.add("hint"); });
  document.addEventListener("dragleave", (e) => { if (!e.relatedTarget) tab.classList.remove("hint"); });
  document.addEventListener("drop", () => tab.classList.remove("hint"));
  tab.addEventListener("dragover", (e) => { e.preventDefault(); if (e.dataTransfer) e.dataTransfer.dropEffect = "copy"; });
  tab.addEventListener("drop", (e) => { e.preventDefault(); tab.classList.remove("hint"); const d = dropped(e); enter(); put(d.files, d.paths, d.types); });
})();
