"""Подарок месяца (1.0.31 — на сайте) теперь и говорится человеку (владелец 20.11: «при начислении сообщать… и о том,
что если не потратят, оно сгорит»): один раз за месяц, на компьютере и телефоне; без подарка и при пустом — молчим."""
import os, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
import cloud as C  # noqa: E402

bad = 0
def ok(c, m):
    global bad
    bad += 0 if c else 1
    print(("✅ " if c else "❌ ") + m)


class S:
    def __init__(self): self.d = {"cloud": {"gift_seen": ""}, "llm": {"active": C.PROFILE_ID}}
    def get(self, a, b=None): return self.d.get(a, {}).get(b) if b else self.d.get(a)
    def update(self, x):
        for k, v in x.items(): self.d.setdefault(k, {}).update(v)


s = S(); cl = C.Cloud(s, lambda *a, **k: None); got = []
cl.on_gift = got.append
g = {"amount": 0.25, "left": 0.25, "until": "2026-12-01"}
cl._set({"balance": 1, "gift": g})
ok(len(got) == 1, "подарок пришёл — сказали")
cl._set({"balance": 1, "gift": dict(g, left=0.2)})
ok(len(got) == 1, "тот же месяц — второй раз не говорим")
cl2 = C.Cloud(s, lambda *a, **k: None); cl2.on_gift = got.append; cl2._set({"balance": 1, "gift": g})
ok(len(got) == 1, "после перезапуска — тоже не повторяем (помним месяц в настройках)")
cl._set({"balance": 1, "gift": {"amount": 0.25, "left": 0.25, "until": "2027-01-01"}})
ok(len(got) == 2, "новый месяц — снова")
s3 = S(); cl3 = C.Cloud(s3, lambda *a, **k: None); g3 = []; cl3.on_gift = g3.append
cl3._set({"balance": 0, "gift": {"amount": 0.25, "left": None, "until": "2026-12-01"}})
cl3._set({"balance": 0, "gift": None})
ok(not g3, "подарка в этом месяце не было (новый ключ) или подарков нет — молчим")
s4 = S(); s4.d["llm"]["active"] = "local"; cl4 = C.Cloud(s4, lambda *a, **k: None); g4 = []; cl4.on_gift = g4.append
cl4._set({"balance": 1, "gift": g})
ok(not g4, "облако — не активная модель — не отвлекаем")
t = C.gift_month_text(g)
ok("0,25 талера" in t and "1 декабря" in t and "сгорит" in t and "первым" in t, f"текст: {t}")
ok("конца месяца" in C.gift_month_text({"amount": 0.25, "until": ""}), "нет даты — «до конца месяца»")
eng = (ROOT / "core/engine.py").read_text(encoding="utf-8")
ok("self.cloud.on_gift" in eng and '"Подарок месяца"' in eng, "компьютер: уведомление «Подарок месяца»")
app = (ROOT / "android/assets/www/app.js").read_text(encoding="utf-8")
ok("function giftNote(" in app and "giftNote(cloudInfo)" in app and "S.giftSeen = g.until" in app, "телефон: то же, один раз за месяц")
print("ALL OK" if not bad else f"FAILED {bad}")
sys.exit(1 if bad else 0)
