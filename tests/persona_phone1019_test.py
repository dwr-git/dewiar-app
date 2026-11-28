"""Свой персонаж на телефоне (19.10: «на телефоне и планшете нет функции создать персонажа», «хочу этот аватар»).
Лист «Кто отвечает» → «+ Свой персонаж»: облик из галереи (квадрат по центру), имя, она/он, роль, характер, цвет.
Сохранили — персонаж выбран, откликается на имя (findPersona), характер — в подсказке модели, облик — портретом;
после перезапуска на месте; карандаш — правка; занятое имя — нельзя; «Удалить» — обратно к встроенной."""
import io, os, shutil, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


from PIL import Image, ImageDraw  # noqa: E402
tmp = Path(tempfile.mkdtemp()); www = tmp / "www"
shutil.copytree(ROOT / "android/assets/www", www)
for x in ("entities.js", "speechnorm.js", "skins.css", "skins.js"):
    shutil.copy(ROOT / "ui/assets" / x, www / x)
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                capture_output=True, text=True, check=True).stdout, encoding="utf-8")
im = Image.new("RGB", (600, 900), (40, 30, 30)); d = ImageDraw.Draw(im); d.ellipse((200, 150, 400, 380), fill=(230, 190, 170))
photo = tmp / "photo.jpg"; im.save(photo, quality=90)
SHOT = os.environ.get("DEWIAR_SHOTS")

from playwright.sync_api import sync_playwright  # noqa: E402
with sync_playwright() as p:
    b = p.chromium.launch(); ctx = b.new_context(viewport={"width": 393, "height": 852}, device_scale_factor=2)
    pg = ctx.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("dialog", lambda dl: dl.accept())
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(1200)
    pg.evaluate("() => { document.querySelectorAll('.sheet.on').forEach(s => s.classList.remove('on')); }")
    pg.click("#who"); pg.wait_for_timeout(400)
    ok(pg.is_visible("#p-new"), "в «Кто отвечает» есть «+ Свой персонаж»")
    pg.click("#p-new"); pg.wait_for_timeout(300)
    pg.set_input_files("#pe-file", str(photo)); pg.wait_for_timeout(600)
    ok("data:image/jpeg" in (pg.get_attribute("#pe-img img", "src") or ""), "облик из галереи — квадрат JPEG в редакторе")
    pg.fill("#pe-name", "Лира"); pg.click("#pe-save"); pg.wait_for_timeout(200)
    ok("занято" in pg.inner_text("#pe-res"), f"имя встроенного персонажа занять нельзя: {pg.inner_text('#pe-res')}")
    pg.fill("#pe-name", "Меган"); pg.fill("#pe-role", "подруга"); pg.fill("#pe-about", "Весёлая, отвечает коротко, любит шутить.")
    pg.click("#pe-g button[data-g='female']")
    if SHOT:
        pg.screenshot(path=str(Path(SHOT) / "pe-editor.png"))
    pg.click("#pe-save"); pg.wait_for_timeout(600)
    r = pg.evaluate("""() => ({ id: S.persona, name: persona().name, ava: (persona().avatar || "").slice(0, 22), who: document.querySelector('#who-name').textContent,
      sys: systemPrompt(), find: (findPersona("меган") || {}).id, gender: persona().gender, len: (persona().avatar || "").length })""")
    ok(r["id"].startswith("u") and r["name"] == "Меган" and r["who"] == "Меган" and r["ava"].startswith("data:image/jpeg"),
       f"сохранили — Меган выбрана, облик — её фото: {r['id']} {r['who']} {r['ava']}")
    ok("Ты — Меган, подруга. Весёлая, отвечает коротко" in r["sys"] and r["find"] == r["id"] and r["gender"] == "female",
       "характер — в подсказке модели, имя зовёт её, она — женский род")
    ok(r["len"] < 120000, f"облик лёгкий (хранится на телефоне): {r['len'] // 1024} КБ")
    if SHOT:
        pg.screenshot(path=str(Path(SHOT) / "pe-main.png"))
    pg.reload(); pg.wait_for_timeout(1200)
    r2 = pg.evaluate("() => ({ name: persona().name, n: PERSONAS.filter(p => p.custom).length })")
    ok(r2 == {"name": "Меган", "n": 1}, f"после перезапуска — на месте: {r2}")
    pg.evaluate("() => { document.querySelectorAll('.sheet.on').forEach(s => s.classList.remove('on')); }")
    pg.click("#who"); pg.wait_for_timeout(400)
    if SHOT:
        pg.screenshot(path=str(Path(SHOT) / "pe-list.png"))
    pg.click(".pedit"); pg.wait_for_timeout(300)
    ok(pg.input_value("#pe-name") == "Меган" and pg.is_visible("#pe-del"), "карандаш — правка того же персонажа")
    pg.fill("#pe-name", "Мэг"); pg.click("#pe-save"); pg.wait_for_timeout(400)
    ok(pg.evaluate("() => persona().name") == "Мэг" and pg.evaluate("() => PERSONAS.filter(p => p.custom).length") == 1, "правка — тот же персонаж с новым именем")
    # 28.11 (скриншот человека: «добавить базу данных» в «Своём персонаже»): «Знания» — кнопкой прямо в редакторе:
    # сохранить и открыть «Кто отвечает» на знаниях этого персонажа
    pg.evaluate("() => { document.querySelectorAll('.sheet.on').forEach(s => s.classList.remove('on')); }")
    pg.click("#who"); pg.wait_for_timeout(300); pg.click(".pedit"); pg.wait_for_timeout(300)
    pg.fill("#pe-name", "Мегги"); pg.click("#pe-kb"); pg.wait_for_timeout(700)
    kb = pg.evaluate("() => ({ name: persona().name, open: document.querySelector('#sh-persona').classList.contains('on'), kb: (document.querySelector('#pkb') || {}).innerText || '' })")
    ok(kb["name"] == "Мегги" and kb["open"] and "Знания" in kb["kb"], f"«Знания» в редакторе — сохранено и открыты знания персонажа: {kb}")
    pg.evaluate("() => closeSheets()"); pg.wait_for_timeout(300)
    pg.evaluate("() => { document.querySelectorAll('.sheet.on').forEach(s => s.classList.remove('on')); }")
    pg.click("#who"); pg.wait_for_timeout(300); pg.click(".pedit"); pg.wait_for_timeout(300); pg.click("#pe-del"); pg.wait_for_timeout(400)
    r3 = pg.evaluate("() => ({ id: S.persona, n: PERSONAS.filter(p => p.custom).length })")
    ok(r3["n"] == 0 and r3["id"] == "lira", f"«Удалить» — персонажа нет, отвечает Лира: {r3}")
    ok(not errs, f"без ошибок: {errs[:2]}")
    b.close()
shutil.rmtree(tmp, ignore_errors=True)
print("\nИТОГ:", "всё прошло" if not fails else f"не прошло {len(fails)}")
sys.exit(1 if fails else 0)
