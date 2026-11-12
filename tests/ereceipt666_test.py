"""№666 (телефон 0.9.32, 12.11, Сергей, Беларусь): «при сканировании QR-кода не добавляет в расходы». У белорусского
электронного чека в QR только ссылка (r.eplus.by/…) — суммы в коде нет; модель пообещала «сразу внесу расход», а потом
вписала трату с суммой прошлого дохода. Теперь: сканер узнаёт электронный чек, читает его страницу и предлагает
«Записать трату» в BYN; не прочиталось — честно просит назвать сумму. Что показал сканер — в истории разговора, и
сканер не обещает модели «запишу сам»."""
import json, os, re, subprocess, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


src = (ROOT / "android/assets/www/app.js").read_text(encoding="utf-8")
js = r'''
const src = require("fs").readFileSync(process.argv[1], "utf8");
const pick = (name) => { const i = src.indexOf(name); const j = src.indexOf("\n}\n", i); return src.slice(i, j + 3); };
eval(src.slice(src.indexOf("const ERECEIPT"), src.indexOf("\n", src.indexOf("const ERECEIPT"))) + "\n" + pick("function ereceiptHost") + pick("function ereceiptParse"));
console.log(JSON.stringify([
  !!ereceiptHost("https://r.eplus.by/5B4A0B-9408C93F-A8BC"), !!ereceiptHost("https://example.com/r.eplus.by"),
  ereceiptParse('<div>Магазин</div><div>12.11.2026 13:31</div><td>Хлеб</td><td>1,89</td><div>ИТОГО: <b>42,10</b> BYN</div>'),
  ereceiptParse('<div>Итого к оплате 1 234,50 руб.</div>'),
  ereceiptParse('<div id="app"></div><script>var x="ИТОГО 5";</script>')]));
'''
out = subprocess.run(["node", "-e", js, str(ROOT / "android/assets/www/app.js")], capture_output=True, text=True, timeout=30)
r = json.loads(out.stdout or "null") or [None] * 5
ok(r[0] is True and r[1] is False, "ссылка r.eplus.by — электронный чек Беларуси; чужой сайт с таким словом в пути — нет")
ok(r[2] == {"sum": 42.1, "date": "2026-11-12", "time": "13:31"}, f"страница чека: итог и дата покупки: {r[2]}")
ok(r[3] and r[3]["sum"] == 1234.5, f"«Итого к оплате 1 234,50» — тоже сумма: {r[3]}")
ok(r[4] is None, "пустая страница (рисуется скриптом) — суммы нет, не выдумываем")
i = src.find("async function ereceiptFlow")
body = src[i:i + 1500]
ok('window.t("scan.ereceipt.nosum")' in body and "D.openUrl(url)" in body and "cur: er.cur" in body,
   "не прочиталось — просим назвать сумму и даём открыть чек; прочиталось — «Записать трату» в валюте чека")
ok("const er = ereceiptHost(t);\n    if (er) return ereceiptFlow(t, er);" in src, "сканер узнаёт электронный чек раньше «В коде ссылка»")
ok(src.count("scanNote(") >= 6, "что показал сканер — в истории разговора (ссылка, текст, чек, запись)")
ru = json.loads((ROOT / "data/i18n/ru.json").read_text(encoding="utf-8"))
ok("сама не записывай" in ru["tool.scan_code.opened"] and "внесу" not in ru["tool.scan_code.opened"], "сканер не обещает модели «запишу сам» и запрещает выдумывать сумму")
ok('currency: cur' in src and '"money.word.BYN"' in src, "трата — в валюте чека (BYN), голосом — «белорусских рублей»")
ex = (ROOT / "android/assets/www/exam.js").read_text(encoding="utf-8")
ok('id: "scan_no_invent"' in ex, "экзамен телефона: «я отсканировал, запиши» без суммы — не выдумывает трату")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
