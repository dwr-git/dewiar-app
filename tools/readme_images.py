#!/usr/bin/env python3
"""Картинки для README и выпусков: docs/img/banner.webp (обложка), team.webp (Лира, Патрик и «Готовые персонажи»),
how.webp (как устроено) и phone-lira.webp (телефон с Лирой). Рисуются из HTML в Chromium (Playwright), поэтому
обновить их после смены персонажей или облика — одна команда:

    python3 tools/readme_images.py [папка, по умолчанию docs/img]

Персонажи и их цвета — из core/personas.py; фото — data/avatars, у остальных — их живой облик (ui/assets/entities.js),
шрифты — свои (android/assets/www/fonts). Сеть не нужна. Ширина картинок — под колонку README на GitHub (880 точек)
в двойной чёткости.
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "core"))
import personas as P  # noqa: E402

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs/img"
SITE = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "server/dwrapp"   # лица и обложка для страницы «Скачать»
COLLECTION = ["dewiar", "agent", "jarvis", "eva", "professor", "femida", "doctor", "iris", "oskar", "gaston", "nika", "mishel"]


def people():
    allp = {**P.BUILTIN, **P.TEMPLATES, **P.GALLERY}
    out = {}
    for k in ["lira", "patrik"] + COLLECTION:
        v = allp[k]
        photo = ROOT / "data/avatars" / f"{k}.webp"
        role = {"dewiar": "Деловой помощник"}.get(k, v.get("role", ""))   # в коллекции «главный» звучит странно
        out[k] = {"name": v["name"], "role": role, "tagline": v.get("tagline", ""), "style": v.get("style", "nexus"),
                  "color": v.get("color", "#8B8CF7"), "photo": f"av/{k}.webp" if photo.exists() else ""}
    return out


CSS = r"""
@font-face { font-family: Manrope; font-weight: 400; src: url(fonts/manrope-cyrillic-400-normal.woff2); unicode-range: U+0400-045F, U+2116; }
@font-face { font-family: Manrope; font-weight: 400; src: url(fonts/manrope-latin-400-normal.woff2); unicode-range: U+0000-00FF, U+2000-206F; }
@font-face { font-family: Manrope; font-weight: 600; src: url(fonts/manrope-cyrillic-600-normal.woff2); unicode-range: U+0400-045F, U+2116; }
@font-face { font-family: Manrope; font-weight: 600; src: url(fonts/manrope-latin-600-normal.woff2); unicode-range: U+0000-00FF, U+2000-206F; }
@font-face { font-family: Manrope; font-weight: 700; src: url(fonts/manrope-cyrillic-700-normal.woff2); unicode-range: U+0400-045F, U+2116; }
@font-face { font-family: Manrope; font-weight: 700; src: url(fonts/manrope-latin-700-normal.woff2); unicode-range: U+0000-00FF, U+2000-206F; }
@font-face { font-family: Unbounded; font-weight: 600; src: url(fonts/unbounded-cyrillic-600-normal.woff2); unicode-range: U+0400-045F, U+2116; }
@font-face { font-family: Unbounded; font-weight: 600; src: url(fonts/unbounded-latin-600-normal.woff2); unicode-range: U+0000-00FF, U+2000-206F; }
:root { --t1: #F4F4F6; --t2: rgba(255,255,255,.86); --t3: rgba(255,255,255,.64); --t4: rgba(255,255,255,.42);
  --pink: #FF7AC6; --blue: #78DBFF; --icon: #8B8CF7; --glass: rgba(255,255,255,.06); --shadow: 0 10px 30px rgb(0 0 0 / 22%); }
* { box-sizing: border-box; margin: 0; }
body { background: #0a0a0f; color: var(--t2); font: 15px/1.5 Manrope, sans-serif; -webkit-font-smoothing: antialiased; }
.scene { position: relative; width: 880px; overflow: hidden; border-radius: 22px;
  background: radial-gradient(circle at 20% 80%, rgba(120,119,198,.3) 0%, transparent 50%),
              radial-gradient(circle at 80% 20%, rgba(255,119,198,.3) 0%, transparent 50%),
              radial-gradient(circle at 40% 40%, rgba(120,219,255,.2) 0%, transparent 50%),
              linear-gradient(135deg, #0a0a0f 0%, #1a1a2e 50%, #16213e 100%); }
h1, h2, h3, .uf { font-family: Unbounded, Manrope, sans-serif; font-weight: 600; color: var(--t1); letter-spacing: -.01em; }
.glass { background: var(--glass); box-shadow: var(--shadow); border-radius: 18px; backdrop-filter: blur(10px); }
.face { position: relative; border-radius: 50%; overflow: hidden; background: #050508; flex: none; }
.face img, .face canvas { width: 100%; height: 100%; object-fit: cover; display: block; }
.halo { position: relative; flex: none; display: grid; place-items: center; border-radius: 50%; }
.halo::before { content: ""; position: absolute; inset: -14%; border-radius: 50%;
  background: radial-gradient(circle, transparent 55%, color-mix(in srgb, var(--c) 34%, transparent) 62%, transparent 72%); }
.halo .face { box-shadow: 0 0 0 calc(var(--s) * .035) color-mix(in srgb, var(--c) 30%, transparent), 0 0 calc(var(--s) * .35) color-mix(in srgb, var(--c) 45%, transparent); }

/* обложка */
#banner { height: 400px; padding: 44px 52px; }
#banner .left { width: 420px; position: relative; z-index: 2; }
#banner .chips { display: flex; gap: 8px; margin-bottom: 22px; }
#banner .chips span { padding: 5px 12px; border-radius: 999px; background: rgba(255,255,255,.08); color: var(--t2); font-size: 13px; font-weight: 600; }
#banner h1 { font-size: 64px; line-height: 1; }
#banner .sub { margin-top: 16px; font-size: 21px; line-height: 1.35; color: var(--t2); font-weight: 600; }
#banner .talk { margin-top: 26px; display: grid; gap: 8px; }
#banner .b { display: inline-block; padding: 9px 14px; border-radius: 14px; font-size: 14.5px; max-width: 340px; }
#banner .you { background: rgba(255,255,255,.08); color: var(--t2); justify-self: start; }
#banner .her { background: linear-gradient(135deg, rgba(102,126,234,.55), rgba(118,75,162,.55)); color: #fff; justify-self: start; margin-left: 26px; }
#banner .lira { position: absolute; right: 62px; top: 40px; --s: 262px; --c: #B78CFF; }
#banner .lira .face { width: 262px; height: 262px; }
#banner .pat { position: absolute; right: 318px; top: 214px; --s: 112px; --c: #FFB547; }
#banner .pat .face { width: 112px; height: 112px; }
#banner .tag { position: absolute; left: 50%; bottom: -30px; transform: translateX(-50%); z-index: 3; padding: 6px 14px; border-radius: 999px;
  background: rgba(15,15,28,.78); color: var(--t1); font-weight: 700; font-size: 14px; box-shadow: var(--shadow); white-space: nowrap; }
#banner .lira .tag { bottom: -22px; }
#banner .tag small { color: var(--t3); font-weight: 600; font-size: 12.5px; margin-left: 6px; }

/* команда */
#team { padding: 38px 40px 40px; }
#team h2 { font-size: 30px; }
#team .lead { margin-top: 8px; color: var(--t3); font-size: 15.5px; }
#team .main { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; margin-top: 26px; }
#team .card { display: flex; gap: 22px; align-items: center; padding: 22px; }
#team .card .halo { --s: 132px; }
#team .card .face { width: 132px; height: 132px; }
#team .card h3 { font-size: 24px; }
#team .card .role { color: var(--c); font-weight: 700; font-size: 14.5px; margin-top: 2px; }
#team .card .tl { color: var(--t3); margin-top: 8px; font-size: 14.5px; }
#team .card .call { margin-top: 10px; color: var(--t2); font-size: 14px; font-weight: 600; }
#team h4 { margin: 30px 0 14px; color: var(--t1); font: 700 17px Manrope, sans-serif; }
#team h4 span { color: var(--t4); font-weight: 600; font-size: 14px; margin-left: 8px; }
#team .grid { display: grid; grid-template-columns: repeat(6, 1fr); gap: 14px 10px; }
#team .p { display: flex; flex-direction: column; align-items: center; text-align: center; padding: 14px 6px 12px; }
#team .p .halo { --s: 74px; }
#team .p .face { width: 74px; height: 74px; }
#team .p b { margin-top: 12px; color: var(--t1); font-size: 14.5px; }
#team .p span { color: var(--t4); font-size: 12.5px; line-height: 1.3; margin-top: 2px; }

/* как устроено */
#how { height: 586px; padding: 34px 40px; }
#how h2 { font-size: 26px; }
#how .lead { color: var(--t3); margin-top: 6px; font-size: 15px; }
#how svg.wires { position: absolute; inset: 0; width: 880px; height: 586px; }
#how .n { position: absolute; padding: 14px 16px; width: 228px; min-height: 120px; }
#how .n .t { display: flex; align-items: center; gap: 10px; color: var(--t1); font-weight: 700; font-size: 15.5px; }
#how .n .t i { width: 30px; height: 30px; border-radius: 10px; display: grid; place-items: center; background: color-mix(in srgb, var(--c) 18%, transparent); flex: none; }
#how .n .t i svg { width: 17px; height: 17px; stroke: var(--c); fill: none; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
#how .n p { margin-top: 6px; color: var(--t3); font-size: 13px; line-height: 1.45; }
#how .hub { width: 236px; padding: 18px; text-align: left; background: linear-gradient(135deg, rgba(102,126,234,.22), rgba(118,75,162,.22)); }
#how .lbl { position: absolute; font-size: 12px; font-weight: 700; color: var(--t3); background: rgba(12,12,24,.7); padding: 3px 9px; border-radius: 999px; white-space: nowrap; }
"""

ICON = {
    "pc": '<svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8M12 16v4"/></svg>',
    "phone": '<svg viewBox="0 0 24 24"><rect x="7" y="2.5" width="10" height="19" rx="2.5"/><path d="M11 18.5h2"/></svg>',
    "server": '<svg viewBox="0 0 24 24"><rect x="4" y="4" width="16" height="6" rx="1.5"/><rect x="4" y="14" width="16" height="6" rx="1.5"/><path d="M8 7h.01M8 17h.01"/></svg>',
    "cloud": '<svg viewBox="0 0 24 24"><path d="M7 18h10a4 4 0 0 0 .6-7.96A6 6 0 0 0 6.1 9.2 4.5 4.5 0 0 0 7 18z"/></svg>',
    "brain": '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M12 2v4M12 18v4M2 12h4M18 12h4M5 5l3 3M16 16l3 3M5 19l3-3M16 8l3-3"/></svg>',
    "chat": '<svg viewBox="0 0 24 24"><path d="M4 5h16v11H9l-5 4z"/></svg>',
}


def face(k, p, size_cls=""):
    inner = f'<img src="{p["photo"]}" alt="">' if p["photo"] else f'<canvas data-style="{p["style"]}" data-color="{p["color"]}" width="300" height="300"></canvas>'
    return f'<div class="halo" style="--c:{p["color"]}"><div class="face">{inner}</div></div>'


def page(ps):
    lira, pat = ps["lira"], ps["patrik"]
    lira_img, pat_img = "av/lira.webp", "av/patrik.webp"      # с глазами (живой облик рисует их поверх)
    banner = f"""<div class="scene" id="banner">
  <div class="left">
    <div class="chips"><span>Windows</span><span>Ubuntu</span><span>Android</span></div>
    <h1>Dewiar</h1>
    <div class="sub">Голосовая помощница, с которой просто разговаривают</div>
    <div class="talk"><span class="b you">Лира, что у меня в среду?</span><span class="b her">В 15:00 — встреча с подрядчиком. Напомнить за час?</span></div>
  </div>
  <div class="halo lira"><div class="face"><img src="{lira_img}" alt=""></div><span class="tag">Лира<small>главная помощница</small></span></div>
  <div class="halo pat"><div class="face"><img src="{pat_img}" alt=""></div><span class="tag">Патрик<small>наставник</small></span></div>
</div>"""
    main = ""
    for k, call in (("lira", "«Лира, напомни через два часа…»"), ("patrik", "«Патрик, стоит ли менять работу?»")):
        p = ps[k]
        img = {"lira": lira_img, "patrik": pat_img}[k]
        main += f"""<div class="glass card" style="--c:{p['color']}"><div class="halo"><div class="face"><img src="{img}" alt=""></div></div>
  <div><h3>{p['name']}</h3><div class="role">{p['role']}</div><div class="tl">{p['tagline']}</div><div class="call">{call}</div></div></div>"""
    grid = "".join(f'<div class="glass p">{face(k, ps[k])}<b>{ps[k]["name"]}</b><span>{ps[k]["role"]}</span></div>' for k in COLLECTION)
    team = f"""<div class="scene" id="team">
  <h2>Команда</h2>
  <div class="lead">С самого начала — Лира и Патрик: у каждого свой голос, характер и живое лицо.</div>
  <div class="main">{main}</div>
  <h4>Готовые персонажи<span>добавляются одной кнопкой — главная сама передаёт им вопрос по их части</span></h4>
  <div class="grid">{grid}</div>
</div>"""
    node = lambda x, y, c, ic, t, p, cls="": f'<div class="glass n {cls}" style="left:{x}px; top:{y}px; --c:{c}"><div class="t"><i>{ICON[ic]}</i>{t}</div><p>{p}</p></div>'
    how = f"""<div class="scene" id="how">
  <h2>Как устроено</h2>
  <div class="lead">Одна помощница на всех устройствах: общая память, напоминания и заметки.</div>
  <svg class="wires" viewBox="0 0 880 586">
    <defs><linearGradient id="g1" x1="0" x2="1"><stop offset="0" stop-color="#78DBFF" stop-opacity=".8"/><stop offset="1" stop-color="#B78CFF" stop-opacity=".8"/></linearGradient>
      <linearGradient id="g2" x1="0" x2="1"><stop offset="0" stop-color="#B78CFF" stop-opacity=".8"/><stop offset="1" stop-color="#FF7AC6" stop-opacity=".8"/></linearGradient></defs>
    <g fill="none" stroke-width="2.4" stroke-linecap="round">
      <path d="M268 182 C 300 182, 296 312, 326 312" stroke="url(#g1)"/>
      <path d="M268 324 C 296 324, 300 330, 326 330" stroke="url(#g1)"/>
      <path d="M268 466 C 300 466, 296 348, 326 348" stroke="url(#g1)"/>
      <path d="M562 312 C 590 312, 586 212, 612 212" stroke="url(#g2)"/>
      <path d="M562 348 C 590 348, 586 452, 612 452" stroke="url(#g2)"/>
    </g>
    <g fill="#F4F4F6"><circle cx="326" cy="312" r="3.5"/><circle cx="326" cy="330" r="3.5"/><circle cx="326" cy="348" r="3.5"/><circle cx="612" cy="212" r="3.5"/><circle cx="612" cy="452" r="3.5"/></g>
  </svg>
  {node(40, 122, "#78DBFF", "pc", "Компьютер", "Виджет и студия: слух, голос, руки, большие задачи и код.")}
  {node(40, 264, "#B78CFF", "phone", "Телефон", "Android: голос, напоминания, деньги, радио, руки в приложениях.")}
  {node(40, 406, "#4BE3A1", "server", "Свой сервер", "Тот же пакет — помощник на связи круглосуточно.")}
  <div class="glass n hub" style="left:326px; top:252px; --c:#FF7AC6"><div class="t"><i>{ICON['cloud']}</i>dewiar.pro</div><p>Аккаунт и синхронизация. Модели Dewiar, если своей нет. Задачи с телефона, когда компьютер выключен.</p></div>
  {node(612, 152, "#FFB547", "brain", "Любая модель", "Своя: vLLM, Ollama, LM Studio. Облачная: OpenAI, Claude, OpenRouter, Dewiar.")}
  {node(612, 392, "#60A5FA", "chat", "Мессенджеры", "Telegram и MAX — ещё один способ поговорить с ней.")}
  <span class="lbl" style="left:250px; top:236px">синхронизация</span>
  <span class="lbl" style="left:556px; top:262px">думает</span>
</div>"""
    data = json.dumps({k: v for k, v in ps.items()}, ensure_ascii=False)
    return f"""<!doctype html><html lang="ru"><head><meta charset="utf-8"><style>{CSS}</style></head><body>
<div style="display:grid; gap:30px; padding:20px; width:920px">{banner}{team}{how}</div>
<script src="entities.js"></script>
<script>
const PS = {data};
window.ents = [];
document.querySelectorAll("canvas[data-style]").forEach(c => {{
  const e = new DewiarEntity(c, {{ style: c.dataset.style, color: c.dataset.color }});
  e.set({{ state: "speaking", level: .45 }}); window.ents.push(e);
}});
</script></body></html>"""


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp())
    shutil.copytree(ROOT / "android/assets/www/fonts", tmp / "fonts")
    shutil.copytree(ROOT / "ui/assets/live", tmp / "live")
    shutil.copytree(ROOT / "data/avatars", tmp / "av")
    shutil.copy(ROOT / "ui/assets/entities.js", tmp / "entities.js")
    (tmp / "index.html").write_text(page(people()), encoding="utf-8")
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 960, "height": 1800}, device_scale_factor=2)
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto((tmp / "index.html").as_uri())
        pg.wait_for_timeout(2500)                         # живые облики успевают «заговорить», шрифты — загрузиться
        pg.evaluate("() => { ents.forEach(e => e.paused = true); }")
        for el, name in (("#banner", "banner"), ("#team", "team"), ("#how", "how")):
            png = tmp / f"{name}.png"
            pg.locator(el).screenshot(path=str(png), omit_background=True)
            Image.open(png).save(OUT / f"{name}.webp", "WEBP", quality=88, method=6)
            print(f"{OUT / (name + '.webp')}")
        b.close()
    phone(tmp)
    styles(tmp)
    styles(tmp, "en")
    if SITE.is_dir():                                   # в открытой копии сайта нет — только картинки README
        site_faces(tmp)
        Image.open(OUT / "banner.webp").convert("RGB").save(SITE / "dewiar_banner.jpg", "JPEG", quality=86, optimize=True)   # превью ссылки
    if errs:
        print("Ошибки страницы:", errs)
        return 1
    return 0


def site_faces(tmp):
    """Круглые лица всей команды (team-<id>.webp, прозрачные углы) и team.json — для раздела «Команда» на странице
    «Скачать» (server/dwrapp/download.php): там они на HTML, чтобы и на телефоне подписи читались."""
    ps = people()
    for k in ("lira", "patrik"):
        ps[k]["photo"] = f"av/{k}.webp"
    cells = "".join(f'<div class="f" id="f-{k}">' + (f'<img src="{p["photo"]}">' if p["photo"] else
                    f'<canvas data-style="{p["style"]}" data-color="{p["color"]}" width="300" height="300"></canvas>') + "</div>"
                    for k, p in ps.items())
    (tmp / "faces.html").write_text(f"""<!doctype html><html><head><meta charset="utf-8"><style>
body {{ margin: 0; background: transparent; display: flex; flex-wrap: wrap; gap: 10px; padding: 10px; }}
.f {{ width: 120px; height: 120px; border-radius: 50%; overflow: hidden; background: #050508; }}
.f img, .f canvas {{ width: 100%; height: 100%; object-fit: cover; display: block; }}
</style></head><body>{cells}<script src="entities.js"></script><script>
window.ents = [...document.querySelectorAll("canvas")].map(c => {{ const e = new DewiarEntity(c, {{ style: c.dataset.style, color: c.dataset.color }}); e.set({{ state: "speaking", level: .45 }}); return e; }});
</script></body></html>""", encoding="utf-8")
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1000, "height": 800}, device_scale_factor=2)
        pg.goto((tmp / "faces.html").as_uri())
        pg.wait_for_timeout(2500)
        pg.evaluate("() => ents.forEach(e => e.paused = true)")
        for k in ps:
            png = tmp / f"f-{k}.png"
            pg.locator(f"#f-{k}").screenshot(path=str(png), omit_background=True)
            Image.open(png).save(SITE / f"team-{k}.webp", "WEBP", quality=88, method=6)
        b.close()
    meta = [{"id": k, "name": v["name"], "role": v["role"], "tagline": v["tagline"], "color": v["color"]} for k, v in ps.items()]
    (SITE / "team.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(SITE / "team.json", "+", len(ps), "лиц")


def phone(tmp):
    """Телефон с Лирой: настоящий интерфейс android/assets/www на подменённом мосте, разговор — подставлен."""
    import subprocess
    www = tmp / "www"
    shutil.copytree(ROOT / "android/assets/www", www)
    shutil.copy(ROOT / "ui/assets/entities.js", www / "entities.js")
    shutil.copytree(ROOT / "ui/assets/live", www / "live", dirs_exist_ok=True)
    (www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                    capture_output=True, text=True, check=True).stdout, encoding="utf-8")
    (www / "radio.js").write_text("window.DEWIAR_RADIO = [];", encoding="utf-8")
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2)
        pg.goto((www / "index.html").as_uri())
        pg.wait_for_timeout(900)
        pg.evaluate("""() => { S.onboarded = true; S.llm.base_url = "https://example.invalid/v1"; saveS(); closeSheets && closeSheets();
          clearCard(); showYou("Лира, что у меня в среду?"); showBot("В 15:00 — встреча с подрядчиком по кухне. Напомнить за час?"); setState("speaking"); }""")
        pg.wait_for_timeout(1600)
        pg.evaluate("() => clearCard()")
        png = tmp / "phone.png"
        pg.screenshot(path=str(png))
        Image.open(png).convert("RGB").resize((420, 909), Image.LANCZOS).save(OUT / "phone-lira.webp", "WEBP", quality=86, method=6)
        print(OUT / "phone-lira.webp")
        b.close()


STYLE_TEXT = {"ru": {"names": ["Глассморфизм", "Неоморфизм", "Фирменная", "Вижн", "Белоснежная"], "lira": "Лира",
                     "q": "Что у меня в среду?", "a": "В 15:00 — встреча с подрядчиком по кухне. Напомнить за час?"},
              "en": {"names": ["Glassmorphism", "Neumorphism", "Signature", "Vision", "Snow-white"], "lira": "Lira",
                     "q": "What do I have on Wednesday?", "a": "At 3 pm — a meeting with the kitchen contractor. Remind you an hour before?"}}


def styles(tmp, lang="ru"):
    """Витрина стилей виджета (docs/img/styles.webp и dewiar_styles.webp для страницы «Скачать»): настоящий виджет
    ui/hud.html с Лирой в нескольких темах (assets/skins.*), разложенный как на презентации дизайн-студии.
    lang="en" — то же по-английски (dewiar_styles.en.webp — английской странице «Скачать», владелец 15.11)."""
    from playwright.sync_api import sync_playwright
    T = STYLE_TEXT[lang]
    shots = list(zip(["glass", "neu", "brand", "vision", "snow"], T["names"]))
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 300, "height": 420}, device_scale_factor=2)
        pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };")
        pg.goto((ROOT / "ui/hud.html").as_uri() + "?mode=card&port=1" + ("&lang=en" if lang == "en" else ""))
        pg.wait_for_timeout(1000)
        pg.evaluate("""([img, T]) => { personas = [{ id: 'lira', name: T.lira, color: '#9BD4FF', style: 'strings', avatar_url: img, live: 'lira' }];
            applyPersona('lira'); setState('idle'); core.emit('turn', { seconds: 60 });
            showCap(T.q, T.a); }""", [(ROOT / "data/avatars/lira.webp").as_uri(), T])
        pg.wait_for_timeout(1500)
        for k, _ in shots:
            pg.evaluate("(k) => applyLook({ skin: k })", k)
            pg.wait_for_timeout(500)
            pg.screenshot(path=str(tmp / f"st-{k}.png"))
        cards = "".join(f'<figure class="c{i}"><img src="st-{k}.png"><figcaption>{n}</figcaption></figure>' for i, (k, n) in enumerate(shots))
        (tmp / "styles.html").write_text(f"""<!doctype html><meta charset="utf-8"><style>
@font-face {{ font-family: Manrope; font-weight: 600; src: url(fonts/manrope-cyrillic-600-normal.woff2); unicode-range: U+0400-04FF; }}
@font-face {{ font-family: Manrope; font-weight: 600; src: url(fonts/manrope-latin-600-normal.woff2); }}
body {{ margin: 0; }}
#s {{ width: 1600px; height: 660px; display: flex; align-items: center; justify-content: center; gap: 34px; font-family: Manrope, sans-serif;
  background: radial-gradient(60% 70% at 15% 20%, #f3e3ef 0%, transparent 70%), radial-gradient(60% 70% at 85% 80%, #dfe6f5 0%, transparent 70%),
              linear-gradient(135deg, #eef0f5 0%, #dde3ed 100%); }}
figure {{ margin: 0; display: flex; flex-direction: column; align-items: center; gap: 18px; }}
img {{ width: 260px; border-radius: 26px; box-shadow: 0 30px 60px -20px rgba(20,30,60,.35), 0 10px 24px -12px rgba(20,30,60,.25); }}
.c2 img {{ width: 320px; }} .c1 img, .c3 img {{ width: 285px; }}
figcaption {{ font-size: 18px; font-weight: 600; color: #2a3140; letter-spacing: .01em; }}
</style><div id="s">{cards}</div>""", encoding="utf-8")
        pg2 = b.new_page(viewport={"width": 1600, "height": 660}, device_scale_factor=1.5)
        pg2.goto((tmp / "styles.html").as_uri())
        pg2.wait_for_timeout(600)
        pg2.locator("#s").screenshot(path=str(tmp / "styles.png"))
        b.close()
    im = Image.open(tmp / "styles.png").convert("RGB")
    if lang == "en":
        if SITE.is_dir():
            im.save(SITE / "dewiar_styles.en.webp", "WEBP", quality=86, method=6)
            print(SITE / "dewiar_styles.en.webp")
        return
    im.save(OUT / "styles.webp", "WEBP", quality=88, method=6)
    print(OUT / "styles.webp")
    if SITE.is_dir():
        im.save(SITE / "dewiar_styles.webp", "WEBP", quality=86, method=6)
        print(SITE / "dewiar_styles.webp")


if __name__ == "__main__":
    sys.exit(main())
