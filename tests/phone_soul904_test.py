"""№904 (19.11, телефон 0.9.69): «открываю Душу — всё приложение замирает, и после перезапуска то же». Дневник за месяцы
сразу целиком размечался в страницу (сотни записей). Теперь — последние 30 дней, «Показать ещё» — следующие, а текст дня
размечается, только когда его открыли."""
import os
import subprocess
import sys
import tempfile
import shutil
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


tmp = Path(tempfile.mkdtemp()); www = tmp / "www"
subprocess.run(["bash", str(ROOT / "android/tools/www_assemble.sh"), str(www)], check=True, capture_output=True)
errs = []
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 400, "height": 820}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(1000)
    ms = pg.evaluate("""() => { const m = mind(); const txt = '# День\\n\\n## 🌙 Ночь\\n' + ('Сегодня **важный** день — разговор о работе.\\n- пункт\\n'.repeat(400));
      for (let i = 0; i < 200; i++) { const d = new Date(Date.now() - i * 864e5).toISOString().slice(0, 10); m.diary[d] = { text: txt, title: 'Записи', mood: 'спокойно' }; }
      m.diary['2020-01-01'] = null; saveMind(m); S.sync.on = true; soulTab = 'diary';
      const t0 = performance.now(); renderSoul(); openSheet('#sh-soul'); return performance.now() - t0; }""")
    n = pg.evaluate("document.querySelectorAll('#soul-body details.dday').length")
    ok(n == 30, f"сразу — последние 30 дней из 201: {n}")
    ok(pg.evaluate("[...document.querySelectorAll('#soul-body .dtext')].every(x => !x.innerHTML)"), "текст дней не размечен, пока их не открыли")
    ok(ms < 1500, f"открывается быстро: {ms:.0f} мс")
    pg.evaluate("document.querySelector('#soul-body details.dday').open = true"); pg.wait_for_timeout(200)
    ok("<h4>" in pg.evaluate("document.querySelector('#soul-body .dtext').innerHTML"), "открыли день — текст на месте, с разметкой")
    pg.click("#so-more"); pg.wait_for_timeout(200)
    ok(pg.evaluate("document.querySelectorAll('#soul-body details.dday').length") == 60, "«Показать ещё» — следующие 30")
    b.close()
ok(not errs, f"без ошибок на странице (и с пустой записью дня): {errs[:3]}")
shutil.rmtree(tmp, ignore_errors=True)
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
