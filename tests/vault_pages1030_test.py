"""Сейф паролей — страницы списка (30.10, владелец: «Может сделать в Сейф паролей пагинацию страниц? Уже много и не очень
симпатично в этом плане, приходится скроллить»).
На странице — сколько входит в окно без прокрутки (6–12; в окне 1030 — 10, в 950 — 9); внизу — «11–20 из 27» и кнопки 1 2 3 со стрелками; поиск начинает с первой страницы и листается
так же; PageUp/PageDown в поиске; новая запись открывает свою страницу и подсвечивается; правка не сбрасывает страницу;
Enter копирует первую запись открытой страницы; до 10 записей — без кнопок, как было."""
import os, re, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


NAMES = ["Авито", "Альфа-Банк", "Банк Тинькофф", "Вайфай дома", "Вайфай дача", "ВКонтакте", "Госуслуги", "Домофон", "Дропбокс",
         "Заметки iCloud", "Каршеринг", "Кинопоиск", "Леруа", "Маркет", "Ozon", "Почта Яндекса", "Почта Gmail", "Роутер",
         "Сбербанк", "Сервер dev", "Сервер prod", "Телеграм", "Умный дом", "Хостинг", "Цифровой ключ", "Школа", "Яндекс ID"]
FAKE = "window.pywebview = { api: new Proxy({}, { get: (_, k) => k === 'clip_secret' ? ((t, s) => { (window.clips = window.clips || []).push([t, s]); return Promise.resolve(true); }) : (...a) => Promise.resolve(true) }) };"
CORE = r"""
(() => { window.calls = []; window.V = NAMES.map((n, i) => ({ id: "i" + i, name: n, login: i % 3 ? "user" + i : "", url: i % 4 ? "" : "site" + i + ".ru", note: "", value: "Секрет-" + i }));
  const pub = () => V.map(x => { const o = Object.assign({}, x, { length: x.value.length }); delete o.value; return o; }).sort((a, b) => a.name.toLowerCase().localeCompare(b.name.toLowerCase()));
  const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.call = async (c, a) => { calls.push([c, a]);
      if (c === "vault_list") return { items: pub() };
      if (c === "vault_reveal") return { value: (V.find(x => x.id === a.id) || {}).value || "" };
      if (c === "vault_put") { let x = a.id && V.find(i => i.id === a.id);
        if (x) Object.assign(x, a, a.value ? {} : { value: x.value }); else { x = Object.assign({ id: "n" + V.length }, a); V.push(x); }
        const o = Object.assign({}, x); delete o.value; return { item: o, items: pub() }; }
      return {}; };
    setTimeout(() => core.emit("hello", {}), 200); };
  ready(); })();
""".replace("NAMES", repr(NAMES).replace("'", '"'))
SHOT = os.environ.get("DEWIAR_SHOTS")
names = lambda pg: pg.evaluate("[...document.querySelectorAll('#vl-list .vl-item .vl-name')].map(e => e.textContent)")
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    ctx = b.new_context(viewport={"width": 1400, "height": 1030}, permissions=["clipboard-read", "clipboard-write"])
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route(re.compile(r"^https?://"), lambda r: r.abort())
    pg.add_init_script(FAKE); pg.add_init_script(CORE)
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(1500)
    pg.evaluate("document.querySelector('nav button[data-p=\"vault\"]').click()"); pg.wait_for_timeout(500)
    n1 = names(pg)
    ok(len(n1) == 10 and n1[0] == "Ozon" and n1[1] == "Авито", f"27 записей — на странице 10, с начала алфавита: {n1[:2]}")
    ok(pg.inner_text(".vl-range").startswith("1–10 из 27") and pg.locator(".vl-pn[data-pg]:not(.vl-step)").count() == 3
       and pg.is_disabled(".vl-step[data-pg='prev']"), f"внизу — «1–10 из 27», кнопки 1 2 3, «назад» выключена: {pg.inner_text('.vl-range')!r}")
    if SHOT: pg.screenshot(path=str(Path(SHOT) / "vault-pages.png"), full_page=True)
    pg.click(".vl-pn[data-pg='2']"); pg.wait_for_timeout(200)
    n3 = names(pg)
    ok(len(n3) == 7 and pg.inner_text(".vl-range").startswith("21–27") and pg.is_disabled(".vl-step[data-pg='next']")
       and pg.get_attribute(".vl-pn.cur", "aria-current") == "page", f"третья страница — 7 последних, «вперёд» выключена: {n3[:2]}")
    pg.click(".vl-step[data-pg='prev']"); pg.wait_for_timeout(200)
    ok(pg.inner_text(".vl-range").startswith("11–20"), "стрелка «назад» — вторая страница")
    # правка не сбрасывает страницу
    second = names(pg)[3]
    pg.click(f".vl-item:has(.vl-name:text-is('{second}')) [data-v='edit']"); pg.wait_for_timeout(200)
    pg.fill("#vl-note", "новая заметка"); pg.click("#vl-save"); pg.wait_for_timeout(300)
    ok(pg.inner_text(".vl-range").startswith("11–20") and second in names(pg), "изменили запись — остались на той же странице")
    # поиск
    pg.fill("#vl-q", "а"); pg.wait_for_timeout(200)
    ok(pg.inner_text(".vl-range").startswith("1–10") and "найдено в 27" in pg.inner_text(".vl-range"), f"поиск — с первой страницы: {pg.inner_text('.vl-range')!r}")
    pg.press("#vl-q", "PageDown"); pg.wait_for_timeout(200)
    ok(pg.inner_text(".vl-range").startswith("11–"), "PageDown в поиске — следующая страница")
    first = names(pg)[0]
    pg.press("#vl-q", "Enter"); pg.wait_for_timeout(300)
    idx = NAMES.index(first)
    ok(pg.evaluate("window.clips && window.clips.length && window.clips.pop()[0]") == f"Секрет-{idx}", f"Enter — копирует первую запись открытой страницы ({first})")
    pg.press("#vl-q", "PageUp"); pg.wait_for_timeout(150)
    ok(pg.inner_text(".vl-range").startswith("1–10"), "PageUp — обратно")
    pg.fill("#vl-q", "сервер"); pg.wait_for_timeout(200)
    ok(pg.locator(".vl-pager").count() == 0 and "Найдено: 2 из 27" in pg.inner_text(".vl-count"), "нашлось мало — без кнопок страниц, как было")
    pg.fill("#vl-q", ""); pg.dispatch_event("#vl-q", "input"); pg.wait_for_timeout(150)
    # новая запись в конце алфавита — открывается её страница
    pg.click("#vl-add"); pg.wait_for_timeout(100); pg.fill("#vl-name", "Ютуб"); pg.fill("#vl-value", "Пароль-ютуб-1"); pg.click("#vl-save"); pg.wait_for_timeout(400)
    ok("Ютуб" in names(pg) and pg.inner_text(".vl-range").startswith("21–28") and pg.locator(".vl-item.fresh").count() == 1,
       f"новая запись — открыта её страница, строка подсвечена: {pg.inner_text('.vl-range')!r}")
    if SHOT: pg.screenshot(path=str(Path(SHOT) / "vault-pages-3.png"), full_page=True)
    # много страниц — с многоточием
    pg.evaluate("for (let i = 0; i < 80; i++) V.push({ id: 'm' + i, name: 'Запись ' + String(i).padStart(2, '0'), value: 'x' }); loadVaultPage()"); pg.wait_for_timeout(300)
    pg.click(".vl-pn[data-pg='3']"); pg.wait_for_timeout(150); pg.click(".vl-pn[data-pg='4']"); pg.wait_for_timeout(150); pg.click(".vl-pn[data-pg='5']"); pg.wait_for_timeout(200)
    labels = pg.evaluate("[...document.querySelectorAll('.vl-pns > *')].map(e => e.classList.contains('vl-gap') ? '…' : e.textContent.trim() || '›')")
    ok(labels.count("…") == 2 and "1" in labels and "11" in labels and "6" in labels and len(labels) <= 11, f"108 записей — «1 … 5 6 7 … 11», ряд не разрастается: {labels}")
    pg.set_viewport_size({"width": 1400, "height": 950}); pg.wait_for_timeout(400)
    ok(pg.inner_text(".vl-range").startswith("46–54"), f"окно ниже — по 9 на странице, первая запись страницы (51-я) остаётся видна: {pg.inner_text('.vl-range')!r}")
    over = pg.evaluate("(() => { const r = document.querySelector('.vl-pager').getBoundingClientRect(); return r.bottom - innerHeight; })()")
    ok(over <= 0, f"страница целиком и кнопки страниц — без прокрутки ({over:.0f} px)")
    if SHOT: pg.screenshot(path=str(Path(SHOT) / "vault-pages-950.png"))
    pg.set_viewport_size({"width": 720, "height": 900}); pg.wait_for_timeout(200)
    ok(pg.evaluate("document.documentElement.scrollWidth <= innerWidth"), "узкое окно — без прокрутки вбок")
    pg.evaluate("document.documentElement.classList.add('st-light')"); pg.wait_for_timeout(100)
    if SHOT: pg.screenshot(path=str(Path(SHOT) / "vault-pages-narrow.png"), full_page=True)
    b.close()
ok(not errs, f"без ошибок на странице: {errs[:3]}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
