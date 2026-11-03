/* Студия в стиле, выбранном в «Оформлении» (ui.skin) — тот же фон и материал, что у виджета.
   Фон студии — переменная --scene (studio.css): панели рисуют её под собой как «матовое стекло», поэтому слои фона
   темы берутся из assets/skins.css через невидимый образец (.lk-prev.skin-<id> — так подхватываются и текстуры)
   и пересобираются с background-attachment: fixed. Светлые темы (light) — тёмный текст и свои поля/кнопки
   (html.st-light), неоморфизм (neu) — панели из того же материала с двумя тенями (html.st-neu). «Фирменная» —
   исходный вид студии без изменений. Тема ставится ещё в <head> (тема из адреса &skin= или последняя запомненная), чтобы окно не мигало чужим фоном. */
(() => {
  const root = document.documentElement;
  const split = (s) => {                        // список слоёв через запятую — без запятых внутри скобок
    const out = []; let depth = 0, cur = "";
    for (const ch of String(s || "")) {
      if (ch === "(") depth++; else if (ch === ")") depth--;
      if (ch === "," && !depth) { out.push(cur.trim()); cur = ""; } else cur += ch;
    }
    if (cur.trim()) out.push(cur.trim());
    return out;
  };
  const VARS = { "--glass": "--sk-glass", "--glass-shadow": "--sk-shadow", "--ink": "--sk-ink", "--muted": "--sk-muted",
                 "--neu-dark": "--sk-nd", "--neu-light": "--sk-nl" };
  let cur = null;
  window.studioSkin = (id, force) => {
    const sk = window.dewiarSkin ? dewiarSkin(id) : { id: "brand" };
    if (sk.id === cur && !force) return;
    cur = sk.id;
    try { localStorage.setItem("studio_skin", sk.id); } catch (e) { }
    root.classList.toggle("st-light", !!sk.light);
    root.classList.toggle("st-neu", !!sk.neu);
    root.classList.toggle("st-skin", sk.id !== "brand");
    root.dataset.skin = sk.id;
    Object.values(VARS).forEach(v => root.style.removeProperty(v));
    if (sk.id === "brand") { root.style.removeProperty("--scene"); return; }
    const probe = document.createElement("div");
    probe.className = "lk-prev skin-" + sk.id;
    probe.style.cssText = "position:fixed;left:-9999px;top:0;width:10px;height:10px;visibility:hidden;pointer-events:none";
    (document.body || root).appendChild(probe);        // в <head> тела ещё нет — образец кладём в <html>
    const cs = getComputedStyle(probe);
    const img = split(cs.backgroundImage), pos = split(cs.backgroundPosition), size = split(cs.backgroundSize), rep = split(cs.backgroundRepeat);
    const layers = img.map((x, i) => x === "none" ? "" : `${x} ${pos[i % pos.length] || "0 0"} / ${size[i % size.length] || "auto"} ${rep[i % rep.length] || "repeat"} fixed`).filter(Boolean);
    const color = cs.backgroundColor && !/^rgba\(0, 0, 0, 0\)$|^transparent$/.test(cs.backgroundColor) ? cs.backgroundColor : "";
    if (color) { if (layers.length) layers[layers.length - 1] += " " + color; else layers.push(color); }
    if (layers.length) root.style.setProperty("--scene", layers.join(", "));
    Object.entries(VARS).forEach(([from, to]) => { const v = cs.getPropertyValue(from).trim(); if (v) root.style.setProperty(to, v); });
    probe.remove();
  };
  // тема из адреса (ui/app.py кладёт &skin= из настроек) — точнее всего; иначе последняя запомненная; иначе «Небесный»
  let early = "";
  try { early = new URLSearchParams(location.search).get("skin") || ""; } catch (e) { }
  if (!early) try { early = localStorage.getItem("studio_skin") || ""; } catch (e) { }
  studioSkin(early || "neusky");
  /* Тема из плагина (Creator, 03.11: dewiar.theme в плагине «Тема оформления»): переменные студии поверх выбранного фона —
     <style id="plg-theme"> с !important (фон темы ставится в style корня). mode light/dark — свои поля и кнопки
     (html.st-light). null — сброс: выбранный фон заново. Хранится в settings.ui.plugin_theme (ядро проверяет значения:
     только цвета и градиенты, plugin_bridge.py) и в localStorage — чтобы окно не мигало при запуске. */
  const PT_OK = /^[#\w\s.,%()+\-/]{1,700}$/, PT_BAD = /url|image|element|expression|attr|import|javascript/i;
  window.studioPluginTheme = (t) => {
    let st = document.getElementById("plg-theme");
    const vars = t && t.vars ? Object.entries(t.vars).filter(([k, v]) => /^--[a-z0-9-]+$/.test(k) && PT_OK.test(String(v)) && !PT_BAD.test(String(v))) : [];
    if (!vars.length) {
      if (st) st.remove();
      if (root.dataset.ptheme) { delete root.dataset.ptheme; window.studioSkin(root.dataset.skin || "brand", true); }
      try { localStorage.removeItem("studio_ptheme"); } catch (e) { }
      return;
    }
    if (!st) { st = document.createElement("style"); st.id = "plg-theme"; (document.head || root).appendChild(st); }
    st.textContent = `html:root, html.st-light:root, html.st-skin:root { ${vars.map(([k, v]) => `${k}: ${v} !important;`).join(" ")} }`;
    root.dataset.ptheme = t.id || "plugin";
    if (t.vars.mode === "light" || t.vars.mode === "dark") root.classList.toggle("st-light", t.vars.mode === "light");
    try { localStorage.setItem("studio_ptheme", JSON.stringify(t)); } catch (e) { }
  };
  try { const pt = JSON.parse(localStorage.getItem("studio_ptheme") || "null"); if (pt) window.studioPluginTheme(pt); } catch (e) { }
  // «Облегчённый вид» (core.js studioLite) — тоже до первого кадра: последнее решение запомнено в localStorage
  try { if (localStorage.getItem("studio_lite") === "1") root.classList.add("st-lite"); } catch (e) { }
})();
