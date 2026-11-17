"""Пакет 17.11 10:30. №813: «нет возможности изменить размер текста в приложении — неудобно тем, у кого проблемы со
зрением» — телефон следует системному «Размеру шрифта» Android: всё приложение крупнее пропорционально, до ×1,3, без
прокрутки вбок. №815: «не работает большинство радиостанций» (на снимке включён VPN) — станция не ответила, а VPN включён:
подсказка про VPN, а не только «попробуйте другую»."""
import os, shutil, subprocess, sys, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


tmp = Path(tempfile.mkdtemp()); www = tmp / "www"
shutil.copytree(ROOT / "android/assets/www", www)
for f in ("entities.js", "rich.js", "skins.js", "skins.css", "speechnorm.js"):
    if (ROOT / "ui/assets" / f).exists():
        shutil.copy(ROOT / "ui/assets" / f, www / f)
shutil.copytree(ROOT / "ui/assets/live", www / "live", dirs_exist_ok=True)
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                capture_output=True, text=True, check=True).stdout, encoding="utf-8")
with sync_playwright() as p:
    b = p.chromium.launch()
    for scale, want in ((1.0, ""), (1.15, "1.15"), (2.0, "1.3")):
        pg = b.new_page(viewport={"width": 390, "height": 844}); errs = []
        pg.on("pageerror", lambda x: errs.append(str(x)))
        pg.add_init_script(f"window.DewiarWeb = (s) => Object.assign(s, {{ fontScale: () => {scale} }});")
        pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(1200)
        z = pg.evaluate("document.documentElement.style.zoom")
        sw = pg.evaluate("document.documentElement.scrollWidth")
        ok(z == want and not errs, f"системный шрифт ×{scale} — приложение ×{want or '1'} ({z!r}) {errs[:1]}")
        ok(sw <= 390, f"×{scale}: без прокрутки вбок ({sw} px)")
        pg.evaluate("() => { try { openSettings(''); } catch (e) {} }"); pg.wait_for_timeout(600)
        top = pg.evaluate("(() => { const s = document.querySelector('.sheet.on'); return s ? s.getBoundingClientRect().top * (parseFloat(document.documentElement.style.zoom) || 1) : -1; })()")
        ok(top > 20, f"×{scale}: лист настроек целиком на экране — ручка и «назад» видны (верх {top:.0f} px)")
        pg.close()
    b.close()
js = (ROOT / "android/www-src/app/01-bridge.js").read_text(encoding="utf-8")
ok('N.on("resume", () => { appPaused = false; fontApply(); });' in js, "поменяли размер шрифта в настройках Android — вернулись, и приложение уже крупнее")
br = (ROOT / "android/src/pro/dewiar/app/Bridge.java").read_text(encoding="utf-8")
ok("@JavascriptInterface public float fontScale()" in br and "getConfiguration().fontScale" in br, "мост отдаёт системный размер шрифта")
ma = (ROOT / "android/src/pro/dewiar/app/MainActivity.java").read_text(encoding="utf-8")
ok("s.setTextZoom(100);" in ma, "WebView не раздувает только текст (вёрстка не ломается) — увеличение целиком, в app.js")
ra = (ROOT / "android/src/pro/dewiar/app/Radio.java").read_text(encoding="utf-8")
ok("TRANSPORT_VPN" in ra and "похоже, мешает VPN" in ra, "№815: станция не ответила при включённом VPN — подсказка про VPN")
dj = (ROOT / "ui/assets/dewiar.js").read_text(encoding="utf-8")
ok("reject(new Error(NO_CORE))" in dj and "закройте Dewiar" in dj and 'new Error("нет связи с ядром")' in dj,
   "№814: ядро не ответило — в ошибке сказано, что делать; обрыв посреди вызова — прежний текст (его ловят по словам)")
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
