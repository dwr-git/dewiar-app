"""Студия → «Устройства» (0.56; письмо пользователя 28.10 — «хрен найдёшь, где эта синхронизация»): раздел в меню
(«Связи и данные»), карта — Лира и все устройства (на связи — яркая линия), это устройство с именем и «Синхронизировать
сейчас», «Подключить ещё устройство» — 6 цифр, QR и обратный отсчёт; подключилось новое — «Подключилось: …» и код
прячется; «Ввести код» — 6 цифр (меньше — подсказка), «Своя модель осталась главной»; список с видом, версией и «на связи
сейчас / был … назад»; «Переименовать», «Убрать». Без входа — «Показать код» приглушена, нажали — сказано, что делать."""
import json, os, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


now = int(time.time())
SYNC = {"available": True, "on": True, "ok": True, "at": now - 20, "error": "", "e2e": {"on": False}}
DEV = {"me": {"id": "pc-home", "name": "Домашний", "app": "pc", "custom": True}, "mode": "account", "login": "misha", "can_pair": True, "error": "", "sync": SYNC,
       "devices": [{"id": "pc-home", "name": "Домашний", "app": "pc", "ver": "0.56.0", "seen": now, "me": True},
                   {"id": "phone-1", "name": "Pixel 7", "app": "phone", "ver": "0.9.0", "seen": now - 40, "me": False},
                   {"id": "pc-work", "name": "Рабочий", "app": "pc", "ver": "0.55.1", "seen": now - 7200, "me": False},
                   {"id": "pc-cloud", "name": "Облако Dewiar", "app": "cloud", "ver": "", "seen": now - 30, "me": False}]}
NEW = dict(DEV, devices=DEV["devices"] + [{"id": "pc-lap", "name": "Ноутбук", "app": "pc", "ver": "0.56.0", "seen": now, "me": False}])
NOLOG = dict(DEV, mode="", can_pair=False, sync=dict(SYNC, available=False), devices=[DEV["devices"][0]])
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 1400, "height": 1000}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };")
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(1000)
    ok(pg.evaluate("() => { const b = document.querySelector('nav button[data-p=devices]'); return !!b && !b.hidden && b.previousElementSibling.textContent === 'Связи и данные'; }"),
       "в меню — «Устройства», первым в «Связи и данные»")
    pg.evaluate("""([dev, nw, nolog]) => { window._calls = []; window._st = dev; window.ask = () => Promise.resolve(true); window.askText = () => Promise.resolve('Рабочий-2');
      core.call = (c, a) => { _calls.push([c, a || {}]);
        if (c === 'devices_get') return Promise.resolve(_st);
        if (c === 'pair_new') return Promise.resolve({ ok: true, code: '482915', expires: 600, account: true, link: 'https://dewiar.pro/dwrapp/download.php?pair=482915', app: 'dewiar://pair?c=482915' });
        if (c === 'pair_claim') return Promise.resolve({ ok: true, account: false, brain_kept: true });
        if (c === 'device_rename') { _st = Object.assign({}, _st, { me: Object.assign({}, _st.me, { name: a.name }) }); return Promise.resolve(_st); }
        if (c === 'device_forget') { _st = Object.assign({}, _st, { devices: _st.devices.filter(d => d.id !== a.id) }); return Promise.resolve(_st); }
        if (c === 'sync_now') return Promise.resolve({});
        if (c === 'brains_pull') return Promise.resolve({ sent: true, until: 0 });
        if (c === 'brains_status') return Promise.resolve({ waiting: false, got: [{ from: 'Рабочий', names: ['Qwen домашний', 'Claude'] }] });
        return Promise.resolve({}); };
      window._nw = nw; window._nolog = nolog;
      document.querySelector('nav button[data-p=devices]').click(); }""", [DEV, NEW, NOLOG])
    pg.wait_for_timeout(700)
    rows = pg.evaluate("() => [...document.querySelectorAll('#dv-list li')].map(li => [li.querySelector('b').textContent, li.querySelector('small').textContent, li.className, !!li.querySelector('[data-forget]')])")
    ok(len(rows) == 4 and rows[0][0].startswith("Домашний") and "это устройство" in rows[0][0] and not rows[0][3], f"список: это устройство первым, без «Убрать»: {rows[0]}")
    ok("на связи сейчас" in rows[1][1] and "Телефон · Dewiar 0.9.0" in rows[1][1] and "on" in rows[1][2], f"телефон — на связи сейчас: {rows[1][1]}")
    ok("был 2 ч назад" in rows[2][1] and "on" not in rows[2][2] and rows[2][3], f"рабочий — был 2 ч назад, можно убрать: {rows[2][1]}")
    ok(not rows[3][3] and "Облако Dewiar" in rows[3][1], "облако Dewiar — без «Убрать»")
    m = pg.evaluate("() => [document.querySelectorAll('#dv-map .dv-node').length, document.querySelectorAll('#dv-map .dv-ln.on').length, document.querySelector('#dv-map .dv-orbt').textContent]")
    ok(m[0] == 4 and m[1] == 3, f"карта: четыре устройства вокруг Лиры, на связи — три яркие линии: {m}")
    st = pg.evaluate("() => [document.querySelector('#dv-myname').textContent, document.querySelector('#dv-sync-st').textContent, document.querySelector('#dv-via').textContent, document.querySelector('#dv-count').textContent]")
    ok(st[0] == "Домашний" and st[1].startswith("Синхронизировано в") and "по аккаунту misha" in st[2] and "на связи сейчас: 2" in st[3], f"это устройство и синхронизация: {st}")
    if os.environ.get("DEWIAR_SHOTS"): pg.screenshot(path=str(Path(os.environ["DEWIAR_SHOTS"]) / "studio-devices.png"), full_page=True)
    # подключить ещё
    pg.click("#dv-give-go"); pg.wait_for_timeout(500)
    c = pg.evaluate("() => [document.querySelector('#dv-code').hidden, document.querySelector('#dv-digits').textContent, !!document.querySelector('#dv-qr svg'), document.querySelector('#dv-left').textContent]")
    ok(c[0] is False and c[1] == "482 915" and c[2] and ("Действует ещё 9:5" in c[3] or "Действует ещё 10:00" in c[3]) and "тем же аккаунтом" in c[3], f"код: 6 цифр, QR, обратный отсчёт, вход тем же аккаунтом: {c}")
    if os.environ.get("DEWIAR_SHOTS"): pg.screenshot(path=str(Path(os.environ["DEWIAR_SHOTS"]) / "studio-devices-code.png"), full_page=True)
    pg.evaluate("() => { _st = _nw; return dvRefresh(); }"); pg.wait_for_timeout(500)
    ok("Подключилось: Ноутбук" in pg.inner_text("#toast") and pg.evaluate("document.querySelector('#dv-code').hidden"), "подключилось новое — «Подключилось: Ноутбук», код спрятан")
    # ввести код
    pg.fill("#dv-codein", "48"); pg.click("#dv-take-go"); pg.wait_for_timeout(200)
    ok("6 цифр" in pg.inner_text("#dv-take-res"), "меньше 6 цифр — подсказка")
    pg.fill("#dv-codein", "482915"); pg.wait_for_timeout(100)
    ok(pg.input_value("#dv-codein") == "482 915", "цифры — группами по три")
    pg.click("#dv-take-go"); pg.wait_for_timeout(400)
    ok(["pair_claim", {"code": "482915"}] in pg.evaluate("_calls") and "модель осталась главной" in pg.inner_text("#dv-take-res"), f"«Подключить» → pair_claim: {pg.inner_text('#dv-take-res')}")
    pg.click("#dv-rename"); pg.wait_for_timeout(300)
    ok(["device_rename", {"name": "Рабочий-2"}] in pg.evaluate("_calls") and pg.inner_text("#dv-myname") == "Рабочий-2", "«Переименовать» — своё имя")
    pg.locator("#dv-list li", has_text="Рабочий").locator("[data-forget]").first.click(); pg.wait_for_timeout(400)
    ok(["device_forget", {"id": "pc-work"}] in pg.evaluate("_calls"), "«Убрать» — device_forget")
    pg.click("#dv-now"); pg.wait_for_timeout(300)
    ok(any(x[0] == "sync_now" for x in pg.evaluate("_calls")), "«Синхронизировать сейчас»")
    pg.click("#dv-brains-go"); pg.wait_for_timeout(300)
    ok("Жду ответа" in pg.inner_text("#dv-brains-res"), "«Взять мозги» — жду ответа")
    pg.evaluate("async () => dvBrains(await core.call('brains_status'))"); pg.wait_for_timeout(200)
    ok("С «Рабочий»: Qwen домашний, Claude" in pg.inner_text("#dv-brains-res"), f"пришли мозги — видно, с какого устройства и какие: {pg.inner_text('#dv-brains-res')}")
    # без входа
    pg.evaluate("() => { _st = _nolog; return loadMyDevices(true); }"); pg.wait_for_timeout(400)
    r = pg.evaluate("() => [document.querySelector('#dv-give-go').classList.contains('ghost'), document.querySelector('#dv-give-hint').textContent, document.querySelector('#dv-sync-st').textContent]")
    n = len(pg.evaluate("_calls"))
    pg.click("#dv-give-go"); pg.wait_for_timeout(200)
    ok(r[0] and "введите его код справа" in r[1] and "Синхронизации нет" in r[2] and "Сначала нужен вход" in pg.inner_text("#dv-give-res")
       and not any(c[0] == "pair_new" for c in pg.evaluate("_calls")[n:]),
       f"без входа — «Показать код» приглушена; нажали — сказано, что делать (не серая без объяснения): {r[1][:60]}")
    b.close()
ok(not errs, "без ошибок JavaScript" + (f": {errs[:3]}" if errs else ""))
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
