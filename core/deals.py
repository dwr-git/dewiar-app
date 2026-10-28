"""Сделки и «кто нам должен» (0.58; согласовано с владельцем 28.10 — третий и четвёртый пункт «Лиры как личной CRM»).
Сделка живёт в карточке клиента («Клиенты», clients.py): c["deals"] = [{id, title, amount, cur, stage, due, created,
moved, paid, note}]. Этапы: заявка → предложение → счёт → оплачено (или отказ). «Счёт» — значит, нам должны: сумма и
«оплатить до» (due); срок прошёл — должник. Зависла — заявка или предложение без движения больше STUCK_DAYS дней, счёт без
срока — больше OWED_DAYS. Каждое движение — строка в истории клиента («Сделка «Коробки 200 шт»: счёт, 1 200 руб.»).

Голосом (tools.py): deal_add — «Ромашке выставили счёт на 1200 за коробки, оплатить до пятницы»; deal_stage — «Ромашка
оплатила счёт» (оплата — и в доходы, если просили или включено в студии), «Иванов отказался от сделки»; deals_list —
«кто нам должен?», «какие сделки зависли?». Студия — «Клиенты» → «Сделки»: доска по этапам с суммами и в карточке клиента.
Утро с Лирой — кто должен и что зависло."""
import re
import time
import uuid
from datetime import date, timedelta

STAGES = {"lead": "Заявка", "offer": "Предложение", "invoice": "Счёт", "paid": "Оплачено", "lost": "Отказ"}
OPEN = ("lead", "offer", "invoice")
STUCK_DAYS = 7
OWED_DAYS = 14
STAGE_WORDS = [("paid", r"оплат|заплат|деньги\s+приш|рассчитал|paid"), ("lost", r"отказ|сорвал|не\s+будет|передумал|lost"),
               ("invoice", r"сч[её]т|инвойс|выставил|долж"), ("offer", r"предложени|кп\b|коммерческ|offer|смет"),
               ("lead", r"заявк|запрос|интерес|lead")]


class DealError(Exception):
    pass


def stage_of(word):
    """«оплатил», «выставили счёт», «КП отправили» -> paid / invoice / offer …; не понятно — ""."""
    w = str(word or "").lower().replace("ё", "е")
    if w in STAGES:
        return w
    for k, rx in STAGE_WORDS:
        if re.search(rx, w):
            return k
    return ""


def amount_of(v):
    """1200, «1 200», «1200,50», «1,2 тыс», «2 млн» -> float (0 — нет суммы)."""
    if isinstance(v, (int, float)):
        return max(0.0, float(v))
    s = str(v or "").lower().replace(" ", " ")
    m = re.search(r"(\d[\d\s]*(?:[.,]\d+)?)\s*(тыс|к\b|млн)?", s)
    if not m:
        return 0.0
    n = float(m.group(1).replace(" ", "").replace(",", "."))
    return n * (1000 if m.group(2) in ("тыс", "к") else 1_000_000 if m.group(2) == "млн" else 1)


def due_of(v, today=None):
    """«2026-11-05», «до пятницы», «5 ноября», «через неделю» -> «ГГГГ-ММ-ДД» или ""."""
    s = str(v or "").strip()
    if not s:
        return ""
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:T.*)?", s):
        return s[:10]
    try:
        from team import due_parse
        at, _ = due_parse(s)
    except Exception:  # noqa: BLE001
        at = None
    return at.date().isoformat() if at else ""


class DealsMixin:
    """Примесь к Clients: self.st, self._lock, self._get, self._save, self.note, self.title, self.now."""
    currency = staticmethod(lambda: "")

    def _deals(self, c):
        return c.setdefault("deals", [])

    def _deal(self, c, did):
        d = next((x for x in self._deals(c) if x["id"] == did), None)
        if not d:
            raise DealError("такой сделки нет")
        return d

    def deal_find(self, cid, words="", strict=False):
        """Сделка клиента по словам названия; открытая одна — она. strict — названа, а такой нет: DealError (новая). -> id."""
        c = self._get(cid)
        ds = [x for x in self._deals(c)]
        if not ds:
            raise DealError(f"у {self.title(c)} сделок нет")
        ws = [w[:5] for w in re.findall(r"[а-яёa-z0-9]{3,}", str(words or "").lower())]
        if ws:
            hit = [x for x in ds if any(w in x["title"].lower() for w in ws)]
            if len(hit) == 1:
                return hit[0]["id"]
            if len(hit) > 1:
                ds = hit
            elif strict:
                raise DealError("такой сделки нет")
        opened = [x for x in ds if x["stage"] in OPEN]
        if len(opened) == 1:
            return opened[0]["id"]
        if not opened:
            return sorted(ds, key=lambda x: -x.get("moved", 0))[0]["id"]
        raise DealError("у клиента несколько сделок: " + "; ".join(f"«{x['title']}»" for x in opened[:5]) + " — какая?")

    def deal_add(self, cid, title, amount=0, cur="", stage="lead", due="", note=""):
        title = re.sub(r"\s+", " ", str(title or "")).strip()[:160]
        stage = stage if stage in STAGES else (stage_of(stage) or "lead")
        amt = round(amount_of(amount), 2)
        with self._lock:
            c = self._get(cid)
            if not title:
                title = "Сделка" + (f" на {fmt_amount(amt, cur or self.currency())}" if amt else "")
            ts = time.time()
            d = {"id": uuid.uuid4().hex[:6], "title": title, "amount": amt, "cur": (cur or self.currency() or "").upper()[:6], "stage": stage,
                 "due": due_of(due), "created": ts, "moved": ts, "paid": ts if stage == "paid" else 0, "note": str(note or "")[:500]}
            self._deals(c).append(d)
            del self._deals(c)[:-200]
        self.note(cid, self._deal_line(d, new=True), kind="deal")
        return dict(d, cid=cid, client=self.title(self._get(cid)))

    def deal_set(self, cid, did, **f):
        """Правка сделки: title, amount, cur, stage, due, note. Смена этапа — строка в истории клиента."""
        with self._lock:
            c = self._get(cid)
            d = self._deal(c, did)
            old = d["stage"]
            if "title" in f and str(f["title"] or "").strip():
                d["title"] = re.sub(r"\s+", " ", str(f["title"])).strip()[:160]
            if "amount" in f:
                d["amount"] = round(amount_of(f["amount"]), 2)
            if f.get("cur"):
                d["cur"] = str(f["cur"]).upper()[:6]
            if "due" in f:
                d["due"] = due_of(f["due"])
            if "note" in f:
                d["note"] = str(f["note"] or "")[:500]
            if "income" in f:
                d["income"] = str(f["income"] or "")[:20]
            if f.get("stage"):
                st = f["stage"] if f["stage"] in STAGES else stage_of(f["stage"])
                if not st:
                    raise DealError(f"не поняла этап «{f['stage']}» — заявка, предложение, счёт, оплачено или отказ")
                if st != old:
                    d["stage"], d["moved"] = st, time.time()
                    d["paid"] = time.time() if st == "paid" else 0
            moved = d["stage"] != old
        if moved:
            self.note(cid, self._deal_line(d), kind="deal")
        else:
            with self._lock:
                self._save()
        return dict(d, cid=cid, client=self.title(self._get(cid)))

    def deal_del(self, cid, did):
        with self._lock:
            c = self._get(cid)
            n = len(self._deals(c))
            c["deals"] = [x for x in self._deals(c) if x["id"] != did]
            if len(c["deals"]) == n:
                raise DealError("такой сделки нет")
            self._save()
        return True

    def _deal_line(self, d, new=False):
        amt = f", {fmt_amount(d['amount'], d['cur'])}" if d.get("amount") else ""
        due = f", оплатить до {human_date(d['due'])}" if d["stage"] == "invoice" and d.get("due") else ""
        return f"Сделка «{d['title']}»: {STAGES[d['stage']].lower()}{amt}{due}" + (" (новая)" if new else "")

    def _deal_state(self, d, today):
        """-> (owed, overdue, stuck, days_still)."""
        days = int((time.time() - (d.get("moved") or d.get("created") or time.time())) / 86400)
        owed = d["stage"] == "invoice"
        overdue = owed and bool(d.get("due")) and d["due"] < today
        stuck = (d["stage"] in ("lead", "offer") and days >= STUCK_DAYS) or (owed and not d.get("due") and days >= OWED_DAYS)
        return owed, overdue, stuck, days

    def deals(self, stage="", cid=""):
        """Все сделки (или одного клиента) с клиентом и состоянием: owed, overdue, stuck, days."""
        today = self.now().date().isoformat()
        out = []
        for c in self.st["clients"].values():
            if cid and c["id"] != cid:
                continue
            for d in c.get("deals") or []:
                if stage and d["stage"] != stage:
                    continue
                owed, overdue, stuck, days = self._deal_state(d, today)
                out.append(dict(d, cid=c["id"], client=self.title(c), owed=owed, overdue=overdue, stuck=stuck, days=days))
        out.sort(key=lambda x: (not x["overdue"], not x["stuck"], -(x.get("moved") or 0)))
        return out

    def deals_board(self):
        """Студия: колонки по этапам с суммами; кто должен — итог по валютам; оплачено за 30 дней."""
        ds = self.deals()
        cut = time.time() - 30 * 86400
        cols = []
        for k, name in STAGES.items():
            items = [d for d in ds if d["stage"] == k and (k not in ("paid", "lost") or (d.get("moved") or 0) > cut)]
            cols.append({"stage": k, "name": name, "items": items, "sum": _sums(items)})
        owed = [d for d in ds if d["owed"]]
        return {"cols": cols, "owed": _sums(owed), "overdue": _sums([d for d in owed if d["overdue"]]), "n_overdue": sum(1 for d in owed if d["overdue"]),
                "stuck": sum(1 for d in ds if d["stuck"]), "paid30": _sums([d for d in ds if d["stage"] == "paid" and (d.get("paid") or 0) > cut])}

    # ---------- «Напомнить об оплате» и выгрузка (0.62; план «Идей Лиры»: «Лира сама напишет вежливое напоминание,
    # выгрузка сделок в таблицу») ----------
    def deal_remind_text(self, cid, did, me=""):
        """Вежливое напоминание об оплате по счёту -> {to, name, subject, body, overdue}."""
        with self._lock:
            c = self._get(cid)
            d = self._deal(c, did)
        if d["stage"] != "invoice":
            raise DealError("напомнить об оплате можно по выставленному счёту — эта сделка не на этапе «Счёт»")
        today = self.now().date().isoformat()
        over = bool(d.get("due")) and d["due"] < today
        who = (c.get("name") or "").split()[0] if c.get("name") and not c.get("company") else (c.get("name") or c.get("company") or "")
        amt = f" на {fmt_amount(d['amount'], d['cur'])}" if d.get("amount") else ""
        due = (f" Срок оплаты был {human_date(d['due'])}." if over else f" Срок оплаты — {human_date(d['due'])}.") if d.get("due") else ""
        body = (f"Здравствуйте{', ' + who if who else ''}!\n\n"
                f"Напоминаю об оплате счёта «{d['title']}»{amt}{'' if amt.endswith('.') else '.'}{due} Если оплата уже ушла — спасибо, просто дайте знать, "
                f"и я отмечу у себя.\n\nЕсли нужен счёт повторно или есть вопросы — напишите, всё пришлю.\n\n"
                f"С уважением{',' if me else ''}\n{me}".rstrip())
        return {"to": c.get("email") or "", "name": self.title(c), "subject": f"Напоминание об оплате: {d['title']}", "body": body, "overdue": over}

    def deal_reminded(self, cid, did, how="письмом"):
        """Отметка в истории клиента: напомнили об оплате (и дата — в сделке, reminded)."""
        with self._lock:
            c = self._get(cid)
            d = self._deal(c, did)
            d["reminded"] = time.time()
        self.note(cid, f"Напомнили об оплате {how}: «{d['title']}»", kind="deal")

    def deals_csv(self):
        """Все сделки таблицей (CSV для Excel: «;», UTF-8 с BOM) -> текст."""
        rows = [["Клиент", "Сделка", "Сумма", "Валюта", "Этап", "Оплатить до", "Срок прошёл", "Создана", "Изменена", "Оплачена", "Заметка"]]
        day = lambda t: time.strftime("%Y-%m-%d", time.localtime(t)) if t else ""   # noqa: E731
        for d in sorted(self.deals(), key=lambda x: (x["client"].lower(), x.get("created") or 0)):
            rows.append([d["client"], d["title"], (f"{d['amount']:.2f}".rstrip("0").rstrip(".").replace(".", ",") if d.get("amount") else ""),
                         d.get("cur") or "", STAGES[d["stage"]], d.get("due") or "", "да" if d["overdue"] else "", day(d.get("created")),
                         day(d.get("moved")), day(d.get("paid")), (d.get("note") or "").replace("\n", " ")])
        esc = lambda v: '"' + str(v).replace('"', '""') + '"' if any(ch in str(v) for ch in ';"\n') else str(v)   # noqa: E731
        return "\ufeff" + "\r\n".join(";".join(esc(v) for v in r) for r in rows) + "\r\n"

    def deals_summary(self, what=""):
        """Для модели: «кто нам должен?» (owed), «что зависло?» (stuck) или всё открытое."""
        ds = [d for d in self.deals() if d["stage"] in OPEN]
        if what == "owed":
            ds = [d for d in ds if d["owed"]]
            if not ds:
                return "Никто не должен: выставленных и неоплаченных счетов нет."
            tot = "; ".join(f"{fmt_amount(v, k)}" for k, v in _sums(ds).items())
            return (f"Нам должны (итого {tot}): " + "; ".join(
                f"{d['client']} — «{d['title']}» {fmt_amount(d['amount'], d['cur']) if d['amount'] else '(сумма не указана)'}"
                + (f", срок оплаты прошёл {human_date(d['due'])}" if d["overdue"] else f", оплатить до {human_date(d['due'])}" if d.get("due") else f", счёт {d['days']} дн. назад")
                for d in ds[:15]) + ".")
        if what == "stuck":
            ds = [d for d in ds if d["stuck"] or d["overdue"]]
            if not ds:
                return "Зависших сделок нет."
        if not ds:
            return "Открытых сделок нет."
        return "Сделки: " + "; ".join(
            f"{d['client']} — «{d['title']}»: {STAGES[d['stage']].lower()}" + (f", {fmt_amount(d['amount'], d['cur'])}" if d["amount"] else "")
            + (" — срок оплаты прошёл" if d["overdue"] else f" — без движения {d['days']} дн." if d["stuck"] else "") for d in ds[:20]) + "."


def to_money(money, d, client=""):
    """Оплачено — в доходы «Денег» один раз (d.income — id записи). -> id записи или ""."""
    if not money or d.get("stage") != "paid" or not d.get("amount") or d.get("income"):
        return ""
    try:
        it = money.add("income", d["amount"], d.get("cur") or None, "Клиенты", f"{client or d.get('client') or 'Клиент'}: {d['title']}"[:200])
        return it.get("id", "") if isinstance(it, dict) else ""
    except Exception:  # noqa: BLE001
        return ""


def _sums(items):
    out = {}
    for d in items:
        if d.get("amount"):
            out[d.get("cur") or ""] = round(out.get(d.get("cur") or "", 0) + d["amount"], 2)
    return out


def fmt_amount(n, cur):
    try:
        from money import fmt
        return fmt(float(n), cur) if cur else f"{n:,.2f}".replace(",", " ").replace(".", ",").removesuffix(",00")
    except Exception:  # noqa: BLE001
        return f"{n} {cur}".strip()


def human_date(iso):
    try:
        d = date.fromisoformat(str(iso)[:10])
    except ValueError:
        return str(iso or "")
    t = date.today()
    if d == t:
        return "сегодня"
    if d == t + timedelta(days=1):
        return "завтра"
    if d == t - timedelta(days=1):
        return "вчера"
    mon = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"][d.month - 1]
    return f"{d.day} {mon}" + (f" {d.year}" if d.year != t.year else "")

