"""Снимки поведения ядра (чистое ядро, шаг 0 — docs/CORE_PLAN.md): перестройка обязана их не менять.
- действия модели: имя, описание, схема параметров, уровень, подпись, функция — байт в байт;
- наборы действий (сеть, без экрана, экзамен, по умолчанию выключены, ядро облегчённого набора, навыки);
- имена, которые модуль tools отдаёт наружу (их импортирует ядро и проверки) — все на месте;
- команды студии и телефона (engine_commands): весь список имён.
Обновить эталон после НАМЕРЕННОГО изменения: python3 tests/core_snap_test.py --update"""
import json, os, re, sys, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path[:0] = [str(ROOT), str(ROOT / "core")]
import srctext  # noqa: E402
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import tools  # noqa: E402

snap = {"tools": {n: {"description": v[0], "parameters": v[1], "level": v[2], "fn": getattr(v[3], "__name__", str(v[3])),
                      "title": v[4] if len(v) > 4 else None, "rest": [repr(x) for x in v[5:]]} for n, v in tools.TOOLS.items()},
        "sets": {k: sorted(getattr(tools, k)) for k in ("NET_TOOLS", "SAFE_CORE", "SERVER_OFF", "EXAM_ON", "DEFAULT_OFF", "SKILL_TOOLS")
                 if hasattr(tools, k)},
        # имена, которые tools отдаёт наружу: свои функции, классы и константы (модули стандартной библиотеки и их
        # объекты, импортированные для своей работы, — не часть «ручек» ядра)
        "names": sorted(n for n in dir(tools) if not n.startswith("__") and not isinstance(getattr(tools, n), types.ModuleType)
                        and n not in ("datetime", "timedelta", "Path", "STATE_DIR")),
        "commands": sorted(set(re.findall(r'cmd\s*==\s*"([a-z0-9_]+)"', srctext.text(ROOT, "core/engine_commands.py"))
                               + re.findall(r'"([a-z0-9_]+)"', " ".join(re.findall(r"cmd in \(([^)]*)\)", srctext.text(ROOT, "core/engine_commands.py"))))))}
f = ROOT / "tests/snap/core.json"
if "--update" in sys.argv or not f.exists():
    f.write_text(json.dumps(snap, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print("эталон записан:", f, {k: len(v) for k, v in snap.items()})
    sys.exit(0)
ref = json.loads(f.read_text(encoding="utf-8"))
cur = json.loads(json.dumps(snap, ensure_ascii=False, sort_keys=True))
for k in ("tools", "sets", "commands"):
    diff = [x for x in set(ref[k]) | set(cur[k]) if (ref[k].get(x) if isinstance(ref[k], dict) else x in ref[k]) !=
            (cur[k].get(x) if isinstance(cur[k], dict) else x in cur[k])]
    ok(not diff, f"{k}: как в эталоне ({len(cur[k])}){' — отличаются: ' + ', '.join(sorted(diff)[:12]) if diff else ''}")
lost = sorted(set(ref["names"]) - set(cur["names"]))
ok(not lost, f"все имена модуля tools на месте ({len(cur['names'])}){' — пропали: ' + ', '.join(lost[:20]) if lost else ''}")
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
