TITLE = "Урок 15 · Плагины"
IDEA = "Главная вещь урока — каталог плиток: из восьми умений выбираем одно, ставим, и оно сразу работает; лишнее — одним нажатием."
H1 = "Плагины"
TAG = "Готовые умения — включаете только нужное"
NEXT = "Скоро — новые уроки"
ICON = '<svg viewBox="0 0 24 24"><path d="M9 3h6v4a2 2 0 1 0 4 0h2v6h-4a2 2 0 1 0 0 4h4v4H3V9h4a2 2 0 1 0 0-4H3V3z"/></svg>'
SCENES = ["title", "problem", "catalog", "install", "use", "jobs", "remove", "how", "end"]
POS = {"problem": "{ lira: [330, 470, 280, 1], patrik: [330, 470, 300, 0] }"}
PLG = [("🌱", "Дача и огород", "заморозки, посадки, полив", "#3fb37f"), ("🥗", "Кухня", "рецепт из того, что есть", "#e88a3c"),
       ("🧳", "Путешествие", "погода, деньги, вещи", "#4a8be8"), ("📈", "Курсы и цены", "валюты и оповещения", "#8a63e0"),
       ("🇬🇧", "Учитель английского", "слова и разговоры", "#d9566b"), ("📰", "Дайджест", "новости по интересам", "#3a9fb0"),
       ("🌙", "Сказка на ночь", "с именем ребёнка", "#6a6fd8"), ("📄", "Проверка договора", "сроки и штрафы", "#b07a3a")]
CSS = """
#plane svg { stroke: var(--accent); }
#mess { position: absolute; left: 620px; top: 200px; width: 1180px; height: 560px; }
#mess span { position: absolute; padding: 16px 22px; border-radius: 20px; background: var(--bg); box-shadow: var(--raise-s); font-size: 24px; font-weight: 800; white-space: nowrap; }
#mess b { position: absolute; left: 330px; top: 470px; font: 600 40px Unbounded; color: #b04a5c; }
#cat { position: absolute; left: 620px; top: 150px; width: 1220px; display: grid; grid-template-columns: repeat(4, 1fr); gap: 22px; }
.pt { padding: 24px 22px; border-radius: 28px; background: var(--bg); box-shadow: var(--raise); }
.pt i { display: grid; place-items: center; width: 66px; height: 66px; border-radius: 20px; font-size: 36px; font-style: normal; margin-bottom: 14px; }
.pt b { display: block; font: 700 21px Manrope; line-height: 1.2; } .pt small { display: block; margin-top: 6px; font-size: 16px; font-weight: 700; color: var(--mut); }
.pt.pick { box-shadow: 0 0 0 4px var(--accent), var(--raise); }
#card { position: absolute; left: 620px; top: 150px; width: 820px; padding: 34px 40px; border-radius: 36px; background: var(--bg); box-shadow: var(--raise); }
#card .hd { display: flex; align-items: center; gap: 20px; } #card .hd i { width: 86px; height: 86px; border-radius: 26px; display: grid; place-items: center; font-size: 48px; font-style: normal; background: rgba(63,179,127,.16); }
#card h3 { font: 700 34px Unbounded; } #card .hd small { font-size: 19px; font-weight: 700; color: var(--mut); }
#card label { display: block; margin-top: 24px; font-size: 18px; font-weight: 800; color: var(--mut); }
#card .in { margin-top: 8px; padding: 18px 22px; border-radius: 18px; box-shadow: var(--press); font-size: 24px; font-weight: 700; min-height: 66px; }
#card .in::after { content: "|"; color: var(--accent); margin-left: 2px; opacity: var(--cur, 0); }
#card .go { margin-top: 28px; display: inline-block; padding: 18px 34px; border-radius: 20px; color: #fff; background: var(--brand); font-size: 23px; font-weight: 800; }
#card .go.ok { background: linear-gradient(135deg, #46d39a, #2fb383); }
.say { position: absolute; left: 620px; top: 190px; max-width: 720px; padding: 20px 26px; border-radius: 26px 26px 8px 26px; background: var(--brand); color: #fff; font-size: 27px; font-weight: 700; line-height: 1.35; }
#ans { position: absolute; left: 620px; top: 340px; width: 760px; padding: 28px 32px; border-radius: 8px 30px 30px 30px; background: var(--bg); box-shadow: var(--raise); font-size: 24px; font-weight: 600; line-height: 1.45; }
#ans b { color: var(--accent); } #ans .t { display: flex; gap: 12px; margin-top: 18px; } #ans .t span { flex: 1; text-align: center; padding: 14px 6px; border-radius: 18px; box-shadow: var(--raise-s); font-size: 19px; font-weight: 800; }
#ans .t span.cold { color: #3a6fd8; background: rgba(74,139,232,.1); box-shadow: none; }
#job { position: absolute; left: 620px; top: 200px; width: 720px; padding: 30px 34px; border-radius: 32px; background: var(--bg); box-shadow: var(--raise); }
#job small { font-size: 18px; font-weight: 800; color: var(--mut); } #job .row { display: flex; align-items: center; gap: 18px; margin-top: 14px; font-size: 25px; font-weight: 700; }
#job .tg { margin-left: auto; width: 76px; height: 42px; border-radius: 99px; box-shadow: var(--press); position: relative; flex: none; }
#job .tg i { position: absolute; top: 5px; left: 5px; width: 32px; height: 32px; border-radius: 50%; background: #fff; box-shadow: var(--raise-s); }
#job .tg.on { background: var(--brand); box-shadow: none; }
#push { position: absolute; left: 1400px; top: 200px; width: 420px; padding: 24px 26px; border-radius: 28px; background: var(--bg); box-shadow: var(--raise); }
#push small { font-size: 16px; font-weight: 800; color: var(--mut); } #push p { margin-top: 10px; font-size: 22px; font-weight: 700; line-height: 1.4; }
#push .tm { font: 600 46px Unbounded; color: var(--accent); margin-bottom: 6px; }
#rm { position: absolute; left: 620px; top: 200px; width: 760px; padding: 30px 34px; border-radius: 32px; background: var(--bg); box-shadow: var(--raise); }
#rm .it { display: flex; align-items: center; gap: 16px; padding: 16px 18px; border-radius: 18px; box-shadow: var(--raise-s); margin-top: 14px; font-size: 22px; font-weight: 700; }
#rm .it em { margin-left: auto; font-style: normal; font-size: 18px; font-weight: 800; padding: 10px 16px; border-radius: 12px; color: #b04a5c; background: rgba(176,74,92,.1); }
#rm .core { margin-top: 26px; font-size: 20px; font-weight: 800; color: var(--mut); }
#rm .core span { display: inline-block; margin: 8px 8px 0 0; padding: 10px 16px; border-radius: 14px; box-shadow: var(--press); color: var(--ink); }
#studio { position: absolute; left: 620px; top: 170px; width: 900px; border-radius: 32px; background: var(--bg); box-shadow: var(--raise); padding: 30px 34px; }
#studio h3 { font: 700 32px Unbounded; margin-bottom: 6px; } #studio > small { font-size: 19px; font-weight: 700; color: var(--mut); }
#studio .ph { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 18px; } #studio .ph span { padding: 14px 20px; border-radius: 18px; box-shadow: var(--raise-s); font-size: 21px; font-weight: 700; }
"""
MESS = [("🌱 Полив и заморозки", 0, 0), ("🥗 Меню на неделю", 380, 60), ("🧳 Вещи в дорогу", 760, 0), ("📈 Курс валют", 120, 160),
        ("🇬🇧 Слова на английском", 560, 190), ("🌙 Сказка на ночь", 40, 300), ("📄 Договор", 470, 330), ("📰 Новости", 860, 290)]
HTML = """
  <div class="layer" id="L-left">
    <div id="mess">""" + "".join(f'<span style="left:{x}px;top:{y}px">{t}</span>' for t, x, y in MESS) + """<b>Всё сразу — каша</b></div>
    <div id="cat">""" + "".join(f'<div class="pt{" pick" if i == 0 else ""}" id="pt{i}"><i style="background:{c}22">{e}</i><b>{n}</b><small>{d}</small></div>'
                               for i, (e, n, d, c) in enumerate(PLG)) + """</div>
    <div id="card"><div class="hd"><i>🌱</i><div><h3>Дача и огород</h3><small>Предупредит о заморозках, подскажет, что сажать и когда поливать</small></div></div>
      <label>Где дача</label><div class="in" id="f1"></div>
      <label>Что растёт</label><div class="in" id="f2"></div>
      <div class="go" id="go">Установить</div></div>
    <div class="say" id="q1">«Будут ли заморозки на этой неделе?»</div>
    <div id="ans">В Минске в ночь на четверг — <b>до −2°</b>. Укройте томаты и огурцы, клубнику можно не трогать.
      <div class="t"><span>Пн +4°</span><span>Вт +2°</span><span>Ср +1°</span><span class="cold">Чт −2°</span><span>Пт +3°</span></div></div>
    <div id="job"><small>ДЕЛА ПО РАСПИСАНИЮ · ДАЧА И ОГОРОД</small>
      <div class="row">🌡 Каждый вечер в 19:00 — проверить прогноз<span class="tg" id="tg"><i></i></span></div></div>
    <div id="push"><small>ЛИРА · 19:00</small><div class="tm">−2°</div><p>Ночью заморозок. Укройте томаты и огурцы.</p></div>
    <div id="rm"><div class="it">🌱 Дача и огород<em id="rmb">Удалить</em></div><div class="it">🥗 Кухня<em>Удалить</em></div>
      <div class="core">ОСТАЁТСЯ КАК БЫЛО<br><span>💬 Разговор</span><span>⏰ Напоминания</span><span>📝 Заметки</span><span>📅 Календарь</span></div></div>
    <div id="studio"><h3>Плагины</h3><small>Что умеет каждый — и что ему сказать</small>
      <div class="ph"><span>«Что сейчас сажать?»</span><span>«Когда поливать помидоры?»</span><span>«Запиши: посадил чеснок»</span><span>«Что я сажал в прошлом году?»</span></div></div>
  </div>
"""
JS = """
  layer("L-left", T, s("problem").start + 0.2, s("end").start);
  scene($("#mess"), T, s("problem").start + 0.3, s("catalog").start);
  [...$("#mess").querySelectorAll("span")].forEach((c, i) => { const k = out((T - s("problem").start - 0.5 - i * 0.28) / 0.4);
    c.style.opacity = k; c.style.transform = `translate(${Math.sin(T * 0.9 + i) * 8}px, ${(1 - k) * 20 + Math.cos(T * 0.7 + i) * 6}px) rotate(${Math.sin(i * 1.7) * 4}deg)`; });
  vis($("#mess b"), out((T - at("s2b")) / 0.4), 12);
  scene($("#cat"), T, s("catalog").start + 0.2, s("install").start);
  [...$("#cat").children].forEach((c, i) => vis(c, out((T - s("catalog").start - 0.4 - i * 0.14) / 0.4), 16, .94));
  $("#pt0").classList.toggle("pick", T > end("s3a") - 0.6);
  scene($("#card"), T, s("install").start + 0.2, s("use").start);
  const k1 = (T - s("install").start - 1.8) / 1.0, k2 = (T - s("install").start - 3.2) / 1.6;
  $("#f1").textContent = type("Минск", k1); $("#f2").textContent = type("томаты, огурцы, клубника", k2);
  $("#f1").style.setProperty("--cur", k1 > 0 && k1 < 1.3 ? (Math.floor(T * 2) % 2) : 0); $("#f2").style.setProperty("--cur", k2 > 0 && k2 < 1.3 ? (Math.floor(T * 2) % 2) : 0);
  const done = T > end("s4a") - 0.4; $("#go").classList.toggle("ok", done); $("#go").textContent = done ? "Установлен ✓" : "Установить";
  scene($("#q1"), T, s("use").start + 0.2, s("jobs").start, 20);
  scene($("#ans"), T, s("use").start + 2.6, s("jobs").start, 20);
  scene($("#job"), T, s("jobs").start + 0.2, s("remove").start);
  $("#tg").classList.toggle("on", T > s("jobs").start + 1.6); $("#tg i").style.left = (T > s("jobs").start + 1.6 ? 39 : 5) + "px";
  scene($("#push"), T, s("jobs").start + 3.4, s("remove").start, 30);
  scene($("#rm"), T, s("remove").start + 0.2, s("how").start);
  const gone = out((T - s("remove").start - 2.2) / 0.5); const r0 = $("#rm .it");
  r0.style.opacity = 1 - gone; r0.style.transform = `translateX(${gone * -60}px)`; r0.style.marginTop = (14 - gone * 14) + "px"; r0.style.maxHeight = (1 - gone) * 90 + "px";
  scene($("#studio"), T, s("how").start + 0.2, s("end").start);
  [...$("#studio .ph").children].forEach((c, i) => vis(c, out((T - s("how").start - 0.8 - i * 0.3) / 0.4), 12));
"""
