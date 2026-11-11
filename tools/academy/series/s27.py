import os, sys, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kit import KIT_CSS, KIT2_CSS, CURSOR, CURSOR_JS
TITLE = "Урок 27 · Подкасты"
IDEA = "Главная вещь урока — толстая книга превращается в разговор на 10 минут: перетащили PDF, «Простыми словами», «Сделать подкаст» — и Лира с Патриком обсуждают её вслух; две дорожки, текст с подсветкой, «На телефон»."
H1 = "Подкасты"
TAG = "Дайте книгу или ссылку — Лира и Патрик обсудят её вслух"
NEXT = "Скоро — новые уроки"
ICON = ('<svg viewBox="0 0 24 24"><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21M8.5 21h7"/></svg>')
SCENES = ["title", "problem", "make", "listen", "player", "phone", "how", "end"]
# живая сцена и «эфир» — Патрик и Лира на виду
TWO = "{ lira: [330, 730, 210, 1], patrik: [330, 350, 250, 1] }"
POS = {"problem": TWO, "listen": TWO}
CSS = KIT_CSS + KIT2_CSS + """
#film { --ca: #4f9fe0; --cb: #e59a1f; }
#plane svg { stroke: var(--accent); }
#stu { left: 640px; top: 112px; width: 1180px; height: 728px; grid-template-columns: 220px 1fr; }
#stu nav { padding: 24px 12px; gap: 2px; } #stu nav span { font-size: 17px; } #stu nav span i { font-style: normal; margin-right: 8px; }
#stu .pg { position: relative; padding: 24px 26px; } #stu .pg > small { font-size: 17px; }
.pdg { display: grid; grid-template-columns: 380px 1fr; gap: 20px; margin-top: 14px; }
.nw { padding: 16px 20px; border-radius: 24px; box-shadow: var(--raise-s); height: 586px; }
.nw h4, .stg h4 { font-size: 20px; font-weight: 800; }
.drop { position: relative; margin-top: 10px; display: grid; justify-items: center; gap: 3px; padding: 10px 10px; border-radius: 18px; border: 2.5px dashed rgba(69,96,234,.35); text-align: center; }
.drop svg { width: 30px; height: 30px; fill: none; stroke: var(--accent); stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
.drop span { font-size: 16px; font-weight: 700; } .drop small { font-size: 13px; font-weight: 700; color: var(--mut); }
.drop.over { border-color: var(--accent); background: rgba(69,96,234,.08); }
.src { display: flex; align-items: center; gap: 10px; margin-top: 10px; padding: 9px 12px; border-radius: 14px; box-shadow: var(--press); font-size: 16px; font-weight: 800; }
.src i { font-style: normal; font-size: 22px; } .src small { display: block; font-size: 13px; font-weight: 700; color: var(--mut); }
.lbl { display: block; margin-top: 10px; font-size: 13px; font-weight: 800; letter-spacing: .06em; text-transform: uppercase; color: var(--mut); }
.sg { display: flex; margin-top: 6px; padding: 4px; border-radius: 14px; box-shadow: var(--press); }
.sg i { flex: 1; text-align: center; padding: 7px 0; border-radius: 11px; font-style: normal; font-size: 15px; font-weight: 800; color: var(--mut); }
.sg i.on { color: #fff; background: var(--brand); }
.sts { display: grid; gap: 6px; margin-top: 6px; }
.st1 { display: flex; align-items: baseline; gap: 8px; padding: 8px 12px; border-radius: 13px; box-shadow: var(--raise-s); white-space: nowrap; overflow: hidden; } .st1 b { font-size: 15px; } .st1 small { font-size: 12.5px; font-weight: 700; color: var(--mut); overflow: hidden; text-overflow: ellipsis; }
.st1.on { box-shadow: 0 0 0 3px var(--accent), var(--raise-s); } .st1.on b { color: var(--accent); }
.hosts { display: flex; align-items: center; gap: 8px; margin-top: 6px; }
.hosts span { flex: 1; min-width: 0; display: flex; align-items: center; gap: 6px; padding: 7px 9px; border-radius: 14px; box-shadow: var(--press); font-size: 15px; font-weight: 800; }
.hosts span i { flex: none; width: 12px; height: 12px; border-radius: 50%; } .hosts span small { margin-left: auto; font-size: 11.5px; font-weight: 700; color: var(--mut); }
.hosts em { font-style: normal; color: var(--mut); font-size: 18px; }
.btn { position: relative; display: inline-block; padding: 11px 20px; border-radius: 15px; font-size: 16px; font-weight: 800; box-shadow: var(--raise-s); white-space: nowrap; }
.btn.pri { color: #fff; background: var(--brand); box-shadow: none; }
.btn::after { content: ""; position: absolute; inset: -7px; border-radius: 21px; border: 3px solid var(--accent); opacity: var(--ta, 0); transform: scale(var(--ts, 1)); }
.nw .go { display: block; text-align: center; margin-top: 12px; font-size: 17px; padding: 11px 0; }
.stg { position: relative; padding: 20px 22px; border-radius: 24px; box-shadow: var(--raise-s); height: 586px; overflow: hidden; }
.pane { position: absolute; left: 22px; right: 22px; top: 20px; bottom: 20px; }
.emp { display: grid; place-items: center; text-align: center; color: var(--mut); font-size: 18px; font-weight: 700; }
.emp .head { display: none; }
.emp .lanes { width: 360px; margin: 0 auto 18px; opacity: .55; }
.pt { font: 700 21px/1.2 Unbounded; }
.ring { box-shadow: 0 0 0 4px var(--accent); border-radius: 12px; }
#txt { padding: 4px; margin-left: -4px; margin-right: -4px; } .ps { margin-top: 6px; font-size: 15px; font-weight: 700; color: var(--mut); line-height: 1.4; }
.stages { list-style: none; display: grid; gap: 8px; margin-top: 16px; }
.stages li { display: flex; align-items: center; gap: 12px; font-size: 17px; font-weight: 700; color: var(--mut); }
.stages li i { width: 26px; height: 26px; border-radius: 50%; display: grid; place-items: center; font-style: normal; font-size: 14px; box-shadow: var(--press); }
.stages li.ok { color: var(--ink); } .stages li.ok i { color: #fff; background: #2fb383; box-shadow: none; }
.stages li.now { color: var(--accent); } .stages li.now i { box-shadow: 0 0 0 3px var(--accent); }
.bar { margin-top: 18px; height: 12px; border-radius: 99px; box-shadow: var(--press); overflow: hidden; } .bar b { display: block; height: 100%; border-radius: 99px; background: var(--brand); }
.player { display: grid; grid-template-columns: 54px 1fr; gap: 12px; align-items: center; margin-top: 14px; }
.play { width: 54px; height: 54px; border-radius: 50%; display: grid; place-items: center; color: #fff; background: var(--brand); }
.play svg { width: 22px; height: 22px; fill: #fff; }
.lanes { position: relative; display: grid; gap: 6px; }
.lane { position: relative; height: 24px; border-radius: 8px; background: rgba(36,50,74,.06); }
.lane > span { position: absolute; left: 6px; top: 2px; z-index: 2; font-size: 12px; font-weight: 800; color: var(--c); padding: 1px 6px; border-radius: 6px; background: rgba(255,255,255,.75); }
.lane > span.on { color: #fff; background: var(--c); }
.lane u { position: absolute; top: 4px; bottom: 4px; border-radius: 4px; background: var(--c); opacity: .5; }
.lane u.cur { opacity: 1; top: 1px; bottom: 1px; }
.head { position: absolute; top: -4px; bottom: -4px; width: 3px; border-radius: 2px; background: var(--ink); z-index: 3; }
.tm { display: flex; justify-content: space-between; margin-top: 4px; font-size: 13px; font-weight: 800; color: var(--mut); padding-left: 66px; }
.acts { display: flex; gap: 10px; margin-top: 12px; } .acts .btn { font-size: 15px; padding: 9px 14px; }
.txt { margin-top: 12px; display: grid; gap: 6px; }
.ln { position: relative; display: grid; grid-template-columns: 70px 1fr; gap: 8px; padding: 7px 10px; border-radius: 12px; font-size: 15px; font-weight: 700; line-height: 1.35; color: var(--mut); }
.ln b { color: var(--c); font-size: 14px; } .ln.cur { color: var(--ink); background: #fff; box-shadow: inset 4px 0 0 var(--c), 0 6px 16px -8px rgba(36,50,74,.3); }
.ln::after { content: ""; position: absolute; inset: -4px; border-radius: 15px; border: 3px solid var(--accent); opacity: var(--ta, 0); transform: scale(var(--ts, 1)); }
.file { position: absolute; left: 0; top: 0; display: flex; align-items: center; gap: 12px; padding: 12px 18px; border-radius: 18px; background: #fff; box-shadow: 0 18px 40px -16px rgba(36,50,74,.45); font-size: 18px; font-weight: 800; white-space: nowrap; z-index: 5; }
.file i { font-style: normal; font-size: 30px; } .file small { display: block; font-size: 14px; font-weight: 700; color: var(--mut); }
/* на телефон */
#ep2 { left: 640px; top: 170px; width: 700px; padding: 28px 32px; } #ep2 .pt { font-size: 26px; } #ep2 .acts .btn { font-size: 18px; padding: 12px 18px; }
#ep2 .lanes { margin-top: 18px; }
#sent { left: 640px; top: 470px; width: 700px; }
#sent > i { background: rgba(42,171,238,.16); }
.phone .scr.tgc { padding: 0; background: #dfe8ef; position: relative; }
.tgh { display: flex; align-items: center; gap: 12px; padding: 34px 20px 14px; background: #fff; }
.tgh img { width: 48px; height: 48px; border-radius: 50%; object-fit: cover; } .tgh b { display: block; font-size: 19px; } .tgh small { font-size: 14px; font-weight: 700; color: var(--tg); }
.tgm { padding: 10px 16px; } .tgm .bub { box-shadow: 0 2px 4px rgba(36,50,74,.08); font-size: 18px; max-width: 92%; }
.au { display: grid; grid-template-columns: 50px 1fr; gap: 12px; align-items: center; }
.au > i { width: 50px; height: 50px; border-radius: 50%; display: grid; place-items: center; background: var(--tg); }
.au > i svg { width: 20px; height: 20px; fill: #fff; }
.au b { display: block; font-size: 16px; line-height: 1.25; } .au small { display: block; margin-top: 4px; font-size: 13px; font-weight: 700; color: var(--mut); }
.wv { display: flex; align-items: center; gap: 2px; height: 26px; margin-top: 6px; } .wv s { flex: 1; border-radius: 2px; background: rgba(42,171,238,.55); }
#studio { top: 170px; width: 900px; }
"""

NAV = [("g", "Главное"), ("🏠", "Главная", 0), ("✳️", "Нода Лиры", 0),
       ("g", "Для себя"), ("💬", "Чат", 0), ("📅", "Календарь", 0), ("📝", "Заметки", 0), ("🎵", "Музыка", 0),
       ("g", "Лира делает сама"), ("🧩", "Задачи", 0), ("👁", "Дозор", 0), ("🗣", "Совет ИИ", 0), ("🎙", "Подкасты", 1),
       ("g", "Семья и близкие"), ("❤️", "Близкие", 0)]


def nav():
    return "".join(f'<div class="g">{x[1]}</div>' if x[0] == "g" else f'<span{" class=on" if x[2] else ""}><i>{x[0]}</i>{x[1]}</span>' for x in NAV)


DUR = 624                                                       # выпуск 10:24
# текст выпуска: (кто, начало, конец, реплика); a — Лира (объясняет), b — Патрик (спрашивает)
TXT = [("a", 124, 134, "Сегодня — книга, которую все хотят прочитать и всё откладывают."),
       ("b", 134, 137, "Так о чём эта книга, если в двух словах?"),
       ("a", 137, 142, "О привычках: маленький шаг каждый день сильнее рывка раз в год."),
       ("b", 142, 146, "Звучит просто. А почему тогда так трудно начать?"),
       ("a", 146, 153, "Потому что ждём вдохновения. А автор советует начать с двух минут в день.")]


def bars():
    """Реплики всего выпуска по дорожкам: вокруг показанного текста — те же времена, остальное — живой разговор."""
    r = random.Random(27)
    segs, t, w = [], 6.0, "a"
    while t < DUR - 6:
        if 120 <= t < 153:
            t = 153; w = "b"; continue
        d = r.uniform(3, 9) if w == "b" else r.uniform(6, 16)
        d = min(d, 120 - t) if t < 120 else d
        if d > 1:
            segs.append((w, t, t + d, -1))
        t += d + r.uniform(0.4, 1.2); w = "b" if w == "a" else "a"
    segs += [(w, a, b, i) for i, (w, a, b, _) in enumerate(TXT)]
    lane = lambda who: "".join(f'<u data-i="{i}" style="left:{a / DUR * 100:.2f}%;width:{max(0.35, (b - a) / DUR * 100):.2f}%"></u>' for w, a, b, i in segs if w == who)
    return (f'<div class="lane" style="--c:var(--ca)"><span>Лира</span>{lane("a")}</div>'
            f'<div class="lane" style="--c:var(--cb)"><span>Патрик</span>{lane("b")}</div><div class="head"></div>')


STAGES = ["Читаю материал", "Выписываю главное", "Составляю план", "Пишу диалог", "Сверяю с материалом", "Озвучиваю", "Собираю звук"]
PLAY = '<svg viewBox="0 0 24 24"><path d="M7 5h3.5v14H7zM13.5 5H17v14h-3.5z"/></svg>'
TRI = '<svg viewBox="0 0 24 24"><path d="M8 5.5v13l10.5-6.5z"/></svg>'
EP_T = "Маленький шаг сильнее рывка"
HTML = """
  <div class="layer" id="L-left">
    <div class="st" id="stu"><nav>""" + nav() + """</nav>
      <div class="pg"><h3>Подкасты</h3><small>Дайте материал — двое ведущих разберут его вслух</small>
        <div class="pdg">
          <div class="nw"><h4>Новый выпуск</h4>
            <div class="drop" id="drop"><svg viewBox="0 0 24 24"><path d="M12 15.5V4.5M7.5 9 12 4.5 16.5 9"/><path d="M4.5 14.5v3a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2v-3"/></svg>
              <span><b>Перетащите файлы</b> или нажмите</span><small>PDF, Word, EPUB, FB2, TXT — до 10 файлов</small></div>
            <div class="src" id="src"><i>📕</i><div>Книга о привычках.pdf<small>312 страниц · 4,1 МБ</small></div></div>
            <span class="lbl">Длина</span><div class="sg" id="len"><i data-m="5">5 мин</i><i data-m="10">10 мин</i><i data-m="20">20 мин</i></div>
            <span class="lbl">Подача</span><div class="sts" id="sty">
              <div class="st1" data-s="simple"><b>Простыми словами</b><small>для тех, кто впервые слышит о теме</small></div>
              <div class="st1" data-s="deep"><b>Глубоко</b><small>причины, механизмы, цифры</small></div>
              <div class="st1" data-s="debate"><b>Спор двух мнений</b><small>ведущие на разных позициях</small></div></div>
            <span class="lbl">Ведут</span><div class="hosts"><span><i style="background:var(--ca)"></i>Лира<small>объясняет</small></span><em>⇄</em><span><i style="background:var(--cb)"></i>Патрик<small>спрашивает</small></span></div>
            <span class="btn pri go" id="go">Сделать подкаст</span></div>
          <div class="stg">
            <div class="pane emp" id="pe"><div><div class="lanes">""" + bars() + """</div>Здесь появится выпуск — его можно слушать, читать и взять с собой</div></div>
            <div class="pane" id="pp"><div class="pt">Книга о привычках</div><div class="ps">Готовлю выпуск · 10 минут, простыми словами</div>
              <ul class="stages" id="stages">""" + "".join(f"<li><i></i>{x}</li>" for x in STAGES) + """</ul><div class="bar"><b id="pct"></b></div></div>
            <div class="pane" id="pv"><div class="pt">""" + EP_T + """</div><div class="ps">Ведут Лира и Патрик, простыми словами · по материалу: Книга о привычках.pdf</div>
              <div class="player"><div class="play" id="play">""" + PLAY + """</div><div class="lanes" id="tr">""" + bars() + """</div></div>
              <div class="tm"><b id="tnow">2:04</b><span>10:24</span></div>
              <div class="acts"><span class="btn pri">Скачать MP3</span><span class="btn" id="tph">На телефон</span><span class="btn">Открыть папку</span></div>
              <div class="txt" id="txt">""" + "".join(f'<div class="ln" style="--c:var(--c{w})"><b>{"Лира" if w == "a" else "Патрик"}</b><span>{x}</span></div>' for w, a, b, x in TXT) + """</div></div>
          </div>
        </div>
      </div></div>
    <div class="file" id="file"><i>📕</i><div>Книга о привычках.pdf<small>312 страниц</small></div></div>
    <div class="card" id="ep2"><small>ВЫПУСК ГОТОВ · 10:24</small><div class="pt">""" + EP_T + """</div>
      <div class="lanes">""" + bars() + """</div>
      <div class="acts"><span class="btn pri">Скачать MP3</span><span class="btn" id="tph2">На телефон</span><span class="btn">Открыть папку</span></div></div>
    <div class="toast" id="sent"><i>✈️</i><div><small>ПОДКАСТЫ</small><b>Отправила в Telegram — выпуск придёт файлом</b></div></div>
    <div class="card" id="studio"><h3>Подкасты</h3><small>Студия → «Лира делает сама» → «Подкасты»</small>
      <div class="row"><i>📄</i>Файл, ссылка, видео YouTube или тема<em>до 10 файлов</em></div>
      <div class="row"><i>⏱</i>Длина<em>5, 10 или 20 минут</em></div>
      <div class="row"><i>🎭</i>Подача<em>просто · глубоко · спор</em></div>
      <div class="row"><i>🎧</i>Слушать, читать, «На телефон»<em class="ok">MP3 с текстом</em></div></div>
  </div>
  <div class="layer" id="L-phone"><div class="phone"><div class="scr tgc">
    <div class="tgh"><img src="../../../../data/avatars/lira.webp" alt=""><div><b>Лира</b><small>в сети</small></div></div>
    <div class="tgm"><div class="bub" id="m1"><div class="au"><i>""" + TRI + """</i><div><b>""" + EP_T + """.mp3</b><div class="wv">""" + "".join(
        f'<s style="height:{h}%"></s>' for h in [30, 55, 80, 45, 65, 90, 50, 35, 70, 85, 40, 60, 95, 55, 30, 75, 50, 65, 40, 80, 55, 35]) + """</div><small>10:24 · 9,8 МБ</small></div></div></div>
      <div class="bub" id="m2">Выпуск готов — слушайте в дороге 🎧</div></div></div></div></div>
  """ + CURSOR + """
"""
JS = CURSOR_JS + """
  layer("L-left", T, s("problem").start + 0.2, s("end").start);
  const fmt = (x) => `${Math.floor(x / 60)}:${String(Math.floor(x % 60)).padStart(2, "0")}`;
  const tap = (el, t0) => { const k = (T - t0) / 0.6; const on = k > 0 && k < 1;
    el.style.setProperty("--ta", on ? (1 - k).toFixed(3) : 0); el.style.setProperty("--ts", on ? (1 + k * 0.2).toFixed(3) : 1);
    el.style.transform = k > 0 && k < 0.22 ? "scale(.95)" : ""; };
  const p0 = s("problem").start, b0 = at("s2b"), bd = LN.s2b.dur;
  const tDrag = b0 + 0.1, tDrop = b0 + 1.3, tLen = b0 + bd * 0.32, tSty = b0 + bd * 0.58, tGo = b0 + bd * 0.86;
  scene($("#stu"), T, at("s2a") + 0.6, s("phone").start, 24);
  // книга: из угла — в «Перетащите файлы»
  const dk = ease((T - tDrag) / (tDrop - tDrag)), [dx, dy] = ctr($("#drop"));
  const fx = lerp(1500, dx - 150, dk), fy = lerp(24, dy - 36, dk);
  const fv = T < tDrop ? out((T - at("s2a") - 1.2) / 0.5) : 1 - out((T - tDrop) / 0.3);
  $("#file").style.opacity = fv; $("#file").style.visibility = fv > 0.01 ? "visible" : "hidden";
  $("#file").style.transform = `translate(${fx}px, ${fy}px) rotate(${(1 - dk) * -4}deg) scale(${T > tDrop ? 1 - (T - tDrop) : 1})`;
  $("#drop").classList.toggle("over", T > tDrop - 0.5 && T < tDrop + 0.4);
  vis($("#src"), out((T - tDrop) / 0.4), 8);
  // длина, подача, «Сделать подкаст»
  const len = T > tLen ? "10" : "5", sty = T > tSty ? "simple" : "deep";
  [...$("#len").children].forEach(c => { c.classList.toggle("on", c.dataset.m === len); if (c.dataset.m === "10") tap(c, tLen); });
  [...$("#sty").children].forEach(c => { c.classList.toggle("on", c.dataset.s === sty); if (c.dataset.s === "simple") tap(c, tSty); });
  tap($("#go"), tGo);
  const busy = T > tGo && T < s("listen").start - 0.4;
  $("#go").textContent = busy ? "Готовлю выпуск…" : "Сделать подкаст"; $("#go").style.opacity = busy ? 0.6 : 1;
  // курсор: книга → 10 мин → простыми словами → сделать подкаст → (позже) реплика
  const tTap = at("s5a") + LN.s5a.dur * 0.62;
  const KF = [[tDrag, [fx + 160, fy + 30]], [tDrop, [dx + 10, dy + 6]], [tLen, ctr($('#len [data-m="10"]'))], [tSty, ctr($('#sty [data-s="simple"]'))],
    [tGo, ctr($("#go"))], [tTap, ctr($("#txt").children[4])]];
  const cp = T >= tDrag && T < tDrop ? [fx + 160, fy + 30] : walk(KF);          // пока тащит книгу — курсор на ней
  cursor(cp, Math.max(Math.min(out((T - tDrag + 0.4) / 0.4), 1 - out((T - tGo - 0.8) / 0.4)), Math.min(out((T - tTap + 1.2) / 0.4), 1 - out((T - tTap - 0.9) / 0.4))));
  // сцена справа: пусто → готовлю → выпуск
  const tEp = s("listen").start - 0.3;
  vis($("#pe"), 1 - out((T - tGo - 0.2) / 0.3), 0);
  vis($("#pp"), Math.min(out((T - tGo - 0.3) / 0.4), 1 - out((T - tEp) / 0.4)), 10);
  vis($("#pv"), out((T - tEp - 0.2) / 0.5), 10);
  const sEnd = end("s3a") - 0.2, kp = clamp((T - tGo - 0.4) / (sEnd - tGo - 0.4));
  [...$("#stages").children].forEach((c, i) => { const a = i / 7, b = (i + 1) / 7;
    c.className = kp >= b ? "ok" : kp >= a ? "now" : ""; c.querySelector("i").textContent = kp >= b ? "✓" : ""; });
  $("#pct").style.width = Math.max(2, kp * 100) + "%";
  // выпуск: время по репликам ведущих; нажали на реплику — перемотка
  const KT = [[-1, 124], [tEp, 124], [at("s4a"), 134], [end("s4a"), 137], [at("s4b"), 137], [end("s4b"), 142], [end("s4b") + 0.9, 142.6]];
  let ep = 124;
  for (let i = 1; i < KT.length; i++) if (T >= KT[i - 1][0]) ep = T >= KT[i][0] ? KT[i][1] : lerp(KT[i - 1][1], KT[i][1], (T - KT[i - 1][0]) / (KT[i][0] - KT[i - 1][0]));
  if (T > end("s4b") + 0.9) ep = 142.6 + (T - end("s4b") - 0.9) * 0.25;
  if (T > tTap) ep = 146 + (T - tTap);
  tap($("#txt").children[4], tTap);
  const r0 = at("s5a"), rd = LN.s5a.dur;
  $("#tr").classList.toggle("ring", T > r0 + 0.2 && T < r0 + rd * 0.3);
  $("#txt").classList.toggle("ring", T > r0 + rd * 0.32 && T < r0 + rd * 0.52);
  const live = T > at("s4a") - 0.3 && T < s("phone").start;
  const ci = live ? [134, 137, 142, 146, 1e9].findIndex(x => ep < x) : -1;
  [...$("#txt").children].forEach((c, i) => c.classList.toggle("cur", i === ci));
  $("#tr").querySelectorAll("u").forEach(u => u.classList.toggle("cur", live && +u.dataset.i === ci));
  const who = ci >= 0 ? (ci % 2 ? "b" : "a") : "";
  [...$("#tr").querySelectorAll(".lane > span")].forEach((c, i) => c.classList.toggle("on", live && who === (i ? "b" : "a")));
  $("#tr .head").style.left = (ep / 624 * 100) + "%"; $("#tnow").textContent = fmt(ep);
  $("#play").innerHTML = live ? `""" + PLAY + """` : `""" + TRI + """`;
  // на телефон
  const f0 = s("phone").start, tSend = at("s6a") + 0.9;
  scene($("#ep2"), T, f0 + 0.2, s("how").start, 24);
  $("#ep2 .head").style.left = "24%";
  tap($("#tph2"), tSend);
  scene($("#sent"), T, tSend + 0.5, s("how").start, 24);
  layer("L-phone", T, f0 + 0.6, s("how").start);
  vis($("#m1"), out((T - tSend - 1.2) / 0.5), 16); vis($("#m2"), out((T - tSend - 2.0) / 0.5), 16);
  scene($("#studio"), T, s("how").start + 0.2, s("end").start);
  [...$("#studio").querySelectorAll(".row")].forEach((c, i) => vis(c, out((T - s("how").start - 0.6 - i * 0.3) / 0.4), 12));
"""
