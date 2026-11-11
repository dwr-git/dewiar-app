import os, sys, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kit import KIT_CSS, KIT2_CSS, CURSOR, CURSOR_JS
TITLE = "Урок 26 · Нода Лиры"
IDEA = "Главная вещь урока — свой компьютер становится частью Лиры одной кнопкой: проверка, «Стать нодой» — и он отвечает людям, пока простаивает, а за принятые ответы приходят талеры; личное не уходит, выключить — сразу."
H1 = "Нода Лиры"
TAG = "Ваш компьютер помогает Лире — и зарабатывает талеры"
NEXT = "Скоро — новые уроки"
ICON = ('<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3.2"/><circle cx="12" cy="3.6" r="1.4"/><circle cx="19.6" cy="16.4" r="1.4"/>'
        '<circle cx="4.4" cy="16.4" r="1.4"/><path d="M12 8.8V5M14.8 13.6l3.6 2.1M9.2 13.6l-3.6 2.1"/></svg>')
SCENES = ["title", "problem", "check", "when", "earn", "safe", "net", "how", "end"]
# живая сцена и итог — Патрик и Лира на виду
POS = {"problem": "{ lira: [330, 730, 210, 1], patrik: [330, 350, 250, 1] }",
       "net": "{ lira: [330, 730, 210, 1], patrik: [330, 350, 250, 1] }"}
CSS = KIT_CSS + KIT2_CSS + """
#film { --lamp: #E39B1B; --lamp-hi: #F6C564; --lamp-ink: #A86400; --line: rgba(36,50,74,.2); }
#plane svg { stroke: var(--lamp); }
#stu { left: 640px; top: 112px; width: 1180px; height: 728px; }
#stu nav { gap: 2px; } #stu nav span { font-size: 17px; } #stu nav span i { font-style: normal; margin-right: 8px; }
#stu nav span.on { position: relative; } #stu nav span.on u { position: absolute; right: 12px; top: 50%; width: 10px; height: 10px; margin-top: -5px; border-radius: 50%; background: #fff; opacity: .55; }
#stu nav span.on u.lit { background: var(--lamp-hi); opacity: 1; box-shadow: 0 0 0 4px rgba(246,197,100,.35); }
#stu .pg { position: relative; padding: 26px 30px; } #stu .pg > small { font-size: 17px; }
.blk { transition: none; }
.hero { position: relative; display: grid; grid-template-columns: 200px 1fr; gap: 28px; align-items: center; margin-top: 12px; padding: 14px 24px; border-radius: 26px; box-shadow: var(--raise-s); }
.orbit { width: 200px; height: 200px; overflow: visible; }
.orbit .rings circle { fill: none; stroke: var(--line); stroke-width: 1.3; stroke-dasharray: 2 5; }
.orbit .peers circle { fill: rgba(36,50,74,.36); }
.orbit .links path { fill: none; stroke: var(--lamp); stroke-width: 1.8; stroke-dasharray: 3 5; }
.orbit .glow { fill: var(--lamp-hi); }
.state { display: block; font: 700 32px/1.1 Unbounded; }
.hero.work .state { color: var(--lamp-ink); }
.why { margin-top: 6px; min-height: 50px; font-size: 17px; font-weight: 700; color: var(--mut); line-height: 1.4; }
.earn { display: flex; align-items: baseline; flex-wrap: wrap; gap: 2px 12px; margin-top: 8px; }
.earn b { font: 700 36px/1 Unbounded; color: var(--lamp-ink); font-variant-numeric: tabular-nums; } .earn span { font-size: 20px; font-weight: 800; }
.earn em { flex-basis: 100%; font-style: normal; font-size: 16px; font-weight: 700; color: var(--mut); margin-top: 4px; }
.acts { display: flex; align-items: center; gap: 16px; margin-top: 10px; } .acts small { font-size: 16px; font-weight: 700; color: var(--mut); }
.btn { position: relative; display: inline-block; padding: 12px 26px; border-radius: 16px; font-size: 19px; font-weight: 800; box-shadow: var(--raise-s); white-space: nowrap; }
.btn.pri { color: #fff; background: var(--brand); box-shadow: none; } .btn.off { color: var(--mut); box-shadow: var(--press); }
.btn::after { content: ""; position: absolute; inset: -7px; border-radius: 22px; border: 3px solid var(--accent); opacity: var(--ta, 0); transform: scale(var(--ts, 1)); }
.chip { position: absolute; left: 66px; top: 120px; padding: 6px 12px; border-radius: 99px; background: #fff; color: var(--lamp-ink); font-size: 17px; font-weight: 800; box-shadow: 0 8px 18px -8px rgba(36,50,74,.4); white-space: nowrap; opacity: 0; }
.grid2 { display: grid; grid-template-columns: 1.08fr 1fr; gap: 18px; margin-top: 12px; }
.pc { position: relative; padding: 16px 22px; border-radius: 24px; box-shadow: var(--raise-s); }
.dh { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 10px; } .dh b { font-size: 20px; }
.dws { padding: 5px 12px; border-radius: 99px; font-size: 15px; font-weight: 800; color: var(--mut); box-shadow: var(--press); white-space: nowrap; }
.dws.ok { color: #1e7d5b; background: rgba(47,179,131,.15); box-shadow: none; }
#chl { list-style: none; display: grid; gap: 5px; min-height: 204px; }
#chl li { display: grid; grid-template-columns: 26px 1fr; gap: 8px; align-items: center; font-size: 16px; font-weight: 700; white-space: nowrap; overflow: hidden; }
#chl li i { width: 24px; height: 24px; border-radius: 50%; display: grid; place-items: center; font-style: normal; font-size: 14px; color: #fff; background: #2fb383; }
#chl li span { overflow: hidden; text-overflow: ellipsis; color: var(--mut); } #chl li span b { color: var(--ink); margin-right: 6px; }
#chl li.hl { color: var(--accent); }
#chh { font-size: 16px; font-weight: 700; color: var(--mut); line-height: 1.45; }
.pc .btn { margin-top: 8px; font-size: 17px; padding: 10px 20px; }
.fld { margin-top: 8px; } .fld > span { display: block; font-size: 14px; font-weight: 800; letter-spacing: .05em; text-transform: uppercase; color: var(--mut); }
.sg { display: inline-flex; margin-top: 6px; padding: 4px; border-radius: 14px; box-shadow: var(--press); }
.sg i { padding: 8px 12px; border-radius: 11px; font-style: normal; font-size: 15px; font-weight: 800; color: var(--mut); white-space: nowrap; }
.sg i.on { color: #fff; background: var(--brand); }
.fld em { display: block; margin-top: 6px; font-style: normal; font-size: 15px; font-weight: 700; color: var(--accent); min-height: 20px; }
.ph { margin-top: 8px; font-size: 15px; font-weight: 700; color: var(--mut); line-height: 1.4; }
.ring { box-shadow: 0 0 0 4px var(--accent), var(--raise-s) !important; }
#bal { left: 1230px; top: 650px; width: 620px; }
#bal > i { background: rgba(227,155,27,.18); }
#bal small b { display: inline; font-size: inherit; color: var(--mut); }
/* личное и пауза */
#gone { left: 640px; top: 190px; width: 660px; }
#gone .q { margin-top: 10px; padding: 20px 24px; border-radius: 22px; box-shadow: var(--raise-s); font-size: 27px; font-weight: 800; }
#gone .q em { display: inline-block; margin-top: 12px; font-style: normal; font-size: 16px; font-weight: 800; color: #1e7d5b; background: rgba(47,179,131,.15); padding: 7px 12px; border-radius: 12px; white-space: nowrap; }
#gone .wall { margin-top: 26px; padding-top: 22px; border-top: 3px dashed rgba(176,74,92,.35); }
#gone .wall > small { display: block; font-size: 18px; font-weight: 800; color: #b04a5c; margin-bottom: 6px; }
#gone .wall .chips span { font-size: 20px; padding: 12px 16px; color: #8a3a4a; }
#ctl { left: 1340px; top: 190px; width: 480px; padding: 28px 30px; }
#ctl .mini { display: flex; align-items: center; gap: 18px; } #ctl .mini svg { width: 110px; height: 110px; flex: none; overflow: visible; }
#ctl .mini b { font: 700 26px Unbounded; } #ctl .mini.work b { color: var(--lamp-ink); }
#ctl .btn { margin-top: 18px; } #ctl .cap { margin-top: 10px; font-size: 16px; font-weight: 700; color: var(--mut); min-height: 22px; }
#ctl .row { font-size: 20px; padding: 13px 15px; } #ctl .row em { font-size: 16px; padding: 7px 12px; }
#ctl .sm { margin-top: 22px; font-size: 14px; font-weight: 800; letter-spacing: .06em; color: var(--mut); }
/* сеть */
#net { position: absolute; left: 600px; top: 110px; width: 1260px; height: 740px; }
#net svg { width: 100%; height: 100%; overflow: visible; }
#net .ln { stroke: var(--lamp); stroke-width: 1.6; fill: none; }
#net .nd { fill: rgba(36,50,74,.28); }
#net .me { fill: none; stroke: var(--accent); stroke-width: 3; }
#net .cg { fill: var(--lamp-hi); }
#net .av { position: absolute; width: 88px; height: 88px; border-radius: 50%; object-fit: cover; background: radial-gradient(circle, #fff, #e3ebf5); box-shadow: 0 0 0 5px #F6C564, 0 10px 30px -8px rgba(168,100,0,.6); }
#net text { font: 800 22px Manrope; fill: var(--ink); }
#net .lb { position: absolute; padding: 10px 16px; border-radius: 16px; background: var(--bg); box-shadow: var(--raise-s); font-size: 20px; font-weight: 800; white-space: nowrap; }
#net .lb.c { font: 700 30px Unbounded; padding: 14px 24px; color: var(--lamp-ink); }
#studio { top: 170px; width: 900px; }
"""

ORBIT = """<svg class="orbit" viewBox="0 0 220 220">
  <g class="rings"><circle cx="110" cy="110" r="46"/><circle cx="110" cy="110" r="74"/><circle cx="110" cy="110" r="102"/></g>
  <g class="peers" data-r="1"><circle cx="110" cy="36" r="4.6"/><circle cx="174" cy="147" r="3.8"/><circle cx="46" cy="147" r="4.2"/></g>
  <g class="peers" data-r="2"><circle cx="110" cy="8" r="3.6"/><circle cx="208" cy="128" r="4.2"/><circle cx="31" cy="176" r="3.4"/><circle cx="160" cy="21" r="3.2"/><circle cx="16" cy="84" r="3.8"/></g>
  <g class="links"><path d="M110 64v-28M150 133l24 14M70 133l-24 14"/></g>
  <circle class="glow" cx="110" cy="110" r="36"/>
  <circle class="core" cx="110" cy="110" r="18"/>
</svg>"""

NAV = [("g", "Главное"), ("🏠", "Главная", ""), ("✳️", "Нода Лиры", "node"),
       ("g", "Для себя"), ("💬", "Чат", ""), ("📅", "Календарь", ""), ("⏰", "Дела и напоминания", ""), ("📝", "Заметки", ""), ("💸", "Платежи", ""),
       ("g", "Лира делает сама"), ("🧩", "Задачи", ""), ("👁", "Дозор", ""), ("🎙", "Подкасты", ""),
       ("g", "Семья и близкие"), ("❤️", "Близкие", ""), ("👪", "Семья", "")]


def nav():
    return "".join(f'<div class="g">{x[1]}</div>' if x[0] == "g" else
                   f'<span{" class=on" if x[2] else ""}><i>{x[0]}</i>{x[1]}{"<u id=ndot></u>" if x[2] else ""}</span>' for x in NAV)


CHECK = [("Аккаунт dewiar.pro", "вход выполнен"), ("Правила сети", "подписаны ключом Dewiar"),
         ("Своя модель", "Ollama: qwen3:8b"), ("Видеокарта", "RTX 4060, 8 ГБ"), ("Питание", "от сети"),
         ("Скорость", "ответ за 2,4 с — быстро")]


def network(seed=26):
    """Сеть нод: точки в эллипсе вокруг центра, каждая — с двумя ближайшими; расстояние до центра — когда загорится."""
    r = random.Random(seed)
    cx, cy, pts = 630, 370, []
    while len(pts) < 110:
        a, d = r.uniform(0, 2 * math.pi), math.sqrt(r.uniform(0.05, 1))
        x, y = cx + math.cos(a) * d * 600, cy + math.sin(a) * d * 345
        if math.hypot((x - cx) / 600, (y - cy) / 345) < 0.2 or any(math.hypot(x - p[0], y - p[1]) < 48 for p in pts):
            continue
        pts.append((x, y))
    lines = set()
    for i, (x, y) in enumerate(pts):
        near = sorted(range(len(pts)), key=lambda j: math.hypot(pts[j][0] - x, pts[j][1] - y))[1:3]
        lines |= {tuple(sorted((i, j))) for j in near}
    inner = sorted(range(len(pts)), key=lambda j: math.hypot(pts[j][0] - cx, pts[j][1] - cy))[:6]
    dist = lambda x, y: math.hypot((x - cx) / 600, (y - cy) / 345)
    me = min(range(len(pts)), key=lambda j: abs(pts[j][0] - (cx + 300)) + abs(pts[j][1] - (cy + 160)))
    svg = ['<svg viewBox="0 0 1260 740">']
    svg += [f'<path class="ln" data-d="{(dist(*pts[i]) + dist(*pts[j])) / 2:.3f}" d="M{pts[i][0]:.0f} {pts[i][1]:.0f}L{pts[j][0]:.0f} {pts[j][1]:.0f}"/>' for i, j in sorted(lines)]
    svg += [f'<path class="ln" data-d="0.1" d="M{cx} {cy}L{pts[j][0]:.0f} {pts[j][1]:.0f}"/>' for j in inner]
    svg += [f'<circle class="nd" data-d="{dist(x, y):.3f}" cx="{x:.0f}" cy="{y:.0f}" r="{6 + (i % 3) * 1.5:.1f}"/>' for i, (x, y) in enumerate(pts)]
    svg += [f'<circle class="me" id="me" cx="{pts[me][0]:.0f}" cy="{pts[me][1]:.0f}" r="18"/>',
            f'<circle class="cg" id="cg" cx="{cx}" cy="{cy}" r="80"/><circle id="cc" cx="{cx}" cy="{cy}" r="38" fill="url(#lampg)"/>',
            '<defs><radialGradient id="lampg"><stop offset="0" stop-color="#FFE3A6"/><stop offset="1" stop-color="#E39B1B"/></radialGradient></defs></svg>']
    lab = (f'<img class="av" src="../../../../data/avatars/lira.webp" alt="" style="left:{cx - 44}px;top:{cy - 44}px">'
           f'<div class="lb c" style="left:{cx - 62}px;top:{cy + 70}px">Лира</div>'
           f'<div class="lb" id="mel" style="left:{pts[me][0] + 30:.0f}px;top:{pts[me][1] - 22:.0f}px">💻 Ваш компьютер</div>')
    return "".join(svg) + lab


HTML = """
  <div class="layer" id="L-left">
    <div class="st" id="stu"><nav>""" + nav() + """</nav>
      <div class="pg"><h3>Нода Лиры</h3><small>Пока компьютер вам не нужен, он помогает Лире отвечать другим людям</small>
        <div class="hero blk" id="hero">""" + ORBIT + """
          <div><b class="state" id="nst">Пока не нода</b><p class="why" id="nwhy">Проверьте компьютер — и одной кнопкой станьте нодой.</p>
            <div class="earn" id="earn"><b id="tal">0</b><span id="tall">талеров сегодня</span><em id="cnt"></em></div>
            <div class="acts"><span class="btn off" id="go">Стать нодой</span><small id="goh">сначала — «Проверить компьютер»</small></div></div>
          <span class="chip">+0,03 тал.</span><span class="chip">+0,04 тал.</span><span class="chip">+0,03 тал.</span></div>
        <div class="grid2">
          <div class="pc blk" id="chk"><div class="dh"><b>Подходит ли мой компьютер</b><span class="dws" id="chs">не проверен</span></div>
            <p id="chh">Найду вашу модель, посмотрю видеокарту, память и питание, задам модели обычный вопрос и замерю, за сколько она отвечает. Около 10 секунд.</p>
            <ul id="chl">""" + "".join(f'<li><i>✓</i><span><b>{t}</b>{x}</span></li>' for t, x in CHECK) + """</ul>
            <span class="btn" id="chb">Проверить компьютер</span></div>
          <div class="pc blk" id="how"><div class="dh"><b>Как работать</b></div>
            <div class="fld"><span>Когда</span><div class="sg" id="when"><i data-v="idle">Когда простаивает</i><i data-v="night">Ночью</i><i data-v="always">Всегда</i></div><em id="whent"></em></div>
            <div class="fld"><span>Сколько отдавать</span><div class="sg" id="share"><i data-v="low">Немного</i><i data-v="half">Побольше</i><i data-v="all">Сколько попросят</i></div><em id="sharet"></em></div>
            <p class="ph">Сама ставится на паузу: от батареи, в игре и фильме на весь экран, пока вы говорите с Лирой.</p></div>
        </div>
      </div></div>
    <div class="toast" id="bal"><i>🪙</i><div><small>ИИ-БАЛАНС · <b>РАЗ В СУТКИ</b></small><b>Модели Dewiar, голоса, задачи в облаке</b><small>тратятся внутри Dewiar, в деньги не выводятся</small></div></div>
    <div class="card" id="gone"><small>НОДЕ УХОДИТ — ТОЛЬКО ОБЩИЙ ВОПРОС</small>
      <div class="q">💬 «Почему небо голубое?»<br><em>без имени, истории и адреса</em></div>
      <div class="wall"><small>НЕ УХОДИТ НИКОГДА</small><div class="chips"><span>🔒 Память</span><span>🔒 Заметки</span><span>🔒 Письма</span><span>🔒 Деньги</span><span>🔒 Здоровье</span><span>🔒 Детский режим</span><span>🔒 Имя и адрес</span></div></div></div>
    <div class="card" id="ctl"><div class="mini work" id="mini">""" + ORBIT.replace('class="orbit"', 'class="orbit" id="morb"') + """<div><b id="mst">Работает</b></div></div>
      <span class="btn" id="off">Выключить</span><div class="cap" id="offc"></div>
      <div class="sm">ПАУЗА — САМА</div>
      <div class="row" id="p1"><i>🎮</i>Игра на весь экран<em class="warn">пауза</em></div>
      <div class="row" id="p2"><i>🔋</i>От батареи<em class="warn">пауза</em></div></div>
    <div id="net">""" + network() + """</div>
    <div class="card" id="studio"><h3>Нода Лиры</h3><small>Студия → «Нода Лиры» — сразу под «Главной»</small>
      <div class="row"><i>🔍</i>Проверить компьютер<em>видеокарта от 8 ГБ, своя модель</em></div>
      <div class="row"><i>✳️</i>Стать нодой<em>одна кнопка</em></div>
      <div class="row"><i>🌙</i>Как работать<em>простаивает или ночью</em></div>
      <div class="row"><i>🪙</i>Сегодня заработано<em class="ok">талеры за ответы</em></div></div>
  </div>
  """ + CURSOR + """
"""
JS = CURSOR_JS + """
  layer("L-left", T, s("problem").start + 0.2, s("end").start);
  const fmt = (x) => x.toFixed(2).replace(".", ",");
  const pl = (n, a, b, c) => { n = Math.abs(n) % 100; const m = n % 10; return n > 10 && n < 20 ? c : m === 1 ? a : m >= 2 && m <= 4 ? b : c; };
  const tap = (el, t0) => { const k = (T - t0) / 0.6; const on = k > 0 && k < 1;
    el.style.setProperty("--ta", on ? (1 - k).toFixed(3) : 0); el.style.setProperty("--ts", on ? (1 + k * 0.3).toFixed(3) : 1);
    el.style.transform = k > 0 && k < 0.22 ? "scale(.94)" : ""; };
  // сердце ноды: кольца идут, линии текут, центр светится, когда работает
  const orbit = (svg, k) => {
    svg.querySelectorAll(".peers").forEach(g => { const r = g.dataset.r === "1" ? 1 : -0.7;
      g.setAttribute("transform", `rotate(${(T * 9 * r * k).toFixed(2)} 110 110)`); });
    svg.querySelectorAll(".peers circle").forEach(c => c.style.fill = k > 0.5 ? "rgba(168,100,0,.55)" : "rgba(36,50,74,.36)");
    const ln = svg.querySelector(".links path"); ln.style.opacity = 0.8 * k; ln.style.strokeDashoffset = -T * 14;
    svg.querySelector(".glow").style.opacity = k * (0.2 + 0.12 * Math.sin(T * 2.2));
    const core = svg.querySelector(".core"); core.style.fill = k > 0.5 ? "#E39B1B" : "rgba(36,50,74,.22)";
    core.setAttribute("r", 18 + k * 2 * Math.sin(T * 2.2));
  };
  const p0 = s("problem").start, b0 = at("s2b"), bd = LN.s2b.dur;
  const tCheck = b0 + 0.5, tJoin = b0 + bd * 0.42, tOff = at("s6a") + LN.s6a.dur * 0.42;
  scene($("#stu"), T, at("s2a") + 0.9, s("safe").start, 24);
  // проверка: пункты по одному
  tap($("#chb"), tCheck);
  const items = [...$("#chl").children];
  items.forEach((c, i) => vis(c, out((T - tCheck - 0.35 - i * 0.22) / 0.3), 8));
  const checked = T > tCheck + 0.35 + items.length * 0.22;
  $("#chh").style.display = T > tCheck ? "none" : "";
  $("#chs").textContent = checked ? "подходит" : T > tCheck ? "проверяю…" : "не проверен"; $("#chs").classList.toggle("ok", checked);
  $("#chb").textContent = T > tCheck ? "Проверить снова" : "Проверить компьютер";
  // «Стать нодой» → работает
  const work = T > tJoin && T < tOff, joined = T > tJoin;
  const go = $("#go"); tap(go, tJoin);
  go.textContent = joined ? "Выключить" : "Стать нодой";
  go.className = "btn " + (joined ? "" : checked ? "pri" : "off");
  $("#goh").textContent = joined ? "сразу — вопросы ответят серверы Dewiar" : checked ? "ничего не начнётся без этой кнопки" : "сначала — «Проверить компьютер»";
  $("#hero").classList.toggle("work", work);
  $("#nst").textContent = joined ? "Работает" : "Пока не нода";
  $("#nwhy").textContent = joined ? "На связи — ваша модель отвечает на общие вопросы людей." : checked ? "Компьютер подходит — выберите, когда работать, и нажмите «Стать нодой»." : "Проверьте компьютер — и одной кнопкой станьте нодой.";
  const kw = clamp((T - tJoin) / 0.8);
  orbit($("#hero .orbit"), joined ? kw : 0);
  $("#ndot").classList.toggle("lit", work);
  // счёт: ответ примерно каждые 1,1 с, за принятый — 0,03–0,04 талера
  const n = joined ? Math.max(0, Math.floor((T - tJoin - 0.9) / 1.1) + 1) : 0, tal = n * 0.034;
  vis($("#earn"), out((T - tJoin - 0.3) / 0.4), 8);
  $("#tal").textContent = (tal > 0 ? "≈ " : "") + fmt(tal);
  $("#tall").textContent = (tal < 1 ? "талера" : pl(Math.floor(tal), "талер", "талера", "талеров")) + " сегодня";
  $("#cnt").textContent = `${n} ${pl(n, "ответ", "ответа", "ответов")} сегодня · за принятые ответы`;
  [...$("#hero").querySelectorAll(".chip")].forEach((c, i) => {
    let best = -1; for (let j = i; j < n; j += 3) best = j;
    const tt = best < 0 ? -9 : T - (tJoin + 0.9 + best * 1.1), k = clamp(tt / 1.2);
    c.style.opacity = tt >= 0 && tt < 1.2 ? Math.sin(k * Math.PI) : 0; c.style.transform = `translate(${(i - 1) * 18}px, ${-k * 70}px)`; });
  // фокус сцены: нужный блок в рамке, остальное притушено
  const FOC = { check: "chk", when: "how", earn: "hero" }, scn = ORDER[sceneAt(T)], fid = FOC[scn];
  const kf = fid ? Math.min(out((T - s(scn).start - 0.2) / 0.5), 1 - out((T - SC[scn].end + 0.6) / 0.5)) : 0;
  ["hero", "chk", "how"].forEach(id => { const el = $("#" + id), me = id === fid;
    el.style.opacity = me || !fid ? 1 : lerp(1, 0.38, kf); el.classList.toggle("ring", me && kf > 0.5); });
  if (scn === "check") items.forEach((c, i) => c.classList.toggle("hl", Math.floor((T - s("check").start - 0.8) / 0.55) === i));
  else items.forEach(c => c.classList.remove("hl"));
  // как работать: когда — простаивает, ночью; сколько — немного, побольше
  const w0 = at("s4a"), wd = LN.s4a.dur;
  const when = T > w0 + wd * 0.5 && T < w0 + wd * 0.76 ? "night" : "idle", share = T > w0 + wd * 0.82 ? "half" : "low";
  const WT = { idle: "пока компьютер простаивает", night: "ночью, с 0 до 7" }, ST = { low: "немного — до 20 ответов в час", half: "побольше — до 60 в час" };
  [...$("#when").children].forEach(c => c.classList.toggle("on", c.dataset.v === when));
  [...$("#share").children].forEach(c => c.classList.toggle("on", c.dataset.v === share));
  $("#whent").textContent = WT[when]; $("#sharet").textContent = ST[share];
  scene($("#bal"), T, at("s5a") + LN.s5a.dur * 0.42, s("safe").start, 26);
  // личное и пауза
  scene($("#gone"), T, s("safe").start + 0.2, s("net").start, 24);
  [...$("#gone .wall .chips").children].forEach((c, i) => vis(c, out((T - s("safe").start - 1.2 - i * 0.16) / 0.3), 10));
  scene($("#ctl"), T, s("safe").start + 0.4, s("net").start, 24);
  const on2 = T < tOff; tap($("#off"), tOff);
  $("#mini").classList.toggle("work", on2); $("#mst").textContent = on2 ? "Работает" : "Выключена";
  $("#off").textContent = on2 ? "Выключить" : "Включить"; $("#off").className = "btn" + (on2 ? "" : " pri");
  $("#offc").textContent = on2 ? "" : "сразу — вопросы ответят серверы Dewiar";
  orbit($("#morb"), on2 ? 1 : clamp(1 - (T - tOff) / 0.4));
  vis($("#p1"), out((T - at("s6a") - LN.s6a.dur * 0.62) / 0.4), 12); vis($("#p2"), out((T - at("s6a") - LN.s6a.dur * 0.76) / 0.4), 12);
  // одна Лира: сеть загорается от центра волной
  const n0 = s("net").start; scene($("#net"), T, n0 + 0.2, s("how").start, 0);
  const wave = (T - n0 - 0.8) / 3.2;
  $("#net").querySelectorAll(".nd").forEach(c => { const k = clamp((wave - +c.dataset.d) / 0.15);
    c.style.fill = k > 0.5 ? "#E39B1B" : "rgba(36,50,74,.28)"; c.style.opacity = 0.55 + 0.45 * k; });
  $("#net").querySelectorAll(".ln").forEach(c => { const k = clamp((wave - +c.dataset.d) / 0.15); c.style.opacity = 0.08 + 0.5 * k;
    c.style.strokeDasharray = "4 6"; c.style.strokeDashoffset = -T * 16; });
  $("#cg").style.opacity = 0.18 + 0.12 * Math.sin(T * 2); $("#cg").setAttribute("r", 82 + 10 * Math.sin(T * 1.4));
  const km = out((T - n0 - 1.6) / 0.5); $("#me").style.opacity = km; $("#me").setAttribute("r", 18 + 4 * Math.sin(T * 3));
  vis($("#mel"), km, 10);
  // курсор: «Проверить компьютер» → «Стать нодой»; потом — «Выключить»
  const onA = Math.min(out((T - tCheck + 1.3) / 0.4), 1 - out((T - tJoin - 0.8) / 0.4)), onB = Math.min(out((T - tOff + 1.3) / 0.4), 1 - out((T - tOff - 0.8) / 0.4));
  const cp = onB > 0 ? walk([[tOff - 1.3, [1700, 760]], [tOff, ctr($("#off"))]]) : walk([[tCheck - 1.3, [1700, 860]], [tCheck, ctr($("#chb"))], [tJoin, ctr($("#go"))]]);
  cursor(cp, Math.max(onA, onB));
  scene($("#studio"), T, s("how").start + 0.2, s("end").start);
  [...$("#studio").querySelectorAll(".row")].forEach((c, i) => vis(c, out((T - s("how").start - 0.6 - i * 0.3) / 0.4), 12));
"""
