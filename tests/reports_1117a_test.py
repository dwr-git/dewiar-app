"""Пакет 17.11, №802: в виджете при длинной подсказке («Микрофон почти ничего не слышит…») кнопка «Написать» открывала
поле вопроса за нижним краем — видно было только «Shift+Enter — новая строка». Пока поле открыто, подсказка — одной
строкой (целиком — во всплывающей подсказке), поле ввода целиком в окне при любой высоте виджета."""
import os, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


NOTE = ("Микрофон почти ничего не слышит. Проверьте, что выбран нужный микрофон в настройках системы, что он не выключен "
        "кнопкой на гарнитуре и что программе разрешён доступ к нему. Если микрофон внешний — переподключите его.")
with sync_playwright() as p:
    b = p.chromium.launch()
    for h in (290, 330, 420):
        pg = b.new_page(viewport={"width": 300, "height": h}); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };")
        pg.goto((ROOT / "ui/hud.html").as_uri() + "?mode=card"); pg.wait_for_timeout(1200)
        pg.evaluate("t => { document.getElementById('note').textContent = t; }", NOTE)
        pg.click("#b-type"); pg.wait_for_timeout(400)
        r = pg.evaluate("""() => { const a = document.getElementById('askin').getBoundingClientRect(),
            n = document.getElementById('note'); return { bottom: a.bottom, top: a.top, h: innerHeight,
            note: n.getBoundingClientRect().height, title: n.title }; }""")
        ok(r["top"] >= 0 and r["bottom"] <= r["h"], f"высота {h}: поле вопроса целиком в окне ({r['top']:.0f}–{r['bottom']:.0f} из {h})")
        ok(r["note"] <= 24, f"высота {h}: подсказка не выше строки, пока открыто поле ({r['note']:.0f} px)")
        if r["note"]:
            ok(r["title"] == NOTE, f"высота {h}: подсказка целиком — при наведении")
        pg.fill("#askin", "привет"); pg.click("#b-type"); pg.wait_for_timeout(300)
        n = pg.evaluate("document.getElementById('note').getBoundingClientRect().height")
        ok(h < 330 or n > 40, f"высота {h}: поле закрыто — подсказка снова целиком ({n:.0f} px)")
        pg.close()
    # №288 (идеи 17.11): «только новую скачал — при запуске уже ОПЯТЬ обнова». Вопрос «обновить сейчас?» — не раньше чем
    # через 3 суток с установки нынешней версии; значок и строка — сразу
    pg = b.new_page(viewport={"width": 300, "height": 520})
    pg.clock.install()
    pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };")
    pg.goto((ROOT / "ui/hud.html").as_uri() + "?mode=card"); pg.clock.run_for(1500)
    asked = lambda: "1.0.99" in pg.inner_text("#cap") and pg.evaluate("document.getElementById('cap').classList.contains('show')")
    pg.evaluate("""() => { CUR_VER = '1.0.98'; updSince(CUR_VER); state = 'idle'; showUpd({ available: { version: '1.0.99' } }); }""")
    pg.clock.run_for(25000)
    ok(not asked(), "свежая версия (меньше 3 суток) — вопрос об обновлении не всплывает")
    ok(pg.evaluate("document.getElementById('b-upd').classList.contains('has')"), "значок обновления у кнопки — сразу")
    pg.evaluate("""() => { localStorage.setItem('upd_since', JSON.stringify({ '1.0.98': Date.now() - 4 * 86400e3 }));
                           localStorage.removeItem('upd_ask'); showUpd({ available: { version: '1.0.99' } }); }""")
    pg.clock.run_for(25000)
    ok(asked(), "через 3 суток — спрашивает, как раньше (раз в сутки)")
    pg.close()
    b.close()
# «Пульт» (владелец 17.11: «коричневый цвет заменить на другой — какой-то он грустноватый»): Радар в светлой теме —
# насыщенный (не бурый) и читается на листе
import colorsys, re  # noqa: E402
m = re.search(r"body\.light \{[^}]*--pu-radar: (#[0-9a-fA-F]{6})", (ROOT / "ui/pad.html").read_text(encoding="utf-8"))
rgb = [int(m.group(1)[i:i + 2], 16) / 255 for i in (1, 3, 5)] if m else [0, 0, 0]
lum = lambda c: 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
lin = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in rgb]
h, l, sat = colorsys.rgb_to_hls(*rgb)
ok(m and sat >= 0.8 and l >= 0.4 and (lum([0.792, 0.827, 0.906]) + 0.05) / (lum(lin) + 0.05) >= 4.2,
   f"Радар в светлом «Пульте» — живой цвет, читается: {m and m.group(1)} (насыщенность {sat:.2f}, светлота {l:.2f})")
# №292 (идеи 17.11): «поле ответа в „Вопросах и ответах“ — побольше»: текстовые поля конструктора сайтов растут с текстом
css = (ROOT / "ui/studio/sites.css").read_text(encoding="utf-8")
ok(re.search(r"\.st-f textarea \{[^}]*field-sizing: content", css) is not None, "поля текста в конструкторе сайтов растут с текстом")
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
