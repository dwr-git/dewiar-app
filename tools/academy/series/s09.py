TITLE = "Урок 9 · Мои файлы"
IDEA = "Главная вещь урока — стена файлов справа: файлы ложатся в «Облако Лиры», и на вопрос загорается ровно тот файл, из которого ответ; потом те же файлы — на всех устройствах (1.0.23)."
H1 = "Мои файлы"
TAG = "Положите файл в облако и спросите — отвечу и покажу, откуда"
NEXT = "Следующий урок — «Почта голосом»"
ICON = '<svg viewBox="0 0 24 24"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="M8 13h8"/></svg>'
SCENES = ["title", "problem", "add", "ask", "private", "phone", "how", "end"]
CSS = """
#plane svg { stroke: var(--accent); }
#mess { position: absolute; left: 620px; top: 260px; width: 660px; padding: 34px 40px; border-radius: 34px; background: var(--bg); box-shadow: var(--raise); }
#mess small { font-size: 20px; color: var(--mut); font-weight: 800; } #mess b { display: block; font: 600 40px/1.3 Unbounded, sans-serif; margin-top: 12px; }
#wall { position: absolute; left: 1350px; top: 150px; width: 500px; display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; }
.fl { height: 112px; border-radius: 18px; background: var(--bg); box-shadow: var(--raise-s); padding: 14px 12px; display: flex; flex-direction: column; justify-content: space-between; }
.fl i { width: 34px; height: 40px; border-radius: 6px 12px 6px 6px; background: #c9d4e4; font-style: normal; }
.fl.pdf i { background: #f0a3a3; } .fl.doc i { background: #9fb8f5; } .fl.xls i { background: #94d9b4; }
.fl span { font-size: 13px; font-weight: 800; color: var(--mut); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.fl.hit { background: #fff; box-shadow: 0 0 0 0 transparent, 0 20px 40px -18px rgba(69,96,234,.55); transform: scale(1.12); }
.fl.hit span { color: var(--accent); }
/* «Облако Лиры» (1.0.23): тот же градиент облака, что в студии и блокноте */
#cloud { position: absolute; left: 620px; top: 190px; width: 700px; padding: 30px 34px; border-radius: 34px; background: var(--bg); box-shadow: var(--raise); }
.ch { display: flex; align-items: center; gap: 18px; } .ch svg { width: 66px; height: 66px; flex: none; }
.ch b { display: block; font: 700 30px Unbounded; } .ch small { display: block; font-size: 19px; font-weight: 700; color: var(--mut); margin-top: 4px; }
.ch .mt { margin-left: auto; text-align: right; font-size: 18px; font-weight: 800; color: var(--mut); white-space: nowrap; } .ch .mt em { display: block; font: 600 26px Unbounded; font-style: normal; color: var(--ink); }
#drop { margin-top: 24px; height: 128px; border-radius: 24px; border: 3px dashed rgba(69,96,234,.35); display: grid; place-items: center; font-size: 24px; font-weight: 800; color: var(--accent); transition: none; }
#drop.over { background: rgba(69,96,234,.08); border-color: var(--accent); }
#tiles { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin-top: 18px; }
.tl { padding: 13px 14px; border-radius: 16px; box-shadow: var(--raise-s); display: flex; align-items: center; gap: 10px; min-width: 0; }
.tl i { width: 26px; height: 32px; flex: none; border-radius: 5px 10px 5px 5px; background: #f0a3a3; } .tl.doc i { background: #9fb8f5; } .tl.xls i { background: #94d9b4; }
.tl span { font-size: 15px; font-weight: 800; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.tl b { width: 9px; height: 9px; flex: none; border-radius: 50%; background: #2fb383; margin-left: auto; }
.fly { position: absolute; z-index: 5; width: 120px; padding: 12px; border-radius: 16px; background: #fff; box-shadow: 0 18px 30px -14px rgba(36,50,74,.45); display: flex; align-items: center; gap: 8px; font-size: 13px; font-weight: 800; }
.fly i { width: 24px; height: 30px; flex: none; border-radius: 5px 9px 5px 5px; background: #f0a3a3; } .fly.doc i { background: #9fb8f5; } .fly.xls i { background: #94d9b4; }
#q { position: absolute; left: 620px; top: 190px; max-width: 680px; padding: 22px 28px; border-radius: 26px 26px 8px 26px; background: var(--brand); color: #fff; font-size: 26px; font-weight: 700; }
#ans { position: absolute; left: 620px; top: 330px; width: 680px; padding: 28px 32px; border-radius: 30px; background: var(--bg); box-shadow: var(--raise); }
#ans p { font-size: 26px; font-weight: 700; line-height: 1.45; } #ans mark { background: rgba(255,207,122,.55); border-radius: 6px; padding: 0 4px; color: inherit; }
#ans span { display: inline-block; margin-top: 18px; padding: 10px 16px; border-radius: 14px; background: rgba(69,96,234,.12); color: var(--accent); font-size: 19px; font-weight: 800; }
#priv { position: absolute; left: 620px; top: 200px; width: 1100px; display: grid; grid-template-columns: 1fr 260px 1fr; align-items: center; }
#priv .box { padding: 40px 28px; border-radius: 30px; background: var(--bg); box-shadow: var(--raise); text-align: center; }
#priv .box i { display: block; font-size: 80px; font-style: normal; } #priv .box b { display: block; font: 600 30px Unbounded; margin-top: 10px; }
#priv .box small { display: block; font-size: 21px; color: var(--mut); font-weight: 700; margin-top: 6px; }
#priv .ar { position: relative; height: 4px; background: repeating-linear-gradient(90deg, var(--nd) 0 10px, transparent 10px 18px); }
#priv .ar em { position: absolute; left: 0; top: -24px; padding: 10px 14px; border-radius: 12px; background: rgba(255,207,122,.6); font-style: normal; font-size: 19px; font-weight: 800; white-space: nowrap; }
#lock { position: absolute; left: 620px; top: 160px; width: 1180px; display: grid; grid-template-columns: 1fr 300px; gap: 40px; align-items: center; }
#lock .cl { padding: 26px 30px; border-radius: 32px; background: var(--bg); box-shadow: var(--raise); }
#lock .gib { margin-top: 18px; padding: 16px 18px; border-radius: 18px; box-shadow: var(--press); font: 600 20px/1.5 "JetBrains Mono", monospace; color: var(--mut); letter-spacing: .04em; word-break: break-all; height: 96px; overflow: hidden; }
#lock .keys { display: flex; flex-direction: column; gap: 14px; } #lock .keys span { display: flex; align-items: center; gap: 14px; padding: 16px 20px; border-radius: 20px; background: var(--bg); box-shadow: var(--raise-s); font-size: 21px; font-weight: 800; }
#lock .keys span i { font-style: normal; font-size: 28px; } #lock .keys span em { margin-left: auto; font-style: normal; font-size: 24px; }
#priv { top: 560px; }
#devs { position: absolute; left: 620px; top: 170px; width: 1220px; height: 660px; }
.dv { position: absolute; padding: 18px 20px 22px; border-radius: 30px; background: var(--bg); box-shadow: var(--raise); }
.dv h5 { display: flex; align-items: center; gap: 12px; font: 700 22px Unbounded; } .dv h5 i { font-style: normal; font-size: 30px; } .dv h5 small { margin-left: auto; font: 800 15px Manrope, sans-serif; color: #1e7d5b; }
.dv .tl { margin-top: 12px; background: var(--bg); }
#d-home { left: 0; top: 0; width: 440px; } #d-work { left: 0; top: 330px; width: 440px; }
#phone { position: absolute; left: 760px; top: -30px; width: 400px; height: 700px; border-radius: 58px; background: var(--bg); box-shadow: var(--raise); padding: 20px; }
#phone .scr { width: 100%; height: 100%; border-radius: 42px; background: #eef2f8; padding: 30px 20px; display: flex; flex-direction: column; gap: 12px; overflow: hidden; }
#phone h6 { font: 700 24px Unbounded; margin: 6px 4px 6px; }
#phone .chp { display: flex; gap: 8px; } #phone .chp span { padding: 9px 15px; border-radius: 99px; background: #fff; font-size: 15px; font-weight: 800; color: var(--mut); }
#phone .chp span.on { color: #fff; background: var(--brand); }
#phone .tl { background: #fff; box-shadow: none; }
#sync { position: absolute; left: 470px; top: 300px; width: 270px; height: 4px; background: repeating-linear-gradient(90deg, var(--accent) 0 10px, transparent 10px 18px); background-size: 36px 4px; }
#studio { position: absolute; left: 620px; top: 190px; width: 700px; border-radius: 32px; background: var(--bg); box-shadow: var(--raise); padding: 28px 32px; }
#studio .crumb { font-size: 19px; font-weight: 800; color: var(--mut); margin-bottom: 16px; } #studio .crumb b { color: var(--accent); }
#studio #drop2 { margin-top: 18px; height: 92px; border-radius: 20px; border: 3px dashed rgba(69,96,234,.35); display: grid; place-items: center; font-size: 21px; font-weight: 800; color: var(--accent); }
#pad { position: absolute; left: 1360px; top: 300px; width: 500px; padding: 20px 20px 26px; border-radius: 32px; background: var(--bg); box-shadow: var(--raise); }
#pad .top { display: flex; align-items: center; gap: 6px; }
#pad .tab { display: flex; align-items: center; gap: 9px; padding: 9px 14px; border-radius: 14px; font-size: 20px; font-weight: 700; color: var(--mut); white-space: nowrap; }
#pad .tab.on { background: #fff; color: var(--ink); box-shadow: var(--raise-s); }
#pad .tab .dt { width: 9px; height: 9px; border-radius: 50%; background: #9aa6ba; }
#pad .cl { width: 46px; justify-content: center; padding: 8px 0; margin-left: -4px; color: var(--accent); box-shadow: 0 0 0 3px rgba(69,96,234,var(--rg,0)); }
#pad .cl svg { width: 26px; height: 26px; fill: none; stroke: currentColor; stroke-width: 1.7; stroke-linecap: round; stroke-linejoin: round; }
#pad .lines { margin-top: 22px; display: flex; flex-direction: column; gap: 12px; } #pad .lines i { height: 12px; border-radius: 6px; background: rgba(36,50,74,.1); }
#pad p { margin-top: 18px; font-size: 20px; font-weight: 800; color: var(--accent); text-align: center; }
"""
FILES = [("pdf", "Договор_Ромашка_2026.pdf"), ("doc", "Инструкция_склад.docx"), ("xls", "Прайс_октябрь.xlsx"), ("pdf", "Договор_Ока.pdf"),
         ("doc", "Регламент_отпусков.docx"), ("pdf", "Сертификат_ГОСТ.pdf"), ("xls", "Остатки.xlsx"), ("doc", "Письмо_поставщику.docx"),
         ("pdf", "Договор_Вектор.pdf"), ("xls", "Прайс_сентябрь.xlsx"), ("doc", "Памятка_новичку.docx"), ("pdf", "Счёт_4471.pdf"),
         ("doc", "Протокол_встречи.docx"), ("pdf", "Договор_Ромашка_2025.pdf"), ("xls", "Бюджет_2026.xlsx"), ("doc", "Оферта.docx"),
         ("pdf", "Акт_сверки.pdf"), ("doc", "Устав.docx"), ("xls", "Клиенты.xlsx"), ("pdf", "Лицензия.pdf")]
HTML = """
  <div class="layer" id="L-wall"><div id="wall">""" + "".join(f'<div class="fl {k}"><i></i><span>{n}</span></div>' for k, n in FILES) + """</div></div>
  <div class="layer" id="L-left">
    <div id="mess"><small>СРОК ПОСТАВКИ ПО «РОМАШКЕ»</small><b>Где-то в договоре…<br>в одном из сорока файлов</b></div>
    <div id="cloud"><div class="ch"><svg viewBox="0 0 48 48"><defs><linearGradient id="cg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#8fd3ff"/><stop offset=".55" stop-color="#8b8cf7"/><stop offset="1" stop-color="#c58cf7"/></linearGradient></defs><path d="M14.5 37h20a8.5 8.5 0 0 0 1.3-16.9A11.5 11.5 0 0 0 13.6 18 9.5 9.5 0 0 0 14.5 37z" fill="url(#cg)"/><path d="M24 31v-9m-4 3.6 4-4 4 4" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg><div><b>Облако Лиры</b><small>на всех ваших устройствах</small></div><div class="mt"><em id="mb">0 МБ</em>из 200 МБ</div></div>
      <div id="drop">Перетащите файлы сюда</div><div id="tiles"><div class="tl t0"><i></i><span>Договор_Ромашка_2026.pdf</span><b></b></div><div class="tl doc t1"><i></i><span>Инструкция_склад.docx</span><b></b></div><div class="tl xls t2"><i></i><span>Прайс_октябрь.xlsx</span><b></b></div></div></div>
    <div class="fly f0"><i></i>Договор…</div><div class="fly doc f1"><i></i>Инструкция…</div><div class="fly xls f2"><i></i>Прайс…</div>
    <div id="q">Что в договоре с Ромашкой про сроки?</div>
    <div id="ans"><p>Поставка — <mark>в течение 14 рабочих дней после оплаты</mark>. Задержка — пеня 0,1% в день.</p><span>📄 Договор_Ромашка_2026.pdf · п. 4.2</span></div>
    <div id="lock"><div class="cl"><div class="ch"><svg viewBox="0 0 48 48"><defs><linearGradient id="cg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#8fd3ff"/><stop offset=".55" stop-color="#8b8cf7"/><stop offset="1" stop-color="#c58cf7"/></linearGradient></defs><path d="M14.5 37h20a8.5 8.5 0 0 0 1.3-16.9A11.5 11.5 0 0 0 13.6 18 9.5 9.5 0 0 0 14.5 37z" fill="url(#cg)"/><path d="M24 31v-9m-4 3.6 4-4 4 4" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg><div><b>Облако Лиры</b><small>сервер хранит только шифр</small></div><div class="mt"><em>🔒</em></div></div>
      <div class="gib" id="gib"></div></div>
      <div class="keys"><span><i>💻</i>Дом<em>🔑</em></span><span><i>💼</i>Работа<em>🔑</em></span><span><i>📱</i>Телефон<em>🔑</em></span></div></div>
    <div id="priv"><div class="box"><i>💻</i><b>Ваше устройство</b><small>поиск — здесь</small></div><div class="ar"><em id="frag">отрывок</em></div><div class="box"><i>🧠</i><b>Модель</b><small>видит только найденное</small></div></div>
    <div id="devs"><div class="dv" id="d-home"><h5><i>💻</i>Дома<small>✓ на месте</small></h5><div class="tl"><i></i><span>Договор_Ромашка_2026.pdf</span><b></b></div><div class="tl doc"><i></i><span>Инструкция_склад.docx</span><b></b></div><div class="tl xls"><i></i><span>Прайс_октябрь.xlsx</span><b></b></div></div>
      <div class="dv" id="d-work"><h5><i>💼</i>На работе<small>✓ на месте</small></h5><div class="tl"><i></i><span>Договор_Ромашка_2026.pdf</span><b></b></div><div class="tl doc"><i></i><span>Инструкция_склад.docx</span><b></b></div><div class="tl xls"><i></i><span>Прайс_октябрь.xlsx</span><b></b></div></div><i id="sync"></i>
      <div id="phone"><div class="scr"><h6>Заметки</h6><div class="chp"><span>Все</span><span>Работа</span><span class="on">Мои файлы</span></div><div class="tl"><i></i><span>Договор_Ромашка_2026.pdf</span><b></b></div><div class="tl doc"><i></i><span>Инструкция_склад.docx</span><b></b></div><div class="tl xls"><i></i><span>Прайс_октябрь.xlsx</span><b></b></div></div></div></div>
    <div id="studio"><div class="crumb">Студия · <b>Мои файлы</b></div><div class="ch"><svg viewBox="0 0 48 48"><defs><linearGradient id="cg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#8fd3ff"/><stop offset=".55" stop-color="#8b8cf7"/><stop offset="1" stop-color="#c58cf7"/></linearGradient></defs><path d="M14.5 37h20a8.5 8.5 0 0 0 1.3-16.9A11.5 11.5 0 0 0 13.6 18 9.5 9.5 0 0 0 14.5 37z" fill="url(#cg)"/><path d="M24 31v-9m-4 3.6 4-4 4 4" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg><div><b>Облако Лиры</b><small>Ваши файлы — на всех ваших устройствах</small></div><div class="mt"><em>12 МБ</em>из 200 МБ</div></div>
      <div id="drop2">Перетащите файлы сюда</div><div id="tiles2" style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-top:16px"><div class="tl"><i></i><span>Договор_Ромашка_2026.pdf</span><b></b></div><div class="tl doc"><i></i><span>Инструкция_склад.docx</span><b></b></div><div class="tl xls"><i></i><span>Прайс_октябрь.xlsx</span><b></b></div></div></div>
    <div id="pad"><div class="top"><span class="tab"><i class="dt"></i>Пульт</span><span class="tab cl"><svg viewBox="0 0 24 24"><path d="M7 18.5h10a4 4 0 0 0 .6-7.95A5.5 5.5 0 0 0 7 9.6a4.5 4.5 0 0 0 0 8.9z"/><path d="M12 16v-5m-2.2 2.1L12 10.9l2.2 2.2"/></svg></span><span class="tab on">Главное</span><span class="tab">Работа</span></div>
      <div class="lines"><i style="width:80%"></i><i style="width:64%"></i><i style="width:72%"></i></div><p>Блокнот у виджета</p></div>
  </div>
"""
JS = """
  layer("L-left", T, s("problem").start + 0.2, s("end").start);
  layer("L-wall", T, s("problem").start + 0.4, s("private").start);
  const fl = [...$("#wall").children];
  fl.forEach((c, i) => { const k = out((T - s("problem").start - 0.5 - i * 0.05) / 0.4); c.style.opacity = k; });
  scene($("#mess"), T, at("s2a") + 0.3, s("add").start);
  // «добавить»: три файла со стены летят в облако — плитки, место растёт
  scene($("#cloud"), T, s("add").start + 0.2, s("ask").start);
  const ad = s("add").start;
  const FROM = [[1360, 160], [1490, 300], [1620, 440]], TO = [700, 360];
  [0, 1, 2].forEach(k => { const f = $(".f" + k), t0 = ad + 1.0 + k * 0.55, q = clamp((T - t0) / 0.9), live = T > t0 && T < t0 + 1.0 && T < s("ask").start;
    f.style.opacity = live ? 1 : 0; const e = ease(q);
    f.style.transform = `translate(${lerp(FROM[k][0], TO[0] + k * 40, e)}px, ${lerp(FROM[k][1], TO[1], e) - Math.sin(e * Math.PI) * 70}px) rotate(${(1 - e) * (k - 1) * 8}deg) scale(${1 - e * 0.15})`;
    vis($(".t" + k), out((T - t0 - 0.9) / 0.3), 10); });
  $("#drop").classList.toggle("over", T > ad + 1.0 && T < ad + 3.2);
  $("#mb").textContent = (T < ad + 1.9 ? "0" : T < ad + 2.4 ? "4" : T < ad + 3.0 ? "7" : "12") + " МБ";
  scene($("#q"), T, s("ask").start + 0.2, s("private").start, 20);
  scene($("#ans"), T, at("s4b") - 0.4, s("private").start);
  const hit = T > at("s4b") - 0.2 && T < s("private").start;
  fl[0].classList.toggle("hit", hit); fl.forEach((c, i) => { if (i && hit) c.style.opacity = 0.45; });
  // «где ищу»: в облаке — только шифр, ключи у своих устройств; модели — только отрывок
  scene($("#lock"), T, s("private").start + 0.2, s("phone").start);
  const G = "a9F2kQ7xLm0vRt8ZpW3nYc6HdJ1sUe4BgK5oTi9MqXr2VbNf7Ly0Cz3PwAh8Sj6DuEk1Og4Iv5";
  $("#gib").textContent = Array.from({ length: 120 }, (_, n) => G[(n * 7 + Math.floor(T * 9)) % G.length]).join("");
  scene($("#priv"), T, at("s5b") - 0.2, s("phone").start);
  $("#frag").style.left = (clamp((T - at("s5b") - 0.6) / 2.2) * 62) + "%";
  // «на всех устройствах»: дома, на работе, в телефоне — в «Заметках» папка «Мои файлы»
  scene($("#devs"), T, s("phone").start + 0.2, s("how").start);
  [["#d-home", 0.3], ["#d-work", 0.9], ["#phone", 1.5]].forEach(([q, d]) => vis($(q), out((T - s("phone").start - d) / 0.4), 16));
  $("#sync").style.backgroundPosition = `${(T * 60) % 36}px 0`; $("#sync").style.opacity = out((T - s("phone").start - 1.0) / 0.4);
  scene($("#studio"), T, s("how").start + 0.2, s("end").start);
  scene($("#pad"), T, s("how").start + 2.6, s("end").start, 16);
  const rg = T - s("how").start - 3.2; $("#pad .cl").style.setProperty("--rg", rg > 0 ? (0.35 + 0.65 * Math.abs(Math.sin(rg * 2.4))).toFixed(2) : 0);
"""
