"""«Рисунки» в студии (31.10, владелец: «закрыл открытку, хотел показать — и не знаю, где она; в „Лира делает сама“ и в
„Задачах“ нет»): раздел «Рисунки» виден, когда установлен «Художник», показывает работы с превью (ядро art_list),
нажатие — работа в браузере. И сам «Художник»: надпись шире плашки — человеку не показываем, сначала поправить."""
import json, os, sys, tempfile, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ["DEWIAR_STATE_DIR"] = str(tmp / "st"); os.environ["DEWIAR_CONFIG_DIR"] = str(tmp / "cfg")
os.environ["DEWIAR_WORKSPACE"] = str(tmp / "ws"); os.environ["DEWIAR_ARTIST_NO_OPEN"] = "1"
sys.path.insert(0, str(ROOT / "core")); sys.path.insert(0, str(ROOT / "data/plugins/artist"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import server as A  # noqa: E402
SVG = ('<svg viewBox="0 0 1000 600"><rect width="1000" height="600" fill="#fee"/><rect x="350" y="400" width="300" height="80" rx="40" fill="#c36"/>'
       '<text x="500" y="452" text-anchor="middle" font-size="44" fill="#fff">Поздравляю тебя, мама!</text><circle r="9"/></svg>')
r = A.draw("Открытка", SVG)
ok(not r["shown"] and "НЕ ПОКАЗАНО" in r["say"] and "шире плашки" in r["say"] and "replace: true" in r["say"], f"надпись шире кнопки — не показано, просят поправить: {r['say'][:120]}")
r2 = A.draw("Открытка", SVG.replace('font-size="44"', 'font-size="22"'), replace=True)
ok(r2["shown"] and "студия → «Рисунки»" in r2["say"], "поправила — открыто, и сказано, где все работы")
src = (ROOT / "core/engine_commands.py").read_text(encoding="utf-8")
ok('if cmd == "art_list":' in src, "ядро: команда art_list")
from playwright.sync_api import sync_playwright  # noqa: E402
items = [{"title": "Открытка", "kind": "picture", "at": "2026-10-31T10:00:00", "page": "Рисунки/Открытка.html",
          "preview": "data:image/svg+xml;base64," + __import__("base64").b64encode(SVG.encode()).decode()},
         {"title": "Снег", "kind": "animation", "at": "2026-10-31T09:00:00", "page": "Рисунки/Снег.html", "preview": ""}]
FAKE = """(() => { window.calls = [];
  const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.call = async (c, a) => { calls.push([c, a]); if (c === "art_list") return { items: ITEMS }; return {}; }; };
  ready(); })();""".replace("ITEMS", json.dumps(items, ensure_ascii=False))
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 1300, "height": 900}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.add_init_script(FAKE); pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(1000)
    pg.evaluate("() => { const w = document.querySelector('#wlc'); if (w) w.remove(); S = S || {}; S.plugins = { on: {} }; artNav(); }")
    ok(pg.evaluate("document.querySelector('nav button[data-p=\"art\"]').hidden"), "без «Художника» — раздела в меню нет")
    pg.evaluate("() => { S.plugins = { on: { artist: {} } }; artNav(); }")
    ok(not pg.evaluate("document.querySelector('nav button[data-p=\"art\"]').hidden"), "«Художник» установлен — «Рисунки» в меню")
    pg.click('nav button[data-p="art"]'); pg.wait_for_timeout(400)
    ok(pg.locator("#art-grid .art-w").count() == 2 and pg.evaluate("document.querySelector('#art-grid img').src.startsWith('data:image/svg')"), "работы с превью")
    pg.click("#art-grid .art-w >> nth=0"); pg.wait_for_timeout(200)
    ok(["ws_open", {"path": "Рисунки/Открытка.html"}] in pg.evaluate("calls"), "нажали — работа открывается в браузере")
    ok(not errs, f"без ошибок JavaScript: {errs[:2]}")
    b.close()
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
