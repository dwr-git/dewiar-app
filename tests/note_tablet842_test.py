"""№842 (17.11, планшет HUAWEI лёжа): «При правке заметки, если в ней много текста, не полностью отображается нижняя
часть в горизонтальном положении». Высота поля текста считалась по экрану без клавиатуры: клавиатура открылась
(окно стало ниже) — низ поля с курсором уходил под неё и под полосу «Отмена / Сохранить». Теперь высота — по видимой
части экрана и пересчитывается при её изменении, а поле с курсором прокручивается в виду над полосой кнопок."""
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
shutil.copy(ROOT / "ui/assets/entities.js", www / "entities.js")
shutil.copytree(ROOT / "ui/assets/live", www / "live", dirs_exist_ok=True)
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                capture_output=True, text=True, check=True).stdout, encoding="utf-8")
LONG = "\\n".join(f"{i}. Пункт длинной заметки про CRM — строка номер {i}" for i in range(1, 80))
try:
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1600, "height": 1000}); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(900)
        pg.evaluate("() => { saveNotes([{ id: 'c', title: 'Промт для CRM', text: '" + LONG + "', time: 1 }]); openNote('c'); }")
        pg.wait_for_timeout(300); pg.click("#nt-edit"); pg.wait_for_timeout(500)
        h0 = pg.evaluate("() => $('#nt-text').getBoundingClientRect().height")
        ok(h0 <= 1000 * 0.55 + 1, f"без клавиатуры — поле не выше половины экрана: {h0:.0f}")
        pg.evaluate("() => { const t = $('#nt-text'); t.focus(); t.setSelectionRange(t.value.length, t.value.length); }")
        pg.set_viewport_size({"width": 1600, "height": 520}); pg.wait_for_timeout(700)     # клавиатура открылась (adjustResize)
        r = pg.evaluate("""() => { const t = $('#nt-text').getBoundingClientRect(), bar = $('.ntbar').getBoundingClientRect();
            return { h: t.height, bottom: t.bottom, barTop: bar.top, vh: innerHeight }; }""")
        ok(r["h"] <= 520 - 200 + 1, f"клавиатура открылась — поле стало ниже, по видимой части: {r['h']:.0f} при окне {r['vh']}")
        ok(r["bottom"] <= r["barTop"] + 2, f"низ поля с курсором — над полосой «Отмена / Сохранить»: низ {r['bottom']:.0f}, полоса {r['barTop']:.0f}")
        pg.set_viewport_size({"width": 1600, "height": 1000}); pg.wait_for_timeout(500)
        h2 = pg.evaluate("() => $('#nt-text').getBoundingClientRect().height")
        ok(h2 > r["h"] + 100, f"клавиатура закрылась — поле снова выше: {h2:.0f}")
        ok(not errs, f"без ошибок JavaScript: {errs[:2]}")
        b.close()
finally:
    shutil.rmtree(tmp, ignore_errors=True)
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
