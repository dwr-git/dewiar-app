"""Владелец 22.11: улыбка образов «не идеально: рот как будто светлее, улыбка высоковато, при смене виден промежуточный
вариант — и нижние губы, и верхние». Слой улыбки: линия смыкания губ — та же, что в основном кадре (не выше), яркость губ —
как в основном; смена улыбки у образов — почти мгновенная (~0,15 с). Базовая Лира — как была."""
import json, os, re, sys
from pathlib import Path
import numpy as np
from PIL import Image
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    c or fails.append(m)


src = (ROOT / "ui/assets/entities.js").read_text(encoding="utf-8")
ok("(up ? 14 : 2.5) : 3)" in src, "улыбка образов появляется быстро (14), гаснет плавно (2,5, владелец 22.11 вечер: «резко исчезает»), у базовой Лиры — как было (3)")
d = ROOT / "ui/assets/live"
bad, lips = [], []
for name, conf in re.findall(r'"((?:lira|patrik)-[a-z]+)": (\{"own".*?\}\}),?\n', src):
    g = json.loads(conf)["geo"]
    if "smile" not in g:
        continue
    b = Image.open(d / f"{name}.webp").convert("RGBA").resize((1080, 1080), Image.LANCZOS)
    sx, sy, sw, sh = g["smile"]
    s2 = Image.open(d / f"{name}-smile.webp").convert("RGBA").resize((int(sw * 3), int(sh * 3)), Image.LANCZOS)
    im = b.copy(); im.alpha_composite(s2, (int(sx * 3), int(sy * 3)))
    A = np.asarray(b).astype(float)[..., :3].mean(2); B = np.asarray(im).astype(float)[..., :3].mean(2)
    mx, my, mw, mh = g["mouth"]
    cx, y0, y1 = int((mx + mw / 2) * 3), int((my + mh / 2 - 12) * 3), int((my + mh / 2 + 10) * 3)
    sa = (y0 + np.argmin(A[y0:y1, cx - 15:cx + 15].mean(1))) / 3
    sb = (y0 + np.argmin(B[y0:y1, cx - 15:cx + 15].mean(1))) / 3
    if abs(sa - sb) > 0.7 and not name.startswith("patrik-home"):
        bad.append((name, sa, sb))
    my_, mx_ = int(my * 3), int(mx * 3)
    lips.append((round(abs(B[my_:my_ + int(mh * 3), mx_:mx_ + int(mw * 3)].mean() - A[my_:my_ + int(mh * 3), mx_:mx_ + int(mw * 3)].mean()), 1), name))
ok(not bad, f"линия губ улыбки — там же, где в основном кадре (не выше): {bad}")
avg = sum(x for x, _ in lips) / max(1, len(lips))
ok(lips and max(lips)[0] < 2.5 and avg < 1.2, f"рот в улыбке не светлее основного кадра (было в среднем 5, до 12 из 255): в среднем {avg:.1f}, {sorted(lips)[-2:]}")
print("ИТОГ: " + ("всё прошло" if not fails else f"провалов {len(fails)}"))
sys.exit(1 if fails else 0)
