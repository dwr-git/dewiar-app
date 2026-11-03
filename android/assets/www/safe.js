/* «Сейф» на телефоне (03.11, группа Telegram: «сейфа нет в мобильном приложении, а пароли как раз часто нужны на чужом
   компе — подглядеть со смартфона»). Тот же сейф, что «Сейф паролей» на компьютере (core/vault.py), — синхронизацией,
   вид «safe», только шифром мастер-пароля:
   • safe.json на телефоне — {meta, items: {id: {kid, c, u}}}: записи лежат так, как пришли, — шифром. Синхронизация
     (safeSnap/safeApply из syncSnapshot/syncApply в app.js) только хранит и пересылает их, ключ ей не нужен.
   • Открыть — мастер-паролем: ключ K = PBKDF2-HMAC-SHA256(пароль NFC, соль, it повторов) — как safe_derive в vault.py;
     подошёл ли — по meta.check = seal(K, "dewiar-safe-v1"). K и расшифрованные записи — только в памяти страницы (SF),
     никуда не отправляются, не пишутся на диск и не попадают в разговор с моделью и журнал.
   • Закрывается сам: при сворачивании приложения, при закрытии листа и через SAFE_IDLE без дела; на время открытого
     сейфа экран — без снимков (D.secureScreen: ни скриншота, ни картинки в «недавних»).
   • Пароль — скрыт; «Показать» — на SAFE_SHOW, «Скопировать» — в буфер с пометкой «секрет» и стиранием через SAFE_CLIP с
     (D.copySecret; без него — D.copy и стирание здесь же).
   • Добавить и изменить можно и здесь: запись шифруется ключом и уходит на компьютеры следующим обменом. */
"use strict";
const SAFE_F = "safe.json", SAFE_CHECK = "dewiar-safe-v1", SAFE_IT = 600000, SAFE_MIN = 8;
const SAFE_IDLE = 5 * 60e3, SAFE_SHOW = 15e3, SAFE_CLIP = 30;
const SF = { k: null, kid: "", list: [], q: "", view: "list", cur: "", edit: null, idle: 0, show: 0, busy: false };
const SF_IC = {
  lock: '<rect x="5" y="10.5" width="14" height="10" rx="3"/><path d="M8 10.5V8a4 4 0 0 1 8 0v2.5"/><circle cx="12" cy="15.3" r="1.3"/>',
  open: '<rect x="5" y="10.5" width="14" height="10" rx="3"/><path d="M8 10.5V8a4 4 0 0 1 7.6-1.7"/><circle cx="12" cy="15.3" r="1.3"/>',
  find: '<circle cx="11" cy="11" r="6.5"/><path d="m20 20-4.4-4.4"/>', plus: '<path d="M12 5v14M5 12h14"/>',
  back: '<path d="m14.5 6-6 6 6 6"/>', eye: '<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="2.8"/>',
  copy: '<rect x="8" y="8" width="12" height="12" rx="2.5"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/>',
  page: '<path d="M6.5 3.5h8l4 4v13h-12z"/><path d="M14.5 3.5v4h4M9.5 12h5M9.5 15.5h5"/>', go: '<path d="m9.5 6 6 6-6 6"/>',
  link: '<path d="M14 4h6v6M20 4l-9 9"/><path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>' };
const sfSvg = (k) => `<svg viewBox="0 0 24 24" aria-hidden="true">${SF_IC[k]}</svg>`;

/* ---------- хранение (шифром) и синхронизация ---------- */
function safeStore() {
  let d = null; try { d = JSON.parse(fileGet(SAFE_F) || "null"); } catch (e) { d = null; }
  return d && typeof d === "object" ? { meta: d.meta || null, items: d.items && typeof d.items === "object" ? d.items : {} } : { meta: null, items: {} };
}
const safeSave = (st) => fileSave(SAFE_F, JSON.stringify(st));
const safeOpen = () => !!SF.k;
function safeMetaOk(m) {
  try { return !!m && DC().b64d(m.salt).length === 16 && +m.it >= 1e5 && +m.it <= 1e7 && /^[0-9a-f]{8,32}$/.test(m.kid || "") && +m.at > 0 && DC().b64d(m.check).length === 48 + SAFE_CHECK.length; }
  catch (e) { return false; }
}
function safeSnap(out) {                            // из syncSnapshot: шифр как есть; t — когда правили (старая копия не перебьёт новую)
  const st = safeStore();
  if (st.meta) { out["safe:key"] = Object.assign({}, st.meta); Object.defineProperty(out["safe:key"], "t", { value: +st.meta.at || 0, enumerable: false }); }
  for (const id in st.items) { const x = st.items[id]; if (!x || !x.c) continue;
    out["safe:" + id] = { kid: x.kid, c: x.c }; Object.defineProperty(out["safe:" + id], "t", { value: +x.u || 0, enumerable: false }); }
}
function safeApply(it) {                            // из syncApply: -> false — не легло (syncRun пометит skip)
  const st = safeStore(), d = it.data || {};
  if (it.id === "key") {
    if (it.deleted || !safeMetaOk(d)) return false;
    if (st.meta && +st.meta.at > +d.at) return true;               // здесь новее (мастер-пароль сменили на телефоне)
    const changed = !st.meta || st.meta.kid !== d.kid;
    st.meta = { v: 1, salt: d.salt, it: +d.it, kid: d.kid, at: +d.at, check: d.check }; safeSave(st);
    if (changed && SF.k) { safeLock(); toast("Мастер-пароль сейфа сменили на другом устройстве — откройте сейф новым"); }
    return true;
  }
  if (!/^[0-9a-z]{6,24}$/.test(it.id)) return false;
  if (it.deleted) { delete st.items[it.id]; safeSave(st); if (SF.k) { SF.list = SF.list.filter(x => x.id !== it.id); safeRender(); } return true; }
  if (typeof d.c !== "string" || !/^[0-9a-f]{8,32}$/.test(d.kid || "")) return false;
  const mine = st.items[it.id];
  if (mine && +mine.u > +it.updated) return false;                  // здесь правили позже — своё уйдёт следующим обменом
  st.items[it.id] = { kid: d.kid, c: d.c, u: +it.updated || Date.now() }; safeSave(st);
  if (SF.k) { const x = safeDec(st.items[it.id], it.id); if (x) { SF.list = SF.list.filter(y => y.id !== it.id).concat([x]); safeRender(); } }
  return true;
}

/* ---------- ключ из мастер-пароля ---------- */
function sfPbkdfJs(pw, salt, it) {                  // запасной путь без WebCrypto: тот же PBKDF2, кусками (экран не замирает)
  return new Promise((done) => {
    const H = DC().hmacKey(pw), first = new Uint8Array(salt.length + 4); first.set(salt); first[salt.length + 3] = 1;
    let u = H(first); const t = u.slice(); let i = 1;
    const step = () => { const end = Math.min(it, i + 20000); for (; i < end; i++) { u = H(u); for (let j = 0; j < 32; j++) t[j] ^= u[j]; }
      if (i < it) setTimeout(step, 0); else done(t); };
    step();
  });
}
async function safeDerive(pw, salt, it) {
  const b = DC().utf8(String(pw).normalize("NFC"));
  try {
    if (window.crypto && crypto.subtle && window.isSecureContext !== false) {
      const key = await crypto.subtle.importKey("raw", b, "PBKDF2", false, ["deriveBits"]);
      return new Uint8Array(await crypto.subtle.deriveBits({ name: "PBKDF2", hash: "SHA-256", salt, iterations: it }, key, 256));
    }
  } catch (e) { console.warn("сейф: WebCrypto не помог — считаю сам"); }
  return sfPbkdfJs(b, salt, it);
}
function safeDec(x, id) {
  if (!SF.k || !x || x.kid !== SF.kid) return null;
  try { const o = JSON.parse(DC().fromUtf8(DC().unseal(SF.k, DC().b64d(x.c)))); return o && o.id === id && o.name ? o : null; } catch (e) { return null; }
}
async function safeUnlock(pw, pw2) {
  let st = safeStore();
  if (!st.meta && syncChan() && S.sync && S.sync.on) { try { await syncRun(false); } catch (e) { } st = safeStore(); }   // вдруг сейф уже включили на компьютере
  if (!st.meta) {                                    // сейфа ещё нет нигде — заводим здесь
    if (String(pw).length < SAFE_MIN) throw new Error(`мастер-пароль — не короче ${SAFE_MIN} знаков: им сейф откроется и на компьютере`);
    if (pw !== pw2) throw new Error("пароли не совпадают — наберите ещё раз");
    const salt = DC().randomBytes(16), k = await safeDerive(pw, salt, SAFE_IT);
    st.meta = { v: 1, salt: DC().b64e(salt), it: SAFE_IT, kid: [...DC().randomBytes(8)].map(b => b.toString(16).padStart(2, "0")).join(""), at: Date.now(),
      check: DC().b64e(DC().seal(k, DC().utf8(SAFE_CHECK))) };
    safeSave(st); syncSoon();
    return safeKeep(k, st);
  }
  const k = await safeDerive(pw, DC().b64d(st.meta.salt), +st.meta.it);
  let good = false; try { good = DC().fromUtf8(DC().unseal(k, DC().b64d(st.meta.check))) === SAFE_CHECK; } catch (e) { good = false; }
  if (!good) throw new Error("мастер-пароль не подошёл — это пароль сейфа, который вы придумали, когда включали синхронизацию сейфа");
  return safeKeep(k, st);
}
function safeKeep(k, st) {
  SF.k = k; SF.kid = st.meta.kid; SF.list = [];
  for (const id in st.items) { const x = safeDec(st.items[id], id); if (x) SF.list.push(x); }
  SF.view = "list"; SF.q = ""; safeSecure(true); safeIdle();
}
function safeLock() {
  if (SF.k) SF.k.fill(0);
  SF.k = null; SF.kid = ""; SF.list = []; SF.cur = ""; SF.edit = null; SF.view = "list"; SF.q = "";
  clearTimeout(SF.idle); clearTimeout(SF.show); safeSecure(false);
  if ($("#safe-body")) safeRender();
}
function safeSecure(on) { try { if (D.secureScreen) D.secureScreen(!!on); } catch (e) { } }
function safeIdle() { clearTimeout(SF.idle); if (SF.k) SF.idle = setTimeout(() => { safeLock(); toast("Сейф закрыт — 5 минут без дела"); }, SAFE_IDLE); }

/* ---------- запись с телефона ---------- */
const sfIso = (t) => { const d = new Date(t); return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`; };
function safePut(x) {
  const st = safeStore(), now = Date.now();
  x = Object.assign({}, x, { updated: sfIso(now), mt: now }); if (!x.created) x.created = x.updated;
  Object.keys(x).forEach(k => { if (x[k] === "" && k !== "note") delete x[k]; });
  st.items[x.id] = { kid: SF.kid, c: DC().b64e(DC().seal(SF.k, DC().utf8(JSON.stringify(x)))), u: now }; safeSave(st);
  SF.list = SF.list.filter(y => y.id !== x.id).concat([x]); syncSoon();
  return x;
}
function safeDel(id) { const st = safeStore(); delete st.items[id]; safeSave(st); SF.list = SF.list.filter(x => x.id !== id); syncSoon(); }
function safeGen(n = 16) {                           // как vlGen в студии: без похожих знаков, все четыре вида
  const L = "abcdefghijkmnpqrstuvwxyz", U = "ABCDEFGHJKLMNPQRSTUVWXYZ", Dg = "23456789", P = "!@#$%*-_+=?", all = L + U + Dg + P;
  const r = (s) => s[DC().randomBytes(4).reduce((a, b) => a * 256 + b, 0) % s.length];
  const out = [r(L), r(U), r(Dg), r(P)]; while (out.length < n) out.push(r(all));
  for (let i = out.length - 1; i > 0; i--) { const j = DC().randomBytes(4).reduce((a, b) => a * 256 + b, 0) % (i + 1); [out[i], out[j]] = [out[j], out[i]]; }
  return out.join("");
}
function safeCopy(text, what) {                      // в буфер с пометкой «секрет»; через SAFE_CLIP с — стереть
  let ok = false;
  try { ok = !!(D.copySecret && D.copySecret(text, SAFE_CLIP)); } catch (e) { ok = false; }
  if (!ok) { D.copy(text); setTimeout(() => { try { D.copy(""); } catch (e) { } }, SAFE_CLIP * 1000); }
  toast(`${what} скопирован — сотрётся из буфера через ${SAFE_CLIP} с`, 2600);
}

/* ---------- экран ---------- */
const sfNorm = (s) => String(s || "").toLowerCase().replace(/ё/g, "е").replace(/wi-?fi|вай-?\s?фа[а-я]*|вифи/g, "вайфай");
const sfHost = (u) => { const m = /^(?:https?:\/\/)?([^/\s?#]+)/i.exec(String(u || "").trim()); return m ? m[1].replace(/^www\./, "") : ""; };
const sfCol = (s) => { const c = ["#5b8def", "#e0795a", "#2fae74", "#c98a1b", "#d4588f", "#4aa3a3", "#8a6ee0", "#d25b5b"];
  return c[[...sfNorm(s)].reduce((a, ch) => a + ch.charCodeAt(0), 0) % c.length]; };
const sfMono = (s) => { const w = String(s || "?").replace(/^(пароль|пин-?код|код|логин)\s+(от|для|к|на)?\s*/i, "").trim() || String(s || "?");
  return /^(wi-?fi|вай-?\s?фа)/i.test(w) ? "Wi" : w.slice(0, 1).toUpperCase(); };
const sfDots = (x) => "•".repeat(Math.min(12, Math.max(6, String(x.value || "").length)));
const sfLines = (x) => String(x.value || "").split("\n").filter(l => l.trim()).length;

function openSafe() {
  if (kidsOn()) { showBot("В детском режиме сейф закрыт.", "err"); return; }
  SF.view = SF.k ? "list" : SF.view; safeRender(); openSheet("#sh-safe");
  setTimeout(() => { const f = $(SF.k ? "#sf-q" : "#sf-pw"); if (f && $("#sh-safe.on")) f.focus(); }, 280);
}
function safeRender() {
  const box = $("#safe-body"); if (!box) return;
  const head = $("#sf-lockbtn"); if (head) head.hidden = !SF.k;
  if (!SF.k) return sfLocked(box);
  if (SF.view === "card") return sfCard(box);
  if (SF.view === "form") return sfForm(box);
  sfList(box);
}
function sfLocked(box) {
  const st = safeStore(), fresh = !st.meta, linked = !!syncChan() && !!(S.sync && S.sync.on);
  box.innerHTML = `<div class="sf-gate">
    <div class="sf-emb" aria-hidden="true">${sfSvg("lock")}</div>
    <b>${fresh ? "Сейфа здесь ещё нет" : "Сейф закрыт"}</b>
    <p>${fresh ? (linked ? "Пароли с компьютера появятся здесь, когда там включат «Синхронизировать сейф между моими устройствами» (студия → «Сейф паролей»). Или заведите сейф прямо здесь — придумайте мастер-пароль."
        : "Сейф приходит с компьютера синхронизацией: подключите телефон в «Устройствах». Или заведите сейф прямо здесь — придумайте мастер-пароль.")
      : `Мастер-пароль сейфа — тот, что вы придумали, когда включали синхронизацию сейфа. ${Object.keys(st.items).length ? `Записей:&nbsp;${Object.keys(st.items).length}.` : ""}`}</p>
    <form id="sf-gate" autocomplete="off">
      <label class="sf-pwf"><input type="password" id="sf-pw" placeholder="${fresh ? "Придумайте мастер-пароль" : "Мастер-пароль"}" autocomplete="${fresh ? "new-password" : "current-password"}" spellcheck="false" aria-label="Мастер-пароль сейфа">
        <button type="button" class="sf-ib" id="sf-eye" aria-label="Показать мастер-пароль" aria-pressed="false">${sfSvg("eye")}</button></label>
      ${fresh ? `<label class="sf-pwf"><input type="password" id="sf-pw2" placeholder="Ещё раз" autocomplete="new-password" spellcheck="false" aria-label="Мастер-пароль ещё раз"></label>` : ""}
      <button class="btn p w" id="sf-open" type="submit">${fresh ? "Создать сейф" : "Открыть"}</button>
      <p class="res" id="sf-res" role="status"></p>
    </form>
    <p class="hint sf-fine">${fresh ? `Не короче ${SAFE_MIN} знаков. Мастер-пароль нигде не хранится и не восстанавливается — запишите его в надёжное место.`
      : "Пароли лежат на телефоне шифром и открываются только здесь. Мастер-пароль и открытые пароли никуда не отправляются — на ваши устройства ходит только шифр."}</p></div>`;
  $("#sf-eye").onclick = () => { const i = $("#sf-pw"), on = i.type === "password"; i.type = on ? "text" : "password"; if ($("#sf-pw2")) $("#sf-pw2").type = i.type; $("#sf-eye").setAttribute("aria-pressed", String(on)); };
  $("#sf-gate").onsubmit = async (e) => {
    e.preventDefault(); if (SF.busy) return;
    const r = $("#sf-res"), b = $("#sf-open"), pw = $("#sf-pw").value;
    if (!pw) { r.className = "res bad"; r.textContent = "Введите мастер-пароль"; $("#sf-pw").focus(); return; }
    SF.busy = true; b.disabled = true; b.textContent = fresh ? "Создаю…" : "Открываю…"; r.className = "res"; r.textContent = "";
    try { await safeUnlock(pw, $("#sf-pw2") ? $("#sf-pw2").value : pw); safeRender(); if (fresh) toast("Сейф создан");
      setTimeout(() => { const q = $("#sf-q"); if (q) q.focus(); }, 60); }
    catch (err) { r.className = "res bad"; r.textContent = err.message; b.disabled = false; b.textContent = fresh ? "Создать сейф" : "Открыть"; $("#sf-pw").select(); }
    finally { SF.busy = false; }
  };
}
function sfHits() {
  const q = sfNorm(SF.q.trim());
  return SF.list.filter(x => !q || [x.name, x.login, x.url, x.note].some(f => sfNorm(f).includes(q)))
    .sort((a, b) => sfNorm(a.name).localeCompare(sfNorm(b.name), "ru"));
}
function sfList(box) {
  const keep = document.activeElement && document.activeElement.id === "sf-q";
  box.innerHTML = `<div class="sf-bar"><label class="sf-find">${sfSvg("find")}<input type="search" id="sf-q" placeholder="Найти: почта, банк, вайфай…" autocomplete="off" spellcheck="false" aria-label="Поиск в сейфе" value="${esc(SF.q)}"></label>
      <button class="sf-add" id="sf-add" aria-label="Добавить запись">${sfSvg("plus")}</button></div>
    <div class="sf-list" id="sf-list"></div>
    <p class="hint sf-fine">Сейф закроется сам — при сворачивании и через 5 минут без дела.</p>`;
  sfRows();
  const q = $("#sf-q");
  q.oninput = () => { SF.q = q.value; sfRows(); safeIdle(); };
  if (keep) { q.focus(); q.setSelectionRange(q.value.length, q.value.length); }
  $("#sf-add").onclick = () => { SF.edit = { kind: "" }; SF.view = "form"; safeRender(); };
}
function sfRows() {
  const l = sfHits(), box = $("#sf-list");
  box.innerHTML = l.length ? l.map(x => {
    const page = x.kind === "page", sub = page ? `Страница · ${lnWord(sfLines(x), "строка", "строки", "строк")}` : [x.login, sfHost(x.url)].filter(Boolean).join(" · ") || "пароль";
    return `<button class="sf-item" data-id="${esc(x.id)}"><i class="sf-mono" style="--c:${sfCol(x.name)}" aria-hidden="true">${page ? sfSvg("page") : esc(sfMono(x.name))}</i>
      <span class="sf-tx"><b class="sf-name">${esc(x.name)}</b><small>${esc(sub)}</small></span>${sfSvg("go")}</button>`; }).join("")
    : `<p class="sf-none">${SF.list.length ? `Ничего не нашлось по «${esc(SF.q.trim())}»` : "В сейфе пока пусто. Нажмите «+» — или добавьте на компьютере: запись придёт сюда."}</p>`;
  $$("#sf-list .sf-item").forEach(b => b.onclick = () => { SF.cur = b.dataset.id; SF.view = "card"; safeRender(); safeIdle(); });
}
function sfCard(box) {
  const x = SF.list.find(y => y.id === SF.cur); if (!x) { SF.view = "list"; return safeRender(); }
  const page = x.kind === "page", host = sfHost(x.url), url = x.url ? (/^https?:/i.test(x.url) ? x.url : "https://" + x.url) : "";
  box.innerHTML = `<div class="sf-card" id="sf-card">
    <button class="sf-back" id="sf-back">${sfSvg("back")}Все записи</button>
    <div class="sf-ch"><i class="sf-mono big" style="--c:${sfCol(x.name)}" aria-hidden="true">${page ? sfSvg("page") : esc(sfMono(x.name))}</i><b>${esc(x.name)}</b></div>
    ${x.login ? `<div class="sf-row"><span>Логин</span><code class="sf-v">${esc(x.login)}</code><button class="sf-ib" id="sf-lcopy" aria-label="Скопировать логин">${sfSvg("copy")}</button></div>` : ""}
    ${page ? `<div class="sf-row col"><span>Текст · ${lnWord(sfLines(x), "строка", "строки", "строк")}</span><pre class="sf-page" id="sf-pv" data-shown="0">Скрыт — нажмите «Показать»</pre></div>`
      : `<div class="sf-row pass"><span>Пароль</span><code class="sf-v" id="sf-pv" data-shown="0" aria-label="пароль скрыт">${sfDots(x)}</code></div>`}
    <div class="sf-acts"><button class="btn" id="sf-show">${sfSvg("eye")}Показать</button><button class="btn p" id="sf-copy">${sfSvg("copy")}Скопировать</button></div>
    ${host ? `<div class="sf-row"><span>Сайт</span><a href="#" class="sf-v sf-url" id="sf-url">${esc(host)}${sfSvg("link")}</a></div>` : ""}
    ${x.note ? `<div class="sf-row col"><span>Заметка</span><p class="sf-note">${esc(x.note)}</p></div>` : ""}
    <div class="sf-foot"><button class="btn ghost" id="sf-edit">Изменить</button><button class="btn ghost sf-del" id="sf-del">Удалить</button></div></div>`;
  $("#sf-back").onclick = () => { SF.view = "list"; safeRender(); };
  if ($("#sf-lcopy")) $("#sf-lcopy").onclick = () => { D.copy(x.login); toast("Логин скопирован"); safeIdle(); };
  if ($("#sf-url")) $("#sf-url").onclick = (e) => { e.preventDefault(); D.openUrl(url); };
  const pv = $("#sf-pv"), hide = () => { clearTimeout(SF.show); if (!pv.isConnected) return; pv.dataset.shown = "0"; pv.textContent = page ? "Скрыт — нажмите «Показать»" : sfDots(x);
    pv.setAttribute("aria-label", page ? "текст скрыт" : "пароль скрыт"); $("#sf-show").lastChild.textContent = "Показать"; };
  $("#sf-show").onclick = () => {
    safeIdle();
    if (pv.dataset.shown === "1") return hide();
    pv.dataset.shown = "1"; pv.textContent = x.value; pv.setAttribute("aria-label", page ? "текст показан" : "пароль показан"); $("#sf-show").lastChild.textContent = "Скрыть";
    clearTimeout(SF.show); SF.show = setTimeout(hide, page ? SAFE_IDLE : SAFE_SHOW);
  };
  $("#sf-copy").onclick = () => { safeCopy(x.value, page ? "Текст" : "Пароль"); safeIdle(); };
  $("#sf-edit").onclick = () => { SF.edit = Object.assign({}, x); SF.view = "form"; safeRender(); };
  $("#sf-del").onclick = () => { if (!confirm(`Удалить «${x.name}» из сейфа? На компьютере она тоже удалится.`)) return; safeDel(x.id); SF.view = "list"; safeRender(); toast("Удалено"); };
}
function sfForm(box) {
  const x = SF.edit || { kind: "" }, page = x.kind === "page", old = !!x.id;
  box.innerHTML = `<form class="sf-form" id="sf-form" autocomplete="off">
    <button type="button" class="sf-back" id="sf-cancel">${sfSvg("back")}${old ? "Назад" : "Отмена"}</button>
    <h3>${old ? "Изменить запись" : "Новая запись"}</h3>
    ${old ? "" : `<div class="seg sf-kind" role="radiogroup" aria-label="Что добавить"><button type="button" role="radio" data-k="" aria-checked="${!page}" class="${page ? "" : "on"}">Пароль</button><button type="button" role="radio" data-k="page" aria-checked="${page}" class="${page ? "on" : ""}">Страница</button></div>`}
    <label class="f"><span>${page ? "Название" : "Что это"}</span><input id="sf-f-name" maxlength="120" value="${esc(x.name || "")}" placeholder="${page ? "Серверы, ключи API" : "Почта, вайфай дома, домофон"}"></label>
    ${page ? `<label class="f"><span>Текст</span><textarea id="sf-f-text" rows="8" spellcheck="false" placeholder="По строке на сервис, адреса, ключи…">${esc(x.value || "")}</textarea></label>`
      : `<label class="f"><span>Логин <i>необязательно</i></span><input id="sf-f-login" maxlength="160" value="${esc(x.login || "")}" autocapitalize="off" spellcheck="false"></label>
    <label class="f"><span>Пароль или код</span><span class="sf-pwrow"><input type="password" id="sf-f-pass" maxlength="500" autocomplete="new-password" spellcheck="false" placeholder="${old ? "пусто — пароль прежний" : ""}">
      <button type="button" class="sf-ib" id="sf-f-eye" aria-label="Показать пароль" aria-pressed="false">${sfSvg("eye")}</button><button type="button" class="btn sf-gen" id="sf-f-gen">Придумать</button></span></label>
    <label class="f"><span>Сайт <i>необязательно</i></span><input id="sf-f-url" maxlength="300" value="${esc(x.url || "")}" inputmode="url" autocapitalize="off" spellcheck="false"></label>
    <label class="f"><span>Заметка <i>необязательно</i></span><input id="sf-f-note" maxlength="300" value="${esc(x.note || "")}"></label>`}
    <button class="btn p w" id="sf-save" type="submit">Сохранить</button><p class="res" id="sf-f-res" role="status"></p></form>`;
  $("#sf-cancel").onclick = () => { SF.view = old ? "card" : "list"; SF.edit = null; safeRender(); };
  $$(".sf-kind [data-k]").forEach(b => b.onclick = () => { SF.edit = Object.assign({}, x, { kind: b.dataset.k, name: $("#sf-f-name").value }); safeRender(); });
  if ($("#sf-f-eye")) $("#sf-f-eye").onclick = () => { const i = $("#sf-f-pass"), on = i.type === "password"; i.type = on ? "text" : "password"; $("#sf-f-eye").setAttribute("aria-pressed", String(on)); };
  if ($("#sf-f-gen")) $("#sf-f-gen").onclick = () => { const i = $("#sf-f-pass"); i.value = safeGen(); i.type = "text"; $("#sf-f-eye").setAttribute("aria-pressed", "true"); };
  $("#sf-form").oninput = () => safeIdle();
  $("#sf-form").onsubmit = (e) => {
    e.preventDefault();
    const r = $("#sf-f-res"), name = $("#sf-f-name").value.trim(), bad = (t, el) => { r.className = "res bad"; r.textContent = t; if (el) $(el).focus(); };
    if (!name) return bad(page ? "Назовите страницу" : "Напишите, что это: «Почта», «Вайфай дома»…", "#sf-f-name");
    let y;
    if (page) { const text = $("#sf-f-text").value; if (!text.trim()) return bad("Страница пустая — впишите текст", "#sf-f-text");
      y = { id: x.id, name, value: text, note: x.note || "", kind: "page", created: x.created }; }
    else { const pass = $("#sf-f-pass").value || (old ? x.value : "");
      if (!pass) return bad("Впишите пароль — или нажмите «Придумать»", "#sf-f-pass");
      y = { id: x.id, name, value: pass, login: $("#sf-f-login").value.trim(), url: $("#sf-f-url").value.trim(), note: $("#sf-f-note").value.trim(), created: x.created }; }
    if (!y.id) y.id = [...DC().randomBytes(5)].map(b => b.toString(16).padStart(2, "0")).join("");
    safePut(y); SF.edit = null; SF.cur = y.id; SF.view = "card"; safeRender(); toast(old ? "Сохранено" : "В сейфе");
  };
  setTimeout(() => { const f = $(old ? (page ? "#sf-f-text" : "#sf-f-pass") : "#sf-f-name"); if (f) f.focus(); }, 60);
}
$("#sf-lockbtn").onclick = () => { safeLock(); toast("Сейф закрыт"); };
// закрыть сейф: свернули приложение, закрыли лист
document.addEventListener("visibilitychange", () => { if (document.hidden && SF.k) safeLock(); });
new MutationObserver(() => { if (SF.k && !$("#sh-safe").classList.contains("on")) safeLock(); }).observe($("#sh-safe"), { attributes: true, attributeFilter: ["class"] });
$("#sh-safe").addEventListener("pointerdown", () => { if (SF.k) safeIdle(); }, true);
