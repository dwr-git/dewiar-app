"""№509 (ПК 0.76, 03.11): «Dewiar не запускается (диагностика)». В отчёте: библиотеки в порядке, папки настроек и журналов
пустые (0 файлов) — ядро ни разу не стартовало; включён Kaspersky Internet Security. А ИТОГ говорил «библиотеки в порядке».
Теперь ИТОГ сам говорит: «Dewiar ни разу не запустился: журналов нет. Включён Kaspersky — добавьте папку программы в
исключения (…) или временно выключите защиту и запустите снова» (так же ESET, Avast, AVG, Dr.Web)."""
import os, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


sys.path.insert(0, str(ROOT / "ui")); sys.path.insert(0, str(ROOT / "core"))
import doctor  # noqa: E402
import winav  # noqa: E402
P = [{"name": "Windows Defender", "kind": "defender", "on": False},
     {"name": "Kaspersky Internet Security", "kind": winav.kind_of("Kaspersky Internet Security"), "on": True}]
n = doctor.never_started_note(False, P)
ok(n.startswith("Dewiar ни разу не запустился: журналов нет.") and "Включён Kaspersky" in n and "исключения" in n
   and "Угрозы и исключения" in n and "временно выключите защиту" in n, f"нет журналов, включён Kaspersky: {n}")
for name, want in (("ESET Security", "ESET"), ("Avast Free Antivirus", "Avast"), ("AVG AntiVirus Free", "AVG"), ("Dr.Web Security Space", "Dr.Web")):
    t = doctor.never_started_note(False, [{"name": name, "kind": winav.kind_of(name), "on": True}])
    ok(f"Включён {want} —" in t, f"{name} → «Включён {want}»: {t}")
ok(doctor.never_started_note(False, [{"name": "Kaspersky", "kind": "kaspersky", "on": False}]) == "Dewiar ни разу не запустился: журналов нет.",
   "Kaspersky выключен — только «ни разу не запустился»")
ok(doctor.never_started_note(False, [{"name": "Windows Defender", "kind": "defender", "on": True}]) == "Dewiar ни разу не запустился: журналов нет.",
   "только Защитник — без совета про сторонний антивирус")
ok(doctor.never_started_note(True, P) == "", "журналы есть — ничего не добавляем")
src = (ROOT / "ui/doctor.py").read_text(encoding="utf-8")
ok("first = never_started_note(started, prods)" in src and '"ИТОГ: " + (first' in src and '("core.log", "ui.log")' in src,
   "ИТОГ начинается с этого, если журналов ядра и окна нет")
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
