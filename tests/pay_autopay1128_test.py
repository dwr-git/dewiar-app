"""28.11 (человек со скриншотом «Платежей»: «у „Интернета“ — „Автооплата 25 ноября“, дата прошла, последняя оплата
25.10 — почему не сработало 25.11?»). Автооплата списывается в банке сама, а программа её не записывала — карточка
выглядела так, будто автооплата не прошла. Теперь в день срока оплата записывается сама (обычной суммой или прошлой
оплатой, заметка «записано само»); удалили — за этот период не повторяет; суммы не знаем — не выдумывает, а просит
проверить; двумя компьютерами — одна запись (id из счёта и периода)."""
import datetime as dt
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
import payments as P  # noqa: E402

fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


class WS:
    def __init__(self, root):
        self.root = root

    def ensure(self):
        self.root.mkdir(parents=True, exist_ok=True)
        return self.root


tmp = Path(tempfile.mkdtemp())
pm = P.Payments(tmp / "p.json", WS(tmp / "ws"))
net = pm.bill_save({"name": "Интернет", "day": 25, "autopay": True})
mom = pm.bill_save({"name": "Маме на интернет", "day": 10, "autopay": True})
gas = pm.bill_save({"name": "Газ", "day": 25, "autopay": True})
for b in pm.bills:
    b["created"] = "2026-01-01T10:00:00"
pm.pay_save({"bill": net["id"], "date": "2026-10-25", "amount": 75, "note": "автооплата"})

ok(pm.autopay_due(dt.date(2026, 11, 24)) == [], "до срока — ничего не записывает")
got = pm.autopay_due(dt.date(2026, 11, 26))
ok([(b["name"], p["date"], p["amount"], p["period"]) for b, p in got] == [("Интернет", "2026-11-25", 75, "2026-11")],
   f"после срока — оплата за ноябрь записана сама, суммой прошлой оплаты, датой срока: {[(b['name'], p) for b, p in got]}")
ok("записано само" in got[0][1]["note"] and pm.status(pm.bill(net["id"]), "2026-11", dt.date(2026, 11, 26))["s"] == "paid",
   "заметка «записано само», карточка — «Оплачено»")
ok(pm.autopay_due(dt.date(2026, 11, 27)) == [], "второй раз за период — не пишет")
pm.pay_delete(got[0][1]["id"])
ok(pm.autopay_due(dt.date(2026, 11, 28)) == [], "удалили (банк не списал) — за этот период не повторяет")
ok(all(b["name"] != "Маме на интернет" for b, _ in pm.autopay_due(dt.date(2026, 11, 28))), "суммы не знаем — не выдумывает")
pm2 = P.Payments(tmp / "p.json", WS(tmp / "ws"))
d = pm2.autopay_due(dt.date(2026, 12, 26))
ok(all(b["name"] != "Газ" for b, _ in d), "по счётчику — не пишет: сумма каждый раз своя")
ok([p["id"] for _, p in d] == [f"au{net['id'][:6]}202612"], f"id из счёта и периода — синхронизация не задвоит: {[p['id'] for _, p in d]}")
src = (ROOT / "ui/studio/pay.js").read_text(encoding="utf-8")
ok("— проверьте" in src, "студия: срок автооплаты прошёл, а записи нет — «проверьте», а не будто впереди")
ok("self.payments.autopay_due()" in (ROOT / "core/engine_pay.py").read_text(encoding="utf-8"), "ядро проверяет автооплаты каждые 10 минут")

print("ИТОГ:", "все проверки пройдены" if not fails else f"не пройдено {len(fails)}")
sys.exit(1 if fails else 0)
