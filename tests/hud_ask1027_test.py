"""№313 (пакет 27.10): «при длинном сообщении кнопка „Отправить“ проваливается за нижнюю панель» — в низком виджете поле
ввода росло до 210 px. Теперь поле не выше свободного места: «Отправить» всегда над панелью; в высоком — как раньше."""
import os, re, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


CORE = r"""(() => { const ready = () => { if (!window.core) return setTimeout(ready, 5);
  core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; try { core.ws.close(); } catch (e) {} } core.connected = true;
  core.call = async () => ({}); setTimeout(() => { core.emit("hello", { settings: { ui: { skin: "neon" }, llm: { active: "m" }, features: {} }, status: {}, persona: "lira", personas: [{ id: "lira", name: "Лира" }], reminders: [], state: "idle" }); }, 150); }; ready(); })();"""
LONG = "В Настройки → Напоминания после срабатывания появится кнопка «Отложить на 10 минут». " * 8
errs = []
with sync_playwright() as p:
    b = p.chromium.launch()
    for w, h in ((290, 370), (300, 620)):
        pg = b.new_page(viewport={"width": w, "height": h}); pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.route(re.compile(r"^https?://"), lambda r: r.abort()); pg.add_init_script(CORE)
        pg.goto((ROOT / "ui/hud.html").as_uri() + "?mode=card"); pg.wait_for_timeout(1200)
        pg.evaluate("() => { const b = document.querySelector('#b-kbd') || document.querySelector('[data-a=\"kbd\"]'); if (b) b.click(); else if (window.openAsk) openAsk(); }")
        pg.wait_for_timeout(300)
        pg.evaluate("(t) => { const a = document.querySelector('#askin'); a.value = t; a.dispatchEvent(new Event('input')); fitAsk(); }", LONG)
        pg.wait_for_timeout(200)
        r = pg.evaluate("() => { const s = document.querySelector('#a-send').getBoundingClientRect(), bar = document.querySelector('#bar').getBoundingClientRect(), t = document.querySelector('#askin');"
                        " return { send: s.bottom, bar: bar.top, vis: getComputedStyle(document.querySelector('#ask')).display, th: t.getBoundingClientRect().height }; }")
        ok(r["vis"] != "none" and r["send"] <= r["bar"] + 1, f"виджет {w}×{h}: «Отправить» над панелью ({r})")
        if h > 600:
            ok(r["th"] > 120, f"в высоком виджете поле по-прежнему растёт: {r['th']:.0f} px")
        pg.close()
    b.close()
ok(not errs, f"без ошибок страницы: {errs[:2]}")
print("ИТОГ:", "OK" if not fails else f"{len(fails)} ошибок")
sys.exit(1 if fails else 0)
