TITLE = "Урок 8 · Суфлёр на переговорах"
IDEA = "Главная вещь урока — окно созвона и узкая панель суфлёра справа: клиент спрашивает — подсказка пишется потоком, янтарная полоса растёт."
H1 = "Суфлёр"
TAG = "Подсказки на переговорах — видите только вы"
NEXT = "Следующий урок — «Ваши документы»"
ICON = '<svg viewBox="0 0 24 24"><path d="M4 5h16v11H9l-5 4z"/><path d="M8 9h8M8 12h5"/></svg>'
SCENES = ["title", "problem", "before", "listen", "hint", "hidden", "after", "how", "end"]
POS = {"hint": "{ lira: [300, 330, 220, 1], patrik: [300, 730, 200, 1] }"}
CSS = """
#plane svg { stroke: #e0a020; }
#mess { position: absolute; left: 620px; top: 260px; width: 700px; padding: 34px 40px; border-radius: 34px; background: var(--bg); box-shadow: var(--raise); }
#mess small { font-size: 20px; color: var(--mut); font-weight: 800; } #mess b { display: block; font: 600 44px/1.3 Unbounded, sans-serif; margin-top: 12px; }
#mess .dots { display: flex; gap: 10px; margin-top: 22px; } #mess .dots i { width: 16px; height: 16px; border-radius: 50%; background: var(--patrik); }
#prep { position: absolute; left: 620px; top: 190px; width: 720px; padding: 30px 34px; border-radius: 32px; background: var(--bg); box-shadow: var(--raise); }
#prep small { font-size: 18px; color: var(--mut); font-weight: 800; } #prep p { font-size: 28px; font-weight: 700; margin: 8px 0 20px; }
#prep .chips { display: flex; gap: 12px; } #prep .chips span { padding: 14px 20px; border-radius: 18px; box-shadow: var(--raise-s); font-size: 21px; font-weight: 800; }
#cheat { position: absolute; left: 620px; top: 500px; width: 720px; display: flex; flex-direction: column; gap: 12px; }
#cheat div { display: flex; gap: 16px; align-items: baseline; padding: 16px 22px; border-radius: 20px; background: rgba(255,181,71,.16); font-size: 22px; font-weight: 700; }
#cheat div em { font-style: normal; color: var(--mut); flex: none; width: 250px; }
#call { position: absolute; left: 600px; top: 150px; width: 880px; height: 600px; border-radius: 36px; background: var(--bg); box-shadow: var(--raise); padding: 24px; display: grid; grid-template-rows: 1fr auto; gap: 18px; }
#call .tiles { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }
#call .tile { position: relative; border-radius: 24px; background: linear-gradient(160deg, #3a4a66, #24324a); display: grid; place-items: center; overflow: hidden; }
#call .tile.me { background: linear-gradient(160deg, #46587a, #2c3a55); }
#call .tile i { width: 120px; height: 120px; border-radius: 50%; display: grid; place-items: center; font: 700 44px Unbounded; font-style: normal; color: #fff; background: linear-gradient(140deg, #8fb4ff, #5a7be8); }
#call .tile.me i { background: linear-gradient(140deg, #ffcf7a, #e59a1f); }
#call .tile span { position: absolute; left: 16px; bottom: 14px; color: #fff; font-size: 19px; font-weight: 800; padding: 6px 12px; border-radius: 10px; background: rgba(0,0,0,.28); }
#call .tile .wave { position: absolute; right: 16px; bottom: 16px; display: flex; gap: 4px; align-items: flex-end; height: 26px; }
#call .tile .wave b { width: 5px; border-radius: 3px; background: #7ee0b0; }
#call .bar { display: flex; justify-content: center; gap: 16px; } #call .bar span { width: 64px; height: 64px; border-radius: 50%; box-shadow: var(--raise-s); }
#call .bar span.red { background: #e2556b; box-shadow: none; }
#ask { position: absolute; left: 20px; top: 20px; padding: 14px 20px; border-radius: 18px 18px 18px 6px; background: #fff; font-size: 22px; font-weight: 800; color: var(--ink); box-shadow: 0 10px 24px -12px rgba(0,0,0,.5); white-space: nowrap; }
#share { position: absolute; left: 50%; top: 18px; transform: translateX(-50%); padding: 10px 18px; border-radius: 12px; background: #2fb383; color: #fff; font-size: 18px; font-weight: 800; white-space: nowrap; }
#pr { position: absolute; left: 1510px; top: 150px; width: 340px; height: 600px; border-radius: 32px; background: #fffaf0; box-shadow: var(--raise); padding: 26px 26px 26px 36px; overflow: hidden; }
#pr::before { content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 10px; background: rgba(224,160,32,.18); }
#pr .amb { position: absolute; left: 0; bottom: 0; width: 10px; background: #e0a020; }
#pr small { font-size: 16px; font-weight: 800; color: #a0781e; } #pr .st { all: unset; display: block; font-size: 20px; color: var(--mut); font-weight: 700; margin-top: 14px; }
#pr h4 { font: 700 30px/1.25 Unbounded; margin-top: 12px; min-height: 76px; }
#pr ul { list-style: none; margin-top: 16px; display: flex; flex-direction: column; gap: 10px; } #pr li { font-size: 19px; font-weight: 700; line-height: 1.35; }
#pr li::before { content: "• "; color: #e0a020; }
#pr .src { display: inline-block; margin-top: 16px; padding: 8px 14px; border-radius: 12px; background: rgba(224,160,32,.16); font-size: 16px; font-weight: 800; }
#pr .hid { position: absolute; left: 36px; right: 26px; bottom: 26px; padding: 12px 14px; border-radius: 14px; background: rgba(47,179,131,.16); font-size: 17px; font-weight: 800; color: #1e7d5b; }
#sum { position: absolute; left: 620px; top: 190px; width: 760px; padding: 32px 36px; border-radius: 32px; background: var(--bg); box-shadow: var(--raise); }
#sum h4 { font: 600 28px Unbounded; margin-bottom: 18px; }
#sum div { display: flex; gap: 14px; padding: 14px 0; font-size: 23px; font-weight: 700; } #sum div + div { box-shadow: 0 -1px 0 rgba(36,50,74,.08); }
#sum div em { font-style: normal; color: var(--mut); width: 190px; flex: none; }
#studio { position: absolute; left: 620px; top: 200px; width: 720px; border-radius: 32px; background: var(--bg); box-shadow: var(--raise); padding: 30px 34px; }
#studio h3 { font: 700 30px Unbounded; margin-bottom: 18px; }
#studio label { display: block; font-size: 17px; font-weight: 800; color: var(--mut); margin: 14px 0 8px; }
#studio .box { padding: 16px 18px; border-radius: 18px; box-shadow: var(--press); font-size: 21px; font-weight: 700; }
#studio .row { display: flex; gap: 10px; flex-wrap: wrap; } #studio .row span { padding: 12px 18px; border-radius: 14px; box-shadow: var(--raise-s); font-size: 19px; font-weight: 800; }
#studio .go { display: inline-block; margin-top: 22px; padding: 16px 26px; border-radius: 16px; color: #fff; background: var(--brand); font-size: 21px; font-weight: 800; }
#say { position: absolute; left: 620px; top: 690px; padding: 16px 26px; border-radius: 99px; background: var(--bg); box-shadow: var(--raise-s); font-size: 24px; font-weight: 800; }
"""
HTML = """
  <div class="layer" id="L-left">
    <div id="mess"><small>СОЗВОН С КЛИЕНТОМ · 14:00</small><b>«А скидку дадите?»</b><div class="dots"><i></i><i></i><i></i></div></div>
    <div id="prep"><small>ЦЕЛЬ ВСТРЕЧИ</small><p>Подписать договор на год</p><div class="chips"><span>📄 Прайс.pdf</span><span>📝 Договор.docx</span><span>📊 План.odt</span></div></div>
    <div id="cheat"><div><em>«Скидка?»</em>5% при оплате за год</div><div><em>«Сроки поставки?»</em>10 рабочих дней</div><div><em>«Гарантия?»</em>24 месяца, замена за 3 дня</div></div>
    <div id="sum"><h4>Итог встречи</h4><div><em>Договорились</em>договор на год, скидка 5%</div><div><em>Патрик</em>счёт до пятницы</div><div><em>Клиент</em>подпись до 15-го</div></div>
    <div id="studio"><h3>Суфлёр</h3><label>Цель</label><div class="box">Подписать договор на год</div><label>Материалы</label><div class="row"><span>Прайс.pdf</span><span>Договор.docx</span><span>+ Файл</span></div><span class="go">Начать встречу</span></div>
    <div id="say">или голосом: «Включи суфлёр»</div>
  </div>
  <div class="layer" id="L-call">
    <div id="call"><div class="tiles"><div class="tile" id="tc"><i>ОК</i><span>Клиент · ООО «Ока»</span><div class="wave" id="w1"></div><div id="ask">А скидку дадите?</div></div>
      <div class="tile me"><i>П</i><span>Вы</span><div class="wave" id="w2"></div></div></div>
      <div class="bar"><span></span><span></span><span class="red"></span></div><div id="share">● Вы показываете экран</div></div>
    <div id="pr"><i class="amb" id="amb"></i><small>СУФЛЁР</small><span class="st" id="prs">Слушаю…</span><h4 id="ph"></h4>
      <ul id="pl"><li>Скидка 5% — только при оплате за год</li><li>Помесячно — цена из прайса</li></ul><span class="src" id="psrc">📄 Прайс.pdf, стр. 2</span>
      <div class="hid" id="phid">👁 Собеседник это окно не видит</div></div>
  </div>
"""
JS = """
  layer("L-left", T, s("problem").start + 0.2, s("end").start);
  scene($("#mess"), T, at("s2a") + 0.3, s("before").start);
  scene($("#prep"), T, s("before").start + 0.2, s("listen").start);
  [...$("#prep .chips").children].forEach((c, i) => vis(c, out((T - at("s3a") - 1.2 - i * 0.35) / 0.4), 16));
  scene($("#cheat"), T, at("s3b") + 0.3, s("listen").start, 20);
  [...$("#cheat").children].forEach((c, i) => vis(c, out((T - at("s3b") - 0.6 - i * 0.5) / 0.4), 16));
  layer("L-call", T, s("listen").start + 0.1, s("after").start);
  const wv = (el, on, ph) => { if (!el.children.length) el.innerHTML = "<b></b>".repeat(5);
    [...el.children].forEach((b, i) => b.style.height = (on ? 6 + 18 * Math.abs(Math.sin(T * 7 + i * 1.3 + ph)) : 4) + "px"); };
  const asking = T > s("hint").start + 0.2 && T < at("s5a") + 1.6;
  wv($("#w1"), (T > s("listen").start && T < s("listen").start + 2.2) || asking, 0);
  wv($("#w2"), T > s("listen").start + 2.4 && T < s("hint").start, 2);
  vis($("#ask"), out((T - s("hint").start - 0.2) / 0.4) * (1 - out((T - s("hidden").start) / 0.4)), 14, .9);
  const k = clamp((T - at("s5a") - 0.8) / 2.6);
  $("#prs").textContent = T < s("hint").start + 0.4 ? "Слушаю…" : k < 1 ? "Пишу подсказку…" : "Готово";
  $("#ph").textContent = type("5% — при оплате за год", k * 1.4);
  [...$("#pl").children].forEach((c, i) => vis(c, out((k - 0.55 - i * 0.18) / 0.15), 10));
  vis($("#psrc"), out((k - 0.9) / 0.1), 10);
  $("#amb").style.height = (k * 100) + "%";
  vis($("#share"), out((T - s("hidden").start - 0.2) / 0.4), -10);
  vis($("#phid"), out((T - s("hidden").start - 0.8) / 0.4), 14);
  scene($("#sum"), T, s("after").start + 0.2, s("how").start);
  [...$("#sum").querySelectorAll("div")].forEach((c, i) => vis(c, out((T - s("after").start - 0.8 - i * 0.5) / 0.4), 12));
  scene($("#studio"), T, s("how").start + 0.2, s("end").start);
  scene($("#say"), T, at("s8a") + 2.2, s("end").start, 16);
"""
