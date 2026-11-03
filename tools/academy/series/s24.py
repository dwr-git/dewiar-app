import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kit import KIT_CSS, KIT2_CSS
TITLE = "Урок 24 · Бот в Telegram с любого устройства"
IDEA = "Главная вещь урока — бот один на аккаунт: ноутбук выключен, а ответ уже пришёл с телефона; отвечает кто-то один, без дублей."
H1 = "Telegram везде"
TAG = "Один бот — отвечает то устройство, что на связи"
NEXT = "Скоро — новые уроки"
ICON = '<svg viewBox="0 0 24 24"><path d="M21 4 3 11l6 2 2 6 3-4 5 4 2-15z"/><path d="m9 13 8-6"/></svg>'
SCENES = ["title", "problem", "account", "who", "reserve", "how", "end"]
POS = {"problem": "{ lira: [330, 730, 210, 1], patrik: [330, 350, 250, 1] }"}
CSS = KIT_CSS + KIT2_CSS + """
#plane svg { stroke: var(--tg); }
.phone .scr.tgc { padding: 0; background: #dfe8ef; position: relative; }
.tgh { display: flex; align-items: center; gap: 12px; padding: 34px 20px 14px; background: #fff; }
.tgh img { width: 48px; height: 48px; border-radius: 50%; object-fit: cover; } .tgh b { display: block; font-size: 19px; } .tgh small { font-size: 14px; font-weight: 700; color: var(--tg); }
.tgm { padding: 10px 16px; } .tgm .bub { box-shadow: 0 2px 4px rgba(36,50,74,.08); font-size: 18px; }
.tgm .bub.me { color: var(--ink); background: #e1f9d4; }
.tgm .bub small { display: block; margin-top: 8px; font-size: 13px; font-weight: 800; color: #1e7d5b; }
.typing { display: inline-flex; gap: 5px; padding: 14px 16px; border-radius: 18px; background: #fff; margin-top: 12px; }
.typing i { width: 8px; height: 8px; border-radius: 50%; background: #9aa7b8; }
#devs { top: 210px; width: 700px; } #devs .row.act { box-shadow: 0 0 0 3px rgba(47,179,131,.6), var(--raise-s); }
#acc { position: absolute; left: 640px; top: 130px; width: 1180px; height: 700px; }
#acc svg { position: absolute; inset: 0; }
#acc .me { position: absolute; left: 400px; top: 250px; width: 380px; padding: 26px; border-radius: 32px; background: var(--bg); box-shadow: var(--raise); text-align: center; }
#acc .me i { font-size: 56px; font-style: normal; } #acc .me b { display: block; font: 700 24px Unbounded; margin-top: 6px; }
#acc .me span { display: inline-block; margin-top: 12px; padding: 10px 16px; border-radius: 14px; color: #fff; background: var(--tg); font-size: 18px; font-weight: 800; }
#acc .dv { position: absolute; width: 230px; padding: 18px; border-radius: 26px; background: var(--bg); box-shadow: var(--raise); text-align: center; font-size: 20px; font-weight: 800; }
#acc .dv i { display: block; font-size: 46px; font-style: normal; } #acc .dv small { display: block; margin-top: 4px; font-size: 15px; color: #1e7d5b; }
#acc .old { position: absolute; left: 0; top: 0; padding: 14px 20px; border-radius: 18px; box-shadow: var(--press); font-size: 19px; font-weight: 800; color: var(--mut); }
#acc .old s { color: #b04a5c; }
#wh { top: 170px; width: 860px; } #wh .row.act { box-shadow: 0 0 0 3px rgba(47,179,131,.6), var(--raise-s); }
#wh .line { margin-top: 22px; padding: 16px 20px; border-radius: 18px; box-shadow: var(--press); font-size: 20px; font-weight: 700; color: var(--mut); }
#wh .line b { color: var(--ink); }
#q1 { left: 640px; top: 640px; }
#one { position: absolute; left: 640px; top: 150px; display: flex; align-items: center; gap: 16px; padding: 16px 24px; border-radius: 22px; background: var(--bg); box-shadow: var(--raise-s); font-size: 24px; font-weight: 800; }
#one em { font-style: normal; color: #1e7d5b; }
#steps { position: absolute; left: 640px; top: 270px; width: 1180px; display: grid; grid-template-columns: repeat(3, 1fr); gap: 30px; }
.stp { padding: 26px 24px; border-radius: 30px; background: var(--bg); box-shadow: var(--raise); transition: none; }
.stp small { display: block; font-size: 16px; font-weight: 800; color: var(--mut); text-transform: uppercase; letter-spacing: .05em; }
.stp .ic { display: flex; gap: 8px; margin: 16px 0 10px; font-size: 44px; } .stp .ic .off { filter: grayscale(1); opacity: .35; }
.stp b { display: block; font-size: 23px; line-height: 1.3; } .stp p { margin-top: 10px; font-size: 18px; font-weight: 700; color: var(--mut); line-height: 1.4; }
.stp.on { box-shadow: 0 0 0 4px var(--tg), var(--raise); }
#studio { top: 150px; width: 960px; }
#studio .hd { display: flex; align-items: center; gap: 16px; margin-bottom: 6px; } #studio .hd i { width: 64px; height: 64px; border-radius: 20px; display: grid; place-items: center; font-size: 32px; font-style: normal; color: #fff; background: var(--tg); }
#studio .who { margin-top: 18px; padding: 16px 20px; border-radius: 18px; box-shadow: 0 0 0 3px rgba(42,171,238,.5), var(--raise-s); font-size: 21px; font-weight: 800; }
#studio .row .tgl { margin-left: auto; }
"""
HTML = """
  <div class="layer" id="L-left">
    <div class="card" id="devs"><small>ВАШИ УСТРОЙСТВА СЕЙЧАС</small>
      <div class="row"><i>💻</i>Ноутбук — дома<em class="warn">выключен</em></div>
      <div class="row"><i>🖥</i>Рабочий компьютер<em class="warn">выключен</em></div>
      <div class="row" id="dph"><i>📱</i>Телефон — в кармане<em class="ok" id="dphe">на связи</em></div></div>
    <div id="acc"><svg viewBox="0 0 1180 700"><g fill="none" stroke="#2AABEE" stroke-width="4" stroke-dasharray="10 10" stroke-linecap="round">
        <path id="ln0" d="M590 300 L180 120"/><path id="ln1" d="M590 300 L1000 120"/><path id="ln2" d="M590 420 L590 560"/></g></svg>
      <div class="old">Раньше: бот — у одного компьютера. <s>Второй не отвечал</s></div>
      <div class="me"><i>👤</i><b>Ваш аккаунт</b><span>✈️ Бот в Telegram</span></div>
      <div class="dv" style="left:60px;top:60px"><i>💻</i>Ноутбук<small>знает бота</small></div>
      <div class="dv" style="left:890px;top:60px"><i>🖥</i>Рабочий<small>знает бота</small></div>
      <div class="dv" style="left:475px;top:540px"><i>📱</i>Телефон<small>узнал сам</small></div></div>
    <div class="card" id="wh"><small>КТО ОТВЕЧАЕТ В TELEGRAM</small>
      <div class="row" id="w0"><i>💻</i>Ноутбук · говорили 5 минут назад<em class="ok" id="w0e">в запасе</em></div>
      <div class="row" id="w1"><i>🖥</i>Рабочий компьютер · вчера<em>в запасе</em></div>
      <div class="row" id="w2"><i>📱</i>Телефон<em>в запасе</em></div>
      <div class="line" id="wl">Отвечает: <b>Ноутбук (этот компьютер)</b> · запасные: Рабочий, Телефон</div></div>
    <div class="say" id="q1">«Лира, напомни завтра позвонить маме»</div>
    <div id="one">✉️ Одно сообщение <em>→</em> один ответ <em>· без дублей</em></div>
    <div id="steps">
      <div class="stp" id="st0"><small>Компьютер включён</small><div class="ic"><span>💻</span><span class="off">🖥</span></div><b>Отвечает ноутбук</b><p>С ним вы говорили последним</p></div>
      <div class="stp" id="st1"><small>Компьютеры выключены</small><div class="ic"><span class="off">💻</span><span>📱</span></div><b>Отвечает телефон</b><p>«Отвечать с телефона» включено само</p></div>
      <div class="stp" id="st2"><small>Никого на связи</small><div class="ic"><span class="off">📱</span><span>☁️</span></div><b>Отвечает сервер Dewiar</b><p>«Компьютер и телефон сейчас не на связи — отвечаю сам»</p></div></div>
    <div class="card" id="studio"><div class="hd"><i>✈️</i><div><h3>Telegram</h3><small>Студия → «Подключение» → «Telegram — ассистент в телефоне»</small></div></div>
      <div class="who">Отвечает: Ноутбук (этот компьютер) · запасные: Рабочий, Телефон</div>
      <div class="row"><i>🌙</i>Отвечать, когда компьютер выключен<span class="tgl on"><i></i></span></div>
      <div class="row"><i>🎙</i>На голосовые — отвечать и голосом<span class="tgl on"><i></i></span></div></div>
  </div>
  <div class="layer" id="L-phone"><div class="phone"><div class="scr tgc">
    <div class="tgh"><img src="../../../../data/avatars/lira.webp" alt=""><div><b>Лира</b><small id="tgs">в сети</small></div></div>
    <div class="tgm"><div class="bub me" id="m1">Что у меня завтра?</div><div class="typing" id="ty"><i></i><i></i><i></i></div>
      <div class="bub" id="m2">Завтра:<br>🦷 10:00 — стоматолог<br>📞 15:00 — созвон с Анной<small>ответил телефон · ноутбук выключен</small></div></div></div></div></div>
"""
JS = """
  layer("L-left", T, s("problem").start + 0.2, s("end").start);
  const p0 = s("problem").start, tr = at("s2b") - 0.2;
  layer("L-phone", T, p0 + 0.3, s("account").start);
  vis($("#m1"), out((T - at("s2a") - 1.8) / 0.35), 14);
  vis($("#ty"), T > at("s2a") + 2.4 && T < tr ? 1 : 0, 6);
  [...$("#ty").children].forEach((c, i) => { c.style.transform = `translateY(${Math.sin(T * 9 - i) * 3}px)`; });
  vis($("#m2"), out((T - tr) / 0.4), 14);
  $("#tgs").textContent = T > at("s2a") + 2.4 && T < tr ? "печатает…" : "в сети";
  scene($("#devs"), T, p0 + 0.4, s("account").start, 24);
  [...$("#devs").querySelectorAll(".row")].forEach((c, i) => vis(c, out((T - p0 - 0.8 - i * 0.35) / 0.4), 12));
  $("#dph").classList.toggle("act", T > tr); $("#dphe").textContent = T > tr ? "ответил ✓" : "на связи";
  scene($("#acc"), T, s("account").start + 0.2, s("who").start);
  const a0 = s("account").start;
  vis($("#acc .old"), Math.min(out((T - a0 - 0.4) / 0.4), 1 - out((T - a0 - 3.2) / 0.4)), 10);
  vis($("#acc .me"), out((T - a0 - 1.0) / 0.5), 16, .9);
  [...$("#acc").querySelectorAll(".dv")].forEach((c, i) => vis(c, out((T - a0 - 2.4 - i * 0.6) / 0.45), 16, .92));
  [0, 1, 2].forEach(i => { const l = $("#ln" + i), k = out((T - a0 - 2.2 - i * 0.6) / 0.5); l.style.opacity = k; l.setAttribute("stroke-dashoffset", (-T * 30).toFixed(1)); });
  scene($("#wh"), T, s("who").start + 0.2, s("reserve").start);
  const w0 = s("who").start, act = T > w0 + 2.0;
  $("#w0").classList.toggle("act", act); $("#w0e").textContent = act ? "отвечает" : "в запасе";
  vis($("#wl"), out((T - w0 - 3.4) / 0.5), 10);
  scene($("#q1"), T, w0 + 0.6, w0 + 2.6, 16);
  scene($("#one"), T, s("reserve").start + 0.2, s("how").start, 16);
  scene($("#steps"), T, s("reserve").start + 0.2, s("how").start);
  const r1 = at("s5b");
  [0, 1, 2].forEach(i => { const t0 = [s("reserve").start + 0.4, r1 + 0.2, r1 + 3.0][i]; const c = $("#st" + i);
    vis(c, out((T - t0) / 0.45), 16, .95); c.classList.toggle("on", T > t0 + 0.3 && (i === 2 || T < [r1 + 0.2, r1 + 3.0][i])); });
  scene($("#studio"), T, s("how").start + 0.2, s("end").start);
  [...$("#studio").querySelectorAll(".who, .row")].forEach((c, i) => vis(c, out((T - s("how").start - 0.6 - i * 0.4) / 0.4), 12));
"""
