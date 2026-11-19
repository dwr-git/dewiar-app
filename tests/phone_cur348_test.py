"""Идея №348 (19.11, телефон): «записываю доходы и расходы в молдавских леях — MDL нет». Валюта трат на телефоне
бралась по часовому поясу, но знали только Минск, Киев и Казахстан — в Молдове (и везде ещё) записывалось в рублях.
Теперь — как на компьютере (core/money.py COUNTRY_CUR): леи, лари, драмы, злотые, евро, доллары…"""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


js = r"""const src = require('fs').readFileSync(process.argv[1], 'utf8'); const a = src.indexOf('const CUR_TZ'), b = src.indexOf('const CUR = ');
eval(src.slice(a, b).replace('const CUR_TZ', 'globalThis.CUR_TZ'));
const f = (tz) => { const h = CUR_TZ.find(([rx]) => rx.test(tz)); return h ? h[1] : 'RUB'; };
console.log(JSON.stringify(JSON.parse(process.argv[2]).map(f)));"""
TZ = {"Europe/Chisinau": "MDL", "Europe/Minsk": "BYN", "Europe/Moscow": "RUB", "Europe/Kyiv": "UAH", "Asia/Almaty": "KZT",
      "Asia/Tbilisi": "GEL", "Asia/Yerevan": "AMD", "Europe/Warsaw": "PLN", "Europe/Berlin": "EUR", "America/New_York": "USD",
      "Europe/London": "GBP", "Asia/Tashkent": "UZS"}
r = json.loads(subprocess.run(["node", "-e", js, str(ROOT / "android/assets/www/app.js"), json.dumps(list(TZ))], capture_output=True, text=True).stdout or "null")
ok(r == list(TZ.values()), f"телефон: валюта по часовому поясу — {dict(zip(TZ, r or []))}")
from money import CURRENCIES, COUNTRY_CUR  # noqa: E402
ok(set(TZ.values()) <= set(CURRENCIES), "те же валюты, что знает компьютер (core/money.py)")
ok(COUNTRY_CUR.get("MD") == "MDL", "компьютер: Молдова — леи")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
