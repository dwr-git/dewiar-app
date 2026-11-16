//@ Телефон и веб-версия, часть 20: «сам замечает».
//@ Собирается в android/assets/www/app.js (tools/app_join.py) — порядок частей = порядок исполнения; шапка «//@» в app.js не попадает.
/* ---------- «сам замечает»: открыли приложение после перерыва — коротко о главном (как core/presence.py) ----------
   Перерыв считается от того, когда приложение последний раз было на экране (S.welcome.seen). Первый раз за день после 3 часов —
   короткая сводка дня; после 30 минут — только если есть что сказать: готовые с тех пор задачи, задача ждёт ответа, скоро
   напоминание. Ночью (23–7), чаще раза в 40 минут, если человек сам заговорил или приложение открыли кнопкой помощника — молчим. */
let lastUserAct = 0;
function welcomePlan(now, seen, lastGreet, tasks, alarms, dstat, eveSaid) {
  const h = new Date(now).getHours();
  if (!seen || h >= 23 || h < 7) return null;
  if (lastGreet && now - lastGreet < 40 * 60000) return null;
  const gone = now - seen;
  if (gone < 30 * 60000) return null;
  const facts = [], since = new Date(seen).toISOString().slice(0, 19);
  const done = tasks.filter(t => t.status === "done" && String(t.updated || "") >= since), wait = tasks.filter(t => t.status === "waiting");
  if (done.length) facts.push("Пока пользователя не было, готовы задачи: " + done.slice(0, 3).map(t => `«${t.title}»`).join("; ") + ".");
  if (wait.length) facts.push("Ждёт ответа пользователя задача: " + wait.slice(0, 2).map(t => `«${t.title}»`).join("; ") + ".");
  const soon = alarms.filter(a => a.kind !== "timer" && a.at > now && a.at - now < 2 * 3600000).sort((a, b) => a.at - b.at);
  const hm = (t) => { const d = new Date(t); return pad(d.getHours()) + ":" + pad(d.getMinutes()); };
  if (soon.length) facts.push("Скоро: " + soon.slice(0, 3).map(a => `в ${hm(a.at)} — ${a.title}`).join("; ") + ".");
  const goneTxt = gone < 3600000 ? Math.round(gone / 60000) + " мин" : Math.floor(gone / 3600000) + " ч";
  // вечер (с 19:00) и сегодня есть сделанные дела — итог дня, один раз за вечер (отзыв 13.10: «в конце дня — ты сегодня сделал 5–7 дел»)
  if (dstat && dstat.today && h >= 19 && eveSaid !== dayKey(now)) {
    facts.unshift(`Сегодня пользователь отметил сделанными ${dstat.today} ${delaRu(dstat.today)}: ${dstat.items.slice(-7).map(x => "«" + x.title + "»").join(", ")}.`
      + (dstat.streak >= 2 ? ` Серия: ${dstat.streak} ${dnRu(dstat.streak)} подряд.` : ""));
    return { kind: "eve", facts, gone: goneTxt };
  }
  const firstToday = (!lastGreet || new Date(lastGreet).toDateString() !== new Date(now).toDateString()) && gone >= 3 * 3600000;
  if (firstToday) {
    const today = alarms.filter(a => a.kind !== "timer" && a.at > now && new Date(a.at).toDateString() === new Date(now).toDateString()).sort((a, b) => a.at - b.at);
    if (today.length) facts.push("Напоминания и будильники на сегодня: " + today.slice(0, 5).map(a => `${hm(a.at)} ${a.title}`).join("; ") + ".");
    return { kind: "day", facts, gone: goneTxt };
  }
  return facts.length ? { kind: "back", facts, gone: goneTxt } : null;
}
function welcomePrompt(p) {
  const d = new Date(), wd = ["воскресенье", "понедельник", "вторник", "среда", "четверг", "пятница", "суббота"][d.getDay()];
  if (p.kind === "eve") return p.facts.join("\n") + `\n\n[Вечер, пользователь вернулся в приложение, не было ${p.gone}] Подведи итог дня: скажи, сколько дел он сегодня сделал, похвали тепло и конкретно (назови одно-два дела своими словами); если есть другие новости отсюда — одной фразой. 2–3 коротких предложения, без списков, без вопросов в конце, без инструментов.`;
  if (p.kind === "day") return `Сегодня ${d.toLocaleDateString("ru-RU")}, ${wd}, сейчас ${pad(d.getHours())}:${pad(d.getMinutes())}.\n` + p.facts.join("\n")
    + `\n\n[Пользователь открыл приложение — первый раз за день, не было ${p.gone}] Поздоровайся первым (в своём роде), по имени, если знаешь, и коротко скажи главное на сегодня из этих данных: погода (если есть), напоминания, что ждёт от сотрудников и клиентов, важные письма от людей, одна интересная новость из Радара (если есть). Не всё подряд — самое нужное; дела, которые он и так видит, не пересказывай целиком. 2–4 коротких предложения, живо и тепло, без списков, без вопросов в конце, без инструментов.`;
  return p.facts.join("\n") + `\n\n[Пользователь вернулся в приложение, не было ${p.gone}] Коротко поприветствуй и скажи главное из этого — 1–2 коротких предложения, живо, без списков и без вопросов в конце, без инструментов.`;
}
/* «Интересное в мире» (14.11, владелец: «интересное и необычное в мире — от Лиры кратко услышать с возможностью перейти…
   у всех разные вкусы»). Сервер раз в ~12 часов собирает ОДИН общий выпуск (core/world.py: до 14 любопытных материалов
   по темам, без политики, войн и катастроф; ?p=/world — без входа). Вкус — только здесь: веса тем S.world.t (выбранные
   темы и «👍 Интересно» / «👎 Не моё» под карточкой) плюс намёки из памяти («люблю космос»); из выпуска — одна лучшая
   для этого человека новость, которой он ещё не видел. Говорит её сводка дня, под ней карточка «Читать». */
const WORLD_TOPICS = [["science", "Наука"], ["space", "Космос"], ["tech", "Технологии"], ["ai", "ИИ"], ["health", "Здоровье"],
  ["nature", "Природа и животные"], ["culture", "Кино, книги, музыка"], ["money", "Деньги"], ["travel", "Путешествия"], ["food", "Еда"],
  ["sport", "Спорт"], ["curious", "Необычное"]];
const WORLD_HINT = { space: /космос|звёзд|звезд|астроном|nasa|space|\bstars?\b/i, science: /наук|физик|химик|биолог|science/i,
  tech: /техник|гаджет|смартфон|компьютер|программ|gadget|\btech/i, ai: /нейросет|искусственн|\bии\b|\bai\b/i,
  health: /здоров|бег\b|бегаю|йог|фитнес|health|fitness/i, nature: /природ|животн|собак|кошк|птиц|рыбал|nature|animal|\bdogs?\b|\bcats?\b/i,
  culture: /кино|фильм|сериал|книг|музык|театр|movie|book|music/i, money: /инвест|финанс|бизнес|акци[ия]|invest|business/i,
  travel: /путешеств|туризм|поездк|travel/i, food: /готовить|кулинар|рецепт|выпечк|cook|recipe|food/i, sport: /футбол|хоккей|спорт|теннис|бокс|football|sport/i };
const worldName = (id) => trL((WORLD_TOPICS.find(x => x[0] === id) || [id, id])[1]);
function worldTaste() { const w = Object.assign({ on: true, t: {}, seen: [] }, S.world || {}); w.t = w.t || {}; w.seen = w.seen || []; return w; }
function worldWeights() {
  const w = worldTaste(), out = Object.assign({}, w.t), mem = [...(S.memory || []), ...Object.values((S.pmem && S.pmem.facts) || {}).flat()].map(String).join("\n");
  for (const [id, rx] of Object.entries(WORLD_HINT)) if (!(id in out) && rx.test(mem)) out[id] = 1;     // «люблю космос» — космос повыше
  return out;
}
async function worldLoad(force) {
  let c = null; try { c = JSON.parse(fileGet("world.json") || "null"); } catch (e) { }
  const lang = appEn() ? "en" : "ru";
  if (!force && c && c.lang === lang && Date.now() - (+c.fetched || 0) < 3 * 3600e3) return c.items || [];
  try {
    const r = await http("GET", annBase() + "?p=/world&lang=" + lang, { timeout: 12000 }), d = JSON.parse(r.body || "{}");
    if (Array.isArray(d.items)) { c = { lang, at: +d.at || 0, fetched: Date.now(), items: d.items.slice(0, 16) }; fileSave("world.json", JSON.stringify(c)); }
  } catch (e) { }
  return (c && c.lang === lang && Date.now() - (+c.at || 0) * 1000 < 3 * 86400e3 ? c.items : null) || [];
}
/* лучшая для этого человека: оценка выпуска + 1.5 × вес темы; «не моё» (вес ≤ −2) — никогда; уже видел — нет */
function worldPick(items, min = 6.5) {
  const w = worldTaste(), wt = worldWeights(), seen = new Set(w.seen);
  let best = null, bs = -1;
  for (const x of items || []) {
    if (!x || !x.id || !x.url || seen.has(x.id)) continue;
    const k = +wt[x.topic] || 0; if (k <= -2) continue;
    const sc = (+x.score || 0) + 1.5 * k; if (sc > bs) { bs = sc; best = x; }
  }
  return bs >= min ? best : null;
}
function worldSeen(id) { const w = worldTaste(); if (!id || w.seen.includes(id)) return; w.seen = w.seen.concat(id).slice(-80); S.world = w; saveS(); }
function worldFeel(topic, d) {
  const w = worldTaste(); if (!topic) return;
  w.t[topic] = Math.max(-3, Math.min(3, Math.round(((+w.t[topic] || 0) + d) * 10) / 10)); S.world = w; saveS();
}
async function worldNewsTool(topic) {
  const items = await worldLoad(), wt = worldWeights(), seen = new Set(worldTaste().seen);
  if (!items.length) return "Подборки «Интересное в мире» пока нет — нет связи с dewiar.pro или выпуск ещё не собран.";
  const list = items.filter(x => (!topic || x.topic === topic) && (+wt[x.topic] || 0) > -2)
    .sort((a, b) => (+b.score + 1.5 * (+wt[b.topic] || 0) - (seen.has(b.id) ? 3 : 0)) - (+a.score + 1.5 * (+wt[a.topic] || 0) - (seen.has(a.id) ? 3 : 0))).slice(0, 4);
  if (!list.length) return "По этой теме в сегодняшней подборке ничего нет.";
  list.forEach(x => worldSeen(x.id));
  setTimeout(() => newsCard({ title: list[0].title, url: list[0].url, world: list[0] }), 1500);
  return "Интересное в мире сегодня (под ответом — карточка «Читать» к первой):\n" + list.map((x, i) => `${i + 1}. [${worldName(x.topic)}] ${x.title} — ${x.text} (${x.source})`).join("\n")
    + "\nРасскажи коротко 1–2 самых интересных своими словами, без ссылок вслух.";
}
/* «Утро с Лирой» (0.57, core/morning.py): компьютер присылает своё утро (конверт own {morning}) — погода по городу из
   его настроек, сотрудники, клиенты, почта. Сводка дня здесь берёт из него то, чего на телефоне нет; доска сотрудников —
   свежее из boss.js; погоду, если утра с компьютера нет, — сама по тому же городу (не дольше 5 секунд). */
function mornTake(m) {
  let cur = null; try { cur = JSON.parse(fileGet("morning.json") || "null"); } catch (e) { }
  if (cur && +cur.at >= +m.at) return;
  fileSave("morning.json", JSON.stringify({ at: +m.at || Date.now(), date: String(m.date || ""), city: String(m.city || "").slice(0, 60), dev: String(m.dev || ""),
    weather: m.weather || null, team: m.team || null, clients: m.clients || null, mail: m.mail || null, radar: m.radar || null }));
}
async function mornFacts() {
  let m = null; try { m = JSON.parse(fileGet("morning.json") || "null"); } catch (e) { }
  const out = [], fresh = m && m.date === isoLocal(new Date()).slice(0, 10), from = m && m.dev ? ` (с компьютера «${m.dev}»)` : "";
  if (fresh && m.weather && m.weather.line) out.push(`Погода (уже узнана): ${m.weather.line}.`);
  else if (m && m.city) {
    try { const t = await Promise.race([weather(m.city, 1), sleep(5000).then(() => "")]); if (t && !/^Ошибка|не нашёлся/.test(t)) out.push("Погода (уже узнана): " + t.split("\n").slice(0, 2).join(" ")); } catch (e) { }
  }
  const tm = typeof bsHas === "function" && bsHas() ? (() => { const s = bsLoad().snap, since = Date.now() / 1000 - 16 * 3600;
    return { late: s.tasks.filter(t => t.late && ["new", "work", "moved"].includes(t.state)), check: s.tasks.filter(t => t.state === "done"), msgs: s.inbox.filter(x => !x.out && +x.ts > since) }; })()
    : fresh ? m.team : null;
  if (tm && (tm.late.length || tm.check.length || tm.msgs.length)) out.push("Сотрудники: " + [tm.late.length ? "просрочено — " + tm.late.slice(0, 4).map(x => `${x.name}: «${x.title}»`).join("; ") : "",
    tm.check.length ? "ждут вашей проверки — " + tm.check.slice(0, 4).map(x => `${x.name}: «${x.title}»`).join("; ") : "",
    tm.msgs.length ? "написали — " + tm.msgs.slice(-3).map(x => `${x.name}: ${x.t || "фото"}`).join("; ") : ""].filter(Boolean).join(". ") + ".");
  if (fresh && m.clients) {
    if ((m.clients.over || []).length) out.push(`Клиенты ждут${from}: ` + m.clients.over.map(x => `${x.name} — ${x.what}`).join("; ") + ".");
    if ((m.clients.today || []).length) out.push(`Клиенты сегодня${from}: ` + m.clients.today.map(x => `${x.time} ${x.name} — ${x.what}`.trim()).join("; ") + ".");
    if ((m.clients.owed || []).length) out.push(`Должны, срок оплаты прошёл${from}: ` + m.clients.owed.map(x => `${x.name} — ${x.what}`).join("; ") + ".");
  }
  // владелец 14.11: «интересное… от Лиры кратко услышать с возможностью перейти»: Радар с компьютера — одна новость и карточка «Читать»
  const rd = fresh && m.radar && (m.radar.items || []).filter(x => x && x.title);
  if (rd && rd.length) {
    out.push(`Радар — своя лента новостей по теме${from}: ` + rd.map(x => `«${x.title}» — ${x.why || ""}`.trim()).join("; ") + ". Если есть место — одной фразой самое интересное отсюда (ссылка будет на карточке).");
    mornFacts.radar = rd[0];
  }
  if (!mornFacts.radar && worldTaste().on && !kidsOn()) {
    try {
      const x = worldPick(await Promise.race([worldLoad(), sleep(6000).then(() => [])]));
      if (x) { out.push(`Интересное в мире (${worldName(x.topic)}): «${x.title}» — ${x.text} Если есть место — одной фразой самое интересное отсюда (ссылка будет на карточке).`);
        mornFacts.radar = { title: x.title, url: x.url, why: x.text, world: x }; }
    } catch (e) { }
  }
  if (fresh && m.mail && m.mail.unread) out.push(`Почта${from}: непрочитанных ${m.mail.unread}` + ((m.mail.people || []).length ? ". От людей: " + m.mail.people.map(x => `${x.from} — «${x.subject}»`).join("; ") : ", всё — рассылки") + ".");
  return out;
}
async function welcomeCheck(shownAt) {
  const w = S.welcome || {};
  if (w.on === false || busy || state !== "idle" || lastUserAct > shownAt || document.hidden) return false;
  const p = welcomePlan(Date.now(), w.seen, w.at, Object.values(mind().tasks || {}), JSON.parse(D.alarms() || "[]"), doneStats(), w.eve);
  if (!p) return false;
  mornFacts.radar = null;
  if (p.kind === "day" && !kidsOn()) { try { p.facts.unshift(...await mornFacts()); } catch (e) { plog("info", "утро: " + e.message); } }
  if (busy || lastUserAct > shownAt || document.hidden) return false;
  await ensureBrain();
  if (!S.llm.base_url || busy || lastUserAct > shownAt) return false;
  S.welcome = Object.assign({}, w, { at: Date.now() }, p.kind === "eve" ? { eve: dayKey(Date.now()) } : {}); saveS();
  plog("info", `👋 ${p.kind === "day" ? "сводка дня" : p.kind === "eve" ? "итог дня" : "с возвращением"} (не было ${p.gone})`);
  const news = mornFacts.radar;
  ask(welcomePrompt(p), { hidden: true });
  if (news && news.url) setTimeout(() => newsCard(news), 2500);
  return true;
}
/* Карточка новости из Радара под сводкой дня: заголовок и «Читать» — открыть полностью в браузере (держится 3 минуты). */
function newsCard(x) {
  if (!x || !/^https?:\/\//.test(String(x.url || ""))) return;
  const w = x.world;
  if (w) worldSeen(w.id);
  showCard(`<div class="rd-news"><small>${esc(w ? trL("Интересное в мире") + " · " + worldName(w.topic) : trL("Радар · самое интересное"))}</small><b>${esc(x.title)}</b>`
    + `<div class="rd-news-b"><button type="button" id="rd-news-go">${esc(trL("Читать"))}</button>`
    + (w ? `<button type="button" class="ghost" id="rd-news-up" title="${esc(trL("Интересно — чаще такое"))}">👍</button><button type="button" class="ghost" id="rd-news-down">${esc(trL("Не моё"))}</button>` : "")
    + `</div></div>`);
  cardSticky = Date.now() + 180000;
  const b = $("#rd-news-go"); if (b) b.onclick = () => { D.openUrl(x.url); if (w) worldFeel(w.topic, 0.5); };
  const up = $("#rd-news-up"), dn = $("#rd-news-down");
  if (up) up.onclick = () => { worldFeel(w.topic, 1); up.disabled = true; up.textContent = "👍 " + trL("Понял"); };
  if (dn) dn.onclick = () => { worldFeel(w.topic, -1.5); cardSticky = 0; showCard(`<div class="rd-news"><small>${esc(trL("Понял — такого будет меньше"))}</small></div>`); setTimeout(clearCard, 2500); };
}
function welcomeSeen() { S.welcome = Object.assign({}, S.welcome || {}, { seen: Date.now() }); saveS(); }
let welcomeT = 0;
function welcomeArm(byIntent) {                   // приложение на экране: через 6 с (успели синхронизироваться) — проверить
  const shownAt = Date.now(), seen = (S.welcome || {}).seen;
  clearTimeout(welcomeT);
  if (!byIntent) welcomeT = setTimeout(() => welcomeCheck(shownAt).finally(welcomeSeen), 6000);
  else welcomeSeen();
  return seen;
}
document.addEventListener("visibilitychange", () => { if (document.hidden) { clearTimeout(welcomeT); welcomeSeen(); } else welcomeArm(false); });
addEventListener("pagehide", welcomeSeen);
setInterval(() => { if (!document.hidden) welcomeSeen(); }, 60000);     // пока открыто — «последний раз видели» свежее

(function boot() {
  applyPersona(); setState("idle"); quietCheck();
  const last = history.filter(m => m.role === "assistant").slice(-1)[0];
  if (D.web && (S.llm.trial || trialOn()) && !loggedIn()) {
    // веб-версия без входа: говорим сразу (пробный разговор); войти — без ограничений и с действиями
    showBot(gfix(`Привет! Я ${persona().name}. Давайте поговорим прямо сейчас — без входа и установки. Нажмите на меня и говорите или напишите.`));
    showCard(`<div class="start" data-first="1"><button class="btn w" onclick="startLogin()">Войти — подробные ответы и дела</button></div>`);
  } else if (!S.llm.base_url && !loggedIn() && autoOk() && !(S.join && !S.join.auto) && trialOn()) {
    // 0.69, первый запуск: говорим сразу (пробный разговор), бесплатный мозг Dewiar подключается сам — без анкеты
    showBot(gfix(`Привет! Я ${persona().name}. Говорите сразу — нажмите на меня или удерживайте и говорите. Мозг Dewiar подключается сам — на старте подарок.`));
    showCard(`<div class="start" data-first="1"><button class="btn w" onclick="openSettings('brain')">Своя модель или код с компьютера</button></div>`);
    setTimeout(() => autoJoin("первый запуск").then(ok => { if (ok) showCard(""); }), 1200);
  } else if (!S.llm.base_url && !loggedIn()) {
    // первый запуск: одна понятная кнопка (отзыв: «не понимаю, как ей мозг включить») — бесплатная проба Dewiar;
    // своя модель, ключ сервиса и код с другого устройства — второй кнопкой
    if (S.join) { showBot(gfix(`Привет! Я ${persona().name}. Заявка отправлена — как только её одобрят, я подключусь сама и скажу. Обычно это быстро.`)); setTimeout(() => joinPoll(false).catch(() => {}), 2500); }
    else showBot(gfix(`Привет! Я ${persona().name}. Чтобы мы могли поговорить, меня нужно один раз подключить — без регистрации, на старте подарок. Это займёт минуту.`));
    showCard(S.join ? `<div class="row2"><button class="btn p" onclick="joinPoll(true).then(d => d && !d.key && toast((d && d.text) || 'Пока ждёт проверки')).catch(e => toast(e.message))" style="flex:1">Проверить</button><button class="btn" onclick="openBrain()" style="flex:1">Другие способы</button></div>`
      : `<div class="start" data-first="1"><button class="btn p w" onclick="openBrain('join')">Подключить мозг Dewiar</button><button class="btn w" onclick="openSettings('devices')">Dewiar уже есть на компьютере — ввести код</button><button class="btn w ghost" onclick="openBrain()">Свой ключ или своя модель</button></div>`); }
  // последний ответ — только свежий (до 20 минут): старый («С возвращением. В 15:00 встреча…» с утра) после каждого
  // запуска и обновления выглядел как новое сообщение (отчёты №52, №53). Он в истории разговора — там его и видно.
  else if (last && last.t && Date.now() - last.t < 20 * 60e3) showBot(last.content.slice(0, 400));
  const it = D.takeIntent(); if (it) { try { handleIntent(JSON.parse(it)); } catch (e) { } }
  welcomeArm(!!it);                                // открыли кнопкой помощника — сразу слушаем, не здороваемся
  if (S.llm.base_url && !it) needPerm(MIC);
  setTimeout(hReady, 0);                           // экран и персонаж готовы — запуск записан для «Здоровья»
  lang2Apply();                                    // второй язык — распознаванию телефона (Speech.java)
  kidsApply();                                     // детский режим: Уго и взрослые кнопки — за PIN
  setTimeout(() => { try { doneInbox(); } catch (e) { } }, 300);   // «Сделано ✓» из уведомлений, пока приложение было закрыто
  setTimeout(() => { try { newsCheck(); } catch (e) { } }, 1200);  // обновились — «Что нового»
  setTimeout(() => { try { if (!document.querySelector(".sheet.on") && window.examCleanCheck) examCleanCheck(); } catch (e) { } }, 4000);   // следы старых экзаменов
  // урок дня (курсы, 28.10): раз в день при первом открытии — карточкой, если ничего другого на экране нет
  const lnTry = () => { try { if ((S.llm.base_url || loggedIn()) && !document.querySelector(".sheet.on") && state === "idle") lnOffer(); } catch (e) { } };
  setTimeout(lnTry, 6000);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) setTimeout(lnTry, 2500); });
  if (!D.web) setTimeout(() => checkUpdate(false), 8000);   // веб-версия всегда свежая: её отдаёт сайт
  // приложение живёт неделями, не закрываясь: проверяем и при возвращении в него, но не чаще раза в 6 часов (29.10)
  let updAt = Date.now();
  if (!D.web) document.addEventListener("visibilitychange", () => { if (!document.hidden && Date.now() - updAt > 6 * 3600e3) { updAt = Date.now(); setTimeout(() => checkUpdate(false), 3000); } });
  setTimeout(() => accountCheck().then(ensureBrain).then(cloudCaps).then(() => tgOn() ? tgStatus().catch(() => {}) : null).then(tgSync), 3000);
  setTimeout(() => syncRun(false), 4000);
  setTimeout(() => radio.refresh(), 10000);
  // радио одно на приложение и переживает пересоздание экрана (Radio.java) — подхватываем, что сейчас играет
  try { const r = JSON.parse(D.radioState() || "{}"); if (r.state) N.ev({ type: "radio", state: r.state, name: r.name || "", error: r.error || "" }); } catch (e) { }
})();
window.DEWIAR_STARTED = true;                      // веб-версия: страница ожила (иначе index.html скажет человеку и сайту — tools/build_web.sh)
