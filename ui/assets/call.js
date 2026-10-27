/* Звонок «Близким» — аудио и видео напрямую между устройствами (WebRTC), общий для телефона (app.js, оверлей поверх
   приложения) и компьютера (ui/call.html в браузере). Сигналы идут зашифрованными сообщениями «Близких» (kind sig) через
   transport — их шифрует и доставляет хозяин страницы; сам звук и видео WebRTC шифрует сквозным DTLS-SRTP.
   Без «капельного» ICE: предложение и ответ уходят целиком (после сбора адресов, до 3 с) — два сообщения на звонок.
     ring {call, video, sdp, ts} → answer {call, sdp} | decline | busy;  cancel — звонящий передумал;  bye — повесили;
     taken — ответили на другом устройстве (остальные перестают звонить).
   DewiarCall.start({role: "caller"|"callee", peer: {pid, name, color}, video, call, offer, transport})
     transport: send(s) -> Promise, ice() -> Promise<iceServers>, fast(on) — опрашивать чаще во время звонка,
                done(info) — звонок закончен ({reason, secs}), say(text) — сказать/показать (необязательно).
   DewiarCall.signal(peerPid, s) — входящий сигнал; DewiarCall.active() — идёт ли звонок. */
(function (root) {
  "use strict";
  let cur = null;
  const RING_MAX = 60000, GATHER = 3000;   // минута: у близкого с закрытым приложением телефон звонит уведомлением — успеть открыть
  const esc = (t) => String(t == null ? "" : t).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const newId = () => Math.random().toString(36).slice(2, 10) + Date.now().toString(36);
  const mmss = (s) => String(Math.floor(s / 60)).padStart(2, "0") + ":" + String(Math.floor(s % 60)).padStart(2, "0");

  // ---------- звук: мягкий звонок (входящий) и редкие гудки (исходящий) — WebAudio, без файлов ----------
  function tones(kind) {
    let ctx = null, timer = 0;
    const AC = root.AudioContext || root.webkitAudioContext;
    const bell = (t0, f, dur, vol) => {
      const o = ctx.createOscillator(), o2 = ctx.createOscillator(), g = ctx.createGain();
      o.frequency.value = f; o2.frequency.value = f * 2.01; o.type = o2.type = "sine";
      g.gain.setValueAtTime(0, t0); g.gain.linearRampToValueAtTime(vol, t0 + 0.02); g.gain.exponentialRampToValueAtTime(0.0008, t0 + dur);
      o.connect(g); o2.connect(g); g.connect(ctx.destination); o.start(t0); o2.start(t0); o.stop(t0 + dur); o2.stop(t0 + dur);
    };
    const play = () => {
      if (!ctx) return; const t = ctx.currentTime + 0.05;
      if (kind === "in") [[659.3, 0], [880, 0.16], [1046.5, 0.32], [880, 0.9], [1046.5, 1.06], [1318.5, 1.22]].forEach(([f, d]) => bell(t + d, f, 1.1, 0.12));
      else bell(t, 425, 1.2, 0.05);
    };
    return {
      start() { try { ctx = new AC(); play(); timer = setInterval(play, kind === "in" ? 3000 : 3500); } catch (e) { } },
      stop() { clearInterval(timer); try { ctx && ctx.close(); } catch (e) { } ctx = null; },
    };
  }

  // ---------- оверлей ----------
  const CSS = `
  .dwc-call{position:fixed;inset:0;z-index:9999;display:flex;flex-direction:column;align-items:center;justify-content:space-between;
    padding:max(28px,env(safe-area-inset-top)) 20px max(30px,calc(env(safe-area-inset-bottom) + 24px));color:#fff;font:15px/1.4 "Manrope",system-ui,sans-serif;
    background:radial-gradient(120% 70% at 50% 0%,color-mix(in srgb,var(--cc,#9BD4FF) 26%,transparent),transparent 60%),linear-gradient(180deg,#14151f,#0a0b10);overflow:hidden}
  .dwc-call video.rv{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;background:#000;opacity:0;transition:opacity .4s}
  .dwc-call.vid.live video.rv{opacity:1}
  .dwc-call video.lv{position:absolute;top:max(20px,env(safe-area-inset-top));right:16px;width:min(28vw,150px);aspect-ratio:3/4;object-fit:cover;border-radius:18px;
    box-shadow:0 12px 30px -10px rgba(0,0,0,.8);background:#111;transform:scaleX(-1);display:none;z-index:2}
  .dwc-call.vid.cam.me video.lv{display:block}
  .dwc-top{position:relative;z-index:1;display:flex;flex-direction:column;align-items:center;gap:10px;margin-top:6vh;text-align:center;transition:opacity .3s}
  .dwc-call.vid.live .dwc-top{margin-top:0;opacity:.0}
  .dwc-ava{width:132px;height:132px;border-radius:50%;display:grid;place-items:center;font:600 52px "Unbounded",sans-serif;color:#12131c;position:relative;
    background:radial-gradient(circle at 35% 30%,#fff,var(--cc,#9BD4FF) 72%);box-shadow:0 20px 50px -18px var(--cc,#9BD4FF)}
  .dwc-ava::before,.dwc-ava::after{content:"";position:absolute;inset:-14px;border-radius:50%;background:color-mix(in srgb,var(--cc,#9BD4FF) 22%,transparent);
    animation:dwcp 2.4s ease-out infinite;z-index:-1}
  .dwc-ava::after{animation-delay:1.2s}
  .dwc-ava.face{background-size:cover;background-position:center;color:transparent}
  .dwc-call.live .dwc-ava::before,.dwc-call.live .dwc-ava::after{animation:none;opacity:0}
  @keyframes dwcp{from{transform:scale(.9);opacity:.9}to{transform:scale(1.5);opacity:0}}
  .dwc-name{font:600 24px "Unbounded","Manrope",sans-serif;margin-top:14px}
  .dwc-st{color:rgba(255,255,255,.7);font-size:15px;min-height:21px;font-variant-numeric:tabular-nums}
  .dwc-bar{position:relative;z-index:2;display:flex;gap:22px;align-items:center;justify-content:center;flex-wrap:wrap}
  .dwc-b{width:64px;height:64px;border-radius:50%;border:0;display:grid;place-items:center;cursor:pointer;color:#fff;background:rgba(255,255,255,.14);
    backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px);transition:transform .15s,background .2s}
  .dwc-b:active{transform:scale(.92)} .dwc-b.off{background:#fff;color:#14151f}
  .dwc-b svg{width:28px;height:28px;fill:none;stroke:currentColor;stroke-width:1.9;stroke-linecap:round;stroke-linejoin:round}
  .dwc-b.end{background:#E5484D;width:72px;height:72px} .dwc-b.ok{background:#2FBF71;width:72px;height:72px}
  .dwc-b.end svg{transform:rotate(135deg)}
  .dwc-lbl{display:flex;flex-direction:column;align-items:center;gap:8px;font-size:12.5px;color:rgba(255,255,255,.75)}
  @media (prefers-reduced-motion:reduce){.dwc-ava::before,.dwc-ava::after{animation:none}}`;
  const SVG = {
    phone: '<path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2"/>',
    mic: '<rect x="9" y="3" width="6" height="11.5" rx="3"/><path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21"/>',
    micoff: '<path d="M9 9v2.5a3 3 0 0 0 5.1 2.1M15 9.3V6a3 3 0 0 0-5.7-1.3"/><path d="M5.5 11a6.5 6.5 0 0 0 10.6 5M18.5 11a6.5 6.5 0 0 1-.4 2.2M12 17.5V21M4 4l16 16"/>',
    cam: '<rect x="2.5" y="6.5" width="13" height="11" rx="2.5"/><path d="m15.5 10.5 6-3.5v10l-6-3.5"/>',
    camoff: '<path d="M15.5 13.5v1.5a2.5 2.5 0 0 1-2.5 2.5H5a2.5 2.5 0 0 1-2.5-2.5V9A2.5 2.5 0 0 1 5 6.5h1.5M10 6.5h3a2.5 2.5 0 0 1 2.5 2.5v1.5l6-3.5v10M3 3l18 18"/>',
  };
  const btn = (cls, ic, lbl) => `<div class="dwc-lbl"><button class="dwc-b ${cls}">${`<svg viewBox="0 0 24 24">${SVG[ic]}</svg>`}</button>${lbl}</div>`;

  function ui(c) {
    if (!document.getElementById("dwc-css")) { const s = document.createElement("style"); s.id = "dwc-css"; s.textContent = CSS; document.head.appendChild(s); }
    const el = document.createElement("div");
    el.className = "dwc-call" + (c.video ? " vid cam" : "");
    el.style.setProperty("--cc", (c.peer && c.peer.color) || "#9BD4FF");
    el.innerHTML = `<video class="rv" autoplay playsinline></video><video class="lv" autoplay playsinline muted></video>
      <div class="dwc-top"><div class="dwc-ava">${esc(((c.peer && c.peer.name) || "?").slice(0, 1).toUpperCase())}</div>
        <div class="dwc-name">${esc((c.peer && c.peer.name) || "")}</div><div class="dwc-st"></div></div>
      <div class="dwc-bar"></div>`;
    document.body.appendChild(el);
    // фото близкого вместо буквы (пакет 27.10: «загрузили фото в „Близких“, а в звонке — буква»): transport.face() -> URL
    const setFace = (u) => { u = typeof u === "string" ? u : (u && u.data) || ""; if (!/^(data:image\/|https?:|blob:)/.test(u)) return;
      const a = el.querySelector(".dwc-ava"); a.style.backgroundImage = `url("${u.replace(/"/g, "%22")}")`; a.classList.add("face"); };
    try { if (c.transport && c.transport.face) Promise.resolve(c.transport.face()).then(setFace).catch(() => {}); } catch (e) { /* без фото — буква */ }
    return el;
  }
  function setStatus(t) { if (cur) cur.el.querySelector(".dwc-st").textContent = t; }
  function bar(kind) {
    const b = cur.el.querySelector(".dwc-bar");
    if (kind === "incoming") {
      b.innerHTML = btn("end", "phone", "Отклонить") + btn("ok", "phone", cur.video ? "Ответить с видео" : "Ответить");
      const [no, yes] = b.querySelectorAll("button"); no.onclick = () => decline(); yes.onclick = () => accept();
      return;
    }
    b.innerHTML = btn("mic", "mic", "Микрофон") + (cur.video ? btn("cam", "cam", "Камера") : "") + btn("end", "phone", "Завершить");
    const bs = b.querySelectorAll("button");
    bs[0].onclick = () => { cur.muted = !cur.muted; (cur.local ? cur.local.getAudioTracks() : []).forEach(t => t.enabled = !cur.muted);
      bs[0].classList.toggle("off", cur.muted); bs[0].innerHTML = `<svg viewBox="0 0 24 24">${SVG[cur.muted ? "micoff" : "mic"]}</svg>`; };
    if (cur.video) bs[1].onclick = () => { cur.camOff = !cur.camOff; (cur.local ? cur.local.getVideoTracks() : []).forEach(t => t.enabled = !cur.camOff);
      bs[1].classList.toggle("off", cur.camOff); cur.el.classList.toggle("cam", !cur.camOff); bs[1].innerHTML = `<svg viewBox="0 0 24 24">${SVG[cur.camOff ? "camoff" : "cam"]}</svg>`; };
    bs[bs.length - 1].onclick = () => hangup();
  }

  // ---------- WebRTC ----------
  async function media(video) {
    const md = root.navigator && navigator.mediaDevices;
    if (!md || !md.getUserMedia) throw new Error("здесь нет доступа к микрофону — откройте звонок в браузере");
    try { return await md.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true }, video: video ? { facingMode: "user", width: { ideal: 1280 } } : false }); }
    catch (e) { if (video) return md.getUserMedia({ audio: true, video: false }); throw new Error("нет доступа к микрофону" + (e && e.name === "NotAllowedError" ? " — разрешите его в настройках" : "")); }
  }
  // пока ждали камеру или ICE, звонок могли закончить (отбой, «занято», тайм-аут) — тогда новое сразу гасим, иначе
  // микрофон и камера остались бы включены
  const GONE = new Error("звонок уже завершён");
  async function grab(c) {
    const s = await media(c.video);
    if (cur !== c) { s.getTracks().forEach(t => t.stop()); throw GONE; }
    c.local = s;
  }
  async function peer() {
    const c = cur;
    let ice = []; try { ice = await c.transport.ice(); } catch (e) { }
    if (cur !== c) throw GONE;
    const pc = new RTCPeerConnection({ iceServers: ice && ice.length ? ice : [{ urls: "stun:stun.l.google.com:19302" }] });
    cur.pc = pc;
    cur.local.getTracks().forEach(t => pc.addTrack(t, cur.local));
    cur.el.querySelector("video.lv").srcObject = cur.local; cur.el.classList.add("me");
    pc.ontrack = (e) => { const v = cur.el.querySelector("video.rv"); if (v.srcObject !== e.streams[0]) { v.srcObject = e.streams[0]; v.play && v.play().catch(() => { }); } };
    pc.onconnectionstatechange = () => {
      if (!cur || cur.pc !== pc) return;
      const s = pc.connectionState;
      if (s === "connected") live();
      else if (s === "disconnected") setStatus("Связь пропала — жду…");
      else if (s === "failed") finish("Связь не установилась" + (cur.started ? " — прервалась" : ": возможно, нужен TURN-сервер"), true);
    };
    return pc;
  }
  function gathered(pc) {
    return new Promise(ok => {
      if (pc.iceGatheringState === "complete") return ok();
      const t = setTimeout(ok, GATHER);
      pc.addEventListener("icegatheringstatechange", () => { if (pc.iceGatheringState === "complete") { clearTimeout(t); ok(); } });
    });
  }
  function live() {
    if (!cur || cur.started) return;
    cur.started = Date.now(); cur.ring && cur.ring.stop(); clearTimeout(cur.timeout);
    cur.el.classList.add("live");
    cur.tick = setInterval(() => setStatus(mmss((Date.now() - cur.started) / 1000)), 1000); setStatus("00:00");
  }
  function finish(reason, notify) {
    if (!cur) return;
    const c = cur; cur = null;
    c.ring && c.ring.stop(); clearInterval(c.tick); clearTimeout(c.timeout);
    try { c.pc && c.pc.close(); } catch (e) { }
    (c.local ? c.local.getTracks() : []).forEach(t => t.stop());
    const secs = c.started ? Math.round((Date.now() - c.started) / 1000) : 0;
    c.el.querySelector(".dwc-st").textContent = reason || (secs ? "Звонок завершён · " + mmss(secs) : "Звонок завершён");
    c.el.querySelector(".dwc-bar").innerHTML = "";
    c.el.classList.remove("live");
    setTimeout(() => c.el.remove(), 1600);
    try { c.transport.fast && c.transport.fast(false); } catch (e) { }
    try { c.transport.done && c.transport.done({ reason: reason || "", secs, role: c.role, peer: c.peer, notify: !!notify }); } catch (e) { }
  }
  const send = (s) => cur && cur.transport.send(Object.assign({ call: cur.call }, s)).catch(() => { });

  async function startCaller() {
    setStatus("Звоню…"); bar("call");
    cur.ring = tones("out"); cur.ring.start();
    await grab(cur);
    if (!cur.local.getVideoTracks().length) { cur.video = false; cur.el.classList.remove("vid", "cam"); bar("call"); }
    const pc = await peer();
    await pc.setLocalDescription(await pc.createOffer());
    await gathered(pc);
    if (!cur) return;
    await send({ type: "ring", video: cur.video, sdp: pc.localDescription.sdp, ts: Date.now() });
    cur.timeout = setTimeout(() => { send({ type: "cancel" }); finish("Не отвечает", true); }, RING_MAX);
  }
  function startCallee() {
    setStatus(cur.video ? "Видеозвонок" : "Звонит"); bar("incoming");
    cur.ring = tones("in"); cur.ring.start();
    cur.timeout = setTimeout(() => finish("Пропущенный звонок", true), RING_MAX);
  }
  async function accept() {
    if (!cur) return;
    cur.ring && cur.ring.stop(); clearTimeout(cur.timeout);
    setStatus("Соединяю…"); bar("call");
    try {
      await grab(cur);
      if (!cur.local.getVideoTracks().length && cur.video) { cur.el.classList.remove("cam"); }
      const pc = await peer();
      await pc.setRemoteDescription({ type: "offer", sdp: cur.offer });
      await pc.setLocalDescription(await pc.createAnswer());
      await gathered(pc);
      if (!cur) return;
      await send({ type: "answer", sdp: pc.localDescription.sdp });
      cur.timeout = setTimeout(() => { if (cur && !cur.started) { send({ type: "bye" }); finish("Связь не установилась: возможно, нужен TURN-сервер", true); } }, 25000);
    } catch (e) { if (e === GONE) return; send({ type: "decline" }); finish("Не получилось: " + e.message, true); }
  }
  function decline() { send({ type: "decline" }); finish("Отклонено"); }
  function hangup() { send({ type: cur && !cur.started && cur.role === "caller" ? "cancel" : "bye" }); finish(""); }

  root.DewiarCall = {
    active: () => !!cur,
    accept: () => { if (cur && cur.role === "callee" && !cur.pc) accept(); },   // «Ответить» на уведомлении звонка
    peer: () => cur && cur.peer && cur.peer.pid,
    async start(o) {
      if (cur) throw new Error("уже идёт звонок");
      cur = Object.assign({ call: o.call || newId(), muted: false, camOff: false }, o);
      cur.el = ui(cur);
      try { cur.transport.fast && cur.transport.fast(true); } catch (e) { }
      try { if (o.role === "caller") await startCaller(); else startCallee(); }
      catch (e) { if (e !== GONE) finish("Не получилось: " + e.message, true); }
    },
    /* входящий сигнал от близкого (peerPid) */
    async signal(peerPid, s, start) {
      if (!s || !s.type) return;
      if (s.type === "ring") {
        if (Date.now() - (+s.ts || 0) > RING_MAX) return;                     // звонок давно закончился
        if (cur && cur.call === s.call) return;
        if (cur) { start && start.busy && start.busy(s); return; }              // занято другим звонком
        if (start && start.ring) start.ring(s);
        return;
      }
      if (!cur || s.call !== cur.call || (cur.peer && cur.peer.pid !== peerPid)) return;
      if (s.type === "answer" && cur.role === "caller" && cur.pc && !cur.answered) {
        cur.answered = true; setStatus("Соединяю…");
        try { await cur.pc.setRemoteDescription({ type: "answer", sdp: s.sdp }); send({ type: "taken" }); } catch (e) { finish("Не получилось соединиться", true); }
      } else if (s.type === "decline") finish(cur.role === "caller" ? "Отклонено" : "", cur.role === "caller");
      else if (s.type === "busy") finish("Занято", true);
      else if (s.type === "cancel" && cur.role === "callee") finish("Пропущенный звонок", true);
      else if (s.type === "taken" && cur.role === "callee" && !cur.pc) finish("Ответили на другом устройстве");
      else if (s.type === "bye") finish("");
    },
  };
})(typeof window !== "undefined" ? window : globalThis);
