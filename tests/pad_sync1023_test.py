"""№216 (пакет 23.10): «блокнот на десктопе говорит, что синхронизировался с устройствами, на андроиде нигде не найти ни
блокнота, ни его записей; в заметках тоже ничего нет». Компьютер был на своём ключе, телефон — на своём: в синхронизации
компьютер был один, а блокнот всё равно писал «синхронизируется с вашими устройствами». Теперь строка под листом — правда:
других устройств нет — как добавить телефон; телефон есть — где искать («Мой день» → «Заметки», пометка «Блокнот»);
синхронизация выключена — только на этом компьютере. На телефоне у заметки с компьютера — пометка папки."""
import json, os, shutil, subprocess, sys, tempfile, urllib.parse
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


STUB = """st => { window._st = st; core.call = (cmd, a) => {
  if (cmd === 'sync_status') return Promise.resolve(window._st);
  if (cmd === 'pad_tabs') return Promise.resolve({ tabs: [{ name: 'Главное' }], active: 'Главное' });
  if (cmd === 'pad_read') return Promise.resolve({ name: 'Главное', text: 'Купить хлеб', mtime: 1 });
  if (cmd === 'pad_write') return Promise.resolve({ mtime: 2 });
  return Promise.resolve(null); }; P.loaded = false; syncAt = 0; refresh(); }"""
cases = (({"available": True, "on": True, "devices": []}, "других устройств пока нет", "«Устройства»"),
         ({"available": True, "on": True, "devices": [{"name": "Pixel 8", "pc": False}]}, "на телефоне", "«Блокнот»"),
         ({"available": True, "on": True, "devices": [{"name": "Ноутбук", "pc": True}]}, "синхронизируется с вашими устройствами", ""),
         ({"available": True, "on": False, "devices": []}, "только на этом компьютере", "выключена"))
with sync_playwright() as p:
    b = p.chromium.launch()
    for st, want, also in cases:
        pg = b.new_page(); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto((ROOT / "ui/pad.html").as_uri() + "?skin=neusky&cfg=" + urllib.parse.quote(json.dumps({"side": "left", "gap": 14, "clips": []})))
        pg.wait_for_timeout(500)
        pg.evaluate(STUB, st); pg.wait_for_timeout(500)
        t = pg.inner_text("#st")
        ok(want in t and also in t and not errs, f"{json.dumps(st, ensure_ascii=False)[:70]} → «{t}»")
        pg.close()

    # телефон: заметка из папки компьютера — с пометкой
    tmp = Path(tempfile.mkdtemp()); www = tmp / "www"
    shutil.copytree(ROOT / "android/assets/www", www)
    shutil.copy(ROOT / "ui/assets/entities.js", www / "entities.js")
    shutil.copytree(ROOT / "ui/assets/live", www / "live", dirs_exist_ok=True)
    (www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                    capture_output=True, text=True, check=True).stdout, encoding="utf-8")
    pg = b.new_page(viewport={"width": 390, "height": 844}); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(800)
    pg.evaluate("""() => { saveNotes([{ id: 'n1', title: 'Главное', text: 'Купить хлеб', time: Date.now(), folder: 'Блокнот' },
        { id: 'n2', title: 'Список', text: 'молоко', time: Date.now() - 1000, folder: '' }]);
        openSheet('#sh-day'); dayTab = 'notes'; renderDay(); }""")
    pg.wait_for_timeout(300)
    tags = pg.evaluate("() => [...document.querySelectorAll('.it.note')].map(e => [e.querySelector('b').firstChild.textContent, (e.querySelector('.ntf') || {}).textContent || ''])")
    ok(["Главное", "Блокнот"] in tags and ["Список", ""] in tags, f"телефон: вкладка блокнота подписана «Блокнот», обычная заметка — без пометки: {tags}")
    ok(not errs, f"телефон без ошибок: {errs[:2]}")
    b.close()
    shutil.rmtree(tmp, ignore_errors=True)

if fails:
    raise SystemExit(1)
