/* Студия → «Подкасты» (0.87; владелец 11.11, ориентир — Audio Overview в NotebookLM). Слева — «Новый выпуск»: материал
   (файлы перетаскиванием, ссылка или тема в поле), длина, подача, кто ведёт, цена до старта; ниже — «Выпуски». Справа —
   сцена: пока готовится — этапы и ход; готовый — проигрыватель с двумя дорожками (у каждого ведущего своя, его цветом:
   видно, кто когда говорит, нажатие — перемотка) и текст выпуска с подсветкой текущей реплики.
   Ядро (core/podcast.py): podcast_list, podcast_get, podcast_estimate, podcast_start, podcast_resume, podcast_stop,
   podcast_delete, podcast_send; событие «podcast» {id, stage, pct, note, status, title | open | stage:"end"}.
   Звук: студия с http://127.0.0.1 (Windows) — через сервер окон /podcast-audio/<id> (ui/app.py), с диска — file://. */
const PD = { items: [], ms: [], hosts: [], files: [], minutes: 10, style: "simple", cur: "", ep: null, live: null, estT: 0, estN: 0,
  follow: true, userScroll: 0, raf: 0, idx: -1 };
const PD_STYLES = [["simple", "Простыми словами", "для тех, кто впервые слышит о теме"], ["deep", "Глубоко", "причины, механизмы, цифры"],
  ["debate", "Спор двух мнений", "ведущие на разных позициях"]];
const PD_STAGES = [["read", "Читаю материал"], ["digest", "Выписываю главное"], ["plan", "Составляю план"], ["script", "Пишу диалог"],
  ["check", "Сверяю с материалом"], ["voice", "Озвучиваю"], ["mix", "Собираю звук"]];
const PD_EX = ["Почему мы забываем сны", "Как работает инфляция", "Чем чёрная дыра отличается от звезды"];
const PD_EXT = /\.(pdf|docx|odt|epub|fb2|rtf|txt|md|html?|csv|srt|vtt)$/i;
const PD_MAXF = 25 * 1024 * 1024;
const pdEsc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const pdN = (x) => { const v = Number(x); return Number.isFinite(v) ? v : 0; };   // число из ответа ядра — только число
const pdDur = (s) => { s = Math.max(0, Math.round(pdN(s))); return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`; };
const pdNum = (x, d = 2) => String(+(+x).toFixed(d)).replace(".", ",");
const pdMB = (b) => b > 1048576 ? pdNum(b / 1048576, 1) + " МБ" : Math.max(1, Math.round(b / 1024)) + " КБ";
const pdHost = (id) => PD.ms.find(m => m.id === id) || { id, name: id, color: "#8B7CFF" };
const pdUrls = () => ($("#pd-topic").value.match(/https?:\/\/\S+/g) || []);
const pdWord = (n, a, b, c) => { const m = n % 10, h = n % 100; return m === 1 && h !== 11 ? a : m >= 2 && m <= 4 && (h < 12 || h > 14) ? b : c; };

async function loadPodcasts() {
  let d;
  try { d = await core.call("podcast_list"); } catch (e) { toast(e.message, 4000); return; }
  PD.items = d.items || []; PD.ms = (d.hosts || []).filter(m => m.id);
  if (!PD.hosts.length || !PD.hosts.every(h => PD.ms.some(m => m.id === h))) PD.hosts = (d.pick || []).slice(0, 2);
  pdForm(); pdList();
  const st = d.state;
  if (st && !st.done) { PD.live = st; PD.cur = st.id; pdProgress(); }
  else if (PD.cur && PD.items.some(x => x.id === PD.cur)) pdOpen(PD.cur);
  else if (PD.items.length) pdOpen(PD.items[0].id);
  else pdEmpty();
  pdEstimate();
}

/* ---------- новый выпуск ---------- */
function pdForm() {
  if (!$("#pd-new").dataset.wired) {
    $("#pd-new").dataset.wired = "1";
    const drop = $("#pd-drop"), inp = $("#pd-file");
    drop.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); inp.click(); } });
    inp.onchange = () => { pdAdd([...inp.files]); inp.value = ""; };
    ["dragenter", "dragover"].forEach(t => drop.addEventListener(t, e => { e.preventDefault(); drop.classList.add("over"); }));
    ["dragleave", "drop"].forEach(t => drop.addEventListener(t, e => { e.preventDefault(); drop.classList.remove("over"); }));
    drop.addEventListener("drop", e => pdAdd([...(e.dataTransfer.files || [])]));
    $("#pd-topic").addEventListener("input", () => { pdSrc(); pdEstimate(); });
    $("#pd-ex").innerHTML = PD_EX.map(x => `<button class="chip" type="button">${pdEsc(x)}</button>`).join("");
    $$("#pd-ex .chip").forEach(b => b.onclick = () => { $("#pd-topic").value = b.textContent; pdSrc(); pdEstimate(); $("#pd-topic").focus(); });
    $$("#pd-len button").forEach(b => b.onclick = () => { PD.minutes = +b.dataset.m; pdForm(); pdEstimate(); });
    $("#pd-go").onclick = pdStart;
    try { const v = JSON.parse(localStorage.getItem("pd_opts") || "{}"); if ([5, 10, 20].includes(v.minutes)) PD.minutes = v.minutes;
      if (PD_STYLES.some(s => s[0] === v.style)) PD.style = v.style; } catch (e) { }
  }
  $$("#pd-len button").forEach(b => { const on = +b.dataset.m === PD.minutes; b.classList.toggle("on", on); b.setAttribute("aria-checked", on); });
  $("#pd-style").innerHTML = PD_STYLES.map(([k, t, s]) => `<button type="button" role="radio" aria-checked="${k === PD.style}" class="pd-st${k === PD.style ? " on" : ""}" data-s="${k}">`
    + `<b>${t}</b><small>${s}</small></button>`).join("");
  $$("#pd-style .pd-st").forEach(b => b.onclick = () => { PD.style = b.dataset.s; pdForm(); });
  const opt = (sel) => PD.ms.map(m => `<option value="${pdEsc(m.id)}"${m.id === sel ? " selected" : ""}>${pdEsc(m.name)}</option>`).join("");
  const [a, b] = PD.hosts;
  const ra = PD.style === "debate" ? "за" : "объясняет", rb = PD.style === "debate" ? "против" : "спрашивает";
  $("#pd-hosts").innerHTML = `<span class="pd-lbl">Ведут</span>`
    + `<label class="pd-h" style="--c:${pdEsc(pdHost(a).color)}"><i aria-hidden="true"></i><select aria-label="Первый ведущий — ${ra}" data-k="0">${opt(a)}</select><small>${ra}</small></label>`
    + `<button type="button" class="pd-swap" title="Поменять ролями" aria-label="Поменять ведущих ролями"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 7h12l-3-3M17 17H5l3 3"/></svg></button>`
    + `<label class="pd-h" style="--c:${pdEsc(pdHost(b).color)}"><i aria-hidden="true"></i><select aria-label="Второй ведущий — ${rb}" data-k="1">${opt(b)}</select><small>${rb}</small></label>`;
  $$("#pd-hosts select").forEach(s => s.onchange = () => {
    const k = +s.dataset.k, o = 1 - k;
    if (s.value === PD.hosts[o]) PD.hosts[o] = PD.hosts[k];         // выбрали того же — второй встаёт на его место
    PD.hosts[k] = s.value; pdForm();
  });
  $("#pd-hosts .pd-swap").onclick = () => { PD.hosts.reverse(); pdForm(); };
  pdSrc();
  const busy = PD.live && !PD.live.done;
  $("#pd-go").disabled = !!busy;
  $("#pd-go").textContent = busy ? "Готовлю выпуск…" : "Сделать подкаст";
}

function pdAdd(list) {
  for (const f of list) {
    if (!PD_EXT.test(f.name)) { toast(`«${f.name}» — такой файл я не читаю. Подойдут PDF, Word, EPUB, FB2, TXT`, 5000); continue; }
    if (f.size > PD_MAXF) { toast(`«${f.name}» больше 25 МБ — возьмите главу или часть`, 5000); continue; }
    if (PD.files.length >= 10) { toast("Не больше 10 файлов за раз"); break; }
    if (!PD.files.some(x => x.name === f.name && x.size === f.size)) PD.files.push(f);
  }
  pdSrc(); pdEstimate();
}
function pdSrc() {
  const urls = pdUrls();
  const item = (cls, ic, name, meta, i) => `<li class="${cls}"><i aria-hidden="true">${ic}</i><span title="${pdEsc(name)}">${pdEsc(name)}</span><small>${meta}</small>`
    + (i == null ? "" : `<button type="button" data-i="${i}" aria-label="Убрать ${pdEsc(name)}">×</button>`) + "</li>";
  const fileIc = '<svg viewBox="0 0 24 24"><path d="M7 3.5h7l4 4v13H7z"/><path d="M14 3.5v4h4"/></svg>';
  const linkIc = '<svg viewBox="0 0 24 24"><path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1.4 1.4"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1.4-1.4"/></svg>';
  const vid = (u) => /youtu\.?be|rutube\.ru|vk\.com\/video|vkvideo/i.test(u);
  $("#pd-src").innerHTML = PD.files.map((f, i) => item("f", fileIc, f.name, pdMB(f.size), i)).join("")
    + urls.map(u => item("u", linkIc, u.replace(/^https?:\/\/(www\.)?/, ""), vid(u) ? "видео" : "страница")).join("");
  $$("#pd-src button[data-i]").forEach(b => b.onclick = () => { PD.files.splice(+b.dataset.i, 1); pdSrc(); pdEstimate(); });
  $("#pd-ex").hidden = !!(PD.files.length || $("#pd-topic").value.trim());
}

function pdEstimate() {
  clearTimeout(PD.estT);
  PD.estT = setTimeout(async () => {
    const n = ++PD.estN, topic = $("#pd-topic").value.trim();
    const el = $("#pd-cost");
    if (!PD.files.length && !topic) { el.className = "pd-cost"; el.textContent = "Хватит и темы одной строкой — остальное ведущие расскажут сами."; return; }
    let e;
    try { e = await core.call("podcast_estimate", { minutes: PD.minutes, files: PD.files.map(f => ({ name: f.name, size: f.size })),
      urls: pdUrls().length, chars: topic.replace(/https?:\/\/\S+/g, "").length }); } catch (x) { return; }
    if (n !== PD.estN) return;
    if (e.error) { el.className = "pd-cost bad"; el.textContent = e.error[0].toUpperCase() + e.error.slice(1) + "."; return; }
    const wait = `Будет готов минут через ${pdN(e.wait)}, говорят ${e.voice}.`;
    let price = "";
    if (e.talers != null) {
      price = `Обойдётся примерно в ${pdNum(Math.max(e.talers, 0.001), 3)} талера`
        + (e.rub != null ? ` (≈ ${pdNum(Math.max(e.rub, 0.1), 1)} ₽)` : "") + (e.answers ? `, как ${e.answers} ${pdWord(e.answers, "обычный ответ", "обычных ответа", "обычных ответов")} Лиры` : "") + ". ";
    } else price = "Своя модель — облако Dewiar не тратится. ";
    el.className = "pd-cost" + (e.short ? " bad" : e.long ? " warn" : "");
    el.textContent = (e.short ? "На ИИ-балансе может не хватить. " : "") + price + wait + (e.long && !e.short ? " Длинный выпуск — можно заняться своими делами, я скажу, когда готово." : "");
  }, 350);
}

async function pdStart() {
  const topic = $("#pd-topic").value.trim();
  if (!PD.files.length && !topic) { toast("Дайте материал: файл, ссылку или тему словами"); $("#pd-topic").focus(); return; }
  const btn = $("#pd-go"); btn.disabled = true; btn.textContent = PD.files.length ? "Передаю файлы…" : "Начинаю…";
  try {
    const files = await Promise.all(PD.files.map(f => new Promise((ok, no) => { const r = new FileReader();
      r.onload = () => ok({ name: f.name, b64: r.result }); r.onerror = () => no(new Error(`«${f.name}» не прочитался`)); r.readAsDataURL(f); })));
    const r = await core.call("podcast_start", { topic, files, minutes: PD.minutes, style: PD.style, hosts: PD.hosts,
      lang: $("#pd-lang").value, intro: $("#pd-intro").checked });
    try { localStorage.setItem("pd_opts", JSON.stringify({ minutes: PD.minutes, style: PD.style })); } catch (e) { }
    PD.files = []; $("#pd-topic").value = "";
    PD.cur = r.id; PD.live = { id: r.id, stage: "read", pct: 0, note: "", title: r.title, done: false };
    pdForm(); pdProgress();
    core.call("podcast_list").then(d => { PD.items = d.items || []; pdList(); }).catch(() => {});
  } catch (e) { toast(e.message, 6000); pdForm(); }
}

/* ---------- выпуски ---------- */
function pdList() {
  const st = { working: "готовится", stopped: "остановлен", error: "не получился" };
  $("#pd-list").innerHTML = PD.items.length ? PD.items.map(x => `<li><button type="button" data-id="${pdEsc(x.id)}" class="${x.id === PD.cur ? "cur" : ""}${st[x.status] ? " " + x.status : ""}">`
    + `<b>${pdEsc(x.title)}</b><small>${x.status === "done" ? pdDur(x.duration) + ", " : ""}${new Date(pdN(x.created) * 1000).toLocaleString("ru-RU", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}`
    + `${st[x.status] ? ` <em>${st[x.status]}</em>` : ""}</small></button></li>`).join("")
    : `<li class="pd-none">Готовые выпуски появятся здесь.</li>`;
  $$("#pd-list [data-id]").forEach(b => b.onclick = () => (PD.live && !PD.live.done && b.dataset.id === PD.live.id) ? (PD.cur = PD.live.id, pdProgress(), pdList()) : pdOpen(b.dataset.id));
}

function pdEmpty() {
  pdStopAudio();
  $("#pd-main").innerHTML = `<div class="pd-stage pd-hello"><div class="pd-wave" aria-hidden="true">${pdDemo()}</div>
    <h2>Здесь зазвучит ваш первый выпуск</h2>
    <p>Положите слева статью, главу книги или конспект — или просто напишите тему. ${pdEsc(pdHost(PD.hosts[0]).name)} объяснит,
      ${pdEsc(pdHost(PD.hosts[1]).name)} спросит то, что спросили бы вы, а в конце они соберут главное.</p>
    <p class="pd-say">Можно и голосом: «Лира, сделай подкаст по этому файлу».</p></div>`;
}
/* заставка пустой сцены: две дорожки «разговора» цветами ведущих — так выглядит выпуск, пока его нет */
function pdDemo() {
  const a = pdHost(PD.hosts[0]), b = pdHost(PD.hosts[1]);
  const seq = [[0, 9], [1, 3], [0, 14], [1, 6], [1, 2], [0, 7], [1, 11], [0, 4], [1, 3], [0, 12], [1, 5]];
  const tot = seq.reduce((s, x) => s + x[1] + 1, 0); let t = 0;
  const bars = seq.map(([w, n]) => { const x = t / tot * 100; t += n + 1; return `<i style="left:${x}%;width:${n / tot * 100}%;--c:${pdEsc((w ? b : a).color)}" class="r${w}"></i>`; }).join("");
  return `<div class="pd-tr">${bars}</div>`;
}

/* ---------- ход работы ---------- */
function pdProgress() {
  pdStopAudio();
  const s = PD.live || {};
  const at = PD_STAGES.findIndex(x => x[0] === s.stage);
  $("#pd-main").innerHTML = `<div class="pd-stage pd-work"><h2 class="pd-title">${pdEsc(s.title || "Новый выпуск")}</h2>
    <p class="pd-sub">${pdEsc(pdHost(PD.hosts[0]).name)} и ${pdEsc(pdHost(PD.hosts[1]).name)} готовят выпуск. Можно закрыть студию — я скажу, когда он будет готов.</p>
    <div class="pd-wave" aria-hidden="true">${pdDemo()}</div>
    <ol class="pd-steps">${PD_STAGES.map(([k, t], i) => `<li class="${i < at ? "done" : i === at ? "now" : ""}${k === "digest" && at > 1 && !s.digested ? " skip" : ""}" data-k="${k}"><span>${t}</span>${i === at && s.note ? `<small>${pdEsc(s.note)}</small>` : ""}</li>`).join("")}</ol>
    <div class="pd-bar" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${pdN(s.pct)}" aria-label="Готовность выпуска"><b style="width:${Math.max(2, pdN(s.pct))}%"></b></div>
    <button class="btn small pd-stop" type="button">Остановить</button></div>`;
  $(".pd-stop").onclick = async () => { try { await core.call("podcast_stop"); } catch (e) { toast(e.message); } };
}

/* ---------- готовый выпуск ---------- */
async function pdOpen(id) {
  let m;
  try { m = await core.call("podcast_get", { id }); } catch (e) { toast(e.message, 5000); return; }
  PD.cur = id; PD.ep = m; PD.idx = -1; pdList();
  pdStopAudio();
  const a = m.hosts.a, b = m.hosts.b, lines = m.lines || [];
  const style = (PD_STYLES.find(s => s[0] === m.style) || [0, ""])[1];
  const when = new Date((m.done_at || m.created) * 1000).toLocaleString("ru-RU", { day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" });
  const src = (m.sources || []).filter(x => !x.skipped).map(x => x.title || x.name);
  const name = (w) => w === "a" ? a : b;
  if (m.status !== "done" || !m.audio) {
    const why = m.status === "error" ? (m.error || "что-то пошло не так") : "выпуск остановили, пока он готовился";
    $("#pd-main").innerHTML = `<div class="pd-stage pd-fail"><h2 class="pd-title">${pdEsc(m.title)}</h2>
      <p class="pd-sub">${pdEsc(why[0].toUpperCase() + why.slice(1))}. То, что уже готово (материал, план, диалог), сохранено — «Продолжить» начнёт с этого места.</p>
      <div class="pd-acts"><button class="btn primary small" data-a="resume" type="button">Продолжить</button><button class="btn small danger" data-a="del" type="button">Удалить</button></div></div>`;
    pdActs(m); return;
  }
  const dur = pdN(m.duration) || 1, fixed = Math.round(pdN(m.checked && m.checked.fixed));
  const bars = lines.map((x, i) => pdN(x.t1) > pdN(x.t0) ? `<i data-i="${i}" class="r${x.who === "a" ? 0 : 1}" style="left:${pdN(x.t0) / dur * 100}%;width:${Math.max(0.15, (pdN(x.t1) - pdN(x.t0)) / dur * 100)}%"></i>` : "").join("");
  const chk = fixed > 0 ? `<p class="pd-note">Сверка с материалом поправила ${fixed} ${pdWord(fixed, "место", "места", "мест")}.</p>` : "";
  const miss = m.checked && (m.checked.missing || []).length ? `<details class="pd-miss"><summary>Что не вошло в выпуск</summary><ul>${m.checked.missing.map(x => `<li>${pdEsc(x)}</li>`).join("")}</ul></details>` : "";
  $("#pd-main").innerHTML = `<div class="pd-stage pd-ep" style="--ca:${pdEsc(a.color)};--cb:${pdEsc(b.color)}">
    <h2 class="pd-title">${pdEsc(m.title)}</h2>
    <p class="pd-sub">Ведут ${pdEsc(a.name)} и ${pdEsc(b.name)}, ${pdEsc(style.toLowerCase())}. ${pdEsc(when)}.${src.length ? ` По материалу: ${pdEsc(src.slice(0, 3).join(", "))}${src.length > 3 ? ` и ещё ${src.length - 3}` : ""}.` : ""}</p>
    <div class="pd-player">
      <button class="pd-play" type="button" aria-label="Слушать"><svg viewBox="0 0 24 24" aria-hidden="true"><path class="pl" d="M8 5.5v13l10.5-6.5z"/><path class="pa" d="M8 5.5v13M16 5.5v13"/></svg></button>
      <div class="pd-tracks" role="slider" tabindex="0" aria-label="Перемотка" aria-valuemin="0" aria-valuemax="${Math.round(dur)}" aria-valuenow="0">
        <div class="pd-lane"><span style="--c:${pdEsc(a.color)}">${pdEsc(a.name)}</span></div><div class="pd-lane"><span style="--c:${pdEsc(b.color)}">${pdEsc(b.name)}</span></div>
        <div class="pd-bars">${bars}<div class="pd-head" aria-hidden="true"></div></div></div>
      <div class="pd-time"><b>0:00</b><span>${pdDur(dur)}</span></div>
      <button class="pd-speed" type="button" title="Скорость">1×</button>
      <audio preload="metadata"></audio>
    </div>
    <div class="pd-acts"><button class="btn small primary" data-a="dl" type="button">Скачать MP3</button><button class="btn small" data-a="phone" type="button">На телефон</button>
      <button class="btn small" data-a="dir" type="button">Открыть папку</button><button class="btn small danger" data-a="del" type="button">Удалить</button></div>
    ${chk}
    <div class="pd-text" tabindex="-1">${lines.map((x, i) => `<button type="button" class="pd-ln" data-i="${i}" style="--c:${pdEsc(name(x.who).color)}"><b>${pdEsc(name(x.who).name)}</b><span>${pdEsc(x.text)}</span></button>`).join("")}</div>
    ${miss}</div>`;
  if (!/\.mp3$/i.test(m.audio)) $('[data-a="dl"]').textContent = "Скачать";
  const au = $("#pd-main audio");
  au.src = /^https?:$/.test(location.protocol) ? `${location.origin}/podcast-audio/${encodeURIComponent(m.id)}` : (/^file:/i.test(m.uri || "") ? m.uri : "");
  PD.audio = au;
  const play = $(".pd-play");
  play.onclick = () => au.paused ? au.play().catch(e => toast("Звук не открылся: " + e.message, 5000)) : au.pause();
  au.onplay = () => { play.classList.add("on"); play.setAttribute("aria-label", "Пауза"); pdTick(); };
  au.onpause = () => { play.classList.remove("on"); play.setAttribute("aria-label", "Слушать"); };
  au.onended = () => { PD.follow = true; };
  au.ontimeupdate = () => pdAt(au.currentTime);
  const sp = $(".pd-speed"), speeds = [1, 1.25, 1.5, 0.85];
  sp.onclick = () => { const v = speeds[(speeds.indexOf(au.playbackRate) + 1) % speeds.length] || 1; au.playbackRate = v; sp.textContent = pdNum(v, 2) + "×"; };
  const tr = $(".pd-tracks");
  const seek = (e) => { const r = $(".pd-bars", tr).getBoundingClientRect(); au.currentTime = Math.max(0, Math.min(1, (e.clientX - r.left) / r.width)) * dur; pdAt(au.currentTime); };
  tr.addEventListener("pointerdown", e => { seek(e); tr.setPointerCapture(e.pointerId); tr.onpointermove = seek; });
  tr.addEventListener("pointerup", () => { tr.onpointermove = null; });
  tr.addEventListener("keydown", e => { const d = { ArrowRight: 5, ArrowLeft: -5, PageUp: 30, PageDown: -30 }[e.key];
    if (d) { e.preventDefault(); au.currentTime = Math.max(0, Math.min(dur, au.currentTime + d)); pdAt(au.currentTime); }
    else if (e.key === " ") { e.preventDefault(); play.click(); } });
  $$("#pd-main .pd-ln").forEach(el => el.onclick = () => { const x = lines[+el.dataset.i]; au.currentTime = pdN(x.t0); PD.follow = true; pdAt(au.currentTime); if (au.paused) au.play().catch(() => {}); });
  const txt = $(".pd-text");
  txt.addEventListener("wheel", () => { PD.userScroll = Date.now(); }, { passive: true });
  pdActs(m);
}

function pdActs(m) {
  $$("#pd-main [data-a]").forEach(b => b.onclick = async () => {
    const a = b.dataset.a;
    try {
      if (a === "dl") { const r = await core.call("ws_export", { path: m.path, fmt: "file" }); toast(`Сохранено в «${r.dir.split(/[\\/]/).pop()}»: ${r.name}`, 5000); }
      else if (a === "phone") { b.disabled = true; const r = await core.call("podcast_send", { id: m.id }); toast(`Отправила в ${r.to} — выпуск придёт файлом`, 5000); }
      else if (a === "dir") await core.call("ws_open", { path: m.folder });
      else if (a === "resume") { const r = await core.call("podcast_resume", { id: m.id }); PD.live = { id: r.id, stage: "", pct: 0, title: r.title, done: false }; pdForm(); pdProgress(); }
      else if (a === "del") {
        if (!await ask(`Удалить выпуск «${m.title}»? Папка с ним уйдёт в корзину.`)) return;
        await core.call("podcast_delete", { id: m.id }); toast("Выпуск — в корзине"); PD.cur = ""; loadPodcasts();
      }
    } catch (e) { toast(e.message, 6000); } finally { b.disabled = false; }
  });
}

/* подсветка реплики и бегунок: из timeupdate (≈4 раза в секунду) — реплика, из rAF — плавный бегунок */
function pdAt(t) {
  const m = PD.ep; if (!m || !m.lines) return;
  const dur = m.duration || 1, lines = m.lines;
  const head = $("#pd-main .pd-head"); if (head) head.style.left = Math.min(100, t / dur * 100) + "%";
  $("#pd-main .pd-time b") && ($("#pd-main .pd-time b").textContent = pdDur(t));
  const tr = $("#pd-main .pd-tracks"); if (tr) tr.setAttribute("aria-valuenow", Math.round(t));
  let i = -1;
  for (let k = 0; k < lines.length; k++) { if (lines[k].t0 <= t + 0.05) i = k; else break; }
  if (i === PD.idx) return;
  PD.idx = i;
  $$("#pd-main .pd-ln.now, #pd-main .pd-bars i.now").forEach(x => x.classList.remove("now"));
  if (i < 0) return;
  const el = $(`#pd-main .pd-ln[data-i="${i}"]`), bar = $(`#pd-main .pd-bars i[data-i="${i}"]`);
  if (bar) bar.classList.add("now");
  if (el) { el.classList.add("now");
    if (PD.audio && !PD.audio.paused && Date.now() - PD.userScroll > 4000) { const box = $("#pd-main .pd-text");
      const top = el.offsetTop - box.offsetTop - box.clientHeight / 3; box.scrollTo({ top, behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" }); } }
}
function pdTick() {
  cancelAnimationFrame(PD.raf);
  const step = () => { if (!PD.audio || PD.audio.paused) return; const h = $("#pd-main .pd-head"), dur = (PD.ep && PD.ep.duration) || 1;
    if (h) h.style.left = Math.min(100, PD.audio.currentTime / dur * 100) + "%"; PD.raf = requestAnimationFrame(step); };
  PD.raf = requestAnimationFrame(step);
}
function pdStopAudio() { if (PD.audio) { try { PD.audio.pause(); } catch (e) { } PD.audio = null; } cancelAnimationFrame(PD.raf); }

core.on("podcast", (e) => {
  if (!e) return;
  const page = $("#p-podcast"), shown = page && page.classList.contains("cur");
  if (e.open || e.started) { if (shown) loadPodcasts(); return; }
  if (!PD.live || PD.live.id !== e.id) { PD.live = { id: e.id, done: false }; }
  if (e.stage === "digest") PD.live.digested = true;
  if (e.stage === "end") {
    PD.live.done = true;
    if (!shown) return;
    core.call("podcast_list").then(d => { PD.items = d.items || []; pdForm(); pdList(); if (PD.cur === e.id || !PD.cur) pdOpen(e.id); }).catch(() => {});
    if (e.status === "done") toast(`Выпуск «${e.title}» готов`, 4000);
    return;
  }
  Object.assign(PD.live, { stage: e.stage, pct: e.pct, note: e.note, title: e.title || PD.live.title, done: false });
  if (!shown || PD.cur !== e.id) return;
  if (!$("#pd-main .pd-work")) { pdForm(); pdProgress(); return; }
  const at = PD_STAGES.findIndex(x => x[0] === e.stage);
  $$("#pd-main .pd-steps li").forEach((li, i) => { li.className = (i < at ? "done" : i === at ? "now" : "") + (li.dataset.k === "digest" && at > 1 && !PD.live.digested ? " skip" : "");
    const sm = $("small", li); if (i === at && e.note) { if (sm) sm.textContent = e.note; else li.insertAdjacentHTML("beforeend", `<small>${pdEsc(e.note)}</small>`); } else if (sm) sm.remove(); });
  const bar = $("#pd-main .pd-bar"); if (bar) { $("b", bar).style.width = Math.max(2, e.pct || 0) + "%"; bar.setAttribute("aria-valuenow", e.pct || 0); }
  if (e.title) $("#pd-main .pd-title").textContent = e.title;
});
