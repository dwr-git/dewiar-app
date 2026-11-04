"""№216 (23.10): компьютер и телефон — каждый со своей заявкой «Подключить бесплатно»: два ключа, синхронизация у каждого
своя, и на телефоне ни заметок, ни блокнота с компьютера. Теперь на втором устройстве первым делом — «Dewiar уже есть на
компьютере или другом телефоне? Введите код»: на телефоне — на первом экране и над заявкой, в студии — над заявкой."""
import os, shutil, subprocess, sys, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


html = (ROOT / "ui/settings.html").read_text(encoding="utf-8")
i = html.find('id="dk-have"')
ok(0 < i < html.find('id="dk-join"') and "Добавить устройство" in html[i:i + 600] and 'id="dk-have-go"' in html[i:i + 600],
   "студия: «Dewiar уже есть на другом устройстве?» — над заявкой, с кнопкой «Ввести код»")
tmp = Path(tempfile.mkdtemp()); www = tmp / "www"
shutil.copytree(ROOT / "android/assets/www", www)
shutil.copy(ROOT / "ui/assets/entities.js", www / "entities.js")
shutil.copytree(ROOT / "ui/assets/live", www / "live", dirs_exist_ok=True)
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                capture_output=True, text=True, check=True).stdout, encoding="utf-8")
try:
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page(viewport={"width": 390, "height": 844}); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(1200)
        btns = pg.evaluate("() => [...document.querySelectorAll('#card .start .btn')].map(b => b.textContent.trim())")
        ok(len(btns) == 3 and btns[0] == "Подключить мозг Dewiar" and "уже есть на компьютере" in btns[1], f"первый экран: бесплатно / уже есть — код / свой ключ: {btns}")
        pg.evaluate("() => openBrain('join')"); pg.wait_for_timeout(700)
        ok(pg.evaluate("() => { const h = document.querySelector('.card.have'), j = document.getElementById('w-go'); return !!h && !!j && (h.compareDocumentPosition(j) & 4) > 0; }"),
           "над заявкой — «Dewiar уже есть на компьютере или другом телефоне?»")
        pg.click("#w-have"); pg.wait_for_timeout(600)
        ok(pg.evaluate("() => !!document.getElementById('w-key')"), "«Ввести код» — поле для кода из 6 цифр")
        ok(not errs, f"без ошибок: {errs[:2]}")
        b.close()
finally:
    shutil.rmtree(tmp, ignore_errors=True)

if fails:
    raise SystemExit(1)
