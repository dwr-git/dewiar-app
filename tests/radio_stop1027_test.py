"""№315 (пакет 27.10): «много раз просил выключить радио — Джарвис отвечает „отключил“, а оно играет». «Выключить
радио», «выключи, пожалуйста, радио» не узнавались быстрой командой, модель включала новую станцию. Теперь — стоп без
модели; «включи радио» по-прежнему включает."""
import os, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
import music  # noqa: E402
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


for t in ("выключить радио", "выключи пожалуйста радио", "выключи радио", "хватит музыку", "выключи это радио пожалуйста",
          "отключи музыку", "ну выключи уже радио", "выруби музыку"):
    ok(music.parse(t, active=True) == {"op": "stop"}, f"«{t}» — стоп без модели")
ok(music.parse("включи радио", active=True) != {"op": "stop"}, "«включи радио» — не стоп")
ok(music.parse("выключи свет", active=True) is None, "«выключи свет» — не про радио")
tools_src = (ROOT / "core/tools.py").read_text(encoding="utf-8")
ok("media_control с action stop, а не play_radio" in tools_src, "модели сказано: выключать — media_control, а не play_radio")
print("ИТОГ:", "OK" if not fails else f"{len(fails)} ошибок")
sys.exit(1 if fails else 0)
