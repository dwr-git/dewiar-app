"""MCP OAuth: локальные AS + ресурс, PKCE/state, DCR, refresh, выход; без внешней сети и браузера."""
import base64
import hashlib
import json
import os
import stat
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

ROOT = Path(__file__).resolve().parent.parent
TMP = Path(tempfile.mkdtemp())
os.environ["DEWIAR_CONFIG_DIR"] = str(TMP / "cfg")
os.environ["DEWIAR_STATE_DIR"] = str(TMP / "state")
sys.path.insert(0, str(ROOT / "core"))
import mcp as M
import mcp_oauth as O
from settings import Settings
from backup import scrub

fails = []
def ok(cond, text):
    print("✅" if cond else "❌", text)
    if not cond:
        fails.append(text)


def until(fn, timeout=6):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if fn():
            return True
        time.sleep(0.02)
    return False


STATE = {"access": "access-1", "refresh": "refresh-1", "refreshes": 0, "registrations": 0,
         "codes": {}, "deny_refresh": False, "reject_access": False, "bad_issuer": False, "pkce": ["S256"], "dcr": True}
BASE = ""
TOOLS = [{"name": "echo", "description": "Повторить", "inputSchema": {"type": "object"},
          "annotations": {"readOnlyHint": True}}]


def handle(msg):  # Самостоятельный fixture: mcp_test_server.py читает stdin уже при импорте.
    i, method = msg.get("id"), msg.get("method")
    if i is None:
        return None
    if method == "initialize":
        result = {"protocolVersion": msg["params"]["protocolVersion"], "capabilities": {"tools": {}},
                  "serverInfo": {"name": "oauth-test", "version": "1"}}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    else:
        result = {"content": [{"type": "text", "text": "эхо: " + msg["params"]["arguments"]["text"]}]}
    return {"jsonrpc": "2.0", "id": i, "result": result}


class H(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, data, status=200, **headers):
        b = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        for k, v in headers.items():
            self.send_header(k.replace("_", "-"), v)
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        p = urlsplit(self.path)
        if p.path == "/.well-known/oauth-protected-resource/mcp":
            self.send({"resource": STATE.get("resource", BASE + "/mcp"), "authorization_servers": [BASE], "scopes_supported": ["tools"]})
        elif p.path == "/.well-known/oauth-authorization-server":
            meta = {"issuer": BASE + ("/wrong" if STATE["bad_issuer"] else ""),
                    "authorization_endpoint": BASE + "/authorize", "token_endpoint": BASE + "/token",
                    "code_challenge_methods_supported": STATE["pkce"]}
            if STATE["dcr"]:
                meta["registration_endpoint"] = BASE + "/register"
            self.send(meta)
        elif p.path == "/authorize":
            q = parse_qs(p.query)
            code = "code-" + str(len(STATE["codes"]) + 1)
            STATE["codes"][code] = q
            self.send({}, 302, Location=q["redirect_uri"][0] + "?" + urlencode({"code": code, "state": q["state"][0]}))
        else:
            self.send({}, 404)

    def do_POST(self):
        b = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        if self.path == "/register":
            q = json.loads(b)
            STATE["registrations"] += 1
            STATE["registration"] = q
            self.send({"client_id": "dewiar-test", "token_endpoint_auth_method": "none"})
        elif self.path == "/token":
            q = {k: v[0] for k, v in parse_qs(b.decode()).items()}
            if q.get("grant_type") == "authorization_code":
                auth = STATE["codes"].pop(q.get("code", ""), {})
                challenge = base64.urlsafe_b64encode(hashlib.sha256(q.get("code_verifier", "").encode()).digest()).rstrip(b"=").decode()
                valid = (auth.get("code_challenge") == [challenge] and auth.get("code_challenge_method") == ["S256"] and
                         auth.get("redirect_uri") == [q.get("redirect_uri")] and q.get("resource") == BASE + "/mcp")
                STATE["pkce_verified"] = valid
                if not valid:
                    self.send({"error": "invalid_grant"}, 400)
                    return
            else:
                if STATE["deny_refresh"] or q.get("refresh_token") != STATE["refresh"] or q.get("resource") != BASE + "/mcp":
                    self.send({"error": "invalid_grant", "secret": "must-not-leak"}, 400)
                    return
                STATE["refreshes"] += 1
                STATE["access"] = "access-" + str(STATE["refreshes"] + 1)
                STATE["refresh"] = "refresh-" + str(STATE["refreshes"] + 1)
            self.send({"access_token": STATE["access"], "refresh_token": STATE["refresh"], "token_type": "Bearer", "expires_in": 3600})
        elif self.path == "/mcp":
            if STATE["reject_access"] or self.headers.get("Authorization") != "Bearer " + STATE["access"]:
                self.send({}, 401, WWW_Authenticate=f'Bearer resource_metadata="{BASE}/.well-known/oauth-protected-resource/mcp"')
                return
            STATE["last_auth"] = self.headers.get("Authorization")
            result = handle(json.loads(b))
            self.send(result, 202 if result is None else 200)
        else:
            self.send({}, 404)


server = ThreadingHTTPServer(("127.0.0.1", 0), H)
BASE = f"http://127.0.0.1:{server.server_port}"
threading.Thread(target=server.serve_forever, daemon=True).start()
client = M._http()
s = Settings()
cfg = {"type": "http", "url": BASE + "/mcp", "auth": "oauth", "headers": {"authorization": "Bearer stale-static"}}
s.update({"mcp": {"servers": {"agent": cfg}}})
events = []
m = M.MCPManager(s, on_oauth=lambda **event: events.append(event))


def browser(url):
    # Следуем только redirect до localhost callback; никакой реальный браузер не нужен.
    r = client.get(url, follow_redirects=False)
    return client.get(r.headers["location"], follow_redirects=False)


def expect_error(fn, part):
    try:
        fn()
    except (ValueError, M.MCPError) as e:
        return part in str(e) and "must-not-leak" not in str(e)
    return False


try:
    m.reconcile()
    ok(until(lambda: m.status()["agent"]["status"] == "error"), "без входа MCP просит авторизацию, не открывая браузер сам")
    r = m.oauth("agent")
    q = parse_qs(urlsplit(r["url"]).query)
    ok(q["code_challenge_method"] == ["S256"] and len(q["code_challenge"][0]) == 43 and
       q["resource"] == [BASE + "/mcp"] and q["scope"] == ["tools"], "authorization URL: PKCE S256, resource, scope")
    ok(STATE["registration"]["token_endpoint_auth_method"] == "none" and
       STATE["registration"]["redirect_uris"] == q["redirect_uri"], "DCR регистрирует публичного клиента с loopback redirect")
    ok(m.oauth("agent")["url"] == r["url"] and STATE["registrations"] == 1, "повторный клик использует тот же незавершённый вход")
    callback = q["redirect_uri"][0]
    bad = client.get(callback + "?" + urlencode({"state": "wrong", "code": "attacker"}))
    ok(bad.status_code == 400 and not O.connected("agent", cfg["url"]), "неверный state не сохраняет токены и не отменяет настоящий вход")
    ok(browser(r["url"]).status_code == 200, "loopback принимает корректный возврат браузера")
    ok(until(lambda: m.status()["agent"]["status"] == "ok") and STATE.get("pkce_verified"), "code обменивается с verifier, MCP переподключается")
    ok(until(lambda: bool(events)) and not events[-1]["error"], "студия получает событие о завершении входа")
    ok(m.call("mcp_agent_echo", {"text": "OAuth"}) == "эхо: OAuth" and
       STATE["last_auth"] == "Bearer access-1", "инструмент вызывается с OAuth Bearer вместо статического заголовка")
    path = O._path()
    ok(path.exists() and (os.name == "nt" or stat.S_IMODE(path.stat().st_mode) == 0o600), "токены записаны отдельным файлом 0600")
    data = json.loads(path.read_text())
    ok("access-1" not in json.dumps(s.snapshot()) and "refresh-1" not in json.dumps(s.snapshot()) and
       "access-1" not in json.dumps(m.status()), "OAuth-токенов нет в настройках и статусе")
    restored = M.MCPManager(s)
    restored.reconcile()
    ok(until(lambda: restored.status()["agent"]["status"] == "ok"), "новый менеджер подхватывает сохранённую сессию с диска")
    restored.close()
    ok("access-1" not in json.dumps(scrub(data)) and "refresh-1" not in json.dumps(scrub(data)), "резервная копия без пароля очищает OAuth-токены")
    ok(not O.connected("agent", BASE + "/other") and expect_error(
        lambda: O.access_token("agent", BASE + "/other", client), "Войти"), "токены привязаны к URL ресурса")
    a = M.HttpTransport({"url": BASE + "/mcp"})
    b = M.HttpTransport({"url": BASE + "/mcp"})
    a.close()
    ok(a.client is b.client is client and not b.client.is_closed, "общий HTTP-пул не закрывается при отключении одного сервера")
    idx = m._index()
    ok(m._index() is idx and m.has("mcp_agent_echo"), "индекс инструментов повторно используется")
    srv = m.servers["agent"]
    srv.status = "error"
    ok(not m.has("mcp_agent_echo"), "кэш индекса инвалидируется при изменении статуса")
    srv.status = "ok"
    srv.tools = [dict(TOOLS[0], name="new")]
    ok(m.has("mcp_agent_new") and not m.has("mcp_agent_echo"), "замена списка той же длины обновляет индекс")
    srv.tools = TOOLS
    # Expiry + concurrent refresh: один сетевой refresh, остальные читают новый токен.
    with O._LOCK:
        data = O._load()
        data["agent"]["expires_at"] = time.time() - 5
        O._save(data)
    with ThreadPoolExecutor(max_workers=4) as pool:
        tokens = list(pool.map(lambda _: O.access_token("agent", cfg["url"], client), range(4)))
    ok(tokens == ["access-2"] * 4 and STATE["refreshes"] == 1 and O._load()["agent"]["refresh_token"] == "refresh-2", "истёкший токен обновляется один раз, ротация refresh сохраняется")
    STATE["access"] = "server-invalidated-token"
    ok(m.call("mcp_agent_echo", {"text": "401"}) == "эхо: 401" and STATE["refreshes"] == 2, "401 вызывает один refresh и повтор запроса")
    STATE["reject_access"] = True
    before = STATE["refreshes"]
    ok(expect_error(lambda: m.call("mcp_agent_echo", {"text": "forbidden"}), "доступ отклонён") and
       STATE["refreshes"] == before + 1, "повторный 401 не зацикливает refresh")
    STATE["reject_access"] = False
    STATE["access"] = "invalid-again"
    STATE["deny_refresh"] = True
    ok(expect_error(lambda: m.call("mcp_agent_echo", {"text": "no"}), "войти заново"), "неуспешный refresh даёт понятную ошибку без утечки ответа AS")
    STATE["deny_refresh"] = False
    m.oauth("agent", forget=True)
    ok(not O.connected("agent", cfg["url"]) and "agent" not in O._load(), "«Выйти» удаляет токены, MCP больше не авторизован")
    ok(until(lambda: m.status()["agent"]["status"] == "error"), "после выхода сервер недоступен модели")
    ok(expect_error(lambda: m.oauth("unknown"), "Выберите"), "неизвестный сервер отклоняется")
    for url in ("http://example.com/mcp", "https://user:pass@example.com/mcp", "https://example.com/mcp#token"):
        ok(expect_error(lambda: O._url(url), "HTTPS"), "небезопасный URL отклонён: " + url.split("#")[0])
    STATE["resource"] = BASE
    ok(O.discover(cfg["url"], client)[0] == BASE, "resource identifier может быть корнем того же origin")
    for resource in ("https://other.example/mcp", BASE + "/other", BASE + "/mc"):
        STATE["resource"] = resource
        ok(expect_error(lambda: O.discover(cfg["url"], client), "другому MCP-ресурсу"), "метаданные чужого origin или соседнего пути отклонены")
    STATE.pop("resource")
    STATE["bad_issuer"] = True
    ok(expect_error(lambda: m.oauth("agent"), "issuer"), "подмена issuer отклоняется")
    STATE["bad_issuer"] = False
    STATE["pkce"] = ["plain"]
    ok(expect_error(lambda: m.oauth("agent"), "S256"), "откат с S256 на plain запрещён")
    STATE["pkce"] = ["S256"]
    STATE["dcr"] = False
    ok(expect_error(lambda: m.oauth("agent"), "Client ID"), "без DCR запрашивается выданный провайдером Client ID")
    done = []
    r = O.begin("manual", dict(cfg, client_id="manual-client"), client, done.append)
    q = parse_qs(urlsplit(r["url"]).query)
    ok(q["client_id"] == ["manual-client"], "предварительно зарегистрированный Client ID поддерживается")
    client.get(q["redirect_uri"][0] + "?" + urlencode({"state": q["state"][0], "error": "access_denied"}))
    ok(until(lambda: bool(done)) and "отменён" in done[0] and not O.connected("manual", cfg["url"]), "отказ пользователя завершает вход без токенов")
    O.LOGIN_TIMEOUT = 0.1
    done = []
    O.begin("timeout", dict(cfg, client_id="manual-client"), client, done.append)
    ok(until(lambda: bool(done)) and "истекло" in done[0], "loopback закрывается по таймауту")
    O.LOGIN_TIMEOUT = 180
    r = O.begin("cancelled", dict(cfg, client_id="manual-client"), client, lambda _: fails.append("callback после отмены"))
    O.forget("cancelled")
    ok(until(lambda: "cancelled" not in O._PENDING) and not O.connected("cancelled", cfg["url"]), "выход отменяет незавершённый вход")

    # Ни reconcile, ни restart/close не удерживают lock во время медленного закрытия транспорта.
    class Slow:
        name = "slow"
        cfg = {"plugin": "p"}
        tools = []
        status, error = "ok", ""
        def close(self):
            acquired = manager.lock.acquire(timeout=0.2)
            ok(acquired, "close транспорта выполняется вне lock менеджера")
            if acquired:
                manager.lock.release()
    manager = M.MCPManager(Settings(TMP / "empty.json"))
    manager.servers = {"slow": Slow()}
    manager.reconcile()
    manager.servers = {"slow": Slow()}
    manager.plugin_restart("p")
    manager.servers = {"slow": Slow()}
    manager.close()
    source = (ROOT / "core/engine_commands.py").read_text()
    ok('"mcp_oauth"' in source.split("def _kids_blocked")[0], "OAuth-команды закрыты детским режимом")
finally:
    m.close()
    for name in list(O._PENDING):
        O.cancel(name)
    server.shutdown()
    server.server_close()

print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
