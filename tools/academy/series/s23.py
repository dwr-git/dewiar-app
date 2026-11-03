import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kit import KIT_CSS, KIT2_CSS
TITLE = "Урок 23 · Сейф на всех устройствах"
IDEA = "Главная вещь урока — пароль, оставшийся дома, есть в телефоне: открыл сейф, скопировал, буфер сам очистился; ключ — только у вас, сервер видит шифр."
H1 = "Сейф везде"
TAG = "Один сейф паролей — на всех ваших устройствах"
NEXT = "Скоро — новые уроки"
ICON = '<svg viewBox="0 0 24 24"><rect x="2.5" y="5" width="12" height="9" rx="1.6"/><path d="M1 17h15"/><rect x="16" y="8" width="6" height="11" rx="1.6"/><path d="M6.4 9.6V8.4a2.1 2.1 0 0 1 4.2 0v1.2"/><rect x="5.6" y="9.6" width="5.8" height="3.2" rx=".8"/></svg>'
SCENES = ["title", "problem", "sync", "master", "phone", "guard", "how", "end"]
POS = {"problem": "{ lira: [330, 730, 210, 1], patrik: [330, 350, 250, 1] }"}
CSS = KIT_CSS + KIT2_CSS + """
#shop { left: 640px; top: 200px; width: 700px; }
#shop .pg { padding: 30px 34px 34px; border-radius: 16px; background: #fff; }
#shop .pg h4 { font: 700 28px Unbounded; } #shop .pg > small { display: block; margin-top: 6px; font-size: 17px; font-weight: 700; color: var(--mut); }
#shop label { display: block; margin-top: 20px; font-size: 16px; font-weight: 800; color: var(--mut); }
#shop .f { margin-top: 8px; padding: 15px 18px; border-radius: 14px; border: 2px solid #dfe5ef; font-size: 22px; font-weight: 700; min-height: 58px; letter-spacing: .02em; }
#shop .f.pw { border-color: var(--accent); }
#shop .go { margin-top: 24px; padding: 17px; border-radius: 14px; text-align: center; color: #fff; background: #2fa36b; font-size: 21px; font-weight: 800; }
#shop .go.ok { background: #1e7d5b; }
.phone { top: 110px; } .phone .scr { position: relative; }
.pn { position: absolute; inset: 0; padding: 34px 22px; }
.pn h5 { display: flex; align-items: center; gap: 10px; } .pn h5 small { margin-left: auto; font: 800 14px Manrope; color: #1e7d5b; }
.srch { padding: 12px 16px; border-radius: 16px; background: #fff; font-size: 17px; font-weight: 700; color: var(--mut); }
.rec { margin-top: 14px; padding: 18px; border-radius: 22px; background: #fff; }
.rec .t { display: flex; align-items: center; gap: 12px; } .rec .t i { width: 52px; height: 52px; border-radius: 16px; display: grid; place-items: center; font-size: 28px; font-style: normal; background: rgba(69,96,234,.1); }
.rec .t b { font-size: 19px; } .rec .t small { display: block; font-size: 14px; font-weight: 700; color: var(--mut); }
.rec label { display: block; margin-top: 14px; font-size: 13px; font-weight: 800; color: var(--mut); letter-spacing: .04em; }
.rec .v { margin-top: 4px; font-size: 20px; font-weight: 800; letter-spacing: .04em; }
.rec .pwv { font: 600 22px Unbounded; letter-spacing: .02em; color: var(--accent); }
.bts { display: flex; gap: 8px; margin-top: 16px; } .bts span { flex: 1; text-align: center; padding: 12px 6px; border-radius: 14px; background: #eef2f8; font-size: 15px; font-weight: 800; }
.bts span.on { color: #fff; background: var(--brand); }
.clip { position: absolute; left: 18px; right: 18px; bottom: 26px; display: flex; align-items: center; gap: 12px; padding: 14px 16px; border-radius: 18px; color: #fff; background: rgba(36,50,74,.92); font-size: 15px; font-weight: 700; line-height: 1.3; }
.clip svg { flex: none; width: 46px; height: 46px; } .clip b { display: block; font-size: 16px; }
.apps { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin-top: 8px; }
.apps span { display: flex; flex-direction: column; align-items: center; gap: 6px; padding: 14px 4px; border-radius: 18px; background: #fff; font-size: 14px; font-weight: 800; }
.apps span i { font-size: 30px; font-style: normal; } .apps span.on { box-shadow: 0 0 0 3px var(--accent); }
.mpw { margin-top: 18px; padding: 16px; border-radius: 16px; background: #fff; font-size: 26px; font-weight: 800; letter-spacing: .12em; min-height: 62px; }
.lst .rw { display: flex; align-items: center; gap: 12px; margin-top: 10px; padding: 13px 14px; border-radius: 16px; background: #fff; font-size: 16px; font-weight: 800; }
.lst .rw i { font-style: normal; font-size: 22px; } .lst .rw em { margin-left: auto; font-style: normal; color: var(--mut); letter-spacing: .08em; }
.lock { position: absolute; inset: 0; border-radius: 42px; display: grid; place-content: center; text-align: center; background: rgba(238,242,248,.86); backdrop-filter: blur(8px); }
.lock i { font-size: 92px; font-style: normal; } .lock b { display: block; font: 700 24px Unbounded; margin-top: 8px; } .lock small { display: block; margin-top: 8px; font-size: 16px; font-weight: 700; color: var(--mut); }
#syn { top: 170px; width: 820px; }
#syn .sw { display: flex; align-items: center; gap: 18px; margin-top: 16px; padding: 20px 22px; border-radius: 22px; box-shadow: var(--raise-s); }
#syn .sw b { display: block; font-size: 24px; } #syn .sw span { display: block; margin-top: 4px; font-size: 18px; font-weight: 700; color: var(--mut); line-height: 1.35; }
#syn .sw.on { box-shadow: 0 0 0 3px rgba(69,96,234,.55), var(--raise-s); }
#syn .row { margin-top: 12px; }
#mp { top: 190px; width: 560px; } #mp .in { margin-top: 12px; padding: 18px 22px; border-radius: 18px; box-shadow: var(--press); font-size: 32px; font-weight: 800; letter-spacing: .14em; min-height: 74px; }
#mp p { margin-top: 18px; font-size: 19px; font-weight: 700; color: var(--mut); line-height: 1.4; }
#mp .ok2 { margin-top: 18px; display: inline-block; padding: 16px 28px; border-radius: 18px; color: #fff; background: var(--brand); font-size: 21px; font-weight: 800; }
#dg { position: absolute; left: 1220px; top: 150px; width: 620px; height: 640px; }
#dg svg { position: absolute; inset: 0; }
#dg .dv { position: absolute; width: 170px; padding: 16px 12px; border-radius: 24px; background: var(--bg); box-shadow: var(--raise); text-align: center; font-size: 18px; font-weight: 800; }
#dg .dv i { display: block; font-size: 44px; font-style: normal; } #dg .dv small { display: block; margin-top: 4px; font-size: 14px; color: #1e7d5b; }
#dg .sv { position: absolute; left: 160px; top: 230px; width: 300px; padding: 20px; border-radius: 26px; background: #24324a; color: #fff; text-align: center; }
#dg .sv b { display: block; font: 700 20px Unbounded; } #dg .sv code { display: block; margin-top: 10px; font: 600 15px/1.5 monospace; color: #9fb4ff; word-break: break-all; }
#dg .sv small { display: block; margin-top: 10px; font-size: 15px; font-weight: 700; color: rgba(255,255,255,.75); }
#edit { top: 200px; width: 720px; } #edit .ar { margin: 10px 0 0 34px; font-size: 30px; color: var(--accent); }
#rules { top: 170px; width: 740px; } #rules .row { font-size: 21px; }
#studio { top: 170px; width: 900px; }
#studio .sw2 { display: flex; align-items: center; gap: 16px; margin-top: 14px; padding: 16px 18px; border-radius: 18px; box-shadow: 0 0 0 3px rgba(69,96,234,.45), var(--raise-s); font-size: 22px; font-weight: 800; }
"""
RING = ('<svg viewBox="0 0 46 46"><circle cx="23" cy="23" r="19" fill="none" stroke="rgba(255,255,255,.2)" stroke-width="5"/>'
        '<circle id="{id}" cx="23" cy="23" r="19" fill="none" stroke="#7ee0b0" stroke-width="5" stroke-linecap="round" stroke-dasharray="119.4" transform="rotate(-90 23 23)"/>'
        '<text id="{id}t" x="23" y="28" text-anchor="middle" font-family="Manrope" font-weight="800" font-size="14" fill="#fff">30</text></svg>')
APPS = [("📝", "Заметки"), ("⏰", "Дела"), ("💬", "Чат"), ("❤️", "Близкие"), ("🔐", "Сейф"), ("💸", "Деньги"), ("📅", "Календарь"), ("🎬", "Уроки"), ("⚙️", "Настройки")]
HTML = """
  <div class="layer" id="L-left">
    <div class="win" id="shop"><div class="bar"><i></i><i></i><i></i><span>🔒 <b>Интернет-магазин «Дом и сад»</b></span></div>
      <div class="pg"><h4>Вход</h4><small>Чтобы оплатить заказ — войдите</small><label>ЛОГИН</label><div class="f">patrik</div>
        <label>ПАРОЛЬ</label><div class="f pw" id="spw"></div><div class="go" id="sgo">Войти и оплатить</div></div></div>
    <div class="card" id="syn"><h3>Сейф паролей</h3>
      <div class="sw" id="sw"><div><b>Один сейф на всех моих устройствах</b><span>Записи уходят на ваши устройства только шифром</span></div><span class="tgl" id="tg1"><i></i></span></div>
      <div class="row"><i>🛒</i>Магазин «Дом и сад»<em>• • • • • • • •</em></div><div class="row"><i>📶</i>Вайфай дома<em>• • • • • •</em></div><div class="row"><i>🔢</i>Домофон<em>• • • •</em></div></div>
    <div class="card" id="mp"><small>ПРИДУМАЙТЕ МАСТЕР-ПАРОЛЬ</small><div class="in" id="mpi"></div>
      <p>Он нигде не хранится — ни на сервере, ни у нас. Из него на ваших устройствах получается ключ.</p><span class="ok2">Включить</span></div>
    <div id="dg"><svg viewBox="0 0 620 640"><g fill="none" stroke="#4560ea" stroke-width="3" stroke-dasharray="8 9" opacity=".45">
        <path d="M95 140 L230 250"/><path d="M525 140 L390 250"/><path d="M310 540 L310 400"/></g></svg>
      <div class="dv" style="left:10px;top:30px"><i>💻</i>Ноутбук<small>🔑 ключ здесь</small></div>
      <div class="dv" style="left:440px;top:30px"><i>🖥</i>Рабочий<small>🔑 ключ здесь</small></div>
      <div class="dv" style="left:225px;top:470px"><i>📱</i>Телефон<small>🔑 ключ здесь</small></div>
      <div class="sv"><b>dewiar.pro</b><code id="hex"></code><small>видит только шифр</small></div></div>
    <div class="card" id="edit"><small>ПОПРАВИЛИ НА КОМПЬЮТЕРЕ</small><div class="row"><i>📶</i>Вайфай дома — новый пароль<em>12:04</em></div>
      <div class="ar">↓</div><div class="row"><i>📱</i>На телефоне — уже новый<em class="ok">✓</em></div>
      <div class="row"><i>🗑</i>Удалили старый домофон — не вернётся<em class="ok">✓</em></div></div>
    <div class="card" id="rules"><small>ЧТОБЫ ПАРОЛЬ НЕ УВИДЕЛ НИКТО ЛИШНИЙ</small>
      <div class="row"><i>👁</i>«Показать» — на 15 секунд</div><div class="row"><i>📋</i>Буфер стирается через 30 секунд</div>
      <div class="row"><i>🔒</i>Свернули или 5 минут без дела — закрыт</div><div class="row"><i>📵</i>Снимок экрана — запрещён</div></div>
    <div class="card" id="studio"><h3>Сейф паролей</h3><small>Студия → «Сейф паролей» · телефон → «Всё» → «Сейф»</small>
      <div class="sw2">🔐 Один сейф на всех моих устройствах<span class="tgl on" style="margin-left:auto"><i></i></span></div>
      <div class="row"><i>✍️</i>Мастер-пароль — запишите: его не восстановить</div>
      <div class="row"><i>🖥</i>Сервер видит только время и шифр</div></div>
  </div>
  <div class="layer" id="L-phone"><div class="phone"><div class="scr">
    <div class="pn" id="pA"><h5>🔐 Сейф<small>● открыт</small></h5><div class="srch">🔎 магазин</div>
      <div class="rec"><div class="t"><i>🛒</i><div><b>Дом и сад</b><small>интернет-магазин</small></div></div><label>ЛОГИН</label><div class="v">patrik</div>
        <label>ПАРОЛЬ</label><div class="v">• • • • • • • •</div><div class="bts"><span>👁 Показать</span><span id="cpy">📋 Скопировать</span></div></div>
      <div class="clip" id="clip">""" + RING.format(id="r1") + """<div><b id="clipb">Скопировано</b><span id="clips">сотрётся из буфера через 30 с</span></div></div></div>
    <div class="pn" id="pB1"><h5>Всё</h5><div class="apps">""" + "".join(f'<span class="{"on" if n == "Сейф" else ""}"><i>{e}</i>{n}</span>' for e, n in APPS) + """</div></div>
    <div class="pn" id="pB2"><h5>🔐 Сейф</h5><div style="font-size:16px;font-weight:700;color:var(--mut)">Мастер-пароль — тот же, что на компьютере</div><div class="mpw" id="mpw2"></div></div>
    <div class="pn lst" id="pB3"><h5>🔐 Сейф<small>● открыт</small></h5><div class="srch">🔎 поиск</div>
      <div class="rw"><i>📶</i>Вайфай дома<em>••••••</em></div><div class="rw"><i>🛒</i>Дом и сад<em>••••••••</em></div><div class="rw"><i>🔢</i>Домофон<em>••••</em></div>
      <div class="rw"><i>💳</i>ПИН карты<em>••••</em></div><div class="rw"><i>🏦</i>Банк онлайн<em>••••••</em></div></div>
    <div class="pn" id="pC"><h5>🔐 Сейф<small>● открыт</small></h5>
      <div class="rec"><div class="t"><i>📶</i><div><b>Вайфай дома</b><small>сеть Home_5G</small></div></div><label>ПАРОЛЬ</label><div class="v pwv" id="pwv">Solnce-25!</div>
        <div class="bts"><span class="on" id="eye">👁 Скрыть</span><span>📋 Скопировать</span></div></div>
      <div class="clip">""" + RING.format(id="r2") + """<div><b>Пароль на экране</b><span>скроется сам</span></div></div>
      <div class="lock" id="lk"><div><i>🔒</i><b>Сейф закрыт</b><small>Свернули телефон — закрылся сам</small></div></div></div>
  </div></div></div>
"""
JS = """
  layer("L-left", T, s("problem").start + 0.2, s("end").start);
  const ring = (id, left, total) => { $("#" + id).setAttribute("stroke-dashoffset", (119.4 * (1 - left / total)).toFixed(1)); $("#" + id + "t").textContent = Math.max(0, Math.ceil(left)); };
  const pane = (id, a, b) => vis($(id), Math.min(out((T - a) / 0.35), 1 - out((T - b + 0.3) / 0.3)), 12);
  // телефон: в живой сцене, в «телефоне» и в «защите»
  const ph = Math.max(Math.min(out((T - s("problem").start - 0.4) / 0.6), 1 - out((T - s("sync").start + 0.5) / 0.5)),
                      Math.min(out((T - s("phone").start - 0.2) / 0.6), 1 - out((T - s("how").start + 0.5) / 0.5)));
  vis($("#L-phone"), clamp(ph));
  scene($("#shop"), T, s("problem").start + 0.3, s("sync").start, 24);
  pane("#pA", s("problem").start + 0.2, s("sync").start);
  const tc = at("s2b") + 1.6, cp = T > tc;
  $("#cpy").classList.toggle("on", cp);
  vis($("#clip"), Math.min(out((T - tc) / 0.35), 1), 16);
  const left = 30 - clamp((T - tc - 0.6) / 4.2) * 30; ring("r1", left, 30);
  const wiped = left <= 0; $("#clipb").textContent = wiped ? "Буфер очищен ✓" : "Скопировано"; $("#clips").textContent = wiped ? "пароля там больше нет" : "сотрётся из буфера через " + Math.ceil(left) + " с";
  $("#spw").textContent = T > tc + 0.9 ? "• • • • • • • • • •" : ""; $("#sgo").classList.toggle("ok", T > tc + 1.6); $("#sgo").textContent = T > tc + 1.6 ? "Вход выполнен ✓" : "Войти и оплатить";
  scene($("#syn"), T, s("sync").start + 0.2, s("master").start);
  const on = T > s("sync").start + 3.2; $("#tg1").classList.toggle("on", on); $("#sw").classList.toggle("on", on);
  scene($("#mp"), T, s("master").start + 0.2, s("phone").start);
  const km = (T - s("master").start - 0.8) / 1.4; $("#mpi").textContent = "•".repeat(Math.round(12 * clamp(km)));
  scene($("#dg"), T, s("master").start + 1.6, s("phone").start, 24);
  [...$("#dg").querySelectorAll(".dv")].forEach((c, i) => vis(c, out((T - s("master").start - 2.0 - i * 0.3) / 0.4), 14));
  const H = "0123456789abcdef"; let hx = ""; for (let i = 0; i < 60; i++) hx += H[Math.floor((Math.sin(i * 12.9898 + Math.floor(T * 6)) * 43758.5453 % 1 + 1) % 1 * 16)] + (i % 4 === 3 ? " " : "");
  $("#hex").textContent = hx;
  pane("#pB1", s("phone").start + 0.2, s("phone").start + 2.6);
  pane("#pB2", s("phone").start + 2.6, s("phone").start + 4.6);
  $("#mpw2").textContent = "•".repeat(Math.round(12 * clamp((T - s("phone").start - 3.0) / 1.0)));
  pane("#pB3", s("phone").start + 4.6, s("guard").start);
  scene($("#edit"), T, s("phone").start + 0.3, s("guard").start);
  [...$("#edit").querySelectorAll(".row, .ar")].forEach((c, i) => vis(c, out((T - s("phone").start - 0.8 - i * 0.7) / 0.4), 12));
  pane("#pC", s("guard").start + 0.1, s("how").start + 0.4);
  const lt = 15 - clamp((T - s("guard").start - 0.8) / 3.0) * 15; ring("r2", lt, 15);
  $("#pwv").textContent = lt > 0 ? "Solnce-25!" : "• • • • • • • •";
  $("#eye").classList.toggle("on", lt > 0); $("#eye").textContent = lt > 0 ? "👁 Скрыть" : "👁 Показать";
  vis($("#lk"), out((T - end("s6a") + 1.4) / 0.5), 0, 1.04);
  scene($("#rules"), T, s("guard").start + 0.2, s("how").start);
  [...$("#rules").querySelectorAll(".row")].forEach((c, i) => vis(c, out((T - s("guard").start - 0.6 - i * 0.6) / 0.4), 12));
  scene($("#studio"), T, s("how").start + 0.2, s("end").start);
  [...$("#studio").querySelectorAll(".sw2, .row")].forEach((c, i) => vis(c, out((T - s("how").start - 0.6 - i * 0.4) / 0.4), 12));
"""
