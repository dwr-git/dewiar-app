"""№445 (31.10): «при публикации поста в канал Telegram не видно полностью сформированного поста — в строке для правки
открывается одной строкой, неудобно осмыслить»; «ИИ пост при написании обрывает и не дописывает». Правка поста — большое
поле (Enter — новая строка, Ctrl+Enter — сохранить); пост пишется с запасом длины, оборванный хвост — до законченной фразы."""
import os, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
import pbot_posts as P  # noqa: E402
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


ok(P._whole("Первая фраза. Вторая фраза длиннее. Третья оборва") == "Первая фраза. Вторая фраза длиннее.", "оборванный пост — до последней фразы")
ok(P._whole("Всё хорошо. Конец!") == "Всё хорошо. Конец!" and P._whole("Чай 🍵") == "Чай 🍵", "законченный — не трогаем")
src = (ROOT / "core/pbot_posts.py").read_text(encoding="utf-8")
ok("max_tokens=2400" in src, "пост пишется с запасом длины")
ok('multi: true' in (ROOT / "ui/studio/pbot_posts.js").read_text(encoding="utf-8"), "правка поста в студии — большим полем")
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page()
    pg.set_content("<html><body></body></html>"); pg.add_script_tag(path=str(ROOT / "ui/assets/dialog.js"))
    pg.evaluate("() => { window.R = undefined; askText('Текст поста', 'Строка один', { ok: 'Сохранить', multi: true }).then(v => { window.R = v; }); }")
    pg.wait_for_timeout(300)
    ok(pg.locator(".dwq textarea").count() == 1 and pg.evaluate("document.querySelector('.dwq textarea').getBoundingClientRect().height") >= 200,
       "большое поле, а не строка")
    pg.keyboard.press("End"); pg.keyboard.press("Enter"); pg.keyboard.type("Строка два"); pg.wait_for_timeout(100)
    ok(pg.evaluate("window.R") is None, "Enter — новая строка, окно не закрылось")
    pg.keyboard.press("Control+Enter"); pg.wait_for_timeout(300)
    ok(pg.evaluate("window.R") == "Строка один\nСтрока два", f"Ctrl+Enter — сохранено целиком: {pg.evaluate('window.R')!r}")
    pg.evaluate("() => { window.R2 = undefined; askText('Имя', 'Ли', {}).then(v => { window.R2 = v; }); }"); pg.wait_for_timeout(250)
    pg.keyboard.press("Enter"); pg.wait_for_timeout(250)
    ok(pg.evaluate("window.R2") == "Ли" and pg.locator(".dwq input").count() == 0, "обычный вопрос — как раньше: строка, Enter — готово")
    b.close()
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
