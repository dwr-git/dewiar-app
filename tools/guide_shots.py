"""Снимки экранов для руководства на сайте (server/dwrapp/guide): телефон и студия с аккуратными примерами, без
сервера — мост телефона и ядро студии подменены. Пишет server/dwrapp/guide-*.webp.
    python3 tools/guide_shots.py"""
import io, shutil, subprocess, sys, tempfile, time
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "server/dwrapp"
NOW = int(time.time() * 1000)


def save(png, name, w=None):
    im = Image.open(io.BytesIO(png)).convert("RGB")
    if w and im.width > w:
        im = im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)
    im.save(OUT / f"guide-{name}.webp", "WEBP", quality=86, method=6)
    print("guide-" + name + ".webp", im.size)


www = Path(tempfile.mkdtemp()) / "www"
shutil.copytree(ROOT / "android/assets/www", www)
for f in ("entities.js", "skins.css", "skins.js", "privacy.js", "closecrypto.js", "qrcode.js", "call.js", "codes.js", "vendor/zxing.min.js"):
    shutil.copy(ROOT / "ui/assets" / f, www / Path(f).name)
shutil.copytree(ROOT / "ui/assets/skins", www / "skins", dirs_exist_ok=True)
shutil.copytree(ROOT / "ui/assets/live", www / "live", dirs_exist_ok=True)
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                capture_output=True, text=True, check=True).stdout, encoding="utf-8")

PEOPLE = """[{ pid: 'pmama', name: 'Мама', devs: [{ dev: 'd1', pub: 'x' }] }, { pid: 'pand', name: 'Андрей', devs: [{ dev: 'd2', pub: 'x' }] },
             { pid: 'pkat', name: 'Катя', devs: [{ dev: 'd3', pub: 'x' }] }]"""
HIST = f"""{{ pmama: [
  {{ t: 'Ты сегодня приедешь к ужину?', ts: {NOW - 52 * 60000}, out: false, mid: 'a' }},
  {{ t: 'Да, буду к семи 🙂', ts: {NOW - 50 * 60000}, out: true, mid: 'b' }},
  {{ t: 'Купи, пожалуйста, хлеба по дороге', ts: {NOW - 31 * 60000}, out: false, mid: 'c' }},
  {{ t: 'Хорошо! И вот рецепт, о котором говорили', ts: {NOW - 29 * 60000}, out: true, mid: 'd', f: [{{ name: 'Пирог с яблоками.pdf', size: 248000 }}] }},
  {{ t: 'Спасибо, родной ❤️', ts: {NOW - 3 * 60000}, out: false, mid: 'e' }}],
  pand: [{{ t: 'Созвонимся вечером?', ts: {NOW - 3 * 3600000}, out: false, mid: 'f' }}],
  pkat: [{{ t: 'Фото с выходных', ts: {NOW - 26 * 3600000}, out: true, mid: 'g', f: [{{ name: 'дача.jpg', size: 2100000 }}] }}] }}"""

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 393, "height": 820}, device_scale_factor=2)
    pg.route("https://**", lambda r: r.abort())
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(1200)
    pg.evaluate("""() => { S.llm = Object.assign({}, S.llm, { cloud: true, api_key: 'dw-demo-key', model: 'chat' }); S.user_name = 'Миша'; saveS(); }""")
    # главный экран: разговор
    pg.evaluate("""() => { showYou('Напомни в пятницу в 15:00 позвонить Лёше'); showBot('Поставила: в пятницу в 15:00 — позвонить Лёше. Напомню и на часах.'); clearCard(); }""")
    pg.wait_for_timeout(500); save(pg.screenshot(), "phone-talk", 600)
    # «Близкие»: переписка с мамой
    pg.evaluate(f"""() => {{ const st = clLoad(); st.people = {PEOPLE}; st.hist = {HIST}; st.unread = {{ pand: 1 }}; st.me = {{ name: 'Миша' }};
      clHello = async () => {{}}; openClose('pmama'); }}""")
    pg.wait_for_timeout(600); save(pg.screenshot(), "phone-close-chat", 600)
    # «Близкие»: список и печать-приглашение
    pg.evaluate("""() => { clCur = ''; clRender(); clInvShow({ link: 'https://dewiar.pro/dwrapp/download?close=Gh7xQ2LmP9aKz3Vt', expires: Date.now() / 1000 + 6 * 86400 }); }""")
    pg.wait_for_timeout(600); save(pg.screenshot(), "phone-close-invite", 600)
    pg.close()

    # студия: «Близкие» в светлой теме — переписка и печать
    pg = b.new_page(viewport={"width": 1280, "height": 800}, device_scale_factor=1.5)
    pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) }; localStorage.setItem('studio_skin', 'snow');")
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(1200)
    pg.evaluate(f"""() => {{ const H = {HIST}, P = {PEOPLE}.map(x => Object.assign(x, {{ last: (H[x.pid] || []).slice(-1)[0], unread: x.pid === 'pand' ? 1 : 0 }}));
      core.call = (c, a) => c === 'close_state' ? Promise.resolve({{ me: {{ name: 'Миша' }}, people: P }})
        : c === 'close_history' ? Promise.resolve(H[a.pid] || []) : c === 'close_invite' ? Promise.resolve({{ link: 'https://dewiar.pro/dwrapp/download?close=Gh7xQ2LmP9aKz3Vt' }}) : Promise.resolve({{}});
      if (window.studioSkin) studioSkin('snow'); $('nav button[data-p="close"]').click(); }}""")
    pg.wait_for_timeout(900); pg.evaluate("async () => { await loadClose(); await clOpen('pmama'); }"); pg.wait_for_timeout(500)
    save(pg.screenshot(), "studio-close", 1600)
    pg.click("#cl-inv-go"); pg.wait_for_timeout(600)
    save(pg.locator("#cl-invite").screenshot(), "studio-seal", 1000)
    b.close()

# превью ссылки-приглашения в «Близкие» для мессенджеров (download.php?close=… → og:image): 1200×630
F = ROOT / "android/assets/www/fonts"
card = f"""<!doctype html><meta charset=utf-8><style>
@font-face {{ font-family: U; src: url('{(F / "unbounded-cyrillic-600-normal.woff2").as_uri()}'); }}
@font-face {{ font-family: U; src: url('{(F / "unbounded-latin-600-normal.woff2").as_uri()}'); }}
@font-face {{ font-family: M; font-weight: 600; src: url('{(F / "manrope-cyrillic-600-normal.woff2").as_uri()}'); }}
@font-face {{ font-family: M; font-weight: 400; src: url('{(F / "manrope-cyrillic-400-normal.woff2").as_uri()}'); }}
body {{ margin: 0; width: 1200px; height: 630px; overflow: hidden; color: #F4F4F6; font-family: M, sans-serif;
  background: radial-gradient(circle at 18% 85%, rgba(120,119,198,.38), transparent 52%), radial-gradient(circle at 80% 10%, rgba(255,119,198,.30), transparent 50%),
  linear-gradient(135deg, #0a0a0f, #1a1a2e 55%, #16213e); position: relative; }}
.t {{ position: absolute; left: 76px; top: 92px; width: 640px; }}
.b {{ font: 600 22px U, sans-serif; display: flex; align-items: center; gap: 12px; color: rgba(255,255,255,.8); }}
.b i {{ width: 34px; height: 34px; border-radius: 10px; background: linear-gradient(135deg,#667eea,#764ba2); display: grid; place-items: center; font-style: normal; }}
h1 {{ font: 600 60px/1.08 U, sans-serif; margin: 40px 0 22px; letter-spacing: -.01em; }}
p {{ font-size: 26px; line-height: 1.45; color: rgba(255,255,255,.72); margin: 0 0 34px; }}
.c {{ display: flex; gap: 12px; }} .c span {{ font-weight: 600; font-size: 21px; padding: 12px 20px; border-radius: 999px; background: rgba(255,255,255,.09); }}
.ph {{ position: absolute; right: 70px; top: 60px; width: 330px; height: 690px; border-radius: 44px; overflow: hidden;
  box-shadow: 0 0 0 10px rgba(255,255,255,.06), 0 40px 90px -20px rgba(118,75,162,.8); background: url('{(OUT / "guide-phone-close-chat.webp").as_uri()}') top / cover; }}
</style><div class=t><div class=b><i>💌</i>Dewiar</div><h1>Вас зовут<br>в «Близкие»</h1>
<p>Помощники пишут и звонят друг другу. Dewiar уже есть — откройте ссылку и добавьтесь.</p>
<div class=c><span>Сообщения</span><span>Файлы</span><span>Звонки</span></div></div><div class=ph></div>"""
tmp = Path(tempfile.mkdtemp()) / "og.html"; tmp.write_text(card, encoding="utf-8")
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1200, "height": 630})
    pg.goto(tmp.as_uri()); pg.wait_for_timeout(600)
    Image.open(io.BytesIO(pg.screenshot())).convert("RGB").save(OUT / "dewiar_close.jpg", "JPEG", quality=88, optimize=True, progressive=True)
    print("dewiar_close.jpg (1200, 630)")
    b.close()
