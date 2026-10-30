"""Веб-версия догоняет сайт сама (пакет 30.10: iPhone на 0.9.10-web, когда на сайте 0.9.13, и «связь с мозгом: Load failed»).
1) «На экран Домой» не перезагружается неделями: вернулись к странице (visibilitychange) — webver.js спрашивается мимо
   кэша (sw.js его не кэширует), на сайте новее — страница перезагружается; та же версия — нет; не чаще раза в 30 минут.
2) «Load failed» / «Failed to fetch» (так Safari и Chrome называют любой обрыв) — человеку словами, а не по-английски."""
import os, re, shutil, subprocess, sys, tempfile, threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


tmp = Path(tempfile.mkdtemp())
r = subprocess.run(["bash", str(ROOT / "tools/build_web.sh"), str(tmp / "b")], capture_output=True, text=True)
ok(r.returncode == 0, f"веб-версия собирается: {r.stderr[-300:]}")
site = tmp / "site"
(site / "dwrapp").mkdir(parents=True)
shutil.copytree(tmp / "b/web", site / "dwrapp/web")
web = site / "dwrapp/web"
sw = (web / "sw.js").read_text(encoding="utf-8")
ok('u.searchParams.has("fresh")) return;' in sw, "sw.js: проверка версии (?fresh=) — мимо кэша, всегда с сайта")
cur = re.search(r'"([^"]+)"', (web / "webver.js").read_text(encoding="utf-8")).group(1)

SEEN = []


class H(SimpleHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_GET(self):
        if "webver.js" in self.path and "fresh=" in self.path:
            SEEN.append(self.path)
        return super().do_GET()


srv = ThreadingHTTPServer(("127.0.0.1", 0), partial(H, directory=str(site)))
threading.Thread(target=srv.serve_forever, daemon=True).start()
url = f"http://127.0.0.1:{srv.server_address[1]}/dwrapp/web/index.html"

with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 393, "height": 820}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route("https://**", lambda rt: rt.abort())
    pg.goto(url); pg.wait_for_timeout(1500)
    ok(pg.evaluate("window.DEWIAR_WEB_VERSION") == cur, f"страница знает свою версию: {cur}")
    hide = "Object.defineProperty(document, 'hidden', {configurable: true, get: () => %s}); document.dispatchEvent(new Event('visibilitychange'))"
    pg.evaluate("window.__mark = 1")
    pg.evaluate(hide % "true"); pg.evaluate(hide % "false"); pg.wait_for_timeout(600)
    ok(not SEEN and pg.evaluate("window.__mark") == 1, "вернулись через минуту — не спрашивает (не чаще раза в 30 минут)")
    # прошло 31 минута, на сайте та же версия — без перезагрузки
    pg.evaluate("(() => { const n = Date.now; Date.now = () => n() + 31 * 60e3; })()")
    pg.evaluate(hide % "true"); pg.evaluate(hide % "false"); pg.wait_for_timeout(800)
    ok(len(SEEN) == 1 and pg.evaluate("window.__mark") == 1, f"через 31 минуту — спросила сайт мимо кэша, версия та же — осталась: {SEEN}")
    # на сайте вышла новая
    (web / "webver.js").write_text('window.DEWIAR_WEB_VERSION = "9.9.9-web";\n', encoding="utf-8")
    pg.evaluate("(() => { const n = Date.now; Date.now = () => n() + 62 * 60e3; })()")
    pg.evaluate(hide % "true"); pg.evaluate(hide % "false"); pg.wait_for_timeout(2500)
    ok(len(SEEN) == 2 and pg.evaluate("window.__mark") is None, "на сайте новее — страница перезагрузилась сама")
    # слова вместо «Load failed»
    words = pg.evaluate("""() => ['Load failed', 'TypeError: Failed to fetch', 'NetworkError when attempting to fetch resource.']
        .map(e => netErr(e, 'https://dewiar.pro/dwrapp/cloud.php'))""")
    ok(all(w.startswith("связь с сервером оборвалась") for w in words), f"«Load failed» и подобное — словами: {words}")
    ok(pg.evaluate("netErr('Load failed', 'http://192.168.1.5:1234/v1')").startswith("домашний сервер"), "домашний сервер — про домашнюю сеть")
    b.close()
srv.shutdown()
ok(not errs, f"без ошибок на странице: {errs[:3]}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
