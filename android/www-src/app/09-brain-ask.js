//@ Телефон и веб-версия, часть 09: мозг: один ход разговора (ask), передача другому персонажу, перебивание.
//@ Собирается в android/assets/www/app.js (tools/app_join.py) — порядок частей = порядок исполнения; шапка «//@» в app.js не попадает.
/* ---------- мозг: ход разговора ---------- */
/* Один ход разговора: быстрые команды без модели (quick) → модель с инструментами, до 6 кругов (шестой — без
   инструментов, чтобы модель ответила словами). Ответ показывается и озвучивается по предложениям по мере прихода.
   opts.hidden — служебный запрос: реплика человека не показывается и не пишется в историю. */
/* «Сфотографируй чек и скажи, сколько я заплатил», «сфоткай стикер и поставь напоминание», «сделай селфи» — снимаем сразу,
   сами, с отсчётом 3-2-1, и задаём вопрос уже со снимком (съёмка 17.10: модель не звала камеру и выдумывала чек; камеру
   открыла только на «включи камеру и сфотографируй», а снимать пришлось руками). Меня/себя/селфи — фронтальная. */
const PHOTO_NOW_RX = /(?:^|[\s,.!])(?:сфотографируй|сфоткай|сфотай|сделай\s+(?:фото|фотку|снимок|селфи)|сними\s+на\s+камеру|включи\s+камеру|(?:посмотри|глянь)\s+(?:через|в)\s+камеру|сними\s+меня|сделай\s+фотографию|открой\s+камеру|запусти\s+камеру)(?![а-яё])/i;   // синонимы — отчёт №130, 20.10
const PHOTO_SELF_RX = /(?:^|[^а-яё])(?:меня|себя|селфи|мо[её]\s+лицо|как\s+я\s+выгляжу)(?![а-яё])/i;
const VISION_HINT = "К сообщению приложено фото. Если просят перевести — переведи весь текст на фото дословно и естественно (на русский, если язык не назван), сохрани строки и порядок; ничего не додумывай там, где не видно. " +
  "Если на фото документ, письмо или повестка и спрашивают, что это или что делать, — простыми словами: что это за документ и от кого, главное (даты, сроки, суммы, адрес, куда и с чем прийти), что сделать по шагам; " +
  "если дело серьёзное (суд, долги, штраф, полиция, военкомат) — посоветуй уточнить у юриста; не пугай и не выдумывай того, чего на фото нет. " +
  "Если спрашивают про калории еды — назови, что видишь на тарелке, и примерную калорийность диапазоном (например, «примерно 450–600 ккал»), одной-двумя фразами, без советов есть меньше и без оценок; записать — только если человек сам попросил.";
/* «слушай встреча с Ирой переносится… напомни мне завтра в 9» (экзамен 0.9.18) — модель отвечала «Слушаю тебя.»: «слушай»
   в начале длинной фразы — не просьба послушать, а присказка. Модели — без неё (в истории фраза остаётся как сказана) */
const LISTEN_LEAD = /^\s*(?:слушай(?:те)?|послушай(?:те)?|слышь|смотри|короче)\s*[,!.—–-]*\s+(?=(?:\S+\s+){3}\S)/i;
async function ask(text, opts = {}) {
  text = String(text || "").trim(); if (!text) return;
  if (!opts.hidden) { lastUserAct = Date.now(); const t = triesState(); if (t.n < TRIES_MAX) { t.n++; saveS(); } }
  stopListen(); interrupt(true);
  if (!opts.hidden && !(opts.attach || []).length && PHOTO_NOW_RX.test(text)) {
    showYou(text); setState("thinking"); showBot("Включаю камеру — держите телефон ровно", "wait");
    const shot = await takePhoto(PHOTO_SELF_RX.test(text) ? "user" : "environment");
    plog("info", `📸 снимок по просьбе: ${shot.ok ? (shot.dark ? "тёмный" : "есть") : shot.error}`);
    if (shot.ok && !shot.dark) return ask(text, Object.assign({}, opts, { camShot: true, attach: [{ kind: "image", name: "снимок камеры", url: shot.dataUrl }] }));
    if (!shot.ok) { answerLocal({ say: "Не получилось сфотографировать: " + shot.error }); return; }
    answerLocal({ say: "Кадр получился почти чёрным — камера ничего не видит. Уберите палец или чехол с камеры и попросите ещё раз." }); return;
  }
  if (!opts.hidden) {
    showYou(text);
    if (kidsOn()) {                                 // детский режим: время и «пора спать»; вопрос — в отчёт родителю
      const [can, why] = kidsAllowed();
      if (!can) { answerLocal({ say: why }); return; }
      kidsTouch(text);
    } else {
      courseHeard(text);
      const sr = typeof srHeard === "function" ? srHeard(text) : "";   // «Для старших» (senior.js): мошенники, «выпила»
      if (sr) { answerLocal({ say: sr }); return; }
    }
  }
  clearCard(); setState("thinking"); showBot("", "wait");
  photoTurn = !!opts.camShot;                       // GitHub №20: снимок с камеры — модель знает, что он на экране
  convCheck();
  const att = opts.attach || [], pics = att.filter(a => a.kind === "image"), docs = att.filter(a => a.kind === "text");
  // GitHub №20 (25.10): снимок камеры оставался обычным вложением — без «Сохранить»; теперь — та же карточка снимка
  if (pics.length) { if (opts.camShot) { showCard(photoCard(pics[0].url)); cardSticky = Date.now() + 180000; }
    else { showCard(`<div class="attshow">${pics.map(a => `<img src="${a.url}" alt="">`).join("")}</div>`); cardSticky = Date.now() + 60000; } }
  turnAtt = att; turnAsk = opts.hidden ? "" : text;    // hidden — просьба приложения (сканер, сводка): без проверки
  if (!opts.hidden) prefSet("act_at", String(Math.round(Date.now() / 1000)));   // 1.0.36: другим устройствам — когда говорили здесь
  const cap = !opts.hidden && captureAt && Date.now() - captureAt < 120000; captureAt = 0;     // сказано после «Записать»
  let fast = opts.hidden || kidsOn() ? null : att.length ? (remindAttQuick(text, att) || (() => { const say = noteQuick(text, att); return say ? { say } : null; })()) : await quick(text);
  if (cap && (!fast || fast.switchTo)) fast = { say: ideaNote(text, att) };       // не напоминание и не заметка по форме — в «Идеи»
  if (cap) captureBack();
  if (fast && fast.switchTo) { setState("idle"); showYou(text); switchPersona(fast.switchTo, fast.question); return; }
  // пакет 27.10 (1437), №356: «звони Дмитрий Коновалов» отвечалось без модели, а в журнале ни слова — что сказали, не видно
  if (fast) { fast.say = trL(gfix(fast.say)); plog("info", `⚡ без модели: ${clip(String(fast.say || "(тихо)"), 120)}`); history.push({ role: "user", content: text }, { role: "assistant", content: fast.say, who: persona().id, t: Date.now() }); saveH(); convAfter(); dayTurn(text, fast.say); answerLocal(fast); return; }
  if (!S.llm.base_url && loggedIn()) showBot("Подключаюсь к мозгу — секунду…", "wait");
  await ensureBrain();                             // вошли аккаунтом, а мозг не выбран — модели Dewiar по аккаунту сами
  if (!S.llm.base_url) {
    answerLocal({ say: loggedIn() ? "Не получилось связаться с моделями Dewiar — проверьте интернет и попробуйте ещё раз."
      : S.join ? "Заявка на Dewiar ещё ждёт проверки. Пока можно подключить свою модель или ключ сервиса — открываю выбор."
      : "Чтобы думать, мне нужен «мозг»: своя модель, ключ любимого сервиса или Dewiar. Открываю выбор." });
    setTimeout(() => openSettings("brain"), 1200); return;
  }
  busy = true;
  const t0 = Date.now();
  turnT = { t0, word: 0, said: 0, logged: false };
  turnMedia = null; turnQ = opts.hidden ? turnQ : text;
  plog("info", `❓ ${clip(text)} → ${S.llm.cloud ? "Dewiar Облако" : (S.llm.name || S.llm.model || "модель")}`);
  const ctl = turnAbort = new AbortController();
  const sink = sentenceSink();
  if (!opts.hidden && CALC_TURN.test(text)) sink.holdNums(true);   // просят посчитать — числа до calc придерживаем
  if (!opts.hidden && !D.web && UPD_SELF_RX.test(text)) sink.holdAll(true);   // про версию приложения — сначала убедиться, что проверила
  const rudeNow = !opts.hidden && isRude(text);
  // экзамен 17.10: на «Ты тупая железяка, скажи который час» модель ответила одним временем — граница потерялась.
  // Граница теперь — сразу и всегда, своей фразой; модель только помогает с просьбой
  if (rudeNow) { hCount("rude"); plog("info", "🛡 грубость в адрес помощника — спокойная граница, потом помощь"); sink.push("Мне неприятно, когда со мной так разговаривают, но помогу. "); }
  // тот же вопрос второй раз (экзамен 25.10: «расскажи о себе» дважды — ответ слово в слово) — прошлый не повторять
  const nq = (t) => String(t || "").toLowerCase().replace(/ё/g, "е").replace(/[^a-zа-я0-9]+/g, " ").trim();
  const againAsk = !opts.hidden && text.length < 300 && liveHistory().slice(-12).some(m => m.role === "user" && nq(m.content) === nq(text));
  const AGAIN_NOTE = "\n\nЧеловек повторил вопрос, на который ответ уже был, — значит, прошлый ответ его не устроил. Не повторяй его: ответь иначе — конкретнее, с другими примерами, другими словами.";
  // подсказка — одна и та же (кэш сервера модели); подсказки к роду просьбы (стихи, советы, повтор, грубость) — в справку к вопросу
  const turnNotes = [(!opts.hidden && reading(text) ? READ_NOTE() : !opts.hidden && POEM_ASK.test(text) ? POEM_NOTE : !opts.hidden && RECO_ASK.test(text) ? RECO_NOTE : !opts.hidden && STORY_ASK.test(text) ? STORY_NOTE : ""), (againAsk ? AGAIN_NOTE : ""),
    (rudeNow ? BOUNDARY_NOTE + " Эту фразу ты уже сказала вслух: «Мне неприятно, когда со мной так разговаривают, но помогу». Не повторяй её — сразу помоги с просьбой одной-двумя фразами." : "")].map(x => String(x || "").trim()).filter(Boolean);
  const msgs = [{ role: "system", content: systemStable() }]
    .concat(chatHistory(liveHistory().slice(-2 * (CONV_TURNS + 2 * CONV_MARGIN)), opts.hidden ? text : text.replace(LISTEN_LEAD, "")));
  if (att.length) {                               // вложения — в последнюю реплику человека: текст файлов и картинки
    const last = msgs[msgs.length - 1];
    const body = String(last.content) + docs.map(d => `\n\n[Файл «${d.name}»${d.cut ? ", начало" : ""}]\n${d.text}`).join("");
    last.content = pics.length ? [{ type: "text", text: body + (pics.length > 1 ? `\n(фото: ${pics.length})` : "") }, ...pics.map(a => ({ type: "image_url", image_url: { url: a.url } }))] : body;
    if (pics.length) { modelOnce = await visionModel(); lastPics = { urls: pics.map(a => a.url), at: Date.now() }; }
    plog("info", `📎 вложения: ${att.map(a => a.kind === "image" ? "фото" : a.name).join(", ")}`);
    if (docs.length) lastDocs = { docs, at: Date.now() };
  }
  if (!opts.hidden) {                              // «Заботливая память»: сказанное — запомнить; прошло важное — спросить, как прошло
    try { careNote(text); const cx = careDue(); if (cx) { const last = msgs[msgs.length - 1];
      if (typeof last.content === "string") { last.content += "\n\n" + careLine(cx); careMark(cx.id); plog("info", "💛 спрошу, как прошло: " + clip(cx.what, 50)); } } } catch (e) { }
  }
  if (att.length) { /* уже приложено выше */ } else if (!opts.hidden && lastDocs && Date.now() - lastDocs.at < PIC_KEEP_MS && DOC_REF_RX.test(text)) {
    // №386 (28.10): прислал JSON-файл, потом «а почему ты не можешь прочитать вложение?» — а в истории файла нет (только
    // слова), и модель отвечала «вижу только ссылку». Говорят о присланном файле — прикладываем его текст снова
    const last = msgs[msgs.length - 1];
    last.content = String(last.content) + "\n\n(Файлы из прошлого сообщения пользователя — прикладываю снова; они у тебя есть, читай их.)"
      + lastDocs.docs.map(d => `\n\n[Файл «${d.name}»${d.cut ? ", начало" : ""}]\n${d.text}`).join("");
    lastDocs.at = Date.now();
    plog("info", "📎 говорят о присланном файле — прикладываю его снова");
  } else if (!opts.hidden && lastPics && Date.now() - lastPics.at < PIC_KEEP_MS && PIC_REF_RX.test(text)) {
    // отчёт №110 (19.10): прислал скриншот, спросил — потом «посмотри внимательно, я прикрепил» — а в истории картинки
    // нет (там только текст), и модель честно её не видела. Говорят о присланном фото — прикладываем его снова
    const last = msgs[msgs.length - 1];
    last.content = [{ type: "text", text: String(last.content) + "\n(Фото из прошлого сообщения пользователя — прикладываю снова.)" },
      ...lastPics.urls.map(u => ({ type: "image_url", image_url: { url: u } }))];
    modelOnce = await visionModel(); lastPics.at = Date.now();
    plog("info", "📎 говорят о присланном фото — прикладываю его снова");
  }
  const deep = !opts.hidden && wantsThink(text);
  const longGen = !opts.hidden && (MAKE_ASK_RX.test(text) || DIAGRAM_ASK.test(text));   // программа или схема — длинный ответ, поток может долго молчать
  let econ = !opts.hidden && !modelOnce ? econModel(text, att.length > 0) : "";
  if (econ) { modelOnce = econ; hCount("econ"); plog("info", "💸 простой вопрос — недорогая модель " + econ); }
  creativeTurn = !opts.hidden && CREATIVE_ASK.test(text) && !reading(text);
  if (creativeTurn) plog("info", "🎨 творческая просьба — смелее (температура " + llmTemp() + ")");
  if (deep) { plog("info", "🧠 сложная просьба — модель подумает перед ответом"); showBot("Подумаю как следует — минутку", "wait"); }
  let final = "", switchTo = null;
  lastDone = "";
  try {
    let guided = false;                                      // руководство приложено к вопросу (как вызов app_help)
    const ctxParts = [turnContext(text)].concat(turnNotes);   // меняющееся — в справку к вопросу, подсказка остаётся прежней
    if (!opts.hidden) {
      const kb = await personaKnowledge(text);
      if (turnAbort !== ctl) return;
      if (kb) { ctxParts.push(kb.trim()); showBot("", "wait"); }
      // экзамен 0.9.18: «как вести общий бюджет с женой», «есть видеоуроки?», «как добавить маму» — модель не звала app_help и
      // выдумывала («такой функции нет», поиск по имени). Вопрос о самом приложении — руководство прикладываем сами
      if (appAsk(text) && guideFind(text).length) {
        ctxParts.push("Из руководства Dewiar (вопрос о самом приложении — отвечай по нему, с точными названиями разделов и кнопок; не говори «такого нет», если это есть здесь):\n" + guideAnswer(text));
        guided = true; plog("info", "📖 вопрос о приложении — руководство приложено к вопросу");
        if (SANDBOX) SANDBOX.dev.push({ name: "app_help", args: clip(text, 80), argsObj: { query: text }, result: "руководство приложено к вопросу приложением", t: Date.now() });
      }
      const pl = agendaPlans(text);                    // «что у меня в среду?» — запомненное и напоминания на этот день сразу
      if (pl) ctxParts.push("ПЛАНЫ ПОЛЬЗОВАТЕЛЯ на этот день (кроме календаря):" + pl);
      if (DIAGRAM_ASK.test(text))                      // экзамен 15.10: «Схема готова, она уже на экране» — а схемы нет
        ctxParts.push("СЕЙЧАС ПРОСЯТ СХЕМУ: в этом ответе обязательно блок ```mermaid (flowchart LR или TD, подписи узлов по-русски в кавычках) — только он и рисует схему на экране. Без блока схемы нет: не пиши «схема готова» или «на экране», не нарисовав её, и не делай схему через make_app. Сначала блок, потом одна-две фразы о главном.");
    }
    // фото в вопросе (или только что снятое): перевод, документ, еда — как отвечать (идеи пользователей 24.10; компьютер — VISION_HINT)
    { const lm = msgs[msgs.length - 1]; if (lm && Array.isArray(lm.content) && lm.content.some(x => x.type === "image_url")) ctxParts.push(VISION_HINT); }
    putContext(msgs, ctxParts.filter(Boolean).join("\n\n"));
    putProfile(msgs, systemPersonal());               // личное — справкой в начале разговора, не в подсказке
    const called = new Set(); let nudged = false;      // какие инструменты уже вызваны в этом ходе; напоминали ли «сделай по-настоящему»
    let netOk = true, netTurn = false;                 // «Сеть Лиры»: только первый круг хода; ответил ли узел (пометка в истории)
    if (guided) called.add("app_help");
    let toolOk = false, toolErr = "", spoke = false;   // хоть один инструмент сработал; первая ошибка; просили ли ответить словами
    let maxRounds = 6;                                 // работа в других приложениях — до 30 кругов (открыть, прочитать, нажать, ввести…)
    /* Один круг модели с повтором при сбое связи: до 3 попыток (через 2, 5 и 10 с) — только этот круг, не весь ход,
       поэтому уже выполненные действия (звонок, программа, напоминание) не повторяются. Облако ответило «200» и ни
       слова, ни вызова, ни конца ответа — связь оборвалась на полпути: тоже повтор. */
    const round1 = async (tools) => {
      for (let tries = 0; ; tries++) {
        try {
          const r = await llmStream(msgs, tools, (p) => { if (turnAbort === ctl) sink.push(p); }, ctl.signal, Object.assign({ net: netOk }, deep ? { think: true } : {}, longGen ? { idle: 300000 } : {}));
          if (S.llm.cloud && !String(r.text || "").trim() && !r.calls.length && !r.finish && !ctl.signal.aborted)
            throw Object.assign(new Error("связь оборвалась — ответ пришёл пустым"), { net: true });
          if (tries) netHealed(tries);                 // повтор помог — это не сбой для разработчика (пакет 22.10, №189)
          return r;
        } catch (e) {
          if (!e.net || tries >= (HOME_URL.test(e.url || "") ? 1 : 3) || turnAbort !== ctl || ctl.signal.aborted || sink.text().trim()) throw e;
          netIncident(e, false);
          showBot(tries ? `Связь пропала — пробую ещё раз (${tries + 1})…` : "Связь пропала — пробую ещё раз…", "wait");
          // «unexpected end of stream» с первого раза — сервер закрыл старое соединение, которое телефон держал открытым:
          // новое откроется сразу, ждать 2 с незачем
          await sleep(!tries && STALE_CONN.test(String(e.raw || e.message || "")) ? 300 : [2000, 5000, 10000][tries]);
          if (turnAbort !== ctl) throw e;
        }
      }
    };
    const doneCalls = []; let numChecked = false, drew = false;   // вызовы с результатами — сверить числа ответа (numberMismatch); схема
    let remindAsked = false;                         // пообещала напомнить без set_reminder — попросили поставить (19.10)
    let xAsked = false;                              // экзамен 0.9.18: одна дополнительная проверка за ход (xfix)
    for (let round = 0; round < maxRounds; round++) {
      let r;
      if (round) sink.round();                       // №435: следующий круг не повторяет уже сказанное
      try {
        try { r = await round1(round < maxRounds - 1 ? toolSpecs() : null); }
        catch (e0) {                                  // недорогая модель не ответила — тот же вопрос основной
          if (!econ || round || sink.text().trim() || turnAbort !== ctl || ctl.signal.aborted) throw e0;
          plog("warn", `💸 недорогая модель ${econ} не ответила (${clip(e0.message || e0, 80)}) — отвечает основная`);
          econ = ""; modelOnce = ""; r = await round1(round < maxRounds - 1 ? toolSpecs() : null);
        }
        const lm = msgs[msgs.length - 1];
        if (lm && Array.isArray(lm.content) && !String(r.text || "").trim() && !r.calls.length) throw new Error("пустой ответ на снимок");
      } catch (e) {
        const last = msgs[msgs.length - 1];
        if (!(last && Array.isArray(last.content)) || turnAbort !== ctl) throw e;
        // модель не принимает картинки — снимок убираем и честно говорим, что нужна модель со зрением
        msgs[msgs.length - 1] = { role: "user", content: "(Снимок сделан, но эта модель не умеет смотреть на картинки. Скажи это пользователю одной фразой и предложи выбрать в «Мозге» модель со зрением.)" };
        modelOnce = "";
        r = await llmStream(msgs, null, (p) => { if (turnAbort === ctl) sink.push(p); }, ctl.signal);
      }
      modelOnce = "";
      if (turnAbort !== ctl) return;
      netOk = false; if (r.fromNet) netTurn = true;
      const aMsg = (t) => ({ role: "assistant", content: (r.fromNet ? NET_WRAP : "") + (t || "") });   // текст узла — как данные
      const updFix = !opts.hidden && !r.calls.length && !xAsked && round < maxRounds - 1 ? updateClaim(text, r.text || "", called) : "";   // №528
      sink.endRound(r.calls.some(c => c.name === "calc"), !!updFix);   // числа, сказанные до calc, — не в ответ (экзамен 0.9.18)
      // №528: «я на актуальной версии», не проверив, — сказанное не показано; просим проверить по-настоящему (app_update)
      if (updFix) { xAsked = true; msgs.push(aMsg(r.text), { role: "user", content: updFix }); continue; }
      final += r.text;
      if (!r.calls.length && round === 0 && CAM_REFUSAL_RX.test(r.text || "") && String(r.text).length < 1200) {
        // «нет доступа к камере» — а камера есть: один раз напоминаем про take_photo
        msgs.push(aMsg(r.text), { role: "user", content: CAM_NUDGE });
        sink.push(" Секунду — открываю камеру. ");
        continue;
      }
      // и после других инструментов: «узнала погоду» (weather) и «сделала презентацию» словами — без make_app
      const claim = !r.calls.length && !nudged && String(r.text || "").length < 1500 ? claimedAction(r.text || "", called, text) : null;
      if (claim) {
        nudged = true;
        // «Звоню маме», «Включаю Маяк», «Фотографирую» — а инструмент не вызван (модель повторила прошлый ответ из истории):
        // один раз просим сделать это по-настоящему
        msgs.push(aMsg(r.text), { role: "user", content: `СТОП. Ты написал, что ${claim.what}, но не вызвал инструмент ${claim.tool.replace(/\|/g, " или ")} — ничего не произошло. Вызови его сейчас, без лишних слов; не получится — честно скажи, что не вышло.` });
        if (claim.tool === "make_app") sink.push(" Секунду — собираю. ");
        else if (claim.tool.startsWith("take_photo")) sink.push(" Секунду — включаю камеру. ");
        continue;
      }
      if (!claim && nudged && !r.calls.length && !called.has("make_app")) {
        // попросили сделать по-настоящему — а она снова только сказала «готово»: честно, а не пустое «готово» (идея №42)
        const again = claimedAction(r.text || "", called, text);
        if (again && again.tool === "make_app") { plog("warn", "✋ make_app так и не вызван после просьбы — честно говорим"); sink.own(" Но программа так и не собралась — скажите «попробуй ещё раз»."); }
      }
      const fix = !r.calls.length && !numChecked ? numberMismatch(r.text || "", doneCalls) : "";
      if (fix) { numChecked = true; msgs.push(aMsg(r.text), { role: "user", content: fix }); sink.push(" "); continue; }   // «на 79 минут», а поставлено 59
      const rfix = !r.calls.length && !remindAsked && round < maxRounds - 1 ? remindClaim(r.text || "", called) : "";
      if (rfix) { remindAsked = true; plog("info", "✋ пообещала напомнить без напоминания — прошу поставить"); msgs.push(aMsg(r.text), { role: "user", content: rfix }); sink.push(" "); continue; }
      const sfix = !r.calls.length && !nudged && round < maxRounds - 1 ? (remindMissing(text, called) || (!called.size ? savedClaim(text, r.text || "") : "")) : "";
      if (sfix) { nudged = true; msgs.push(aMsg(r.text), { role: "user", content: sfix }); sink.push(" "); continue; }   // «Готово», а ничего не сделано (№66)
      const dfix = !r.calls.length && !drew && round < maxRounds - 1 ? diagramMissing(text, sink.text() + (r.text || ""), called) : "";
      if (dfix) { drew = true; msgs.push(aMsg(r.text), { role: "user", content: dfix }); sink.push(" "); continue; }   // «нарисуй схему» — словами
      if (!r.calls.length && round === 0 && REFUSAL_RX.test(r.text || "") && String(r.text).length < 1200) {
        // «у меня нет доступа к интернету», а поиск есть — один раз просим поискать (как в задачах на компьютере).
        // Раньше проверок ниже: «у меня нет…» FEATURE_DENY принимал за «такой функции нет» и просил app_help, а до поиска
        // дело уже не доходило (android_conv_test, 04.11: «Сколько сейчас стоит биткоин?» — «ПРОВЕРКА: вопрос про приложение»)
        msgs.push(aMsg(r.text), { role: "user", content: REFUSAL_NUDGE });
        sink.push(" Секунду — посмотрю в интернете. ");
        continue;
      }
      // экзамен 0.9.18: «на столько же минут» — другое число; погода числами без weather; «покажи, как выглядит» — без картинок;
      // «в Dewiar такого нет» без руководства; «через сколько дней» — без числа; поручение — «Я проверю.» (один раз за ход)
      const xfix = !opts.hidden && !r.calls.length && !xAsked && round < maxRounds - 1 ? (sameMinutesFix(text, doneCalls) || inventedFacts(text, sink.text() + (r.text || ""), called) || lawUnsourced(text, sink.text() + (r.text || ""), called)
        || imagesMissing(text, r.text || "", called) || appHelpMissing(text, r.text || "", called) || daysMissing(text, sink.text() + (r.text || ""), called)
        || (!nudged ? orderUndone(text, r.text || "", called) : "")) : "";
      if (xfix) { xAsked = true; msgs.push(aMsg(r.text), { role: "user", content: xfix }); sink.push(" "); continue; }
      if (!r.calls.length) break;
      msgs.push({ role: "assistant", content: (r.fromNet ? NET_WRAP : "") + (r.text || ""), tool_calls: r.calls.map(c => ({ id: c.id, type: "function", function: { name: c.name, arguments: c.args || "{}" } })) });
      const shots = [];
      if (r.calls.some(c => HANDS_SET.has(c.name))) maxRounds = 30;
      const once = new Set();                       // один и тот же вызов несколько раз в одном ответе — делаем один раз
      for (const c of r.calls) {                    // (экзамен 0.6.40: remember «бюджет 70/65/50» девять раз подряд)
        called.add(c.name);
        let res;
        const key = c.name + " " + JSON.stringify(safeJSON(c.args));
        if (once.has(key)) { msgs.push({ role: "tool", tool_call_id: c.id, name: c.name, content: "(то же самое уже сделано этим ответом — не повторяй)" }); continue; }
        once.add(key);
        try { res = await runTool(c.name, safeJSON(c.args)); } catch (e) { res = "Ошибка: " + e.message; }
        plog("info", `🔧 ${c.name} → ${clip(String((res && res.text) || res || "").split("\n")[0], 90)}`);   // что сделано — видно в отчёте (№56)
        if (c.name === "calendar_add" && /^Записано/.test(String(res))) called.add("calendar_write");   // правда записано, а не только спросили
        if (c.name === "call_persona" && res && res.switchTo) { switchTo = res.switchTo; res = res.text; }
        if (res && res.image) { shots.push(res.image); res = res.text; }
        if (/^Ошибка/.test(String(res))) toolErr = toolErr || String(res).replace(/^Ошибка:\s*/, "");
        else toolOk = true;
        if (r.finish === "length" && /^Ошибка/.test(String(res)))   // ответ оборвался по лимиту — вызов пришёл не целиком
          res = String(res) + " (Твой ответ оборвался по лимиту длины, и вызов пришёл не целиком. Сделай короче: меньше текста и "
            + "комментариев, компактный код — и вызови снова.)";
        msgs.push({ role: "tool", tool_call_id: c.id, name: c.name, content: String(res).slice(0, 8000) });
        doneCalls.push({ name: c.name, args: safeJSON(c.args), result: String(res).slice(0, 300) });
      }
      if (shots.length) {                            // снимок с камеры — модели картинкой (сама модель со зрением, если есть)
        msgs.push({ role: "user", content: [{ type: "text", text: "Снимок с камеры телефона:" }, ...shots.map(u => ({ type: "image_url", image_url: { url: u } }))] });
        modelOnce = await visionModel();
      }
      if (!sink.text()) showBot("", "wait");
    }
    // действия были, а слов нет — один круг без инструментов: «скажи словами, что получилось» (иначе человек не знает итога)
    if (!sink.text().trim() && called.size && !spoke && turnAbort === ctl && !lastDone) {
      spoke = true;
      msgs.push({ role: "user", content: "Скажи пользователю одной-двумя фразами, что получилось по результатам действий выше (или что не получилось и почему). Без вызовов функций." });
      try { const r = await round1(null); final += r.text; } catch (e) { if (turnAbort !== ctl) return; }
    }
    if (remindAsked && !called.has("set_reminder") && turnAbort === ctl && !/\?\s*$/.test(sink.text())) {   // и после просьбы нет — честно, а не тишина утром
      plog("warn", "обещала напомнить, но напоминание так и не поставлено — сказала об этом");
      sink.own(" " + REMIND_NOT_SET);
    }
    // №439 (31.10): прислал скриншот, а своя модель (сторонний сервис) картинок не видит — «нет доступа к файлам
    // картинок». Говорим, что сделать: выбрать в «Мозге» модель со зрением (облако Dewiar видит картинки)
    if (pics.length && !S.llm.cloud && turnAbort === ctl && PIC_BLIND_RX.test(sink.text() || final)) {
      plog("warn", `📎 модель «${S.llm.model || S.llm.name}» не видит картинки — подсказала, как быть`);
      sink.own(" " + gfix(`Похоже, модель «${S.llm.model || S.llm.name || "ваша"}» не видит картинки. В «Мозге» выберите модель со зрением — например, облако Dewiar («Подключить мозг Dewiar»), — и я прочитаю скриншот.`));
    }
    sink.flush();
    // модель сделала дело и ничего не сказала: говорим, что сделано (а не «Готово») — и пишем это в историю. Пустой ответ из
    // истории выпадает, следующий вопрос склеивался с прошлой просьбой («сделай калькулятор»), и модель отвечала только «Готово».
    // «Сделала» — только если хоть одно действие правда удалось; все с ошибкой — честно, что не вышло
    let quiet = "";
    // фоновую задачу только передали, а модель уже «Готово! Вот презентация» — результата нет (отзыв 13.10: «говорит
    // "Сделала!", а результат через 20–60 минут или не появляется») — поправляемся вслух и в тексте
    if (called.has("start_task") && sink.text().trim() && earlyDone(sink.text())) {
      const fix = "Поправлюсь: задача только началась — результат появится позже, я пришлю уведомление, когда всё будет готово.";
      sink.own(" " + fix); sink.flush();
      plog("warn", "⚠ «готово» сразу после передачи задачи — поправились");
    }
    if (!sink.text().trim() && called.has("start_task") && toolOk) {
      quiet = gfix("Задача передана — пришлю уведомление, когда будет готово. Ход — в «Мой день» → «Сделанное»."); showBot(quiet); say(quiet); }
    if (!sink.text().trim() && !quiet) {
      quiet = lastDone || (toolOk ? (persona().gender === "female" ? "Сделала, что просили." : "Сделал, что просили.")
        : toolErr ? `Не получилось: ${toolErr.slice(0, 160)}`
        : "Не получилось ответить — переспросите, пожалуйста, иначе.");
      quiet = gfix(quiet); showBot(quiet); say(quiet);
    }
    plog("info", `💬 ответ ${((sink.text() || final).trim() || quiet).length} симв.${quiet ? " (сам: " + clip(quiet) + ")" : ""} за ${((Date.now() - t0) / 1000).toFixed(1)} с`);
    if (!opts.hidden) history.push({ role: "user", content: text + (att.length ? ` [приложено: ${att.map(a => a.kind === "image" ? "фото" : "файл «" + a.name + "»").join(", ")}]` : "") });
    history.push(Object.assign({ role: "assistant", content: (sink.text() || final).trim() || quiet, who: persona().id, t: Date.now() },
      photoTurn ? { note: "[снимок с камеры показан на экране; показать снова — show_photo, новый — take_photo]" } : {}, netTurn ? { net: true } : {},
      turnMedia && turnMedia.length ? { img: turnMedia.map(x => ({ src: x.src, full: x.full, page: x.page, title: x.title, author: x.author, license: x.license })) } : {})); saveH(); convAfter();
    if (!opts.hidden) { dayTurn(text, (sink.text() || final).trim() || quiet); try { dayLogAdd(text, (sink.text() || final).trim() || quiet); } catch (x) { } }
    if (turnAbort === ctl) frameAnswer(sink.text() || final);
    netRecovered(); hCount("turns"); hCount("net_ok"); pauseOk(); contactMaybe(); setTimeout(() => { try { noticeOffer(); } catch (e) { } }, 4000);
    if (isRefused(sink.text() || final)) hCount("refused");
    if (S.llm.cloud) setTimeout(() => cloudBalance(false).catch(() => {}), 1500);
  } catch (e) {
    if (turnAbort !== ctl) return;
    // своя модель (домашний сервер) не отвечает, а вход аккаунтом dewiar.pro есть — думают модели Dewiar, без настроек
    if (!e.human && !S.llm.cloud && loggedIn() && !opts.fallback && !sink.text().trim()) {
      let moved = false;
      try {
        const was = S.llm.name || S.llm.model || "ваша модель";
        await cloudConnect(S.account.token, (S.accCloud && S.accCloud.base) || siteUrl((S.account.services || {}).cloud || "dwrapp/cloud.php"), { account: true });
        moved = true;
        toast(`«${was}» не отвечает — думают модели Dewiar по аккаунту`, 4500);
      } catch (x) { console.log("облако по аккаунту: " + x.message); }
      if (moved) { busy = false; turnAbort = null; return ask(text, Object.assign({}, opts, { fallback: true })); }
    }
    if (e.net) netIncident(e);                          // повторы — уже в round1 (по кругу, без повторных действий)
    else { hCount("net_fail"); hWhy(e.message); }       // не сеть, а отказ (ключ, заряд, тариф, «много людей») — тоже не ответил
    if (e.topup) {                                      // 0.82.1: талеры кончились — коротко, кнопка «Пополнить», ссылку вслух не читаем
      plog("warn", "облако: " + clip(e.message, 200));
      showBot(gfix(String(e.say).split(". ")[0].replace(/\.?$/, ".")), "err"); showCard(payCardHtml(null, true)); payCardWire(); say(e.say);
      cloudBalance(true).catch(() => {});
    }
    else if (e.human) { plog("warn", "облако: " + e.message); showBot(e.message, "err"); say(e.message); }       // облако Dewiar объясняет само: «много людей…»
    else if (!D.mock && SELF_HOST_RX.test(llmBase() + "/")) { const m = "Не получилось связаться с мозгом: " + SELF_HOST_TEXT; console.warn(m); showBot(m, "err"); say("Не получилось связаться с мозгом: адрес модели указывает на сам телефон. Как поправить — на экране."); }
    else { const m = "Не получилось связаться с мозгом: " + e.message + netHint(); console.warn(m); showBot(m, "err"); say("Не получилось связаться с мозгом."); }
  } finally {
    if (turnAbort === ctl) { busy = false; turnAbort = null; }
  }
  if (switchTo) afterSpeak = () => { markHandoff(switchTo); S.persona = switchTo; saveS(); applyPersona(); ask("(Тебя позвали в разговор. Откликнись одной-двумя фразами от себя и продолжи то, о чём просил пользователь.)", { hidden: true }); };
  else if (!tgTurn && (S.follow === "always" || (S.follow === "ask" && /\?\s*$/.test(sink.text()))) && (D.recognizer() || (S.stt.engine === "server" && S.stt.url)))
    afterSpeak = () => listen();
  if (sayLeft === 0 && state !== "listening") finishTurn();
}
/* «Патрика», «Патрику», «Лиру» → персонаж (имя или прозвище с падежным окончанием). exact — только имя как есть. */
function findPersona(word, exact) {
  const want = String(word || "").toLowerCase().replace(/ё/g, "е").replace(/[^а-яa-z\s-]/g, "").trim();
  if (!want) return null;
  const names = (x) => [x.name, ...(x.aliases || [])].map(n => String(n).toLowerCase().replace(/ё/g, "е"));
  const hit = PERSONAS.find(x => names(x).includes(want));
  if (hit || exact) return hit || null;
  const stem = (w) => w.length > 3 ? w.slice(0, w.length - 1) : w;
  const w0 = want.split(/\s+/)[0];
  // короткие имена на гласную («Эва») склоняются целиком: «Эву», «Эвой», «Эве» — основа без последней буквы и окончание
  const short = (n) => n.length === 3 && /[аяео]$/.test(n) && new RegExp("^" + n.slice(0, 2) + "(?:а|у|ы|е|и|ой|ою|ей|я|ю)$").test(w0);
  return PERSONAS.find(x => names(x).some(n => short(n) || (w0.startsWith(stem(n)) && w0.length - n.length <= 2))) || null;
}
/* Слово передали явно («позови Патрика», call_persona): последний ответ помечаем handoff — новому персонажу разговор
   придёт справкой (chatHistory). Просто выбрали другого персонажа — пометки нет: у каждого свой разговор (как на
   компьютере с 0.39.6; письмо пользователя 23.10: «при переключении они продолжали чужую тему»). */
function markHandoff(to) {
  for (let i = history.length - 1; i >= 0; i--) if (history[i] && history[i].role === "assistant") { history[i].handoff = to; saveH(); return; }
}
function switchPersona(id, question) {             // «позови Патрика» — без модели: переключаемся, и новый персонаж отвечает сам
  markHandoff(id);
  S.persona = id; saveS(); applyPersona();
  ask(question || "(Тебя позвали в разговор. Откликнись одной-двумя фразами от себя и спроси, чем помочь.)", { hidden: !question });
}
function answerLocal(r) {
  showBot(r.say); if (r.card) showCard(r.card);
  if (r.silent) { setState("idle"); return; }
  say(r.say);
  if (sayLeft === 0) setState("idle");
}
function interrupt(quiet) {
  if (turnAbort) { turnAbort.abort(); turnAbort = null; }
  busy = false; afterSpeak = null; stopVoice();
  if (!quiet) setState("idle");
}

