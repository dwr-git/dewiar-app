"""№575 (ПК 0.84.2, Windows 11, 05.11): «„Видеоуроки“: не отображаются картинки» (человек сам нашёл причину: «зеркало того,
что сделано для close_thumb и art_url»). На Windows студия открыта с http://127.0.0.1, а Chromium с http-страницы file://
не грузит — обложки из кэша уроков пропадали (и видео с диска — тоже). Теперь картинки ядро отдаёт data:URL, а видео
отдаёт сервер окон по имени из кэша (/academy-cache/…)."""
import http.server, os, socket, sys, tempfile, threading, urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ["DEWIAR_STATE_DIR"] = str(tmp / "state")
sys.path.insert(0, str(ROOT / "core"))
sys.path.insert(0, str(ROOT / "ui"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


def free():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


PNG = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000" "1f15c4890000000d49444154789c6360f8cf000000030101" "00c9fe92ef0000000049454e44ae426082")


class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_GET(self):
        b = {"/dwrapp/academy/05-clients.png": PNG, "/dwrapp/academy/05-clients.mp4": b"\x00\x00\x00\x18ftypmp42" + b"0" * 2000}.get(self.path)
        if b is None:
            self.send_response(404); self.end_headers(); return
        self.send_response(200); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)


PORT = free()
threading.Thread(target=http.server.ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever, daemon=True).start()
for k in [k for k in os.environ if "proxy" in k.lower()]:
    os.environ.pop(k)
import engine_commands as EC  # noqa: E402
from settings import STATE_DIR  # noqa: E402
EC.STATE_DIR = STATE_DIR


class E(EC.CommandsMixin):
    class cloud:
        url = f"http://127.0.0.1:{PORT}/dwrapp/cloud.php?p="
    kids = None


img = E().command("academy_file", {"url": f"http://127.0.0.1:{PORT}/dwrapp/academy/05-clients.png"})
ok(img["uri"].startswith("data:image/png;base64,") and img["name"] == "05-clients.png", f"обложка — data:URL, а не file://: {img['uri'][:40]}")
vid = E().command("academy_file", {"url": f"http://127.0.0.1:{PORT}/dwrapp/academy/05-clients.mp4"})
ok(vid["uri"].startswith("file://") and vid["name"] == "05-clients.mp4", f"видео — с диска, с именем для сервера окон: {vid}")

import app as UI  # noqa: E402
base = UI.ui_http_base()
got = urllib.request.urlopen(base + "academy-cache/05-clients.mp4", timeout=5)
ok(got.headers.get("Content-Type") == "video/mp4" and got.read()[4:8] == b"ftyp", "сервер окон отдаёт видеоурок из кэша по имени")
for bad in ("academy-cache/..%2F..%2Fsettings.json", "academy-cache/x.sh", "academy-cache/%2Fetc%2Fpasswd.png", "academy-cache/CON.mp4", "academy-cache/nul.jpg"):
    try:
        urllib.request.urlopen(base + bad, timeout=5); ok(False, f"чужое не отдаёт: {bad}")
    except urllib.error.HTTPError as e:
        ok(e.code == 404, f"чужое не отдаёт: {bad} → {e.code}")

errs = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1300, "height": 860}); pg.on("pageerror", lambda x: errs.append(str(x)))
    pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };")
    pg.goto(base + "settings.html?port=1"); pg.wait_for_timeout(1200)       # как на Windows: студия — с http://127.0.0.1
    r = pg.evaluate("""([img, vid]) => { LSN.files = {};
        core.call = (c, a) => Promise.resolve(c === 'academy_file' ? (a.url.endsWith('.png') ? img : vid) : {});
        return Promise.all([lsLocal('https://dewiar.pro/dwrapp/academy/05-clients.png'), lsLocal('https://dewiar.pro/dwrapp/academy/05-clients.mp4')]); }""",
        [img, vid])
    ok(r[0].startswith("data:image/png") and r[1] == base + "academy-cache/05-clients.mp4", f"студия с http: обложка data:, видео — с сервера окон: {[x[:50] for x in r]}")
    shown = pg.evaluate("""(u) => new Promise(res => { const i = new Image(); i.onload = () => res(i.naturalWidth); i.onerror = () => res(-1); i.src = u; })""", r[0])
    ok(shown == 1, f"обложка на http-странице и правда показывается: {shown}")
    b.close()
ok(not errs, f"без ошибок на странице: {errs[:3]}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
