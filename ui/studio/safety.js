/* Студия Dewiar: раздел «Безопасность» — стоп-кран, схема «куда идут ваши данные», замки и журнал (0.38.98).
   Данные — команда ядра security_state (core/security.py): схема считается по настройкам сейчас, журнал — core/egress.py.
   Изменения — security_set: {local_only} или {lock, value}. Сейф, резервная копия и «Чего не сделает» — ниже, как раньше
   (welcome.js). Вызывается из core.js при открытии раздела; пока раздел открыт, журнал освежается раз в 10 секунд. */
let SF = null, sfPick = "";

const SF_ICON = {
  mic: '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/>',
  voice: '<path d="M4 9.5v5h3.5L12 18.5v-13L7.5 9.5z"/><path d="M15.5 9a4 4 0 0 1 0 6M18 6.5a7.5 7.5 0 0 1 0 11"/>',
  brain: '<circle cx="12" cy="12" r="3"/><path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M5.6 18.4l2.1-2.1M16.3 7.7l2.1-2.1"/>',
  notes: '<path d="M6.5 3.5h8l4 4v13h-12z"/><path d="M14.5 3.5v4h4M9 12h6M9 15.5h6"/>',
  vault: '<rect x="4.5" y="10.5" width="15" height="10" rx="2.5"/><path d="M8 10.5V7.5a4 4 0 0 1 8 0v3"/><path d="M12 14.5v2.5"/>',
  folder: '<path d="M3.5 6.5a2 2 0 0 1 2-2h4l2 2.2h7a2 2 0 0 1 2 2V18a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z"/>',
  camera: '<path d="M15 10l5-3v10l-5-3"/><rect x="3" y="7" width="12" height="10" rx="2"/>',
  screen: '<rect x="3" y="4.5" width="18" height="12" rx="2"/><path d="M9 20.5h6M12 16.5v4"/>',
};
const sfSvg = (k) => `<svg viewBox="0 0 24 24" aria-hidden="true">${SF_ICON[k]}</svg>`;
const sfWho = () => ((typeof personas !== "undefined" && personas.find(p => p.id === active)) || {}).name || "Ассистент";

async function loadSafety() {
  try { SF = await core.call("security_state"); } catch (e) { return; }
  renderSafety();
}
// журнал — раз в 10 с, только пока раздел виден (core.js secPoll: закрыли раздел или свернули окно — опроса нет)
secPoll("safety", 10000, async () => { if (!SF) return; SF = await core.call("security_state"); renderJournal(); renderStop(); });

function renderSafety() { if (!SF) return; renderStop(); renderMap(); renderLocks(); renderJournal(); loadRights(); }

/* ---------- «Что делает сам, а что — с вашего «да»» (отзывы 18–20.10: «насколько безопасен агент?», «лучше разрешать,
   а не запрещать — разрешаю только калькулятор») ----------
   Список умений — команда ядра tools (core/tools.py catalog: enabled, confirm, off_by, core). «Только безопасное» выключает
   всё, кроме core (разговор, напоминания, заметки, деньги, поиск); «Включить всё» — обратно; по одному — «Руки» → «Умения».
   Удаление файлов и команды терминала всегда спрашивают — это держит ядро (guard), а не галочка. */
let sfTools = [], sfArm = 0;
async function loadRights() {
  try { sfTools = await core.call("tools"); } catch (e) { return; }
  renderRights();
}
function renderRights() {
  const box = $("#sf-rights"); if (!box) return;
  const self = sfTools.filter(t => t.enabled && !t.confirm), ask = sfTools.filter(t => t.enabled && t.confirm);
  const off = sfTools.filter(t => t.off_by === "user"), na = sfTools.filter(t => t.off_by === "service");
  const chips = (list) => list.map(t => `<span class="sfchip" title="${escH(t.description)}">${escH(t.title)}</span>`).join("");
  const row = (cls, title, sub, list) => `<div class="sfr ${cls}"><div class="sfr-h"><i></i><b>${title}</b><span>${list.length}</span></div>`
    + (sub ? `<p class="sfr-sub">${sub}</p>` : "") + `<div class="sfchips">${chips(list)}</div></div>`;
  box.innerHTML = row("g", "Сам, без вопросов", "", self)
    + row("a", "Только после вашего «да»", "Спросит «Выполнить?» голосом и кнопками в виджете. Удаление файлов и команды терминала спрашивают всегда, даже если это выключить.", ask)
    + (off.length ? row("x", "Выключено вами", "Этого ассистент не делает и знает об этом — скажет, где включить.", off) : "")
    + (na.length ? `<p class="sfr-na">Ещё ${na.length} — появятся, когда подключите то, что им нужно (почту, умный дом, Telegram, сервер), или снимете замок.</p>` : "");
  const notCore = sfTools.filter(t => !t.core && t.off_by !== "user").length;
  $("#sfr-safe").disabled = !notCore; $("#sfr-all").disabled = !off.length;
}
async function sfSetTools(on) {
  const patch = {}; sfTools.forEach(t => { patch[t.name] = on(t); });
  await save({ tools: { enabled: patch } }, true);
  await loadRights();
}
$("#sfr-safe").onclick = async () => {
  const n = sfTools.filter(t => !t.core && t.off_by !== "user").length;
  if (Date.now() > sfArm) {                       // два нажатия: выключить сразу много умений — осознанно
    sfArm = Date.now() + 5000;
    $("#sfr-note").textContent = `Нажмите ещё раз — выключу ${n} умений: файлы, программы, команды, почту, сообщения, камеру и экран. Останутся разговор, напоминания, заметки, деньги и поиск.`;
    return;
  }
  sfArm = 0; await sfSetTools(t => !!t.core);
  $("#sfr-note").textContent = "Готово: только безопасное. Нужное включите по одному — «Настроить по одному».";
};
$("#sfr-all").onclick = async () => { sfArm = 0; await sfSetTools(() => true); $("#sfr-note").textContent = "Все умения снова включены; опасные по-прежнему спрашивают «Выполнить?»."; };
$("#sfr-one").onclick = () => { const b = $('nav button[data-p="hands"]'); if (b) b.click(); setTimeout(() => { const t = $("#toollist"); if (t) t.scrollIntoView({ block: "start" }); }, 200); };

/* ---------- стоп-кран ---------- */
function renderStop() {
  const f = SF.flows, lo = SF.local_only, who = sfWho(), own = SF.own || [];
  $("#sf-lo").checked = lo;
  $("#sf-stop").classList.toggle("lo", lo);
  $("#sf-lo-state").textContent = lo ? "Включено" : "Выключено";
  $("#sf-lo-hint").textContent = lo
    ? `Соединения с интернетом не открываются вовсе — ни одной частью программы. ${who} думает, слышит и говорит здесь; домашняя сеть работает (своя модель на соседнем компьютере — можно).`
      + (f.brain.where === "here" || f.brain.where === "home" ? "" : " Своей модели нет — отвечать как собеседник не получится, простые команды работают.")
    : `Включите — ${who} будет работать только здесь: свой слух, свой голос, своя модель. Облако, синхронизация, «Близкие» и интернет — на паузе, пока не выключите.`
      + (own.length ? ` Думать будет «${own[0].name}».` : " Своей модели пока нет: без неё — только простые команды. Подключить — «Мозг».");
  const pills = [];
  const b = f.brain;
  pills.push(b.where === "here" ? ["g", "думает здесь" + (b.name ? ` — ${b.name}` : "")] : b.where === "home" ? ["g", `думает дома — ${b.name}`]
    : b.where === "dewiar" ? [lo ? "x" : "a", lo ? "Dewiar Облако — на паузе" : "вопросы → Dewiar Облако"]
    : b.where === "service" ? [lo ? "x" : "a", lo ? `${b.name} — на паузе` : `вопросы → ${b.name}`] : ["x", "модель не подключена"]);
  pills.push(f.stt.where === "here" ? ["g", "речь распознаётся здесь"] : f.stt.where === "home" ? ["g", "речь — домашний сервер"] : ["a", `речь → ${f.stt.name}`]);
  if (f.sync.on) pills.push(lo ? ["x", "синхронизация — на паузе"] : f.sync.e2e ? ["b", "заметки → синхронизация, зашифровано"] : ["a", "заметки → синхронизация, без шифрования"]);
  if (f.close.on) pills.push(lo ? ["x", "«Близкие» — на паузе"] : ["b", "«Близкие» → зашифровано"]);
  if (f.bots.on) pills.push(lo ? ["x", f.bots.names.join(" и ") + " — на паузе"] : ["a", "бот " + f.bots.names.join(" и ")]);
  $("#sf-now").innerHTML = pills.map(([c, t]) => `<span class="sfp ${c}">${escH(t)}</span>`).join("");
}
$("#sf-lo").onchange = async (ev) => {
  const on = ev.target.checked;
  if (on && !(SF.own || []).length && !(await ask(`Своей модели на этом компьютере нет. Со стоп-краном ${sfWho()} будет слышать и выполнять простые команды — будильник, громкость, заметку, — но разговаривать не сможет, пока не подключите модель в «Мозге» или не выключите стоп-кран. Включить?`, { ok: "Включить", danger: false }))) {
    ev.target.checked = false; return;
  }
  try { const r = await core.call("security_set", { local_only: on }); SF = r.state; renderSafety(); if (r.note) toast(r.note, 4200); }
  catch (e) { ev.target.checked = !on; toast(e.message, 4000); }
};

/* ---------- схема ---------- */
const SF_COL = { g: "var(--sf-g)", b: "var(--sf-b)", a: "var(--sf-a)", x: "var(--sf-x)" };
function sfDests() {
  const f = SF.flows, lo = SF.local_only, out = [];
  const b = f.brain;
  if (b.where === "home") out.push({ id: "brain", from: 2, c: "g", t: "Мозг: " + b.name, s: "домашняя сеть, не интернет", l: "вопрос",
    why: `Вопросы уходят на вашу модель «${b.name}» в домашней сети — в интернет они не попадают.` });
  if (b.where === "dewiar") out.push({ id: "brain", from: 2, c: lo ? "x" : "a", t: "Мозг: Dewiar Облако", s: lo ? "на паузе" : "текст не хранится", l: "вопрос",
    why: "Чтобы ответить, вопрос и нужная часть разговора уходят на серверы Dewiar. Модель отвечает и забывает: тексты разговоров мы не сохраняем, учитываем только расход. Своя модель — «Мозг»: тогда здесь будет зелёная линия." });
  if (b.where === "service") out.push({ id: "brain", from: 2, c: lo ? "x" : "a", t: "Мозг: " + b.name, s: lo ? "на паузе" : "по вашему ключу, их правила", l: "вопрос",
    why: `Вопросы уходят в ${b.name} (${b.host}) по вашему ключу — сервис обращается с ними по своим правилам.` });
  if (b.where === "none") out.push({ id: "brain", from: 2, c: "x", t: "Мозг не подключён", s: "подключить — «Мозг»", l: "", why: "Модель не выбрана: ассистент выполняет простые команды, но не разговаривает." });
  if (f.stt.where === "dewiar" || f.stt.where === "service" || f.tts.where === "dewiar" || f.tts.where === "service") {
    const parts = [f.stt.where !== "here" && f.stt.where !== "home" ? "речь → " + f.stt.name : "", f.tts.where === "dewiar" || f.tts.where === "service" ? "голос ← " + f.tts.name : ""].filter(Boolean);
    out.push({ id: "voice", from: f.stt.where === "here" ? 1 : 0, c: "a", t: "Слух и голос", s: parts.join(", "), l: "звук",
      why: "Слух или голос работают на сервере: после имени фраза уходит туда звуком, ответ возвращается голосом. Распознавать на этом компьютере — «Звук и поведение» → «Слух» (GigaAM)." });
  }
  if (f.sync.on || f.close.on) {
    const enc = f.sync.e2e || !f.sync.on;
    out.push({ id: "sync", from: 3, c: lo ? "x" : enc ? "b" : "a", t: "Сервер Dewiar", s: lo ? "на паузе" : enc ? "видит только шифротекст" : "заметки — без шифрования", l: lo ? "" : enc ? "зашифровано" : "заметки",
      why: (f.sync.on ? (f.sync.e2e ? "Заметки, напоминания и учёт денег уходят на сервер зашифрованными на этом компьютере — ключ знают только ваши устройства. "
        : "Синхронизация без шифрования на устройстве: сервер хранит заметки как есть. Включить шифрование — «Связь» → «Синхронизация» → «Шифровать на устройстве». ") : "")
        + (f.close.on ? "Сообщения «Близким» шифруются на устройствах: сервер видит, кому и когда, но не что." : "") });
  }
  out.push({ id: "web", from: 2, c: lo ? "x" : "a", t: f.bots.on ? "Интернет и " + f.bots.names.join(", ") : "Интернет", s: lo ? "на паузе" : "поиск, погода — по просьбе", l: "запрос", dash: true,
    why: (f.web.via_dewiar ? "Поиск, погоду и чтение страниц ассистент делает только по вашей просьбе; если сайт не открывается напрямую — через сервер Dewiar. " : "Поиск, погоду и чтение страниц ассистент делает только по вашей просьбе, напрямую. ")
      + (f.bots.on ? `Бот ${f.bots.names.join(" и ")} пересылает ваши сообщения через их серверы.` : "") });
  return out;
}
function renderMap() {
  const f = SF.flows, d = sfDests();
  const rows = [
    ["mic", "Слух", f.stt.where === "here" ? "здесь" : f.stt.where === "home" ? "дома" : "на сервере"],
    ["voice", "Голос", f.tts.where === "off" ? "выключен" : f.tts.where === "here" ? "здесь" : f.tts.where === "home" ? "дома" : "на сервере"],
    ["brain", "Мозг", f.brain.where === "here" ? "здесь" : f.brain.where === "home" ? "дома" : f.brain.where === "none" ? "нет" : SF.local_only ? "на паузе" : "в облаке"],
    ["notes", "Память, заметки", "здесь"],
    ["vault", "Сейф паролей", "здесь"],
    ["folder", "Файлы", "здесь"],
  ];
  const RH = 40, top = 58, H = Math.max(top + rows.length * RH + 16, 40 + d.length * 86);
  const cy = (i) => top + i * RH + 17;
  const dy = (j) => (H - d.length * 70 - (d.length - 1) * 14) / 2 + j * 84;
  let s = `<svg viewBox="0 0 600 ${H}" class="sfm" role="img" aria-label="Схема: что остаётся на компьютере и что уходит наружу">`
    + `<defs>${Object.entries(SF_COL).map(([k, c]) => `<marker id="sfa-${k}" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" style="fill:${c}"/></marker>`).join("")}</defs>`;
  s += `<g class="you"><rect x="2" y="${H / 2 - 32}" width="80" height="64" rx="16"/><text x="42" y="${H / 2 - 3}" class="b" text-anchor="middle">Вы</text><text x="42" y="${H / 2 + 15}" class="m" text-anchor="middle">голос, текст</text></g>`;
  s += `<path d="M82 ${H / 2} H116" style="stroke:${SF_COL.g}" class="ln" marker-end="url(#sfa-g)"/>`;
  s += `<rect class="pc" x="120" y="10" width="236" height="${H - 20}" rx="20"/><text x="238" y="38" class="b" text-anchor="middle">Этот компьютер</text>`;
  rows.forEach(([ic, t, sub], i) => {
    const far = sub === "на сервере" || sub === "в облаке";
    s += `<g class="row"><rect x="132" y="${cy(i) - 17}" width="212" height="34" rx="10"/><g transform="translate(142 ${cy(i) - 9}) scale(.75)" class="ic">${SF_ICON[ic]}</g>`
      + `<text x="166" y="${cy(i) + 4.5}" class="b">${escH(t)}</text><text x="334" y="${cy(i) + 4.5}" class="m${far ? " far" : ""}" text-anchor="end">${escH(sub)}</text></g>`;
  });
  d.forEach((x, j) => {
    const y = dy(j), c = SF_COL[x.c], y0 = cy(x.from), y1 = y + 35;
    s += `<path class="ln${x.dash || x.c === "x" ? " dash" : ""}" d="M344 ${y0} C 386 ${y0}, 380 ${y1}, 420 ${y1}" style="stroke:${c}" marker-end="url(#sfa-${x.c})"/>`;
    s += `<g class="dst ${x.c}${sfPick === x.id ? " pick" : ""}" data-id="${x.id}" tabindex="0" role="button" aria-label="${escH(x.t)}: ${escH(x.s)}">`
      + `<rect x="424" y="${y}" width="174" height="70" rx="16" style="stroke:${c}"/>`
      + `<text x="511" y="${y + 30}" class="b" text-anchor="middle">${escH(sfFit(x.t, 22))}</text><text x="511" y="${y + 50}" class="m" text-anchor="middle">${escH(sfFit(x.s, 27))}</text></g>`;
  });
  s += "</svg>";
  $("#sf-map").innerHTML = s;
  $$("#sf-map .dst").forEach(g => { g.onclick = g.onkeydown = (ev) => { if (ev.type === "keydown" && ev.key !== "Enter" && ev.key !== " ") return; ev.preventDefault?.(); sfPick = sfPick === g.dataset.id ? "" : g.dataset.id; renderMap(); }; });
  const p = d.find(x => x.id === sfPick);
  $("#sf-why").innerHTML = p ? `<b>${escH(p.t)}.</b> ${escH(p.why)}` : "Нажмите на блок справа — откроется, что именно уходит и почему.";
  $("#sf-why").classList.toggle("on", !!p);
}
const sfFit = (t, n) => t.length > n ? t.slice(0, n - 1) + "…" : t;

/* ---------- замки ---------- */
function renderLocks() {
  const L = SF.locks, f = SF.flows, who = sfWho();
  const remoteEar = !(f.stt.where === "here" || f.stt.where === "home");
  const defs = [
    ["camera", "Камера", [["off", "Нельзя"], ["ask", "Спрашивать"]],
      { off: "Камеру не включает вовсе", ask: "Снимок — только с вашего «да»" }],
    ["screen", "Экран", [["off", "Нельзя"], ["ask", "Спрашивать"], ["on", "Можно"]],
      { off: "Не смотрит на экран и не делает снимков", ask: "Посмотреть на экран — после вашего «да»", on: "Смотрит, когда просите: «что у меня на экране?»" }],
    ["files", "Файлы", [["folder", "Папка ассистента"], ["all", "Весь компьютер"]],
      { folder: "Удаляет и отправляет только из своей папки, терминал выключен", all: "Удаление — в корзину и с вашего «да», системное — никогда" }],
    ["mic", "Микрофон", [["name", "Слышит имя"], ["button", "Только кнопка"]],
      { name: remoteEar ? "Ждёт имя; фразы распознаёт сервер — это видно в журнале" : "Ждёт имя — до него звук не пишется и никуда не уходит",
        button: `Слушает только после нажатия на лицо ${who === "Ассистент" ? "ассистента" : "в виджете"} или пробела` }],
  ];
  $("#sf-locks").innerHTML = defs.map(([k, t, opts, sub]) => `<div class="sfl" data-k="${k}">${sfSvg(k === "files" ? "folder" : k)}`
    + `<div><b>${t}</b><span>${escH(sub[L[k]] || "")}</span></div>`
    + `<div class="sfseg" role="radiogroup" aria-label="${t}">${opts.map(([v, n]) => `<button role="radio" aria-checked="${L[k] === v}" class="${L[k] === v ? "on" : ""}" data-v="${v}">${n}</button>`).join("")}</div></div>`).join("");
  $$("#sf-locks .sfl").forEach(row => $$("button", row).forEach(btn => btn.onclick = async () => {
    if (btn.classList.contains("on")) return;
    try { const r = await core.call("security_set", { lock: row.dataset.k, value: btn.dataset.v }); SF = r.state; renderLocks(); toast("Сохранено"); }
    catch (e) { toast(e.message, 4000); }
  }));
}

/* ---------- журнал ---------- */
const sfKB = (n) => n >= 1048576 ? (n / 1048576).toFixed(1).replace(".", ",") + " МБ" : n >= 1024 ? (n / 1024).toFixed(1).replace(".", ",") + " КБ" : n + " Б";
function renderJournal() {
  const rows = SF.journal || [];
  const hhmm = (t) => { const d = new Date(t * 1000); return String(d.getHours()).padStart(2, "0") + ":" + String(d.getMinutes()).padStart(2, "0"); };
  const n = (k) => { const m = k % 10, h = k % 100; return k + " " + (m === 1 && h !== 11 ? "раз" : m >= 2 && m <= 4 && (h < 12 || h > 14) ? "раза" : "раз"); };
  const lo = SF.local_only ? `<p class="sfempty lo">Стоп-кран включён — новых строк не будет, пока не выключите.</p>` : "";
  $("#sf-log").innerHTML = lo + (rows.length ? `<table class="sft"><tbody>${rows.map(r => `<tr><td class="t">${hhmm(r.last)}</td>`
    + `<td><i class="dot" style="background:${SF_COL[{ amber: "a", blue: "b", grey: "x" }[r.color] || "x"]}"></i>${escH(r.kind)}<span class="h">${escH(r.host)}</span></td>`
    + `<td class="n">${n(r.n)}${r.out ? ", отправлено " + sfKB(r.out) : ""}</td></tr>`).join("")}</tbody></table>`
    : `<p class="sfempty">Сегодня ничего не уходило наружу.</p>`);
}
