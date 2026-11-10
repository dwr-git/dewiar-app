/* Начало каждой страницы окна (ui/*.html): ПЕРВЫЙ скрипт в <head>, сразу после <base href="страница.html">.
   Четвёртая рецензия выпуска 5 (05.11): фрейм-песочница (srcdoc, about:blank) наследует базовый адрес родителя —
   document.baseURI отдавал ему адрес окна с ?token=…&bn=… (ключ ядра и ключ моста). Теперь:
   — <base href="страница.html"> — базовый адрес без «?…» с самого начала (шрифты и картинки assets/… — как раньше);
   — параметры адреса читаются здесь один раз (dwQuery() — их копия, без ключа моста), и адрес окна сразу становится
     «страница.html#раздел» (history.replaceState) — раньше, чем появится любой фрейм;
   — перезагрузка окна (F5): параметры берутся из sessionStorage этого окна. Выбрано вместо «Python подставит адрес
     заново»: работает одинаково в WebKitGTK, WebView2 и WKWebView, без своего обработчика загрузки в каждой системе;
     sessionStorage — у каждого окна свой, а фреймам-песочницам (другое происхождение) он недоступен;
   — ключ моста (bn) живёт только в замыкании ниже: им подписан каждый вызов pywebview.api.* (Python без него не
     исполняет — ui/app.py: guard_bridge). Код страниц прежний: pywebview.api.X(...). */
(function () {
  const KEY = "dw.page:" + location.pathname;
  let raw = location.search;
  try {
    if (/[?&]token=/.test(raw)) sessionStorage.setItem(KEY, raw);
    else if (!raw.replace(/^\?/, "")) raw = sessionStorage.getItem(KEY) || raw;   // перезагрузка: адрес уже без параметров
  } catch (e) { }
  const all = new URLSearchParams(raw), bn = all.get("bn") || "";
  all.delete("bn");
  const pub = all.toString();
  window.dwQuery = () => new URLSearchParams(pub);
  try { if (location.search) history.replaceState(history.state, "", location.pathname + location.hash); } catch (e) { }
  if (!/^[A-Za-z0-9_-]{16,}$/.test(bn)) return;
  const own = (f) => /^pywebview/.test(String(f)) || f === "_pywebviewAlert";
  const add = (f, p) => own(f) ? p : [bn].concat(Array.prototype.slice.call(p || []));
  const wrap = (pw) => {
    if (!pw || typeof pw !== "object" || pw.__dwBridge) return pw;
    try { Object.defineProperty(pw, "__dwBridge", { value: true }); } catch (e) { }
    const cb = pw._jsApiCallback;                                        // pywebview 5.1+
    if (typeof cb === "function") pw._jsApiCallback = function (f, p, id) { return cb.call(this, f, add(f, p), id); };
    const br = pw._bridge;                                               // pywebview 5.0
    if (br && typeof br.call === "function") { const bc = br.call; br.call = function (f, p, id) { return bc.call(this, f, add(f, p), id); }; }
    return pw;
  };
  let cur = wrap(window.pywebview);
  try {
    Object.defineProperty(window, "pywebview", { configurable: true, enumerable: true,
      get() { return cur; }, set(v) { cur = wrap(v); } });
  } catch (e) { }
})();
