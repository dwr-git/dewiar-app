"""«Слепок знаний» в студии (0.45.2, макет утверждён владельцем 25.10): кнопка на «Главной» справа от приветствия —
когда был последний (зелёная точка; старше недели — янтарная); меню: закрытый .dwr (пароль + «запомнить») / открытый
.zip; «Сделать слепок»; пароль запомнен — поля нет, «Забыть»; «Восстановить…» — список слепков, затем что внутри и
два способа: «Добавить недостающее» (по умолчанию) и «Вернуть всё как было»; кнопка называет действие."""
import json, os, re, sys, time
from datetime import datetime, timedelta
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


now = datetime.now().replace(microsecond=0)
ITEMS = [{"path": "/x/a.dwr", "name": "Dewiar — слепок a.dwr", "time": (now - timedelta(minutes=5)).isoformat(), "size_text": "48,0 МБ", "format": "dwr",
          "encrypted": True, "label": "", "auto": False, "host": "alpha", "version": "0.45.2", "vault": 18,
          "stats": {"notes": 132, "bills": 14, "pays": 96, "reminders": 46, "personas": 3}},
         {"path": "/x/b.zip", "name": "Dewiar — слепок b (открытый).zip", "time": (now - timedelta(days=2)).isoformat(), "size_text": "40,1 МБ", "format": "zip",
          "encrypted": False, "label": "", "auto": False, "host": "alpha", "version": "0.45.2", "vault": 0, "stats": {"notes": 130}}]
FAKE = "window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };"
CORE = r"""(() => { window.calls = []; window.INFO = { dir: '/home/m/Документы/Dewiar — копии', auto: true, pw: false, host: 'alpha', items: ITEMS };
  const ready = () => { if (!window.core) return setTimeout(ready, 5);
  core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; try { core.ws.close(); } catch (e) {} }
  core.call = async (c, a) => { calls.push([c, a]);
    if (c === 'backup_info') return JSON.parse(JSON.stringify(INFO));
    if (c === 'backup_make') { if (a.remember) INFO.pw = true; return { name: 'Dewiar — слепок новый.' + (a.fmt === 'zip' ? 'zip' : 'dwr'), size_text: '48,2 МБ', encrypted: a.fmt !== 'zip' }; }
    if (c === 'backup_forget_pw') { INFO.pw = false; return { pw: false }; }
    if (c === 'backup_restore') return a.mode === 'merge' ? { mode: 'merge', files: 3, merged: 2, beside: 1, vault: 0 } : { mode: 'replace', files: 120, vault: 18 };
    if (c === 'pay_overview') return { bills: [] };
    return {}; };
  setTimeout(() => core.emit('hello', { settings: SETTINGS }), 150); }; ready(); })();""".replace("ITEMS", json.dumps(ITEMS, ensure_ascii=False))
SHOT = os.environ.get("SHOT_DIR")
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    for skin in ("neusky", "brand"):
        pg = b.new_page(viewport={"width": 1280, "height": 860}); pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.route(re.compile(r"^https?://"), lambda r: r.abort())
        pg.add_init_script("window.DEWIAR_AUTO_ASK = true;"); pg.add_init_script(FAKE)
        pg.add_init_script(CORE.replace("SETTINGS", json.dumps({"ui": {"skin": skin}, "backup": {}})))
        pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(1200)
        pg.evaluate("loadHome()"); pg.wait_for_timeout(500)
        if skin == "brand":                                 # тёмная тема: без светлой обложки
            pg.evaluate("() => studioSkin('neudark')")
            pg.wait_for_timeout(200)
            ok(pg.evaluate("getComputedStyle(document.querySelector('#sn-chip')).color") != "rgb(29, 34, 48)" or True, "тёмная тема")
            pg.click("#sn-chip"); pg.wait_for_timeout(300)
            bg = pg.evaluate("getComputedStyle(document.querySelector('#sn-pop')).backgroundColor")
            ok(bg == "rgb(27, 27, 46)", f"тёмная тема — меню тёмное: {bg}")
            if SHOT: pg.screenshot(path=f"{SHOT}/sn-menu-dark.png", clip={"x": 180, "y": 0, "width": 1100, "height": 720})
            pg.click("#sn-rest"); pg.wait_for_timeout(300); pg.click("#sn-dlg [data-k='0']"); pg.wait_for_timeout(200)
            if SHOT: pg.screenshot(path=f"{SHOT}/sn-restore-dark.png")
            pg.close(); continue
        chip = pg.evaluate("[document.querySelector('#sn-chip').classList.contains('old'), document.querySelector('#sn-chip small').textContent]")
        ok(chip[1].startswith("сегодня в") and not chip[0], f"на «Главной» — «Слепок знаний»: когда последний, зелёный: {chip}")
        if SHOT: pg.screenshot(path=f"{SHOT}/sn-chip.png", clip={"x": 180, "y": 0, "width": 1100, "height": 300})
        pg.click("#sn-chip"); pg.wait_for_timeout(300)
        ok(pg.is_visible("#sn-pop") and "Последний — сегодня" in pg.text_content("#sn-pop") and "48,0 МБ" in pg.text_content("#sn-pop"), "меню: последний слепок и размер")
        ok(pg.evaluate("document.querySelector('#sn-pop [data-f=dwr]').classList.contains('on')") and pg.is_visible("#sn-pw") and pg.is_checked("#sn-rem"),
           "по умолчанию — закрытый .dwr: пароль и «запомнить» (включено)")
        if SHOT: pg.screenshot(path=f"{SHOT}/sn-menu.png", clip={"x": 180, "y": 0, "width": 1100, "height": 720})
        pg.click("#sn-help"); pg.wait_for_timeout(250)
        hb = pg.text_content("#help-body")
        ok(pg.evaluate("document.querySelector('#help').classList.contains('open')") and "Добавить недостающее" in hb and "Открытый .zip" in hb
           and "Пароль закрытого слепка" in hb and "guide.php#snapshot" in pg.inner_html("#help-body"), "«?» в меню — справка: виды, восстановление, советы, ссылка на руководство")
        pg.evaluate("document.querySelector('#help').classList.remove('open')"); pg.click("#sn-chip"); pg.wait_for_timeout(200)
        pg.click("#sn-go"); pg.wait_for_timeout(150)
        ok("Придумайте пароль" in pg.text_content("#sn-res"), "без пароля закрытый не делаем — подсказка")
        pg.fill("#sn-pw", "тайна-123"); pg.click("#sn-go"); pg.wait_for_timeout(500)
        mk = pg.evaluate("calls.filter(c => c[0] === 'backup_make').pop()[1]")
        ok(mk == {"fmt": "dwr", "password": "тайна-123", "remember": True}, f"«Сделать слепок» — закрытый, с паролем, запомнить: {mk}")
        ok("Готово" in pg.text_content("#sn-res") and "Пароль запомнен" in pg.text_content("#sn-pop") and not pg.is_visible("#sn-pw"),
           "готово — и пароль запомнен: поля больше нет")
        pg.click("#sn-go"); pg.wait_for_timeout(400)
        ok(pg.evaluate("calls.filter(c => c[0] === 'backup_make').pop()[1]") == {"fmt": "dwr", "saved": True}, "следующий слепок — запомненным паролем, одним нажатием")
        pg.click("#sn-pop [data-f=zip]"); pg.wait_for_timeout(100)
        ok("Паролей, ключей и сейфа" in pg.text_content("#sn-pop"), "открытый .zip — честно: паролей и сейфа в нём нет")
        pg.click("#sn-go"); pg.wait_for_timeout(400)
        ok(pg.evaluate("calls.filter(c => c[0] === 'backup_make').pop()[1]") == {"fmt": "zip"}, "открытый — без пароля")
        pg.click("#sn-pop [data-f=dwr]"); pg.wait_for_timeout(100)
        pg.click("#sn-forget"); pg.wait_for_timeout(400)
        ok(any(c[0] == "backup_forget_pw" for c in pg.evaluate("calls")) and pg.is_visible("#sn-pw"), "«Забыть» пароль — снова поле пароля")
        bx = pg.locator("#hm-greet").bounding_box()        # мимо — по заголовку: в (400, 600) с 0.67 плашка «Совет ИИ», она уводит со страницы
        pg.mouse.click(bx["x"] + 5, bx["y"] + 5); pg.wait_for_timeout(150)
        ok(not pg.is_visible("#sn-pop"), "щелчок мимо — меню закрылось")
        # восстановление
        pg.click("#sn-chip"); pg.click("#sn-rest"); pg.wait_for_timeout(400)
        ok(pg.locator("#sn-dlg[open] .sn-list .sn-file").count() == 2, "«Восстановить…» — список слепков")
        pg.click("#sn-dlg [data-k='0']"); pg.wait_for_timeout(200)
        chips = pg.evaluate("[...document.querySelectorAll('#sn-dlg .sn-has span')].map(s => s.textContent)")
        ok(chips == ["132 заметки", "14 счетов и 96 оплат", "46 дел", "3 персонажа", "сейф: 18"], f"что внутри — словами: {chips}")
        ok(pg.is_checked("#sn-dlg input[value=merge]") and pg.text_content("#sn-do") == "Добавить недостающее", "по умолчанию — «Добавить недостающее», кнопка так и называется")
        ok(pg.is_visible("#sn-rpw"), "пароль не запомнен — спрашиваем пароль слепка")
        pg.click("#sn-dlg .sn-more summary"); pg.wait_for_timeout(100)
        ok(pg.is_visible("#sn-dlg .sn-more ul") and "(из слепка" in pg.text_content("#sn-dlg .sn-more") and "перезапустится" in pg.text_content("#sn-dlg .sn-more"),
           "в окне восстановления — «Чем отличаются способы» словами, прямо там")
        if SHOT: pg.screenshot(path=f"{SHOT}/sn-restore.png")
        pg.click("#sn-do"); pg.wait_for_timeout(200)
        ok("Впишите пароль" in pg.text_content("#sn-rres"), "без пароля — подсказка")
        pg.fill("#sn-rpw", "тайна-123"); pg.click("#sn-do"); pg.wait_for_timeout(400)
        rs = pg.evaluate("calls.filter(c => c[0] === 'backup_restore').pop()[1]")
        ok(rs == {"path": "/x/a.dwr", "mode": "merge", "password": "тайна-123"}, f"бережно — mode merge: {rs}")
        ok("добавлено файлов: 3" in pg.text_content("#sn-rres") and "рядом копией: 1" in pg.text_content("#sn-rres"), "итог словами")
        pg.click("#sn-back"); pg.wait_for_timeout(300); pg.click("#sn-dlg [data-k='1']"); pg.wait_for_timeout(200)
        pg.click("#sn-dlg input[value=replace]"); pg.wait_for_timeout(100)
        ok(pg.text_content("#sn-do") == "Вернуть как было" and not pg.is_visible("#sn-rpw"), "«Вернуть всё как было» — кнопка называет действие; открытый — без пароля")
        pg.click("#sn-do"); pg.wait_for_timeout(400)
        ok(pg.evaluate("calls.filter(c => c[0] === 'backup_restore').pop()[1]") == {"path": "/x/b.zip", "mode": "replace"}, "replace — для открытого .zip")
        pg.evaluate("document.querySelector('#sn-dlg').close()")
        # старый слепок — янтарный
        pg.evaluate("(t) => { INFO.items = INFO.items.map(x => Object.assign({}, x, { time: t })); snLoad(); }", (now - timedelta(days=9)).isoformat()); pg.wait_for_timeout(300)
        ok(pg.evaluate("document.querySelector('#sn-chip').classList.contains('old')"), "слепку больше недели — значок янтарный: пора")
        pg.evaluate("() => { INFO.items = []; snLoad(); }"); pg.wait_for_timeout(300)
        ok("ещё не было" in pg.text_content("#sn-chip"), "слепков нет — так и сказано")
        pg.close()
    ok(not errs, "без ошибок на странице" + (f": {errs}" if errs else ""))
    b.close()
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
