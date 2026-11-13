/* Студия → «Сайты» → «Статьи» (0.93). Подключается после sites.js: берёт его $, stE, stI, stAgo, SITES, stPublish. */
/* ---------- «Статьи» (0.93, sites_blog.py + sites.php) ----------
   Владелец 12.11: «Лира пишет статьи на темы клиента по плану и тематике сайта… брать из Радара… Радар — незаметно сам…
   черновик — поправить на телефоне». Не включены — приглашение с тем, что получится; включены — следующий черновик,
   «Ждут вашего „Да“», «На сайте», справа — как вести (частота, день, время, публикация, длина, о чём не писать), Радар и план
   тем. Черновик — окно правки: заголовок, описание для поиска со счётчиком, текст с подсказкой разметки, вопрос Лиры,
   источники, «Попросить Лиру поправить», «Опубликовать». Все тексты — словарём (sites.blog.*). */
const TB = (k, v) => window.t("sites.blog." + k, v);
const SB = { d: null, busy: false, ed: null };
async function sbLoad(quiet) {
  const box = $("#st-blog");
  if (!quiet) box.innerHTML = `<div class="st-loading">${stE(TB("loading"))}</div>`;
  try { SB.d = await core.call("sites_blog", { id: SITES.sid }); } catch (e) { box.innerHTML = `<div class="st-zero"><h3>${stE(TB("err"))}</h3><p>${stE(e.message)}</p></div>`; return; }
  sbRender();
}
function sbWhen(ts) {
  if (!ts) return "";
  const d = new Date(ts * 1000);
  return d.toLocaleDateString(window.dwLang && dwLang() === "en" ? "en-GB" : "ru-RU", { weekday: "long", day: "numeric", month: "long" }) + ", " + d.toLocaleTimeString(window.dwLang && dwLang() === "en" ? "en-GB" : "ru-RU", { hour: "2-digit", minute: "2-digit" });
}
function sbCard(a) {
  const meta = [a.status === "live" ? (a.pub_ts ? new Date(a.pub_ts * 1000).toLocaleDateString("ru-RU", { day: "numeric", month: "short" }) : "") : stAgo(a.updated),
    TB("words", { n: a.words }), a.status === "live" ? TB("views", { n: a.views }) : ""].filter(Boolean).join(" · ");
  return `<li class="sb-card ${stE(a.status)}"><button type="button" class="sb-open" data-a="${a.id}"><b>${stE(a.title)}</b><span>${stE(a.descr || "")}</span><small>${stE(meta)}</small></button>
    ${a.status === "live" ? `<a class="st-ib sb-ext" href="#" data-u="${stE(a.url)}" title="${stE(TB("ed.view"))}" aria-label="${stE(TB("ed.view"))}">${stI('<path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>')}</a>` : ""}</li>`;
}
function sbRender() {
  const d = SB.d, b = d.blog, box = $("#st-blog");
  const drafts = (d.articles || []).filter(a => a.status === "draft"), live = (d.articles || []).filter(a => a.status === "live");
  $("#st-nblog").textContent = drafts.length || "";
  if (!b.on) {
    box.innerHTML = `<div class="sb-hero"><div class="sb-heroart" aria-hidden="true">${stI('<path d="M6 3h9l4 4v14H6z"/><path d="M14 3v5h5M9 12h7M9 16h5"/>')}</div>
      <h3>${stE(TB("zero.h"))}</h3><p>${stE(TB("zero.p"))}</p>
      <ul class="sb-pts"><li>${stE(TB("zero.pt1"))}</li><li>${stE(TB("zero.pt2"))}</li><li>${stE(TB("zero.pt3"))}</li></ul>
      ${d.published ? `<button type="button" class="btn primary" id="sb-on">${stE(TB("zero.go"))}</button>`
        : `<p class="hint">${stE(TB("zero.pub"))}</p><button type="button" class="btn primary" id="sb-pub">${stE(TB("zero.pubbtn"))}</button>`}</div>`;
    const on = $("#sb-on"); if (on) on.onclick = () => sbSet({ on: true }, on, TB("zero.wait"));
    const pb = $("#sb-pub"); if (pb) pb.onclick = () => stPublish();
    return;
  }
  const next = (b.plan || []).find(x => !x.done);
  const rad = d.radar;
  const days = [0, 1, 2, 3, 4, 5, 6].map(i => `<option value="${i}"${b.day === i ? " selected" : ""}>${stE(TB("day" + i))}</option>`).join("");
  const hours = [8, 9, 10, 11, 12, 14, 16, 18, 20].map(h => `<option value="${h}"${b.hour === h ? " selected" : ""}>${String(h).padStart(2, "0")}:00</option>`).join("");
  const seg = (k, opts, cur) => `<div class="stabs sb-seg" role="radiogroup">${opts.map(([v, lab, dis, tip]) => `<button type="button" role="radio" aria-checked="${cur === v}" class="${cur === v ? "on" : ""}" data-k="${k}" data-v="${v}"${dis ? ` disabled title="${stE(tip)}"` : ""}>${stE(lab)}</button>`).join("")}</div>`;
  const locked = b.approved < d.auto_after, dn = drafts.length ? " · " + drafts.length : "", ln = live.length ? " · " + live.length : "";
  box.innerHTML = `<div class="sb-wrap"><div class="sb-main">
      <div class="sb-next"><div><small>${stE(TB("next", { when: sbWhen(b.next) }))}</small><b>${next ? stE(TB("next.topic", { t: next.t })) : stE(TB("next.plan"))}</b>
        ${b.err ? `<span class="sb-err">${stE(b.err)}</span>` : ""}</div><button type="button" class="btn primary" id="sb-write">${stE(TB("write"))}</button></div>
      <h4 class="st-h4">${stE(TB("drafts.h") + dn)}</h4>
      ${drafts.length ? `<ul class="sb-list">${drafts.map(sbCard).join("")}</ul>` : `<p class="sb-empty">${stE(TB("empty.drafts"))}</p>`}
      <h4 class="st-h4">${stE(TB("live.h") + ln)}</h4>
      ${live.length ? `<ul class="sb-list">${live.map(sbCard).join("")}</ul>` : `<p class="sb-empty">${stE(TB("empty.live"))}</p>`}
      <p class="hint sb-phone">${stI('<rect x="7" y="2.5" width="10" height="19" rx="2.5"/><path d="M11 18.5h2"/>')}${stE(TB("phone.hint"))}</p>
    </div><aside class="sb-side">
      <div class="sb-box"><div class="sb-boxh"><h4>${stE(TB("set.h"))}</h4><label class="tg" title="${stE(TB("set.on"))}"><input type="checkbox" id="sb-onoff" checked><i></i></label></div>
        <label class="sb-l">${stE(TB("set.freq"))}<select id="sb-freq">${[["2w", TB("f.2w")], ["week", TB("f.week")], ["2pw", TB("f.2pw")]].map(([v, l]) => `<option value="${v}"${b.freq === v ? " selected" : ""}>${stE(l)}</option>`).join("")}</select></label>
        <div class="sb-row"><label class="sb-l">${stE(TB("set.day"))}<select id="sb-day">${days}</select></label><label class="sb-l">${stE(TB("set.hour"))}<select id="sb-hour">${hours}</select></label></div>
        <label class="sb-l">${stE(TB("set.mode"))}</label>${seg("mode", [["ask", TB("m.ask")], ["auto", TB("m.auto"), locked, TB("m.locked", { n: d.auto_after, k: b.approved })]], b.mode)}
        ${locked ? `<p class="sb-note">${stE(TB("m.locked", { n: d.auto_after, k: b.approved }))}</p>` : ""}
        <label class="sb-l">${stE(TB("set.len"))}</label>${seg("len", [["short", TB("l.short")], ["mid", TB("l.mid")], ["long", TB("l.long")]], b.len)}
        <label class="sb-l" for="sb-avoid">${stE(TB("set.avoid"))}</label><textarea id="sb-avoid" rows="2" maxlength="400" placeholder="${stE(TB("set.avoid.ph"))}">${stE(b.avoid || "")}</textarea>
      </div>
      <div class="sb-box"><div class="sb-boxh"><h4>${stE(TB("radar.h"))}</h4><button type="button" class="btn small" id="sb-radar">${stE(TB("radar.go"))}</button></div>
        <p class="sb-note">${stE(rad && rad.sources ? TB("radar.t", { s: rad.sources, m: rad.items }) : TB("radar.none"))}</p></div>
      <div class="sb-box"><div class="sb-boxh"><h4>${stE(TB("plan.h"))}</h4><button type="button" class="btn small" id="sb-more">${stE(TB("plan.more"))}</button></div>
        <ol class="sb-plan">${(b.plan || []).map((x, i) => `<li class="${x.done ? "done" : ""}"><span>${stE(x.t)}</span>${x.done ? `<em>${stE(TB("plan.done"))}</em>` :
          `<button type="button" class="st-ib" data-w="${i}" title="${stE(TB("plan.write"))}" aria-label="${stE(TB("plan.write"))}">${stI('<path d="M4 20h4l10-10-4-4L4 16z"/><path d="M13.5 6.5l4 4"/>')}</button><button type="button" class="st-ib" data-x="${i}" title="${stE(TB("plan.del"))}" aria-label="${stE(TB("plan.del"))}">${stI('<path d="M6 6l12 12M18 6 6 18"/>')}</button>`}</li>`).join("")}</ol>
        <form class="sb-add" id="sb-add"><input id="sb-addt" maxlength="140" placeholder="${stE(TB("plan.add.ph"))}" aria-label="${stE(TB("plan.add.ph"))}"><button class="btn small" type="submit">${stE(TB("plan.add"))}</button></form></div>
    </aside></div>`;
  $("#sb-write").onclick = () => sbWrite("", $("#sb-write"));
  $$("#st-blog .sb-open").forEach(x => x.onclick = () => sbOpen(+x.dataset.a));
  $$("#st-blog .sb-ext").forEach(x => x.onclick = (e) => { e.preventDefault(); openExt(x.dataset.u); });
  $("#sb-onoff").onchange = (e) => sbSet({ on: e.target.checked });
  $$("#st-blog .sb-seg button").forEach(x => x.onclick = () => { if (!x.disabled) sbSet({ [x.dataset.k]: x.dataset.v }); });
  $("#sb-day").onchange = (e) => sbSet({ day: +e.target.value });
  $("#sb-freq").onchange = (e) => sbSet({ freq: e.target.value });
  $("#sb-hour").onchange = (e) => sbSet({ hour: +e.target.value });
  let avT = 0; $("#sb-avoid").oninput = (e) => { clearTimeout(avT); avT = setTimeout(() => sbSet({ avoid: e.target.value }, null, null, true), 900); };
  $("#sb-radar").onclick = () => { const n = $('nav button[data-p="insight"]'); if (n) n.click(); };
  $("#sb-more").onclick = async () => { const m = $("#sb-more"); m.disabled = true; m.textContent = TB("plan.more.wait");
    try { SB.d = await core.call("sites_blog_plan", { id: SITES.sid, more: true }); sbRender(); } catch (e) { toast(e.message, 5000); m.disabled = false; m.textContent = TB("plan.more"); } };
  $$("#st-blog [data-w]").forEach(x => x.onclick = () => sbWrite(b.plan[+x.dataset.w].t, x));
  $$("#st-blog [data-x]").forEach(x => x.onclick = () => sbSet({ plan: b.plan.filter((_, i) => i !== +x.dataset.x) }));
  $("#sb-add").onsubmit = (e) => { e.preventDefault(); const t = $("#sb-addt").value.trim(); if (t.length < 6) { $("#sb-addt").focus(); return; }
    sbSet({ plan: [{ t }].concat(b.plan) }); };
}
async function sbSet(patch, btn, wait, quiet) {
  if (btn) { btn.disabled = true; if (wait) btn.textContent = wait; }
  try { const r = await core.call("sites_blog_set", { id: SITES.sid, patch }); SB.d = Object.assign(SB.d || {}, r); if (!quiet) sbRender(); }
  catch (e) { toast(e.message, 6000); if (btn) btn.disabled = false; sbLoad(true); }
}
async function sbWrite(topic, btn) {
  if (SB.busy) return;
  SB.busy = true; const was = btn.innerHTML; btn.disabled = true; btn.textContent = TB("writing");
  try { const r = await core.call("sites_blog_write", { id: SITES.sid, topic }); SB.d = r; sbRender(); toast(TB("written"), 4000); if (r.written) sbOpen(r.written.id); }
  catch (e) { toast(e.message, 6000); btn.disabled = false; btn.innerHTML = was; }
  SB.busy = false;
}
async function sbOpen(aid) {
  const m = $("#sb-ed"), box = $("#sb-edbox");
  box.innerHTML = `<div class="st-loading">${stE(TB("loading"))}</div>`; m.hidden = false;
  let a; try { a = (await core.call("sites_blog_article", { id: SITES.sid, aid })).article; } catch (e) { m.hidden = true; toast(e.message, 5000); return; }
  SB.ed = a; sbEd();
}
function sbEd() {
  const a = SB.ed, box = $("#sb-edbox"), live = a.status === "live";
  const dl = (a.descr || "").length;
  box.innerHTML = `<div class="sb-edh"><span class="sb-st ${stE(a.status)}">${stE(TB("st." + a.status))}</span><h3 id="sb-edh">${stE(a.title)}</h3>
      <button class="st-ib" type="button" id="sb-x" aria-label="${stE(TB("ed.close"))}">${stI('<path d="M6 6l12 12M18 6 6 18"/>')}</button></div>
    <div class="sb-edgrid"><div class="sb-edmain">
      <label class="sb-l" for="sb-t">${stE(TB("ed.title"))}</label><input id="sb-t" maxlength="200" value="${stE(a.title)}">
      <label class="sb-l" for="sb-d">${stE(TB("ed.descr"))} <em id="sb-dn" class="${dl >= 120 && dl <= 160 ? "ok" : ""}">${stE(TB("ed.descr.hint", { n: dl }))}</em></label>
      <textarea id="sb-d" rows="2" maxlength="300">${stE(a.descr || "")}</textarea>
      <label class="sb-l" for="sb-b">${stE(TB("ed.body"))} <em>${stE(TB("ed.md"))}</em></label><textarea id="sb-b" class="sb-body" spellcheck="true">${stE(a.body || "")}</textarea>
    </div><aside class="sb-edside">
      ${a.ask ? `<div class="sb-ask"><b>${stE(TB("ed.ask"))}</b><p>${stE(a.ask)}</p><small>${stE(TB("ed.ask.hint"))}</small></div>` : ""}
      <div class="sb-fix"><b>${stE(TB("ed.fix"))}</b><textarea id="sb-fixt" rows="3" maxlength="500" placeholder="${stE(TB("ed.fix.ph"))}"></textarea><button type="button" class="btn small" id="sb-fixb">${stE(TB("ed.fix.go"))}</button></div>
      ${(a.refs || []).length ? `<div class="sb-refs"><b>${stE(TB("ed.refs"))}</b><ul>${a.refs.map(r => `<li><a href="#" data-u="${stE(r.url)}">${stE(r.title || r.url)}</a></li>`).join("")}</ul></div>` : ""}
    </aside></div>
    <div class="sb-edact">${live ? `<button type="button" class="btn" id="sb-view">${stE(TB("ed.view"))}</button><button type="button" class="btn" id="sb-hide">${stE(TB("ed.hide"))}</button>` : ""}
      <button type="button" class="btn ghost sb-del" id="sb-del">${stE(TB("ed.del"))}</button><span class="st-sp"></span>
      <button type="button" class="btn" id="sb-save">${stE(TB("ed.save"))}</button>${live ? "" : `<button type="button" class="btn primary" id="sb-pub">${stE(TB("ed.publish"))}</button>`}</div>`;
  const val = () => ({ title: $("#sb-t").value.trim(), descr: $("#sb-d").value.trim(), body: $("#sb-b").value });
  $("#sb-d").oninput = (e) => { const n = e.target.value.length, el = $("#sb-dn"); el.textContent = TB("ed.descr.hint", { n }); el.className = n >= 120 && n <= 160 ? "ok" : ""; };
  $("#sb-x").onclick = sbClose;
  const save = async (btn) => { btn.disabled = true; try { SB.ed = (await core.call("sites_blog_save", Object.assign({ id: SITES.sid, aid: a.id }, val()))).article; return true; }
    catch (e) { toast(e.message, 5000); btn.disabled = false; return false; } };
  $("#sb-save").onclick = async (e) => { if (await save(e.target)) { toast(TB("ed.saved")); sbEd(); sbLoad(true); } };
  const pb = $("#sb-pub"); if (pb) pb.onclick = async () => { if (!(await save(pb))) return;
    try { await core.call("sites_blog_status", { id: SITES.sid, aid: a.id, status: "live" }); toast(TB("ed.published"), 4000); sbClose(); sbLoad(true); } catch (e) { toast(e.message, 5000); pb.disabled = false; } };
  const hd = $("#sb-hide"); if (hd) hd.onclick = async () => { try { await core.call("sites_blog_status", { id: SITES.sid, aid: a.id, status: "hidden" }); toast(TB("ed.hidden")); sbClose(); sbLoad(true); } catch (e) { toast(e.message, 5000); } };
  const vw = $("#sb-view"); if (vw) vw.onclick = () => openExt(a.url);
  $("#sb-del").onclick = async () => { if (!(await ask(TB("ed.del.ask", { t: a.title }), { ok: TB("ed.del") }))) return;
    try { await core.call("sites_blog_status", { id: SITES.sid, aid: a.id, status: "deleted" }); sbClose(); sbLoad(true); } catch (e) { toast(e.message, 5000); } };
  $("#sb-fixb").onclick = async () => { const t = $("#sb-fixt").value.trim(), b = $("#sb-fixb"); if (!t) { $("#sb-fixt").focus(); return; }
    if (!(await save(b))) return; b.textContent = TB("ed.fixing");
    try { SB.ed = (await core.call("sites_blog_fix", { id: SITES.sid, aid: a.id, text: t })).article; sbEd(); } catch (e) { toast(e.message, 6000); b.disabled = false; b.textContent = TB("ed.fix.go"); } };
  $$("#sb-edbox .sb-refs [data-u]").forEach(x => x.onclick = (e) => { e.preventDefault(); openExt(x.dataset.u); });
  setTimeout(() => $("#sb-b").focus({ preventScroll: true }), 30);
}
function sbClose() { $("#sb-ed").hidden = true; SB.ed = null; }
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && $("#sb-ed") && !$("#sb-ed").hidden) sbClose(); });


/* «Продвижение» → «Подтвердить»: Яндекс Вебмастер и Google Search Console — метатегом. Вставить можно весь тег или код;
   сохраняем, сайт обновляется сам — и в Вебмастере остаётся нажать «Проверить». */
function sbVerify() {
  const m = $("#sb-ed"), box = $("#sb-edbox"), seo = (SITES.cur && SITES.cur.seo) || {}, p = (SITES.cur && SITES.cur.published) || {};
  box.innerHTML = `<div class="sb-edh"><h3 id="sb-edh">${stE(TB("vf.h"))}</h3><button class="st-ib" type="button" id="sb-x" aria-label="${stE(TB("ed.close"))}">${stI('<path d="M6 6l12 12M18 6 6 18"/>')}</button></div>
    <p class="hint">${stE(TB("vf.p"))}</p>
    <ol class="sb-steps"><li>${stE(TB("vf.s1"))}</li><li>${stE(TB("vf.s2", { url: p.url || "" }))}</li><li>${stE(TB("vf.s3"))}</li><li>${stE(TB("vf.s4"))}</li></ol>
    <label class="sb-l" for="sb-vy">${stE(TB("vf.y"))}</label><input id="sb-vy" maxlength="300" value="${stE(seo.verify_yandex || "")}" placeholder='<meta name="yandex-verification" content="…">'>
    <label class="sb-l" for="sb-vg">${stE(TB("vf.g"))}</label><input id="sb-vg" maxlength="300" value="${stE(seo.verify_google || "")}" placeholder='<meta name="google-site-verification" content="…">'>
    <p class="sb-note">${stE(TB("vf.map", { url: (p.url || "") + "/sitemap.xml" }))}</p>
    <div class="sb-edact"><a class="btn" href="#" data-u="https://webmaster.yandex.ru/sites/add/">${stE(TB("vf.oy"))}</a><a class="btn" href="#" data-u="https://search.google.com/search-console/welcome">${stE(TB("vf.og"))}</a>
      <span class="st-sp"></span><button type="button" class="btn primary" id="sb-vsave">${stE(TB("vf.save"))}</button></div>`;
  m.hidden = false;
  $("#sb-x").onclick = sbClose;
  $$("#sb-edbox [data-u]").forEach(x => x.onclick = (e) => { e.preventDefault(); openExt(x.dataset.u); });
  $("#sb-vsave").onclick = async () => {
    const btn = $("#sb-vsave"); btn.disabled = true; btn.textContent = TB("vf.saving");
    try {
      let r = await core.call("sites_apply", { id: SITES.sid, ops: [{ op: "site", verify_yandex: $("#sb-vy").value, verify_google: $("#sb-vg").value }], label: TB("vf.h") });
      if (p.name) r = await core.call("sites_publish", { id: SITES.sid, name: p.name });
      SITES.cur = r.site || SITES.cur; toast(TB("vf.done"), 6000); sbClose(); if (typeof stSeo === "function") stSeo();
    } catch (e) { toast(e.message, 6000); btn.disabled = false; btn.textContent = TB("vf.save"); }
  };
}
