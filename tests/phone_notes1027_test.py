"""Заметки на телефоне (владелец 27.10: «заметки — одна из важнейших частей… открывается только для правки в сыром
маркдауне, некрасиво; при выборе папки — странные серые блоки; фото на весь экран — назад не вернуться»; №321, №342):
открытая заметка — чтение с оформлением (заголовки, жирный, дела галочкой, нумерация с нужного числа, ссылки), галочка
сохраняется в тексте; «Править» — правка с мини-панелью и папками-чипами (новая папка — там же), «Отмена» и «Назад» —
обратно к чтению; новая заметка — сразу правка; фото — «×» и «Назад» закрывают просмотр; удалили — снова «Мой день»."""
import json, os, shutil, subprocess, sys, tempfile
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
MD = "## План\n\n**Главное** — отчёт.\n\n- [ ] купить хлеб\n- [x] оплатить газ\n\n3. третье\n4. четвёртое\n\n> цитата\n\n[Сайт](https://dewiar.pro)"
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 400, "height": 820})
    pg.on("pageerror", lambda x: errs.append(str(x)))
    pg.add_init_script("window.toasts = [];")
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(1000)
    pg.evaluate("""(md) => { window._opened = []; D.openUrl = (u) => { _opened.push(u); return true; };
      fileSave('natt-a1', 'data:image/svg+xml;utf8,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"/>'));
      saveNotes([{ id: 'n1', title: 'План', text: md, time: Date.now(), folder: 'Работа', att: [{ id: 'a1', name: 'фото', type: 'image', size: 10 }] },
                 { id: 'n2', title: 'Рецепт', text: 'мука', time: Date.now() - 1e6, folder: 'Дом' }]); openNote('n1'); }""", MD)
    pg.wait_for_timeout(500)
    ok(pg.locator("#nt-text").count() == 0 and pg.is_visible("#nt-read"), "открытая заметка — чтение, не поле правки")
    t = pg.inner_text("#nt-read")
    ok("**" not in t and "[ ]" not in t and "Главное" in t and pg.locator("#nt-read b").count() >= 1, f"без сырого Markdown: {t[:80]!r}")
    ok(pg.inner_text("#nt-h") == "План" and "Работа" in pg.inner_text(".ntmeta"), "заголовок — имя заметки, рядом папка и дата")
    ok(pg.get_attribute("#nt-read ol", "start") == "3", "нумерация — с нужного числа (3.), а не «1, 1, 1»")
    pg.click("#nt-read .tk >> nth=0"); pg.wait_for_timeout(200)
    ok("- [x] купить хлеб" in pg.evaluate("notes().find(x => x.id === 'n1').text"), "галочка в чтении — сохранена в тексте")
    pg.click("#nt-read a[data-url]"); ok(pg.evaluate("_opened") == ["https://dewiar.pro"], "ссылка открывается в браузере")
    # фото на весь экран: «Назад» закрывает просмотр, лист остаётся
    pg.click("#note-body .ntimg .ntopen"); pg.wait_for_timeout(150)
    ok(pg.is_visible("#imgview.on") and pg.is_visible("#imgview .ivx"), "фото на весь экран — с «×»")
    ok(pg.evaluate("N.back()") is True and not pg.is_visible("#imgview.on") and pg.is_visible("#sh-note.on"), "«Назад» закрыл фото, заметка на месте")
    pg.click("#note-body .ntimg .ntopen"); pg.click("#imgview .ivx"); pg.wait_for_timeout(100)
    ok(not pg.is_visible("#imgview.on"), "«×» закрывает фото")
    # правка
    pg.click("#nt-edit"); pg.wait_for_timeout(200)
    ok(pg.is_visible("#nt-text") and pg.locator("#nt-folders").count() == 0 and pg.locator("datalist").count() == 0, "«Править» — поле, папки без системного списка")
    chips = pg.evaluate("[...document.querySelectorAll('#nt-folds [data-f]')].map(b => [b.textContent, b.classList.contains('on')])")
    ok(["Работа", True] in chips and ["Без папки", False] in chips and ["Дом", False] in chips, f"папки — чипами, своя выбрана: {chips}")
    pg.click("#nt-newf"); pg.fill("#nt-fname", "Проекты"); pg.keyboard.press("Enter"); pg.wait_for_timeout(100)
    ok(pg.input_value("#nt-folder") == "Проекты", "новая папка — там же")
    pg.fill("#nt-text", "текст"); pg.evaluate("document.querySelector('#nt-text').setSelectionRange(0, 0)"); pg.click(".ntmd [data-md='task']")
    ok(pg.input_value("#nt-text").startswith("- [ ] "), "мини-панель: «Дело» ставит галочку в строку")
    ok(pg.evaluate("N.back()") is True and pg.is_visible("#nt-read"), "«Назад» в правке — обратно к чтению, без сохранения")
    ok("купить хлеб" in pg.inner_text("#nt-read"), "несохранённое не записалось")
    pg.click("#nt-edit"); pg.fill("#nt-title", "План 2"); pg.click("#note-body [data-f='Дом']"); pg.click("#nt-save"); pg.wait_for_timeout(300)
    n1 = pg.evaluate("notes().find(x => x.id === 'n1')")
    ok(n1["title"] == "План 2" and n1["folder"] == "Дом" and pg.is_visible("#nt-read"), "«Сохранить» — записано, снова чтение")
    # новая — сразу правка
    pg.evaluate("closeSheets(); openNote('')"); pg.wait_for_timeout(300)
    ok(pg.is_visible("#nt-text") and pg.inner_text("#nt-h") == "Новая заметка" and pg.locator("#nt-cancel").count() == 0, "новая заметка — сразу правка")
    # удалить → «Мой день»
    pg.evaluate("closeSheets(); window.confirm = () => true; openNote('n2')"); pg.wait_for_timeout(300)
    pg.click("#nt-del"); pg.wait_for_timeout(400)
    ok(pg.is_visible("#sh-day.on") and not pg.evaluate("notes().some(x => x.id === 'n2')"), "удалили — открыт «Мой день», а не главный экран (№342)")
    # «Возможности» (владелец 27.10: «выключил „Рядом“ и „Встречи“ — сердечко осталось, логика запутанная»)
    pg.evaluate("closeSheets(); openSettings('features')"); pg.wait_for_timeout(500)
    ok(pg.locator("#ft-sub #ft-near").count() == 1 and pg.locator("#ft-sub #ft-meet").count() == 1, "«Рядом» и «Встречи» — внутри «Близких», отступом")
    pg.evaluate("document.querySelector('#ft-close').scrollIntoView({block: 'center'})"); pg.click("label:has(#ft-close)"); pg.wait_for_timeout(200)
    ok(not pg.is_visible("#b-close") and pg.evaluate("S.features.close") is False and pg.evaluate("document.querySelector('#ft-sub').classList.contains('off')"),
       "выключили «Близкие» — сердечко пропало, вкладки притушены")
    pg.click("label:has(#ft-close)"); pg.wait_for_timeout(200)
    ok(pg.is_visible("#b-close"), "включили — сердечко вернулось")
    b.close()
ok(not errs, f"без ошибок страницы: {errs[:2]}")
print("ИТОГ:", "OK" if not fails else f"{len(fails)} ошибок")
sys.exit(1 if fails else 0)
