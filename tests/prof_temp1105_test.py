"""Пакет 05.11, частый сбой: «Задача: float() argument must be a string or a real number, not 'NoneType'» — в профиле
модели было "temperature": null, и запрос к модели падал на float(None). Теперь пустая/None/нечисловая температура — 0,7."""
import os, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
import llm as L  # noqa: E402
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


ok(L.prof_temp({"temperature": None}) == 0.7 and L.prof_temp({}) == 0.7 and L.prof_temp({"temperature": ""}) == 0.7, "None, пусто, нет — 0,7")
ok(L.prof_temp({"temperature": "0.3"}) == 0.3 and L.prof_temp({"temperature": "abc"}) == 0.7, "строка-число — число, мусор — 0,7")
ok(L.creative_temp("напиши стих", None) == L.CREATIVE_TEMP and L.creative_temp("привет", 0.3) == 0.3, "creative_temp — как было")
src = (ROOT / "core/llm.py").read_text(encoding="utf-8")
ok('float(p.get("temperature"' not in src, "в запросах к модели — prof_temp, а не float(p.get(...))")
print("ИТОГ:", "всё прошло" if not fails else f"{len(fails)} ошибок")
sys.exit(1 if fails else 0)
