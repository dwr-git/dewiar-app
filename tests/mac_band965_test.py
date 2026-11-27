"""№965 (22.11, Mac, 1.0.62, «восьмая попытка»): над студией — тёмная полоса со светофором. В журнале: «подложка в цвет
страницы rgb(38, 42, 49)» — цвет тёмной темы, а студия светлая. Подложку красили один раз при загрузке и по фону body
(у светлых тем он прозрачный). Теперь: theme.js кладёт основной цвет темы в --sk-base, macui.match_page_bg берёт его и
следит за ним, пока окно открыто (тема сменилась — перекрашивает)."""
import os, sys, tempfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "ui"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    c or fails.append(m)


import macui  # noqa: E402
calls, painted = [], []


class Win:
    seq = ["#262a31", "#262a31", "#dbe5f1"]

    def evaluate_js(self, js):
        calls.append(js)
        if not self.seq:
            raise RuntimeError("окно закрыто")
        return self.seq.pop(0)


macui._paint_under = lambda win, rgb, css: painted.append(css)
macui.time.sleep = lambda s: None
macui.match_page_bg(Win())
ok(painted == ["#262a31", "#dbe5f1"], f"подложка перекрашивается, когда тема сменилась (и не дёргается без смены): {painted}")
ok("--sk-base" in calls[0], "цвет — основной цвет темы (--sk-base), а не фон body")
from playwright.sync_api import sync_playwright  # noqa: E402
page = Path(tempfile.mkdtemp()) / "t.html"
page.write_text(f"""<html><head><link rel="stylesheet" href="{(ROOT / 'ui/assets/skins.css').as_uri()}">
<script>window.dwQuery = () => new URLSearchParams("skin=neusky");</script>
<script src="{(ROOT / 'ui/assets/skins.js').as_uri()}"></script><script src="{(ROOT / 'ui/studio/theme.js').as_uri()}"></script>
</head><body></body></html>""", encoding="utf-8")
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(); pg.goto(page.as_uri())
    base = pg.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--sk-base').trim()")
    pg.evaluate("studioSkin('neudark')")
    base2 = pg.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--sk-base').trim()")
    b.close()
ok(base.lower() == "#dbe5f1" and base2.lower() == "#262a31", f"«Небесный» — светлая подложка, «Графитовый» — тёмная: {base}, {base2}")
print("ИТОГ: " + ("всё прошло" if not fails else f"провалов {len(fails)}"))
sys.exit(1 if fails else 0)
