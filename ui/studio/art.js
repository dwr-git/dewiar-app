/* «Рисунки» (31.10, владелец: «закрыл открытку, хотел показать — и не знаю, где она; галерея работ есть?»). Раздел
   виден, когда установлен плагин «Художник»: работы из папки Dewiar → «Рисунки» (ядро art_list, превью — data:),
   нажали — страница работы в браузере (ws_open), «Открыть папку» — сама папка. */
const artEsc = (t) => String(t ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
function artNav() {
  const b = $('nav button[data-p="art"]'); if (!b) return;
  b.hidden = !((((S && S.plugins) || {}).on || {}).artist);
}
function artWhen(s) { const d = new Date(s); return isNaN(d) ? "" : d.toLocaleString("ru-RU", { day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" }); }
async function loadArt() {
  const g = $("#art-grid"); if (!g) return;
  let r = null;
  try { r = await core.call("art_list", { limit: 60 }); } catch (e) { g.innerHTML = `<p class="hint">${artEsc(e.message)}</p>`; return; }
  const items = (r && r.items) || [];
  g.innerHTML = items.length ? items.map((w, i) => `<button class="art-w" type="button" data-i="${i}" title="Открыть в браузере">
      <span class="art-pv">${w.preview ? `<img src="${w.preview}" alt="" loading="lazy">` : `<i aria-hidden="true">${w.kind === "animation" ? "▶" : "🎨"}</i>`}</span>
      <b>${artEsc(w.title)}</b><small>${w.kind === "animation" ? "анимация" : "рисунок"} · ${artEsc(artWhen(w.at))}</small></button>`).join("")
    : `<p class="hint">Пока пусто. Скажите Лире: «Нарисуй открытку с днём рождения для мамы» — работа появится здесь.</p>`;
  $$("#art-grid .art-w").forEach(b => b.onclick = () => core.call("ws_open", { path: items[+b.dataset.i].page }).catch(e => toast(e.message)));
}
if ($("#art-folder")) {
  $("#art-folder").onclick = () => core.call("ws_open", { path: "Рисунки" }).catch(e => toast(e.message));
  $("#art-reload").onclick = loadArt;
  document.addEventListener("click", (e) => { const b = e.target.closest && e.target.closest('nav button[data-p="art"]'); if (b) setTimeout(loadArt, 50); }, true);
  core.on("hello", () => setTimeout(artNav, 0)).on("settings", () => setTimeout(artNav, 0)).on("plugins", () => setTimeout(artNav, 0));
}
