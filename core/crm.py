"""«CRM» — клиенты из Dewiar в свою CRM (0.69; запрос бизнеса 29.10: «связать чат с лидами в CRM — Битрикс24»).

Два способа, оба — входящая ссылка, которую человек создаёт у себя сам (пароль от CRM Dewiar не нужен):
  • Битрикс24 — «Разработчикам» → «Другое» → «Входящий вебхук» с правом «CRM»: ссылка вида
    https://<портал>.bitrix24.ru/rest/<номер>/<ключ>/. Клиент уходит лидом (crm.lead.add): имя, компания, телефон, почта,
    история записей — в комментарий, источник — «Dewiar». Новые записи по тому же клиенту — комментарием в его ленту
    (crm.timeline.comment.add), не вторым лидом.
  • Свой вебхук (amoCRM через свой обработчик, Make, n8n, Zapier, своя таблица) — POST JSON
    {event: "lead"|"update"|"test", source: "dewiar", client: {name, company, phone, email, note, tags}, notes: [...], crm_id}.
«Новых клиентов — сразу в CRM» (auto): заведённая голосом или в студии карточка уходит сама.

Ссылка — это ключ к CRM: хранится только на этом компьютере (STATE_DIR/crm.json, права 600), в журналы и студию целиком не
попадает — студия видит только адрес портала. Стоп-кран «Ничего не уходит в интернет» действует и здесь (egress.py)."""

import json
import logging
import os
import re
import threading
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

log = logging.getLogger("dewiar.crm")
BITRIX_RX = re.compile(r"^(https://[A-Za-z0-9.-]+(?::\d+)?/rest/\d+/[A-Za-z0-9_]+)(?:/.*)?$")
KIND_NAME = {"bitrix": "Битрикс24", "webhook": "свой вебхук"}
LOG_KIND = {"note": "", "call": "Звонок: ", "deal": "Сделка: ", "done": "✓ "}


class CrmError(Exception):
    pass


def bitrix_base(url):
    """Ссылка входящего вебхука Битрикс24 -> основа «https://портал/rest/N/ключ» (лишний метод в конце — убираем)."""
    m = BITRIX_RX.match((url or "").strip())
    if not m:
        raise CrmError("это не ссылка входящего вебхука Битрикс24 — она выглядит так: https://ваш-портал.bitrix24.ru/rest/1/ключ/")
    return m.group(1)


def _local(host):
    return host in ("localhost", "127.0.0.1", "::1") or host.endswith(".local")


def check_hook(url):
    u = urlparse((url or "").strip())
    if u.scheme not in ("https", "http") or not u.hostname:
        raise CrmError("нужна ссылка, начинающаяся с https://")
    if u.scheme == "http" and not _local(u.hostname):
        raise CrmError("ссылка вебхука — только https:// (по http данные клиентов ушли бы открытыми)")
    return url.strip()


def split_name(name):
    """«Иванов Пётр Сергеевич» / «Пётр Иванов» -> (имя, фамилия): Битрикс24 хранит их отдельно."""
    ws = (name or "").split()
    if len(ws) >= 3:
        return ws[1], ws[0]
    if len(ws) == 2:
        a, b = ws
        surname = re.search(r"(ов|ев|ин|ын|ий|ая|ова|ева|ина|ына|ский|цкий|ко|ук|юк|ич)$", a.lower())
        return (b, a) if surname else (a, b)
    return (ws[0] if ws else ""), ""


def _notes_text(notes):
    out = []
    for x in notes:
        d = datetime.fromtimestamp(x.get("ts") or time.time())
        out.append(f"{d.day:02d}.{d.month:02d}.{d.year} — {LOG_KIND.get(x.get('kind'), '')}{x.get('t', '')}")
    return "\n".join(out)


class Crm:
    def __init__(self, path, clients=None, http=None):
        self.path, self.clients = Path(path), clients
        self._lock = threading.RLock()
        self.st = {"kind": "", "url": "", "auto": False}
        try:
            self.st.update(json.loads(self.path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass
        self._http = http
        if clients is not None:
            clients.on_add = self._on_add

    # ---------- настройки ----------
    def _save(self):
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.st, ensure_ascii=False, indent=1), encoding="utf-8")
            try:
                os.chmod(tmp, 0o600)
            except OSError:
                pass
            os.replace(tmp, self.path)

    def connected(self):
        return bool(self.st.get("kind") and self.st.get("url"))

    def public(self):
        """Студии — без ключа: только вид, адрес портала и «новых сразу»."""
        host = urlparse(self.st.get("url") or "").hostname or ""
        return {"kind": self.st.get("kind", ""), "name": KIND_NAME.get(self.st.get("kind"), ""), "host": host,
                "connected": self.connected(), "auto": bool(self.st.get("auto")), "last": self.st.get("last") or None}

    def connect(self, kind, url, test=True):
        if kind == "bitrix":
            url = bitrix_base(url)
        elif kind == "webhook":
            url = check_hook(url)
        else:
            raise CrmError("выберите Битрикс24 или свой вебхук")
        old = dict(self.st)
        self.st.update(kind=kind, url=url)
        if test:
            try:
                self.test()
            except CrmError:
                self.st = old
                raise
        self._save()
        log.info("🔗 CRM подключена: %s (%s)", KIND_NAME[kind], urlparse(url).hostname)
        return self.public()

    def forget(self):
        self.st = {"kind": "", "url": "", "auto": False}
        self._save()
        return self.public()

    def set_auto(self, on):
        self.st["auto"] = bool(on)
        self._save()
        return self.public()

    # ---------- сеть ----------
    def _post(self, url, body):
        if self._http:
            return self._http(url, body)
        import httpx
        try:
            r = httpx.post(url, json=body, timeout=20, follow_redirects=False)
        except httpx.HTTPError as e:
            raise CrmError(f"CRM не ответила: {type(e).__name__}") from e
        try:
            d = r.json()
        except ValueError:
            d = {}
        if r.status_code >= 400:
            msg = (d.get("error_description") or d.get("error") or "") if isinstance(d, dict) else ""
            if r.status_code in (401, 403) or "insufficient_scope" in str(d) or "invalid_credentials" in str(d) or "INVALID_CREDENTIALS" in str(d):
                raise CrmError("CRM не пускает: ссылка устарела или у вебхука нет права «CRM» — создайте новую")
            raise CrmError(f"CRM ответила ошибкой {r.status_code}" + (f": {msg}" if msg else ""))
        return d if isinstance(d, dict) else {}

    def _bx(self, method, body):
        d = self._post(f"{self.st['url']}/{method}.json", body)
        if d.get("error"):
            raise CrmError("Битрикс24: " + str(d.get("error_description") or d.get("error")))
        return d.get("result")

    def test(self):
        if not self.connected():
            raise CrmError("CRM не подключена — студия → «Клиенты» → «CRM»")
        if self.st["kind"] == "bitrix":
            self._bx("crm.lead.fields", {})
        else:
            self._post(self.st["url"], {"event": "test", "source": "dewiar", "ts": int(time.time())})
        return True

    # ---------- отправка ----------
    def send(self, cid, source="Dewiar", extra=""):
        """Клиента — в CRM: в первый раз лидом, дальше — новые записи комментарием. -> {id, kind, new, n}."""
        if not self.connected():
            raise CrmError("CRM не подключена — студия → «Клиенты» → «CRM»")
        try:
            c = self.clients.get(cid)
        except Exception as e:  # noqa: BLE001 — ClientError «такого клиента нет»
            raise CrmError(str(e)) from e
        link = c.get("crm") or {}
        same = link.get("kind") == self.st["kind"] and link.get("host") == urlparse(self.st["url"]).hostname
        since = link.get("at", 0) if same else 0
        notes = [x for x in c.get("log") or [] if (x.get("ts") or 0) > since]
        text = _notes_text(notes) + (("\n\n" if notes else "") + extra if extra else "")
        if self.st["kind"] == "bitrix":
            if same and link.get("id"):
                if not text:
                    return {"id": link["id"], "kind": "bitrix", "new": False, "n": 0}
                etype, eid = self._bx_target(link)
                self._bx("crm.timeline.comment.add", {"fields": {"ENTITY_ID": int(eid), "ENTITY_TYPE": etype,
                                                                 "COMMENT": "Из Dewiar:\n" + text}})
                rid, new = link["id"], False
            else:
                first, last = split_name(c["name"])
                first = first or c["name"]                    # простой режим CRM без имени лид в сделку не превратит
                f = {"TITLE": (c.get("company") or c["name"]) + " — из Dewiar", "NAME": first, "LAST_NAME": last,
                     "COMPANY_TITLE": c.get("company") or "", "SOURCE_ID": "OTHER", "SOURCE_DESCRIPTION": source,
                     "COMMENTS": "\n\n".join(x for x in (c.get("note") or "", text) if x)}
                if c.get("phone"):
                    f["PHONE"] = [{"VALUE": c["phone"], "VALUE_TYPE": "WORK"}]
                if c.get("email"):
                    f["EMAIL"] = [{"VALUE": c["email"], "VALUE_TYPE": "WORK"}]
                rid, new = str(self._bx("crm.lead.add", {"fields": f, "params": {"REGISTER_SONET_EVENT": "Y"}})), True
        else:
            body = {"event": "update" if same and link.get("id") else "lead", "source": "dewiar", "ts": int(time.time()),
                    "crm_id": link.get("id") if same else None,
                    "client": {k: c.get(k) or ("" if k != "tags" else []) for k in ("name", "company", "phone", "email", "note", "tags")},
                    "notes": [{"at": datetime.fromtimestamp(x["ts"]).isoformat(timespec="minutes"), "kind": x.get("kind", "note"), "text": x["t"]} for x in notes],
                    "extra": extra or ""}
            d = self._post(self.st["url"], body)
            rid = str(d.get("id") or d.get("lead_id") or (link.get("id") if same else "") or c["id"])
            new = not (same and link.get("id"))
        info = {"id": rid, "kind": self.st["kind"], "host": urlparse(self.st["url"]).hostname, "at": time.time()}
        if same and link.get("deal"):
            info["deal"] = link["deal"]
        elif same and getattr(self, "_deal", None):
            info["deal"], self._deal = self._deal, None
        self.clients.set_crm(cid, info)
        self.st["last"] = {"at": info["at"], "name": c["name"], "ok": True}
        self._save()
        log.info("🔗 CRM: %s — %s", c["name"], "новый лид" if new else "добавлены записи")
        return {"id": rid, "kind": self.st["kind"], "new": new, "n": len(notes)}

    def _bx_target(self, link):
        """Куда писать новые записи: в лид — или в сделку, если лид уже в неё превращён (простой режим CRM делает это
        сразу, в обычном — менеджер). -> («lead»|«deal», id)."""
        if link.get("deal"):
            return "deal", link["deal"]
        try:
            ld = self._bx("crm.lead.get", {"id": link["id"]}) or {}
            if ld.get("STATUS_ID") == "CONVERTED":
                ds = self._bx("crm.deal.list", {"filter": {"LEAD_ID": link["id"]}, "select": ["ID"]}) or []
                if ds:
                    self._deal = str(ds[0]["ID"])
                    return "deal", self._deal
        except CrmError as e:
            log.info("🔗 CRM: лид %s не прочитался: %s", link.get("id"), e)
        return "lead", link["id"]

    def _on_add(self, cid):
        """«Новых клиентов — сразу в CRM»: в фоне, ошибка — в журнал и в «последнюю отправку» (видно в студии)."""
        if not (self.connected() and self.st.get("auto")):
            return

        def go():
            try:
                self.send(cid)
            except Exception as e:  # noqa: BLE001
                log.info("🔗 CRM: новый клиент не ушёл: %s", e)
                self.st["last"] = {"at": time.time(), "name": "", "ok": False, "err": str(e)[:200]}
                self._save()
        threading.Thread(target=go, name="crm-auto", daemon=True).start()
