import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kit import KIT_CSS, MESS_JS, mess
TITLE = "Урок 16 · Напоминания"
IDEA = "Главная вещь урока — фраза превращается в напоминание с повтором: дни недели загораются сами, как их назвали."
H1 = "Напоминания"
TAG = "Скажите, когда и что, — остальное я"
NEXT = "Скоро — новые уроки"
ICON = '<svg viewBox="0 0 24 24"><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.9 1.9 0 0 0 3.4 0"/></svg>'
SCENES = ["title", "problem", "say", "days", "ring", "phone", "how", "end"]
POS = {"problem": "{ lira: [330, 470, 280, 1], patrik: [330, 470, 300, 0] }"}
CSS = KIT_CSS + """
#rem { top: 330px; } #rem .big { font-size: 54px; }
#wk { top: 170px; width: 1100px; } .wk { display: grid; grid-template-columns: repeat(7, 1fr); gap: 10px; margin-top: 12px; }
.wk span { text-align: center; padding: 16px 0; border-radius: 16px; box-shadow: var(--press); font-size: 21px; font-weight: 800; color: var(--mut); transition: none; }
.wk span.on { color: #fff; background: var(--brand); box-shadow: none; }
.wl { display: flex; align-items: center; gap: 18px; margin-top: 22px; font-size: 24px; font-weight: 800; } .wl b { min-width: 420px; }
#alarm { left: 760px; top: 170px; width: 620px; text-align: center; }
#alarm .big { font-size: 96px; margin: 8px 0 4px; } #alarm p { font-size: 28px; font-weight: 700; }
#alarm .bt { display: flex; gap: 12px; justify-content: center; margin-top: 22px; } #alarm .bt span { padding: 16px 22px; border-radius: 18px; box-shadow: var(--raise-s); font-size: 21px; font-weight: 800; }
#alarm .bt span.on { color: #fff; background: var(--brand); box-shadow: none; }
#ans { left: 620px; top: 600px; width: 520px; padding: 20px 26px; }
#cal { top: 170px; width: 1000px; }
"""
DAYS = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
HTML = """
  <div class="layer" id="L-left">
    """ + mess(["📞 Позвонить маме", "🌐 Оплатить интернет", "🗑 Мусор по вторникам", "💊 Витамины", "🎂 День рождения Оли", "🚗 Техосмотр", "📚 Сдать книгу", "🦷 Записаться к врачу"], "Всё не упомнишь") + """
    <div class="say" id="q1">«Напомни завтра в девять позвонить маме»</div>
    <div class="card" id="rem"><small>НАПОМИНАНИЕ</small><div class="big">Завтра, 9:00</div><div class="row"><i>📞</i>Позвонить маме<em class="ok">записала ✓</em></div></div>
    <div class="card" id="wk"><small>ПОВТОРЫ — КАК ГОВОРИТЕ ВЫ</small>
      <div class="wl" id="w0"><b>«По будням, кроме пятницы»</b><div class="wk" style="flex:1">""" + "".join(f'<span data-d="{i}">{d}</span>' for i, d in enumerate(DAYS)) + """</div></div>
      <div class="wl" id="w1"><b>«Каждый вторник и четверг»</b><div class="wk" style="flex:1">""" + "".join(f'<span data-d="{i}">{d}</span>' for i, d in enumerate(DAYS)) + """</div></div>
      <div class="wl" id="w2"><b>«Каждый месяц 5 числа»</b><div class="chips" style="margin:0"><span class="on">5 ноября</span><span>5 декабря</span><span>5 января</span></div></div></div>
    <div class="card" id="alarm"><small>НАПОМИНАНИЕ · 9:00</small><div class="big">9:00</div><p>📞 Позвонить маме</p>
      <div class="bt"><span id="bt1">Готово</span><span id="bt2">Через 10 мин</span><span>Через час</span></div></div>
    <div class="say" id="a1" style="left:620px;top:640px;max-width:420px">«Понял»</div>
    <div class="say" id="a2" style="left:620px;top:640px;max-width:520px">«Отложи на десять минут»</div>
    <div class="card" id="cal"><h3>Дела и напоминания</h3>
      <div class="row"><i>📞</i>Позвонить маме<em>завтра 9:00</em></div>
      <div class="row"><i>🗑</i>Вынести мусор<em>вт, чт · 19:00</em></div>
      <div class="row"><i>🧾</i>Планёрка<em>пн–чт · 9:00</em></div>
      <div class="row"><i>🌐</i>Оплатить интернет<em>5 числа</em></div></div>
  </div>
  <div class="layer" id="L-phone"><div class="phone"><div class="scr"><h5>Напоминание</h5><div class="big" style="font-size:72px">9:00</div>
    <div class="bub">📞 Позвонить маме</div><div class="bub" style="color:var(--mut);font-size:16px">Компьютер выключен — звенит телефон</div></div></div></div>
"""
JS = MESS_JS + """
  layer("L-left", T, s("problem").start + 0.2, s("end").start);
  scene($("#q1"), T, s("say").start + 0.2, s("days").start, 20);
  scene($("#rem"), T, s("say").start + 2.4, s("days").start, 24);
  scene($("#wk"), T, s("days").start + 0.2, s("ring").start);
  const D0 = [0, 1, 2, 3], D1 = [1, 3], t0 = s("days").start;
  [...$("#w0").querySelectorAll("span[data-d]")].forEach(e => { const d = +e.dataset.d; e.classList.toggle("on", D0.includes(d) && T > t0 + 1.6 + d * 0.18); });
  [...$("#w1").querySelectorAll("span[data-d]")].forEach(e => { const d = +e.dataset.d; e.classList.toggle("on", D1.includes(d) && T > t0 + 4.6 + d * 0.15); });
  ["#w0", "#w1", "#w2"].forEach((id, i) => vis($(id), out((T - t0 - 0.8 - i * 3.0) / 0.4), 12));
  scene($("#alarm"), T, s("ring").start + 0.2, s("phone").start);
  $("#alarm .big").style.transform = `rotate(${Math.sin(T * 30) * (T < at("s5a") + 2 ? 2.5 : 0)}deg)`;
  scene($("#a1"), T, at("s5a") + 3.0, at("s5b"), 16); scene($("#a2"), T, at("s5b") + 0.4, s("phone").start, 16);
  $("#bt1").classList.toggle("on", T > at("s5a") + 3.4 && T < at("s5b")); $("#bt2").classList.toggle("on", T > at("s5b") + 0.8);
  layer("L-phone", T, s("phone").start + 0.2, s("how").start);
  scene($("#cal"), T, s("how").start + 0.2, s("end").start);
  [...$("#cal").querySelectorAll(".row")].forEach((c, i) => vis(c, out((T - s("how").start - 0.6 - i * 0.3) / 0.4), 12));
"""
