"""«Память» в стиле студии (владелец 30.10: «в центре сделано не в том стиле — можно ли под наш стиль, чтобы красиво?»).
В светлой теме карта была тёмным пятном посреди светлой студии. Теперь в светлых темах — светлое вдавленное поле из того же
материала, узлы глубже по цвету, подписи тёмные с белой обводкой, свечение — мягкая тень; в тёмных — «мозг в ночи», как
было. Тему поменяли — карта перекрашивается на месте."""
import json, os, random, re, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import settings as SET  # noqa: E402

rnd = random.Random(7)
nodes = [{"id": "me", "kind": "me", "label": "Миша", "degree": 20}] + [{"id": f"h-{k}", "kind": "hub", "label": l, "degree": 9} for k, l in
         (("note", "Заметки"), ("diary", "Дневник"), ("skill", "Навыки"))]
for i in range(18):
    nodes.append({"id": f"n{i}", "kind": "note", "label": f"Заметка {i}", "degree": rnd.randint(1, 6)})
for i in range(12):
    nodes.append({"id": f"d{i}", "kind": "diary", "label": f"2026-10-{10 + i}", "degree": rnd.randint(1, 5)})
for i in range(14):
    nodes.append({"id": f"s{i}", "kind": "skill", "label": f"skill-{i}", "degree": 1})
for i in range(6):
    nodes.append({"id": f"e{i}", "kind": "entity", "label": ["Минск", "Аргон", "Лира", "Андрей", "Офис", "Дача"][i], "degree": 3})
edges = [{"from": n["id"], "to": "h-" + n["kind"], "kind": "hub", "w": 0.5} for n in nodes if n["kind"] in ("note", "diary", "skill")]
edges += [{"from": f"n{rnd.randrange(18)}", "to": f"e{rnd.randrange(6)}", "kind": "mention", "w": 0.6} for _ in range(20)]
edges += [{"from": f"d{i}", "to": f"d{i + 1}", "kind": "time", "w": 0.5} for i in range(11)] + [{"from": "me", "to": f"e{i}", "kind": "mention", "w": 0.7} for i in range(6)]
GRAPH = {"nodes": nodes, "edges": edges, "stats": {"facts": 1, "notes": 18, "diary": 12, "docs": 0, "tasks": 0, "entities": 6, "links": len(edges), "week": 9, "days": 26,
                                                   "growth": [{"day": "2026-10-2" + str(i), "n": i + 1} for i in range(6)]}}


def run(skin):
    ST = json.loads(json.dumps(SET.DEFAULTS))
    ST["ui"]["skin"] = skin
    ST["ui"]["memory_motion"] = "off"
    core = """(() => { const ready = () => { if (!window.core) return setTimeout(ready, 5);
      core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
      core.call = async (c, a) => { if (c === "memory_graph") return GRAPH; if (c === "ws_tree") return []; return null; };
      setTimeout(() => core.emit("hello", { settings: ST, personas: [], persona: "lira", presets: {}, piper_voices: [] }), 200); };
      ready(); })();""".replace("GRAPH", json.dumps(GRAPH, ensure_ascii=False)).replace("ST", json.dumps(ST, ensure_ascii=False))
    pg = b.new_page(viewport={"width": 1500, "height": 950}); pg.on("pageerror", lambda e: errs.append(str(e) + " " + (e.stack or "")[:160]))
    pg.route(re.compile(r"^https?://"), lambda r: r.abort())
    pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };"); pg.add_init_script(core)
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(1500)
    pg.evaluate("document.querySelector('#wlc') && document.querySelector('#wlc').remove()")
    pg.evaluate("document.querySelector('nav button[data-p=\"memory\"]').click()"); pg.wait_for_timeout(3500)
    return pg


SHOT = os.environ.get("DEWIAR_SHOTS")
errs = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = run("neusky")
    light = pg.evaluate("document.documentElement.classList.contains('st-light')")
    me = pg.evaluate("mNodes.get('me')")
    n0 = pg.evaluate("mNodes.get('n0')")
    bg = pg.evaluate("getComputedStyle(document.querySelector('#m-graph')).backgroundImage")
    ok(light and "rgba(255, 255, 255, 0.92)" in bg, f"светлая тема — светлое поле карты, не тёмное пятно: {bg[:80]}")
    ok(n0["font"]["color"] == "#2A2F47" and "255,255,255" in n0["font"]["strokeColor"].replace(" ", ""), f"подписи — тёмные с белой обводкой: {n0['font']['color']}")
    ok(me["color"]["background"] == "#5B5FE0", "«Вы» — цветом студии, а не белым на белом")
    if SHOT:
        pg.screenshot(path=str(Path(SHOT) / "memory-light.png"))
    pg.evaluate("studioSkin('brand')"); pg.wait_for_timeout(500)
    ok(pg.evaluate("mNodes.get('n0').font.color") == "#F2F3FA" and pg.evaluate("mNodes.get('me').color.background") == "#FFFFFF",
       "сменили тему на тёмную — карта перекрасилась на месте")
    pg.close()
    pg = run("brand")
    ok(not pg.evaluate("document.documentElement.classList.contains('st-light')") and pg.evaluate("mNodes.get('n0').font.color") == "#F2F3FA",
       "тёмная тема — «мозг в ночи», как было")
    if SHOT:
        pg.screenshot(path=str(Path(SHOT) / "memory-dark.png"))
    b.close()
errs = [x for x in errs if "loadGallery" not in x]
ok(not errs, f"без ошибок на странице: {errs[:3]}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
