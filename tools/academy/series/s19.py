import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kit import KIT_CSS, MESS_JS, mess
TITLE = "Урок 19 · Сейф паролей"
IDEA = "Главная вещь урока — пароль сказан вслух, а показан только на экране, под замком."
H1 = "Сейф паролей"
TAG = "Пароли и коды — под замком, не на бумажках"
NEXT = "Скоро — новые уроки"
ICON = '<svg viewBox="0 0 24 24"><rect x="5" y="10" width="14" height="10" rx="3"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/><circle cx="12" cy="15" r="1.4"/></svg>'
SCENES = ["title", "problem", "save", "show", "lock", "phone", "how", "end"]
POS = {"problem": "{ lira: [330, 470, 280, 1], patrik: [330, 470, 300, 0] }"}
CSS = KIT_CSS + """
#saved { top: 340px; width: 680px; } #saved .big { font-size: 44px; letter-spacing: .08em; }
#reveal { left: 620px; top: 330px; width: 620px; text-align: center; } #reveal .big { font-size: 58px; margin: 14px 0; letter-spacing: .06em; }
#reveal .mute { display: inline-flex; gap: 10px; align-items: center; padding: 12px 18px; border-radius: 16px; box-shadow: var(--press); font-size: 20px; font-weight: 800; color: var(--mut); }
#safe { left: 760px; top: 150px; width: 600px; text-align: center; } #safe .lk { font-size: 150px; line-height: 1.1; }
#safe .bits { font-family: monospace; font-size: 22px; color: var(--mut); word-break: break-all; margin-top: 10px; line-height: 1.5; }
#studio { top: 160px; width: 900px; }
"""
HTML = """
  <div class="layer" id="L-left">
    """ + mess(["📶 Вайфай: ?", "🚨 Сигнализация: ?", "💳 ПИН карты", "🔢 Домофон", "🗝 Почта: пароль", "📝 Бумажка под клавиатурой"], "Бумажки теряются") + """
    <div class="say" id="q1">«Запомни пароль от вайфая: Солнце двадцать пять»</div>
    <div class="card" id="saved"><small>В СЕЙФЕ · НЕ В ЗАМЕТКАХ</small><div class="row"><i>📶</i>Пароль от вайфая<em class="ok">• • • • • • ✓</em></div></div>
    <div class="say" id="q2">«Какой пароль от вайфая?»</div>
    <div class="card" id="reveal"><small>ПАРОЛЬ ОТ ВАЙФАЯ</small><div class="big" id="pw">Solnce25</div><span class="mute">🔇 Вслух не говорю — смотрите на экран</span></div>
    <div class="card" id="safe"><div class="lk">🔐</div><h3>Зашифровано</h3><div class="bits" id="bits"></div></div>
    <div class="card" id="studio"><h3>Сейф паролей</h3><small>Записи, поиск и секретные страницы</small>
      <div class="row"><i>📶</i>Вайфай дома<em>• • • • • •</em></div><div class="row"><i>💳</i>ПИН карты<em>• • • •</em></div><div class="row"><i>🔢</i>Домофон<em>• • • •</em></div></div>
  </div>
  <div class="layer" id="L-phone"><div class="phone"><div class="scr"><h5>Сейф</h5><div class="bub">📶 Вайфай дома<br><b style="letter-spacing:.06em">• • • • • •</b></div>
    <div class="bub" style="color:var(--mut);font-size:16px">🔒 Пришёл зашифрованным с компьютера</div></div></div></div>
"""
JS = MESS_JS + """
  layer("L-left", T, s("problem").start + 0.2, s("end").start);
  scene($("#q1"), T, s("save").start + 0.2, s("show").start, 20);
  scene($("#saved"), T, s("save").start + 3.2, s("show").start, 24);
  scene($("#q2"), T, s("show").start + 0.2, s("lock").start, 20);
  scene($("#reveal"), T, s("show").start + 2.2, s("lock").start, 24);
  scene($("#safe"), T, s("lock").start + 0.2, s("phone").start);
  const H = "0123456789abcdef"; let b = ""; for (let i = 0; i < 96; i++) b += H[Math.floor((Math.sin(i * 12.9898 + Math.floor(T * 8)) * 43758.5453 % 1 + 1) % 1 * 16)];
  $("#bits").textContent = b;
  layer("L-phone", T, s("phone").start + 0.2, s("how").start);
  scene($("#studio"), T, s("how").start + 0.2, s("end").start);
  [...$("#studio").querySelectorAll(".row")].forEach((c, i) => vis(c, out((T - s("how").start - 0.6 - i * 0.3) / 0.4), 12));
"""
