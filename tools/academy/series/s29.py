import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kit import KIT_CSS, KIT2_CSS, CURSOR, CURSOR_JS
TITLE = "Урок 29 · Статьи для сайта"
IDEA = ("Главная вещь урока — сайт сам приводит людей из поиска: одна кнопка «Вести статьи» — Лира составляет план тем, "
        "пишет черновик по свежему из Радара вашей ниши (Радар включается сам), черновик приходит на телефон, «Поправить» "
        "и «Опубликовать» — статья на сайте, в меню «Статьи», Яндекс узнаёт о ней сразу.")
H1 = "Статьи для сайта"
TAG = "Лира пишет — вы говорите «Да», а люди находят вас в поиске"
NEXT = "Скоро — новые уроки"
ICON = ('<svg viewBox="0 0 24 24"><rect x="4" y="3" width="13" height="18" rx="2.5"/><path d="M7.5 7.5h6M7.5 11h6M7.5 14.5h3.5"/>'
        '<path d="M14.5 19.5l5.6-5.6a1.5 1.5 0 0 0-2.1-2.1l-5.6 5.6-.6 2.7z"/></svg>')
SCENES = ["title", "problem", "on", "radar", "phone", "live", "how", "end"]
TWO = "{ lira: [330, 730, 210, 1], patrik: [330, 350, 250, 1] }"
POS = {"problem": TWO, "phone": TWO}

NAV = [("g", "Главное"), ("🏠", "Главная", 0), ("✳️", "Нода Лиры", 0),
       ("g", "Для себя"), ("💬", "Чат", 0), ("📅", "Календарь", 0), ("📝", "Заметки", 0),
       ("g", "Лира делает сама"), ("🧩", "Задачи", 0), ("👁", "Дозор", 0),
       ("g", "Работа"), ("🌐", "Сайты", 1), ("📡", "Радар", 0), ("🎧", "Суфлёр", 0), ("✈️", "Бот в Telegram", 0)]


def nav():
    return "".join(f'<div class="g">{x[1]}</div>' if x[0] == "g" else f'<span{" class=on" if x[2] else ""}><i>{x[0]}</i>{x[1]}</span>' for x in NAV)


TABS = ["Страницы", "Вид", "Поиск", "Статьи", "Заявки"]
PLAN = ["Как выбрать кофе для дома", "Турка или кофемашина: что выбрать", "Как хранить зёрна, чтобы не выдыхались",
        "Почему кофе горчит — и как это исправить", "Колумбия или Эфиопия: чем отличаются зёрна"]
MAT = [("8,7", "Урожай арабики в Бразилии — ниже прогноза", "coffee-news.ru"),
       ("7,9", "Светлая обжарка: почему её выбирают всё чаще", "@coffee_lab"),
       ("7,2", "Как помол меняет вкус: опыт бариста", "habr.com")]
TTL = "Как выбрать кофе для дома"
DESC = "Обжарка, помол и свежесть: три вещи, которые решают вкус"
BODY = ["Хороший кофе дома начинается с зёрен. В этом году урожай арабики в Бразилии ниже прогноза [1] — тем важнее понимать, за что вы платите.",
        "## Обжарка", "Светлая — кислинка и фрукты, тёмная — горчинка и шоколад. Светлую сейчас выбирают всё чаще [2]."]
ASK = "Какие зёрна у вас берут чаще всего?"
FIX = "добавь, что у нас берут колумбийскую"

CSS = KIT_CSS + KIT2_CSS + """
#plane svg { stroke: var(--accent); }
#stu { left: 640px; top: 112px; width: 1180px; height: 728px; grid-template-columns: 230px 1fr; }
#stu nav { padding: 24px 12px; gap: 2px; } #stu nav span { font-size: 17px; } #stu nav span i { font-style: normal; margin-right: 8px; }
#stu .pg { position: relative; padding: 24px 28px; } #stu .pg > small { font-size: 17px; }
.tabs { display: inline-flex; gap: 2px; margin-top: 14px; padding: 4px; border-radius: 16px; box-shadow: var(--press); }
.tabs i { font-style: normal; padding: 8px 15px; border-radius: 12px; font-size: 15px; font-weight: 700; color: var(--mut); }
.tabs i.on { color: var(--accent); box-shadow: var(--raise-s); }
.pane { position: absolute; left: 28px; right: 28px; top: 160px; bottom: 24px; }
.cd { padding: 16px 20px; border-radius: 22px; box-shadow: var(--raise-s); }
.cd h4 { font: 700 18px Unbounded; margin-bottom: 8px; } .cd h4 small { margin-left: 8px; font: 700 13px Manrope; color: var(--mut); }
.btn { position: relative; display: inline-block; padding: 11px 20px; border-radius: 15px; font-size: 16px; font-weight: 800; box-shadow: var(--raise-s); white-space: nowrap; }
.btn.pri { color: #fff; background: var(--brand); box-shadow: none; }
.btn.ok { color: #fff; background: linear-gradient(135deg, #46d39a, #2fb383); box-shadow: none; }
.btn::after { content: ""; position: absolute; inset: -7px; border-radius: 21px; border: 3px solid var(--accent); opacity: var(--ta, 0); transform: scale(var(--ts, 1)); }
/* приглашение */
#zero { padding: 34px 38px; } #zero h4 { font-size: 26px; margin-bottom: 10px; }
#zero > p { font-size: 18px; font-weight: 600; line-height: 1.5; color: var(--mut); max-width: 760px; }
#zero ul { list-style: none; margin: 18px 0 24px; } #zero li { position: relative; padding: 7px 0 7px 34px; font-size: 18px; font-weight: 700; }
#zero li::before { content: "✓"; position: absolute; left: 0; top: 6px; width: 24px; height: 24px; border-radius: 50%; display: grid; place-items: center;
  font-size: 14px; color: #fff; background: linear-gradient(135deg, #46d39a, #2fb383); }
#zero .btn { font-size: 18px; padding: 14px 26px; }
/* вкладка «Статьи» */
.sb { display: grid; grid-template-columns: 1.35fr 1fr; gap: 16px; height: 100%; }
.nx { display: flex; align-items: center; gap: 14px; } .nx i { font-style: normal; width: 50px; height: 50px; border-radius: 16px; display: grid; place-items: center; font-size: 24px; background: rgba(69,96,234,.1); }
.nx b { display: block; font-size: 17px; } .nx small { display: block; font-size: 14px; font-weight: 700; color: var(--mut); margin-top: 2px; }
.nx .btn { margin-left: auto; }
.pl { margin-top: 14px; } .pl div { display: flex; align-items: center; gap: 10px; padding: 8px 4px; border-bottom: 1px solid rgba(36,50,74,.08); font-size: 16px; font-weight: 700; }
.pl div:last-child { border-bottom: 0; } .pl div i { font-style: normal; width: 24px; height: 24px; border-radius: 8px; display: grid; place-items: center; font-size: 12px; font-weight: 800; color: var(--accent); background: rgba(69,96,234,.1); }
.kv { display: flex; justify-content: space-between; align-items: center; padding: 8px 0; font-size: 15px; font-weight: 700; color: var(--mut); }
.kv b { color: var(--ink); padding: 6px 12px; border-radius: 12px; box-shadow: var(--press); font-size: 15px; }
.rdr { margin-top: 14px; } .rdr p { font-size: 14px; font-weight: 700; color: var(--mut); line-height: 1.45; }
.rdr p b { color: var(--ink); }
.mt { display: grid; grid-template-columns: 44px 1fr; gap: 10px; align-items: center; margin-top: 9px; padding: 9px 11px; border-radius: 14px; background: rgba(255,255,255,.55); }
.mt em { font-style: normal; font: 700 15px Unbounded; color: #3550E0; text-align: center; } .mt b { display: block; font-size: 14.5px; } .mt small { font-size: 12.5px; font-weight: 700; color: var(--mut); }
.dr { position: relative; } .dr .st2 { display: inline-block; padding: 4px 10px; border-radius: 99px; font-size: 12.5px; font-weight: 800; color: #9a6a00; background: rgba(240,180,40,.18); }
.dr h5 { font: 700 21px/1.25 Unbounded; margin: 10px 0 6px; min-height: 27px; } .dr .ds { font-size: 14px; font-weight: 700; color: var(--mut); min-height: 18px; }
.dr .tx { margin-top: 10px; font-size: 15px; font-weight: 600; line-height: 1.55; } .dr .tx h6 { font: 700 16px Unbounded; margin: 8px 0 2px; }
.rf { display: inline-grid; place-items: center; min-width: 20px; height: 20px; padding: 0 5px; border-radius: 6px; font-size: 12px; font-weight: 800; color: var(--accent); background: rgba(69,96,234,.12); vertical-align: 1px; }
.qa { margin-top: 12px; padding: 12px 14px; border-radius: 16px; background: rgba(69,96,234,.08); font-size: 15px; font-weight: 700; }
.qa small { display: block; font-size: 12.5px; font-weight: 800; color: var(--accent); margin-bottom: 3px; }
.fl { position: absolute; width: 10px; height: 10px; border-radius: 50%; background: #3550E0; box-shadow: 0 0 0 4px rgba(53,80,224,.15); }
#fact { left: 1240px; top: 30px; width: 580px; } #fact > i { background: rgba(69,96,234,.14); }
/* телефон */
.phone .scr { overflow: hidden; }
.phone .scr.lock { background: linear-gradient(160deg, #cfdcf2, #e8eef8); padding: 60px 18px; text-align: center; }
.lock .tm { font: 600 64px Unbounded; color: #24324a; } .lock .dd { font-size: 17px; font-weight: 700; color: var(--mut); margin-bottom: 28px; }
.pn { text-align: left; padding: 14px 16px; border-radius: 20px; background: rgba(255,255,255,.88); box-shadow: 0 10px 24px -14px rgba(36,50,74,.5); }
.pn small { display: flex; align-items: center; gap: 8px; font-size: 13px; font-weight: 800; color: var(--mut); } .pn small img { width: 22px; height: 22px; border-radius: 6px; }
.pn b { display: block; margin-top: 6px; font-size: 17px; } .pn span { display: block; margin-top: 3px; font-size: 15px; font-weight: 600; line-height: 1.4; }
.scr.ed { position: absolute; inset: 20px; border-radius: 40px; background: var(--bg); padding: 34px 20px 20px; text-align: left; }
.ed h5 { font-size: 13px; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; color: var(--mut); }
.ed .f { margin-top: 8px; padding: 10px 12px; border-radius: 14px; box-shadow: var(--press); font-size: 15px; font-weight: 700; line-height: 1.4; }
.ed .f.t { font-size: 17px; font-weight: 800; } .ed .f.b { height: 150px; overflow: hidden; font-weight: 600; font-size: 14px; color: #33415c; }
.ed .qa { font-size: 14px; }
.ed .fx { display: flex; gap: 6px; margin-top: 10px; } .ed .fx .f { flex: 1; margin: 0; font-size: 14px; min-height: 40px; } .ed .fx .f.ph { color: var(--mut); }
.ed .fx .btn { padding: 10px 12px; font-size: 14px; }
.ed .ok2 { margin-top: 8px; font-size: 13px; font-weight: 800; color: #1e7d5b; min-height: 17px; }
.ed .btn.pub { display: block; text-align: center; margin-top: 12px; font-size: 17px; padding: 13px; }
#drt { left: 640px; top: 300px; width: 560px; } #drt b { font-size: 20px; }
#L-phone .phone { left: 1280px; } #drt > i { background: rgba(240,180,40,.2); }
/* сайт со статьёй */
#w3 { left: 640px; top: 110px; width: 1180px; }
.site { --sb: #FBF4EC; --sf: #3A2A1F; --sm: rgba(58,42,31,.62); --sa: #B8652E; --sc: #FFFFFF; --sh: #F3E3D2;
  position: relative; height: 610px; overflow: hidden; border-radius: 16px; background: var(--sb); color: var(--sf); font-family: Manrope; }
.site .nv { display: flex; align-items: center; gap: 26px; padding: 18px 30px; font-size: 16px; font-weight: 700; }
.site .lg { display: flex; align-items: center; gap: 9px; font: 700 20px Unbounded; margin-right: 10px; }
.site .lg i { width: 32px; height: 32px; border-radius: 50%; display: grid; place-items: center; font-size: 17px; font-style: normal; background: var(--sa); }
.site .nv span { color: var(--sm); } .site .nv span.new { color: var(--sf); position: relative; }
.site .nv span.new::after { content: ""; position: absolute; left: -10px; right: -10px; top: -7px; bottom: -7px; border-radius: 99px; border: 2.5px solid var(--sa); opacity: var(--na, 0); }
.site .bt { margin-left: auto; padding: 10px 18px; border-radius: 99px; background: var(--sa); color: #fff; font-weight: 800; font-size: 14px; }
.site .art { max-width: 760px; margin: 8px auto 0; }
.site .cr { font-size: 14px; font-weight: 700; color: var(--sm); } .site h4 { font: 700 40px/1.12 Unbounded; letter-spacing: -.02em; margin: 10px 0 10px; }
.site .me { font-size: 14px; font-weight: 700; color: var(--sm); } .site .art p { font-size: 18px; line-height: 1.6; margin-top: 16px; }
.site .art h6 { font: 700 22px Unbounded; margin-top: 20px; }
.site .art p .rf { background: var(--sh); color: var(--sa); }
.site .rs { margin-top: 18px; padding: 14px 18px; border-radius: 18px; background: var(--sc); font-size: 14px; font-weight: 700; color: var(--sm); }
.site .rs b { display: block; color: var(--sf); margin-bottom: 4px; }
#idx { left: 1180px; top: 700px; width: 620px; }
#studio { top: 170px; width: 900px; }
"""

PH_BODY = "Хороший кофе дома начинается с зёрен.<br><b>## Обжарка</b><br>Светлая — кислинка и фрукты, тёмная — горчинка…<br><b>## Помол</b><br>Для турки — мелкий, для фильтра — средний."

HTML = """
  <div class="layer" id="L-left">
    <div class="st" id="stu"><nav>""" + nav() + """</nav>
      <div class="pg"><h3>Кофейня «Зерно»</h3><small>zerno.dewiar.pro · опубликован</small>
        <div class="tabs" id="tabs">""" + "".join(f'<i data-t="{i}">{t}</i>' for i, t in enumerate(TABS)) + """</div>
        <div class="pane" id="pZ"><div class="cd" id="zero"><h4>Статьи приводят клиентов из поиска</h4>
            <p>Лира пишет полезные статьи на вопросы ваших клиентов — по свежим новостям вашей ниши из Радара и по тому, что есть на вашем сайте.</p>
            <ul><li>Факты о вашем деле — только с сайта: Лира не придумает цен, скидок и обещаний.</li>
              <li>Радар включится сам и подберёт источники вашей ниши — настраивать ничего не нужно.</li>
              <li>Карта сайта, страница «Статьи» в меню и оповещение Яндекса — автоматически.</li></ul>
            <span class="btn pri" id="go">Вести статьи</span></div></div>
        <div class="pane" id="pB"><div class="sb">
            <div><div class="cd nx"><i>🗓</i><div><b>Следующий черновик — вторник, 17 ноября, 10:00</b><small>«""" + PLAN[0] + """»</small></div></div>
              <div class="cd" style="margin-top:14px" id="cP"><h4>План тем<small>Лира подобрала сама</small></h4><div class="pl" id="pl">""" + "".join(
                  f'<div><i>{i + 1}</i>{t}</div>' for i, t in enumerate(PLAN)) + """</div></div>
              <div class="cd dr" style="margin-top:14px" id="cD"><span class="st2">Черновик</span><h5 id="dt"></h5><div class="ds" id="dd"></div>
                <div class="tx" id="dx"></div><div class="qa" id="dq"><small>Лира спрашивает</small>""" + ASK + """</div></div></div>
            <div><div class="cd"><h4>Как вести</h4><div class="kv">Как часто<b>Раз в неделю</b></div><div class="kv">Публикация<b>После моего «Да»</b></div><div class="kv">Длина<b>Средние</b></div></div>
              <div class="cd rdr" id="cR"><h4>Материалы из Радара</h4><p id="rt">Радар подбирает источники вашей ниши…</p><div id="ml">""" + "".join(
                  f'<div class="mt"><em>{s}</em><div><b>{t}</b><small>{w}</small></div></div>' for s, t, w in MAT) + """</div></div></div></div></div>
      </div></div>
    <div class="toast" id="fact"><i>🛡</i><div><small>ФАКТЫ О ВАШЕМ ДЕЛЕ</small><b>Цены и скидки — только с вашего сайта</b></div></div>
    <div class="toast" id="drt"><i>📝</i><div><small>DEWIAR · СТАТЬИ САЙТА</small><b>Черновик статьи для сайта: «""" + TTL + """»</b></div></div>
    <div class="win" id="w3"><div class="bar"><i></i><i></i><i></i><span><b>zerno.dewiar.pro</b>/blog/kak-vybrat-kofe-dlya-doma</span></div>
      <div class="site"><div class="nv"><div class="lg"><i>☕</i>Зерно</div><span>Меню</span><span>О нас</span><span class="new" id="nnew">Статьи</span><span>Контакты</span><span class="bt">Заказать</span></div>
        <div class="art"><div class="cr">Главная › Статьи</div><h4>""" + TTL + """</h4><div class="me">12 ноября 2026 · 4 минуты</div>
          <p>Хороший кофе дома начинается с зёрен. В этом году урожай арабики в Бразилии ниже прогноза <span class="rf">1</span> — тем важнее понимать, за что вы платите.</p>
          <h6>Обжарка</h6><p>Светлая — кислинка и фрукты, тёмная — горчинка и шоколад. У нас чаще всего берут колумбийскую арабику средней обжарки.</p>
          <div class="rs"><b>Источники</b>1. Урожай арабики в Бразилии — ниже прогноза · 2. Светлая обжарка: почему её выбирают всё чаще</div></div></div></div>
    <div class="toast" id="idx"><i>🔎</i><div><small>ПОИСК УЗНАЛ СРАЗУ</small><b>Яндекс оповещён о новой статье</b></div></div>
    <div class="card" id="studio"><h3>Статьи для сайта</h3><small>Студия → «Сайты» → ваш сайт → «Статьи»</small>
      <div class="row"><i>🗓</i>План тем и расписание<em>Лира составит сама</em></div>
      <div class="row"><i>📡</i>Свежее из Радара вашей ниши<em>включится сам</em></div>
      <div class="row"><i>📱</i>Черновик — на телефон<em class="warn">«Поправить» · «Опубликовать»</em></div>
      <div class="row"><i>💬</i>«Напиши статью для сайта»<em class="ok">голосом</em></div></div>
  </div>
  <div class="layer" id="L-phone"><div class="phone"><div class="scr lock" id="lk">
    <div class="tm">10:00</div><div class="dd">вторник, 17 ноября</div>
    <div class="pn" id="pn"><small><img src="../../../../data/avatars/lira.webp" alt="">DEWIAR · сейчас</small><b>Черновик статьи для сайта</b>
      <span>«""" + TTL + """» — прочитайте и опубликуйте</span></div></div>
    <div class="scr ed" id="ed"><h5>Заголовок</h5><div class="f t" id="et">""" + TTL + """</div>
      <h5 style="margin-top:12px">Текст</h5><div class="f b">""" + PH_BODY + """<span id="eadd"></span></div>
      <div class="qa"><small>Лира спрашивает</small>""" + ASK + """</div>
      <div class="fx"><div class="f ph" id="efx">Попросить Лиру поправить</div><span class="btn" id="efb">Поправить</span></div>
      <div class="ok2" id="eok"></div><span class="btn pri pub" id="epub">Опубликовать</span></div></div></div>
  """ + CURSOR + """
"""
JS = CURSOR_JS + """
  const tap = (el, t0) => { const k = (T - t0) / 0.6; const on = k > 0 && k < 1;
    el.style.setProperty("--ta", on ? (1 - k).toFixed(3) : 0); el.style.setProperty("--ts", on ? (1 + k * 0.2).toFixed(3) : 1);
    el.style.transform = k > 0 && k < 0.22 ? "scale(.95)" : ""; };
  layer("L-left", T, s("problem").start + 0.2, s("end").start);
  // студия: «Сайты» → «Статьи» → «Вести статьи» → план; потом Радар и черновик
  const o0 = at("s3a"), od = LN.s3a.dur, tGo = o0 + od * 0.55;
  const stuOn = Math.min(out((T - at("s2b") - 0.3) / 0.5), 1 - out((T - s("phone").start + 0.4) / 0.4));
  vis($("#stu"), clamp(stuOn), 24, .97);
  [...$("#tabs").children].forEach(c => c.classList.toggle("on", +c.dataset.t === 3));
  vis($("#pZ"), T < tGo + 0.5 ? 1 : 0, 0); vis($("#pB"), out((T - tGo - 0.5) / 0.4), 10);
  tap($("#go"), tGo);
  [...$("#pl").children].forEach((c, i) => vis(c, out((T - tGo - 0.9 - i * 0.28) / 0.35), 6));
  // Радар: источники ниши подобрались, материалы читаются — из них пишется черновик
  const r0 = s("radar").start, rd = LN.s4a.dur + LN.s4b.dur;
  const nm = Math.round(41 * clamp((T - r0 - 0.4) / 2.2));
  $("#rt").innerHTML = T > r0 + 0.4 ? `Источников: <b>6</b> · материалов: <b>${nm}</b>. Из них Лира берёт свежие новости вашей ниши.` : "Радар подбирает источники вашей ниши…";
  [...$("#ml").children].forEach((c, i) => vis(c, out((T - r0 - 0.8 - i * 0.4) / 0.4), 8));
  const radar = T > r0 - 0.2;
  vis($("#cP"), radar ? 1 - out((T - r0) / 0.35) : out((T - tGo - 0.6) / 0.4), 0); $("#cP").style.display = T > r0 + 0.35 ? "none" : "";
  vis($("#cD"), out((T - r0 - 0.35) / 0.4), 10); $("#cD").style.display = T > r0 + 0.35 ? "" : "none";
  const w0 = r0 + 2.2;
  $("#dt").textContent = type(\"""" + TTL + """\", (T - w0) / 0.9);
  $("#dd").textContent = type(\"""" + DESC + """\", (T - w0 - 0.9) / 0.9);
  const BODY = """ + repr(BODY).replace("'", '"') + """.map(window.DW_FILM_TX || (s => s)), bk = clamp((T - w0 - 1.9) / (rd * 0.45));
  let left = Math.round(BODY.join("").length * bk), html = "";
  for (const b of BODY) { const piece = b.slice(0, Math.max(0, left)); left -= b.length; if (!piece) break;
    html += b.startsWith("## ") ? `<h6>${piece.slice(3)}</h6>` : `<p>${piece.replace(/\\[(\\d)\\]/g, '<span class="rf">$1</span>')}</p>`; }
  $("#dx").innerHTML = html;
  vis($("#dq"), out((T - w0 - 1.9 - rd * 0.45) / 0.4), 6);
  scene($("#fact"), T, at("s4b") + 0.2, s("phone").start, 20);
  // телефон: весточка → лист черновика → «Поправить» → «Опубликовать»
  const p0 = s("phone").start;
  scene($("#drt"), T, p0 + 0.3, s("live").start, 20);
  layer("L-phone", T, p0 + 0.4, s("live").start);
  vis($("#pn"), out((T - p0 - 1.0) / 0.5), -30);
  const tEd = at("s5b") - 0.1; vis($("#ed"), out((T - tEd) / 0.4), 20); vis($("#lk"), 1 - out((T - tEd) / 0.4), 0);
  const fx0 = at("s5b") + 0.5, fx1 = fx0 + LN.s5b.dur * 0.35, tFx = fx1 + 0.3, tPub = at("s5b") + LN.s5b.dur * 0.88;
  const fx = type(\"""" + FIX + """\", (T - fx0) / (fx1 - fx0));
  $("#efx").textContent = T > fx0 && T < tFx + 0.4 ? fx : "Попросить Лиру поправить"; $("#efx").classList.toggle("ph", !(T > fx0 && T < tFx + 0.4));
  tap($("#efb"), tFx);
  $("#eok").textContent = T > tFx + 0.7 ? "Поправила — посмотрите и сохраните" : "";
  $("#eadd").innerHTML = T > tFx + 0.7 ? "<br>У нас чаще всего берут колумбийскую." : "";
  tap($("#epub"), tPub); $("#epub").classList.toggle("ok", T > tPub + 0.3); $("#epub").textContent = T > tPub + 0.3 ? "Опубликовано ✓" : "Опубликовать";
  // сайт: статья на месте, в меню «Статьи», Яндекс оповещён
  const l0 = s("live").start;
  scene($("#w3"), T, l0 + 0.2, s("how").start, 24);
  const na = clamp((T - l0 - 1.2) / 0.4) * (1 - clamp((T - l0 - 3.2) / 0.5)); $("#nnew").style.setProperty("--na", na.toFixed(3));
  scene($("#idx"), T, at("s6a") + LN.s6a.dur * 0.6, s("how").start, 20);
  // курсор: «Вести статьи»
  cursor(walk([[o0, [1500, 760]], [tGo, ctr($("#go"))]]), Math.min(out((T - o0 + 0.1) / 0.4), 1 - out((T - tGo - 0.9) / 0.4)));
  scene($("#studio"), T, s("how").start + 0.2, s("end").start);
  [...$("#studio").querySelectorAll(".row")].forEach((c, i) => vis(c, out((T - s("how").start - 0.6 - i * 0.3) / 0.4), 12));
"""
