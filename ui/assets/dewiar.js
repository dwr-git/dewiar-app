/* Связь страниц интерфейса с ядром по WebSocket — общий объект window.core для всех окон.
   Протокол описан в core/bridge.py: первым сообщением {cmd:"hello", token}, ядро отвечает снимком состояния
   (core.snapshot, событие "hello"); затем вызовы core.call(cmd, args) -> Promise по {id → reply} и поток событий
   (core.on(type, fn), "*" — любое событие, "offline" — связь пропала).
   token и port приходят в адресе страницы (?token=…&port=…, их подставляет ui/app.py).
   При разрыве ждущие вызовы отклоняются, переподключение — каждые 1,5 с, пока ядро не ответит.
   window.api() — методы окна pywebview (там, где окно открыто через него), иначе null. */
(function () {
  const q = new URLSearchParams(location.search);
  class Core {
    constructor() {
      this.token = q.get("token") || ""; this.port = q.get("port") || "8765";
      this.handlers = {}; this.pending = {}; this.n = 0; this.snapshot = null; this.connected = false;
      this.later = [];                   // сообщения, написанные без связи (sendLater) — уйдут, когда ядро вернётся
      this.connect();
    }
    on(type, fn) { (this.handlers[type] = this.handlers[type] || []).push(fn); return this; }
    off(type, fn) { this.handlers[type] = (this.handlers[type] || []).filter(f => f !== fn); return this; }
    emit(type, e) { (this.handlers[type] || []).forEach(fn => { try { fn(e); } catch (err) { console.error(err); } }); }
    connect() {
      let ws;
      try { ws = new WebSocket(`ws://127.0.0.1:${this.port}`); } catch (e) { return this.retry(); }
      this.ws = ws;
      ws.onopen = () => ws.send(JSON.stringify({ cmd: "hello", token: this.token }));
      ws.onmessage = (m) => {
        const e = JSON.parse(m.data);
        if (e.type === "hello") { this.snapshot = e.data; this.connected = true; this.emit("hello", e.data); this._flush(); return; }
        if (e.type === "reply") {
          const p = this.pending[e.id]; delete this.pending[e.id];
          if (p) e.ok ? p.resolve(e.data) : p.reject(new Error(e.error || "ошибка"));
          return;
        }
        this.emit(e.type, e); this.emit("*", e);
      };
      ws.onclose = () => {
        if (this.connected) this.emit("offline", {});
        this.connected = false;
        Object.values(this.pending).forEach(p => p.reject(new Error("нет связи с ядром"))); this.pending = {};
        this.retry();
      };
      ws.onerror = () => {};
    }
    retry() { clearTimeout(this._rt); this._rt = setTimeout(() => this.connect(), 1500); }
    /* Сообщение человека (виджет, чат студии): нет связи — не теряем, а отправляем, как только ядро вернётся (пакет 23.10,
       №200: «теряется связь с ядром — большое сообщение пропадает, набираю заново»). Старше 10 минут — уже не отправляем. */
    sendLater(cmd, args = {}) {
      if (this.connected) return this.call(cmd, args);
      return new Promise((resolve, reject) => { this.later.push({ cmd, args, resolve, reject, t: Date.now() }); });
    }
    _flush() {
      const q = this.later; this.later = [];
      q.forEach(x => Date.now() - x.t < 600000 ? this.call(x.cmd, x.args).then(x.resolve, x.reject)
        : x.reject(Object.assign(new Error("не отправлено: ядро долго не отвечало"), { stale: true })));
    }
    get waiting() { return this.later.length; }
    /* Нет связи — подождать её до 6 с, а не отказать сразу (владелец 27.10 и №308: «с виджета в заметки — первый раз
       пустая страница и „нет связи с ядром“, второй раз всё открывается»: студия звала ядро раньше, чем успела
       подключиться). Ядро так и не ответило — тогда «нет связи с ядром». */
    call(cmd, args = {}) {
      if (!this.connected) return new Promise((resolve, reject) => {
        let done = false;
        const go = () => { if (done) return; done = true; clearTimeout(t); this.off("hello", go); this.call(cmd, args).then(resolve, reject); };
        const t = setTimeout(() => { if (done) return; done = true; this.off("hello", go); reject(new Error("нет связи с ядром")); }, window.DEWIAR_CALL_WAIT || 6000);
        this.on("hello", go);
      });
      return new Promise((resolve, reject) => {
        const id = ++this.n; this.pending[id] = { resolve, reject };
        this.ws.send(JSON.stringify({ id, cmd, args }));
      });
    }
  }
  window.core = new Core();
  window.api = () => (window.pywebview && window.pywebview.api) || null;
})();
