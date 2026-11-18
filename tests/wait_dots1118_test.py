"""Владелец 18.11: на телефоне точки ожидания ответа — третья видна на треть. Причина: полоска растёт ступенями
steps(3), а такие ступени до конечной ширины не доходят (8 → 14,3 → 20,7 вместо 27). Проверка: на каждой ступени —
целое число точек, на последней — все три."""
import re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
css = (ROOT / "android/assets/www/app.css").read_text(encoding="utf-8")
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


rule = re.search(r"#bot\.wait::after\s*\{([^}]*)\}", css)
ok(bool(rule), "правило точек ожидания найдено")
body = rule.group(1) if rule else ""
tile = re.search(r"/\s*(\d+(?:\.\d+)?)px\s+\d+px\s+repeat-x", body)
rad = re.search(r"circle\s+(\d+(?:\.\d+)?)px", body)
steps = re.search(r"animation:\s*(\w+)\s+[\d.]+m?s\s+steps\((\d+)\)", body)
ok(bool(tile and rad and steps), "размер точки, шаг и ступени читаются")
if tile and rad and steps:
    t, r, name, n = float(tile.group(1)), float(rad.group(1)), steps.group(1), int(steps.group(2))
    kf = re.search(r"@keyframes\s+" + name + r"\s*\{\s*from\s*\{\s*width:\s*([\d.]+)px;?\s*\}\s*to\s*\{\s*width:\s*([\d.]+)px", css)
    ok(bool(kf), "ширина в ключевых кадрах читается")
    if kf:
        a, b = float(kf.group(1)), float(kf.group(2))
        widths = [a + (b - a) * i / n for i in range(n)]       # steps(n) = jump-end: конечная ширина не показывается
        shown = []
        for w in widths:
            whole = sum(1 for k in range(n) if k * t + t / 2 + r <= w + 0.01)
            cut = any(k * t + t / 2 - r < w < k * t + t / 2 + r - 0.01 for k in range(n))
            shown.append((round(w, 1), whole, cut))
        ok(not any(c for _, _, c in shown), f"ни на одной ступени точка не обрезана: {shown}")
        ok([s[1] for s in shown] == list(range(1, n + 1)), f"ступени показывают 1, 2, 3 точки: {[s[1] for s in shown]}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
