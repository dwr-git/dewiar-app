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
ok("const smileGoal = (!L.soft || L.geo.smile) && !talking" in src, "у образа улыбка — только настоящая, из кадра с улыбкой (geo.smile); у обычной Лиры и Патрика — как была")
import json as _j, re as _re  # noqa: E402
# 22.11 (владелец: «улыбаются слишком часто… раза в 3 реже», базовая Лира — как была): все три повода — с множителем rare
ok("const rare = L.geo && L.geo.smile ? 1 / 3 : 1;" in src and "Math.random() < 0.3 * rare" in src
   and "tnWarm ? Math.random() < rare : !tnSoft && Math.random() < 0.5 * rare" in src,
   "образы с настоящей улыбкой улыбаются втрое реже (в тишине, после ответа, на радостное), базовая Лира — как была")
conf = _re.findall(r'"(lira-\w+|patrik-\w+)": \{[^\n]*"smile": (\[[^\]]*\])', src)
ok(len(conf) == 19 and all((ROOT / "ui/assets/live" / f"{k}-smile.webp").exists() for k, _ in conf),
   f"владелец 21.11 прислал кадры с улыбкой — у всех 19 образов настоящая улыбка (рамка низа лица): {len(conf)}")
print("ИТОГ:", "всё прошло" if not fails else f"{len(fails)} не прошло")
sys.exit(1 if fails else 0)
