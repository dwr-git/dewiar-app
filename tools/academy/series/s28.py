import os, sys, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kit import KIT_CSS, KIT2_CSS, CURSOR, CURSOR_JS
TITLE = "Урок 28 · Радар"
IDEA = ("Главная вещь урока — двадцать вкладок новостей заменяет один экран: ссылки вставили разом — Лира читает сама, "
        "ставит каждому материалу сигнал (луч радара проходит по полю — точки загораются), утром — бриф дня, срочное — "
        "сразу на телефон, а на вопрос «почему все пишут про ИИ-агентов?» отвечает по прочитанному со ссылками.")
H1 = "Радар"
TAG = "Лира читает вашу тему за вас — и говорит главное первым"
NEXT = "Скоро — новые уроки"
ICON = ('<svg viewBox="0 0 24 24"><circle cx="12" cy="12.5" r="8.5"/><circle cx="12" cy="12.5" r="4.2"/><path d="M12 12.5l6.2-5.8"/>'
        '<circle cx="15.6" cy="9.4" r="1"/><path d="M19.5 2.8v2.8M18.1 4.2h2.8"/></svg>')
SCENES = ["title", "problem", "add", "pulse", "urgent", "ask", "how", "end"]
TWO = "{ lira: [330, 730, 210, 1], patrik: [330, 350, 250, 1] }"
POS = {"problem": TWO, "urgent": TWO, "ask": TWO}

# поле сигналов: точки недели (день 0..7, сигнал 0..10); три сильнейших — подписаны, как в студии
R = random.Random(28)
DOTS = []
for i in range(96):
    x = R.random() ** 0.8 * 7
    s = round(min(8.2, max(1.2, R.gauss(5, 1.5))), 1)
    DOTS.append((x, s))
DOTS += [(6.55, 9.4), (4.2, 8.7), (6.8, 8.1)]
FW, FH, FL, FB, FT = 860, 230, 34, 26, 16
X = lambda d: FL + d / 7 * (FW - FL - 10)
Y = lambda s: FT + (1 - s / 10) * (FH - FT - FB)


def col(s):
    if s >= 8.5:
        return "#E8467A"
    a, b, f = (180, 195, 255), (53, 80, 224), max(0, min(1, s / 8.5))
    return "rgb(%d,%d,%d)" % tuple(round(a[k] + (b[k] - a[k]) * f) for k in range(3))


def field():
    grid = "".join(f'<line x1="{FL}" x2="{FW - 10}" y1="{Y(v):.1f}" y2="{Y(v):.1f}"/><text x="8" y="{Y(v) + 4:.1f}">{v}</text>' for v in (0, 5, 10))
    grid += "".join(f'<line x1="{X(d):.1f}" x2="{X(d):.1f}" y1="{FT}" y2="{FH - FB}"/>' for d in range(8))
    days = ["чт, 5", "пт, 6", "сб, 7", "вс, 8", "пн, 9", "вт, 10", "ср, 11"]
    grid += "".join(f'<text x="{X(d + .5) - 16:.1f}" y="{FH - 6}">{t}</text>' for d, t in enumerate(days))
    dots = "".join(f'<circle class="dt" data-x="{x:.3f}" cx="{X(x):.1f}" cy="{Y(s):.1f}" r="{3 + s * .5:.1f}" fill="{col(s)}"'
                   f'{' data-hot="1"' if s >= 8.5 else ''}/>' for x, s in DOTS)
    lab = [("Утечка исходников движка PHP: в сеть попали ключи", 6.55, 9.4), ("Майнинговые карты превращаются в A100", 4.2, 8.7)]
    labs = "".join(f'<g class="lb" data-x="{x}"><path d="M{X(x):.1f} {Y(s):.1f}L{FW - 20 - len(t) * 7.6:.1f} {FT + 14 + i * 24}"/>'
                   f'<rect x="{FW - 30 - len(t) * 7.6:.1f}" y="{FT + 1 + i * 24}" width="{len(t) * 7.6 + 18:.1f}" height="21" rx="7"/>'
                   f'<text x="{FW - 21 - len(t) * 7.6:.1f}" y="{FT + 16 + i * 24}">{t}</text></g>' for i, (t, x, s) in enumerate(lab))
    return (f'<svg class="fld" viewBox="0 0 {FW} {FH}"><rect class="now" x="{X(6):.1f}" y="{FT}" width="{X(7) - X(6):.1f}" height="{FH - FT - FB}"/>'
            f'<g class="gr">{grid}</g><line class="sweep" id="sweep" x1="0" x2="0" y1="{FT}" y2="{FH - FB}"/>{dots}{labs}</svg>')


def spark(vals, c):
    mx, n = max(vals), len(vals) - 1
    pts = " ".join(f"{i * 120 / n:.1f},{34 - v / mx * 30:.1f}" for i, v in enumerate(vals))
    lx, ly = 120, 34 - vals[-1] / mx * 30
    return f'<svg viewBox="0 0 120 36" class="sp"><polyline points="{pts}" fill="none" stroke="{c}" stroke-width="2.2"/><circle cx="{lx}" cy="{ly:.1f}" r="3.5" fill="{c}"/></svg>'


NAV = [("g", "Главное"), ("🏠", "Главная", 0), ("✳️", "Нода Лиры", 0),
       ("g", "Для себя"), ("💬", "Чат", 0), ("📅", "Календарь", 0), ("📝", "Заметки", 0),
       ("g", "Лира делает сама"), ("🧩", "Задачи", 0), ("👁", "Дозор", 0), ("🎙", "Подкасты", 0),
       ("g", "Работа"), ("🌐", "Сайты", 0), ("📡", "Радар", 1), ("🎧", "Суфлёр", 0), ("✈️", "Бот в Telegram", 0)]


def nav():
    return "".join(f'<div class="g">{x[1]}</div>' if x[0] == "g" else f'<span{" class=on" if x[2] else ""}><i>{x[0]}</i>{x[1]}</span>' for x in NAV)


LINKS = ["https://habr.com/ru/rss/all/", "https://www.youtube.com/@lexfridman", "@ai_newz", "github.com/ollama/ollama"]
SRC = [("RSS", "habr.com", "52 за неделю"), ("YT", "@lexfridman", "9 за неделю"), ("TG", "@ai_newz", "38 за неделю"), ("GH", "ollama/ollama", "4 за неделю")]
TABS = ["Пульс", "Лента", "Тренды", "Источники", "Разум", "Галактика"]
BRIEF = "Неделя уязвимостей: PHP и curl, а ИИ-агенты дешевеют"
PTS = ["Утечка исходников PHP: в сеть попали ключи сборки — проверьте зависимости.",
       "В curl — переполнение при разборе заголовков прокси.",
       "Gemini 4 Carbon: агентная модель в 2–6 раз дешевле."]
TR = [("ии-агенты", "растёт", [2, 3, 2, 3, 4, 3, 9], "#E8467A", 9), ("безопасность", "растёт", [3, 2, 4, 3, 3, 5, 8], "#E8467A", 8),
      ("php", "новая тема", [0, 0, 1, 0, 0, 1, 6], "#3550E0", 6)]
Q = "Почему все вдруг пишут про ИИ-агентов?"
ANS = ("За сутки — 9 материалов против обычных 3: Google выпустила Gemini 4 Carbon, в 2–6 раз дешевле [1], "
       "а Московская биржа рассказала, как агенты ведут ночную диагностику [2]. Агенты стали дешёвыми — и их пробуют все.")
REFS = ["Google выпустила Gemini 4 Carbon — @ai_newz", "Биржа автоматизировала диагностику с LLM — habr.com"]

CSS = KIT_CSS + KIT2_CSS + """
#film { --c1: #3550E0; --hot: #E8467A; --grid: rgba(36,50,74,.1); }
#plane svg { stroke: var(--accent); }
#stu { left: 640px; top: 112px; width: 1180px; height: 728px; grid-template-columns: 230px 1fr; }
#stu nav { padding: 24px 12px; gap: 2px; } #stu nav span { font-size: 17px; } #stu nav span i { font-style: normal; margin-right: 8px; }
#stu .pg { position: relative; padding: 24px 28px; } #stu .pg > small { font-size: 17px; }
.chs { display: flex; gap: 8px; margin-top: 12px; } .chs span { padding: 6px 13px; border-radius: 99px; box-shadow: var(--raise-s); font-size: 14px; font-weight: 700; color: var(--mut); }
.chs b { color: var(--ink); }
.tabs { display: inline-flex; gap: 2px; margin-top: 14px; padding: 4px; border-radius: 16px; box-shadow: var(--press); }
.tabs i { font-style: normal; padding: 8px 15px; border-radius: 12px; font-size: 15px; font-weight: 700; color: var(--mut); }
.tabs i.on { color: var(--accent); box-shadow: var(--raise-s); }
.pane { position: absolute; left: 28px; right: 28px; top: 196px; bottom: 24px; }
.cd { padding: 16px 20px; border-radius: 22px; box-shadow: var(--raise-s); }
.cd h4 { font: 700 18px Unbounded; margin-bottom: 8px; } .cd h4 small { margin-left: 8px; font: 700 13px Manrope; color: var(--mut); }
/* источники */
.ta { margin-top: 6px; height: 130px; padding: 12px 14px; border-radius: 16px; box-shadow: var(--press); font: 600 16px/1.6 ui-monospace, "Ubuntu Mono", monospace; color: var(--ink); white-space: pre; overflow: hidden; }
.ta u { text-decoration: none; display: inline-block; width: 2px; height: 18px; margin-left: 1px; background: var(--accent); vertical-align: -3px; }
.kinds { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 4px; } .kinds span { padding: 4px 10px; border-radius: 99px; background: rgba(69,96,234,.08); font-size: 13px; font-weight: 700; color: var(--mut); }
.row2 { display: flex; justify-content: flex-end; margin-top: 12px; }
.btn { position: relative; display: inline-block; padding: 11px 20px; border-radius: 15px; font-size: 16px; font-weight: 800; box-shadow: var(--raise-s); white-space: nowrap; }
.btn.pri { color: #fff; background: var(--brand); box-shadow: none; }
.btn::after { content: ""; position: absolute; inset: -7px; border-radius: 21px; border: 3px solid var(--accent); opacity: var(--ta, 0); transform: scale(var(--ts, 1)); }
.srcs { margin-top: 14px; }
.sr { display: grid; grid-template-columns: 50px 1fr auto 60px; align-items: center; gap: 12px; padding: 9px 4px; border-bottom: 1px solid var(--grid); font-size: 16px; font-weight: 700; }
.sr:last-child { border-bottom: 0; }
.sr i { font-style: normal; display: grid; place-items: center; height: 28px; border-radius: 9px; font-size: 12px; font-weight: 800; color: var(--accent); background: rgba(69,96,234,.09); }
.sr small { color: var(--mut); font-size: 14px; } .sr em { font-style: normal; font-size: 13px; color: #1e9e74; }
.sr .tg2 { justify-self: end; width: 44px; height: 24px; border-radius: 99px; background: var(--brand); position: relative; } .sr .tg2::after { content: ""; position: absolute; right: 3px; top: 3px; width: 18px; height: 18px; border-radius: 50%; background: #fff; }
/* пульс */
.fld { width: 100%; height: auto; display: block; overflow: visible; }
.fld .gr line { stroke: var(--grid); stroke-width: 1; } .fld .gr text { font: 700 11px Manrope; fill: var(--mut); }
.fld .now { fill: rgba(79,108,240,.08); }
.fld .dt { stroke: #fff; stroke-width: 1.4; }
.fld .sweep { stroke: var(--accent); stroke-width: 2.5; }
.fld .lb path { stroke: rgba(232,70,122,.5); stroke-width: 1.2; fill: none; } .fld .lb rect { fill: #fff; } .fld .lb text { font: 700 13px Manrope; fill: var(--ink); }
.lgd { position: absolute; right: 20px; top: 18px; display: flex; align-items: center; gap: 8px; font-size: 13px; font-weight: 700; color: var(--mut); }
.lgd i { width: 64px; height: 6px; border-radius: 6px; background: linear-gradient(90deg, #B4C3FF, #3550E0); } .lgd em { font-style: normal; display: flex; align-items: center; gap: 5px; }
.lgd em::before { content: ""; width: 9px; height: 9px; border-radius: 50%; background: var(--hot); }
.two { display: grid; grid-template-columns: 1.55fr 1fr; gap: 16px; margin-top: 14px; }
.bh { font: 700 22px/1.2 Unbounded; margin: 2px 0 8px; } .bm { font-size: 13px; font-weight: 700; color: var(--mut); }
.bp { list-style: none; } .bp li { position: relative; padding: 3px 0 3px 18px; font-size: 15px; font-weight: 600; line-height: 1.4; }
.bp li::before { content: ""; position: absolute; left: 2px; top: 11px; width: 7px; height: 7px; border-radius: 50%; background: var(--c1); }
.trow { display: grid; grid-template-columns: 1fr 96px 28px; align-items: center; gap: 8px; padding: 6px 0; }
.trow b { display: block; font-size: 15px; } .trow small { font-size: 12.5px; font-weight: 800; } .trow .v { font: 700 18px Unbounded; text-align: right; }
.sp { width: 96px; height: 30px; overflow: visible; }
/* спросить */
.aq { display: flex; gap: 8px; margin-top: 4px; } .aq .in { flex: 1; padding: 11px 14px; border-radius: 14px; box-shadow: var(--press); font-size: 16px; font-weight: 600; white-space: nowrap; overflow: hidden; }
.aq .in.ph { color: var(--mut); } .aq .go { width: 46px; display: grid; place-items: center; border-radius: 14px; background: var(--brand); color: #fff; font-size: 20px; font-weight: 800; }
.sg { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; } .sg span { padding: 5px 11px; border-radius: 99px; box-shadow: var(--raise-s); font-size: 13px; font-weight: 700; color: var(--mut); }
.an { margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--grid); } .an > b { display: block; font-size: 15px; margin-bottom: 6px; }
.an p { font-size: 16px; font-weight: 600; line-height: 1.55; min-height: 100px; }
.rf { display: inline-grid; place-items: center; min-width: 20px; height: 20px; padding: 0 5px; border-radius: 6px; font-size: 12px; font-weight: 800; color: var(--accent); background: rgba(69,96,234,.12); vertical-align: 1px; }
.an ol { margin: 8px 0 0 20px; font-size: 14px; font-weight: 700; color: var(--accent); } .an ol li { margin: 3px 0; }
.dots { display: flex; gap: 6px; align-items: center; color: var(--mut); font-size: 15px; font-weight: 700; } .dots i { width: 8px; height: 8px; border-radius: 50%; background: var(--c1); }
.tc { padding: 14px 16px; border-radius: 18px; box-shadow: var(--raise-s); margin-bottom: 12px; }
.tc b { font: 700 17px Unbounded; } .tc small { display: block; font-size: 13px; font-weight: 800; margin: 2px 0 4px; } .tc .sp { width: 100%; height: 44px; }
/* срочное */
#hot { left: 640px; top: 210px; width: 700px; }
#hot > i { background: rgba(232,70,122,.14); }
.phone .scr.lock { background: linear-gradient(160deg, #cfdcf2, #e8eef8); padding: 60px 18px; text-align: center; }
.lock .tm { font: 600 64px Unbounded; color: #24324a; } .lock .dd { font-size: 17px; font-weight: 700; color: var(--mut); margin-bottom: 28px; }
.pn { text-align: left; padding: 14px 16px; border-radius: 20px; background: rgba(255,255,255,.88); box-shadow: 0 10px 24px -14px rgba(36,50,74,.5); }
.pn small { display: flex; align-items: center; gap: 8px; font-size: 13px; font-weight: 800; color: var(--mut); } .pn small img { width: 22px; height: 22px; border-radius: 6px; }
.pn b { display: block; margin-top: 6px; font-size: 17px; } .pn span { display: block; margin-top: 3px; font-size: 15px; font-weight: 600; line-height: 1.4; }
#studio { top: 170px; width: 900px; }
"""

HTML = """
  <div class="layer" id="L-left">
    <div class="st" id="stu"><nav>""" + nav() + """</nav>
      <div class="pg"><h3>Радар</h3><small>Главное в вашей нише за сутки: сигналы, тренды и выводы</small>
        <div class="chs"><span><b id="c-src">0</b> источников</span><span><b id="c-day">0</b> разобрано за сутки</span><span>сегодня <b id="c-lim">0</b> из 60 разборов</span></div>
        <div class="tabs" id="tabs">""" + "".join(f'<i data-t="{i}">{t}</i>' for i, t in enumerate(TABS)) + """</div>
        <div class="pane" id="pS"><div class="cd"><h4>Добавить источники</h4>
            <div class="kinds"><span>Сайт</span><span>RSS</span><span>YouTube</span><span>Telegram @канал</span><span>Reddit</span><span>GitHub</span><span>VK</span><span>Дзен</span></div>
            <div class="ta" id="ta"></div><div class="row2"><span class="btn pri" id="add">Добавить</span></div></div>
          <div class="cd srcs"><h4>Мои источники <small id="s-n"></small></h4><div id="srl">""" + "".join(
              f'<div class="sr"><i>{k}</i><div>{n}<small> · {w}</small></div><em>● прочитан</em><span class="tg2"></span></div>' for k, n, w in SRC) + """</div></div></div>
        <div class="pane" id="pP"><div class="cd" style="position:relative"><h4>Поле сигналов<small>260 материалов за неделю</small></h4>
            <div class="lgd">слабый<i></i>сильный<em>срочное</em></div>""" + field() + """</div>
          <div class="two"><div class="cd"><div class="bm">Бриф собран в 7:00 · по 47 материалам</div><div class="bh" id="bh"></div>
              <ul class="bp" id="bp">""" + "".join(f"<li>{p}</li>" for p in PTS) + """</ul></div>
            <div class="cd"><h4>Тренды</h4>""" + "".join(
              f'<div class="trow"><div><b>{n}</b><small style="color:{c}">{st}</small></div>{spark(v, c)}<span class="v">{d}</span></div>' for n, st, v, c, d in TR) + """</div></div></div>
        <div class="pane" id="pA"><div class="two" style="margin-top:0;grid-template-columns:1fr 1.25fr">
            <div class="cd"><div class="bm">Бриф собран в 7:00 · по 47 материалам</div><div class="bh">""" + BRIEF + """</div>
              <ul class="bp">""" + "".join(f"<li>{p}</li>" for p in PTS) + """</ul></div>
            <div class="cd"><h4>Спросите Лиру о теме</h4><div class="bm">Ответ — по прочитанному Радаром, со ссылками на материалы.</div>
              <div class="aq"><div class="in ph" id="aq">Например: что важного за неделю?</div><div class="go" id="ago">→</div></div>
              <div class="sg"><span>Что главное за неделю?</span><span>Почему растёт «ии-агенты»?</span><span>Что сделать первым?</span></div>
              <div class="an" id="an"><b id="anq">""" + Q + """</b><div class="dots" id="adots"><i></i><i></i><i></i>Лира читает материалы…</div>
                <p id="ant"></p><ol id="anr">""" + "".join(f"<li>{x}</li>" for x in REFS) + """</ol></div></div></div></div>
      </div></div>
    <div class="toast" id="hot"><i>⚡</i><div><small>РАДАР · СРОЧНО · СИГНАЛ 9,4</small><b>Утечка исходников PHP: в сеть попали ключи сборки</b></div></div>
    <div class="card" id="studio"><h3>Радар</h3><small>Студия → «Работа» → «Радар»</small>
      <div class="row"><i>🔗</i>Источники одним полем<em>сайт · YouTube · Telegram</em></div>
      <div class="row"><i>☀️</i>Бриф дня и тренды<em>каждое утро</em></div>
      <div class="row"><i>⚡</i>Срочное — сразу<em class="warn">на телефон</em></div>
      <div class="row"><i>💬</i>«Что нового в моей теме?»<em class="ok">голосом или здесь</em></div></div>
  </div>
  <div class="layer" id="L-phone"><div class="phone"><div class="scr lock">
    <div class="tm">7:42</div><div class="dd">четверг, 12 ноября</div>
    <div class="pn" id="pn"><small><img src="../../../../data/avatars/lira.webp" alt="">DEWIAR · РАДАР · сейчас</small><b>⚡ Срочно: утечка исходников PHP</b>
      <span>В сеть попали ключи сборки. Проверьте зависимости и обновите PHP сегодня.</span></div></div></div></div>
  """ + CURSOR + """
"""
LINKS_TXT = "\\n".join(LINKS)
JS = CURSOR_JS + """
  layer("L-left", T, s("problem").start + 0.2, s("end").start);
  const tap = (el, t0) => { const k = (T - t0) / 0.6; const on = k > 0 && k < 1;
    el.style.setProperty("--ta", on ? (1 - k).toFixed(3) : 0); el.style.setProperty("--ts", on ? (1 + k * 0.2).toFixed(3) : 1);
    el.style.transform = k > 0 && k < 0.22 ? "scale(.95)" : ""; };
  // студия: «Источники» → «Пульс»; срочное — на телефоне; потом «Спросите Лиру о теме»
  const a0 = at("s3a"), ad = LN.s3a.dur, tType = a0 + 0.4, tTyped = a0 + ad * 0.62, tAdd = a0 + ad * 0.78;
  const stuOn = Math.min(out((T - at("s2b") - 0.4) / 0.5), 1 - out((T - s("urgent").start + 0.4) / 0.4)) + (T > s("ask").start ? out((T - s("ask").start - 0.2) / 0.5) * (1 - out((T - s("how").start + 0.4) / 0.4)) : 0);
  vis($("#stu"), clamp(stuOn), 24, .97);
  const tab = T < s("pulse").start ? 3 : 0;
  [...$("#tabs").children].forEach(c => c.classList.toggle("on", +c.dataset.t === tab));
  vis($("#pS"), tab === 3 ? 1 : 0, 0); const ask = T >= s("ask").start; vis($("#pP"), tab === 0 && !ask ? out((T - s("pulse").start) / 0.4) : 0, 10); vis($("#pA"), ask ? 1 : 0, 0);
  // ссылки печатаются, «Добавить», источники встают в список
  const LT = \"""" + LINKS_TXT + """\";
  const typed = type(LT, (T - tType) / (tTyped - tType));
  $("#ta").innerHTML = typed.replace(/&/g, "&amp;").replace(/</g, "&lt;") + (T < tAdd && Math.floor(T * 2.5) % 2 ? "<u></u>" : "");
  tap($("#add"), tAdd);
  [...$("#srl").children].forEach((c, i) => vis(c, out((T - tAdd - 0.3 - i * 0.25) / 0.35), 8));
  $("#s-n").textContent = T > tAdd + 0.4 ? "4 из 4 включены" : "";
  const n = (k) => Math.round(clamp(k));
  $("#c-src").textContent = T > tAdd + 0.3 ? 4 : 0;
  // пульс: луч радара проходит по неделе — точки загораются; бриф печатается
  const p0 = s("pulse").start + 0.5, pd = LN.s4a.dur * 0.75, sw = clamp((T - p0) / pd);
  const fx = 34 + sw * (860 - 44);
  $("#sweep").setAttribute("x1", fx); $("#sweep").setAttribute("x2", fx); $("#sweep").style.opacity = sw > 0 && sw < 1 ? 1 : 0;
  document.querySelectorAll("#pP .dt").forEach(c => { const x = 34 + (+c.dataset.x) / 7 * (860 - 44), k = out((fx - x) / 30);
    c.style.opacity = k; const hot = c.dataset.hot; c.setAttribute("transform", hot && k > 0 && k < 1 ? "" : ""); });
  document.querySelectorAll("#pP .lb").forEach((g, i) => { g.style.opacity = out((T - p0 - pd - 0.2 - i * 0.3) / 0.4); });
  const day = Math.round(78 * sw), lim = Math.round(47 * sw);
  $("#c-day").textContent = T > s("pulse").start ? day : 0; $("#c-lim").textContent = T > s("pulse").start ? lim : 0;
  const tB = at("s4a") + LN.s4a.dur * 0.7;
  $("#bh").textContent = type(\"""" + BRIEF + """\", (T - tB) / 1.4);
  [...$("#bp").children].forEach((c, i) => vis(c, out((T - tB - 1.2 - i * 0.35) / 0.4), 6));
  // срочное: весточка в студии и на телефоне
  const u0 = s("urgent").start;
  scene($("#hot"), T, u0 + 0.3, s("ask").start, 24);
  layer("L-phone", T, u0 + 0.5, s("ask").start);
  vis($("#pn"), out((T - u0 - 1.2) / 0.5), -30);
  // спросить: вопрос печатается, «→», ответ со ссылками
  const q0 = at("s6a"), tQ = q0 + 0.3, tQd = q0 + LN.s6a.dur * 0.85, tGo = tQd + 0.3, tAns = at("s6b") + 0.2;
  const qtxt = type(\"""" + Q + """\", (T - tQ) / (tQd - tQ));
  $("#aq").textContent = T > tQ && T < tGo + 0.3 ? qtxt : "Например: что важного за неделю?"; $("#aq").classList.toggle("ph", !(T > tQ && T < tGo + 0.3));
  tap($("#ago"), tGo);
  vis($("#an"), out((T - tGo - 0.2) / 0.4), 8);
  vis($("#adots"), T < tAns ? 1 : 0, 0); $("#adots").style.display = T < tAns ? "" : "none";
  const at_ = type(\"""" + ANS + """\", (T - tAns) / (LN.s6b.dur * 0.75));
  $("#ant").innerHTML = at_.replace(/\\[(\\d)\\]/g, '<span class="rf">$1</span>');
  [...$("#anr").children].forEach((c, i) => vis(c, out((T - tAns - LN.s6b.dur * 0.75 - i * 0.3) / 0.4), 6));
  // курсор: печать ссылок → «Добавить»; вопрос → «→»
  const KF = [[a0, ctr($("#ta"))], [tAdd, ctr($("#add"))], [tGo - 1.2, ctr($("#aq"))], [tGo, ctr($("#ago"))]];
  cursor(walk(KF), Math.max(Math.min(out((T - a0 + 0.2) / 0.4), 1 - out((T - tAdd - 0.8) / 0.4)), Math.min(out((T - tQ) / 0.4), 1 - out((T - tGo - 0.9) / 0.4))));
  scene($("#studio"), T, s("how").start + 0.2, s("end").start);
  [...$("#studio").querySelectorAll(".row")].forEach((c, i) => vis(c, out((T - s("how").start - 0.6 - i * 0.3) / 0.4), 12));
"""
