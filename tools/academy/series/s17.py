import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kit import KIT_CSS, MESS_JS, mess
TITLE = "Урок 17 · Близкие"
IDEA = "Главная вещь урока — живая переписка семьи: фото, файл, звонок и группа в одном месте, с замком шифрования."
H1 = "Близкие"
TAG = "Переписка, фото и звонки своих — в одном месте"
NEXT = "Скоро — новые уроки"
ICON = '<svg viewBox="0 0 24 24"><path d="M12 20s-7.5-4.6-7.5-10.2A4.3 4.3 0 0 1 12 7.2a4.3 4.3 0 0 1 7.5 2.6C19.5 15.4 12 20 12 20z"/></svg>'
SCENES = ["title", "problem", "invite", "chat", "call", "group", "how", "end"]
POS = {"problem": "{ lira: [330, 470, 280, 1], patrik: [330, 470, 300, 0] }"}
CSS = KIT_CSS + """
#seal { left: 760px; top: 160px; width: 560px; text-align: center; }
#seal .ring { width: 300px; height: 300px; margin: 18px auto 10px; border-radius: 50%; display: grid; place-items: center; box-shadow: var(--press);
  background: conic-gradient(from var(--a, 0deg), #6f8cff, #b48cff, #ff9ac2, #6f8cff); }
#seal .ring i { width: 220px; height: 220px; border-radius: 50%; background: var(--bg); display: grid; place-items: center; font-style: normal; font-size: 92px; }
#seal p { font-size: 22px; font-weight: 700; color: var(--mut); }
#chat { top: 160px; width: 760px; } #chat .bub { box-shadow: var(--raise-s); max-width: 70%; }
#chat .ph { width: 300px; height: 170px; border-radius: 20px; margin-top: 12px; background: linear-gradient(135deg, #ffd29a, #ff9ac2 55%, #9ab8ff); }
#lock { position: absolute; left: 1420px; top: 220px; width: 380px; padding: 26px 28px; border-radius: 30px; background: var(--bg); box-shadow: var(--raise); }
#lock .big { font-size: 70px; } #lock p { font-size: 21px; font-weight: 700; margin-top: 8px; line-height: 1.4; }
#call { left: 760px; top: 150px; width: 560px; text-align: center; }
#call .av { width: 200px; height: 200px; margin: 16px auto; border-radius: 50%; background: linear-gradient(135deg, #ffd29a, #ff9ac2); display: grid; place-items: center; font-size: 90px; box-shadow: 0 0 0 calc(var(--p, 0) * 30px) rgba(111,140,255,.18); }
#call .bt { display: flex; gap: 24px; justify-content: center; margin-top: 10px; } #call .bt span { width: 86px; height: 86px; border-radius: 50%; display: grid; place-items: center; font-size: 36px; box-shadow: var(--raise-s); }
#call .bt span.end { background: #e2566b; color: #fff; box-shadow: none; }
#grp { top: 150px; width: 900px; } #grp .who { display: flex; gap: 10px; margin: 6px 0 4px; } #grp .who span { width: 64px; height: 64px; border-radius: 50%; display: grid; place-items: center; font-size: 32px; box-shadow: var(--raise-s); }
#studio { top: 170px; width: 900px; }
"""
HTML = """
  <div class="layer" id="L-left">
    """ + mess(["📷 Фото — в мессенджер", "📎 Файл — на почту", "📞 Звонок — по телефону", "💬 Чат — в другом", "🔑 Пароль — от всех", "🗂 Ищи потом…"], "Всё в разных местах") + """
    <div class="card" id="seal"><small>ПРИГЛАШЕНИЕ</small><div class="ring"><i>💗</i></div><p>Покажите печать Dewiar — или отправьте ссылку</p></div>
    <div class="card" id="chat"><small>МАМА</small>
      <div class="bub" id="c1">Как доехали? 😊</div><div class="bub me" id="c2">Отлично! Смотри 👇</div><div class="ph" id="c3" style="margin-left:auto"></div>
      <div class="bub me" id="c4">Я выезжаю, буду в семь</div></div>
    <div id="lock"><div class="big">🔒</div><p>Шифруется на ваших устройствах — сервер видит только замок</p></div>
    <div class="card" id="call"><small>ЗВОНОК · С ВИДЕО</small><div class="av">👩</div><h3>Мама</h3><div class="bt"><span>🎤</span><span>📹</span><span class="end">✆</span></div></div>
    <div class="card" id="grp"><small>ГРУППА</small><h3>Семья</h3><div class="who"><span>👩</span><span>👨</span><span>👧</span><span>👦</span><span>👵</span></div>
      <div class="row"><i>⏰</i>«Напомни всем в группе Семья в субботу в 10 — дача»<em class="ok">у каждого ✓</em></div>
      <div class="row"><i>🖼</i>Фото и файлы группы — альбомом</div></div>
    <div class="card" id="studio"><h3>Близкие</h3><small>В студии и на телефоне — та же переписка</small>
      <div class="chips"><span>«Напиши маме, что я выезжаю»</span><span>«Позвони маме»</span><span>«Отправь брату файл»</span></div></div>
  </div>
"""
JS = MESS_JS + """
  layer("L-left", T, s("problem").start + 0.2, s("end").start);
  scene($("#seal"), T, s("invite").start + 0.2, s("chat").start); $("#seal .ring").style.setProperty("--a", (T * 40) + "deg");
  scene($("#chat"), T, s("chat").start + 0.2, s("call").start);
  ["#c1", "#c2", "#c3"].forEach((id, i) => vis($(id), out((T - s("chat").start - 0.8 - i * 0.7) / 0.4), 14));
  vis($("#c4"), out((T - at("s4a") - 3.4) / 0.4), 14);
  scene($("#lock"), T, at("s4b") + 0.2, s("call").start, 20);
  scene($("#call"), T, s("call").start + 0.2, s("group").start); $("#call .av").style.setProperty("--p", (Math.sin(T * 4) + 1) / 2);
  scene($("#grp"), T, s("group").start + 0.2, s("how").start);
  [...$("#grp .who").children].forEach((c, i) => vis(c, out((T - s("group").start - 0.6 - i * 0.2) / 0.3), 10, .8));
  [...$("#grp").querySelectorAll(".row")].forEach((c, i) => vis(c, out((T - s("group").start - 2.2 - i * 0.8) / 0.4), 12));
  scene($("#studio"), T, s("how").start + 0.2, s("end").start);
  [...$("#studio .chips").children].forEach((c, i) => vis(c, out((T - s("how").start - 0.8 - i * 0.3) / 0.4), 12));
"""
