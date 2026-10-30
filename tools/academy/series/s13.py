TITLE = "Урок 13 · Деньги голосом"
IDEA = "Главная вещь урока — записи справа: сказали трату — строка появилась; спросили — Лира посчитала; в начале месяца — полосы «куда ушли деньги»."
H1 = "Деньги голосом"
TAG = "Сказали трату — записано, спросили — посчитано"
NEXT = "Следующий урок — «Большие задачи»"
ICON = '<svg viewBox="0 0 24 24"><rect x="3" y="6" width="18" height="13" rx="2.5"/><path d="M3 10h18M7 15h3"/></svg>'
SCENES = ["title", "problem", "say", "income", "ask", "month", "family", "how", "end"]
POS = {"problem": "{ lira: [330, 470, 280, 1], patrik: [330, 470, 300, 0] }"}
CSS = """
#plane svg { stroke: #2fb383; }
.say { position: absolute; left: 620px; top: 200px; max-width: 640px; padding: 20px 26px; border-radius: 26px 26px 8px 26px; background: var(--brand); color: #fff; font-size: 26px; font-weight: 700; line-height: 1.35; }
#mess { position: absolute; left: 620px; top: 250px; width: 680px; padding: 34px 40px; border-radius: 34px; background: var(--bg); box-shadow: var(--raise); }
#mess b { display: block; font: 600 44px/1.25 Unbounded, sans-serif; }
#rc { position: absolute; left: 640px; top: 520px; width: 680px; height: 220px; }
#rc span { position: absolute; width: 120px; padding: 16px 14px; border-radius: 10px; background: #fff; box-shadow: 0 14px 30px -16px rgba(36,50,74,.45); font-size: 15px; font-weight: 700; color: var(--mut); line-height: 1.5; }
#rc span::before { content: "🧾"; display: block; font-size: 26px; margin-bottom: 4px; }
#led { position: absolute; left: 1360px; top: 140px; width: 480px; height: 700px; border-radius: 36px; background: var(--bg); box-shadow: var(--raise); padding: 28px 26px; overflow: hidden; }
#led h4 { font: 600 24px Unbounded; margin-bottom: 6px; } #led small.d { font-size: 17px; font-weight: 800; color: var(--mut); }
.en { display: flex; align-items: center; gap: 14px; padding: 16px 14px; margin-top: 12px; border-radius: 20px; background: #fff; box-shadow: 0 10px 22px -16px rgba(36,50,74,.5); }
.en i { width: 48px; height: 48px; border-radius: 15px; display: grid; place-items: center; font-style: normal; font-size: 24px; background: rgba(69,96,234,.1); flex: none; }
.en div { flex: 1; } .en b { display: block; font-size: 20px; } .en small { font-size: 15px; color: var(--mut); font-weight: 700; }
.en em { font-style: normal; font: 700 22px Unbounded; } .en em.minus { color: var(--ink); } .en em.plus { color: #1e9b6c; }
.en.old { opacity: .55; box-shadow: none; background: transparent; }
#ans { position: absolute; left: 620px; top: 330px; width: 660px; padding: 30px 34px; border-radius: 30px; background: var(--bg); box-shadow: var(--raise); }
#ans b { display: block; font: 700 46px Unbounded; margin: 8px 0 6px; } #ans small { font-size: 20px; font-weight: 800; color: var(--mut); }
#ans span { display: inline-block; margin-top: 16px; padding: 10px 16px; border-radius: 14px; background: rgba(69,96,234,.1); color: var(--accent); font-size: 18px; font-weight: 800; }
#mon { position: absolute; left: 620px; top: 150px; width: 1220px; padding: 34px 40px; border-radius: 36px; background: var(--bg); box-shadow: var(--raise); }
#mon h4 { font: 700 34px Unbounded; } #mon p { font-size: 22px; color: var(--mut); font-weight: 700; margin: 8px 0 22px; }
.bar { display: grid; grid-template-columns: 220px 1fr 150px; align-items: center; gap: 18px; margin-top: 14px; font-size: 23px; font-weight: 800; }
.bar s { height: 30px; border-radius: 10px; box-shadow: var(--press); position: relative; overflow: hidden; text-decoration: none; display: block; }
.bar s i { position: absolute; inset: 0 auto 0 0; border-radius: 10px; }
.bar em { font-style: normal; text-align: right; }
#fam { position: absolute; left: 620px; top: 200px; width: 760px; padding: 30px 34px; border-radius: 32px; background: var(--bg); box-shadow: var(--raise); }
#fam h4 { font: 600 26px Unbounded; margin-bottom: 8px; }
#fam .fr { display: flex; align-items: center; gap: 14px; padding: 14px 0; font-size: 22px; font-weight: 700; } #fam .fr + .fr { box-shadow: 0 -1px 0 rgba(36,50,74,.08); }
#fam .fr i { width: 46px; height: 46px; border-radius: 50%; display: grid; place-items: center; color: #fff; font: 700 18px Unbounded; font-style: normal; flex: none; }
#fam .fr span { flex: 1; } #fam .fr em { font-style: normal; font: 700 22px Unbounded; }
#studio { position: absolute; left: 620px; top: 210px; width: 760px; border-radius: 32px; background: var(--bg); box-shadow: var(--raise); padding: 30px 34px; }
#studio h3 { font: 700 30px Unbounded; margin-bottom: 18px; }
#studio .tabs { display: flex; gap: 10px; } #studio .tabs span { padding: 14px 22px; border-radius: 16px; box-shadow: var(--raise-s); font-size: 21px; font-weight: 800; }
#studio .tabs span.on { color: #fff; background: var(--brand); box-shadow: none; }
#studio p { margin-top: 20px; font-size: 21px; color: var(--mut); font-weight: 700; }
"""
RC = [("Пятёрочка<br>1 245 ₽", 0, 30, -8), ("Такси<br>380 ₽", 150, 0, 6), ("Аптека<br>612 ₽", 300, 40, -4), ("Кафе<br>890 ₽", 450, 10, 9), ("АЗС<br>2 100 ₽", 560, 70, -10)]
BARS = [("🛒 Продукты", 24300, "#4f6cf0"), ("🏠 Дом", 12800, "#6a8dff"), ("☕ Кафе", 7340, "#e59a1f"), ("🚕 Транспорт", 5100, "#5aa9e6"), ("… Остальное", 3900, "#9aa6b8")]
HTML = """
  <div class="layer" id="L-left">
    <div id="mess"><b>Куда ушли деньги<br>в этом месяце?</b></div>
    <div id="rc">""" + "".join(f'<span style="left:{x}px;top:{y}px;transform:rotate({r}deg)">{t}</span>' for t, x, y, r in RC) + """</div>
    <div class="say" id="q1">«Потратил тысячу двести на продукты»</div>
    <div class="say" id="q2">«Пришла зарплата, восемьдесят тысяч»</div>
    <div class="say" id="q3">«Сколько я потратил на кафе в октябре?»</div>
    <div id="ans"><small>КАФЕ · ОКТЯБРЬ</small><b>7 340 ₽</b><small>12 раз · чаще всего по пятницам</small><br><span>посчитано: 890 + 1 250 + 640 + … = 7 340</span></div>
    <div id="mon"><h4>Ваш октябрь</h4><p>Куда ушли деньги — 53 440 ₽</p>""" + "".join(
        f'<div class="bar"><span>{n}</span><s><i data-w="{v / 24300 * 100:.1f}" style="background:{c};width:0"></i></s><em>{v:,} ₽</em></div>'.replace(",", " ") for n, v, c in BARS) + """</div>
    <div id="fam"><h4>Семья · общий бюджет</h4>
      <div class="fr"><i style="background:linear-gradient(140deg,#ffcf7a,#e59a1f)">А</i><span>Анна: аптека</span><em>−2 400 ₽</em></div>
      <div class="fr"><i style="background:linear-gradient(140deg,#8fb4ff,#5a7be8)">Я</i><span>Вы: продукты</span><em>−1 200 ₽</em></div>
      <div class="fr"><i style="background:linear-gradient(140deg,#8fe0b5,#2fb383)">М</i><span>Миша: кружок</span><em>−3 000 ₽</em></div></div>
    <div id="studio"><h3>Календарь</h3><div class="tabs"><span>Месяц</span><span>Дела</span><span class="on">Деньги</span></div>
      <p>На телефоне: «Мой день» → «Деньги»</p></div>
  </div>
  <div class="layer" id="L-led"><div id="led"><h4>Деньги</h4><small class="d">четверг, 29 октября</small>
    <div class="en old"><i>🚕</i><div><b>Такси</b><small>вчера</small></div><em class="minus">−380 ₽</em></div>
    <div class="en" id="e1"><i>🛒</i><div><b>Продукты</b><small>сегодня · голосом</small></div><em class="minus">−1 200 ₽</em></div>
    <div class="en" id="e2"><i>💼</i><div><b>Зарплата</b><small>сегодня · доход</small></div><em class="plus">+80 000 ₽</em></div>
  </div></div>
"""
JS = """
  layer("L-left", T, s("problem").start + 0.2, s("end").start);
  layer("L-led", T, s("say").start + 0.4, s("month").start);
  scene($("#mess"), T, s("problem").start + 0.3, s("say").start);
  [...$("#rc").children].forEach((c, i) => { const k = out((T - s("problem").start - 0.8 - i * 0.3) / 0.4); c.style.opacity = k * (1 - out((T - s("say").start + 0.4) / 0.4)); });
  scene($("#q1"), T, s("say").start + 0.2, s("income").start, 20);
  scene($("#q2"), T, s("income").start + 0.2, s("ask").start, 20);
  scene($("#q3"), T, s("ask").start + 0.2, s("month").start, 20);
  const row = (el, t0) => { const k = out((T - t0) / 0.45); el.style.opacity = k; el.style.transform = `translateY(${(1 - k) * 24}px) scale(${lerp(0.96, 1, k)})`; };
  row($("#e1"), at("s3a") + 2.2); row($("#e2"), at("s4a") + 2.4);
  scene($("#ans"), T, at("s5a") + 2.6, s("month").start);
  scene($("#mon"), T, s("month").start + 0.2, s("family").start);
  [...$("#mon").querySelectorAll(".bar i")].forEach((b, i) => { b.style.width = (parseFloat(b.dataset.w) * out((T - s("month").start - 0.8 - i * 0.25) / 0.9)) + "%"; });
  scene($("#fam"), T, s("family").start + 0.2, s("how").start);
  [...$("#fam").querySelectorAll(".fr")].forEach((c, i) => vis(c, out((T - s("family").start - 0.7 - i * 0.45) / 0.4), 12));
  scene($("#studio"), T, s("how").start + 0.2, s("end").start);
"""
