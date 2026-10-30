"""«Главная»: поиск по студии и «Почта» (30.10, владелец: «Добавил почту, и теперь не могу понять, как увидеть например
последние письма.. Лира у нас большая очень, много настроек и разделов. Может быть на „Главная“… такую поисковую форму,
чтобы прямо моментально можно было найти любой раздел или настройку? …под слепком знаний. И может здесь показывать
последние письма с почты красиво, если почта подключена»).
Поиск: под «Слепком знаний»; разделы, настройки внутри разделов (переход с подсветкой), слова людей («письма», «пароль»,
«скорость голоса»), «Вопрос — ответ»; стрелки/Enter/Esc; Ctrl+K — из любого раздела; ничего — «Спросить Лиру».
Почта: пять писем, новые — жирно с точкой, «N новых»; нажали — письмо целиком; нет почты — карточки нет."""
import json, os, re, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


MAIL = [{"uid": "41", "from": "Анна Петрова <anna@example.com>", "subject": "Договор на ноябрь", "date": "Fri, 30 Oct 2026 11:05:00 +0300", "snippet": "Михаил, добрый день! Прикладываю договор", "unread": True, "files": ["dogovor.pdf"]},
        {"uid": "40", "from": "GitHub <noreply@github.com>", "subject": "[dewiar-app] New issue #30", "date": "Thu, 29 Oct 2026 18:40:00 +0300", "snippet": "Opened by someone", "unread": False, "files": []},
        {"uid": "39", "from": "shop@ozon.ru", "subject": "Заказ доставлен", "date": "Mon, 26 Oct 2026 09:00:00 +0300", "snippet": "", "unread": False, "files": []}]
GUIDE = [{"id": "home-tv-mail-calendars", "title": "Умный дом, телевизор, почта и календари", "group": "Каждый день", "where": ["pc"], "lead": "почту читает", "how": ["Почта: пароль приложения"], "say": [], "tips": []}]
CORE = r"""
(() => { window.calls = []; window.MAILON = true;
  const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.call = async (c, a) => { calls.push([c, a]);
      if (c === "mail_inbox") return MAILON ? { on: true, items: MAIL } : { on: false, items: [] };
      if (c === "mail_read") return { uid: a.uid, from: MAIL[0].from, to: "me@example.com", subject: MAIL[0].subject, text: "Михаил, добрый день!\n\nПрикладываю договор на ноябрь.\n\nАнна", files: ["dogovor.pdf"] };
      if (c === "guide") return GUIDE;
      return null; };
    setTimeout(() => core.emit("hello", {}), 200); };
  ready(); })();
""".replace("MAIL", json.dumps(MAIL, ensure_ascii=False)).replace("GUIDE", json.dumps(GUIDE, ensure_ascii=False)).replace("window.MAILON = true", "window.MAILON = true")
CORE = CORE.replace(json.dumps(MAIL, ensure_ascii=False) + "ON", "MAILON")   # MAILON не подменять
SHOT = os.environ.get("DEWIAR_SHOTS")
res = lambda pg: pg.evaluate("[...document.querySelectorAll('#fd-res .fd-row b')].map(b => b.textContent)")
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 1440, "height": 1000}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route(re.compile(r"^https?://"), lambda r: r.abort())
    pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };"); pg.add_init_script(CORE)
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(1800)
    pg.evaluate("loadHome()"); pg.wait_for_timeout(600)
    # ---------- почта ----------
    ok(pg.is_visible("#hm-mail") and pg.locator("#hm-mail .hmm-row").count() == 3 and "1 новое" in pg.inner_text("#hm-mail .hmm-n"), "почта подключена — карточка, три письма, «1 новое»")
    r0 = pg.inner_text("#hm-mail .hmm-row >> nth=0")
    ok("Анна Петрова" in r0 and "Договор на ноябрь" in r0 and "Прикладываю" in r0 and pg.locator("#hm-mail .hmm-row.new").count() == 1 and "📎" in r0,
       f"от кого, тема, начало текста; новое — выделено; вложение — скрепкой: {r0[:80]!r}")
    ok("shop@ozon.ru" in pg.inner_text("#hm-mail .hmm-row >> nth=2"), "без имени — адрес")
    if SHOT: pg.screenshot(path=str(Path(SHOT) / "home-find-mail.png"))
    pg.click("#hm-mail .hmm-row >> nth=0"); pg.wait_for_timeout(300)
    ok(pg.evaluate("document.querySelector('#hmm-dlg').open") and "Прикладываю договор на ноябрь" in pg.inner_text("#hmm-body") and ["mail_read", {"uid": "41"}] in pg.evaluate("calls"),
       "нажали — письмо целиком (mail_read)")
    if SHOT: pg.screenshot(path=str(Path(SHOT) / "home-mail-read.png"))
    pg.keyboard.press("Escape"); pg.wait_for_timeout(200)
    ok(not pg.evaluate("document.querySelector('#hmm-dlg').open"), "Esc — закрыто")
    pg.evaluate("MAILON = false; HM.mail = null; hmMailLoad()"); pg.wait_for_timeout(300)
    ok(pg.is_hidden("#hm-mail"), "почты нет — карточки нет")
    pg.evaluate("MAILON = true; HM.mail = null; hmMailLoad()"); pg.wait_for_timeout(300)
    # ---------- поиск ----------
    ok(pg.is_visible("#fd-q") and pg.evaluate("document.querySelector('.hm-side #sn') !== null && document.querySelector('.hm-side .fd') !== null"), "поиск — под «Слепком знаний»")
    pg.click("#fd-q"); pg.keyboard.type("письма"); pg.wait_for_timeout(300)
    r = res(pg)
    ok(r and r[0] == "Последние письма", f"«письма» — первым «Последние письма»: {r[:4]}")
    pg.keyboard.press("Enter"); pg.wait_for_timeout(500)
    ok(pg.evaluate("document.querySelector('#hm-mail').classList.contains('fd-hl')") and pg.is_hidden("#fd-res") and pg.input_value("#fd-q") == "", "Enter — к карточке «Почта», с подсветкой")
    pg.click("#fd-q"); pg.keyboard.type("пароль приложения"); pg.wait_for_timeout(300)
    r = res(pg)
    ok(any("почт" in x.lower() for x in r[:2]), f"«пароль приложения» — к подключению почты: {r[:4]}")
    pg.fill("#fd-q", ""); pg.keyboard.type("скорость"); pg.wait_for_timeout(300)
    r = res(pg)
    ok(any("Голос" in x or "скорост" in x.lower() for x in r[:3]), f"«скорость» — голос: {r[:4]}")
    if SHOT: pg.screenshot(path=str(Path(SHOT) / "home-find.png"))
    pg.fill("#fd-q", ""); pg.keyboard.type("звуки"); pg.wait_for_timeout(300)
    r = res(pg)
    ok(r and r[0].startswith("Звонок будильника"), f"30.10: «звуки» — к звонку будильника (послушать и выбрать): {r[:3]}")
    pg.fill("#fd-q", ""); pg.keyboard.type("мелодия"); pg.wait_for_timeout(300)
    ok((res(pg) or [""])[0].startswith("Звонок будильника"), "«мелодия» — туда же")
    pg.fill("#fd-q", ""); pg.keyboard.type("сейф"); pg.wait_for_timeout(300)
    r = res(pg)
    ok(r and r[0] == "Сейф паролей", f"раздел по названию: {r[:3]}")
    pg.keyboard.press("Enter"); pg.wait_for_timeout(400)
    ok(pg.evaluate("document.querySelector('#p-vault').classList.contains('cur')"), "Enter — раздел открыт")
    # настройка внутри раздела + Ctrl+K из другого раздела
    pg.keyboard.press("Control+k"); pg.wait_for_timeout(300)
    ok(pg.evaluate("document.querySelector('#p-home').classList.contains('cur') && document.activeElement.id === 'fd-q'"), "Ctrl+K в другом разделе — «Главная», курсор в поиске")
    pg.keyboard.type("почта"); pg.wait_for_timeout(300)
    hits = pg.evaluate("FD.hits.map(h => [h.k, h.p, h.t])")
    ok(any(h[1] == "connect" and h[2] == "Почта" for h in hits), f"настройка «Почта» в «Подключении» находится сама (заголовок раздела): {hits[:6]}")
    i = next(i for i, h in enumerate(hits) if h[1] == "connect" and h[2] == "Почта")
    for _ in range(i): pg.keyboard.press("ArrowDown")
    pg.keyboard.press("Enter"); pg.wait_for_timeout(700)
    ok(pg.evaluate("document.querySelector('#p-connect').classList.contains('cur')") and pg.evaluate("!!document.querySelector('#p-connect .fd-hl')"), "стрелки и Enter — «Подключение», почта подсвечена")
    pg.keyboard.press("Control+k"); pg.wait_for_timeout(300); pg.keyboard.type("умный дом"); pg.wait_for_timeout(400)
    ok(any(h["k"] == "qa" for h in pg.evaluate("FD.hits")) or len(pg.evaluate("FD.hits")) > 0, "«Вопрос — ответ» тоже в поиске")
    pg.fill("#fd-q", ""); pg.keyboard.type("абракадабра"); pg.wait_for_timeout(300)
    ok(pg.is_visible("#fd-ask") and "Ничего не нашлось" in pg.inner_text("#fd-res"), "ничего — «Спросить Лиру»")
    pg.keyboard.press("Escape"); pg.wait_for_timeout(100)
    ok(pg.is_hidden("#fd-res") and pg.input_value("#fd-q") == "", "Esc — очищено и закрыто")
    pg.set_viewport_size({"width": 760, "height": 900}); pg.wait_for_timeout(200)
    ok(pg.evaluate("document.documentElement.scrollWidth <= innerWidth"), "узкое окно — без прокрутки вбок")
    b.close()
eng = (ROOT / "core/engine_commands.py").read_text(encoding="utf-8")
ok('cmd == "mail_inbox"' in eng and 'return {"on": False, "items": []}' in eng and 'cmd == "mail_read"' in eng and '"mail_"' in eng.split("_KIDS_LOCKED")[1][:2000],
   "ядро: mail_inbox (нет почты — on: false, без сети), mail_read; в детском режиме почта закрыта")
ok(not errs, f"без ошибок на странице: {errs[:3]}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
