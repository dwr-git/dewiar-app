"""Владелец 22.11: «при настройке цветов нет чёрного цвета». Чёрный — в палитре персонажа; тёмный цвет на тёмном диске облика
не виден (и наложение «lighter» его не складывает) — у тёмного цвета диск светлый, рисунок — обычным наложением, как тушь.
Новый персонаж случайным цветом чёрный не получает."""
import os, sys, tempfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    c or fails.append(m)


core = (ROOT / "ui/studio/core.js").read_text(encoding="utf-8")
ok('"#16181D"]' in core, "в палитре персонажа есть чёрный")
ok("COLORS.length - 1" in (ROOT / "ui/studio/personas.js").read_text(encoding="utf-8"), "новый персонаж случайным цветом — не чёрный")
from playwright.sync_api import sync_playwright  # noqa: E402
page = Path(tempfile.mkdtemp()) / "e.html"
page.write_text(f"""<body style="margin:0;background:#888"><canvas id=a style="width:160px;height:160px"></canvas>
<canvas id=b style="width:160px;height:160px"></canvas><script src="{(ROOT / 'ui/assets/entities.js').as_uri()}"></script><script>
new DewiarEntity(document.getElementById('a'), {{style: 'particles', color: '#16181D', plate: true}});
new DewiarEntity(document.getElementById('b'), {{style: 'particles', color: '#4FC3FF', plate: true}});</script></body>""", encoding="utf-8")
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 340, "height": 170}); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(page.as_uri()); pg.wait_for_timeout(900)
    lum = pg.evaluate("""() => ['a', 'b'].map(id => { const c = document.getElementById(id), x = c.getContext('2d');
        const d = x.getImageData(Math.round(c.width * 0.12), Math.round(c.height * 0.5), 1, 1).data; return d[0] + d[1] + d[2]; })""")
    b.close()
ok(not errs and lum[0] > 600 and lum[1] < 200, f"чёрный — на светлом диске, обычный цвет — на тёмном, как был: {lum} {errs}")
print("ИТОГ: " + ("всё прошло" if not fails else f"провалов {len(fails)}"))
sys.exit(1 if fails else 0)
