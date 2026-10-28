"""Телефон (0.60; владелец 28.10: «сверху иконок многовато, а внутренние разделы перегружены — захожу в „Ещё“ и скроллю,
скроллю»; «проверь, чтобы новая иконка была в один уровень»). Настройки — меню по группам (строка: что выбрано сейчас),
нажали — один раздел со стрелкой «назад»; «Ещё» (старое имя) — меню. Вверху — звук, «Близкие», день, «Всё», настройки:
«Досуг» и «Душа» — плитками во «Всё»; значок «Всё» — ровно в ряд; в детском режиме во «Всё» — только безопасное."""
import os, shutil, subprocess, sys, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
SHOTS = Path(os.environ.get("DEWIAR_SHOTS") or tempfile.mkdtemp())
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


w = Path(tempfile.mkdtemp()) / "www"
subprocess.run(["bash", str(ROOT / "android/tools/www_assemble.sh"), str(w)], check=True, capture_output=True)
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 393, "height": 852}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route("https://**", lambda r: r.abort())
    pg.goto((w / "index.html").as_uri()); pg.wait_for_timeout(1000)
    vis = pg.evaluate("() => [...document.querySelectorAll('#top .ib')].filter(b => b.offsetParent !== null).map(b => b.id)")
    ok(vis == ["b-voice", "b-close", "b-day", "b-apps", "b-set"], f"вверху — звук, «Близкие», день, «Всё», настройки: {vis}")
    tops = pg.evaluate("() => ['b-day', 'b-apps', 'b-set'].map(id => { const r = document.querySelector('#' + id + ' svg').getBoundingClientRect(); return [Math.round(r.top), Math.round(r.height)]; })")
    ok(len({t for t, h in tops}) == 1 and len({h for t, h in tops}) == 1, f"значок «Всё» — в один уровень с соседями: {tops}")
    pg.click("#b-set"); pg.wait_for_timeout(400)
    groups = pg.evaluate("() => [...document.querySelectorAll('#set-body h3')].map(h => h.textContent)")
    ok(groups == ["Главное", "Вид и звук", "Подключения", "Помощь и связь"], f"меню по группам: {groups}")
    rows = pg.evaluate("() => [...document.querySelectorAll('#set-body .setrow')].map(r => r.dataset.st || r.id)")
    ok(rows[:3] == ["brain", "voice", "devices"] and "bug" in rows and "about" in rows and "ideas-open" in rows, f"строки разделов: {rows}")
    sub = pg.evaluate("() => document.querySelector('.setrow[data-st=look] small').textContent")
    ok(sub == "Небесный", f"под строкой — что выбрано сейчас: «Оформление» — {sub}")
    pg.screenshot(path=str(SHOTS / "phone-menu.png"))
    pg.click(".setrow[data-st=sound]"); pg.wait_for_timeout(300)
    r = pg.evaluate("() => [setTab, document.querySelector('#set-body .sethd h2').textContent, document.querySelectorAll('#set-body .snd').length > 3, !!document.querySelector('#set-body .skins'), getComputedStyle(document.querySelector('#sh-set > h2')).display]")
    ok(r[:4] == ["sound", "Звук напоминаний", True, False] and r[4] == "none", f"раздел — только он, заголовок и стрелка «назад»: {r}")
    pg.click(".setback"); pg.wait_for_timeout(300)
    ok(pg.evaluate("setTab") == "menu" and pg.locator("#set-body .setrow").count() == len(rows), "«назад» — к меню")
    pg.evaluate("openSettings('more')"); pg.wait_for_timeout(300)
    ok(pg.evaluate("setTab") == "menu", "старое «Ещё» открывает меню")
    pg.evaluate("closeSheets()"); pg.wait_for_timeout(300)
    pg.click("#b-apps"); pg.wait_for_timeout(400)
    apps = pg.evaluate("() => [...document.querySelectorAll('#apps-body [data-app]')].map(b => b.dataset.app)")
    ok(apps[:2] == ["play", "soul"] and {"ideas", "tricks", "course", "qa", "kids", "news", "work"} <= set(apps), f"«Всё»: Досуг, Душа, Работа, Идеи, обучение: {apps}")
    pg.screenshot(path=str(SHOTS / "phone-apps.png"))
    pg.click("[data-app=soul]"); pg.wait_for_timeout(500)
    ok(pg.evaluate("document.querySelector('#sh-soul').classList.contains('on')"), "«Душа» открывается из «Всё»")
    pg.evaluate("closeSheets(); S.kids = Object.assign({}, S.kids || {}, { on: true }); saveS();"); pg.wait_for_timeout(200)
    kid = pg.evaluate("() => kidsOn() ? [...new DOMParser().parseFromString(appsHtml(), 'text/html').querySelectorAll('[data-app]')].map(b => b.dataset.app) : null")
    if kid is not None:
        ok("soul" not in kid and "work" not in kid and "ideas" not in kid and "kids" in kid, f"детский режим — во «Всё» только безопасное: {kid}")
    ok(not errs, f"без ошибок: {errs[:3]}")
    b.close()
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
