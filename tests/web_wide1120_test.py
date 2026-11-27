"""Владелец 20.11, веб-версия на мониторе 1900 точек: «блок сообщений урезанный и кривой; скролл слева грубый и не в цвет;
середину и сообщения ограничить максимальной шириной». Полоса «облик слева, ответ справа» считала ширину от окна, а не от
области правее меню — ответу оставалось 270 точек. Теперь верх, облик с ответом и поле ввода — одной полосой до 1040 точек по
центру области разговора, ответ — до 680; раздел открыт рядом — разговор колонкой по центру оставшегося; прокрутка тонкая."""
import os, shutil, subprocess, sys, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


www = Path(tempfile.mkdtemp()) / "www"
shutil.copytree(ROOT / "android/assets/www", www)
for f in ("entities.js", "skins.css", "skins.js", "privacy.js"):
    shutil.copy(ROOT / "ui/assets" / f, www / f)
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                capture_output=True, text=True, check=True).stdout, encoding="utf-8")
TXT = "Привет. В мире физики случилось необычное: впервые передали сообщение с помощью гравитации. " * 2
box = "(s) => { const r = document.querySelector(s).getBoundingClientRect(); return [Math.round(r.left), Math.round(r.right), Math.round(r.width)]; }"
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    for w, h in ((1910, 1046), (1280, 800)):
        pg = b.new_page(viewport={"width": w, "height": h}); pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.route("https://**", lambda r: r.abort())
        pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(1200)
        pg.evaluate(f"() => {{ showYou('Что нового в физике?'); showBot({TXT!r}); }}"); pg.wait_for_timeout(500)
        tab = pg.evaluate("document.body.classList.contains('tab')")
        bot, bar, stage = pg.evaluate(box, "#bot"), pg.evaluate(box, "#bar"), pg.evaluate(box, "#stage")
        mid = (stage[0] + stage[1]) / 2
        ok(tab and 560 <= bot[2] <= 690, f"{w}: ответ — широкой колонкой, не 270 ({bot[2]})")
        ok(bot[1] <= mid + 520 + 2, f"{w}: ответ — в полосе по центру области разговора")
        pad = pg.evaluate("parseFloat(getComputedStyle(document.querySelector('#bar')).paddingLeft)")
        ok(abs((bar[0] + pad) - (mid - min(520, (stage[2] - 48) / 2))) < 3, f"{w}: поле ввода — той же полосой")
        tp = pg.evaluate("parseFloat(getComputedStyle(document.querySelector('#talk')).paddingRight)")
        ok(tp >= 20, f"{w}: у колонки ответа поля под тень — светлая тень пузыря не режется ({tp})")
        sb = pg.evaluate("getComputedStyle(document.querySelector('#rail')).scrollbarWidth")
        ok(sb == "thin", f"{w}: прокрутка меню тонкая ({sb})")
        if w == 1910:
            pg.evaluate("() => openSettings('about')"); pg.wait_for_timeout(700)
            t = pg.evaluate(box, "#talk")
            ok(t[2] <= 722, f"раздел открыт рядом — разговор колонкой до 720 с полями под тень ({t[2]})")
        pg.close()
    b.close()
ok(not errs, f"без ошибок на странице: {errs[:3]}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
