/* Плагин «Расшифровка» (1.0.33) — вкладка «Расшифровки» на странице плагина (plugpage.js → trPage), раздела в меню нет.
   Ядро — core/transcribe.py (команды transcribe_*, событие «transcribe» с ходом работы). Здесь: принять файл (кнопка,
   перетаскивание, на Linux — путь от окна), список с ходом и «Стоп», поиск по тексту всех записей, запись целиком:
   метки времени, «Скопировать текст», «Субтитры .srt», «В «Моих файлах»», «Спросить Лиру», переименовать, удалить. */
const TR = { box: null, items: [], q: "", hits: null, open: null, rec: null, timer: 0, done: new Set() };
const TR_EXT = /\.(mp3|wav|m4a|ogg|oga|opus|flac|aac|wma|amr|webm|mp4|mkv|mov|avi|wmv|m4v|3gp|mpe?g|ts)$/i;
const trEsc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const trDur = (s) => { s = Math.round(+s || 0); if (!s) return ""; const h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60);
  return h ? `${h} ч ${m} мин` : m ? `${m} мин` : `${s} с`; };
const trWhen = (t) => { if (!t) return ""; const d = new Date(t * 1000), n = new Date();
  const hm = d.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
  return d.toDateString() === n.toDateString() ? `сегодня в ${hm}` : d.toLocaleDateString("ru-RU", { day: "numeric", month: "long" }) + ` в ${hm}`; };
const trMark = (t, q) => { const s = trEsc(t); if (!q) return s;
  const words = q.toLowerCase().replace(/\u0451/g, "\u0435").split(/\s+/).filter(Boolean).map(w => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  return words.length ? s.replace(new RegExp(`(${words.join("|")})`, "gi"), "<mark>$1</mark>") : s; };
const TR_IC = { mic: '<path d="M12 3.5a3 3 0 0 1 3 3v5a3 3 0 0 1-6 0v-5a3 3 0 0 1 3-3z"/><path d="M6 11a6 6 0 0 0 12 0M12 17v3.5M9 20.5h6"/>',
  film: '<rect x="3.5" y="5.5" width="17" height="13" rx="2.5"/><path d="M3.5 9.5h17M3.5 14.5h17M8 5.5v13M16 5.5v13"/>' };
const trSvg = (k) => `<svg viewBox="0 0 24 24" aria-hidden="true">${TR_IC[k]}</svg>`;

async function trPage(box) {
  TR.box = box; TR.open = null;
  box.innerHTML = `<div class="tr">
    <div class="tr-drop" id="tr-drop" tabindex="0" role="button" aria-label="Выбрать аудио или видео для расшифровки">
      <i class="tr-dic" aria-hidden="true">${trSvg("mic")}</i>
      <div class="tr-dt"><b>Перетащите запись сюда</b><span>Созвон, лекция, интервью, голосовое — аудио или видео. Расшифровка идёт на этом компьютере.</span></div>
      <button class="btn primary" type="button" id="tr-pick">Выбрать файл</button>
    </div>
    <label class="tr-find"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="6.5"/><path d="m20 20-4.4-4.4"/></svg>
      <input type="search" id="tr-q" placeholder="Найти в расшифровках: о чём говорили…" autocomplete="off" spellcheck="false" aria-label="Поиск в расшифровках"></label>
    <div id="tr-body"></div></div>`;
  $("#tr-pick").onclick = (e) => { e.stopPropagation(); trPick(); };
  const drop = $("#tr-drop");
  drop.onclick = () => trPick();
  drop.onkeydown = (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); trPick(); } };
  ["dragenter", "dragover"].forEach(t => box.addEventListener(t, (e) => { e.preventDefault(); if (e.dataTransfer) e.dataTransfer.dropEffect = "copy"; drop.classList.add("over"); }));
  box.addEventListener("dragleave", (e) => { if (!box.contains(e.relatedTarget)) drop.classList.remove("over"); });
  box.addEventListener("drop", (e) => { e.preventDefault(); drop.classList.remove("over"); TR.lastDrop = Date.now();
    const d = typeof cldDropped === "function" ? cldDropped(e) : { files: [...((e.dataTransfer || {}).files || [])], paths: [] };
    trAdd(d.files, d.paths); });
  $("#tr-q").oninput = () => { clearTimeout(TR.qt); TR.qt = setTimeout(() => { TR.q = $("#tr-q").value.trim(); TR.open = null; trLoad(); }, 220); };
  $("#tr-q").onkeydown = (e) => { if (e.key === "Escape" && $("#tr-q").value) { $("#tr-q").value = ""; TR.q = ""; trLoad(); } };
  await trLoad();
}

async function trLoad() {
  if (!TR.box || !TR.box.isConnected) return;
  let r; try { r = await core.call("transcribe_list", { q: TR.q }); } catch (e) { $("#tr-body").innerHTML = `<p class="res bad">${trEsc(e.message)}</p>`; return; }
  TR.items = r.items || []; TR.hits = TR.q ? (r.hits || []) : null;
  TR.items.filter(x => x.state === "done").forEach(x => TR.done.add(x.id));
  if (TR.open) return trOpen(TR.open, TR.openAt);
  trList();
}

function trState(x) {
  if (x.state === "run") return `<span class="tr-run"><i class="tr-bar"><i style="width:${x.pct || 0}%"></i></i>${x.pct ? `${x.pct}%` : "начинаю…"}</span>
    <button class="btn small ghost" data-stop="${trEsc(x.id)}">Стоп</button>`;
  if (x.state === "wait") return `<span class="tr-st">в очереди${x.place > 1 ? ` · ${x.place}-я` : ""}</span><button class="btn small ghost" data-stop="${trEsc(x.id)}">Убрать</button>`;
  if (x.state === "err") return `<span class="tr-st bad" title="${trEsc(x.err)}">не вышло: ${trEsc(String(x.err || "").slice(0, 90))}</span>`;
  if (x.state === "stop") return `<span class="tr-st">${trEsc(x.err || "остановлено")}</span>`;
  return "";
}

function trList() {
  const b = $("#tr-body"); if (!b) return;
  const q = TR.q, hits = TR.hits;
  if (!TR.items.length && !q) {
    b.innerHTML = `<div class="plp-none tr-none"><b>Расшифровок пока нет</b><span>Выберите файл выше или скажите Лире: «Расшифруй запись созвона». Готовый текст и субтитры появятся здесь и в «Моих файлах» → «Расшифровки».</span></div>`;
    return;
  }
  let html = "";
  if (hits) {
    html += hits.length ? `<p class="tr-k">Нашлось в записях · ${hits.length}</p><ol class="tr-hits">${hits.map((h, i) => `<li><button type="button" data-hit="${i}">
        <time>${trEsc(h.t)}</time><span><b>${trEsc(h.name)}</b>${trMark(h.text, q)}</span></button></li>`).join("")}</ol>`
      : `<p class="hint tr-zero">В тексте записей «${trEsc(q)}» не нашлось.</p>`;
  }
  const list = TR.items;
  if (list.length) html += (hits ? `<p class="tr-k">Записи</p>` : "") + `<ul class="tr-list">${list.map(x => `<li class="tr-item ${x.state}" data-id="${trEsc(x.id)}">
      <i class="tr-ic" aria-hidden="true">${trSvg(/\.(mp4|mkv|mov|avi|wmv|m4v|webm|3gp|mpe?g|ts)$/i.test(x.src || "") ? "film" : "mic")}</i>
      <button type="button" class="tr-main" data-open="${trEsc(x.id)}" ${x.n ? "" : "disabled"}>
        <b>${trMark(x.name, q)}</b>
        <small>${[trDur(x.dur), x.n ? `${x.words} слов` : "", trWhen(x.at)].filter(Boolean).join(" · ")}</small>
        ${x.preview && x.state !== "run" ? `<span class="tr-pv">${trEsc(x.preview)}</span>` : ""}
      </button>
      <span class="tr-side">${trState(x)}</span></li>`).join("")}</ul>`;
  b.innerHTML = html;
  $$("#tr-body [data-open]").forEach(el => el.onclick = () => trOpen(el.dataset.open));
  $$("#tr-body [data-stop]").forEach(el => el.onclick = async () => { try { await core.call("transcribe_stop", { id: el.dataset.stop }); trLoad(); } catch (e) { toast(e.message); } });
  $$("#tr-body [data-hit]").forEach(el => el.onclick = () => { const h = hits[+el.dataset.hit]; trOpen(h.id, h.at_s); });
}

async function trOpen(id, at) {
  TR.open = id; TR.openAt = at;
  let x; try { x = await core.call("transcribe_get", { id }); } catch (e) { toast(e.message); TR.open = null; return trList(); }
  TR.rec = x;
  const b = $("#tr-body"); if (!b) return;
  const segs = x.segs || [], q = TR.q;
  const fmt = (s) => { s = Math.max(0, +s || 0); const h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), c = Math.floor(s % 60);
    return (h ? `${h}:${String(m).padStart(2, "0")}` : String(m).padStart(2, "0")) + ":" + String(c).padStart(2, "0"); };
  b.innerHTML = `<article class="tr-rec">
    <header class="tr-rh">
      <button class="tr-back" type="button" id="tr-back"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m14.5 6-6 6 6 6"/></svg>Все расшифровки</button>
      <h3 id="tr-name" title="Нажмите, чтобы переименовать" tabindex="0">${trEsc(x.name)}</h3>
      <p class="tr-meta">${[trDur(x.dur), `${x.words} слов`, trWhen(x.at)].filter(Boolean).join(" · ")}${x.state === "stop" ? " · " + trEsc(x.err) : ""}</p>
      <div class="tr-acts">
        <button class="btn primary" id="tr-ask">Спросить Лиру</button>
        <button class="btn" id="tr-copy">Скопировать текст</button>
        ${(x.files || []).length ? `<button class="btn" id="tr-srt">Субтитры .srt</button><button class="btn ghost" id="tr-dir">В «Моих файлах»</button>` : ""}
        <span class="grow"></span><button class="btn ghost danger" id="tr-del">Удалить</button>
      </div>
    </header>
    <ol class="tr-segs">${segs.map(([a, , t], i) => `<li data-i="${i}"${at != null && a <= at && (segs[i + 1] ? segs[i + 1][0] > at : true) ? ' class="hit"' : ""}><time>${fmt(a)}</time><p>${trMark(t, q)}</p></li>`).join("")}</ol>
  </article>`;
  $("#tr-back").onclick = () => { TR.open = null; TR.openAt = null; trLoad(); };
  $("#tr-ask").onclick = () => plpAsk(`Сделай выжимку расшифровки «${x.name}»: главное, что решили, и задачи — кто, что, когда.`);
  $("#tr-copy").onclick = async () => { try { const r = await core.call("transcribe_text", { id }); await navigator.clipboard.writeText(r.text); toast("Текст скопирован — с метками времени"); } catch (e) { toast(e.message); } };
  if ($("#tr-srt")) $("#tr-srt").onclick = () => core.call("ws_open", { path: x.files.find(f => f.endsWith(".srt")) }).catch(e => toast(e.message));
  if ($("#tr-dir")) $("#tr-dir").onclick = () => core.call("ws_open", { path: "Расшифровки" }).catch(e => toast(e.message));
  $("#tr-del").onclick = async () => {
    if (!await ask(`Удалить расшифровку «${x.name}»? Текст и субтитры в «Моих файлах» останутся.`)) return;
    try { await core.call("transcribe_del", { id }); TR.open = null; trLoad(); toast("Удалено"); } catch (e) { toast(e.message); } };
  const nm = $("#tr-name");
  const rename = async () => { const v = nm.textContent.trim(); nm.contentEditable = "false"; if (!v || v === x.name) { nm.textContent = x.name; return; }
    try { const r = await core.call("transcribe_rename", { id, name: v }); x.name = r.name; nm.textContent = r.name; } catch (e) { nm.textContent = x.name; toast(e.message); } };
  nm.onclick = () => { if (nm.isContentEditable) return; nm.contentEditable = "true"; nm.focus(); document.getSelection().selectAllChildren(nm); };
  nm.onkeydown = (e) => { if (e.key === "Enter") { e.preventDefault(); nm.blur(); } if (e.key === "Escape") { nm.textContent = x.name; nm.blur(); } };
  nm.onblur = rename;
  const hit = $(".tr-segs li.hit"); if (hit) hit.scrollIntoView({ block: "center" });
}

async function trPick() {
  const a = window.api && window.api();
  if (!a || !a.pick_file) return toast("Выбрать файл можно в программе на компьютере");
  const p = await a.pick_file("Аудио и видео (*.mp3;*.m4a;*.wav;*.ogg;*.opus;*.flac;*.mp4;*.mov;*.mkv;*.webm;*.avi)");
  if (p) trAdd([], [p]);
}

async function trAdd(files, paths) {
  const a = window.api && window.api();
  for (const p of paths || []) {
    const n = p.split(/[\\/]/).pop();
    if (!TR_EXT.test(n)) { toast(`«${n}» — это не аудио и не видео`, 4000); continue; }
    try { await core.call("transcribe_start", { path: p }); } catch (e) { toast(`${n}: ${e.message}`, 5000); }
  }
  for (const f of files || []) {
    if (!TR_EXT.test(f.name)) { toast(`«${f.name}» — это не аудио и не видео`, 4000); continue; }
    try {
      if (f.size > 11e6) {                        // большое через окно ядра не передать — ядро возьмёт файл с диска
        const p = a && a.pick_file ? await a.pick_file(`Файл «${f.name}» (*${f.name.slice(f.name.lastIndexOf("."))})`) : "";
        if (!p) throw new Error("большой файл — выберите его ещё раз в окне");
        await core.call("transcribe_start", { path: p });
      } else {
        const b64 = await new Promise((ok, bad) => { const fr = new FileReader(); fr.onload = () => ok(fr.result); fr.onerror = bad; fr.readAsDataURL(f); });
        await core.call("transcribe_upload", { name: f.name, b64 });
      }
    } catch (e) { toast(`${f.name}: ${e.message}`, 5000); }
  }
  TR.open = null; trLoad();
}

/* файл, брошенный на окно (Linux: путь отдаёт само окно, ui/app.py) — если открыта вкладка «Расшифровки» */
(() => {
  const prev = window.dwNativeDrop;
  window.dwNativeDrop = (paths) => {
    if (TR.box && TR.box.isConnected && $("#p-plg") && $("#p-plg").classList.contains("cur")) {
      if (Date.now() - (TR.lastDrop || 0) < 3000 || !Array.isArray(paths) || !paths.length) return;
      return trAdd([], paths);
    }
    if (typeof prev === "function") return prev(paths);
  };
})();

if (window.core) core.on("transcribe", (e) => {
  const x = e.item;
  if (x && x.state === "done" && !TR.done.has(x.id)) {
    TR.done.add(x.id);
    toast(`Расшифровка «${x.name}» готова — ${trDur(x.dur) || "запись"}, текст и субтитры в «Моих файлах» → «Расшифровки»`, 5000);
  }
  if (!TR.box || !TR.box.isConnected || TR.open) return;
  clearTimeout(TR.timer); TR.timer = setTimeout(trLoad, 150);
});
window.trPage = trPage;
