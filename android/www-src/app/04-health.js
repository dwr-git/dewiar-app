//@ Телефон и веб-версия, часть 04: «Здоровье» и жалобы.
//@ Собирается в android/assets/www/app.js (tools/app_join.py) — порядок частей = порядок исполнения; шапка «//@» в app.js не попадает.
/* ---------- «Здоровье» и жалобы (сервер — cloud.php, вкладка «Здоровье»; компьютер — core/health.py, формат общий) ----------
   Пульс (/pulse): через минуту после запуска и раз в 6 часов — случайный номер установки (S.dev), версия, Android, модель
   телефона, где думает (dewiar | local | server | cloud | none — без адресов), запуски (за сколько секунд готов), ответы,
   удачные и неудачные запросы к мозгу, сбои по подписям. Без разговоров, файлов и ключей; выключается S.pulse.
   Счётчики — pref "health" до отправки. Жалоба: слова, снимок экрана приложения (D.snapshot() — снимается, когда открывают
   настройки: каким был экран до них), подпись S.who; номер и секрет — в S.complaints, раз в 6 часов спрашиваем ответ
   (/report/status) и, когда ответили или исправили, — уведомление со спасибо. Голосом: «сообщи об ошибке: …» (quick). */
const H_T0 = Date.now() - (window.performance && performance.now ? performance.now() : 0);
let bugSnap = null, thanksCache = null, bugWait = 0, bugPick = "";   // bugPick — фото или скриншот из галереи к жалобе
function hLoad() { try { return JSON.parse(prefGet("health") || "{}") || {}; } catch (e) { return {}; } }
function hSave(h) { try { prefSet("health", JSON.stringify(h)); } catch (e) { } }
function hCount(k, n = 1) { const h = hLoad(); h[k] = (h[k] || 0) + n; hSave(h); }
// «Чем пользуются» (13.11, владелец: «понять, чем пользуются и чем нет»): листы sh:имя и умения pt:имя — только имена и числа
function hUse(k) { if (!/^(sh|pt):[a-z][a-z0-9_]{0,40}$/.test(k)) return; const h = hLoad(); h.uses = h.uses || {}; if (!(k in h.uses) && Object.keys(h.uses).length >= 150) return; h.uses[k] = (h.uses[k] || 0) + 1; hSave(h); }
/* «Голос без пауз» (04.11): подсказка в токенах и сколько из неё сервер взял из кэша начала запроса — как llm.last_usage */
function usageOf(o) {
  const t = o.timings;                                         // llama.cpp: prompt_n — прочитано заново, cache_n — из кэша
  if (t && t.cache_n != null && t.prompt_n != null) return { prompt: (+t.prompt_n || 0) + (+t.cache_n || 0), cached: +t.cache_n || 0 };
  const u = o.usage;
  if (u && u.prompt_tokens != null) {                          // OpenAI/vLLM/OpenRouter; Kimi — cached_tokens наверху; DeepSeek — prompt_cache_hit_tokens
    let c = (u.prompt_tokens_details || {}).cached_tokens;
    if (c == null) c = u.cached_tokens != null ? u.cached_tokens : u.prompt_cache_hit_tokens;
    return { prompt: +u.prompt_tokens || 0, cached: c != null ? +c : null };
  }
  if (o.done && o.prompt_eval_count != null) return { prompt: +o.prompt_eval_count || 0, cached: null };   // Ollama
  return null;
}
function usageLine(u, sec) {
  const n = (x) => String(Math.round(x)).replace(/\B(?=(\d{3})+(?!\d))/g, " ");
  return `⏱ модель: ${sec.toFixed(1)} с, подсказка ${n(u.prompt)} ток.` + (u.cached != null ? `, из кэша ${n(u.cached)}` + (u.prompt ? ` (${Math.round(100 * u.cached / u.prompt)}%)` : "") : ", сколько из кэша — сервер не сообщает");
}
/* в пульс — суммы (как health_cache на компьютере): n — запросов, k — из них с ответом про кэш, ptok/cached — токены по k */
function hCache(u) {
  const h = hLoad(), pc = h.pcache = h.pcache || {};
  pc.n = (pc.n || 0) + 1; pc.ptok_all = (pc.ptok_all || 0) + u.prompt;
  if (u.cached != null) {
    pc.k = (pc.k || 0) + 1; pc.ptok = (pc.ptok || 0) + u.prompt; pc.cached = (pc.cached || 0) + u.cached;
    const b = (pc.by = pc.by || {})[brainKind()] = (pc.by || {})[brainKind()] || [0, 0, 0]; b[0]++; b[1] += u.prompt; b[2] += u.cached;
  }
  hSave(h);
}
/* Почему не ответил мозг — «где думает : почему» (пакет 20.10: «неудачных 10,7 %» — а каких?). Как why_kind в core/health.py. */
const WHY_RX = [["timeout", /не ответил вовремя|timed? ?out|таймаут|отменено|abort/i], ["connect", /подключ|connect|resolve|сеть|network|failed to fetch|refused/i],
  ["context", /окна контекста|context/i], ["busy", /много людей|занят|429|503|busy/i], ["balance", /заряд|талер|402|quota/i],
  ["key", /ключ|401|403|forbidden|не пускает/i], ["rejected", /отклонил|400|422|413|тариф/i], ["server", /\b5\d\d\b|недоступн/i]];
function hWhy(err) {
  const k = brainKind() + ":" + ((WHY_RX.find(([, rx]) => rx.test(String(err || ""))) || ["other"])[0]);
  const h = hLoad(); h.net_why = h.net_why || {};
  if (h.net_why[k] || Object.keys(h.net_why).length < 40) h.net_why[k] = (h.net_why[k] || 0) + 1;
  hSave(h);
}
/* Голос по всем телефонам (отзыв 13.10: «у многих голосом не выходит, ответы только текстом», а объяснить не могут):
   счётчики слуха и голоса уходят в пульс (voice) — в «Здоровье» видно, у скольких и почему молчит. Только числа. */
function vCount(k, n = 1) { const h = hLoad(); h.voice = h.voice || {}; h.voice[k] = (h.voice[k] || 0) + n; hSave(h); }
function hClean(t) {
  return String(t || "").replace(/(Bearer\s+)[\w.-]+/g, "$1***").replace(/\bdw-[a-z0-9-]{6,}/gi, "dw-***").replace(/(:\/\/[^/\s:@]+:)[^@\s/]+@/g, "$1***@")
    .replace(/\b[\w.+-]+@[\w-]+\.[\w.]+\b/g, "<почта>").replace(/\b(?!127\.0\.0\.1\b)\d{1,3}(?:\.\d{1,3}){3}\b/g, "<ip>").trim().slice(0, 300);
}
function hProblem(text) {
  text = hClean(text); if (!text) return;
  const sig = text.replace(/https?:\/\/\S+/g, "URL").replace(/\d+/g, "#").slice(0, 160);
  const h = hLoad(); h.problems = h.problems || {};
  if (!h.problems[sig] && Object.keys(h.problems).length >= 30) return;
  const p = h.problems[sig] = h.problems[sig] || { text, n: 0 }; p.n++; p.text = text; h.errors = (h.errors || 0) + 1; hSave(h);
}
/* «Первая минута» (19.11, владелец: «бережно улучшать»; воронка: 289 из 878 новых телефонов закрыли приложение за 10 минут,
   ни о чём не спросив, — и после 1.0.26 доля та же, 33 %). Что человек успел за первый запуск — только события и секунды от
   старта (без текстов): приветствие какого вида, подсказки, нажал подсказку / микрофон / написал, разрешил ли микрофон,
   подключился ли мозг сам, пришёл ли ответ, открыл ли настройки, когда ушёл. Окно — первые 10 минут первого запуска;
   ушёл раньше минуты — пульс уходит сразу (иначе такие запуски не видны вовсе). В пульс — first. */
const FS_ON = !prefGet("h_seen") && !prefGet("fs_done");
const FS_KEYS = ["greet", "tries", "try", "ask", "mic", "mic_ok", "mic_no", "type", "settings", "brain", "brain_no", "answer", "fail", "hide"];
let fsSent = false;
function fsSec() { return Math.round((Date.now() - H_T0) / 1000); }
function fsMark(e, kind) {
  if (!FS_ON || !FS_KEYS.includes(e) || fsSec() > 600) return;
  const h = hLoad(), f = h.first = h.first || {};
  if (!(e in f)) { f[e] = fsSec(); if (kind && /^[a-z]{2,10}$/.test(kind)) f.kind = kind; hSave(h); }
}
if (FS_ON) document.addEventListener("visibilitychange", () => {
  if (!document.hidden || fsSec() > 600) return;
  fsMark("hide");
  if (!fsSent && fsSec() < 70) { fsSent = true; pulseSend().catch(() => {}); }   // ушёл раньше первого пульса (через минуту)
});
function hReady() {                                       // приложение готово слушать — запуск записан (для «Запуск» в «Здоровье»)
  const h = hLoad(), first = !prefGet("h_seen");
  h.starts = (h.starts || []).slice(-9).concat([{ ts: Math.round(Date.now() / 1000), ready_s: Math.round((Date.now() - H_T0) / 100) / 10, cpu: 0, first }]);
  hSave(h); if (first) prefSet("h_seen", "1");
}
function devId() { if (!/^ph-[0-9a-f]{16}$/.test(S.dev || "")) { S.dev = "ph-" + Array.from({ length: 16 }, () => "0123456789abcdef"[Math.random() * 16 | 0]).join(""); saveS(); } return S.dev; }
function brainKind() {
  if (S.llm.cloud) return "dewiar";
  if (!S.llm.base_url) return loggedIn() ? "dewiar" : "none";
  const host = String(S.llm.base_url).replace(/^\w+:\/\//, "").split(/[/:]/)[0].toLowerCase();
  if (/dewiar/.test(host)) return "dewiar";
  if (/^(localhost|127\.|0\.0\.0\.0)/.test(host)) return "local";
  if (/^(10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.)/.test(host) || /\.local$/.test(host) || !host.includes(".")) return "server";
  return "cloud";
}
const healthBase = () => ((syncCred() || {}).base || CLOUD_URL).split("?")[0];
async function pulseSend() {
  if (S.pulse === false) return false;
  let info = {}; try { info = JSON.parse(D.info() || "{}"); } catch (e) { }
  const h = hLoad();
  const body = { dev: devId(), app: "phone", version: info.version || "", os: "Android " + (info.android || ""), hw: { device: info.device || "", webview: webviewVer().replace(/^ · /, "") },
    brain: brainKind(), uptime_h: Math.round((Date.now() - H_T0) / 36e4) / 10, starts: h.starts || [], turns: h.turns || 0, net_ok: h.net_ok || 0,
    net_fail: h.net_fail || 0, net_why: h.net_why || {}, errors: h.errors || 0, rude: h.rude || 0, refused: h.refused || 0, problems: Object.entries(h.problems || {}).map(([sig, p]) => ({ sig, text: p.text, n: p.n })),
    voice: Object.assign({}, h.voice || {}, { tts_engine: S.tts.engine || "", tts_ready: ttsOk() ? 1 : 0, text_mode: S.textMode ? 1 : 0,
      stt_engine: S.stt.engine || "", recognizer: D.recognizer() ? 1 : 0, vol: (() => { try { return D.volume("get", 0); } catch (e) { return -1; } })() }),
    pcache: h.pcache || {}, uses: h.uses || {}, first: h.first || undefined };
  let r; try { r = await http("POST", healthBase() + "?p=/pulse", { headers: { "Content-Type": "application/json" }, body, timeout: 20000 }); }
  catch (e) { console.log("💓 пульс не ушёл: " + (e.message || e)); return false; }
  if (r.status >= 400) return false;
  const now = hLoad();                                        // вычесть отправленное: пока шёл запрос, могло прибавиться
  for (const k of ["turns", "net_ok", "net_fail", "errors", "rude", "refused"]) now[k] = Math.max(0, (now[k] || 0) - (body[k] || 0));
  for (const k of Object.keys(body.net_why)) if (now.net_why && now.net_why[k]) { now.net_why[k] -= body.net_why[k]; if (now.net_why[k] <= 0) delete now.net_why[k]; }
  if (now.voice) { for (const k of Object.keys(body.voice)) if (typeof now.voice[k] === "number" && !/^(tts_ready|text_mode|recognizer|vol)$/.test(k)) now.voice[k] = Math.max(0, now.voice[k] - (body.voice[k] || 0)); }
  for (const p of body.problems) if (now.problems && now.problems[p.sig]) { now.problems[p.sig].n -= p.n; if (now.problems[p.sig].n <= 0) delete now.problems[p.sig]; }
  now.starts = (now.starts || []).slice(body.starts.length);
  for (const [k, n] of Object.entries(body.uses)) if (now.uses && now.uses[k]) { now.uses[k] -= n; if (now.uses[k] <= 0) delete now.uses[k]; }
  if (now.pcache) {                                           // кэш подсказки: вычесть отправленное
    for (const k of ["n", "k", "ptok_all", "ptok", "cached"]) if (now.pcache[k]) now.pcache[k] = Math.max(0, now.pcache[k] - (body.pcache[k] || 0));
    for (const [kind, v] of Object.entries(body.pcache.by || {})) { const b = (now.pcache.by || {})[kind]; if (b) { for (let i = 0; i < 3; i++) b[i] = Math.max(0, b[i] - v[i]); if (!b[0]) delete now.pcache.by[kind]; } }
    if (!now.pcache.n) delete now.pcache;
  }
  if (now.first && fsSec() > 600) { delete now.first; prefSet("fs_done", "1"); }   // окно первой минуты кончилось и ушло — больше не шлём
  hSave(now); prefSet("pulse_at", String(Date.now()));
  console.log(`💓 Пульс отправлен: запусков ${body.starts.length}, ответов ${body.turns}, сбоев ${body.problems.length}`);
  try { const d = JSON.parse(r.body || "{}"); if (d.exam && typeof examOffer === "function") examOffer(d.exam); } catch (e) { }   // экзамен из кабинета
  return true;
}
function bugSnapTake() {                                    // открыли настройки — каким был экран до них (для жалобы)
  if ($("#sh-safe.on")) return;                               // открытый сейф (пароли на экране) в жалобу не снимаем
  try { const b = D.snapshot ? D.snapshot() : ""; bugSnap = b ? { ts: Date.now(), b64: b } : bugSnap; } catch (e) { }
}
const bugPickHtml = () => bugPick
  ? `<div class="bpk"><img src="${bugPick}" alt="Фото к жалобе" id="bug-pickimg"><button class="x" id="bug-pickx" title="Убрать фото" aria-label="Убрать фото">${X_SVG}</button></div>`
  : `<label class="btn w"><input type="file" id="bug-file" accept="image/*" hidden>📎 Добавить фото или скриншот</label><p class="hint" style="margin:6px 2px 0">Откроется галерея — свежие скриншоты в ней первыми.</p>`;
async function complaintSend(note, who, withShot, via, talk) {
  note = String(note || "").trim();
  if (note.length < 3) throw new Error("напишите хотя бы пару слов — что пошло не так");
  who = String(who || "").replace(/[<>"]/g, "").trim().slice(0, 40); S.who = who;
  const snap = withShot && bugSnap && Date.now() - bugSnap.ts < 30 * 6e4 ? "data:image/jpeg;base64," + bugSnap.b64 : "";
  const shot = snap && bugPick ? await stitchShots([bugPick, snap]) : (bugPick || snap);    // снимок один — оба рядом
  const d = await reportSend(note, false, `жалоба (${via || "кнопкой"})`, { shot, who, talk: talk !== false });
  S.complaints = (S.complaints || []).filter(c => Date.now() / 1000 - c.ts < 180 * 86400).slice(-49)
    .concat([{ id: d.id, s: d.secret || "", base: d.base, note: note.slice(0, 2000), ts: Math.round(Date.now() / 1000), status: "new", reply: "", fixed: "", shot: !!shot }]);
  saveS(); if (shot) { bugSnap = null; bugPick = ""; }
  console.log(`🐞 Жалоба №${d.id} отправлена (${via || "кнопкой"})${shot ? " со снимком" : ""}`);
  return { id: d.id, shot: !!shot };
}
/* две картинки (фото из галереи и снимок экрана) — одной, рядом: в жалобе место для одного снимка */
function stitchShots(urls) {
  return Promise.all(urls.map(u => new Promise((ok, no) => { const im = new Image(); im.onload = () => ok(im); im.onerror = () => no(new Error("снимок не открылся")); im.src = u; })))
    .then(ims => { const h = Math.min(1400, Math.max(...ims.map(i => i.height))), ws = ims.map(i => Math.round(i.width * h / i.height)), gap = 16;
      const c = document.createElement("canvas"); c.width = ws.reduce((a, b) => a + b, 0) + gap * (ims.length - 1); c.height = h;
      const g = c.getContext("2d"); g.fillStyle = "#111"; g.fillRect(0, 0, c.width, c.height);
      let x = 0; ims.forEach((im, i) => { g.drawImage(im, x, 0, ws[i], h); x += ws[i] + gap; });
      return c.toDataURL("image/jpeg", 0.85); }).catch(() => urls[0]);
}
function complaintMessage(c) {
  const what = `«${String(c.note || "").slice(0, 60)}»`, reply = c.reply ? " " + c.reply.trim() : "", reward = c.reward ? ` В благодарность — ${c.reward} тал. на ваш ключ.` : "";
  if (c.status === "fixed") return [`Ваша жалоба №${c.id} исправлена`, `${what} — исправлено${c.fixed ? " в версии " + c.fixed : ""}.${reply}${reward} Спасибо, что помогаете делать Dewiar лучше!`];
  if (c.status === "work") return [`Жалоба №${c.id} — в работе`, `${what}: разработчик подтвердил и чинит.${reply}${reward} Спасибо!`];
  if (c.status === "no") return [`Ответ на жалобу №${c.id}`, `${what}.${reply || " Разработчик не нашёл тут ошибки."} Спасибо, что написали!`];
  return [`Ответ на жалобу №${c.id}`, `${what}.${reply}`];
}
async function complaintsCheck() {
  const now = Date.now() / 1000;          // старше 60 дней — не спрашиваем; ответили по существу — ещё неделю, потом нет
  const ask = (S.complaints || []).filter(c => c.s && now - (c.ts || 0) < 60 * 86400
    && (!(["fixed", "no"].includes(c.status) || (c.status === "seen" && c.reply)) || now - (c.ts || 0) < 7 * 86400));
  if (!ask.length) return [];
  const news = [];
  for (const base of [...new Set(ask.map(c => c.base || healthBase()))]) {
    let r; try { r = await http("POST", base + "?p=/report/status", { headers: { "Content-Type": "application/json" },
      body: { items: ask.filter(c => (c.base || healthBase()) === base).map(c => ({ id: c.id, s: c.s })) }, timeout: 15000 }); } catch (e) { continue; }
    let d = {}; try { d = JSON.parse(r.body || "{}"); } catch (e) { }
    for (const x of d.items || []) {
      const c = S.complaints.find(y => y.id === x.id && (y.base || healthBase()) === base); if (!c) continue;
      const changed = x.status !== c.status || (x.reply || "") !== (c.reply || "");
      Object.assign(c, { status: x.status, reply: x.reply || "", fixed: x.fixed || "", reward: x.reward || 0 });
      if (changed && (["work", "fixed", "no"].includes(x.status) || x.reply)) news.push(c);
    }
  }
  saveS();
  if (news.length) thanksCache = null;                       // подтвердили — в «Помощниках» мог появиться и он сам
  for (const c of news) { const [t, x] = complaintMessage(c); D.notify(t, x); toast(`💬 ${t}${c.reply ? " — " + c.reply.slice(0, 90) : ""}`, 8000); }
  return news;
}
async function thanksGet() {
  if (thanksCache && Date.now() - thanksCache.at < 36e5) return thanksCache.people;
  const r = await http("GET", healthBase() + "?p=/thanks", { timeout: 10000 });
  let d = {}; try { d = JSON.parse(r.body || "{}"); } catch (e) { }
  thanksCache = { at: Date.now(), people: d.people || [] };
  return thanksCache.people;
}
const BUG_ST = { new: "отправлена", seen: "прочитана", work: "в работе", fixed: "исправлено", no: "не ошибка" };
function complaintsHtml() {
  const mine = (S.complaints || []).slice().reverse().slice(0, 6);
  return mine.length ? `<div class="bugh">Мои жалобы</div>` + mine.map(c => `<div class="bugc"><div><b>№${esc(c.id)}</b> ${esc(c.note || "")}</div>`
    + `<div class="bst"><span class="chip ${esc(c.status)}">${BUG_ST[c.status] || esc(c.status)}${c.status === "fixed" && c.fixed ? " в " + esc(c.fixed) : ""}</span>`
    + `${new Date(c.ts * 1000).toLocaleDateString("ru-RU")}${c.reward ? ` · спасибо ${+c.reward || 0} тал.` : ""}</div>${c.reply ? `<div class="brep">${esc(c.reply)}</div>` : ""}</div>`).join("") : "";
}
// «сообщи об ошибке: радио молчит», «передай разработчику, что…», «пожалуйся разработчику…»
const BUG_RX = /^(?:(?:сообщи|передай|напиши|отправь|скажи)\s+(?:разработчик\S*\s+)?(?:об?\s+)?(?:ошибк\S*|проблем\S*|баг\S*|сбо\S*)|отправь\s+жалобу(?:\s+разработчик\S*)?|пожалуйся(?:\s+разработчик\S*)?|(?:передай|скажи|напиши)\s+разработчик\S*)(?:\s*[:,.—-]\s*|\s+)?(?:что\s+)?([\s\S]*)$/i;
/* Жалоба оборвалась на паузе (отчёт №90, 19.10: «передай разработчику приложения что» ушло как есть — «меня до конца
   дослушай»): хвост — служебное слово или пусто — переспросить и дописать следующую фразу к началу (как core/health.py). */
const BUG_LEAD = /^(?:(?:этого\s+|этой\s+)?(?:приложени\S*|программ\S*|dewiar\S*|девиар\S*|лиры|ассистент\S*)\s*[,:]?\s*)?(?:что\s+|о\s+том,?\s+что\s+)?/i;
const BUG_TAIL = new Set("что чтобы и а но или в во на про о об у с со к ко по за для из от до когда если потому как где это вот ну типа не очень приложения программы мне меня там тут так".split(" "));
function bugNote(raw) {
  const s = String(raw || "").trim().replace(/^[\s.,:;—-]+|[\s.,:;—-]+$/g, "").replace(BUG_LEAD, "").replace(/^[\s.,:;—-]+|[\s.,:;—-]+$/g, "");
  const w = s.toLowerCase().replace(/ё/g, "е").match(/[\p{L}\d-]+/gu) || [];
  if (s.length < 4 || !w.length) return ["", true];
  if (BUG_TAIL.has(w[w.length - 1])) return [w.length > 2 ? s : "", true];
  return [s, false];
}
let bugPrefix = "";
async function bugQuick(text) {
  const t = text.trim();
  let note;
  if (bugWait && Date.now() - bugWait < 40000) {
    bugWait = 0;
    if (/^(отмена|отмени|не надо|ничего|передумал\S*|забудь)\W*$/i.test(t)) { bugPrefix = ""; return { say: "Хорошо, не отправляю." }; }
    note = (bugPrefix + " " + t).trim(); bugPrefix = "";
  } else {
    const m = t.match(BUG_RX); if (!m) return null;
    const [n, cut] = bugNote(m[1]);
    if (cut) { bugWait = Date.now(); bugPrefix = n; return { say: n ? "Слушаю — договорите, что передать разработчику." : "Что случилось? Расскажите одной-двумя фразами — передам разработчику." }; }
    note = n;
  }
  try { const r = await complaintSend(note, S.who, false, "голосом"); return { say: gfix(`Передал разработчику — жалоба №${r.id}. Когда ответят или исправят, скажу. Спасибо, что помогаете!`) }; }
  catch (e) { return { say: `Не получилось отправить: ${e.message}. Можно в настройках: «Настройки» → «Сообщить о проблеме».` }; }
}
setTimeout(async function pulseTick() {
  try { if (Date.now() - (+prefGet("pulse_at") || 0) > 6 * 36e5 - 6e4 || (hLoad().starts || []).length) await pulseSend(); } catch (e) { }
  try { if (Date.now() - (+prefGet("cmp_at") || 0) > 6 * 36e5 - 6e4) { prefSet("cmp_at", String(Date.now())); await complaintsCheck(); } } catch (e) { }
  setTimeout(pulseTick, window.DEWIAR_PULSE_EVERY || 6 * 36e5);
}, window.DEWIAR_PULSE_WAIT || 60000);
/* Ответы на жалобы — раз в 15 минут, пока есть жалобы без ответа (29.10, владелец: «чтобы видел, что ему ответили»;
   раньше — раз в 6 часов вместе с пульсом). Открыли приложение — тоже проверка (не чаще раза в 2 минуты). */
// без ответа и моложе 2 дней — раз в 15 минут, моложе 14 — раз в час; старше — только с пульсом (раз в 6 часов); как на компьютере
const cmpWait = () => { const now = Date.now() / 1000, w = (S.complaints || []).filter(c => c.s && now - (c.ts || 0) < 14 * 86400
  && !["fixed", "no"].includes(c.status) && !c.reply).map(c => now - (c.ts || 0));
  return !w.length ? 0 : Math.min(...w) < 2 * 86400 ? 15 * 6e4 - 3e4 : 36e5 - 3e4; };
async function cmpTick(min) {
  const every = cmpWait(); if (!every || Date.now() - (+prefGet("cmp_at") || 0) < Math.max(min, every === 15 * 6e4 - 3e4 ? min : every)) return;
  prefSet("cmp_at", String(Date.now()));
  try { await complaintsCheck(); } catch (e) { }
}
setInterval(() => cmpTick(15 * 6e4 - 3e4), window.DEWIAR_CMP_EVERY || 15 * 6e4);   // и в фоне: ответ разработчика — уведомлением (раз в 15 мин, только пока жалоба без ответа)   // сама решает, пора ли (cmpWait)
document.addEventListener("visibilitychange", () => { if (!document.hidden) cmpTick(2 * 6e4); });
/* Прокси только для серверов Dewiar: dewiar.pro, поддомены, свой сайт аккаунта и облака (Java: NetProxy). */
function proxyHosts(extra) {
  return [S.account.server, S.accCloud && S.accCloud.base, S.llm.cloud && S.llm.base_url, S.stt.from_account && S.stt.url].concat(extra || [])
    .filter(Boolean).join(",");
}
function applyProxy(extra) {
  if (!D.setProxy) return "";
  const err = D.setProxy(effProxy(), proxyHosts(extra));
  if (err) console.warn("прокси:", err);
  return err;
}
/* Свой прокси главнее; нет своего, а включено «Использовать прокси Dewiar» — прокси, который выдал dewiar.pro (запомнен,
   пока сайт открывался). Только для серверов Dewiar: Telegram и остальной интернет — напрямую (трафик прокси платный). */
function effProxy() { return S.net.proxy || (S.net.dewiar && S.net.dewiar_secret) || ""; }
function dwProxyCred() {
  if (loggedIn()) return { token: S.account.token, base: ((S.accCloud && S.accCloud.base) || siteUrl("dwrapp/cloud.php")).split("?")[0] };
  if (S.llm.cloud && S.llm.api_key) return { token: S.llm.api_key, base: cloudBase() };
  return null;
}
/* «Прокси Dewiar»: адрес выдаёт облако (cloud.php ?p=/netcfg) вошедшим аккаунтом или с ключом Dewiar; обновляем раз в 6 ч.
   -> "" — получили (или ещё свежий), иначе текст ошибки. */
async function dwProxyFetch(force) {
  if (!S.net.dewiar) return "";
  if (!force && S.net.dewiar_secret && Date.now() - (S.net.dewiar_at || 0) < 6 * 36e5) return "";
  const c = dwProxyCred();
  if (!c) return "прокси Dewiar выдаётся тем, кто вошёл аккаунтом dewiar.pro или подключил ключ Dewiar";
  try {
    const d = await cloudGet(c.base, c.token, "/netcfg");
    S.net.dewiar_secret = normProxy(d.proxy || ""); S.net.dewiar_at = Date.now(); saveS();
    console.log("прокси Dewiar получен: " + hideProxy(S.net.dewiar_secret));
    return "";
  } catch (e) { console.log("прокси Dewiar не получен: " + e.message); return e.message; }
}
setTimeout(() => dwProxyFetch(false).catch(() => {}), 4000);
/* socks5://user:pass@host:1080, http://host:3128, host:port, ссылка t.me/socks?… → адрес; MTProto — отказ (как на компьютере). */
function normProxy(t) {
  t = String(t || "").trim(); if (!t) return "";
  const low = t.toLowerCase();
  if (/^(tg:\/\/socks|https?:\/\/t\.me\/socks|t\.me\/socks)/.test(low)) {
    const q = new URL(t.replace(/^tg:\/\/socks/i, "https://t.me/socks").replace(/^t\.me/i, "https://t.me")).searchParams;
    if (!q.get("server")) throw new Error("в ссылке нет адреса прокси (server=…)");
    const cred = q.get("user") ? encodeURIComponent(q.get("user")) + ":" + encodeURIComponent(q.get("pass") || "") + "@" : "";
    return `socks5://${cred}${q.get("server")}:${q.get("port") || 1080}`;
  }
  if (/^(tg:\/\/proxy|https?:\/\/t\.me\/proxy|t\.me\/proxy)/.test(low) || low.includes("secret="))
    throw new Error("это MTProto-прокси — он работает только в приложении Telegram. Нужен SOCKS5- или HTTP-прокси (socks5://адрес:порт) или VPN");
  if (!t.includes("://")) t = "http://" + t;
  let u; try { u = new URL(t.replace(/^socks5h?:|^socks:/i, "http:")); } catch (e) { throw new Error("прокси — socks5://адрес:порт или http://адрес:порт"); }
  const sch = t.split("://")[0].toLowerCase();
  if (!["http", "https", "socks5", "socks5h", "socks"].includes(sch)) throw new Error("прокси — socks5://адрес:порт или http://адрес:порт");
  if (!u.hostname || !u.port) throw new Error("у прокси нужен адрес и порт, например socks5://192.168.1.10:1080");
  return sch === "socks" ? "socks5" + t.slice(sch.length) : t;
}
const hideProxy = (p) => String(p || "").replace(/\/\/([^:/@]+):[^@]*@/, "//$1:•••@");
async function saveProxy(text, res, btn) {
  const old = S.net.proxy || "";
  let px;
  try { px = String(text || "").trim() === hideProxy(old) ? old : normProxy(text); }
  catch (e) { res.className = "res bad"; res.textContent = e.message; return false; }
  btn && (btn.disabled = true);
  res.className = "res"; res.textContent = px ? "проверяю, открывается ли dewiar.pro через этот прокси…" : "";
  S.net.proxy = px;
  const err = applyProxy();
  let ok = !err, why = err;
  if (px && ok) {
    try { const r = await http("GET", (S.account.server || SITE) + "/dwrapp/latest.json", { timeout: 15000 }); ok = r.status < 500 && r.status !== 407;
      why = r.status === 407 ? "прокси не принял логин или пароль" : "сайт ответил " + r.status; }
    catch (e) { ok = false; why = /end of stream|unexpected end/i.test(e.message) ? "прокси оборвал связь — проверьте адрес, порт, логин и пароль" : e.message; }
  }
  btn && (btn.disabled = false);
  if (!ok) { S.net.proxy = old; applyProxy(); res.className = "res bad"; res.textContent = `через этот прокси dewiar.pro не открывается (${why}) — не сохраняю`; return false; }
  saveS(); res.className = "res ok"; res.textContent = px ? "Готово: запросы к Dewiar идут через прокси." : "Прокси выключен — напрямую.";
  const inp = $("#px-in"); if (inp) inp.value = hideProxy(px);
  return true;
}
const blockedHint = () => S.net.proxy ? " Сейчас запросы к Dewiar идут через прокси — проверьте его: Настройки → Мозг → «Сеть»."
  : " Если dewiar.pro у вас заблокирован провайдером — укажите прокси: Настройки → Мозг → «Сеть».";
// реплики разговора: pref "history", хранятся последние 40 (вместе со свёрнутыми f:1 — см. ниже)
let history = (() => { try { return JSON.parse(prefGet("history") || "[]"); } catch (e) { return []; } })();
function saveH() { history = history.slice(-40); prefSet("history", JSON.stringify(history)); if (typeof histSoon === "function" && $("#sh-hist.on")) histSoon(); }

