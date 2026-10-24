/* Студия → «Что нового» после обновления (core/news.py, data/whatsnew.json — тот же текст, что на телефоне).
   При связи с ядром: есть невиданное — окно с пунктами (что это и как попробовать); «Понятно» — больше не показывать
   (news_seen). Открыть снова — «О программе» → «✨ Что нового». */
const nwEsc = (t) => String(t == null ? "" : t).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
function newsShow(r) {
  const rels = (r && r.releases) || [];
  if (!rels.length) return false;
  $("#nw-sub").textContent = `Dewiar ${rels[0].version} — вот что появилось`;
  $("#nw-list").innerHTML = rels.map(x => x.items.map(i => `<div class="nwi"><i aria-hidden="true">${nwEsc(i.icon || "✨")}</i><div><b>${nwEsc(i.title)}</b>
    <p>${nwEsc(i.text)}</p>${i.try ? `<small>${/^«/.test(i.try) ? "Скажите: " : ""}${nwEsc(i.try)}</small>` : ""}</div></div>`).join("")).join("");
  const d = $("#news-dlg"); if (!d.open) d.showModal(); d.scrollTop = 0; $("#nw-title").focus();
  return true;
}
$("#nw-ok").onclick = () => { $("#news-dlg").close(); core.call("news_seen").catch(() => {}); };
$("#news-dlg").addEventListener("cancel", () => core.call("news_seen").catch(() => {}));
$("#ab-news").onclick = () => core.call("news", { all: true }).then(r => { if (!newsShow(r)) toast("Новостей пока нет"); }).catch(e => toast(e.message));
core.on("hello", () => setTimeout(() => core.call("news").then(newsShow).catch(() => {}), 600));
/* Объявления для всех (24.10; кабинет → «Объявления», ядро — news.announcements, событие ann): окно с фото, текстом и
   ссылкой — один раз; «Понятно» — ann_seen (и строка у виджета пропадает). После «Что нового», если оба сразу. */
const MON_A = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"];
function annShow(it) {
  if (!it || $("#news-dlg").open) return false;
  const d = $("#ann-dlg"), when = new Date((it.ts || 0) * 1000), img = $("#an-img");
  img.hidden = !it.img; if (it.img) { img.src = it.img; img.onerror = () => { img.hidden = true; }; } else img.removeAttribute("src");
  $("#an-k").textContent = (it.level === "warn" ? "Предупреждение" : "Новость Dewiar") + (it.ts ? ` · ${when.getDate()} ${MON_A[when.getMonth()]}` : "");
  $("#an-k").classList.toggle("warn", it.level === "warn");
  $("#an-title").textContent = it.title || ""; $("#an-title").hidden = !it.title;
  $("#an-text").textContent = it.text || "";
  const go = $("#an-go"); go.hidden = !/^https:\/\//.test(it.link || ""); if (!go.hidden) { go.href = it.link; go.textContent = it.link_label || "Смотреть"; }
  d.dataset.id = it.id; if (!d.open) d.showModal(); $("#an-title").focus();
  return true;
}
function annCheck() { core.call("ann").then(r => annShow((r.items || []).find(i => i.id > (r.seen || 0)))).catch(() => {}); }
$("#an-ok").onclick = () => { const d = $("#ann-dlg"); d.close(); core.call("ann_seen", { id: +d.dataset.id }).catch(() => {}); };
core.on("ann", e => { if (e.item) annShow(e.item); });
core.on("hello", () => setTimeout(annCheck, 1400));
window.addEventListener("focus", () => { if (!$("#ann-dlg").open) annCheck(); });
$("#news-dlg").addEventListener("close", () => setTimeout(annCheck, 300));
