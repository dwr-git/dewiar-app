"""Блокнот у виджета, 24.10, владелец:
- 17:18 «Редактор стал справа от Лиры… раньше был слева… можно добавить элемент, чтобы переключать сторону?» — кнопка ⇄ на
  панели листа: Api.pad_flip, выбор — в ui.pad_side; _pad_geom ставит лист с выбранной стороны, а не поместился — с другой;
- 17:19 «Вставил скриншот из буфера, пробовал убрать Ctrl+Z, пробовал Delete — не получается» — выделенная картинка
  убирается клавишами Delete/Backspace и кнопкой «×» на ней; Ctrl+Z сразу после вставки — тоже;
- 17:20 «На панели не хватает разделителя-черты и, может, ещё чего-то полезного» — «Разделитель» и «Цитата»."""
import json, os, re, sys, urllib.parse
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


# ---------- ui/app.py: сторона листа ----------
app = (ROOT / "ui/app.py").read_text(encoding="utf-8")
ns = {}
src = app[app.index("    def _pad_geom(self):"):app.index("    def pad_size(self):")]
consts = re.search(r"^PAD_W, PAD_MIN_H.*$", app, re.M).group(0) + "\n" + re.search(r"^PAD_W_MIN.*$", app, re.M).group(0) + "\n" + \
    re.search(r"^PAD_CLIP = .*$", app, re.M).group(0)
code = "WIN = True\n" + consts + "\nclass winshell:\n    @staticmethod\n    def work_area(h=None):\n        return (0, 0, 1920, 1040)\n" \
    "    @staticmethod\n    def rect(h):\n        return (0, 0, 340, 420)\n    @staticmethod\n    def scale(h):\n        return 1.0\n" \
    "ZOOM = [1.0]\nSIZES = {'card': (340, 420)}\nPOS = [(300, 300)]\nclass A:\n" + src + "\n    def get_pos(self, m):\n        return POS[0]\n    def _hwnd(self, m):\n        return 7\n"
exec(code, ns)
a = ns["A"](); a._pad_size = [None, None]
ok(a._pad_geom()["side"] == "right", "как раньше: виджет слева на экране — лист справа (к середине)")
a._pad_side_pref = "left"
ok(a._pad_geom()["side"] == "right", "выбрали «слева», а слева нет места (виджет у края) — лист всё равно справа")
ns["POS"][0] = (1000, 300)
g = a._pad_geom()
ok(g["side"] == "left" and g["x"] + g["w"] + g["gap"] == 1000, f"выбрали «слева» — слева от виджета, прижат к нему: {g}")
a._pad_side_pref = "right"
ok(a._pad_geom()["side"] == "right", "выбрали «справа» — справа, хоть виджет и в правой половине")
ok("def pad_flip(self)" in app and "_pad_apply(g, True)" in app and '"pad_side": "auto"' in (ROOT / "core/settings.py").read_text(encoding="utf-8"),
   "Api.pad_flip двигает лист сразу; ui.pad_side — в настройках")

# ---------- страница ----------
from playwright.sync_api import sync_playwright  # noqa: E402
import base64, io  # noqa: E402
from PIL import Image  # noqa: E402
_b = io.BytesIO(); Image.new("RGB", (640, 360), (40, 60, 120)).save(_b, "PNG"); PNG = base64.b64encode(_b.getvalue()).decode()
FAKE = """window.apiCalls = []; window.pywebview = { api: new Proxy({}, { get: (_, k) => (...a) => { apiCalls.push([k, ...a]);
  if (k === 'pad_flip') return Promise.resolve(window.flipTo || 'right');
  if (k === 'pad_size') return Promise.resolve([440, 520]);
  return Promise.resolve(true); } }) };"""
CORE = r"""
(() => { window.calls = [];
  const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.connected = true;
    core.call = async (c, a) => { calls.push([c, a]);
      if (c === "pad_tabs") return { tabs: [{ name: "Главное", mtime: 1 }], active: "Главное" };
      if (c === "pad_read") return { name: a.name, text: "# Главное\n\nРанвайр - проверить\n\nГрог - токен\n", mtime: 1 };
      if (c === "pad_attach") return { line: "![Снимок](Вложения/Главное/Снимок.png)" };
      if (c === "pad_write") return { mtime: 2 };
      return {}; }; };
  ready(); })();
"""
md = lambda pg: pg.evaluate("PadMD.html2md(document.querySelector('#ed').innerHTML)")
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 454, "height": 600}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.add_init_script(FAKE); pg.add_init_script(CORE)
    pg.goto((ROOT / "ui/pad.html").as_uri() + "?skin=neusky&cfg=" + urllib.parse.quote(json.dumps({"side": "right", "gap": 14, "clips": []})))
    pg.wait_for_timeout(1200)

    def paste_image():
        pg.click("#ed p:last-of-type"); pg.keyboard.press("End")
        pg.evaluate(f"""(async () => {{ const r = await fetch('data:image/png;base64,{PNG}'); const bl = await r.blob();
            await addImages([new File([bl], 'image.png', {{ type: 'image/png' }})]); }})()""")
        pg.wait_for_timeout(400)
    # Ctrl+Z сразу после вставки
    paste_image()
    ok(pg.locator("#ed img").count() == 1, "скриншот вставлен")
    pg.keyboard.press("Control+z"); pg.wait_for_timeout(200)
    ok(pg.locator("#ed img").count() == 0 and "Грог" in md(pg), f"Ctrl+Z сразу после вставки — картинки нет, текст на месте: {md(pg)!r}")
    # щелчок — рамка и «×»; Delete — убрана
    paste_image(); pg.keyboard.type("после"); pg.wait_for_timeout(100)
    pg.keyboard.press("Control+z"); pg.wait_for_timeout(200)
    ok(pg.locator("#ed img").count() == 1, "напечатали после вставки — Ctrl+Z снова обычная отмена, картинка цела")
    pg.click("#ed img"); pg.wait_for_timeout(150)
    ib, xb = pg.locator("#ed img").bounding_box(), pg.locator("#imgx").bounding_box()
    ok(pg.is_visible("#imgx") and xb and ib["x"] < xb["x"] < ib["x"] + ib["width"] and ib["y"] <= xb["y"] < ib["y"] + 60,
       f"щелчок по картинке — рамка и «×» в её углу: {xb}")
    pg.keyboard.press("Delete"); pg.wait_for_timeout(200)
    ok(pg.locator("#ed img").count() == 0 and not pg.is_visible("#imgx") and "Ранвайр" in md(pg), "Delete — выделенная картинка убрана")
    paste_image(); pg.click("#ed img"); pg.keyboard.press("Backspace"); pg.wait_for_timeout(200)
    ok(pg.locator("#ed img").count() == 0, "Backspace — тоже")
    paste_image(); pg.click("#ed img"); pg.wait_for_timeout(100); pg.click("#imgx"); pg.wait_for_timeout(200)
    ok(pg.locator("#ed img").count() == 0, "кнопка «×» на картинке — убрана")
    pg.wait_for_timeout(900)
    w = [c[1] for c in pg.evaluate("calls") if c[0] == "pad_write"]
    ok(w and "Вложения" not in w[-1]["text"], "в файл заметки ушло без картинки")
    # разделитель и цитата
    pg.click("#ed p:nth-of-type(1)"); pg.keyboard.press("End")
    pg.click("#tools button[data-c='hr']"); pg.wait_for_timeout(150)
    m = md(pg)
    ok(re.search(r"Ранвайр - проверить\n+---\n", m) and pg.locator("#ed hr").count() == 1, f"«Разделитель» — черта после строки: {m!r}")
    pg.keyboard.type("под чертой"); pg.wait_for_timeout(100)
    ok("---\n\nпод чертой" in md(pg), f"курсор — сразу под чертой: {md(pg)!r}")
    pg.click("#ed p:has-text('Грог')"); pg.click("#tools button[data-c='quote']"); pg.wait_for_timeout(150)
    ok("> Грог - токен" in md(pg), f"«Цитата» — строка в цитату: {md(pg)!r}")
    pg.click("#ed blockquote p"); pg.click("#tools button[data-c='quote']"); pg.wait_for_timeout(150)
    ok("> Грог" not in md(pg) and "Грог - токен" in md(pg), "ещё раз — цитата снята")
    tb = pg.locator("#tools").bounding_box()
    last = pg.locator("#tools > button.tool[data-c]").last.bounding_box()
    first = pg.locator("#tools > button.tool[data-c]").first.bounding_box()
    ok(last and abs(last["y"] - first["y"]) < 2 and last["x"] + last["width"] <= tb["x"] + tb["width"] + 1, f"узкий лист (как задумано, 440) — панель в одну строку: {last}, панель {tb}")
    # сторона
    pg.evaluate("window.flipTo = 'left'"); pg.click("#b-side"); pg.wait_for_timeout(300)
    saved = [c[1] for c in pg.evaluate("calls") if c[0] == "settings_save"]
    ok(any(c[0] == "pad_flip" for c in pg.evaluate("apiCalls")) and any(s["patch"]["ui"].get("pad_side") == "left" for s in saved),
       "⇄ — лист на другую сторону, выбор запомнен (ui.pad_side)")
    pg.evaluate("padCfg({ side: 'left', gap: 14, clips: [] }); window.flipTo = 'left'"); pg.click("#b-side"); pg.wait_for_timeout(300)
    ok("места" in pg.inner_text("#foot"), f"с той стороны не поместился — так и сказано: {pg.inner_text('#foot')!r}")
    pg.screenshot(path="/tmp/claude-0/pad_tools.png")
    ok(not errs, f"без ошибок на странице: {errs[:2]}")
    b.close()

print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
