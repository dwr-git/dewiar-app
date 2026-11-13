"""№697 (13.11, телефон, тёмная тема Dewiar): «Судоку — в начале и в конце игры окно с двумя кнопками, вторая сливается: не
видно ни надписи, ни самой кнопки; предполагаю, в остальных играх то же». Вторая кнопка (.ghost) — белый текст на светлом
стекле светлой игры. Теперь в светлых играх карточка и её кнопки — тёмным по светлому. Проверяем все светлые игры полки."""
import os, re, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


def lum(rgb):
    def ch(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = rgb[:3]
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def rgba(s):
    v = [float(x) for x in re.findall(r"[\d.]+", s)]
    return v + [1.0] * (4 - len(v))


try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("нет Playwright"); sys.exit(0)
arc = ROOT / "ui/assets/arcade"
light = [d.name for d in arc.iterdir() if (d / "game.js").exists() and re.search(r"tone:\s*'light'", (d / "game.js").read_text(encoding="utf-8"))]
ok("sudoku" in light, f"светлые игры: {light}")
with sync_playwright() as p:
    b = p.chromium.launch()
    for g in light:
        pg = b.new_page(viewport={"width": 390, "height": 760})
        pg.goto((arc / g / "index.html").as_uri() + "?phone=1"); pg.wait_for_timeout(900)
        got = pg.evaluate("""() => [...document.querySelectorAll('.card .ghost')].map(e => [getComputedStyle(e).color, getComputedStyle(e).backgroundColor])""")
        for color, bg in got:
            fg, bk = rgba(color), rgba(bg)
            base = [244, 247, 252]                    # светлое стекло карточки под кнопкой
            mix = [bk[i] * bk[3] + base[i] * (1 - bk[3]) for i in range(3)]
            l1, l2 = sorted([lum(fg), lum(mix)], reverse=True)
            ok((l1 + 0.05) / (l2 + 0.05) >= 4.5, f"{g}: вторая кнопка читается ({color} на {bg})")
        pg.close()
    b.close()
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
