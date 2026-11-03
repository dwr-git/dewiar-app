import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kit import KIT_CSS, KIT2_CSS
TITLE = "Урок 25 · Студия под себя"
IDEA = "Главная вещь урока — меню студии сжимается до нужного одним нажатием: «Минимум», «Для себя» или переключатели; скрытое не грузится, но работает."
H1 = "Студия под себя"
TAG = "В меню — только то, чем вы пользуетесь"
NEXT = "Скоро — новые уроки"
ICON = '<svg viewBox="0 0 24 24"><path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12M20 18h0"/><circle cx="16" cy="6" r="2"/><circle cx="10" cy="12" r="2"/><circle cx="18" cy="18" r="2"/></svg>'
SCENES = ["title", "problem", "sets", "hide", "find", "lite", "how", "end"]
POS = {"problem": "{ lira: [330, 730, 210, 1], patrik: [330, 350, 250, 1] }"}
CSS = KIT_CSS + KIT2_CSS + """
#stu { left: 640px; top: 120px; width: 1180px; height: 700px; }
#stu nav { gap: 0; padding: 22px 14px; } #stu nav .g { margin: 10px 10px 2px; font-size: 12px; } #stu nav .g:first-child { margin-top: 0; }
#stu nav span { font-size: 15px; padding: 5px 12px; margin-top: 3px; overflow: hidden; } #stu nav span i { font-style: normal; margin-right: 8px; }
#stu nav .x { color: #b04a5c; background: rgba(176,74,92,.1); }
#stu nav .g, #stu nav span { max-height: 60px; }
#stu .pg { position: relative; }
.pane { position: absolute; left: 32px; right: 32px; top: 112px; }
.sets { display: grid; grid-template-columns: repeat(3, 1fr); gap: 18px; }
.set { padding: 22px; border-radius: 24px; box-shadow: var(--raise-s); min-height: 210px; }
.set b { display: block; font: 700 24px Unbounded; } .set p { margin-top: 10px; font-size: 17px; font-weight: 700; color: var(--mut); line-height: 1.4; }
.set i { display: grid; place-items: center; width: 54px; height: 54px; border-radius: 16px; font-size: 28px; font-style: normal; margin-bottom: 14px; background: rgba(69,96,234,.1); }
.set.on { box-shadow: 0 0 0 4px var(--accent), var(--raise-s); } .set.on b { color: var(--accent); }
.now { margin-top: 22px; padding: 16px 20px; border-radius: 18px; box-shadow: var(--press); font-size: 19px; font-weight: 700; color: var(--mut); }
.now b { color: var(--ink); }
.hmh { margin-top: 24px; font-size: 15px; font-weight: 800; color: var(--mut); text-transform: uppercase; letter-spacing: .05em; }
.hm { display: flex; flex-wrap: wrap; margin-top: 4px; }
.hm span { width: 104px; overflow: hidden; display: flex; flex-direction: column; align-items: center; gap: 6px; padding: 12px 0 0; font-size: 14px; font-weight: 800; white-space: nowrap; }
.hm span i { width: 62px; height: 62px; border-radius: 20px; display: grid; place-items: center; font-size: 30px; font-style: normal; background: var(--bg); box-shadow: var(--raise-s); }
.grp { display: flex; align-items: center; gap: 14px; padding: 14px 18px; border-radius: 18px; box-shadow: var(--raise-s); margin-top: 12px; }
.grp b { font-size: 20px; min-width: 210px; } .grp .cs { display: flex; flex-wrap: wrap; gap: 8px; flex: 1; }
.grp .cs span { padding: 7px 12px; border-radius: 12px; box-shadow: var(--press); font-size: 15px; font-weight: 800; }
.grp .cs span.off { opacity: .4; text-decoration: line-through; box-shadow: none; }
.grp.off b { opacity: .45; }
#pay { left: 1250px; top: 690px; width: 540px; }
#pay > i { background: rgba(69,96,234,.12); }
#home { top: 160px; width: 900px; }
#home .sr { display: flex; align-items: center; gap: 12px; margin-top: 12px; padding: 18px 22px; border-radius: 20px; box-shadow: var(--press); font-size: 26px; font-weight: 700; min-height: 72px; }
#home .sr b::after { content: "|"; display: inline-block; width: 0; color: var(--accent); opacity: var(--cur, 0); }
#home .row em { cursor: default; } #home .row em.p { color: #fff; background: var(--brand); }
#ok { left: 640px; top: 520px; width: 900px; }
#ok > i { background: rgba(47,179,131,.16); }
#cmpv { position: absolute; left: 640px; top: 150px; width: 1180px; display: grid; grid-template-columns: 1fr 1fr; gap: 34px; }
.mock { position: relative; height: 380px; border-radius: 30px; overflow: hidden; padding: 26px; }
.mock.glass { background: linear-gradient(135deg, #8fb4ff, #c99cff 55%, #ffb3c7); }
.mock.glass .bl { position: absolute; border-radius: 50%; filter: blur(30px); opacity: .8; }
.mock .pnl { position: relative; height: 100%; border-radius: 22px; padding: 22px; }
.mock.glass .pnl { background: rgba(255,255,255,.32); backdrop-filter: blur(18px); border: 1px solid rgba(255,255,255,.6); box-shadow: 0 20px 50px -20px rgba(40,30,90,.45); }
.mock.flat { background: var(--bg); box-shadow: var(--raise); } .mock.flat .pnl { background: #e6edf6; box-shadow: 0 6px 16px -8px rgba(36,50,74,.3); }
.mock .pnl b { display: block; font: 700 22px Unbounded; } .mock .pnl p { margin-top: 14px; height: 30px; border-radius: 10px; background: rgba(255,255,255,.55); }
.mock.flat .pnl p { background: #fff; } .mock .pnl p:nth-child(3) { width: 80%; } .mock .pnl p:nth-child(4) { width: 60%; }
.cap { margin-top: 16px; font-size: 21px; font-weight: 800; text-align: center; } .cap small { display: block; margin-top: 4px; font-size: 17px; color: var(--mut); }
#seg { position: absolute; left: 640px; top: 690px; display: flex; align-items: center; gap: 22px; padding: 18px 24px; border-radius: 24px; background: var(--bg); box-shadow: var(--raise-s); }
#seg b { font-size: 22px; } #seg .sg { display: flex; padding: 5px; border-radius: 16px; box-shadow: var(--press); }
#seg .sg span { padding: 10px 18px; border-radius: 12px; font-size: 18px; font-weight: 800; color: var(--mut); } #seg .sg span.on { color: #fff; background: var(--brand); }
#seg small { font-size: 17px; font-weight: 700; color: var(--mut); }
#studio { top: 170px; width: 900px; }
"""
# пункты меню: (значок, имя, скрыт в «Для себя», скрыт в «Минимуме», «лишнее» для Патрика)
NAV = [("g", "Главное"), ("🏠", "Главная", 0, 0, 0),
       ("g", "Для себя"), ("💬", "Чат", 0, 0, 0), ("📅", "Календарь", 0, 0, 0), ("⏰", "Дела и напоминания", 0, 0, 0), ("📝", "Заметки", 0, 0, 0),
       ("💸", "Платежи", 0, 1, 0), ("🔐", "Сейф паролей", 0, 1, 0),
       ("g", "Лира делает сама"), ("🧩", "Задачи", 0, 1, 0), ("👁", "Дозор", 0, 1, 0),
       ("g", "Семья и близкие"), ("❤️", "Близкие", 0, 0, 0),
       ("g", "Работа"), ("👥", "Клиенты", 1, 1, 1), ("✉️", "Рассылка", 1, 1, 1), ("🌐", "Сайты", 1, 1, 1), ("🎧", "Суфлёр", 1, 1, 0)]


def nav():
    out, i = [], 0
    while i < len(NAV):
        g = NAV[i][1]; j = i + 1; kids = []
        while j < len(NAV) and NAV[j][0] != "g":
            kids.append(NAV[j]); j += 1
        hs, hm = int(all(k[2] for k in kids)), int(all(k[3] for k in kids))
        out.append(f'<div class="g" data-s="{hs}" data-m="{hm}">{g}</div>')
        out += [f'<span data-s="{s}" data-m="{m}" data-x="{x}"><i>{e}</i>{n}</span>' for e, n, s, m, x in kids]
        i = j
    return "".join(out)


SETS = [("all", "🗂", "Всё", "Все разделы на виду"), ("self", "🏡", "Для себя", "Без работы и бизнеса: клиентов, рассылок, сайтов, суфлёра, ботов"),
        ("min", "✨", "Минимум", "Чат, дела, календарь, заметки, близкие, память — и настройки")]
GRP = [("Для себя", ["Чат", "Календарь", "Дела", "Заметки", "Платежи", "Сейф"], True, ["Платежи"]),
       ("Лира делает сама", ["Задачи", "Дозор", "Совет ИИ"], True, []),
       ("Режимы Лиры", ["Для ребёнка", "Для старших"], False, []),
       ("Работа", ["Клиенты", "Рассылка", "Сайты", "Суфлёр", "Бот"], True, [])]
HTML = """
  <div class="layer" id="L-left">
    <div class="st" id="stu"><nav>""" + nav() + """</nav>
      <div class="pg"><h3>Оформление</h3><small>Что показывать — меню и значки «Главной»</small>
        <div class="pane" id="pn1"><div class="sets">""" + "".join(f'<div class="set" data-id="{i}"><i>{e}</i><b>{n}</b><p>{d}</p></div>' for i, e, n, d in SETS) + """</div>
          <div class="now" id="now"></div><div class="hmh">Значки «Главной»</div><div class="hm" id="hm"><span data-s="0" data-m="0"><i>💬</i>Чат</span><span data-s="0" data-m="0"><i>📅</i>Календарь</span><span data-s="0" data-m="0"><i>⏰</i>Дела</span><span data-s="0" data-m="0"><i>📝</i>Заметки</span><span data-s="0" data-m="0"><i>❤️</i>Близкие</span><span data-s="0" data-m="1"><i>💸</i>Платежи</span><span data-s="0" data-m="1"><i>🔐</i>Сейф</span><span data-s="0" data-m="1"><i>🧩</i>Задачи</span><span data-s="1" data-m="1"><i>👥</i>Клиенты</span><span data-s="1" data-m="1"><i>✉️</i>Рассылка</span><span data-s="1" data-m="1"><i>🌐</i>Сайты</span><span data-s="1" data-m="1"><i>🎧</i>Суфлёр</span></div></div>
        <div class="pane" id="pn2">""" + "".join(f'<div class="grp{"" if on else " off"}"><b>{g}</b><div class="cs">' + "".join(f'<span data-c="{c}">{c}</span>' for c in cs) +
                                                  f'</div><span class="tgl{" on" if on else ""}"><i></i></span></div>' for g, cs, on, _ in GRP) + """</div>
      </div></div>
    <div class="toast" id="pay"><i>💸</i><div><small>ПЛАТЕЖИ · РАЗДЕЛ СКРЫТ</small><b>Завтра — оплата интернета</b></div></div>
    <div class="card" id="home"><small>ГЛАВНАЯ · ПОИСК</small><div class="sr">🔎 <b id="sq"></b></div>
      <div class="row" id="hr"><i>🌐</i>Сайты<span style="font-size:18px;color:var(--mut);margin-left:10px">раздел скрыт — показать?</span><em id="hb">Показать</em></div></div>
    <div class="toast" id="ok"><i>✓</i><div><small>ГОТОВО</small><b>«Сайты» снова в меню. Скрыть — «Оформление» → «Что показывать»</b></div></div>
    <div id="cmpv">
      <div><div class="mock glass"><span class="bl" style="left:40px;top:60px;width:220px;height:220px;background:#6f8cff"></span><span class="bl" style="right:30px;bottom:20px;width:260px;height:200px;background:#ff8fb8"></span>
        <div class="pnl"><b>Студия</b><p></p><p></p><p></p><p></p></div></div><div class="cap">Обычный вид<small>стекло и размытие</small></div></div>
      <div><div class="mock flat"><div class="pnl"><b>Студия</b><p></p><p></p><p></p><p></p></div></div><div class="cap">Облегчённый вид<small>почти так же — а отзывается быстрее</small></div></div></div>
    <div id="seg"><b>Облегчённый вид</b><div class="sg"><span class="on">Сам</span><span>Включён</span><span>Выключен</span></div><small>«Сам» — включится на слабом компьютере</small></div>
    <div class="card" id="studio"><h3>Оформление</h3><small>Студия → «Оформление»</small>
      <div class="row"><i>🗂</i>Что показывать<em>наборы и переключатели</em></div>
      <div class="row"><i>⚡</i>Скорость<em>облегчённый вид</em></div>
      <div class="row"><i>🔍</i>Размер<em>масштаб</em></div>
      <div class="row"><i>🎨</i>Фон и анимация голоса<em>стили</em></div></div>
  </div>
"""
JS = """
  layer("L-left", T, s("problem").start + 0.2, s("end").start);
  const p0 = s("problem").start, s0 = s("sets").start;
  // режим меню во времени: живая сцена — «Минимум»; «Наборы» — по очереди; «Скрыть» — переключатели
  const tMin = at("s2b") + 0.8, tS1 = at("s3a") + LN.s3a.dur * 0.42, tS2 = at("s3a") + LN.s3a.dur * 0.8, h0 = s("hide").start;
  const EV = [[-1, "all"], [tMin, "min"], [s0 + 0.6, "all"], [tS1, "self"], [tS2, "min"], [h0, "all"], [h0 + 2.6, "g1"], [h0 + 3.8, "g2"]];
  let ei = 0; EV.forEach((e, i) => { if (T >= e[0]) ei = i; });
  const mode = EV[ei][1], pmode = EV[Math.max(0, ei - 1)][1], km = out((T - EV[ei][0]) / 0.5);
  const hid = (m, c) => m === "self" ? c.dataset.s === "1" : m === "min" ? c.dataset.m === "1" :
    m === "g1" ? c.dataset.s === "1" : m === "g2" ? (c.dataset.s === "1" || c.textContent.includes("Платежи")) : false;
  [...$("#stu nav").children].forEach(c => {
    const k = lerp(hid(pmode, c) ? 1 : 0, hid(mode, c) ? 1 : 0, km); c.dataset.k = k;
    c.style.maxHeight = ((1 - k) * 60) + "px"; c.style.opacity = 1 - k;
    c.style.marginTop = c.classList.contains("g") ? ((1 - k) * 10) + "px" : ((1 - k) * 3) + "px";
    if (!c.classList.contains("g")) c.style.paddingTop = c.style.paddingBottom = ((1 - k) * 6) + "px";
    c.classList.toggle("x", c.dataset.x === "1" && T > at("s2a") + 1.6 && T < tMin);
  });
  [...$("#hm").children].forEach(c => { const k = lerp(hid(pmode, c) ? 1 : 0, hid(mode, c) ? 1 : 0, km);
    c.style.width = ((1 - k) * 104) + "px"; c.style.opacity = 1 - k; });
  const offGrp = T > h0 + 2.6, offPay = T > h0 + 3.8;
  scene($("#stu"), T, p0 + 0.3, s("find").start, 24);
  vis($("#pn1"), Math.min(out((T - p0 - 0.8) / 0.4), 1 - out((T - h0) / 0.3)), 12);
  vis($("#pn2"), out((T - h0 - 0.2) / 0.4), 12);
  const curSet = { all: "all", self: "self", min: "min" }[mode] || "";
  [...$("#pn1 .sets").children].forEach(c => c.classList.toggle("on", c.dataset.id === curSet && T < h0));
  const nh = [...$("#stu nav").querySelectorAll("span")].filter(c => +c.dataset.k > 0.5).length;
  $("#now").innerHTML = nh ? `Скрыто разделов: <b>${nh}</b> — не загружаются, но работают` : "<b>Все разделы на виду</b>";
  const g4 = $("#pn2").children[3], g1 = $("#pn2").children[0];
  g4.classList.toggle("off", offGrp); g4.querySelector(".tgl").classList.toggle("on", !offGrp);
  [...g4.querySelectorAll(".cs span")].forEach(c => c.classList.toggle("off", offGrp));
  g1.querySelector('[data-c="Платежи"]').classList.toggle("off", offPay);
  scene($("#pay"), T, h0 + 5.0, s("find").start, 30);
  scene($("#home"), T, s("find").start + 0.2, s("lite").start);
  const kq = (T - s("find").start - 0.9) / 0.7; $("#sq").textContent = type("сайты", kq);
  $("#sq").style.setProperty("--cur", kq > 0 && kq < 1.6 ? (Math.floor(T * 2) % 2) : 0);
  vis($("#hr"), out((T - s("find").start - 1.8) / 0.4), 12);
  $("#hb").classList.toggle("p", T > s("find").start + 3.4);
  scene($("#ok"), T, s("find").start + 3.8, s("lite").start, 24);
  scene($("#cmpv"), T, s("lite").start + 0.2, s("how").start);
  vis($("#cmpv").children[1], out((T - s("lite").start - 2.0) / 0.5), 16);
  scene($("#seg"), T, s("lite").start + 3.6, s("how").start, 20);
  [...$("#cmpv .glass").querySelectorAll(".bl")].forEach((c, i) => { c.style.transform = `translate(${Math.sin(T * 0.7 + i * 2) * 30}px, ${Math.cos(T * 0.6 + i) * 20}px)`; });
  scene($("#studio"), T, s("how").start + 0.2, s("end").start);
  [...$("#studio").querySelectorAll(".row")].forEach((c, i) => vis(c, out((T - s("how").start - 0.6 - i * 0.3) / 0.4), 12));
"""
