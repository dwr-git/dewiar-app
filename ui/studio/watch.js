/* Студия → «Дозор» (0.58; владелец 28.10: «смотрела на экран раз в 10 минут по заданию и, если выполнено, сообщала мне на
   компе и на телефоне… режим может получиться действительно крутым — описать везде и показать»).
   Сверху — что это и фразы-примеры (нажать — форма заполнена); «Новый дозор»: экран, папка или страница, чего ждать,
   как часто и сколько; справа — «Сейчас в дозоре» (последняя проверка, «Стоп») и «Недавно» (чем кончилось).
   Ядро: watch_get, watch_add {kind, what, every_minutes, hours, folder, pattern, url}, watch_stop {id};
   событие «watch» (то же, что watch_get) — список освежается сам. */
const WT = { st: null, kind: "screen" };
const WT_KIND = { screen: "экран", file: "папка", page: "страница" };
const WT_ST = { done: ["Готово", "ok"], stopped: ["Остановлен", ""], expired: ["Срок вышел", ""], failed: ["Не смог", "bad"] };
const wtT = (ts) => ts ? new Date(ts * 1000).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" }) : "";
const wtEsc = (t) => typeof escH === "function" ? escH(t) : String(t == null ? "" : t).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

async function loadWatch() {
  try { WT.st = await core.call("watch_get"); } catch (e) { return; }
  wtRender();
}
function wtKind(k) {
  WT.kind = k;
  $$("#p-watch .wt-kind [data-kind]").forEach(b => { const on = b.dataset.kind === k; b.classList.toggle("on", on); b.setAttribute("aria-checked", on); });
  $$("#p-watch [data-for]").forEach(el => { el.hidden = !el.dataset.for.split(" ").includes(k); });
  $("#wt-what-t").textContent = k === "page" ? "Какое слово ждать на странице (пусто — любое изменение)" : "Чего ждать на экране";
  $("#wt-what").placeholder = k === "page" ? "Одобрено" : "Claude закончил и написал ответ";
  $("#wt-safe").hidden = k !== "screen";
  if (k === "page" && $("#wt-every").value === "5") $("#wt-every").value = "10";
}
function wtRender() {
  const st = WT.st || { items: [] }, act = st.items.filter(x => x.status === "active"), old = st.items.filter(x => x.status !== "active").slice(0, 8);
  const dot = $("#wt-dot"); if (dot) dot.classList.toggle("on", act.length > 0);
  const every = (x) => x.kind === "file" ? "слежу постоянно" : `раз в ${Math.max(1, Math.round(x.every / 60))} мин`;
  $("#wt-act").innerHTML = act.length ? act.map(x => `<div class="wt-item on" data-id="${wtEsc(x.id)}">
      <i class="wt-pulse" aria-hidden="true"></i><div><b>${wtEsc(x.title)}</b>
      <small>${WT_KIND[x.kind]} · ${every(x)} · до ${wtT(x.until)}</small>
      <small class="wt-last">${x.last ? `смотрела в ${wtT(x.last)}: ${wtEsc(x.note || "")}` : "сейчас посмотрю…"}</small></div>
      <button class="btn small" type="button" data-stop="${wtEsc(x.id)}">Стоп</button></div>`).join("")
    : `<p class="hint" style="margin:0">Сейчас Лира ничего не ждёт. Скажите ей: «Лира, скажи, когда Claude ответит» — или начните дозор слева.</p>`;
  $("#wt-old").innerHTML = old.length ? old.map(x => { const s = WT_ST[x.status] || [x.status, ""];
    return `<div class="wt-item ${s[1]}"><i class="wt-mark" aria-hidden="true"></i><div><b>${wtEsc(x.title)}</b><small>${s[0]}${x.done_at ? " в " + wtT(x.done_at) : ""}${x.result ? " — " + wtEsc(x.result) : ""}</small></div></div>`; }).join("")
    : `<p class="hint" style="margin:0">Здесь будет, чем кончились дозоры.</p>`;
  $$("#wt-act [data-stop]").forEach(b => b.onclick = async () => { try { WT.st = await core.call("watch_stop", { id: b.dataset.stop }); wtRender(); toast("Дозор остановлен"); } catch (e) { toast(e.message); } });
}
$$("#p-watch .wt-kind [data-kind]").forEach(b => b.onclick = () => wtKind(b.dataset.kind));
$$("#wt-try button").forEach(b => b.onclick = () => {
  wtKind(b.dataset.k);
  if (b.dataset.w) $("#wt-what").value = b.dataset.w;
  if (b.dataset.f) $("#wt-folder").value = b.dataset.f;
  (b.dataset.k === "page" ? $("#wt-url") : $("#wt-go")).focus();
});
$("#wt-go").onclick = async () => {
  const k = WT.kind, r = $("#wt-res");
  const a = { kind: k, what: $("#wt-what").value.trim(), hours: +$("#wt-hours").value };
  if (k !== "file") a.every_minutes = +$("#wt-every").value;
  if (k === "file") { a.folder = $("#wt-folder").value.trim() || "Загрузки"; a.pattern = $("#wt-pattern").value.trim() || "*"; }
  if (k === "page") a.url = $("#wt-url").value.trim();
  if (k === "screen" && a.what.length < 3) { r.className = "res bad"; r.textContent = "Напишите, чего ждать — например: «Claude закончил и написал ответ»"; $("#wt-what").focus(); return; }
  r.className = "res"; r.textContent = "…";
  try { WT.st = await core.call("watch_add", a); wtRender(); r.className = "res ok"; r.textContent = "Дозор начат — скажу, когда готово";
    setTimeout(() => { if (r.textContent.startsWith("Дозор начат")) r.textContent = ""; }, 4000); }
  catch (e) { r.className = "res bad"; r.textContent = e.message; }
};
core.on("watch", (st) => { WT.st = st; if ($("#p-watch").classList.contains("cur")) wtRender(); else { const d = $("#wt-dot"); if (d) d.classList.toggle("on", (st.items || []).some(x => x.status === "active")); } });
core.on("watch_done", (e) => toast(`👁 Готово: ${e.title}${e.note ? " — " + e.note : ""}`, 8000));
document.addEventListener("click", (e) => { if (e.target.closest && e.target.closest('nav button[data-p="watch"]')) setTimeout(loadWatch, 0); });
wtKind("screen");
