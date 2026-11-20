"""№933 (20.11, macOS 27, 1.0.51: «мимо 😉, последняя версия тоже не решила»): полоса под светофором студии осталась, хотя
отступ снят и подложка в цвет страницы. С macOS 26 WebKit рисует под строкой заголовка «карман» края прокрутки. Теперь его
прячем тем, что есть у этой версии WebKit, и пишем в журнал, что нашлось."""
import os, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "ui"))
bad = 0


def ok(c, m):
    global bad
    bad += 0 if c else 1
    print(("✅ " if c else "❌ ") + m)


import macui  # noqa: E402
logged = []
macui.log = logged.append


class WV:
    def __init__(self): self.calls = []
    def _setTopScrollPocketHidden_(self, v): self.calls.append(("hidden", v))
    def setTopEdgeEffectEnabled_(self, v): self.calls.append(("enabled", v))
    def _topScrollPocket(self): return None
    def setFrame_(self, r): pass


w = WV()
macui._no_pocket(w)
ok(("hidden", True) in w.calls and ("enabled", False) in w.calls, f"карман и край спрятаны: {w.calls}")
ok(logged and "карман WebView" in logged[0] and "_topScrollPocket" in logged[0], f"в журнале — что нашлось: {logged}")
macui._no_pocket(WV())
ok(len(logged) == 1, "в журнал — один раз за запуск")
macui._no_pocket(object())
ok(True, "у старого WebKit кармана нет — не падает")
src = (ROOT / "ui/macui.py").read_text(encoding="utf-8")
ok("_no_pocket(wv)" in src.split("def _no_insets", 1)[1], "вызывается вместе со снятием отступа")
print("ИТОГ:", "всё в порядке" if not bad else f"ошибок {bad}")
sys.exit(1 if bad else 0)
