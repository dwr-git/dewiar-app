"""№435 (31.10, телефон 0.9.16): «Дважды пишет и проговаривает текст» — на снимке: «Записала: расход 3 795 руб, оплата
через Alcor (заказ 125672). Записала: расход 3 795 руб, Alcor, заказ 125672.» Модель сказала итог до действия
(money_add) и повторила его после. Теперь начало следующего круга придерживается: повтор уже сказанного не
показывается и не озвучивается; новое — как обычно."""
import os, subprocess, sys, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


w = Path(tempfile.mkdtemp()) / "www"
subprocess.run(["bash", str(ROOT / "android/tools/www_assemble.sh"), str(w)], check=True, capture_output=True)
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 393, "height": 852}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route("https://**", lambda r: r.abort())
    pg.goto((w / "index.html").as_uri()); pg.wait_for_timeout(900)
    run = """(parts) => { window.__said = []; const s0 = say; say = (t) => { __said.push(t); };
      const k = sentenceSink();
      for (const [kind, t] of parts) { if (kind === 'round') k.round(); else k.push(t); }
      k.flush(); say = s0; return [k.text(), __said.join('|')]; }"""
    A = "Записала: расход 3 795 руб, оплата через Alcor (заказ 125672). "
    t, said = pg.evaluate(run, [["p", A[:20]], ["p", A[20:]], ["round", ""], ["p", "Записала: рас"], ["p", "ход 3 795 руб, Alcor, "], ["p", "заказ 125672."]])
    ok(t.strip() == A.strip() and said.count("Записала") == 1, f"повтор итога после действия — не показан и не сказан: {t!r} / {said!r}")
    t, said = pg.evaluate(run, [["p", A], ["round", ""], ["p", "Ещё поставила напоминание "], ["p", "оплатить завтра в 10:00."]])
    ok("напоминание" in t and said.count("Записала") == 1 and "напоминание" in said, f"новое после действия — как обычно: {t!r}")
    t, said = pg.evaluate(run, [["p", A], ["round", ""], ["p", "Готово."]])
    ok(t.endswith("Готово.") and "Готово" in said, f"короткая новая фраза в конце — не теряется: {t!r}")
    t, said = pg.evaluate(run, [["round", ""], ["p", "Сейчас посмотрю погоду."]])
    ok(t == "Сейчас посмотрю погоду." and said, "в первом круге ничего не придерживается")
    t, said = pg.evaluate(run, [["p", "Секунду. "], ["round", ""], ["p", "Секу"], ["round", ""], ["p", "Погода: +6, пасмурно."]])
    ok("Погода" in t, f"недосказанный короткий круг не теряет следующий: {t!r}")
    ok(not errs, f"без ошибок JavaScript: {errs[:2]}")
    b.close()
# и на компьютере — тот же сторож в ядре (engine_answer.repeat_head)
sys.path.insert(0, str(ROOT / "core"))
import engine_answer as EA  # noqa: E402
ok(EA.repeat_head(A, "Записала: рас") is None and EA.repeat_head(A, "Записала: расход 3 795 руб, Alcor") is True
   and EA.repeat_head(A, "Ещё поставила напоминание на завтра") is False and EA.repeat_head(A, "Готово.", fin=True) is False,
   "компьютер: начало шага — повтор сказанного / новое / рано судить")
src = (ROOT / "core/engine_answer.py").read_text(encoding="utf-8")
ok("probing = False" in src and "repeat_head(turn.full, probe)" in src and "repeat_head(turn.full, probe, fin=True)" in src,
   "компьютер: начало следующего шага придерживается, повтор не говорится")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
