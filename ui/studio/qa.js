/* Студия Dewiar, «Вопрос — ответ» (27.10, по макету «Dewiar — обучение и «Команда»», владелец: «удобно, красиво, плиткой,
   с поиском»). Тот же текст, что руководство на сайте и ответы Лиры (data/guide.json, core/guide.py): core.call("guide")
   — всё, {q} — поиск (ids), {id} — статья. Слева — плитки разделов (или статьи раздела, или найденное), справа — статья:
   что это, как сделать, «попробуйте сказать» (▶ — фраза уйдёт Лире), советы, «Открыть раздел». */
let QA = { all: null, group: "", hits: null, cur: "", t: 0 };
const QA_GROUPS = {          // вид плиток: подложка, цвет значка, рисунок
  "Начало": ["#DDE3F7", "#3F4BD8", "M12 3l8 4.5v9L12 21l-8-4.5v-9z M12 12l8-4.5 M12 12v9 M12 12L4 7.5"],
  "Каждый день": ["#D9EFE7", "#12704F", "M5 5h14v14H5z M5 10h14 M10 5v14"],
  "Телефон": ["#F6E6CF", "#8A5300", "M8 3h8a1 1 0 0 1 1 1v16a1 1 0 0 1-1 1H8a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z M11 18h2"],
  "Близкие": ["#F6DDE6", "#A3284F", "M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z"],
  "Семья и дети": ["#E6DEF6", "#5B36A8", "M8 5.5a2.5 2.5 0 1 0 0 5a2.5 2.5 0 1 0 0-5 M16 5.5a2.5 2.5 0 1 0 0 5a2.5 2.5 0 1 0 0-5 M3 20v-2a4 4 0 0 1 4-4h2 M21 20v-2a4 4 0 0 0-4-4h-2 M10 20v-1a2 2 0 0 1 4 0v1"],
  "Работа": ["#DDE3F7", "#3F4BD8", "M4 8h16v11H4z M9 8V5h6v3 M4 13h16"],
  "Оформление и голос": ["#D9EFE7", "#12704F", "M12 3a9 9 0 1 0 9 9c0-1.5-1-2-2-2h-2a2 2 0 0 1-2-2V6c0-1.5-1.5-3-3-3z"],
  "Данные и аккаунт": ["#F6E6CF", "#8A5300", "M6 10V7a6 6 0 0 1 12 0v3 M5 10h14v10H5z"],
  "Если что-то не так": ["#F6DDE6", "#A3284F", "M12 4l9 16H3z M12 10v4 M12 17v.5"]
};
// статья руководства → раздел студии («Открыть раздел»)
const QA_OPEN = { reminders: "reminders", "notes-memory": "notes", "calendar-money": "calendar", payments: "pay", vault: "vault", close: "close",
  "close-invite": "close", "near-meet": "close", family: "family", kids: "kids", music: "music", tasks: "tasks", prompter: "prompter",
  "folder-docs": "folder", personas: "personas", "brain-account": "brain", voices: "voice", look: "look", hands: "hands",
  "home-tv-mail-calendars": "connect", "home-assistant": "connect", "telegram-max": "connect", "skills-mcp-servers": "skills", sync: "dw",
  privacy: "safety", "safety-backup": "safety", features: "features", tricks: "tricks", "soul-diary": "soul", talk: "ears", "chat-pc": "chat",
  "invite-friend": "ref", snapshot: "home", play: "home", "report-problem": "about", troubleshooting: "about" };
const QA_WHERE = { pc: "компьютер", phone: "телефон" };
const qaWord = (n, a, b, c) => `${n} ${plural(n, a, b, c)}`;
function qaGroups() {
  const g = {};
  (QA.all || []).forEach(s => (g[s.group || "Ещё"] = g[s.group || "Ещё"] || []).push(s));
  return g;
}
function qaLeft() {
  const box = $("#qa-left"); if (!box || !QA.all) return;
  const byId = Object.fromEntries(QA.all.map(s => [s.id, s]));
  const row = (s) => `<button class="qa-row${s.id === QA.cur ? " on" : ""}" data-id="${escH(s.id)}"><b>${escH(s.title)}</b><small>${escH(s.lead || "")}</small></button>`;
  if (QA.hits) {
    box.innerHTML = `<div class="qa-head"><button class="btn small" id="qa-back">Все разделы</button><span>${QA.hits.length ? `Нашлось: ${qaWord(QA.hits.length, "ответ", "ответа", "ответов")}` : "Ничего не нашлось"}</span></div>`
      + (QA.hits.length ? `<div class="qa-rows">${QA.hits.map(id => byId[id]).filter(Boolean).map(row).join("")}</div>`
        : `<p class="qa-none">Попробуйте другими словами — или нажмите «Спросить Лиру»: она ответит по этому же руководству.</p>`);
  } else if (QA.group) {
    const list = qaGroups()[QA.group] || [];
    box.innerHTML = `<div class="qa-head"><button class="btn small" id="qa-back">Все разделы</button><span>${escH(QA.group)}</span></div><div class="qa-rows">${list.map(row).join("")}</div>`;
  } else {
    const g = qaGroups();
    box.innerHTML = `<div class="qa-tiles">${Object.keys(g).map(name => {
      const [bg, ink, d] = QA_GROUPS[name] || ["#DDE3F7", "#3F4BD8", "M12 4v16M4 12h16"];
      return `<button class="qa-tile" data-g="${escH(name)}"><i style="background:${bg}"><svg viewBox="0 0 24 24" aria-hidden="true" style="stroke:${ink}"><path d="${d}"/></svg></i>`
        + `<b>${escH(name)}</b><small>${escH(g[name].slice(0, 4).map(s => s.title.replace(/[«»]/g, "").split(/[:—]/)[0].trim()).join(", "))}</small>`
        + `<em>${qaWord(g[name].length, "статья", "статьи", "статей")}</em></button>`;
    }).join("")}</div>`;
  }
  if ($("#qa-back")) $("#qa-back").onclick = () => { QA.group = ""; QA.hits = null; $("#qa-q").value = ""; qaLeft(); };
  $$("#qa-left .qa-tile").forEach(b => b.onclick = () => { QA.group = b.dataset.g; qaLeft(); const f = (qaGroups()[QA.group] || [])[0]; if (f) qaOpen(f.id); });
  $$("#qa-left .qa-row").forEach(b => b.onclick = () => qaOpen(b.dataset.id));
}
function qaOpen(id) {
  const s = (QA.all || []).find(x => x.id === id), box = $("#qa-art");
  if (!s || !box) return;
  QA.cur = id;
  $$("#qa-left .qa-row").forEach(b => b.classList.toggle("on", b.dataset.id === id));
  const li = (a) => (a || []).map(x => `<li>${escH(x)}</li>`).join("");
  const sec = QA_OPEN[s.id];
  box.innerHTML = `<small class="qa-meta">${escH(s.group || "")} · ${escH((s.where || []).map(w => QA_WHERE[w] || w).join(" и "))}</small>`
    + `<h2>${escH(s.title)}</h2><p class="qa-lead">${escH(s.lead || "")}</p>`
    + ((s.how || []).length ? `<h4>Как сделать</h4><ul class="qa-how">${li(s.how)}</ul>` : "")
    + ((s.say || []).length ? `<div class="qa-say"><h4>Попробуйте сказать</h4>${s.say.slice(0, 6).map((x, i) => `<button class="qa-try" data-i="${i}" title="Отправить Лире">`
        + `<span>«${escH(x)}»</span><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5.5v13l10.5-6.5z"/></svg></button>`).join("")}</div>` : "")
    + ((s.tips || []).length ? `<h4>Советы</h4><ul class="qa-tips">${li(s.tips)}</ul>` : "")
    + `<div class="qa-acts">${sec && $(`nav button[data-p="${sec}"]`) ? `<button class="btn primary" id="qa-go">Открыть раздел</button>` : ""}`
    + `<button class="btn" id="qa-lira">Не получилось — спросить Лиру</button>`
    + `<a class="qa-site" href="${typeof GUIDE_URL !== "undefined" ? GUIDE_URL : "https://dewiar.pro/dwrapp/guide.php"}#${escH(s.id)}" target="_blank" rel="noopener">На сайте, со снимками</a></div>`;
  $$("#qa-art .qa-try").forEach(b => b.onclick = async () => {
    b.disabled = true;
    try { await core.call("say", { text: s.say[+b.dataset.i] }); toast("Отправил Лире — смотрите виджет", 2500); } catch (e) { toast(e.message); }
    setTimeout(() => { b.disabled = false; }, 1500);
  });
  if ($("#qa-go")) $("#qa-go").onclick = () => { const b = $(`nav button[data-p="${sec}"]`); if (b) b.click(); };
  $("#qa-lira").onclick = () => qaAsk(`Помоги: ${s.title.replace(/[«»]/g, "")}. ${$("#qa-q").value.trim()}`.trim());
}
function qaAsk(text) {                                   // вопрос — в «Чат», ответ Лиры там же (по этому же руководству)
  const q = (text || $("#qa-q").value || "").trim();
  if (!q) { $("#qa-q").focus(); return; }
  const b = $('nav button[data-p="chat"]'); if (b) b.click();
  setTimeout(() => { const t = $("#ch-text"); if (t && typeof chatSend === "function") { t.value = q; chatSend(); } else core.call("say", { text: q }).catch(() => {}); }, 150);
}
async function qaSearch() {
  const q = $("#qa-q").value.trim();
  if (!q) { QA.hits = null; qaLeft(); return; }
  try { QA.hits = await core.call("guide", { q }); } catch (e) { QA.hits = []; }
  QA.group = ""; qaLeft();
  if (QA.hits.length) qaOpen(QA.hits[0]);
}
async function qaLoad() {
  if (!Array.isArray(QA.all)) { try { QA.all = await core.call("guide"); } catch (e) { return; } if (!Array.isArray(QA.all)) { QA.all = null; return; } }
  qaLeft();
  if (!QA.cur && QA.all.length) qaOpen((QA.all.find(s => s.id === "first-steps") || QA.all[0]).id);
}
window.loadQA = qaLoad;
if ($("#p-qa")) {
  $("#qa-q").oninput = () => { clearTimeout(QA.t); QA.t = setTimeout(qaSearch, 220); };
  $("#qa-q").onkeydown = (e) => { if (e.key === "Enter") { clearTimeout(QA.t); qaSearch(); } };
  $("#qa-ask").onclick = () => qaAsk();
}
