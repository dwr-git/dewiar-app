"""№921 (Mac, 1.0.48, снимок): над студией тёмно-серая полоса со светофором («как в Unsloth — без этой линии»). Строка
заголовка прозрачная, но WKWebView держит сверху отступ безопасной зоны (safeArea 28 в журнале окна), а под страницей —
серый цвет окна по умолчанию. Теперь подложка страницы и окно — в цвет самой студии (match_page_bg после загрузки)."""
import os, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "ui")); sys.path.insert(0, str(ROOT / "core"))
bad = 0
def ok(c, m):
    global bad
    bad += 0 if c else 1
    print(("✅ " if c else "❌ ") + m)

src = (ROOT / "ui/macui.py").read_text(encoding="utf-8")
ns = {}
exec(src[src.index("def _rgb(css):"):src.index("def match_page_bg(")], ns)
rgb = ns["_rgb"]
ok(rgb("rgb(10, 10, 15)") == (10 / 255, 10 / 255, 15 / 255) and rgb("rgba(227, 234, 244, 1)")[0] == 227 / 255, "цвет страницы читается из CSS")
ok(rgb("#0a0a0f") == (10 / 255, 10 / 255, 15 / 255) and rgb("") is None and rgb("transparent") is None, "и в виде #rrggbb; пустое — нет цвета")
fn = src[src.index("def match_page_bg("):src.index("def _rect(")]
ok("setUnderPageBackgroundColor_" in fn and "setBackgroundColor_" in fn and "getComputedStyle(document.body)" in fn,
   "подложка страницы и окно — в цвет студии")
ok("threading.Thread(target=match_page_bg, args=(win,), daemon=True).start()" in src, "после загрузки студии — в фоне (не в главном потоке)")
print("ALL OK" if not bad else f"FAILED {bad}")
sys.exit(1 if bad else 0)
