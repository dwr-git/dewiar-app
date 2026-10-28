"""Семейный бюджет (27.10, решение владельца по макету «Dewiar — новые режимы»): общий месяц на всю семью.

Семья — это свои «Близкие» (close.py), которых пригласили в бюджет и которые согласились. Всё идёт тем же сквозным
шифрованием, что и сообщения близким: сервер видит лишь «кому и когда» (вид «fam» в close_msgs).
  • Траты: каждая запись расхода в «Деньгах» (money.Money.add — голосом «продукты 46,20», моделью, в студии) уходит
    семье, если «делиться тратами» включено; у каждого — общая лента и итог месяца по людям.
  • Общие платежи: свет, газ, интернет — кто платит и до какого числа; «Оплачено» — всем, «Напомнить» — сообщением.
  • Лимит на месяц — общий: кто поменял, у всех то же самое (последнее изменение главнее).
Сообщения вида fam: {"fam": {"op": ...}} — invite, join, leave, spend, del, bill, paid, limit. Старые программы
вид «fam» показывают как обычное сообщение — поэтому у приглашения есть понятный текст (t); остальное шлём только
тем, кто уже согласился (у них программа новая).
Состояние — STATE_DIR/family.json: members {pid: {name, st: invited|asked|joined}}, ledger [...], bills {...}, limit."""

import json
import logging
import os
import threading
import time
import uuid
from datetime import date
from pathlib import Path

log = logging.getLogger("dewiar.family")
LEDGER_DAYS = 400


class FamilyError(Exception):
    pass


class Family:
    """host — ядро (close, s, emit, money); path — family.json."""

    def __init__(self, host, path):
        self.host, self.path = host, Path(path)
        self._lock = threading.RLock()
        try:
            self.st = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.st = {}
        self.st.setdefault("members", {})
        self.st.setdefault("ledger", [])
        self.st.setdefault("bills", {})
        self.st.setdefault("limit", {"v": 0, "at": 0})
        self.st.setdefault("share", True)

    # ---------- хранение ----------

    def _save(self):
        cut = time.time() - LEDGER_DAYS * 86400
        self.st["ledger"] = [x for x in self.st["ledger"] if x.get("ts", 0) / 1000 > cut][-5000:]
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.st, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError as e:
            log.info("Семья: не записалось: %s", e)

    def _changed(self):
        self._save()
        try:
            self.host.emit("family", **self.public())
        except Exception:  # noqa: BLE001
            log.debug("семья: событие", exc_info=True)

    def joined(self):
        return [pid for pid, m in self.st["members"].items() if m.get("st") == "joined"]

    def active(self):
        return bool(self.joined())

    def _me(self):
        c = getattr(self.host, "close", None)
        return ((c.st.get("me") or {}).get("name") if c else "") or "Я"

    def _send(self, pids, op, text=""):
        """Отправить действие семье (каждому — своим конвертом). Не дошло до кого-то — не страшно: в журнал."""
        c = self.host.close
        for pid in pids:
            try:
                c.send(pid, text=text, kind="fam", payload={"fam": op})
            except Exception as e:  # noqa: BLE001
                log.info("Семья: %s не получил(а) «%s»: %s", pid, op.get("op"), e)

    # ---------- участники ----------

    def invite(self, pid):
        p = self.host.close.person(pid)
        with self._lock:
            m = self.st["members"].get(p["pid"]) or {}
            if m.get("st") == "joined":
                return self.public()
            if m.get("st") == "asked":                    # он нас уже пригласил — значит, просто соглашаемся
                return self.accept(p["pid"])
            self.st["members"][p["pid"]] = {"name": p["name"], "st": "invited", "at": int(time.time())}
        self._send([p["pid"]], {"op": "invite"},
                   text=f"Приглашаю вести общий семейный бюджет в Dewiar: траты и общие платежи у всех вместе. "
                        "Принять: на телефоне — «Близкие» → вкладка «Семья» (обновите приложение Dewiar, если её нет), "
                        "на компьютере — студия → «Семья».")
        self._changed()
        return self.public()

    def accept(self, pid):
        with self._lock:
            m = self.st["members"].get(pid)
            if not m:
                raise FamilyError("приглашения от этого человека нет")
            m["st"], m["at"] = "joined", int(time.time())
        self._send([pid], {"op": "join", "limit": self.st["limit"], "bills": list(self.st["bills"].values())})
        self._changed()
        return self.public()

    def leave(self, pid):
        with self._lock:
            m = self.st["members"].pop(pid, None)
        if m:
            self._send([pid], {"op": "leave"})
        self._changed()
        return self.public()

    # ---------- траты ----------

    def share_spend(self, it):
        """Новая запись в «Деньгах» (money.Money.on_add): расход — в общую ленту и семье."""
        if it.get("kind") != "expense" or not self.st.get("share", True):
            return
        e = {"id": it["id"], "who": "", "name": self._me(), "amount": it["amount"], "cur": it.get("currency", ""),
             "cat": it.get("category", ""), "note": it.get("note", ""), "said": (it.get("said") or "")[:120],
             "date": it.get("date"), "ts": int(time.time() * 1000)}
        with self._lock:
            self.st["ledger"].append(e)
        pids = self.joined()
        if pids:                                         # в фоне: ответ голосом «Записал расход» не ждёт сети
            threading.Thread(target=self._send, args=(pids, {"op": "spend", "e": {k: v for k, v in e.items() if k != "who"}}),
                             name="family-send", daemon=True).start()
        self._changed()

    def delete_spend(self, iid):
        with self._lock:
            n = len(self.st["ledger"])
            self.st["ledger"] = [x for x in self.st["ledger"] if not (x["id"] == iid and not x.get("who"))]
            if len(self.st["ledger"]) == n:
                return
        if self.joined():
            threading.Thread(target=self._send, args=(self.joined(), {"op": "del", "id": iid}), name="family-send", daemon=True).start()
        self._changed()

    # ---------- общие платежи ----------

    def bill_save(self, b):
        name = str(b.get("name") or "").strip()[:60]
        if not name:
            raise FamilyError("назовите платёж: свет, газ, интернет…")
        due = str(b.get("due") or "")[:10]
        if due:
            date.fromisoformat(due)
        bill = {"id": b.get("id") or uuid.uuid4().hex[:10], "name": name, "amount": round(float(b.get("amount") or 0), 2),
                "due": due, "payer": str(b.get("payer") or "")[:40], "paid_by": "", "paid_at": 0, "at": int(time.time() * 1000)}
        with self._lock:
            old = self.st["bills"].get(bill["id"]) or {}
            bill["paid_by"], bill["paid_at"] = old.get("paid_by", ""), old.get("paid_at", 0)
            self.st["bills"][bill["id"]] = bill
        self._send(self.joined(), {"op": "bill", "b": bill})
        self._changed()
        return bill

    def bill_paid(self, bid, paid=True):
        with self._lock:
            b = self.st["bills"].get(bid)
            if not b:
                raise FamilyError("нет такого платежа")
            b["paid_by"], b["paid_at"], b["at"] = (self._me(), int(time.time() * 1000), int(time.time() * 1000)) if paid else ("", 0, int(time.time() * 1000))
        self._send(self.joined(), {"op": "bill", "b": b})
        self._changed()
        return b

    def bill_delete(self, bid):
        with self._lock:
            b = self.st["bills"].pop(bid, None)
        if b:
            self._send(self.joined(), {"op": "bill", "b": dict(b, gone=1, at=int(time.time() * 1000))})
        self._changed()

    def remind(self, bid):
        """«Напомнить» — обычным сообщением в «Близких» тому, кто платит (если он в семье)."""
        b = self.st["bills"].get(bid)
        if not b:
            raise FamilyError("нет такого платежа")
        who = next((pid for pid in self.joined() if self.st["members"][pid]["name"] == b.get("payer")), None)
        if not who:
            raise FamilyError("напомнить можно тому, кто в семье, — выберите, кто платит")
        due = f" до {b['due'][8:10]}.{b['due'][5:7]}" if b.get("due") else ""
        self.host.close.send(who, f"Напоминаю: оплатить «{b['name']}»{due}" + (f" — {b['amount']:g}" if b.get("amount") else "") + ".")
        return True

    def set_limit(self, v):
        lim = {"v": max(0, round(float(v or 0), 2)), "at": int(time.time() * 1000)}
        with self._lock:
            self.st["limit"] = lim
        self._send(self.joined(), {"op": "limit", "l": lim})
        self._changed()

    def set_share(self, on):
        self.st["share"] = bool(on)
        self._changed()

    # ---------- входящие (close.py, вид «fam») ----------

    def incoming(self, peer, name, body, out=False):
        """Действие от близкого (или от другого своего устройства — out: применяем так же, но «кто» — я)."""
        op = (body or {}).get("fam") or {}
        kind = op.get("op")
        with self._lock:
            m = self.st["members"].get(peer)
            if kind == "invite" and not out:
                if not m or m.get("st") != "joined":
                    self.st["members"][peer] = {"name": name or "Близкий", "st": "asked", "at": int(time.time())}
                    try:                                 # позвали в семью — раздел «Семья» включается сам (он по желанию)
                        if self.host.s.get("features", "family") is not True:
                            self.host.s.update({"features": {"family": True}})
                            self.host.emit("settings", settings=self.host.s.snapshot())
                    except Exception:  # noqa: BLE001
                        log.debug("семья: включить раздел", exc_info=True)
                    try:
                        self.host.push("👪 Семейный бюджет", f"{name} приглашает вести общий бюджет — студия → «Семья»")
                    except Exception:  # noqa: BLE001
                        pass
            elif kind == "join" and not out:
                if m and m.get("st") in ("invited", "asked"):
                    m["st"] = "joined"
                    self._merge_limit(op.get("limit"))
                    for b in op.get("bills") or []:
                        self._merge_bill(b)
                    # ему — то, что уже есть у нас: платежи и лимит
                    threading.Thread(target=self._send, args=([peer], {"op": "join", "limit": self.st["limit"],
                                                                        "bills": list(self.st["bills"].values())}), daemon=True).start()
                elif m and m.get("st") == "joined":
                    self._merge_limit(op.get("limit"))
                    for b in op.get("bills") or []:
                        self._merge_bill(b)
            elif kind == "leave" and not out:
                self.st["members"].pop(peer, None)
            elif kind in ("invite", "join", "leave") and out:
                # то же действие с другого своего устройства (компьютер ↔ телефон): состав семьи — общий
                if kind == "leave":
                    self.st["members"].pop(peer, None)
                elif kind == "invite" and not m:
                    self.st["members"][peer] = {"name": name or "Близкий", "st": "invited", "at": int(time.time())}
                elif kind == "join":
                    self.st["members"][peer] = dict(m or {}, name=(m or {}).get("name") or name or "Близкий", st="joined")
            elif not (m and m.get("st") == "joined") and not out:
                return                                   # не из семьи — не принимаем
            elif kind == "spend":
                e = op.get("e") or {}
                if e.get("id") and not any(x["id"] == e["id"] and x.get("who") == (peer if not out else "") for x in self.st["ledger"]):
                    self.st["ledger"].append(dict(e, who="" if out else peer, name=e.get("name") or name))
            elif kind == "del":
                self.st["ledger"] = [x for x in self.st["ledger"] if not (x["id"] == op.get("id") and x.get("who") == (peer if not out else ""))]
            elif kind == "bill":
                self._merge_bill(op.get("b") or {})
            elif kind == "limit":
                self._merge_limit(op.get("l"))
        self._changed()

    def _merge_bill(self, b):
        if not b.get("id"):
            return
        cur = self.st["bills"].get(b["id"])
        if cur and int(cur.get("at", 0)) > int(b.get("at", 0)):
            return                                       # у нас новее — оставляем
        if b.get("gone"):
            self.st["bills"].pop(b["id"], None)
        else:
            self.st["bills"][b["id"]] = {k: b.get(k) for k in ("id", "name", "amount", "due", "payer", "paid_by", "paid_at", "at")}

    def _merge_limit(self, lim):
        if isinstance(lim, dict) and int(lim.get("at", 0)) > int(self.st["limit"].get("at", 0)):
            self.st["limit"] = {"v": float(lim.get("v") or 0), "at": int(lim["at"])}

    # ---------- для окон ----------

    def public(self, month=None):
        month = month or date.today().isoformat()[:7]
        led = [x for x in self.st["ledger"] if str(x.get("date") or "")[:7] == month]
        by = {}
        for x in led:
            k = x.get("who") or ""
            by.setdefault(k, {"pid": k, "name": "Я" if not k else x.get("name") or (self.st["members"].get(k) or {}).get("name", ""), "sum": 0.0})
            by[k]["sum"] = round(by[k]["sum"] + float(x.get("amount") or 0), 2)
        for pid in [""] + self.joined():
            by.setdefault(pid, {"pid": pid, "name": "Я" if not pid else self.st["members"][pid]["name"], "sum": 0.0})
        today = date.today().isoformat()
        bills = sorted(self.st["bills"].values(), key=lambda b: (bool(b.get("paid_by")), b.get("due") or "9999"))
        try:
            cur = self.host.money.currency()
        except Exception:  # noqa: BLE001
            cur = ""
        return {"me": self._me(), "currency": cur,
                "members": [dict(m, pid=pid) for pid, m in self.st["members"].items()], "active": self.active(),
                "share": self.st.get("share", True), "month": month, "total": round(sum(v["sum"] for v in by.values()), 2),
                "limit": self.st["limit"].get("v", 0), "by": sorted(by.values(), key=lambda v: (v["pid"] != "", -v["sum"])),
                "bills": bills, "feed": sorted([x for x in led if x.get("date") == today], key=lambda x: -x.get("ts", 0))[:30],
                "recent": sorted(led, key=lambda x: -x.get("ts", 0))[:60]}
