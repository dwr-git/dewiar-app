import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kit import KIT_CSS, MESS_JS, mess
TITLE = "Урок 18 · Заметки и память"
IDEA = "Главная вещь урока — сказанное вслух становится фактом в памяти и тут же находится вопросом."
H1 = "Заметки и память"
TAG = "Скажите — запомню. Спросите — найду"
NEXT = "Скоро — новые уроки"
ICON = '<svg viewBox="0 0 24 24"><path d="M6 3h9l4 4v14H6z"/><path d="M15 3v4h4M9 12h7M9 16h5"/></svg>'
SCENES = ["title", "problem", "remember", "notes", "find", "map", "how", "end"]
POS = {"problem": "{ lira: [330, 470, 280, 1], patrik: [330, 470, 300, 0] }"}
CSS = KIT_CSS + """
#fact { top: 340px; width: 760px; } #fact .big { font-size: 42px; }
#tiles { position: absolute; left: 620px; top: 150px; width: 1200px; display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; }
.nt { padding: 24px 24px; border-radius: 26px; background: var(--bg); box-shadow: var(--raise); min-height: 200px; }
.nt b { display: block; font: 700 23px Manrope; margin-bottom: 8px; } .nt p { font-size: 18px; font-weight: 600; color: var(--mut); line-height: 1.45; }
.nt .tg { display: inline-block; margin-top: 12px; padding: 7px 12px; border-radius: 10px; font-size: 15px; font-weight: 800; }
#res { top: 330px; width: 900px; }
#map { position: absolute; left: 640px; top: 130px; width: 1180px; height: 700px; border-radius: 40px; background: radial-gradient(ellipse at 50% 45%, #fff, rgba(255,255,255,.3) 60%), var(--bg); box-shadow: var(--press); }
#map svg { width: 100%; height: 100%; }
#about { top: 330px; width: 860px; }
"""
import math, random
rnd = random.Random(5)
NODES = [("Вы", 590, 350, 34, "#5B5FE0")] + [(n, 590 + math.cos(a) * r, 350 + math.sin(a) * r * 0.78, 14 + rnd.random() * 10, c) for n, a, r, c in
         [("Дима · 32 размер", 0.3, 230, "#e3a33a"), ("Отпуск", 1.2, 260, "#7a6be0"), ("Мама", 2.1, 220, "#e05a8a"), ("Дача", 2.9, 250, "#3fb37f"),
          ("Работа", 3.8, 240, "#4a8be8"), ("Подарки", 4.6, 260, "#e3a33a"), ("Минск", 5.4, 230, "#3a9fb0"), ("Книга", 6.0, 280, "#7a6be0")]]
SVG = '<svg viewBox="0 0 1180 700">' + "".join(f'<path class="ed" d="M590 350 Q {(590 + x) / 2 + 40} {(350 + y) / 2 - 40} {x} {y}" stroke="{c}" stroke-opacity=".45" stroke-width="3" fill="none"/>' for _, x, y, _, c in NODES[1:]) + \
      "".join(f'<g class="nd"><circle cx="{x}" cy="{y}" r="{r}" fill="{c}"/><text x="{x}" y="{y + r + 26}" text-anchor="middle" font-family="Manrope" font-weight="800" font-size="20" fill="#2A2F47" stroke="#fff" stroke-width="5" paint-order="stroke">{n}</text></g>' for n, x, y, r, c in NODES) + "</svg>"
HTML = """
  <div class="layer" id="L-left">
    """ + mess(["👟 Размер обуви сына", "🔢 Код домофона", "🎁 Идея подарка", "📖 Что почитать", "🏖 Отпуск: куда?", "🍰 Рецепт пирога"], "В голове не удержать") + """
    <div class="say" id="q1">«Запомни: у Димы тридцать второй размер обуви»</div>
    <div class="card" id="fact"><small>ЗАПОМНИЛА · ФАКТ О ВАС</small><div class="big">👟 Дима — 32 размер</div></div>
    <div id="tiles">
      <div class="nt" style="background:#fff6d9"><b>Идеи для отпуска</b><p>Грузия в мае · море в сентябре · взять палатку</p><span class="tg" style="background:#ffe7a3">#отпуск</span></div>
      <div class="nt"><b>Покупки</b><p>Молоко, хлеб, батарейки AA</p><span class="tg" style="background:rgba(69,96,234,.12)">#дом</span></div>
      <div class="nt" style="background:#e9f7ef"><b>Дача</b><p>Посадил чеснок, две грядки</p><span class="tg" style="background:#c8eed8">#дача</span></div></div>
    <div class="say" id="q2">«Что я писала про отпуск?»</div>
    <div class="card" id="res"><small>НАШЛА</small>
      <div class="row"><i>📝</i>Заметка «Идеи для отпуска»<em>Грузия в мае</em></div>
      <div class="row"><i>📔</i>Дневник, 12 октября<em>«хочу к морю»</em></div>
      <div class="row"><i>📄</i>Документы: путёвка.pdf<em>сентябрь</em></div></div>
    <div id="map">""" + SVG + """</div>
    <div class="say" id="q3">«Что ты обо мне знаешь?»</div>
    <div class="card" id="about"><small>ЧТО Я ЗНАЮ О ВАС</small>
      <div class="row"><i>👟</i>У Димы 32-й размер обуви<em>поправить</em></div><div class="row"><i>🏡</i>Дача под Минском<em>поправить</em></div></div>
  </div>
"""
JS = MESS_JS + """
  layer("L-left", T, s("problem").start + 0.2, s("end").start);
  scene($("#q1"), T, s("remember").start + 0.2, s("notes").start, 20);
  scene($("#fact"), T, s("remember").start + 3.0, s("notes").start, 24);
  scene($("#tiles"), T, s("notes").start + 0.2, s("find").start);
  [...$("#tiles").children].forEach((c, i) => vis(c, out((T - s("notes").start - 0.6 - i * 0.4) / 0.4), 16, .95));
  scene($("#q2"), T, s("find").start + 0.2, s("map").start, 20);
  scene($("#res"), T, s("find").start + 2.4, s("map").start, 24);
  [...$("#res").querySelectorAll(".row")].forEach((c, i) => vis(c, out((T - s("find").start - 2.8 - i * 0.5) / 0.4), 12));
  scene($("#map"), T, s("map").start + 0.2, s("how").start);
  [...$("#map").querySelectorAll(".nd")].forEach((g, i) => { const k = out((T - s("map").start - 0.5 - i * 0.2) / 0.4); g.style.opacity = k; });
  [...$("#map").querySelectorAll(".ed")].forEach((e, i) => { e.style.strokeDasharray = 600; e.style.strokeDashoffset = 600 * (1 - out((T - s("map").start - 0.9 - i * 0.2) / 0.6)); });
  scene($("#q3"), T, s("how").start + 0.2, s("end").start, 20);
  scene($("#about"), T, s("how").start + 2.2, s("end").start, 24);
"""
