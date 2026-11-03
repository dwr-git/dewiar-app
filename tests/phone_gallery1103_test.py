"""Идея №56 «Готовые персонажи на телефоне» (03.11): на компьютере — Фемида, Доктор, Джарвис, Эва… (core/personas.py
TEMPLATES и GALLERY), на телефоне были только Лира, Патрик и «свой». Теперь personas.js (android/tools/personas_json.py)
несёт window.DEWIAR_GALLERY, а лист «Кто отвечает» — раздел «Готовые персонажи»: «Выбрать» — персонаж в команде и сразу
отвечает (имя вверху, характер и роль — в подсказке модели), «Убрать» — уходит; выбор переживает перезапуск.
Инструментов компьютера (lab_run, search_documents) в подсказке телефона нет; друга ребёнка (Уго) в разделе нет."""
import json, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
import personas as P  # noqa: E402
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


js = subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)], capture_output=True, text=True, check=True).stdout
line = next(l for l in js.splitlines() if l.startswith("window.DEWIAR_GALLERY = "))
gal = json.loads(line[len("window.DEWIAR_GALLERY = "):].rstrip(";"))
ids = [g["id"] for g in gal]
want = [k for k in list(P.TEMPLATES) + list(P.GALLERY) if not (P.TEMPLATES.get(k) or P.GALLERY.get(k)).get("kids")]
ok(ids == want and "femida" in ids and "doctor" in ids and "jarvis" in ids, f"готовые — те же, что на компьютере: {ids}")
ok("ugo" not in ids and not set(ids) & set(P.BUILTIN), "без друга ребёнка и без встроенных (Лира, Патрик)")
ok(all(g["name"] and g["character"] and g["color"] and g["role"] for g in gal), "у каждого — имя, характер, роль, цвет")
ok(not any(re.search(r"lab_run|lab_write|search_documents", g["focus"]) for g in gal), "в подсказке телефона нет инструментов компьютера")
ok(all(g["focus"] for g in gal if g["id"] != "dewiar"), "специализация — словами в подсказке (focus)")
ok(len(js) < 600_000, f"personas.js не разросся: {len(js) // 1024} КБ")

tmp = Path(tempfile.mkdtemp()); www = tmp / "www"
shutil.copytree(ROOT / "android/assets/www", www)
for x in ("entities.js", "rich.js", "skins.js", "skins.css", "privacy.js", "closecrypto.js", "qrcode.js", "call.js", "codes.js"):
    if (ROOT / "ui/assets" / x).exists():
        shutil.copy(ROOT / "ui/assets" / x, www / x)
shutil.copytree(ROOT / "ui/assets/live", www / "live", dirs_exist_ok=True)
shutil.copytree(ROOT / "ui/assets/arcade", www / "arcade", dirs_exist_ok=True)
(www / "personas.js").write_text(js, encoding="utf-8")
errs = []
with sync_playwright() as p:
    b = p.chromium.launch(); ctx = b.new_context(viewport={"width": 390, "height": 844})
    pg = ctx.new_page(); pg.on("pageerror", lambda x: errs.append(str(x)))
    pg.add_init_script("window.toasts = [];")
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(1000)
    before = pg.evaluate("PERSONAS.map(p => p.id)")
    ok("femida" not in before and pg.evaluate("persona().id") == "lira", f"по умолчанию — Лира, готовых в команде нет: {before}")
    pg.click("#who"); pg.wait_for_timeout(400)
    ok(pg.locator("#p-gal").count() == 1 and "Готовые персонажи" in pg.inner_text("#p-gal summary"), "в листе «Кто отвечает» есть раздел «Готовые персонажи»")
    ok(pg.locator("#p-gal .pg").count() == len(gal), f"в разделе все готовые: {pg.locator('#p-gal .pg').count()}")
    pg.click("#p-gal summary"); pg.wait_for_timeout(200)
    card = pg.locator("#p-gal .pg[data-g='femida']")
    ok("Фемида" in card.inner_text() and "Юрист" in card.inner_text(), "карточка: имя и роль")
    card.locator(".pgon").click(); pg.wait_for_timeout(400)
    ok(pg.evaluate("persona().id") == "femida" and pg.inner_text("#who-name") == "Фемида", "«Выбрать» — одной кнопкой Фемида отвечает (имя вверху)")
    ok(not pg.is_visible("#sh-persona.on"), "лист закрылся")
    sp = pg.evaluate("systemPrompt()")
    ok("Тебя зовут Фемида" in sp and "правовые вопросы" in sp, "характер и роль Фемиды — в подсказке модели")
    ok(pg.evaluate("findPersona('фемида') && findPersona('фемида').id") == "femida", "по имени «Фемида» — находится (зовут голосом)")
    ok(pg.evaluate("PERSONAS.findIndex(p => p.id === 'femida') > PERSONAS.findIndex(p => p.id === 'patrik')"), "в команде — после встроенных")
    # переживает перезапуск
    pg.reload(); pg.wait_for_timeout(1000)
    ok(pg.evaluate("persona().id") == "femida" and pg.evaluate("PERSONAS.some(p => p.id === 'femida' && p.gallery)"), "после перезапуска — Фемида на месте")
    pg.click("#who"); pg.wait_for_timeout(400)
    ok(pg.evaluate("document.querySelector('#p-gal').open") and pg.locator("#p-gal .pg[data-g='femida'] .pgnow").count() == 1,
       "раздел открыт, у Фемиды — «Отвечает»")
    ok(pg.locator("#plist .pi[data-id='femida']").count() == 1, "Фемида — и в списке команды наверху")
    # вторая — Доктор; затем убрать Фемиду, когда отвечает Доктор
    pg.locator("#p-gal .pg[data-g='doctor'] .pgon").click(); pg.wait_for_timeout(300)
    ok(pg.evaluate("persona().id") == "doctor", "Доктор — тоже одной кнопкой")
    pg.click("#who"); pg.wait_for_timeout(300)
    pg.locator("#p-gal .pg[data-g='femida'] .pgoff").click(); pg.wait_for_timeout(300)
    ok(not pg.evaluate("PERSONAS.some(p => p.id === 'femida')") and pg.evaluate("persona().id") == "doctor", "«Убрать» — Фемида ушла из команды, Доктор отвечает")
    pg.evaluate("galRemove('doctor')"); pg.wait_for_timeout(100)
    ok(pg.evaluate("persona().id") == "lira", "убрали того, кто отвечал, — снова Лира")
    b.close()
ok(not errs, f"без ошибок страницы: {errs[:2]}")
shutil.rmtree(tmp, ignore_errors=True)
print("ИТОГ:", "OK" if not fails else f"{len(fails)} ошибок")
sys.exit(1 if fails else 0)
