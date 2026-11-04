"""№519 (04.11, телефон 0.9.18, «Раньше сама обновлялась, сейчас нет»; на «обновись» модель ответила «Я не могу обновить
саму себя»). «Обновись», «проверь обновления», «есть новая версия?» — делом и без модели: есть новее — «Есть новая версия
X — обновляю» и открывается обновление; нет — «У вас последняя версия». Обычные фразы со словом «обнови» сюда не попадают."""
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


tmp = Path(tempfile.mkdtemp()); www = tmp / "www"
shutil.copytree(ROOT / "android/assets/www", www)
for x in ("entities.js", "rich.js", "skins.js", "skins.css", "privacy.js", "closecrypto.js", "qrcode.js", "call.js", "codes.js"):
    if (ROOT / "ui/assets" / x).exists():
        shutil.copy(ROOT / "ui/assets" / x, www / x)
shutil.copytree(ROOT / "ui/assets/live", www / "live", dirs_exist_ok=True)
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                capture_output=True, text=True, check=True).stdout, encoding="utf-8")
LATEST = {"v": "0.9.99"}
errs = []
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 390, "height": 844})
    pg.on("pageerror", lambda x: errs.append(str(x)))
    pg.route("https://dewiar.pro/dwrapp/latest.json", lambda r: r.fulfill(status=200, body=json.dumps({"android": {"version": LATEST["v"], "apk": "Dewiar.apk", "sha256": "x"}}),
                                                                      headers={"Access-Control-Allow-Origin": "*", "Content-Type": "application/json"}))
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(1000)
    pg.evaluate("() => { const i = D.info; D.info = () => JSON.stringify(Object.assign(JSON.parse(i ? i() || '{}' : '{}'), { version: '0.9.18' })); window.updChecked = 0; const c = checkUpdate; checkUpdate = (m) => { updChecked++; return c(m); }; window.updGets = 0; D.updateGet = () => { updGets++; }; }")
    # рецензия 0.82: «проверь обновления», «есть новая версия?» — сказать и показать, но не скачивать
    for q in ("Лира, проверь обновления", "есть новая версия?", "обновление есть?"):
        r = pg.evaluate("async (q) => (await quick(q)) || null", q)
        pg.wait_for_timeout(900)
        ok(r and "0.9.99" in r["say"] and "обновись" in r["say"] and "обновляю" not in r["say"] and pg.evaluate("updGets") == 0,
           f"«{q}» при новой версии — «Скажите „обновись“», без скачивания: {r and r['say']}")
    ok(pg.evaluate("updChecked") >= 1 and pg.evaluate("!!document.querySelector('#upd-go')"), "«О приложении» открыто, кнопка «Обновить» — для человека")
    pg.evaluate("() => { const s = document.querySelector('#sh-set'); if (s) s.classList.remove('on'); }")
    for q in ("Обновись", "Лира, обнови приложение", "установи обновление"):
        pg.evaluate("window.updGets = 0")
        r = pg.evaluate("async (q) => (await quick(q)) || null", q)
        ok(r and "0.9.99" in r["say"] and "обновляю" in r["say"], f"«{q}» при новой версии — делом, без модели: {r}")
        pg.wait_for_timeout(900)
        ok(pg.evaluate("updGets") == 1, f"«{q}» — скачивание началось (открыто «О приложении», «Обновить»)")
    # детский режим: не скачиваем и PIN не просим
    pg.evaluate("() => { window.updGets = 0; window.pinAsked = 0; const kp = kidsPin; kidsPin = (t) => { pinAsked++; }; S.kids = Object.assign({}, S.kids || {}, { on: true }); }")
    r = pg.evaluate("async () => (await quick('Обновись')) || null")
    pg.wait_for_timeout(900)
    ok(r and "взрослый" in r["say"] and pg.evaluate("updGets") == 0 and pg.evaluate("pinAsked") == 0,
       f"детский режим: «Обновление ставит взрослый», без скачивания и PIN: {r and r['say']}")
    pg.evaluate("() => { S.kids.on = false; }")
    LATEST["v"] = "0.9.18"
    r = pg.evaluate("async () => (await quick('Лира, проверь обновления')) || null")
    ok(r and "последняя версия" in r["say"] and "0.9.18" in r["say"], f"«проверь обновления» без новой — «У вас последняя версия»: {r}")
    for q in ("есть новая версия?", "обнови приложение"):
        r = pg.evaluate("async (q) => (await quick(q)) || null", q)
        ok(r and "последняя версия" in r["say"], f"«{q}» — тоже: {r and r['say']}")
    for q in ("обнови список покупок", "обновись в заметке про ремонт"):
        r = pg.evaluate("async (q) => (await quick(q)) || null", q)
        ok(not r or "верси" not in (r.get("say") or ""), f"«{q}» — не про обновление программы")
    ok(not errs, f"без ошибок: {errs}")
    b.close()
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
