TITLE = "Урок 10 · Почта голосом"
IDEA = "Главная вещь урока — ящик справа: сто писем, рассылки сворачиваются в одну строку, наверху остаются письма от людей."
H1 = "Почта голосом"
TAG = "Важное — сразу, рассылки — одной строкой"
NEXT = "Следующий урок — «Дела по расписанию»"
ICON = '<svg viewBox="0 0 24 24"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 7l9 6 9-6"/></svg>'
SCENES = ["title", "problem", "new", "read", "reply", "boxes", "how", "end"]
CSS = """
#plane svg { stroke: var(--accent); }
#box { position: absolute; left: 1330px; top: 140px; width: 520px; height: 700px; border-radius: 36px; background: var(--bg); box-shadow: var(--raise); padding: 26px 22px; overflow: hidden; }
#box h4 { font: 600 24px Unbounded; display: flex; justify-content: space-between; padding: 0 8px 14px; } #box h4 em { font-style: normal; color: var(--accent); }
.ml { display: flex; gap: 12px; align-items: center; padding: 12px 10px; border-radius: 16px; overflow: hidden; }
.ml i { width: 42px; height: 42px; border-radius: 50%; flex: none; display: grid; place-items: center; font: 700 16px Unbounded; font-style: normal; color: #fff; background: #b9c4d4; }
.ml.p i { background: linear-gradient(140deg, #8fb4ff, #5a7be8); } .ml.p.o i { background: linear-gradient(140deg, #ffcf7a, #e59a1f); } .ml.p.g i { background: linear-gradient(140deg, #8fe0b5, #2fb383); }
.ml div { min-width: 0; } .ml b { display: block; font-size: 18px; white-space: nowrap; } .ml small { display: block; font-size: 15px; color: var(--mut); font-weight: 700; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.ml.n b { color: var(--mut); font-weight: 700; }
.ml.p { background: #fff; margin-bottom: 8px; box-shadow: 0 10px 22px -16px rgba(36,50,74,.5); }
#news { margin-top: 6px; padding: 14px 16px; border-radius: 16px; box-shadow: var(--press); font-size: 19px; font-weight: 800; color: var(--mut); }
#mess { position: absolute; left: 620px; top: 260px; width: 640px; padding: 34px 40px; border-radius: 34px; background: var(--bg); box-shadow: var(--raise); }
#mess small { font-size: 20px; color: var(--mut); font-weight: 800; } #mess b { display: block; font: 600 46px/1.25 Unbounded, sans-serif; margin-top: 12px; }
#q { position: absolute; left: 620px; top: 190px; max-width: 640px; padding: 20px 26px; border-radius: 26px 26px 8px 26px; background: var(--brand); color: #fff; font-size: 26px; font-weight: 700; }
#said { position: absolute; left: 620px; top: 300px; width: 660px; padding: 28px 32px; border-radius: 30px; background: var(--bg); box-shadow: var(--raise); }
#said div { font-size: 23px; font-weight: 700; padding: 10px 0; line-height: 1.35; } #said div b { color: var(--accent); }
#said small { display: block; margin-top: 10px; font-size: 19px; color: var(--mut); font-weight: 800; }
#letter { position: absolute; left: 620px; top: 300px; width: 660px; padding: 30px 34px; border-radius: 30px; background: #fff; box-shadow: 0 24px 50px -24px rgba(36,50,74,.45); }
#letter small { font-size: 18px; color: var(--mut); font-weight: 800; } #letter h4 { font: 600 26px Unbounded; margin: 6px 0 14px; }
#letter p { font-size: 20px; line-height: 1.5; color: var(--mut); font-weight: 600; }
#gist { position: absolute; left: 620px; top: 640px; width: 660px; padding: 18px 24px; border-radius: 22px; background: rgba(255,207,122,.35); font-size: 22px; font-weight: 800; }
#draft { position: absolute; left: 620px; top: 300px; width: 660px; padding: 28px 32px; border-radius: 30px; background: #fff; box-shadow: 0 24px 50px -24px rgba(36,50,74,.45); }
#draft div { font-size: 19px; color: var(--mut); font-weight: 800; padding: 4px 0; } #draft div b { color: var(--ink); }
#draft p { font-size: 22px; line-height: 1.5; font-weight: 600; margin-top: 14px; min-height: 100px; }
#confirm { position: absolute; left: 620px; top: 650px; width: 660px; display: flex; align-items: center; gap: 14px; padding: 18px 22px; border-radius: 24px; background: var(--bg); box-shadow: var(--raise-s); font-size: 22px; font-weight: 800; }
#confirm span { flex: 1; } #confirm b { padding: 12px 22px; border-radius: 14px; font-size: 20px; box-shadow: var(--raise-s); } #confirm b.y { color: #fff; background: var(--brand); box-shadow: none; }
#confirm b.ok { background: linear-gradient(135deg, #46d39a, #2fb383); }
#boxes { position: absolute; left: 620px; top: 250px; width: 680px; display: flex; gap: 20px; }
#boxes div { flex: 1; padding: 30px; border-radius: 30px; background: var(--bg); box-shadow: var(--raise); }
#boxes i { font-size: 50px; font-style: normal; } #boxes b { display: block; font: 600 26px Unbounded; margin-top: 10px; } #boxes small { font-size: 20px; color: var(--mut); font-weight: 700; }
#bq { position: absolute; left: 620px; top: 540px; display: flex; flex-direction: column; gap: 14px; }
#bq span { padding: 14px 24px; border-radius: 99px; background: var(--bg); box-shadow: var(--raise-s); font-size: 22px; font-weight: 800; align-self: flex-start; }
#studio { position: absolute; left: 620px; top: 210px; width: 700px; border-radius: 32px; background: var(--bg); box-shadow: var(--raise); padding: 30px 34px; }
#studio h3 { font: 700 30px Unbounded; margin-bottom: 20px; }
#studio .row { display: flex; gap: 12px; flex-wrap: wrap; } #studio .row span { padding: 14px 22px; border-radius: 16px; box-shadow: var(--raise-s); font-size: 21px; font-weight: 800; }
#studio .row span.on { color: #fff; background: var(--brand); box-shadow: none; }
#studio .more { margin-top: 22px; font-size: 21px; font-weight: 800; color: var(--accent); }
"""
NEWS = ["Скидки недели — до −40%", "Ваш заказ передан в доставку", "Дайджест: 10 статей", "Вебинар завтра в 19:00", "Новая коллекция осени",
        "Бонусы сгорают через 3 дня", "Подборка для вас", "Обновление условий"]
HTML = """
  <div class="layer" id="L-box"><div id="box"><h4>Входящие <em id="cnt">100</em></h4>
    <div class="ml p" id="m1"><i>ОМ</i><div><b>Ольга Миронова</b><small>Договор на подпись</small></div></div>
    <div class="ml p o" id="m2"><i>СК</i><div><b>Сергей Ким</b><small>Переносим встречу?</small></div></div>
    <div class="ml p g" id="m3"><i>АН</i><div><b>Анна, бухгалтер</b><small>Счёт оплачен</small></div></div>
    <div id="nl">""" + "".join(f'<div class="ml n"><i>✉</i><div><b>Рассылка</b><small>{t}</small></div></div>' for t in NEWS) + """</div>
    <div id="news">🗞 27 рассылок — по запросу</div></div></div>
  <div class="layer" id="L-left">
    <div id="mess"><small>ВХОДЯЩИЕ</small><b>100 писем.<br>Где важное?</b></div>
    <div id="q">Что нового в почте?</div>
    <div id="said"><div><b>Ольга</b> прислала договор на подпись.</div><div><b>Сергей</b> просит перенести встречу.</div><div><b>Анна</b>: счёт оплачен.</div><small>И 27 рассылок.</small></div>
    <div id="letter"><small>ОЛЬГА МИРОНОВА</small><h4>Договор на подпись</h4><p>Добрый день! Высылаю договор. Внесла правки в пункт 3 — про сроки оплаты. Подпишите, пожалуйста, до пятницы…</p></div>
    <div id="gist">Главное: подписать до пятницы, правки — в п. 3.</div>
    <div id="draft"><div>Кому: <b>Ольга Миронова</b></div><div>Тема: <b>Re: Договор на подпись</b></div><p id="dt"></p></div>
    <div id="confirm"><span>Отправить письмо?</span><b>Нет</b><b class="y" id="yes">Да</b></div>
    <div id="boxes"><div><i>💼</i><b>Рабочий</b><small>3 новых</small></div><div><i>🏠</i><b>Личный</b><small>1 новое</small></div></div>
    <div id="bq"><span>«Что нового в почте?» — по всем</span><span>«Что в рабочей почте?» — по одному</span></div>
    <div id="studio"><h3>Подключение → Почта</h3><div class="row"><span class="on">Яндекс</span><span>Mail.ru</span><span>Gmail</span><span>Другая</span></div><div class="more">+ Ещё ящик</div></div>
  </div>
"""
JS = """
  layer("L-left", T, s("problem").start + 0.2, s("end").start);
  layer("L-box", T, s("problem").start + 0.4, s("boxes").start);
  scene($("#mess"), T, at("s2a") + 0.3, s("new").start);
  const fold = out((T - at("s3a") - 1.2) / 0.9);
  [...$("#nl").children].forEach((c) => { c.style.maxHeight = (66 * (1 - fold)) + "px"; c.style.opacity = 1 - fold; c.style.paddingTop = c.style.paddingBottom = (12 * (1 - fold)) + "px"; });
  vis($("#news"), fold, 10);
  for (const [i, id] of [[0, "#m1"], [1, "#m2"], [2, "#m3"]]) { const el = $(id); el.style.background = fold > 0.5 ? "#fff" : "transparent"; el.style.boxShadow = fold > 0.5 ? "" : "none"; }
  $("#cnt").textContent = fold > 0.5 ? "3 от людей" : "100";
  scene($("#q"), T, s("new").start + 0.2, s("read").start, 20);
  scene($("#said"), T, at("s3a") + 1.8, s("read").start);
  [...$("#said").children].forEach((c, i) => vis(c, out((T - at("s3a") - 2.0 - i * 0.45) / 0.4), 12));
  scene($("#letter"), T, s("read").start + 0.2, s("reply").start);
  scene($("#gist"), T, at("s4a") + 2.2, s("reply").start, 16);
  $("#m1").style.transform = T > s("read").start && T < s("reply").start ? "scale(1.04)" : "";
  scene($("#draft"), T, s("reply").start + 0.2, s("boxes").start);
  $("#dt").textContent = type("Ольга, добрый день! Договорились: в четверг в 10:00. Договор подпишу до пятницы.", (T - at("s5a") - 0.8) / 2.2);
  scene($("#confirm"), T, at("s5b") + 0.2, s("boxes").start, 16);
  const sent = T > at("s5b") + 2.6; $("#yes").classList.toggle("ok", sent); $("#yes").textContent = sent ? "Отправлено ✓" : "Да";
  scene($("#boxes"), T, s("boxes").start + 0.2, s("how").start);
  scene($("#bq"), T, s("boxes").start + 1.2, s("how").start, 16);
  scene($("#studio"), T, s("how").start + 0.2, s("end").start);
"""
