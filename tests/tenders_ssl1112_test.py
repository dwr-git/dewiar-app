"""Владелец 12.11, плагин «Тендеры»: «пока не работает — goszakupki.by и icetrade.by: CERTIFICATE_VERIFY_FAILED unable to
get local issuer certificate; и непонятно, как править площадки, добавлять новые и удалять». Теперь:
1) сертификат не проверился — второй заход как у браузера: хранилище системы (антивирус, шлюз) и недостающее
   промежуточное звено цепочки по адресу из самого сертификата (AIA). Проверка не отключается.
2) свои площадки — несколько, добавляются на странице плагина: вставили адрес страницы поиска — слово из запросов
   само заменяется на {QUERY}; ✕ — убрать; встроенные — галочкой."""
import http.server, os, shutil, ssl, subprocess, sys, tempfile, threading
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


if not shutil.which("openssl"):
    print("✅ пропуск: нет openssl"); sys.exit(0)
tmp = Path(tempfile.mkdtemp())
os.environ["DEWIAR_PLUGIN_DATA"] = str(tmp / "data")


def sh(*a):
    subprocess.run(a, cwd=tmp, check=True, capture_output=True)


# корень → промежуточный → лист; у листа — AIA на промежуточный, сервер шлёт только лист (как «забывчивая» площадка)
aia = http.server.ThreadingHTTPServer(("127.0.0.1", 0), http.server.SimpleHTTPRequestHandler)
AIA_PORT = aia.server_port
(tmp / "ext.cnf").write_text(f"""[ca]
basicConstraints=critical,CA:TRUE
keyUsage=critical,keyCertSign,cRLSign
[leaf]
basicConstraints=CA:FALSE
subjectAltName=DNS:localhost,IP:127.0.0.1
authorityInfoAccess=caIssuers;URI:http://127.0.0.1:{AIA_PORT}/int.der
""")
sh("openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", "root.key", "-out", "root.pem", "-days", "3", "-subj", "/CN=Test Root",
   "-addext", "basicConstraints=critical,CA:TRUE", "-addext", "keyUsage=critical,keyCertSign,cRLSign")
sh("openssl", "req", "-newkey", "rsa:2048", "-nodes", "-keyout", "int.key", "-out", "int.csr", "-subj", "/CN=Test Intermediate")
sh("openssl", "x509", "-req", "-in", "int.csr", "-CA", "root.pem", "-CAkey", "root.key", "-CAcreateserial", "-out", "int.pem", "-days", "3",
   "-extfile", "ext.cnf", "-extensions", "ca")
sh("openssl", "x509", "-in", "int.pem", "-outform", "DER", "-out", "int.der")
sh("openssl", "req", "-newkey", "rsa:2048", "-nodes", "-keyout", "leaf.key", "-out", "leaf.csr", "-subj", "/CN=localhost")
sh("openssl", "x509", "-req", "-in", "leaf.csr", "-CA", "int.pem", "-CAkey", "int.key", "-CAcreateserial", "-out", "leaf.pem", "-days", "3",
   "-extfile", "ext.cnf", "-extensions", "leaf")


class AIA(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(tmp), **kw)

    def log_message(self, *a):
        pass


aia.RequestHandlerClass = AIA
threading.Thread(target=aia.serve_forever, daemon=True).start()


class Site(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        b = "<html><body><table><tr><td>Тендер 1</td></tr></table></body></html>".encode()
        self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(b)))
        self.end_headers(); self.wfile.write(b)


site = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Site)
sctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); sctx.load_cert_chain(tmp / "leaf.pem", tmp / "leaf.key")
site.socket = sctx.wrap_socket(site.socket, server_side=True)
threading.Thread(target=site.serve_forever, daemon=True).start()
PORT = site.server_port

os.environ["SSL_CERT_FILE"] = str(tmp / "root.pem")        # «корень есть в системе» (как у антивируса или шлюза)
sys.path.insert(0, str(ROOT / "data/plugins/tenders"))
import server as TS  # noqa: E402

ok(TS._aia_urls((tmp / "leaf.pem").read_text() and ssl.PEM_cert_to_DER_cert((tmp / "leaf.pem").read_text()))
   == [f"http://127.0.0.1:{AIA_PORT}/int.der"], "адрес выдавшего сертификата (AIA) читается без сторонних библиотек")
src = {"id": "own", "name": "localhost", "base": f"https://localhost:{PORT}", "url": f"https://localhost:{PORT}/s?q={{QUERY}}"}
import httpx  # noqa: E402
try:
    httpx.get(f"https://localhost:{PORT}/", timeout=10)
    plain = "открылась"
except Exception as e:  # noqa: BLE001
    plain = str(e)
ok("CERTIFICATE_VERIFY_FAILED" in plain, f"обычный клиент — та же ошибка, что у владельца: {plain[:100]}")
try:
    page = TS.fetch(src, "видеонаблюдение")
except Exception as e:  # noqa: BLE001
    page = f"ошибка: {e}"
ok("Тендер 1" in page and "own" in TS._SSL_FIXED, f"второй заход: хранилище системы + недостающее звено по AIA — страница открылась: {page[:120]!r}")
# проверка не ослаблена: чужой сертификат (самоподписанный, без доверенного корня) — по-прежнему ошибка
sh("openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", "bad.key", "-out", "bad.pem", "-days", "3", "-subj", "/CN=localhost",
   "-addext", "subjectAltName=DNS:localhost")
bad = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Site)
bctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); bctx.load_cert_chain(tmp / "bad.pem", tmp / "bad.key")
bad.socket = bctx.wrap_socket(bad.socket, server_side=True)
threading.Thread(target=bad.serve_forever, daemon=True).start()
bsrc = {"id": "bad", "name": "bad", "base": f"https://localhost:{bad.server_port}", "url": f"https://localhost:{bad.server_port}/s?q={{QUERY}}"}
try:
    TS.fetch(bsrc, "x")
    ok(False, "самоподписанный сертификат пропущен — проверка ослаблена!")
except Exception as e:  # noqa: BLE001
    ok("CERTIFICATE_VERIFY_FAILED" in str(e), f"чужой сертификат — по-прежнему не открывается: {str(e)[:80]}")

# свои площадки — несколько
s = {"own_url": "https://a.by/search?q={QUERY}\nhttps://b.by/find?text={QUERY}&page=1  https://a.by/search?q={QUERY} nonsense"}
ow = TS.own_sites(s)
ok([x["id"] for x in ow] == ["own", "own2"] and [x["name"] for x in ow] == ["a.by", "b.by"], f"свои площадки — несколько, без повторов: {ow}")
ok([x["id"] for x in TS.sources(dict(s, goszakupki=False))] == ["icetrade", "own", "own2"], "встроенная выключена галочкой — не ищем на ней")
ui = (ROOT / "data/plugins/tenders/ui.html").read_text(encoding="utf-8")
ok('id="own-add"' in ui and "data-owndel" in ui and "withQuery" in ui and "сама заменится" not in ui and "само заменится на {QUERY}" in ui,
   "страница: добавить свою площадку адресом поиска (слово → {QUERY}), ✕ — убрать")
print("ИТОГ:", "всё прошло" if not fails else f"{len(fails)} ошибок")
sys.exit(1 if fails else 0)
