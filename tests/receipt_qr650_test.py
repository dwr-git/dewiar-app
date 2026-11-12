"""№650 (телефон 0.9.28, 11.11, McDuck): «сканер QR-кода чеков… и бухгалтерия расходов». QR кассового чека России
(«t=20261111T1530&s=1234.00&fn=…&i=…&fp=…&n=1») несёт сумму и время покупки. Сканер на телефоне узнаёт чек и предлагает
«Записать трату» с датой чека; возврат (n=2) — доходом; тот же чек второй раз не записывается."""
import json, os, re, subprocess, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


src = (ROOT / "android/assets/www/app.js").read_text(encoding="utf-8")
m = re.search(r"^function receiptQr\(t\) \{.*?^\}", src, re.S | re.M)
ok(bool(m), "app.js: receiptQr")
cases = ["t=20261111T1530&s=1234.50&fn=9960440300123456&i=12345&fp=1234567890&n=1",
         "t=20261105T0907&s=99.00&fn=9289000100&i=7&fp=55&n=2",
         "t=20261105T0907&s=0&fn=9289000100&i=7&fp=55&n=1",
         "https://example.com/?t=1", "просто текст", "t=20261105T09&s=10&fn=1"]
js = m.group(0) + "\nconsole.log(JSON.stringify(" + json.dumps(cases) + ".map(receiptQr)));"
out = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=30)
r = json.loads(out.stdout or "null") or [None] * len(cases)
ok(r[0] == {"date": "2026-11-11", "time": "15:30", "sum": 1234.5, "kind": "expense", "id": "чек 9960440300123456/12345/1234567890"},
   f"чек: сумма, дата, время, трата: {r[0]}")
ok(r[1] and r[1]["kind"] == "income" and r[1]["sum"] == 99, "возврат прихода (n=2) — доход")
ok(r[2] is None and r[3] is None and r[4] is None and r[5] is None, "нулевая сумма, ссылка, текст, обрывок — не чек")
ok("const rc = receiptQr(t);\n  if (rc) return receiptOffer(rc);" in src, "сканер: чек узнаётся до «В коде: …»")
i = src.find("function receiptOffer(rc)")
body = src[i:i + 3200]
ok("money().some(x => String(x.note || \"\").includes(rc.id))" in body and "Этот чек уже записан" in body, "тот же чек второй раз не записывается")
ok("date: rc.date" in body and 'currency: cur' in body and 'rc.cur || "RUB"' in body and "famShareSpend(x)" in body,
   "запись с датой чека, в рублях (чек России; электронный чек Беларуси — в BYN, №666), и в общий бюджет семьи")
ok('sub: "QR, чек, штрихкод' in src, "в сканере подсказка: «чек»")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
