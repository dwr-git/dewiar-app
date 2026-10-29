"""«Рассылка» (0.69; запрос бизнеса 29.10: «писать письма на почту, делать рассылку групповую — начальник отправляет письма
10 сотрудникам или 100 клиентам»; владелец: «все пункты делаем»).

Каждому — своё письмо со своей почты (почта Dewiar, mail.py): «{имя}» в теме и тексте подставляется; адреса друг друга
получатели не видят (раньше send_email с десятью адресами — одно письмо всем, с адресами всех).
Кому: «Клиенты» (у кого есть почта; можно меткой), сотрудники (у кого в карточке почта) или свой список — строки
«Имя <адрес>», «адрес, Имя» или просто адреса. Повторы и неверные адреса — отсеиваются, отписавшиеся — тоже.
Сначала — черновик: сколько получателей и пример письма первому; отправка — только по «Отправить» (в студии или
голосом с подтверждением). Письма уходят по одному, с паузой (по умолчанию 8 с) и не больше дневного предела почты
(по умолчанию 300 — у Яндекса и Mail.ru около 500 в сутки): дошли до предела — рассылка ждёт следующего дня и
продолжает сама (и после перезапуска). Итог — сколько ушло и у кого ошибка.

Реклама (kind «ads») — по закону только тем, кто согласился, и с возможностью отписаться: в конце письма — строка
«не хотите получать — ответьте „Отписаться“», заголовок List-Unsubscribe (mailto на свой адрес); ответы «Отписаться»
во «Входящих» перед каждой рассылкой попадают в стоп-список (его видно и можно править в студии). Деловые письма
(kind «work») — без этой строки.

Состояние — STATE_DIR/mailing.json: {campaigns: {id: {...}}, stop: [адреса], day: {date, n}}."""

import json
import logging
import re
import threading
import time
import uuid
from datetime import date
from pathlib import Path

log = logging.getLogger("dewiar.mailing")
EMAIL_RX = re.compile(r"[A-Za-z0-9._%+'-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
UNSUB_RX = re.compile(r"(?i)\b(отписа\w*|отпиши\w*|unsubscribe)\b")
PAUSE_S, DAY_MAX, MAX_RECIPS = 8.0, 300, 2000


class MailingError(Exception):
    pass


def parse_list(text):
    """«Анна <anna@x.ru>», «anna@x.ru, Анна», «Анна anna@x.ru» или просто адреса — по строке/через ; -> [{name, email}]."""
    out = []
    for line in re.split(r"[\n;]+", text or ""):
        for m in EMAIL_RX.finditer(line):
            rest = (line[:m.start()] + " " + line[m.end():])
            name = re.sub(r"[<>,\"'()\[\]]+", " ", rest).strip()
            name = re.sub(r"\s+", " ", name) if len(EMAIL_RX.findall(line)) == 1 else ""
            out.append({"name": name[:80], "email": m.group(0).strip(".").lower()})
    return out


def first_name(name):
    """«Иванова Анна Петровна» → обращение: «Анна Петровна» не угадать — берём имя, как записано первым словом, если
    второго нет; «Анна Иванова» → «Анна». Пусто — «» (в письме подставится «Здравствуйте»)."""
    ws = [w for w in re.split(r"\s+", (name or "").strip()) if w]
    return ws[0] if ws else ""


def render(text, r):
    """{имя} — обращение, {полное_имя}, {почта}; без имени «{имя}» в «Здравствуйте, {имя}!» — просто «Здравствуйте!»."""
    nm = first_name(r.get("name"))
    t = text or ""
    if not nm:
        t = re.sub(r",\s*\{(имя|name)\}", "", t)
    return (t.replace("{имя}", nm).replace("{name}", nm).replace("{полное_имя}", r.get("name") or "")
            .replace("{почта}", r.get("email") or ""))


def plain(subject):
    """Тема без подстановок — для уведомлений и голоса: «{имя}, расписание» → «расписание»."""
    return re.sub(r"\s{2,}", " ", re.sub(r"\{[^{}]*\}[,!:]?\s*", "", subject or "")).strip(" ,!:—-")


class Mailing:
    def __init__(self, host, path):
        self.host, self.path = host, Path(path)
        self._lock = threading.RLock()
        self.st = {"campaigns": {}, "stop": [], "day": {"date": "", "n": 0}}
        try:
            self.st.update(json.loads(self.path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass
        self._cancel = {}
        self.pause_s = PAUSE_S

    # ---------- хранение ----------
    def _save(self):
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.st, ensure_ascii=False, indent=1), encoding="utf-8")
            tmp.replace(self.path)

    def _emit(self, c):
        try:
            self.host.emit("mailing", campaign=self.public(c))
        except Exception:  # noqa: BLE001
            pass

    def day_max(self):
        try:
            return max(1, int(self.host.s.get("mailing", "day_max") or DAY_MAX))
        except (TypeError, ValueError, AttributeError):
            return DAY_MAX

    # ---------- кому ----------
    def sources(self):
        """Студия: сколько адресов есть в «Клиентах» (и метки) и у сотрудников."""
        cl = self._clients()
        tags = sorted({t for c in cl for t in c.get("tags") or []})
        mail = getattr(self.host, "mail", None)
        boxes = [b.data.get("address", "") for b in (getattr(mail, "boxes", None) or []) if b.configured()]
        return {"boxes": boxes, "clients": len(cl), "tags": tags, "team": len(self._team()), "stop": len(self.st.get("stop") or []),
                "mail": bool(getattr(self.host, "mail", None) and self.host.mail.configured()), "day_max": self.day_max()}

    def _clients(self, tag=""):
        c = getattr(self.host, "clients", None)
        if c is None:
            return []
        out = []
        for x in (c.st.get("clients") or {}).values():
            if EMAIL_RX.fullmatch((x.get("email") or "").strip()) and (not tag or tag in (x.get("tags") or [])):
                out.append({"name": x.get("name", ""), "email": x["email"].strip().lower(), "tags": x.get("tags") or []})
        return out

    def _team(self):
        t = getattr(self.host, "team", None)
        if t is None:
            return []
        return [{"name": m.get("name", ""), "email": (m.get("email") or "").strip().lower()}
                for m in (t.st.get("members") or {}).values() if EMAIL_RX.fullmatch((m.get("email") or "").strip())]

    def recipients(self, source="list", text="", tag=""):
        """-> (получатели без повторов и отписавшихся, сколько отсеяно: {dup, stop})."""
        raw = self._clients(tag) if source == "clients" else self._team() if source == "team" else parse_list(text)
        stop = set(self.st.get("stop") or [])
        seen, out, dup, st = set(), [], 0, 0
        for r in raw:
            e = r["email"].lower()
            if e in seen:
                dup += 1
                continue
            seen.add(e)
            if e in stop:
                st += 1
                continue
            out.append({"name": r.get("name", ""), "email": e})
        return out[:MAX_RECIPS], {"dup": dup, "stop": st}

    def preview(self, subject="", body="", source="list", text="", tag="", kind="work", box=None):
        """Студия, на лету: сколько получателей, кто, и как будет выглядеть письмо первому — до черновика."""
        rs, sk = self.recipients(source, text, tag)
        out = {"n": len(rs), "skipped": sk, "names": [r["name"] or r["email"] for r in rs[:8]]}
        if rs and (subject or body):
            c = {"subject": subject or "", "body": body or "", "kind": "ads" if kind == "ads" else "work", "box": box or ""}
            s, b = self.letter(c, rs[0])
            out["sample"] = {"to": rs[0]["email"], "name": rs[0]["name"], "subject": s, "body": b}
        return out

    # ---------- черновик ----------
    def draft(self, subject, body, source="list", text="", tag="", kind="work", box=None):
        subject, body = (subject or "").strip(), (body or "").strip()
        if not subject or not body:
            raise MailingError("нужны тема и текст письма")
        rs, skipped = self.recipients(source, text, tag)
        if not rs:
            raise MailingError("некому отправлять: " + ("в «Клиентах» нет никого с почтой" if source == "clients"
                                                       else "у сотрудников не указаны почты" if source == "team"
                                                       else "в списке нет ни одного адреса"))
        cid = uuid.uuid4().hex[:10]
        c = {"id": cid, "subject": subject[:200], "body": body[:20000], "kind": "ads" if kind == "ads" else "work",
             "source": source, "tag": tag, "box": box or "", "created": time.time(), "status": "draft",
             "to": [dict(r, st="", err="") for r in rs], "skipped": skipped}
        with self._lock:
            self.st["campaigns"][cid] = c
            old = sorted(self.st["campaigns"].values(), key=lambda x: x["created"])[:-30]   # храним 30 последних
            for o in old:
                if o["status"] != "sending":
                    self.st["campaigns"].pop(o["id"], None)
            self._save()
        return self.public(c, sample=True)

    def letter(self, c, r):
        """-> (тема, текст) одного письма."""
        me = ""
        try:
            me = self.host.mail.box(c.get("box") or None).data.get("address", "")
        except Exception:  # noqa: BLE001
            pass
        body = render(c["body"], r)
        if c["kind"] == "ads":
            body += ("\n\n—\nВы получили это письмо, потому что согласились получать наши новости. Не хотите больше — "
                     "ответьте на него словом «Отписаться»" + (f" (или напишите на {me})" if me else "") + ".")
        return render(c["subject"], r), body

    def public(self, c, sample=False):
        n = len(c["to"])
        ok = sum(1 for r in c["to"] if r["st"] == "ok")
        bad = [r for r in c["to"] if r["st"] == "err"]
        out = {k: c[k] for k in ("id", "subject", "kind", "source", "tag", "created", "status")}
        out.update(total=n, sent=ok, failed=len(bad), errors=[{"email": r["email"], "err": r["err"]} for r in bad][:20],
                   skipped=c.get("skipped") or {}, waiting=c.get("waiting", ""), body=c["body"])
        if sample and c["to"]:
            s, b = self.letter(c, c["to"][0])
            out["sample"] = {"to": c["to"][0]["email"], "name": c["to"][0]["name"], "subject": s, "body": b}
            out["names"] = [r["name"] or r["email"] for r in c["to"][:8]]
        return out

    def list(self):
        return [self.public(c) for c in sorted(self.st["campaigns"].values(), key=lambda x: -x["created"])]

    def get(self, cid):
        c = self.st["campaigns"].get(cid)
        if not c:
            raise MailingError("такой рассылки нет")
        return self.public(c, sample=True)

    def forget(self, cid):
        with self._lock:
            c = self.st["campaigns"].get(cid)
            if c and c["status"] == "sending":
                raise MailingError("рассылка идёт — сначала остановите")
            self.st["campaigns"].pop(cid, None)
            self._save()
        return True

    # ---------- отписка ----------
    def stop_list(self):
        return sorted(self.st.get("stop") or [])

    def stop_set(self, emails):
        with self._lock:
            self.st["stop"] = sorted({e.lower() for e in EMAIL_RX.findall(" ".join(emails if isinstance(emails, list) else [emails or ""]))})
            self._save()
        return self.stop_list()

    def _scan_unsub(self, c):
        """Ответы «Отписаться» во «Входящих» — в стоп-список (перед рекламной рассылкой; ошибки почты не мешают)."""
        mail = getattr(self.host, "mail", None)
        if mail is None or c["kind"] != "ads":
            return 0
        try:
            items = mail.inbox(limit=50, box=c.get("box") or None)
        except Exception as e:  # noqa: BLE001
            log.info("✉️ Рассылка: «Входящие» для отписок не прочитались: %s", e)
            return 0
        new = set()
        for x in items:
            if UNSUB_RX.search(" ".join(str(x.get(k) or "") for k in ("subject", "preview", "snippet", "text"))):
                new.update(e.lower() for e in EMAIL_RX.findall(str(x.get("from") or "")))
        with self._lock:
            before = set(self.st.get("stop") or [])
            self.st["stop"] = sorted(before | new)
            added = len(self.st["stop"]) - len(before)
            if added:
                for r in c["to"]:
                    if r["st"] == "" and r["email"] in new:
                        r["st"], r["err"] = "skip", "отписался"
                self._save()
        if added:
            log.info("✉️ Рассылка: отписались %d — им не пишем", added)
        return added

    # ---------- отправка ----------
    def start(self, cid):
        with self._lock:
            c = self.st["campaigns"].get(cid)
            if not c:
                raise MailingError("такой рассылки нет")
            if c["status"] == "sending":
                return self.public(c)
            if c["status"] == "done":
                raise MailingError("эта рассылка уже ушла — для новой сделайте черновик")
            if not (getattr(self.host, "mail", None) and self.host.mail.configured()):
                raise MailingError("почта не подключена — студия → «Подключение» → «Почта»")
            c["status"], c["started"] = "sending", c.get("started") or time.time()
            self._save()
        ev = threading.Event()
        self._cancel[cid] = ev
        threading.Thread(target=self._run, args=(cid, ev), name="mailing", daemon=True).start()
        self._emit(c)
        return self.public(c)

    def stop(self, cid):
        ev = self._cancel.get(cid)
        if ev:
            ev.set()
        with self._lock:
            c = self.st["campaigns"].get(cid)
            if c and c["status"] in ("sending", "waiting"):
                c["status"] = "stopped"
                self._save()
                self._emit(c)
        return True

    def resume(self):
        """После перезапуска: рассылки, которые шли или ждали следующего дня, — продолжить."""
        for c in list(self.st["campaigns"].values()):
            if c["status"] in ("sending", "waiting"):
                c["status"] = "paused"
                try:
                    self.start(c["id"])
                except MailingError as e:
                    log.info("✉️ Рассылка «%s» не продолжилась: %s", c["subject"], e)

    def _room(self):
        """Сколько писем ещё можно сегодня (дневной предел почты)."""
        d = self.st.setdefault("day", {"date": "", "n": 0})
        today = date.today().isoformat()
        if d.get("date") != today:
            d["date"], d["n"] = today, 0
        return self.day_max() - int(d.get("n") or 0)

    def _run(self, cid, ev):
        c = self.st["campaigns"][cid]
        self._scan_unsub(c)
        log.info("✉️ Рассылка «%s»: %d писем", c["subject"], sum(1 for r in c["to"] if not r["st"]))
        for r in c["to"]:
            if ev.is_set():
                return
            if r["st"]:
                continue
            while self._room() <= 0:                           # дневной предел почты — ждём завтра и продолжаем
                with self._lock:
                    c["status"], c["waiting"] = "waiting", "дневной предел почты — продолжу завтра"
                    self._save()
                self._emit(c)
                if ev.wait(600):
                    return
            with self._lock:
                c["status"], c["waiting"] = "sending", ""
            subj, body = self.letter(c, r)
            try:
                me = self.host.mail.box(c.get("box") or None).data.get("address", "")
                hdr = {"List-Unsubscribe": f"<mailto:{me}?subject=Отписаться>"} if c["kind"] == "ads" and me else None
                self.host.mail.send(r["email"], subj, body, (), box=c.get("box") or None, headers=hdr)
                r["st"], r["at"] = "ok", time.time()
                self.st["day"]["n"] = int(self.st["day"].get("n") or 0) + 1
            except Exception as e:  # noqa: BLE001
                r["st"], r["err"] = "err", str(e)[:200]
                log.info("✉️ Рассылка: %s — %s", r["email"], e)
            with self._lock:
                self._save()
            self._emit(c)
            if any(not x["st"] for x in c["to"]) and ev.wait(self.pause_s):
                return
        with self._lock:
            c["status"], c["done"] = "done", time.time()
            self._save()
        p = self.public(c)
        log.info("✉️ Рассылка «%s» закончена: ушло %d из %d%s", c["subject"], p["sent"], p["total"],
                 f", ошибок {p['failed']}" if p["failed"] else "")
        self._emit(c)
        try:
            self.host.push("Рассылка закончена", f"«{plain(c['subject'])}»: ушло {p['sent']} из {p['total']}"
                           + (f", не дошло {p['failed']}" if p["failed"] else ""), telegram=False)
        except Exception:  # noqa: BLE001
            pass
