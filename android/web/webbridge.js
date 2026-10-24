/* Dewiar в браузере (веб-версия, dewiar.pro/dwrapp/web/): тот же интерфейс, что у Android (android/assets/www/app.js),
   а вместо Bridge.java — возможности браузера. 19.10: «iPhone», «MacBook», «не хочу ставить на каждый компьютер» —
   один путь для всех. Загружается ДО app.js: app.js берёт заглушку браузера и отдаёт её сюда (window.DewiarWeb) —
   здесь настоящие слух (Web Speech или запись для сервера), голос (speechSynthesis и голос сервера по очереди),
   напоминания (пока вкладка открыта + уведомление), радио (<audio>), ссылки. Чего браузер не умеет (звонки, SMS,
   фонарик, громкость, чужие приложения) — честно «нет»: app.js убирает эти инструменты у модели (D.web).
   Настройки и файлы — в localStorage этого сайта (у каждого браузера свои; общие — через синхронизацию Dewiar). */
(function () {
  "use strict";
  const ev = (o) => setTimeout(() => { if (window.N) window.N.ev(JSON.stringify(o)); }, 0);
  // распознавание браузера — только где оно надёжно (Chrome, Edge; на iPhone и в Safari — слушает сервер Dewiar)
  const SR0 = window.SpeechRecognition || window.webkitSpeechRecognition;
  const SR = SR0 && /Chrome\/|Edg\//.test(navigator.userAgent) && !/iPhone|iPad|iPod|CriOS|EdgiOS/.test(navigator.userAgent) ? SR0 : null;
  const synth = window.speechSynthesis;
  const LS = { get: (k) => { try { return localStorage.getItem(k); } catch (e) { return null; } },
               set: (k, v) => { try { localStorage.setItem(k, v); return true; } catch (e) { return false; } } };

  // ---------- звук на iPhone и в Safari: играть можно только после касания. Первое касание «открывает» один общий
  // <audio> для голоса сервера, синтез речи и AudioContext — дальше фразы звучат сами, без новых касаний ----------
  const IOS = /iPhone|iPad|iPod/.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  const voiceEl = new Audio(); voiceEl.preload = "auto"; voiceEl.setAttribute("playsinline", "");
  let actx = null, unlocked = false;
  const audioCtx = () => { try { if (!actx) actx = new (window.AudioContext || window.webkitAudioContext)(); if (actx.state === "suspended") actx.resume(); } catch (e) { } return actx; };
  const SILENT = "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAIA+AAACABAAZGF0YQAAAAA=";
  function unlock() {
    if (unlocked) return; unlocked = true;
    try { if (!playing) { voiceEl.src = SILENT; voiceEl.play().catch(() => { unlocked = false; }); } } catch (e) { }
    try { if (synth && !synth.speaking) { const u = new SpeechSynthesisUtterance(" "); u.volume = 0; synth.speak(u); } } catch (e) { }
    audioCtx();
  }
  ["pointerdown", "touchend", "keydown"].forEach(t => document.addEventListener(t, unlock, { capture: true, passive: true }));

  // ---------- голос: очередь фраз — голос сервера (fetch → <audio>) и голос браузера (speechSynthesis) строго по одной ----------
  const queue = []; let playing = null, gen = 0;
  function ruVoices() { return (synth ? synth.getVoices() : []).filter(v => /^ru/i.test(v.lang)); }
  function sayLocal(id, text, rate, pitch, voice) {
    return new Promise(done => {
      if (!synth) { ev({ type: "tts_fail", id, code: -1 }); ev({ type: "tts_done", id }); done(); return; }
      const u = new SpeechSynthesisUtterance(text);
      u.lang = "ru-RU"; u.rate = Math.max(0.5, Math.min(2, +rate || 1)); u.pitch = Math.max(0.5, Math.min(2, +pitch || 1));
      const v = ruVoices().find(x => x.name === voice) || ruVoices()[0]; if (v) u.voice = v;
      let fin = false; const end = () => { if (fin) return; fin = true; clearTimeout(guard); ev({ type: "tts_done", id }); done(); };
      const guard = setTimeout(end, 12000 + String(text).length * 150);   // Chrome порой не присылает onend — очередь не встаёт
      u.onstart = () => ev({ type: "tts_start", id });
      u.onend = u.onerror = end;
      synth.speak(u);
    });
  }
  const authH = (key) => !key ? {} : key.startsWith("xi-api-key:") ? { "xi-api-key": key.slice(11) } : { Authorization: "Bearer " + key };
  function fetchVoice(job) {        // звук качается сразу, пока звучат предыдущие фразы (как fetch-поток Tts.java)
    return fetch(job.url, { method: "POST", headers: Object.assign({ "Content-Type": "application/json" }, authH(job.key)), body: job.body })
      .then(r => { if (!r.ok) throw new Error("сервер голоса ответил " + r.status); return r.blob(); });
  }
  async function sayRemote(job) {
    const my = gen;
    if (!job.url) {                 // сервер голоса только что подвёл — фраза голосом браузера, но в очереди, после начатых
      if (job.fb && synth) { const f = JSON.parse(job.fb); await sayLocal("f" + job.id, f.text, f.rate, f.pitch, f.voice); }
      ev({ type: "tts_done", id: job.id }); return;
    }
    let blob = null;
    try { blob = await job.got; } catch (e) {
      if (my !== gen) { ev({ type: "tts_done", id: job.id }); return; }
      const own = !!(job.fb && synth);
      ev({ type: "tts_error", id: job.id, error: String(e.message || e), fallback: own });
      if (own) { const f = JSON.parse(job.fb); await sayLocal("f" + job.id, f.text, f.rate, f.pitch, f.voice); }
      ev({ type: "tts_done", id: job.id }); return;
    }
    if (my !== gen) { ev({ type: "tts_done", id: job.id }); return; }
    await new Promise(done => {
      const a = voiceEl, src = URL.createObjectURL(blob); playing = a; let fin = false;
      const end = () => { if (fin) return; fin = true; a.onplay = a.onended = a.onerror = a.onpause = null; URL.revokeObjectURL(src); if (playing === a) playing = null; ev({ type: "tts_done", id: job.id }); done(); };
      a.onplay = () => ev({ type: "tts_start", id: job.id });
      a.onended = a.onerror = a.onpause = end;
      a.src = src;
      a.play().catch(end);          // браузер не дал играть без нажатия — не висим
    });
  }
  let pumping = false;
  async function pump() {
    if (pumping) return; pumping = true;
    while (queue.length) { const j = queue.shift(); if (j.remote) await sayRemote(j); else await sayLocal(j.id, j.text, j.rate, j.pitch, j.voice); }
    pumping = false;
  }
  function pushRemote(id, url, key, body, fb) {
    const j = { remote: true, id, url, key, body, fb };
    if (url) { j.got = fetchVoice(j); j.got.catch(() => { }); }
    queue.push(j); pump();
  }

  // ---------- слух: Web Speech (если есть) или запись 16 кГц для сервера (как Speech.listenServer на Android) ----------
  let rec = null, srv = null, extraMs = 0;
  function listenWeb(g, hold) {
    if (!SR) { ev({ type: "stt_error", g, code: 9, msg: "в этом браузере нет распознавания речи" }); return; }
    const r = new SR(); rec = r;
    r.lang = "ru-RU"; r.interimResults = true; r.continuous = !!hold; r.maxAlternatives = 1;
    let final = "", said = false;
    r.onstart = () => ev({ type: "stt_start", g });
    r.onresult = (e) => {
      let interim = ""; final = "";
      for (let i = 0; i < e.results.length; i++) { const t = e.results[i][0].transcript; if (e.results[i].isFinal) final += t; else interim += t; }
      ev({ type: "stt_partial", g, text: (final + " " + interim).trim() });
    };
    // «network», «service-not-allowed», «audio-capture», «language-not-supported»: распознавания у браузера на деле нет
    // (Chrome и Chromium на Linux — без сервиса Google; 21.10: «нажимаю — через секунду сбрасывает»). Код 13 — app.js
    // переводит слух на сервер Dewiar насовсем (или честно говорит, что слуха нет), а не молча гасит кнопку как «отменено» (5)
    r.onerror = (e) => { said = true; const er = String(e.error || "");
      ev({ type: "stt_error", g, code: er === "no-speech" ? 6 : er === "not-allowed" ? 9 : er === "aborted" ? 5
        : /network|service-not-allowed|audio-capture|language-not-supported|bad-grammar/.test(er) ? 13 : 5, msg: er || "ошибка" }); };
    r.onend = () => { rec = null; ev({ type: "stt_end", g }); if (!said) ev({ type: "stt_result", g, text: final.trim() }); };
    try { r.start(); } catch (e) { ev({ type: "stt_error", g, code: 11, msg: String(e.message || e) }); }
  }
  async function listenServer(g, url, key, model, hold) {
    if (srv) return;
    const st = srv = { finish: false, cancel: false };       // занято сразу — второе нажатие не откроет второй микрофон
    let stream;
    try { stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } }); }
    catch (e) { srv = null; ev({ type: "stt_error", g, code: 9, msg: "нет доступа к микрофону — разрешите его для этого сайта" }); return; }
    if (st.cancel) { stream.getTracks().forEach(t => t.stop()); srv = null; ev({ type: "stt_error", g, code: 5, msg: "отменено" }); return; }
    const ctx = audioCtx();                                 // общий, «открытый» касанием (на iPhone свой был бы немым)
    if (!ctx) { stream.getTracks().forEach(t => t.stop()); srv = null; ev({ type: "stt_error", g, code: 9, msg: "браузер не даёт записывать звук" }); return; }
    const src = ctx.createMediaStreamSource(stream), node = ctx.createScriptProcessor(4096, 1, 1);
    const ratio = ctx.sampleRate / 16000, chunks = [];
    const endQuiet = 30 + Math.round(extraMs / 50);         // 1,5 с тишины + добавка под манеру речи (как Speech.java)
    let noise = 300, peak = 0, speech = 0, quiet = 0, frames = 0, heard = false, acc = [];
    ev({ type: "stt_start", g });
    const end = async () => {
      node.disconnect(); src.disconnect(); stream.getTracks().forEach(t => t.stop()); srv = null;
      ev({ type: "stt_end", g });
      if (st.cancel) { ev({ type: "stt_error", g, code: 5, msg: "отменено" }); return; }
      if (!heard && hold) heard = frames >= 8 && peak > 40;
      if (!heard && peak > noise * 1.8 + 60) heard = true;
      if (!heard) { ev({ type: "stt_error", g, code: 6, msg: "не услышал речи" }); return; }
      const pcm = new Int16Array(chunks.reduce((n, c) => n + c.length, 0)); let o = 0; chunks.forEach(c => { pcm.set(c, o); o += c.length; });
      const fd = new FormData();
      fd.append("file", new Blob([wav(pcm, 16000)], { type: "audio/wav" }), "speech.wav");
      fd.append("model", model || "whisper-1"); fd.append("language", "ru");
      try {
        const r = await fetch(url, { method: "POST", headers: key ? { Authorization: "Bearer " + key } : {}, body: fd });
        const t = await r.text(); if (!r.ok) throw new Error("сервер ответил " + r.status);
        let text = t; try { text = JSON.parse(t).text || ""; } catch (x) { }
        ev({ type: "stt_result", g, text: String(text).trim(), cut: !hold && frames > 300 });
      } catch (e) { ev({ type: "stt_error", g, code: -2, msg: String(e.message || e) }); }
    };
    node.onaudioprocess = (e) => {
      if (st.done) return;
      const x = e.inputBuffer.getChannelData(0);
      for (let i = 0; i < x.length; i += ratio) acc.push(Math.max(-1, Math.min(1, x[Math.floor(i)])) * 32767);
      while (acc.length >= 800) {                           // 50 мс при 16 кГц — как кадр на Android
        const f = Int16Array.from(acc.splice(0, 800)); chunks.push(f); frames++;
        let s = 0; for (let i = 0; i < f.length; i++) s += f[i] * f[i];
        const rms = Math.sqrt(s / f.length); peak = Math.max(peak, rms);
        ev({ type: "stt_level", g, v: Math.min(1, rms / 4000) });
        if (frames < 6) { noise = Math.max(150, (noise + rms) / 2); continue; }
        if (rms > noise * 2.2 + 120) { speech++; quiet = 0; if (speech >= 3) heard = true; } else { quiet++; if (!heard) noise = noise * 0.95 + rms * 0.05; }
        const stop = st.finish || st.cancel || (hold ? frames > 2400 : (heard && quiet >= endQuiet) || (!heard && frames > 160) || frames > 300);
        if (stop) { st.done = true; end(); return; }
      }
    };
    src.connect(node); node.connect(ctx.destination);
  }
  function wav(pcm, rate) {
    const b = new ArrayBuffer(44 + pcm.length * 2), v = new DataView(b), w = (o, s) => { for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)); };
    w(0, "RIFF"); v.setUint32(4, 36 + pcm.length * 2, true); w(8, "WAVE"); w(12, "fmt "); v.setUint32(16, 16, true); v.setUint16(20, 1, true);
    v.setUint16(22, 1, true); v.setUint32(24, rate, true); v.setUint32(28, rate * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true);
    w(36, "data"); v.setUint32(40, pcm.length * 2, true); for (let i = 0; i < pcm.length; i++) v.setInt16(44 + i * 2, pcm[i], true);
    return b;
  }

  // ---------- напоминания: в localStorage, срабатывают, пока вкладка открыта (уведомление + звук) ----------
  const AK = "w_alarms", HK = "w_alarm_hist";
  const alarms = () => { try { return JSON.parse(LS.get(AK) || "[]"); } catch (e) { return []; } };
  const saveAlarms = (l) => LS.set(AK, JSON.stringify(l));
  function beep() {                    // три мягкие ноты — как «фирменная» мелодия напоминаний на Android
    const c = audioCtx(); if (!c) return;
    try {
      const t = c.currentTime;
      [0, 0.35, 0.7].forEach((d, i) => { const o = c.createOscillator(), gn = c.createGain(); o.frequency.value = [660, 880, 990][i];
        gn.gain.setValueAtTime(0.0001, t + d); gn.gain.exponentialRampToValueAtTime(0.25, t + d + 0.03); gn.gain.exponentialRampToValueAtTime(0.0001, t + d + 0.3);
        o.connect(gn).connect(c.destination); o.start(t + d); o.stop(t + d + 0.32); });
    } catch (e) { }
  }
  function notify(title, text) {
    try { if ("Notification" in window && Notification.permission === "granted") new Notification(title, { body: text, icon: "icon-192.png", tag: "dewiar-" + Date.now() }); } catch (e) { }
  }
  function nextAt(x, now) {            // как Alarms.next на Android: днями календаря (летнее время не сдвигает), будни — без выходных
    const d = new Date(+x.at), step = x.repeat === "weekly" ? 7 : 1;
    for (let i = 0; i < 1000; i++) {
      d.setDate(d.getDate() + step);
      if (x.repeat === "weekdays" && (d.getDay() === 0 || d.getDay() === 6)) continue;
      if (d.getTime() > now) break;
    }
    return d.getTime();
  }
  function tick() {
    const now = Date.now(), l = alarms(); let changed = false;
    for (const x of l.slice()) {
      if (+x.at > now) continue;
      if (now - x.at < 6 * 3600e3) {        // вкладку открыли спустя полдня — задним числом не звеним
        const name = x.kind === "timer" ? "Таймер" : x.kind === "alarm" ? "Будильник" : "Напоминание";
        beep(); notify(name, x.title || "");
        if (typeof window.toast === "function") window.toast((x.kind === "timer" ? "⏱ " : x.kind === "alarm" ? "⏰ " : "🔔 ") + (x.title || name), 12000);
      }
      try { const h = JSON.parse(LS.get(HK) || "[]"); h.push({ title: x.title || "", kind: x.kind || "reminder", time: now }); LS.set(HK, JSON.stringify(h.slice(-300))); } catch (e) { }
      if (x.repeat) x.at = nextAt(x, now); else l.splice(l.indexOf(x), 1);
      changed = true;
    }
    if (changed) { saveAlarms(l); ev({ type: "alarms" }); }
  }
  window.addEventListener("focus", () => tick());
  setInterval(tick, 5000); setTimeout(tick, 2500);

  // ---------- радио: обычный <audio> ----------
  const radioEl = new Audio(); let radioName = "", radioState = "stopped", radioErr = "";
  const radioEv = (s, by) => { radioState = s; ev({ type: "radio", state: s, name: radioName, error: radioErr, by }); };
  radioEl.onplaying = () => { radioErr = ""; radioEv("playing"); };
  radioEl.onerror = () => { if (radioState !== "stopped") { radioErr = "станция не отвечает"; radioEv("error"); } };

  // ---------- сеть: fetch с отменой и сроком; чужие сайты без CORS браузер не открывает — говорим это словами ----------
  const ctl = {};
  function http(id, method, url, headers, body, stream, timeout) {
    const ac = new AbortController(); ctl[id] = ac;
    const tm = timeout ? setTimeout(() => ac.abort("timeout"), +timeout) : 0;
    const fin = () => { clearTimeout(tm); delete ctl[id]; };
    let h = {}; try { h = JSON.parse(headers || "{}"); } catch (e) { }
    delete h["User-Agent"];                                   // подпись браузера не меняется — и лишний предзапрос не нужен
    fetch(url, { method, headers: h, body: body || undefined, signal: ac.signal }).then(async r => {
      if (stream && r.ok && r.body) {
        const rd = r.body.getReader(), dec = new TextDecoder();
        for (;;) { const { value, done } = await rd.read(); if (done) break; ev({ type: "http_chunk", id, text: dec.decode(value, { stream: true }) }); }
        fin(); ev({ type: "http_done", id, status: r.status, body: "" });
      } else { const t = await r.text(); fin(); ev({ type: "http_done", id, status: r.status, body: t, url: r.url }); }
    }).catch(e => {
      fin();
      const cross = (() => { try { return new URL(url, location.href).origin !== location.origin; } catch (x) { return false; } })();
      const msg = ac.signal.aborted ? "timeout: сервер не ответил за " + Math.round((+timeout || 0) / 1000) + " с"
        : cross && /Failed to fetch|Load failed|NetworkError/i.test(String(e)) ? "браузер не пускает к " + (() => { try { return new URL(url).host; } catch (x) { return "этому адресу"; } })() + " (сайт не разрешает запросы со страниц — CORS) или нет связи"
        : String(e && e.message || e);
      ev({ type: "http_error", id, error: msg });
    });
  }

  // свой сайт: веб-версия лежит в <сайт>/dwrapp/web/ — вход, облако и голоса там же (тот же адрес — без CORS)
  if (/^https?:$/.test(location.protocol) && /\/dwrapp\/web\//.test(location.pathname)) {
    window.DEWIAR_SITE = window.DEWIAR_SITE || location.origin;
    window.DEWIAR_CLOUD_URL = window.DEWIAR_CLOUD_URL || new URL("../cloud.php", location.href).href;
  }

  window.DewiarWeb = function (stub) {
    const has = (n) => /RECORD_AUDIO|CAMERA|LOCATION/.test(n) ? true : /POST_NOTIFICATIONS/.test(n) ? ("Notification" in window && Notification.permission === "granted") : false;
    return Object.assign(stub, {
      mock: false, web: true,
      info: () => JSON.stringify({ version: window.DEWIAR_WEB_VERSION || "web", sdk: 0, web: true, ios: IOS, device: IOS ? "iPhone / iPad" : "Браузер", recognizer: !!SR, tts: !!synth, crash: "" }),
      has,
      perm(n) {
        if (/POST_NOTIFICATIONS/.test(n) && "Notification" in window) { Notification.requestPermission().then(p => ev({ type: "perm", name: n, granted: p === "granted" })); return; }
        ev({ type: "perm", name: n, granted: has(n) });
      },
      // радар «Рядом»: место — у браузера (он сам спросит разрешение); ответ событием loc, как у Android
      locate(maxAgeSec) {
        if (!navigator.geolocation) { ev({ type: "loc", error: "браузер не умеет определять место" }); return; }
        navigator.geolocation.getCurrentPosition(p => ev({ type: "loc", lat: p.coords.latitude, lon: p.coords.longitude, acc: Math.round(p.coords.accuracy || 0), ts: p.timestamp || Date.now() }),
          e => ev({ type: "loc", error: e && e.code === 1 ? "браузер не разрешил определять место — разрешите в настройках сайта" : "не удалось определить место" }),
          { maximumAge: Math.max(0, +maxAgeSec || 0) * 1000, timeout: 20000, enableHighAccuracy: false });
      },
      locSettings: () => false,
      openSettings: () => false, vibrate(ms) { try { navigator.vibrate && navigator.vibrate(ms); } catch (e) { } },
      notify(title, text) { notify(title, text); },
      share(text) { if (navigator.share) navigator.share({ text }).catch(() => { }); },
      copy: (t) => { try { navigator.clipboard.writeText(t); return true; } catch (e) { return false; } },
      keepScreen() { }, setFace() { }, bars() { },
      immersive(on) { try { if (on && document.documentElement.requestFullscreen) document.documentElement.requestFullscreen({ navigationUI: "hide" }).catch(() => { }); else if (!on && document.fullscreenElement) document.exitFullscreen().catch(() => { }); } catch (e) { } },
      recognizer: () => !!SR,
      listen(g) { listenWeb(g, false); }, listenHold(g) { listenWeb(g, true); },
      listenServer(g, url, key, model) { listenServer(g, url, key, model, false); },
      listenServerHold(g, url, key, model) { listenServer(g, url, key, model, true); },
      pauseExtra(ms) { extraMs = Math.max(0, +ms || 0); },
      stopListen() { if (rec) try { rec.stop(); } catch (e) { } if (srv) srv.finish = true; },
      cancelListen() { if (rec) try { rec.abort(); } catch (e) { } if (srv) srv.cancel = true; },
      speak(id, text, rate, pitch, voice) { queue.push({ id, text, rate, pitch, voice }); pump(); },
      speakRemote(id, url, key, body) { pushRemote(id, url, key, body, null); },
      speakRemoteFb(id, url, key, body, fb) { pushRemote(id, url, key, body, fb); },
      stopSpeak() { gen++; queue.length = 0; if (synth) synth.cancel(); if (playing) { try { playing.pause(); } catch (e) { } playing = null; } },
      voices: () => JSON.stringify(ruVoices().map(v => ({ name: v.name, offline: !!v.localService, features: [] }))),
      ttsReady: () => !!synth && ruVoices().length > 0,
      alarmSet(j) { const x = JSON.parse(j); x.id = x.id || "a" + Date.now(); const l = alarms(), i = l.findIndex(a => a.id === x.id); if (i >= 0) l[i] = x; else l.push(x); saveAlarms(l); return JSON.stringify(x); },
      alarmCancel(id) { const l = alarms(), i = l.findIndex(a => a.id === id); if (i >= 0) { l.splice(i, 1); saveAlarms(l); } return i >= 0; },
      alarms: () => JSON.stringify(alarms()), alarmHistory: () => LS.get(HK) || "[]", exactAlarms: () => true,
      call: () => false, sms: () => false, contact: () => "", openApp: () => "", apps: () => "[]", torch: () => false,
      volume: () => -1, battery: () => JSON.stringify({ percent: -1, charging: false }),
      calEvents: () => JSON.stringify({ events: [] }), calAdd: () => JSON.stringify({ error: "в браузере нет календаря телефона" }), calOpenInsert: () => false,
      openUrl: (u) => { try { window.open(u, "_blank", "noopener"); return true; } catch (e) { return false; } },
      saveDownload(n, m, t) { const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([t], { type: m || "text/plain" })); a.download = n; a.click(); return "Загрузки/" + n; },
      saveDownloadB64(n, m, b) { const a = document.createElement("a"); a.href = "data:" + (m || "application/octet-stream") + ";base64," + b; a.download = n; a.click(); return "Загрузки/" + n; },
      updateInstall: () => "web", updateCanInstall: () => false, updateReady: () => false, openStorage: () => false,
      widgetState: () => JSON.stringify({ on: false, placed: 0, pin: false }), widgetSet() { }, widgetPin: () => false, home() { },
      batteryOk: () => true, askBattery() { }, deviceClass: () => JSON.stringify({ ram_mb: 8192, low_ram: false, cores: navigator.hardwareConcurrency || 4, power_save: false }),
      radioPlay(url, name) { radioName = name || ""; radioErr = ""; radioEv("preparing"); radioEl.src = url; radioEl.play().catch(e => { radioErr = "браузер не дал включить звук — нажмите ▶"; radioEv("error"); }); },
      radioPause() { radioEl.pause(); radioEv("paused", "user"); }, radioResume() { radioEl.play().catch(() => { }); },
      radioStop() { radioEl.pause(); radioEl.removeAttribute("src"); radioEl.load(); radioEv("stopped"); },
      radioDuck(on) { radioEl.volume = on ? 0.25 : 1; }, radioVolume(v) { radioEl.volume = Math.max(0, Math.min(1, +v)); },
      radioState: () => JSON.stringify({ state: radioState, name: radioName, error: radioErr }),
      http, abort(id) { if (ctl[id]) ctl[id].abort("cancel"); }, setProxy: () => "",
      takeIntent: () => "", snapshot: () => "", toast: (t) => { if (typeof window.toast === "function") window.toast(t); },
      // только у Android: «руки», звук будильника, Bluetooth-микрофон, служба «Близких», обновление APK, размер приложения
      handsState: undefined, alarmSound: undefined, alarmSoundSet: undefined, alarmSoundTry: undefined, alarmSoundCustom: undefined,
      btMic: undefined, btMicAvailable: undefined, closeWatch: undefined, closeLive: undefined, appSize: undefined, clearOwnCache: undefined,
      updateGet: undefined, openDownloads: undefined, shareTo: undefined, viewHtml: undefined, sttQuiet: undefined,
    });
  };
})();
