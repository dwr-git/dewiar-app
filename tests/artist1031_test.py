"""Плагин «Художник» (владелец 30.10: «генеративной модели нет, а было бы интересно, если бы Лира умела красиво рисовать…
вот бы Лиру такому научить»; 30.10 23:41: «Художник — невероятно важен»). Лира рисует кодом, как Claude:
— SVG чистится: без скриптов, on…, внешних ссылок и <foreignObject>; «&» и &nbsp; не ломают разбор; viewBox и размер — сами;
— надпись у края или за краем — замечание модели (картинку она не видит), «replace» — поправка той же работы;
— анимация: function draw(ctx, t, w, h); сеть, хранилища и eval — отказ; своя «const ctx» не ломает страницу;
— страница просмотра в браузере: «Сохранить PNG» (размер как у рисунка), у анимации — «Записать видео» (WebM не пустой);
— «Галерея» со всеми работами; страницы — с запретом сети (CSP); плагин встроенный, MCP отвечает."""
import json, os, re, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ["DEWIAR_STATE_DIR"] = str(tmp / "st"); os.environ["DEWIAR_CONFIG_DIR"] = str(tmp / "cfg")
os.environ["DEWIAR_WORKSPACE"] = str(tmp / "ws"); os.environ["DEWIAR_ARTIST_NO_OPEN"] = "1"
os.environ["DEWIAR_PLUGIN_SETTINGS"] = json.dumps({"size": "Открытка 1500×1050"})
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


sys.path.insert(0, str(ROOT / "data/plugins/artist"))
import server as A  # noqa: E402

EVIL = """```svg
<svg viewBox="0 0 1500 1050" onload="alert(1)"><script>alert(2)</script>
<defs><linearGradient id="g"><stop offset="0" stop-color="#fc9"/><stop offset="1" stop-color="#f69"/></linearGradient></defs>
<rect width="1500" height="1050" fill="url(#g)"/><image href="https://evil.test/x.png" width="10" height="10"/>
<foreignObject width="100" height="100"><div>x</div></foreignObject>
<a href="javascript:alert(3)"><circle cx="300" cy="300" r="120" fill="#fff" style="fill:url(https://evil.test/y)"/></a>
<style>@import url(https://evil.test/z.css); .t{fill:#333}</style>
<text x="750" y="900" text-anchor="middle" font-size="80" class="t">Том &amp; Джерри & друзья&nbsp;!</text>
</svg>
```"""
svg, notes, (w, h), n = A.clean_svg(EVIL, 1500, 1050)
ok("<script" not in svg and "onload" not in svg and "evil.test" not in svg and "foreignObject" not in svg and "javascript:" not in svg
   and "@import" not in svg, f"скрипты, on…, внешние ссылки, foreignObject, @import — убраны: {notes}")
ok("Джерри &amp; друзья" in svg and " " in svg and 'xmlns="http://www.w3.org/2000/svg"' in svg and (w, h) == (1500, 1050),
   "«&» и &nbsp; не ломают разбор; xmlns и размер на месте; обёртка ```svg снята")
_, n2, (w2, h2), _ = A.clean_svg('<svg width="400" height="200"><rect width="400" height="200"/><circle r="5"/><circle r="6"/></svg>', 1080, 1080)
ok((w2, h2) == (1080, 540) and "добавлен viewBox" in n2, f"нет viewBox — добавлен, размер по пропорции рисунка: {(w2, h2)}")
try:
    A.clean_svg("нарисуй кота", 100, 100); bad = False
except ValueError as e:
    bad = "SVG" in str(e)
ok(bad, "не SVG — понятная ошибка для модели")
over = A.clean_svg('<svg viewBox="0 0 1000 600"><rect width="1000" height="600"/><text x="700" y="300" font-size="90">Поздравляю!</text>'
                   '<g transform="translate(480 0)"><text x="20" y="500" font-size="60" text-anchor="middle">ок</text></g></svg>', 1000, 600)[1]
ok(any("Поздравляю" in x and "правый" in x for x in over) and not any("«ок»" in x for x in over), f"надпись за краем — замечание: {over}")

pv, pn, _, _ = A.clean_svg('<svg viewBox="0 0 400 300"><rect width="400" height="300" fill="#fee"/><use href="#dw-balloon" x="20" y="20" width="80" height="140" color="#7C6CF2"/>'
                           "<use xlink:href='#dw-star' x='200' y='40' width='60' height='60' color='gold'/><use href=\"#dw-nope\"/></svg>", 400, 300)
ok('id="dw-balloon"' in pv and 'id="dw-star"' in pv and "dw-nope\"" not in pv.split("<defs>")[1].split("</defs>")[0] and any("balloon" in x for x in pn),
   f"готовые детали: <use href=\"#dw-…\"> — symbol вставлен сам, неизвестная — нет: {pn}")
r = A.draw("Открытка маме", (ROOT / "tests/fixtures/artist/card.svg").read_text(encoding="utf-8"))
d = Path(os.environ["DEWIAR_WORKSPACE"]) / "Рисунки"
ok(Path(r["saved"]).is_file() and Path(r["page"]).is_file() and r["size"] == "1500×1050" and Path(r["saved"]).parent == d,
   f"сохранено в «Рисунки» папки Dewiar, размер — из настроек плагина: {r['size']}")
ok(any("рождения" in x for x in r["notes"]) and "replace: true" in r["say"], f"надпись у края — модель просят поправить: {r['notes']}")
r2 = A.draw("Открытка маме", (ROOT / "tests/fixtures/artist/card.svg").read_text(encoding="utf-8"))
r3 = A.draw("Открытка маме", (ROOT / "tests/fixtures/artist/card.svg").read_text(encoding="utf-8"), replace=True)
ok(r2["saved"].endswith("Открытка маме (2).svg") and r3["saved"].endswith("Открытка маме.svg"), "новая — рядом с номером, «поправь» — заменяет")
SNOW = (ROOT / "tests/fixtures/artist/snow.js").read_text(encoding="utf-8")
ra = A.animate("Снег над городом", "const ctx = 1, W = 2;\n" + SNOW, 2, "640x360")
ok(Path(ra["page"]).is_file() and ra["size"] == "640×360" and ra["seconds"] == 2, "анимация сохранена страницей")
for evil in ("fetch('https://x')", "localStorage.x = 1", "eval('1')", "new Function('x')"):
    try:
        A.animate("x", "function draw(ctx){ " + evil + " }"); bad = False
    except ValueError:
        bad = True
    ok(bad, f"в анимации нельзя: {evil}")
g = A.gallery(False)
ok(g["count"] == 3 and (d / "Галерея.html").is_file() and "Снег над городом" in (d / "Галерея.html").read_text(encoding="utf-8"), f"галерея: {g['count']}")
ok(all("connect-src 'none'" in (d / f).read_text(encoding="utf-8") for f in ("Открытка маме.html", "Снег над городом.html", "Галерея.html")),
   "страницы — с запретом сети")

from playwright.sync_api import sync_playwright  # noqa: E402
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 1280, "height": 900}, accept_downloads=True)
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto((d / "Открытка маме.html").as_uri()); pg.wait_for_timeout(700)
    ok(pg.evaluate("document.getElementById('art').naturalWidth") == 1500, "рисунок показан")
    with pg.expect_download() as dl:
        pg.click("#png1")
    f = tmp / "a.png"; dl.value.save_as(f)
    import struct  # noqa: E402
    head = f.read_bytes()[:24]
    ok(head[:8] == b"\x89PNG\r\n\x1a\n" and struct.unpack(">II", head[16:24]) == (1500, 1050) and dl.value.suggested_filename == "Открытка маме.png",
       f"«Сохранить PNG» — 1500×1050: {dl.value.suggested_filename}")
    with pg.expect_download() as dl:
        pg.click("#png2")
    dl.value.save_as(tmp / "b.png")
    ok(struct.unpack(">II", (tmp / "b.png").read_bytes()[16:24]) == (3000, 2100), "«PNG ×2» — вдвое больше")
    pg.goto((d / "Снег над городом.html").as_uri()); pg.wait_for_timeout(900)
    ok(pg.evaluate("document.getElementById('cv').getContext('2d').getImageData(320, 100, 1, 1).data[3]") == 255 and "Ошибка" not in pg.inner_text("body"),
       "анимация рисуется (своя const ctx в коде её не ломает)")
    with pg.expect_download(timeout=20000) as dl:
        pg.click("#rec")
    dl.value.save_as(tmp / "v.webm")
    ok((tmp / "v.webm").stat().st_size > 5000 and dl.value.suggested_filename.endswith((".webm", ".mp4")), f"«Записать видео» — не пустое: {(tmp / 'v.webm').stat().st_size}")
    bad = A.animate("Сломанная", "function draw(ctx, t) { ctx.nope(); }", 2, "320x200")
    pg.goto(Path(bad["page"]).as_uri()); pg.wait_for_timeout(500)
    ok(pg.evaluate("(() => { const d = document.getElementById('cv').getContext('2d').getImageData(0, 0, 320, 200).data; for (let i = 0; i < d.length; i += 4) if (d[i] > 150 && d[i + 1] < 90) return true; return false; })()"),
       "ошибка в анимации — видна на холсте, а не пустота")
    pg.goto((d / "Галерея.html").as_uri()); pg.wait_for_timeout(500)
    ok(pg.locator(".w").count() == 4 and pg.evaluate("[...document.images].every(i => i.naturalWidth > 0)"), "галерея: карточки и превью картинок")
    ok(not errs, f"без ошибок JavaScript: {errs[:2]}")
    b.close()

env = dict(os.environ, DEWIAR_WORKSPACE=str(tmp / "ws2"))
msgs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "art_draw", "arguments": {"title": "Кот", "svg": "<svg viewBox='0 0 10 10'><circle r='3' cx='5' cy='5'/></svg>"}}},
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "art_draw", "arguments": {"title": "Кот", "svg": "кот"}}}]
pr = subprocess.run([sys.executable, str(ROOT / "data/plugins/artist/server.py")], input="\n".join(json.dumps(x) for x in msgs) + "\n",
                    capture_output=True, text=True, env=env, timeout=60)
out = [json.loads(x) for x in pr.stdout.splitlines() if x.strip()]
ok(len(out) == 4 and {t["name"] for t in out[1]["result"]["tools"]} == {"art_draw", "art_animate", "art_gallery"}
   and all(t["annotations"]["readOnlyHint"] for t in out[1]["result"]["tools"]), f"MCP: три действия без «Выполнить?»: {pr.stderr[-200:]}")
ok(json.loads(out[2]["result"]["content"][0]["text"])["saved"].endswith("Кот.svg") and out[3]["result"].get("isError")
   and "Исправь" in out[3]["result"]["content"][0]["text"], "через MCP рисует; ошибка — с просьбой исправить")

sys.path.insert(0, str(ROOT / "core"))
import settings as ST  # noqa: E402
import plugins as PL  # noqa: E402
import mcp as M  # noqa: E402
s = ST.Settings(tmp / "s.json")
P = PL.Plugins(s)
pa = P.items.get("artist")
ok(pa and pa["builtin"] and pa["try"].startswith("Нарисуй") and pa["skill_dirs"], "встроенный плагин «Художник»")
ok(pa["links"] == [{"label": "Открыть галерею", "path": "Рисунки/Галерея.html"}] and pa["video"] == "20-artist", "в панели — «Открыть галерею», ролик — урок 20")
bad = PL.parse_plugin(ROOT / "data/plugins/artist", True)
import shutil  # noqa: E402
ev = tmp / "evil"; shutil.copytree(ROOT / "data/plugins/artist", ev)
mm = json.loads((ev / "plugin.json").read_text(encoding="utf-8")); mm["links"] = [{"label": "x", "path": "../../etc/passwd"}, {"label": "y", "path": "C:/Windows"}, {"label": "z", "path": "/etc"}]
(ev / "plugin.json").write_text(json.dumps(mm, ensure_ascii=False), encoding="utf-8")
ok(PL.parse_plugin(ev, False)["links"] == [], "ссылки плагина — только внутрь папки Dewiar")
P.install("artist")
mgr = M.MCPManager(s)
seen = {}
mgr.servers = {}
orig = M.Server


class Fake:
    def __init__(self, n, cfg):
        seen[n] = cfg; self.cfg, self.name, self.status, self.tools = cfg, n, "ok", []

    def connect(self): pass

    def close(self): pass


M.Server = Fake
s.update({"workspace": {"path": str(tmp / "Мои документы")}})
mgr.reconcile()
M.Server = orig
x = M.plugin_expand(seen.get("artist-main") or {})
ok(x.get("env", {}).get("DEWIAR_WORKSPACE") == str(tmp / "Мои документы"), "плагину — папка Dewiar из настроек (туда — «Рисунки»)")
src = (ROOT / "core/engine_tools.py").read_text(encoding="utf-8")
ok("«Художник» (действие …art_draw)" in src and "если включить плагин «Художник»" in src, "«нарисуй» без плагина — честно и с подсказкой включить; с плагином — рисует")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
