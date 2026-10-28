"""28.10, пользователь: «Сказал: найди у меня в заметках рецепты блюд и покажи их в браузере красиво оформленными. Найти
нашла, но потом создала кучу питоновских скриптов, и вроде создала HTML-разметку, но не в файле, а в самом чате, и начала
зачитывать его структуру со всеми тегами». Теперь: инструмент show_page (файл в «Страницы» + браузер), подсказка модели,
когда просят страницу; HTML в ответе — Лира сама сохраняет страницей и открывает; теги и CSS вслух не читаются."""
import json
import os
import sys
import tempfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ.update(DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_CONFIG_DIR=str(tmp / "cfg"), DEWIAR_DRY_RUN=str(tmp / "launch.log"))
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import quality as Q  # noqa: E402
import tools as T  # noqa: E402
from llm import CodeFilter, speakable  # noqa: E402
from workspace import Workspace  # noqa: E402

ASK = "найди у меня в заметках рецепты блюд и покажи их в браузере красиво оформленными"
ok(Q.PAGE_ASK.search(ASK) and Q.PAGE_ASK.search("сделай страницу с подборкой фильмов") and not Q.PAGE_ASK.search("какая погода завтра")
   and not Q.PAGE_ASK.search("нарисуй схему процесса"), "просьбу «покажи в браузере красиво» узнаём, обычные — нет")
spec = T.TOOLS["show_page"]
ok("НЕ пиши HTML в ответе" in spec[0] and spec[2] == "safe" and "show_page" in T.SAFE_CORE and "show_page" in T.SERVER_OFF,
   "инструмент show_page: безопасный, в основном наборе; в облаке (без браузера) — нет")
ok("show_page" in (ROOT / "core/engine_answer.py").read_text(encoding="utf-8").split("СЕЙЧАС ПРОСЯТ СТРАНИЦУ")[1][:200],
   "просят страницу — модели подсказка: show_page, а не HTML в ответе")


class FakeS:
    def get(self, *k, default=None): return str(tmp / "ws") if k == ("workspace", "path") else default


T.DRY = str(tmp / "launch.log")
ws = Workspace(FakeS())
r = T.t_show_page({"title": "Рецепты: из заметок", "html": "<section><h2>Сырники</h2><ul><li>творог 400 г</li><li>яйцо</li></ul></section>"},
                  {"workspace": ws})
f = ws.ensure() / "Страницы" / "Рецепты  из заметок.html"
page = f.read_text(encoding="utf-8") if f.exists() else ""
ok(f.exists() and "<h1>Рецепты  из заметок</h1>" in page.replace("Рецепты: из заметок", "Рецепты  из заметок") and "<style>" in page
   and "prefers-color-scheme:dark" in page and "Сырники" in page, f"кусок разметки — в оформленную страницу, файлом в «Страницы»: {f.name}")
launched = [json.loads(x) for x in (tmp / "launch.log").read_text(encoding="utf-8").splitlines()]
ok(launched and launched[-1][-1] == str(f), "страница открыта в браузере")
ok("открыта в браузере" in r and "HTML в ответе не повторяй" in r, "модели — что сказать: одна фраза, без HTML")
full = "<!DOCTYPE html><html><head><title>Мои</title></head><body><p>x</p></body></html>"
ok(T.page_html("Мои", full) == full, "полный документ — как есть")
try:
    T.t_show_page({"title": "Пусто", "html": "  "}, {"workspace": ws}); ok(False, "пустая страница — ошибка")
except T.ToolError:
    ok(True, "пустая страница — понятная ошибка, а не пустой файл")

# 28.10 (отзыв писателя): «выведи мою заметку в браузере» — модель отказалась перепечатывать «неудобный» текст. Теперь
# show_page с file показывает заметку целиком сама, без пересказа моделью; правило «материал пользователя» — в подсказке
note = ws.ensure() / "Заметки" / "Эйнштейн и Марич.md"
note.parent.mkdir(parents=True, exist_ok=True)
note.write_text("# Тёмное дело\n\nРоль **Милевы Марич** замалчивается.\n\n- статьи 1905 года\n- E = mc²\n\n> версия для романа\n\n<script>alert(1)</script>\n", encoding="utf-8")
r = T.t_show_page({"file": "Заметки/Эйнштейн и Марич.md"}, {"workspace": ws})
f2 = ws.ensure() / "Страницы" / "Эйнштейн и Марич.html"
pg2 = f2.read_text(encoding="utf-8") if f2.exists() else ""
ok(f2.exists() and "<h2>Тёмное дело</h2>" in pg2 and "<b>Милевы Марич</b> замалчивается" in pg2 and "<li>E = mc²</li>" in pg2
   and "<blockquote>версия для романа</blockquote>" in pg2, "своя заметка — целиком, оформленной страницей, название — по файлу")
ok("<script>alert" not in pg2 and "&lt;script&gt;" in pg2, "HTML внутри заметки — текстом, не выполняется")
ok("file" in T.TOOLS["show_page"][1]["properties"] and "как есть" in T.TOOLS["show_page"][0], "модели — как показать свою заметку (file)")
import boundaries as B  # noqa: E402
ok("не отказывайся" in B.OWN_MATERIAL and "OWN_MATERIAL" in (ROOT / "core/engine_answer.py").read_text(encoding="utf-8")
   and "МАТЕРИАЛ ПОЛЬЗОВАТЕЛЯ" in (ROOT / "android/assets/www/app.js").read_text(encoding="utf-8"),
   "в подсказке компьютера и телефона: свой материал — показывать как есть, без нотаций")
try:
    T.t_show_page({"file": "../../etc/passwd"}, {"workspace": ws}); ok(False, "файл вне папки — отказ")
except Exception:  # noqa: BLE001
    ok(True, "файл вне папки ассистента — отказ")

# HTML в ответе — найти его
ans = "Нашла три рецепта. Вот страница:\n<!DOCTYPE html>\n<html lang=\"ru\"><head><title>Рецепты</title>\n<style>body{font:16px sans-serif}</style></head>\n<body><h1>Рецепты</h1><p>Борщ</p></body>\n</html>\nОткрой её."
doc = Q.page_html_in(ans)
ok(doc.startswith("<!DOCTYPE html>") and doc.endswith("</html>"), "HTML-документ в ответе находится целиком")
ok(Q.page_html_in("```html\n<html><body>a</body></html>\n```").startswith("<html>"), "и в блоке ```html")
ok(Q.page_html_in("Обычный ответ без страницы, a < b.") == "", "обычный ответ — не страница")
eng = (ROOT / "core/engine_answer.py").read_text(encoding="utf-8")
ok('self.toolbox.run("show_page"' in eng and "page_html_in(step_text)" in eng, "HTML в ответе — Лира сама сохраняет страницей и открывает")


# голос: ни тегов, ни CSS
def stream(t, step):
    cf = CodeFilter(); out = ""
    for i in range(0, len(t), step):
        out += cf.feed(t[i:i + step])
    return out + cf.flush()


ans2 = ans.replace("<html lang=\"ru\"><head>", "<html lang=\"ru\">\n<head>").replace("<style>body{font:16px sans-serif}</style>", "<style>\n  body { font: 16px sans-serif; }\n</style>") + "\nЕсли x < 5 — хорошо.\n<b>Совет:</b> сметана к сырникам."
for st in (1, 4, 60):
    out = speakable(stream(ans2, st))
    ok("<" not in out.replace("x < 5", "") and "font" not in out and "DOCTYPE" not in out and "Нашла три рецепта" in out and "Открой её" in out
       and "x < 5" in out and "Совет: сметана к сырникам" in out,
       f"вслух (поток по {st}): без тегов и CSS, текст до и после и «x < 5» на месте: {out!r}")
ok(speakable("Готово: <b>Борщ</b> и <i>плов</i>.<style>a{b:c}</style>") == "Готово: Борщ и плов .", "speakable снимает теги и стили")
app = (ROOT / "android/assets/www/app.js").read_text(encoding="utf-8")
ok("теги вслух не читаем (28.10)" in app, "на телефоне теги тоже не читаются")
sc = json.loads((ROOT / "data/exam/scenarios.json").read_text(encoding="utf-8"))
ok(any(s.get("id") == "page_recipes" for s in sc["scenarios"]), "сценарий экзамена «рецепты в браузере»")
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
