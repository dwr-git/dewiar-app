TITLE = "Урок 11 · Дела по расписанию"
IDEA = "Главная вещь урока — день по часам: Лира сама делает дело в срок, и в Telegram приходит только результат, строками со смайликами."
H1 = "Дела по расписанию"
TAG = "Курс, почта, новости — приходят сами"
NEXT = "Следующий урок — «Утро с Лирой»"
ICON = '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/></svg>'
SCENES = ["title", "problem", "ask", "hourly", "quiet", "where", "how", "end"]
CSS = """
#plane svg { stroke: var(--accent); }
#t-title h1 { font-size: 100px; }
#phone { position: absolute; left: 1380px; top: 120px; width: 440px; height: 740px; border-radius: 60px; background: var(--bg); box-shadow: var(--raise); padding: 22px; }
#phone .scr { width: 100%; height: 100%; border-radius: 44px; background: #e6edf5; overflow: hidden; display: flex; flex-direction: column; }
#phone header { display: flex; align-items: center; gap: 12px; padding: 18px; background: #fff; }
#phone header img { width: 46px; height: 46px; border-radius: 50%; object-fit: cover; }
#phone header b { display: block; font-size: 20px; } #phone header small { font-size: 15px; color: #7a7f8c; font-weight: 700; }
#chat { flex: 1; min-height: 0; padding: 14px; display: flex; flex-direction: column; justify-content: flex-end; gap: 12px; overflow: hidden; }
.msg { align-self: flex-start; max-width: 92%; background: #fff; border-radius: 18px 18px 18px 6px; padding: 12px 16px 8px; font-size: 18px; line-height: 1.5; font-weight: 600; box-shadow: 0 6px 14px -10px rgba(36,50,74,.4); flex: none; }
.msg small { display: block; text-align: right; font-size: 13px; color: #8a8f9c; font-weight: 700; margin-top: 4px; }
#mess { position: absolute; left: 620px; top: 240px; width: 680px; padding: 34px 40px; border-radius: 34px; background: var(--bg); box-shadow: var(--raise); }
#mess small { font-size: 20px; color: var(--mut); font-weight: 800; }
#mess div { display: flex; gap: 14px; margin-top: 18px; } #mess div span { padding: 14px 20px; border-radius: 18px; box-shadow: var(--raise-s); font-size: 24px; font-weight: 800; }
#mess b { display: block; font: 600 40px Unbounded; margin-top: 24px; color: #b04a5c; }
#q { position: absolute; left: 620px; top: 190px; max-width: 700px; padding: 20px 26px; border-radius: 26px 26px 8px 26px; background: var(--brand); color: #fff; font-size: 25px; font-weight: 700; line-height: 1.35; }
#job { position: absolute; left: 620px; top: 400px; width: 680px; padding: 28px 32px; border-radius: 30px; background: var(--bg); box-shadow: var(--raise); }
#job small { font-size: 18px; font-weight: 800; color: var(--mut); } #job b { display: block; font: 600 28px/1.3 Unbounded; margin: 8px 0 16px; }
#job div { display: flex; gap: 10px; flex-wrap: wrap; } #job span { padding: 10px 16px; border-radius: 14px; background: rgba(69,96,234,.12); color: var(--accent); font-size: 19px; font-weight: 800; }
#job span.tg { background: rgba(42,171,238,.16); color: #1b86c0; }
#hours { position: absolute; left: 620px; top: 420px; width: 700px; display: grid; grid-template-columns: repeat(10, 1fr); gap: 8px; }
#hours span { padding: 20px 0 14px; border-radius: 18px; text-align: center; font-size: 22px; font-weight: 800; box-shadow: var(--raise-s); }
#hours span i { display: block; font-style: normal; font-size: 22px; margin-top: 6px; height: 28px; }
#hours span.now { color: #fff; background: var(--brand); box-shadow: none; }
#hours span.hit { color: #fff; background: linear-gradient(135deg, #ffcf7a, #e59a1f); box-shadow: none; }
#hours span.past { color: var(--mut); box-shadow: var(--press); }
#qh { top: 190px; }
#calm { position: absolute; left: 620px; top: 600px; width: 700px; display: flex; align-items: center; gap: 18px; padding: 22px 28px; border-radius: 26px; background: rgba(47,179,131,.13); font-size: 24px; font-weight: 800; color: #1e7d5b; }
#calm i { font-size: 40px; font-style: normal; }
#where { position: absolute; left: 620px; top: 280px; width: 1060px; display: flex; gap: 26px; }
#where div { flex: 1; padding: 46px 16px; border-radius: 30px; background: var(--bg); box-shadow: var(--raise); text-align: center; }
#where i { display: block; font-size: 76px; font-style: normal; } #where b { display: block; font: 600 32px Unbounded; margin-top: 16px; }
#studio { position: absolute; left: 620px; top: 200px; width: 700px; border-radius: 32px; background: var(--bg); box-shadow: var(--raise); padding: 30px 34px; }
#studio h3 { font: 700 30px Unbounded; margin-bottom: 18px; }
#studio .it { display: flex; align-items: center; gap: 16px; padding: 18px 20px; border-radius: 20px; box-shadow: var(--raise-s); margin-top: 14px; }
#studio .it i { font-size: 32px; font-style: normal; } #studio .it b { display: block; font-size: 22px; } #studio .it small { font-size: 18px; color: var(--mut); font-weight: 700; }
"""
HOURS = list(range(9, 19))
HTML = """
  <div class="layer" id="L-phone"><div id="phone"><div class="scr"><header><img src="../../../../data/avatars/lira.webp" alt=""><div><b>Лира</b><small>бот в Telegram</small></div></header>
    <div id="chat">
      <div class="msg" id="c1">💵 Доллар — 92,40 ₽ (+0,35)<br>💶 Евро — 99,10 ₽ (−0,12)<br>📈 За неделю доллар +1,2%<small>пн, 9:00</small></div>
      <div class="msg" id="c2">💵 Доллар — 92,55 ₽ (+0,15)<br>💶 Евро — 99,30 ₽ (+0,20)<small>вт, 9:00</small></div>
      <div class="msg" id="c3">📩 Ольга прислала договор<br>✍️ Подписать до пятницы<br>📎 Правки — в пункте 3<small>вт, 13:00</small></div>
    </div></div></div></div>
  <div class="layer" id="L-left">
    <div id="mess"><small>КАЖДОЕ УТРО — ВРУЧНУЮ</small><div><span>💵 курс</span><span>📩 почта</span><span>📰 новости</span></div><b>≈ 30 минут</b></div>
    <div id="q">«Каждый будний день в девять присылай курс доллара в Telegram»</div>
    <div id="job"><small>ДЕЛО ЗАВЕДЕНО</small><b>Прислать курс доллара</b><div><span>по будням в 9:00</span><span class="tg">→ Telegram</span></div></div>
    <div id="q2" class="qq">«По будням с 9 до 18 каждый час проверяй почту и пиши о важном»</div>
    <div id="hours">""" + "".join(f'<span>{h}<i></i></span>' for h in HOURS) + """</div>
    <div id="calm"><i>🔕</i>Нового нет — промолчу</div>
    <div id="where"><div><i>🔊</i><b>Голосом</b></div><div><i>✈️</i><b>Telegram</b></div><div><i>💬</i><b>MAX</b></div></div>
    <div id="studio"><h3>Дела и напоминания</h3>
      <div class="it"><i>💵</i><div><b>Прислать курс доллара</b><small>по будням в 9:00 · Telegram</small></div></div>
      <div class="it"><i>📩</i><div><b>Проверить почту, написать о важном</b><small>по будням с 9 до 18 каждый час · Telegram</small></div></div></div>
  </div>
"""
CSS += "#q2 { position: absolute; left: 620px; top: 190px; max-width: 700px; padding: 20px 26px; border-radius: 26px 26px 8px 26px; background: var(--brand); color: #fff; font-size: 25px; font-weight: 700; line-height: 1.35; }\n"
JS = """
  layer("L-left", T, s("problem").start + 0.2, s("end").start);
  layer("L-phone", T, s("ask").start + 0.4, s("where").start);
  scene($("#mess"), T, at("s2a") + 0.3, s("ask").start);
  [...$("#mess div").children].forEach((c, i) => vis(c, out((T - at("s2a") - 0.6 - i * 0.4) / 0.4), 12));
  scene($("#q"), T, s("ask").start + 0.2, s("hourly").start, 20);
  scene($("#job"), T, at("s3a") + 2.6, s("hourly").start);
  const post = (el, t0) => { const k = out((T - t0) / 0.5); el.style.display = T >= t0 ? "" : "none"; el.style.opacity = k; el.style.transform = `translateY(${(1 - k) * 30}px)`; };
  post($("#c1"), at("s3b") + 0.6); post($("#c2"), at("s3b") + 2.2);
  scene($("#q2"), T, s("hourly").start + 0.2, s("where").start, 20);
  scene($("#hours"), T, s("hourly").start + 0.6, s("where").start);
  const hk = Math.floor((T - at("s4a") - 1.0) / 0.55), hit = 4;
  [...$("#hours").children].forEach((c, i) => { const done = i < hk, now = i === hk;
    c.className = (now && i === hit) || (done && i === hit) ? "hit" : now ? "now" : done ? "past" : "";
    c.querySelector("i").textContent = done || now ? (i === hit ? "📩" : "·") : ""; });
  post($("#c3"), at("s4a") + 1.0 + hit * 0.55 + 0.3);
  scene($("#calm"), T, s("quiet").start + 0.2, s("where").start, 16);
  scene($("#where"), T, s("where").start + 0.2, s("how").start);
  [...$("#where").children].forEach((c, i) => vis(c, out((T - s("where").start - 0.4 - i * 0.35) / 0.4), 16, .9));
  scene($("#studio"), T, s("how").start + 0.2, s("end").start);
"""
