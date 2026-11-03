import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kit import KIT_CSS, KIT2_CSS, qr
TITLE = "Урок 21 · Сайты"
IDEA = "Главная вещь урока — сайт собирается на глазах: попросили словами — готов и на телефоне, переделали одной фразой — опубликован, заявки пошли."
H1 = "Сайты"
TAG = "Расскажите, что у вас за дело, — сайт готов через минуту"
NEXT = "Скоро — новые уроки"
ICON = '<svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="16" rx="3"/><path d="M3 9h18"/><circle cx="6" cy="6.5" r=".6"/><circle cx="8.4" cy="6.5" r=".6"/><path d="M7 13h6M7 16h4"/></svg>'
SCENES = ["title", "problem", "ask", "redo", "publish", "leads", "how", "end"]
# живая сцена: Патрик просит, Лира отвечает — оба на виду
POS = {"problem": "{ lira: [330, 730, 210, 1], patrik: [330, 350, 250, 1] }"}
CSS = KIT_CSS + KIT2_CSS + """
.site { --sb: #FBF4EC; --sf: #3A2A1F; --sm: rgba(58,42,31,.62); --sa: #B8652E; --sk: #fff; --sc: #FFFFFF; --sh: #F3E3D2;
  position: relative; height: 520px; overflow: hidden; border-radius: 16px; background: var(--sb); color: var(--sf); font-family: Manrope; }
.site.dk { --sb: #16110E; --sf: #F5EBDD; --sm: rgba(245,235,221,.6); --sa: #E2A25E; --sk: #16110E; --sc: #231B16; --sh: #2E241D; }
.site .nv { display: flex; align-items: center; gap: 22px; padding: 18px 26px; font-size: 15px; font-weight: 700; }
.site .lg { display: flex; align-items: center; gap: 9px; font: 700 20px Unbounded; }
.site .lg i { width: 32px; height: 32px; border-radius: 50%; display: grid; place-items: center; font-size: 17px; font-style: normal; background: var(--sa); }
.site .nv span { color: var(--sm); } .site .bt { padding: 10px 18px; border-radius: 99px; background: var(--sa); color: var(--sk); font-weight: 800; white-space: nowrap; }
.site .nv .bt { margin-left: auto; font-size: 14px; }
.site .hero { display: grid; grid-template-columns: 1.1fr .9fr; gap: 20px; align-items: center; padding: 6px 26px 0; }
.site h4 { font: 700 38px/1.08 Unbounded; letter-spacing: -.02em; } .site .hero p { font-size: 16px; font-weight: 600; color: var(--sm); margin: 12px 0 18px; line-height: 1.45; }
.site .hero .bt { display: inline-block; font-size: 16px; padding: 13px 22px; }
.site .ill { height: 210px; border-radius: 26px; background: radial-gradient(80% 80% at 30% 20%, var(--sc), var(--sh)); display: grid; place-items: center; }
.site .ill svg { width: 190px; }
.site .mn { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; padding: 22px 26px 0; }
.site .mn div { display: flex; align-items: center; gap: 12px; padding: 12px 14px; border-radius: 18px; background: var(--sc); }
.site .mn i { flex: none; width: 44px; height: 44px; border-radius: 50%; display: grid; place-items: center; font-size: 22px; font-style: normal; background: var(--sh); }
.site .mn b { display: block; font-size: 15px; } .site .mn small { display: block; font-size: 13px; font-weight: 600; color: var(--sm); }
.site .ft { position: absolute; left: 26px; right: 26px; bottom: 16px; display: flex; align-items: center; gap: 14px; font-size: 14px; font-weight: 700; color: var(--sm); }
.site .lw { margin-left: auto; display: flex; align-items: center; gap: 10px; }
.site .lw p { padding: 9px 14px; border-radius: 16px 16px 4px 16px; background: var(--sc); color: var(--sf); font-size: 13px; font-weight: 800; box-shadow: 0 8px 20px rgba(40,20,10,.14); }
.site .lw img { width: 50px; height: 50px; border-radius: 50%; object-fit: cover; box-shadow: 0 0 0 3px var(--sa); }
/* телефонный вид того же сайта */
.phone .scr.web { padding: 0; background: none; }
.site.m { height: 100%; border-radius: 42px; }
.site.m .nv { padding: 34px 22px 10px; } .site.m .nv .bt { font-size: 20px; padding: 6px 14px; }
.site.m .hero { grid-template-columns: 1fr; padding: 6px 22px 0; gap: 12px; } .site.m h4 { font-size: 30px; }
.site.m .hero p { margin: 8px 0 12px; font-size: 15px; } .site.m .ill { height: 150px; } .site.m .ill svg { width: 140px; }
.site.m .mn { grid-template-columns: 1fr; gap: 10px; padding: 14px 22px 0; } .site.m .mn div:nth-child(n+2) { display: none; } .site.m .nv span { display: none; }
.site.m .ft { left: 22px; right: 22px; bottom: 22px; } .site.m .ft > span { display: none; }
#w1 { top: 150px; } #ph1 { top: 150px; }
#lead { left: 740px; top: 768px; width: 640px; }
#tell { top: 330px; width: 760px; }
#tell .in { margin-top: 10px; padding: 18px 22px; border-radius: 18px; box-shadow: var(--press); font-size: 24px; font-weight: 700; min-height: 66px; }
#tell .in::after { content: "|"; color: var(--accent); margin-left: 2px; opacity: var(--cur, 0); }
#tell .chips span { font-size: 19px; padding: 11px 16px; }
#mk { position: absolute; left: 620px; top: 720px; display: flex; gap: 12px; } #mk span { padding: 12px 18px; border-radius: 16px; background: var(--bg); box-shadow: var(--raise-s); font-size: 19px; font-weight: 800; }
#mk span.ok { color: #1e7d5b; }
#q2 { left: 640px; top: 140px; }
#w2 { top: 250px; } #w2 .pic { position: relative; } #w2 .site.dk { position: absolute; inset: 0; }
#hist { left: 1440px; top: 250px; width: 380px; padding: 26px 26px; } #hist .row { font-size: 19px; padding: 13px 15px; } #hist .row em { font-size: 15px; padding: 7px 11px; }
#pub { top: 190px; width: 760px; }
#pub .in { display: flex; align-items: center; margin-top: 10px; padding: 18px 22px; border-radius: 18px; box-shadow: var(--press); font-size: 28px; font-weight: 800; min-height: 72px; }
#pub .in u { text-decoration: none; color: var(--mut); } #pub .in b::after { content: "|"; display: inline-block; width: 0; color: var(--accent); opacity: var(--cur, 0); }
#pub .go { margin-top: 26px; display: inline-block; padding: 18px 34px; border-radius: 20px; color: #fff; background: var(--brand); font-size: 23px; font-weight: 800; }
#pub .go.ok { background: linear-gradient(135deg, #46d39a, #2fb383); }
#qr { left: 1440px; top: 190px; width: 380px; padding: 28px; text-align: center; }
#qr .q { display: inline-block; padding: 16px; border-radius: 22px; background: #fff; line-height: 0; } #qr p { margin-top: 16px; font-size: 21px; font-weight: 800; }
#qr span { display: block; margin-top: 6px; font-size: 17px; font-weight: 700; color: var(--mut); }
#leads { top: 160px; width: 640px; padding: 30px 32px; } #leads .row { font-size: 21px; padding: 14px 16px; } #leads .row em { font-size: 16px; }
#leads .to { margin-top: 20px; font-size: 20px; font-weight: 800; color: #1e7d5b; }
#ana { left: 1300px; top: 160px; width: 520px; padding: 30px 32px; }
#ana .big { font-size: 54px; } #ana .big span { font: 700 20px Manrope; color: var(--mut); margin-left: 8px; }
#ana .bars { display: flex; align-items: flex-end; gap: 12px; height: 170px; margin-top: 14px; }
#ana .bars div { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: flex-end; height: 100%; gap: 6px; font-size: 15px; font-weight: 800; color: var(--mut); }
#ana .bars i { width: 100%; border-radius: 10px 10px 4px 4px; background: var(--brand); }
#ana .src { margin-top: 18px; display: flex; flex-direction: column; gap: 8px; }
#ana .src div { display: grid; grid-template-columns: 170px 1fr 52px; align-items: center; gap: 12px; font-size: 18px; font-weight: 700; }
#ana .src s { height: 12px; border-radius: 99px; background: rgba(69,96,234,.12); text-decoration: none; position: relative; overflow: hidden; }
#ana .src s i { position: absolute; inset: 0 auto 0 0; border-radius: 99px; background: var(--brand); }
#ana .src b { text-align: right; }
#studio { top: 170px; width: 900px; }
"""
CUP = ('<svg viewBox="0 0 200 170"><g fill="none" stroke-width="5" stroke-linecap="round" style="stroke:var(--sa)" opacity=".55">'
       '<path d="M74 52c-10-12 10-20 0-34"/><path d="M100 50c-10-12 10-20 0-34"/><path d="M126 52c-10-12 10-20 0-34"/></g>'
       '<ellipse cx="100" cy="150" rx="86" ry="14" style="fill:var(--sf)" opacity=".12"/>'
       '<path d="M40 70h120l-10 62a24 24 0 0 1-24 20H74a24 24 0 0 1-24-20z" style="fill:var(--sa)"/>'
       '<path d="M158 82h10a18 18 0 0 1 0 36h-14" fill="none" stroke-width="9" style="stroke:var(--sa)"/>'
       '<path d="M52 84h96" stroke="#fff" stroke-opacity=".35" stroke-width="5" stroke-linecap="round"/></svg>')


def site(cls=""):
    return f"""<div class="site {cls}">
      <div class="nv"><div class="lg"><i>☕</i>Зерно</div><span>Меню</span><span>Завтраки</span><span>Контакты</span><div class="bt">{'☰' if 'm' in cls.split() else 'Забронировать'}</div></div>
      <div class="hero"><div><h4>Кофе и завтраки на Садовой</h4><p>Каждый день с 8:00 до 22:00,<br>завтраки — до полудня</p><div class="bt">Забронировать столик</div></div><div class="ill">{CUP}</div></div>
      <div class="mn"><div><i>☕</i><span><b>Капучино</b><small>на овсяном</small></span></div><div><i>🥞</i><span><b>Сырники</b><small>со сметаной</small></span></div><div><i>🥐</i><span><b>Круассан</b><small>с миндалём</small></span></div></div>
      <div class="ft"><span>📍 Садовая, 12</span><div class="lw"><p>Забронировать столик?</p><img src="../../../../data/avatars/lira.webp" alt=""></div></div></div>"""


def win(wid, body, addr="zerno.dewiar.pro"):
    return f'<div class="win" id="{wid}"><div class="bar"><i></i><i></i><i></i><span>🔒 <b>{addr}</b></span></div><div class="pic">{body}</div></div>'


TPL = [("☕", "Кофейня", True), ("💇", "Салон", False), ("⚖️", "Юрист", False), ("🎓", "Онлайн-школа", False), ("🛍", "Магазин", False), ("📷", "Фотограф", False)]
BARS = [("пн", 38), ("вт", 46), ("ср", 52), ("чт", 61), ("пт", 78), ("сб", 100), ("вс", 92)]
SRC = [("🔎 Поиск", 46), ("📱 QR на витрине", 28), ("💬 Соцсети", 26)]
HTML = """
  <div class="layer" id="L-left">
    """ + win("w1", site()) + """
    <div class="toast" id="lead"><i>🙋</i><div><small>НОВАЯ ЗАЯВКА · С САЙТА</small><b>Анна — столик на четверых, сегодня в 19:00</b></div></div>
    <div class="say" id="q1">«Кофейня на Садовой, завтраки, бронь столиков»</div>
    <div class="card" id="tell"><small>РАССКАЖИТЕ О СВОЁМ ДЕЛЕ — ИЛИ ВОЗЬМИТЕ ШАБЛОН</small><div class="in" id="tin"></div>
      <div class="chips">""" + "".join(f'<span class="{"on" if on else ""}">{e} {n}</span>' for e, n, on in TPL) + """</div></div>
    <div id="mk"><span>🎨 Палитра</span><span>🔤 Шрифты</span><span>🧩 Разделы</span><span>📱 Под телефон</span></div>
    <div class="say" id="q2">«Переделай в тёмных тонах»</div>
    """ + win("w2", site() + site("dk")) + """
    <div class="card" id="hist"><small>ИСТОРИЯ</small><div class="row" id="h3">🌙 Тёмные тона<em class="ok">сейчас</em></div><div class="row">🧾 Добавлены цены<em>вчера</em></div><div class="row">✨ Первый вариант<em>вчера</em></div></div>
    <div class="card" id="pub"><h3>Опубликовать</h3><small>ИМЯ САЙТА</small><div class="in"><b id="nm"></b><u>.dewiar.pro</u></div><div class="go" id="go">Опубликовать</div>
      <div class="chips" id="pch"><span>🔒 Защищённая ссылка</span><span>📱 Удобно с телефона</span><span>⚡ Без хостинга и настроек</span></div></div>
    <div class="card" id="qr"><div class="q">""" + qr() + """</div><p>zerno.dewiar.pro</p><span>Распечатайте — и на витрину</span></div>
    <div class="card" id="leads"><small>ЗАЯВКИ</small>
      <div class="row"><i>🙋</i>Анна · столик на 4, 19:00<em>с формы</em></div>
      <div class="row"><i>💬</i>Олег · торт к пятнице<em>из чата Лиры</em></div>
      <div class="row"><i>🙋</i>Мария · завтрак на шестерых<em>с формы</em></div>
      <div class="to">→ уже в «Клиентах», с телефоном и пожеланием</div></div>
    <div class="card" id="ana"><small>АНАЛИТИКА · 7 ДНЕЙ</small><div class="big">412<span>посещений</span></div>
      <div class="bars">""" + "".join(f'<div><i data-h="{h}"></i>{d}</div>' for d, h in BARS) + """</div>
      <div class="src">""" + "".join(f'<div>{n}<s><i data-w="{w}"></i></s><b>{w}%</b></div>' for n, w in SRC) + """</div></div>
    <div class="card" id="studio"><h3>Сайты</h3><small>Студия → «Сайты»</small>
      <div class="row"><i>🗣</i>Расскажите о деле — или шаблон<em>11 шаблонов</em></div>
      <div class="row"><i>✏️</i>Редактор и «Сказать Лире»<em>история версий</em></div>
      <div class="row"><i>🚀</i>Опубликовать на имя.dewiar.pro<em>QR-код</em></div>
      <div class="row"><i>📊</i>Аналитика, заявки, продвижение<em>без cookie</em></div></div>
  </div>
  <div class="layer" id="L-phone"><div class="phone" id="ph1"><div class="scr web">""" + site("m") + """</div></div></div>
"""
JS = """
  layer("L-left", T, s("problem").start + 0.2, s("end").start);
  // живая сцена: сайт собирается по частям, рядом — он же на телефоне, и приходит заявка
  scene($("#w1"), T, end("s2a") - 0.6, s("ask").start, 24);
  const t1 = end("s2a") - 0.3;
  [...$("#w1 .site").children].forEach((c, i) => { const k = out((T - t1 - i * 0.28) / 0.45); c.style.opacity = k; c.style.transform = `translateY(${(1 - k) * 18}px)`; });
  layer("L-phone", T, at("s2b") + 0.6, s("ask").start + 0.1);
  if (T > s("ask").start) layer("L-phone", T, at("s3a") + 3.6, s("redo").start);
  $("#ph1").style.transform = `translateY(${(1 - out((T - at("s2b") - 0.6) / 0.6)) * 30}px)`;
  scene($("#lead"), T, at("s2b") + 3.2, s("ask").start, 30);
  scene($("#q1"), T, s("ask").start + 0.2, s("redo").start, 20);
  scene($("#tell"), T, s("ask").start + 0.4, s("redo").start, 24);
  const kt = (T - s("ask").start - 1.2) / 1.8;
  $("#tin").textContent = type("кофейня на Садовой, завтраки, бронь", kt);
  $("#tin").style.setProperty("--cur", kt > 0 && kt < 1.4 ? (Math.floor(T * 2) % 2) : 0);
  scene($("#mk"), T, s("ask").start + 3.4, s("redo").start, 16);
  [...$("#mk").children].forEach((c, i) => { const d = T > s("ask").start + 3.8 + i * 0.5; c.classList.toggle("ok", d); c.textContent = c.textContent.replace(/ ✓$/, "") + (d ? " ✓" : ""); });
  scene($("#q2"), T, s("redo").start + 0.2, s("publish").start, 20);
  scene($("#w2"), T, s("redo").start + 0.4, s("publish").start, 24);
  const wipe = ease((T - s("redo").start - 2.4) / 1.1);
  $("#w2 .site.dk").style.clipPath = `inset(0 ${(1 - wipe) * 100}% 0 0)`;
  scene($("#hist"), T, s("redo").start + 3.6, s("publish").start, 24);
  vis($("#h3"), out((T - s("redo").start - 3.9) / 0.4), 10);
  scene($("#pub"), T, s("publish").start + 0.2, s("leads").start);
  const kn = (T - s("publish").start - 1.0) / 0.8;
  $("#nm").textContent = type("zerno", kn); $("#nm").style.setProperty("--cur", kn > 0 && kn < 1.6 ? (Math.floor(T * 2) % 2) : 0);
  const pub = T > s("publish").start + 2.6; $("#go").classList.toggle("ok", pub); $("#go").textContent = pub ? "Опубликован ✓" : "Опубликовать";
  [...$("#pch").children].forEach((c, i) => vis(c, out((T - s("publish").start - 3.2 - i * 0.3) / 0.4), 12));
  scene($("#qr"), T, s("publish").start + 3.0, s("leads").start, 24);
  scene($("#leads"), T, s("leads").start + 0.2, s("how").start);
  [...$("#leads").querySelectorAll(".row, .to")].forEach((c, i) => vis(c, out((T - s("leads").start - 0.6 - i * 0.45) / 0.4), 12));
  scene($("#ana"), T, at("s6b") - 0.2, s("how").start, 24);
  [...$("#ana .bars").querySelectorAll("i")].forEach((c, i) => { c.style.height = (+c.dataset.h * 1.3 * out((T - at("s6b") - 0.2 - i * 0.1) / 0.6)) + "px"; });
  [...$("#ana .src").querySelectorAll("i")].forEach((c, i) => { c.style.width = (+c.dataset.w * 2 * out((T - at("s6b") - 1.2 - i * 0.15) / 0.6)) + "%"; });
  scene($("#studio"), T, s("how").start + 0.2, s("end").start);
  [...$("#studio").querySelectorAll(".row")].forEach((c, i) => vis(c, out((T - s("how").start - 0.6 - i * 0.3) / 0.4), 12));
"""
