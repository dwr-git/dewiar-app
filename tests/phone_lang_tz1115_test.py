"""№732 (15.11, Xiaomi с глобальной прошивкой, 0.9.43): «проблема вернулась — невозможно изменить язык распознавания
с английского на русский, русскую речь не распознаёт, если прошивка не русифицирована». С 0.96 приложение на «авто» берёт
язык системы: английская система — английское приложение и английское распознавание. Как на компьютере (русская раскладка):
русский среди языков системы или часовой пояс России, Беларуси, Казахстана, Украины — по-русски. Англичанин в Нью-Йорке —
по-английски, явный выбор в «Оформлении» — как выбрали."""
import os, re, subprocess, sys, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


www = Path(tempfile.mkdtemp()) / "www"
subprocess.run(["bash", str(ROOT / "android/tools/www_assemble.sh"), str(www)], check=True, capture_output=True)
SYS = "(() => { const m = D.mock; D.mock = false; const r = phoneSysLang(); D.mock = m; return r; })()"   # как на телефоне (мост есть)


def lang(b, locale, tz, extra=None):
    ctx = b.new_context(locale=locale, timezone_id=tz, viewport={"width": 412, "height": 900})
    if extra:
        ctx.add_init_script("Object.defineProperty(navigator, 'languages', {get: () => %s})" % extra)
    pg = ctx.new_page(); pg.route(re.compile(r"^https?://"), lambda r: r.abort())
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(1500)
    r = pg.evaluate(SYS)
    ctx.close()
    return r


with sync_playwright() as p:
    b = p.chromium.launch()
    ok(lang(b, "en-US", "Europe/Moscow") == "ru", "система по-английски, пояс Москвы — приложение и распознавание по-русски (№732)")
    ok(lang(b, "en-US", "Europe/Minsk") == "ru" and lang(b, "en-US", "Asia/Almaty") == "ru", "Минск, Алматы — тоже по-русски")
    ok(lang(b, "en-US", "America/New_York") == "en", "англичанин в Нью-Йорке — по-английски, как в 0.96")
    ok(lang(b, "en-US", "America/New_York", '["en-US", "ru-RU"]') == "ru", "русский среди языков системы — по-русски")
    ok(lang(b, "ru-RU", "America/New_York") == "ru", "система по-русски — по-русски, где бы ни был")
    b.close()
src = (ROOT / "android/assets/www/app.js").read_text(encoding="utf-8")
ok("if (!window.DW_SYS_LANG && l === \"en\")" in src, "явный язык системы из проверок (DW_SYS_LANG) — без догадок")
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
