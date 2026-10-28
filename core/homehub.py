"""«Дома по Wi-Fi» — синхронизация телефона и компьютера напрямую, без dewiar.pro (0.59; владелец 28.10: «Свой сервер
в телефоне — не нужно», напрямую по домашнему Wi-Fi — «подойдёт»).

Компьютер становится маленьким узлом синхронизации: тот же обмен, что ?p=/sync в cloud.php (формат запросов и ответов
— один в один, поэтому syncRun() телефона и Sync компьютера работают с ним, как с облаком), только хранится всё здесь,
в STATE_DIR/homehub.sqlite, а слушает он домашнюю сеть (порт 8766, занят — следующий свободный).

Кто может подключиться. Телефон получает ключ, только сканируя код с экрана этого компьютера («Устройства» →
«Дома по Wi-Fi»): в коде — адреса компьютера, номер ключа и сам ключ (32 байта). Код живёт 10 минут; ключ
становится постоянным с первого обмена. Каждый запрос и ответ телефона целиком зашифрованы этим ключом (closecrypto.seal:
шифр + подпись) — соседи по Wi-Fi не прочтут и не подделают; в запросе — время (±15 минут) и одноразовый номер, повтор
перехваченного не пройдёт. Сам компьютер ходит к своему узлу по 127.0.0.1 открыто (свой ключ, только с этого компьютера).
«Отключить» телефон — его ключ удаляется; следующий его запрос — 401.

Запрос телефона: POST /sync, заголовок X-Home: <номер ключа>, тело — b64url(seal(K, JSON {ts, n, body})); ответ — тот же
вид: b64url(seal(K, JSON ответа)). Ошибка — открытым JSON {error: {message}} (в нём нет данных)."""

import json
import logging
import os
import secrets
import socket
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import closecrypto as CC

log = logging.getLogger("dewiar.homehub")

PORT = 8766
PORTS = 10                                   # занят — следующий, до 8775
PAIR_TTL = 600                               # код на экране — 10 минут
SKEW = 900                                   # время запроса — ±15 минут
MAX_BODY = 24 * 1024 * 1024
ITEM_MAX = 300_000
ITEMS_MAX = 40_000
BASE_KINDS = ("reminder", "note", "money", "memory")
EXTRA_KINDS = ("soul", "mind", "diary", "dayturn", "taskreq", "task", "vault", "done", "persona", "bill", "pay", "payfile", "pmemory")


class HubError(Exception):
    def __init__(self, code, msg):
        super().__init__(msg)
        self.code = code


def lan_addresses():
    """Адреса этого компьютера в домашней сети (192.168.*, 10.*, 172.16–31.*) — первым тот, через который идёт интернет."""
    out = []
    try:                                      # маршрут «наружу» — без отправки пакетов (UDP connect только выбирает адрес)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(("10.255.255.255", 1))
        out.append(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            if ip not in out:
                out.append(ip)
    except OSError:
        pass
    return [ip for ip in out if is_private(ip)][:4]


def is_private(ip):
    p = str(ip).split(".")
    if len(p) != 4 or not all(x.isdigit() for x in p):
        return False
    a, b = int(p[0]), int(p[1])
    return a == 10 or (a == 192 and b == 168) or (a == 172 and 16 <= b <= 31)


class HomeHub:
    def __init__(self, path, name=lambda: "Компьютер", now=time.time):
        self.path = Path(path)
        self.name = name
        self.now = now
        self._lock = threading.RLock()
        self._nonces = {}                     # номер ключа -> {одноразовый номер: время} за последние SKEW·2 секунд
        self.server = None
        self.port = 0
        self.on_change = None                 # (устройство) -> чужая правка записана: компьютеру забрать сразу
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(self.path), check_same_thread=False, isolation_level=None)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS items (kind TEXT, iid TEXT, data TEXT, updated INTEGER, deleted INTEGER, rev INTEGER, dev TEXT,
                PRIMARY KEY (kind, iid));
            CREATE INDEX IF NOT EXISTS items_rev ON items (rev);
            CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT);
            CREATE TABLE IF NOT EXISTS keys (tid TEXT PRIMARY KEY, k TEXT, name TEXT, created INTEGER, until INTEGER, seen INTEGER, dev TEXT);
        """)

    # ---------- ключи ----------

    def _meta(self, k, default=""):
        r = self.db.execute("SELECT v FROM meta WHERE k = ?", (k,)).fetchone()
        return r[0] if r else default

    def _meta_set(self, k, v):
        self.db.execute("INSERT OR REPLACE INTO meta (k, v) VALUES (?, ?)", (k, str(v)))

    def own_token(self):
        """Ключ самого компьютера (для его Sync по 127.0.0.1)."""
        with self._lock:
            t = self._meta("own")
            if not t:
                t = "hm-" + secrets.token_urlsafe(24)
                self._meta_set("own", t)
            return t

    def hub_id(self):
        with self._lock:
            h = self._meta("id")
            if not h:
                h = secrets.token_hex(6)
                self._meta_set("id", h)
            return h

    def pair_new(self):
        """Новый ключ для телефона: живёт PAIR_TTL, пока телефон не сделает первый обмен. -> {tid, k, until}."""
        with self._lock:
            now = int(self.now())
            self.db.execute("DELETE FROM keys WHERE seen = 0 AND until < ?", (now,))
            tid, k = secrets.token_hex(5), CC.b64e(os.urandom(32))
            self.db.execute("INSERT INTO keys (tid, k, name, created, until, seen, dev) VALUES (?, ?, '', ?, ?, 0, '')", (tid, k, now, now + PAIR_TTL))
            return {"tid": tid, "k": k, "until": now + PAIR_TTL}

    def pair_link(self, p):
        """Ссылка для кода на экране: dewiar://home?u=<адреса через запятую>&t=<номер>&k=<ключ>&h=<узел>&n=<имя>."""
        from urllib.parse import quote
        ips = lan_addresses()
        us = ",".join(f"http://{ip}:{self.port}/" for ip in ips)
        return (f"dewiar://home?u={quote(us, safe='')}&t={p['tid']}&k={quote(p['k'], safe='')}&h={self.hub_id()}"
                f"&n={quote(str(self.name() or 'Компьютер')[:40], safe='')}")

    def phones(self):
        rows = self.db.execute("SELECT tid, name, created, seen, dev FROM keys WHERE seen > 0 ORDER BY seen DESC").fetchall()
        return [{"tid": t, "name": n or "Телефон", "created": c, "seen": s, "dev": d} for t, n, c, s, d in rows]

    def forget(self, tid):
        with self._lock:
            self.db.execute("DELETE FROM keys WHERE tid = ?", (str(tid),))
            dev = [x for x in self._devs() if x.get("tid") != tid]
            self._meta_set("devs", json.dumps(dev, ensure_ascii=False))

    def _key(self, tid):
        r = self.db.execute("SELECT k, until, seen FROM keys WHERE tid = ?", (str(tid),)).fetchone()
        if not r:
            return None
        k, until, seen = r
        if not seen and until < self.now():
            return None
        return CC.b64d(k)

    # ---------- запрос ----------

    def open_request(self, tid, raw):
        """Тело телефона -> (запрос). Чужой ключ, испорчено, старое или повтор — HubError."""
        k = self._key(tid)
        if k is None:
            raise HubError(401, "этот телефон не подключён к компьютеру — отсканируйте код заново («Устройства» → «Дома по Wi-Fi»)")
        try:
            env = json.loads(CC.unseal(k, CC.b64d(raw)).decode("utf-8"))
        except Exception:  # noqa: BLE001
            raise HubError(401, "запрос не расшифровался — подключите телефон заново") from None
        ts, n = float(env.get("ts") or 0) / 1000, str(env.get("n") or "")
        now = self.now()
        if abs(now - ts) > SKEW:
            raise HubError(400, "часы телефона и компьютера расходятся больше чем на 15 минут — проверьте время")
        with self._lock:
            seen = self._nonces.setdefault(tid, {})
            for x in [x for x, t in seen.items() if now - t > 2 * SKEW]:
                seen.pop(x, None)
            if not n or n in seen:
                raise HubError(400, "повтор запроса")
            seen[n] = now
        return k, env.get("body") or {}

    @staticmethod
    def seal_reply(k, data):
        return CC.b64e(CC.seal(k, json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")))

    def _devs(self):
        try:
            d = json.loads(self._meta("devs", "[]"))
            return d if isinstance(d, list) else []
        except ValueError:
            return []

    def sync(self, body, tid=""):
        """Обмен — как sync_handler() в cloud.php. -> ответ (dict)."""
        body = body if isinstance(body, dict) else {}
        kinds = list(BASE_KINDS) + [k for k in EXTRA_KINDS if k in [str(x) for x in (body.get("kinds") or [])]]
        dev = "".join(ch for ch in str(body.get("device") or "") if ch.isalnum() or ch in "._:-")[:60]
        now_ms = int(self.now() * 1000)
        changes = body.get("changes") if isinstance(body.get("changes"), list) else []
        written, lost = 0, []
        with self._lock:
            db = self.db
            db.execute("BEGIN IMMEDIATE")
            try:
                rev = int(self._meta("rev", "0") or 0)
                count = None
                for c in changes[:2000]:
                    if not isinstance(c, dict):
                        continue
                    kind, iid = str(c.get("kind") or ""), str(c.get("id") or "")[:200]
                    if kind not in kinds or not iid:
                        continue
                    data = json.dumps(c.get("data") if isinstance(c.get("data"), dict) else {}, ensure_ascii=False, separators=(",", ":"))
                    if len(data.encode("utf-8")) > ITEM_MAX:
                        continue
                    upd = min(int(c.get("updated") or now_ms), now_ms + 60000)
                    cur = db.execute("SELECT updated, dev FROM items WHERE kind = ? AND iid = ?", (kind, iid)).fetchone()
                    if "prev" in c and kind in ("vault", "taskreq") and cur and int(cur[0]) != int(c.get("prev") or 0) and cur[1] != dev:
                        lost.append((kind, iid))
                        continue
                    if count is None:
                        count = db.execute("SELECT COUNT(*) FROM items").fetchone()[0]
                    if count > ITEMS_MAX:
                        break
                    if cur and int(cur[0]) > upd:
                        lost.append((kind, iid))           # здесь правка новее — она и останется, устройству вернём её
                        continue
                    deleted = 1 if c.get("deleted") else 0
                    db.execute("INSERT OR REPLACE INTO items (kind, iid, data, updated, deleted, rev, dev) VALUES (?, ?, ?, ?, ?, ?, ?)",
                               (kind, iid, "{}" if deleted else data, upd, deleted, rev + 1, dev))
                    rev += 1
                    written += 1
                    if cur is None:
                        count += 1
                devs = [d for d in self._devs() if isinstance(d, dict) and d.get("id") != dev and d.get("seen", 0) > self.now() - 90 * 86400]
                if dev:
                    app = str(body.get("app") or "")
                    devs.append({"id": dev, "name": str(body.get("name") or "")[:60], "seen": int(self.now()),
                                 "app": app if app in ("pc", "phone", "web") else ("pc" if dev.startswith("pc-") else "phone"),
                                 "ver": "".join(ch for ch in str(body.get("ver") or "") if ch.isalnum() or ch in "._-")[:20], "tid": tid})
                    if tid:
                        db.execute("UPDATE keys SET seen = ?, name = ?, dev = ? WHERE tid = ?", (int(self.now()), str(body.get("name") or "")[:60], dev, tid))
                self._meta_set("rev", rev)
                self._meta_set("devs", json.dumps(devs[-12:], ensure_ascii=False))
                db.execute("COMMIT")
            except Exception:
                db.execute("ROLLBACK")
                raise
            if written and tid and self.on_change:
                try:
                    self.on_change(dev)
                except Exception:  # noqa: BLE001
                    pass
            since = max(0, int(body.get("since") or 0))
            q = ",".join("?" * len(kinds))
            rows = db.execute(f"SELECT kind, iid, data, updated, deleted, rev, dev FROM items WHERE rev > ? AND kind IN ({q}) ORDER BY rev LIMIT 1001",
                              [since] + kinds).fetchall()
            more = len(rows) > 1000
            items = [self._item(r) for r in rows[:1000]]
            nxt = items[-1]["rev"] if more and items else rev
            for kind, iid in lost[:500]:
                r = db.execute("SELECT kind, iid, data, updated, deleted, rev, dev FROM items WHERE kind = ? AND iid = ? AND rev <= ?", (kind, iid, since)).fetchone()
                if r:
                    items.append(self._item(r))
        all_ = sorted(({"id": d["id"], "name": d.get("name", ""), "seen": d.get("seen", 0), "app": d.get("app", "phone"), "ver": d.get("ver", ""),
                        "me": d["id"] == dev} for d in devs if d.get("id")), key=lambda d: (not d["me"], -d["seen"]))
        return {"rev": nxt, "items": items, "more": more, "written": written, "kinds": kinds, "lost": [k + ":" + i for k, i in lost[:2000]],
                "space": "home", "devices": [{"name": d["name"], "seen": d["seen"], "pc": d["app"] == "pc"} for d in all_ if not d["me"]],
                "all": all_, "box": 0, "hub": {"id": self.hub_id(), "name": str(self.name() or "")[:40], "urls": [f"http://{ip}:{self.port}/" for ip in lan_addresses()]}}

    @staticmethod
    def _item(r):
        try:
            data = json.loads(r[2] or "{}")
        except ValueError:
            data = {}
        return {"kind": r[0], "id": r[1], "data": data, "updated": int(r[3]), "deleted": bool(r[4]), "rev": int(r[5]), "dev": r[6]}

    # ---------- сервер ----------

    def start(self, host="0.0.0.0", port=PORT):
        """Слушать домашнюю сеть. -> порт; занято всё — HubError."""
        if self.server:
            return self.port
        hub = self
        last = None
        for p in range(port, port + PORTS):
            try:
                srv = ThreadingHTTPServer((host, p), _handler(hub))
                break
            except OSError as e:
                last = e
        else:
            raise HubError(500, f"порт для синхронизации по Wi-Fi занят: {last}")
        srv.daemon_threads = True
        self.server, self.port = srv, srv.server_address[1]
        threading.Thread(target=srv.serve_forever, name="homehub", daemon=True).start()
        log.info("🏠 Синхронизация по Wi-Fi: слушаю порт %d (%s)", self.port, ", ".join(lan_addresses()) or "адреса в сети нет")
        return self.port

    def stop(self):
        srv, self.server = self.server, None
        if srv:
            try:
                srv.shutdown()
                srv.server_close()
            except Exception:  # noqa: BLE001
                pass

    def running(self):
        return self.server is not None


def _handler(hub):
    class H(BaseHTTPRequestHandler):
        server_version = "Dewiar"
        sys_version = ""

        def log_message(self, *a):            # без строк о каждом запросе
            pass

        def _send(self, code, body, ctype="application/json"):
            b = body.encode("utf-8") if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", ctype + "; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.send_header("Cache-Control", "no-store")
            self._cors()
            self.end_headers()
            self.wfile.write(b)

        def _cors(self):
            # страница приложения (WebView и проверки в браузере) — запрос с другого «происхождения»; ключ всё равно
            # нужен: без него узел не отдаст и не примет ничего
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Home")
            self.send_header("Access-Control-Allow-Methods", "GET, POST")

        def do_OPTIONS(self):
            self.send_response(204)
            self._cors()
            self.send_header("Content-Length", "0")
            self.end_headers()

        def _err(self, code, msg):
            self._send(code, json.dumps({"error": {"message": msg}}, ensure_ascii=False))

        def do_GET(self):                      # «жив ли узел» — без данных
            if self.path.split("?")[0] in ("/", "/hello"):
                return self._send(200, json.dumps({"dewiar": "home", "id": hub.hub_id()}))
            return self._err(404, "нет такого адреса")

        def do_POST(self):
            path = self.path.split("?")[0]
            if path != "/sync" and "p=/sync" not in self.path:
                return self._err(404, "нет такого адреса")
            n = int(self.headers.get("Content-Length") or 0)
            if n > MAX_BODY:
                return self._err(413, "слишком много за раз")
            raw = self.rfile.read(n) if n else b""
            local = self.client_address[0] in ("127.0.0.1", "::1")
            auth = self.headers.get("Authorization") or ""
            try:
                if local and auth == "Bearer " + hub.own_token():
                    body = json.loads(raw.decode("utf-8") or "{}")
                    return self._send(200, json.dumps(hub.sync(body), ensure_ascii=False))
                tid = (self.headers.get("X-Home") or "").strip()
                if not tid:
                    return self._err(401, "нужен код с экрана компьютера")
                k, body = hub.open_request(tid, raw.decode("ascii", "replace").strip())
                return self._send(200, hub.seal_reply(k, hub.sync(body, tid)), "text/plain")
            except HubError as e:
                return self._err(e.code, str(e))
            except Exception as e:  # noqa: BLE001
                log.exception("Синхронизация по Wi-Fi")
                return self._err(500, f"компьютер не смог: {type(e).__name__}")
    return H
