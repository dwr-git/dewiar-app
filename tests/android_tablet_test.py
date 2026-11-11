"""Телефонное приложение на планшете (жалоба №13, 11.10: планшет Huawei лёжа — «иконки расположены хаотично»).
app.js в Chromium размером планшета лёжа (1074×711 и 1280×800), светлая и тёмная темы:
— облик, ответ и панель внизу — в одной полосе: левый край облика не левее кнопки клавиатуры, конец ответа — у кнопки
  разговора, микрофон — по центру; облик целиком в своей колонке;
— снимок для жалобы — PixelCopy (то, что правда на экране), в жалобе и пульсе — версия WebView."""
import os, shutil, subprocess, sys, tempfile
from pathlib import Path
SRC = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


from playwright.sync_api import sync_playwright  # noqa: E402
www = Path(tempfile.mkdtemp()) / "www"
shutil.copytree(SRC / "android/assets/www", www)
for f in ("entities.js", "skins.css", "skins.js", "privacy.js", "closecrypto.js", "qrcode.js", "codes.js", "call.js", "refnet.js", "vendor/zxing.min.js"):
    shutil.copy(SRC / "ui/assets" / f, www / Path(f).name)
shutil.copytree(SRC / "ui/assets/skins", www / "skins")
(www / "personas.js").write_text(subprocess.run([sys.executable, str(SRC / "android/tools/personas_json.py"), str(SRC)],
                                                capture_output=True, text=True, check=True).stdout, encoding="utf-8")
GEOM = """() => { const r = (s) => { const b = document.querySelector(s).getBoundingClientRect(); return [Math.round(b.left), Math.round(b.right), Math.round(b.top), Math.round(b.bottom)]; };
  return { orb: r('#orbwrap'), bot: r('#bot'), kb: r('#b-kb'), hist: r('#b-hist'), mic: r('#mic'), w: innerWidth }; }"""
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    for vw in ((1074, 711), (1280, 800)):
        pg = b.new_page(viewport={"width": vw[0], "height": vw[1]}); pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.route("https://**", lambda r: r.abort())
        pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(800)
        for skin in ("snow", "brand"):
            pg.evaluate("(k) => { S.skin = k; saveS(); applyLook(); showYou('Лира привет'); showBot('Чтобы думать, мне нужен «мозг»: своя модель, ключ любимого сервиса или Dewiar.'); }", skin)
            pg.wait_for_timeout(500)
            g = pg.evaluate(GEOM)
            mic_c = (g["mic"][0] + g["mic"][1]) / 2
            # 0.9.32 (отчёты 657, 658): на планшете слева меню разделов — «по центру» значит по центру места правее него
            rail = pg.evaluate("(() => { const r = document.querySelector('#rail'); return r && getComputedStyle(r).display !== 'none' ? r.getBoundingClientRect().right : 0; })()")
            ok(g["orb"][0] >= g["kb"][0] - 2 and g["bot"][1] <= g["hist"][1] + 2 and g["bot"][0] > g["orb"][1] and abs(mic_c - (rail + g["w"]) / 2) < 3
               and g["orb"][1] - g["orb"][0] >= 200,
               f"{vw[0]}×{vw[1]} {skin}: облик и ответ — между кнопкой клавиатуры и кнопкой разговора, микрофон по центру: {g}")
        pg.close()
    b.close()
ok(not errs, f"без ошибок на странице: {errs[:3]}")
br = (SRC / "android/src/pro/dewiar/app/Bridge.java").read_text(encoding="utf-8")
app = (SRC / "android/assets/www/app.js").read_text(encoding="utf-8")
ok("android.view.PixelCopy" in br and "drawSnapshot()" in br and "webviewVer()" in app and "webview: webviewVer()" in app,
   "жалоба: снимок — PixelCopy (запасной — как раньше), версия WebView — в жалобе и пульсе")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
