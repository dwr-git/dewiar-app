"""Перед съёмкой видео (отзыв 17.10):
- «очистить диалоги с близкими нельзя, или выборочно поудалять лишнее» — студия: «Выбрать» → отметить → «Удалить у
  меня» (core close.forget), «Отметить все» — вся переписка; телефон: долгое нажатие → «Удалить у меня», корзина в
  шапке — очистить переписку. У близкого переписка остаётся (история у каждого устройства своя);
- «как удалить прошлую встречу?» — у итога в «Суфлёре» кнопка удаления, файл — в корзину;
- «Слух»: при распознавании сервером Dewiar показывали адрес, ключ, модель и язык — «он должен их вносить руками?».
  Теперь «Сервер Dewiar» — отдельный вариант без полей; поля — только у «Своего сервера» (и чистые, без ключа Dewiar);
- чёрное окно до минуты (суфлёр, «Закинуть идею» по Ctrl+Alt+N): страницы ждали шрифты с fonts.googleapis.com.
  Теперь шрифты свои (ui/assets/fonts), внешних таблиц стилей нет;
- окно «Закинуть идею» на трёх мониторах прыгало на другой экран — двигает оконный менеджер, как у суфлёра.
Ядро — настоящее (core/main.py, без звука); студия — ui/settings.html в Chromium."""
import json, os, re, shutil, socket, subprocess, sys, tempfile, time
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
TESTS = Path(__file__).resolve().parent
PY = os.environ.get("DEWIAR_PY") or sys.executable
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


from playwright.sync_api import sync_playwright  # noqa: E402

# ---------- шрифты: свои, без fonts.googleapis.com ----------
pages = ["alarm", "capture", "hud", "prompter", "settings"]
ext = [f for f in pages if re.search(r"fonts\.(googleapis|gstatic)\.com", (ROOT / f"ui/{f}.html").read_text(encoding="utf-8"))]
local = [f for f in pages if 'href="assets/fonts.css"' in (ROOT / f"ui/{f}.html").read_text(encoding="utf-8")]
css = (ROOT / "ui/assets/fonts.css").read_text(encoding="utf-8")
miss = [u for u in re.findall(r"url\((fonts/[^)]+)\)", css) if not (ROOT / "ui/assets" / u).is_file()]
ok(not ext and local == pages and not miss and all(f'"{n}"' in css for n in ("Manrope", "Unbounded", "Lora")),
   f"страницы компьютера — шрифты свои (assets/fonts.css), без fonts.googleapis.com: внешние {ext}, без своих {sorted(set(pages) - set(local))}, нет файлов {miss}")
app = (ROOT / "ui/app.py").read_text(encoding="utf-8")
cap = app.split("def show_capture", 1)[1].split("def _focus_title", 1)[0]
ok("self._wm_drag(gw, lambda px, py, ww: py < CAPTURE_BAR and px < ww - CAPTURE_BTNS)" in cap,
   "«Закинуть идею»: заголовок двигает оконный менеджер (begin_move_drag) — окно не прыгает на другой монитор")

# значок «Записать» на телефоне (отзыв 17.10: «настолько некрасивая, что не хочется нажимать… может в неё мозг и цвета
# получше без обводок», «фиолетовый надоел, может чёрный»): мозг Dewiar вместо микрофона, матово-чёрный фон без обводки
lay = (ROOT / "android/res/layout/widget_capture.xml").read_text(encoding="utf-8")
bg = (ROOT / "android/res/drawable/w_bg.xml").read_text(encoding="utf-8")
from PIL import Image  # noqa: E402
im = Image.open(ROOT / "android/res/drawable-nodpi/w_brain.png")
ok("@drawable/w_brain" in lay and "w_mic" not in lay and "<stroke" not in bg and "<gradient" not in bg and "#EE0A0A0D" in bg and im.mode == "RGBA" and im.size[0] >= 144 and '"22dp"' in bg
   and all(r == g == b == 255 for r, g, b, a in im.getdata() if a > 0) and max(a for *_, a in im.getdata()) < 255,
   "телефон: значок «Записать» — белый полупрозрачный мозг на матово-чёрном без обводки, скругление 22dp")

cw = (ROOT / "android/src/pro/dewiar/app/CaptureWidget.java").read_text(encoding="utf-8")
al = (ROOT / "android/src/pro/dewiar/app/Alarms.java").read_text(encoding="utf-8")
ok('android:id="@+id/w_sub"' in lay and '#B3FFFFFF' in lay and 'paddingLeft="16dp"' in lay
   and "v.setTextViewText(R.id.w_sub, nextLine(c))" in cw and "CaptureWidget.refresh(c);" in al.split("private static void save", 1)[1][:200],
   "телефон: подпись значка белая полупрозрачная, мозг не прижат к краю; в подписи — ближайшее напоминание (обновляется при изменении)")


def free():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


tmp = Path(tempfile.mkdtemp())
PORT = free()
cfg, st, ws = tmp / "cfg", tmp / "st", tmp / "ws"
for d in (cfg, st, ws / "Встречи"):
    d.mkdir(parents=True)
(ws / "Встречи" / "2026-10-11 1944 Встреча.md").write_text("# Встреча\n\nДоговорились.\n", encoding="utf-8")
(ws / "Встречи" / "2026-10-12 1000 Планёрка.md").write_text("# Планёрка\n", encoding="utf-8")
PID = "p_lyoha"
hist = [{"mid": f"m{i}", "ts": 1792000000000 + i * 60000, "out": i % 2 == 1, "t": t, "f": []}
        for i, t in enumerate(["Привет", "Привет", "Кукукукукуку", "Ку-ку ку-ку", "Михалыч, я доехал, всё ок", "Отлично!"])]
(st / "close.json").write_text(json.dumps({"dev": "pc-test", "cursor": 5, "me": {"pid": "p_me", "name": "Миша"},
                                           "people": [{"pid": PID, "name": "Лёха", "devs": [{"dev": "ph-1", "pub": ""}]}],
                                           "hist": {PID: hist}, "unread": {}}, ensure_ascii=False), encoding="utf-8")
(cfg / "settings.json").write_text(json.dumps({"persona": "lira", "audio": {"sounds": False}, "ui": {"news_seen": "99.0.0", "welcome": "done"},
                                               "stt": {"engine": "remote", "remote": {"base_url": "https://dewiar.pro/dwrapp/cloud.php?p=", "api_key": "dw-secret",
                                                                                      "model": "gigaam", "language": "ru", "cloud": True}}}), encoding="utf-8")
env = dict(os.environ, DEWIAR_CONFIG_DIR=str(cfg), DEWIAR_STATE_DIR=str(st), DEWIAR_PORT=str(PORT), DEWIAR_ASSUME_AEC="1",
           DEWIAR_WORKSPACE_DIR=str(ws), XDG_DATA_HOME=str(tmp / "share"), DEWIAR_PROVISION=str(tmp / "no-provision.json"))
core = subprocess.Popen([PY, str(ROOT / "core/main.py"), "--wav", str(TESTS / "silence90.wav"), "--null-audio"], env=env,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
for _ in range(150):
    time.sleep(0.2)
    if (cfg / "token").exists():
        break
time.sleep(2)
tok = (cfg / "token").read_text().strip()
settings = lambda: json.loads((cfg / "settings.json").read_text(encoding="utf-8"))
closest = lambda: json.loads((st / "close.json").read_text(encoding="utf-8"))
errs = []
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        # ---------- шрифты в окне: загружаются с диска ----------
        pg = b.new_page(); pg.goto((ROOT / "ui/capture.html").as_uri()); pg.wait_for_timeout(600)
        fl = pg.evaluate("async () => { await document.fonts.ready; return [...document.fonts].filter(f => f.status === 'loaded').map(f => f.family.replace(/\"/g, '')); }")
        ok("Manrope" in fl and "Unbounded" in fl, f"окно «Закинуть идею»: Manrope и Unbounded загружены сразу, с диска: {sorted(set(fl))}")
        pg.close()

        pg = b.new_page(viewport={"width": 1500, "height": 1000})
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("dialog", lambda d: d.accept()); pg.add_init_script("window.DEWIAR_AUTO_ASK = true")   # свои окна вопроса (assets/dialog.js) — «да»
        pg.goto((ROOT / "ui/settings.html").as_uri() + f"?token={tok}&port={PORT}"); pg.wait_for_timeout(2500)

        # ---------- «Близкие»: выбрать и удалить у себя ----------
        pg.click('nav button[data-p="close"]'); pg.wait_for_timeout(800)
        pg.click(f'#cl-people .cl-p[data-pid="{PID}"]'); pg.wait_for_timeout(500)
        ok(pg.is_visible("#cl-pick") and pg.inner_text("#cl-pick") == "Удалить сообщения", "в шапке переписки — «Удалить сообщения»")
        pg.click("#cl-pick"); pg.wait_for_timeout(200)
        r = [pg.is_visible("#cl-selbar"), pg.is_visible("#cl-send"), pg.is_disabled("#cl-seldel")]
        ok(r == [True, False, True],
           f"режим «Выбрать»: внизу полоса «Удалить у меня» (пока неактивна) вместо поля ввода: {r}")
        pg.click('#cl-msgs .cl-m[data-i="2"]'); pg.click('#cl-msgs .cl-m[data-i="3"]'); pg.wait_for_timeout(100)
        if len(sys.argv) > 1: pg.screenshot(path=str(Path(sys.argv[1]) / "close-pick.png"))
        sel = pg.evaluate("() => [document.querySelectorAll('#cl-msgs .cl-m.sel').length, document.querySelector('#cl-selnum').textContent]")
        ok(sel == [2, "Отмечено: 2"], f"нажатие отмечает сообщение: {sel}")
        pg.click("#cl-seldel"); pg.wait_for_timeout(800)
        left = [m["t"] for m in closest()["hist"][PID]]
        ok(left == ["Привет", "Привет", "Михалыч, я доехал, всё ок", "Отлично!"] and not pg.is_visible("#cl-selbar") and pg.is_visible("#cl-send"),
           f"«Удалить у меня» — ушли только отмеченные, режим выключен: {left}")
        ok(pg.evaluate("() => document.querySelectorAll('#cl-msgs .cl-m').length") == 4, "в окне — оставшиеся четыре")
        # правой кнопкой по одному сообщению — «Удалить у меня» в меню (отзыв 17.10: «не вижу удаления сообщений»)
        pg.click('#cl-msgs .cl-m[data-i="1"]', button="right"); pg.wait_for_timeout(200)
        has = pg.is_visible(".cl-repick .cl-redel")
        pg.click(".cl-repick .cl-redel"); pg.wait_for_timeout(800)
        left = [m["t"] for m in closest()["hist"].get(PID, [])]
        ok(has and left == ["Привет", "Михалыч, я доехал, всё ок", "Отлично!"], f"правая кнопка по сообщению — «Удалить у меня»: {left}")
        pg.click("#cl-pick"); pg.click("#cl-selall"); pg.wait_for_timeout(100)
        ok(pg.inner_text("#cl-seldel") == "Очистить переписку", "«Отметить все» — кнопка становится «Очистить переписку»")
        pg.click("#cl-seldel"); pg.wait_for_timeout(800)
        c = closest()
        ok(PID not in c["hist"] and any(x["pid"] == PID for x in c["people"]) and "пока без сообщений" in pg.inner_text("#cl-people"),
           "вся переписка очищена, а человек остался в близких")

        # ---------- «Суфлёр»: удалить итог прошлой встречи ----------
        pg.click('nav button[data-p="prompter"]'); pg.wait_for_timeout(800)
        if len(sys.argv) > 1: pg.screenshot(path=str(Path(sys.argv[1]) / "prompter.png"))
        n0 = pg.evaluate("() => document.querySelectorAll('#pr-list .pr-del').length")
        pg.click('#pr-list .pr-del[data-p="Встречи/2026-10-11 1944 Встреча.md"]'); pg.wait_for_timeout(1000)
        trashed = list((tmp / "share" / "Trash" / "files").glob("*.md")) if (tmp / "share" / "Trash").exists() else []
        ok(n0 == 2 and not (ws / "Встречи" / "2026-10-11 1944 Встреча.md").exists() and (ws / "Встречи" / "2026-10-12 1000 Планёрка.md").exists()
           and pg.evaluate("() => document.querySelectorAll('#pr-list .pr-del').length") == 1,
           f"у итога встречи — «Удалить»: файл ушёл, остальные на месте (в корзине: {[x.name for x in trashed]})")
        bad = pg.evaluate("() => core.call('prompter_meeting_remove', { path: 'Заметки/../Встречи/2026-10-12 1000 Планёрка.md' }).then(() => 'ok', e => e.message)")
        ok(bad != "ok" and (ws / "Встречи" / "2026-10-12 1000 Планёрка.md").exists(), f"удалить можно только итог встречи: {bad}")

        # ---------- «Слух»: сервер Dewiar — без адреса и ключа ----------
        pg.click('nav button[data-p="ears"]'); pg.wait_for_timeout(800)
        if len(sys.argv) > 1: pg.screenshot(path=str(Path(sys.argv[1]) / "ears.png"))
        r = pg.evaluate("""() => ({ opt: !!document.querySelector('#srv-stt-opt').offsetParent, on: document.querySelector('#srv-stt-opt input').checked,
            remote: document.querySelector('[data-eng="remote"] input').checked, sub: !!document.querySelector('.sub[data-for="remote"]').offsetParent })""")
        ok(r == {"opt": True, "on": True, "remote": False, "sub": False},
           f"распознаёт сервер Dewiar — выбран «Сервер Dewiar», адреса и ключа не видно: {r}")
        pg.click('[data-eng="gigaam"]'); pg.wait_for_timeout(1000)
        s1 = settings()["stt"]
        ok(s1["engine"] == "gigaam" and not s1["remote"].get("cloud"), f"выбрали GigaAM — сервер Dewiar выключен: {s1['engine']}")
        ok(not pg.is_visible("#srv-stt-opt"), "без аккаунта и ключа Dewiar варианта «Сервер Dewiar» нет")
        pg.evaluate("() => { DW.dev = Object.assign({}, DW.dev, { cloud_stt: true }); renderSrvSttOpt(); }")   # облако умеет, а ключа нет
        pg.click('#srv-stt-opt'); pg.wait_for_timeout(1000)
        r2 = [settings()["stt"]["engine"], pg.inner_text("#toast"), pg.evaluate("() => document.querySelector('[data-eng=\"gigaam\"] input').checked")]
        ok(r2[0] == "gigaam" and "ключ" in r2[1] and r2[2], f"«Сервер Dewiar» без ключа — понятная причина, выбор остаётся прежним: {r2}")
        pg.evaluate("() => core.call('settings_save', { patch: { stt: { engine: 'remote', remote: { base_url: 'https://dewiar.pro/dwrapp/cloud.php?p=', api_key: 'dw-secret', cloud: true } } } }).then(s => { S = s; refreshStatic(); })")
        pg.wait_for_timeout(300)
        pg.click('[data-eng="remote"]'); pg.wait_for_timeout(1200)
        s3 = settings()["stt"]["remote"]
        vis = pg.evaluate("() => [!!document.querySelector('.sub[data-for=\"remote\"]').offsetParent, document.querySelector('[data-k=\"stt.remote.base_url\"]').value, document.querySelector('[data-k=\"stt.remote.api_key\"]').value]")
        ok(settings()["stt"]["engine"] == "remote" and s3.get("base_url") == "" and s3.get("api_key") == "" and not s3.get("cloud") and vis == [True, "", ""],
           f"«Свой сервер распознавания» — поля открыты и пустые, ключ Dewiar туда не переносится: {vis}")
        ok("Свой сервер распознавания" in pg.inner_text("#p-ears"), "вариант для своего сервера так и назван")
        ok(not errs, f"студия без ошибок: {errs[:3]}")
        pg.close()

        # ---------- телефон: долгое нажатие → «Удалить у меня», корзина — очистить ----------
        www = tmp / "www"
        shutil.copytree(ROOT / "android/assets/www", www)
        for x in ("entities.js", "speechnorm.js"):
            shutil.copy(ROOT / "ui/assets" / x, www / x)
        shutil.copytree(ROOT / "ui/assets/live", www / "live", dirs_exist_ok=True)
        (www / "personas.js").write_text(subprocess.run([PY, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                        capture_output=True, text=True, check=True).stdout, encoding="utf-8")
        ph = b.new_page(viewport={"width": 400, "height": 820}); perr = []
        ph.on("pageerror", lambda e: perr.append(str(e))); ph.on("dialog", lambda d: d.accept())
        ph.goto((www / "index.html").as_uri()); ph.wait_for_timeout(900)
        ph.evaluate("""(h) => { S.onboarded = true; window.syncCred = () => ({ token: 't', link: 't' }); window.clHello = async () => {};
            const st = clLoad(); st.people = [{ pid: 'p1', name: 'Лёха', devs: [] }]; st.hist = { p1: h }; clSave(); openClose('p1'); }""", hist)
        ph.wait_for_timeout(400)
        el = ph.locator('#cl-msgs .clm[data-i="2"]'); bb = el.bounding_box()
        ph.mouse.move(bb["x"] + 20, bb["y"] + 10); ph.mouse.down(); ph.wait_for_timeout(650); ph.mouse.up()
        if len(sys.argv) > 1: ph.screenshot(path=str(Path(sys.argv[1]) / "phone-menu.png"))
        ph.click(".clrepick .dl"); ph.wait_for_timeout(300)
        r = ph.evaluate("() => [(clLoad().hist.p1 || []).map(m => m.t), document.querySelectorAll('#cl-msgs .clm').length]")
        ok(r[0] == ["Привет", "Привет", "Ку-ку ку-ку", "Михалыч, я доехал, всё ок", "Отлично!"] and r[1] == 5,
           f"телефон: долгое нажатие → «Удалить у меня» — ушло одно это сообщение: {r[0]}")
        ph.click("#cl-album"); ph.wait_for_timeout(300); ph.click("#cl-wipe"); ph.wait_for_timeout(300)   # 0.61: корзина — в «Фото и файлы»
        r = ph.evaluate("() => [clLoad().hist.p1 === undefined, clLoad().people.length, !!document.querySelector('#cl-wipe')]")
        ok(r == [True, 1, False], f"телефон: «Фото и файлы» → «Очистить переписку» — очищена, человек остался: {r}")
        ok(not perr, f"телефон без ошибок: {perr[:3]}")
        b.close()
finally:
    core.terminate()
    try:
        core.wait(10)
    except subprocess.TimeoutExpired:
        core.kill()
print("\nИТОГ:", "всё прошло" if not fails else f"не прошло {len(fails)}")
sys.exit(1 if fails else 0)
