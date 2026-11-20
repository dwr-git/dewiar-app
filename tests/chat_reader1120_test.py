"""«Читать» в «Чате» (владелец 20.11): большой ответ — «здоровый вертикальный блок, читать сложно». Кнопка «Читать» у ответов
длиннее 600 знаков открывает ответ по центру крупно; большие ответы беседы листаются как страницы (‹ ›, стрелки), размер
текста A−/A+ запоминается; Esc закрывает. Сплошной текст оживает: короткая строка — подзаголовок, «X: …» — начало пункта
жирным. Заодно: переключатель «Текстовый режим» виден на светлой теме, лента сверху мягко уходит под шапку."""
import os, re, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)

bad = 0
def ok(c, m):
    global bad
    bad += 0 if c else 1
    print(("✅ " if c else "❌ ") + m)

rj = (ROOT / "ui/studio/reader.js").read_text(encoding="utf-8")
cj = (ROOT / "ui/studio/chat.js").read_text(encoding="utf-8")
css = (ROOT / "ui/studio/studio.css").read_text(encoding="utf-8")
st = (ROOT / "ui/settings.html").read_text(encoding="utf-8")
ok("CHR_MIN = 600" in rj and "(x.text || \"\").length >= 600" in cj, "кнопка — у ответов от 600 знаков (одна граница)")
ok(st.index('studio/chat.js') < st.index('studio/reader.js'), "reader.js подключён после chat.js")
ok(re.search(r"html\.st-light \.ch-tm i\b", css) is not None, "переключатель «Текстовый режим» на светлой теме — контрастный")
ok(re.search(r"#ch-msgs\s*\{[^}]*mask-image", css) is not None, "лента сверху уходит под шапку мягко")
ok("const CHR " in rj and not re.search(r"^const RD\b", rj, re.M), "свои имена (CHR, chr-), не как у «Радара» и «Радио»")

LONG = ("Как это работает. Сервер ловит каждый пакет звонка через зеркальный порт, коллектор собирает их в звонки.\n\n"
        "Слабости и противоречия.\n\n"
        "Главная — пик 1500 звонков даёт 225 тыс. пакетов в секунду, а коллектор проверен только до 150 тыс. " * 2 + "\n\n"
        "Kafka на одном сервере: отказ любого диска убивает голосовой поток, и это нигде не сказано прямо.\n\n"
        "Итого: сервер держит 1000 звонков с запасом, 1500 — на пределе. " * 3)
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("⚠️ playwright нет — только проверки исходников"); sys.exit(1 if bad else 0)

with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1300, "height": 860})
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route(re.compile(r"^https?://"), lambda r: r.abort())
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(1300)
    ok(pg.evaluate("typeof chrOpen === 'function' && typeof chrLively === 'function'"), "окно чтения загрузилось")
    lv = pg.evaluate("t => chrLively(t)", LONG)
    ok("### Слабости и противоречия" in lv, "короткая строка — подзаголовок")
    ok("**Kafka на одном сервере:**" in lv and "**Итого:**" in lv, "«X: …» — начало пункта жирным")
    ok(pg.evaluate("chrLively('## Уже\\n\\nтекст') === '## Уже\\n\\nтекст'"), "разметку модели не трогаем")
    pg.evaluate("""a => { CH.items = [
        {id: 1, role: 'user', text: 'Проанализируй спецификацию', ts: 1}, {id: 2, role: 'assistant', text: a, ts: 2},
        {id: 3, role: 'user', text: 'Коротко?', ts: 3}, {id: 4, role: 'assistant', text: 'Да, коротко.', ts: 4},
        {id: 5, role: 'user', text: 'А второй вариант?', ts: 5}, {id: 6, role: 'assistant', text: a + ' Ещё.', ts: 6}];
      document.body.insertAdjacentHTML('beforeend', '<div id="t-feed"></div>');
      document.getElementById('t-feed').innerHTML = CH.items.map(x => chatBubble1(x, '')).join(''); }""", LONG)
    ok(pg.locator("#t-feed .ch-read").count() == 2, "«Читать» — только у двух больших ответов")
    pg.locator('#t-feed .ch-read[data-read="2"]').click(); pg.wait_for_timeout(250)
    ov = pg.locator("#chr-ov")
    ok(ov.evaluate("e => e.classList.contains('on')"), "открылось по центру")
    ok(pg.locator(".chr-n").inner_text().strip() == "1 из 2" and "Проанализируй" in pg.locator(".chr-q").inner_text(),
       "«1 из 2», сверху — вопрос")
    ok(pg.locator(".chr-body h3").count() >= 1 and pg.locator(".chr-body b, .chr-body strong").count() >= 2, "подзаголовки и выделения видны")
    pg.keyboard.press("ArrowRight"); pg.wait_for_timeout(100)
    ok(pg.locator(".chr-n").inner_text().strip() == "2 из 2" and "второй" in pg.locator(".chr-q").inner_text(), "→ — следующий ответ")
    ok(pg.locator(".chr-nav.next").evaluate("e => e.hidden") and not pg.locator(".chr-nav.prev").evaluate("e => e.hidden"),
       "на последнем — только «назад»")
    f0 = pg.locator(".chr-body").evaluate("e => parseFloat(getComputedStyle(e).fontSize)")
    pg.locator('.chr-size button[data-d="1"]').click(); pg.wait_for_timeout(100)
    f1 = pg.locator(".chr-body").evaluate("e => parseFloat(getComputedStyle(e).fontSize)")
    ok(f1 > f0, f"A+ — крупнее ({f0:g} → {f1:g})")
    ok(pg.evaluate("localStorage.getItem('dw.rd.size')") is not None, "размер запоминается")
    pg.keyboard.press("Escape"); pg.wait_for_timeout(100)
    ok(not ov.evaluate("e => e.classList.contains('on')"), "Esc — закрыть")
    ok(not errs, "без ошибок на странице" + (f": {errs[:2]}" if errs else ""))
    b.close()

print("ИТОГ:", "всё в порядке" if not bad else f"ошибок {bad}")
sys.exit(1 if bad else 0)
