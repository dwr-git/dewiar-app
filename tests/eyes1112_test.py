"""Владелец 12.11: «посмотреть глазами важно — и в разделе, где она рисует изображения и делает сайты». Сделанный сайт
(site_create, site_edit) и рисунок «Художника» (art_draw, art_animate) — снимок экрана телефона модели со зрением
(engine.eyes_page, Q.LOOK): видно пустоту, наложения, обрезанное, нечитаемое — замечание уходит модели вместе с
результатом («поправь сразу»). Модель без зрения, браузера нет — молча; тот же файл дважды не смотрим."""
import os, sys, tempfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import engine_tools as ET  # noqa: E402
import llm  # noqa: E402
import tools  # noqa: E402

d = Path(tempfile.mkdtemp())
page = d / "Кот.html"
page.write_text("<!doctype html><html><body style='margin:0;background:#fff'><svg width='300' height='300'></svg></body></html>", encoding="utf-8")
calls = []


def fake(prof, system, msgs, cancel=None, **k):
    calls.append(msgs)
    yield '{"verdict":"revise","problems":"рисунок пустой — белый экран"}'


llm.stream_chat = fake


class E(ET.ToolsMixin):
    def __init__(self):
        self._blind = set()

    def llm_profile(self):
        return {"base_url": "http://m", "model": "v", "kind": "openai"}


e = E()
r = e.eyes_page(str(page), "Нарисуй кота")
import quality as Q  # noqa: E402
if Q.html_check([page]) is None:
    print("⚠ браузера нет — пропускаю")
else:
    ok(r == "рисунок пустой — белый экран" and calls and any(x.get("type") == "image_url" for x in calls[0][0]["content"]), f"рисунок — модели снимком, она видит пустоту: {r!r}")
    n = len(calls)
    ok(e.eyes_page(str(page), "x") == r and len(calls) == n, "тот же файл дважды не смотрим")

    def blind(*a, **k):
        raise llm.LLMError("this model does not support images")
        yield ""
    llm.stream_chat = blind
    page.write_text(page.read_text(encoding="utf-8") + "<!-- 2 -->", encoding="utf-8")
    ok(e.eyes_page(str(page), "x") == "" and "http://m|v" in e._blind, "модель без зрения — молча, запомнили")
ok(ET.art_page('{"saved": "/a/Кот.svg", "page": "/a/Кот.html"}') == "/a/Кот.html" and ET.art_page("нет") == "", "из ответа «Художника» — страница рисунка")
ok(tools._eyes({"eyes": lambda p, g: "текст белым по белому"}, "/x/index.html", "кофейня").startswith(" ПОСМОТРЕЛА НА РЕЗУЛЬТАТ")
   and tools._eyes({}, "/x", "") == "" and tools._eyes({"eyes": lambda p, g: ""}, "/x", "") == "", "сайт: замечание — к ответу инструмента; без глаз — ничего")
src = (ROOT / "core/tools.py").read_text(encoding="utf-8")
ok(src.count("_eyes(ctx, page,") == 2, "смотрим после site_create и site_edit")
et = (ROOT / "core/engine_tools.py").read_text(encoding="utf-8")
ok('re.search(r"art_(?:draw|animate)$", name)' in et and "self.eyes_page(art_page(" in et, "смотрим после art_draw и art_animate")
ok('self.toolbox.hooks["eyes"] = self.eyes_page' in (ROOT / "core/engine.py").read_text(encoding="utf-8"), "крючок eyes — у инструментов")
if fails:
    sys.exit(1)
print("\n✅ всё в порядке")
