/* «Статьи сайта» на телефоне (0.93; владелец 12.11: «когда приходит черновик — возможность корректировки на телефоне, быстрее
   всего человек будет смотреть на телефоне»). Черновики пишет компьютер (студия → «Сайты» → «Статьи»), хранит сайт
   (cloud.php ?p=/sites/articles, /sites/article, /sites/article/save, /sites/article/set) — по ключу Dewiar или аккаунту того
   же человека (sites_can: одно пространство синхронизации). Здесь: лист «Статьи сайта» — «Ждут вашего „Да“» и «На сайте»;
   черновик — заголовок, описание, текст, вопрос Лиры, «Попросить Лиру поправить» (своей моделью телефона), «Сохранить»,
   «Опубликовать». Новый черновик — уведомление и плитка «Всё» с числом (проверка при открытии приложения и раз в 15 минут).
   Все тексты — словарём (phone.blog.*). */
"use strict";
const BT = (k, v) => window.t("phone.blog." + k, v);
const BLG = { list: null, cur: null, err: "", busy: false };
const blogCred = () => (typeof dwProxyCred === "function" ? dwProxyCred() : null);
async function blogCall(path, body) {
  const c = blogCred(); if (!c) throw new Error(BT("nocred"));
  const r = await http("POST", c.base + "?p=" + path, { headers: { Authorization: "Bearer " + c.token, "Content-Type": "application/json" }, body: body || {}, timeout: 30000 });
  let d = {}; try { d = JSON.parse(r.body || "{}"); } catch (e) { }
  if (r.status >= 400) throw new Error((d.error && d.error.message) || BT("http", { n: r.status }));
  return d;
}
function blogHas() { return !!(BLG.list && ((BLG.list.sites || []).length || (BLG.list.articles || []).length)); }
function blogDraftsN() { return ((BLG.list || {}).articles || []).filter(a => a.status === "draft").length; }
/* новые черновики: при открытии приложения и раз в 15 минут — уведомление один раз на черновик */
async function blogCheck(quiet) {
  if (!blogCred() || (typeof kidsOn === "function" && kidsOn())) return;
  try { BLG.list = await blogCall("/sites/articles", {}); BLG.err = ""; } catch (e) { BLG.err = e.message; return; }
  const seen = new Set(JSON.parse(prefGet("blog_seen") || "[]")), fresh = BLG.list.articles.filter(a => a.status === "draft" && !seen.has(a.id));
  if (fresh.length && !quiet) {
    try { D.notify(BT("note.t"), BT("note.x", { t: fresh[0].title })); } catch (e) { }
    toast("📝 " + BT("note.x", { t: fresh[0].title }), 6000);
  }
  BLG.list.articles.filter(a => a.status === "draft").forEach(a => seen.add(a.id));
  prefSet("blog_seen", JSON.stringify([...seen].slice(-200)));
  blogRender();
}
setTimeout(() => blogCheck(false), 9000);
setInterval(() => { if (!document.hidden) blogCheck(false); }, 15 * 60000);
document.addEventListener("visibilitychange", () => { if (!document.hidden) setTimeout(() => blogCheck(false), 2500); });

function openBlog(aid) {
  if (!$("#sh-blog")) {
    const s = document.createElement("section"); s.className = "sheet tall"; s.id = "sh-blog"; s.setAttribute("aria-labelledby", "blg-h");
    s.innerHTML = `<div class="grab"></div><h2 id="blg-h">${esc(BT("title"))}</h2><div id="blg-body"></div>`;
    document.body.appendChild(s);
  }
  BLG.cur = null; blogRender(); openSheet("#sh-blog");
  blogCheck(true).then(() => { if (aid) blogOpen(aid); });
}
function blogItem(a) {
  const when = a.status === "live" && a.pub_ts ? new Date(a.pub_ts * 1000).toLocaleDateString("ru-RU", { day: "numeric", month: "short" }) : "";
  return `<button class="blg-i ${esc(a.status)}" data-a="${a.id}"><b>${esc(a.title)}</b>${a.descr ? `<span>${esc(a.descr)}</span>` : ""}
    <small>${esc([a.site + ".dewiar.pro", when, BT("words", { n: a.words }), a.status === "live" ? BT("views", { n: a.views }) : ""].filter(Boolean).join(" · "))}</small></button>`;
}
function blogRender() {
  const box = $("#blg-body"); if (!box) return;
  if (BLG.cur) return blogEdRender();
  if (!blogCred()) { box.innerHTML = `<div class="card"><p class="hint" style="margin:0">${esc(BT("nocred"))}</p></div>`; return; }
  if (BLG.err && !BLG.list) { box.innerHTML = `<div class="card"><p class="hint" style="margin:0">${esc(BT("err", { e: BLG.err }))}</p></div>`; return; }
  if (!BLG.list) { box.innerHTML = `<p class="hint">${esc(BT("loading"))}</p>`; return; }
  const arts = BLG.list.articles || [], drafts = arts.filter(a => a.status === "draft"), live = arts.filter(a => a.status === "live");
  if (!arts.length) { box.innerHTML = `<div class="card blg-zero"><b>${esc(BT("zero.h"))}</b><p class="hint">${esc(BT("zero.p"))}</p></div>`; return; }
  box.innerHTML = `<h3 class="blg-h">${esc(BT("drafts"))}${drafts.length ? " · " + drafts.length : ""}</h3>
    ${drafts.length ? `<div class="blg-list">${drafts.map(blogItem).join("")}</div>` : `<p class="hint">${esc(BT("drafts.none"))}</p>`}
    <h3 class="blg-h">${esc(BT("live"))}${live.length ? " · " + live.length : ""}</h3>
    ${live.length ? `<div class="blg-list">${live.map(blogItem).join("")}</div>` : `<p class="hint">${esc(BT("live.none"))}</p>`}`;
  $$("#blg-body [data-a]").forEach(b => b.onclick = () => blogOpen(+b.dataset.a));
}
async function blogOpen(aid) {
  const box = $("#blg-body"); if (box) box.innerHTML = `<p class="hint">${esc(BT("loading"))}</p>`;
  try { BLG.cur = (await blogCall("/sites/article", { id: aid })).article; } catch (e) { toast(e.message, 4000); BLG.cur = null; }
  blogRender();
}
function blogEdRender() {
  const a = BLG.cur, box = $("#blg-body"), live = a.status === "live";
  box.innerHTML = `<button class="lnk blg-back" id="blg-back">← ${esc(BT("back"))}</button>
    <div class="blg-st ${esc(a.status)}">${esc(BT("st." + a.status))} · ${esc(a.site)}.dewiar.pro</div>
    ${a.ask ? `<div class="card blg-ask"><b>${esc(BT("ask"))}</b><p>${esc(a.ask)}</p><small class="hint">${esc(BT("ask.hint"))}</small></div>` : ""}
    <label class="blg-l" for="blg-t">${esc(BT("ed.title"))}</label><input id="blg-t" maxlength="200" value="${esc(a.title)}">
    <label class="blg-l" for="blg-d">${esc(BT("ed.descr"))}</label><textarea id="blg-d" rows="3" maxlength="300">${esc(a.descr || "")}</textarea>
    <label class="blg-l" for="blg-b">${esc(BT("ed.body"))}</label><textarea id="blg-b" class="blg-body">${esc(a.body || "")}</textarea>
    <small class="hint">${esc(BT("ed.md"))}</small>
    <div class="card blg-fix"><b>${esc(BT("fix"))}</b><textarea id="blg-fx" rows="2" maxlength="500" placeholder="${esc(BT("fix.ph"))}"></textarea>
      <button class="btn w" id="blg-fxb">${esc(BT("fix.go"))}</button></div>
    <div class="blg-act">${live ? `<button class="btn w" id="blg-view">${esc(BT("view"))}</button>` : ""}
      <button class="btn w" id="blg-save">${esc(BT("save"))}</button>${live ? "" : `<button class="btn p w" id="blg-pub">${esc(BT("publish"))}</button>`}
      <button class="lnk blg-del" id="blg-del">${esc(BT("del"))}</button></div>`;
  const val = () => ({ id: a.id, title: $("#blg-t").value.trim(), descr: $("#blg-d").value.trim(), body: $("#blg-b").value });
  const save = async (btn) => { btn.disabled = true; try { BLG.cur = (await blogCall("/sites/article/save", val())).article; btn.disabled = false; return true; } catch (e) { toast(e.message, 4500); btn.disabled = false; return false; } };
  $("#blg-back").onclick = () => { BLG.cur = null; blogCheck(true); blogRender(); };
  $("#blg-save").onclick = async (e) => { if (await save(e.target)) toast(BT("saved")); };
  const pb = $("#blg-pub"); if (pb) pb.onclick = async () => { if (!(await save(pb))) return; pb.disabled = true;
    try { await blogCall("/sites/article/set", { id: a.id, status: "live" }); toast(BT("published"), 4000); try { D.vibrate && D.vibrate(20); } catch (e) { } BLG.cur = null; blogCheck(true); blogRender(); }
    catch (e) { toast(e.message, 4500); pb.disabled = false; } };
  const vw = $("#blg-view"); if (vw) vw.onclick = () => D.openUrl(a.url);
  $("#blg-del").onclick = async () => { if (!(await askYes(BT("del.ask", { t: a.title })))) return;
    try { await blogCall("/sites/article/set", { id: a.id, status: "deleted" }); BLG.cur = null; blogCheck(true); blogRender(); } catch (e) { toast(e.message, 4500); } };
  $("#blg-fxb").onclick = () => blogFix();
}
/* «Попросить Лиру поправить» — моделью телефона (тот же мозг, что в разговоре): просьба своими словами, разметка и факты — как были */
async function blogFix() {
  const t = $("#blg-fx").value.trim(), b = $("#blg-fxb"); if (!t) { $("#blg-fx").focus(); return; }
  if (BLG.busy) return; BLG.busy = true; b.disabled = true; b.textContent = BT("fix.wait");
  const cur = { title: $("#blg-t").value.trim(), descr: $("#blg-d").value.trim(), body: $("#blg-b").value };
  try {
    const r = await llmStream([{ role: "system", content: BT("fix.sys") }, { role: "user", content: BT("fix.user", { ask: t, title: cur.title, descr: cur.descr, body: cur.body }) }],
      null, null, undefined, { think: false, max: 4200 });
    const raw = String(r.text || "").replace(/<think>[\s\S]*?<\/think>/g, "").replace(/^```(?:json)?\s*|\s*```\s*$/g, "").trim();
    const a = raw.indexOf("{"), z = raw.lastIndexOf("}"); const d = a >= 0 && z > a ? JSON.parse(raw.slice(a, z + 1)) : null;
    if (!d || String(d.body || "").length < 200) throw new Error(BT("fix.bad"));
    $("#blg-t").value = String(d.title || cur.title).slice(0, 200); $("#blg-d").value = String(d.descr || cur.descr).slice(0, 300); $("#blg-b").value = String(d.body);
    $("#blg-fx").value = ""; toast(BT("fix.done"), 3500);
  } catch (e) { toast(e.message || BT("fix.bad"), 4500); }
  BLG.busy = false; b.disabled = false; b.textContent = BT("fix.go");
}
async function askYes(text) { return confirm(text); }
