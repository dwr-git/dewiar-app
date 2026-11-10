"""№605 (ПК 0.84.2, 06.11): «не хватает ползунка справа у главного меню (в маленьком окне не долистать) и, может, кнопок
масштаба для всего окна». Меню листалось, но полоса прокрутки была скрыта. Теперь — тонкая полоса (ярче под мышью).
Масштаб окна студии уже есть: Ctrl + колесо, Ctrl +/−/0 и «Оформление» → «Размер», и он запоминается (ui.zoom) — проверяем.
На снимке ещё: в «Сообщить о проблеме» «Снять экран» в две строки, «приложить» обрезано — кнопки не переносятся по слову."""
import os, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


errs = []
with sync_playwright() as p:
    b = p.chromium.launch(ignore_default_args=["--hide-scrollbars"])     # как в окне программы: полосы видны
    for skin in ("neusky", "neudusk"):
        pg = b.new_page(viewport={"width": 1100, "height": 560}); pg.on("pageerror", lambda x: errs.append(str(x)))
        pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };")
        pg.goto((ROOT / "ui/settings.html").as_uri() + f"?port=1&skin={skin}"); pg.wait_for_timeout(1000)
        r = pg.evaluate("""() => { const n = document.querySelector('nav'); const cs = getComputedStyle(n);
            return { over: n.scrollHeight > n.clientHeight, bar: n.offsetWidth - n.clientWidth - parseFloat(cs.borderLeftWidth) - parseFloat(cs.borderRightWidth), sw: cs.scrollbarWidth, sc: cs.scrollbarColor }; }""")
        ok(r["over"] and r["bar"] >= 4 and r["sw"] != "none", f"[{skin}] маленькое окно: у меню видна полоса прокрутки: {r}")
        if os.environ.get("DEWIAR_SHOTS"):
            pg.screenshot(path=str(Path(os.environ["DEWIAR_SHOTS"]) / f"studio-nav605-{skin}.png"), clip={"x": 0, "y": 0, "width": 300, "height": 560})
        # масштаб: Ctrl + колесо и Ctrl + — сохраняется в настройки
        pg.evaluate("() => { window._saved = []; window.save = (patch) => { _saved.push(patch); return Promise.resolve(); }; }")
        pg.mouse.move(600, 300); pg.keyboard.down("Control"); pg.mouse.wheel(0, -100); pg.keyboard.up("Control"); pg.wait_for_timeout(600)
        z1 = pg.evaluate("document.documentElement.style.zoom")
        pg.keyboard.press("Control+Minus"); pg.wait_for_timeout(600)
        z2 = pg.evaluate("document.documentElement.style.zoom")
        saved = pg.evaluate("_saved")
        ok(z1 == "1.1" and z2 in ("", "1") and saved and saved[-1].get("ui", {}).get("zoom") == 1, f"[{skin}] Ctrl+колесо и Ctrl− меняют масштаб окна и запоминают его: {z1}, {z2!r}, {saved}")
        # «Сообщить о проблеме»: кнопки снимка — в одну строку каждая
        pg.evaluate("() => { document.querySelectorAll('section.cur').forEach(x => x.classList.remove('cur')); document.querySelector('#bug-shot').closest('section').classList.add('cur'); }")
        pg.wait_for_timeout(200)
        r = pg.evaluate("""() => [...document.querySelectorAll('.bugbar .btn, .bugbar .chk')].map(e => { const lh = parseFloat(getComputedStyle(e).lineHeight) || 18;
            return [e.textContent.trim(), e.scrollWidth <= e.clientWidth + 1, getComputedStyle(e).whiteSpace]; })""")
        ok(all(x[2] == "nowrap" and x[1] for x in r), f"[{skin}] «Снять экран», «Картинка…», «приложить» — не ломаются и не обрезаются: {r}")
        pg.close()
    b.close()
ok(not errs, f"без ошибок на странице: {errs[:3]}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
