"""«Чат для сайта» в программе владельца (0.69; запрос бизнеса 29.10: «виджет на сайт и ссылка, переписка с лидами — в CRM»;
владелец: «ответы с сайта Девиар»). Отвечает сервер dewiar.pro (cloud.php: /sc/ask) — компьютер владельца может быть
выключен. Здесь — настройка и заявки:

  • «Опубликовать» — персонаж (имя, характер, портрет 128 px), заголовок, приветствие, «О чём», знания (что вписано вручную
    + по желанию текст документов из папок персонажа, всего до 60 тыс. знаков) уходят на сервер (/sitechat/save); в ответ —
    ссылка и строка для сайта. Нужен вход аккаунтом dewiar.pro или ключ Dewiar — с него и платится.
  • Заявки посетителей («Оставить контакт») раз в 2 минуты забираются (/sitechat/leads) и становятся клиентами в «Клиентах»
    (есть такой по телефону или почте — запись в его историю) с разговором; уведомление владельцу; CRM — как у любого нового
    клиента (crm.py: «новых — сразу»), у знакомого — новые записи комментарием.

Настройки — settings["sitechat"]: {persona, title, greeting, brief, kb, folders, ask_contact, per_ip, per_day, on};
что ответил сервер (ссылка, счётчики) — в памяти (remote)."""

import base64
import io
import logging
import re
import threading
import time
from datetime import datetime
from pathlib import Path

log = logging.getLogger("dewiar.sitechat")
KB_MAX = 60000
DEF = {"persona": "", "title": "", "greeting": "", "brief": "", "kb": "", "folders": False, "ask_contact": True,
       "per_ip": 40, "per_day": 500, "on": False}
PHONE_RX = re.compile(r"\+?\d[\d\s()-]{5,}\d")
EMAIL_RX = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


class SiteChatError(Exception):
    pass


def readable(hex_color, min_ratio=4.5):
    """Цвет персонажа для чата на чужом сайте: на нём белый текст (свои сообщения, кнопки) — светлые цвета (у Лиры —
    #9BD4FF) темнеем, пока белый на нём не станет читаться (контраст ≥ 4,5)."""
    def lum(c):
        def ch(v):
            v /= 255
            return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
        return 0.2126 * ch(c[0]) + 0.7152 * ch(c[1]) + 0.0722 * ch(c[2])
    try:
        c = [int(hex_color[i:i + 2], 16) for i in (1, 3, 5)]
    except (TypeError, ValueError):
        return "#6a5cf0"
    for _ in range(40):
        if 1.05 / (lum(c) + 0.05) >= min_ratio:
            break
        c = [int(v * 0.92) for v in c]
    return "#%02x%02x%02x" % tuple(c)


class SiteChat:
    def __init__(self, host):
        self.host = host
        self.remote, self.error = None, ""
        self._stop = threading.Event()
        self._thread = None
        self.recent = []                          # последние заявки (для студии): [{ts, name, contact, cid}]

    # ---------- настройки ----------
    def cfg(self):
        return {**DEF, **(self.host.s.get("sitechat") or {})}

    def public(self, fresh=False):
        if fresh and self.cfg().get("on"):
            try:
                self.remote = self._fetch("/sitechat/get")
            except SiteChatError as e:
                self.error = str(e)
        c = self.cfg()
        r = self.remote if self.remote and not self.remote.get("none") else None
        return {**c, "kb_chars": len(c.get("kb") or ""), "remote": r, "error": self.error, "recent": self.recent[-10:][::-1],
                "signed": bool(self._key())}

    def _key(self):
        return (getattr(getattr(self.host, "cloud", None), "key", "") or "").strip()

    def _fetch(self, path, body=None):
        from cloud import CloudError, fetch
        if not self._key():
            raise SiteChatError("нужен вход аккаунтом dewiar.pro или ключ Dewiar — студия → «Мозг»")
        try:
            return fetch(self.host.cloud.url, self._key(), path, timeout=25, body=body)
        except CloudError as e:
            raise SiteChatError(str(e)) from e

    def _persona(self, pid):
        try:
            return self.host.personas.get(pid or self.host.s.get("persona")) or {}
        except Exception:  # noqa: BLE001
            return {}

    def _avatar(self, p):
        """Портрет персонажа — маленьким (128 px, webp): в окне чата он размером с монету."""
        try:
            url = self.host.personas.avatar_data_url(p)
            if not url.startswith("data:image"):
                return ""
            from PIL import Image
            im = Image.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1]))).convert("RGB")
            im.thumbnail((128, 128))
            buf = io.BytesIO()
            im.save(buf, "WEBP", quality=82)
            return "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode()
        except Exception:  # noqa: BLE001
            return ""

    def _folder_text(self, p, room):
        """Текст документов из папок знаний персонажа (по порядку, сколько влезет)."""
        from knowledge import EXTS, extract
        out = []
        for b in p.get("knowledge") or []:
            if b.get("kind") != "folder" or not b.get("path"):
                continue
            for f in sorted(Path(b["path"]).rglob("*")):
                if room <= 200:
                    break
                if f.is_file() and f.suffix.lower() in EXTS and f.stat().st_size < 20 * 1024 * 1024:
                    try:
                        t = re.sub(r"\n{3,}", "\n\n", extract(f) or "").strip()
                    except Exception:  # noqa: BLE001
                        continue
                    if t:
                        t = f"Документ «{f.name}»:\n{t}"[:room]
                        out.append(t)
                        room -= len(t) + 2
        return "\n\n".join(out)

    def build(self, c):
        p = self._persona(c.get("persona"))
        kb = (c.get("kb") or "").strip()[:KB_MAX]
        if c.get("folders"):
            extra = self._folder_text(p, KB_MAX - len(kb) - 2)
            kb = (kb + "\n\n" + extra).strip() if extra else kb
        return {"name": p.get("name") or "Консультант", "character": re.sub(r"\s+", " ", str(p.get("character") or "")).strip()[:900],
                "brief": c.get("brief") or "", "greeting": c.get("greeting") or "", "title": c.get("title") or "", "kb": kb[:KB_MAX],
                "color": readable(p.get("color")) if re.fullmatch(r"#[0-9a-fA-F]{6}", str(p.get("color") or "")) else "#6a5cf0",
                "avatar": self._avatar(p), "ask_contact": bool(c.get("ask_contact")), "on": True,
                "per_ip": int(c.get("per_ip") or 40), "per_day": int(c.get("per_day") or 500)}

    def publish(self, patch=None):
        """Сохранить настройки и отправить на сервер — ссылка и код для сайта в ответе."""
        patch = {k: v for k, v in (patch or {}).items() if k in DEF}
        for k in ("title", "greeting"):
            if k in patch:
                patch[k] = str(patch[k] or "").strip()[:300]
        if "brief" in patch:
            patch["brief"] = str(patch["brief"] or "").strip()[:1500]
        if "kb" in patch:
            patch["kb"] = str(patch["kb"] or "")[:KB_MAX]
        c = {**self.cfg(), **patch, "on": True}
        self.remote = self._fetch("/sitechat/save", self.build(c))
        self.error = ""
        self.host.s.update({"sitechat": c, "features": {"clients": True}})      # заявки — в «Клиенты»: раздел включаем
        log.info("💬 Чат для сайта опубликован: %s", self.remote.get("link"))
        self.start()
        return self.public()

    def forget(self):
        try:
            self._fetch("/sitechat/forget", {})
        finally:
            self.remote = None
            self.host.s.update({"sitechat": {"on": False}})
        return self.public()

    # ---------- заявки ----------
    def _find_client(self, contact):
        C = self.host.clients
        digits = re.sub(r"\D", "", contact)
        for c in C.st["clients"].values():
            if digits and len(digits) >= 6 and re.sub(r"\D", "", c.get("phone") or "")[-10:] == digits[-10:]:
                return c["id"]
            if "@" in contact and (c.get("email") or "").lower() == contact.lower():
                return c["id"]
        return None

    def take(self, lead):
        """Заявка с сайта -> клиент (новый или знакомый) с разговором в истории. -> id клиента."""
        C = self.host.clients
        contact = (lead.get("contact") or "").strip()
        m1, m2 = EMAIL_RX.search(contact), PHONE_RX.search(contact)
        email = m1.group(0) if m1 else ""
        phone = m2.group(0) if m2 and not m1 else ""
        talk = "\n".join(("Посетитель: " if m.get("role") == "user" else "Консультант: ") + str(m.get("text") or "")[:500]
                         for m in (lead.get("talk") or [])[-12:])
        when = datetime.fromtimestamp(lead.get("ts") or time.time()).strftime("%d.%m %H:%M")
        text = f"Заявка с сайта ({when}): {contact}" + (f" — {lead['note']}" if lead.get("note") else "") + (f"\n{talk}" if talk else "")
        cid = self._find_client(contact)
        if cid:
            C.note(cid, text)
            crm = getattr(self.host, "crm", None)
            if crm is not None and crm.connected() and crm.st.get("auto"):
                threading.Thread(target=lambda: crm.send(cid), name="crm-site", daemon=True).start()
        else:
            name = (lead.get("name") or "").strip() or contact
            cid = C.add(name, phone=phone or "", email=email or "")["id"]
            C.note(cid, text)
        return cid

    def poll(self):
        """Забрать новые заявки, завести клиентов, подтвердить серверу."""
        if not self.cfg().get("on") or not self._key():
            return 0
        try:
            d = self._fetch("/sitechat/leads", {})
        except SiteChatError as e:
            self.error = str(e)
            return 0
        self.remote = {k: v for k, v in d.items() if k != "leads"}
        self.error = ""
        done = []
        for lead in d.get("leads") or []:
            try:
                cid = self.take(lead)
            except Exception as e:  # noqa: BLE001
                log.warning("💬 Заявка с сайта не завелась: %s", e)
                continue
            done.append(lead["id"])
            self.recent.append({"ts": lead.get("ts"), "name": lead.get("name") or "", "contact": lead.get("contact") or "", "cid": cid})
            self.recent = self.recent[-20:]
            try:
                self.host.push("Заявка с сайта", f"{lead.get('name') or 'Посетитель'}, {lead.get('contact')} — в «Клиентах»")
            except Exception:  # noqa: BLE001
                pass
        if done:
            try:
                self._fetch("/sitechat/leads", {"ack": done})
            except SiteChatError as e:
                log.info("💬 Заявки заведены, но сервер не узнал: %s (придут ещё раз — повторы найдутся по контакту)", e)
            try:
                self.host.emit("sitechat", **self.public())
            except Exception:  # noqa: BLE001
                pass
        return len(done)

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="sitechat", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _loop(self):
        while not self._stop.wait(5 if not self.remote else 120):
            if not self.cfg().get("on"):
                continue
            try:
                self.poll()
            except Exception:  # noqa: BLE001
                log.exception("Чат для сайта: заявки")
