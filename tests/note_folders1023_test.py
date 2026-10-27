"""№195 (22.10, Сергей): «было бы удобно, если бы в заметках был функционал создания папок, особенно в мобильной версии».
Телефон: полоска «Все · Блокнот · Работа…» над заметками, поле «Папка» в заметке (с подсказкой из существующих),
«запиши в папку Работа: …» голосом — без модели, и save_note с folder. Компьютер: заметку перенесли в папку на телефоне —
файл переезжает в эту папку (пустая папка от старых телефонов ничего не двигает)."""
import os, shutil, subprocess, sys, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


# ---------- компьютер: перенос файла ----------
import sync  # noqa: E402
root = Path(tempfile.mkdtemp())
(root / "Идеи").mkdir(); (root / "Идеи/Краска.md").write_text("# Краска\n\nкупить", encoding="utf-8")
(root / "Работа").mkdir(); (root / "Работа/Краска.md").write_text("занято", encoding="utf-8")
sy = sync.Sync.__new__(sync.Sync)
sy.state = {"map": {"n1": "Идеи/Краска.md", "n2": "Корень.md"}}
pads = []; sy._pad_event = lambda rel, deleted: pads.append((rel, deleted))
new = sy._move_to_folder("n1", "Идеи/Краска.md", {"folder": "Работа"}, root)
ok(new == "Работа/Краска (2).md" and (root / new).exists() and not (root / "Идеи/Краска.md").exists() and sy.state["map"]["n1"] == new,
   f"папку сменили на телефоне — файл переехал (имя занято — с номером): {new}")
ok(sy._move_to_folder("n1", new, {"folder": ""}, root) == new and (root / new).exists(), "пустая папка (старый телефон) — файл не трогаем")
ok(sy._move_to_folder("n1", new, {"folder": "Работа"}, root) == new, "та же папка — ничего не делаем")
(root / "Блокнот").mkdir(); (root / "Блокнот/Главное.md").write_text("вкладка", encoding="utf-8")
sy.state["map"]["p1"] = "Блокнот/Главное.md"
sy._move_to_folder("p1", "Блокнот/Главное.md", {"folder": "Архив"}, root)
ok(("Блокнот/Главное.md", True) in pads, "вкладку блокнота унесли в другую папку — блокнот её уберёт")
shutil.rmtree(root, ignore_errors=True)

# ---------- телефон ----------
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
        pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(900)
        pg.evaluate("""() => { saveNotes([{ id: 'a', title: 'Главное', text: 'вкладка', time: 3, folder: 'Блокнот' },
            { id: 'b', title: 'Отчёт', text: 'сдать', time: 2, folder: 'Работа' }, { id: 'c', title: 'Хлеб', text: 'купить', time: 1 }]);
            openSheet('#sh-day'); dayTab = 'notes'; renderDay(); }""")
        pg.wait_for_timeout(200)
        chips = pg.evaluate("() => [...document.querySelectorAll('.ntfolds button')].map(b => b.textContent)")
        ok(chips == ["Все", "Блокнот", "Работа"], f"полоска папок: «Все», «Блокнот» первым: {chips}")
        titles = lambda: pg.evaluate("() => [...document.querySelectorAll('.it.note b')].map(b => b.firstChild.textContent)")
        pg.click(".ntfolds button[data-f='Работа']"); pg.wait_for_timeout(150)
        ok(titles() == ["Отчёт"], f"папка «Работа» — только её заметки: {titles()}")
        pg.click("#nt-new"); pg.wait_for_timeout(400)
        ok(pg.input_value("#nt-folder") == "Работа", "новая заметка из папки — сразу в ней")
        # 27.10: папка — чипами (системный список WebView рисовал серые плашки); новая — «＋ Новая» и имя
        pg.fill("#nt-title", "Звонок"); pg.fill("#nt-text", "клиенту"); pg.click("#nt-newf"); pg.fill("#nt-fname", "работа"); pg.keyboard.press("Enter"); pg.click("#nt-save"); pg.wait_for_timeout(300)
        ok(pg.evaluate("() => notes().find(x => x.title === 'Звонок').folder") == "Работа", "«работа» строчными — в существующую «Работа»")
        pg.evaluate("() => { closeSheets(); }")
        pg.evaluate("() => openNote('c')"); pg.wait_for_timeout(300); pg.click("#nt-edit"); pg.wait_for_timeout(200)
        pg.click("#nt-newf"); pg.fill("#nt-fname", "Покупки"); pg.keyboard.press("Enter"); pg.click("#nt-save"); pg.wait_for_timeout(300)
        ok(pg.evaluate("() => notes().find(x => x.id === 'c').folder") == "Покупки", "заметку перенесли в новую папку «Покупки»")
        r = pg.evaluate("() => noteQuick('Запиши в папку Работа: позвонить поставщику в понедельник', [])")
        n = pg.evaluate("() => notes().find(x => /поставщику/.test(x.text))")
        ok("в папку «Работа»" in r and n and n["folder"] == "Работа", f"голосом «запиши в папку Работа: …» — без модели: {r}")
        r = pg.evaluate("() => noteQuick('Запиши в заметки: купить батарейки', [])")
        ok("в заметки" in r and not pg.evaluate("() => notes().find(x => /батарейки/.test(x.text)).folder"), "обычная запись — без папки, как раньше")
        r = pg.evaluate("() => runTool('save_note', { title: 'Идея', text: 'сайт', folder: 'проекты' })")
        ok("в папку «Проекты»" in r and pg.evaluate("() => notes().find(x => x.title === 'Идея').folder") == "Проекты", f"модель: save_note с папкой: {r}")
        ok(not errs, f"без ошибок: {errs[:2]}")
        b.close()
finally:
    shutil.rmtree(tmp, ignore_errors=True)

if fails:
    raise SystemExit(1)
