/* «Облако Лиры» в «Моих файлах» (1.0.23; владелец 17.11: «в Лире нужно место типа сетевой флешки: закидываешь — и
   открывается с любого устройства, Лира знает, что там… красиво, стильно, привлекательно»). Ядро — core/drive.py
   (команды drive_status, drive_sync, drive_remove, drive_open, drive_add_path; событие "drive"), сервер — cloud/drive.php.
   Сверху — облако и шкала места, ниже — свои устройства, зона «перетащите сюда» и плитки файлов. Плитки — все файлы
   «Моих файлов»: из облака и те, что пока только здесь (облако выключено, файл больше 25 МБ, отправляется). */
const LDV = { st: null, adding: [] };
const LDV_K = { pdf: "PDF", doc: "DOC", sheet: "XLS", slides: "PPT", image: "IMG", text: "TXT" };
const LDV_EXT = /\.(pdf|docx|odt|xlsx|pptx|txt|md|csv|html?|jpe?g|png|webp)$/i;
const cldMB = (b) => !b ? "0 МБ" : b >= 1048576 ? (b / 1048576).toFixed(b >= 10485760 ? 0 : 1).replace(".", ",") + " МБ" : Math.max(1, Math.round(b / 1024)) + " КБ";
const cldKind = (n) => { const e = (String(n).split(".").pop() || "").toLowerCase();
  return e === "pdf" ? "pdf" : /^(docx|odt)$/.test(e) ? "doc" : /^(xlsx|csv)$/.test(e) ? "sheet" : e === "pptx" ? "slides" : /^(jpe?g|png|webp)$/.test(e) ? "image" : "text"; };
const LDV_DEV = {
  pc: '<svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8M12 16v4"/></svg>',
  phone: '<svg viewBox="0 0 24 24"><rect x="7" y="2.5" width="10" height="19" rx="2.5"/><path d="M11 18.5h2"/></svg>',
};

function cldRender(st) {
  if (!st || !$("#ld")) return;
  LDV.st = st;
  const used = st.used || 0, quota = st.quota || 200 * 1048576, pct = Math.min(1, used / quota);
  $("#ld-used").textContent = cldMB(used); $("#ld-quota").textContent = "из " + cldMB(quota);
  const C = 2 * Math.PI * 18, ring = $("#ld-ring");
  ring.style.strokeDasharray = `${C}`; ring.style.strokeDashoffset = `${C * (1 - pct)}`;
  $("#ld-meter").classList.toggle("full", pct > 0.9);
  $("#ld-meter").setAttribute("aria-label", `Занято ${cldMB(used)} из ${cldMB(quota)}`);
  // свои устройства: облако на всех — у каждого галочка
  const devs = (st.devices || []).length ? st.devices : [{ name: "Этот компьютер", app: "pc", me: true }];
  $("#ld-devs").innerHTML = devs.map(d => `<li class="${d.me ? "me" : ""}">${LDV_DEV[d.app === "phone" || d.app === "web" ? "phone" : "pc"]}`
    + `<span>${escH(d.me ? "Этот компьютер" : d.name || (d.app === "pc" ? "Компьютер" : "Телефон"))}</span>`
    + `${st.why ? "" : '<i aria-label="на связи"></i>'}</li>`).join("");
  // выключено: нет входа или шифрования — одна понятная кнопка
  const off = $("#ld-off"); off.hidden = !st.why;
  $("#ld").classList.toggle("is-off", !!st.why);
  if (st.why === "e2e") {
    $("#ld-off-t").textContent = "Облако хранит файлы зашифрованными — ключ есть только у ваших устройств, сервер Dewiar их не прочтёт. Включите, и файлы появятся на всех ваших компьютерах и телефоне.";
    $("#ld-on").hidden = false;
  } else if (st.why === "nokey") {
    $("#ld-off-t").textContent = "Облаку нужен мозг Dewiar или вход аккаунтом — студия → «Мозг». Пока файлы — только на этом компьютере.";
    $("#ld-on").hidden = true;
  }
  const err = st.error ? `Облако: ${st.error}` : st.full ? `«${st.full}» не поместился — в облаке не хватает места` : "";
  $("#ld-sub").textContent = err || "Ваши файлы — на всех ваших устройствах. Лира знает, что в них, и ответит.";
  $("#ld-sub").classList.toggle("bad", !!err);
  cldGrid();
}

/* плитки: облако + то, что пока только здесь (DC.files — «Мои файлы» этого компьютера, links.js) */
function cldGrid() {
  const g = $("#ld-grid"); if (!g) return;
  const st = LDV.st || { files: [] }, cloud = st.files || [], names = new Set(cloud.map(f => f.name));
  const local = (typeof DC === "object" ? DC.files : []).filter(f => !String(f.path).includes("/") && !names.has(f.path));
  const busy = String(st.busy || "");
  const tiles = LDV.adding.map(n => ({ name: n, fly: true }))
    .concat(cloud.map(f => Object.assign({ cloud: true }, f)))
    .concat(local.map(f => ({ name: f.path, size: f.size, here: true, only: true, err: f.error })));
  g.innerHTML = tiles.map((f, i) => {
    const k = f.kind || cldKind(f.name);
    const up = busy.startsWith("up:" + f.name + ":"), down = busy.startsWith("down:" + f.name + ":");
    const where = f.fly ? "отправляется в облако…" : up ? "отправляется в облако…" : down ? "приходит с другого устройства…"
      : f.only ? (st.why ? "только на этом компьютере" : f.size > 25 * 1048576 ? "больше 25 МБ — только здесь" : "отправляется в облако…")
      : f.here ? "на всех устройствах" : "в облаке · скоро будет здесь";
    return `<article class="ld-f k-${k}${f.fly || up || down ? " moving" : ""}${f.here && !f.only && !up && !down ? " synced" : ""}" data-i="${i}" tabindex="0" title="${escH(f.name)}">`
      + `<span class="ld-k">${LDV_K[k]}</span><b>${escH(f.name)}</b>`
      + `<small>${f.size ? cldMB(f.size) + " · " : ""}${escH(where)}</small>`
      + (f.fly ? "" : `<button class="ld-x" type="button" data-x="${i}" aria-label="Убрать «${escH(f.name)}»" title="Убрать отовсюду">×</button>`)
      + `</article>`;
  }).join("");
  LDV.tiles = tiles;
  $("#ld-grid").classList.toggle("empty", !tiles.length);
  const n = cloud.length + local.length;
  $("#ld-know").textContent = n ? `Лира знает ${n} ${n % 10 === 1 && n % 100 !== 11 ? "файл" : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20) ? "файла" : "файлов"} — спросите о любом.`
    : "Пока пусто — положите сюда первый файл: инструкцию, договор, конспект.";
}

async function cldLoad(fresh) {
  try { cldRender(await core.call("drive_status", { fresh: !!fresh })); } catch (e) { /* ядро старее — карточка остаётся как есть */ }
}

/* что бросили: сами файлы, а если система отдала только ссылки file://… (17.11, владелец: «перетягиваю pdf — ничего не
   происходит»; так бывает на Linux под Wayland, из браузера и некоторых файловых менеджеров) — пути, их ядро возьмёт с диска */
function cldDropped(e) {
  const dt = e.dataTransfer || {}, files = [...(dt.files || [])];
  const uris = files.length ? "" : String((dt.getData && dt.getData("text/uri-list")) || "");
  const paths = uris.split(/\r?\n/).map(u => u.trim()).filter(u => /^file:\/\//i.test(u)).map(u => {
    const p = decodeURIComponent(u.replace(/^file:\/\/(localhost)?/i, "")); return /^\/[A-Za-z]:\//.test(p) ? p.slice(1) : p; });
  return { files, paths, types: [...(dt.types || [])].join(",") };
}

/* добавить: файл в «Мои файлы» (как «Добавить файлы…»), облако заберёт его сразу (ядро будит обмен) */
async function cldAdd(files, paths, types) {
  const a = window.api && window.api();
  if (!files.length && !(paths || []).length) {
    toast("Файл не дошёл до окна — нажмите на поле с пунктиром и выберите его", 5000);
    // 17.11 (владелец, Windows): перетаскивание «ничего не делает» — в журнал, что пришло вместо файла
    core.call("js_errors", { errors: [`cloud (studio): drop without a file, got: ${types || "nothing"}`] }).catch(() => {});
    return;
  }
  // владелец 17.11: положил файл в облако — включаем облако сами (шифрование на устройстве), без кнопки «Включить»
  const st = await core.call("drive_status", {}).catch(() => LDV.st);
  if (st && st.why === "e2e") {
    try { await core.call("sync_e2e", { on: true }); toast("Облако включено — файлы шифруются на ваших устройствах", 3500); }
    catch (e) { /* не вышло — файл ляжет в «Мои файлы», облако подскажет кнопкой */ }
  }
  for (const p of paths || []) {
    const n = p.split(/[\\/]/).pop();
    if (!LDV_EXT.test(n)) { toast(`«${n}» — такие файлы облако не берёт: PDF, Word, Excel, PowerPoint, текст и картинки`, 5000); continue; }
    LDV.adding.push(n); cldGrid();
    try { const r = await core.call("drive_add_path", { path: p }); if (typeof renderKn === "function" && r && r.files) renderKn(r.files); }
    catch (e) { toast(`${n}: ${e.message}`, 5000); }
    LDV.adding = LDV.adding.filter(x => x !== n);
  }
  for (const f of files || []) {
    if (!LDV_EXT.test(f.name)) { toast(`«${f.name}» — такие файлы облако не берёт: PDF, Word, Excel, PowerPoint, текст и картинки`, 5000); continue; }
    if (f.size > 25 * 1048576) { toast(`«${f.name}» больше 25 МБ — в облако такой не поместится`, 5000); continue; }
    LDV.adding.push(f.name); cldGrid();
    try {
      if (f.size > 11e6) {                       // большое через окно ядра не передать — пусть ядро возьмёт сам файл с диска
        const p = a && a.pick_file ? await a.pick_file(`Файл «${f.name}» (*${f.name.slice(f.name.lastIndexOf("."))})`) : "";
        if (!p) throw new Error("большой файл — выберите его ещё раз в окне");
        await core.call("drive_add_path", { path: p });
      } else {
        const b64 = await new Promise((ok, bad) => { const fr = new FileReader(); fr.onload = () => ok(fr.result); fr.onerror = bad; fr.readAsDataURL(f); });
        const r = await core.call("knowledge_add", { name: f.name, b64 });
        if (typeof renderKn === "function") renderKn(r.files);
      }
    } catch (e) { toast(`${f.name}: ${e.message}`, 5000); }
    LDV.adding = LDV.adding.filter(x => x !== f.name);
  }
  cldGrid();
  setTimeout(() => cldLoad(true), 1200);
}

(function cldInit() {
  if (!$("#ld")) return;
  const drop = $("#ld-drop");
  $("#ld-file").onchange = (e) => { const fs = [...e.target.files]; e.target.value = ""; if (fs.length) cldAdd(fs, []); };
  drop.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); $("#ld-file").click(); } });
  // принимает вся карточка облака, а не только поле с пунктиром (бросили на плитки — тоже в облако)
  const card = $("#ld");
  ["dragenter", "dragover"].forEach(t => card.addEventListener(t, (e) => { e.preventDefault(); e.stopPropagation(); if (e.dataTransfer) e.dataTransfer.dropEffect = "copy"; drop.classList.add("over"); }));
  card.addEventListener("dragleave", (e) => { if (!card.contains(e.relatedTarget)) drop.classList.remove("over"); });
  card.addEventListener("dragend", () => drop.classList.remove("over"));
  card.addEventListener("drop", (e) => { e.preventDefault(); e.stopPropagation(); drop.classList.remove("over");
    const d = cldDropped(e); if (d.files.length || d.paths.length) { drop.classList.add("caught"); setTimeout(() => drop.classList.remove("caught"), 700); } cldAdd(d.files, d.paths, d.types); });
  // Ctrl+V: файл, скопированный в проводнике (Ctrl+C), — тоже в облако, пока открыты «Мои файлы»
  document.addEventListener("paste", (e) => {
    const pg = $("#p-docs"); if (!pg || !pg.classList.contains("cur") || /^(INPUT|TEXTAREA)$/.test((e.target || {}).tagName || "")) return;
    const cd = e.clipboardData || {}, fs = [...(cd.files || [])];
    const d = fs.length ? { files: fs, paths: [] } : cldDropped({ dataTransfer: cd });
    if (!d.files.length && !d.paths.length) return;
    e.preventDefault(); cldAdd(d.files, d.paths);
  });
  $("#ld-on").onclick = () => core.call("sync_e2e", { on: true }).then(() => { toast("Облако включено — файлы уже летят", 3500); setTimeout(() => cldLoad(true), 1500); }).catch(e => toast(e.message));
  $("#ld-grid").addEventListener("click", async (e) => {
    const x = e.target.closest("[data-x]");
    if (x) {
      e.stopPropagation();
      const f = LDV.tiles[+x.dataset.x]; if (!f) return;
      if (!await ask(`Убрать «${f.name}» из облака? Файл пропадёт на всех ваших устройствах (здесь — в корзину).`, { ok: "Убрать" })) return;
      try { cldRender(await core.call("drive_remove", { name: f.name })); if (typeof loadDocs === "function") loadDocs(); } catch (er) { toast(er.message); }
      return;
    }
    const t = e.target.closest(".ld-f"); if (!t) return;
    const f = LDV.tiles[+t.dataset.i]; if (!f || f.fly) return;
    core.call("drive_open", { name: f.name }).catch(er => toast(er.message));
  });
  $("#ld-grid").addEventListener("keydown", (e) => { if ((e.key === "Enter") && e.target.classList.contains("ld-f")) e.target.click(); });
  core.on("drive", (e) => { if ($("#p-docs") && $("#p-docs").classList.contains("cur")) cldRender(e); });
  window.cldLoad = cldLoad; window.cldGrid = cldGrid;
})();
