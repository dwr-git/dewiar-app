"""Студия, 05.11 (владелец): «жучок и лампочка у вопросика визуально выше» и «блок с вариантами оплаты блеклый, серый, со
светлым текстом, а что поле для снимка нажимается — непонятно». Теперь:
- значки у заголовка раздела — на одной линии с «?»;
- пополнение — шагами «1 Оплатите», «2 Пришлите снимок»; номер DW — крупно с «Скопировать»; ссылка отдельной строкой —
  способ оплаты строкой (название из строки над ней, сайт, «Открыть», пояснение под ним); текст тёмный, не серый;
- поле снимка — значок, две строки, пунктир, открывается и с клавиатуры (Enter)."""
import os, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


TXT = ("Ваш номер для оплаты: DW-10 — укажите его в комментарии к переводу, чтобы мы нашли вас и зачислили.\n\n"
       "Пополнить можно любой ссылкой ниже (1 талер = 1$).\nПосле перевода прикрепите скриншот.\n\n"
       "Пополнить можно через донат:\nhttps://donate.example/donate_dewiar\n\nМожно через ЮMoney:\nhttps://yoomoney.example/to/41001/0\n\n"
       "Для пополнения из Беларуси:\nhttps://checkout.example.by/confirm/20360\nТелефон +375 00 000-00-00\n\n"
       "Или напишите в поддержку https://t.example/dewiar — поможем.")
errs = []
with sync_playwright() as pw:
    br = pw.chromium.launch(); pg = br.new_page(viewport={"width": 1400, "height": 950}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: (t, k) => k === 'open_url' ? ((u) => { window._opened = u; return Promise.resolve(true); }) : () => Promise.resolve(true) }) };")
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(1000)
    pg.evaluate("() => $('nav button[data-p=\"brain\"]').click()"); pg.wait_for_timeout(300)
    mids = pg.evaluate("() => [...document.querySelectorAll('#p-brain h1 .hbtn')].map(b => { const r = b.getBoundingClientRect(); return (r.top + r.bottom) / 2; })")
    ok(len(mids) >= 3 and max(mids) - min(mids) < 1, f"«?», жучок и лампочка — на одной линии: {mids}")
    pg.evaluate("""(t) => { $('#cloud-card').style.display = ''; $('#cc-pay').style.display = ''; ymFill(null); cxFill(null);
        payArrange([{id: 'manual', title: 'Снимок оплаты администратору'}]); topupText(t); }""", TXT)
    pg.wait_for_timeout(200)
    r = pg.evaluate("""() => ({ code: $('#cc-topup .tp-code b').textContent, copy: $('#cc-topup .tp-code button').dataset.copy,
        opts: [...document.querySelectorAll('#cc-topup .tp-opt')].map(o => [o.querySelector('b').textContent, o.querySelector('small').textContent, o.querySelector('button').dataset.ext]),
        note: ($('#cc-topup .tp-opt:last-child .tp-on') || {}).textContent || '', inline: !!document.querySelector('#cc-topup .tp-p a[data-ext="https://t.example/dewiar"]'),
        steps: [...document.querySelectorAll('#cc-man .tp-step b')].map(b => b.textContent), all: $('#cc-topup').textContent })""")
    ok(r["code"] == "DW-10" and r["copy"] == "DW-10", f"номер DW — крупно и с «Скопировать»: {r['code']}")
    ok([o[0] for o in r["opts"]] == ["Через донат", "Через ЮMoney", "Для пополнения из Беларуси"]
       and [o[1] for o in r["opts"]] == ["donate.example", "yoomoney.example", "checkout.example.by"], f"способы оплаты — строками с названием и сайтом: {r['opts']}")
    ok("Телефон +375" in r["note"], "пояснение под ссылкой — в строке способа")
    ok(r["inline"] and "поможем" in r["all"] and "1 талер = 1$" in r["all"], "ссылка внутри предложения и прочий текст — на месте, ничего не потеряно")
    ok(r["steps"] == ["Оплатите удобным способом", "Пришлите снимок оплаты"], f"шаги: {r['steps']}")
    pg.click("#cc-topup .tp-opt:nth-child(2) button"); ok(pg.evaluate("window._opened") == "https://yoomoney.example/to/41001/0", "«Открыть» — ссылка в браузере")
    ink = pg.evaluate("() => [getComputedStyle($('#cc-topup .tp-p')).color, getComputedStyle(document.body).color]")
    ok(ink[0] == ink[1], f"текст — цветом основного текста, а не бледным: {ink}")
    sh = pg.evaluate("() => ({ role: $('#cp-shot').getAttribute('role'), t: $('#cp-shot-t').textContent, s: $('#cp-shot-s').textContent, ic: !!$('#cp-shot .cp-si svg'), b: getComputedStyle($('#cp-shot')).borderTopStyle })")
    ok(sh["role"] == "button" and sh["ic"] and sh["b"] == "dashed" and "Приложите снимок" in sh["t"] and "перетащите" in sh["s"], f"поле снимка — видно, что нажимается: {sh}")
    pg.evaluate("() => { window._picked = 0; $('#cp-file').click = () => { window._picked++; }; }")
    pg.focus("#cp-shot"); pg.keyboard.press("Enter")
    ok(pg.evaluate("window._picked") == 1, "Enter на поле снимка — выбор файла (с клавиатуры тоже)")
    ok(not errs, f"без ошибок JavaScript: {errs[:2]}")
    br.close()
print("ИТОГ:", "всё прошло" if not fails else f"{len(fails)} ошибок")
sys.exit(1 if fails else 0)
