TITLE = "Урок 9 · Ваши документы"
IDEA = "Главная вещь урока — стена файлов справа: Лира прочитала папку, и на вопрос загорается ровно тот файл, из которого ответ."
H1 = "Ваши документы"
TAG = "Спросите — найду в ваших папках и покажу файл"
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
#folder { position: absolute; left: 620px; top: 230px; width: 680px; padding: 32px 36px; border-radius: 32px; background: var(--bg); box-shadow: var(--raise); }
#folder .h { display: flex; align-items: center; gap: 18px; } #folder .h i { font-size: 54px; font-style: normal; }
#folder b { display: block; font: 600 30px Unbounded; } #folder small { font-size: 20px; color: var(--mut); font-weight: 700; }
#folder .pb { height: 14px; border-radius: 99px; box-shadow: var(--press); margin-top: 24px; overflow: hidden; } #folder .pb i { display: block; height: 100%; border-radius: 99px; background: var(--brand); }
#folder p { font-size: 22px; font-weight: 800; margin-top: 16px; }
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
#nope { position: absolute; left: 620px; top: 560px; display: flex; gap: 14px; width: 700px; flex-wrap: wrap; }
#nope span { padding: 14px 22px; border-radius: 99px; background: var(--bg); box-shadow: var(--raise-s); font-size: 22px; font-weight: 800; }
#nope span.no { color: #b04a5c; text-decoration: line-through; }
#phone { position: absolute; left: 640px; top: 150px; width: 380px; height: 640px; border-radius: 56px; background: var(--bg); box-shadow: var(--raise); padding: 20px; }
#phone .scr { width: 100%; height: 100%; border-radius: 40px; background: #eef2f8; padding: 26px 18px; display: flex; flex-direction: column; justify-content: flex-end; gap: 12px; }
#phone .me { align-self: flex-end; max-width: 86%; padding: 12px 16px; border-radius: 18px 18px 6px 18px; background: var(--brand); color: #fff; font-size: 17px; font-weight: 700; }
#phone .wait { align-self: flex-start; font-size: 16px; color: var(--mut); font-weight: 800; }
#phone .li { align-self: flex-start; max-width: 90%; padding: 12px 16px; border-radius: 18px 18px 18px 6px; background: #fff; font-size: 17px; font-weight: 700; line-height: 1.4; }
#link { position: absolute; left: 1050px; top: 420px; width: 260px; text-align: center; font-size: 20px; font-weight: 800; color: var(--mut); }
#link i { display: block; height: 4px; margin-bottom: 12px; background: repeating-linear-gradient(90deg, var(--accent) 0 10px, transparent 10px 18px); background-size: 36px 4px; }
#pcx { position: absolute; left: 1340px; top: 300px; width: 380px; padding: 30px; border-radius: 30px; background: var(--bg); box-shadow: var(--raise); text-align: center; }
#pcx i { display: block; font-size: 64px; font-style: normal; } #pcx b { display: block; font: 600 26px Unbounded; margin-top: 10px; } #pcx small { font-size: 19px; color: var(--mut); font-weight: 700; }
#studio { position: absolute; left: 620px; top: 210px; width: 700px; border-radius: 32px; background: var(--bg); box-shadow: var(--raise); padding: 30px 34px; }
#studio h3 { font: 700 30px Unbounded; margin-bottom: 14px; } #studio p { font-size: 21px; color: var(--mut); font-weight: 700; }
#studio .go { display: inline-block; margin-top: 22px; padding: 16px 26px; border-radius: 16px; color: #fff; background: var(--brand); font-size: 21px; font-weight: 800; }
#studio .ok { margin-top: 22px; padding: 16px 20px; border-radius: 18px; background: rgba(47,179,131,.14); color: #1e7d5b; font-size: 21px; font-weight: 800; }
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
    <div id="folder"><div class="h"><i>📁</i><div><b>Договоры и прайсы</b><small id="fn">Читаю…</small></div></div><div class="pb"><i id="fp"></i></div><p id="fr"></p></div>
    <div id="q">Что в договоре с Ромашкой про сроки?</div>
    <div id="ans"><p>Поставка — <mark>в течение 14 рабочих дней после оплаты</mark>. Задержка — пеня 0,1% в день.</p><span>📄 Договор_Ромашка_2026.pdf · п. 4.2</span></div>
    <div id="priv"><div class="box"><i>💻</i><b>Ваш компьютер</b><small>поиск — здесь</small></div><div class="ar"><em id="frag">отрывок</em></div><div class="box"><i>🧠</i><b>Модель</b><small>видит только найденное</small></div></div>
    <div id="nope"><span>✓ файлы остаются на месте</span><span class="no">весь архив в облако</span></div>
    <div id="phone"><div class="scr"><div class="me" id="pm">Что в договоре с Ромашкой про сроки?</div><div class="wait" id="pw">💻 спрашиваю компьютер…</div><div class="li" id="pa">14 рабочих дней после оплаты — п. 4.2 договора 2026 года.</div></div></div>
    <div id="link"><i id="li"></i>через интернет, зашифровано</div><div id="pcx"><i>💻</i><b>Ваш компьютер</b><small>ищет в ваших папках</small></div>
    <div id="studio"><h3>Документы</h3><p>Лира читает ваши папки и отвечает по ним</p><span class="go">Добавить папку…</span><div class="ok">2 папки, 418 файлов — Лира готова отвечать</div></div>
  </div>
"""
JS = """
  layer("L-left", T, s("problem").start + 0.2, s("end").start);
  layer("L-wall", T, s("problem").start + 0.4, s("private").start);
  const fl = [...$("#wall").children];
  fl.forEach((c, i) => { const k = out((T - s("problem").start - 0.5 - i * 0.05) / 0.4); c.style.opacity = k; });
  scene($("#mess"), T, at("s2a") + 0.3, s("add").start);
  scene($("#folder"), T, s("add").start + 0.2, s("ask").start);
  const rd = clamp((T - s("add").start - 0.8) / 3.0);
  $("#fp").style.width = (rd * 100) + "%"; $("#fn").textContent = rd < 1 ? `Читаю… ${Math.round(418 * rd)} из 418` : "418 файлов прочитано";
  $("#fr").textContent = rd >= 1 ? "Лира готова отвечать" : "";
  fl.forEach((c, i) => { const r = clamp((rd * 20 - i)); c.style.filter = s("add").start < T && T < s("ask").start ? `saturate(${0.3 + 0.7 * r})` : ""; });
  scene($("#q"), T, s("ask").start + 0.2, s("private").start, 20);
  scene($("#ans"), T, at("s4b") - 0.4, s("private").start);
  const hit = T > at("s4b") - 0.2 && T < s("private").start;
  fl[0].classList.toggle("hit", hit); fl.forEach((c, i) => { if (i && hit) c.style.opacity = 0.45; });
  scene($("#priv"), T, s("private").start + 0.2, s("phone").start);
  $("#frag").style.left = (clamp((T - s("private").start - 1.2) / 2.2) * 62) + "%";
  scene($("#nope"), T, at("s5b") + 0.2, s("phone").start, 16);
  scene($("#phone"), T, s("phone").start + 0.2, s("how").start);
  vis($("#pm"), out((T - s("phone").start - 0.6) / 0.4), 14);
  vis($("#pw"), out((T - s("phone").start - 1.2) / 0.4) * (1 - out((T - s("phone").start - 3.2) / 0.3)), 10);
  vis($("#pa"), out((T - s("phone").start - 3.4) / 0.4), 14);
  scene($("#link"), T, s("phone").start + 1.0, s("how").start, 10);
  scene($("#pcx"), T, s("phone").start + 0.8, s("how").start);
  $("#li").style.backgroundPosition = `${(T * 60) % 36}px 0`;
  scene($("#studio"), T, s("how").start + 0.2, s("end").start);
"""
