"""Идея №144 (05.11): «новичок долго не понимал, что включать в настройках Android после „Включить“ в Dewiar — пять раз
переключался между экранами». Теперь у «Управлять приложениями» — шаги с названиями пунктов как на экране (у Xiaomi,
Samsung, Huawei — их подписи), что делать, если Dewiar серый («Ограниченная настройка» Android 13+), и «Что-то не так?»."""
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
for x in ("entities.js", "rich.js", "skins.js", "skins.css", "privacy.js", "closecrypto.js", "qrcode.js", "call.js", "codes.js"):
    if (ROOT / "ui/assets" / x).exists():
        shutil.copy(ROOT / "ui/assets" / x, www / x)
shutil.copytree(ROOT / "ui/assets/live", www / "live", dirs_exist_ok=True)
shutil.copytree(ROOT / "ui/assets/arcade", www / "arcade", dirs_exist_ok=True)
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                capture_output=True, text=True, check=True).stdout, encoding="utf-8")
errs = []
with sync_playwright() as p:
    b = p.chromium.launch()
    for sdk, dev, want in ((33, "Xiaomi 2201117TG", "Скачанные приложения"), (34, "samsung SM-A546E", "Установленные приложения"), (30, "Google Pixel 4", "Скачанные приложения")):
        pg = b.new_page(viewport={"width": 393, "height": 852}); pg.on("pageerror", lambda x: errs.append(str(x)))
        pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(900)
        pg.evaluate("""([sdk, dev]) => { D.info = () => JSON.stringify({ sdk, device: dev, version: 'x' }); D.handsState = () => '';
            S.onboarded = true; setTab = 'hands'; openSettings('hands'); }""", [sdk, dev])
        pg.wait_for_timeout(400)
        t = pg.evaluate("() => { const c = document.querySelector('#hands-card'); return c ? c.innerText : ''; }")
        n = pg.evaluate("() => document.querySelectorAll('#hands-card .hguide > li').length")
        if sdk >= 33:
            ok(n == 3 and "Разрешить ограниченные настройки" in t and "Пункта ⋮ нет?" in t and want in t and "Использовать Dewiar" in t,
               f"Android {sdk}, {dev.split()[0]}: три шага, «Разрешить ограниченные настройки», куда нажать — «{want}»: {n}")
            ok(pg.evaluate("!!document.querySelector('#hands-app') && !!document.querySelector('#hands-go')"), "две кнопки: «1. Страница Dewiar», «2. Включить»")
        else:
            ok(n == 2 and "ограниченные" not in t and want in t, f"Android {sdk}: без шага про ограниченные настройки: {n}")
        pg.evaluate("() => document.querySelector('#hands-card .hfaq').open = true"); pg.wait_for_timeout(100)
        t = pg.evaluate("() => document.querySelector('#hands-card').innerText")
        ok("Dewiar серый" in t and "Автозапуск" in t and "полный контроль" in t, f"«Что-то не так?» — серый, выключилось, предупреждение Android")
        if os.environ.get("DEWIAR_SHOTS") and sdk == 33:
            pg.screenshot(path=str(Path(os.environ["DEWIAR_SHOTS"]) / "phone-hands144.png"), full_page=True)
        pg.close()
    b.close()
ok(not errs, f"без ошибок на странице: {errs[:3]}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
