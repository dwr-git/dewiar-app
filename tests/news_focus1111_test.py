"""Владелец 11.11 (Ubuntu): после обновления «Что нового» — заголовок всегда обведён рамкой, «складывается ощущение, что его
можно отредактировать». Заголовок окна получает фокус программой (tabindex="-1"); у таких элементов рамки фокуса нет."""
import os, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


css = (ROOT / "ui/studio/studio.css").read_text(encoding="utf-8")
ok('[tabindex="-1"]:focus, [tabindex="-1"]:focus-visible { outline: none; box-shadow: none; }' in css,
   "у заголовков с программным фокусом нет рамки (и в WebKitGTK)")
html = (ROOT / "ui/settings.html").read_text(encoding="utf-8")
ok('<h2 id="nw-title" tabindex="-1" autofocus>' in html, "«Что нового»: фокус по-прежнему на заголовке, а не на кнопке")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
