"""Телефон, шапка (отзыв 15.10: «нажатая кнопка „без голоса“ — приплюснутым овалом»): кнопки шапки всегда круглые на
любой ширине — на узком экране сжимаются не они, а имя персонажа (стрелка прячется, имя — многоточием); страница не
шире экрана."""
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
for x in ("entities.js", "rich.js", "skins.js", "skins.css"):
    if (ROOT / "ui/assets" / x).exists():
        shutil.copy(ROOT / "ui/assets" / x, www / x)
shutil.copytree(ROOT / "ui/assets/live", www / "live", dirs_exist_ok=True)
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                capture_output=True, text=True, check=True).stdout, encoding="utf-8")
errs = []
with sync_playwright() as p:
    b = p.chromium.launch()
    for w in (320, 340, 360, 393, 414, 480):
        pg = b.new_page(viewport={"width": w, "height": 760})
        pg.on("pageerror", lambda x: errs.append(str(x)))
        pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(700)
        pg.evaluate("() => document.getElementById('b-voice').classList.add('off')")
        r = pg.evaluate("""() => ({ ib: [...document.querySelectorAll('#top .ib')].filter(e => !e.hidden).map(e => { const b = e.getBoundingClientRect(); return [b.width, b.height, b.right]; }),
            sw: document.documentElement.scrollWidth, name: (() => { const s = document.getElementById('who-name'); return [s.scrollWidth, s.clientWidth]; })() })""")
        round_ = all(abs(a - h) < 0.5 and a >= 36 for a, h, _ in r["ib"])
        ok(round_ and max(x for _, _, x in r["ib"]) <= w and r["sw"] <= w, f"{w} px: кнопки шапки круглые и на экране: {[(round(a), round(h)) for a, h, _ in r['ib']]}")
        if w >= 340:
            ok(r["name"][0] <= r["name"][1] + 1, f"{w} px: имя «Лира» целиком: {r['name']}")
        # «Работа» (0.55): портфель — седьмой значок вместе с «Досугом»; всё на экране, значки круглые, имя прячется, лицо остаётся
        pg.evaluate("() => { document.getElementById('b-work').hidden = false; document.getElementById('b-play').hidden = false; }")
        r = pg.evaluate("""() => ({ ib: [...document.querySelectorAll('#top .ib')].filter(e => !e.hidden && e.offsetWidth).map(e => { const b = e.getBoundingClientRect(); return [b.width, b.height, b.right]; }),
            sw: document.documentElement.scrollWidth, who: document.getElementById('who').getBoundingClientRect().width })""")
        ok(len(r["ib"]) == 6 and all(abs(a - h) < 0.5 and a >= 34 for a, h, _ in r["ib"]) and max(x for _, _, x in r["ib"]) <= w and r["sw"] <= w and r["who"] >= 40,
           f"{w} px, шесть значков (с «Работой»; «Досуг» с 0.60 — во «Всё»): круглые, на экране, лицо персонажа видно: {[(round(a), round(h)) for a, h, _ in r['ib']]} who={round(r['who'])}")
        pg.close()
    b.close()
ok(not errs, "без ошибок JavaScript" + (f": {errs}" if errs else ""))
shutil.rmtree(tmp, ignore_errors=True)
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
