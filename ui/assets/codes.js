/* Коды Dewiar: «печать» — дизайнерский Aztec (приглашения в «Близкие») и сканер кодов камерой (телефон).
   Aztec — стандартный код (его читают Google Lens, сканеры ZXing и сам Dewiar): строгие квадратные модули, почти чёрный,
   на белой скруглённой плашке со скруглённой рамкой. Сканер читает и QR, Data Matrix, штрихкоды товаров (EAN/UPC, Code 128…). Кодирование и чтение — @zxing/library (assets/vendor/zxing.min.js, Apache-2.0).
   DewiarCodes.seal(text, {ink}) -> SVG;  DewiarCodes.scan({onResult(text, format), title}) -> закрыть();  decodeCanvas(canvas) -> текст|null. */
(function (root) {
  "use strict";
  const Z = () => root.ZXing;

  function matrix(text) {
    const bytes = new TextEncoder().encode(String(text));
    const code = Z().AztecEncoder.encode(bytes, 33, 0);
    const m = code.getMatrix(), n = m.getWidth(), rows = [];
    for (let y = 0; y < n; y++) { const r = []; for (let x = 0; x < n; x++) r.push(m.get(x, y)); rows.push(r); }
    return { n, rows, core: code.isCompact() ? 4 : 6 };     // «яблочко»: компактный — кольца до 4, полный — до 6 модулей от центра
  }

  /* Печать: строгие квадратные модули (как и «яблочко» в центре — по углам его колец сканеры находят код), почти чёрная,
     на белой скруглённой плашке со скруглённой рамкой того же цвета. Тёмные модули строки слиты в полосы — один путь, без швов. */
  function seal(text, o) {
    o = o || {};
    if (!Z()) return "";
    const ink = o.ink || "#16142a", { n, rows } = matrix(text), fw = 1.6, pad = 2.2 + fw + 1.4, W = n + pad * 2;
    const f = (v) => +v.toFixed(3);
    let d = "";
    for (let y = 0; y < n; y++) for (let x = 0; x < n; ) {
      if (!rows[y][x]) { x++; continue; }
      let e = x; while (e + 1 < n && rows[y][e + 1]) e++;
      d += `M${f(x + pad)} ${f(y + pad)}h${e - x + 1}v1h${-(e - x + 1)}z`; x = e + 1;
    }
    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${f(W)} ${f(W)}">`
      + `<rect x="0" y="0" width="${f(W)}" height="${f(W)}" rx="${f(W * 0.07)}" fill="#fff"/>`
      + `<rect x="${f(1.4 + fw / 2)}" y="${f(1.4 + fw / 2)}" width="${f(W - 2.8 - fw)}" height="${f(W - 2.8 - fw)}" rx="${f(W * 0.05)}" fill="none" stroke="${ink}" stroke-width="${fw}"/>`
      + `<path d="${d}" fill="${ink}"/></svg>`;
  }

  // ---------- чтение ----------
  let reader = null;
  const api = { format: "" };                      // формат последнего прочитанного кода: qr, aztec, datamatrix, ean13, code128…
  const fmtName = (f) => { try { return String(Z().BarcodeFormat[f] || f).toLowerCase().replace(/_/g, ""); } catch (e) { return ""; } };
  // zxing-js находит Aztec только почти ровно (поворот больше ~5° уже мимо) — пробуем и повёрнутый кадр:
  // в сканере по одному углу на кадр (step), в decodeAll — все сразу
  const ANGLES = [0, 8, -8, 16, -16, 24, -24, 32, -32, 40, -40];
  function attempt(cv, angle) {
    const one = (c) => { try { const res = reader.decode(new (Z().BinaryBitmap)(new (Z().HybridBinarizer)(new (Z().HTMLCanvasElementLuminanceSource)(c))));
      api.format = fmtName(res.getBarcodeFormat()); return res.getText(); } catch (e) { return null; } };
    if (!angle) return one(cv);
    const c2 = document.createElement("canvas"), w = cv.width, h = cv.height;
    c2.width = w; c2.height = h; const x = c2.getContext("2d", { willReadFrequently: true });
    x.fillStyle = "#888"; x.fillRect(0, 0, w, h); x.translate(w / 2, h / 2); x.rotate(-angle * Math.PI / 180); x.drawImage(cv, -w / 2, -h / 2);
    return one(c2);
  }
  function ready() {
    if (!Z()) return false;
    if (!reader) {
      reader = new (Z().MultiFormatReader)();
      const h = new Map();
      const F = Z().BarcodeFormat;                   // двумерные коды и штрихкоды товаров (EAN/UPC), коробок и билетов (Code 128/39, ITF, PDF417)
      h.set(Z().DecodeHintType.POSSIBLE_FORMATS, [F.QR_CODE, F.AZTEC, F.DATA_MATRIX, F.PDF_417, F.EAN_13, F.EAN_8, F.UPC_A, F.UPC_E,
        F.CODE_128, F.CODE_39, F.ITF, F.CODABAR].filter(x => x != null));
      h.set(Z().DecodeHintType.TRY_HARDER, true);
      reader.setHints(h);
    }
    return true;
  }
  function decodeCanvas(cv, step) {
    if (!ready()) return null;
    const t = attempt(cv, 0);
    if (t || step == null) return t;
    return attempt(cv, ANGLES[1 + (step % (ANGLES.length - 1))]);
  }
  function decodeAll(cv) {
    if (!ready()) return null;
    for (const a of ANGLES) { const t = attempt(cv, a); if (t) return t; }
    return null;
  }

  const CSS = `.dwq{position:fixed;inset:0;z-index:9998;background:#000;color:#fff;display:flex;flex-direction:column;font:15px/1.4 "Manrope",system-ui,sans-serif}
  .dwq video{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;opacity:0;transition:opacity .25s}.dwq video.on{opacity:1}
  .dwq .fr{position:absolute;left:50%;top:44%;width:min(70vw,300px);aspect-ratio:1;transform:translate(-50%,-50%);border-radius:36px;
    box-shadow:0 0 0 100vmax rgba(5,6,12,.55);transition:box-shadow .2s}
  .dwq .fr::before{content:"";position:absolute;inset:-3px;border-radius:38px;padding:3px;background:conic-gradient(from 0deg,#9BD4FF,#B78CFF,#FF7AB6,#9BD4FF);
    -webkit-mask:linear-gradient(#000 0 0) content-box,linear-gradient(#000 0 0);-webkit-mask-composite:xor;mask-composite:exclude;animation:dwqs 3s linear infinite;opacity:.9}
  @keyframes dwqs{to{filter:hue-rotate(360deg)}}
  .dwq .hd{position:relative;z-index:1;padding:max(22px,env(safe-area-inset-top)) 20px 0;text-align:center}
  .dwq .hd b{display:block;font:600 19px "Unbounded","Manrope",sans-serif} .dwq .hd span{color:rgba(255,255,255,.75);font-size:14px}
  .dwq .x{position:absolute;z-index:2;left:50%;bottom:max(34px,calc(env(safe-area-inset-bottom) + 24px));transform:translateX(-50%);width:64px;height:64px;border-radius:50%;
    border:0;background:rgba(255,255,255,.16);backdrop-filter:blur(12px);color:#fff;display:grid;place-items:center}
  .dwq .x svg{width:26px;height:26px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round}
  .dwq .tl{position:absolute;z-index:2;right:max(26px,calc(50% - 150px));bottom:max(40px,calc(env(safe-area-inset-bottom) + 30px));width:52px;height:52px;border-radius:50%;
    border:0;background:rgba(255,255,255,.16);backdrop-filter:blur(12px);color:#fff;display:grid;place-items:center;transition:background .2s,color .2s}
  .dwq .tl[hidden]{display:none} .dwq .tl.on{background:#FFE7A3;color:#3a2a00;box-shadow:0 0 28px rgba(255,220,130,.55)}
  .dwq .tl svg{width:24px;height:24px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}
  @media (prefers-reduced-motion:reduce){.dwq .fr::before{animation:none}}`;

  function scan(o) {
    o = o || {};
    if (!document.getElementById("dwq-css")) { const s = document.createElement("style"); s.id = "dwq-css"; s.textContent = CSS; document.head.appendChild(s); }
    const el = document.createElement("div"); el.className = "dwq";
    // poster — прозрачная точка: иначе Android WebView до первого кадра камеры рисует свою серую кнопку «play» на весь экран
    el.innerHTML = `<video playsinline muted autoplay poster="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"></video><div class="fr"></div>
      <div class="hd"><b>${o.title || "Наведите на код"}</b><span>${o.sub || "QR, Aztec и печати Dewiar"}</span></div>
      <button class="x" title="Закрыть"><svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6 6 18"/></svg></button>
      <button class="tl" title="Фонарик" aria-label="Фонарик" aria-pressed="false" hidden><svg viewBox="0 0 24 24"><path d="M8 3h8l-1 5H9z"/><path d="M9 8h6v4l-1 1v7a2 2 0 0 1-4 0v-7l-1-1z"/><path d="M12 14.5v1.5"/></svg></button>`;
    document.body.appendChild(el);
    const v = el.querySelector("video"), cv = document.createElement("canvas"), cx = cv.getContext("2d", { willReadFrequently: true }),
      wide = document.createElement("canvas");
    let stream = null, timer = 0, done = false, frame = 0;
    // №634 (09.11, телефон): «в тёмном помещении сканер запущен, а кнопки фонарика нет — или пусть Лира включает его сама».
    // Камера умеет фонарик (torch) — кнопка; темно ~1,5 с подряд и человек фонарик не трогал — включаем сами
    const tl = el.querySelector(".tl"), lum = document.createElement("canvas");
    let torch = false, touched = false, dark = 0;
    const setTorch = async (on) => {
      const tr = stream && stream.getVideoTracks()[0]; if (!tr) return;
      try { await tr.applyConstraints({ advanced: [{ torch: !!on }] }); torch = !!on; } catch (e) { return; }
      tl.classList.toggle("on", torch); tl.setAttribute("aria-pressed", String(torch)); tl.title = torch ? "Выключить фонарик" : "Фонарик";
    };
    tl.onclick = () => { touched = true; setTorch(!torch); };
    const darkness = () => {                         // средняя яркость середины кадра (0–255) на маленькой копии
      lum.width = lum.height = 24; const g = lum.getContext("2d", { willReadFrequently: true });
      g.drawImage(cv, 0, 0, 24, 24); const d = g.getImageData(0, 0, 24, 24).data; let sum = 0;
      for (let i = 0; i < d.length; i += 4) sum += d[i] * 0.3 + d[i + 1] * 0.59 + d[i + 2] * 0.11;
      return sum / (d.length / 4);
    };
    const close = (txt) => {
      if (done) return; done = true; clearTimeout(timer);
      (stream ? stream.getTracks() : []).forEach(t => t.stop()); el.remove();
      if (txt != null) o.onResult && o.onResult(txt, api.format); else o.onClose && o.onClose();
    };
    el.querySelector(".x").onclick = () => close(null);
    const tick = () => {
      if (done) return;
      if (v.videoWidth) {
        const s = Math.min(v.videoWidth, v.videoHeight), k = Math.min(1, 720 / s);           // середина кадра, не больше 720 точек
        cv.width = cv.height = Math.round(s * k);
        cx.drawImage(v, (v.videoWidth - s) / 2, (v.videoHeight - s) / 2, s, s, 0, 0, cv.width, cv.height);
        if (!tl.hidden && !torch && !touched && frame % 2 === 0) { dark = darkness() < 45 ? dark + 1 : 0; if (dark >= 5) { touched = true; setTorch(true); } }
        let t = decodeCanvas(cv, frame++);
        if (!t && frame % 3 === 0) {                 // штрихкод шире квадрата в середине — раз в три кадра весь кадр целиком
          const k2 = Math.min(1, 1280 / v.videoWidth); wide.width = Math.round(v.videoWidth * k2); wide.height = Math.round(v.videoHeight * k2);
          wide.getContext("2d", { willReadFrequently: true }).drawImage(v, 0, 0, wide.width, wide.height); t = decodeCanvas(wide);
        }
        if (t) { try { navigator.vibrate && navigator.vibrate(30); } catch (e) { } return close(t); }
      }
      timer = setTimeout(tick, 160);
    };
    (async () => {
      try {
        stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: "environment" }, width: { ideal: 1280 } }, audio: false });
        if (done) { stream.getTracks().forEach(t => t.stop()); return; }
        v.addEventListener("playing", () => v.classList.add("on"), { once: true });   // показываем, когда пошли кадры
        v.srcObject = stream; await v.play().catch(() => { }); tick();
        try { const tr = stream.getVideoTracks()[0], cap = tr && tr.getCapabilities ? tr.getCapabilities() : {}; tl.hidden = !cap.torch; } catch (e) { }
      } catch (e) { close(null); o.onError && o.onError("нет доступа к камере"); }
    })();
    return () => close(null);
  }


  root.DewiarCodes = { seal, scan, decodeCanvas, decodeAll, matrix, get format() { return api.format; } };
})(typeof window !== "undefined" ? window : globalThis);
