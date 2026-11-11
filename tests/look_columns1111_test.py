"""Владелец 11.11 (Ubuntu, «Оформление» → «Что показывать»): «небольшой баг со светлой тенью в центре блоков».
Панели групп стоят колонками (columns); WebKitGTK не понимает break-inside и рвал панель между колонками — её кусок со
светлой тенью начинался посреди соседней колонки. Теперь панель — строчный блок (inline-block): колонками не рвётся."""
import os, re, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


css = (ROOT / "ui/studio/studio.css").read_text(encoding="utf-8")
rule = re.search(r"\.sh-g \{[^}]*\}", css).group(0)
ok("display: inline-block" in rule and "width: 100%" in rule and "-webkit-column-break-inside: avoid" in rule, "панель — строчный блок во всю колонку (не рвётся и в WebKitGTK)")
ok(".sh-g[hidden] { display: none; }" in css, "скрытая панель так и скрыта")
FAKE = """(() => { const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.call = async (c, a) => { if (c === "month_get") throw new Error("нет"); return {}; };
    setTimeout(() => core.emit("hello", {}), 200); }; ready(); })();"""
with sync_playwright() as p:
    b = p.chromium.launch()
    for w in (1420, 1100, 900):
        pg = b.new_page(viewport={"width": w, "height": 1100})
        pg.route(re.compile(r"^https?://"), lambda r: r.abort()); pg.add_init_script(FAKE)
        pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(1200)
        pg.evaluate("() => { S = { ui: {} }; personas = []; const x = document.querySelector('#wlc'); if (x) x.remove(); document.querySelector('nav button[data-p=\"look\"]').click(); }")
        pg.wait_for_timeout(600)
        n = pg.evaluate("[...document.querySelectorAll('#sh-groups .sh-g')].filter(g => !g.hidden).length")
        split = pg.evaluate("[...document.querySelectorAll('#sh-groups .sh-g')].filter(g => !g.hidden && g.getClientRects().length > 1).length")
        ok(n >= 8 and split == 0, f"ширина {w}: панелей {n}, разорванных между колонками — {split}")
        pg.close()
    b.close()
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
