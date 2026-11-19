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
что ответил сервер (ссылка, счётчики) — в памяти (remote).

Свой консультант для каждого сайта (14.11, владелец: «для каждого сайта свой консультант — просто логично»): настройки
сайта — settings["sitechat"]["sites"][<имя сайта на dewiar.pro>] (новый — копия общих, выключен), на сервере — свой чат
с site; сайт без своего показывает общий. Заявки забираются одним запросом со всех чатов, у заявки — сайт."""

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
DOCS_MAX = 3_000_000       # документы папок персонажа целиком — сервер ищет по ним (sitechat_kb.php, 19.11: «12 книг»)
DEF = {"persona": "", "title": "", "greeting": "", "brief": "", "kb": "", "folders": False, "ask_contact": True,
       "per_ip": 40, "per_day": 500, "on": False, "theme": "auto"}
THEMES = ("soft", "night", "auto", "brand", "classic", "neo", "neo-dark")   # оформление окна чата (владелец 11.11): server/dwrapp/sitechat.php
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
        self.remotes, self.error = {}, ""          # что ответил сервер — по сайтам ('' — общий чат)
        self._stop = threading.Event()
        self._thread = None
        self.recent = []                          # последние заявки (для студии): [{ts, name, contact, cid}]
        self.fit, self.fits = None, {}            # что из папок персонажа вошло в знания сайта (отзыв 17.11 «книги») — по сайтам

    # ---------- настройки ----------
    def _raw(self):
        return dict(self.host.s.get("sitechat") or {})

    def cfg(self, site=""):
        base = {**DEF, **{k: v for k, v in self._raw().items() if k != "sites"}}
        if not site:
            return base
        own = (self._raw().get("sites") or {}).get(site)
        return {**base, "on": False, **(own or {})}            # свой ещё не сделан — начинаем с общих настроек

    def _store(self, c, site=""):
        c = {k: v for k, v in c.items() if k in DEF}
        if site:
            sites = dict(self._raw().get("sites") or {})
            sites[site] = c
            self.host.s.update({"sitechat": {"sites": sites}})
        else:
            self.host.s.update({"sitechat": c})

    def any_on(self):
        return bool(self.cfg().get("on")) or any((v or {}).get("on") for v in (self._raw().get("sites") or {}).values())

    def site_names(self):
        """Опубликованные сайты на dewiar.pro — для выбора «Для какого сайта»."""
        S = getattr(self.host, "sites", None)
        out = []
        try:
            for x in S.list() if S is not None and hasattr(S, "list") else []:
                n = ((x.get("published") or {}).get("name") or "") if isinstance(x, dict) else ""
                if n and n not in out:
                    out.append(n)
        except Exception:  # noqa: BLE001
            pass
        return out

    def public(self, fresh=False, site=""):
        site = site if site in self.site_names() or site in (self._raw().get("sites") or {}) else ""
        if fresh and (self.cfg(site).get("on") or (site and self.cfg().get("on"))):
            try:
                self.remotes[site] = self._fetch("/sitechat/get", {"site": site})
            except SiteChatError as e:
                self.error = str(e)
        c = self.cfg(site)
        rem = self.remotes.get(site)
        r = rem if rem and not rem.get("none") else None
        own = self._raw().get("sites") or {}
        return {**c, "kb_chars": len(c.get("kb") or ""), "remote": r, "error": self.error, "recent": self.recent[-10:][::-1],
                "signed": bool(self._key()), "site": site, "fit": self.fits.get(site),
                "sites": [{"name": n, "own": bool((own.get(n) or {}).get("on"))} for n in self.site_names()]}

    @property
    def remote(self):
        return self.remotes.get("")

    @remote.setter
    def remote(self, v):
        self.remotes[""] = v

    def _key(self):
        return (getattr(getattr(self.host, "cloud", None), "key", "") or "").strip()

    def _fetch(self, path, body=None):
        from cloud import CloudError, fetch
        if not self._key():
            raise SiteChatError("нужен вход аккаунтом dewiar.pro или ключ Dewiar — студия → «Мозг»")
        try:
            return fetch(self.host.cloud.url, self._key(), path, timeout=180 if (body or {}).get("docs") else 25, body=body)   # книги целиком — сервер режет их не сразу
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

    def _folder_docs(self, p, room=DOCS_MAX):
        """Документы папок знаний персонажа целиком: [{f: имя, t: текст}] — до room знаков всего. Сервер режет их на
        отрывки и к вопросу посетителя ищет лучшие (sitechat_kb.php). Отзыв 19.11 (автор, 12 книг): раньше уходило
        60 000 знаков — начало первой книги. В self.fit — что вошло (студия показывает, если вошло не всё)."""
        from knowledge import EXTS, extract
        docs = []
        fit = {"files": 0, "full": 0, "cut": [], "out": 0}
        for b in p.get("knowledge") or []:
            if b.get("kind") != "folder" or not b.get("path"):
                continue
            for f in sorted(Path(b["path"]).rglob("*")):
                if not (f.is_file() and f.suffix.lower() in EXTS and f.stat().st_size < 20 * 1024 * 1024) or f.name == "О папке.md":
                    continue
                fit["files"] += 1
                if room <= 200:
                    fit["out"] += 1
                    continue
                try:
                    t = re.sub(r"\n{3,}", "\n\n", extract(f) or "").strip()
                except Exception:  # noqa: BLE001
                    continue
                if t:
                    if len(t) > room:
                        fit["cut"].append(f.name)
                        t = t[:room]
                    else:
                        fit["full"] += 1
                    docs.append({"f": f.stem[:120], "t": t})
                    room -= len(t)
        self.fit = fit
        return docs

    def _folder_text(self, p, room):
        """Старый сервер (без поиска по документам): текст документов по порядку, сколько влезет в знания (60 000)."""
        out = []
        for d in self._folder_docs(p):
            if room <= 200:
                break
            t = f"Документ «{d['f']}»:\n{d['t']}"[:room]
            out.append(t)
            room -= len(t) + 2
        return "\n\n".join(out)

    def build(self, c):
        p = self._persona(c.get("persona"))
        kb = (c.get("kb") or "").strip()[:KB_MAX]
        self.fit = None
        docs = self._folder_docs(p) if c.get("folders") else []
        return {"docs": docs, "name": p.get("name") or "Консультант", "character": re.sub(r"\s+", " ", str(p.get("character") or "")).strip()[:900],
                "brief": c.get("brief") or "", "greeting": c.get("greeting") or "", "title": c.get("title") or "", "kb": kb[:KB_MAX],
                "color": readable(p.get("color")) if re.fullmatch(r"#[0-9a-fA-F]{6}", str(p.get("color") or "")) else "#6a5cf0",
                "avatar": self._avatar(p), "ask_contact": bool(c.get("ask_contact")), "on": True,
                "theme": c.get("theme") if c.get("theme") in THEMES else "auto",
                "per_ip": int(c.get("per_ip") or 40), "per_day": int(c.get("per_day") or 500)}

    def publish(self, patch=None, site=""):
        """Сохранить настройки и отправить на сервер — ссылка и код для сайта в ответе. site — свой консультант этого сайта."""
        patch = {k: v for k, v in (patch or {}).items() if k in DEF}
        for k in ("title", "greeting"):
            if k in patch:
                patch[k] = str(patch[k] or "").strip()[:300]
        if "brief" in patch:
            patch["brief"] = str(patch["brief"] or "").strip()[:1500]
        if "kb" in patch:
            patch["kb"] = str(patch["kb"] or "")[:KB_MAX]
        c = {**self.cfg(site), **patch, "on": True}
        body = self.build(c)
        if site:
            body["site"] = site
        r = self._fetch("/sitechat/save", body)
        if body.get("docs") and "docs" not in r:          # сервер ещё без поиска по документам — по-старому, началом в знаниях
            p = self._persona(c.get("persona"))
            extra = self._folder_text(p, KB_MAX - len(body["kb"]) - 2)
            body = dict(body, kb=(body["kb"] + "\n\n" + extra).strip()[:KB_MAX] if extra else body["kb"])
            body.pop("docs")
            r = self._fetch("/sitechat/save", body)
            self.fit = dict(self.fit or {}, old=True)
        if site and not r.get("per_site"):
            raise SiteChatError("сервер Dewiar ещё не умеет отдельный чат для сайта — обновите сервер")
        self.remotes[site] = r
        self.fits[site] = self.fit
        self.error = ""
        self._store(c, site)
        self.host.s.update({"features": {"clients": True}})      # заявки — в «Клиенты»: раздел включаем
        log.info("💬 Чат для сайта%s опубликован: %s", f" {site}" if site else "", r.get("link"))
        self.start()
        return self.public(site=site)

    def forget(self, site=""):
        try:
            self._fetch("/sitechat/forget", {"site": site} if site else {})
        finally:
            self.remotes.pop(site, None)
            self._store({**self.cfg(site), "on": False}, site)
        return self.public(site=site)

    # ---------- знания с сайта (18.11, «Компания»: «минимум ручных настроек») ----------
    SITE_HINT = re.compile(r"(?i)цен|прайс|стоим|услуг|работ|каталог|контакт|о нас|о компании|доставк|оплат|гарант|вопрос|faq|"
                           r"price|service|contact|about|delivery|payment|warranty")

    def from_site(self, url, max_pages=8, limit=40000):
        """«Взять с сайта»: главная и до max_pages страниц того же сайта, похожих на цены, услуги, контакты, доставку, вопросы,
        — текстом (заголовки и абзацы строками, без меню, скриптов и повторов). -> {text, pages: [{url, title, chars}]}.
        Человек видит текст в «Знаниях» и правит его сам — ничего не публикуется без «Опубликовать»."""
        import html as _h
        from urllib.parse import urljoin, urlparse
        import httpx
        url = str(url or "").strip()
        if not re.match(r"(?i)^https?://", url):
            url = "https://" + url
        host = urlparse(url).netloc.lower()
        if not host or "." not in host:
            raise SiteChatError("впишите адрес сайта, например example.ru")

        def get(u):
            r = httpx.get(u, timeout=12, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0 (Dewiar; site knowledge)"})
            if r.status_code >= 400 or "html" not in r.headers.get("content-type", "html"):
                raise SiteChatError(f"сайт ответил {r.status_code}")
            return str(r.url), r.text[:1_500_000]

        def text_of(page):
            t = re.sub(r"(?is)<(head|script|style|noscript|svg|nav|footer|form|iframe)[^>]*>.*?</\1>", " ", page)
            t = re.sub(r"(?is)<!--.*?-->", " ", t)
            t = re.sub(r"(?is)<a\s[^>]*>(.*?)</a>", "\x01\\1\x02", t)          # ссылки помечаем: строка из одних ссылок — меню
            t = re.sub(r"(?i)</?(br|p|h[1-6]|tr|div|section|article|header|main|aside|dd|dt|ul|ol|table)\b[^>]*>", "\n", t)
            t = re.sub(r"(?i)<li[^>]*>", "\n• ", t)
            t = re.sub(r"<[^>]+>", " ", t)
            out = []
            for x in t.split("\n"):
                if "\x01" in x and not re.search(r"\w{3}", re.sub(r"\x01.*?\x02|•", "", x)):
                    continue                                      # одни ссылки — меню или список разделов
                x = re.sub(r"[ \t\xa0]+", " ", _h.unescape(x.replace("\x01", "").replace("\x02", ""))).strip()
                if len(x) >= 3 and not re.fullmatch(r"[\W\d_]+", x):
                    out.append(x)
            return out

        def title_of(page):
            m = re.search(r"(?is)<title[^>]*>(.*?)</title>", page)
            return re.sub(r"\s+", " ", _h.unescape(m.group(1))).strip()[:120] if m else ""
        try:
            first, page = get(url)
        except httpx.HTTPError as e:
            raise SiteChatError(f"сайт не открылся: {e.__class__.__name__}") from e
        host = urlparse(first).netloc.lower()
        links = []
        for m in re.finditer(r'(?is)<a\s[^>]*href=["\']([^"\'#]+)["\'][^>]*>(.*?)</a>', page):
            u = urljoin(first, _h.unescape(m.group(1)).strip())
            label = re.sub(r"<[^>]+>|\s+", " ", m.group(2)).strip()
            pu = urlparse(u)
            if pu.scheme not in ("http", "https") or pu.netloc.lower() != host or re.search(r"(?i)\.(pdf|jpe?g|png|gif|webp|zip|docx?|xlsx?)$", pu.path):
                continue
            u = u.split("#")[0]
            if u.rstrip("/") == first.rstrip("/") or u in [x[0] for x in links]:
                continue
            if self.SITE_HINT.search(label + " " + pu.path):
                links.append((u, label))
        pages, seen, out, total = [], set(), [], 0
        for u, pg in [(first, page)] + [(u, None) for u, _ in links[:max_pages]]:
            if total >= limit:
                break
            if pg is None:
                try:
                    u, pg = get(u)
                except (httpx.HTTPError, SiteChatError):
                    continue
            keep = []
            for ln in text_of(pg):
                k = ln.lower()
                if k in seen:                              # меню, шапка, подвал — повторяются на каждой странице
                    continue
                seen.add(k)
                keep.append(ln)
            body = "\n".join(keep)[: max(0, limit - total)]
            if len(body) < 40:
                continue
            ttl = title_of(pg) or urlparse(u).path or host
            out.append(f"## {ttl}\n{body}")
            total += len(body)
            pages.append({"url": u, "title": ttl, "chars": len(body)})
        if not pages:
            raise SiteChatError("на сайте не нашлось текста — возможно, он собран скриптами; вставьте знания вручную")
        log.info("💬 Знания с сайта %s: %d стр., %d знаков", host, len(pages), total)
        return {"text": "\n\n".join(out), "pages": pages, "host": host}

    # ---------- свой бот в Telegram (18.11, пилот «Компания», часть А) ----------
    def tg(self, token, site=""):
        """Тот же консультант — ещё и в своём боте компании в Telegram; отвечает облако (компьютер может быть выключен).
        token — из @BotFather; "" — отключить. Токен уходит на сервер Dewiar и здесь не хранится. -> public()."""
        token = str(token or "").strip()
        if token:
            mine = []
            for owner in (getattr(self.host, "telegram", None), getattr(getattr(self.host, "team", None), "bot", None)):
                t = (getattr(owner, "data", None) or {}).get("token") if owner is not None else ""
                if t:
                    mine.append(t)
            if token in mine:
                raise SiteChatError("этот бот уже работает у вас в программе (личный Telegram или «Поручения») — "
                                    "для клиентов нужен отдельный: @BotFather → /newbot")
            if not (self.remotes.get(site) and not self.remotes[site].get("none")):
                raise SiteChatError("сначала опубликуйте чат — бот отвечает по тем же знаниям")
        body = {"token": token}
        if site:
            body["site"] = site
        self.remotes[site] = self._fetch("/sitechat/tg", body)
        self.error = ""
        log.info("💬 Чат для сайта: бот в Telegram %s", self.remotes[site].get("tg") or "отключён")
        return self.public(site=site)

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
        where = f" {lead['site']}.dewiar.pro" if lead.get("site") else ""
        head = "Заявка из Telegram" if lead.get("via") == "tg" else f"Заявка с сайта{where}"
        text = f"{head} ({when}): {contact}" + (f" — {lead['note']}" if lead.get("note") else "") + (f"\n{talk}" if talk else "")
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
        if not self.any_on() or not self._key():
            return 0
        try:
            d = self._fetch("/sitechat/leads", {})
        except SiteChatError as e:
            self.error = str(e)
            return 0
        if not d.get("per_site") or "" in (d.get("sites") or {}):      # счётчики в ответе — общего чата (если он есть)
            self.remote = {k: v for k, v in d.items() if k not in ("leads", "sites")}
        self.error = ""
        done = []
        for lead in d.get("leads") or []:
            try:
                cid = self.take(lead)
            except Exception as e:  # noqa: BLE001
                log.warning("💬 Заявка с сайта не завелась: %s", e)
                continue
            done.append(lead["id"])
            team = getattr(self.host, "team", None)
            if team is not None and hasattr(team, "lead_task"):      # «Поручения»: заявку — сотруднику, если выбран (18.11)
                try:
                    team.lead_task(lead, cid)
                except Exception:  # noqa: BLE001
                    log.exception("💬 Заявка: поручение")
            sites = getattr(self.host, "sites", None)
            if lead.get("site") and lead.get("via") != "tg" and sites is not None and hasattr(sites, "_lead_log"):
                # 0.99 (владелец 14.11: «заявка в «Заявках» сайта не появилась, нашёл случайно в «Клиентах»»): заявка из чата —
                # и во вкладку «Заявки» своего сайта, с пометкой, что из чата
                try:
                    sites._lead_log(dict(lead, page="chat"), cid)
                except Exception:  # noqa: BLE001
                    log.exception("💬 Заявка: журнал сайта")
            self.recent.append({"ts": lead.get("ts"), "name": lead.get("name") or "", "contact": lead.get("contact") or "", "cid": cid})
            self.recent = self.recent[-20:]
            try:
                self.host.push("Заявка из Telegram" if lead.get("via") == "tg" else "Заявка с сайта", f"{lead.get('name') or 'Посетитель'}, {lead.get('contact')} — в «Клиентах»")
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
            if not self.any_on():
                continue
            try:
                self.poll()
            except Exception:  # noqa: BLE001
                log.exception("Чат для сайта: заявки")
