"""№358 (27.10): «Пока включено прокси на компьютере, локальная модель не подключается. Как только прокси отключается —
подключается». httpx брал прокси системы (Windows — из настроек, иначе HTTP_PROXY) и для localhost:11434: запрос уходил
на прокси, а у прокси свой localhost. Теперь (net._SysProxy): свои адреса — этот компьютер и своя сеть — напрямую,
интернет — через прокси системы, как и раньше; NO_PROXY уважается."""
import json, os, subprocess, sys, tempfile, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


sys.path.insert(0, str(ROOT / "core"))
import net  # noqa: E402
ok(all(net._private_host(h) for h in ("localhost", "127.0.0.1", "192.168.130.200", "10.0.0.5", "172.20.1.1", "::1", "nas.local"))
   and not any(net._private_host(h) for h in ("dewiar.pro", "8.8.8.8", "api.openai.com", "172.32.0.1")), "свои адреса узнаются")

SCRIPT = r'''
import os, sys, threading, json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
sys.path.insert(0, sys.argv[1] + "/core")
hits = {"proxy": [], "direct": []}
def mk(kind, body):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def do_GET(self):
            hits[kind].append(self.path); b = body
            self.send_response(200); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    return H
px = ThreadingHTTPServer(("127.0.0.1", 0), mk("proxy", b"via-proxy")); dr = ThreadingHTTPServer(("127.0.0.1", 0), mk("direct", b"direct"))
for s in (px, dr): threading.Thread(target=s.serve_forever, daemon=True).start()
os.environ["HTTP_PROXY"] = f"http://127.0.0.1:{px.server_port}"
import httpx, net
net.install()
out = {"local": httpx.get(f"http://127.0.0.1:{dr.server_port}/v1/models").text,
       "localhost": httpx.get(f"http://localhost:{dr.server_port}/api/tags").text,
       "internet": httpx.get("http://example.invalid/page").text}
os.environ["NO_PROXY"] = "example.invalid"
try:
    httpx.get("http://example.invalid/x", timeout=2); out["no_proxy"] = "ушло через прокси"
except Exception:
    out["no_proxy"] = "напрямую"
print(json.dumps(out))
'''
env = {k: v for k, v in os.environ.items() if k.lower() not in ("http_proxy", "https_proxy", "all_proxy", "no_proxy")}
r = subprocess.run([sys.executable, "-c", SCRIPT, str(ROOT)], env=env, capture_output=True, text=True, timeout=60)
d = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 and r.stdout.strip() else {}
ok(d.get("local") == "direct" and d.get("localhost") == "direct", f"своя модель (localhost, 127.0.0.1) — мимо прокси системы: {d} {r.stderr[-300:]}")
ok(d.get("internet") == "via-proxy", "интернет — через прокси системы, как раньше")
ok(d.get("no_proxy") == "напрямую", "NO_PROXY — уважается")
print("ИТОГ:", "все проверки пройдены" if not fails else f"не пройдено {len(fails)}")
sys.exit(1 if fails else 0)
