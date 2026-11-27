"""№986 (23.11): задача «Ежемесячный конкурентный анализ» остановилась: «много раз повторил одно и то же действие». Модель
8 раз запускала run_python с кодом «[убрано из памяти: 3543 знаков]» — повторяла свой старый вызов, а большой код в нём
память задачи уже заменила пометкой; получала SyntaxError и снова то же. Теперь пометка вместо кода или содержимого —
понятная ошибка: что произошло и что делать."""
import os, sys, tempfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ["DEWIAR_STATE_DIR"] = str(tmp / "st"); os.environ["DEWIAR_CONFIG_DIR"] = str(tmp / "cfg")
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    c or fails.append(m)


import tasks_exec as TE  # noqa: E402
cls = next(v for v in vars(TE).values() if isinstance(v, type) and hasattr(v, "_work"))
r = cls._work(None, None, "run_python", {"code": "[убрано из памяти: 3543 знаков]"})
ok(r.startswith("Ошибка") and "не код" in r and "заново целиком" in r, f"код-пометка — понятная ошибка: {r[:120]}")
r2 = cls._work(None, None, "write_file", {"path": "outputs/a.md", "content": "[убрано из памяти: 9000 знаков — в файле outputs/a.md]"})
ok(r2.startswith("Ошибка") and "read_file" in r2, "содержимое-пометка — взять из файла")
print("ИТОГ: " + ("всё прошло" if not fails else f"провалов {len(fails)}"))
sys.exit(1 if fails else 0)
