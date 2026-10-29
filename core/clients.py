"""«Клиенты» — Лира как личная CRM (28.10, владелец: «Лира как личная CRM… что ещё нужно бизнесу»; первое из списка идей
в docs/RESTART.md). Карточка клиента: кто это (имя, компания), как связаться (телефон, почта), о чём договорились —
история записей, и следующий шаг (что и когда; когда — напоминание в «Делах»).

Голосом (инструменты модели в tools.py): «запиши: Иванов из „Ромашки“ хочет 200 коробок до пятницы» — client_note
(нет такого клиента — карточка заводится сама); «что у нас с Ивановым?» — client_info; «перезвонить Иванову в четверг
в 11» — client_next (+ напоминание); «кто из клиентов ждёт ответа?» — client_list. В студии — «Клиенты» (группа «Работа»):
список с поиском, карточка, история, «Следующий шаг».

Хранение — STATE_DIR/clients.json (только этот компьютер; телефоны и сервер его не видят):
{"clients": {cid: {name, company, phone, email, note, tags, created, updated, log: [{id, ts, t, kind}], next: {at, what, rid}}}}.
kind записи: note (договорились, заметка) | call (звонок) | deal (сделка, сумма) | done (сделан следующий шаг)."""

import json
import logging
import os
import re
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

log = logging.getLogger("dewiar.clients")


class ClientError(Exception):
    """Понятная человеку ошибка — её говорит модель или показывает студия."""


def _norm(s):
    return re.sub(r"\s+", " ", str(s or "")).strip()


LEGAL = {"ооо", "ип", "оао", "зао", "ао", "пао", "чуп", "уп", "одо", "llc", "ltd", "inc"}


def _words(s):
    return [w for w in re.findall(r"[а-яa-z0-9]+", _norm(s).lower().replace("ё", "е")) if len(w) > 1 and w not in LEGAL]


def _stem(w):
    return w[:max(3, len(w) - 2)] if len(w) >= 4 else w


def _same(a, b):
    """Одно слово в разных падежах: «Иванов» / «Иванову» / «Ивановым», «Ромашка» / «Ромашки»."""
    if a == b:
        return True
    if min(len(a), len(b)) < 4:                    # «до», «на», «200» — только целиком: иначе «договор» = «до»
        return False
    sa, sb = _stem(a), _stem(b)
    if sa == sb:
        return True
    # «Пётр» — не «Петрова» (29.10): по началу слова — только у слов от пяти букв («Иванов» / «Ивановым»)
    return min(len(a), len(b)) >= 5 and (a.startswith(sb) or b.startswith(sa))


QUOTES = "«»\"'„“”"


def split_who(who):
    """«Иванов из „Ромашки“», «Иванов (Ромашка)», «Ромашка, Иванов» -> (имя, компания). Компания в кавычках или после «из»."""
    s = _norm(who)
    m = re.search(r"[«\"„“]([^»\"“”]+)[»\"“”]", s)
    company = m.group(1).strip() if m else ""
    if m:
        s = (s[:m.start()] + s[m.end():]).strip()
    m2 = re.match(r"^(.*?)\s+(?:из|от|с)\s+(?:компании\s+|фирмы\s+|ооо\s+|ип\s+)?(.+)$", s, re.I)
    if m2 and not company:
        s, company = m2.group(1), m2.group(2)
    elif m2:
        s = m2.group(1)
    m3 = re.match(r"^(.*?)\s*\((.+)\)$", s)
    if m3 and not company:
        s, company = m3.group(1), m3.group(2)
    s = re.sub(r"\s+(?:из|от|с)$", "", s.strip(" ,—-"), flags=re.I)
    if s.lower().strip(" .") in LEGAL:                         # «ООО «Вектор»» — это компания, имени нет
        s = ""
    return s.strip(" ,—-" + QUOTES), company.strip(" ,—-" + QUOTES)


from deals import DealError, DealsMixin  # noqa: E402 — сделки и «кто нам должен» (deals.py)


class Clients(DealsMixin):
    """path — clients.json; reminders — общие напоминания ядра (следующий шаг); now — время (проверки)."""

    def __init__(self, path, reminders=None, emit=None, now=None):
        self.path, self.reminders = Path(path), reminders
        self.emit = emit or (lambda *a, **k: None)
        self.now = now or datetime.now
        self._lock = threading.Lock()
        self.on_add = None                                   # crm.py: «новых клиентов — сразу в CRM»
        try:
            self.st = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.st = {}
        self.st.setdefault("clients", {})

    # ---------- хранение ----------

    def _save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.st, ensure_ascii=False, indent=1), encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError as e:
            log.warning("Клиенты: не записалось: %s", e)
        self.emit("clients")

    def _get(self, cid):
        c = self.st["clients"].get(cid)
        if not c:
            raise ClientError("такого клиента нет")
        return c

    def title(self, c):
        return c["name"] + (f" («{c['company']}»)" if c.get("company") and c["company"] != c["name"] else "")

    # ---------- поиск ----------

    def find(self, who, create=False):
        """«Иванову», «Иванов из Ромашки», «Ромашка» -> cid. Нет — create: завести; иначе ClientError. Двое — уточнить."""
        name, company = split_who(who)
        words = _words(name) + _words(company)
        if not words:
            raise ClientError("скажите, о каком клиенте речь")
        hits = []
        for cid, c in self.st["clients"].items():
            nm, cm = _words(c["name"]), _words(c.get("company"))
            if _words(company) and cm and not any(_same(w, x) for w in _words(company) for x in cm + nm):
                continue                                   # «Петрова из „Беты“» — не Петров из «Альфы»
            sc = sum(2 for w in _words(name) if any(_same(w, x) for x in nm)) + sum(1 for w in _words(name) if any(_same(w, x) for x in cm))
            sc += sum(2 for w in _words(company) if any(_same(w, x) for x in cm)) + sum(1 for w in _words(company) if any(_same(w, x) for x in nm))
            if sc:
                hits.append((sc, c.get("updated", 0), cid))
        if hits:
            best = max(h[0] for h in hits)
            top = [h for h in hits if h[0] == best]
            if len(top) == 1 or not create:
                if len(top) > 1:
                    raise ClientError("подходят несколько: " + ", ".join(self.title(self.st["clients"][h[2]]) for h in top[:4]) + " — кто именно?")
                return top[0][2]
            if len(top) > 1:
                raise ClientError("подходят несколько: " + ", ".join(self.title(self.st["clients"][h[2]]) for h in top[:4]) + " — кто именно?")
        if not create:
            raise ClientError(f"клиента «{_norm(who)}» в «Клиентах» нет")
        return self.add(name or company, company if name else "")["id"]

    # ---------- изменения ----------

    def add(self, name, company="", phone="", email="", note=""):
        name = _norm(name).strip(QUOTES)
        if not name:
            raise ClientError("впишите имя клиента или компании")
        if len(self.st["clients"]) >= 5000:
            raise ClientError("клиентов слишком много — удалите старых")
        cid = uuid.uuid4().hex[:8]
        ts = time.time()
        c = {"id": cid, "name": name[:120], "company": _norm(company)[:120], "phone": _norm(phone)[:60], "email": _norm(email)[:120],
             "note": str(note or "")[:2000], "tags": [], "created": ts, "updated": ts, "log": [], "next": None}
        with self._lock:
            self.st["clients"][cid] = c
            self._save()
        log.info("👤 Клиент заведён: %s", self.title(c))
        if self.on_add:
            try:
                self.on_add(cid)
            except Exception as e:  # noqa: BLE001
                log.info("Клиенты: CRM — %s", e)
        return dict(c)

    def set_crm(self, cid, info):
        """crm.py: куда и когда ушёл в CRM ({id, kind, host, at}) — дальше туда уходят только новые записи."""
        with self._lock:
            c = self._get(cid)
            c["crm"] = dict(info)
            self._save()

    def save(self, cid, fields):
        """Правка карточки из студии: name, company, phone, email, note, tags."""
        with self._lock:
            c = self._get(cid)
            for k, lim in (("name", 120), ("company", 120), ("phone", 60), ("email", 120)):
                if k in fields:
                    c[k] = _norm(fields[k])[:lim]
            if "note" in fields:
                c["note"] = str(fields["note"] or "")[:2000]
            if "tags" in fields:
                c["tags"] = [_norm(t)[:30] for t in (fields["tags"] or []) if _norm(t)][:12]
            if not c["name"]:
                raise ClientError("у клиента должно быть имя")
            c["updated"] = time.time()
            self._save()
            return dict(c)

    def delete(self, cid):
        with self._lock:
            c = self.st["clients"].pop(cid, None)
            if not c:
                raise ClientError("такого клиента нет")
            rid = (c.get("next") or {}).get("rid")
            self._save()
        if rid and self.reminders is not None:
            try:
                self.reminders.remove(rid)
            except Exception:  # noqa: BLE001
                pass
        return True

    def note(self, cid, text, kind="note", phone="", email=""):
        """Запись в историю (договорились, звонок, сделка). Телефон и почта из фразы — в карточку, если их не было."""
        text = _norm(text)
        if not text:
            raise ClientError("что записать?")
        if kind not in ("note", "call", "deal", "done"):
            kind = "note"
        with self._lock:
            c = self._get(cid)
            c["log"].append({"id": uuid.uuid4().hex[:6], "ts": time.time(), "t": text[:1000], "kind": kind})
            c["log"] = c["log"][-300:]
            if phone and not c.get("phone"):
                c["phone"] = _norm(phone)[:60]
            if email and not c.get("email"):
                c["email"] = _norm(email)[:120]
            c["updated"] = time.time()
            self._save()
            return dict(c)

    def note_del(self, cid, nid):
        with self._lock:
            c = self._get(cid)
            c["log"] = [x for x in c["log"] if x.get("id") != nid]
            self._save()
            return dict(c)

    def set_next(self, cid, what, at=None):
        """Следующий шаг: что и когда. Когда есть — напоминание «<что> — <клиент>» в «Делах» (прежнее снимается)."""
        what = _norm(what)
        with self._lock:
            c = self._get(cid)
            old = (c.get("next") or {}).get("rid")
            c["next"] = None
            if what:
                c["next"] = {"what": what[:300], "at": at.replace(microsecond=0).isoformat(timespec="minutes") if at else "", "rid": ""}
            c["updated"] = time.time()
        if old and self.reminders is not None:
            try:
                self.reminders.remove(old)
            except Exception:  # noqa: BLE001
                pass
        if what and at and self.reminders is not None:
            item = self.reminders.add(at, f"{what[0].upper() + what[1:]} — {self.title(c)}")
            c["next"]["rid"] = item["id"]
        with self._lock:
            self._save()
        return dict(c)

    def next_done(self, cid):
        """Следующий шаг сделан: в историю «✓ …», шаг снимается."""
        c = self._get(cid)
        n = c.get("next")
        if not n:
            raise ClientError("следующего шага нет")
        self.note(cid, "Сделано: " + n["what"], kind="done")       # «Сделано: отправить счёт»
        return self.set_next(cid, "", None)

    # ---------- для модели и студии ----------

    def list(self, q=""):
        """Студия: карточки, свежие сверху; q — поиск по имени, компании, контактам и записям."""
        ws = _words(q)
        out = []
        for c in self.st["clients"].values():
            if ws:
                hay = _words(" ".join([c["name"], c.get("company", ""), c.get("phone", ""), c.get("email", ""), c.get("note", "")]
                                      + [x["t"] for x in c["log"][-30:]]))
                if not all(any(_same(w, h) for h in hay) for w in ws):
                    continue
            last = c["log"][-1] if c["log"] else None
            out.append({"id": c["id"], "name": c["name"], "company": c.get("company", ""), "phone": c.get("phone", ""),
                        "updated": c["updated"], "last": last["t"] if last else "", "next": c.get("next"), "n": len(c["log"]),
                        "overdue": self._overdue(c)})
        out.sort(key=lambda x: (not x["overdue"], -(x["updated"] or 0)))
        return out

    def _overdue(self, c):
        at = (c.get("next") or {}).get("at")
        try:
            return bool(at) and datetime.fromisoformat(at) < self.now()
        except ValueError:
            return False

    def get(self, cid):
        return dict(self._get(cid), overdue=self._overdue(self._get(cid)))

    def card_text(self, cid):
        """Для модели: карточка одним текстом — кто, контакты, последние записи, следующий шаг."""
        c = self._get(cid)
        lines = [f"Клиент: {self.title(c)}."]
        if c.get("phone") or c.get("email"):
            lines.append("Контакты: " + ", ".join(x for x in (c.get("phone"), c.get("email")) if x) + ".")
        if c.get("note"):
            lines.append("О клиенте: " + c["note"][:400])
        for x in c["log"][-6:]:
            d = datetime.fromtimestamp(x["ts"])
            lines.append(f"— {d.day:02d}.{d.month:02d}: {x['t']}")
        n = c.get("next")
        if n:
            lines.append("Следующий шаг: " + n["what"] + (f" — {_when(n['at'])}" if n.get("at") else "") + (" (просрочен)" if self._overdue(c) else ""))
        if not c["log"] and not n:
            lines.append("Записей пока нет.")
        return "\n".join(lines)

    def summary(self, q=""):
        """Для модели: кто ждёт (просрочено и ближайшие шаги), остальные — коротко."""
        items = self.list(q)
        if not items:
            return "В «Клиентах» пока пусто." if not q else f"По «{q}» клиентов нет."
        over = [x for x in items if x["overdue"]]
        soon = sorted([x for x in items if x["next"] and x["next"].get("at") and not x["overdue"]], key=lambda x: x["next"]["at"])
        out = []
        if over:
            out.append("Ждут, срок прошёл: " + "; ".join(f"{_t(x)} — {x['next']['what']} ({_when(x['next']['at'])})" for x in over[:10]))
        if soon:
            out.append("Дальше: " + "; ".join(f"{_t(x)} — {x['next']['what']} ({_when(x['next']['at'])})" for x in soon[:10]))
        rest = [x for x in items if not x["next"]][:10]
        if rest:
            out.append("Без следующего шага: " + "; ".join(_t(x) + (f" — последнее: {x['last'][:80]}" if x["last"] else "") for x in rest))
        owed = [d for d in self.deals() if d["owed"]]
        if owed and not q:
            out.append(self.deals_summary("owed"))           # «кто ждёт?» — и кто нам должен (deals.py)
        return f"Клиентов: {len(items)}. " + " ".join(out)


def _t(x):
    return x["name"] + (f" («{x['company']}»)" if x.get("company") and x["company"] != x["name"] else "")


def _when(at):
    try:
        d = datetime.fromisoformat(at)
    except (TypeError, ValueError):
        return at or ""
    now = datetime.now()
    hm = f"{d.hour}:{d.minute:02d}"
    days = (d.date() - now.date()).days
    if days == 0:
        return f"сегодня в {hm}"
    if days == 1:
        return f"завтра в {hm}"
    if days == -1:
        return f"вчера в {hm}"
    mon = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"][d.month - 1]
    return f"{d.day} {mon} в {hm}"
