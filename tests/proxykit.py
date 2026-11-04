"""Стенд для проверок прокси: свой «dewiar.pro» по HTTPS (сертификат от тестового центра), SOCKS5 с логином anna/s3cret,
HTTP-прокси с CONNECT. Прокси «видят» интернет так: dewiar.pro, cdn.dewiar.pro, my.site.test → наш сайт; остальное — как есть.
    kit = start(tmp)  → kit.TLS, kit.PLAIN, kit.SP, kit.HP, kit.DEAD, kit.SEEN, kit.CA (путь к корневому сертификату)"""
import json, os, select, socket, ssl, struct, subprocess, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from socketserver import StreamRequestHandler, ThreadingTCPServer
from types import SimpleNamespace


def start(tmp):
    # --- сертификаты: свой центр и «dewiar.pro» ---
    sh = lambda *a: subprocess.run(a, cwd=tmp, check=True, capture_output=True)
    # расширения — как у настоящих центров: Python 3.13 проверяет сертификаты строго (VERIFY_X509_STRICT) и без keyUsage
    # у центра и authorityKeyIdentifier у сайта отвергает их («CA cert does not include key usage extension»)
    sh("openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", "ca.key", "-out", "ca.pem", "-days", "2", "-subj", "/CN=Dewiar Test CA",
       "-addext", "basicConstraints=critical,CA:TRUE", "-addext", "keyUsage=critical,keyCertSign,cRLSign", "-addext", "subjectKeyIdentifier=hash")
    (tmp / "ext.cnf").write_text("subjectAltName=DNS:dewiar.pro,DNS:*.dewiar.pro,DNS:my.site.test\nbasicConstraints=CA:FALSE\n"
                                 "keyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\n"
                                 "subjectKeyIdentifier=hash\nauthorityKeyIdentifier=keyid,issuer\n")
    sh("openssl", "req", "-newkey", "rsa:2048", "-nodes", "-keyout", "site.key", "-out", "site.csr", "-subj", "/CN=dewiar.pro")
    sh("openssl", "x509", "-req", "-in", "site.csr", "-CA", "ca.pem", "-CAkey", "ca.key", "-CAcreateserial", "-out", "site.pem", "-days", "2", "-extfile", "ext.cnf")
    SEEN = {"site": [], "socks": 0, "http": 0}


    class Site(BaseHTTPRequestHandler):
        """Сайт Dewiar: обновления и вход для приложения."""
        def log_message(self, *a): pass

        def _out(self, code, obj):
            b = json.dumps(obj, ensure_ascii=False).encode()
            self.send_response(code); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b)))
            self.end_headers(); self.wfile.write(b)

        def do_GET(self):
            SEEN["site"].append(self.headers.get("Host", "") + self.path)
            if self.path.startswith("/dwrapp/latest.json"):
                return self._out(200, {"name": "Dewiar", "version": "0.0.1", "deb": "x.deb", "sha256": "0" * 64, "size": 1, "notes": "", "mirrors": {}})
            if self.path.startswith("/dwrapp/login.php"):
                ok_ = self.headers.get("Authorization") == "Bearer tok-123"
                return self._out(200 if ok_ else 401, {"ok": ok_, "user": {"login": "anna"}, "rag_url": "/synapbase/api_rag", "services": {}})
            return self._out(404, {"error": "нет"})

        def do_POST(self):
            n = int(self.headers.get("Content-Length") or 0); body = json.loads(self.rfile.read(n) or b"{}")
            SEEN["site"].append(self.headers.get("Host", "") + self.path)
            if self.path.startswith("/dwrapp/login.php"):
                if (body.get("login"), body.get("password")) == ("anna", "pw"):
                    return self._out(200, {"ok": True, "token": "tok-123", "user": {"login": "anna"}, "rag_url": "/synapbase/api_rag", "services": {}})
                return self._out(401, {"ok": False, "error": "Неверный логин или пароль."})
            return self._out(404, {"error": "нет"})


    def pipe(a, b):
        try:
            while True:
                r, _, _ = select.select([a, b], [], [], 30)
                if not r:
                    return
                for s in r:
                    d = s.recv(65536)
                    if not d:
                        return
                    (b if s is a else a).sendall(d)
        except OSError:
            return


    def target(host, port):
        """Прокси «видит» интернет: адреса Dewiar → наш сайт; остальное — как есть (127.0.0.1)."""
        if host in ("dewiar.pro", "cdn.dewiar.pro", "my.site.test"):
            return ("127.0.0.1", TLS if port == 443 else PLAIN)
        return (host, port)


    class Socks(StreamRequestHandler):
        def handle(self):
            c = self.connection
            ver, n = c.recv(2); methods = c.recv(n)
            if 2 not in methods:
                c.sendall(b"\x05\xff"); return
            c.sendall(b"\x05\x02")
            c.recv(1); ul = c.recv(1)[0]; user = c.recv(ul); pl = c.recv(1)[0]; pw = c.recv(pl)
            if (user, pw) != (b"anna", b"s3cret"):
                c.sendall(b"\x01\x01"); return
            c.sendall(b"\x01\x00")
            ver, cmd, _, atyp = c.recv(4)
            host = socket.inet_ntoa(c.recv(4)) if atyp == 1 else c.recv(c.recv(1)[0]).decode() if atyp == 3 else None
            port = struct.unpack(">H", c.recv(2))[0]
            SEEN["socks"] += 1
            up = socket.create_connection(target(host, port))
            c.sendall(b"\x05\x00\x00\x01" + socket.inet_aton("127.0.0.1") + struct.pack(">H", port))
            pipe(c, up)


    class HttpProxy(StreamRequestHandler):
        """HTTP-прокси: CONNECT (https) и запросы с полным адресом (http)."""
        def handle(self):
            method, url, ver = self.rfile.readline().decode().split()
            hdrs = []
            while True:
                h = self.rfile.readline()
                if h in (b"\r\n", b"\n", b""):
                    break
                hdrs.append(h)
            SEEN["http"] += 1
            if getattr(self.server, "need_auth", None):        # платный прокси: без логина сразу рвёт связь (без 407)
                import base64
                want = b"basic " + base64.b64encode(self.server.need_auth.encode()).lower()
                if not any(h.lower().startswith(b"proxy-authorization:") and h.split(b":", 1)[1].strip().lower() == want for h in hdrs):
                    SEEN["http_noauth"] = SEEN.get("http_noauth", 0) + 1
                    return
            if getattr(self.server, "flaky", 0):                # «не с первого раза»: из каждых flaky+1 соединений проходит одно
                self.server.n = getattr(self.server, "n", 0) + 1
                if self.server.n % (self.server.flaky + 1):
                    SEEN["http_502"] = SEEN.get("http_502", 0) + 1
                    self.connection.sendall(b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\n\r\n")
                    return
            if method == "CONNECT":
                host, port = url.rsplit(":", 1)
                up = socket.create_connection(target(host, int(port)))
                self.connection.sendall(b"HTTP/1.1 200 Connection established\r\n\r\n")
                return pipe(self.connection, up)
            from urllib.parse import urlsplit
            u = urlsplit(url)
            up = socket.create_connection(target(u.hostname, u.port or 80))
            n = next((int(h.split(b":", 1)[1]) for h in hdrs if h.lower().startswith(b"content-length:")), 0)
            up.sendall(f"{method} {u.path or '/'}{'?' + u.query if u.query else ''} {ver}\r\n".encode() + b"".join(hdrs) + b"\r\n" + (self.rfile.read(n) if n else b""))
            pipe(self.connection, up)


    ThreadingTCPServer.allow_reuse_address = True
    ThreadingTCPServer.daemon_threads = True
    ThreadingTCPServer.handle_error = lambda *a: None


    def serve(srv):
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        return srv.server_address[1]


    tls_srv = ThreadingHTTPServer(("127.0.0.1", 0), Site)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); ctx.load_cert_chain(tmp / "site.pem", tmp / "site.key")
    tls_srv.socket = ctx.wrap_socket(tls_srv.socket, server_side=True)
    TLS = serve(tls_srv)
    PLAIN = serve(ThreadingHTTPServer(("127.0.0.1", 0), Site))
    SP = serve(ThreadingTCPServer(("127.0.0.1", 0), Socks))
    HP = serve(ThreadingTCPServer(("127.0.0.1", 0), HttpProxy))
    hpa = ThreadingTCPServer(("127.0.0.1", 0), HttpProxy); hpa.need_auth = "user1:pa ss"
    HPA = serve(hpa)                                       # HTTP-прокси с логином user1 и паролем «pa ss»
    hpf = ThreadingTCPServer(("127.0.0.1", 0), HttpProxy); hpf.flaky = 2
    HPF = serve(hpf)                                       # HTTP-прокси, который 2 раза из 3 отвечает «502 Bad Gateway»
    DEAD = (lambda s: (s.bind(("127.0.0.1", 0)), s.getsockname()[1], s.close())[1])(socket.socket())
    return SimpleNamespace(TLS=TLS, PLAIN=PLAIN, SP=SP, HP=HP, HPA=HPA, HPF=HPF, DEAD=DEAD, SEEN=SEEN, CA=str(tmp / "ca.pem"))
