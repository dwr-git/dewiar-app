"""MCP-клиент (Model Context Protocol): подключает внешние инструменты.

Два транспорта:
  stdio — локальная программа (npx …, uvx …, python …), JSON-RPC построчно через stdin/stdout;
  http  — Streamable HTTP: POST JSON-RPC, ответ JSON или SSE, сессия в заголовке Mcp-Session-Id.

Настройки: settings.mcp.servers = {имя: {type, command, args, env, url, headers, enabled, trust}}; MCPManager
подключает их в фоне и переподключает при изменении настроек (reconcile).
Инструменты сервера видны модели как mcp_<сервер>_<инструмент> (не длиннее 64 знаков).
Подтверждение: спрашиваем, если инструмент не помечен readOnlyHint, пока серверу не выставлено trust. readOnlyHint
сообщает сам сервер — защита рассчитана на серверы, которые человек подключил сознательно.
"""

import itertools
import json
import logging
import os
import queue
import re
import shutil
import subprocess
import threading
from pathlib import Path

import httpx

log = logging.getLogger("dewiar.mcp")
PROTOCOL = "2025-06-18"               # предлагаем при initialize; сервер отвечает своей версией — её и шлём дальше (HTTP)
CLIENT = {"name": "dewiar", "version": "0.9"}


def plugin_expand(cfg):
    """Плагин со своим кодом (0.75; владелец 30.10: «готовые модули — тендеры, резюме — включаемыми плагинами»): в command,
    args и env сервера плагина {plugin_dir} — его папка (свои — CONFIG_DIR/plugins/<id>, встроенные — DATA_DIR/plugins/<id>),
    {python} — Python самой программы (в Windows — python.exe рядом с pythonw.exe: окно консоли не нужно, трубы — да).
    Есть папка lib/ у плагина — она первой в PYTHONPATH: библиотеки модуля едут вместе с ним."""
    pid = str(cfg.get("plugin") or "")
    text = json.dumps([cfg.get("command"), cfg.get("args"), cfg.get("env")], ensure_ascii=False)
    if not pid or ("{plugin_dir}" not in text and "{python}" not in text):
        return cfg
    # и ещё серверу плагина: DEWIAR_PLUGIN_DATA — его папка данных (рядом с настройками, переживает переустановку),
    # DEWIAR_PLUGIN_SETTINGS — его настройки из карточки плагина (JSON), ядро Dewiar — в пути модулей (knowledge.extract
    # и др.: текст из PDF и Word без своих библиотек)
    import sys
    from plugins import BUILTIN_DIR, USER_DIR
    d = next((x for x in (USER_DIR / pid, BUILTIN_DIR / pid) if re.fullmatch(r"[\w-]{1,40}", pid) and x.is_dir()), None)
    if d is None:
        raise MCPError(f"папка плагина «{pid}» не найдена — переустановите плагин")
    py = sys.executable
    if os.name == "nt" and py.lower().endswith("pythonw.exe"):
        py = py[:-len("pythonw.exe")] + "python.exe"
    sub = lambda v: str(v).replace("{plugin_dir}", str(d)).replace("{python}", py)   # noqa: E731
    env = {k: sub(v) for k, v in (cfg.get("env") or {}).items()}
    from settings import STATE_DIR
    data = STATE_DIR / "plugins-data" / pid
    data.mkdir(parents=True, exist_ok=True)
    env.setdefault("DEWIAR_PLUGIN_DATA", str(data))
    env["DEWIAR_PLUGIN_SETTINGS"] = json.dumps(cfg.get("_values") or {}, ensure_ascii=False)
    if cfg.get("_ws"):                                  # папка ассистента («Документы/Dewiar») — плагину, который сохраняет работы
        env.setdefault("DEWIAR_WORKSPACE", str(cfg["_ws"]))
    cl = cfg.get("_cloud") or {}
    if cl.get("base") and cl.get("key") and d.parent == BUILTIN_DIR:    # облако Dewiar — только встроенным плагинам
        env["DEWIAR_CLOUD_URL"], env["DEWIAR_CLOUD_KEY"] = str(cl["base"]), str(cl["key"])
    core = str(Path(__file__).resolve().parent)
    env["PYTHONPATH"] = os.pathsep.join(([str(d / "lib")] if (d / "lib").is_dir() else []) + [core]
                                        + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
    return dict(cfg, command=sub(cfg.get("command") or ""), args=[sub(a) for a in cfg.get("args") or []], env=env)


class MCPError(Exception):
    pass


_PNAMES = {}


def plugin_name(pid):
    """Имя плагина по его id («recruiter» → «Рекрутер») из plugin.json — для подписи шагов; нет плагина — ""."""
    pid = str(pid or "")
    if not pid or not re.fullmatch(r"[\w-]{1,40}", pid):
        return ""
    if pid not in _PNAMES:
        name = ""
        try:
            from plugins import BUILTIN_DIR, USER_DIR
            for d in (BUILTIN_DIR / pid, USER_DIR / pid):
                f = d / "plugin.json"
                if f.is_file():
                    name = str(json.loads(f.read_text(encoding="utf-8")).get("name") or "").strip()[:60]
                    break
        except Exception:  # noqa: BLE001
            name = ""
        _PNAMES[pid] = name
    return _PNAMES[pid]


class StdioTransport:
    """Сервер — программа на компьютере. Ответы читает отдельный поток и раздаёт ждущим по id запроса.
    stderr тоже читается постоянно (в журнал, уровень debug): иначе труба переполнится и сервер встанет."""

    def __init__(self, cfg):
        cfg = plugin_expand(cfg)
        cmd = [cfg["command"]] + list(cfg.get("args") or [])
        found = shutil.which(cmd[0])
        if not found and not os.path.exists(cmd[0]):
            raise MCPError(f"не найдена программа «{cmd[0]}» (для npx нужен Node.js, для uvx — uv)")
        if os.name == "nt" and found:
            cmd[0] = found                      # Windows: npx → C:\…\npx.cmd (без полного пути .cmd не запустится)
        env = dict(os.environ, **{k: str(v) for k, v in (cfg.get("env") or {}).items()})
        if os.name == "nt":                     # Python-серверы в Windows пишут в трубу в cp1251 — просим UTF-8
            env.setdefault("PYTHONUTF8", "1")
            env.setdefault("PYTHONIOENCODING", "utf-8")
        self.p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  env=env, text=True, bufsize=1, encoding="utf-8",
                                  creationflags=0x08000000 if os.name == "nt" else 0)   # Windows: без окна консоли
        self.waiters, self.lock = {}, threading.Lock()
        threading.Thread(target=self._read, daemon=True).start()
        threading.Thread(target=self._drain_err, daemon=True).start()

    def _drain_err(self):
        for line in self.p.stderr:
            log.debug("mcp stderr: %s", line.rstrip())

    def _read(self):
        """Поток чтения: одна строка — одно сообщение JSON-RPC; не-JSON (отладочный вывод сервера) пропускаем.
        Сервер завершился — всем ждущим ответа сразу ошибка, а не ожидание до таймаута."""
        for line in self.p.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            if "id" in msg and ("result" in msg or "error" in msg):
                q = self.waiters.pop(msg["id"], None)
                if q:
                    q.put(msg)
            elif "id" in msg and "method" in msg:          # запрос от сервера (sampling, roots…) — не поддерживаем, отказываем
                self._send({"jsonrpc": "2.0", "id": msg["id"], "error": {"code": -32601, "message": "not supported"}})
        for q in list(self.waiters.values()):
            q.put({"error": {"message": "сервер MCP завершился"}})

    def _send(self, msg):
        with self.lock:
            self.p.stdin.write(json.dumps(msg, ensure_ascii=False) + "\n")
            self.p.stdin.flush()

    def request(self, msg, timeout):
        """Отправить запрос и ждать ответ с тем же id -> сообщение JSON-RPC (с result или error)."""
        q = queue.Queue()
        self.waiters[msg["id"]] = q
        try:
            self._send(msg)
        except (BrokenPipeError, OSError) as e:
            raise MCPError("сервер MCP не отвечает") from e
        try:
            return q.get(timeout=timeout)
        except queue.Empty as e:
            self.waiters.pop(msg["id"], None)
            raise MCPError("сервер MCP не ответил вовремя") from e

    def notify(self, msg):
        self._send(msg)

    def close(self):
        try:
            self.p.terminate()
            self.p.wait(timeout=3)
        except Exception:  # noqa: BLE001
            self.p.kill()


class HttpTransport:
    """Streamable HTTP: каждый запрос — POST; ответ — JSON или поток SSE. headers из настроек (например,
    Authorization) добавляются к каждому запросу."""

    def __init__(self, cfg):
        self.url = cfg["url"]
        self.headers = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json",
                        **{k: str(v) for k, v in (cfg.get("headers") or {}).items()}}
        self.client = httpx.Client(timeout=httpx.Timeout(15, read=120), follow_redirects=True)

    def _post(self, msg, timeout):
        """-> ответ на msg или None. 202 — сервер принял уведомление без ответа. Mcp-Session-Id из ответа
        запоминаем и шлём дальше. В SSE событие — строки data: до пустой строки; до нашего ответа сервер может
        прислать другие сообщения (уведомления о ходе работы) — их пропускаем."""
        with self.client.stream("POST", self.url, json=msg, headers=self.headers, timeout=timeout) as r:
            if r.status_code == 202:
                return None
            if r.status_code >= 400:
                r.read()
                raise MCPError(f"сервер MCP ответил {r.status_code}: {r.text[:160]}")
            sid = r.headers.get("mcp-session-id")
            if sid:
                self.headers["Mcp-Session-Id"] = sid
            if "event-stream" in r.headers.get("content-type", ""):
                data = []
                lines = r.iter_lines()
                for line in itertools.chain(lines, [""]):   # пустая строка в конце: поток, оборванный без неё, —
                    if line.startswith("data:"):             # последнее событие иначе терялось
                        data.append(line[5:].strip())
                    elif not line and data:
                        obj = json.loads("\n".join(data))
                        data = []
                        if obj.get("id") == msg.get("id") and ("result" in obj or "error" in obj):
                            return obj
                return None
            r.read()
            return r.json() if r.content else None

    def request(self, msg, timeout):
        try:
            res = self._post(msg, timeout)
        except httpx.ConnectError as e:
            raise MCPError(f"сервер недоступен по адресу {self.url} — он запущен?") from e
        except httpx.TimeoutException as e:
            raise MCPError("сервер не ответил вовремя") from e
        except httpx.HTTPError as e:
            raise MCPError(f"нет связи с сервером: {e}") from e
        if res is None:
            raise MCPError("сервер MCP не прислал ответ")
        return res

    def notify(self, msg):
        # Уведомление без ответа: не дошло — не повод ронять подключение.
        try:
            self._post(msg, 10)
        except (httpx.HTTPError, MCPError):
            pass

    def close(self):
        self.client.close()


class Server:
    """Один сервер MCP: подключение (initialize → initialized → tools/list), список инструментов, вызовы.
    status: connecting | ok | error (текст — в error)."""

    def __init__(self, name, cfg):
        self.name, self.cfg = name, cfg
        self.status, self.error, self.tools, self.t = "connecting", "", [], None
        self.ids = itertools.count(1)

    def rpc(self, method, params=None, timeout=30):
        msg = {"jsonrpc": "2.0", "id": next(self.ids), "method": method}
        if params is not None:
            msg["params"] = params
        res = self.t.request(msg, timeout)
        if "error" in res:
            raise MCPError(res["error"].get("message", "ошибка MCP"))
        return res.get("result") or {}

    def connect(self):
        """Подключиться и получить инструменты (постранично, не больше 20 страниц). Исключений не бросает:
        ошибка остаётся в status/error, транспорт закрывается."""
        try:
            self.t = HttpTransport(self.cfg) if self.cfg.get("type") == "http" else StdioTransport(self.cfg)
            init = self.rpc("initialize", {"protocolVersion": PROTOCOL, "capabilities": {}, "clientInfo": CLIENT}, 60)
            if isinstance(self.t, HttpTransport):
                self.t.headers["MCP-Protocol-Version"] = init.get("protocolVersion", PROTOCOL)
            self.t.notify({"jsonrpc": "2.0", "method": "notifications/initialized"})
            tools, cursor = [], None
            for _ in range(20):
                r = self.rpc("tools/list", {"cursor": cursor} if cursor else {})
                tools += r.get("tools") or []
                cursor = r.get("nextCursor")
                if not cursor:
                    break
            self.tools = tools
            self.status, self.error = "ok", ""
            log.info("MCP «%s»: подключён, инструментов %d", self.name, len(tools))
        except Exception as e:  # noqa: BLE001
            self.status, self.error = "error", str(e)
            log.warning("MCP «%s»: %s", self.name, e)
            self.close()

    def call(self, tool, args):
        """Вызвать инструмент -> текст для модели (не больше 8000 знаков). Текст и текстовые ресурсы — как есть,
        прочее (картинки, звук) — пометкой [тип]; isError — с приставкой «Ошибка:»."""
        r = self.rpc("tools/call", {"name": tool, "arguments": args or {}}, timeout=120)
        parts = []
        for c in r.get("content") or []:
            if c.get("type") == "text":
                parts.append(c.get("text", ""))
            elif c.get("type") == "resource":
                parts.append(str((c.get("resource") or {}).get("text", "")))
            else:
                parts.append(f"[{c.get('type')}]")
        if not parts and r.get("structuredContent") is not None:
            parts.append(json.dumps(r["structuredContent"], ensure_ascii=False))
        text = "\n".join(parts)[:8000] or "(пусто)"
        return ("Ошибка: " + text) if r.get("isError") else text

    def call_raw(self, tool, args, timeout=180):
        """Вызвать инструмент для страницы плагина в студии (без модели) -> ответ сервера как есть: {content, isError,
        structuredContent}. Длинный текст не обрезается до 8000, как для модели, — страница покажет его целиком."""
        r = self.rpc("tools/call", {"name": tool, "arguments": args or {}}, timeout=timeout)
        return r if isinstance(r, dict) else {}

    def close(self):
        if self.t:
            try:
                self.t.close()
            except Exception:  # noqa: BLE001
                pass
        self.t = None


def page_only(t):
    """Действие сервера только для своей страницы плагина в студии (ui.html: список кандидатов целиком и т. п.) —
    помощнице не показывается: «_meta»: {"dewiar/page": true}."""
    return bool(((t or {}).get("_meta") or {}).get("dewiar/page"))


def _safe(s):
    """Часть имени инструмента для модели: API моделей принимают только латиницу, цифры, _ и -."""
    return re.sub(r"[^A-Za-z0-9_-]+", "_", s)


class MCPManager:
    """Все серверы из настроек. on_change() вызывается после каждого подключения — чтобы обновить список
    инструментов модели и студию."""

    def __init__(self, settings, on_change=None):
        self.s, self.on_change = settings, on_change
        self.servers = {}
        self.lock = threading.Lock()

    def reconcile(self):
        """Подключить новые, отключить удалённые/выключенные, переподключить изменённые — в фоне."""
        want = {n: c for n, c in (self.s.get("mcp", "servers") or {}).items() if c.get("enabled", True)}
        on = self.s.get("plugins", "on") or {}
        ws = ""
        if any(c.get("plugin") for c in want.values()):
            try:
                import workspace
                ws = str(self.s.get("workspace", "path") or "").strip() or str(workspace.default_dir())
            except Exception:  # noqa: BLE001
                ws = ""
        cloud = {}
        for pr in ((self.s.get("llm", "profiles") or {}).values() if any(c.get("plugin") for c in want.values()) else []):
            if isinstance(pr, dict) and pr.get("cloud") and pr.get("api_key") and pr.get("base_url"):
                cloud = {"base": pr["base_url"], "key": pr["api_key"]}   # «Художник»: картинки генератором облака Dewiar
                break
        for n, c in list(want.items()):                 # сервер плагина получает его настройки (поменяли — перезапуск)
            if c.get("plugin") and cloud and c.get("plugin") == "artist":
                c = want[n] = dict(c, _cloud=cloud)
            if c.get("plugin"):
                want[n] = dict(c, _values=dict((on.get(c["plugin"]) or {}).get("values") or {}), **({"_ws": ws} if ws else {}))
        with self.lock:
            for n in list(self.servers):
                if n not in want or self.servers[n].cfg != want[n]:
                    self.servers.pop(n).close()
            for n, c in want.items():
                if n not in self.servers:
                    srv = Server(n, dict(c))
                    self.servers[n] = srv
                    threading.Thread(target=self._connect, args=(srv,), daemon=True).start()

    def _connect(self, srv):
        srv.connect()
        if self.on_change:
            self.on_change()

    def status(self):
        with self.lock:
            return {n: {"status": s.status, "error": s.error, "tools": [t.get("name") for t in s.tools]}
                    for n, s in self.servers.items()}

    def _index(self):
        """Имя для модели -> (сервер, инструмент); только подключённые серверы."""
        out = {}
        with self.lock:
            for n, s in self.servers.items():
                if s.status != "ok":
                    continue
                for t in s.tools:
                    if page_only(t):                # действие только для страницы плагина — помощнице не показываем
                        continue
                    key = base = f"mcp_{_safe(n)}_{_safe(t['name'])}"[:64]
                    i = 2
                    while key in out:               # совпало после _safe или обрезки до 64 — иначе инструмент пропал бы
                        suf = f"_{i}"
                        key, i = base[:64 - len(suf)] + suf, i + 1
                    out[key] = (s, t)
        return out

    def specs(self):
        """Описания инструментов для модели; в описании — имя сервера, чтобы модель понимала, откуда инструмент."""
        return [{"name": k, "description": (f"[{s.name}] " + (t.get("description") or t["name"]))[:1000],
                 "parameters": t.get("inputSchema") or {"type": "object", "properties": {}}}
                for k, (s, t) in self._index().items()]

    def has(self, name):
        return name in self._index()

    def needs_confirm(self, name):
        """Спрашивать ли «Выполнить?»: нет — серверу доверяют (trust) или инструмент сам объявил, что только читает."""
        s, t = self._index()[name]
        if s.cfg.get("trust"):
            return False
        return not (t.get("annotations") or {}).get("readOnlyHint", False)

    def title(self, name):
        """Подпись шага в виджете и «Чате». Сервер плагина — по-человечески: «Плагин «Рекрутер»: разобрать резюме»
        (№463: пока плагин работает, человек должен видеть, что идёт работа и чья); остальные — «сервер: действие»."""
        s, t = self._index()[name]
        what = (t.get("annotations") or {}).get("title") or t["name"]
        pname = plugin_name(s.cfg.get("plugin"))
        if pname:
            return f"Плагин «{pname}»: {what[:1].lower() + what[1:] if what[1:2].islower() else what}"
        return f"{s.name}: {what}"

    def plugin_tools(self):
        """{id плагина: [(имя действия для модели, название)]} — только подключённые серверы плагинов."""
        out = {}
        for k, (s, t) in self._index().items():
            if s.cfg.get("plugin"):
                out.setdefault(s.cfg["plugin"], []).append((k, (t.get("annotations") or {}).get("title") or ""))
        return out

    def plugin_tool_texts(self):
        """{id плагина: [«имя название описание»]} — для слов плагина без своего words (№507, core/plugins.py)."""
        out = {}
        for _k, (s, t) in self._index().items():
            if s.cfg.get("plugin"):
                out.setdefault(s.cfg["plugin"], []).append(" ".join(str(x) for x in (
                    str(t.get("name") or "").replace("_", " "), (t.get("annotations") or {}).get("title") or "",
                    str(t.get("description") or "")[:300])))
        return out

    def plugin_errors(self):
        """{id плагина: что не так} — серверы плагинов, которые не подключились."""
        with self.lock:
            return {s.cfg["plugin"]: (s.error or "не запустился") for s in self.servers.values()
                    if s.cfg.get("plugin") and s.status == "error"}

    def call(self, name, args):
        s, t = self._index()[name]
        return s.call(t["name"], args)

    # ---- страница плагина в студии (03.11): действия напрямую, без модели ----
    def _of(self, pid):
        with self.lock:
            return [s for s in self.servers.values() if s.cfg.get("plugin") == pid]

    def plugin_info(self, pid):
        """Серверы плагина -> {state: ok | connecting | error | off, error, tools: [описание инструмента + server]}.
        off — у плагина нет серверов (навык без своего кода) или их выключили в «MCP-серверах»."""
        srvs = self._of(pid)
        if not srvs:
            return {"state": "off", "error": "", "tools": []}
        tools, errs, busy = [], [], False
        for s in srvs:
            if s.status == "ok":
                tools += [dict(t, server=s.name) for t in s.tools]
            elif s.status == "error":
                errs.append(s.error or "не запустился")
            else:
                busy = True
        state = "error" if errs and not tools else "connecting" if busy and not tools else "ok"
        return {"state": state, "error": "; ".join(errs)[:400], "tools": tools}

    def plugin_call(self, pid, tool, args, wait=40, timeout=180):
        """Вызвать инструмент СВОЕГО плагина без модели (кнопка «Выполнить» и мост ui.html) -> ответ сервера как есть.
        Ищется только среди серверов этого плагина: чужое действие отсюда не вызвать. Сервер ещё подключается — ждём."""
        import time
        end = time.time() + wait
        while True:
            srvs = self._of(pid)
            for s in srvs:
                if s.status == "ok" and any(t.get("name") == tool for t in s.tools):
                    return s.call_raw(tool, args, timeout)
            if not srvs:
                raise MCPError("у плагина нет такого действия — он не установлен или его подключение выключено")
            if not any(s.status == "connecting" for s in srvs):
                err = next((s.error for s in srvs if s.status == "error"), "")
                raise MCPError(f"плагин не запустился: {err}" if err else "у плагина нет такого действия")
            if time.time() > end:
                raise MCPError("плагин ещё запускается — попробуйте через минуту")
            time.sleep(0.2)

    def plugin_restart(self, pid):
        """«Перезапустить» на странице плагина: его серверы закрываются и подключаются заново (выключенные — включаются)."""
        servers = dict(self.s.get("mcp", "servers") or {})
        off = [n for n, c in servers.items() if c.get("plugin") == pid and not c.get("enabled", True)]
        if off:
            for n in off:
                servers[n] = dict(servers[n], enabled=True)
            self.s.update({"mcp": {"servers": servers}})
        with self.lock:
            for n in [n for n, s in self.servers.items() if s.cfg.get("plugin") == pid]:
                self.servers.pop(n).close()
        self.reconcile()

    def close(self):
        with self.lock:
            for s in self.servers.values():
                s.close()
            self.servers = {}
