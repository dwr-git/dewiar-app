"""№756 (15.11): «ответ Лиры в окне виджета прячется, пока я его читаю». Пока Лира договаривает ответ вслух — карточка
не прячется (время на чтение — от конца речи); длинный ответ висит дольше: до минуты, ≈ 850 знаков в минуту."""
import os, re, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


hud = (ROOT / "ui/hud.html").read_text(encoding="utf-8")
i = hud.index("function hideCapLater(ms)")
f = hud[i:i + 700]
ok('if (ms > 1000 && state === "speaking") { hideCapLater(Math.min(ms, 8000)); return; }' in f, "пока говорит — не прячем, ждём конца речи")
m = re.search(r"if \(e\.done\) hideCapLater\(Math\.min\((\d+), (\d+) \+ e\.text\.length \* (\d+)\)\)", hud)
ok(m and int(m.group(1)) >= 60000, "длинный ответ — до минуты на чтение")
if m:
    t = lambda n: min(int(m.group(1)), int(m.group(2)) + n * int(m.group(3)))
    ok(t(600) >= 40000 and t(80) <= 13000, f"600 знаков — {t(600) / 1000:.0f} с, короткий — {t(80) / 1000:.0f} с")
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
