//@ Телефон и веб-версия, часть 06: слух и голос (фразы по очереди, Tts.java).
//@ Собирается в android/assets/www/app.js (tools/app_join.py) — порядок частей = порядок исполнения; шапка «//@» в app.js не попадает.
/* ---------- слух ----------
   Распознаёт телефон (SpeechRecognizer) или сервер (свой или Dewiar Облако — GigaAM по ключу или аккаунту, cloudEars).
   Сторож sttGuard: распознаватель телефона бывает «есть, но молчит» (планшеты без сервисов Google — Huawei и др.):
   не начал слушать за 4 с — переходим на сервер Dewiar насовсем (S.stt.auto) или честно говорим, что слуха нет;
   замолчал посреди (нет событий 15 с) или не отпускает после нажатия «стоп» — сами заканчиваем, кнопка не залипает. */
let sttActive = false, heardPartial = "", sttWatch = null, sttStarted = false, sttVia = "", sttGen = 0, sttOnce = null;
function sttGuard(ms, why) { clearTimeout(sttWatch); sttWatch = ms ? setTimeout(() => sttStall(why), ms) : null; }
/* Событие слуха из прежнего сеанса (поле g от Speech.java; после cancel ещё приходит «отменено») — не наше: иначе оно
   сбило бы новый сеанс, и кнопка осталась бы «слушаю». В браузере-заглушке поля g нет — принимаем всё. */
let sttT0 = 0;                     // когда начали слушать — в журнал идёт, за сколько пришёл текст
const clip = (t, n = 120) => { t = String(t || "").replace(/\s+/g, " ").trim(); return t.length > n ? t.slice(0, n) + "…" : t; };
const sttMine = (e) => e.g === undefined || e.g === sttGen;
/* Распознавание Dewiar Облака: вход аккаунтом или ключ dw- и в облаке есть распознавание -> {url, key} или null. */
function cloudEars() {
  if (loggedIn() && S.accCloud && S.accCloud.stt) return { url: S.accCloud.base.split("?")[0] + "?p=", key: S.account.token };
  if (S.llm.cloud && S.llm.stt) return { url: cloudBase() + "?p=", key: S.llm.api_key };
  return null;
}
/* Сервер не пустил слушать (402 — талеры или заряд закончились, 429 — дневной лимит, 401/403 — ключ) — раньше было
   «Не получилось услышать: сервер распознавания ответил 402», и всё. Теперь, если у телефона есть своё распознавание,
   слушает оно — 30 минут или до перезапуска приложения, потом снова пробуем сервер (вдруг пополнили). */
let sttSysUntil = 0;
/* Распознавание телефона (Google) — через интернет: на слабой мобильной сети (24.10, владелец: «не получилось услышать:
   нет сети для распознавания» через раз) оно обрывается, а сказанное пропадает. Теперь сбой сети — не ошибка на экране:
   есть распознавание Dewiar — эту фразу слушает сервер (он ждёт дольше), два сбоя за 10 минут — сервер слушает 10 минут;
   нет — один тихий повтор «скажите ещё раз». */
let sttNetUntil = 0, sttNetFails = [], sttNetRetryAt = 0;
const STT_NET = [1, 2];                             // SpeechRecognizer.ERROR_NETWORK_TIMEOUT, ERROR_NETWORK
const STT_DENIED = /ответил (40[1-3]|429)\b/;
function sttServerUrl(u) { return u.replace(/\/+$/, "") + (/(transcriptions)$/.test(u) ? "" : "/audio/transcriptions"); }
async function listen() {
  stopVoice();
  if (!(await needPerm(MIC))) { fsMark("mic_no"); showBot("Без микрофона я вас не услышу. Разрешите микрофон — или напишите текстом.", "err"); return; }
  fsMark("mic_ok");
  // ответ не стираем, пока человек не сказал новое (№241: «чат закрывается сам, дочитывать нужно в чате» — Лира
  // спросила «…?», слушание включилось само и убрало ответ); новый вопрос (ask) сменит его сам
  heardPartial = ""; sttUserStop = false; showYou(dict ? dict + " …" : ""); clearCard();
  if (/\b(err|wait)\b/.test($("#bot").className)) showBot("");
  setState("listening"); sttActive = true; sttStarted = false; if (!dict) D.vibrate(18);
  let server = S.stt.engine === "server" && S.stt.url ? { url: S.stt.url, key: S.stt.key || "", model: S.stt.model || "" } : null;
  if (!server && (!D.recognizer() || sttOnce)) { const c = sttOnce || cloudEars(); sttOnce = null; if (c) server = { url: c.url, key: c.key, model: "gigaam" }; }
  if (!server && Date.now() < sttNetUntil) { const c = cloudEars(); if (c) server = { url: c.url, key: c.key, model: "gigaam" }; }   // сеть Google сбоит — сервер
  if (server && Date.now() < sttSysUntil && D.recognizer()) server = null;     // сервер не пускает (талеры) — слушает телефон
  if (!server && !D.recognizer() && D.recognizerAny && D.recognizerAny()) D.useAnyRecognizer();   // №712: iPhone без входа — распознавание Safari
  if (!server && !D.recognizer()) {
    sttActive = false; setState("idle");
    showBot("В этом устройстве нет распознавания речи. Войдите аккаунтом dewiar.pro (Настройки → Мозг) — слушать будет сервер Dewiar. Или напишите текстом.", "err"); return;
  }
  sttVia = server ? "server" : "system"; sttT0 = Date.now();
  plog("info", "слушаю: " + (server ? "сервер " + server.url.replace(/\?.*$/, "") : "распознавание телефона"));
  sttGen++;
  if (server && holdTalk && D.listenServerHold) D.listenServerHold(sttGen, sttServerUrl(server.url), server.key, server.model);   // держат — пишем всё до «отпустили»
  else if (server) D.listenServer(sttGen, sttServerUrl(server.url), server.key, server.model);
  else if (holdTalk && D.listenHold) D.listenHold(sttGen);     // держат кнопку — пауза конца фразы подольше, реже перезапуск
  else D.listen(sttGen);
  sttGuard(server ? 20000 : 4000, "start");
}
/* Длинная диктовка: распознаватель телефона сам заканчивает примерно через минуту, запись для сервера — через 15 с.
   Оборвалось на лимите, а не на паузе, — копим сказанное в dict и тихо слушаем дальше; всё вместе уходит, когда человек
   замолчит по-настоящему (или следующий отрезок окажется пустым). */
let dict = "", sttUserStop = false;
/* «Удерживайте и говорите» (как голосовое в Telegram, отзыв 13.10): пока палец на кнопке, слушаем сколько угодно —
   паузы, обрывы распознавателя и тишина не заканчивают запись, сказанное копится в dict; отпустили — всё уходит
   помощнику; увели палец далеко от кнопки — «отпустите — отменить». Обычное нажатие — как раньше. */
var holdTalk = false, holdCancel = false;
function dictMore(t, cut) {
  if (holdTalk) {                                     // держат кнопку — копим и слушаем дальше, что бы ни было
    if (t) dict = (dict ? dict + " " : "") + t;
    showYou(dict ? dict + " …" : "…"); setTimeout(() => { if (holdTalk) listen(); }, 60);
    return true;
  }
  const dur = Date.now() - sttT0, user = sttUserStop; sttUserStop = false;
  if (user || !t || !(cut || (sttVia === "system" && dur >= 45000)) || dict.length > 12000) return false;
  dict = (dict ? dict + " " : "") + t;
  plog("info", `длинная диктовка: ${dict.length} зн., слушаю дальше`);
  showYou(dict + " …"); setTimeout(() => listen(), 60);
  return true;
}
/* Сказанное голосом — с тем, что прикреплено в поле ввода (фото, файл): прикрепили скриншот и сказали «сохрани в
   заметки …» — он уходит вместе с фразой и попадает в заметку (отзыв 11.10: фото так и висело над полем). */
// voice — сказано голосом (1.0.53, владелец 20.11 «скорость голоса»): облако отдаёт простой вопрос лёгкому мозгу (X-Dewiar-Voice)
function askHeard(t) { if (gameVoice()) return gameHeard(t); const att = attached; attached = []; renderAtts(); return ask(t, att.length ? { attach: att } : { voice: true }); }
const dictTake = (t) => { const all = ((dict ? dict + " " : "") + (t || "")).trim(); dict = ""; return all; };
function sttStall(why) {
  if (!sttActive) return;
  sttActive = false; D.cancelListen(); sttGen++;
  plog("warn", "распознавание: нет ответа (" + why + ", " + sttVia + ")");
  if (why === "start" && sttVia === "system" && !sttStarted) {
    const c = Date.now() < sttSysUntil ? null : cloudEars();     // сервер сейчас не пускает — не ходим по кругу
    if (c) {
      // Первый раз — только этот вопрос слушает сервер (распознаватель мог просто долго подключаться к сети);
      // второй раз подряд — насовсем. Заработал сам — счётчик сбрасывается (sttAlive).
      S.stt.sysFails = (S.stt.sysFails || 0) + 1;
      if (S.stt.sysFails >= 2) {
        S.stt = { engine: "server", url: c.url, key: c.key, model: "gigaam", from_account: loggedIn(), auto: true };
        toast("Распознавание этого устройства не отвечает — слушает сервер Dewiar", 4500);
      } else sttOnce = c;
      saveS();
      return listen();
    }
    setState("idle"); showYou("");
    showBot("Распознавание речи этого устройства не отвечает. Войдите аккаунтом dewiar.pro (Настройки → Мозг) — слушать будет сервер Dewiar. Или напишите текстом.", "err");
    return;
  }
  if (holdTalk) { dictMore(heardPartial, true); return; }
  if (heardPartial || dict) { if (dictMore(heardPartial, false)) return; askHeard(dictTake(heardPartial)); return; }
  setState("idle"); showYou("");
}
const sttAlive = () => { sttStarted = true; sttRetry = 0; if (sttVia === "system" && S.stt.sysFails) { S.stt.sysFails = 0; saveS(); } if (sttActive) sttGuard(15000, "silent"); };
N.on("stt_start", e => { if (sttMine(e)) sttAlive(); });
N.on("stt_end", e => {
  if (!sttMine(e) || !sttActive) return;
  sttGuard(sttVia === "server" ? 60000 : 8000, "end");          // запись уходит на сервер — при слабом интернете это не мгновенно
  if (sttVia === "server" && !String($("#you").textContent || "").trim()) showYou(trL("распознаю…"));
});
/* №366 (20.11): запись для сервера (своя, Speech.listenServer) шлёт уровень каждые 50 мс, а частичного текста у неё нет —
   сторож «нет событий 15 с» срабатывал посреди удержания кнопки: запись отменялась, голосовое пропадало целиком. Уровень от
   своей записи — знак, что она жива: сторож заводится заново (у распознавания телефона — только частичный текст, как было). */
N.on("stt_level", e => { if (!sttMine(e)) return; if (orb && state === "listening") orb.set({ level: e.v }); if (!sttStarted) sttAlive(); else if (sttVia === "server" && sttActive) sttGuard(15000, "silent"); });
N.on("stt_partial", e => { if (!sttMine(e)) return; heardPartial = e.text; showYou((dict ? dict + " " : "") + e.text); sttAlive(); });
N.on("stt_result", e => {
  if (!sttMine(e)) return;
  sttGuard(0);
  if (!sttActive) return; sttActive = false;
  let t = (e.text || heardPartial || "").trim();
  plog("info", `📝 ${t ? clip(t) : "(пусто)"} (${sttVia === "server" ? "сервер" : "телефон"}, ${((Date.now() - sttT0) / 1000).toFixed(1)} с)`);
  vCount((t ? "stt_ok_" : "stt_none_") + (sttVia === "server" ? "srv" : "sys")); sttRetry = 0;
  if (t && sttVia === "system" && sttForeign(t)) return;
  if (t && S.stt.notRu && !sttNotRu(t)) { S.stt.notRu = 0; saveS(); }
  if (dictMore(t, !!e.cut)) return;
  t = dictTake(t);
  if (t && pausePrefix && Date.now() - pausePrefix.at < 30000) t = pausePrefix.text + " " + t;   // договорил после обрыва — один вопрос
  pausePrefix = null;
  if (t) { lastStt = { at: Date.now(), text: t, cut: false }; askHeard(t); } else { setState("idle"); showYou(""); if (gameVoice()) gameHeard(""); }
});
/* Распознаватель телефона слышит не по-русски (№253: телефон без русской прошивки — «настойчиво пытается распознать
   английский и китайский»): иероглифы или несколько латинских слов без единой русской буквы. Такое Лире не отдаём:
   первый раз — переспрашиваем, и этот вопрос слушает сервер Dewiar; второй раз подряд — сервер слушает насовсем
   (как при «распознаватель не отвечает»). Сервера нет — честно говорим, что делать. Русское слово — счётчик к нулю. */
const STT_CJK = /[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]/;
// английский в порядке, когда он второй язык («Понимать английскую речь») или язык самого приложения (0.96)
const sttEnOk = () => S.lang2 === "en" || !!(window.dwLang && dwLang() === "en");
const sttNotRu = (t) => !/[а-яё]/i.test(t) && (STT_CJK.test(t) || (!sttEnOk() && (t.match(/[a-z]{2,}/gi) || []).length >= 2));
function sttForeign(t) {
  if (!sttNotRu(t) || holdTalk) return false;
  S.stt.notRu = (S.stt.notRu || 0) + 1; saveS();
  plog("warn", `распознавание телефона услышало не по-русски (${S.stt.notRu}-й раз): ${clip(t, 60)}`);
  const c = Date.now() < sttSysUntil ? null : cloudEars();
  if (!c) {
    setState("idle"); showYou(t);
    showBot("Распознавание этого телефона слышит не по-русски. Подключите Dewiar в «Мозге» (вход аккаунтом dewiar.pro или мозг Dewiar) — слушать будет сервер Dewiar. Или поставьте «Распознавание речи от Google» и выберите в нём русский.", "err");
    return true;
  }
  if (S.stt.notRu >= 2) {
    S.stt = { engine: "server", url: c.url, key: c.key, model: "gigaam", from_account: loggedIn(), auto: true, notRu: 0 }; saveS();
    toast("Распознавание телефона слышит не по-русски — теперь слушает сервер Dewiar. Скажите ещё раз.", 6000);
  } else { sttOnce = c; toast("Не разобрала по-русски — скажите ещё раз", 3500); }
  setState("idle"); showYou("");
  setTimeout(() => { if (state === "idle" && !busy) listen(); }, 500);
  return true;
}
let sttRetry = 0;
N.on("stt_error", e => {
  if (!sttMine(e)) return;
  sttGuard(0);
  if (!sttActive) return; sttActive = false;
  vCount(e.code === 11 ? "stt_e11" : [6, 7].includes(e.code) ? "stt_none_" + (sttVia === "server" ? "srv" : "sys") : "stt_err_" + (sttVia === "server" ? "srv" : "sys"));
  // 11 — распознаватель ещё отключается от прошлого раза, 8 — занят (Samsung и др. сразу после ответа, отчёт №14): это не
  // поломка — через полсекунды он слушает. Раньше уходили на запись для сервера, та писала «речи не было», человек не
  // понимал, что случилось. Теперь — тихо пробуем ещё раз (до двух раз), и только потом — сервер.
  if (holdTalk && [6, 7, 11, 8].includes(e.code)) { dictMore(heardPartial, true); return; }   // держат кнопку — тишина не конец
  if (sttVia === "system" && !sttStarted && [11, 8].includes(e.code) && sttRetry < 2) {
    sttRetry++; plog("info", `распознавание телефона ещё занято (${e.code}) — пробую снова`);
    setTimeout(() => { if (state === "listening") listen(); }, 450 * sttRetry); return;
  }
  sttRetry = 0;
  if (sttVia === "system" && e.code === 13) {          // браузер: своего распознавания на деле нет (веб-версия, webbridge.js)
    plog("warn", "распознавание браузера недоступно: " + (e.msg || ""));
    const c = Date.now() < sttSysUntil ? null : cloudEars();
    if (c) { S.stt = { engine: "server", url: c.url, key: c.key, model: "gigaam", from_account: loggedIn(), auto: true }; saveS();
      toast("В этом браузере своего распознавания нет — слушает сервер Dewiar", 4500); setState("idle"); return listen(); }
    setState("idle"); showYou("");
    showBot("В этом браузере распознавание речи не работает (так у Chrome и Chromium на Linux, у Firefox). Войдите аккаунтом dewiar.pro или подключите Dewiar Облако в «Мозге» — слушать будет сервер Dewiar. Или откройте в Edge, Яндекс Браузере, Safari. Пока можно писать текстом.", "err");
    return;
  }
  plog([6, 7, 5].includes(e.code) ? "info" : "warn", `распознавание (${sttVia}): ${e.code === 6 ? "речи не было" + (/громкость/.test(e.msg || "") ? " — " + String(e.msg).replace(/^[^(]*/, "") : "") : e.code === 7 ? "не расслышал" : "ошибка " + (e.code ?? "") + " " + (e.msg || "")}`);
  // распознаватель телефона сломался, не начав слушать (не запустился, нет сервиса, сеть) — слушает сервер Dewiar
  if (sttVia === "system" && !sttStarted && ![6, 7].includes(e.code) && cloudEars() && Date.now() >= sttSysUntil) { sttActive = true; sttStall("start"); return; }
  // сервер не пустил (кончились талеры, лимит, ключ) — слушает сам телефон; сказанное пропало, просим повторить
  if (sttVia === "server" && STT_DENIED.test(String(e.msg || ""))) {
    const why = String(e.msg).replace(/^[^:]*:?\s*/, "").trim();
    vCount("stt_denied"); plog("warn", "распознавание: сервер не пустил — " + clip(e.msg, 160));
    if (D.recognizer()) {
      sttSysUntil = Date.now() + 30 * 60e3; setState("idle"); showYou("");
      // сразу слушаем снова — уже телефоном; объяснение — всплывающей строкой (listen очищает ответ на экране)
      toast(`${/талер|заряд|счёт|счет|закончил/i.test(why) ? "ИИ-талеры на распознавание закончились" : "Сервер распознавания сейчас не пускает"} — `
        + "слушает сам телефон. Скажите ещё раз.", 6000);
      setTimeout(() => { if (state === "idle" && !busy) listen(); }, 700);
      return;
    }
    setState("idle"); showYou("");
    showBot((why || "Сервер распознавания не пускает.") + " Своего распознавания у этого телефона нет — напишите текстом.", "err");
    if (/ответил 402\b/.test(String(e.msg || "")) && S.llm.cloud) { showCard(payCardHtml(null, true)); payCardWire(); }
    return;
  }
  if (sttVia === "system" && STT_NET.includes(e.code) && !heardPartial && !dict) {
    const now = Date.now(); sttNetFails = sttNetFails.filter(t => now - t < 600e3).concat(now); vCount("stt_net");
    const c = Date.now() < sttSysUntil ? null : cloudEars();
    if (c) {
      if (sttNetFails.length >= 2) { sttNetUntil = now + 600e3; plog("warn", "распознавание телефона: сеть сбоит — 10 минут слушает сервер Dewiar"); }
      else sttOnce = c;
      toast("Распознавание телефона потеряло сеть — слушает сервер Dewiar. Скажите ещё раз.", 4000);
      setState("idle"); showYou(""); setTimeout(() => { if (state === "idle" && !busy) listen(); }, 500);
      return;
    }
    if (now - sttNetRetryAt > 120e3) {
      sttNetRetryAt = now; toast("Связь моргнула — скажите ещё раз.", 3500);
      setState("idle"); showYou(""); setTimeout(() => { if (state === "idle" && !busy) listen(); }, 500);
      return;
    }
  }
  if (heardPartial || dict) { if (dictMore(heardPartial, false)) return; askHeard(dictTake(heardPartial)); return; }
  setState("idle"); showYou("");
  // молча (коды SpeechRecognizer, Speech.java): 6 — речи не было, 7 — не расслышал, 5 — отменено, 11 — распознаватель отключился
  if (![6, 7, 5, 11].includes(e.code)) showBot("Не получилось услышать: " + (e.msg || e.code) + (STT_NET.includes(e.code) ? ". Связь слабая — скажите ещё раз или напишите." : ""), "err");
});
function stopListen() { sttGuard(0); sttGen++; dict = ""; if (sttActive) { sttActive = false; D.cancelListen(); } }

/* ---------- голос: фразы по очереди (Tts.java) — голос телефона или сервера (/v1/audio/speech) ----------
   sayLeft — сколько фраз ещё не отзвучало: tts_done приходит на каждую (и при ошибке), на нуле ход заканчивается. */
let sayN = 0, sayLeft = 0, voiceWarned = false, afterSpeak = null;
/* Голос сервера не ответил (служба голосов выключена, сервер недоступен) — фраза звучит голосом телефона, и следующие две
   минуты тоже: не ждём отказа на каждой фразе. sayTexts — текст фраз, ушедших на сервер, чтобы было что повторить. */
let srvVoiceDownAt = 0, srvVoiceWarnAt = 0;
const sayTexts = new Map();
const EMOJI = (() => { try { return new RegExp("\\p{Extended_Pictographic}", "gu"); } catch (e) { return /[\u2600-\u27BF]|[\uD83C-\uDBFF][\uDC00-\uDFFF]/g; } })();
/* Текст для голоса — как speakable в core/llm.py: без кода, ссылок, путей к файлам и расширений; сокращения — словами */
const FILE_EXT = "(?:html?|pdf|pptx?|docx?|xlsx?|csv|json|md|txt|py|js|css|zip|png|jpe?g|svg|mp3|wav|mp4)";
const SPEAK_RULES = [[/(?:https?:\/\/|www\.)\S+/gi, ""],
  [new RegExp("(^|[^\\wА-Яа-яЁё.])(?:[~/]?[\\wА-Яа-яЁё.-]+/)+[\\wА-Яа-яЁё-]+\\." + FILE_EXT + "(?![\\w])", "gi"), "$1"],
  [/(^|[^\w.])(?:\/?[A-Za-z0-9_.~-]+\/){2,}[A-Za-z0-9_.-]*/g, "$1"],
  [new RegExp("([\\wА-Яа-яЁё-]+)\\." + FILE_EXT + "(?![\\w])", "gi"), "$1"],
  [/(^|\s)в т\.\s?ч\./gi, "$1в том числе"], [/(^|\s)т\.\s?е\./gi, "$1то есть"], [/(^|\s)и т\.\s?д\./gi, "$1и так далее"],
  [/(^|\s)и т\.\s?п\./gi, "$1и тому подобное"], [/(^|\s)т\.\s?к\./gi, "$1так как"], [/(^|\s)напр\./gi, "$1например"],
  [/:\s*[—–-]\s+/g, ": "], [/\s+(?:и|или|в|на|по|из)\s*(?=[.,;:!?]|$)/g, ""], [/\s+([:,;—–-])\s*(?=[:,;.!?—–]|$)/g, ""], [/\(\s*\)/g, ""]];
function speechText(t) {
  t = t.replace(/```[\s\S]*?```/g, " ")
    .replace(/<(script|style)\b[\s\S]*?<\/\1\s*>/gi, " ").replace(/<!--[\s\S]*?-->|<!doctype[^>]*>|<\/?[A-Za-z][\w:-]*(?:\s[^<>]*)?\/?>/gi, " ");   // теги вслух не читаем (28.10)
  t = t.replace(/!?\[([^\]]*)\]\([^()]*\)/g, "$1");                     // [текст](ссылка) → текст, до правил про ссылки
  for (const [rx, to] of SPEAK_RULES) t = t.replace(rx, to);
  // №561 (05.11): голос Safari читал «кавычки» вслух — кавычки, тире, «!!!», скобки и разметка — ui/assets/speechnorm.js clean
  if (typeof window !== "undefined" && window.DewiarSpeech && window.DewiarSpeech.clean) return window.DewiarSpeech.clean(t.replace(EMOJI, " "));
  return t.replace(/[*_#>`|~«»"“”„]+/g, " ").replace(EMOJI, "").replace(/\s+/g, " ").trim();
}
/* <option> голосов устройства для выбора в настройках; пометка «муж.» / «жен.», если пол известен */
function voiceOpts(voices, cur) {
  return voices.map(v => { const m = voiceIsMale(v);
    return `<option value="${esc(v.name)}" ${v.name === cur ? "selected" : ""}>${esc(v.name.replace(/^ru-ru-x-|-local|-network/g, ""))}${m === true ? " · муж." : m === false ? " · жен." : ""}${v.offline ? "" : " · сеть"}</option>`; }).join("");
}
/* Голос Dewiar Облака (озвучка по аккаунту или ключу dw-, если она включена в облаке): {url, key} или null.
   Говорит, когда выбран («Голос Dewiar») или когда в устройстве нет русского голоса. Голос — свой у каждого персонажа. */
function cloudVoice() {
  if (loggedIn() && S.accCloud && S.accCloud.tts) return { url: S.accCloud.base.split("?")[0] + "?p=", key: S.account.token };
  if (S.llm.cloud && S.llm.tts) return { url: cloudBase() + "?p=", key: S.llm.api_key };
  // №928/№363 (20.11): мозг — своя модель по API, а слух — облако Dewiar своим ключом: голос пропадал совсем, если в телефоне
  // нет своего синтеза речи (помогала только установка «Синтеза речи Google»). Тот же ключ облака озвучит ответы
  if (S.stt.engine === "server" && S.stt.key && /cloud\.php/.test(S.stt.url || "")) return { url: String(S.stt.url).split("?")[0] + "?p=", key: S.stt.key };
  return null;
}
/* Голос устройства для героя или героини. Выбран в настройках — он. Иначе подбираем сами: признак пола у голоса (у части
   движков он есть) или голоса Google по имени (ru-ru-x-rud/ruf — мужские, ruc/rue — женские). -> {name, pitch}: нашёлся
   голос нужного пола — без подстройки высоты; нет — один голос на всех, героям чуть ниже, героиням чуть выше (как раньше). */
const EL_VOICES = { f: "EXAVITQu4vr4xnSDxMaL", m: "JBFqnCBsd6RMkjVDRZzb" };   // ElevenLabs по умолчанию: Sarah и George
let voicesCache = null;
function deviceVoices() {
  if (!voicesCache) { try { voicesCache = JSON.parse(D.voices() || "[]"); } catch (e) { voicesCache = []; } }
  return voicesCache;
}
function voiceIsMale(v) {
  const f = (v.features || []).map(x => String(x).toLowerCase());
  if (f.includes("male")) return true;
  if (f.includes("female")) return false;
  if (/-x-ru[df]-/i.test(v.name)) return true;
  if (/-x-ru[ce]-/i.test(v.name)) return false;
  return null;
}
function sysVoiceFor(gender) {
  const male = gender !== "female";
  const own = male ? S.tts.sys_voice_m : S.tts.sys_voice;
  if (own) return { name: own, pitch: 1.0 };
  const vs = deviceVoices(), pick = (want) => (vs.find(v => voiceIsMale(v) === want && v.offline) || vs.find(v => voiceIsMale(v) === want));
  if (male) { const v = pick(true); if (v) return { name: v.name, pitch: 1.0 }; }
  else if (!S.tts.sys_voice) { const v = pick(false); if (v) return { name: v.name, pitch: 1.0 }; }
  return { name: S.tts.sys_voice || "", pitch: male ? 0.92 : 1.12 };
}
let volWarned = false, volMuted = "", volMutedAt = 0;
function volCard() {
  if (!volMuted || $("#vol-up")) return;
  showCard(`<div class="start"><button class="btn p w" id="vol-up">🔊 Звук на нуле — включить и прочитать ответ</button></div>`);
  $("#vol-up").onclick = () => {
    try { D.volume("set", 50); } catch (e) { }
    const t = volMuted; volMuted = ""; volWarned = false; showCard("");
    if (t) say(t);
  };
}
function say(text, retry = 0) {
  if (tgTurn) return;
  text = trL(text);                                         // ответ в Telegram за выключенный компьютер — молча (tgHandle)
  const t = speechText(text); if (!t) return;
  if (S.textMode) { vCount("tts_text"); return; }            // текстовый режим — ответ только на экране
  if (!D.mock) {                                              // звук на нуле — голос всё равно не услышат: не синтезируем
    let v = -1; try { v = D.volume("get", 0); } catch (e) { }   // (сервер голосов не тратится впустую — идея 15.10), ответ на экране
    if (v === 0 && retry < 6 && Date.now() - sttT0 < 120000) {
      // только что слушали: распознаватель телефона на время записи сам глушит звук и возвращает его не сразу —
      // «Звук на нуле» выскакивал зря (20.10, отзыв владельца: «ложно выскочило, следующее аудио — исчезло»). Ждём ~2 с.
      setTimeout(() => say(text, retry + 1), 350); return;
    }
    if (v === 0) {
      vCount("tts_vol0");
      // звук на нуле (у 30 телефонов из 178, пакет 20.10): тихий тост проглядывали — ответы «пропадали». Теперь — кнопка на
      // экране: прибавить громкость и прочитать этот ответ вслух
      if (Date.now() - volMutedAt > 60000) volMuted = "";
      volMuted = (volMuted + " " + t).trim().slice(-1500); volMutedAt = Date.now();
      if (!volWarned) { volWarned = true; plog("warn", "голос: громкость звука на нуле — отвечаю текстом"); }
      setTimeout(volCard, 0);
      return;
    }
    volWarned = false;                                        // прибавили — в следующий раз снова подскажем
    if (volMuted) { volMuted = ""; if ($("#vol-up")) showCard(""); }     // и кнопка «включить звук» больше не нужна
  }
  const id = "s" + (++sayN); sayLeft++;
  turnTime("said");
  // эмоции (19.11, как core/tone.py): тон фразы — голосу Dewiar манерой, всем — чуть темп, лицу — улыбка или без
  const tn = window.DewiarTone && S.tts.tone !== false ? DewiarTone.toneOf(t, DewiarTone.moodOf(typeof turnAsk === "string" ? turnAsk : "")) : null;
  const tsp = tn ? DewiarTone.speedOf(tn) : 1;
  if (tn) window.DEWIAR_TONE = { tone: tn, at: Date.now() };
  const cv = (S.tts.engine === "cloud" || (S.tts.engine === "system" && !ttsOk())) ? cloudVoice() : null;
  const srvDown = Date.now() - srvVoiceDownAt < 120e3 && ttsOk();   // голос сервера только что не ответил — пока свой
  const fem = persona().gender === "female";
  if (S.tts.engine === "eleven" && S.tts.el_key) {           // ElevenLabs своим ключом: голос героя или героини
    const vid = (fem ? S.tts.el_voice_f : S.tts.el_voice_m) || EL_VOICES[fem ? "f" : "m"];
    D.speakRemote(id, `https://api.elevenlabs.io/v1/text-to-speech/${encodeURIComponent(vid)}?output_format=mp3_44100_128`, "xi-api-key:" + S.tts.el_key,
      JSON.stringify({ text: t, model_id: S.tts.el_model || "eleven_flash_v2_5", voice_settings: { speed: Math.max(0.7, Math.min(1.2, +S.tts.rate || 1)) } }));
  } else if (!srvDown && ((S.tts.engine === "server" && S.tts.url) || cv)) {
    sayTexts.set(id, t);
    // голосу сервера — уже словами: «14:10» → «четырнадцать десять» (ui/assets/speechnorm.js, как core/speechnorm.py);
    // старая служба голосов читала цифры странно («ствисе», отзыв 16.10), а новая сделает это сама — дважды не мешает
    const said = window.DewiarSpeech && !isEnglish(t) ? (DewiarSpeech.norm(t, false) || t) : t;   // английское — как есть: сервер сам узнаёт язык
    const u = cv ? cv.url : S.tts.url, url = u.replace(/\/+$/, "") + (/speech$/.test(u) ? "" : "/audio/speech");
    const body = cv ? Object.assign({ model: "tts-1", input: said, voice: persona().voice_remote || (persona().gender === "female" ? "serena" : "aiden"), persona: persona().id || "", response_format: "wav", speed: (+S.tts.rate || 1) * tsp },
      tn ? { instruct: DewiarTone.INSTRUCT[tn] } : {})
      : { model: S.tts.model || "tts-1", input: said, voice: (fem ? S.tts.voice : (S.tts.voice_m || S.tts.voice)) || "alloy", persona: persona().id || "", response_format: "mp3" };
    const sv0 = sysVoiceFor(persona().gender);
    if (D.speakRemoteFb && ttsOk())     // запасной голос — в той же очереди, по порядку (отчёт №93: два голоса разом)
      D.speakRemoteFb(id, url, cv ? cv.key : (S.tts.key || ""), JSON.stringify(body), JSON.stringify({ text: t, rate: +S.tts.rate || 1.0, pitch: sv0.pitch, voice: sv0.name || "" }));
    else D.speakRemote(id, url, cv ? cv.key : (S.tts.key || ""), JSON.stringify(body));
  } else if (srvDown && sayTexts.size && D.speakRemoteFb) {
    // сервер голоса только что подвёл, а его фразы ещё звучат — эту голосом телефона, но в той же очереди, после них
    sayLeft++;                                               // придут два «готово»: запасной фразы и самой
    const sv = sysVoiceFor(persona().gender);
    D.speakRemoteFb(id, "", "", "", JSON.stringify({ text: t, rate: +S.tts.rate || 1.0, pitch: sv.pitch, voice: sv.name || "" }));
  } else {
    if (!ttsOk()) {
      sayLeft--; vCount("tts_none");
      if (!voiceWarned && !D.mock) { voiceWarned = true; plog("warn", "голоса нет: в устройстве нет русского синтеза речи, озвучка облака " + (cloudVoice() ? "есть, но не выбрана" : "не включена") + " — отвечаю текстом"); toast("В устройстве нет русского голоса — отвечаю текстом. Как включить голос — Настройки → Слух и голос.", 6000); }
      return;
    }
    const sv = sysVoiceFor(persona().gender);                 // героям — мужской голос устройства, героиням — женский
    if ((isEnglish(t) || (appEn() && !/[а-яё]/i.test(t))) && D.speakLang) D.speakLang(id, t, S.tts.rate || 1.0, sv.pitch, "", true, "en-US");   // по-английски — английским голосом (приложение по-английски — и короткое «OK.»)
    else D.speak(id, t, (S.tts.rate || 1.0) * tsp, sv.pitch, sv.name, true);
  }
  if (state !== "speaking" && state !== "listening") setState("speaking");
}
// какие фразы звучат прямо сейчас: облик «говорит» губами только под звук. Голос с сервера приходит через секунды после
// начала ответа — до tts_start и в паузах между фразами рот закрыт (отзыв 14.10: «звука нет, а они болтают губами»)
const playingIds = new Set();
const soundOn = () => { if (orb) orb.set({ audible: playingIds.size > 0 }); };
N.on("tts_start", e => { vCount("tts_ok"); playingIds.add((e && e.id) || "?"); soundOn(); turnTime("sound"); if (state === "thinking") setState("speaking"); });
N.on("tts_fail", e => { vCount("tts_err"); plog("warn", "голос устройства не сказал фразу (код " + (e.code ?? "?") + ")"); });
N.on("tts_done", e => {
  if (e && e.id) sayTexts.delete(e.id);
  playingIds.delete((e && e.id) || "?"); soundOn();
  sayLeft = Math.max(0, sayLeft - 1);
  if (sayLeft === 0) listenReset();                          // «Прослушать» дочитал — кнопка снова «Прослушать»
  if (sayLeft === 0 && state === "speaking" && !busy) finishTurn();
});
N.on("tts_error", e => {
  vCount("tts_err"); plog("warn", "голос сервера: " + e.error);
  const t = sayTexts.get(e.id); sayTexts.delete(e.id);
  if (t && ttsOk()) {                                   // эта фраза — голосом телефона, а не тишина
    srvVoiceDownAt = Date.now(); sayLeft++;
    if (!e.fallback) {                                       // старое приложение: запасной голос говорим сами
      const sv = sysVoiceFor(persona().gender);
      D.speak("f" + e.id, t, S.tts.rate || 1.0, sv.pitch, sv.name, true);
    }
    if (Date.now() - srvVoiceWarnAt > 600e3) { srvVoiceWarnAt = Date.now(); toast("Голос сервера сейчас недоступен — говорю голосом телефона", 5000); }
  } else if (t) toast("Голос сервера: " + e.error);      // своего голоса нет — честно говорим, почему тихо
});
function stopVoice() { sayLeft = 0; D.stopSpeak(); playingIds.clear(); soundOn(); listenReset(); }
/* «Прослушать» (идея №58, 29.10: «на прогулке без очков не прочитать — переслушать ответ проще; паузу/стоп»): кнопка под
   ответами в «Разговоре» и под последним ответом на главном экране. Читает и в текстовом режиме (человек сам попросил);
   нажали ещё раз — «Стоп». */
const LISTEN_IC = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 9.5h3.5L12 5.5v13l-4.5-4H4z"/><path d="M15.5 9a4 4 0 0 1 0 6M18 6.5a7.5 7.5 0 0 1 0 11"/></svg>';
const STOP_IC = '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="7" y="7" width="10" height="10" rx="2"/></svg>';
let listenBtn = null;
function listenReset() {
  if (!listenBtn) return;
  const b = listenBtn; listenBtn = null;
  b.classList.remove("on"); b.innerHTML = LISTEN_IC + "<span>Прослушать</span>"; b.setAttribute("aria-label", "Прослушать ответ");
}
function listenToggle(b, text) {
  if (listenBtn === b) { stopVoice(); return; }
  if (playingIds.size || sayLeft) stopVoice();
  const tm = S.textMode; S.textMode = false;
  try { say(text); } finally { S.textMode = tm; }
  if (!sayLeft && !playingIds.size) { toast("Голоса нет — в телефоне не установлен синтез речи (Настройки → «Голос»)", 4000); return; }
  listenBtn = b; b.classList.add("on"); b.innerHTML = STOP_IC + "<span>Стоп</span>"; b.setAttribute("aria-label", "Остановить");
}
function finishTurn() {
  setState("idle");
  const f = afterSpeak; afterSpeak = null;
  if (f) f();
}

