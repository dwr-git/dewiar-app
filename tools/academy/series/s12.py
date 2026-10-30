TITLE = "Урок 12 · Утро с Лирой"
IDEA = "Главная вещь урока — карточка «Утро с Лирой»: пять приложений сходятся в одну, строки появляются по мере рассказа."
H1 = "Утро с Лирой"
TAG = "Одна сводка вместо пяти приложений"
NEXT = "Скоро — новые уроки"
ICON = '<svg viewBox="0 0 24 24"><circle cx="12" cy="13" r="4"/><path d="M12 4v2M5 13H3M21 13h-2M6.3 7.3l1.4 1.4M17.7 7.3l-1.4 1.4M4 19h16"/></svg>'
SCENES = ["title", "problem", "brief", "work", "mail", "voice", "phone", "how", "end"]
CSS = """
#plane svg { stroke: #e0a020; }
#apps { position: absolute; left: 640px; top: 300px; width: 1100px; height: 520px; }
#apps span { position: absolute; width: 150px; height: 150px; border-radius: 40px; background: var(--bg); box-shadow: var(--raise); display: grid; place-items: center; font-size: 64px; }
#apps span small { position: absolute; bottom: -40px; font-size: 20px; font-weight: 800; color: var(--mut); white-space: nowrap; }
#am { position: absolute; left: 640px; top: 600px; font: 600 34px Unbounded; color: #b04a5c; }
#card { position: absolute; left: 620px; top: 120px; width: 720px; padding: 30px 34px; border-radius: 36px; background: var(--bg); box-shadow: var(--raise); }
#card .hd { display: flex; justify-content: space-between; align-items: center; } #card .hd small { font-size: 18px; font-weight: 800; color: var(--mut); }
#card .hd h3 { font: 700 30px Unbounded; }
#card .wx { display: flex; align-items: center; gap: 18px; margin: 18px 0 8px; } #card .wx i { font-size: 64px; font-style: normal; }
#card .wx b { font: 700 64px/1 Unbounded; } #card .wx span { font-size: 22px; color: var(--mut); font-weight: 700; }
.rw { display: flex; gap: 16px; align-items: center; padding: 13px 0; font-size: 22px; font-weight: 700; } .rw + .rw { box-shadow: 0 -1px 0 rgba(36,50,74,.08); }
.rw i { width: 44px; height: 44px; border-radius: 14px; display: grid; place-items: center; font-style: normal; font-size: 24px; box-shadow: var(--raise-s); flex: none; }
.rw em { font-style: normal; color: var(--mut); }
.rw.warn b { color: #c0522d; }
#card .acts { display: flex; gap: 12px; margin-top: 16px; } #card .acts span { padding: 14px 20px; border-radius: 16px; box-shadow: var(--raise-s); font-size: 19px; font-weight: 800; }
#card .acts span.on { color: #fff; background: var(--brand); box-shadow: none; }
#phone { position: absolute; left: 1420px; top: 150px; width: 400px; height: 700px; border-radius: 58px; background: var(--bg); box-shadow: var(--raise); padding: 20px; }
#phone .scr { width: 100%; height: 100%; border-radius: 42px; background: #eef2f8; padding: 30px 22px; }
#phone h4 { font: 700 24px Unbounded; } #phone .wx { font: 700 46px Unbounded; margin: 16px 0 6px; } #phone .wx small { font: 700 18px Manrope; color: var(--mut); }
#phone p { font-size: 18px; font-weight: 700; padding: 12px 0; line-height: 1.35; } #phone p + p { box-shadow: 0 -1px 0 rgba(36,50,74,.08); }
#homel { position: absolute; left: 620px; top: 70px; font-size: 20px; font-weight: 800; color: var(--mut); }
"""
APPS = [("🌤", "Погода", 0, 40), ("📅", "Календарь", 230, 0), ("📩", "Почта", 460, 60), ("✅", "Задачи", 690, 10), ("👥", "Сотрудники", 920, 70)]
HTML = """
  <div class="layer" id="L-left">
    <div id="apps">""" + "".join(f'<span style="left:{x}px;top:{y}px">{e}<small>{n}</small></span>' for e, n, x, y in APPS) + """</div>
    <div id="am">5 приложений — каждое утро</div>
    <div id="homel">Студия → Главная</div>
    <div id="card"><div class="hd"><h3>Утро с Лирой</h3><small>четверг, 8:00</small></div>
      <div class="wx"><i>🌤</i><b>+12°</b><span>ясно, днём до +16°</span></div>
      <div class="rw" id="r1"><i>📅</i><div>10:00 планёрка · <em>15:00 звонок «Ока»</em></div></div>
      <div class="rw" id="r2"><i>✅</i><div>3 дела на сегодня</div></div>
      <div class="rw warn" id="r3"><i>👥</i><div><b>Ольга: прайс просрочен</b> · <em>1 ждёт проверки</em></div></div>
      <div class="rw" id="r4"><i>🤝</i><div>Позвонить Иванову — сегодня</div></div>
      <div class="rw" id="r5"><i>📩</i><div>2 письма от людей · <em>14 рассылок</em></div></div>
      <div class="rw" id="r6"><i>🌙</i><div>За ночь: отчёт по продажам готов</div></div>
      <div class="acts" id="acts"><span id="tell">▶ Расскажи утро</span><span id="at8">Каждое утро в 8:00 голосом</span></div></div>
  </div>
  <div class="layer" id="L-phone"><div id="phone"><div class="scr"><h4>Ваш день</h4><div class="wx">+12° <small>ясно</small></div>
    <p>📅 10:00 планёрка, 15:00 «Ока»</p><p>👥 Ольга: прайс просрочен</p><p>🤝 Позвонить Иванову</p><p>📩 2 письма от людей</p></div></div></div>
"""
JS = """
  layer("L-left", T, s("problem").start + 0.2, s("end").start);
  const gather = out((T - s("brief").start - 0.1) / 0.9);
  [...$("#apps").children].forEach((c, i) => { const k = out((T - s("problem").start - 0.5 - i * 0.25) / 0.4);
    c.style.opacity = k * (1 - gather); c.style.transform = `translate(${gather * (120 - i * 230)}px, ${gather * 40}px) scale(${lerp(0.8, 1, k) * (1 - 0.5 * gather)})`; });
  vis($("#am"), out((T - at("s2a") - 2.0) / 0.4) * (1 - gather), 12);
  scene($("#card"), T, s("brief").start + 0.5, s("end").start);
  const row = (id, t0) => vis($(id), out((T - t0) / 0.4), 12);
  row("#r1", at("s3a") + 1.6); row("#r2", at("s3a") + 2.4);
  row("#r3", at("s4a") + 0.3); row("#r4", at("s4a") + 3.0);
  row("#r5", at("s5a") + 0.3); row("#r6", at("s5a") + 3.0);
  vis($("#acts"), out((T - s("voice").start - 0.2) / 0.4), 12);
  $("#tell").classList.toggle("on", T > at("s6a") + 0.6 && T < at("s6a") + 2.6);
  $("#at8").classList.toggle("on", T > at("s6a") + 3.0);
  layer("L-phone", T, s("phone").start + 0.2, s("end").start);
  [...$("#phone .scr").querySelectorAll("p")].forEach((c, i) => vis(c, out((T - s("phone").start - 0.8 - i * 0.3) / 0.4), 10));
  vis($("#homel"), out((T - s("how").start - 0.2) / 0.4), 10);
"""
