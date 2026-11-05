"""№556 (05.11, телефон 0.9.24): «Малое поле в напоминаниях, малое количество символов. Хотелось бы поле как в заметках, где
можно пункты ставить. Красные часы, сверху надпись, как в заголовке, чтобы было больше места при чтении всех напоминаний».
Теперь: «Что напомнить» — растущее поле до 1000 знаков с «• Пункт» (Enter в пункте — следующий, в пустом — снимает); в
списке время — строкой-заголовком над текстом, текст во всю ширину и с переносами строк."""
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
SHOT = os.environ.get("DEWIAR_SHOTS")
with sync_playwright() as p:
    b = p.chromium.launch(); ctx = b.new_context(viewport={"width": 400, "height": 820}, timezone_id="Europe/Minsk")
    pg = ctx.new_page(); pg.on("pageerror", lambda x: errs.append(str(x)))
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(1000)
    rid = pg.evaluate("() => addAlarm('Купить в магазине', new Date(Date.now() + 3 * 3600e3), 'reminder', '').id")
    pg.evaluate("() => addAlarm('Позвонить маме', new Date(Date.now() + 5 * 3600e3), 'reminder', 'daily')")
    pg.evaluate(f"remEdit('{rid}')"); pg.wait_for_timeout(300)
    ok(pg.evaluate("document.querySelector('#rm-text').tagName") == "TEXTAREA" and pg.get_attribute("#rm-text", "maxlength") == "1000",
       "«Что напомнить» — многострочное поле до 1000 знаков (было 200 в одну строку)")
    h0 = pg.evaluate("document.querySelector('#rm-text').offsetHeight")
    pg.click("#rm-text"); pg.keyboard.press("End")
    pg.click(".rmmd button[data-md=li]")                   # текст есть, курсор в конце — новый пункт ниже
    pg.keyboard.type("молоко"); pg.keyboard.press("Enter"); pg.keyboard.type("хлеб"); pg.keyboard.press("Enter")
    pg.keyboard.type("сыр"); pg.keyboard.press("Enter"); pg.keyboard.press("Enter")   # пустой пункт — снимается
    pg.keyboard.type("и не забыть пакет")
    v = pg.input_value("#rm-text")
    ok(v == "Купить в магазине\n• молоко\n• хлеб\n• сыр\nи не забыть пакет", f"пункты: «• Пункт», Enter — следующий, пустой — снимается: {v!r}")
    ok(pg.evaluate("document.querySelector('#rm-text').offsetHeight") > h0, "поле растёт вместе с текстом")
    if SHOT: pg.screenshot(path=str(Path(SHOT) / "phone-remind-edit556.png"))
    pg.click("#rm-save"); pg.wait_for_timeout(400)
    t = pg.evaluate(f"JSON.parse(D.alarms()).find(y => y.id === '{rid}').title")
    ok(t == v, "сохранено целиком, со строками")
    pg.wait_for_selector("#sh-day.on, #sh-day.open, #day-body .it.rem", timeout=3000)
    row = pg.locator(f".it.rem[data-edit='{rid}']")
    ok(row.count() == 1, "в списке — строка напоминания")
    box = pg.evaluate(f"""() => {{ const r = document.querySelector(".it.rem[data-edit='{rid}']"), tm = r.querySelector('.rh .tm'), b = r.querySelector('.bd > b');
      return {{ tmTop: tm.getBoundingClientRect().bottom <= b.getBoundingClientRect().top + 1, bLeft: b.getBoundingClientRect().left - r.getBoundingClientRect().left,
               ws: getComputedStyle(b).whiteSpace, lines: Math.round(b.getBoundingClientRect().height / parseFloat(getComputedStyle(b).lineHeight)) }}; }}""")
    ok(box["tmTop"] and box["bLeft"] < 30, f"время — заголовком над текстом, текст с левого края (не за столбиком часов): {box}")
    ok(box["ws"] == "pre-line" and box["lines"] >= 5, f"пункты — каждый со своей строки: {box}")
    if SHOT: pg.screenshot(path=str(Path(SHOT) / "phone-remind-list556.png"))
    ok(not errs, f"без ошибок на странице: {errs[:2]}")
    b.close()
src = (ROOT / "android/src/pro/dewiar/app/AlarmReceiver.java").read_text(encoding="utf-8")
ok("BigTextStyle" in src, "в уведомлении длинный текст разворачивается целиком (BigTextStyle)")
print("ИТОГ:", "всё прошло" if not fails else f"{len(fails)} ошибок")
sys.exit(1 if fails else 0)
