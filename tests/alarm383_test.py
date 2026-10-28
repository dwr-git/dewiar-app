"""№383 (28.10, Windows 11, масштаб экрана): окно напоминания — «перекрывает поле с наименованием задачи; если текст на двух
строчках, вторую не видно». Текст напоминания не сжимается под кнопками: в низком окне меньше колокол и время, а не текст;
длинному тексту окно выше (ui/app.py)."""
import os, re, sys
from pathlib import Path
from urllib.parse import urlencode
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    for (w, h), text in (((507, 407), "Проверить чайник"), ((507, 407), "Позвонить Артёму Бородину насчёт заявки в БЕЛГИЭ и договора"),
                         ((520, 440), "Позвонить Артёму Бородину насчёт заявки в БЕЛГИЭ и договора"), ((416, 352), "Выпить таблетку от давления")):
        pg = b.new_page(viewport={"width": w, "height": h}); pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };")
        pg.goto((ROOT / "ui/alarm.html").as_uri() + "?" + urlencode({"id": "r1", "text": text, "title": "Напоминание", "at": "2026-10-28T13:24:00"}))
        pg.wait_for_timeout(500)
        r = pg.evaluate("""() => { const t = document.getElementById('text'), o = document.getElementById('ok'), a = t.getBoundingClientRect(), k = o.getBoundingClientRect();
          return [Math.round(a.bottom), Math.round(k.top), t.scrollHeight <= t.clientHeight + 1, Math.round(k.bottom) <= innerHeight, t.textContent]; }""")
        ok(r[0] <= r[1] and r[2] and r[3] and r[4] == text, f"окно {w}×{h}, «{text[:24]}…»: текст целиком и над «Готово» ({r[0]} ≤ {r[1]}), кнопки в окне")
        pg.close()
    b.close()
app = (ROOT / "ui/app.py").read_text(encoding="utf-8")
ok("h += 36 if len(str(p.get(\"text\") or \"\")) <= 60 else 68" in app, "длинный текст — окно выше")
ok(not errs, f"без ошибок: {errs[:2]}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
