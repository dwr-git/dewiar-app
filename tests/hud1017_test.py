"""Виджет компьютера (отзыв 17.10):
- «шарик мелкий, часто не понятно, слушает она или нет… может этот кружочек вообще убрать?» — значка-шарика больше нет:
  окно одно (карточка), кнопки «свернуть в значок» нет, сохранённый режим «mini» открывается карточкой;
- подсказка у портрета («Удерживайте (или пробел) — диктовка любой длины…») вылезала за края виджета и обрезалась —
  подсказки теперь свои, внутри карточки, переносятся по словам."""
import os, re, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


app = (ROOT / "ui/app.py").read_text(encoding="utf-8")
hud = (ROOT / "ui/hud.html").read_text(encoding="utf-8")
ok('BASE_SIZES = {"card": (300, 420)}' in app and app.count('for m in ("card",):') == 2 and 'uis.get("hud_mode") == "mini"' not in app,
   "одно окно виджета — карточка; сохранённый «mini» тоже открывается карточкой (Linux и Windows)")
ok('id="b-mini"' not in hud and "setMode(\"mini\")" not in hud, "в карточке нет кнопки «свернуть в значок»")

# «Закинуть идею» (отзыв 17.10: окно уехало на другой монитор, верх за краем экрана — закрыть было нечем): ставим на монитор,
# где мышь, и держим целиком в рабочей области; то же сочетание ещё раз — окно прячется
cap = app.split("    def show_capture", 1)[1].split("    def _focus_title", 1)[0]
ok("_keep_on_screen(gw, True)" in cap and "self.close_capture()" in cap and "def _keep_on_screen(gw, center=False)" in app
   and "get_workarea()" in app.split("def _keep_on_screen", 1)[1][:2500],
   "окно идеи: на мониторе с мышью и целиком на экране; повторное сочетание — прячет")
import types  # noqa: E402
sys.path.insert(0, str(ROOT / "ui"))
try:
    import app as A  # noqa: E402
    calls = []
    st = types.SimpleNamespace(_capture=object(), _capture_shown=True, close_capture=lambda: calls.append("close"))
    r = A.Api.show_capture(st)
    ok(r is True and calls == ["close"], f"окно идеи на экране — сочетание его прячет: {calls}")
except ImportError as e:
    print(f"(ui/app.py не импортируется здесь: {e} — проверено по тексту)")

from playwright.sync_api import sync_playwright  # noqa: E402
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 300, "height": 420})
    pg.goto((ROOT / "ui/hud.html").as_uri()); pg.wait_for_timeout(800)
    pg.evaluate("() => { document.body.classList.remove('mini'); }")
    pg.hover("#orb"); pg.wait_for_timeout(900)
    r = pg.evaluate("""() => { const t = document.getElementById('htip'), b = t.getBoundingClientRect(), o = document.getElementById('orb');
        return { on: t.classList.contains('on'), text: t.textContent, l: b.left, r: b.right, top: b.top, bot: b.bottom, title: o.getAttribute('title') }; }""")
    ok(r["on"] and "диктовка любой длины" in r["text"] and r["l"] >= 0 and r["r"] <= 300 and r["top"] >= 0 and r["bot"] <= 420 and r["title"] is None,
       f"подсказка у портрета — внутри карточки, по словам, без системной: {r}")
    # №868: подсказка не под указателем-рукой — ниже указателя (или выше кнопки), а не вплотную под кнопкой
    pg.mouse.move(5, 5); pg.wait_for_timeout(300)
    btn = pg.evaluate("""() => { const b = [...document.querySelectorAll('button[title], button[data-tip]')].find(x => {
        const r = x.getBoundingClientRect(); return r.width > 8 && r.height > 8 && r.top >= 0 && r.top < 120 && getComputedStyle(x).visibility !== 'hidden'; });
        if (!b) return null; const r = b.getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2, id: b.id }; }""")
    if btn:
        pg.mouse.move(btn["x"], btn["y"]); pg.wait_for_timeout(900)
        t = pg.evaluate("() => { const t = document.getElementById('htip'), b = t.getBoundingClientRect(); return { on: t.classList.contains('on'), top: b.top, bot: b.bottom }; }")
        ok(t["on"] and (t["top"] >= btn["y"] + 26 or t["bot"] <= btn["y"] - 4),
           f"№868: подсказка кнопки {btn['id']} не под указателем (мышь y={btn['y']:.0f}): {t}")
    else:
        print("(в верхней части виджета нет видимой кнопки с подсказкой — пропуск)")
    pg.mouse.move(5, 5); pg.wait_for_timeout(300)
    ok(not pg.evaluate("document.getElementById('htip').classList.contains('on')"), "увели мышь — подсказка ушла")
    b.close()
print("\nИТОГ:", "всё прошло" if not fails else f"не прошло {len(fails)}")
sys.exit(1 if fails else 0)
