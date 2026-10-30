TITLE = "Урок 14 · Большие задачи"
IDEA = "Главная вещь урока — живой план справа: пункты отмечаются один за другим, текущий крутится, в конце — готовая таблица."
H1 = "Большие задачи"
TAG = "Часы работы — Лира делает сама, по шагам"
NEXT = "Скоро — новые уроки"
ICON = '<svg viewBox="0 0 24 24"><path d="M9 6h11M9 12h11M9 18h11"/><path d="M4 6l1 1 2-2M4 12l1 1 2-2"/><circle cx="5" cy="18" r="1.2"/></svg>'
SCENES = ["title", "problem", "give", "plan", "result", "ask", "phone", "how", "end"]
POS = {"problem": "{ lira: [330, 470, 280, 1], patrik: [330, 470, 300, 0] }"}
CSS = """
#plane svg { stroke: var(--accent); }
.say { position: absolute; left: 620px; top: 190px; max-width: 660px; padding: 20px 26px; border-radius: 26px 26px 8px 26px; background: var(--brand); color: #fff; font-size: 26px; font-weight: 700; line-height: 1.35; }
#mess { position: absolute; left: 620px; top: 240px; width: 700px; padding: 34px 40px; border-radius: 34px; background: var(--bg); box-shadow: var(--raise); }
#mess div { display: flex; flex-wrap: wrap; gap: 12px; } #mess div span { padding: 14px 20px; border-radius: 18px; box-shadow: var(--raise-s); font-size: 23px; font-weight: 800; }
#mess b { display: block; font: 600 42px Unbounded; margin-top: 26px; color: #b04a5c; }
#plan { position: absolute; left: 1320px; top: 140px; width: 520px; padding: 30px 30px; border-radius: 36px; background: var(--bg); box-shadow: var(--raise); }
#plan h4 { font: 600 24px Unbounded; } #plan small.g { display: block; font-size: 17px; font-weight: 700; color: var(--mut); margin: 6px 0 16px; line-height: 1.4; }
.pi { display: flex; align-items: center; gap: 14px; padding: 13px 4px; font-size: 20px; font-weight: 700; }
.pi i { width: 34px; height: 34px; border-radius: 50%; flex: none; display: grid; place-items: center; font-style: normal; font-size: 18px; box-shadow: var(--press); color: transparent; }
.pi.done i { background: linear-gradient(135deg, #46d39a, #2fb383); color: #fff; box-shadow: none; }
.pi.now i { box-shadow: none; border: 4px solid rgba(69,96,234,.2); border-top-color: var(--accent); }
.pi.now { color: var(--accent); } .pi.todo { color: var(--mut); }
#plan .pb { height: 12px; border-radius: 99px; box-shadow: var(--press); margin-top: 14px; overflow: hidden; } #plan .pb i { display: block; height: 100%; background: var(--brand); border-radius: 99px; }
#tbl { position: absolute; left: 620px; top: 170px; width: 1220px; padding: 30px 36px; border-radius: 36px; background: var(--bg); box-shadow: var(--raise); }
#tbl h4 { font: 700 30px Unbounded; margin-bottom: 18px; display: flex; justify-content: space-between; align-items: center; }
#tbl h4 span { font: 800 19px Manrope; color: #fff; background: var(--brand); padding: 12px 20px; border-radius: 14px; }
#tbl table { width: 100%; border-collapse: collapse; font-size: 22px; font-weight: 700; }
#tbl th { text-align: left; font-size: 17px; color: var(--mut); font-weight: 800; padding: 0 12px 12px; }
#tbl td { padding: 15px 12px; box-shadow: 0 -1px 0 rgba(36,50,74,.08); } #tbl tr.best td { background: rgba(47,179,131,.12); } #tbl tr.best td:first-child { border-radius: 14px 0 0 14px; } #tbl tr.best td:last-child { border-radius: 0 14px 14px 0; }
#qa { position: absolute; left: 620px; top: 250px; width: 700px; padding: 30px 34px; border-radius: 32px; background: var(--bg); box-shadow: var(--raise); }
#qa small { font-size: 18px; font-weight: 800; color: var(--mut); } #qa p { font: 600 30px/1.3 Unbounded; margin: 10px 0 20px; }
#qa div { display: flex; gap: 12px; } #qa div span { padding: 14px 22px; border-radius: 16px; box-shadow: var(--raise-s); font-size: 22px; font-weight: 800; }
#qa div span.on { color: #fff; background: var(--brand); box-shadow: none; }
#phone { position: absolute; left: 1360px; top: 140px; width: 420px; height: 700px; border-radius: 58px; background: var(--bg); box-shadow: var(--raise); padding: 20px; }
#phone .scr { width: 100%; height: 100%; border-radius: 42px; background: #eef2f8; padding: 30px 22px; }
#phone h5 { font: 700 26px Unbounded; margin-bottom: 16px; } #phone .tabs { display: flex; gap: 6px; margin-bottom: 18px; } #phone .tabs span { flex: 1; text-align: center; padding: 10px 0; border-radius: 12px; font-size: 14px; font-weight: 800; background: #fff; }
#phone .tabs span.on { background: var(--brand); color: #fff; }
#phone .ta { background: #fff; border-radius: 16px; padding: 14px; font-size: 17px; font-weight: 600; min-height: 120px; line-height: 1.4; }
#phone .go { margin-top: 14px; padding: 15px; border-radius: 16px; text-align: center; color: #fff; background: var(--brand); font-size: 19px; font-weight: 800; }
#phone .nt { margin-top: 16px; font-size: 16px; color: var(--mut); font-weight: 700; line-height: 1.4; }
#studio { position: absolute; left: 620px; top: 200px; width: 760px; border-radius: 32px; background: var(--bg); box-shadow: var(--raise); padding: 30px 34px; }
#studio h3 { font: 700 30px Unbounded; margin-bottom: 14px; }
#studio .it { display: flex; align-items: center; gap: 14px; padding: 16px 18px; border-radius: 18px; box-shadow: var(--raise-s); margin-top: 12px; font-size: 21px; font-weight: 700; }
#studio .it em { margin-left: auto; font-style: normal; font-size: 17px; font-weight: 800; padding: 8px 14px; border-radius: 12px; }
#studio .it em.ok { background: rgba(47,179,131,.15); color: #1e7d5b; } #studio .it em.run { background: rgba(69,96,234,.12); color: var(--accent); }
"""
PLAN = ["Найти ноутбуки до 100 000 ₽", "Собрать характеристики", "Сравнить вес и батарею", "Сделать таблицу", "Проверить цены"]
ROWS = [("Лёгкий 14″", "1,2 кг", "14 ч", "94 900 ₽"), ("Рабочий 15″", "1,7 кг", "10 ч", "79 990 ₽"), ("Студент 14″", "1,4 кг", "12 ч", "61 500 ₽"),
        ("Мощный 16″", "2,1 кг", "7 ч", "99 000 ₽"), ("Тонкий 13″", "1,1 кг", "11 ч", "88 400 ₽")]
HTML = """
  <div class="layer" id="L-left">
    <div id="mess"><div><span>💻 Сравнить 5 ноутбуков</span><span>📊 Отчёт</span><span>🖥 Презентация</span></div><b>≈ 4 часа работы</b></div>
    <div class="say" id="q1">«Сравни пять ноутбуков до ста тысяч рублей и сделай таблицу»</div>
    <div id="tbl"><h4>Ноутбуки до 100 000 ₽<span>Открыть</span></h4><table><tr><th>Модель</th><th>Вес</th><th>Батарея</th><th>Цена</th></tr>""" + "".join(
        ('<tr class="best">' if i == 2 else "<tr>") + f"<td>{a}</td><td>{b}</td><td>{c}</td><td>{d}</td></tr>" for i, (a, b, c, d) in enumerate(ROWS)) + """</table></div>
    <div id="qa"><small>ЛИРА СПРАШИВАЕТ</small><p>Что важнее — вес или батарея?</p><div><span id="qa1">Вес</span><span id="qa2">Батарея</span></div></div>
    <div id="studio"><h3>Задачи</h3>
      <div class="it">💻 Сравнить ноутбуки<em class="ok">готово ✓</em></div>
      <div class="it">🖥 Презентация о погоде<em class="run">делаю · 3 из 5</em></div>
      <div class="it">📊 Отчёт за неделю<em class="ok">готово ✓</em></div></div>
  </div>
  <div class="layer" id="L-plan"><div id="plan"><h4>План</h4><small class="g">Сравнить пять ноутбуков до 100 000 ₽ и сделать таблицу</small>""" + "".join(
        f'<div class="pi todo" id="p{i}"><i>✓</i>{t}</div>' for i, t in enumerate(PLAN)) + """<div class="pb"><i id="pbar"></i></div></div></div>
  <div class="layer" id="L-phone"><div id="phone"><div class="scr"><h5>Мой день</h5><div class="tabs"><span>Дела</span><span>Заметки</span><span class="on">Сделанное</span></div>
    <div class="ta">Сделай презентацию о погоде на завтра</div><div class="go">Передать</div>
    <div class="nt" id="pn">Компьютер выключен — делаю в облаке Dewiar, пришлю, когда будет готово</div></div></div></div>
"""
JS = """
  layer("L-left", T, s("problem").start + 0.2, s("end").start);
  layer("L-plan", T, s("give").start + 1.2, s("result").start);
  scene($("#mess"), T, s("problem").start + 0.3, s("give").start);
  [...$("#mess div").children].forEach((c, i) => vis(c, out((T - s("problem").start - 0.6 - i * 0.35) / 0.4), 12));
  scene($("#q1"), T, s("give").start + 0.2, s("result").start, 20);
  const k = clamp((T - s("plan").start - 0.3) / Math.max(1, s("result").start - s("plan").start - 0.6)), n = Math.floor(k * 5);
  [0, 1, 2, 3, 4].forEach(i => { $("#p" + i).className = "pi " + (i < n || k >= 1 ? "done" : i === n ? "now" : "todo");
    const ic = $("#p" + i).querySelector("i"); ic.style.transform = i === n && k < 1 ? `rotate(${T * 360}deg)` : ""; });
  $("#pbar").style.width = (k * 100) + "%";
  scene($("#tbl"), T, s("result").start + 0.2, s("ask").start);
  [...$("#tbl").querySelectorAll("tr")].forEach((r, i) => { r.style.opacity = out((T - s("result").start - 0.5 - i * 0.18) / 0.3); });
  scene($("#qa"), T, s("ask").start + 0.2, s("phone").start);
  $("#qa1").classList.toggle("on", T > at("s6a") + 2.4);
  layer("L-phone", T, s("phone").start + 0.2, s("how").start);
  vis($("#pn"), out((T - s("phone").start - 2.0) / 0.4), 10);
  scene($("#studio"), T, s("how").start + 0.2, s("end").start);
  [...$("#studio").querySelectorAll(".it")].forEach((c, i) => vis(c, out((T - s("how").start - 0.6 - i * 0.35) / 0.4), 12));
"""
