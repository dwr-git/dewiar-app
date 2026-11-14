"""№700 (пакет 14.11): клип собран и лежит на рабочем столе, а большая задача остановлена «не выполнено»: проверка
итога трижды нашла «ЦИФРЫ БЕЗ ОПОРЫ: 17.4» — это размер файла (17 365 198 байт = 17.4 МБ). Размеры результатов теперь
опора и в КБ/МБ/ГБ (десятичных и двоичных)."""
import os, re, sys, tempfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import quality as Q  # noqa: E402
src = (ROOT / "core/tasks.py").read_text(encoding="utf-8")
m = re.search(r'sizes = " "\.join\((f".*?")\s*\n\s*for n in \(p\.stat\(\)\.st_size for p in outs\)\)', src, re.S)
ok(bool(m), "размеры результатов — в байтах, КБ, МБ, ГБ")
d = Path(tempfile.mkdtemp()); f = d / "клип.mp4"; f.write_bytes(b"\0" * 17365198)
outs = [f]
sizes = eval('" ".join(' + m.group(1) + ' for n in (p.stat().st_size for p in outs))') if m else ""
pool = Q.number_pool(sizes)
ok(Q.unsupported_numbers("Файл: клип.mp4 (17.4 МБ), 1:51.", pool) in ([], ["1"], ["51"]) and
   "17.4" not in Q.unsupported_numbers("Файл: клип.mp4 (17.4 МБ)", pool), "«17.4 МБ» при файле 17 365 198 байт — с опорой")
ok("16.6" not in Q.unsupported_numbers("Размер — 16.6 МиБ", pool), "и в двоичных мегабайтах")
ok("42.5" in Q.unsupported_numbers("Файл весит 42.5 МБ", pool), "чужой размер — по-прежнему без опоры")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
