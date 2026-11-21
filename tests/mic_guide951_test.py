"""Жалоба №951 (21.11): «нужна функция отключения микрофона… спрашиваешь агента, как это отключить, — выдаёт неправильный
путь». Кнопка-микрофон в панели виджета есть (отпускает микрофон — им могут пользоваться другие программы и телефон с теми же
наушниками), но в руководстве её не было — помощница не могла подсказать. И владелец 21.11: улыбка образов — гримаса, «лучше
вообще без улыбки»."""
import os, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import guide  # noqa: E402
for q in ("как выключить микрофон, чтобы ты не слушала", "Микрофон занят агентом, как отключить микрофон?"):
    r = guide.search(q, "pc")
    ok(r and r[0].get("id") == "widget" and any("Кнопка-микрофон" in h for h in r[0].get("how") or []),
       f"«{q}» — руководство отвечает про кнопку-микрофон в виджете")
src = (ROOT / "ui/assets/entities.js").read_text(encoding="utf-8")
ok("const smileGoal = !L.soft && !talking" in src, "у образов улыбки нет (у обычной Лиры и Патрика — как была)")
print("ИТОГ:", "всё прошло" if not fails else f"{len(fails)} не прошло")
sys.exit(1 if fails else 0)
