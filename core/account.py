"""Аккаунт сайта Dewiar: вход логином и паролем, вопросы к Знаниям пользователя.

Сервер (см. server/dwrapp/login.php):
  POST {сервер}/dwrapp/login.php  {"login", "password"}  → {"ok", "token", "user", "rag_url", "services"}
  GET  {сервер}/dwrapp/login.php  (Bearer)              → {"ok", "user", "rag_url", "services"} — токен ещё действует?
services — адреса сервисов сайта для этого входа (stt, tts, tg, cloud, rag). Знания — api_rag (Bearer = api_token
пользователя), ответ в формате chat.completion + rag_meta; список баз — api_scope рядом с ним.

Храним в ~/.config/dewiar/account.json (%APPDATA%\\Dewiar на Windows, права 0600) только адрес, логин и токен;
пароль не сохраняется. Токен в студию не отдаётся. Если dewiar.pro блокирует провайдер — запросы идут через прокси net.py.
"""

import ipaddress
import json
import re
import logging
import os
import threading
import time
from urllib.parse import urlparse

import httpx

from settings import CONFIG_DIR

log = logging.getLogger("dewiar.account")
PATH = CONFIG_DIR / "account.json"
DEFAULT_SERVER = "https://dewiar.pro"


APP_ID = "dewiar-app"                  # заголовок X-App-Id и _sid: какое приложение обращается к сайту


def _blocked():
    """Добавка к ошибке «сайт не отвечает»: что делать, если сайт блокирует провайдер (net.blocked_hint)."""
    from net import blocked_hint
    return blocked_hint()


class AccountError(Exception):
    pass


def _check_server(url):
    """Адрес сайта -> нормальный вид (пусто — dewiar.pro, без схемы — https://).
    https — всегда; http — только для своей сети (127.0.0.1, 10.x, 192.168.x, .local, .lan), иначе пароль ушёл бы открытым."""
    url = (url or "").strip().rstrip("/")
    if not url:
        url = DEFAULT_SERVER
    if "://" not in url:
        url = "https://" + url
    u = urlparse(url)
    if u.scheme not in ("http", "https") or not u.hostname:
        raise AccountError("это не похоже на адрес сайта")
    if u.scheme == "http":
        host = u.hostname
        try:
            local = ipaddress.ip_address(host).is_private or ipaddress.ip_address(host).is_loopback
        except ValueError:
            local = host == "localhost" or host.endswith(".local") or host.endswith(".lan")
        if not local:
            raise AccountError("для входа нужен адрес с https:// — иначе пароль ушёл бы открытым")
    return url


def _err(r):
    """Текст ошибки для человека: поле error из ответа сайта, иначе по коду ответа (429 — защита login.php от перебора)."""
    try:
        e = r.json().get("error")
    except ValueError:
        e = None
    if e:
        return str(e)
    return {401: "неверный логин или пароль", 403: "доступ запрещён", 404: "на сервере нет входа для приложения (dwrapp/login.php)",
            429: "слишком много попыток — подождите 15 минут"}.get(r.status_code, f"сервер ответил {r.status_code}")


def _sources(meta, limit=6):
    """Названия документов из rag_meta -> не больше limit. Строгого формата у rag_meta нет, поэтому обходим его
    целиком (до глубины 6) и берём первое похожее на название поле каждого словаря."""
    out, seen = [], set()

    def walk(x, depth=0):
        if depth > 6 or len(out) >= limit:
            return
        if isinstance(x, dict):
            name = next((x[k] for k in ("title", "doc_name", "document", "filename", "file_name", "name", "source")
                         if isinstance(x.get(k), str) and x.get(k).strip()), None)
            if name and name not in seen and len(name) < 200:
                seen.add(name)
                out.append(name.strip())
            for v in x.values():
                walk(v, depth + 1)
        elif isinstance(x, list):
            for v in x:
                walk(v, depth + 1)
    walk(meta)
    return out


class Account:
    """Вход в аккаунт сайта и запросы от его имени (Знания). Используется и другими модулями: token() и
    service_url() — для облака, речи на сервере и общего Telegram-бота."""

    def __init__(self, path=PATH):
        self.path = path
        self._lock = threading.Lock()
        self.data = self._load()

    def _load(self):
        try:
            d = json.loads(self.path.read_text(encoding="utf-8"))
            return d if isinstance(d, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        tmp.replace(self.path)

    # ---------- состояние ----------

    def logged_in(self):
        return bool(self.data.get("token"))

    def status(self):
        """Для студии — без токена; адрес Знаний (rag) тоже не показываем — он нужен только внутри."""
        d = self.data
        return {"logged_in": self.logged_in(), "server": d.get("server") or DEFAULT_SERVER, "login": d.get("login", ""),
                "user": d.get("user") or {}, "since": d.get("since"), "problem": d.get("problem", ""),
                "services": {k: v for k, v in (d.get("services") or {}).items() if k != "rag"} if self.logged_in() else {}}

    def service_url(self, name):
        """Полный адрес сервиса сайта (stt, tts, tg, cloud) или "" — если не вошли или сайт его не предлагает."""
        u = (self.data.get("services") or {}).get(name) or ""
        if not u or not self.logged_in():
            return ""
        return u if u.startswith("http") else (self.data.get("server") or DEFAULT_SERVER) + "/" + u.lstrip("/")

    def token(self):
        return self.data.get("token", "")

    def _rag_url(self):
        server, rag = self.data.get("server") or DEFAULT_SERVER, self.data.get("rag_url") or "/synapbase/api_rag"
        return rag if rag.startswith("http") else server + "/" + rag.lstrip("/")

    # ---------- вход и выход ----------

    def login(self, server, login, password):
        """Войти -> status(). Пароль уходит только в этот запрос и нигде не сохраняется.
        Без перенаправлений: иначе пароль мог бы уйти по чужому адресу."""
        server = _check_server(server)
        login = (login or "").strip()
        if not login or not password:
            raise AccountError("введите логин и пароль")
        try:
            r = httpx.post(server + "/dwrapp/login.php", json={"login": login, "password": password},
                           headers={"X-App-Id": APP_ID}, timeout=20, follow_redirects=False)
        except httpx.HTTPError as e:
            raise AccountError(f"сайт не отвечает: {e}.{_blocked()}") from e
        if r.status_code != 200:
            raise AccountError(_err(r))
        try:
            d = r.json()
        except ValueError as e:
            raise AccountError("сайт ответил не тем (нет входа для приложения?)") from e
        if not d.get("ok") or not d.get("token"):
            raise AccountError(d.get("error") or "вход не удался")
        with self._lock:
            self.data = {"server": server, "login": login, "token": d["token"], "user": d.get("user") or {},
                         "rag_url": d.get("rag_url") or "/synapbase/api_rag", "since": int(time.time()),
                         "services": d.get("services") or {}}
            self._save()
        log.info("Вход в аккаунт %s на %s", login, server)
        return self.status()

    def adopt(self, server, token):
        """Вход тем же аккаунтом, что на другом устройстве, — по коду «Подключить устройство» (0.56), без пароля: токен
        пришёл с сайта по одноразовому коду. Проверяем его тем же запросом, что check(). -> status()"""
        server = _check_server(server)
        if not token:
            raise AccountError("код не подошёл")
        with self._lock:
            self.data = {"server": server, "login": "", "token": token, "user": {}, "rag_url": "/synapbase/api_rag",
                         "since": int(time.time()), "services": {}}
        st = self.check()
        if not self.logged_in():
            raise AccountError(self.data.get("problem") or "вход по коду не удался")
        with self._lock:
            self.data["login"] = (self.data.get("user") or {}).get("login") or self.data.get("login") or ""
            self._save()
        log.info("Вход в аккаунт по коду с другого устройства (%s)", server)
        return self.status()

    def logout(self):
        """Выйти: стираем токен, адрес сайта оставляем — для следующего входа."""
        with self._lock:
            server = self.data.get("server")
            self.data = {"server": server} if server else {}
            self._save()
        return self.status()

    def check(self):
        """Токен ещё действует? Отозвали (401) — выходим, чтобы не слать вопросы впустую; действует — обновляем
        пользователя, адрес Знаний и сервисы. Сайт недоступен — только отметка problem, вход сохраняется."""
        if not self.logged_in():
            return self.status()
        try:
            r = httpx.get(self.data["server"] + "/dwrapp/login.php", timeout=15,
                          headers={"Authorization": "Bearer " + self.data["token"], "X-App-Id": APP_ID})
        except httpx.HTTPError as e:
            with self._lock:
                self.data["problem"] = f"сайт не отвечает: {e}.{_blocked()}"
            return self.status()
        d = None
        if r.status_code == 200:
            try:
                d = r.json()
            except ValueError:
                d = None
        with self._lock:
            if r.status_code == 401:
                self.data = {"server": self.data.get("server"), "login": self.data.get("login", ""),
                             "problem": "вход устарел — войдите заново"}
            elif isinstance(d, dict):
                self.data["user"] = d.get("user") or self.data.get("user")
                self.data["rag_url"] = d.get("rag_url") or self.data.get("rag_url")
                if "services" in d:
                    self.data["services"] = d.get("services") or {}
                self.data.pop("problem", None)
            elif r.status_code == 200:                  # HTML вместо JSON (страница прокси, заглушка) — вход не трогаем
                self.data["problem"] = "сайт ответил не тем (нет входа для приложения?)"
            else:
                self.data["problem"] = _err(r)          # сбой сервера (5xx и т. п.) — только отметка, вход сохраняется
            self._save()
        return self.status()

    # ---------- Знания: базы сайта (свои папки, публичная библиотека) ----------

    def _scope_url(self):
        # api_scope лежит рядом с api_rag: …/api_rag(.php) -> …/api_scope(.php)
        return re.sub(r"api_rag(\.php)?(?=$|\?)", lambda m: "api_scope" + (m.group(1) or ""), self._rag_url())

    def scope(self, force=False, timeout=20):
        """Что можно подключить: свои папки, публичные библиотеки целиком и их разделы →
        {"bases": [{kind, id, label, docs, group…}], "docs": число документов}. Кэш на 5 минут (force — обойти)."""
        if not self.logged_in():
            raise AccountError("не выполнен вход в аккаунт Dewiar (студия → «Dewiar.pro» → «Аккаунт dewiar.pro»)")
        c = getattr(self, "_scope_cache", None)
        if c and not force and time.time() - c[0] < 300:
            return c[1]
        try:
            r = httpx.post(self._scope_url(), json={}, timeout=timeout,
                           headers={"Authorization": "Bearer " + self.data["token"], "X-App-Id": APP_ID})
        except httpx.HTTPError as e:
            raise AccountError(f"сайт не отвечает: {e}.{_blocked()}") from e
        if r.status_code == 401:
            raise AccountError("вход в аккаунт устарел — войдите заново в студии")
        if r.status_code != 200:
            raise AccountError(_err(r))
        try:
            d = r.json()
        except ValueError as e:
            raise AccountError("сайт ответил непонятно") from e
        bases = []
        for f in d.get("folders") or []:
            bases.append({"kind": "folder", "id": str(f.get("id")), "label": f.get("name") or "Папка", "docs": int(f.get("doc_count") or 0),
                          "group": "Мои папки"})
        for lib in d.get("libraries") or []:
            lab = lib.get("label") or "Публичная библиотека"
            bases.append({"kind": "library", "id": str(lib.get("id")), "label": lab, "docs": int(lib.get("doc_count") or 0),
                          "group": lab, "whole": True})
            for f in lib.get("folders") or []:
                bases.append({"kind": "library_folder", "id": str(f.get("id")), "lib": str(lib.get("id")),
                              "label": f.get("name") or "Раздел", "docs": int(f.get("doc_count") or 0), "group": lab})
        out = {"bases": bases, "docs": len(d.get("docs") or [])}
        self._scope_cache = (time.time(), out)
        return out

    @staticmethod
    def _rag_options(base):
        """База из scope() -> rag_options для api_rag (какое поле какому виду базы — так ждёт сайт)."""
        k, i = base.get("kind"), str(base.get("id") or "")
        if k == "folder":
            return {"bd_id": i}
        if k == "doc":
            return {"doc_id": i}
        if k == "library":
            return {"library_id": int(i) if i.isdigit() else i}
        if k == "library_folder":
            o = {"library_bd_id": i}
            if base.get("lib"):
                o["library_id"] = int(base["lib"]) if str(base["lib"]).isdigit() else base["lib"]
            return o
        return {}

    def retrieve(self, question, base, history=None, timeout=60):
        """Найти в базе нужное к вопросу (response_mode=retrieval_only: сайт не отвечает сам — отвечает свой персонаж)
        → {"context", "sources", "images": [{url, title}…], "found": bool}. Для уточняющих вопросов сайту уходят
        4 последние реплики. Ничего не найдено — сайт пишет в ответе «ДАННЫЕ_НЕ_НАЙДЕНЫ»."""
        if not self.logged_in():
            raise AccountError("не выполнен вход в аккаунт Dewiar")
        msgs = [m for m in (history or []) if m.get("role") in ("user", "assistant") and isinstance(m.get("content"), str)][-4:]
        msgs.append({"role": "user", "content": question})
        body = {"messages": msgs, "stream": False, "_sid": APP_ID,
                "rag_options": dict(self._rag_options(base), response_mode="retrieval_only", history_depth=4)}
        try:
            r = httpx.post(self._rag_url(), json=body, timeout=timeout,
                           headers={"Authorization": "Bearer " + self.data["token"], "X-App-Id": APP_ID})
        except httpx.TimeoutException as e:
            raise AccountError(f"база «{base.get('label')}» отвечает слишком долго") from e
        except httpx.HTTPError as e:
            raise AccountError(f"сайт не отвечает: {e}.{_blocked()}") from e
        if r.status_code == 401:
            raise AccountError("вход в аккаунт устарел — войдите заново в студии")
        if r.status_code == 429:
            raise AccountError("слишком много вопросов подряд — сайт просит подождать")
        if r.status_code != 200:
            raise AccountError(_err(r))
        try:
            d = r.json()
        except ValueError as e:
            raise AccountError("Знания ответили в непонятном виде") from e
        ctx = (d.get("ready_to_use_context") or "").strip()
        ans = ((d.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        found = bool(ctx) and "ДАННЫЕ_НЕ_НАЙДЕНЫ" not in ans
        return {"context": ctx if found else "", "sources": _sources(d.get("rag_meta")), "found": found,
                "images": self._images(d)}

    def _images(self, d, limit=4):
        """Картинки к найденному -> [{url, title}] (не больше limit): медиа-якоря типа image и картинки визуальных
        фрагментов (гравюры, схемы). Пути сайта (user_uploads/…) превращаются в полные адреса."""
        out = []
        base = self.data.get("server") or DEFAULT_SERVER
        rx = re.compile(r"\.(jpe?g|png|gif|webp)(\?|#|$)", re.I)

        def url(p, doc=None):
            p = str(p or "").strip().replace("\\", "/")
            if not p:
                return ""
            i = p.find("user_uploads/")
            if i > 0:
                p = p[i:]
            if p.startswith("http"):
                return p
            if not p.startswith(("/", "user_uploads/")):
                return ""                              # путь внутри документа без владельца — адреса не знаем
            return base.rstrip("/") + "/" + p.lstrip("/")

        for a in d.get("media_anchors") or []:
            if isinstance(a, dict) and (a.get("media_type") == "image" or rx.search(str(a.get("media_url") or ""))):
                u = url(a.get("media_url") or a.get("embed_url"))
                if u and u not in [x["url"] for x in out]:
                    out.append({"url": u, "title": a.get("title") or a.get("description") or ""})
        docs = ((d.get("rag_meta") or {}).get("retrieved_docs")) or []
        for x in docs if isinstance(docs, list) else []:
            if not isinstance(x, dict):
                continue
            for k in ("meta_path", "image_url", "media_url", "img_url", "image_path", "visual_path"):
                v = x.get(k)
                if isinstance(v, str) and rx.search(v):
                    u = url(v)
                    if u and u not in [y["url"] for y in out]:
                        out.append({"url": u, "title": x.get("name") or x.get("doc_name") or ""})
                    break
        return out[:limit]

    # ---------- Знания ----------

    def ask(self, question, bd_id=None, timeout=150, base=None):
        """Вопрос к Знаниям пользователя на сайте → {"answer", "sources"}: здесь отвечает сам сайт (в отличие от retrieve).
        401 отмечается в problem, чтобы студия предложила войти заново."""
        if not self.logged_in():
            raise AccountError("не выполнен вход в аккаунт Dewiar (студия → «Аккаунт»)")
        question = (question or "").strip()
        if not question:
            raise AccountError("пустой вопрос")
        body = {"messages": [{"role": "user", "content": question}], "stream": False, "_sid": APP_ID}
        bd = bd_id or self.data.get("bd_id")
        if base:
            body["rag_options"] = self._rag_options(base)
        elif bd:
            body["rag_options"] = {"bd_id": bd}
        try:
            r = httpx.post(self._rag_url(), json=body, timeout=timeout,
                           headers={"Authorization": "Bearer " + self.data["token"], "X-App-Id": APP_ID})
        except httpx.TimeoutException as e:
            raise AccountError("Знания отвечают слишком долго") from e
        except httpx.HTTPError as e:
            raise AccountError(f"сайт не отвечает: {e}.{_blocked()}") from e
        if r.status_code == 401:
            with self._lock:
                self.data["problem"] = "вход устарел — войдите заново"
                self._save()
            raise AccountError("вход в аккаунт устарел — войдите заново в студии")
        if r.status_code == 429:
            raise AccountError("слишком много вопросов подряд — сайт просит подождать")
        if r.status_code != 200:
            raise AccountError(_err(r))
        try:
            d = r.json()
            answer = d["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as e:
            raise AccountError("Знания ответили в непонятном виде") from e
        return {"answer": (answer or "").strip(), "sources": _sources(d.get("rag_meta"))}
