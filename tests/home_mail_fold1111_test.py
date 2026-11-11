"""Владелец 11.11 (Ubuntu): «когда подключена почта, она занимает много места и всё время мозолит глаз — сворачивать
красиво, аккуратно, с возможностью развернуть, или убирать неинтересные письма из отображаемых». Карточка «Почта» на
«Главной» сворачивается шапкой в одну строку (сколько новых и последнее письмо), выбор помнится; у письма — «Убрать с
главной» (в ящике остаётся), тут же «Не показывать письма от …» и «Вернуть»; «Показать скрытые» — всё назад."""
import json, os, re, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
SHOT = os.environ.get("SHOT_DIR")
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


ITEMS = [{"uid": str(i), "box": "me@example.org", "from": f"{n} <{a}>", "subject": s, "snippet": "Текст письма", "date": f"2026-11-11T1{i}:00:00",
          "unread": i < 3} for i, (n, a, s) in enumerate([("Сервис", "news@shop.example", "Скидки недели"), ("Анна", "anna@example.org", "Договор"),
                                                         ("Сервис", "news@shop.example", "Ещё скидки"), ("Пётр", "petr@example.org", "Встреча"),
                                                         ("Банк", "bank@example.org", "Выписка"), ("Олег", "oleg@example.org", "Фото"),
                                                         ("Мария", "maria@example.org", "Привет")])]
INBOX = {"on": True, "items": ITEMS}
FAKE = """(() => { window.calls = [];
  const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.call = async (c, a) => { calls.push([c, a]);
      if (c === "mail_inbox") return JSON.parse(INBOX);
      if (c === "month_get") throw new Error("нет");
      return {}; };
    setTimeout(() => core.emit("hello", {}), 200); };
  ready(); })();""".replace("INBOX", json.dumps(json.dumps(INBOX, ensure_ascii=False)))
errs = []
with sync_playwright() as p:
    b = p.chromium.launch()
    st = b.new_page(viewport={"width": 1300, "height": 900}); st.on("pageerror", lambda e: errs.append(str(e)))
    st.route(re.compile(r"^https?://"), lambda r: r.abort()); st.add_init_script(FAKE)
    st.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); st.wait_for_timeout(1200)
    st.evaluate("() => { localStorage.clear(); const w = document.querySelector('#wlc'); if (w) w.remove(); document.querySelector('nav button[data-p=\"home\"]').click(); HM.mail = null; loadHome(); }")
    st.wait_for_timeout(1200)
    rows = lambda: st.evaluate("[...document.querySelectorAll('#hm-mail .hmm-l1 b')].map(b => b.textContent)")   # noqa: E731
    ok(len(rows()) == 5, f"видно пять писем: {rows()}")
    ok(any(c[0] == "mail_inbox" and (c[1] or {}).get("limit", 0) > 5 for c in st.evaluate("calls")), "писем берётся с запасом — убранные не в счёт")
    if SHOT:
        st.locator("#hm-mail").screenshot(path=f"{SHOT}/mail_open.png")
    st.click("#hmm-fold"); st.wait_for_timeout(300)
    ok(st.evaluate("document.querySelector('#hm-mail').classList.contains('fold') && document.querySelector('#hmm-wrap').hidden"), "свернули — писем не видно")
    ok(st.get_attribute("#hmm-fold", "aria-expanded") == "false", "aria-expanded = false")
    h = st.evaluate("document.querySelector('#hm-mail').getBoundingClientRect().height")
    ok(h < 80, f"свёрнутая карточка — одна строка ({h:.0f} px)")
    ok("Сервис" in st.inner_text("#hm-mail") and "новых" in st.inner_text("#hm-mail"), "в строке — сколько новых и последнее письмо")
    if SHOT:
        st.locator("#hm-mail").screenshot(path=f"{SHOT}/mail_fold.png")
    st.evaluate("() => { HM.mail = null; loadHome(); }"); st.wait_for_timeout(900)
    ok(st.evaluate("document.querySelector('#hm-mail').classList.contains('fold')"), "свёрнутость помнится")
    st.click("#hmm-fold"); st.wait_for_timeout(300)
    ok(not st.evaluate("document.querySelector('#hmm-wrap').hidden"), "развернули — письма снова видно")
    # убрать письмо с главной
    st.hover("#hm-mail li >> nth=0"); st.click("#hm-mail .hmm-x >> nth=0"); st.wait_for_timeout(300)
    ok(rows()[0] != "Сервис" or len(rows()) == 5, f"письмо ушло с главной, на его место — следующее: {rows()}")
    ok(st.locator("#hmm-undo, .hmm-undo").count() == 1 and "Не показывать письма от Сервис" in st.inner_text("#hm-mail"), "предложено не показывать отправителя")
    if SHOT:
        st.locator("#hm-mail").screenshot(path=f"{SHOT}/mail_undo.png")
    st.click("#hmm-mute"); st.wait_for_timeout(300)
    ok("Сервис" not in " ".join(rows()) and len(rows()) == 5, f"отправитель заглушён — его писем нет: {rows()}")
    ok(st.locator("#hmm-all").count() == 1, "есть «Показать скрытые»")
    st.click("#hmm-all"); st.wait_for_timeout(300)
    ok(rows()[0] == "Сервис", "«Показать скрытые» — всё вернулось")
    st.hover("#hm-mail li >> nth=1"); st.click("#hm-mail .hmm-x >> nth=1"); st.wait_for_timeout(200); st.click("#hmm-back"); st.wait_for_timeout(200)
    ok(rows()[1] == "Анна", "«Вернуть» — письмо снова на месте")
    ok(not errs, f"без ошибок JavaScript: {errs[:2]}")
    b.close()
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
