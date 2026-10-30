/* «Фото и файлы в «Близких» — альбомом» (0.61; план: «превью, общий альбом переписки, „переслать“ другому близкому»).
   Фото в переписке — сразу картинкой: присланное скачивается и расшифровывается само (до 8 МБ), уменьшается до 960 px и
   хранится на телефоне (climg-<id>); своё — кладётся в кэш при отправке. Нажали — фото на весь экран: «Сохранить»,
   «Переслать». «Фото и файлы» в шапке переписки — альбом: сетка фото и список файлов этой переписки (человек или группа).
   «Переслать» — выбрать близкого или группу: файл скачивается, расшифровывается и уходит заново, уже для них. */
"use strict";
const CLI_MAX = 8 * 1024 * 1024;
// картинка — по типу (и image/x-png, image/pjpeg — так пишут старые программы) или по имени (30.10: «PNG непонятно, загрузились или нет»)
const clIsImg = (f) => f && (/^image\/(x-)?(p?jpeg|jpg|png|webp|gif)/i.test(f.type || "") || /\.(jpe?g|png|webp|gif)$/i.test(f.name || ""));
const clImgCached = (id) => { try { return fileGet("climg-" + id) || ""; } catch (e) { return ""; } };
const CLI_WAIT = {};
let clWipe = null;                                  // «Очистить переписку» открытого человека (ставит clRender)
const AL_IC = {
  album: '<svg viewBox="0 0 24 24"><rect x="3.5" y="4.5" width="17" height="15" rx="3"/><circle cx="9" cy="10" r="1.8"/><path d="m4 17 5-4.5 4 3.5 3-2.5 4.5 3.8"/></svg>',
  fwd: '<svg viewBox="0 0 24 24"><path d="M13.5 5.5 20 12l-6.5 6.5M20 12H9.5A5.5 5.5 0 0 0 4 17.5V19"/></svg>',
  save: '<svg viewBox="0 0 24 24"><path d="M12 4v11M7.5 10.5 12 15l4.5-4.5M5 19.5h14"/></svg>',
  x: '<svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6 6 18"/></svg>',
  file: '<svg viewBox="0 0 24 24"><path d="M6 3.5h8.5L19 8v12.5H6z"/><path d="M14 3.5V8h5"/></svg>',
};
/* уменьшить до 960 px по длинной стороне — превью не занимает место как оригинал */
function clImgShrink(url) {
  return new Promise((ok) => {
    const im = new Image();
    im.onload = () => { try { const k = Math.min(1, 960 / Math.max(im.naturalWidth, im.naturalHeight)); if (k >= 1 && url.length < 400000) return ok(url);
      const c = document.createElement("canvas"); c.width = Math.round(im.naturalWidth * k); c.height = Math.round(im.naturalHeight * k);
      c.getContext("2d").drawImage(im, 0, 0, c.width, c.height); ok(c.toDataURL("image/jpeg", 0.82)); } catch (e) { ok(url); } };
    im.onerror = () => ok(""); im.src = url;
  });
}
const clDataUrl = (bytes, type) => `data:${type || "image/jpeg"};base64,${clStdB64(bytes)}`;
async function clImgPut(id, bytes, type) {
  const u = await clImgShrink(clDataUrl(bytes, type));
  if (u) { try { fileSave("climg-" + id, u); } catch (e) { } }
  return u;
}
async function clFileBytes(f) {                     // скачать и расшифровать
  const d = await clReq("GET", "/close/file", null, "&b64=1&id=" + encodeURIComponent(f.id));
  return DC().unseal(DC().b64d(f.key), Uint8Array.from(atob(d.b64), c => c.charCodeAt(0)));
}
function clImgGet(f) {
  const c = clImgCached(f.id); if (c) return Promise.resolve(c);
  if (!clIsImg(f) || (f.size || 0) > CLI_MAX || !f.key) return Promise.resolve("");
  return CLI_WAIT[f.id] = CLI_WAIT[f.id] || clFileBytes(f).then(b => clImgPut(f.id, b, f.type)).catch(() => "").finally(() => { delete CLI_WAIT[f.id]; });
}
/* в переписке: фото — картинкой, остальное — строкой файла (как раньше) */
function clFileHtml(f, i, j) {
  if (!clIsImg(f)) return `<button class="clf" data-i="${i}" data-j="${j}">${AL_IC.file}<span>${esc(f.name)}</span><small>${f.saved ? "сохранён" : clKb(f.size || 0)}</small></button>`;
  const c = clImgCached(f.id);
  return `<button class="clph${c ? "" : " wait"}" data-i="${i}" data-j="${j}" data-fid="${esc(f.id)}" aria-label="Фото ${esc(f.name)}">${c ? `<img src="${c}" alt="">` : ""}</button>`;
}
/* после отрисовки: догрузить фото, нажатие — на весь экран */
function clImgFill(root, h, where) {
  $$(".clph", root).forEach(b => {
    const m = h[+b.dataset.i], f = m && (m.f || [])[+b.dataset.j]; if (!f) return;
    b.onclick = (e) => { e.stopPropagation(); clView(where, m, +b.dataset.j); };
    if (!b.classList.contains("wait")) return;
    clImgGet(f).then(u => { if (!u) { b.classList.add("bad"); b.innerHTML = `${AL_IC.file}<span>${esc(f.name)}</span>`; return; }
      b.classList.remove("wait"); b.innerHTML = `<img src="${u}" alt="">`;
      const box = b.closest(".clmsgs"); if (box && box.scrollHeight - box.scrollTop - box.clientHeight < 400) box.scrollTop = box.scrollHeight; });
  });
}
/* где: { pid } — человек, { gid } — группа */
const clWhereName = (w) => w.gid ? `«${(grOf(w.gid) || {}).name || "группа"}»` : ((clLoad().people.find(p => p.pid === w.pid) || {}).name || "");
async function clSaveF(f) {
  toast("Сохраняю «" + f.name + "»…");
  const bytes = await clFileBytes(f);
  const where = D.saveDownloadB64 ? D.saveDownloadB64(f.name, f.type || "application/octet-stream", clStdB64(bytes)) : "";
  f.saved = true; clSave(); toast(where ? "Сохранено: " + where : "Сохранено", 4000);
}
/* фото на весь экран */
function clView(where, m, j) {
  const f = (m.f || [])[j]; if (!f) return;
  clViewClose();
  const v = document.createElement("div"); v.className = "clview"; v.id = "clview"; v.setAttribute("role", "dialog"); v.setAttribute("aria-label", "Фото");
  const from = m.out ? "Вы" : (m.who || clWhereName(where));
  v.innerHTML = `<div class="clv-top"><span><b>${esc(from)}</b><small>${clTime(m.ts)}</small></span><button class="ib soft" id="clv-x" aria-label="Закрыть">${AL_IC.x}</button></div>
    <div class="clv-img"><img src="${clImgCached(f.id)}" alt="${esc(f.name)}"></div>
    <div class="clv-acts"><button class="btn" id="clv-save">${AL_IC.save}Сохранить</button><button class="btn p" id="clv-fwd">${AL_IC.fwd}Переслать</button></div>`;
  document.body.appendChild(v);
  if (!clImgCached(f.id)) clImgGet(f).then(u => { const im = $("#clview img"); if (im && u) im.src = u; });
  $("#clv-x").onclick = clViewClose;
  $("#clv-save").onclick = () => clSaveF(f).catch(e => toast("Не сохранилось: " + e.message, 4000));
  $("#clv-fwd").onclick = () => clFwdPick({ t: "", f: [f] });
}
function clViewClose() { const v = $("#clview"); if (v) v.remove(); }
/* альбом переписки: сетка фото и список файлов */
function clAlbum(where) {
  const st = clLoad(), key = where.gid || where.pid, h = st.hist[key] || [];
  const ph = [], fl = [];
  h.forEach((m, i) => (m.f || []).forEach((f, j) => (clIsImg(f) ? ph : fl).push([m, i, j, f])));
  clViewClose();
  const v = document.createElement("div"); v.className = "clview clalbum"; v.id = "clview"; v.setAttribute("role", "dialog"); v.setAttribute("aria-label", "Фото и файлы");
  v.innerHTML = `<div class="clv-top"><span><b>Фото и файлы</b><small>${esc(clWhereName(where))} · ${ph.length} фото, ${fl.length} ${fl.length % 10 === 1 && fl.length % 100 !== 11 ? "файл" : fl.length % 10 >= 2 && fl.length % 10 <= 4 && (fl.length % 100 < 12 || fl.length % 100 > 14) ? "файла" : "файлов"}</small></span><button class="ib soft" id="clv-x" aria-label="Закрыть">${AL_IC.x}</button></div>
    <div class="cla-body">${ph.length ? `<div class="cla-grid">${ph.slice().reverse().map(([m, i, j, f]) => `<button class="clph${clImgCached(f.id) ? "" : " wait"}" data-i="${i}" data-j="${j}" data-fid="${esc(f.id)}" aria-label="Фото ${esc(f.name)}">${clImgCached(f.id) ? `<img src="${clImgCached(f.id)}" alt="">` : ""}</button>`).join("")}</div>` : ""}
      ${fl.length ? `<h3>Файлы</h3>${fl.slice().reverse().map(([m, i, j, f]) => `<div class="cla-f">${AL_IC.file}<span><b>${esc(f.name)}</b><small>${m.out ? "вы" : esc(String(m.who || clWhereName(where)).split(/\s+/)[0])} · ${clTime(m.ts)} · ${clKb(f.size || 0)}</small></span>${m.out ? "" : `<button class="ib soft" data-sv="${i}:${j}" aria-label="Сохранить">${AL_IC.save}</button>`}<button class="ib soft" data-fw="${i}:${j}" aria-label="Переслать">${AL_IC.fwd}</button></div>`).join("")}` : ""}
      ${!ph.length && !fl.length ? `<p class="hint" style="text-align:center;margin:40px 12px">Здесь соберутся фото и файлы этой переписки.</p>` : ""}
      ${h.length && where.pid ? `<button class="btn w cla-wipe" id="cl-wipe">Очистить переписку на этом телефоне</button>` : ""}</div>`;
  document.body.appendChild(v);
  $("#clv-x").onclick = clViewClose;
  if ($("#cl-wipe")) $("#cl-wipe").onclick = () => { clViewClose(); if (clWipe) clWipe(); };   // корзина переехала сюда из шапки (0.61: в шапке — «Фото и файлы»)
  clImgFill(v, h, where);
  const at = (s) => { const [i, j] = s.split(":").map(Number); return (h[i].f || [])[j]; };
  $$("[data-sv]", v).forEach(b => b.onclick = () => clSaveF(at(b.dataset.sv)).catch(e => toast("Не сохранилось: " + e.message, 4000)));
  $$("[data-fw]", v).forEach(b => b.onclick = () => clFwdPick({ t: "", f: [at(b.dataset.fw)] }));
}
/* «Переслать»: кому — близкие и группы */
function clFwdPick(what) {
  const st = clLoad(), old = $("#clfwd"); if (old) old.remove();
  const d = document.createElement("div"); d.className = "clfwd"; d.id = "clfwd"; d.setAttribute("role", "dialog"); d.setAttribute("aria-label", "Переслать");
  const n = (what.f || []).length;
  d.innerHTML = `<div class="clfwd-card"><div class="clv-top"><span><b>Переслать</b><small>${n ? (n === 1 ? `«${esc(what.f[0].name)}»` : `файлов: ${n}`) : "сообщение"}</small></span><button class="ib soft" id="clfwd-x" aria-label="Закрыть">${AL_IC.x}</button></div>
    <div class="clfwd-list">${(st.groups || []).map(g => `<button class="clp" data-to="${esc(g.gid)}">${typeof grStack === "function" ? grStack(g, 2) : ""}<span><b>${esc(g.name)}</b><small>группа</small></span></button>`).join("")}
      ${st.people.map(p => `<button class="clp" data-to="${esc(p.pid)}">${clAvaH(p.pid, p.name, p.face)}<span><b>${esc(p.name)}</b></span></button>`).join("")}</div></div>`;
  document.body.appendChild(d); clFacesFill(d);
  $("#clfwd-x").onclick = () => d.remove();
  d.onclick = (e) => { if (e.target === d) d.remove(); };
  $$("[data-to]", d).forEach(b => b.onclick = async () => {
    $$("[data-to]", d).forEach(x => x.disabled = true); b.classList.add("busy");
    try { const r = await clForward(b.dataset.to, what); d.remove(); clViewClose(); toast(`Переслано ${r.to || ""}`.trim()); if ($("#sh-close").classList.contains("on")) clRender(); }
    catch (e) { toast(e.message, 4000); $$("[data-to]", d).forEach(x => x.disabled = false); b.classList.remove("busy"); }
  });
}
async function clForward(to, what) {
  const files = [];
  for (const f of what.f || []) files.push({ name: f.name, type: f.type || "", bytes: await clFileBytes(f) });
  return to[0] === "g" ? grSend(to, what.t || "", files) : clSend(to, what.t || "", files);
}
