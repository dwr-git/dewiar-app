"""Телефон, владелец 17.11: «последние пару дней — предупреждение о слишком ресурсоёмкой программе» (Huawei: «частое
обновление данных в фоновом режиме»). Свёрнутое приложение (MainActivity.onPause → событие «pause») больше не опрашивает
облако по таймерам — синхронизация, радар «Близких», объявления (ответ на жалобу — и в фоне: раз в 15 минут, пока ждёт); развернули — сразу синхронизация. Служба
«на связи» (CloseLive) при погасшем экране и без нового делает передышку между ожиданиями."""
import os, re, shutil, subprocess, sys, tempfile
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
for f in ("entities.js", "rich.js", "skins.js", "skins.css", "speechnorm.js"):
    if (ROOT / "ui/assets" / f).exists():
        shutil.copy(ROOT / "ui/assets" / f, www / f)
shutil.copytree(ROOT / "ui/assets/live", www / "live", dirs_exist_ok=True)
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                capture_output=True, text=True, check=True).stdout, encoding="utf-8")
errs = []
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 400, "height": 860})
    pg.on("pageerror", lambda x: errs.append(str(x)))
    pg.clock.install()
    pg.goto((www / "index.html").as_uri()); pg.clock.run_for(1500)
    # считаем вызовы фоновых опросов — подменой самих функций (сеть в проверке не нужна)
    pg.evaluate("""() => { window.__hits = []; S.join = 'x'; const wrap = (n) => { window[n] = (...a) => { __hits.push(n); return Promise.resolve(); }; };
        for (const n of ['syncRun', 'joinPoll', 'welcomeSeen', 'annCheck', 'cmpTick', 'syncSoon', 'doneInbox']) wrap(n); }""")
    pg.clock.run_for(5 * 60_000 + 1000)
    seen = sorted(set(pg.evaluate("__hits")))
    ok({"syncRun", "welcomeSeen", "annCheck"} <= set(seen), f"на экране — опросы идут: {seen}")
    pg.evaluate("() => { __hits = []; N.ev(JSON.stringify({type: 'pause'})); }")
    pg.clock.run_for(20 * 60_000)
    hid = [x for x in pg.evaluate("__hits") if x != "cmpTick"]   # ответ разработчика на жалобу — и в фоне (раз в 15 мин, пока ждёт ответа)
    ok(not hid and pg.evaluate("appAway()"), f"свёрнуто 20 минут — ни одного опроса по таймеру: {sorted(set(hid))}")
    pg.evaluate("() => N.ev(JSON.stringify({type: 'resume'}))"); pg.clock.run_for(500)
    back = pg.evaluate("__hits")
    ok("syncSoon" in back and not pg.evaluate("appAway()"), f"развернули — сразу синхронизация: {back}")
    b.close()
ok(not [e for e in errs if "appAway" in e or "appPaused" in e], f"без ошибок: {errs[:2]}")
src = "".join((ROOT / "android/www-src/app" / f).read_text(encoding="utf-8") for f in sorted(os.listdir(ROOT / "android/www-src/app")))
left = [m for m in re.findall(r"setInterval\(\(\) => \{[^\n]*document\.hidden[^\n]*(?:syncRun|joinPoll|annCheck|welcomeSeen)", src)]
ok(not left, f"опросы облака по таймеру смотрят appAway(), а не только document.hidden: {left[:1]}")
ok("if (appAway() || (typeof EXAM" in src, "радар «Близких» (radTick) в фоне тоже молчит")
cl = (ROOT / "android/src/pro/dewiar/app/CloseLive.java").read_text(encoding="utf-8")
ok("if (empty && !screenOn()) Thread.sleep(QUIET_MS);" in cl and "isInteractive()" in cl, "CloseLive: экран погас и нового нет — передышка")
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
