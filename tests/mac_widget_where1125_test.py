"""№1049 (25.11, Mac, третий раз): «после „Лира!“ виджет открывается где-то за экраном, виден с 4–5-й попытки».
Положение уже проверяется (№880), но причины в отчётах не видно. После каждого показа на имя — строка в журнал окна:
где окно, на каком экране, на этом ли рабочем столе, видно ли его на самом деле, уровень и прозрачность."""
import os, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


s = (ROOT / "ui/macui.py").read_text(encoding="utf-8")
show = s[s.index("    def show(self):"):s.index("    def _hide_now(self):")]
ok('_where(win, "показ на имя")' in show, "показ на имя — запись, где окно")
w = s[s.index("def _where(win, why):"):s.index("def everywhere(win):")]
for k in ("isOnActiveSpace", "occlusionState", "screen()", "level()", "alphaValue"):
    ok(k in w, f"в записи: {k}")
ok("_main(run)" in w, "окно читаем в главном потоке Cocoa")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
