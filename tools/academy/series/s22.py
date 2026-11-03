import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kit import KIT_CSS, KIT2_CSS
TITLE = "Урок 22 · Страница плагина"
IDEA = "Главная вещь урока — у плагина своя страница: бросили сорок резюме — кандидаты разобраны и сравнены; кнопки, настройки и «спросить Лиру» — там же."
H1 = "Страница плагина"
TAG = "Свой раздел у каждого плагина — кнопки, настройки, результаты"
NEXT = "Скоро — новые уроки"
ICON = '<svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="16" rx="3"/><path d="M9 4v16"/><path d="M12.5 9h5M12.5 12.5h5M12.5 16h3"/></svg>'
SCENES = ["title", "problem", "open", "act", "ask", "settings", "how", "end"]
POS = {"problem": "{ lira: [330, 730, 210, 1], patrik: [330, 350, 250, 1] }"}
CSS = KIT_CSS + KIT2_CSS + """
#drop { position: absolute; left: 640px; top: 140px; width: 1180px; height: 170px; border-radius: 30px; box-shadow: var(--press); }
#drop .dz { position: absolute; inset: 14px; border-radius: 22px; border: 3px dashed rgba(69,96,234,.35); display: flex; align-items: center; gap: 22px; padding: 0 30px; }
#drop .dz > i { font-size: 54px; font-style: normal; } #drop .dz b { display: block; font: 700 26px Unbounded; } #drop .dz small { font-size: 19px; font-weight: 700; color: var(--mut); }
#drop .cnt { margin-left: auto; padding: 14px 20px; border-radius: 18px; background: var(--bg); box-shadow: var(--raise-s); font-size: 21px; font-weight: 800; white-space: nowrap; }
#drop .cnt.ok { color: #1e7d5b; }
.fl { position: absolute; top: 60px; padding: 12px 16px; border-radius: 14px; background: #fff; box-shadow: 0 10px 24px -8px rgba(36,50,74,.35); font-size: 18px; font-weight: 800; white-space: nowrap; }
#cands { position: absolute; left: 640px; top: 350px; width: 1180px; display: grid; grid-template-columns: repeat(3, 1fr); gap: 24px; }
.cd { padding: 24px 24px 22px; border-radius: 28px; background: var(--bg); box-shadow: var(--raise); }
.cd.top { box-shadow: 0 0 0 4px #f2a65a, var(--raise); }
.cd .hd { display: flex; align-items: center; gap: 14px; } .cd .av { flex: none; width: 58px; height: 58px; border-radius: 50%; display: grid; place-items: center; color: #fff; font: 700 21px Unbounded; }
.cd b { display: block; font-size: 22px; } .cd .hd small { font-size: 17px; font-weight: 700; color: var(--mut); }
.cd .meta { margin-top: 14px; font-size: 18px; font-weight: 700; color: var(--mut); }
.cd .sc { display: flex; align-items: center; gap: 12px; margin-top: 16px; } .cd .sc s { flex: 1; height: 12px; border-radius: 99px; background: rgba(69,96,234,.12); position: relative; overflow: hidden; text-decoration: none; }
.cd .sc s i { position: absolute; inset: 0 auto 0 0; border-radius: 99px; background: var(--brand); } .cd.top .sc s i { background: linear-gradient(90deg, #f7b96d, #e8893a); }
.cd .sc b { font: 700 26px Unbounded; } .cd .sc em { font-style: normal; font-size: 15px; font-weight: 800; color: var(--mut); }
.cd .win1 { margin-top: 14px; display: inline-block; padding: 8px 14px; border-radius: 12px; font-size: 16px; font-weight: 800; color: #9a5a17; background: rgba(242,166,90,.2); }
#stu { left: 620px; top: 130px; width: 1220px; height: 720px; }
#stu nav span i { font-style: normal; margin-right: 8px; } #stu nav span.new { box-shadow: 0 0 0 3px rgba(242,166,90,.7); }
#stu .pg { position: relative; }
.ph { display: flex; align-items: center; gap: 18px; } .ph > i { flex: none; width: 76px; height: 76px; border-radius: 24px; display: grid; place-items: center; font-size: 42px; font-style: normal; background: rgba(242,166,90,.22); }
.ph small { display: block; font-size: 17px; font-weight: 700; color: var(--mut); margin-top: 4px; } .ph .st-on { margin-left: auto; padding: 9px 14px; border-radius: 12px; font-size: 16px; font-weight: 800; color: #1e7d5b; background: rgba(47,179,131,.15); white-space: nowrap; }
.tabs { display: flex; gap: 10px; margin-top: 22px; } .tabs span { padding: 11px 18px; border-radius: 14px; box-shadow: var(--raise-s); font-size: 18px; font-weight: 800; }
.tabs span.on { color: #fff; background: var(--brand); box-shadow: none; }
.pane { position: absolute; left: 32px; right: 32px; top: 196px; }
.fun { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
.fun > div { padding: 16px; border-radius: 20px; box-shadow: var(--press); min-height: 380px; } .fun h6 { font-size: 16px; font-weight: 800; color: var(--mut); text-transform: uppercase; letter-spacing: .05em; margin-bottom: 10px; }
.fun h6 b { color: var(--accent); margin-left: 6px; } .fun p { padding: 11px 13px; border-radius: 14px; background: var(--bg); box-shadow: var(--raise-s); font-size: 16px; font-weight: 700; margin-top: 10px; }
.acts { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }
.ac { padding: 20px 22px; border-radius: 22px; box-shadow: var(--raise-s); } .ac b { display: block; font-size: 21px; } .ac small { display: block; font-size: 15px; font-weight: 700; color: var(--mut); margin-top: 4px; }
.ac .f { margin-top: 12px; padding: 12px 16px; border-radius: 14px; box-shadow: var(--press); font-size: 18px; font-weight: 700; min-height: 48px; }
.ac .f::after { content: "|"; display: inline-block; width: 0; color: var(--accent); opacity: var(--cur, 0); }
.ac .go { margin-top: 14px; display: inline-block; padding: 12px 22px; border-radius: 14px; color: #fff; background: var(--brand); font-size: 17px; font-weight: 800; }
.ac .go.ok { background: linear-gradient(135deg, #46d39a, #2fb383); }
.tbl { margin-top: 18px; border-radius: 20px; box-shadow: var(--raise-s); overflow: hidden; font-size: 18px; font-weight: 700; }
.tbl div { display: grid; grid-template-columns: 1.4fr 1fr .6fr .9fr; padding: 12px 20px; } .tbl div:first-child { font-size: 15px; font-weight: 800; color: var(--mut); text-transform: uppercase; letter-spacing: .04em; background: rgba(255,255,255,.35); }
.tbl div + div { border-top: 1px solid rgba(36,50,74,.08); }
#q1 { left: 640px; top: 140px; }
#cmp { left: 640px; top: 260px; width: 1000px; padding: 30px 36px; }
#cmp .cr { display: grid; grid-template-columns: 220px 1fr 70px 1fr 70px; align-items: center; gap: 14px; margin-top: 14px; font-size: 20px; font-weight: 700; }
#cmp .hd2 { display: grid; grid-template-columns: 220px 1fr 1fr; gap: 14px; font-size: 21px; font-weight: 800; } #cmp .hd2 span:nth-child(2) { color: #c4741f; } #cmp .hd2 span:nth-child(3) { color: var(--accent); }
#cmp s { height: 12px; border-radius: 99px; background: rgba(69,96,234,.12); position: relative; overflow: hidden; text-decoration: none; }
#cmp s i { position: absolute; inset: 0 auto 0 0; border-radius: 99px; background: var(--brand); } #cmp s.a i { background: linear-gradient(90deg, #f7b96d, #e8893a); }
#cmp .cr b { font-size: 20px; text-align: right; } #cmp .vd { margin-top: 22px; padding: 16px 20px; border-radius: 18px; box-shadow: var(--press); font-size: 21px; font-weight: 700; line-height: 1.4; }
#set { top: 160px; width: 760px; } #set label { display: block; margin-top: 18px; font-size: 17px; font-weight: 800; color: var(--mut); }
#set .in { margin-top: 8px; padding: 16px 20px; border-radius: 16px; box-shadow: var(--press); font-size: 22px; font-weight: 700; }
#set .jb .tgl { margin-left: auto; }
#set .jb { display: flex; align-items: center; gap: 16px; margin-top: 24px; padding: 18px 20px; border-radius: 18px; box-shadow: var(--raise-s); font-size: 21px; font-weight: 700; }
#ring { left: 1420px; top: 220px; width: 400px; flex-direction: column; align-items: flex-start; }
#ring .tm { font: 600 46px Unbounded; color: var(--accent); } #ring p { font-size: 21px; font-weight: 700; line-height: 1.4; }
#pages { position: absolute; left: 620px; top: 170px; width: 1200px; display: grid; grid-template-columns: repeat(3, 1fr); gap: 26px; }
.pp { padding: 24px; border-radius: 30px; background: var(--bg); box-shadow: var(--raise); }
.pp .ph > i { width: 64px; height: 64px; font-size: 34px; border-radius: 20px; } .pp .ph b { font-size: 22px; }
.pp .pv { margin-top: 18px; height: 250px; border-radius: 20px; box-shadow: var(--press); padding: 16px; display: flex; flex-direction: column; gap: 10px; overflow: hidden; }
.pp .pv p { padding: 11px 13px; border-radius: 12px; background: var(--bg); box-shadow: var(--raise-s); font-size: 16px; font-weight: 700; display: flex; justify-content: space-between; gap: 8px; }
.pp .pv p em { font-style: normal; color: var(--accent); font-weight: 800; white-space: nowrap; }
.pp .gal { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; flex: 1; } .pp .gal i { border-radius: 12px; display: grid; place-items: center; font-size: 40px; font-style: normal; }
.pp > small { display: block; margin-top: 14px; font-size: 17px; font-weight: 800; color: var(--mut); }
"""
FILES = ["📄 Ковалёва.pdf", "📝 Петров.docx", "🗜 резюме-октябрь.zip", "📄 Лис_А.pdf", "📝 Орлова.docx", "📄 Мороз_П.pdf"]
CANDS = [("ИК", "#e8893a", "Ирина Ковалёва", "главный бухгалтер", "7 лет · 1С, налоги, отчётность", 87, True),
         ("СП", "#5a7bea", "Сергей Петров", "бухгалтер", "5 лет · 1С, зарплата", 74, False),
         ("АЛ", "#3a9fb0", "Анна Лис", "бухгалтер", "3 года · первичка, банк", 68, False)]
NAV = [("g", "Главное"), ("🏠", "Главная"), ("💬", "Чат"), ("⏰", "Напоминания"), ("g", "Работа"), ("👥", "Клиенты"), ("🌐", "Сайты"),
       ("g", "Плагины"), ("🧑‍💼", "Рекрутер"), ("📄", "Тендеры"), ("🎨", "Художник")]
FUN = [("Новый", ["Орлова Е.", "Гаврик М.", "Савич Д.", "Бондарь О."], 12), ("Интересен", ["Петров С.", "Лис А.", "Жук Т."], 6),
       ("Собеседование", ["Ковалёва И.", "Мороз П."], 3), ("Оффер", ["Жданова В."], 1)]
CMP = [("навыки", 92, 78), ("опыт", 88, 70), ("формат и условия", 80, 90), ("образование", 85, 80), ("языки", 60, 75)]
HTML = """
  <div class="layer" id="L-left">
    <div id="drop"><div class="dz"><i>📥</i><div><b>Перетащите резюме сюда</b><small>PDF, Word, текст или ZIP — сколько угодно</small></div><span class="cnt" id="cnt">0 резюме</span></div>
      """ + "".join(f'<span class="fl">{f}</span>' for f in FILES) + """</div>
    <div id="cands">""" + "".join(f'''<div class="cd{" top" if t else ""}"><div class="hd"><span class="av" style="background:{c}">{a}</span><div><b>{n}</b><small>{r}</small></div></div>
      <div class="meta">{m}</div><div class="sc"><s><i data-w="{sc}"></i></s><b>{sc}</b><em>из 100</em></div>{'<span class="win1">🏆 Лучшая под «Бухгалтер»</span>' if t else ''}</div>''' for a, c, n, r, m, sc, t in CANDS) + """</div>
    <div class="st" id="stu"><nav>""" + "".join(f'<div class="g">{t}</div>' if e == "g" else f'<span class="{"on" if t == "Рекрутер" else ""}" data-n="{t}"><i>{e}</i>{t}</span>' for e, t in NAV) + """</nav>
      <div class="pg"><div class="ph"><i>🧑‍💼</i><div><h3>Рекрутер</h3><small>Разбор резюме, отбор под вакансию, честная оценка</small></div><span class="st-on">● работает</span></div>
        <div class="tabs"><span id="tb1" class="on">Резюме и подбор</span><span id="tb2">Сделать сейчас</span><span>Настройки</span><span>Файлы</span></div>
        <div class="pane" id="pn1"><div class="fun">""" + "".join(f'<div><h6>{h}<b>{k}</b></h6>' + "".join(f"<p>{x}</p>" for x in xs) + "</div>" for h, xs, k in FUN) + """</div></div>
        <div class="pane" id="pn2"><div class="acts">
          <div class="ac"><b>Новая вакансия</b><small>Под неё Лира отбирает и оценивает</small><div class="f" id="f1"></div><div class="f" id="f2"></div><span class="go" id="go1">Сохранить вакансию</span></div>
          <div class="ac"><b>Кандидаты</b><small>Кто в базе — по этапу или по словам</small><div class="f">этап: интересен</div><div class="f">бухгалтер</div><span class="go" id="go2">Показать</span></div></div>
          <div class="tbl" id="tbl"><div><span>Имя</span><span>Должность</span><span>Стаж</span><span>Этап</span></div>
            <div><span>Ирина Ковалёва</span><span>гл. бухгалтер</span><span>7 лет</span><span>собеседование</span></div>
            <div><span>Сергей Петров</span><span>бухгалтер</span><span>5 лет</span><span>интересен</span></div>
            <div><span>Анна Лис</span><span>бухгалтер</span><span>3 года</span><span>интересен</span></div></div></div>
      </div></div>
    <div class="say" id="q1">«Сравни Ковалёву и Петрова»</div>
    <div class="card" id="cmp"><div class="hd2"><span></span><span>Ирина Ковалёва · 87</span><span>Сергей Петров · 74</span></div>
      """ + "".join(f'<div class="cr"><span>{c}</span><s class="a"><i data-w="{a}"></i></s><b>{a}</b><s><i data-w="{b}"></i></s><b>{b}</b></div>' for c, a, b in CMP) + """
      <div class="vd">Ковалёва сильнее в 1С и налогах, у Петрова — удобнее график. На собеседовании уточните у неё ожидания по зарплате.</div></div>
    <div class="card" id="set"><h3>Настройки</h3><label>ПАПКА С РЕЗЮМЕ</label><div class="in">📁 ~/Документы/Резюме</div>
      <label>О КОМПАНИИ — ДЛЯ ПИСЕМ КАНДИДАТАМ</label><div class="in">ООО «Север», Минск, производство</div>
      <div class="jb">🗓 Новые резюме из папки — по будням в 10:00<span class="tgl" id="tg"><i></i></span></div></div>
    <div class="toast" id="ring"><small>ЛИРА · 10:00</small><div class="tm">+3 резюме</div><p>Новые на бухгалтера: Мороз, Савич, Бондарь. У Мороза уточните стаж в 1С.</p></div>
    <div id="pages">
      <div class="pp"><div class="ph"><i>🧑‍💼</i><b>Рекрутер</b></div><div class="pv"><p>Ирина Ковалёва<em>87</em></p><p>Сергей Петров<em>74</em></p><p>Анна Лис<em>68</em></p><p>Турнир лучших<em>→</em></p></div><small>Кандидаты, этапы, сравнение</small></div>
      <div class="pp"><div class="ph"><i style="background:rgba(74,139,232,.18)">📄</i><b>Тендеры</b></div><div class="pv"><p>Поставка бумаги<em>12 дн.</em></p><p>Ремонт кровли<em>5 дн.</em></p><p>Мебель для школы<em>9 дн.</em></p><p>Мои запросы<em>3</em></p></div><small>Лента с фильтрами и сроками</small></div>
      <div class="pp"><div class="ph"><i style="background:rgba(255,122,182,.2)">🎨</i><b>Художник</b></div><div class="pv"><div class="gal"><i style="background:linear-gradient(160deg,#FFE3D3,#F59BB0)">🎂</i><i style="background:linear-gradient(160deg,#0B1636,#3A3F73)">❄️</i><i style="background:linear-gradient(160deg,#F3E2CF,#8B5A3C)">☕</i><i style="background:linear-gradient(160deg,#BFD0FF,#4F6CF0)">🚀</i></div></div><small>Рисунки — все в одном месте</small></div>
    </div>
  </div>
"""
JS = """
  layer("L-left", T, s("problem").start + 0.2, s("end").start);
  const p0 = s("problem").start, tA = end("s2a") - 0.4;
  scene($("#drop"), T, p0 + 0.3, s("open").start, 24);
  [...$("#drop").querySelectorAll(".fl")].forEach((c, i) => { const k = ease((T - p0 - 0.9 - i * 0.32) / 0.9);
    c.style.left = (1060 - k * (700 - i * 40)) + "px"; c.style.top = (30 + (i % 3) * 38 - Math.sin(k * Math.PI) * 40) + "px"; c.style.opacity = k <= 0 ? 0 : k < 0.85 ? 1 : (1 - k) / 0.15;
    c.style.transform = `rotate(${(1 - k) * (i % 2 ? 8 : -8)}deg)`; });
  const n = Math.round(40 * clamp((T - p0 - 1.0) / 2.6));
  $("#cnt").textContent = n >= 40 ? "40 резюме · разобрано ✓" : n + " резюме"; $("#cnt").classList.toggle("ok", n >= 40);
  scene($("#cands"), T, tA, s("open").start, 24);
  [...$("#cands").children].forEach((c, i) => vis(c, out((T - tA - 0.2 - i * 0.35) / 0.45), 18, .95));
  [...$("#cands").querySelectorAll(".sc i")].forEach((c, i) => { c.style.width = (+c.dataset.w * out((T - tA - 0.7 - i * 0.35) / 0.8)) + "%"; });
  [...$("#cands").querySelectorAll(".cd")].forEach((c, i) => c.classList.toggle("top", i === 0 && T > at("s2b") + 2.6));
  vis($(".win1"), out((T - at("s2b") - 2.6) / 0.4), 10);
  // студия: меню слева — группа «Плагины», страница «Рекрутера»; потом «Сделать сейчас»
  scene($("#stu"), T, s("open").start + 0.2, s("ask").start);
  const nav = [...$("#stu nav").children];
  nav.forEach((c, i) => { if (i >= 7) vis(c, out((T - s("open").start - 1.4 - (i - 7) * 0.3) / 0.4), 10); });
  $('#stu nav [data-n="Рекрутер"]').classList.toggle("new", T > s("open").start + 1.4 && T < s("open").start + 4);
  const onAct = T > s("act").start + 0.1;
  $("#tb1").classList.toggle("on", !onAct); $("#tb2").classList.toggle("on", onAct);
  vis($("#pn1"), Math.min(out((T - s("open").start - 1.0) / 0.5), 1 - out((T - s("act").start) / 0.3)), 14);
  vis($("#pn2"), out((T - s("act").start - 0.2) / 0.4), 14);
  [...$("#pn1").querySelectorAll("p")].forEach((c, i) => vis(c, out((T - s("open").start - 1.8 - i * 0.12) / 0.4), 10));
  const k1 = (T - s("act").start - 1.0) / 0.8, k2 = (T - s("act").start - 2.0) / 1.2;
  $("#f1").textContent = type("Бухгалтер", k1); $("#f2").textContent = type("1С, налоги, опыт от трёх лет", k2);
  $("#f1").style.setProperty("--cur", k1 > 0 && k1 < 1.3 ? (Math.floor(T * 2) % 2) : 0); $("#f2").style.setProperty("--cur", k2 > 0 && k2 < 1.3 ? (Math.floor(T * 2) % 2) : 0);
  const sv = T > s("act").start + 3.6; $("#go1").classList.toggle("ok", sv); $("#go1").textContent = sv ? "Сохранено ✓" : "Сохранить вакансию";
  $("#go2").classList.toggle("ok", T > s("act").start + 4.6);
  vis($("#tbl"), out((T - s("act").start - 5.0) / 0.5), 16);
  scene($("#q1"), T, s("ask").start + 0.2, s("settings").start, 20);
  scene($("#cmp"), T, s("ask").start + 2.2, s("settings").start, 24);
  [...$("#cmp").querySelectorAll("s i")].forEach((c, i) => { c.style.width = (+c.dataset.w * out((T - s("ask").start - 2.6 - Math.floor(i / 2) * 0.2) / 0.7)) + "%"; });
  vis($("#cmp .vd"), out((T - s("ask").start - 4.0) / 0.5), 10);
  scene($("#set"), T, s("settings").start + 0.2, s("how").start);
  const on = T > s("settings").start + 3.0; $("#tg").classList.toggle("on", on);
  scene($("#ring"), T, s("settings").start + 4.0, s("how").start, 30);
  scene($("#pages"), T, s("how").start + 0.2, s("end").start);
  [...$("#pages").children].forEach((c, i) => vis(c, out((T - s("how").start - 0.5 - i * 0.4) / 0.45), 16, .95));
"""
