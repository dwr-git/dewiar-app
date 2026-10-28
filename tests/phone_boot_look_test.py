"""Телефон, отзывы 14.10:
1. «Опять „С возвращением. В 15:00 встреча с подрядчиком“ — сразу после обновления» (отчёты №52, №53): это был не новый
   ответ, а последний старый, который приложение показывало при каждом запуске. Теперь при запуске — только свежий
   (до 20 минут); старый остаётся в истории разговора.
2. «Темы — некрасивые прямоугольники, занимают кучу места»: круглые образцы, все темы в несколько строк, выбранная —
   с кольцом."""
import json, os, shutil, subprocess, sys, tempfile, time
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
for f in ("entities.js", "rich.js", "skins.js", "skins.css"):                     # как build_apk.sh
    if (ROOT / "ui/assets" / f).exists():
        shutil.copy(ROOT / "ui/assets" / f, www / f)
shutil.copytree(ROOT / "ui/assets/live", www / "live", dirs_exist_ok=True)
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                capture_output=True, text=True, check=True).stdout, encoding="utf-8")
errs = []
now = int(time.time() * 1000)
OLD = "С возвращением. В 15:00 у тебя встреча с подрядчиком по кухне."


def boot(pg, hist):
    pg.evaluate("""(h) => { S.llm.base_url = 'http://127.0.0.1:9/v1'; S.llm.model = 'm'; S.welcome = { on: false }; saveS();
        history = h; saveH(); }""", hist)                   # через само приложение: при уходе со страницы оно сохраняет S
    pg.reload(); pg.wait_for_timeout(1500)
    return pg.evaluate("() => document.getElementById('bot').textContent")


with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 400, "height": 820})
    pg.on("pageerror", lambda x: errs.append(str(x)))
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(1000)
    q = {"role": "user", "content": "Как дела"}
    ok(boot(pg, [q, {"role": "assistant", "content": OLD, "who": "lira", "t": now - 4 * 3600e3}]) == "",
       "ответ четырёхчасовой давности при запуске не показывается")
    ok(boot(pg, [q, {"role": "assistant", "content": OLD, "who": "lira"}]) == "", "старый ответ без времени (из прежних версий) — тоже нет")
    ok(boot(pg, [q, {"role": "assistant", "content": "Всё хорошо, спасибо!", "who": "lira", "t": now - 5 * 60e3}]) == "Всё хорошо, спасибо!",
       "свежий ответ (5 минут) — на месте, как раньше")
    ok(pg.evaluate("() => history.some(m => m.content === 'Всё хорошо, спасибо!')"), "история разговора не тронута")
    # темы
    pg.evaluate("() => openSettings('look')"); pg.wait_for_timeout(700)
    T = pg.evaluate("""() => { const box = document.querySelector('#sh-set .skins'), items = [...box.querySelectorAll('.skm')];
        const i0 = items[0].querySelector('i').getBoundingClientRect();
        return { n: items.length, h: box.getBoundingClientRect().height, w: i0.width, round: getComputedStyle(items[0].querySelector('i')).borderRadius,
                 on: items.filter(x => x.classList.contains('on')).length, groups: document.querySelectorAll('#sh-set .skg').length,
                 radios: items.every(x => x.getAttribute('role') === 'radio') }; }""")
    ok(T["n"] >= 10 and T["w"] <= 46 and T["round"] == "50%" and T["groups"] == 0 and T["on"] == 1 and T["radios"],
       f"темы — круглые образцы без громоздких групп, выбрана одна: {T}")
    ok(T["h"] <= 80 * ((T["n"] + 3) // 4) + 20, f"компактно: {T['n']} тем в {T['h']:.0f} px (раньше — несколько экранов)")
    pg.click("#sh-set .skm[data-skin='graphite']"); pg.wait_for_timeout(300)
    ok(pg.evaluate("() => [S.skin, document.querySelector('#sh-set .skm.on').dataset.skin, document.querySelector('#sh-set .skm[data-skin=graphite]').getAttribute('aria-checked')]")
       == ["graphite", "graphite", "true"], "нажали — тема выбрана")
    b.close()
ok(not errs, "без ошибок JavaScript" + (f": {errs}" if errs else ""))
shutil.rmtree(tmp, ignore_errors=True)
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
