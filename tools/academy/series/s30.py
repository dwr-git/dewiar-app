import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kit import KIT_CSS, KIT2_CSS, CURSOR, CURSOR_JS, mess, MESS_JS
TITLE = "Урок 30 · Лира для компании"
IDEA = ("Главная вещь урока — полный цикл компании в одном месте (владелец 19.11: «руководитель, посмотрев одно видео, сразу "
        "понимал бы, зачем она ему»): компания и общий баланс, сотрудник по ссылке, поручение голосом → «Беру» → «Сделано» с "
        "фото, доска; сайт и консультант на сайте и в Telegram; заявка → карточка клиента и поручение; сделки и кто должен; "
        "итог недели; каждому — помощник на каждый день; «Запуск компании» — пять шагов.")
H1 = "Лира для компании"
TAG = "Сотрудники, клиенты, сайт и деньги — в одном месте"
NEXT = "Скоро — новые уроки"
ICON = ('<svg viewBox="0 0 24 24"><rect x="3" y="7" width="18" height="13" rx="2.5"/><path d="M9 7V5.5A1.5 1.5 0 0 1 10.5 4h3A1.5 1.5 0 0 1 15 5.5V7"/>'
        '<path d="M3 12.5h18M10.5 12.5v1.5h3v-1.5"/></svg>')
SCENES = ["title", "problem", "company", "people", "tasks", "site", "lead", "clients", "week", "everyone", "how", "end"]
TWO = "{ lira: [330, 730, 210, 1], patrik: [330, 350, 250, 1] }"
POS = {"problem": TWO, "tasks": TWO, "week": TWO}

CO = "Электро Плюс"
NAV = [("g", "Главное"), ("🏠", "Главная", ""), ("g", "Для себя"), ("💬", "Чат", ""), ("📅", "Календарь", ""),
       ("g", "Работа"), ("📋", "Поручения", "team"), ("👥", "Клиенты", "clients"), ("🌐", "Сайты", "sites"), ("💭", "Чат для сайта", "sitechat"),
       ("g", "Настройка"), ("🧠", "Мозг", "brain")]


def nav():
    return "".join(f'<div class="g">{x[1]}</div>' if x[0] == "g" else f'<span data-n="{x[2]}"><i>{x[0]}</i>{x[1]}</span>' for x in NAV)


PEOPLE = [("Сергей", "электрик", "#5aa9e6"), ("Анна", "менеджер", "#e59a1f"), ("Олег", "сметчик", "#2fb383")]
COLS = [("Ждут проверки", [("Сергей", "Проводка у Ивановых", "📷 фото", "")]),
        ("В работе", [("Анна", "Счёт для «Ромашки»", "до завтра", ""), ("Сергей", "Розетки в офисе", "сегодня", "")]),
        ("Просрочено", [("Олег", "Смета для школы", "вчера", "late")])]
DEALS = [("Заявка", "1 200", [("Петрова", "замена проводки")]), ("Предложение", "3 400", [("Школа №5", "освещение")]),
         ("Счёт", "1 450", [("«Ромашка»", "до 15 ноября", "late")]), ("Оплачено", "5 900", [("Ивановы", "проводка")])]
WEEK = ["Поручено 24, сделано 21.", "Кто сделал: Сергей — 9, Анна — 7, Олег — 5.", "Заявок клиентов 12, связались по 12.",
        "Просрочено 1: Олег — «Смета для школы»."]
STEPS = ["Компания", "Знания", "Каналы", "Люди", "Заявки"]
DAY = [("⏰", "Напомню о встрече", "в 15:00 — «Ромашка»"), ("✉️", "Разберу почту", "3 важных из 40"),
       ("📄", "Найду в документах", "договор со школой, п. 4"), ("✅", "Дела на день", "5 дел, 2 звонка")]

CSS = KIT_CSS + KIT2_CSS + """
#plane svg { stroke: var(--accent); }
.st { left: 640px; top: 112px; width: 1180px; height: 728px; grid-template-columns: 230px 1fr; }
.st nav { padding: 24px 12px; gap: 2px; } .st nav span { font-size: 17px; } .st nav span i { font-style: normal; margin-right: 8px; }
.st .pg { position: relative; padding: 26px 30px; } .st .pg > small { font-size: 17px; }
.cd { padding: 18px 22px; border-radius: 22px; box-shadow: var(--raise-s); }
.cd h4 { font: 700 19px Unbounded; margin-bottom: 10px; } .cd h4 small { margin-left: 8px; font: 700 14px Manrope; color: var(--mut); }
.btn { position: relative; display: inline-block; padding: 12px 22px; border-radius: 15px; font-size: 17px; font-weight: 800; box-shadow: var(--raise-s); white-space: nowrap; }
.btn.pri { color: #fff; background: var(--brand); box-shadow: none; }
.btn.ok { color: #fff; background: linear-gradient(135deg, #46d39a, #2fb383); box-shadow: none; }
.btn::after { content: ""; position: absolute; inset: -7px; border-radius: 21px; border: 3px solid var(--accent); opacity: var(--ta, 0); transform: scale(var(--ts, 1)); }
.fld { margin-top: 10px; padding: 12px 16px; border-radius: 14px; box-shadow: var(--press); font-size: 18px; font-weight: 700; min-height: 48px; }
.fld.ph { color: var(--mut); }
.lbl { margin-top: 14px; font-size: 14px; font-weight: 800; letter-spacing: .06em; text-transform: uppercase; color: var(--mut); }
.ava { flex: none; width: 40px; height: 40px; border-radius: 50%; display: grid; place-items: center; color: #fff; font-weight: 800; font-size: 18px; }
.pp { display: flex; align-items: center; gap: 14px; padding: 12px 6px; border-bottom: 1px solid rgba(36,50,74,.08); font-size: 18px; font-weight: 700; }
.pp:last-child { border-bottom: 0; } .pp small { display: block; font-size: 14px; color: var(--mut); } .pp em { margin-left: auto; font-style: normal; font-size: 15px; font-weight: 800; color: var(--mut); }
.pp em.ok { color: #1e7d5b; }
/* компания */
#coBal { display: flex; align-items: baseline; gap: 14px; margin-top: 6px; } #coBal b { font: 600 46px Unbounded; color: var(--accent); }
#coBal span { font-size: 17px; font-weight: 700; color: var(--mut); }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; margin-top: 18px; }
#stu.narrow { width: 760px; } #stu.narrow .board { gap: 10px; } #stu.narrow .tk b { font-size: 15px; } #stu.narrow .tk small { font-size: 12.5px; }
/* доска поручений */
.board { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin-top: 16px; }
.board > div > h6 { font-size: 14px; font-weight: 800; letter-spacing: .06em; text-transform: uppercase; color: var(--mut); margin: 0 4px 8px; }
.tk { padding: 14px 16px; border-radius: 18px; box-shadow: var(--raise-s); margin-bottom: 12px; }
.tk b { display: block; font-size: 17px; } .tk small { display: flex; justify-content: space-between; margin-top: 6px; font-size: 14px; font-weight: 800; color: var(--mut); }
.tk.late { box-shadow: none; background: rgba(176,74,92,.12); } .tk.late small i { color: #b04a5c; font-style: normal; }
.tk.new { box-shadow: none; background: rgba(69,96,234,.1); }
/* телефон: «Работа» */
.ph2 .scr { padding: 34px 18px; }
.ph2 .scr > small { display: block; font-size: 13px; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; color: var(--mut); }
.job { margin-top: 12px; padding: 16px; border-radius: 22px; background: #fff; }
.job b { display: block; font-size: 19px; line-height: 1.3; } .job small { display: block; margin-top: 6px; font-size: 14px; font-weight: 800; color: var(--mut); }
.job .acts { display: flex; gap: 8px; margin-top: 14px; } .job .btn { padding: 10px 14px; font-size: 15px; }
.job .photo { margin-top: 12px; height: 120px; border-radius: 16px; background: linear-gradient(160deg, #e9e1d6, #cbbfae); position: relative; overflow: hidden; }
.job .photo::after { content: ""; position: absolute; left: 50%; top: 50%; width: 76px; height: 76px; margin: -38px 0 0 -38px; border-radius: 18px;
  background: radial-gradient(circle at 36% 50%, #3a4256 0 5px, transparent 6px), radial-gradient(circle at 64% 50%, #3a4256 0 5px, transparent 6px), radial-gradient(circle, #fff 0 26px, #f1f3f7 27px);
  box-shadow: 0 8px 18px -8px rgba(36,50,74,.5); }
.job .st3 { display: inline-block; margin-top: 10px; padding: 5px 11px; border-radius: 99px; font-size: 13px; font-weight: 800; color: #1e7d5b; background: rgba(47,179,131,.16); }
.msg { margin-top: 10px; padding: 12px 14px; border-radius: 18px; background: #fff; font-size: 15px; font-weight: 600; line-height: 1.4; }
.msg u { text-decoration: none; color: var(--accent); font-weight: 800; }
/* сайт с чатом */
#w1 { left: 640px; top: 120px; width: 830px; }
.site { --sb: #F2F6FB; --sf: #1D2B44; --sm: rgba(29,43,68,.62); --sa: #F2A516; position: relative; height: 560px; overflow: hidden; border-radius: 16px; background: var(--sb); color: var(--sf); }
.site .nv { display: flex; align-items: center; gap: 24px; padding: 18px 28px; font-size: 16px; font-weight: 700; }
.site .lg { display: flex; align-items: center; gap: 9px; font: 700 20px Unbounded; margin-right: 8px; }
.site .lg i { width: 32px; height: 32px; border-radius: 10px; display: grid; place-items: center; font-style: normal; font-size: 17px; background: var(--sa); }
.site .nv span { color: var(--sm); }
.site .hero { padding: 40px 28px 0; } .site .hero h4 { font: 700 40px/1.12 Unbounded; letter-spacing: -.02em; max-width: 520px; }
.site .hero p { margin-top: 14px; font-size: 18px; font-weight: 600; color: var(--sm); max-width: 470px; line-height: 1.5; }
.site .hero .bt { display: inline-block; margin-top: 22px; padding: 13px 22px; border-radius: 14px; background: var(--sa); color: #1D2B44; font-weight: 800; }
.chatw { position: absolute; right: 20px; bottom: 20px; width: 360px; padding: 16px; border-radius: 22px; background: #fff; box-shadow: 0 20px 44px -18px rgba(29,43,68,.45); }
.chatw > small { display: flex; align-items: center; gap: 8px; font-size: 14px; font-weight: 800; } .chatw > small img { width: 28px; height: 28px; border-radius: 50%; }
.cb { margin-top: 10px; padding: 10px 13px; border-radius: 16px; font-size: 15px; font-weight: 600; line-height: 1.4; background: #eef2f8; max-width: 88%; }
.cb.me { margin-left: auto; color: #fff; background: #3550E0; }
#kn { left: 900px; top: 770px; width: 620px; } #kn > i { background: rgba(69,96,234,.14); }
.tgch .scr { background: #dfe9f2; padding: 30px 14px; }
.tgch .hd { display: flex; align-items: center; gap: 10px; padding: 0 6px 12px; font-size: 16px; font-weight: 800; }
.tgch .hd i { width: 38px; height: 38px; border-radius: 50%; display: grid; place-items: center; font-style: normal; background: var(--sa, #F2A516); }
.tgch .hd small { display: block; font-size: 12px; color: var(--mut); }
.tb { margin-top: 10px; padding: 10px 13px; border-radius: 16px; font-size: 15px; font-weight: 600; line-height: 1.4; background: #fff; max-width: 88%; }
.tb.me { margin-left: auto; background: #e1f7cf; }
#L-tg .phone { left: 1500px; top: 160px; width: 340px; height: 640px; }
/* заявка */
#lt { left: 640px; top: 130px; width: 560px; } #lt > i { background: rgba(240,180,40,.2); }
#ccard { left: 640px; top: 290px; width: 560px; }
#ctask { left: 1250px; top: 290px; width: 570px; }
.kvl { display: flex; justify-content: space-between; padding: 9px 0; font-size: 17px; font-weight: 700; color: var(--mut); border-bottom: 1px solid rgba(36,50,74,.08); }
.kvl:last-child { border-bottom: 0; } .kvl b { color: var(--ink); }
.quote { margin-top: 12px; padding: 12px 14px; border-radius: 16px; background: rgba(69,96,234,.08); font-size: 16px; font-weight: 600; line-height: 1.45; }
.quote small { display: block; font-size: 13px; font-weight: 800; color: var(--accent); margin-bottom: 3px; }
/* сделки */
.deals { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-top: 16px; }
.deals > div > h6 { display: flex; justify-content: space-between; font-size: 14px; font-weight: 800; letter-spacing: .04em; text-transform: uppercase; color: var(--mut); margin: 0 4px 8px; }
.deals > div > h6 b { color: var(--ink); letter-spacing: 0; }
.owe { display: flex; align-items: center; gap: 18px; margin-top: 6px; } .owe b { font: 600 40px Unbounded; color: #b04a5c; } .owe span { font-size: 17px; font-weight: 700; color: var(--mut); }
.owe em { margin-left: auto; font-style: normal; font-size: 16px; font-weight: 800; color: #1e7d5b; padding: 9px 14px; border-radius: 12px; background: rgba(47,179,131,.15); }
/* итог недели */
#wk { left: 640px; top: 150px; width: 760px; } #wk h3 { font-size: 30px; }
#wk .ln { display: flex; gap: 14px; align-items: flex-start; padding: 12px 0; border-bottom: 1px solid rgba(36,50,74,.08); font-size: 22px; font-weight: 700; line-height: 1.4; }
#wk .ln:last-child { border-bottom: 0; } #wk .ln i { font-style: normal; flex: none; }
#wk .ln.late { color: #b04a5c; }
#L-boss .phone { left: 1460px; }
.mini { margin-top: 10px; padding: 11px 13px; border-radius: 16px; background: #fff; font-size: 15px; font-weight: 700; }
.mini small { display: block; font-size: 12.5px; font-weight: 800; color: var(--mut); margin-bottom: 3px; } .mini.late { background: rgba(176,74,92,.12); }
.mini .acts { display: flex; gap: 6px; margin-top: 8px; } .mini .btn { padding: 7px 10px; font-size: 13px; }
/* каждому — помощник */
.dayg { position: absolute; left: 640px; top: 170px; width: 1180px; display: grid; grid-template-columns: repeat(2, 1fr); gap: 22px; }
.dayg .toast { position: relative; } .dayg .toast > i { background: rgba(69,96,234,.12); }
.dayg .toast b { font-size: 24px; } .dayg .toast small { font-size: 17px; }
.who { position: absolute; left: 640px; top: 600px; width: 1180px; display: flex; gap: 22px; }
.who span { flex: 1; display: flex; align-items: center; gap: 14px; padding: 20px 24px; border-radius: 24px; box-shadow: var(--raise-s); font-size: 21px; font-weight: 800; }
.who span i { font-style: normal; font-size: 30px; }
/* как начать */
#how { top: 150px; width: 980px; }
.chk { display: flex; gap: 12px; margin-top: 16px; } .chk span { flex: 1; display: flex; align-items: center; gap: 10px; padding: 14px 14px; border-radius: 18px; box-shadow: var(--raise-s); font-size: 18px; font-weight: 800; }
.chk span i { flex: none; width: 26px; height: 26px; border-radius: 8px; box-shadow: var(--press); display: grid; place-items: center; font-style: normal; font-size: 15px; color: #fff; }
.chk span.on i { background: linear-gradient(135deg, #46d39a, #2fb383); box-shadow: none; }
"""

PROBLEM = mess(["Кто взял заказ Ивановых?", "Заявка с сайта — 2 дня без ответа", "Сергей, ты где?", "Счёт «Ромашке» оплатили?",
                "Telegram: 14 непрочитанных", "Где фото работ?", "Смета — у кого?", "Клиент ждёт звонка"], "Всё — в голове руководителя")

HTML = PROBLEM + """
  <div class="layer" id="L-left">
    <div class="st" id="stu"><nav>""" + nav() + """</nav>
      <div class="pg">
        <div class="pane" id="pCo"><h3>Мозг</h3><small>Компания: код от руководителя или своя</small>
          <div class="cd" style="margin-top:18px" id="coNew"><div class="lbl" style="margin-top:0">Название компании</div><div class="fld" id="coName"></div>
            <div style="margin-top:16px"><span class="btn pri" id="coGo">Создать компанию</span></div></div>
          <div id="coDone"><div class="cd" style="margin-top:18px"><h4>Компания «""" + CO + """»<small>Вы — руководитель</small></h4>
              <div id="coBal"><b>120 т.</b><span>баланс компании — один на всех</span></div></div>
            <div class="grid2"><div class="cd"><h4>Места и лимиты</h4>""" + "".join(
                f'<div class="pp"><span class="ava" style="background:{c}">{n[0]}</span><div>{n}<small>{r}</small></div><em>лимит 10 т./мес.</em></div>' for n, r, c in PEOPLE) + """</div>
              <div class="cd"><h4>Запуск компании</h4><div id="coSteps">""" + "".join(
                f'<div class="pp"><span class="ava" style="background:{"#2fb383" if i == 0 else "#b8c5d6"}">{"✓" if i == 0 else i + 1}</span><div>{t}</div></div>' for i, t in enumerate(STEPS[:3])) + """</div></div></div></div></div>
        <div class="pane" id="pIn"><h3>Поручения</h3><small>Пригласить сотрудника</small>
          <div class="cd" style="margin-top:18px;max-width:560px"><div class="lbl" style="margin-top:0">Имя</div><div class="fld" id="inName"></div>
            <div class="lbl">Чем занят</div><div class="fld" id="inRole"></div>
            <div style="margin-top:16px"><span class="btn pri" id="inGo">Получить ссылку</span></div>
            <div class="fld" id="inLink" style="margin-top:14px;color:var(--accent)">dewiar.pro/j/Kx7m-Q2</div></div></div>
        <div class="pane" id="pBo"><h3>Поручения</h3><small>Компания «""" + CO + """» · доска</small>
          <div class="board">""" + "".join(
              f'<div><h6>{h}</h6>' + "".join(f'<div class="tk {cl}" data-c="{ci}"><b>{t}</b><small><span>{w}</span><i>{d}</i></small></div>' for w, t, d, cl in items) + '</div>'
              for ci, (h, items) in enumerate(COLS)) + """</div></div>
        <div class="pane" id="pDe"><h3>Клиенты</h3><small>Сделки и кто должен</small>
          <div class="cd" style="margin-top:16px"><div class="owe"><b>1 450</b><span>вам должны · срок оплаты прошёл</span><em>оплачено за месяц: 5 900</em></div></div>
          <div class="deals">""" + "".join(
              f'<div><h6>{h}<b>{s}</b></h6>' + "".join(f'<div class="tk {(x[2] if len(x) > 2 else "")}"><b>{x[0]}</b><small><span>{x[1]}</span></small></div>' for x in items) + '</div>'
              for h, s, items in DEALS) + """</div></div>
      </div></div>
    <div class="win" id="w1"><div class="bar"><i></i><i></i><i></i><span><b>elektroplus.dewiar.pro</b></span></div>
      <div class="site"><div class="nv"><div class="lg"><i>⚡</i>""" + CO + """</div><span>Услуги</span><span>Цены</span><span>Контакты</span></div>
        <div class="hero"><h4>Электрик на дом за 2 часа</h4><p>Проводка, розетки, щиты и освещение. Гарантия на работы — 2 года.</p><span class="bt">Вызвать мастера</span></div>
        <div class="chatw" id="chw"><small><img src="../../../../data/avatars/lira.webp" alt="">Консультант · онлайн</small>
          <div class="cb me" id="cq">Сколько стоит заменить розетку?</div>
          <div class="cb" id="ca">От 25 руб. за розетку, выезд сегодня с 14 до 18. Оставите телефон — мастер перезвонит.</div>
          <div class="cb me" id="cp">+375 29 •••-••-17, Анна</div></div></div></div>
    <div class="toast" id="kn"><i>🌐</i><div><small>ЗНАНИЯ — С ВАШЕГО САЙТА</small><b>Цены, услуги, адрес и часы работы</b></div></div>
    <div class="toast" id="lt"><i>🔔</i><div><small>НОВАЯ ЗАЯВКА · САЙТ</small><b>Анна оставила телефон</b></div></div>
    <div class="card" id="ccard"><h3>Анна Петрова</h3><small>Клиенты · новая карточка</small>
      <div class="kvl">Телефон<b>+375 29 •••-••-17</b></div><div class="kvl">Откуда<b>чат на сайте</b></div>
      <div class="quote"><small>О чём договорились</small>Заменить розетки на кухне, сегодня после 14:00</div>
      <div class="kvl">Следующий шаг<b>позвонить · Сергей</b></div></div>
    <div class="card" id="ctask"><h3>Поручение</h3><small>Заявка клиента — сразу сотруднику</small>
      <div class="tk new" style="margin-top:14px"><b>Связаться с клиентом: Анна Петрова</b><small><span>Сергей</span><i>за 2 часа · до 16:40</i></small></div>
      <div class="kvl">Сергею<b>пришло в «Работу»</b></div></div>
    <div class="card" id="wk"><h3>Итог недели</h3><small>Пятница, 18:00 · компания «""" + CO + """»</small>""" + "".join(
        f'<div class="ln{" late" if i == 3 else ""}"><i>{["📋", "👷", "📨", "⚠️"][i]}</i><span>{t}</span></div>' for i, t in enumerate(WEEK)) + """</div>
    <div class="dayg" id="dayg">""" + "".join(f'<div class="toast"><i>{i}</i><div><small>{s}</small><b>{t}</b></div></div>' for i, t, s in DAY) + """</div>
    <div class="who" id="whoR"><span><i>💻</i>Руководителю</span><span><i>📱</i>Каждому сотруднику</span><span><i>🎙</i>Голосом</span></div>
    <div class="card" id="how"><h3>Лира для компании</h3><small>Студия → «Мозг» → «Создать компанию»</small>
      <div class="lbl" style="margin-top:22px">Запуск компании — пять шагов</div>
      <div class="chk" id="chk">""" + "".join(f'<span><i>✓</i>{t}</span>' for t in STEPS) + """</div>
      <div class="row"><i>📋</i>Поручения: «Беру» → «Сделано» с фото<em>доска и календарь</em></div>
      <div class="row"><i>💭</i>Консультант на сайте и в Telegram<em>днём и ночью</em></div>
      <div class="row"><i>👥</i>Заявка → карточка клиента и поручение<em class="ok">сама</em></div></div>
  </div>
  <div class="layer" id="L-emp"><div class="phone ph2"><div class="scr" id="emp">
    <small>Работа · """ + CO + """</small>
    <div class="msg" id="eInv">Вас пригласили в компанию «""" + CO + """»: <u>dewiar.pro/j/Kx7m-Q2</u></div>
    <div class="job" id="eJob"><b>Заменить проводку у Ивановых</b><small>до пятницы · от руководителя</small>
      <div class="acts" id="eActs"><span class="btn pri" id="eTake">Беру</span><span class="btn" id="eDone">Сделано</span><span class="btn">Перенести</span></div>
      <div class="photo" id="ePh"></div><span class="st3" id="eSt">Сделано · с фото</span></div>
    <div class="msg" id="eRem">⏰ Через час срок: «Заменить проводку у Ивановых»</div></div></div></div>
  <div class="layer" id="L-tg"><div class="phone tgch"><div class="scr">
    <div class="hd"><i>⚡</i><div>""" + CO + """<small>бот компании</small></div></div>
    <div class="tb me" id="tq">Вы работаете в субботу?</div>
    <div class="tb" id="ta">Да, в субботу с 10 до 16. Оставьте телефон — мастер перезвонит.</div></div></div></div>
  <div class="layer" id="L-boss"><div class="phone"><div class="scr">
    <h5>Сотрудники</h5><small style="font-size:13px;font-weight:800;color:var(--mut)">ЖДУТ ВАШЕЙ ПРОВЕРКИ</small>
    <div class="mini"><small>Сергей · 📷 фото</small>Проводка у Ивановых<div class="acts"><span class="btn ok" id="bOk">Принять</span><span class="btn">Вернуть</span></div></div>
    <small style="display:block;margin-top:14px;font-size:13px;font-weight:800;color:var(--mut)">ПРОСРОЧЕНО</small>
    <div class="mini late"><small>Олег · вчера</small>Смета для школы<div class="acts"><span class="btn">Напомнить</span><span class="btn">Написать</span></div></div>
    <div style="margin-top:14px"><span class="btn pri" id="bAs">Поручить</span></div></div></div></div>
  """ + CURSOR + """
"""

JS = CURSOR_JS + MESS_JS + """
  const tap = (el, t0) => { const k = (T - t0) / 0.6; const on = k > 0 && k < 1;
    el.style.setProperty("--ta", on ? (1 - k).toFixed(3) : 0); el.style.setProperty("--ts", on ? (1 + k * 0.2).toFixed(3) : 1);
    el.style.transform = k > 0 && k < 0.22 ? "scale(.95)" : ""; };
  const navOn = (n) => [...$("#stu nav").querySelectorAll("span")].forEach(c => c.classList.toggle("on", c.dataset.n === n));
  layer("L-left", T, s("problem").start + 0.2, s("end").start);
  const S = (id) => s(id).start, E = (id) => s(ORDER[ORDER.indexOf(id) + 1]).start;
  // студия: компания → приглашение → доска → (сайт отдельно) → сделки
  const stuK = Math.max(
    Math.min(out((T - S("company") - 0.2) / 0.5), 1 - out((T - E("people") + 0.4) / 0.4)),
    Math.min(out((T - at("s5c") + 0.3) / 0.5), 1 - out((T - E("tasks") + 0.4) / 0.4)),
    Math.min(out((T - S("clients") - 0.2) / 0.5), 1 - out((T - E("clients") + 0.4) / 0.4)));
  vis($("#stu"), clamp(stuK), 24, .97);
  const pane = T < S("people") ? "pCo" : T < S("tasks") ? "pIn" : T < S("clients") ? "pBo" : "pDe";
  ["pCo", "pIn", "pBo", "pDe"].forEach(p => $("#" + p).style.display = p === pane ? "" : "none");
  navOn({ pCo: "brain", pIn: "team", pBo: "team", pDe: "clients" }[pane]);
  $("#stu").classList.toggle("narrow", pane === "pIn" || pane === "pBo");     // рядом телефон сотрудника
  // компания: название → «Создать компанию» → баланс, места, «Запуск компании»
  const c0 = S("company"), cd = LN.s3a.dur, tCo = c0 + 0.5 + cd * 0.28;
  $("#coName").textContent = type(\"""" + CO + """\", (T - c0 - 0.6) / (cd * 0.18));
  vis($("#coNew"), T < tCo + 0.5 ? 1 : 0, 0); $("#coNew").style.display = T < tCo + 0.5 ? "" : "none";
  vis($("#coDone"), out((T - tCo - 0.5) / 0.4), 12); $("#coDone").style.display = T < tCo + 0.5 ? "none" : "";
  tap($("#coGo"), tCo);
  // приглашение: имя, чем занят → ссылка → у сотрудника на телефоне
  const i0 = S("people"), id_ = LN.s4a.dur, tIn = i0 + 0.5 + id_ * 0.3;
  $("#inName").textContent = type("Сергей", (T - i0 - 0.4) / (id_ * 0.1));
  $("#inRole").textContent = type("электрик", (T - i0 - 0.4 - id_ * 0.12) / (id_ * 0.12));
  tap($("#inGo"), tIn); vis($("#inLink"), out((T - tIn - 0.4) / 0.4), 8);
  layer("L-emp", T, i0 + id_ * 0.55, E("tasks"));
  vis($("#eInv"), out((T - i0 - id_ * 0.6) / 0.4), 10);
  // поручение: Патрик голосом → у Сергея «Беру» → «Сделано» с фото → напоминание; доска
  const t0 = S("tasks"), tTake = at("s5b") + LN.s5b.dur * 0.15, tDone = at("s5b") + LN.s5b.dur * 0.35;
  vis($("#eJob"), out((T - at("s5a") - LN.s5a.dur * 0.6) / 0.4), 14);
  tap($("#eTake"), tTake); tap($("#eDone"), tDone);
  vis($("#eActs"), T < tDone + 0.5 ? 1 : 0, 0); $("#eActs").style.display = T < tDone + 0.5 ? "" : "none";
  $("#ePh").style.display = T > tDone + 0.5 ? "" : "none"; vis($("#ePh"), out((T - tDone - 0.5) / 0.4), 10);
  $("#eSt").style.display = T > tDone + 0.8 ? "" : "none";
  vis($("#eRem"), out((T - at("s5b") - LN.s5b.dur * 0.75) / 0.4), 10);
  [...$("#pBo").querySelectorAll(".tk")].forEach(c => vis(c, out((T - at("s5c") - 0.3 - (+c.dataset.c) * 0.5) / 0.4), 10));
  // сайт: консультант отвечает; знания — с сайта; бот компании в Telegram
  const w0 = S("site");
  scene($("#w1"), T, w0 + 0.2, E("site"), 24);
  vis($("#chw"), out((T - w0 - 0.8) / 0.4), 20); vis($("#cq"), out((T - w0 - 1.2) / 0.3), 8);
  vis($("#ca"), out((T - w0 - 2.2) / 0.4), 8); vis($("#cp"), out((T - at("s6a") - LN.s6a.dur * 0.85) / 0.4), 8);
  scene($("#kn"), T, at("s6a") + LN.s6a.dur * 0.45, at("s6b"), 20);
  layer("L-tg", T, at("s6b") + 0.3, E("site"));
  vis($("#tq"), out((T - at("s6b") - 0.8) / 0.3), 8); vis($("#ta"), out((T - at("s6b") - 1.8) / 0.4), 8);
  // заявка: клиент оставил телефон → карточка → поручение Сергею
  const l0 = S("lead"), ld = LN.s7a.dur;
  scene($("#lt"), T, l0 + 0.2, E("lead"), 20);
  scene($("#ccard"), T, l0 + ld * 0.25, E("lead"), 24);
  scene($("#ctask"), T, l0 + ld * 0.55, E("lead"), 24);
  // сделки: колонки и долг
  [...$("#pDe").querySelectorAll(".deals > div")].forEach((c, i) => vis(c, out((T - S("clients") - 0.8 - i * 0.35) / 0.4), 10));
  // итог недели и доска на телефоне руководителя
  const k0 = S("week");
  scene($("#wk"), T, k0 + 0.2, E("week"), 24);
  [...$("#wk").querySelectorAll(".ln")].forEach((c, i) => vis(c, out((T - k0 - 0.7 - i * 0.45) / 0.4), 10));
  layer("L-boss", T, at("s9c") - 0.2, E("week"));
  tap($("#bOk"), at("s9c") + LN.s9c.dur * 0.55);
  // каждому — помощник
  const d0 = S("everyone");
  vis($("#dayg"), Math.min(out((T - d0 - 0.2) / 0.5), 1 - out((T - E("everyone") + 0.4) / 0.4)), 20, .97);
  [...$("#dayg").children].forEach((c, i) => vis(c, out((T - d0 - 0.5 - i * 0.4) / 0.4), 12));
  vis($("#whoR"), Math.min(out((T - d0 - LN.s10a.dur * 0.55) / 0.5), 1 - out((T - E("everyone") + 0.4) / 0.4)), 16);
  // как начать
  const h0 = S("how");
  scene($("#how"), T, h0 + 0.2, S("end"));
  [...$("#chk").children].forEach((c, i) => c.classList.toggle("on", T > h0 + LN.s11a.dur * 0.45 + i * 0.35));
  [...$("#how").querySelectorAll(".row")].forEach((c, i) => vis(c, out((T - h0 - 0.8 - i * 0.3) / 0.4), 12));
  // курсор: «Создать компанию», «Получить ссылку»
  cursor(walk([[c0, [1500, 760]], [tCo, ctr($("#coGo"))], [i0 + 0.3, ctr($("#coGo"))], [tIn, ctr($("#inGo"))]]),
    T < S("people") ? Math.min(out((T - c0 - 0.2) / 0.4), 1 - out((T - tCo - 0.9) / 0.4)) : Math.min(out((T - i0 - 0.2) / 0.4), 1 - out((T - tIn - 0.9) / 0.4)));
"""
