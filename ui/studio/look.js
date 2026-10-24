/* Студия → «Оформление»: тема виджета (ui.skin) и чем голос отзывается вокруг портрета (ui.voice_fx).
   Карточки — живые образцы: тема — фон, портрет и строка состояния в её цветах; анимация — настоящий облик
   (DewiarEntity) главного персонажа, который «говорит» в выбранной манере. Выбор сохраняется сразу (save), виджет
   получает событие settings и перекрашивается (hud.html applyLook); студия перекрашивается сама (studio/theme.js). */
const LOOK_FX = [
  ["bars", "Лучи", "Полоски вокруг портрета отзываются на голос"],
  ["pulse", "Пульс", "От портрета мягко расходятся круги"],
  ["wave", "Волна", "Живая линия по кругу"],
];
let lookEnts = [];
if (typeof IS_WIN !== "undefined" && IS_WIN && $("#lk-smooth")) $("#lk-smooth").style.display = "none";   // прозрачное окно — только Linux (№234)

function loadLook() {
  const ui = (S && S.ui) || {};
  const skin = window.dewiarSkin ? dewiarSkin(ui.skin).id : "brand";
  const fx = LOOK_FX.some(x => x[0] === ui.voice_fx) ? ui.voice_fx : "bars";
  const p = personas.find(x => x.id === "lira") || personas.find(x => x.id === active) || personas[0] || {};
  const img = p.avatar_url || "";
  const esc = (t) => String(t).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const skins = window.DEWIAR_SKINS || [], groups = [...new Set(skins.map(x => x.group))];
  $("#lk-skins").innerHTML = groups.map(g => `<div class="lk-group">${esc(g)}</div><div class="lk-grid">` + skins.filter(x => x.group === g).map(x => `<button class="lk ${x.id === skin ? "on" : ""}" data-skin="${x.id}">
      <div class="lk-prev skin-${x.id}" style="--persona:${esc(p.color || "#9BD4FF")}"><canvas class="pc"></canvas><span class="pl">Ваша очередь</span></div>
      <b>${esc(x.name)}</b><span>${esc(x.sub)}</span></button>`).join("") + `</div>`).join("");
  lookEnts.forEach(e => e.destroy()); lookEnts = [];
  const look = (cv, sk, fx, still) => new DewiarEntity(cv, { style: img && p.style !== "aura" ? "photo" : (p.style || "nexus"), color: p.color || "#9BD4FF",
    image: img || null, live: p.live || "", plate: false, still, tone: (window.dewiarSkin ? dewiarSkin(sk).tone : "") || "mono", fx });
  // образцы фона — тот же облик, что в виджете (живое лицо, край портрета этой темы), неподвижный
  $$("#lk-skins .lk").forEach(b => lookEnts.push(look($("canvas", b), b.dataset.skin, "bars", true)));
  $("#lk-fx").innerHTML = LOOK_FX.map(([id, name, sub]) => `<button class="lk ${id === fx ? "on" : ""}" data-fx="${id}">
      <div class="lk-prev skin-${skin}"><canvas></canvas></div><b>${name}</b><span>${sub}</span></button>`).join("");
  $$("#lk-fx .lk").forEach(b => {
    const e = look($("canvas", b), skin, b.dataset.fx, false);
    e.set({ state: "speaking", level: 0.45 });
    lookEnts.push(e);
  });
  $$("#lk-skins .lk").forEach(b => b.onclick = () => save({ ui: { skin: b.dataset.skin } }).then(() => { if (window.studioSkin) studioSkin(b.dataset.skin); loadLook(); }));
  $$("#lk-fx .lk").forEach(b => b.onclick = () => save({ ui: { voice_fx: b.dataset.fx } }).then(loadLook));
}

/* «Размер»: масштаб интерфейса (ui.zoom) и текста (ui.text) — assets/zoom.js. Текст меняется сразу, пока тянете
   ползунок; масштаб — когда отпустили (иначе страница уезжает из-под курсора). Виджет получает settings и подгоняет
   окно (hud.html → Api.set_zoom). Ctrl + / Ctrl − / Ctrl 0 и Ctrl + колесо — в любом месте студии. */
let zoomT = 0;
function zoomSave(patch, label) {
  clearTimeout(zoomT);
  zoomT = setTimeout(() => save({ ui: patch }, true).then(() => toast(label)), 350);
}
function zoomSet(k, v) {
  const ui = Object.assign({}, (S && S.ui) || {}, DewiarZoom.get(), { [k]: v });
  const cur = DewiarZoom.apply(ui);
  zoomSync(cur);
  zoomSave({ [k]: cur[k] }, (k === "zoom" ? "Масштаб " : "Текст ") + DewiarZoom.pct(cur[k]));
}
function zoomSync(cur) {
  if (!window.DewiarZoom || !$("#zm-zoom")) return;
  cur = cur || DewiarZoom.get();
  for (const k of ["zoom", "text"]) {
    const r = $("#zm-" + k);
    if (document.activeElement !== r) r.value = cur[k];
    $("#zm-" + k + "-v").textContent = DewiarZoom.pct(cur[k]);
  }
}
if (window.DewiarZoom && $("#zm")) {
  $("#zm-zoom").oninput = (e) => { $("#zm-zoom-v").textContent = DewiarZoom.pct(+e.target.value); };
  $("#zm-zoom").onchange = (e) => zoomSet("zoom", +e.target.value);
  $("#zm-text").oninput = (e) => zoomSet("text", +e.target.value);
  $$("#zm .zm-b").forEach(b => b.onclick = () => {
    const k = b.dataset.k, d = +b.dataset.d, cur = DewiarZoom.get()[k];
    zoomSet(k, k === "zoom" ? DewiarZoom.step(cur, d) : Math.round((cur + d * 0.05) * 100) / 100);
  });
  $("#zm-reset").onclick = () => { DewiarZoom.apply({ zoom: 1, text: 1 }); zoomSync(); clearTimeout(zoomT); save({ ui: { zoom: 1, text: 1 } }, true).then(() => toast("Обычный размер")); };
  DewiarZoom.keys(() => DewiarZoom.get().zoom, z => { zoomSync(); zoomSave({ zoom: z }, "Масштаб " + DewiarZoom.pct(z) + " · Ctrl 0 — обычный"); });
  window.zoomSync = zoomSync;
}
