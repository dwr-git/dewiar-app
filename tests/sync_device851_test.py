"""Отчёт №851 (18.11, Windows): «Устройства — при каждом запуске клонируется подключённое устройство»: пять одинаковых
«DESKTOP-…», и каждое новое — с запуска. Если sync.json не прочитался (или пропал), компьютер заводил новый id и выходил
на связь новым устройством. Теперь id лежит и рядом с настройками (CONFIG_DIR/sync_device): компьютер остаётся собой,
а почему sync.json не прочитался — в журнале. Настоящий core/sync.py (Sync._load/_save)."""
import json, logging, os, sys, tempfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ.update(DEWIAR_CONFIG_DIR=str(tmp / "cfg"), DEWIAR_STATE_DIR=str(tmp / "st"))
(tmp / "cfg").mkdir(); (tmp / "st").mkdir()
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import sync as SY  # noqa: E402
logs = []
logging.getLogger("dewiar.sync").addHandler(type("H", (logging.Handler,), {"emit": lambda self, r: logs.append(r.getMessage())})())


def fresh():
    s = SY.Sync.__new__(SY.Sync)
    s.path = SY.SB.STATE_DIR / "sync.json"
    s.state = s._load()
    return s


a = fresh(); dev = a.state["device"]
a._save()
ok((tmp / "cfg" / "sync_device").read_text(encoding="utf-8") == dev, f"id компьютера сохранён и рядом с настройками: {dev}")
ok(fresh().state["device"] == dev, "следующий запуск — тот же компьютер")
(tmp / "st" / "sync.json").write_text('{"rev": 5, "device": "pc-', encoding="utf-8")       # оборванная запись
b = fresh()
ok(b.state["device"] == dev, f"sync.json испорчен — устройство прежнее, не клон: {b.state['device']}")
ok(any("sync.json не прочитался" in m and "прежнее" in m for m in logs), f"и почему — в журнале: {logs[-1:]}")
(tmp / "st" / "sync.json").unlink()
ok(fresh().state["device"] == dev, "sync.json пропал — тоже прежнее устройство")
(tmp / "cfg" / "sync_device").unlink(); (tmp / "st" / "sync.json").unlink(missing_ok=True)
c = fresh()
ok(c.state["device"].startswith("pc-") and c.state["device"] != dev, "совсем новая установка — новое устройство, как раньше")
import backup as BK  # noqa: E402
ok("sync_device" in BK.CONFIG_SKIP, "в слепок id компьютера не идёт: восстановят на другом — тот не станет «этим же»")
print("\nИТОГ: " + ("всё прошло" if not fails else f"не прошло {len(fails)}"))
sys.exit(1 if fails else 0)
