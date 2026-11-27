"""№350 (20.11): «Проработать формулировки времени: без 5 шесть, без 10 двенадцать — и чтобы предлагала утро или вечер».
Время, как его говорят, — и на компьютере (when.py), и на телефоне (10-time.js): «без пяти шесть», «без четверти восемь
вечера», «полшестого», «в половине шестого», «в четверть девятого», «в 5 минут седьмого». «Без 5 рублей» — не время.
Час без «утра/вечера», уже прошедший сегодня, — вечером и подсказка, как поправить (на компьютере — guessed для модели,
на телефоне — в ответе); будильник — как сказано."""
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import when  # noqa: E402
NOW = datetime(2026, 11, 20, 9, 0)
CASES = {"напомни без пяти шесть позвонить": "17:55", "напомни без 10 двенадцать": "11:50",
         "напомни без четверти восемь вечера выключить духовку": "19:45", "напомни в полшестого забрать сына": "17:30",
         "напомни в половине шестого": "17:30", "напомни в четверть девятого": "20:15", "напомни в 5 минут седьмого": "18:05",
         "напомни без пяти час": "12:55", "разбуди без пятнадцати семь": "06:45"}
for t, hm in CASES.items():
    r = when.parse(t, now=NOW)
    ok(r and r["at"].strftime("%H:%M") == hm, f"компьютер: «{t}» → {hm} ({r and r['at'].strftime('%H:%M')})")
ok(when.parse("напомни купить хлеб без 5 рублей", now=NOW) is None, "«без 5 рублей» — не время")
r = when.parse("напомни без пяти шесть позвонить", now=NOW)
ok(r["text"] == "Позвонить" and r.get("guessed") == ("05:55", "17:55"), f"компьютер: утро или вечер — модели подсказка: {r.get('guessed')}")

node = shutil.which("node")
if node:
    js = r"""
const fs = require("fs"), vm = require("vm"), root = process.argv[2];
const ctx = { console, Date, String, Math, RegExp, Object, JSON, pad: n => String(n).padStart(2, "0"), LBRX: (a, b) => new RegExp(a, b),
  whenDays: () => null, repNorm: x => x, rollRepeat: d => d, window: {}, D: {},
  document: { addEventListener() {}, getElementById() { return null; }, querySelector() { return null; }, querySelectorAll() { return []; } } };
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(root + "/android/www-src/app/10-time.js", "utf8") + ";this.parseWhen=parseWhen;this.dayHalf=dayHalf;", ctx);
const now = new Date(2026, 10, 20, 9, 0), out = {};
for (const t of JSON.parse(process.argv[3])) { const w = ctx.parseWhen(t, now); const h = w ? ctx.dayHalf(w, now) : "";
  out[t] = w ? [String(w.at.getHours()).padStart(2, "0") + ":" + String(w.at.getMinutes()).padStart(2, "0"), h] : null; }
console.log(JSON.stringify(out));
"""
    f = Path(os.environ.get("TMPDIR", "/tmp")) / "colloq350.js"
    f.write_text(js, encoding="utf-8")
    ph = {k.replace("напомни ", "").replace("разбуди ", ""): v for k, v in CASES.items() if not k.startswith("разбуди")}
    ph.update({"в 3 позвонить": "15:00", "в 10 позвонить": "10:00"})
    r = subprocess.run([node, str(f), str(ROOT), json.dumps(list(ph) + ["купить хлеб без 5 рублей"], ensure_ascii=False)],
                       capture_output=True, text=True, timeout=60)
    if r.returncode:
        print(r.stderr[-600:])
    d = json.loads(r.stdout or "{}")
    for t, hm in ph.items():
        ok(d.get(t) and d[t][0] == hm, f"телефон: «{t}» → {hm} ({d.get(t)})")
    ok(d.get("купить хлеб без 5 рублей") is None, "телефон: «без 5 рублей» — не время")
    ok("Если нужно в 3 утра — поправьте время в карточке." in (d.get("в 3 позвонить") or ["", ""])[1] and not d["в 10 позвонить"][1],
       "телефон: «в 3», а 3:00 прошло — 15:00 и как поправить; «в 10» — без подсказки")
    f.unlink()
cmd = (ROOT / "android/www-src/app/11-commands.js").read_text(encoding="utf-8")
ok("const half = dayHalf(w);" in cmd and "${what}.${half}`" in cmd, "телефон: подсказка — только у напоминаний (будильник — как сказано)")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
