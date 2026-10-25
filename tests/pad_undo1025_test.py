"""Блокнот: шаг назад и шаг вперёд (25.10, владелец: «удалил часть текста, захватил лишнее, жал Ctrl+Z — не
возвращается… фактически потерял важную информацию — нужно шаг вперёд и шаг назад»). Своя история листа:
удаление выделенного — Ctrl+Z возвращает, Ctrl+Y / Ctrl+Shift+Z — снова; набор подряд — один шаг; «- » (список на
лету) — свой шаг; кнопки ↶ ↷ гаснут, когда некуда; восстановленное сохраняется; у вкладок — своя история; меню
«Правка → Отменить» (historyUndo) — тоже наша история."""
import json, os, re, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


TEXT = "Важная строка: договор №17 до пятницы\n\nВторая строка остаётся"
FAKE = "window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };"
CORE = r"""(() => { window.calls = []; const T = { "Главное": TEXT, "Вторая": "Другая вкладка" };
  const ready = () => { if (!window.core) return setTimeout(ready, 5);
  core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; try { core.ws.close(); } catch (e) {} } core.connected = true;
  core.call = async (c, a) => { calls.push([c, a]); if (c === "pad_tabs") return { tabs: [{ name: "Главное", mtime: 1 }, { name: "Вторая", mtime: 1 }], active: "Главное" };
    if (c === "pad_read") return { name: a.name, text: T[a.name], mtime: 1 }; if (c === "pad_write") return { mtime: 2 }; return {}; };
  setTimeout(() => core.emit("hello", { settings: { ui: { skin: "neusky" } }, status: { state: "idle" } }), 150); }; ready(); })();""".replace("TEXT", json.dumps(TEXT))
txt = lambda pg: pg.evaluate("document.querySelector('#ed').innerText.replace(/\\n+/g, ' | ').trim()")
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 620, "height": 800}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route(re.compile(r"^https?://"), lambda r: r.abort())
    pg.add_init_script(FAKE); pg.add_init_script(CORE)
    pg.goto((ROOT / "ui/pad.html").as_uri() + "?skin=neusky"); pg.wait_for_timeout(1500)
    t0 = txt(pg)
    ok("договор №17" in t0 and pg.is_disabled("#b-undo") and pg.is_disabled("#b-redo"), f"открыли лист — назад и вперёд некуда, кнопки погашены: {t0}")
    # выделить «: договор №17 до пятницы» и удалить
    pg.evaluate("""() => { const p = document.querySelector('#ed p'), n = p.firstChild, r = document.createRange();
      r.setStart(n, n.nodeValue.indexOf(':')); r.setEnd(n, n.nodeValue.length); const s = getSelection(); s.removeAllRanges(); s.addRange(r); document.querySelector('#ed').focus(); }""")
    pg.keyboard.press("Backspace"); pg.wait_for_timeout(150)
    ok("договор" not in txt(pg) and not pg.is_disabled("#b-undo"), f"удалили выделенное: {txt(pg)}")
    pg.keyboard.press("Control+z"); pg.wait_for_timeout(150)
    ok(txt(pg) == t0, f"Ctrl+Z — удалённое вернулось целиком: {txt(pg)}")
    ok(not pg.is_disabled("#b-redo"), "можно шаг вперёд")
    pg.keyboard.press("Control+y"); pg.wait_for_timeout(150)
    ok("договор" not in txt(pg), "Ctrl+Y — снова удалено")
    pg.keyboard.press("Control+Shift+z"); pg.wait_for_timeout(100)
    ok("Вперёд больше некуда" in pg.text_content("#status") if pg.locator("#status").count() else True, "дальше вперёд — некуда, так и сказано")
    pg.click("#b-undo"); pg.wait_for_timeout(150)
    ok(txt(pg) == t0, "кнопка ↶ — тоже шаг назад")
    pg.wait_for_timeout(900)
    w = [c[1] for c in pg.evaluate("calls") if c[0] == "pad_write"]
    ok(w and "договор №17" in w[-1]["text"], "восстановленное сохранилось в файл")
    # набор подряд — один шаг
    pg.evaluate("() => { const ps = document.querySelectorAll('#ed p'), p = ps[ps.length - 1], r = document.createRange(); r.selectNodeContents(p); r.collapse(false); const s = getSelection(); s.removeAllRanges(); s.addRange(r); }")
    pg.keyboard.type("абвгд", delay=30); pg.wait_for_timeout(100)
    pg.keyboard.press("Control+z"); pg.wait_for_timeout(100)
    ok(txt(pg) == t0, f"набранное слово — один шаг назад: {txt(pg)}")
    # список на лету — свой шаг
    pg.keyboard.press("End"); pg.keyboard.press("Enter"); pg.keyboard.type("- пункт", delay=20); pg.wait_for_timeout(150)
    ok(pg.locator("#ed ul li").count() == 1, "«- » — список на лету")
    for _ in range(6):
        pg.keyboard.press("Control+z"); pg.wait_for_timeout(60)
    ok(pg.locator("#ed ul").count() == 0 and "договор №17" in txt(pg), f"назад через список — без ошибок, к началу: {txt(pg)}")
    # меню «Правка → Отменить» (beforeinput historyUndo)
    pg.evaluate("() => { const p = document.querySelector('#ed p'); p.firstChild.nodeValue = 'X'; document.querySelector('#ed').dispatchEvent(new InputEvent('input', { bubbles: true })); }")
    pg.wait_for_timeout(50)
    pg.evaluate("() => document.querySelector('#ed').dispatchEvent(new InputEvent('beforeinput', { inputType: 'historyUndo', bubbles: true, cancelable: true }))")
    pg.wait_for_timeout(100)
    ok("договор №17" in txt(pg), "«Отменить» из меню — тоже наша история")
    # своя история у вкладки
    pg.evaluate("() => { const ps = document.querySelectorAll('#ed p'), p = ps[ps.length - 1], r = document.createRange(); r.selectNodeContents(p); r.collapse(false); const s = getSelection(); s.removeAllRanges(); s.addRange(r); }")
    pg.keyboard.type(" ещё", delay=20); pg.wait_for_timeout(900)
    pg.evaluate("openTab('Вторая')"); pg.wait_for_timeout(500)
    ok(txt(pg) == "Другая вкладка" and pg.is_disabled("#b-undo"), "другая вкладка — своя история (назад некуда)")
    pg.evaluate("openTab('Главное')"); pg.wait_for_timeout(500)
    ok(not pg.is_disabled("#b-undo"), "вернулись — история первой вкладки на месте")
    ok(not errs, "без ошибок на странице" + (f": {errs}" if errs else ""))
    b.close()
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
