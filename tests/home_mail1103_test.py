"""№467 (01.11, ПК 0.71): «На „Главной“ при нажатии на „Почта“ открывается страница настроек, а не список писем.
Календарь при этом открывает „Календарь“». Строка «Почта: N новых» в «Утре с Лирой» (studio/morning.js) вела в
«Подключение». Теперь: почта подключена — к письмам на «Главной» (карточка «Почта», свежая проверка, подсветка);
не подключена — к её настройке («Подключение» → почта)."""
import datetime as dt, json, os, re, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


MORNING = {"city": "", "weather": None, "today": {"meet": [], "todo": []}, "mail_on": True,
           "mail": {"unread": 3, "more": False, "people": [{"from": "Анна", "subject": "Договор"}]}, "settings": {}, "daily": None}
INBOX = {"on": True, "items": [{"uid": "1", "from": "Анна <anna@example.org>", "subject": "Договор", "snippet": "Посмотрите", "date": "2026-11-03T08:10:00", "unread": True}]}
FAKE = """(() => { window.calls = []; window.MAIL_ON = true;
  const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.call = async (c, a) => { calls.push([c, a]);
      if (c === "morning_get") return Object.assign(JSON.parse(MORNING), { mail_on: MAIL_ON });
      if (c === "month_get") throw new Error("нет");            // «Мой месяц» — не про это
      if (c === "mail_inbox") return MAIL_ON ? JSON.parse(INBOX) : { on: false, items: [] };
      return {}; };
    setTimeout(() => core.emit("hello", {}), 200); };
  ready(); })();""".replace("MORNING", json.dumps(json.dumps(MORNING, ensure_ascii=False))).replace("INBOX", json.dumps(json.dumps(INBOX, ensure_ascii=False)))
errs = []
with sync_playwright() as p:
    b = p.chromium.launch()
    st = b.new_page(viewport={"width": 1300, "height": 900}); st.on("pageerror", lambda e: errs.append(str(e) + " @ " + (e.stack or "")[:300]))
    st.clock.install(time=dt.datetime(2026, 11, 3, 9, 0))         # «Утро» видно с 4 до 13
    st.route(re.compile(r"^https?://"), lambda r: r.abort()); st.add_init_script(FAKE)
    st.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); st.wait_for_timeout(1200)
    st.evaluate("() => { const w = document.querySelector('#wlc'); if (w) w.remove(); document.querySelector('nav button[data-p=\"home\"]').click(); loadHome(); }")
    st.wait_for_timeout(1200)
    row = st.locator("#hm-morning [data-mgo='mail']")
    ok(row.count() == 1 and "Почта: 3" in row.inner_text(), "в «Утре» — строка «Почта: 3 новых»")
    ok(st.evaluate("!document.querySelector('#hm-mail').hidden") and "Договор" in st.inner_text("#hm-mail"), "на «Главной» — карточка с письмами")
    n0 = len([c for c in st.evaluate("calls") if c[0] == "mail_inbox"])
    row.click(); st.wait_for_timeout(500)
    ok(st.evaluate("document.querySelector('#p-home').classList.contains('cur')"), "нажали «Почта» — остались на «Главной», не в настройках")
    ok(st.evaluate("document.querySelector('#hm-mail').classList.contains('hl')"), "карточка писем подсвечена")
    ok(len([c for c in st.evaluate("calls") if c[0] == "mail_inbox"]) > n0, "почта проверена заново")
    ok(st.evaluate("(() => { const r = document.querySelector('#hm-mail').getBoundingClientRect(); return r.top < innerHeight && r.bottom > 0; })()"),
       "карточка писем — на экране")
    cal = st.locator("#hm-morning [data-mgo='calendar']")
    if cal.count():
        cal.first.click(); st.wait_for_timeout(300)
        ok(st.evaluate("document.querySelector('#p-calendar').classList.contains('cur')"), "«День свободен» — как и раньше, в «Календарь»")
    # почта не подключена — к настройке почты
    st.evaluate("() => { MAIL_ON = false; document.querySelector('nav button[data-p=\"home\"]').click(); HM.mail = null; loadHome(); }")
    st.wait_for_timeout(1000)
    ok(st.evaluate("document.querySelector('#hm-mail').hidden"), "почты нет — карточки писем нет")
    st.evaluate("mnGo('mail')"); st.wait_for_timeout(500)
    ok(st.evaluate("document.querySelector('#p-connect').classList.contains('cur')"), "почта не подключена — «Подключение», где её добавить")
    ok(not errs, f"без ошибок JavaScript: {errs[:2]}")
    b.close()
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
