"""№544, №545 (пакет 04.11, ПК 0.82.2): «пополнил, DW-…» и «вот ничего не пришло» — снимок перевода ЮMoney 1000 ₽, а в
программе ни заявки, ни статуса. Перевод на кошелёк (не со страницы «Оплатить картой») приходит без номера DW-…: сервер его
записывает, но сам зачислить не может, а человек 10 минут смотрит на прежний баланс и не знает, что делать.
Теперь: прошло 10 минут после оплаты картой, а талеров нет — подсказка «пришлите снимок оплаты заявкой, обычно в течение
дня» и открытая форма заявки; пришло — «Пришло: +N тал.»; заявка на проверке видна в карточке «Мозга» со сроком (ПК и
телефон); в руководстве — что делать, если не пришло."""
import json, os, re, subprocess, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


pc = (ROOT / "ui" / "studio" / "dewiar.js").read_text(encoding="utf-8")
ph = (ROOT / "android" / "assets" / "www" / "app.js").read_text(encoding="utf-8")
for name, src, note in (("ПК", pc, "cc-ym-note"), ("телефон", ph, "cl-ym-res")):
    ok("function payLate()" in src and "return payLate();" in src, f"{name}: 10 минут без зачисления — подсказка, что делать")
    ok("пришлите снимок оплаты ниже («Отправить заявку»): проверим вручную, обычно в течение дня" in src, f"{name}: текст подсказки")
    ok("Пришло: +" in src, f"{name}: пришло — видно сразу")
    ok("заявка на пополнение на проверке — обычно зачисляем в течение дня" in src and "if (c.pending)" in src, f"{name}: заявка на проверке — в карточке «Мозга», со сроком")

# поведение: страница студии в браузере без ядра — подсказка через 30 опросов, без зачисления
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None
if sync_playwright and (ROOT / "ui" / "settings.html").exists():
    html = (ROOT / "ui" / "settings.html").read_text(encoding="utf-8")
    js = pc
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page()
        pg.set_content('<div id="cc-ym-note" class="ym-n"></div><div id="cc-man" style="display:none"><div id="cc-man-h" style="display:none"></div></div>'
                       '<div id="cc-pay"></div>')
        fn = re.search(r"function pendingLine\(\)[^\n]+\nfunction payLate\(\) \{[\s\S]*?\n\}", js).group(0)
        r = pg.evaluate("() => { const $ = (s) => document.querySelector(s); Element.prototype.scrollIntoView = function () {}; " + fn
                        + "; payLate(); return [$('#cc-ym-note').className, $('#cc-ym-note').textContent, $('#cc-man').style.display, $('#cc-man-h').style.display]; }")
        ok(r[0] == "ym-n bad" and "не пришли" in r[1] and r[2] == "" and r[3] == "", f"ПК: подсказка видна, форма заявки открыта: {r}")
        b.close()

g = json.loads((ROOT / "data" / "guide.json").read_text(encoding="utf-8"))
t = next(x for x in g if x["id"] == "taler")
ok(any("не пришли за 10–15 минут" in h for h in t["how"]), "руководство: «оплатил — не пришло» — что делать")
import guide  # noqa: E402
ok("Талер" in str(guide.hint("пополнил счёт, ничего не пришло")), "Лира на «пополнил — не пришло» находит этот раздел")
php = (ROOT / "server" / "dwrapp" / "cloud.php").read_text(encoding="utf-8")
ok("'без номера DW-…'" in php and "'pending' => (int)$pend['n']" in php, "сервер: перевод без номера записан для владельца; заявки на проверке — в балансе")
print("ALL OK" if not fails else f"FAILED: {len(fails)}")
sys.exit(1 if fails else 0)
