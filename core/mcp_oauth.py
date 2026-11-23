"""OAuth для HTTP MCP: RFC 9728/8414, public client, authorization code + PKCE S256.

Только явный вход из студии. Loopback слушает IPv4 localhost со случайным портом; state одноразовый,
ожидание ограничено. Секреты не попадают в настройки/экспорт: отдельный атомарный файл 0600.
HTTP разрешён только для локальной разработки; удалённые серверы авторизации требуют HTTPS.
"""
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

import httpx

_LOCK = threading.RLock()
_PENDING = {}
LOGIN_TIMEOUT = 180


def _path():
    from settings import CONFIG_DIR
    return CONFIG_DIR / "mcp_tokens.json"


def _load():
    try:
        data = json.loads(_path().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as e:
        raise ValueError("OAuth: не удалось прочитать хранилище токенов") from e


def _save(data):
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".mcp_tokens-", suffix=".json", dir=p.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            if os.name != "nt":
                os.fchmod(f.fileno(), 0o600)
            json.dump(data, f, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, p)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _url(url):
    """Не принимаем userinfo, fragments и незашифрованные удалённые endpoints."""
    u = urlsplit(str(url or ""))
    if (not u.hostname or u.username or u.password or u.fragment or
            (u.scheme != "https" and not (u.scheme == "http" and u.hostname in ("127.0.0.1", "localhost", "::1")))):
        raise ValueError("OAuth: нужен HTTPS-адрес (HTTP допустим только на localhost)")
    return url


def _json(client, method, url, **kw):
    try:
        r = client.request(method, _url(url), timeout=15, follow_redirects=False, **kw)
        if not r.is_success:
            # Не включаем тело ответа: сервер может вернуть code, client_secret или токен.
            raise ValueError(f"OAuth: сервер авторизации ответил HTTP {r.status_code}")
        out = r.json()
        if not isinstance(out, dict):
            raise ValueError("OAuth: неверный ответ сервера авторизации")
        return out
    except (httpx.HTTPError, ValueError) as e:
        if isinstance(e, ValueError) and str(e).startswith("OAuth:"):
            raise
        raise ValueError("OAuth: нет связи или неверный ответ сервера авторизации") from e


def discover(url, client):
    """Сначала challenge RFC 9728; затем well-known с путём ресурса и fallback на корень."""
    _url(url)
    u = urlsplit(url)
    root = urlunsplit((u.scheme, u.netloc, "", "", ""))
    candidates = []
    try:
        with client.stream("POST", url, json={"jsonrpc": "2.0", "id": 0, "method": "initialize",
                           "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                                      "clientInfo": {"name": "dewiar", "version": "0.9"}}},
                           headers={"Accept": "application/json, text/event-stream"},
                           timeout=15, follow_redirects=False) as r:
            challenge = r.headers.get("www-authenticate", "") if r.status_code == 401 else ""
        m = re.search(r'\bresource_metadata\s*=\s*(?:"([^"\r\n]+)"|([^,\s]+))', challenge, re.I)
        if m:
            candidates.append(m.group(1) or m.group(2))
        candidates += [root + "/.well-known/oauth-protected-resource" + u.path.rstrip("/"),
                       root + "/.well-known/oauth-protected-resource"]
        pr = None
        for endpoint in dict.fromkeys(candidates):
            try:
                pr = _json(client, "GET", endpoint)
                break
            except ValueError:
                continue
        if not pr or not pr.get("resource") or not pr.get("authorization_servers"):
            raise ValueError("OAuth: MCP-сервер не публикует метаданные авторизации RFC 9728")
        resource = _url(pr["resource"])
        # Ресурс может быть корнем сайта или родительским путём MCP (RFC 9728), но не чужим
        # origin/соседним путём. Токен всё равно привязан и к точному URL подключения в нашем файле.
        ru = urlsplit(resource)
        path = ru.path.rstrip("/")
        if (ru.scheme != u.scheme or ru.netloc.lower() != u.netloc.lower() or
                not (u.path.rstrip("/") == path or u.path.startswith(path + "/")) or
                (ru.query and ru.query != u.query)):
            raise ValueError("OAuth: метаданные относятся к другому MCP-ресурсу")
        issuer = _url(pr["authorization_servers"][0])
        a = urlsplit(issuer.rstrip("/"))
        origin = urlunsplit((a.scheme, a.netloc, "", "", ""))
        metadata_urls = [origin + "/.well-known/oauth-authorization-server" + a.path,
                         origin + "/.well-known/openid-configuration" + a.path,
                         issuer.rstrip("/") + "/.well-known/openid-configuration"]
        meta = None
        for endpoint in dict.fromkeys(metadata_urls):
            try:
                meta = _json(client, "GET", endpoint)
                break
            except ValueError:
                continue
        if not meta or meta.get("issuer") != issuer:
            raise ValueError("OAuth: issuer в метаданных не совпадает с сервером авторизации")
        if "S256" not in (meta.get("code_challenge_methods_supported") or []):
            raise ValueError("OAuth: сервер не поддерживает PKCE S256")
        for key in ("authorization_endpoint", "token_endpoint"):
            _url(meta.get(key))
        return resource, meta, pr.get("scopes_supported") or []
    except httpx.HTTPError as e:
        raise ValueError("OAuth: не удалось обнаружить сервер авторизации") from e


def connected(name, url):
    # Файл заменяется атомарно; чтение статуса не ждёт сетевой refresh/login под _LOCK.
    try:
        t = _load().get(name) or {}
        return t.get("url") == url and bool(t.get("access_token") or t.get("refresh_token"))
    except ValueError:
        return False


def _tokens(response, previous=None):
    if not isinstance(response.get("access_token"), str) or not re.fullmatch(r"[A-Za-z0-9._~+/-]+=*", response["access_token"]):
        raise ValueError("OAuth: сервер не вернул корректный access_token")
    if str(response.get("token_type", "")).lower() != "bearer":
        raise ValueError("OAuth: сервер вернул неподдерживаемый тип токена")
    t = dict(previous or {}, access_token=response["access_token"])
    if response.get("refresh_token"):
        t["refresh_token"] = response["refresh_token"]
    try:
        t["expires_at"] = time.time() + max(0, float(response["expires_in"])) if "expires_in" in response else 0
    except (TypeError, ValueError, OverflowError) as e:
        raise ValueError("OAuth: неверный срок действия токена") from e
    return t


def access_token(name, url, client, rejected=""):
    # Один refresh при одновременных запросах; ротация refresh_token сохраняется атомарно.
    with _LOCK:
        data = _load()
        t = data.get(name) or {}
        if t.get("url") != url or not t.get("access_token"):
            raise ValueError("OAuth: нажмите «Войти» у MCP-сервера в студии")
        expired = bool(t.get("expires_at") and t["expires_at"] <= time.time() + 30)
        if not expired and (not rejected or rejected != t["access_token"]):
            return t["access_token"]
        if not t.get("refresh_token"):
            raise ValueError("OAuth: сессия истекла — войдите заново")
        payload = {"grant_type": "refresh_token", "refresh_token": t["refresh_token"],
                   "client_id": t["client_id"], "resource": t["resource"]}
        try:
            data[name] = _tokens(_json(client, "POST", t["token_endpoint"], data=payload), t)
        except ValueError as e:
            raise ValueError("OAuth: не удалось обновить сессию — попробуйте войти заново") from e
        _save(data)
        return data[name]["access_token"]


def cancel(name):
    with _LOCK:
        flow = _PENDING.pop(name, None)
        if flow:
            flow["cancelled"] = True
            flow["event"].set()


def forget(name):
    """Локальный выход: отменяет незавершённый вход; не обещает отзыв согласия на стороне провайдера."""
    with _LOCK:
        cancel(name)
        data = _load()
        data.pop(name, None)
        _save(data)


def begin(name, cfg, client, done):
    # Два клика не создают два ожидающих listener-а. Сетевой discovery не держит замок MCPManager.
    with _LOCK:
        if name in _PENDING:
            return {"url": _PENDING[name]["url"], "expires_in": LOGIN_TIMEOUT}
        resource, meta, scopes = discover(cfg["url"], client)
        state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(48)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")
        flow = {"event": threading.Event(), "cancelled": False, "result": None}

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass  # code/state в URL — не в журнал

            def do_GET(self):
                u = urlsplit(self.path)
                q = parse_qs(u.query)
                valid = (u.path == "/callback" and len(q.get("state", [])) == 1 and
                         hmac.compare_digest(q["state"][0], state))
                with _LOCK:
                    valid = valid and not flow["cancelled"] and not flow["event"].is_set()
                    if valid:
                        flow["result"] = q
                        flow["event"].set()
                body = ("Вход обработан. Вернитесь в Dewiar." if valid else "Неверный или истёкший запрос входа.").encode("utf-8")
                self.send_response(200 if valid else 400)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Referrer-Policy", "no-referrer")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        server.daemon_threads = True
        redirect = f"http://127.0.0.1:{server.server_port}/callback"
        try:
            client_id = str(cfg.get("client_id") or "").strip()
            if not client_id:
                if not meta.get("registration_endpoint"):
                    raise ValueError("OAuth: сервер не поддерживает регистрацию клиента — укажите Client ID")
                reg = _json(client, "POST", meta["registration_endpoint"], json={
                    "client_name": "Dewiar", "redirect_uris": [redirect], "token_endpoint_auth_method": "none",
                    "grant_types": ["authorization_code", "refresh_token"], "response_types": ["code"]})
                client_id = reg.get("client_id")
                if not isinstance(client_id, str) or not client_id or reg.get("token_endpoint_auth_method", "none") != "none":
                    raise ValueError("OAuth: сервер не зарегистрировал публичного клиента (auth method none)")
            payload = {"response_type": "code", "client_id": client_id, "redirect_uri": redirect,
                       "state": state, "code_challenge": challenge, "code_challenge_method": "S256", "resource": resource}
            scope = str(cfg.get("scope") or " ".join(scopes))
            if scope:
                payload["scope"] = scope
            endpoint = meta["authorization_endpoint"]
            flow["url"] = endpoint + ("&" if "?" in endpoint else "?") + urlencode(payload)
            _PENDING[name] = flow
        except Exception:
            server.server_close()
            raise

    def wait():
        error = ""
        listener = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.1}, daemon=True)
        listener.start()
        try:
            if not flow["event"].wait(LOGIN_TIMEOUT):
                raise ValueError("OAuth: время входа истекло — нажмите «Войти» ещё раз")
            if flow["cancelled"]:
                return
            q = flow["result"] or {}
            if q.get("iss") and q["iss"] != [meta["issuer"]]:
                raise ValueError("OAuth: issuer в ответе авторизации не совпадает")
            if q.get("error"):
                raise ValueError("OAuth: вход отменён или доступ не предоставлен")
            if len(q.get("code", [])) != 1:
                raise ValueError("OAuth: сервер не вернул код авторизации")
            response = _json(client, "POST", meta["token_endpoint"], data={
                "grant_type": "authorization_code", "code": q["code"][0], "code_verifier": verifier,
                "client_id": client_id, "redirect_uri": redirect, "resource": resource})
            token = _tokens(response, {"url": cfg["url"], "resource": resource, "client_id": client_id,
                                      "token_endpoint": meta["token_endpoint"], "issuer": meta["issuer"]})
            with _LOCK:
                if flow["cancelled"] or _PENDING.get(name) is not flow:
                    return
                data = _load()
                data[name] = token
                _save(data)
        except Exception as e:  # callback не должен уронить процесс; секретные ответы наружу не отдаём
            error = str(e) if isinstance(e, ValueError) and str(e).startswith("OAuth:") else "OAuth: не удалось завершить вход"
        finally:
            server.shutdown()
            server.server_close()
            with _LOCK:
                if _PENDING.get(name) is flow:
                    _PENDING.pop(name, None)
            if not flow["cancelled"]:
                done(error)

    threading.Thread(target=wait, name="mcp-oauth", daemon=True).start()
    return {"url": flow["url"], "expires_in": LOGIN_TIMEOUT}
