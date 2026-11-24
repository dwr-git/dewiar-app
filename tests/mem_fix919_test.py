"""№919 (ПК 1.0.48, «Добрый тестировщик»): «remember не обновляет файл памяти — при попытке исправить запись (Харламент →
Харламенко) старый факт не удаляется, а новый добавляется рядом; в „Обо мне" остаются дубликаты и неверные записи».
remember(fact, replace=часть старой записи) — неверная строка заменяется, повторы убираются; модель знает об этом из
описания действия."""
import os, sys, tempfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
os.environ["DEWIAR_WORKSPACE"] = tempfile.mkdtemp()
os.environ.setdefault("DEWIAR_CONFIG_DIR", tempfile.mkdtemp()); os.environ.setdefault("DEWIAR_STATE_DIR", tempfile.mkdtemp())
sys.path.insert(0, str(ROOT / "core"))
import workspace as W  # noqa: E402

bad = 0
def ok(c, m):
    global bad
    bad += 0 if c else 1
    print(("✅ " if c else "❌ ") + m)

ws = W.Workspace(None)
ws.remember("Харламент — клиент пользователя, находится в городе Владивосток")
ws.remember("Любит крепкий чай")
r = ws.remember("Харламенко — клиент пользователя, находится в городе Владивосток", replace="Харламент")
mem = ws.memory_get()
ok("Исправил" in r and "Харламенко" in mem and "Харламент " not in mem.replace("Харламенко", "") and mem.count("Владивосток") == 1,
   f"исправление заменяет запись, а не копит рядом: {r}")
ok("Любит крепкий чай" in mem, "остальные факты на месте")
ws.remember("Дочь зовут Аня"); ws.remember("Дочь Аня учится в 5 классе")
r = ws.remember("Дочь зовут Анна", replace="Аня")
mem = ws.memory_get()
ok("Поправил и в других записях (1)" in r and mem.count("Анна") == 2 and "Аня" not in mem and "учится в 5 классе" in mem,
   f"то же неверное имя в другой записи — поправлено слово, факт не потерян: {r}")
r = ws.remember("Работает в Сбере", replace="Газпром")
ok("не нашёл" in r and "Работает в Сбере" in ws.memory_get(), f"старой записи нет — новый факт добавлен и сказано честно: {r}")
r = ws.remember("Пьёт кофе без сахара")
ok(r == "Запомнил.", "обычное «запомни» — как раньше")
sys.path.insert(0, str(ROOT / "core"))
from tools import TOOLS  # noqa: E402
spec = TOOLS["remember"]
ok("replace" in str(spec[1]) and "старая заменится" in spec[0], "модель знает: исправление — replace")
print("ALL OK" if not bad else f"FAILED {bad}")
sys.exit(1 if bad else 0)
