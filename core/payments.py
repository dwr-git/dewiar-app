"""«Платежи» — реестр обязательных оплат (25.10, владелец: «каждый месяц я делаю оплаты коммунальных и вношу, за что и
сколько заплатил… это позволяет быть уверенным, что все важные вещи оплачены своевременно, всегда можно вернуться и
перепроверить… от ежедневного отличается логически — это стратегически важная система учёта серьёзных оплат»; «главное
гибко и универсально… а сколько за год оплатили за это, за это — красивые графики и диаграммы»).

Отличие от «Денег» (money.py): там — поток расходов за день; здесь — СЧЕТА, у каждого реквизиты («как платить»), срок,
история оплат по периодам, показания счётчика и вложения (платёжка, скриншот из банка, памятка ЕРИП).

Счёт (bill): id, name, kind — вид (KINDS: счётчик, постоянная сумма, кредит, раз в год, своё), group — для итогов
(«Коммунальные», «Связь», «Кредиты», …), icon (эмодзи), unit (куб, кВт·ч…), day — день срока в месяце, month — месяц
(для «раз в год»), autopay, amount — обычная сумма (для подсказки), total — сумма кредита, how — как платить и реквизиты,
phones, note, remind — напоминать о сроке, att — вложения, archived, created.
Оплата (pay): id, bill, date, period («ГГГГ-ММ» или «ГГГГ» для годовых), amount, reading — показание, used — расход
(сам из прошлого показания), note, status (paid | unpaid — «не погашено»), att, created.

Файлы: payments.json в STATE_DIR (через .tmp); вложения — в папке ассистента «Платежи/Вложения/<счёт>/» (их видит и
поиск по заметкам); «Платежи/<счёт>.md» — история человеческим текстом (переписывается сама, правки в .md не читаются).
Срок и напоминания: due(bill, period) — дата срока; status(...) — paid / unpaid / overdue / soon / wait; check_due() —
что пора напомнить (накануне и в день срока, один раз на период), Engine зовёт её раз в 10 минут."""
import calendar
import datetime as dt
import json
import re
import threading
import uuid
from pathlib import Path

KINDS = {
    "meter": {"title": "По счётчику", "hint": "газ, свет, вода — показание, расход и сумма", "icon": "🔥"},
    "fixed": {"title": "Постоянная сумма", "hint": "интернет, телефон, подписки", "icon": "🌐"},
    "loan": {"title": "Кредит или рассрочка", "hint": "платёж по графику и остаток", "icon": "🏦"},
    "yearly": {"title": "Раз в год", "hint": "страховка, налог, техосмотр", "icon": "📅"},
    "other": {"title": "Своё", "hint": "секция, кружок, аренда — что угодно", "icon": "🧾"},
}
GROUPS = ["Коммунальные", "Связь", "Кредиты", "Страховка и налоги", "Дети и семья", "Другое"]
_GROUP_RX = [("Коммунальные", r"газ|свет|электр|вод|отоплен|коммун|жкх|квартпл|мусор|канализ|тепло"),
             ("Связь", r"интернет|телефон|мобил|связ|тв\b|телевид|zala|byfly|белтелеком|mts|мтс|а1|life"),
             ("Кредиты", r"кредит|рассроч|ипотек|займ|долг"),
             ("Страховка и налоги", r"страхов|налог|техосмотр|осаго|каско|пошлин"),
             ("Дети и семья", r"сад|школ|кружок|секци|репетит|мам|пап|дет")]
_ICON_RX = [("🔥", r"газ"), ("💡", r"свет|электр"), ("💧", r"вод"), ("🌡️", r"отоплен|тепло"), ("🌐", r"интернет|byfly"),
            ("📱", r"телефон|мобил|мтс|а1|life"), ("📺", r"тв\b|телевид|zala"), ("🏦", r"кредит|ипотек|рассроч"),
            ("🛡️", r"страхов|осаго|каско"), ("🧾", r"налог"), ("🏠", r"квартпл|жкх|коммун"), ("🚗", r"машин|авто|техосмотр")]
MONTHS = ["январь", "февраль", "март", "апрель", "май", "июнь", "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь"]
MONTHS_GEN = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"]


def guess_group(name):
    n = (name or "").lower()
    return next((g for g, rx in _GROUP_RX if re.search(rx, n)), "Другое")


def guess_icon(name, kind="other"):
    n = (name or "").lower()
    return next((i for i, rx in _ICON_RX if re.search(rx, n)), KINDS.get(kind, KINDS["other"])["icon"])


def guess_unit(name):
    n = (name or "").lower()
    return "кВт·ч" if re.search(r"свет|электр", n) else "м³" if re.search(r"газ|вод", n) else "Гкал" if re.search(r"тепло|отоплен", n) else ""


def _num(v):
    if v is None or v == "":
        return None
    try:
        return round(float(str(v).replace(",", ".").replace(" ", "")), 3)
    except ValueError:
        return None


def _date(v):
    try:
        return dt.date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def fmt_money(n):
    """1234.5 -> «1 234,50»; целое — без копеек."""
    if n is None:
        return ""
    s = f"{float(n):,.2f}".replace(",", " ").replace(".", ",")
    return s[:-3] if s.endswith(",00") else s


class Payments:
    """Счета и оплаты; методы — под замком (зовут из окна, модели и проверки сроков). on_change — после сохранения."""

    def __init__(self, path, workspace=None):
        self.path = Path(path)
        self.ws = workspace
        self.on_change = None
        self._lock = threading.RLock()
        d = self._load()
        self.bills, self.pays, self.marks = d.get("bills", []), d.get("pays", []), d.get("marks", {})

    # ---------- хранение ----------
    def _load(self):
        try:
            d = json.loads(self.path.read_text(encoding="utf-8"))
            return d if isinstance(d, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save(self, bills=()):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"bills": self.bills, "pays": self.pays, "marks": self.marks}, ensure_ascii=False, indent=1),
                       encoding="utf-8")
        tmp.replace(self.path)
        for bid in set(bills):
            try:
                self._write_md(bid)
            except OSError:
                pass
        if self.on_change:
            try:
                self.on_change()
            except Exception:  # noqa: BLE001
                pass

    def bill(self, bid):
        """Счёт по id или по названию (без регистра, «за газ» → «Газ»). Нет — None."""
        with self._lock:
            b = next((x for x in self.bills if x["id"] == bid), None)
            if b is None and bid:
                q = re.sub(r"^(?:за|по|на)\s+", "", str(bid).strip().lower())
                cands = [x for x in self.bills if not x.get("archived")]
                b = next((x for x in cands if x["name"].lower() == q), None) \
                    or next((x for x in cands if q and (q in x["name"].lower() or x["name"].lower() in q)), None) \
                    or next((x for x in cands if q[:4] and x["name"].lower().startswith(q[:4])), None)
            return b

    # ---------- счета ----------
    def bill_save(self, data):
        """Создать (без id) или поправить счёт. -> счёт."""
        with self._lock:
            name = str(data.get("name") or "").strip()[:60]
            cur = self.bill(data["id"]) if data.get("id") else None
            if cur is None:
                if not name:
                    raise ValueError("нужно название платежа")
                if any(x["name"].lower() == name.lower() and not x.get("archived") for x in self.bills):
                    raise ValueError(f"платёж «{name}» уже есть")
                kind = data.get("kind") if data.get("kind") in KINDS else ("meter" if guess_unit(name) else "fixed")
                cur = {"id": uuid.uuid4().hex[:8], "name": name, "kind": kind, "group": guess_group(name),
                       "icon": guess_icon(name, kind), "unit": guess_unit(name) if kind == "meter" else "", "day": None,
                       "month": None, "autopay": False, "amount": None, "total": None, "how": "", "phones": "", "note": "",
                       "remind": True, "att": [], "archived": False, "created": dt.datetime.now().isoformat(timespec="seconds"),
                       "order": len(self.bills)}
                self.bills.append(cur)
            elif name:
                cur["name"] = name
            for k in ("kind", "group", "icon", "unit", "how", "phones", "note"):
                if k in data and data[k] is not None:
                    v = str(data[k]).strip()
                    if k == "kind" and v not in KINDS:
                        continue
                    cur[k] = v[:4000] if k in ("how", "note") else v[:200]
            for k in ("day", "month"):
                if k in data:
                    v = data[k]
                    v = int(v) if str(v or "").strip().isdigit() else None
                    cur[k] = v if v and 1 <= v <= (31 if k == "day" else 12) else None
            for k in ("amount", "total"):
                if k in data:
                    cur[k] = _num(data[k])
            for k in ("autopay", "remind", "archived"):
                if k in data:
                    cur[k] = bool(data[k])
            if "order" in data and isinstance(data["order"], int):
                cur["order"] = data["order"]
            self._save([cur["id"]])
            return dict(cur)

    def bill_delete(self, bid):
        """Удалить счёт вместе с историей (вложения остаются в папке ассистента). -> {ok}."""
        with self._lock:
            b = self.bill(bid)
            if not b:
                raise ValueError("нет такого платежа")
            self.bills.remove(b)
            self.pays = [p for p in self.pays if p["bill"] != b["id"]]
            self._save()
            if self.ws is not None:
                try:
                    (Path(self.ws.ensure()) / "Платежи" / f"{_safe(b['name'])}.md").unlink(missing_ok=True)
                except OSError:
                    pass
            return {"ok": True, "id": b["id"]}

    def reorder(self, ids):
        with self._lock:
            for i, bid in enumerate(ids or []):
                b = next((x for x in self.bills if x["id"] == bid), None)
                if b:
                    b["order"] = i
            self._save()
            return {"ok": True}

    # ---------- оплаты ----------
    def period_of(self, b, day):
        """Период оплаты по дате: годовой — «ГГГГ», остальные — «ГГГГ-ММ»."""
        return f"{day.year}" if b.get("kind") == "yearly" else f"{day.year}-{day.month:02d}"

    def prev_reading(self, bid, before_date, skip=None):
        """Последнее показание до даты (для расхода). -> число или None."""
        best = None
        for p in self.pays:
            if p["bill"] != bid or p.get("reading") is None or p["id"] == skip:
                continue
            d = _date(p["date"])
            if d and d < before_date and (best is None or d > best[0]):
                best = (d, p["reading"])
        return best[1] if best else None

    def pay_save(self, data):
        """Записать оплату (без id — новую) или поправить. Расход по счётчику — сам из прошлого показания, если не указан.
        -> оплата."""
        with self._lock:
            b = self.bill(data.get("bill") or "")
            cur = next((p for p in self.pays if p["id"] == data.get("id")), None) if data.get("id") else None
            if cur is None and not b:
                raise ValueError("какой платёж? Сначала добавьте его в «Платежи»")
            if cur is not None and b is None:
                b = self.bill(cur["bill"])
            day = _date(data.get("date")) or (_date(cur["date"]) if cur else None) or dt.date.today()
            if cur is None:
                cur = {"id": uuid.uuid4().hex[:8], "bill": b["id"], "date": day.isoformat(), "period": self.period_of(b, day),
                       "amount": None, "reading": None, "used": None, "note": "", "status": "paid", "att": [],
                       "created": dt.datetime.now().isoformat(timespec="seconds")}
                self.pays.append(cur)
            cur["bill"] = b["id"]
            cur["date"] = day.isoformat()
            per = str(data.get("period") or "").strip()
            if re.fullmatch(r"\d{4}(-\d{2})?", per):
                cur["period"] = per
            elif "date" in data:
                cur["period"] = self.period_of(b, day)
            for k in ("amount", "reading", "used"):
                if k in data:
                    cur[k] = _num(data[k])
            if "note" in data:
                cur["note"] = str(data.get("note") or "").strip()[:300]
            if data.get("status") in ("paid", "unpaid"):
                cur["status"] = data["status"]
            if b.get("kind") == "meter" and cur.get("reading") is not None and data.get("used") in (None, ""):
                prev = self.prev_reading(b["id"], day, skip=cur["id"])
                cur["used"] = round(cur["reading"] - prev, 3) if prev is not None and cur["reading"] >= prev else cur.get("used")
            if cur.get("amount") is None and cur["status"] == "paid" and b.get("amount") and data.get("auto_amount"):
                cur["amount"] = b["amount"]
            self._save([b["id"]])
            return dict(cur)

    def pay_delete(self, pid):
        with self._lock:
            p = next((x for x in self.pays if x["id"] == pid), None)
            if not p:
                raise ValueError("нет такой оплаты")
            self.pays.remove(p)
            self._save([p["bill"]])
            return {"ok": True, "id": pid, "bill": p["bill"]}

    def pays_of(self, bid):
        with self._lock:
            return sorted((dict(p) for p in self.pays if p["bill"] == bid), key=lambda p: (p["date"], p["created"]), reverse=True)

    # ---------- вложения ----------
    def attach(self, target, tid, name, data):
        """Вложение к счёту (target="bill") или к оплате ("pay"): bytes -> файл в «Платежи/Вложения/<счёт>/». -> запись вложения."""
        if self.ws is None:
            raise ValueError("папка ассистента недоступна")
        with self._lock:
            if target == "bill":
                obj = self.bill(tid)
                b = obj
            else:
                obj = next((p for p in self.pays if p["id"] == tid), None)
                b = self.bill(obj["bill"]) if obj else None
            if not obj or not b:
                raise ValueError("нет такого платежа")
            base = Path(self.ws.ensure()) / "Платежи" / "Вложения" / _safe(b["name"])
            base.mkdir(parents=True, exist_ok=True)
            stem, ext = Path(_safe(name or "файл")).stem[:60] or "файл", (Path(name or "").suffix or ".png").lower()[:8]
            if target == "pay":
                stem = f"{obj['date']} {stem}"
            p, n = base / f"{stem}{ext}", 2
            while p.exists():
                p, n = base / f"{stem} ({n}){ext}", n + 1
            p.write_bytes(data)
            rel = p.relative_to(Path(self.ws.ensure())).as_posix()
            item = {"id": uuid.uuid4().hex[:6], "name": p.name, "path": rel,
                    "img": ext in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp")}
            obj.setdefault("att", []).append(item)
            self._save([b["id"]])
            return item

    def detach(self, target, tid, aid):
        with self._lock:
            obj = self.bill(tid) if target == "bill" else next((p for p in self.pays if p["id"] == tid), None)
            if not obj:
                raise ValueError("нет такого платежа")
            a = next((x for x in obj.get("att") or [] if x["id"] == aid), None)
            if a:
                obj["att"].remove(a)
                if self.ws is not None:
                    try:
                        (Path(self.ws.ensure()) / a["path"]).unlink(missing_ok=True)
                    except OSError:
                        pass
            self._save([obj["id"] if target == "bill" else obj["bill"]])
            return {"ok": True}

    # ---------- сроки и статусы ----------
    def due(self, b, period):
        """Дата срока за период или None (срок не задан). 31-е в коротком месяце — последний день."""
        if not b.get("day"):
            return None
        try:
            if b.get("kind") == "yearly":
                y, m = int(period[:4]), int(b.get("month") or 1)
            else:
                y, m = int(period[:4]), int(period[5:7])
        except (ValueError, IndexError):
            return None
        return dt.date(y, m, min(int(b["day"]), calendar.monthrange(y, m)[1]))

    def status(self, b, period, today=None):
        """Статус счёта за период: {s: paid | unpaid | overdue | soon | wait | none, amount, used, pays: [id], due}."""
        today = today or dt.date.today()
        ps = [p for p in self.pays if p["bill"] == b["id"] and p.get("period") == period]
        paid = [p for p in ps if p.get("status") != "unpaid"]
        due = self.due(b, period)
        out = {"amount": round(sum(p.get("amount") or 0 for p in paid), 2) if paid else None,
               "used": round(sum(p.get("used") or 0 for p in paid), 3) if any(p.get("used") is not None for p in paid) else None,
               "pays": [p["id"] for p in ps], "due": due.isoformat() if due else None}
        if paid:
            out["s"] = "paid"
        elif ps:
            out["s"] = "unpaid"
        elif due is None:
            out["s"] = "none"
        elif b.get("autopay"):                         # автооплата — спишется сама: не «просрочено», а «ждёт списания»
            out["s"] = "wait"
        elif today > due:
            out["s"] = "overdue"
        elif (due - today).days <= 3:
            out["s"] = "soon"
        else:
            out["s"] = "wait"
        return out

    def cur_period(self, b, today=None):
        today = today or dt.date.today()
        return f"{today.year}" if b.get("kind") == "yearly" else f"{today.year}-{today.month:02d}"

    def overview(self, today=None):
        """Для окна и голоса: счета с текущим статусом, последней оплатой и итогом года. -> {bills, year, total_year, open}."""
        today = today or dt.date.today()
        with self._lock:
            out = []
            for b in sorted(self.bills, key=lambda x: (x.get("archived", False), x.get("order", 0), x["name"].lower())):
                ps = sorted((p for p in self.pays if p["bill"] == b["id"]), key=lambda p: p["date"])
                last = ps[-1] if ps else None
                year_sum = round(sum(p.get("amount") or 0 for p in ps if p["date"][:4] == str(today.year) and p.get("status") != "unpaid"), 2)
                st = self.status(b, self.cur_period(b, today), today)
                x = dict(b, now=st, last=dict(last) if last else None, year_sum=year_sum, count=len(ps))
                if b.get("kind") == "loan" and b.get("total"):
                    x["left"] = round(max(0.0, b["total"] - sum(p.get("amount") or 0 for p in ps if p.get("status") != "unpaid")), 2)
                out.append(x)
            open_ = [x for x in out if not x.get("archived") and x["now"]["s"] in ("overdue", "soon", "unpaid")]
            return {"bills": out, "year": today.year, "total_year": round(sum(x["year_sum"] for x in out), 2), "open": len(open_),
                    "kinds": KINDS, "groups": GROUPS}

    def year_grid(self, year, today=None):
        """Таблица года: {year, months: [«ГГГГ-ММ»…], rows: [{bill, cells: [статус × 12] или [1 ячейка] для годовых}]}."""
        today = today or dt.date.today()
        with self._lock:
            rows = []
            for b in sorted(self.bills, key=lambda x: (x.get("order", 0), x["name"].lower())):
                if b.get("archived"):
                    continue
                if b.get("kind") == "yearly":
                    cells = [self.status(b, str(year), today)]
                else:
                    cells = []
                    for m in range(1, 13):
                        per = f"{year}-{m:02d}"
                        c = self.status(b, per, today)
                        if c["s"] in ("wait", "none", "soon") and dt.date(year, m, 1) > today:
                            c["s"] = "future"
                        elif c["s"] in ("wait", "none") and (year, m) < (today.year, today.month) and not c["pays"]:
                            created = _date(b.get("created")) or today
                            c["s"] = "before" if (year, m) < (created.year, created.month) else ("missed" if b.get("day") else "none")
                        cells.append(c)
                rows.append({"bill": {k: b.get(k) for k in ("id", "name", "icon", "kind", "unit", "group", "day", "month")}, "cells": cells})
            return {"year": year, "months": [f"{year}-{m:02d}" for m in range(1, 13)], "rows": rows}

    def stats(self, year, today=None):
        """Аналитика года: итог и прошлый год, по счетам, по группам (кольцо), по месяцам (столбцы по счетам), по счётчикам —
        расход и цена единицы по месяцам (тариф)."""
        with self._lock:
            def paid_in(y):
                return [p for p in self.pays if p["date"][:4] == str(y) and p.get("status") != "unpaid" and p.get("amount")]
            cur, prev = paid_in(year), paid_in(year - 1)
            names = {b["id"]: b for b in self.bills}
            by_bill, by_group = {}, {}
            for p in cur:
                b = names.get(p["bill"])
                if not b:
                    continue
                by_bill[b["id"]] = by_bill.get(b["id"], 0) + p["amount"]
                g = b.get("group") or "Другое"
                by_group[g] = by_group.get(g, 0) + p["amount"]
            prev_by = {}
            for p in prev:
                prev_by[p["bill"]] = prev_by.get(p["bill"], 0) + p["amount"]
            months = [{"m": f"{year}-{m:02d}", "by": {}} for m in range(1, 13)]
            for p in cur:
                mi = int(p["date"][5:7]) - 1
                months[mi]["by"][p["bill"]] = round(months[mi]["by"].get(p["bill"], 0) + p["amount"], 2)
            meters = []
            for b in self.bills:
                if b.get("kind") != "meter":
                    continue
                pts = []
                for p in sorted((p for p in self.pays if p["bill"] == b["id"] and p["date"][:4] in (str(year), str(year - 1))), key=lambda p: p["date"]):
                    if p.get("used") or p.get("amount"):
                        pts.append({"date": p["date"], "period": p.get("period"), "used": p.get("used"), "amount": p.get("amount"),
                                    "rate": round(p["amount"] / p["used"], 4) if p.get("amount") and p.get("used") else None})
                if pts:
                    meters.append({"bill": b["id"], "name": b["name"], "icon": b.get("icon"), "unit": b.get("unit") or "", "points": pts})
            total, total_prev = round(sum(by_bill.values()), 2), round(sum(prev_by.values()), 2)
            return {"year": year, "total": total, "total_prev": total_prev, "prev_months": len({p["date"][:7] for p in prev}),
                    "by_bill": sorted(({"id": k, "name": names[k]["name"], "icon": names[k].get("icon"), "sum": round(v, 2),
                                        "prev": round(prev_by.get(k, 0), 2)} for k, v in by_bill.items()), key=lambda x: -x["sum"]),
                    "by_group": sorted(({"name": k, "sum": round(v, 2)} for k, v in by_group.items()), key=lambda x: -x["sum"]),
                    "months": months, "meters": meters, "years": sorted({int(p["date"][:4]) for p in self.pays} | {year}, reverse=True)}

    def check_due(self, today=None, now_hour=None):
        """Что пора напомнить: [(bill, текст)] — накануне срока (с 10 утра) и в день срока, если за период ещё не оплачено;
        каждое — один раз (marks). Автооплату не напоминаем."""
        today = today or dt.date.today()
        hour = dt.datetime.now().hour if now_hour is None else now_hour
        out = []
        with self._lock:
            for b in self.bills:
                if b.get("archived") or not b.get("remind", True) or b.get("autopay") or not b.get("day"):
                    continue
                per = self.cur_period(b, today)
                due = self.due(b, per)
                if due is None or self.status(b, per, today)["s"] in ("paid", "unpaid"):
                    continue
                left = (due - today).days
                stage = "day" if left == 0 else "before" if left == 1 and hour >= 10 else None
                if not stage:
                    continue
                key = f"{b['id']}:{per}:{stage}"
                if self.marks.get(key):
                    continue
                self.marks[key] = today.isoformat()
                last = next(iter(sorted((p for p in self.pays if p["bill"] == b["id"] and p.get("amount")), key=lambda p: p["date"], reverse=True)), None)
                hint = f" В прошлый раз — {fmt_money(last['amount'])}." if last else ""
                meter = " Не забудьте показания." if b.get("kind") == "meter" else ""
                out.append((b, f"{'Сегодня' if stage == 'day' else 'Завтра'} срок оплаты: {b['name']}.{meter}{hint}"))
            if out:
                old = (today - dt.timedelta(days=120)).isoformat()
                self.marks = {k: v for k, v in self.marks.items() if v >= old}
                self._save()
        return out

    # ---------- голосом и модели ----------
    def text_report(self, what="", today=None):
        """Ответ словами: what — «open» (что не оплачено), название счёта (история и как платить) или пусто (сводка)."""
        today = today or dt.date.today()
        ov = self.overview(today)
        if not ov["bills"]:
            return "Платежей пока нет. Добавьте их в студии — раздел «Платежи», или скажите «добавь платёж: газ, до 25-го»."
        if what and what != "open":
            b = self.bill(what)
            if not b:
                return f"Платежа «{what}» нет. Есть: " + ", ".join(x["name"] for x in ov["bills"] if not x.get("archived")) + "."
            ps = self.pays_of(b["id"])[:6]
            lines = [f"«{b['name']}»" + (f", срок — {b['day']}-е число" if b.get("day") else "") + (", автооплата" if b.get("autopay") else "") + "."]
            if b.get("how"):
                lines.append("Как платить: " + b["how"].strip())
            if b.get("phones"):
                lines.append("Телефоны: " + b["phones"].strip())
            if ps:
                lines.append("Последние оплаты: " + "; ".join(
                    f"{_d(p['date'])} — {fmt_money(p['amount']) if p.get('amount') is not None else 'без суммы'}"
                    + (f", показание {fmt_num(p['reading'])}" if p.get("reading") is not None else "")
                    + (f", расход {fmt_num(p['used'])} {b.get('unit') or ''}".rstrip() if p.get("used") is not None else "")
                    + (" (не погашено)" if p.get("status") == "unpaid" else "") for p in ps) + ".")
            return "\n".join(lines)
        rows = [x for x in ov["bills"] if not x.get("archived")]
        bad = [x for x in rows if x["now"]["s"] in ("overdue", "unpaid")]
        soon = [x for x in rows if x["now"]["s"] == "soon"]
        wait = [x for x in rows if x["now"]["s"] in ("wait", "none")]
        done = [x for x in rows if x["now"]["s"] == "paid"]
        parts = []
        if bad:
            parts.append("не оплачено: " + ", ".join(f"«{x['name']}»" + (f" (срок был {_human(x['now']['due'])})" if x["now"].get("due") else "") for x in bad))
        if soon:
            parts.append("скоро срок: " + ", ".join(f"«{x['name']}» — {_human(x['now']['due'])}" for x in soon))
        if what == "open":
            if not bad and not soon:
                return "За этот месяц всё оплачено или срок ещё не подошёл." + (f" Оплачено: {', '.join('«' + x['name'] + '»' for x in done)}." if done else "")
            if wait:
                parts.append("ещё не записано, но срок не скоро: " + ", ".join(f"«{x['name']}»" for x in wait))
            return _cap("; ".join(parts)) + "."
        if done:
            parts.append("оплачено в этом месяце: " + ", ".join(f"«{x['name']}»" for x in done))
        parts.append(f"всего за {today.year} год — {fmt_money(ov['total_year'])}")
        return _cap("; ".join(parts)) + "."

    def _write_md(self, bid):
        """«Платежи/<счёт>.md» — история человеческим текстом (видна поиску по заметкам и в Obsidian)."""
        if self.ws is None:
            return
        b = next((x for x in self.bills if x["id"] == bid), None)
        if not b:
            return
        base = Path(self.ws.ensure()) / "Платежи"
        base.mkdir(parents=True, exist_ok=True)
        lines = [f"# {b['name']}", "", "_Файл обновляется сам из раздела «Платежи». Записать оплату: «оплатил газ 47,84, "
                 "показания 28135»._", ""]
        meta = [KINDS.get(b.get("kind"), KINDS["other"])["title"]]
        if b.get("day"):
            meta.append(f"срок — {b['day']}-е" + (f" {MONTHS_GEN[b['month'] - 1]}" if b.get("kind") == "yearly" and b.get("month") else ""))
        if b.get("autopay"):
            meta.append("автооплата")
        lines += ["**" + " · ".join(meta) + "**", ""]
        if b.get("how"):
            lines += ["## Как платить", "", b["how"].strip(), ""]
        if b.get("phones"):
            lines += ["**Телефоны:** " + b["phones"].strip(), ""]
        ps = sorted((p for p in self.pays if p["bill"] == bid), key=lambda p: p["date"], reverse=True)
        if ps:
            unit = b.get("unit") or ""
            lines += ["## Оплаты", "", "| Дата | Показание | Расход | Сумма | Заметка |", "|---|---:|---:|---:|---|"]
            for p in ps:
                lines.append(f"| {_d(p['date'])} | {fmt_num(p.get('reading'))} | {(fmt_num(p.get('used')) + ' ' + unit).strip() if p.get('used') is not None else ''} | "
                             f"{fmt_money(p.get('amount'))} | {(p.get('note') or '') + (' · не погашено' if p.get('status') == 'unpaid' else '')} |")
            lines.append("")
        (base / f"{_safe(b['name'])}.md").write_text("\n".join(lines), encoding="utf-8")


def fmt_num(v):
    if v is None:
        return ""
    v = float(v)
    return (f"{v:,.0f}" if v == int(v) else f"{v:,.3f}".rstrip("0").rstrip(".")).replace(",", " ").replace(".", ",")


def _d(iso):
    d = _date(iso)
    return f"{d.day:02d}.{d.month:02d}.{d.year % 100:02d}" if d else str(iso or "")


def _cap(s):
    return s[:1].upper() + s[1:]


def _human(iso):
    d = _date(iso)
    return f"{d.day} {MONTHS_GEN[d.month - 1]}" if d else str(iso or "")


def _safe(name):
    return re.sub(r'[\\/:*?"<>|\n\r\t]+', " ", str(name or "")).strip()[:80] or "Платёж"


# ---------- перенос из старого органайзера ----------
_DATE_RX = re.compile(r"(?<!\d)(\d{1,2})[./](\d{1,2})[./](\d{2,4})(?!\d)")
_UNIT_RX = re.compile(r"(\d[\d\s]*(?:[.,]\d+)?)\s*(куб\w*|м3|м³|квт\w*|киловат\w*|kwh|гкал)", re.I)
_MONEY_RX = re.compile(r"(\d[\d\s]*(?:[.,]\d{1,2})?)\s*(?:р\.?|руб\w*|byn|бел\.?\s*руб\w*)(?![а-я])", re.I)


def parse_import(text, today=None):
    """Текст из старого органайзера -> черновик для переноса: [{name, kind, how, pays: [{date, reading, used, amount, note,
    status}]}]. Раздел — заголовок (строка без даты, обычно с «:» или жирная) и строки «ДД.ММ.ГГ - …» под ним; разделители
    «~~~~» и пустые строки. Сумма — число с «р./руб.» или последнее число после «=»; показание — первое число после даты;
    расход — число перед «куб/кВт». Всё, что не разобралось, остаётся в «Как платить» — человек проверит перед переносом."""
    today = today or dt.date.today()
    secs, cur = [], None
    raw_lines = [ln.strip().strip("*").strip() for ln in str(text or "").replace("\r", "").split("\n")]
    SEP = re.compile(r"[~\-=_—–*#\s]{3,}")
    blocks = any(SEP.fullmatch(ln) for ln in raw_lines if ln)       # есть разделители «~~~~» — раздел = блок между ними
    lines, starts = [], set()
    for ln in raw_lines:
        if ln and SEP.fullmatch(ln):
            starts.add(len(lines))
        elif ln:
            lines.append(ln)
    starts.add(0)
    dated = [bool(_DATE_RX.search(ln[:14])) for ln in lines]
    for i, line in enumerate(lines):
        if blocks and i in starts and not dated[i]:
            cur = None                                     # начало блока — новый раздел, его первая строка — заголовок
        m = _DATE_RX.search(line[:14])
        if m and cur is not None:
            d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            y = y + 2000 if y < 100 else y
            try:
                day = dt.date(y, mo, d)
            except ValueError:
                cur["how"].append(line)
                continue
            rest = line[m.end():].strip(" -—–:")
            p = {"date": day.isoformat(), "reading": None, "used": None, "amount": None, "note": "", "status": "paid"}
            mu = _UNIT_RX.search(rest)
            if mu:
                p["used"] = _num(mu.group(1))
            mm = list(_MONEY_RX.finditer(rest))
            if mm:
                p["amount"] = _num(mm[-1].group(1))
            else:
                eq = re.findall(r"=\s*(\d[\d\s]*(?:[.,]\d{1,2})?)", rest)
                if eq:
                    p["amount"] = _num(eq[-1])
            first = re.match(r"\(?\s*(\d[\d\s]{0,9}(?:[.,]\d+)?)", rest)
            if first and not (mu and mu.start() == first.start(1) - (1 if rest.startswith("(") else 0)) and not (mm and mm[0].start() <= first.start(1) <= mm[0].end()):
                v = _num(first.group(1))
                if v is not None and v != p["amount"] and v != p["used"]:
                    p["reading"] = v
            if re.search(r"не\s+погаш|не\s+оплач|долг", rest, re.I):
                p["status"] = "unpaid"
            if re.search(r"авто\s*оплат|автооплат|автоматическ\w*\s+оплат", rest, re.I):
                p["note"] = "автооплата"
            extra = re.sub(r"\s+", " ", re.sub(r"\d[\d\s.,]*|куб\w*|квт\w*|киловат\w*|р\.|руб\w*|[=()\-—:;,+]|автоматическ\w*\s+оплат\w*|автооплат\w*|не\s+погашен\w*", " ", rest, flags=re.I)).strip()
            if extra and len(extra) > 3:
                p["note"] = (p["note"] + "; " if p["note"] else "") + extra[:120]
            cur["pays"].append(p)
            continue
        # заголовок раздела: строка без даты в начале нового блока — «ГАЗ: …», «За Электричество:», «КРЕДИТ счёт 123…»;
        # название — слова до двоеточия, тире или первой цифры
        head = re.match(r"^(?:за\s+)?([А-ЯЁA-Za-zа-яё][^:\d—–]{1,40}?)\s*(?:[:—–]|\s-\s|(?=\d)|$)\s*(.*)$", line)
        new_block = cur is None or (not blocks and bool(cur["pays"]))
        soon_dates = any(dated[i + 1:i + 6])
        if head and new_block and (soon_dates or len(line) < 60):
            name = re.sub(r"^(?:за|по)\s+", "", head.group(1).strip(" :.-"), flags=re.I)
            name = re.sub(r"\s+(?:сч[её]т|л/с|лиц\.?\s*сч[её]т|договор|№).*$", "", name, flags=re.I).strip() or name
            name = name.capitalize() if name.isupper() else name[:1].upper() + name[1:]
            rest = line[len(head.group(0)) - len(head.group(2)):].strip() if head.group(2) else ""
            if not line[:1].isupper() or len(name.split()) > 4:      # «показания давать с 20 по 7…» — это не название
                cur = {"name": "", "how": [line], "pays": []}
            else:
                cur = {"name": name[:40], "how": [line] if re.search(r"\d{4,}", line) and not rest else ([rest] if rest else []), "pays": []}
            secs.append(cur)
        elif cur is not None:
            cur["how"].append(line)
        else:
            cur = {"name": "Без названия", "how": [line], "pays": []}
            secs.append(cur)
    out = []
    for s in secs:
        if not s["pays"] and not s["how"]:
            continue
        if not s["name"]:
            s["name"] = f"Платёж {len(out) + 1}"                 # название человек впишет при проверке
        has_meter = any(p["used"] or p["reading"] for p in s["pays"]) or bool(guess_unit(s["name"]))
        kind = "loan" if re.search(r"кредит|рассроч", s["name"], re.I) else "meter" if has_meter else "fixed"
        days = [int(p["date"][8:10]) for p in s["pays"]]
        out.append({"name": s["name"], "kind": kind, "how": "\n".join(s["how"]).strip(), "day": max(set(days), key=days.count) if days else None,
                    "autopay": sum(1 for p in s["pays"] if "автооплата" in p["note"]) > len(s["pays"]) / 2 if s["pays"] else False,
                    "pays": sorted(s["pays"], key=lambda p: p["date"])})
    return out


def import_apply(pm, items):
    """Перенести черновик parse_import (после проверки человеком): счета создаются (или находятся по имени), оплаты
    добавляются без повторов (та же дата и сумма). -> {bills, pays}."""
    nb = npays = 0
    for it in items or []:
        name = str(it.get("name") or "").strip()
        if not name or it.get("skip"):
            continue
        b = pm.bill(name)
        if not b or b["name"].lower() != name.lower():
            b = pm.bill_save({"name": name, "kind": it.get("kind"), "how": it.get("how") or "", "day": it.get("day"),
                              "autopay": bool(it.get("autopay"))})
            nb += 1
        have = {(p["date"], p.get("amount")) for p in pm.pays if p["bill"] == b["id"]}
        for p in sorted(it.get("pays") or [], key=lambda p: p.get("date") or ""):
            if (p.get("date"), _num(p.get("amount"))) in have:
                continue
            pm.pay_save(dict({k: p.get(k) for k in ("date", "amount", "reading", "used", "note", "status")}, bill=b["id"]))
            npays += 1
    return {"bills": nb, "pays": npays}


# ---------- голосом ----------
_SYN = {"свет": "электр", "электроэнерг": "электр", "электричеств": "электр", "квартплат": "коммун", "жкх": "коммун",
        "инет": "интернет", "мобильн": "телефон", "сотов": "телефон"}
PAY_VERB = r"(?:оплатил[аи]?|заплатил[аи]?|внес(?:ла|ли)?|внёс|перевел[аи]?|перевёл|погасил[аи]?|отдал[аи]?)"
PAY_RX = re.compile(r"^(?:[\w-]+,\s*)?(?:я\s+)?(?:сегодня\s+|вчера\s+)?" + PAY_VERB + r"\s+(?P<rest>.+)$", re.I)
OPEN_RX = re.compile(r"(?:что|какие|какой|какое|чего)\s+(?:у\s+меня\s+|я\s+|мы\s+)?(?:ещ[её]\s+)?(?:не\s+оплачен\w*|не\s+заплачен\w*|не\s+оплатил\w*|не\s+заплатил\w*|осталось\s+оплатить|"
                     r"надо\s+оплатить|нужно\s+оплатить)|вс[её]\s+ли\s+(?:у\s+меня\s+)?оплачен\w*|(?:какие|что\s+за)\s+платеж\w*\s+(?:остал\w*|скоро|на\s+этой)",
                     re.I)
HOW_RX = re.compile(r"(?:как|куда|где)\s+(?:мне\s+)?(?:платить|оплачивать|оплатить|заплатить)\s+(?:за\s+)?(?P<b>.+?)\??$|"
                    r"(?:реквизиты|номер\s+(?:абонента|лицевого\s+сч[её]та)|лицевой\s+сч[её]т)\s+(?:для\s+|за\s+|по\s+|от\s+)?(?P<b2>.+?)\??$", re.I)
SUM_RX = re.compile(r"сколько\s+(?:за\s+(?P<y0>этот\s+|прошлый\s+)?год\s+)?(?:я\s+|мы\s+)?(?:всего\s+)?(?:заплатил\w*|отдал\w*|платил\w*|потратил\w*|ушло)\s+(?:за|на)\s+(?P<b>.+?)"
                    r"(?:\s+(?:в|за)\s+(?P<y>этом|прошлом|\d{4})\s*(?:году|год)?)?\??$", re.I)


def _stems(t):
    out = []
    for w in re.findall(r"[а-яёa-z]+", (t or "").lower().replace("ё", "е")):
        s = next((v for k, v in _SYN.items() if w.startswith(k)), w[:5] if len(w) > 4 else w)
        out.append(s)
    return out


def match_bill(pm, text):
    """Счёт, названный во фразе («за свет» → «Электричество»). -> счёт или None."""
    ws = set(_stems(text))
    best, score = None, 0
    for b in pm.bills:
        if b.get("archived"):
            continue
        bs = _stems(b["name"])
        k = sum(1 for s in bs if s in ws or any(w.startswith(s) or s.startswith(w) for w in ws if len(w) >= 3 and len(s) >= 3))
        if k > score:
            best, score = b, k
    return best


def parse_voice(text, pm):
    """Фраза про платежи -> {"op": "pay", bill, amount, reading, used, date} | {"op": "open"} | {"op": "how", bill}
    | {"op": "sum", bill, year} | None. Оплата — только если назван существующий счёт (иначе это «Деньги»)."""
    t = " ".join((text or "").replace("ё", "е").split()).strip(" .!")
    if not t or not pm.bills:
        return None
    if OPEN_RX.search(t):
        return {"op": "open"}
    m = SUM_RX.search(t)
    if m:
        b = match_bill(pm, m.group("b"))
        if b:
            y = dt.date.today().year
            w = (m.group("y") or (m.group("y0") or "").strip() or "").lower()
            return {"op": "sum", "bill": b, "year": y - 1 if w in ("прошлом", "прошлый") else int(w) if w.isdigit() else y}
    m = HOW_RX.search(t)
    if m:
        b = match_bill(pm, m.group("b") or m.group("b2") or "")
        if b:
            return {"op": "how", "bill": b}
    m = PAY_RX.match(t)
    if not m:
        return None
    rest = m.group("rest")
    b = match_bill(pm, rest.split(",")[0] if "," in rest[:30] else rest[:40])
    if not b:
        return None
    reading = used = None
    mr = re.search(r"показани\w*\s*(?:счетчика\s*)?(?:—|-|:)?\s*(\d[\d\s]*(?:[.,]\d+)?)", rest, re.I)
    if mr:
        reading = _num(mr.group(1))
        rest = rest[:mr.start()] + " " + rest[mr.end():]
    mu = re.search(r"(?:расход\s*)?(\d[\d\s]*(?:[.,]\d+)?)\s*(?:куб\w*|м3|м³|квт\w*|киловат\w*)", rest, re.I)
    if mu:
        used = _num(mu.group(1))
        rest = rest[:mu.start()] + " " + rest[mu.end():]
    amount = None
    mk = re.search(r"(\d[\d\s]*)\s*(?:руб\w*|р\.?)\s*(?:и\s+)?(\d{1,2})\s*коп\w*", rest, re.I)
    if mk:
        amount = _num(mk.group(1)) + int(mk.group(2)) / 100
    else:
        mm = re.search(r"(\d[\d\s]*(?:[.,]\d{1,2})?)", rest)
        if mm:
            amount = _num(mm.group(1))
        else:
            try:
                from money import words_to_number
                amount = words_to_number(rest)[0] or None
            except Exception:  # noqa: BLE001
                amount = None
    day = dt.date.today() - dt.timedelta(days=1) if re.search(r"\bвчера\b", t, re.I) else dt.date.today()
    unpaid = bool(re.search(r"не\s+погаш|не\s+прош", t, re.I))
    if amount is None and reading is None:
        return None
    return {"op": "pay", "bill": b, "amount": round(amount, 2) if amount else None, "reading": reading, "used": used,
            "date": day.isoformat(), "status": "unpaid" if unpaid else "paid"}


def year_sum(pm, bid, year):
    with pm._lock:
        ps = [p for p in pm.pays if p["bill"] == bid and p["date"][:4] == str(year) and p.get("status") != "unpaid" and p.get("amount")]
        return round(sum(p["amount"] for p in ps), 2), len(ps)
