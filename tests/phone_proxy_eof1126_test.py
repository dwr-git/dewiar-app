"""№1113 (26.11): «Обновление на телефоне так и не работает… Не проверилось: unexpected end of stream on null» — с 0.9.81 по
0.9.93, и отчёт с телефона не уходит, а сайт в браузере открывается. Повтор новым соединением (№994, 0.9.87) не помог:
«…on null» Android пишет, когда ПРОКСИ на пути молча закрыл связь на CONNECT (свой, прокси Dewiar или прокси из настроек
Wi-Fi/VPN), — тем же путём шёл и повтор.
- отказ прокси — повтор напрямую, мимо любых прокси; открылось — 15 минут к этому адресу напрямую;
- сайт ответил, что прокси Dewiar больше не раздаётся, — старый адрес прокси забываем (иначе все запросы — в мёртвый прокси,
  и обновить его некому: запрос за новым идёт туда же);
- человеку — понятная причина, а не «unexpected end of stream on null»."""
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
for k in [k for k in os.environ if k.lower().endswith("_proxy")]:
    os.environ.pop(k)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


# ---------- Java: мёртвый прокси → напрямую ----------
if shutil.which("javac"):
    tmp = Path(tempfile.mkdtemp())

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            b = b'{"android":{"version":"9.9.9"}}'
            self.send_response(200)
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    dead = socket.socket()
    dead.bind(("127.0.0.1", 0))
    dead.listen(16)

    def closer():
        while True:
            try:
                c, _ = dead.accept()
                c.recv(1024)
                c.close()                      # прокси молча закрыл связь
            except OSError:
                return
    threading.Thread(target=closer, daemon=True).start()
    src = tmp / "src/pro/dewiar/app"
    src.mkdir(parents=True)
    shutil.copy(ROOT / "android/src/pro/dewiar/app/NetProxy.java", src)
    (src / "M.java").write_text('''package pro.dewiar.app;
import java.io.*; import java.net.*;
public class M { public static void main(String[] a) throws Exception {
  URL u = new URL(a[0]);
  NetProxy.set("http://127.0.0.1:" + a[1], "");
  System.out.println("uses " + NetProxy.uses(u) + " any " + NetProxy.viaAnyProxy(u));
  try { HttpURLConnection c = (HttpURLConnection) NetProxy.open(u); c.setReadTimeout(5000); System.out.println("A " + c.getResponseCode()); }
  catch (IOException e) { System.out.println("A ERR " + e.getMessage()); }
  HttpURLConnection d = (HttpURLConnection) NetProxy.openDirect(u); d.setReadTimeout(5000);
  System.out.println("D " + d.getResponseCode()); NetProxy.directOk(u);
  HttpURLConnection c2 = (HttpURLConnection) NetProxy.open(u); c2.setReadTimeout(5000); System.out.println("B " + c2.getResponseCode());
  System.out.println("F " + NetProxy.proxyFail(new IOException("unexpected end of stream on null")) + " " + NetProxy.proxyFail(new IOException("timeout")));
}}''')
    env = {k: v for k, v in os.environ.items() if k != "JAVA_TOOL_OPTIONS"}
    subprocess.run(["javac", "-d", str(tmp / "cls")] + [str(p) for p in src.glob("*.java")], check=True, env=env, capture_output=True)
    (tmp / "hosts").write_text("127.0.0.1 localhost\n127.0.0.1 t.dewiar.pro\n")
    out = subprocess.run(["java", "-cp", str(tmp / "cls"), f"-Djdk.net.hosts.file={tmp / 'hosts'}", "pro.dewiar.app.M",
                          f"http://t.dewiar.pro:{srv.server_port}/dwrapp/latest.json", str(dead.getsockname()[1])],
                         capture_output=True, text=True, env=env, timeout=60)
    print(out.stderr[-1500:])
    out = out.stdout
    print(out)
    ok("uses true any true" in out, "адрес Dewiar с прокси — «через прокси»")
    ok("A ERR" in out, "мёртвый прокси — ошибка (так и было у человека)")
    ok("D 200" in out, "напрямую, мимо прокси, — открывается")
    ok("B 200" in out, "после удачи напрямую — и дальше напрямую (15 минут), без мёртвого прокси")
    ok("F true false" in out, "«…end of stream on null» — признак прокси; таймаут — нет")
    srv.shutdown()
    dead.close()
else:
    print("нет JDK — Java-часть пропускаю")

net = (ROOT / "android/src/pro/dewiar/app/Net.java").read_text(encoding="utf-8")
ok("NetProxy.openDirect(new URL(url))" in net and "NetProxy.proxyFail(e)" in net and "NetProxy.directOk(new URL(url))" in net,
   "Net.request: отказ прокси — повтор напрямую; удалось — запомнить")

# ---------- app.js: причина словами, мёртвый прокси Dewiar забываем ----------
app = (ROOT / "android/www-src/app/02-radio.js").read_text(encoding="utf-8")
js = r"""
const src = require("fs").readFileSync(process.argv[1], "utf8");
const D = {}; eval(src.slice(src.indexOf("const HOME_URL"), src.indexOf("\n}\n", src.indexOf("function netErr")) + 3));
console.log(JSON.stringify([netErr("unexpected end of stream on null", "https://dewiar.pro/dwrapp/latest.json"),
  netErr("unexpected end of stream on Connection{dewiar.pro:443}", "https://dewiar.pro/dwrapp/cloud.php")]));
"""
import json  # noqa: E402
o = json.loads(subprocess.run(["node", "-e", js, str(ROOT / "android/www-src/app/02-radio.js")], capture_output=True, text=True, check=True).stdout)
ok("прокси" in o[0] and "Wi-Fi" in o[0] and "end of stream" not in o[0], f"«…on null» — человеку про прокси: {o[0]}")
ok(o[1] == "связь с сервером оборвалась", f"обрыв без прокси — «связь оборвалась»: {o[1]}")
h = (ROOT / "android/www-src/app/04-health.js").read_text(encoding="utf-8")
fn = h[h.index("async function dwProxyFetch"):h.index("\n}\n", h.index("async function dwProxyFetch")) + 3]
ok('if (!e.net && S.net.dewiar_secret) { S.net.dewiar_secret = ""' in fn, "прокси Dewiar больше не раздают — старый адрес забыт")
built = (ROOT / "android/assets/www/app.js").read_text(encoding="utf-8")
ok("end of stream on null|response code for CONNECT" in built, "app.js собран из частей")

print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
